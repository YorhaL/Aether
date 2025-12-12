"""
并发管理器 - 支持 Redis 或内存的并发控制

功能：
1. Endpoint 级别的并发限制
2. ProviderAPIKey 级别的并发限制
3. 分布式环境下优先使用 Redis，多实例共享
4. 在开发/单实例场景下自动降级为内存计数
5. 自动释放和异常处理（Redis 提供 TTL，内存模式请确保手动释放）
"""

import asyncio
import math
import os
from contextlib import asynccontextmanager
from datetime import timedelta  # noqa: F401 - kept for potential future use
from typing import Optional, Tuple

import redis.asyncio as aioredis
from src.core.logger import logger


class ConcurrencyManager:
    """分布式并发管理器"""

    _instance: Optional["ConcurrencyManager"] = None
    _redis: Optional[aioredis.Redis] = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化内存后端结构（只执行一次）"""
        if hasattr(self, "_memory_initialized"):
            return

        self._memory_lock: asyncio.Lock = asyncio.Lock()
        self._memory_endpoint_counts: dict[str, int] = {}
        self._memory_key_counts: dict[str, int] = {}
        self._memory_initialized = True

    async def initialize(self) -> None:
        """初始化 Redis 连接"""
        if self._redis is not None:
            return

        # 优先使用 REDIS_URL，如果没有则根据密码构建 URL
        redis_url = os.getenv("REDIS_URL")

        if not redis_url:
            # 本地开发模式：从 REDIS_PASSWORD 构建 URL
            redis_password = os.getenv("REDIS_PASSWORD")
            if redis_password:
                redis_url = f"redis://:{redis_password}@localhost:6379/0"
            else:
                redis_url = "redis://localhost:6379/0"

        try:
            self._redis = await aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
            # 测试连接
            await self._redis.ping()
            # 脱敏显示（隐藏密码）
            safe_url = redis_url.split("@")[-1] if "@" in redis_url else redis_url
            logger.info(f"[OK] Redis 连接成功: {safe_url}")
        except Exception as e:
            logger.error(f"[ERROR] Redis 连接失败: {e}")
            logger.warning("[WARN] 并发控制将被禁用（仅在单实例环境下安全）")
            self._redis = None

    async def close(self) -> None:
        """关闭 Redis 连接"""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("Redis 连接已关闭")

    def _get_endpoint_key(self, endpoint_id: str) -> str:
        """获取 Endpoint 并发计数的 Redis Key"""
        return f"concurrency:endpoint:{endpoint_id}"

    def _get_key_key(self, key_id: str) -> str:
        """获取 ProviderAPIKey 并发计数的 Redis Key"""
        return f"concurrency:key:{key_id}"

    async def get_current_concurrency(
        self, endpoint_id: Optional[str] = None, key_id: Optional[str] = None
    ) -> Tuple[int, int]:
        """
        获取当前并发数

        Args:
            endpoint_id: Endpoint ID（可选）
            key_id: ProviderAPIKey ID（可选）

        Returns:
            (endpoint_concurrency, key_concurrency)
        """
        if self._redis is None:
            async with self._memory_lock:
                endpoint_count = (
                    self._memory_endpoint_counts.get(endpoint_id, 0) if endpoint_id else 0
                )
                key_count = self._memory_key_counts.get(key_id, 0) if key_id else 0
                return endpoint_count, key_count

        endpoint_count = 0
        key_count = 0

        try:
            if endpoint_id:
                endpoint_key = self._get_endpoint_key(endpoint_id)
                result = await self._redis.get(endpoint_key)
                endpoint_count = int(result) if result else 0

            if key_id:
                key_key = self._get_key_key(key_id)
                result = await self._redis.get(key_key)
                key_count = int(result) if result else 0

        except Exception as e:
            logger.error(f"获取并发数失败: {e}")

        return endpoint_count, key_count

    async def check_available(
        self,
        endpoint_id: str,
        endpoint_max_concurrent: Optional[int],
        key_id: str,
        key_max_concurrent: Optional[int],
    ) -> bool:
        """
        检查是否可以获取并发槽位（不实际获取）

        Args:
            endpoint_id: Endpoint ID
            endpoint_max_concurrent: Endpoint 最大并发数（None 表示不限制）
            key_id: ProviderAPIKey ID
            key_max_concurrent: Key 最大并发数（None 表示不限制）

        Returns:
            是否可用（True/False）
        """
        if self._redis is None:
            async with self._memory_lock:
                endpoint_count = self._memory_endpoint_counts.get(endpoint_id, 0)
                key_count = self._memory_key_counts.get(key_id, 0)

                if (
                    endpoint_max_concurrent is not None
                    and endpoint_count >= endpoint_max_concurrent
                ):
                    return False

                if key_max_concurrent is not None and key_count >= key_max_concurrent:
                    return False

                return True

        endpoint_count, key_count = await self.get_current_concurrency(endpoint_id, key_id)

        # 检查 Endpoint 级别限制
        if endpoint_max_concurrent is not None and endpoint_count >= endpoint_max_concurrent:
            return False

        # 检查 Key 级别限制
        if key_max_concurrent is not None and key_count >= key_max_concurrent:
            return False

        return True

    async def acquire_slot(
        self,
        endpoint_id: str,
        endpoint_max_concurrent: Optional[int],
        key_id: str,
        key_max_concurrent: Optional[int],
        is_cached_user: bool = False,  # 新增：是否是缓存用户
        cache_reservation_ratio: Optional[float] = None,  # 缓存预留比例，None 时从配置读取
        ttl_seconds: Optional[int] = None,  # TTL 秒数，None 时从配置读取
    ) -> bool:
        """
        尝试获取并发槽位（支持缓存用户优先级）

        Args:
            endpoint_id: Endpoint ID
            endpoint_max_concurrent: Endpoint 最大并发数（None 表示不限制）
            key_id: ProviderAPIKey ID
            key_max_concurrent: Key 最大并发数（None 表示不限制）
            is_cached_user: 是否是缓存用户（缓存用户可使用全部槽位）
            cache_reservation_ratio: 缓存预留比例，None 时从配置读取
            ttl_seconds: TTL 秒数，None 时从配置读取

        Returns:
            是否成功获取（True/False）

        缓存预留机制说明:
        - 假设 key_max_concurrent = 10, cache_reservation_ratio = 0.3
        - 新用户最多使用: 7个槽位 (10 * (1 - 0.3))
        - 缓存用户最多使用: 10个槽位（全部）
        - 预留的3个槽位专门给缓存用户，保证他们的请求优先
        """
        # 从配置读取默认值
        from src.config.settings import config

        if cache_reservation_ratio is None:
            cache_reservation_ratio = config.cache_reservation_ratio
        if ttl_seconds is None:
            ttl_seconds = config.concurrency_slot_ttl

        if self._redis is None:
            async with self._memory_lock:
                endpoint_count = self._memory_endpoint_counts.get(endpoint_id, 0)
                key_count = self._memory_key_counts.get(key_id, 0)

                # Endpoint 限制
                if (
                    endpoint_max_concurrent is not None
                    and endpoint_count >= endpoint_max_concurrent
                ):
                    return False

                # Key 限制，包含缓存预留
                if key_max_concurrent is not None:
                    if is_cached_user:
                        if key_count >= key_max_concurrent:
                            return False
                    else:
                        available_for_new = max(
                            1, math.ceil(key_max_concurrent * (1 - cache_reservation_ratio))
                        )
                        if key_count >= available_for_new:
                            return False

                # 通过限制，更新计数
                self._memory_endpoint_counts[endpoint_id] = endpoint_count + 1
                self._memory_key_counts[key_id] = key_count + 1
                return True

        endpoint_key = self._get_endpoint_key(endpoint_id)
        key_key = self._get_key_key(key_id)

        try:
            # 使用 Lua 脚本保证原子性（新增缓存预留逻辑）
            lua_script = """
            local endpoint_key = KEYS[1]
            local key_key = KEYS[2]
            local endpoint_max = tonumber(ARGV[1])
            local key_max = tonumber(ARGV[2])
            local ttl = tonumber(ARGV[3])
            local is_cached = tonumber(ARGV[4])  -- 0=新用户, 1=缓存用户
            local cache_ratio = tonumber(ARGV[5])  -- 缓存预留比例

            -- 获取当前值
            local endpoint_count = tonumber(redis.call('GET', endpoint_key) or '0')
            local key_count = tonumber(redis.call('GET', key_key) or '0')

            -- 检查 endpoint 限制（-1 表示不限制）
            if endpoint_max >= 0 and endpoint_count >= endpoint_max then
                return 0  -- 失败：endpoint 已满
            end

            -- 检查 key 限制（支持缓存预留）
            if key_max >= 0 then
                if is_cached == 0 then
                    -- 新用户：只能使用 (1 - cache_ratio) 的槽位
                    local available_for_new = math.floor(key_max * (1 - cache_ratio))
                    if key_count >= available_for_new then
                        return 0  -- 失败：新用户配额已满
                    end
                else
                    -- 缓存用户：可以使用全部槽位
                    if key_count >= key_max then
                        return 0  -- 失败：总配额已满
                    end
                end
            end

            -- 增加计数
            redis.call('INCR', endpoint_key)
            redis.call('EXPIRE', endpoint_key, ttl)
            redis.call('INCR', key_key)
            redis.call('EXPIRE', key_key, ttl)

            return 1  -- 成功
            """

            # 执行脚本
            result = await self._redis.eval(
                lua_script,
                2,  # 2 个 KEYS
                endpoint_key,
                key_key,
                endpoint_max_concurrent if endpoint_max_concurrent is not None else -1,
                key_max_concurrent if key_max_concurrent is not None else -1,
                ttl_seconds,
                1 if is_cached_user else 0,  # 缓存用户标志
                cache_reservation_ratio,  # 预留比例
            )

            success = result == 1

            if success:
                user_type = "缓存用户" if is_cached_user else "新用户"
                logger.debug(
                    f"[OK] 获取并发槽位成功: endpoint={endpoint_id}, key={key_id}, "
                    f"类型={user_type}"
                )
            else:
                endpoint_count, key_count = await self.get_current_concurrency(endpoint_id, key_id)

                # 计算新用户可用槽位
                if key_max_concurrent and not is_cached_user:
                    available_for_new = int(key_max_concurrent * (1 - cache_reservation_ratio))
                    user_info = f"新用户配额={available_for_new}, 当前={key_count}"
                else:
                    user_info = f"缓存用户, 当前={key_count}/{key_max_concurrent}"

                logger.warning(
                    f"[WARN] 并发槽位已满: endpoint={endpoint_id}({endpoint_count}/{endpoint_max_concurrent}), "
                    f"key={key_id}({user_info})"
                )

            return success

        except Exception as e:
            logger.error(f"获取并发槽位失败，降级到内存模式: {e}")
            # Redis 异常时降级到内存模式进行保守限流
            # 使用较低的限制值（原限制的 50%）避免上游 API 被打爆
            async with self._memory_lock:
                endpoint_count = self._memory_endpoint_counts.get(endpoint_id, 0)
                key_count = self._memory_key_counts.get(key_id, 0)

                # 降级模式下使用更保守的限制（50%）
                fallback_endpoint_limit = (
                    max(1, endpoint_max_concurrent // 2)
                    if endpoint_max_concurrent is not None
                    else None
                )
                fallback_key_limit = (
                    max(1, key_max_concurrent // 2) if key_max_concurrent is not None else None
                )

                if (
                    fallback_endpoint_limit is not None
                    and endpoint_count >= fallback_endpoint_limit
                ):
                    logger.warning(
                        f"[FALLBACK] Endpoint 并发达到降级限制: {endpoint_count}/{fallback_endpoint_limit}"
                    )
                    return False

                if fallback_key_limit is not None and key_count >= fallback_key_limit:
                    logger.warning(
                        f"[FALLBACK] Key 并发达到降级限制: {key_count}/{fallback_key_limit}"
                    )
                    return False

                # 更新内存计数
                self._memory_endpoint_counts[endpoint_id] = endpoint_count + 1
                self._memory_key_counts[key_id] = key_count + 1
                logger.debug(
                    f"[FALLBACK] 使用内存模式获取槽位: endpoint={endpoint_id}, key={key_id}"
                )
                return True

    async def release_slot(self, endpoint_id: str, key_id: str) -> None:
        """
        释放并发槽位

        Args:
            endpoint_id: Endpoint ID
            key_id: ProviderAPIKey ID
        """
        if self._redis is None:
            async with self._memory_lock:
                if endpoint_id in self._memory_endpoint_counts:
                    self._memory_endpoint_counts[endpoint_id] = max(
                        0, self._memory_endpoint_counts[endpoint_id] - 1
                    )
                    if self._memory_endpoint_counts[endpoint_id] == 0:
                        self._memory_endpoint_counts.pop(endpoint_id, None)

                if key_id in self._memory_key_counts:
                    self._memory_key_counts[key_id] = max(0, self._memory_key_counts[key_id] - 1)
                    if self._memory_key_counts[key_id] == 0:
                        self._memory_key_counts.pop(key_id, None)
            return

        endpoint_key = self._get_endpoint_key(endpoint_id)
        key_key = self._get_key_key(key_id)

        try:
            # 使用 Lua 脚本保证原子性（不会减到负数）
            lua_script = """
            local endpoint_key = KEYS[1]
            local key_key = KEYS[2]

            local endpoint_count = tonumber(redis.call('GET', endpoint_key) or '0')
            local key_count = tonumber(redis.call('GET', key_key) or '0')

            if endpoint_count > 0 then
                redis.call('DECR', endpoint_key)
            end

            if key_count > 0 then
                redis.call('DECR', key_key)
            end

            return 1
            """

            await self._redis.eval(lua_script, 2, endpoint_key, key_key)

            logger.debug(f"[OK] 释放并发槽位: endpoint={endpoint_id}, key={key_id}")

        except Exception as e:
            logger.error(f"释放并发槽位失败: {e}")

    @asynccontextmanager
    async def concurrency_guard(
        self,
        endpoint_id: str,
        endpoint_max_concurrent: Optional[int],
        key_id: str,
        key_max_concurrent: Optional[int],
        is_cached_user: bool = False,  # 新增：是否是缓存用户
        cache_reservation_ratio: Optional[float] = None,  # 缓存预留比例，None 时从配置读取
    ):
        """
        并发控制上下文管理器（支持缓存用户优先级）

        用法：
            async with manager.concurrency_guard(
                endpoint_id, endpoint_max, key_id, key_max,
                is_cached_user=True  # 缓存用户
            ):
                # 执行请求
                response = await send_request(...)

        如果获取失败，会抛出 ConcurrencyLimitError 异常
        """
        # 从配置读取默认值
        from src.config.settings import config

        if cache_reservation_ratio is None:
            cache_reservation_ratio = config.cache_reservation_ratio

        # 尝试获取槽位（传递缓存用户参数）
        acquired = await self.acquire_slot(
            endpoint_id,
            endpoint_max_concurrent,
            key_id,
            key_max_concurrent,
            is_cached_user,
            cache_reservation_ratio,
        )

        if not acquired:
            from src.core.exceptions import ConcurrencyLimitError

            user_type = "缓存用户" if is_cached_user else "新用户"
            raise ConcurrencyLimitError(
                f"并发限制已达上限: endpoint={endpoint_id}, key={key_id}, 类型={user_type}"
            )

        # 记录开始时间和状态
        import time

        slot_acquired_at = time.time()
        exception_occurred = False

        try:
            yield  # 执行请求
        except Exception as e:
            # 记录异常
            exception_occurred = True
            raise
        finally:
            # 计算槽位占用时长
            slot_duration = time.time() - slot_acquired_at

            # 记录 Prometheus 指标
            try:
                from src.core.metrics import (
                    concurrency_slot_duration_seconds,
                    concurrency_slot_release_total,
                )

                # 记录槽位占用时长分布
                concurrency_slot_duration_seconds.labels(
                    key_id=key_id[:8] if key_id else "unknown",  # 只记录前8位
                    exception=str(exception_occurred),
                ).observe(slot_duration)

                # 记录槽位释放计数
                concurrency_slot_release_total.labels(
                    key_id=key_id[:8] if key_id else "unknown", exception=str(exception_occurred)
                ).inc()

                # 告警：槽位占用时间过长（超过 60 秒）
                if slot_duration > 60:
                    logger.warning(
                        f"[WARN] 并发槽位占用时间过长: "
                        f"key_id={key_id[:8] if key_id else 'unknown'}..., "
                        f"duration={slot_duration:.1f}s, "
                        f"exception={exception_occurred}"
                    )

            except Exception as metric_error:
                # 指标记录失败不应影响业务逻辑
                logger.debug(f"记录并发指标失败: {metric_error}")

            # 自动释放槽位（即使发生异常）
            await self.release_slot(endpoint_id, key_id)

    async def reset_concurrency(
        self, endpoint_id: Optional[str] = None, key_id: Optional[str] = None
    ) -> None:
        """
        重置并发计数（管理功能，慎用）

        Args:
            endpoint_id: Endpoint ID（可选，None 表示重置所有 endpoint）
            key_id: ProviderAPIKey ID（可选，None 表示重置所有 key）
        """
        if self._redis is None:
            async with self._memory_lock:
                if endpoint_id:
                    self._memory_endpoint_counts.pop(endpoint_id, None)
                    logger.info(f"[RESET] 重置 Endpoint 并发计数(内存): {endpoint_id}")
                else:
                    count = len(self._memory_endpoint_counts)
                    self._memory_endpoint_counts.clear()
                    if count:
                        logger.info(f"[RESET] 重置所有 Endpoint 并发计数(内存): {count} 个")

                if key_id:
                    self._memory_key_counts.pop(key_id, None)
                    logger.info(f"[RESET] 重置 Key 并发计数(内存): {key_id}")
                else:
                    count = len(self._memory_key_counts)
                    self._memory_key_counts.clear()
                    if count:
                        logger.info(f"[RESET] 重置所有 Key 并发计数(内存): {count} 个")
            return

        try:
            if endpoint_id:
                endpoint_key = self._get_endpoint_key(endpoint_id)
                await self._redis.delete(endpoint_key)
                logger.info(f"[RESET] 重置 Endpoint 并发计数: {endpoint_id}")
            else:
                # 重置所有 endpoint
                keys = await self._redis.keys("concurrency:endpoint:*")
                if keys:
                    await self._redis.delete(*keys)
                    logger.info(f"[RESET] 重置所有 Endpoint 并发计数: {len(keys)} 个")

            if key_id:
                key_key = self._get_key_key(key_id)
                await self._redis.delete(key_key)
                logger.info(f"[RESET] 重置 Key 并发计数: {key_id}")
            else:
                # 重置所有 key
                keys = await self._redis.keys("concurrency:key:*")
                if keys:
                    await self._redis.delete(*keys)
                    logger.info(f"[RESET] 重置所有 Key 并发计数: {len(keys)} 个")

        except Exception as e:
            logger.error(f"重置并发计数失败: {e}")


# 全局单例
_concurrency_manager: Optional[ConcurrencyManager] = None


async def get_concurrency_manager() -> ConcurrencyManager:
    """获取全局 ConcurrencyManager 实例"""
    global _concurrency_manager

    if _concurrency_manager is None:
        _concurrency_manager = ConcurrencyManager()
        await _concurrency_manager.initialize()

    return _concurrency_manager

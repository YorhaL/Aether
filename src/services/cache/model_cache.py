"""
Model 映射缓存服务 - 减少模型查询

架构说明
========
本服务采用混合 async/sync 模式：
- 缓存操作（CacheService）：真正的 async，使用 aioredis
- 数据库查询（db.query）：同步的 SQLAlchemy Session

设计决策
--------
1. 保持 async 方法签名：因为缓存命中时完全异步，性能最优
2. 缓存未命中时的同步查询：FastAPI 会在线程池中执行，不会阻塞事件循环
3. 调用方必须在 async 上下文中使用 await

使用示例
--------
    global_model = await ModelCacheService.resolve_global_model_by_name_or_mapping(db, "gpt-4")
"""

import time
from typing import List, Optional

from sqlalchemy.orm import Session

from src.config.constants import CacheTTL
from src.core.cache_service import CacheService
from src.core.logger import logger
from src.core.metrics import (
    model_mapping_conflict_total,
    model_mapping_resolution_duration_seconds,
    model_mapping_resolution_total,
)
from src.models.database import GlobalModel, Model


class ModelCacheService:
    """Model 映射缓存服务

    提供 GlobalModel 和 Model 的缓存查询功能，减少数据库访问。
    所有公开方法均为 async，需要在 async 上下文中调用。
    """

    # 缓存 TTL（秒）- 使用统一常量
    CACHE_TTL = CacheTTL.MODEL

    @staticmethod
    async def get_model_by_id(db: Session, model_id: str) -> Optional[Model]:
        """
        获取 Model（带缓存）

        Args:
            db: 数据库会话
            model_id: Model ID

        Returns:
            Model 对象或 None
        """
        cache_key = f"model:id:{model_id}"

        # 1. 尝试从缓存获取
        cached_data = await CacheService.get(cache_key)
        if cached_data:
            logger.debug(f"Model 缓存命中: {model_id}")
            return ModelCacheService._dict_to_model(cached_data)

        # 2. 缓存未命中，查询数据库
        model = db.query(Model).filter(Model.id == model_id).first()

        # 3. 写入缓存
        if model:
            model_dict = ModelCacheService._model_to_dict(model)
            await CacheService.set(cache_key, model_dict, ttl_seconds=ModelCacheService.CACHE_TTL)
            logger.debug(f"Model 已缓存: {model_id}")

        return model

    @staticmethod
    async def get_global_model_by_id(db: Session, global_model_id: str) -> Optional[GlobalModel]:
        """
        获取 GlobalModel（带缓存）

        Args:
            db: 数据库会话
            global_model_id: GlobalModel ID

        Returns:
            GlobalModel 对象或 None
        """
        cache_key = f"global_model:id:{global_model_id}"

        # 1. 尝试从缓存获取
        cached_data = await CacheService.get(cache_key)
        if cached_data:
            logger.debug(f"GlobalModel 缓存命中: {global_model_id}")
            return ModelCacheService._dict_to_global_model(cached_data)

        # 2. 缓存未命中，查询数据库
        global_model = db.query(GlobalModel).filter(GlobalModel.id == global_model_id).first()

        # 3. 写入缓存
        if global_model:
            global_model_dict = ModelCacheService._global_model_to_dict(global_model)
            await CacheService.set(
                cache_key, global_model_dict, ttl_seconds=ModelCacheService.CACHE_TTL
            )
            logger.debug(f"GlobalModel 已缓存: {global_model_id}")

        return global_model

    @staticmethod
    async def get_model_by_provider_and_global_model(
        db: Session, provider_id: str, global_model_id: str
    ) -> Optional[Model]:
        """
        通过 Provider ID 和 GlobalModel ID 获取 Model（带缓存）

        Args:
            db: 数据库会话
            provider_id: Provider ID
            global_model_id: GlobalModel ID

        Returns:
            Model 对象或 None
        """
        cache_key = f"model:provider_global:{provider_id}:{global_model_id}"
        hit_count_key = f"model:provider_global:hits:{provider_id}:{global_model_id}"

        # 1. 尝试从缓存获取
        cached_data = await CacheService.get(cache_key)
        if cached_data:
            logger.debug(
                f"Model 缓存命中(provider+global): {provider_id[:8]}...+{global_model_id[:8]}..."
            )
            # 递增命中计数，同时刷新 TTL
            await CacheService.incr(hit_count_key, ttl_seconds=ModelCacheService.CACHE_TTL)
            return ModelCacheService._dict_to_model(cached_data)

        # 2. 缓存未命中，查询数据库
        model = (
            db.query(Model)
            .filter(
                Model.provider_id == provider_id,
                Model.global_model_id == global_model_id,
                Model.is_active == True,
            )
            .first()
        )

        # 3. 写入缓存
        if model:
            model_dict = ModelCacheService._model_to_dict(model)
            await CacheService.set(cache_key, model_dict, ttl_seconds=ModelCacheService.CACHE_TTL)
            # 重置命中计数（新缓存从1开始）
            await CacheService.set(hit_count_key, 1, ttl_seconds=ModelCacheService.CACHE_TTL)
            logger.debug(
                f"Model 已缓存(provider+global): {provider_id[:8]}...+{global_model_id[:8]}..."
            )

        return model

    @staticmethod
    async def get_global_model_by_name(db: Session, name: str) -> Optional[GlobalModel]:
        """
        通过名称获取 GlobalModel（带缓存）

        Args:
            db: 数据库会话
            name: GlobalModel 名称

        Returns:
            GlobalModel 对象或 None
        """
        cache_key = f"global_model:name:{name}"

        # 1. 尝试从缓存获取
        cached_data = await CacheService.get(cache_key)
        if cached_data:
            logger.debug(f"GlobalModel 缓存命中(名称): {name}")
            return ModelCacheService._dict_to_global_model(cached_data)

        # 2. 缓存未命中，查询数据库
        global_model = db.query(GlobalModel).filter(GlobalModel.name == name).first()

        # 3. 写入缓存
        if global_model:
            global_model_dict = ModelCacheService._global_model_to_dict(global_model)
            await CacheService.set(
                cache_key, global_model_dict, ttl_seconds=ModelCacheService.CACHE_TTL
            )
            logger.debug(f"GlobalModel 已缓存(名称): {name}")

        return global_model

    @staticmethod
    async def invalidate_model_cache(
        model_id: str,
        provider_id: Optional[str] = None,
        global_model_id: Optional[str] = None,
        provider_model_name: Optional[str] = None,
        provider_model_mappings: Optional[list] = None,
    ) -> None:
        """清除 Model 缓存

        Args:
            model_id: Model ID
            provider_id: Provider ID（用于清除 provider_global 缓存）
            global_model_id: GlobalModel ID（用于清除 provider_global 缓存）
            provider_model_name: provider_model_name（用于清除 resolve 缓存）
            provider_model_mappings: 映射名称列表（用于清除 resolve 缓存）
        """
        # 清除 model:id 缓存
        await CacheService.delete(f"model:id:{model_id}")

        # 清除 provider_global 缓存及其命中计数（如果提供了必要参数）
        if provider_id and global_model_id:
            await CacheService.delete(f"model:provider_global:{provider_id}:{global_model_id}")
            await CacheService.delete(f"model:provider_global:hits:{provider_id}:{global_model_id}")
            logger.debug(
                f"Model 缓存已清除: {model_id}, provider_global:{provider_id[:8]}...:{global_model_id[:8]}..."
            )
        else:
            logger.debug(f"Model 缓存已清除: {model_id}")

        # 清除 resolve 缓存（provider_model_name 和 mappings 可能都被用作解析 key）
        resolve_keys_to_clear = []
        if provider_model_name:
            resolve_keys_to_clear.append(provider_model_name)
        if provider_model_mappings:
            for mapping_entry in provider_model_mappings:
                if isinstance(mapping_entry, dict):
                    mapping_name = mapping_entry.get("name", "").strip()
                    if mapping_name:
                        resolve_keys_to_clear.append(mapping_name)

        for key in resolve_keys_to_clear:
            await CacheService.delete(f"global_model:resolve:{key}")

        if resolve_keys_to_clear:
            logger.debug(f"Model resolve 缓存已清除: {resolve_keys_to_clear}")

    @staticmethod
    async def invalidate_global_model_cache(global_model_id: str, name: Optional[str] = None) -> None:
        """清除 GlobalModel 缓存"""
        await CacheService.delete(f"global_model:id:{global_model_id}")
        if name:
            await CacheService.delete(f"global_model:name:{name}")
            # 同时清除 resolve 缓存，因为 GlobalModel.name 也是一个 resolve key
            await CacheService.delete(f"global_model:resolve:{name}")
        # 全量清除 resolve 缓存，确保映射规则变更后不命中旧缓存
        try:
            await CacheService.delete_pattern("global_model:resolve:*")
        except Exception as e:
            logger.error(f"GlobalModel resolve 缓存清除失败，可能导致映射不一致: {e}")
        logger.debug(f"GlobalModel 缓存已清除: {global_model_id}")

    @staticmethod
    async def invalidate_all_resolve_cache() -> None:
        """
        清除所有 GlobalModel 解析缓存

        在 Provider 启用/禁用时调用，因为 Provider 状态变更会影响模型解析结果。
        """
        try:
            deleted = await CacheService.delete_pattern("global_model:resolve:*")
            logger.debug(f"已清除 {deleted} 个 GlobalModel resolve 缓存")
        except Exception as e:
            logger.error(f"GlobalModel resolve 缓存清除失败: {e}")

    @staticmethod
    async def resolve_global_model_by_name_or_mapping(
        db: Session, model_name: str
    ) -> Optional[GlobalModel]:
        """
        通过名称解析 GlobalModel（带缓存）

        查找顺序：
        1. 检查缓存
        2. 直接匹配 GlobalModel.name
        3. 通过 provider_model_name 匹配（查询 Model 表）
        4. 通过 provider_model_mappings 匹配（查询 Model 表）
        5. 通过 GlobalModel.config.model_mappings 匹配（支持正则）

        注意：provider_model_mappings 是 Provider 级别的映射配置，可能存在跨 Provider 冲突；
        如匹配到多个 GlobalModel，将记录告警并选择第一个匹配结果。

        Args:
            db: 数据库会话
            model_name: 模型名称（可以是 GlobalModel.name 或 provider_model_name）

        Returns:
            GlobalModel 对象或 None
        """
        start_time = time.time()
        resolution_method = "not_found"
        cache_hit = False

        normalized_name = model_name.strip()
        if not normalized_name:
            return None

        cache_key = f"global_model:resolve:{normalized_name}"

        try:
            # 1. 尝试从缓存获取
            cached_data = await CacheService.get(cache_key)
            if cached_data:
                if cached_data == "NOT_FOUND":
                    # 缓存的负结果
                    cache_hit = True
                    resolution_method = "not_found"
                    logger.debug(f"GlobalModel 缓存命中(映射解析-未找到): {normalized_name}")
                    return None
                if isinstance(cached_data, dict) and "supported_capabilities" not in cached_data:
                    # 兼容旧缓存：字段不全时视为未命中，走 DB 刷新
                    logger.debug(f"GlobalModel 缓存命中但 schema 过旧，刷新: {normalized_name}")
                else:
                    cache_hit = True
                    resolution_method = "direct_match"  # 缓存命中时无法区分原始解析方式
                    logger.debug(f"GlobalModel 缓存命中(映射解析): {normalized_name}")
                    return ModelCacheService._dict_to_global_model(cached_data)

            # 2. 直接通过 GlobalModel.name 匹配（优先级最高）
            # 说明：如果存在同名 GlobalModel，应优先解析为 GlobalModel 本身，
            # 避免被某个 Provider 的 provider_model_name 误导导致解析到错误的 GlobalModel。
            global_model = (
                db.query(GlobalModel)
                .filter(GlobalModel.name == normalized_name, GlobalModel.is_active == True)
                .first()
            )

            if global_model:
                resolution_method = "direct_match"
                global_model_dict = ModelCacheService._global_model_to_dict(global_model)
                await CacheService.set(
                    cache_key, global_model_dict, ttl_seconds=ModelCacheService.CACHE_TTL
                )
                logger.debug(f"GlobalModel 已缓存(映射解析-直接匹配): {normalized_name}")
                return global_model

            # 3. 通过 provider_model_name 匹配
            from src.models.database import Provider

            models_with_global = (
                db.query(Model, GlobalModel)
                .join(Provider, Model.provider_id == Provider.id)
                .join(GlobalModel, Model.global_model_id == GlobalModel.id)
                .filter(
                    Provider.is_active == True,
                    Model.is_active == True,
                    GlobalModel.is_active == True,
                    Model.provider_model_name == normalized_name,
                )
                .all()
            )

            # 收集匹配的 GlobalModel（只通过 provider_model_name 匹配）
            matched_global_models: List[GlobalModel] = []
            seen_global_model_ids: set[str] = set()
            for model, gm in models_with_global:
                if gm.id not in seen_global_model_ids:
                    seen_global_model_ids.add(gm.id)
                    matched_global_models.append(gm)
                    logger.debug(
                        f"模型名称 '{normalized_name}' 通过 provider_model_name 匹配到 "
                        f"GlobalModel: {gm.name} (Model: {model.id[:8]}...)"
                    )

            # 如果通过 provider_model_name 找到了，返回
            if matched_global_models:
                resolution_method = "provider_model_name"

                if len(matched_global_models) > 1:
                    # 检测到冲突（多个不同的 GlobalModel 有相同的 provider_model_name）
                    model_names = [gm.name for gm in matched_global_models if gm.name]
                    logger.warning(
                        f"模型映射冲突: 名称 '{normalized_name}' 匹配到多个不同的 GlobalModel: "
                        f"{', '.join(model_names)}，使用第一个匹配结果"
                    )
                    # 记录冲突指标
                    model_mapping_conflict_total.inc()

                # 返回第一个匹配的 GlobalModel
                result_global_model = matched_global_models[0]
                global_model_dict = ModelCacheService._global_model_to_dict(result_global_model)
                await CacheService.set(
                    cache_key, global_model_dict, ttl_seconds=ModelCacheService.CACHE_TTL
                )
                logger.debug(
                    f"GlobalModel 已缓存(映射解析-{resolution_method}): {normalized_name} -> {result_global_model.name}"
                )
                return result_global_model

            # 4. 通过 provider_model_mappings 匹配
            models_with_mappings = (
                db.query(Model, GlobalModel)
                .join(Provider, Model.provider_id == Provider.id)
                .join(GlobalModel, Model.global_model_id == GlobalModel.id)
                .filter(
                    Provider.is_active == True,
                    Model.is_active == True,
                    GlobalModel.is_active == True,
                    Model.provider_model_mappings.isnot(None),
                )
                .all()
            )

            mapping_matched_global_models: List[GlobalModel] = []
            mapping_seen_ids: set[str] = set()
            for model, gm in models_with_mappings:
                raw_mappings = model.provider_model_mappings
                if not isinstance(raw_mappings, list):
                    continue
                for raw in raw_mappings:
                    if not isinstance(raw, dict):
                        continue
                    name = raw.get("name")
                    if not isinstance(name, str):
                        continue
                    if name.strip() != normalized_name:
                        continue
                    if gm.id not in mapping_seen_ids:
                        mapping_seen_ids.add(gm.id)
                        mapping_matched_global_models.append(gm)
                        logger.debug(
                            f"模型名称 '{normalized_name}' 通过 provider_model_mappings 匹配到 "
                            f"GlobalModel: {gm.name} (Model: {model.id[:8]}...)"
                        )
                    break

            if mapping_matched_global_models:
                resolution_method = "provider_model_mappings"

                if len(mapping_matched_global_models) > 1:
                    model_names = [gm.name for gm in mapping_matched_global_models if gm.name]
                    logger.warning(
                        f"模型映射冲突: 名称 '{normalized_name}' 匹配到多个不同的 GlobalModel: "
                        f"{', '.join(model_names)}，使用第一个匹配结果"
                    )
                    model_mapping_conflict_total.inc()

                # 按名称排序确保确定性
                result_global_model = sorted(
                    mapping_matched_global_models, key=lambda gm: gm.name or ""
                )[0]
                global_model_dict = ModelCacheService._global_model_to_dict(result_global_model)
                await CacheService.set(
                    cache_key, global_model_dict, ttl_seconds=ModelCacheService.CACHE_TTL
                )
                logger.debug(
                    f"GlobalModel 已缓存(映射解析-{resolution_method}): "
                    f"{normalized_name} -> {result_global_model.name}"
                )
                return result_global_model

            # 5. 通过 GlobalModel.config.model_mappings 匹配（支持正则）
            from sqlalchemy import func

            from src.core.model_permissions import match_model_with_pattern

            mapping_rows = (
                db.query(GlobalModel)
                .filter(
                    GlobalModel.is_active == True,
                    GlobalModel.config.isnot(None),
                    GlobalModel.config["model_mappings"].isnot(None),
                    func.jsonb_array_length(GlobalModel.config["model_mappings"]) > 0,
                )
                .all()
            )

            mapping_matches: List[GlobalModel] = []
            for gm in mapping_rows:
                config = gm.config or {}
                mappings = config.get("model_mappings")
                if not isinstance(mappings, list):
                    continue
                for pattern in mappings:
                    if isinstance(pattern, str) and match_model_with_pattern(
                        pattern, normalized_name
                    ):
                        mapping_matches.append(gm)
                        break

            if mapping_matches:
                resolution_method = "model_mappings"

                if len(mapping_matches) > 1:
                    model_names = [gm.name for gm in mapping_matches if gm.name]
                    logger.warning(
                        f"模型映射冲突: 名称 '{normalized_name}' 匹配到多个不同的 GlobalModel: "
                        f"{', '.join(model_names)}，使用第一个匹配结果"
                    )
                    model_mapping_conflict_total.inc()

                # 按名称排序确保确定性
                result_global_model = sorted(
                    mapping_matches, key=lambda gm: gm.name or ""
                )[0]
                global_model_dict = ModelCacheService._global_model_to_dict(result_global_model)
                await CacheService.set(
                    cache_key, global_model_dict, ttl_seconds=ModelCacheService.CACHE_TTL
                )
                logger.debug(
                    f"GlobalModel 已缓存(映射解析-{resolution_method}): "
                    f"{normalized_name} -> {result_global_model.name}"
                )
                return result_global_model

            # 6. 完全未找到
            resolution_method = "not_found"
            # 未找到匹配，缓存负结果
            await CacheService.set(
                cache_key, "NOT_FOUND", ttl_seconds=ModelCacheService.CACHE_TTL
            )
            logger.debug(f"GlobalModel 未找到(映射解析): {normalized_name}")
            return None

        finally:
            # 记录监控指标
            duration = time.time() - start_time
            model_mapping_resolution_total.labels(
                method=resolution_method, cache_hit=str(cache_hit).lower()
            ).inc()
            model_mapping_resolution_duration_seconds.labels(method=resolution_method).observe(
                duration
            )

    @staticmethod
    def _model_to_dict(model: Model) -> dict:
        """将 Model 对象转换为字典"""
        return {
            "id": model.id,
            "provider_id": model.provider_id,
            "global_model_id": model.global_model_id,
            "provider_model_name": model.provider_model_name,
            "provider_model_mappings": getattr(model, "provider_model_mappings", None),
            "is_active": model.is_active,
            "is_available": model.is_available if hasattr(model, "is_available") else True,
            "price_per_request": (
                float(model.price_per_request) if model.price_per_request is not None else None
            ),
            "tiered_pricing": model.tiered_pricing,
            "supports_vision": model.supports_vision,
            "supports_function_calling": model.supports_function_calling,
            "supports_streaming": model.supports_streaming,
            "supports_extended_thinking": model.supports_extended_thinking,
            "supports_image_generation": getattr(model, "supports_image_generation", None),
            "config": model.config,
        }

    @staticmethod
    def _dict_to_model(model_dict: dict) -> Model:
        """从字典重建 Model 对象"""
        model = Model(
            id=model_dict["id"],
            provider_id=model_dict["provider_id"],
            global_model_id=model_dict["global_model_id"],
            provider_model_name=model_dict["provider_model_name"],
            provider_model_mappings=model_dict.get("provider_model_mappings"),
            is_active=model_dict["is_active"],
            is_available=model_dict.get("is_available", True),
            price_per_request=model_dict.get("price_per_request"),
            tiered_pricing=model_dict.get("tiered_pricing"),
            supports_vision=model_dict.get("supports_vision"),
            supports_function_calling=model_dict.get("supports_function_calling"),
            supports_streaming=model_dict.get("supports_streaming"),
            supports_extended_thinking=model_dict.get("supports_extended_thinking"),
            supports_image_generation=model_dict.get("supports_image_generation"),
            config=model_dict.get("config"),
        )
        return model

    @staticmethod
    def _global_model_to_dict(global_model: GlobalModel) -> dict:
        """将 GlobalModel 对象转换为字典"""
        return {
            "id": global_model.id,
            "name": global_model.name,
            "display_name": global_model.display_name,
            "supported_capabilities": global_model.supported_capabilities,
            "config": global_model.config,
            "default_tiered_pricing": global_model.default_tiered_pricing,
            "default_price_per_request": (
                float(global_model.default_price_per_request)
                if global_model.default_price_per_request is not None
                else None
            ),
            "is_active": global_model.is_active,
        }

    @staticmethod
    def _dict_to_global_model(global_model_dict: dict) -> GlobalModel:
        """从字典重建 GlobalModel 对象"""
        global_model = GlobalModel(
            id=global_model_dict["id"],
            name=global_model_dict["name"],
            display_name=global_model_dict.get("display_name"),
            supported_capabilities=global_model_dict.get("supported_capabilities") or [],
            config=global_model_dict.get("config"),
            default_tiered_pricing=global_model_dict.get("default_tiered_pricing"),
            default_price_per_request=global_model_dict.get("default_price_per_request"),
            is_active=global_model_dict.get("is_active", True),
        )
        return global_model

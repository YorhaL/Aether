"""
Telemetry writer abstraction for stream usage.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.api.handlers.base.base_handler import MessageTelemetry
from src.clients.redis_client import get_redis_client
from src.config.settings import config
from src.core.logger import logger
from src.services.usage.events import UsageEventType, build_usage_event


class TelemetryWriter(ABC):
    @abstractmethod
    async def record_success(self, **kwargs: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    async def record_failure(self, **kwargs: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    async def record_cancelled(self, **kwargs: Any) -> None:
        raise NotImplementedError


class DbTelemetryWriter(TelemetryWriter):
    """通过 MessageTelemetry 写入数据库的 Writer"""

    # MessageTelemetry 不支持的参数，需要过滤掉
    # - request_type: MessageTelemetry 内部固定为 "chat"，无需外部传入
    # - metadata: MessageTelemetry 不支持额外元数据字段
    _IGNORED_KWARGS = frozenset({"request_type", "metadata"})

    def __init__(self, telemetry: MessageTelemetry) -> None:
        self._telemetry = telemetry

    def _filter_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """过滤掉 MessageTelemetry 不支持的参数"""
        return {k: v for k, v in kwargs.items() if k not in self._IGNORED_KWARGS}

    async def record_success(self, **kwargs: Any) -> None:
        await self._telemetry.record_success(**self._filter_kwargs(kwargs))

    async def record_failure(self, **kwargs: Any) -> None:
        await self._telemetry.record_failure(**self._filter_kwargs(kwargs))

    async def record_cancelled(self, **kwargs: Any) -> None:
        await self._telemetry.record_cancelled(**self._filter_kwargs(kwargs))


class QueueTelemetryWriter(TelemetryWriter):
    def __init__(
        self,
        *,
        request_id: str,
        user_id: str,
        api_key_id: str,
    ) -> None:
        self.request_id = request_id
        self.user_id = user_id
        self.api_key_id = api_key_id

    async def record_success(self, **kwargs: Any) -> None:
        await self._publish_event(UsageEventType.COMPLETED, **kwargs)

    async def record_failure(self, **kwargs: Any) -> None:
        await self._publish_event(UsageEventType.FAILED, **kwargs)

    async def record_cancelled(self, **kwargs: Any) -> None:
        await self._publish_event(UsageEventType.CANCELLED, **kwargs)

    async def _publish_event(self, event_type: UsageEventType, **kwargs: Any) -> None:
        redis_client = await get_redis_client(require_redis=False)
        if not redis_client:
            raise RuntimeError("Redis unavailable for usage queue")

        data = self._build_event_data(**kwargs)
        event = build_usage_event(
            event_type=event_type,
            request_id=self.request_id,
            data=data,
        )
        maxlen = config.usage_queue_stream_maxlen
        try:
            if maxlen > 0:
                await redis_client.xadd(
                    config.usage_queue_stream_key,
                    event.to_stream_fields(),
                    maxlen=maxlen,
                    approximate=True,
                )
            else:
                await redis_client.xadd(config.usage_queue_stream_key, event.to_stream_fields())
        except Exception as exc:
            logger.error(f"[usage-queue] XADD failed: {exc}")
            raise

    def _truncate_body(self, value: Any) -> Optional[str]:
        """将 body 序列化为字符串，超长时截断并添加标记"""
        if value is None:
            return None
        try:
            raw = json.dumps(value, ensure_ascii=False)
        except TypeError:
            raw = str(value)
        max_bytes = config.usage_queue_body_max_bytes
        if max_bytes > 0 and len(raw) > max_bytes:
            # 截断并添加标记，预留 15 字符给标记
            truncate_at = max(0, max_bytes - 15)
            raw = raw[:truncate_at] + "...[truncated]"
        return raw

    def _build_event_data(self, **kwargs: Any) -> Dict[str, Any]:
        # 必需字段
        data: Dict[str, Any] = {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "api_key_id": self.api_key_id,
        }
        
        # 可选字段 - 只添加非 None/非默认值，减少 payload 大小
        # 注意：消费者端需要处理缺失字段的默认值
        if kwargs.get("provider"):
            data["provider"] = kwargs["provider"]
        if kwargs.get("model"):
            data["model"] = kwargs["model"]
        if kwargs.get("target_model"):
            data["target_model"] = kwargs["target_model"]
        
        # Token 计数 - 0 是常见值，但仍需传递
        input_tokens = kwargs.get("input_tokens", 0)
        output_tokens = kwargs.get("output_tokens", 0)
        if input_tokens:
            data["input_tokens"] = input_tokens
        if output_tokens:
            data["output_tokens"] = output_tokens
        
        # 缓存 token（cache_creation_tokens -> cache_creation_input_tokens 映射）
        cache_creation = kwargs.get("cache_creation_tokens", 0)
        cache_read = kwargs.get("cache_read_tokens", 0)
        if cache_creation:
            data["cache_creation_input_tokens"] = cache_creation
        if cache_read:
            data["cache_read_input_tokens"] = cache_read
        
        # 时间指标
        if kwargs.get("response_time_ms") is not None:
            data["response_time_ms"] = kwargs["response_time_ms"]
        if kwargs.get("first_byte_time_ms") is not None:
            data["first_byte_time_ms"] = kwargs["first_byte_time_ms"]
        
        # 状态信息
        status_code = kwargs.get("status_code", 200)
        if status_code != 200:
            data["status_code"] = status_code
        if kwargs.get("error_message"):
            data["error_message"] = kwargs["error_message"]
        
        # 格式信息
        request_type = kwargs.get("request_type", "chat")
        if request_type != "chat":
            data["request_type"] = request_type
        if kwargs.get("api_format"):
            data["api_format"] = kwargs["api_format"]
        if kwargs.get("endpoint_api_format"):
            data["endpoint_api_format"] = kwargs["endpoint_api_format"]
        if kwargs.get("has_format_conversion"):
            data["has_format_conversion"] = True
        
        # 流式标记 - 默认 True，只记录 False
        if not kwargs.get("is_stream", True):
            data["is_stream"] = False
        
        # Provider 追踪
        if kwargs.get("provider_id"):
            data["provider_id"] = kwargs["provider_id"]
        if kwargs.get("provider_endpoint_id"):
            data["provider_endpoint_id"] = kwargs["provider_endpoint_id"]
        if kwargs.get("provider_api_key_id"):
            data["provider_api_key_id"] = kwargs["provider_api_key_id"]
        
        # 元数据
        if kwargs.get("metadata"):
            data["metadata"] = kwargs["metadata"]

        # 可选：Headers
        if config.usage_queue_include_headers:
            if kwargs.get("request_headers"):
                data["request_headers"] = kwargs["request_headers"]
            if kwargs.get("provider_request_headers"):
                data["provider_request_headers"] = kwargs["provider_request_headers"]
            if kwargs.get("response_headers"):
                data["response_headers"] = kwargs["response_headers"]
            if kwargs.get("client_response_headers"):
                data["client_response_headers"] = kwargs["client_response_headers"]

        # 可选：Bodies
        if config.usage_queue_include_bodies:
            request_body = self._truncate_body(kwargs.get("request_body"))
            response_body = self._truncate_body(kwargs.get("response_body"))
            if request_body:
                data["request_body"] = request_body
            if response_body:
                data["response_body"] = response_body

        return data

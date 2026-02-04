"""
基础消息处理器，封装通用的编排、转换、遥测逻辑。

接口约定：
- process_stream: 处理流式请求，返回 StreamingResponse
- process_sync: 处理非流式请求，返回 JSONResponse

签名规范（推荐）：
    async def process_stream(
        self,
        request: Any,                           # 解析后的请求模型
        http_request: Request,                  # FastAPI Request 对象
        original_headers: dict[str, str],       # 原始请求头
        original_request_body: dict[str, Any],  # 原始请求体
        query_params: dict[str, str] | None = None,  # 查询参数
    ) -> StreamingResponse: ...

    async def process_sync(
        self,
        request: Any,
        http_request: Request,
        original_headers: dict[str, str],
        original_request_body: dict[str, Any],
        query_params: dict[str, str] | None = None,
    ) -> JSONResponse: ...
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Coroutine
from typing import (
    TYPE_CHECKING,
    Any,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from src.clients.redis_client import get_redis_client_sync
from src.core.logger import logger
from src.services.provider.format import normalize_endpoint_signature
from src.services.system.audit import audit_service
from src.services.usage.service import UsageService

if TYPE_CHECKING:
    from src.api.handlers.base.stream_context import StreamContext

# Adapter 检测器类型：接受 headers 和可选的 request_body，返回能力需求字典
type AdapterDetectorType = Callable[[dict[str, str], dict[str, Any] | None], dict[str, bool]]


class MessageTelemetry:
    """
    负责记录 Usage/Audit，避免处理器里重复代码。
    """

    def __init__(
        self, db: Session, user: Any, api_key: Any, request_id: str, client_ip: str
    ) -> None:
        self.db = db
        self.user = user
        self.api_key = api_key
        self.request_id = request_id
        self.client_ip = client_ip

    async def calculate_cost(
        self,
        provider: str,
        model: str,
        *,
        input_tokens: int,
        output_tokens: int,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0,
    ) -> float:
        input_price, output_price = await UsageService.get_model_price_async(
            self.db, provider, model
        )
        _, _, _, _, _, _, total_cost = UsageService.calculate_cost(
            input_tokens,
            output_tokens,
            input_price,
            output_price,
            cache_creation_tokens,
            cache_read_tokens,
            *await UsageService.get_cache_prices_async(self.db, provider, model, input_price),
        )
        return total_cost

    async def record_success(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        response_time_ms: int,
        status_code: int,
        request_body: dict[str, Any],
        request_headers: dict[str, Any],
        response_body: Any,
        response_headers: dict[str, Any],
        client_response_headers: dict[str, Any] | None = None,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0,
        is_stream: bool = False,
        provider_request_headers: dict[str, Any] | None = None,
        # 时间指标
        first_byte_time_ms: int | None = None,  # 首字时间/TTFB
        # Provider 侧追踪信息（用于记录真实成本）
        provider_id: str | None = None,
        provider_endpoint_id: str | None = None,
        provider_api_key_id: str | None = None,
        api_format: str | None = None,
        # 格式转换追踪
        endpoint_api_format: str | None = None,  # 端点原生 API 格式
        has_format_conversion: bool = False,  # 是否发生了格式转换
        # 模型映射信息
        target_model: str | None = None,
        # Provider 响应元数据（如 Gemini 的 modelVersion）
        response_metadata: dict[str, Any] | None = None,
    ) -> float:
        usage = await UsageService.record_usage(
            db=self.db,
            user=self.user,
            api_key=self.api_key,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_input_tokens=cache_creation_tokens,
            cache_read_input_tokens=cache_read_tokens,
            request_type="chat",
            api_format=api_format,
            endpoint_api_format=endpoint_api_format,
            has_format_conversion=has_format_conversion,
            is_stream=is_stream,
            response_time_ms=response_time_ms,
            first_byte_time_ms=first_byte_time_ms,  # 传递首字时间
            status_code=status_code,
            request_headers=request_headers,
            request_body=request_body,
            provider_request_headers=provider_request_headers or {},
            response_headers=response_headers,
            client_response_headers=client_response_headers,
            response_body=response_body,
            request_id=self.request_id,
            # Provider 侧追踪信息（用于记录真实成本）
            provider_id=provider_id,
            provider_endpoint_id=provider_endpoint_id,
            provider_api_key_id=provider_api_key_id,
            # 模型映射信息
            target_model=target_model,
            # Provider 响应元数据
            metadata=response_metadata,
        )

        total_cost = float(getattr(usage, "total_cost_usd", 0.0) or 0.0)

        if self.user and self.api_key:
            audit_service.log_api_request(
                db=self.db,
                user_id=self.user.id,
                api_key_id=self.api_key.id,
                request_id=self.request_id,
                model=model,
                provider=provider,
                success=True,
                ip_address=self.client_ip,
                status_code=status_code,
                input_tokens=getattr(usage, "input_tokens", input_tokens),
                output_tokens=getattr(usage, "output_tokens", output_tokens),
                cost_usd=total_cost,
            )

        return total_cost

    async def record_failure(
        self,
        *,
        provider: str,
        model: str,
        response_time_ms: int,
        status_code: int,
        error_message: str,
        request_body: dict[str, Any],
        request_headers: dict[str, Any],
        is_stream: bool,
        api_format: str | None = None,
        provider_request_headers: dict[str, Any] | None = None,
        # 预估 token 信息（来自 message_start 事件，用于中断请求的成本估算）
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0,
        response_body: dict[str, Any] | None = None,
        response_headers: dict[str, Any] | None = None,
        client_response_headers: dict[str, Any] | None = None,
        # 格式转换追踪
        endpoint_api_format: str | None = None,
        has_format_conversion: bool = False,
        # 模型映射信息
        target_model: str | None = None,
    ) -> None:
        """
        记录失败请求

        注意：Provider 链路信息（provider_id, endpoint_id, key_id）不在此处记录，
        因为 RequestCandidate 表已经记录了完整的请求链路追踪信息。

        Args:
            input_tokens: 预估输入 tokens（来自 message_start，用于中断请求的成本估算）
            output_tokens: 预估输出 tokens（来自已收到的内容）
            cache_creation_tokens: 缓存创建 tokens
            cache_read_tokens: 缓存读取 tokens
            response_body: 响应体（如果有部分响应）
            response_headers: 响应头（Provider 返回的原始响应头）
            client_response_headers: 返回给客户端的响应头
            target_model: 映射后的目标模型名（如果发生了映射）
        """
        provider_name = provider or "unknown"
        if provider_name == "unknown":
            logger.warning(
                f"[Telemetry] Recording failure with unknown provider (request_id={self.request_id})"
            )

        await UsageService.record_usage(
            db=self.db,
            user=self.user,
            api_key=self.api_key,
            provider=provider_name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_input_tokens=cache_creation_tokens,
            cache_read_input_tokens=cache_read_tokens,
            request_type="chat",
            api_format=api_format,
            endpoint_api_format=endpoint_api_format,
            has_format_conversion=has_format_conversion,
            is_stream=is_stream,
            response_time_ms=response_time_ms,
            status_code=status_code,
            error_message=error_message,
            request_headers=request_headers,
            request_body=request_body,
            provider_request_headers=provider_request_headers or {},
            response_headers=response_headers or {},
            client_response_headers=client_response_headers,
            response_body=response_body or {"error": error_message},
            request_id=self.request_id,
            # 模型映射信息
            target_model=target_model,
        )

    async def record_cancelled(
        self,
        *,
        provider: str,
        model: str,
        response_time_ms: int,
        first_byte_time_ms: int | None,
        status_code: int,
        request_body: dict[str, Any],
        request_headers: dict[str, Any],
        is_stream: bool,
        api_format: str | None = None,
        provider_request_headers: dict[str, Any] | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0,
        response_body: dict[str, Any] | None = None,
        response_headers: dict[str, Any] | None = None,
        client_response_headers: dict[str, Any] | None = None,
        # 格式转换追踪
        endpoint_api_format: str | None = None,
        has_format_conversion: bool = False,
        target_model: str | None = None,
    ) -> None:
        """
        记录客户端取消的请求

        客户端主动断开连接不算系统失败，使用 cancelled 状态。
        """
        provider_name = provider or "unknown"

        await UsageService.record_usage(
            db=self.db,
            user=self.user,
            api_key=self.api_key,
            provider=provider_name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_input_tokens=cache_creation_tokens,
            cache_read_input_tokens=cache_read_tokens,
            request_type="chat",
            api_format=api_format,
            endpoint_api_format=endpoint_api_format,
            has_format_conversion=has_format_conversion,
            is_stream=is_stream,
            response_time_ms=response_time_ms,
            first_byte_time_ms=first_byte_time_ms,
            status_code=status_code,
            status="cancelled",
            request_headers=request_headers,
            request_body=request_body,
            provider_request_headers=provider_request_headers or {},
            response_headers=response_headers or {},
            client_response_headers=client_response_headers,
            response_body=response_body or {},
            request_id=self.request_id,
            target_model=target_model,
        )


@runtime_checkable
class MessageHandlerProtocol(Protocol):
    """
    消息处理器协议 - 定义标准接口

    ChatHandlerBase 和 CliMessageHandlerBase 均支持 http_request 参数用于客户端断连检测。
    """

    async def process_stream(
        self,
        request: Any,
        http_request: Request,
        original_headers: dict[str, str],
        original_request_body: dict[str, Any],
        query_params: dict[str, str] | None = None,
    ) -> StreamingResponse:
        """处理流式请求"""
        ...

    async def process_sync(
        self,
        request: Any,
        http_request: Request,
        original_headers: dict[str, str],
        original_request_body: dict[str, Any],
        query_params: dict[str, str] | None = None,
    ) -> JSONResponse:
        """处理非流式请求"""
        ...


class BaseMessageHandler:
    """
    消息处理器基类，所有具体格式的 handler 可以继承它。

    子类需要实现：
    - process_stream: 处理流式请求
    - process_sync: 处理非流式请求

    推荐使用 MessageHandlerProtocol 中定义的签名。
    """

    def __init__(
        self,
        *,
        db: Session,
        user: Any,
        api_key: Any,
        request_id: str,
        client_ip: str,
        user_agent: str,
        start_time: float,
        allowed_api_formats: list[str] | None = None,
        adapter_detector: AdapterDetectorType | None = None,
    ) -> None:
        self.db = db
        self.user = user
        self.api_key = api_key
        self.request_id = request_id
        self.client_ip = client_ip
        self.user_agent = user_agent
        self.start_time = start_time
        # 新模式：endpoint signature key（family:kind），如 "claude:chat"
        self.allowed_api_formats = allowed_api_formats or ["claude:chat"]
        self.primary_api_format = normalize_endpoint_signature(self.allowed_api_formats[0])
        self.adapter_detector = adapter_detector

        redis_client = get_redis_client_sync()
        self.redis = redis_client
        self.telemetry = MessageTelemetry(db, user, api_key, request_id, client_ip)

    def elapsed_ms(self) -> int:
        return int((time.time() - self.start_time) * 1000)

    def _resolve_capability_requirements(
        self,
        model_name: str,
        request_headers: dict[str, str] | None = None,
        request_body: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        """
        解析请求的能力需求

        来源:
        1. 用户模型级配置 (User.model_capability_settings)
        2. 用户 API Key 强制配置 (ApiKey.force_capabilities)
        3. 请求头 X-Require-Capability
        4. Adapter 的 detect_capability_requirements（如 Claude 的 anthropic-beta）

        Args:
            model_name: 模型名称
            request_headers: 请求头
            request_body: 请求体（可选）

        Returns:
            能力需求字典
        """
        from src.services.capability.resolver import CapabilityResolver

        return CapabilityResolver.resolve_requirements(
            user=self.user,
            user_api_key=self.api_key,
            model_name=model_name,
            request_headers=request_headers,
            request_body=request_body,
            adapter_detector=self.adapter_detector,
        )

    async def _resolve_preferred_key_ids(
        self,
        model_name: str,
        request_body: dict[str, Any] | None = None,
    ) -> list[str] | None:
        """可选的 Key 优先级解析钩子（默认不启用）。"""
        return None

    def build_provider_payload(
        self,
        original_body: dict[str, Any],
        *,
        mapped_model: str | None = None,
    ) -> dict[str, Any]:
        """构建发送给 Provider 的请求体，替换 model 名称"""
        payload = dict(original_body)
        if mapped_model:
            payload["model"] = mapped_model
        return payload

    def _update_usage_to_streaming(self, request_id: str | None = None) -> None:
        """更新 Usage 状态为 streaming（流式传输开始时调用）

        使用 asyncio 后台任务执行数据库更新，避免阻塞流式传输

        注意：TTFB（首字节时间）由 StreamContext.record_first_byte_time() 记录，
        并在最终 record_success 时传递到数据库，避免重复记录导致数据不一致。

        Args:
            request_id: 请求 ID，如果不传则使用 self.request_id
        """
        import asyncio

        from src.database.database import get_db

        target_request_id = request_id or self.request_id

        async def _do_update() -> None:
            try:
                db_gen = get_db()
                db = next(db_gen)
                try:
                    UsageService.update_usage_status(
                        db=db,
                        request_id=target_request_id,
                        status="streaming",
                    )
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"[{target_request_id}] 更新 Usage 状态为 streaming 失败: {e}")

        # 创建后台任务，不阻塞当前流
        asyncio.create_task(_do_update())

    def _update_usage_to_streaming_with_ctx(self, ctx: StreamContext) -> None:
        """更新 Usage 状态为 streaming，同时更新 provider 相关信息

        使用 asyncio 后台任务执行数据库更新，避免阻塞流式传输

        注意：TTFB（首字节时间）由 StreamContext.record_first_byte_time() 记录，
        并在最终 record_success 时传递到数据库，避免重复记录导致数据不一致。

        Args:
            ctx: 流式上下文，包含 provider 相关信息
        """
        import asyncio

        from src.database.database import get_db

        target_request_id = self.request_id
        provider = ctx.provider_name
        target_model = ctx.mapped_model
        provider_id = ctx.provider_id
        endpoint_id = ctx.endpoint_id
        key_id = ctx.key_id
        first_byte_time_ms = ctx.first_byte_time_ms
        api_format = ctx.api_format
        # 格式转换追踪
        endpoint_api_format = ctx.provider_api_format or None
        has_format_conversion = ctx.needs_conversion

        # 如果 provider 为空，记录警告（不应该发生，但用于调试）
        if not provider:
            logger.warning(
                f"[{target_request_id}] 更新 streaming 状态时 provider 为空: "
                f"ctx.provider_name={ctx.provider_name}, ctx.provider_id={ctx.provider_id}"
            )

        async def _do_update() -> None:
            try:
                db_gen = get_db()
                db = next(db_gen)
                try:
                    UsageService.update_usage_status(
                        db=db,
                        request_id=target_request_id,
                        status="streaming",
                        provider=provider,
                        target_model=target_model,
                        provider_id=provider_id,
                        provider_endpoint_id=endpoint_id,
                        provider_api_key_id=key_id,
                        first_byte_time_ms=first_byte_time_ms,
                        api_format=api_format,
                        endpoint_api_format=endpoint_api_format,
                        has_format_conversion=has_format_conversion,
                    )
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"[{target_request_id}] 更新 Usage 状态为 streaming 失败: {e}")

        # 创建后台任务，不阻塞当前流
        asyncio.create_task(_do_update())

    def _log_request_error(self, message: str, error: Exception) -> None:
        """记录请求错误日志，对业务异常不打印堆栈

        Args:
            message: 错误消息前缀
            error: 异常对象
        """
        from src.core.exceptions import (
            ModelNotSupportedException,
            ProviderException,
            QuotaExceededException,
            RateLimitException,
            UpstreamClientException,
        )

        if isinstance(
            error,
            (
                ProviderException,
                QuotaExceededException,
                RateLimitException,
                ModelNotSupportedException,
                UpstreamClientException,
            ),
        ):
            # 业务异常：简洁日志，不打印堆栈
            logger.error(f"{message}: [{type(error).__name__}] {error}")
        else:
            # 未知异常：完整堆栈
            logger.exception(f"{message}: {error}")


# ============================================================================
# 客户端断连检测
# ============================================================================


class ClientDisconnectedException(Exception):
    """客户端在等待首字节时断开连接"""

    pass


_T = TypeVar("_T")


async def wait_for_with_disconnect_detection(
    coro: Coroutine[Any, Any, _T],
    timeout: float,
    is_disconnected: Callable[[], Awaitable[bool]],
    request_id: str,
    check_interval: float = 0.5,
) -> _T:
    """
    等待协程完成，同时检测客户端断连

    在等待上游响应（如首字节）时，定期检测客户端是否已断连。
    若检测到断连，取消任务并抛出 ClientDisconnectedException。

    Args:
        coro: 要等待的协程
        timeout: 超时时间（秒）
        is_disconnected: 异步断连检测函数（如 http_request.is_disconnected）
        request_id: 请求 ID（用于日志）
        check_interval: 断连检测间隔（秒），默认 0.5s

    Returns:
        协程的返回值

    Raises:
        ClientDisconnectedException: 客户端断连
        asyncio.TimeoutError: 超时
        asyncio.CancelledError: 任务被外部取消
    """
    task = asyncio.create_task(coro)
    client_disconnected = False

    async def check_client_disconnect() -> None:
        nonlocal client_disconnected
        while not task.done():
            await asyncio.sleep(check_interval)
            try:
                if await is_disconnected():
                    client_disconnected = True
                    logger.debug(f"  [{request_id}] 检测到客户端断连，取消预取任务")
                    task.cancel()
                    break
            except Exception as e:
                logger.debug(f"  [{request_id}] 断连检测异常: {e}")

    disconnect_task = asyncio.create_task(check_client_disconnect())

    try:
        return await asyncio.wait_for(task, timeout=timeout)

    except asyncio.CancelledError:
        if client_disconnected:
            raise ClientDisconnectedException("Client disconnected during prefetch")
        raise

    finally:
        disconnect_task.cancel()
        try:
            await disconnect_task
        except asyncio.CancelledError:
            pass

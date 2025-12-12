"""
流式处理器 - 从 ChatHandlerBase 提取的流式响应处理逻辑

职责：
1. SSE 事件解析和处理
2. 响应流生成
3. 预读和嵌套错误检测
4. 客户端断开检测
"""

import asyncio
import json
from typing import Any, AsyncGenerator, Callable, Optional

import httpx

from src.api.handlers.base.parsers import get_parser_for_format
from src.api.handlers.base.response_parser import ResponseParser
from src.api.handlers.base.stream_context import StreamContext
from src.core.exceptions import EmbeddedErrorException
from src.core.logger import logger
from src.models.database import Provider, ProviderEndpoint
from src.utils.sse_parser import SSEEventParser


class StreamProcessor:
    """
    流式响应处理器

    负责处理 SSE 流的解析、错误检测和响应生成。
    从 ChatHandlerBase 中提取，使其职责更加单一。
    """

    def __init__(
        self,
        request_id: str,
        default_parser: ResponseParser,
        on_streaming_start: Optional[Callable[[], None]] = None,
    ):
        """
        初始化流处理器

        Args:
            request_id: 请求 ID（用于日志）
            default_parser: 默认响应解析器
            on_streaming_start: 流开始时的回调（用于更新状态）
        """
        self.request_id = request_id
        self.default_parser = default_parser
        self.on_streaming_start = on_streaming_start

    def get_parser_for_provider(self, ctx: StreamContext) -> ResponseParser:
        """
        获取 Provider 格式的解析器

        根据 Provider 的 API 格式选择正确的解析器。
        """
        if ctx.provider_api_format:
            try:
                return get_parser_for_format(ctx.provider_api_format)
            except KeyError:
                pass
        return self.default_parser

    def handle_sse_event(
        self,
        ctx: StreamContext,
        event_name: Optional[str],
        data_str: str,
    ) -> None:
        """
        处理单个 SSE 事件

        解析事件数据，提取 usage 信息和文本内容。

        Args:
            ctx: 流式上下文
            event_name: 事件名称
            data_str: 事件数据字符串
        """
        if not data_str:
            return

        if data_str == "[DONE]":
            ctx.has_completion = True
            return

        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            return

        ctx.data_count += 1

        if not isinstance(data, dict):
            return

        # 收集原始 chunk 数据
        ctx.parsed_chunks.append(data)

        # 根据 Provider 格式选择解析器
        parser = self.get_parser_for_provider(ctx)

        # 使用解析器提取 usage
        usage = parser.extract_usage_from_response(data)
        if usage:
            ctx.update_usage(
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                cached_tokens=usage.get("cache_read_tokens"),
                cache_creation_tokens=usage.get("cache_creation_tokens"),
            )

        # 提取文本
        text = parser.extract_text_content(data)
        if text:
            ctx.collected_text += text

        # 检查完成
        event_type = event_name or data.get("type", "")
        if event_type in ("response.completed", "message_stop"):
            ctx.has_completion = True

    async def prefetch_and_check_error(
        self,
        line_iterator: Any,
        provider: Provider,
        endpoint: ProviderEndpoint,
        ctx: StreamContext,
        max_prefetch_lines: int = 5,
    ) -> list:
        """
        预读流的前几行，检测嵌套错误

        某些 Provider（如 Gemini）可能返回 HTTP 200，但在响应体中包含错误信息。
        这种情况需要在流开始输出之前检测，以便触发重试逻辑。

        Args:
            line_iterator: 行迭代器
            provider: Provider 对象
            endpoint: Endpoint 对象
            ctx: 流式上下文
            max_prefetch_lines: 最多预读行数

        Returns:
            预读的行列表

        Raises:
            EmbeddedErrorException: 如果检测到嵌套错误
        """
        prefetched_lines: list = []
        parser = self.get_parser_for_provider(ctx)

        try:
            line_count = 0
            async for line in line_iterator:
                prefetched_lines.append(line)
                line_count += 1

                normalized_line = line.rstrip("\r")
                if not normalized_line or normalized_line.startswith(":"):
                    if line_count >= max_prefetch_lines:
                        break
                    continue

                # 尝试解析 SSE 数据
                data_str = normalized_line
                if normalized_line.startswith("data: "):
                    data_str = normalized_line[6:]

                if data_str == "[DONE]":
                    break

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    if line_count >= max_prefetch_lines:
                        break
                    continue

                # 使用解析器检查是否为错误响应
                if isinstance(data, dict) and parser.is_error_response(data):
                    parsed = parser.parse_response(data, 200)
                    logger.warning(
                        f"  [{self.request_id}] 检测到嵌套错误: "
                        f"Provider={provider.name}, "
                        f"error_type={parsed.error_type}, "
                        f"message={parsed.error_message}"
                    )
                    raise EmbeddedErrorException(
                        provider_name=str(provider.name),
                        error_code=(
                            int(parsed.error_type)
                            if parsed.error_type and parsed.error_type.isdigit()
                            else None
                        ),
                        error_message=parsed.error_message,
                        error_status=parsed.error_type,
                    )

                # 预读到有效数据，没有错误，停止预读
                break

        except EmbeddedErrorException:
            raise
        except Exception as e:
            logger.debug(f"  [{self.request_id}] 预读流时发生异常: {e}")

        return prefetched_lines

    async def create_response_stream(
        self,
        ctx: StreamContext,
        line_iterator: Any,
        response_ctx: Any,
        http_client: httpx.AsyncClient,
        prefetched_lines: Optional[list] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        创建响应流生成器

        统一的流生成器，支持带预读数据和不带预读数据两种情况。

        Args:
            ctx: 流式上下文
            line_iterator: 行迭代器
            response_ctx: HTTP 响应上下文管理器
            http_client: HTTP 客户端
            prefetched_lines: 预读的行列表（可选）

        Yields:
            编码后的响应数据块
        """
        try:
            sse_parser = SSEEventParser()
            streaming_started = False

            # 处理预读数据
            if prefetched_lines:
                if not streaming_started and self.on_streaming_start:
                    self.on_streaming_start()
                    streaming_started = True

                for line in prefetched_lines:
                    for chunk in self._process_line(ctx, sse_parser, line):
                        yield chunk

            # 处理剩余的流数据
            async for line in line_iterator:
                if not streaming_started and self.on_streaming_start:
                    self.on_streaming_start()
                    streaming_started = True

                for chunk in self._process_line(ctx, sse_parser, line):
                    yield chunk

            # 处理剩余事件
            for event in sse_parser.flush():
                self.handle_sse_event(ctx, event.get("event"), event.get("data") or "")

        except GeneratorExit:
            raise
        finally:
            await self._cleanup(response_ctx, http_client)

    def _process_line(
        self,
        ctx: StreamContext,
        sse_parser: SSEEventParser,
        line: str,
    ) -> list[bytes]:
        """
        处理单行数据

        Args:
            ctx: 流式上下文
            sse_parser: SSE 解析器
            line: 原始行数据

        Returns:
            要发送的数据块列表
        """
        result: list[bytes] = []
        normalized_line = line.rstrip("\r")
        events = sse_parser.feed_line(normalized_line)

        if normalized_line == "":
            for event in events:
                self.handle_sse_event(ctx, event.get("event"), event.get("data") or "")
            result.append(b"\n")
        else:
            ctx.chunk_count += 1
            result.append((line + "\n").encode("utf-8"))

            for event in events:
                self.handle_sse_event(ctx, event.get("event"), event.get("data") or "")

        return result

    async def create_monitored_stream(
        self,
        ctx: StreamContext,
        stream_generator: AsyncGenerator[bytes, None],
        is_disconnected: Callable[[], Any],
    ) -> AsyncGenerator[bytes, None]:
        """
        创建带监控的流生成器

        检测客户端断开连接并更新状态码。

        Args:
            ctx: 流式上下文
            stream_generator: 原始流生成器
            is_disconnected: 检查客户端是否断开的函数

        Yields:
            响应数据块
        """
        try:
            async for chunk in stream_generator:
                if await is_disconnected():
                    logger.warning(f"ID:{self.request_id} | Client disconnected")
                    ctx.status_code = 499  # Client Closed Request
                    ctx.error_message = "client_disconnected"
                    break
                yield chunk
        except asyncio.CancelledError:
            ctx.status_code = 499
            ctx.error_message = "client_disconnected"
            raise
        except Exception as e:
            ctx.status_code = 500
            ctx.error_message = str(e)
            raise

    async def _cleanup(
        self,
        response_ctx: Any,
        http_client: httpx.AsyncClient,
    ) -> None:
        """清理资源"""
        try:
            await response_ctx.__aexit__(None, None, None)
        except Exception:
            pass
        try:
            await http_client.aclose()
        except Exception:
            pass

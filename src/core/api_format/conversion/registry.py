"""
格式转换注册表（Canonical / Hub-and-Spoke）

实现路径：
source -> internal -> target

说明：
- 旧 N×N converters 已移除；这里是唯一的格式转换实现。
- 转换失败将抛出 `FormatConversionError`（不再静默回退）。
"""

import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from src.core.api_format.conversion.exceptions import FormatConversionError
from src.core.api_format.conversion.normalizer import FormatNormalizer
from src.core.api_format.conversion.stream_state import StreamState
from src.core.logger import logger
from src.core.metrics import format_conversion_duration_seconds, format_conversion_total


@contextmanager
def _track_conversion_metrics(
    direction: str,
    source: str,
    target: str,
) -> Generator[None]:
    start = time.perf_counter()
    try:
        yield
        format_conversion_total.labels(direction, source, target, "success").inc()
    except Exception:
        format_conversion_total.labels(direction, source, target, "error").inc()
        raise
    finally:
        format_conversion_duration_seconds.labels(direction, source, target).observe(
            time.perf_counter() - start
        )


class FormatConversionRegistry:
    """基于 Normalizer 的格式转换注册表"""

    def __init__(self) -> None:
        self._normalizers: dict[str, FormatNormalizer] = {}

    def register(self, normalizer: FormatNormalizer) -> None:
        self._normalizers[str(normalizer.FORMAT_ID).upper()] = normalizer
        logger.info(f"[FormatConversionRegistry] 注册 normalizer: {normalizer.FORMAT_ID}")

    def get_normalizer(self, format_id: str) -> FormatNormalizer | None:
        return self._normalizers.get(str(format_id).upper())

    def _require_normalizer(self, format_id: str) -> FormatNormalizer:
        normalizer = self.get_normalizer(format_id)
        if normalizer is None:
            raise FormatConversionError(format_id, format_id, f"未注册 Normalizer: {format_id}")
        return normalizer

    # ==================== 请求/响应转换（严格） ====================

    def convert_request(
        self,
        request: dict[str, Any],
        source_format: str,
        target_format: str,
    ) -> dict[str, Any]:
        if str(source_format).upper() == str(target_format).upper():
            return request

        src = self._require_normalizer(source_format)
        tgt = self._require_normalizer(target_format)

        with _track_conversion_metrics(
            "request", str(source_format).upper(), str(target_format).upper()
        ):
            try:
                internal = src.request_to_internal(request)
                return tgt.request_from_internal(internal)
            except Exception as e:
                raise FormatConversionError(source_format, target_format, str(e)) from e

    def convert_response(
        self,
        response: dict[str, Any],
        source_format: str,
        target_format: str,
        *,
        requested_model: str | None = None,
    ) -> dict[str, Any]:
        """转换响应格式

        Args:
            response: 原始响应
            source_format: 源格式
            target_format: 目标格式
            requested_model: 用户请求的原始模型名（可选）。
                            如果提供，响应中的 model 字段将使用此值，
                            而不是上游返回的映射后模型名。
        """
        if str(source_format).upper() == str(target_format).upper():
            # 即使格式相同，也需要替换 model 字段
            if requested_model and isinstance(response, dict):
                response = dict(response)  # 避免修改原始响应
                # 支持不同格式的 model 字段名
                if "model" in response:
                    response["model"] = requested_model
                elif "modelVersion" in response:
                    response["modelVersion"] = requested_model
            return response

        src = self._require_normalizer(source_format)
        tgt = self._require_normalizer(target_format)

        with _track_conversion_metrics(
            "response", str(source_format).upper(), str(target_format).upper()
        ):
            try:
                internal = src.response_to_internal(response)
                return tgt.response_from_internal(internal, requested_model=requested_model)
            except Exception as e:
                raise FormatConversionError(source_format, target_format, str(e)) from e

    def convert_error_response(
        self,
        error_response: dict[str, Any],
        source_format: str,
        target_format: str,
    ) -> dict[str, Any]:
        if str(source_format).upper() == str(target_format).upper():
            return error_response

        src = self._require_normalizer(source_format)
        tgt = self._require_normalizer(target_format)

        if not (
            src.capabilities.supports_error_conversion
            and tgt.capabilities.supports_error_conversion
        ):
            raise FormatConversionError(
                source_format,
                target_format,
                "source/target normalizer 不支持错误转换",
            )

        with _track_conversion_metrics(
            "error", str(source_format).upper(), str(target_format).upper()
        ):
            try:
                internal = src.error_to_internal(error_response)
                return tgt.error_from_internal(internal)
            except Exception as e:
                raise FormatConversionError(source_format, target_format, str(e)) from e

    # ==================== 流式转换（严格） ====================

    def convert_stream_chunk(
        self,
        chunk: dict[str, Any],
        source_format: str,
        target_format: str,
        state: StreamState | None = None,
    ) -> list[dict[str, Any]]:
        if str(source_format).upper() == str(target_format).upper():
            return [chunk]

        src = self._require_normalizer(source_format)
        tgt = self._require_normalizer(target_format)

        if not (src.capabilities.supports_stream and tgt.capabilities.supports_stream):
            raise FormatConversionError(
                source_format,
                target_format,
                "source/target normalizer 不支持流式转换",
            )

        if state is None:
            # 调用方应提供预初始化的 state（包含 model/message_id），
            # 这里仅作为防御性回退，可能导致响应中 model 字段为空
            logger.debug(
                f"convert_stream_chunk: state is None, creating empty StreamState "
                f"(source={source_format}, target={target_format})"
            )
            state = StreamState()

        with _track_conversion_metrics(
            "stream", str(source_format).upper(), str(target_format).upper()
        ):
            try:
                events = src.stream_chunk_to_internal(chunk, state)
                out: list[dict[str, Any]] = []
                for event in events:
                    out.extend(tgt.stream_event_from_internal(event, state))
                return out
            except Exception as e:
                raise FormatConversionError(source_format, target_format, str(e)) from e

    # ==================== 能力查询 ====================

    def can_convert_request(self, source_format: str, target_format: str) -> bool:
        if str(source_format).upper() == str(target_format).upper():
            return True
        return (
            self.get_normalizer(source_format) is not None
            and self.get_normalizer(target_format) is not None
        )

    def can_convert_response(self, source_format: str, target_format: str) -> bool:
        return self.can_convert_request(source_format, target_format)

    def can_convert_stream(self, source_format: str, target_format: str) -> bool:
        if str(source_format).upper() == str(target_format).upper():
            return True
        src = self.get_normalizer(source_format)
        tgt = self.get_normalizer(target_format)
        if src is None or tgt is None:
            return False
        return bool(src.capabilities.supports_stream and tgt.capabilities.supports_stream)

    def can_convert_error(self, source_format: str, target_format: str) -> bool:
        if str(source_format).upper() == str(target_format).upper():
            return True
        src = self.get_normalizer(source_format)
        tgt = self.get_normalizer(target_format)
        if src is None or tgt is None:
            return False
        return bool(
            src.capabilities.supports_error_conversion
            and tgt.capabilities.supports_error_conversion
        )

    def can_convert_full(
        self, format_a: str, format_b: str, *, require_stream: bool = False
    ) -> bool:
        if not self.can_convert_request(format_a, format_b):
            return False
        if not self.can_convert_request(format_b, format_a):
            return False
        if require_stream:
            return self.can_convert_stream(format_a, format_b) and self.can_convert_stream(
                format_b, format_a
            )
        return True

    def list_normalizers(self) -> list[str]:
        return sorted(self._normalizers.keys())

    def get_supported_targets(self, source_format: str) -> list[str]:
        src = str(source_format).upper()
        if src not in self._normalizers:
            return []
        return [k for k in self._normalizers.keys() if k != src]


# 全局注册表（唯一实现）
format_conversion_registry = FormatConversionRegistry()
_DEFAULT_NORMALIZERS_REGISTERED = False
_REGISTRATION_LOCK = threading.Lock()


def register_default_normalizers() -> None:
    """注册默认 Normalizers（OPENAI/CLAUDE/GEMINI + *_CLI）"""
    global _DEFAULT_NORMALIZERS_REGISTERED  # noqa: PLW0603 - module-level 缓存

    # 快速路径：已注册则直接返回（无锁）
    if _DEFAULT_NORMALIZERS_REGISTERED:
        return

    # 慢路径：加锁后双重检查
    with _REGISTRATION_LOCK:
        if _DEFAULT_NORMALIZERS_REGISTERED:
            return

        from src.core.api_format.conversion.normalizers.claude import ClaudeNormalizer
        from src.core.api_format.conversion.normalizers.claude_cli import ClaudeCliNormalizer
        from src.core.api_format.conversion.normalizers.gemini import GeminiNormalizer
        from src.core.api_format.conversion.normalizers.gemini_cli import GeminiCliNormalizer
        from src.core.api_format.conversion.normalizers.openai import OpenAINormalizer
        from src.core.api_format.conversion.normalizers.openai_cli import OpenAICliNormalizer

        format_conversion_registry.register(OpenAINormalizer())
        format_conversion_registry.register(OpenAICliNormalizer())
        format_conversion_registry.register(ClaudeNormalizer())
        format_conversion_registry.register(ClaudeCliNormalizer())
        format_conversion_registry.register(GeminiNormalizer())
        format_conversion_registry.register(GeminiCliNormalizer())

        _DEFAULT_NORMALIZERS_REGISTERED = True
        logger.info(
            f"[FormatConversionRegistry] 已注册 {len(format_conversion_registry.list_normalizers())} 个 normalizer"
        )


__all__ = [
    "FormatConversionRegistry",
    "format_conversion_registry",
    "register_default_normalizers",
]

"""
错误转换单元测试（Canonical）

重点：
- registry_canonical.convert_error_response(_strict) 的基本链路
- ErrorEvent 在 stream_event_from_internal 的输出形态
"""

from __future__ import annotations

from typing import Any, cast

from src.core.api_format.conversion.internal import ErrorType, InternalError
from src.core.api_format.conversion.normalizers.claude import ClaudeNormalizer
from src.core.api_format.conversion.normalizers.gemini import GeminiNormalizer
from src.core.api_format.conversion.normalizers.openai import OpenAINormalizer
from src.core.api_format.conversion.registry import FormatConversionRegistry
from src.core.api_format.conversion.stream_events import ErrorEvent
from src.core.api_format.conversion.stream_state import StreamState


def _make_registry() -> FormatConversionRegistry:
    reg = FormatConversionRegistry()
    reg.register(OpenAINormalizer())
    reg.register(ClaudeNormalizer())
    reg.register(GeminiNormalizer())
    return reg


def test_error_conversion_openai_to_claude() -> None:
    reg = _make_registry()

    openai_error = {
        "error": {"message": "bad request", "type": "invalid_request_error", "code": "bad_request"}
    }

    out = reg.convert_error_response(openai_error, "openai:chat", "claude:chat")
    assert out.get("type") == "error"
    assert isinstance(out.get("error"), dict)
    assert out["error"]["message"] == "bad request"


def test_error_conversion_claude_to_openai() -> None:
    reg = _make_registry()

    claude_error = {"type": "error", "error": {"type": "invalid_request_error", "message": "nope"}}
    out = reg.convert_error_response(claude_error, "claude:chat", "openai:chat")
    assert isinstance(out.get("error"), dict)
    assert out["error"]["message"] == "nope"


def test_error_event_stream_output_openai() -> None:
    n = OpenAINormalizer()
    state = StreamState(model="gpt-4o-mini", message_id="chatcmpl_1")

    internal = InternalError(type=ErrorType.INVALID_REQUEST, message="bad", retryable=False)
    events = n.stream_event_from_internal(ErrorEvent(error=internal), state)
    assert events == [{"error": {"message": "bad", "type": "invalid_request_error"}}]


def test_error_event_stream_openai_to_claude_via_registry() -> None:
    reg = _make_registry()

    # OpenAI 流式错误块
    chunk = {"error": {"message": "bad", "type": "invalid_request_error"}}
    out = reg.convert_stream_chunk(chunk, "openai:chat", "claude:chat", state=StreamState())
    assert isinstance(out, list) and out
    evt0 = cast(dict[str, Any], out[0])
    assert evt0.get("type") == "error"
    assert isinstance(evt0.get("error"), dict)
    assert evt0["error"]["message"] == "bad"

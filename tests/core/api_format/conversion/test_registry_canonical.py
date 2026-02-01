"""
Canonical Registry 单元测试

覆盖重点：
- request/response/stream 的基本两段式转换（source -> internal -> target）
- 严格模式下的可用性（已注册格式可转换）
"""

from __future__ import annotations

from typing import Any, cast

from src.core.api_format.conversion.normalizers.claude import ClaudeNormalizer
from src.core.api_format.conversion.normalizers.gemini import GeminiNormalizer
from src.core.api_format.conversion.normalizers.openai import OpenAINormalizer
from src.core.api_format.conversion.registry import FormatConversionRegistry
from src.core.api_format.conversion.stream_state import StreamState


def _make_registry() -> FormatConversionRegistry:
    reg = FormatConversionRegistry()
    reg.register(OpenAINormalizer())
    reg.register(ClaudeNormalizer())
    reg.register(GeminiNormalizer())
    return reg


def _first_openai_choice_message(resp: dict[str, Any]) -> dict[str, Any]:
    choices = resp.get("choices") or []
    assert isinstance(choices, list) and choices
    c0 = choices[0]
    assert isinstance(c0, dict)
    msg = c0.get("message")
    assert isinstance(msg, dict)
    return cast(dict[str, Any], msg)


def test_registry_canonical_can_convert_full_stream() -> None:
    reg = _make_registry()
    assert reg.can_convert_full("openai:chat", "claude:chat", require_stream=True) is True
    assert reg.can_convert_full("openai:chat", "gemini:chat", require_stream=True) is True
    assert reg.can_convert_full("claude:chat", "gemini:chat", require_stream=True) is True


def test_registry_canonical_request_openai_to_claude() -> None:
    reg = _make_registry()

    openai_req = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "sys"},
            {"role": "developer", "content": "dev"},
            {"role": "user", "content": "hi"},
        ],
        "max_tokens": 12,
        "temperature": 0.2,
        "stream": True,
    }

    claude_req = reg.convert_request(openai_req, "openai:chat", "claude:chat")
    assert claude_req["model"] == "gpt-4o-mini"
    assert claude_req["system"] == "sys\n\ndev"
    assert claude_req["stream"] is True
    assert isinstance(claude_req.get("messages"), list)
    assert claude_req["messages"][0]["role"] == "user"
    assert claude_req["messages"][0]["content"] == "hi"


def test_registry_canonical_response_claude_to_openai() -> None:
    reg = _make_registry()

    claude_resp = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-3-5-sonnet-latest",
        "content": [{"type": "text", "text": "hello"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 5, "output_tokens": 7},
    }

    openai_resp = reg.convert_response(claude_resp, "claude:chat", "openai:chat")
    assert openai_resp["object"] == "chat.completion"
    msg = _first_openai_choice_message(openai_resp)
    assert msg["role"] == "assistant"
    assert msg["content"] == "hello"


def test_registry_canonical_stream_openai_to_claude() -> None:
    reg = _make_registry()

    chunk = {
        "id": "chatcmpl_1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "gpt-4o-mini",
        "choices": [
            {"index": 0, "delta": {"role": "assistant", "content": "hi"}, "finish_reason": None}
        ],
    }

    state = StreamState()
    out_events = reg.convert_stream_chunk(chunk, "openai:chat", "claude:chat", state=state)
    assert isinstance(out_events, list) and out_events

    types = [cast(dict[str, Any], e).get("type") for e in cast(list[dict[str, Any]], out_events)]
    assert types[:3] == ["message_start", "content_block_start", "content_block_delta"]

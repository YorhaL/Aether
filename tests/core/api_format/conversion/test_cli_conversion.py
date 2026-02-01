"""
CLI 格式参与转换的单元测试

覆盖：
- OPENAI_CLI（Responses）与其他格式的 request/response/stream 基础互转
- CLAUDE_CLI / GEMINI_CLI 的 registry 注册与互转能力
"""

from __future__ import annotations

from typing import Any, cast

from src.core.api_format.conversion.normalizers.claude import ClaudeNormalizer
from src.core.api_format.conversion.normalizers.claude_cli import ClaudeCliNormalizer
from src.core.api_format.conversion.normalizers.gemini import GeminiNormalizer
from src.core.api_format.conversion.normalizers.gemini_cli import GeminiCliNormalizer
from src.core.api_format.conversion.normalizers.openai import OpenAINormalizer
from src.core.api_format.conversion.normalizers.openai_cli import OpenAICliNormalizer
from src.core.api_format.conversion.registry import FormatConversionRegistry
from src.core.api_format.conversion.stream_state import StreamState


def _make_registry_with_cli() -> FormatConversionRegistry:
    reg = FormatConversionRegistry()
    reg.register(OpenAINormalizer())
    reg.register(OpenAICliNormalizer())
    reg.register(ClaudeNormalizer())
    reg.register(ClaudeCliNormalizer())
    reg.register(GeminiNormalizer())
    reg.register(GeminiCliNormalizer())
    return reg


def test_registry_can_convert_full_with_cli_stream() -> None:
    reg = _make_registry_with_cli()
    assert reg.can_convert_full("openai:cli", "openai:chat", require_stream=True) is True
    assert reg.can_convert_full("openai:cli", "claude:cli", require_stream=True) is True
    assert reg.can_convert_full("gemini:cli", "claude:chat", require_stream=True) is True


def test_openai_cli_request_to_claude() -> None:
    reg = _make_registry_with_cli()

    openai_cli_req = {
        "model": "gpt-4o-mini",
        "input": [{"role": "user", "content": [{"type": "input_text", "text": "hi"}]}],
        "stream": True,
        "max_output_tokens": 12,
    }

    claude_req = reg.convert_request(openai_cli_req, "openai:cli", "claude:chat")
    assert claude_req["model"] == "gpt-4o-mini"
    assert claude_req["stream"] is True
    assert isinstance(claude_req.get("messages"), list)
    assert claude_req["messages"][0]["role"] == "user"
    assert claude_req["messages"][0]["content"] == "hi"


def test_claude_response_to_openai_cli() -> None:
    reg = _make_registry_with_cli()

    claude_resp = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-3-5-sonnet-latest",
        "content": [{"type": "text", "text": "hello"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 5, "output_tokens": 7},
    }

    openai_cli_resp = reg.convert_response(claude_resp, "claude:chat", "openai:cli")
    assert openai_cli_resp["object"] == "response"
    assert isinstance(openai_cli_resp.get("output"), list)
    msg = cast(dict[str, Any], openai_cli_resp["output"][0])
    assert msg["type"] == "message"
    assert msg["role"] == "assistant"
    content = cast(list[dict[str, Any]], msg.get("content") or [])
    assert content and content[0]["type"] == "output_text"
    assert content[0]["text"] == "hello"


def test_stream_openai_to_openai_cli_delta() -> None:
    reg = _make_registry_with_cli()
    state = StreamState()

    chunk = {
        "id": "chatcmpl_1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "gpt-4o-mini",
        "choices": [
            {"index": 0, "delta": {"role": "assistant", "content": "hi"}, "finish_reason": None}
        ],
    }

    out_events = reg.convert_stream_chunk(chunk, "openai:chat", "openai:cli", state=state)
    assert isinstance(out_events, list) and out_events
    assert out_events[0].get("type") == "response.created"
    assert out_events[1].get("type") == "response.output_text.delta"
    assert out_events[1].get("delta") == "hi"


def test_stream_openai_cli_to_openai_delta() -> None:
    reg = _make_registry_with_cli()
    state = StreamState()

    chunk = {
        "type": "response.output_text.delta",
        "delta": "hi",
        "response": {"id": "resp_1", "model": "gpt-4o-mini"},
    }

    out_events = reg.convert_stream_chunk(chunk, "openai:cli", "openai:chat", state=state)
    assert isinstance(out_events, list) and out_events

    # 第一个 chunk 先补齐 assistant role
    assert out_events[0].get("object") == "chat.completion.chunk"
    # 第二个 chunk 才是文本增量
    choices = out_events[1].get("choices") or []
    assert isinstance(choices, list) and choices
    delta = cast(dict[str, Any], choices[0]).get("delta") or {}
    assert cast(dict[str, Any], delta).get("content") == "hi"


def test_openai_cli_function_call_to_claude() -> None:
    """测试 OpenAI CLI 的 function_call/function_call_output 转换为 Claude tool_use/tool_result"""
    reg = _make_registry_with_cli()

    openai_cli_req = {
        "model": "gpt-5",
        "instructions": "You are helpful.",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "列出当前目录"}],
            },
            {
                "type": "function_call",
                "name": "shell_command",
                "arguments": '{"command": "ls -la"}',
                "call_id": "call_abc123",
            },
            {
                "type": "function_call_output",
                "call_id": "call_abc123",
                "output": "file1.txt\nfile2.txt",
            },
        ],
        "stream": True,
    }

    claude_req = reg.convert_request(openai_cli_req, "openai:cli", "claude:chat")

    messages = claude_req.get("messages", [])
    assert len(messages) == 3

    # 第一条：user 消息
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "列出当前目录"

    # 第二条：assistant + tool_use
    assert messages[1]["role"] == "assistant"
    content1 = messages[1]["content"]
    assert isinstance(content1, list) and len(content1) == 1
    assert content1[0]["type"] == "tool_use"
    assert content1[0]["name"] == "shell_command"
    assert content1[0]["id"] == "call_abc123"
    assert content1[0]["input"] == {"command": "ls -la"}

    # 第三条：user + tool_result
    assert messages[2]["role"] == "user"
    content2 = messages[2]["content"]
    assert isinstance(content2, list) and len(content2) == 1
    assert content2[0]["type"] == "tool_result"
    assert content2[0]["tool_use_id"] == "call_abc123"
    assert content2[0]["content"] == "file1.txt\nfile2.txt"


def test_openai_cli_reasoning_preserved_in_roundtrip() -> None:
    """测试 OpenAI CLI 的 reasoning block 在 roundtrip 中被保留"""
    reg = _make_registry_with_cli()

    openai_cli_req = {
        "model": "gpt-5",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "思考一下"}],
            },
            {
                "type": "reasoning",
                "summary": [{"type": "summary_text", "text": "I am thinking about the problem..."}],
                "content": None,
                "encrypted_content": "xxx_encrypted",
            },
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "我想好了"}],
            },
        ],
    }

    # 转换到 internal 再转回 OPENAI_CLI
    converted = reg.convert_request(openai_cli_req, "openai:cli", "openai:cli")

    input_items = converted.get("input", [])
    # 应该有 user message, reasoning, assistant message
    assert len(input_items) >= 2

    # 找到 reasoning block
    reasoning_items = [
        i for i in input_items if isinstance(i, dict) and i.get("type") == "reasoning"
    ]
    assert len(reasoning_items) == 1
    assert "summary" in reasoning_items[0]


def test_claude_tool_use_to_openai_cli() -> None:
    """测试 Claude tool_use/tool_result 转换为 OpenAI CLI function_call/function_call_output"""
    reg = _make_registry_with_cli()

    claude_req = {
        "model": "claude-3",
        "messages": [
            {"role": "user", "content": "查看文件"},
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool_123",
                        "name": "read_file",
                        "input": {"path": "/tmp/test.txt"},
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool_123",
                        "content": "Hello World",
                    }
                ],
            },
        ],
    }

    openai_cli_req = reg.convert_request(claude_req, "claude:chat", "openai:cli")

    input_items = openai_cli_req.get("input", [])
    assert len(input_items) >= 3

    # 找到 function_call
    fc_items = [i for i in input_items if isinstance(i, dict) and i.get("type") == "function_call"]
    assert len(fc_items) == 1
    assert fc_items[0]["name"] == "read_file"
    assert fc_items[0]["call_id"] == "tool_123"

    # 找到 function_call_output
    fco_items = [
        i for i in input_items if isinstance(i, dict) and i.get("type") == "function_call_output"
    ]
    assert len(fco_items) == 1
    assert fco_items[0]["call_id"] == "tool_123"
    assert fco_items[0]["output"] == "Hello World"


def test_stream_openai_cli_in_progress_event() -> None:
    """测试 OpenAI CLI 流式 response.in_progress 事件"""
    reg = _make_registry_with_cli()
    state = StreamState()

    # response.created 事件
    created_chunk = {
        "type": "response.created",
        "response": {
            "id": "resp_123",
            "object": "response",
            "model": "gpt-5",
            "status": "in_progress",
        },
    }

    events1 = reg.convert_stream_chunk(created_chunk, "openai:cli", "claude:chat", state=state)
    assert isinstance(events1, list) and events1
    assert events1[0].get("type") == "message_start"

    # response.in_progress 事件（不应产生内容事件）
    in_progress_chunk = {
        "type": "response.in_progress",
        "response": {
            "id": "resp_123",
            "object": "response",
            "model": "gpt-5",
            "status": "in_progress",
        },
    }

    events2 = reg.convert_stream_chunk(in_progress_chunk, "openai:cli", "claude:chat", state=state)
    # response.in_progress 不应产生任何事件
    assert events2 == []


def test_stream_openai_cli_function_call_events() -> None:
    """测试 OpenAI CLI 流式 function_call 相关事件"""
    reg = _make_registry_with_cli()
    state = StreamState()

    # 首先发送 response.created
    created_chunk = {
        "type": "response.created",
        "response": {"id": "resp_456", "model": "gpt-5"},
    }
    reg.convert_stream_chunk(created_chunk, "openai:cli", "claude:chat", state=state)

    # response.output_item.added (function_call)
    output_item_chunk = {
        "type": "response.output_item.added",
        "item": {
            "type": "function_call",
            "call_id": "call_xyz",
            "name": "get_weather",
        },
    }

    events1 = reg.convert_stream_chunk(output_item_chunk, "openai:cli", "claude:chat", state=state)
    assert isinstance(events1, list) and events1
    assert events1[0].get("type") == "content_block_start"

    # response.function_call_arguments.delta
    args_delta_chunk = {
        "type": "response.function_call_arguments.delta",
        "delta": '{"city":',
    }

    events2 = reg.convert_stream_chunk(args_delta_chunk, "openai:cli", "claude:chat", state=state)
    assert isinstance(events2, list) and events2
    # ToolCallDeltaEvent 转换为 Claude 的 content_block_delta
    assert events2[0].get("type") == "content_block_delta"
    delta_obj = events2[0].get("delta", {})
    assert delta_obj.get("type") == "input_json_delta"
    assert delta_obj.get("partial_json") == '{"city":'

    # response.output_item.done (function_call)
    output_done_chunk = {
        "type": "response.output_item.done",
        "item": {
            "type": "function_call",
            "call_id": "call_xyz",
            "name": "get_weather",
            "arguments": '{"city": "Beijing"}',
        },
    }

    events3 = reg.convert_stream_chunk(output_done_chunk, "openai:cli", "claude:chat", state=state)
    assert isinstance(events3, list) and events3
    assert events3[0].get("type") == "content_block_stop"


def test_real_claude_cli_stream_response_conversion() -> None:
    """测试真实的 Claude CLI 流式响应转换（完整事件序列）

    使用来自 Claude Code 的真实流式响应数据，验证：
    - message_start, content_block_start, ping, content_block_delta,
      content_block_stop, message_delta, message_stop 的完整处理链路
    - 文本增量正确拼接
    - usage 和 stop_reason 正确提取
    """
    reg = _make_registry_with_cli()
    state = StreamState()

    # 真实的 Claude CLI 流式响应事件序列
    chunks = [
        {
            "type": "message_start",
            "message": {
                "model": "claude-opus-4-5-20251101",
                "id": "msg_01JEmQ1u53gZndRGBUBLvVZ9",
                "type": "message",
                "role": "assistant",
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {
                    "input_tokens": 3,
                    "cache_creation_input_tokens": 32760,
                    "cache_read_input_tokens": 61777,
                    "cache_creation": {
                        "ephemeral_5m_input_tokens": 32760,
                        "ephemeral_1h_input_tokens": 0,
                    },
                    "output_tokens": 2,
                    "service_tier": "standard",
                },
            },
        },
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "text", "text": ""},
        },
        {"type": "ping"},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "明"}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "白"}},
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "了，请"},
        },
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "把"}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "包"}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "含 "}},
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "tools"},
        },
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": " 具"}},
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "体内"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "容的 "},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "Claude"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": " CLI"},
        },
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": " 请"}},
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "求体"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "发给我，"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "我会一"},
        },
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "并"}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "审"}},
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "查整"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "个改"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "动。"},
        },
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {
                "input_tokens": 3,
                "cache_creation_input_tokens": 32760,
                "cache_read_input_tokens": 61777,
                "output_tokens": 42,
            },
        },
        {"type": "message_stop"},
    ]

    # 收集所有转换后的 OpenAI 格式事件
    all_openai_events: list[dict[str, Any]] = []
    for chunk in chunks:
        events = reg.convert_stream_chunk(chunk, "claude:cli", "openai:chat", state=state)
        all_openai_events.extend(events)

    # 验证转换结果
    assert len(all_openai_events) > 0

    # 第一个事件应该是 chat.completion.chunk（来自 message_start）
    assert all_openai_events[0].get("object") == "chat.completion.chunk"
    assert all_openai_events[0].get("model") == "claude-opus-4-5-20251101"

    # 收集所有文本增量
    text_deltas = []
    for evt in all_openai_events:
        choices = evt.get("choices") or []
        if choices:
            delta = choices[0].get("delta", {})
            content = delta.get("content")
            if content:
                text_deltas.append(content)

    # 验证文本拼接结果
    full_text = "".join(text_deltas)
    assert "明白了" in full_text
    assert "tools" in full_text
    assert "Claude CLI" in full_text
    assert "请求体发给我" in full_text

    # 验证最后一个事件有 finish_reason
    last_with_finish = [
        e for e in all_openai_events if (e.get("choices") or [{}])[0].get("finish_reason")
    ]
    assert len(last_with_finish) > 0
    assert last_with_finish[-1]["choices"][0]["finish_reason"] == "stop"


def test_real_claude_cli_stream_to_openai_cli() -> None:
    """测试 Claude CLI 流式响应转换为 OpenAI CLI (Responses API) 格式"""
    reg = _make_registry_with_cli()
    state = StreamState()

    # 简化的真实事件序列
    chunks = [
        {
            "type": "message_start",
            "message": {
                "model": "claude-opus-4-5-20251101",
                "id": "msg_test123",
                "type": "message",
                "role": "assistant",
                "content": [],
                "stop_reason": None,
                "usage": {"input_tokens": 10, "output_tokens": 0},
            },
        },
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "ping"},
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "Hello"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": " World"},
        },
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
        {"type": "message_stop"},
    ]

    all_events: list[dict[str, Any]] = []
    for chunk in chunks:
        events = reg.convert_stream_chunk(chunk, "claude:cli", "openai:cli", state=state)
        all_events.extend(events)

    # 验证 OpenAI CLI 格式事件
    assert len(all_events) > 0

    # 应该有 response.created 事件
    created_events = [e for e in all_events if e.get("type") == "response.created"]
    assert len(created_events) == 1

    # 应该有 response.output_text.delta 事件
    delta_events = [e for e in all_events if e.get("type") == "response.output_text.delta"]
    assert len(delta_events) >= 2
    deltas = [e.get("delta") for e in delta_events]
    assert "Hello" in deltas
    assert " World" in deltas

    # 应该有 response.completed 或 response.done 事件
    done_events = [
        e for e in all_events if e.get("type") in ("response.completed", "response.done")
    ]
    assert len(done_events) >= 1

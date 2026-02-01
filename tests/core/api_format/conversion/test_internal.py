"""
internal 数据结构单元测试

目标：
- 验证 dataclass/Enum 可正确实例化
- 验证 ContentBlock 联合类型可用于运行时判断
- 验证 StreamState.substate() 隔离机制
- 验证各类型的默认值、字段访问、序列化
"""

from __future__ import annotations

from dataclasses import asdict
from typing import get_args

import pytest

from src.core.api_format.conversion.internal import (
    ContentBlock,
    ContentType,
    ErrorType,
    FormatCapabilities,
    ImageBlock,
    InstructionSegment,
    InternalError,
    InternalMessage,
    InternalRequest,
    InternalResponse,
    Role,
    StopReason,
    TextBlock,
    ToolChoice,
    ToolChoiceType,
    ToolDefinition,
    ToolResultBlock,
    ToolUseBlock,
    UnknownBlock,
    UsageInfo,
)
from src.core.api_format.conversion.stream_state import StreamState

# ============================================================================
# Enum 类型测试
# ============================================================================


class TestRoleEnum:
    def test_role_values(self) -> None:
        assert Role.USER.value == "user"
        assert Role.ASSISTANT.value == "assistant"
        assert Role.SYSTEM.value == "system"
        assert Role.DEVELOPER.value == "developer"
        assert Role.TOOL.value == "tool"
        assert Role.UNKNOWN.value == "unknown"

    def test_role_is_str_subclass(self) -> None:
        assert isinstance(Role.USER, str)
        assert Role.USER == "user"


class TestContentTypeEnum:
    def test_content_type_values(self) -> None:
        assert ContentType.TEXT.value == "text"
        assert ContentType.IMAGE.value == "image"
        assert ContentType.TOOL_USE.value == "tool_use"
        assert ContentType.TOOL_RESULT.value == "tool_result"
        assert ContentType.UNKNOWN.value == "unknown"


class TestStopReasonEnum:
    def test_stop_reason_values(self) -> None:
        assert StopReason.END_TURN.value == "end_turn"
        assert StopReason.MAX_TOKENS.value == "max_tokens"
        assert StopReason.STOP_SEQUENCE.value == "stop_sequence"
        assert StopReason.TOOL_USE.value == "tool_use"
        assert StopReason.PAUSE_TURN.value == "pause_turn"
        assert StopReason.REFUSAL.value == "refusal"
        assert StopReason.CONTENT_FILTERED.value == "content_filtered"
        assert StopReason.UNKNOWN.value == "unknown"


class TestErrorTypeEnum:
    def test_error_type_values(self) -> None:
        assert ErrorType.INVALID_REQUEST.value == "invalid_request"
        assert ErrorType.AUTHENTICATION.value == "authentication"
        assert ErrorType.PERMISSION_DENIED.value == "permission_denied"
        assert ErrorType.NOT_FOUND.value == "not_found"
        assert ErrorType.RATE_LIMIT.value == "rate_limit"
        assert ErrorType.OVERLOADED.value == "overloaded"
        assert ErrorType.SERVER_ERROR.value == "server_error"
        assert ErrorType.CONTENT_FILTERED.value == "content_filtered"
        assert ErrorType.CONTEXT_LENGTH_EXCEEDED.value == "context_length_exceeded"
        assert ErrorType.UNKNOWN.value == "unknown"


class TestToolChoiceTypeEnum:
    def test_tool_choice_type_values(self) -> None:
        assert ToolChoiceType.AUTO.value == "auto"
        assert ToolChoiceType.NONE.value == "none"
        assert ToolChoiceType.REQUIRED.value == "required"
        assert ToolChoiceType.TOOL.value == "tool"


# ============================================================================
# ContentBlock 类型测试
# ============================================================================


def test_content_block_runtime_check() -> None:
    block_types = get_args(ContentBlock)
    assert block_types, "typing.get_args(ContentBlock) 应返回可用的类型列表"

    assert isinstance(TextBlock(text="hi"), block_types)
    assert isinstance(ImageBlock(url="https://example.com/a.png"), block_types)
    assert isinstance(ToolUseBlock(tool_id="t1", tool_name="x"), block_types)
    assert isinstance(ToolResultBlock(tool_use_id="t1", output={"ok": True}), block_types)
    assert isinstance(UnknownBlock(raw_type="weird", payload={"x": 1}), block_types)


def test_internal_error_to_debug_dict() -> None:
    err = InternalError(
        type=ErrorType.INVALID_REQUEST,
        message="bad request",
        code="bad_request",
        param="messages",
        retryable=False,
        extra={"raw": {"type": "invalid_request_error"}},
    )
    d = err.to_debug_dict()
    assert d["type"] == "invalid_request"
    assert d["message"] == "bad request"
    assert d["code"] == "bad_request"
    assert d["param"] == "messages"
    assert d["retryable"] is False
    assert isinstance(d["extra"], dict)


def test_internal_request_debug_dict_and_serialization() -> None:
    req = InternalRequest(
        model="m",
        messages=[],
        instructions=[
            InstructionSegment(role=Role.SYSTEM, text="sys1"),
            InstructionSegment(role=Role.DEVELOPER, text="dev1"),
        ],
        system="sys1\n\ndev1",
        stream=True,
        extra={"raw": {"openai_messages": []}},
    )
    d = req.to_debug_dict()
    assert d["instruction_count"] == 2
    assert d["message_count"] == 0
    assert d["has_system"] is True
    assert d["stream"] is True

    # asdict 只要能跑通即可（Enum 会保留为对象，属于预期）
    dumped = asdict(req)
    assert dumped["model"] == "m"
    assert isinstance(dumped["instructions"], list)


def test_internal_response_debug_dict() -> None:
    resp = InternalResponse(
        id="r1",
        model="m",
        content=[TextBlock(text="hi")],
        stop_reason=StopReason.END_TURN,
        usage=UsageInfo(input_tokens=1, output_tokens=2, total_tokens=3),
    )
    d = resp.to_debug_dict()
    assert d["id"] == "r1"
    assert d["stop_reason"] == "end_turn"
    assert d["usage"] == {"input": 1, "output": 2}


def test_stream_state_substate_isolated() -> None:
    state = StreamState()
    openai_state = state.substate("openai")
    claude_state = state.substate("CLAUDE")

    openai_state["x"] = 1
    assert "x" not in claude_state
    assert state.substate("OPENAI") is openai_state


# ============================================================================
# ContentBlock 各子类型详细测试
# ============================================================================


class TestTextBlock:
    def test_default_values(self) -> None:
        block = TextBlock()
        assert block.type == ContentType.TEXT
        assert block.text == ""
        assert block.extra == {}

    def test_with_content(self) -> None:
        block = TextBlock(text="Hello, world!", extra={"source": "test"})
        assert block.text == "Hello, world!"
        assert block.extra == {"source": "test"}

    def test_type_is_readonly(self) -> None:
        block = TextBlock(text="hi")
        assert block.type == ContentType.TEXT


class TestImageBlock:
    def test_with_url(self) -> None:
        block = ImageBlock(url="https://example.com/img.png")
        assert block.type == ContentType.IMAGE
        assert block.url == "https://example.com/img.png"
        assert block.data is None
        assert block.media_type is None

    def test_with_base64_data(self) -> None:
        block = ImageBlock(data="base64encodeddata", media_type="image/png")
        assert block.data == "base64encodeddata"
        assert block.media_type == "image/png"
        assert block.url is None


class TestToolUseBlock:
    def test_default_values(self) -> None:
        block = ToolUseBlock()
        assert block.type == ContentType.TOOL_USE
        assert block.tool_id == ""
        assert block.tool_name == ""
        assert block.tool_input == {}

    def test_with_values(self) -> None:
        block = ToolUseBlock(
            tool_id="call_123",
            tool_name="get_weather",
            tool_input={"city": "Beijing"},
        )
        assert block.tool_id == "call_123"
        assert block.tool_name == "get_weather"
        assert block.tool_input == {"city": "Beijing"}


class TestToolResultBlock:
    def test_default_values(self) -> None:
        block = ToolResultBlock()
        assert block.type == ContentType.TOOL_RESULT
        assert block.tool_use_id == ""
        assert block.output is None
        assert block.content_text is None
        assert block.is_error is False

    def test_with_success_output(self) -> None:
        block = ToolResultBlock(
            tool_use_id="call_123",
            output={"temperature": 25},
            content_text="Temperature: 25C",
        )
        assert block.tool_use_id == "call_123"
        assert block.output == {"temperature": 25}
        assert block.is_error is False

    def test_with_error_output(self) -> None:
        block = ToolResultBlock(
            tool_use_id="call_456",
            output="Error: city not found",
            is_error=True,
        )
        assert block.is_error is True


class TestUnknownBlock:
    def test_default_values(self) -> None:
        block = UnknownBlock()
        assert block.type == ContentType.UNKNOWN
        assert block.raw_type == ""
        assert block.payload == {}

    def test_with_values(self) -> None:
        block = UnknownBlock(
            raw_type="custom_block",
            payload={"key": "value"},
            extra={"source": "gemini"},
        )
        assert block.raw_type == "custom_block"
        assert block.payload == {"key": "value"}


# ============================================================================
# InternalMessage 测试
# ============================================================================


class TestInternalMessage:
    def test_simple_user_message(self) -> None:
        msg = InternalMessage(role=Role.USER, content=[TextBlock(text="Hello")])
        assert msg.role == Role.USER
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], TextBlock)

    def test_assistant_with_tool_use(self) -> None:
        msg = InternalMessage(
            role=Role.ASSISTANT,
            content=[
                TextBlock(text="Let me check the weather"),
                ToolUseBlock(
                    tool_id="t1", tool_name="get_weather", tool_input={"city": "Shanghai"}
                ),
            ],
        )
        assert msg.role == Role.ASSISTANT
        assert len(msg.content) == 2
        assert msg.content[0].type == ContentType.TEXT
        assert msg.content[1].type == ContentType.TOOL_USE

    def test_tool_message(self) -> None:
        msg = InternalMessage(
            role=Role.TOOL,
            content=[ToolResultBlock(tool_use_id="t1", output="Sunny, 28C")],
        )
        assert msg.role == Role.TOOL

    def test_with_extra(self) -> None:
        msg = InternalMessage(
            role=Role.USER,
            content=[],
            extra={"original_format": "openai"},
        )
        assert msg.extra == {"original_format": "openai"}


# ============================================================================
# InstructionSegment 测试
# ============================================================================


class TestInstructionSegment:
    def test_system_instruction(self) -> None:
        seg = InstructionSegment(role=Role.SYSTEM, text="You are a helpful assistant.")
        assert seg.role == Role.SYSTEM
        assert seg.text == "You are a helpful assistant."

    def test_developer_instruction(self) -> None:
        seg = InstructionSegment(role=Role.DEVELOPER, text="Always respond in JSON format.")
        assert seg.role == Role.DEVELOPER
        assert seg.text == "Always respond in JSON format."

    def test_with_extra(self) -> None:
        seg = InstructionSegment(
            role=Role.SYSTEM,
            text="test",
            extra={"cache_control": {"type": "ephemeral"}},
        )
        assert seg.extra == {"cache_control": {"type": "ephemeral"}}


# ============================================================================
# ToolDefinition 和 ToolChoice 测试
# ============================================================================


class TestToolDefinition:
    def test_minimal(self) -> None:
        tool = ToolDefinition(name="get_time")
        assert tool.name == "get_time"
        assert tool.description is None
        assert tool.parameters is None

    def test_full(self) -> None:
        tool = ToolDefinition(
            name="get_weather",
            description="Get current weather for a city",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"},
                },
                "required": ["city"],
            },
            extra={"strict": True},
        )
        assert tool.name == "get_weather"
        assert tool.description == "Get current weather for a city"
        assert tool.parameters is not None
        assert "city" in tool.parameters["properties"]


class TestToolChoice:
    def test_auto(self) -> None:
        choice = ToolChoice(type=ToolChoiceType.AUTO)
        assert choice.type == ToolChoiceType.AUTO
        assert choice.tool_name is None

    def test_none(self) -> None:
        choice = ToolChoice(type=ToolChoiceType.NONE)
        assert choice.type == ToolChoiceType.NONE

    def test_required(self) -> None:
        choice = ToolChoice(type=ToolChoiceType.REQUIRED)
        assert choice.type == ToolChoiceType.REQUIRED

    def test_specific_tool(self) -> None:
        choice = ToolChoice(type=ToolChoiceType.TOOL, tool_name="get_weather")
        assert choice.type == ToolChoiceType.TOOL
        assert choice.tool_name == "get_weather"


# ============================================================================
# UsageInfo 测试
# ============================================================================


class TestUsageInfo:
    def test_default_values(self) -> None:
        usage = UsageInfo()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_tokens == 0
        assert usage.cache_read_tokens == 0
        assert usage.cache_write_tokens == 0

    def test_with_values(self) -> None:
        usage = UsageInfo(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cache_read_tokens=20,
            cache_write_tokens=10,
        )
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.total_tokens == 150
        assert usage.cache_read_tokens == 20
        assert usage.cache_write_tokens == 10

    def test_with_extra(self) -> None:
        usage = UsageInfo(
            input_tokens=10,
            output_tokens=5,
            extra={"reasoning_tokens": 100},
        )
        assert usage.extra == {"reasoning_tokens": 100}


# ============================================================================
# FormatCapabilities 测试
# ============================================================================


class TestFormatCapabilities:
    def test_default_values(self) -> None:
        caps = FormatCapabilities()
        assert caps.supports_stream is True
        assert caps.supports_error_conversion is True
        assert caps.supports_tools is True
        assert caps.supports_images is False
        assert caps.supported_features == frozenset()

    def test_custom_values(self) -> None:
        caps = FormatCapabilities(
            supports_stream=False,
            supports_error_conversion=True,
            supports_tools=False,
            supports_images=True,
            supported_features=frozenset({"vision", "function_calling"}),
        )
        assert caps.supports_stream is False
        assert caps.supports_images is True
        assert "vision" in caps.supported_features

    def test_is_frozen(self) -> None:
        caps = FormatCapabilities()
        with pytest.raises(Exception):
            caps.supports_stream = False  # type: ignore


# ============================================================================
# InternalRequest 详细测试
# ============================================================================


class TestInternalRequest:
    def test_minimal(self) -> None:
        req = InternalRequest(model="gpt-4", messages=[])
        assert req.model == "gpt-4"
        assert req.messages == []
        assert req.stream is False
        assert req.max_tokens is None
        assert req.tools is None

    def test_with_messages(self) -> None:
        req = InternalRequest(
            model="claude-3",
            messages=[
                InternalMessage(role=Role.USER, content=[TextBlock(text="Hi")]),
                InternalMessage(role=Role.ASSISTANT, content=[TextBlock(text="Hello!")]),
            ],
        )
        assert len(req.messages) == 2
        assert req.messages[0].role == Role.USER
        assert req.messages[1].role == Role.ASSISTANT

    def test_with_tools(self) -> None:
        req = InternalRequest(
            model="gpt-4",
            messages=[],
            tools=[ToolDefinition(name="get_time"), ToolDefinition(name="get_weather")],
            tool_choice=ToolChoice(type=ToolChoiceType.AUTO),
        )
        assert req.tools is not None
        assert len(req.tools) == 2
        assert req.tool_choice is not None
        assert req.tool_choice.type == ToolChoiceType.AUTO

    def test_to_debug_dict_with_tools(self) -> None:
        req = InternalRequest(
            model="m",
            messages=[InternalMessage(role=Role.USER, content=[TextBlock(text="test")])],
            tools=[ToolDefinition(name="tool1")],
            stream=True,
            extra={"key": "value"},
        )
        d = req.to_debug_dict()
        assert d["tool_count"] == 1
        assert d["message_count"] == 1
        assert d["stream"] is True
        assert "key" in d["extra_keys"]


# ============================================================================
# InternalResponse 详细测试
# ============================================================================


class TestInternalResponse:
    def test_minimal(self) -> None:
        resp = InternalResponse(id="r1", model="gpt-4", content=[])
        assert resp.id == "r1"
        assert resp.model == "gpt-4"
        assert resp.content == []
        assert resp.stop_reason is None
        assert resp.usage is None

    def test_with_tool_use(self) -> None:
        resp = InternalResponse(
            id="r1",
            model="claude-3",
            content=[
                TextBlock(text="I'll check that for you"),
                ToolUseBlock(tool_id="t1", tool_name="search", tool_input={"q": "test"}),
            ],
            stop_reason=StopReason.TOOL_USE,
        )
        assert resp.stop_reason == StopReason.TOOL_USE
        assert len(resp.content) == 2

    def test_to_debug_dict_without_usage(self) -> None:
        resp = InternalResponse(id="r1", model="m", content=[])
        d = resp.to_debug_dict()
        assert d["usage"] is None

    def test_to_debug_dict_with_all_stop_reasons(self) -> None:
        for reason in StopReason:
            resp = InternalResponse(
                id="r1",
                model="m",
                content=[],
                stop_reason=reason,
            )
            d = resp.to_debug_dict()
            assert d["stop_reason"] == reason.value


# ============================================================================
# InternalError 详细测试
# ============================================================================


class TestInternalError:
    def test_minimal(self) -> None:
        err = InternalError(type=ErrorType.UNKNOWN, message="Unknown error")
        assert err.type == ErrorType.UNKNOWN
        assert err.message == "Unknown error"
        assert err.code is None
        assert err.retryable is False

    def test_retryable_error(self) -> None:
        err = InternalError(
            type=ErrorType.RATE_LIMIT,
            message="Rate limit exceeded",
            code="rate_limit_exceeded",
            retryable=True,
        )
        assert err.type == ErrorType.RATE_LIMIT
        assert err.retryable is True

    def test_all_error_types_in_debug_dict(self) -> None:
        for err_type in ErrorType:
            err = InternalError(type=err_type, message="test")
            d = err.to_debug_dict()
            assert d["type"] == err_type.value


# ============================================================================
# asdict 序列化测试
# ============================================================================


class TestSerialization:
    def test_content_block_asdict(self) -> None:
        block = TextBlock(text="hello")
        d = asdict(block)
        assert d["text"] == "hello"
        assert d["type"] == ContentType.TEXT

    def test_tool_use_block_asdict(self) -> None:
        block = ToolUseBlock(
            tool_id="t1",
            tool_name="test",
            tool_input={"a": 1},
        )
        d = asdict(block)
        assert d["tool_id"] == "t1"
        assert d["tool_input"] == {"a": 1}

    def test_message_asdict(self) -> None:
        msg = InternalMessage(
            role=Role.USER,
            content=[TextBlock(text="hi")],
        )
        d = asdict(msg)
        assert d["role"] == Role.USER
        assert len(d["content"]) == 1

    def test_response_asdict(self) -> None:
        resp = InternalResponse(
            id="r1",
            model="m",
            content=[TextBlock(text="response")],
            stop_reason=StopReason.END_TURN,
            usage=UsageInfo(input_tokens=10, output_tokens=5),
        )
        d = asdict(resp)
        assert d["id"] == "r1"
        assert d["stop_reason"] == StopReason.END_TURN
        assert d["usage"]["input_tokens"] == 10

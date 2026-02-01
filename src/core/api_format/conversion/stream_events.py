"""
类型安全的流式事件定义（InternalStreamEvent）

用于把 OpenAI/Claude/Gemini 的流式协议映射为统一事件序列，再由目标格式 Normalizer 输出。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .internal import ContentType, InternalError, StopReason, UsageInfo


class StreamEventType(str, Enum):
    """流式事件类型"""

    MESSAGE_START = "message_start"
    CONTENT_BLOCK_START = "content_block_start"
    CONTENT_DELTA = "content_delta"
    TOOL_CALL_DELTA = "tool_call_delta"
    CONTENT_BLOCK_STOP = "content_block_stop"
    MESSAGE_STOP = "message_stop"
    USAGE = "usage"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class MessageStartEvent:
    """消息开始事件"""

    type: StreamEventType = field(default=StreamEventType.MESSAGE_START, init=False)
    message_id: str = ""
    model: str = ""
    usage: UsageInfo | None = None  # Claude 流式响应的 message_start 可能包含 usage
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContentBlockStartEvent:
    """内容块开始事件"""

    type: StreamEventType = field(default=StreamEventType.CONTENT_BLOCK_START, init=False)
    block_index: int = 0
    block_type: ContentType = ContentType.TEXT
    # 工具调用时使用（TOOL_USE block）
    tool_id: str | None = None
    tool_name: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContentDeltaEvent:
    """内容增量事件"""

    type: StreamEventType = field(default=StreamEventType.CONTENT_DELTA, init=False)
    block_index: int = 0
    text_delta: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallDeltaEvent:
    """工具调用增量事件（工具输入 JSON 的字符串片段）"""

    type: StreamEventType = field(default=StreamEventType.TOOL_CALL_DELTA, init=False)
    block_index: int = 0
    tool_id: str = ""
    input_delta: str = ""  # JSON 字符串片段
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContentBlockStopEvent:
    """内容块结束事件"""

    type: StreamEventType = field(default=StreamEventType.CONTENT_BLOCK_STOP, init=False)
    block_index: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class MessageStopEvent:
    """消息结束事件"""

    type: StreamEventType = field(default=StreamEventType.MESSAGE_STOP, init=False)
    stop_reason: StopReason | None = None
    usage: UsageInfo | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageEvent:
    """使用量事件"""

    type: StreamEventType = field(default=StreamEventType.USAGE, init=False)
    usage: UsageInfo = field(default_factory=UsageInfo)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorEvent:
    """错误事件"""

    type: StreamEventType = field(default=StreamEventType.ERROR, init=False)
    error: InternalError
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class UnknownStreamEvent:
    """未知事件（用于前向兼容）"""

    type: StreamEventType = field(default=StreamEventType.UNKNOWN, init=False)
    raw_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


InternalStreamEvent = (
    MessageStartEvent
    | ContentBlockStartEvent
    | ContentDeltaEvent
    | ToolCallDeltaEvent
    | ContentBlockStopEvent
    | MessageStopEvent
    | UsageEvent
    | ErrorEvent
    | UnknownStreamEvent
)


__all__ = [
    "StreamEventType",
    "MessageStartEvent",
    "ContentBlockStartEvent",
    "ContentDeltaEvent",
    "ToolCallDeltaEvent",
    "ContentBlockStopEvent",
    "MessageStopEvent",
    "UsageEvent",
    "ErrorEvent",
    "UnknownStreamEvent",
    "InternalStreamEvent",
]

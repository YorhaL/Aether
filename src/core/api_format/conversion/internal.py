"""
格式转换内部表示（Internal / Canonical Format）

该模块定义 Hub-and-Spoke 架构的“中间表示法”，用于把不同 Provider 的请求/响应/流式事件
统一映射到稳定的内部结构，再转换为目标格式。

设计原则：
- 类型安全：尽量用 dataclass + Enum 表达语义，便于 IDE/静态检查
- 可扩展：未知/不可逆字段写入 extra/raw，避免静默丢失
- 兼容优先：UnknownBlock 在内部保留，但默认在输出阶段丢弃（可观测、可随时调整策略）
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    DEVELOPER = "developer"
    TOOL = "tool"
    UNKNOWN = "unknown"


class ContentType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    UNKNOWN = "unknown"


class StopReason(str, Enum):
    END_TURN = "end_turn"
    MAX_TOKENS = "max_tokens"
    STOP_SEQUENCE = "stop_sequence"
    TOOL_USE = "tool_use"
    # Claude streaming 里会出现（官方文档枚举）：pause_turn / refusal
    PAUSE_TURN = "pause_turn"
    REFUSAL = "refusal"
    CONTENT_FILTERED = "content_filtered"
    UNKNOWN = "unknown"


class ErrorType(str, Enum):
    INVALID_REQUEST = "invalid_request"
    AUTHENTICATION = "authentication"
    PERMISSION_DENIED = "permission_denied"
    NOT_FOUND = "not_found"
    RATE_LIMIT = "rate_limit"
    OVERLOADED = "overloaded"
    SERVER_ERROR = "server_error"
    CONTENT_FILTERED = "content_filtered"
    CONTEXT_LENGTH_EXCEEDED = "context_length_exceeded"
    UNKNOWN = "unknown"


@dataclass
class TextBlock:
    """文本内容块"""

    type: ContentType = field(default=ContentType.TEXT, init=False)
    text: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageBlock:
    """图片内容块"""

    type: ContentType = field(default=ContentType.IMAGE, init=False)
    # base64 编码的图片数据（二选一）
    data: str | None = None
    media_type: str | None = None
    # 或者 URL 引用
    url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolUseBlock:
    """工具调用内容块"""

    type: ContentType = field(default=ContentType.TOOL_USE, init=False)
    tool_id: str = ""
    tool_name: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResultBlock:
    """工具结果内容块"""

    type: ContentType = field(default=ContentType.TOOL_RESULT, init=False)
    tool_use_id: str = ""  # 对应的 ToolUseBlock.tool_id
    # 工具输出可能是纯文本，也可能是结构化 JSON（Gemini functionResponse 等）
    output: Any = None
    content_text: str | None = None
    is_error: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class UnknownBlock:
    """未知内容块（用于前向兼容）"""

    type: ContentType = field(default=ContentType.UNKNOWN, init=False)
    raw_type: str = ""  # 原始的类型字符串（各格式不一致）
    payload: dict[str, Any] = field(default_factory=dict)  # 原始结构（尽量保持）
    extra: dict[str, Any] = field(default_factory=dict)


ContentBlock = TextBlock | ImageBlock | ToolUseBlock | ToolResultBlock | UnknownBlock


@dataclass
class InternalMessage:
    """统一的消息表示"""

    role: Role
    content: list[ContentBlock]  # 统一使用列表，纯文本用单个 TextBlock
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolDefinition:
    """统一的工具定义"""

    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None  # JSON Schema
    extra: dict[str, Any] = field(default_factory=dict)


class ToolChoiceType(str, Enum):
    AUTO = "auto"
    NONE = "none"
    REQUIRED = "required"
    TOOL = "tool"


@dataclass
class ToolChoice:
    """统一的工具选择"""

    type: ToolChoiceType
    tool_name: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class InstructionSegment:
    """系统/开发者指令段（用于保留 OpenAI system/developer 结构与顺序）"""

    role: Role  # 仅允许 Role.SYSTEM / Role.DEVELOPER
    text: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class InternalRequest:
    """统一的请求表示"""

    model: str
    messages: list[InternalMessage]

    # 指令层：保留 system/developer 结构与顺序
    instructions: list[InstructionSegment] = field(default_factory=list)

    # 兼容字段：instructions 的 join 文本（无 role 标签），用于 Claude/Gemini 这类仅接受字符串 system 的格式
    system: str | None = None

    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    stop_sequences: list[str] | None = None
    stream: bool = False
    tools: list[ToolDefinition] | None = None
    tool_choice: ToolChoice | None = None  # auto/none/required 或指定 tool_name
    extra: dict[str, Any] = field(default_factory=dict)  # 未识别字段透传

    def to_debug_dict(self) -> dict[str, Any]:
        """用于日志和调试的简化表示"""
        return {
            "model": self.model,
            "instruction_count": len(self.instructions),
            "message_count": len(self.messages),
            "has_system": bool(self.instructions) or bool(self.system),
            "max_tokens": self.max_tokens,
            "stream": self.stream,
            "tool_count": len(self.tools) if self.tools else 0,
            "extra_keys": list(self.extra.keys()),
        }


@dataclass
class UsageInfo:
    """统一的使用量信息"""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class InternalResponse:
    """统一的响应表示"""

    id: str
    model: str
    content: list[ContentBlock]
    stop_reason: StopReason | None = None
    usage: UsageInfo | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_debug_dict(self) -> dict[str, Any]:
        """用于日志和调试的简化表示"""
        usage = None
        if self.usage:
            usage = {
                "input": self.usage.input_tokens,
                "output": self.usage.output_tokens,
            }
        return {
            "id": self.id,
            "model": self.model,
            "content_block_count": len(self.content),
            "stop_reason": self.stop_reason.value if self.stop_reason else None,
            "usage": usage,
            "extra_keys": list(self.extra.keys()),
        }


@dataclass
class InternalError:
    """统一的错误表示"""

    type: ErrorType
    message: str
    code: str | None = None  # 原始错误码
    param: str | None = None  # 导致错误的参数
    retryable: bool = False  # 是否可重试
    extra: dict[str, Any] = field(default_factory=dict)

    def to_debug_dict(self) -> dict[str, Any]:
        """用于日志和调试"""
        return {
            "type": self.type.value,
            "message": self.message,
            "code": self.code,
            "param": self.param,
            "retryable": self.retryable,
            "extra": self.extra,
        }


@dataclass(frozen=True)
class FormatCapabilities:
    supports_stream: bool = True
    supports_error_conversion: bool = True
    supports_tools: bool = True
    supports_images: bool = False
    supported_features: frozenset[str] = field(default_factory=frozenset)


__all__ = [
    "Role",
    "ContentType",
    "StopReason",
    "ErrorType",
    "ToolChoiceType",
    "TextBlock",
    "ImageBlock",
    "ToolUseBlock",
    "ToolResultBlock",
    "UnknownBlock",
    "ContentBlock",
    "InternalMessage",
    "InstructionSegment",
    "ToolDefinition",
    "ToolChoice",
    "InternalRequest",
    "UsageInfo",
    "InternalResponse",
    "InternalError",
    "FormatCapabilities",
]

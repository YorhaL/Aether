"""
字段映射配置（集中定义）

该文件用于承载：
- role/stop_reason/usage/error 的常见映射表

注意：
- conversion 层只负责 body 结构转换，不维护 model_in_body/stream_in_body/auth_header 等元数据；
  这些应复用 `src/core/api_format/metadata.py`（API_FORMAT_DEFINITIONS）作为单一事实来源。
"""

# 角色映射（仅作为辅助；system/tool 的具体落点以 Normalizer 规则为准）
ROLE_MAPPINGS: dict[str, dict[str, str]] = {
    "OPENAI": {
        "user": "user",
        "assistant": "assistant",
        "system": "system",
        "developer": "developer",
        "tool": "tool",
    },
    "CLAUDE": {"user": "user", "assistant": "assistant"},
    "GEMINI": {"user": "user", "assistant": "model"},
}


# 停止原因映射（internal -> provider），未知值使用 UNKNOWN 并写入 extra/raw
STOP_REASON_MAPPINGS: dict[str, dict[str, str]] = {
    "CLAUDE": {
        "end_turn": "end_turn",
        "max_tokens": "max_tokens",
        "stop_sequence": "stop_sequence",
        "tool_use": "tool_use",
        # Claude 通常以错误/阻断体现，这里仅兜底
        "content_filtered": "end_turn",
        "unknown": "end_turn",
    },
    "OPENAI": {
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
        "tool_use": "tool_calls",
        "content_filtered": "content_filter",
        "unknown": "stop",
    },
    "GEMINI": {
        "end_turn": "STOP",
        "max_tokens": "MAX_TOKENS",
        "stop_sequence": "STOP",
        # Gemini finishReason 对工具调用并没有稳定等价枚举，这里保守兜底为 STOP
        "tool_use": "STOP",
        "content_filtered": "SAFETY",
        "unknown": "OTHER",
    },
}


# 使用量字段映射（provider usage field -> internal UsageInfo field）
USAGE_FIELD_MAPPINGS: dict[str, dict[str, str]] = {
    "CLAUDE": {
        "input_tokens": "input_tokens",
        "output_tokens": "output_tokens",
        "cache_read_input_tokens": "cache_read_tokens",
        "cache_creation_input_tokens": "cache_write_tokens",
    },
    "OPENAI": {
        "prompt_tokens": "input_tokens",
        "completion_tokens": "output_tokens",
        "total_tokens": "total_tokens",
    },
    "GEMINI": {
        "promptTokenCount": "input_tokens",
        "candidatesTokenCount": "output_tokens",
        "totalTokenCount": "total_tokens",
        "cachedContentTokenCount": "cache_read_tokens",
    },
}


# 错误类型映射（provider -> internal ErrorType.value）
ERROR_TYPE_MAPPINGS: dict[str, dict[str, str]] = {
    "CLAUDE": {
        "invalid_request_error": "invalid_request",
        "authentication_error": "authentication",
        "permission_error": "permission_denied",
        "not_found_error": "not_found",
        "rate_limit_error": "rate_limit",
        "timeout_error": "server_error",
        "overloaded_error": "overloaded",
        "billing_error": "permission_denied",
        "api_error": "server_error",
    },
    "OPENAI": {
        "invalid_request_error": "invalid_request",
        "invalid_api_key": "authentication",
        "insufficient_quota": "rate_limit",
        "rate_limit_exceeded": "rate_limit",
        "server_error": "server_error",
        "context_length_exceeded": "context_length_exceeded",
        "content_policy_violation": "content_filtered",
    },
    "GEMINI": {
        "INVALID_ARGUMENT": "invalid_request",
        "UNAUTHENTICATED": "authentication",
        "PERMISSION_DENIED": "permission_denied",
        "NOT_FOUND": "not_found",
        "RESOURCE_EXHAUSTED": "rate_limit",
        "INTERNAL": "server_error",
        "UNAVAILABLE": "overloaded",
    },
}


# 可重试的错误类型（internal ErrorType.value）
RETRYABLE_ERROR_TYPES: set[str] = {
    "rate_limit",
    "overloaded",
    "server_error",
}


__all__ = [
    "ROLE_MAPPINGS",
    "STOP_REASON_MAPPINGS",
    "USAGE_FIELD_MAPPINGS",
    "ERROR_TYPE_MAPPINGS",
    "RETRYABLE_ERROR_TYPES",
]

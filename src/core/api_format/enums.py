"""API format enums.

新模式下系统使用结构化的 (ApiFamily, EndpointKind) / `family:kind` signature 作为唯一标识。
"""

from enum import Enum


class ApiFamily(str, Enum):
    """
    协议族（兼容族）- 决定数据格式与认证方式的基础。

    注意：不叫 Provider 避免与 ORM 的 Provider 模型撞名。
    """

    OPENAI = "openai"  # openai-compatible（含 deepseek, grok, qwen 等）
    CLAUDE = "claude"  # claude-compatible
    GEMINI = "gemini"  # gemini-compatible


class EndpointKind(str, Enum):
    """
    端点变体 - 决定 API 路径/认证变体/数据格式变体等。

    注意：不复用现有 EndpointType（EndpointType 用于请求上下文检测/功能分类）。
    """

    CHAT = "chat"
    CLI = "cli"
    VIDEO = "video"
    IMAGE = "image"


class AuthMethod(str, Enum):
    """认证方式 - 决定如何构造认证 Header"""

    BEARER = "bearer"  # Authorization: Bearer {token}
    API_KEY = "api_key"  # x-api-key: {key}
    GOOG_API_KEY = "goog_key"  # x-goog-api-key: {key}
    OAUTH2 = "oauth2"  # Google OAuth2 / Service Account
    QUERY_KEY = "query_key"  # ?key={key} (Gemini 备用)


class EndpointType(str, Enum):
    """端点类型 - 决定 API 功能类别"""

    CHAT = "chat"  # Chat/Completion API
    VIDEO = "video"  # Video Generation API
    FILES = "files"  # Files API
    IMAGE = "image"  # Image Generation API
    AUDIO = "audio"  # Audio API
    EMBEDDING = "embedding"  # Embedding API
    MODELS = "models"  # Models API


__all__ = [
    "ApiFamily",
    "EndpointKind",
    "AuthMethod",
    "EndpointType",
]

"""
认证处理器

将认证逻辑从 API 格式中解耦，支持多种认证方式。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from src.core.api_format.enums import AuthMethod
from src.core.api_format.metadata import resolve_endpoint_definition
from src.core.api_format.signature import EndpointSignature

if TYPE_CHECKING:
    from starlette.requests import Request


class AuthHandler(ABC):
    """认证处理器基类"""

    @abstractmethod
    def extract_credentials(self, request: Request) -> str | None:
        """从请求中提取凭证"""

    @abstractmethod
    def build_headers(self, credentials: str) -> dict[str, str]:
        """构造上游请求的认证 Header"""


class BearerAuthHandler(AuthHandler):
    """Authorization: Bearer <token>"""

    def extract_credentials(self, request: Request) -> str | None:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return None

    def build_headers(self, credentials: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {credentials}"}


class ApiKeyAuthHandler(AuthHandler):
    """x-api-key: <key>"""

    def extract_credentials(self, request: Request) -> str | None:
        return request.headers.get("x-api-key")

    def build_headers(self, credentials: str) -> dict[str, str]:
        return {"x-api-key": credentials}


class GoogApiKeyAuthHandler(AuthHandler):
    """x-goog-api-key: <key> (支持 ?key=)"""

    def extract_credentials(self, request: Request) -> str | None:
        return request.query_params.get("key") or request.headers.get("x-goog-api-key")

    def build_headers(self, credentials: str) -> dict[str, str]:
        return {"x-goog-api-key": credentials}


class QueryKeyAuthHandler(AuthHandler):
    """?key= 参数认证（仅提取，通常用于 Gemini）"""

    def extract_credentials(self, request: Request) -> str | None:
        return request.query_params.get("key")

    def build_headers(self, credentials: str) -> dict[str, str]:
        return {"x-goog-api-key": credentials}


class OAuth2AuthHandler(AuthHandler):
    """
    Google OAuth2 / Service Account 认证

    目前使用 Authorization: Bearer 透传 access token。
    """

    def extract_credentials(self, request: Request) -> str | None:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return None

    def build_headers(self, credentials: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {credentials}"}


_AUTH_HANDLERS: dict[AuthMethod, AuthHandler] = {
    AuthMethod.BEARER: BearerAuthHandler(),
    AuthMethod.API_KEY: ApiKeyAuthHandler(),
    AuthMethod.GOOG_API_KEY: GoogApiKeyAuthHandler(),
    AuthMethod.OAUTH2: OAuth2AuthHandler(),
    AuthMethod.QUERY_KEY: QueryKeyAuthHandler(),
}


def get_auth_handler(auth_method: AuthMethod) -> AuthHandler:
    """获取认证处理器实例"""
    handler = _AUTH_HANDLERS.get(auth_method)
    if not handler:
        raise ValueError(f"Unsupported auth method: {auth_method}")
    return handler


def get_default_auth_method_for_endpoint(
    value: str | EndpointSignature | tuple,  # tuple[ApiFamily, EndpointKind]
) -> AuthMethod:
    """
    新模式：从 endpoint signature 推断默认 AuthMethod。

    只接受 `family:kind` / EndpointSignature / (ApiFamily, EndpointKind)。
    """
    definition = resolve_endpoint_definition(value)
    return definition.auth_method if definition else AuthMethod.BEARER


__all__ = [
    "AuthHandler",
    "BearerAuthHandler",
    "ApiKeyAuthHandler",
    "GoogApiKeyAuthHandler",
    "OAuth2AuthHandler",
    "QueryKeyAuthHandler",
    "get_auth_handler",
    "get_default_auth_method_for_endpoint",
]

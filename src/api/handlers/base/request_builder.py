"""
请求构建器 - 透传模式

透传模式 (Passthrough): CLI 和 Chat 等场景，原样转发请求体和头部
- 清理敏感头部：authorization, x-api-key, host, content-length 等
- 保留所有其他头部和请求体字段
- 适用于：Claude CLI、OpenAI CLI、Chat API 等场景

使用方式：
    builder = PassthroughRequestBuilder()
    payload, headers = builder.build(original_body, original_headers, endpoint, key)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, FrozenSet, Optional, Tuple

from src.core.crypto import crypto_service
from src.core.api_format import HeaderBuilder, UPSTREAM_DROP_HEADERS

# ==============================================================================
# 统一的头部配置常量
# ==============================================================================

# 兼容别名：历史代码使用 SENSITIVE_HEADERS 命名
SENSITIVE_HEADERS: FrozenSet[str] = UPSTREAM_DROP_HEADERS


# ==============================================================================
# 测试请求常量与辅助函数
# ==============================================================================

# 标准测试请求体（OpenAI 格式）
# 用于 check_endpoint 等测试场景，使用简单安全的消息内容避免触发安全过滤
DEFAULT_TEST_REQUEST: Dict[str, Any] = {
    "messages": [{"role": "user", "content": "Hi"}],
    "max_tokens": 5,
    "temperature": 0,
}


def get_test_request_data(request_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """获取测试请求数据

    如果传入 request_data，则合并到默认测试请求中；
    否则使用默认测试请求。

    Args:
        request_data: 用户提供的请求数据（会覆盖默认值）

    Returns:
        合并后的测试请求数据（OpenAI 格式）
    """
    if request_data:
        merged = DEFAULT_TEST_REQUEST.copy()
        merged.update(request_data)
        return merged
    return DEFAULT_TEST_REQUEST.copy()


def build_test_request_body(
    format_id: str,
    request_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """构建测试请求体，自动处理格式转换

    使用 converter_registry 将 OpenAI 格式的测试请求转换为目标格式。

    Args:
        format_id: 目标 API 格式 ID（如 "CLAUDE", "GEMINI", "OPENAI_CLI"）
        request_data: 可选的请求数据，会与默认测试请求合并

    Returns:
        转换为目标 API 格式的请求体
    """
    from src.core.api_format.conversion import converter_registry
    from src.core.api_format.utils import get_base_format

    # 获取测试请求数据（OpenAI 格式）
    source_data = get_test_request_data(request_data)

    # CLI 格式使用基础格式进行转换（CLAUDE_CLI -> CLAUDE）
    # 因为 converter_registry 只注册了基础格式之间的转换器
    target_format = get_base_format(format_id) or format_id

    # 使用注册表进行格式转换 (OPENAI -> 目标基础格式)
    return converter_registry.convert_request(source_data, "OPENAI", target_format)


# ==============================================================================
# 请求构建器
# ==============================================================================


class RequestBuilder(ABC):
    """请求构建器抽象基类"""

    @abstractmethod
    def build_payload(
        self,
        original_body: Dict[str, Any],
        *,
        mapped_model: Optional[str] = None,
        is_stream: bool = False,
    ) -> Dict[str, Any]:
        """构建请求体"""
        pass

    @abstractmethod
    def build_headers(
        self,
        original_headers: Dict[str, str],
        endpoint: Any,
        key: Any,
        *,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """构建请求头"""
        pass

    def build(
        self,
        original_body: Dict[str, Any],
        original_headers: Dict[str, str],
        endpoint: Any,
        key: Any,
        *,
        mapped_model: Optional[str] = None,
        is_stream: bool = False,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """
        构建完整的请求（请求体 + 请求头）

        Args:
            original_body: 原始请求体
            original_headers: 原始请求头
            endpoint: 端点配置
            key: Provider API Key
            mapped_model: 映射后的模型名
            is_stream: 是否为流式请求
            extra_headers: 额外请求头

        Returns:
            Tuple[payload, headers]
        """
        payload = self.build_payload(
            original_body,
            mapped_model=mapped_model,
            is_stream=is_stream,
        )
        headers = self.build_headers(
            original_headers,
            endpoint,
            key,
            extra_headers=extra_headers,
        )
        return payload, headers


class PassthroughRequestBuilder(RequestBuilder):
    """
    透传模式请求构建器

    适用于 CLI 等场景，尽量保持请求原样：
    - 请求体：直接复制，只修改必要字段（model, stream）
    - 请求头：清理敏感头部（黑名单），透传其他所有头部
    """

    def build_payload(
        self,
        original_body: Dict[str, Any],
        *,
        mapped_model: Optional[str] = None,  # noqa: ARG002 - 由 apply_mapped_model 处理
        is_stream: bool = False,  # noqa: ARG002 - 保留原始值，不自动添加
    ) -> Dict[str, Any]:
        """
        透传请求体 - 原样复制，不做任何修改

        透传模式下：
        - model: 由各 handler 的 apply_mapped_model 方法处理
        - stream: 保留客户端原始值（不同 API 处理方式不同）
        """
        return dict(original_body)

    def build_headers(
        self,
        original_headers: Dict[str, str],
        endpoint: Any,
        key: Any,
        *,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        透传请求头 - 清理敏感头部（黑名单），透传其他所有头部

        Args:
            original_headers: 原始请求头
            endpoint: 端点配置
            key: Provider API Key
            extra_headers: 额外请求头
        """
        from src.core.api_format import get_auth_config, resolve_api_format

        # 1. 根据 API 格式自动设置认证头
        decrypted_key = crypto_service.decrypt(key.api_key)
        api_format = getattr(endpoint, "api_format", None)
        resolved_format = resolve_api_format(api_format)
        auth_header, auth_type = (
            get_auth_config(resolved_format) if resolved_format else ("Authorization", "bearer")
        )

        auth_value = f"Bearer {decrypted_key}" if auth_type == "bearer" else decrypted_key
        # 认证头始终受保护，防止 header_rules 覆盖
        protected_keys = {auth_header.lower(), "content-type"}

        builder = HeaderBuilder()

        # 2. 透传原始头部（排除默认敏感头部）
        if original_headers:
            for name, value in original_headers.items():
                if name.lower() in SENSITIVE_HEADERS:
                    continue
                builder.add(name, value)

        # 3. 应用 endpoint 的请求头规则（认证头受保护，无法通过 rules 设置）
        header_rules = getattr(endpoint, "header_rules", None)
        if header_rules:
            builder.apply_rules(header_rules, protected_keys)

        # 4. 添加额外头部
        if extra_headers:
            builder.add_many(extra_headers)

        # 5. 设置认证头（最高优先级，上游始终使用 header 认证）
        builder.add(auth_header, auth_value)

        # 6. 确保有 Content-Type
        headers = builder.build()
        if not any(k.lower() == "content-type" for k in headers):
            headers["Content-Type"] = "application/json"

        return headers


# ==============================================================================
# 便捷函数
# ==============================================================================


def build_passthrough_request(
    original_body: Dict[str, Any],
    original_headers: Dict[str, str],
    endpoint: Any,
    key: Any,
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    构建透传模式的请求

    纯透传：原样复制请求体，只处理请求头（认证等）。
    model mapping 和 stream 由调用方自行处理（不同 API 格式处理方式不同）。
    """
    builder = PassthroughRequestBuilder()
    return builder.build(
        original_body,
        original_headers,
        endpoint,
        key,
    )

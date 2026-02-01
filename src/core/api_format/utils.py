"""
API 格式工具函数

提供格式判断、规范化等工具函数，供整个项目使用。
"""

from __future__ import annotations


def is_cli_format(format_id: str | None) -> bool:
    """
    判断是否为 CLI 透传格式

    新模式下使用 endpoint signature：`family:kind`，CLI 的 kind 为 `cli`。

    Args:
        format_id: endpoint signature key（如 "openai:cli"）

    Returns:
        True 如果是 CLI 格式

    Examples:
        >>> is_cli_format("claude:cli")
        True
        >>> is_cli_format("claude:chat")
        False
    """
    if format_id is None:
        return False
    text = str(format_id).strip()
    return text.lower().endswith(":cli")


def get_base_format(format_id: str | None) -> str | None:
    """
    获取基础格式（CLI -> CHAT）

    Args:
        format_id: 格式标识符

    Returns:
        基础格式字符串，或 None

    Examples:
        >>> get_base_format("claude:cli")
        "claude:chat"
        >>> get_base_format("openai:chat")
        "openai:chat"
    """
    if format_id is None:
        return None
    text = str(format_id).strip()
    if not text:
        return None

    from src.core.api_format.enums import EndpointKind
    from src.core.api_format.signature import make_signature_key, parse_signature_key

    try:
        sig = parse_signature_key(text)
    except Exception:
        return None
    if sig.endpoint_kind == EndpointKind.CLI:
        return make_signature_key(sig.api_family, EndpointKind.CHAT)
    return make_signature_key(sig.api_family, sig.endpoint_kind)


def normalize_format(format_id: str | None) -> str | None:
    """
    规范化 endpoint signature key（canonical: 全小写 `family:kind`）。

    Args:
        format_id: endpoint signature key

    Returns:
        canonical signature key，或 None
    """
    if format_id is None:
        return None
    text = str(format_id).strip()
    if not text:
        return None
    from src.core.api_format.signature import normalize_signature_key

    try:
        return normalize_signature_key(text)
    except Exception:
        return None


def is_same_format(
    format1: str | None,
    format2: str | None,
) -> bool:
    """
    判断两个格式是否相同

    忽略大小写和枚举/字符串差异。
    """
    return normalize_format(format1) == normalize_format(format2)


def is_convertible_format(format_id: str | None) -> bool:
    """
    判断是否为可转换格式

    .. deprecated::
        此函数语义已退化（对非 None 输入总返回 True）。
        真正的可转换性应通过 format_conversion_registry.can_convert_*() 查询。
    """
    if format_id is None:
        return False
    return True

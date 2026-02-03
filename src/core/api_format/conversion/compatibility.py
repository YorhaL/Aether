"""
格式兼容性检查

用于候选筛选时判断端点是否可以处理客户端请求格式。

三层开关优先级（从高到低）：
1. 全局开关 ON → 强制允许（跳过后续检查）
2. 全局开关 OFF → 看提供商开关
   - 提供商开关 ON → 强制允许（跳过端点检查）
   - 提供商开关 OFF → 看端点配置
3. 端点配置（format_acceptance_config）
   - enabled=true + 白名单/黑名单检查 → 允许
   - enabled=false 或未配置 → 禁止

转换逻辑：
1. 格式完全匹配 -> 透传（无需转换）
2. 格式不同 -> 需要检查三层开关
   - data_format_id 相同 -> 可透传（无需数据转换）
   - data_format_id 不同 -> 需要转换，检查转换器能力
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.api_format.conversion.registry import FormatConversionRegistry

from src.core.api_format.metadata import can_passthrough_endpoint

logger = logging.getLogger(__name__)


def is_format_compatible(
    client_format: str,
    endpoint_api_format: str,
    endpoint_format_acceptance_config: dict | None,
    is_stream: bool,
    effective_conversion_enabled: bool,
    registry: FormatConversionRegistry | None = None,
    *,
    skip_endpoint_check: bool = False,
) -> tuple[bool, bool, str | None]:
    """
    检查端点是否兼容客户端格式

    Args:
        client_format: 客户端请求格式
        endpoint_api_format: 端点的 API 格式
        endpoint_format_acceptance_config: 端点的格式接受配置
        is_stream: 是否是流式请求
        effective_conversion_enabled: 格式转换总开关（通常来自环境变量/Feature Flag）
        registry: 转换器注册表（可选，默认使用全局单例）
        skip_endpoint_check: 是否跳过端点配置检查（当全局或提供商开关为 ON 时设为 True）

    Returns:
        (is_compatible, needs_conversion, skip_reason)
        - is_compatible: 是否兼容
        - needs_conversion: 是否需要转换
        - skip_reason: 不兼容时的原因
    """
    # 延迟导入避免循环依赖
    if registry is None:
        from src.core.api_format.conversion.registry import (
            format_conversion_registry,
            register_default_normalizers,
        )

        register_default_normalizers()
        registry = format_conversion_registry

    # 统一大写用于比较和 registry 查找（registry 以大写 key 索引 normalizer）
    client_key = client_format.upper()
    provider_key = endpoint_api_format.upper()

    # 1. 格式完全匹配 -> 透传（无需转换）
    if provider_key == client_key:
        return True, False, None

    # 2. 格式不同 -> 需要检查格式转换开关
    # 如果总开关为 False，直接拒绝（禁用任何跨格式转换）
    if not effective_conversion_enabled:
        return False, False, "格式转换已禁用（enable_format_conversion=false）"

    # 3. 如果全局或提供商开关为 ON，跳过端点配置检查
    if not skip_endpoint_check:
        # 检查端点配置（第三层开关）
        if endpoint_format_acceptance_config is None:
            return False, False, "端点未配置格式接受策略"

        config = endpoint_format_acceptance_config
        if not isinstance(config, dict):
            return False, False, "端点格式配置无效"
        if not config.get("enabled", False):
            return False, False, "端点格式接受未启用"

        # 检查 reject_formats（优先）
        reject_formats = config.get("reject_formats", [])
        if client_key in [f.upper() for f in reject_formats]:
            return False, False, f"端点拒绝 {client_format} 格式"

        # 检查 accept_formats
        accept_formats = config.get("accept_formats", [])
        if accept_formats and client_key not in [f.upper() for f in accept_formats]:
            return False, False, f"端点不接受 {client_format} 格式"

        # 检查流式转换
        if is_stream and not config.get("stream_conversion", True):
            return False, False, "端点不支持流式格式转换"

    # 4. 检查是否可以透传（data_format_id 相同）
    # 例如：claude:chat / claude:cli 的 data_format_id 都是 "claude"，数据格式相同可透传
    #      openai:chat 是 "openai_chat"，openai:cli 是 "openai_responses"，需要转换
    if can_passthrough_endpoint(client_key, provider_key):
        # data_format_id 相同，可透传（无需数据转换）
        return True, False, None

    # 5. 需要数据转换的情况（data_format_id 不同）
    # 检查转换器能力
    if not registry.can_convert_full(
        client_key,
        provider_key,
        require_stream=is_stream,
    ):
        return False, False, f"不存在 {client_format} <-> {endpoint_api_format} 的完整转换器"

    return True, True, None


__all__ = [
    "is_format_compatible",
]

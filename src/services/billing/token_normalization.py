"""
计费相关 token 归一化工具。
"""

from __future__ import annotations

from src.core.api_format.enums import ApiFamily
from src.core.api_format.signature import parse_signature_key


def _get_api_family(api_format: str | None) -> ApiFamily | None:
    """解析 api_format 字符串，返回对应的 ApiFamily 枚举。"""
    if not api_format:
        return None
    text = str(api_format).strip()
    if not text:
        return None
    sig = parse_signature_key(text)
    return sig.api_family


def normalize_input_tokens_for_billing(
    api_format: str | None,
    input_tokens: int,
    cache_read_tokens: int,
) -> int:
    """
    归一化 `input_tokens`，使其在计费中表示"非缓存输入 token"。

    计费口径：`input_tokens`=非缓存输入 token；`cache_read_tokens`=缓存命中 token（折扣/免费维度）。

    - Claude 系：保持上游口径（不扣除），因为 Claude API 的 input_tokens 本身就不包含缓存部分。
    - OpenAI 系：`input_tokens` 包含缓存命中部分，需要扣除 `cache_read_tokens`。
    - Gemini 系：`promptTokenCount` 包含 `cachedContentTokenCount`，需要扣除。
    """
    if input_tokens <= 0:
        return 0 if input_tokens == 0 else input_tokens
    if cache_read_tokens <= 0:
        return input_tokens

    api_family = _get_api_family(api_format)
    if api_family == ApiFamily.CLAUDE:
        return input_tokens
    if api_family in (ApiFamily.OPENAI, ApiFamily.GEMINI):
        return max(input_tokens - cache_read_tokens, 0)
    # 未知格式，保守处理，不扣除
    return input_tokens

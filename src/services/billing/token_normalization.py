"""
计费相关 token 归一化工具。
"""

from __future__ import annotations

from src.core.api_format.enums import ApiFamily
from src.core.api_format.signature import parse_signature_key


def _is_claude_family(api_format: str | None) -> bool:
    if api_format is None:
        return False
    text = str(api_format).strip()
    if not text:
        return False
    sig = parse_signature_key(text)
    return sig.api_family == ApiFamily.CLAUDE


def _is_openai_family(api_format: str | None) -> bool:
    if api_format is None:
        return False
    text = str(api_format).strip()
    if not text:
        return False
    sig = parse_signature_key(text)
    return sig.api_family == ApiFamily.OPENAI


def normalize_input_tokens_for_billing(
    api_format: str | None,
    input_tokens: int,
    cache_read_tokens: int,
) -> int:
    """
    归一化 `input_tokens`，使其在计费中表示“非缓存输入 token”。

    计费口径：`input_tokens`=非缓存输入 token；`cache_read_tokens`=缓存命中 token（折扣/免费维度）。

    - Claude 系：保持上游口径（不扣除）。
    - OpenAI 系：`input_tokens` 通常包含缓存命中部分，需要扣除 `cache_read_tokens`。
    """
    if input_tokens <= 0:
        return 0 if input_tokens == 0 else input_tokens
    if cache_read_tokens <= 0:
        return input_tokens
    if _is_claude_family(api_format):
        return input_tokens
    if _is_openai_family(api_format):
        return max(input_tokens - cache_read_tokens, 0)
    return input_tokens

"""
Claude CLI Normalizer

CLAUDE_CLI 的请求/响应 body 与 CLAUDE 一致（Anthropic Messages API），差异主要在认证头。
因此这里复用 ClaudeNormalizer 的转换逻辑，仅更换 FORMAT_ID。

如需 CLI 特殊处理，可覆盖 request_from_internal / request_to_internal 等方法。
"""

from src.core.api_format.conversion.normalizers.claude import ClaudeNormalizer


class ClaudeCliNormalizer(ClaudeNormalizer):
    FORMAT_ID = "claude:cli"


__all__ = ["ClaudeCliNormalizer"]

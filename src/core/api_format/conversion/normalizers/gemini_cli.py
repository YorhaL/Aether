"""
Gemini CLI Normalizer

GEMINI_CLI 的请求/响应 body 与 GEMINI 一致（Google Gemini API），差异主要在鉴权/UA 等请求层。
因此这里复用 GeminiNormalizer 的转换逻辑，仅更换 FORMAT_ID。

如需 CLI 特殊处理，可覆盖 request_from_internal / request_to_internal 等方法。
"""

from src.core.api_format.conversion.normalizers.gemini import GeminiNormalizer


class GeminiCliNormalizer(GeminiNormalizer):
    FORMAT_ID = "gemini:cli"


__all__ = ["GeminiCliNormalizer"]

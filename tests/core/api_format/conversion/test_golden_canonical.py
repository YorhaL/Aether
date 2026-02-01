"""
Golden tests（Canonical）

说明：
- 这些 Golden 用于冻结 Canonical registry 的外部输出形态（request/response/stream）。
- 文件由 `tools/generate_format_conversion_golden.py` 生成。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.core.api_format.conversion.normalizers.claude import ClaudeNormalizer
from src.core.api_format.conversion.normalizers.gemini import GeminiNormalizer
from src.core.api_format.conversion.normalizers.openai import OpenAINormalizer
from src.core.api_format.conversion.registry import FormatConversionRegistry
from src.core.api_format.conversion.stream_state import StreamState

GOLDEN_DIR = Path(__file__).resolve().parent / "golden_data"
INPUT_DIR = GOLDEN_DIR / "inputs"
EXPECTED_DIR = GOLDEN_DIR / "expected"


def _scrub(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_scrub(x) for x in obj]
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k in {"created"}:
                continue
            if k == "system_fingerprint" and v is None:
                continue
            out[k] = _scrub(v)
        return out
    return obj


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _make_registry() -> FormatConversionRegistry:
    reg = FormatConversionRegistry()
    reg.register(OpenAINormalizer())
    reg.register(ClaudeNormalizer())
    reg.register(GeminiNormalizer())
    return reg


def test_golden_requests() -> None:
    reg = _make_registry()
    formats = ["openai:chat", "claude:chat", "gemini:chat"]

    inputs = {
        "openai:chat": _load_json(INPUT_DIR / "request_openai.json"),
        "claude:chat": _load_json(INPUT_DIR / "request_claude.json"),
        "gemini:chat": _load_json(INPUT_DIR / "request_gemini.json"),
    }

    for source in formats:
        for target in formats:
            if source == target:
                continue
            expected = _load_json(EXPECTED_DIR / f"request_{source}_to_{target}.json")
            actual = reg.convert_request(inputs[source], source, target)
            assert _scrub(actual) == expected


def test_golden_responses() -> None:
    reg = _make_registry()
    formats = ["openai:chat", "claude:chat", "gemini:chat"]

    inputs = {
        "openai:chat": _load_json(INPUT_DIR / "response_openai.json"),
        "claude:chat": _load_json(INPUT_DIR / "response_claude.json"),
        "gemini:chat": _load_json(INPUT_DIR / "response_gemini.json"),
    }

    for source in formats:
        for target in formats:
            if source == target:
                continue
            expected = _load_json(EXPECTED_DIR / f"response_{source}_to_{target}.json")
            actual = reg.convert_response(inputs[source], source, target)
            assert _scrub(actual) == expected


def test_golden_streams() -> None:
    reg = _make_registry()
    formats = ["openai:chat", "claude:chat", "gemini:chat"]

    inputs: dict[str, list[dict[str, Any]]] = {
        "openai:chat": _load_json(INPUT_DIR / "stream_openai.json"),
        "claude:chat": _load_json(INPUT_DIR / "stream_claude.json"),
        "gemini:chat": _load_json(INPUT_DIR / "stream_gemini.json"),
    }

    for source in formats:
        for target in formats:
            if source == target:
                continue
            expected = _load_json(EXPECTED_DIR / f"stream_{source}_to_{target}.json")

            state = StreamState()
            if source == "gemini:chat":
                state.message_id = "gemini_1"

            out: list[dict[str, Any]] = []
            for chunk in inputs[source]:
                out.extend(reg.convert_stream_chunk(chunk, source, target, state=state))

            assert _scrub(out) == expected

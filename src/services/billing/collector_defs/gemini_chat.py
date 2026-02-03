from __future__ import annotations

from typing import Any

# Gemini generateContent
COLLECTORS: list[dict[str, Any]] = [
    {
        "api_format": "gemini:chat",
        "task_type": "chat",
        "dimension_name": "input_tokens",
        "source_type": "response",
        "source_path": "usageMetadata.promptTokenCount",
        "value_type": "int",
        "priority": 10,
        "is_enabled": True,
    },
    {
        "api_format": "gemini:chat",
        "task_type": "chat",
        "dimension_name": "output_tokens",
        "source_type": "response",
        "source_path": "usageMetadata.candidatesTokenCount",
        "value_type": "int",
        "priority": 10,
        "is_enabled": True,
    },
]

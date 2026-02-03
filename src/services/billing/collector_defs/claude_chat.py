from __future__ import annotations

from typing import Any

# Anthropic / Claude messages
COLLECTORS: list[dict[str, Any]] = [
    {
        "api_format": "claude:chat",
        "task_type": "chat",
        "dimension_name": "input_tokens",
        "source_type": "response",
        "source_path": "usage.input_tokens",
        "value_type": "int",
        "priority": 10,
        "is_enabled": True,
    },
    {
        "api_format": "claude:chat",
        "task_type": "chat",
        "dimension_name": "output_tokens",
        "source_type": "response",
        "source_path": "usage.output_tokens",
        "value_type": "int",
        "priority": 10,
        "is_enabled": True,
    },
]

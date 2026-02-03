from __future__ import annotations

from typing import Any

# OpenAI chat completions
COLLECTORS: list[dict[str, Any]] = [
    {
        "api_format": "openai:chat",
        "task_type": "chat",
        "dimension_name": "input_tokens",
        "source_type": "response",
        "source_path": "usage.prompt_tokens",
        "value_type": "int",
        "priority": 10,
        "is_enabled": True,
    },
    {
        "api_format": "openai:chat",
        "task_type": "chat",
        "dimension_name": "output_tokens",
        "source_type": "response",
        "source_path": "usage.completion_tokens",
        "value_type": "int",
        "priority": 10,
        "is_enabled": True,
    },
]

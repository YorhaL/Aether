"""
Collector definitions (config-file mode).

Goal:
- Developers define dimension collectors in code, grouped by api_format.
- Adding support for a new api_format should only require adding a new file here.
- No DB seeding required.

Each module should export:
- COLLECTORS: list[dict[str, Any]]

Each dict supports keys (aligned with DimensionCollector):
- api_format: "openai:chat" (canonical family:kind)
- task_type: "chat" | "cli" | "video" | "image" | "audio"
- dimension_name: string
- source_type: "request" | "response" | "metadata" | "computed"
- source_path: string | None
- value_type: "float" | "int" | "string"
- transform_expression: string | None
- default_value: string | None
- priority: int
- is_enabled: bool
"""

from __future__ import annotations

from typing import Any

# This package is discovered dynamically by `src.services.billing.presets`.

COLLECTORS: list[dict[str, Any]] = []

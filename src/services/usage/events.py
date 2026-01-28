"""
Usage 事件定义与序列化工具（用于 Redis Streams）
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

USAGE_EVENT_VERSION = 1


class UsageEventType(str, Enum):
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def now_ms() -> int:
    return int(time.time() * 1000)


def _sanitize_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return str(value)


def sanitize_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    return {str(k): _sanitize_value(v) for k, v in data.items()}


@dataclass
class UsageEvent:
    event_type: UsageEventType
    request_id: str
    timestamp_ms: int
    data: Dict[str, Any]

    def to_stream_fields(self) -> Dict[str, str]:
        payload = {
            "v": USAGE_EVENT_VERSION,
            "type": self.event_type.value,
            "request_id": self.request_id,
            "timestamp_ms": self.timestamp_ms,
            "data": sanitize_payload(self.data),
        }
        return {"payload": json.dumps(payload, ensure_ascii=False)}

    @classmethod
    def from_stream_fields(cls, fields: Dict[str, Any]) -> "UsageEvent":
        raw = fields.get("payload")
        if not raw:
            raise ValueError("Missing payload field in usage event")
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        payload = json.loads(raw)
        event_type = UsageEventType(payload["type"])
        return cls(
            event_type=event_type,
            request_id=payload["request_id"],
            timestamp_ms=int(payload.get("timestamp_ms", 0)),
            data=payload.get("data", {}) or {},
        )


def build_usage_event(
    *,
    event_type: UsageEventType,
    request_id: str,
    data: Dict[str, Any],
    timestamp_ms: Optional[int] = None,
) -> UsageEvent:
    return UsageEvent(
        event_type=event_type,
        request_id=request_id,
        timestamp_ms=timestamp_ms or now_ms(),
        data=data,
    )

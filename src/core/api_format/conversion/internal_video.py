"""
视频格式转换内部表示（Internal Video Format）

用于 Video API 的 Hub-and-Spoke 统一中间表示。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class VideoStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class InternalVideoRequest:
    """统一的视频生成请求格式"""

    prompt: str
    model: str = "sora-2"
    duration_seconds: int = 4
    aspect_ratio: str = "16:9"
    resolution: str = "720p"
    reference_image_url: str | None = None  # base64 或 URL
    character_ids: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
    preferred_provider: str | None = None
    preferred_format: str | None = None


@dataclass
class InternalVideoTask:
    """统一的视频任务状态"""

    id: str
    external_id: str | None = None
    status: VideoStatus = VideoStatus.PENDING
    progress_percent: int = 0
    progress_message: str | None = None
    video_url: str | None = None
    video_urls: list[str] = field(default_factory=list)
    thumbnail_url: str | None = None
    video_duration_seconds: int | None = None
    video_size_bytes: int | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    original_request: InternalVideoRequest | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class InternalVideoPollResult:
    """轮询结果"""

    status: VideoStatus
    progress_percent: int = 0
    video_url: str | None = None
    video_urls: list[str] = field(default_factory=list)
    expires_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    raw_response: dict[str, Any] | None = None
    video_duration_seconds: float | None = None  # 实际视频时长


__all__ = [
    "VideoStatus",
    "InternalVideoRequest",
    "InternalVideoTask",
    "InternalVideoPollResult",
]

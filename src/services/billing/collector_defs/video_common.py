from __future__ import annotations

from typing import Any

# Async video finalize flow: extra dims from metadata (base_dimensions already provided by caller).
#
# Note:
# - DimensionCollectorService has a "video -> base api_format fallback" that may query
#   base api_format collectors when api_format is "openai:video"/"gemini:video" etc.
COLLECTORS: list[dict[str, Any]] = [
    # Prefer size as "resolution key" (e.g. 1024x1792), fallback to resolution label (e.g. 720p/4k).
    {
        "api_format": "openai:chat",
        "task_type": "video",
        "dimension_name": "video_resolution_key",
        "source_type": "metadata",
        "source_path": "task.size",
        "value_type": "string",
        "priority": 10,
        "is_enabled": True,
    },
    {
        "api_format": "openai:chat",
        "task_type": "video",
        "dimension_name": "video_resolution_key",
        "source_type": "metadata",
        "source_path": "task.resolution",
        "value_type": "string",
        "priority": 0,
        "is_enabled": True,
    },
    {
        "api_format": "openai:chat",
        "task_type": "video",
        "dimension_name": "video_size_bytes",
        "source_type": "metadata",
        "source_path": "task.video_size_bytes",
        "value_type": "int",
        "priority": 0,
        "is_enabled": True,
    },
    # 实际视频时长（秒），优先使用从 provider 响应中提取的实际时长
    {
        "api_format": "openai:chat",
        "task_type": "video",
        "dimension_name": "video_duration_seconds",
        "source_type": "metadata",
        "source_path": "task.video_duration_seconds",
        "value_type": "float",
        "priority": 10,
        "is_enabled": True,
    },
    # 回退到请求的 duration_seconds（如果没有实际时长）
    {
        "api_format": "openai:chat",
        "task_type": "video",
        "dimension_name": "video_duration_seconds",
        "source_type": "metadata",
        "source_path": "task.duration_seconds",
        "value_type": "int",
        "priority": 0,
        "is_enabled": True,
    },
    {
        "api_format": "gemini:chat",
        "task_type": "video",
        "dimension_name": "video_resolution_key",
        "source_type": "metadata",
        "source_path": "task.size",
        "value_type": "string",
        "priority": 10,
        "is_enabled": True,
    },
    {
        "api_format": "gemini:chat",
        "task_type": "video",
        "dimension_name": "video_resolution_key",
        "source_type": "metadata",
        "source_path": "task.resolution",
        "value_type": "string",
        "priority": 0,
        "is_enabled": True,
    },
    {
        "api_format": "gemini:chat",
        "task_type": "video",
        "dimension_name": "video_size_bytes",
        "source_type": "metadata",
        "source_path": "task.video_size_bytes",
        "value_type": "int",
        "priority": 0,
        "is_enabled": True,
    },
    # 实际视频时长（秒），优先使用从 provider 响应中提取的实际时长
    {
        "api_format": "gemini:chat",
        "task_type": "video",
        "dimension_name": "video_duration_seconds",
        "source_type": "metadata",
        "source_path": "task.video_duration_seconds",
        "value_type": "float",
        "priority": 10,
        "is_enabled": True,
    },
    # 回退到请求的 duration_seconds（如果没有实际时长）
    {
        "api_format": "gemini:chat",
        "task_type": "video",
        "dimension_name": "video_duration_seconds",
        "source_type": "metadata",
        "source_path": "task.duration_seconds",
        "value_type": "int",
        "priority": 0,
        "is_enabled": True,
    },
]

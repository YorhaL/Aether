"""
格式标准化器接口（FormatNormalizer）

每个格式（OpenAI/Claude/Gemini）实现一个 Normalizer，将 provider 结构转换到 internal，
再从 internal 输出到目标格式。
"""

from abc import ABC, abstractmethod
from typing import Any

from .internal import FormatCapabilities, InternalError, InternalRequest, InternalResponse
from .internal_video import InternalVideoPollResult, InternalVideoRequest, InternalVideoTask
from .stream_events import InternalStreamEvent
from .stream_state import StreamState


class FormatNormalizer(ABC):
    """格式标准化器基类"""

    FORMAT_ID: str  # 如 "CLAUDE", "OPENAI", "GEMINI"
    capabilities: FormatCapabilities

    # ============ 请求转换 ============

    @abstractmethod
    def request_to_internal(self, request: dict[str, Any]) -> InternalRequest:
        """将格式特定请求转换为内部表示"""
        raise NotImplementedError

    @abstractmethod
    def request_from_internal(self, internal: InternalRequest) -> dict[str, Any]:
        """将内部表示转换为格式特定请求"""
        raise NotImplementedError

    # ============ 响应转换 ============

    @abstractmethod
    def response_to_internal(self, response: dict[str, Any]) -> InternalResponse:
        """将格式特定响应转换为内部表示"""
        raise NotImplementedError

    @abstractmethod
    def response_from_internal(
        self,
        internal: InternalResponse,
        *,
        requested_model: str | None = None,
    ) -> dict[str, Any]:
        """将内部表示转换为格式特定响应

        Args:
            internal: 内部响应表示
            requested_model: 用户请求的原始模型名（可选）。
                            如果提供，响应中的 model 字段将使用此值，
                            而不是上游返回的映射后模型名。
        """
        raise NotImplementedError

    # ============ 流式转换（可选） ============

    def stream_chunk_to_internal(
        self,
        chunk: dict[str, Any],
        state: StreamState,
    ) -> list[InternalStreamEvent]:
        """将格式特定流式块转换为内部事件"""
        raise NotImplementedError

    def stream_event_from_internal(
        self,
        event: InternalStreamEvent,
        state: StreamState,
    ) -> list[dict[str, Any]]:
        """将内部事件转换为格式特定流式块"""
        raise NotImplementedError

    # ============ 错误转换（可选） ============

    def is_error_response(self, response: dict[str, Any]) -> bool:
        """基于 body 的兜底判断（不可靠），子类可覆盖"""
        return False

    def error_to_internal(self, error_response: dict[str, Any]) -> InternalError:
        """将格式特定错误转换为内部表示"""
        raise NotImplementedError

    def error_from_internal(self, internal: InternalError) -> dict[str, Any]:
        """将内部错误表示转换为格式特定错误"""
        raise NotImplementedError

    # ============ 视频转换（可选） ============

    def video_request_to_internal(self, request: dict[str, Any]) -> InternalVideoRequest:
        """将视频请求转换为内部表示"""
        raise NotImplementedError(f"{self.__class__.__name__} does not support video conversion")

    def video_request_from_internal(self, internal: InternalVideoRequest) -> dict[str, Any]:
        """将内部视频请求转换为格式特定请求"""
        raise NotImplementedError(f"{self.__class__.__name__} does not support video conversion")

    def video_task_to_internal(self, response: dict[str, Any]) -> InternalVideoTask:
        """将视频任务响应转换为内部表示"""
        raise NotImplementedError(f"{self.__class__.__name__} does not support video conversion")

    def video_task_from_internal(
        self, internal: InternalVideoTask, *, base_url: str | None = None
    ) -> dict[str, Any]:
        """将内部视频任务转换为格式特定响应

        Args:
            internal: 内部视频任务表示
            base_url: 可选的基础 URL，用于构建完整的下载链接
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support video conversion")

    def video_poll_to_internal(self, response: dict[str, Any]) -> InternalVideoPollResult:
        """将视频轮询响应转换为内部表示"""
        raise NotImplementedError(f"{self.__class__.__name__} does not support video conversion")


__all__ = [
    "FormatNormalizer",
]

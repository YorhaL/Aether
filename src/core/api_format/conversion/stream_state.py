"""
统一流式状态容器（StreamState）

目标：在多个 chunk 之间维护转换上下文，但避免把“某个格式特定的状态字段”固化在核心层。
每个 Normalizer 通过 `substate(format_id)` 获取自己的隔离状态字典。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StreamState:
    """
    统一的流式状态容器

    关键点：
    - 不把具体格式字段固化为属性，避免 source/target 互相污染
    - 每个 Normalizer 只读写自己的隔离子状态：`state.substate(self.FORMAT_ID)`
    """

    # 可选：便于调试与链路追踪（不强依赖）
    model: str = ""
    message_id: str = ""

    # Registry/调用层的通用扩展信息（与具体格式无关）
    extra: dict[str, Any] = field(default_factory=dict)

    # 各 Normalizer 的隔离状态（key: FORMAT_ID）
    by_format: dict[str, dict[str, Any]] = field(default_factory=dict)

    def substate(self, format_id: str) -> dict[str, Any]:
        """获取指定格式的隔离子状态"""
        key = str(format_id).upper()
        return self.by_format.setdefault(key, {})

    def reset(self) -> None:
        """重置状态（重试时调用）"""
        self.model = ""
        self.message_id = ""
        self.extra.clear()
        self.by_format.clear()


__all__ = [
    "StreamState",
]

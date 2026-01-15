"""
请求候选记录服务 - 管理候选队列
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from src.core.batch_committer import get_batch_committer
from src.core.logger import logger
from src.models.database import RequestCandidate


class RequestCandidateService:
    """请求候选记录服务"""

    @staticmethod
    def create_candidate(
        db: Session,
        request_id: str,
        candidate_index: int,
        retry_index: int = 0,  # 新增：重试序号
        user_id: Optional[str] = None,
        api_key_id: Optional[str] = None,
        provider_id: Optional[str] = None,
        endpoint_id: Optional[str] = None,
        key_id: Optional[str] = None,
        status: str = "available",
        skip_reason: Optional[str] = None,
        is_cached: bool = False,
        extra_data: Optional[dict] = None,
        required_capabilities: Optional[dict] = None,
    ) -> RequestCandidate:
        """
        创建候选记录

        Args:
            db: 数据库会话
            request_id: 请求ID
            candidate_index: 候选序号
            retry_index: 重试序号（从0开始）
            user_id: 用户ID
            api_key_id: API Key ID
            provider_id: Provider ID
            endpoint_id: Endpoint ID
            key_id: API Key ID
            status: 候选状态 ('available', 'used', 'skipped', 'success', 'failed')
            skip_reason: 跳过原因
            is_cached: 是否为缓存亲和性候选
            extra_data: 额外数据
            required_capabilities: 请求需要的能力标签
        """
        candidate = RequestCandidate(
            id=str(uuid.uuid4()),
            request_id=request_id,
            candidate_index=candidate_index,
            retry_index=retry_index,  # 新增
            user_id=user_id,
            api_key_id=api_key_id,
            provider_id=provider_id,
            endpoint_id=endpoint_id,
            key_id=key_id,
            status=status,
            skip_reason=skip_reason,
            is_cached=is_cached,
            extra_data=extra_data or {},
            required_capabilities=required_capabilities,
            created_at=datetime.now(timezone.utc),
        )
        db.add(candidate)
        db.flush()  # 只flush，不立即 commit
        # 标记为批量提交（非关键数据，可延迟）
        get_batch_committer().mark_dirty(db)
        return candidate

    @staticmethod
    def mark_candidate_started(db: Session, candidate_id: str) -> None:
        """
        标记候选开始执行

        Args:
            db: 数据库会话
            candidate_id: 候选ID
        """
        candidate = db.query(RequestCandidate).filter(RequestCandidate.id == candidate_id).first()
        if candidate:
            candidate.status = "pending"
            candidate.started_at = datetime.now(timezone.utc)
            # 关键状态更新：立即提交，不使用批量提交
            # 原因：前端需要实时看到请求开始执行
            db.commit()

    @staticmethod
    def update_candidate_status(db: Session, candidate_id: str, status: str) -> None:
        """
        更新候选状态（通用方法）

        Args:
            db: 数据库会话
            candidate_id: 候选ID
            status: 新状态（pending, available, success, failed, skipped）
        """
        candidate = db.query(RequestCandidate).filter(RequestCandidate.id == candidate_id).first()
        if candidate:
            candidate.status = status
            # 如果状态变更为 pending，记录开始时间
            if status == "pending" and not candidate.started_at:
                candidate.started_at = datetime.now(timezone.utc)
            # 立即提交，确保前端能实时看到状态变化
            db.commit()

    @staticmethod
    def mark_candidate_streaming(
        db: Session,
        candidate_id: str,
        status_code: int = 200,
        concurrent_requests: Optional[int] = None,
    ) -> None:
        """
        标记候选为流式传输中

        用于流式请求：连接建立成功后，流开始传输时调用。
        此时请求尚未完成，需要等流传输完毕后再调用 mark_candidate_success。

        Args:
            db: 数据库会话
            candidate_id: 候选ID
            status_code: HTTP 状态码（通常是 200）
            concurrent_requests: 并发请求数
        """
        candidate = db.query(RequestCandidate).filter(RequestCandidate.id == candidate_id).first()
        if candidate:
            candidate.status = "streaming"
            candidate.status_code = status_code
            candidate.concurrent_requests = concurrent_requests
            # streaming 状态不设置 finished_at，因为请求还在进行中
            db.commit()

    @staticmethod
    def mark_candidate_success(
        db: Session,
        candidate_id: str,
        status_code: int,
        latency_ms: int,
        concurrent_requests: Optional[int] = None,
        extra_data: Optional[dict] = None,
    ) -> None:
        """
        标记候选执行成功

        Args:
            db: 数据库会话
            candidate_id: 候选ID
            status_code: HTTP 状态码
            latency_ms: 延迟（毫秒）
            concurrent_requests: 并发请求数
            extra_data: 额外数据
        """
        candidate = db.query(RequestCandidate).filter(RequestCandidate.id == candidate_id).first()
        if candidate:
            candidate.status = "success"
            candidate.status_code = status_code
            candidate.latency_ms = latency_ms
            candidate.concurrent_requests = concurrent_requests
            candidate.finished_at = datetime.now(timezone.utc)
            if extra_data:
                candidate.extra_data = {**(candidate.extra_data or {}), **extra_data}
            # 关键状态更新：立即提交，不使用批量提交
            # 原因：前端需要实时看到请求成功/失败状态
            db.commit()

    @staticmethod
    def mark_candidate_failed(
        db: Session,
        candidate_id: str,
        error_type: str,
        error_message: str,
        status_code: Optional[int] = None,
        latency_ms: Optional[int] = None,
        concurrent_requests: Optional[int] = None,
        extra_data: Optional[dict] = None,
    ) -> None:
        """
        标记候选执行失败

        Args:
            db: 数据库会话
            candidate_id: 候选ID
            error_type: 错误类型
            error_message: 错误消息
            status_code: HTTP 状态码（如果有）
            latency_ms: 延迟（毫秒）
            concurrent_requests: 并发请求数
            extra_data: 额外数据
        """
        candidate = db.query(RequestCandidate).filter(RequestCandidate.id == candidate_id).first()
        if candidate:
            candidate.status = "failed"
            candidate.error_type = error_type
            candidate.error_message = error_message
            candidate.status_code = status_code
            candidate.latency_ms = latency_ms
            candidate.concurrent_requests = concurrent_requests
            candidate.finished_at = datetime.now(timezone.utc)
            if extra_data:
                candidate.extra_data = {**(candidate.extra_data or {}), **extra_data}
            # 关键状态更新：立即提交，不使用批量提交
            # 原因：前端需要实时看到请求成功/失败状态
            db.commit()

    @staticmethod
    def mark_candidate_skipped(
        db: Session, candidate_id: str, skip_reason: Optional[str] = None
    ) -> None:
        """
        标记候选为已跳过

        Args:
            db: 数据库会话
            candidate_id: 候选ID
            skip_reason: 跳过原因
        """
        candidate = db.query(RequestCandidate).filter(RequestCandidate.id == candidate_id).first()
        if candidate:
            candidate.status = "skipped"
            candidate.skip_reason = skip_reason
            candidate.finished_at = datetime.now(timezone.utc)
            db.flush()  # 只 flush，不立即 commit
            get_batch_committer().mark_dirty(db)

    @staticmethod
    def get_candidates_by_request_id(db: Session, request_id: str) -> List[RequestCandidate]:
        """
        获取请求的所有候选记录

        Args:
            db: 数据库会话
            request_id: 请求ID

        Returns:
            候选记录列表，按 candidate_index 排序
        """
        return (
            db.query(RequestCandidate)
            .filter(RequestCandidate.request_id == request_id)
            .order_by(RequestCandidate.candidate_index)
            .all()
        )

    @staticmethod
    def get_candidate_stats_by_provider(db: Session, provider_id: str, limit: int = 100) -> dict:
        """
        获取 Provider 的候选统计

        Args:
            db: 数据库会话
            provider_id: Provider ID
            limit: 最近记录数量限制

        Returns:
            统计信息字典
        """
        candidates = (
            db.query(RequestCandidate)
            .filter(RequestCandidate.provider_id == provider_id)
            .order_by(RequestCandidate.created_at.desc())
            .limit(limit)
            .all()
        )

        total_candidates = len(candidates)
        success_count = sum(1 for c in candidates if c.status == "success")
        failed_count = sum(1 for c in candidates if c.status == "failed")
        skipped_count = sum(1 for c in candidates if c.status == "skipped")
        pending_count = sum(1 for c in candidates if c.status == "pending")
        available_count = sum(1 for c in candidates if c.status == "available")

        # 计算失败率（只统计已完成的候选，即成功或失败的）
        completed_count = success_count + failed_count
        failure_rate = (failed_count / completed_count * 100) if completed_count > 0 else 0

        return {
            "total_attempts": total_candidates,  # 前端使用 total_attempts 字段
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "pending_count": pending_count,
            "available_count": available_count,  # 新增：尚未被调度的候选数
            "failure_rate": round(failure_rate, 2),
        }

    @staticmethod
    def calculate_candidate_ttfb(
        db: Session,
        candidate_id: str,
        request_start_time: float,
        global_first_byte_time_ms: int,
    ) -> int:
        """
        计算候选自身的首字节时间 (TTFB)

        请求链路追踪中的 TTFB 应该是"该候选自身"的首字时间，
        而不是整个请求从开始到收到首字节的时间。

        Args:
            db: 数据库会话
            candidate_id: 候选 ID
            request_start_time: 请求开始时间（Unix timestamp，秒）
            global_first_byte_time_ms: 全局首字节时间（相对于 request_start_time 的毫秒数）

        Returns:
            候选自身的 TTFB（毫秒），如果计算失败则返回 global_first_byte_time_ms
        """
        try:
            candidate = db.query(RequestCandidate).filter(RequestCandidate.id == candidate_id).first()
            if candidate and candidate.started_at:
                started_at = candidate.started_at
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                # 使用整数毫秒计算，避免浮点精度问题
                request_start_epoch_ms = round(request_start_time * 1000)
                started_at_epoch_ms = round(started_at.timestamp() * 1000)
                first_byte_epoch_ms = request_start_epoch_ms + global_first_byte_time_ms
                return max(0, int(first_byte_epoch_ms - started_at_epoch_ms))
        except Exception as e:
            logger.debug(f"计算候选 TTFB 失败: {e}")
        return global_first_byte_time_ms

"""
API密钥统计同步服务
定期同步API密钥的统计数据，确保与实际使用记录一致
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.core.logger import logger
from src.models.database import ApiKey, Usage


class SyncStatsService:
    """API密钥统计同步服务"""

    # 分页批量大小
    BATCH_SIZE = 100

    @staticmethod
    def sync_api_key_stats(db: Session, api_key_id: str | None = None) -> dict:  # UUID
        """
        同步API密钥的统计数据

        Args:
            db: 数据库会话
            api_key_id: 指定要同步的API密钥ID，如果不指定则同步所有

        Returns:
            同步结果统计
        """
        result = {"synced": 0, "updated": 0, "errors": 0}

        try:
            # 获取要同步的API密钥（使用分页避免大数据量问题）
            if api_key_id:
                api_keys = db.query(ApiKey).filter(ApiKey.id == api_key_id).all()
            else:
                # 分页处理，避免一次加载所有数据
                offset = 0
                api_keys: list[ApiKey] = []
                while True:
                    batch = db.query(ApiKey).offset(offset).limit(SyncStatsService.BATCH_SIZE).all()
                    if not batch:
                        break
                    api_keys.extend(batch)
                    offset += SyncStatsService.BATCH_SIZE

            # Pre-aggregate Usage stats in ONE query to avoid per-key N+1 scans.
            # This is critical for large datasets (DB CPU killer otherwise).
            usage_stats_map: dict[str, dict[str, Any]] = {}
            if not api_key_id:
                rows = (
                    db.query(
                        Usage.api_key_id,
                        func.count(Usage.id).label("requests"),
                        func.sum(Usage.total_cost_usd).label("cost"),
                        func.max(Usage.created_at).label("last_used"),
                    )
                    .filter(Usage.api_key_id.isnot(None))
                    .group_by(Usage.api_key_id)
                    .all()
                )
                usage_stats_map = {
                    str(r.api_key_id): {
                        "requests": int(r.requests or 0),
                        "cost": float(r.cost or 0),
                        "last_used": r.last_used,
                    }
                    for r in rows
                    if r.api_key_id is not None
                }

            for api_key in api_keys:
                try:
                    if api_key_id:
                        # 单 key 路径：直接查（数据量小）
                        stats = (
                            db.query(
                                func.count(Usage.id).label("requests"),
                                func.sum(Usage.total_cost_usd).label("cost"),
                                func.max(Usage.created_at).label("last_used"),
                            )
                            .filter(Usage.api_key_id == api_key.id)
                            .first()
                        )
                        actual_requests = int(stats.requests or 0) if stats else 0
                        actual_cost = float(stats.cost or 0) if stats else 0.0
                        last_used_at = stats.last_used if stats else None
                    else:
                        # 批量路径：使用预聚合结果
                        s = usage_stats_map.get(str(api_key.id)) or {}
                        actual_requests = int(s.get("requests") or 0)
                        actual_cost = float(s.get("cost") or 0.0)
                        last_used_at = s.get("last_used")

                    # 检查是否需要更新
                    needs_update = False
                    if api_key.total_requests != actual_requests:
                        logger.info(
                            f"API密钥 {api_key.id} 请求数不一致: {api_key.total_requests} -> {actual_requests}"
                        )
                        api_key.total_requests = actual_requests
                        needs_update = True

                    if abs(api_key.total_cost_usd - actual_cost) > 0.0001:
                        logger.info(
                            f"API密钥 {api_key.id} 费用不一致: {api_key.total_cost_usd} -> {actual_cost}"
                        )
                        api_key.total_cost_usd = actual_cost
                        needs_update = True

                    if last_used_at and api_key.last_used_at != last_used_at:
                        api_key.last_used_at = last_used_at
                        needs_update = True

                    result["synced"] += 1
                    if needs_update:
                        result["updated"] += 1
                        logger.info(f"已更新API密钥 {api_key.id} 的统计数据")

                except Exception as e:
                    logger.error(f"同步API密钥 {api_key.id} 统计时出错: {e}")
                    result["errors"] += 1
                    # 回滚当前失败的操作，继续处理其他密钥
                    try:
                        db.rollback()
                    except Exception:
                        pass

            # 提交所有更改
            db.commit()
            logger.info(
                f"同步完成: 处理 {result['synced']} 个密钥, 更新 {result['updated']} 个, 错误 {result['errors']} 个"
            )

        except Exception as e:
            logger.error(f"同步统计数据时出错: {e}")
            db.rollback()
            raise

        return result

    @staticmethod
    def get_api_key_real_stats(db: Session, api_key_id: str) -> dict:  # UUID
        """
        获取API密钥的实际统计数据（直接从使用记录计算）

        Args:
            db: 数据库会话
            api_key_id: API密钥ID

        Returns:
            实际的统计数据
        """
        # 计算实际的使用统计
        stats = (
            db.query(
                func.count(Usage.id).label("requests"),
                func.sum(Usage.total_cost_usd).label("cost"),
                func.max(Usage.created_at).label("last_used"),
            )
            .filter(Usage.api_key_id == api_key_id)
            .first()
        )

        return {
            "total_requests": stats.requests or 0,
            "total_cost_usd": float(stats.cost or 0),
            "last_used_at": stats.last_used,
        }

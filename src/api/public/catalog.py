"""
公开API端点 - 用户可查看的提供商和模型信息
不包含敏感信息，普通用户可访问
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from src.api.base.adapter import ApiAdapter, ApiMode
from src.api.base.pipeline import ApiRequestPipeline
from src.core.logger import logger
from src.database import get_db
from src.models.api import (
    ProviderStatsResponse,
    PublicGlobalModelListResponse,
    PublicGlobalModelResponse,
    PublicModelResponse,
    PublicProviderResponse,
)
from src.models.database import (
    GlobalModel,
    Model,
    Provider,
    ProviderEndpoint,
    RequestCandidate,
)
from src.models.endpoint_models import (
    PublicApiFormatHealthMonitor,
    PublicApiFormatHealthMonitorResponse,
    PublicHealthEvent,
)
from src.services.health.endpoint import EndpointHealthService

router = APIRouter(prefix="/api/public", tags=["Public Catalog"])
pipeline = ApiRequestPipeline()


@router.get("/providers", response_model=List[PublicProviderResponse])
async def get_public_providers(
    request: Request,
    is_active: Optional[bool] = Query(None, description="过滤活跃状态"),
    skip: int = Query(0, description="跳过记录数"),
    limit: int = Query(100, description="返回记录数限制"),
    db: Session = Depends(get_db),
):
    """获取提供商列表（用户视图）。"""

    adapter = PublicProvidersAdapter(is_active=is_active, skip=skip, limit=limit)
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=ApiMode.PUBLIC)


@router.get("/models", response_model=List[PublicModelResponse])
async def get_public_models(
    request: Request,
    provider_id: Optional[str] = Query(None, description="提供商ID过滤"),
    is_active: Optional[bool] = Query(None, description="过滤活跃状态"),
    skip: int = Query(0, description="跳过记录数"),
    limit: int = Query(100, description="返回记录数限制"),
    db: Session = Depends(get_db),
):
    adapter = PublicModelsAdapter(
        provider_id=provider_id, is_active=is_active, skip=skip, limit=limit
    )
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=ApiMode.PUBLIC)


@router.get("/stats", response_model=ProviderStatsResponse)
async def get_public_stats(request: Request, db: Session = Depends(get_db)):
    adapter = PublicStatsAdapter()
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=ApiMode.PUBLIC)


@router.get("/search/models")
async def search_models(
    request: Request,
    q: str = Query(..., description="搜索关键词"),
    provider_id: Optional[int] = Query(None, description="提供商ID过滤"),
    limit: int = Query(20, description="返回记录数限制"),
    db: Session = Depends(get_db),
):
    adapter = PublicSearchModelsAdapter(query=q, provider_id=provider_id, limit=limit)
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=ApiMode.PUBLIC)


@router.get("/health/api-formats", response_model=PublicApiFormatHealthMonitorResponse)
async def get_public_api_format_health(
    request: Request,
    lookback_hours: int = Query(6, ge=1, le=168, description="回溯小时数"),
    per_format_limit: int = Query(100, ge=10, le=500, description="每个格式的事件数限制"),
    db: Session = Depends(get_db),
):
    """获取各 API 格式的健康监控数据（公开版，不含敏感信息）"""
    adapter = PublicApiFormatHealthMonitorAdapter(
        lookback_hours=lookback_hours,
        per_format_limit=per_format_limit,
    )
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=ApiMode.PUBLIC)


@router.get("/global-models", response_model=PublicGlobalModelListResponse)
async def get_public_global_models(
    request: Request,
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数限制"),
    is_active: Optional[bool] = Query(None, description="过滤活跃状态"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    db: Session = Depends(get_db),
):
    """获取 GlobalModel 列表（用户视图，只读）"""
    adapter = PublicGlobalModelsAdapter(
        skip=skip,
        limit=limit,
        is_active=is_active,
        search=search,
    )
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=ApiMode.PUBLIC)


# -------- 公共适配器 --------


class PublicApiAdapter(ApiAdapter):
    mode = ApiMode.PUBLIC

    def authorize(self, context):  # type: ignore[override]
        return None


@dataclass
class PublicProvidersAdapter(PublicApiAdapter):
    is_active: Optional[bool]
    skip: int
    limit: int

    async def handle(self, context):  # type: ignore[override]
        db = context.db
        logger.debug("公共API请求提供商列表")
        query = db.query(Provider)
        if self.is_active is not None:
            query = query.filter(Provider.is_active == self.is_active)
        else:
            query = query.filter(Provider.is_active.is_(True))

        providers = query.offset(self.skip).limit(self.limit).all()
        result = []
        for provider in providers:
            models_count = db.query(Model).filter(Model.provider_id == provider.id).count()
            active_models_count = (
                db.query(Model)
                .filter(and_(Model.provider_id == provider.id, Model.is_active.is_(True)))
                .count()
            )
            endpoints_count = len(provider.endpoints) if provider.endpoints else 0
            active_endpoints_count = (
                sum(1 for ep in provider.endpoints if ep.is_active) if provider.endpoints else 0
            )
            provider_data = PublicProviderResponse(
                id=provider.id,
                name=provider.name,
                display_name=provider.display_name,
                description=provider.description,
                is_active=provider.is_active,
                provider_priority=provider.provider_priority,
                models_count=models_count,
                active_models_count=active_models_count,
                endpoints_count=endpoints_count,
                active_endpoints_count=active_endpoints_count,
            )
            result.append(provider_data.model_dump())

        logger.debug(f"返回 {len(result)} 个提供商信息")
        return result


@dataclass
class PublicModelsAdapter(PublicApiAdapter):
    provider_id: Optional[str]
    is_active: Optional[bool]
    skip: int
    limit: int

    async def handle(self, context):  # type: ignore[override]
        db = context.db
        logger.debug("公共API请求模型列表")
        query = (
            db.query(Model, Provider)
            .options(joinedload(Model.global_model))
            .join(Provider)
            .filter(and_(Model.is_active.is_(True), Provider.is_active.is_(True)))
        )
        if self.provider_id is not None:
            query = query.filter(Model.provider_id == self.provider_id)
        results = query.offset(self.skip).limit(self.limit).all()

        response = []
        for model, provider in results:
            global_model = model.global_model
            display_name = global_model.display_name if global_model else model.provider_model_name
            unified_name = global_model.name if global_model else model.provider_model_name
            model_data = PublicModelResponse(
                id=model.id,
                provider_id=model.provider_id,
                provider_name=provider.name,
                provider_display_name=provider.display_name,
                name=unified_name,
                display_name=display_name,
                description=global_model.description if global_model else None,
                tags=None,
                icon_url=global_model.icon_url if global_model else None,
                input_price_per_1m=model.get_effective_input_price(),
                output_price_per_1m=model.get_effective_output_price(),
                cache_creation_price_per_1m=model.get_effective_cache_creation_price(),
                cache_read_price_per_1m=model.get_effective_cache_read_price(),
                supports_vision=model.get_effective_supports_vision(),
                supports_function_calling=model.get_effective_supports_function_calling(),
                supports_streaming=model.get_effective_supports_streaming(),
                is_active=model.is_active,
            )
            response.append(model_data.model_dump())

        logger.debug(f"返回 {len(response)} 个模型信息")
        return response


class PublicStatsAdapter(PublicApiAdapter):
    async def handle(self, context):  # type: ignore[override]
        db = context.db
        logger.debug("公共API请求系统统计信息")
        active_providers = db.query(Provider).filter(Provider.is_active.is_(True)).count()
        active_models = (
            db.query(Model)
            .join(Provider)
            .filter(and_(Model.is_active.is_(True), Provider.is_active.is_(True)))
            .count()
        )
        formats = (
            db.query(Provider.api_format).filter(Provider.is_active.is_(True)).distinct().all()
        )
        supported_formats = [f.api_format for f in formats if f.api_format]
        stats = ProviderStatsResponse(
            total_providers=active_providers,
            active_providers=active_providers,
            total_models=active_models,
            active_models=active_models,
            supported_formats=supported_formats,
        )
        logger.debug("返回系统统计信息")
        return stats.model_dump()


@dataclass
class PublicSearchModelsAdapter(PublicApiAdapter):
    query: str
    provider_id: Optional[int]
    limit: int

    async def handle(self, context):  # type: ignore[override]
        db = context.db
        logger.debug(f"公共API搜索模型: {self.query}")
        query_stmt = (
            db.query(Model, Provider)
            .options(joinedload(Model.global_model))
            .join(Provider)
            .outerjoin(GlobalModel, Model.global_model_id == GlobalModel.id)
            .filter(and_(Model.is_active.is_(True), Provider.is_active.is_(True)))
        )
        search_filter = (
            Model.provider_model_name.ilike(f"%{self.query}%")
            | GlobalModel.name.ilike(f"%{self.query}%")
            | GlobalModel.display_name.ilike(f"%{self.query}%")
            | GlobalModel.description.ilike(f"%{self.query}%")
        )
        query_stmt = query_stmt.filter(search_filter)
        if self.provider_id is not None:
            query_stmt = query_stmt.filter(Model.provider_id == self.provider_id)
        results = query_stmt.limit(self.limit).all()

        response = []
        for model, provider in results:
            global_model = model.global_model
            display_name = global_model.display_name if global_model else model.provider_model_name
            unified_name = global_model.name if global_model else model.provider_model_name
            model_data = PublicModelResponse(
                id=model.id,
                provider_id=model.provider_id,
                provider_name=provider.name,
                provider_display_name=provider.display_name,
                name=unified_name,
                display_name=display_name,
                description=global_model.description if global_model else None,
                tags=None,
                icon_url=global_model.icon_url if global_model else None,
                input_price_per_1m=model.get_effective_input_price(),
                output_price_per_1m=model.get_effective_output_price(),
                cache_creation_price_per_1m=model.get_effective_cache_creation_price(),
                cache_read_price_per_1m=model.get_effective_cache_read_price(),
                supports_vision=model.get_effective_supports_vision(),
                supports_function_calling=model.get_effective_supports_function_calling(),
                supports_streaming=model.get_effective_supports_streaming(),
                is_active=model.is_active,
            )
            response.append(model_data.model_dump())

        logger.debug(f"搜索 '{self.query}' 返回 {len(response)} 个结果")
        return response


@dataclass
class PublicApiFormatHealthMonitorAdapter(PublicApiAdapter):
    """公开版 API 格式健康监控适配器（返回 events 数组，前端复用 EndpointHealthTimeline 组件）"""

    lookback_hours: int
    per_format_limit: int

    async def handle(self, context):  # type: ignore[override]
        db = context.db
        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=self.lookback_hours)

        # 1. 获取所有活跃的 API 格式
        active_formats = (
            db.query(ProviderEndpoint.api_format)
            .join(Provider, ProviderEndpoint.provider_id == Provider.id)
            .filter(
                ProviderEndpoint.is_active.is_(True),
                Provider.is_active.is_(True),
            )
            .distinct()
            .all()
        )

        all_formats: List[str] = []
        for (api_format_enum,) in active_formats:
            api_format = (
                api_format_enum.value if hasattr(api_format_enum, "value") else str(api_format_enum)
            )
            all_formats.append(api_format)

        # API 格式 -> Endpoint ID 映射（用于 Usage 时间线）
        endpoint_rows = (
            db.query(ProviderEndpoint.api_format, ProviderEndpoint.id)
            .join(Provider, ProviderEndpoint.provider_id == Provider.id)
            .filter(
                ProviderEndpoint.is_active.is_(True),
                Provider.is_active.is_(True),
            )
            .all()
        )
        endpoint_map: Dict[str, List[str]] = defaultdict(list)
        for api_format_enum, endpoint_id in endpoint_rows:
            api_format = (
                api_format_enum.value if hasattr(api_format_enum, "value") else str(api_format_enum)
            )
            endpoint_map[api_format].append(endpoint_id)

        # 2. 获取最近一段时间的 RequestCandidate（限制数量）
        # 只查询最终状态的记录：success, failed, skipped
        final_statuses = ["success", "failed", "skipped"]
        limit_rows = max(500, self.per_format_limit * 10)
        rows = (
            db.query(
                RequestCandidate,
                ProviderEndpoint.api_format,
            )
            .join(ProviderEndpoint, RequestCandidate.endpoint_id == ProviderEndpoint.id)
            .filter(
                RequestCandidate.created_at >= since,
                RequestCandidate.status.in_(final_statuses),
            )
            .order_by(RequestCandidate.created_at.desc())
            .limit(limit_rows)
            .all()
        )

        grouped_candidates: Dict[str, List[RequestCandidate]] = {}

        for candidate, api_format_enum in rows:
            api_format = (
                api_format_enum.value if hasattr(api_format_enum, "value") else str(api_format_enum)
            )
            if api_format not in grouped_candidates:
                grouped_candidates[api_format] = []

            if len(grouped_candidates[api_format]) < self.per_format_limit:
                grouped_candidates[api_format].append(candidate)

        # 3. 为所有活跃格式生成监控数据
        monitors: List[PublicApiFormatHealthMonitor] = []
        for api_format in all_formats:
            candidates = grouped_candidates.get(api_format, [])

            # 统计
            success_count = sum(1 for c in candidates if c.status == "success")
            failed_count = sum(1 for c in candidates if c.status == "failed")
            skipped_count = sum(1 for c in candidates if c.status == "skipped")
            total_attempts = len(candidates)

            # 计算成功率 = success / (success + failed)
            actual_completed = success_count + failed_count
            success_rate = success_count / actual_completed if actual_completed > 0 else 1.0

            # 转换为公开版事件列表（不含敏感信息如 provider_id, key_id）
            events: List[PublicHealthEvent] = []
            for c in candidates:
                event_time = c.finished_at or c.started_at or c.created_at
                events.append(
                    PublicHealthEvent(
                        timestamp=event_time,
                        status=c.status,
                        status_code=c.status_code,
                        latency_ms=c.latency_ms,
                        error_type=c.error_type,
                    )
                )

            # 最后事件时间
            last_event_at = None
            if candidates:
                last_event_at = (
                    candidates[0].finished_at
                    or candidates[0].started_at
                    or candidates[0].created_at
                )

            timeline_data = EndpointHealthService._generate_timeline_from_usage(
                db=db,
                endpoint_ids=endpoint_map.get(api_format, []),
                now=now,
                lookback_hours=self.lookback_hours,
            )

            # 获取本站入口路径
            from src.core.api_format_metadata import get_local_path
            from src.core.enums import APIFormat

            try:
                api_format_enum = APIFormat(api_format)
                local_path = get_local_path(api_format_enum)
            except ValueError:
                local_path = "/"

            monitors.append(
                PublicApiFormatHealthMonitor(
                    api_format=api_format,
                    api_path=local_path,
                    total_attempts=total_attempts,
                    success_count=success_count,
                    failed_count=failed_count,
                    skipped_count=skipped_count,
                    success_rate=success_rate,
                    last_event_at=last_event_at,
                    events=events,
                    timeline=timeline_data.get("timeline", []),
                    time_range_start=timeline_data.get("time_range_start"),
                    time_range_end=timeline_data.get("time_range_end"),
                )
            )

        response = PublicApiFormatHealthMonitorResponse(
            generated_at=now,
            formats=monitors,
        )

        logger.debug(f"公开健康监控: 返回 {len(monitors)} 个 API 格式的健康数据")
        return response


@dataclass
class PublicGlobalModelsAdapter(PublicApiAdapter):
    """公开的 GlobalModel 列表适配器"""

    skip: int
    limit: int
    is_active: Optional[bool]
    search: Optional[str]

    async def handle(self, context):  # type: ignore[override]
        db = context.db
        logger.debug("公共API请求 GlobalModel 列表")

        query = db.query(GlobalModel)

        # 默认只返回活跃的模型
        if self.is_active is not None:
            query = query.filter(GlobalModel.is_active == self.is_active)
        else:
            query = query.filter(GlobalModel.is_active.is_(True))

        # 搜索过滤
        if self.search:
            search_term = f"%{self.search}%"
            query = query.filter(
                or_(
                    GlobalModel.name.ilike(search_term),
                    GlobalModel.display_name.ilike(search_term),
                    GlobalModel.description.ilike(search_term),
                )
            )

        # 统计总数
        total = query.count()

        # 分页
        models = query.order_by(GlobalModel.name).offset(self.skip).limit(self.limit).all()

        # 转换为响应格式
        model_responses = []
        for gm in models:
            model_responses.append(
                PublicGlobalModelResponse(
                    id=gm.id,
                    name=gm.name,
                    display_name=gm.display_name,
                    description=gm.description,
                    icon_url=gm.icon_url,
                    is_active=gm.is_active,
                    default_price_per_request=gm.default_price_per_request,
                    default_tiered_pricing=gm.default_tiered_pricing,
                    default_supports_vision=gm.default_supports_vision or False,
                    default_supports_function_calling=gm.default_supports_function_calling or False,
                    default_supports_streaming=(
                        gm.default_supports_streaming
                        if gm.default_supports_streaming is not None
                        else True
                    ),
                    default_supports_extended_thinking=gm.default_supports_extended_thinking
                    or False,
                    supported_capabilities=gm.supported_capabilities,
                )
            )

        logger.debug(f"返回 {len(model_responses)} 个 GlobalModel")
        return PublicGlobalModelListResponse(models=model_responses, total=total)

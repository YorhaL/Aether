"""
GlobalModel Admin API

提供 GlobalModel 的 CRUD 操作接口
"""

from dataclasses import dataclass
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.api.base.admin_adapter import AdminApiAdapter
from src.api.base.pipeline import ApiRequestPipeline
from src.core.logger import logger
from src.database import get_db
from src.models.pydantic_models import (
    BatchAssignToProvidersRequest,
    BatchAssignToProvidersResponse,
    GlobalModelCreate,
    GlobalModelListResponse,
    GlobalModelResponse,
    GlobalModelUpdate,
    GlobalModelWithStats,
)
from src.services.model.global_model import GlobalModelService

router = APIRouter(prefix="/global", tags=["Admin - Global Models"])
pipeline = ApiRequestPipeline()


@router.get("", response_model=GlobalModelListResponse)
async def list_global_models(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> GlobalModelListResponse:
    """获取 GlobalModel 列表"""
    adapter = AdminListGlobalModelsAdapter(
        skip=skip,
        limit=limit,
        is_active=is_active,
        search=search,
    )
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.get("/{global_model_id}", response_model=GlobalModelWithStats)
async def get_global_model(
    request: Request,
    global_model_id: str,
    db: Session = Depends(get_db),
) -> GlobalModelWithStats:
    """获取单个 GlobalModel 详情（含统计信息）"""
    adapter = AdminGetGlobalModelAdapter(global_model_id=global_model_id)
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.post("", response_model=GlobalModelResponse, status_code=201)
async def create_global_model(
    request: Request,
    payload: GlobalModelCreate,
    db: Session = Depends(get_db),
) -> GlobalModelResponse:
    """创建 GlobalModel"""
    adapter = AdminCreateGlobalModelAdapter(payload=payload)
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.patch("/{global_model_id}", response_model=GlobalModelResponse)
async def update_global_model(
    request: Request,
    global_model_id: str,
    payload: GlobalModelUpdate,
    db: Session = Depends(get_db),
) -> GlobalModelResponse:
    """更新 GlobalModel"""
    adapter = AdminUpdateGlobalModelAdapter(global_model_id=global_model_id, payload=payload)
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.delete("/{global_model_id}", status_code=204)
async def delete_global_model(
    request: Request,
    global_model_id: str,
    db: Session = Depends(get_db),
):
    """删除 GlobalModel（级联删除所有关联的 Provider 模型实现）"""
    adapter = AdminDeleteGlobalModelAdapter(global_model_id=global_model_id)
    await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)
    return None


@router.post(
    "/{global_model_id}/assign-to-providers", response_model=BatchAssignToProvidersResponse
)
async def batch_assign_to_providers(
    request: Request,
    global_model_id: str,
    payload: BatchAssignToProvidersRequest,
    db: Session = Depends(get_db),
) -> BatchAssignToProvidersResponse:
    """批量为多个 Provider 添加 GlobalModel 实现"""
    adapter = AdminBatchAssignToProvidersAdapter(global_model_id=global_model_id, payload=payload)
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


# ========== Adapters ==========


@dataclass
class AdminListGlobalModelsAdapter(AdminApiAdapter):
    """列出 GlobalModel"""

    skip: int
    limit: int
    is_active: Optional[bool]
    search: Optional[str]

    async def handle(self, context):  # type: ignore[override]
        from sqlalchemy import func

        from src.models.database import Model

        models = GlobalModelService.list_global_models(
            db=context.db,
            skip=self.skip,
            limit=self.limit,
            is_active=self.is_active,
            search=self.search,
        )

        # 为每个 GlobalModel 添加统计数据
        model_responses = []
        for gm in models:
            # 统计关联的 Model 数量（去重 Provider）
            provider_count = (
                context.db.query(func.count(func.distinct(Model.provider_id)))
                .filter(Model.global_model_id == gm.id)
                .scalar()
                or 0
            )

            response = GlobalModelResponse.model_validate(gm)
            response.provider_count = provider_count
            # usage_count 直接从 GlobalModel 表读取，已在 model_validate 中自动映射
            model_responses.append(response)

        return GlobalModelListResponse(
            models=model_responses,
            total=len(models),
        )


@dataclass
class AdminGetGlobalModelAdapter(AdminApiAdapter):
    """获取单个 GlobalModel"""

    global_model_id: str

    async def handle(self, context):  # type: ignore[override]
        global_model = GlobalModelService.get_global_model(context.db, self.global_model_id)
        stats = GlobalModelService.get_global_model_stats(context.db, self.global_model_id)

        return GlobalModelWithStats(
            **GlobalModelResponse.model_validate(global_model).model_dump(),
            total_models=stats["total_models"],
            total_providers=stats["total_providers"],
            price_range=stats["price_range"],
        )


@dataclass
class AdminCreateGlobalModelAdapter(AdminApiAdapter):
    """创建 GlobalModel"""

    payload: GlobalModelCreate

    async def handle(self, context):  # type: ignore[override]
        # 将 TieredPricingConfig 转换为 dict
        tiered_pricing_dict = self.payload.default_tiered_pricing.model_dump()

        global_model = GlobalModelService.create_global_model(
            db=context.db,
            name=self.payload.name,
            display_name=self.payload.display_name,
            description=self.payload.description,
            official_url=self.payload.official_url,
            icon_url=self.payload.icon_url,
            is_active=self.payload.is_active,
            # 按次计费配置
            default_price_per_request=self.payload.default_price_per_request,
            # 阶梯计费配置
            default_tiered_pricing=tiered_pricing_dict,
            # 默认能力配置
            default_supports_vision=self.payload.default_supports_vision,
            default_supports_function_calling=self.payload.default_supports_function_calling,
            default_supports_streaming=self.payload.default_supports_streaming,
            default_supports_extended_thinking=self.payload.default_supports_extended_thinking,
            # Key 能力配置
            supported_capabilities=self.payload.supported_capabilities,
        )

        logger.info(f"GlobalModel 已创建: id={global_model.id} name={global_model.name}")

        return GlobalModelResponse.model_validate(global_model)


@dataclass
class AdminUpdateGlobalModelAdapter(AdminApiAdapter):
    """更新 GlobalModel"""

    global_model_id: str
    payload: GlobalModelUpdate

    async def handle(self, context):  # type: ignore[override]
        global_model = GlobalModelService.update_global_model(
            db=context.db,
            global_model_id=self.global_model_id,
            update_data=self.payload,
        )

        logger.info(f"GlobalModel 已更新: id={global_model.id} name={global_model.name}")

        # 失效相关缓存
        from src.services.cache.invalidation import get_cache_invalidation_service

        cache_service = get_cache_invalidation_service()
        cache_service.on_global_model_changed(global_model.name)

        return GlobalModelResponse.model_validate(global_model)


@dataclass
class AdminDeleteGlobalModelAdapter(AdminApiAdapter):
    """删除 GlobalModel（级联删除所有关联的 Provider 模型实现）"""

    global_model_id: str

    async def handle(self, context):  # type: ignore[override]
        # 先获取 GlobalModel 信息（用于失效缓存）
        from src.models.database import GlobalModel

        global_model = (
            context.db.query(GlobalModel).filter(GlobalModel.id == self.global_model_id).first()
        )
        model_name = global_model.name if global_model else None

        GlobalModelService.delete_global_model(context.db, self.global_model_id)

        logger.info(f"GlobalModel 已删除: id={self.global_model_id}")

        # 失效相关缓存
        if model_name:
            from src.services.cache.invalidation import get_cache_invalidation_service

            cache_service = get_cache_invalidation_service()
            cache_service.on_global_model_changed(model_name)

        return None


@dataclass
class AdminBatchAssignToProvidersAdapter(AdminApiAdapter):
    """批量为 Provider 添加 GlobalModel 实现"""

    global_model_id: str
    payload: BatchAssignToProvidersRequest

    async def handle(self, context):  # type: ignore[override]
        result = GlobalModelService.batch_assign_to_providers(
            db=context.db,
            global_model_id=self.global_model_id,
            provider_ids=self.payload.provider_ids,
            create_models=self.payload.create_models,
        )

        logger.info(f"批量为 Provider 添加 GlobalModel: global_model_id={self.global_model_id} success={len(result['success'])} errors={len(result['errors'])}")

        return BatchAssignToProvidersResponse(**result)

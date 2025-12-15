"""
统一模型目录 Admin API

基于 GlobalModel 的聚合视图
"""

from dataclasses import dataclass
from typing import Dict, List

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, joinedload

from src.api.base.admin_adapter import AdminApiAdapter
from src.api.base.pipeline import ApiRequestPipeline
from src.database import get_db
from src.models.database import GlobalModel, Model
from src.models.pydantic_models import (
    ModelCapabilities,
    ModelCatalogItem,
    ModelCatalogProviderDetail,
    ModelCatalogResponse,
    ModelPriceRange,
)

router = APIRouter(prefix="/catalog", tags=["Admin - Model Catalog"])
pipeline = ApiRequestPipeline()


@router.get("", response_model=ModelCatalogResponse)
async def get_model_catalog(
    request: Request,
    db: Session = Depends(get_db),
) -> ModelCatalogResponse:
    adapter = AdminGetModelCatalogAdapter()
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@dataclass
class AdminGetModelCatalogAdapter(AdminApiAdapter):
    """管理员查询统一模型目录

    架构说明：
    1. 以 GlobalModel 为中心聚合数据
    2. Model 表提供关联提供商和价格
    """

    async def handle(self, context):  # type: ignore[override]
        db: Session = context.db

        # 1. 获取所有活跃的 GlobalModel
        global_models: List[GlobalModel] = (
            db.query(GlobalModel).filter(GlobalModel.is_active == True).all()
        )

        # 2. 获取所有活跃的 Model 实现（包含 global_model 以便计算有效价格）
        models: List[Model] = (
            db.query(Model)
            .options(joinedload(Model.provider), joinedload(Model.global_model))
            .filter(Model.is_active == True)
            .all()
        )

        # 按 GlobalModel ID 组织关联提供商
        models_by_global_model: Dict[str, List[Model]] = {}
        for model in models:
            if model.global_model_id:
                models_by_global_model.setdefault(model.global_model_id, []).append(model)

        # 3. 为每个 GlobalModel 构建 catalog item
        catalog_items: List[ModelCatalogItem] = []

        for gm in global_models:
            gm_id = gm.id
            provider_entries: List[ModelCatalogProviderDetail] = []
            capability_flags = {
                "supports_vision": gm.default_supports_vision or False,
                "supports_function_calling": gm.default_supports_function_calling or False,
                "supports_streaming": gm.default_supports_streaming or False,
            }

            # 遍历该 GlobalModel 的所有关联提供商
            for model in models_by_global_model.get(gm_id, []):
                provider = model.provider
                if not provider:
                    continue

                # 使用有效价格（考虑 GlobalModel 默认值）
                effective_input = model.get_effective_input_price()
                effective_output = model.get_effective_output_price()
                effective_tiered = model.get_effective_tiered_pricing()
                tier_count = len(effective_tiered.get("tiers", [])) if effective_tiered else 1

                # 使用有效能力值
                capability_flags["supports_vision"] = (
                    capability_flags["supports_vision"] or model.get_effective_supports_vision()
                )
                capability_flags["supports_function_calling"] = (
                    capability_flags["supports_function_calling"]
                    or model.get_effective_supports_function_calling()
                )
                capability_flags["supports_streaming"] = (
                    capability_flags["supports_streaming"]
                    or model.get_effective_supports_streaming()
                )

                provider_entries.append(
                    ModelCatalogProviderDetail(
                        provider_id=provider.id,
                        provider_name=provider.name,
                        provider_display_name=provider.display_name,
                        model_id=model.id,
                        target_model=model.provider_model_name,
                        # 显示有效价格
                        input_price_per_1m=effective_input,
                        output_price_per_1m=effective_output,
                        cache_creation_price_per_1m=model.get_effective_cache_creation_price(),
                        cache_read_price_per_1m=model.get_effective_cache_read_price(),
                        cache_1h_creation_price_per_1m=model.get_effective_1h_cache_creation_price(),
                        price_per_request=model.get_effective_price_per_request(),
                        effective_tiered_pricing=effective_tiered,
                        tier_count=tier_count,
                        supports_vision=model.get_effective_supports_vision(),
                        supports_function_calling=model.get_effective_supports_function_calling(),
                        supports_streaming=model.get_effective_supports_streaming(),
                        is_active=bool(model.is_active),
                    )
                )

            # 模型目录显示 GlobalModel 的第一个阶梯价格（不是 Provider 聚合价格）
            tiered = gm.default_tiered_pricing or {}
            first_tier = tiered.get("tiers", [{}])[0] if tiered.get("tiers") else {}
            price_range = ModelPriceRange(
                min_input=first_tier.get("input_price_per_1m", 0),
                max_input=first_tier.get("input_price_per_1m", 0),
                min_output=first_tier.get("output_price_per_1m", 0),
                max_output=first_tier.get("output_price_per_1m", 0),
            )

            catalog_items.append(
                ModelCatalogItem(
                    global_model_name=gm.name,
                    display_name=gm.display_name,
                    description=gm.description,
                    providers=provider_entries,
                    price_range=price_range,
                    total_providers=len(provider_entries),
                    capabilities=ModelCapabilities(**capability_flags),
                )
            )

        return ModelCatalogResponse(
            models=catalog_items,
            total=len(catalog_items),
        )

"""Billing 配置管理 API 路由。

包含：
- billing_rules: 计费规则（公式/变量/维度映射）
- dimension_collectors: 维度采集器（request/response/metadata/computed）
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.base.admin_adapter import AdminApiAdapter
from src.api.base.context import ApiRequestContext
from src.api.base.pipeline import ApiRequestPipeline
from src.core.exceptions import InvalidRequestException, NotFoundException
from src.database import get_db
from src.models.database import BillingRule, DimensionCollector
from src.services.billing.formula_engine import SafeExpressionEvaluator, UnsafeExpressionError
from src.services.billing.presets import BillingPresetService, PresetApplyMode, list_preset_packs

router = APIRouter(prefix="/api/admin/billing", tags=["Admin - Billing"])
pipeline = ApiRequestPipeline()
_expr_validator = SafeExpressionEvaluator()


AllowedTaskType = Literal["chat", "video", "image", "audio"]
AllowedCollectorSourceType = Literal["request", "response", "metadata", "computed"]
AllowedValueType = Literal["float", "int", "string"]


class BillingRuleUpsertRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    task_type: AllowedTaskType = "chat"

    global_model_id: str | None = None
    model_id: str | None = None

    expression: str = Field(..., min_length=1)
    variables: dict[str, Any] = Field(default_factory=dict)
    dimension_mappings: dict[str, Any] = Field(default_factory=dict)

    is_enabled: bool = True


class BillingRuleResponse(BaseModel):
    id: str
    name: str
    task_type: str
    global_model_id: str | None
    model_id: str | None
    expression: str
    variables: dict[str, Any]
    dimension_mappings: dict[str, Any]
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_obj(cls, rule: BillingRule) -> "BillingRuleResponse":
        return cls(
            id=rule.id,
            name=rule.name,
            task_type=rule.task_type,
            global_model_id=rule.global_model_id,
            model_id=rule.model_id,
            expression=rule.expression,
            variables=rule.variables or {},
            dimension_mappings=rule.dimension_mappings or {},
            is_enabled=bool(rule.is_enabled),
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )


class DimensionCollectorUpsertRequest(BaseModel):
    api_format: str = Field(..., min_length=1, max_length=50)
    task_type: str = Field(..., min_length=1, max_length=20)
    dimension_name: str = Field(..., min_length=1, max_length=100)

    source_type: AllowedCollectorSourceType
    source_path: str | None = None
    value_type: AllowedValueType = "float"
    transform_expression: str | None = None
    default_value: str | None = None

    priority: int = 0
    is_enabled: bool = True


class DimensionCollectorResponse(BaseModel):
    id: str
    api_format: str
    task_type: str
    dimension_name: str
    source_type: str
    source_path: str | None
    value_type: str
    transform_expression: str | None
    default_value: str | None
    priority: int
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_obj(cls, c: DimensionCollector) -> "DimensionCollectorResponse":
        return cls(
            id=c.id,
            api_format=c.api_format,
            task_type=c.task_type,
            dimension_name=c.dimension_name,
            source_type=c.source_type,
            source_path=c.source_path,
            value_type=c.value_type,
            transform_expression=c.transform_expression,
            default_value=c.default_value,
            priority=int(c.priority or 0),
            is_enabled=bool(c.is_enabled),
            created_at=c.created_at,
            updated_at=c.updated_at,
        )


class BillingPresetInfoResponse(BaseModel):
    name: str
    version: str
    description: str
    collector_count: int


class ApplyBillingPresetRequest(BaseModel):
    preset: str = Field(..., min_length=1, max_length=100)
    mode: PresetApplyMode = "merge"


@router.get("/presets")
async def list_billing_presets(request: Request, db: Session = Depends(get_db)) -> Any:
    adapter = BillingPresetListAdapter()
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.post("/presets/apply")
async def apply_billing_preset(request: Request, db: Session = Depends(get_db)) -> Any:
    adapter = BillingPresetApplyAdapter()
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.get("/rules")
async def list_billing_rules(
    request: Request,
    task_type: str | None = Query(None),
    is_enabled: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Any:
    adapter = BillingRuleListAdapter(
        task_type=task_type,
        is_enabled=is_enabled,
        page=page,
        page_size=page_size,
    )
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.get("/rules/{rule_id}")
async def get_billing_rule(rule_id: str, request: Request, db: Session = Depends(get_db)) -> Any:
    adapter = BillingRuleDetailAdapter(rule_id=rule_id)
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.post("/rules")
async def create_billing_rule(request: Request, db: Session = Depends(get_db)) -> Any:
    adapter = BillingRuleCreateAdapter()
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.put("/rules/{rule_id}")
async def update_billing_rule(rule_id: str, request: Request, db: Session = Depends(get_db)) -> Any:
    adapter = BillingRuleUpdateAdapter(rule_id=rule_id)
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.get("/collectors")
async def list_dimension_collectors(
    request: Request,
    api_format: str | None = Query(None),
    task_type: str | None = Query(None),
    dimension_name: str | None = Query(None),
    is_enabled: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Any:
    adapter = DimensionCollectorListAdapter(
        api_format=api_format,
        task_type=task_type,
        dimension_name=dimension_name,
        is_enabled=is_enabled,
        page=page,
        page_size=page_size,
    )
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.get("/collectors/{collector_id}")
async def get_dimension_collector(
    collector_id: str, request: Request, db: Session = Depends(get_db)
) -> Any:
    adapter = DimensionCollectorDetailAdapter(collector_id=collector_id)
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.post("/collectors")
async def create_dimension_collector(request: Request, db: Session = Depends(get_db)) -> Any:
    adapter = DimensionCollectorCreateAdapter()
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


@router.put("/collectors/{collector_id}")
async def update_dimension_collector(
    collector_id: str, request: Request, db: Session = Depends(get_db)
) -> Any:
    adapter = DimensionCollectorUpdateAdapter(collector_id=collector_id)
    return await pipeline.run(adapter=adapter, http_request=request, db=db, mode=adapter.mode)


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------


@dataclass
class BillingRuleListAdapter(AdminApiAdapter):
    page: int
    page_size: int
    task_type: str | None = None
    is_enabled: bool | None = None

    async def handle(self, context: ApiRequestContext) -> dict[str, Any]:
        q = context.db.query(BillingRule)
        if self.task_type:
            q = q.filter(BillingRule.task_type == self.task_type.lower())
        if self.is_enabled is not None:
            q = q.filter(BillingRule.is_enabled == self.is_enabled)

        total = q.count()
        items = (
            q.order_by(BillingRule.updated_at.desc())
            .offset((self.page - 1) * self.page_size)
            .limit(self.page_size)
            .all()
        )
        return {
            "items": [BillingRuleResponse.from_orm_obj(r).model_dump() for r in items],
            "total": total,
            "page": self.page,
            "page_size": self.page_size,
            "pages": (total + self.page_size - 1) // self.page_size,
        }


@dataclass
class BillingRuleDetailAdapter(AdminApiAdapter):
    rule_id: str

    async def handle(self, context: ApiRequestContext) -> dict[str, Any]:
        rule = context.db.query(BillingRule).filter(BillingRule.id == self.rule_id).first()
        if not rule:
            raise NotFoundException("Billing rule not found")
        return BillingRuleResponse.from_orm_obj(rule).model_dump()


class BillingRuleCreateAdapter(AdminApiAdapter):
    async def handle(self, context: ApiRequestContext) -> dict[str, Any]:
        payload = context.ensure_json_body()
        try:
            req = BillingRuleUpsertRequest.model_validate(payload)
        except Exception as exc:
            raise InvalidRequestException(f"Invalid request body: {exc}")

        _validate_billing_rule_request(req)

        rule = BillingRule(
            name=req.name,
            task_type=req.task_type,
            global_model_id=req.global_model_id,
            model_id=req.model_id,
            expression=req.expression,
            variables=req.variables,
            dimension_mappings=req.dimension_mappings,
            is_enabled=req.is_enabled,
        )
        context.db.add(rule)
        try:
            context.db.commit()
        except IntegrityError as exc:
            context.db.rollback()
            raise InvalidRequestException(f"Integrity error: {exc}")

        context.db.refresh(rule)
        return BillingRuleResponse.from_orm_obj(rule).model_dump()


@dataclass
class BillingRuleUpdateAdapter(AdminApiAdapter):
    rule_id: str

    async def handle(self, context: ApiRequestContext) -> dict[str, Any]:
        rule = context.db.query(BillingRule).filter(BillingRule.id == self.rule_id).first()
        if not rule:
            raise NotFoundException("Billing rule not found")

        payload = context.ensure_json_body()
        try:
            req = BillingRuleUpsertRequest.model_validate(payload)
        except Exception as exc:
            raise InvalidRequestException(f"Invalid request body: {exc}")

        _validate_billing_rule_request(req)

        rule.name = req.name
        rule.task_type = req.task_type
        rule.global_model_id = req.global_model_id
        rule.model_id = req.model_id
        rule.expression = req.expression
        rule.variables = req.variables
        rule.dimension_mappings = req.dimension_mappings
        rule.is_enabled = req.is_enabled

        try:
            context.db.commit()
        except IntegrityError as exc:
            context.db.rollback()
            raise InvalidRequestException(f"Integrity error: {exc}")

        context.db.refresh(rule)
        return BillingRuleResponse.from_orm_obj(rule).model_dump()


@dataclass
class DimensionCollectorListAdapter(AdminApiAdapter):
    page: int
    page_size: int
    api_format: str | None = None
    task_type: str | None = None
    dimension_name: str | None = None
    is_enabled: bool | None = None

    async def handle(self, context: ApiRequestContext) -> dict[str, Any]:
        q = context.db.query(DimensionCollector)
        if self.api_format:
            q = q.filter(DimensionCollector.api_format == self.api_format.upper())
        if self.task_type:
            q = q.filter(DimensionCollector.task_type == self.task_type.lower())
        if self.dimension_name:
            q = q.filter(DimensionCollector.dimension_name == self.dimension_name)
        if self.is_enabled is not None:
            q = q.filter(DimensionCollector.is_enabled == self.is_enabled)

        total = q.count()
        items = (
            q.order_by(DimensionCollector.updated_at.desc())
            .offset((self.page - 1) * self.page_size)
            .limit(self.page_size)
            .all()
        )
        return {
            "items": [DimensionCollectorResponse.from_orm_obj(c).model_dump() for c in items],
            "total": total,
            "page": self.page,
            "page_size": self.page_size,
            "pages": (total + self.page_size - 1) // self.page_size,
        }


@dataclass
class DimensionCollectorDetailAdapter(AdminApiAdapter):
    collector_id: str

    async def handle(self, context: ApiRequestContext) -> dict[str, Any]:
        c = (
            context.db.query(DimensionCollector)
            .filter(DimensionCollector.id == self.collector_id)
            .first()
        )
        if not c:
            raise NotFoundException("Dimension collector not found")
        return DimensionCollectorResponse.from_orm_obj(c).model_dump()


class DimensionCollectorCreateAdapter(AdminApiAdapter):
    async def handle(self, context: ApiRequestContext) -> dict[str, Any]:
        payload = context.ensure_json_body()
        try:
            req = DimensionCollectorUpsertRequest.model_validate(payload)
        except Exception as exc:
            raise InvalidRequestException(f"Invalid request body: {exc}")

        _validate_dimension_collector_request(context.db, req, existing_id=None)

        c = DimensionCollector(
            api_format=req.api_format.upper(),
            task_type=req.task_type.lower(),
            dimension_name=req.dimension_name,
            source_type=req.source_type,
            source_path=req.source_path,
            value_type=req.value_type,
            transform_expression=req.transform_expression,
            default_value=req.default_value,
            priority=req.priority,
            is_enabled=req.is_enabled,
        )
        context.db.add(c)
        try:
            context.db.commit()
        except IntegrityError as exc:
            context.db.rollback()
            raise InvalidRequestException(f"Integrity error: {exc}")

        context.db.refresh(c)
        return DimensionCollectorResponse.from_orm_obj(c).model_dump()


@dataclass
class DimensionCollectorUpdateAdapter(AdminApiAdapter):
    collector_id: str

    async def handle(self, context: ApiRequestContext) -> dict[str, Any]:
        c = (
            context.db.query(DimensionCollector)
            .filter(DimensionCollector.id == self.collector_id)
            .first()
        )
        if not c:
            raise NotFoundException("Dimension collector not found")

        payload = context.ensure_json_body()
        try:
            req = DimensionCollectorUpsertRequest.model_validate(payload)
        except Exception as exc:
            raise InvalidRequestException(f"Invalid request body: {exc}")

        _validate_dimension_collector_request(context.db, req, existing_id=self.collector_id)

        c.api_format = req.api_format.upper()
        c.task_type = req.task_type.lower()
        c.dimension_name = req.dimension_name
        c.source_type = req.source_type
        c.source_path = req.source_path
        c.value_type = req.value_type
        c.transform_expression = req.transform_expression
        c.default_value = req.default_value
        c.priority = req.priority
        c.is_enabled = req.is_enabled

        try:
            context.db.commit()
        except IntegrityError as exc:
            context.db.rollback()
            raise InvalidRequestException(f"Integrity error: {exc}")

        context.db.refresh(c)
        return DimensionCollectorResponse.from_orm_obj(c).model_dump()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_billing_rule_request(req: BillingRuleUpsertRequest) -> None:
    # model/global_model 二选一
    if bool(req.global_model_id) == bool(req.model_id):
        raise InvalidRequestException("Exactly one of global_model_id or model_id must be provided")

    # task_type 校验：Pydantic Literal 已限制为 "chat", "video", "image", "audio"
    # 注：CLI 在计费域等同于 chat，billing_rules 不存储 "cli"

    # expression 安全校验
    try:
        _expr_validator.validate(req.expression)
    except UnsafeExpressionError as exc:
        raise InvalidRequestException(f"Invalid expression: {exc}")

    # variables 必须为数值（JSON 可包含 int/float）
    if not isinstance(req.variables, dict):
        raise InvalidRequestException("variables must be a JSON object")
    for k, v in req.variables.items():
        if not isinstance(k, str) or not k:
            raise InvalidRequestException("variables keys must be non-empty strings")
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise InvalidRequestException(f"variables['{k}'] must be a number")

    # dimension_mappings 结构做轻量校验（详细 schema 由业务侧保障）
    if not isinstance(req.dimension_mappings, dict):
        raise InvalidRequestException("dimension_mappings must be a JSON object")
    for var_name, mapping in req.dimension_mappings.items():
        if not isinstance(var_name, str) or not var_name:
            raise InvalidRequestException("dimension_mappings keys must be non-empty strings")
        if not isinstance(mapping, dict):
            raise InvalidRequestException(f"dimension_mappings['{var_name}'] must be an object")
        if "source" not in mapping:
            raise InvalidRequestException(f"dimension_mappings['{var_name}'].source is required")


def _validate_dimension_collector_request(
    db: Session,
    req: DimensionCollectorUpsertRequest,
    *,
    existing_id: str | None,
) -> None:
    src = req.source_type
    if src == "computed":
        if req.source_path is not None:
            raise InvalidRequestException("computed collector must have source_path=null")
        if not req.transform_expression:
            raise InvalidRequestException("computed collector must have transform_expression")
    else:
        if not req.source_path:
            raise InvalidRequestException("non-computed collector must have source_path")

    # transform_expression 安全校验（如配置）
    if req.transform_expression:
        try:
            _expr_validator.validate(req.transform_expression)
        except UnsafeExpressionError as exc:
            raise InvalidRequestException(f"Invalid transform_expression: {exc}")

    # default_value 仅允许同一维度一条（enabled=true）
    if req.default_value is not None and req.is_enabled:
        q = db.query(DimensionCollector).filter(
            DimensionCollector.api_format == req.api_format.upper(),
            DimensionCollector.task_type == req.task_type.lower(),
            DimensionCollector.dimension_name == req.dimension_name,
            DimensionCollector.is_enabled.is_(True),
            DimensionCollector.default_value.isnot(None),
        )
        if existing_id:
            q = q.filter(DimensionCollector.id != existing_id)
        exists = db.query(q.exists()).scalar()
        if exists:
            raise InvalidRequestException(
                "default_value already exists for this (api_format, task_type, dimension_name)"
            )


@dataclass
class BillingPresetListAdapter(AdminApiAdapter):
    async def handle(self, context: ApiRequestContext) -> dict[str, Any]:
        items = []
        for p in list_preset_packs():
            items.append(
                BillingPresetInfoResponse(
                    name=p.name,
                    version=p.version,
                    description=p.description,
                    collector_count=len(p.collectors or []),
                ).model_dump()
            )
        return {"items": items}


class BillingPresetApplyAdapter(AdminApiAdapter):
    async def handle(self, context: ApiRequestContext) -> dict[str, Any]:
        payload = context.ensure_json_body()
        try:
            req = ApplyBillingPresetRequest.model_validate(payload)
        except Exception as exc:
            raise InvalidRequestException(f"Invalid request body: {exc}")

        result = BillingPresetService.apply_preset(
            context.db,
            preset_name=req.preset,
            mode=req.mode,
        )
        if result.errors:
            # still return counts; caller can display partial results
            return {"ok": False, **result.to_dict()}
        return {"ok": True, **result.to_dict()}

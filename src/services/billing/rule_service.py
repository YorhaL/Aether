"""
BillingRule 查找逻辑

查找顺序（与 .plans/humming-seeking-marble.md 一致）：
1) 读取 GlobalModel/Model 价格配置 → 2) 使用代码内置计费模板生成规则（config-file mode）

注意：
- CLI 在计费域等同于 chat：billing_rules.task_type 不含 "cli"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from sqlalchemy.orm import Session

from src.config.settings import config
from src.models.database import GlobalModel, Model
from src.services.billing.cache import BillingCache
from src.services.billing.default_rules import DefaultBillingRuleGenerator, VirtualBillingRule
from src.services.billing.rule_templates import CodeBillingRuleTemplateService

TaskType = Literal["chat", "cli", "video", "image", "audio"]
BillingRuleScope = Literal["model", "global", "default"]


class BillingRuleLike(Protocol):
    id: str
    name: str
    expression: str
    variables: dict[str, Any]
    dimension_mappings: dict[str, Any]


def effective_rule_task_type(task_type: str) -> str:
    """CLI 在计费规则域里恒等于 chat。"""
    t = (task_type or "").lower()
    return "chat" if t == "cli" else t


@dataclass(frozen=True)
class BillingRuleLookupResult:
    rule: BillingRuleLike
    scope: BillingRuleScope
    effective_task_type: str


class BillingRuleService:
    @staticmethod
    def find_rule(
        db: Session,
        *,
        provider_id: str | None,
        model_name: str,
        task_type: str,
    ) -> BillingRuleLookupResult | None:
        effective_task = effective_rule_task_type(task_type)

        # Normalize provider_id for cache key to avoid duplicate entries (None vs "").
        pid = provider_id or ""
        # Cache must include runtime knobs that affect fallback behavior.
        cache_key = (
            f"{pid}:{model_name}:{effective_task}:require={int(config.billing_require_rule)}"
        )
        cached = BillingCache.get_rule(cache_key)
        if cached is not None:
            return cached

        global_model = (
            db.query(GlobalModel)
            .filter(
                GlobalModel.name == model_name,
                GlobalModel.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not global_model:
            return None

        model_obj: Model | None = None

        # Provider Model（用于覆盖价格配置）
        if provider_id:
            model_obj = (
                db.query(Model)
                .filter(
                    Model.provider_id == provider_id,
                    Model.global_model_id == global_model.id,
                    Model.is_active == True,  # noqa: E712
                )
                .first()
            )

        # Code templates (config-file mode)
        code_rule = CodeBillingRuleTemplateService.resolve_rule(
            global_model=global_model,
            model=model_obj,
            provider_id=provider_id,
            model_name=model_name,
            task_type=effective_task,
        )
        if code_rule is not None:
            result = BillingRuleLookupResult(
                rule=code_rule,
                scope="default",
                effective_task_type=effective_task,
            )
            BillingCache.set_rule(cache_key, result)
            return result

        # Runtime default rule (backward compatible)
        #
        # - Always applies to chat-domain billing (cli is normalized to chat).
        # - For video/image/audio:
        #   - When BILLING_REQUIRE_RULE=true, caller expects an explicit BillingRule (missing -> no_rule/error).
        #   - When BILLING_REQUIRE_RULE=false, fallback to default rule to preserve legacy pricing semantics
        #     (avoid silent $0 billing due to missing rule).
        if effective_task == "chat" or not config.billing_require_rule:
            default_rule = DefaultBillingRuleGenerator.generate_for_model(
                global_model=global_model,
                model=model_obj,
                task_type=effective_task,
            )
            result = BillingRuleLookupResult(
                rule=default_rule,
                scope="default",
                effective_task_type=effective_task,
            )
            BillingCache.set_rule(cache_key, result)
            return result

        return None

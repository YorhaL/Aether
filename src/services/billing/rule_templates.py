"""
Billing rule templates (config-file mode).

Goal:
- Developers define billing rules in code as templates ("模式一/二/三/四/五 ...").
- Adding a new billing template should only require adding a new `*.py` file under
  `src.services.billing.rule_defs` (no DB / no UI).

How it works:
- Each module under `rule_defs/` exports `TEMPLATES: list[CodeBillingRuleTemplate]`.
- We dynamically discover all templates at runtime and pick the best one by:
  - task_type match
  - optional match(ctx) predicate
  - highest priority wins
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Callable, Iterable

from src.models.database import GlobalModel, Model
from src.services.billing.default_rules import VirtualBillingRule


@dataclass(frozen=True)
class RuleTemplateContext:
    global_model: GlobalModel
    model: Model | None
    provider_id: str | None
    model_name: str
    task_type: str


MatchFn = Callable[[RuleTemplateContext], bool]
BuildFn = Callable[[RuleTemplateContext], VirtualBillingRule]


@dataclass(frozen=True)
class CodeBillingRuleTemplate:
    """
    A code-defined billing template.

    Notes:
    - `task_types` are billing-domain task types ("cli" is normalized to "chat" by rule_service).
    - `build()` must return a VirtualBillingRule-like object (VirtualBillingRule is used here).
    """

    name: str
    description: str
    task_types: set[str]
    priority: int = 0
    match: MatchFn | None = None
    build: BuildFn | None = None

    def supports(self, task_type: str) -> bool:
        return (task_type or "").lower() in {t.lower() for t in (self.task_types or set())}


def _iter_modules() -> Iterable[str]:
    try:
        pkg = importlib.import_module("src.services.billing.rule_defs")
        pkg_path = getattr(pkg, "__path__", None)
        if not pkg_path:
            return []
    except Exception:
        return []

    out: list[str] = []
    for mod in pkgutil.iter_modules(pkg_path):
        if mod.ispkg:
            continue
        out.append(f"src.services.billing.rule_defs.{mod.name}")
    return out


def discover_rule_templates() -> list[CodeBillingRuleTemplate]:
    templates: list[CodeBillingRuleTemplate] = []
    for mod_name in _iter_modules():
        try:
            m = importlib.import_module(mod_name)
        except Exception:
            continue
        items = getattr(m, "TEMPLATES", None)
        if not isinstance(items, list):
            continue
        for t in items:
            if isinstance(t, CodeBillingRuleTemplate):
                templates.append(t)
    # higher priority first, stable within same module import order
    templates.sort(key=lambda x: int(getattr(x, "priority", 0) or 0), reverse=True)
    return templates


class CodeBillingRuleTemplateService:
    @staticmethod
    def resolve_rule(
        *,
        global_model: GlobalModel,
        model: Model | None,
        provider_id: str | None,
        model_name: str,
        task_type: str,
    ) -> VirtualBillingRule | None:
        ctx = RuleTemplateContext(
            global_model=global_model,
            model=model,
            provider_id=provider_id,
            model_name=model_name,
            task_type=(task_type or "").lower(),
        )
        for t in discover_rule_templates():
            if not t.supports(ctx.task_type):
                continue
            if t.match is not None:
                try:
                    if not bool(t.match(ctx)):
                        continue
                except Exception:
                    continue
            if t.build is None:
                continue
            try:
                return t.build(ctx)
            except Exception:
                continue
        return None

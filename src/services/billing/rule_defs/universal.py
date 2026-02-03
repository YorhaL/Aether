"""
Universal billing template.

This is the single unified billing template for all task types.
Formula: total = (input_cost + output_cost + cache_creation_cost + cache_read_cost) + request_cost + video_cost

Each component can be 0 if not applicable for the specific task type.
"""

from __future__ import annotations

import re

from src.services.billing.default_rules import DefaultBillingRuleGenerator, VirtualBillingRule
from src.services.billing.rule_templates import CodeBillingRuleTemplate, RuleTemplateContext


def _get_nested(obj: object | None, path: str) -> object | None:
    if not isinstance(obj, dict):
        return None
    cur: object = obj
    for part in (path or "").split("."):
        if not part:
            continue
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)  # type: ignore[assignment]
    return cur


def _as_float(v: object | None) -> float | None:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        return float(v)
    except Exception:
        return None


_WXH_PATTERN = re.compile(r"^(\d+)x(\d+)$")


def _normalize_resolution_key(raw: str) -> str:
    """
    Normalize resolution key:
    - lowercase, remove spaces, × → x
    - For WxH format, sort dimensions so smaller comes first (1080x720 → 720x1080)
    """
    k = (raw or "").strip().lower().replace(" ", "").replace("×", "x")
    match = _WXH_PATTERN.match(k)
    if match:
        a, b = int(match.group(1)), int(match.group(2))
        k = f"{a}x{b}" if a <= b else f"{b}x{a}"
    return k


def _effective_unit_price(ctx: RuleTemplateContext) -> float:
    """Get video price per second from config."""
    if ctx.model is not None:
        v = _as_float(
            _get_nested(getattr(ctx.model, "config", None), "billing.video.price_per_second")
        )
        if v is not None:
            return v
    v = _as_float(
        _get_nested(getattr(ctx.global_model, "config", None), "billing.video.price_per_second")
    )
    if v is not None:
        return v
    return 0.0


def _effective_resolution_price_per_second(ctx: RuleTemplateContext) -> dict[str, float]:
    """
    Resolution (or size) -> price_per_second.
    """
    for conf in (
        getattr(ctx.model, "config", None) if ctx.model is not None else None,
        getattr(ctx.global_model, "config", None),
    ):
        raw = _get_nested(conf, "billing.video.price_per_second_by_resolution")
        if not isinstance(raw, dict):
            continue
        out: dict[str, float] = {}
        for k, v in raw.items():
            fk = _normalize_resolution_key(str(k))
            fv = _as_float(v)
            if not fk:
                continue
            if fv is None:
                continue
            out[fk] = fv
        if out:
            return out

    # Backward-compat: resolution multipliers
    base = _effective_unit_price(ctx)
    if base and base > 0:
        for conf in (
            getattr(ctx.model, "config", None) if ctx.model is not None else None,
            getattr(ctx.global_model, "config", None),
        ):
            raw = _get_nested(conf, "billing.video.resolution_multipliers")
            if not isinstance(raw, dict):
                continue
            out2: dict[str, float] = {}
            for k, v in raw.items():
                fk = _normalize_resolution_key(str(k))
                mv = _as_float(v)
                if not fk:
                    continue
                if mv is None:
                    continue
                out2[fk] = float(base) * float(mv)
            if out2:
                return out2

    return {}


def build_universal(ctx: RuleTemplateContext) -> VirtualBillingRule:
    """
    Build the universal billing rule.

    Formula:
        total = (input_cost + output_cost + cache_creation_cost + cache_read_cost) + request_cost + video_cost

    Each component defaults to 0 if not configured or not applicable.
    """
    # Base rule: token + per-request
    base = DefaultBillingRuleGenerator.generate_for_model(
        global_model=ctx.global_model,
        model=ctx.model,
        task_type=ctx.task_type,
    )

    unit_price = _effective_unit_price(ctx)
    resolution_price_map = _effective_resolution_price_per_second(ctx)

    variables = dict(base.variables or {})

    dimension_mappings = dict(base.dimension_mappings or {})

    # Video duration dimension
    dimension_mappings["duration_seconds"] = {
        "source": "dimension",
        "key": "duration_seconds",
        "required": False,
        "allow_zero": True,
        "default": 0,
    }

    # Video price per second (resolved from resolution map or fallback to unit price)
    dimension_mappings["video_price_per_second"] = {
        "source": "matrix",
        "key": "video_resolution_key",
        "required": False,
        "default": unit_price,
        "map": resolution_price_map,
    }

    # Video cost component
    dimension_mappings["video_cost"] = {
        "source": "computed",
        "required": False,
        "default": 0,
        "expression": "duration_seconds * video_price_per_second",
    }

    # Universal formula: token costs + request cost + video cost
    # base.expression = "input_cost + output_cost + cache_creation_cost + cache_read_cost + request_cost"
    expression = f"({base.expression}) + video_cost"

    return VirtualBillingRule(
        id="__default__",
        name="Universal Billing Rule",
        task_type=ctx.task_type,
        expression=expression,
        variables=variables,
        dimension_mappings=dimension_mappings,
        is_virtual=True,
    )


TEMPLATES = [
    CodeBillingRuleTemplate(
        name="universal",
        description="Universal billing: (input + output + cache) + request + video. All components default to 0 if not applicable.",
        task_types={"chat", "cli", "video", "image", "audio"},
        priority=100,  # Highest priority - used for all task types
        build=build_universal,
    )
]

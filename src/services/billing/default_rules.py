"""
Default billing rules (runtime-generated).

Goal:
- Keep backward compatibility with existing GlobalModel/Model pricing config
  (tiered_pricing + price_per_request)
- Provide a virtual BillingRule when no explicit BillingRule is configured in DB.

This module MUST NOT write to DB.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.models.database import GlobalModel, Model


@dataclass(frozen=True)
class VirtualBillingRule:
    """A rule object compatible with BillingRule fields, generated at runtime."""

    id: str
    name: str
    task_type: str
    expression: str
    variables: dict[str, Any]
    dimension_mappings: dict[str, Any]
    is_virtual: bool = True


def _as_float(value: Any, *, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        # avoid bool being treated as int
        if isinstance(value, bool):
            return default
        return float(value)
    except Exception:
        return default


def _get_tiers(tiered_pricing: dict | None) -> list[dict[str, Any]]:
    if not isinstance(tiered_pricing, dict):
        return []
    tiers = tiered_pricing.get("tiers")
    if not isinstance(tiers, list):
        return []
    return [t for t in tiers if isinstance(t, dict)]


class DefaultBillingRuleGenerator:
    """
    Build a virtual BillingRule from GlobalModel/Model pricing fields.

    Pricing sources:
    - Tiered pricing: Model.tiered_pricing overrides GlobalModel.default_tiered_pricing
    - Per-request price: Model.price_per_request overrides GlobalModel.default_price_per_request
    """

    @staticmethod
    def generate_for_model(
        *,
        global_model: GlobalModel,
        model: Model | None = None,
        task_type: str = "chat",
    ) -> VirtualBillingRule:
        tiered_pricing = (
            model.get_effective_tiered_pricing()
            if model is not None
            else global_model.default_tiered_pricing
        )
        tiers = _get_tiers(tiered_pricing)

        # Base prices (used as defaults if tier_key missing)
        first_tier = tiers[0] if tiers else {}
        base_input_price = _as_float(first_tier.get("input_price_per_1m"), default=0.0)
        base_output_price = _as_float(first_tier.get("output_price_per_1m"), default=0.0)

        # Cache prices: keep legacy behavior (derive from input price when missing)
        base_cache_creation_price = _as_float(
            first_tier.get("cache_creation_price_per_1m"),
            default=base_input_price * 1.25,
        )
        base_cache_read_price = _as_float(
            first_tier.get("cache_read_price_per_1m"),
            default=base_input_price * 0.1,
        )

        # Per-request price
        if model is not None:
            request_price = model.get_effective_price_per_request()
        else:
            request_price = global_model.default_price_per_request
        base_request_price = _as_float(request_price, default=0.0)

        # Expression uses per-1M prices and token counts.
        # v2-friendly expression: total cost is sum of component costs.
        expression = (
            "input_cost + output_cost + cache_creation_cost + cache_read_cost + request_cost"
        )

        variables: dict[str, Any] = {
            "input_price_per_1m": base_input_price,
            "output_price_per_1m": base_output_price,
            "cache_creation_price_per_1m": base_cache_creation_price,
            "cache_read_price_per_1m": base_cache_read_price,
            "price_per_request": base_request_price,
        }

        dimension_mappings: dict[str, Any] = {
            # Raw dimensions
            "input_tokens": {
                "source": "dimension",
                "key": "input_tokens",
                "required": False,
                "allow_zero": True,
                "default": 0,
            },
            "output_tokens": {
                "source": "dimension",
                "key": "output_tokens",
                "required": False,
                "allow_zero": True,
                "default": 0,
            },
            "cache_creation_tokens": {
                "source": "dimension",
                "key": "cache_creation_tokens",
                "required": False,
                "allow_zero": True,
                "default": 0,
            },
            "cache_read_tokens": {
                "source": "dimension",
                "key": "cache_read_tokens",
                "required": False,
                "allow_zero": True,
                "default": 0,
            },
            "request_count": {
                "source": "dimension",
                "key": "request_count",
                "required": False,
                "allow_zero": True,
                "default": 1,
            },
            # Component costs (computed)
            "input_cost": {
                "source": "computed",
                "expression": "input_tokens * input_price_per_1m / 1000000",
                "required": False,
                "default": 0,
            },
            "output_cost": {
                "source": "computed",
                "expression": "output_tokens * output_price_per_1m / 1000000",
                "required": False,
                "default": 0,
            },
            "cache_creation_cost": {
                "source": "computed",
                "expression": "cache_creation_tokens * cache_creation_price_per_1m / 1000000",
                "required": False,
                "default": 0,
            },
            "cache_read_cost": {
                "source": "computed",
                "expression": "cache_read_tokens * cache_read_price_per_1m / 1000000",
                "required": False,
                "default": 0,
            },
            "request_cost": {
                "source": "computed",
                "expression": "request_count * price_per_request",
                "required": False,
                "default": 0,
            },
        }

        # Tiered pricing: resolve effective prices based on total_input_context
        # (legacy definition: input_tokens + cache_read_tokens)
        if tiers:
            # Build tier lists with legacy cache fallbacks per tier.
            def _tier_value(
                t: dict[str, Any], key: str, *, default_multiplier: float | None = None
            ) -> float:
                if key in t and t.get(key) is not None:
                    return _as_float(t.get(key), default=0.0)
                if default_multiplier is not None:
                    input_price = _as_float(t.get("input_price_per_1m"), default=0.0)
                    return input_price * default_multiplier
                return 0.0

            def _tiers_for(
                key: str,
                *,
                default_multiplier: float | None = None,
                include_cache_ttl_pricing: bool = False,
            ) -> list[dict[str, Any]]:
                out: list[dict[str, Any]] = []
                for t in tiers:
                    item: dict[str, Any] = {
                        "up_to": t.get("up_to"),
                        "value": _tier_value(t, key, default_multiplier=default_multiplier),
                    }
                    if include_cache_ttl_pricing and isinstance(t.get("cache_ttl_pricing"), list):
                        # Preserve raw ttl pricing list for FormulaEngine tiered resolver.
                        item["cache_ttl_pricing"] = t.get("cache_ttl_pricing")
                    out.append(item)
                return out

            tier_key = "total_input_context"
            dimension_mappings["input_price_per_1m"] = {
                "source": "tiered",
                "tier_key": tier_key,
                "allow_zero": True,
                "tiers": _tiers_for("input_price_per_1m"),
                "default": base_input_price,
            }
            dimension_mappings["output_price_per_1m"] = {
                "source": "tiered",
                "tier_key": tier_key,
                "allow_zero": True,
                "tiers": _tiers_for("output_price_per_1m"),
                "default": base_output_price,
            }
            dimension_mappings["cache_creation_price_per_1m"] = {
                "source": "tiered",
                "tier_key": tier_key,
                "allow_zero": True,
                "tiers": _tiers_for("cache_creation_price_per_1m", default_multiplier=1.25),
                "default": base_cache_creation_price,
            }
            dimension_mappings["cache_read_price_per_1m"] = {
                "source": "tiered",
                "tier_key": tier_key,
                "allow_zero": True,
                # TTL override supported when dims include cache_ttl_minutes
                "ttl_key": "cache_ttl_minutes",
                "ttl_value_key": "cache_read_price_per_1m",
                "tiers": _tiers_for(
                    "cache_read_price_per_1m",
                    default_multiplier=0.1,
                    include_cache_ttl_pricing=True,
                ),
                "default": base_cache_read_price,
            }

        return VirtualBillingRule(
            id="__default__",
            name=f"Default rule for {getattr(global_model, 'name', 'unknown')}",
            task_type=task_type,
            expression=expression,
            variables=variables,
            dimension_mappings=dimension_mappings,
        )

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.config.settings import config
from src.core.logger import logger
from src.services.billing.dimension_collector_service import DimensionCollectorService
from src.services.billing.formula_engine import BillingIncompleteError, FormulaEngine
from src.services.billing.precision import quantize_cost, to_decimal
from src.services.billing.rule_service import BillingRuleService

from .schema import BILLING_SNAPSHOT_SCHEMA_VERSION, BillingSnapshot, CostResult


class BillingService:
    """
    BillingService (pure-ish application helper for billing domain).

    Notes:
    - This service **does not** write Usage rows.
    - It may read billing rules & collectors from DB.
    """

    # FormulaEngine is stateless and safe to share within a process.
    _shared_formula_engine: FormulaEngine | None = None

    def __init__(self, db: Session):
        self.db = db
        self._formula_engine = self._get_formula_engine()
        # Lazy-init: most call sites already provide dimensions (hot path).
        self._dimension_collector: DimensionCollectorService | None = None

    @classmethod
    def _get_formula_engine(cls) -> FormulaEngine:
        if cls._shared_formula_engine is None:
            cls._shared_formula_engine = FormulaEngine()
        return cls._shared_formula_engine

    def _get_dimension_collector(self) -> DimensionCollectorService:
        if self._dimension_collector is None:
            self._dimension_collector = DimensionCollectorService(self.db)
        return self._dimension_collector

    def collect_dimensions(
        self,
        *,
        api_format: str | None,
        task_type: str | None,
        request: dict[str, Any] | None = None,
        response: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        base_dimensions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._get_dimension_collector().collect_dimensions(
            api_format=api_format,
            task_type=task_type,
            request=request,
            response=response,
            metadata=metadata,
            base_dimensions=base_dimensions,
        )

    def calculate(
        self,
        *,
        task_type: str,
        model: str,
        provider_id: str,
        dimensions: dict[str, Any],
        strict_mode: bool | None = None,
    ) -> CostResult:
        """
        Calculate cost for a task.

        Returns:
            CostResult (includes BillingSnapshot)

        Raises:
            BillingIncompleteError: when strict_mode=True and required dims missing.
        """
        strict = config.billing_strict_mode if strict_mode is None else bool(strict_mode)

        # Normalize & enrich dimensions (do not mutate caller dict)
        dims: dict[str, Any] = dict(dimensions or {})

        # Compatibility aliases (legacy fields in some call sites)
        if "cache_creation_tokens" not in dims and "cache_creation_input_tokens" in dims:
            dims["cache_creation_tokens"] = dims.get("cache_creation_input_tokens")
        if "cache_read_tokens" not in dims and "cache_read_input_tokens" in dims:
            dims["cache_read_tokens"] = dims.get("cache_read_input_tokens")

        # Default request_count=1 for per-request billing
        if "request_count" not in dims:
            dims["request_count"] = 1

        # total_input_context is the tier-key for legacy tiered pricing:
        # default: input_tokens + cache_creation_tokens + cache_read_tokens
        #
        # NOTE:
        # Some adapters (e.g. Claude) include cache_creation tokens in the tier context.
        # Making this the default avoids per-callsite inconsistency.
        if "total_input_context" not in dims:
            try:
                input_tokens_i = int(float(dims.get("input_tokens") or 0))
            except Exception:
                input_tokens_i = 0
            try:
                cache_creation_tokens_i = int(float(dims.get("cache_creation_tokens") or 0))
            except Exception:
                cache_creation_tokens_i = 0
            try:
                cache_read_tokens_i = int(float(dims.get("cache_read_tokens") or 0))
            except Exception:
                cache_read_tokens_i = 0
            dims["total_input_context"] = (
                input_tokens_i + cache_creation_tokens_i + cache_read_tokens_i
            )

        lookup = BillingRuleService.find_rule(
            self.db,
            provider_id=provider_id,
            model_name=model,
            task_type=task_type,
        )

        if lookup and lookup.rule and lookup.rule.expression:
            rule = lookup.rule
            result = self._formula_engine.evaluate(
                expression=rule.expression,
                variables=rule.variables or {},
                dimensions=dims,
                dimension_mappings=rule.dimension_mappings or {},
                strict_mode=strict,
            )
            # ------------------------------------------------------------
            # Quantize: component costs first, then total = sum(components)
            # ------------------------------------------------------------
            breakdown_dec: dict[str, Decimal] = {
                k: to_decimal(v) for k, v in (result.cost_breakdown or {}).items()
            }

            breakdown_quantized: dict[str, Decimal] = {
                k: quantize_cost(v) for k, v in breakdown_dec.items()
            }
            total_dec = (
                quantize_cost(sum(breakdown_quantized.values(), Decimal("0")))
                if breakdown_quantized
                else quantize_cost(to_decimal(result.cost))
            )

            cost_breakdown = {k: float(v) for k, v in breakdown_quantized.items()}
            total_cost = float(total_dec) if result.status == "complete" else 0.0

            # Filter resolved_variables for JSON safety + semantics clarity:
            # - remove dims (they live in resolved_dimensions)
            # - remove *_cost (they live in cost_breakdown)
            resolved_vars: dict[str, Any] = {}
            for k, v in (result.resolved_variables or {}).items():
                if k in (result.resolved_dimensions or {}):
                    continue
                if k.endswith("_cost"):
                    continue
                if isinstance(v, Decimal):
                    resolved_vars[k] = str(v)
                else:
                    resolved_vars[k] = v

            snapshot = BillingSnapshot(
                schema_version=BILLING_SNAPSHOT_SCHEMA_VERSION,
                rule_id=str(rule.id),
                rule_name=str(rule.name),
                scope=str(getattr(lookup, "scope", None) or ""),
                expression=str(rule.expression),
                resolved_dimensions=result.resolved_dimensions or dims,
                resolved_variables=resolved_vars,
                cost_breakdown=cost_breakdown,
                total_cost=total_cost,
                tier_index=result.tier_index,
                tier_info=result.tier_info,
                missing_required=result.missing_required,
                status=result.status,
                calculated_at=datetime.now(timezone.utc).isoformat(),
            )
            return CostResult(cost=total_cost, status=result.status, snapshot=snapshot)

        logger.warning(
            "No billing rule for task (task_type={}, model={}, provider_id={})",
            task_type,
            model,
            provider_id,
        )
        snapshot = BillingSnapshot(
            schema_version=BILLING_SNAPSHOT_SCHEMA_VERSION,
            rule_id=None,
            rule_name=None,
            scope=None,
            expression=None,
            resolved_dimensions=dims,
            resolved_variables={},
            cost_breakdown={},
            total_cost=0.0,
            missing_required=[],
            status="no_rule",
            calculated_at=datetime.now(timezone.utc).isoformat(),
        )
        return CostResult(cost=0.0, status="no_rule", snapshot=snapshot)

    def calculate_from_response(
        self,
        *,
        task_type: str,
        model: str,
        provider_id: str,
        api_format: str | None,
        request: dict[str, Any] | None = None,
        response: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        base_dimensions: dict[str, Any] | None = None,
        strict_mode: bool | None = None,
    ) -> CostResult:
        """
        Convenience wrapper:
        - collect dimensions from request/response/metadata
        - run billing calculation
        """
        dimensions = self.collect_dimensions(
            api_format=api_format,
            task_type=task_type,
            request=request,
            response=response,
            metadata=metadata,
            base_dimensions=base_dimensions,
        )
        return self.calculate(
            task_type=task_type,
            model=model,
            provider_id=provider_id,
            dimensions=dimensions,
            strict_mode=strict_mode,
        )

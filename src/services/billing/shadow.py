"""
Shadow billing (reconciliation period).

This module runs the new billing engine alongside the legacy billing outcome.
Truth vs Shadow is kept strictly separated:
- truth_breakdown: the values written into Usage rows (the "billable truth")
- shadow_snapshot: new engine snapshot stored only in request_metadata.billing_shadow

Runtime switch:
- config.billing_engine: legacy | shadow | new_with_fallback | new
- config.billing_engine_overrides: JSON mapping of "provider/model" patterns -> mode
"""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from sqlalchemy.orm import Session

from src.config.settings import config
from src.core.logger import logger
from src.core.metrics import (
    billing_diff_exceeds_threshold_total,
    billing_fallback_total,
    billing_invariant_violation_total,
    billing_requests_total,
)
from src.services.billing.schema import BillingSnapshot
from src.services.billing.service import BillingService

EngineMode = Literal["legacy", "shadow", "new_with_fallback", "new"]
TruthEngine = Literal["legacy", "new"]


@lru_cache(maxsize=32)
def _compile_engine_overrides(overrides_raw: str) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """
    Parse and normalize engine overrides.

    Cached to avoid json.loads + dict walk on every request.
    """
    try:
        overrides = json.loads(overrides_raw or "{}")
    except Exception:
        overrides = {}

    exact: dict[str, str] = {}
    patterns: list[tuple[str, str]] = []

    if isinstance(overrides, dict):
        for pattern, mode in overrides.items():
            p = str(pattern)
            m = str(mode).strip().lower()
            # fnmatch supports *, ?, and [] character classes.
            if any(ch in p for ch in ("*", "?", "[")):
                patterns.append((p, m))
            else:
                exact[p] = m

    return exact, patterns


@lru_cache(maxsize=4096)
def _resolve_engine_mode_cached(key: str, base_mode: str, overrides_raw: str) -> str:
    exact, patterns = _compile_engine_overrides(overrides_raw)
    if key in exact:
        return exact[key]
    for pattern, mode in patterns:
        try:
            if fnmatch.fnmatch(key, pattern):
                return mode
        except Exception:
            continue
    return base_mode


def resolve_engine_mode(provider: str, model: str) -> EngineMode:
    """Resolve engine mode with overrides (pure function, no DB)."""
    base_mode = (config.billing_engine or "legacy").strip().lower()
    overrides_raw = getattr(config, "billing_engine_overrides", "{}") or "{}"

    key = f"{provider}/{model}"
    return _resolve_engine_mode_cached(key, base_mode, overrides_raw)  # type: ignore[return-value]


@dataclass(frozen=True)
class CostBreakdown:
    """Cost breakdown written into Usage rows (truth)."""

    input_cost: float
    output_cost: float
    cache_creation_cost: float
    cache_read_cost: float
    request_cost: float
    total_cost: float

    @property
    def cache_cost(self) -> float:
        return float(self.cache_creation_cost) + float(self.cache_read_cost)

    def validate(self) -> bool:
        """
        Invariant: total_cost == sum(components) (within tiny tolerance).

        For new engine we quantize and sum components deterministically, so this should be exact.
        For legacy floats, we allow a tiny epsilon.
        """
        computed_total = (
            float(self.input_cost)
            + float(self.output_cost)
            + float(self.cache_creation_cost)
            + float(self.cache_read_cost)
            + float(self.request_cost)
        )
        return abs(computed_total - float(self.total_cost)) < 1e-8


@dataclass(frozen=True)
class ShadowBillingResult:
    # billable truth (written to Usage table)
    truth_breakdown: CostBreakdown
    # shadow snapshot (written to request_metadata.billing_shadow only)
    shadow_snapshot: BillingSnapshot | None
    # reconciliation information (diffs etc.)
    comparison: dict[str, Any]

    # policy vs actual
    engine_mode: EngineMode = "legacy"
    truth_engine: TruthEngine = "legacy"
    was_fallback: bool = False


class ShadowBillingService:
    """
    Shadow billing orchestrator.

    This service does NOT write DB rows. Callers decide how to persist truth and shadow data.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        # Lazy init: many call sites only need resolve_engine_mode(), and legacy mode
        # should not pay the cost of constructing BillingService.
        self._new_billing: BillingService | None = None

    def _get_new_billing(self) -> BillingService:
        if self._new_billing is None:
            self._new_billing = BillingService(self.db)
        return self._new_billing

    def get_engine_mode(self, provider: str, model: str) -> EngineMode:
        return resolve_engine_mode(provider, model)

    def calculate_with_shadow(
        self,
        *,
        provider: str,
        provider_id: str | None,
        model: str,
        task_type: str,
        api_format: str | None,
        input_tokens: int,
        output_tokens: int,
        cache_creation_input_tokens: int = 0,
        cache_read_input_tokens: int = 0,
        cache_ttl_minutes: int | None = None,
        legacy_truth: CostBreakdown,
        is_failed_request: bool,
    ) -> ShadowBillingResult:
        """
        Compute shadow billing outcome given the legacy truth.

        Notes:
        - When engine_mode is legacy, we skip new engine calculation.
        - When engine_mode is shadow, we compute new engine snapshot and compare, but keep truth legacy.
        - new/new_with_fallback are supported for later phases; callers can choose to honor truth_engine.
        """
        engine_mode = resolve_engine_mode(provider, model)

        # Default response (legacy only)
        if engine_mode == "legacy":
            billing_requests_total.labels(engine_mode=engine_mode, truth_engine="legacy").inc()
            return ShadowBillingResult(
                truth_breakdown=legacy_truth,
                shadow_snapshot=None,
                comparison={"engine_mode": engine_mode},
                engine_mode=engine_mode,
                truth_engine="legacy",
                was_fallback=False,
            )

        # Build dimensions for new engine
        request_count = 0 if is_failed_request else 1
        dimensions: dict[str, Any] = {
            "input_tokens": int(input_tokens or 0),
            "output_tokens": int(output_tokens or 0),
            "cache_creation_input_tokens": int(cache_creation_input_tokens or 0),
            "cache_read_input_tokens": int(cache_read_input_tokens or 0),
            "request_count": int(request_count),
        }
        if cache_ttl_minutes is not None:
            dimensions["cache_ttl_minutes"] = int(cache_ttl_minutes)

        # Normalize task_type
        tt = (task_type or "").lower()
        if tt not in {"chat", "cli", "video", "image", "audio"}:
            tt = "chat"

        new_result = self._get_new_billing().calculate(
            task_type=tt,
            model=model,
            provider_id=provider_id or "",
            dimensions=dimensions,
            strict_mode=None,
        )
        shadow_snapshot = new_result.snapshot

        new_breakdown = CostBreakdown(
            input_cost=float(shadow_snapshot.cost_breakdown.get("input_cost", 0.0)),
            output_cost=float(shadow_snapshot.cost_breakdown.get("output_cost", 0.0)),
            cache_creation_cost=float(
                shadow_snapshot.cost_breakdown.get("cache_creation_cost", 0.0)
            ),
            cache_read_cost=float(shadow_snapshot.cost_breakdown.get("cache_read_cost", 0.0)),
            request_cost=float(shadow_snapshot.cost_breakdown.get("request_cost", 0.0)),
            total_cost=float(shadow_snapshot.total_cost),
        )

        diff = abs(float(new_breakdown.total_cost) - float(legacy_truth.total_cost))
        diff_pct = (
            (diff / float(legacy_truth.total_cost) * 100.0) if legacy_truth.total_cost > 0 else 0.0
        )

        comparison = {
            "engine_mode": engine_mode,
            "old_total": legacy_truth.total_cost,
            "new_total": new_breakdown.total_cost,
            "diff_usd": diff,
            "diff_pct": diff_pct,
            "breakdown_diff": {
                "input_cost": new_breakdown.input_cost - legacy_truth.input_cost,
                "output_cost": new_breakdown.output_cost - legacy_truth.output_cost,
                "cache_creation_cost": new_breakdown.cache_creation_cost
                - legacy_truth.cache_creation_cost,
                "cache_read_cost": new_breakdown.cache_read_cost - legacy_truth.cache_read_cost,
                "request_cost": new_breakdown.request_cost - legacy_truth.request_cost,
            },
        }

        # Diff logging / metrics
        threshold = float(getattr(config, "billing_diff_threshold_usd", 0.0001) or 0.0001)
        if diff > threshold:
            billing_diff_exceeds_threshold_total.labels(engine_mode=engine_mode).inc()
            log_level = (
                (getattr(config, "billing_shadow_log_level", "INFO") or "INFO").strip().lower()
            )
            log_fn = getattr(logger, log_level, logger.info)
            log_fn(
                "Billing diff detected: provider={}, model={}, old={:.8f}, new={:.8f}, diff={:.8f} ({:.4f}%), mode={}",
                provider,
                model,
                legacy_truth.total_cost,
                new_breakdown.total_cost,
                diff,
                diff_pct,
                engine_mode,
            )

        # Invariant monitoring (should be 0)
        truth_engine: TruthEngine = "legacy"
        was_fallback = False

        if engine_mode == "shadow":
            truth_engine = "legacy"
            truth = legacy_truth
        elif engine_mode == "new":
            truth_engine = "new"
            truth = new_breakdown
        elif engine_mode == "new_with_fallback":
            # new is truth unless diff is too large
            fallback_threshold = threshold * 10.0
            if diff > fallback_threshold:
                truth_engine = "legacy"
                truth = legacy_truth
                was_fallback = True
                billing_fallback_total.inc()
            else:
                truth_engine = "new"
                truth = new_breakdown
        else:
            # Unknown value -> behave like legacy
            truth_engine = "legacy"
            truth = legacy_truth

        billing_requests_total.labels(engine_mode=engine_mode, truth_engine=truth_engine).inc()

        if not truth.validate():
            billing_invariant_violation_total.labels(
                engine_mode=engine_mode, truth_engine=truth_engine
            ).inc()
            logger.warning(
                "Billing invariant violation: provider={}, model={}, engine_mode={}, truth_engine={}, truth_total={}",
                provider,
                model,
                engine_mode,
                truth_engine,
                truth.total_cost,
            )

        return ShadowBillingResult(
            truth_breakdown=truth,
            shadow_snapshot=(
                shadow_snapshot if engine_mode in {"shadow", "new_with_fallback", "new"} else None
            ),
            comparison=comparison,
            engine_mode=engine_mode,
            truth_engine=truth_engine,
            was_fallback=was_fallback,
        )

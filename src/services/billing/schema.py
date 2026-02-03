"""
Billing schema (stable contracts)

These dataclasses are meant to be stored in `Usage.request_metadata` / `Task.request_metadata`
for auditability. They are internal-only and MUST NOT be exposed to end users without sanitizing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

BILLING_SNAPSHOT_SCHEMA_VERSION = "2.0"

BillingSnapshotStatus = Literal["complete", "incomplete", "no_rule", "legacy"]


@dataclass(frozen=True)
class BillingSnapshot:
    """
    Stable billing snapshot for audit.

    v2.0 semantics:
    - resolved_dimensions: final dimension values used (tokens, request_count, etc.)
    - resolved_variables: final variables used (prices, tier-resolved values, etc.)
    - cost_breakdown: itemized costs (quantized)
    - total_cost: quantized total cost (equals sum(cost_breakdown) when breakdown present)

    Backward compatibility:
    - dimensions_used aliases resolved_dimensions
    - cost aliases total_cost
    """

    schema_version: str = BILLING_SNAPSHOT_SCHEMA_VERSION

    # Rule info (optional for legacy/no_rule)
    rule_id: str | None = None
    rule_name: str | None = None
    scope: str | None = None

    # Rule expression (internal, do not expose to clients)
    expression: str | None = None

    # v2: resolved inputs
    resolved_dimensions: dict[str, Any] = field(default_factory=dict)
    resolved_variables: dict[str, Any] = field(default_factory=dict)

    # v2: breakdown and totals
    cost_breakdown: dict[str, float] = field(default_factory=dict)
    total_cost: float = 0.0

    # Tier info (optional)
    tier_index: int | None = None
    tier_info: dict[str, Any] | None = None

    # Missing dims
    missing_required: list[str] = field(default_factory=list)

    # Result status
    status: BillingSnapshotStatus = "no_rule"

    # Audit
    calculated_at: str = ""  # ISO 8601
    engine_version: str = "2.0"

    # ---------------------------------------------------------------------
    # Backward-compatible aliases (v1 fields)
    # ---------------------------------------------------------------------
    @property
    def dimensions_used(self) -> dict[str, Any]:
        return self.resolved_dimensions

    @property
    def cost(self) -> float:
        return self.total_cost

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize snapshot.

        Includes both v2 keys and v1-compatible keys for safer rollouts.
        """
        return {
            "schema_version": self.schema_version,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "scope": self.scope,
            "expression": self.expression,
            # v2
            "resolved_dimensions": self.resolved_dimensions,
            "resolved_variables": self.resolved_variables,
            "cost_breakdown": self.cost_breakdown,
            "total_cost": self.total_cost,
            "tier_index": self.tier_index,
            "tier_info": self.tier_info,
            "missing_required": self.missing_required,
            "status": self.status,
            "calculated_at": self.calculated_at,
            "engine_version": self.engine_version,
            # v1 compat
            "dimensions_used": self.resolved_dimensions,
            "cost": self.total_cost,
        }


@dataclass(frozen=True)
class CostResult:
    """Billing calculation output."""

    cost: float
    status: BillingSnapshotStatus
    snapshot: BillingSnapshot

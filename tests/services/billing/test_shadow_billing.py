from unittest.mock import MagicMock

import pytest

from src.config.settings import config
from src.services.billing.schema import BillingSnapshot, CostResult
from src.services.billing.shadow import CostBreakdown, ShadowBillingService


class TestShadowBillingServiceModeResolution:
    def test_get_engine_mode_exact_and_wildcard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config, "billing_engine", "legacy", raising=False)
        monkeypatch.setattr(
            config,
            "billing_engine_overrides",
            '{"anthropic/*": "shadow", "openai/gpt-4o": "new"}',
            raising=False,
        )

        svc = ShadowBillingService(MagicMock())
        assert svc.get_engine_mode("openai", "gpt-4o") == "new"
        assert svc.get_engine_mode("anthropic", "claude-3-5-sonnet") == "shadow"
        assert svc.get_engine_mode("other", "x") == "legacy"


class TestShadowBillingServiceExecution:
    def test_legacy_mode_skips_new_engine(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config, "billing_engine", "legacy", raising=False)
        monkeypatch.setattr(config, "billing_engine_overrides", "{}", raising=False)

        svc = ShadowBillingService(MagicMock())
        # Guard: if new engine calculate gets called, fail.
        svc._new_billing = MagicMock()
        svc._new_billing.calculate.side_effect = AssertionError(
            "new engine should not run in legacy mode"
        )

        legacy_truth = CostBreakdown(
            input_cost=0.1,
            output_cost=0.2,
            cache_creation_cost=0.0,
            cache_read_cost=0.0,
            request_cost=0.0,
            total_cost=0.3,
        )

        res = svc.calculate_with_shadow(
            provider="openai",
            provider_id="p-1",
            model="gpt-4o",
            task_type="chat",
            api_format="openai:chat",
            input_tokens=1,
            output_tokens=1,
            legacy_truth=legacy_truth,
            is_failed_request=False,
        )

        assert res.engine_mode == "legacy"
        assert res.truth_engine == "legacy"
        assert res.shadow_snapshot is None
        assert res.truth_breakdown.total_cost == 0.3

    def test_shadow_mode_returns_snapshot_and_keeps_legacy_truth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config, "billing_engine", "shadow", raising=False)
        monkeypatch.setattr(config, "billing_engine_overrides", "{}", raising=False)
        monkeypatch.setattr(config, "billing_diff_threshold_usd", 0.0001, raising=False)

        svc = ShadowBillingService(MagicMock())

        # Stub new engine output
        snapshot = BillingSnapshot(
            resolved_dimensions={"input_tokens": 1},
            resolved_variables={"input_price_per_1m": "3.0"},
            cost_breakdown={"input_cost": 0.003},
            total_cost=0.003,
            status="complete",
            calculated_at="2026-02-02T00:00:00Z",
        )
        svc._new_billing = MagicMock()
        svc._new_billing.calculate.return_value = CostResult(
            cost=0.003, status="complete", snapshot=snapshot
        )

        legacy_truth = CostBreakdown(
            input_cost=0.004,
            output_cost=0.0,
            cache_creation_cost=0.0,
            cache_read_cost=0.0,
            request_cost=0.0,
            total_cost=0.004,
        )

        res = svc.calculate_with_shadow(
            provider="openai",
            provider_id="p-1",
            model="gpt-4o",
            task_type="chat",
            api_format="openai:chat",
            input_tokens=1,
            output_tokens=0,
            legacy_truth=legacy_truth,
            is_failed_request=False,
        )

        assert res.engine_mode == "shadow"
        assert res.truth_engine == "legacy"
        assert res.shadow_snapshot is not None
        assert res.truth_breakdown.total_cost == 0.004
        assert "diff_usd" in res.comparison

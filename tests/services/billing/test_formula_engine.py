import pytest

from src.services.billing.formula_engine import (
    BillingIncompleteError,
    FormulaEngine,
    UnsafeExpressionError,
)


class TestSafeExpression:
    def test_reject_attribute_access(self) -> None:
        engine = FormulaEngine()
        with pytest.raises(UnsafeExpressionError):
            engine.evaluate(
                expression="(1).__class__",
                variables={},
                dimensions={},
                dimension_mappings={},
                strict_mode=True,  # 确保抛出异常，便于断言类型
            )

    def test_reject_import(self) -> None:
        engine = FormulaEngine()
        with pytest.raises(UnsafeExpressionError):
            engine.evaluate(
                expression="__import__('os').system('echo hacked')",
                variables={},
                dimensions={},
                dimension_mappings={},
                strict_mode=True,
            )


class TestFormulaEngine:
    def test_basic_video_formula(self) -> None:
        engine = FormulaEngine()
        result = engine.evaluate(
            expression="(base_price + duration_seconds * price_per_second) * resolution_multiplier",
            variables={"base_price": 0.05, "price_per_second": 0.02},
            dimensions={"duration_seconds": 10, "resolution": "720p"},
            dimension_mappings={
                "duration_seconds": {
                    "source": "dimension",
                    "key": "duration_seconds",
                    "required": True,
                },
                "resolution_multiplier": {
                    "source": "matrix",
                    "key": "resolution",
                    "map": {"720p": 1.0, "1080p": 1.5},
                    "default": 1.0,
                },
            },
        )
        assert result.status == "complete"
        assert result.missing_required == []
        assert abs(float(result.cost) - 0.25) < 1e-9

    def test_required_dimension_missing_non_strict(self) -> None:
        engine = FormulaEngine()
        result = engine.evaluate(
            expression="base_price + duration_seconds * price_per_second",
            variables={"base_price": 0.05, "price_per_second": 0.02},
            dimensions={"duration_seconds": None},
            dimension_mappings={
                "duration_seconds": {
                    "source": "dimension",
                    "key": "duration_seconds",
                    "required": True,
                },
            },
            strict_mode=False,
        )
        assert result.status == "incomplete"
        assert float(result.cost) == 0.0
        assert result.missing_required == ["duration_seconds"]

    def test_required_dimension_missing_strict_raises(self) -> None:
        engine = FormulaEngine()
        with pytest.raises(BillingIncompleteError) as exc:
            engine.evaluate(
                expression="base_price + duration_seconds * price_per_second",
                variables={"base_price": 0.05, "price_per_second": 0.02},
                dimensions={"duration_seconds": None},
                dimension_mappings={
                    "duration_seconds": {
                        "source": "dimension",
                        "key": "duration_seconds",
                        "required": True,
                    },
                },
                strict_mode=True,
            )
        assert exc.value.missing_required == ["duration_seconds"]

    def test_allow_zero(self) -> None:
        engine = FormulaEngine()

        # allow_zero=false（默认）：0 视为缺失
        result = engine.evaluate(
            expression="duration_seconds * 1",
            variables={},
            dimensions={"duration_seconds": 0},
            dimension_mappings={
                "duration_seconds": {
                    "source": "dimension",
                    "key": "duration_seconds",
                    "required": True,
                },
            },
        )
        assert result.status == "incomplete"
        assert result.missing_required == ["duration_seconds"]

        # allow_zero=true：0 合法
        result = engine.evaluate(
            expression="duration_seconds * 1",
            variables={},
            dimensions={"duration_seconds": 0},
            dimension_mappings={
                "duration_seconds": {
                    "source": "dimension",
                    "key": "duration_seconds",
                    "required": True,
                    "allow_zero": True,
                },
            },
        )
        assert result.status == "complete"
        assert float(result.cost) == 0.0

    def test_tiered_mapping(self) -> None:
        engine = FormulaEngine()

        result = engine.evaluate(
            expression="input_price",
            variables={},
            dimensions={"total_input_tokens": 100_000},
            dimension_mappings={
                "input_price": {
                    "source": "tiered",
                    "tier_key": "total_input_tokens",
                    "tiers": [
                        {"up_to": 128_000, "value": 3.0},
                        {"up_to": None, "value": 1.5},
                    ],
                }
            },
        )
        assert result.status == "complete"
        assert float(result.cost) == 3.0

        result = engine.evaluate(
            expression="input_price",
            variables={},
            dimensions={"total_input_tokens": 200_000},
            dimension_mappings={
                "input_price": {
                    "source": "tiered",
                    "tier_key": "total_input_tokens",
                    "tiers": [
                        {"up_to": 128_000, "value": 3.0},
                        {"up_to": None, "value": 1.5},
                    ],
                }
            },
        )
        assert result.status == "complete"
        assert float(result.cost) == 1.5

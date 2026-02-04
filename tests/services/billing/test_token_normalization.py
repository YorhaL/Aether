from src.services.billing.token_normalization import normalize_input_tokens_for_billing
from src.services.billing.usage_mapper import UsageMapper


class TestNormalizeInputTokensForBilling:
    def test_openai_family_subtracts_cached_tokens(self) -> None:
        assert normalize_input_tokens_for_billing("openai:cli", 160_070, 81_664) == 78_406

    def test_claude_family_does_not_change(self) -> None:
        assert normalize_input_tokens_for_billing("claude:cli", 160_070, 81_664) == 160_070

    def test_missing_format_does_not_change(self) -> None:
        assert normalize_input_tokens_for_billing(None, 100, 20) == 100
        assert normalize_input_tokens_for_billing("", 100, 20) == 100

    def test_clamps_when_cached_tokens_exceed_input(self) -> None:
        assert normalize_input_tokens_for_billing("openai:cli", 10, 20) == 0


class TestUsageMapperOpenAICacheTokens:
    def test_openai_mapping_maps_cached_tokens_details(self) -> None:
        raw_usage = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "prompt_tokens_details": {"cached_tokens": 20},
        }

        usage = UsageMapper.map(raw_usage, api_format="openai:chat")
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.cache_read_tokens == 20

    def test_openai_mapping_without_cached_tokens_is_unchanged(self) -> None:
        raw_usage = {"prompt_tokens": 100, "completion_tokens": 50}
        usage = UsageMapper.map(raw_usage, api_format="openai:chat")
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.cache_read_tokens == 0

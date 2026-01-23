from src.core.model_permissions import check_model_allowed_with_mappings


class TestCheckModelAllowedWithMappings:
    def test_exact_match_returns_allowed_without_mapping(self) -> None:
        is_allowed, matched = check_model_allowed_with_mappings(
            model_name="gpt-4o",
            allowed_models=["gpt-4o"],
            model_mappings=[r"gpt-4o-.*"],
        )
        assert is_allowed is True
        assert matched is None

    def test_mapping_match_is_deterministic(self) -> None:
        is_allowed, matched = check_model_allowed_with_mappings(
            model_name="target",
            allowed_models=["b", "a"],
            model_mappings=[r".*"],
        )
        assert is_allowed is True
        assert matched == "a"

    def test_mapping_match_with_candidate_intersection(self) -> None:
        """当 candidate_models 和 allowed_models 有交集时，应优先返回交集中的模型"""
        is_allowed, matched = check_model_allowed_with_mappings(
            model_name="target",
            allowed_models=["other-1", "allowed-1"],
            model_mappings=[r".*-1"],
            candidate_models={"allowed-1"},
        )
        assert is_allowed is True
        # 交集精确匹配优先于正则匹配
        assert matched == "allowed-1"

    def test_mapping_match_without_candidate_intersection(self) -> None:
        """当 candidate_models 和 allowed_models 没有交集时，应继续尝试正则匹配"""
        is_allowed, matched = check_model_allowed_with_mappings(
            model_name="target",
            allowed_models=["allowed-1"],
            model_mappings=[r".*-1"],
            candidate_models={"not-present"},
        )
        # 正则匹配应该成功，因为 allowed-1 匹配 .*-1
        assert is_allowed is True
        assert matched == "allowed-1"

    def test_mapping_match_no_regex_match(self) -> None:
        """当正则不匹配 allowed_models 时，应返回 False"""
        is_allowed, matched = check_model_allowed_with_mappings(
            model_name="target",
            allowed_models=["allowed-2"],
            model_mappings=[r"other-.*"],
            candidate_models={"not-present"},
        )
        # 正则 other-.* 不匹配 allowed-2
        assert is_allowed is False
        assert matched is None

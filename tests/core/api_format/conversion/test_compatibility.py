"""
is_format_compatible 单元测试

覆盖：
- 同格式透传
- CLI 格式允许转换（按 registry 能力）
- 全局开关/端点开关/白黑名单
- 流式转换开关
- 转换器能力校验
"""

from unittest.mock import MagicMock

from src.core.api_format.conversion.compatibility import is_format_compatible


def test_same_format_is_compatible() -> None:
    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "claude:chat",
        endpoint_format_acceptance_config=None,
        is_stream=False,
        global_conversion_enabled=False,
        registry=MagicMock(),
    )
    assert ok is True
    assert needs_conv is False
    assert reason is None


def test_cli_format_convertible_when_converter_supports_full() -> None:
    registry = MagicMock()
    registry.can_convert_full.return_value = True

    ok, needs_conv, reason = is_format_compatible(
        "claude:cli",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True},
        is_stream=False,
        global_conversion_enabled=True,
        registry=registry,
    )
    assert ok is True
    assert needs_conv is True
    assert reason is None


def test_global_switch_disabled_blocks_conversion() -> None:
    """全局开关关闭时（环境变量 FORMAT_CONVERSION_ENABLED=false）阻止转换"""
    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True},
        is_stream=False,
        global_conversion_enabled=False,
        registry=MagicMock(),
    )
    assert ok is False
    assert needs_conv is False
    assert reason and ("全局" in reason or "FORMAT_CONVERSION_ENABLED" in reason)


def test_endpoint_config_none_blocks_conversion() -> None:
    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "openai:chat",
        endpoint_format_acceptance_config=None,
        is_stream=False,
        global_conversion_enabled=True,
        registry=MagicMock(),
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "未配置" in reason


def test_endpoint_disabled_blocks_conversion() -> None:
    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": False},
        is_stream=False,
        global_conversion_enabled=True,
        registry=MagicMock(),
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "未启用" in reason


def test_accept_formats_allows_only_whitelist() -> None:
    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True, "accept_formats": ["openai:chat"]},
        is_stream=False,
        global_conversion_enabled=True,
        registry=MagicMock(),
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "不接受" in reason


def test_reject_formats_blocks_blacklist() -> None:
    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True, "reject_formats": ["claude:chat"]},
        is_stream=False,
        global_conversion_enabled=True,
        registry=MagicMock(),
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "拒绝" in reason


def test_stream_conversion_disabled_blocks_stream() -> None:
    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True, "stream_conversion": False},
        is_stream=True,
        global_conversion_enabled=True,
        registry=MagicMock(),
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "流式" in reason


def test_converter_support_required() -> None:
    registry = MagicMock()
    registry.can_convert_full.return_value = False

    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True},
        is_stream=False,
        global_conversion_enabled=True,
        registry=registry,
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "转换器" in reason


def test_conversion_allowed_when_converter_supports_full() -> None:
    registry = MagicMock()
    registry.can_convert_full.return_value = True

    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True, "accept_formats": ["claude:chat"]},
        is_stream=False,
        global_conversion_enabled=True,
        registry=registry,
    )
    assert ok is True
    assert needs_conv is True
    assert reason is None


# ==================== 同族格式测试 ====================


def test_claude_cli_to_claude_no_conversion_needed() -> None:
    """CLAUDE 和 CLAUDE_CLI 格式相同，只是认证不同，可透传（需开关启用）"""
    ok, needs_conv, reason = is_format_compatible(
        "claude:cli",
        "claude:chat",
        endpoint_format_acceptance_config={"enabled": True},
        is_stream=False,
        global_conversion_enabled=True,
        registry=MagicMock(),
    )
    assert ok is True
    assert needs_conv is False
    assert reason is None


def test_claude_to_claude_cli_no_conversion_needed() -> None:
    """CLAUDE 和 CLAUDE_CLI 格式相同，只是认证不同，可透传（需开关启用）"""
    ok, needs_conv, reason = is_format_compatible(
        "claude:chat",
        "claude:cli",
        endpoint_format_acceptance_config={"enabled": True},
        is_stream=False,
        global_conversion_enabled=True,
        registry=MagicMock(),
    )
    assert ok is True
    assert needs_conv is False
    assert reason is None


def test_gemini_cli_to_gemini_no_conversion_needed() -> None:
    """GEMINI 和 GEMINI_CLI 格式相同，只是认证不同，可透传（需开关启用）"""
    ok, needs_conv, reason = is_format_compatible(
        "gemini:cli",
        "gemini:chat",
        endpoint_format_acceptance_config={"enabled": True},
        is_stream=False,
        global_conversion_enabled=True,
        registry=MagicMock(),
    )
    assert ok is True
    assert needs_conv is False
    assert reason is None


def test_claude_cli_to_claude_blocked_when_global_switch_disabled() -> None:
    """透传格式（CLAUDE_CLI -> CLAUDE）也受全局开关限制"""
    ok, needs_conv, reason = is_format_compatible(
        "claude:cli",
        "claude:chat",
        endpoint_format_acceptance_config={"enabled": True},
        is_stream=False,
        global_conversion_enabled=False,
        registry=MagicMock(),
    )
    assert ok is False
    assert reason and ("全局" in reason or "FORMAT_CONVERSION_ENABLED" in reason)


def test_claude_cli_to_claude_blocked_when_endpoint_not_configured() -> None:
    """透传格式（CLAUDE_CLI -> CLAUDE）也需要端点配置"""
    ok, needs_conv, reason = is_format_compatible(
        "claude:cli",
        "claude:chat",
        endpoint_format_acceptance_config=None,
        is_stream=False,
        global_conversion_enabled=True,
        registry=MagicMock(),
    )
    assert ok is False
    assert reason and "未配置" in reason


def test_openai_cli_to_openai_needs_conversion() -> None:
    """OPENAI 和 OPENAI_CLI 格式不同（Chat Completions vs Responses API），需要转换"""
    registry = MagicMock()
    registry.can_convert_full.return_value = True

    ok, needs_conv, reason = is_format_compatible(
        "openai:cli",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True},  # 同族转换也需要端点配置
        is_stream=False,
        global_conversion_enabled=True,  # 同族转换也需要全局开关
        registry=registry,
    )
    assert ok is True
    assert needs_conv is True  # 需要转换！
    assert reason is None


def test_openai_to_openai_cli_needs_conversion() -> None:
    """OPENAI 和 OPENAI_CLI 格式不同（Chat Completions vs Responses API），需要转换"""
    registry = MagicMock()
    registry.can_convert_full.return_value = True

    ok, needs_conv, reason = is_format_compatible(
        "openai:chat",
        "openai:cli",
        endpoint_format_acceptance_config={"enabled": True},  # 同族转换也需要端点配置
        is_stream=False,
        global_conversion_enabled=True,  # 同族转换也需要全局开关
        registry=registry,
    )
    assert ok is True
    assert needs_conv is True  # 需要转换！
    assert reason is None


def test_openai_cli_to_openai_stream_needs_conversion() -> None:
    """OPENAI_CLI 流式请求到 OPENAI 也需要转换"""
    registry = MagicMock()
    registry.can_convert_full.return_value = True

    ok, needs_conv, reason = is_format_compatible(
        "openai:cli",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True},  # 同族转换也需要端点配置
        is_stream=True,
        global_conversion_enabled=True,  # 同族转换也需要全局开关
        registry=registry,
    )
    assert ok is True
    assert needs_conv is True
    assert reason is None


def test_openai_cli_to_openai_fails_without_converter() -> None:
    """如果转换器不支持，同族转换也会失败"""
    registry = MagicMock()
    registry.can_convert_full.return_value = False

    ok, needs_conv, reason = is_format_compatible(
        "openai:cli",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True},
        is_stream=False,
        global_conversion_enabled=True,
        registry=registry,
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "转换器" in reason


def test_openai_cli_to_openai_blocked_when_global_switch_disabled() -> None:
    """同族转换（OPENAI/OPENAI_CLI）也受全局开关限制（环境变量 FORMAT_CONVERSION_ENABLED=false）"""
    registry = MagicMock()
    registry.can_convert_full.return_value = True

    ok, needs_conv, reason = is_format_compatible(
        "openai:cli",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": True},
        is_stream=False,
        global_conversion_enabled=False,  # 全局开关关闭
        registry=registry,
    )
    assert ok is False
    assert needs_conv is False
    assert reason and ("全局" in reason or "FORMAT_CONVERSION_ENABLED" in reason)


def test_openai_cli_to_openai_blocked_when_endpoint_disabled() -> None:
    """同族转换（OPENAI/OPENAI_CLI）也受端点开关限制"""
    registry = MagicMock()
    registry.can_convert_full.return_value = True

    ok, needs_conv, reason = is_format_compatible(
        "openai:cli",
        "openai:chat",
        endpoint_format_acceptance_config={"enabled": False},  # 端点开关关闭
        is_stream=False,
        global_conversion_enabled=True,
        registry=registry,
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "未启用" in reason


def test_openai_cli_to_openai_blocked_when_endpoint_not_configured() -> None:
    """同族转换（OPENAI/OPENAI_CLI）也需要端点配置"""
    registry = MagicMock()
    registry.can_convert_full.return_value = True

    ok, needs_conv, reason = is_format_compatible(
        "openai:cli",
        "openai:chat",
        endpoint_format_acceptance_config=None,  # 无端点配置
        is_stream=False,
        global_conversion_enabled=True,
        registry=registry,
    )
    assert ok is False
    assert needs_conv is False
    assert reason and "未配置" in reason

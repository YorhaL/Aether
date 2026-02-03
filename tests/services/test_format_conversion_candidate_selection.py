from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.api_format.conversion import register_default_normalizers
from src.services.cache.aware_scheduler import CacheAwareScheduler


def _mock_key(key_id: str, api_formats: list[str]) -> MagicMock:
    key = MagicMock()
    key.id = key_id
    key.is_active = True
    key.api_formats = api_formats
    key.cache_ttl_minutes = 1
    key.internal_priority = 1
    return key


def _mock_endpoint(api_format: str, config: dict | None = None) -> MagicMock:
    endpoint = MagicMock()
    endpoint.id = f"ep_{api_format.lower().replace(':', '_')}"
    endpoint.is_active = True
    endpoint.api_format = api_format
    endpoint.api_family = api_format.split(":", 1)[0]
    endpoint.endpoint_kind = api_format.split(":", 1)[1]
    endpoint.format_acceptance_config = config
    return endpoint


@pytest.mark.asyncio
async def test_build_candidates_allows_cross_format_when_endpoint_accepts_and_overrides_off() -> (
    None
):
    register_default_normalizers()

    scheduler = CacheAwareScheduler()
    scheduler._check_model_support = AsyncMock(return_value=(True, None, None, {"m"}))  # type: ignore[attr-defined]
    scheduler._check_key_availability = MagicMock(return_value=(True, None, None))  # type: ignore[attr-defined]

    provider = MagicMock()
    provider.name = "p1"
    provider.enable_format_conversion = False
    provider.endpoints = [
        _mock_endpoint(
            "openai:chat",
            {"enabled": True, "accept_formats": ["claude:chat"], "stream_conversion": True},
        )
    ]
    provider.api_keys = [_mock_key("k1", ["openai:chat"])]

    candidates = await scheduler._build_candidates(
        db=MagicMock(),
        providers=[provider],
        client_format="claude:chat",
        model_name="dummy-model",
        affinity_key=None,
        global_conversion_enabled=True,  # 全局开关开启
    )

    assert len(candidates) == 1
    assert candidates[0].needs_conversion is True
    assert candidates[0].provider_api_format == "openai:chat"


@pytest.mark.asyncio
async def test_build_candidates_blocks_cross_format_when_master_switch_off() -> None:
    register_default_normalizers()

    scheduler = CacheAwareScheduler()
    scheduler._check_model_support = AsyncMock(return_value=(True, None, None, {"m"}))  # type: ignore[attr-defined]
    scheduler._check_key_availability = MagicMock(return_value=(True, None, None))  # type: ignore[attr-defined]

    provider = MagicMock()
    provider.name = "p1"
    provider.enable_format_conversion = False
    provider.endpoints = [
        _mock_endpoint(
            "openai:chat",
            {"enabled": True, "accept_formats": ["claude:chat"], "stream_conversion": True},
        )
    ]
    provider.api_keys = [_mock_key("k1", ["openai:chat"])]

    candidates = await scheduler._build_candidates(
        db=MagicMock(),
        providers=[provider],
        client_format="claude:chat",
        model_name="dummy-model",
        affinity_key=None,
        global_conversion_enabled=False,  # 全局开关关闭
    )

    assert candidates == []


@pytest.mark.asyncio
async def test_build_candidates_includes_cross_format_when_enabled() -> None:
    register_default_normalizers()

    scheduler = CacheAwareScheduler()
    scheduler._check_model_support = AsyncMock(return_value=(True, None, None, {"m"}))  # type: ignore[attr-defined]
    scheduler._check_key_availability = MagicMock(return_value=(True, None, None))  # type: ignore[attr-defined]

    provider = MagicMock()
    provider.name = "p1"
    provider.enable_format_conversion = False
    provider.endpoints = [
        # 端点未配置/未启用格式接受策略，但 DB 全局覆盖开启应强制允许
        _mock_endpoint("openai:chat", None)
    ]
    provider.api_keys = [_mock_key("k1", ["openai:chat"])]

    candidates = await scheduler._build_candidates(
        db=MagicMock(),
        providers=[provider],
        client_format="claude:chat",
        model_name="dummy-model",
        affinity_key=None,
        global_conversion_enabled=True,  # 全局开关开启：跳过端点检查
    )

    assert len(candidates) == 1
    assert candidates[0].needs_conversion is True
    assert candidates[0].provider_api_format == "openai:chat"


@pytest.mark.asyncio
async def test_exact_matches_rank_before_convertible() -> None:
    register_default_normalizers()

    scheduler = CacheAwareScheduler()
    scheduler._check_model_support = AsyncMock(return_value=(True, None, None, {"m"}))  # type: ignore[attr-defined]
    scheduler._check_key_availability = MagicMock(return_value=(True, None, None))  # type: ignore[attr-defined]

    provider = MagicMock()
    provider.name = "p1"
    provider.enable_format_conversion = False
    # 故意把 OPENAI 放在 endpoints[0]，验证排序仍然是 CLAUDE（exact）在前
    provider.endpoints = [
        _mock_endpoint(
            "openai:chat",
            {"enabled": True, "accept_formats": ["claude:chat"], "stream_conversion": True},
        ),
        _mock_endpoint("claude:chat", None),
    ]
    provider.api_keys = [
        _mock_key("k_openai", ["openai:chat"]),
        _mock_key("k_claude", ["claude:chat"]),
    ]

    candidates = await scheduler._build_candidates(
        db=MagicMock(),
        providers=[provider],
        client_format="claude:chat",
        model_name="dummy-model",
        affinity_key=None,
        global_conversion_enabled=True,  # 全局开关开启
    )

    assert len(candidates) == 2
    assert candidates[0].needs_conversion is False
    assert candidates[0].provider_api_format == "claude:chat"
    assert candidates[1].needs_conversion is True
    assert candidates[1].provider_api_format == "openai:chat"

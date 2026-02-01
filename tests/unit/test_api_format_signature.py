import pytest

from src.core.api_format.enums import ApiFamily, EndpointKind
from src.core.api_format.signature import (
    EndpointSignature,
    make_signature_key,
    normalize_endpoint_signature,
    normalize_signature_key,
    parse_signature_key,
)


def test_make_signature_key_accepts_enums_and_strings() -> None:
    assert make_signature_key(ApiFamily.OPENAI, EndpointKind.CHAT) == "openai:chat"
    assert make_signature_key("OpenAI", "CHAT") == "openai:chat"


def test_parse_signature_key_roundtrip() -> None:
    sig = parse_signature_key("OpenAI:CHAT")
    assert sig.api_family == ApiFamily.OPENAI
    assert sig.endpoint_kind == EndpointKind.CHAT
    assert sig.key == "openai:chat"


def test_parse_signature_key_invalid_raises() -> None:
    with pytest.raises(ValueError):
        parse_signature_key("OPENAI")  # missing ':'


def test_normalize_signature_key() -> None:
    assert normalize_signature_key("  OpenAI:CHAT  ") == "openai:chat"


def test_normalize_endpoint_signature_tuple_input() -> None:
    sig = normalize_endpoint_signature((ApiFamily.GEMINI, EndpointKind.VIDEO))
    assert sig == EndpointSignature(api_family=ApiFamily.GEMINI, endpoint_kind=EndpointKind.VIDEO)


def test_normalize_endpoint_signature_invalid_string_returns_default() -> None:
    default = EndpointSignature(api_family=ApiFamily.CLAUDE, endpoint_kind=EndpointKind.CHAT)
    assert normalize_endpoint_signature("not-a-signature", default=default) == default

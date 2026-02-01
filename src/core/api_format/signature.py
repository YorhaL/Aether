"""
Endpoint signature utilities.

新模式下，系统以 (ApiFamily, EndpointKind) 作为结构化标识；
在需要用 string 做 key（JSON dict / metrics label / logs）时，统一使用 `family:kind` 的 signature key。
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.api_format.enums import ApiFamily, EndpointKind


@dataclass(frozen=True, slots=True)
class EndpointSignature:
    api_family: ApiFamily
    endpoint_kind: EndpointKind

    @property
    def key(self) -> str:
        return make_signature_key(self.api_family, self.endpoint_kind)


def make_signature_key(api_family: ApiFamily | str, endpoint_kind: EndpointKind | str) -> str:
    fam = api_family.value if isinstance(api_family, ApiFamily) else str(api_family).strip().lower()
    kind = (
        endpoint_kind.value
        if isinstance(endpoint_kind, EndpointKind)
        else str(endpoint_kind).strip().lower()
    )
    return f"{fam}:{kind}"


def parse_signature_key(value: str) -> EndpointSignature:
    """
    Parse a signature key into structured enums.

    Canonical form: `<api_family>:<endpoint_kind>`, both lowercase.
    """
    raw = str(value).strip()
    if not raw or ":" not in raw:
        raise ValueError(f"Invalid endpoint signature: {value!r}")
    fam_raw, kind_raw = raw.split(":", 1)
    fam = ApiFamily(fam_raw.strip().lower())
    kind = EndpointKind(kind_raw.strip().lower())
    return EndpointSignature(api_family=fam, endpoint_kind=kind)


def normalize_signature_key(value: str) -> str:
    """Normalize signature key (case/whitespace) to canonical lowercase `family:kind`."""
    sig = parse_signature_key(value)
    return sig.key


def normalize_endpoint_signature(
    value: str | EndpointSignature | tuple[ApiFamily, EndpointKind] | None,
    *,
    default: EndpointSignature | None = None,
) -> EndpointSignature | None:
    if value is None:
        return default
    if isinstance(value, EndpointSignature):
        return value
    if isinstance(value, tuple) and len(value) == 2:
        fam, kind = value
        if isinstance(fam, ApiFamily) and isinstance(kind, EndpointKind):
            return EndpointSignature(api_family=fam, endpoint_kind=kind)
        return default
    if isinstance(value, str):
        try:
            return parse_signature_key(value)
        except Exception:
            return default
    return default


__all__ = [
    "EndpointSignature",
    "make_signature_key",
    "parse_signature_key",
    "normalize_signature_key",
    "normalize_endpoint_signature",
]

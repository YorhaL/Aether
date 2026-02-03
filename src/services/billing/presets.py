"""
Billing presets (developer-provided defaults).

Why:
- Asking end-users to configure DimensionCollectors / BillingRules from scratch is too complex.
- We ship a curated set of "known-good" collector presets per api_format/task_type
  and provide an Admin API to apply them into DB (merge or overwrite).

Notes:
- BillingRule presets are intentionally NOT materialized here, because the unified
  billing architecture already provides a runtime default rule generator that stays
  in-sync with Model/GlobalModel pricing. Persisting those prices into BillingRule
  rows would become stale when model pricing changes.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from src.core.api_format.signature import normalize_signature_key
from src.models.database import DimensionCollector

PresetApplyMode = Literal["merge", "overwrite"]


def _norm_api(api_format: str) -> str:
    return normalize_signature_key(api_format or "")


def _norm_task(task_type: str) -> str:
    return (task_type or "").strip().lower()


@dataclass(frozen=True)
class CollectorPreset:
    api_format: str
    task_type: str
    dimension_name: str

    source_type: str
    source_path: str | None = None

    value_type: str = "float"  # float/int/string
    transform_expression: str | None = None
    default_value: str | None = None

    priority: int = 0
    is_enabled: bool = True


@dataclass(frozen=True)
class PresetPack:
    name: str
    version: str
    description: str
    collectors: list[CollectorPreset]


def _discover_collectors() -> list[CollectorPreset]:
    """
    Config-file mode: discover collectors from `src.services.billing.collector_defs`.

    Developers add a new file under that package; no central registry edits required.
    """
    out: list[CollectorPreset] = []

    try:
        pkg = importlib.import_module("src.services.billing.collector_defs")
        pkg_path = getattr(pkg, "__path__", None)
        if not pkg_path:
            return out
    except Exception:
        return out

    for mod in pkgutil.iter_modules(pkg_path):
        if mod.ispkg:
            continue
        mod_name = f"src.services.billing.collector_defs.{mod.name}"
        try:
            m = importlib.import_module(mod_name)
        except Exception:
            continue

        items = getattr(m, "COLLECTORS", None)
        if not isinstance(items, list):
            continue

        for raw in items:
            if not isinstance(raw, dict):
                continue
            try:
                out.append(
                    CollectorPreset(
                        api_format=str(raw.get("api_format") or "").strip(),
                        task_type=str(raw.get("task_type") or "").strip().lower(),
                        dimension_name=str(raw.get("dimension_name") or "").strip(),
                        source_type=str(raw.get("source_type") or "").strip().lower(),
                        source_path=raw.get("source_path"),
                        value_type=str(raw.get("value_type") or "float").strip().lower(),
                        transform_expression=raw.get("transform_expression"),
                        default_value=raw.get("default_value"),
                        priority=int(raw.get("priority") or 0),
                        is_enabled=bool(raw.get("is_enabled", True)),
                    )
                )
            except Exception:
                continue

    return out


CORE_PRESET_PACK = PresetPack(
    name="aether-core",
    version="1.0",
    description="Aether built-in dimension collectors for common api_formats/task_types.",
    collectors=_discover_collectors(),
)


def list_preset_packs() -> list[PresetPack]:
    return [CORE_PRESET_PACK]


@dataclass(frozen=True)
class PresetApplyResult:
    preset: str
    mode: PresetApplyMode
    created: int
    updated: int
    skipped: int
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "preset": self.preset,
            "mode": self.mode,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": list(self.errors),
        }


class BillingPresetService:
    @staticmethod
    def apply_preset(
        db: Session,
        *,
        preset_name: str,
        mode: PresetApplyMode = "merge",
    ) -> PresetApplyResult:
        preset_name = (preset_name or "").strip()
        packs = {p.name: p for p in list_preset_packs()}
        pack = packs.get(preset_name)
        if pack is None:
            available = ", ".join(sorted(packs.keys()))
            return PresetApplyResult(
                preset=preset_name,
                mode=mode,
                created=0,
                updated=0,
                skipped=0,
                errors=[f"Unknown preset: {preset_name!r}. Available: {available}"],
            )

        created = 0
        updated = 0
        skipped = 0
        errors: list[str] = []

        for item in pack.collectors:
            api_format = _norm_api(item.api_format)
            task_type = _norm_task(item.task_type)
            dim = (item.dimension_name or "").strip()

            if not api_format or not task_type or not dim:
                skipped += 1
                continue

            try:
                existing = (
                    db.query(DimensionCollector)
                    .filter(
                        DimensionCollector.api_format == api_format,
                        DimensionCollector.task_type == task_type,
                        DimensionCollector.dimension_name == dim,
                        DimensionCollector.priority == int(item.priority or 0),
                        DimensionCollector.is_enabled == True,  # noqa: E712
                    )
                    .first()
                )
            except Exception as exc:
                errors.append(
                    f"Failed to query collector: api_format={api_format} task_type={task_type} dim={dim}: {exc}"
                )
                continue

            if existing is not None:
                if mode == "overwrite":
                    try:
                        existing.source_type = (item.source_type or "").strip().lower()
                        existing.source_path = item.source_path
                        existing.value_type = (item.value_type or "float").strip().lower()
                        existing.transform_expression = item.transform_expression
                        existing.default_value = item.default_value
                        existing.is_enabled = bool(item.is_enabled)
                        updated += 1
                    except Exception as exc:
                        errors.append(
                            f"Failed to update collector {getattr(existing, 'id', None)}: {exc}"
                        )
                else:
                    skipped += 1
                continue

            try:
                c = DimensionCollector(
                    api_format=api_format,
                    task_type=task_type,
                    dimension_name=dim,
                    source_type=(item.source_type or "").strip().lower(),
                    source_path=item.source_path,
                    value_type=(item.value_type or "float").strip().lower(),
                    transform_expression=item.transform_expression,
                    default_value=item.default_value,
                    priority=int(item.priority or 0),
                    is_enabled=bool(item.is_enabled),
                )
                db.add(c)
                created += 1
            except Exception as exc:
                errors.append(
                    f"Failed to create collector: api_format={api_format} task_type={task_type} dim={dim}: {exc}"
                )

        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            errors.append(f"DB commit failed: {exc}")

        return PresetApplyResult(
            preset=pack.name,
            mode=mode,
            created=created,
            updated=updated,
            skipped=skipped,
            errors=errors,
        )

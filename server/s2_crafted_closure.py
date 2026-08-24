"""Offline closure report for one bounded Midnight Season 2 recipe probe.

This module only interprets the projected, exact-filtered DB2 evidence already
captured by ``s2_limited_db2``.  It deliberately does not turn modifier item
ids, bonus-tree ids, or transport descriptions into player-visible stat or
effect identities.  Those identities require a separate first-party semantic
owner and fixed SimC evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

from .s2_limited_db2 import (
    LimitedDb2Error,
    canonical_json_sha256,
    validate_db2_field_allowlist,
)


SCHEMA_REVISION = "s2-crafted-closure-report-v1"
REPORT_PREFIX = "s2-crafted-closure:sha256:"
DEFAULT_ALLOWLIST_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "midnight-season-2"
    / "db2-field-allowlist-v1.json"
)
_ID_PATTERN = re.compile(r"^[1-9][0-9]*$")
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_BUILD_PATTERN = re.compile(r"^\d+\.\d+\.\d+\.\d+$")


class CraftedClosureError(ValueError):
    """Raised when a local crafted probe cannot be interpreted safely."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _id(value: Any, label: str) -> str:
    text = _text(value)
    if not _ID_PATTERN.fullmatch(text):
        raise CraftedClosureError(f"{label} must be a positive integer id")
    return str(int(text))


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _hash_report(value: Mapping[str, Any]) -> str:
    payload = {
        key: child
        for key, child in value.items()
        if key not in {"reportId", "generatedAt"}
    }
    digest = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return f"{REPORT_PREFIX}{digest}"


def _safe_response_path(root: Path, relative_path: Any) -> Path:
    relative = Path(_text(relative_path))
    candidate = (root / relative).resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise CraftedClosureError("capture response path escapes capture root")
    if not candidate.is_file():
        raise CraftedClosureError(f"capture response file is missing: {relative}")
    return candidate


def _load_capture_rows(
    capture_root: Path,
    *,
    allowlist: Mapping[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    root = Path(capture_root).expanduser().resolve()
    try:
        manifest = json.loads(
            (root / "capture-manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as error:
        raise CraftedClosureError("capture manifest is unavailable") from error
    if not isinstance(manifest, Mapping) or manifest.get("status") != "captured":
        raise CraftedClosureError("capture manifest must be captured")
    if manifest.get("rawDb2Persisted") is not False:
        raise CraftedClosureError("raw DB2 persistence is not allowed")
    normalized_allowlist = validate_db2_field_allowlist(allowlist)
    if _text(manifest.get("allowlistRevision")) != _text(
        normalized_allowlist.get("schemaRevision")
    ):
        raise CraftedClosureError("capture allowlist revision mismatch")

    rows_by_table: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_rows: dict[str, set[str]] = defaultdict(set)
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise CraftedClosureError("capture manifest entries are required")
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise CraftedClosureError("capture manifest entry is invalid")
        table = _text(entry.get("table"))
        if table not in normalized_allowlist["tables"]:
            raise CraftedClosureError(f"capture table is not allowlisted: {table}")
        response_path = _safe_response_path(root, entry.get("responsePath"))
        try:
            record = json.loads(response_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise CraftedClosureError(
                f"capture response is not valid JSON: {entry.get('responsePath')}"
            ) from error
        if not isinstance(record, Mapping) or _text(record.get("table")) != table:
            raise CraftedClosureError("capture response table mismatch")
        if record.get("bodySha256") != entry.get("bodySha256"):
            raise CraftedClosureError("capture response body hash mismatch")
        if record.get("bodyBytes") != entry.get("bodyBytes"):
            raise CraftedClosureError("capture response body size mismatch")
        fields = record.get("fields")
        if not isinstance(fields, list):
            raise CraftedClosureError(f"capture response fields missing: {table}")
        allowed_fields = set(normalized_allowlist["tables"][table]["fields"])
        if not set(fields).issubset(allowed_fields):
            raise CraftedClosureError(f"capture response leaves field allowlist: {table}")
        response_rows = record.get("rows")
        if not isinstance(response_rows, list):
            raise CraftedClosureError(f"capture response rows missing: {table}")
        for row in response_rows:
            if not isinstance(row, Mapping) or not set(row).issubset(set(fields)):
                raise CraftedClosureError(f"capture response row is not projected: {table}")
            canonical = canonical_json_sha256(row)
            if canonical in seen_rows[table]:
                continue
            seen_rows[table].add(canonical)
            rows_by_table[table].append(dict(row))
    return dict(rows_by_table), dict(manifest)


def _rows(rows: Mapping[str, list[dict[str, Any]]], table: str) -> list[dict[str, Any]]:
    return list(rows.get(table) or [])


def _single(rows: list[Mapping[str, Any]], label: str) -> dict[str, Any] | None:
    if len(rows) != 1:
        return None
    return dict(rows[0])


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _quality_fact(
    rows: Mapping[str, list[dict[str, Any]]],
    crafting_difficulty_id: str,
) -> dict[str, Any]:
    difficulty_rows = [
        row
        for row in _rows(rows, "CraftingDifficultyQuality")
        if _text(row.get("CraftingDifficultyID")) == crafting_difficulty_id
    ]
    percentages = sorted(
        {
            int(row.get("QualityPercentage"))
            for row in difficulty_rows
            if isinstance(row.get("QualityPercentage"), int)
        }
    )
    quality_ids = sorted(
        {
            _text(row.get("CraftingQualityID"))
            for row in difficulty_rows
            if _text(row.get("CraftingQualityID"))
        },
        key=int,
    )
    quality_by_id = {
        _text(row.get("ID")): row
        for row in _rows(rows, "CraftingQuality")
        if _text(row.get("ID"))
    }
    quality_tiers = sorted(
        {
            int(quality_by_id[quality_id]["QualityTier"])
            for quality_id in quality_ids
            if quality_id in quality_by_id
            and isinstance(quality_by_id[quality_id].get("QualityTier"), int)
        }
    )
    status = (
        "verified"
        if len(difficulty_rows) == 5
        and percentages == [0, 20, 50, 80, 100]
        and quality_tiers == [1, 2, 3, 4, 5]
        else "UNVERIFIED"
    )
    return {
        "status": status,
        "craftingDifficultyId": crafting_difficulty_id,
        "qualityPercentages": percentages,
        "qualityIds": quality_ids,
        "qualityTiers": quality_tiers,
    }


def _slot_fact(
    rows: Mapping[str, list[dict[str, Any]]],
    slot_row: Mapping[str, Any],
) -> dict[str, Any]:
    slot_id = _text(slot_row.get("ModifiedCraftingReagentSlotID"))
    slot = next(
        (
            row
            for row in _rows(rows, "ModifiedCraftingReagentSlot")
            if _text(row.get("ID")) == slot_id
        ),
        {},
    )
    name = _text(slot.get("Name_lang"))
    category_id = _text(slot.get("ID"))
    modifier_rows = [
        row
        for row in _rows(rows, "ModifiedCraftingReagentItem")
        if _text(row.get("ModifiedCraftingCategoryID")) == category_id
    ]
    modifier_ids = {
        _text(row.get("ID"))
        for row in modifier_rows
        if _text(row.get("ID"))
    }
    generated_item_ids = sorted(
        {
            _text(row.get("ItemID"))
            for row in _rows(rows, "ModifiedCraftingItem")
            if _text(row.get("ModifiedCraftingReagentItemID")) in modifier_ids
            and _text(row.get("ItemID"))
        },
        key=int,
    )
    reagent_item_ids = sorted(
        {
            _text(row.get("ItemID"))
            for row in _rows(rows, "CraftingReagentQuality")
            if _text(row.get("ModifiedCraftingCategoryID")) == category_id
            and _text(row.get("ItemID"))
        },
        key=int,
    )
    bonus_tree_ids = sorted(
        {
            _text(row.get("ItemBonusTreeID"))
            for row in modifier_rows
            if _text(row.get("ItemBonusTreeID"))
        },
        key=int,
    )
    descriptions = sorted(
        {
            _text(row.get("Description_lang"))
            for row in modifier_rows
            if _text(row.get("Description_lang"))
        }
    )
    semantic_options: list[dict[str, Any]] = []
    if name == "Amplify Secondary Stat":
        status = "UNVERIFIED"
        blocker_code = "SECONDARY_OPTION_SEMANTICS_UNVERIFIED"
    elif name == "Add Embellishment":
        status = "UNVERIFIED"
        blocker_code = "EMBELLISHMENT_EFFECT_UNVERIFIED"
    else:
        status = "observed_capability"
        blocker_code = ""
    return {
        "status": status,
        "slot": int(slot_row.get("Slot") or 0),
        "slotId": category_id,
        "name": name,
        "reagentType": slot.get("ReagentType"),
        "reagentSource": slot.get("ReagentSource"),
        "modifierItemIds": sorted(modifier_ids, key=int),
        "generatedModifierItemIds": generated_item_ids,
        "reagentItemIds": reagent_item_ids,
        "bonusTreeIds": bonus_tree_ids,
        "descriptions": descriptions,
        "semanticOptions": semantic_options,
        "blockerCode": blocker_code,
    }


def _evaluate_simc_probe(
    probe: Mapping[str, Any],
    *,
    client_build: str,
    item_id: str,
) -> dict[str, Any]:
    blocker_codes: set[str] = set()
    runtime = probe.get("runtimeIdentity")
    runtime = runtime if isinstance(runtime, Mapping) else {}
    runtime_build = _text(runtime.get("build"))
    runtime_revision = _text(runtime.get("commit")).lower()
    binary_sha256 = _text(runtime.get("binarySha256")).lower()
    if not _BUILD_PATTERN.fullmatch(runtime_build):
        blocker_codes.add("SIMC_RUNTIME_BUILD_UNAVAILABLE")
    if not _COMMIT_PATTERN.fullmatch(runtime_revision):
        blocker_codes.add("SIMC_RUNTIME_COMMIT_INVALID")
    if not _SHA256_PATTERN.fullmatch(binary_sha256):
        blocker_codes.add("SIMC_RUNTIME_BINARY_HASH_INVALID")
    if runtime_build != client_build:
        blocker_codes.add("SIMC_CLIENT_BUILD_MISMATCH")
    if probe.get("sourceCompatibilityVerified") is not True:
        blocker_codes.add("SIMC_SOURCE_COMPATIBILITY_UNVERIFIED")

    raw_probes = probe.get("probes")
    if not isinstance(raw_probes, list) or not raw_probes:
        blocker_codes.add("SIMC_PROBE_MATRIX_EMPTY")
        raw_probes = []
    summaries: list[dict[str, Any]] = []
    passed_count = 0
    for raw_probe in raw_probes:
        row = raw_probe if isinstance(raw_probe, Mapping) else {}
        option = _text(row.get("option"))
        encoded_item = _text(row.get("encodedItem"))
        row_blockers: set[str] = set()
        if row.get("returncode") != 0:
            row_blockers.add("SIMC_PROBE_EXIT_FAILED")
        if not option or f"crafted_stats={option}" not in encoded_item:
            row_blockers.add("SIMC_PROBE_OPTION_NOT_SERIALIZED")
        if f"id={item_id}" not in encoded_item:
            row_blockers.add("SIMC_PROBE_ITEM_ID_MISMATCH")
        item_level = row.get("itemLevel")
        if isinstance(item_level, bool) or not isinstance(item_level, int) or item_level <= 0:
            row_blockers.add("SIMC_PROBE_ITEM_LEVEL_MISSING")
        stats = row.get("stats")
        if not isinstance(stats, Mapping) or not stats:
            row_blockers.add("SIMC_TARGET_STATS_MISSING")
        if "trivial" in _text(row.get("stderr")).casefold() or "warning" in _text(row.get("stderr")).casefold():
            row_blockers.add("SIMC_ITEM_RESOLUTION_WARNING")
        blocker_codes.update(row_blockers)
        if not row_blockers:
            passed_count += 1
        summaries.append(
            {
                "option": option,
                "status": "pass" if not row_blockers else "blocked",
                "returncode": row.get("returncode"),
                "encodedItem": encoded_item,
                "itemLevel": item_level,
                "stats": dict(stats) if isinstance(stats, Mapping) else {},
                "blockerCodes": sorted(row_blockers),
            }
        )
    return {
        "status": "verified" if not blocker_codes else "blocked",
        "runtimeRevision": runtime_revision,
        "runtimeBuild": runtime_build,
        "binarySha256": binary_sha256,
        "probeCount": len(summaries),
        "passedProbeCount": passed_count,
        "probes": summaries,
        "blockerCodes": sorted(blocker_codes),
    }


def build_crafted_closure_report(
    capture_root: Path,
    *,
    recipe_id: Any,
    allowlist: Mapping[str, Any] | None = None,
    simc_probe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_recipe_id = _id(recipe_id, "recipeId")
    if allowlist is None:
        try:
            allowlist = json.loads(DEFAULT_ALLOWLIST_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise CraftedClosureError("default DB2 allowlist is unavailable") from error
    rows, manifest = _load_capture_rows(capture_root, allowlist=allowlist)

    recipe_row = _single(
        [
            row
            for row in _rows(rows, "SkillLineAbility")
            if _text(row.get("ID")) == normalized_recipe_id
        ],
        "recipe",
    )
    spell_id = _text(recipe_row.get("Spell")) if recipe_row else ""
    spell_effect = _single(
        [
            row
            for row in _rows(rows, "SpellEffect")
            if _text(row.get("SpellID")) == spell_id
            and row.get("Effect") == 288
        ],
        "recipe output spell effect",
    )
    crafting_data_id = _text(spell_effect.get("EffectMiscValue_0")) if spell_effect else ""
    crafting_data = _single(
        [
            row
            for row in _rows(rows, "CraftingData")
            if _text(row.get("ID")) == crafting_data_id
        ],
        "crafting data",
    )
    item_id = _text(crafting_data.get("CraftedItemID")) if crafting_data else ""
    recipe_output = {
        "status": (
            "verified"
            if recipe_row and spell_id and spell_effect and crafting_data and item_id
            else "blocked"
        ),
        "recipeId": normalized_recipe_id,
        "spellId": spell_id,
        "craftingDataId": crafting_data_id,
        "itemId": item_id,
    }
    crafting_quality = _quality_fact(
        rows,
        _text(crafting_data.get("CraftingDifficultyID")) if crafting_data else "",
    )

    slot_rows = [
        row
        for row in _rows(rows, "ModifiedCraftingSpellSlot")
        if _text(row.get("SpellID")) == spell_id
    ]
    slots: dict[str, dict[str, Any]] = {}
    blocker_codes: set[str] = set()
    for row in sorted(slot_rows, key=lambda value: int(value.get("Slot") or 0)):
        fact = _slot_fact(rows, row)
        key = _slug(_text(fact.get("name"))) or f"slot_{fact['slot']}"
        slots[key] = fact
        if fact.get("blockerCode"):
            blocker_codes.add(str(fact["blockerCode"]))
    if recipe_output["status"] != "verified":
        blocker_codes.add("RECIPE_OUTPUT_RELATION_BLOCKED")
    if crafting_quality["status"] != "verified":
        blocker_codes.add("CRAFTING_QUALITY_RELATION_UNVERIFIED")

    simc = dict(simc_probe) if isinstance(simc_probe, Mapping) else {}
    if not simc:
        simc_readiness = {
            "status": "blocked",
            "runtimeRevision": "",
            "probes": [],
            "blockerCodes": [
                "SIMC_RUNTIME_IDENTITY_UNAVAILABLE",
                "SIMC_PROBE_MATRIX_MISSING",
            ],
        }
    else:
        simc_readiness = _evaluate_simc_probe(
            simc,
            client_build=_text(manifest.get("clientBuild")),
            item_id=item_id,
        )
    blocker_codes.update(simc_readiness["blockerCodes"])
    report = {
        "schemaRevision": SCHEMA_REVISION,
        "status": "blocked" if recipe_output["status"] == "blocked" else "partial",
        "recipeId": normalized_recipe_id,
        "clientBuild": _text(manifest.get("clientBuild")),
        "allowlistRevision": _text(manifest.get("allowlistRevision")),
        "captureRoot": Path(capture_root).name,
        "captureRequestCount": int(manifest.get("requestCount") or 0),
        "recipeOutput": recipe_output,
        "craftingQuality": crafting_quality,
        "slots": slots,
        "simcReadiness": simc_readiness,
        "blockerCodes": sorted(blocker_codes),
        "semanticAuthority": "official_client_db2_fields_only; no semantic inference",
        "notARelease": True,
        "activeManifestChanged": False,
        "productionWritten": False,
    }
    report["reportId"] = _hash_report(report)
    return report


__all__ = [
    "CraftedClosureError",
    "DEFAULT_ALLOWLIST_PATH",
    "REPORT_PREFIX",
    "SCHEMA_REVISION",
    "build_crafted_closure_report",
]

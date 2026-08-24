"""Build an auditable, non-promotable Midnight Season 2 equipment closure.

This module is the boundary between captured facts and the existing
Catalog/Exact/Resolver stack.  It deliberately does not build a Catalog, write
PostgreSQL, run SimC, or mutate an Active Manifest.  Its output is a
field-oriented coverage report that can only become a candidate input after
every unresolved fact and fixed SimC gate has closed.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

try:
    from .websim_payload import item_slot_from_payload
except ImportError:  # pragma: no cover - direct module execution support
    from websim_payload import item_slot_from_payload

try:
    from .s2_variant_authority import classify_variant_upgrade
except ImportError:  # pragma: no cover - direct module execution support
    from s2_variant_authority import classify_variant_upgrade

try:
    from .s2_enhancement_authority import build_s2_enhancement_authority
except ImportError:  # pragma: no cover - direct module execution support
    from s2_enhancement_authority import build_s2_enhancement_authority

try:
    from .s2_journal_item_scope import classify_mythic_plus_journal_item_scope
except ImportError:  # pragma: no cover - direct module execution support
    from s2_journal_item_scope import classify_mythic_plus_journal_item_scope

try:
    from .s2_mythic_plus_item_scope import (
        ADAPTER_REVISION as MYTHIC_PLUS_ITEM_SCOPE_ADAPTER_REVISION,
        classify_mythic_plus_item_scope,
    )
except ImportError:  # pragma: no cover - direct module execution support
    from s2_mythic_plus_item_scope import (
        ADAPTER_REVISION as MYTHIC_PLUS_ITEM_SCOPE_ADAPTER_REVISION,
        classify_mythic_plus_item_scope,
    )


SCHEMA_REVISION = "s2-equipment-library-closure-v1"
REPORT_PREFIX = "s2-equipment-library-closure:sha256:"
_ID_PATTERN = re.compile(r"^[1-9][0-9]*$")
_LOGICAL_SOURCES = ("raid", "mythic_plus", "crafted", "tier_set")
_EXCLUDED_SOURCE_TYPES = (
    "dungeon",
    "delve",
    "prey",
    "great_vault",
    "world_content",
)
_SIMC_RUNTIME_BUILD_PATTERN = re.compile(
    r"^simc:(?P<build>\d+\.\d+\.\d+\.\d+):"
)
_SIMC_MATRIX_DIMENSION_BLOCKERS = frozenset(
    {
        "SIMC_PUBLIC_VARIANT_MATRIX_UNVERIFIED",
        "SIMC_CRAFTED_VARIANT_MATRIX_UNVERIFIED",
        "SIMC_SET_CONVERSION_MATRIX_UNVERIFIED",
        "SIMC_REPRESENTATIVE_PROFILE_MATRIX_UNVERIFIED",
        "SIMC_ENHANCEMENT_MATRIX_UNVERIFIED",
    }
)
_CRAFTED_TRACK_RANGE_PATTERN = re.compile(
    r"sets the item level of the resulting item to\s+(?P<minimum>\d+)-(?P<maximum>\d+)\s+based on quality",
    re.IGNORECASE,
)
_CANONICAL_DB2_STATIC_FIELDS = (
    "ID",
    "ItemLevel",
    "ItemSet",
    "OverallQualityID",
    "InventoryType",
    "Gem_properties",
    "Socket_match_enchantment_ID",
    "SocketType_0",
    "SocketType_1",
    "SocketType_2",
    "StatModifier_bonusStat_0",
    "StatModifier_bonusStat_1",
    "StatModifier_bonusStat_2",
    "StatModifier_bonusStat_3",
    "StatModifier_bonusStat_4",
    "StatModifier_bonusStat_5",
    "StatModifier_bonusStat_6",
    "StatModifier_bonusStat_7",
    "StatModifier_bonusStat_8",
    "StatModifier_bonusStat_9",
)


class S2EquipmentLibraryClosureError(ValueError):
    """Raised when closure inputs leave the fixed product or evidence contract."""


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _simc_runtime_build(identity: str) -> str | None:
    match = _SIMC_RUNTIME_BUILD_PATTERN.match(_text(identity))
    return match.group("build") if match else None


def _id(value: Any, label: str) -> str:
    text = _text(value)
    if not _ID_PATTERN.fullmatch(text):
        raise S2EquipmentLibraryClosureError(f"{label} must be a positive integer id")
    return str(int(text))


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise S2EquipmentLibraryClosureError(f"{label} must be an object")
    return dict(value)


def _load_json(value: Any, label: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    try:
        payload = json.loads(Path(value).expanduser().read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise S2EquipmentLibraryClosureError(f"unable to load {label}") from error
    return _mapping(payload, label)


def _safe_file(root: Path, relative_path: Any) -> Path:
    relative = Path(_text(relative_path))
    if relative.is_absolute():
        raise S2EquipmentLibraryClosureError("capture response path must be relative")
    resolved_root = root.resolve()
    candidate = (root / relative).resolve()
    if candidate == resolved_root or resolved_root not in candidate.parents:
        raise S2EquipmentLibraryClosureError("capture response path escapes capture root")
    if not candidate.is_file():
        raise S2EquipmentLibraryClosureError(
            f"capture response file is missing: {relative.as_posix()}"
        )
    return candidate


def _hash_report(report: Mapping[str, Any]) -> str:
    payload = {
        key: value
        for key, value in report.items()
        if key not in {"reportId", "generatedAt"}
    }
    return REPORT_PREFIX + hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _candidate_identity_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    """Return the fact identity that a fixed SimC matrix binds to.

    A matrix is an evidence attachment and is produced *after* the closure
    facts are assembled.  Including its result, gate status, or matrix-only
    blocker codes in the candidate hash would make every accepted matrix
    change the candidate id and create an impossible one-step-late binding.
    """

    payload = _canonical(report)
    payload.pop("reportId", None)
    payload.pop("generatedAt", None)
    payload.pop("status", None)
    payload.pop("simcMatrixEvidence", None)
    coverage_counts = payload.get("coverageCounts")
    if isinstance(coverage_counts, dict):
        coverage_counts.pop("simcMatrix", None)
        for key in (
            "blockedCount",
            "blockedItemCount",
            "blockedVariantCount",
            "simcReadyCount",
            "simcReadyVariantCount",
            "simcBlockedVariantCount",
            "simcExcludedVariantCount",
            "craftedVariantTemplateSimcReadyCount",
            "craftedVariantTemplateSimcBlockedCount",
        ):
            coverage_counts.pop(key, None)
    evidence_packet = payload.get("evidencePacket")
    if isinstance(evidence_packet, dict):
        evidence_packet.pop("simcMatrix", None)
    blocker_codes = payload.get("blockerCodes")
    if isinstance(blocker_codes, list):
        payload["blockerCodes"] = sorted(
            code
            for code in blocker_codes
            if not (
                _text(code).startswith("SIMC_MATRIX_")
                or _text(code) in _SIMC_MATRIX_DIMENSION_BLOCKERS
            )
        )
    for collection_key in (
        "itemDefinitions",
        "variants",
        "craftedVariantTemplates",
    ):
        collection = payload.get(collection_key)
        if not isinstance(collection, list):
            continue
        for row in collection:
            if isinstance(row, dict):
                row.pop("simcReadiness", None)
                row.pop("simcEvidence", None)
    return payload


def _candidate_identity_report_id(report: Mapping[str, Any]) -> str:
    """Return the stable identity shared by matrix-free and matrix-bound reports."""

    return _hash_report(_candidate_identity_payload(report))


def _apply_simc_matrix_readiness(
    report: dict[str, Any],
    matrix: Mapping[str, Any],
) -> None:
    """Project exact matrix readback status onto candidate readiness fields.

    The matrix remains runtime evidence, not a game-fact owner.  Every
    public/crafted row is matched by its full job key suffix; a successful
    readback becomes ``ready``, a missing or failed readback stays ``blocked``,
    and an explicit scope exclusion stays ``excluded``.  Item-level readiness
    is the conjunction of all non-excluded rows owned by that item.
    """

    matrix_report_id = _text(matrix.get("reportId"))
    runtime_identity = _text(matrix.get("runtimeIdentity"))

    def result_by_key(section_key: str, prefix: str) -> dict[str, Mapping[str, Any]]:
        raw_section = matrix.get(section_key)
        section = raw_section if isinstance(raw_section, Mapping) else {}
        results: dict[str, Mapping[str, Any]] = {}
        for raw_result in section.get("results") or []:
            if not isinstance(raw_result, Mapping):
                continue
            job_key = _text(raw_result.get("jobKey"))
            marker = f"{prefix}:"
            if job_key.startswith(marker):
                results[job_key[len(marker) :]] = raw_result
        return results

    public_results = result_by_key("publicVariantMatrix", "public")
    crafted_results = result_by_key("craftedVariantMatrix", "crafted")

    def apply_rows(
        rows: Sequence[Mapping[str, Any]],
        results: Mapping[str, Mapping[str, Any]],
    ) -> None:
        for raw_row in rows:
            if not isinstance(raw_row, dict):
                continue
            variant_key = _text(raw_row.get("variantKey"))
            if _text(raw_row.get("status")) == "excluded":
                raw_row["simcReadiness"] = "excluded"
                raw_row["simcEvidence"] = {
                    "status": "excluded",
                    "reason": "scope_excluded",
                }
                continue
            result = results.get(variant_key)
            result_status = _text((result or {}).get("status"))
            readiness = "ready" if result_status == "verified" else "blocked"
            raw_row["simcReadiness"] = readiness
            raw_row["simcEvidence"] = {
                "status": result_status or "UNVERIFIED",
                "matrixReportId": matrix_report_id,
                "runtimeIdentity": runtime_identity,
                "jobKey": _text((result or {}).get("jobKey"))
                or f"unmatched:{variant_key}",
                "failureCodes": sorted(
                    {
                        _text(code)
                        for code in (result or {}).get("failureCodes") or []
                        if _text(code)
                    }
                ),
            }

    variants = report.get("variants") or []
    crafted_templates = report.get("craftedVariantTemplates") or []
    apply_rows(variants, public_results)
    apply_rows(crafted_templates, crafted_results)

    rows_by_item: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for raw_row in [*variants, *crafted_templates]:
        if not isinstance(raw_row, Mapping):
            continue
        if _text(raw_row.get("status")) == "excluded":
            continue
        item_id = _text(raw_row.get("itemId"))
        if item_id:
            rows_by_item[item_id].append(raw_row)

    for raw_item in report.get("itemDefinitions") or []:
        if not isinstance(raw_item, dict):
            continue
        owned_rows = rows_by_item.get(_text(raw_item.get("itemId")), [])
        raw_item["simcReadiness"] = (
            "ready"
            if owned_rows
            and all(_text(row.get("simcReadiness")) == "ready" for row in owned_rows)
            else "blocked"
        )

    coverage = report.get("coverageCounts")
    if not isinstance(coverage, dict):
        return
    item_definitions = [
        row
        for row in report.get("itemDefinitions") or []
        if isinstance(row, Mapping)
    ]
    variant_rows = [
        row for row in variants if isinstance(row, Mapping)
    ]
    crafted_rows = [
        row for row in crafted_templates if isinstance(row, Mapping)
    ]
    coverage.update(
        {
            "blockedCount": sum(
                1 for row in item_definitions if _text(row.get("simcReadiness")) == "blocked"
            ),
            "blockedItemCount": sum(
                1 for row in item_definitions if _text(row.get("simcReadiness")) == "blocked"
            ),
            "blockedVariantCount": sum(
                1 for row in variant_rows if _text(row.get("simcReadiness")) == "blocked"
            ),
            "simcReadyCount": sum(
                1 for row in item_definitions if _text(row.get("simcReadiness")) == "ready"
            ),
            "simcReadyVariantCount": sum(
                1 for row in variant_rows if _text(row.get("simcReadiness")) == "ready"
            ),
            "simcBlockedVariantCount": sum(
                1 for row in variant_rows if _text(row.get("simcReadiness")) == "blocked"
            ),
            "simcExcludedVariantCount": sum(
                1 for row in variant_rows if _text(row.get("simcReadiness")) == "excluded"
            ),
            "craftedVariantTemplateSimcReadyCount": sum(
                1 for row in crafted_rows if _text(row.get("simcReadiness")) == "ready"
            ),
            "craftedVariantTemplateSimcBlockedCount": sum(
                1 for row in crafted_rows if _text(row.get("simcReadiness")) == "blocked"
            ),
        }
    )


def _validate_scope(inventory: Mapping[str, Any]) -> dict[str, Any]:
    scope = _mapping(inventory.get("scopeContract"), "inventory.scopeContract")
    logical_sources = [_text(value) for value in scope.get("logicalSources") or []]
    if set(logical_sources) != set(_LOGICAL_SOURCES) or len(logical_sources) != 4:
        raise S2EquipmentLibraryClosureError(
            "inventory scopeContract.logicalSources must be exactly the four equipment sources"
        )
    if scope.get("raidIncludesLair") is not True:
        raise S2EquipmentLibraryClosureError("raid must include lair at product level")
    if scope.get("lairRawSourceTypePreserved") is not True:
        raise S2EquipmentLibraryClosureError("raw lair source type must be preserved")
    if scope.get("tierSetIsIndependentMembershipDimension") is not True:
        raise S2EquipmentLibraryClosureError("tier_set must remain an independent membership dimension")
    excluded = sorted({_text(value) for value in scope.get("excludedSourceTypes") or []})
    if excluded != sorted(_EXCLUDED_SOURCE_TYPES):
        raise S2EquipmentLibraryClosureError(
            "inventory scopeContract.excludedSourceTypes does not match the fixed contract"
        )
    return {
        "logicalSources": list(_LOGICAL_SOURCES),
        "raidIncludesLair": True,
        "lairRawSourceTypePreserved": True,
        "tierSetIsIndependentMembershipDimension": True,
        "excludedSourceTypes": list(_EXCLUDED_SOURCE_TYPES),
    }


def _load_official_item_capture(
    capture_root: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    root = Path(capture_root).expanduser().resolve()
    try:
        manifest = json.loads((root / "capture-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise S2EquipmentLibraryClosureError("official item capture manifest is invalid") from error
    if manifest.get("status") not in {"captured", "partial"}:
        raise S2EquipmentLibraryClosureError("official item capture must be captured or partial")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise S2EquipmentLibraryClosureError("official item capture entries are required")

    items: dict[str, dict[str, Any]] = {}
    refs: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise S2EquipmentLibraryClosureError("official item capture entry is invalid")
        path = _text(entry.get("path"))
        match = re.fullmatch(r"/data/wow/item/([1-9][0-9]*)", path)
        if not match:
            continue
        item_id = str(int(match.group(1)))
        response_path = _safe_file(root, entry.get("responsePath"))
        body = response_path.read_bytes()
        if "responseBytes" in entry and len(body) != entry.get("responseBytes"):
            raise S2EquipmentLibraryClosureError(f"official item response byte drift: {path}")
        expected_hash = _text(entry.get("responseSha256"))
        if expected_hash and hashlib.sha256(body).hexdigest() != expected_hash:
            raise S2EquipmentLibraryClosureError(f"official item response hash drift: {path}")
        try:
            payload = _mapping(json.loads(body.decode("utf-8")), f"official item {path}")
        except (UnicodeDecodeError, ValueError) as error:
            raise S2EquipmentLibraryClosureError(f"official item response is invalid: {path}") from error
        if _text(payload.get("id")) != item_id:
            raise S2EquipmentLibraryClosureError(f"official item id mismatch: {path}")
        previous = items.get(item_id)
        if previous is not None and _canonical(previous) != _canonical(payload):
            raise S2EquipmentLibraryClosureError(f"official item payload conflict: {item_id}")
        items[item_id] = payload
        refs[item_id].extend(
            [
                f"official-api:{path}#/id",
                f"official-api-response:{root.name}/{Path(entry['responsePath']).as_posix()}",
            ]
        )
    return items, {key: sorted(set(value)) for key, value in refs.items()}, manifest


def _load_official_item_set_capture(
    capture_root: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    """Load only item-set responses from an already verified API capture."""

    root = Path(capture_root).expanduser().resolve()
    try:
        manifest = json.loads((root / "capture-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise S2EquipmentLibraryClosureError("official item-set capture manifest is invalid") from error
    if manifest.get("status") not in {"captured", "partial"}:
        raise S2EquipmentLibraryClosureError("official item-set capture must be captured or partial")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise S2EquipmentLibraryClosureError("official item-set capture entries are required")

    sets: dict[str, dict[str, Any]] = {}
    refs: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise S2EquipmentLibraryClosureError("official item-set capture entry is invalid")
        path = _text(entry.get("path"))
        match = re.fullmatch(r"/data/wow/item-set/([1-9][0-9]*)", path)
        if not match:
            continue
        set_id = str(int(match.group(1)))
        response_path = _safe_file(root, entry.get("responsePath"))
        body = response_path.read_bytes()
        if "responseBytes" in entry and len(body) != entry.get("responseBytes"):
            raise S2EquipmentLibraryClosureError(f"official item-set response byte drift: {path}")
        expected_hash = _text(entry.get("responseSha256"))
        if expected_hash and hashlib.sha256(body).hexdigest() != expected_hash:
            raise S2EquipmentLibraryClosureError(f"official item-set response hash drift: {path}")
        try:
            payload = _mapping(json.loads(body.decode("utf-8")), f"official item-set {path}")
        except (UnicodeDecodeError, ValueError) as error:
            raise S2EquipmentLibraryClosureError(f"official item-set response is invalid: {path}") from error
        if _text(payload.get("id")) != set_id:
            raise S2EquipmentLibraryClosureError(f"official item-set id mismatch: {path}")
        previous = sets.get(set_id)
        if previous is not None and _canonical(previous) != _canonical(payload):
            raise S2EquipmentLibraryClosureError(f"official item-set payload conflict: {set_id}")
        sets[set_id] = payload
        refs[set_id].extend(
            [
                f"official-api:{path}#/id",
                f"official-api:{path}#/effects",
                f"official-api-response:{root.name}/{Path(entry['responsePath']).as_posix()}",
            ]
        )
    return sets, {key: sorted(set(value)) for key, value in refs.items()}, manifest


def _load_db2_capture(
    capture_root: Path,
) -> tuple[dict[str, list[dict[str, Any]]], dict[tuple[str, str], list[str]], dict[str, Any]]:
    root = Path(capture_root).expanduser().resolve()
    try:
        manifest = json.loads((root / "capture-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise S2EquipmentLibraryClosureError("DB2 capture manifest is invalid") from error
    if manifest.get("status") != "captured":
        raise S2EquipmentLibraryClosureError("DB2 capture must be captured")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise S2EquipmentLibraryClosureError("DB2 capture entries are required")

    rows_by_table: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    refs: dict[tuple[str, str], list[str]] = defaultdict(list)
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise S2EquipmentLibraryClosureError("DB2 capture entry is invalid")
        table = _text(entry.get("table"))
        target_value = _text(entry.get("targetValue"))
        response_path_value = _text(entry.get("responsePath"))
        response_path = _safe_file(root, response_path_value)
        try:
            response = _mapping(json.loads(response_path.read_text(encoding="utf-8")), "DB2 response")
        except (OSError, ValueError) as error:
            raise S2EquipmentLibraryClosureError("DB2 response is invalid") from error
        if _text(response.get("table")) not in {"", table}:
            raise S2EquipmentLibraryClosureError(f"DB2 response table mismatch: {table}")
        response_rows = response.get("rows")
        if not isinstance(response_rows, list):
            raise S2EquipmentLibraryClosureError(f"DB2 response rows are missing: {table}")
        refs[(table, f"__query__:{_text(entry.get('filterField'))}:{target_value}")].append(
            f"db2-query:{root.name}/{response_path_value}#/rows"
        )
        for row_index, row in enumerate(response_rows):
            if not isinstance(row, Mapping):
                raise S2EquipmentLibraryClosureError(f"DB2 response row is invalid: {table}")
            normalized = dict(row)
            row_key = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            rows_by_table[table][row_key] = normalized
            refs[(table, row_key)].append(
                f"db2-response:{root.name}/{response_path_value}#/rows/{row_index}"
            )
    return (
        {table: list(values.values()) for table, values in rows_by_table.items()},
        {key: sorted(set(value)) for key, value in refs.items()},
        manifest,
    )


def _merge_db2_captures(
    captures: Mapping[str, Path] | None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[tuple[str, str], list[str]], dict[str, Any]]:
    merged: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    merged_refs: dict[tuple[str, str], set[str]] = defaultdict(set)
    manifests: dict[str, Any] = {}
    for label, capture_root in sorted((captures or {}).items()):
        rows, refs, manifest = _load_db2_capture(Path(capture_root))
        manifests[str(label)] = {
            "captureRoot": Path(capture_root).expanduser().resolve().name,
            "clientBuild": manifest.get("clientBuild"),
            "schemaRevision": manifest.get("schemaRevision"),
        }
        # Query-level refs are evidence even when the exact response has zero
        # rows.  Preserve them so an empty ItemXItemEffect query can prove
        # that the source item has no original special-effect relation.
        for ref_key, ref_values in refs.items():
            merged_refs[ref_key].update(ref_values)
        for table, table_rows in rows.items():
            for row in table_rows:
                key = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                merged[table][key] = row
                merged_refs[(table, key)].update(refs.get((table, key), []))
    return (
        {table: list(values.values()) for table, values in merged.items()},
        {key: sorted(value) for key, value in merged_refs.items()},
        manifests,
    )


def _index(rows: Mapping[str, Sequence[Mapping[str, Any]]], table: str, field: str) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows.get(table, []):
        value = row.get(field)
        if value in (None, "", 0, "0"):
            continue
        result[_text(value)].append(dict(row))
    return result


def _row_ref(
    row: Mapping[str, Any],
    *,
    table: str,
    refs: Mapping[tuple[str, str], list[str]],
) -> list[str]:
    if not isinstance(row, Mapping):
        return []
    key = json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return list(refs.get((table, key), []))


def _mythic_plus_cap_track_evidence(
    db2_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    db2_refs: Mapping[tuple[str, str], list[str]],
) -> dict[str, Any]:
    """Close the bounded M+ cap/track fact from one official DB2 chain.

    ``MythicPlusSeasonRewardLevels`` is not populated in the current DB2
    snapshot.  The item graph still exposes the source-side M+ level ranges,
    while each S2 upgrade group exposes rank entries, costs, and the named
    Mistcrest currency.  This adapter accepts that fallback only when the
    complete five-track cost chain and at least the observed lower/open-ended
    M+ ranges are present.  It never uses SimC or a guessed bonus id.
    """

    track_labels = {
        "adventurer": "Adventurer",
        "veteran": "Veteran",
        "champion": "Champion",
        "hero": "Hero",
        "myth": "Myth",
    }
    track_by_name = {
        label.lower(): key for key, label in track_labels.items()
    }
    refs: set[str] = set()
    failures: set[str] = set()
    group_rows_by_id = {
        _text(row.get("ID")): row
        for row in db2_rows.get("ItemBonusListGroup", [])
        if _text(row.get("ID"))
    }
    entries_by_group: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in db2_rows.get("ItemBonusListGroupEntry", []):
        group_id = _text(row.get("ItemBonusListGroupID"))
        if group_id:
            entries_by_group[group_id].append(row)
    costs_by_id = {
        _text(row.get("ID")): row
        for row in db2_rows.get("ItemExtendedCost", [])
        if _text(row.get("ID"))
    }
    currencies_by_id = {
        _text(row.get("ID")): row
        for row in db2_rows.get("CurrencyTypes", [])
        if _text(row.get("ID"))
    }

    track_facts: list[dict[str, Any]] = []
    for group_id in sorted(group_rows_by_id, key=lambda value: int(value)):
        group_row = group_rows_by_id[group_id]
        group_entries = sorted(
            entries_by_group.get(group_id, []),
            key=lambda row: (
                int(row.get("SequenceValue") or 0),
                int(row.get("ID") or 0),
            ),
        )
        if not group_entries:
            continue
        costs = [
            costs_by_id[_text(row.get("ItemExtendedCostID"))]
            for row in group_entries
            if _text(row.get("ItemExtendedCostID"))
            and _text(row.get("ItemExtendedCostID")) in costs_by_id
        ]
        missing_cost_ids = sorted(
            {
                _text(row.get("ItemExtendedCostID"))
                for row in group_entries
                if _text(row.get("ItemExtendedCostID"))
                and _text(row.get("ItemExtendedCostID")) not in costs_by_id
            },
            key=int,
        )
        if missing_cost_ids:
            failures.add("MYTHIC_PLUS_TRACK_COST_CHAIN_UNVERIFIED")
            continue
        currency_ids = sorted(
            {
                _text(cost.get("CurrencyID_0"))
                for cost in costs
                if _text(cost.get("CurrencyID_0"))
            },
            key=int,
        )
        if len(currency_ids) != 1:
            # Groups without a cost-bearing rank are not a public track fact.
            continue
        currency_id = currency_ids[0]
        currency = currencies_by_id.get(currency_id)
        if currency is None:
            failures.add("MYTHIC_PLUS_TRACK_CURRENCY_FACT_MISSING")
            continue
        name = _text(currency.get("Name_lang"))
        description = _text(currency.get("Description_lang"))
        if "Midnight Season 2" not in description:
            continue
        track_key = next(
            (
                key
                for key, label in track_labels.items()
                if name.startswith(f"{label} ")
            ),
            None,
        )
        if track_key is None:
            failures.add("MYTHIC_PLUS_TRACK_CURRENCY_NOT_S2")
            continue
        sequence_values = sorted(
            {
                int(row.get("SequenceValue"))
                for row in group_entries
                if isinstance(row.get("SequenceValue"), int)
                and not isinstance(row.get("SequenceValue"), bool)
                and int(row.get("SequenceValue")) > 0
            }
        )
        expected_sequence = list(range(1, max(sequence_values or [0]) + 1))
        if not sequence_values or sequence_values != expected_sequence:
            failures.add("MYTHIC_PLUS_TRACK_RANK_CHAIN_UNVERIFIED")
            continue
        for row in [group_row, *group_entries, *costs, currency]:
            refs.update(_row_ref(row, table="ItemBonusListGroup" if row is group_row else "ItemBonusListGroupEntry" if row in group_entries else "ItemExtendedCost" if row in costs else "CurrencyTypes", refs=db2_refs))
        track_facts.append(
            {
                "groupId": group_id,
                "trackKey": track_key,
                "currencyTypeId": currency_id,
                "currencyName": name,
                "currencyDescription": description,
                "rankCount": len(sequence_values),
                "maxRank": max(sequence_values),
                "status": "verified",
                "evidenceRefs": sorted(
                    set(
                        _row_ref(group_row, table="ItemBonusListGroup", refs=db2_refs)
                    )
                    | {
                        ref
                        for row in group_entries
                        for ref in _row_ref(
                            row,
                            table="ItemBonusListGroupEntry",
                            refs=db2_refs,
                        )
                    }
                    | {
                        ref
                        for row in costs
                        for ref in _row_ref(row, table="ItemExtendedCost", refs=db2_refs)
                    }
                    | set(_row_ref(currency, table="CurrencyTypes", refs=db2_refs))
                ),
            }
        )

    track_facts_by_key = {
        row["trackKey"]: row for row in track_facts
    }
    missing_tracks = sorted(set(track_labels) - set(track_facts_by_key))
    if missing_tracks:
        failures.add("MYTHIC_PLUS_TRACK_GROUP_FACT_MISSING")

    ranges: set[tuple[int, int | None]] = set()
    for row in db2_rows.get("ItemBonusTreeNode", []):
        context = _text(row.get("ItemContext"))
        group_id = _text(row.get("ChildItemBonusListGroupID"))
        if context not in _MYTHIC_PLUS_VARIANT_CONTEXT_VALUES or not group_id:
            continue
        if group_id not in {
            fact.get("groupId") for fact in track_facts
        }:
            # Historical/non-S2 branches remain in the raw graph and are
            # handled by per-variant scope exclusion.  They must not make the
            # current S2 cap/track fact look incomplete.
            continue
        try:
            minimum = int(row.get("MinMythicPlusLevel") or 0)
            maximum_raw = int(row.get("MaxMythicPlusLevel") or 0)
        except (TypeError, ValueError):
            failures.add("MYTHIC_PLUS_CAP_RANGE_UNVERIFIED")
            continue
        if minimum < 0 or maximum_raw < 0:
            failures.add("MYTHIC_PLUS_CAP_RANGE_UNVERIFIED")
            continue
        ranges.add((minimum, maximum_raw if maximum_raw > 0 else None))
        refs.update(_row_ref(row, table="ItemBonusTreeNode", refs=db2_refs))
    ordered_ranges = sorted(
        ([minimum, maximum] for minimum, maximum in ranges),
        key=lambda value: (value[0], value[1] is not None, value[1] or 0),
    )
    if not ordered_ranges:
        failures.add("MYTHIC_PLUS_CAP_RANGE_UNVERIFIED")
    elif not any(row[0] == 0 for row in ordered_ranges) or not any(
        row[1] is None for row in ordered_ranges
    ):
        failures.add("MYTHIC_PLUS_CAP_RANGE_UNVERIFIED")

    # The current M+ Journal pool contains legacy item identities as well as
    # current S2 identities.  A global Mistcrest cost chain proves the S2
    # tracks exist, but it does not prove that a legacy item root may use
    # those groups.  Keep the finite DisplaySeason -> ItemBonusSeason ->
    # ItemBonusSeasonBonusListGroup bridge as a separate fact so a missing
    # relation cannot be silently projected onto every old item.
    season_bridge: dict[str, Any] = {
        "status": "not_captured",
        "displaySeasonId": None,
        "milestoneSeasonId": None,
        "expansionId": None,
        "itemBonusSeasonId": None,
        "itemBonusSeasonRows": [],
        "itemBonusSeasonBonusListGroupRows": [],
        "projectedGroupIds": [],
        "reasonCode": "OFFICIAL_DB2_S2_SEASON_BRIDGE_NOT_CAPTURED",
        "evidenceRefs": [],
    }
    display_rows = [
        row
        for row in db2_rows.get("DisplaySeason", [])
        if _text(row.get("Season")) == "18"
    ]
    if display_rows:
        display_refs = {
            ref
            for row in display_rows
            for ref in _row_ref(row, table="DisplaySeason", refs=db2_refs)
        }
        if len(display_rows) != 1:
            season_bridge.update(
                {
                    "status": "UNVERIFIED",
                    "reasonCode": "OFFICIAL_DB2_S2_DISPLAY_SEASON_AMBIGUOUS",
                    "evidenceRefs": sorted(display_refs),
                }
            )
        else:
            display_row = display_rows[0]
            display_id = _text(display_row.get("ID"))
            season_id = _text(display_row.get("Season"))
            if not season_id.isdigit() or int(season_id) <= 0:
                season_bridge.update(
                    {
                        "status": "UNVERIFIED",
                        "displaySeasonId": display_id,
                        "milestoneSeasonId": season_id or None,
                        "expansionId": display_row.get("ExpansionID"),
                        "reasonCode": "OFFICIAL_DB2_DISPLAY_SEASON_VALUE_MISSING",
                        "evidenceRefs": sorted(
                            display_refs
                            | {
                                ref
                                for ref in _row_ref(
                                    display_row,
                                    table="DisplaySeason",
                                    refs=db2_refs,
                                )
                            }
                        ),
                    }
                )
                return {
                    "status": "UNVERIFIED" if failures else "verified",
                    "reasonCode": None if not failures else sorted(failures)[0],
                    "authority": "official_client_db2.ItemBonusTreeNode_plus_upgrade_cost_chain",
                    "trackKeys": sorted(track_facts_by_key),
                    "trackFacts": [track_facts_by_key[key] for key in sorted(track_facts_by_key)],
                    "missingTrackKeys": missing_tracks,
                    "mythicPlusLevelRanges": ordered_ranges,
                    "fallbackSeasonRewardLevelTable": "not_required_when_source_branch_and_cost_chain_verified",
                    "failureCodes": sorted(failures),
                    "evidenceRefs": sorted(refs),
                    "seasonBridge": season_bridge,
                    "legacyProjectionStatus": "UNVERIFIED",
                    "legacyProjectionReasonCode": season_bridge["reasonCode"],
                }
            item_bonus_rows = [
                row
                for row in db2_rows.get("ItemBonusSeason", [])
                if _text(row.get("SeasonID")) == season_id
            ]
            item_bonus_query_refs = set(
                db2_refs.get(
                    ("ItemBonusSeason", f"__query__:SeasonID:{season_id}"),
                    [],
                )
            )
            bridge_refs = display_refs | item_bonus_query_refs
            if len(item_bonus_rows) != 1:
                season_bridge.update(
                    {
                        "status": "verified_empty"
                        if not item_bonus_rows
                        else "UNVERIFIED",
                        "displaySeasonId": display_id,
                        "milestoneSeasonId": display_row.get("Season"),
                        "expansionId": display_row.get("ExpansionID"),
                        "itemBonusSeasonRows": [dict(row) for row in item_bonus_rows],
                        "reasonCode": (
                            "OFFICIAL_DB2_ITEM_BONUS_SEASON_RELATION_EMPTY"
                            if not item_bonus_rows
                            else "OFFICIAL_DB2_ITEM_BONUS_SEASON_RELATION_AMBIGUOUS"
                        ),
                        "evidenceRefs": sorted(bridge_refs),
                    }
                )
            else:
                item_bonus_row = item_bonus_rows[0]
                item_bonus_id = _text(item_bonus_row.get("ID"))
                group_rows = [
                    row
                    for row in db2_rows.get("ItemBonusSeasonBonusListGroup", [])
                    if _text(row.get("ItemBonusSeasonID")) == item_bonus_id
                ]
                group_query_refs = set(
                    db2_refs.get(
                        (
                            "ItemBonusSeasonBonusListGroup",
                            f"__query__:ItemBonusSeasonID:{item_bonus_id}",
                        ),
                        [],
                    )
                )
                bridge_refs.update(group_query_refs)
                group_ids = sorted(
                    {
                        _text(row.get("ItemBonusListGroupID"))
                        for row in group_rows
                        if _text(row.get("ItemBonusListGroupID"))
                    },
                    key=int,
                )
                bridge_refs.update(
                    ref
                    for row in group_rows
                    for ref in _row_ref(
                        row,
                        table="ItemBonusSeasonBonusListGroup",
                        refs=db2_refs,
                    )
                )
                s2_group_ids = {
                    _text(row.get("groupId"))
                    for row in track_facts
                    if _text(row.get("groupId"))
                }
                bridge_status = (
                    "verified"
                    if s2_group_ids and s2_group_ids <= set(group_ids)
                    else "UNVERIFIED"
                )
                season_bridge.update(
                    {
                        "status": bridge_status,
                        "displaySeasonId": display_id,
                        "milestoneSeasonId": display_row.get("Season"),
                        "expansionId": display_row.get("ExpansionID"),
                        "itemBonusSeasonId": item_bonus_id,
                        "itemBonusSeasonRows": [dict(item_bonus_row)],
                        "itemBonusSeasonBonusListGroupRows": [
                            dict(row) for row in group_rows
                        ],
                        "projectedGroupIds": group_ids,
                        "reasonCode": (
                            None
                            if bridge_status == "verified"
                            else "OFFICIAL_DB2_S2_ITEM_BONUS_SEASON_GROUP_BRIDGE_INCOMPLETE"
                        ),
                        "evidenceRefs": sorted(bridge_refs),
                    }
                )

    legacy_projection_status = (
        "verified"
        if season_bridge.get("status") == "verified"
        else "not_captured"
        if season_bridge.get("status") == "not_captured"
        else "UNVERIFIED"
    )
    legacy_projection_reason = (
        None
        if legacy_projection_status in {"verified", "not_captured"}
        else season_bridge.get("reasonCode")
    )

    status = "verified" if not failures else "UNVERIFIED"
    reason_code = None if status == "verified" else sorted(failures)[0]
    return {
        "status": status,
        "reasonCode": reason_code,
        "authority": "official_client_db2.ItemBonusTreeNode_plus_upgrade_cost_chain",
        "trackKeys": sorted(track_facts_by_key),
        "trackFacts": [
            track_facts_by_key[key]
            for key in sorted(track_facts_by_key)
        ],
        "missingTrackKeys": missing_tracks,
        "mythicPlusLevelRanges": ordered_ranges,
        "fallbackSeasonRewardLevelTable": "not_required_when_source_branch_and_cost_chain_verified",
        "failureCodes": sorted(failures),
        "evidenceRefs": sorted(refs),
        "seasonBridge": season_bridge,
        "legacyProjectionStatus": legacy_projection_status,
        "legacyProjectionReasonCode": legacy_projection_reason,
    }


def _item_static_facts(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(row, Mapping):
        return None
    facts: dict[str, Any] = {}
    for field in _CANONICAL_DB2_STATIC_FIELDS:
        if field in row:
            facts[field] = row[field]
    stats = []
    for index in range(10):
        field = f"StatModifier_bonusStat_{index}"
        value = row.get(field)
        if isinstance(value, int) and value >= 0:
            stats.append({"index": index, "bonusStat": value})
    facts["greenStatSlots"] = stats
    socket_fields_present = any(
        f"SocketType_{index}" in row for index in range(3)
    )
    if socket_fields_present:
        socket_count = 0
        for index in range(3):
            value = row.get(f"SocketType_{index}")
            try:
                if int(value or 0) > 0:
                    socket_count += 1
            except (TypeError, ValueError):
                continue
        facts["socketCount"] = socket_count
    return facts or None


def _item_class_facts(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Project the bounded Item table fields needed for SimC gear legality."""

    if not isinstance(row, Mapping):
        return None
    fields = (
        "ID",
        "ClassID",
        "SubclassID",
        "InventoryType",
        "CraftingQualityID",
        "ModifiedCraftingReagentItemID",
    )
    facts = {field: row[field] for field in fields if field in row}
    return facts or None


def _official_item_facts(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"status": "UNVERIFIED"}
    preview = payload.get("preview_item") if isinstance(payload.get("preview_item"), Mapping) else {}
    level = preview.get("level") if isinstance(preview.get("level"), Mapping) else {}
    return {
        "status": "verified",
        "name": _text(payload.get("name")),
        "isEquippable": payload.get("is_equippable") is True,
        "itemLevel": payload.get("level"),
        "previewItemLevel": level.get("value"),
        "previewBonusIds": [str(value) for value in preview.get("bonus_list") or []],
        "inventoryType": _text((payload.get("inventory_type") or {}).get("type")),
        "quality": _text((payload.get("quality") or {}).get("type")),
    }


def _official_item_set_facts(
    set_id: str,
    payload: Mapping[str, Any] | None,
    *,
    refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Normalize only set facts returned by the official item-set endpoint."""

    if not isinstance(payload, Mapping):
        return {
            "setId": set_id,
            "status": "UNVERIFIED",
            "name": None,
            "itemIds": [],
            "effects": [],
            "reasonCode": "OFFICIAL_ITEM_SET_FACT_MISSING",
            "evidenceRefs": sorted(set(refs)),
        }

    raw_items = payload.get("items")
    item_ids = []
    if isinstance(raw_items, list):
        for raw_item in raw_items:
            if not isinstance(raw_item, Mapping):
                continue
            value = raw_item.get("id")
            if value is None and isinstance(raw_item.get("item"), Mapping):
                value = raw_item["item"].get("id")
            if _ID_PATTERN.fullmatch(_text(value)):
                item_ids.append(str(int(_text(value))))

    effects = []
    valid = isinstance(payload.get("effects"), list)
    if valid:
        for raw_effect in payload.get("effects") or []:
            if not isinstance(raw_effect, Mapping):
                valid = False
                break
            required_count = raw_effect.get("required_count")
            display_string = _text(raw_effect.get("display_string"))
            if (
                isinstance(required_count, bool)
                or not isinstance(required_count, int)
                or required_count <= 0
                or not display_string
            ):
                valid = False
                break
            effects.append(
                {
                    "requiredCount": required_count,
                    "displayString": display_string,
                }
            )

    return {
        "setId": set_id,
        "status": "verified" if valid else "UNVERIFIED",
        "name": _text(payload.get("name")) or None,
        "itemIds": sorted(set(item_ids), key=int),
        "effects": effects,
        "reasonCode": None if valid else "OFFICIAL_ITEM_SET_EFFECT_FACT_INVALID",
        "evidenceRefs": sorted(set(refs)),
    }


def _equipment_scope(
    payload: Mapping[str, Any] | None,
    *,
    static_row: Mapping[str, Any] | None = None,
    has_bonus_tree: bool = False,
) -> tuple[str, str | None]:
    """Return a canonical combat-equipment slot and explicit exclusions.

    The four-source library contains acquisition memberships, but its item
    payload is a combat-equipment catalog.  Profession-only statless gear and
    level-one statless journal entries are retained as source evidence and
    excluded from the public combat catalog; neither exclusion creates a new
    logical source.
    """

    if not isinstance(payload, Mapping):
        return "", "OFFICIAL_ITEM_IDENTITY_UNVERIFIED"
    if payload.get("is_equippable") is not True:
        return "", "OUT_OF_SCOPE_NON_EQUIPMENT_ITEM"
    item_class = payload.get("item_class") if isinstance(payload.get("item_class"), Mapping) else {}
    item_subclass = payload.get("item_subclass") if isinstance(payload.get("item_subclass"), Mapping) else {}
    class_id = item_class.get("id")
    if str(class_id) not in {"2", "4"}:
        return "", "OUT_OF_SCOPE_PROFESSION_OR_NON_GEAR_ITEM_CLASS"
    if str(class_id) == "4" and str(item_subclass.get("id")) == "5":
        return "", "OUT_OF_SCOPE_NON_COMBAT_COSMETIC"
    preview = payload.get("preview_item") if isinstance(payload.get("preview_item"), Mapping) else {}
    preview_stats = preview.get("stats") if isinstance(preview.get("stats"), list) else []
    combat_stat_observed = False
    for stat in preview_stats:
        if not isinstance(stat, Mapping):
            continue
        stat_type = stat.get("type") if isinstance(stat.get("type"), Mapping) else {}
        stat_key = _text(stat_type.get("type") or stat_type.get("name")).upper()
        if stat_key and "PROFESSION" not in stat_key:
            combat_stat_observed = True
            break
    profession_requirement = (
        (preview.get("requirements") or {}).get("skill")
        if isinstance(preview.get("requirements"), Mapping)
        else None
    )
    if (
        str(class_id) == "4"
        and str(item_subclass.get("id")) == "0"
        and preview.get("is_subclass_hidden") is True
        and isinstance(profession_requirement, Mapping)
        and not combat_stat_observed
    ):
        return "", "OUT_OF_SCOPE_PROFESSION_ONLY_GEAR"
    preview_level = (
        preview.get("level", {}).get("value")
        if isinstance(preview.get("level"), Mapping)
        else None
    )
    static_level = static_row.get("ItemLevel") if isinstance(static_row, Mapping) else None
    preview_has_effect = any(
        isinstance(preview.get(key), list) and preview.get(key)
        for key in ("spells", "effects", "use_effects", "equip_effects", "item_effects")
    )
    if (
        isinstance(payload.get("level"), int)
        and payload.get("level") == 1
        and isinstance(preview_level, int)
        and preview_level == 1
        and isinstance(static_level, int)
        and static_level == 1
        and not has_bonus_tree
        and not combat_stat_observed
        and not preview_has_effect
    ):
        return "", "OUT_OF_SCOPE_STATLESS_LEVEL_ONE_ITEM"
    slot = item_slot_from_payload(dict(payload))
    if not slot:
        return "", "OUT_OF_SCOPE_NON_CANONICAL_GEAR_SLOT"
    return slot, None


def _reachable_tree_ids(
    root_ids: Sequence[str],
    nodes_by_parent: Mapping[str, Sequence[Mapping[str, Any]]],
) -> set[str]:
    result: set[str] = set()
    pending = [str(value) for value in root_ids if _ID_PATTERN.fullmatch(str(value))]
    while pending:
        tree_id = pending.pop()
        if tree_id in result:
            continue
        result.add(tree_id)
        for node in nodes_by_parent.get(tree_id, []):
            child = _text(node.get("ChildItemBonusTreeID"))
            if child and child != "0":
                pending.append(child)
    return result


def _item_scaling_evidence(
    item_id: str,
    *,
    db2_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    db2_refs: Mapping[tuple[str, str], list[str]],
) -> tuple[list[dict[str, Any]], list[str], str | None]:
    item_tree_rows = [row for row in db2_rows.get("ItemXBonusTree", []) if _text(row.get("ItemID")) == item_id]
    root_ids = [_text(row.get("ItemBonusTreeID")) for row in item_tree_rows]
    nodes_by_parent = _index(db2_rows, "ItemBonusTreeNode", "ParentItemBonusTreeID")
    nodes_by_id = _index(db2_rows, "ItemBonusTreeNode", "ID")
    tree_ids = _reachable_tree_ids(root_ids, nodes_by_parent)
    nodes = [row for tree_id in tree_ids for row in nodes_by_parent.get(tree_id, [])]
    bonus_list_ids: set[str] = set()
    group_ids: set[str] = set()
    for node in nodes:
        direct = _text(node.get("ChildItemBonusListID"))
        group = _text(node.get("ChildItemBonusListGroupID"))
        if direct and direct != "0":
            bonus_list_ids.add(direct)
        if group and group != "0":
            group_ids.add(group)
    group_rows = [
        row for row in db2_rows.get("ItemBonusListGroupEntry", [])
        if _text(row.get("ItemBonusListGroupID")) in group_ids
    ]
    bonus_list_ids.update(
        _text(row.get("ItemBonusListID"))
        for row in group_rows
        if _text(row.get("ItemBonusListID"))
    )
    bonus_rows = [
        row for row in db2_rows.get("ItemBonus", [])
        if _text(row.get("ParentItemBonusListID")) in bonus_list_ids
        and _text(row.get("Type")) in {"49", "51"}
    ]
    scaling_by_id = {
        _text(row.get("ID")): row
        for row in db2_rows.get("ItemScalingConfig", [])
        if _text(row.get("ID"))
    }
    offset_curve_by_id = {
        _text(row.get("ID")): row
        for row in db2_rows.get("ItemOffsetCurve", [])
        if _text(row.get("ID"))
    }
    curve_by_id = {
        _text(row.get("ID")): row
        for row in db2_rows.get("Curve", [])
        if _text(row.get("ID"))
    }
    curve_points_by_curve_id = _index(db2_rows, "CurvePoint", "CurveID")
    evidence = []
    evidence_refs: set[str] = set()
    for bonus in sorted(bonus_rows, key=lambda row: (_text(row.get("ParentItemBonusListID")), int(row.get("ID") or 0))):
        scaling_id = _text(bonus.get("Value_0"))
        scaling = scaling_by_id.get(scaling_id)
        refs = set(_row_ref(bonus, table="ItemBonus", refs=db2_refs))
        if scaling is not None:
            refs.update(_row_ref(scaling, table="ItemScalingConfig", refs=db2_refs))
        item_level = scaling.get("ItemLevel") if scaling else None
        item_offset_curve_id = _text(scaling.get("ItemOffsetCurveID")) if scaling else ""
        offset_curve = offset_curve_by_id.get(item_offset_curve_id)
        if offset_curve is not None:
            refs.update(_row_ref(offset_curve, table="ItemOffsetCurve", refs=db2_refs))
        curve_id = _text(offset_curve.get("CurveID")) if offset_curve else ""
        curve = curve_by_id.get(curve_id)
        if curve is not None:
            refs.update(_row_ref(curve, table="Curve", refs=db2_refs))
        curve_points = sorted(
            curve_points_by_curve_id.get(curve_id, []),
            key=lambda row: (
                int(row.get("OrderIndex") or 0),
                int(row.get("ID") or 0),
            ),
        ) if curve_id else []
        for point in curve_points:
            refs.update(_row_ref(point, table="CurvePoint", refs=db2_refs))
        if isinstance(item_level, int) and item_level > 0:
            curve_evidence_status = "not_required"
            curve_reason_code = None
            entry_status = "verified"
        elif scaling is None:
            curve_evidence_status = "UNVERIFIED"
            curve_reason_code = "ITEM_SCALING_CONFIG_MISSING"
            entry_status = "UNVERIFIED"
        elif not item_offset_curve_id or item_offset_curve_id == "0":
            curve_evidence_status = "UNVERIFIED"
            curve_reason_code = "ITEM_SCALING_NUMERIC_LEVEL_MISSING"
            entry_status = "UNVERIFIED"
        elif offset_curve is None:
            curve_evidence_status = "UNVERIFIED"
            curve_reason_code = "ITEM_OFFSET_CURVE_MISSING"
            entry_status = "UNVERIFIED"
        elif curve is None:
            curve_evidence_status = "UNVERIFIED"
            curve_reason_code = "CURVE_MISSING"
            entry_status = "UNVERIFIED"
        elif not curve_points:
            curve_evidence_status = "UNVERIFIED"
            curve_reason_code = "CURVE_POINTS_MISSING"
            entry_status = "UNVERIFIED"
        else:
            # The points prove that the bounded graph is present, but not the
            # official client formula or public track label that consumes it.
            curve_evidence_status = "observed"
            curve_reason_code = "ITEM_SCALING_CURVE_FORMULA_UNVERIFIED"
            entry_status = "UNVERIFIED"
        evidence_refs.update(refs)
        evidence.append(
            {
                "bonusId": _text(bonus.get("ID")),
                "bonusListId": _text(bonus.get("ParentItemBonusListID")),
                "type": int(bonus.get("Type")),
                "scalingConfigId": scaling_id,
                "itemLevel": item_level,
                "itemOffsetCurveId": item_offset_curve_id or None,
                "curveId": curve_id or None,
                "curveEvidenceStatus": curve_evidence_status,
                "curveReasonCode": curve_reason_code,
                "curvePoints": [dict(point) for point in curve_points],
                "status": entry_status,
                "evidenceRefs": sorted(refs),
            }
        )
    root_ref = ",".join(sorted(set(root_ids), key=int)) if root_ids else None
    return evidence, sorted(evidence_refs), root_ref


_VARIANT_NODE_FIELDS = (
    "ID",
    "ParentItemBonusTreeID",
    "ItemContext",
    "ChildItemBonusTreeID",
    "ChildItemBonusListID",
    "ChildItemBonusListGroupID",
    "ChildItemLevelSelectorID",
    "IblGroupPointsModSetID",
    "MinMythicPlusLevel",
    "MaxMythicPlusLevel",
    "ItemCreationContextGroupID",
    "Flags",
)


def _variant_node_facts(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "nodeId": _text(row.get("ID")),
        "itemContext": row.get("ItemContext", 0),
        "minMythicPlusLevel": row.get("MinMythicPlusLevel", 0),
        "maxMythicPlusLevel": row.get("MaxMythicPlusLevel", 0),
        "itemCreationContextGroupId": row.get("ItemCreationContextGroupID", 0),
    }


# These map ids are the bounded source-context targets derived from the
# captured official Journal instance payloads.  They are not a second source
# inventory: they only bind the raw DB2 ItemContext graph to the four-source
# product scope already frozen in the official inventory.
_SOURCE_CONTEXT_MAP_IDS = {
    "mythic_plus": ("1762", "1877", "2521", "2813", "2825", "2859", "2923", "2993"),
    "raid": ("2987", "3004"),
}
_MYTHIC_PLUS_DIFFICULTY_ID = "8"
_MYTHIC_PLUS_ITEM_CONTEXT = "16"
_RAID_DIFFICULTY_IDS = {"14", "15", "16", "17", "220", "233", "241", "250"}

# ItemContext is a property of an official bonus-tree branch, not a product
# source by itself.  Keep the source families explicit: a newly observed
# context remains blocked until its meaning is added with evidence.
_MYTHIC_PLUS_VARIANT_CONTEXT_VALUES = {"16", "33", "34", "87"}
_RAID_VARIANT_CONTEXT_VALUES = {
    "0",
    "3",
    "4",
    "5",
    "6",
    "82",
    "83",
    "84",
    "85",
    "89",
    "90",
    "91",
    "92",
    "93",
    "94",
    "95",
    "96",
    "149",
    "150",
    "151",
    "152",
    "153",
    "154",
    "155",
    "156",
    "157",
    "158",
}
_DUNGEON_VARIANT_CONTEXT_VALUES = {"1", "2", "23"}
_OUT_OF_SCOPE_CONTEXT_REASONS = {
    "35": "OUT_OF_SCOPE_GREAT_VAULT_PROJECTION_VARIANT",
    "81": "OUT_OF_SCOPE_WORLD_BOSS_VARIANT",
}


def _variant_source_eligibility(
    variant: Mapping[str, Any],
    *,
    memberships: Sequence[Mapping[str, Any]],
    db2_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    db2_refs: Mapping[tuple[str, str], list[str]],
) -> dict[str, Any]:
    """Bind a raw variant to source-context facts without inferring tracks.

    The official Journal membership identifies the item/source edge.  The
    bounded MapDifficulty capture identifies the legal source context.  A
    branch is never promoted merely because SimC accepts its bonus vector.
    Crafted and tier-set memberships do not use MapDifficulty, so they remain
    explicitly ``not_required`` in this adapter and are governed by their own
    relationship evidence.
    """

    source_names = sorted(
        {
            _text(row.get("logicalSource"))
            for row in memberships
            if _text(row.get("logicalSource")) in {"mythic_plus", "raid", "crafted", "tier_set"}
        }
    )
    context_values = sorted(
        {
            _text(value)
            for value in variant.get("itemContextValues") or []
            if _text(value)
        },
        key=lambda value: (0, int(value)) if value.isdigit() else (1, value),
    )
    by_source: dict[str, dict[str, Any]] = {}
    reason_codes: set[str] = set()
    evidence_refs: set[str] = set()

    map_rows = [
        dict(row)
        for row in db2_rows.get("MapDifficulty", [])
        if isinstance(row, Mapping)
    ]
    def context_value_text(value: Any) -> str:
        return "" if value is None else str(value).strip()

    context_rows = [
        dict(row)
        for row in db2_rows.get("ItemCreationContext", [])
        if isinstance(row, Mapping)
    ]
    context_facts_by_value: dict[str, list[dict[str, Any]]] = {}
    for row in context_rows:
        value = context_value_text(row.get("ItemContext"))
        if value:
            context_facts_by_value.setdefault(value, []).append(row)

    def context_evidence(
        values: Sequence[str],
    ) -> tuple[list[dict[str, Any]], set[str]]:
        facts: list[dict[str, Any]] = []
        refs: set[str] = set()
        for value in values:
            if value == "0":
                facts.append(
                    {
                        "itemContext": value,
                        "status": "verified",
                        "authority": "MapDifficulty_default_context",
                        "rows": [],
                        "evidenceRefs": [],
                    }
                )
                continue
            rows = context_facts_by_value.get(value, [])
            row_refs = {
                ref
                for row in rows
                for ref in _row_ref(row, table="ItemCreationContext", refs=db2_refs)
            }
            refs.update(row_refs)
            facts.append(
                {
                    "itemContext": value,
                    "status": "verified" if rows else "UNVERIFIED",
                    "rows": rows,
                    "evidenceRefs": sorted(row_refs),
                }
            )
        return facts, refs

    def classify_contexts(
        *,
        source: str,
        observed_values: Sequence[str],
    ) -> tuple[str, str | None, list[dict[str, Any]], set[str]]:
        values = list(observed_values) or (["0"] if source == "raid" else [])
        allowed = (
            _MYTHIC_PLUS_VARIANT_CONTEXT_VALUES
            if source == "mythic_plus"
            else _RAID_VARIANT_CONTEXT_VALUES
        )
        excluded: dict[str, str] = dict(_OUT_OF_SCOPE_CONTEXT_REASONS)
        if source == "mythic_plus":
            excluded.update(
                {
                    value: "OUT_OF_SCOPE_RAID_VARIANT"
                    for value in _RAID_VARIANT_CONTEXT_VALUES
                    if value != "0"
                }
            )
        else:
            excluded.update(
                {
                    value: "OUT_OF_SCOPE_MYTHIC_PLUS_VARIANT"
                    for value in _MYTHIC_PLUS_VARIANT_CONTEXT_VALUES
                }
            )
        excluded.update(
            {
                value: "OUT_OF_SCOPE_DUNGEON_VARIANT"
                for value in _DUNGEON_VARIANT_CONTEXT_VALUES
            }
        )

        facts, refs = context_evidence(values)

        # The client enum table is sparse for some legacy Challenge Mode
        # values (notably 34 and 87).  When the exact variant branch carries
        # the value on an official ItemBonusTreeNode row, that row is the
        # field-level DB2 owner for the observed enum value.  This promotion
        # is limited to the frozen source-policy allowlist; unknown values
        # still require an ItemCreationContext fact and remain fail-closed.
        direct_context_facts: dict[str, dict[str, Any]] = {}
        node_path = variant.get("nodePath")
        if isinstance(node_path, Sequence) and not isinstance(node_path, (str, bytes)):
            for value in values:
                if value not in allowed or context_facts_by_value.get(value):
                    continue
                node_rows = [
                    dict(row)
                    for node in node_path
                    if isinstance(node, Mapping)
                    and _text(node.get("itemContext")) == value
                    for row in db2_rows.get("ItemBonusTreeNode", [])
                    if _text(row.get("ID")) == _text(node.get("nodeId"))
                    and _text(row.get("ItemContext")) == value
                ]
                if not node_rows:
                    continue
                node_refs = {
                    ref
                    for row in node_rows
                    for ref in _row_ref(row, table="ItemBonusTreeNode", refs=db2_refs)
                }
                direct_context_facts[value] = {
                    "itemContext": value,
                    "status": "verified",
                    "authority": (
                        "official_client_db2.ItemBonusTreeNode.ItemContext_plus_frozen_scope_enum"
                    ),
                    "rows": node_rows,
                    "evidenceRefs": sorted(node_refs),
                }
                refs.update(node_refs)
        if direct_context_facts:
            facts = [
                direct_context_facts.get(_text(fact.get("itemContext")), fact)
                for fact in facts
            ]
        missing_allowed_values = {
            row["itemContext"]
            for row in facts
            if row.get("itemContext") in allowed and row.get("status") != "verified"
        }
        if missing_allowed_values:
            return (
                "UNVERIFIED",
                "OFFICIAL_DB2_ITEM_CREATION_CONTEXT_FACT_MISSING",
                facts,
                refs,
            )

        # A raw bonus-tree can contain branches for other acquisition paths.
        # They stay in the evidence graph, but are explicitly excluded from
        # this item/source membership when their context is not one of this
        # source's allowed contexts.  This is a scope decision, not a claim
        # that the branch is a legal variant of the current source.
        excluded.update(
            {
                value: (
                    "OUT_OF_SCOPE_RAID_VARIANT"
                    if source == "mythic_plus" and value in _RAID_VARIANT_CONTEXT_VALUES
                    else "OUT_OF_SCOPE_MYTHIC_PLUS_VARIANT"
                    if source == "raid" and value in _MYTHIC_PLUS_VARIANT_CONTEXT_VALUES
                    else "OUT_OF_SCOPE_NON_SOURCE_CONTEXT_VARIANT"
                )
                for value in values
                if value not in allowed and value not in excluded
            }
        )

        if not values:
            return (
                "UNVERIFIED",
                (
                    "MYTHIC_PLUS_VARIANT_ITEM_CONTEXT_UNVERIFIED"
                    if source == "mythic_plus"
                    else "RAID_VARIANT_ITEM_CONTEXT_UNVERIFIED"
                ),
                facts,
                refs,
            )
        if all(value in allowed for value in values):
            return "verified", None, facts, refs
        if all(value in excluded for value in values):
            reasons = sorted({excluded[value] for value in values})
            return (
                "excluded",
                reasons[0] if len(reasons) == 1 else "OUT_OF_SCOPE_MIXED_VARIANT",
                facts,
                refs,
            )
        return (
            "UNVERIFIED",
            (
                "MYTHIC_PLUS_VARIANT_ITEM_CONTEXT_UNVERIFIED"
                if source == "mythic_plus"
                else "RAID_VARIANT_ITEM_CONTEXT_UNVERIFIED"
            ),
            facts,
            refs,
        )

    for source in source_names:
        if source in {"crafted", "tier_set"}:
            by_source[source] = {
                "status": "not_required",
                "mapIds": [],
                "requiredItemContextValues": [],
                "observedItemContextValues": context_values,
                "itemCreationContextEvidence": [],
                "evidenceRefs": [],
            }
            continue

        map_ids = _SOURCE_CONTEXT_MAP_IDS[source]
        scoped_rows = [
            row for row in map_rows if _text(row.get("MapID")) in set(map_ids)
        ]
        refs = {
            ref
            for row in scoped_rows
            for ref in _row_ref(row, table="MapDifficulty", refs=db2_refs)
        }
        evidence_refs.update(refs)
        if source == "mythic_plus":
            valid_rows = [
                row
                for row in scoped_rows
                if _text(row.get("DifficultyID")) == _MYTHIC_PLUS_DIFFICULTY_ID
                and context_value_text(row.get("ItemContext")) == _MYTHIC_PLUS_ITEM_CONTEXT
            ]
            required_contexts = [_MYTHIC_PLUS_ITEM_CONTEXT]
            allowed_contexts = _MYTHIC_PLUS_VARIANT_CONTEXT_VALUES
        else:
            valid_rows = [
                row
                for row in scoped_rows
                if _text(row.get("DifficultyID")) in _RAID_DIFFICULTY_IDS
                and context_value_text(row.get("ItemContext")) == "0"
            ]
            required_contexts = ["0"]
            allowed_contexts = _RAID_VARIANT_CONTEXT_VALUES

        context_status, context_reason, context_facts, context_refs = classify_contexts(
            source=source,
            observed_values=context_values,
        )
        evidence_refs.update(context_refs)
        map_status = (
            "verified"
            if len({_text(row.get("MapID")) for row in valid_rows}) == len(map_ids)
            else "UNVERIFIED"
        )
        status = context_status if map_status == "verified" else "UNVERIFIED"
        source_reason = context_reason
        if map_status != "verified":
            source_reason = (
                "OFFICIAL_DB2_SOURCE_CONTEXT_MAP_DIFFICULTY_INCOMPLETE"
                if source == "mythic_plus"
                else "OFFICIAL_DB2_RAID_CONTEXT_MAP_DIFFICULTY_INCOMPLETE"
            )
        if source_reason:
            reason_codes.add(source_reason)
        by_source[source] = {
            "status": status,
            "mapIds": list(map_ids),
            "mapEvidenceStatus": map_status,
            "requiredItemContextValues": required_contexts,
            "observedItemContextValues": context_values,
            "itemCreationContextEvidence": context_facts,
            "allowedItemContextValues": sorted(allowed_contexts, key=int),
            "validDifficultyIds": sorted(
                {_text(row.get("DifficultyID")) for row in valid_rows},
                key=int,
            ),
            "reasonCode": source_reason,
            "evidenceRefs": sorted(refs | context_refs),
        }

    statuses = [row.get("status") for row in by_source.values()]
    if not source_names:
        overall_status = "not_applicable"
    elif all(status == "not_required" for status in statuses):
        overall_status = "not_required"
    elif any(status == "UNVERIFIED" for status in statuses):
        overall_status = "UNVERIFIED"
    elif any(status == "verified" for status in statuses):
        # A variant can be attached to more than one product source.  A
        # source-specific exclusion is not a blocker when another official
        # source proves the same raw variant legal; the per-source evidence is
        # retained above for coverage and audit.
        overall_status = "verified"
    elif all(status in {"excluded", "not_required"} for status in statuses):
        overall_status = "excluded"
    else:
        overall_status = "UNVERIFIED"
    return {
        "status": overall_status,
        "bySource": by_source,
        "observedItemContextValues": context_values,
        "reasonCodes": sorted(reason_codes),
        "evidenceRefs": sorted(evidence_refs),
    }


def _variant_scaling_fact(
    bonus: Mapping[str, Any],
    *,
    db2_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    db2_refs: Mapping[tuple[str, str], list[str]],
) -> tuple[dict[str, Any], set[str]]:
    scaling_id = _text(bonus.get("Value_0"))
    scaling = next(
        (
            row
            for row in db2_rows.get("ItemScalingConfig", [])
            if _text(row.get("ID")) == scaling_id
        ),
        None,
    )
    refs = set(_row_ref(bonus, table="ItemBonus", refs=db2_refs))
    if scaling is not None:
        refs.update(_row_ref(scaling, table="ItemScalingConfig", refs=db2_refs))
    item_level = scaling.get("ItemLevel") if scaling else None
    offset_id = _text(scaling.get("ItemOffsetCurveID")) if scaling else ""
    offset = next(
        (
            row
            for row in db2_rows.get("ItemOffsetCurve", [])
            if _text(row.get("ID")) == offset_id
        ),
        None,
    )
    if offset is not None:
        refs.update(_row_ref(offset, table="ItemOffsetCurve", refs=db2_refs))
    curve_id = _text(offset.get("CurveID")) if offset else ""
    curve = next(
        (
            row
            for row in db2_rows.get("Curve", [])
            if _text(row.get("ID")) == curve_id
        ),
        None,
    )
    if curve is not None:
        refs.update(_row_ref(curve, table="Curve", refs=db2_refs))
    points = sorted(
        [
            row
            for row in db2_rows.get("CurvePoint", [])
            if _text(row.get("CurveID")) == curve_id
        ],
        key=lambda row: (int(row.get("OrderIndex") or 0), int(row.get("ID") or 0)),
    ) if curve_id else []
    for point in points:
        refs.update(_row_ref(point, table="CurvePoint", refs=db2_refs))

    if isinstance(item_level, int) and item_level > 0:
        curve_status = "not_required"
        reason_code = None
        status = "verified"
    elif scaling is None:
        curve_status = "UNVERIFIED"
        reason_code = "ITEM_SCALING_CONFIG_MISSING"
        status = "UNVERIFIED"
    elif not offset_id or offset_id == "0":
        curve_status = "UNVERIFIED"
        reason_code = "ITEM_SCALING_NUMERIC_LEVEL_MISSING"
        status = "UNVERIFIED"
    elif offset is None:
        curve_status = "UNVERIFIED"
        reason_code = "ITEM_OFFSET_CURVE_MISSING"
        status = "UNVERIFIED"
    elif curve is None:
        curve_status = "UNVERIFIED"
        reason_code = "CURVE_MISSING"
        status = "UNVERIFIED"
    elif not points:
        curve_status = "UNVERIFIED"
        reason_code = "CURVE_POINTS_MISSING"
        status = "UNVERIFIED"
    else:
        curve_status = "observed"
        reason_code = "ITEM_SCALING_CURVE_FORMULA_UNVERIFIED"
        status = "UNVERIFIED"
    return (
        {
            "bonusId": _text(bonus.get("ID")),
            "bonusListId": _text(bonus.get("ParentItemBonusListID")),
            "type": int(bonus.get("Type") or 0),
            "scalingConfigId": scaling_id,
            "itemLevel": item_level,
            "itemOffsetCurveId": offset_id or None,
            "curveId": curve_id or None,
            "curveEvidenceStatus": curve_status,
            "curveReasonCode": reason_code,
            "curvePointIds": [_text(point.get("ID")) for point in points],
            "status": status,
            "evidenceRefs": sorted(refs),
        },
        refs,
    )


def _variant_selector_facts(
    selector_id: str,
    *,
    db2_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    db2_refs: Mapping[tuple[str, str], list[str]],
) -> tuple[dict[str, Any], set[str]]:
    selector = next(
        (
            row
            for row in db2_rows.get("ItemLevelSelector", [])
            if _text(row.get("ID")) == selector_id
        ),
        None,
    )
    refs: set[str] = set()
    if selector is not None:
        refs.update(_row_ref(selector, table="ItemLevelSelector", refs=db2_refs))
    quality_set_id = _text(selector.get("ItemLevelSelectorQualitySetID")) if selector else ""
    quality_set = next(
        (
            row
            for row in db2_rows.get("ItemLevelSelectorQualitySet", [])
            if _text(row.get("ID")) == quality_set_id
        ),
        None,
    )
    if quality_set is not None:
        refs.update(_row_ref(quality_set, table="ItemLevelSelectorQualitySet", refs=db2_refs))
    qualities = [
        row
        for row in db2_rows.get("ItemLevelSelectorQuality", [])
        if _text(row.get("ParentILSQualitySetID")) == quality_set_id
    ]
    for row in qualities:
        refs.update(_row_ref(row, table="ItemLevelSelectorQuality", refs=db2_refs))
    return (
        {
            "selectorId": selector_id,
            "status": "verified" if selector and quality_set and qualities else "UNVERIFIED",
            "minItemLevel": selector.get("MinItemLevel") if selector else None,
            "qualitySet": dict(quality_set) if quality_set else None,
            "qualityOptions": [dict(row) for row in sorted(qualities, key=lambda row: int(row.get("ID") or 0))],
            "evidenceRefs": sorted(refs),
        },
        refs,
    )


def _build_item_variant_records(
    item_id: str,
    *,
    db2_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    db2_refs: Mapping[tuple[str, str], list[str]],
    official_payload: Mapping[str, Any] | None = None,
    composition_context_values: Sequence[str] | None = None,
    static_item_level: Any = None,
    allow_empty_base_variant: bool = False,
    allow_raid_base_numeric_evidence: bool = False,
    allow_default_context_group_resolution: bool = False,
    allow_default_context_numeric_evidence: bool = False,
) -> list[dict[str, Any]]:
    item_roots = sorted(
        {
            _text(row.get("ItemBonusTreeID"))
            for row in db2_rows.get("ItemXBonusTree", [])
            if _text(row.get("ItemID")) == item_id and _text(row.get("ItemBonusTreeID"))
        },
        key=int,
    )
    nodes_by_parent = _index(db2_rows, "ItemBonusTreeNode", "ParentItemBonusTreeID")
    nodes_by_id = _index(db2_rows, "ItemBonusTreeNode", "ID")
    group_entries_by_group = _index(db2_rows, "ItemBonusListGroupEntry", "ItemBonusListGroupID")
    group_facts_by_id = _index(db2_rows, "ItemBonusListGroup", "ID")
    scaling_entries_by_group = _index(
        db2_rows,
        "ItemGroupIlvlScalingEntry",
        "ItemGroupIlvlScalingID",
    )
    conditions_by_id = _index(db2_rows, "PlayerCondition", "ID")
    bonus_rows_by_list = _index(db2_rows, "ItemBonus", "ParentItemBonusListID")
    level_delta_rows_by_list = _index(db2_rows, "ItemBonusListLevelDelta", "ID")
    item_bonus_list_ids = {
        _text(row.get("ID"))
        for row in db2_rows.get("ItemBonusList", [])
        if _text(row.get("ID"))
    }

    def choices_for_node(node: Mapping[str, Any]) -> list[dict[str, Any]]:
        direct = _text(node.get("ChildItemBonusListID"))
        if direct and direct != "0":
            return [{"kind": "direct", "bonusListIds": [direct]}]
        group = _text(node.get("ChildItemBonusListGroupID"))
        if group and group != "0":
            entries = sorted(
                group_entries_by_group.get(group, []),
                key=lambda row: (
                    int(row.get("SequenceValue") or 0),
                    int(row.get("ID") or 0),
                ),
            )
            if not entries:
                return [{"kind": "group", "groupId": group, "bonusListIds": []}]
            choices = []
            for entry in entries:
                selector_id = _text(entry.get("ItemLevelSelectorID"))
                choices.append(
                    {
                        "kind": "group",
                        "groupId": group,
                        "groupEntry": dict(entry),
                        "bonusListIds": [_text(entry.get("ItemBonusListID"))]
                        if _text(entry.get("ItemBonusListID"))
                        else [],
                        "selectorFacts": (
                            _variant_selector_facts(
                                selector_id,
                                db2_rows=db2_rows,
                                db2_refs=db2_refs,
                            )[0]
                            if selector_id
                            else None
                        ),
                    }
                )
            return choices
        selector_id = _text(node.get("ChildItemLevelSelectorID"))
        if selector_id and selector_id != "0":
            selector_facts, _selector_refs = _variant_selector_facts(
                selector_id,
                db2_rows=db2_rows,
                db2_refs=db2_refs,
            )
            quality_options = selector_facts.get("qualityOptions") or []
            if quality_options:
                return [
                    {
                        "kind": "selector",
                        "selectorFacts": selector_facts,
                        "bonusListIds": [
                            _text(option.get("QualityItemBonusListID"))
                        ]
                        if _text(option.get("QualityItemBonusListID"))
                        else [],
                    }
                    for option in quality_options
                ]
            return [{"kind": "selector", "selectorFacts": selector_facts, "bonusListIds": []}]
        return [{"kind": "empty", "bonusListIds": []}]

    def walk(
        tree_id: str,
        node_path: list[dict[str, Any]],
        active_tree_ids: set[str],
        component_id: str,
        root_tree_id: str,
    ) -> list[dict[str, Any]]:
        if tree_id in active_tree_ids:
            return [
                {
                    "rootTreeId": root_tree_id,
                    "treeId": tree_id,
                    "componentId": component_id,
                    "nodePath": list(node_path),
                    "choice": {"kind": "cycle", "bonusListIds": []},
                }
            ]
        nodes = sorted(
            nodes_by_parent.get(tree_id, []),
            key=lambda row: int(row.get("ID") or 0),
        )
        if not nodes:
            return [
                {
                    "rootTreeId": root_tree_id,
                    "treeId": tree_id,
                    "componentId": component_id,
                    "nodePath": list(node_path),
                    "choice": {"kind": "missing_tree_nodes", "bonusListIds": []},
                }
            ]
        result: list[dict[str, Any]] = []
        for node in nodes:
            current_path = [*node_path, _variant_node_facts(node)]
            child_tree = _text(node.get("ChildItemBonusTreeID"))
            if child_tree and child_tree != "0":
                result.extend(
                    walk(
                        child_tree,
                        current_path,
                        active_tree_ids | {tree_id},
                        component_id,
                        root_tree_id,
                    )
                )
                continue
            for choice in choices_for_node(node):
                result.append(
                    {
                        "rootTreeId": root_tree_id,
                        "treeId": tree_id,
                        "componentId": component_id,
                        "nodePath": current_path,
                        "choice": choice,
                    }
                )
        return result

    raw_branches: list[dict[str, Any]] = []
    for root_tree_id in item_roots:
        container_tree_id = root_tree_id
        prefix_path: list[dict[str, Any]] = []
        active_tree_ids: set[str] = set()
        while True:
            nodes = sorted(
                nodes_by_parent.get(container_tree_id, []),
                key=lambda row: int(row.get("ID") or 0),
            )
            if len(nodes) != 1:
                break
            child_tree = _text(nodes[0].get("ChildItemBonusTreeID"))
            if not child_tree or child_tree == "0":
                break
            prefix_path.append(_variant_node_facts(nodes[0]))
            active_tree_ids.add(container_tree_id)
            container_tree_id = child_tree

        component_nodes = sorted(
            nodes_by_parent.get(container_tree_id, []),
            key=lambda row: int(row.get("ID") or 0),
        )
        if not component_nodes:
            raw_branches.extend(
                walk(
                    container_tree_id,
                    prefix_path,
                    active_tree_ids,
                    f"tree:{container_tree_id}",
                    root_tree_id,
                )
            )
            continue
        for node in component_nodes:
            current_path = [*prefix_path, _variant_node_facts(node)]
            child_tree = _text(node.get("ChildItemBonusTreeID"))
            component_id = (
                f"tree:{child_tree}"
                if child_tree and child_tree != "0"
                else f"node:{_text(node.get('ID'))}"
            )
            if child_tree and child_tree != "0":
                raw_branches.extend(
                    walk(
                        child_tree,
                        current_path,
                        active_tree_ids | {container_tree_id},
                        component_id,
                        root_tree_id,
                    )
                )
                continue
            for choice in choices_for_node(node):
                raw_branches.append(
                    {
                        "rootTreeId": root_tree_id,
                        "treeId": container_tree_id,
                        "componentId": component_id,
                        "nodePath": current_path,
                        "choice": choice,
                    }
                )
    if not raw_branches and allow_empty_base_variant:
        raw_branches = [
            {
                "rootTreeId": None,
                "treeId": None,
                "componentId": "empty:static-identity",
                "nodePath": [],
                "choice": {
                    "kind": "empty_base",
                    "bonusListIds": [],
                    "bonusVectorOptional": True,
                },
            }
        ]
    if not raw_branches:
        raw_branches = [
            {
                "rootTreeId": None,
                "treeId": None,
                "componentId": "missing",
                "nodePath": [],
                "choice": {"kind": "missing_root", "bonusListIds": []},
            }
        ]

    root_facts_by_id = _index(db2_rows, "ItemBonusTree", "ID")
    preview_item = (
        official_payload.get("preview_item")
        if isinstance(official_payload, Mapping)
        and isinstance(official_payload.get("preview_item"), Mapping)
        else {}
    )
    preview_bonus_list_ids = [
        _text(value)
        for value in preview_item.get("bonus_list") or []
        if _text(value)
    ]
    preview_item_level = None
    preview_level_payload = preview_item.get("level")
    if isinstance(preview_level_payload, Mapping):
        preview_level_payload = preview_level_payload.get("value")
    try:
        parsed_preview_item_level = int(preview_level_payload)
    except (TypeError, ValueError):
        parsed_preview_item_level = 0
    if parsed_preview_item_level > 0:
        preview_item_level = parsed_preview_item_level

    def compose_official_preview_branches(
        branches: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        """Join tree components only when an official preview fixes the vector.

        A raw ItemBonusTree walk describes internal choices, not necessarily a
        complete item link.  The official item preview is the bounded join
        authority: it identifies the exact bonus-list vector and prevents
        unrelated sibling trees from being treated as one public variant.
        """

        if len(preview_bonus_list_ids) < 2:
            return []
        preview_set = set(preview_bonus_list_ids)
        root_ids = {
            _text(branch.get("rootTreeId"))
            for branch in branches
            if _text(branch.get("rootTreeId"))
        }
        if len(root_ids) != 1:
            return []

        def branch_tree_ids(branch: Mapping[str, Any]) -> set[str]:
            """Return every DB2 tree touched by one raw graph branch.

            ItemXBonusTree can point at a wrapper tree whose only child is a
            composition tree. The node path carries node ids rather than
            tree ids, so recover parent/child tree ids from the captured
            ItemBonusTreeNode rows before looking for the composition marker.
            """

            tree_ids = {
                value
                for value in (
                    _text(branch.get("rootTreeId")),
                    _text(branch.get("treeId")),
                )
                if value
            }
            for node in branch.get("nodePath") or []:
                node_id = _text(node.get("nodeId"))
                for raw_node in nodes_by_id.get(node_id, []):
                    parent_tree_id = _text(raw_node.get("ParentItemBonusTreeID"))
                    child_tree_id = _text(raw_node.get("ChildItemBonusTreeID"))
                    if parent_tree_id:
                        tree_ids.add(parent_tree_id)
                    if child_tree_id and child_tree_id != "0":
                        tree_ids.add(child_tree_id)
            return tree_ids

        candidates = [
            branch
            for branch in branches
            if branch.get("choice", {}).get("kind") in {"direct", "selector"}
            and branch.get("choice", {}).get("bonusListIds")
            and set(branch.get("choice", {}).get("bonusListIds") or []) <= preview_set
        ]
        if not candidates:
            return []

        common_tree_ids = set.intersection(
            *(branch_tree_ids(branch) for branch in candidates)
        )
        composition_tree_ids = sorted(
            tree_id
            for tree_id in common_tree_ids
            if len(root_facts_by_id.get(tree_id, [])) == 1
            and int(root_facts_by_id[tree_id][0].get("Flags") or 0) == 4
        )
        # Current S2 data can have a wrapper root (for example 6045) above a
        # composition tree (for example 5937). Compose only when the captured
        # graph identifies exactly one common composition marker; ambiguity
        # remains unverified.
        if len(composition_tree_ids) != 1:
            return []
        composition_tree_id = composition_tree_ids[0]

        by_component: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for branch in candidates:
            component_id = _text(branch.get("componentId"))
            if component_id:
                by_component[component_id].append(branch)
        if not by_component:
            return []

        ordered_components = sorted(by_component)
        matches: list[list[Mapping[str, Any]]] = []

        def search(
            index: int,
            selected: list[Mapping[str, Any]],
            selected_bonus_ids: set[str],
        ) -> None:
            if index == len(ordered_components):
                if selected_bonus_ids == preview_set:
                    matches.append(list(selected))
                return
            component_id = ordered_components[index]
            for branch in sorted(
                by_component[component_id],
                key=lambda row: (
                    tuple(
                        _text(value)
                        for value in row.get("choice", {}).get("bonusListIds") or []
                    ),
                    _text(row.get("treeId")),
                ),
            ):
                bonus_ids = {
                    _text(value)
                    for value in branch.get("choice", {}).get("bonusListIds") or []
                    if _text(value)
                }
                if selected_bonus_ids & bonus_ids:
                    continue
                search(index + 1, [*selected, branch], selected_bonus_ids | bonus_ids)

        search(0, [], set())
        if not matches:
            return []

        composed: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for selected in matches:
            node_path: list[dict[str, Any]] = []
            seen_node_ids: set[str] = set()
            component_ids = sorted(
                {_text(row.get("componentId")) for row in selected}
            )
            for branch in selected:
                for node in branch.get("nodePath") or []:
                    node_id = _text(node.get("nodeId"))
                    if node_id and node_id in seen_node_ids:
                        continue
                    if node_id:
                        seen_node_ids.add(node_id)
                    node_path.append(dict(node))
            variant_key = ":".join(
                [
                    _text(selected[0].get("rootTreeId")) or "none",
                    ",".join(preview_bonus_list_ids),
                    ",".join(component_ids),
                ]
            )
            if variant_key in seen_keys:
                continue
            seen_keys.add(variant_key)
            composed.append(
                {
                    "rootTreeId": selected[0].get("rootTreeId"),
                    "treeId": selected[0].get("treeId"),
                    "componentId": "composed:official-preview",
                    "nodePath": node_path,
                    "choice": {
                        "kind": "composed",
                        "bonusListIds": list(preview_bonus_list_ids),
                        "compositionTreeId": composition_tree_id,
                        "componentIds": component_ids,
                        "rawBranchKeys": [
                            ":".join(
                                [
                                    _text(row.get("componentId")),
                                    ",".join(
                                        _text(value)
                                        for value in row.get("choice", {}).get("bonusListIds") or []
                                    ),
                                ]
                            )
                            for row in selected
                        ],
                        "officialPreview": True,
                    },
                }
            )
        return composed

    item_inventory_type_values: set[int] = set()
    for table in ("Item", "ItemSparse"):
        for row in db2_rows.get(table, []):
            if _text(row.get("ID")) != item_id:
                continue
            raw_inventory_type = row.get("InventoryType")
            try:
                inventory_type = int(raw_inventory_type or 0)
            except (TypeError, ValueError):
                continue
            if inventory_type > 0:
                item_inventory_type_values.add(inventory_type)
    item_inventory_type = (
        next(iter(item_inventory_type_values))
        if len(item_inventory_type_values) == 1
        else None
    )
    context_groups_by_value: dict[str, set[str]] = defaultdict(set)
    for row in db2_rows.get("ItemCreationContext", []):
        context_value = _text(row.get("ItemContext"))
        group_id = _text(row.get("ItemCreationContextGroupID"))
        if context_value and group_id and group_id != "0":
            context_groups_by_value[context_value].add(group_id)

    def reachable_tree_ids(root_tree_id: str) -> set[str]:
        result: set[str] = set()
        pending = [root_tree_id]
        while pending:
            tree_id = pending.pop()
            if not tree_id or tree_id in result:
                continue
            result.add(tree_id)
            for node in nodes_by_parent.get(tree_id, []):
                child_tree_id = _text(node.get("ChildItemBonusTreeID"))
                if child_tree_id and child_tree_id != "0":
                    pending.append(child_tree_id)
        return result

    def tree_fact(tree_id: str) -> Mapping[str, Any] | None:
        rows = root_facts_by_id.get(tree_id, [])
        return rows[0] if len(rows) == 1 else None

    def tree_mask_matches(tree_id: str, blockers: set[str]) -> bool:
        fact = tree_fact(tree_id)
        if fact is None:
            blockers.add("OFFICIAL_DB2_ITEM_BONUS_TREE_FACT_MISSING")
            return False
        try:
            slot_mask = int(fact.get("InventoryTypeSlotMask") or 0)
        except (TypeError, ValueError):
            blockers.add("OFFICIAL_DB2_ITEM_BONUS_TREE_SLOT_MASK_UNVERIFIED")
            return False
        if slot_mask == 0:
            return True
        if item_inventory_type is None:
            blockers.add(
                "OFFICIAL_DB2_ITEM_INVENTORY_TYPE_CONFLICT"
                if len(item_inventory_type_values) > 1
                else "OFFICIAL_DB2_ITEM_INVENTORY_TYPE_MISSING"
            )
            blockers.add("OFFICIAL_DB2_ITEM_BONUS_TREE_SLOT_MASK_UNVERIFIED")
            return False
        return bool(slot_mask & (1 << item_inventory_type))

    def node_matches(
        node: Mapping[str, Any],
        *,
        context_value: str,
        mythic_plus_level: int,
    ) -> tuple[bool, bool, bool]:
        node_context = _text(node.get("ItemContext")) or "0"
        if node_context not in {"0", context_value}:
            return False, False, False
        try:
            minimum = int(node.get("MinMythicPlusLevel") or 0)
        except (TypeError, ValueError):
            minimum = 0
        try:
            maximum = int(node.get("MaxMythicPlusLevel") or 0)
        except (TypeError, ValueError):
            maximum = 0
        if mythic_plus_level < minimum:
            return False, False, False
        if maximum > 0 and mythic_plus_level > maximum:
            return False, False, False

        group_id = _text(node.get("ItemCreationContextGroupID"))
        if not group_id or group_id == "0":
            return True, False, False
        if context_value == "0":
            if (
                allow_raid_base_numeric_evidence
                or allow_default_context_group_resolution
            ):
                # MapDifficulty identifies context 0 as the raid default
                # context.  A non-zero group id on this exact default edge is
                # therefore not a selectable upgrade group for the bounded
                # default-context projection; retain the node and record that
                # the default context resolved it without a separate
                # ItemCreationContext row.  Tier-set conversion uses the same
                # sentinel only after its independent membership and official
                # conversion tree have been established by the caller.
                return True, False, True
            # The captured DB2 set has no default-context group row.  Keep the
            # branch observable for graph inspection, but do not claim that
            # the group selector is understood for context 0.
            return True, True, False
        if group_id not in context_groups_by_value.get(context_value, set()):
            return False, False, False
        return True, False, False

    def dedupe_composed_parts(parts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for part in parts:
            terminals = part.get("terminals") or []
            key = json.dumps(
                {
                    "bonusListIds": [
                        _text(value)
                        for terminal in terminals
                        for value in terminal.get("choice", {}).get("bonusListIds") or []
                    ],
                    "nodeIds": [
                        _text(node.get("nodeId"))
                        for terminal in terminals
                        for node in terminal.get("nodePath") or []
                    ],
                    "compositionTreeIds": sorted(
                        {
                            _text(value)
                            for value in part.get("compositionTreeIds") or []
                            if _text(value)
                        },
                        key=int,
                    ),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(dict(part))
        return result

    def compose_context_slot_branches() -> list[dict[str, Any]]:
        composed: list[dict[str, Any]] = []

        def evaluate_tree(
            tree_id: str,
            *,
            context_value: str,
            mythic_plus_level: int,
            node_path: list[dict[str, Any]],
            active_tree_ids: set[str],
        ) -> list[dict[str, Any]]:
            branch_blockers: set[str] = set()
            if tree_id in active_tree_ids:
                return []
            if not tree_mask_matches(tree_id, branch_blockers):
                return []
            nodes = sorted(
                nodes_by_parent.get(tree_id, []),
                key=lambda row: int(row.get("ID") or 0),
            )
            if not nodes:
                return []
            fact = tree_fact(tree_id)
            if fact is None:
                return []
            try:
                flags = int(fact.get("Flags") or 0)
            except (TypeError, ValueError):
                flags = 0
            is_composition_tree = flags in {4, 5}

            node_options: list[list[dict[str, Any]]] = []
            for node in nodes:
                matches, group_unverified, default_context_group_resolved = node_matches(
                    node,
                    context_value=context_value,
                    mythic_plus_level=mythic_plus_level,
                )
                if not matches:
                    continue
                current_path = [*node_path, _variant_node_facts(node)]
                child_tree_id = _text(node.get("ChildItemBonusTreeID"))
                if child_tree_id and child_tree_id != "0":
                    child_parts = evaluate_tree(
                        child_tree_id,
                        context_value=context_value,
                        mythic_plus_level=mythic_plus_level,
                        node_path=current_path,
                        active_tree_ids=active_tree_ids | {tree_id},
                    )
                    for child_part in child_parts:
                        child_part["contextGroupUnverified"] = bool(
                            child_part.get("contextGroupUnverified")
                            or group_unverified
                        )
                        child_part["defaultContextGroupResolved"] = bool(
                            child_part.get("defaultContextGroupResolved")
                            or default_context_group_resolved
                        )
                        child_part["compositionBlockerCodes"] = sorted(
                            set(child_part.get("compositionBlockerCodes") or [])
                            | branch_blockers
                        )
                    if child_parts:
                        node_options.append(child_parts)
                    continue
                choices = []
                for choice in choices_for_node(node):
                    choices.append(
                        {
                            "terminals": [
                                {
                                    "componentId": f"tree:{tree_id}",
                                    "treeId": tree_id,
                                    "choice": dict(choice),
                                    "nodePath": current_path,
                                }
                            ],
                            "compositionTreeIds": (
                                [tree_id] if is_composition_tree else []
                            ),
                            "contextGroupUnverified": group_unverified,
                            "defaultContextGroupResolved": default_context_group_resolved,
                            "compositionBlockerCodes": sorted(branch_blockers),
                        }
                    )
                if choices:
                    node_options.append(choices)

            if not node_options:
                return []
            if not is_composition_tree:
                return dedupe_composed_parts(
                    [part for options in node_options for part in options]
                )

            combined: list[dict[str, Any]] = [
                {
                    "terminals": [],
                    "compositionTreeIds": [tree_id],
                    "contextGroupUnverified": False,
                    "defaultContextGroupResolved": False,
                    "compositionBlockerCodes": sorted(branch_blockers),
                }
            ]
            for options in node_options:
                next_combined: list[dict[str, Any]] = []
                for prefix in combined:
                    for option in options:
                        next_combined.append(
                            {
                                "terminals": [
                                    *(prefix.get("terminals") or []),
                                    *(option.get("terminals") or []),
                                ],
                                "compositionTreeIds": sorted(
                                    {
                                        tree_id,
                                        *(
                                            _text(value)
                                            for value in prefix.get("compositionTreeIds") or []
                                        ),
                                        *(
                                            _text(value)
                                            for value in option.get("compositionTreeIds") or []
                                        ),
                                    },
                                    key=int,
                                ),
                                "contextGroupUnverified": bool(
                                    prefix.get("contextGroupUnverified")
                                    or option.get("contextGroupUnverified")
                                ),
                                "defaultContextGroupResolved": bool(
                                    prefix.get("defaultContextGroupResolved")
                                    or option.get("defaultContextGroupResolved")
                                ),
                                "compositionBlockerCodes": sorted(
                                    set(prefix.get("compositionBlockerCodes") or [])
                                    | set(option.get("compositionBlockerCodes") or [])
                                    | branch_blockers
                                ),
                            }
                        )
                combined = dedupe_composed_parts(next_combined)
                if not combined:
                    break
            return combined

        for root_tree_id in item_roots:
            reachable_ids = reachable_tree_ids(root_tree_id)
            composition_ids = {
                tree_id
                for tree_id in reachable_ids
                if tree_fact(tree_id) is not None
                and int(tree_fact(tree_id).get("Flags") or 0) in {4, 5}
            }
            if not composition_ids:
                continue
            reachable_nodes = [
                node
                for tree_id in reachable_ids
                for node in nodes_by_parent.get(tree_id, [])
            ]
            context_values = {
                "0",
                *{
                    _text(node.get("ItemContext"))
                    for node in reachable_nodes
                    if _text(node.get("ItemContext"))
                },
            }
            if composition_context_values is not None:
                requested_context_values = {
                    _text(value)
                    for value in composition_context_values
                    if _text(value)
                }
                context_values &= requested_context_values
            levels = {0}
            for node in reachable_nodes:
                for field in ("MinMythicPlusLevel", "MaxMythicPlusLevel"):
                    try:
                        value = int(node.get(field) or 0)
                    except (TypeError, ValueError):
                        value = 0
                    if value > 0:
                        levels.add(value)
                        if field == "MaxMythicPlusLevel":
                            levels.add(value + 1)

            for context_value in sorted(
                context_values,
                key=lambda value: (0, int(value)) if value.isdigit() else (1, value),
            ):
                context_levels = [0] if context_value == "0" else sorted(levels)
                for mythic_plus_level in context_levels:
                    parts = evaluate_tree(
                        root_tree_id,
                        context_value=context_value,
                        mythic_plus_level=mythic_plus_level,
                        node_path=[],
                        active_tree_ids=set(),
                    )
                    for part in parts:
                        terminals = part.get("terminals") or []
                        bonus_list_ids = [
                            _text(value)
                            for terminal in terminals
                            for value in terminal.get("choice", {}).get("bonusListIds") or []
                            if _text(value)
                        ]
                        if not bonus_list_ids or not part.get("compositionTreeIds"):
                            continue
                        node_path: list[dict[str, Any]] = []
                        seen_node_ids: set[str] = set()
                        for terminal in terminals:
                            for node in terminal.get("nodePath") or []:
                                node_id = _text(node.get("nodeId"))
                                if node_id and node_id in seen_node_ids:
                                    continue
                                if node_id:
                                    seen_node_ids.add(node_id)
                                node_path.append(dict(node))
                        component_ids = []
                        raw_branch_keys = []
                        group_ids: set[str] = set()
                        group_entries: list[Mapping[str, Any]] = []
                        selector_facts: list[Mapping[str, Any]] = []
                        component_choices = []
                        for terminal in terminals:
                            component_id = _text(terminal.get("componentId"))
                            if component_id and component_id not in component_ids:
                                component_ids.append(component_id)
                            choice = dict(terminal.get("choice") or {})
                            component_choices.append(choice)
                            raw_branch_keys.append(
                                ":".join(
                                    [
                                        component_id or "none",
                                        ",".join(
                                            _text(value)
                                            for value in choice.get("bonusListIds") or []
                                        ),
                                    ]
                                )
                            )
                            group_id = _text(choice.get("groupId"))
                            if group_id:
                                group_ids.add(group_id)
                            if isinstance(choice.get("groupEntry"), Mapping):
                                group_entries.append(choice["groupEntry"])
                            if isinstance(choice.get("selectorFacts"), Mapping):
                                selector_facts.append(choice["selectorFacts"])
                        choice: dict[str, Any] = {
                            "kind": "composed",
                            "bonusListIds": bonus_list_ids,
                            "compositionTreeIds": sorted(
                                {
                                    _text(value)
                                    for value in part.get("compositionTreeIds") or []
                                    if _text(value)
                                },
                                key=int,
                            ),
                            "componentIds": component_ids,
                            "componentChoices": component_choices,
                            "rawBranchKeys": raw_branch_keys,
                            "officialPreview": False,
                            "compositionEvidenceStatus": "observed",
                            "itemContext": context_value,
                            "mythicPlusLevel": mythic_plus_level,
                        }
                        if len(group_ids) == 1:
                            choice["groupId"] = next(iter(group_ids))
                        elif len(group_ids) > 1:
                            choice["multipleGroupIds"] = sorted(group_ids, key=int)
                        if len(group_entries) == 1:
                            choice["groupEntry"] = dict(group_entries[0])
                        if len(selector_facts) == 1:
                            choice["selectorFacts"] = dict(selector_facts[0])
                        composed.append(
                            {
                                "rootTreeId": root_tree_id,
                                "treeId": root_tree_id,
                                "componentId": "composed:db2-context-slot",
                                "nodePath": node_path,
                                "choice": choice,
                                "contextGroupUnverified": bool(
                                    part.get("contextGroupUnverified")
                                ),
                                "defaultContextGroupResolved": bool(
                                    part.get("defaultContextGroupResolved")
                                ),
                                "compositionBlockerCodes": sorted(
                                    set(part.get("compositionBlockerCodes") or [])
                                    | (
                                        {
                                            "OFFICIAL_DB2_ITEM_CREATION_CONTEXT_GROUP_SEMANTICS_UNVERIFIED"
                                        }
                                        if part.get("contextGroupUnverified")
                                        else set()
                                    )
                                ),
                            }
                        )
        return composed

    composed_branches = compose_official_preview_branches(raw_branches)
    official_preview_active = bool(composed_branches)
    if composed_branches:
        raw_branches = composed_branches
    context_composed_branches = compose_context_slot_branches()
    if context_composed_branches:
        official_preview_bonus_ids = tuple(preview_bonus_list_ids)
        for branch in context_composed_branches:
            branch_bonus_ids = tuple(branch.get("choice", {}).get("bonusListIds") or [])
            if official_preview_active and branch_bonus_ids == official_preview_bonus_ids:
                continue
            raw_branches.append(branch)

    variants: dict[str, dict[str, Any]] = {}
    for branch in raw_branches:
        root_tree_id = _text(branch.get("rootTreeId")) or "none"
        node_ids = [
            _text(node.get("nodeId"))
            for node in branch.get("nodePath") or []
            if _text(node.get("nodeId"))
        ]
        choice = branch.get("choice") or {}
        bonus_list_ids = [
            _text(value)
            for value in choice.get("bonusListIds") or []
            if _text(value)
        ]
        bonus_rows = [
            row
            for bonus_list_id in bonus_list_ids
            for row in sorted(
                bonus_rows_by_list.get(bonus_list_id, []),
                key=lambda row: int(row.get("ID") or 0),
            )
        ]
        bonus_list_level_delta_evidence = []
        level_delta_refs: set[str] = set()
        for bonus_list_id in bonus_list_ids:
            delta_rows = level_delta_rows_by_list.get(bonus_list_id, [])
            row_refs = {
                ref
                for row in delta_rows
                for ref in _row_ref(
                    row,
                    table="ItemBonusListLevelDelta",
                    refs=db2_refs,
                )
            }
            level_delta_refs.update(row_refs)
            if len(delta_rows) == 1:
                delta_row = delta_rows[0]
                bonus_list_level_delta_evidence.append(
                    {
                        "bonusListId": bonus_list_id,
                        "status": "verified",
                        "itemLevelDelta": delta_row.get("ItemLevelDelta"),
                        "evidenceRefs": sorted(row_refs),
                    }
                )
            elif not delta_rows:
                bonus_list_level_delta_evidence.append(
                    {
                        "bonusListId": bonus_list_id,
                        "status": "not_found",
                        "itemLevelDelta": None,
                        "evidenceRefs": [],
                    }
                )
            else:
                bonus_list_level_delta_evidence.append(
                    {
                        "bonusListId": bonus_list_id,
                        "status": "UNVERIFIED",
                        "itemLevelDelta": None,
                        "reasonCode": "OFFICIAL_DB2_ITEM_BONUS_LIST_LEVEL_DELTA_AMBIGUOUS",
                        "evidenceRefs": sorted(row_refs),
                    }
                )
        selected_list_ids = set(bonus_list_ids)
        known_list_ids = item_bonus_list_ids | set(bonus_rows_by_list)
        reason_codes = {"VARIANT_TRACK_AUTHORITY_UNVERIFIED"}
        if choice.get("kind") in {"missing_root", "missing_tree_nodes"}:
            reason_codes.add("OFFICIAL_DB2_ITEM_BONUS_TREE_MISSING")
        if choice.get("kind") == "cycle":
            reason_codes.add("OFFICIAL_DB2_ITEM_BONUS_TREE_CYCLE")
        if choice.get("kind") == "empty":
            reason_codes.add("OFFICIAL_DB2_VARIANT_TERMINAL_BONUS_LIST_MISSING")
        if choice.get("kind") == "group" and not bonus_list_ids:
            reason_codes.add("OFFICIAL_DB2_BONUS_LIST_GROUP_ENTRY_MISSING")
        composition_blocker_codes = set(
            choice.get("compositionBlockerCodes") or []
        ) | set(branch.get("compositionBlockerCodes") or [])
        if choice.get("kind") == "composed" and not choice.get("officialPreview"):
            if branch.get("contextGroupUnverified"):
                composition_blocker_codes.add(
                    "OFFICIAL_DB2_ITEM_CREATION_CONTEXT_GROUP_SEMANTICS_UNVERIFIED"
                )
            if choice.get("multipleGroupIds"):
                composition_blocker_codes.add(
                    "OFFICIAL_DB2_COMPOSED_VARIANT_MULTIPLE_UPGRADE_GROUPS_UNVERIFIED"
                )
        reason_codes.update(composition_blocker_codes)
        group_id = _text(choice.get("groupId"))
        group_fact_rows = group_facts_by_id.get(group_id, []) if group_id else []
        group_fact = group_fact_rows[0] if len(group_fact_rows) == 1 else None
        group_scaling_id = _text(group_fact.get("ItemGroupIlvlScalingID")) if group_fact else ""
        group_scaling_entries = (
            sorted(
                scaling_entries_by_group.get(group_scaling_id, []),
                key=lambda row: int(row.get("ID") or 0),
            )
            if group_scaling_id
            else []
        )
        condition_ids = set()
        if group_fact is not None:
            condition_id = _text(group_fact.get("PlayerConditionID"))
            if condition_id and condition_id != "0":
                condition_ids.add(condition_id)
        for entry in group_scaling_entries:
            condition_id = _text(entry.get("PlayerConditionID"))
            if condition_id and condition_id != "0":
                condition_ids.add(condition_id)
        condition_rows = [
            conditions_by_id[condition_id][0]
            for condition_id in sorted(condition_ids, key=int)
            if len(conditions_by_id.get(condition_id, [])) == 1
        ]
        group_evidence_refs: set[str] = set()
        for row in group_fact_rows:
            group_evidence_refs.update(
                _row_ref(row, table="ItemBonusListGroup", refs=db2_refs)
            )
        for row in group_scaling_entries:
            group_evidence_refs.update(
                _row_ref(row, table="ItemGroupIlvlScalingEntry", refs=db2_refs)
            )
        for row in condition_rows:
            group_evidence_refs.update(
                _row_ref(row, table="PlayerCondition", refs=db2_refs)
            )
        missing_condition_ids = sorted(
            condition_ids
            - {
                _text(row.get("ID"))
                for row in condition_rows
            },
            key=int,
        )
        if choice.get("kind") == "group":
            if group_fact is None:
                reason_codes.add("OFFICIAL_DB2_BONUS_LIST_GROUP_FACT_MISSING")
            if not group_scaling_entries:
                reason_codes.add("OFFICIAL_DB2_UPGRADE_SCALING_ENTRIES_MISSING")
            if missing_condition_ids:
                reason_codes.add("OFFICIAL_DB2_UPGRADE_PLAYER_CONDITION_MISSING")
        if selected_list_ids - known_list_ids:
            reason_codes.add("OFFICIAL_DB2_BONUS_LIST_FACTS_MISSING")

        scaling_evidence: list[dict[str, Any]] = []
        scaling_refs: set[str] = set()
        bonus_type50: list[dict[str, Any]] = []
        bonus_refs: set[str] = set()
        for bonus in bonus_rows:
            bonus_type = int(bonus.get("Type") or 0)
            if bonus_type in {49, 51}:
                fact, refs = _variant_scaling_fact(
                    bonus,
                    db2_rows=db2_rows,
                    db2_refs=db2_refs,
                )
                scaling_evidence.append(fact)
                scaling_refs.update(refs)
                if fact.get("curveEvidenceStatus") == "observed":
                    reason_codes.add("ITEM_SCALING_CURVE_FORMULA_UNVERIFIED")
            if bonus_type == 50:
                bonus_type50.append(
                    {
                        "bonusId": _text(bonus.get("ID")),
                        "bonusListId": _text(bonus.get("ParentItemBonusListID")),
                        "value0": bonus.get("Value_0"),
                        "value1": bonus.get("Value_1"),
                        "value2": bonus.get("Value_2"),
                        "value3": bonus.get("Value_3"),
                        "status": "UNVERIFIED",
                        "reasonCode": "BONUS_TYPE_50_SEMANTICS_UNVERIFIED",
                        "evidenceRefs": _row_ref(bonus, table="ItemBonus", refs=db2_refs),
                    }
                )
                reason_codes.add("BONUS_TYPE_50_SEMANTICS_UNVERIFIED")
            bonus_refs.update(_row_ref(bonus, table="ItemBonus", refs=db2_refs))

        bonus_type_ids = sorted({int(row.get("Type") or 0) for row in bonus_rows})

        item_contexts = [
            node.get("itemContext")
            for node in branch.get("nodePath") or []
            if node.get("itemContext") not in (None, "", 0, "0")
        ]
        context_group_ids = sorted(
            {
                _text(node.get("itemCreationContextGroupId"))
                for node in branch.get("nodePath") or []
                if _text(node.get("itemCreationContextGroupId")) not in {"", "0"}
            },
            key=int,
        )
        bound_facts = [
            {
                "nodeId": _text(node.get("nodeId")),
                "itemContext": node.get("itemContext"),
                "minMythicPlusLevel": node.get("minMythicPlusLevel"),
                "maxMythicPlusLevel": node.get("maxMythicPlusLevel"),
            }
            for node in branch.get("nodePath") or []
        ]
        branch_refs = set(bonus_refs) | scaling_refs | level_delta_refs
        for node in branch.get("nodePath") or []:
            for raw_node in nodes_by_id.get(_text(node.get("nodeId")), []):
                branch_refs.update(
                    _row_ref(raw_node, table="ItemBonusTreeNode", refs=db2_refs)
                )
        composition_tree_id = _text(choice.get("compositionTreeId"))
        composition_tree_ids = sorted(
            {
                _text(value)
                for value in choice.get("compositionTreeIds") or []
                if _text(value)
            },
            key=int,
        )
        if composition_tree_id and composition_tree_id not in composition_tree_ids:
            composition_tree_ids.append(composition_tree_id)
        for composition_tree in composition_tree_ids:
            for tree_fact in root_facts_by_id.get(composition_tree, []):
                branch_refs.update(
                    _row_ref(tree_fact, table="ItemBonusTree", refs=db2_refs)
                )
        group_entry = choice.get("groupEntry")
        if isinstance(group_entry, Mapping):
            branch_refs.update(
                _row_ref(group_entry, table="ItemBonusListGroupEntry", refs=db2_refs)
            )
        selector_facts = choice.get("selectorFacts")
        if isinstance(selector_facts, Mapping):
            branch_refs.update(selector_facts.get("evidenceRefs") or [])
        branch_refs.update(group_evidence_refs)
        db2_composition_verified = (
            choice.get("kind") == "composed"
            and choice.get("compositionEvidenceStatus") == "observed"
            and not choice.get("officialPreview")
            and not composition_blocker_codes
        )
        graph_has_terminal = bool(bonus_list_ids) or choice.get("kind") == "empty_base"
        graph_status = (
            "verified"
            if (
                choice.get("kind") in {"direct", "group", "selector", "empty_base"}
                or db2_composition_verified
            )
            and graph_has_terminal
            and not (selected_list_ids - known_list_ids)
            else "UNVERIFIED"
        )
        if (
            choice.get("kind") == "composed"
            and choice.get("officialPreview") is True
            and bonus_list_ids
            and not (selected_list_ids - known_list_ids)
        ):
            graph_status = "verified"
        if composition_blocker_codes:
            graph_status = "UNVERIFIED"
        official_preview_vector_match = bool(preview_item_level) and tuple(
            bonus_list_ids
        ) == tuple(preview_bonus_list_ids)
        base_item_level_evidence = None
        if (
            allow_raid_base_numeric_evidence
            or allow_default_context_numeric_evidence
        ) and not official_preview_vector_match:
            base_item_level_evidence = _raid_base_numeric_evidence(
                official_payload,
                item_context_values=item_contexts,
                scaling_evidence=scaling_evidence,
                bonus_list_level_delta_evidence=bonus_list_level_delta_evidence,
                bonus_type_ids=bonus_type_ids,
            )
            if base_item_level_evidence is not None and allow_default_context_numeric_evidence:
                base_item_level_evidence = {
                    **base_item_level_evidence,
                    "resolution": "tier_set_default_context_zero_rows_and_static_item_level",
                    "authority": "blizzard_game_data_api.item.level_plus_official_client_db2.ItemCreationContext",
                }
        if (
            base_item_level_evidence is None
            and allow_raid_base_numeric_evidence
            and item_contexts
        ):
            base_item_level_evidence = _raid_contextual_static_numeric_evidence(
                official_payload,
                static_item_level=static_item_level,
                item_context_values=item_contexts,
                item_creation_context_group_ids=context_group_ids,
                bonus_type_ids=bonus_type_ids,
                scaling_evidence=scaling_evidence,
                bonus_list_level_delta_evidence=bonus_list_level_delta_evidence,
                db2_rows=db2_rows,
                db2_refs=db2_refs,
            )
        if not scaling_evidence and base_item_level_evidence is None:
            numeric_status = "UNVERIFIED"
        else:
            numeric_status = (
                "verified"
                if all(row.get("status") == "verified" for row in scaling_evidence)
                else "UNVERIFIED"
            )
        if official_preview_vector_match:
            numeric_status = "verified"
        elif base_item_level_evidence is not None:
            numeric_status = "verified"
        if numeric_status != "verified":
            reason_codes.add("NUMERIC_VARIANT_EVIDENCE_UNVERIFIED")
        choice_key = ":".join(
            [
                _text(choice.get("kind")) or "none",
                _text(choice.get("groupId")) or "none",
                ",".join(bonus_list_ids) or "none",
            ]
        )
        node_key = ",".join(node_ids) or "none"
        variant_key = (
            f"s2-variant:item:{item_id}:root:{root_tree_id}:nodes:{node_key}:choice:{choice_key}"
        )
        raw_branch_key = ":".join(
            [
                _text(branch.get("componentId")) or "none",
                ",".join(bonus_list_ids),
            ]
        )
        variant = {
            "itemId": item_id,
            "variantKey": variant_key,
            "rootItemBonusTreeId": None if root_tree_id == "none" else root_tree_id,
            "rawBranchKey": raw_branch_key,
            "bonusVectorOptional": bool(choice.get("bonusVectorOptional")),
            "variantComposition": (
                {"status": "verified", "kind": "empty_base_identity"}
                if choice.get("kind") == "empty_base"
                else (
                    {
                        "status": "verified",
                        "kind": "official_preview_vector",
                        "compositionTreeId": _text(choice.get("compositionTreeId")) or None,
                        "compositionTreeIds": composition_tree_ids,
                        "componentIds": list(choice.get("componentIds") or []),
                        "rawBranchKeys": list(choice.get("rawBranchKeys") or []),
                    }
                    if choice.get("kind") == "composed"
                    and choice.get("officialPreview") is True
                    else (
                        {
                            "status": "observed",
                            "kind": "db2_context_slot_vector",
                            "compositionTreeIds": composition_tree_ids,
                            "componentIds": list(choice.get("componentIds") or []),
                            "rawBranchKeys": list(choice.get("rawBranchKeys") or []),
                            "compositionEvidenceStatus": choice.get(
                                "compositionEvidenceStatus"
                            ),
                            "itemContext": choice.get("itemContext"),
                            "mythicPlusLevel": choice.get("mythicPlusLevel"),
                            "defaultContextGroupStatus": (
                                "not_required"
                                if branch.get("defaultContextGroupResolved")
                                else "unverified"
                                if branch.get("contextGroupUnverified")
                                else "not_applicable"
                            ),
                        }
                        if choice.get("kind") == "composed"
                        else {"status": "not_composed", "kind": "raw_graph_edge"}
                    )
                )
            ),
            "nodePath": branch.get("nodePath") or [],
            "itemContextValues": [str(value) for value in item_contexts],
            "itemCreationContextGroupIds": context_group_ids,
            "mythicPlusLevelBounds": bound_facts,
            "bonusListIds": bonus_list_ids,
            "bonusListLevelDeltaEvidence": bonus_list_level_delta_evidence,
            "bonusTypeIds": bonus_type_ids,
            "bonusType50Evidence": bonus_type50,
            "bonusListGroupId": _text(choice.get("groupId")) or None,
            "bonusListGroupEntry": dict(group_entry) if isinstance(group_entry, Mapping) else None,
            "upgradeGroupEvidence": {
                "status": (
                    "observed"
                    if choice.get("kind") in {"group", "composed"}
                    and group_fact is not None
                    and group_scaling_entries
                    and not missing_condition_ids
                    else "not_applicable"
                    if choice.get("kind") != "group"
                    else "UNVERIFIED"
                ),
                "groupId": group_id or None,
                "groupFact": (
                    {
                        field: group_fact.get(field)
                        for field in (
                            "ID",
                            "ItemGroupIlvlScalingID",
                            "PlayerConditionID",
                            "SequenceSpellID",
                        )
                    }
                    if group_fact
                    else None
                ),
                "scalingEntryIds": [
                    _text(row.get("ID")) for row in group_scaling_entries
                ],
                "conditionIds": sorted(condition_ids, key=int),
                "conditionFacts": [
                    {
                        "ID": row.get("ID"),
                        "Failure_description_lang": row.get("Failure_description_lang"),
                    }
                    for row in condition_rows
                ],
                "missingConditionIds": missing_condition_ids,
                "evidenceRefs": sorted(group_evidence_refs),
            },
            "selectorFacts": dict(selector_facts) if isinstance(selector_facts, Mapping) else None,
            "itemScalingEvidence": scaling_evidence,
            "officialPreviewItemLevelEvidence": (
                {
                    "status": "verified",
                    "itemLevel": preview_item_level,
                    "authority": "blizzard_game_data_api.item.preview_item.level",
                }
                if official_preview_vector_match
                else None
            ),
            "officialBaseItemLevelEvidence": base_item_level_evidence,
            "numericVariantEvidenceStatus": numeric_status,
            "rawGraphStatus": graph_status,
            "trackStatus": "UNVERIFIED",
            "sourceEligibilityStatus": "UNVERIFIED",
            "variantStatus": "UNVERIFIED",
            "simcReadiness": "blocked",
            "reasonCodes": sorted(reason_codes),
            "evidenceRefs": sorted(branch_refs),
            "status": "UNVERIFIED",
        }
        variants[variant_key] = variant
    return list(variants.values())


def _compact_variant_record(variant: Mapping[str, Any]) -> dict[str, Any]:
    scaling_evidence = []
    scaling_config_ids = []
    curve_ids = []
    curve_point_ids = []
    for row in variant.get("itemScalingEvidence") or []:
        compact = {
            key: row.get(key)
            for key in (
                "bonusId",
                "bonusListId",
                "type",
                "scalingConfigId",
                "itemLevel",
                "itemOffsetCurveId",
                "curveId",
                "curveEvidenceStatus",
                "curveReasonCode",
                "curvePointIds",
                "status",
            )
            if key in row
        }
        scaling_evidence.append(compact)
        if _text(row.get("scalingConfigId")):
            scaling_config_ids.append(_text(row.get("scalingConfigId")))
        if _text(row.get("curveId")):
            curve_ids.append(_text(row.get("curveId")))
        curve_point_ids.extend(
            _text(value)
            for value in row.get("curvePointIds") or []
            if _text(value)
        )

    bonus_type50 = []
    for row in variant.get("bonusType50Evidence") or []:
        bonus_type50.append(
            {
                key: row.get(key)
                for key in (
                    "bonusId",
                    "bonusListId",
                    "value0",
                    "value1",
                    "value2",
                    "value3",
                    "status",
                    "reasonCode",
                )
                if key in row
            }
        )

    level_delta_evidence = []
    level_delta_ids = []
    for row in variant.get("bonusListLevelDeltaEvidence") or []:
        level_delta_evidence.append(
            {
                key: row.get(key)
                for key in (
                    "bonusListId",
                    "status",
                    "itemLevelDelta",
                    "reasonCode",
                )
                if key in row
            }
        )
        if row.get("status") == "verified" and _text(row.get("bonusListId")):
            level_delta_ids.append(_text(row.get("bonusListId")))

    group_entry = variant.get("bonusListGroupEntry")
    compact_group_entry = None
    if isinstance(group_entry, Mapping):
        compact_group_entry = {
            key: group_entry.get(key)
            for key in (
                "ID",
                "ItemBonusListGroupID",
                "ItemBonusListID",
                "ItemLevelSelectorID",
                "SequenceValue",
                "Flags",
            )
            if key in group_entry
        }
    group_evidence = variant.get("upgradeGroupEvidence") or {}
    compact_group_evidence = {
        key: group_evidence.get(key)
        for key in (
            "status",
            "groupId",
            "scalingEntryIds",
            "conditionIds",
            "missingConditionIds",
        )
        if key in group_evidence
    }
    node_ids = [
        _text(node.get("nodeId"))
        for node in variant.get("nodePath") or []
        if _text(node.get("nodeId"))
    ]
    selector_facts = variant.get("selectorFacts")
    selector_ids = []
    if isinstance(selector_facts, Mapping) and _text(selector_facts.get("selectorId")):
        selector_ids.append(_text(selector_facts.get("selectorId")))

    source_evidence = variant.get("sourceEligibilityEvidence")
    compact_source_evidence: dict[str, Any] | None = None
    if isinstance(source_evidence, Mapping):
        compact_by_source: dict[str, Any] = {}
        for source, source_row in (source_evidence.get("bySource") or {}).items():
            if not isinstance(source_row, Mapping):
                continue
            compact_by_source[_text(source)] = {
                key: source_row.get(key)
                for key in (
                    "status",
                    "mapIds",
                    "mapEvidenceStatus",
                    "requiredItemContextValues",
                    "observedItemContextValues",
                    "allowedItemContextValues",
                    "validDifficultyIds",
                    "reasonCode",
                )
                if key in source_row
            }
        compact_source_evidence = {
            key: source_evidence.get(key)
            for key in (
                "status",
                "observedItemContextValues",
                "reasonCodes",
            )
            if key in source_evidence
        }
        compact_source_evidence["bySource"] = compact_by_source

    track_authority = variant.get("trackAuthority")
    compact_track_authority = None
    if isinstance(track_authority, Mapping):
        compact_track_authority = {
            key: track_authority.get(key)
            for key in (
                "status",
                "reasonCode",
                "trackStatus",
                "sourceEligibilityStatus",
                "trackKey",
                "rank",
                "maxRank",
                "itemLevel",
                "currencyTypeId",
                "currencyName",
                "currencyDescription",
                "extendedCostIds",
                "evidenceKeys",
            )
            if key in track_authority
        }

    compact_selector_facts = None
    if isinstance(selector_facts, Mapping):
        compact_selector_facts = {
            key: selector_facts.get(key)
            for key in (
                "selectorId",
                "status",
                "minItemLevel",
                "qualitySet",
                "qualityOptions",
            )
            if key in selector_facts
        }
    composition = variant.get("variantComposition")
    compact_composition = None
    if isinstance(composition, Mapping):
        compact_composition = {
            key: composition.get(key)
            for key in (
                "status",
                "kind",
                "compositionTreeId",
                "compositionTreeIds",
                "componentIds",
                "rawBranchKeys",
                "compositionEvidenceStatus",
                "itemContext",
                "mythicPlusLevel",
                "defaultContextGroupStatus",
            )
            if key in composition
        }
    return {
        key: variant.get(key)
        for key in (
            "itemId",
            "variantKey",
            "rawBranchKey",
            "rootItemBonusTreeId",
            "variantComposition",
            "bonusVectorOptional",
            "itemContextValues",
            "itemCreationContextGroupIds",
            "bonusListIds",
            "bonusListLevelDeltaEvidence",
            "bonusTypeIds",
            "bonusListGroupId",
            "itemSlot",
            "officialPreviewItemLevelEvidence",
            "officialBaseItemLevelEvidence",
            "qualityStatus",
            "canonicalSimcInput",
            "numericVariantEvidenceStatus",
            "rawGraphStatus",
            "trackAuthority",
            "trackKey",
            "rank",
            "maxRank",
            "trackItemLevel",
            "trackStatus",
            "sourceEligibilityStatus",
            "sourceEligibilityEvidence",
            "uncomposedComponentEvidence",
            "variantStatus",
            "simcReadiness",
            "reasonCodes",
            "status",
        )
        if key in variant
    } | {
        "variantComposition": compact_composition,
        "bonusType50Evidence": bonus_type50,
        "bonusListGroupEntry": compact_group_entry,
        "upgradeGroupEvidence": compact_group_evidence,
        "selectorFacts": compact_selector_facts,
        "trackAuthority": compact_track_authority,
        "sourceEligibilityEvidence": compact_source_evidence,
        "itemScalingEvidence": scaling_evidence,
        "evidenceKeys": {
            "nodeIds": sorted(set(node_ids), key=int),
            "bonusListIds": sorted(
                {_text(value) for value in variant.get("bonusListIds") or [] if _text(value)},
                key=int,
            ),
            "bonusListGroupIds": (
                [_text(variant.get("bonusListGroupId"))]
                if _text(variant.get("bonusListGroupId"))
                else []
            ),
            "groupEntryIds": (
                [_text(group_entry.get("ID"))]
                if isinstance(group_entry, Mapping) and _text(group_entry.get("ID"))
                else []
            ),
            "selectorIds": selector_ids,
            "scalingConfigIds": sorted(set(scaling_config_ids), key=int),
            "curveIds": sorted(set(curve_ids), key=int),
            "curvePointIds": sorted(set(curve_point_ids), key=int),
            "levelDeltaBonusListIds": sorted(set(level_delta_ids), key=int),
            "conditionIds": sorted(
                {
                    _text(value)
                    for value in compact_group_evidence.get("conditionIds") or []
                    if _text(value)
                },
                key=int,
            ),
        },
    }


def _crafted_selection_contract(
    edge: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Project verified crafted compatibility edges without enumerating them."""

    fields = (
        ("secondaryStats", "secondaryStatCompatibility"),
        ("embellishment", "embellishmentCompatibility"),
        ("enhancement", "enhancementCompatibility"),
    )
    result: dict[str, dict[str, Any]] = {}
    for output_key, edge_key in fields:
        raw = edge.get(edge_key)
        payload = dict(raw) if isinstance(raw, Mapping) else {}
        result[output_key] = {
            "status": _text(payload.get("status")) or "UNVERIFIED",
            "options": [
                dict(option)
                for option in payload.get("options") or []
                if isinstance(option, Mapping)
            ],
            "evidenceRefs": sorted(
                {
                    _text(value)
                    for value in payload.get("evidenceRefs") or []
                    if _text(value)
                }
            ),
        }
    return result


def _crafted_quality_option_rows(
    quality_variants: Mapping[str, Any],
) -> list[dict[str, Any]]:
    raw_options = quality_variants.get("qualityOptions")
    if isinstance(raw_options, list) and raw_options:
        return [dict(option) for option in raw_options if isinstance(option, Mapping)]
    quality_ids = [
        _text(value)
        for value in quality_variants.get("qualityIds") or []
        if _text(value)
    ]
    quality_tiers = [
        value
        for value in quality_variants.get("qualityTiers") or []
        if isinstance(value, int) and not isinstance(value, bool)
    ]
    return [
        {
            "qualityId": quality_id,
            "qualityTier": quality_tiers[index]
            if index < len(quality_tiers)
            else None,
            "status": "verified"
            if _text(quality_variants.get("status")) == "verified"
            else "UNVERIFIED",
        }
        for index, quality_id in enumerate(quality_ids)
    ]


def _canonical_crafted_quality_simc_input(
    *,
    item_id: str,
    item_slot: str,
    quality_option: Mapping[str, Any],
    quality_status: str,
    track_option: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize one recipe output/quality pair without selecting modifiers."""

    quality_id = _text(quality_option.get("qualityId"))
    try:
        quality_tier = int(quality_option.get("qualityTier") or 0)
    except (TypeError, ValueError):
        quality_tier = 0
    bonus_ids = [
        _text(value)
        for value in quality_option.get("bonusListIds") or []
        if _text(value)
    ]
    try:
        item_level = int(quality_option.get("itemLevel") or 0)
    except (TypeError, ValueError):
        item_level = 0
    track = dict(track_option) if isinstance(track_option, Mapping) else {}
    track_key = _text(track.get("trackKey"))
    track_currency_id = _text(track.get("currencyTypeId"))
    track_status = _text(track.get("status")) or "not_required"
    if track:
        try:
            item_level = int(track.get("itemLevel") or 0)
        except (TypeError, ValueError):
            item_level = 0
    reasons: set[str] = set()
    if not _text(item_id):
        reasons.add("SIMC_CANONICAL_ITEM_ID_MISSING")
    if not _text(item_slot):
        reasons.add("SIMC_CANONICAL_ITEM_SLOT_MISSING")
    if _text(quality_status) != "verified" or _text(quality_option.get("status")) not in {
        "",
        "verified",
    }:
        reasons.add("CRAFTED_QUALITY_FACT_UNVERIFIED")
    if not quality_id or quality_tier <= 0:
        reasons.add("CRAFTED_QUALITY_ID_OR_TIER_MISSING")
    if item_level <= 0:
        reasons.add("CRAFTED_QUALITY_ITEM_LEVEL_MISSING")
    if not bonus_ids:
        reasons.add("CRAFTED_QUALITY_BONUS_VECTOR_MISSING")
    if track and track_status != "verified":
        reasons.add("CRAFTED_TRACK_FACT_UNVERIFIED")

    options: dict[str, str] = {
        "id": _text(item_id),
        "crafted_quality_id": quality_id,
        "crafted_quality_tier": str(quality_tier) if quality_tier > 0 else "",
    }
    if track_currency_id:
        options["crafted_track_currency_id"] = track_currency_id
    if item_level > 0:
        options["ilevel"] = str(item_level)
    if bonus_ids:
        options["bonus_id"] = "/".join(bonus_ids)
    line = f"{_text(item_slot) or 'unknown'}=s2_crafted,id={_text(item_id)}"
    if item_level > 0:
        line += f",ilevel={item_level}"
    if bonus_ids:
        line += f",bonus_id={'/'.join(bonus_ids)}"
    return {
        "schemaRevision": "s2-canonical-simc-crafted-quality-input-v1",
        "status": "verified" if not reasons else "blocked",
        "simcReadiness": "blocked",
        "itemId": _text(item_id),
        "slot": _text(item_slot) or None,
        "qualityId": quality_id or None,
        "qualityTier": quality_tier or None,
        "craftedTrackKey": track_key or None,
        "craftedTrackCurrencyId": track_currency_id or None,
        "itemLevel": item_level or None,
        "bonusIds": bonus_ids,
        "simcOptions": options,
        "line": line,
        "reasonCodes": sorted(reasons),
    }


def _build_crafted_variant_templates(
    edge: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Create one public quality template per crafted output edge.

    Secondary stats, embellishments, and other crafted enhancements remain
    compatibility edges on the template.  The resolver may later choose one
    legal option; the closure must not pretend that every Cartesian product
    has been simulated here.
    """

    quality_variants = edge.get("qualityVariants")
    quality_variants = (
        dict(quality_variants) if isinstance(quality_variants, Mapping) else {}
    )
    options = _crafted_quality_option_rows(quality_variants)
    if not options:
        return []
    item_id = _text(edge.get("itemId"))
    recipe_id = _text(edge.get("recipeId"))
    item_slot = _text(edge.get("itemSlot"))
    selection_contract = _crafted_selection_contract(edge)
    evidence_refs = {
        _text(value)
        for value in quality_variants.get("evidenceRefs") or []
        if _text(value)
    }
    evidence_refs.update(
        ref
        for field in selection_contract.values()
        for ref in field.get("evidenceRefs") or []
    )
    raw_currency_options = [
        dict(option)
        for option in selection_contract.get("enhancement", {}).get("options") or []
        if isinstance(option, Mapping) and _text(option.get("kind")) == "currency"
    ]
    track_options: list[dict[str, Any] | None] = []
    if not raw_currency_options:
        track_options = [None]
    else:
        quality_levels = [
            int(option.get("itemLevel"))
            for option in options
            if isinstance(option.get("itemLevel"), int)
            and not isinstance(option.get("itemLevel"), bool)
            and int(option.get("itemLevel")) > 0
        ]
        quality_floor = min(quality_levels) if quality_levels else None
        for raw_track in raw_currency_options:
            description = _text(raw_track.get("description"))
            match = _CRAFTED_TRACK_RANGE_PATTERN.search(description)
            track_name = _text(raw_track.get("name")).split(" ", 1)[0].lower()
            track_status = _text(raw_track.get("evidenceStatus")) or "UNVERIFIED"
            track = {
                **raw_track,
                "trackKey": track_name or None,
                "status": "verified"
                if track_status == "verified" and match and quality_floor is not None
                else "UNVERIFIED",
                "itemLevelRange": (
                    [int(match.group("minimum")), int(match.group("maximum"))]
                    if match
                    else None
                ),
            }
            if match and quality_floor is not None:
                # Type 52 Value_0 is carried by the quality fact.  The
                # fallback to the observed quality level delta keeps the
                # helper deterministic for compact synthetic inputs.
                minimum_quality_option = min(
                    options,
                    key=lambda value: int(value.get("qualityTier") or 0),
                )
                raw_bonus = minimum_quality_option.get("bonusType52")
                if isinstance(raw_bonus, Mapping):
                    try:
                        quality_offset = int(raw_bonus.get("Value_0") or 0)
                    except (TypeError, ValueError):
                        quality_offset = None
                else:
                    quality_offset = None
                if quality_offset is None:
                    try:
                        quality_offset = (
                            int(minimum_quality_option.get("itemLevel") or 0)
                            - quality_floor
                        )
                    except (TypeError, ValueError):
                        quality_offset = None
                track["qualityFloor"] = quality_floor
                track["qualityOffsetSource"] = (
                    "qualityOption.bonusType52.Value_0"
                    if isinstance(raw_bonus, Mapping)
                    else "qualityOption.itemLevel_delta"
                )
                track["_qualityOffset"] = quality_offset
            track_options.append(track)
    templates: list[dict[str, Any]] = []
    for option in options:
        try:
            tier = int(option.get("qualityTier") or 0)
        except (TypeError, ValueError):
            tier = 0
        key_tier = str(tier) if tier > 0 else _text(option.get("qualityId")) or "unknown"
        for track in track_options:
            selected_track = dict(track) if isinstance(track, Mapping) else None
            if selected_track is not None:
                try:
                    minimum = int((selected_track.get("itemLevelRange") or [0])[0])
                    raw_bonus = option.get("bonusType52")
                    if isinstance(raw_bonus, Mapping):
                        offset = int(raw_bonus.get("Value_0") or 0)
                    else:
                        offset = int(option.get("itemLevel") or 0) - int(
                            selected_track.get("qualityFloor") or 0
                        )
                    selected_track["itemLevel"] = minimum + offset
                except (TypeError, ValueError, IndexError):
                    selected_track["status"] = "UNVERIFIED"
            canonical = _canonical_crafted_quality_simc_input(
                item_id=item_id,
                item_slot=item_slot,
                quality_option=option,
                quality_status=_text(quality_variants.get("status")),
                track_option=selected_track,
            )
            option_refs = {
                _text(value)
                for value in option.get("evidenceRefs") or []
                if _text(value)
            }
            if selected_track:
                option_refs.update(selected_track.get("evidenceRefs") or [])
            track_key = _text(selected_track.get("trackKey")) if selected_track else "none"
            variant_key = (
                f"s2-crafted:recipe:{recipe_id}:item:{item_id}:quality:{key_tier}"
            )
            if selected_track:
                variant_key += f":track:{track_key}"
            templates.append(
                {
                    "variantKey": variant_key,
                    "variantKind": "crafted_quality_template",
                    "recipeId": recipe_id,
                    "itemId": item_id,
                    "itemSlot": item_slot or None,
                    "craftedTrackKey": selected_track.get("trackKey") if selected_track else None,
                    "craftedTrackCurrencyId": (
                        selected_track.get("currencyTypeId") if selected_track else None
                    ),
                    "quality": {
                        key: option.get(key)
                        for key in (
                            "qualityId",
                            "qualityTier",
                            "qualityPercentage",
                            "order",
                            "itemLevel",
                            "bonusListIds",
                            "status",
                        )
                        if key in option
                    },
                    "selection": {
                        "enhancement": selected_track,
                    },
                    "selectionContract": selection_contract,
                    "canonicalSimcInput": canonical,
                    "evidenceRefs": sorted(evidence_refs | option_refs),
                    "status": "verified"
                    if canonical.get("status") == "verified"
                    else "UNVERIFIED",
                    "simcReadiness": "blocked",
                }
            )
    return templates


def _canonical_simc_variant_input(
    variant: Mapping[str, Any],
    *,
    item_id: str,
    item_slot: str | None,
    static_status: str,
) -> dict[str, Any]:
    """Build a deterministic SimC item input without upgrading evidence.

    The line is serializable even for blocked variants.  Readiness is derived
    from the owning fact fields, so a syntactically valid SimC line can never
    turn an unresolved track, graph, or static-fact owner into ``verified``.
    """

    bonus_ids = [
        _text(value)
        for value in variant.get("bonusListIds") or []
        if _text(value)
    ]
    context_values = sorted(
        {
            _text(value)
            for value in variant.get("itemContextValues") or []
            if _text(value)
        },
        key=lambda value: (0, int(value)) if value.isdigit() else (1, value),
    )
    level_source = ""
    item_level = None
    level_evidence_candidates = (
        (variant.get("officialPreviewItemLevelEvidence"), "official_api.preview_item.level"),
        (variant.get("officialBaseItemLevelEvidence"), "official_api.item.level"),
    )
    for level_evidence, candidate_source in level_evidence_candidates:
        if not (
            isinstance(level_evidence, Mapping)
            and _text(level_evidence.get("status")) == "verified"
        ):
            continue
        try:
            candidate_level = int(level_evidence.get("itemLevel") or 0)
        except (TypeError, ValueError):
            candidate_level = 0
        if candidate_level > 0:
            item_level = candidate_level
            level_source = candidate_source
            break
    if item_level is None:
        raw_track_level = variant.get("trackItemLevel")
        try:
            candidate_level = int(raw_track_level)
        except (TypeError, ValueError):
            candidate_level = 0
        if candidate_level > 0:
            item_level = candidate_level
            level_source = "trackAuthority"
    if item_level is None:
        verified_levels = set()
        observed_levels = set()
        for row in variant.get("itemScalingEvidence") or []:
            try:
                level = int(row.get("itemLevel") or 0)
            except (TypeError, ValueError):
                level = 0
            if level <= 0:
                continue
            observed_levels.add(level)
            if _text(row.get("status")) == "verified":
                verified_levels.add(level)
        if len(verified_levels) == 1:
            item_level = next(iter(verified_levels))
            level_source = "ItemScalingConfig"
        elif len(observed_levels) == 1:
            item_level = next(iter(observed_levels))
            level_source = "ItemScalingConfig:observed"

    reasons: set[str] = set()
    if not _text(item_id):
        reasons.add("SIMC_CANONICAL_ITEM_ID_MISSING")
    if not _text(item_slot):
        reasons.add("SIMC_CANONICAL_ITEM_SLOT_MISSING")
    if not bonus_ids and not variant.get("bonusVectorOptional"):
        reasons.add("SIMC_CANONICAL_BONUS_VECTOR_MISSING")
    if item_level is None:
        reasons.add("SIMC_CANONICAL_ITEM_LEVEL_MISSING")
    if _text(variant.get("numericVariantEvidenceStatus")) != "verified":
        reasons.add("SIMC_CANONICAL_NUMERIC_FACT_UNVERIFIED")
    if _text(variant.get("rawGraphStatus")) != "verified":
        reasons.add("SIMC_CANONICAL_RAW_GRAPH_UNVERIFIED")
    if _text(variant.get("variantStatus")) == "excluded":
        status = "excluded"
    else:
        if _text(variant.get("variantStatus")) != "verified":
            reasons.add("SIMC_CANONICAL_VARIANT_NOT_VERIFIED")
        if _text(static_status) != "verified":
            reasons.add("SIMC_CANONICAL_STATIC_FACT_UNVERIFIED")
        status = "verified" if not reasons else "blocked"

    options: dict[str, str] = {
        "id": _text(item_id),
        "bonus_id": "/".join(bonus_ids),
    }
    if item_level is not None:
        options["ilevel"] = str(item_level)
    if len(context_values) == 1:
        options["context"] = context_values[0]
    slot = _text(item_slot)
    line = f"{slot}=s2_item,id={_text(item_id)}"
    if item_level is not None:
        line += f",ilevel={item_level}"
    if bonus_ids:
        line += f",bonus_id={'/'.join(bonus_ids)}"
    if len(context_values) == 1:
        line += f",context={context_values[0]}"
    return {
        "schemaRevision": "s2-canonical-simc-item-input-v1",
        "status": status,
        "itemId": _text(item_id),
        "slot": slot or None,
        "bonusIds": bonus_ids,
        "itemLevel": item_level,
        "itemLevelSource": level_source or None,
        "itemContextValues": context_values,
        "staticFactsStatus": _text(static_status) or "UNVERIFIED",
        "simcOptions": options,
        "line": line,
        "reasonCodes": sorted(reasons),
    }


def _crafted_quality_facts(
    recipe_id: str,
    item_id: str,
    *,
    crafted_recipe_rows: Mapping[str, Mapping[str, Any]],
    db2_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    db2_refs: Mapping[tuple[str, str], list[str]],
) -> dict[str, Any]:
    crafting_rows = [
        row for row in db2_rows.get("CraftingData", [])
        if _text(row.get("CraftedItemID")) == item_id
    ]
    if not crafting_rows:
        return {
            "status": "UNVERIFIED",
            "recipeId": recipe_id,
            "craftingDataIds": [],
            "qualityTiers": [],
            "evidenceRefs": [],
        }
    difficulty_ids = sorted(
        {
            _text(row.get("CraftingDifficultyID"))
            for row in crafting_rows
            if _text(row.get("CraftingDifficultyID"))
        },
        key=int,
    )
    quality_rows = [
        row for row in db2_rows.get("CraftingDifficultyQuality", [])
        if _text(row.get("CraftingDifficultyID")) in set(difficulty_ids)
    ]
    quality_ids = sorted(
        {_text(row.get("CraftingQualityID")) for row in quality_rows},
        key=int,
    )
    tier_map = {
        _text(row.get("ID")): row.get("QualityTier")
        for row in db2_rows.get("CraftingQuality", [])
    }
    quality_tiers = sorted(
        {
            int(tier_map[quality_id])
            for quality_id in quality_ids
            if quality_id in tier_map and isinstance(tier_map[quality_id], int)
        }
    )
    quality_options: list[dict[str, Any]] = []
    seen_quality_ids: set[str] = set()
    for row in sorted(
        quality_rows,
        key=lambda value: (
            int(value.get("_Order") or 0),
            int(value.get("ID") or 0),
        ),
    ):
        quality_id = _text(row.get("CraftingQualityID"))
        if not quality_id or quality_id in seen_quality_ids:
            continue
        seen_quality_ids.add(quality_id)
        tier = tier_map.get(quality_id)
        quality_options.append(
            {
                "qualityId": quality_id,
                "qualityTier": tier,
                "qualityPercentage": row.get("QualityPercentage"),
                "order": row.get("_Order"),
                "status": "verified"
                if isinstance(tier, int)
                and not isinstance(tier, bool)
                and isinstance(row.get("QualityPercentage"), int)
                else "UNVERIFIED",
                "evidenceRefs": sorted(
                    set(_row_ref(row, table="CraftingDifficultyQuality", refs=db2_refs))
                    | {
                        ref
                        for quality_row in db2_rows.get("CraftingQuality", [])
                        if _text(quality_row.get("ID")) == quality_id
                        for ref in _row_ref(
                            quality_row,
                            table="CraftingQuality",
                            refs=db2_refs,
                        )
                    }
                ),
            }
        )
    # CraftingData points to the quality-only bonus tree.  The output item
    # contributes the DB2 base ItemSparse level; each exact quality leaf
    # contributes one Type 52 offset and one stable bonus-list id.  Do not
    # publish a quality until the tree, list, bonus, and quality index agree.
    item_sparse_rows = [
        row
        for row in db2_rows.get("ItemSparse", [])
        if _text(row.get("ID")) == item_id
    ]
    base_item_level = None
    if len(item_sparse_rows) == 1:
        raw_level = item_sparse_rows[0].get("ItemLevel")
        if isinstance(raw_level, int) and not isinstance(raw_level, bool) and raw_level > 0:
            base_item_level = raw_level

    quality_tree_ids = sorted(
        {
            _text(row.get("ItemBonusTreeID"))
            for row in crafting_rows
            if _text(row.get("ItemBonusTreeID"))
        },
        key=int,
    )
    nodes_by_parent = _index(db2_rows, "ItemBonusTreeNode", "ParentItemBonusTreeID")
    pending_tree_ids = list(quality_tree_ids)
    visited_tree_ids: set[str] = set()
    quality_group_ids: set[str] = set()
    quality_direct_bonus_ids: set[str] = set()
    while pending_tree_ids:
        tree_id = pending_tree_ids.pop()
        if tree_id in visited_tree_ids:
            continue
        visited_tree_ids.add(tree_id)
        for node in nodes_by_parent.get(tree_id, []):
            child_tree_id = _text(node.get("ChildItemBonusTreeID"))
            if child_tree_id and child_tree_id != "0":
                pending_tree_ids.append(child_tree_id)
            group_id = _text(node.get("ChildItemBonusListGroupID"))
            if group_id and group_id != "0":
                quality_group_ids.add(group_id)
            direct_bonus_id = _text(node.get("ChildItemBonusListID"))
            if direct_bonus_id and direct_bonus_id != "0":
                quality_direct_bonus_ids.add(direct_bonus_id)

    base_bonus_tree_ids = sorted(
        {
            _text(row.get("ItemBonusTreeID"))
            for row in db2_rows.get("ItemXBonusTree", [])
            if _text(row.get("ItemID")) == item_id
            and _text(row.get("ItemBonusTreeID"))
        },
        key=int,
    )
    base_pending_tree_ids = list(base_bonus_tree_ids)
    base_visited_tree_ids: set[str] = set()
    base_bonus_list_ids: list[str] = []
    base_bonus_nodes: list[Mapping[str, Any]] = []
    base_mapping_reason = None
    while base_pending_tree_ids:
        tree_id = base_pending_tree_ids.pop()
        if tree_id in base_visited_tree_ids:
            continue
        base_visited_tree_ids.add(tree_id)
        for node in sorted(
            nodes_by_parent.get(tree_id, []),
            key=lambda row: int(row.get("ID") or 0),
        ):
            base_bonus_nodes.append(node)
            child_tree_id = _text(node.get("ChildItemBonusTreeID"))
            if child_tree_id and child_tree_id != "0":
                base_pending_tree_ids.append(child_tree_id)
            if _text(node.get("ChildItemBonusListGroupID")) not in {"", "0"}:
                base_mapping_reason = "CRAFTED_BASE_BONUS_GROUP_UNVERIFIED"
            direct_bonus_id = _text(node.get("ChildItemBonusListID"))
            if direct_bonus_id and direct_bonus_id != "0":
                base_bonus_list_ids.append(direct_bonus_id)
    base_bonus_list_ids = list(dict.fromkeys(base_bonus_list_ids))
    base_levels: set[int] = set()
    if base_bonus_list_ids:
        for bonus in db2_rows.get("ItemBonus", []):
            if _text(bonus.get("ParentItemBonusListID")) not in set(base_bonus_list_ids):
                continue
            if _text(bonus.get("Type")) not in {"49", "51"}:
                continue
            scaling_id = _text(bonus.get("Value_0"))
            for scaling in db2_rows.get("ItemScalingConfig", []):
                if _text(scaling.get("ID")) == scaling_id:
                    raw_level = scaling.get("ItemLevel")
                    if isinstance(raw_level, int) and raw_level > 0:
                        base_levels.add(raw_level)
        for bonus_list_id in base_bonus_list_ids:
            if not any(
                _text(row.get("ID")) == bonus_list_id
                for row in db2_rows.get("ItemBonusList", [])
            ):
                base_mapping_reason = "CRAFTED_BASE_BONUS_LIST_MISSING"
        if len(base_levels) > 1:
            base_mapping_reason = "CRAFTED_BASE_ITEM_LEVEL_AMBIGUOUS"
    elif not base_bonus_tree_ids:
        base_mapping_reason = "CRAFTED_BASE_BONUS_TREE_MISSING"
    if base_mapping_reason is None and not base_bonus_list_ids:
        base_mapping_reason = "CRAFTED_BASE_BONUS_VECTOR_MISSING"
    if base_mapping_reason is None and base_levels:
        base_item_level = next(iter(base_levels))

    quality_mapping_reason = base_mapping_reason
    if len(quality_tree_ids) != 1:
        quality_mapping_reason = "CRAFTED_QUALITY_BONUS_TREE_AMBIGUOUS"
    elif not base_item_level:
        quality_mapping_reason = "CRAFTED_QUALITY_BASE_ITEM_LEVEL_MISSING"
    elif len(quality_group_ids) != 1 or quality_direct_bonus_ids:
        quality_mapping_reason = "CRAFTED_QUALITY_BONUS_TREE_COMPOSITION_UNVERIFIED"
    else:
        quality_group_id = next(iter(quality_group_ids))
        group_entries = sorted(
            [
                row
                for row in db2_rows.get("ItemBonusListGroupEntry", [])
                if _text(row.get("ItemBonusListGroupID")) == quality_group_id
            ],
            key=lambda row: (
                int(row.get("SequenceValue") or 0),
                int(row.get("ID") or 0),
            ),
        )
        option_by_order = {
            int(option.get("order")): option
            for option in quality_options
            if isinstance(option.get("order"), int)
            and not isinstance(option.get("order"), bool)
        }
        if len(group_entries) != len(quality_options) or not option_by_order:
            quality_mapping_reason = "CRAFTED_QUALITY_BONUS_GROUP_CARDINALITY_UNVERIFIED"
        else:
            for entry in group_entries:
                sequence = entry.get("SequenceValue")
                option = option_by_order.get(int(sequence or 0) - 1)
                bonus_list_id = _text(entry.get("ItemBonusListID"))
                if option is None or not bonus_list_id:
                    quality_mapping_reason = "CRAFTED_QUALITY_BONUS_GROUP_ORDER_UNVERIFIED"
                    break
                list_rows = [
                    row
                    for row in db2_rows.get("ItemBonusList", [])
                    if _text(row.get("ID")) == bonus_list_id
                ]
                bonus_rows = [
                    row
                    for row in db2_rows.get("ItemBonus", [])
                    if _text(row.get("ParentItemBonusListID")) == bonus_list_id
                    and _text(row.get("Type")) == "52"
                ]
                quality_tier = option.get("qualityTier")
                type52 = bonus_rows[0] if len(bonus_rows) == 1 else None
                try:
                    offset = int(type52.get("Value_0")) if type52 else -1
                    quality_index = int(type52.get("Value_2")) if type52 else -1
                except (TypeError, ValueError):
                    offset = -1
                    quality_index = -1
                if (
                    len(list_rows) != 1
                    or type52 is None
                    or not isinstance(quality_tier, int)
                    or quality_index != quality_tier - 1
                    or offset < 0
                ):
                    quality_mapping_reason = "CRAFTED_QUALITY_BONUS_OFFSET_UNVERIFIED"
                    break
                option.update(
                    {
                        "bonusListIds": [*base_bonus_list_ids, bonus_list_id],
                        "itemLevel": base_item_level + offset,
                        "itemLevelSource": (
                            "ItemScalingConfig_or_ItemSparse_plus_ItemBonus.Type52.Value_0"
                        ),
                        "bonusType52": {
                            key: type52.get(key)
                            for key in (
                                "ID",
                                "ParentItemBonusListID",
                                "Type",
                                "Value_0",
                                "Value_1",
                                "Value_2",
                                "Value_3",
                            )
                            if key in type52
                        },
                        "bonusMappingStatus": "verified",
                    }
                )
    if quality_mapping_reason:
        for option in quality_options:
            option.setdefault("bonusMappingStatus", "UNVERIFIED")
            option.setdefault("reasonCode", quality_mapping_reason)
    refs: set[str] = set()
    for row in crafting_rows + quality_rows:
        table = "CraftingData" if row in crafting_rows else "CraftingDifficultyQuality"
        refs.update(_row_ref(row, table=table, refs=db2_refs))
    refs.update(
        ref
        for row in db2_rows.get("CraftingQuality", [])
        if _text(row.get("ID")) in set(quality_ids)
        for ref in _row_ref(row, table="CraftingQuality", refs=db2_refs)
    )
    refs.update(
        ref
        for row in item_sparse_rows
        for ref in _row_ref(row, table="ItemSparse", refs=db2_refs)
    )
    refs.update(
        ref
        for tree_id in quality_tree_ids
        for row in db2_rows.get("ItemBonusTree", [])
        if _text(row.get("ID")) == tree_id
        for ref in _row_ref(row, table="ItemBonusTree", refs=db2_refs)
    )
    refs.update(
        ref
        for tree_id in visited_tree_ids
        for row in nodes_by_parent.get(tree_id, [])
        for ref in _row_ref(row, table="ItemBonusTreeNode", refs=db2_refs)
    )
    refs.update(
        ref
        for option in quality_options
        for ref in option.get("evidenceRefs") or []
    )
    refs.update(
        ref
        for tree_id in base_visited_tree_ids
        for row in db2_rows.get("ItemBonusTree", [])
        if _text(row.get("ID")) == tree_id
        for ref in _row_ref(row, table="ItemBonusTree", refs=db2_refs)
    )
    refs.update(
        ref
        for row in base_bonus_nodes
        for ref in _row_ref(row, table="ItemBonusTreeNode", refs=db2_refs)
    )
    refs.update(
        ref
        for row in db2_rows.get("ItemBonusList", [])
        if _text(row.get("ID")) in set(base_bonus_list_ids)
        for ref in _row_ref(row, table="ItemBonusList", refs=db2_refs)
    )
    refs.update(
        ref
        for row in db2_rows.get("ItemBonus", [])
        if _text(row.get("ParentItemBonusListID")) in set(base_bonus_list_ids)
        for ref in _row_ref(row, table="ItemBonus", refs=db2_refs)
    )
    refs.update(
        ref
        for row in db2_rows.get("ItemScalingConfig", [])
        if row.get("ItemLevel") in base_levels
        for ref in _row_ref(row, table="ItemScalingConfig", refs=db2_refs)
    )
    quality_status = (
        "verified"
        if set(quality_tiers) == {1, 2, 3, 4, 5}
        and not quality_mapping_reason
        and quality_options
        and all(
            option.get("status") == "verified"
            and option.get("bonusMappingStatus") == "verified"
            for option in quality_options
        )
        else "UNVERIFIED"
    )
    return {
        "status": quality_status,
        "recipeId": recipe_id,
        "craftingDataIds": sorted({_text(row.get("ID")) for row in crafting_rows}, key=int),
        "craftingDifficultyIds": difficulty_ids,
        "qualityIds": quality_ids,
        "qualityTiers": quality_tiers,
        "qualityOptions": quality_options,
        "baseItemLevel": base_item_level,
        "qualityBonusTreeIds": quality_tree_ids,
        "qualityBonusListGroupIds": sorted(quality_group_ids, key=int),
        "qualityMappingReasonCode": quality_mapping_reason,
        "evidenceRefs": sorted(refs),
        "recipeMetadata": crafted_recipe_rows.get(recipe_id, {}),
    }


def _conversion_bonus_tree_facts(
    root_ids: Sequence[str],
    *,
    db2_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    db2_refs: Mapping[tuple[str, str], list[str]],
) -> dict[str, Any]:
    """Resolve the bounded conversion tree without assigning bonus semantics."""

    nodes_by_parent = _index(db2_rows, "ItemBonusTreeNode", "ParentItemBonusTreeID")
    item_bonus_lists = _index(db2_rows, "ItemBonusList", "ID")
    bonus_rows_by_list = _index(db2_rows, "ItemBonus", "ParentItemBonusListID")
    pending = [str(value) for value in root_ids if _ID_PATTERN.fullmatch(str(value))]
    visited: set[str] = set()
    nodes: list[Mapping[str, Any]] = []
    missing_tree_ids: set[str] = set()
    unsupported_node_ids: set[str] = set()
    leaf_ids: set[str] = set()
    refs: set[str] = set()

    while pending:
        tree_id = pending.pop()
        if tree_id in visited:
            continue
        visited.add(tree_id)
        tree_nodes = nodes_by_parent.get(tree_id, [])
        if not tree_nodes:
            missing_tree_ids.add(tree_id)
            refs.update(
                db2_refs.get(
                    ("ItemBonusTreeNode", f"__query__:ParentItemBonusTreeID:{tree_id}"),
                    [],
                )
            )
            continue
        for node in tree_nodes:
            nodes.append(node)
            refs.update(_row_ref(node, table="ItemBonusTreeNode", refs=db2_refs))
            child_tree_id = _text(node.get("ChildItemBonusTreeID"))
            child_list_id = _text(node.get("ChildItemBonusListID"))
            child_group_id = _text(node.get("ChildItemBonusListGroupID"))
            selector_id = _text(node.get("ChildItemLevelSelectorID"))
            if child_tree_id and child_tree_id != "0":
                pending.append(child_tree_id)
            elif child_list_id and child_list_id != "0":
                leaf_ids.add(child_list_id)
            else:
                unsupported_node_ids.add(_text(node.get("ID")))
                if child_group_id and child_group_id != "0":
                    refs.update(
                        db2_refs.get(
                            (
                                "ItemBonusListGroupEntry",
                                f"__query__:ItemBonusListGroupID:{child_group_id}",
                            ),
                            [],
                        )
                    )
                if selector_id and selector_id != "0":
                    refs.update(
                        db2_refs.get(
                            (
                                "ItemLevelSelector",
                                f"__query__:ID:{selector_id}",
                            ),
                            [],
                        )
                    )

    bonus_list_facts = []
    for bonus_list_id in sorted(leaf_ids, key=int):
        list_rows = item_bonus_lists.get(bonus_list_id, [])
        bonus_rows = sorted(
            bonus_rows_by_list.get(bonus_list_id, []),
            key=lambda row: int(row.get("ID") or 0),
        )
        for row in list_rows:
            refs.update(_row_ref(row, table="ItemBonusList", refs=db2_refs))
        for row in bonus_rows:
            refs.update(_row_ref(row, table="ItemBonus", refs=db2_refs))
        if not list_rows:
            refs.update(
                db2_refs.get(
                    ("ItemBonusList", f"__query__:ID:{bonus_list_id}"),
                    [],
                )
            )
        if not bonus_rows:
            refs.update(
                db2_refs.get(
                    (
                        "ItemBonus",
                        f"__query__:ParentItemBonusListID:{bonus_list_id}",
                    ),
                    [],
                )
            )
        bonus_list_facts.append(
            {
                "bonusListId": bonus_list_id,
                "status": "verified" if list_rows else "UNVERIFIED",
                "bonusRows": [
                    {
                        key: row.get(key)
                        for key in (
                            "ID",
                            "ParentItemBonusListID",
                            "Type",
                            "Value_0",
                            "Value_1",
                            "Value_2",
                            "Value_3",
                        )
                        if key in row
                    }
                    for row in bonus_rows
                ],
                "evidenceRefs": sorted(
                    set(
                        ref
                        for row in list_rows
                        for ref in _row_ref(row, table="ItemBonusList", refs=db2_refs)
                    )
                    | set(
                        ref
                        for row in bonus_rows
                        for ref in _row_ref(row, table="ItemBonus", refs=db2_refs)
                    )
                ),
            }
        )

    tree_status = (
        "verified"
        if visited and not missing_tree_ids and not unsupported_node_ids
        else "UNVERIFIED"
    )
    return {
        "status": tree_status,
        "rootTreeIds": sorted(set(root_ids), key=int),
        "reachableTreeIds": sorted(visited, key=int),
        "missingTreeIds": sorted(missing_tree_ids, key=int),
        "unsupportedNodeIds": sorted(
            {value for value in unsupported_node_ids if value},
            key=int,
        ),
        "nodeFacts": [
            {
                key: row.get(key)
                for key in (
                    "ID",
                    "ParentItemBonusTreeID",
                    "ChildItemBonusTreeID",
                    "ChildItemBonusListID",
                    "ChildItemBonusListGroupID",
                    "ChildItemLevelSelectorID",
                )
                if key in row
            }
            for row in sorted(nodes, key=lambda row: int(row.get("ID") or 0))
        ],
        "leafBonusListIds": sorted(leaf_ids, key=int),
        "bonusListFacts": bonus_list_facts,
        "evidenceRefs": sorted(refs),
    }


def _conversion_fact(
    item_id: str,
    tier_rows: Sequence[Mapping[str, Any]],
    *,
    db2_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    db2_refs: Mapping[tuple[str, str], list[str]],
    static_row: Mapping[str, Any] | None,
    official_payload: Mapping[str, Any] | None,
    official_set_facts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    entries = [row for row in db2_rows.get("ItemConversionEntry", []) if _text(row.get("ItemID")) == item_id]
    refs: set[str] = set()
    for row in entries:
        refs.update(_row_ref(row, table="ItemConversionEntry", refs=db2_refs))
    conversion_ids = sorted({_text(row.get("ItemConversionID")) for row in entries if _text(row.get("ItemConversionID"))}, key=int)
    conversions = [
        row for row in db2_rows.get("ItemConversion", [])
        if _text(row.get("ID")) in set(conversion_ids)
    ]
    for row in conversions:
        refs.update(_row_ref(row, table="ItemConversion", refs=db2_refs))
    conversion_tree_ids = sorted({_text(row.get("ItemBonusTreeID")) for row in conversions if _text(row.get("ItemBonusTreeID"))}, key=int)
    set_membership_ids = sorted(
        {_text(row.get("setId")) for row in tier_rows if _text(row.get("setId"))},
        key=int,
    )
    set_membership_facts = [
        dict(official_set_facts.get(set_id) or {
            "setId": set_id,
            "status": "UNVERIFIED",
            "reasonCode": "OFFICIAL_ITEM_SET_FACT_MISSING",
            "effects": [],
            "evidenceRefs": [],
        })
        for set_id in set_membership_ids
    ]
    for fact in set_membership_facts:
        refs.update(fact.get("evidenceRefs") or [])

    identity_status = (
        "verified"
        if isinstance(official_payload, Mapping)
        and _text(official_payload.get("id")) == item_id
        and entries
        and conversions
        else "UNVERIFIED"
    )
    original_static_facts = _item_static_facts(static_row)
    green_stat_facts = (original_static_facts or {}).get("greenStatSlots", [])
    green_status = "verified" if static_row is not None else "UNVERIFIED"
    preservation = {
        "originalItemId": item_id,
        "originalStaticFacts": original_static_facts,
        "originalGreenStatFacts": green_stat_facts,
        "originalSpecialEffectFacts": [],
        "setMembershipIds": set_membership_ids,
        "identity": {
            "beforeItemId": item_id,
            "afterItemId": item_id,
            "status": identity_status,
            "proof": "same_official_item_identity_and_conversion_entry",
        },
        "greenStats": {
            "before": green_stat_facts,
            "after": green_stat_facts,
            "status": green_status,
            "proof": "same_item_sparse_static_facts",
        },
        "setMembershipFacts": set_membership_facts,
        "status": "UNVERIFIED",
        "reasonCode": "TIER_CONVERSION_PRESERVATION_UNVERIFIED",
    }
    if static_row is not None:
        refs.update(_row_ref(static_row, table="ItemSparse", refs=db2_refs))
    item_effect_rows = [
        row for row in db2_rows.get("ItemXItemEffect", [])
        if _text(row.get("ItemID")) == item_id
    ]
    for row in item_effect_rows:
        refs.update(_row_ref(row, table="ItemXItemEffect", refs=db2_refs))
    item_effect_query_refs = db2_refs.get(
        ("ItemXItemEffect", f"__query__:ItemID:{item_id}"),
        [],
    )
    if item_effect_rows:
        item_effect_by_id = _index(db2_rows, "ItemEffect", "ID")
        spell_by_id = _index(db2_rows, "Spell", "ID")
        spell_name_by_id = _index(db2_rows, "SpellName", "ID")
        spell_effect_by_id = _index(db2_rows, "SpellEffect", "SpellID")
        special_effect_facts: list[dict[str, Any]] = []
        special_effect_statuses: list[str] = []
        for relation in item_effect_rows:
            item_effect_id = _text(relation.get("ItemEffectID"))
            effect_rows = item_effect_by_id.get(item_effect_id, [])
            for effect_row in effect_rows:
                refs.update(_row_ref(effect_row, table="ItemEffect", refs=db2_refs))
            if not item_effect_id or not effect_rows:
                special_effect_facts.append(
                    {
                        "itemEffectId": item_effect_id or None,
                        "status": "UNVERIFIED",
                        "preserved": False,
                        "reasonCode": "TIER_CONVERSION_ITEM_EFFECT_FACT_MISSING",
                        "evidenceRefs": _row_ref(
                            relation,
                            table="ItemXItemEffect",
                            refs=db2_refs,
                        ),
                    }
                )
                special_effect_statuses.append("UNVERIFIED")
                continue

            # An ItemXItemEffect relation can theoretically point at more than
            # one exact ItemEffect row in a merged capture.  Every row must be
            # closed before the conversion can claim effect preservation.
            for effect_row in effect_rows:
                spell_id = _text(effect_row.get("SpellID"))
                spell_rows = spell_by_id.get(spell_id, [])
                spell_name_rows = spell_name_by_id.get(spell_id, [])
                spell_effect_rows = spell_effect_by_id.get(spell_id, [])
                for row in spell_rows:
                    refs.update(_row_ref(row, table="Spell", refs=db2_refs))
                for row in spell_name_rows:
                    refs.update(_row_ref(row, table="SpellName", refs=db2_refs))
                for row in spell_effect_rows:
                    refs.update(_row_ref(row, table="SpellEffect", refs=db2_refs))

                spell_effect_query_refs = db2_refs.get(
                    ("SpellEffect", f"__query__:SpellID:{spell_id}"),
                    [],
                )
                if spell_effect_query_refs:
                    refs.update(spell_effect_query_refs)
                effect_status = (
                    "verified"
                    if spell_id
                    and spell_rows
                    and (spell_effect_rows or spell_effect_query_refs)
                    else "UNVERIFIED"
                )
                effect_reason = None if effect_status == "verified" else (
                    "TIER_CONVERSION_SPELL_FACT_MISSING"
                    if not spell_rows
                    else "TIER_CONVERSION_SPELL_EFFECT_FACT_MISSING"
                )
                spell_row = dict(spell_rows[0]) if spell_rows else None
                spell_name_row = dict(spell_name_rows[0]) if spell_name_rows else None
                special_effect_facts.append(
                    {
                        "itemEffectId": item_effect_id,
                        "itemEffect": {
                            key: effect_row.get(key)
                            for key in (
                                "ID",
                                "SpellID",
                                "TriggerType",
                                "LegacySlotIndex",
                                "Charges",
                                "CoolDownMSec",
                                "CategoryCoolDownMSec",
                                "SpellCategoryID",
                                "ChrSpecializationID",
                                "PlayerConditionID",
                            )
                            if key in effect_row
                        },
                        "spellId": spell_id or None,
                        "spell": (
                            {
                                "id": _text(spell_row.get("ID")),
                                "name": _text(spell_row.get("Name_lang")),
                                "description": _text(
                                    spell_row.get("Description_lang")
                                ),
                                "raw": {
                                    key: spell_row.get(key)
                                    for key in ("ID", "Name_lang", "Description_lang")
                                    if key in spell_row
                                },
                            }
                            if spell_row
                            else None
                        ),
                        "spellName": (
                            {
                                "id": _text(spell_name_row.get("ID")),
                                "name": _text(spell_name_row.get("Name_lang")),
                                "raw": {
                                    key: spell_name_row.get(key)
                                    for key in ("ID", "Name_lang")
                                    if key in spell_name_row
                                },
                            }
                            if spell_name_row
                            else None
                        ),
                        "spellEffects": [
                            {
                                "id": _text(row.get("ID")),
                                "spellId": _text(row.get("SpellID")),
                                "effectIndex": row.get("EffectIndex"),
                                "effect": row.get("Effect"),
                                "effectBasePoints": row.get("EffectBasePointsF"),
                                "effectItemType": row.get("EffectItemType"),
                                "effectMiscValue0": row.get("EffectMiscValue_0"),
                                "effectMiscValue1": row.get("EffectMiscValue_1"),
                                "effectTriggerSpell": row.get("EffectTriggerSpell"),
                                "difficultyId": row.get("DifficultyID"),
                                "raw": dict(row),
                            }
                            for row in sorted(
                                spell_effect_rows,
                                key=lambda value: int(value.get("EffectIndex") or 0),
                            )
                        ],
                        "status": effect_status,
                        "preserved": effect_status == "verified",
                        "reasonCode": effect_reason,
                        "evidenceRefs": sorted(
                            set(_row_ref(relation, table="ItemXItemEffect", refs=db2_refs))
                            | set(_row_ref(effect_row, table="ItemEffect", refs=db2_refs))
                            | set(
                                ref
                                for row in spell_rows
                                for ref in _row_ref(row, table="Spell", refs=db2_refs)
                            )
                            | set(
                                ref
                                for row in spell_name_rows
                                for ref in _row_ref(row, table="SpellName", refs=db2_refs)
                            )
                            | set(
                                ref
                                for row in spell_effect_rows
                                for ref in _row_ref(row, table="SpellEffect", refs=db2_refs)
                            )
                            | set(spell_effect_query_refs)
                        ),
                    }
                )
                special_effect_statuses.append(effect_status)
        preservation["originalSpecialEffectFacts"] = special_effect_facts
        if special_effect_statuses and all(
            status in {"verified", "verified_empty"}
            for status in special_effect_statuses
        ):
            preservation["originalSpecialEffectStatus"] = "verified"
            preservation["originalSpecialEffectReasonCode"] = None
        else:
            preservation["originalSpecialEffectStatus"] = "UNVERIFIED"
            preservation["originalSpecialEffectReasonCode"] = (
                "TIER_CONVERSION_EFFECT_SEMANTICS_UNVERIFIED"
            )
            preservation["reasonCode"] = "TIER_CONVERSION_EFFECT_SEMANTICS_UNVERIFIED"
    elif item_effect_query_refs:
        preservation["originalSpecialEffectFacts"] = []
        preservation["originalSpecialEffectStatus"] = "verified_empty"
        preservation["originalSpecialEffectReasonCode"] = None
        preservation["reasonCode"] = "TIER_CONVERSION_PRESERVES_NO_ORIGINAL_SPECIAL_EFFECT"
        refs.update(item_effect_query_refs)
    else:
        preservation["originalSpecialEffectFacts"] = []
        preservation["originalSpecialEffectStatus"] = "UNVERIFIED"
        preservation["originalSpecialEffectReasonCode"] = (
            "TIER_CONVERSION_ORIGINAL_EFFECT_COVERAGE_MISSING"
        )
        preservation["reasonCode"] = "TIER_CONVERSION_ORIGINAL_EFFECT_COVERAGE_MISSING"

    tree_facts = _conversion_bonus_tree_facts(
        conversion_tree_ids,
        db2_rows=db2_rows,
        db2_refs=db2_refs,
    )
    refs.update(tree_facts.get("evidenceRefs") or [])
    preview_bonus_ids = [
        _text(value)
        for value in (
            ((official_payload or {}).get("preview_item") or {}).get("bonus_list")
            or []
        )
        if _text(value)
    ]
    leaf_bonus_ids = set(tree_facts.get("leafBonusListIds") or [])
    preview_match_status = (
        "verified"
        if preview_bonus_ids and set(preview_bonus_ids).issubset(leaf_bonus_ids)
        else "UNVERIFIED"
    )
    preservation["conversionBonusListPreservation"] = {
        "previewBonusListIds": preview_bonus_ids,
        "conversionTreeBonusListIds": sorted(leaf_bonus_ids, key=int),
        "status": preview_match_status,
        "reasonCode": None
        if preview_match_status == "verified"
        else "TIER_CONVERSION_PREVIEW_BONUS_LIST_MISMATCH",
    }
    set_status = (
        "verified"
        if set_membership_facts
        and all(fact.get("status") == "verified" for fact in set_membership_facts)
        else "UNVERIFIED"
    )
    preservation["setMembershipStatus"] = set_status
    preservation_parts = {
        "identity": identity_status,
        "greenStats": green_status,
        "specialEffects": preservation.get("originalSpecialEffectStatus"),
        "setMembership": set_status,
        "conversionBonusLists": preview_match_status,
        "conversionTree": tree_facts.get("status"),
    }
    if all(
        value in {"verified", "verified_empty"}
        for value in preservation_parts.values()
    ):
        preservation["status"] = "verified"
        preservation["reasonCode"] = None
    else:
        preservation["status"] = "UNVERIFIED"
        if preservation["reasonCode"] is None:
            preservation["reasonCode"] = "TIER_CONVERSION_PRESERVATION_UNVERIFIED"
    return {
        "itemId": item_id,
        "status": (
            "verified"
            if entries and conversions and tree_facts.get("status") == "verified"
            else "UNVERIFIED"
        ),
        "conversionIds": conversion_ids,
        "conversionTreeIds": conversion_tree_ids,
        "conversionTreeFacts": tree_facts,
        "previewBonusListIds": preview_bonus_ids,
        "originalItemIdentity": {
            "itemId": item_id,
            "name": _text((official_payload or {}).get("name")),
            "status": identity_status,
            "preserved": identity_status == "verified",
        },
        "preservation": preservation,
        "evidenceRefs": sorted(refs),
    }


def _requires_track_authority(
    memberships: Sequence[Mapping[str, Any]],
    variant: Mapping[str, Any],
) -> bool:
    """Return whether this source edge needs an explicit upgrade-track fact.

    Mythic+ variants are track-bearing even when the raw branch has not yet
    resolved a group.  A normal raid drop is not a Mistcrest track by default;
    only a raid branch that explicitly carries an upgrade group is evaluated
    by the track authority adapter.  This keeps raid base drops from being
    blocked by a currency relationship they do not possess.
    """

    composition = variant.get("variantComposition")
    if (
        isinstance(composition, Mapping)
        and _text(composition.get("kind")) == "empty_base_identity"
    ):
        # An exact empty ItemXBonusTree query proves that this identity has no
        # upgrade-tree relationship.  It is a static item, not an unresolved
        # M+ track.
        return False
    sources = {
        _text(row.get("logicalSource"))
        for row in memberships
        if isinstance(row, Mapping)
    }
    if "mythic_plus" in sources:
        return True
    return "raid" in sources and bool(_text(variant.get("bonusListGroupId")))


def _is_uncomposed_mythic_plus_component(
    variant: Mapping[str, Any],
    *,
    memberships: Sequence[Mapping[str, Any]],
    mythic_plus_item_scope_status: str,
    has_context_slot_vector: bool,
) -> bool:
    """Identify raw DB2 component edges once a final M+ composition exists.

    ``_build_item_variant_records`` retains raw graph edges as evidence.  For
    current S2 M+ items the same graph also yields an observed
    ``db2_context_slot_vector`` containing the complete source-context and
    track selection.  A raw edge for that item is an intermediate component,
    not a second public equipment variant.  Keep it in the evidence graph but
    exclude it from final variant coverage so it cannot create a synthetic
    track blocker or a partial SimC input.
    """

    if mythic_plus_item_scope_status != "verified" or not has_context_slot_vector:
        return False
    if not any(
        _text(row.get("logicalSource")) == "mythic_plus"
        and _text(row.get("scopeStatus")) == "included"
        for row in memberships
        if isinstance(row, Mapping)
    ):
        return False
    composition = variant.get("variantComposition")
    return (
        isinstance(composition, Mapping)
        and _text(composition.get("kind")) == "raw_graph_edge"
    )


def _is_uncomposed_raid_component(
    variant: Mapping[str, Any],
    *,
    memberships: Sequence[Mapping[str, Any]],
    composed_variants: Sequence[Mapping[str, Any]],
) -> bool:
    """Exclude a raid graph leaf only when a verified context vector owns it.

    Raid ItemBonusTree roots are composition trees.  Their direct leaves are
    useful evidence, but are not public item links when the same leaf bonus
    vector is a strict subset of a verified source-context vector.  Matching
    on the exact bonus subset keeps unrelated standalone raid bonuses public.
    """

    if not any(
        _text(row.get("logicalSource")) == "raid"
        and _text(row.get("scopeStatus")) == "included"
        for row in memberships
        if isinstance(row, Mapping)
    ):
        return False
    composition = variant.get("variantComposition")
    if not isinstance(composition, Mapping) or _text(composition.get("kind")) != "raw_graph_edge":
        return False
    raw_bonus_ids = {
        _text(value) for value in variant.get("bonusListIds") or [] if _text(value)
    }
    if not raw_bonus_ids:
        return False
    for composed in composed_variants:
        composed_composition = composed.get("variantComposition")
        if not isinstance(composed_composition, Mapping):
            continue
        if _text(composed_composition.get("kind")) != "db2_context_slot_vector":
            continue
        if not (
            _text(composed.get("variantStatus")) == "verified"
            or (
                _text(composed.get("rawGraphStatus")) == "verified"
                and _text(composed.get("numericVariantEvidenceStatus")) == "verified"
            )
        ):
            continue
        composed_bonus_ids = {
            _text(value) for value in composed.get("bonusListIds") or [] if _text(value)
        }
        if raw_bonus_ids < composed_bonus_ids:
            return True
    return False


def _is_crafted_graph_component(
    variant: Mapping[str, Any],
    *,
    memberships: Sequence[Mapping[str, Any]],
    crafted_templates: Sequence[Mapping[str, Any]],
) -> bool:
    """Keep crafted DB2 graph leaves as evidence once templates own output.

    Crafted quality templates are the public output variants.  The output
    recipe/quality adapter already composes the complete bonus vector, so
    graph leaves must not remain a second public denominator or create a
    numeric blocker for the same recipe.
    """

    if not any(
        _text(row.get("logicalSource")) == "crafted"
        and _text(row.get("scopeStatus")) == "included"
        for row in memberships
        if isinstance(row, Mapping)
    ):
        return False
    composition = variant.get("variantComposition")
    if not isinstance(composition, Mapping):
        return False
    if _text(composition.get("kind")) not in {
        "raw_graph_edge",
        "db2_context_slot_vector",
        "official_preview_vector",
    }:
        return False
    item_id = _text(variant.get("itemId"))
    recipe_ids = {
        _text(row.get("recipeId"))
        for row in memberships
        if isinstance(row, Mapping) and _text(row.get("recipeId"))
    }
    owned_templates = [
        row
        for row in crafted_templates
        if isinstance(row, Mapping)
        and _text(row.get("itemId")) == item_id
        and (not recipe_ids or _text(row.get("recipeId")) in recipe_ids)
    ]
    return bool(owned_templates) and all(
        _text(row.get("status")) == "verified" for row in owned_templates
    )


def _raid_base_numeric_evidence(
    official_payload: Mapping[str, Any] | None,
    *,
    item_context_values: Sequence[str],
    scaling_evidence: Sequence[Mapping[str, Any]],
    bonus_list_level_delta_evidence: Sequence[Mapping[str, Any]],
    bonus_type_ids: Sequence[int],
) -> dict[str, Any] | None:
    """Return the narrow official level fact for a plain raid base branch.

    The item endpoint's top-level ``level`` is a static identity fact.  It is
    only a valid variant level here when the branch has no source context, no
    known scaling bonus, and no non-zero/ambiguous level-delta row.  Contextual
    raid branches remain unresolved because their level is selected by the
    contextual bonus graph rather than by the static item identity.
    """

    if not isinstance(official_payload, Mapping):
        return None
    if any(_text(value) for value in item_context_values):
        return None
    if scaling_evidence:
        return None
    if any(int(value or 0) in {49, 50, 51} for value in bonus_type_ids):
        return None

    for row in bonus_list_level_delta_evidence:
        status = _text(row.get("status"))
        if status == "not_found":
            continue
        if status != "verified":
            return None
        try:
            delta = int(row.get("itemLevelDelta"))
        except (TypeError, ValueError):
            return None
        if delta != 0:
            return None

    raw_level = official_payload.get("level")
    if isinstance(raw_level, Mapping):
        raw_level = raw_level.get("value")
    try:
        item_level = int(raw_level)
    except (TypeError, ValueError):
        return None
    if item_level <= 0:
        return None
    return {
        "status": "verified",
        "itemLevel": item_level,
        "authority": "blizzard_game_data_api.item.level",
        "constraints": {
            "itemContext": "0",
            "scalingBonusTypes": [],
            "levelDelta": 0,
        },
    }


_RAID_CONTEXTUAL_STATIC_CONTEXT_VALUES = frozenset({"153", "154"})
_RAID_CONTEXTUAL_STATIC_BONUS_TYPE_ALLOWLIST = frozenset({0, 4, 6, 26, 37})
_RAID_LEVEL_MUTATING_BONUS_TYPES = frozenset(
    {1, 11, 13, 14, 36, 42, 48, 49, 50, 51, 52, 53}
)


def _raid_contextual_static_numeric_evidence(
    official_payload: Mapping[str, Any] | None,
    *,
    static_item_level: Any,
    item_context_values: Sequence[str],
    item_creation_context_group_ids: Sequence[str],
    bonus_type_ids: Sequence[int],
    scaling_evidence: Sequence[Mapping[str, Any]],
    bonus_list_level_delta_evidence: Sequence[Mapping[str, Any]],
    db2_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    db2_refs: Mapping[tuple[str, str], list[str]] | None = None,
) -> dict[str, Any] | None:
    """Close the bounded S2 raid context-153/154 static-level branches.

    These branches are not upgrade tracks.  The exact current-build DB2
    capture has one ``ItemCreationContext`` row for each of contexts 153 and
    154, and the branch bonus lists contain only the bounded non-level bonus
    types observed in this S2 raid graph.  This helper intentionally does not
    generalize the rule to other contexts or bonus types: an unseen context,
    duplicate context row, level-mutating bonus type, scaling row, or ambiguous
    level delta remains unresolved.
    """

    if not isinstance(official_payload, Mapping):
        return None

    contexts = sorted(
        {_text(value) for value in item_context_values if _text(value)},
        key=lambda value: int(value) if value.isdigit() else value,
    )
    if len(contexts) != 1 or contexts[0] not in _RAID_CONTEXTUAL_STATIC_CONTEXT_VALUES:
        return None

    context_rows = [
        dict(row)
        for row in db2_rows.get("ItemCreationContext", [])
        if isinstance(row, Mapping) and _text(row.get("ItemContext")) == contexts[0]
    ]
    if len(context_rows) != 1:
        return None
    context_row = context_rows[0]
    context_group_id = _text(context_row.get("ItemCreationContextGroupID"))
    if not context_group_id or context_group_id == "0":
        return None
    requested_group_ids = {
        _text(value)
        for value in item_creation_context_group_ids
        if _text(value)
    }
    if requested_group_ids and requested_group_ids != {context_group_id}:
        return None

    try:
        static_level = int(static_item_level)
    except (TypeError, ValueError):
        return None
    raw_level = official_payload.get("level")
    if isinstance(raw_level, Mapping):
        raw_level = raw_level.get("value")
    preview_item = official_payload.get("preview_item")
    preview_level = (
        preview_item.get("level")
        if isinstance(preview_item, Mapping)
        else None
    )
    if isinstance(preview_level, Mapping):
        preview_level = preview_level.get("value")
    try:
        official_level = int(raw_level)
        preview_level = int(preview_level)
    except (TypeError, ValueError):
        return None
    if static_level <= 0 or official_level <= 0 or preview_level <= 0:
        return None
    if len({static_level, official_level, preview_level}) != 1:
        return None

    normalized_bonus_types = sorted({int(value) for value in bonus_type_ids})
    if not normalized_bonus_types:
        return None
    if set(normalized_bonus_types) & _RAID_LEVEL_MUTATING_BONUS_TYPES:
        return None
    if not set(normalized_bonus_types) <= _RAID_CONTEXTUAL_STATIC_BONUS_TYPE_ALLOWLIST:
        return None

    for row in scaling_evidence:
        if _text(row.get("status")) != "not_required":
            return None
    for row in bonus_list_level_delta_evidence:
        status = _text(row.get("status"))
        if status == "not_found":
            continue
        if status != "verified":
            return None
        try:
            if int(row.get("itemLevelDelta")) != 0:
                return None
        except (TypeError, ValueError):
            return None

    refs: set[str] = set()
    for row in context_rows:
        refs.update(
            _row_ref(
                row,
                table="ItemCreationContext",
                refs=db2_refs or {},
            )
        )
    return {
        "status": "verified",
        "itemLevel": static_level,
        "authority": (
            "blizzard_game_data_api.item.level_plus_preview_item.level."
            "official_client_db2.ItemCreationContext_ItemBonus_ItemBonusListLevelDelta"
        ),
        "resolution": "raid_context_static_item_level_no_level_mutating_bonus_or_delta",
        "itemContextValues": contexts,
        "itemCreationContextGroupIds": [context_group_id],
        "bonusTypeIds": normalized_bonus_types,
        "bonusTypeAllowlist": sorted(_RAID_CONTEXTUAL_STATIC_BONUS_TYPE_ALLOWLIST),
        "constraints": {
            "staticItemLevel": static_level,
            "officialItemLevel": official_level,
            "officialPreviewItemLevel": preview_level,
            "scalingEvidence": "empty_or_not_required",
            "levelDelta": 0,
            "contextRowCount": 1,
        },
        "itemCreationContextRows": context_rows,
        "evidenceRefs": sorted(refs),
    }


def build_s2_equipment_library_closure(
    *,
    inventory: Mapping[str, Any] | str | Path,
    crafted_targets: Mapping[str, Any] | str | Path,
    official_api_captures: Sequence[str | Path],
    enhancement_api_captures: Sequence[str | Path] | None = None,
    db2_captures: Mapping[str, str | Path] | None = None,
    crafted_compatibility: Mapping[str, Any] | str | Path | None = None,
    detailed_variants: bool = True,
    simc_runtime_identity: str = "",
    simc_matrix: Mapping[str, Any] | str | Path | None = None,
) -> dict[str, Any]:
    """Merge frozen official/API/DB2 evidence into a fail-closed closure report."""

    inventory_payload = _load_json(inventory, "official capture inventory")
    normalized_simc_runtime_identity = _text(simc_runtime_identity)
    simc_matrix_payload = (
        _load_json(simc_matrix, "SimC matrix report")
        if simc_matrix is not None
        else None
    )
    simc_matrix_source = (
        Path(simc_matrix).expanduser().resolve().name
        if simc_matrix is not None and not isinstance(simc_matrix, Mapping)
        else "inline"
        if simc_matrix is not None
        else None
    )
    scope_contract = _validate_scope(inventory_payload)
    crafted_target_payload = _load_json(crafted_targets, "crafted output targets")
    if crafted_target_payload.get("status") not in {"verified", "partial"}:
        raise S2EquipmentLibraryClosureError("crafted output targets are not usable")
    crafted_compatibility_payload = None
    crafted_compatibility_recipes: dict[str, dict[str, Any]] = {}
    if crafted_compatibility is not None:
        crafted_compatibility_payload = _load_json(
            crafted_compatibility,
            "crafted compatibility evidence",
        )
        if crafted_compatibility_payload.get("status") not in {"verified", "partial"}:
            raise S2EquipmentLibraryClosureError(
                "crafted compatibility evidence is not usable"
            )
        raw_compatibility_recipes = crafted_compatibility_payload.get("recipes")
        if not isinstance(raw_compatibility_recipes, list):
            raise S2EquipmentLibraryClosureError(
                "crafted compatibility evidence recipes are required"
            )
        for raw_recipe in raw_compatibility_recipes:
            recipe = _mapping(raw_recipe, "crafted compatibility recipe")
            recipe_id = _id(recipe.get("recipeId"), "crafted compatibility recipeId")
            if recipe_id in crafted_compatibility_recipes:
                raise S2EquipmentLibraryClosureError(
                    f"crafted compatibility recipe conflict: {recipe_id}"
                )
            crafted_compatibility_recipes[recipe_id] = recipe

    official_items: dict[str, dict[str, Any]] = {}
    official_refs: dict[str, set[str]] = defaultdict(set)
    official_manifests: dict[str, Any] = {}
    official_item_sets: dict[str, dict[str, Any]] = {}
    official_item_set_refs: dict[str, set[str]] = defaultdict(set)
    official_item_set_manifests: dict[str, Any] = {}
    for capture_root in official_api_captures:
        items, refs, manifest = _load_official_item_capture(Path(capture_root))
        item_sets, item_set_refs, _item_set_manifest = _load_official_item_set_capture(
            Path(capture_root)
        )
        root_name = Path(capture_root).expanduser().resolve().name
        official_manifests[root_name] = {
            "schemaRevision": manifest.get("schemaRevision"),
            "captureRoot": root_name,
            "clientBuild": manifest.get("sourceDb2Build") or manifest.get("clientBuild"),
        }
        official_item_set_manifests[root_name] = {
            "schemaRevision": manifest.get("schemaRevision"),
            "captureRoot": root_name,
            "clientBuild": manifest.get("sourceDb2Build") or manifest.get("clientBuild"),
        }
        for item_id, payload in items.items():
            previous = official_items.get(item_id)
            if previous is not None and _canonical(previous) != _canonical(payload):
                raise S2EquipmentLibraryClosureError(f"official item payload conflict: {item_id}")
            official_items[item_id] = payload
            official_refs[item_id].update(refs.get(item_id, []))
        for set_id, payload in item_sets.items():
            previous = official_item_sets.get(set_id)
            if previous is not None and _canonical(previous) != _canonical(payload):
                raise S2EquipmentLibraryClosureError(
                    f"official item-set payload conflict: {set_id}"
                )
            official_item_sets[set_id] = payload
            official_item_set_refs[set_id].update(item_set_refs.get(set_id, []))

    enhancement_items: dict[str, dict[str, Any]] = {}
    enhancement_refs: dict[str, set[str]] = defaultdict(set)
    enhancement_manifests: dict[str, Any] = {}
    for capture_root in enhancement_api_captures or ():
        items, refs, manifest = _load_official_item_capture(Path(capture_root))
        root_name = Path(capture_root).expanduser().resolve().name
        enhancement_manifests[root_name] = {
            "schemaRevision": manifest.get("schemaRevision"),
            "captureRoot": root_name,
            "clientBuild": manifest.get("sourceDb2Build") or manifest.get("clientBuild"),
            "capturePurpose": manifest.get("capturePurpose"),
            "status": manifest.get("status"),
        }
        for item_id, payload in items.items():
            previous = enhancement_items.get(item_id)
            if previous is not None and _canonical(previous) != _canonical(payload):
                raise S2EquipmentLibraryClosureError(
                    f"official enhancement item payload conflict: {item_id}"
                )
            enhancement_items[item_id] = payload
            enhancement_refs[item_id].update(refs.get(item_id, []))

    db2_rows, db2_refs, db2_manifests = _merge_db2_captures(db2_captures)
    mythic_plus_cap_track_evidence = _mythic_plus_cap_track_evidence(
        db2_rows,
        db2_refs,
    )
    s2_track_group_ids = {
        _text(row.get("groupId"))
        for row in mythic_plus_cap_track_evidence.get("trackFacts") or []
        if _text(row.get("groupId"))
    }
    mythic_plus_item_scope_by_item: dict[str, dict[str, Any]] = {}
    db2_client_builds = sorted(
        {
            _text(manifest.get("clientBuild"))
            for manifest in db2_manifests.values()
            if _text(manifest.get("clientBuild"))
        }
    )
    runtime_build = _simc_runtime_build(normalized_simc_runtime_identity)
    db2_runtime_build_mismatch = bool(
        runtime_build
        and db2_client_builds
        and (
            len(db2_client_builds) != 1
            or db2_client_builds[0] != runtime_build
        )
    )
    sparse_by_item = _index(db2_rows, "ItemSparse", "ID")
    item_by_id = _index(db2_rows, "Item", "ID")
    bonus_tree_item_ids = {
        _text(row.get("ItemID"))
        for row in db2_rows.get("ItemXBonusTree", [])
        if _text(row.get("ItemID"))
    }

    def equipment_scope_for_item(
        item_id: str,
        payload: Mapping[str, Any] | None,
    ) -> tuple[str, str | None]:
        static_rows_for_item = sparse_by_item.get(item_id, [])
        static_row_for_item = (
            static_rows_for_item[0]
            if len(static_rows_for_item) == 1
            else None
        )
        return _equipment_scope(
            payload,
            static_row=static_row_for_item,
            has_bonus_tree=item_id in bonus_tree_item_ids,
        )

    inventory_tier_facts = {
        _id(row.get("setId"), "tierSetFacts.setId"): row
        for row in inventory_payload.get("tierSetFacts") or []
        if isinstance(row, Mapping) and row.get("setId")
    }
    tier_set_ids = sorted(
        {
            *inventory_tier_facts,
            *{
                _id(row.get("setId"), "tier_set membership setId")
                for row in inventory_payload.get("tierSetMemberships") or []
                if isinstance(row, Mapping) and row.get("setId")
            },
        },
        key=int,
    )
    tier_set_facts: list[dict[str, Any]] = []
    official_set_facts: dict[str, dict[str, Any]] = {}
    for set_id in tier_set_ids:
        official_fact = _official_item_set_facts(
            set_id,
            official_item_sets.get(set_id),
            refs=sorted(official_item_set_refs.get(set_id, set())),
        )
        inventory_fact = inventory_tier_facts.get(set_id, {})
        merged_fact = {
            **inventory_fact,
            **official_fact,
            "setId": set_id,
            "evidenceRefs": sorted(
                set(inventory_fact.get("evidenceRefs") or [])
                | set(official_fact.get("evidenceRefs") or [])
            ),
        }
        official_set_facts[set_id] = merged_fact
        tier_set_facts.append(merged_fact)

    source_memberships: list[dict[str, Any]] = []
    tier_memberships: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    candidate_ids: set[str] = set()
    tier_rows_by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
    # The inventory was produced before the bounded DB2 output graph existed.
    # Re-evaluate its legacy recipe-output blocker below instead of carrying a
    # stale API-only blocker into the merged closure report.
    blocker_codes: set[str] = set(inventory_payload.get("blockerCodes") or []) - {
        "OFFICIAL_API_RECIPE_OUTPUT_MISSING"
    }
    if db2_runtime_build_mismatch:
        blocker_codes.add("SIMC_RUNTIME_DB2_BUILD_MISMATCH")
    if any(fact.get("status") != "verified" for fact in tier_set_facts):
        blocker_codes.add("TIER_SET_EFFECT_FACT_UNVERIFIED")
    if crafted_compatibility_payload is not None:
        blocker_codes.update(crafted_compatibility_payload.get("blockerCodes") or [])
        if crafted_compatibility_payload.get("status") != "verified":
            blocker_codes.add("CRAFTED_COMPATIBILITY_EVIDENCE_PARTIAL")

    for raw_row in inventory_payload.get("sourceMemberships") or []:
        row = _mapping(raw_row, "source membership")
        logical_source = _text(row.get("logicalSource"))
        if logical_source not in _LOGICAL_SOURCES or logical_source == "tier_set":
            raise S2EquipmentLibraryClosureError("source membership leaves fixed logical source scope")
        item_id = _id(row.get("itemId"), "source membership itemId")
        payload = official_items.get(item_id)
        slot, scope_exclusion_reason = equipment_scope_for_item(item_id, payload)
        journal_item_scope = None
        mythic_plus_item_scope = None
        if logical_source == "mythic_plus":
            journal_item_scope = classify_mythic_plus_journal_item_scope(
                {**row, "itemId": item_id},
                db2_rows=db2_rows,
                db2_refs=db2_refs,
            )
            journal_status = _text(journal_item_scope.get("status"))
            if journal_status == "excluded":
                slot = None
                scope_exclusion_reason = journal_item_scope.get("reasonCode")
            elif journal_status != "verified":
                blocker_codes.add("MYTHIC_PLUS_JOURNAL_ITEM_SCOPE_UNVERIFIED")
            elif slot:
                if item_id not in mythic_plus_item_scope_by_item:
                    mythic_plus_item_scope_by_item[item_id] = (
                        classify_mythic_plus_item_scope(
                            item_id,
                            db2_rows=db2_rows,
                            db2_refs=db2_refs,
                            s2_track_group_ids=sorted(s2_track_group_ids, key=int),
                            current_item_context_values=sorted(
                                _MYTHIC_PLUS_VARIANT_CONTEXT_VALUES,
                                key=int,
                            ),
                        )
                    )
                mythic_plus_item_scope = mythic_plus_item_scope_by_item[item_id]
                mplus_scope_status = _text(mythic_plus_item_scope.get("status"))
                if mplus_scope_status == "excluded":
                    slot = None
                    scope_exclusion_reason = mythic_plus_item_scope.get("reasonCode")
                elif mplus_scope_status != "verified":
                    blocker_codes.add("MYTHIC_PLUS_ITEM_S2_SCOPE_UNVERIFIED")
        row = {
            **row,
            "itemId": item_id,
            "scopeStatus": "included" if slot else "excluded",
            "exclusionReason": None if slot else scope_exclusion_reason,
            "itemSlot": slot,
            "itemIdentityStatus": "verified" if payload else "UNVERIFIED",
            "evidenceRefs": sorted(
                set(row.get("officialEvidenceRefs") or [])
                | official_refs.get(item_id, set())
                | set(
                    journal_item_scope.get("evidenceRefs") or []
                    if journal_item_scope is not None
                    else []
                )
                | set(
                    mythic_plus_item_scope.get("evidenceRefs") or []
                    if mythic_plus_item_scope is not None
                    else []
                )
            ),
        }
        if journal_item_scope is not None:
            row["journalItemScope"] = journal_item_scope
        if mythic_plus_item_scope is not None:
            row["mythicPlusItemScope"] = mythic_plus_item_scope
        source_memberships.append(row)
        if slot:
            candidate_ids.add(item_id)
        else:
            exclusions.append(
                {
                    "logicalSource": logical_source,
                    "itemId": item_id,
                    "reasonCode": scope_exclusion_reason,
                    "evidenceRefs": row["evidenceRefs"],
                }
            )

    for raw_row in inventory_payload.get("tierSetMemberships") or []:
        row = _mapping(raw_row, "tier_set membership")
        if _text(row.get("logicalSource")) != "tier_set":
            raise S2EquipmentLibraryClosureError("tier membership must use tier_set logical source")
        item_id = _id(row.get("itemId"), "tier membership itemId")
        payload = official_items.get(item_id)
        slot, scope_exclusion_reason = equipment_scope_for_item(item_id, payload)
        row = {
            **row,
            "itemId": item_id,
            "scopeStatus": "included" if slot else "excluded",
            "exclusionReason": None if slot else scope_exclusion_reason,
            "itemSlot": slot,
            "itemIdentityStatus": "verified" if payload else "UNVERIFIED",
            "evidenceRefs": sorted(
                set(row.get("officialEvidenceRefs") or []) | official_refs.get(item_id, set())
            ),
        }
        tier_memberships.append(row)
        tier_rows_by_item[item_id].append(row)
        if slot:
            candidate_ids.add(item_id)
        else:
            exclusions.append(
                {
                    "logicalSource": "tier_set",
                    "itemId": item_id,
                    "reasonCode": scope_exclusion_reason,
                    "evidenceRefs": row["evidenceRefs"],
                }
            )

    recipe_rows = {
        _id(row.get("recipeId"), "crafted recipeId"): row
        for row in inventory_payload.get("craftedRecipes") or []
        if isinstance(row, Mapping) and row.get("recipeId")
    }
    crafted_edges: list[dict[str, Any]] = []
    crafted_variant_templates: list[dict[str, Any]] = []
    crafted_item_ids: set[str] = set()
    for raw_edge in crafted_target_payload.get("recipeOutputEdges") or []:
        edge = _mapping(raw_edge, "crafted recipe output edge")
        recipe_id = _id(edge.get("recipeId"), "crafted recipeId")
        item_id = _id(edge.get("itemId"), "crafted output itemId")
        payload = official_items.get(item_id)
        slot, scope_exclusion_reason = equipment_scope_for_item(item_id, payload)
        quality = _crafted_quality_facts(
            recipe_id,
            item_id,
            crafted_recipe_rows=recipe_rows,
            db2_rows=db2_rows,
            db2_refs=db2_refs,
        )
        compatibility = crafted_compatibility_recipes.get(recipe_id)
        if compatibility is None:
            if crafted_compatibility_payload is not None:
                blocker_codes.add("CRAFTED_COMPATIBILITY_RECIPE_MISSING")
            secondary_compatibility = {
                "status": "UNVERIFIED",
                "options": [],
                "reasonCode": "CRAFTED_SECONDARY_OPTION_SEMANTICS_UNVERIFIED",
            }
            embellishment_compatibility = {
                "status": "UNVERIFIED",
                "options": [],
                "reasonCode": "CRAFTED_EMBELLISHMENT_SEMANTICS_UNVERIFIED",
            }
            enhancement_compatibility = {
                "status": "UNVERIFIED",
                "options": [],
                "reasonCode": "CRAFTED_ENHANCEMENT_SEMANTICS_UNVERIFIED",
            }
            compatibility_status = "UNVERIFIED"
            compatibility_refs: set[str] = set()
        else:
            secondary_compatibility = _mapping(
                compatibility.get("secondaryStatCompatibility"),
                "crafted compatibility secondaryStatCompatibility",
            )
            embellishment_compatibility = _mapping(
                compatibility.get("embellishmentCompatibility"),
                "crafted compatibility embellishmentCompatibility",
            )
            enhancement_compatibility = _mapping(
                compatibility.get("enhancementCompatibility"),
                "crafted compatibility enhancementCompatibility",
            )
            compatibility_status = _text(compatibility.get("evidenceStatus")) or "UNVERIFIED"
            compatibility_refs = set(compatibility.get("evidenceRefs") or [])
            for compatibility_field in (
                secondary_compatibility,
                embellishment_compatibility,
                enhancement_compatibility,
            ):
                compatibility_refs.update(compatibility_field.get("evidenceRefs") or [])
            if compatibility_status != "verified":
                blocker_codes.add("CRAFTED_COMPATIBILITY_RECIPE_UNVERIFIED")
            if any(
                _text(compatibility_field.get("status")) in {"UNVERIFIED", "blocked"}
                for compatibility_field in (
                    secondary_compatibility,
                    embellishment_compatibility,
                    enhancement_compatibility,
                )
            ):
                blocker_codes.add("CRAFTED_COMPATIBILITY_RECIPE_UNVERIFIED")
        row = {
            **edge,
            "recipeId": recipe_id,
            "itemId": item_id,
            "logicalSource": "crafted",
            "rawSourceType": "crafted",
            "rawSourceKey": f"crafted:recipe:{recipe_id}",
            "scopeStatus": "included" if slot else "excluded",
            "exclusionReason": None if slot else scope_exclusion_reason,
            "itemSlot": slot,
            "outputStatus": "verified" if payload and edge.get("status") == "verified" else "UNVERIFIED",
            "qualityVariants": quality,
            "secondaryStatCompatibility": secondary_compatibility,
            "embellishmentCompatibility": embellishment_compatibility,
            "enhancementCompatibility": enhancement_compatibility,
            "craftedCompatibilityEvidenceStatus": compatibility_status,
            "itemIdentityStatus": "verified" if payload else "UNVERIFIED",
            "evidenceRefs": sorted(
                set(edge.get("evidenceRefs") or [])
                | official_refs.get(item_id, set())
                | set(quality.get("evidenceRefs") or [])
                | compatibility_refs
            ),
        }
        crafted_edges.append(row)
        if slot:
            candidate_ids.add(item_id)
            crafted_item_ids.add(item_id)
            templates = _build_crafted_variant_templates(row)
            crafted_variant_templates.extend(templates)
            if any(template.get("status") != "verified" for template in templates):
                blocker_codes.add("CRAFTED_QUALITY_CANONICAL_INPUT_UNVERIFIED")
        else:
            exclusions.append(
                {
                    "logicalSource": "crafted",
                    "recipeId": recipe_id,
                    "itemId": item_id,
                    "reasonCode": scope_exclusion_reason,
                    "evidenceRefs": row["evidenceRefs"],
                }
            )

    missing_recipe_ids = sorted(
        {
            _id(value, "recipeWithoutOutput")
            for value in crafted_target_payload.get("recipesWithoutOutput") or []
        },
        key=int,
    )
    missing_recipe_records = {
        _id(row.get("recipeId"), "recipeWithoutOutputRecord.recipeId"): row
        for row in crafted_target_payload.get("recipeWithoutOutputRecords") or []
        if isinstance(row, Mapping) and row.get("recipeId")
    }
    unresolved_recipe_ids = [
        recipe_id
        for recipe_id in missing_recipe_ids
        if missing_recipe_records.get(recipe_id, {}).get("classificationStatus")
        != "verified"
    ]
    if unresolved_recipe_ids:
        blocker_codes.add("OFFICIAL_DB2_RECIPE_OUTPUT_EDGE_UNRESOLVED")

    # The same item identity is deliberately represented once, while all
    # source/tier/crafted memberships remain separate rows above.
    item_definitions: list[dict[str, Any]] = []
    variants: list[dict[str, Any]] = []
    set_conversions: list[dict[str, Any]] = []
    tier_conversion_by_item: dict[str, dict[str, Any]] = {}
    legacy_projection_item_ids: set[str] = set()
    for item_id in sorted(candidate_ids, key=int):
        payload = official_items.get(item_id)
        slot, _scope_exclusion_reason = equipment_scope_for_item(item_id, payload)
        static_rows = sparse_by_item.get(item_id, [])
        static_row = static_rows[0] if len(static_rows) == 1 else None
        item_class_rows = item_by_id.get(item_id, [])
        item_class_row = item_class_rows[0] if len(item_class_rows) == 1 else None
        scaling_evidence, scaling_refs, root_tree = _item_scaling_evidence(
            item_id,
            db2_rows=db2_rows,
            db2_refs=db2_refs,
        )
        identity_refs = set(official_refs.get(item_id, set()))
        identity_refs.update(_row_ref(static_row, table="ItemSparse", refs=db2_refs))
        identity_refs.update(_row_ref(item_class_row, table="Item", refs=db2_refs))
        identity_status = "verified" if payload and slot else "UNVERIFIED"
        static_status = "verified" if static_row is not None else "UNVERIFIED"
        if static_status != "verified":
            blocker_codes.add("OFFICIAL_ITEM_STATIC_DB2_MISSING")
        if item_class_row is None:
            blocker_codes.add("OFFICIAL_ITEM_CLASS_FACT_UNVERIFIED")
        numeric_variant_status = "verified" if scaling_evidence and all(
            entry.get("status") == "verified" for entry in scaling_evidence
        ) else "UNVERIFIED"
        item_memberships = [
            row
            for row in [*source_memberships, *tier_memberships, *crafted_edges]
            if row.get("itemId") == item_id and row.get("scopeStatus") == "included"
        ]
        composition_context_values: set[str] = set()
        for membership in item_memberships:
            logical_source = _text(membership.get("logicalSource"))
            if logical_source == "mythic_plus":
                composition_context_values.update(
                    _MYTHIC_PLUS_VARIANT_CONTEXT_VALUES
                )
            elif logical_source == "raid":
                composition_context_values.update(_RAID_VARIANT_CONTEXT_VALUES)
            else:
                composition_context_values.add("0")
        mythic_plus_item_scope = mythic_plus_item_scope_by_item.get(item_id)
        # ItemScalingConfig closes only a numeric fact.  It does not identify
        # the public track/rank, source eligibility, terminal-state semantics,
        # or the exact bonus list emitted for every legal variant.  Keep every
        # raw tree branch as evidence instead of collapsing it into one
        # synthetic "highest track" variant.
        graph_variants = _build_item_variant_records(
            item_id,
            db2_rows=db2_rows,
            db2_refs=db2_refs,
            official_payload=payload,
            composition_context_values=sorted(composition_context_values, key=int),
            static_item_level=static_row.get("ItemLevel") if static_row else None,
            allow_empty_base_variant=(
                _text((mythic_plus_item_scope or {}).get("status")) == "verified"
                and _text((mythic_plus_item_scope or {}).get("graphStatus")) == "empty"
            ),
            allow_raid_base_numeric_evidence=(
                any(
                    row.get("logicalSource") == "raid"
                    and row.get("scopeStatus") == "included"
                    for row in item_memberships
                )
                and not any(
                    row.get("logicalSource") == "mythic_plus"
                    and row.get("scopeStatus") == "included"
                    for row in item_memberships
                )
            ),
            allow_default_context_group_resolution=any(
                row.get("logicalSource") == "tier_set"
                and row.get("scopeStatus") == "included"
                for row in item_memberships
            ),
            allow_default_context_numeric_evidence=any(
                row.get("logicalSource") == "tier_set"
                and row.get("scopeStatus") == "included"
                for row in item_memberships
            ),
        )
        has_context_slot_vector = any(
            _text((row.get("variantComposition") or {}).get("kind"))
            == "db2_context_slot_vector"
            and any(
                _text(value) in _MYTHIC_PLUS_VARIANT_CONTEXT_VALUES
                for value in row.get("itemContextValues") or []
            )
            and _text(row.get("rawGraphStatus")) == "verified"
            for row in graph_variants
            if isinstance(row.get("variantComposition"), Mapping)
        )
        has_direct_s2_track_group = any(
            _text(row.get("bonusListGroupId")) in s2_track_group_ids
            for row in graph_variants
        )
        needs_legacy_track_projection = (
            any(
                row.get("logicalSource") == "mythic_plus"
                and row.get("scopeStatus") == "included"
                for row in item_memberships
            )
            and not has_direct_s2_track_group
            and _text((mythic_plus_item_scope or {}).get("graphStatus")) != "empty"
            and mythic_plus_cap_track_evidence.get("legacyProjectionStatus")
            == "UNVERIFIED"
        )
        if needs_legacy_track_projection:
            legacy_projection_item_ids.add(item_id)
        quality_status = "verified" if item_id in crafted_item_ids and any(
            edge["itemId"] == item_id and edge["qualityVariants"]["status"] == "verified"
            for edge in crafted_edges
        ) else "UNVERIFIED"
        for graph_variant in graph_variants:
            graph_variant["itemSlot"] = slot
            graph_variant["qualityStatus"] = quality_status
            requires_track_authority = _requires_track_authority(
                item_memberships,
                graph_variant,
            )
            track_authority = classify_variant_upgrade(
                graph_variant,
                db2_rows=db2_rows,
                db2_refs=db2_refs,
            )
            if (
                not requires_track_authority
                and track_authority.get("status") == "UNVERIFIED"
            ):
                track_authority = {
                    **track_authority,
                    "status": "not_required",
                    "reasonCode": None,
                    "trackStatus": "not_required",
                    "sourceEligibilityStatus": "not_required",
                }
            source_eligibility = _variant_source_eligibility(
                graph_variant,
                memberships=item_memberships,
                db2_rows=db2_rows,
                db2_refs=db2_refs,
            )
            empty_base_variant = (
                _text((graph_variant.get("variantComposition") or {}).get("kind"))
                == "empty_base_identity"
            )
            if (
                empty_base_variant
                and _text((mythic_plus_item_scope or {}).get("status")) == "verified"
                and _text((mythic_plus_item_scope or {}).get("graphStatus")) == "empty"
            ):
                source_by_source = {
                    source: dict(source_row)
                    for source, source_row in (source_eligibility.get("bySource") or {}).items()
                    if isinstance(source_row, Mapping)
                }
                mplus_source_evidence = source_by_source.get("mythic_plus")
                if mplus_source_evidence is not None:
                    mplus_source_evidence["observedStatus"] = _text(
                        mplus_source_evidence.get("status")
                    )
                    mplus_source_evidence["status"] = "not_required"
                    mplus_source_evidence["reasonCode"] = None
                    mplus_source_evidence["exclusionReason"] = None
                source_eligibility = {
                    **source_eligibility,
                    "status": (
                        "not_required"
                        if source_by_source
                        and all(
                            _text(row.get("status")) == "not_required"
                            for row in source_by_source.values()
                        )
                        else source_eligibility.get("status")
                    ),
                    "bySource": source_by_source,
                    "reasonCodes": [
                        code
                        for code in source_eligibility.get("reasonCodes") or []
                        if code != "MYTHIC_PLUS_VARIANT_ITEM_CONTEXT_UNVERIFIED"
                    ],
                }
            uncomposed_mplus_component = _is_uncomposed_mythic_plus_component(
                graph_variant,
                memberships=item_memberships,
                mythic_plus_item_scope_status=_text(
                    (mythic_plus_item_scope or {}).get("status")
                ),
                has_context_slot_vector=has_context_slot_vector,
            )
            uncomposed_raid_component = _is_uncomposed_raid_component(
                graph_variant,
                memberships=item_memberships,
                composed_variants=graph_variants,
            )
            crafted_graph_component = _is_crafted_graph_component(
                graph_variant,
                memberships=item_memberships,
                crafted_templates=crafted_variant_templates,
            )
            component_reason = (
                "OUT_OF_SCOPE_UNCOMPOSED_MPLUS_VARIANT_COMPONENT"
                if uncomposed_mplus_component
                else "OUT_OF_SCOPE_UNCOMPOSED_RAID_VARIANT_COMPONENT"
                if uncomposed_raid_component
                else "OUT_OF_SCOPE_CRAFTED_GRAPH_COMPONENT_TEMPLATE_OWNED"
                if crafted_graph_component
                else None
            )
            if component_reason:
                source_by_source = {
                    source: dict(source_row)
                    for source, source_row in (source_eligibility.get("bySource") or {}).items()
                    if isinstance(source_row, Mapping)
                }
                component_source = (
                    "mythic_plus"
                    if uncomposed_mplus_component
                    else "raid"
                    if uncomposed_raid_component
                    else "crafted"
                )
                component_source_evidence = source_by_source.get(component_source)
                if component_source_evidence is not None:
                    component_source_evidence["observedStatus"] = _text(
                        component_source_evidence.get("status")
                    )
                    component_source_evidence["status"] = "excluded"
                    component_source_evidence["reasonCode"] = component_reason
                    component_source_evidence["exclusionReason"] = component_reason
                source_eligibility = {
                    **source_eligibility,
                    "status": "excluded",
                    "bySource": source_by_source,
                    "reasonCodes": sorted(
                        set(source_eligibility.get("reasonCodes") or [])
                        | {component_reason}
                    ),
                }
            source_status = source_eligibility.get("status")
            legacy_projection_reason = (
                "MYTHIC_PLUS_LEGACY_TRACK_PROJECTION_UNVERIFIED"
                if needs_legacy_track_projection
                and source_status in {"verified", "UNVERIFIED"}
                else None
            )
            if source_status == "excluded":
                # Track/rank facts are not required for a branch that is
                # explicitly outside the frozen four-source product scope.
                # Keep the exclusion visible without labeling it as an
                # unresolved public track.
                track_authority = {
                    **track_authority,
                    "status": "excluded",
                    "reasonCode": None,
                    "trackStatus": "excluded",
                    "sourceEligibilityStatus": "excluded",
                }
            graph_variant["trackAuthority"] = track_authority
            graph_variant["trackKey"] = track_authority.get("trackKey")
            graph_variant["rank"] = track_authority.get("rank")
            graph_variant["maxRank"] = track_authority.get("maxRank")
            graph_variant["trackItemLevel"] = track_authority.get("itemLevel")
            graph_variant["trackStatus"] = track_authority.get("trackStatus")
            graph_variant["sourceEligibilityEvidence"] = source_eligibility
            graph_variant["sourceEligibilityStatus"] = source_status
            if component_reason:
                graph_variant["uncomposedComponentEvidence"] = {
                    "status": "excluded",
                    "reasonCode": component_reason,
                    "authority": "official_client_db2.ItemBonusTreeNode_composition",
                }
            graph_variant["reasonCodes"] = sorted(
                {
                    code
                    for code in graph_variant.get("reasonCodes") or []
                    if code not in {
                        "VARIANT_TRACK_AUTHORITY_UNVERIFIED",
                        "NUMERIC_VARIANT_EVIDENCE_UNVERIFIED"
                        if component_reason
                        else "__keep_numeric_reason__",
                    }
                }
                | (
                    {track_authority["reasonCode"]}
                    if track_authority.get("status") in {"UNVERIFIED", "excluded"}
                    and track_authority.get("reasonCode")
                    else set()
                )
                | ({legacy_projection_reason} if legacy_projection_reason else set())
                | set(source_eligibility.get("reasonCodes") or [])
                | ({component_reason} if component_reason else set())
            )
            if legacy_projection_reason:
                graph_variant["legacyTrackProjectionStatus"] = "UNVERIFIED"
                graph_variant["legacyTrackProjectionReasonCode"] = (
                    mythic_plus_cap_track_evidence.get("legacyProjectionReasonCode")
                    or legacy_projection_reason
                )
            if source_eligibility.get("status") == "excluded":
                graph_variant["variantStatus"] = "excluded"
                graph_variant["status"] = "excluded"
                graph_variant["simcReadiness"] = "excluded"
            elif track_authority.get("status") == "excluded":
                graph_variant["variantStatus"] = "excluded"
                graph_variant["status"] = "excluded"
                graph_variant["simcReadiness"] = "excluded"
            elif (
                (
                    (not requires_track_authority)
                    or track_authority.get("status") == "verified"
                )
                and not graph_variant.get("reasonCodes")
                and graph_variant.get("rawGraphStatus") == "verified"
                and graph_variant.get("numericVariantEvidenceStatus") == "verified"
                and source_eligibility.get("status") in {
                    "verified",
                    "not_applicable",
                    "not_required",
                }
            ):
                graph_variant["variantStatus"] = "verified"
                graph_variant["status"] = "verified"
            graph_variant["canonicalSimcInput"] = _canonical_simc_variant_input(
                graph_variant,
                item_id=item_id,
                item_slot=slot,
                static_status=static_status,
            )
            graph_variant["evidenceRefs"] = sorted(
                set(graph_variant.get("evidenceRefs") or [])
                | identity_refs
                | set(track_authority.get("evidenceRefs") or [])
                | set(source_eligibility.get("evidenceRefs") or [])
            )
        variants.extend(
            graph_variants
            if detailed_variants
            else [_compact_variant_record(row) for row in graph_variants]
        )
        variant_status = (
            "verified"
            if graph_variants
            and (
                (
                    any(row.get("variantStatus") == "verified" for row in graph_variants)
                    and all(
                        row.get("variantStatus") in {"verified", "excluded"}
                        for row in graph_variants
                    )
                )
                or (
                    any(
                        _text(row.get("logicalSource")) == "crafted"
                        and _text(row.get("scopeStatus")) == "included"
                        for row in item_memberships
                    )
                    and any(
                        _text(template.get("itemId")) == item_id
                        and _text(template.get("status")) == "verified"
                        for template in crafted_variant_templates
                    )
                    and all(
                        row.get("variantStatus") in {"verified", "excluded"}
                        for row in graph_variants
                    )
                )
            )
            else "UNVERIFIED"
        )
        if any(
            row.get("sourceEligibilityStatus") in {"verified", "UNVERIFIED"}
            and row.get("trackAuthority", {}).get("status") == "UNVERIFIED"
            for row in graph_variants
        ):
            blocker_codes.add("VARIANT_TRACK_AUTHORITY_UNVERIFIED")
        if any(
            row.get("sourceEligibilityEvidence", {}).get("status") == "UNVERIFIED"
            for row in graph_variants
        ):
            blocker_codes.add("SOURCE_VARIANT_ELIGIBILITY_UNVERIFIED")

        tier_conversion = _conversion_fact(
            item_id,
            tier_rows_by_item.get(item_id, []),
            db2_rows=db2_rows,
            db2_refs=db2_refs,
            static_row=static_row,
            official_payload=payload,
            official_set_facts=official_set_facts,
        )
        if tier_rows_by_item.get(item_id):
            tier_conversion_by_item[item_id] = tier_conversion
            set_conversions.append(tier_conversion)
            if tier_conversion["preservation"]["status"] != "verified":
                blocker_codes.add("TIER_CONVERSION_PRESERVATION_UNVERIFIED")

        source_count = sum(1 for row in source_memberships if row["itemId"] == item_id and row["scopeStatus"] == "included")
        tier_count = sum(1 for row in tier_memberships if row["itemId"] == item_id and row["scopeStatus"] == "included")
        crafted_count = sum(1 for edge in crafted_edges if edge["itemId"] == item_id and edge["scopeStatus"] == "included")
        item_status = "verified" if identity_status == "verified" and variant_status == "verified" else "UNVERIFIED"
        item_definitions.append(
            {
                "itemId": item_id,
                "itemName": _text((payload or {}).get("name")),
                "itemSlot": slot,
                "logicalSources": sorted(
                    {
                        *[row["logicalSource"] for row in source_memberships if row["itemId"] == item_id and row["scopeStatus"] == "included"],
                        *( ["tier_set"] if tier_count else [] ),
                        *( ["crafted"] if crafted_count else [] ),
                    }
                ),
                "sourceMembershipCount": source_count,
                "tierSetMembershipCount": tier_count,
                "craftedRelationshipCount": crafted_count,
                "variantCount": len(graph_variants),
                "variantGraphStatus": (
                    "verified"
                    if graph_variants and all(
                        row.get("rawGraphStatus") == "verified"
                        for row in graph_variants
                    )
                    else "UNVERIFIED"
                ),
                "itemIdentity": _official_item_facts(payload),
                "db2StaticFacts": _item_static_facts(static_row),
                "db2StaticStatus": static_status,
                "db2ItemFacts": _item_class_facts(item_class_row),
                "db2ItemFactsStatus": "verified" if item_class_row is not None else "UNVERIFIED",
                "variantStatus": variant_status,
                "mythicPlusItemScope": mythic_plus_item_scope,
                "conversionStatus": tier_conversion.get("status") if tier_conversion else "not_applicable",
                "evidenceStatus": item_status,
                "simcReadiness": "blocked",
                "evidenceRefs": sorted(identity_refs | set(scaling_refs)),
            }
        )

    spell_refs_by_id: dict[str, list[str]] = {
        _text(row.get("ID")): _row_ref(row, table="Spell", refs=db2_refs)
        for row in db2_rows.get("Spell", [])
        if _text(row.get("ID"))
    }
    spell_effect_refs_by_id: dict[str, set[str]] = defaultdict(set)
    for row in db2_rows.get("SpellEffect", []):
        spell_id = _text(row.get("SpellID"))
        if spell_id:
            spell_effect_refs_by_id[spell_id].update(
                _row_ref(row, table="SpellEffect", refs=db2_refs)
            )

    enhancement_authority = build_s2_enhancement_authority(
        crafted_relationships=crafted_edges,
        variants=variants,
        crafted_variant_templates=crafted_variant_templates,
        item_definitions=item_definitions,
        official_option_items=enhancement_items,
        official_option_refs={
            item_id: sorted(refs)
            for item_id, refs in enhancement_refs.items()
        },
        enchant_rows=db2_rows.get("SpellItemEnchantment", []),
        enchant_refs={
            _text(row.get("ID")): db2_refs.get(
                (
                    "SpellItemEnchantment",
                    json.dumps(
                        dict(row),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                ),
                [],
            )
            for row in db2_rows.get("SpellItemEnchantment", [])
            if _text(row.get("ID"))
        },
        spell_rows=db2_rows.get("Spell", []),
        spell_effect_rows=db2_rows.get("SpellEffect", []),
        spell_refs=spell_refs_by_id,
        spell_effect_refs={
            spell_id: sorted(refs)
            for spell_id, refs in spell_effect_refs_by_id.items()
        },
    )
    blocker_codes.update(enhancement_authority.get("blockerCodes") or [])

    if legacy_projection_item_ids:
        blocker_codes.add("MYTHIC_PLUS_LEGACY_TRACK_PROJECTION_UNVERIFIED")
    mythic_plus_cap_track_evidence["legacyProjectionItemIds"] = sorted(
        legacy_projection_item_ids,
        key=int,
    )

    # Every recipe root without an equipment item output is retained as an
    # explicit exclusion.  Only roots whose bounded DB2 graph is still
    # ambiguous remain blockers; no missing relation is silently discarded.
    if missing_recipe_ids:
        for recipe_id in missing_recipe_ids:
            record = missing_recipe_records.get(recipe_id, {})
            evidence_refs = sorted(
                set(recipe_rows.get(recipe_id, {}).get("officialEvidenceRefs") or [])
            )
            exclusions.append(
                {
                    "logicalSource": "crafted",
                    "recipeId": recipe_id,
                    "itemId": None,
                    "reasonCode": record.get(
                        "reasonCode", "OFFICIAL_DB2_RECIPE_OUTPUT_EDGE_UNRESOLVED"
                    ),
                    "classificationStatus": record.get(
                        "classificationStatus", "UNVERIFIED"
                    ),
                    "effectCodes": list(record.get("effectCodes") or []),
                    "craftingDataIds": list(record.get("craftingDataIds") or []),
                    "evidenceTables": list(record.get("evidenceTables") or []),
                    "evidenceRefs": evidence_refs,
                }
            )
    if any(
        row["logicalSource"] == "mythic_plus"
        for row in source_memberships
        if row["scopeStatus"] == "included"
    ) and mythic_plus_cap_track_evidence.get("status") != "verified":
        blocker_codes.add("MYTHIC_PLUS_CAP_TRACK_UNVERIFIED")
    if crafted_edges and crafted_compatibility_payload is None:
        blocker_codes.add("CRAFTED_ENHANCEMENT_SEMANTICS_UNVERIFIED")
    if crafted_edges and any(
        _text(row.get("qualityVariants", {}).get("status")) != "verified"
        for row in crafted_edges
        if row.get("scopeStatus") == "included"
    ):
        blocker_codes.add("CRAFTED_QUALITY_RELATION_UNVERIFIED")
    if crafted_edges and any(
        row.get("scopeStatus") == "included"
        and not any(
            template.get("itemId") == row.get("itemId")
            and template.get("recipeId") == row.get("recipeId")
            for template in crafted_variant_templates
        )
        for row in crafted_edges
    ):
        blocker_codes.add("CRAFTED_QUALITY_VARIANT_TEMPLATE_MISSING")
    if variants:
        blocker_codes.add("SIMC_MATRIX_NOT_RUN")
        if not normalized_simc_runtime_identity:
            blocker_codes.add("SIMC_RUNTIME_IDENTITY_UNAVAILABLE")

    excluded_counts = {
        "source_non_canonical_gear_slot": sum(
            1 for row in exclusions
            if row.get("reasonCode") == "OUT_OF_SCOPE_NON_CANONICAL_GEAR_SLOT"
            and row.get("recipeId") is None
        ),
        "mythic_plus_non_mplus_journal_item": sum(
            1
            for row in exclusions
            if row.get("reasonCode")
            == "OUT_OF_SCOPE_NON_MPLUS_JOURNAL_DIFFICULTY_MASK"
        ),
        "mythic_plus_non_s2_variant_graph": sum(
            1
            for row in exclusions
            if row.get("reasonCode")
            == "OUT_OF_SCOPE_NON_S2_MPLUS_ITEM_VARIANT_GRAPH"
        ),
        "mythic_plus_item_s2_scope_unverified": sum(
            1
            for row in source_memberships
            if row.get("logicalSource") == "mythic_plus"
            and row.get("scopeStatus") == "included"
            and _text(
                (row.get("mythicPlusItemScope") or {}).get("status")
            )
            == "UNVERIFIED"
        ),
        "uncomposed_mythic_plus_variant_component": sum(
            1
            for row in variants
            if "OUT_OF_SCOPE_UNCOMPOSED_MPLUS_VARIANT_COMPONENT"
            in (row.get("reasonCodes") or [])
        ),
        "uncomposed_raid_variant_component": sum(
            1
            for row in variants
            if "OUT_OF_SCOPE_UNCOMPOSED_RAID_VARIANT_COMPONENT"
            in (row.get("reasonCodes") or [])
        ),
        "crafted_graph_component_template_owned": sum(
            1
            for row in variants
            if "OUT_OF_SCOPE_CRAFTED_GRAPH_COMPONENT_TEMPLATE_OWNED"
            in (row.get("reasonCodes") or [])
        ),
        "crafted_output_non_canonical_gear_slot": sum(
            1 for row in crafted_edges
            if row.get("scopeStatus") == "excluded"
        ),
        "crafted_recipe_output_missing": len(missing_recipe_ids),
        "crafted_recipe_output_excluded": len(missing_recipe_ids) - len(unresolved_recipe_ids),
        "crafted_recipe_output_unresolved": len(unresolved_recipe_ids),
        **{
            source_type: {
                "value": 0,
                "status": "excluded",
                "reasonCode": "OUT_OF_SCOPE_SOURCE_TYPE",
            }
            for source_type in _EXCLUDED_SOURCE_TYPES
        },
    }
    blocked_item_count = sum(
        1 for row in item_definitions if row["simcReadiness"] == "blocked"
    )
    blocked_variant_count = sum(
        1 for row in variants if row["simcReadiness"] == "blocked"
    )
    source_coverage: dict[str, dict[str, Any]] = {}
    for source in _LOGICAL_SOURCES:
        source_membership_rows = [
            row for row in source_memberships if row.get("logicalSource") == source
        ]
        tier_membership_rows = [
            row for row in tier_memberships if row.get("logicalSource") == source
        ]
        crafted_relationship_rows = [
            row for row in crafted_edges if row.get("logicalSource") == source
        ]
        source_edge_rows = (
            crafted_relationship_rows
            if source == "crafted"
            else [*source_membership_rows, *tier_membership_rows]
        )
        source_item_ids = {
            _text(row.get("itemId"))
            for row in source_edge_rows
            if _text(row.get("itemId")) and row.get("scopeStatus") == "included"
        }
        source_variant_rows = [
            row
            for row in variants
            if source in ((row.get("sourceEligibilityEvidence") or {}).get("bySource") or {})
        ]
        source_statuses = [
            _text(
                ((row.get("sourceEligibilityEvidence") or {}).get("bySource") or {})
                .get(source, {})
                .get("status")
            )
            for row in source_variant_rows
        ]
        crafted_template_rows = [
            row
            for row in crafted_variant_templates
            if source == "crafted"
            and _text(row.get("itemId")) in source_item_ids
        ]
        source_variant_statuses_closed = all(
            status in {"verified", "not_required", "excluded"}
            for status in source_statuses
        )
        crafted_template_status_closed = (
            source != "crafted"
            or (
                crafted_template_rows
                and all(
                    _text(row.get("status")) in {"verified", "excluded"}
                    for row in crafted_template_rows
                )
            )
        )
        source_coverage[source] = {
            "candidateItemCount": len(source_item_ids),
            "includedMembershipEdgeCount": sum(
                1
                for row in source_edge_rows
                if row.get("scopeStatus") == "included"
            ),
            "excludedMembershipEdgeCount": sum(
                1
                for row in source_edge_rows
                if row.get("scopeStatus") == "excluded"
            ),
            "variantEvidenceCount": len(source_variant_rows),
            "verifiedVariantCount": sum(
                1 for status in source_statuses if status == "verified"
            ),
            "unverifiedVariantCount": sum(
                1 for status in source_statuses if status == "UNVERIFIED"
            ),
            "notRequiredVariantCount": sum(
                1 for status in source_statuses if status == "not_required"
            ),
            "status": (
                "verified"
                if source_variant_rows
                and source_variant_statuses_closed
                and crafted_template_status_closed
                else "UNVERIFIED"
                if source_variant_rows
                else "blocked"
            ),
        }
    mythic_plus_item_scope_counts = {
        "observedItemCount": len(mythic_plus_item_scope_by_item),
        "verifiedItemCount": sum(
            1
            for row in mythic_plus_item_scope_by_item.values()
            if _text(row.get("status")) == "verified"
        ),
        "excludedItemCount": sum(
            1
            for row in mythic_plus_item_scope_by_item.values()
            if _text(row.get("status")) == "excluded"
        ),
        "unverifiedItemCount": sum(
            1
            for row in mythic_plus_item_scope_by_item.values()
            if _text(row.get("status")) == "UNVERIFIED"
        ),
        "status": (
            "verified"
            if mythic_plus_item_scope_by_item
            and all(
                _text(row.get("status")) in {"verified", "excluded"}
                for row in mythic_plus_item_scope_by_item.values()
            )
            else "UNVERIFIED"
            if mythic_plus_item_scope_by_item
            else "not_observed"
        ),
        "adapterRevision": MYTHIC_PLUS_ITEM_SCOPE_ADAPTER_REVISION,
        "authority": "official_client_db2",
        "currentItemContextValues": sorted(
            _MYTHIC_PLUS_VARIANT_CONTEXT_VALUES,
            key=int,
        ),
        "s2TrackGroupIds": sorted(s2_track_group_ids, key=int),
    }
    coverage_counts = {
        "fourSourceCandidateTotal": {
            "value": len(candidate_ids),
            "status": "observed",
            "definition": "unique canonical gear item identities with an in-scope official membership or crafted output edge",
        },
        "candidateIncludedCount": len(item_definitions),
        "officialIdentityVerifiedCount": sum(
            1 for row in item_definitions if row["itemIdentity"]["status"] == "verified"
        ),
        "verifiedCount": sum(1 for row in item_definitions if row["evidenceStatus"] == "verified"),
        "unverifiedCount": sum(1 for row in item_definitions if row["evidenceStatus"] == "UNVERIFIED"),
        "blockedCount": blocked_item_count,
        "blockedItemCount": blocked_item_count,
        "blockedVariantCount": blocked_variant_count,
        "blockerCodeCount": len(blocker_codes),
        "blockedCountDefinition": "itemDefinitions with simcReadiness=blocked",
        "simcReadyCount": sum(1 for row in item_definitions if row["simcReadiness"] == "ready"),
        "variantEvidenceCount": len(variants),
        "finalVariantVerifiedCount": sum(1 for row in variants if row["status"] == "verified"),
        "unverifiedVariantCount": sum(1 for row in variants if row["status"] == "UNVERIFIED"),
        "excludedVariantCount": sum(1 for row in variants if row["status"] == "excluded"),
        "sourceMembershipEdgeCount": len(source_memberships),
        "byLogicalSource": source_coverage,
        "tierSetMembershipCount": len(tier_memberships),
        "craftedRecipeOutputEdgeCount": len(crafted_edges),
        "craftedRecipeWithoutOutputCount": len(missing_recipe_ids),
        "craftedVariantTemplateCount": len(crafted_variant_templates),
        "craftedVariantTemplateVerifiedCount": sum(
            1 for row in crafted_variant_templates if row.get("status") == "verified"
        ),
        "craftedVariantTemplateUnverifiedCount": sum(
            1 for row in crafted_variant_templates if row.get("status") == "UNVERIFIED"
        ),
        "craftedVariantTemplateSimcReadyCount": sum(
            1 for row in crafted_variant_templates if row.get("simcReadiness") == "ready"
        ),
        "excludedCount": excluded_counts,
    }
    coverage_counts["mythicPlusItemScope"] = mythic_plus_item_scope_counts
    coverage_counts["enhancement"] = {
        **dict(enhancement_authority.get("coverage") or {}),
        "status": _text(enhancement_authority.get("status")) or "UNVERIFIED",
    }
    status = (
        "verified"
        if candidate_ids
        and not blocker_codes
        and all(row["evidenceStatus"] == "verified" for row in item_definitions)
        and all(row["status"] in {"verified", "excluded"} for row in variants)
        and all(
            row["status"] in {"verified", "excluded"}
            for row in crafted_variant_templates
        )
        and _text(enhancement_authority.get("status")) == "verified"
        else "partial"
        if candidate_ids
        else "blocked"
    )
    report = {
        "schemaRevision": SCHEMA_REVISION,
        "status": status,
        "seasonKey": "midnight-season-2",
        "simcRuntimeIdentity": normalized_simc_runtime_identity or None,
        "db2ClientBuilds": db2_client_builds,
        "mythicPlusCapTrackEvidence": mythic_plus_cap_track_evidence,
        "mythicPlusItemScopeEvidence": {
            **mythic_plus_item_scope_counts,
            "items": [
                mythic_plus_item_scope_by_item[item_id]
                for item_id in sorted(mythic_plus_item_scope_by_item, key=int)
            ],
        },
        "scopeContract": scope_contract,
        "authority": {
            "officialApiFactOwner": "blizzard_game_data_api",
            "db2FactOwner": "official_client_db2",
            "db2TransportRole": "transport_only",
            "simcFactOwner": "none_for_game_facts",
            "simcRuntimeIdentityRequired": True,
        },
        "itemDefinitions": item_definitions,
        "sourceMemberships": sorted(
            source_memberships,
            key=lambda row: (
                _text(row.get("logicalSource")),
                _text(row.get("rawSourceType")),
                _text(row.get("rawSourceKey")),
                int(row["itemId"]),
            ),
        ),
        "tierSetMemberships": sorted(
            tier_memberships,
            key=lambda row: (_text(row.get("setId")), int(row["itemId"])),
        ),
        "tierSetFacts": tier_set_facts,
        "craftedRelationships": sorted(
            crafted_edges,
            key=lambda row: (int(row["recipeId"]), int(row["itemId"])),
        ),
        "craftedVariantTemplates": sorted(
            crafted_variant_templates,
            key=lambda row: (
                int(row["itemId"]),
                int(row["recipeId"]),
                _text(row.get("variantKey")),
            ),
        ),
        "enhancementCatalog": enhancement_authority,
        "setConversions": sorted(set_conversions, key=lambda row: int(row["itemId"])),
        "variants": sorted(variants, key=lambda row: int(row["itemId"])),
        "exclusions": sorted(
            exclusions,
            key=lambda row: (
                _text(row.get("logicalSource")),
                int(row["itemId"]) if _text(row.get("itemId")).isdigit() else 0,
                int(row["recipeId"]) if _text(row.get("recipeId")).isdigit() else 0,
                _text(row.get("reasonCode")),
            ),
        ),
        "coverageCounts": coverage_counts,
        "blockerCodes": sorted(blocker_codes),
        "evidencePacket": {
            "officialApiCaptures": official_manifests,
            "officialItemSetCaptures": official_item_set_manifests,
            "officialEnhancementApiCaptures": enhancement_manifests,
            "db2Captures": db2_manifests,
            "db2ClientBuilds": db2_client_builds,
            "inventorySchemaRevision": inventory_payload.get("schemaRevision"),
            "craftedTargetsSchemaRevision": crafted_target_payload.get("schemaRevision"),
            "craftedCompatibility": {
                "status": (
                    crafted_compatibility_payload.get("status")
                    if crafted_compatibility_payload is not None
                    else "UNVERIFIED"
                ),
                "schemaRevision": (
                    crafted_compatibility_payload.get("schemaRevision")
                    if crafted_compatibility_payload is not None
                    else None
                ),
                "recipeCount": len(crafted_compatibility_recipes),
                "source": (
                    Path(crafted_compatibility).expanduser().resolve().name
                    if crafted_compatibility is not None
                    and not isinstance(crafted_compatibility, Mapping)
                    else "inline"
                    if crafted_compatibility is not None
                    else None
                ),
            },
            "fieldOwners": {
                "sourceMembership": "blizzard_game_data_api",
                "mythicPlusItemScope": (
                    "official_client_db2.ItemXBonusTree_plus_"
                    "ItemBonusTreeNode_plus_ItemBonusListGroup"
                ),
                "itemIdentity": "blizzard_game_data_api",
                "itemStaticFacts": "official_client_db2",
                "variantNumericItemLevel": "official_client_db2.ItemScalingConfig",
                "tierSetEffect": "blizzard_game_data_api.item_set",
                "tierConversionRelation": "official_client_db2.ItemConversion",
                "craftedOutputRelation": "official_client_db2.CraftingData",
                "craftedOptionSemantics": (
                    "official_api_slot_type_plus_bounded_db2_currency_or_item_adapter"
                    if crafted_compatibility_payload is not None
                    else "UNVERIFIED"
                ),
                "enhancementCatalog": "s2_enhancement_authority",
                "gemIdentity": "blizzard_game_data_api.item.preview_item.gem_properties",
                "enchantIdentity": "official_client_db2.SpellItemEnchantment",
                "enhancementSimcSerializer": "s2_enhancement_authority_plus_fixed_simc_readback",
                "craftedQualityVariantTemplate": (
                    "official_client_db2.CraftingDifficultyQuality_plus_exact_bonus_vector"
                    if crafted_variant_templates
                    else "UNVERIFIED"
                ),
                "mythicPlusCapTrack": (
                    "official_client_db2.ItemBonusTreeNode_plus_upgrade_cost_chain"
                    if mythic_plus_cap_track_evidence.get("status") == "verified"
                    else "UNVERIFIED"
                ),
                "mythicPlusJournalItemScope": (
                    "official_client_db2.JournalEncounterItem"
                    if "JournalEncounterItem" in db2_rows
                    else "UNVERIFIED"
                ),
                "simcReadiness": "fixed_same_version_simc_runtime_probe",
            },
        },
        "notARelease": True,
        "activeManifestChanged": False,
        "productionWritten": False,
    }
    # The matrix is an evidence attachment to the exact closure candidate,
    # not an independent source of game facts.  Bind it to the stable fact
    # identity so attaching the matrix does not change the id it was captured
    # against and create a one-step-late self-reference.
    baseline_report_id = _candidate_identity_report_id(report)
    if simc_matrix_payload is not None:
        matrix_candidate_id = _text(simc_matrix_payload.get("candidateReportId"))
        matrix_candidate_identity = _text(
            simc_matrix_payload.get("candidateIdentity")
        )
        matrix_runtime_identity = _text(simc_matrix_payload.get("runtimeIdentity"))
        matrix_status = _text(simc_matrix_payload.get("status"))
        matrix_blocker_codes = {
            _text(code)
            for code in simc_matrix_payload.get("blockerCodes") or []
            if _text(code)
        }
        matrix_status_by_dimension = {
            "publicVariantMatrix": _text(
                _mapping(
                    simc_matrix_payload.get("publicVariantMatrix"),
                    "SimC matrix publicVariantMatrix",
                ).get("status")
            ),
            "craftedVariantMatrix": (
                _text(
                    _mapping(
                        simc_matrix_payload.get("craftedVariantMatrix"),
                        "SimC matrix craftedVariantMatrix",
                    ).get("status")
                )
                if crafted_variant_templates
                else "not_applicable"
            ),
            "setConversionMatrix": _text(
                _mapping(
                    simc_matrix_payload.get("setConversionMatrix"),
                    "SimC matrix setConversionMatrix",
                ).get("status")
            ),
            "representativeProfileMatrix": _text(
                _mapping(
                    simc_matrix_payload.get("representativeProfileMatrix"),
                    "SimC matrix representativeProfileMatrix",
                ).get("status")
            ),
            "enhancementMatrix": _text(
                _mapping(
                    simc_matrix_payload.get("enhancementMatrix"),
                    "SimC matrix enhancementMatrix",
                ).get("status")
            ),
        }
        dimension_blockers = {
            "publicVariantMatrix": "SIMC_PUBLIC_VARIANT_MATRIX_UNVERIFIED",
            "craftedVariantMatrix": "SIMC_CRAFTED_VARIANT_MATRIX_UNVERIFIED",
            "setConversionMatrix": "SIMC_SET_CONVERSION_MATRIX_UNVERIFIED",
            "representativeProfileMatrix": "SIMC_REPRESENTATIVE_PROFILE_MATRIX_UNVERIFIED",
            "enhancementMatrix": "SIMC_ENHANCEMENT_MATRIX_UNVERIFIED",
        }
        for dimension, blocker in dimension_blockers.items():
            if (
                matrix_status_by_dimension[dimension] != "verified"
                and matrix_status_by_dimension[dimension] != "not_applicable"
            ):
                matrix_blocker_codes.add(blocker)
        matrix_rejection_codes: set[str] = set()
        if matrix_candidate_identity:
            candidate_identity_matches = (
                matrix_candidate_identity == baseline_report_id
            )
        else:
            # Backward-compatible fallback for matrix reports produced before
            # candidateIdentity was added.
            candidate_identity_matches = matrix_candidate_id == baseline_report_id
        if not candidate_identity_matches:
            matrix_rejection_codes.add("SIMC_MATRIX_CANDIDATE_ID_MISMATCH")
        if (
            normalized_simc_runtime_identity
            and matrix_runtime_identity != normalized_simc_runtime_identity
        ):
            matrix_rejection_codes.add("SIMC_MATRIX_RUNTIME_IDENTITY_MISMATCH")
        if matrix_status not in {"partial", "verified"}:
            matrix_rejection_codes.add("SIMC_MATRIX_REPORT_STATUS_UNUSABLE")
        if _text(simc_matrix_payload.get("runtimeIdentityStatus")) != "verified":
            matrix_rejection_codes.add("SIMC_MATRIX_RUNTIME_UNVERIFIED")
        matrix_accepted = not matrix_rejection_codes
        if matrix_accepted:
            blocker_codes.discard("SIMC_MATRIX_NOT_RUN")
            blocker_codes.update(matrix_blocker_codes)
        else:
            blocker_codes.update(matrix_rejection_codes)
        matrix_counts = _mapping(simc_matrix_payload.get("counts"), "SimC matrix counts")
        matrix_evidence_status = "accepted" if matrix_accepted else "rejected"
        simc_matrix_evidence = {
            "status": matrix_evidence_status,
            "source": simc_matrix_source,
            "schemaRevision": _text(simc_matrix_payload.get("schemaRevision")),
            "reportId": _text(simc_matrix_payload.get("reportId")),
            "candidateReportId": matrix_candidate_id,
            "candidateIdentity": matrix_candidate_identity or None,
            "baselineCandidateReportId": baseline_report_id,
            "runtimeIdentity": matrix_runtime_identity,
            "matrixStatus": matrix_status,
            "counts": {
                key: matrix_counts.get(key)
                for key in (
                    "publicVariantExpectedCount",
                    "publicVariantProbeCount",
                    "publicVariantVerifiedCount",
                    "publicVariantBlockedCount",
                    "craftedVariantExpectedCount",
                    "craftedVariantProbeCount",
                    "craftedVariantVerifiedCount",
                    "craftedVariantBlockedCount",
                    "setConversionExpectedCount",
                    "setConversionVerifiedCount",
                    "representativeProfileExpectedCount",
                    "representativeProfileVerifiedCount",
                    "remoteBatchCount",
                )
                if key in matrix_counts
            },
            "dimensionStatuses": matrix_status_by_dimension,
            "blockerCodes": sorted(
                matrix_blocker_codes if matrix_accepted else matrix_rejection_codes
            ),
        }
        report["simcMatrixEvidence"] = simc_matrix_evidence
        report["coverageCounts"]["simcMatrix"] = {
            **simc_matrix_evidence["counts"],
            "status": matrix_evidence_status,
            "dimensionStatuses": matrix_status_by_dimension,
        }
        report["evidencePacket"]["simcMatrix"] = simc_matrix_evidence
        if matrix_accepted:
            _apply_simc_matrix_readiness(report, simc_matrix_payload)
        report["blockerCodes"] = sorted(blocker_codes)
        report["status"] = (
            "verified"
            if candidate_ids
            and not blocker_codes
            and all(row["evidenceStatus"] == "verified" for row in item_definitions)
            and all(row["status"] in {"verified", "excluded"} for row in variants)
            and all(
                row["status"] in {"verified", "excluded"}
                for row in crafted_variant_templates
            )
            and _text(enhancement_authority.get("status")) == "verified"
            and all(
                _text(row.get("simcReadiness")) == "ready"
                for row in item_definitions
            )
            and all(
                _text(row.get("simcReadiness")) in {"ready", "excluded"}
                for row in [*variants, *crafted_variant_templates]
            )
            else "partial"
            if candidate_ids
            else "blocked"
        )
    report["reportId"] = _candidate_identity_report_id(report)
    return report


__all__ = [
    "REPORT_PREFIX",
    "SCHEMA_REVISION",
    "S2EquipmentLibraryClosureError",
    "_candidate_identity_report_id",
    "build_s2_equipment_library_closure",
]

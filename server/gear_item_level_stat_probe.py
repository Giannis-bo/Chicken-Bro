#!/usr/bin/env python3
"""Bounded exact-item SimulationCraft stat probe for one governed instance."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable, Iterable, Mapping


SCHEMA_REVISION = "gear-item-level-stat-probe-v1"
REPORT_PREFIX = "gear-item-level-stat-probe:sha256:"
EXPECTED_ITEM_COUNT = 12
EXPECTED_TRACKS = (
    {"difficultyKey": "champion", "itemLevel": 263},
    {"difficultyKey": "hero", "itemLevel": 276},
    {"difficultyKey": "myth", "itemLevel": 289},
    {"difficultyKey": "void_upgrade", "itemLevel": 298},
)
EXPECTED_PAIR_COUNT = EXPECTED_ITEM_COUNT * len(EXPECTED_TRACKS)
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class GearItemLevelStatProbeError(RuntimeError):
    pass


def _text(value: Any) -> str:
    return str(value or "").strip()


def _integer(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _validate_simc_identity(revision: str, binary_sha256: str) -> tuple[str, str]:
    normalized_revision = _text(revision).lower()
    normalized_sha = _text(binary_sha256).lower()
    if not _COMMIT_PATTERN.fullmatch(normalized_revision):
        raise GearItemLevelStatProbeError(
            "SimC revision must be one immutable 40-character commit"
        )
    if not _SHA256_PATTERN.fullmatch(normalized_sha):
        raise GearItemLevelStatProbeError(
            "SimC binary hash must be one immutable SHA-256"
        )
    return normalized_revision, normalized_sha


def _source_items(
    values: Iterable[Mapping[str, Any]],
    *,
    instance_id: str,
    source_type: str,
) -> list[dict[str, Any]]:
    rows = [dict(row) for row in values if isinstance(row, Mapping)]
    rows.sort(key=lambda row: _text(row.get("itemId")))
    item_ids = [_text(row.get("itemId")) for row in rows]
    valid = (
        len(rows) == EXPECTED_ITEM_COUNT
        and len(set(item_ids)) == EXPECTED_ITEM_COUNT
        and all(item_ids)
        and all(_text(row.get("instanceId")) == instance_id for row in rows)
        and all(_text(row.get("sourceType")).lower() == source_type for row in rows)
    )
    return rows if valid else []


def _probe_error_code(
    payload: Mapping[str, Any],
    *,
    item_id: str,
    item_level: int,
) -> str:
    stats = payload.get("itemStats")
    if not isinstance(stats, list) or not stats:
        return "SIMC_TARGET_STATS_MISSING"
    if _text(payload.get("simcItemId")) != item_id:
        return "SIMC_ITEM_ID_MISMATCH"
    if _integer(payload.get("simcItemLevel")) != item_level:
        return "SIMC_ITEM_LEVEL_MISMATCH"
    return ""


def load_instance_items(
    connection: Any,
    instance_id: str,
    source_type: str,
) -> list[dict[str, Any]]:
    from . import websim_payload

    normalized_instance = _text(instance_id)
    normalized_source = _text(source_type).lower()
    with connection.cursor() as cursor:
        cursor.execute(
            "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
        )
        cursor.execute(
            """
            SELECT DISTINCT ON (source.item_id)
                   source.item_id,
                   loot.name,
                   loot.slot,
                   loot.quality,
                   item.payload_json
            FROM websim_gear_sources AS source
            JOIN websim_loot AS loot
              ON loot.item_id = source.item_id
             AND loot.instance_id = source.instance_id
             AND COALESCE(loot.encounter_id, '') =
                 COALESCE(source.encounter_id, '')
            LEFT JOIN websim_items AS item
              ON item.id = source.item_id
            WHERE source.instance_id = %s
              AND source.source_type = %s
            ORDER BY source.item_id, source.encounter_id, loot.id
            """,
            (normalized_instance, normalized_source),
        )
        rows = cursor.fetchall()
    result = []
    for row in rows:
        payload = row[4]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
        payload = payload if isinstance(payload, dict) else {}
        type_metadata = websim_payload.item_type_metadata_from_payload(payload)
        result.append(
            {
                "itemId": _text(row[0]),
                "name": _text(row[1]),
                "slot": websim_payload.normalize_slot(row[2]),
                "quality": _text(row[3]),
                "instanceId": normalized_instance,
                "sourceType": normalized_source,
                "metadataPayload": payload,
                "armorType": _text(type_metadata.get("armorType")).lower(),
                "weaponType": _text(type_metadata.get("weaponType")).lower(),
            }
        )
    return result


def build_probe_report(
    items: Iterable[Mapping[str, Any]],
    *,
    resolver: Callable[[dict[str, Any], int, dict[str, Any]], Mapping[str, Any]],
    instance_id: str,
    source_type: str,
    simc_revision: str,
    simc_binary_sha256: str,
) -> dict[str, Any]:
    normalized_instance = _text(instance_id)
    normalized_source = _text(source_type).lower()
    if normalized_instance != "1305" or normalized_source != "raid":
        raise GearItemLevelStatProbeError(
            "exact item-level stat probe is fixed to raid instance 1305"
        )
    revision, binary_sha = _validate_simc_identity(
        simc_revision,
        simc_binary_sha256,
    )
    source_rows = _source_items(
        items,
        instance_id=normalized_instance,
        source_type=normalized_source,
    )
    result_rows: list[dict[str, Any]] = []
    problem_codes: set[str] = set()
    exact_pairs = 0
    if not source_rows:
        problem_codes.add("SOURCE_ITEM_COUNT_MISMATCH")
    else:
        for item in source_rows:
            item_id = _text(item.get("itemId"))
            levels = []
            for track in EXPECTED_TRACKS:
                item_level = _integer(track["itemLevel"])
                try:
                    resolved = resolver(item, item_level, dict(track))
                    payload = dict(resolved) if isinstance(resolved, Mapping) else {}
                    error_code = _probe_error_code(
                        payload,
                        item_id=item_id,
                        item_level=item_level,
                    )
                except Exception:
                    error_code = "SIMC_PROBE_FAILED"
                if error_code:
                    problem_codes.add(error_code)
                    levels.append(
                        {
                            "itemLevel": item_level,
                            "status": "blocked",
                            "errorCode": error_code,
                        }
                    )
                else:
                    exact_pairs += 1
                    levels.append({"itemLevel": item_level, "status": "exact"})
            result_rows.append({"itemId": item_id, "levels": levels})

    report = {
        "schemaRevision": SCHEMA_REVISION,
        "status": (
            "pass"
            if exact_pairs == EXPECTED_PAIR_COUNT and not problem_codes
            else "blocked"
        ),
        "instanceId": normalized_instance,
        "sourceType": normalized_source,
        "simcRuntime": {
            "revision": revision,
            "binarySha256": binary_sha,
        },
        "targetItemCount": EXPECTED_ITEM_COUNT,
        "targetPairCount": EXPECTED_PAIR_COUNT,
        "exactPairCount": exact_pairs,
        "failedPairCount": EXPECTED_PAIR_COUNT - exact_pairs,
        "items": result_rows,
        "problemCodes": sorted(problem_codes),
    }
    report["reportId"] = REPORT_PREFIX + hashlib.sha256(
        _canonical_bytes(report)
    ).hexdigest()
    return report


def validate_probe_report(
    value: Any,
    *,
    instance_id: str,
    simc_revision: str,
    simc_binary_sha256: str,
) -> bool:
    if not isinstance(value, Mapping):
        return False
    try:
        revision, binary_sha = _validate_simc_identity(
            simc_revision,
            simc_binary_sha256,
        )
    except GearItemLevelStatProbeError:
        return False
    runtime = (
        value.get("simcRuntime")
        if isinstance(value.get("simcRuntime"), Mapping)
        else {}
    )
    if (
        value.get("schemaRevision") != SCHEMA_REVISION
        or value.get("status") not in {"pass", "blocked"}
        or _text(value.get("instanceId")) != _text(instance_id)
        or _text(runtime.get("revision")) != revision
        or _text(runtime.get("binarySha256")) != binary_sha
    ):
        return False
    identity = {
        key: _canonical(item)
        for key, item in value.items()
        if key != "reportId"
    }
    expected_report_id = REPORT_PREFIX + hashlib.sha256(
        _canonical_bytes(identity)
    ).hexdigest()
    return _text(value.get("reportId")) == expected_report_id


__all__ = (
    "EXPECTED_ITEM_COUNT",
    "EXPECTED_PAIR_COUNT",
    "EXPECTED_TRACKS",
    "GearItemLevelStatProbeError",
    "SCHEMA_REVISION",
    "build_probe_report",
    "load_instance_items",
    "validate_probe_report",
)

#!/usr/bin/env python3
"""Guarded PostgreSQL backfill for exact instance-1305 item-level stats."""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Iterable, Mapping

from .gear_item_level_stat_probe import (
    EXPECTED_EXCLUDED_ITEM_COUNT,
    EXPECTED_ITEM_COUNT,
    EXPECTED_PAIR_COUNT,
    EXPECTED_SOURCE_ITEM_COUNT,
    EXPECTED_TRACKS,
    validate_probe_report,
)


BACKFILL_SCHEMA_REVISION = "gear-item-level-stat-backfill-v1"
DERIVED_VARIANT_SOURCE = "simulationcraft_item_level_probe"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class GearItemLevelStatBackfillError(RuntimeError):
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


def _pointer_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "generation": _integer(value.get("generation")),
        "manifestRevision": _text(value.get("manifestRevision")),
        "pointerMode": _text(value.get("pointerMode")),
        "rollbackManifestRevision": _text(value.get("rollbackManifestRevision")),
    }


def target_pairs(
    report: Mapping[str, Any],
    *,
    simc_revision: str,
    simc_binary_sha256: str,
) -> list[tuple[str, int]]:
    valid_identity = validate_probe_report(
        report,
        instance_id="1305",
        simc_revision=simc_revision,
        simc_binary_sha256=simc_binary_sha256,
    )
    excluded = report.get("excludedItems")
    rows = report.get("items")
    if (
        not valid_identity
        or report.get("status") != "pass"
        or _text(report.get("sourceType")).lower() != "raid"
        or _integer(report.get("sourceItemCount")) != EXPECTED_SOURCE_ITEM_COUNT
        or _integer(report.get("targetItemCount")) != EXPECTED_ITEM_COUNT
        or _integer(report.get("excludedItemCount"))
        != EXPECTED_EXCLUDED_ITEM_COUNT
        or _integer(report.get("targetPairCount")) != EXPECTED_PAIR_COUNT
        or _integer(report.get("exactPairCount")) != EXPECTED_PAIR_COUNT
        or _integer(report.get("failedPairCount")) != 0
        or report.get("problemCodes") != []
        or not isinstance(excluded, list)
        or len(excluded) != EXPECTED_EXCLUDED_ITEM_COUNT
        or not isinstance(rows, list)
        or len(rows) != EXPECTED_ITEM_COUNT
    ):
        raise GearItemLevelStatBackfillError(
            "probe report is not one exact eligible-item pass"
        )
    excluded_row = excluded[0] if isinstance(excluded[0], Mapping) else {}
    if (
        _text(excluded_row.get("status")) != "excluded"
        or _text(excluded_row.get("reasonCode")) != "NON_COMBAT_COSMETIC"
        or not _text(excluded_row.get("itemId"))
    ):
        raise GearItemLevelStatBackfillError(
            "probe report cosmetic exclusion is invalid"
        )

    expected_levels = [_integer(track["itemLevel"]) for track in EXPECTED_TRACKS]
    pairs: list[tuple[str, int]] = []
    item_ids: set[str] = set()
    for row in rows:
        item = row if isinstance(row, Mapping) else {}
        item_id = _text(item.get("itemId"))
        levels = item.get("levels")
        if not item_id or item_id in item_ids or not isinstance(levels, list):
            raise GearItemLevelStatBackfillError(
                "probe report target item rows are invalid"
            )
        observed_levels = []
        for level_row in levels:
            value = level_row if isinstance(level_row, Mapping) else {}
            level = _integer(value.get("itemLevel"))
            if _text(value.get("status")) != "exact" or value.get("errorCode"):
                raise GearItemLevelStatBackfillError(
                    "probe report contains a non-exact target pair"
                )
            observed_levels.append(level)
            pairs.append((item_id, level))
        if observed_levels != expected_levels:
            raise GearItemLevelStatBackfillError(
                "probe report target levels are invalid"
            )
        item_ids.add(item_id)
    if (
        len(pairs) != EXPECTED_PAIR_COUNT
        or len(set(pairs)) != EXPECTED_PAIR_COUNT
        or _text(excluded_row.get("itemId")) in item_ids
    ):
        raise GearItemLevelStatBackfillError(
            "probe report target pair set is invalid"
        )
    return sorted(pairs, key=lambda pair: (pair[0], pair[1]))


def prepare_variant_updates(
    original_rows: Iterable[Mapping[str, Any]],
    resolved_by_pair: Mapping[tuple[str, int], Mapping[str, Any]],
    *,
    simc_revision: str,
    simc_binary_sha256: str,
) -> list[dict[str, Any]]:
    revision = _text(simc_revision).lower()
    binary_sha = _text(simc_binary_sha256).lower()
    if not re.fullmatch(r"[0-9a-f]{40}", revision) or not _SHA256_PATTERN.fullmatch(
        binary_sha
    ):
        raise GearItemLevelStatBackfillError("SimC identity is invalid")
    rows = [dict(row) for row in original_rows if isinstance(row, Mapping)]
    row_keys = {
        (_text(row.get("itemId")), _integer(row.get("itemLevel")))
        for row in rows
    }
    resolved_keys = {
        (_text(key[0]), _integer(key[1]))
        for key in resolved_by_pair
        if isinstance(key, tuple) and len(key) == 2
    }
    if (
        len(rows) != EXPECTED_PAIR_COUNT
        or len(row_keys) != EXPECTED_PAIR_COUNT
        or len(resolved_keys) != EXPECTED_PAIR_COUNT
        or row_keys != resolved_keys
    ):
        raise GearItemLevelStatBackfillError(
            "backfill requires exactly 44 exact staging rows"
        )

    updates = []
    for row in rows:
        item_id = _text(row.get("itemId"))
        item_level = _integer(row.get("itemLevel"))
        pair = (item_id, item_level)
        original_payload = (
            dict(row.get("payload"))
            if isinstance(row.get("payload"), Mapping)
            else {}
        )
        resolved = resolved_by_pair.get(pair)
        stat_payload = dict(resolved) if isinstance(resolved, Mapping) else {}
        stats = stat_payload.get("itemStats")
        if (
            not _text(row.get("id"))
            or _text(row.get("readiness")).lower() != "partial"
            or _text(row.get("status")).lower() != "partial"
            or _text(original_payload.get("derivedVariantSource"))
            != DERIVED_VARIANT_SOURCE
            or not isinstance(stats, list)
            or not stats
            or _text(stat_payload.get("simcItemId")) != item_id
            or _integer(stat_payload.get("simcItemLevel")) != item_level
        ):
            raise GearItemLevelStatBackfillError(
                "backfill staging row or resolved stat payload is not exact"
            )
        payload = original_payload
        for key in ("error", "simcProfile", "classKey", "specKey"):
            payload.pop(key, None)
        for key in (
            "statSource",
            "statSourceDetail",
            "statDisplayStatus",
            "statSummary",
            "simcItemId",
            "simcItemLevel",
            "simcEncodedItem",
            "probeClassKey",
            "probeSpecKey",
            "simcCheckedAt",
            "simcDurationMs",
        ):
            value = stat_payload.get(key)
            if value not in (None, "", [], {}):
                payload[key] = _canonical(value)
        payload.update(
            {
                "derivedVariantSource": DERIVED_VARIANT_SOURCE,
                "simcIlevelOnly": True,
                "statSource": "simulationcraft",
                "statDisplayStatus": "verified_variant",
                "itemStats": _canonical(stats),
                "stats": _canonical(stats),
                "simcRuntimeRevision": revision,
                "simcBinarySha256": binary_sha,
            }
        )
        updates.append(
            {
                "id": _text(row.get("id")),
                "itemId": item_id,
                "itemLevel": item_level,
                "readiness": "verified",
                "status": "verified",
                "blockers": [],
                "payload": payload,
                "originalUpdatedAt": row.get("updatedAt"),
            }
        )
    return sorted(
        updates,
        key=lambda update: (update["itemId"], update["itemLevel"]),
    )


def _start_serializable(connection: Any) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        cursor.execute("SET lock_timeout = 5000")
        cursor.execute("SET statement_timeout = 30000")


def _read_pointer(connection: Any) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT generation, manifest_revision, pointer_mode,
                   rollback_manifest_revision
            FROM cache.websim_active_manifest_pointer
            WHERE environment = 'retail'
            """
        )
        row = cursor.fetchone()
    if not row:
        raise GearItemLevelStatBackfillError(
            "active retail Manifest pointer is unavailable"
        )
    return {
        "generation": row[0],
        "manifestRevision": row[1],
        "pointerMode": row[2],
        "rollbackManifestRevision": row[3],
    }


def _load_rows_for_update(
    connection: Any,
    pairs: Iterable[tuple[str, int]],
) -> list[dict[str, Any]]:
    pair_list = list(pairs)
    item_ids = sorted({pair[0] for pair in pair_list})
    levels = sorted({pair[1] for pair in pair_list})
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id::text, item_id, item_level, readiness, status,
                   blockers_json, payload_json, updated_at
            FROM cache.websim_gear_variants
            WHERE item_id = ANY(%s::text[])
              AND item_level = ANY(%s::integer[])
              AND source_type = 'raid'
              AND payload_json->>'derivedVariantSource' = %s
            ORDER BY item_id, item_level, id::text
            FOR UPDATE
            """,
            (item_ids, levels, DERIVED_VARIANT_SOURCE),
        )
        rows = cursor.fetchall()
    return [
        {
            "id": _text(row[0]),
            "itemId": _text(row[1]),
            "itemLevel": _integer(row[2]),
            "readiness": _text(row[3]),
            "status": _text(row[4]),
            "blockers": _canonical(row[5] if isinstance(row[5], list) else []),
            "payload": _canonical(row[6] if isinstance(row[6], dict) else {}),
            "updatedAt": row[7],
        }
        for row in rows
        if (_text(row[1]), _integer(row[2])) in set(pair_list)
    ]


def _update_row(connection: Any, update: Mapping[str, Any]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE cache.websim_gear_variants
            SET readiness = %s,
                status = %s,
                blockers_json = %s::jsonb,
                payload_json = %s::jsonb,
                updated_at = now()
            WHERE id = %s::uuid
              AND updated_at = %s
            """,
            (
                update["readiness"],
                update["status"],
                json.dumps(update["blockers"], ensure_ascii=False),
                json.dumps(update["payload"], ensure_ascii=False),
                update["id"],
                update["originalUpdatedAt"],
            ),
        )
        if cursor.rowcount != 1:
            raise GearItemLevelStatBackfillError(
                "staging variant changed during guarded backfill"
            )


def _verify_rows(
    connection: Any,
    pairs: Iterable[tuple[str, int]],
) -> set[tuple[str, int]]:
    pair_list = list(pairs)
    item_ids = sorted({pair[0] for pair in pair_list})
    levels = sorted({pair[1] for pair in pair_list})
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT item_id, item_level
            FROM cache.websim_gear_variants
            WHERE item_id = ANY(%s::text[])
              AND item_level = ANY(%s::integer[])
              AND source_type = 'raid'
              AND payload_json->>'derivedVariantSource' = %s
              AND readiness = 'verified'
              AND status = 'verified'
              AND blockers_json = '[]'::jsonb
              AND payload_json->>'statDisplayStatus' = 'verified_variant'
              AND jsonb_array_length(
                    COALESCE(payload_json->'itemStats', '[]'::jsonb)
                  ) > 0
            ORDER BY item_id, item_level
            """,
            (item_ids, levels, DERIVED_VARIANT_SOURCE),
        )
        rows = cursor.fetchall()
    return {
        (_text(row[0]), _integer(row[1]))
        for row in rows
        if (_text(row[0]), _integer(row[1])) in set(pair_list)
    }


def backfill_exact_rows(
    connection: Any,
    *,
    report: Mapping[str, Any],
    resolved_by_pair: Mapping[tuple[str, int], Mapping[str, Any]],
    simc_revision: str,
    simc_binary_sha256: str,
    backup_writer: Callable[
        [list[dict[str, Any]], dict[str, Any]], Mapping[str, Any]
    ],
    transaction_starter: Callable[[Any], None] = _start_serializable,
    pointer_reader: Callable[[Any], Mapping[str, Any]] = _read_pointer,
    row_loader: Callable[
        [Any, Iterable[tuple[str, int]]], list[dict[str, Any]]
    ] = _load_rows_for_update,
    row_updater: Callable[[Any, Mapping[str, Any]], None] = _update_row,
    row_verifier: Callable[
        [Any, Iterable[tuple[str, int]]], set[tuple[str, int]]
    ] = _verify_rows,
) -> dict[str, Any]:
    pairs = target_pairs(
        report,
        simc_revision=simc_revision,
        simc_binary_sha256=simc_binary_sha256,
    )
    try:
        transaction_starter(connection)
        pointer_before = _pointer_identity(pointer_reader(connection))
        original_rows = row_loader(connection, pairs)
        updates = prepare_variant_updates(
            original_rows,
            resolved_by_pair,
            simc_revision=simc_revision,
            simc_binary_sha256=simc_binary_sha256,
        )
        backup = dict(backup_writer(original_rows, pointer_before))
        if (
            not _text(backup.get("path"))
            or not _SHA256_PATTERN.fullmatch(_text(backup.get("sha256")))
        ):
            raise GearItemLevelStatBackfillError(
                "staging backup identity is invalid"
            )
        for update in updates:
            row_updater(connection, update)
        if row_verifier(connection, pairs) != set(pairs):
            raise GearItemLevelStatBackfillError(
                "updated staging row verification failed"
            )
        pointer_after = _pointer_identity(pointer_reader(connection))
        if pointer_after != pointer_before:
            raise GearItemLevelStatBackfillError(
                "active Manifest pointer changed during staging backfill"
            )
        connection.commit()
        return {
            "schemaRevision": BACKFILL_SCHEMA_REVISION,
            "status": "pass",
            "updatedVariantCount": len(updates),
            "targetItemCount": EXPECTED_ITEM_COUNT,
            "excludedItemCount": EXPECTED_EXCLUDED_ITEM_COUNT,
            "pointerBefore": pointer_before,
            "pointerAfter": pointer_after,
            "backup": {
                "path": _text(backup.get("path")),
                "sha256": _text(backup.get("sha256")),
            },
        }
    except Exception:
        connection.rollback()
        raise


__all__ = (
    "BACKFILL_SCHEMA_REVISION",
    "GearItemLevelStatBackfillError",
    "backfill_exact_rows",
    "prepare_variant_updates",
    "target_pairs",
)

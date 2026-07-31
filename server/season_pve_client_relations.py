"""Pure joins for official current-client PVE relation evidence."""

from __future__ import annotations

import json
from typing import Any, Iterable, TextIO


class ClientRelationEvidenceError(ValueError):
    """Raised when a client relation cannot be joined unambiguously."""


_COMBAT_ITEM_CLASS_IDS = {2, 4}
_COMBAT_INVENTORY_TYPE_IDS = {
    1,
    2,
    3,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    20,
    21,
    22,
    23,
    25,
    26,
}
_MIDNIGHT_RENOWN_IDS = set(range(36, 45))
_MIDNIGHT_POWER_RENOWN_LABELS = {
    "Head Armor Available",
    "Necklace Available",
    "Trinket Available",
    "Waist Armor Available",
}
_MIDNIGHT_DELVE_PROGRESSION_LABELS = {
    "Champion Warbound Equipment",
    "Delve Vendor Zah'ran Unlocked",
    "Delve Vendor Zah'ran Upgraded",
}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _positive_id(value: Any, label: str) -> str:
    resolved = _text(value)
    if not resolved.isdigit() or int(resolved) < 1:
        raise ClientRelationEvidenceError(
            f"{label} requires a positive integer id"
        )
    return resolved


def _nonnegative_int(value: Any, label: str) -> int:
    resolved = _text(value)
    if not resolved.isdigit():
        raise ClientRelationEvidenceError(
            f"{label} requires a non-negative integer"
        )
    return int(resolved)


def _rows(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ClientRelationEvidenceError(f"{label} must be a list")
    if not all(isinstance(row, dict) for row in value):
        raise ClientRelationEvidenceError(
            f"{label} rows must be objects"
        )
    return list(value)


def _byte_sequence(
    row: dict[str, Any],
    field_prefix: str,
    length: int,
    label: str,
) -> bytes:
    values = []
    for index in range(1, length + 1):
        value = _nonnegative_int(
            row.get(f"{field_prefix}_{index}"),
            f"{label} byte {index}",
        )
        if value > 255:
            raise ClientRelationEvidenceError(
                f"{label} byte {index} must be at most 255"
            )
        values.append(value)
    return bytes(values)


def wdc5_tact_key_id_to_blte_key_id(value: Any) -> str:
    """Convert a WDC5 uint64 key id to its BLTE byte-order identity."""

    key_id = _text(value).lower()
    if (
        len(key_id) != 16
        or any(
            character not in "0123456789abcdef"
            for character in key_id
        )
    ):
        raise ClientRelationEvidenceError(
            "WDC5 TACT key id requires 16 hexadecimal characters"
        )
    return bytes.fromhex(key_id)[::-1].hex()


def audit_public_tact_key_reextract(
    *,
    public_key_coverage: Any,
    blte_encryption_audit: Any,
    table_comparisons: Any,
) -> dict[str, Any]:
    """Audit the distinct record-key and BLTE-key decryption layers."""

    if not isinstance(public_key_coverage, dict):
        raise ClientRelationEvidenceError(
            "public TACT key coverage must be an object"
        )
    coverage_summary = public_key_coverage.get("summary")
    if not isinstance(coverage_summary, dict):
        raise ClientRelationEvidenceError(
            "public TACT key coverage summary must be an object"
        )
    coverage_values = {
        field: _nonnegative_int(
            coverage_summary.get(field),
            f"public TACT key coverage {field}",
        )
        for field in (
            "targetKeyCount",
            "targetRecordCount",
            "availableTargetKeyCount",
            "missingTargetKeyCount",
            "coveredTargetRecordCount",
            "missingTargetRecordCount",
        )
    }
    if (
        coverage_values["targetKeyCount"] < 1
        or coverage_values["targetRecordCount"] < 1
        or coverage_values["availableTargetKeyCount"]
        + coverage_values["missingTargetKeyCount"]
        != coverage_values["targetKeyCount"]
        or coverage_values["coveredTargetRecordCount"]
        + coverage_values["missingTargetRecordCount"]
        != coverage_values["targetRecordCount"]
    ):
        raise ClientRelationEvidenceError(
            "public TACT key coverage counts are inconsistent"
        )
    record_target_keys = _rows(
        public_key_coverage.get("targetKeys"),
        "public TACT record target keys",
    )
    record_key_ids = {
        _text(row.get("tactKeyId")).lower()
        for row in record_target_keys
    }
    if (
        len(record_target_keys) != coverage_values["targetKeyCount"]
        or len(record_key_ids) != len(record_target_keys)
        or any(
            len(key_id) != 16
            or any(
                character not in "0123456789abcdef"
                for character in key_id
            )
            for key_id in record_key_ids
        )
    ):
        raise ClientRelationEvidenceError(
            "public TACT record target key identities are invalid"
        )
    record_blte_key_ids = {
        wdc5_tact_key_id_to_blte_key_id(key_id)
        for key_id in record_key_ids
    }

    if not isinstance(blte_encryption_audit, dict):
        raise ClientRelationEvidenceError(
            "BLTE encryption audit must be an object"
        )
    salsa20_available = blte_encryption_audit.get(
        "salsa20Available"
    )
    if not isinstance(salsa20_available, bool):
        raise ClientRelationEvidenceError(
            "BLTE encryption audit requires a Salsa20 capability result"
        )
    blte_counts = {
        field: _nonnegative_int(
            blte_encryption_audit.get(field),
            f"BLTE encryption audit {field}",
        )
        for field in (
            "encryptedChunkCount",
            "keyAvailableChunkCount",
            "decryptedChunkCount",
            "zeroFallbackChunkCount",
        )
    }
    blte_key_audits = _rows(
        blte_encryption_audit.get("keyAudits"),
        "BLTE encryption key audits",
    )
    blte_key_ids = set()
    chunk_count = 0
    key_available_chunk_count = 0
    decrypted_chunk_count = 0
    for row in blte_key_audits:
        key_id = _text(row.get("keyId")).lower()
        row_chunk_count = _nonnegative_int(
            row.get("chunkCount"),
            f"BLTE key {key_id} chunk count",
        )
        row_output_bytes = _nonnegative_int(
            row.get("outputBytes"),
            f"BLTE key {key_id} output bytes",
        )
        row_key_available = _nonnegative_int(
            row.get("keyAvailableChunkCount"),
            f"BLTE key {key_id} available chunk count",
        )
        row_decrypted = _nonnegative_int(
            row.get("decryptedChunkCount"),
            f"BLTE key {key_id} decrypted chunk count",
        )
        if (
            len(key_id) != 16
            or any(
                character not in "0123456789abcdef"
                for character in key_id
            )
            or key_id in blte_key_ids
            or row_chunk_count < 1
            or row_output_bytes < 1
            or row_key_available > row_chunk_count
            or row_decrypted > row_key_available
        ):
            raise ClientRelationEvidenceError(
                "BLTE key audits require unique key identities and "
                "bounded non-empty chunk counts"
            )
        blte_key_ids.add(key_id)
        chunk_count += row_chunk_count
        key_available_chunk_count += row_key_available
        decrypted_chunk_count += row_decrypted
    if (
        not blte_key_ids
        or chunk_count != blte_counts["encryptedChunkCount"]
        or key_available_chunk_count
        != blte_counts["keyAvailableChunkCount"]
        or decrypted_chunk_count
        != blte_counts["decryptedChunkCount"]
        or blte_counts["zeroFallbackChunkCount"]
        != blte_counts["encryptedChunkCount"]
        - blte_counts["decryptedChunkCount"]
    ):
        raise ClientRelationEvidenceError(
            "BLTE encryption audit counts are inconsistent"
        )

    comparisons = _rows(
        table_comparisons,
        "TACT key re-extraction table comparisons",
    )
    if not comparisons:
        raise ClientRelationEvidenceError(
            "TACT key re-extraction table comparisons must not be empty"
        )
    table_rows = []
    table_names = set()
    for row in comparisons:
        table = _text(row.get("table"))
        original_sha = _text(row.get("originalSha256")).lower()
        reextracted_sha = _text(row.get("reextractedSha256")).lower()
        encrypted_count = _nonnegative_int(
            row.get("encryptedRecordCount"),
            f"{table} encrypted record count",
        )
        available_count = _nonnegative_int(
            row.get("availableEncryptedRecordCount"),
            f"{table} available encrypted record count",
        )
        if (
            not table
            or table in table_names
            or encrypted_count < 1
            or available_count > encrypted_count
            or any(
                len(value) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in value
                )
                for value in (original_sha, reextracted_sha)
            )
        ):
            raise ClientRelationEvidenceError(
                "TACT key re-extraction comparisons require unique tables, "
                "SHA-256 values, and bounded encrypted record counts"
            )
        changed = original_sha != reextracted_sha
        if available_count and not changed:
            raise ClientRelationEvidenceError(
                f"{table} cannot recover encrypted records without "
                "changing the static payload"
            )
        table_names.add(table)
        table_rows.append(
            {
                "table": table,
                "originalSha256": original_sha,
                "reextractedSha256": reextracted_sha,
                "changed": changed,
                "encryptedRecordCount": encrypted_count,
                "availableEncryptedRecordCount": available_count,
                "unavailableEncryptedRecordCount": (
                    encrypted_count - available_count
                ),
            }
        )

    encrypted_record_count = sum(
        row["encryptedRecordCount"] for row in table_rows
    )
    recovered_record_count = sum(
        row["availableEncryptedRecordCount"] for row in table_rows
    )
    if encrypted_record_count != coverage_values["targetRecordCount"]:
        raise ClientRelationEvidenceError(
            "TACT key re-extraction must retain the target record baseline"
        )
    unavailable_record_count = (
        encrypted_record_count - recovered_record_count
    )
    complete = (
        coverage_values["missingTargetKeyCount"] == 0
        and unavailable_record_count == 0
        and blte_counts["zeroFallbackChunkCount"] == 0
    )
    blockers = []
    if coverage_values["missingTargetKeyCount"]:
        blockers.append("APPROVED_PUBLIC_TACT_KEYS_INCOMPLETE")
    if not salsa20_available:
        blockers.append("SIMC_CASC_SALSA20_DECRYPTION_UNAVAILABLE")
    if blte_counts["zeroFallbackChunkCount"]:
        blockers.append(
            "CURRENT_CLIENT_BLTE_DECRYPTION_KEYS_UNAVAILABLE"
        )
    if unavailable_record_count:
        blockers.append(
            "CURRENT_CLIENT_ENCRYPTED_SOURCE_RECORDS_UNAVAILABLE"
        )
    return {
        "status": (
            "complete"
            if complete
            else (
                "partial"
                if recovered_record_count
                or blte_counts["decryptedChunkCount"]
                else "blocked"
            )
        ),
        "summary": {
            "tableCount": len(table_rows),
            "changedTableCount": sum(
                row["changed"] for row in table_rows
            ),
            "recordTactKeyCount": coverage_values["targetKeyCount"],
            "publicRecordTactKeyCount": coverage_values[
                "availableTargetKeyCount"
            ],
            "missingRecordTactKeyCount": coverage_values[
                "missingTargetKeyCount"
            ],
            "publicRecordTactKeyCoveredRecordCount": coverage_values[
                "coveredTargetRecordCount"
            ],
            "recordTactKeyToBlteKeyOverlapCount": len(
                record_blte_key_ids & blte_key_ids
            ),
            "blteKeyCount": len(blte_key_ids),
            "blteEncryptedChunkCount": blte_counts[
                "encryptedChunkCount"
            ],
            "blteKeyAvailableChunkCount": blte_counts[
                "keyAvailableChunkCount"
            ],
            "blteDecryptedChunkCount": blte_counts[
                "decryptedChunkCount"
            ],
            "blteZeroFallbackChunkCount": blte_counts[
                "zeroFallbackChunkCount"
            ],
            "targetEncryptedRecordCount": encrypted_record_count,
            "recoveredEncryptedRecordCount": recovered_record_count,
            "unavailableEncryptedRecordCount": (
                unavailable_record_count
            ),
        },
        "tables": sorted(table_rows, key=lambda row: row["table"]),
        "blockers": blockers,
    }


def write_ephemeral_tact_keyfile(
    *,
    base_key_entries: Any,
    approved_public_key_lines: Iterable[str],
    target_keys: Any,
    destination: TextIO,
) -> dict[str, Any]:
    """Prepare an ephemeral keyfile while returning only redacted metadata."""

    def parse_key_lines(
        lines: Iterable[str],
        label: str,
    ) -> dict[str, str]:
        records: dict[str, str] = {}
        for raw_line in lines:
            line = _text(raw_line)
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) < 2:
                raise ClientRelationEvidenceError(
                    f"malformed {label} TACT key record"
                )
            key_id = fields[0].lower()
            key_material = fields[1].lower()
            if (
                len(key_id) != 16
                or any(character not in "0123456789abcdef" for character in key_id)
                or len(key_material) != 32
                or any(
                    character not in "0123456789abcdef"
                    for character in key_material
                )
            ):
                raise ClientRelationEvidenceError(
                    f"malformed {label} TACT key record"
                )
            existing = records.get(key_id)
            if existing is not None and existing != key_material:
                raise ClientRelationEvidenceError(
                    f"conflicting {label} TACT key {key_id}"
                )
            records[key_id] = key_material
        return records

    base_rows = _rows(base_key_entries, "base TACT key entries")
    base_output = []
    base_keys: dict[str, str] = {}
    base_ids = set()
    maximum_base_id = 0
    for row in base_rows:
        row_id = int(_positive_id(row.get("id"), "base TACT key"))
        key_id = _text(row.get("key_id")).lower()
        key_material = _text(row.get("key")).lower()
        if (
            row_id in base_ids
            or len(key_id) != 16
            or any(character not in "0123456789abcdef" for character in key_id)
            or (
                key_material
                and (
                    len(key_material) != 32
                    or any(
                        character not in "0123456789abcdef"
                        for character in key_material
                    )
                )
            )
        ):
            raise ClientRelationEvidenceError(
                "base TACT key entries require unique positive ids, "
                "16-character key ids, and optional 32-character keys"
            )
        existing = base_keys.get(key_id)
        if (
            key_material
            and existing is not None
            and existing != key_material
        ):
            raise ClientRelationEvidenceError(
                f"conflicting base TACT key {key_id}"
            )
        if key_material:
            base_keys[key_id] = key_material
        base_ids.add(row_id)
        maximum_base_id = max(maximum_base_id, row_id)
        base_output.append(
            {
                "id": row_id,
                "key_id": key_id,
                "key": (
                    key_material.upper()
                    if key_material
                    else None
                ),
            }
        )

    public_keys = parse_key_lines(
        approved_public_key_lines,
        "approved public",
    )
    targets = _rows(target_keys, "target TACT keys")
    if not targets:
        raise ClientRelationEvidenceError(
            "target TACT keys must not be empty"
        )
    target_by_id: dict[str, dict[str, Any]] = {}
    for row in targets:
        key_id = _text(row.get("tactKeyId")).lower()
        blte_key_id = wdc5_tact_key_id_to_blte_key_id(key_id)
        record_count = _nonnegative_int(
            row.get("recordCount"),
            f"target TACT key {key_id} record count",
        )
        tables = row.get("tables")
        if (
            len(key_id) != 16
            or any(character not in "0123456789abcdef" for character in key_id)
            or record_count < 1
            or not isinstance(tables, list)
            or not tables
            or not all(_text(table) for table in tables)
        ):
            raise ClientRelationEvidenceError(
                "target TACT key requires a 16-character key id, "
                "positive record count, and tables"
            )
        if key_id in target_by_id:
            raise ClientRelationEvidenceError(
                f"duplicate target TACT key {key_id}"
            )
        target_by_id[key_id] = {
            "tactKeyId": key_id,
            "blteKeyId": blte_key_id,
            "recordCount": record_count,
            "tables": sorted({_text(table) for table in tables}),
            "presentInBaseKeyfile": blte_key_id in base_keys,
            "presentInApprovedPublicSnapshot": key_id in public_keys,
            "availableAfterMerge": (
                blte_key_id in base_keys or key_id in public_keys
            ),
        }

    merged_entries = list(base_output)
    added_target_key_ids = []
    next_id = maximum_base_id + 1
    for key_id in sorted(target_by_id):
        blte_key_id = target_by_id[key_id]["blteKeyId"]
        if blte_key_id in base_keys or key_id not in public_keys:
            continue
        merged_entries.append(
            {
                "id": next_id,
                "key_id": blte_key_id,
                "key": public_keys[key_id].upper(),
            }
        )
        next_id += 1
        added_target_key_ids.append(key_id)

    target_rows = [
        target_by_id[key_id]
        for key_id in sorted(target_by_id)
    ]
    covered_record_count = sum(
        row["recordCount"]
        for row in target_rows
        if row["availableAfterMerge"]
    )
    target_record_count = sum(
        row["recordCount"] for row in target_rows
    )
    available_target_count = sum(
        row["availableAfterMerge"] for row in target_rows
    )
    complete = available_target_count == len(target_rows)
    json.dump(
        merged_entries,
        destination,
        ensure_ascii=True,
        indent=2,
    )
    destination.write("\n")
    return {
        "status": "complete" if complete else "blocked",
        "summary": {
            "baseEntryCount": len(base_rows),
            "baseUsableKeyCount": len(base_keys),
            "approvedPublicKeyCount": len(public_keys),
            "targetKeyCount": len(target_rows),
            "targetRecordCount": target_record_count,
            "addedTargetKeyCount": len(added_target_key_ids),
            "availableTargetKeyCount": available_target_count,
            "missingTargetKeyCount": (
                len(target_rows) - available_target_count
            ),
            "coveredTargetRecordCount": covered_record_count,
            "missingTargetRecordCount": (
                target_record_count - covered_record_count
            ),
        },
        "targetKeys": target_rows,
        "blockers": (
            []
            if complete
            else ["APPROVED_PUBLIC_TACT_KEYS_INCOMPLETE"]
        ),
    }


def audit_current_client_tact_key_coverage(
    *,
    tact_keys: Any,
    tact_key_lookups: Any,
    encrypted_sections: Any,
) -> dict[str, Any]:
    """Audit static client TACT-key coverage without returning key material."""

    key_rows = _rows(tact_keys, "TACT keys")
    lookup_rows = _rows(tact_key_lookups, "TACT key lookups")
    section_rows = _rows(encrypted_sections, "encrypted sections")

    key_ids = set()
    for row in key_rows:
        row_id = _positive_id(row.get("id"), "TACT key")
        if row_id in key_ids:
            raise ClientRelationEvidenceError(
                f"duplicate TACT key {row_id}"
            )
        _byte_sequence(row, "key", 16, f"TACT key {row_id}")
        key_ids.add(row_id)

    lookup_by_id = {}
    for row in lookup_rows:
        row_id = _positive_id(row.get("id"), "TACT key lookup")
        if row_id in lookup_by_id:
            raise ClientRelationEvidenceError(
                f"duplicate TACT key lookup {row_id}"
            )
        key_name = _byte_sequence(
            row,
            "key_name",
            8,
            f"TACT key lookup {row_id}",
        ).hex()
        lookup_by_id[row_id] = key_name

    available_key_names = {
        lookup_by_id[row_id]
        for row_id in key_ids.intersection(lookup_by_id)
    }
    target_by_id: dict[str, dict[str, Any]] = {}
    for row in section_rows:
        table = _text(row.get("table"))
        tact_key_id = _text(row.get("tactKeyId")).lower()
        record_count = _nonnegative_int(
            row.get("recordCount"),
            f"encrypted section {tact_key_id} record count",
        )
        if (
            not table
            or len(tact_key_id) != 16
            or any(character not in "0123456789abcdef" for character in tact_key_id)
            or record_count < 1
        ):
            raise ClientRelationEvidenceError(
                "encrypted section requires table, 16-character key id, "
                "and a positive record count"
            )
        target = target_by_id.setdefault(
            tact_key_id,
            {
                "tactKeyId": tact_key_id,
                "recordCount": 0,
                "tables": set(),
                "presentInCurrentClientStaticTables": (
                    tact_key_id in available_key_names
                ),
            },
        )
        target["recordCount"] += record_count
        target["tables"].add(table)

    target_keys = []
    for tact_key_id in sorted(target_by_id):
        target = target_by_id[tact_key_id]
        target_keys.append(
            {
                **target,
                "tables": sorted(target["tables"]),
            }
        )
    target_record_count = sum(
        row["recordCount"] for row in target_keys
    )
    covered_record_count = sum(
        row["recordCount"]
        for row in target_keys
        if row["presentInCurrentClientStaticTables"]
    )
    present_target_count = sum(
        row["presentInCurrentClientStaticTables"]
        for row in target_keys
    )
    complete = (
        bool(target_keys)
        and present_target_count == len(target_keys)
    )
    return {
        "status": "complete" if complete else "blocked",
        "summary": {
            "staticKeyRowCount": len(key_rows),
            "staticLookupRowCount": len(lookup_rows),
            "joinedStaticKeyCount": len(available_key_names),
            "targetKeyCount": len(target_keys),
            "targetRecordCount": target_record_count,
            "presentTargetKeyCount": present_target_count,
            "missingTargetKeyCount": (
                len(target_keys) - present_target_count
            ),
            "coveredTargetRecordCount": covered_record_count,
            "missingTargetRecordCount": (
                target_record_count - covered_record_count
            ),
        },
        "targetKeys": target_keys,
        "blockers": (
            []
            if complete
            else ["CURRENT_CLIENT_STATIC_TACT_KEYS_INCOMPLETE"]
        ),
    }


def audit_current_client_progression_evidence(
    *,
    mythic_plus_seasons: Any,
    mythic_plus_reward_levels: Any,
    renown_rewards: Any,
    item_bonus_seasons: Any,
) -> dict[str, Any]:
    """Bound current-client progression evidence without inventing joins.

    The official client tables expose useful current-expansion facts, but they
    do not themselves bind one Mythic+ season row to the public season name,
    publish current end-of-run reward levels, or resolve Midnight Renown power
    unlocks to vendor item IDs.  This audit preserves those boundaries.
    """

    seasons = _rows(mythic_plus_seasons, "Mythic+ seasons")
    rewards = _rows(
        mythic_plus_reward_levels,
        "Mythic+ reward levels",
    )
    renown = _rows(renown_rewards, "Renown rewards")
    bonus_seasons = _rows(item_bonus_seasons, "item bonus seasons")

    expansion_season_ids = {
        _positive_id(row.get("id"), "Mythic+ season")
        for row in seasons
        if _nonnegative_int(
            row.get("id_expansion"),
            "Mythic+ expansion",
        )
        == 11
    }
    reward_season_ids = {
        _positive_id(
            row.get("id_mythic_plus_season"),
            "Mythic+ reward season",
        )
        for row in rewards
    }
    candidate_season_ids = sorted(
        expansion_season_ids.intersection(reward_season_ids),
        key=int,
    )
    candidate_season_id = (
        candidate_season_ids[0]
        if len(candidate_season_ids) == 1
        else None
    )

    weekly_by_key: dict[int, dict[str, int]] = {}
    if candidate_season_id:
        for row in rewards:
            if (
                _text(row.get("id_mythic_plus_season"))
                != candidate_season_id
                or _text(row.get("id_activity_tier")) != "103"
            ):
                continue
            key_level = _nonnegative_int(
                row.get("difficulty_level"),
                "Mythic+ key level",
            )
            if key_level < 2 or key_level > 10:
                continue
            if key_level in weekly_by_key:
                raise ClientRelationEvidenceError(
                    f"duplicate Mythic+ key level {key_level}"
                )
            weekly_by_key[key_level] = {
                "keyLevel": key_level,
                "weeklyRewardItemLevel": _nonnegative_int(
                    row.get("weekly_reward_level"),
                    f"Mythic+ {key_level} weekly reward",
                ),
                "endOfRunRewardItemLevel": _nonnegative_int(
                    row.get("end_of_run_reward_level"),
                    f"Mythic+ {key_level} end-of-run reward",
                ),
            }
    weekly_rows = [weekly_by_key[key] for key in sorted(weekly_by_key)]

    current_renown = []
    for row in renown:
        raw_covenant_id = _text(row.get("id_covenant"))
        if not raw_covenant_id.isdigit():
            continue
        if int(raw_covenant_id) in _MIDNIGHT_RENOWN_IDS:
            current_renown.append(row)
    power_unlocks = [
        row
        for row in current_renown
        if _text(row.get("desc2")) in _MIDNIGHT_POWER_RENOWN_LABELS
        and "powerful" in _text(row.get("desc")).casefold()
        and "level 90" in _text(row.get("desc")).casefold()
    ]
    power_unlocks.sort(key=lambda row: int(_positive_id(row.get("id"), "Renown reward")))
    delve_unlocks = [
        row
        for row in current_renown
        if _text(row.get("desc2")) in _MIDNIGHT_DELVE_PROGRESSION_LABELS
    ]
    resolved_power_item_count = sum(
        1
        for row in power_unlocks
        if _text(row.get("id_item")).isdigit()
        and int(_text(row.get("id_item"))) > 0
    )

    blockers = {
        "CURRENT_CLIENT_MYTHIC_PLUS_SEASON_AUTHORITY_JOIN_UNAVAILABLE",
    }
    if set(weekly_by_key) != set(range(2, 11)):
        blockers.add(
            "CURRENT_CLIENT_MYTHIC_PLUS_WEEKLY_REWARD_LADDER_INCOMPLETE"
        )
    if any(
        row["endOfRunRewardItemLevel"] == 0
        for row in weekly_rows
    ):
        blockers.add(
            "CURRENT_CLIENT_DIRECT_RUN_REWARD_LEVEL_UNAVAILABLE"
        )
    if (
        not power_unlocks
        or resolved_power_item_count != len(power_unlocks)
    ):
        blockers.add(
            "CURRENT_CLIENT_RENOWN_POWER_ITEM_ID_UNAVAILABLE"
        )

    return {
        "status": "blocked" if blockers else "complete",
        "mythicPlus": {
            "expansionSeasonIds": sorted(expansion_season_ids, key=int),
            "candidateSeasonIds": candidate_season_ids,
            "candidateSeasonId": candidate_season_id,
            "keyLevelCount": len(weekly_rows),
            "weeklyRewardRows": weekly_rows,
        },
        "renown": {
            "currentRewardRowCount": len(current_renown),
            "powerUnlockCount": len(power_unlocks),
            "resolvedPowerItemCount": resolved_power_item_count,
            "delveProgressionUnlockCount": len(delve_unlocks),
            "powerUnlocks": [
                {
                    "rewardId": _text(row.get("id")),
                    "renownId": _text(row.get("id_covenant")),
                    "renownLevel": _nonnegative_int(
                        row.get("level"),
                        "Renown level",
                    ),
                    "name": _text(row.get("name")),
                    "description": _text(row.get("desc")),
                    "itemId": _text(row.get("id_item")),
                }
                for row in power_unlocks
            ],
        },
        "itemBonusSeason": {
            "rowCount": len(bonus_seasons),
            "displaySeasonIds": sorted(
                {
                    _positive_id(
                        row.get("id_season"),
                        "item bonus display season",
                    )
                    for row in bonus_seasons
                },
                key=int,
            ),
        },
        "blockers": sorted(blockers),
    }


def audit_unverified_source_membership_relations(
    *,
    collectable_vendor: Any,
    collectable_source_info: Any,
    item_modified_appearances: Any,
    quest_package_items: Any,
    official_items: Any,
    unparsed_encrypted_record_count: Any = 0,
) -> dict[str, Any]:
    """Audit unverified source relation candidates without promotion."""

    vendor_rows = _rows(collectable_vendor, "collectable vendor")
    source_rows = _rows(
        collectable_source_info,
        "collectable source info",
    )
    appearance_rows = _rows(
        item_modified_appearances,
        "item modified appearances",
    )
    package_rows = _rows(quest_package_items, "quest package items")
    official_rows = _rows(official_items, "official items")
    encrypted_record_count = _nonnegative_int(
        unparsed_encrypted_record_count,
        "unparsed encrypted source record count",
    )

    def unique_index(
        rows: list[dict[str, Any]],
        key: str,
        label: str,
    ) -> dict[str, dict[str, Any]]:
        indexed = {}
        for row in rows:
            row_id = _positive_id(row.get(key), label)
            if row_id in indexed:
                raise ClientRelationEvidenceError(
                    f"duplicate {label} {row_id}"
                )
            indexed[row_id] = row
        return indexed

    source_by_id = unique_index(
        source_rows,
        "id",
        "collectable source info",
    )
    appearance_by_id = unique_index(
        appearance_rows,
        "id",
        "item modified appearance",
    )
    official_by_id = unique_index(
        official_rows,
        "itemId",
        "official item",
    )

    vendor_candidates_by_item: dict[str, dict[str, Any]] = {}
    missing_source_info_count = 0
    missing_appearance_count = 0
    vendor_missing_official_item_count = 0
    for row in vendor_rows:
        vendor_id = _positive_id(row.get("id"), "collectable vendor")
        source_info_id = _nonnegative_int(
            row.get("id_parent"),
            f"collectable vendor {vendor_id} parent",
        )
        if source_info_id == 0:
            missing_source_info_count += 1
            continue
        source_info = source_by_id.get(str(source_info_id))
        if not source_info:
            missing_source_info_count += 1
            continue
        appearance_id = _nonnegative_int(
            source_info.get(
                "unverified_item_modified_appearance_id"
            ),
            f"collectable source info {source_info_id} appearance",
        )
        if appearance_id == 0:
            missing_appearance_count += 1
            continue
        appearance = appearance_by_id.get(str(appearance_id))
        if not appearance:
            missing_appearance_count += 1
            continue
        item_id = _positive_id(
            appearance.get("id_item"),
            f"item modified appearance {appearance_id}",
        )
        official_item = official_by_id.get(item_id)
        if not official_item:
            vendor_missing_official_item_count += 1
            continue
        candidate = vendor_candidates_by_item.setdefault(
            item_id,
            {
                "itemId": item_id,
                "name": _text(official_item.get("name")),
                "requiredLevel": _nonnegative_int(
                    official_item.get("requiredLevel", 0),
                    f"official item {item_id} required level",
                ),
                "sourceKeys": list(
                    official_item.get("sourceKeys") or []
                ),
                "sourceTypes": list(
                    official_item.get("sourceTypes") or []
                ),
                "candidateStatus": _text(
                    official_item.get("candidateStatus")
                ),
                "outcome": "unverified_not_promotable",
                "relations": [],
            },
        )
        candidate["relations"].append(
            {
                "collectableVendorId": vendor_id,
                "collectableSourceInfoId": str(source_info_id),
                "itemModifiedAppearanceId": str(appearance_id),
                "unverifiedSourceTypeEnum": _text(
                    source_info.get("unverified_source_type_enum")
                ),
            }
        )

    quest_candidates_by_item: dict[str, dict[str, Any]] = {}
    quest_missing_official_item_count = 0
    for row in package_rows:
        relation_id = _positive_id(row.get("id"), "quest package item")
        item_id = _positive_id(
            row.get("item_id"),
            f"quest package item {relation_id}",
        )
        official_item = official_by_id.get(item_id)
        if not official_item:
            quest_missing_official_item_count += 1
            continue
        candidate = quest_candidates_by_item.setdefault(
            item_id,
            {
                "itemId": item_id,
                "name": _text(official_item.get("name")),
                "requiredLevel": _nonnegative_int(
                    official_item.get("requiredLevel", 0),
                    f"official item {item_id} required level",
                ),
                "sourceKeys": list(
                    official_item.get("sourceKeys") or []
                ),
                "sourceTypes": list(
                    official_item.get("sourceTypes") or []
                ),
                "candidateStatus": _text(
                    official_item.get("candidateStatus")
                ),
                "outcome": "unverified_not_promotable",
                "relations": [],
            },
        )
        candidate["relations"].append(
            {
                "questPackageItemId": relation_id,
                "packageId": _positive_id(
                    row.get("package_id"),
                    f"quest package item {relation_id} package",
                ),
                "itemQuantity": _nonnegative_int(
                    row.get("item_quantity"),
                    f"quest package item {relation_id} quantity",
                ),
                "displayType": _nonnegative_int(
                    row.get("display_type"),
                    f"quest package item {relation_id} display type",
                ),
            }
        )

    vendor_candidates = sorted(
        vendor_candidates_by_item.values(),
        key=lambda row: int(row["itemId"]),
    )
    quest_candidates = sorted(
        quest_candidates_by_item.values(),
        key=lambda row: int(row["itemId"]),
    )
    blockers = [
        "CURRENT_QUEST_PACKAGE_RELATION_UNAVAILABLE",
        "CURRENT_SEASON_PVE_VENDOR_IDENTITY_UNAVAILABLE",
        "THIRD_PARTY_SCHEMA_FIELDS_UNVERIFIED",
    ]
    return {
        "status": "blocked",
        "summary": {
            "promotableMemberCount": 0,
            "unparsedEncryptedRecordCount": encrypted_record_count,
            "vendorRecordCount": len(vendor_rows),
            "vendorCandidateItemCount": len(vendor_candidates),
            "vendorCurrentLevelCandidateItemCount": sum(
                row["requiredLevel"] == 90
                for row in vendor_candidates
            ),
            "vendorMissingSourceInfoCount": (
                missing_source_info_count
            ),
            "vendorMissingAppearanceCount": missing_appearance_count,
            "vendorMissingOfficialItemCount": (
                vendor_missing_official_item_count
            ),
            "questPackageRecordCount": len(package_rows),
            "questPackageCandidateItemCount": len(quest_candidates),
            "questPackageCurrentLevelCandidateItemCount": sum(
                row["requiredLevel"] == 90
                for row in quest_candidates
            ),
            "questPackageMissingOfficialItemCount": (
                quest_missing_official_item_count
            ),
        },
        "vendorCandidates": vendor_candidates,
        "questPackageCandidates": quest_candidates,
        "blockers": sorted(
            [
                *blockers,
                *(
                    [
                        "CURRENT_CLIENT_ENCRYPTED_SOURCE_RECORDS_UNAVAILABLE"
                    ]
                    if encrypted_record_count
                    else []
                ),
            ]
        ),
    }


def classify_client_item_equip_eligibility(
    item_row: Any,
    item_sparse_row: Any,
) -> dict[str, Any]:
    """Classify one current-client item using both authoritative item tables."""

    if not isinstance(item_row, dict) or not isinstance(
        item_sparse_row,
        dict,
    ):
        raise ClientRelationEvidenceError(
            "item eligibility requires Item and ItemSparse rows"
        )
    item_id = _positive_id(item_row.get("id"), "Item row")
    sparse_item_id = _positive_id(
        item_sparse_row.get("id"),
        "ItemSparse row",
    )
    if item_id != sparse_item_id:
        raise ClientRelationEvidenceError(
            f"item id mismatch {item_id}:{sparse_item_id}"
        )
    item_class_id = _nonnegative_int(
        item_row.get("classs"),
        f"item {item_id} class",
    )
    inventory_type_id = _nonnegative_int(
        item_row.get("type_inv"),
        f"item {item_id} inventory type",
    )
    sparse_inventory_type_id = _nonnegative_int(
        item_sparse_row.get("inv_type"),
        f"item {item_id} sparse inventory type",
    )
    if inventory_type_id != sparse_inventory_type_id:
        raise ClientRelationEvidenceError(
            f"item {item_id} inventory type mismatch "
            f"{inventory_type_id}:{sparse_inventory_type_id}"
        )
    if item_class_id not in _COMBAT_ITEM_CLASS_IDS:
        is_combat_equippable = False
        reason_code = "CURRENT_CLIENT_NON_COMBAT_ITEM_CLASS"
    elif inventory_type_id not in _COMBAT_INVENTORY_TYPE_IDS:
        is_combat_equippable = False
        reason_code = "CURRENT_CLIENT_NON_COMBAT_INVENTORY_TYPE"
    else:
        is_combat_equippable = True
        reason_code = "CURRENT_CLIENT_COMBAT_EQUIPMENT"
    return {
        "itemId": item_id,
        "itemClassId": item_class_id,
        "inventoryTypeId": inventory_type_id,
        "isCombatEquippable": is_combat_equippable,
        "reasonCode": reason_code,
    }


def classify_current_client_crafted_candidate(
    member: Any,
    item_row: Any,
    item_sparse_row: Any,
    noncombat_skill_line_ids: Iterable[Any],
) -> dict[str, Any]:
    """Apply current-season PVE exclusions to one crafted output relation."""

    if not isinstance(member, dict):
        raise ClientRelationEvidenceError(
            "crafted candidate member must be an object"
        )
    recipe_id = _positive_id(member.get("recipeId"), "crafted recipe")
    member_item_id = _positive_id(
        member.get("itemId"),
        f"recipe {recipe_id} item",
    )
    equip = classify_client_item_equip_eligibility(
        item_row,
        item_sparse_row,
    )
    if equip["itemId"] != member_item_id:
        raise ClientRelationEvidenceError(
            f"recipe {recipe_id} item relation mismatch"
        )
    if isinstance(noncombat_skill_line_ids, (str, bytes, dict)):
        raise ClientRelationEvidenceError(
            "noncombat skill line ids must be a collection"
        )
    try:
        noncombat_skill_lines = {
            _positive_id(skill_line_id, "noncombat skill line")
            for skill_line_id in noncombat_skill_line_ids
        }
    except TypeError as error:
        raise ClientRelationEvidenceError(
            "noncombat skill line ids must be iterable"
        ) from error

    name = _text(item_sparse_row.get("name"))
    item_level = _nonnegative_int(
        item_sparse_row.get("ilevel"),
        f"item {member_item_id} level",
    )
    required_skill_id = _nonnegative_int(
        item_sparse_row.get("req_skill"),
        f"item {member_item_id} required skill",
    )
    has_combat_stats = any(
        (
            _text(item_sparse_row.get(f"stat_type_{index}"))
            not in {"", "-1", "0"}
        )
        or _nonnegative_int(
            item_sparse_row.get(f"stat_alloc_{index}", 0),
            f"item {member_item_id} stat allocation {index}",
        )
        > 0
        for index in range(1, 11)
    )
    if not equip["isCombatEquippable"]:
        outcome = "excluded"
        reason_code = equip["reasonCode"]
    elif "competitor" in name.casefold():
        outcome = "excluded"
        reason_code = "CURRENT_CLIENT_PVP_CRAFTED_OUTPUT"
    elif (
        required_skill_id > 0
        and str(required_skill_id) in noncombat_skill_lines
    ):
        outcome = "excluded"
        reason_code = "CURRENT_CLIENT_PROFESSION_UTILITY_EQUIPMENT"
    elif item_level <= 1 and not has_combat_stats:
        outcome = "excluded"
        reason_code = "CURRENT_CLIENT_NO_COMBAT_POWER"
    else:
        outcome = "included"
        reason_code = "CURRENT_CLIENT_SEASON_PVE_CRAFTED_OUTPUT"
    return {
        **equip,
        "recipeId": recipe_id,
        "name": name,
        "itemLevel": item_level,
        "requiredSkillLineId": required_skill_id,
        "hasCombatStats": has_combat_stats,
        "outcome": outcome,
        "reasonCode": reason_code,
    }


def select_midnight_profession_spell_targets(
    skill_lines: Any,
    skill_line_abilities: Any,
    profession_names: Any,
) -> list[dict[str, str]]:
    """Select every current expansion ability for named crafting professions."""

    lines = _rows(skill_lines, "skill lines")
    abilities = _rows(skill_line_abilities, "skill line abilities")
    if isinstance(profession_names, (str, bytes, dict)):
        raise ClientRelationEvidenceError(
            "profession names must be a collection"
        )
    try:
        professions = [_text(name) for name in profession_names]
    except TypeError as error:
        raise ClientRelationEvidenceError(
            "profession names must be iterable"
        ) from error
    if (
        not professions
        or any(not name for name in professions)
        or len(set(professions)) != len(professions)
    ):
        raise ClientRelationEvidenceError(
            "profession names must be unique and non-empty"
        )

    skill_line_by_profession = {}
    for profession in professions:
        expected_name = f"Midnight {profession}"
        matches = [
            row for row in lines if _text(row.get("name")) == expected_name
        ]
        if len(matches) != 1:
            raise ClientRelationEvidenceError(
                f"{expected_name} has {len(matches)} skill line rows"
            )
        skill_line_by_profession[
            _positive_id(matches[0].get("id"), expected_name)
        ] = profession

    targets = []
    seen_recipe_ids = set()
    matched_professions = set()
    for row in abilities:
        skill_line_id = _text(row.get("id_skill_up"))
        profession = skill_line_by_profession.get(skill_line_id)
        if not profession:
            continue
        recipe_id = _positive_id(
            row.get("id"),
            f"{profession} skill line ability",
        )
        spell_id = _positive_id(
            row.get("id_spell"),
            f"recipe {recipe_id}",
        )
        if recipe_id in seen_recipe_ids:
            raise ClientRelationEvidenceError(
                f"duplicate recipe id {recipe_id}"
            )
        seen_recipe_ids.add(recipe_id)
        matched_professions.add(profession)
        targets.append(
            {
                "profession": profession,
                "skillLineId": skill_line_id,
                "recipeId": recipe_id,
                "spellId": spell_id,
            }
        )
    missing_professions = sorted(set(professions) - matched_professions)
    if missing_professions:
        raise ClientRelationEvidenceError(
            "no current skill line abilities for "
            + ",".join(missing_professions)
        )
    return sorted(targets, key=lambda row: int(row["recipeId"]))


def resolve_crafted_recipe_outputs(
    spell_targets: Any,
    spell_effects: Any,
    crafting_data: Any,
    crafting_data_item_quality: Any,
    equippable_item_ids: Iterable[Any],
) -> dict[str, Any]:
    """Resolve type-288 crafting spells to current equippable output items."""

    targets = _rows(spell_targets, "spell targets")
    effects = _rows(spell_effects, "spell effects")
    crafting_rows = _rows(crafting_data, "crafting data")
    quality_rows = _rows(
        crafting_data_item_quality,
        "crafting data item quality",
    )
    if isinstance(equippable_item_ids, (str, bytes, dict)):
        raise ClientRelationEvidenceError(
            "equippable item ids must be a collection"
        )
    try:
        equippable = {
            _positive_id(item_id, "equippable item")
            for item_id in equippable_item_ids
        }
    except TypeError as error:
        raise ClientRelationEvidenceError(
            "equippable item ids must be iterable"
        ) from error

    effects_by_spell: dict[str, list[dict[str, Any]]] = {}
    for effect in effects:
        if _text(effect.get("type")) != "288":
            continue
        spell_id = _positive_id(
            effect.get("id_parent"),
            "type-288 spell effect parent",
        )
        effects_by_spell.setdefault(spell_id, []).append(effect)

    crafting_by_id: dict[str, dict[str, Any]] = {}
    for row in crafting_rows:
        crafting_id = _positive_id(row.get("id"), "crafting data")
        if crafting_id in crafting_by_id:
            raise ClientRelationEvidenceError(
                f"duplicate crafting data id {crafting_id}"
            )
        crafting_by_id[crafting_id] = row

    quality_by_parent: dict[str, list[str]] = {}
    for row in quality_rows:
        parent_id = _positive_id(
            row.get("id_parent"),
            "crafting quality parent",
        )
        item_id = _positive_id(
            row.get("id_item"),
            f"crafting quality {parent_id}",
        )
        quality_by_parent.setdefault(parent_id, []).append(item_id)

    members = []
    type_288_spell_count = 0
    equippable_recipe_ids = set()
    seen_targets = set()
    for target in targets:
        recipe_id = _positive_id(target.get("recipeId"), "spell target")
        spell_id = _positive_id(
            target.get("spellId"),
            f"recipe {recipe_id}",
        )
        target_identity = (recipe_id, spell_id)
        if target_identity in seen_targets:
            raise ClientRelationEvidenceError(
                f"duplicate recipe spell target {recipe_id}:{spell_id}"
            )
        seen_targets.add(target_identity)
        matching_effects = effects_by_spell.get(spell_id, [])
        if not matching_effects:
            continue
        type_288_spell_count += 1
        if len(matching_effects) != 1:
            raise ClientRelationEvidenceError(
                f"recipe {recipe_id} has "
                f"{len(matching_effects)} type-288 effects"
            )
        effect = matching_effects[0]
        effect_id = _positive_id(
            effect.get("id"),
            f"recipe {recipe_id} spell effect",
        )
        crafting_id = _positive_id(
            effect.get("misc_value_1"),
            f"recipe {recipe_id} crafting data",
        )
        crafting_row = crafting_by_id.get(crafting_id)
        if not crafting_row:
            raise ClientRelationEvidenceError(
                f"recipe {recipe_id} references missing crafting data "
                f"{crafting_id}"
            )
        outputs = []
        crafted_item_id = _text(crafting_row.get("id_crafted_item"))
        if crafted_item_id and crafted_item_id != "0":
            outputs.append((crafted_item_id, "crafted_item"))
        outputs.extend(
            (item_id, "quality_item")
            for item_id in quality_by_parent.get(crafting_id, [])
        )
        seen_output_ids = set()
        for item_id, output_kind in outputs:
            resolved_item_id = _positive_id(
                item_id,
                f"recipe {recipe_id} output",
            )
            if (
                resolved_item_id not in equippable
                or resolved_item_id in seen_output_ids
            ):
                continue
            seen_output_ids.add(resolved_item_id)
            equippable_recipe_ids.add(recipe_id)
            members.append(
                {
                    "itemId": resolved_item_id,
                    "profession": _text(target.get("profession")),
                    "recipeId": recipe_id,
                    "skillLineId": _positive_id(
                        target.get("skillLineId"),
                        f"recipe {recipe_id} skill line",
                    ),
                    "spellId": spell_id,
                    "spellEffectId": effect_id,
                    "craftingDataId": crafting_id,
                    "outputKind": output_kind,
                }
            )

    members.sort(
        key=lambda row: (int(row["recipeId"]), int(row["itemId"]))
    )
    return {
        "summary": {
            "targetSpellCount": len(targets),
            "type288SpellCount": type_288_spell_count,
            "equippableRecipeCount": len(equippable_recipe_ids),
            "equippableItemCount": len(
                {row["itemId"] for row in members}
            ),
        },
        "members": members,
    }


def compare_crafted_recipe_membership(
    official_api_recipes: Any,
    current_client_members: Any,
) -> dict[str, Any]:
    """Compare API recipe membership with resolved current-client membership."""

    api_rows = _rows(official_api_recipes, "official API recipes")
    client_rows = _rows(
        current_client_members,
        "current client crafted members",
    )
    api_ids = {
        _positive_id(row.get("recipeId"), "official API recipe")
        for row in api_rows
    }
    client_ids = {
        _positive_id(row.get("recipeId"), "current client recipe")
        for row in client_rows
    }
    api_only = sorted(api_ids - client_ids, key=int)
    client_only = sorted(client_ids - api_ids, key=int)
    return {
        "status": (
            "matched" if not api_only and not client_only else "mismatched"
        ),
        "officialApiRecipeCount": len(api_ids),
        "currentClientRecipeCount": len(client_ids),
        "sharedRecipeCount": len(api_ids & client_ids),
        "officialApiOnlyRecipeIds": api_only,
        "currentClientOnlyRecipeIds": client_only,
    }

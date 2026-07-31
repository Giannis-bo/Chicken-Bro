#!/usr/bin/env python3

import argparse
import hashlib
import json
import re
import struct
from datetime import datetime, timezone
from pathlib import Path


HEX_16_RE = re.compile(r"^[0-9a-f]{16}$")
HEX_32_RE = re.compile(r"^[0-9a-f]{32}$")
XFTH_HEADER = struct.Struct("<4sII32s")
XFTH_ENTRY_V9 = struct.Struct("<4siiIIIIB3s")
TACT_KEY_TABLE_HASH = 0xDF2F53CF
TACT_KEY_LOOKUP_TABLE_HASH = 0xAFC190D1
BROADCAST_TEXT_TABLE_HASH = 0x021826BB
MODELED_RECORD_STATES = {1, 2, 3, 4}
RECOGNIZED_TABLE_NAMES = {
    TACT_KEY_TABLE_HASH: "TactKey",
    TACT_KEY_LOOKUP_TABLE_HASH: "TactKeyLookup",
    BROADCAST_TEXT_TABLE_HASH: "BroadcastText",
}


def _file_evidence(path):
    payload = path.read_bytes()
    return {
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _wdc5_to_blte_key_id(tact_key_id):
    if not HEX_16_RE.fullmatch(tact_key_id):
        raise ValueError(f"invalid WDC5 TACT key identity: {tact_key_id!r}")
    return bytes.fromhex(tact_key_id)[::-1].hex()


def _parse_cache_header(cache_path, expected_build):
    with cache_path.open("rb") as handle:
        payload = handle.read(XFTH_HEADER.size)
    if len(payload) != XFTH_HEADER.size:
        raise ValueError("DBCache.bin is shorter than the XFTH header")
    magic, version, build, verify_hash = XFTH_HEADER.unpack(payload)
    if magic != b"XFTH":
        raise ValueError(f"invalid DBCache.bin magic: {magic!r}")
    if version < 1:
        raise ValueError(f"invalid DBCache.bin version: {version}")
    if build != expected_build:
        raise ValueError(
            f"DBCache.bin build {build} does not match expected build "
            f"{expected_build}"
        )
    return {
        "magic": "XFTH",
        "version": version,
        "build": build,
        "verifyHashSha256": hashlib.sha256(verify_hash).hexdigest(),
    }


def scan_xfth_target_keys(
    payload,
    *,
    expected_build,
    target_blte_key_ids,
    base_key_material_record_ids=None,
    base_lookup_by_record_id=None,
):
    if len(payload) < XFTH_HEADER.size:
        raise ValueError("DBCache.bin is shorter than the XFTH header")
    magic, version, build, verify_hash = XFTH_HEADER.unpack_from(payload)
    if magic != b"XFTH":
        raise ValueError(f"invalid DBCache.bin magic: {magic!r}")
    if version < 9:
        raise ValueError(
            f"lightweight target scan requires XFTH version 9+, got {version}"
        )
    if build != expected_build:
        raise ValueError(
            f"DBCache.bin build {build} does not match expected build "
            f"{expected_build}"
        )
    normalized_targets = set()
    for key_id in target_blte_key_ids:
        normalized = str(key_id).lower()
        if not HEX_16_RE.fullmatch(normalized):
            raise ValueError(f"invalid target BLTE key identity: {key_id!r}")
        normalized_targets.add(normalized)

    key_material_record_ids = set(base_key_material_record_ids or ())
    lookup_by_record_id = dict(base_lookup_by_record_id or {})
    broadcast_text_key_by_record_id = {}
    target_table_entry_count = 0
    broadcast_text_entry_count = 0
    broadcast_text_tact_key_entry_count = 0
    parsed_entry_count = 0
    unrecognized_table_entry_count = 0
    record_state_counts = {}
    recognized_table_record_state_counts = {
        table_name: {}
        for table_name in sorted(RECOGNIZED_TABLE_NAMES.values())
    }
    unmodeled_record_state_count = 0
    offset = XFTH_HEADER.size
    while offset < len(payload):
        if len(payload) - offset < XFTH_ENTRY_V9.size:
            raise ValueError("truncated XFTH entry header")
        (
            entry_magic,
            _region_id,
            _index,
            _unique_id,
            table_hash,
            record_id,
            length,
            state,
            _padding,
        ) = XFTH_ENTRY_V9.unpack_from(payload, offset)
        if entry_magic != b"XFTH":
            raise ValueError(
                f"invalid XFTH entry magic at offset {offset}: "
                f"{entry_magic!r}"
            )
        offset += XFTH_ENTRY_V9.size
        end_offset = offset + length
        if end_offset > len(payload):
            raise ValueError("truncated XFTH entry payload")
        entry_payload = payload[offset:end_offset]
        offset = end_offset

        parsed_entry_count += 1
        state_key = str(state)
        record_state_counts[state_key] = (
            record_state_counts.get(state_key, 0) + 1
        )
        if state not in MODELED_RECORD_STATES:
            unmodeled_record_state_count += 1
        table_name = RECOGNIZED_TABLE_NAMES.get(table_hash)
        if table_name is None:
            unrecognized_table_entry_count += 1
        else:
            table_state_counts = recognized_table_record_state_counts[
                table_name
            ]
            table_state_counts[state_key] = (
                table_state_counts.get(state_key, 0) + 1
            )

        if table_hash == TACT_KEY_TABLE_HASH:
            target_table_entry_count += 1
            if state == 1:
                if length != 16:
                    raise ValueError(
                        f"TactKey hotfix record has length {length}, expected 16"
                    )
                key_material_record_ids.add(record_id)
            else:
                key_material_record_ids.discard(record_id)
        elif table_hash == TACT_KEY_LOOKUP_TABLE_HASH:
            target_table_entry_count += 1
            if state == 1:
                if length != 8:
                    raise ValueError(
                        "TactKeyLookup hotfix record has length "
                        f"{length}, expected 8"
                    )
                lookup_by_record_id[record_id] = entry_payload.hex()
            else:
                lookup_by_record_id.pop(record_id, None)
        elif table_hash == BROADCAST_TEXT_TABLE_HASH:
            broadcast_text_entry_count += 1
            if state != 1:
                broadcast_text_key_by_record_id.pop(record_id, None)
                continue
            if length < 28:
                broadcast_text_key_by_record_id.pop(record_id, None)
                continue
            optional_data = entry_payload[-28:]
            extra_table_hash = struct.unpack_from("<I", optional_data)[0]
            if extra_table_hash != TACT_KEY_TABLE_HASH:
                broadcast_text_key_by_record_id.pop(record_id, None)
                continue
            key_id = struct.unpack_from("<Q", optional_data, 4)[0]
            broadcast_text_key_by_record_id[record_id] = f"{key_id:016x}"
            broadcast_text_tact_key_entry_count += 1

    joined_key_ids = {
        key_id
        for record_id, key_id in lookup_by_record_id.items()
        if record_id in key_material_record_ids
    }
    broadcast_text_key_ids = set(broadcast_text_key_by_record_id.values())
    available_key_ids = joined_key_ids | broadcast_text_key_ids
    return {
        "header": {
            "magic": "XFTH",
            "version": version,
            "build": build,
            "verifyHashSha256": hashlib.sha256(verify_hash).hexdigest(),
        },
        "targetTableEntryCount": target_table_entry_count,
        "parsedEntryCount": parsed_entry_count,
        "unrecognizedTableEntryCount": unrecognized_table_entry_count,
        "recordStateCounts": record_state_counts,
        "recognizedTableRecordStateCounts": (
            recognized_table_record_state_counts
        ),
        "unmodeledRecordStateCount": unmodeled_record_state_count,
        "joinedHotfixKeyCount": len(joined_key_ids),
        "broadcastTextEntryCount": broadcast_text_entry_count,
        "broadcastTextTactKeyEntryCount": (
            broadcast_text_tact_key_entry_count
        ),
        "broadcastTextEffectiveTactKeyRecordCount": len(
            broadcast_text_key_by_record_id
        ),
        "broadcastTextCarriedMaterialKeyCount": len(
            broadcast_text_key_ids
        ),
        "availableKeyIdentityCount": len(available_key_ids),
        "presentTargetBlteKeyIds": sorted(
            available_key_ids & normalized_targets
        ),
    }


def _available_key_ids(generated_rows):
    if not isinstance(generated_rows, list):
        raise ValueError("generated TACT-key output must be a JSON list")
    available = set()
    for row in generated_rows:
        if not isinstance(row, dict):
            raise ValueError("generated TACT-key row must be an object")
        key_id = str(row.get("key_id") or "").lower()
        key = row.get("key")
        if key is None:
            continue
        key = str(key).lower()
        if not HEX_16_RE.fullmatch(key_id):
            raise ValueError(
                f"generated TACT-key row has invalid key_id: {key_id!r}"
            )
        if not HEX_32_RE.fullmatch(key):
            raise ValueError(
                f"generated TACT-key row has invalid key material length"
            )
        available.add(key_id)
    return available


def build_audit(
    *,
    cache_path,
    generated_key_path,
    static_coverage_audit_path,
    expected_build,
    source_url,
    source_etag,
    source_generation,
    source_last_modified,
):
    cache_path = Path(cache_path)
    generated_key_path = Path(generated_key_path)
    static_coverage_audit_path = Path(static_coverage_audit_path)

    cache_header = _parse_cache_header(cache_path, expected_build)
    static_audit = _load_json(static_coverage_audit_path)
    if not str(static_audit.get("build", "")).endswith(
        f".{expected_build}"
    ):
        raise ValueError("static coverage audit build does not match expected build")
    target_rows = static_audit.get("coverage", {}).get("targetKeys")
    if not isinstance(target_rows, list) or not target_rows:
        raise ValueError("static coverage audit has no target keys")

    generated_rows = _load_json(generated_key_path)
    available_blte_ids = _available_key_ids(generated_rows)
    audited_targets = []
    seen_target_ids = set()
    for row in target_rows:
        tact_key_id = str(row.get("tactKeyId") or "").lower()
        if tact_key_id in seen_target_ids:
            raise ValueError(f"duplicate target TACT key identity: {tact_key_id}")
        seen_target_ids.add(tact_key_id)
        record_count = row.get("recordCount")
        if not isinstance(record_count, int) or record_count < 1:
            raise ValueError(
                f"invalid recordCount for target TACT key {tact_key_id}"
            )
        tables = row.get("tables")
        if (
            not isinstance(tables, list)
            or not tables
            or not all(isinstance(table, str) and table for table in tables)
        ):
            raise ValueError(f"invalid tables for target TACT key {tact_key_id}")
        blte_key_id = _wdc5_to_blte_key_id(tact_key_id)
        audited_targets.append(
            {
                "tactKeyId": tact_key_id,
                "blteKeyId": blte_key_id,
                "recordCount": record_count,
                "tables": sorted(set(tables)),
                "presentInVerifiedDBCache": (
                    blte_key_id in available_blte_ids
                ),
            }
        )

    target_record_count = sum(row["recordCount"] for row in audited_targets)
    present_targets = [
        row for row in audited_targets if row["presentInVerifiedDBCache"]
    ]
    covered_record_count = sum(
        row["recordCount"] for row in present_targets
    )
    missing_key_count = len(audited_targets) - len(present_targets)
    if missing_key_count == 0:
        status = "complete"
        blockers = []
    elif present_targets:
        status = "partial"
        blockers = ["VERIFIED_DBCACHE_TACT_KEYS_INCOMPLETE"]
    else:
        status = "blocked"
        blockers = ["VERIFIED_DBCACHE_TACT_KEYS_UNAVAILABLE"]

    return {
        "schemaVersion": 1,
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "build": f"12.0.7.{expected_build}",
        "authority": {
            "type": "verified_third_party_client_hotfix_cache",
            "provider": "Raidbots",
            "upstreamBytes": (
                "Blizzard server-delivered World of Warcraft client hotfix cache"
            ),
            "collectionProvenance": "third_party",
            "mayEstablishOfficialSeasonMembership": False,
            "auditContainsKeyMaterial": False,
            "ephemeralGeneratedOutputContainsKeyMaterial": True,
            "rawCleanupRequired": True,
        },
        "source": {
            "url": source_url,
            "etag": source_etag,
            "generation": source_generation,
            "lastModified": source_last_modified,
        },
        "inputs": {
            "DBCache.bin": {
                **_file_evidence(cache_path),
                "header": cache_header,
            },
            "ephemeralGeneratedTactKeys": {
                **_file_evidence(generated_key_path),
                "persistedAfterAudit": False,
            },
            "staticCoverageAudit": {
                **_file_evidence(static_coverage_audit_path),
                "path": static_coverage_audit_path.name,
            },
        },
        "coverage": {
            "status": status,
            "summary": {
                "availableKeyMaterialCount": len(available_blte_ids),
                "targetKeyCount": len(audited_targets),
                "targetRecordCount": target_record_count,
                "availableTargetKeyCount": len(present_targets),
                "missingTargetKeyCount": missing_key_count,
                "coveredTargetRecordCount": covered_record_count,
                "missingTargetRecordCount": (
                    target_record_count - covered_record_count
                ),
            },
            "targetKeys": audited_targets,
            "blockers": blockers,
        },
        "conclusion": (
            "the exact-build verified DBCache covers every target TACT key"
            if status == "complete"
            else (
                "the exact-build verified DBCache covers only part of the "
                "target TACT-key set"
                if status == "partial"
                else "the exact-build verified DBCache covers no target TACT key"
            )
        ),
        "productionMutation": False,
        "releasePointerMutation": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--generated-keys", required=True, type=Path)
    parser.add_argument("--static-coverage-audit", required=True, type=Path)
    parser.add_argument("--expected-build", required=True, type=int)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-etag", required=True)
    parser.add_argument("--source-generation", required=True)
    parser.add_argument("--source-last-modified", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    audit = build_audit(
        cache_path=args.cache,
        generated_key_path=args.generated_keys,
        static_coverage_audit_path=args.static_coverage_audit,
        expected_build=args.expected_build,
        source_url=args.source_url,
        source_etag=args.source_etag,
        source_generation=args.source_generation,
        source_last_modified=args.source_last_modified,
    )
    args.output.write_text(
        json.dumps(audit, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = audit["coverage"]["summary"]
    print(
        json.dumps(
            {
                "status": audit["status"],
                "availableTargetKeyCount": summary[
                    "availableTargetKeyCount"
                ],
                "missingTargetKeyCount": summary["missingTargetKeyCount"],
                "coveredTargetRecordCount": summary[
                    "coveredTargetRecordCount"
                ],
                "missingTargetRecordCount": summary[
                    "missingTargetRecordCount"
                ],
            },
            sort_keys=True,
        )
    )
    raise SystemExit(0 if audit["status"] == "complete" else 2)


if __name__ == "__main__":
    main()

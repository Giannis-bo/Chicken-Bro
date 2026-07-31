"""Deterministic projection of raw official PVE evidence into a blocked ledger.

The Blizzard Game Data API exposes several useful raw memberships, but it does
not expose every acquisition pool, Journal difficulty membership, progression
state, or crafted recipe output item id. This module records what the official
responses do prove and keeps every missing join literal instead of upgrading a
partial graph to a verified SeasonPveUniverse.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit, urlunsplit

from server.season_pve_official_capture import (
    OfficialCaptureContractError,
    canonical_official_name,
    validate_official_item_range_page,
)


EVIDENCE_SCHEMA_REVISION = "season-pve-official-evidence-v1"


class OfficialEvidenceError(ValueError):
    """Raised when raw evidence cannot be projected deterministically."""


_JOURNAL_GROUP_SOURCE = {
    "midnight_dungeon": "dungeon:midnight-season-1-heroic-mythic0",
    "midnight_world_boss": "world_boss:midnight-season-1-core",
    "mythic_plus": "mythic_plus:midnight-season-1",
    "timewalking": "timewalking_event:turbulent-timeways-revelations",
}

_SIMC_ITEM_ROW = re.compile(
    r'^\s*\{\s*("(?:[^"\\]|\\.)*")\s*,\s*(\d+)\s*,'
)
_SOURCE_RELATION_AUDIT_TABLES = {
    "ChallengeModeReward",
    "ChallengeModeXReward",
    "CollectableSourceInfo",
    "CollectableSourceVendor",
    "CollectableSourceVendorSparse",
    "CreatureDifficultyTreasure",
    "InitiativeReward",
    "ItemAppearance",
    "ItemModifiedAppearance",
    "QuestPackageItem",
}
_SOURCE_RELATION_MEMBERSHIP_CHAIN_TABLES = {
    "CollectableSourceInfo",
    "CollectableSourceVendor",
    "CollectableSourceVendorSparse",
    "ItemModifiedAppearance",
}
_SOURCE_RELATION_AUDIT_BLOCKERS = {
    "CURRENT_CLIENT_ENCRYPTED_SOURCE_RECORDS_UNAVAILABLE",
    "CURRENT_QUEST_PACKAGE_RELATION_UNAVAILABLE",
    "CURRENT_SEASON_PVE_VENDOR_IDENTITY_UNAVAILABLE",
    "THIRD_PARTY_SCHEMA_FIELDS_UNVERIFIED",
}
_PUBLIC_TACT_KEY_SOURCE = (
    "wowdev/TACTKeys@"
    "a3449fd5cfc3a0053cbff2c65f7d16166774cbf9"
)
_PUBLIC_TACT_KEY_REEXTRACT_BLOCKERS = {
    "APPROVED_PUBLIC_TACT_KEYS_INCOMPLETE",
    "CURRENT_CLIENT_BLTE_DECRYPTION_KEYS_UNAVAILABLE",
    "CURRENT_CLIENT_ENCRYPTED_SOURCE_RECORDS_UNAVAILABLE",
}
_TACT_KEY_UPSTREAM_SOURCE_BLOCKERS = {
    "APPROVED_PUBLIC_TACT_KEYS_INCOMPLETE",
    "CURRENT_CLIENT_DBCACHE_CORPUS_TACT_KEYS_INCOMPLETE",
    "CURRENT_CLIENT_ENCRYPTED_SOURCE_RECORDS_UNAVAILABLE",
}
_TACT_KEY_UPSTREAM_MISSING_IDS = {
    "14f4b11d7b067aa2",
    "62bf37a70e6d54f6",
    "fbbf041f980ce0dc",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def authority_identity(value: Any) -> str:
    """Normalize an authority URL without erasing Blizzard article identity."""

    raw = _text(value)
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise OfficialEvidenceError("authority reference requires an HTTP URL")
    article_match = re.search(r"/news/(\d+)(?:/|$)", parsed.path)
    if article_match:
        return f"blizzard-news:{article_match.group(1)}"
    normalized_path = parsed.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            normalized_path,
            "",
            "",
        )
    )


def official_response_namespaces(payload: Any) -> list[str]:
    """Collect namespace query values embedded in one official response."""

    namespaces = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)
            return
        if not isinstance(value, str) or "namespace=" not in value:
            return
        parsed = urlsplit(value)
        for namespace in parse_qs(parsed.query).get("namespace", []):
            resolved = _text(namespace)
            if resolved:
                namespaces.add(resolved)

    visit(payload)
    return sorted(namespaces)


def client_build_from_namespace(value: Any) -> str:
    """Return the client build encoded by a versioned static namespace."""

    namespace = _text(value)
    match = re.fullmatch(
        r"static-\d+\.\d+\.\d+_(\d+)-[a-z]+",
        namespace,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else ""


def client_build_from_simc_version(value: Any) -> str:
    """Return the WoW client build declared by a SimulationCraft version."""

    match = re.search(
        r"World of Warcraft\s+\d+\.\d+\.\d+\.(\d+)\b",
        _text(value),
    )
    return match.group(1) if match else ""


def verify_current_client_public_tact_key_reextract_audit(
    payload: Any,
    *,
    expected_encrypted_record_count: int,
) -> dict[str, Any]:
    """Verify that public-key re-extraction did not hide missing records."""

    if (
        not isinstance(payload, dict)
        or payload.get("schemaVersion") != 1
        or payload.get("status") not in {"blocked", "partial"}
        or not re.fullmatch(
            r"\d+\.\d+\.\d+\.\d+",
            _text(payload.get("build")),
        )
        or payload.get("productionMutation") is not False
        or payload.get("releasePointerMutation") is not False
    ):
        raise OfficialEvidenceError(
            "public TACT-key re-extraction audit identity is invalid"
        )
    authority = payload.get("authority")
    if (
        not isinstance(authority, dict)
        or authority.get("recordTactKeyIdentitySource")
        != _PUBLIC_TACT_KEY_SOURCE
        or authority.get("blteKeyIdentitySource")
        != "Blizzard retail CDN BLTE chunks"
        or authority.get(
            "recordAndBlteKeyIdentityByteOrderMapped"
        )
        is not True
        or authority.get("recordBytes") != "Blizzard retail CDN"
        or authority.get("keyMaterialEmitted") is not False
        or authority.get("duplicateOfficialDb2PayloadsPersisted")
        is not False
    ):
        raise OfficialEvidenceError(
            "public TACT-key re-extraction authority boundary is invalid"
        )
    audit = payload.get("reextractAudit")
    summary = audit.get("summary") if isinstance(audit, dict) else None
    if (
        not isinstance(expected_encrypted_record_count, int)
        or isinstance(expected_encrypted_record_count, bool)
        or expected_encrypted_record_count < 1
        or not isinstance(summary, dict)
        or audit.get("status") not in {"blocked", "partial"}
        or set(audit.get("blockers") or [])
        != _PUBLIC_TACT_KEY_REEXTRACT_BLOCKERS
    ):
        raise OfficialEvidenceError(
            "public TACT-key re-extraction blocker is invalid"
        )
    integer_fields = (
        "tableCount",
        "changedTableCount",
        "recordTactKeyCount",
        "publicRecordTactKeyCount",
        "missingRecordTactKeyCount",
        "publicRecordTactKeyCoveredRecordCount",
        "recordTactKeyToBlteKeyOverlapCount",
        "blteKeyCount",
        "blteEncryptedChunkCount",
        "blteKeyAvailableChunkCount",
        "blteDecryptedChunkCount",
        "blteZeroFallbackChunkCount",
        "targetEncryptedRecordCount",
        "recoveredEncryptedRecordCount",
        "unavailableEncryptedRecordCount",
    )
    if any(
        not isinstance(summary.get(field), int)
        or isinstance(summary.get(field), bool)
        or summary[field] < 0
        for field in integer_fields
    ):
        raise OfficialEvidenceError(
            "public TACT-key re-extraction counts are invalid"
        )
    recovered_record_count = summary[
        "recoveredEncryptedRecordCount"
    ]
    unavailable_record_count = summary[
        "unavailableEncryptedRecordCount"
    ]
    expected_status = (
        "partial" if recovered_record_count else "blocked"
    )
    if (
        summary["tableCount"] != 4
        or summary["changedTableCount"]
        != (4 if recovered_record_count else 0)
        or summary["recordTactKeyCount"] < 1
        or summary["publicRecordTactKeyCount"] < 1
        or summary["missingRecordTactKeyCount"] < 1
        or summary["publicRecordTactKeyCount"]
        + summary["missingRecordTactKeyCount"]
        != summary["recordTactKeyCount"]
        or summary["publicRecordTactKeyCoveredRecordCount"] < 1
        or summary["publicRecordTactKeyCoveredRecordCount"]
        >= expected_encrypted_record_count
        or summary["recordTactKeyToBlteKeyOverlapCount"]
        != summary["recordTactKeyCount"]
        or summary["blteKeyCount"] < 1
        or summary["blteEncryptedChunkCount"]
        < summary["blteKeyCount"]
        or summary["blteKeyAvailableChunkCount"]
        != summary["blteDecryptedChunkCount"]
        or summary["blteDecryptedChunkCount"] < 0
        or summary["blteDecryptedChunkCount"]
        > summary["blteEncryptedChunkCount"]
        or summary["blteZeroFallbackChunkCount"]
        != summary["blteEncryptedChunkCount"]
        - summary["blteDecryptedChunkCount"]
        or summary["targetEncryptedRecordCount"]
        != expected_encrypted_record_count
        or recovered_record_count
        != summary["publicRecordTactKeyCoveredRecordCount"]
        or recovered_record_count + unavailable_record_count
        != expected_encrypted_record_count
        or unavailable_record_count < 1
        or payload["status"] != expected_status
        or audit["status"] != expected_status
    ):
        raise OfficialEvidenceError(
            "public TACT-key re-extraction must retain every "
            "unavailable encrypted record"
        )
    return {
        "status": expected_status,
        "build": payload["build"],
        "source": _PUBLIC_TACT_KEY_SOURCE,
        "recordTactKeyCount": summary["recordTactKeyCount"],
        "publicRecordTactKeyCount": summary[
            "publicRecordTactKeyCount"
        ],
        "missingRecordTactKeyCount": summary[
            "missingRecordTactKeyCount"
        ],
        "publicRecordTactKeyCoveredRecordCount": summary[
            "publicRecordTactKeyCoveredRecordCount"
        ],
        "recordTactKeyToBlteKeyOverlapCount": summary[
            "recordTactKeyToBlteKeyOverlapCount"
        ],
        "blteKeyCount": summary["blteKeyCount"],
        "blteEncryptedChunkCount": summary[
            "blteEncryptedChunkCount"
        ],
        "blteKeyAvailableChunkCount": summary[
            "blteKeyAvailableChunkCount"
        ],
        "blteDecryptedChunkCount": summary[
            "blteDecryptedChunkCount"
        ],
        "blteZeroFallbackChunkCount": summary[
            "blteZeroFallbackChunkCount"
        ],
        "recoveredEncryptedRecordCount": recovered_record_count,
        "unavailableEncryptedRecordCount": unavailable_record_count,
        "blockers": sorted(_PUBLIC_TACT_KEY_REEXTRACT_BLOCKERS),
    }


def verify_current_client_tact_key_upstream_input_files(
    inputs: Any,
    *,
    snapshot_root: Path,
) -> dict[str, dict[str, Any]]:
    """Verify that every upstream source input still matches its file."""

    expected_sources = {
        "currentPublicTactKeys",
        "verifiedDBCacheCorpus",
        "unverifiedDBCacheCorpus",
    }
    if not isinstance(inputs, dict) or set(inputs) != expected_sources:
        raise OfficialEvidenceError(
            "TACT-key upstream source input files are incomplete"
        )
    root = Path(snapshot_root).resolve()

    def _verify_file(evidence: Any, label: str):
        relative_text = (
            _text(evidence.get("path"))
            if isinstance(evidence, dict)
            else ""
        )
        relative_path = Path(relative_text)
        resolved_path = (root / relative_path).resolve()
        if (
            not relative_text
            or relative_path.is_absolute()
            or not resolved_path.is_relative_to(root)
            or not resolved_path.is_file()
        ):
            raise OfficialEvidenceError(
                f"TACT-key upstream source input file is invalid: {label}"
            )
        payload = resolved_path.read_bytes()
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if (
            evidence.get("bytes") != len(payload)
            or evidence.get("sha256") != actual_sha256
        ):
            raise OfficialEvidenceError(
                f"TACT-key upstream source input file drifted: {label}"
            )
        return payload, {
            "relativePath": resolved_path.relative_to(root).as_posix(),
            "bytes": len(payload),
            "sha256": actual_sha256,
        }

    verified = {}
    for source_name in sorted(expected_sources):
        evidence = inputs.get(source_name)
        payload, verified[source_name] = _verify_file(evidence, source_name)
        if source_name == "currentPublicTactKeys":
            continue
        try:
            component = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OfficialEvidenceError(
                "TACT-key upstream source component is invalid: "
                f"{source_name}"
            ) from error
        source_list = (
            component.get("sourceList")
            if isinstance(component, dict)
            else None
        )
        _, source_list_verified = _verify_file(
            source_list,
            f"{source_name}.sourceList",
        )
        verified[source_name]["sourceList"] = source_list_verified
    return verified


def verify_current_client_tact_key_upstream_source_audit(
    payload: Any,
    *,
    expected_encrypted_record_count: int,
    snapshot_root: Path | None = None,
) -> dict[str, Any]:
    """Verify that current public and cache key sources remain incomplete."""

    if (
        not isinstance(payload, dict)
        or payload.get("schemaVersion") != 1
        or payload.get("status") != "partial"
        or payload.get("build") != "12.0.7.68887"
        or payload.get("productionMutation") is not False
        or payload.get("releasePointerMutation") is not False
    ):
        raise OfficialEvidenceError(
            "TACT-key upstream source audit identity is invalid"
        )
    authority = payload.get("authority")
    if (
        not isinstance(authority, dict)
        or authority.get("scope")
        != "current public TACTKeys plus exact-build DBCache corpora"
        or authority.get("tactKeysObservedHead")
        != _PUBLIC_TACT_KEY_SOURCE.rsplit("@", 1)[-1]
        or authority.get("dbcacheCollectionProvenance") != "third_party"
        or authority.get("mayEstablishOfficialSeasonMembership") is not False
        or authority.get("auditContainsKeyMaterial") is not False
        or authority.get(
            "rawKeyOrCacheMaterialPersistedAfterAudit"
        )
        is not False
    ):
        raise OfficialEvidenceError(
            "TACT-key upstream source authority boundary is invalid"
        )
    inputs = payload.get("inputs")
    if (
        not isinstance(inputs, dict)
        or set(inputs)
        != {
            "currentPublicTactKeys",
            "verifiedDBCacheCorpus",
            "unverifiedDBCacheCorpus",
        }
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get("bytes"), int)
            or isinstance(item.get("bytes"), bool)
            or item["bytes"] < 1
            or not re.fullmatch(r"[0-9a-f]{64}", _text(item.get("sha256")))
            for item in inputs.values()
        )
    ):
        raise OfficialEvidenceError(
            "TACT-key upstream source audit inputs are invalid"
        )
    if snapshot_root is None:
        raise OfficialEvidenceError(
            "TACT-key upstream source snapshot root is required"
        )
    verify_current_client_tact_key_upstream_input_files(
        inputs,
        snapshot_root=snapshot_root,
    )
    root = Path(snapshot_root).resolve()
    input_documents = {}
    for source_name, evidence in inputs.items():
        try:
            input_documents[source_name] = json.loads(
                (root / evidence["path"]).read_bytes()
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OfficialEvidenceError(
                "TACT-key upstream source component is invalid: "
                f"{source_name}"
            ) from error

    def _component_target_state(
        source_name: str,
        *,
        section_name: str,
        presence_name: str,
    ) -> dict[str, tuple[str, int, bool]]:
        document = input_documents[source_name]
        section = (
            document.get(section_name)
            if isinstance(document, dict)
            else None
        )
        rows = section.get("targetKeys") if isinstance(section, dict) else None
        if not isinstance(rows, list) or len(rows) != 12:
            raise OfficialEvidenceError(
                "TACT-key upstream source component target ledger is invalid: "
                f"{source_name}"
            )
        result = {}
        for row in rows:
            tact_key_id = _text(row.get("tactKeyId"))
            state = (
                _text(row.get("blteKeyId")),
                row.get("recordCount"),
                row.get(presence_name),
            )
            if (
                not re.fullmatch(r"[0-9a-f]{16}", tact_key_id)
                or tact_key_id in result
                or not re.fullmatch(r"[0-9a-f]{16}", state[0])
                or not isinstance(state[1], int)
                or isinstance(state[1], bool)
                or state[1] < 1
                or not isinstance(state[2], bool)
            ):
                raise OfficialEvidenceError(
                    "TACT-key upstream source component target row is invalid: "
                    f"{source_name}"
                )
            result[tact_key_id] = state
        return result

    component_target_states = {
        "currentPublicTactKeys": _component_target_state(
            "currentPublicTactKeys",
            section_name="coverage",
            presence_name="presentInCurrentPublicSnapshot",
        ),
        "verifiedDBCacheCorpus": _component_target_state(
            "verifiedDBCacheCorpus",
            section_name="corpus",
            presence_name="presentInCorpusUnion",
        ),
        "unverifiedDBCacheCorpus": _component_target_state(
            "unverifiedDBCacheCorpus",
            section_name="corpus",
            presence_name="presentInCorpusUnion",
        ),
    }
    coverage = payload.get("coverage")
    summary = coverage.get("summary") if isinstance(coverage, dict) else None
    if (
        not isinstance(expected_encrypted_record_count, int)
        or isinstance(expected_encrypted_record_count, bool)
        or expected_encrypted_record_count < 1
        or not isinstance(summary, dict)
        or coverage.get("status") != "partial"
        or set(coverage.get("blockers") or [])
        != _TACT_KEY_UPSTREAM_SOURCE_BLOCKERS
    ):
        raise OfficialEvidenceError(
            "TACT-key upstream source blocker is invalid"
        )
    expected_summary = {
        "targetKeyCount": 12,
        "targetRecordCount": expected_encrypted_record_count,
        "sourceUnionAvailableTargetKeyCount": 9,
        "sourceUnionMissingTargetKeyCount": 3,
        "sourceUnionCoveredTargetRecordCount": 114,
        "sourceUnionMissingTargetRecordCount": 64,
        "dbcacheAddsTargetKeyBeyondCurrentPublicCount": 0,
    }
    if any(summary.get(key) != value for key, value in expected_summary.items()):
        raise OfficialEvidenceError(
            "TACT-key upstream source summary is invalid"
        )
    target_rows = coverage.get("targetKeys")
    if not isinstance(target_rows, list) or len(target_rows) != 12:
        raise OfficialEvidenceError(
            "TACT-key upstream target ledger is incomplete"
        )
    seen_ids = set()
    public_ids = set()
    verified_cache_ids = set()
    unverified_cache_ids = set()
    union_ids = set()
    target_record_count = 0
    covered_record_count = 0
    for row in target_rows:
        tact_key_id = _text(row.get("tactKeyId"))
        blte_key_id = _text(row.get("blteKeyId"))
        source_presence = row.get("sourcePresence")
        record_count = row.get("recordCount")
        if (
            not re.fullmatch(r"[0-9a-f]{16}", tact_key_id)
            or tact_key_id in seen_ids
            or not re.fullmatch(
                r"[0-9a-f]{16}",
                blte_key_id,
            )
            or not isinstance(record_count, int)
            or isinstance(record_count, bool)
            or record_count < 1
            or not isinstance(source_presence, dict)
            or set(source_presence)
            != {
                "currentPublicTactKeys",
                "verifiedDBCacheCorpus",
                "unverifiedDBCacheCorpus",
            }
            or any(
                not isinstance(value, bool)
                for value in source_presence.values()
            )
            or row.get("presentInSourceUnion")
            != any(source_presence.values())
        ):
            raise OfficialEvidenceError(
                "TACT-key upstream target row is invalid"
            )
        if any(
            component_target_states[source_name].get(tact_key_id)
            != (blte_key_id, record_count, source_presence[source_name])
            for source_name in component_target_states
        ):
            raise OfficialEvidenceError(
                "TACT-key upstream target row does not match component files"
            )
        seen_ids.add(tact_key_id)
        target_record_count += record_count
        if source_presence["currentPublicTactKeys"]:
            public_ids.add(tact_key_id)
        if source_presence["verifiedDBCacheCorpus"]:
            verified_cache_ids.add(tact_key_id)
        if source_presence["unverifiedDBCacheCorpus"]:
            unverified_cache_ids.add(tact_key_id)
        if row["presentInSourceUnion"]:
            union_ids.add(tact_key_id)
            covered_record_count += record_count
    if (
        target_record_count != expected_encrypted_record_count
        or covered_record_count != 114
        or len(public_ids) != 9
        or len(verified_cache_ids) != 6
        or len(unverified_cache_ids) != 6
        or verified_cache_ids != unverified_cache_ids
        or not verified_cache_ids.issubset(public_ids)
        or union_ids != public_ids
        or seen_ids - union_ids != _TACT_KEY_UPSTREAM_MISSING_IDS
    ):
        raise OfficialEvidenceError(
            "TACT-key upstream source union is invalid"
        )
    source_results = payload.get("sourceResults")
    if not isinstance(source_results, dict) or set(source_results) != {
        "currentPublicTactKeys",
        "verifiedDBCacheCorpus",
        "unverifiedDBCacheCorpus",
    }:
        raise OfficialEvidenceError(
            "TACT-key upstream cache corpus summary is invalid"
        )
    public_summary = source_results.get("currentPublicTactKeys")
    verified_summary = (
        source_results.get("verifiedDBCacheCorpus")
    )
    unverified_summary = (
        source_results.get("unverifiedDBCacheCorpus")
    )
    public_component_summary = input_documents["currentPublicTactKeys"].get(
        "coverage", {}
    ).get("summary")
    verified_component_summary = input_documents[
        "verifiedDBCacheCorpus"
    ].get("corpus", {}).get("summary")
    unverified_component_summary = input_documents[
        "unverifiedDBCacheCorpus"
    ].get("corpus", {}).get("summary")
    public_keys = {
        "availableTargetKeyCount",
        "coveredTargetRecordCount",
    }
    corpus_keys = {
        "selectedCacheCount",
        "fetchedCacheCount",
        "failedCacheCount",
        "totalFetchedBytes",
        "broadcastTextEntryCount",
        "broadcastTextTactKeyEntryCount",
        "targetKeyCount",
        "targetRecordCount",
        "unionAvailableTargetKeyCount",
        "unionMissingTargetKeyCount",
        "unionCoveredTargetRecordCount",
        "unionMissingTargetRecordCount",
    }

    def _matches_component_summary(summary, component_summary, keys):
        return (
            isinstance(summary, dict)
            and set(summary) == keys
            and isinstance(component_summary, dict)
            and all(
                isinstance(summary[key], int)
                and not isinstance(summary[key], bool)
                and summary[key] >= 0
                and summary[key] == component_summary.get(key)
                for key in keys
            )
        )

    if (
        not _matches_component_summary(
            public_summary,
            public_component_summary,
            public_keys,
        )
        or not _matches_component_summary(
            verified_summary,
            verified_component_summary,
            corpus_keys,
        )
        or not _matches_component_summary(
            unverified_summary,
            unverified_component_summary,
            corpus_keys,
        )
        or verified_summary.get("selectedCacheCount") < 1
        or verified_summary.get("fetchedCacheCount")
        != verified_summary.get("selectedCacheCount")
        or verified_summary.get("failedCacheCount") != 0
        or verified_summary.get("unionAvailableTargetKeyCount") != 6
        or verified_summary.get("unionCoveredTargetRecordCount") != 82
        or unverified_summary.get("selectedCacheCount") < 1
        or unverified_summary.get("fetchedCacheCount")
        != unverified_summary.get("selectedCacheCount")
        or unverified_summary.get("failedCacheCount") != 0
        or unverified_summary.get("unionAvailableTargetKeyCount") != 6
        or unverified_summary.get("unionCoveredTargetRecordCount") != 82
    ):
        raise OfficialEvidenceError(
            "TACT-key upstream cache corpus summary is invalid"
        )
    return {
        "status": "partial",
        "build": payload["build"],
        "sourceUnionAvailableTargetKeyCount": 9,
        "sourceUnionMissingTargetKeyCount": 3,
        "sourceUnionCoveredTargetRecordCount": 114,
        "sourceUnionMissingTargetRecordCount": 64,
        "verifiedCacheCount": verified_summary["selectedCacheCount"],
        "unverifiedCacheCount": unverified_summary["selectedCacheCount"],
        "dbcacheAddsTargetKeyBeyondCurrentPublicCount": 0,
        "missingTactKeyIds": sorted(_TACT_KEY_UPSTREAM_MISSING_IDS),
        "blockers": sorted(_TACT_KEY_UPSTREAM_SOURCE_BLOCKERS),
    }


def verify_current_client_tact_key_coverage_audit(
    payload: Any,
    *,
    expected_encrypted_record_count: int,
) -> dict[str, Any]:
    """Verify that static client keys do not hide encrypted-record gaps."""

    if (
        not isinstance(payload, dict)
        or payload.get("schemaVersion") != 1
        or payload.get("status") != "blocked"
        or not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", _text(payload.get("build")))
        or payload.get("productionMutation") is not False
        or payload.get("releasePointerMutation") is not False
    ):
        raise OfficialEvidenceError(
            "current-client TACT-key audit identity is invalid"
        )
    authority = payload.get("authority")
    if (
        not isinstance(authority, dict)
        or authority.get("keyBytes")
        != "captured Blizzard retail client DB2"
        or authority.get("scope")
        != "static TactKey and TactKeyLookup tables only"
        or authority.get("keyMaterialEmitted") is not False
    ):
        raise OfficialEvidenceError(
            "current-client TACT-key authority boundary is invalid"
        )
    coverage = payload.get("coverage")
    summary = (
        coverage.get("summary")
        if isinstance(coverage, dict)
        else None
    )
    if (
        not isinstance(expected_encrypted_record_count, int)
        or isinstance(expected_encrypted_record_count, bool)
        or expected_encrypted_record_count < 1
        or not isinstance(summary, dict)
        or coverage.get("status") != "blocked"
        or "CURRENT_CLIENT_STATIC_TACT_KEYS_INCOMPLETE"
        not in set(coverage.get("blockers") or [])
        or summary.get("targetRecordCount")
        != expected_encrypted_record_count
        or summary.get("missingTargetRecordCount")
        != expected_encrypted_record_count
        or summary.get("coveredTargetRecordCount") != 0
        or summary.get("presentTargetKeyCount") != 0
        or not isinstance(summary.get("targetKeyCount"), int)
        or isinstance(summary.get("targetKeyCount"), bool)
        or summary["targetKeyCount"] < 1
        or summary.get("missingTargetKeyCount")
        != summary["targetKeyCount"]
    ):
        raise OfficialEvidenceError(
            "current-client static TACT keys do not preserve "
            "the encrypted-record blocker"
        )
    return {
        "status": "blocked",
        "build": payload["build"],
        "targetKeyCount": summary["targetKeyCount"],
        "presentTargetKeyCount": 0,
        "missingTargetKeyCount": summary["missingTargetKeyCount"],
        "coveredTargetRecordCount": 0,
        "missingTargetRecordCount": summary[
            "missingTargetRecordCount"
        ],
        "blockers": sorted(set(coverage.get("blockers") or [])),
    }


def verify_current_client_source_relations_audit(
    payload: Any,
    *,
    expected_gap_count: int,
) -> dict[str, Any]:
    """Verify that client relation candidates remain explicitly unpromoted."""

    if (
        not isinstance(payload, dict)
        or payload.get("schemaVersion") != 1
        or payload.get("status") != "blocked"
        or not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", _text(payload.get("build")))
    ):
        raise OfficialEvidenceError(
            "current-client source relation audit identity is invalid"
        )
    authority = payload.get("authority")
    if (
        not isinstance(authority, dict)
        or authority.get("recordBytes")
        != "captured Blizzard retail client DB2"
        or authority.get("schemaAid")
        != "pinned wowdev/WoWDBDefs definitions"
        or authority.get("schemaAidMayEstablishOfficialMembership") is not False
    ):
        raise OfficialEvidenceError(
            "current-client source relation authority boundary is invalid"
        )
    table_audits = payload.get("tableAudits")
    if (
        not isinstance(table_audits, dict)
        or set(table_audits) != _SOURCE_RELATION_AUDIT_TABLES
    ):
        raise OfficialEvidenceError(
            "current-client source relation table audit is incomplete"
        )
    encrypted_record_count = 0
    recovered_encrypted_record_count = 0
    for table, raw_audit in table_audits.items():
        audit = raw_audit if isinstance(raw_audit, dict) else {}
        counts = [
            audit.get("recordCount"),
            audit.get("unencryptedRecordCount"),
            audit.get("encryptedRecordCount"),
            audit.get("parserRecordCount"),
            audit.get("parserRecoveredEncryptedRecordCount"),
        ]
        if (
            any(
                not isinstance(count, int)
                or isinstance(count, bool)
                or count < 0
                for count in counts
            )
            or counts[0] != counts[1] + counts[2]
            or counts[3] < counts[1]
            or counts[3] > counts[0]
            or counts[4] != counts[3] - counts[1]
            or audit.get("parserCoveredUnencryptedRecords") is not True
            or audit.get("parserCoveredAvailableRecords") is not True
        ):
            raise OfficialEvidenceError(
                f"current-client source relation table audit is invalid: {table}"
            )
        if table in _SOURCE_RELATION_MEMBERSHIP_CHAIN_TABLES:
            encrypted_record_count += counts[2]
            recovered_encrypted_record_count += counts[4]
    relation_audit = payload.get("relationAudit")
    relation_summary = (
        relation_audit.get("summary")
        if isinstance(relation_audit, dict)
        else None
    )
    blockers = (
        set(relation_audit.get("blockers") or [])
        if isinstance(relation_audit, dict)
        else set()
    )
    if (
        not isinstance(relation_summary, dict)
        or relation_audit.get("status") != "blocked"
        or relation_summary.get("promotableMemberCount") != 0
        or not isinstance(
            relation_summary.get("unparsedEncryptedRecordCount"),
            int,
        )
        or isinstance(
            relation_summary.get("unparsedEncryptedRecordCount"),
            bool,
        )
        or relation_summary["unparsedEncryptedRecordCount"] < 1
        or relation_summary["unparsedEncryptedRecordCount"]
        != encrypted_record_count - recovered_encrypted_record_count
        or not _SOURCE_RELATION_AUDIT_BLOCKERS.issubset(blockers)
    ):
        raise OfficialEvidenceError(
            "current-client source relation promotion boundary is invalid"
        )
    gap_impact = payload.get("gapImpact")
    if (
        not isinstance(expected_gap_count, int)
        or isinstance(expected_gap_count, bool)
        or expected_gap_count < 1
        or not isinstance(gap_impact, dict)
        or gap_impact.get("beforeGapCount") != expected_gap_count
        or gap_impact.get("resolvedGapCount") != 0
        or gap_impact.get("afterGapCount") != expected_gap_count
    ):
        raise OfficialEvidenceError(
            "current-client source relation gap impact is not fail-closed"
        )
    promotion = payload.get("promotionDecision")
    if (
        not isinstance(promotion, dict)
        or promotion.get("promotedMemberCount") != 0
        or promotion.get("catalogMutation") is not False
        or payload.get("productionMutation") is not False
        or payload.get("releasePointerMutation") is not False
    ):
        raise OfficialEvidenceError(
            "current-client source relation audit mutated release state"
        )
    return {
        "status": "blocked",
        "build": payload["build"],
        "promotableMemberCount": 0,
        "encryptedRecordCount": encrypted_record_count,
        "recoveredEncryptedRecordCount": (
            recovered_encrypted_record_count
        ),
        "unparsedEncryptedRecordCount": relation_summary[
            "unparsedEncryptedRecordCount"
        ],
        "vendorCandidateItemCount": relation_summary.get(
            "vendorCandidateItemCount",
            0,
        ),
        "questPackageCandidateItemCount": relation_summary.get(
            "questPackageCandidateItemCount",
            0,
        ),
        "gapCount": expected_gap_count,
        "verifiedTableCount": len(table_audits),
        "blockers": sorted(blockers),
    }


def _verified_json_record(root: Path, record: Any, label: str) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise OfficialEvidenceError(f"{label} record must be an object")
    relative_path = _text(record.get("relativePath"))
    if not relative_path:
        raise OfficialEvidenceError(f"{label} record requires relativePath")
    resolved_root = root.resolve()
    path = (resolved_root / relative_path).resolve()
    if not path.is_relative_to(resolved_root) or not path.is_file():
        raise OfficialEvidenceError(
            f"{label} response missing or outside snapshot: {relative_path}"
        )
    if sha256_file(path) != _text(record.get("sha256")):
        raise OfficialEvidenceError(
            f"{label} checksum mismatch: {relative_path}"
        )
    if path.stat().st_size != record.get("bytes"):
        raise OfficialEvidenceError(
            f"{label} byte count mismatch: {relative_path}"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise OfficialEvidenceError(
            f"{label} is not valid JSON: {relative_path}"
        ) from error
    if not isinstance(payload, dict):
        raise OfficialEvidenceError(f"{label} payload must be an object")
    return payload


def verify_official_item_range_snapshot(
    snapshot_root: Any,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Verify cursor, checksum, and termination closure for an Item range."""

    root = Path(snapshot_root).expanduser().resolve()
    try:
        manifest = json.loads(
            (root / "capture-manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise OfficialEvidenceError(
            "official item range manifest is unavailable or invalid"
        ) from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("schemaRevision")
        != "season-pve-official-item-range-v1"
        or manifest.get("status") != "captured"
        or not isinstance(manifest.get("responses"), list)
        or not manifest["responses"]
    ):
        raise OfficialEvidenceError(
            "official item range manifest is incomplete"
        )
    summary = _verified_json_record(
        root,
        manifest.get("summary"),
        "official item range summary",
    )
    item_range = summary.get("range")
    if not isinstance(item_range, dict):
        raise OfficialEvidenceError(
            "official item range summary requires range"
        )
    start_id = item_range.get("startItemId")
    end_id = item_range.get("endItemId")
    if (
        not isinstance(start_id, int)
        or isinstance(start_id, bool)
        or not isinstance(end_id, int)
        or isinstance(end_id, bool)
        or start_id < 1
        or end_id < start_id
        or item_range.get("equippable") is not True
        or summary.get("itemIndexComplete") is not True
        or summary.get("sourceMembershipComplete") is not False
        or summary.get("membershipComplete") is not False
    ):
        raise OfficialEvidenceError(
            "official item range summary scope is incomplete"
        )
    capture_implementation = summary.get("captureImplementation")
    repository_root = Path(__file__).resolve().parents[1]
    expected_script_sha = sha256_file(
        repository_root / "scripts/capture-official-item-range.py"
    )
    expected_owner_sha = sha256_file(
        repository_root / "server/season_pve_official_capture.py"
    )
    if (
        not isinstance(capture_implementation, dict)
        or capture_implementation.get("schemaRevision")
        != "season-pve-official-item-range-v1"
        or capture_implementation.get("scriptSha256")
        != expected_script_sha
        or capture_implementation.get("validatorOwnerSha256")
        != expected_owner_sha
    ):
        raise OfficialEvidenceError(
            "official item range capture implementation does not match "
            "the exact-head verifier"
        )
    capture_limits = summary.get("captureLimits")
    if (
        not isinstance(capture_limits, dict)
        or not isinstance(capture_limits.get("pageSize"), int)
        or isinstance(capture_limits.get("pageSize"), bool)
        or capture_limits["pageSize"] < 1
        or capture_limits["pageSize"] > 1000
        or not isinstance(capture_limits.get("maxPages"), int)
        or isinstance(capture_limits.get("maxPages"), bool)
        or capture_limits["maxPages"] < 1
        or capture_limits["maxPages"] > 500
        or not isinstance(capture_limits.get("maxResponseBytes"), int)
        or isinstance(capture_limits.get("maxResponseBytes"), bool)
        or capture_limits["maxResponseBytes"] < 1024 * 1024
        or capture_limits["maxResponseBytes"] > 16 * 1024 * 1024
        or not isinstance(
            capture_limits.get("maxTotalResponseBytes"),
            int,
        )
        or isinstance(
            capture_limits.get("maxTotalResponseBytes"),
            bool,
        )
        or capture_limits["maxTotalResponseBytes"] < 1024 * 1024
        or capture_limits["maxTotalResponseBytes"] > 1024 * 1024 * 1024
        or not isinstance(capture_limits.get("minimumItemCount"), int)
        or isinstance(capture_limits.get("minimumItemCount"), bool)
        or capture_limits["minimumItemCount"] < 0
        or capture_limits["minimumItemCount"] > 1000000
        or not isinstance(capture_limits.get("delaySeconds"), (int, float))
        or isinstance(capture_limits.get("delaySeconds"), bool)
        or capture_limits["delaySeconds"] < 0
        or capture_limits["delaySeconds"] > 5
    ):
        raise OfficialEvidenceError(
            "official item range capture limits are invalid"
        )
    responses = manifest["responses"]
    manifest_response_paths = {
        _text(record.get("relativePath"))
        for record in responses
        if isinstance(record, dict)
    }
    raw_response_paths = {
        path.relative_to(root).as_posix()
        for path in (
            root / "raw/game-data/items/equippable-range"
        ).glob("cursor-*.json")
        if path.is_file()
    }
    if (
        summary.get("pages") != responses
        or summary.get("pageCount") != len(responses)
        or manifest.get("pageCount") != len(responses)
        or manifest.get("capturedAt") != summary.get("capturedAt")
        or manifest_response_paths != raw_response_paths
    ):
        raise OfficialEvidenceError(
            "official item range page manifest does not match summary"
        )

    item_index: dict[str, list[dict[str, Any]]] = {}
    seen_ids = set()
    response_namespaces = set()
    verified_bytes = 0
    expected_cursor = start_id
    terminal_seen = False
    for page_index, record in enumerate(responses):
        if (
            not isinstance(record, dict)
            or record.get("cursor") != expected_cursor
        ):
            raise OfficialEvidenceError(
                "official item range cursor chain is not contiguous"
            )
        payload = _verified_json_record(
            root,
            record,
            "official item range page",
        )
        try:
            validated = validate_official_item_range_page(
                payload,
                start_id=expected_cursor,
                end_id=end_id,
                expected_page_size=capture_limits["pageSize"],
            )
        except OfficialCaptureContractError as error:
            raise OfficialEvidenceError(str(error)) from error
        rows = validated["rows"]
        item_ids = [str(row["id"]) for row in rows]
        if (
            record.get("itemCount") != len(item_ids)
            or _text(record.get("firstItemId"))
            != (item_ids[0] if item_ids else "")
            or _text(record.get("lastItemId"))
            != (item_ids[-1] if item_ids else "")
            or record.get("resultCountCapped")
            is not validated["resultCountCapped"]
        ):
            raise OfficialEvidenceError(
                "official item range page metadata drifted"
            )
        duplicates = seen_ids & set(item_ids)
        if duplicates:
            raise OfficialEvidenceError(
                "official item range repeats item ids across cursors"
            )
        seen_ids.update(item_ids)
        for row in rows:
            localized_name = row.get("name")
            if isinstance(localized_name, dict):
                name = _text(
                    localized_name.get("en_US")
                    or localized_name.get("en_GB")
                    or next(iter(localized_name.values()), "")
                )
            else:
                name = _text(localized_name)
            canonical_name = canonical_official_name(name)
            if not canonical_name:
                raise OfficialEvidenceError(
                    "official item range row requires a localized name"
                )
            item_index.setdefault(canonical_name, []).append(row)
        response_namespaces.update(official_response_namespaces(payload))
        verified_bytes += record["bytes"]
        terminal_seen = validated["terminal"]
        if terminal_seen:
            if page_index != len(responses) - 1:
                raise OfficialEvidenceError(
                    "official item range continued after terminal page"
                )
        else:
            expected_cursor = validated["nextCursor"]

    if not terminal_seen:
        raise OfficialEvidenceError(
            "official item range did not prove terminal closure"
        )
    first_item_id = min(seen_ids, key=int) if seen_ids else ""
    last_item_id = max(seen_ids, key=int) if seen_ids else ""
    if (
        summary.get("itemCount") != len(seen_ids)
        or manifest.get("itemCount") != len(seen_ids)
        or summary.get("responseBytes") != verified_bytes
        or manifest.get("responseBytes") != verified_bytes
        or _text(summary.get("firstItemId")) != first_item_id
        or _text(summary.get("lastItemId")) != last_item_id
        or capture_limits["maxPages"] < len(responses)
        or capture_limits["maxTotalResponseBytes"] < verified_bytes
        or len(seen_ids) < capture_limits["minimumItemCount"]
    ):
        raise OfficialEvidenceError(
            "official item range aggregate counts drifted"
        )
    for rows in item_index.values():
        rows.sort(key=lambda row: int(row["id"]))
    namespaces = sorted(response_namespaces)
    return (
        {
            "status": "verified",
            "range": item_range,
            "verifiedPageCount": len(responses),
            "verifiedItemCount": len(seen_ids),
            "verifiedResponseBytes": verified_bytes,
            "responseNamespaces": namespaces,
            "staticClientBuilds": sorted(
                {
                    client_build_from_namespace(namespace)
                    for namespace in namespaces
                    if client_build_from_namespace(namespace)
                },
                key=int,
            ),
            "itemIndexComplete": True,
            "sourceMembershipComplete": False,
            "captureImplementationStatus": "matched",
            "captureImplementation": capture_implementation,
        },
        dict(sorted(item_index.items())),
    )


def index_simc_generated_item_data(lines: Any) -> dict[str, list[dict[str, str]]]:
    """Index the generated SimulationCraft client item table by exact name."""

    if isinstance(lines, str):
        source_lines = lines.splitlines()
    else:
        try:
            source_lines = list(lines)
        except TypeError as error:
            raise OfficialEvidenceError(
                "SimulationCraft item data must be text lines"
            ) from error
    indexed: dict[str, list[dict[str, str]]] = {}
    seen_ids = set()
    for line in source_lines:
        match = _SIMC_ITEM_ROW.match(str(line))
        if not match:
            continue
        try:
            name = json.loads(match.group(1))
        except json.JSONDecodeError as error:
            raise OfficialEvidenceError(
                "SimulationCraft item data contains an invalid item name"
            ) from error
        item_id = match.group(2)
        if item_id in seen_ids:
            raise OfficialEvidenceError(
                f"SimulationCraft item data has duplicate item id {item_id}"
            )
        seen_ids.add(item_id)
        indexed.setdefault(canonical_official_name(name), []).append(
            {
                "itemId": item_id,
                "name": name,
            }
        )
    if not indexed:
        raise OfficialEvidenceError(
            "SimulationCraft item data did not contain item rows"
        )
    for rows in indexed.values():
        rows.sort(key=lambda row: int(row["itemId"]))
    return dict(sorted(indexed.items()))


def journal_source_key(source_group: Any, instance_id: Any) -> str:
    """Map a captured Journal relation to one policy-owned acquisition source."""

    group = _text(source_group)
    resolved_instance = _text(instance_id)
    if group == "midnight_raid":
        return (
            "raid:sporefall"
            if resolved_instance == "1305"
            else "raid:midnight-season-1-core"
        )
    source_key = _JOURNAL_GROUP_SOURCE.get(group)
    if not source_key:
        raise OfficialEvidenceError(
            f"unsupported official Journal source group {group or 'missing'}"
        )
    return source_key


def _journal_raw_members(
    capture: dict[str, Any],
    capture_directory: str,
) -> dict[str, list[dict[str, Any]]]:
    journal = capture.get("journalCapture")
    contexts = journal.get("itemContexts") if isinstance(journal, dict) else None
    if not isinstance(contexts, dict):
        raise OfficialEvidenceError(
            "official capture requires journalCapture.itemContexts"
        )
    sources: dict[str, list[dict[str, Any]]] = {}
    seen = set()
    for item_id, raw_contexts in contexts.items():
        if not _text(item_id) or not isinstance(raw_contexts, list):
            raise OfficialEvidenceError("official Journal item context is malformed")
        for context in raw_contexts:
            row = context if isinstance(context, dict) else {}
            source_key = journal_source_key(
                row.get("sourceGroup"),
                row.get("instanceId"),
            )
            relation = {
                "itemId": _text(item_id),
                "instanceId": _text(row.get("instanceId")),
                "instanceName": _text(row.get("instanceName")),
                "encounterId": _text(row.get("encounterId")),
                "encounterName": _text(row.get("encounterName")),
                "lootRelationId": _text(row.get("lootRelationId")),
                "evidenceRef": (
                    f"{capture_directory}/raw/game-data/journal/encounters/"
                    f"{_text(row.get('encounterId'))}.json"
                    f"#loot-relation-{_text(row.get('lootRelationId'))}"
                ),
            }
            if not all(
                relation[field]
                for field in (
                    "itemId",
                    "instanceId",
                    "encounterId",
                    "lootRelationId",
                )
            ):
                raise OfficialEvidenceError(
                    "official Journal relation requires item, instance, "
                    "encounter, and loot-relation ids"
                )
            identity = (
                source_key,
                relation["itemId"],
                relation["instanceId"],
                relation["encounterId"],
                relation["lootRelationId"],
            )
            if identity in seen:
                raise OfficialEvidenceError(
                    "official Journal capture has a duplicate relation identity"
                )
            seen.add(identity)
            sources.setdefault(source_key, []).append(relation)
    for rows in sources.values():
        rows.sort(
            key=lambda row: (
                int(row["instanceId"]),
                int(row["encounterId"]),
                int(row["itemId"]),
                int(row["lootRelationId"]),
            )
        )
    return sources


def _gap(reason_code: str, boundary: str, evidence_ref: str) -> dict[str, str]:
    return {
        "reasonCode": reason_code,
        "boundary": boundary,
        "evidenceRef": evidence_ref,
    }


def _verified_current_client_crafted_members(
    evidence: Any,
    official_recipes: list[dict[str, Any]],
    evidence_ref: str,
) -> list[dict[str, Any]]:
    if not isinstance(evidence, dict):
        raise OfficialEvidenceError(
            "current-client crafted evidence must be an object"
        )
    included = evidence.get("included")
    excluded = evidence.get("excluded")
    summary = evidence.get("summary")
    comparison = evidence.get("officialApiComparison")
    if (
        evidence.get("status") != "complete"
        or evidence.get("scope")
        != "current_client_midnight_crafted_pve_combat_equipment"
        or not _text(evidence.get("build"))
        or not _text(evidence_ref)
        or not isinstance(included, list)
        or not isinstance(excluded, list)
        or not isinstance(summary, dict)
        or not isinstance(comparison, dict)
        or comparison.get("status") != "matched"
        or comparison.get("officialApiOnlyRecipeIds") != []
        or comparison.get("currentClientOnlyRecipeIds") != []
    ):
        raise OfficialEvidenceError(
            "current-client crafted evidence is incomplete"
        )
    if (
        summary.get("candidateItemCount") != len(included) + len(excluded)
        or summary.get("includedItemCount") != len(included)
        or summary.get("excludedItemCount") != len(excluded)
    ):
        raise OfficialEvidenceError(
            "current-client crafted evidence counts drifted"
        )

    official_by_recipe_id = {}
    for recipe in official_recipes:
        recipe_id = _text(recipe.get("recipeId"))
        if not recipe_id or recipe_id in official_by_recipe_id:
            raise OfficialEvidenceError(
                "official crafted recipes require unique recipe ids"
            )
        official_by_recipe_id[recipe_id] = recipe

    included_by_recipe_id = {}
    all_item_ids = set()
    for expected_outcome, rows in (
        ("included", included),
        ("excluded", excluded),
    ):
        for raw_row in rows:
            row = raw_row if isinstance(raw_row, dict) else {}
            item_id = _text(row.get("itemId"))
            recipe_id = _text(row.get("recipeId"))
            if (
                not item_id.isdigit()
                or int(item_id) < 1
                or not recipe_id.isdigit()
                or int(recipe_id) < 1
                or row.get("outcome") != expected_outcome
                or not _text(row.get("reasonCode"))
                or item_id in all_item_ids
            ):
                raise OfficialEvidenceError(
                    "current-client crafted member is malformed"
                )
            all_item_ids.add(item_id)
            if expected_outcome == "included":
                if recipe_id in included_by_recipe_id:
                    raise OfficialEvidenceError(
                        "current-client PVE recipe has multiple included outputs"
                    )
                included_by_recipe_id[recipe_id] = row

    official_recipe_ids = set(official_by_recipe_id)
    included_recipe_ids = set(included_by_recipe_id)
    if (
        official_recipe_ids != included_recipe_ids
        or summary.get("includedRecipeCount") != len(included_recipe_ids)
        or comparison.get("officialApiRecipeCount")
        != len(official_recipe_ids)
        or comparison.get("currentClientRecipeCount")
        != len(included_recipe_ids)
        or comparison.get("sharedRecipeCount")
        != len(official_recipe_ids)
    ):
        raise OfficialEvidenceError(
            "current-client crafted recipe membership drifted"
        )

    resolved = []
    for recipe_id in sorted(official_recipe_ids, key=int):
        official = official_by_recipe_id[recipe_id]
        current = included_by_recipe_id[recipe_id]
        item_id = _text(current.get("itemId"))
        resolved.append(
            {
                **official,
                "itemId": item_id,
                "itemName": _text(current.get("name")),
                "candidateItemIds": [item_id],
                "officialCandidateItemIds": sorted(
                    {
                        _text(candidate)
                        for candidate in (
                            official.get("officialCandidateItemIds")
                            or official.get("candidateItemIds")
                            or []
                        )
                        if _text(candidate)
                    },
                    key=int,
                ),
                "clientItemIds": [item_id],
                "candidateJoinMethod": (
                    "current_client_spell_effect_crafting_data"
                ),
                "membershipStatus": "verified_output_item",
                "clientBuild": _text(evidence.get("build")),
                "evidenceRef": f"{evidence_ref}#item={item_id}",
            }
        )
    return resolved


def _verified_current_client_journal_members(
    evidence: Any,
    official_members: dict[str, list[dict[str, Any]]],
    evidence_ref: str,
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(evidence, dict):
        raise OfficialEvidenceError(
            "current-client Journal evidence must be an object"
        )
    relations = evidence.get("relations")
    summary = evidence.get("summary")
    if (
        evidence.get("status") != "complete"
        or evidence.get("scope")
        != "current_client_journal_item_difficulty_relations"
        or not _text(evidence.get("clientBuild"))
        or not _text(evidence_ref)
        or not isinstance(relations, list)
        or not isinstance(summary, dict)
        or summary.get("relationCount") != len(relations)
    ):
        raise OfficialEvidenceError(
            "current-client Journal evidence is incomplete"
        )
    official_by_identity: dict[
        tuple[str, str, str, str], list[dict[str, Any]]
    ] = {}
    for source_key, members in official_members.items():
        for member in members:
            identity = (
                source_key,
                _text(member.get("instanceId")),
                _text(member.get("encounterId")),
                _text(member.get("itemId")),
            )
            official_by_identity.setdefault(identity, []).append(member)
    evidence_by_identity = {}
    for raw_relation in relations:
        relation = (
            raw_relation if isinstance(raw_relation, dict) else {}
        )
        identity = (
            _text(relation.get("sourceKey")),
            _text(relation.get("instanceId")),
            _text(relation.get("encounterId")),
            _text(relation.get("itemId")),
        )
        difficulty_keys = [
            _text(key)
            for key in relation.get("difficultyKeys") or []
            if _text(key)
        ]
        current_relation_ids = [
            _text(relation_id)
            for relation_id in relation.get(
                "currentClientRelationIds"
            )
            or []
            if _text(relation_id)
        ]
        official_relation_ids = {
            _text(relation_id)
            for relation_id in relation.get(
                "officialLootRelationIds"
            )
            or []
            if _text(relation_id)
        }
        if (
            not all(identity)
            or identity in evidence_by_identity
            or identity not in official_by_identity
            or not difficulty_keys
            or not current_relation_ids
            or relation.get("membershipStatus")
            != "verified_current_client_relation"
        ):
            raise OfficialEvidenceError(
                "current-client Journal relation is malformed or unowned"
            )
        expected_official_ids = {
            _text(member.get("lootRelationId"))
            for member in official_by_identity[identity]
        }
        if official_relation_ids != expected_official_ids:
            raise OfficialEvidenceError(
                "current-client Journal official relation ids drifted"
            )
        evidence_by_identity[identity] = relation
    if set(evidence_by_identity) != set(official_by_identity):
        raise OfficialEvidenceError(
            "current-client Journal relation membership drifted"
        )
    resolved: dict[str, list[dict[str, Any]]] = {}
    for identity, members in official_by_identity.items():
        relation = evidence_by_identity[identity]
        source_key = identity[0]
        resolved[source_key] = [
            *resolved.get(source_key, []),
            *[
                {
                    **member,
                    "difficultyKeys": list(
                        relation["difficultyKeys"]
                    ),
                    "currentClientRelationIds": list(
                        relation["currentClientRelationIds"]
                    ),
                    "membershipStatus": (
                        "verified_current_client_relation"
                    ),
                    "clientBuild": _text(
                        evidence.get("clientBuild")
                    ),
                    "clientRelationEvidenceRef": (
                        f"{evidence_ref}#source={source_key}"
                        f"&item={identity[3]}"
                        f"&encounter={identity[2]}"
                    ),
                }
                for member in members
            ],
        ]
    for rows in resolved.values():
        rows.sort(
            key=lambda row: (
                int(row["instanceId"]),
                int(row["encounterId"]),
                int(row["itemId"]),
                int(row["lootRelationId"]),
            )
        )
    return resolved


def build_official_membership_snapshot(
    policy: Any,
    capture: Any,
    *,
    captured_at: str,
    authority_manifest_ref: str,
    capture_ref: str,
    capture_directory: str,
    simc_item_index: dict[str, list[dict[str, str]]],
    simc_evidence_ref: str,
    client_crafted_membership: Any = None,
    client_crafted_evidence_ref: str = "",
    client_journal_membership: Any = None,
    client_journal_evidence_ref: str = "",
) -> dict[str, Any]:
    """Project official raw rows while preserving all unproven joins as gaps."""

    if not isinstance(policy, dict) or not isinstance(capture, dict):
        raise OfficialEvidenceError("policy and capture must be objects")
    policy_sources = policy.get("sources")
    if not isinstance(policy_sources, list) or not policy_sources:
        raise OfficialEvidenceError("policy requires sources")
    journal_members = _journal_raw_members(capture, capture_directory)
    verified_client_journal_members = (
        _verified_current_client_journal_members(
            client_journal_membership,
            journal_members,
            client_journal_evidence_ref,
        )
        if client_journal_membership is not None
        else None
    )
    profession = capture.get("professionCapture")
    recipes = profession.get("recipes") if isinstance(profession, dict) else None
    class_sets = capture.get("classSetCapture")
    sets = class_sets.get("sets") if isinstance(class_sets, dict) else None
    if (
        not isinstance(recipes, list)
        or not isinstance(sets, list)
        or not isinstance(simc_item_index, dict)
    ):
        raise OfficialEvidenceError(
            "official capture requires recipes, class sets, and SimC item index"
        )
    projected_recipes = []
    for raw_recipe in recipes:
        recipe = raw_recipe if isinstance(raw_recipe, dict) else {}
        if "competitor" in canonical_official_name(recipe.get("name")):
            continue
        official_candidate_ids = sorted(
            {
                _text(item_id)
                for item_id in recipe.get("candidateItemIds") or []
                if _text(item_id)
            },
            key=int,
        )
        simc_candidates = simc_item_index.get(
            canonical_official_name(recipe.get("name")),
            [],
        )
        simc_candidate_ids = [
            row["itemId"] for row in simc_candidates
        ]
        cross_source_candidate_ids = (
            sorted(
                set(official_candidate_ids) & set(simc_candidate_ids),
                key=int,
            )
            if official_candidate_ids
            else simc_candidate_ids
            if len(simc_candidate_ids) == 1
            else []
        )
        projected_recipes.append(
            {
                **recipe,
                "officialCandidateItemIds": official_candidate_ids,
                "simcClientCandidateItemIds": simc_candidate_ids,
                "candidateItemIds": cross_source_candidate_ids,
                "candidateJoinMethod": (
                    "official_and_simc_exact_name"
                    if official_candidate_ids
                    and cross_source_candidate_ids
                    else "simc_exact_name_unique"
                    if not official_candidate_ids
                    and len(simc_candidate_ids) == 1
                    else "cross_source_name_unresolved"
                ),
                "membershipStatus": "candidate_unproven",
                "simcEvidenceRef": simc_evidence_ref,
            }
        )
    verified_client_crafted_members = (
        _verified_current_client_crafted_members(
            client_crafted_membership,
            projected_recipes,
            client_crafted_evidence_ref,
        )
        if client_crafted_membership is not None
        else None
    )

    projected_sources = []
    for raw_policy_source in policy_sources:
        policy_source = (
            raw_policy_source if isinstance(raw_policy_source, dict) else {}
        )
        source_key = _text(policy_source.get("sourceKey"))
        if not source_key:
            raise OfficialEvidenceError("policy source requires sourceKey")
        raw_members = list(
            (
                verified_client_journal_members
                if verified_client_journal_members is not None
                else journal_members
            ).get(source_key)
            or []
        )
        gaps = []
        if raw_members:
            if verified_client_journal_members is None:
                gaps.append(
                    _gap(
                        "OFFICIAL_JOURNAL_DIFFICULTY_MEMBERSHIP_UNAVAILABLE",
                        "journal_relation_to_difficulty",
                        capture_ref,
                    )
                )
            gaps.append(
                _gap(
                    "OFFICIAL_PROGRESSION_STATE_UNAVAILABLE",
                    "journal_relation_to_progression_state",
                    (
                        client_journal_evidence_ref
                        if verified_client_journal_members is not None
                        else capture_ref
                    ),
                )
            )
        elif source_key == "crafted:midnight-season-1":
            if verified_client_crafted_members is not None:
                raw_members = verified_client_crafted_members
                gaps.append(
                    _gap(
                        "OFFICIAL_PROGRESSION_STATE_UNAVAILABLE",
                        "crafted_item_to_maximum_quality",
                        client_crafted_evidence_ref,
                    )
                )
            else:
                raw_members = [
                    {
                        **row,
                        "evidenceRef": (
                            f"{capture_directory}/raw/game-data/professions/"
                            f"recipes/{_text(row.get('recipeId'))}.json"
                        ),
                    }
                    for row in projected_recipes
                ]
                gaps.append(
                    _gap(
                        "OFFICIAL_RECIPE_OUTPUT_ITEM_ID_UNAVAILABLE",
                        "profession_recipe_to_item",
                        capture_ref,
                    )
                )
        elif source_key in {
            "tier_set_vendor:chiming-void-curio",
            "catalyst:midnight-season-1",
        }:
            raw_members = [
                {
                    "itemSetId": _text(row.get("itemSetId")),
                    "name": _text(row.get("name")),
                    "itemIds": sorted(
                        {_text(item_id) for item_id in row.get("itemIds") or []},
                        key=int,
                    ),
                    "evidenceRef": (
                        f"{capture_directory}/raw/game-data/item-sets/"
                        f"{_text(row.get('itemSetId'))}.json"
                    ),
                }
                for row in sets
            ]
            gaps.extend(
                [
                    _gap(
                        "OFFICIAL_TRANSFORM_ELIGIBILITY_RELATION_UNAVAILABLE",
                        "item_set_to_source_eligibility",
                        capture_ref,
                    ),
                    _gap(
                        "OFFICIAL_PROGRESSION_STATE_UNAVAILABLE",
                        "item_set_to_progression_state",
                        capture_ref,
                    ),
                ]
            )
        else:
            gaps.append(
                _gap(
                    "OFFICIAL_SOURCE_MEMBERSHIP_API_UNAVAILABLE",
                    _text(policy_source.get("membershipMode")),
                    authority_manifest_ref,
                )
            )
        projected_sources.append(
            {
                "sourceKey": source_key,
                "sourceType": _text(policy_source.get("sourceType")),
                "membershipMode": _text(policy_source.get("membershipMode")),
                "effectiveWindow": policy_source.get("effectiveWindow"),
                "authorityRefs": sorted(
                    {_text(ref) for ref in policy_source.get("authorityRefs") or []}
                ),
                "status": "captured_partial" if raw_members else "blocked",
                "membershipComplete": False,
                "rawMemberCount": len(raw_members),
                "rawDistinctItemCount": len(
                    {
                        _text(row.get("itemId"))
                        for row in raw_members
                        if _text(row.get("itemId"))
                    }
                    | {
                        _text(item_id)
                        for row in raw_members
                        for item_id in row.get("itemIds") or []
                        if _text(item_id)
                    }
                    | {
                        _text(item_id)
                        for row in raw_members
                        for item_id in row.get("candidateItemIds") or []
                        if _text(item_id)
                    }
                ),
                "rawMembers": raw_members,
                "gaps": gaps,
            }
        )

    projected_sources.sort(key=lambda row: row["sourceKey"])
    known_source_keys = {row["sourceKey"] for row in projected_sources}
    unknown_journal_sources = sorted(set(journal_members) - known_source_keys)
    if unknown_journal_sources:
        raise OfficialEvidenceError(
            "official Journal projection is outside policy: "
            + ",".join(unknown_journal_sources)
        )
    gap_reason_counts: dict[str, int] = {}
    for source in projected_sources:
        for gap in source["gaps"]:
            reason_code = gap["reasonCode"]
            gap_reason_counts[reason_code] = gap_reason_counts.get(reason_code, 0) + 1
    return {
        "schemaVersion": 1,
        "schemaRevision": EVIDENCE_SCHEMA_REVISION,
        "status": "blocked",
        "seasonRevision": _text(policy.get("seasonRevision")),
        "sourcePolicyRevision": _text(policy.get("sourcePolicyRevision")),
        "sourcePolicyStatus": _text(policy.get("status")),
        "capturedAt": _text(captured_at),
        "asOf": _text(capture.get("asOf")),
        "authorityManifestRef": authority_manifest_ref,
        "officialCaptureRef": capture_ref,
        "simcClientItemDataRef": simc_evidence_ref,
        "sources": projected_sources,
        "summary": {
            "sourceCount": len(projected_sources),
            "completeSourceCount": 0,
            "partialSourceCount": sum(
                row["status"] == "captured_partial"
                for row in projected_sources
            ),
            "blockedSourceCount": sum(
                row["status"] == "blocked"
                for row in projected_sources
            ),
            "rawMemberCount": sum(
                row["rawMemberCount"] for row in projected_sources
            ),
            "gapCount": sum(len(row["gaps"]) for row in projected_sources),
            "gapReasonCounts": dict(sorted(gap_reason_counts.items())),
        },
    }


def build_universe_discovery_input(
    membership_snapshot: Any,
    *,
    evidence_ref: str,
) -> dict[str, Any]:
    """Adapt partial official evidence without inventing canonical members."""

    if not isinstance(membership_snapshot, dict) or not isinstance(
        membership_snapshot.get("sources"),
        list,
    ):
        raise OfficialEvidenceError(
            "Universe discovery adapter requires membership sources"
        )
    resolved_evidence_ref = _text(evidence_ref)
    if not resolved_evidence_ref:
        raise OfficialEvidenceError(
            "Universe discovery adapter requires evidence_ref"
        )
    sources = []
    for raw_source in membership_snapshot["sources"]:
        source = raw_source if isinstance(raw_source, dict) else {}
        source_key = _text(source.get("sourceKey"))
        authority_refs = source.get("authorityRefs")
        gaps = source.get("gaps")
        if (
            not source_key
            or not isinstance(authority_refs, list)
            or not authority_refs
            or not isinstance(gaps, list)
        ):
            raise OfficialEvidenceError(
                "Universe discovery adapter source is malformed"
            )
        adapted_gaps = []
        for raw_gap in gaps:
            gap = raw_gap if isinstance(raw_gap, dict) else {}
            reason_code = _text(gap.get("reasonCode"))
            if not re.fullmatch(r"OFFICIAL_[A-Z0-9_]{3,100}", reason_code):
                raise OfficialEvidenceError(
                    "Universe discovery adapter gap reason is invalid"
                )
            adapted_gaps.append(
                {
                    "kind": reason_code.lower(),
                    "boundary": _text(gap.get("boundary")),
                    "identity": reason_code,
                    "cursor": "",
                    "omittedCount": 0,
                    "evidenceRef": _text(gap.get("evidenceRef"))
                    or resolved_evidence_ref,
                }
            )
        sources.append(
            {
                "sourceKey": source_key,
                "status": _text(source.get("status")) or "blocked",
                "capturedAt": _text(
                    membership_snapshot.get("capturedAt")
                ),
                "validUntil": "",
                "evidenceRef": (
                    f"{resolved_evidence_ref}#source={source_key}"
                ),
                "authorityRefs": sorted(
                    {_text(ref) for ref in authority_refs if _text(ref)}
                ),
                "membershipComplete": False,
                "declaredMemberCount": 0,
                "members": [],
                "gaps": adapted_gaps,
                "rawMemberCount": int(source.get("rawMemberCount") or 0),
            }
        )
    sources.sort(key=lambda row: row["sourceKey"])
    return {
        "schemaVersion": 1,
        "schemaRevision": EVIDENCE_SCHEMA_REVISION,
        "status": "blocked",
        "seasonRevision": _text(
            membership_snapshot.get("seasonRevision")
        ),
        "sourcePolicyRevision": _text(
            membership_snapshot.get("sourcePolicyRevision")
        ),
        "asOf": _text(
            membership_snapshot.get("asOf")
            or membership_snapshot.get("capturedAt")
        ),
        "membershipEvidenceRef": resolved_evidence_ref,
        "sources": sources,
    }


def build_official_item_opposition(
    official_item_index: Any,
    membership_snapshot: Any,
    *,
    required_level: int | None = 90,
    search_scope: str = "required_level_90_equippable",
    client_item_ids: Any = None,
) -> dict[str, Any]:
    """Explain every item in one checksummed official Item Search scope.

    This is deliberately an opposition ledger, not a Universe denominator.
    PvP, cosmetic, legacy, or otherwise ineligible equipment may sit inside
    an all-equippable scope.  A max-level scope can instead omit scaled legacy
    dungeon and Timewalking items.  Unlinked rows therefore remain candidates
    requiring source membership or governed exclusion evidence.
    """

    if not isinstance(official_item_index, dict):
        raise OfficialEvidenceError(
            "official item opposition requires an indexed item search"
        )
    if (
        required_level is not None
        and (
            not isinstance(required_level, int)
            or isinstance(required_level, bool)
            or required_level < 1
        )
    ):
        raise OfficialEvidenceError(
            "official item opposition required_level is invalid"
        )
    resolved_search_scope = _text(search_scope)
    if not resolved_search_scope:
        raise OfficialEvidenceError(
            "official item opposition requires search_scope"
        )
    if not isinstance(membership_snapshot, dict) or not isinstance(
        membership_snapshot.get("sources"),
        list,
    ):
        raise OfficialEvidenceError(
            "official item opposition requires membership sources"
        )
    normalized_client_item_ids = None
    if client_item_ids is not None:
        if isinstance(client_item_ids, (str, bytes, dict)):
            raise OfficialEvidenceError(
                "official item opposition client ids must be a collection"
            )
        try:
            normalized_client_item_ids = {
                _text(item_id) for item_id in client_item_ids
            } - {""}
        except TypeError as error:
            raise OfficialEvidenceError(
                "official item opposition client ids must be iterable"
            ) from error
        if any(
            not item_id.isdigit() or int(item_id) < 1
            for item_id in normalized_client_item_ids
        ):
            raise OfficialEvidenceError(
                "official item opposition client ids must be positive integers"
            )
    source_links: dict[str, list[dict[str, str]]] = {}
    for raw_source in membership_snapshot["sources"]:
        source = raw_source if isinstance(raw_source, dict) else {}
        source_key = _text(source.get("sourceKey"))
        source_type = _text(source.get("sourceType"))
        raw_members = source.get("rawMembers")
        if not source_key or not isinstance(raw_members, list):
            raise OfficialEvidenceError(
                "official item opposition source is malformed"
            )
        for raw_member in raw_members:
            member = raw_member if isinstance(raw_member, dict) else {}
            item_ids = {
                _text(member.get("itemId")),
                *{
                    _text(item_id)
                    for item_id in member.get("itemIds") or []
                },
                *{
                    _text(item_id)
                    for item_id in member.get("candidateItemIds") or []
                },
            }
            for item_id in item_ids - {""}:
                source_links.setdefault(item_id, []).append(
                    {
                        "sourceKey": source_key,
                        "sourceType": source_type,
                    }
                )

    items = []
    seen_ids = set()
    source_type_item_ids: dict[str, set[str]] = {}
    for rows in official_item_index.values():
        if not isinstance(rows, list):
            raise OfficialEvidenceError(
                "official item opposition index rows must be lists"
            )
        for raw_item in rows:
            item = raw_item if isinstance(raw_item, dict) else {}
            item_id = _text(item.get("id"))
            if (
                not item_id
                or item_id in seen_ids
                or (
                    required_level is not None
                    and item.get("required_level") != required_level
                )
                or item.get("is_equippable") is not True
            ):
                raise OfficialEvidenceError(
                    "official item opposition row violates bounded search scope"
                )
            seen_ids.add(item_id)
            localized_name = item.get("name")
            if isinstance(localized_name, dict):
                name = _text(
                    localized_name.get("en_US")
                    or localized_name.get("en_GB")
                    or next(iter(localized_name.values()), "")
                )
            else:
                name = _text(localized_name)
            links = sorted(
                {
                    (row["sourceKey"], row["sourceType"])
                    for row in source_links.get(item_id, [])
                }
            )
            for _source_key, source_type in links:
                source_type_item_ids.setdefault(source_type, set()).add(
                    item_id
                )
            items.append(
                {
                    "itemId": item_id,
                    "name": name,
                    "requiredLevel": item.get("required_level"),
                    "inventoryType": _text(
                        (item.get("inventory_type") or {}).get("name")
                    ),
                    "itemClass": _text(
                        (item.get("item_class") or {}).get("name")
                    ),
                    "itemSubclass": _text(
                        (item.get("item_subclass") or {}).get("name")
                    ),
                    "quality": _text(
                        (item.get("quality") or {}).get("name")
                    ),
                    "sourceKeys": [row[0] for row in links],
                    "sourceTypes": sorted({row[1] for row in links}),
                    "candidateStatus": (
                        "source_linked_partial"
                        if links
                        else "unresolved_source_or_exclusion"
                    ),
                }
            )
    items.sort(key=lambda row: int(row["itemId"]))
    unresolved = [
        row
        for row in items
        if row["candidateStatus"] == "unresolved_source_or_exclusion"
    ]
    client_comparison = {
        "status": "not_provided",
        "officialItemCount": len(seen_ids),
        "clientItemCount": 0,
        "sharedItemCount": 0,
        "officialOnlyItemIds": [],
        "clientOnlyItemIds": [],
    }
    if normalized_client_item_ids is not None:
        official_only = sorted(
            seen_ids - normalized_client_item_ids,
            key=int,
        )
        client_only = sorted(
            normalized_client_item_ids - seen_ids,
            key=int,
        )
        client_comparison = {
            "status": (
                "matched"
                if not official_only and not client_only
                else "mismatched"
            ),
            "officialItemCount": len(seen_ids),
            "clientItemCount": len(normalized_client_item_ids),
            "sharedItemCount": len(
                seen_ids & normalized_client_item_ids
            ),
            "officialOnlyItemIds": official_only,
            "clientOnlyItemIds": client_only,
        }
    return {
        "schemaVersion": 1,
        "schemaRevision": EVIDENCE_SCHEMA_REVISION,
        "status": "blocked",
        "scope": {
            "officialSearchScope": resolved_search_scope,
            "requiredLevel": required_level,
            "equippable": True,
            "officialSearchScopeComplete": True,
            "seasonPveUniverseComplete": False,
        },
        "reasonCodes": [
            "OFFICIAL_ITEM_SEARCH_SCOPE_NOT_UNIVERSE",
            *(
                ["OFFICIAL_ITEM_RANGE_CLIENT_DATA_MISMATCH"]
                if client_comparison["status"] == "mismatched"
                else []
            ),
            *(
                ["OFFICIAL_ITEM_SOURCE_OR_EXCLUSION_UNRESOLVED"]
                if unresolved
                else []
            ),
        ],
        "summary": {
            "scopedItemCount": len(items),
            "sourceLinkedItemCount": len(items) - len(unresolved),
            "unresolvedItemCount": len(unresolved),
            "clientComparisonStatus": client_comparison["status"],
            "officialOnlyVsClientCount": len(
                client_comparison["officialOnlyItemIds"]
            ),
            "clientOnlyVsOfficialCount": len(
                client_comparison["clientOnlyItemIds"]
            ),
            "sourceLinkedByType": {
                source_type: len(item_ids)
                for source_type, item_ids in sorted(
                    source_type_item_ids.items()
                )
            },
        },
        "clientItemComparison": client_comparison,
        "items": items,
    }


def build_crafted_allowlist_diff(
    crafted_source: Any,
    project_allowlist: Any,
    *,
    project_unsupported: Any = None,
    project_excluded: Any = None,
) -> dict[str, Any]:
    """Compare the cross-source crafted candidate set with project membership."""

    if not isinstance(crafted_source, dict) or not isinstance(
        crafted_source.get("rawMembers"),
        list,
    ):
        raise OfficialEvidenceError(
            "crafted source requires rawMembers"
        )
    allowlist = {
        _text(item_id)
        for item_id in project_allowlist or []
        if _text(item_id)
    }
    unsupported = {
        _text(item_id)
        for item_id in project_unsupported or []
        if _text(item_id)
    }
    excluded = {
        _text(item_id)
        for item_id in project_excluded or []
        if _text(item_id)
    }
    projected = {}
    unresolved = []
    for raw_member in crafted_source["rawMembers"]:
        member = raw_member if isinstance(raw_member, dict) else {}
        candidate_ids = sorted(
            {
                _text(item_id)
                for item_id in member.get("candidateItemIds") or []
                if _text(item_id)
            },
            key=int,
        )
        if len(candidate_ids) != 1:
            unresolved.append(
                {
                    "recipeId": _text(member.get("recipeId")),
                    "name": _text(member.get("name")),
                    "candidateItemIds": candidate_ids,
                }
            )
            continue
        item_id = candidate_ids[0]
        if item_id in projected:
            raise OfficialEvidenceError(
                f"crafted projection has duplicate item id {item_id}"
            )
        modified_slot_names = sorted(
            {
                _text(name)
                for name in member.get("modifiedCraftingSlotNames") or []
                if _text(name)
            }
        )
        secondary_stat_mode = (
            "customize_two_secondary"
            if "Customize Secondary Stats" in modified_slot_names
            else "amplify_one_secondary"
            if "Amplify Secondary Stat" in modified_slot_names
            else "fixed_or_recipe_defined_stats"
        )
        projected[item_id] = {
            "itemId": item_id,
            "profession": _text(member.get("profession")),
            "category": _text(member.get("category")),
            "recipeId": _text(member.get("recipeId")),
            "name": _text(member.get("name")),
            "candidateJoinMethod": _text(
                member.get("candidateJoinMethod")
            ),
            "officialCandidateItemIds": list(
                member.get("officialCandidateItemIds") or []
            ),
            "simcClientCandidateItemIds": list(
                member.get("simcClientCandidateItemIds") or []
            ),
            "modifiedCraftingSlotNames": modified_slot_names,
            "secondaryStatMode": secondary_stat_mode,
            "canAddEmbellishment": (
                "Add Embellishment" in modified_slot_names
            ),
            "supportsSocketReagent": (
                "Socket" in modified_slot_names
            ),
            "powerReagentMode": (
                "spark"
                if "Spark" in modified_slot_names
                else "empower"
                if "Empower" in modified_slot_names
                else "recipe_defined"
            ),
        }
    projected_ids = set(projected)
    missing = [
        projected[item_id]
        for item_id in sorted(projected_ids - allowlist, key=int)
    ]
    outside = sorted(allowlist - projected_ids, key=int)
    profession_counts: dict[str, int] = {}
    missing_profession_counts: dict[str, int] = {}
    capability_counts: dict[str, int] = {}
    missing_capability_counts: dict[str, int] = {}
    for row in projected.values():
        profession = row["profession"]
        profession_counts[profession] = profession_counts.get(profession, 0) + 1
        capability = row["secondaryStatMode"]
        capability_counts[capability] = capability_counts.get(capability, 0) + 1
    for row in missing:
        profession = row["profession"]
        missing_profession_counts[profession] = (
            missing_profession_counts.get(profession, 0) + 1
        )
        capability = row["secondaryStatMode"]
        missing_capability_counts[capability] = (
            missing_capability_counts.get(capability, 0) + 1
        )
    status = (
        "verified"
        if not missing and not outside and not unresolved
        else "blocked"
    )
    return {
        "schemaVersion": 1,
        "schemaRevision": EVIDENCE_SCHEMA_REVISION,
        "status": status,
        "reasonCodes": sorted(
            {
                *(
                    ["CRAFTED_CANDIDATE_MISSING_FROM_PROJECT_ALLOWLIST"]
                    if missing
                    else []
                ),
                *(
                    ["PROJECT_CRAFTED_ALLOWLIST_OUTSIDE_PROJECTION"]
                    if outside
                    else []
                ),
                *(
                    ["CRAFTED_CANDIDATE_IDENTITY_UNRESOLVED"]
                    if unresolved
                    else []
                ),
            }
        ),
        "summary": {
            "projectedCandidateCount": len(projected),
            "projectAllowlistCount": len(allowlist),
            "includedCount": len(projected_ids & allowlist),
            "missingFromProjectAllowlistCount": len(missing),
            "projectAllowlistOutsideProjectionCount": len(outside),
            "unresolvedCandidateCount": len(unresolved),
            "unsupportedProjectedCount": len(projected_ids & unsupported),
            "excludedProjectedCount": len(projected_ids & excluded),
            "projectedByProfession": dict(sorted(profession_counts.items())),
            "missingByProfession": dict(
                sorted(missing_profession_counts.items())
            ),
            "projectedBySecondaryStatMode": dict(
                sorted(capability_counts.items())
            ),
            "missingBySecondaryStatMode": dict(
                sorted(missing_capability_counts.items())
            ),
        },
        "missingFromProjectAllowlist": missing,
        "projectAllowlistOutsideProjection": outside,
        "unresolvedCandidates": unresolved,
        "projectUnsupportedProjected": sorted(
            projected_ids & unsupported,
            key=int,
        ),
        "projectExcludedProjected": sorted(
            projected_ids & excluded,
            key=int,
        ),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(body)
    temporary.replace(path)

#!/usr/bin/env python3
"""Pure contracts for immutable observed player build snapshots."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


OBSERVED_BUILD_SNAPSHOT_SCHEMA_REVISION = "observed-build-snapshot-v1"
OBSERVED_BUILD_SNAPSHOT_ID_PREFIX = "observed-build:sha256:"
OBSERVED_BUILD_SOURCE_CHECK_SCHEMA_REVISION = "observed-build-source-check-v1"

_SLOT_FIELDS = ("classKey", "specKey", "heroKey", "scenarioKey")
_SOURCE_FIELDS = (
    "sourceKey",
    "sourceIdentity",
    "profileUrl",
    "region",
    "realm",
    "character",
)
_SOURCE_CHECK_STATUSES = {"captured", "changed", "unchanged", "failed"}
_SLUG_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,79}")
_SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
_SNAPSHOT_ID_PATTERN = re.compile(r"observed-build:sha256:[0-9a-f]{64}")


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


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _required_text(value: Any, name: str, *, limit: int = 512) -> str:
    normalized = _text(value)
    if not normalized or len(normalized) > limit:
        raise ValueError(f"{name} must be a bounded non-empty string")
    return normalized


def _slot(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("slot must be an object")
    normalized: dict[str, str] = {}
    for field in _SLOT_FIELDS:
        item = _required_text(value.get(field), field, limit=80)
        if not _SLUG_PATTERN.fullmatch(item):
            raise ValueError(f"{field} must be a canonical slug")
        normalized[field] = item
    return normalized


def slot_key(slot: Any) -> str:
    """Return the exact class/spec/hero/scenario identity for one slot."""

    normalized = _slot(slot)
    return ":".join(normalized[field] for field in _SLOT_FIELDS)


def _source(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("source must be an object")
    normalized = {
        field: _required_text(value.get(field), field)
        for field in _SOURCE_FIELDS
    }
    if normalized["sourceKey"] != "raiderio":
        raise ValueError("sourceKey must identify a real Raider.IO source")
    if not normalized["sourceIdentity"].startswith("raiderio:"):
        raise ValueError("sourceIdentity must be a bounded Raider.IO identity")
    if not normalized["profileUrl"].startswith("https://raider.io/"):
        raise ValueError("profileUrl must be an HTTPS Raider.IO profile URL")
    return normalized


def _snapshot_profile_payload(
    snapshot: dict[str, Any],
    *,
    talent_hash: str = "",
    gear_hash: str = "",
) -> dict[str, Any]:
    return {
        "slot": snapshot.get("slot"),
        "source": snapshot.get("source"),
        "rankingEvidence": snapshot.get("rankingEvidence"),
        "talentHash": talent_hash or snapshot.get("talentHash"),
        "gearHash": gear_hash or snapshot.get("gearHash"),
        "sourceRevision": snapshot.get("sourceRevision"),
    }


def _snapshot_identity_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaRevision": snapshot.get("schemaRevision"),
        "slot": snapshot.get("slot"),
        "source": snapshot.get("source"),
        "rankingEvidence": snapshot.get("rankingEvidence"),
        "talentObservation": snapshot.get("talentObservation"),
        "gearObservation": snapshot.get("gearObservation"),
        "profileHash": snapshot.get("profileHash"),
        "talentHash": snapshot.get("talentHash"),
        "gearHash": snapshot.get("gearHash"),
        "sourceRevision": snapshot.get("sourceRevision"),
    }


def _expected_snapshot_id(snapshot: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        _canonical_bytes(_snapshot_identity_payload(snapshot))
    ).hexdigest()
    return OBSERVED_BUILD_SNAPSHOT_ID_PREFIX + digest


def build_observed_snapshot(
    *,
    slot: dict[str, Any],
    source: dict[str, Any],
    ranking_evidence: dict[str, Any],
    talent_observation: dict[str, Any],
    gear_observation: dict[str, Any],
    source_revision: str,
) -> dict[str, Any]:
    """Build one content-addressed observed player snapshot.

    Collection/check time deliberately lives in ``snapshot_check`` so identical
    observed content reuses the same immutable snapshot identity.
    """

    normalized_talent = _canonical(
        talent_observation if isinstance(talent_observation, dict) else {}
    )
    normalized_gear = _canonical(
        gear_observation if isinstance(gear_observation, dict) else {}
    )
    if not normalized_talent:
        raise ValueError("talent_observation must be a non-empty object")
    if not normalized_gear:
        raise ValueError("gear_observation must be a non-empty object")
    snapshot = {
        "schemaRevision": OBSERVED_BUILD_SNAPSHOT_SCHEMA_REVISION,
        "snapshotId": "",
        "slot": _slot(slot),
        "source": _source(source),
        "rankingEvidence": _canonical(
            ranking_evidence if isinstance(ranking_evidence, dict) else {}
        ),
        "talentObservation": normalized_talent,
        "gearObservation": normalized_gear,
        "profileHash": "",
        "talentHash": _sha256({"talentObservation": normalized_talent}),
        "gearHash": _sha256({"gearObservation": normalized_gear}),
        "sourceRevision": _required_text(
            source_revision,
            "source_revision",
        ),
    }
    snapshot["profileHash"] = _sha256(_snapshot_profile_payload(snapshot))
    snapshot["snapshotId"] = _expected_snapshot_id(snapshot)
    return snapshot


def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def validate_observed_snapshot(snapshot: Any) -> list[dict[str, str]]:
    """Return integrity issues for one detached snapshot record."""

    if not isinstance(snapshot, dict):
        return [_issue("SNAPSHOT_INVALID", "snapshot", "Snapshot must be an object.")]
    issues: list[dict[str, str]] = []
    try:
        _slot(snapshot.get("slot"))
    except ValueError as error:
        issues.append(_issue("SLOT_INVALID", "snapshot.slot", str(error)))
    try:
        _source(snapshot.get("source"))
    except ValueError as error:
        issues.append(_issue("SOURCE_INVALID", "snapshot.source", str(error)))
    if snapshot.get("schemaRevision") != OBSERVED_BUILD_SNAPSHOT_SCHEMA_REVISION:
        issues.append(
            _issue(
                "SCHEMA_REVISION_INVALID",
                "snapshot.schemaRevision",
                "Snapshot schema revision is unsupported.",
            )
        )
    try:
        _required_text(snapshot.get("sourceRevision"), "sourceRevision")
    except ValueError as error:
        issues.append(
            _issue(
                "SOURCE_REVISION_INVALID",
                "snapshot.sourceRevision",
                str(error),
            )
        )
    if not isinstance(snapshot.get("rankingEvidence"), dict):
        issues.append(
            _issue(
                "RANKING_EVIDENCE_INVALID",
                "snapshot.rankingEvidence",
                "Ranking evidence must be an object.",
            )
        )
    if not isinstance(snapshot.get("talentObservation"), dict) or not snapshot.get(
        "talentObservation"
    ):
        issues.append(
            _issue(
                "TALENT_OBSERVATION_INVALID",
                "snapshot.talentObservation",
                "Talent observation must be a non-empty object.",
            )
        )
    if not isinstance(snapshot.get("gearObservation"), dict) or not snapshot.get(
        "gearObservation"
    ):
        issues.append(
            _issue(
                "GEAR_OBSERVATION_INVALID",
                "snapshot.gearObservation",
                "Gear observation must be a non-empty object.",
            )
        )
    expected_talent_hash = _sha256(
        {"talentObservation": snapshot.get("talentObservation")}
    )
    if not _SHA256_PATTERN.fullmatch(_text(snapshot.get("talentHash"))) or (
        snapshot.get("talentHash") != expected_talent_hash
    ):
        issues.append(
            _issue(
                "TALENT_HASH_MISMATCH",
                "snapshot.talentHash",
                "Talent observation does not match its hash.",
            )
        )
    expected_gear_hash = _sha256(
        {"gearObservation": snapshot.get("gearObservation")}
    )
    if not _SHA256_PATTERN.fullmatch(_text(snapshot.get("gearHash"))) or (
        snapshot.get("gearHash") != expected_gear_hash
    ):
        issues.append(
            _issue(
                "GEAR_HASH_MISMATCH",
                "snapshot.gearHash",
                "Gear observation does not match its hash.",
            )
        )
    expected_profile_hash = _sha256(
        _snapshot_profile_payload(
            snapshot,
            talent_hash=expected_talent_hash,
            gear_hash=expected_gear_hash,
        )
    )
    if not _SHA256_PATTERN.fullmatch(_text(snapshot.get("profileHash"))) or (
        snapshot.get("profileHash") != expected_profile_hash
    ):
        issues.append(
            _issue(
                "PROFILE_HASH_MISMATCH",
                "snapshot.profileHash",
                "Observed profile does not match its hash.",
            )
        )
    expected_snapshot_id = _expected_snapshot_id(snapshot)
    if not _SNAPSHOT_ID_PATTERN.fullmatch(_text(snapshot.get("snapshotId"))) or (
        snapshot.get("snapshotId") != expected_snapshot_id
    ):
        issues.append(
            _issue(
                "SNAPSHOT_ID_MISMATCH",
                "snapshot.snapshotId",
                "Snapshot content does not match its content-addressed ID.",
            )
        )
    return issues


def snapshot_check(
    *,
    run_id: str,
    slot: dict[str, Any],
    checked_at: str,
    status: str,
    snapshot_id: str = "",
    problem: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one append-only source observation check."""

    normalized_status = _text(status)
    if normalized_status not in _SOURCE_CHECK_STATUSES:
        raise ValueError("status must be captured, changed, unchanged, or failed")
    normalized_snapshot_id = _text(snapshot_id)
    if normalized_status != "failed" and not _SNAPSHOT_ID_PATTERN.fullmatch(
        normalized_snapshot_id
    ):
        raise ValueError("snapshot_id is required for successful source checks")
    normalized_problem = _canonical(problem if isinstance(problem, dict) else {})
    if normalized_status == "failed" and not normalized_problem:
        raise ValueError("problem is required for failed source checks")
    if normalized_status != "failed" and normalized_problem:
        raise ValueError("problem is only allowed for failed source checks")
    return {
        "schemaRevision": OBSERVED_BUILD_SOURCE_CHECK_SCHEMA_REVISION,
        "runId": _required_text(run_id, "run_id"),
        "slot": _slot(slot),
        "slotKey": slot_key(slot),
        "checkedAt": _required_text(checked_at, "checked_at"),
        "status": normalized_status,
        "snapshotId": normalized_snapshot_id,
        "problem": normalized_problem,
    }


__all__ = (
    "OBSERVED_BUILD_SNAPSHOT_ID_PREFIX",
    "OBSERVED_BUILD_SNAPSHOT_SCHEMA_REVISION",
    "OBSERVED_BUILD_SOURCE_CHECK_SCHEMA_REVISION",
    "build_observed_snapshot",
    "slot_key",
    "snapshot_check",
    "validate_observed_snapshot",
)

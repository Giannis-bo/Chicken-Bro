#!/usr/bin/env python3
"""Pure contracts for revision-bound asynchronous Gear stat snapshots."""

from __future__ import annotations

import hashlib
import json
from typing import Any


STAT_SIGNATURE_SCHEMA_REVISION = "stat-signature-v1"
STAT_SNAPSHOT_SCHEMA_REVISION = "gear-stat-snapshot-v1"

STAT_SIGNATURE_DEPENDENCY_FIELDS = (
    "seasonRevision",
    "gearCatalogReleaseId",
    "gearCatalogRevision",
    "gearRuleRevision",
    "resolverContractRevision",
    "serializerRevision",
    "simcRuntimeRevision",
    "statPolicyRevision",
    "selectionSchemaRevision",
    "capabilityRevision",
)

STAT_SIGNATURE_RELEASE_FIELDS = (
    "manifestRevision",
    "pointerGeneration",
    "gearCatalogRevision",
    "communityTemplateRevision",
    "talentCatalogRevision",
)

_REQUIRED_DEPENDENCY_FIELDS = (
    "seasonRevision",
    "gearRuleRevision",
    "resolverContractRevision",
    "serializerRevision",
    "simcRuntimeRevision",
    "statPolicyRevision",
    "selectionSchemaRevision",
)

_SNAPSHOT_FIELDS = (
    "statStatus",
    "statSource",
    "classKey",
    "specKey",
    "maxLevel",
    "itemLevel",
    "primary",
    "stamina",
    "secondary",
    "armor",
    "blockers",
    "gearSchemaRevision",
)


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bounded_string(value: Any, limit: int = 160) -> str:
    return _text(value)[:limit]


def client_key_hash(value: Any) -> str:
    """Return a one-way bounded client identity or an empty anonymous key."""

    normalized = _text(value)
    if not normalized:
        return ""
    return _sha256(normalized[:256].encode("utf-8"))


def build_stat_signature(
    resolved_snapshot: dict[str, Any],
    stat_profile: str,
    release_context: dict[str, Any],
) -> dict[str, Any]:
    """Build one server-owned signature for an exact resolved stat profile."""

    snapshot = resolved_snapshot if isinstance(resolved_snapshot, dict) else {}
    if snapshot.get("contractRevision") != "gear-resolved-snapshot-v1" or snapshot.get("status") != "verified":
        raise ValueError("verified gear-resolved-snapshot-v1 is required")
    resolved_signature = _text(snapshot.get("resolvedGearSignature"))
    if not resolved_signature:
        raise ValueError("resolved Gear signature is required")
    profile = str(stat_profile or "").strip()
    if not profile:
        raise ValueError("stat snapshot profile is required")
    dependencies = snapshot.get("dependencyVector") if isinstance(snapshot.get("dependencyVector"), dict) else {}
    missing_dependencies = [field for field in _REQUIRED_DEPENDENCY_FIELDS if not _text(dependencies.get(field))]
    if missing_dependencies:
        raise ValueError("stat signature dependency revisions are incomplete")
    release = release_context if isinstance(release_context, dict) else {}
    if not _text(release.get("manifestRevision")) or not _text(release.get("gearCatalogRevision")):
        raise ValueError("formal Manifest and Gear Release context are required")
    try:
        pointer_generation = int(release.get("pointerGeneration"))
    except (TypeError, ValueError, OverflowError):
        raise ValueError("pointer generation is required") from None
    if pointer_generation < 0:
        raise ValueError("pointer generation is required")

    dependency_vector = {
        field: _text(dependencies.get(field))
        for field in STAT_SIGNATURE_DEPENDENCY_FIELDS
        if _text(dependencies.get(field))
    }
    release_vector = {
        field: (pointer_generation if field == "pointerGeneration" else _text(release.get(field)))
        for field in STAT_SIGNATURE_RELEASE_FIELDS
        if field == "pointerGeneration" or _text(release.get(field))
    }
    profile_hash = _sha256(profile.encode("utf-8"))
    identity = {
        "schemaRevision": STAT_SIGNATURE_SCHEMA_REVISION,
        "resolvedGearSignature": resolved_signature,
        "profileHash": profile_hash,
        "releaseContext": release_vector,
        "dependencyVector": dependency_vector,
    }
    return {
        **identity,
        "manifestRevision": release_vector["manifestRevision"],
        "pointerGeneration": pointer_generation,
        "gearReleaseId": _text(dependencies.get("gearCatalogReleaseId") or release.get("gearCatalogRevision")),
        "simcRuntimeRevision": dependency_vector["simcRuntimeRevision"],
        "statSignature": "stat-snapshot:" + _sha256(_canonical_bytes(identity)),
    }


def _bounded_metric(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {
        key: _bounded_string(source.get(key), 80)
        for key in ("key", "label", "value", "percent")
        if _bounded_string(source.get(key), 80)
    }


def _bounded_item_level(value: Any) -> Any:
    if isinstance(value, (int, float, str)):
        return value
    source = value if isinstance(value, dict) else {}
    return {
        key: source[key]
        for key in ("average", "equipped", "display")
        if key in source and isinstance(source[key], (int, float, str))
    }


def _bounded_snapshot(raw_snapshot: dict[str, Any]) -> dict[str, Any]:
    source = raw_snapshot if isinstance(raw_snapshot, dict) else {}
    if source.get("statStatus") != "verified":
        raise ValueError("only verified stat snapshots may be published")
    output: dict[str, Any] = {
        "schemaRevision": STAT_SNAPSHOT_SCHEMA_REVISION,
        "statStatus": "verified",
        "statSource": _bounded_string(source.get("statSource"), 80),
        "classKey": _bounded_string(source.get("classKey"), 64),
        "specKey": _bounded_string(source.get("specKey"), 64),
        "maxLevel": source.get("maxLevel") if isinstance(source.get("maxLevel"), (int, float, str)) else None,
        "itemLevel": _bounded_item_level(source.get("itemLevel")),
        "primary": _bounded_metric(source.get("primary")),
        "stamina": _bounded_metric(source.get("stamina")),
        "secondary": [
            _bounded_metric(row)
            for row in (source.get("secondary") or [])[:16]
            if isinstance(row, dict)
        ],
        "armor": _bounded_metric(source.get("armor")),
        "blockers": [],
        "gearSchemaRevision": _bounded_string(source.get("gearSchemaRevision"), 120),
    }
    return {key: _canonical(value) for key, value in output.items() if value not in (None, "", {}, []) or key in {"secondary", "blockers"}}


def verified_snapshot_record(
    signature: dict[str, Any],
    raw_snapshot: dict[str, Any],
    *,
    verified_at: str,
) -> dict[str, Any]:
    """Build an immutable bounded publication record without DPS or raw output."""

    identity = signature if isinstance(signature, dict) else {}
    stat_signature = _text(identity.get("statSignature"))
    if not stat_signature.startswith("stat-snapshot:sha256:"):
        raise ValueError("valid stat signature is required")
    snapshot = _bounded_snapshot(raw_snapshot)
    snapshot.update(
        {
            "statSignature": stat_signature,
            "verifiedAt": _text(verified_at),
        }
    )
    return {
        "statSignature": stat_signature,
        "schemaRevision": _text(identity.get("schemaRevision")),
        "resolvedGearSignature": _text(identity.get("resolvedGearSignature")),
        "manifestRevision": _text(identity.get("manifestRevision")),
        "gearReleaseId": _text(identity.get("gearReleaseId")),
        "simcRuntimeRevision": _text(identity.get("simcRuntimeRevision")),
        "dependencyVector": _canonical(identity.get("dependencyVector") or {}),
        "profileHash": _text(identity.get("profileHash")),
        "snapshotHash": _sha256(_canonical_bytes(snapshot)),
        "snapshot": _canonical(snapshot),
        "verifiedAt": _text(verified_at),
    }


__all__ = (
    "STAT_SIGNATURE_DEPENDENCY_FIELDS",
    "STAT_SIGNATURE_SCHEMA_REVISION",
    "STAT_SNAPSHOT_SCHEMA_REVISION",
    "build_stat_signature",
    "client_key_hash",
    "verified_snapshot_record",
)

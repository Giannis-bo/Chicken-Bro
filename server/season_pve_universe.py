"""Deterministic current-season PVE source-universe reconciliation.

This module is deliberately pure. It does not fetch an authority, connect to a
database, mutate a Catalog, or infer missing membership from downstream counts.
Callers must provide independently captured discovery, staging, and Catalog
snapshots.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


UNIVERSE_SCHEMA_REVISION = "season-pve-universe-v1"
UNIVERSE_REVISION_PREFIX = "season-pve-universe:sha256:"


class UniverseContractError(ValueError):
    """Raised when an input cannot participate in deterministic reconciliation."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _content_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        raise UniverseContractError(f"{label} must be a non-empty object")
    if len(_canonical_json(value).encode("utf-8")) > 2048:
        raise UniverseContractError(f"{label} exceeds 2048 bytes")
    return json.loads(_canonical_json(value))


def _instant(value: Any, label: str) -> datetime:
    raw = _text(value)
    if not raw:
        raise UniverseContractError(f"{label} requires an ISO-8601 instant")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise UniverseContractError(
            f"{label} requires an ISO-8601 instant"
        ) from error
    if parsed.tzinfo is None:
        raise UniverseContractError(f"{label} requires a timezone")
    return parsed.astimezone(timezone.utc)


def item_relation_identity(value: dict[str, Any]) -> dict[str, Any]:
    row = value if isinstance(value, dict) else {}
    identity = {
        "sourceKey": _text(row.get("sourceKey")),
        "instanceId": _text(row.get("instanceId")),
        "encounterId": _text(row.get("encounterId")),
        "difficultyKey": _text(row.get("difficultyKey")),
        "itemId": _text(row.get("itemId")),
        "progressionState": _canonical_mapping(
            row.get("progressionState"),
            "item relation progressionState",
        ),
    }
    for field in (
        "sourceKey",
        "instanceId",
        "encounterId",
        "difficultyKey",
        "itemId",
    ):
        if not identity[field]:
            raise UniverseContractError(
                f"item relation requires {field}"
            )
    if not _text(identity["progressionState"].get("kind")):
        raise UniverseContractError(
            "item relation requires progressionState.kind"
        )
    return identity


def item_relation_key(value: dict[str, Any]) -> str:
    identity = item_relation_identity(value)
    return f"season-pve-item:sha256:{_content_hash(identity)}"


def _progression_state_key(value: dict[str, Any]) -> str:
    return f"progression-state:sha256:{_content_hash(value)}"


def _source_member_key(source_key: str) -> str:
    return f"season-pve-source:{source_key}"


def _gap_member_key(source_key: str, gap: dict[str, Any]) -> str:
    identity = {
        "sourceKey": source_key,
        "kind": _text(gap.get("kind")),
        "boundary": _text(gap.get("boundary")),
        "identity": _text(gap.get("identity")),
        "cursor": _text(gap.get("cursor")),
        "omittedCount": int(gap.get("omittedCount") or 0),
        "evidenceRef": _text(gap.get("evidenceRef")),
    }
    return f"season-pve-gap:sha256:{_content_hash(identity)}"


def _require_text(row: dict[str, Any], field: str, label: str) -> str:
    value = _text(row.get(field))
    if not value:
        raise UniverseContractError(f"{label} requires {field}")
    return value


def _validated_policy_sources(policy: dict[str, Any]) -> list[dict[str, Any]]:
    raw_sources = policy.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise UniverseContractError("source policy requires sources")
    sources = []
    seen = set()
    for raw_source in raw_sources:
        if not isinstance(raw_source, dict):
            raise UniverseContractError("source policy source must be an object")
        source_key = _require_text(raw_source, "sourceKey", "source policy source")
        if source_key in seen:
            raise UniverseContractError(
                f"source policy has duplicate sourceKey {source_key}"
            )
        seen.add(source_key)
        if raw_source.get("required") is not True:
            continue
        _require_text(raw_source, "sourceType", source_key)
        _require_text(raw_source, "membershipMode", source_key)
        if not isinstance(raw_source.get("authorityRefs"), list) or not raw_source.get(
            "authorityRefs"
        ):
            raise UniverseContractError(f"{source_key} requires authorityRefs")
        authority_refs = sorted(
            {
                _text(reference)
                for reference in raw_source.get("authorityRefs") or []
                if _text(reference)
            }
        )
        if not authority_refs:
            raise UniverseContractError(
                f"{source_key} requires non-empty authorityRefs"
            )
        minimum_member_count = raw_source.get("minimumMemberCount", 1)
        if (
            not isinstance(minimum_member_count, int)
            or isinstance(minimum_member_count, bool)
            or minimum_member_count < 1
        ):
            raise UniverseContractError(
                f"{source_key} requires positive minimumMemberCount"
            )
        normalized_source = dict(raw_source)
        normalized_source["authorityRefs"] = authority_refs
        normalized_source["minimumMemberCount"] = minimum_member_count
        sources.append(normalized_source)
    if not sources:
        raise UniverseContractError(
            "source policy requires at least one required source"
        )
    return sorted(sources, key=lambda row: _text(row.get("sourceKey")))


def _index_unique(rows: Any, key_fn, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        raise UniverseContractError(f"{label} members must be a list")
    index: dict[str, dict[str, Any]] = {}
    for raw_row in rows:
        if not isinstance(raw_row, dict):
            raise UniverseContractError(f"{label} row must be an object")
        key = key_fn(raw_row)
        if key in index:
            raise UniverseContractError(f"{label} has duplicate member {key}")
        index[key] = raw_row
    return index


def _validated_exclusions(
    exclusions: Any,
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    required_fields = (
        "memberKey",
        "reasonCode",
        "factOwner",
        "evidenceRef",
        "decidedAt",
    )
    for raw_row in exclusions if isinstance(exclusions, list) else []:
        if not isinstance(raw_row, dict):
            raise UniverseContractError("exclusion must be an object")
        for field in required_fields:
            _require_text(raw_row, field, "exclusion")
        _instant(raw_row.get("decidedAt"), "exclusion decidedAt")
        member_key = _text(raw_row.get("memberKey"))
        if member_key in index:
            raise UniverseContractError(
                f"exclusions have duplicate memberKey {member_key}"
            )
        index[member_key] = dict(raw_row)
    return index


GAP_REASON_CODES = {
    "cap": "SOURCE_CAP_TRUNCATED",
    "pagination": "SOURCE_PAGINATION_INCOMPLETE",
    "fetch_failure": "SOURCE_FETCH_FAILED",
    "fallback": "SOURCE_FALLBACK_USED",
    "official_journal_difficulty_membership_unavailable": (
        "OFFICIAL_JOURNAL_DIFFICULTY_MEMBERSHIP_UNAVAILABLE"
    ),
    "official_progression_state_unavailable": (
        "OFFICIAL_PROGRESSION_STATE_UNAVAILABLE"
    ),
    "official_recipe_output_item_id_unavailable": (
        "OFFICIAL_RECIPE_OUTPUT_ITEM_ID_UNAVAILABLE"
    ),
    "official_source_membership_api_unavailable": (
        "OFFICIAL_SOURCE_MEMBERSHIP_API_UNAVAILABLE"
    ),
    "official_transform_eligibility_relation_unavailable": (
        "OFFICIAL_TRANSFORM_ELIGIBILITY_RELATION_UNAVAILABLE"
    ),
}


def _source_effective_window(
    policy_source: dict[str, Any],
    *,
    as_of: datetime,
) -> dict[str, str]:
    raw_window = policy_source.get("effectiveWindow")
    if not isinstance(raw_window, dict):
        return {
            "state": "missing",
            "reasonCode": "SOURCE_EFFECTIVE_WINDOW_MISSING",
            "startsAt": "",
            "endsAt": "",
        }
    starts_at_raw = _text(raw_window.get("startsAt"))
    ends_at_raw = _text(raw_window.get("endsAt"))
    end_policy = _text(raw_window.get("endPolicy"))
    has_bounded_end = bool(ends_at_raw)
    has_open_end = end_policy == "until_officially_superseded"
    if (
        not starts_at_raw
        or has_bounded_end == has_open_end
        or (end_policy and not has_open_end)
    ):
        return {
            "state": "invalid",
            "reasonCode": "SOURCE_EFFECTIVE_WINDOW_INVALID",
            "startsAt": starts_at_raw,
            "endsAt": ends_at_raw,
            "endPolicy": end_policy,
        }
    try:
        starts_at = _instant(
            starts_at_raw,
            f"{_text(policy_source.get('sourceKey'))} effectiveWindow.startsAt",
        )
        ends_at = (
            _instant(
                ends_at_raw,
                f"{_text(policy_source.get('sourceKey'))} effectiveWindow.endsAt",
            )
            if has_bounded_end
            else None
        )
    except UniverseContractError:
        return {
            "state": "invalid",
            "reasonCode": "SOURCE_EFFECTIVE_WINDOW_INVALID",
            "startsAt": starts_at_raw,
            "endsAt": ends_at_raw,
            "endPolicy": end_policy,
        }
    if ends_at is not None and starts_at > ends_at:
        return {
            "state": "invalid",
            "reasonCode": "SOURCE_EFFECTIVE_WINDOW_INVALID",
            "startsAt": starts_at_raw,
            "endsAt": ends_at_raw,
            "endPolicy": end_policy,
        }
    if as_of < starts_at or (ends_at is not None and as_of > ends_at):
        return {
            "state": "outside",
            "reasonCode": "SOURCE_OUTSIDE_EFFECTIVE_WINDOW",
            "startsAt": starts_at_raw,
            "endsAt": ends_at_raw,
            "endPolicy": end_policy,
        }
    return {
        "state": "active",
        "reasonCode": "",
        "startsAt": starts_at_raw,
        "endsAt": ends_at_raw,
        "endPolicy": end_policy,
    }


def _gap_ledger_row(
    source_key: str,
    gap: dict[str, Any],
) -> dict[str, Any]:
    kind = _text(gap.get("kind"))
    reason_code = GAP_REASON_CODES.get(kind, "SOURCE_DISCOVERY_GAP")
    return {
        "memberKey": _gap_member_key(source_key, gap),
        "memberType": "gap",
        "sourceKey": source_key,
        "outcome": "blocked",
        "reasonCode": reason_code,
        "gapKind": kind,
        "boundary": _text(gap.get("boundary")),
        "identity": _text(gap.get("identity")),
        "cursor": _text(gap.get("cursor")),
        "omittedCount": int(gap.get("omittedCount") or 0),
        "evidenceRef": _text(gap.get("evidenceRef")),
    }


def _source_ledger_row(
    policy_source: dict[str, Any],
    discovered_source: dict[str, Any] | None,
    *,
    as_of: datetime,
    apply_effective_window: bool = True,
) -> dict[str, Any]:
    source_key = _text(policy_source.get("sourceKey"))
    effective_window = (
        _source_effective_window(
            policy_source,
            as_of=as_of,
        )
        if apply_effective_window
        else {
            "state": "end_game",
            "reasonCode": "",
            "startsAt": _text(
                (policy_source.get("captureContext") or {}).get("capturedAt")
            ),
            "endsAt": "",
            "endPolicy": "",
        }
    )
    base = {
        "memberKey": _source_member_key(source_key),
        "memberType": "source",
        "sourceKey": source_key,
        "sourceType": _text(policy_source.get("sourceType")),
        "membershipMode": _text(policy_source.get("membershipMode")),
        "authorityRefs": list(policy_source.get("authorityRefs") or []),
        "minimumMemberCount": int(policy_source.get("minimumMemberCount") or 1),
        "effectiveWindowState": effective_window["state"],
        "effectiveStartsAt": effective_window["startsAt"],
        "effectiveEndsAt": effective_window["endsAt"],
        "effectiveEndPolicy": effective_window.get("endPolicy") or "",
    }
    if effective_window["state"] in {"missing", "invalid"}:
        return {
            **base,
            "outcome": "blocked",
            "reasonCode": effective_window["reasonCode"],
            "evidenceRef": "",
            "capturedAt": "",
        }
    if effective_window["state"] == "outside":
        return {
            **base,
            "outcome": "excluded",
            "reasonCode": effective_window["reasonCode"],
            "factOwner": _text(policy_source.get("sourcePolicyOwner"))
            or "source_policy",
            "evidenceRef": ";".join(base["authorityRefs"]),
            "capturedAt": "",
        }
    if discovered_source is None:
        return {
            **base,
            "outcome": "blocked",
            "reasonCode": "SOURCE_DISCOVERY_MISSING",
            "evidenceRef": "",
            "capturedAt": "",
        }
    status = _text(discovered_source.get("status"))
    gaps = discovered_source.get("gaps")
    members = discovered_source.get("members")
    if not isinstance(members, list):
        raise UniverseContractError(f"{source_key} members must be a list")
    if not isinstance(gaps, list):
        raise UniverseContractError(f"{source_key} gaps must be a list")
    member_rows = members
    membership_complete = discovered_source.get("membershipComplete") is True
    declared_member_count = discovered_source.get("declaredMemberCount")
    count_matches = (
        isinstance(declared_member_count, int)
        and not isinstance(declared_member_count, bool)
        and declared_member_count >= 0
        and declared_member_count == len(member_rows)
    )
    evidence_ref = _text(discovered_source.get("evidenceRef"))
    raw_discovery_authority_refs = discovered_source.get("authorityRefs")
    discovery_authority_refs = (
        sorted(
            {
                _text(reference)
                for reference in raw_discovery_authority_refs
                if _text(reference)
            }
        )
        if isinstance(raw_discovery_authority_refs, list)
        else []
    )
    authority_coverage_complete = (
        discovery_authority_refs == base["authorityRefs"]
    )
    captured_at_raw = _text(discovered_source.get("capturedAt"))
    valid_until_raw = _text(discovered_source.get("validUntil"))
    if captured_at_raw:
        captured_at = _instant(captured_at_raw, f"{source_key} capturedAt")
    else:
        captured_at = None
    if valid_until_raw:
        valid_until = _instant(valid_until_raw, f"{source_key} validUntil")
    else:
        valid_until = None
    if status != "verified" or gaps:
        reason_code = "SOURCE_DISCOVERY_NOT_VERIFIED"
    elif not authority_coverage_complete:
        reason_code = "SOURCE_AUTHORITY_COVERAGE_MISMATCH"
    elif not evidence_ref or captured_at is None or valid_until is None:
        reason_code = "SOURCE_EVIDENCE_INCOMPLETE"
    elif captured_at > as_of:
        reason_code = "SOURCE_EVIDENCE_AFTER_AUDIT"
    elif valid_until < as_of:
        reason_code = "SOURCE_DISCOVERY_EXPIRED"
    elif not membership_complete:
        reason_code = "SOURCE_MEMBERSHIP_COMPLETENESS_UNPROVEN"
    elif not count_matches:
        reason_code = "SOURCE_MEMBER_COUNT_MISMATCH"
    elif len(member_rows) < base["minimumMemberCount"]:
        reason_code = "SOURCE_EMPTY_MEMBERSHIP_UNPROVEN"
    else:
        reason_code = ""
    verified = not reason_code
    return {
        **base,
        "outcome": "included" if verified else "blocked",
        "reasonCode": reason_code,
        "evidenceRef": evidence_ref,
        "capturedAt": captured_at_raw,
        "validUntil": valid_until_raw,
        "discoveryAuthorityRefs": discovery_authority_refs,
        "authorityCoverageComplete": authority_coverage_complete,
        "discoveryStatus": status or "missing",
        "membershipComplete": membership_complete,
        "declaredMemberCount": (
            declared_member_count
            if isinstance(declared_member_count, int)
            and not isinstance(declared_member_count, bool)
            else None
        ),
        "observedMemberCount": len(member_rows),
    }


def _item_ledger_row(
    member: dict[str, Any],
    staging_index: dict[str, dict[str, Any]],
    catalog_index: dict[str, dict[str, Any]],
    exclusions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    member_key = item_relation_key(member)
    identity = item_relation_identity(member)
    base = {
        "memberKey": member_key,
        "memberType": "item_relation",
        **identity,
        "progressionStateKey": _progression_state_key(
            identity["progressionState"]
        ),
        "evidenceRef": _text(member.get("evidenceRef")),
    }
    if not base["evidenceRef"]:
        return {
            **base,
            "outcome": "blocked",
            "reasonCode": "ITEM_EVIDENCE_MISSING",
        }
    exclusion = exclusions.get(member_key)
    if exclusion:
        return {
            **base,
            "outcome": "excluded",
            "reasonCode": _text(exclusion.get("reasonCode")),
            "factOwner": _text(exclusion.get("factOwner")),
            "exclusionEvidenceRef": _text(exclusion.get("evidenceRef")),
            "decidedAt": _text(exclusion.get("decidedAt")),
        }
    staging_row = staging_index.get(member_key)
    if staging_row is None:
        return {
            **base,
            "outcome": "blocked",
            "reasonCode": "STAGING_RELATION_MISSING",
        }
    if _text(staging_row.get("status")) != "verified":
        return {
            **base,
            "outcome": "blocked",
            "reasonCode": "STAGING_RELATION_NOT_VERIFIED",
            "stagingStatus": _text(staging_row.get("status")) or "missing",
        }
    if not _text(staging_row.get("sourceId")):
        return {
            **base,
            "outcome": "blocked",
            "reasonCode": "STAGING_IDENTITY_MISSING",
        }
    catalog_row = catalog_index.get(member_key)
    if catalog_row is None:
        return {
            **base,
            "outcome": "blocked",
            "reasonCode": "CATALOG_MEMBERSHIP_MISSING",
            "sourceId": _text(staging_row.get("sourceId")),
        }
    if _text(catalog_row.get("status")) != "verified":
        return {
            **base,
            "outcome": "blocked",
            "reasonCode": "CATALOG_MEMBERSHIP_NOT_VERIFIED",
            "catalogStatus": _text(catalog_row.get("status")) or "missing",
        }
    browse_variant_keys = sorted(
        {
            _text(key)
            for key in catalog_row.get("browseVariantKeys") or []
            if _text(key)
        }
    )
    if len(browse_variant_keys) != 1:
        return {
            **base,
            "outcome": "blocked",
            "reasonCode": "CATALOG_BROWSE_VARIANT_CARDINALITY_MISMATCH",
            "browseVariantCount": len(browse_variant_keys),
        }
    return {
        **base,
        "outcome": "included",
        "reasonCode": "",
        "sourceId": _text(staging_row.get("sourceId")),
        "browseVariantKeys": browse_variant_keys,
    }


def _downstream_orphan_ledger_row(
    member_key: str,
    staging_row: dict[str, Any] | None,
    catalog_row: dict[str, Any] | None,
) -> dict[str, Any]:
    source_row = staging_row or catalog_row or {}
    identity = item_relation_identity(source_row)
    return {
        "memberKey": member_key,
        "memberType": "item_relation",
        **identity,
        "progressionStateKey": _progression_state_key(
            identity["progressionState"]
        ),
        "evidenceRef": _text(source_row.get("evidenceRef")),
        "outcome": "blocked",
        "reasonCode": "DOWNSTREAM_MEMBER_NOT_DISCOVERED",
        "presentInStaging": staging_row is not None,
        "presentInCatalog": catalog_row is not None,
        "stagingStatus": (
            _text((staging_row or {}).get("status")) or "missing"
        ),
        "catalogStatus": (
            _text((catalog_row or {}).get("status")) or "missing"
        ),
    }


def _contract_ledger_row(
    reason_code: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    canonical_details = {
        key: _text(value)
        for key, value in sorted(details.items())
    }
    return {
        "memberKey": (
            f"season-pve-contract:sha256:"
            f"{_content_hash({'reasonCode': reason_code, **canonical_details})}"
        ),
        "memberType": "contract",
        "sourceKey": "",
        "outcome": "blocked",
        "reasonCode": reason_code,
        **canonical_details,
    }


def bounded_universe_report(
    report: dict[str, Any],
    *,
    max_ledger_rows: int = 100,
) -> dict[str, Any]:
    """Return a journald-safe view without unbounded source payloads."""

    if not isinstance(report, dict):
        raise UniverseContractError("universe report must be an object")
    try:
        row_limit = max(0, min(int(max_ledger_rows), 1000))
    except (TypeError, ValueError) as error:
        raise UniverseContractError(
            "max_ledger_rows must be an integer"
        ) from error
    raw_ledger = report.get("ledger")
    ledger = raw_ledger if isinstance(raw_ledger, list) else []
    safe_keys = (
        "memberKey",
        "memberType",
        "sourceKey",
        "sourceType",
        "itemId",
        "instanceId",
        "encounterId",
        "difficultyKey",
        "progressionStateKey",
        "outcome",
        "reasonCode",
        "gapKind",
        "boundary",
        "omittedCount",
        "discoveryStatus",
        "capturedAt",
        "validUntil",
        "effectiveWindowState",
        "effectiveStartsAt",
        "effectiveEndsAt",
        "effectiveEndPolicy",
        "minimumMemberCount",
        "membershipComplete",
        "declaredMemberCount",
        "observedMemberCount",
        "stagingStatus",
        "catalogStatus",
        "authorityCoverageComplete",
        "browseVariantCount",
        "presentInStaging",
        "presentInCatalog",
        "factOwner",
        "evidenceRef",
        "exclusionEvidenceRef",
        "decidedAt",
    )
    safe_ledger = []
    for raw_row in ledger[:row_limit]:
        if not isinstance(raw_row, dict):
            continue
        row = {}
        for key in safe_keys:
            value = raw_row.get(key)
            if value in (None, "", [], {}):
                continue
            row[key] = (
                value[:500]
                if isinstance(value, str)
                else value
            )
        safe_ledger.append(row)
    emitted = len(safe_ledger)
    total = len(ledger)
    return {
        key: report.get(key)
        for key in (
            "schemaVersion",
            "schemaRevision",
            "status",
            "mode",
            "scope",
            "universeRevision",
            "seasonRevision",
            "sourcePolicyRevision",
            "sourcePolicyStatus",
            "asOf",
            "catalogRevision",
            "counts",
            "blockerCodes",
        )
        if report.get(key) not in (None, "", [], {})
    } | {
        "ledger": safe_ledger,
        "diagnostics": {
            "ledgerRowsTotal": total,
            "ledgerRowsEmitted": emitted,
            "truncated": emitted < total,
        },
    }


def build_season_pve_universe(
    policy: dict[str, Any],
    discovery: dict[str, Any],
    staging: dict[str, Any],
    catalog: dict[str, Any],
    *,
    exclusions: list[dict[str, Any]] | None = None,
    mode: str = "current",
) -> dict[str, Any]:
    """Build one fail-closed current or complete End Game PVE report."""

    if mode not in {"current", "end_game"}:
        raise UniverseContractError(
            "mode must be current or end_game"
        )

    for label, value in (
        ("policy", policy),
        ("discovery", discovery),
        ("staging", staging),
        ("catalog", catalog),
    ):
        if not isinstance(value, dict):
            raise UniverseContractError(f"{label} must be an object")

    season_revision = _require_text(policy, "seasonRevision", "source policy")
    source_policy_revision = _require_text(
        policy,
        "sourcePolicyRevision",
        "source policy",
    )
    source_policy_status = _text(policy.get("status")).lower()
    scope = _text(policy.get("scope")) or "current"
    policy_sources = _validated_policy_sources(policy)
    exclusion_index = _validated_exclusions(exclusions)
    as_of = _instant(discovery.get("asOf"), "discovery asOf")
    as_of_raw = _text(discovery.get("asOf"))

    discovered_sources = _index_unique(
        discovery.get("sources"),
        lambda row: _require_text(row, "sourceKey", "discovery source"),
        "discovery sources",
    )
    staging_index = _index_unique(
        staging.get("members"),
        item_relation_key,
        "staging",
    )
    catalog_index = _index_unique(
        catalog.get("members"),
        item_relation_key,
        "catalog",
    )

    ledger: list[dict[str, Any]] = []
    if mode == "end_game" and scope != "end_game":
        ledger.append(
            _contract_ledger_row(
                "ENDGAME_SCOPE_MISMATCH",
                {
                    "owner": "source_policy",
                    "actualScope": scope or "missing",
                },
            )
        )
    if source_policy_status != "approved":
        ledger.append(
            _contract_ledger_row(
                "SOURCE_POLICY_NOT_APPROVED",
                {
                    "owner": "source_policy",
                    "actualStatus": source_policy_status or "missing",
                },
            )
        )
    if not _text(catalog.get("catalogRevision")):
        ledger.append(
            _contract_ledger_row(
                "CATALOG_REVISION_MISSING",
                {"owner": "catalog"},
            )
        )
    revision_inputs = {
        "discovery": _text(discovery.get("seasonRevision")),
        "staging": _text(staging.get("seasonRevision")),
        "catalog": _text(catalog.get("seasonRevision")),
    }
    for owner, revision in sorted(revision_inputs.items()):
        if revision != season_revision:
            ledger.append(
                _contract_ledger_row(
                    "SEASON_REVISION_MISMATCH",
                    {
                        "owner": owner,
                        "expectedRevision": season_revision,
                        "actualRevision": revision or "missing",
                    },
                )
            )
    actual_policy_revision = _text(discovery.get("sourcePolicyRevision"))
    if actual_policy_revision != source_policy_revision:
        ledger.append(
            _contract_ledger_row(
                "SOURCE_POLICY_REVISION_MISMATCH",
                {
                    "owner": "discovery",
                    "expectedRevision": source_policy_revision,
                    "actualRevision": actual_policy_revision or "missing",
                },
            )
        )

    known_policy_source_keys = {
        _text(row.get("sourceKey"))
        for row in policy_sources
    }
    unknown_discovery_sources = sorted(
        set(discovered_sources) - known_policy_source_keys
    )
    for source_key in unknown_discovery_sources:
        ledger.append(
            _contract_ledger_row(
                "DISCOVERY_SOURCE_NOT_IN_POLICY",
                {
                    "owner": "discovery",
                    "sourceKey": source_key,
                },
            )
        )

    active_policy_source_count = 0
    for policy_source in policy_sources:
        source_key = _text(policy_source.get("sourceKey"))
        discovered_source = discovered_sources.get(source_key)
        source_ledger_row = _source_ledger_row(
            policy_source,
            discovered_source,
            as_of=as_of,
            apply_effective_window=mode != "end_game",
        )
        ledger.append(source_ledger_row)
        active_states = {"active"}
        if mode == "end_game":
            active_states.add("end_game")
        if source_ledger_row.get("effectiveWindowState") not in active_states:
            continue
        active_policy_source_count += 1
        if discovered_source is None:
            continue
        for gap in discovered_source.get("gaps") or []:
            if not isinstance(gap, dict):
                raise UniverseContractError(
                    f"{source_key} discovery gap must be an object"
                )
            ledger.append(_gap_ledger_row(source_key, gap))
        raw_members = discovered_source.get("members")
        if isinstance(raw_members, list):
            for raw_member in raw_members:
                if (
                    isinstance(raw_member, dict)
                    and _text(raw_member.get("sourceKey")) != source_key
                ):
                    raise UniverseContractError(
                        "discovery member sourceKey "
                        f"{_text(raw_member.get('sourceKey')) or 'missing'} "
                        f"does not match container {source_key}"
                    )
        members = _index_unique(
            raw_members,
            item_relation_key,
            f"{source_key} discovery members",
        )
        for member_key in sorted(members):
            ledger.append(
                _item_ledger_row(
                    members[member_key],
                    staging_index,
                    catalog_index,
                    exclusion_index,
                )
            )
    if active_policy_source_count == 0:
        ledger.append(
            _contract_ledger_row(
                "NO_ACTIVE_REQUIRED_SOURCES",
                {
                    "owner": "source_policy",
                    "auditInstant": as_of_raw,
                },
            )
        )

    discovered_member_keys = {
        row["memberKey"]
        for row in ledger
        if row.get("memberType") == "item_relation"
    }
    downstream_only_member_keys = sorted(
        (set(staging_index) | set(catalog_index)) - discovered_member_keys
    )
    for member_key in downstream_only_member_keys:
        ledger.append(
            _downstream_orphan_ledger_row(
                member_key,
                staging_index.get(member_key),
                catalog_index.get(member_key),
            )
        )
    unused_exclusions = sorted(set(exclusion_index) - discovered_member_keys)
    for member_key in unused_exclusions:
        ledger.append(
            _contract_ledger_row(
                "EXCLUSION_MEMBER_NOT_DISCOVERED",
                {
                    "owner": "governance",
                    "memberKey": member_key,
                },
            )
        )

    ledger.sort(
        key=lambda row: (
            _text(row.get("memberType")),
            _text(row.get("memberKey")),
        )
    )
    blocker_codes = sorted(
        {
            _text(row.get("reasonCode"))
            for row in ledger
            if row.get("outcome") == "blocked"
            and _text(row.get("reasonCode"))
        }
    )
    counts = {
        "total": len(ledger),
        "included": sum(row.get("outcome") == "included" for row in ledger),
        "excluded": sum(row.get("outcome") == "excluded" for row in ledger),
        "blocked": sum(row.get("outcome") == "blocked" for row in ledger),
        "sourceMembers": sum(
            row.get("memberType") == "source"
            for row in ledger
        ),
        "itemMembers": sum(
            row.get("memberType") == "item_relation"
            for row in ledger
        ),
        "gapMembers": sum(
            row.get("memberType") == "gap"
            for row in ledger
        ),
    }
    status = "blocked" if blocker_codes else "verified"
    canonical_content = {
        "schemaRevision": UNIVERSE_SCHEMA_REVISION,
        "mode": mode,
        "scope": scope,
        "seasonRevision": season_revision,
        "sourcePolicyRevision": source_policy_revision,
        "sourcePolicyStatus": source_policy_status,
        "asOf": as_of_raw,
        "catalogRevision": _text(catalog.get("catalogRevision")),
        "policySources": policy_sources,
        "ledger": ledger,
    }
    return {
        "schemaVersion": 1,
        "schemaRevision": UNIVERSE_SCHEMA_REVISION,
        "status": status,
        "mode": mode,
        "scope": scope,
        "universeRevision": (
            f"{UNIVERSE_REVISION_PREFIX}{_content_hash(canonical_content)}"
        ),
        "seasonRevision": season_revision,
        "sourcePolicyRevision": source_policy_revision,
        "sourcePolicyStatus": source_policy_status,
        "asOf": as_of_raw,
        "catalogRevision": _text(catalog.get("catalogRevision")),
        "counts": counts,
        "blockerCodes": blocker_codes,
        "ledger": ledger,
    }

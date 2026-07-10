#!/usr/bin/env python3
"""Deterministic current-fact Evidence Ledger for canonical gear resolution."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from server.gear_result_envelope import gear_problem


EVIDENCE_LEDGER_CONTRACT_REVISION = "gear-evidence-ledger-v1"
CLAIM_GROUPS = (
    "identity_options",
    "provenance",
    "legality",
    "static_attributes",
    "profile_executability",
)

_CLAIM_STATUSES = {"verified", "blocked"}
_AGGREGATE_DEPENDENCY_PREFIXES = (
    "aggregate:legality",
    "aggregate:static_attributes",
    "aggregate:profile_readiness",
    "aggregate:set_state",
)
_GROUP_ORDER = {group: index for index, group in enumerate(CLAIM_GROUPS)}


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _normalized_ids(values: Iterable[Any]) -> list[str]:
    normalized = {str(value or "").strip() for value in values or []}
    normalized.discard("")
    return sorted(normalized)


def evidence_claim(
    group: str,
    claim_key: str,
    value: Any,
    *,
    status: str,
    source_ref_ids: Iterable[str],
    rule_revision: str,
    resolved_signature: str,
    dependency_vector: dict[str, Any],
    depends_on: Iterable[str] = (),
    problems: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Create one current-fact claim with a stable semantic identity."""

    if group not in CLAIM_GROUPS:
        raise ValueError(f"Unsupported evidence claim group: {group}")
    if status not in _CLAIM_STATUSES:
        raise ValueError(f"Unsupported evidence claim status: {status}")
    normalized_key = str(claim_key or "").strip()
    if not normalized_key:
        raise ValueError("Evidence claim_key is required.")
    normalized_dependencies = _normalized_ids(depends_on)
    if normalized_dependencies and not normalized_key.startswith(_AGGREGATE_DEPENDENCY_PREFIXES):
        raise ValueError("Only approved aggregate claims may declare dependsOn.")
    normalized_sources = _normalized_ids(source_ref_ids)
    canonical_value = _canonical(value)
    canonical_dependency_vector = _canonical(dependency_vector)
    claim_id = _sha256(
        {
            "claimKey": normalized_key,
            "valueDigest": _sha256(canonical_value),
            "sourceRefIds": normalized_sources,
            "ruleRevision": str(rule_revision or "").strip(),
            "resolvedSignature": str(resolved_signature or "").strip(),
            "dependencyVector": canonical_dependency_vector,
        }
    )
    return {
        "claimId": claim_id,
        "claimKey": normalized_key,
        "group": group,
        "status": status,
        "value": canonical_value,
        "sourceRefIds": normalized_sources,
        "ruleRevision": str(rule_revision or "").strip(),
        "resolvedSignature": str(resolved_signature or "").strip(),
        "dependencyVector": canonical_dependency_vector,
        "dependsOn": normalized_dependencies,
        "problems": _canonical(list(problems or [])),
    }


def _claim_sort_key(claim: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _GROUP_ORDER[claim["group"]],
        claim["claimKey"],
        claim["claimId"],
    )


def _assert_dependency_graph(claims_by_id: dict[str, dict[str, Any]]) -> None:
    for claim in claims_by_id.values():
        for dependency in claim.get("dependsOn") or []:
            if dependency not in claims_by_id:
                raise ValueError(
                    f"Evidence claim {claim['claimId']} depends on unknown claim {dependency}."
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(claim_id: str) -> None:
        if claim_id in visiting:
            raise ValueError("Evidence claim dependency cycle detected.")
        if claim_id in visited:
            return
        visiting.add(claim_id)
        for dependency in claims_by_id[claim_id].get("dependsOn") or []:
            visit(dependency)
        visiting.remove(claim_id)
        visited.add(claim_id)

    for claim_id in sorted(claims_by_id):
        visit(claim_id)


def build_evidence_ledger(
    claims: Iterable[dict[str, Any]],
    evidence_records_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build a shallow ordered Ledger and fail claims closed on missing records."""

    if not isinstance(evidence_records_by_id, dict):
        raise ValueError("evidence_records_by_id must be an object.")
    detached_claims = [_canonical(claim) for claim in claims or []]
    claims_by_id: dict[str, dict[str, Any]] = {}
    for claim in detached_claims:
        claim_id = str(claim.get("claimId") or "")
        group = claim.get("group")
        key = str(claim.get("claimKey") or "")
        status = claim.get("status")
        if not claim_id or group not in CLAIM_GROUPS or not key or status not in _CLAIM_STATUSES:
            raise ValueError("Evidence Ledger received a malformed claim.")
        if claim_id in claims_by_id:
            raise ValueError(f"Duplicate evidence claim ID: {claim_id}")
        if claim.get("dependsOn") and not key.startswith(_AGGREGATE_DEPENDENCY_PREFIXES):
            raise ValueError("Only approved aggregate claims may declare dependsOn.")
        claims_by_id[claim_id] = claim

    _assert_dependency_graph(claims_by_id)
    ordered_claims = sorted(claims_by_id.values(), key=_claim_sort_key)
    projected_records: dict[str, dict[str, Any]] = {}
    ledger_problems: list[dict[str, Any]] = []
    for claim in ordered_claims:
        claim_problems = list(claim.get("problems") or [])
        for source_id in _normalized_ids(claim.get("sourceRefIds") or []):
            record = evidence_records_by_id.get(source_id)
            if not isinstance(record, dict) or (
                record.get("id") not in (None, "", source_id)
            ):
                problem = gear_problem(
                    "AUTHORITY_UNAVAILABLE",
                    "EVIDENCE_RECORD_MISSING",
                    "Required evidence record is unavailable.",
                    path=f"evidenceRecordsById.{source_id}",
                    meta={"claimKey": claim["claimKey"], "sourceRefId": source_id},
                )
                claim_problems.append(problem)
                ledger_problems.append(problem)
                claim["status"] = "blocked"
                continue
            projected_records[source_id] = _canonical(record)
        claim["problems"] = _canonical(claim_problems)

    claim_groups = {group: [] for group in CLAIM_GROUPS}
    for claim in ordered_claims:
        claim_groups[claim["group"]].append(claim["claimId"])
    return {
        "contractRevision": EVIDENCE_LEDGER_CONTRACT_REVISION,
        "claims": ordered_claims,
        "claimGroups": claim_groups,
        "evidenceRecordsById": {
            key: projected_records[key] for key in sorted(projected_records)
        },
        "problems": _canonical(ledger_problems),
    }


__all__ = (
    "EVIDENCE_LEDGER_CONTRACT_REVISION",
    "CLAIM_GROUPS",
    "evidence_claim",
    "build_evidence_ledger",
)

#!/usr/bin/env python3
"""Pure contracts and policy for immutable gear/community releases.

The module deliberately owns no persistence, route, environment, clock, file,
network, or process-execution behavior. Callers provide current time, Resolver access,
release registry rows, and dependency revisions explicitly.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any, Callable, Iterable

try:
    from .gear_contracts import parse_selection_intent
except ImportError:
    from gear_contracts import parse_selection_intent


GEAR_RELEASE_SCHEMA_REVISION = "gear-release-v1"
COMMUNITY_RELEASE_SCHEMA_REVISION = "community-release-v1"
ACTIVE_SEASON_MANIFEST_SCHEMA_REVISION = "active-season-manifest-v1"
ACTIVE_MANIFEST_POINTER_COMMAND_REVISION = "active-manifest-pointer-command-v2"

_RELEASE_KINDS = {"gear", "community"}
_RELEASE_STATUSES = {"validated", "degraded", "blocked"}
_PUBLIC_OBSERVED_SOURCE_KEYS = {
    "raiderio_observed_profile",
    "community_best_v2",
}
_CONTROLLED_RISK_CLASSES = {
    "new_season",
    "rule_change",
    "serializer_change",
    "schema_change",
    "capability_change",
    "high_risk_gear",
}
_REQUIRED_DEPENDENCY_REVISIONS = (
    "gearRuleRevision",
    "resolverContractRevision",
    "serializerRevision",
    "simcRuntimeRevision",
    "statPolicyRevision",
    "selectionSchemaRevision",
    "capabilityRevision",
)


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def is_public_observed_source(source_key: Any) -> bool:
    """Return whether one source may participate in public community election."""

    return _text(source_key) in _PUBLIC_OBSERVED_SOURCE_KEYS


def _positive_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0
    return parsed if parsed > 0 else 0


def _issue(code: str, path: str, message: str, kind: str = "RELEASE_INVALID") -> dict[str, str]:
    return {
        "kind": kind,
        "code": code,
        "path": path,
        "message": message,
    }


def _required_text(value: Any, name: str) -> str:
    normalized = _text(value)
    if not normalized or len(normalized) > 512:
        raise ValueError(f"{name} must be a bounded non-empty string")
    return normalized


def _dependency_revisions(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("dependency_revisions must be an object")
    missing = [field for field in _REQUIRED_DEPENDENCY_REVISIONS if not _text(value.get(field))]
    if missing:
        raise ValueError(f"missing dependency revisions: {', '.join(missing)}")
    return _canonical(value)


def _release_identity_payload(release: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaRevision": release.get("schemaRevision"),
        "releaseKind": release.get("releaseKind"),
        "seasonRevision": release.get("seasonRevision"),
        "dependencyRevisions": release.get("dependencyRevisions"),
        "releaseStatus": release.get("releaseStatus"),
        "parentReleaseId": release.get("parentReleaseId") or "",
        "validatedAgainstReleaseId": release.get("validatedAgainstReleaseId") or "",
        "source": release.get("source") or {},
        "content": release.get("content"),
    }


def _expected_release_id(release: dict[str, Any]) -> str:
    return f"{release.get('releaseKind')}-release:sha256:{_sha256(_release_identity_payload(release))}"


def _expected_content_hash(release: dict[str, Any]) -> str:
    return "sha256:" + _sha256({
        "releaseKind": release.get("releaseKind"),
        "content": release.get("content"),
    })


def build_release(
    *,
    release_kind: str,
    season_revision: str,
    schema_revision: str,
    content: Any,
    dependency_revisions: dict[str, Any],
    release_status: str,
    source: dict[str, Any],
    parent_release_id: str = "",
    validated_against_release_id: str = "",
) -> dict[str, Any]:
    """Build one canonical, hash-addressed immutable release descriptor."""

    kind = _text(release_kind)
    if kind not in _RELEASE_KINDS:
        raise ValueError("release_kind must be gear or community")
    status = _text(release_status)
    if status not in _RELEASE_STATUSES:
        raise ValueError("release_status must be validated, degraded, or blocked")
    season = _required_text(season_revision, "season_revision")
    schema = _required_text(schema_revision, "schema_revision")
    parent = _text(parent_release_id)
    validated_against = _text(validated_against_release_id)
    if kind == "gear" and validated_against:
        raise ValueError("gear releases cannot be validated against another release")
    if kind == "community" and not validated_against:
        raise ValueError("community releases require validated_against_release_id")

    release = {
        "schemaRevision": schema,
        "releaseId": "",
        "releaseKind": kind,
        "seasonRevision": season,
        "contentHash": "",
        "dependencyRevisions": _dependency_revisions(dependency_revisions),
        "releaseStatus": status,
        "parentReleaseId": parent,
        "validatedAgainstReleaseId": validated_against,
        "source": _canonical(source if isinstance(source, dict) else {}),
        "content": _canonical(content),
    }
    release["contentHash"] = _expected_content_hash(release)
    release["releaseId"] = _expected_release_id(release)
    return release


def _release_integrity_issues(release: Any, path: str) -> list[dict[str, str]]:
    if not isinstance(release, dict):
        return [_issue("RELEASE_RECORD_INVALID", path, "Release registry row must be an object.")]
    issues: list[dict[str, str]] = []
    kind = _text(release.get("releaseKind"))
    if kind not in _RELEASE_KINDS:
        issues.append(_issue("RELEASE_KIND_INVALID", f"{path}.releaseKind", "Release kind is invalid."))
    if _text(release.get("releaseStatus")) not in _RELEASE_STATUSES:
        issues.append(_issue("RELEASE_STATUS_INVALID", f"{path}.releaseStatus", "Release status is invalid."))
    if _text(release.get("contentHash")) != _expected_content_hash(release):
        issues.append(_issue(
            "RELEASE_CONTENT_HASH_MISMATCH",
            f"{path}.contentHash",
            "Release content does not match its sealed content hash.",
            "RELEASE_INTEGRITY_FAILURE",
        ))
    if kind in _RELEASE_KINDS and _text(release.get("releaseId")) != _expected_release_id(release):
        issues.append(_issue(
            "RELEASE_ID_MISMATCH",
            f"{path}.releaseId",
            "Release descriptor does not match its hash-addressed release ID.",
            "RELEASE_INTEGRITY_FAILURE",
        ))
    return issues


def validate_release(release: Any) -> list[dict[str, str]]:
    """Validate one detached hash-addressed release descriptor."""

    return _release_integrity_issues(release, "release")


def _manifest_identity_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaRevision": manifest.get("schemaRevision"),
        "seasonRevision": manifest.get("seasonRevision"),
        "gearCatalogReleaseId": manifest.get("gearCatalogReleaseId"),
        "communityTemplateReleaseId": manifest.get("communityTemplateReleaseId") or "",
        "talentCatalogRevision": manifest.get("talentCatalogRevision"),
        "dependencyRevisions": manifest.get("dependencyRevisions"),
        "rollbackManifestRevision": manifest.get("rollbackManifestRevision") or "",
        "formalActiveManifest": bool(manifest.get("formalActiveManifest")),
    }


def _expected_manifest_revision(manifest: dict[str, Any]) -> str:
    return "season-manifest:sha256:" + _sha256(_manifest_identity_payload(manifest))


def build_manifest(
    *,
    season_revision: str,
    gear_release: dict[str, Any],
    community_release: dict[str, Any] | None,
    talent_catalog_revision: str,
    dependency_revisions: dict[str, Any],
    rollback_manifest_revision: str = "",
) -> dict[str, Any]:
    """Build a formal immutable Season Manifest without activating it."""

    season = _required_text(season_revision, "season_revision")
    talent_revision = _required_text(talent_catalog_revision, "talent_catalog_revision")
    gear_issues = _release_integrity_issues(gear_release, "gearRelease")
    if gear_issues:
        raise ValueError(gear_issues[0]["message"])
    if gear_release.get("releaseKind") != "gear":
        raise ValueError("gear_release must be a Gear Release")
    if gear_release.get("releaseStatus") == "blocked":
        raise ValueError("blocked Gear Release cannot enter a manifest")
    if gear_release.get("seasonRevision") != season:
        raise ValueError("Gear Release season does not match the manifest")

    community_id = ""
    if community_release is not None:
        community_issues = _release_integrity_issues(community_release, "communityRelease")
        if community_issues:
            raise ValueError(community_issues[0]["message"])
        if community_release.get("releaseKind") != "community":
            raise ValueError("community_release must be a Community Release")
        if community_release.get("releaseStatus") == "blocked":
            raise ValueError("blocked Community Release cannot enter a manifest")
        if community_release.get("seasonRevision") != season:
            raise ValueError("Community Release season does not match the manifest")
        if community_release.get("validatedAgainstReleaseId") != gear_release.get("releaseId"):
            raise ValueError("Community Release is not validated against the manifest Gear Release")
        community_id = _text(community_release.get("releaseId"))

    normalized_dependencies = _dependency_revisions(dependency_revisions)
    for release_name, release in (("Gear", gear_release), ("Community", community_release)):
        if release is None:
            continue
        release_dependencies = release.get("dependencyRevisions") if isinstance(release.get("dependencyRevisions"), dict) else {}
        if any(
            release_dependencies.get(field) != normalized_dependencies.get(field)
            for field in _REQUIRED_DEPENDENCY_REVISIONS
        ):
            raise ValueError(f"{release_name} Release dependencies do not match the manifest")

    manifest = {
        "schemaRevision": ACTIVE_SEASON_MANIFEST_SCHEMA_REVISION,
        "manifestRevision": "",
        "seasonRevision": season,
        "gearCatalogReleaseId": _text(gear_release.get("releaseId")),
        "communityTemplateReleaseId": community_id,
        "talentCatalogRevision": talent_revision,
        "dependencyRevisions": normalized_dependencies,
        "rollbackManifestRevision": _text(rollback_manifest_revision),
        "formalActiveManifest": True,
    }
    manifest["manifestRevision"] = _expected_manifest_revision(manifest)
    return manifest


def validate_manifest(
    manifest: Any,
    releases_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    """Validate one manifest against detached release registry rows."""

    if not isinstance(manifest, dict):
        return [_issue("MANIFEST_INVALID", "manifest", "Manifest must be an object.")]
    issues: list[dict[str, str]] = []
    if manifest.get("schemaRevision") != ACTIVE_SEASON_MANIFEST_SCHEMA_REVISION:
        issues.append(_issue("MANIFEST_SCHEMA_INVALID", "manifest.schemaRevision", "Manifest schema is not supported."))
    if not manifest.get("formalActiveManifest"):
        issues.append(_issue("MANIFEST_NOT_FORMAL", "manifest.formalActiveManifest", "Formal manifest flag is required."))
    if _text(manifest.get("manifestRevision")) != _expected_manifest_revision(manifest):
        issues.append(_issue(
            "MANIFEST_HASH_MISMATCH",
            "manifest.manifestRevision",
            "Manifest fields do not match its immutable revision.",
            "RELEASE_INTEGRITY_FAILURE",
        ))

    registry = releases_by_id if isinstance(releases_by_id, dict) else {}
    manifest_dependencies = manifest.get("dependencyRevisions") if isinstance(manifest.get("dependencyRevisions"), dict) else {}
    gear_id = _text(manifest.get("gearCatalogReleaseId"))
    gear = registry.get(gear_id)
    if not isinstance(gear, dict):
        issues.append(_issue("GEAR_RELEASE_MISSING", "manifest.gearCatalogReleaseId", "Referenced Gear Release is missing.", "AUTHORITY_UNAVAILABLE"))
    else:
        issues.extend(_release_integrity_issues(gear, f"releases.{gear_id}"))
        if gear.get("releaseKind") != "gear":
            issues.append(_issue("GEAR_RELEASE_KIND_INVALID", f"releases.{gear_id}.releaseKind", "Manifest gear reference is not a Gear Release."))
        if gear.get("releaseStatus") == "blocked":
            issues.append(_issue("GEAR_RELEASE_BLOCKED", f"releases.{gear_id}.releaseStatus", "Blocked Gear Release cannot be active."))
        if gear.get("seasonRevision") != manifest.get("seasonRevision"):
            issues.append(_issue("GEAR_RELEASE_SEASON_MISMATCH", f"releases.{gear_id}.seasonRevision", "Gear Release season does not match manifest."))
        gear_dependencies = gear.get("dependencyRevisions") if isinstance(gear.get("dependencyRevisions"), dict) else {}
        if any(
            gear_dependencies.get(field) != manifest_dependencies.get(field)
            for field in _REQUIRED_DEPENDENCY_REVISIONS
        ):
            issues.append(_issue("RELEASE_DEPENDENCY_MISMATCH", f"releases.{gear_id}.dependencyRevisions", "Gear Release dependencies do not match manifest.", "RELEASE_BINDING_MISMATCH"))

    community_id = _text(manifest.get("communityTemplateReleaseId"))
    if community_id:
        community = registry.get(community_id)
        if not isinstance(community, dict):
            issues.append(_issue("COMMUNITY_RELEASE_MISSING", "manifest.communityTemplateReleaseId", "Referenced Community Release is missing.", "AUTHORITY_UNAVAILABLE"))
        else:
            issues.extend(_release_integrity_issues(community, f"releases.{community_id}"))
            if community.get("releaseKind") != "community":
                issues.append(_issue("COMMUNITY_RELEASE_KIND_INVALID", f"releases.{community_id}.releaseKind", "Manifest community reference is not a Community Release."))
            if community.get("releaseStatus") == "blocked":
                issues.append(_issue("COMMUNITY_RELEASE_BLOCKED", f"releases.{community_id}.releaseStatus", "Blocked Community Release cannot be active."))
            if community.get("seasonRevision") != manifest.get("seasonRevision"):
                issues.append(_issue("COMMUNITY_RELEASE_SEASON_MISMATCH", f"releases.{community_id}.seasonRevision", "Community Release season does not match manifest."))
            if community.get("validatedAgainstReleaseId") != gear_id:
                issues.append(_issue(
                    "COMMUNITY_GEAR_RELEASE_MISMATCH",
                    f"releases.{community_id}.validatedAgainstReleaseId",
                    "Community Release is not validated against this Gear Release.",
                    "RELEASE_BINDING_MISMATCH",
                ))
            community_dependencies = community.get("dependencyRevisions") if isinstance(community.get("dependencyRevisions"), dict) else {}
            if any(
                community_dependencies.get(field) != manifest_dependencies.get(field)
                for field in _REQUIRED_DEPENDENCY_REVISIONS
            ):
                issues.append(_issue("RELEASE_DEPENDENCY_MISMATCH", f"releases.{community_id}.dependencyRevisions", "Community Release dependencies do not match manifest.", "RELEASE_BINDING_MISMATCH"))
    return issues


def _parse_timestamp(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.utcoffset() is None:
        return None
    return parsed


def _timestamp_score(value: Any) -> float:
    parsed = _parse_timestamp(value)
    if parsed is None:
        return 0.0
    try:
        return parsed.timestamp()
    except (OverflowError, OSError, ValueError):
        return 0.0


def _candidate_problem(code: str, path: str, message: str) -> dict[str, str]:
    return _issue(code, path, message, "COMMUNITY_CANDIDATE_REJECTED")


def _candidate_source_issues(candidate: dict[str, Any], now: datetime | None) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    source_key = _text(candidate.get("sourceKey"))
    if not is_public_observed_source(source_key):
        issues.append(_candidate_problem("COMMUNITY_SOURCE_NOT_PUBLIC", "candidate.sourceKey", "Only real-player observed sources are public-election eligible."))
    if not _text(candidate.get("sourceUrl")):
        issues.append(_candidate_problem("COMMUNITY_SOURCE_URL_MISSING", "candidate.sourceUrl", "Observed source URL is required."))
    if _positive_int(candidate.get("sampleCount")) <= 0:
        issues.append(_candidate_problem("COMMUNITY_SAMPLE_EVIDENCE_MISSING", "candidate.sampleCount", "Positive sample evidence is required."))
    if not (_text(candidate.get("profileHash")) or _text(candidate.get("gearHash"))):
        issues.append(_candidate_problem("COMMUNITY_SOURCE_HASH_MISSING", "candidate.profileHash", "Profile or gear provenance hash is required."))
    source_status = _text(candidate.get("sourceStatus")).lower()
    if not source_status:
        issues.append(_candidate_problem("COMMUNITY_SOURCE_STATUS_MISSING", "candidate.sourceStatus", "Observed source status is required."))
    elif source_status in {"blocked", "rejected", "expired"}:
        issues.append(_candidate_problem("COMMUNITY_SOURCE_BLOCKED", "candidate.sourceStatus", "Blocked source evidence is not eligible."))
    expires_text = _text(candidate.get("expiresAt"))
    expires = _parse_timestamp(expires_text)
    if not expires_text:
        issues.append(_candidate_problem("COMMUNITY_SOURCE_EXPIRY_MISSING", "candidate.expiresAt", "Observed source expiry is required."))
    elif expires is None:
        issues.append(_candidate_problem("COMMUNITY_SOURCE_EXPIRY_INVALID", "candidate.expiresAt", "Observed source expiry must be a timezone-aware ISO timestamp."))
    elif now is not None and expires <= now:
        issues.append(_candidate_problem("COMMUNITY_SOURCE_STALE", "candidate.expiresAt", "Observed source evidence is expired."))
    return issues


def _candidate_rank(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -_positive_int(row.get("sampleCount")),
        -_timestamp_score(row.get("updatedAt")),
        _text(row.get("candidateId")),
    )


def _resolver_result_issues(result: Any, gear_release_id: str) -> list[dict[str, str]]:
    if not isinstance(result, dict):
        return [_candidate_problem("COMMUNITY_RESOLVER_UNAVAILABLE", "resolver", "Resolver did not return a structured result.")]
    issues: list[dict[str, str]] = []
    legality = result.get("aggregateLegality") if isinstance(result.get("aggregateLegality"), dict) else {}
    if result.get("status") not in {"verified", "resolved"} or legality.get("status") not in {"verified", "legal"}:
        issues.append(_candidate_problem("COMMUNITY_RESOLVER_ILLEGAL", "resolver.aggregateLegality", "Candidate did not pass current legality rules."))
    readiness = result.get("profileReadiness") if isinstance(result.get("profileReadiness"), dict) else {}
    if readiness.get("simcReady") is not True:
        issues.append(_candidate_problem("COMMUNITY_PROFILE_NOT_READY", "resolver.profileReadiness", "Candidate is not serializer/profile ready."))
    dependency = result.get("dependencyVector") if isinstance(result.get("dependencyVector"), dict) else {}
    if _text(dependency.get("gearCatalogReleaseId")) != gear_release_id:
        issues.append(_candidate_problem("COMMUNITY_GEAR_RELEASE_MISMATCH", "resolver.dependencyVector.gearCatalogReleaseId", "Resolver result is bound to a different Gear Release."))
    if not _text(result.get("resolvedGearSignature")):
        issues.append(_candidate_problem("COMMUNITY_RESOLVED_SIGNATURE_MISSING", "resolver.resolvedGearSignature", "Resolved gear signature is required."))
    return issues


def _without_evidence_identity(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_evidence_identity(item)
            for key, item in value.items()
            if key not in {"sourceRefIds", "evidenceClaimIds"}
        }
    if isinstance(value, list):
        return [_without_evidence_identity(item) for item in value]
    return value


def semantic_gear_signature(intent: Any, result: Any) -> str:
    """Hash resolved gear semantics without release-identity-only fields."""

    selection = intent if isinstance(intent, dict) else {}
    snapshot = result if isinstance(result, dict) else {}
    return "sha256:" + hashlib.sha256(
        _canonical_bytes({
            "eligibilityContext": snapshot.get("eligibilityContext") or selection.get("eligibilityContext") or {},
            "resolvedSlots": _without_evidence_identity(snapshot.get("resolvedSlots") or {}),
            "staticAttributes": snapshot.get("staticAttributes") or {},
            "setState": snapshot.get("setState") or {},
            "constraints": snapshot.get("constraints") or {},
            "serializerInput": snapshot.get("serializerInput") or {},
        })
    ).hexdigest()


def _elected_row(candidate: dict[str, Any], intent: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    semantic_signature = semantic_gear_signature(intent, result)
    return {
        "candidateId": _text(candidate.get("id")),
        "classKey": _text(candidate.get("classKey")),
        "specKey": _text(candidate.get("specKey")),
        "role": "eligible",
        "carryForward": bool(candidate.get("carryForward")),
        "sourceKey": _text(candidate.get("sourceKey")),
        "sourceUrl": _text(candidate.get("sourceUrl")),
        "sourceStatus": _text(candidate.get("sourceStatus")),
        "sampleCount": _positive_int(candidate.get("sampleCount")),
        "profileHash": _text(candidate.get("profileHash")),
        "gearHash": _text(candidate.get("gearHash")),
        "updatedAt": _text(candidate.get("updatedAt")),
        "expiresAt": _text(candidate.get("expiresAt")),
        "selectionIntent": _canonical(intent),
        "resolvedGearSignature": _text(result.get("resolvedGearSignature")),
        "semanticGearSignature": semantic_signature,
        "dependencyVector": _canonical(result.get("dependencyVector") or {}),
        "aggregateLegality": _canonical(result.get("aggregateLegality") or {}),
        "profileReadiness": _canonical(result.get("profileReadiness") or {}),
    }


def elect_community_candidates(
    candidates: Iterable[dict[str, Any]],
    *,
    gear_release_id: str,
    resolver: Callable[[dict[str, Any]], dict[str, Any]],
    now: str,
    expected_specs: Iterable[tuple[str, str]],
) -> dict[str, Any]:
    """Revalidate observed candidates and deterministically elect public winners."""

    target_release = _required_text(gear_release_id, "gear_release_id")
    current_time = _parse_timestamp(now)
    if current_time is None:
        raise ValueError("now must be an ISO timestamp")
    expected = sorted({(_text(class_key), _text(spec_key)) for class_key, spec_key in expected_specs})
    eligible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    candidate_rows = [_canonical(row) for row in candidates if isinstance(row, dict)]
    candidate_rows.sort(key=lambda row: _text(row.get("id")))
    for candidate in candidate_rows:
        candidate_id = _text(candidate.get("id"))
        class_key = _text(candidate.get("classKey"))
        spec_key = _text(candidate.get("specKey"))
        problems = _candidate_source_issues(candidate, current_time)
        intent, intent_issues = parse_selection_intent(candidate.get("selectionIntent"))
        problems.extend(intent_issues)
        if intent is not None:
            eligibility = intent.get("eligibilityContext") or {}
            if eligibility.get("classKey") != class_key or eligibility.get("specKey") != spec_key:
                problems.append(_candidate_problem("COMMUNITY_INTENT_SPEC_MISMATCH", "candidate.selectionIntent.eligibilityContext", "Intent class/spec does not match the candidate slot."))
            authored = intent.get("authoredAgainst") or {}
            if authored.get("gearCatalogRevision") != target_release:
                problems.append(_candidate_problem("COMMUNITY_GEAR_RELEASE_MISMATCH", "candidate.selectionIntent.authoredAgainst.gearCatalogRevision", "Intent is not authored against the target Gear Release."))
        if (class_key, spec_key) not in expected:
            problems.append(_candidate_problem("COMMUNITY_SPEC_NOT_EXPECTED", "candidate.specKey", "Candidate spec is not part of the expected retail matrix."))

        result: dict[str, Any] | None = None
        if not problems and intent is not None:
            try:
                result = resolver(_canonical(intent))
            except Exception:
                result = None
            problems.extend(_resolver_result_issues(result, target_release))

        if problems or intent is None or result is None:
            rejected.append({
                "candidateId": candidate_id,
                "classKey": class_key,
                "specKey": spec_key,
                "role": "rejected",
                "problems": _canonical(problems),
            })
            continue
        eligible.append(_elected_row(candidate, intent, result))

    by_spec: dict[tuple[str, str], list[dict[str, Any]]] = {spec: [] for spec in expected}
    for row in eligible:
        by_spec.setdefault((row["classKey"], row["specKey"]), []).append(row)

    winners: list[dict[str, Any]] = []
    standbys: list[dict[str, Any]] = []
    missing_specs: list[dict[str, str]] = []
    for class_key, spec_key in expected:
        ranked = sorted(by_spec.get((class_key, spec_key), []), key=_candidate_rank)
        if not ranked:
            missing_specs.append({"classKey": class_key, "specKey": spec_key})
            continue
        winner = {**ranked[0], "role": "winner"}
        winners.append(winner)
        standbys.extend({**row, "role": "standby"} for row in ranked[1:])

    rejected.sort(key=lambda row: (row["classKey"], row["specKey"], row["candidateId"]))
    return {
        "schemaRevision": "community-election-v1",
        "gearReleaseId": target_release,
        "status": "validated" if not missing_specs else "degraded",
        "expectedSpecCount": len(expected),
        "winnerSpecCount": len(winners),
        "winners": winners,
        "standbys": standbys,
        "rejected": rejected,
        "missingSpecs": missing_specs,
    }


def _spec_key(row: dict[str, Any]) -> tuple[str, str]:
    return (_text(row.get("classKey")), _text(row.get("specKey")))


def _selection_semantics(intent: Any) -> Any:
    if not isinstance(intent, dict):
        return {}
    return _canonical({
        "schemaRevision": intent.get("schemaRevision"),
        "eligibilityContext": intent.get("eligibilityContext"),
        "slots": intent.get("slots"),
    })


def _shadow_blocker(code: str, class_key: str, spec_key: str, message: str) -> dict[str, str]:
    return _issue(code, f"specs.{class_key}.{spec_key}", message, "SHADOW_COMPARE_BLOCKED")


def compare_shadow(
    legacy_winners: Iterable[dict[str, Any]],
    candidate_winners: Iterable[dict[str, Any]],
    *,
    expected_specs: Iterable[tuple[str, str]],
    gear_release_id: str,
    allow_semantic_changes: bool = False,
    allowed_semantic_change_specs: Iterable[tuple[str, str]] = (),
) -> dict[str, Any]:
    """Compare old/new public winners while separating release-only signature churn."""

    target_release = _required_text(gear_release_id, "gear_release_id")
    expected = sorted({(_text(class_key), _text(spec_key)) for class_key, spec_key in expected_specs})
    expected_set = set(expected)
    allowed_change_specs = {
        (_text(class_key), _text(spec_key))
        for class_key, spec_key in allowed_semantic_change_specs
        if _text(class_key) and _text(spec_key)
    }
    blockers: list[dict[str, str]] = []
    diffs: list[dict[str, Any]] = []

    def index_rows(rows: Iterable[dict[str, Any]], label: str) -> dict[tuple[str, str], dict[str, Any]]:
        indexed: dict[tuple[str, str], dict[str, Any]] = {}
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            row = _canonical(raw)
            key = _spec_key(row)
            if key in indexed:
                blockers.append(_shadow_blocker("DUPLICATE_PUBLIC_WINNER", *key, f"{label} has multiple public winners for one spec."))
            indexed[key] = row
        return indexed

    legacy = index_rows(legacy_winners, "legacy")
    candidate = index_rows(candidate_winners, "candidate")
    for class_key, spec_key in sorted(set(candidate).difference(expected_set)):
        blockers.append(_shadow_blocker("UNEXPECTED_PUBLIC_SPEC", class_key, spec_key, "Candidate exposes a public winner outside the expected matrix."))

    empty_specs: list[dict[str, str]] = []
    for class_key, spec_key in expected:
        key = (class_key, spec_key)
        old = legacy.get(key)
        new = candidate.get(key)
        if new is None:
            empty_specs.append({"classKey": class_key, "specKey": spec_key})
            diffs.append({"classKey": class_key, "specKey": spec_key, "classification": "candidate_empty"})
            continue

        if _text(new.get("sourceKey")) not in _PUBLIC_OBSERVED_SOURCE_KEYS:
            blockers.append(_shadow_blocker("PUBLIC_SOURCE_NOT_OBSERVED", class_key, spec_key, "Candidate public winner is not real-player observed."))
        if _positive_int(new.get("baselineCount")) != 0:
            blockers.append(_shadow_blocker("PUBLIC_BASELINE_LEAK", class_key, spec_key, "Public baseline count must remain zero."))
        if _text(new.get("aggregateLegality")) not in {"verified", "legal"}:
            blockers.append(_shadow_blocker("PUBLIC_WINNER_ILLEGAL", class_key, spec_key, "Candidate public winner is not legal."))
        if _text(new.get("validatedAgainstGearReleaseId")) != target_release:
            blockers.append(_shadow_blocker("COMMUNITY_GEAR_RELEASE_MISMATCH", class_key, spec_key, "Candidate winner is bound to a different Gear Release."))
        if not (_text(new.get("profileHash")) or _text(new.get("gearHash"))):
            blockers.append(_shadow_blocker("PUBLIC_PROVENANCE_HASH_MISSING", class_key, spec_key, "Candidate winner has no profile or gear provenance hash."))

        if old is None:
            classification = "new_winner"
            semantic_changed = True
        else:
            old_semantic = _text(old.get("semanticGearSignature")) or _text(old.get("resolvedGearSignature"))
            new_semantic = _text(new.get("semanticGearSignature")) or _text(new.get("resolvedGearSignature"))
            selection_changed = _selection_semantics(old.get("selectionIntent")) != _selection_semantics(new.get("selectionIntent"))
            provenance_changed = any(
                old.get(field) != new.get(field)
                for field in ("sourceKey", "sourceUrl", "gearHash", "sampleCount")
            )
            old_profile_hash = _text(old.get("profileHash"))
            new_profile_hash = _text(new.get("profileHash"))
            if old_profile_hash and new_profile_hash and old_profile_hash != new_profile_hash:
                provenance_changed = True
            resolved_semantic_changed = selection_changed or old_semantic != new_semantic
            semantic_changed = resolved_semantic_changed or provenance_changed
            resolved_changed = old.get("resolvedGearSignature") != new.get("resolvedGearSignature")
            expected_enhancement_migration = (
                resolved_semantic_changed
                and not provenance_changed
                and key in allowed_change_specs
            )
            if expected_enhancement_migration:
                classification = "expected_enhancement_migration"
            elif semantic_changed:
                classification = "semantic_change"
            elif resolved_changed:
                classification = "revision_only"
            else:
                classification = "match"
        diffs.append({"classKey": class_key, "specKey": spec_key, "classification": classification})
        if (
            semantic_changed
            and not allow_semantic_changes
            and classification != "expected_enhancement_migration"
        ):
            blockers.append(_shadow_blocker("PUBLIC_WINNER_SEMANTIC_CHANGE", class_key, spec_key, "Candidate winner differs from the accepted public winner."))

    status = "blocked" if blockers else ("degraded" if empty_specs else "pass")
    return {
        "schemaRevision": "gear-release-shadow-report-v1",
        "status": status,
        "gearReleaseId": target_release,
        "expectedSpecCount": len(expected),
        "candidateWinnerCount": sum(1 for spec in expected if spec in candidate),
        "diffs": diffs,
        "emptySpecs": empty_specs,
        "blockers": blockers,
    }


def decide_promotion(
    *,
    risk_class: str,
    shadow_report: dict[str, Any],
    coverage_regressions: Iterable[dict[str, Any]],
    full_matrix_passed: bool,
) -> dict[str, Any]:
    """Return a pure risk-classified promotion decision."""

    risk = _text(risk_class)
    blockers = list(_canonical((shadow_report or {}).get("blockers") or []))
    regressions = list(_canonical(list(coverage_regressions or [])))
    if regressions:
        blockers.append(_issue("LEGAL_WINNER_COVERAGE_REGRESSION", "promotion.coverage", "A still-legal active winner would be lost.", "PROMOTION_BLOCKED"))
    if not full_matrix_passed:
        blockers.append(_issue("FULL_MATRIX_REQUIRED", "promotion.fullMatrix", "The required full regression matrix did not pass.", "PROMOTION_BLOCKED"))
    shadow_status = _text((shadow_report or {}).get("status"))
    if shadow_status == "blocked" and not blockers:
        blockers.append(_issue("SHADOW_COMPARE_BLOCKED", "promotion.shadow", "Shadow comparison blocked promotion.", "PROMOTION_BLOCKED"))
    elif shadow_status not in {"pass", "degraded"}:
        blockers.append(_issue("SHADOW_COMPARE_REQUIRED", "promotion.shadow", "A completed shadow comparison is required.", "PROMOTION_BLOCKED"))

    if blockers:
        decision = "blocked"
    elif risk in {"same_gear_community", "low_risk_additive_gear"}:
        decision = "auto_promote"
    else:
        decision = "manual_required"
    return {
        "schemaRevision": "gear-release-promotion-decision-v1",
        "riskClass": risk,
        "decision": decision,
        "controlledCutover": risk in _CONTROLLED_RISK_CLASSES or decision == "manual_required",
        "blockers": blockers,
        "coverageRegressions": regressions,
    }


def build_pointer_command(
    action: str,
    manifest_revision: str,
    expected_generation: int,
    rollback_manifest_revision: str = "",
    *,
    target_mode: str = "active",
) -> dict[str, Any]:
    """Build an exact compare-and-swap pointer mutation intent."""

    normalized_action = _text(action)
    if normalized_action not in {"promote", "rollback"}:
        raise ValueError("action must be promote or rollback")
    normalized_mode = _text(target_mode)
    if normalized_mode not in {"active", "transitional"}:
        raise ValueError("target_mode must be active or transitional")
    manifest = _text(manifest_revision)
    rollback_manifest = _text(rollback_manifest_revision)
    if normalized_mode == "active" and not manifest:
        raise ValueError("active pointer command requires manifest_revision")
    if normalized_mode == "transitional":
        if normalized_action != "rollback":
            raise ValueError("only rollback may target transitional mode")
        if manifest:
            raise ValueError("transitional pointer command must not carry manifest_revision")
        if rollback_manifest:
            raise ValueError("transitional pointer command must not carry rollback_manifest_revision")
    if isinstance(expected_generation, bool) or not isinstance(expected_generation, int) or expected_generation < 0:
        raise ValueError("expected_generation must be a non-negative integer")
    return {
        "schemaRevision": ACTIVE_MANIFEST_POINTER_COMMAND_REVISION,
        "action": normalized_action,
        "environment": "retail",
        "targetMode": normalized_mode,
        "manifestRevision": manifest,
        "expectedGeneration": expected_generation,
        "rollbackManifestRevision": rollback_manifest,
    }


def validate_capability_proof(proof: Any) -> dict[str, Any]:
    """Keep Catalyst disabled unless the complete approved proof matrix passes."""

    value = proof if isinstance(proof, dict) else {}
    required = (
        "overlayPolicyVerified",
        "resolverFixtureVerified",
        "serializerFixtureVerified",
        "simcRuntimeFixtureVerified",
        "frontendExplanationVerified",
        "manifestRevisionBound",
    )
    missing = [field for field in required if value.get(field) is not True]
    enabled = not missing
    blockers = [] if enabled else ["CATALYST_PROOF_MATRIX_INCOMPLETE"]
    return {
        "schemaRevision": "gear-capability-proof-result-v1",
        "capabilityKey": _text(value.get("capabilityKey")),
        "status": "verified" if enabled else "blocked",
        "capabilityEnabled": enabled,
        "parserAllowlisted": value.get("parserAllowlisted") is True,
        "missingProofs": missing,
        "blockers": blockers,
    }


__all__ = [
    "ACTIVE_MANIFEST_POINTER_COMMAND_REVISION",
    "ACTIVE_SEASON_MANIFEST_SCHEMA_REVISION",
    "COMMUNITY_RELEASE_SCHEMA_REVISION",
    "GEAR_RELEASE_SCHEMA_REVISION",
    "build_manifest",
    "build_pointer_command",
    "build_release",
    "compare_shadow",
    "decide_promotion",
    "elect_community_candidates",
    "is_public_observed_source",
    "semantic_gear_signature",
    "validate_capability_proof",
    "validate_release",
    "validate_manifest",
]

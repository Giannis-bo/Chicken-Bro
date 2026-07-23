#!/usr/bin/env python3
"""Pure deterministic contracts for projections compiled from observed builds."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

try:
    from .observed_build_registry import slot_key, validate_observed_snapshot
except ImportError:
    from observed_build_registry import slot_key, validate_observed_snapshot


OBSERVED_BUILD_PROJECTION_SCHEMA_REVISION = "observed-build-projection-v2"
OBSERVED_BUILD_PROJECTION_ID_PREFIX = "build-projection:sha256:"

_DEPENDENCY_INPUT_FIELDS = (
    ("season_revision", "seasonRevision"),
    ("talent_catalog_revision", "talentCatalogRevision"),
    ("gear_release_id", "gearReleaseId"),
    ("gear_rule_revision", "gearRuleRevision"),
    ("resolver_contract_revision", "resolverContractRevision"),
    ("serializer_revision", "serializerRevision"),
    ("simc_runtime_revision", "simcRuntimeRevision"),
    ("selection_schema_revision", "selectionSchemaRevision"),
    ("projection_schema_revision", "projectionSchemaRevision"),
)
_DEPENDENCY_FIELDS = tuple(output for _, output in _DEPENDENCY_INPUT_FIELDS)
_PROJECTION_ID_PATTERN = re.compile(r"build-projection:sha256:[0-9a-f]{64}")
_SNAPSHOT_ID_PATTERN = re.compile(r"observed-build:sha256:[0-9a-f]{64}")
_SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")


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


def _required_text(value: Any, name: str) -> str:
    normalized = _text(value)
    if not normalized or len(normalized) > 512:
        raise ValueError(f"{name} must be a bounded non-empty string")
    return normalized


def build_dependency_vector(
    *,
    season_revision: str,
    talent_catalog_revision: str,
    gear_release_id: str,
    gear_rule_revision: str,
    resolver_contract_revision: str,
    serializer_revision: str,
    simc_runtime_revision: str,
    selection_schema_revision: str,
    projection_schema_revision: str,
) -> dict[str, str]:
    """Build the complete authority vector used by one projection."""

    values = locals()
    return {
        output: _required_text(values[input_name], input_name)
        for input_name, output in _DEPENDENCY_INPUT_FIELDS
    }


def _dependency_vector(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("dependency_vector must be an object")
    if set(value) != set(_DEPENDENCY_FIELDS):
        raise ValueError("dependency_vector must contain exactly the authority fields")
    normalized: dict[str, str] = {}
    for field in _DEPENDENCY_FIELDS:
        normalized[field] = _required_text(value.get(field), field)
    return normalized


def _problems(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError("problems must be a list")
    normalized: list[dict[str, Any]] = []
    for index, problem in enumerate(value):
        if not isinstance(problem, dict) or not _text(problem.get("code")):
            raise ValueError(f"problems[{index}].code must be a bounded non-empty string")
        normalized.append(_canonical(problem))
    return normalized


def _projection_ready(
    talent_projection: dict[str, Any],
    gear_projection: dict[str, Any],
    profile_readiness: dict[str, Any],
    problems: list[dict[str, Any]],
) -> bool:
    return (
        talent_projection.get("status") == "verified"
        and gear_projection.get("status") == "verified"
        and profile_readiness.get("status") == "verified"
        and profile_readiness.get("simcReady") is True
        and not problems
    )


def _identity_payload(projection: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaRevision": projection.get("schemaRevision"),
        "snapshotId": projection.get("snapshotId"),
        "sourceIdentity": projection.get("sourceIdentity"),
        "slot": projection.get("slot"),
        "dependencyVector": projection.get("dependencyVector"),
        "talentProjection": projection.get("talentProjection"),
        "gearProjection": projection.get("gearProjection"),
        "profileReadiness": projection.get("profileReadiness"),
        "status": projection.get("status"),
        "importable": projection.get("importable"),
        "problems": projection.get("problems"),
    }


def _expected_projection_id(projection: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_bytes(_identity_payload(projection))).hexdigest()
    return OBSERVED_BUILD_PROJECTION_ID_PREFIX + digest


def build_projection(
    *,
    snapshot: dict[str, Any],
    dependency_vector: dict[str, Any],
    talent_projection: dict[str, Any],
    gear_projection: dict[str, Any],
    profile_readiness: dict[str, Any],
    problems: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    """Seal one deterministic verified or blocked projection."""

    snapshot_issues = validate_observed_snapshot(snapshot)
    if snapshot_issues:
        raise ValueError(
            "snapshot integrity failed: "
            + ", ".join(issue["code"] for issue in snapshot_issues)
        )
    normalized_dependencies = _dependency_vector(dependency_vector)
    normalized_talent = _canonical(
        talent_projection if isinstance(talent_projection, dict) else {}
    )
    normalized_gear = _canonical(
        gear_projection if isinstance(gear_projection, dict) else {}
    )
    normalized_readiness = _canonical(
        profile_readiness if isinstance(profile_readiness, dict) else {}
    )
    normalized_problems = _problems(problems)
    ready = _projection_ready(
        normalized_talent,
        normalized_gear,
        normalized_readiness,
        normalized_problems,
    )
    if not ready and not normalized_problems:
        normalized_problems = [
            {
                "code": "projection_not_ready",
                "stage": "projection",
                "message": "Talent, gear, and profile readiness must all be verified.",
            }
        ]
    source_identity = _text(
        (snapshot.get("source") or {}).get("sourceIdentity")
    )
    if not source_identity.startswith("raiderio:"):
        raise ValueError("snapshot sourceIdentity must be a Raider.IO identity")
    projection = {
        "schemaRevision": OBSERVED_BUILD_PROJECTION_SCHEMA_REVISION,
        "projectionId": "",
        "snapshotId": snapshot["snapshotId"],
        "sourceIdentity": source_identity,
        "slot": _canonical(snapshot["slot"]),
        "slotKey": slot_key(snapshot["slot"]),
        "dependencyHash": _sha256(normalized_dependencies),
        "dependencyVector": normalized_dependencies,
        "talentProjection": normalized_talent,
        "gearProjection": normalized_gear,
        "profileReadiness": normalized_readiness,
        "status": "verified" if ready else "blocked",
        "importable": ready,
        "problems": normalized_problems,
    }
    projection["projectionId"] = _expected_projection_id(projection)
    return projection


def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def validate_projection(projection: Any) -> list[dict[str, str]]:
    """Return detached projection integrity issues."""

    if not isinstance(projection, dict):
        return [_issue("PROJECTION_INVALID", "projection", "Projection must be an object.")]
    issues: list[dict[str, str]] = []
    if projection.get("schemaRevision") != OBSERVED_BUILD_PROJECTION_SCHEMA_REVISION:
        issues.append(
            _issue(
                "PROJECTION_SCHEMA_INVALID",
                "projection.schemaRevision",
                "Projection schema revision is unsupported.",
            )
        )
    if not _SNAPSHOT_ID_PATTERN.fullmatch(_text(projection.get("snapshotId"))):
        issues.append(
            _issue(
                "PROJECTION_SNAPSHOT_ID_INVALID",
                "projection.snapshotId",
                "Projection snapshot ID is invalid.",
            )
        )
    if not _text(projection.get("sourceIdentity")).startswith("raiderio:"):
        issues.append(
            _issue(
                "PROJECTION_SOURCE_IDENTITY_INVALID",
                "projection.sourceIdentity",
                "Projection source identity must be a Raider.IO identity.",
            )
        )
    try:
        actual_slot_key = slot_key(projection.get("slot"))
    except ValueError as error:
        actual_slot_key = ""
        issues.append(
            _issue(
                "PROJECTION_SLOT_INVALID",
                "projection.slot",
                str(error),
            )
        )
    if actual_slot_key != _text(projection.get("slotKey")):
        issues.append(
            _issue(
                "PROJECTION_SLOT_MISMATCH",
                "projection.slotKey",
                "Projection slot key does not match its exact slot.",
            )
        )
    try:
        dependencies = _dependency_vector(projection.get("dependencyVector"))
    except ValueError as error:
        dependencies = {}
        issues.append(
            _issue(
                "PROJECTION_DEPENDENCIES_INVALID",
                "projection.dependencyVector",
                str(error),
            )
        )
    if dependencies:
        expected_dependency_hash = _sha256(dependencies)
        if (
            not _SHA256_PATTERN.fullmatch(_text(projection.get("dependencyHash")))
            or projection.get("dependencyHash") != expected_dependency_hash
        ):
            issues.append(
                _issue(
                    "PROJECTION_DEPENDENCY_HASH_MISMATCH",
                    "projection.dependencyHash",
                    "Projection dependency vector does not match its hash.",
                )
            )
    projection_parts: dict[str, dict[str, Any]] = {}
    for field in ("talentProjection", "gearProjection", "profileReadiness"):
        value = projection.get(field)
        if not isinstance(value, dict):
            issues.append(
                _issue(
                    "PROJECTION_PART_INVALID",
                    f"projection.{field}",
                    f"{field} must be an object.",
                )
            )
            projection_parts[field] = {}
        else:
            projection_parts[field] = value
    raw_problems = projection.get("problems")
    if not isinstance(raw_problems, list):
        issues.append(
            _issue(
                "PROJECTION_PROBLEMS_INVALID",
                "projection.problems",
                "Projection problems must be a list.",
            )
        )
        normalized_problems: list[dict[str, Any]] = []
    else:
        try:
            normalized_problems = _problems(raw_problems)
        except ValueError as error:
            normalized_problems = []
            issues.append(
                _issue(
                    "PROJECTION_PROBLEMS_INVALID",
                    "projection.problems",
                    str(error),
                )
            )
    ready = _projection_ready(
        projection_parts["talentProjection"],
        projection_parts["gearProjection"],
        projection_parts["profileReadiness"],
        normalized_problems,
    )
    expected_status = "verified" if ready else "blocked"
    if (
        projection.get("status") != expected_status
        or projection.get("importable") is not ready
    ):
        issues.append(
            _issue(
                "PROJECTION_STATUS_MISMATCH",
                "projection.status",
                "Projection status does not match readiness.",
            )
        )
    expected_projection_id = _expected_projection_id(projection)
    if (
        not _PROJECTION_ID_PATTERN.fullmatch(_text(projection.get("projectionId")))
        or projection.get("projectionId") != expected_projection_id
    ):
        issues.append(
            _issue(
                "PROJECTION_ID_MISMATCH",
                "projection.projectionId",
                "Projection content does not match its content-addressed ID.",
            )
        )
    return issues


def publication_change_kind(
    active_vector: dict[str, Any],
    candidate_vector: dict[str, Any],
) -> str:
    """Classify whether one candidate is observed-only or a dependency cutover."""

    active = _dependency_vector(active_vector)
    candidate = _dependency_vector(candidate_vector)
    return "observed_only" if active == candidate else "dependency_cutover"


__all__ = (
    "OBSERVED_BUILD_PROJECTION_ID_PREFIX",
    "OBSERVED_BUILD_PROJECTION_SCHEMA_REVISION",
    "build_dependency_vector",
    "build_projection",
    "publication_change_kind",
    "validate_projection",
)

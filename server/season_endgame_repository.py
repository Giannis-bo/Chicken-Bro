"""Canonical identity and validation for the Midnight Season 2 End Game repository."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping


REPOSITORY_SCHEMA_REVISION = "season-endgame-repository-v1"
ENDGAME_SEASON_ID = "midnight-season-2"
ENDGAME_SCOPE = "end_game"
SEASON_REVISION_PREFIX = "season-midnight-season-2:"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, set):
        return sorted(_canonical(item) for item in value)
    return value


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _canonical(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _revision(value: Any) -> str:
    digest = hashlib.sha256(_canonical_bytes(value)).hexdigest()
    return f"{SEASON_REVISION_PREFIX}{digest}"


def _problem(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _capture_files(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, Mapping):
        return []
    rows = value.get("files")
    if not isinstance(rows, list):
        return []
    result = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        result.append({
            "path": _text(row.get("path")),
            "sha256": _text(row.get("sha256")).lower(),
        })
    return result


def validate_endgame_binding(value: Any) -> list[dict[str, str]]:
    """Return stable problems for an S2 End Game repository binding."""

    if not isinstance(value, Mapping):
        return [_problem(
            "S2_BINDING_MALFORMED",
            "binding",
            "S2 repository binding must be an object.",
        )]

    problems: list[dict[str, str]] = []
    if _text(value.get("seasonId")) != ENDGAME_SEASON_ID:
        problems.append(_problem(
            "S2_SEASON_ID_UNSUPPORTED",
            "seasonId",
            "S2 repository binding must use midnight-season-2.",
        ))
    if _text(value.get("scope")) != ENDGAME_SCOPE:
        problems.append(_problem(
            "S2_SCOPE_UNSUPPORTED",
            "scope",
            "S2 repository binding must use the complete end_game scope.",
        ))
    revision = _text(value.get("seasonRevision"))
    if not revision.startswith(SEASON_REVISION_PREFIX):
        problems.append(_problem(
            "S2_SEASON_REVISION_MISSING",
            "seasonRevision",
            "S2 repository binding must carry a generated season revision.",
        ))
    if not _text(value.get("sourcePolicyRevision")):
        problems.append(_problem(
            "S2_SOURCE_POLICY_REVISION_MISSING",
            "sourcePolicyRevision",
            "S2 repository binding must carry the source policy revision.",
        ))
    if not _text(value.get("captureRevision")):
        problems.append(_problem(
            "S2_CAPTURE_REVISION_MISSING",
            "captureRevision",
            "S2 repository binding must carry the capture revision.",
        ))
    if not _text(value.get("clientBuild")):
        problems.append(_problem(
            "S2_CAPTURE_IDENTITY_MISSING",
            "clientBuild",
            "S2 repository binding requires an official/client build.",
        ))
    if not _text(value.get("simcRuntimeRevision")):
        problems.append(_problem(
            "S2_CAPTURE_IDENTITY_MISSING",
            "simcRuntimeRevision",
            "S2 repository binding requires a SimC runtime revision.",
        ))

    sources = value.get("sourceKeys")
    if not isinstance(sources, list) or not sources or any(
        not _text(source) for source in sources
    ):
        problems.append(_problem(
            "S2_SOURCE_POLICY_EMPTY",
            "sourceKeys",
            "S2 End Game repository requires at least one source key.",
        ))

    files = _capture_files(value.get("captureManifest"))
    if not files:
        problems.append(_problem(
            "S2_CAPTURE_IDENTITY_MISSING",
            "captureManifest.files",
            "S2 repository binding requires checksummed capture files.",
        ))
    for index, row in enumerate(files):
        if not row["path"] or not _SHA256_PATTERN.fullmatch(row["sha256"]):
            problems.append(_problem(
                "S2_CAPTURE_CHECKSUM_INVALID",
                f"captureManifest.files[{index}]",
                "Every S2 capture file requires a path and SHA-256 checksum.",
            ))
    return problems


def build_endgame_binding(
    *,
    season_id: str,
    season_metadata: Mapping[str, Any],
    source_policy: Mapping[str, Any],
    capture_manifest: Mapping[str, Any],
    client_build: str,
    simc_runtime_revision: str,
) -> dict[str, Any]:
    """Build one deterministic S2 End Game repository identity."""

    metadata = dict(season_metadata) if isinstance(season_metadata, Mapping) else {}
    policy = dict(source_policy) if isinstance(source_policy, Mapping) else {}
    capture = dict(capture_manifest) if isinstance(capture_manifest, Mapping) else {}
    source_rows = policy.get("sources")
    source_keys = sorted({
        _text(row.get("sourceKey"))
        for row in source_rows
        if isinstance(row, Mapping) and _text(row.get("sourceKey"))
    }) if isinstance(source_rows, list) else []

    identity = {
        "schemaRevision": REPOSITORY_SCHEMA_REVISION,
        "seasonId": _text(season_id),
        "scope": ENDGAME_SCOPE,
        "seasonMetadata": metadata,
        "sourcePolicyRevision": _text(policy.get("sourcePolicyRevision")),
        "sourceKeys": source_keys,
        "captureRevision": _text(capture.get("captureRevision")),
        "captureFiles": _capture_files(capture),
        "clientBuild": _text(client_build),
        "simcRuntimeRevision": _text(simc_runtime_revision),
    }
    binding = {
        "schemaRevision": REPOSITORY_SCHEMA_REVISION,
        "seasonId": ENDGAME_SEASON_ID,
        "scope": ENDGAME_SCOPE,
        "seasonRevision": _revision(identity),
        "sourcePolicyRevision": identity["sourcePolicyRevision"],
        "sourceKeys": source_keys,
        "captureRevision": identity["captureRevision"],
        "captureManifest": capture,
        "captureContext": {
            "seasonMetadata": metadata,
            "clientBuild": identity["clientBuild"],
            "simcRuntimeRevision": identity["simcRuntimeRevision"],
        },
        "clientBuild": identity["clientBuild"],
        "simcRuntimeRevision": identity["simcRuntimeRevision"],
    }
    problems = []
    if _text(season_id) != ENDGAME_SEASON_ID:
        problems.append(_problem(
            "S2_SEASON_ID_UNSUPPORTED",
            "seasonId",
            "S2 repository builder only accepts midnight-season-2.",
        ))
    if _text(policy.get("scope")) != ENDGAME_SCOPE:
        problems.append(_problem(
            "S2_SCOPE_UNSUPPORTED",
            "sourcePolicy.scope",
            "S2 source policy must declare the end_game scope.",
        ))
    problems.extend(validate_endgame_binding(binding))
    deduped = []
    seen = set()
    for problem in problems:
        identity_key = (problem["code"], problem["path"], problem["message"])
        if identity_key not in seen:
            seen.add(identity_key)
            deduped.append(problem)
    binding["status"] = "verified" if not deduped else "blocked"
    binding["problems"] = deduped
    return binding


__all__ = (
    "ENDGAME_SCOPE",
    "ENDGAME_SEASON_ID",
    "REPOSITORY_SCHEMA_REVISION",
    "SEASON_REVISION_PREFIX",
    "build_endgame_binding",
    "validate_endgame_binding",
)

#!/usr/bin/env python3
"""Assemble the S2 Gear Release, Catalog, and Exact candidate without promotion."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import gear_release_tool  # noqa: E402
from server.season_endgame_candidate import build_season_endgame_candidate  # noqa: E402
from server.season_endgame_repository import build_endgame_binding  # noqa: E402
from server.s2_equipment_library_candidate import (  # noqa: E402
    build_s2_option_catalog,
    build_s2_set_membership,
    build_s2_track_authority,
    project_s2_catalog_rows,
)
from server.s2_community_exact import (  # noqa: E402
    merge_s2_community_exact_snapshot,
    select_s2_bindable_community_templates,
)


def _text(value: Any) -> str:
    return str(value or "").strip()


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


def _load_json(path: Path) -> Any:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def _atomic_json_write(path: Path, payload: Mapping[str, Any]) -> None:
    target = path.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = handle.name
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        temporary = ""
    finally:
        if temporary:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.expanduser().resolve().open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _templates(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    value = _load_json(path)
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    if isinstance(value, Mapping):
        rows = value.get("templates") or value.get("communityTemplates") or []
        return [dict(row) for row in rows if isinstance(row, Mapping)]
    return []


def _community_staging(path: Path | None) -> tuple[Mapping[str, Any] | None, list[dict[str, Any]]]:
    """Load the private, read-only staging bundle used for Exact binding.

    The bundle is intentionally separate from the public candidate shape:
    ``{"snapshot": {...}, "templates": [...]}``.  A couple of aliases are
    accepted so an export from the existing GearReleaseStore can be wrapped
    without rewriting its rows.
    """

    if path is None:
        return None, []
    value = _load_json(path)
    if not isinstance(value, Mapping):
        raise ValueError("community staging must be a JSON object")
    snapshot = (
        value.get("snapshot")
        or value.get("gearSnapshot")
        or value.get("gear")
    )
    if snapshot is None and "variants" in value:
        snapshot = value
    if not isinstance(snapshot, Mapping):
        raise ValueError("community staging is missing a gear snapshot")
    rows = value.get("templates") or value.get("communityTemplates") or []
    if not isinstance(rows, list):
        raise ValueError("community staging templates must be an array")
    return snapshot, [dict(row) for row in rows if isinstance(row, Mapping)]


def _prepare_snapshot(
    snapshot: Mapping[str, Any],
    *,
    candidate: Mapping[str, Any],
    dependency_vector: Mapping[str, Any],
    community_templates: list[dict[str, Any]],
    community_snapshot: Mapping[str, Any] | None,
    personal_templates: list[dict[str, Any]],
) -> dict[str, Any]:
    prepared = copy.deepcopy(dict(snapshot))
    community_binding = None
    if community_snapshot is not None:
        community_templates = select_s2_bindable_community_templates(
            community_templates,
            community_snapshot.get("variants") or [],
        )
        community_specs = {
            (_text(row.get("classKey")), _text(row.get("specKey")))
            for row in community_templates
            if _text(row.get("classKey")) and _text(row.get("specKey"))
        }
        if len(community_specs) < 40:
            missing = 40 - len(community_specs)
            raise ValueError(
                "community staging bindable coverage is incomplete: "
                f"{len(community_specs)}/40 specs ({missing} missing)"
            )
        merged = merge_s2_community_exact_snapshot(
            prepared,
            community_snapshot,
            community_templates,
        )
        prepared = merged["snapshot"]
        community_templates = merged["templates"]
        community_binding = merged["binding"]
    catalog_rows = project_s2_catalog_rows(prepared)
    catalog_keys = {
        (_text(row.get("itemId")), _text(row.get("variantKey")))
        for row in catalog_rows
    }
    runtime_variants = []
    exact_rows = []
    for raw in prepared.get("variants") or []:
        if not isinstance(raw, Mapping):
            continue
        row = copy.deepcopy(dict(raw))
        identity = (_text(row.get("itemId")), _text(row.get("variantKey")))
        payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
        canonical = payload.get("canonicalSimcInput") if isinstance(payload.get("canonicalSimcInput"), Mapping) else {}
        resolved_stats = payload.get("resolvedStats") if isinstance(payload.get("resolvedStats"), Mapping) else {}
        if not resolved_stats and isinstance(row.get("staticStats"), Mapping):
            resolved_stats = row.get("staticStats")
        if not resolved_stats and isinstance(payload.get("itemStats"), Mapping):
            resolved_stats = payload.get("itemStats")
        bonus_ids = [str(value) for value in canonical.get("bonusIds") or [] if str(value).strip()]
        if not bonus_ids:
            bonus_ids = [str(value) for value in row.get("bonusIds") or [] if str(value).strip()]
        track_key = _text(payload.get("trackKey"))
        if not track_key and _text(row.get("sourceType")).lower() == "tier_set":
            # Tier static rows have no item-level progression in the SimC
            # payload, but Track Authority exposes their finite Browse track
            # explicitly under this stable key.
            track_key = "tier_set_static"
        row.update({
            "rowFamily": "browse" if identity in catalog_keys else "exact_instance",
            "bonusIds": bonus_ids,
            "staticStats": _canonical(resolved_stats),
            "sourceVariantKey": _text(row.get("variantKey")),
            "trackKey": track_key,
            "trackRank": payload.get("rank"),
            "trackRankMax": payload.get("maxRank"),
        })
        if row["rowFamily"] == "exact_instance":
            # Track/rank fields define Browse membership.  Exact progression
            # is re-derived from the immutable bonus/ilevel evidence by the
            # Track Authority, so keeping these fields would be an explicit
            # Browse leak even when the row is marked exact_instance.
            for field in ("trackKey", "trackRank", "trackRankMax"):
                row.pop(field, None)
        runtime_variants.append(row)
        exact = copy.deepcopy(row)
        exact["rowFamily"] = "exact_instance"
        exact_rows.append(exact)
    prepared["variants"] = runtime_variants
    prepared["exactRows"] = exact_rows
    prepared["variantSummary"] = {
        "exactInstanceRowCount": len(exact_rows),
        "exactVerifiedRowCount": len(exact_rows),
        "exactExcludedRowCount": 0,
        "observedAscendantItemIds": [],
    }
    prepared["dependencyVector"] = _canonical(dependency_vector)
    prepared["communityTemplates"] = copy.deepcopy(community_templates)
    if community_binding is not None:
        prepared["communityExactBinding"] = copy.deepcopy(community_binding)
    prepared["personalTemplates"] = copy.deepcopy(personal_templates)
    return prepared


def _repository_binding(
    candidate: Mapping[str, Any],
    source_policy: Mapping[str, Any],
    *,
    client_build: str,
    simc_runtime_revision: str,
    capture_revision: str,
    capture_files: list[Path],
) -> dict[str, Any]:
    matrix = candidate.get("simcMatrixEvidence") if isinstance(candidate.get("simcMatrixEvidence"), Mapping) else {}
    capture_manifest = {
        "schemaRevision": "s2-runtime-capture-manifest-v1",
        "status": "verified",
        "captureRevision": capture_revision,
        "files": [
            {"path": str(path.expanduser().resolve().relative_to(ROOT)), "sha256": _sha256_file(path)}
            for path in capture_files
        ],
    }
    return build_endgame_binding(
        season_id="midnight-season-2",
        season_metadata={
            "candidateReportId": _text(candidate.get("reportId")),
            "matrixReportId": _text(matrix.get("reportId")),
            "captureFiles": [str(path.expanduser().resolve().relative_to(ROOT)) for path in capture_files],
        },
        source_policy=source_policy,
        capture_manifest=capture_manifest,
        client_build=client_build,
        simc_runtime_revision=simc_runtime_revision,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--source-policy", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--prepared-snapshot-output", required=True, type=Path)
    parser.add_argument("--community-templates", type=Path)
    parser.add_argument(
        "--community-staging",
        type=Path,
        help="Private JSON bundle containing a staging Gear snapshot and templates.",
    )
    parser.add_argument("--personal-templates", type=Path)
    parser.add_argument("--capture-file", action="append", type=Path, default=[])
    parser.add_argument("--capture-revision", required=True)
    parser.add_argument("--client-build", required=True)
    parser.add_argument("--simc-runtime-revision", required=True)
    parser.add_argument("--track-authority-revision", default="midnight-season-2-track-authority-v69")
    args = parser.parse_args()

    candidate = _load_json(args.candidate)
    snapshot = _load_json(args.snapshot)
    source_policy = _load_json(args.source_policy)
    if not isinstance(candidate, Mapping) or not isinstance(snapshot, Mapping) or not isinstance(source_policy, Mapping):
        raise ValueError("candidate, snapshot and source policy must be JSON objects")

    community_snapshot, staged_templates = _community_staging(args.community_staging)
    if args.community_staging and args.community_templates:
        raise ValueError("use --community-staging or --community-templates, not both")
    community_templates = (
        staged_templates
        if args.community_staging
        else _templates(args.community_templates)
    )
    dependency_vector = gear_release_tool.runtime_dependency_revisions(args.simc_runtime_revision)
    prepared_snapshot = _prepare_snapshot(
        snapshot,
        candidate=candidate,
        dependency_vector=dependency_vector,
        community_templates=community_templates,
        community_snapshot=community_snapshot,
        personal_templates=_templates(args.personal_templates),
    )
    repository = _repository_binding(
        candidate,
        source_policy,
        client_build=_text(args.client_build),
        simc_runtime_revision=_text(args.simc_runtime_revision),
        capture_revision=_text(args.capture_revision),
        # The prepared runtime snapshot is a derived output.  Including it in
        # the repository identity would make seasonRevision depend on a file
        # whose own seasonRevision is derived from this identity.
        capture_files=[args.candidate, args.source_policy, *args.capture_file],
    )
    if _text(prepared_snapshot.get("seasonRevision")) != _text(repository.get("seasonRevision")):
        raise ValueError(
            "snapshot seasonRevision does not match repository binding: "
            f"{prepared_snapshot.get('seasonRevision')} != {repository.get('seasonRevision')}"
        )
    track_authority = build_s2_track_authority(
        candidate,
        season_revision=repository["seasonRevision"],
        gear_rule_revision=dependency_vector["gearRuleRevision"],
        track_authority_revision=args.track_authority_revision,
        snapshot=prepared_snapshot,
    )
    option_catalog = build_s2_option_catalog(candidate, season_revision=repository["seasonRevision"])
    set_membership = build_s2_set_membership(candidate, season_revision=repository["seasonRevision"])
    result = build_season_endgame_candidate(
        repository=repository,
        gear_snapshot=prepared_snapshot,
        option_catalog=option_catalog,
        set_membership=set_membership,
        track_authority=track_authority,
        simc_runtime_revision=_text(args.simc_runtime_revision),
    )
    result = {
        **result,
        "repository": repository,
        "trackAuthority": track_authority,
        "optionCatalog": option_catalog,
        "setMembership": set_membership,
    }
    _atomic_json_write(args.prepared_snapshot_output, prepared_snapshot)
    _atomic_json_write(args.output, result)
    summary = {
        "status": result.get("status"),
        "seasonRevision": result.get("seasonRevision"),
        "problemCodes": result.get("problemCodes") or [],
        "gearReleaseId": (result.get("gearRelease") or {}).get("releaseId"),
        "catalogRevision": (result.get("catalog") or {}).get("catalogRevision"),
        "exactRegistryRevision": (result.get("exactRegistry") or {}).get("registryRevision"),
        "preparedSnapshot": str(args.prepared_snapshot_output.expanduser().resolve()),
        "output": str(args.output.expanduser().resolve()),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") == "candidate" else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)

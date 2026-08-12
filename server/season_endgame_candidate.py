"""Candidate-only S2 End Game Gear Release, Catalog, and Exact Registry assembly."""

from __future__ import annotations

import copy
import json
from typing import Any, Mapping

try:
    from . import gear_catalog_revision, gear_release, gear_release_tool
    from .gear_enhancement_catalog import (
        OPTION_REVISION_PREFIX,
        validate_enhancement_option_catalog,
    )
    from .gear_exact_item_registry import (
        build_exact_item_registry,
        verify_exact_item_registry,
    )
    from .season_endgame_repository import validate_endgame_binding
    from .season_set_membership import (
        SET_MEMBERSHIP_REVISION_PREFIX,
        validate_set_membership,
    )
except ImportError:
    import gear_catalog_revision
    import gear_release
    import gear_release_tool
    from gear_enhancement_catalog import (
        OPTION_REVISION_PREFIX,
        validate_enhancement_option_catalog,
    )
    from gear_exact_item_registry import (
        build_exact_item_registry,
        verify_exact_item_registry,
    )
    from season_endgame_repository import validate_endgame_binding
    from season_set_membership import (
        SET_MEMBERSHIP_REVISION_PREFIX,
        validate_set_membership,
    )


SCHEMA_REVISION = "season-endgame-candidate-v1"
S2_SEASON_PREFIX = "season-midnight-season-2:"
_REQUIRED_DEPENDENCY_FIELDS = (
    "gearRuleRevision",
    "resolverContractRevision",
    "serializerRevision",
    "simcRuntimeRevision",
    "statPolicyRevision",
    "selectionSchemaRevision",
    "capabilityRevision",
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


def _problem(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _problem_codes(problems: list[Mapping[str, Any]]) -> list[str]:
    return sorted({
        _text(problem.get("code"))
        for problem in problems
        if _text(problem.get("code"))
    })


def _append_problem(
    problems: list[dict[str, str]],
    code: str,
    path: str,
    message: str,
) -> None:
    if not any(
        problem.get("code") == code and problem.get("path") == path
        for problem in problems
    ):
        problems.append(_problem(code, path, message))


def _blocked(
    season_revision: str,
    problems: list[Mapping[str, Any]],
    *,
    dependency_vector: Mapping[str, Any] | None = None,
    gear_release: Any = None,
    catalog: Any = None,
    exact_registry: Any = None,
) -> dict[str, Any]:
    canonical_problems = sorted(
        (_canonical(problem) for problem in problems),
        key=lambda problem: (
            _text(problem.get("code")),
            _text(problem.get("path")),
            _text(problem.get("message")),
        ),
    )
    return {
        "schemaRevision": SCHEMA_REVISION,
        "status": "blocked",
        "candidateOnly": True,
        "activePointerChanged": False,
        "promotionAttempted": False,
        "seasonRevision": season_revision,
        "dependencyVector": _canonical(dependency_vector or {}),
        "gearRelease": gear_release,
        "catalog": catalog,
        "exactRegistry": exact_registry,
        "problemCodes": _problem_codes(canonical_problems),
        "problems": canonical_problems[:60],
        "gate": {
            "status": "blocked",
            "problemCodes": _problem_codes(canonical_problems),
        },
    }


def _snapshot_rows(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Add only deterministic mapping flags required by Catalog v3."""

    rows = copy.deepcopy(dict(snapshot))
    items = [row for row in rows.get("items") or [] if isinstance(row, dict)]
    sources = [row for row in rows.get("sources") or [] if isinstance(row, dict)]
    variants = [row for row in rows.get("variants") or [] if isinstance(row, dict)]
    source_item_ids = {
        _text(row.get("itemId")) for row in sources if _text(row.get("itemId"))
    }
    variant_item_ids = {
        _text(row.get("itemId")) for row in variants if _text(row.get("itemId"))
    }
    for item in items:
        item["hasSourceRefs"] = (
            item.get("hasSourceRefs") is True
            or _text(item.get("itemId")) in source_item_ids
        )
        item["hasVariantRefs"] = (
            item.get("hasVariantRefs") is True
            or _text(item.get("itemId")) in variant_item_ids
        )
    rows["items"] = items
    rows["sources"] = sources
    rows["variants"] = variants
    return rows


def _duplicate_browse_shape_problems(
    snapshot: Mapping[str, Any],
) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str, str, str]] = set()
    problems: list[dict[str, str]] = []
    for index, row in enumerate(snapshot.get("variants") or []):
        if not isinstance(row, Mapping) or _text(row.get("rowFamily")) != "browse":
            continue
        progression_state = row.get("progressionState")
        progression_token = (
            json.dumps(_canonical(progression_state), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if isinstance(progression_state, Mapping)
            else ""
        )
        key = (
            _text(row.get("itemId")),
            _text(row.get("trackKey")).lower(),
            _text(row.get("trackRank")),
            _text(row.get("itemLevel")),
            progression_token,
        )
        if key in seen:
            problems.append(_problem(
                "CATALOG_BROWSE_VARIANT_SHAPE_DUPLICATE",
                f"gear_snapshot.variants[{index}]",
                "Browse variants contain duplicate progression shape identity.",
            ))
        seen.add(key)
    return problems


def _validate_component_identity(
    *,
    repository: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    option_catalog: Mapping[str, Any],
    set_membership: Mapping[str, Any],
    track_authority: Mapping[str, Any],
    simc_runtime_revision: str,
) -> tuple[str, dict[str, str], list[dict[str, str]]]:
    season_revision = _text(repository.get("seasonRevision"))
    problems: list[dict[str, str]] = []
    repository_problems = validate_endgame_binding(repository)
    for issue in repository_problems:
        _append_problem(
            problems,
            f"S2_REPOSITORY_{_text(issue.get('code')) or 'INVALID'}",
            _text(issue.get("path")) or "repository",
            _text(issue.get("message")) or "S2 repository binding is invalid.",
        )
    if not season_revision.startswith(S2_SEASON_PREFIX):
        _append_problem(
            problems,
            "S2_REPOSITORY_SEASON_REVISION_INVALID",
            "repository.seasonRevision",
            "Candidate requires an S2 season revision.",
        )
    capture_manifest = repository.get("captureManifest")
    if isinstance(capture_manifest, Mapping) and _text(capture_manifest.get("status")):
        if _text(capture_manifest.get("status")) != "verified":
            _append_problem(
                problems,
                "S2_REPOSITORY_CAPTURE_NOT_VERIFIED",
                "repository.captureManifest.status",
                "S2 candidate requires a verified official capture manifest.",
            )
    if _text(repository.get("clientBuild")).startswith("UNVERIFIED:"):
        _append_problem(
            problems,
            "S2_REPOSITORY_CLIENT_BUILD_UNVERIFIED",
            "repository.clientBuild",
            "S2 candidate cannot bind an unverified client build.",
        )
    if _text(repository.get("simcRuntimeRevision")).startswith("UNVERIFIED:"):
        _append_problem(
            problems,
            "S2_SIMC_RUNTIME_UNVERIFIED",
            "repository.simcRuntimeRevision",
            "S2 candidate cannot bind an unverified SimC runtime.",
        )

    component_seasons = {
        "gear_snapshot": _text(snapshot.get("seasonRevision")),
        "option_catalog": _text(option_catalog.get("seasonRevision")),
        "set_membership": _text(set_membership.get("seasonRevision")),
        "track_authority": _text(track_authority.get("seasonRevision")),
    }
    for component, component_season in component_seasons.items():
        if component_season and component_season != season_revision:
            _append_problem(
                problems,
                "S2_CANDIDATE_SEASON_REVISION_MIXED",
                f"{component}.seasonRevision",
                "S2 candidate components must share one season revision.",
            )

    option_problems = validate_enhancement_option_catalog(option_catalog)
    if _text(option_catalog.get("status")) != "verified":
        _append_problem(
            problems,
            "S2_OPTION_CATALOG_UNAVAILABLE",
            "option_catalog.status",
            "S2 enhancement option catalog is not verified.",
        )
    if not _text(option_catalog.get("optionRevision")).startswith(OPTION_REVISION_PREFIX):
        _append_problem(
            problems,
            "S2_OPTION_REVISION_MISSING",
            "option_catalog.optionRevision",
            "S2 candidate requires one enhancement option revision.",
        )
    for issue in option_problems:
        _append_problem(
            problems,
            f"S2_OPTION_{_text(issue.get('code')) or 'INVALID'}",
            "option_catalog",
            _text(issue.get("message")) or "S2 enhancement option catalog is invalid.",
        )

    set_problems = validate_set_membership(set_membership)
    if _text(set_membership.get("status")) != "verified":
        _append_problem(
            problems,
            "S2_SET_MEMBERSHIP_UNAVAILABLE",
            "set_membership.status",
            "S2 set membership is not verified.",
        )
    if not _text(set_membership.get("setMembershipRevision")).startswith(SET_MEMBERSHIP_REVISION_PREFIX):
        _append_problem(
            problems,
            "S2_SET_MEMBERSHIP_REVISION_MISSING",
            "set_membership.setMembershipRevision",
            "S2 candidate requires one set membership revision.",
        )
    for issue in set_problems:
        _append_problem(
            problems,
            f"S2_SET_{_text(issue.get('code')) or 'INVALID'}",
            "set_membership",
            _text(issue.get("message")) or "S2 set membership is invalid.",
        )

    track_revision = _text(
        track_authority.get("trackAuthorityRevision")
        or track_authority.get("ruleRevision")
    )
    if _text(track_authority.get("status")) != "verified":
        _append_problem(
            problems,
            "S2_TRACK_AUTHORITY_UNAVAILABLE",
            "track_authority.status",
            "S2 Track Authority is not verified.",
        )
    if not track_revision:
        _append_problem(
            problems,
            "S2_TRACK_AUTHORITY_REVISION_MISSING",
            "track_authority.trackAuthorityRevision",
            "S2 candidate requires one Track Authority revision.",
        )
    if not isinstance(track_authority.get("records"), list) or not track_authority.get("records"):
        _append_problem(
            problems,
            "S2_TRACK_AUTHORITY_RECORDS_MISSING",
            "track_authority.records",
            "S2 candidate requires explicit Track Authority records.",
        )
    if _text(track_authority.get("gearRuleRevision")) and _text(track_authority.get("gearRuleRevision")) != _text(
        next(
            (
                value
                for value in (
                    (snapshot.get("dependencyVector") or {}).get("gearRuleRevision")
                    if isinstance(snapshot.get("dependencyVector"), Mapping)
                    else "",
                )
                if _text(value)
            ),
            "",
        )
    ):
        _append_problem(
            problems,
            "S2_GEAR_RULE_REVISION_MIXED",
            "track_authority.gearRuleRevision",
            "Track Authority and gear snapshot must share one gear-rule revision.",
        )

    if _text(repository.get("simcRuntimeRevision")) != _text(simc_runtime_revision):
        _append_problem(
            problems,
            "S2_SIMC_RUNTIME_REVISION_MISMATCH",
            "simc_runtime_revision",
            "Candidate runtime does not match the S2 repository capture identity.",
        )
    for index, row in enumerate(snapshot.get("variants") or []):
        if not isinstance(row, Mapping):
            continue
        if (
            _text(row.get("rowFamily")) == "exact_instance"
            and (
                _text(row.get("variantId")).startswith("browse-")
                or "trackKey" in row
                or "trackRank" in row
            )
        ):
            _append_problem(
                problems,
                "S2_EXACT_INSTANCE_BROWSE_LEAK",
                f"gear_snapshot.variants[{index}]",
                "ExactItemInstance cannot enter BrowseVariant membership.",
            )
    problems.extend(_duplicate_browse_shape_problems(snapshot))

    dependency_source = snapshot.get("dependencyVector")
    if not isinstance(dependency_source, Mapping):
        dependency_source = snapshot.get("dependencyRevisions")
    dependency = {
        _text(key): value
        for key, value in (dependency_source.items() if isinstance(dependency_source, Mapping) else [])
        if _text(key)
    }
    dependency["simcRuntimeRevision"] = _text(simc_runtime_revision)
    track_rule_revision = _text(track_authority.get("gearRuleRevision"))
    if track_rule_revision:
        dependency["gearRuleRevision"] = track_rule_revision
    for field in _REQUIRED_DEPENDENCY_FIELDS:
        if not _text(dependency.get(field)):
            _append_problem(
                problems,
                "S2_DEPENDENCY_REVISION_MISSING",
                f"dependencyVector.{field}",
                "Candidate dependency vector is incomplete.",
            )
    return season_revision, dependency, problems


def build_season_endgame_candidate(
    *,
    repository: Any,
    gear_snapshot: Any,
    option_catalog: Any,
    set_membership: Any,
    track_authority: Any,
    simc_runtime_revision: str,
) -> dict[str, Any]:
    """Build a dormant S2 candidate without any promotion or pointer mutation."""

    repo = repository if isinstance(repository, Mapping) else {}
    snapshot = gear_snapshot if isinstance(gear_snapshot, Mapping) else {}
    options = option_catalog if isinstance(option_catalog, Mapping) else {}
    sets = set_membership if isinstance(set_membership, Mapping) else {}
    tracks = track_authority if isinstance(track_authority, Mapping) else {}
    season_revision, dependency, problems = _validate_component_identity(
        repository=repo,
        snapshot=snapshot,
        option_catalog=options,
        set_membership=sets,
        track_authority=tracks,
        simc_runtime_revision=simc_runtime_revision,
    )
    snapshot_problems = gear_release_tool.validate_gear_snapshot(snapshot)
    for issue in snapshot_problems:
        _append_problem(
            problems,
            f"S2_GEAR_{_text(issue.get('code')) or 'INVALID'}",
            _text(issue.get("path")) or "gear_snapshot",
            "S2 gear snapshot failed its release-shape validation.",
        )
    if problems:
        return _blocked(season_revision, problems, dependency_vector=dependency)

    summary = gear_release_tool.gear_snapshot_summary(snapshot)
    release = gear_release.build_release(
        release_kind="gear",
        season_revision=season_revision,
        schema_revision="gear-release-v1",
        content=summary,
        dependency_revisions=dependency,
        release_status="validated",
        source={
            "sourceRevision": "midnight-season-2-endgame-candidate-v1",
            "candidateOnly": True,
            "repositoryCaptureRevision": _text(repo.get("captureRevision")),
            "simcRuntimeRevision": _text(simc_runtime_revision),
            "enhancementOptionRevision": _text(options.get("optionRevision")),
            "setMembershipRevision": _text(sets.get("setMembershipRevision")),
            "trackAuthorityRevision": _text(
                tracks.get("trackAuthorityRevision") or tracks.get("ruleRevision")
            ),
        },
    )
    release_problems = gear_release.validate_release(release)
    if release_problems:
        return _blocked(
            season_revision,
            release_problems,
            dependency_vector=dependency,
            gear_release=release,
        )

    track_revision = _text(
        tracks.get("trackAuthorityRevision") or tracks.get("ruleRevision")
    )
    catalog_binding = {
        "bindingMode": "validated_release_pair",
        "manifestRevision": "candidate-manifest:unsealed",
        "gearReleaseId": release["releaseId"],
        "gearReleaseContentHash": release["contentHash"],
        "gearReleaseSchemaRevision": release["schemaRevision"],
        "seasonRevision": season_revision,
        "gearRuleRevision": dependency["gearRuleRevision"],
        "trackAuthorityRevision": track_revision,
        "trackRecords": _canonical(tracks.get("records") or []),
        "dependencyVector": {
            **dependency,
            "trackAuthorityRevision": track_revision,
        },
        "sourceSummary": {
            "mode": "season_endgame_candidate",
            "repositoryCaptureRevision": _text(repo.get("captureRevision")),
        },
    }
    catalog_rows = _snapshot_rows(snapshot)
    catalog = gear_catalog_revision.build_catalog_revision(
        catalog_binding,
        catalog_rows,
    )
    if catalog.get("status") != "verified":
        for code in catalog.get("problemCodes") or []:
            _append_problem(
                problems,
                _text(code) or "S2_CATALOG_BLOCKED",
                "catalog",
                "S2 Catalog builder returned a blocked candidate.",
            )
        return _blocked(
            season_revision,
            problems,
            dependency_vector={
                **dependency,
                "optionRevision": _text(options.get("optionRevision")),
                "setMembershipRevision": _text(sets.get("setMembershipRevision")),
                "trackAuthorityRevision": track_revision,
            },
            gear_release=release,
            catalog=catalog,
        )

    catalog_problems = gear_catalog_revision.verify_catalog_revision(catalog)
    if catalog_problems:
        for code in catalog_problems:
            _append_problem(
                problems,
                _text(code),
                "catalog",
                "S2 Catalog candidate failed its integrity verification.",
            )
        return _blocked(
            season_revision,
            problems,
            dependency_vector=dependency,
            gear_release=release,
            catalog=catalog,
        )

    exact_rows = [
        row
        for row in snapshot.get("exactRows") or snapshot.get("variants") or []
        if isinstance(row, Mapping) and _text(row.get("rowFamily")) == "exact_instance"
    ]
    exact_registry = build_exact_item_registry(
        catalog_binding,
        catalog_revision=_text(catalog.get("catalogRevision")),
        exact_rows=exact_rows,
        source_exact_row_count=(
            (snapshot.get("variantSummary") or {}).get("exactInstanceRowCount")
            if isinstance(snapshot.get("variantSummary"), Mapping)
            else len(exact_rows)
        ),
        community_templates=snapshot.get("communityTemplates") or [],
        personal_templates=snapshot.get("personalTemplates") or [],
    )
    if exact_registry.get("status") != "verified":
        for code in exact_registry.get("problemCodes") or []:
            _append_problem(
                problems,
                _text(code) or "S2_EXACT_REGISTRY_BLOCKED",
                "exactRegistry",
                "S2 Exact Registry candidate is not fully verified.",
            )
    else:
        for code in verify_exact_item_registry(exact_registry):
            _append_problem(
                problems,
                _text(code),
                "exactRegistry",
                "S2 Exact Registry candidate failed its integrity verification.",
            )

    dependency_vector = {
        **dependency,
        "gearCatalogRevision": _text(catalog.get("catalogRevision")),
        "gearExactRegistryRevision": _text(exact_registry.get("registryRevision")),
        "optionRevision": _text(options.get("optionRevision")),
        "setMembershipRevision": _text(sets.get("setMembershipRevision")),
        "trackAuthorityRevision": track_revision,
    }
    if problems:
        return _blocked(
            season_revision,
            problems,
            dependency_vector=dependency_vector,
            gear_release=release,
            catalog=catalog,
            exact_registry=exact_registry,
        )
    return {
        "schemaRevision": SCHEMA_REVISION,
        "status": "candidate",
        "candidateOnly": True,
        "activePointerChanged": False,
        "promotionAttempted": False,
        "seasonRevision": season_revision,
        "dependencyVector": _canonical(dependency_vector),
        "gearRelease": release,
        "catalog": catalog,
        "exactRegistry": exact_registry,
        "problemCodes": [],
        "problems": [],
        "gate": {
            "status": "candidate",
            "activePointerChanged": False,
            "candidateOnly": True,
        },
    }


__all__ = ("SCHEMA_REVISION", "build_season_endgame_candidate")

#!/usr/bin/env python3
"""Seal the validated S2 Gear/Catalog candidate and optionally its community pair.

This command only writes immutable dormant releases.  Active Manifest sealing and
pointer promotion remain separate commands so a failed community election cannot
change production state.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import gear_release_tool  # noqa: E402
from server.gear_catalog_revision_store import GearCatalogRevisionStore  # noqa: E402
from server.gear_exact_item_registry import (  # noqa: E402
    build_exact_item_registry,
    verify_exact_item_registry,
)
from server.gear_exact_item_registry_store import GearExactItemRegistryStore  # noqa: E402
from server.gear_release import validate_manifest  # noqa: E402
from server.gear_release_store import GearReleaseIntegrityError  # noqa: E402
from server.s2_community_exact import (  # noqa: E402
    merge_s2_community_exact_snapshot,
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _load_json(path: Path) -> Any:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def _canonical(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str))


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
        Path(temporary).replace(target)
        temporary = ""
    finally:
        if temporary:
            try:
                Path(temporary).unlink()
            except FileNotFoundError:
                pass


def _community_templates_from_rows(rows: Any) -> list[dict[str, Any]]:
    """Project sealed public winner payloads into Exact Registry input templates."""

    templates: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, Mapping) or _text(row.get("role")) not in {"winner", "eligible"}:
            continue
        payload = row.get("payload")
        if not isinstance(payload, Mapping):
            continue
        template = copy.deepcopy(dict(payload))
        template["templateId"] = _text(row.get("templateId")) or _text(template.get("templateId"))
        template["classKey"] = _text(row.get("classKey")) or _text(template.get("classKey"))
        template["specKey"] = _text(row.get("specKey")) or _text(template.get("specKey"))
        template["sourceKey"] = _text(row.get("sourceKey")) or _text(template.get("sourceKey"))
        template["sourceStatus"] = _text(row.get("sourceStatus")) or _text(template.get("sourceStatus"))
        templates.append(template)
    return templates


def _exact_binding(
    release: Mapping[str, Any],
    dependency_vector: Mapping[str, Any],
    track_authority: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    authority = track_authority if isinstance(track_authority, Mapping) else {}
    return {
        "bindingMode": "validated_release_pair",
        "manifestRevision": "candidate-manifest:unsealed",
        "gearReleaseId": _text(release.get("releaseId")),
        "gearReleaseContentHash": _text(release.get("contentHash")),
        "gearReleaseSchemaRevision": _text(release.get("schemaRevision")),
        "seasonRevision": _text(release.get("seasonRevision")),
        "gearRuleRevision": _text(dependency_vector.get("gearRuleRevision")),
        "trackAuthorityRevision": _text(
            authority.get("trackAuthorityRevision")
            or authority.get("ruleRevision")
        ),
        "trackRecords": _canonical(authority.get("records") or []),
        "dependencyVector": _canonical(dependency_vector),
    }


def _bind_community_staging_templates(
    community_staging: Mapping[str, Any],
    templates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Carry the immutable observed variant identity into release templates."""

    gear = (
        community_staging.get("gear")
        if isinstance(community_staging.get("gear"), Mapping)
        else {}
    )
    merged = merge_s2_community_exact_snapshot(
        {},
        gear,
        templates,
    )
    return [
        copy.deepcopy(dict(template))
        for template in merged.get("templates") or []
        if isinstance(template, Mapping)
    ]


def _require_verified_snapshot(snapshot: Mapping[str, Any], release: Mapping[str, Any]) -> None:
    problems = gear_release_tool.validate_gear_snapshot(snapshot)
    if problems:
        raise GearReleaseIntegrityError(
            "runtime snapshot failed release validation: "
            + json.dumps(problems[:20], ensure_ascii=False, sort_keys=True)
        )
    if gear_release_tool.gear_snapshot_summary(snapshot) != _mapping(release.get("content")):
        raise GearReleaseIntegrityError("runtime snapshot does not match Gear Release content")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument(
        "--exact-rows",
        type=Path,
        help="Optional compact Exact-row input when --snapshot is a normalized release snapshot.",
    )
    parser.add_argument(
        "--source-exact-row-count",
        type=int,
        default=0,
        help="Full source Exact-row count represented by a compact Exact-row input.",
    )
    parser.add_argument(
        "--snapshot-is-normalized",
        action="store_true",
        help="Treat --snapshot as the already projected immutable release shape.",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--build-community", action="store_true")
    parser.add_argument(
        "--community-staging",
        type=Path,
        help=(
            "Optional candidate community staging bundle. When supplied, "
            "community election reads this immutable candidate file instead "
            "of the live staging tables."
        ),
    )
    parser.add_argument(
        "--community-release-mode",
        choices=("hero-v2", "single-v1"),
        default="hero-v2",
        help=(
            "Select the community release contract. single-v1 keeps one "
            "fresh importable winner per spec when Hero talent staging is absent."
        ),
    )
    parser.add_argument("--level", type=int, default=90)
    parser.add_argument("--source-revision", default="s2-equipment-library-candidate-v69")
    args = parser.parse_args()

    candidate = _load_json(args.candidate)
    snapshot = _load_json(args.snapshot)
    exact_input = _load_json(args.exact_rows) if args.exact_rows else snapshot
    if not isinstance(candidate, Mapping) or not isinstance(snapshot, Mapping):
        raise ValueError("candidate and snapshot must be JSON objects")
    if not isinstance(exact_input, Mapping):
        raise ValueError("exact rows input must be a JSON object")
    release = _mapping(candidate.get("gearRelease"))
    catalog = _mapping(candidate.get("catalog"))
    if _text(release.get("releaseKind")) != "gear" or _text(release.get("releaseStatus")) != "validated":
        raise ValueError("candidate does not contain a validated Gear Release")
    if _text(catalog.get("status")) != "verified":
        raise ValueError("candidate does not contain a verified Catalog")
    release_snapshot = (
        snapshot
        if args.snapshot_is_normalized
        else gear_release_tool.normalize_gear_snapshot_for_release(snapshot)
    )
    _require_verified_snapshot(release_snapshot, release)

    store = gear_release_tool._store_from_environment()
    connection_factory = getattr(store, "_connection_factory", None)
    if not callable(connection_factory):
        connection_factory = getattr(store, "connection_factory", None)
    if not callable(connection_factory):
        raise GearReleaseIntegrityError("GearReleaseStore connection factory is unavailable")
    catalog_store = GearCatalogRevisionStore(connection_factory)
    exact_store = GearExactItemRegistryStore(connection_factory)
    result: dict[str, Any] = {
        "schemaRevision": "s2-equipment-library-seal-report-v1",
        "status": "blocked",
        "candidateStatus": _text(candidate.get("status")),
        "gearRelease": {"releaseId": _text(release.get("releaseId")), "status": "not_attempted"},
        "catalog": {"catalogRevision": _text(catalog.get("catalogRevision")), "status": "not_attempted"},
        "community": None,
        "exactRegistry": None,
    }

    result["gearRelease"]["seal"] = store.seal_gear_release(
        dict(release),
        release_snapshot,
        gate_result={"status": "validated", "source": args.source_revision},
        event={"mode": args.source_revision, "candidateOnly": True},
    )
    result["gearRelease"]["status"] = "sealed"

    catalog_sealed = catalog_store.seal_catalog(dict(catalog))
    result["catalog"]["seal"] = {
        "status": catalog_sealed.get("status", "sealed"),
        "catalogRevision": _text(catalog_sealed.get("catalogRevision")),
    }
    result["catalog"]["status"] = "sealed"

    if args.build_community:
        if args.community_staging:
            community_staging = _load_json(args.community_staging)
            staged_templates = (
                community_staging.get("templates")
                if isinstance(community_staging, Mapping)
                else None
            )
            if not isinstance(staged_templates, list) or not staged_templates:
                raise GearReleaseIntegrityError(
                    "candidate community staging must contain a non-empty templates list"
                )
            staged_templates = [
                copy.deepcopy(dict(template))
                for template in staged_templates
                if isinstance(template, Mapping)
            ]
            if not staged_templates:
                raise GearReleaseIntegrityError(
                    "candidate community staging templates are empty"
                )
            staged_templates = _bind_community_staging_templates(
                community_staging,
                staged_templates,
            )

            def snapshot_candidate_community_templates(_expected_specs):
                return copy.deepcopy(staged_templates)

            # Keep the release builder and the live staging tables separate:
            # this override is process-local and only affects this dormant
            # candidate seal.
            store.snapshot_staging_community_templates = (
                snapshot_candidate_community_templates
            )
        dependencies = _mapping(release.get("dependencyRevisions"))
        if args.community_release_mode == "single-v1":
            # The v1 contract is still the supported import surface: one
            # fresh winner per spec.  Keep the newer Hero-slot projection
            # opt-in so an empty talent staging cannot silently block all
            # community imports.
            store.community_hero_projection_enabled = False
            store.community_skip_invalid_public_template_evidence = True
        community = gear_release_tool.build_legacy_community_release(
            store,
            gear_release_descriptor=dict(release),
            # A supplied candidate staging bundle must be validated against
            # the same complete release snapshot that produced it.  The live
            # builder projection is intentionally scoped to the live staging
            # tables and would otherwise bind this candidate to a different
            # template set.
            gear_snapshot=(
                release_snapshot
                if args.community_staging
                else store.snapshot_gear_release_for_community_builder(
                    _text(release.get("releaseId"))
                )
            ),
            dependency_revisions=dependencies,
            expected_specs=gear_release_tool.expected_spec_pairs(),
            now=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            level=args.level,
            source_revision=args.source_revision,
            set_membership=_mapping(candidate.get("setMembership")) or None,
        )
        result["community"] = {
            "releaseMode": args.community_release_mode,
            "status": _text(community.get("gate", {}).get("status")),
            "releaseId": _text(community.get("release", {}).get("releaseId")),
            "seal": community.get("seal"),
            "gate": community.get("gate"),
            "rowCount": len(community.get("rows") or []),
        }
        if _text(community.get("gate", {}).get("status")) != "validated":
            raise GearReleaseIntegrityError(
                "community election is not validated: "
                + json.dumps(community.get("gate") or {}, ensure_ascii=False, sort_keys=True)
            )

        community_templates = _community_templates_from_rows(community.get("rows"))
        exact_input_rows = (
            exact_input.get("exactRows")
            or exact_input.get("variants")
            or []
        )
        exact_rows = [
            row
            for row in exact_input_rows
            if isinstance(row, Mapping) and _text(row.get("rowFamily")) == "exact_instance"
        ]
        source_exact_row_count = (
            args.source_exact_row_count
            or int(exact_input.get("sourceExactRowCount") or 0)
            or len(exact_rows)
        )
        exact_binding = _exact_binding(
            release,
            dependencies,
            _mapping(candidate.get("trackAuthority")),
        )
        exact_registry = build_exact_item_registry(
            exact_binding,
            catalog_revision=_text(catalog.get("catalogRevision")),
            exact_rows=exact_rows,
            source_exact_row_count=source_exact_row_count,
            community_templates=community_templates,
            personal_templates=[],
            set_membership=_mapping(candidate.get("setMembership")) or None,
        )
        exact_problems = verify_exact_item_registry(exact_registry)
        if _text(exact_registry.get("status")) != "verified" or exact_problems:
            raise GearReleaseIntegrityError(
                "Exact Registry is not verified: "
                + json.dumps({"status": exact_registry.get("status"), "problems": exact_registry.get("problemCodes"), "verify": exact_problems}, ensure_ascii=False, sort_keys=True)
            )
        exact_sealed = exact_store.seal_registry(exact_registry)
        result["exactRegistry"] = {
            "status": "sealed",
            "registryRevision": _text(exact_registry.get("registryRevision")),
            "summary": exact_registry.get("summary"),
            "seal": exact_sealed,
        }

    result["status"] = (
        "verified"
        if result["community"] is not None and result["exactRegistry"] is not None
        else "catalog_verified"
    )
    result["candidate"] = {
        "status": _text(candidate.get("status")),
        "problemCodes": candidate.get("problemCodes") or [],
        "seasonRevision": _text(candidate.get("seasonRevision")),
    }
    _atomic_json_write(args.output, result)
    print(json.dumps({
        "status": result["status"],
        "gearReleaseId": result["gearRelease"]["releaseId"],
        "catalogRevision": result["catalog"]["catalogRevision"],
        "communityReleaseId": (result.get("community") or {}).get("releaseId"),
        "exactRegistryRevision": (result.get("exactRegistry") or {}).get("registryRevision"),
        "output": str(args.output.expanduser().resolve()),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, GearReleaseIntegrityError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)

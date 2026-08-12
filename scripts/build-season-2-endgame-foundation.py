#!/usr/bin/env python3
"""Materialize the bounded, fail-closed Season 2 End Game input reports."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.gear_enhancement_catalog import (  # noqa: E402
    build_enhancement_option_catalog,
)
from server.gear_item_level_stat_probe import (  # noqa: E402
    build_season_item_level_stat_probe_report,
)
from server.gear_track_authority import track_authority_for_binding  # noqa: E402
from server.gear_variant_simc_matrix import (  # noqa: E402
    build_s2_variant_identity_report,
)
from server.season_pve_universe import (  # noqa: E402
    bounded_universe_report,
    build_season_pve_universe,
)
from server.season_set_membership import build_set_membership  # noqa: E402


CAPTURE_BLOCKER = "OFFICIAL_CAPTURE_CONTRACT_INVALID"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _text(value: Any) -> str:
    return str(value or "").strip()


def _variant_blocked_report(*, season_revision: str, runtime_revision: str) -> dict[str, Any]:
    failure_codes = [
        "GEAR_VARIANT_OBSERVATIONS_MISSING",
        "GEAR_VARIANT_SIMC_RUNTIME_UNVERIFIED",
    ]
    report = {
        "schemaRevision": "gear-variant-identity-v1",
        "status": "blocked",
        "seasonRevision": season_revision,
        "simcRuntimeRevision": runtime_revision,
        "inputObservationCount": 0,
        "uniqueVariantCount": 0,
        "failureCodes": failure_codes,
        "problems": [
            {
                "code": "GEAR_VARIANT_OBSERVATIONS_MISSING",
                "message": "S2 BrowseVariant observations are unavailable until the official capture is complete.",
            },
            {
                "code": "GEAR_VARIANT_SIMC_RUNTIME_UNVERIFIED",
                "message": "S2 BrowseVariant identity cannot bind an unverified SimC runtime.",
            },
        ],
        "rows": [],
    }
    identity = json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    report["reportId"] = "gear-variant-simc-matrix:sha256:" + hashlib.sha256(identity).hexdigest()
    return report


def _gear_snapshot(
    *,
    season_revision: str,
    repository: dict[str, Any],
    gear_rule_revision: str,
) -> dict[str, Any]:
    return {
        "schemaRevision": "gear-snapshot-v1",
        "status": "blocked",
        "seasonId": "midnight-season-2",
        "scope": "end_game",
        "seasonRevision": season_revision,
        "items": [],
        "sources": [],
        "variants": [],
        "exactRows": [],
        "options": [],
        "communityTemplates": [],
        "personalTemplates": [],
        "variantSummary": {
            "browseVariantRowCount": 0,
            "exactInstanceRowCount": 0,
        },
        "dependencyVector": {
            "gearRuleRevision": gear_rule_revision,
            "resolverContractRevision": "pending:build_s2_resolver_contract",
            "serializerRevision": "pending:build_s2_serializer",
            "simcRuntimeRevision": _text(repository.get("simcRuntimeRevision")),
            "statPolicyRevision": "pending:build_s2_stat_policy",
            "selectionSchemaRevision": "pending:build_s2_selection_schema",
            "capabilityRevision": "pending:build_s2_capability",
        },
        "sourceCoverage": {
            "status": "blocked",
            "reasonCode": CAPTURE_BLOCKER,
            "capturedItemCount": 0,
            "capturedVariantCount": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--source-policy", required=True, type=Path)
    parser.add_argument("--track-input", required=True, type=Path)
    args = parser.parse_args()

    artifact_root = args.artifact_root.resolve()
    repository = _read(args.repository.resolve())
    source_policy = _read(args.source_policy.resolve())
    track_input = _read(args.track_input.resolve())
    season_revision = _text(repository.get("seasonRevision"))
    runtime_revision = _text(repository.get("simcRuntimeRevision"))
    normalized = artifact_root / "normalized"

    track_binding = {
        **repository,
        "status": _text(track_input.get("authorityStatus")) or "pending",
        "gearRuleRevision": _text(track_input.get("gearRuleRevision")),
        "trackAuthorityRevision": _text(track_input.get("trackAuthorityRevision")),
        "sourceRefs": track_input.get("sourceRefs") or [],
    }
    track_authority = track_authority_for_binding(
        track_binding,
        records=track_input.get("records"),
    )
    track_authority["inputSchemaRevision"] = _text(track_input.get("schemaRevision"))
    track_authority["inputStatus"] = _text(track_input.get("status")) or "pending"
    track_authority["inputRecordCount"] = len(track_input.get("records") or [])
    track_authority["blockerContext"] = {"officialCapture": CAPTURE_BLOCKER}
    _write(normalized / "track-authority.json", track_authority)

    option_binding = {
        "seasonId": "midnight-season-2",
        "seasonRevision": season_revision,
        "scope": "end_game",
        "status": "blocked",
    }
    option_catalog = build_enhancement_option_catalog(
        season_binding=option_binding,
        official_items=[],
        variants=None,
    )
    option_catalog["blockerContext"] = {"officialCapture": CAPTURE_BLOCKER}
    _write(normalized / "enhancement-option-catalog.json", option_catalog)

    set_membership = build_set_membership(
        {
            "seasonId": "midnight-season-2",
            "seasonRevision": season_revision,
            "scope": "end_game",
            "status": "blocked",
        },
        None,
    )
    set_membership["blockerContext"] = {"officialCapture": CAPTURE_BLOCKER}
    _write(normalized / "set-membership.json", set_membership)

    snapshot = _gear_snapshot(
        season_revision=season_revision,
        repository=repository,
        gear_rule_revision=_text(track_input.get("gearRuleRevision")),
    )
    _write(normalized / "gear-snapshot.json", snapshot)

    item_probe = build_season_item_level_stat_probe_report(
        [],
        resolver=lambda _item, _track: {},
        season_revision=season_revision,
        simc_runtime_revision=runtime_revision,
        tracks=track_input.get("records") or [],
    )
    item_probe["authorityContext"] = {
        "status": "blocked",
        "officialCapture": CAPTURE_BLOCKER,
        "simcRuntime": "UNVERIFIED",
    }
    _write(normalized / "item-level-stat-probe.json", item_probe)

    variant_report = _variant_blocked_report(
        season_revision=season_revision,
        runtime_revision=runtime_revision,
    )
    _write(normalized / "variant-identity.json", variant_report)

    universe_policy = copy.deepcopy(source_policy)
    universe_policy["seasonRevision"] = season_revision
    universe_discovery = {
        "schemaRevision": "season-pve-discovery-v1",
        "status": "blocked",
        "seasonRevision": season_revision,
        "sourcePolicyRevision": _text(source_policy.get("sourcePolicyRevision")),
        "asOf": "2026-08-12T07:56:12Z",
        "sources": [],
    }
    universe_staging = {
        "schemaRevision": "season-pve-staging-v1",
        "status": "blocked",
        "seasonRevision": season_revision,
        "members": [],
    }
    universe_catalog = {
        "schemaRevision": "season-pve-catalog-v1",
        "status": "blocked",
        "seasonRevision": season_revision,
        "catalogRevision": "",
        "members": [],
    }
    universe = build_season_pve_universe(
        universe_policy,
        universe_discovery,
        universe_staging,
        universe_catalog,
        mode="end_game",
    )
    _write(normalized / "end-game-universe.json", bounded_universe_report(universe, max_ledger_rows=100))

    print(json.dumps({
        "status": "blocked",
        "seasonRevision": season_revision,
        "outputs": sorted(
            str(path.relative_to(artifact_root))
            for path in normalized.glob("*.json")
        ),
    }, ensure_ascii=False, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

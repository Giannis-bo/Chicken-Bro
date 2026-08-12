#!/usr/bin/env python3
"""Build a dormant Midnight Season 2 End Game candidate artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.season_endgame_candidate import build_season_endgame_candidate


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a candidate-only Midnight Season 2 End Game release."
    )
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--normalized-snapshot", required=True, type=Path)
    parser.add_argument("--option-catalog", required=True, type=Path)
    parser.add_argument("--set-membership", required=True, type=Path)
    parser.add_argument("--track-authority", required=True, type=Path)
    parser.add_argument("--simc-runtime-revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    result = build_season_endgame_candidate(
        repository=_load(args.repository),
        gear_snapshot=_load(args.normalized_snapshot),
        option_catalog=_load(args.option_catalog),
        set_membership=_load(args.set_membership),
        track_authority=_load(args.track_authority),
        simc_runtime_revision=args.simc_runtime_revision,
    )
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    _write(output / "requirement.json", {
        "schemaRevision": "season-endgame-candidate-requirement-v1",
        "seasonId": "midnight-season-2",
        "scope": "end_game",
        "candidateOnly": True,
        "activePointerMutation": False,
        "simcRuntimeRevision": args.simc_runtime_revision,
        "inputs": {
            "repository": str(args.repository),
            "normalizedSnapshot": str(args.normalized_snapshot),
            "optionCatalog": str(args.option_catalog),
            "setMembership": str(args.set_membership),
            "trackAuthority": str(args.track_authority),
        },
    })
    _write(output / "candidate.json", result)
    _write(output / "manifest.json", {
        "schemaRevision": "season-endgame-candidate-manifest-v1",
        "formalActiveManifest": False,
        "candidateOnly": True,
        "activePointerChanged": False,
        "seasonRevision": result.get("seasonRevision", ""),
        "dependencyVector": result.get("dependencyVector", {}),
        "gearReleaseId": (result.get("gearRelease") or {}).get("releaseId", ""),
        "gearCatalogRevision": (result.get("catalog") or {}).get("catalogRevision", ""),
        "gearExactRegistryRevision": (result.get("exactRegistry") or {}).get("registryRevision", ""),
        "status": result.get("status", "blocked"),
    })
    _write(output / "gate-summary.json", result.get("gate", {}))
    _write(output / "blocked-diagnostics.json", {
        "status": result.get("status", "blocked"),
        "problemCodes": result.get("problemCodes", []),
        "problems": result.get("problems", []),
        "activePointerChanged": False,
    })
    return 0 if result.get("status") == "candidate" else 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build a fail-closed Season PVE Universe from existing JSON snapshots."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.season_pve_universe import (  # noqa: E402
    UniverseContractError,
    bounded_universe_report,
    build_season_pve_universe,
)


def _json_file(value: str) -> dict:
    path = Path(value).expanduser().resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise argparse.ArgumentTypeError(
            f"cannot read JSON snapshot {path.name}: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError(
            f"JSON snapshot {path.name} must contain an object"
        )
    return payload


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile independently captured source discovery, staging, and "
            "Catalog snapshots. This command performs no network or DB I/O."
        )
    )
    parser.add_argument("--policy", required=True, type=_json_file)
    parser.add_argument("--discovery", required=True, type=_json_file)
    parser.add_argument("--staging", required=True, type=_json_file)
    parser.add_argument("--catalog", required=True, type=_json_file)
    parser.add_argument("--exclusions", type=_json_file)
    parser.add_argument(
        "--mode",
        choices=("current", "end_game"),
        default="current",
        help="Use current-season windows or the complete End Game pool.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the exact bounded JSON report.",
    )
    parser.add_argument(
        "--max-ledger-rows",
        type=int,
        default=100,
        help="Maximum safe ledger rows printed to stdout (0-1000).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    exclusions_payload = args.exclusions or {}
    exclusions = exclusions_payload.get("exclusions")
    if exclusions is None and exclusions_payload:
        raise UniverseContractError(
            "exclusions snapshot requires exclusions"
        )
    report = build_season_pve_universe(
        args.policy,
        args.discovery,
        args.staging,
        args.catalog,
        exclusions=exclusions or [],
        mode=args.mode,
    )
    bounded = bounded_universe_report(
        report,
        max_ledger_rows=args.max_ledger_rows,
    )
    serialized = json.dumps(
        bounded,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if args.output:
        output = args.output.expanduser().resolve()
        if not output.parent.is_dir() or output.is_dir():
            raise UniverseContractError(
                "output parent must exist and output must not be a directory"
            )
        output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if report["status"] == "verified" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except UniverseContractError as error:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reasonCode": "UNIVERSE_CONTRACT_INVALID",
                    "error": str(error)[:500],
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        raise SystemExit(2)

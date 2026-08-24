#!/usr/bin/env python3
"""Build the isolated four-source Midnight Season 2 equipment closure report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.s2_equipment_library_closure import (  # noqa: E402
    S2EquipmentLibraryClosureError,
    build_s2_equipment_library_closure,
)


def _parse_db2_capture(value: str) -> tuple[str, Path]:
    label, separator, path = value.partition("=")
    if not separator or not label.strip() or not path.strip():
        raise argparse.ArgumentTypeError("DB2 capture must use label=path")
    return label.strip(), Path(path.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--crafted-targets", required=True, type=Path)
    parser.add_argument("--official-api-capture", required=True, action="append", type=Path)
    parser.add_argument(
        "--enhancement-api-capture",
        action="append",
        type=Path,
        default=[],
        help="authorized official item captures for gems and crafted optional reagents",
    )
    parser.add_argument("--db2-capture", action="append", type=_parse_db2_capture, default=[])
    parser.add_argument("--crafted-compatibility", type=Path)
    parser.add_argument(
        "--simc-runtime-identity",
        default="",
        help="Bind an already verified immutable SimC runtime identity without clearing the matrix gate.",
    )
    parser.add_argument(
        "--simc-matrix",
        type=Path,
        help="Attach a matrix report captured against this exact closure candidate.",
    )
    parser.add_argument(
        "--compact-variants",
        action="store_true",
        help="emit stable variant join keys and evidence refs without repeating full capture refs per branch",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output.exists():
        print(f"output already exists: {output}", file=sys.stderr)
        return 2
    try:
        report = build_s2_equipment_library_closure(
            inventory=args.inventory,
            crafted_targets=args.crafted_targets,
            official_api_captures=args.official_api_capture,
            enhancement_api_captures=args.enhancement_api_capture,
            db2_captures=dict(args.db2_capture),
            crafted_compatibility=args.crafted_compatibility,
            detailed_variants=not args.compact_variants,
            simc_runtime_identity=args.simc_runtime_identity,
            simc_matrix=args.simc_matrix,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    except S2EquipmentLibraryClosureError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": report["status"],
                "reportId": report["reportId"],
                "fourSourceCandidateTotal": report["coverageCounts"]["fourSourceCandidateTotal"],
                "simcReadyCount": report["coverageCounts"]["simcReadyCount"],
                "blockerCodes": report["blockerCodes"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "verified" else 3


if __name__ == "__main__":
    raise SystemExit(main())

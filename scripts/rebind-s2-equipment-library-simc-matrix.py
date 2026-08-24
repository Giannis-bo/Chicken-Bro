#!/usr/bin/env python3
"""Rebind fixed-runtime SimC evidence after a strict identical-plan check."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.s2_equipment_library_simc_matrix import (
    rebind_s2_equipment_library_simc_matrix_report,
)


def _read(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--source-report", required=True, type=Path)
    parser.add_argument("--source-plan", required=True, type=Path)
    parser.add_argument("--target-plan", required=True, type=Path)
    parser.add_argument("--golden-prefix", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.output.expanduser().resolve()
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    report = rebind_s2_equipment_library_simc_matrix_report(
        _read(args.candidate),
        _read(args.source_report),
        _read(args.source_plan),
        _read(args.target_plan),
        golden_prefix=_read(args.golden_prefix),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "reportId": report["reportId"],
                "candidateReportId": report["candidateReportId"],
                "matrixReuse": report["matrixReuse"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error))

#!/usr/bin/env python3
"""Run the isolated four-source S2 equipment-library SimC matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.s2_equipment_library_simc_matrix import (  # noqa: E402
    assemble_s2_equipment_library_simc_matrix_report,
    build_s2_equipment_library_simc_matrix_plan,
    execute_s2_equipment_library_simc_batches,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--runtime-identity", required=True)
    parser.add_argument("--golden-prefix", required=True, type=Path)
    parser.add_argument("--remote", default="wow-lighthouse")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument(
        "--set-probe-spec",
        action="append",
        default=[],
        help="Limit set/representative probes to CLASS:SPEC; repeat for more pairs",
    )
    parser.add_argument("--plan-output", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    golden = json.loads(args.golden_prefix.read_text(encoding="utf-8"))
    selected_specs = None
    if args.set_probe_spec:
        selected_specs = []
        for value in args.set_probe_spec:
            class_key, separator, spec_key = value.partition(":")
            if not separator or not class_key or not spec_key:
                parser.error(f"--set-probe-spec must be CLASS:SPEC, got {value!r}")
            selected_specs.append((class_key, spec_key))
    plan = build_s2_equipment_library_simc_matrix_plan(
        candidate,
        runtime_identity=args.runtime_identity,
        include_set_probe_specs=selected_specs,
    )
    if args.plan_output:
        plan_output = args.plan_output.expanduser().resolve()
        plan_output.parent.mkdir(parents=True, exist_ok=True)
        plan_output.write_text(
            json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    batches = execute_s2_equipment_library_simc_batches(
        plan,
        remote=args.remote,
        batch_size=args.batch_size,
        workers=args.workers,
        timeout_seconds=args.timeout_seconds,
        progress_callback=lambda completed, total: (
            print(
                json.dumps(
                    {"matrixBatchesCompleted": completed, "matrixBatchesTotal": total},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                file=sys.stderr,
                flush=True,
            )
        ),
    )
    report = assemble_s2_equipment_library_simc_matrix_report(
        candidate,
        plan,
        batch_results=batches,
        golden_prefix=golden,
    )
    output = args.output.expanduser().resolve()
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
                "counts": report["counts"],
                "blockerCodes": report["blockerCodes"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "verified" else 3


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Capture numeric SimC static-attribute readbacks for the S2 runtime build."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.s2_equipment_library_runtime import (  # noqa: E402
    assemble_s2_simc_readback_report,
)
from server.s2_equipment_library_simc_matrix import (  # noqa: E402
    execute_s2_equipment_library_simc_batches,
)


def _atomic_json_write(path: Path, payload: dict) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = handle.name
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = ""
    finally:
        if temporary:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--remote", default="wow-lighthouse")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()

    plan = json.loads(args.plan.expanduser().read_text(encoding="utf-8"))
    variant_jobs = [
        job
        for job in plan.get("jobs") or []
        if isinstance(job, dict)
        and job.get("kind") in {"public_variant", "crafted_variant"}
    ]
    readback_plan = {
        **plan,
        "jobs": variant_jobs,
    }
    batches = execute_s2_equipment_library_simc_batches(
        readback_plan,
        remote=args.remote,
        batch_size=args.batch_size,
        workers=args.workers,
        timeout_seconds=args.timeout_seconds,
        progress_callback=lambda completed, total: print(
            json.dumps(
                {
                    "readbackBatchesCompleted": completed,
                    "readbackBatchesTotal": total,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
            flush=True,
        ),
    )
    report = assemble_s2_simc_readback_report(readback_plan, batches)
    _atomic_json_write(args.output, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "runtimeIdentityStatus": report["runtimeIdentityStatus"],
                "counts": report["counts"],
                "output": str(args.output.expanduser().resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "verified" else 3


if __name__ == "__main__":
    raise SystemExit(main())

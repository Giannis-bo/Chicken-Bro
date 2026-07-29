#!/usr/bin/env python3
"""Run the aggregate-only active 26/14 SimC execution matrix."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.gear_release_tool import expected_spec_pairs
from server.simc_execution_matrix import run_simc_execution_matrix
from server.simulator_payload import (
    parse_simcraft_metrics,
    simcraft_item_name_diagnostics,
    simcraft_only_item_name_diagnostics,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1")
    parser.add_argument("--simc-bin", required=True)
    parser.add_argument("--manifest-revision", required=True)
    parser.add_argument("--pointer-generation", required=True, type=int)
    parser.add_argument("--gear-release-id", required=True)
    parser.add_argument("--community-release-id", required=True)
    parser.add_argument("--gear-catalog-revision", required=True)
    parser.add_argument("--gear-exact-registry-revision", required=True)
    parser.add_argument("--simc-runtime-revision", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--http-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--simc-timeout-seconds", type=float, default=45.0)
    parser.add_argument("--smoke-max-time-seconds", type=int, default=5)
    return parser


def _atomic_json_write(path_value: str, payload: dict[str, Any]) -> None:
    path = Path(path_value).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = handle.name
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
        os.replace(temporary_path, path)
        temporary_path = ""
    finally:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    base_url = str(args.base_url or "").rstrip("/")

    def request_json(method, path, payload, headers):
        body = (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            if isinstance(payload, dict)
            else None
        )
        request = Request(
            f"{base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        started = time.perf_counter()
        try:
            with urlopen(
                request,
                timeout=max(1.0, float(args.http_timeout_seconds)),
            ) as response:
                status = int(response.status)
                raw = response.read()
        except HTTPError as error:
            status = int(error.code)
            raw = error.read()
        duration_ms = (time.perf_counter() - started) * 1000
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            decoded = {}
        return (
            status,
            decoded if isinstance(decoded, dict) else {},
            duration_ms,
        )

    def execute_profile(profile):
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                [
                    str(args.simc_bin),
                    "-",
                    "iterations=1",
                    f"max_time={max(1, int(args.smoke_max_time_seconds))}",
                    "vary_combat_length=0",
                    "calculate_scale_factors=0",
                ],
                input=profile,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=max(1.0, float(args.simc_timeout_seconds)),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return {
                "ran": False,
                "hasDps": False,
                "timedOut": True,
                "durationMs": (time.perf_counter() - started) * 1000,
            }
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        metrics = parse_simcraft_metrics(stdout or stderr)
        diagnostics = simcraft_item_name_diagnostics(stderr)
        trivial_item_name_exit = (
            completed.returncode != 0
            and bool(metrics.get("dps"))
            and bool(diagnostics)
            and simcraft_only_item_name_diagnostics(stderr)
        )
        return {
            "ran": completed.returncode == 0 or trivial_item_name_exit,
            "hasDps": bool(metrics.get("dps")),
            "timedOut": False,
            "durationMs": (time.perf_counter() - started) * 1000,
        }

    report = run_simc_execution_matrix(
        request_json,
        execute_profile,
        expected_specs=expected_spec_pairs(),
        manifest_revision=args.manifest_revision,
        pointer_generation=args.pointer_generation,
        gear_release_id=args.gear_release_id,
        community_release_id=args.community_release_id,
        catalog_revision=args.gear_catalog_revision,
        exact_registry_revision=args.gear_exact_registry_revision,
        simc_runtime_revision=args.simc_runtime_revision,
        observed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    _atomic_json_write(args.output, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report.get("status") == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())

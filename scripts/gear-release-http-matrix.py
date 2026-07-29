#!/usr/bin/env python3
"""Run the aggregate-only active Gear/Community HTTP acceptance matrix."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.gear_release_http_matrix import run_http_matrix
from server.gear_release_tool import expected_spec_pairs


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1")
    parser.add_argument("--manifest-revision", required=True)
    parser.add_argument("--pointer-generation", required=True, type=int)
    parser.add_argument("--gear-release-id", required=True)
    parser.add_argument("--community-release-id", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--candidate-preview", action="store_true")
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
                timeout=max(1.0, float(args.timeout_seconds)),
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

    report = run_http_matrix(
        request_json,
        expected_specs=expected_spec_pairs(),
        manifest_revision=args.manifest_revision,
        pointer_generation=args.pointer_generation,
        gear_release_id=args.gear_release_id,
        community_release_id=args.community_release_id,
        candidate_preview=args.candidate_preview,
        observed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    _atomic_json_write(args.output, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report.get("status") == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())

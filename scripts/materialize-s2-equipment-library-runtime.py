#!/usr/bin/env python3
"""Materialize the verified S2 candidate and exact SimC readback into a release snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.gear_release_tool import validate_gear_snapshot  # noqa: E402
from server.s2_equipment_library_runtime import build_s2_runtime_snapshot  # noqa: E402


def _text(value: Any) -> str:
    return str(value or "").strip()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _load_json(path: Path) -> Any:
    with path.expanduser().resolve().open("r", encoding="utf-8") as handle:
        return json.load(handle)


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
        os.replace(temporary, target)
        temporary = ""
    finally:
        if temporary:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def _official_items(manifest_paths: list[Path]) -> dict[str, Any]:
    items: dict[str, Any] = {}
    for manifest_path in manifest_paths:
        manifest = _load_json(manifest_path)
        if not isinstance(manifest, Mapping):
            raise ValueError(f"official capture manifest must be an object: {manifest_path}")
        root = manifest_path.expanduser().resolve().parent
        for entry in manifest.get("entries") or []:
            if not isinstance(entry, Mapping):
                continue
            match = re.fullmatch(r"/data/wow/item/(\d+)", _text(entry.get("path")))
            response_path = _text(entry.get("responsePath"))
            if not match or not response_path:
                continue
            raw_path = (root / response_path).resolve()
            if root not in raw_path.parents:
                raise ValueError(f"official capture response escapes manifest root: {raw_path}")
            item_id = match.group(1)
            if item_id in items:
                continue
            items[item_id] = _load_json(raw_path)
    return items


def _readback_report_id(report: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_bytes(report)).hexdigest()
    return f"s2-equipment-library-simc-readback:sha256:{digest}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--readback", required=True, type=Path)
    parser.add_argument(
        "--official-capture",
        required=True,
        action="append",
        type=Path,
        help="capture-manifest.json path; repeat for the general and crafted item captures",
    )
    parser.add_argument("--season-revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    candidate = _load_json(args.candidate)
    readback = _load_json(args.readback)
    if not isinstance(readback, Mapping):
        raise ValueError("SimC readback report must be an object")
    readback = dict(readback)
    if not _text(readback.get("reportId")):
        readback["reportId"] = _readback_report_id(readback)
    official_items = _official_items(args.official_capture)
    snapshot = build_s2_runtime_snapshot(
        candidate,
        readback,
        official_items=official_items,
        season_revision=_text(args.season_revision),
    )
    snapshot["runtimeValidation"] = {
        "status": "verified" if not validate_gear_snapshot(snapshot) else "blocked",
        "gearSnapshotProblems": validate_gear_snapshot(snapshot),
        "officialItemCount": len(official_items),
        "officialCaptureManifests": [str(path.expanduser().resolve()) for path in args.official_capture],
    }
    _atomic_json_write(args.output, snapshot)
    summary = {
        "status": snapshot.get("status"),
        "runtimeValidationStatus": snapshot["runtimeValidation"]["status"],
        "seasonRevision": snapshot.get("seasonRevision"),
        "counts": snapshot.get("counts"),
        "blockers": snapshot.get("blockers"),
        "gearSnapshotProblems": snapshot["runtimeValidation"]["gearSnapshotProblems"],
        "output": str(args.output.expanduser().resolve()),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if snapshot.get("status") == "verified" and summary["runtimeValidationStatus"] == "verified" else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)

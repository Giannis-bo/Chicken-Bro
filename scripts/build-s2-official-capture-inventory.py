#!/usr/bin/env python3
"""Build a non-promotable official S2 source-membership inventory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.s2_official_capture_inventory import (  # noqa: E402
    OfficialCaptureInventoryError,
    build_official_capture_inventory,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", required=True, type=Path)
    parser.add_argument("--scope", required=True, type=Path)
    parser.add_argument("--source-policy", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def _output_path(value: Path) -> Path:
    output = (value if value.is_absolute() else ROOT / value).resolve()
    try:
        output.relative_to(ROOT.resolve())
    except ValueError as error:
        raise OfficialCaptureInventoryError(
            "inventory output must stay inside the repository"
        ) from error
    if output.name in {"requirement.json", "evidence.json", "manifest.json"}:
        raise OfficialCaptureInventoryError("inventory cannot replace a Harness control file")
    if output.exists():
        raise OfficialCaptureInventoryError("inventory output already exists")
    return output


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = _output_path(args.output)
    report = build_official_capture_inventory(
        args.capture_root,
        product_scope=args.scope,
        source_policy=args.source_policy,
    )
    _write(output, report)
    print(
        json.dumps(
            {
                "output": output.relative_to(ROOT).as_posix(),
                "reportId": report["reportId"],
                "status": report["status"],
                "blockerCodes": report["blockerCodes"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "verified" else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OfficialCaptureInventoryError, OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)

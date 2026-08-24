#!/usr/bin/env python3
"""Build the crafted option compatibility evidence packet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.s2_crafted_compatibility_evidence import (  # noqa: E402
    S2CraftedCompatibilityEvidenceError,
    build_crafted_compatibility_evidence_from_captures,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", required=True, type=Path)
    parser.add_argument("--db2-capture", required=True, type=Path)
    parser.add_argument("--official-item-capture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.output.expanduser().resolve()
    if output.exists():
        print(f"output already exists: {output}", file=sys.stderr)
        return 2
    try:
        report = build_crafted_compatibility_evidence_from_captures(
            targets=args.targets,
            db2_capture_root=args.db2_capture,
            official_item_capture_root=args.official_item_capture,
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
                    "categoryCount": report["coverage"]["categoryCount"],
                    "categoryVerifiedCount": report["coverage"]["categoryVerifiedCount"],
                    "categoryUnverifiedCount": report["coverage"]["categoryUnverifiedCount"],
                    "recipeCount": report["coverage"]["recipeCount"],
                    "recipeCompatibilityVerifiedCount": report["coverage"]["recipeCompatibilityVerifiedCount"],
                    "blockerCodes": report["blockerCodes"],
                    "output": str(output),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0 if report["status"] == "verified" else 3
    except (S2CraftedCompatibilityEvidenceError, OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

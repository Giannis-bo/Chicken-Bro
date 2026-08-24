#!/usr/bin/env python3
"""Build the finite official category target set for crafted equipment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.s2_crafted_compatibility import (  # noqa: E402
    S2CraftedCompatibilityError,
    build_crafted_slot_category_targets,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe-capture", required=True, type=Path)
    parser.add_argument("--slot-capture", required=True, type=Path)
    parser.add_argument("--crafted-targets", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.output.expanduser().resolve()
    if output.exists():
        print(f"output already exists: {output}", file=sys.stderr)
        return 2
    try:
        result = build_crafted_slot_category_targets(
            recipe_capture_root=args.recipe_capture,
            slot_capture_root=args.slot_capture,
            crafted_targets=args.crafted_targets,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "equipmentRecipeCount": result["equipmentRecipeCount"],
                    "roleCount": len(result["roleIds"]),
                    "categoryCount": len(result["categoryIds"]),
                    "output": str(output),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (S2CraftedCompatibilityError, OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Evaluate one local SimC item-effect probe without network or Catalog writes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.simc_item_effect_probe import evaluate_effect_probe  # noqa: E402


def _read(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--experiment-report", required=True)
    parser.add_argument("--control-report", required=True)
    args = parser.parse_args(argv)
    result = evaluate_effect_probe(_read(args.manifest), _read(args.experiment_report), _read(args.control_report))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

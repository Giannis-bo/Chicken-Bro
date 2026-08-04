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
    parser.add_argument("--runtime-revision", required=True)
    args = parser.parse_args(argv)
    manifest = _read(args.manifest)
    experiment = _read(args.experiment_report)
    control = _read(args.control_report)
    runtime = str(args.runtime_revision or "").strip()
    if not isinstance(manifest, dict) or not isinstance(experiment, dict) or not isinstance(control, dict):
        return 1
    if runtime != str(manifest.get("simcRuntimeRevision") or "").strip() or runtime != str(experiment.get("runtimeRevision") or "").strip() or runtime != str(control.get("runtimeRevision") or "").strip():
        return 1
    result = evaluate_effect_probe(manifest, experiment, control)
    if result.get("status") != "verified":
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

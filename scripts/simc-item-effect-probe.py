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


class _ReasonCodeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        self.exit(2, "CLI_ARGUMENT_INVALID\n")


def _read(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _fail(reason_code: str) -> int:
    sys.stderr.write(reason_code + "\n")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = _ReasonCodeArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--experiment-report", required=True)
    parser.add_argument("--control-report", required=True)
    parser.add_argument("--runtime-revision", required=True)
    args = parser.parse_args(argv)
    try:
        manifest = _read(args.manifest)
        experiment = _read(args.experiment_report)
        control = _read(args.control_report)
    except Exception:
        return _fail("INPUT_JSON_INVALID")
    try:
        result = evaluate_effect_probe(
            manifest,
            experiment,
            control,
            runtime_revision=args.runtime_revision,
        )
    except Exception:
        return _fail("PROBE_INTERNAL_ERROR")
    if result.status != "verified" or result.document is None:
        if result.status == "blocked" and result.issues:
            return _fail(result.issues[0].code)
        return _fail(f"PROBE_{result.status.upper()}")
    sys.stdout.buffer.write(result.document.canonical_bytes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

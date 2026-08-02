#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.chickenbro_eval import (
    evaluate_chickenbro_trace_cases,
    load_chickenbro_eval_cases,
)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate synthetic Chickenbro trace cases without runtime dependencies."
    )
    parser.add_argument(
        "--cases",
        default="tests/fixtures/chickenbro_trace_eval_cases.json",
    )
    args = parser.parse_args()
    summary = evaluate_chickenbro_trace_cases(
        load_chickenbro_eval_cases(args.cases)
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build current-client Journal difficulty membership evidence."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.season_pve_journal_relations import (  # noqa: E402
    build_current_client_journal_membership,
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(body, encoding="utf-8")
    temporary.replace(path)


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--official-capture", type=Path, required=True)
    parser.add_argument("--derived-csv-root", type=Path, required=True)
    parser.add_argument("--client-build", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    capture = read_json(args.official_capture)
    payload = build_current_client_journal_membership(
        capture.get("journalCapture") or {},
        read_csv(args.derived_csv_root / "JournalEncounterItem.csv"),
        read_csv(args.derived_csv_root / "JournalItemXDifficulty.csv"),
        read_csv(args.derived_csv_root / "Difficulty.csv"),
        client_build=args.client_build,
    )
    write_json(args.output, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": str(args.output),
                "summary": payload["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build the deterministic identity for the isolated Midnight Season 2 End Game repository."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.season_endgame_repository import build_endgame_binding  # noqa: E402


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(body, encoding="utf-8")
    temporary.replace(path)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season-metadata", required=True, type=Path)
    parser.add_argument("--source-policy", required=True, type=Path)
    parser.add_argument("--capture-manifest", required=True, type=Path)
    parser.add_argument("--client-build", required=True)
    parser.add_argument("--simc-runtime-revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    binding = build_endgame_binding(
        season_id="midnight-season-2",
        season_metadata=_read_json(args.season_metadata),
        source_policy=_read_json(args.source_policy),
        capture_manifest=_read_json(args.capture_manifest),
        client_build=args.client_build,
        simc_runtime_revision=args.simc_runtime_revision,
    )
    _write_json(args.output, binding)
    print(json.dumps({
        "status": binding["status"],
        "seasonId": binding["seasonId"],
        "seasonRevision": binding["seasonRevision"],
        "problemCodes": sorted({row["code"] for row in binding["problems"]}),
        "output": str(args.output),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if binding["status"] == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())

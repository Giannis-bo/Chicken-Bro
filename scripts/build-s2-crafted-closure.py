#!/usr/bin/env python3
"""Build a local, non-promotable closure report for one S2 recipe probe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.s2_crafted_closure import (  # noqa: E402
    CraftedClosureError,
    build_crafted_closure_report,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", required=True, type=Path)
    parser.add_argument("--recipe-id", required=True)
    parser.add_argument("--simc-probe", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def _output_path(value: Path, *, repo_root: Path) -> Path:
    output = (value if value.is_absolute() else repo_root / value).resolve()
    try:
        output.relative_to(repo_root.resolve())
    except ValueError as error:
        raise CraftedClosureError("closure output must stay inside the repository") from error
    if output.name in {"requirement.json", "evidence.json", "manifest.json"}:
        raise CraftedClosureError("closure cannot replace a Harness control file")
    if output.exists():
        raise CraftedClosureError("closure output already exists")
    return output


def _write(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path, *, repo_root: Path) -> dict[str, Any]:
    candidate = (path if path.is_absolute() else repo_root / path).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CraftedClosureError("SimC probe input is unavailable or invalid") from error
    if not isinstance(payload, Mapping):
        raise CraftedClosureError("SimC probe input must be an object")
    return dict(payload)


def main(argv: list[str] | None = None, *, repo_root: Path | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path.cwd().resolve() if repo_root is None else Path(repo_root).resolve()
    output = _output_path(args.output, repo_root=root)
    simc_probe = (
        _read_json(args.simc_probe, repo_root=root)
        if args.simc_probe is not None
        else None
    )
    report = build_crafted_closure_report(
        args.capture_root,
        recipe_id=args.recipe_id,
        simc_probe=simc_probe,
    )
    _write(output, report)
    print(
        json.dumps(
            {
                "output": output.relative_to(root).as_posix(),
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
    except (CraftedClosureError, OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)

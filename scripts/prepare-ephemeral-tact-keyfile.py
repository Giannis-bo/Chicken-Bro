#!/usr/bin/env python3
"""Prepare an approved, target-only TACT keyfile and redacted audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.season_pve_client_relations import (  # noqa: E402
    write_ephemeral_tact_keyfile,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _input(path: Path) -> dict[str, object]:
    return {
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as output:
        temporary_path = Path(output.name)
        json.dump(payload, output, ensure_ascii=False, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary_path, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-keyfile", type=Path, required=True)
    parser.add_argument(
        "--approved-public-keyfile",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--static-coverage-audit",
        type=Path,
        required=True,
    )
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output-keyfile", type=Path, required=True)
    parser.add_argument("--output-audit", type=Path, required=True)
    args = parser.parse_args()

    commit = args.source_commit.lower()
    if (
        len(commit) != 40
        or any(character not in "0123456789abcdef" for character in commit)
    ):
        parser.error("--source-commit must be a full 40-character SHA")
    inputs = [
        args.base_keyfile,
        args.approved_public_keyfile,
        args.static_coverage_audit,
    ]
    if not all(path.is_file() for path in inputs):
        parser.error("all key preparation inputs must be files")
    if args.output_keyfile.exists() or args.output_audit.exists():
        parser.error("output paths must not already exist")

    static_audit = json.loads(
        args.static_coverage_audit.read_text(encoding="utf-8")
    )
    static_coverage = static_audit.get("coverage")
    if (
        static_audit.get("status") != "blocked"
        or static_audit.get("authority", {}).get("keyMaterialEmitted")
        is not False
        or not isinstance(static_coverage, dict)
        or static_coverage.get("summary", {}).get("targetKeyCount") != 12
        or static_coverage.get("summary", {}).get("targetRecordCount") != 178
    ):
        raise ValueError(
            "static coverage audit must retain the redacted 12-key, "
            "178-record baseline"
        )

    args.output_keyfile.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=args.output_keyfile.parent,
        prefix=f".{args.output_keyfile.name}.",
        delete=False,
    ) as output:
        temporary_keyfile = Path(output.name)
        base_entries = json.loads(
            args.base_keyfile.read_text(encoding="utf-8")
        )
        with args.approved_public_keyfile.open(
            encoding="utf-8"
        ) as public_source:
            coverage = write_ephemeral_tact_keyfile(
                base_key_entries=base_entries,
                approved_public_key_lines=public_source,
                target_keys=static_coverage["targetKeys"],
                destination=output,
            )
        output.flush()
        os.fsync(output.fileno())
    os.chmod(temporary_keyfile, 0o600)
    os.replace(temporary_keyfile, args.output_keyfile)

    payload: dict[str, object] = {
        "schemaVersion": 1,
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "status": coverage["status"],
        "authority": {
            "type": "approved_public_third_party_key_snapshot",
            "repository": "wowdev/TACTKeys",
            "commit": commit,
            "sourceRawUrl": (
                "https://raw.githubusercontent.com/wowdev/TACTKeys/"
                f"{commit}/WoW.txt"
            ),
            "auditContainsKeyMaterial": False,
            "ephemeralKeyfileContainsKeyMaterial": True,
        },
        "inputs": {
            "baseKeyfile": _input(args.base_keyfile),
            "approvedPublicWoWTxt": _input(
                args.approved_public_keyfile
            ),
            "staticCoverageAudit": _input(
                args.static_coverage_audit
            ),
        },
        "coverage": coverage,
        "ephemeralOutput": {
            **_input(args.output_keyfile),
            "mode": "0600",
        },
        "productionMutation": False,
        "releasePointerMutation": False,
    }
    _atomic_json(args.output_audit, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "summary": coverage["summary"],
                "auditContainsKeyMaterial": False,
            },
            sort_keys=True,
        )
    )
    return 0 if payload["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())

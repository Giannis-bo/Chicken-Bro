#!/usr/bin/env python3
"""Build an S2 official-fact snapshot from a local capture root only.

This CLI intentionally has no live mode.  It validates raw response file
identity and consumes only the local normalized official-fact payload produced
by a future capture/normalizer step.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from server.s2_official_api_fact_snapshot import (  # noqa: E402
    OfficialFactSnapshotContractError,
    build_official_api_fact_snapshot,
    validate_capture_manifest,
    validate_official_api_fact_snapshot,
)
from server.s2_official_fact_scope import (  # noqa: E402
    load_official_fact_scope,
    load_product_content_scope,
)


class OfflineSnapshotCliError(ValueError):
    """Raised when a local capture root cannot produce a safe snapshot."""


_NON_OFFICIAL_INPUT_KEY_TOKENS = (
    "simc",
    "raider",
    "wowhead",
    "catalog",
    "client",
)


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise OfflineSnapshotCliError(f"unable to read {label}") from error
    if not isinstance(payload, Mapping):
        raise OfflineSnapshotCliError(f"{label} must be an object")
    return dict(payload)


def _reject_non_official_input_keys(value: Any, path: str = "normalized-facts") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).casefold()
            if any(token in key_text for token in _NON_OFFICIAL_INPUT_KEY_TOKENS):
                raise OfflineSnapshotCliError(
                    f"non-official fact input is not allowed: {path}.{key}"
                )
            _reject_non_official_input_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_non_official_input_keys(child, f"{path}[{index}]")


def _capture_file(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    root_resolved = root.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise OfflineSnapshotCliError(
            f"capture response path escapes capture root: {relative_path}"
        )
    if not candidate.is_file():
        raise OfflineSnapshotCliError(
            f"capture response file is missing: {relative_path}"
        )
    return candidate


def _validate_raw_files(capture_root: Path, manifest: Mapping[str, Any]) -> None:
    entries = manifest["entries"]
    expected_paths = set()
    for entry in entries:
        relative_path = str(entry["responsePath"])
        expected_paths.add(relative_path)
        response_path = _capture_file(capture_root, relative_path)
        content = response_path.read_bytes()
        if len(content) != entry["responseBytes"]:
            raise OfflineSnapshotCliError(
                f"capture response byte count mismatch: {relative_path}"
            )
        digest = hashlib.sha256(content).hexdigest()
        if digest != entry["responseSha256"]:
            raise OfflineSnapshotCliError(
                f"capture response hash mismatch: {relative_path}"
            )

    raw_root = capture_root / "raw"
    if raw_root.exists():
        actual_paths = {
            str(path.relative_to(capture_root)).replace("\\", "/")
            for path in raw_root.rglob("*")
            if path.is_file()
        }
        extra_paths = sorted(actual_paths - expected_paths)
        if extra_paths:
            raise OfflineSnapshotCliError(
                "capture root contains raw files absent from manifest: "
                + ", ".join(extra_paths)
            )


def build_from_capture_root(
    *,
    product_scope_path: Path,
    fact_scope_path: Path,
    capture_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    product_scope = load_product_content_scope(product_scope_path)
    fact_scope = load_official_fact_scope(fact_scope_path)
    manifest_raw = _read_json(capture_root / "capture-manifest.json", "capture manifest")
    manifest = validate_capture_manifest(manifest_raw)
    _validate_raw_files(capture_root, manifest)
    normalized_facts = _read_json(
        capture_root / "normalized-facts.json",
        "normalized official facts",
    )
    _reject_non_official_input_keys(normalized_facts)
    scope_counts = normalized_facts.get("scopeCounts")
    if not isinstance(scope_counts, Mapping):
        raise OfflineSnapshotCliError(
            "normalized official facts require scopeCounts"
        )
    snapshot = build_official_api_fact_snapshot(
        product_scope=product_scope,
        fact_scope=fact_scope,
        capture_manifest=manifest,
        scope_counts=scope_counts,
        source_facts=normalized_facts.get("sourceFacts") or [],
        item_facts=normalized_facts.get("itemFacts") or [],
        exclusion_ledger=normalized_facts.get("exclusionLedger") or [],
        unresolved_facts=normalized_facts.get("unresolvedFacts") or [],
    )
    validate_official_api_fact_snapshot(snapshot, scope=product_scope)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return snapshot


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an S2 official-fact snapshot from a local capture root."
    )
    parser.add_argument("--scope", required=True, type=Path)
    parser.add_argument("--fact-scope", required=True, type=Path)
    parser.add_argument("--capture-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        snapshot = build_from_capture_root(
            product_scope_path=args.scope,
            fact_scope_path=args.fact_scope,
            capture_root=args.capture_root,
            output_path=args.output,
        )
    except (OfflineSnapshotCliError, OfficialFactSnapshotContractError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except SystemExit:
        raise
    summary = {
        "status": snapshot["status"],
        "officialApiFactSnapshotRevision": snapshot[
            "officialApiFactSnapshotRevision"
        ],
        "unresolvedFactCount": len(snapshot["unresolvedFacts"]),
        "excludedCount": len(snapshot["exclusionLedger"]),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if snapshot["status"] == "verified" else 3


if __name__ == "__main__":
    raise SystemExit(main())

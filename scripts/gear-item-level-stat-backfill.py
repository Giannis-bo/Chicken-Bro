#!/usr/bin/env python3
"""Apply the validated instance-1305 44-pair stat repair to PostgreSQL staging."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable, Mapping

from server.db import connect_postgres
from server.gear_item_level_stat_backfill import (
    BACKFILL_SCHEMA_REVISION,
    GearItemLevelStatBackfillError,
    backfill_exact_rows,
    target_pairs,
)
from server.gear_item_level_stat_probe import (
    load_instance_items,
    load_profile_presets,
    resolve_item_level_stat,
)
from server.gear_release_resource_probe import (
    ReadOnlyConnectionFactory,
    require_postgres_only_environment,
)


MAX_ARTIFACT_BYTES = 2 * 1024 * 1024
PROTECTED_NAMES = {"requirement.json", "evidence.json", "manifest.json"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--backup-output", required=True)
    parser.add_argument(
        "--simc-bin",
        default=os.environ.get("WOW_SIMC_BIN", "/opt/wow-simc/current/simc"),
    )
    parser.add_argument(
        "--simc-commit-file",
        default=os.environ.get("SIMC_COMMIT_FILE", "/opt/wow-simc/.commit"),
    )
    return parser


def _repository_path(
    repo_root: Path,
    value: str,
    *,
    output: bool = False,
) -> Path:
    root = repo_root.resolve()
    raw = Path(value)
    path = (raw if raw.is_absolute() else root / raw).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise GearItemLevelStatBackfillError(
            "backfill artifacts must stay inside the repository"
        ) from exc
    if output and path.name in PROTECTED_NAMES:
        raise GearItemLevelStatBackfillError(
            "backfill cannot replace a Harness control file"
        )
    if output and path.exists():
        raise GearItemLevelStatBackfillError(
            "backfill output already exists"
        )
    return path


def _load_json(path: Path) -> dict[str, Any]:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise GearItemLevelStatBackfillError(
            "probe report is unavailable"
        ) from exc
    if len(content) > MAX_ARTIFACT_BYTES:
        raise GearItemLevelStatBackfillError(
            "probe report exceeds its size limit"
        )
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GearItemLevelStatBackfillError(
            "probe report is invalid"
        ) from exc
    if not isinstance(value, dict):
        raise GearItemLevelStatBackfillError(
            "probe report must be one object"
        )
    return value


def _simc_identity(binary_path: str, commit_file: str) -> tuple[str, str]:
    binary = Path(binary_path).resolve()
    revision_path = Path(commit_file).resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise GearItemLevelStatBackfillError(
            "configured SimC binary is unavailable"
        )
    try:
        revision = revision_path.read_text(encoding="utf-8").strip().lower()
    except OSError as exc:
        raise GearItemLevelStatBackfillError(
            "configured SimC revision is unavailable"
        ) from exc
    digest = hashlib.sha256()
    with binary.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return revision, digest.hexdigest()


def _atomic_json_write(path: Path, payload: Mapping[str, Any]) -> str:
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        + "\n"
    ).encode("utf-8")
    if len(encoded) > MAX_ARTIFACT_BYTES:
        raise GearItemLevelStatBackfillError(
            "backfill artifact exceeds its size limit"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = None
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        os.write(descriptor, encoded)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.replace(temporary, path)
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    return hashlib.sha256(encoded).hexdigest()


@contextlib.contextmanager
def _configured_simc_binary(path: str):
    previous = os.environ.get("WOW_SIMC_BIN")
    os.environ["WOW_SIMC_BIN"] = path
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("WOW_SIMC_BIN", None)
        else:
            os.environ["WOW_SIMC_BIN"] = previous


def _report_identity(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "gear-item-level-stat-backfill:sha256:" + hashlib.sha256(
        encoded
    ).hexdigest()


def main(
    argv: list[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    repo_root: Path | None = None,
    read_connection_factory: Callable[[], Any] | None = None,
    write_connection_factory: Callable[[], Any] | None = None,
    simc_identity_fn: Callable[[str, str], tuple[str, str]] = _simc_identity,
    item_loader: Callable[[Any, str, str], list[dict[str, Any]]] = load_instance_items,
    profile_loader: Callable[[Any], list[tuple[str, str, str, str]]] = load_profile_presets,
    resolver: Callable[
        [
            Mapping[str, Any],
            int,
            Mapping[str, Any],
            list[tuple[str, str, str, str]],
        ],
        Mapping[str, Any],
    ] = resolve_item_level_stat,
    backfill_runner: Callable[..., Mapping[str, Any]] = backfill_exact_rows,
) -> int:
    args = _parser().parse_args(argv)
    environment = os.environ if environ is None else environ
    require_postgres_only_environment(environment)
    root = Path.cwd().resolve() if repo_root is None else Path(repo_root).resolve()
    probe_path = _repository_path(root, args.probe_report)
    output_path = _repository_path(root, args.output, output=True)
    backup_path = _repository_path(root, args.backup_output, output=True)
    probe_report = _load_json(probe_path)
    simc_revision, binary_sha = simc_identity_fn(
        args.simc_bin,
        args.simc_commit_file,
    )
    pairs = target_pairs(
        probe_report,
        simc_revision=simc_revision,
        simc_binary_sha256=binary_sha,
    )

    raw_read_factory = read_connection_factory or (
        lambda: connect_postgres(str(environment.get("WOW_DATABASE_URL") or ""))
    )
    read_only_factory = ReadOnlyConnectionFactory(raw_read_factory)
    read_connection = read_only_factory()
    try:
        items = item_loader(read_connection, "1305", "raid")
        profiles = profile_loader(read_connection)
    finally:
        try:
            read_connection.rollback()
        finally:
            read_connection.close()
    items_by_id = {
        str(item.get("itemId") or "").strip(): item
        for item in items
        if isinstance(item, Mapping)
    }
    resolved_by_pair: dict[tuple[str, int], Mapping[str, Any]] = {}
    track_by_level = {
        263: {"difficultyKey": "champion", "itemLevel": 263},
        276: {"difficultyKey": "hero", "itemLevel": 276},
        289: {"difficultyKey": "myth", "itemLevel": 289},
        298: {"difficultyKey": "void_upgrade", "itemLevel": 298},
    }
    with _configured_simc_binary(args.simc_bin):
        for item_id, item_level in pairs:
            item = items_by_id.get(item_id)
            if not item:
                raise GearItemLevelStatBackfillError(
                    "one validated target item is unavailable"
                )
            resolved_by_pair[(item_id, item_level)] = resolver(
                item,
                item_level,
                track_by_level[item_level],
                profiles,
            )

    def write_backup(
        original_rows: list[dict[str, Any]],
        pointer: dict[str, Any],
    ) -> dict[str, str]:
        payload = {
            "schemaRevision": "gear-item-level-stat-backfill-backup-v1",
            "sourceProbeReportId": str(probe_report.get("reportId") or ""),
            "simcRuntime": {
                "revision": simc_revision,
                "binarySha256": binary_sha,
            },
            "pointer": pointer,
            "rows": original_rows,
        }
        digest = _atomic_json_write(backup_path, payload)
        return {
            "path": backup_path.relative_to(root).as_posix(),
            "sha256": digest,
        }

    raw_write_factory = write_connection_factory or (
        lambda: connect_postgres(str(environment.get("WOW_DATABASE_URL") or ""))
    )
    write_connection = raw_write_factory()
    try:
        result = dict(
            backfill_runner(
                write_connection,
                report=probe_report,
                resolved_by_pair=resolved_by_pair,
                simc_revision=simc_revision,
                simc_binary_sha256=binary_sha,
                backup_writer=write_backup,
            )
        )
    finally:
        write_connection.close()
    if result.get("status") != "pass" or result.get(
        "schemaRevision"
    ) != BACKFILL_SCHEMA_REVISION:
        raise GearItemLevelStatBackfillError(
            "backfill runner did not return a pass result"
        )
    result["sourceProbeReportId"] = str(probe_report.get("reportId") or "")
    result["simcRuntime"] = {
        "revision": simc_revision,
        "binarySha256": binary_sha,
    }
    result["reportId"] = _report_identity(result)
    _atomic_json_write(output_path, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "updatedVariantCount": result["updatedVariantCount"],
                "reportId": result["reportId"],
                "output": output_path.relative_to(root).as_posix(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GearItemLevelStatBackfillError as exc:
        message = str(exc)
        message = re.sub(r"postgres(?:ql)?://\\S+", "[redacted]", message)
        print(message, file=sys.stderr)
        raise SystemExit(2)

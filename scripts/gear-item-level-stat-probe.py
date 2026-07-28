#!/usr/bin/env python3
"""Run the fixed no-write 48-pair SimC stat probe for raid instance 1305."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable, Mapping

from server.db import connect_postgres
from server.gear_item_level_stat_probe import (
    GearItemLevelStatProbeError,
    build_probe_report,
    load_instance_items,
    load_profile_presets,
    resolve_item_level_stat,
)
from server.gear_release_resource_probe import (
    ReadOnlyConnectionFactory,
    require_postgres_only_environment,
)


MAX_REPORT_BYTES = 256 * 1024


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance-id", default="1305")
    parser.add_argument("--source-type", default="raid")
    parser.add_argument(
        "--simc-bin",
        default=os.environ.get("WOW_SIMC_BIN", "/opt/wow-simc/current/simc"),
    )
    parser.add_argument(
        "--simc-commit-file",
        default=os.environ.get("SIMC_COMMIT_FILE", "/opt/wow-simc/.commit"),
    )
    parser.add_argument("--output", required=True)
    return parser


def _repository_output(repo_root: Path, value: str) -> Path:
    root = repo_root.resolve()
    raw = Path(value)
    output = (raw if raw.is_absolute() else root / raw).resolve()
    try:
        output.relative_to(root)
    except ValueError as exc:
        raise GearItemLevelStatProbeError(
            "probe output must stay inside the repository"
        ) from exc
    if output.name in {"requirement.json", "evidence.json", "manifest.json"}:
        raise GearItemLevelStatProbeError(
            "probe cannot replace a Harness control file"
        )
    if output.exists():
        raise GearItemLevelStatProbeError("probe output already exists")
    return output


def _simc_identity(binary_path: str, commit_file: str) -> tuple[str, str]:
    binary = Path(binary_path).resolve()
    revision_path = Path(commit_file).resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise GearItemLevelStatProbeError("configured SimC binary is unavailable")
    try:
        revision = revision_path.read_text(encoding="utf-8").strip().lower()
    except OSError as exc:
        raise GearItemLevelStatProbeError(
            "configured SimC revision is unavailable"
        ) from exc
    digest = hashlib.sha256()
    with binary.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return revision, digest.hexdigest()


def _atomic_write(path: Path, report: Mapping[str, Any]) -> None:
    encoded = (
        json.dumps(
            report,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    if len(encoded) > MAX_REPORT_BYTES:
        raise GearItemLevelStatProbeError("probe report exceeds its size limit")
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


def main(
    argv: list[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    repo_root: Path | None = None,
    connection_factory: Callable[[], Any] | None = None,
    simc_identity_fn: Callable[[str, str], tuple[str, str]] = _simc_identity,
    item_loader: Callable[[Any, str, str], list[dict[str, Any]]] = load_instance_items,
    resolver: Callable[[dict[str, Any], int, dict[str, Any]], Mapping[str, Any]]
    | None = None,
) -> int:
    args = _parser().parse_args(argv)
    environment = os.environ if environ is None else environ
    require_postgres_only_environment(environment)
    root = Path.cwd().resolve() if repo_root is None else Path(repo_root).resolve()
    output = _repository_output(root, args.output)
    simc_revision, binary_sha = simc_identity_fn(
        args.simc_bin,
        args.simc_commit_file,
    )
    raw_factory = connection_factory or (
        lambda: connect_postgres(str(environment.get("WOW_DATABASE_URL") or ""))
    )
    read_only_factory = ReadOnlyConnectionFactory(raw_factory)
    connection = read_only_factory()
    try:
        items = item_loader(connection, args.instance_id, args.source_type)
        profiles = [] if resolver is not None else load_profile_presets(connection)
        resolve = resolver or (
            lambda item, item_level, track: resolve_item_level_stat(
                item,
                item_level,
                track,
                profiles,
            )
        )
        with _configured_simc_binary(args.simc_bin):
            report = build_probe_report(
                items,
                resolver=resolve,
                instance_id=args.instance_id,
                source_type=args.source_type,
                simc_revision=simc_revision,
                simc_binary_sha256=binary_sha,
            )
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
    _atomic_write(output, report)
    written = output.relative_to(root).as_posix()
    print(
        json.dumps(
            {
                "output": written,
                "reportId": report["reportId"],
                "status": report["status"],
                "exactPairCount": report["exactPairCount"],
                "failedPairCount": report["failedPairCount"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GearItemLevelStatProbeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)

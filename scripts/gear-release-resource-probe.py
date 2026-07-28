#!/usr/bin/env python3
"""Run one bounded, no-seal Community Release resource probe."""

from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import sys
from typing import Any, Callable, Mapping

from server.db import connect_postgres
from server.gear_release_resource_probe import (
    ReadOnlyConnectionFactory,
    ResourceProbeError,
    require_postgres_only_environment,
    run_resource_probe,
)
from server.gear_release_store import GearReleaseStore
from server.gear_release_tool import expected_spec_pairs


MAX_REPORT_BYTES = 256 * 1024


def _cleanup_on_signal(signum: int, _frame: Any) -> None:
    raise SystemExit(128 + int(signum))


@contextlib.contextmanager
def _resource_probe_signal_handlers():
    previous = {}
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.getsignal(signum)
            signal.signal(signum, _cleanup_on_signal)
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gear-release-id", required=True)
    parser.add_argument("--simc-runtime-revision", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--now", default="")
    parser.add_argument("--level", type=int, default=90)
    parser.add_argument("--temporary-root", default="")
    return parser


def _repository_path(
    repo_root: Path,
    value: str,
    *,
    output: bool = False,
) -> Path:
    root = repo_root.resolve()
    raw = Path(value)
    candidate = (raw if raw.is_absolute() else root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ResourceProbeError(
            "resource probe paths must stay inside the repository"
        ) from exc
    if output and candidate.name in {
        "requirement.json",
        "evidence.json",
        "manifest.json",
    }:
        raise ResourceProbeError(
            "resource probe cannot replace a Harness control file"
        )
    return candidate


def _atomic_write_report(
    path: Path,
    report: Mapping[str, Any],
    *,
    repo_root: Path,
) -> str:
    output = _repository_path(repo_root, str(path), output=True)
    if output.exists():
        raise ResourceProbeError("resource probe output already exists")
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
        raise ResourceProbeError("resource probe report exceeds its hard size limit")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    descriptor = None
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(descriptor, encoded)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.replace(temporary, output)
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    return output.relative_to(repo_root.resolve()).as_posix()


def main(
    argv: list[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    repo_root: Path | None = None,
    store_factory: Callable[[], Any] | None = None,
    run_probe_fn: Callable[..., Mapping[str, Any]] = run_resource_probe,
) -> int:
    args = _parser().parse_args(argv)
    environment = os.environ if environ is None else environ
    require_postgres_only_environment(environment)
    root = Path.cwd().resolve() if repo_root is None else Path(repo_root).resolve()
    output = _repository_path(root, args.output, output=True)
    if output.exists():
        raise ResourceProbeError("resource probe output already exists")
    if not 1 <= args.level <= 100:
        raise ResourceProbeError("resource probe level is outside its fixed bound")

    if store_factory is None:
        database_url = str(environment.get("WOW_DATABASE_URL") or "")
        connection_factory = ReadOnlyConnectionFactory(
            lambda: connect_postgres(database_url)
        )
        store_factory = lambda: GearReleaseStore(connection_factory)
    store = store_factory()
    release = store.get_release(args.gear_release_id)
    if not release:
        raise ResourceProbeError("resource probe Gear Release is unavailable")
    snapshot = store.snapshot_gear_release_for_community_builder(
        args.gear_release_id
    )
    dependencies = (
        release.get("dependencyRevisions")
        if isinstance(release.get("dependencyRevisions"), dict)
        else {}
    )
    temporary_root = (
        _repository_path(root, args.temporary_root)
        if args.temporary_root
        else None
    )
    with _resource_probe_signal_handlers():
        report = run_probe_fn(
            store,
            gear_release_descriptor=release,
            gear_snapshot=snapshot,
            dependency_revisions=dependencies,
            expected_specs=expected_spec_pairs(),
            simc_runtime_revision=args.simc_runtime_revision,
            now=args.now
            or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            level=args.level,
            temporary_root=temporary_root,
        )
    written = _atomic_write_report(output, report, repo_root=root)
    print(json.dumps({
        "output": written,
        "reportId": str(report.get("reportId") or ""),
        "status": str(report.get("status") or "blocked"),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if report.get("status") == "pass" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ResourceProbeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)

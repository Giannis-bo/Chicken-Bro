#!/usr/bin/env python3
"""Bounded, aggregate-only resource probe for Community Release preparation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import resource
import sys
import tempfile
import time
from typing import Any, Callable, Iterable, Mapping


SCHEMA_REVISION = "gear-release-resource-probe-v1"
REPORT_PREFIX = "gear-release-resource-probe:sha256:"
BUILDER_REVISION = "community-release-prepared-index-v1"
DEFAULT_LIMITS = {
    "elapsedMilliseconds": 300_000,
    "peakRssObservedBytes": 2_000_000_000,
    "temporaryBytesObserved": 268_435_456,
}
_WRITE_STATEMENT = re.compile(
    r"""
    (?:
        ^\s*(?:INSERT|UPDATE|DELETE|MERGE|TRUNCATE|ALTER|CREATE|DROP|
             GRANT|REVOKE|COPY|VACUUM|ANALYZE|REFRESH|CALL)\b
        |
        \b(?:INSERT\s+INTO|UPDATE\s+[\w".]+|DELETE\s+FROM|MERGE\s+INTO)\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


class ResourceProbeError(RuntimeError):
    pass


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _integer(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def _pointer_identity(pointer: Any) -> dict[str, Any]:
    value = pointer if isinstance(pointer, Mapping) else {}
    return {
        "environment": _text(value.get("environment") or "retail"),
        "pointerMode": _text(value.get("pointerMode")),
        "manifestRevision": _text(value.get("manifestRevision")),
        "generation": _integer(value.get("generation")),
        "rollbackManifestRevision": _text(value.get("rollbackManifestRevision")),
    }


def require_postgres_only_environment(environ: Mapping[str, str]) -> None:
    if (
        _text(environ.get("WOW_DATABASE_RUNTIME")) != "postgres_only"
        or not _text(environ.get("WOW_DATABASE_URL"))
    ):
        raise ResourceProbeError(
            "resource probe requires WOW_DATABASE_RUNTIME=postgres_only and WOW_DATABASE_URL"
        )


class _ReadOnlyCursor:
    def __init__(self, cursor: Any, owner: "ReadOnlyConnectionFactory"):
        self._cursor = cursor
        self._owner = owner

    def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        normalized = " ".join(str(statement or "").split())
        self._owner.metrics["totalStatements"] += 1
        if _WRITE_STATEMENT.search(normalized):
            self._owner.metrics["writeStatements"] += 1
            raise ResourceProbeError("resource probe rejected a write statement")
        self._owner.metrics["readStatements"] += 1
        return self._cursor.execute(statement, *args, **kwargs)

    def executemany(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        normalized = " ".join(str(statement or "").split())
        self._owner.metrics["totalStatements"] += 1
        if _WRITE_STATEMENT.search(normalized):
            self._owner.metrics["writeStatements"] += 1
            raise ResourceProbeError("resource probe rejected a write statement")
        self._owner.metrics["readStatements"] += 1
        return self._cursor.executemany(statement, *args, **kwargs)

    def __enter__(self) -> "_ReadOnlyCursor":
        self._cursor.__enter__()
        return self

    def __exit__(self, *args: Any) -> Any:
        return self._cursor.__exit__(*args)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class _ReadOnlyConnection:
    def __init__(self, connection: Any, owner: "ReadOnlyConnectionFactory"):
        self._connection = connection
        self._owner = owner

    def cursor(self, *args: Any, **kwargs: Any) -> _ReadOnlyCursor:
        return _ReadOnlyCursor(
            self._connection.cursor(*args, **kwargs),
            self._owner,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)


class ReadOnlyConnectionFactory:
    """Set PostgreSQL default read-only and reject any detected write SQL."""

    def __init__(
        self,
        connection_factory: Callable[[], Any],
        *,
        statement_timeout_ms: int = 15_000,
        lock_timeout_ms: int = 1_000,
    ):
        self._connection_factory = connection_factory
        self._statement_timeout_ms = _integer(statement_timeout_ms)
        self._lock_timeout_ms = _integer(lock_timeout_ms)
        if not 1 <= self._statement_timeout_ms <= 15_000:
            raise ResourceProbeError("resource probe statement timeout is invalid")
        if not 1 <= self._lock_timeout_ms <= 1_000:
            raise ResourceProbeError("resource probe lock timeout is invalid")
        self.metrics = {
            "totalStatements": 0,
            "readStatements": 0,
            "writeStatements": 0,
        }

    def __call__(self) -> _ReadOnlyConnection:
        connection = self._connection_factory()
        set_session = getattr(connection, "set_session", None)
        if callable(set_session):
            set_session(readonly=True, autocommit=False)
        elif hasattr(connection, "read_only"):
            connection.read_only = True
        elif hasattr(connection, "readonly"):
            connection.readonly = True
        else:
            raise ResourceProbeError(
                "resource probe connection cannot enforce default read-only"
            )
        with connection.cursor() as cursor:
            cursor.execute(
                f"SET statement_timeout = '{self._statement_timeout_ms}ms'"
            )
            cursor.execute(f"SET lock_timeout = '{self._lock_timeout_ms}ms'")
        return _ReadOnlyConnection(connection, self)


def current_peak_rss_bytes() -> int:
    observed = _integer(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return observed if sys.platform == "darwin" else observed * 1024


def _directory_bytes(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def _write_statement_count(store: Any) -> int:
    factory = getattr(store, "connection_factory", None)
    metrics = getattr(factory, "metrics", None)
    if isinstance(metrics, Mapping):
        return _integer(metrics.get("writeStatements"))
    metrics = getattr(store, "resource_probe_statement_metrics", None)
    if callable(metrics):
        values = metrics()
        return _integer(
            values.get("writeStatements")
            if isinstance(values, Mapping)
            else 0
        )
    return 0


def _prepared_summary(result: Any) -> dict[str, Any]:
    value = result if isinstance(result, Mapping) else {}
    release = value.get("release") if isinstance(value.get("release"), Mapping) else {}
    gate = value.get("gate") if isinstance(value.get("gate"), Mapping) else {}
    source = release.get("source") if isinstance(release.get("source"), Mapping) else {}
    return {
        "communityReleaseStatus": _text(
            release.get("releaseStatus") or gate.get("status")
        ),
        "communityContentHash": _text(release.get("contentHash")),
        "stagingTemplateCount": _integer(
            gate.get("stagingTemplateCount") or source.get("stagingTemplateCount")
        ),
        "winnerSpecCount": _integer(gate.get("winnerSpecCount")),
        "winnerHeroSlotCount": _integer(gate.get("winnerHeroSlotCount")),
    }


def build_resource_report(
    *,
    gear_release_id: str,
    season_revision: str,
    simc_runtime_revision: str,
    builder_revision: str,
    pointer_before: Mapping[str, Any],
    pointer_after: Mapping[str, Any],
    metrics: Mapping[str, Any],
    limits: Mapping[str, Any],
    prepared: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_metrics = {
        key: _integer(metrics.get(key))
        for key in (
            "elapsedMilliseconds",
            "peakRssObservedBytes",
            "temporaryBytesObserved",
            "writeStatementCount",
        )
    }
    normalized_limits = {
        key: _integer(limits.get(key))
        for key in (
            "elapsedMilliseconds",
            "peakRssObservedBytes",
            "temporaryBytesObserved",
        )
    }
    before = _pointer_identity(pointer_before)
    after = _pointer_identity(pointer_after)
    problems = []
    if before != after:
        problems.append("RESOURCE_POINTER_CHANGED")
    if normalized_metrics["writeStatementCount"]:
        problems.append("RESOURCE_WRITE_STATEMENT_DETECTED")
    for field, code in (
        ("elapsedMilliseconds", "RESOURCE_ELAPSED_EXCEEDED"),
        ("peakRssObservedBytes", "RESOURCE_PEAK_RSS_EXCEEDED"),
        ("temporaryBytesObserved", "RESOURCE_TEMPORARY_BYTES_EXCEEDED"),
    ):
        if (
            normalized_limits[field] <= 0
            or normalized_metrics[field] > normalized_limits[field]
        ):
            problems.append(code)
    identity = {
        "schemaRevision": SCHEMA_REVISION,
        "status": "blocked" if problems else "pass",
        "gearReleaseId": _text(gear_release_id),
        "seasonRevision": _text(season_revision),
        "simcRuntimeRevision": _text(simc_runtime_revision),
        "builderRevision": _text(builder_revision),
        "pointerBefore": before,
        "pointerAfter": after,
        "metrics": normalized_metrics,
        "limits": normalized_limits,
        "prepared": {
            "communityReleaseStatus": _text(
                prepared.get("communityReleaseStatus")
            ),
            "communityContentHash": _text(
                prepared.get("communityContentHash")
            ),
            "stagingTemplateCount": _integer(
                prepared.get("stagingTemplateCount")
            ),
            "winnerSpecCount": _integer(prepared.get("winnerSpecCount")),
            "winnerHeroSlotCount": _integer(
                prepared.get("winnerHeroSlotCount")
            ),
        },
        "problemCodes": sorted(set(problems)),
    }
    return {
        **identity,
        "reportId": REPORT_PREFIX
        + hashlib.sha256(_canonical_bytes(identity)).hexdigest(),
    }


def validate_resource_report(
    report: Any,
    *,
    gear_release_id: str,
    simc_runtime_revision: str,
) -> bool:
    value = report if isinstance(report, Mapping) else {}
    if (
        value.get("schemaRevision") != SCHEMA_REVISION
        or value.get("status") not in {"pass", "blocked"}
        or _text(value.get("gearReleaseId")) != _text(gear_release_id)
        or _text(value.get("simcRuntimeRevision"))
        != _text(simc_runtime_revision)
    ):
        return False
    identity = {
        key: _canonical(item)
        for key, item in value.items()
        if key != "reportId"
    }
    expected = REPORT_PREFIX + hashlib.sha256(
        _canonical_bytes(identity)
    ).hexdigest()
    return _text(value.get("reportId")) == expected


def run_resource_probe(
    store: Any,
    *,
    gear_release_descriptor: Mapping[str, Any],
    gear_snapshot: Mapping[str, Any],
    dependency_revisions: Mapping[str, Any],
    expected_specs: Iterable[tuple[str, str]],
    simc_runtime_revision: str,
    now: str,
    level: int = 90,
    prepare_fn: Callable[..., Mapping[str, Any]] | None = None,
    builder_revision: str = BUILDER_REVISION,
    limits: Mapping[str, Any] | None = None,
    temporary_root: Path | None = None,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
    peak_rss_bytes: Callable[[], int] = current_peak_rss_bytes,
) -> dict[str, Any]:
    release_id = _text(gear_release_descriptor.get("releaseId"))
    season_revision = _text(gear_release_descriptor.get("seasonRevision"))
    if not release_id or _text(gear_release_descriptor.get("releaseKind")) != "gear":
        raise ResourceProbeError("resource probe requires an exact Gear Release")
    expected_simc = _text(dependency_revisions.get("simcRuntimeRevision"))
    if expected_simc and expected_simc != _text(simc_runtime_revision):
        raise ResourceProbeError(
            "resource probe SimC revision does not match Gear Release dependencies"
        )
    if prepare_fn is None:
        from .gear_release_tool import prepare_staging_community_release

        prepare_fn = prepare_staging_community_release

    normalized_limits = {
        **DEFAULT_LIMITS,
        **(dict(limits) if isinstance(limits, Mapping) else {}),
    }
    pointer_before = _pointer_identity(store.get_active_pointer())
    started = monotonic_ns()
    previous_tmpdir = os.environ.get("TMPDIR")
    previous_tempfile_directory = tempfile.tempdir
    result: Mapping[str, Any]
    try:
        with tempfile.TemporaryDirectory(
            prefix="wow-gear-resource-probe-",
            dir=str(temporary_root) if temporary_root is not None else None,
        ) as directory:
            os.environ["TMPDIR"] = directory
            tempfile.tempdir = directory
            try:
                result = prepare_fn(
                    store,
                    gear_release_descriptor=dict(gear_release_descriptor),
                    gear_snapshot=dict(gear_snapshot),
                    dependency_revisions=dict(dependency_revisions),
                    expected_specs=list(expected_specs),
                    now=_text(now),
                    level=_integer(level),
                    source_revision=builder_revision,
                )
            except Exception as exc:
                raise ResourceProbeError(
                    "resource probe Community prepare failed"
                ) from exc
            temporary_bytes = _directory_bytes(Path(directory))
    finally:
        if previous_tmpdir is None:
            os.environ.pop("TMPDIR", None)
        else:
            os.environ["TMPDIR"] = previous_tmpdir
        tempfile.tempdir = previous_tempfile_directory
    elapsed_ms = max(0, (monotonic_ns() - started) // 1_000_000)
    pointer_after = _pointer_identity(store.get_active_pointer())
    metrics = {
        "elapsedMilliseconds": elapsed_ms,
        "peakRssObservedBytes": _integer(peak_rss_bytes()),
        "temporaryBytesObserved": temporary_bytes,
        "writeStatementCount": _write_statement_count(store),
    }
    return build_resource_report(
        gear_release_id=release_id,
        season_revision=season_revision,
        simc_runtime_revision=simc_runtime_revision,
        builder_revision=builder_revision,
        pointer_before=pointer_before,
        pointer_after=pointer_after,
        metrics=metrics,
        limits=normalized_limits,
        prepared=_prepared_summary(result),
    )


__all__ = (
    "BUILDER_REVISION",
    "DEFAULT_LIMITS",
    "ReadOnlyConnectionFactory",
    "ResourceProbeError",
    "SCHEMA_REVISION",
    "build_resource_report",
    "current_peak_rss_bytes",
    "require_postgres_only_environment",
    "run_resource_probe",
    "validate_resource_report",
)

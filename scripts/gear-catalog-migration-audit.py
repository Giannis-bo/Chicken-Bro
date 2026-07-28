#!/usr/bin/env python3
"""Bounded, read-only Phase 0 gear catalog migration audit."""

from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sys
import uuid
from typing import Any, Callable, Iterable, Mapping


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from server.gear_catalog_audit_store import (  # noqa: E402
    GearCatalogAuditPointerChanged,
    GearCatalogAuditStore,
)
from server.gear_catalog_migration_audit import (  # noqa: E402
    audit_catalog_mapping,
    audit_resource_baseline,
    audit_spec_coverage,
    audit_template_exactness,
    build_phase0_report,
    validate_phase0_report,
)


MAX_CALLER_BYTES = 2 * 1024 * 1024
MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_STATEMENT_TIMEOUT_MS = 30_000
MAX_LOCK_TIMEOUT_MS = 5_000
MAX_BATCH_SIZE = 1_000
MAX_SAMPLE_LIMIT = 20
SPEC_READ_QUERY_LIMIT = 2_000
PROTECTED_OUTPUT_NAMES = frozenset({
    "evidence.json",
    "manifest.json",
    "requirement.json",
})
_STATUS_ORDER = {"verified": 0, "partial": 1, "blocked": 2}
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
_LEADING_SQL_COMMENT = re.compile(
    r"^\s*(?:(?:--[^\n]*(?:\n|$))|(?:/\*.*?\*/))\s*",
    re.DOTALL,
)
_REPORT_ID = re.compile(r"^gear-catalog-callers:sha256:[0-9a-f]{64}$")
_ACTIVE_TEMP_PATHS: set[Path] = set()


class AuditCliError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _bounded_integer(label: str, maximum: int) -> Callable[[str], int]:
    def parse(value: str) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise argparse.ArgumentTypeError(
                f"{label} must be an integer"
            ) from exc
        if not 1 <= parsed <= maximum:
            raise argparse.ArgumentTypeError(
                f"{label} must be between 1 and {maximum}"
            )
        return parsed

    return parse


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the bounded read-only Phase 0 gear catalog audit.",
    )
    parser.add_argument("--callers-json", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--statement-timeout-ms",
        type=_bounded_integer("statement_timeout_ms", MAX_STATEMENT_TIMEOUT_MS),
        default=15_000,
    )
    parser.add_argument(
        "--lock-timeout-ms",
        type=_bounded_integer("lock_timeout_ms", MAX_LOCK_TIMEOUT_MS),
        default=1_000,
    )
    parser.add_argument(
        "--batch-size",
        type=_bounded_integer("batch_size", MAX_BATCH_SIZE),
        default=500,
    )
    parser.add_argument(
        "--sample-limit",
        type=_bounded_integer("sample_limit", MAX_SAMPLE_LIMIT),
        default=MAX_SAMPLE_LIMIT,
    )
    parser.add_argument(
        "--filesystem-root",
        action="append",
        default=[],
        help="Repository-relative filesystem root to measure; defaults to the repository root.",
    )
    return parser.parse_args(argv)


def validate_environment(environ: Mapping[str, str]) -> str:
    runtime = str(environ.get("WOW_DATABASE_RUNTIME") or "").strip()
    if runtime != "postgres_only":
        raise AuditCliError(
            "AUDIT_REQUIRES_POSTGRES_ONLY",
            "gear catalog audit requires WOW_DATABASE_RUNTIME=postgres_only",
        )
    database_url = str(environ.get("WOW_DATABASE_URL") or "").strip()
    if not database_url:
        raise AuditCliError(
            "AUDIT_DATABASE_URL_MISSING",
            "gear catalog audit requires WOW_DATABASE_URL",
        )
    return database_url


def _repository_path(
    repo_root: Path,
    value: str | os.PathLike[str],
    *,
    output: bool = False,
) -> Path:
    root = Path(repo_root).resolve()
    raw = Path(value)
    candidate = (raw if raw.is_absolute() else root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise AuditCliError(
            "AUDIT_PATH_OUTSIDE_REPOSITORY",
            "audit paths must stay inside the current repository",
        ) from exc
    if output and candidate.name in PROTECTED_OUTPUT_NAMES:
        raise AuditCliError(
            "AUDIT_CONTROL_FILE_PROTECTED",
            f"audit output cannot replace {candidate.name}",
        )
    return candidate


def load_caller_report(
    repo_root: Path,
    value: str | os.PathLike[str],
) -> tuple[dict[str, Any], int]:
    path = _repository_path(repo_root, value)
    try:
        with path.open("rb") as handle:
            content = handle.read(MAX_CALLER_BYTES + 1)
    except OSError as exc:
        raise AuditCliError(
            "AUDIT_CALLER_JSON_UNAVAILABLE",
            "caller JSON is unavailable",
        ) from exc
    if len(content) > MAX_CALLER_BYTES:
        raise AuditCliError(
            "AUDIT_CALLER_JSON_TOO_LARGE",
            "caller JSON exceeds the 2 MiB limit",
        )
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditCliError(
            "AUDIT_CALLER_JSON_INVALID",
            "caller JSON is invalid",
        ) from exc
    if not isinstance(payload, dict):
        raise AuditCliError(
            "AUDIT_CALLER_JSON_INVALID",
            "caller JSON must be an object",
        )
    if (
        payload.get("schemaRevision") != "gear-catalog-callers-v1"
        or not _REPORT_ID.fullmatch(str(payload.get("reportId") or ""))
        or str(payload.get("status") or "") not in _STATUS_ORDER
    ):
        raise AuditCliError(
            "AUDIT_CALLER_CONTRACT_INVALID",
            "caller JSON does not satisfy gear-catalog-callers-v1",
        )
    return payload, len(content)


def _canonical_json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        + "\n"
    ).encode("utf-8")


def _contains_secret(content: bytes, secrets: Iterable[str]) -> bool:
    return any(
        secret and secret.encode("utf-8") in content
        for secret in secrets
    )


def atomic_write_json(
    output_path: str | os.PathLike[str],
    payload: Any,
    *,
    repo_root: Path,
    replace_fn: Callable[[str | os.PathLike[str], str | os.PathLike[str]], Any] = os.replace,
    secrets: Iterable[str] = (),
) -> None:
    output = _repository_path(repo_root, output_path, output=True)
    content = _canonical_json_bytes(payload)
    if len(content) > MAX_REPORT_BYTES:
        raise AuditCliError(
            "AUDIT_REPORT_TOO_LARGE",
            "audit result exceeds the 8 MiB limit",
        )
    if _contains_secret(content, secrets):
        raise AuditCliError(
            "AUDIT_SECRET_PRESENT",
            "audit result contains a protected runtime secret",
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / (
        f".{output.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    _ACTIVE_TEMP_PATHS.add(temporary)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if temporary.stat().st_size > MAX_REPORT_BYTES:
            raise AuditCliError(
                "AUDIT_REPORT_TOO_LARGE",
                "audit result exceeds the 8 MiB limit",
            )
        replace_fn(temporary, output)
        _ACTIVE_TEMP_PATHS.discard(temporary)
        try:
            directory_descriptor = os.open(output.parent, os.O_RDONLY)
        except OSError:
            directory_descriptor = -1
        if directory_descriptor >= 0:
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        _ACTIVE_TEMP_PATHS.discard(temporary)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _cleanup_on_signal(signum, _frame):
    for temporary in tuple(_ACTIVE_TEMP_PATHS):
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        finally:
            _ACTIVE_TEMP_PATHS.discard(temporary)
    raise SystemExit(128 + int(signum))


@contextlib.contextmanager
def _signal_cleanup_handlers():
    previous = {}
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.getsignal(signum)
            signal.signal(signum, _cleanup_on_signal)
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def _normalized_sql(sql: Any) -> str:
    normalized = str(sql or "")
    while True:
        stripped = _LEADING_SQL_COMMENT.sub("", normalized, count=1)
        if stripped == normalized:
            break
        normalized = stripped
    return " ".join(normalized.split())


class ReadOnlyQueryMetrics:
    def __init__(self, *, max_reads: int = SPEC_READ_QUERY_LIMIT):
        if not 1 <= int(max_reads) <= SPEC_READ_QUERY_LIMIT:
            raise ValueError(
                f"max_reads must be between 1 and {SPEC_READ_QUERY_LIMIT}"
            )
        self.max_reads = int(max_reads)
        self.reads = 0
        self.writes = 0
        self.transaction_control = 0

    def record(self, sql: Any) -> None:
        normalized = _normalized_sql(sql)
        if _WRITE_STATEMENT.search(normalized):
            self.writes += 1
            raise RuntimeError(
                "gear catalog specialization audit attempted a write statement"
            )
        if normalized.upper().startswith((
            "BEGIN",
            "COMMIT",
            "ROLLBACK",
            "SET ",
        )):
            self.transaction_control += 1
            return
        self.reads += 1
        if self.reads > self.max_reads:
            raise RuntimeError(
                "gear catalog specialization audit exceeded its read query budget"
            )

    def snapshot(self) -> dict[str, int]:
        return {
            "reads": self.reads,
            "writes": self.writes,
            "transactionControl": self.transaction_control,
            "maxReads": self.max_reads,
        }


class _ReadOnlyCursor:
    def __init__(self, cursor, metrics: ReadOnlyQueryMetrics):
        self._cursor = cursor
        self._metrics = metrics

    def __enter__(self):
        enter = getattr(self._cursor, "__enter__", None)
        if callable(enter):
            enter()
        return self

    def __exit__(self, exc_type, exc, traceback):
        exit_method = getattr(self._cursor, "__exit__", None)
        if callable(exit_method):
            return exit_method(exc_type, exc, traceback)
        close = getattr(self._cursor, "close", None)
        if callable(close):
            close()
        return False

    def execute(self, sql, params=None):
        self._metrics.record(sql)
        if params is None:
            return self._cursor.execute(sql)
        return self._cursor.execute(sql, params)

    def executemany(self, sql, params):
        self._metrics.record(sql)
        return self._cursor.executemany(sql, params)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class _ReadOnlyConnection:
    def __init__(self, connection, metrics: ReadOnlyQueryMetrics):
        self._connection = connection
        self._metrics = metrics

    def cursor(self, *args, **kwargs):
        return _ReadOnlyCursor(
            self._connection.cursor(*args, **kwargs),
            self._metrics,
        )

    def __getattr__(self, name):
        return getattr(self._connection, name)


def _set_connection_read_only(connection) -> None:
    try:
        connection.read_only = True
        return
    except (AttributeError, TypeError):
        pass
    cursor = connection.cursor()
    try:
        cursor.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
    finally:
        close = getattr(cursor, "close", None)
        if callable(close):
            close()
    commit = getattr(connection, "commit", None)
    if callable(commit):
        commit()


def read_only_connection_factory(
    connection_factory: Callable[[], Any],
    metrics: ReadOnlyQueryMetrics,
) -> Callable[[], _ReadOnlyConnection]:
    def create():
        connection = connection_factory()
        try:
            _set_connection_read_only(connection)
        except Exception:
            close = getattr(connection, "close", None)
            if callable(close):
                close()
            raise
        return _ReadOnlyConnection(connection, metrics)

    return create


def _text(value: Any) -> str:
    return str(value or "").strip()


def _integer(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _pointer_identity(payload: Mapping[str, Any]) -> tuple[str, int]:
    active_binding = _mapping(payload.get("_activeManifestBinding"))
    manifest = _mapping(active_binding.get("manifest"))
    return (
        _text(payload.get("manifestRevision") or manifest.get("manifestRevision")),
        _integer(payload.get("pointerGeneration") or active_binding.get("generation")),
    )


def _candidate_count(payload: Mapping[str, Any]) -> int:
    count = 0
    groups = payload.get("replacementCandidates")
    if isinstance(groups, list):
        for group in groups:
            items = _mapping(group).get("items")
            if isinstance(items, list):
                count += len([item for item in items if isinstance(item, Mapping)])
    if count:
        return count
    items = payload.get("catalogItems")
    return len([item for item in items or [] if isinstance(item, Mapping)])


def _blocker_code(value: Any) -> str:
    if isinstance(value, Mapping):
        candidate = _text(value.get("code"))
        if re.fullmatch(r"[A-Z][A-Z0-9_]{2,95}", candidate):
            return candidate
        value = value.get("message") or candidate
    candidate = _text(value)
    if re.fullmatch(r"[A-Z][A-Z0-9_]{2,95}", candidate):
        return candidate
    if not candidate:
        return ""
    digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:16].upper()
    return f"BACKEND_BLOCKER_SHA256_{digest}"


def _backend_status(payload: Mapping[str, Any]) -> str:
    statuses = [
        _text(payload.get("catalogStatus")),
        _text(payload.get("dataStatus")),
        _text(_mapping(payload.get("readiness")).get("status")),
    ]
    recognized = [value for value in statuses if value in _STATUS_ORDER]
    return (
        max(recognized, key=lambda value: _STATUS_ORDER[value])
        if recognized
        else "blocked"
    )


def _spec_pairs(class_spec_matrix: Any) -> list[tuple[str, str]]:
    pairs = []
    for klass in class_spec_matrix or []:
        class_key = _text(_mapping(klass).get("key"))
        for spec_key in _mapping(klass).get("specs") or []:
            pair = (class_key, _text(spec_key))
            if not all(pair):
                raise AuditCliError(
                    "AUDIT_SPEC_MATRIX_INVALID",
                    "backend specialization matrix contains an empty identity",
                )
            pairs.append(pair)
    if len(pairs) != 40 or len(set(pairs)) != 40:
        raise AuditCliError(
            "AUDIT_SPEC_MATRIX_INVALID",
            "backend specialization matrix must contain exactly 40 unique pairs",
        )
    return pairs


def _spec_rows(
    *,
    class_spec_matrix: Any,
    spec_payload_reader: Callable[[str, str], Any],
    pointer: Mapping[str, Any],
) -> list[dict[str, Any]]:
    expected_manifest = _text(pointer.get("manifestRevision"))
    expected_generation = _integer(pointer.get("generation"))
    rows = []
    for class_key, spec_key in _spec_pairs(class_spec_matrix):
        payload = _mapping(spec_payload_reader(class_key, spec_key))
        manifest_revision, generation = _pointer_identity(payload)
        blockers = [
            _blocker_code(value)
            for value in (
                list(payload.get("catalogBlockers") or [])
                + list(payload.get("errors") or [])
            )
        ]
        blockers = sorted({value for value in blockers if value})
        if manifest_revision and manifest_revision != expected_manifest:
            raise GearCatalogAuditPointerChanged(
                "AUDIT_POINTER_CHANGED: specialization reader observed another Manifest"
            )
        if generation and generation != expected_generation:
            raise GearCatalogAuditPointerChanged(
                "AUDIT_POINTER_CHANGED: specialization reader observed another generation"
            )
        if not manifest_revision or not generation:
            blockers.append("AUDIT_SPEC_POINTER_IDENTITY_MISSING")

        candidate_count = _candidate_count(payload)
        backend_status = _backend_status(payload)
        if (
            backend_status == "verified"
            and candidate_count > 0
            and not blockers
        ):
            status = "verified"
        elif candidate_count > 0 and backend_status != "blocked":
            status = "partial"
        else:
            status = "blocked"
        rows.append({
            "classKey": class_key,
            "specKey": spec_key,
            "status": status,
            "candidateCount": candidate_count,
            "blockerCodes": sorted(set(blockers)),
        })
    return rows


def _caller_summary(caller_report: Mapping[str, Any]) -> dict[str, Any]:
    categories = _mapping(caller_report.get("categories"))
    return {
        "schemaRevision": _text(caller_report.get("schemaRevision")),
        "reportId": _text(caller_report.get("reportId")),
        "status": _text(caller_report.get("status")),
        "runtimeCallerCount": _integer(
            caller_report.get("runtimeCallerCount")
        ),
        "unresolvedCount": _integer(caller_report.get("unresolvedCount")),
        "categoryCounts": {
            key: len(value) if isinstance(value, list) else 0
            for key, value in sorted(categories.items())
        },
    }


def _resource_rows(
    snapshot: Mapping[str, Any],
    *,
    caller_bytes: int,
    filesystem_roots: Iterable[Path],
    statvfs_fn: Callable[[str | os.PathLike[str]], Any],
) -> dict[str, Any]:
    relation_sizes = [
        row
        for row in snapshot.get("relationSizes") or []
        if isinstance(row, Mapping)
    ]
    database_bytes = sum(
        max(0, _integer(row.get("totalBytes")))
        for row in relation_sizes
    )
    active_bytes = sum(
        max(0, _integer(row.get("activeLogicalBytes")))
        for row in relation_sizes
    )
    rollback_bytes = sum(
        max(0, _integer(row.get("rollbackLogicalBytes")))
        for row in relation_sizes
    )

    filesystem_total = 0
    filesystem_free = 0
    filesystem_measured = False
    for root in filesystem_roots:
        try:
            facts = statvfs_fn(root)
        except OSError:
            continue
        fragment_size = _integer(getattr(facts, "f_frsize", 0))
        filesystem_total += max(0, _integer(facts.f_blocks)) * fragment_size
        filesystem_free += max(0, _integer(facts.f_bavail)) * fragment_size
        filesystem_measured = True
    filesystem_used = (
        max(0, filesystem_total - filesystem_free)
        if filesystem_measured
        else None
    )
    used_percent = (
        round((filesystem_used / filesystem_total) * 100, 4)
        if filesystem_measured and filesystem_total > 0
        else (0.0 if filesystem_measured else None)
    )
    return {
        "databaseRelationsBytes": database_bytes,
        "activeMaterializationBytes": active_bytes,
        "rollbackMaterializationBytes": rollback_bytes,
        "diagnosticBytesObserved": max(0, int(caller_bytes)),
        "filesystemTotalBytes": filesystem_total if filesystem_measured else None,
        "filesystemUsedBytes": filesystem_used,
        "filesystemFreeBytes": filesystem_free if filesystem_measured else None,
        "filesystemUsedPercent": used_percent,
        "peakRssObservedBytes": None,
        "temporaryBytesObserved": None,
    }


def _cap_template_samples(
    template_audit: dict[str, Any],
    sample_limit: int,
) -> dict[str, Any]:
    for category in ("community", "personal"):
        section = template_audit.get(category)
        if isinstance(section, dict):
            section["sampleHashes"] = list(
                section.get("sampleHashes") or []
            )[:sample_limit]
    return template_audit


def run_audit(
    *,
    caller_report: Mapping[str, Any],
    caller_bytes: int,
    database_url: str = "",
    statement_timeout_ms: int = 15_000,
    lock_timeout_ms: int = 1_000,
    batch_size: int = 500,
    sample_limit: int = MAX_SAMPLE_LIMIT,
    snapshot_reader: Callable[..., Mapping[str, Any]] | None = None,
    spec_payload_reader: Callable[[str, str], Mapping[str, Any]] | None = None,
    class_spec_matrix: Any = None,
    filesystem_roots: Iterable[Path] | None = None,
    statvfs_fn: Callable[[str | os.PathLike[str]], Any] = os.statvfs,
    observed_at: str | None = None,
    connection_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    if not 1 <= int(statement_timeout_ms) <= MAX_STATEMENT_TIMEOUT_MS:
        raise AuditCliError(
            "AUDIT_LIMIT_INVALID",
            "statement_timeout_ms is outside its fixed bound",
        )
    if not 1 <= int(lock_timeout_ms) <= MAX_LOCK_TIMEOUT_MS:
        raise AuditCliError(
            "AUDIT_LIMIT_INVALID",
            "lock_timeout_ms is outside its fixed bound",
        )
    if not 1 <= int(batch_size) <= MAX_BATCH_SIZE:
        raise AuditCliError(
            "AUDIT_LIMIT_INVALID",
            "batch_size is outside its fixed bound",
        )
    if not 1 <= int(sample_limit) <= MAX_SAMPLE_LIMIT:
        raise AuditCliError(
            "AUDIT_LIMIT_INVALID",
            "sample_limit is outside its fixed bound",
        )

    raw_connection_factory = connection_factory
    if snapshot_reader is None or spec_payload_reader is None:
        if raw_connection_factory is None:
            if not database_url:
                raise AuditCliError(
                    "AUDIT_DATABASE_URL_MISSING",
                    "gear catalog audit requires WOW_DATABASE_URL",
                )
            from server.db import connect_postgres

            raw_connection_factory = lambda: connect_postgres(database_url)

    if snapshot_reader is None:
        audit_store = GearCatalogAuditStore(raw_connection_factory)
        snapshot_reader = audit_store.snapshot
    snapshot = _mapping(snapshot_reader(
        statement_timeout_ms=statement_timeout_ms,
        lock_timeout_ms=lock_timeout_ms,
        batch_size=batch_size,
    ))
    pointer_before = _mapping(snapshot.get("pointerBefore"))
    pointer_after = _mapping(snapshot.get("pointerAfter"))
    if pointer_before != pointer_after:
        raise GearCatalogAuditPointerChanged(
            "AUDIT_POINTER_CHANGED: snapshot pointer identities differ"
        )

    query_metrics = ReadOnlyQueryMetrics(max_reads=SPEC_READ_QUERY_LIMIT)
    if spec_payload_reader is None:
        from server.postgres_cache_store import PostgresCacheStore

        cache_store = PostgresCacheStore(
            read_only_connection_factory(
                raw_connection_factory,
                query_metrics,
            )
        )
        spec_payload_reader = lambda class_key, spec_key: cache_store.get_websim_gear(
            class_key=class_key,
            spec_key=spec_key,
            compact=True,
            mode="initial",
        )
    if class_spec_matrix is None:
        from server.websim_payload import WOW_CLASSES

        class_spec_matrix = WOW_CLASSES

    spec_rows = _spec_rows(
        class_spec_matrix=class_spec_matrix,
        spec_payload_reader=spec_payload_reader,
        pointer=pointer_before,
    )
    active_binding = _mapping(snapshot.get("activeBinding"))
    manifest = _mapping(active_binding.get("manifest"))
    gear_release = _mapping(active_binding.get("gearRelease"))
    catalog = audit_catalog_mapping(
        {
            "manifestRevision": manifest.get("manifestRevision"),
            "gearReleaseId": gear_release.get("releaseId"),
        },
        snapshot.get("catalogRows"),
    )
    catalog["sourceQueryMetrics"] = dict(
        _mapping(snapshot.get("queryMetrics"))
    )
    templates = _cap_template_samples(
        audit_template_exactness(
            snapshot.get("communityTemplates"),
            snapshot.get("personalGearTemplates"),
        ),
        int(sample_limit),
    )
    coverage = audit_spec_coverage(spec_rows)
    coverage["queryMetrics"] = query_metrics.snapshot()
    resources = audit_resource_baseline(_resource_rows(
        snapshot,
        caller_bytes=caller_bytes,
        filesystem_roots=list(filesystem_roots or [REPOSITORY_ROOT]),
        statvfs_fn=statvfs_fn,
    ))
    report = build_phase0_report(
        catalog=catalog,
        templates=templates,
        coverage=coverage,
        resources=resources,
        callers=_caller_summary(caller_report),
        observed_at=observed_at or datetime.now(timezone.utc).isoformat(),
    )
    issues = validate_phase0_report(report)
    if issues:
        raise AuditCliError(
            "AUDIT_REPORT_INVALID",
            "generated Phase 0 report failed validation",
        )
    return report


def _safe_error(exc: BaseException) -> str:
    if isinstance(exc, AuditCliError):
        return f"{exc.code}: {exc}"
    if isinstance(exc, GearCatalogAuditPointerChanged):
        return "AUDIT_POINTER_CHANGED"
    return f"AUDIT_EXECUTION_FAILED: {type(exc).__name__}"


def main(
    argv: list[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    repo_root: Path = REPOSITORY_ROOT,
    run_audit_fn: Callable[..., dict[str, Any]] = run_audit,
) -> int:
    args = parse_args(argv)
    environment = os.environ if environ is None else environ
    try:
        database_url = validate_environment(environment)
        root = Path(repo_root).resolve()
        output = _repository_path(root, args.output, output=True)
        callers, caller_bytes = load_caller_report(root, args.callers_json)
        filesystem_roots = [
            _repository_path(root, value)
            for value in (args.filesystem_root or ["."])
        ]
        report = run_audit_fn(
            caller_report=callers,
            caller_bytes=caller_bytes,
            database_url=database_url,
            statement_timeout_ms=args.statement_timeout_ms,
            lock_timeout_ms=args.lock_timeout_ms,
            batch_size=args.batch_size,
            sample_limit=args.sample_limit,
            filesystem_roots=filesystem_roots,
        )
        issues = validate_phase0_report(report)
        if issues:
            raise AuditCliError(
                "AUDIT_REPORT_INVALID",
                "generated Phase 0 report failed validation",
            )
        with _signal_cleanup_handlers():
            atomic_write_json(
                output,
                report,
                repo_root=root,
                secrets=(database_url,),
            )
        print(json.dumps(
            {
                "status": report.get("status"),
                "reportId": report.get("reportId"),
                "output": output.relative_to(root).as_posix(),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ))
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        print(_safe_error(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

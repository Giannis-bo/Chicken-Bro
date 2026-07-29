#!/usr/bin/env python3
"""Build, seal and shadow-check one dormant exact gear registry."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time
from typing import Any, Callable, Mapping


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from server.gear_catalog_audit_store import GearCatalogAuditStore  # noqa: E402
from server.gear_catalog_revision import build_catalog_revision  # noqa: E402
from server.gear_catalog_revision_store import GearCatalogRevisionStore  # noqa: E402
from server.gear_exact_item_registry import (  # noqa: E402
    EXACT_REGISTRY_EVIDENCE_GAP_CODES,
    build_exact_item_registry,
)
from server.gear_exact_item_registry_store import (  # noqa: E402
    GearExactItemRegistryStore,
)


MAX_STATEMENT_TIMEOUT_MS = 30_000
MAX_LOCK_TIMEOUT_MS = 5_000
MAX_BATCH_SIZE = 1_000
MAX_CANDIDATE_BYTES = 2_000_000_000
MAX_CANDIDATE_SECONDS = 300.0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _hash(prefix: str, value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return prefix + hashlib.sha256(encoded).hexdigest()


def _streaming_hash(prefix: str, value: Any) -> str:
    digest = hashlib.sha256()
    encoder = json.JSONEncoder(
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    for chunk in encoder.iterencode(value):
        digest.update(chunk.encode("utf-8"))
    return prefix + digest.hexdigest()


def _binding(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    active = _mapping(snapshot.get("activeBinding"))
    manifest = _mapping(active.get("manifest"))
    gear = _mapping(active.get("gearRelease"))
    dependency = _mapping(gear.get("dependencyVector"))
    if not dependency:
        dependency = _mapping(manifest.get("dependencyVector"))
    return {
        "manifestRevision": _text(manifest.get("manifestRevision")),
        "seasonRevision": _text(manifest.get("seasonRevision")),
        "gearReleaseId": _text(gear.get("releaseId")),
        "gearReleaseContentHash": _text(gear.get("contentHash")),
        "gearReleaseSchemaRevision": _text(gear.get("schemaRevision")),
        "gearRuleRevision": _text(
            dependency.get("gearRuleRevision")
            or _mapping(manifest.get("dependencyVector")).get(
                "gearRuleRevision"
            )
        ),
        "dependencyVector": dependency,
        "sourceSummary": {
            "releaseStatus": _text(gear.get("releaseStatus")),
            "source": _mapping(gear.get("source")),
            "contentSummary": _mapping(gear.get("contentSummary")),
        },
    }


def _peak_rss_bytes() -> int:
    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss or 0)
    return peak if sys.platform == "darwin" else peak * 1024


def _blocked_report(
    *,
    problem_codes: list[str],
    pointer_before: Mapping[str, Any],
    pointer_after: Mapping[str, Any],
    deterministic: bool,
    observed_at: str,
    registry: Mapping[str, Any] | None = None,
    catalog_revision: str = "",
    elapsed_seconds: float = 0.0,
    peak_bytes: int = 0,
) -> dict[str, Any]:
    registry_row = _mapping(registry)
    report = {
        "schemaRevision": "gear-exact-shadow-report-v1",
        "status": "blocked",
        "catalogRevision": catalog_revision,
        "registryRevision": _text(registry_row.get("registryRevision")),
        "registryStatus": _text(registry_row.get("status")),
        "deterministicBuild": deterministic,
        "pointerStable": dict(pointer_before) == dict(pointer_after),
        "pointerBefore": dict(pointer_before),
        "pointerAfter": dict(pointer_after),
        "summary": _mapping(registry_row.get("summary")),
        "resource": {
            "peakBytes": peak_bytes,
            "elapsedSeconds": elapsed_seconds,
            "maxBytes": MAX_CANDIDATE_BYTES,
            "maxSeconds": MAX_CANDIDATE_SECONDS,
        },
        "problemCodes": sorted(set(problem_codes)),
        "evidenceGapCodes": sorted(
            set(registry_row.get("problemCodes") or [])
            & EXACT_REGISTRY_EVIDENCE_GAP_CODES
        ),
        "observedAt": observed_at,
    }
    report["reportId"] = _hash(
        "gear-exact-shadow:sha256:",
        {
            key: value
            for key, value in report.items()
            if key not in {"observedAt", "reportId", "resource"}
        },
    )
    return report


def run_migration(
    *,
    snapshot_reader: Callable[..., Mapping[str, Any]],
    pointer_reader: Callable[..., Mapping[str, Any]],
    catalog_reader: Callable[[str], Mapping[str, Any]],
    seal_writer: Callable[[dict[str, Any]], Mapping[str, Any]],
    statement_timeout_ms: int = 15_000,
    lock_timeout_ms: int = 1_000,
    batch_size: int = 500,
    observed_at: str = "",
    elapsed_seconds_reader: Callable[[], float] | None = None,
    peak_bytes_reader: Callable[[], int] | None = None,
) -> dict[str, Any]:
    """Run one bounded active-template to dormant-exact migration shadow."""

    started = time.monotonic()
    snapshot = _mapping(snapshot_reader(
        statement_timeout_ms=statement_timeout_ms,
        lock_timeout_ms=lock_timeout_ms,
        batch_size=batch_size,
    ))
    pointer_before = _mapping(snapshot.get("pointerBefore"))
    snapshot_after = _mapping(snapshot.get("pointerAfter"))
    if pointer_before != snapshot_after:
        raise RuntimeError("EXACT_SHADOW_SNAPSHOT_POINTER_CHANGED")
    binding = _binding(snapshot)
    catalog_rows = _mapping(snapshot.get("catalogRows"))
    catalog = build_catalog_revision(binding, catalog_rows)
    catalog_revision = _text(catalog.get("catalogRevision"))
    catalog_status = _text(catalog.get("status"))
    del catalog
    persisted_catalog = _mapping(catalog_reader(catalog_revision))
    persisted_catalog_revision = _text(
        persisted_catalog.get("catalogRevision")
    )
    del persisted_catalog
    if (
        catalog_status != "verified"
        or persisted_catalog_revision != catalog_revision
    ):
        return _blocked_report(
            problem_codes=["EXACT_SHADOW_CATALOG_UNAVAILABLE"],
            pointer_before=pointer_before,
            pointer_after=snapshot_after,
            deterministic=False,
            observed_at=observed_at,
            catalog_revision=catalog_revision,
        )

    exact_rows = [
        row
        for row in catalog_rows.get("variants") or []
        if (
            isinstance(row, Mapping)
            and _text(row.get("rowFamily")) == "exact_instance"
        )
    ]
    build_args = {
        "catalog_revision": catalog_revision,
        "exact_rows": exact_rows,
        "community_templates": snapshot.get("communityTemplates") or [],
        "personal_templates": snapshot.get("personalGearTemplates") or [],
    }
    first = build_exact_item_registry(binding, **build_args)
    first_problem_codes = set(first.get("problemCodes") or [])
    first_content_hash = _streaming_hash("sha256:", first)
    del first
    registry = build_exact_item_registry(binding, **build_args)
    deterministic = first_content_hash == _streaming_hash(
        "sha256:",
        registry,
    )
    elapsed = (
        float(elapsed_seconds_reader())
        if elapsed_seconds_reader
        else time.monotonic() - started
    )
    peak_bytes = (
        int(peak_bytes_reader())
        if peak_bytes_reader
        else _peak_rss_bytes()
    )
    registry_problem_codes = first_problem_codes | set(
        registry.get("problemCodes") or []
    )
    evidence_gap_codes = (
        registry_problem_codes & EXACT_REGISTRY_EVIDENCE_GAP_CODES
    )
    preseal_codes = (
        registry_problem_codes - EXACT_REGISTRY_EVIDENCE_GAP_CODES
    )
    if not deterministic:
        preseal_codes.add("EXACT_SHADOW_BUILD_NONDETERMINISTIC")
    if elapsed > MAX_CANDIDATE_SECONDS:
        preseal_codes.add("EXACT_SHADOW_RESOURCE_SECONDS_EXCEEDED")
    if peak_bytes > MAX_CANDIDATE_BYTES:
        preseal_codes.add("EXACT_SHADOW_RESOURCE_BYTES_EXCEEDED")
    summary = _mapping(registry.get("summary"))
    if (
        summary.get("templateCount")
        != summary.get("classifiedTemplateCount")
        or summary.get("templateItemCount")
        != summary.get("classifiedTemplateItemCount")
        or summary.get("templateItemCount")
        != (
            int(summary.get("verifiedTemplateItemCount") or 0)
            + int(summary.get("partialTemplateItemCount") or 0)
            + int(summary.get("blockedTemplateItemCount") or 0)
        )
    ):
        preseal_codes.add("EXACT_SHADOW_TEMPLATE_SILENT_DROP")
    registry_status = _text(registry.get("status"))
    if (
        registry_status not in {"verified", "partial"}
        or (registry_status == "verified" and registry_problem_codes)
        or (
            registry_status == "partial"
            and (
                not evidence_gap_codes
                or registry_problem_codes != evidence_gap_codes
            )
        )
    ):
        preseal_codes.add("EXACT_SHADOW_REGISTRY_STATUS_INVALID")
    if preseal_codes:
        return _blocked_report(
            problem_codes=sorted(preseal_codes),
            pointer_before=pointer_before,
            pointer_after=snapshot_after,
            deterministic=deterministic,
            observed_at=observed_at,
            registry=registry,
            catalog_revision=catalog_revision,
            elapsed_seconds=elapsed,
            peak_bytes=peak_bytes,
        )

    registry_revision = _text(registry.get("registryRevision"))
    # Transfer the only full-registry reference to the store so it can release
    # the input before loading the sealed copy back from PostgreSQL.
    registry_owner = [registry]
    del registry
    sealed = _mapping(seal_writer(registry_owner.pop()))
    elapsed = (
        float(elapsed_seconds_reader())
        if elapsed_seconds_reader
        else time.monotonic() - started
    )
    peak_bytes = (
        int(peak_bytes_reader())
        if peak_bytes_reader
        else _peak_rss_bytes()
    )
    pointer_after = _mapping(pointer_reader(
        statement_timeout_ms=min(statement_timeout_ms, 5_000),
        lock_timeout_ms=lock_timeout_ms,
    ))
    problem_codes: set[str] = set()
    if _text(sealed.get("registryRevision")) != _text(
        registry_revision
    ):
        problem_codes.add("EXACT_SHADOW_SEAL_IDENTITY_MISMATCH")
    if (
        _text(sealed.get("status")) != registry_status
        or set(sealed.get("problemCodes") or []) != registry_problem_codes
    ):
        problem_codes.add("EXACT_SHADOW_SEAL_STATUS_MISMATCH")
    if pointer_before != pointer_after:
        problem_codes.add("EXACT_SHADOW_POINTER_CHANGED")
    if elapsed > MAX_CANDIDATE_SECONDS:
        problem_codes.add("EXACT_SHADOW_RESOURCE_SECONDS_EXCEEDED")
    if peak_bytes > MAX_CANDIDATE_BYTES:
        problem_codes.add("EXACT_SHADOW_RESOURCE_BYTES_EXCEEDED")
    report = {
        "schemaRevision": "gear-exact-shadow-report-v1",
        "status": "blocked" if problem_codes else "verified",
        "catalogRevision": catalog_revision,
        "registryRevision": registry_revision,
        "registryStatus": registry_status,
        "sourceGearReleaseId": _text(binding.get("gearReleaseId")),
        "sourceGearReleaseContentHash": _text(
            binding.get("gearReleaseContentHash")
        ),
        "deterministicBuild": deterministic,
        "pointerStable": pointer_before == pointer_after,
        "pointerBefore": pointer_before,
        "pointerAfter": pointer_after,
        "summary": summary,
        "resource": {
            "peakBytes": peak_bytes,
            "elapsedSeconds": elapsed,
            "maxBytes": MAX_CANDIDATE_BYTES,
            "maxSeconds": MAX_CANDIDATE_SECONDS,
        },
        "problemCodes": sorted(problem_codes),
        "evidenceGapCodes": sorted(evidence_gap_codes),
        "observedAt": observed_at,
    }
    report["reportId"] = _hash(
        "gear-exact-shadow:sha256:",
        {
            key: value
            for key, value in report.items()
            if key not in {"observedAt", "reportId", "resource"}
        },
    )
    return report


def _bounded_integer(label: str, maximum: int):
    def parse(value: str) -> int:
        parsed = int(value)
        if not 1 <= parsed <= maximum:
            raise argparse.ArgumentTypeError(
                f"{label} must be between 1 and {maximum}"
            )
        return parsed

    return parse


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and seal one dormant exact gear registry.",
    )
    parser.add_argument("--output", default="-")
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if _text(os.environ.get("WOW_DATABASE_RUNTIME")) != "postgres_only":
        print("EXACT_REGISTRY_REQUIRES_POSTGRES_ONLY", file=sys.stderr)
        return 2
    database_url = _text(os.environ.get("WOW_DATABASE_URL"))
    if not database_url:
        print("EXACT_REGISTRY_DATABASE_URL_MISSING", file=sys.stderr)
        return 2

    from server.db import connect_postgres

    connection_factory = lambda: connect_postgres(database_url)
    audit_store = GearCatalogAuditStore(connection_factory)
    catalog_store = GearCatalogRevisionStore(connection_factory)
    registry_store = GearExactItemRegistryStore(connection_factory)
    try:
        report = run_migration(
            snapshot_reader=audit_store.snapshot,
            pointer_reader=audit_store.pointer_identity,
            catalog_reader=catalog_store.load_catalog,
            seal_writer=registry_store.seal_registry,
            statement_timeout_ms=args.statement_timeout_ms,
            lock_timeout_ms=args.lock_timeout_ms,
            batch_size=args.batch_size,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:
        print(
            f"EXACT_SHADOW_EXECUTION_FAILED:{type(exc).__name__}",
            file=sys.stderr,
        )
        return 1
    content = json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    if args.output == "-":
        sys.stdout.write(content)
    else:
        Path(args.output).write_text(content, encoding="utf-8")
    return 0 if report.get("status") == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())

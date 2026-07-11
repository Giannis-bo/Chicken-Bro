#!/usr/bin/env python3
"""Single-child fenced worker for canonical Gear stat snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
import os
import re
import signal
import socket
import threading
import uuid
from typing import Any, Callable

try:
    from .db import connect_postgres, database_config_from_env
    from .gear_stat_snapshot import verified_snapshot_record
    from .gear_stat_snapshot_api import prepare_stat_snapshot_request
    from .gear_stat_snapshot_store import GearStatSnapshotIntegrityError, GearStatSnapshotStore
    from .postgres_cache_store import PostgresCacheStore
    from .simulator_payload import simc_version_status
    from .websim_payload import (
        GEAR_SCHEMA_REVISION,
        parse_simcraft_json_stat_snapshot,
        run_websim_stat_simcraft,
    )
except ImportError:
    from db import connect_postgres, database_config_from_env
    from gear_stat_snapshot import verified_snapshot_record
    from gear_stat_snapshot_api import prepare_stat_snapshot_request
    from gear_stat_snapshot_store import GearStatSnapshotIntegrityError, GearStatSnapshotStore
    from postgres_cache_store import PostgresCacheStore
    from simulator_payload import simc_version_status
    from websim_payload import GEAR_SCHEMA_REVISION, parse_simcraft_json_stat_snapshot, run_websim_stat_simcraft


WORKER_REVISION = "gear-stat-snapshot-worker-v1"


class LeaseLost(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _problem(code: str) -> dict[str, Any]:
    return {"code": code}


def _fail(
    store: Any,
    job: dict[str, Any],
    *,
    code: str,
    deterministic: bool,
    now: str,
) -> dict[str, Any]:
    store.fail_job(
        job_id=int(job.get("jobId") or 0),
        lock_token=_text(job.get("lockToken")),
        problem=_problem(code),
        now=now,
        deterministic=deterministic,
        cooldown_seconds=60,
    )
    return {"status": "blocked" if deterministic else "failed", "code": code}


def run_simc_with_heartbeat(
    run: Callable[[str], dict[str, Any]],
    profile: str,
    heartbeat: Callable[[], bool],
    *,
    interval_seconds: float = 5.0,
) -> dict[str, Any]:
    """Keep a separate-connection lease alive while exactly one SimC child runs."""

    if heartbeat() is not True:
        raise LeaseLost()
    stopped = threading.Event()
    lost = threading.Event()

    def maintain() -> None:
        while not stopped.wait(max(0.25, interval_seconds)):
            try:
                if heartbeat() is not True:
                    lost.set()
                    return
            except Exception:
                lost.set()
                return

    thread = threading.Thread(target=maintain, name="gear-stat-lease-heartbeat", daemon=True)
    thread.start()
    try:
        result = run(profile)
    finally:
        stopped.set()
        thread.join(timeout=max(1.0, interval_seconds + 1.0))
    if lost.is_set() or heartbeat() is not True:
        raise LeaseLost()
    return result


def process_claimed_job(
    job: dict[str, Any],
    *,
    authority_store: Any,
    snapshot_store: Any,
    simc_runtime_revision: str,
    worker_id: str,
    now_fn: Callable[[], str] = utc_now,
    prepare: Callable[..., tuple[int, dict[str, Any], dict[str, Any]]] = prepare_stat_snapshot_request,
    runner: Callable[[str], dict[str, Any]] = run_websim_stat_simcraft,
    run_with_heartbeat: Callable[..., dict[str, Any]] = run_simc_with_heartbeat,
) -> dict[str, Any]:
    """Re-resolve one claimed job, verify identity, then run and publish one child."""

    now = now_fn()
    _status, resolved, prepared = prepare(
        job.get("request") or {},
        authority_store=authority_store,
        simc_runtime_revision=simc_runtime_revision,
        request_id=f"gear-stat-worker-{int(job.get('jobId') or 0)}",
    )
    if not prepared:
        code = "GEAR_STAT_RE_RESOLVE_BLOCKED"
        problems = resolved.get("problems") if isinstance(resolved, dict) else []
        if isinstance(problems, list) and problems and isinstance(problems[0], dict):
            code = _text(problems[0].get("code")) or code
        return _fail(snapshot_store, job, code=code, deterministic=True, now=now)
    if (
        _text(prepared.get("signature", {}).get("statSignature")) != _text(job.get("statSignature"))
        or prepared.get("releaseContext") != job.get("releaseContext")
    ):
        return _fail(
            snapshot_store,
            job,
            code="GEAR_STAT_SIGNATURE_DRIFT",
            deterministic=True,
            now=now,
        )

    def heartbeat() -> bool:
        heartbeat_at = now_fn()
        alive = snapshot_store.heartbeat(
            job_id=int(job.get("jobId") or 0),
            lock_token=_text(job.get("lockToken")),
            now=heartbeat_at,
            lease_seconds=30,
        )
        if alive:
            snapshot_store.update_worker_state(
                worker_id=worker_id,
                status="running",
                worker_revision=WORKER_REVISION,
                simc_runtime_revision=simc_runtime_revision,
                now=heartbeat_at,
                current_job_id=int(job.get("jobId") or 0),
            )
        return bool(alive)

    try:
        simc_result = run_with_heartbeat(runner, prepared["profile"], heartbeat)
    except LeaseLost:
        return {"status": "abandoned", "code": "GEAR_STAT_LEASE_LOST"}
    except Exception:
        return _fail(
            snapshot_store,
            job,
            code="GEAR_STAT_SIMC_FAILED",
            deterministic=False,
            now=now_fn(),
        )
    if not isinstance(simc_result, dict) or simc_result.get("ran") is not True:
        return _fail(
            snapshot_store,
            job,
            code="GEAR_STAT_SIMC_FAILED",
            deterministic=False,
            now=now_fn(),
        )
    if simc_result.get("itemResolutionWarnings"):
        return _fail(
            snapshot_store,
            job,
            code="GEAR_STAT_ITEM_RESOLUTION_BLOCKED",
            deterministic=True,
            now=now_fn(),
        )
    snapshot = parse_simcraft_json_stat_snapshot(simc_result.get("jsonPayload"))
    if snapshot.get("statStatus") != "verified":
        return _fail(
            snapshot_store,
            job,
            code="GEAR_STAT_JSON_INVALID",
            deterministic=True,
            now=now_fn(),
        )
    eligibility = prepared.get("resolvedSnapshot", {}).get("eligibilityContext")
    eligibility = eligibility if isinstance(eligibility, dict) else {}
    snapshot.update(
        {
            "classKey": _text(eligibility.get("classKey")),
            "specKey": _text(eligibility.get("specKey")),
            "maxLevel": eligibility.get("level"),
            "gearSchemaRevision": GEAR_SCHEMA_REVISION,
        }
    )
    record = verified_snapshot_record(
        prepared["signature"],
        snapshot,
        verified_at=now_fn(),
    )
    try:
        published = snapshot_store.publish_verified(
            job_id=int(job.get("jobId") or 0),
            lock_token=_text(job.get("lockToken")),
            record=record,
            now=now_fn(),
        )
    except GearStatSnapshotIntegrityError:
        return {"status": "abandoned", "code": "GEAR_STAT_LEASE_LOST"}
    return {
        "status": "verified",
        "code": "GEAR_STAT_VERIFIED",
        "snapshotHash": _text(published.get("snapshotHash")),
    }


def current_simc_runtime_revision() -> str:
    status = simc_version_status()
    websim_state = status.get("websimState") if isinstance(status.get("websimState"), dict) else {}
    for candidate in (
        status.get("sourceCommit"),
        status.get("simcRuntimeRevision"),
        status.get("localTag"),
    ):
        value = _text(candidate).lower()
        if re.fullmatch(r"[0-9a-f]{40}", value):
            return value
    match = re.search(r"(?<![0-9a-f])([0-9a-f]{40})(?![0-9a-f])", _text(websim_state.get("source")).lower())
    if match:
        return match.group(1)
    return _text(status.get("simcRuntimeRevision") or status.get("localTag") or status.get("sourceCommit"))


def main() -> int:
    config = database_config_from_env()
    if config.backend != "postgres" or not config.database_url:
        raise RuntimeError("Gear stat snapshot worker requires PostgreSQL")
    connection_factory = lambda: connect_postgres(config.database_url)
    snapshot_store = GearStatSnapshotStore(connection_factory)
    authority_store = PostgresCacheStore(connection_factory)
    worker_id = f"{socket.gethostname()}-{os.getpid()}"
    stopping = threading.Event()

    def stop(_signum, _frame) -> None:
        stopping.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    poll_seconds = max(0.25, min(float(os.environ.get("WOW_GEAR_STAT_WORKER_POLL_SECONDS", "1")), 30.0))
    while not stopping.is_set():
        revision = current_simc_runtime_revision()
        now = utc_now()
        snapshot_store.update_worker_state(
            worker_id=worker_id,
            status="idle",
            worker_revision=WORKER_REVISION,
            simc_runtime_revision=revision,
            now=now,
        )
        if not revision:
            stopping.wait(poll_seconds)
            continue
        job = snapshot_store.claim_next(
            worker_id=worker_id,
            lock_token=uuid.uuid4().hex,
            now=now,
            lease_seconds=30,
        )
        if not job:
            stopping.wait(poll_seconds)
            continue
        snapshot_store.update_worker_state(
            worker_id=worker_id,
            status="running",
            worker_revision=WORKER_REVISION,
            simc_runtime_revision=revision,
            now=utc_now(),
            current_job_id=int(job.get("jobId") or 0),
        )
        outcome = process_claimed_job(
            job,
            authority_store=authority_store,
            snapshot_store=snapshot_store,
            simc_runtime_revision=revision,
            worker_id=worker_id,
        )
        snapshot_store.update_worker_state(
            worker_id=worker_id,
            status="idle",
            worker_revision=WORKER_REVISION,
            simc_runtime_revision=revision,
            now=utc_now(),
            last_outcome=outcome,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

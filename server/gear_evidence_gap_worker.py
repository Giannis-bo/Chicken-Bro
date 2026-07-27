#!/usr/bin/env python3
"""Bounded, request-only recovery for unresolved Gear Evidence inputs.

This module owns operational gap fencing, immutable Artifact/Observation
persistence, and bounded requests for later collection/recompilation.  It has
no publication imports or publication writer: a successful worker run can
never alter a Canonical Fact or an active release pointer.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import re
import socket
import uuid
from typing import Any, Mapping

try:
    from .gear_evidence_candidate_request_store import (
        GearEvidenceCandidateRequestStore,
        build_candidate_recompile_request,
    )
    from .gear_evidence_gap_store import GearEvidenceGapIntegrityError, GearEvidenceGapStore
    from .gear_evidence_observers import observe_artifact
    from .gear_evidence_registry import build_evidence_artifact
    from .gear_evidence_store import GearEvidenceStore
except ImportError:  # pragma: no cover - direct script/module compatibility
    from gear_evidence_candidate_request_store import (
        GearEvidenceCandidateRequestStore,
        build_candidate_recompile_request,
    )
    from gear_evidence_gap_store import GearEvidenceGapIntegrityError, GearEvidenceGapStore
    from gear_evidence_observers import observe_artifact
    from gear_evidence_registry import build_evidence_artifact
    from gear_evidence_store import GearEvidenceStore


MAX_GAP_JOBS_PER_RUN = 8
DEFAULT_LEASE_SECONDS = 90
RETRY_DELAY_SECONDS = 300
APPROVED_COLLECTOR_SOURCES = frozenset({"simc_bonus_probe"})
_COLLECTOR_INPUT_FIELDS = (
    "factType",
    "seasonRevision",
    "sourceIdentity",
    "sourceRevision",
    "sourceScope",
    "sourceType",
    "subjectKey",
)
_TERMINAL_CONFLICT_CODES = frozenset({"observation_conflict"})
_SIMC_BONUS_SUBJECT = re.compile(
    r"^item:(?P<item_id>[1-9][0-9]*)/variant:[^/]+-(?P<bonus_id>[1-9][0-9]*)$"
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bounded_jobs(value: Any) -> int:
    if isinstance(value, bool):
        return MAX_GAP_JOBS_PER_RUN
    try:
        return max(1, min(int(value), MAX_GAP_JOBS_PER_RUN))
    except (TypeError, ValueError, OverflowError):
        return MAX_GAP_JOBS_PER_RUN


def _retry_at(now: str) -> str:
    try:
        parsed = datetime.fromisoformat(_text(now).replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Gear Evidence Gap worker time must be ISO-8601.") from error
    if parsed.tzinfo is None:
        raise ValueError("Gear Evidence Gap worker time must include a timezone.")
    return (parsed + timedelta(seconds=RETRY_DELAY_SECONDS)).isoformat()


class SimcBonusSocketCollector:
    """Collect only an exact-variant socket fact from trusted local SimC evidence."""

    def __init__(self, loader: Any):
        if not callable(loader):
            raise ValueError("SimC bonus evidence loader is required.")
        self._loader = loader

    @staticmethod
    def _route_bonus_id(route: Any) -> str:
        source = route if isinstance(route, Mapping) else {}
        if (
            _text(source.get("sourceType")) != "simc_bonus_probe"
            or _text(source.get("sourceScope")) != "exact_variant"
            or _text(source.get("factType")) != "socket_count"
        ):
            return ""
        matched = _SIMC_BONUS_SUBJECT.fullmatch(_text(source.get("subjectKey")))
        return matched.group("bonus_id") if matched else ""

    @staticmethod
    def _trusted_envelope(value: Any) -> dict[str, Any]:
        source = value if isinstance(value, Mapping) else {}
        minimums = source.get("minimums") if isinstance(source.get("minimums"), Mapping) else {}
        normalized_minimums: dict[str, int] = {}
        for raw_bonus_id, raw_minimum in minimums.items():
            bonus_id = _text(raw_bonus_id)
            if (
                not bonus_id.isdigit()
                or int(bonus_id) <= 0
                or isinstance(raw_minimum, bool)
                or not isinstance(raw_minimum, int)
                or raw_minimum <= 0
            ):
                return {}
            normalized_minimums[str(int(bonus_id))] = raw_minimum
        if (
            source.get("schemaRevision") != "simc-socket-bonus-evidence-v1"
            or source.get("status") != "verified"
            or source.get("sourceType") != "simc_bonus_probe"
            or source.get("sourceScope") != "exact_variant"
            or not _text(source.get("sourceIdentity"))
            or not _text(source.get("sourceRevision"))
            or not normalized_minimums
        ):
            return {}
        return {
            "sourceIdentity": _text(source.get("sourceIdentity")),
            "sourceRevision": _text(source.get("sourceRevision")),
            "minimums": normalized_minimums,
        }

    def collect(self, route: Mapping[str, str], *, now: str) -> dict[str, Any]:
        bonus_id = self._route_bonus_id(route)
        if not bonus_id:
            return {"status": "unsupported"}
        envelope = self._trusted_envelope(self._loader())
        socket_count = envelope.get("minimums", {}).get(bonus_id)
        if not isinstance(socket_count, int) or isinstance(socket_count, bool) or socket_count <= 0:
            return {"status": "unavailable"}
        return {
            "status": "artifact",
            "artifact": build_evidence_artifact(
                source_type="simc_bonus_probe",
                source_identity=envelope["sourceIdentity"],
                source_revision=envelope["sourceRevision"],
                season_revision=_text(route.get("seasonRevision")),
                captured_at=_text(now),
                payload={
                    "bonusId": int(bonus_id),
                    "factType": "socket_count",
                    "socketCount": socket_count,
                    "subjectKey": _text(route.get("subjectKey")),
                },
            ),
        }


def runtime_approved_collection_adapters(
    simc_bonus_loader: Any,
) -> dict[str, SimcBonusSocketCollector]:
    """Expose only the trusted local SimC bonus collector at runtime."""

    return {"simc_bonus_probe": SimcBonusSocketCollector(simc_bonus_loader)}


def _collector_input(requirement: Any) -> dict[str, str]:
    source = requirement if isinstance(requirement, Mapping) else {}
    return {
        field: _text(source.get(field))
        for field in _COLLECTOR_INPUT_FIELDS
        if _text(source.get(field))
    }


def _retry_outcome(gap: Mapping[str, Any], *, problem_code: str, now: str) -> dict[str, Any]:
    return {
        "status": "retryable",
        "problemCode": problem_code,
        "missingRequirement": dict(gap.get("missingRequirement") or {}),
        "nextAttemptAt": _retry_at(now),
    }


def _terminal_outcome(gap: Mapping[str, Any], *, problem_code: str | None = None) -> dict[str, Any]:
    return {
        "status": "terminal",
        "problemCode": _text(problem_code if problem_code is not None else gap.get("problemCode")),
        "missingRequirement": dict(gap.get("missingRequirement") or {}),
    }


def _finish_gap(gap_store: Any, *, gap: Mapping[str, Any], lock_token: str, outcome: dict[str, Any], now: str) -> str:
    try:
        gap_store.finish(
            gap_key=_text(gap.get("gapKey")),
            lock_token=lock_token,
            outcome=outcome,
            now=now,
        )
    except GearEvidenceGapIntegrityError as error:
        if "lease was lost" in str(error).lower():
            return "lease_lost"
        raise
    return "finished"


def _parser_problem_code(result: Any) -> str:
    diagnostics = result.get("diagnostics") if isinstance(result, Mapping) else []
    for diagnostic in diagnostics if isinstance(diagnostics, list) else []:
        if isinstance(diagnostic, Mapping) and _text(diagnostic.get("code")) == "parser_unhandled_shape":
            return "parser_unhandled_shape"
    return "source_unavailable"


def _matching_observations(result: Any, requirement: Mapping[str, Any]) -> list[dict[str, Any]]:
    expected_subject = _text(requirement.get("subjectKey"))
    expected_fact_type = _text(requirement.get("factType"))
    observations = result.get("observations") if isinstance(result, Mapping) else []
    return [
        dict(observation)
        for observation in observations if isinstance(observation, Mapping)
        and _text(observation.get("subjectKey")) == expected_subject
        and _text(observation.get("factType")) == expected_fact_type
        and _text(observation.get("status")) == "accepted"
    ]


def _artifact_matches_route(artifact: Any, route: Mapping[str, str]) -> bool:
    if not isinstance(artifact, Mapping):
        return False
    for field in ("sourceType", "seasonRevision"):
        if _text(artifact.get(field)) != _text(route.get(field)):
            return False
    for field in ("sourceIdentity", "sourceRevision"):
        if _text(route.get(field)) and _text(artifact.get(field)) != _text(route.get(field)):
            return False
    return True


def _collection_result(value: Any) -> tuple[str, Mapping[str, Any] | None]:
    result = value if isinstance(value, Mapping) else {}
    status = _text(result.get("status"))
    if status == "requested":
        return status, None
    if status == "artifact" and isinstance(result.get("artifact"), Mapping):
        return status, result["artifact"]
    return "invalid", None


def _finish_or_lease_lost(summary: dict[str, int | str], gap_store: Any, *, gap: Mapping[str, Any], lock_token: str, outcome: dict[str, Any], now: str, terminal: bool) -> bool:
    finished = _finish_gap(gap_store, gap=gap, lock_token=lock_token, outcome=outcome, now=now)
    if finished == "lease_lost":
        summary["status"] = "lease_lost"
        summary["leaseLostCount"] = int(summary["leaseLostCount"]) + 1
        return True
    summary["processedCount"] = int(summary["processedCount"]) + 1
    key = "terminalCount" if terminal else "retryableCount"
    summary[key] = int(summary[key]) + 1
    return False


def run_gear_evidence_gap_worker(
    *,
    gap_store: Any,
    evidence_store: Any,
    approved_collectors: Mapping[str, Any] | None,
    candidate_request_store: Any,
    worker_id: str,
    now: str,
    artifact_observer=observe_artifact,
    max_jobs: int = MAX_GAP_JOBS_PER_RUN,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    lock_token_factory=None,
) -> dict[str, Any]:
    """Claim a bounded batch, persist only immutable evidence, and request follow-up."""

    if not hasattr(gap_store, "claim_next") or not hasattr(gap_store, "finish"):
        raise ValueError("Gear Evidence Gap queue owner is required.")
    if not hasattr(evidence_store, "persist_artifact") or not hasattr(evidence_store, "persist_observation"):
        raise ValueError("Gear Evidence Artifact/Observation store is required.")
    if not hasattr(candidate_request_store, "handoff_recovered"):
        raise ValueError("Fenced Gear Evidence candidate request store is required.")
    if not callable(artifact_observer):
        raise ValueError("An approved Artifact observer is required.")
    normalized_worker_id = _text(worker_id)
    normalized_now = _text(now)
    if not normalized_worker_id or not normalized_now:
        raise ValueError("Gear Evidence Gap worker identity and time are required.")
    _retry_at(normalized_now)
    active_collectors = approved_collectors if isinstance(approved_collectors, Mapping) else {}
    token_factory = lock_token_factory or (lambda _index: uuid.uuid4().hex)
    summary: dict[str, int | str] = {
        "status": "completed",
        "claimedCount": 0,
        "processedCount": 0,
        "retryableCount": 0,
        "terminalCount": 0,
        "leaseLostCount": 0,
        "candidateHandoffCount": 0,
    }

    for index in range(_bounded_jobs(max_jobs)):
        lock_token = _text(token_factory(index))
        if not lock_token:
            raise ValueError("Gear Evidence Gap lock token is required.")
        gap = gap_store.claim_next(
            worker_id=normalized_worker_id,
            lock_token=lock_token,
            now=normalized_now,
            lease_seconds=lease_seconds,
        )
        if not isinstance(gap, Mapping) or not _text(gap.get("gapKey")):
            break
        normalized_gap = dict(gap)
        summary["claimedCount"] = int(summary["claimedCount"]) + 1
        problem_code = _text(normalized_gap.get("problemCode"))
        if problem_code in _TERMINAL_CONFLICT_CODES:
            if _finish_or_lease_lost(summary, gap_store, gap=normalized_gap, lock_token=lock_token, outcome=_terminal_outcome(normalized_gap), now=normalized_now, terminal=True):
                break
            continue

        route = {
            **_collector_input(normalized_gap.get("missingRequirement")),
            "gapKey": _text(normalized_gap.get("gapKey")),
            "factKey": _text(normalized_gap.get("factKey")),
        }
        source_type = route.get("sourceType", "")
        if not source_type or not route.get("sourceScope"):
            if _finish_or_lease_lost(summary, gap_store, gap=normalized_gap, lock_token=lock_token, outcome=_terminal_outcome(normalized_gap, problem_code="compiler_policy_missing"), now=normalized_now, terminal=True):
                break
            continue
        collector = active_collectors.get(source_type)
        if not hasattr(collector, "collect"):
            if _finish_or_lease_lost(summary, gap_store, gap=normalized_gap, lock_token=lock_token, outcome=_terminal_outcome(normalized_gap, problem_code="compiler_policy_missing"), now=normalized_now, terminal=True):
                break
            continue
        try:
            collection_status, artifact = _collection_result(collector.collect(dict(route), now=normalized_now))
            if collection_status == "requested":
                outcome = _retry_outcome(normalized_gap, problem_code=problem_code or "artifact_missing", now=normalized_now)
            elif collection_status == "artifact" and _artifact_matches_route(artifact, route):
                persisted_artifact = evidence_store.persist_artifact(dict(artifact or {}))
                observed = artifact_observer(persisted_artifact)
                observations = _matching_observations(observed, route)
                if observations:
                    persisted_observations = [
                        evidence_store.persist_observation(observation)
                        for observation in observations
                    ]
                    request = build_candidate_recompile_request(
                        gap_key=_text(normalized_gap.get("gapKey")),
                        artifact=persisted_artifact,
                        observations=persisted_observations,
                        now=normalized_now,
                    )
                    candidate_request_store.handoff_recovered(
                        request=request,
                        gap_lock_token=lock_token,
                        now=normalized_now,
                    )
                    summary["candidateHandoffCount"] = int(summary["candidateHandoffCount"]) + 1
                    continue
                outcome = _retry_outcome(normalized_gap, problem_code=_parser_problem_code(observed), now=normalized_now)
            else:
                outcome = _retry_outcome(normalized_gap, problem_code="source_unavailable", now=normalized_now)
        except Exception:
            outcome = _retry_outcome(normalized_gap, problem_code="source_unavailable", now=normalized_now)
        if _finish_or_lease_lost(summary, gap_store, gap=normalized_gap, lock_token=lock_token, outcome=outcome, now=normalized_now, terminal=False):
            break

    return dict(summary)


def _run_from_environment(*, now: str) -> dict[str, Any]:
    try:
        from .db import connect_postgres, database_config_from_env, postgres_only_runtime_enabled
        from .gear_evidence_candidate_request_store import GearEvidenceCandidateRequestStore
        from .gear_release_tool import load_simc_socket_bonus_minimums
        from .simulator_payload import simc_version_status
    except ImportError:  # pragma: no cover - direct script/module compatibility
        from db import connect_postgres, database_config_from_env, postgres_only_runtime_enabled
        from gear_evidence_candidate_request_store import GearEvidenceCandidateRequestStore
        from gear_release_tool import load_simc_socket_bonus_minimums
        from simulator_payload import simc_version_status
    config = database_config_from_env()
    if not postgres_only_runtime_enabled(config):
        raise RuntimeError("Gear Evidence Gap worker requires the PostgreSQL-only runtime")
    connection_factory = lambda: connect_postgres(config.database_url)
    simc_status = simc_version_status()
    simc_binary = _text((simc_status if isinstance(simc_status, Mapping) else {}).get("binaryPath"))
    simc_revision = _text((simc_status if isinstance(simc_status, Mapping) else {}).get("sourceCommit"))
    if not simc_binary or not simc_revision:
        raise RuntimeError("Gear Evidence Gap worker requires the current SimC probe identity")
    return run_gear_evidence_gap_worker(
        gap_store=GearEvidenceGapStore(connection_factory),
        evidence_store=GearEvidenceStore(connection_factory),
        approved_collectors=runtime_approved_collection_adapters(
            lambda: load_simc_socket_bonus_minimums(
                simc_binary,
                source_identity="simulationcraft:show_bonus_ids",
                source_revision=simc_revision,
            )
        ),
        candidate_request_store=GearEvidenceCandidateRequestStore(connection_factory),
        worker_id=f"gear-evidence-gap:{socket.gethostname()}",
        now=now,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = _run_from_environment(now=datetime.now(timezone.utc).isoformat())
    except Exception:
        result = {
            "status": "failed",
            "claimedCount": 0,
            "processedCount": 0,
            "retryableCount": 0,
            "terminalCount": 0,
            "leaseLostCount": 0,
            "candidateHandoffCount": 0,
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result.get("status") in {"failed", "lease_lost"} else 0


__all__ = (
    "APPROVED_COLLECTOR_SOURCES",
    "MAX_GAP_JOBS_PER_RUN",
    "SimcBonusSocketCollector",
    "run_gear_evidence_gap_worker",
    "runtime_approved_collection_adapters",
)


if __name__ == "__main__":
    raise SystemExit(main())

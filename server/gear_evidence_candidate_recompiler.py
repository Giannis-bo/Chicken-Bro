#!/usr/bin/env python3
"""Consume fenced evidence requests by sealing only inactive candidate releases."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import socket
from typing import Any, Mapping

try:
    from .gear_evidence_candidate_request_store import (
        GearEvidenceCandidateRequestIntegrityError,
        validate_candidate_recompile_evidence,
    )
except ImportError:  # pragma: no cover - direct script/module compatibility
    from gear_evidence_candidate_request_store import (
        GearEvidenceCandidateRequestIntegrityError,
        validate_candidate_recompile_evidence,
    )


MAX_CANDIDATE_RECOMPILE_JOBS_PER_RUN = 8


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bounded_jobs(value: Any) -> int:
    if isinstance(value, bool):
        return MAX_CANDIDATE_RECOMPILE_JOBS_PER_RUN
    try:
        return max(1, min(int(value), MAX_CANDIDATE_RECOMPILE_JOBS_PER_RUN))
    except (TypeError, ValueError, OverflowError):
        return MAX_CANDIDATE_RECOMPILE_JOBS_PER_RUN


def _sealed_candidate_id(value: Any) -> str:
    result = value if isinstance(value, Mapping) else {}
    gear = result.get("gearRelease") if isinstance(result.get("gearRelease"), Mapping) else {}
    seal = result.get("gearSeal") if isinstance(result.get("gearSeal"), Mapping) else {}
    release_id = _text(gear.get("releaseId"))
    if not release_id or _text(seal.get("releaseId")) != release_id:
        return ""
    if _text(seal.get("status")) not in {"inserted", "reused"}:
        return ""
    return release_id


def run_gear_evidence_candidate_recompiler(
    *,
    request_store: Any,
    evidence_store: Any,
    candidate_builder: Any,
    worker_id: str,
    now: str,
    lock_token_factory=None,
    max_jobs: int = MAX_CANDIDATE_RECOMPILE_JOBS_PER_RUN,
) -> dict[str, Any]:
    """Seal candidate-only releases, then complete the matching fenced handoff."""

    if not all(hasattr(request_store, name) for name in ("claim_next", "complete_sealed", "retry")):
        raise ValueError("Fenced candidate request store is required.")
    if not hasattr(evidence_store, "load_candidate_evidence"):
        raise ValueError("Candidate evidence store is required.")
    if not callable(candidate_builder):
        raise ValueError("Candidate builder is required.")
    if not _text(worker_id) or not _text(now):
        raise ValueError("Candidate worker identity and time are required.")
    token_factory = lock_token_factory or (lambda index: f"candidate-{index}")
    summary = {
        "status": "completed",
        "claimedCount": 0,
        "sealedCount": 0,
        "retryableCount": 0,
    }
    for index in range(_bounded_jobs(max_jobs)):
        lock_token = _text(token_factory(index))
        if not lock_token:
            raise ValueError("Candidate worker lock token is required.")
        request = request_store.claim_next(
            worker_id=_text(worker_id),
            lock_token=lock_token,
            now=_text(now),
        )
        if not isinstance(request, Mapping) or not _text(request.get("requestKey")):
            break
        summary["claimedCount"] += 1
        request_key = _text(request.get("requestKey"))
        request_token = _text(request.get("lockToken")) or lock_token
        try:
            evidence = evidence_store.load_candidate_evidence(
                artifact_id=_text(request.get("artifactId")),
                observation_ids=list(request.get("observationIds") or ()),
            )
            collected_evidence = validate_candidate_recompile_evidence(request, evidence)
            candidate = candidate_builder(
                collected_evidence=collected_evidence,
                request=dict(request),
            )
            candidate_gear_release_id = _sealed_candidate_id(candidate)
            if not candidate_gear_release_id:
                raise GearEvidenceCandidateRequestIntegrityError(
                    "Candidate Gear Release was not sealed."
                )
            request_store.complete_sealed(
                request_key=request_key,
                lock_token=request_token,
                candidate_gear_release_id=candidate_gear_release_id,
                now=_text(now),
            )
            summary["sealedCount"] += 1
        except Exception:
            request_store.retry(
                request_key=request_key,
                lock_token=request_token,
                problem_code="candidate_recompile_failed",
                now=_text(now),
            )
            summary["retryableCount"] += 1
    return dict(summary)


def _simc_probe_identity(status: Any) -> tuple[str, str]:
    source = status if isinstance(status, Mapping) else {}
    binary = _text(source.get("binaryPath"))
    revision = _text(source.get("sourceCommit"))
    if not binary or not revision:
        raise RuntimeError("candidate evidence recompile requires the current SimC probe identity")
    return binary, revision


def _formal_active_binding(value: Any) -> Mapping[str, Any]:
    binding = value if isinstance(value, Mapping) else {}
    if binding.get("formalActiveManifest") is not True:
        raise RuntimeError("candidate evidence recompile requires the formal active Manifest")
    manifest = binding.get("manifest") if isinstance(binding.get("manifest"), Mapping) else {}
    gear = binding.get("gearRelease") if isinstance(binding.get("gearRelease"), Mapping) else {}
    community = binding.get("communityRelease") if isinstance(binding.get("communityRelease"), Mapping) else {}
    if not manifest or not _text(gear.get("releaseId")) or not _text(community.get("releaseId")):
        raise RuntimeError("candidate evidence recompile requires the complete active release pair")
    return binding


def _run_from_environment(*, now: str) -> dict[str, Any]:
    """Run the candidate-only consumer without entering refresh/promotion."""

    try:
        from .db import connect_postgres, database_config_from_env, postgres_only_runtime_enabled
        from .gear_evidence_candidate_request_store import GearEvidenceCandidateRequestStore
        from .gear_evidence_store import GearEvidenceStore
        from .gear_release_refresh import build_staging_candidates
        from .gear_release_store import GearReleaseStore
        from .gear_release_tool import (
            expected_spec_pairs,
            load_simc_socket_bonus_minimums,
            runtime_dependency_revisions,
        )
        from .simulator_payload import simc_version_status
    except ImportError:  # pragma: no cover - direct script/module compatibility
        from db import connect_postgres, database_config_from_env, postgres_only_runtime_enabled
        from gear_evidence_candidate_request_store import GearEvidenceCandidateRequestStore
        from gear_evidence_store import GearEvidenceStore
        from gear_release_refresh import build_staging_candidates
        from gear_release_store import GearReleaseStore
        from gear_release_tool import (
            expected_spec_pairs,
            load_simc_socket_bonus_minimums,
            runtime_dependency_revisions,
        )
        from simulator_payload import simc_version_status

    config = database_config_from_env()
    if not postgres_only_runtime_enabled(config):
        raise RuntimeError("candidate evidence recompile requires the PostgreSQL-only runtime")
    connection_factory = lambda: connect_postgres(config.database_url)
    store = GearReleaseStore(connection_factory)
    active_binding = _formal_active_binding(store.load_active_manifest_binding())
    simc_binary, simc_revision = _simc_probe_identity(simc_version_status())
    dependencies = runtime_dependency_revisions(simc_revision)
    active_manifest = active_binding.get("manifest") if isinstance(active_binding.get("manifest"), Mapping) else {}
    active_gear = active_binding.get("gearRelease") if isinstance(active_binding.get("gearRelease"), Mapping) else {}
    season_revision = _text(active_manifest.get("seasonRevision") or active_gear.get("seasonRevision"))
    if not season_revision:
        raise RuntimeError("candidate evidence recompile requires an active season revision")

    def candidate_builder(*, collected_evidence: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
        if _text(request.get("seasonRevision")) != season_revision:
            raise RuntimeError("candidate evidence request season no longer matches the active binding")
        return build_staging_candidates(
            store,
            active_binding=dict(active_binding),
            expected_specs=expected_spec_pairs(),
            dependency_revisions=dependencies,
            now=now,
            socket_bonus_minimums=load_simc_socket_bonus_minimums(
                simc_binary,
                source_identity="simulationcraft:show_bonus_ids",
                source_revision=simc_revision,
            ),
            candidate_season_revision=season_revision,
            extra_artifacts=tuple(collected_evidence.get("artifacts") or ()),
            extra_observations=tuple(collected_evidence.get("observations") or ()),
        )

    return run_gear_evidence_candidate_recompiler(
        request_store=GearEvidenceCandidateRequestStore(connection_factory),
        evidence_store=GearEvidenceStore(connection_factory),
        candidate_builder=candidate_builder,
        worker_id=f"gear-evidence-candidate-recompiler:{socket.gethostname()}",
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
            "sealedCount": 0,
            "retryableCount": 0,
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result.get("status") == "failed" else 0


__all__ = ("run_gear_evidence_candidate_recompiler",)


if __name__ == "__main__":
    raise SystemExit(main())

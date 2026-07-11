#!/usr/bin/env python3
"""Candidate-first scheduled refresh orchestration for immutable gear releases."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import json
from typing import Any, Iterable

try:
    from . import gear_release
    from .gear_release_store import canonical_row_hash
except ImportError:
    import gear_release
    from gear_release_store import canonical_row_hash


_ROW_IDENTITIES = {
    "items": "itemId",
    "sources": "sourceId",
    "variants": "variantId",
    "options": "optionId",
}

_TERMINAL_WINNER_PROBLEM_CODES = {
    "COMMUNITY_SOURCE_STALE",
    "COMMUNITY_SOURCE_BLOCKED",
    "COMMUNITY_RESOLVER_ILLEGAL",
    "COMMUNITY_PROFILE_NOT_READY",
    "COMMUNITY_GEAR_RELEASE_MISMATCH",
    "COMMUNITY_INTENT_SPEC_MISMATCH",
}

_DEPENDENCY_RISK_FIELDS = (
    ("capabilityRevision", "capability_change"),
    ("serializerRevision", "serializer_change"),
    ("selectionSchemaRevision", "schema_change"),
    ("gearRuleRevision", "rule_change"),
    ("resolverContractRevision", "rule_change"),
    ("simcRuntimeRevision", "high_risk_gear"),
    ("statPolicyRevision", "high_risk_gear"),
)

_LEASE_KEY = "wow-gear-release-refresh-v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


class PostgresRefreshLease:
    """Hold one non-blocking session advisory lock for the full refresh run."""

    def __init__(self, connection_factory, lease_key: str = _LEASE_KEY):
        self._connection_factory = connection_factory
        self._lease_key = _text(lease_key) or _LEASE_KEY
        self._connection = None
        self._acquired = False

    def __enter__(self) -> bool:
        self._connection = self._connection_factory()
        with self._connection.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtext(%s))", (self._lease_key,))
            row = cur.fetchone()
        self._acquired = bool(row and row[0] is True)
        return self._acquired

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._connection is not None and self._acquired:
                with self._connection.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(hashtext(%s))", (self._lease_key,))
        finally:
            if self._connection is not None:
                self._connection.close()
            self._connection = None
            self._acquired = False
        return False


def _canonical_counts(value: dict[str, int]) -> dict[str, int]:
    return {key: int(value.get(key) or 0) for key in _ROW_IDENTITIES}


def classify_gear_change(
    active_row_hashes: dict[str, dict[str, str]],
    candidate_snapshot: dict[str, Iterable[dict[str, Any]]],
) -> dict[str, Any]:
    """Classify a staging Gear snapshot against one immutable active release.

    Additive means every active identity and row hash is preserved exactly and
    the candidate only adds identities. Any mutation or removal is high risk.
    """

    active = active_row_hashes if isinstance(active_row_hashes, dict) else {}
    snapshot = candidate_snapshot if isinstance(candidate_snapshot, dict) else {}
    added: dict[str, int] = {}
    changed: dict[str, int] = {}
    removed: dict[str, int] = {}
    for category, identity_field in _ROW_IDENTITIES.items():
        active_rows = active.get(category) if isinstance(active.get(category), dict) else {}
        candidate_rows = {}
        for row in snapshot.get(category) or []:
            if not isinstance(row, dict):
                continue
            identity = _text(row.get(identity_field))
            if identity:
                candidate_rows[identity] = canonical_row_hash(row)
        active_ids = set(active_rows)
        candidate_ids = set(candidate_rows)
        added[category] = len(candidate_ids - active_ids)
        removed[category] = len(active_ids - candidate_ids)
        changed[category] = sum(
            1
            for identity in active_ids.intersection(candidate_ids)
            if _text(active_rows.get(identity)) != _text(candidate_rows.get(identity))
        )

    has_removed_or_changed = any(removed.values()) or any(changed.values())
    has_added = any(added.values())
    if has_removed_or_changed:
        risk_class = "high_risk_gear"
    elif has_added:
        risk_class = "low_risk_additive_gear"
    else:
        risk_class = "same_gear_community"
    return {
        "schemaRevision": "gear-release-change-classification-v1",
        "riskClass": risk_class,
        "addedCounts": _canonical_counts(added),
        "changedCounts": _canonical_counts(changed),
        "removedCounts": _canonical_counts(removed),
    }


def classify_refresh_risk(
    gear_risk_class: str,
    active_dependencies: dict[str, Any],
    candidate_dependencies: dict[str, Any],
    *,
    season_changed: bool,
) -> str:
    """Promote dependency/season changes above content-only Gear risk."""

    if season_changed:
        return "new_season"
    active = active_dependencies if isinstance(active_dependencies, dict) else {}
    candidate = candidate_dependencies if isinstance(candidate_dependencies, dict) else {}
    for field, risk_class in _DEPENDENCY_RISK_FIELDS:
        if _text(active.get(field)) != _text(candidate.get(field)):
            return risk_class
    return _text(gear_risk_class) or "high_risk_gear"


def _scheduled_gear_descriptor(
    prepared: dict[str, Any],
    *,
    active_release_id: str,
    dependency_revisions: dict[str, Any],
) -> dict[str, Any]:
    release = prepared.get("release") if isinstance(prepared.get("release"), dict) else {}
    gate = prepared.get("gate") if isinstance(prepared.get("gate"), dict) else {}
    return gear_release.build_release(
        release_kind="gear",
        season_revision=_text(release.get("seasonRevision")),
        schema_revision=_text(release.get("schemaRevision")) or "gear-release-v1",
        content=release.get("content") or {},
        dependency_revisions=dependency_revisions,
        release_status=_text(release.get("releaseStatus")) or "validated",
        source={
            "sourceRevision": "scheduled-refresh-v1",
            "stagingSnapshotHash": _text(gate.get("snapshotHash")),
        },
        parent_release_id=active_release_id,
    )


def _scheduled_community_descriptor(
    prepared: dict[str, Any],
    *,
    active_release_id: str,
    gear_release_id: str,
    dependency_revisions: dict[str, Any],
) -> dict[str, Any]:
    release = prepared.get("release") if isinstance(prepared.get("release"), dict) else {}
    source = release.get("source") if isinstance(release.get("source"), dict) else {}
    return gear_release.build_release(
        release_kind="community",
        season_revision=_text(release.get("seasonRevision")),
        schema_revision=_text(release.get("schemaRevision")) or "community-release-v1",
        content=release.get("content") or {},
        dependency_revisions=dependency_revisions,
        release_status=_text(release.get("releaseStatus")) or "blocked",
        source={
            "sourceRevision": "scheduled-refresh-v1",
            "validatedAgainstGearReleaseId": gear_release_id,
            "stagingTemplateCount": int(source.get("stagingTemplateCount") or 0),
        },
        parent_release_id=active_release_id,
        validated_against_release_id=gear_release_id,
    )


def build_staging_candidates(
    store: Any,
    *,
    active_binding: dict[str, Any],
    expected_specs: Iterable[tuple[str, str]],
    dependency_revisions: dict[str, Any],
    now: str,
    candidate_season_revision: str = "",
    gear_preparer: Any = None,
    community_preparer: Any = None,
) -> dict[str, Any]:
    """Create/reuse and seal the inactive candidate pair before any decision."""

    if gear_preparer is None or community_preparer is None:
        try:
            from .gear_release_tool import (
                prepare_staging_community_release,
                prepare_staging_gear_release,
            )
        except ImportError:
            from gear_release_tool import prepare_staging_community_release, prepare_staging_gear_release
        gear_preparer = gear_preparer or prepare_staging_gear_release
        community_preparer = community_preparer or prepare_staging_community_release

    binding = active_binding if isinstance(active_binding, dict) else {}
    active_manifest = binding.get("manifest") if isinstance(binding.get("manifest"), dict) else {}
    active_gear = binding.get("gearRelease") if isinstance(binding.get("gearRelease"), dict) else {}
    active_community = binding.get("communityRelease") if isinstance(binding.get("communityRelease"), dict) else {}
    active_gear_id = _text(active_gear.get("releaseId"))
    active_community_id = _text(active_community.get("releaseId"))
    if not active_gear_id or not active_community_id:
        raise RuntimeError("active release pair is required")

    active_gear_source = active_gear.get("source") if isinstance(active_gear.get("source"), dict) else {}
    prepared_gear = gear_preparer(
        store,
        season_revision=(
            _text(candidate_season_revision)
            or _text(active_manifest.get("seasonRevision") or active_gear.get("seasonRevision"))
        ),
        dependency_revisions=dependency_revisions,
        source_revision=_text(active_gear_source.get("sourceRevision")) or "scheduled-refresh-v1",
        parent_release_id=_text(active_gear.get("parentReleaseId")),
    )
    snapshot = prepared_gear.get("snapshot") if isinstance(prepared_gear.get("snapshot"), dict) else {}
    gear_change = classify_gear_change(
        store.get_gear_release_row_hashes(active_gear_id),
        snapshot,
    )
    active_dependencies = (
        active_manifest.get("dependencyRevisions")
        if isinstance(active_manifest.get("dependencyRevisions"), dict)
        else active_gear.get("dependencyRevisions") or {}
    )
    season_changed = _text(active_gear.get("seasonRevision")) != _text((prepared_gear.get("release") or {}).get("seasonRevision"))
    risk_class = classify_refresh_risk(
        gear_change["riskClass"],
        active_dependencies,
        dependency_revisions,
        season_changed=season_changed,
    )
    candidate_gear = prepared_gear.get("release") if isinstance(prepared_gear.get("release"), dict) else {}
    if risk_class != "same_gear_community":
        candidate_gear = _scheduled_gear_descriptor(
            prepared_gear,
            active_release_id=active_gear_id,
            dependency_revisions=dependency_revisions,
        )
    gear_seal = store.seal_gear_release(
        candidate_gear,
        snapshot,
        gate_result=prepared_gear.get("gate") or {},
        event={"mode": "scheduled-refresh-v1", "change": gear_change},
    )

    active_community_source = active_community.get("source") if isinstance(active_community.get("source"), dict) else {}
    prepared_community = community_preparer(
        store,
        gear_release_descriptor=candidate_gear,
        gear_snapshot=snapshot,
        dependency_revisions=dependency_revisions,
        expected_specs=expected_specs,
        now=now,
        source_revision=_text(active_community_source.get("sourceRevision")) or "scheduled-refresh-v1",
        parent_release_id=_text(active_community.get("parentReleaseId")),
    )
    candidate_community = prepared_community.get("release") if isinstance(prepared_community.get("release"), dict) else {}
    can_reuse_active_community = (
        candidate_gear.get("releaseId") == active_gear_id
        and candidate_community.get("content") == active_community.get("content")
        and candidate_community.get("dependencyRevisions") == active_community.get("dependencyRevisions")
        and candidate_community.get("releaseStatus") == active_community.get("releaseStatus")
        and candidate_community.get("seasonRevision") == active_community.get("seasonRevision")
        and candidate_community.get("schemaRevision") == active_community.get("schemaRevision")
    )
    if can_reuse_active_community:
        candidate_community = active_community
    else:
        candidate_community = _scheduled_community_descriptor(
            prepared_community,
            active_release_id=active_community_id,
            gear_release_id=_text(candidate_gear.get("releaseId")),
            dependency_revisions=dependency_revisions,
        )
    candidate_rows = [row for row in prepared_community.get("rows") or [] if isinstance(row, dict)]
    community_seal = store.seal_community_release(
        candidate_community,
        candidate_rows,
        gate_result=prepared_community.get("gate") or {},
        event={"mode": "scheduled-refresh-v1", "riskClass": risk_class},
    )

    active_pair = store.load_community_release(active_gear_id, active_community_id)
    active_winners = active_pair.get("winners") if isinstance(active_pair, dict) else []
    role_counts = {
        role: sum(1 for row in candidate_rows if _text(row.get("role")) == role)
        for role in ("winner", "standby", "rejected")
    }
    counts = {
        **role_counts,
        "empty": max(0, len(list(expected_specs)) - role_counts["winner"]),
    }
    return {
        "gearRelease": candidate_gear,
        "communityRelease": candidate_community,
        "gearSeal": gear_seal,
        "communitySeal": community_seal,
        "gearChange": gear_change,
        "riskClass": risk_class,
        "activeWinners": active_winners or [],
        "candidateRows": candidate_rows,
        "election": prepared_community.get("election") or {},
        "counts": counts,
    }


def coverage_regressions(
    active_winners: Iterable[dict[str, Any]],
    candidate_rows: Iterable[dict[str, Any]],
) -> list[dict[str, str]]:
    """Return active legal winners lost without explicit terminal evidence."""

    rows = [row for row in candidate_rows or [] if isinstance(row, dict)]
    candidate_winner_specs = {
        (_text(row.get("classKey")), _text(row.get("specKey")))
        for row in rows
        if _text(row.get("role")) == "winner"
    }
    rejected_by_id: dict[str, set[str]] = {}
    for row in rows:
        if _text(row.get("role")) != "rejected":
            continue
        template_id = _text(row.get("templateId") or row.get("candidateId"))
        rejected_by_id[template_id] = {
            _text(problem.get("code"))
            for problem in row.get("problems") or []
            if isinstance(problem, dict) and _text(problem.get("code"))
        }

    regressions = []
    for row in active_winners or []:
        if not isinstance(row, dict):
            continue
        class_key = _text(row.get("classKey"))
        spec_key = _text(row.get("specKey"))
        if (class_key, spec_key) in candidate_winner_specs:
            continue
        template_id = _text(row.get("templateId") or row.get("candidateId"))
        terminal = bool(rejected_by_id.get(template_id, set()).intersection(_TERMINAL_WINNER_PROBLEM_CODES))
        if terminal:
            continue
        regressions.append({
            "code": "ACTIVE_LEGAL_WINNER_LOST",
            "classKey": class_key,
            "specKey": spec_key,
            "templateId": template_id,
        })
    return sorted(regressions, key=lambda row: (row["classKey"], row["specKey"], row["templateId"]))


def _matrix_passed(shadow: dict[str, Any], expected_count: int) -> bool:
    execution = shadow if isinstance(shadow, dict) else {}
    report = execution.get("report") if isinstance(execution.get("report"), dict) else execution
    blockers = [*list(execution.get("blockers") or []), *list(report.get("blockers") or [])]
    spec_results = [row for row in execution.get("specResults") or [] if isinstance(row, dict)]
    return (
        _text(execution.get("status")) in {"pass", "degraded"}
        and _text(report.get("status")) in {"pass", "degraded"}
        and not blockers
        and len(spec_results) == expected_count
        and all(_text(row.get("status")) not in {"blocked", "failed"} for row in spec_results)
    )


def _bounded_problem(code: str, detail: str) -> dict[str, str]:
    return {
        "kind": "RELEASE_REFRESH_FAILED",
        "code": code,
        "path": "releaseRefresh",
        "detail": detail,
    }


def _event_summary(
    *,
    status: str,
    candidate: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
    manifest_revision: str = "",
    shadow: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate = candidate if isinstance(candidate, dict) else {}
    gear = candidate.get("gearRelease") if isinstance(candidate.get("gearRelease"), dict) else {}
    community = candidate.get("communityRelease") if isinstance(candidate.get("communityRelease"), dict) else {}
    decision = decision if isinstance(decision, dict) else {}
    shadow = shadow if isinstance(shadow, dict) else {}
    shadow_report = shadow.get("report") if isinstance(shadow.get("report"), dict) else {}
    performance = shadow.get("performance") if isinstance(shadow.get("performance"), dict) else {}
    gear_change = candidate.get("gearChange") if isinstance(candidate.get("gearChange"), dict) else {}
    bounded_change = {
        change_kind: _canonical_counts(
            gear_change.get(change_kind) if isinstance(gear_change.get(change_kind), dict) else {}
        )
        for change_kind in ("addedCounts", "changedCounts", "removedCounts")
    }
    return {
        "status": status,
        "gearReleaseId": _text(gear.get("releaseId")),
        "communityReleaseId": _text(community.get("releaseId")),
        "manifestRevision": _text(manifest_revision),
        "riskClass": _text(decision.get("riskClass") or candidate.get("riskClass")),
        "decision": _text(decision.get("decision")),
        "blockerCodes": [
            _text(problem.get("code"))
            for problem in (decision.get("blockers") or [])[:16]
            if isinstance(problem, dict) and _text(problem.get("code"))
        ],
        "counts": candidate.get("counts") if isinstance(candidate.get("counts"), dict) else {},
        "gearChange": bounded_change,
        "sealStatus": {
            "gear": _text((candidate.get("gearSeal") or {}).get("status")),
            "community": _text((candidate.get("communitySeal") or {}).get("status")),
        },
        "shadowStatus": _text(shadow.get("status") or shadow_report.get("status")),
        "shadowSpecCount": len([
            row for row in shadow.get("specResults") or [] if isinstance(row, dict)
        ]),
        "shadowPerformance": {
            key: performance.get(key)
            for key in ("specP95Ms", "specMaxMs", "totalDurationMs")
            if isinstance(performance.get(key), (int, float))
        },
    }


def run_release_refresh(
    store: Any,
    *,
    expected_specs: Iterable[tuple[str, str]],
    dependency_revisions: dict[str, Any],
    now: str,
    updated_by: str,
    candidate_season_revision: str = "",
    lease: Any = None,
    candidate_builder: Any,
    shadow_runner: Any,
) -> dict[str, Any]:
    """Run one candidate-first refresh while keeping pointer mutation last."""

    expected = sorted({(_text(class_key), _text(spec_key)) for class_key, spec_key in expected_specs})
    lease_context = lease if lease is not None else nullcontext(True)
    with lease_context as acquired:
        if not acquired:
            event = {"status": "lease_conflict", "at": _text(now)}
            store.record_refresh_event("gear_release_refresh_lease_conflict", event)
            return event

        store.record_refresh_event("gear_release_refresh_started", {
            "status": "running",
            "at": _text(now),
            "expectedSpecCount": len(expected),
        })
        candidate = None
        try:
            binding = store.load_active_manifest_binding()
            if not isinstance(binding, dict) or binding.get("formalActiveManifest") is not True:
                raise RuntimeError("formal active Manifest binding is required")
            candidate = candidate_builder(
                store,
                active_binding=binding,
                expected_specs=expected,
                dependency_revisions=dependency_revisions,
                now=now,
                candidate_season_revision=candidate_season_revision,
            )
            if not isinstance(candidate, dict):
                raise RuntimeError("candidate builder returned no result")
            gear = candidate.get("gearRelease") if isinstance(candidate.get("gearRelease"), dict) else {}
            community = candidate.get("communityRelease") if isinstance(candidate.get("communityRelease"), dict) else {}
            if not _text(gear.get("releaseId")) or not _text(community.get("releaseId")):
                raise RuntimeError("candidate release binding is incomplete")

            shadow = shadow_runner(
                expected_specs=expected,
                gear_release_id=gear["releaseId"],
                community_release_id=community["releaseId"],
                simc_runtime_revision=_text(dependency_revisions.get("simcRuntimeRevision")),
            )
            report = shadow.get("report") if isinstance(shadow, dict) and isinstance(shadow.get("report"), dict) else shadow
            regressions = coverage_regressions(
                candidate.get("activeWinners") or [],
                candidate.get("candidateRows") or [],
            )
            decision = gear_release.decide_promotion(
                risk_class=_text(candidate.get("riskClass")),
                shadow_report=report if isinstance(report, dict) else {},
                coverage_regressions=regressions,
                full_matrix_passed=_matrix_passed(shadow, len(expected)),
            )
            active_manifest = binding.get("manifest") if isinstance(binding.get("manifest"), dict) else {}
            manifest = gear_release.build_manifest(
                season_revision=_text(gear.get("seasonRevision")),
                gear_release=gear,
                community_release=community,
                talent_catalog_revision=_text(active_manifest.get("talentCatalogRevision")),
                dependency_revisions=dependency_revisions,
                rollback_manifest_revision=_text(binding.get("manifestRevision")),
            )
            status = _text(decision.get("decision"))
            pointer = None
            if status == "auto_promote":
                command = gear_release.build_pointer_command(
                    "promote",
                    manifest["manifestRevision"],
                    int(binding.get("generation") or 0),
                    _text(binding.get("manifestRevision")),
                    target_mode="active",
                )
                pointer = store.seal_manifest_and_compare_and_swap_pointer(
                    manifest,
                    command,
                    updated_by=updated_by,
                )
                result_status = "promoted"
            else:
                store.seal_manifest(manifest)
                result_status = "manual_required" if status == "manual_required" else "blocked"
            event = _event_summary(
                status=result_status,
                candidate=candidate,
                decision=decision,
                manifest_revision=manifest["manifestRevision"],
                shadow=shadow,
            )
            event["at"] = _text(now)
            store.record_refresh_event(
                "gear_release_refresh_completed",
                event,
                release_id=community["releaseId"],
                manifest_revision=manifest["manifestRevision"],
            )
            return {
                **event,
                "decision": decision,
                "pointer": pointer,
                "shadow": shadow,
            }
        except Exception:
            problem = _bounded_problem(
                "REFRESH_EXECUTION_FAILED",
                "Release refresh failed before a safe pointer decision; inspect server logs with operator access.",
            )
            event = _event_summary(status="failed", candidate=candidate)
            event.update({"at": _text(now), "problemCodes": [problem["code"]]})
            store.record_refresh_event("gear_release_refresh_failed", event)
            return {"status": "failed", "problems": [problem]}


def _run_from_environment(*, updated_by: str) -> dict[str, Any]:
    try:
        from .db import connect_postgres, database_config_from_env, postgres_only_runtime_enabled
        from .gear_release_shadow import run_release_shadow
        from .gear_release_store import GearReleaseStore
        from .gear_release_tool import expected_spec_pairs, runtime_dependency_revisions
        from .postgres_cache_store import PostgresCacheStore
        from .simulator_payload import simc_version_status
    except ImportError:
        from db import connect_postgres, database_config_from_env, postgres_only_runtime_enabled
        from gear_release_shadow import run_release_shadow
        from gear_release_store import GearReleaseStore
        from gear_release_tool import expected_spec_pairs, runtime_dependency_revisions
        from postgres_cache_store import PostgresCacheStore
        from simulator_payload import simc_version_status

    config = database_config_from_env()
    if not postgres_only_runtime_enabled(config):
        raise RuntimeError("release refresh requires the PostgreSQL-only runtime")
    connection_factory = lambda: connect_postgres(config.database_url)
    store = GearReleaseStore(connection_factory)
    shadow_store = PostgresCacheStore(connection_factory)
    simc_status = simc_version_status()
    simc_revision = _text(
        simc_status.get("sourceCommit")
        or simc_status.get("simcRuntimeRevision")
        or simc_status.get("localTag")
    )
    if not simc_revision:
        raise RuntimeError("current SimC runtime revision is unavailable")
    dependencies = runtime_dependency_revisions(simc_revision)
    expected = expected_spec_pairs()
    season_payload = shadow_store.get_active_season_payload()
    candidate_season_revision = _text(
        (season_payload if isinstance(season_payload, dict) else {}).get("seasonRevision")
        or (season_payload if isinstance(season_payload, dict) else {}).get("revision")
    )
    now = datetime.now(timezone.utc).isoformat()

    def shadow_runner(**kwargs):
        return run_release_shadow(
            shadow_store,
            expected_specs=kwargs["expected_specs"],
            gear_release_id=kwargs["gear_release_id"],
            community_release_id=kwargs["community_release_id"],
            simc_runtime_revision=kwargs["simc_runtime_revision"],
            expect_formal_active=True,
            allow_degraded_empty=True,
        )

    return run_release_refresh(
        store,
        expected_specs=expected,
        dependency_revisions=dependencies,
        now=now,
        updated_by=_text(updated_by) or "systemd-gear-release-refresh",
        candidate_season_revision=candidate_season_revision,
        lease=PostgresRefreshLease(connection_factory),
        candidate_builder=build_staging_candidates,
        shadow_runner=shadow_runner,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--updated-by", default="systemd-gear-release-refresh")
    args = parser.parse_args(argv)
    try:
        result = _run_from_environment(updated_by=args.updated_by)
    except Exception:
        result = {
            "status": "failed",
            "problems": [_bounded_problem(
                "REFRESH_ENVIRONMENT_FAILED",
                "Release refresh could not initialize safely; inspect server logs with operator access.",
            )],
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result.get("status") == "failed" else 0


__all__ = [
    "PostgresRefreshLease",
    "build_staging_candidates",
    "classify_gear_change",
    "classify_refresh_risk",
    "coverage_regressions",
    "run_release_refresh",
]


if __name__ == "__main__":
    raise SystemExit(main())

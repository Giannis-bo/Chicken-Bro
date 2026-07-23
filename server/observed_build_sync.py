#!/usr/bin/env python3
"""Bounded orchestration for immutable observed-player TemplateSets."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
from typing import Any, Callable

try:
    from .observed_build_compiler import (
        compile_with_postgres,
        prepare_observed_gear_with_postgres,
    )
    from .observed_build_ingest import (
        select_distinct_snapshot_winners,
        snapshot_candidates_from_raiderio,
    )
    from .observed_build_projection import (
        OBSERVED_BUILD_PROJECTION_SCHEMA_REVISION,
        build_dependency_vector,
    )
    from .observed_build_registry import slot_key, snapshot_check
    from .observed_build_template_set import (
        EXPECTED_TEMPLATE_SLOT_COUNT,
        build_template_set,
        promotion_decision,
    )
    from .postgres_cache_sync import (
        cache_store_from_env,
        sync_raiderio_cache_postgres,
    )
    from .simulator_payload import simc_version_status
    from .websim_payload import (
        expected_hero_tree_triplets,
        gear_resolver_runtime_authority,
    )
except ImportError:
    from observed_build_compiler import (
        compile_with_postgres,
        prepare_observed_gear_with_postgres,
    )
    from observed_build_ingest import (
        select_distinct_snapshot_winners,
        snapshot_candidates_from_raiderio,
    )
    from observed_build_projection import (
        OBSERVED_BUILD_PROJECTION_SCHEMA_REVISION,
        build_dependency_vector,
    )
    from observed_build_registry import slot_key, snapshot_check
    from observed_build_template_set import (
        EXPECTED_TEMPLATE_SLOT_COUNT,
        build_template_set,
        promotion_decision,
    )
    from postgres_cache_sync import (
        cache_store_from_env,
        sync_raiderio_cache_postgres,
    )
    from simulator_payload import simc_version_status
    from websim_payload import (
        expected_hero_tree_triplets,
        gear_resolver_runtime_authority,
    )


OBSERVED_BUILD_SYNC_SCHEMA_REVISION = "observed-build-registry-sync-v1"
OBSERVED_BUILD_SYNC_STATE_KEY = "observed_build_registry_sync"
_SCOPES = {"candidate", "retail"}
_SAFE_TOKEN = re.compile(r"[^a-zA-Z0-9_.:-]+")


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


def _expected_slots() -> list[dict[str, str]]:
    return [
        {
            "classKey": class_key,
            "specKey": spec_key,
            "heroKey": hero_key,
            "scenarioKey": "mythic_plus",
        }
        for class_key, spec_key, hero_key in (
            triplet.split(":")
            for triplet in expected_hero_tree_triplets()
        )
    ]


def _dependency_hash(dependency_vector: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(
        _canonical_bytes(dependency_vector)
    ).hexdigest()


def _source_run_id(payload: dict[str, Any], checked_at: str) -> str:
    explicit = _text(
        payload.get("sourceRunId")
        or payload.get("scanRunId")
    )
    if explicit:
        return explicit[:512]
    identity = {
        "checkedAt": payload.get("checkedAt") or checked_at,
        "seasonSlug": payload.get("seasonSlug"),
        "sourceStatus": payload.get("sourceStatus") or payload.get("status"),
        "templates": [
            {
                "id": item.get("id"),
                "classKey": item.get("classKey"),
                "specKey": item.get("specKey"),
                "heroKey": item.get("heroKey"),
                "sourceIdentity": (
                    (item.get("payload") or {}).get("raiderio") or {}
                ).get("sourceIdentity"),
            }
            for item in payload.get("communityTemplates") or []
            if isinstance(item, dict)
        ],
    }
    return (
        "observed-build-source:sha256:"
        + hashlib.sha256(_canonical_bytes(identity)).hexdigest()
    )


def _checked_since(checked_at: str) -> str:
    raw = _text(checked_at)
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        value = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError("checked_at must be an ISO-8601 timestamp") from error
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    try:
        hours = int(
            os.environ.get("WOW_OBSERVED_BUILD_STAGING_TTL_HOURS", "48")
        )
    except (TypeError, ValueError, OverflowError):
        hours = 48
    hours = max(1, min(168, hours))
    return (
        (value.astimezone(timezone.utc) - timedelta(hours=hours))
        .isoformat()
        .replace("+00:00", "Z")
    )


def _safe_problem(
    problem: Any,
    *,
    slot_key_value: str = "",
    default_code: str = "observed_build_sync_blocked",
) -> dict[str, Any]:
    value = problem if isinstance(problem, dict) else {}
    code = _SAFE_TOKEN.sub(
        "_",
        _text(value.get("code") or default_code),
    )[:120]
    stage = _SAFE_TOKEN.sub(
        "_",
        _text(value.get("stage") or "sync"),
    )[:80]
    output: dict[str, Any] = {
        "code": code or default_code,
        "stage": stage or "sync",
    }
    key = _text(slot_key_value or value.get("slotKey"))
    if key:
        output["slotKey"] = key[:240]
    count = value.get("count")
    if isinstance(count, int) and not isinstance(count, bool):
        output["count"] = max(0, count)
    return output


def _active_bundle(store: Any, scope: str) -> dict[str, Any]:
    bundle = store.load_active_records(scope)
    return bundle if isinstance(bundle, dict) else {}


def _active_snapshot_ids(active_set: dict[str, Any] | None) -> dict[str, str]:
    return {
        _text(entry.get("slotKey")): _text(entry.get("snapshotId"))
        for entry in (active_set or {}).get("entries") or []
        if isinstance(entry, dict)
    }


def _gear_complete_specs(entries: list[dict[str, Any]]) -> int:
    by_spec: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        slot = entry.get("slot") if isinstance(entry.get("slot"), dict) else {}
        spec_id = f"{_text(slot.get('classKey'))}:{_text(slot.get('specKey'))}"
        by_spec.setdefault(spec_id, []).append(entry)
    return sum(
        len(spec_entries) == 2
        and all(
            entry.get("status") in {"verified", "stale_lkg"}
            and _text(entry.get("projectionId"))
            and _text(entry.get("sourceIdentity"))
            for entry in spec_entries
        )
        and len(
            {
                _text(entry.get("sourceIdentity"))
                for entry in spec_entries
            }
        )
        == 2
        for spec_entries in by_spec.values()
    )


def _coverage(template_set: dict[str, Any]) -> dict[str, int]:
    counts = (
        template_set.get("counts")
        if isinstance(template_set.get("counts"), dict)
        else {}
    )
    entries = [
        entry
        for entry in template_set.get("entries") or []
        if isinstance(entry, dict)
    ]
    return {
        "total": EXPECTED_TEMPLATE_SLOT_COUNT,
        "verified": int(counts.get("verified") or 0),
        "stale_lkg": int(counts.get("stale_lkg") or 0),
        "pending_collection": int(
            counts.get("pending_collection") or 0
        ),
        "gearCompleteSpecs": _gear_complete_specs(entries),
    }


def _audit_result(
    *,
    scope: str,
    pointer: dict[str, Any],
    active_set: dict[str, Any],
) -> dict[str, Any]:
    problems = [
        _safe_problem(
            entry.get("problem"),
            slot_key_value=entry.get("slotKey"),
        )
        for entry in active_set.get("entries") or []
        if isinstance(entry, dict) and entry.get("status") != "verified"
    ][:12]
    return {
        "schemaRevision": OBSERVED_BUILD_SYNC_SCHEMA_REVISION,
        "scope": scope,
        "sourceRunId": _text(active_set.get("sourceRunId")),
        "sourceStatus": "audit",
        "coverage": (
            _coverage(active_set)
            if active_set
            else {
                "total": EXPECTED_TEMPLATE_SLOT_COUNT,
                "verified": 0,
                "stale_lkg": 0,
                "pending_collection": EXPECTED_TEMPLATE_SLOT_COUNT,
                "gearCompleteSpecs": 0,
            }
        ),
        "candidateTemplateSetId": _text(
            active_set.get("templateSetId")
        ),
        "promotion": {
            "action": "no_op",
            "reason": "read_only_audit",
        },
        "pointerBefore": _canonical(pointer),
        "pointerAfter": _canonical(pointer),
        "problems": problems,
    }


def run_observed_build_sync(
    store: Any,
    *,
    scope: str,
    refresh_source: bool,
    allow_promotion: bool,
    source_fetcher: Callable[[], dict[str, Any]] | None,
    compiler: Callable[[dict[str, Any]], dict[str, Any]] | None,
    checked_at: str,
    audit: bool = False,
    allow_controlled_cutover: bool | None = None,
) -> dict[str, Any]:
    """Run the fixed observed-build stage sequence and optionally move a pointer."""

    normalized_scope = _text(scope)
    if normalized_scope not in _SCOPES:
        raise ValueError("scope must be candidate or retail")
    checked_at = _text(checked_at)
    if not checked_at:
        raise ValueError("checked_at is required")

    active_bundle = _active_bundle(store, normalized_scope)
    pointer_before = (
        active_bundle.get("pointer")
        if isinstance(active_bundle.get("pointer"), dict)
        else {}
    )
    active_set = (
        active_bundle.get("templateSet")
        if isinstance(active_bundle.get("templateSet"), dict)
        else {}
    )
    if audit:
        return _audit_result(
            scope=normalized_scope,
            pointer=pointer_before,
            active_set=active_set,
        )
    if not callable(source_fetcher) or not callable(compiler):
        raise ValueError("source_fetcher and compiler are required")
    dependency_vector = getattr(compiler, "dependency_vector", None)
    if not isinstance(dependency_vector, dict):
        raise ValueError("compiler.dependency_vector is required")
    dependency_vector = _canonical(dependency_vector)

    payload = source_fetcher()
    if not isinstance(payload, dict):
        raise ValueError("source_fetcher must return a Raider.IO payload")
    source_status = _text(
        payload.get("sourceStatus") or payload.get("status") or "blocked"
    )
    source_run_id = _source_run_id(payload, checked_at)
    extracted = snapshot_candidates_from_raiderio(payload)
    winners = select_distinct_snapshot_winners(
        extracted.get("candidatesBySlot") or {}
    )
    expected_slots = _expected_slots()
    if len(expected_slots) != EXPECTED_TEMPLATE_SLOT_COUNT:
        raise ValueError("observed-build slot contract must contain 80 slots")

    active_snapshot_ids = _active_snapshot_ids(active_set or None)
    active_records = {
        _text((record.get("entry") or {}).get("slotKey")): record
        for record in active_bundle.get("records") or []
        if isinstance(record, dict)
    }
    candidates: dict[str, dict[str, Any]] = {}
    problems: list[dict[str, Any]] = []
    template_set_problems: dict[str, dict[str, Any]] = {}
    problems_by_slot = extracted.get("problemsBySlot")
    problems_by_slot = (
        problems_by_slot if isinstance(problems_by_slot, dict) else {}
    )
    snapshots_to_compile: dict[str, dict[str, Any]] = {}
    for key, snapshot in winners.items():
        active_record = active_records.get(key)
        active_projection = (
            active_record.get("projection")
            if isinstance(active_record, dict)
            and isinstance(active_record.get("projection"), dict)
            else {}
        )
        if (
            active_snapshot_ids.get(key) == snapshot.get("snapshotId")
            and active_projection.get("dependencyVector")
            == dependency_vector
            and active_projection.get("status") == "verified"
            and active_projection.get("importable") is True
        ):
            candidates[key] = _canonical(active_projection)
        else:
            snapshots_to_compile[key] = snapshot

    prepare = getattr(compiler, "prepare", None)
    if callable(prepare):
        prepare(
            [
                snapshots_to_compile[key]
                for key in sorted(snapshots_to_compile)
            ]
        )

    for slot in expected_slots:
        key = slot_key(slot)
        snapshot = winners.get(key)
        if snapshot is None:
            slot_problems = [
                problem
                for problem in problems_by_slot.get(key) or []
                if isinstance(problem, dict)
            ]
            problem = _safe_problem(
                slot_problems[0] if slot_problems else None,
                slot_key_value=key,
                default_code="snapshot_candidate_missing",
            )
            store.record_snapshot_check(
                snapshot_check(
                    run_id=source_run_id,
                    slot=slot,
                    checked_at=checked_at,
                    status="failed",
                    problem=problem,
                )
            )
            problems.append(problem)
            template_set_problems[key] = problem
            continue
        sealed_snapshot = store.seal_snapshot(snapshot)
        previous_snapshot_id = active_snapshot_ids.get(key)
        status = (
            "unchanged"
            if previous_snapshot_id == sealed_snapshot["snapshotId"]
            else "changed"
            if previous_snapshot_id
            else "captured"
        )
        store.record_snapshot_check(
            snapshot_check(
                run_id=source_run_id,
                slot=slot,
                checked_at=checked_at,
                status=status,
                snapshot_id=sealed_snapshot["snapshotId"],
            )
        )
        if key in snapshots_to_compile:
            projection = compiler(sealed_snapshot)
            sealed_projection = store.seal_projection(projection)
            candidates[key] = sealed_projection
            if sealed_projection.get("status") != "verified":
                problems.extend(
                    _safe_problem(problem, slot_key_value=key)
                    for problem in sealed_projection.get("problems") or []
                )

    if not active_set:
        staging = store.load_latest_verified_projections(
            _dependency_hash(dependency_vector),
            _checked_since(checked_at),
        )
        for key, projection in (staging or {}).items():
            if key not in candidates and isinstance(projection, dict):
                candidates[key] = projection

    candidate_set = build_template_set(
        expected_slots=expected_slots,
        candidates_by_slot=candidates,
        active_set=active_set or None,
        dependency_vector=dependency_vector,
        source_run_id=source_run_id,
        problems_by_slot=template_set_problems,
    )
    candidate_set = store.seal_template_set(candidate_set)
    promotion = promotion_decision(
        active_set=active_set or None,
        candidate_set=candidate_set,
    )
    pointer_after = _canonical(pointer_before)
    action = _text(promotion.get("action"))
    controlled_allowed = (
        bool(allow_promotion)
        if allow_controlled_cutover is None
        else bool(allow_controlled_cutover)
    )
    should_apply = bool(allow_promotion) and (
        action == "auto_promote"
        or (action == "controlled_cutover" and controlled_allowed)
    )
    if should_apply:
        pointer_after = store.compare_and_swap_pointer(
            normalized_scope,
            int(pointer_before.get("generation") or 0),
            candidate_set["templateSetId"],
            "observed-build-sync",
        )
    promotion = {
        **_canonical(promotion),
        "applied": should_apply,
    }
    problems.extend(
        _safe_problem(problem)
        for problem in promotion.get("problems") or []
    )
    result = {
        "schemaRevision": OBSERVED_BUILD_SYNC_SCHEMA_REVISION,
        "scope": normalized_scope,
        "sourceRunId": source_run_id,
        "sourceStatus": source_status,
        "refreshSource": bool(refresh_source),
        "coverage": _coverage(candidate_set),
        "candidateTemplateSetId": candidate_set["templateSetId"],
        "promotion": promotion,
        "pointerBefore": _canonical(pointer_before),
        "pointerAfter": _canonical(pointer_after),
        "problems": problems[:12],
    }
    store.save_sync_state(
        OBSERVED_BUILD_SYNC_STATE_KEY,
        result,
        checked_at,
    )
    return result


class _RuntimeStore:
    def __init__(self, cache_store: Any):
        self.cache_store = cache_store
        self.registry = cache_store._observed_build_store

    def __getattr__(self, name: str) -> Any:
        if name == "save_sync_state":
            return self.cache_store.save_sync_state
        return getattr(self.registry, name)


class _PostgresCompiler:
    def __init__(
        self,
        cache_store: Any,
        dependency_vector: dict[str, Any],
        simc_runtime_revision: str,
    ):
        self.cache_store = cache_store
        self.dependency_vector = _canonical(dependency_vector)
        self.simc_runtime_revision = simc_runtime_revision
        self._prepared = False

    def prepare(self, snapshots: list[dict[str, Any]]) -> None:
        prepare_observed_gear_with_postgres(
            self.cache_store,
            snapshots,
        )
        self._prepared = True

    def __call__(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        return compile_with_postgres(
            self.cache_store,
            snapshot,
            self.dependency_vector,
            self.simc_runtime_revision,
            gear_prepared=self._prepared,
        )


def _current_simc_runtime_revision() -> str:
    status = simc_version_status()
    for key in (
        "sourceCommit",
        "simcRuntimeRevision",
        "localTag",
    ):
        value = _text(status.get(key))
        if value:
            return value
    raise RuntimeError("SimulationCraft runtime revision is unavailable")


def _current_dependency_vector(
    cache_store: Any,
    simc_runtime_revision: str,
) -> dict[str, str]:
    binding = cache_store._active_manifest_binding_for_authority()
    binding = binding if isinstance(binding, dict) else {}
    manifest = (
        binding.get("manifest")
        if isinstance(binding.get("manifest"), dict)
        else {}
    )
    expected_slots = _expected_slots()
    first_slot = expected_slots[0]
    runtime = gear_resolver_runtime_authority(
        first_slot["classKey"],
        first_slot["specKey"],
        simc_runtime_revision=simc_runtime_revision,
    )
    revisions = (
        runtime.get("dependencyRevisions")
        if isinstance(runtime.get("dependencyRevisions"), dict)
        else {}
    )
    return build_dependency_vector(
        season_revision=_text(manifest.get("seasonRevision")),
        talent_catalog_revision=_text(
            manifest.get("talentCatalogRevision")
        ),
        gear_release_id=_text(manifest.get("gearCatalogReleaseId")),
        gear_rule_revision=_text(revisions.get("gearRuleRevision")),
        resolver_contract_revision=_text(
            revisions.get("resolverContractRevision")
        ),
        serializer_revision=_text(revisions.get("serializerRevision")),
        simc_runtime_revision=simc_runtime_revision,
        selection_schema_revision=_text(
            revisions.get("selectionSchemaRevision")
        ),
        projection_schema_revision=(
            OBSERVED_BUILD_PROJECTION_SCHEMA_REVISION
        ),
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _truthy_env(name: str) -> bool:
    return _text(os.environ.get(name)).lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refresh or audit the observed-build Registry.",
    )
    parser.add_argument(
        "--scope",
        required=True,
        choices=sorted(_SCOPES),
    )
    parser.add_argument("--refresh-source", action="store_true")
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.audit and (args.refresh_source or args.promote):
        raise SystemExit(
            "--audit cannot be combined with --refresh-source or --promote"
        )
    if (
        args.scope == "retail"
        and args.promote
        and not _truthy_env("WOW_OBSERVED_BUILD_RETAIL_CUTOVER")
    ):
        raise SystemExit(
            "retail promotion requires WOW_OBSERVED_BUILD_RETAIL_CUTOVER=1"
        )

    cache_store = cache_store_from_env()
    runtime_store = _RuntimeStore(cache_store)
    checked_at = _utc_now()
    if args.audit:
        result = run_observed_build_sync(
            runtime_store,
            scope=args.scope,
            refresh_source=False,
            allow_promotion=False,
            source_fetcher=None,
            compiler=None,
            checked_at=checked_at,
            audit=True,
        )
    else:
        pointer = runtime_store.load_pointer(args.scope)
        simc_runtime_revision = _current_simc_runtime_revision()
        dependency_vector = _current_dependency_vector(
            cache_store,
            simc_runtime_revision,
        )
        compiler = _PostgresCompiler(
            cache_store,
            dependency_vector,
            simc_runtime_revision,
        )

        def source_fetcher() -> dict[str, Any]:
            if args.refresh_source:
                return sync_raiderio_cache_postgres(
                    force=True,
                    store=cache_store,
                )
            return cache_store.get_raiderio_payload()

        result = run_observed_build_sync(
            runtime_store,
            scope=args.scope,
            refresh_source=args.refresh_source,
            allow_promotion=bool(args.promote or pointer),
            allow_controlled_cutover=bool(args.promote),
            source_fetcher=source_fetcher,
            compiler=compiler,
            checked_at=checked_at,
        )
    output = json.dumps(
        result,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "OBSERVED_BUILD_SYNC_SCHEMA_REVISION",
    "OBSERVED_BUILD_SYNC_STATE_KEY",
    "main",
    "run_observed_build_sync",
)

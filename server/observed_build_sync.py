#!/usr/bin/env python3
"""Bounded orchestration for immutable observed-player TemplateSets."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import itertools
import json
import os
import re
from typing import Any, Callable

try:
    from .observed_build_compiler import (
        compile_with_postgres,
        load_observed_gear_compile_context_with_postgres,
        observed_talent_projection_runtime_ready_with_postgres,
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
        resolve_community_talent_structured_loadout,
    )
except ImportError:
    from observed_build_compiler import (
        compile_with_postgres,
        load_observed_gear_compile_context_with_postgres,
        observed_talent_projection_runtime_ready_with_postgres,
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
        resolve_community_talent_structured_loadout,
    )


OBSERVED_BUILD_SYNC_SCHEMA_REVISION = "observed-build-registry-sync-v1"
OBSERVED_BUILD_SYNC_STATE_KEY = "observed_build_registry_sync"
_SCOPES = {"candidate", "retail"}
_SAFE_TOKEN = re.compile(r"[^a-zA-Z0-9_.:-]+")
_CANDIDATE_PLAYER_LIMIT_PER_SLOT = 8
_CANDIDATE_SNAPSHOT_LIMIT_PER_PLAYER = 2


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


def _canonical_hero_resolver(
    cache_store: Any,
) -> Callable[[str, str, list[dict[str, Any]], str], str]:
    """Resolve the selected Hero nodes through one cached PG talent view."""

    authority_cache: dict[tuple[str, str], dict[Any, Any]] = {}

    class AuthorityView:
        def community_talent_authority_index(
            self,
            class_key: str,
            spec_key: str,
        ) -> dict[Any, Any]:
            key = (_text(class_key), _text(spec_key))
            if key not in authority_cache:
                authority = cache_store.community_talent_authority_index(
                    *key
                )
                authority_cache[key] = (
                    authority if isinstance(authority, dict) else {}
                )
            return authority_cache[key]

    authority_view = AuthorityView()

    def resolve(
        class_key: str,
        spec_key: str,
        loadout: list[dict[str, Any]],
        declared_hero: str,
    ) -> str:
        del declared_hero
        resolved = resolve_community_talent_structured_loadout(
            authority_view,
            {
                "classKey": class_key,
                "specKey": spec_key,
                "heroKey": "",
                "loadout": loadout,
            },
        )
        if (
            not isinstance(resolved, dict)
            or resolved.get("errors")
            or not resolved.get("selectedNodes")
        ):
            return ""
        return _text(resolved.get("heroKey"))

    return resolve


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


def _active_lkg_recomposition_snapshots(
    active_records: dict[str, dict[str, Any]],
    lkg_slots: set[str],
) -> dict[str, dict[str, Any]]:
    """Return only same-slot sealed snapshots selected as LKG fallbacks.

    Active snapshots are never source-ranking candidates.  Once selection has
    already chosen an active same-slot LKG, however, its immutable snapshot can
    be recompiled against newly completed evidence without changing the winner
    selection or allowing it to displace a current ranked candidate.
    """

    snapshots: dict[str, dict[str, Any]] = {}
    for key in sorted(lkg_slots):
        record = active_records.get(key)
        entry = record.get("entry") if isinstance(record, dict) else {}
        snapshot = record.get("snapshot") if isinstance(record, dict) else {}
        if not isinstance(entry, dict) or not isinstance(snapshot, dict):
            continue
        try:
            snapshot_key = slot_key(snapshot.get("slot"))
        except ValueError:
            continue
        source = (
            snapshot.get("source")
            if isinstance(snapshot.get("source"), dict)
            else {}
        )
        if (
            snapshot_key != key
            or _text(snapshot.get("snapshotId"))
            != _text(entry.get("snapshotId"))
            or _text(source.get("sourceIdentity"))
            != _text(entry.get("sourceIdentity"))
        ):
            continue
        snapshots[key] = _canonical(snapshot)
    return snapshots


def _bounded_candidate_snapshots(
    candidates_by_slot: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Keep two exact snapshots for each of eight highest-ranked players."""

    bounded: dict[str, list[dict[str, Any]]] = {}
    for key in sorted(candidates_by_slot):
        snapshot_counts_by_identity: dict[str, int] = {}
        selected: list[dict[str, Any]] = []
        for snapshot in candidates_by_slot.get(key) or []:
            identity = _text(
                (snapshot.get("source") or {}).get("sourceIdentity")
            )
            if not identity:
                continue
            if identity not in snapshot_counts_by_identity:
                if (
                    len(snapshot_counts_by_identity)
                    >= _CANDIDATE_PLAYER_LIMIT_PER_SLOT
                ):
                    continue
                snapshot_counts_by_identity[identity] = 0
            if (
                snapshot_counts_by_identity[identity]
                >= _CANDIDATE_SNAPSHOT_LIMIT_PER_PLAYER
            ):
                continue
            selected.append(snapshot)
            snapshot_counts_by_identity[identity] += 1
        if selected:
            bounded[key] = selected
    return bounded


def _select_importable_winners(
    candidates_by_slot: dict[str, list[dict[str, Any]]],
    eligible_snapshot_ids: set[str],
    active_set: dict[str, Any] | None,
    dependency_vector: dict[str, Any],
    *,
    allow_dependency_recomposition: bool = False,
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    """Prefer a fully new distinct pair, then use same-slot LKG per failed slot."""

    winners = select_distinct_snapshot_winners(
        candidates_by_slot,
        eligible_snapshot_ids=eligible_snapshot_ids,
    )
    active_entries = {
        _text(entry.get("slotKey")): entry
        for entry in (active_set or {}).get("entries") or []
        if isinstance(entry, dict)
    }
    allow_lkg = (
        bool(active_set)
        and (
            active_set.get("dependencyVector") == dependency_vector
            or allow_dependency_recomposition
        )
    )
    slots_by_spec: dict[str, list[str]] = {}
    for slot in _expected_slots():
        key = slot_key(slot)
        parts = _text(key).split(":")
        if len(parts) >= 2:
            slots_by_spec.setdefault(":".join(parts[:2]), []).append(key)

    lkg_slots: set[str] = set()
    for spec_id in sorted(slots_by_spec):
        slot_keys = sorted(set(slots_by_spec[spec_id]))
        if len(slot_keys) != 2 or all(key in winners for key in slot_keys):
            continue
        for key in slot_keys:
            winners.pop(key, None)
        options_by_slot: list[list[dict[str, Any]]] = []
        for key in slot_keys:
            slot_candidates = candidates_by_slot.get(key) or []
            options = [
                {
                    "kind": "candidate",
                    "identity": _text(
                        (snapshot.get("source") or {}).get(
                            "sourceIdentity"
                        )
                    ),
                    "snapshot": snapshot,
                    "rank": index,
                }
                for index, snapshot in enumerate(slot_candidates)
                if _text(snapshot.get("snapshotId"))
                in eligible_snapshot_ids
            ]
            active_entry = active_entries.get(key)
            if (
                allow_lkg
                and isinstance(active_entry, dict)
                and active_entry.get("status")
                in {"verified", "stale_lkg"}
                and _text(active_entry.get("sourceIdentity"))
            ):
                options.append(
                    {
                        "kind": "lkg",
                        "identity": _text(
                            active_entry.get("sourceIdentity")
                        ),
                        "snapshot": None,
                        "rank": len(slot_candidates),
                    }
                )
            options_by_slot.append(options)
        combinations = [
            pair
            for pair in itertools.product(*options_by_slot)
            if pair[0]["identity"] != pair[1]["identity"]
        ]
        if not combinations:
            used_identities: set[str] = set()
            for key, options in zip(slot_keys, options_by_slot):
                candidate = next(
                    (
                        option
                        for option in options
                        if option["kind"] == "candidate"
                        and option["identity"] not in used_identities
                    ),
                    None,
                )
                if candidate:
                    winners[key] = candidate["snapshot"]
                    used_identities.add(candidate["identity"])
            continue
        selected = min(
            combinations,
            key=lambda pair: (
                sum(option["kind"] == "lkg" for option in pair),
                sum(int(option["rank"]) for option in pair),
                tuple(option["identity"] for option in pair),
            ),
        )
        for key, option in zip(slot_keys, selected):
            if option["kind"] == "candidate":
                winners[key] = option["snapshot"]
            else:
                lkg_slots.add(key)
    return winners, lkg_slots


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
    hero_resolver: Callable[
        [str, str, list[dict[str, Any]], str],
        str,
    ]
    | None = None,
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
    extracted = snapshot_candidates_from_raiderio(
        payload,
        hero_resolver=hero_resolver,
    )
    candidate_snapshots_by_slot = (
        extracted.get("candidatesBySlot")
        if isinstance(extracted.get("candidatesBySlot"), dict)
        else {}
    )
    candidate_snapshots_by_slot = _bounded_candidate_snapshots(
        candidate_snapshots_by_slot
    )
    problems_by_slot = extracted.get("problemsBySlot")
    problems_by_slot = (
        problems_by_slot if isinstance(problems_by_slot, dict) else {}
    )
    del extracted
    del payload
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
    projections_by_snapshot_id: dict[str, dict[str, Any]] = {}
    snapshots_to_compile: dict[str, dict[str, Any]] = {}
    for key, snapshots in candidate_snapshots_by_slot.items():
        active_record = active_records.get(key)
        active_projection = (
            active_record.get("projection")
            if isinstance(active_record, dict)
            and isinstance(active_record.get("projection"), dict)
            else {}
        )
        for snapshot in snapshots:
            snapshot_id = _text(snapshot.get("snapshotId"))
            if not snapshot_id:
                continue
            if (
                active_snapshot_ids.get(key) == snapshot_id
                and active_projection.get("dependencyVector")
                == dependency_vector
                and active_projection.get("status") == "verified"
                and active_projection.get("importable") is True
                and (
                    not callable(getattr(compiler, "can_reuse", None))
                    or compiler.can_reuse(
                        snapshot,
                        active_projection,
                    )
                )
            ):
                projections_by_snapshot_id[snapshot_id] = _canonical(
                    active_projection
                )
            else:
                snapshots_to_compile[snapshot_id] = snapshot

    def compile_snapshots(
        snapshots_by_id: dict[str, dict[str, Any]],
    ) -> None:
        if not snapshots_by_id:
            return
        prepare = getattr(compiler, "prepare", None)
        if callable(prepare):
            prepare(
                [
                    snapshots_by_id[snapshot_id]
                    for snapshot_id in sorted(snapshots_by_id)
                ]
            )
        for snapshot_id in sorted(snapshots_by_id):
            sealed_snapshot = store.seal_snapshot(
                snapshots_by_id[snapshot_id]
            )
            projection = compiler(sealed_snapshot)
            projections_by_snapshot_id[snapshot_id] = (
                store.seal_projection(projection)
            )

    compile_snapshots(snapshots_to_compile)

    eligible_snapshot_ids = {
        snapshot_id
        for snapshot_id, projection in projections_by_snapshot_id.items()
        if projection.get("status") == "verified"
        and projection.get("importable") is True
    }
    winners, lkg_slots = _select_importable_winners(
        candidate_snapshots_by_slot,
        eligible_snapshot_ids,
        active_set or None,
        dependency_vector,
        allow_dependency_recomposition=(
            normalized_scope == "candidate"
            and bool(allow_controlled_cutover)
        ),
    )
    recomposition_by_slot = _active_lkg_recomposition_snapshots(
        active_records,
        lkg_slots,
    )
    recomposition_by_id = {
        _text(snapshot.get("snapshotId")): snapshot
        for snapshot in recomposition_by_slot.values()
        if _text(snapshot.get("snapshotId"))
    }
    compile_snapshots(recomposition_by_id)
    for key, snapshot in recomposition_by_slot.items():
        snapshot_id = _text(snapshot.get("snapshotId"))
        projection = projections_by_snapshot_id.get(snapshot_id)
        active_record = active_records.get(key)
        active_entry = (
            active_record.get("entry")
            if isinstance(active_record, dict)
            else {}
        )
        source = (
            snapshot.get("source")
            if isinstance(snapshot.get("source"), dict)
            else {}
        )
        if (
            isinstance(projection, dict)
            and projection.get("status") == "verified"
            and projection.get("importable") is True
            and isinstance(active_entry, dict)
            and _text(source.get("sourceIdentity"))
            == _text(active_entry.get("sourceIdentity"))
            and _text(projection.get("sourceIdentity"))
            == _text(active_entry.get("sourceIdentity"))
        ):
            winners[key] = snapshot
            lkg_slots.discard(key)

    for slot in expected_slots:
        key = slot_key(slot)
        snapshot = winners.get(key)
        if snapshot is None:
            blocked_projection = next(
                (
                    projections_by_snapshot_id.get(
                        _text(candidate.get("snapshotId"))
                    )
                    for candidate in (
                        candidate_snapshots_by_slot.get(key) or []
                    )
                    if isinstance(
                        projections_by_snapshot_id.get(
                            _text(candidate.get("snapshotId"))
                        ),
                        dict,
                    )
                    and projections_by_snapshot_id[
                        _text(candidate.get("snapshotId"))
                    ].get("status")
                    != "verified"
                ),
                None,
            )
            slot_problems = [
                problem
                for problem in problems_by_slot.get(key) or []
                if isinstance(problem, dict)
            ]
            blocked_problems = (
                blocked_projection.get("problems")
                if isinstance(blocked_projection, dict)
                and isinstance(
                    blocked_projection.get("problems"),
                    list,
                )
                else []
            )
            problem = _safe_problem(
                (
                    blocked_problems[0]
                    if blocked_problems
                    else slot_problems[0]
                    if slot_problems
                    else {
                        "code": (
                            "candidate_pair_not_importable"
                            if key in lkg_slots
                            else "snapshot_candidate_missing"
                        ),
                        "stage": "selection",
                    }
                ),
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
            if isinstance(blocked_projection, dict):
                candidates[key] = blocked_projection
            continue
        sealed_snapshot = snapshot
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
        candidates[key] = projections_by_snapshot_id[
            _text(sealed_snapshot.get("snapshotId"))
        ]

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
        self._gear_release_context = None
        self._talent_runtime_context_cache = {}

    def prepare(self, snapshots: list[dict[str, Any]]) -> None:
        prepare_observed_gear_with_postgres(
            self.cache_store,
            snapshots,
        )
        self._gear_release_context = (
            load_observed_gear_compile_context_with_postgres(
                self.cache_store,
                snapshots,
            )
        )
        self._prepared = True

    def can_reuse(
        self,
        snapshot: dict[str, Any],
        projection: dict[str, Any],
    ) -> bool:
        return observed_talent_projection_runtime_ready_with_postgres(
            self.cache_store,
            snapshot,
            projection,
            self._talent_runtime_context_cache,
        )

    def __call__(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        return compile_with_postgres(
            self.cache_store,
            snapshot,
            self.dependency_vector,
            self.simc_runtime_revision,
            gear_prepared=self._prepared,
            gear_release_context=self._gear_release_context,
            talent_runtime_context_cache=(
                self._talent_runtime_context_cache
            ),
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
            hero_resolver=_canonical_hero_resolver(cache_store),
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

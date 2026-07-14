#!/usr/bin/env python3
"""Explicit inactive release builder for equipment simulator Phase 4B."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import subprocess
from typing import Any, Callable, Iterable, Mapping

try:
    from . import gear_release, gear_release_shadow, gear_resolver, gear_socket_authority
    from .db import connect_postgres, database_config_from_env, postgres_only_runtime_enabled
    from .gear_release_store import (
        CandidateGearAuthorityIndex,
        GearReleaseIntegrityError,
        GearReleaseStore,
        build_candidate_authority_context,
        community_rows_summary,
        gear_snapshot_summary,
    )
    from .websim_payload import WOW_CLASSES, gear_resolver_runtime_authority, normalize_slot
    from .postgres_cache_store import PostgresCacheStore
except ImportError:
    import gear_release
    import gear_release_shadow
    import gear_resolver
    import gear_socket_authority
    from db import connect_postgres, database_config_from_env, postgres_only_runtime_enabled
    from gear_release_store import (
        CandidateGearAuthorityIndex,
        GearReleaseIntegrityError,
        GearReleaseStore,
        build_candidate_authority_context,
        community_rows_summary,
        gear_snapshot_summary,
    )
    from websim_payload import WOW_CLASSES, gear_resolver_runtime_authority, normalize_slot
    from postgres_cache_store import PostgresCacheStore


CAPABILITY_REVISION = "gear-capability-matrix-v1"
_SIMC_SOCKET_PROBE_TIMEOUT_SECONDS = 30
_SIMC_SOCKET_PROBE_MAX_CHARS = 4 * 1024 * 1024
_SIMC_SOCKET_PROBE_FAILURE = "SimC socket probe failed"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _canonical(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str))


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _socket_probe_digest(socket_bonus_minimums: Mapping[str, Any]) -> str:
    return _canonical_digest({
        "socketBonusMinimums": {
            _text(bonus_id): _canonical(minimum)
            for bonus_id, minimum in socket_bonus_minimums.items()
            if _text(bonus_id)
        },
    })


def _socket_fact_value(row: dict[str, Any], field: str) -> dict[str, Any]:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    value = payload.get(field) if isinstance(payload.get(field), dict) else row.get(field)
    return value if isinstance(value, dict) else {}


def _materialized_socket_fact_digest(snapshot: dict[str, Any]) -> str:
    items = [
        {
            "itemId": _text(row.get("itemId")),
            "socketCount": _int(_socket_fact_value(row, "baseCapabilities").get("socketCount")),
            "socketEvidence": _canonical(_socket_fact_value(row, "socketEvidence")),
        }
        for row in snapshot.get("items") or []
        if isinstance(row, dict)
    ]
    variants = [
        {
            "variantId": _text(row.get("variantId")),
            "itemId": _text(row.get("itemId")),
            "variantKey": _text(row.get("variantKey")),
            "socketCount": _int(
                _socket_fact_value(row, "capabilityOverrides").get("socketCount")
            ),
            "socketEvidence": _canonical(_socket_fact_value(row, "socketEvidence")),
        }
        for row in snapshot.get("variants") or []
        if isinstance(row, dict)
    ]
    items.sort(key=lambda row: row["itemId"])
    variants.sort(key=lambda row: (row["variantId"], row["itemId"], row["variantKey"]))
    return _canonical_digest({"items": items, "variants": variants})


def _project_socket_facts_into_release_payloads(snapshot: dict[str, Any]) -> dict[str, Any]:
    projected = _canonical(snapshot)
    for category, fields in (
        ("items", ("baseCapabilities", "socketEvidence")),
        ("variants", ("capabilityOverrides", "socketEvidence")),
    ):
        rows = [row for row in projected.get(category) or [] if isinstance(row, dict)]
        if any(not isinstance(row.get(field), dict) for row in rows for field in fields):
            raise GearReleaseIntegrityError("materialized socket facts are incomplete")
        for row in rows:
            payload = _canonical(row.get("payload") if isinstance(row.get("payload"), dict) else {})
            for field in fields:
                materialized = row.pop(field)
                if field in {"baseCapabilities", "capabilityOverrides"}:
                    existing = payload.get(field) if isinstance(payload.get(field), dict) else {}
                    payload[field] = {**existing, **materialized}
                else:
                    payload[field] = materialized
            row["payload"] = payload
    return projected


def load_simc_socket_bonus_minimums(
    simc_binary: str,
    *,
    runner=subprocess.run,
) -> dict[str, int]:
    """Run the bounded candidate-only SimC bonus probe and parse socket effects."""

    binary = _text(simc_binary)
    if not binary:
        raise RuntimeError(_SIMC_SOCKET_PROBE_FAILURE)
    try:
        result = runner(
            [binary, "show_bonus_ids=1"],
            capture_output=True,
            text=True,
            timeout=_SIMC_SOCKET_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception:
        raise RuntimeError(_SIMC_SOCKET_PROBE_FAILURE) from None
    returncode = getattr(result, "returncode", None)
    if type(returncode) is not int or returncode != 0:
        raise RuntimeError(_SIMC_SOCKET_PROBE_FAILURE)
    output = getattr(result, "stdout", "")
    if not isinstance(output, str) or len(output) > _SIMC_SOCKET_PROBE_MAX_CHARS:
        raise RuntimeError(_SIMC_SOCKET_PROBE_FAILURE)
    try:
        parsed = gear_socket_authority.parse_simc_socket_bonus_minimums(output)
    except Exception:
        raise RuntimeError(_SIMC_SOCKET_PROBE_FAILURE) from None
    if not parsed:
        raise RuntimeError(_SIMC_SOCKET_PROBE_FAILURE)
    return parsed


def expected_spec_pairs() -> list[tuple[str, str]]:
    return sorted(
        (_text(klass.get("key")), _text(spec))
        for klass in WOW_CLASSES
        for spec in klass.get("specs") or []
    )


def runtime_dependency_revisions(simc_runtime_revision: str) -> dict[str, str]:
    runtime = gear_resolver_runtime_authority(
        "mage",
        "arcane",
        simc_runtime_revision=simc_runtime_revision,
    )
    revisions = dict(runtime.get("dependencyRevisions") or {})
    revisions["capabilityRevision"] = CAPABILITY_REVISION
    return revisions


def validate_gear_snapshot(snapshot: Any) -> list[dict[str, str]]:
    value = snapshot if isinstance(snapshot, dict) else {}
    problems: list[dict[str, str]] = []
    items = [row for row in value.get("items") or [] if isinstance(row, dict)]
    sources = [row for row in value.get("sources") or [] if isinstance(row, dict)]
    variants = [row for row in value.get("variants") or [] if isinstance(row, dict)]
    options = [row for row in value.get("options") or [] if isinstance(row, dict)]
    if not items:
        problems.append({"code": "GEAR_RELEASE_ITEMS_EMPTY", "path": "snapshot.items"})
    if not sources:
        problems.append({"code": "GEAR_RELEASE_SOURCES_EMPTY", "path": "snapshot.sources"})
    if not variants:
        problems.append({"code": "GEAR_RELEASE_VARIANTS_EMPTY", "path": "snapshot.variants"})

    required_text_fields = (
        (items, "itemId", "GEAR_RELEASE_ITEM_ID_EMPTY", "snapshot.items"),
        (sources, "sourceId", "GEAR_RELEASE_SOURCE_ID_EMPTY", "snapshot.sources"),
        (sources, "itemId", "GEAR_RELEASE_SOURCE_ITEM_ID_EMPTY", "snapshot.sources"),
        (sources, "sourceKey", "GEAR_RELEASE_SOURCE_KEY_EMPTY", "snapshot.sources"),
        (variants, "variantId", "GEAR_RELEASE_VARIANT_ID_EMPTY", "snapshot.variants"),
        (variants, "itemId", "GEAR_RELEASE_VARIANT_ITEM_ID_EMPTY", "snapshot.variants"),
        (variants, "variantKey", "GEAR_RELEASE_VARIANT_KEY_EMPTY", "snapshot.variants"),
        (options, "optionId", "GEAR_RELEASE_OPTION_ID_EMPTY", "snapshot.options"),
        (options, "optionKey", "GEAR_RELEASE_OPTION_KEY_EMPTY", "snapshot.options"),
    )
    for rows, field, code, path in required_text_fields:
        if any(not _text(row.get(field)) for row in rows):
            problems.append({"code": code, "path": path})

    def duplicate_values(rows: Iterable[dict[str, Any]], key: Callable[[dict[str, Any]], Any], code: str, path: str):
        seen = set()
        duplicates = set()
        for row in rows:
            value = key(row)
            if value in seen:
                duplicates.add(value)
            seen.add(value)
        if duplicates:
            problems.append({"code": code, "path": path})

    duplicate_values(items, lambda row: _text(row.get("itemId")), "GEAR_RELEASE_ITEM_ID_DUPLICATE", "snapshot.items")
    duplicate_values(sources, lambda row: _text(row.get("sourceId")), "GEAR_RELEASE_SOURCE_ID_DUPLICATE", "snapshot.sources")
    duplicate_values(variants, lambda row: _text(row.get("variantId")), "GEAR_RELEASE_VARIANT_ID_DUPLICATE", "snapshot.variants")
    duplicate_values(variants, lambda row: (_text(row.get("itemId")), _text(row.get("variantKey"))), "GEAR_RELEASE_VARIANT_KEY_DUPLICATE", "snapshot.variants")
    duplicate_values(options, lambda row: _text(row.get("optionId")), "GEAR_RELEASE_OPTION_ID_DUPLICATE", "snapshot.options")
    duplicate_values(options, lambda row: _text(row.get("optionKey")), "GEAR_RELEASE_OPTION_KEY_DUPLICATE", "snapshot.options")

    item_ids = {_text(row.get("itemId")) for row in items}
    variant_ids = {_text(row.get("variantId")) for row in variants}
    if any(_text(row.get("itemId")) not in item_ids for row in sources):
        problems.append({"code": "GEAR_RELEASE_SOURCE_ITEM_ORPHAN", "path": "snapshot.sources"})
    if any(_text(row.get("itemId")) not in item_ids for row in variants):
        problems.append({"code": "GEAR_RELEASE_VARIANT_ITEM_ORPHAN", "path": "snapshot.variants"})
    if any(_text(row.get("variantId")) and _text(row.get("variantId")) not in variant_ids for row in options):
        problems.append({"code": "GEAR_RELEASE_OPTION_VARIANT_ORPHAN", "path": "snapshot.options"})
    return problems


def selection_intent_from_template(
    template: dict[str, Any],
    *,
    gear_release_id: str,
    season_revision: str,
    level: int,
) -> dict[str, Any]:
    slots: dict[str, dict[str, Any]] = {}
    for raw in template.get("gearItems") or []:
        if not isinstance(raw, dict):
            continue
        slot = normalize_slot(raw.get("slot") or raw.get("simcSlot"))
        item_id = _text(raw.get("itemId") or raw.get("id"))
        if not slot or not item_id or slot in slots:
            continue
        slots[slot] = {
            "itemId": item_id,
            "variantKey": _text(raw.get("variantKey")),
            "gemOptionIds": [],
            "enchantOptionId": "",
            "embellishmentOptionId": "",
            "craftedOptionId": "",
            "catalystOptionId": "",
        }
    return {
        "schemaRevision": "selection-intent-v1",
        "authoredAgainst": {
            "seasonRevision": _text(season_revision),
            "gearCatalogRevision": _text(gear_release_id),
        },
        "eligibilityContext": {
            "classKey": _text(template.get("classKey")),
            "specKey": _text(template.get("specKey")),
            "level": _int(level),
        },
        "slots": {key: slots[key] for key in sorted(slots)},
    }


def prepare_staging_gear_release(
    store: GearReleaseStore,
    *,
    season_revision: str,
    dependency_revisions: dict[str, Any],
    socket_bonus_minimums: Mapping[str, Any],
    source_revision: str = "legacy-import-r0",
    parent_release_id: str = "",
) -> dict[str, Any]:
    if not isinstance(socket_bonus_minimums, Mapping) or not socket_bonus_minimums:
        raise GearReleaseIntegrityError("socket bonus evidence must be a non-empty mapping")
    normalized_bonus_minimums = socket_bonus_minimums
    snapshot = _project_socket_facts_into_release_payloads(
        gear_socket_authority.materialize_gear_socket_facts(
            store.snapshot_staging_gear(),
            season_revision=season_revision,
            socket_bonus_minimums=normalized_bonus_minimums,
        )
    )
    problems = validate_gear_snapshot(snapshot)
    if problems:
        raise GearReleaseIntegrityError(json.dumps(problems, ensure_ascii=False, sort_keys=True))
    summary = gear_snapshot_summary(snapshot)
    release = gear_release.build_release(
        release_kind="gear",
        season_revision=season_revision,
        schema_revision="gear-release-v1",
        content=summary,
        dependency_revisions=dependency_revisions,
        release_status="validated",
        source={
            "sourceRevision": source_revision,
            "stagingSnapshotHash": summary["snapshotHash"],
            "sourceEvidence": {
                "simcRuntimeRevision": _text(dependency_revisions.get("simcRuntimeRevision")),
                "socketProbeDigest": _socket_probe_digest(normalized_bonus_minimums),
                "materializedSocketFactDigest": _materialized_socket_fact_digest(snapshot),
            },
        },
        parent_release_id=parent_release_id,
    )
    gate = {"status": "validated", **summary}
    return {"release": release, "snapshot": snapshot, "gate": gate}


def build_legacy_gear_release(
    store: GearReleaseStore,
    *,
    season_revision: str,
    dependency_revisions: dict[str, Any],
    socket_bonus_minimums: Mapping[str, Any],
    source_revision: str = "legacy-import-r0",
) -> dict[str, Any]:
    prepared = prepare_staging_gear_release(
        store,
        season_revision=season_revision,
        dependency_revisions=dependency_revisions,
        socket_bonus_minimums=socket_bonus_minimums,
        source_revision=source_revision,
    )
    release = prepared["release"]
    snapshot = prepared["snapshot"]
    gate = prepared["gate"]
    seal = store.seal_gear_release(
        release,
        snapshot,
        gate_result=gate,
        event={"mode": source_revision, "gate": gate},
    )
    return {"release": release, "snapshot": snapshot, "gate": gate, "seal": seal}


def _template_candidate(
    template: dict[str, Any],
    *,
    gear_release_id: str,
    season_revision: str,
    level: int,
) -> dict[str, Any]:
    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    evidence = payload.get("templateEvidence") if isinstance(payload.get("templateEvidence"), dict) else {}
    refs = [row for row in template.get("sourceRefs") or [] if isinstance(row, dict)]
    ref = refs[0] if refs else {}
    return {
        "id": _text(template.get("templateId")),
        "classKey": _text(template.get("classKey")),
        "specKey": _text(template.get("specKey")),
        "sourceKey": _text(template.get("sourceKey")),
        "sourceUrl": _text(template.get("sourceUrl") or evidence.get("sourceProfileUrl") or ref.get("sourceUrl")),
        "sourceStatus": _text(template.get("sourceStatus")),
        "sampleCount": _int(template.get("sampleCount") or evidence.get("sampleCount") or ref.get("sampleCount")),
        "profileHash": _text(template.get("profileHash") or evidence.get("profileHash")),
        "gearHash": _text(template.get("gearHash") or evidence.get("gearHash") or template.get("signature")),
        "updatedAt": _text(template.get("updatedAt")),
        "expiresAt": _text(template.get("expiresAt")),
        "selectionIntent": selection_intent_from_template(
            template,
            gear_release_id=gear_release_id,
            season_revision=season_revision,
            level=level,
        ),
    }


def _release_rows_from_election(
    election: dict[str, Any],
    templates_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    rank_by_spec: dict[tuple[str, str], int] = {}
    for elected in [*(election.get("winners") or []), *(election.get("standbys") or [])]:
        key = (_text(elected.get("classKey")), _text(elected.get("specKey")))
        rank_by_spec[key] = rank_by_spec.get(key, 0) + 1
        original = templates_by_id.get(_text(elected.get("candidateId")), {})
        payload = original.get("payload") if isinstance(original.get("payload"), dict) else {}
        rows.append({
            "templateId": _text(elected.get("candidateId")),
            "classKey": key[0],
            "specKey": key[1],
            "role": _text(elected.get("role")),
            "electionRank": rank_by_spec[key],
            "sourceKey": _text(elected.get("sourceKey")),
            "sourceUrl": _text(elected.get("sourceUrl")),
            "sourceStatus": _text(elected.get("sourceStatus")),
            "sampleCount": _int(elected.get("sampleCount")),
            "profileHash": _text(elected.get("profileHash")),
            "gearHash": _text(elected.get("gearHash")),
            "selectionIntent": _canonical(elected.get("selectionIntent") or {}),
            "resolvedGearSignature": _text(elected.get("resolvedGearSignature")),
            "semanticGearSignature": _text(elected.get("semanticGearSignature")),
            "dependencyVector": _canonical(elected.get("dependencyVector") or {}),
            "evidence": _canonical(payload.get("templateEvidence") or {"sourceRefs": original.get("sourceRefs") or []}),
            "problems": [],
            "payload": _canonical(original),
            "updatedAt": _text(elected.get("updatedAt")),
            "expiresAt": _text(elected.get("expiresAt")),
        })
    for rejected in election.get("rejected") or []:
        candidate_id = _text(rejected.get("candidateId"))
        original = templates_by_id.get(candidate_id, {})
        rows.append({
            "templateId": candidate_id,
            "classKey": _text(rejected.get("classKey")),
            "specKey": _text(rejected.get("specKey")),
            "role": "rejected",
            "electionRank": 0,
            "sourceKey": _text(original.get("sourceKey")),
            "sourceUrl": _text(original.get("sourceUrl")),
            "sourceStatus": _text(original.get("sourceStatus")),
            "sampleCount": 0,
            "profileHash": "",
            "gearHash": _text(original.get("signature")),
            "selectionIntent": {},
            "resolvedGearSignature": "",
            "semanticGearSignature": "",
            "dependencyVector": {},
            "evidence": _canonical(original.get("sourceRefs") or []),
            "problems": _canonical(rejected.get("problems") or []),
            "payload": _canonical(original),
            "updatedAt": _text(original.get("updatedAt")),
            "expiresAt": _text(original.get("expiresAt")),
        })
    return sorted(rows, key=lambda row: (row["classKey"], row["specKey"], row["role"], row["electionRank"], row["templateId"]))


def prepare_staging_community_release(
    store: GearReleaseStore,
    *,
    gear_release_descriptor: dict[str, Any],
    gear_snapshot: dict[str, Any],
    dependency_revisions: dict[str, Any],
    expected_specs: Iterable[tuple[str, str]],
    now: str,
    level: int = 90,
    source_revision: str = "legacy-import-r0",
    parent_release_id: str = "",
    resolver_for_spec: Callable[[str, str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    expected = sorted({
        (_text(class_key), _text(spec_key))
        for class_key, spec_key in expected_specs
        if _text(class_key) and _text(spec_key)
    })
    if not expected:
        raise GearReleaseIntegrityError("expected_specs must contain at least one spec")
    templates = store.snapshot_staging_community_templates(expected)
    template_ids = [_text(row.get("templateId")) for row in templates]
    if any(not template_id for template_id in template_ids):
        raise GearReleaseIntegrityError("staging community templateId must be non-empty")
    if len(set(template_ids)) != len(template_ids):
        raise GearReleaseIntegrityError("staging community templateId must be unique")
    templates_by_id = {_text(row.get("templateId")): row for row in templates if _text(row.get("templateId"))}
    candidates = [
        _template_candidate(
            template,
            gear_release_id=gear_release_descriptor["releaseId"],
            season_revision=gear_release_descriptor["seasonRevision"],
            level=level,
        )
        for template in templates
    ]
    prepared_authority = (
        CandidateGearAuthorityIndex(gear_snapshot, gear_release_descriptor)
        if resolver_for_spec is None
        else None
    )

    def resolve_candidate(intent: dict[str, Any]) -> dict[str, Any]:
        eligibility = intent.get("eligibilityContext") or {}
        class_key = _text(eligibility.get("classKey"))
        spec_key = _text(eligibility.get("specKey"))
        if resolver_for_spec is not None:
            return resolver_for_spec(class_key, spec_key, intent)
        runtime = gear_resolver_runtime_authority(
            class_key,
            spec_key,
            simc_runtime_revision=_text(dependency_revisions.get("simcRuntimeRevision")),
        )
        runtime["dependencyRevisions"] = dict(dependency_revisions)
        authority = build_candidate_authority_context(
            gear_snapshot,
            intent,
            runtime,
            gear_release_descriptor,
            prepared_index=prepared_authority,
        )
        return gear_resolver.resolve(intent, authority)

    election = gear_release.elect_community_candidates(
        candidates,
        gear_release_id=gear_release_descriptor["releaseId"],
        resolver=resolve_candidate,
        now=now,
        expected_specs=expected,
    )
    rows = _release_rows_from_election(election, templates_by_id)
    summary = community_rows_summary(rows)
    release = gear_release.build_release(
        release_kind="community",
        season_revision=gear_release_descriptor["seasonRevision"],
        schema_revision="community-release-v1",
        content=summary,
        dependency_revisions=dependency_revisions,
        release_status=election["status"],
        source={
            "sourceRevision": source_revision,
            "validatedAgainstGearReleaseId": gear_release_descriptor["releaseId"],
            "stagingTemplateCount": len(templates),
        },
        parent_release_id=parent_release_id,
        validated_against_release_id=gear_release_descriptor["releaseId"],
    )
    gate = {
        "status": election["status"],
        "expectedSpecCount": election["expectedSpecCount"],
        "winnerSpecCount": election["winnerSpecCount"],
        "standbyCount": len(election.get("standbys") or []),
        "rejectedCount": len(election.get("rejected") or []),
        "missingSpecs": election.get("missingSpecs") or [],
        **summary,
    }
    return {"release": release, "rows": rows, "election": election, "gate": gate}


def build_legacy_community_release(
    store: GearReleaseStore,
    *,
    gear_release_descriptor: dict[str, Any],
    gear_snapshot: dict[str, Any],
    dependency_revisions: dict[str, Any],
    expected_specs: Iterable[tuple[str, str]],
    now: str,
    level: int = 90,
    source_revision: str = "legacy-import-r0",
    resolver_for_spec: Callable[[str, str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    prepared = prepare_staging_community_release(
        store,
        gear_release_descriptor=gear_release_descriptor,
        gear_snapshot=gear_snapshot,
        dependency_revisions=dependency_revisions,
        expected_specs=expected_specs,
        now=now,
        level=level,
        source_revision=source_revision,
        resolver_for_spec=resolver_for_spec,
    )
    release = prepared["release"]
    rows = prepared["rows"]
    election = prepared["election"]
    gate = prepared["gate"]
    seal = store.seal_community_release(
        release,
        rows,
        gate_result=gate,
        event={"mode": source_revision, "gate": gate},
    )
    return {"release": release, "rows": rows, "election": election, "gate": gate, "seal": seal}


def _store_from_environment() -> GearReleaseStore:
    config = database_config_from_env()
    if not postgres_only_runtime_enabled(config):
        raise RuntimeError("gear release tooling requires WOW_DATABASE_RUNTIME=postgres_only and WOW_DATABASE_URL")
    return GearReleaseStore(lambda: connect_postgres(config.database_url))


class _CountingCursor:
    def __init__(self, cursor, counter):
        self._cursor = cursor
        self._counter = counter

    def execute(self, statement, *args, **kwargs):
        self._counter.record(statement)
        return self._cursor.execute(statement, *args, **kwargs)

    def executemany(self, statement, *args, **kwargs):
        self._counter.record(statement)
        return self._cursor.executemany(statement, *args, **kwargs)

    def __enter__(self):
        self._cursor.__enter__()
        return self

    def __exit__(self, *args):
        return self._cursor.__exit__(*args)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class _CountingConnection:
    def __init__(self, connection, counter):
        self._connection = connection
        self._counter = counter

    def cursor(self, *args, **kwargs):
        return _CountingCursor(self._connection.cursor(*args, **kwargs), self._counter)

    def __getattr__(self, name):
        return getattr(self._connection, name)


class _StatementCounter:
    def __init__(self, connection_factory):
        self._connection_factory = connection_factory
        self.total = 0
        self.transaction_control = 0
        self.read_queries = 0
        self.write_statements = 0

    def __call__(self):
        return _CountingConnection(self._connection_factory(), self)

    def record(self, statement):
        normalized = " ".join(str(statement or "").split()).upper()
        self.total += 1
        if normalized.startswith("SET TRANSACTION"):
            self.transaction_control += 1
        elif normalized.startswith(("INSERT ", "UPDATE ", "DELETE ", "MERGE ", "TRUNCATE ")):
            self.write_statements += 1
        else:
            self.read_queries += 1

    def snapshot(self):
        return {
            "total": self.total,
            "transactionControl": self.transaction_control,
            "readQueries": self.read_queries,
            "writeStatements": self.write_statements,
        }


def _shadow_store_from_environment() -> PostgresCacheStore:
    config = database_config_from_env()
    if not postgres_only_runtime_enabled(config):
        raise RuntimeError("gear release shadow requires WOW_DATABASE_RUNTIME=postgres_only and WOW_DATABASE_URL")
    counter = _StatementCounter(lambda: connect_postgres(config.database_url))
    store = PostgresCacheStore(counter)
    store.shadow_read_statement_metrics = counter.snapshot
    return store


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build-legacy-gear", "build-legacy-all", "show", "shadow", "promote", "rollback"))
    parser.add_argument("--season-revision", default="")
    parser.add_argument("--simc-runtime-revision", default="")
    parser.add_argument("--release-id", default="")
    parser.add_argument("--gear-release-id", default="")
    parser.add_argument("--community-release-id", default="")
    parser.add_argument("--talent-catalog-revision", default="")
    parser.add_argument("--manifest-revision", default="")
    parser.add_argument("--rollback-manifest-revision", default="")
    parser.add_argument("--expected-generation", type=int, default=-1)
    parser.add_argument("--target-mode", choices=("active", "transitional"), default="active")
    parser.add_argument("--updated-by", default="")
    parser.add_argument("--level", type=int, default=90)
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "promote":
        required = {
            "--season-revision": args.season_revision,
            "--simc-runtime-revision": args.simc_runtime_revision,
            "--gear-release-id": args.gear_release_id,
            "--talent-catalog-revision": args.talent_catalog_revision,
            "--updated-by": args.updated_by,
        }
        missing = [name for name, value in required.items() if not _text(value)]
        if args.expected_generation < 0:
            missing.append("--expected-generation")
        if missing:
            raise SystemExit(", ".join(missing) + " are required")
        store = _store_from_environment()
        gear_descriptor = store.get_release(args.gear_release_id)
        if not gear_descriptor:
            raise GearReleaseIntegrityError("Gear Release is missing")
        community_descriptor = None
        if args.community_release_id:
            community_descriptor = store.get_release(args.community_release_id)
            if not community_descriptor:
                raise GearReleaseIntegrityError("Community Release is missing")
        dependencies = runtime_dependency_revisions(args.simc_runtime_revision)
        manifest = gear_release.build_manifest(
            season_revision=args.season_revision,
            gear_release=gear_descriptor,
            community_release=community_descriptor,
            talent_catalog_revision=args.talent_catalog_revision,
            dependency_revisions=dependencies,
            rollback_manifest_revision=args.rollback_manifest_revision,
        )
        command = gear_release.build_pointer_command(
            "promote",
            manifest["manifestRevision"],
            args.expected_generation,
            args.rollback_manifest_revision,
            target_mode="active",
        )
        result = store.seal_manifest_and_compare_and_swap_pointer(
            manifest,
            command,
            updated_by=args.updated_by,
        )
        print(json.dumps({"status": "updated", "manifestRevision": manifest["manifestRevision"], **result}, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "rollback":
        if args.expected_generation < 0 or not _text(args.updated_by):
            raise SystemExit("--expected-generation and --updated-by are required")
        if args.target_mode == "active" and not _text(args.manifest_revision):
            raise SystemExit("--manifest-revision is required for active rollback")
        command = gear_release.build_pointer_command(
            "rollback",
            args.manifest_revision,
            args.expected_generation,
            args.rollback_manifest_revision,
            target_mode=args.target_mode,
        )
        result = _store_from_environment().compare_and_swap_pointer(
            command,
            updated_by=args.updated_by,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "shadow":
        if not args.gear_release_id or not args.community_release_id or not args.simc_runtime_revision:
            raise SystemExit("--gear-release-id, --community-release-id and --simc-runtime-revision are required")
        shadow_store = _shadow_store_from_environment()
        result = gear_release_shadow.run_release_shadow(
            shadow_store,
            expected_specs=expected_spec_pairs(),
            gear_release_id=args.gear_release_id,
            community_release_id=args.community_release_id,
            simc_runtime_revision=args.simc_runtime_revision,
            level=args.level,
        )
        cache_metrics = getattr(shadow_store, "gear_authority_cache_metrics", None)
        statement_metrics = getattr(shadow_store, "shadow_read_statement_metrics", None)
        if callable(cache_metrics):
            result["authorityCache"] = cache_metrics()
        if callable(statement_metrics):
            result["databaseStatements"] = statement_metrics()
            if result["databaseStatements"].get("writeStatements"):
                result["status"] = "blocked"
                result.setdefault("blockers", []).append({
                    "kind": "SHADOW_COMPARE_BLOCKED",
                    "code": "SHADOW_WRITE_STATEMENT_DETECTED",
                    "title": "Release shadow comparison blocked.",
                    "detail": "Internal shadow executed a write statement.",
                    "path": "shadow",
                    "retryable": False,
                    "meta": {},
                })
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result.get("status") == "pass" else 2
    store = _store_from_environment()
    if args.command == "show":
        print(json.dumps(store.get_release(args.release_id), ensure_ascii=False, sort_keys=True))
        return 0
    if not args.season_revision or not args.simc_runtime_revision:
        raise SystemExit("--season-revision and --simc-runtime-revision are required")
    dependencies = runtime_dependency_revisions(args.simc_runtime_revision)
    try:
        from .simulator_payload import simc_binary
    except ImportError:
        from simulator_payload import simc_binary
    socket_bonus_minimums = load_simc_socket_bonus_minimums(simc_binary())
    gear = build_legacy_gear_release(
        store,
        season_revision=args.season_revision,
        dependency_revisions=dependencies,
        socket_bonus_minimums=socket_bonus_minimums,
    )
    output = {"gear": {"release": gear["release"], "gate": gear["gate"], "seal": gear["seal"]}}
    if args.command == "build-legacy-all":
        community = build_legacy_community_release(
            store,
            gear_release_descriptor=gear["release"],
            gear_snapshot=gear["snapshot"],
            dependency_revisions=dependencies,
            expected_specs=expected_spec_pairs(),
            now=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            level=args.level,
        )
        output["community"] = {"release": community["release"], "gate": community["gate"], "seal": community["seal"]}
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "build_legacy_community_release",
    "build_legacy_gear_release",
    "expected_spec_pairs",
    "load_simc_socket_bonus_minimums",
    "prepare_staging_gear_release",
    "runtime_dependency_revisions",
    "selection_intent_from_template",
    "validate_gear_snapshot",
)

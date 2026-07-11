#!/usr/bin/env python3
"""Explicit inactive release builder for equipment simulator Phase 4B."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from typing import Any, Callable, Iterable

try:
    from . import gear_release, gear_resolver
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
except ImportError:
    import gear_release
    import gear_resolver
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


CAPABILITY_REVISION = "gear-capability-matrix-v1"


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


def build_legacy_gear_release(
    store: GearReleaseStore,
    *,
    season_revision: str,
    dependency_revisions: dict[str, Any],
    source_revision: str = "legacy-import-r0",
) -> dict[str, Any]:
    snapshot = store.snapshot_staging_gear()
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
        source={"sourceRevision": source_revision, "stagingSnapshotHash": summary["snapshotHash"]},
    )
    gate = {"status": "validated", **summary}
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build-legacy-gear", "build-legacy-all", "show", "promote", "rollback"))
    parser.add_argument("--season-revision", default="")
    parser.add_argument("--simc-runtime-revision", default="")
    parser.add_argument("--release-id", default="")
    parser.add_argument("--level", type=int, default=90)
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    if args.command in {"promote", "rollback"}:
        print(json.dumps({"status": "blocked", "reason": "pointer mutation is disabled in Phase 4B"}, sort_keys=True))
        return 2
    store = _store_from_environment()
    if args.command == "show":
        print(json.dumps(store.get_release(args.release_id), ensure_ascii=False, sort_keys=True))
        return 0
    if not args.season_revision or not args.simc_runtime_revision:
        raise SystemExit("--season-revision and --simc-runtime-revision are required")
    dependencies = runtime_dependency_revisions(args.simc_runtime_revision)
    gear = build_legacy_gear_release(
        store,
        season_revision=args.season_revision,
        dependency_revisions=dependencies,
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
    "runtime_dependency_revisions",
    "selection_intent_from_template",
    "validate_gear_snapshot",
)

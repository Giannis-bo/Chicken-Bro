#!/usr/bin/env python3
"""Explicit inactive release builder for equipment simulator Phase 4B."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import heapq
import json
import os
import re
import subprocess
import tempfile
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlparse

try:
    from . import (
        community_winner_projection,
        gear_enhancement_management,
        gear_evidence_registry,
        gear_fact_compiler,
        gear_fact_shadow,
        gear_release,
        gear_release_shadow,
        gear_resolver,
        gear_socket_authority,
        raiderio_payload,
    )
    from .db import connect_postgres, database_config_from_env, postgres_only_runtime_enabled
    from .gear_release_store import (
        CandidateGearAuthorityIndex,
        GearReleaseIntegrityError,
        GearReleaseStore,
        build_candidate_authority_context,
        community_rows_summary,
        gear_snapshot_summary,
    )
    from .websim_payload import (
        PRIMARY_STAT_GEM_IDS,
        SIMC_GEAR_OPTION_KEYS,
        WOW_CLASSES,
        gear_resolver_runtime_authority,
        hero_trees_for_spec,
        item_can_enchant_slot,
        normalize_option_value,
        normalize_slot,
        observed_gear_simc_options,
        simc_encoded_item_options,
    )
    from .postgres_cache_store import PostgresCacheStore
except ImportError:
    import gear_enhancement_management
    import gear_evidence_registry
    import gear_fact_compiler
    import gear_fact_shadow
    import community_winner_projection
    import gear_release
    import gear_release_shadow
    import gear_resolver
    import gear_socket_authority
    import raiderio_payload
    from db import connect_postgres, database_config_from_env, postgres_only_runtime_enabled
    from gear_release_store import (
        CandidateGearAuthorityIndex,
        GearReleaseIntegrityError,
        GearReleaseStore,
        build_candidate_authority_context,
        community_rows_summary,
        gear_snapshot_summary,
    )
    from websim_payload import (
        PRIMARY_STAT_GEM_IDS,
        SIMC_GEAR_OPTION_KEYS,
        WOW_CLASSES,
        gear_resolver_runtime_authority,
        hero_trees_for_spec,
        item_can_enchant_slot,
        normalize_option_value,
        normalize_slot,
        observed_gear_simc_options,
        simc_encoded_item_options,
    )
    from postgres_cache_store import PostgresCacheStore


_SIMC_SOCKET_PROBE_TIMEOUT_SECONDS = 30
_RANK_ONE_REJECTION_LIMIT = 80
_RANK_ONE_REJECTION_PROBLEM_LIMIT = 12
_SIMC_SOCKET_PROBE_MAX_CHARS = 4 * 1024 * 1024
_SIMC_SOCKET_PROBE_FAILURE = "SimC socket probe failed"
_FULL_RELEASE_EVIDENCE_BATCH_SIZE = 32
_MAX_STREAMING_RELEASE_EVIDENCE_BATCH_SIZE = 128
_GEM_SIMC_SEQUENCE_FIELDS = gear_enhancement_management.GEM_SIMC_SEQUENCE_FIELDS
_ENHANCEMENT_SIMC_FIELDS = gear_enhancement_management.ENHANCEMENT_SIMC_FIELDS
_BATTLE_NET_GAME_DATA_API = "Battle.net Game Data API"
_OFFICIAL_GEM_UNIQUE_CATEGORY_ALIASES = {
    "thalassian diamond": "thalassian-diamond",
    "萨拉斯钻石": "thalassian-diamond",
    "薩拉斯鑽石": "thalassian-diamond",
}
_OFFICIAL_GEM_UNIQUE_CATEGORY_LIMITS = {
    "thalassian-diamond": 1,
}
_OFFICIAL_UNIQUE_GEM_POLICIES = {
    gem_id: {"categoryKey": "thalassian-diamond", "uniqueLimit": 1}
    for gem_id in {*PRIMARY_STAT_GEM_IDS, "241144"}
}
COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISION = (
    gear_release.COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISION
)
_ATTRIBUTE_STABLE_EFFECT_CONTEXT_REVISION = "gear-attribute-stable-effects-v1"
_ATTRIBUTE_STABLE_EFFECT_ID_PATTERN = re.compile(r"[a-z][a-z0-9:_-]{0,255}")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _attribute_race_key(value: Any) -> str:
    key = _text(value)
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", key):
        return ""
    return key


def _attribute_character_context_from_template(template: dict[str, Any]) -> dict[str, str]:
    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    raw = template.get("attributeCharacterContext")
    if not isinstance(raw, dict):
        raw = payload.get("attributeCharacterContext") if isinstance(payload.get("attributeCharacterContext"), dict) else {}
    race_key = _attribute_race_key(raw.get("raceKey"))
    if (
        raw.get("schemaRevision") == "gear-attribute-character-v1"
        and raw.get("origin") == "source_profile"
        and race_key
    ):
        return {"raceKey": race_key, "origin": "source_profile"}
    return {"raceKey": "human", "origin": "default_human"}


def _attribute_stable_effect_context_from_template(template: dict[str, Any]) -> dict[str, Any]:
    """Return only a sealed source loadout projection, never its import code."""

    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    raw = template.get("attributeStableEffectContext")
    if not isinstance(raw, dict):
        raw = payload.get("attributeStableEffectContext") if isinstance(
            payload.get("attributeStableEffectContext"), dict
        ) else {}
    effect_ids = raw.get("effectIds")
    signature = _text(raw.get("loadoutSignature"))
    if (
        raw.get("schemaRevision") == _ATTRIBUTE_STABLE_EFFECT_CONTEXT_REVISION
        and raw.get("status") == "verified"
        and raw.get("origin") == "source_profile"
        and isinstance(effect_ids, list)
        and all(
            isinstance(effect_id, str)
            and bool(_ATTRIBUTE_STABLE_EFFECT_ID_PATTERN.fullmatch(effect_id))
            for effect_id in effect_ids
        )
        and effect_ids == sorted(set(effect_ids))
        and bool(re.fullmatch(r"sha256:[0-9a-f]{64}", signature))
    ):
        return {
            "schemaRevision": _ATTRIBUTE_STABLE_EFFECT_CONTEXT_REVISION,
            "status": "verified",
            "origin": "source_profile",
            "effectIds": list(effect_ids),
            "loadoutSignature": signature,
        }
    return {
        "schemaRevision": _ATTRIBUTE_STABLE_EFFECT_CONTEXT_REVISION,
        "status": "unavailable",
        "reason": "source_talent_loadout_unavailable",
    }


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


def _socket_probe_digest(socket_bonus_evidence: Mapping[str, Any]) -> str:
    return _canonical_digest({
        "socketBonusEvidence": _canonical(socket_bonus_evidence),
    })


def _shadow_blocker_summary(blockers: Iterable[Any], *, limit: int = 3) -> str:
    """Return a bounded internal locator for a fail-closed shadow rejection."""

    entries: list[str] = []
    for blocker in blockers:
        if not isinstance(blocker, Mapping):
            continue
        code = _text(blocker.get("code"))
        if not code:
            continue
        subject_key = _text(blocker.get("subjectKey"))
        fact_type = _text(blocker.get("factType"))
        entries.append(":".join(
            value for value in (code, subject_key, fact_type) if value
        ))
        if len(entries) >= limit:
            break
    return ", ".join(entries) or "UNKNOWN_SHADOW_BLOCKER"


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
            "socketEligibility": _canonical(_socket_fact_value(row, "socketEligibility")),
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


_RELEASE_FACT_REF_LIMIT = 8
_SIMC_SOCKET_BONUS_EVIDENCE_REVISION = (
    "simc-socket-bonus-evidence-v1"
)


def _validated_socket_bonus_evidence(value: Any) -> dict[str, Any]:
    evidence = value if isinstance(value, Mapping) else {}
    minimums = (
        evidence.get("minimums")
        if isinstance(evidence.get("minimums"), Mapping)
        else {}
    )
    normalized_minimums: dict[str, int] = {}
    for bonus_id, minimum in minimums.items():
        normalized_id = _text(bonus_id)
        if (
            not normalized_id.isdigit()
            or int(normalized_id) <= 0
            or isinstance(minimum, bool)
            or not isinstance(minimum, int)
            or minimum <= 0
        ):
            raise GearReleaseIntegrityError(
                "verified SimC socket bonus evidence envelope is required"
            )
        normalized_minimums[str(int(normalized_id))] = minimum
    if (
        evidence.get("schemaRevision")
        != _SIMC_SOCKET_BONUS_EVIDENCE_REVISION
        or evidence.get("status") != "verified"
        or evidence.get("sourceType") != "simc_bonus_probe"
        or not _text(evidence.get("sourceIdentity"))
        or not _text(evidence.get("sourceRevision"))
        or evidence.get("sourceScope") != "exact_variant"
        or not normalized_minimums
    ):
        raise GearReleaseIntegrityError(
            "verified SimC socket bonus evidence envelope is required"
        )
    return {
        "schemaRevision": _SIMC_SOCKET_BONUS_EVIDENCE_REVISION,
        "status": "verified",
        "sourceType": "simc_bonus_probe",
        "sourceIdentity": _text(evidence.get("sourceIdentity")),
        "sourceRevision": _text(evidence.get("sourceRevision")),
        "sourceScope": "exact_variant",
        "minimums": {
            bonus_id: normalized_minimums[bonus_id]
            for bonus_id in sorted(normalized_minimums, key=int)
        },
    }


def _official_game_asset_evidence(
    payload: Mapping[str, Any],
    item_id: Any,
) -> dict[str, str] | None:
    metadata = (
        payload.get("_metadata")
        if isinstance(payload.get("_metadata"), Mapping)
        else {}
    )
    game_asset = (
        metadata.get("gameAsset")
        if isinstance(metadata.get("gameAsset"), Mapping)
        else {}
    )
    normalized_item_id = _text(item_id)
    source_identity = _text(game_asset.get("sourceIdentity"))
    source_revision = _text(game_asset.get("sourceRevision"))
    if (
        _text(game_asset.get("source")).lower() != "blizzard"
        or _text(game_asset.get("status")).lower() != "verified"
        or not normalized_item_id
        or source_identity
        != f"battle-net:item:{normalized_item_id}"
        or source_identity.startswith("gear-release:")
        or not source_revision
    ):
        return None
    return {
        "status": "verified",
        "sourceType": "battle_net_item",
        "sourceIdentity": source_identity,
        "sourceRevision": source_revision,
        "sourceScope": "exact_item",
    }


def _release_fact_projection(fact: Mapping[str, Any]) -> dict[str, Any]:
    observation_refs = sorted(
        {
            _text(reference)
            for reference in fact.get("observationRefs") or ()
            if _text(reference)
        }
    )
    return {
        "schemaRevision": _text(fact.get("schemaRevision")),
        "factKey": _text(fact.get("factKey")),
        "subjectKey": _text(fact.get("subjectKey")),
        "factType": _text(fact.get("factType")),
        "value": _canonical(fact.get("value")),
        "status": _text(fact.get("status")),
        "factValueHash": _text(fact.get("factValueHash")),
        "provenanceHash": _text(fact.get("provenanceHash")),
        "compilerRuleRevision": _text(fact.get("compilerRuleRevision")),
        "observationRefs": observation_refs[:_RELEASE_FACT_REF_LIMIT],
        "observationRefCount": len(observation_refs),
        "referencesTruncated": len(observation_refs) > _RELEASE_FACT_REF_LIMIT,
    }


def _gear_evidence_gap_records(
    facts: Iterable[Mapping[str, Any]],
    *,
    now: str,
) -> list[dict[str, Any]]:
    records = []
    for gap in gear_fact_compiler.evidence_gaps_from_facts(facts):
        identity = {
            "factKey": _text(gap.get("factKey")),
            "problemCode": _text(gap.get("problemCode")),
            "missingRequirement": _canonical(gap.get("missingRequirement") or {}),
        }
        records.append(
            {
                "schemaRevision": "gear-evidence-gap-v1",
                "gapKey": "gear-gap:" + _canonical_digest(identity),
                **identity,
                # This gap is deliberately non-claimable: raw occupied gems
                # prove neither an exact slot count nor a safe collector path.
                "status": (
                    "manual_pending"
                    if identity["problemCode"] == "unverified_observed_capacity"
                    else "pending"
                ),
                "attempt": 0,
                "nextAttemptAt": _text(now),
            }
        )
    return sorted(records, key=lambda row: row["gapKey"])


def _compile_release_gear_evidence(
    snapshot: dict[str, Any],
    *,
    season_revision: str,
    source_revision: str,
    captured_at: str,
    socket_bonus_minimums: Mapping[str, Any],
    socket_bonus_evidence: Mapping[str, Any],
    extra_artifacts: Iterable[Mapping[str, Any]] = (),
    extra_observations: Iterable[Mapping[str, Any]] = (),
    categories: Iterable[str] | None = None,
    compiler_context_artifacts: Iterable[Mapping[str, Any]] = (),
    compiler_context_observations: Iterable[Mapping[str, Any]] = (),
    compiler_context_facts: Mapping[
        tuple[str, str], Mapping[str, Any]
    ] | Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    selected_categories = frozenset(
        _text(category)
        for category in (
            categories
            if categories is not None
            else ("items", "variants", "options")
        )
        if _text(category)
    )
    unknown_categories = selected_categories - {"items", "variants", "options"}
    if unknown_categories:
        raise GearReleaseIntegrityError(
            "unknown Gear evidence compilation category"
        )
    artifacts: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    subject_fact_types: dict[str, set[str]] = {}
    row_subjects: dict[tuple[str, int], str] = {}
    socket_claims_by_subject: dict[str, list[dict[str, Any]]] = {}
    socket_eligibility_by_item_id: dict[str, dict[str, Any]] = {}
    # A streaming category batch must not rebuild unrelated catalog indexes.
    # In particular, option batches often have no owning variant at all; on a
    # real catalog, indexing every item, source, and variant beside that small
    # batch defeats the memory bound before compilation begins.
    items_by_id: dict[str, Mapping[str, Any]] = {}
    variants_by_id: dict[str, Mapping[str, Any]] = {}
    if "variants" in selected_categories:
        items_by_id = {
            _text(row.get("itemId")): row
            for row in snapshot.get("items") or ()
            if isinstance(row, dict) and _text(row.get("itemId"))
        }
    if "options" in selected_categories:
        option_rows = snapshot.get("options") or ()
        requested_variant_ids = {
            _text(row.get("variantId"))
            for row in option_rows
            if isinstance(row, Mapping) and _text(row.get("variantId"))
        }
        if requested_variant_ids:
            variants_by_id = {
                _text(row.get("variantId")): row
                for row in snapshot.get("variants") or ()
                if (
                    isinstance(row, dict)
                    and _text(row.get("variantId")) in requested_variant_ids
                )
            }
            if "variants" not in selected_categories:
                option_item_ids = {
                    _text(row.get("itemId"))
                    for row in variants_by_id.values()
                    if _text(row.get("itemId"))
                }
                if option_item_ids:
                    items_by_id = {
                        _text(row.get("itemId")): row
                        for row in snapshot.get("items") or ()
                        if (
                            isinstance(row, dict)
                            and _text(row.get("itemId")) in option_item_ids
                        )
                    }
    sources_by_item_id: dict[str, list[Mapping[str, Any]]] = {}
    if "items" in selected_categories:
        for source in snapshot.get("sources") or ():
            if isinstance(source, Mapping) and _text(source.get("itemId")):
                sources_by_item_id.setdefault(
                    _text(source.get("itemId")), []
                ).append(source)

    def add_artifact(
        *,
        source_type: str,
        source_identity: str,
        payload: dict[str, Any],
        fact_specs: Iterable[tuple[str, str, Any, str]],
        artifact_source_revision: str = "",
    ) -> None:
        if (
            not _text(source_identity)
            or _text(source_identity).startswith("gear-release:")
        ):
            return
        artifact = gear_evidence_registry.build_evidence_artifact(
            source_type=source_type,
            source_identity=source_identity,
            source_revision=artifact_source_revision or source_revision,
            season_revision=season_revision,
            captured_at=captured_at,
            payload=payload,
        )
        artifacts.append(artifact)
        for subject_key, fact_type, value, source_scope in fact_specs:
            observations.append(
                gear_evidence_registry.build_evidence_observation(
                    artifact_id=artifact["artifactId"],
                    subject_key=subject_key,
                    fact_type=fact_type,
                    observed_value=value,
                    parser_revision="gear-release-legacy-import-v1",
                    source_scope=source_scope,
                    status="accepted",
                )
            )
            subject_fact_types.setdefault(subject_key, set()).add(fact_type)

    def add_socket_inputs(
        inputs: Iterable[Mapping[str, Any]],
        *,
        evidence_row: Mapping[str, Any],
        official_payload: bool,
    ) -> None:
        evidence_payload = (
            evidence_row.get("payload")
            if isinstance(evidence_row.get("payload"), Mapping)
            else {}
        )
        for source_input in inputs:
            subject_key = _text(source_input.get("subjectKey"))
            source_name = _text(source_input.get("source"))
            source_scope = _text(source_input.get("sourceScope"))
            input_revision = _text(source_input.get("sourceRevision"))
            if (
                not subject_key
                or not source_name
                or not source_scope
                or not input_revision
            ):
                continue
            if source_name == "observed_gem_occupancy":
                if _int(source_input.get("observedValue")) > 0:
                    # An equipped-gem count is valuable as a replayable
                    # lower-bound constraint, but it is not a verified socket
                    # probe.  A generic stat probe cannot promote this legacy
                    # field to capacity without a dedicated socket Artifact.
                    add_artifact(
                        source_type="legacy_observed_variant",
                        source_identity=(
                            f"legacy-observed-variant:{subject_key}"
                        ),
                        artifact_source_revision=input_revision,
                        payload={
                            "subjectKey": subject_key,
                            "factType": "socket_count",
                            "observedGemCount": _int(
                                source_input.get("observedValue")
                            ),
                            "source": source_name,
                            "sourceScope": source_scope,
                        },
                        fact_specs=[
                            (
                                subject_key,
                                "socket_count",
                                _int(source_input.get("observedValue")),
                                source_scope,
                            )
                        ],
                    )
                continue
            source_evidence: Mapping[str, Any] | None = None
            if source_name == "official_item_payload" and official_payload:
                source_evidence = _official_game_asset_evidence(
                    evidence_payload,
                    subject_key.split("/", 1)[0].removeprefix(
                        "item:"
                    ),
                )
            elif source_name == "simc_bonus" and (
                input_revision
                == _text(socket_bonus_evidence.get("sourceRevision"))
                and source_scope
                == _text(socket_bonus_evidence.get("sourceScope"))
            ):
                source_evidence = socket_bonus_evidence
            elif (
                source_name.startswith("midnight_s1_")
                and input_revision == season_revision
            ):
                source_evidence = {
                    "sourceType": "season_rule",
                    "sourceIdentity": f"gear-socket-rule:{source_name}",
                    "sourceRevision": season_revision,
                    "sourceScope": source_scope,
                    "status": "verified",
                }
            if (
                not isinstance(source_evidence, Mapping)
                or _text(source_evidence.get("status")).lower()
                != "verified"
                or _text(source_evidence.get("sourceRevision"))
                != input_revision
                or _text(source_evidence.get("sourceScope"))
                != source_scope
                or not _text(source_evidence.get("sourceType"))
                or not _text(source_evidence.get("sourceIdentity"))
            ):
                continue
            socket_claims_by_subject.setdefault(subject_key, []).append(
                {
                    "minimumTotal": _int(source_input.get("observedValue")),
                    "scope": source_scope,
                    "source": source_name,
                    "sourceType": _text(
                        source_evidence.get("sourceType")
                    ),
                    "sourceIdentity": _text(
                        source_evidence.get("sourceIdentity")
                    ),
                    "sourceRevision": input_revision,
                }
            )
            add_artifact(
                source_type=_text(source_evidence.get("sourceType")),
                source_identity=_text(
                    source_evidence.get("sourceIdentity")
                ),
                artifact_source_revision=input_revision,
                payload={
                    "subjectKey": subject_key,
                    "factType": "socket_count",
                    "socketCount": source_input.get("observedValue"),
                    "source": source_name,
                    "sourceKey": _text(
                        source_input.get("sourceKey")
                    ),
                    "sourceScope": source_scope,
                },
                fact_specs=[
                    (
                        subject_key,
                        "socket_count",
                        source_input.get("observedValue"),
                        source_scope,
                    )
                ],
            )

    def official_item_source(
        payload: Mapping[str, Any],
        item_id: str,
    ) -> bool:
        return _official_game_asset_evidence(
            payload,
            item_id,
        ) is not None

    def add_allowed_enhancement_rules(
        *,
        subject: str,
        payload: Mapping[str, Any],
        canonical_evidence: Mapping[str, Any],
    ) -> None:
        """Compile only explicit, attributed closed-world slot rules."""

        if (
            "allowed_enhancement_options"
            not in {
                _text(value)
                for value in canonical_evidence.get("claims") or ()
                if _text(value)
            }
            or _text(canonical_evidence.get("status")).lower() != "verified"
            or _text(canonical_evidence.get("sourceType")).lower()
            != "season_rule"
            or not _text(canonical_evidence.get("sourceIdentity"))
            or not _text(canonical_evidence.get("sourceRevision"))
        ):
            return
        raw_rules = payload.get("allowedEnhancementRules")
        if not isinstance(raw_rules, list) or not raw_rules:
            return
        rules = []
        for raw_rule in raw_rules:
            if not isinstance(raw_rule, Mapping):
                return
            capability_type = _text(raw_rule.get("capabilityFactType"))
            option_ids = raw_rule.get("optionIds")
            slot = _text(raw_rule.get("slot"))
            if (
                capability_type
                not in {
                    "socket_count",
                    "enchant_capability",
                    "embellishment_capability",
                }
                or not isinstance(option_ids, list)
                or any(not _text(option_id) for option_id in option_ids)
                or not slot
            ):
                return
            rules.append(
                {
                    "capabilityFactType": capability_type,
                    "optionIds": sorted(
                        {_text(option_id) for option_id in option_ids}
                    ),
                    "slot": slot,
                }
            )
        add_artifact(
            source_type="season_rule",
            source_identity=(
                f"{_text(canonical_evidence.get('sourceIdentity'))}:"
                "allowed-enhancement-options"
            ),
            artifact_source_revision=_text(
                canonical_evidence.get("sourceRevision")
            ),
            payload={
                "subjectKey": subject,
                "allowedEnhancementRules": rules,
            },
            fact_specs=[
                (
                    subject,
                    "allowed_enhancement_options",
                    rule,
                    "slot_rule",
                )
                for rule in rules
            ],
        )

    for index, row in enumerate(
        snapshot.get("items") or () if "items" in selected_categories else ()
    ):
        if not isinstance(row, dict) or not _text(row.get("itemId")):
            continue
        item_id = _text(row["itemId"])
        subject = f"item:{item_id}"
        row_subjects[("items", index)] = subject
        subject_fact_types.setdefault(subject, set()).update(
            {
                "item_identity",
                "slot_compatibility",
                "socket_count",
                "enchant_capability",
                "embellishment_capability",
                "allowed_enhancement_options",
                "item_set_membership",
                "equipment_uniqueness",
            }
        )
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        canonical_evidence = (
            payload.get("canonicalEvidence")
            if isinstance(payload.get("canonicalEvidence"), dict)
            else {}
        )
        structural_revision = _text(canonical_evidence.get("sourceRevision"))
        structural_claims = {
            _text(value)
            for value in canonical_evidence.get("claims") or ()
            if _text(value)
        }
        structural_verified = (
            _text(canonical_evidence.get("status")).lower() == "verified"
            and _text(canonical_evidence.get("sourceType")).lower()
            == "season_rule"
            and bool(_text(canonical_evidence.get("sourceIdentity")))
            and bool(structural_revision)
            and _text(canonical_evidence.get("sourceScope")).lower()
            in {"base_item", "exact_item", "season_rule"}
        )
        capabilities = (
            payload.get("baseCapabilities")
            if isinstance(payload.get("baseCapabilities"), dict)
            else {}
        )
        is_official = official_item_source(payload, item_id)
        official_specs: list[tuple[str, str, Any, str]] = []
        if is_official:
            equipment_identity = {"itemId": item_id}
            for field in (
                "inventoryType",
                "armorType",
                "weaponType",
                "handedness",
            ):
                if _text(payload.get(field)):
                    equipment_identity[field] = _text(payload.get(field))
            official_specs.append(
                (
                    subject,
                    "item_identity",
                    equipment_identity,
                    "base_item",
                )
            )
            equipment_uniqueness = payload.get("equipmentUniqueness")
            if isinstance(equipment_uniqueness, dict):
                official_specs.append(
                    (
                        subject,
                        "equipment_uniqueness",
                        _canonical(equipment_uniqueness),
                        "base_item",
                    )
                )
        allowed_slots = payload.get("allowedSlots")
        if not isinstance(allowed_slots, list) or not allowed_slots:
            allowed_slots = [_text(row.get("slot"))] if _text(row.get("slot")) else []
        if is_official and allowed_slots:
            official_specs.append(
                (
                    subject,
                    "slot_compatibility",
                    sorted({_text(slot) for slot in allowed_slots if _text(slot)}),
                    "base_item",
                )
            )
        structural_specs: list[tuple[str, str, Any, str]] = []
        for field, fact_type in (
            ("canEnchant", "enchant_capability"),
            ("canEmbellish", "embellishment_capability"),
        ):
            if (
                structural_verified
                and fact_type in structural_claims
                and field in capabilities
            ):
                structural_specs.append(
                    (
                        subject,
                        fact_type,
                        capabilities[field],
                        _text(canonical_evidence.get("sourceScope")).lower(),
                    )
                )
        if official_specs:
            metadata = (
                payload.get("_metadata")
                if isinstance(payload.get("_metadata"), dict)
                else {}
            )
            official_evidence = _official_game_asset_evidence(
                payload,
                item_id,
            )
            add_artifact(
                source_type="battle_net_item",
                source_identity=_text(
                    official_evidence.get("sourceIdentity")
                ),
                artifact_source_revision=_text(
                    official_evidence.get("sourceRevision")
                ),
                payload={
                    "itemId": item_id,
                    "officialMetadata": _canonical(metadata),
                    "allowedSlots": allowed_slots,
                    "capabilities": _canonical(capabilities),
                    "equipmentUniqueness": _canonical(
                        payload.get("equipmentUniqueness")
                    ),
                },
                fact_specs=official_specs,
            )
        if structural_specs:
            add_artifact(
                source_type="season_rule",
                source_identity=_text(canonical_evidence.get("sourceIdentity")),
                artifact_source_revision=structural_revision,
                payload={
                    "subjectKey": subject,
                    "capabilities": {
                        key: capabilities[key]
                        for key in ("canEnchant", "canEmbellish")
                        if key in capabilities
                    },
                },
                fact_specs=structural_specs,
            )
        add_allowed_enhancement_rules(
            subject=subject,
            payload=payload,
            canonical_evidence=canonical_evidence,
        )
        socket_item = _canonical(row)
        official_evidence = _official_game_asset_evidence(
            payload,
            item_id,
        )
        if official_evidence:
            socket_item["sourceRevision"] = _text(
                official_evidence.get("sourceRevision")
            )
        eligibility = gear_socket_authority._active_pve_catalog_socket_eligibility(
            socket_item,
            sources_by_item_id.get(item_id, []),
            season_revision,
        )
        if isinstance(eligibility, Mapping):
            socket_item["socketEligibility"] = _canonical(eligibility)
            socket_eligibility_by_item_id[item_id] = _canonical(eligibility)
        add_socket_inputs(
            gear_socket_authority.derive_item_socket_observation_inputs(
                socket_item,
                season_revision,
            ),
            evidence_row=row,
            official_payload=is_official,
        )

    for index, row in enumerate(
        snapshot.get("variants") or () if "variants" in selected_categories else ()
    ):
        if (
            not isinstance(row, dict)
            or not _text(row.get("itemId"))
            or not _text(row.get("variantKey"))
        ):
            continue
        item_id = _text(row["itemId"])
        variant_key = _text(row["variantKey"])
        subject = f"item:{item_id}/variant:{variant_key}"
        row_subjects[("variants", index)] = subject
        subject_fact_types.setdefault(subject, set()).update(
            {
                "item_identity",
                "slot_compatibility",
                "variant_track",
                "static_stats",
                "socket_count",
                "enchant_capability",
                "embellishment_capability",
                "allowed_enhancement_options",
                "item_set_membership",
                "executable_item_options",
            }
        )
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        canonical_evidence = (
            payload.get("canonicalEvidence")
            if isinstance(payload.get("canonicalEvidence"), dict)
            else {}
        )
        evidence_revision = _text(canonical_evidence.get("sourceRevision"))
        evidence_type = _text(canonical_evidence.get("sourceType")).lower()
        evidence_scope = _text(
            canonical_evidence.get("sourceScope")
        ).lower()
        item_payload_for_evidence = (
            items_by_id.get(item_id, {}).get("payload")
            if isinstance(items_by_id.get(item_id, {}), dict)
            and isinstance(
                items_by_id.get(item_id, {}).get("payload"),
                dict,
            )
            else {}
        )
        battle_net_anchor = _official_game_asset_evidence(
            item_payload_for_evidence,
            item_id,
        )
        evidence_claims = {
            _text(value)
            for value in canonical_evidence.get("claims") or ()
            if _text(value)
        }
        evidence_verified = (
            _text(canonical_evidence.get("status")).lower() == "verified"
            and bool(_text(canonical_evidence.get("sourceIdentity")))
            and bool(evidence_revision)
            and evidence_scope == "exact_variant"
            and evidence_type in {"battle_net_item", "season_rule"}
            and (
                evidence_type != "battle_net_item"
                or (
                    isinstance(battle_net_anchor, Mapping)
                    and _text(
                        canonical_evidence.get("sourceIdentity")
                    )
                    == battle_net_anchor["sourceIdentity"]
                    and evidence_revision
                    == battle_net_anchor["sourceRevision"]
                )
            )
        )
        identity_evidence = (
            payload.get("identityEvidence")
            if isinstance(payload.get("identityEvidence"), dict)
            else {}
        )
        identity_source = _text(
            identity_evidence.get("sourceType")
        ).lower()
        identity_revision = _text(
            identity_evidence.get("sourceRevision")
        )
        identity_verified = (
            _text(identity_evidence.get("status")).lower() == "verified"
            and identity_source == "battle_net_item"
            and isinstance(battle_net_anchor, Mapping)
            and _text(identity_evidence.get("sourceIdentity"))
            == battle_net_anchor["sourceIdentity"]
            and identity_revision == battle_net_anchor["sourceRevision"]
            and _text(identity_evidence.get("sourceScope")).lower()
            == "exact_variant"
        )
        stat_evidence = (
            payload.get("statEvidence")
            if isinstance(payload.get("statEvidence"), dict)
            else {}
        )
        stat_revision = _text(stat_evidence.get("sourceRevision"))
        stat_claims = {
            _text(value)
            for value in stat_evidence.get("claims") or ()
            if _text(value)
        }
        stat_evidence_verified = (
            _text(stat_evidence.get("status")).lower() == "verified"
            and _text(stat_evidence.get("sourceType")).lower()
            == "simc_item_probe"
            and bool(_text(stat_evidence.get("sourceIdentity")))
            and bool(stat_revision)
            and _text(stat_evidence.get("sourceScope")).lower()
            == "exact_variant"
        )
        capabilities = (
            payload.get("capabilityOverrides")
            if isinstance(payload.get("capabilityOverrides"), dict)
            else {}
        )
        specs: list[tuple[str, str, Any, str]] = []
        if evidence_verified and "slot_compatibility" in evidence_claims and _text(row.get("slot")):
            specs.append(
                (
                    subject,
                    "slot_compatibility",
                    [_text(row.get("slot"))],
                    "exact_variant",
                )
            )
        for field, fact_type in (
            ("canEnchant", "enchant_capability"),
            ("canEmbellish", "embellishment_capability"),
        ):
            if (
                evidence_verified
                and fact_type in evidence_claims
                and field in capabilities
            ):
                specs.append(
                    (subject, fact_type, capabilities[field], "exact_variant")
                )
        # A capability override is trusted only when the same immutable
        # exact-variant evidence explicitly attests socket_count.  This is a
        # separate path from an equipped-gem sequence, which remains a raw
        # lower-bound constraint even when the variant also has stat evidence.
        socket_capacity = capabilities.get("socketCount")
        if (
            evidence_verified
            and "socket_count" in evidence_claims
            and isinstance(socket_capacity, int)
            and not isinstance(socket_capacity, bool)
            and socket_capacity >= 0
        ):
            specs.append(
                (subject, "socket_count", socket_capacity, "exact_variant")
            )
        if specs:
            add_artifact(
                source_type=evidence_type,
                source_identity=_text(canonical_evidence.get("sourceIdentity")),
                artifact_source_revision=evidence_revision,
                payload={
                    "subjectKey": subject,
                    "slot": _text(row.get("slot")),
                    "capabilities": {
                        key: capabilities[key]
                        for key in (
                            "socketCount",
                            "canEnchant",
                            "canEmbellish",
                        )
                        if (
                            key != "socketCount"
                            or "socket_count" in evidence_claims
                        )
                        if key in capabilities
                    },
                },
                fact_specs=specs,
            )
        if identity_verified:
            add_artifact(
                source_type=identity_source,
                source_identity=_text(
                    identity_evidence.get("sourceIdentity")
                ),
                artifact_source_revision=identity_revision,
                payload={
                    "itemId": item_id,
                    "variantKey": variant_key,
                },
                fact_specs=[
                    (
                        subject,
                        "item_identity",
                        {
                            "itemId": item_id,
                            "variantKey": variant_key,
                        },
                        "exact_variant",
                    )
                ],
            )
        add_allowed_enhancement_rules(
            subject=subject,
            payload=payload,
            canonical_evidence=canonical_evidence,
        )
        item_row = _canonical(items_by_id.get(item_id, {}))
        item_payload = (
            item_row.get("payload")
            if isinstance(item_row.get("payload"), dict)
            else {}
        )
        item_official_evidence = _official_game_asset_evidence(
            item_payload,
            item_id,
        )
        item_is_official = item_official_evidence is not None
        if item_official_evidence:
            # The derived exact-item input must carry the immutable official
            # revision, not this staging row's cache timestamp.
            item_row["sourceRevision"] = _text(
                item_official_evidence.get("sourceRevision")
            )
        eligibility = gear_socket_authority._active_pve_catalog_socket_eligibility(
            item_row,
            sources_by_item_id.get(item_id, []),
            season_revision,
        )
        if isinstance(eligibility, Mapping):
            item_row["socketEligibility"] = _canonical(eligibility)
        add_socket_inputs(
            gear_socket_authority.derive_variant_socket_observation_inputs(
                item_row,
                row,
                season_revision,
                socket_bonus_minimums,
            ),
            # An exact-variant socket claim can inherit a verified official
            # item payload.  The Artifact must validate that owning item, not
            # the observed variant row that only carries the claim subject.
            evidence_row=item_row,
            official_payload=item_is_official,
        )
        resolved_stats = payload.get("resolvedStats")
        stat_specs: list[tuple[str, str, Any, str]] = []
        if (
            isinstance(resolved_stats, dict)
            and resolved_stats
            and stat_evidence_verified
            and "static_stats" in stat_claims
        ):
            stat_specs.append(
                (subject, "static_stats", resolved_stats, "exact_variant")
            )
            if (
                _text(row.get("difficultyKey"))
                and "variant_track" in stat_claims
                and isinstance(row.get("itemLevel"), int)
                and not isinstance(row.get("itemLevel"), bool)
                and row["itemLevel"] > 0
            ):
                stat_specs.append(
                    (
                        subject,
                        "variant_track",
                        {
                            "itemId": item_id,
                            "variantKey": variant_key,
                            "track": _text(row.get("difficultyKey")),
                            "itemLevel": row["itemLevel"],
                        },
                        "exact_variant",
                    )
                )
        simc_options = row.get("simcOptions")
        if (
            stat_evidence_verified
            and "executable_item_options" in stat_claims
            and isinstance(simc_options, dict)
        ):
            validated_management = (
                gear_enhancement_management
                .project_validated_enhancement_management(
                    simc_options,
                    payload.get("enhancementManagement"),
                    gear_socket_authority.CAPABILITY_REVISION,
                )
            )
            executable_options = {
                key: _canonical(value)
                for key, value in simc_options.items()
                if (
                    key not in _ENHANCEMENT_SIMC_FIELDS
                    or validated_management is not None
                )
            }
            executable_value = {
                "itemId": item_id,
                "variantKey": variant_key,
                "options": executable_options,
            }
            if validated_management is not None:
                executable_value["enhancementManagement"] = (
                    validated_management
                )
            stat_specs.append(
                (
                    subject,
                    "executable_item_options",
                    executable_value,
                    "exact_variant",
                )
            )
        if stat_specs:
            add_artifact(
                source_type="simc_item_probe",
                source_identity=_text(stat_evidence.get("sourceIdentity")),
                artifact_source_revision=stat_revision,
                payload={
                    "itemId": item_id,
                    "variantKey": variant_key,
                    "staticStats": _canonical(resolved_stats),
                    "executableItemOptions": _canonical(simc_options),
                    "enhancementManagement": _canonical(
                        payload.get("enhancementManagement")
                    ),
                },
                fact_specs=stat_specs,
            )

    for index, row in enumerate(
        snapshot.get("options") or () if "options" in selected_categories else ()
    ):
        if not isinstance(row, dict) or not _text(row.get("optionId")):
            continue
        option_id = _text(row.get("optionKey") or row["optionId"])
        subject = f"option:{option_id}"
        row_subjects[("options", index)] = subject
        subject_fact_types.setdefault(subject, set()).add(
            "enhancement_option"
        )
        variant = variants_by_id.get(_text(row.get("variantId")), {})
        item_id = _text(variant.get("itemId")) or "release-option"
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        effect = (
            row.get("simcOptions")
            if isinstance(row.get("simcOptions"), dict) and row.get("simcOptions")
            else payload.get("effect")
        )
        canonical_option_type = (
            "gem"
            if _text(row.get("optionType")).lower() in {"socket", "gem"}
            else _text(row.get("optionType")).lower()
        )
        value = {
            "optionId": option_id,
            "optionType": canonical_option_type,
            "effect": _canonical(effect if isinstance(effect, dict) else {}),
            "applicableScopes": (
                ["*"]
                if canonical_option_type == "gem"
                else sorted(
                    {
                        _text(scope)
                        for scope in row.get("applicableSlots") or ()
                        if _text(scope)
                    }
                )
            ),
        }
        if isinstance(payload.get("statDeltas"), Mapping):
            value["statDeltas"] = _canonical(payload["statDeltas"])
        if _text(payload.get("uniqueGroup")):
            value["uniqueGroupId"] = _text(payload.get("uniqueGroup"))
        if (
            isinstance(payload.get("uniqueLimit"), int)
            and not isinstance(payload.get("uniqueLimit"), bool)
            and payload["uniqueLimit"] > 0
        ):
            value["uniqueLimit"] = payload["uniqueLimit"]
        evidence_source = _text(
            payload.get("evidenceSource")
            or payload.get("metadataSource")
            or payload.get("source")
        ).lower()
        option_evidence = (
            payload.get("optionEvidence")
            if isinstance(payload.get("optionEvidence"), dict)
            else {}
        )
        option_source_type = _text(option_evidence.get("sourceType")).lower()
        option_source_revision = _text(option_evidence.get("sourceRevision"))
        option_item_payload = (
            items_by_id.get(item_id, {}).get("payload")
            if isinstance(items_by_id.get(item_id, {}), dict)
            and isinstance(
                items_by_id.get(item_id, {}).get("payload"),
                dict,
            )
            else {}
        )
        option_battle_net_anchor = _official_game_asset_evidence(
            option_item_payload,
            item_id,
        )
        if (
            _text(option_evidence.get("status")).lower() == "verified"
            and option_source_type in {"battle_net_item", "simc_item_probe"}
            and bool(_text(option_evidence.get("sourceIdentity")))
            and bool(option_source_revision)
            and _text(option_evidence.get("sourceScope")).lower()
            in {"option", "exact_item", "exact_variant", "season_rule"}
            and (
                option_source_type != "battle_net_item"
                or (
                    isinstance(option_battle_net_anchor, Mapping)
                    and _text(option_evidence.get("sourceIdentity"))
                    == option_battle_net_anchor["sourceIdentity"]
                    and option_source_revision
                    == option_battle_net_anchor["sourceRevision"]
                )
            )
        ):
            add_artifact(
                source_type=option_source_type,
                source_identity=_text(option_evidence.get("sourceIdentity")),
                artifact_source_revision=option_source_revision,
                payload={
                    "itemId": item_id,
                    "enhancementOption": value,
                    "evidenceSource": evidence_source or option_source_type,
                },
                fact_specs=[
                    (
                        subject,
                        "enhancement_option",
                        value,
                        _text(option_evidence.get("sourceScope")).lower(),
                    ),
                ],
            )

    # Gap recovery can supply a narrow, immutable input bundle for a candidate
    # recompile.  It is deliberately an explicit compiler input: Evidence
    # Store persistence alone must not silently change a candidate release.
    supplied_artifacts: dict[str, dict[str, Any]] = {}
    for raw_artifact in extra_artifacts:
        if not isinstance(raw_artifact, Mapping):
            raise GearReleaseIntegrityError("candidate evidence Artifact must be an object")
        try:
            artifact = gear_evidence_registry.build_evidence_artifact(
                source_type=raw_artifact.get("sourceType"),
                source_identity=raw_artifact.get("sourceIdentity"),
                source_revision=raw_artifact.get("sourceRevision"),
                season_revision=raw_artifact.get("seasonRevision"),
                captured_at=raw_artifact.get("capturedAt"),
                payload=raw_artifact.get("payload"),
            )
        except ValueError as error:
            raise GearReleaseIntegrityError("candidate evidence Artifact is invalid") from error
        if _canonical(raw_artifact) != artifact or artifact["seasonRevision"] != season_revision:
            raise GearReleaseIntegrityError("candidate evidence Artifact is not release-fenced")
        existing = supplied_artifacts.setdefault(artifact["artifactId"], artifact)
        if existing != artifact:
            raise GearReleaseIntegrityError("candidate evidence Artifact identity conflicts")

    supplied_observations: dict[str, dict[str, Any]] = {}
    for raw_observation in extra_observations:
        if not isinstance(raw_observation, Mapping):
            raise GearReleaseIntegrityError("candidate evidence Observation must be an object")
        try:
            observation = gear_evidence_registry.build_evidence_observation(
                artifact_id=raw_observation.get("artifactId"),
                subject_key=raw_observation.get("subjectKey"),
                fact_type=raw_observation.get("factType"),
                observed_value=raw_observation.get("observedValue"),
                parser_revision=raw_observation.get("parserRevision"),
                source_scope=raw_observation.get("sourceScope"),
                status=raw_observation.get("status"),
            )
        except ValueError as error:
            raise GearReleaseIntegrityError("candidate evidence Observation is invalid") from error
        artifact = supplied_artifacts.get(observation["artifactId"])
        policy = gear_fact_compiler.FACT_POLICIES.get(observation["factType"]) or {}
        if (
            _canonical(raw_observation) != observation
            or artifact is None
            or observation["subjectKey"] not in subject_fact_types
            or observation["factType"] not in subject_fact_types[observation["subjectKey"]]
            or artifact["sourceType"] not in policy.get("allowedSources", ())
            or observation["sourceScope"] not in policy.get("sourceScopes", ())
        ):
            raise GearReleaseIntegrityError("candidate evidence Observation is outside the candidate contract")
        existing = supplied_observations.setdefault(observation["observationId"], observation)
        if existing != observation:
            raise GearReleaseIntegrityError("candidate evidence Observation identity conflicts")

    returned_artifacts_by_id = {
        artifact["artifactId"]: artifact for artifact in artifacts
    }
    for artifact_id, artifact in supplied_artifacts.items():
        existing = returned_artifacts_by_id.setdefault(artifact_id, artifact)
        if existing != artifact:
            raise GearReleaseIntegrityError("candidate evidence conflicts with staging Artifact")
    returned_observations_by_id = {
        observation["observationId"]: observation for observation in observations
    }
    for observation_id, observation in supplied_observations.items():
        existing = returned_observations_by_id.setdefault(observation_id, observation)
        if existing != observation:
            raise GearReleaseIntegrityError("candidate evidence conflicts with staging Observation")
    artifacts = [
        returned_artifacts_by_id[artifact_id]
        for artifact_id in sorted(returned_artifacts_by_id)
    ]
    observations = [
        returned_observations_by_id[observation_id]
        for observation_id in sorted(returned_observations_by_id)
    ]
    context_artifacts_by_id: dict[str, Mapping[str, Any]] = {}
    for raw_artifact in compiler_context_artifacts:
        if not isinstance(raw_artifact, Mapping) or not _text(
            raw_artifact.get("artifactId")
        ):
            raise GearReleaseIntegrityError(
                "compiler context Artifact is invalid"
            )
        context_artifacts_by_id[_text(raw_artifact["artifactId"])] = raw_artifact
    context_observations_by_id: dict[str, Mapping[str, Any]] = {}
    for raw_observation in compiler_context_observations:
        if not isinstance(raw_observation, Mapping) or not _text(
            raw_observation.get("observationId")
        ):
            raise GearReleaseIntegrityError(
                "compiler context Observation is invalid"
            )
        context_observations_by_id[
            _text(raw_observation["observationId"])
        ] = raw_observation
    if isinstance(compiler_context_facts, Mapping):
        # The streaming coordinator constructs this compact Fact index once.
        # Reuse it by reference for every equipment batch: rebuilding an
        # equally large dictionary would reintroduce the all-option CPU/memory
        # slope that the bounded path removes.
        context_facts_by_subject_fact = compiler_context_facts
    else:
        context_facts_by_subject_fact: dict[
            tuple[str, str], Mapping[str, Any]
        ] = {}
        for raw_fact in compiler_context_facts:
            if not isinstance(raw_fact, Mapping):
                raise GearReleaseIntegrityError("compiler context Fact is invalid")
            subject_key = _text(raw_fact.get("subjectKey"))
            fact_type = _text(raw_fact.get("factType"))
            if not subject_key or not fact_type:
                raise GearReleaseIntegrityError("compiler context Fact is invalid")
            identity = (subject_key, fact_type)
            existing = context_facts_by_subject_fact.setdefault(identity, raw_fact)
            if _canonical(existing) != _canonical(raw_fact):
                raise GearReleaseIntegrityError("compiler context Fact conflicts")
    compiler_artifacts_by_id = dict(context_artifacts_by_id)
    for artifact in artifacts:
        artifact_id = _text(artifact.get("artifactId"))
        existing = compiler_artifacts_by_id.setdefault(artifact_id, artifact)
        if _canonical(existing) != _canonical(artifact):
            raise GearReleaseIntegrityError(
                "compiler context conflicts with staging Artifact"
            )
    compiler_observations_by_id = dict(context_observations_by_id)
    for observation in observations:
        observation_id = _text(observation.get("observationId"))
        existing = compiler_observations_by_id.setdefault(
            observation_id,
            observation,
        )
        if _canonical(existing) != _canonical(observation):
            raise GearReleaseIntegrityError(
                "compiler context conflicts with staging Observation"
            )
    # Compile the entire candidate universe from one immutable Evidence index.
    # Allowed-option rules can still resolve referenced option subjects through
    # that same index without rescanning every Artifact and Observation for
    # every equipment row.
    facts = gear_fact_compiler.compile_facts_by_subject(
        season_revision=season_revision,
        observations=[
            compiler_observations_by_id[observation_id]
            for observation_id in sorted(compiler_observations_by_id)
        ],
        artifacts=[
            compiler_artifacts_by_id[artifact_id]
            for artifact_id in sorted(compiler_artifacts_by_id)
        ],
        fact_types_by_subject=subject_fact_types,
        precompiled_facts_by_subject_fact=context_facts_by_subject_fact,
    )
    return {
        "artifacts": sorted(artifacts, key=lambda row: row["artifactId"]),
        "observations": sorted(
            observations, key=lambda row: row["observationId"]
        ),
        "facts": sorted(
            facts,
            key=lambda row: (
                row["subjectKey"],
                row["factType"],
                row["factKey"],
            ),
        ),
        "rowSubjects": row_subjects,
        "socketClaimsBySubject": {
            subject: sorted(
                claims,
                key=lambda claim: (
                    claim["source"],
                    claim["sourceRevision"],
                    claim["scope"],
                    claim["minimumTotal"],
                ),
            )
            for subject, claims in socket_claims_by_subject.items()
        },
        "socketEligibilityByItemId": socket_eligibility_by_item_id,
        "expectedFactTypesBySubject": {
            subject: sorted(fact_types)
            for subject, fact_types in subject_fact_types.items()
        },
    }


def _evidence_batch_slices(
    rows: Iterable[Mapping[str, Any]],
    batch_size: int,
) -> Iterable[tuple[int, list[Mapping[str, Any]]]]:
    values = list(rows)
    for offset in range(0, len(values), batch_size):
        yield offset, values[offset : offset + batch_size]


def _stream_release_evidence_batches(
    snapshot: dict[str, Any],
    *,
    season_revision: str,
    source_revision: str,
    captured_at: str,
    socket_bonus_minimums: Mapping[str, Any],
    socket_bonus_evidence: Mapping[str, Any],
    batch_size: int,
) -> Iterable[tuple[str, int, list[Mapping[str, Any]], dict[str, Any]]]:
    """Compile one deterministic release category batch at a time.

    Option evidence is the only cross-subject compiler input: it is built once
    and then read by the allowed-option policy for item/variant batches.  It is
    deliberately returned only in its own batch so append-only persistence does
    not duplicate immutable Artifact or Observation rows.
    """

    if batch_size <= 0:
        raise GearReleaseIntegrityError(
            "evidence_batch_size must be a positive integer"
        )

    option_context_facts: dict[tuple[str, str], Mapping[str, Any]] = {}

    def batch_snapshot(
        category: str,
        rows: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        return {
            **snapshot,
            category: rows,
        }

    # Compile options first so later allowed-option rules read the exact same
    # immutable evidence universe as the old one-shot compiler.
    for offset, rows in _evidence_batch_slices(
        snapshot.get("options") or (),
        batch_size,
    ):
        compiled = _compile_release_gear_evidence(
            batch_snapshot("options", rows),
            season_revision=season_revision,
            source_revision=source_revision,
            captured_at=captured_at,
            socket_bonus_minimums=socket_bonus_minimums,
            socket_bonus_evidence=socket_bonus_evidence,
            categories=("options",),
        )
        for fact in compiled["facts"]:
            if _text(fact.get("factType")) != "enhancement_option":
                continue
            identity = (_text(fact.get("subjectKey")), "enhancement_option")
            existing = option_context_facts.setdefault(identity, fact)
            if _canonical(existing) != _canonical(fact):
                raise GearReleaseIntegrityError("compiler option Fact conflicts")
        yield "options", offset, rows, compiled

    # Variants consume item provenance.  Keep the source items untouched until
    # every variant batch has compiled; projection happens only after a batch
    # has already consumed its raw input.
    for category in ("variants", "items"):
        for offset, rows in _evidence_batch_slices(
            snapshot.get(category) or (),
            batch_size,
        ):
            compiled = _compile_release_gear_evidence(
                batch_snapshot(category, rows),
                season_revision=season_revision,
                source_revision=source_revision,
                captured_at=captured_at,
                socket_bonus_minimums=socket_bonus_minimums,
                socket_bonus_evidence=socket_bonus_evidence,
                categories=(category,),
                compiler_context_facts=option_context_facts,
            )
            yield category, offset, rows, compiled


def _project_release_evidence_batch(
    snapshot: dict[str, Any],
    *,
    category: str,
    offset: int,
    rows: list[Mapping[str, Any]],
    compiled: Mapping[str, Any],
) -> None:
    """Apply one batch to the single release snapshot without cloning it all."""

    projection_input = {
        "items": rows if category == "items" else [],
        "sources": [],
        "variants": rows if category == "variants" else [],
        "options": rows if category == "options" else [],
    }
    projected = _project_canonical_facts(
        projection_input,
        compiled.get("facts") or (),
        compiled.get("rowSubjects") or {},
        socket_claims_by_subject=(
            compiled.get("socketClaimsBySubject") or {}
        ),
        socket_eligibility_by_item_id=(
            compiled.get("socketEligibilityByItemId") or {}
        ),
    )
    snapshot[category][offset : offset + len(rows)] = projected[category]


def _evidence_receipt_identity(owner: str, row: Mapping[str, Any]) -> Any:
    if owner == "artifacts":
        return _text(row.get("artifactId"))
    if owner == "observations":
        return _text(row.get("observationId"))
    if owner == "facts":
        return (
            _text(row.get("factKey")),
            _text(row.get("factValueHash")),
            _text(row.get("provenanceHash")),
        )
    return _text(row.get("gapKey"))


class _StreamingEvidenceReceipt:
    """Small deterministic receipt for an append-only streaming build."""

    schema_revision = "gear-evidence-receipt-v2"

    def __init__(self) -> None:
        self._owners = {
            owner: {"count": 0, "sequenceDigest": _canonical_digest({"owner": owner})}
            for owner in ("artifacts", "observations", "facts", "gaps")
        }
        self.inserted_gaps = 0
        self.reused_gaps = 0

    def record(self, owner: str, rows: Iterable[Mapping[str, Any]]) -> None:
        state = self._owners[owner]
        for row in rows:
            identity = _evidence_receipt_identity(owner, row)
            if not identity or (
                isinstance(identity, tuple) and not all(identity)
            ):
                raise GearReleaseIntegrityError(
                    "streaming evidence receipt identity is incomplete"
                )
            state["sequenceDigest"] = _canonical_digest(
                {
                    "owner": owner,
                    "previous": state["sequenceDigest"],
                    "identity": identity,
                }
            )
            state["count"] += 1

    def record_persistence(
        self,
        result: Mapping[str, Any],
        *,
        artifacts: list[Mapping[str, Any]],
        observations: list[Mapping[str, Any]],
        facts: list[Mapping[str, Any]],
        gaps: list[Mapping[str, Any]],
    ) -> None:
        expected_rows = {
            "artifacts": artifacts,
            "observations": observations,
            "facts": facts,
            "gaps": gaps,
        }
        for owner, rows in expected_rows.items():
            persisted = result.get(owner) if isinstance(result, Mapping) else {}
            persisted = persisted if isinstance(persisted, Mapping) else {}
            count = (
                _int(persisted.get("requested"))
                if owner == "gaps"
                else _int(persisted.get("persisted"))
            )
            if count != len(rows):
                raise GearReleaseIntegrityError(
                    "streaming evidence persistence receipt is incomplete"
                )
            self.record(owner, rows)
        gaps_result = result.get("gaps") if isinstance(result, Mapping) else {}
        gaps_result = gaps_result if isinstance(gaps_result, Mapping) else {}
        self.inserted_gaps += _int(gaps_result.get("inserted"))
        self.reused_gaps += _int(gaps_result.get("reused"))

    def compilation(self) -> dict[str, Any]:
        return {
            owner: {
                "count": state["count"],
                "sequenceDigest": state["sequenceDigest"],
            }
            for owner, state in self._owners.items()
        }

    def persistence(self) -> dict[str, Any]:
        result = {
            owner: {
                "persisted": state["count"],
                "sequenceDigest": state["sequenceDigest"],
            }
            for owner, state in self._owners.items()
        }
        result["gaps"].update(
            {
                "requested": self._owners["gaps"]["count"],
                "inserted": self.inserted_gaps,
                "reused": self.reused_gaps,
            }
        )
        return result


def _canonical_fact_digest_from_snapshot(snapshot: Mapping[str, Any]) -> str:
    """Hash canonical facts without copying the whole registry into another list.

    The external merge ordering preserves the v1 list digest exactly, including
    stable ordering for otherwise-identical facts, while keeping one bounded
    sort run and merge fan-in in Python memory at a time.  It deliberately uses
    ordinary temporary files rather than SQLite: release construction must
    remain valid while the runtime is PostgreSQL-only.
    """

    run_size = 1024
    merge_fan_in = 32

    def write_record(output, record: tuple[str, str, str, int, str]) -> None:
        output.write(
            json.dumps(
                record,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        )

    def read_record(source) -> tuple[str, str, str, int, str] | None:
        line = source.readline()
        if not line:
            return None
        row = json.loads(line)
        if not isinstance(row, list) or len(row) != 5:
            raise GearReleaseIntegrityError(
                "canonical Fact digest sort run is malformed"
            )
        return (
            _text(row[0]),
            _text(row[1]),
            _text(row[2]),
            _int(row[3]),
            _text(row[4]),
        )

    def merge_runs(paths: list[str], output) -> None:
        sources = [open(path, encoding="utf-8") for path in paths]
        try:
            heap: list[tuple[tuple[str, str, str, int], int, str]] = []
            for index, source in enumerate(sources):
                record = read_record(source)
                if record is not None:
                    heapq.heappush(
                        heap,
                        (record[:4], index, record[4]),
                    )
            while heap:
                sort_key, index, payload = heapq.heappop(heap)
                write_record(output, (*sort_key, payload))
                record = read_record(sources[index])
                if record is not None:
                    heapq.heappush(
                        heap,
                        (record[:4], index, record[4]),
                    )
        finally:
            for source in sources:
                source.close()

    with tempfile.TemporaryDirectory(prefix="wow-gear-canonical-facts-") as directory:
        runs: list[str] = []
        buffered: list[tuple[str, str, str, int, str]] = []
        sequence = 0

        def flush_run() -> None:
            if not buffered:
                return
            buffered.sort(key=lambda record: record[:4])
            path = os.path.join(directory, f"run-{len(runs):06d}.jsonl")
            with open(path, "w", encoding="utf-8") as output:
                for record in buffered:
                    write_record(output, record)
            runs.append(path)
            buffered.clear()

        for category in ("items", "variants", "options"):
            for row in snapshot.get(category) or ():
                if not isinstance(row, Mapping):
                    continue
                payload = row.get("payload")
                if not isinstance(payload, Mapping):
                    continue
                for fact in payload.get("canonicalFacts") or ():
                    if not isinstance(fact, Mapping):
                        continue
                    digest_row = {
                        "factKey": _text(fact.get("factKey")),
                        "status": _text(fact.get("status")),
                        "factValueHash": _text(fact.get("factValueHash")),
                        "provenanceHash": _text(fact.get("provenanceHash")),
                    }
                    buffered.append(
                        (
                            digest_row["factKey"],
                            digest_row["factValueHash"],
                            digest_row["provenanceHash"],
                            sequence,
                            json.dumps(
                                digest_row,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                        )
                    )
                    sequence += 1
                    if len(buffered) == run_size:
                        flush_run()
        flush_run()
        merge_round = 0
        while len(runs) > merge_fan_in:
            merged_runs: list[str] = []
            for offset in range(0, len(runs), merge_fan_in):
                group = runs[offset:offset + merge_fan_in]
                path = os.path.join(
                    directory,
                    f"merge-{merge_round:02d}-{len(merged_runs):06d}.jsonl",
                )
                with open(path, "w", encoding="utf-8") as output:
                    merge_runs(group, output)
                for source in group:
                    os.remove(source)
                merged_runs.append(path)
            runs = merged_runs
            merge_round += 1
        digest = hashlib.sha256()
        digest.update(b"[")
        first = True
        if runs:
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as merged:
                merge_runs(runs, merged)
                merged.seek(0)
                while record := read_record(merged):
                    if not first:
                        digest.update(b",")
                    digest.update(record[4].encode("utf-8"))
                    first = False
        digest.update(b"]")
    return "sha256:" + digest.hexdigest()


def _project_canonical_facts(
    snapshot: dict[str, Any],
    facts: Iterable[Mapping[str, Any]],
    row_subjects: Mapping[tuple[str, int], str],
    *,
    socket_claims_by_subject: Mapping[str, list[dict[str, Any]]],
    socket_eligibility_by_item_id: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    projected = _canonical(snapshot)
    facts_by_subject: dict[str, list[Mapping[str, Any]]] = {}
    for fact in facts:
        facts_by_subject.setdefault(_text(fact.get("subjectKey")), []).append(fact)
    for category in ("items", "variants", "options"):
        for index, row in enumerate(projected.get(category) or ()):
            if not isinstance(row, dict):
                continue
            subject = _text(row_subjects.get((category, index)))
            if not subject:
                continue
            subject_facts = facts_by_subject.get(subject, [])
            payload = (
                _canonical(row.get("payload"))
                if isinstance(row.get("payload"), dict)
                else {}
            )
            payload["canonicalFacts"] = sorted(
                [_release_fact_projection(fact) for fact in subject_facts],
                key=lambda fact: (fact["factType"], fact["factKey"]),
            )
            facts_by_type = {
                _text(fact.get("factType")): fact
                for fact in subject_facts
            }
            capability_field = (
                "baseCapabilities"
                if category == "items"
                else "capabilityOverrides"
            )
            if category in {"items", "variants"}:
                capabilities = (
                    _canonical(payload.get(capability_field))
                    if isinstance(payload.get(capability_field), dict)
                    else {}
                )
                for fact_type, field in (
                    ("socket_count", "socketCount"),
                    ("enchant_capability", "canEnchant"),
                    ("embellishment_capability", "canEmbellish"),
                ):
                    fact = facts_by_type.get(fact_type, {})
                    if fact.get("status") == "verified":
                        capabilities[field] = _canonical(fact.get("value"))
                    else:
                        capabilities.pop(field, None)
                payload[capability_field] = capabilities
                socket_fact = facts_by_type.get("socket_count", {})
                if socket_fact.get("status") == "verified":
                    payload["socketEvidence"] = {
                        "schemaRevision": gear_socket_authority.SOCKET_FACT_SCHEMA_REVISION,
                        "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
                        "minimumTotal": _int(socket_fact.get("value")),
                        "claims": _canonical(
                            socket_claims_by_subject.get(subject, [])
                        ),
                        "canonicalFactRef": {
                            "factKey": _text(socket_fact.get("factKey")),
                            "factValueHash": _text(
                                socket_fact.get("factValueHash")
                            ),
                            "provenanceHash": _text(
                                socket_fact.get("provenanceHash")
                            ),
                        },
                    }
                else:
                    payload.pop("socketEvidence", None)
                static_fact = facts_by_type.get("static_stats", {})
                if static_fact.get("status") == "verified":
                    payload["resolvedStats"] = _canonical(
                        static_fact.get("value")
                    )
                elif category == "variants":
                    payload.pop("resolvedStats", None)
            if category == "items":
                eligibility = socket_eligibility_by_item_id.get(
                    _text(row.get("itemId"))
                )
                if isinstance(eligibility, Mapping):
                    payload["socketEligibility"] = _canonical(eligibility)
            if category == "options":
                option_fact = facts_by_type.get("enhancement_option", {})
                if option_fact.get("status") != "verified":
                    row["status"] = "blocked"
                    row["isVisible"] = False
            row["payload"] = payload
    return projected


def _project_canonical_enhancement_management(
    snapshot: dict[str, Any],
    *,
    capability_revision: str,
    in_place: bool = False,
) -> dict[str, Any]:
    """Project field governance only from sealed canonical Facts and explicit echoes."""

    projected = snapshot if in_place else _canonical(snapshot)
    if capability_revision != gear_socket_authority.CAPABILITY_REVISION:
        for variant in projected.get("variants") or ():
            if isinstance(variant, dict):
                payload = (
                    _canonical(variant.get("payload"))
                    if isinstance(variant.get("payload"), dict)
                    else {}
                )
                payload.pop("enhancementManagement", None)
                variant["payload"] = payload
        return projected

    def verified_facts(row: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
        payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
        return {
            _text(fact.get("factType")): fact
            for fact in payload.get("canonicalFacts") or ()
            if isinstance(fact, Mapping) and fact.get("status") == "verified"
        }

    canonical_options: list[dict[str, Any]] = []
    for option in projected.get("options") or ():
        if not isinstance(option, dict):
            continue
        fact = verified_facts(option).get("enhancement_option")
        value = fact.get("value") if isinstance(fact, Mapping) else {}
        if not isinstance(value, Mapping):
            continue
        if _text(option.get("optionType")).lower() in {"socket", "gem"}:
            option["applicableSlots"] = ["*"]
        canonical_options.append(
            {
                "optionType": (
                    "gem"
                    if _text(value.get("optionType")).lower() in {"socket", "gem"}
                    else _text(value.get("optionType")).lower()
                ),
                "effect": _canonical(
                    value.get("effect")
                    if isinstance(value.get("effect"), Mapping)
                    else {}
                ),
                "scopes": {
                    normalize_slot(scope)
                    for scope in value.get("applicableScopes") or ()
                    if _text(scope)
                },
            }
        )

    items_by_id = {
        _text(item.get("itemId")): item
        for item in projected.get("items") or ()
        if isinstance(item, dict) and _text(item.get("itemId"))
    }

    def option_applies(option: Mapping[str, Any], slot: str) -> bool:
        scopes = option.get("scopes") if isinstance(option.get("scopes"), set) else set()
        return not scopes or "*" in scopes or slot in scopes

    def verified_simc_echo(
        variant: Mapping[str, Any],
        payload: Mapping[str, Any],
        field: str,
        raw_value: str,
    ) -> bool:
        evidence = (
            payload.get("statEvidence")
            if isinstance(payload.get("statEvidence"), Mapping)
            else {}
        )
        claims = {_text(value) for value in evidence.get("claims") or ()}
        if not (
            evidence.get("status") == "verified"
            and evidence.get("sourceType") == "simc_item_probe"
            and _text(evidence.get("sourceIdentity"))
            and _text(evidence.get("sourceRevision"))
            and "enhancement_echo" in claims
        ):
            return False
        encoded = payload.get("simcEncodedItem")
        if not isinstance(encoded, str) or encoded != encoded.strip():
            return False
        encoded_options = simc_encoded_item_options(encoded)
        raw_options = (
            variant.get("simcOptions")
            if isinstance(variant.get("simcOptions"), Mapping)
            else {}
        )
        return (
            _text(encoded_options.get("id")) == _text(variant.get("itemId"))
            and _int(encoded_options.get("ilevel")) == _int(variant.get("itemLevel"))
            and normalize_option_value(encoded_options.get(field))
            == normalize_option_value(raw_value)
            and normalize_option_value(raw_options.get(field))
            == normalize_option_value(raw_value)
        )

    for variant in projected.get("variants") or ():
        if not isinstance(variant, dict):
            continue
        payload = (
            _canonical(variant.get("payload"))
            if isinstance(variant.get("payload"), dict)
            else {}
        )
        payload.pop("editorManagedSimcFields", None)
        payload.pop("enhancementManagement", None)
        item = items_by_id.get(_text(variant.get("itemId")), {})
        item_facts = verified_facts(item)
        variant_facts = verified_facts(variant)
        slot_fact = variant_facts.get("slot_compatibility")
        slot_values = (
            slot_fact.get("value")
            if isinstance(slot_fact, Mapping)
            and isinstance(slot_fact.get("value"), list)
            else []
        )
        if not slot_values:
            item_slot_fact = item_facts.get("slot_compatibility")
            slot_values = (
                item_slot_fact.get("value")
                if isinstance(item_slot_fact, Mapping)
                and isinstance(item_slot_fact.get("value"), list)
                else []
            )
        slot = normalize_slot(slot_values[0] if len(slot_values) == 1 else "")
        socket_fact = variant_facts.get("socket_count") or item_facts.get("socket_count")
        enchant_fact = (
            variant_facts.get("enchant_capability")
            or item_facts.get("enchant_capability")
        )
        embellish_fact = (
            variant_facts.get("embellishment_capability")
            or item_facts.get("embellishment_capability")
        )
        socket_count = (
            _int(socket_fact.get("value"))
            if isinstance(socket_fact, Mapping)
            else 0
        )
        can_enchant = (
            enchant_fact.get("value") is True
            if isinstance(enchant_fact, Mapping)
            else False
        )
        can_embellish = (
            embellish_fact.get("value") is True
            if isinstance(embellish_fact, Mapping)
            else False
        )
        raw_options = (
            variant.get("simcOptions")
            if isinstance(variant.get("simcOptions"), dict)
            else {}
        )
        classifications: dict[str, str] = {}
        for field in _ENHANCEMENT_SIMC_FIELDS:
            raw_value = _text(raw_options.get(field))
            if not raw_value:
                continue
            editor_managed = False
            if field in _GEM_SIMC_SEQUENCE_FIELDS:
                editor_managed = socket_count > 0 and any(
                    option["optionType"] == "gem"
                    for option in canonical_options
                )
            elif field == "enchant_id" and "/" not in raw_value:
                editor_managed = can_enchant and any(
                    option["optionType"] in {"enchant", "runeforge"}
                    and option_applies(option, slot)
                    and normalize_option_value(option["effect"].get(field))
                    == normalize_option_value(raw_value)
                    for option in canonical_options
                )
            elif field == "embellishment":
                editor_managed = can_embellish and any(
                    option["optionType"] == "embellishment"
                    and option_applies(option, slot)
                    and normalize_option_value(option["effect"].get(field))
                    == normalize_option_value(raw_value)
                    for option in canonical_options
                )
            classifications[field] = (
                "editor_managed"
                if editor_managed
                else "unresolved_drop"
                if field in _GEM_SIMC_SEQUENCE_FIELDS
                else "source_only"
                if verified_simc_echo(variant, payload, field, raw_value)
                else "unresolved_drop"
            )
        management = gear_enhancement_management.seal_enhancement_management(
            raw_options,
            classifications,
            capability_revision,
        )
        if management:
            payload["enhancementManagement"] = management
        variant["payload"] = payload
    return projected


def _project_socket_facts_into_release_payloads(
    snapshot: dict[str, Any],
    *,
    in_place: bool = False,
) -> dict[str, Any]:
    """Move materialized socket facts into release payloads.

    The default protects regular callers.  The legacy shadow pipeline owns its
    compact intermediate and may safely reuse it in place.
    """

    projected = snapshot if in_place else _canonical(snapshot)
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
            if category == "items":
                eligibility = row.pop("socketEligibility", None)
                payload.pop("socketEligibility", None)
                if isinstance(eligibility, dict):
                    payload["socketEligibility"] = eligibility
            row["payload"] = payload
    return projected


def _materialize_enhancement_management(
    snapshot: dict[str, Any],
    capability_revision: str,
    *,
    in_place: bool = False,
) -> dict[str, Any]:
    """Seal v2 field governance without treating absence as trusted source data."""

    materialized = snapshot if in_place else _canonical(snapshot)
    items_by_id = {
        _text(row.get("itemId")): row
        for row in materialized.get("items") or []
        if isinstance(row, dict) and _text(row.get("itemId"))
    }

    def canonical_simc_options(options: Any) -> dict[str, Any] | None:
        values = options if isinstance(options, dict) else {}
        normalized = {}
        for field, value in values.items():
            if not isinstance(field, str) or not field or field != field.strip():
                return None
            normalized_field = field
            if not re.fullmatch(r"[A-Za-z0-9_]+", normalized_field):
                return None
            canonical_field = (
                "id"
                if normalized_field in {"id", "item_id", "itemId"}
                else normalized_field
            )
            if canonical_field in normalized:
                return None
            raw_value = str(value if value is not None else "")
            if raw_value != raw_value.strip():
                return None
            normalized_value = normalize_option_value(value)
            if not normalized_value or raw_value != normalized_value:
                return None
            if canonical_field == "bonus_id":
                tokens = normalized_value.split("/") if normalized_value else []
                normalized[canonical_field] = (
                    sorted(tokens) if tokens and all(tokens) else []
                )
            elif canonical_field == "ilevel":
                normalized[canonical_field] = normalized_value
            else:
                normalized[canonical_field] = normalized_value
        return normalized

    def exact_encoded_simc_options(encoded: str) -> dict[str, str] | None:
        seen: dict[str, str] = {}
        for index, part in enumerate(encoded.split(",")):
            if "=" not in part:
                if index == 0 and part.strip():
                    continue
                return None
            raw_key, raw_value = part.split("=", 1)
            if (
                part != part.strip()
                or raw_key != raw_key.strip()
                or raw_value != raw_value.strip()
            ):
                return None
            key = raw_key
            normalized_key = re.sub(r"[^A-Za-z0-9_]+", "", key)
            normalized_value = normalize_option_value(raw_value)
            canonical_key = (
                "id" if normalized_key in {"id", "item_id", "itemId"} else normalized_key
            )
            if (
                not normalized_key
                or key != normalized_key
                or not normalized_value
                or raw_value != normalized_value
                or canonical_key in seen
            ):
                return None
            seen[canonical_key] = normalized_value
        parsed = simc_encoded_item_options(encoded)
        return parsed if parsed == seen else None

    def verified_official_gem_option(
        gem_id: str,
    ) -> tuple[str, dict[str, Any] | None]:
        """Project an observed gem only from already-cached official item facts."""

        item = items_by_id.get(gem_id)
        item = item if isinstance(item, dict) else {}
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        metadata = payload.get("_metadata") if isinstance(payload.get("_metadata"), dict) else {}
        game_asset = metadata.get("gameAsset") if isinstance(metadata.get("gameAsset"), dict) else {}
        item_class = payload.get("item_class") if isinstance(payload.get("item_class"), dict) else {}
        preview = payload.get("preview_item") if isinstance(payload.get("preview_item"), dict) else {}
        gem_properties = preview.get("gem_properties") if isinstance(preview.get("gem_properties"), dict) else {}
        links = payload.get("_links") if isinstance(payload.get("_links"), dict) else {}
        self_link = links.get("self") if isinstance(links.get("self"), dict) else {}
        evidence_ref = _text(self_link.get("href"))
        metadata_source = _text(metadata.get("source"))
        icon_url = _text(metadata.get("iconUrl") or payload.get("iconUrl"))
        stat_summary = _text(gem_properties.get("effect"))
        display_name = _text(item.get("name") or payload.get("name") or preview.get("name"))
        parsed_evidence_ref = urlparse(evidence_ref)
        evidence_host = _text(parsed_evidence_ref.hostname).lower()
        evidence_path = parsed_evidence_ref.path.rstrip("/")
        metadata_verified = (
            _text(game_asset.get("status")).lower() == "verified"
            and _text(game_asset.get("source")).lower() == "blizzard"
        )
        if (
            not metadata_verified
            or metadata_source != _BATTLE_NET_GAME_DATA_API
            or _int(item_class.get("id")) != 3
            or not display_name
            or not stat_summary
            or not icon_url
            or parsed_evidence_ref.scheme.lower() != "https"
            or not (
                evidence_host == "api.blizzard.com"
                or evidence_host.endswith(".api.blizzard.com")
            )
            or evidence_path != f"/data/wow/item/{gem_id}"
        ):
            return "unavailable", None

        option_payload: dict[str, Any] = {
            "source": "official_observed_gem_release_projection",
            "status": "verified",
            "gemItemId": gem_id,
            "gemItemIds": [gem_id],
            "displayName": display_name,
            "displayLabel": stat_summary,
            "displayKind": "stat",
            "displayStatus": "verified",
            "statSummary": stat_summary,
            "iconUrl": icon_url,
            "metadataStatus": "verified",
            "metadataSource": metadata_source,
            "evidenceSource": "blizzard_game_data_api",
            "evidenceRef": evidence_ref,
        }
        raw_limit_category = preview.get("limit_category")
        limit_categories: list[str] = []
        limit_category_invalid = False
        if raw_limit_category is None:
            pass
        elif isinstance(raw_limit_category, str):
            if raw_limit_category.strip():
                limit_categories.append(raw_limit_category.strip())
        elif isinstance(raw_limit_category, dict):
            supported_fields = (
                "display_string",
                "displayString",
                "name",
                "label",
                "text",
                "description",
            )
            for field in supported_fields:
                if field not in raw_limit_category:
                    continue
                field_value = raw_limit_category.get(field)
                if field_value is None or field_value == "":
                    continue
                if not isinstance(field_value, str) or not field_value.strip():
                    limit_category_invalid = True
                    break
                limit_categories.append(field_value.strip())
            if raw_limit_category and not limit_categories:
                limit_category_invalid = True
        else:
            limit_category_invalid = "limit_category" in preview

        parsed_limit_categories: set[tuple[str, int]] = set()
        for limit_category in limit_categories:
            limit_match = re.fullmatch(
                r"\s*(?:unique[\s_-]*equipped|装备唯一|唯一装备|裝備唯一|唯一裝備)"
                r"\s*[:：]\s*"
                r"(?P<category>.+?)\s*[\(（]\s*(?P<limit>[1-9]\d*)\s*[\)）]\s*",
                limit_category,
                flags=re.IGNORECASE,
            )
            if not limit_match:
                limit_category_invalid = True
                break
            unique_limit = _int(limit_match.group("limit"))
            category_alias = re.sub(
                r"\s+",
                " ",
                _text(limit_match.group("category")),
            ).casefold()
            category_key = _OFFICIAL_GEM_UNIQUE_CATEGORY_ALIASES.get(
                category_alias,
                "",
            )
            expected_limit = _OFFICIAL_GEM_UNIQUE_CATEGORY_LIMITS.get(category_key)
            if (
                unique_limit <= 0
                or not category_key
                or expected_limit is None
                or unique_limit != expected_limit
            ):
                limit_category_invalid = True
                break
            parsed_limit_categories.add((category_key, unique_limit))
        if len(parsed_limit_categories) > 1:
            limit_category_invalid = True

        unique_policy = _OFFICIAL_UNIQUE_GEM_POLICIES.get(gem_id)
        parsed_limit_category = next(iter(parsed_limit_categories), None)
        if limit_category_invalid:
            return "invalid", None
        if parsed_limit_category:
            category_key, unique_limit = parsed_limit_category
            if unique_policy and (
                category_key != unique_policy["categoryKey"]
                or unique_limit != unique_policy["uniqueLimit"]
            ):
                return "invalid", None
            option_payload.update({
                "uniqueEquipped": True,
                "uniqueGroup": f"official-gem-limit:{category_key}",
                "uniqueLimit": unique_limit,
                "uniqueScope": "gear_socket",
            })
        elif unique_policy:
            return "invalid", None
        return "verified", {
            "optionId": f"official-gem-{gem_id}",
            "variantId": "",
            "optionKey": f"gem-{gem_id}",
            "optionType": "socket",
            "name": display_name,
            "applicableSlots": ["*"],
            "simcOptions": {"gem_id": gem_id},
            "status": "verified",
            "isVisible": True,
            "payload": option_payload,
            "updatedAt": _text(item.get("updatedAt")),
        }

    if capability_revision == gear_socket_authority.CAPABILITY_REVISION:
        observed_gem_ids = {
            token.strip()
            for variant in materialized.get("variants") or []
            if isinstance(variant, dict)
            and _text(variant.get("sourceType")).lower() == "observed_profile"
            and _text(variant.get("status")).lower() in {"verified", "partial"}
            for token in _text((variant.get("simcOptions") or {}).get("gem_id")).split("/")
            if token.strip().isdigit()
        }
        projected_options = [
            option
            for option in materialized.get("options") or []
            if isinstance(option, dict)
        ]
        for gem_id in sorted(observed_gem_ids):
            option_key = f"gem-{gem_id}"
            matching_options = []
            canonical_options = []
            for existing in projected_options:
                existing_key = _text(existing.get("optionKey"))
                existing_simc_options = (
                    existing.get("simcOptions")
                    if isinstance(existing.get("simcOptions"), dict)
                    else {}
                )
                existing_gem_id = normalize_option_value(
                    existing_simc_options.get("gem_id")
                )
                if (
                    existing_key == option_key
                    and existing_gem_id
                    and existing_gem_id != gem_id
                ):
                    raise GearReleaseIntegrityError(
                        f"gem option identity conflicts with cached option: {gem_id}"
                    )
                if existing_key == option_key or existing_gem_id == gem_id:
                    matching_options.append(existing)
                if (
                    existing_key == option_key
                    and existing_simc_options == {"gem_id": gem_id}
                    and _text(existing.get("optionId"))
                    and _text(existing.get("optionType")).lower()
                    in {"socket", "gem"}
                    and _text(existing.get("status")).lower() == "verified"
                    and existing.get("isVisible") is True
                ):
                    canonical_options.append(existing)
            retained_options = [
                existing
                for existing in projected_options
                if existing not in matching_options
            ]
            official_state, official_option = verified_official_gem_option(gem_id)
            if official_state != "verified":
                if gem_id in _OFFICIAL_UNIQUE_GEM_POLICIES:
                    raise GearReleaseIntegrityError(
                        f"official unique gem evidence is unavailable: {gem_id}"
                    )
                projected_options = retained_options
                continue
            official_option = copy.deepcopy(official_option)
            live_presentation_options = []
            for existing in canonical_options:
                payload = (
                    existing.get("payload")
                    if isinstance(existing.get("payload"), dict)
                    else {}
                )
                if (
                    _text(payload.get("evidenceSource"))
                    == "wowhead_live_tooltip"
                    and _text(payload.get("displayStatus")) == "verified"
                    and _text(payload.get("displayLabel"))
                    and _text(payload.get("statSummary"))
                ):
                    live_presentation_options.append(existing)
            if len(live_presentation_options) == 1:
                presentation = live_presentation_options[0]
                presentation_payload = presentation["payload"]
                official_payload = official_option["payload"]
                official_payload["governanceEvidenceSource"] = _text(
                    official_payload.get("evidenceSource")
                )
                official_payload["governanceEvidenceRef"] = _text(
                    official_payload.get("evidenceRef")
                )
                for field in (
                    "displayName",
                    "displayLabel",
                    "displayKind",
                    "displayStatus",
                    "statSummary",
                    "iconUrl",
                ):
                    if field in presentation_payload:
                        official_payload[field] = copy.deepcopy(
                            presentation_payload[field]
                        )
                official_payload["evidenceSource"] = "wowhead_live_tooltip"
                presentation_ref = _text(presentation_payload.get("evidenceRef"))
                if presentation_ref:
                    official_payload["evidenceRef"] = presentation_ref
                else:
                    official_payload.pop("evidenceRef", None)
                official_option["name"] = _text(
                    official_payload.get("displayName")
                    or presentation.get("name")
                    or official_option.get("name")
                )
            projected_options = [*retained_options, official_option]
        materialized["options"] = projected_options

    options = [
        row
        for row in materialized.get("options") or []
        if isinstance(row, dict)
        and _text(row.get("status")).lower() == "verified"
        and row.get("isVisible") is True
    ]

    def option_type(option: dict[str, Any]) -> str:
        value = _text(option.get("optionType")).lower()
        return "gem" if value in {"socket", "gem"} else value

    def option_applies(option: dict[str, Any], slot: str) -> bool:
        applicable = [_text(value) for value in option.get("applicableSlots") or []]
        normalized = [normalize_slot(value) for value in applicable]
        return not applicable or "*" in applicable or slot in normalized

    if capability_revision == gear_socket_authority.CAPABILITY_REVISION:
        for option in options:
            if option_type(option) == "gem":
                # Gem compatibility is capacity-governed by the exact item/variant,
                # not by the legacy jewelry-only option catalog scope.
                option["applicableSlots"] = ["*"]

    def built_in_embellishment_state(
        raw_value: str,
        item_payload: dict[str, Any],
        variant_payload: dict[str, Any],
    ) -> str:
        payloads = (item_payload, variant_payload)
        explicit_values = {
            value.strip()
            for source in payloads
            for key in (
                "builtInEmbellishment",
                "intrinsicEmbellishment",
                "inherentEmbellishment",
            )
            for value in (source.get(key),)
            if isinstance(value, str) and value.strip()
        }
        if len(explicit_values) > 1:
            return "conflict"
        if explicit_values:
            return "proven" if raw_value in explicit_values else "conflict"
        built_in_source = any(
            isinstance(source.get("embellishmentSource"), str)
            and source["embellishmentSource"].strip().lower()
            in {"built_in", "builtin", "intrinsic", "item"}
            for source in payloads
        )
        strict_marker = any(
            source.get("hasBuiltInEmbellishment") is True
            for source in payloads
        )
        return "proven" if strict_marker or built_in_source else "absent"

    def simc_echo_enchant_proven(
        raw_value: str,
        slot: str,
        variant: dict[str, Any],
        variant_payload: dict[str, Any],
    ) -> bool:
        """Require an exact candidate-time SimC echo for immutable raw enchants."""

        if (
            _text(variant_payload.get("statSource")).lower() != "simulationcraft"
            or _text(variant_payload.get("statDisplayStatus")).lower()
            != "verified_variant"
            or not isinstance(variant_payload.get("itemStats"), list)
            or not variant_payload.get("itemStats")
        ):
            return False
        encoded = variant_payload.get("simcEncodedItem")
        if (
            not isinstance(encoded, str)
            or not encoded
            or encoded != encoded.strip()
        ):
            return False
        encoded_options = exact_encoded_simc_options(encoded)
        if encoded_options is None:
            return False
        item_id = _text(variant.get("itemId"))
        item_level = _int(variant.get("itemLevel"))
        raw_options = (
            variant.get("simcOptions")
            if isinstance(variant.get("simcOptions"), dict)
            else {}
        )

        normalized_raw_options = canonical_simc_options(raw_options)
        encoded_semantic_options = canonical_simc_options(encoded_options)
        if normalized_raw_options is None or encoded_semantic_options is None:
            return False
        if any(
            not expected
            or encoded_semantic_options.get(field) != expected
            for field, expected in normalized_raw_options.items()
        ):
            return False
        if set(encoded_semantic_options) - set(normalized_raw_options) - {"id", "ilevel"}:
            return False
        return (
            bool(slot)
            and bool(item_id)
            and _text(encoded_options.get("id")) == item_id
            and item_level > 0
            and _int(encoded_options.get("ilevel")) == item_level
            and _text(variant_payload.get("simcItemId")) == item_id
            and _int(variant_payload.get("simcItemLevel")) == item_level
            and normalize_option_value(encoded_options.get("enchant_id"))
            == normalize_option_value(raw_value)
        )

    variants = [
        row
        for row in materialized.get("variants") or []
        if isinstance(row, dict)
    ]

    def equivalent_simc_echo_enchant_proven(
        raw_value: str,
        slot: str,
        variant: dict[str, Any],
        variant_payload: dict[str, Any],
    ) -> bool:
        if simc_echo_enchant_proven(raw_value, slot, variant, variant_payload):
            return True
        variant_simc_options = canonical_simc_options(variant.get("simcOptions"))
        if variant_simc_options is None:
            return False
        semantic_identity = _canonical({
            "itemId": _text(variant.get("itemId")),
            "slot": slot,
            "itemLevel": _int(variant.get("itemLevel")),
            "simcOptions": variant_simc_options,
        })
        for sibling in variants:
            if sibling is variant:
                continue
            sibling_slot = normalize_slot(sibling.get("slot"))
            sibling_simc_options = canonical_simc_options(sibling.get("simcOptions"))
            if sibling_simc_options is None:
                continue
            sibling_identity = _canonical({
                "itemId": _text(sibling.get("itemId")),
                "slot": sibling_slot,
                "itemLevel": _int(sibling.get("itemLevel")),
                "simcOptions": sibling_simc_options,
            })
            sibling_payload = sibling.get("payload") if isinstance(sibling.get("payload"), dict) else {}
            if (
                sibling_identity == semantic_identity
                and _text(sibling.get("status")).lower() == "verified"
                and _text(sibling.get("sourceType")).lower() == "observed_profile"
                and simc_echo_enchant_proven(
                    raw_value,
                    sibling_slot,
                    sibling,
                    sibling_payload,
                )
            ):
                return True
        return False

    for variant in variants:
        if not isinstance(variant, dict):
            continue
        payload = _canonical(variant.get("payload") if isinstance(variant.get("payload"), dict) else {})
        payload.pop("editorManagedSimcFields", None)
        payload.pop("enhancementManagement", None)
        if capability_revision != gear_socket_authority.CAPABILITY_REVISION:
            variant["payload"] = payload
            continue
        item = items_by_id.get(_text(variant.get("itemId")), {})
        item_payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        slot = normalize_slot(variant.get("slot") or item.get("slot"))
        simc_options = variant.get("simcOptions") if isinstance(variant.get("simcOptions"), dict) else {}
        applicable_options = [option for option in options if option_applies(option, slot)]
        base_capabilities = item_payload.get("baseCapabilities") if isinstance(item_payload.get("baseCapabilities"), dict) else {}
        variant_capabilities = payload.get("capabilityOverrides") if isinstance(payload.get("capabilityOverrides"), dict) else {}
        socket_count = _int(variant_capabilities.get("socketCount", base_capabilities.get("socketCount")))
        can_enchant = item_can_enchant_slot(item_payload, slot, item)
        trusted_observed = (
            _text(variant.get("status")).lower() == "verified"
            and _text(variant.get("sourceType")).lower() == "observed_profile"
        )
        classifications: dict[str, str] = {}
        raw_gem_sequences = {
            field: simc_options.get(field)
            for field in _GEM_SIMC_SEQUENCE_FIELDS
            if _text(simc_options.get(field))
        }
        if raw_gem_sequences:
            raw_gem_ids = raw_gem_sequences.get("gem_id")

            def valid_numeric_sequence(raw: Any) -> list[str] | None:
                if not isinstance(raw, str) or not raw.strip():
                    return None
                tokens = raw.split("/")
                if any(not token.strip() or not token.strip().isdigit() for token in tokens):
                    return None
                return [token.strip() for token in tokens]

            gem_ids = valid_numeric_sequence(raw_gem_ids)
            auxiliary_sequences = {
                field: valid_numeric_sequence(raw_value)
                for field, raw_value in raw_gem_sequences.items()
                if field != "gem_id"
            }
            if (
                gem_ids is None
                or socket_count <= 0
                or len(gem_ids) > socket_count
                or any(
                    tokens is None or len(tokens) != len(gem_ids)
                    for tokens in auxiliary_sequences.values()
                )
            ):
                raise GearReleaseIntegrityError(
                    "raw gem sequence conflicts with materialized socket capacity"
                )
        for field in _ENHANCEMENT_SIMC_FIELDS:
            raw_value = _text(simc_options.get(field))
            if not raw_value:
                continue
            editor_managed = False
            if field in _GEM_SIMC_SEQUENCE_FIELDS:
                editor_managed = socket_count > 0
            elif field == "embellishment":
                editor_managed = any(
                    option_type(option) == "embellishment"
                    and _text((option.get("simcOptions") or {}).get(field)) == raw_value
                    for option in applicable_options
                )
            elif field == "enchant_id" and "/" not in raw_value:
                editor_managed = can_enchant and any(
                    option_type(option) in {"enchant", "runeforge"}
                    and _text((option.get("simcOptions") or {}).get(field)) == raw_value
                    for option in applicable_options
                )
            built_in_embellishment = built_in_embellishment_state(
                raw_value,
                item_payload,
                payload,
            )
            if field == "embellishment" and built_in_embellishment == "conflict":
                raise GearReleaseIntegrityError(
                    "built-in embellishment evidence conflicts with raw SimC value"
                )
            source_only = trusted_observed and (
                (field == "embellishment" and built_in_embellishment == "proven")
                or (
                    field == "enchant_id"
                    and (
                        not can_enchant
                        or (
                            slot in {"main_hand", "off_hand"}
                            and not editor_managed
                        )
                    )
                    and equivalent_simc_echo_enchant_proven(
                        raw_value,
                        slot,
                        variant,
                        payload,
                    )
                )
            )
            classifications[field] = (
                "source_only"
                if field == "embellishment" and built_in_embellishment == "proven"
                else "unresolved_drop"
                if field == "embellishment" and built_in_embellishment == "conflict"
                else "editor_managed"
                if editor_managed
                else "source_only"
                if source_only
                else "unresolved_drop"
            )
        management = gear_enhancement_management.seal_enhancement_management(
            simc_options,
            classifications,
            capability_revision,
        )
        if management:
            payload["enhancementManagement"] = management
        variant["payload"] = payload
    return materialized


def load_simc_socket_bonus_minimums(
    simc_binary: str,
    *,
    source_identity: str = "",
    source_revision: str = "",
    runner=subprocess.run,
) -> dict[str, Any]:
    """Run the bounded candidate-only SimC bonus probe and parse socket effects."""

    binary = _text(simc_binary)
    identity = _text(source_identity)
    revision = _text(source_revision)
    if not binary or not identity or not revision:
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
    return _validated_socket_bonus_evidence({
        "schemaRevision": _SIMC_SOCKET_BONUS_EVIDENCE_REVISION,
        "status": "verified",
        "sourceType": "simc_bonus_probe",
        "sourceIdentity": identity,
        "sourceRevision": revision,
        "sourceScope": "exact_variant",
        "minimums": parsed,
    })


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
    return dict(runtime.get("dependencyRevisions") or {})


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


def _observed_template_item_level(raw: dict[str, Any]) -> tuple[int, bool]:
    """Return the observed instance level and whether two source spellings conflict."""

    declared_item_level = _int(raw.get("itemLevel"))
    declared_ilevel = _int(raw.get("ilevel"))
    return (
        declared_item_level or declared_ilevel,
        (
            declared_item_level > 0
            and declared_ilevel > 0
            and declared_item_level != declared_ilevel
        ),
    )


def _observed_profile_urls(value: Any) -> set[str]:
    """Read bounded player-profile identifiers carried by observed instance evidence."""

    row = value if isinstance(value, dict) else {}
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    urls: set[str] = set()
    for source in (row, payload):
        for field in ("profileUrl", "sourceProfileUrl", "sourceUrl", "url"):
            url = _text(source.get(field))
            if url:
                urls.add(url)
        for ref in source.get("observedProfileRefs") or []:
            if not isinstance(ref, dict):
                continue
            for field in ("profileUrl", "sourceProfileUrl", "sourceUrl", "url"):
                url = _text(ref.get(field))
                if url:
                    urls.add(url)
    return urls


def _observed_template_instance_options(raw: dict[str, Any], observed_item_level: int) -> dict[str, str]:
    """Canonicalize exactly the SimC instance facts present in one observed slot."""

    options = dict(observed_gear_simc_options(raw))
    if observed_item_level > 0:
        options["ilevel"] = str(observed_item_level)
    return {
        key: normalized
        for key, value in options.items()
        if key in SIMC_GEAR_OPTION_KEYS
        and (normalized := normalize_option_value(value))
    }


def _canonical_observed_template_variant(
    raw: dict[str, Any],
    *,
    item_id: str,
    slot: str,
    variant_key: str,
    variants: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Resolve a legacy observed key to its one sealed game-instance identity.

    Older observed templates encode a variant key as concatenated ``field:value``
    text, while staging now stores a canonical JSON form.  The serialized key is
    not a gameplay fact, so that representation change may be bridged only by the
    exact observed item id, slot, instance level, all SimC fields, and target
    player profile identity.  When the catalog has no row from that player, it
    may use a deterministic, semantically identical catalog row only if every
    resolver-relevant fact agrees.  Any ambiguity remains unavailable.
    """

    normalized_item_id = _text(item_id)
    normalized_slot = normalize_slot(slot)
    normalized_variant_key = _text(variant_key)
    candidates = [
        row
        for row in variants
        if isinstance(row, dict)
        and _text(row.get("itemId")) == normalized_item_id
        and _text(row.get("status")).lower() == "verified"
        and normalize_slot(row.get("slot")) == normalized_slot
    ]
    exact = [
        row for row in candidates
        if _text(row.get("variantKey")) == normalized_variant_key
    ]
    if len(exact) == 1:
        return exact[0]

    normalized_variant_key = normalize_option_value(normalized_variant_key)
    normalized = [
        row for row in candidates
        if normalized_variant_key
        and normalize_option_value(row.get("variantKey")) == normalized_variant_key
    ]
    if len(normalized) == 1:
        return normalized[0]

    observed_item_level, conflicting_levels = _observed_template_item_level(raw)
    profile_urls = _observed_profile_urls(raw)
    expected_options = _observed_template_instance_options(raw, observed_item_level)
    if (
        conflicting_levels
        or observed_item_level <= 0
        or not profile_urls
        or not expected_options
    ):
        return {}

    equivalent = []
    semantic_candidates = []
    for candidate in candidates:
        if _text(candidate.get("sourceType")).lower() != "observed_profile":
            continue
        if _int(candidate.get("itemLevel")) != observed_item_level:
            continue
        candidate_options = {
            key: normalized
            for key, value in (candidate.get("simcOptions") or {}).items()
            if key in SIMC_GEAR_OPTION_KEYS
            and (normalized := normalize_option_value(value))
        }
        if candidate_options != expected_options:
            continue
        payload = candidate.get("payload") if isinstance(candidate.get("payload"), dict) else {}
        semantic_candidate = (candidate, _canonical({
            "itemId": _text(candidate.get("itemId")),
            "slot": normalize_slot(candidate.get("slot")),
            "itemLevel": _int(candidate.get("itemLevel")),
            "simcOptions": candidate_options,
            "resolvedStats": payload.get("resolvedStats") or {},
            "capabilityOverrides": payload.get("capabilityOverrides") or {},
            "enhancementManagement": payload.get("enhancementManagement") or {},
        }))
        semantic_candidates.append(semantic_candidate)
        if _observed_profile_urls(candidate) & profile_urls:
            equivalent.append(semantic_candidate)
    scoped_candidates = equivalent or semantic_candidates
    if not scoped_candidates:
        return {}
    signatures = {
        json.dumps(signature, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for _candidate, signature in scoped_candidates
    }
    if len(signatures) != 1:
        return {}
    return sorted(
        (candidate for candidate, _signature in scoped_candidates),
        key=lambda row: (_text(row.get("variantKey")), _text(row.get("variantId"))),
    )[0]


def _verified_item_icon_url(
    raw: dict[str, Any],
    item: dict[str, Any],
    item_id: str,
) -> str:
    """Return only icon evidence bound to the exact observed item identity."""

    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    metadata = payload.get("_metadata") if isinstance(payload.get("_metadata"), dict) else {}
    game_asset = metadata.get("gameAsset") if isinstance(metadata.get("gameAsset"), dict) else {}
    catalog_icon_url = _text(metadata.get("iconUrl"))
    if _text(game_asset.get("status")).lower() == "verified" and catalog_icon_url:
        return catalog_icon_url

    # Some catalog rows are intentionally slim.  A real-player observed item may
    # still carry a sealed Battle.net asset; accept it only when the asset itself
    # names the same item and repeats the exact icon URL.
    observed_asset = raw.get("gameAsset") if isinstance(raw.get("gameAsset"), dict) else {}
    observed_icon_url = _text(raw.get("iconUrl"))
    if (
        _text(observed_asset.get("status")).lower() == "verified"
        and _text(observed_asset.get("entityType")).lower() == "item"
        and _text(observed_asset.get("entityId")) == _text(item_id)
        and observed_icon_url
        and _text(observed_asset.get("iconUrl")) == observed_icon_url
    ):
        return observed_icon_url
    return ""


def selection_intent_from_template(
    template: dict[str, Any],
    *,
    gear_release_id: str,
    season_revision: str,
    level: int,
    gear_snapshot: dict[str, Any] | None = None,
    capability_revision: str = "",
) -> dict[str, Any]:
    snapshot = gear_snapshot if isinstance(gear_snapshot, dict) else {}
    enhancements_are_public_evidence = gear_release.is_public_observed_source(
        template.get("sourceKey")
    )
    items_by_id = {
        _text(row.get("itemId")): row
        for row in snapshot.get("items") or []
        if isinstance(row, dict) and _text(row.get("itemId"))
    }
    variants_by_item: dict[str, list[dict[str, Any]]] = {}
    for row in snapshot.get("variants") or []:
        if not isinstance(row, dict) or not _text(row.get("itemId")):
            continue
        variants_by_item.setdefault(_text(row.get("itemId")), []).append(row)
    verified_options = [
        row
        for row in snapshot.get("options") or []
        if isinstance(row, dict)
        and _text(row.get("optionKey"))
        and _text(row.get("status")).lower() == "verified"
        and row.get("isVisible") is True
    ]

    def matching_variant(
        raw: dict[str, Any],
        item_id: str,
        slot: str,
        variant_key: str,
    ) -> dict[str, Any]:
        return _canonical_observed_template_variant(
            raw,
            item_id=item_id,
            slot=slot,
            variant_key=variant_key,
            variants=variants_by_item.get(item_id, []),
        )

    def option_type(row: dict[str, Any]) -> str:
        normalized = _text(row.get("optionType")).lower()
        return "gem" if normalized in {"socket", "gem"} else normalized

    def option_applies(row: dict[str, Any], slot: str) -> bool:
        raw_applicable = [
            _text(value)
            for value in row.get("applicableSlots") or []
            if _text(value)
        ]
        applicable = [
            normalize_slot(value)
            for value in raw_applicable
        ]
        return not raw_applicable or "*" in raw_applicable or slot in applicable

    def unique_option_key(slot: str, expected_types: set[str], field: str, raw_value: str) -> str:
        normalized_value = normalize_option_value(raw_value)
        matches = [
            row
            for row in verified_options
            if option_type(row) in expected_types
            and option_applies(row, slot)
            and normalize_option_value(
                (row.get("simcOptions") or {}).get(field)
                if isinstance(row.get("simcOptions"), dict)
                else ""
            ) == normalized_value
        ]
        option_keys = {_text(row.get("optionKey")) for row in matches}
        return next(iter(option_keys)) if len(option_keys) == 1 else ""

    def raw_enhancement_options(
        raw: dict[str, Any],
        slot: str,
        socket_count: int,
    ) -> dict[str, str]:
        payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
        sources = [raw]
        for enhancement_by_slot in (
            template.get("enhancementBySlot"),
            payload.get("enhancementBySlot"),
        ):
            if not isinstance(enhancement_by_slot, dict):
                continue
            for raw_slot, value in enhancement_by_slot.items():
                if normalize_slot(raw_slot) == slot and isinstance(value, dict):
                    sources.append(value)
        values: dict[str, set[str]] = {}
        for source in sources:
            observed = observed_gear_simc_options(source)
            raw_gem_sequence = _text(observed.get("gem_id"))
            if raw_gem_sequence:
                gem_tokens = raw_gem_sequence.split("/")
                if (
                    socket_count <= 0
                    or any(not token.strip() or not token.strip().isdigit() for token in gem_tokens)
                    or len(gem_tokens) > socket_count
                ):
                    raise GearReleaseIntegrityError(
                        "template gem sequence conflicts with materialized socket capacity"
                    )
            for field, value in observed.items():
                if field not in {"gem_id", "enchant_id", "embellishment"}:
                    continue
                normalized = normalize_option_value(value)
                if normalized:
                    values.setdefault(field, set()).add(normalized)
        if len(values.get("gem_id", set())) > 1:
            raise GearReleaseIntegrityError(
                "template gem sequence conflicts with materialized socket capacity"
            )
        return {
            field: next(iter(candidates))
            for field, candidates in values.items()
            if len(candidates) == 1
        }

    def canonical_enhancements(
        raw: dict[str, Any],
        slot: str,
        item_id: str,
        variant_key: str,
    ) -> dict[str, Any]:
        empty = {
            "gemOptionIds": [],
            "enchantOptionId": "",
            "embellishmentOptionId": "",
        }
        if (
            capability_revision != gear_socket_authority.CAPABILITY_REVISION
            or not enhancements_are_public_evidence
        ):
            return empty
        item = items_by_id.get(item_id)
        variant = matching_variant(raw, item_id, slot, variant_key)
        if not isinstance(item, dict) or not variant:
            return empty
        item_payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        variant_payload = variant.get("payload") if isinstance(variant.get("payload"), dict) else {}
        base_capabilities = (
            item_payload.get("baseCapabilities")
            if isinstance(item_payload.get("baseCapabilities"), dict)
            else {}
        )
        overrides = (
            variant_payload.get("capabilityOverrides")
            if isinstance(variant_payload.get("capabilityOverrides"), dict)
            else {}
        )
        socket_count = _int(overrides.get("socketCount", base_capabilities.get("socketCount")))
        can_enchant = item_can_enchant_slot(item_payload, slot, item) or base_capabilities.get("canEnchant") is True
        if "canEnchant" in overrides:
            can_enchant = overrides.get("canEnchant") is True
        management_fields = gear_enhancement_management.validated_enhancement_management_fields(
            variant.get("simcOptions") if isinstance(variant.get("simcOptions"), dict) else {},
            variant_payload.get("enhancementManagement"),
            capability_revision,
        )
        can_embellish = (
            overrides.get("canEmbellish", base_capabilities.get("canEmbellish")) is True
            or management_fields.get("embellishment") == "editor_managed"
        )
        observed = raw_enhancement_options(raw, slot, socket_count)
        selected = dict(empty)
        raw_gems = [
            token.strip()
            for token in observed.get("gem_id", "").split("/")
            if token.strip()
        ]
        if raw_gems and (socket_count <= 0 or len(raw_gems) > socket_count):
            raise GearReleaseIntegrityError(
                "template gem sequence conflicts with materialized socket capacity"
            )
        if raw_gems and socket_count > 0 and len(raw_gems) <= socket_count:
            gem_option_ids = [
                unique_option_key(slot, {"gem"}, "gem_id", gem_id)
                for gem_id in raw_gems
            ]
            if all(gem_option_ids):
                selected["gemOptionIds"] = gem_option_ids
        variant_simc_options = (
            variant.get("simcOptions") if isinstance(variant.get("simcOptions"), dict) else {}
        )
        raw_enchant = observed.get("enchant_id", "")
        source_only_enchant = (
            management_fields.get("enchant_id") == "source_only"
            and normalize_option_value(variant_simc_options.get("enchant_id")) == raw_enchant
        )
        if raw_enchant and can_enchant and not source_only_enchant:
            selected["enchantOptionId"] = unique_option_key(
                slot,
                {"enchant", "runeforge"},
                "enchant_id",
                raw_enchant,
            )
        raw_embellishment = observed.get("embellishment", "")
        source_only_embellishment = (
            management_fields.get("embellishment") == "source_only"
            and normalize_option_value(variant_simc_options.get("embellishment")) == raw_embellishment
        )
        if raw_embellishment and can_embellish and not source_only_embellishment:
            selected["embellishmentOptionId"] = unique_option_key(
                slot,
                {"embellishment"},
                "embellishment",
                raw_embellishment,
            )
        return selected

    slots: dict[str, dict[str, Any]] = {}
    for raw in template.get("gearItems") or []:
        if not isinstance(raw, dict):
            continue
        slot = normalize_slot(raw.get("slot") or raw.get("simcSlot"))
        item_id = _text(raw.get("itemId") or raw.get("id"))
        if not slot or not item_id or slot in slots:
            continue
        variant_key = _text(raw.get("variantKey"))
        resolved_variant = matching_variant(raw, item_id, slot, variant_key)
        canonical_variant_key = _text(resolved_variant.get("variantKey")) or variant_key
        enhancements = canonical_enhancements(raw, slot, item_id, canonical_variant_key)
        slots[slot] = {
            "itemId": item_id,
            "variantKey": canonical_variant_key,
            **enhancements,
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


def community_template_import_evidence_from_template(
    template: dict[str, Any],
    *,
    gear_release_id: str,
    gear_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Seal observed per-slot display facts without changing Resolver Intent."""

    snapshot = gear_snapshot if isinstance(gear_snapshot, dict) else {}
    item_rows_by_id: dict[str, list[dict[str, Any]]] = {}
    for row in snapshot.get("items") or []:
        if not isinstance(row, dict) or not _text(row.get("itemId")):
            continue
        item_rows_by_id.setdefault(_text(row.get("itemId")), []).append(row)
    variant_rows_by_item: dict[str, list[dict[str, Any]]] = {}
    for row in snapshot.get("variants") or []:
        if not isinstance(row, dict):
            continue
        item_id = _text(row.get("itemId"))
        if item_id:
            variant_rows_by_item.setdefault(item_id, []).append(row)

    slots: dict[str, dict[str, Any]] = {}
    for raw in template.get("gearItems") or []:
        if not isinstance(raw, dict):
            raise GearReleaseIntegrityError("community import evidence gear item is invalid")
        slot = normalize_slot(raw.get("slot") or raw.get("simcSlot"))
        item_id = _text(raw.get("itemId") or raw.get("id"))
        variant_key = _text(raw.get("variantKey"))
        if not slot or not item_id or slot in slots:
            raise GearReleaseIntegrityError("community import evidence selection is incomplete")
        # Observed-profile ingestion serializes an item instance's actual level as
        # ``ilevel``.  Older/community payloads may expose the same observed fact
        # as ``itemLevel`` instead.  Neither spelling may fall back to the generic
        # catalogue item level: ambiguity is evidence failure, not a value to
        # calculate away.
        observed_item_level, conflicting_levels = _observed_template_item_level(raw)
        if conflicting_levels:
            raise GearReleaseIntegrityError(
                "community import evidence observed item level is ambiguous"
            )
        if observed_item_level <= 0:
            raise GearReleaseIntegrityError("community import evidence observed item level is missing")

        item_rows = item_rows_by_id.get(item_id) or []
        variant = _canonical_observed_template_variant(
            raw,
            item_id=item_id,
            slot=slot,
            variant_key=variant_key,
            variants=variant_rows_by_item.get(item_id, []),
        )
        if len(item_rows) != 1 or not variant:
            raise GearReleaseIntegrityError("community import evidence exact gear identity is unavailable")
        item = item_rows[0]
        if (
            _text(variant.get("status")).lower() != "verified"
            or normalize_slot(variant.get("slot")) != slot
            or _int(variant.get("itemLevel")) != observed_item_level
        ):
            raise GearReleaseIntegrityError("community import evidence variant does not match observed item level")
        icon_url = _verified_item_icon_url(raw, item, item_id)
        if not icon_url:
            raise GearReleaseIntegrityError("community import evidence verified item icon is missing")
        slots[slot] = {
            "itemId": item_id,
            "variantKey": _text(variant.get("variantKey")),
            "observedItemLevel": observed_item_level,
            "iconUrl": icon_url,
        }

    if not slots:
        raise GearReleaseIntegrityError("community import evidence selection is empty")
    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    attribute_character_context = _attribute_character_context_from_template(template)
    attribute_stable_effect_context = _attribute_stable_effect_context_from_template(template)
    template_evidence = (
        payload.get("templateEvidence")
        if isinstance(payload.get("templateEvidence"), dict)
        else {}
    )
    ordered_slots = {slot: slots[slot] for slot in sorted(slots)}
    source_fingerprint = _canonical_digest({
        "templateId": _text(template.get("templateId")),
        "sourceKey": _text(template.get("sourceKey")),
        "profileHash": _text(template.get("profileHash") or template_evidence.get("profileHash")),
        "gearHash": _text(template.get("gearHash") or template_evidence.get("gearHash") or template.get("signature")),
        "gearReleaseId": _text(gear_release_id),
        "sourceRaceKey": attribute_character_context["raceKey"],
        "sourceRaceOrigin": attribute_character_context["origin"],
        "sourceStableEffects": attribute_stable_effect_context,
        "slots": ordered_slots,
    })
    return {
        "schemaRevision": COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISION,
        "sourceFingerprint": source_fingerprint,
        "sourceRaceKey": attribute_character_context["raceKey"],
        "sourceRaceOrigin": attribute_character_context["origin"],
        "sourceStableEffects": attribute_stable_effect_context,
        "slots": ordered_slots,
    }


def _shadow_socket_payload(value: Any) -> Any:
    """Keep only socket/pvp data needed to reconstruct a legacy shadow."""

    if isinstance(value, Mapping):
        selected: dict[str, Any] = {}
        for key, child in value.items():
            text_key = _text(key)
            normalized = gear_socket_authority._normalized_key(text_key)
            nested = _shadow_socket_payload(child)
            if (
                normalized in gear_socket_authority._SOCKET_PAYLOAD_KEYS
                or normalized in {"ispvp", "pvp", "sourcerevision"}
            ):
                selected[text_key] = _canonical(child)
            elif nested not in ({}, []):
                selected[text_key] = nested
        return selected
    if isinstance(value, (list, tuple)):
        selected = [
            nested
            for child in value
            for nested in [_shadow_socket_payload(child)]
            if nested not in ({}, [])
        ]
        return selected
    return {}


def _legacy_shadow_input(raw_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Build the minimal input that the legacy/canonical comparison can read."""

    item_payload_fields = (
        "inventoryType",
        "armorType",
        "weaponType",
        "handedness",
        "allowedSlots",
        "baseCapabilities",
        "equipmentUniqueness",
        "allowedEnhancementRules",
    )
    variant_payload_fields = (
        "capabilityOverrides",
        "resolvedStats",
        "enhancementManagement",
        "allowedEnhancementRules",
        "statEvidence",
        "statSource",
        "statDisplayStatus",
        "itemStats",
        "simcEncodedItem",
        "simcItemId",
        "simcItemLevel",
    )
    observed_gem_ids = {
        token.strip()
        for row in raw_snapshot.get("variants") or ()
        if isinstance(row, Mapping)
        and _text(row.get("sourceType")).lower() == "observed_profile"
        and _text(row.get("status")).lower() in {"verified", "partial"}
        for token in _text(
            (row.get("simcOptions") or {}).get("gem_id")
            if isinstance(row.get("simcOptions"), Mapping)
            else ""
        ).split("/")
        if token.strip().isdigit()
    }

    def projected_payload(
        payload: Any,
        fields: Iterable[str],
        *,
        include_socket_payload: bool = True,
    ) -> dict[str, Any]:
        source = payload if isinstance(payload, Mapping) else {}
        result = {
            field: _canonical(source[field])
            for field in fields
            if field in source
        }
        if include_socket_payload:
            socket_payload = _shadow_socket_payload(source)
            for key, value in socket_payload.items():
                result.setdefault(key, value)
        return result

    items = []
    for row in raw_snapshot.get("items") or ():
        if not isinstance(row, Mapping):
            continue
        item_id = _text(row.get("itemId"))
        item_payload = (
            row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
        )
        fields = item_payload_fields + (
            (
                "_metadata",
                "item_class",
                "preview_item",
                "_links",
                "iconUrl",
            )
            if item_id in observed_gem_ids
            else ()
        )
        items.append(
            {
                key: _canonical(row[key])
                for key in (
                    "itemId",
                    "name",
                    "slot",
                    "hasSocket",
                    "sourceRevision",
                    "updatedAt",
                )
                if key in row
            }
            | {
                # The legacy materializer may read an explicit socket array,
                # but the shadow baseline cannot treat an unbound cache payload
                # as official capacity.  Preserve it only when it carries the
                # same immutable Battle.net identity/revision the compiler
                # requires for a canonical Fact.
                "payload": projected_payload(
                    item_payload,
                    fields,
                    include_socket_payload=(
                        _official_game_asset_evidence(item_payload, item_id)
                        is not None
                    ),
                )
            }
        )
    sources = []
    for row in raw_snapshot.get("sources") or ():
        if not isinstance(row, Mapping):
            continue
        source_payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
        sources.append(
            {
                key: _canonical(row[key])
                for key in (
                    "sourceId",
                    "itemId",
                    "sourceType",
                    "seasonRevision",
                    "status",
                    "sourceStatus",
                )
                if key in row
            }
            | {
                "payload": {
                    key: _canonical(source_payload[key])
                    for key in ("status", "sourceStatus")
                    if key in source_payload
                }
            }
        )
    variants = []
    for row in raw_snapshot.get("variants") or ():
        if not isinstance(row, Mapping):
            continue
        variants.append(
            {
                key: _canonical(row[key])
                for key in (
                    "variantId",
                    "itemId",
                    "variantKey",
                    "slot",
                    "difficultyKey",
                    "itemLevel",
                    "simcOptions",
                    "hasSocket",
                    "sourceType",
                    "status",
                    "sourceRevision",
                    "updatedAt",
                )
                if key in row
            }
            | {"payload": projected_payload(row.get("payload"), variant_payload_fields)}
        )
    options = []
    for row in raw_snapshot.get("options") or ():
        if not isinstance(row, Mapping):
            continue
        options.append(
            {
                key: _canonical(row[key])
                for key in (
                    "optionId",
                    "variantId",
                    "optionKey",
                    "optionType",
                    "name",
                    "simcOptions",
                    "applicableSlots",
                    "status",
                    "isVisible",
                    "updatedAt",
                )
                if key in row
            }
            # Options are a bounded shared catalog.  Retain their payload
            # verbatim so legacy enhancement governance keeps its established
            # presentation/unique-gem semantics without cloning every item or
            # variant payload.
            | {"payload": _canonical(row.get("payload") or {})}
        )
    return {
        "items": items,
        "sources": sources,
        "variants": variants,
        "options": options,
    }


def _legacy_shadow_snapshot(
    raw_snapshot: Mapping[str, Any],
    *,
    season_revision: str,
    capability_revision: str,
    socket_bonus_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    verified_socket_evidence = _validated_socket_bonus_evidence(
        socket_bonus_evidence
    )
    normalized_bonus_minimums = {
        bonus_id: {
            "minimumTotal": minimum,
            "sourceRevision": verified_socket_evidence[
                "sourceRevision"
            ],
        }
            for bonus_id, minimum in verified_socket_evidence[
                "minimums"
            ].items()
    }
    legacy_socket_input = _legacy_shadow_input(raw_snapshot)
    # Enhancement materialization rewrites the release-facing option catalog.
    # The legacy shadow intentionally retains the pre-projection option rows;
    # this bounded shared catalog is the only copy needed for that boundary.
    legacy_options = _canonical(legacy_socket_input.get("options") or ())
    legacy_snapshot = _materialize_enhancement_management(
        _project_socket_facts_into_release_payloads(
            gear_socket_authority.materialize_gear_socket_facts(
                legacy_socket_input,
                season_revision=season_revision,
                socket_bonus_minimums=normalized_bonus_minimums,
                in_place=True,
            ),
            in_place=True,
        ),
        capability_revision,
        in_place=True,
    )
    legacy_snapshot["options"] = legacy_options
    return legacy_snapshot


def _legacy_shadow_snapshot_for_evidence_batch(
    raw_snapshot: Mapping[str, Any],
    *,
    category: str,
    rows: Iterable[Mapping[str, Any]],
    season_revision: str,
    capability_revision: str,
    socket_bonus_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Materialize only the legacy rows needed to shadow one evidence batch.

    The final release still owns the complete staging snapshot.  Keeping a
    second catalog solely for legacy comparison creates a large transient peak,
    whereas each compiler batch only compares its own item, variant, or option
    subjects.  Item and variant batches retain their matching item/source rows
    so socket authority observes the exact same provenance as the full shadow.
    """

    batch_rows = [row for row in rows if isinstance(row, Mapping)]
    snapshot = raw_snapshot if isinstance(raw_snapshot, Mapping) else {}
    if category == "options":
        scoped_snapshot = {
            "items": [],
            "sources": [],
            "variants": [],
            "options": batch_rows,
        }
    elif category in {"items", "variants"}:
        item_ids = {
            _text(row.get("itemId"))
            for row in batch_rows
            if _text(row.get("itemId"))
        }
        if category == "variants":
            # Variant enhancement management consults the official cached item
            # record for each equipped gem, notably to preserve unique-gem
            # semantics.  Carry those few related items into the batch shadow
            # without retaining the entire item catalog.
            item_ids.update(
                token.strip()
                for row in batch_rows
                for token in _text(
                    (
                        row.get("simcOptions") or {}
                    ).get("gem_id")
                    if isinstance(row.get("simcOptions"), Mapping)
                    else ""
                ).split("/")
                if token.strip().isdigit()
            )
        scoped_snapshot = {
            "items": (
                batch_rows
                if category == "items"
                else [
                    row
                    for row in snapshot.get("items") or ()
                    if isinstance(row, Mapping)
                    and _text(row.get("itemId")) in item_ids
                ]
            ),
            "sources": [
                row
                for row in snapshot.get("sources") or ()
                if isinstance(row, Mapping)
                and _text(row.get("itemId")) in item_ids
            ],
            "variants": batch_rows if category == "variants" else [],
            # The shared option catalog is bounded and is an input to legacy
            # enhancement-management classification for item/variant facts.
            "options": [
                row
                for row in snapshot.get("options") or ()
                if isinstance(row, Mapping)
            ],
        }
    else:
        raise GearReleaseIntegrityError(
            "legacy shadow batch category is unsupported"
        )
    return _legacy_shadow_snapshot(
        scoped_snapshot,
        season_revision=season_revision,
        capability_revision=capability_revision,
        socket_bonus_evidence=socket_bonus_evidence,
    )


def _prepare_staging_gear_release_streaming(
    store: GearReleaseStore,
    *,
    season_revision: str,
    dependency_revisions: dict[str, Any],
    socket_bonus_evidence: Mapping[str, Any],
    normalized_bonus_minimums: Mapping[str, Any],
    source_revision: str,
    parent_release_id: str,
    captured_at: str,
    evidence_batch_size: int,
) -> dict[str, Any]:
    """Build a full release with bounded transient Evidence work."""

    if (
        evidence_batch_size <= 0
        or evidence_batch_size > _MAX_STREAMING_RELEASE_EVIDENCE_BATCH_SIZE
    ):
        raise GearReleaseIntegrityError(
            "streaming evidence_batch_size is outside the bounded release envelope"
        )

    raw_snapshot = store.snapshot_staging_gear()
    raw_snapshot_summary = gear_snapshot_summary(raw_snapshot)
    persist = getattr(store, "persist_gear_evidence_bundle", None)
    if not callable(persist):
        raise GearReleaseIntegrityError(
            "Gear Evidence Registry persistence owner is required"
        )

    compilation_receipt = _StreamingEvidenceReceipt()
    persistence_receipt = _StreamingEvidenceReceipt()
    shadow_parts: list[dict[str, Any]] = []
    gap_count = 0
    for category, offset, rows, compiled in _stream_release_evidence_batches(
        raw_snapshot,
        season_revision=season_revision,
        source_revision=source_revision,
        captured_at=captured_at,
        socket_bonus_minimums=normalized_bonus_minimums,
        socket_bonus_evidence=socket_bonus_evidence,
        batch_size=evidence_batch_size,
    ):
        artifacts = list(compiled["artifacts"])
        observations = list(compiled["observations"])
        facts = list(compiled["facts"])
        gaps = _gear_evidence_gap_records(facts, now=captured_at)
        persistence = persist(
            artifacts=artifacts,
            observations=observations,
            facts=facts,
            gaps=gaps,
            now=captured_at,
        )
        for owner, evidence_rows in (
            ("artifacts", artifacts),
            ("observations", observations),
            ("facts", facts),
            ("gaps", gaps),
        ):
            compilation_receipt.record(owner, evidence_rows)
        persistence_receipt.record_persistence(
            persistence,
            artifacts=artifacts,
            observations=observations,
            facts=facts,
            gaps=gaps,
        )
        shadow_snapshot = _legacy_shadow_snapshot_for_evidence_batch(
            raw_snapshot,
            category=category,
            rows=rows,
            season_revision=season_revision,
            capability_revision=_text(
                dependency_revisions.get("capabilityRevision")
            ),
            socket_bonus_evidence=socket_bonus_evidence,
        )
        shadow_part = gear_fact_shadow.compare_legacy_and_canonical(
            shadow_snapshot,
            facts,
            expected_fact_types_by_subject=(
                compiled["expectedFactTypesBySubject"]
            ),
            include_comparisons=False,
        )
        del shadow_snapshot
        if shadow_part["status"] != "pass":
            raise GearReleaseIntegrityError(
                "canonical fact shadow blocked candidate: "
                + _shadow_blocker_summary(shadow_part.get("blockers") or ())
            )
        shadow_parts.append(shadow_part)
        gap_count += len(gaps)
        _project_release_evidence_batch(
            raw_snapshot,
            category=category,
            offset=offset,
            rows=rows,
            compiled=compiled,
        )

    shadow = gear_fact_shadow.merge_compact_shadow_results(shadow_parts)
    if shadow["status"] != "pass":
        raise GearReleaseIntegrityError("canonical fact shadow blocked candidate")
    snapshot = _project_canonical_enhancement_management(
        raw_snapshot,
        capability_revision=_text(
            dependency_revisions.get("capabilityRevision")
        ),
        in_place=True,
    )
    problems = validate_gear_snapshot(snapshot)
    if problems:
        raise GearReleaseIntegrityError(
            json.dumps(problems, ensure_ascii=False, sort_keys=True)
        )
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
            "stagingSnapshotHash": raw_snapshot_summary["snapshotHash"],
            "sourceEvidence": {
                "simcRuntimeRevision": _text(
                    dependency_revisions.get("simcRuntimeRevision")
                ),
                "socketProbeDigest": _socket_probe_digest(
                    socket_bonus_evidence
                ),
                "socketBonusEvidence": socket_bonus_evidence,
                "materializedSocketFactDigest": _materialized_socket_fact_digest(
                    snapshot
                ),
                "compilerPolicyDigest": _canonical_digest(
                    gear_fact_compiler.FACT_POLICIES
                ),
                "canonicalFactDigest": _canonical_fact_digest_from_snapshot(
                    snapshot
                ),
            },
        },
        parent_release_id=parent_release_id,
    )
    gate = {
        "status": "validated",
        **summary,
        "evidenceStream": {
            "schemaRevision": "gear-evidence-stream-v1",
            "batchSize": evidence_batch_size,
            "rowOrderRevision": "staging-category-v1",
        },
        "factShadow": shadow,
        "evidenceCompilation": {
            "schemaRevision": compilation_receipt.schema_revision,
            **compilation_receipt.compilation(),
        },
        "evidencePersistence": {
            "schemaRevision": persistence_receipt.schema_revision,
            **persistence_receipt.persistence(),
        },
        "evidenceGapCount": gap_count,
    }
    return {"release": release, "snapshot": snapshot, "gate": gate}


def prepare_staging_gear_release(
    store: GearReleaseStore,
    *,
    season_revision: str,
    dependency_revisions: dict[str, Any],
    socket_bonus_minimums: Mapping[str, Any],
    source_revision: str = "legacy-import-r0",
    parent_release_id: str = "",
    evidence_now: str = "",
    extra_artifacts: Iterable[Mapping[str, Any]] = (),
    extra_observations: Iterable[Mapping[str, Any]] = (),
    evidence_batch_size: int | None = None,
) -> dict[str, Any]:
    socket_bonus_evidence = _validated_socket_bonus_evidence(
        socket_bonus_minimums
    )
    normalized_bonus_minimums = {
        bonus_id: {
            "minimumTotal": minimum,
            "sourceRevision": socket_bonus_evidence["sourceRevision"],
        }
        for bonus_id, minimum in socket_bonus_evidence["minimums"].items()
    }
    captured_at = _text(evidence_now) or datetime.now(timezone.utc).isoformat()
    if evidence_batch_size is not None:
        if extra_artifacts or extra_observations:
            raise GearReleaseIntegrityError(
                "streaming release build does not accept gap-recovery inputs"
            )
        return _prepare_staging_gear_release_streaming(
            store,
            season_revision=season_revision,
            dependency_revisions=dependency_revisions,
            socket_bonus_evidence=socket_bonus_evidence,
            normalized_bonus_minimums=normalized_bonus_minimums,
            source_revision=source_revision,
            parent_release_id=parent_release_id,
            captured_at=captured_at,
            evidence_batch_size=_int(evidence_batch_size),
        )
    raw_snapshot = store.snapshot_staging_gear()
    raw_snapshot_summary = gear_snapshot_summary(raw_snapshot)
    legacy_snapshot = _legacy_shadow_snapshot(
        raw_snapshot,
        season_revision=season_revision,
        capability_revision=_text(
            dependency_revisions.get("capabilityRevision")
        ),
        socket_bonus_evidence=socket_bonus_evidence,
    )
    compiled = _compile_release_gear_evidence(
        raw_snapshot,
        season_revision=season_revision,
        source_revision=source_revision,
        captured_at=captured_at,
        socket_bonus_minimums=normalized_bonus_minimums,
        socket_bonus_evidence=socket_bonus_evidence,
        extra_artifacts=extra_artifacts,
        extra_observations=extra_observations,
    )
    gaps = _gear_evidence_gap_records(compiled["facts"], now=captured_at)
    persist = getattr(store, "persist_gear_evidence_bundle", None)
    if not callable(persist):
        raise GearReleaseIntegrityError(
            "Gear Evidence Registry persistence owner is required"
        )
    persistence = persist(
        artifacts=compiled["artifacts"],
        observations=compiled["observations"],
        facts=compiled["facts"],
        gaps=gaps,
        now=captured_at,
    )
    shadow = gear_fact_shadow.compare_legacy_and_canonical(
        legacy_snapshot,
        compiled["facts"],
        expected_fact_types_by_subject=compiled[
            "expectedFactTypesBySubject"
        ],
    )
    if shadow["status"] != "pass":
        raise GearReleaseIntegrityError(
            "canonical fact shadow blocked candidate: "
            + _shadow_blocker_summary(shadow.get("blockers") or ())
        )
    snapshot = _project_canonical_facts(
        raw_snapshot,
        compiled["facts"],
        compiled["rowSubjects"],
        socket_claims_by_subject=compiled["socketClaimsBySubject"],
        socket_eligibility_by_item_id=compiled[
            "socketEligibilityByItemId"
        ],
    )
    snapshot = _project_canonical_enhancement_management(
        snapshot,
        capability_revision=_text(
            dependency_revisions.get("capabilityRevision")
        ),
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
            "stagingSnapshotHash": raw_snapshot_summary["snapshotHash"],
            "sourceEvidence": {
                "simcRuntimeRevision": _text(dependency_revisions.get("simcRuntimeRevision")),
                "socketProbeDigest": _socket_probe_digest(
                    socket_bonus_evidence
                ),
                "socketBonusEvidence": socket_bonus_evidence,
                "materializedSocketFactDigest": _materialized_socket_fact_digest(snapshot),
                "compilerPolicyDigest": _canonical_digest(
                    gear_fact_compiler.FACT_POLICIES
                ),
                "canonicalFactDigest": _canonical_digest(
                    sorted([
                        {
                            "factKey": fact["factKey"],
                            "status": fact["status"],
                            "factValueHash": fact["factValueHash"],
                            "provenanceHash": fact["provenanceHash"],
                        }
                        for fact in compiled["facts"]
                    ], key=lambda fact: (
                        fact["factKey"],
                        fact["factValueHash"],
                        fact["provenanceHash"],
                    ))
                ),
            },
        },
        parent_release_id=parent_release_id,
    )
    gate = {
        "status": "validated",
        **summary,
        "factShadow": shadow,
        "evidencePersistence": persistence,
        "evidenceCompilation": {
            "artifacts": {
                "count": len(compiled["artifacts"]),
                "identities": sorted(
                    artifact["artifactId"]
                    for artifact in compiled["artifacts"]
                ),
                "identityDigest": _canonical_digest(sorted(
                    artifact["artifactId"]
                    for artifact in compiled["artifacts"]
                )),
            },
            "observations": {
                "count": len(compiled["observations"]),
                "identities": sorted(
                    observation["observationId"]
                    for observation in compiled["observations"]
                ),
                "identityDigest": _canonical_digest(sorted(
                    observation["observationId"]
                    for observation in compiled["observations"]
                )),
            },
            "facts": {
                "count": len(compiled["facts"]),
                "identities": sorted(
                    (
                        fact["factKey"],
                        fact["factValueHash"],
                        fact["provenanceHash"],
                    )
                    for fact in compiled["facts"]
                ),
                "identityDigest": _canonical_digest(sorted(
                    (
                        fact["factKey"],
                        fact["factValueHash"],
                        fact["provenanceHash"],
                    )
                    for fact in compiled["facts"]
                )),
            },
            "gaps": {
                "count": len(gaps),
                "identities": sorted(
                    gap["gapKey"] for gap in gaps
                ),
                "identityDigest": _canonical_digest(sorted(
                    gap["gapKey"] for gap in gaps
                )),
            },
        },
        "evidenceGapCount": len(gaps),
    }
    return {"release": release, "snapshot": snapshot, "gate": gate}


def build_legacy_gear_release(
    store: GearReleaseStore,
    *,
    season_revision: str,
    dependency_revisions: dict[str, Any],
    socket_bonus_minimums: Mapping[str, Any],
    source_revision: str = "legacy-import-r0",
    evidence_batch_size: int = _FULL_RELEASE_EVIDENCE_BATCH_SIZE,
) -> dict[str, Any]:
    prepared = prepare_staging_gear_release(
        store,
        season_revision=season_revision,
        dependency_revisions=dependency_revisions,
        socket_bonus_minimums=socket_bonus_minimums,
        source_revision=source_revision,
        evidence_batch_size=evidence_batch_size,
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
    gear_snapshot: dict[str, Any],
    capability_revision: str,
) -> dict[str, Any]:
    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    evidence = payload.get("templateEvidence") if isinstance(payload.get("templateEvidence"), dict) else {}
    refs = [row for row in template.get("sourceRefs") or [] if isinstance(row, dict)]
    ref = refs[0] if refs else {}
    selection_intent = selection_intent_from_template(
        template,
        gear_release_id=gear_release_id,
        season_revision=season_revision,
        level=level,
        gear_snapshot=gear_snapshot,
        capability_revision=capability_revision,
    )
    candidate = {
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
        "selectionIntent": selection_intent,
    }
    try:
        candidate["importEvidence"] = community_template_import_evidence_from_template(
            template,
            gear_release_id=gear_release_id,
            gear_snapshot=gear_snapshot,
        )
    except GearReleaseIntegrityError:
        # A historical/incomplete observed template remains browseable but cannot win an
        # importable release; the election records the missing sealed evidence.
        pass
    return candidate


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
        release_payload = _canonical(original)
        release_payload["importEvidence"] = _canonical(elected.get("importEvidence") or {})
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
            "payload": release_payload,
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


def _observed_source_identity(template: Any) -> str:
    """Read the one Raider.IO character identity carried by a staged row."""

    if not isinstance(template, dict):
        return ""
    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    raiderio = payload.get("raiderio") if isinstance(payload.get("raiderio"), dict) else {}
    identity = _text(template.get("sourceIdentity") or payload.get("sourceIdentity") or raiderio.get("sourceIdentity"))
    return identity if identity.startswith("raiderio:") else ""


def _talent_projection_candidates(
    staged_talents: Iterable[dict[str, Any]],
    class_key: str,
    spec_key: str,
    hero_key: str,
) -> list[dict[str, Any]]:
    candidates = []
    for talent in staged_talents:
        if not isinstance(talent, dict):
            continue
        if (
            _text(talent.get("classKey")) != class_key
            or _text(talent.get("specKey")) != spec_key
            or _text(talent.get("heroKey")) != hero_key
            or _text(talent.get("scenarioKey")) != "mythic_plus"
        ):
            continue
        candidate_id = _text(talent.get("id") or talent.get("templateId"))
        source_identity = _observed_source_identity(talent)
        if not candidate_id:
            continue
        candidates.append({
            "candidateId": candidate_id,
            "classKey": class_key,
            "specKey": spec_key,
            "heroKey": hero_key,
            "scenarioKey": "mythic_plus",
            "talentCandidateRank": _int(talent.get("talentCandidateRank")),
            "sourceKey": _text(talent.get("sourceKey")),
            "sourceIdentity": source_identity,
            "sourceUrl": raiderio_payload.profile_url_for_source_identity(source_identity),
        })
    ordered = sorted(
        candidates,
        key=lambda row: (
            _int(row.get("talentCandidateRank")) if _int(row.get("talentCandidateRank")) > 0 else 2 ** 31,
            _text(row.get("candidateId")),
        ),
    )
    for index, candidate in enumerate(ordered, start=1):
        candidate["talentCandidateRank"] = index
    return ordered


def _rank_one_rejection_gate_evidence(rejected: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rank_one = [
        row
        for row in rejected or []
        if isinstance(row, dict) and _int(row.get("talentCandidateRank")) == 1
    ]
    evidence = []
    for row in rank_one[:_RANK_ONE_REJECTION_LIMIT]:
        problems = row.get("problems") if isinstance(row.get("problems"), list) else []
        evidence.append({
            "candidateId": _text(row.get("candidateId")),
            "sourceIdentity": _text(row.get("sourceIdentity")),
            "sourceUrl": _text(row.get("sourceUrl")),
            "problems": _canonical(problems[:_RANK_ONE_REJECTION_PROBLEM_LIMIT]),
        })
    return {
        "rankOneRejectionCount": len(rank_one),
        "rankOneRejections": evidence,
        "rankOneRejectionLimit": _RANK_ONE_REJECTION_LIMIT,
        "rankOneRejectionTruncatedCount": max(0, len(rank_one) - len(evidence)),
    }


def _projected_community_release_rows(
    *,
    staged_talents: Iterable[dict[str, Any]],
    templates: Iterable[dict[str, Any]],
    expected_specs: Iterable[tuple[str, str]],
    candidate_for_template: Callable[[dict[str, Any]], dict[str, Any]],
    resolve_candidate: Callable[[dict[str, Any]], dict[str, Any]],
    gear_release_id: str,
    now: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Project the fixed Talent ordering into one legal gear row per hero slot.

    This is deliberately separate from the historical one-winner gear election:
    its candidate order is the Talent election order, while the canonical Gear
    resolver remains the authority for whether each selected player's equipment
    can be imported.
    """

    gear_by_identity: dict[tuple[str, str, str], dict[str, Any]] = {}
    observed_by_spec: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for template in templates:
        if not isinstance(template, dict):
            continue
        identity = _observed_source_identity(template)
        template_class_key = _text(template.get("classKey"))
        template_spec_key = _text(template.get("specKey"))
        if (
            identity
            and template_class_key
            and template_spec_key
            and _text(template.get("sourceKey")) == community_winner_projection.PUBLIC_OBSERVED_SOURCE_KEY
            and _text(template.get("status")) == "complete"
        ):
            # One player can have several observed profiles. A talent source
            # must only project to equipment observed for the same class/spec.
            key = (identity, template_class_key, template_spec_key)
            current = gear_by_identity.get(key)
            if current is None or _text(template.get("updatedAt")) > _text(current.get("updatedAt")):
                gear_by_identity[key] = template
            observed_by_spec.setdefault((template_class_key, template_spec_key), []).append(template)

    def observed_template_weight(template: dict[str, Any]) -> tuple[int, int, str, str]:
        payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
        refs = [row for row in template.get("sourceRefs") or [] if isinstance(row, dict)]
        ref = refs[0] if refs else {}
        ranking = payload.get("rankingEvidence") if isinstance(payload.get("rankingEvidence"), dict) else {}
        return (
            _int(ranking.get("score") or ref.get("score") or 0),
            _int(ranking.get("maxKeyLevel") or ref.get("maxKeyLevel") or 0),
            _text(template.get("updatedAt")),
            _text(template.get("templateId")),
        )

    for key, candidates in observed_by_spec.items():
        observed_by_spec[key] = sorted(candidates, key=observed_template_weight, reverse=True)

    expected_slots = [
        (class_key, spec_key, hero_key)
        for class_key, spec_key in expected_specs
        for hero_key in hero_trees_for_spec(class_key, spec_key)[:2]
    ]
    rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    missing_slots: list[dict[str, str]] = []
    winner_count_by_spec: dict[tuple[str, str], int] = {}
    used_template_ids_by_spec: dict[tuple[str, str], set[str]] = {}
    used_source_identities_by_spec: dict[tuple[str, str], set[str]] = {}

    for class_key, spec_key, hero_key in expected_slots:
        spec_key_pair = (class_key, spec_key)
        used_template_ids = used_template_ids_by_spec.setdefault(spec_key_pair, set())
        used_source_identities = used_source_identities_by_spec.setdefault(spec_key_pair, set())
        ordered_talents = _talent_projection_candidates(
            staged_talents, class_key, spec_key, hero_key,
        )

        def validate(_talent_candidate: dict[str, Any], template: Any) -> dict[str, Any]:
            if not isinstance(template, dict):
                return {"status": "blocked", "problems": [{"code": "GEAR_CAPTURE_MISSING"}]}
            candidate = candidate_for_template(template)
            election = gear_release.elect_community_candidates(
                [candidate],
                gear_release_id=gear_release_id,
                resolver=resolve_candidate,
                now=now,
                expected_specs=[(class_key, spec_key)],
            )
            winners = election.get("winners") or []
            if not winners:
                problems = (election.get("rejected") or [{}])[0].get("problems") or []
                return {"status": "blocked", "problems": problems}
            return {"status": "verified", "template": {**_canonical(template), "_elected": _canonical(winners[0])}}

        projection = community_winner_projection.project_hero_slot(
            ordered_talents,
            {
                identity: template
                for (identity, template_class_key, template_spec_key), template in gear_by_identity.items()
                if template_class_key == class_key and template_spec_key == spec_key
                and _text(template.get("templateId")) not in used_template_ids
                and identity not in used_source_identities
            },
            validate,
        )
        winner = projection.get("winner")
        if not isinstance(winner, dict):
            rejected.extend(projection.get("rejected") or [])
            talent_winner_id = _text(ordered_talents[0].get("candidateId")) if ordered_talents else ""
            for template in observed_by_spec.get(spec_key_pair, []):
                template_id = _text(template.get("templateId"))
                source_identity = _observed_source_identity(template)
                if not template_id or template_id in used_template_ids or source_identity in used_source_identities:
                    continue
                fallback_candidate = {
                    "candidateId": talent_winner_id or f"spec-re-election:{template_id}",
                    "classKey": class_key,
                    "specKey": spec_key,
                    "heroKey": hero_key,
                    "scenarioKey": "mythic_plus",
                    "sourceKey": community_winner_projection.PUBLIC_TALENT_SOURCE_KEY,
                    "sourceIdentity": source_identity,
                    "talentCandidateRank": 1,
                }
                verdict = validate(fallback_candidate, template)
                if _text(verdict.get("status")) != "verified" or not isinstance(verdict.get("template"), dict):
                    continue
                winner = {
                    **_canonical(verdict["template"]),
                    "talentWinnerId": talent_winner_id or fallback_candidate["candidateId"],
                    "gearProjectionMode": "gear_fallback",
                    "gearProjectionFallbackScope": "class_spec",
                    "gearProjectionFallbackReason": "no_importable_same_hero_raiderio_candidate",
                }
                break
        if not isinstance(winner, dict):
            missing_slots.append({"classKey": class_key, "specKey": spec_key, "heroKey": hero_key})
            continue
        elected = winner.get("_elected") if isinstance(winner.get("_elected"), dict) else {}
        source_template_id = _text(winner.get("templateId"))
        source_identity = _observed_source_identity(winner)
        if source_template_id:
            used_template_ids.add(source_template_id)
        if source_identity:
            used_source_identities.add(source_identity)
        projection_id = f"community-gear:{class_key}:{spec_key}:{hero_key}:{source_template_id}"
        release_payload = _canonical(winner)
        release_payload.pop("_elected", None)
        release_payload["id"] = projection_id
        release_payload["templateId"] = projection_id
        release_payload["gearSourceTemplateId"] = source_template_id
        release_payload["heroKey"] = hero_key
        release_payload["talentWinnerId"] = _text(winner.get("talentWinnerId"))
        release_payload["gearProjectionMode"] = _text(winner.get("gearProjectionMode"))
        release_payload["canApplyGear"] = True
        # The projection changes the public template identity from the staged
        # character template to one hero-slot row. Preserve the elected
        # character's sealed import evidence on that new row, otherwise it is
        # browseable but fails closed when the user actually imports it.
        release_payload["importEvidence"] = _canonical(elected.get("importEvidence") or {})
        payload = release_payload.get("payload") if isinstance(release_payload.get("payload"), dict) else {}
        payload = _canonical(payload)
        payload["sourceIdentity"] = _observed_source_identity(winner)
        release_payload["payload"] = payload
        winner_count_by_spec[spec_key_pair] = winner_count_by_spec.get(spec_key_pair, 0) + 1
        rows.append({
            "templateId": projection_id,
            "classKey": class_key,
            "specKey": spec_key,
            "role": "winner",
            "electionRank": winner_count_by_spec[spec_key_pair],
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
            "evidence": _canonical((winner.get("payload") or {}).get("templateEvidence") or {"sourceRefs": winner.get("sourceRefs") or []}),
            "problems": [],
            "payload": release_payload,
            "updatedAt": _text(elected.get("updatedAt") or winner.get("updatedAt")),
            "expiresAt": _text(elected.get("expiresAt") or winner.get("expiresAt")),
        })
        rejected.extend(projection.get("rejected") or [])

    rows.sort(key=lambda row: (row["classKey"], row["specKey"], row["electionRank"], row["templateId"]))
    election = {
        "schemaRevision": "community-hero-gear-projection-v1",
        "status": "validated" if not missing_slots else "degraded",
        "expectedHeroSlotCount": len(expected_slots),
        "winnerHeroSlotCount": len(rows),
        "winnerSpecCount": len({(row["classKey"], row["specKey"]) for row in rows}),
        "rejected": rejected,
        "missingHeroSlots": missing_slots,
    }
    return rows, election


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
    projection_enabled = bool(getattr(store, "community_hero_projection_enabled", False))
    talent_snapshot = (
        store.snapshot_staging_community_talent_candidates(expected)
        if projection_enabled
        else []
    )
    template_ids = [_text(row.get("templateId")) for row in templates]
    if any(not template_id for template_id in template_ids):
        raise GearReleaseIntegrityError("staging community templateId must be non-empty")
    if len(set(template_ids)) != len(template_ids):
        raise GearReleaseIntegrityError("staging community templateId must be unique")
    templates_by_id = {_text(row.get("templateId")): row for row in templates if _text(row.get("templateId"))}
    release_dependencies = (
        gear_release_descriptor.get("dependencyRevisions")
        if isinstance(gear_release_descriptor.get("dependencyRevisions"), dict)
        else {}
    )
    capability_revision = _text(
        release_dependencies.get("capabilityRevision")
        or dependency_revisions.get("capabilityRevision")
    )
    def candidate_for_template(template: dict[str, Any]) -> dict[str, Any]:
        return _template_candidate(
            template,
            gear_release_id=gear_release_descriptor["releaseId"],
            season_revision=gear_release_descriptor["seasonRevision"],
            level=level,
            gear_snapshot=gear_snapshot,
            capability_revision=capability_revision,
        )

    candidates = [candidate_for_template(template) for template in templates]
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

    if projection_enabled:
        rows, election = _projected_community_release_rows(
            staged_talents=talent_snapshot,
            templates=templates,
            expected_specs=expected,
            candidate_for_template=candidate_for_template,
            resolve_candidate=resolve_candidate,
            gear_release_id=gear_release_descriptor["releaseId"],
            now=now,
        )
        summary = community_rows_summary(rows)
        release = gear_release.build_release(
            release_kind="community",
            season_revision=gear_release_descriptor["seasonRevision"],
            schema_revision="community-release-v2",
            content=summary,
            dependency_revisions=dependency_revisions,
            release_status=election["status"],
            source={
                "sourceRevision": source_revision,
                "validatedAgainstGearReleaseId": gear_release_descriptor["releaseId"],
                "stagingTemplateCount": len(templates),
                "stagingTalentCandidateCount": len(talent_snapshot),
                "projection": "talent-winner-hero-slots-v1",
            },
            parent_release_id=parent_release_id,
            validated_against_release_id=gear_release_descriptor["releaseId"],
        )
        gate = {
            "status": election["status"],
            "expectedHeroSlotCount": election["expectedHeroSlotCount"],
            "winnerHeroSlotCount": election["winnerHeroSlotCount"],
            "winnerSpecCount": election["winnerSpecCount"],
            "rejectedCount": len(election.get("rejected") or []),
            "missingHeroSlots": election.get("missingHeroSlots") or [],
            **_rank_one_rejection_gate_evidence(election.get("rejected") or []),
            **summary,
        }
        return {"release": release, "rows": rows, "election": election, "gate": gate}

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
    parser.add_argument("--expect-formal-active", action="store_true")
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
            expect_formal_active=args.expect_formal_active,
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
    socket_bonus_minimums = load_simc_socket_bonus_minimums(
        simc_binary(),
        source_identity="simulationcraft:show_bonus_ids",
        source_revision=args.simc_runtime_revision,
    )
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
    "COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISION",
    "build_legacy_community_release",
    "build_legacy_gear_release",
    "expected_spec_pairs",
    "load_simc_socket_bonus_minimums",
    "prepare_staging_gear_release",
    "runtime_dependency_revisions",
    "community_template_import_evidence_from_template",
    "selection_intent_from_template",
    "validate_gear_snapshot",
)

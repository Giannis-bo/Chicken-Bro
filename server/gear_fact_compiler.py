#!/usr/bin/env python3
"""Deterministic, policy-driven compilation of canonical static gear facts."""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Sequence

try:
    from .gear_evidence_registry import (
        EVIDENCE_ARTIFACT_SCHEMA_REVISION,
        build_evidence_artifact,
        build_canonical_fact,
    )
except ImportError:  # pragma: no cover - direct script/module compatibility
    from gear_evidence_registry import (  # type: ignore
        EVIDENCE_ARTIFACT_SCHEMA_REVISION,
        build_evidence_artifact,
        build_canonical_fact,
    )


_STRUCTURAL_SOURCES = ("battle_net_item", "season_rule")
_ALL_STATIC_SOURCES = (
    "battle_net_item",
    "season_rule",
    "simc_item_probe",
    "simc_bonus_probe",
)

FACT_POLICIES: dict[str, dict[str, Any]] = {
    "item_identity": {
        "allowedSources": ("battle_net_item",),
        "sourceScopes": ("base_item", "exact_item", "exact_variant"),
        "combinationMode": "exact_agreement",
        "closedWorldCondition": "explicit_structured_identity",
        "conflictPolicy": "unresolved_on_distinct_exact_values",
        "impactScope": "exact_variant",
        "ruleRevision": "gear-item-identity-policy-v1",
    },
    "slot_compatibility": {
        "allowedSources": _STRUCTURAL_SOURCES,
        "sourceScopes": (
            "base_item",
            "exact_item",
            "exact_variant",
            "slot_rule",
            "season_rule",
        ),
        "combinationMode": "canonical_set_union",
        "closedWorldCondition": "explicit_inventory_or_slot_rule",
        "conflictPolicy": "unresolved_on_incompatible_value_shape",
        "impactScope": "exact_variant",
        "ruleRevision": "gear-slot-compatibility-policy-v1",
    },
    "variant_track": {
        "allowedSources": ("battle_net_item", "simc_item_probe", "season_rule"),
        "sourceScopes": ("exact_item", "exact_variant", "season_rule"),
        "combinationMode": "exact_agreement",
        "closedWorldCondition": "exact_track_and_item_level_observed",
        "conflictPolicy": "unresolved_on_distinct_exact_values",
        "impactScope": "exact_variant",
        "ruleRevision": "gear-variant-track-policy-v1",
    },
    "executable_item_options": {
        "allowedSources": ("simc_item_probe",),
        "sourceScopes": ("exact_item", "exact_variant"),
        "combinationMode": "exact_agreement",
        "closedWorldCondition": "exact_executable_item_options_observed",
        "conflictPolicy": "unresolved_on_distinct_exact_values",
        "impactScope": "simc_execution",
        "ruleRevision": "gear-executable-item-options-policy-v1",
    },
    "static_stats": {
        "allowedSources": ("simc_item_probe",),
        "sourceScopes": ("exact_item", "exact_variant"),
        "combinationMode": "exact_agreement",
        "closedWorldCondition": "exact_probe_completed",
        "conflictPolicy": "unresolved_on_distinct_exact_values",
        "impactScope": "simc_execution",
        "ruleRevision": "gear-static-stats-policy-v1",
    },
    "socket_count": {
        "allowedSources": _ALL_STATIC_SOURCES,
        "sourceScopes": (
            "base_item",
            "exact_item",
            "exact_variant",
            "slot_rule",
            "season_rule",
            "season_slot",
        ),
        "combinationMode": "socket_capacity",
        "closedWorldCondition": "explicit_zero_or_exact_capacity",
        "conflictPolicy": "unresolved_on_distinct_exact_values",
        "impactScope": "socket_only",
        "ruleRevision": "gear-socket-count-policy-v1",
    },
    "enchant_capability": {
        "allowedSources": _STRUCTURAL_SOURCES,
        "sourceScopes": (
            "base_item",
            "exact_item",
            "exact_variant",
            "slot_rule",
            "season_rule",
        ),
        "combinationMode": "exact_agreement",
        "closedWorldCondition": "explicit_false_or_applicable_slot_rule",
        "conflictPolicy": "unresolved_on_distinct_exact_values",
        "impactScope": "enchant_only",
        "ruleRevision": "gear-enchant-capability-policy-v1",
    },
    "embellishment_capability": {
        "allowedSources": _STRUCTURAL_SOURCES,
        "sourceScopes": (
            "base_item",
            "exact_item",
            "exact_variant",
            "slot_rule",
            "season_rule",
        ),
        "combinationMode": "exact_agreement",
        "closedWorldCondition": "explicit_false_or_crafting_metadata",
        "conflictPolicy": "unresolved_on_distinct_exact_values",
        "impactScope": "embellishment_only",
        "ruleRevision": "gear-embellishment-capability-policy-v1",
    },
    "enhancement_option": {
        "allowedSources": ("battle_net_item", "simc_item_probe"),
        "sourceScopes": ("option", "exact_item", "exact_variant", "season_rule"),
        "combinationMode": "exact_agreement",
        "closedWorldCondition": "explicit_option_identity_effect_and_scope",
        "conflictPolicy": "unresolved_on_distinct_exact_values",
        "impactScope": "referencing_option_only",
        "ruleRevision": "gear-enhancement-option-policy-v1",
    },
    "allowed_enhancement_options": {
        "allowedSources": ("season_rule",),
        "sourceScopes": ("slot_rule", "season_rule"),
        "combinationMode": "canonical_set_union",
        "closedWorldCondition": "verified_capability_option_and_slot_rule",
        "conflictPolicy": "unresolved_on_incompatible_value_shape",
        "impactScope": "enhancement_category_only",
        "ruleRevision": "gear-allowed-enhancement-options-policy-v1",
    },
    "item_set_membership": {
        "allowedSources": ("battle_net_item",),
        "sourceScopes": ("base_item", "exact_item", "exact_variant"),
        "combinationMode": "exact_agreement",
        "closedWorldCondition": "explicit_set_identity_or_non_membership",
        "conflictPolicy": "unresolved_on_distinct_exact_values",
        "impactScope": "item_set_only",
        "ruleRevision": "gear-item-set-membership-policy-v1",
    },
    "equipment_uniqueness": {
        "allowedSources": ("battle_net_item",),
        "sourceScopes": ("base_item", "exact_item"),
        "combinationMode": "exact_agreement",
        "closedWorldCondition": "explicit_equipment_uniqueness",
        "conflictPolicy": "unresolved_on_distinct_exact_values",
        "impactScope": "whole_character_legality",
        "ruleRevision": "gear-equipment-uniqueness-policy-v1",
    },
}

_REQUIRED_POLICY_FIELDS = frozenset(
    {
        "allowedSources",
        "sourceScopes",
        "combinationMode",
        "closedWorldCondition",
        "conflictPolicy",
        "impactScope",
        "ruleRevision",
    }
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _canonical(value: Any) -> Any:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return json.loads(encoded)


def _canonical_key(value: Any) -> str:
    return json.dumps(
        _canonical(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _validated_artifact(
    row: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    try:
        rebuilt = build_evidence_artifact(
            source_type=row.get("sourceType"),
            source_identity=row.get("sourceIdentity"),
            source_revision=row.get("sourceRevision"),
            season_revision=row.get("seasonRevision"),
            captured_at=row.get("capturedAt"),
            payload=row.get("payload"),
        )
    except (TypeError, ValueError):
        return None
    if (
        row.get("schemaRevision") != EVIDENCE_ARTIFACT_SCHEMA_REVISION
        or _text(row.get("artifactId")) != rebuilt["artifactId"]
        or _text(row.get("payloadHash")) != rebuilt["payloadHash"]
    ):
        return None
    return row


def _artifact_identity_content(row: Mapping[str, Any]) -> str:
    return _canonical_key(
        {
            "artifactId": row.get("artifactId"),
            "payload": row.get("payload"),
            "payloadHash": row.get("payloadHash"),
            "schemaRevision": row.get("schemaRevision"),
            "seasonRevision": row.get("seasonRevision"),
            "sourceIdentity": row.get("sourceIdentity"),
            "sourceRevision": row.get("sourceRevision"),
            "sourceType": row.get("sourceType"),
        }
    )


def _artifact_index(
    values: Any,
) -> dict[str, Mapping[str, Any] | None]:
    if isinstance(values, Mapping):
        if _text(values.get("artifactId")):
            rows = [values]
        else:
            rows = list(values.values())
    else:
        rows = list(values or ())
    indexed: dict[str, Mapping[str, Any] | None] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        artifact_id = _text(row.get("artifactId"))
        if not artifact_id:
            continue
        validated = _validated_artifact(row)
        if validated is None:
            indexed[artifact_id] = None
            continue
        if artifact_id not in indexed:
            indexed[artifact_id] = validated
            continue
        current = indexed[artifact_id]
        if current is None:
            continue
        if _artifact_identity_content(current) != _artifact_identity_content(
            validated
        ):
            indexed[artifact_id] = None
    return indexed


def _flatten_observations(values: Iterable[Any]) -> list[Mapping[str, Any]]:
    flattened: list[Mapping[str, Any]] = []
    for value in values or ():
        if not isinstance(value, Mapping):
            continue
        nested = value.get("observations")
        if isinstance(nested, (list, tuple)):
            flattened.extend(
                observation
                for observation in nested
                if isinstance(observation, Mapping)
            )
        else:
            flattened.append(value)
    return flattened


def _validate_policy(fact_type: str, policy: Mapping[str, Any]) -> None:
    missing = _REQUIRED_POLICY_FIELDS.difference(policy)
    if missing:
        raise ValueError(
            f"Fact policy {fact_type} is missing: {', '.join(sorted(missing))}"
        )
    if policy.get("combinationMode") not in {
        "exact_agreement",
        "canonical_set_union",
        "socket_capacity",
    }:
        raise ValueError(f"Unsupported combination mode for {fact_type}.")
    for field in ("allowedSources", "sourceScopes"):
        values = policy.get(field)
        if not isinstance(values, (list, tuple)) or not values:
            raise ValueError(f"Fact policy {fact_type} requires {field}.")
    for field in (
        "closedWorldCondition",
        "conflictPolicy",
        "impactScope",
        "ruleRevision",
    ):
        if not _text(policy.get(field)):
            raise ValueError(f"Fact policy {fact_type} requires {field}.")
    if policy["closedWorldCondition"] not in _CLOSED_WORLD_VALIDATORS:
        raise ValueError(
            f"Fact policy {fact_type} has no closed-world evaluator."
        )


def _eligible_observations(
    observations: Sequence[Mapping[str, Any]],
    subject_key: str,
    fact_type: str,
    policy: Mapping[str, Any],
    season_revision: str,
    artifacts_by_id: Mapping[str, Mapping[str, Any] | None],
) -> tuple[list[Mapping[str, Any]], bool, bool]:
    candidates = [
        observation
        for observation in observations
        if _text(observation.get("subjectKey")) == subject_key
        and _text(observation.get("factType")) == fact_type
        and observation.get("status") == "accepted"
    ]
    eligible: list[Mapping[str, Any]] = []
    policy_rejected = False
    missing_artifact = False
    for observation in candidates:
        artifact = artifacts_by_id.get(_text(observation.get("artifactId")))
        if not artifact:
            missing_artifact = True
            continue
        source_allowed = (
            artifact.get("schemaRevision") == EVIDENCE_ARTIFACT_SCHEMA_REVISION
            and _text(artifact.get("seasonRevision")) == season_revision
            and _text(artifact.get("sourceType")) in policy["allowedSources"]
        )
        scope_allowed = (
            _text(observation.get("sourceScope")) in policy["sourceScopes"]
        )
        if (
            source_allowed
            and scope_allowed
            and _text(observation.get("observationId"))
        ):
            eligible.append(observation)
        else:
            policy_rejected = True
    return eligible, policy_rejected, missing_artifact


def _valid_string_list(value: Any, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(
            isinstance(entry, str) and bool(entry.strip())
            for entry in value
        )
        and len(set(value)) == len(value)
    )


def _valid_item_identity(value: Any, subject_key: str) -> bool:
    if not isinstance(value, dict) or not _text(value.get("itemId")):
        return False
    expected_item = subject_key.split("/variant:", 1)[0]
    if expected_item != f"item:{_text(value.get('itemId'))}":
        return False
    if "/variant:" not in subject_key:
        return "variantKey" not in value or not _text(value.get("variantKey"))
    return (
        _text(value.get("variantKey"))
        == subject_key.split("/variant:", 1)[1]
    )


def _valid_variant_track(value: Any, subject_key: str) -> bool:
    return (
        isinstance(value, dict)
        and _valid_item_identity(
            {
                "itemId": value.get("itemId"),
                "variantKey": value.get("variantKey"),
            },
            subject_key,
        )
        and bool(_text(value.get("track")))
        and isinstance(value.get("itemLevel"), int)
        and not isinstance(value.get("itemLevel"), bool)
        and value["itemLevel"] > 0
    )


_EXECUTABLE_SIMC_OPTION_FIELDS = frozenset(
    {
        "bonus_id",
        "crafted_stats",
        "embellishment",
        "enchant_id",
        "gem_bonus_id",
        "gem_id",
        "gem_ilevel",
        "ilevel",
        "redirected_base_stats",
    }
)


def _valid_executable_item_options(value: Any, subject_key: str) -> bool:
    if (
        not isinstance(value, dict)
        or set(value).difference(
            {
                "itemId",
                "variantKey",
                "options",
                "enhancementManagement",
            }
        )
        or not _valid_item_identity(
            {
                "itemId": value.get("itemId"),
                "variantKey": value.get("variantKey"),
            },
            subject_key,
        )
    ):
        return False
    options = value.get("options")
    if (
        not isinstance(options, dict)
        or not options
        or set(options).difference(_EXECUTABLE_SIMC_OPTION_FIELDS)
        or not all(
            isinstance(option_value, str) and bool(option_value.strip())
            for option_value in options.values()
        )
        or not _text(options.get("bonus_id"))
        or not _text(options.get("ilevel")).isdigit()
        or int(_text(options.get("ilevel"))) <= 0
    ):
        return False
    management = value.get("enhancementManagement")
    if management is None:
        return True
    if not isinstance(management, dict):
        return False
    fields = (
        management.get("fields")
        if isinstance(management, dict)
        else None
    )
    present_enhancements = set(options).intersection(
        {
            "embellishment",
            "enchant_id",
            "gem_bonus_id",
            "gem_id",
            "gem_ilevel",
        }
    )
    return (
        management.get("schemaRevision") == "gear-enhancement-management-v1"
        and management.get("authorityRevision") == "gear-capability-matrix-v2"
        and isinstance(fields, dict)
        and set(fields) == present_enhancements
        and all(
            classification
            in {"editor_managed", "source_only", "unresolved_drop"}
            for classification in fields.values()
        )
        and not any(
            fields.get(field) == "source_only"
            for field in ("gem_id", "gem_bonus_id", "gem_ilevel")
        )
    )


def _valid_static_stats(value: Any, _subject_key: str) -> bool:
    return (
        isinstance(value, dict)
        and bool(value)
        and all(
            bool(_text(stat))
            and isinstance(amount, (int, float))
            and not isinstance(amount, bool)
            for stat, amount in value.items()
        )
    )


def _valid_socket_count(value: Any, _subject_key: str) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
    )


def _valid_boolean(value: Any, _subject_key: str) -> bool:
    return isinstance(value, bool)


def _valid_enhancement_option(value: Any, subject_key: str) -> bool:
    if not isinstance(value, dict):
        return False
    option_id = _text(value.get("optionId"))
    return (
        bool(option_id)
        and subject_key == f"option:{option_id}"
        and _text(value.get("optionType"))
        in {
            "catalyst",
            "crafted",
            "embellishment",
            "enchant",
            "gem",
            "runeforge",
        }
        and isinstance(value.get("effect"), dict)
        and bool(value["effect"])
        and _valid_string_list(value.get("applicableScopes"))
    )


def _valid_allowed_option_basis(value: Any, _subject_key: str) -> bool:
    return (
        isinstance(value, dict)
        and _text(value.get("capabilityFactType"))
        in {
            "socket_count",
            "enchant_capability",
            "embellishment_capability",
        }
        and _valid_string_list(value.get("optionIds"), allow_empty=True)
        and bool(_text(value.get("slot")))
    )


def _valid_set_membership(value: Any, _subject_key: str) -> bool:
    if value is False:
        return True
    text = _text(value)
    return (
        text.startswith("set:")
        and text.removeprefix("set:").isdigit()
        and int(text.removeprefix("set:")) > 0
    )


def _valid_equipment_uniqueness(value: Any, subject_key: str) -> bool:
    if (
        not isinstance(value, dict)
        or "/variant:" in subject_key
        or not subject_key.startswith("item:")
        or not isinstance(value.get("isUnique"), bool)
    ):
        return False
    if value["isUnique"] is False:
        return set(value) == {"isUnique"}
    return (
        set(value) == {"isUnique", "groupId", "limit"}
        and bool(_text(value.get("groupId")))
        and isinstance(value.get("limit"), int)
        and not isinstance(value.get("limit"), bool)
        and value["limit"] > 0
    )


_CLOSED_WORLD_VALIDATORS = {
    "explicit_structured_identity": _valid_item_identity,
    "explicit_inventory_or_slot_rule": (
        lambda value, _subject_key: _valid_string_list(value)
    ),
    "exact_track_and_item_level_observed": _valid_variant_track,
    "exact_executable_item_options_observed": _valid_executable_item_options,
    "exact_probe_completed": _valid_static_stats,
    "explicit_zero_or_exact_capacity": _valid_socket_count,
    "explicit_false_or_applicable_slot_rule": _valid_boolean,
    "explicit_false_or_crafting_metadata": _valid_boolean,
    "explicit_option_identity_effect_and_scope": _valid_enhancement_option,
    "verified_capability_option_and_slot_rule": _valid_allowed_option_basis,
    "explicit_set_identity_or_non_membership": _valid_set_membership,
    "explicit_equipment_uniqueness": _valid_equipment_uniqueness,
}


def _closed_world_complete(
    policy: Mapping[str, Any],
    value: Any,
    subject_key: str,
) -> bool:
    validator = _CLOSED_WORLD_VALIDATORS.get(
        _text(policy.get("closedWorldCondition"))
    )
    return bool(validator and validator(value, subject_key))


def _combine(
    observations: Sequence[Mapping[str, Any]],
    subject_key: str,
    policy: Mapping[str, Any],
    artifacts_by_id: Mapping[str, Mapping[str, Any] | None],
) -> tuple[str, Any, bool]:
    if not observations:
        return "unresolved_missing", None, False
    complete_observations = [
        observation
        for observation in observations
        if _closed_world_complete(
            policy,
            _canonical(observation.get("observedValue")),
            subject_key,
        )
    ]
    if len(complete_observations) != len(observations):
        return "unresolved_missing", None, True
    values = [
        _canonical(observation.get("observedValue"))
        for observation in complete_observations
    ]
    mode = policy["combinationMode"]
    if mode == "canonical_set_union":
        values_by_key: dict[str, Any] = {}
        for value in values:
            for entry in value:
                values_by_key[_canonical_key(entry)] = entry
        return (
            "verified",
            [values_by_key[key] for key in sorted(values_by_key)],
            False,
        )
    if mode == "socket_capacity":
        exact_values = {
            value
            for observation, value in zip(complete_observations, values)
            if _text(
                artifacts_by_id.get(
                    _text(observation.get("artifactId")), {}
                ).get("sourceType")
            )
            in {"battle_net_item", "simc_item_probe"}
        }
        if len(exact_values) > 1:
            return "unresolved_conflict", None, False
        return "verified", max(values), False
    distinct = {_canonical_key(value): value for value in values}
    if len(distinct) != 1:
        return "unresolved_conflict", None, False
    return "verified", next(iter(distinct.values())), False


def _compile_one(
    *,
    season_revision: str,
    subject_key: str,
    fact_type: str,
    observations: Sequence[Mapping[str, Any]],
    artifacts_by_id: Mapping[str, Mapping[str, Any] | None],
    policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if policy is None:
        return build_canonical_fact(
            season_revision=season_revision,
            subject_key=subject_key,
            fact_type=fact_type,
            value=None,
            status="unresolved_missing",
            observation_refs=[],
            compiler_rule_revision="gear-compiler-policy-missing-v1",
            impact_scope="structural",
            problem_code="compiler_policy_missing",
        )
    _validate_policy(fact_type, policy)
    eligible, policy_rejected_candidates, missing_artifact = (
        _eligible_observations(
            observations,
            subject_key,
            fact_type,
            policy,
            season_revision,
            artifacts_by_id,
        )
    )
    status, value, incomplete_closed_world = _combine(
        eligible,
        subject_key,
        policy,
        artifacts_by_id,
    )
    if status == "verified":
        problem_code = ""
    elif status == "unresolved_conflict":
        problem_code = "observation_conflict"
    elif incomplete_closed_world:
        problem_code = "parser_unhandled_shape"
    elif missing_artifact:
        problem_code = "artifact_missing"
    elif policy_rejected_candidates:
        problem_code = "compiler_policy_missing"
    else:
        problem_code = "artifact_missing"
    return build_canonical_fact(
        season_revision=season_revision,
        subject_key=subject_key,
        fact_type=fact_type,
        value=value,
        status=status,
        observation_refs=[
            observation["observationId"]
            for observation in eligible
        ],
        compiler_rule_revision=policy["ruleRevision"],
        impact_scope=policy["impactScope"],
        problem_code=problem_code,
    )


def _capability_supports_options(fact: Mapping[str, Any]) -> bool:
    if fact.get("status") != "verified":
        return False
    value = fact.get("value")
    if fact.get("factType") == "socket_count":
        return (
            isinstance(value, int)
            and not isinstance(value, bool)
            and value > 0
        )
    return value is True


def _compile_allowed_options(
    *,
    season_revision: str,
    subject_key: str,
    observations: Sequence[Mapping[str, Any]],
    artifacts_by_id: Mapping[str, Mapping[str, Any] | None],
    policies: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    fact_type = "allowed_enhancement_options"
    policy = policies.get(fact_type)
    if policy is None:
        return _compile_one(
            season_revision=season_revision,
            subject_key=subject_key,
            fact_type=fact_type,
            observations=observations,
            artifacts_by_id=artifacts_by_id,
            policy=None,
        )
    _validate_policy(fact_type, policy)
    eligible, policy_rejected, missing_artifact = _eligible_observations(
        observations,
        subject_key,
        fact_type,
        policy,
        season_revision,
        artifacts_by_id,
    )
    complete_rules = [
        observation
        for observation in eligible
        if _closed_world_complete(
            policy,
            _canonical(observation.get("observedValue")),
            subject_key,
        )
    ]
    incomplete_rules = len(complete_rules) != len(eligible)
    observation_refs = [
        observation["observationId"] for observation in eligible
    ]
    allowed_option_ids: set[str] = set()
    dependency_missing = False
    dependency_conflict = False
    slot_fact = _compile_one(
        season_revision=season_revision,
        subject_key=subject_key,
        fact_type="slot_compatibility",
        observations=observations,
        artifacts_by_id=artifacts_by_id,
        policy=policies.get("slot_compatibility"),
    )
    observation_refs.extend(slot_fact["observationRefs"])
    if slot_fact["status"] == "unresolved_conflict":
        dependency_conflict = True
    elif slot_fact["status"] != "verified":
        dependency_missing = True
    for rule in complete_rules:
        basis = _canonical(rule.get("observedValue"))
        if (
            slot_fact.get("status") == "verified"
            and basis["slot"] not in slot_fact["value"]
        ):
            dependency_missing = True
        capability_type = basis["capabilityFactType"]
        capability_fact = _compile_one(
            season_revision=season_revision,
            subject_key=subject_key,
            fact_type=capability_type,
            observations=observations,
            artifacts_by_id=artifacts_by_id,
            policy=policies.get(capability_type),
        )
        observation_refs.extend(capability_fact["observationRefs"])
        if capability_fact["status"] == "unresolved_conflict":
            dependency_conflict = True
        elif capability_fact["status"] != "verified":
            dependency_missing = True
        elif basis["optionIds"] and not _capability_supports_options(
            capability_fact
        ):
            dependency_missing = True

        for option_id in basis["optionIds"]:
            option_fact = _compile_one(
                season_revision=season_revision,
                subject_key=f"option:{option_id}",
                fact_type="enhancement_option",
                observations=observations,
                artifacts_by_id=artifacts_by_id,
                policy=policies.get("enhancement_option"),
            )
            observation_refs.extend(option_fact["observationRefs"])
            if option_fact["status"] == "unresolved_conflict":
                dependency_conflict = True
            elif option_fact["status"] != "verified":
                dependency_missing = True
            else:
                option_value = option_fact["value"]
                compatible_types = {
                    "socket_count": {"gem"},
                    "enchant_capability": {"enchant", "runeforge"},
                    "embellishment_capability": {
                        "crafted",
                        "embellishment",
                    },
                }[capability_type]
                if (
                    option_value["optionType"] not in compatible_types
                    or (
                        basis["slot"]
                        not in option_value["applicableScopes"]
                        and "*"
                        not in option_value["applicableScopes"]
                    )
                ):
                    dependency_missing = True
                else:
                    allowed_option_ids.add(option_id)

    if dependency_conflict:
        status, value, problem_code = (
            "unresolved_conflict",
            None,
            "observation_conflict",
        )
    elif incomplete_rules or not complete_rules or dependency_missing:
        status, value = "unresolved_missing", None
        if incomplete_rules or (eligible and not complete_rules):
            problem_code = "parser_unhandled_shape"
        elif missing_artifact:
            problem_code = "artifact_missing"
        elif policy_rejected:
            problem_code = "compiler_policy_missing"
        else:
            problem_code = "artifact_missing"
    else:
        status, value, problem_code = (
            "verified",
            sorted(allowed_option_ids),
            "",
        )
    return build_canonical_fact(
        season_revision=season_revision,
        subject_key=subject_key,
        fact_type=fact_type,
        value=value,
        status=status,
        observation_refs=observation_refs,
        compiler_rule_revision=policy["ruleRevision"],
        impact_scope=policy["impactScope"],
        problem_code=problem_code,
    )


def compile_subject_facts(
    *,
    season_revision: Any,
    subject_key: Any,
    observations: Iterable[Any],
    artifacts: Any = (),
    fact_types: Iterable[Any] | None = None,
    policies: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Compile a deterministic fact vector for one exact subject."""

    normalized_season_revision = _text(season_revision)
    normalized_subject_key = _text(subject_key)
    if not normalized_season_revision:
        raise ValueError("season_revision is required.")
    if not normalized_subject_key:
        raise ValueError("subject_key is required.")
    selected_policies = policies if policies is not None else FACT_POLICIES
    selected_fact_types = (
        {_text(fact_type) for fact_type in fact_types}
        if fact_types is not None
        else set(selected_policies)
    )
    if "" in selected_fact_types:
        raise ValueError("fact_type is required.")
    flattened = _flatten_observations(observations)
    artifacts_by_id = _artifact_index(artifacts)
    facts: list[dict[str, Any]] = []
    for fact_type in sorted(selected_fact_types):
        if fact_type == "allowed_enhancement_options":
            facts.append(
                _compile_allowed_options(
                    season_revision=normalized_season_revision,
                    subject_key=normalized_subject_key,
                    observations=flattened,
                    artifacts_by_id=artifacts_by_id,
                    policies=selected_policies,
                )
            )
        else:
            facts.append(
                _compile_one(
                    season_revision=normalized_season_revision,
                    subject_key=normalized_subject_key,
                    fact_type=fact_type,
                    observations=flattened,
                    artifacts_by_id=artifacts_by_id,
                    policy=selected_policies.get(fact_type),
                )
            )
    return facts


def compile_facts(
    *,
    season_revision: Any,
    observations: Iterable[Any],
    artifacts: Any = (),
    subjects: Iterable[Any] | None = None,
    fact_types: Iterable[Any] | None = None,
    policies: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Compile deterministic canonical facts without external or mutable state."""

    flattened = _flatten_observations(observations)
    artifacts_by_id = _artifact_index(artifacts)
    normalized_subjects = (
        {_text(subject) for subject in subjects}
        if subjects is not None
        else {
            _text(observation.get("subjectKey"))
            for observation in flattened
        }
    )
    normalized_subjects.discard("")
    facts: list[dict[str, Any]] = []
    for subject_key in sorted(normalized_subjects):
        facts.extend(
            compile_subject_facts(
                season_revision=season_revision,
                subject_key=subject_key,
                observations=flattened,
                artifacts=artifacts_by_id,
                fact_types=fact_types,
                policies=policies,
            )
        )
    return sorted(
        facts,
        key=lambda fact: (
            fact["subjectKey"],
            fact["factType"],
            fact["factKey"],
        ),
    )


def evidence_gaps_from_facts(
    facts: Iterable[Any],
) -> list[dict[str, Any]]:
    """Project unresolved Facts into time-free, operational gap requirements."""

    gaps: list[dict[str, Any]] = []
    for fact in facts or ():
        if not isinstance(fact, Mapping):
            continue
        if fact.get("status") not in {
            "unresolved_missing",
            "unresolved_conflict",
        }:
            continue
        missing_requirement = {
            "subjectKey": _text(fact.get("subjectKey")),
            "factType": _text(fact.get("factType")),
            "seasonRevision": _text(fact.get("seasonRevision")),
            "compilerRuleRevision": _text(fact.get("compilerRuleRevision")),
            "requiredInputKey": (
                "consistent_observation"
                if fact.get("status") == "unresolved_conflict"
                else "allowed_observation"
            ),
        }
        gaps.append(
            {
                "factKey": _text(fact.get("factKey")),
                "problemCode": _text(fact.get("problemCode"))
                or (
                    "observation_conflict"
                    if fact.get("status") == "unresolved_conflict"
                    else "artifact_missing"
                ),
                "missingRequirement": missing_requirement,
            }
        )
    return sorted(
        gaps,
        key=lambda gap: (gap["problemCode"], gap["factKey"]),
    )


__all__ = (
    "FACT_POLICIES",
    "compile_facts",
    "compile_subject_facts",
    "evidence_gaps_from_facts",
)

#!/usr/bin/env python3
"""Deterministic, policy-driven compilation of canonical static gear facts."""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Sequence

try:
    from .gear_evidence_registry import build_canonical_fact
except ImportError:  # pragma: no cover - direct script/module compatibility
    from gear_evidence_registry import build_canonical_fact  # type: ignore


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
        "allowedSources": _ALL_STATIC_SOURCES,
        "sourceScopes": ("option", "exact_item", "exact_variant", "season_rule"),
        "combinationMode": "exact_agreement",
        "closedWorldCondition": "explicit_option_identity_effect_and_scope",
        "conflictPolicy": "unresolved_on_distinct_exact_values",
        "impactScope": "referencing_option_only",
        "ruleRevision": "gear-enhancement-option-policy-v1",
    },
    "allowed_enhancement_options": {
        "allowedSources": _ALL_STATIC_SOURCES,
        "sourceScopes": (
            "base_item",
            "exact_item",
            "exact_variant",
            "slot_rule",
            "season_rule",
        ),
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


def _source_type(observation: Mapping[str, Any]) -> str:
    explicit = _text(observation.get("sourceType"))
    if explicit:
        return explicit
    revision = _text(observation.get("parserRevision")).lower()
    prefixes = (
        ("battle-net-item-observer-", "battle_net_item"),
        ("simc-item-probe-observer-", "simc_item_probe"),
        ("simc-bonus-probe-observer-", "simc_bonus_probe"),
        ("season-rule-observer-", "season_rule"),
    )
    for prefix, source_type in prefixes:
        if revision.startswith(prefix):
            return source_type
    return ""


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


def _eligible_observations(
    observations: Sequence[Mapping[str, Any]],
    subject_key: str,
    fact_type: str,
    policy: Mapping[str, Any],
) -> tuple[list[Mapping[str, Any]], bool]:
    candidates = [
        observation
        for observation in observations
        if _text(observation.get("subjectKey")) == subject_key
        and _text(observation.get("factType")) == fact_type
        and observation.get("status") == "accepted"
    ]
    eligible = [
        observation
        for observation in candidates
        if _source_type(observation) in policy["allowedSources"]
        and _text(observation.get("sourceScope")) in policy["sourceScopes"]
        and _text(observation.get("observationId"))
    ]
    return eligible, bool(candidates and not eligible)


def _valid_fact_value(fact_type: str, value: Any) -> bool:
    if fact_type == "socket_count":
        return (
            isinstance(value, int)
            and not isinstance(value, bool)
            and value >= 0
        )
    if fact_type in {"enchant_capability", "embellishment_capability"}:
        return isinstance(value, bool)
    if fact_type in {
        "item_identity",
        "variant_track",
        "static_stats",
        "enhancement_option",
    }:
        return isinstance(value, dict) and bool(value)
    if fact_type in {
        "slot_compatibility",
        "allowed_enhancement_options",
    }:
        return isinstance(value, list)
    if fact_type == "item_set_membership":
        return value is False or bool(_text(value))
    return True


def _combine(
    observations: Sequence[Mapping[str, Any]],
    fact_type: str,
    mode: str,
) -> tuple[str, Any]:
    if not observations:
        return "unresolved_missing", None
    values = [_canonical(observation.get("observedValue")) for observation in observations]
    if not all(_valid_fact_value(fact_type, value) for value in values):
        return "unresolved_conflict", None
    if mode == "canonical_set_union":
        values_by_key: dict[str, Any] = {}
        for value in values:
            for entry in value:
                values_by_key[_canonical_key(entry)] = entry
        return "verified", [
            values_by_key[key] for key in sorted(values_by_key)
        ]
    if mode == "socket_capacity":
        exact_values = {
            value
            for observation, value in zip(observations, values)
            if _source_type(observation)
            in {"battle_net_item", "simc_item_probe"}
        }
        if len(exact_values) > 1:
            return "unresolved_conflict", None
        return "verified", max(values)
    distinct = {_canonical_key(value): value for value in values}
    if len(distinct) != 1:
        return "unresolved_conflict", None
    return "verified", next(iter(distinct.values()))


def _compile_one(
    *,
    season_revision: str,
    subject_key: str,
    fact_type: str,
    observations: Sequence[Mapping[str, Any]],
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
    eligible, policy_rejected_candidates = _eligible_observations(
        observations, subject_key, fact_type, policy
    )
    status, value = _combine(
        eligible, fact_type, policy["combinationMode"]
    )
    if status == "verified":
        problem_code = ""
    elif status == "unresolved_conflict":
        problem_code = "observation_conflict"
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


def compile_subject_facts(
    *,
    season_revision: Any,
    subject_key: Any,
    observations: Iterable[Any],
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
    return [
        _compile_one(
            season_revision=normalized_season_revision,
            subject_key=normalized_subject_key,
            fact_type=fact_type,
            observations=flattened,
            policy=selected_policies.get(fact_type),
        )
        for fact_type in sorted(selected_fact_types)
    ]


def compile_facts(
    *,
    season_revision: Any,
    observations: Iterable[Any],
    subjects: Iterable[Any] | None = None,
    fact_types: Iterable[Any] | None = None,
    policies: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Compile deterministic canonical facts without external or mutable state."""

    flattened = _flatten_observations(observations)
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

#!/usr/bin/env python3
"""Pure exact-only ResolvedLoadout contract.

This module joins the current verified whole-loadout Resolver result with the
immutable ExactItemInstance registry. It performs no I/O and owns no gameplay
rules: legality remains owned by ``gear_resolver`` and concrete serializer
facts remain owned by the Phase 2 exact validation rows.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping

try:
    from .gear_contracts import CANONICAL_GEAR_SLOTS
except ImportError:
    from gear_contracts import CANONICAL_GEAR_SLOTS


RESOLVED_LOADOUT_SCHEMA_REVISION = "resolved-loadout-v1"
RESOLVED_LOADOUT_KEY_PATTERN = re.compile(
    r"^resolved-loadout:sha256:[0-9a-f]{64}$"
)
EXACT_ITEM_INSTANCE_KEY_PATTERN = re.compile(
    r"^exact-item-instance:sha256:[0-9a-f]{64}$"
)
CATALOG_REVISION_PATTERN = re.compile(
    r"^gear-catalog:sha256:[0-9a-f]{64}$"
)

SIMC_OPTION_ORDER = (
    "id",
    "ilevel",
    "bonus_id",
    "gem_id",
    "gem_bonus_id",
    "gem_ilevel",
    "enchant_id",
    "crafted_stats",
    "embellishment",
    "redirected_base_stats",
)
_SET_OPTION_FIELDS = {
    "bonus_id",
    "crafted_stats",
    "embellishment",
    "redirected_base_stats",
}
_ORDERED_OPTION_FIELDS = {"gem_id", "gem_bonus_id", "gem_ilevel"}


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


def _hash(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _problem(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _dedupe_problems(problems: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    indexed = {
        json.dumps(problem, ensure_ascii=False, sort_keys=True, separators=(",", ":")):
        _canonical(problem)
        for problem in problems
        if isinstance(problem, Mapping)
    }
    return [indexed[key] for key in sorted(indexed)]


def _tokens(value: Any) -> list[str] | None:
    if value in (None, "", []):
        return []
    if isinstance(value, str):
        raw = value.split("/")
    elif isinstance(value, (list, tuple)):
        raw = list(value)
    else:
        return None
    tokens: list[str] = []
    for item in raw:
        if isinstance(item, bool) or not isinstance(item, (str, int)):
            return None
        token = str(item).strip()
        if not token or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", token):
            return None
        tokens.append(token)
    return tokens


def canonical_simc_options(
    value: Any,
    *,
    strict_single_values: bool = True,
) -> dict[str, str] | None:
    """Canonicalize the bounded item option surface in fixed SimC order."""

    source = dict(value) if isinstance(value, Mapping) else {}
    if set(source).difference(SIMC_OPTION_ORDER):
        return None
    result: dict[str, str] = {}
    for field in SIMC_OPTION_ORDER:
        if field not in source or source.get(field) in (None, "", []):
            continue
        tokens = _tokens(source.get(field))
        if tokens is None:
            return None
        if field in _SET_OPTION_FIELDS:
            tokens = sorted(set(tokens))
        elif (
            strict_single_values
            and field not in _ORDERED_OPTION_FIELDS
            and len(tokens) != 1
        ):
            return None
        if tokens:
            result[field] = "/".join(tokens)
    return result


def _blocked(
    *,
    catalog_revision: str,
    gear_rule_revision: str,
    exact_registry_revision: str,
    eligibility_context: Mapping[str, Any] | None,
    required_slots: Iterable[str],
    problems: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    normalized = _dedupe_problems(problems)
    return {
        "schemaRevision": RESOLVED_LOADOUT_SCHEMA_REVISION,
        "status": "blocked",
        "catalogRevision": catalog_revision,
        "gearRuleRevision": gear_rule_revision,
        "exactRegistryRevision": exact_registry_revision,
        "eligibilityContext": _canonical(eligibility_context or {}),
        "requiredSlots": list(required_slots),
        "orderedSlots": [],
        "staticAttributes": {},
        "constraints": {},
        "serializerInput": {"gearItems": []},
        "problemCodes": sorted(
            {_text(problem.get("code")) for problem in normalized if problem.get("code")}
        ),
        "problems": normalized,
    }


def _index_unique(
    rows: Any,
    key_field: str,
    duplicate_code: str,
    problems: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(rows or []):
        if not isinstance(raw, Mapping):
            problems.append(
                _problem(
                    duplicate_code,
                    f"{key_field}[{index}]",
                    "Registry row must be an object with one stable identity.",
                )
            )
            continue
        row = _canonical(raw)
        key = _text(row.get(key_field))
        if not key or key in result:
            problems.append(
                _problem(
                    duplicate_code,
                    f"{key_field}[{index}]",
                    "Registry identity is missing or duplicated.",
                )
            )
            continue
        result[key] = row
    return result


def _static_totals(rows: Iterable[Mapping[str, Any]]) -> dict[str, int | float] | None:
    totals: dict[str, int | float] = {}
    for row in rows:
        facts = row.get("staticFacts")
        if not isinstance(facts, Mapping) or not facts:
            return None
        for raw_key, value in facts.items():
            key = _text(raw_key)
            if (
                not key
                or isinstance(value, bool)
                or not isinstance(value, (int, float))
            ):
                return None
            totals[key] = totals.get(key, 0) + value
    return {key: totals[key] for key in sorted(totals)}


def build_resolved_loadout(
    *,
    resolver_snapshot: Any,
    exact_registry: Any,
    template_scope: str,
    template_content_hash: str,
) -> dict[str, Any]:
    """Join one verified Resolver snapshot to one exact template reference set."""

    snapshot = dict(resolver_snapshot) if isinstance(resolver_snapshot, Mapping) else {}
    registry = dict(exact_registry) if isinstance(exact_registry, Mapping) else {}
    dependency = (
        dict(snapshot.get("dependencyVector"))
        if isinstance(snapshot.get("dependencyVector"), Mapping)
        else {}
    )
    eligibility = (
        dict(snapshot.get("eligibilityContext"))
        if isinstance(snapshot.get("eligibilityContext"), Mapping)
        else {}
    )
    readiness = (
        dict(snapshot.get("profileReadiness"))
        if isinstance(snapshot.get("profileReadiness"), Mapping)
        else {}
    )
    catalog_revision = _text(registry.get("catalogRevision"))
    gear_rule_revision = _text(registry.get("gearRuleRevision"))
    registry_revision = _text(registry.get("registryRevision"))
    required = [
        slot
        for slot in CANONICAL_GEAR_SLOTS
        if slot in set(readiness.get("requiredSlots") or [])
    ]
    problems: list[dict[str, Any]] = []

    if not CATALOG_REVISION_PATTERN.fullmatch(catalog_revision):
        problems.append(
            _problem(
                "LOADOUT_CATALOG_REVISION_INVALID",
                "exactRegistry.catalogRevision",
                "ResolvedLoadout requires one canonical CatalogRevision.",
            )
        )
    if (
        not gear_rule_revision
        or gear_rule_revision != _text(dependency.get("gearRuleRevision"))
    ):
        problems.append(
            _problem(
                "LOADOUT_RULE_REVISION_CONFLICT",
                "exactRegistry.gearRuleRevision",
                "Exact validation and Resolver rule revisions must match.",
            )
        )
    aggregate_legality = snapshot.get("aggregateLegality")
    aggregate_legality = (
        aggregate_legality if isinstance(aggregate_legality, Mapping) else {}
    )
    if (
        snapshot.get("contractRevision") != "gear-resolved-snapshot-v1"
        or snapshot.get("status") != "verified"
        or aggregate_legality.get("status") != "verified"
        or readiness.get("status") != "verified"
        or readiness.get("simcReady") is not True
        or not required
        or required != [
            slot
            for slot in CANONICAL_GEAR_SLOTS
            if slot in set(readiness.get("readySlots") or [])
        ]
    ):
        problems.append(
            _problem(
                "LOADOUT_RESOLVER_NOT_READY",
                "resolverSnapshot.profileReadiness",
                "Only one verified whole-loadout Resolver result can be promoted.",
            )
        )

    instances = _index_unique(
        registry.get("exactItemInstances"),
        "exactItemInstanceKey",
        "LOADOUT_EXACT_INSTANCE_IDENTITY_INVALID",
        problems,
    )
    selections = _index_unique(
        registry.get("enhancementSelections"),
        "enhancementSelectionKey",
        "LOADOUT_ENHANCEMENT_IDENTITY_INVALID",
        problems,
    )
    validations: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(registry.get("validations") or []):
        row = dict(raw) if isinstance(raw, Mapping) else {}
        key = _text(row.get("exactItemInstanceKey"))
        if not key or key in validations:
            problems.append(
                _problem(
                    "LOADOUT_EXACT_VALIDATION_IDENTITY_INVALID",
                    f"exactRegistry.validations[{index}]",
                    "Exact validation identity is missing or duplicated.",
                )
            )
        else:
            validations[key] = _canonical(row)

    matching_refs = [
        _canonical(row)
        for row in registry.get("templateReferences") or []
        if (
            isinstance(row, Mapping)
            and _text(row.get("templateScope")) == _text(template_scope)
            and _text(row.get("templateContentHash"))
            == _text(template_content_hash)
        )
    ]
    refs_by_slot: dict[str, list[dict[str, Any]]] = {}
    for row in matching_refs:
        refs_by_slot.setdefault(_text(row.get("slot")), []).append(row)

    resolved_slots = (
        snapshot.get("resolvedSlots")
        if isinstance(snapshot.get("resolvedSlots"), Mapping)
        else {}
    )
    ordered_slots: list[dict[str, Any]] = []
    used_validations: list[dict[str, Any]] = []
    for slot in required:
        refs = refs_by_slot.get(slot, [])
        if not refs:
            problems.append(
                _problem(
                    "LOADOUT_REQUIRED_SLOT_MISSING",
                    f"templateReferences.{slot}",
                    "Required slot has no exact template reference.",
                )
            )
            continue
        if len(refs) != 1:
            problems.append(
                _problem(
                    "LOADOUT_SLOT_REFERENCE_AMBIGUOUS",
                    f"templateReferences.{slot}",
                    "Required slot must bind exactly one exact reference.",
                )
            )
            continue
        reference = refs[0]
        exact_key = _text(reference.get("exactItemInstanceKey"))
        if (
            reference.get("validationStatus") != "verified"
            or not EXACT_ITEM_INSTANCE_KEY_PATTERN.fullmatch(exact_key)
            or reference.get("problemCodes")
        ):
            problems.append(
                _problem(
                    "LOADOUT_EXACT_REFERENCE_NOT_VERIFIED",
                    f"templateReferences.{slot}",
                    "Only a verified exact reference can enter a ready loadout.",
                )
            )
            continue
        instance = instances.get(exact_key)
        validation = validations.get(exact_key)
        if not instance or not validation:
            problems.append(
                _problem(
                    "LOADOUT_EXACT_INSTANCE_UNAVAILABLE",
                    f"templateReferences.{slot}.exactItemInstanceKey",
                    "Referenced exact instance or validation is unavailable.",
                )
            )
            continue
        if (
            validation.get("status") != "verified"
            or _text(validation.get("catalogRevision")) != catalog_revision
            or _text(validation.get("gearRuleRevision")) != gear_rule_revision
        ):
            problems.append(
                _problem(
                    "LOADOUT_EXACT_VALIDATION_NOT_CURRENT",
                    f"validations.{exact_key}",
                    "Exact validation must be verified for the current Catalog and Rule.",
                )
            )
            continue
        selection_key = _text(instance.get("enhancementSelectionKey"))
        if selection_key not in selections:
            problems.append(
                _problem(
                    "LOADOUT_ENHANCEMENT_SELECTION_UNAVAILABLE",
                    f"instances.{exact_key}.enhancementSelectionKey",
                    "Exact enhancement selection is unavailable.",
                )
            )
            continue

        resolved = resolved_slots.get(slot)
        resolved = dict(resolved) if isinstance(resolved, Mapping) else {}
        exact_options = canonical_simc_options(validation.get("serializerInput"))
        resolved_options = canonical_simc_options(
            {
                "id": _text(resolved.get("itemId")),
                **(
                    dict(resolved.get("simcOptions"))
                    if isinstance(resolved.get("simcOptions"), Mapping)
                    else {}
                ),
            }
        )
        if (
            not resolved
            or resolved.get("legality", {}).get("status") != "verified"
            or resolved.get("problems")
            or _text(resolved.get("itemId")) != _text(instance.get("itemId"))
        ):
            problems.append(
                _problem(
                    "LOADOUT_RESOLVED_SLOT_MISMATCH",
                    f"resolverSnapshot.resolvedSlots.{slot}",
                    "Exact instance does not match one verified Resolver slot.",
                )
            )
            continue
        if exact_options is None or resolved_options is None or exact_options != resolved_options:
            problems.append(
                _problem(
                    "LOADOUT_SERIALIZER_PARITY_MISMATCH",
                    f"resolverSnapshot.resolvedSlots.{slot}.simcOptions",
                    "Resolver and exact validation serializer fields must match.",
                )
            )
            continue

        ordered_slots.append(
            {
                "slot": slot,
                "exactItemInstanceKey": exact_key,
                "enhancementSelectionKey": selection_key,
                "itemId": _text(instance.get("itemId")),
                "itemLevel": int(instance.get("ilevel") or 0),
                "progressionState": _canonical(
                    instance.get("progressionState") or {}
                ),
                "staticFacts": _canonical(validation.get("staticFacts") or {}),
                "serializerInput": exact_options,
            }
        )
        used_validations.append(validation)

    if set(refs_by_slot).difference(required):
        problems.append(
            _problem(
                "LOADOUT_UNEXPECTED_SLOT_REFERENCE",
                "templateReferences",
                "Template contains a slot outside Resolver-required slots.",
            )
        )
    static_attributes = _static_totals(used_validations)
    if static_attributes is None or static_attributes != _canonical(
        snapshot.get("staticAttributes") or {}
    ):
        problems.append(
            _problem(
                "LOADOUT_STATIC_ATTRIBUTES_MISMATCH",
                "resolverSnapshot.staticAttributes",
                "Exact static facts and verified Resolver totals must match.",
            )
        )

    if problems:
        return _blocked(
            catalog_revision=catalog_revision,
            gear_rule_revision=gear_rule_revision,
            exact_registry_revision=registry_revision,
            eligibility_context=eligibility,
            required_slots=required,
            problems=problems,
        )

    identity = {
        "classKey": _text(eligibility.get("classKey")),
        "specKey": _text(eligibility.get("specKey")),
        "orderedSlotExactInstanceKeys": [
            {
                "slot": row["slot"],
                "exactItemInstanceKey": row["exactItemInstanceKey"],
            }
            for row in ordered_slots
        ],
        "enhancementSelections": [
            {
                "slot": row["slot"],
                "enhancementSelectionKey": row["enhancementSelectionKey"],
            }
            for row in ordered_slots
        ],
        "ruleRevision": gear_rule_revision,
        "catalogRevision": catalog_revision,
    }
    resolved_key = _hash("resolved-loadout:sha256:", identity)
    row = {
        "schemaRevision": RESOLVED_LOADOUT_SCHEMA_REVISION,
        "status": "ready",
        "resolvedLoadoutKey": resolved_key,
        "catalogRevision": catalog_revision,
        "gearRuleRevision": gear_rule_revision,
        "exactRegistryRevision": registry_revision,
        "eligibilityContext": _canonical(eligibility),
        "requiredSlots": required,
        "orderedSlots": ordered_slots,
        "aggregateLegality": _canonical(snapshot.get("aggregateLegality") or {}),
        "staticAttributes": static_attributes,
        "constraints": _canonical(snapshot.get("constraints") or {}),
        "serializerInput": {
            "gearItems": [
                {
                    "slot": item["slot"],
                    "itemId": item["itemId"],
                    "exactItemInstanceKey": item["exactItemInstanceKey"],
                    "simcOptions": item["serializerInput"],
                }
                for item in ordered_slots
            ]
        },
        "sourceResolverSignature": _text(snapshot.get("resolvedGearSignature")),
        "problemCodes": [],
        "problems": [],
    }
    row["rowHash"] = _hash(
        "sha256:",
        {key: value for key, value in row.items() if key != "rowHash"},
    )
    return row


def build_resolved_loadout_from_registry(
    *,
    resolver_snapshot: Any,
    exact_registry: Any,
    template_scope: str = "",
    template_content_hash: str = "",
    template_authority_identity: str = "",
) -> dict[str, Any]:
    """Match a Resolver result to one unique exact template content group.

    This adapter is intentionally exact-only.  Callers must provide either the
    immutable content hash or the server-bound authority identity.  Serializer
    similarity is validation after identity binding, never a registry-wide
    discovery mechanism.
    """

    registry = dict(exact_registry) if isinstance(exact_registry, Mapping) else {}
    requested_hash = _text(template_content_hash)
    requested_authority = _text(template_authority_identity)
    if not requested_hash and not requested_authority:
        snapshot = (
            dict(resolver_snapshot)
            if isinstance(resolver_snapshot, Mapping)
            else {}
        )
        dependency = (
            snapshot.get("dependencyVector")
            if isinstance(snapshot.get("dependencyVector"), Mapping)
            else {}
        )
        return _blocked(
            catalog_revision=_text(registry.get("catalogRevision")),
            gear_rule_revision=_text(registry.get("gearRuleRevision"))
            or _text(dependency.get("gearRuleRevision")),
            exact_registry_revision=_text(
                registry.get("registryRevision")
            ),
            eligibility_context=(
                snapshot.get("eligibilityContext")
                if isinstance(snapshot.get("eligibilityContext"), Mapping)
                else {}
            ),
            required_slots=(
                snapshot.get("profileReadiness", {}).get(
                    "requiredSlots",
                    [],
                )
                if isinstance(snapshot.get("profileReadiness"), Mapping)
                else []
            ),
            problems=[
                _problem(
                    "LOADOUT_EXACT_TEMPLATE_IDENTITY_REQUIRED",
                    "exactRegistry.templateReferences",
                    "ResolvedLoadout requires one server-bound exact template identity.",
                )
            ],
        )
    groups = sorted(
        {
            (
                _text(row.get("templateScope")),
                _text(row.get("templateContentHash")),
            )
            for row in registry.get("templateReferences") or []
            if (
                isinstance(row, Mapping)
                and _text(row.get("templateContentHash"))
                and (
                    not _text(template_scope)
                    or _text(row.get("templateScope")) == _text(template_scope)
                )
                and (
                    not requested_hash
                    or _text(row.get("templateContentHash")) == requested_hash
                )
                and (
                    not requested_authority
                    or _text(row.get("templateAuthorityIdentity"))
                    == requested_authority
                )
            )
        }
    )
    candidates = [
        build_resolved_loadout(
            resolver_snapshot=resolver_snapshot,
            exact_registry=registry,
            template_scope=scope,
            template_content_hash=content_hash,
        )
        for scope, content_hash in groups
    ]
    ready_by_key = {
        row["resolvedLoadoutKey"]: row
        for row in candidates
        if row.get("status") == "ready" and row.get("resolvedLoadoutKey")
    }
    if len(ready_by_key) == 1:
        return next(iter(ready_by_key.values()))
    snapshot = (
        dict(resolver_snapshot)
        if isinstance(resolver_snapshot, Mapping)
        else {}
    )
    registry_revision = _text(registry.get("registryRevision"))
    dependency = (
        snapshot.get("dependencyVector")
        if isinstance(snapshot.get("dependencyVector"), Mapping)
        else {}
    )
    code = (
        "LOADOUT_EXACT_TEMPLATE_MATCH_AMBIGUOUS"
        if len(ready_by_key) > 1
        else "LOADOUT_EXACT_TEMPLATE_MATCH_UNAVAILABLE"
    )
    return _blocked(
        catalog_revision=_text(registry.get("catalogRevision")),
        gear_rule_revision=_text(registry.get("gearRuleRevision"))
        or _text(dependency.get("gearRuleRevision")),
        exact_registry_revision=registry_revision,
        eligibility_context=(
            snapshot.get("eligibilityContext")
            if isinstance(snapshot.get("eligibilityContext"), Mapping)
            else {}
        ),
        required_slots=(
            snapshot.get("profileReadiness", {}).get("requiredSlots", [])
            if isinstance(snapshot.get("profileReadiness"), Mapping)
            else []
        ),
        problems=[
            _problem(
                code,
                "exactRegistry.templateReferences",
                "Resolver output must match one unique sealed exact template.",
            )
        ],
    )


def verify_resolved_loadout(value: Any) -> list[str]:
    row = dict(value) if isinstance(value, Mapping) else {}
    issues: list[str] = []
    if row.get("schemaRevision") != RESOLVED_LOADOUT_SCHEMA_REVISION:
        issues.append("RESOLVED_LOADOUT_SCHEMA_INVALID")
    if row.get("status") != "ready":
        issues.append("RESOLVED_LOADOUT_NOT_READY")
        return issues
    if not RESOLVED_LOADOUT_KEY_PATTERN.fullmatch(
        _text(row.get("resolvedLoadoutKey"))
    ):
        issues.append("RESOLVED_LOADOUT_KEY_INVALID")
    eligibility = (
        row.get("eligibilityContext")
        if isinstance(row.get("eligibilityContext"), Mapping)
        else {}
    )
    ordered_slots = (
        row.get("orderedSlots")
        if isinstance(row.get("orderedSlots"), list)
        else []
    )
    expected_key = _hash(
        "resolved-loadout:sha256:",
        {
            "classKey": _text(eligibility.get("classKey")),
            "specKey": _text(eligibility.get("specKey")),
            "orderedSlotExactInstanceKeys": [
                {
                    "slot": _text(item.get("slot")),
                    "exactItemInstanceKey": _text(
                        item.get("exactItemInstanceKey")
                    ),
                }
                for item in ordered_slots
                if isinstance(item, Mapping)
            ],
            "enhancementSelections": [
                {
                    "slot": _text(item.get("slot")),
                    "enhancementSelectionKey": _text(
                        item.get("enhancementSelectionKey")
                    ),
                }
                for item in ordered_slots
                if isinstance(item, Mapping)
            ],
            "ruleRevision": _text(row.get("gearRuleRevision")),
            "catalogRevision": _text(row.get("catalogRevision")),
        },
    )
    if _text(row.get("resolvedLoadoutKey")) != expected_key:
        issues.append("RESOLVED_LOADOUT_IDENTITY_MISMATCH")
    expected_hash = _hash(
        "sha256:",
        {key: value for key, value in row.items() if key != "rowHash"},
    )
    if _text(row.get("rowHash")) != expected_hash:
        issues.append("RESOLVED_LOADOUT_ROW_HASH_INVALID")
    return issues


__all__ = (
    "RESOLVED_LOADOUT_SCHEMA_REVISION",
    "SIMC_OPTION_ORDER",
    "build_resolved_loadout",
    "build_resolved_loadout_from_registry",
    "canonical_simc_options",
    "verify_resolved_loadout",
)

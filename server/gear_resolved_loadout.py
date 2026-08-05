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
    from .gear_exact_authority import (
        reload_exact_authority_envelope,
        reload_exact_progression,
    )
    from .gear_exact_authority_store import ExactAuthorityBundle
    from .gear_exact_item_instance import (
        reload_exact_item,
        reload_exact_static_facts,
    )
    from .simc_item_effect_support import (
        reload_effect_aggregate,
        reload_effect_record,
    )
except ImportError:
    from gear_contracts import CANONICAL_GEAR_SLOTS
    from gear_exact_authority import reload_exact_authority_envelope, reload_exact_progression
    from gear_exact_authority_store import ExactAuthorityBundle
    from gear_exact_item_instance import reload_exact_item, reload_exact_static_facts
    from simc_item_effect_support import reload_effect_aggregate, reload_effect_record


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
RESOLVED_LOADOUT_V2_SCHEMA_REVISION = "resolved-loadout-v2"
RESOLVED_LOADOUT_V2_KEY_PATTERN = re.compile(
    r"^resolved-loadout-v2:sha256:[0-9a-f]{64}$"
)
EXACT_AUTHORITY_ENVELOPE_KEY_PATTERN = re.compile(
    r"^exact-authority:sha256:[0-9a-f]{64}$"
)
EFFECT_RECORD_KEY_PATTERN = re.compile(
    r"^simc-item-effect-record:sha256:[0-9a-f]{64}$"
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


def _v2_document(value: Any) -> dict[str, Any]:
    """Return the decoded payload for one already rehydrated sealed document."""
    raw = getattr(value, "canonical_bytes", None)
    if isinstance(raw, bytes):
        try:
            decoded = json.loads(raw)
        except (TypeError, ValueError, UnicodeDecodeError):
            return {}
        if not isinstance(decoded, Mapping):
            return {}
        payload = _canonical(decoded)
        content_key = _text(getattr(value, "content_key", ""))
        if content_key:
            payload["content_key"] = content_key
        return payload
    return {}


def _rehydrate_v2_bundle(
    value: Any,
    *,
    resolver_revision: str,
    simc_runtime_revision: str,
) -> dict[str, dict[str, Any]] | None:
    """Verify one complete Exact Authority Bundle before resolving v2 facts."""
    if type(value) is not ExactAuthorityBundle or type(value.effect_records) is not tuple or not value.effect_records:
        return None
    try:
        exact = reload_exact_item(
            value.exact_item.canonical_bytes,
            value.exact_item.content_key,
        )
        static_facts = reload_exact_static_facts(
            value.static_facts.canonical_bytes,
            value.static_facts.content_key,
            exact=exact,
        )
        progression = reload_exact_progression(
            value.progression.canonical_bytes,
            value.progression.content_key,
            exact=exact,
        )
        records = tuple(
            reload_effect_record(
                record.canonical_bytes,
                record.content_key,
                runtime_revision=simc_runtime_revision,
            )
            for record in value.effect_records
        )
        effect_support = reload_effect_aggregate(
            value.effect_support.canonical_bytes,
            value.effect_support.content_key,
            exact=exact,
            runtime_revision=simc_runtime_revision,
            records=records,
        )
        envelope = reload_exact_authority_envelope(
            value.envelope.canonical_bytes,
            value.envelope.content_key,
            exact=exact,
            static_facts=static_facts,
            progression=progression,
            effect_support=effect_support,
            resolver_revision=resolver_revision,
        )
    except (AttributeError, TypeError, ValueError):
        return None
    return {
        "envelope": _v2_document(envelope),
        "exact_item": _v2_document(exact),
        "progression": _v2_document(progression),
        "effect_support": _v2_document(effect_support),
    }

def _v2_blocked(problems: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = _dedupe_problems(problems)
    return {
        "schemaRevision": RESOLVED_LOADOUT_V2_SCHEMA_REVISION,
        "status": "blocked",
        "problemCodes": sorted({_text(problem.get("code")) for problem in normalized if problem.get("code")}),
        "problems": normalized,
    }


def _v2_simc_options(exact: Mapping[str, Any]) -> dict[str, str] | None:
    """Project sealed Exact fields into the fixed SimC serializer surface."""
    return canonical_simc_options({
        "id": _text(exact.get("itemId")),
        "ilevel": _text(exact.get("itemLevel") or exact.get("declaredItemLevel")),
        "bonus_id": exact.get("bonusIds") or [],
        "gem_id": exact.get("gemIds") or [],
        "gem_bonus_id": exact.get("gemBonusIds") or [],
        "gem_ilevel": exact.get("gemItemLevels") or [],
        "enchant_id": _text(exact.get("enchantId")),
        "crafted_stats": exact.get("craftedStats") or [],
        "embellishment": exact.get("embellishmentIds") or [],
        "redirected_base_stats": exact.get("redirectedBaseStats") or [],
    })


def build_resolved_loadout_v2(
    *,
    resolver_snapshot: Any,
    exact_authority_by_slot: Any,
    authority_bundles: Any,
    gear_rule_revision: str,
    resolver_revision: str,
    simc_runtime_revision: str,
    origin_catalog_revision: str = "",
) -> dict[str, Any]:
    """Build a catalog-independent v2 loadout from slot-bound authority bundles."""
    snapshot = dict(resolver_snapshot) if isinstance(resolver_snapshot, Mapping) else {}
    bundles = dict(authority_bundles) if isinstance(authority_bundles, Mapping) else {}
    rule = _text(gear_rule_revision)
    resolver = _text(resolver_revision)
    runtime = _text(simc_runtime_revision)
    problems: list[dict[str, str]] = []
    readiness = snapshot.get("profileReadiness") if isinstance(snapshot.get("profileReadiness"), Mapping) else {}
    slots = snapshot.get("resolvedSlots") if isinstance(snapshot.get("resolvedSlots"), Mapping) else {}
    required = [slot for slot in CANONICAL_GEAR_SLOTS if slot in set(readiness.get("requiredSlots") or [])]
    if not rule or not resolver or not runtime or not required or readiness.get("status") != "verified" or readiness.get("simcReady") is not True:
        problems.append(_problem("LOADOUT_V2_RESOLVER_NOT_READY", "resolverSnapshot", "V2 requires one verified resolver snapshot and revisions."))
    if not isinstance(exact_authority_by_slot, list) or not exact_authority_by_slot:
        problems.append(_problem("LOADOUT_V2_EXACT_AUTHORITY_REQUIRED", "exactAuthorityBySlot", "V2 requires non-empty slot-bound exact authority."))
        pairs: list[dict[str, str]] = []
    else:
        pairs = []
        seen_slots: set[str] = set()
        seen_keys: set[str] = set()
        for index, raw in enumerate(exact_authority_by_slot):
            row = dict(raw) if isinstance(raw, Mapping) else {}
            slot = _text(row.get("slot"))
            key = _text(row.get("exactAuthorityEnvelopeKey"))
            if slot not in CANONICAL_GEAR_SLOTS or not EXACT_AUTHORITY_ENVELOPE_KEY_PATTERN.fullmatch(key):
                problems.append(_problem("LOADOUT_V2_EXACT_AUTHORITY_INVALID", f"exactAuthorityBySlot[{index}]", "Exact authority pair is invalid."))
                continue
            if slot in seen_slots:
                problems.append(_problem("LOADOUT_V2_SLOT_DUPLICATE", f"exactAuthorityBySlot[{index}].slot", "A slot may occur once."))
            if key in seen_keys:
                problems.append(_problem("LOADOUT_EXACT_AUTHORITY_REUSED", f"exactAuthorityBySlot[{index}].exactAuthorityEnvelopeKey", "One envelope cannot bind two slots."))
            seen_slots.add(slot)
            seen_keys.add(key)
            pairs.append({"slot": slot, "exactAuthorityEnvelopeKey": key})
        pairs.sort(key=lambda pair: CANONICAL_GEAR_SLOTS.index(pair["slot"]))
    if [pair["slot"] for pair in pairs] != required:
        problems.append(_problem("LOADOUT_V2_SLOT_BINDING_MISMATCH", "exactAuthorityBySlot", "Authority pairs must equal the occupied resolver slots."))

    occurrences: list[dict[str, Any]] = []
    ordered_slots: list[dict[str, Any]] = []
    for pair in pairs:
        slot, key = pair["slot"], pair["exactAuthorityEnvelopeKey"]
        bundle = _rehydrate_v2_bundle(
            bundles.get(key),
            resolver_revision=resolver,
            simc_runtime_revision=runtime,
        )
        if bundle is None:
            problems.append(_problem("LOADOUT_V2_AUTHORITY_BUNDLE_INVALID", f"authorityBundles.{key}", "V2 requires one fully rehydrated Exact Authority Bundle."))
            continue
        envelope = bundle["envelope"]
        exact = bundle["exact_item"]
        progression = bundle["progression"]
        effect_support = bundle["effect_support"]
        if _text(envelope.get("content_key") or envelope.get("contentKey")) != key or _text(envelope.get("resolverRevision")) != resolver:
            problems.append(_problem("LOADOUT_V2_ENVELOPE_INVALID", f"authorityBundles.{key}", "Envelope key or resolver revision does not match."))
        track = progression.get("trackAuthorityInput") if isinstance(progression.get("trackAuthorityInput"), Mapping) else {}
        if _text(progression.get("gearRuleRevision")) != rule or _text(track.get("slot")) != slot:
            problems.append(_problem("LOADOUT_V2_PROGRESSION_SLOT_MISMATCH", f"authorityBundles.{key}.progression", "Progression must bind this exact slot and rule revision."))
        resolved = slots.get(slot) if isinstance(slots.get(slot), Mapping) else {}
        options = _v2_simc_options(exact)
        if resolved.get("legality", {}).get("status") != "verified" or _text(resolved.get("itemId")) != _text(exact.get("itemId")):
            problems.append(_problem("LOADOUT_V2_RESOLVED_SLOT_MISMATCH", f"resolverSnapshot.resolvedSlots.{slot}", "Resolver slot must match the sealed Exact item."))
        if options is None or not options.get("id"):
            problems.append(_problem("LOADOUT_V2_SERIALIZER_INPUT_INVALID", f"authorityBundles.{key}.exactItem", "Sealed Exact serializer fields are invalid."))
        subjects = effect_support.get("subjects") if isinstance(effect_support.get("subjects"), list) else []
        if effect_support.get("status") != "verified" or _text(effect_support.get("simcRuntimeRevision")) != runtime:
            problems.append(_problem("LOADOUT_V2_EFFECT_SUPPORT_NOT_READY", f"authorityBundles.{key}.effectSupport", "Every slot effect aggregate must be verified for this runtime."))
        for ordinal, raw in enumerate(subjects):
            subject = dict(raw) if isinstance(raw, Mapping) else {}
            record_key = _text(subject.get("supportRecordKey"))
            if (subject.get("status", "verified") != "verified" or not _text(subject.get("subjectKind")) or not _text(subject.get("subjectKey")) or not _text(subject.get("subjectVariantSignature")) or not EFFECT_RECORD_KEY_PATTERN.fullmatch(record_key)):
                problems.append(_problem("LOADOUT_V2_EFFECT_RECORD_INVALID", f"authorityBundles.{key}.effectSupport.subjects[{ordinal}]", "Effect record is not verified."))
                continue
            occurrences.append({"scope": "slot", "slot": slot, "exactAuthorityEnvelopeKey": key, "recordOrdinal": ordinal, "subjectKind": _text(subject.get("subjectKind")), "subjectKey": _text(subject.get("subjectKey")), "subjectVariantSignature": _text(subject.get("subjectVariantSignature")), "supportRecordKey": record_key})
        ordered_slots.append({"slot": slot, "itemId": _text(exact.get("itemId")), "exactAuthorityEnvelopeKey": key, "simcOptions": options or {}})
    if problems:
        return _v2_blocked(problems)
    identity = {"classKey": _text(snapshot.get("eligibilityContext", {}).get("classKey")) if isinstance(snapshot.get("eligibilityContext"), Mapping) else "", "specKey": _text(snapshot.get("eligibilityContext", {}).get("specKey")) if isinstance(snapshot.get("eligibilityContext"), Mapping) else "", "exactAuthorityBySlot": pairs, "orderedSlots": ordered_slots, "effectEvidenceByOccurrence": occurrences, "gearRuleRevision": rule, "resolverRevision": resolver, "simcRuntimeRevision": runtime}
    row = {"schemaRevision": RESOLVED_LOADOUT_V2_SCHEMA_REVISION, "status": "ready", "resolvedLoadoutKey": _hash("resolved-loadout-v2:sha256:", identity), "exactAuthorityBySlot": pairs, "effectEvidenceByOccurrence": occurrences, "gearRuleRevision": rule, "resolverRevision": resolver, "simcRuntimeRevision": runtime, "eligibilityContext": _canonical(snapshot.get("eligibilityContext") or {}), "orderedSlots": ordered_slots, "serializerInput": _canonical(snapshot.get("serializerInput") or {}), "problemCodes": [], "problems": []}
    if _text(origin_catalog_revision):
        row["originCatalogRevision"] = _text(origin_catalog_revision)
    row["rowHash"] = _hash("sha256:", {key: value for key, value in row.items() if key not in {"rowHash", "originCatalogRevision"}})
    return row


def verify_resolved_loadout_v2(value: Any) -> list[str]:
    row = dict(value) if isinstance(value, Mapping) else {}
    issues: list[str] = []
    if row.get("schemaRevision") != RESOLVED_LOADOUT_V2_SCHEMA_REVISION:
        return ["RESOLVED_LOADOUT_V2_SCHEMA_INVALID"]
    if row.get("status") != "ready":
        return ["RESOLVED_LOADOUT_V2_NOT_READY"]
    raw_evidence = row.get("effectEvidenceByOccurrence")
    if not isinstance(raw_evidence, list):
        return ["RESOLVED_LOADOUT_V2_EFFECT_EVIDENCE_INVALID"]
    pairs = row.get("exactAuthorityBySlot") if isinstance(row.get("exactAuthorityBySlot"), list) else []
    slots = [_text(pair.get("slot")) for pair in pairs if isinstance(pair, Mapping)]
    keys = [_text(pair.get("exactAuthorityEnvelopeKey")) for pair in pairs if isinstance(pair, Mapping)]
    if any(not isinstance(pair, Mapping) or set(pair) != {"slot", "exactAuthorityEnvelopeKey"} or not isinstance(pair.get("slot"), str) or pair.get("slot") not in CANONICAL_GEAR_SLOTS or not isinstance(pair.get("exactAuthorityEnvelopeKey"), str) for pair in pairs):
        issues.append("RESOLVED_LOADOUT_V2_SLOT_BINDING_INVALID")
    if not pairs or slots != sorted(slots, key=lambda slot: CANONICAL_GEAR_SLOTS.index(slot) if slot in CANONICAL_GEAR_SLOTS else len(CANONICAL_GEAR_SLOTS)) or len(set(slots)) != len(slots):
        issues.append("RESOLVED_LOADOUT_V2_SLOT_ORDER_INVALID")
    if len(set(keys)) != len(keys) or any(not EXACT_AUTHORITY_ENVELOPE_KEY_PATTERN.fullmatch(key) for key in keys):
        issues.append("RESOLVED_LOADOUT_V2_ENVELOPE_BINDING_INVALID")
    evidence = raw_evidence
    def occurrence_sort_key(item: Any) -> tuple[int, int]:
        if not isinstance(item, Mapping):
            return len(CANONICAL_GEAR_SLOTS), -1
        slot = _text(item.get("slot"))
        ordinal = item.get("recordOrdinal")
        return (CANONICAL_GEAR_SLOTS.index(slot) if slot in CANONICAL_GEAR_SLOTS else len(CANONICAL_GEAR_SLOTS), ordinal if type(ordinal) is int else -1)
    expected_evidence = sorted(evidence, key=occurrence_sort_key)
    if evidence != expected_evidence:
        issues.append("RESOLVED_LOADOUT_V2_EFFECT_ORDER_INVALID")
    pair_by_slot = {pair["slot"]: pair["exactAuthorityEnvelopeKey"] for pair in pairs if isinstance(pair, Mapping) and _text(pair.get("slot")) and _text(pair.get("exactAuthorityEnvelopeKey"))}
    ordered_slots = row.get("orderedSlots") if isinstance(row.get("orderedSlots"), list) else []
    if any(not isinstance(item, Mapping) or set(item) != {"slot", "itemId", "exactAuthorityEnvelopeKey", "simcOptions"} or not isinstance(item.get("simcOptions"), Mapping) for item in ordered_slots) or [(_text(item.get("slot")), _text(item.get("exactAuthorityEnvelopeKey"))) for item in ordered_slots if isinstance(item, Mapping)] != [(slot, key) for slot, key in zip(slots, keys, strict=True)]:
        issues.append("RESOLVED_LOADOUT_V2_SLOT_BINDING_MISMATCH")
    next_ordinal: dict[str, int] = {}
    for occurrence in evidence:
        current = dict(occurrence) if isinstance(occurrence, Mapping) else {}
        slot = _text(current.get("slot"))
        key = _text(current.get("exactAuthorityEnvelopeKey"))
        ordinal = current.get("recordOrdinal")
        if (set(current) != {"scope", "slot", "exactAuthorityEnvelopeKey", "recordOrdinal", "subjectKind", "subjectKey", "subjectVariantSignature", "supportRecordKey"} or current.get("scope") != "slot" or pair_by_slot.get(slot) != key or type(ordinal) is not int or ordinal != next_ordinal.get(slot, 0) or not _text(current.get("subjectKind")) or not _text(current.get("subjectKey")) or not _text(current.get("subjectVariantSignature")) or not EFFECT_RECORD_KEY_PATTERN.fullmatch(_text(current.get("supportRecordKey")))):
            issues.append("RESOLVED_LOADOUT_V2_EFFECT_OCCURRENCE_INVALID")
            break
        next_ordinal[slot] = ordinal + 1
    identity = {"classKey": _text(row.get("eligibilityContext", {}).get("classKey")) if isinstance(row.get("eligibilityContext"), Mapping) else "", "specKey": _text(row.get("eligibilityContext", {}).get("specKey")) if isinstance(row.get("eligibilityContext"), Mapping) else "", "exactAuthorityBySlot": pairs, "orderedSlots": ordered_slots, "effectEvidenceByOccurrence": evidence, "gearRuleRevision": _text(row.get("gearRuleRevision")), "resolverRevision": _text(row.get("resolverRevision")), "simcRuntimeRevision": _text(row.get("simcRuntimeRevision"))}
    if _text(row.get("resolvedLoadoutKey")) != _hash("resolved-loadout-v2:sha256:", identity):
        issues.append("RESOLVED_LOADOUT_V2_IDENTITY_MISMATCH")
    expected_hash = _hash("sha256:", {key: value for key, value in row.items() if key not in {"rowHash", "originCatalogRevision"}})
    if _text(row.get("rowHash")) != expected_hash:
        issues.append("RESOLVED_LOADOUT_V2_ROW_HASH_INVALID")
    return issues


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
    "RESOLVED_LOADOUT_V2_SCHEMA_REVISION",
    "SIMC_OPTION_ORDER",
    "build_resolved_loadout",
    "build_resolved_loadout_v2",
    "build_resolved_loadout_from_registry",
    "canonical_simc_options",
    "verify_resolved_loadout",
    "verify_resolved_loadout_v2",
)

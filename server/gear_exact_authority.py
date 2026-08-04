#!/usr/bin/env python3
"""Strict, cross-bound authority envelope for one ready Exact item."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Mapping

try:
    from .gear_canonical_kernel import (
        CanonicalIssue,
        CanonicalResult,
        CanonicalValueError,
        SealedCanonicalDocument,
        canonical_identity_token,
        canonical_int,
        canonical_json_bytes,
        canonical_mapping,
        canonical_set_list,
        canonical_slot,
        seal_canonical_document,
        verified_payload_copy,
    )
    from .gear_exact_item_instance import (
        EXACT_ITEM_DOCUMENT_KIND,
        EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
        EXACT_ITEM_KEY_PREFIX,
        EXACT_STATIC_FACTS_DOCUMENT_KIND,
        EXACT_STATIC_FACTS_KEY_PREFIX,
        EXACT_STATIC_FACTS_SCHEMA_REVISION,
        _validate_exact_item_payload,
        _validate_exact_static_facts_payload,
        _verified_exact_payload_copy,
        build_exact_item_identity,
        seal_exact_static_facts,
    )
    from .gear_track_authority import resolve_exact_instance_progression
    from .simc_item_effect_support import (
        EFFECT_AGGREGATE_DOCUMENT_KIND,
        EFFECT_AGGREGATE_KEY_PREFIX,
        EFFECT_SUPPORT_SCHEMA_REVISION,
        _validate_effect_aggregate_payload,
        effect_support_key,
        resolve_exact_item_effect_support,
        validate_effect_record,
    )
except ImportError:
    from gear_canonical_kernel import (
        CanonicalIssue,
        CanonicalResult,
        CanonicalValueError,
        SealedCanonicalDocument,
        canonical_identity_token,
        canonical_int,
        canonical_json_bytes,
        canonical_mapping,
        canonical_set_list,
        canonical_slot,
        seal_canonical_document,
        verified_payload_copy,
    )
    from gear_exact_item_instance import (
        EXACT_ITEM_DOCUMENT_KIND,
        EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
        EXACT_ITEM_KEY_PREFIX,
        EXACT_STATIC_FACTS_DOCUMENT_KIND,
        EXACT_STATIC_FACTS_KEY_PREFIX,
        EXACT_STATIC_FACTS_SCHEMA_REVISION,
        _validate_exact_item_payload,
        _validate_exact_static_facts_payload,
        _verified_exact_payload_copy,
        build_exact_item_identity,
        seal_exact_static_facts,
    )
    from gear_track_authority import resolve_exact_instance_progression
    from simc_item_effect_support import (
        EFFECT_AGGREGATE_DOCUMENT_KIND,
        EFFECT_AGGREGATE_KEY_PREFIX,
        EFFECT_SUPPORT_SCHEMA_REVISION,
        _validate_effect_aggregate_payload,
        effect_support_key,
        resolve_exact_item_effect_support,
        validate_effect_record,
    )


_EXACT_KEY_PATTERN = re.compile(r"^exact-item-instance:sha256:[0-9a-f]{64}$")
_PROGRESSION_KEY_PATTERN = re.compile(r"^exact-progression:sha256:[0-9a-f]{64}$")
_FORBIDDEN_FRAGMENTS = ("owner", "catalog", "observ", "provenance", "sourceurl", "profileurl")
_EXACT_OUTPUT_KEYS = frozenset({"status", "schemaRevision", "exactItemInstanceKey", "exactVariantSignature", "enhancementSelectionKey", "itemId", "bonusIds", "context", "itemLevel", "redirectedBaseStats", "enhancementSelection", "serializerInput", "problemCodes", "problems"})
_STATIC_KEYS = frozenset({"schemaRevision", "exactItemInstanceKey", "facts"})
_PROGRESSION_KEYS = frozenset({
    "schemaRevision", "exactItemInstanceKey", "gearRuleRevision",
    "trackAuthorityRuleRevision", "trackAuthorityRecordKey",
    "trackAuthorityInput", "progressionState", "progressionBindingKey",
})
_TRACK_AUTHORITY_INPUT_KEYS = frozenset({
    "seasonRevision", "gearRuleRevision", "slot", "hasCraftedSource",
})
_SERIALIZER_FIELDS = frozenset({"id", "ilevel", "bonus_id", "gem_id", "gem_bonus_id", "gem_ilevel", "enchant_id", "crafted_stats", "embellishment"})
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,256}$")
_SEALED_PROGRESSION_DOCUMENT_KIND = "exact_progression"
_SEALED_PROGRESSION_SCHEMA_REVISION = "exact-progression-binding-v1"
_SEALED_PROGRESSION_KEY_PREFIX = "exact-progression:sha256:"
_SEALED_PROGRESSION_PAYLOAD_KEYS = frozenset({
    "schemaRevision", "exactItemInstanceKey", "gearRuleRevision",
    "trackAuthorityRuleRevision", "trackAuthorityRecordKey",
    "trackAuthorityInput", "progressionState",
})
_SEALED_TRACK_AUTHORITY_INPUT_KEYS = frozenset({
    "seasonRevision", "gearRuleRevision", "rowFamily", "status", "itemId",
    "variantKey", "itemLevel", "bonusIds", "slot", "hasCraftedSource",
})
_SEALED_AUTHORITY_DOCUMENT_KIND = "exact_authority"
_SEALED_AUTHORITY_SCHEMA_REVISION = "exact-authority-envelope-v1"
_SEALED_AUTHORITY_KEY_PREFIX = "exact-authority:sha256:"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _hash(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(_canonical(value)).hexdigest()


def _blocked(code: str) -> dict[str, Any]:
    return {"schemaRevision": "exact-authority-envelope-v1", "status": "blocked", "problemCodes": [code]}


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(any(fragment in re.sub(r"[^a-z0-9]", "", str(key).lower()) for fragment in _FORBIDDEN_FRAGMENTS) or _contains_forbidden(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden(item) for item in value)
    return False


def _valid_exact(exact: Mapping[str, Any]) -> bool:
    if set(exact) != _EXACT_OUTPUT_KEYS or exact.get("schemaRevision") != "gear-exact-item-instance-v2" or exact.get("status") != "verified":
        return False
    try:
        selection = exact["enhancementSelection"]
        if not isinstance(selection, Mapping):
            return False
        rebuilt = build_exact_item_identity({}, {
            "itemId": exact["itemId"],
            "declaredItemLevel": exact["itemLevel"],
            "bonusIds": exact["bonusIds"],
            "context": exact["context"],
            "gemIds": selection["gemIds"],
            "gemBonusIds": selection["gemBonusIds"],
            "gemItemLevels": selection["gemItemLevels"],
            "enchantId": selection["enchantId"],
            "craftedStats": selection["craftedStats"],
            "embellishmentIds": selection["embellishmentIds"],
            "redirectedBaseStats": exact["redirectedBaseStats"],
        })
        return rebuilt.get("status") == "verified" and dict(exact) == rebuilt
    except (KeyError, TypeError, ValueError):
        return False


def _valid_token(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value == value.strip()
        and _TOKEN_PATTERN.fullmatch(value) is not None
        and not any(ord(character) < 32 or ord(character) == 127 for character in value)
    )


def _expected_serializer(exact: Mapping[str, Any]) -> dict[str, str]:
    selection = exact["enhancementSelection"]
    result = {"id": exact["itemId"], "ilevel": str(exact["itemLevel"])}
    for field, values in (("bonus_id", exact["bonusIds"]), ("gem_id", selection.get("gemIds") or []), ("gem_bonus_id", selection.get("gemBonusIds") or []), ("gem_ilevel", selection.get("gemItemLevels") or []), ("crafted_stats", selection.get("craftedStats") or []), ("embellishment", selection.get("embellishmentIds") or [])):
        if values:
            result[field] = "/".join(str(value) for value in values)
    if selection.get("enchantId"):
        result["enchant_id"] = str(selection["enchantId"])
    return result


def _valid_static_facts(value: Any, exact_key: str) -> bool:
    return (
        isinstance(value, Mapping) and set(value) == _STATIC_KEYS
        and value.get("schemaRevision") == "exact-static-facts-v1"
        and value.get("exactItemInstanceKey") == exact_key
        and isinstance(value.get("facts"), Mapping) and bool(value["facts"])
        and all(_valid_token(key) for key in value["facts"])
        and all(isinstance(amount, (int, float)) and not isinstance(amount, bool) and math.isfinite(amount) for amount in value["facts"].values())
    )


def _canonical_progression_identifier(value: object, path: str) -> str:
    return canonical_identity_token(value, path=path)


def _validate_exact_progression_payload(
    value: object,
    *,
    exact: SealedCanonicalDocument,
) -> object:
    """Rebuild decoded progression bytes against one verified sealed Exact."""

    exact_payload = _verified_exact_payload_copy(exact)
    payload = canonical_mapping(
        value,
        path="exactProgression",
        exact_keys=_SEALED_PROGRESSION_PAYLOAD_KEYS,
    )
    if payload["schemaRevision"] != _SEALED_PROGRESSION_SCHEMA_REVISION:
        raise CanonicalValueError(
            "SCHEMA_REVISION_MISMATCH", "exactProgression.schemaRevision",
        )
    if payload["exactItemInstanceKey"] != exact.content_key:
        raise CanonicalValueError(
            "EXACT_ITEM_BINDING_MISMATCH",
            "exactProgression.exactItemInstanceKey",
        )
    gear_rule_revision = canonical_identity_token(
        payload["gearRuleRevision"],
        path="exactProgression.gearRuleRevision",
    )
    track_rule_revision = canonical_identity_token(
        payload["trackAuthorityRuleRevision"],
        path="exactProgression.trackAuthorityRuleRevision",
    )
    track_record_key = canonical_identity_token(
        payload["trackAuthorityRecordKey"],
        path="exactProgression.trackAuthorityRecordKey",
    )
    authority = canonical_mapping(
        payload["trackAuthorityInput"],
        path="exactProgression.trackAuthorityInput",
        exact_keys=_SEALED_TRACK_AUTHORITY_INPUT_KEYS,
    )
    season_revision = canonical_identity_token(
        authority["seasonRevision"],
        path="exactProgression.trackAuthorityInput.seasonRevision",
    )
    authority_rule_revision = canonical_identity_token(
        authority["gearRuleRevision"],
        path="exactProgression.trackAuthorityInput.gearRuleRevision",
    )
    row_family = canonical_identity_token(
        authority["rowFamily"],
        path="exactProgression.trackAuthorityInput.rowFamily",
    )
    status = canonical_identity_token(
        authority["status"],
        path="exactProgression.trackAuthorityInput.status",
    )
    item_id = canonical_identity_token(
        authority["itemId"],
        path="exactProgression.trackAuthorityInput.itemId",
    )
    variant_key = canonical_identity_token(
        authority["variantKey"],
        path="exactProgression.trackAuthorityInput.variantKey",
    )
    item_level = canonical_int(
        authority["itemLevel"],
        path="exactProgression.trackAuthorityInput.itemLevel",
        minimum=1,
        maximum=9999,
    )
    bonus_ids = canonical_set_list(
        authority["bonusIds"],
        path="exactProgression.trackAuthorityInput.bonusIds",
        item_rule=_canonical_progression_identifier,
        max_items=256,
    )
    slot = canonical_slot(
        authority["slot"],
        path="exactProgression.trackAuthorityInput.slot",
    )
    if type(authority["hasCraftedSource"]) is not bool:
        raise CanonicalValueError(
            "INVALID_BOOLEAN",
            "exactProgression.trackAuthorityInput.hasCraftedSource",
        )
    has_crafted_source = authority["hasCraftedSource"]
    if row_family != "exact_instance" or status != "verified":
        raise CanonicalValueError(
            "INVALID_TRACK_AUTHORITY_INPUT",
            "exactProgression.trackAuthorityInput",
        )
    if gear_rule_revision != authority_rule_revision:
        raise CanonicalValueError(
            "GEAR_RULE_REVISION_MISMATCH",
            "exactProgression.gearRuleRevision",
        )
    if (
        item_id != exact_payload["itemId"]
        or variant_key != exact.content_key
        or item_level != exact_payload["itemLevel"]
        or list(bonus_ids) != exact_payload["bonusIds"]
    ):
        raise CanonicalValueError(
            "EXACT_ITEM_BINDING_MISMATCH",
            "exactProgression.trackAuthorityInput",
        )
    canonical_input = {
        "seasonRevision": season_revision,
        "gearRuleRevision": authority_rule_revision,
        "rowFamily": row_family,
        "status": status,
        "itemId": item_id,
        "variantKey": variant_key,
        "itemLevel": item_level,
        "bonusIds": list(bonus_ids),
        "slot": slot,
        "hasCraftedSource": has_crafted_source,
    }
    if dict(authority) != canonical_input:
        raise CanonicalValueError(
            "TRACK_AUTHORITY_INPUT_MISMATCH",
            "exactProgression.trackAuthorityInput",
        )
    resolved = resolve_exact_instance_progression(
        {
            "seasonRevision": season_revision,
            "gearRuleRevision": authority_rule_revision,
        },
        canonical_input,
    )
    if resolved.get("status") != "verified":
        raise CanonicalValueError(
            "TRACK_AUTHORITY_BLOCKED",
            "exactProgression.trackAuthorityInput",
        )
    if track_rule_revision != resolved.get("ruleRevision"):
        raise CanonicalValueError(
            "TRACK_AUTHORITY_RULE_MISMATCH",
            "exactProgression.trackAuthorityRuleRevision",
        )
    if track_record_key != resolved.get("recordKey"):
        raise CanonicalValueError(
            "TRACK_AUTHORITY_RECORD_MISMATCH",
            "exactProgression.trackAuthorityRecordKey",
        )
    if canonical_json_bytes(payload["progressionState"]) != canonical_json_bytes(
        resolved.get("progressionState")
    ):
        raise CanonicalValueError(
            "TRACK_AUTHORITY_STATE_MISMATCH",
            "exactProgression.progressionState",
        )
    return value


def _blocked_progression(error: CanonicalValueError) -> CanonicalResult:
    return CanonicalResult(
        "blocked",
        None,
        (CanonicalIssue(
            error.code,
            error.path,
            "Re-import the exact item and use the current canonical progression inputs.",
        ),),
    )


def seal_exact_progression(
    exact: SealedCanonicalDocument,
    *,
    season_revision: str,
    gear_rule_revision: str,
    slot: str,
    has_crafted_source: bool,
) -> CanonicalResult:
    """Seal only the progression state returned by production Track Authority."""

    try:
        canonical_slot_value = canonical_slot(slot, path="exactProgression.slot")
        canonical_season_revision = canonical_identity_token(
            season_revision, path="exactProgression.seasonRevision",
        )
        canonical_gear_rule_revision = canonical_identity_token(
            gear_rule_revision, path="exactProgression.gearRuleRevision",
        )
        if type(has_crafted_source) is not bool:
            raise CanonicalValueError(
                "INVALID_BOOLEAN", "exactProgression.hasCraftedSource",
            )
        exact_payload = _verified_exact_payload_copy(exact)
        authority_input = {
            "seasonRevision": canonical_season_revision,
            "gearRuleRevision": canonical_gear_rule_revision,
            "rowFamily": "exact_instance",
            "status": "verified",
            "itemId": exact_payload["itemId"],
            "variantKey": exact.content_key,
            "itemLevel": exact_payload["itemLevel"],
            "bonusIds": list(exact_payload["bonusIds"]),
            "slot": canonical_slot_value,
            "hasCraftedSource": has_crafted_source,
        }
        resolved = resolve_exact_instance_progression(
            {
                "seasonRevision": canonical_season_revision,
                "gearRuleRevision": canonical_gear_rule_revision,
            },
            authority_input,
        )
        if resolved.get("status") != "verified":
            issues = tuple(
                CanonicalIssue(
                    problem.get("code")
                    if type(problem.get("code")) is str
                    else "TRACK_AUTHORITY_BLOCKED",
                    "exactProgression.trackAuthorityInput",
                    "Choose an exact item with verified current-season progression evidence.",
                )
                for problem in resolved.get("problems", ())
                if type(problem) is dict
            )
            return CanonicalResult(
                "blocked",
                None,
                issues or (CanonicalIssue(
                    "TRACK_AUTHORITY_BLOCKED",
                    "exactProgression.trackAuthorityInput",
                    "Choose an exact item with verified current-season progression evidence.",
                ),),
            )
        payload = {
            "schemaRevision": _SEALED_PROGRESSION_SCHEMA_REVISION,
            "exactItemInstanceKey": exact.content_key,
            "gearRuleRevision": canonical_gear_rule_revision,
            "trackAuthorityRuleRevision": resolved["ruleRevision"],
            "trackAuthorityRecordKey": resolved["recordKey"],
            "trackAuthorityInput": authority_input,
            "progressionState": resolved["progressionState"],
        }
        _validate_exact_progression_payload(payload, exact=exact)
        document = seal_canonical_document(
            document_kind=_SEALED_PROGRESSION_DOCUMENT_KIND,
            schema_revision=_SEALED_PROGRESSION_SCHEMA_REVISION,
            payload=payload,
            key_prefix=_SEALED_PROGRESSION_KEY_PREFIX,
        )
        return CanonicalResult("verified", document, ())
    except CanonicalValueError as error:
        return _blocked_progression(error)


def _blocked_exact_authority(error: CanonicalValueError) -> CanonicalResult:
    return CanonicalResult(
        "blocked",
        None,
        (CanonicalIssue(
            error.code,
            error.path,
            "Rebuild every authority document from the same sealed Exact item.",
        ),),
    )


def _validate_effect_aggregate_for_envelope(
    value: object,
    *,
    exact: SealedCanonicalDocument,
) -> object:
    runtime_revision = (
        value.get("simcRuntimeRevision")
        if type(value) is dict
        else None
    )
    return _validate_effect_aggregate_payload(
        value,
        exact=exact,
        runtime_revision=runtime_revision,
    )


def seal_exact_authority_envelope(
    *,
    exact: SealedCanonicalDocument,
    static_facts: SealedCanonicalDocument,
    progression: SealedCanonicalDocument,
    effect_support: SealedCanonicalDocument,
    resolver_revision: str,
) -> CanonicalResult:
    """Compose four independently re-verified Exact-bound documents."""

    documents = {
        "exact": exact,
        "static_facts": static_facts,
        "progression": progression,
        "effect_support": effect_support,
    }
    for field, document in documents.items():
        if type(document) is not SealedCanonicalDocument:
            raise TypeError(f"{field} must be an exact SealedCanonicalDocument.")

    try:
        verified_payload_copy(
            exact,
            document_kind=EXACT_ITEM_DOCUMENT_KIND,
            schema_revision=EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
            key_prefix=EXACT_ITEM_KEY_PREFIX,
            payload_validator=_validate_exact_item_payload,
        )
        static_payload = verified_payload_copy(
            static_facts,
            document_kind=EXACT_STATIC_FACTS_DOCUMENT_KIND,
            schema_revision=EXACT_STATIC_FACTS_SCHEMA_REVISION,
            key_prefix=EXACT_STATIC_FACTS_KEY_PREFIX,
            payload_validator=_validate_exact_static_facts_payload,
        )
        progression_payload = verified_payload_copy(
            progression,
            document_kind=_SEALED_PROGRESSION_DOCUMENT_KIND,
            schema_revision=_SEALED_PROGRESSION_SCHEMA_REVISION,
            key_prefix=_SEALED_PROGRESSION_KEY_PREFIX,
            payload_validator=lambda payload: _validate_exact_progression_payload(
                payload,
                exact=exact,
            ),
        )
        effect_payload = verified_payload_copy(
            effect_support,
            document_kind=EFFECT_AGGREGATE_DOCUMENT_KIND,
            schema_revision=EFFECT_SUPPORT_SCHEMA_REVISION,
            key_prefix=EFFECT_AGGREGATE_KEY_PREFIX,
            payload_validator=lambda payload: _validate_effect_aggregate_for_envelope(
                payload,
                exact=exact,
            ),
        )
        exact_key = exact.content_key
        for payload, path in (
            (static_payload, "exactAuthority.staticFacts"),
            (progression_payload, "exactAuthority.progression"),
            (effect_payload, "exactAuthority.effectSupport"),
        ):
            if payload["exactItemInstanceKey"] != exact_key:
                raise CanonicalValueError(
                    "EXACT_ITEM_BINDING_MISMATCH",
                    f"{path}.exactItemInstanceKey",
                )
        if effect_payload["status"] != "verified":
            raise CanonicalValueError(
                "EFFECT_SUPPORT_NOT_VERIFIED",
                "exactAuthority.effectSupport.status",
            )
        resolver = canonical_identity_token(
            resolver_revision,
            path="exactAuthority.resolverRevision",
        )
        document = seal_canonical_document(
            document_kind=_SEALED_AUTHORITY_DOCUMENT_KIND,
            schema_revision=_SEALED_AUTHORITY_SCHEMA_REVISION,
            payload={
                "schemaRevision": _SEALED_AUTHORITY_SCHEMA_REVISION,
                "exactItemInstanceKey": exact_key,
                "staticFactsKey": static_facts.content_key,
                "progressionBindingKey": progression.content_key,
                "effectSupportKey": effect_support.content_key,
                "resolverRevision": resolver,
            },
            key_prefix=_SEALED_AUTHORITY_KEY_PREFIX,
        )
        return CanonicalResult("verified", document, ())
    except CanonicalValueError as error:
        return _blocked_exact_authority(error)


def build_exact_progression_binding(
    exact_item: Any,
    track_authority_input: Any,
) -> dict[str, Any]:
    """Rebuild one progression binding through the production Track Authority."""

    exact = exact_item if isinstance(exact_item, Mapping) else {}
    authority_input = (
        dict(track_authority_input)
        if isinstance(track_authority_input, Mapping) else {}
    )
    if (
        set(authority_input) != _TRACK_AUTHORITY_INPUT_KEYS
        or not _valid_token(authority_input.get("seasonRevision"))
        or not _valid_token(authority_input.get("gearRuleRevision"))
        or not _valid_token(authority_input.get("slot"))
        or type(authority_input.get("hasCraftedSource")) is not bool
        or not _valid_exact(exact)
        or not _EXACT_KEY_PATTERN.fullmatch(
            exact.get("exactItemInstanceKey")
            if isinstance(exact.get("exactItemInstanceKey"), str) else ""
        )
    ):
        return {
            "schemaRevision": "exact-progression-binding-v1",
            "status": "blocked",
            "problemCodes": ["EXACT_PROGRESSION_TRACK_AUTHORITY_INPUT_INVALID"],
        }
    resolved = resolve_exact_instance_progression(
        {
            "seasonRevision": authority_input["seasonRevision"],
            "gearRuleRevision": authority_input["gearRuleRevision"],
        },
        {
            "rowFamily": "exact_instance",
            "status": "verified",
            "itemId": exact.get("itemId"),
            "variantKey": exact.get("exactItemInstanceKey"),
            "itemLevel": exact.get("itemLevel"),
            "bonusIds": exact.get("bonusIds"),
            "slot": authority_input["slot"],
            "hasCraftedSource": authority_input["hasCraftedSource"],
        },
    )
    if resolved.get("status") != "verified":
        return {
            "schemaRevision": "exact-progression-binding-v1",
            "status": "blocked",
            "problemCodes": [
                problem.get("code")
                for problem in resolved.get("problems") or []
                if isinstance(problem, Mapping) and _valid_token(problem.get("code"))
            ] or ["EXACT_PROGRESSION_TRACK_AUTHORITY_BLOCKED"],
        }
    payload = {
        "schemaRevision": "exact-progression-binding-v1",
        "exactItemInstanceKey": exact["exactItemInstanceKey"],
        "gearRuleRevision": authority_input["gearRuleRevision"],
        "trackAuthorityRuleRevision": resolved["ruleRevision"],
        "trackAuthorityRecordKey": resolved["recordKey"],
        "trackAuthorityInput": authority_input,
        "progressionState": resolved["progressionState"],
    }
    return {
        **payload,
        "progressionBindingKey": _hash("exact-progression:sha256:", payload),
    }


def _valid_progression(value: Any, exact: Mapping[str, Any]) -> bool:
    if (
        not isinstance(value, Mapping)
        or set(value) != _PROGRESSION_KEYS
        or value.get("schemaRevision") != "exact-progression-binding-v1"
        or value.get("exactItemInstanceKey") != exact.get("exactItemInstanceKey")
        or not _PROGRESSION_KEY_PATTERN.fullmatch(
            value.get("progressionBindingKey")
            if isinstance(value.get("progressionBindingKey"), str) else ""
        )
    ):
        return False
    rebuilt = build_exact_progression_binding(
        exact, value.get("trackAuthorityInput"),
    )
    return "status" not in rebuilt and _canonical(value) == _canonical(rebuilt)


def _valid_effect_support(exact: Mapping[str, Any], effect: Any) -> bool:
    if not isinstance(effect, Mapping) or set(effect) != {"schemaRevision", "status", "simcRuntimeRevision", "subjects", "supportRecords", "supportRecordKeys", "effectSupportKey"}:
        return False
    if effect.get("schemaRevision") != "simc-item-effect-support-v1" or effect.get("status") != "verified" or not isinstance(effect.get("simcRuntimeRevision"), str) or not effect["simcRuntimeRevision"]:
        return False
    try:
        if any(not validate_effect_record(record, runtime_revision=effect["simcRuntimeRevision"]) for record in effect["supportRecords"]):
            return False
        recomputed = resolve_exact_item_effect_support(exact, runtime_revision=effect["simcRuntimeRevision"], support_records=effect["supportRecords"])
        return effect == recomputed and effect.get("effectSupportKey") == effect_support_key(effect)
    except (KeyError, TypeError, ValueError):
        return False


def build_exact_authority_envelope(*, exact_item: Any, static_facts: Any, serializer_input: Any, progression_binding: Any, effect_support: Any, resolver_revision: str) -> dict[str, Any]:
    """Return a ready envelope only for mutually consistent sealed authority."""

    if not all(isinstance(value, Mapping) for value in (exact_item, static_facts, serializer_input, progression_binding, effect_support)):
        return _blocked("EXACT_AUTHORITY_FIELDS_INVALID")
    try:
        _canonical([exact_item, static_facts, serializer_input, progression_binding, effect_support])
    except (TypeError, ValueError):
        return _blocked("EXACT_AUTHORITY_NON_CANONICAL_VALUE")
    if _contains_forbidden((exact_item, static_facts, serializer_input, progression_binding, effect_support)):
        return _blocked("EXACT_AUTHORITY_PROVENANCE_FORBIDDEN")
    if not _valid_exact(exact_item):
        return _blocked("EXACT_AUTHORITY_EXACT_ITEM_INVALID")
    exact_key = exact_item["exactItemInstanceKey"]
    if not _valid_static_facts(static_facts, exact_key):
        return _blocked("EXACT_AUTHORITY_STATIC_FACTS_MISSING")
    if not isinstance(serializer_input, Mapping) or set(serializer_input).difference(_SERIALIZER_FIELDS) or serializer_input != _expected_serializer(exact_item):
        return _blocked("EXACT_AUTHORITY_SERIALIZER_INPUT_MISMATCH")
    if not _valid_progression(progression_binding, exact_item):
        return _blocked("EXACT_AUTHORITY_PROGRESSION_BINDING_MISSING")
    if not _valid_effect_support(exact_item, effect_support):
        return _blocked("EXACT_AUTHORITY_EFFECT_SUPPORT_NOT_READY")
    if not _valid_token(resolver_revision):
        return _blocked("EXACT_AUTHORITY_REVISION_MISSING")
    payload = {"schemaRevision": "exact-authority-envelope-v1", "exactItem": exact_item, "staticFacts": static_facts, "serializerInput": serializer_input, "progressionBinding": progression_binding, "effectSupport": effect_support, "resolverRevision": resolver_revision}
    return {"schemaRevision": "exact-authority-envelope-v1", "status": "ready", "exactAuthorityKey": _hash("exact-authority:sha256:", payload), "canonicalPayload": json.loads(_canonical(payload))}


__all__ = (
    "build_exact_authority_envelope",
    "build_exact_progression_binding",
    "seal_exact_authority_envelope",
    "seal_exact_progression",
    "seal_exact_static_facts",
)

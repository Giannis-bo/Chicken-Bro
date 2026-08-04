#!/usr/bin/env python3
"""Strict, cross-bound authority envelope for one ready Exact item."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Mapping

try:
    from .gear_exact_item_instance import build_exact_item_identity
    from .simc_item_effect_support import effect_support_key, resolve_exact_item_effect_support, validate_effect_record
except ImportError:
    from gear_exact_item_instance import build_exact_item_identity
    from simc_item_effect_support import effect_support_key, resolve_exact_item_effect_support, validate_effect_record


_EXACT_KEY_PATTERN = re.compile(r"^exact-item-instance:sha256:[0-9a-f]{64}$")
_PROGRESSION_KEY_PATTERN = re.compile(r"^exact-progression:sha256:[0-9a-f]{64}$")
_FORBIDDEN_FRAGMENTS = ("owner", "catalog", "observ", "provenance", "sourceurl", "profileurl")
_EXACT_OUTPUT_KEYS = frozenset({"status", "schemaRevision", "exactItemInstanceKey", "exactVariantSignature", "enhancementSelectionKey", "itemId", "bonusIds", "context", "itemLevel", "redirectedBaseStats", "enhancementSelection", "serializerInput", "problemCodes", "problems"})
_STATIC_KEYS = frozenset({"schemaRevision", "exactItemInstanceKey", "facts"})
_PROGRESSION_KEYS = frozenset({"schemaRevision", "exactItemInstanceKey", "gearRuleRevision", "progressionState", "progressionBindingKey"})
_SERIALIZER_FIELDS = frozenset({"id", "ilevel", "bonus_id", "gem_id", "gem_bonus_id", "gem_ilevel", "enchant_id", "crafted_stats", "embellishment"})
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,256}$")


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


def _valid_progression_state(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    kind = value.get("kind")
    if kind == "upgrade_track":
        return set(value) == {"kind", "trackKey", "rank", "maxRank"} and value.get("trackKey") in {"champion", "hero", "myth"} and type(value.get("rank")) is int and 1 <= value["rank"] <= 6 and value.get("maxRank") == 6
    if kind == "crafted_quality":
        return set(value) == {"kind", "trackKey", "qualityKey"} and value.get("trackKey") == "myth" and value.get("qualityKey") == "radiance_max"
    if kind == "ascendant":
        return set(value) == {"kind", "trackKey", "originKind"} and value.get("trackKey") == "void_upgrade" and value.get("originKind") in {"upgrade_track", "crafted_quality"}
    return False


def _valid_progression(value: Any, exact_key: str) -> bool:
    if not isinstance(value, Mapping) or set(value) != _PROGRESSION_KEYS or value.get("schemaRevision") != "exact-progression-binding-v1" or value.get("exactItemInstanceKey") != exact_key or not _valid_token(value.get("gearRuleRevision")) or not _valid_progression_state(value.get("progressionState")):
        return False
    payload = {key: value[key] for key in _PROGRESSION_KEYS if key != "progressionBindingKey"}
    return _PROGRESSION_KEY_PATTERN.fullmatch(str(value.get("progressionBindingKey") or "")) is not None and value["progressionBindingKey"] == _hash("exact-progression:sha256:", payload)


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
    if not _valid_progression(progression_binding, exact_key):
        return _blocked("EXACT_AUTHORITY_PROGRESSION_BINDING_MISSING")
    if not _valid_effect_support(exact_item, effect_support):
        return _blocked("EXACT_AUTHORITY_EFFECT_SUPPORT_NOT_READY")
    if not _valid_token(resolver_revision):
        return _blocked("EXACT_AUTHORITY_REVISION_MISSING")
    payload = {"schemaRevision": "exact-authority-envelope-v1", "exactItem": exact_item, "staticFacts": static_facts, "serializerInput": serializer_input, "progressionBinding": progression_binding, "effectSupport": effect_support, "resolverRevision": resolver_revision}
    return {"schemaRevision": "exact-authority-envelope-v1", "status": "ready", "exactAuthorityKey": _hash("exact-authority:sha256:", payload), "canonicalPayload": json.loads(_canonical(payload))}


__all__ = ("build_exact_authority_envelope",)

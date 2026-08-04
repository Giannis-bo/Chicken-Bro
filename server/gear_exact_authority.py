#!/usr/bin/env python3
"""Strict, cross-bound authority envelope for one ready Exact item."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

try:
    from .simc_item_effect_support import effect_support_key, resolve_exact_item_effect_support
except ImportError:
    from simc_item_effect_support import effect_support_key, resolve_exact_item_effect_support


_EXACT_KEY_PATTERN = re.compile(r"^exact-item-instance:sha256:[0-9a-f]{64}$")
_PROGRESSION_KEY_PATTERN = re.compile(r"^exact-progression:sha256:[0-9a-f]{64}$")
_FORBIDDEN_FRAGMENTS = ("owner", "catalog", "observ", "provenance", "sourceurl", "profileurl")
_EXACT_OUTPUT_KEYS = frozenset({"status", "schemaRevision", "exactItemInstanceKey", "exactVariantSignature", "enhancementSelectionKey", "itemId", "bonusIds", "context", "itemLevel", "redirectedBaseStats", "enhancementSelection", "serializerInput", "problemCodes", "problems"})
_STATIC_KEYS = frozenset({"schemaRevision", "exactItemInstanceKey", "facts"})
_PROGRESSION_KEYS = frozenset({"schemaRevision", "exactItemInstanceKey", "gearRuleRevision", "progressionState", "progressionBindingKey"})
_SERIALIZER_FIELDS = frozenset({"id", "ilevel", "bonus_id", "gem_id", "gem_bonus_id", "gem_ilevel", "enchant_id", "crafted_stats", "embellishment"})


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
    if not _EXACT_KEY_PATTERN.fullmatch(str(exact.get("exactItemInstanceKey") or "")):
        return False
    if not isinstance(exact.get("itemId"), str) or not isinstance(exact.get("itemLevel"), int) or isinstance(exact.get("itemLevel"), bool):
        return False
    if not isinstance(exact.get("bonusIds"), list) or not isinstance(exact.get("redirectedBaseStats"), list) or not isinstance(exact.get("enhancementSelection"), Mapping):
        return False
    try:
        variant = {"itemId": exact["itemId"], "bonusIds": exact["bonusIds"], "context": exact["context"], "itemLevel": exact["itemLevel"], "redirectedBaseStats": exact["redirectedBaseStats"]}
        instance = {"schemaRevision": "gear-exact-item-instance-v2", **variant, "enhancementSelection": exact["enhancementSelection"]}
        return exact.get("exactVariantSignature") == _hash("exact-variant:sha256:", variant) and exact.get("exactItemInstanceKey") == _hash("exact-item-instance:sha256:", instance)
    except (KeyError, TypeError, ValueError):
        return False


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
    return isinstance(value, Mapping) and set(value) == _STATIC_KEYS and value.get("schemaRevision") == "exact-static-facts-v1" and value.get("exactItemInstanceKey") == exact_key and isinstance(value.get("facts"), Mapping) and bool(value["facts"])


def _valid_progression(value: Any, exact_key: str) -> bool:
    if not isinstance(value, Mapping) or set(value) != _PROGRESSION_KEYS or value.get("schemaRevision") != "exact-progression-binding-v1" or value.get("exactItemInstanceKey") != exact_key or not isinstance(value.get("gearRuleRevision"), str) or not value["gearRuleRevision"] or not isinstance(value.get("progressionState"), Mapping) or not value["progressionState"]:
        return False
    payload = {key: value[key] for key in _PROGRESSION_KEYS if key != "progressionBindingKey"}
    return _PROGRESSION_KEY_PATTERN.fullmatch(str(value.get("progressionBindingKey") or "")) is not None and value["progressionBindingKey"] == _hash("exact-progression:sha256:", payload)


def _valid_effect_support(exact: Mapping[str, Any], effect: Any) -> bool:
    if not isinstance(effect, Mapping) or set(effect) != {"schemaRevision", "status", "simcRuntimeRevision", "subjects", "supportRecords", "supportRecordKeys", "effectSupportKey"}:
        return False
    if effect.get("schemaRevision") != "simc-item-effect-support-v1" or effect.get("status") != "verified" or not isinstance(effect.get("simcRuntimeRevision"), str) or not effect["simcRuntimeRevision"]:
        return False
    try:
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
    if not isinstance(resolver_revision, str) or not resolver_revision.strip():
        return _blocked("EXACT_AUTHORITY_REVISION_MISSING")
    payload = {"schemaRevision": "exact-authority-envelope-v1", "exactItem": exact_item, "staticFacts": static_facts, "serializerInput": serializer_input, "progressionBinding": progression_binding, "effectSupport": effect_support, "resolverRevision": resolver_revision.strip()}
    return {"schemaRevision": "exact-authority-envelope-v1", "status": "ready", "exactAuthorityKey": _hash("exact-authority:sha256:", payload), "canonicalPayload": json.loads(_canonical(payload))}


__all__ = ("build_exact_authority_envelope",)

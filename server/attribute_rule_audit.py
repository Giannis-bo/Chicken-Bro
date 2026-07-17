#!/usr/bin/env python3
"""Pure, fail-closed contracts for winner-driven attribute rule audits.

This module owns no database, HTTP client, Release pointer or SimulationCraft
process.  It converts already sealed winner facts into audit records and only
permits arithmetic after a normalized official profile exactly matches that
sealed input.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

try:
    from .gear_attribute_rules import applicable_attribute_rule
except ImportError:
    from gear_attribute_rules import applicable_attribute_rule


ATTRIBUTE_RULE_AUDIT_SCHEMA_REVISION = "winner-attribute-rule-audit-v1"
_OBSERVED_SOURCE_KEYS = {"raiderio_observed_profile"}
_REQUIRED_SLOTS = {
    "head", "neck", "shoulder", "back", "chest", "wrist", "hands", "waist",
    "legs", "feet", "finger1", "finger2", "trinket1", "trinket2", "main_hand",
}
_OPTIONAL_SLOTS = {"off_hand"}
_PERCENT_VALUE = re.compile(r"^(-?\d+(?:\.\d+)?)%$")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _canonical(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str))


def _hash(prefix: str, value: Any) -> str:
    encoded = json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{prefix}:sha256:{hashlib.sha256(encoded).hexdigest()}"


def _sha256(value: Any) -> str:
    return _hash("", value)[1:]


def _is_sha256(value: Any) -> bool:
    text = _text(value)
    return bool(re.fullmatch(r"sha256:[0-9a-f]{64}", text))


def _canonical_ids(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    normalized = [_text(item) for item in value]
    if any(not item for item in normalized):
        return None
    # Socket order is not semantically important, but occurrence count is: a
    # duplicate gem must never be normalized into a single gem before the
    # audit compares the sealed winner with the official equipment record.
    return sorted(normalized)


def _canonical_equipment(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list) or len(value) not in {len(_REQUIRED_SLOTS), len(_REQUIRED_SLOTS) + 1}:
        return None
    slots: set[str] = set()
    rows: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict):
            return None
        slot = _text(raw.get("slot"))
        item_id = _text(raw.get("itemId"))
        item_level = raw.get("itemLevel")
        if slot not in _REQUIRED_SLOTS | _OPTIONAL_SLOTS or slot in slots or not item_id:
            return None
        if isinstance(item_level, bool) or not isinstance(item_level, int) or item_level < 1:
            return None
        bonus_ids = _canonical_ids(raw.get("bonusIds"))
        gem_ids = _canonical_ids(raw.get("gemIds"))
        enchant_ids = _canonical_ids(raw.get("enchantIds"))
        if bonus_ids is None or gem_ids is None or enchant_ids is None:
            return None
        slots.add(slot)
        rows.append({
            "slot": slot,
            "itemId": item_id,
            "itemLevel": item_level,
            "bonusIds": bonus_ids,
            "gemIds": gem_ids,
            "enchantIds": enchant_ids,
        })
    if not _REQUIRED_SLOTS.issubset(slots):
        return None
    return sorted(rows, key=lambda row: row["slot"])


def _canonical_character(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    class_key = _text(value.get("classKey"))
    spec_key = _text(value.get("specKey"))
    race_key = _text(value.get("raceKey"))
    level = value.get("level")
    if (
        not class_key or class_key != class_key.lower()
        or not spec_key or spec_key != spec_key.lower()
        or not race_key or race_key != race_key.lower()
        or isinstance(level, bool) or not isinstance(level, int) or level < 1 or level > 100
    ):
        return None
    return {"classKey": class_key, "specKey": spec_key, "raceKey": race_key, "level": level}


def _canonical_stable_effects(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    effects = [_text(item) for item in value]
    if any(not item for item in effects):
        return None
    return sorted(set(effects))


def _canonical_static_attributes(value: Any) -> dict[str, int | float] | None:
    if not isinstance(value, dict):
        return None
    attributes: dict[str, int | float] = {}
    for key, raw in value.items():
        normalized_key = _text(key)
        if not normalized_key or normalized_key != normalized_key.lower() or isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return None
        numeric = float(raw)
        if not math.isfinite(numeric):
            return None
        attributes[normalized_key] = int(numeric) if numeric.is_integer() else numeric
    return {key: attributes[key] for key in sorted(attributes)}


def _canonical_sealed_input(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    character = _canonical_character(value.get("character"))
    equipment = _canonical_equipment(value.get("equipment"))
    stable_effects = _canonical_stable_effects(value.get("stableEffects"))
    static_attributes = _canonical_static_attributes(value.get("staticAttributes"))
    resolver_signature = _text(value.get("resolverStaticSignature"))
    if not character or equipment is None or stable_effects is None or static_attributes is None or not _is_sha256(resolver_signature):
        return None
    return {
        "character": character,
        "equipment": equipment,
        "stableEffects": stable_effects,
        "staticAttributes": static_attributes,
        "resolverStaticSignature": resolver_signature,
    }


def _canonical_official_input(value: Any) -> dict[str, Any] | None:
    """Normalize only the profile facts an official endpoint can prove."""
    if not isinstance(value, dict):
        return None
    character = _canonical_character(value.get("character"))
    equipment = _canonical_equipment(value.get("equipment"))
    if not character or equipment is None:
        return None
    result: dict[str, Any] = {"character": character, "equipment": equipment}
    if "stableEffects" in value:
        stable_effects = _canonical_stable_effects(value.get("stableEffects"))
        if stable_effects is None:
            return None
        result["stableEffects"] = stable_effects
    if "staticAttributes" in value:
        static_attributes = _canonical_static_attributes(value.get("staticAttributes"))
        if static_attributes is None:
            return None
        result["staticAttributes"] = static_attributes
    if "resolverStaticSignature" in value:
        resolver_signature = _text(value.get("resolverStaticSignature"))
        if not _is_sha256(resolver_signature):
            return None
        result["resolverStaticSignature"] = resolver_signature
    return result


def canonical_input_signature(audit_input: dict[str, Any]) -> str:
    """Hash a complete already-sealed attribute input without source identity."""
    normalized = _canonical_sealed_input(audit_input)
    if normalized is None:
        raise ValueError("complete canonical attribute audit input is required")
    return _sha256(normalized)


def audit_key(intent: dict[str, Any]) -> str:
    """Return an immutable deduplication key for one winner/rule/input context."""
    if not isinstance(intent, dict):
        raise ValueError("attribute audit intent must be an object")
    required = (
        "candidateCommunityReleaseId", "candidateGearReleaseId", "manifestRevision",
        "templateId", "profileHash", "gearHash", "canonicalInputSignature", "attributeRuleRevision",
    )
    payload = {key: _text(intent.get(key)) for key in required}
    if any(not value for value in payload.values()) or not _is_sha256(payload["canonicalInputSignature"]):
        raise ValueError("attribute audit identity is incomplete")
    return _hash("attribute-audit", payload)


def _source_identity(row: dict[str, Any]) -> dict[str, str] | None:
    evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    refs = evidence.get("sourceRefs") if isinstance(evidence.get("sourceRefs"), list) else []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        identity = {
            "region": _text(ref.get("region")).lower(),
            "realmSlug": _text(ref.get("realmSlug")).lower(),
            "characterName": _text(ref.get("characterName")),
            "locale": _text(ref.get("locale")) or "en_US",
        }
        if identity["region"] and identity["realmSlug"] and identity["characterName"]:
            return identity
    return None


def _sealed_input(row: dict[str, Any]) -> dict[str, Any] | None:
    evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    raw = evidence.get("attributeAudit") if isinstance(evidence.get("attributeAudit"), dict) else {}
    character = _canonical_character(raw.get("characterContext"))
    input_payload = {
        "character": character,
        "equipment": raw.get("canonicalEquipment"),
        "stableEffects": raw.get("stableEffects"),
        "staticAttributes": raw.get("staticAttributes"),
        "resolverStaticSignature": raw.get("resolverStaticSignature"),
    }
    return _canonical_sealed_input(input_payload)


def _winner_changed(row: dict[str, Any], active_by_context: dict[tuple[str, str], dict[str, Any]]) -> bool:
    active = active_by_context.get((_text(row.get("classKey")), _text(row.get("specKey"))))
    if not active:
        return True
    return (
        _text(active.get("profileHash")) != _text(row.get("profileHash"))
        or _text(active.get("gearHash")) != _text(row.get("gearHash"))
    )


def _terminal_intent(
    row: dict[str, Any],
    context: dict[str, Any],
    *,
    status: str,
    code: str,
    rulebook: Any,
) -> dict[str, Any]:
    class_key = _text(row.get("classKey")) or "unknown"
    spec_key = _text(row.get("specKey")) or "unknown"
    profile_hash = _text(row.get("profileHash")) or "missing-profile-hash"
    gear_hash = _text(row.get("gearHash")) or "missing-gear-hash"
    attribute_rule_revision = _text((rulebook or {}).get("attributeRuleRevision")) or "unavailable"
    intent = {
        "schemaRevision": ATTRIBUTE_RULE_AUDIT_SCHEMA_REVISION,
        "status": status,
        "code": code,
        "externalFetchAllowed": False,
        "templateId": _text(row.get("templateId") or row.get("candidateId")),
        "classKey": class_key,
        "specKey": spec_key,
        "profileHash": profile_hash,
        "gearHash": gear_hash,
        "candidateCommunityReleaseId": _text(context.get("candidateCommunityReleaseId")),
        "candidateGearReleaseId": _text(context.get("candidateGearReleaseId")),
        "manifestRevision": _text(context.get("manifestRevision")),
        "attributeRuleRevision": attribute_rule_revision,
        "contextKey": f"{class_key}:{spec_key}:unavailable",
        "sourceIdentity": {},
        "sealedInput": {},
        "rule": {},
    }
    intent["canonicalInputSignature"] = _sha256({
        "status": status,
        "code": code,
        "templateId": intent["templateId"],
        "profileHash": profile_hash,
        "gearHash": gear_hash,
        "candidateCommunityReleaseId": intent["candidateCommunityReleaseId"],
        "candidateGearReleaseId": intent["candidateGearReleaseId"],
        "manifestRevision": intent["manifestRevision"],
        "attributeRuleRevision": attribute_rule_revision,
    })
    intent["auditKey"] = audit_key(intent)
    return intent


def build_winner_audit_intents(
    *,
    active_winners: Any,
    candidate_rows: Any,
    candidate_context: Any,
    rulebook: Any,
) -> list[dict[str, Any]]:
    """Return bounded deterministic intents for new observed winners only.

    An evidence/rule failure remains visible as a terminal no-fetch record. A
    winner that has not materially changed is omitted because it has already
    had the same audit opportunity.
    """
    context = candidate_context if isinstance(candidate_context, dict) else {}
    required_context = ("candidateCommunityReleaseId", "candidateGearReleaseId", "manifestRevision")
    if any(not _text(context.get(key)) for key in required_context):
        return []
    active_by_context = {
        (_text(row.get("classKey")), _text(row.get("specKey"))): row
        for row in active_winners or []
        if isinstance(row, dict) and _text(row.get("role")) == "winner"
    }
    rows = sorted(
        (row for row in candidate_rows or [] if isinstance(row, dict) and _text(row.get("role")) == "winner"),
        key=lambda row: (_text(row.get("classKey")), _text(row.get("specKey")), _text(row.get("templateId") or row.get("candidateId"))),
    )
    intents: list[dict[str, Any]] = []
    seen_contexts: set[tuple[str, str]] = set()
    for row in rows:
        pair = (_text(row.get("classKey")), _text(row.get("specKey")))
        if not pair[0] or not pair[1] or pair in seen_contexts or not _winner_changed(row, active_by_context):
            continue
        seen_contexts.add(pair)
        if _text(row.get("sourceKey")) not in _OBSERVED_SOURCE_KEYS:
            intents.append(_terminal_intent(row, context, status="not_applicable", code="ATTRIBUTE_AUDIT_SOURCE_NOT_OBSERVED", rulebook=rulebook))
            continue
        sealed_input = _sealed_input(row)
        source_identity = _source_identity(row)
        if sealed_input is None or source_identity is None or not _is_sha256(row.get("profileHash")) or not _is_sha256(row.get("gearHash")):
            intents.append(_terminal_intent(row, context, status="blocked_missing_evidence", code="ATTRIBUTE_AUDIT_INPUT_INCOMPLETE", rulebook=rulebook))
            continue
        character = sealed_input["character"]
        rule, _issues = applicable_attribute_rule(
            rulebook if isinstance(rulebook, dict) else {},
            class_key=character["classKey"],
            spec_key=character["specKey"],
            level=character["level"],
            race_key=character["raceKey"],
        )
        if not isinstance(rule, dict) or _text(rule.get("status")) != "verified":
            intents.append(_terminal_intent(row, context, status="not_applicable", code="ATTRIBUTE_AUDIT_RULE_UNAVAILABLE", rulebook=rulebook))
            continue
        signature = canonical_input_signature(sealed_input)
        intent = {
            "schemaRevision": ATTRIBUTE_RULE_AUDIT_SCHEMA_REVISION,
            "status": "pending",
            "code": "",
            "externalFetchAllowed": True,
            "templateId": _text(row.get("templateId") or row.get("candidateId")),
            "classKey": character["classKey"],
            "specKey": character["specKey"],
            "profileHash": _text(row.get("profileHash")),
            "gearHash": _text(row.get("gearHash")),
            "candidateCommunityReleaseId": _text(context.get("candidateCommunityReleaseId")),
            "candidateGearReleaseId": _text(context.get("candidateGearReleaseId")),
            "manifestRevision": _text(context.get("manifestRevision")),
            "attributeRuleRevision": _text(rule.get("attributeRuleRevision")),
            "contextKey": _text(rule.get("contextKey")),
            "canonicalInputSignature": signature,
            "sourceIdentity": source_identity,
            "sealedInput": sealed_input,
            "rule": _canonical(rule),
        }
        intent["auditKey"] = audit_key(intent)
        intents.append(intent)
    return intents


def match_official_profile(sealed_input: Any, official_profile: Any) -> dict[str, Any]:
    """Require equality of all sealed non-combat inputs before arithmetic."""
    expected = _canonical_sealed_input(sealed_input)
    actual = _canonical_official_input(official_profile)
    if expected is None or actual is None:
        return {
            "status": "inconclusive_input_mismatch",
            "mismatches": [{"field": "input", "expected": "complete", "actual": "incomplete"}],
        }
    mismatches: list[dict[str, Any]] = []
    for field in ("character", "stableEffects", "staticAttributes", "resolverStaticSignature"):
        if field not in actual:
            continue
        if expected[field] != actual[field]:
            mismatches.append({"field": field, "expected": expected[field], "actual": actual[field]})
    actual_by_slot = {row["slot"]: row for row in actual["equipment"]}
    for row in expected["equipment"]:
        actual_row = actual_by_slot.get(row["slot"])
        if actual_row is None:
            mismatches.append({"field": "slot", "slot": row["slot"], "expected": "present", "actual": "missing"})
            continue
        for field in ("itemId", "itemLevel", "bonusIds", "gemIds", "enchantIds"):
            if row[field] != actual_row[field]:
                mismatches.append({"field": field, "slot": row["slot"], "expected": row[field], "actual": actual_row[field]})
    expected_slots = {row["slot"] for row in expected["equipment"]}
    for row in actual["equipment"]:
        if row["slot"] not in expected_slots:
            mismatches.append({"field": "slot", "slot": row["slot"], "expected": "absent", "actual": "present"})
    return {
        "status": "matched" if not mismatches else "inconclusive_input_mismatch",
        "mismatches": mismatches[:64],
    }


def _display_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    match = _PERCENT_VALUE.fullmatch(_text(value))
    if not match:
        return None
    return float(match.group(1))


def _raw_value(row: Any) -> int | float | None:
    if not isinstance(row, dict):
        return None
    value = row.get("rawValue")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return int(numeric) if numeric.is_integer() else numeric if math.isfinite(numeric) else None


def _secondary_by_key(value: Any) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("key")): row
        for row in value or []
        if isinstance(row, dict) and _text(row.get("key"))
    }


def compare_attribute_panel(*, rule: Any, expected: Any, observed: Any) -> dict[str, Any]:
    """Compare a matched official non-combat panel with rule-declared precision."""
    rule_object = rule if isinstance(rule, dict) else {}
    expected_panel = expected if isinstance(expected, dict) else {}
    observed_panel = observed if isinstance(observed, dict) else {}
    fields: list[dict[str, Any]] = []
    for key in ("primary", "stamina"):
        expected_row = expected_panel.get(key)
        observed_row = observed_panel.get(key)
        expected_raw = _raw_value(expected_row)
        observed_raw = _raw_value(observed_row)
        matched = expected_raw is not None and expected_raw == observed_raw
        fields.append({"key": key, "matched": matched, "expected": {"rawValue": expected_raw}, "observed": {"rawValue": observed_raw}, "precision": 0})
    expected_resources = expected_panel.get("resources") if isinstance(expected_panel.get("resources"), dict) else {}
    observed_resources = observed_panel.get("resources") if isinstance(observed_panel.get("resources"), dict) else {}
    for key in sorted(set(expected_resources) | set(observed_resources)):
        expected_raw = _raw_value(expected_resources.get(key))
        observed_raw = _raw_value(observed_resources.get(key))
        fields.append({"key": key, "matched": expected_raw is not None and expected_raw == observed_raw, "expected": {"rawValue": expected_raw}, "observed": {"rawValue": observed_raw}, "precision": 0})
    precision_by_key = {
        _text(item.get("outputKey")): item.get("precision")
        for item in rule_object.get("secondaryRules") or []
        if isinstance(item, dict) and isinstance(item.get("precision"), int)
    }
    expected_secondary = _secondary_by_key(expected_panel.get("secondary"))
    observed_secondary = _secondary_by_key(observed_panel.get("secondary"))
    for key in sorted(set(expected_secondary) | set(observed_secondary)):
        expected_row = expected_secondary.get(key, {})
        observed_row = observed_secondary.get(key, {})
        precision = precision_by_key.get(key)
        expected_raw = _raw_value(expected_row)
        observed_raw = _raw_value(observed_row)
        expected_display = _text(expected_row.get("convertedValue"))
        observed_display = _text(observed_row.get("convertedValue"))
        expected_unit = _text(expected_row.get("displayUnit"))
        observed_unit = _text(observed_row.get("displayUnit"))
        expected_number = _display_number(expected_display)
        observed_number = _display_number(observed_display)
        tolerance = (0.5 * (10 ** (-precision))) + 1e-12 if isinstance(precision, int) else -1
        matched = (
            isinstance(precision, int)
            and expected_raw is not None
            and expected_raw == observed_raw
            and expected_unit == observed_unit
            and expected_number is not None
            and observed_number is not None
            and abs(expected_number - observed_number) <= tolerance
        )
        fields.append({
            "key": key,
            "matched": matched,
            "precision": precision if isinstance(precision, int) else -1,
            "expected": {"rawRating": expected_raw, "displayValue": expected_display, "displayUnit": expected_unit},
            "observed": {"rawRating": observed_raw, "displayValue": observed_display, "displayUnit": observed_unit},
        })
    return {
        "status": "pass" if fields and all(field["matched"] for field in fields) else "confirmed_mismatch",
        "fields": fields,
    }


__all__ = [
    "ATTRIBUTE_RULE_AUDIT_SCHEMA_REVISION",
    "audit_key",
    "build_winner_audit_intents",
    "canonical_input_signature",
    "compare_attribute_panel",
    "match_official_profile",
]

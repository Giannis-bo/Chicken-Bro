#!/usr/bin/env python3
"""Versioned, fail-closed contracts for the real-time gear attribute engine.

This module deliberately contains no game values, persistence access, Resolver
call, or SimulationCraft integration.  It only validates the server-owned
rulebook and exposes verified rule contexts to downstream read paths.
"""

from __future__ import annotations

import copy
from typing import Any


ATTRIBUTE_RULEBOOK_SCHEMA_REVISION = "gear-attribute-rulebook-v1"
ATTRIBUTE_CHARACTER_CONTEXT_REVISION = "gear-attribute-character-v1"
ATTRIBUTE_CALCULATOR_CONTEXT_REVISION = "gear-attribute-calculator-context-v1"
ATTRIBUTE_ARMORY_SAMPLE_SCHEMA_REVISION = "gear-attribute-armory-v1"

_MAX_IDENTIFIER_LENGTH = 256
_RULEBOOK_KEYS = {"schemaRevision", "attributeRuleRevision", "contexts"}
_CONTEXT_REQUIRED_KEYS = {
    "contextKey",
    "classKey",
    "specKey",
    "level",
    "raceKey",
    "status",
    "primaryKey",
    "baseAttributes",
    "stableModifiers",
    "resources",
    "secondaryRules",
    "sourceRefs",
    "goldenSampleIds",
}
_CONTEXT_OPTIONAL_KEYS = {"implementationNotes"}
_SECONDARY_RULE_KEYS = {
    "inputKey",
    "outputKey",
    "label",
    "basePercent",
    "ratingPerPercent",
    "precision",
    "sourceRefs",
    "displayUnit",
}
_PUBLIC_STATUSES = {"verified"}
_ALLOWED_STATUSES = _PUBLIC_STATUSES | {"fixture_only"}
_ALLOWED_DISPLAY_UNITS = {"percent", "effect"}
_ARMORY_SAMPLE_STATUSES = {"candidate", "verified"}
_ARMORY_SAMPLE_TOP_LEVEL_KEYS = {"schemaRevision", "samples"}
_ARMORY_SAMPLE_REQUIRED_KEYS = {
    "id",
    "status",
    "source",
    "identity",
    "equipment",
    "observedPanel",
    "missingEvidence",
}
_ARMORY_SAMPLE_OPTIONAL_KEYS = {"evidence"}
_ARMORY_SOURCE_REQUIRED_KEYS = {"url", "capturedAt", "captureStatus"}
_ARMORY_IDENTITY_REQUIRED_KEYS = {
    "region",
    "realm",
    "name",
    "classKey",
    "specKey",
    "raceKey",
    "level",
}
_ARMORY_REQUIRED_SLOTS = {
    "head",
    "neck",
    "shoulder",
    "back",
    "chest",
    "wrist",
    "hands",
    "waist",
    "legs",
    "feet",
    "finger1",
    "finger2",
    "trinket1",
    "trinket2",
    "main_hand",
    "off_hand",
}
_ARMORY_EVIDENCE_KEYS = {"officialProfileApi", "officialProfileSnapshot", "officialProfilePanel"}
_ARMORY_OFFICIAL_PROFILE_API_KEYS = {"url", "capturedAt", "credentialHandling"}
_ARMORY_OFFICIAL_PROFILE_SNAPSHOT_REQUIRED_KEYS = {"capturedAt", "canonicalEquipmentCount", "instances"}
_ARMORY_OFFICIAL_PROFILE_SNAPSHOT_OPTIONAL_KEYS = {"excludedCosmeticSlots"}
_ARMORY_OFFICIAL_PROFILE_PANEL_KEYS = {"capturedAt", "values"}


def _issue(kind: str, code: str, path: str, message: str) -> dict[str, str]:
    return {"kind": kind, "code": code, "path": path, "message": message}


def _bounded_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > _MAX_IDENTIFIER_LENGTH:
        return None
    return normalized


def _canonical_key(value: Any) -> str | None:
    normalized = _bounded_string(value)
    if normalized is None or normalized != normalized.lower():
        return None
    return normalized


def _string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    normalized = [_bounded_string(item) for item in value]
    if any(item is None for item in normalized):
        return None
    return normalized


def _is_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float))


def _has_complete_verified_equipment(equipment: Any) -> bool:
    if not isinstance(equipment, list) or len(equipment) != len(_ARMORY_REQUIRED_SLOTS):
        return False
    slots: set[str] = set()
    for item in equipment:
        if not isinstance(item, dict):
            return False
        slot = item.get("slot")
        if slot not in _ARMORY_REQUIRED_SLOTS or slot in slots:
            return False
        slots.add(slot)
        if item.get("status") == "empty":
            if slot != "off_hand" or _bounded_string(item.get("reason")) is None:
                return False
            continue
        if _bounded_string(item.get("itemId")) is None or _bounded_string(item.get("variantKey")) is None:
            return False
        if isinstance(item.get("itemLevel"), bool) or not isinstance(item.get("itemLevel"), int) or item["itemLevel"] < 1:
            return False
        if not isinstance(item.get("stats"), dict):
            return False
    return slots == _ARMORY_REQUIRED_SLOTS


def _validate_armory_evidence(evidence: Any, path: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not isinstance(evidence, dict):
        return [_issue("INVALID_ARMORY_SAMPLE", "INVALID_EVIDENCE", path, "evidence must be an object")]
    for key in sorted(set(evidence) - _ARMORY_EVIDENCE_KEYS):
        issues.append(_issue("INVALID_ARMORY_SAMPLE", "UNKNOWN_FIELD", f"{path}.{key}", "unknown evidence field"))

    api = evidence.get("officialProfileApi")
    if api is not None:
        api_path = f"{path}.officialProfileApi"
        if not isinstance(api, dict):
            issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_OFFICIAL_PROFILE_API", api_path, "officialProfileApi must be an object"))
        else:
            for key in sorted(set(api) - _ARMORY_OFFICIAL_PROFILE_API_KEYS):
                issues.append(_issue("INVALID_ARMORY_SAMPLE", "UNKNOWN_FIELD", f"{api_path}.{key}", "unknown official profile API field"))
            for key in sorted(_ARMORY_OFFICIAL_PROFILE_API_KEYS - set(api)):
                issues.append(_issue("INVALID_ARMORY_SAMPLE", "MISSING_REQUIRED_FIELD", f"{api_path}.{key}", "official profile API field is required"))
            if _ARMORY_OFFICIAL_PROFILE_API_KEYS.issubset(api):
                if not isinstance(api["url"], str) or not api["url"].startswith("https://"):
                    issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_SOURCE_URL", f"{api_path}.url", "official profile API URL must use https"))
                for key in ("capturedAt", "credentialHandling"):
                    if _bounded_string(api[key]) is None:
                        issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_EVIDENCE", f"{api_path}.{key}", "official profile API evidence text must be bounded"))

    snapshot = evidence.get("officialProfileSnapshot")
    if snapshot is not None:
        snapshot_path = f"{path}.officialProfileSnapshot"
        if not isinstance(snapshot, dict):
            issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_OFFICIAL_PROFILE_SNAPSHOT", snapshot_path, "officialProfileSnapshot must be an object"))
        else:
            allowed_snapshot_keys = _ARMORY_OFFICIAL_PROFILE_SNAPSHOT_REQUIRED_KEYS | _ARMORY_OFFICIAL_PROFILE_SNAPSHOT_OPTIONAL_KEYS
            for key in sorted(set(snapshot) - allowed_snapshot_keys):
                issues.append(_issue("INVALID_ARMORY_SAMPLE", "UNKNOWN_FIELD", f"{snapshot_path}.{key}", "unknown official profile snapshot field"))
            for key in sorted(_ARMORY_OFFICIAL_PROFILE_SNAPSHOT_REQUIRED_KEYS - set(snapshot)):
                issues.append(_issue("INVALID_ARMORY_SAMPLE", "MISSING_REQUIRED_FIELD", f"{snapshot_path}.{key}", "official profile snapshot field is required"))
            if _ARMORY_OFFICIAL_PROFILE_SNAPSHOT_REQUIRED_KEYS.issubset(snapshot):
                if _bounded_string(snapshot["capturedAt"]) is None:
                    issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_CAPTURE_TIME", f"{snapshot_path}.capturedAt", "official profile snapshot capture time must be bounded"))
                count = snapshot["canonicalEquipmentCount"]
                if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= len(_ARMORY_REQUIRED_SLOTS):
                    issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_EQUIPMENT", f"{snapshot_path}.canonicalEquipmentCount", "canonical equipment count must be an integer from 0 to 16"))
                if not isinstance(snapshot["instances"], list):
                    issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_EQUIPMENT", f"{snapshot_path}.instances", "official profile instances must be a list"))
                if "excludedCosmeticSlots" in snapshot and not isinstance(snapshot["excludedCosmeticSlots"], list):
                    issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_EQUIPMENT", f"{snapshot_path}.excludedCosmeticSlots", "excluded cosmetic slots must be a list"))

    panel = evidence.get("officialProfilePanel")
    if panel is not None:
        panel_path = f"{path}.officialProfilePanel"
        if not isinstance(panel, dict):
            issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_OFFICIAL_PROFILE_PANEL", panel_path, "officialProfilePanel must be an object"))
        else:
            for key in sorted(set(panel) - _ARMORY_OFFICIAL_PROFILE_PANEL_KEYS):
                issues.append(_issue("INVALID_ARMORY_SAMPLE", "UNKNOWN_FIELD", f"{panel_path}.{key}", "unknown official profile panel field"))
            for key in sorted(_ARMORY_OFFICIAL_PROFILE_PANEL_KEYS - set(panel)):
                issues.append(_issue("INVALID_ARMORY_SAMPLE", "MISSING_REQUIRED_FIELD", f"{panel_path}.{key}", "official profile panel field is required"))
            if _ARMORY_OFFICIAL_PROFILE_PANEL_KEYS.issubset(panel):
                if _bounded_string(panel["capturedAt"]) is None:
                    issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_CAPTURE_TIME", f"{panel_path}.capturedAt", "official profile panel capture time must be bounded"))
                if not isinstance(panel["values"], dict) or not panel["values"]:
                    issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_OBSERVED_PANEL", f"{panel_path}.values", "official profile panel values must be a non-empty object"))
    return issues


def _validate_armory_golden_sample(sample: Any, index: int) -> list[dict[str, str]]:
    path = f"armorySamples.samples[{index}]"
    issues: list[dict[str, str]] = []
    if not isinstance(sample, dict):
        return [_issue("INVALID_ARMORY_SAMPLE", "INVALID_SAMPLE", path, "sample must be an object")]
    sample_keys = _ARMORY_SAMPLE_REQUIRED_KEYS | _ARMORY_SAMPLE_OPTIONAL_KEYS
    for key in sorted(set(sample) - sample_keys):
        issues.append(_issue("INVALID_ARMORY_SAMPLE", "UNKNOWN_FIELD", f"{path}.{key}", "unknown sample field"))
    missing_sample_keys = _ARMORY_SAMPLE_REQUIRED_KEYS - set(sample)
    for key in sorted(missing_sample_keys):
        issues.append(_issue("INVALID_ARMORY_SAMPLE", "MISSING_REQUIRED_FIELD", f"{path}.{key}", "required sample field is missing"))
    if missing_sample_keys:
        return issues

    if _bounded_string(sample["id"]) is None:
        issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_SAMPLE_ID", f"{path}.id", "sample id must be a bounded string"))
    if sample["status"] not in _ARMORY_SAMPLE_STATUSES:
        issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_SAMPLE_STATUS", f"{path}.status", "sample status must be candidate or verified"))

    source = sample["source"]
    if not isinstance(source, dict):
        issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_SOURCE", f"{path}.source", "source must be an object"))
    else:
        for key in sorted(set(source) - _ARMORY_SOURCE_REQUIRED_KEYS):
            issues.append(_issue("INVALID_ARMORY_SAMPLE", "UNKNOWN_FIELD", f"{path}.source.{key}", "unknown source field"))
        missing_source_keys = _ARMORY_SOURCE_REQUIRED_KEYS - set(source)
        for key in sorted(missing_source_keys):
            issues.append(_issue("INVALID_ARMORY_SAMPLE", "MISSING_REQUIRED_FIELD", f"{path}.source.{key}", "required source field is missing"))
        if not missing_source_keys:
            if not isinstance(source["url"], str) or not source["url"].startswith("https://"):
                issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_SOURCE_URL", f"{path}.source.url", "source url must use https"))
            if _bounded_string(source["capturedAt"]) is None:
                issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_CAPTURE_TIME", f"{path}.source.capturedAt", "capturedAt must be a bounded string"))
            if source["captureStatus"] not in {"captured", "not_found"}:
                issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_CAPTURE_STATUS", f"{path}.source.captureStatus", "captureStatus must be captured or not_found"))
            elif sample["status"] == "verified" and source["captureStatus"] != "captured":
                issues.append(_issue("INVALID_ARMORY_SAMPLE", "VERIFIED_SAMPLE_NOT_CAPTURED", f"{path}.source.captureStatus", "verified samples require a successful official capture"))

    identity = sample["identity"]
    if not isinstance(identity, dict):
        issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_IDENTITY", f"{path}.identity", "identity must be an object"))
    else:
        for key in sorted(set(identity) - _ARMORY_IDENTITY_REQUIRED_KEYS):
            issues.append(_issue("INVALID_ARMORY_SAMPLE", "UNKNOWN_FIELD", f"{path}.identity.{key}", "unknown identity field"))
        missing_identity_keys = _ARMORY_IDENTITY_REQUIRED_KEYS - set(identity)
        for key in sorted(missing_identity_keys):
            issues.append(_issue("INVALID_ARMORY_SAMPLE", "MISSING_REQUIRED_FIELD", f"{path}.identity.{key}", "required identity field is missing"))
        if not missing_identity_keys:
            for key in ("region", "realm", "name"):
                if _bounded_string(identity[key]) is None:
                    issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_IDENTITY", f"{path}.identity.{key}", "identity text must be bounded"))
            for key in ("classKey", "specKey", "raceKey"):
                if _canonical_key(identity[key]) is None:
                    issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_IDENTITY", f"{path}.identity.{key}", "identity keys must be lower-case identifiers"))
            if isinstance(identity["level"], bool) or not isinstance(identity["level"], int) or not 1 <= identity["level"] <= 100:
                issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_LEVEL", f"{path}.identity.level", "level must be an integer from 1 to 100"))

    if "evidence" in sample:
        issues.extend(_validate_armory_evidence(sample["evidence"], f"{path}.evidence"))

    if not isinstance(sample["equipment"], list):
        issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_EQUIPMENT", f"{path}.equipment", "equipment must be a list"))
    elif sample["status"] == "verified" and not _has_complete_verified_equipment(sample["equipment"]):
        issues.append(_issue("INVALID_ARMORY_SAMPLE", "VERIFIED_SAMPLE_INCOMPLETE_EQUIPMENT", f"{path}.equipment", "verified samples require complete 16-slot item identities and variants"))
    if not isinstance(sample["observedPanel"], dict):
        issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_OBSERVED_PANEL", f"{path}.observedPanel", "observedPanel must be an object"))
    elif any(_canonical_key(key) is None or not _is_number(value) for key, value in sample["observedPanel"].items()):
        issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_OBSERVED_PANEL", f"{path}.observedPanel", "observed panel requires lower-case numeric fields"))
    missing_evidence = _string_list(sample["missingEvidence"])
    if missing_evidence is None:
        issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_MISSING_EVIDENCE", f"{path}.missingEvidence", "missingEvidence must be a list of bounded strings"))
    elif sample["status"] == "candidate" and not missing_evidence:
        issues.append(_issue("INVALID_ARMORY_SAMPLE", "CANDIDATE_MISSING_GAP", f"{path}.missingEvidence", "candidate samples must state their evidence gap"))
    elif sample["status"] == "verified" and missing_evidence:
        issues.append(_issue("INVALID_ARMORY_SAMPLE", "VERIFIED_SAMPLE_HAS_GAP", f"{path}.missingEvidence", "verified samples cannot retain evidence gaps"))
    return issues


def validate_armory_golden_samples(raw: object) -> tuple[dict | None, list[dict]]:
    """Validate captured Armory samples without treating candidates as rule evidence."""
    if not isinstance(raw, dict):
        return None, [_issue("INVALID_ARMORY_SAMPLE", "INVALID_REGISTRY", "armorySamples", "samples must be an object")]
    issues: list[dict[str, str]] = []
    for key in sorted(set(raw) - _ARMORY_SAMPLE_TOP_LEVEL_KEYS):
        issues.append(_issue("INVALID_ARMORY_SAMPLE", "UNKNOWN_FIELD", f"armorySamples.{key}", "unknown registry field"))
    for key in sorted(_ARMORY_SAMPLE_TOP_LEVEL_KEYS - set(raw)):
        issues.append(_issue("INVALID_ARMORY_SAMPLE", "MISSING_REQUIRED_FIELD", f"armorySamples.{key}", "required registry field is missing"))
    if raw.get("schemaRevision") != ATTRIBUTE_ARMORY_SAMPLE_SCHEMA_REVISION:
        issues.append(_issue("INVALID_ARMORY_SAMPLE", "UNSUPPORTED_SCHEMA_REVISION", "armorySamples.schemaRevision", "unsupported Armory sample revision"))
    samples = raw.get("samples")
    if not isinstance(samples, list) or not samples:
        issues.append(_issue("INVALID_ARMORY_SAMPLE", "INVALID_SAMPLES", "armorySamples.samples", "samples must be a non-empty list"))
    else:
        sample_ids: set[str] = set()
        for index, sample in enumerate(samples):
            issues.extend(_validate_armory_golden_sample(sample, index))
            if isinstance(sample, dict) and isinstance(sample.get("id"), str):
                sample_id = sample["id"]
                if sample_id in sample_ids:
                    issues.append(_issue("INVALID_ARMORY_SAMPLE", "DUPLICATE_SAMPLE_ID", f"armorySamples.samples[{index}].id", "sample id must be unique"))
                sample_ids.add(sample_id)
    if issues:
        return None, issues
    return copy.deepcopy(raw), []


def _validate_rulebook_context(context: Any, index: int) -> list[dict[str, str]]:
    path = f"rulebook.contexts[{index}]"
    issues: list[dict[str, str]] = []
    if not isinstance(context, dict):
        return [_issue("INVALID_RULEBOOK", "INVALID_CONTEXT", path, "context must be an object")]

    unknown_keys = set(context) - _CONTEXT_REQUIRED_KEYS - _CONTEXT_OPTIONAL_KEYS
    for key in sorted(unknown_keys):
        issues.append(_issue("INVALID_RULEBOOK", "UNKNOWN_FIELD", f"{path}.{key}", "unknown context field"))
    for key in sorted(_CONTEXT_REQUIRED_KEYS - set(context)):
        issues.append(_issue("INVALID_RULEBOOK", "MISSING_REQUIRED_FIELD", f"{path}.{key}", "required context field is missing"))
    if issues:
        return issues

    class_key = _canonical_key(context["classKey"])
    spec_key = _canonical_key(context["specKey"])
    race_key = _canonical_key(context["raceKey"])
    primary_key = _canonical_key(context["primaryKey"])
    for key, value in (("classKey", class_key), ("specKey", spec_key), ("raceKey", race_key), ("primaryKey", primary_key)):
        if value is None:
            issues.append(_issue("INVALID_RULEBOOK", "INVALID_IDENTIFIER", f"{path}.{key}", "expected a bounded lower-case identifier"))

    level = context["level"]
    if isinstance(level, bool) or not isinstance(level, int) or level < 1 or level > 100:
        issues.append(_issue("INVALID_RULEBOOK", "INVALID_LEVEL", f"{path}.level", "level must be an integer from 1 to 100"))
    elif class_key and spec_key and race_key:
        expected_context_key = f"{class_key}:{spec_key}:{level}:{race_key}"
        if context["contextKey"] != expected_context_key:
            issues.append(_issue("INVALID_RULEBOOK", "INVALID_CONTEXT_KEY", f"{path}.contextKey", "contextKey must match class:spec:level:race"))

    if context["status"] not in _ALLOWED_STATUSES:
        issues.append(_issue("INVALID_RULEBOOK", "INVALID_RULE_STATUS", f"{path}.status", "status must be verified or fixture_only"))

    base_attributes = context["baseAttributes"]
    if not isinstance(base_attributes, dict) or not base_attributes:
        issues.append(_issue("INVALID_RULEBOOK", "INVALID_BASE_ATTRIBUTES", f"{path}.baseAttributes", "baseAttributes must be a non-empty object"))
    else:
        for attribute_key, value in base_attributes.items():
            if _canonical_key(attribute_key) is None or not _is_number(value):
                issues.append(_issue("INVALID_RULEBOOK", "INVALID_BASE_ATTRIBUTE", f"{path}.baseAttributes.{attribute_key}", "base attributes require lower-case keys and numeric values"))

    if not isinstance(context["stableModifiers"], list):
        issues.append(_issue("INVALID_RULEBOOK", "INVALID_STABLE_MODIFIERS", f"{path}.stableModifiers", "stableModifiers must be an ordered list"))
    if not isinstance(context["resources"], dict):
        issues.append(_issue("INVALID_RULEBOOK", "INVALID_RESOURCES", f"{path}.resources", "resources must be an object"))

    source_refs = _string_list(context["sourceRefs"])
    if not source_refs:
        issues.append(_issue("INVALID_RULEBOOK", "MISSING_SOURCE_REFS", f"{path}.sourceRefs", "every rule context requires source references"))
    golden_sample_ids = _string_list(context["goldenSampleIds"])
    if golden_sample_ids is None:
        issues.append(_issue("INVALID_RULEBOOK", "INVALID_GOLDEN_SAMPLE_IDS", f"{path}.goldenSampleIds", "goldenSampleIds must be a list of bounded strings"))
    elif context["status"] == "verified" and not golden_sample_ids:
        issues.append(_issue("INVALID_RULEBOOK", "MISSING_GOLDEN_SAMPLE", f"{path}.goldenSampleIds", "verified contexts require a golden sample id"))

    secondary_rules = context["secondaryRules"]
    if not isinstance(secondary_rules, list):
        issues.append(_issue("INVALID_RULEBOOK", "INVALID_SECONDARY_RULES", f"{path}.secondaryRules", "secondaryRules must be a list"))
        return issues

    output_keys: set[str] = set()
    for rule_index, rule in enumerate(secondary_rules):
        rule_path = f"{path}.secondaryRules[{rule_index}]"
        if not isinstance(rule, dict):
            issues.append(_issue("INVALID_RULEBOOK", "INVALID_SECONDARY_RULE", rule_path, "secondary rule must be an object"))
            continue
        for key in sorted(set(rule) - _SECONDARY_RULE_KEYS):
            issues.append(_issue("INVALID_RULEBOOK", "UNKNOWN_FIELD", f"{rule_path}.{key}", "unknown secondary rule field"))
        for key in sorted(_SECONDARY_RULE_KEYS - set(rule)):
            issues.append(_issue("INVALID_RULEBOOK", "MISSING_REQUIRED_FIELD", f"{rule_path}.{key}", "required secondary rule field is missing"))
        if set(rule) != _SECONDARY_RULE_KEYS:
            continue
        input_key = _canonical_key(rule["inputKey"])
        output_key = _canonical_key(rule["outputKey"])
        if input_key is None or output_key is None:
            issues.append(_issue("INVALID_RULEBOOK", "INVALID_IDENTIFIER", rule_path, "secondary rule keys must be bounded lower-case identifiers"))
        elif output_key in output_keys:
            issues.append(_issue("INVALID_RULEBOOK", "DUPLICATE_OUTPUT_KEY", f"{rule_path}.outputKey", "secondary output keys must be unique per context"))
        else:
            output_keys.add(output_key)
        if _bounded_string(rule["label"]) is None:
            issues.append(_issue("INVALID_RULEBOOK", "INVALID_LABEL", f"{rule_path}.label", "secondary rule label must be a bounded string"))
        for numeric_key in ("basePercent", "ratingPerPercent"):
            if not _is_number(rule[numeric_key]):
                issues.append(_issue("INVALID_RULEBOOK", "INVALID_SECONDARY_NUMBER", f"{rule_path}.{numeric_key}", "secondary conversion fields must be numeric"))
        if _is_number(rule["ratingPerPercent"]) and rule["ratingPerPercent"] <= 0:
            issues.append(_issue("INVALID_RULEBOOK", "INVALID_RATING_CONVERSION", f"{rule_path}.ratingPerPercent", "ratingPerPercent must be greater than zero"))
        precision = rule["precision"]
        if isinstance(precision, bool) or not isinstance(precision, int) or precision < 0 or precision > 6:
            issues.append(_issue("INVALID_RULEBOOK", "INVALID_PRECISION", f"{rule_path}.precision", "precision must be an integer from 0 to 6"))
        if not _string_list(rule["sourceRefs"]):
            issues.append(_issue("INVALID_RULEBOOK", "MISSING_SOURCE_REFS", f"{rule_path}.sourceRefs", "secondary rules require source references"))
        if rule["displayUnit"] not in _ALLOWED_DISPLAY_UNITS:
            issues.append(_issue("INVALID_RULEBOOK", "INVALID_DISPLAY_UNIT", f"{rule_path}.displayUnit", "displayUnit must be percent or effect"))
    return issues


def parse_attribute_character_context(raw: object) -> tuple[dict | None, list[dict]]:
    """Parse the narrow character context without accepting client final stats."""
    if not isinstance(raw, dict):
        return None, [_issue("INVALID_CHARACTER_CONTEXT", "INVALID_CONTEXT", "characterContext", "character context must be an object")]

    issues: list[dict[str, str]] = []
    allowed_keys = {"schemaRevision", "raceKey"}
    for key in sorted(set(raw) - allowed_keys):
        issues.append(_issue("INVALID_CHARACTER_CONTEXT", "UNKNOWN_FIELD", f"characterContext.{key}", "only schemaRevision and raceKey are accepted"))
    revision = raw.get("schemaRevision")
    if revision is None:
        issues.append(_issue("INVALID_CHARACTER_CONTEXT", "MISSING_SCHEMA_REVISION", "characterContext.schemaRevision", "schemaRevision is required"))
    elif revision != ATTRIBUTE_CHARACTER_CONTEXT_REVISION:
        issues.append(_issue("INVALID_CHARACTER_CONTEXT", "UNSUPPORTED_SCHEMA_REVISION", "characterContext.schemaRevision", "unsupported character context revision"))
    race_key = _canonical_key(raw.get("raceKey"))
    if race_key is None:
        issues.append(_issue("INVALID_CHARACTER_CONTEXT", "INVALID_RACE_KEY", "characterContext.raceKey", "raceKey must be a bounded lower-case identifier"))
    if issues:
        return None, issues
    return {"schemaRevision": ATTRIBUTE_CHARACTER_CONTEXT_REVISION, "raceKey": race_key}, []


def validate_attribute_rulebook(
    raw: object,
    *,
    golden_samples: object | None = None,
    promotion_findings_reader: Any = None,
) -> tuple[dict | None, list[dict]]:
    """Validate a static rulebook and keep fixture-only contexts non-public."""
    if not isinstance(raw, dict):
        return None, [_issue("INVALID_RULEBOOK", "INVALID_RULEBOOK", "rulebook", "rulebook must be an object")]

    issues: list[dict[str, str]] = []
    for key in sorted(set(raw) - _RULEBOOK_KEYS):
        issues.append(_issue("INVALID_RULEBOOK", "UNKNOWN_FIELD", f"rulebook.{key}", "unknown rulebook field"))
    for key in sorted(_RULEBOOK_KEYS - set(raw)):
        issues.append(_issue("INVALID_RULEBOOK", "MISSING_REQUIRED_FIELD", f"rulebook.{key}", "required rulebook field is missing"))
    if raw.get("schemaRevision") != ATTRIBUTE_RULEBOOK_SCHEMA_REVISION:
        issues.append(_issue("INVALID_RULEBOOK", "UNSUPPORTED_SCHEMA_REVISION", "rulebook.schemaRevision", "unsupported rulebook revision"))
    if _bounded_string(raw.get("attributeRuleRevision")) is None:
        issues.append(_issue("INVALID_RULEBOOK", "INVALID_ATTRIBUTE_RULE_REVISION", "rulebook.attributeRuleRevision", "attributeRuleRevision must be a bounded string"))
    contexts = raw.get("contexts")
    if not isinstance(contexts, list) or not contexts:
        issues.append(_issue("INVALID_RULEBOOK", "INVALID_CONTEXTS", "rulebook.contexts", "contexts must be a non-empty list"))
    else:
        context_keys: set[str] = set()
        for index, context in enumerate(contexts):
            issues.extend(_validate_rulebook_context(context, index))
            if isinstance(context, dict) and isinstance(context.get("contextKey"), str):
                context_key = context["contextKey"]
                if context_key in context_keys:
                    issues.append(_issue("INVALID_RULEBOOK", "DUPLICATE_CONTEXT_KEY", f"rulebook.contexts[{index}].contextKey", "contextKey must be unique"))
                context_keys.add(context_key)
    if golden_samples is not None:
        samples, sample_issues = validate_armory_golden_samples(golden_samples)
        if sample_issues:
            issues.extend(sample_issues)
        elif isinstance(contexts, list):
            verified_sample_ids = {
                sample["id"]
                for sample in samples["samples"]
                if sample["status"] == "verified"
            }
            for index, context in enumerate(contexts):
                if not isinstance(context, dict) or context.get("status") != "verified":
                    continue
                for sample_id in context.get("goldenSampleIds", []):
                    if sample_id not in verified_sample_ids:
                        issues.append(_issue("INVALID_RULEBOOK", "UNVERIFIED_GOLDEN_SAMPLE", f"rulebook.contexts[{index}].goldenSampleIds", "verified rules require referenced verified Armory samples"))
    if callable(promotion_findings_reader) and isinstance(raw.get("attributeRuleRevision"), str):
        try:
            findings = promotion_findings_reader(raw["attributeRuleRevision"])
        except Exception:
            findings = []
            issues.append(_issue("INVALID_RULEBOOK", "ATTRIBUTE_RULE_AUDIT_FINDING_READER_UNAVAILABLE", "rulebook.attributeRuleRevision", "attribute audit finding reader is unavailable for rule promotion"))
        for finding in findings if isinstance(findings, list) else []:
            if not isinstance(finding, dict):
                continue
            if finding.get("attributeRuleRevision") != raw["attributeRuleRevision"]:
                continue
            context_key = _bounded_string(finding.get("contextKey")) or "attributeRuleAudit"
            issues.append(_issue("INVALID_RULEBOOK", "ATTRIBUTE_RULE_AUDIT_MISMATCH_BLOCKS_PROMOTION", f"rulebook.contexts.{context_key}", "a confirmed winner attribute audit mismatch blocks this rule revision from promotion"))
            break
    if issues:
        return None, issues
    return copy.deepcopy(raw), []


def _unavailable_context(attribute_rule_revision: str, message: str) -> dict:
    return {
        "contractRevision": ATTRIBUTE_CALCULATOR_CONTEXT_REVISION,
        "status": "rule_unavailable",
        "attributeRuleRevision": attribute_rule_revision,
        "raceOptions": [],
        "rules": [],
        "problems": [
            _issue("ATTRIBUTE_RULE_UNAVAILABLE", "ATTRIBUTE_RULE_UNAVAILABLE", "attributeCalculator", message)
        ],
    }


def _normalize_public_query(class_key: Any, spec_key: Any, level: Any) -> tuple[str, str, int] | None:
    normalized_class = _canonical_key(class_key)
    normalized_spec = _canonical_key(spec_key)
    if normalized_class is None or normalized_spec is None:
        return None
    if isinstance(level, bool) or not isinstance(level, int) or level < 1 or level > 100:
        return None
    return normalized_class, normalized_spec, level


def _public_rule(rule: dict, attribute_rule_revision: str) -> dict:
    public_rule = copy.deepcopy(rule)
    public_rule.pop("implementationNotes", None)
    public_rule["attributeRuleRevision"] = attribute_rule_revision
    return public_rule


def public_attribute_calculator_context(rulebook: dict, *, class_key: str, spec_key: str, level: int) -> dict:
    """Expose only verified, provenance-backed rules for one class/spec/level."""
    validated, validation_issues = validate_attribute_rulebook(rulebook)
    revision = validated["attributeRuleRevision"] if validated else ""
    query = _normalize_public_query(class_key, spec_key, level)
    if validation_issues or query is None:
        return _unavailable_context(revision, "no verified attribute rule context is available")

    normalized_class, normalized_spec, normalized_level = query
    matching_rules = [
        context
        for context in validated["contexts"]
        if context["status"] in _PUBLIC_STATUSES
        and context["classKey"] == normalized_class
        and context["specKey"] == normalized_spec
        and context["level"] == normalized_level
    ]
    if not matching_rules:
        return _unavailable_context(revision, "no verified attribute rule context is available")

    matching_rules.sort(key=lambda context: (context["raceKey"], context["contextKey"]))
    return {
        "contractRevision": ATTRIBUTE_CALCULATOR_CONTEXT_REVISION,
        "status": "available",
        "attributeRuleRevision": revision,
        "raceOptions": [{"raceKey": context["raceKey"]} for context in matching_rules],
        "rules": [_public_rule(context, revision) for context in matching_rules],
        "problems": [],
    }


def applicable_attribute_rule(
    rulebook: dict,
    *,
    class_key: str,
    spec_key: str,
    level: int,
    race_key: str,
) -> tuple[dict | None, list[dict]]:
    """Return one verified rule or a bounded unavailable problem for an exact race."""
    validated, validation_issues = validate_attribute_rulebook(rulebook)
    query = _normalize_public_query(class_key, spec_key, level)
    normalized_race = _canonical_key(race_key)
    if validation_issues or query is None or normalized_race is None:
        return None, [
            _issue("ATTRIBUTE_RULE_UNAVAILABLE", "ATTRIBUTE_RULE_UNAVAILABLE", "attributeCalculator", "no verified attribute rule context is available")
        ]
    normalized_class, normalized_spec, normalized_level = query
    for context in validated["contexts"]:
        if (
            context["status"] in _PUBLIC_STATUSES
            and context["classKey"] == normalized_class
            and context["specKey"] == normalized_spec
            and context["level"] == normalized_level
            and context["raceKey"] == normalized_race
        ):
            return _public_rule(context, validated["attributeRuleRevision"]), []
    return None, [
        _issue("ATTRIBUTE_RULE_UNAVAILABLE", "ATTRIBUTE_RULE_UNAVAILABLE", "attributeCalculator", "no verified attribute rule context is available")
    ]

#!/usr/bin/env python3
"""Exhaustive legacy/canonical fact comparison for candidate Gear Releases."""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping


_CLASSIFICATIONS = frozenset(
    {
        "exact_parity",
        "intended_correction",
        "newly_exposed_gap",
        "regression",
    }
)
_SUPPORTED_FACT_TYPES = frozenset(
    {
        "item_identity",
        "slot_compatibility",
        "variant_track",
        "executable_item_options",
        "static_stats",
        "socket_count",
        "enchant_capability",
        "embellishment_capability",
        "enhancement_option",
        "allowed_enhancement_options",
        "item_set_membership",
        "equipment_uniqueness",
    }
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )


def _row_indexes(snapshot: Any) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    value = snapshot if isinstance(snapshot, Mapping) else {}
    subjects: dict[str, Mapping[str, Any]] = {}
    options: dict[str, Mapping[str, Any]] = {}
    for row in value.get("items") or ():
        if not isinstance(row, Mapping) or not _text(row.get("itemId")):
            continue
        subjects[f"item:{_text(row['itemId'])}"] = row
    for row in value.get("variants") or ():
        if (
            not isinstance(row, Mapping)
            or not _text(row.get("itemId"))
            or not _text(row.get("variantKey"))
        ):
            continue
        subjects[
            f"item:{_text(row['itemId'])}/variant:{_text(row['variantKey'])}"
        ] = row
    for row in value.get("options") or ():
        if not isinstance(row, Mapping) or not _text(row.get("optionId")):
            continue
        options[f"option:{_text(row['optionId'])}"] = row
        if _text(row.get("optionKey")):
            options[f"option:{_text(row['optionKey'])}"] = row
    return subjects, options


def _capabilities(row: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
    for field in ("capabilityOverrides", "baseCapabilities"):
        value = payload.get(field)
        if isinstance(value, Mapping):
            return value
    return {}


def _legacy_value(
    subject_key: str,
    fact_type: str,
    subjects: Mapping[str, Mapping[str, Any]],
    options: Mapping[str, Mapping[str, Any]],
) -> tuple[bool, Any]:
    if fact_type == "enhancement_option":
        row = options.get(subject_key)
        if not row:
            return False, None
        payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
        effect = (
            row.get("simcOptions")
            if isinstance(row.get("simcOptions"), Mapping) and row.get("simcOptions")
            else payload.get("effect")
        )
        option_type = (
            "gem"
            if _text(row.get("optionType")).lower() in {"socket", "gem"}
            else _text(row.get("optionType")).lower()
        )
        value = {
            "optionId": subject_key.removeprefix("option:"),
            "optionType": option_type,
            "effect": _canonical(effect if isinstance(effect, Mapping) else {}),
            "applicableScopes": (
                ["*"]
                if option_type == "gem"
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
        return True, value
    row = subjects.get(subject_key)
    if not row:
        return False, None
    payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
    if fact_type == "item_identity":
        value = {"itemId": _text(row.get("itemId"))}
        if "/variant:" in subject_key:
            value["variantKey"] = _text(row.get("variantKey"))
        else:
            for field in (
                "inventoryType",
                "armorType",
                "weaponType",
                "handedness",
            ):
                if _text(payload.get(field)):
                    value[field] = _text(payload.get(field))
        return True, value
    if fact_type == "slot_compatibility":
        allowed = payload.get("allowedSlots")
        if isinstance(allowed, list) and allowed:
            return True, sorted({_text(slot) for slot in allowed if _text(slot)})
        if _text(row.get("slot")):
            return True, [_text(row.get("slot"))]
        return False, None
    if fact_type == "socket_count":
        capabilities = _capabilities(row)
        socket_count = capabilities.get("socketCount")
        has_socket = (
            row.get("hasSocket")
            if isinstance(row.get("hasSocket"), bool)
            else payload.get("hasSocket")
        )
        if (
            subject_key.split("/variant:", 1)[0] == "item:250033"
            and has_socket is False
            and socket_count == 1
        ):
            return True, False
        if isinstance(socket_count, int) and not isinstance(socket_count, bool):
            return True, socket_count
        if isinstance(has_socket, bool):
            return True, has_socket
        return False, None
    if fact_type in {"enchant_capability", "embellishment_capability"}:
        field = (
            "canEnchant"
            if fact_type == "enchant_capability"
            else "canEmbellish"
        )
        value = _capabilities(row).get(field)
        return (True, value) if isinstance(value, bool) else (False, None)
    if fact_type == "static_stats":
        value = payload.get("resolvedStats")
        return (
            (True, _canonical(value))
            if isinstance(value, Mapping) and value
            else (False, None)
        )
    if fact_type == "variant_track":
        if not _text(row.get("difficultyKey")) or not isinstance(row.get("itemLevel"), int):
            return False, None
        return True, {
            "itemId": _text(row.get("itemId")),
            "variantKey": _text(row.get("variantKey")),
            "track": _text(row.get("difficultyKey")),
            "itemLevel": row["itemLevel"],
        }
    if fact_type == "executable_item_options":
        simc_options = row.get("simcOptions")
        if not isinstance(simc_options, Mapping):
            return False, None
        value = {
            "itemId": _text(row.get("itemId")),
            "variantKey": _text(row.get("variantKey")),
            "options": _canonical(simc_options),
        }
        if isinstance(payload.get("enhancementManagement"), Mapping):
            value["enhancementManagement"] = _canonical(
                payload["enhancementManagement"]
            )
        return True, value
    if fact_type == "equipment_uniqueness":
        uniqueness = payload.get("equipmentUniqueness")
        return (
            (True, _canonical(uniqueness))
            if isinstance(uniqueness, Mapping)
            else (False, None)
        )
    if fact_type == "allowed_enhancement_options":
        raw_rules = payload.get("allowedEnhancementRules")
        if not isinstance(raw_rules, list) or not raw_rules:
            return False, None
        option_ids = []
        for rule in raw_rules:
            if (
                not isinstance(rule, Mapping)
                or not isinstance(rule.get("optionIds"), list)
            ):
                return False, None
            option_ids.extend(
                _text(option_id)
                for option_id in rule["optionIds"]
                if _text(option_id)
            )
        return True, sorted(set(option_ids))
    return False, None


def compare_legacy_and_canonical(
    legacy_snapshot: Any,
    canonical_facts: Iterable[Any],
    *,
    expected_fact_types_by_subject: Mapping[str, Iterable[str]] | None = None,
) -> dict[str, Any]:
    """Classify every supplied Fact exactly once and fail closed on unknowns."""

    subjects, options = _row_indexes(legacy_snapshot)
    comparisons: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    seen_fact_identities: set[tuple[str, str]] = set()
    for raw_fact in canonical_facts or ():
        fact = raw_fact if isinstance(raw_fact, Mapping) else {}
        subject_key = _text(fact.get("subjectKey"))
        fact_type = _text(fact.get("factType"))
        status = _text(fact.get("status"))
        fact_identity = (subject_key, fact_type)
        if fact_identity in seen_fact_identities:
            blockers.append(
                {
                    "code": "UNCLASSIFIED_FACT_DIFFERENCE",
                    "subjectKey": subject_key,
                    "factType": fact_type,
                }
            )
            continue
        seen_fact_identities.add(fact_identity)
        has_legacy, legacy_value = _legacy_value(
            subject_key,
            fact_type,
            subjects,
            options,
        )
        canonical_value = _canonical(fact.get("value"))
        if fact_type not in _SUPPORTED_FACT_TYPES:
            classification = ""
        elif status in {"unresolved_missing", "unresolved_conflict"}:
            classification = "newly_exposed_gap"
        elif (
            subject_key.split("/variant:", 1)[0] == "item:250033"
            and fact_type == "socket_count"
            and has_legacy
            and legacy_value is False
            and canonical_value == 1
        ):
            classification = "intended_correction"
        elif status == "verified" and has_legacy and _canonical(legacy_value) == canonical_value:
            classification = "exact_parity"
        elif status == "verified" and has_legacy:
            classification = "regression"
        else:
            classification = ""
        comparison = {
            "factKey": _text(fact.get("factKey")),
            "subjectKey": subject_key,
            "factType": fact_type,
            "legacyValue": _canonical(legacy_value),
            "canonicalValue": canonical_value,
            "canonicalStatus": status,
            "classification": classification or "unclassified",
        }
        comparisons.append(comparison)
        if classification == "regression":
            blockers.append(
                {
                    "code": "CANONICAL_FACT_REGRESSION",
                    "subjectKey": subject_key,
                    "factType": fact_type,
                }
            )
        elif classification not in _CLASSIFICATIONS:
            blockers.append(
                {
                    "code": "UNCLASSIFIED_FACT_DIFFERENCE",
                    "subjectKey": subject_key,
                    "factType": fact_type,
                }
            )
    for subject_key, fact_types in (
        expected_fact_types_by_subject or {}
    ).items():
        for fact_type in fact_types:
            identity = (_text(subject_key), _text(fact_type))
            if identity in seen_fact_identities:
                continue
            blockers.append(
                {
                    "code": "UNCLASSIFIED_FACT_DIFFERENCE",
                    "subjectKey": identity[0],
                    "factType": identity[1],
                }
            )
    comparisons.sort(
        key=lambda row: (
            row["subjectKey"],
            row["factType"],
            row["factKey"],
        )
    )
    blockers.sort(key=lambda row: (row["code"], row["subjectKey"], row["factType"]))
    return {
        "schemaRevision": "gear-fact-shadow-v1",
        "status": "blocked" if blockers else "pass",
        "comparisons": comparisons,
        "counts": {
            category: sum(
                row["classification"] == category for row in comparisons
            )
            for category in sorted(_CLASSIFICATIONS)
        },
        "blockers": blockers,
    }


__all__ = ("compare_legacy_and_canonical",)

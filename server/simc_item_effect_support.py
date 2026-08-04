#!/usr/bin/env python3
"""Pure, fail-closed effect support classification for one Exact item."""

from __future__ import annotations

from typing import Any, Mapping


EFFECT_SUPPORT_SCHEMA_REVISION = "simc-item-effect-support-v1"
EFFECT_SUBJECT_KINDS = (
    "item", "gem", "enchant", "embellishment", "crafted_effect", "set_bonus",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _subjects(exact_item: Any) -> list[dict[str, str]]:
    item = exact_item if isinstance(exact_item, Mapping) else {}
    selection = item.get("enhancementSelection")
    selection = selection if isinstance(selection, Mapping) else {}
    variant = _text(item.get("exactVariantSignature"))
    result = [{
        "subjectKind": "item", "subjectKey": _text(item.get("itemId")),
        "subjectVariantSignature": variant,
    }]
    for key in selection.get("gemIds") or []:
        token = _text(key)
        if token:
            result.append({"subjectKind": "gem", "subjectKey": token, "subjectVariantSignature": f"gem:{token}"})
    enchant = _text(selection.get("enchantId"))
    if enchant:
        result.append({"subjectKind": "enchant", "subjectKey": enchant, "subjectVariantSignature": f"enchant:{enchant}"})
    for kind, field in (("embellishment", "embellishmentIds"), ("crafted_effect", "craftedEffectIds")):
        values = selection.get(field) if field in selection else item.get(field)
        for key in values or []:
            token = _text(key)
            if token:
                result.append({"subjectKind": kind, "subjectKey": token, "subjectVariantSignature": f"{kind}:{token}"})
    return result


def _matching(records: Any, subject: Mapping[str, str]) -> list[Mapping[str, Any]]:
    source = records.get("records") if isinstance(records, Mapping) else records
    return [
        record for record in (source or [])
        if isinstance(record, Mapping)
        and _text(record.get("subjectKind")) == subject["subjectKind"]
        and _text(record.get("subjectKey")) == subject["subjectKey"]
        and _text(record.get("subjectVariantSignature")) == subject["subjectVariantSignature"]
    ]


def _subject_status(subject: Mapping[str, str], runtime: str, records: Any) -> dict[str, str]:
    matches = _matching(records, subject)
    if any(_text(record.get("status")) == "unsupported" for record in matches):
        return {**subject, "status": "unsupported"}
    static = any(record.get("hasDynamicEffect") is False for record in matches)
    dynamic = any(record.get("hasDynamicEffect") is True for record in matches)
    governed = any(
        record.get("hasDynamicEffect") is True
        and _text(record.get("status")) == "verified"
        and _text(record.get("simcRuntimeRevision")) == runtime
        and _text(record.get("supportRecordKey") or record.get("probeKey"))
        and _text(record.get("verifiedAt"))
        and "exitCode" not in record
        for record in matches
    )
    return {**subject, "status": "verified" if static or (dynamic and governed) else "unknown"}


def resolve_exact_item_effect_support(
    exact_item: Any,
    *,
    runtime_revision: str,
    support_records: Any,
) -> dict[str, Any]:
    """Aggregate Exact-owned subjects into verified, unknown, or unsupported."""

    runtime = _text(runtime_revision)
    resolved = [_subject_status(subject, runtime, support_records) for subject in _subjects(exact_item)]
    statuses = {entry["status"] for entry in resolved}
    status = "unsupported" if "unsupported" in statuses else "unknown" if "unknown" in statuses else "verified"
    keys = sorted({
        _text(record.get("supportRecordKey") or record.get("probeKey"))
        for subject in resolved
        for record in _matching(support_records, subject)
        if _text(record.get("simcRuntimeRevision")) == runtime
        and _text(record.get("status")) == "verified"
        and _text(record.get("supportRecordKey") or record.get("probeKey"))
    })
    return {
        "schemaRevision": EFFECT_SUPPORT_SCHEMA_REVISION,
        "status": status,
        "simcRuntimeRevision": runtime,
        "subjects": resolved,
        "supportRecordKeys": keys,
    }


__all__ = ("EFFECT_SUBJECT_KINDS", "EFFECT_SUPPORT_SCHEMA_REVISION", "resolve_exact_item_effect_support")

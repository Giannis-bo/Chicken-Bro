#!/usr/bin/env python3
"""Pure, content-addressed SimC effect-support contracts for one Exact item."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Mapping


EFFECT_SUPPORT_SCHEMA_REVISION = "simc-item-effect-support-v1"
EFFECT_SUBJECT_KINDS = (
    "item", "gem", "enchant", "embellishment", "crafted_effect", "set_bonus",
)
_RECORD_KEY_PATTERN = re.compile(r"^simc-item-effect-record:sha256:[0-9a-f]{64}$")
_SNAPSHOT_KEY_PATTERN = re.compile(r"^simulation-snapshot:sha256:[0-9a-f]{64}$")
_EFFECT_TYPES = frozenset({"on_use", "proc", "buff"})
_STATIC_KEYS = frozenset({"schemaRevision", "subjectKind", "subjectKey", "subjectVariantSignature", "hasDynamicEffect", "simcRuntimeRevision", "verifiedAt", "supportRecordKey"})
_DYNAMIC_KEYS = frozenset({"schemaRevision", "status", "subjectKind", "subjectKey", "subjectVariantSignature", "hasDynamicEffect", "simcRuntimeRevision", "effectType", "expectedActionTokens", "expectedBuffTokens", "experimentSnapshotKey", "controlSnapshotKey", "verifiedAt", "supportRecordKey"})
_UNSUPPORTED_KEYS = frozenset({"schemaRevision", "status", "subjectKind", "subjectKey", "subjectVariantSignature", "hasDynamicEffect", "simcRuntimeRevision", "unsupportedReason", "verifiedAt", "supportRecordKey"})


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _signature_token(value: Any) -> str:
    if isinstance(value, bool):
        return ""
    return value.strip() if isinstance(value, str) else str(value) if isinstance(value, int) else ""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _record_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "supportRecordKey"}


def effect_record_key(record: Mapping[str, Any]) -> str:
    """Return the content key for a strict record payload (without its key)."""

    return "simc-item-effect-record:sha256:" + hashlib.sha256(_canonical(_record_payload(record))).hexdigest()


def seal_effect_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Add the deterministic support-record key; callers still need validation."""

    sealed = dict(record)
    sealed["supportRecordKey"] = effect_record_key(sealed)
    return sealed


def _valid_timestamp(value: Any) -> bool:
    text = _text(value)
    if not text.endswith("Z") or "\n" in text:
        return False
    try:
        return datetime.fromisoformat(text[:-1] + "+00:00").tzinfo is not None
    except ValueError:
        return False


def _tokens(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_text(token) for token in value)


def _valid_subject(record: Mapping[str, Any]) -> bool:
    return (
        _text(record.get("subjectKind")) in EFFECT_SUBJECT_KINDS
        and bool(_text(record.get("subjectKey")))
        and bool(_text(record.get("subjectVariantSignature")))
    )


def _valid_record_key(record: Mapping[str, Any]) -> bool:
    key = _text(record.get("supportRecordKey"))
    if not _RECORD_KEY_PATTERN.fullmatch(key):
        return False
    try:
        return key == effect_record_key(record)
    except (TypeError, ValueError):
        return False


def _valid_static(record: Mapping[str, Any], runtime: str) -> bool:
    return (
        set(record) == _STATIC_KEYS
        and _text(record.get("schemaRevision")) == "simc-item-effect-authority-v1"
        and record.get("hasDynamicEffect") is False
        and _text(record.get("simcRuntimeRevision")) == runtime
        and _valid_subject(record)
        and _valid_timestamp(record.get("verifiedAt"))
        and _valid_record_key(record)
    )


def _valid_dynamic(record: Mapping[str, Any], runtime: str) -> bool:
    return (
        set(record) == _DYNAMIC_KEYS
        and _text(record.get("schemaRevision")) == "simc-item-effect-record-v1"
        and _text(record.get("status")) == "verified"
        and record.get("hasDynamicEffect") is True
        and _text(record.get("simcRuntimeRevision")) == runtime
        and _valid_subject(record)
        and _text(record.get("effectType")) in _EFFECT_TYPES
        and _tokens(record.get("expectedActionTokens"))
        and _tokens(record.get("expectedBuffTokens"))
        and bool(_SNAPSHOT_KEY_PATTERN.fullmatch(_text(record.get("experimentSnapshotKey"))))
        and bool(_SNAPSHOT_KEY_PATTERN.fullmatch(_text(record.get("controlSnapshotKey"))))
        and _text(record.get("experimentSnapshotKey")) != _text(record.get("controlSnapshotKey"))
        and _valid_timestamp(record.get("verifiedAt"))
        and _valid_record_key(record)
    )


def _valid_unsupported(record: Mapping[str, Any], runtime: str) -> bool:
    return (
        set(record) == _UNSUPPORTED_KEYS
        and _text(record.get("schemaRevision")) == "simc-item-effect-record-v1"
        and _text(record.get("status")) == "unsupported"
        and record.get("hasDynamicEffect") is True
        and _text(record.get("simcRuntimeRevision")) == runtime
        and _valid_subject(record)
        and bool(_text(record.get("unsupportedReason")))
        and _valid_timestamp(record.get("verifiedAt"))
        and _valid_record_key(record)
    )


def _subject_signature(kind: str, value: Any) -> str:
    return f"{kind}-variant:sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _subjects(exact_item: Any) -> list[dict[str, str]]:
    item = exact_item if isinstance(exact_item, Mapping) else {}
    selection = item.get("enhancementSelection") if isinstance(item.get("enhancementSelection"), Mapping) else {}
    result = [{"subjectKind": "item", "subjectKey": _text(item.get("itemId")), "subjectVariantSignature": _text(item.get("exactVariantSignature"))}]
    gem_ids, bonuses, levels = list(selection.get("gemIds") or []), list(selection.get("gemBonusIds") or []), list(selection.get("gemItemLevels") or [])
    for index, key in enumerate(gem_ids):
        token = _text(key)
        if token:
            bonus = _signature_token(bonuses[index]) if index < len(bonuses) else ""
            level = _signature_token(levels[index]) if index < len(levels) else ""
            result.append({"subjectKind": "gem", "subjectKey": token, "subjectVariantSignature": _subject_signature("gem", [token, bonus, level])})
    enchant = _text(selection.get("enchantId"))
    if enchant:
        result.append({"subjectKind": "enchant", "subjectKey": enchant, "subjectVariantSignature": _subject_signature("enchant", [enchant])})
    for kind, field in (("embellishment", "embellishmentIds"), ("crafted_effect", "craftedEffectIds")):
        values = selection.get(field) if field in selection else item.get(field)
        for key in values or []:
            token = _text(key)
            if token:
                result.append({"subjectKind": kind, "subjectKey": token, "subjectVariantSignature": _subject_signature(kind, [token])})
    return result


def _matching(records: Any, subject: Mapping[str, str]) -> list[Mapping[str, Any]]:
    source = records.get("records") if isinstance(records, Mapping) else records
    return [record for record in (source or []) if isinstance(record, Mapping) and all(_text(record.get(field)) == subject[field] for field in ("subjectKind", "subjectKey", "subjectVariantSignature"))]


def _subject_status(subject: Mapping[str, str], runtime: str, records: Any) -> dict[str, str]:
    matches = _matching(records, subject)
    if any(_valid_unsupported(record, runtime) for record in matches):
        return {**subject, "status": "unsupported"}
    if any(_valid_static(record, runtime) or _valid_dynamic(record, runtime) for record in matches):
        return {**subject, "status": "verified"}
    return {**subject, "status": "unknown"}


def effect_support_key(result: Mapping[str, Any]) -> str:
    payload = {key: result[key] for key in ("schemaRevision", "status", "simcRuntimeRevision", "subjects", "supportRecords", "supportRecordKeys")}
    return "simc-item-effect-support:sha256:" + hashlib.sha256(_canonical(payload)).hexdigest()


def resolve_exact_item_effect_support(exact_item: Any, *, runtime_revision: str, support_records: Any) -> dict[str, Any]:
    """Aggregate Exact-owned subjects into verified, unknown, or unsupported."""

    runtime = _text(runtime_revision)
    subjects = _subjects(exact_item)
    resolved = [_subject_status(subject, runtime, support_records) for subject in subjects]
    statuses = {entry["status"] for entry in resolved}
    status = "unsupported" if "unsupported" in statuses else "unknown" if "unknown" in statuses else "verified"
    sealed = []
    for subject in resolved:
        for record in _matching(support_records, subject):
            if _valid_static(record, runtime) or _valid_dynamic(record, runtime):
                sealed.append(dict(record))
    sealed.sort(key=lambda record: _text(record.get("supportRecordKey")))
    result = {"schemaRevision": EFFECT_SUPPORT_SCHEMA_REVISION, "status": status, "simcRuntimeRevision": runtime, "subjects": resolved, "supportRecords": sealed, "supportRecordKeys": [record["supportRecordKey"] for record in sealed]}
    result["effectSupportKey"] = effect_support_key(result)
    return result


__all__ = ("EFFECT_SUBJECT_KINDS", "EFFECT_SUPPORT_SCHEMA_REVISION", "effect_record_key", "effect_support_key", "resolve_exact_item_effect_support", "seal_effect_record")

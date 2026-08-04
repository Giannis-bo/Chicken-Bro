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
_RUNTIME_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,256}$")
_EFFECT_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.: -]{1,256}$")
_MAX_EFFECT_TOKENS = 32
_MAX_EFFECT_TOKEN_BYTES = 256
_MAX_EFFECT_SEQUENCE_BYTES = 4096
_STATIC_KEYS = frozenset({"schemaRevision", "subjectKind", "subjectKey", "subjectVariantSignature", "hasDynamicEffect", "simcRuntimeRevision", "verifiedAt", "supportRecordKey"})
_DYNAMIC_KEYS = frozenset({"schemaRevision", "status", "subjectKind", "subjectKey", "subjectVariantSignature", "hasDynamicEffect", "simcRuntimeRevision", "effectType", "expectedActionTokens", "expectedBuffTokens", "experimentSnapshotKey", "controlSnapshotKey", "verifiedAt", "supportRecordKey"})
_UNSUPPORTED_KEYS = frozenset({"schemaRevision", "status", "subjectKind", "subjectKey", "subjectVariantSignature", "hasDynamicEffect", "simcRuntimeRevision", "unsupportedReason", "verifiedAt", "supportRecordKey"})


def _raw_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _canonical_text(value: Any, *, max_bytes: int = 256, allow_empty: bool = False) -> str | None:
    if not isinstance(value, str) or value != value.strip():
        return None
    if not allow_empty and not value:
        return None
    if len(value.encode("utf-8")) > max_bytes:
        return None
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return None
    return value


def _signature_token(value: Any) -> str:
    if isinstance(value, bool):
        return ""
    return value if isinstance(value, str) else str(value) if isinstance(value, int) else ""


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
    text = _canonical_text(value, max_bytes=64)
    if text is None or not text.endswith("Z"):
        return False
    try:
        return datetime.fromisoformat(text[:-1] + "+00:00").tzinfo is not None
    except ValueError:
        return False


def _tokens(value: Any, *, allow_empty: bool = False) -> bool:
    if not isinstance(value, list) or (not allow_empty and not value) or len(value) > _MAX_EFFECT_TOKENS:
        return False
    total = 0
    for token in value:
        text = _canonical_text(token, max_bytes=_MAX_EFFECT_TOKEN_BYTES)
        if text is None or not _EFFECT_TOKEN_PATTERN.fullmatch(text):
            return False
        encoded = token.encode("utf-8")
        total += len(encoded)
    return total <= _MAX_EFFECT_SEQUENCE_BYTES


def valid_runtime_revision(value: Any) -> bool:
    text = _canonical_text(value, max_bytes=256)
    return text is not None and _RUNTIME_PATTERN.fullmatch(text) is not None


def valid_effect_tokens(value: Any, *, allow_empty: bool = False) -> bool:
    return _tokens(value, allow_empty=allow_empty)


def _valid_subject(record: Mapping[str, Any]) -> bool:
    return (
        record.get("subjectKind") in EFFECT_SUBJECT_KINDS
        and _canonical_text(record.get("subjectKey")) is not None
        and _canonical_text(record.get("subjectVariantSignature")) is not None
    )


def _valid_record_key(record: Mapping[str, Any]) -> bool:
    key = _canonical_text(record.get("supportRecordKey"))
    if key is None or not _RECORD_KEY_PATTERN.fullmatch(key):
        return False
    try:
        return key == effect_record_key(record)
    except (TypeError, ValueError):
        return False


def _valid_static(record: Mapping[str, Any], runtime: str) -> bool:
    return (
        set(record) == _STATIC_KEYS
        and record.get("schemaRevision") == "simc-item-effect-authority-v1"
        and record.get("hasDynamicEffect") is False
        and valid_runtime_revision(runtime)
        and record.get("simcRuntimeRevision") == runtime
        and _valid_subject(record)
        and _valid_timestamp(record.get("verifiedAt"))
        and _valid_record_key(record)
    )


def _valid_dynamic(record: Mapping[str, Any], runtime: str) -> bool:
    return (
        set(record) == _DYNAMIC_KEYS
        and record.get("schemaRevision") == "simc-item-effect-record-v1"
        and record.get("status") == "verified"
        and record.get("hasDynamicEffect") is True
        and valid_runtime_revision(runtime)
        and record.get("simcRuntimeRevision") == runtime
        and _valid_subject(record)
        and record.get("effectType") in _EFFECT_TYPES
        and _tokens(record.get("expectedActionTokens"))
        and _tokens(record.get("expectedBuffTokens"))
        and _canonical_text(record.get("experimentSnapshotKey")) is not None
        and _canonical_text(record.get("controlSnapshotKey")) is not None
        and bool(_SNAPSHOT_KEY_PATTERN.fullmatch(record["experimentSnapshotKey"]))
        and bool(_SNAPSHOT_KEY_PATTERN.fullmatch(record["controlSnapshotKey"]))
        and record.get("experimentSnapshotKey") != record.get("controlSnapshotKey")
        and _valid_timestamp(record.get("verifiedAt"))
        and _valid_record_key(record)
    )


def _valid_unsupported(record: Mapping[str, Any], runtime: str) -> bool:
    return (
        set(record) == _UNSUPPORTED_KEYS
        and record.get("schemaRevision") == "simc-item-effect-record-v1"
        and record.get("status") == "unsupported"
        and record.get("hasDynamicEffect") is True
        and valid_runtime_revision(runtime)
        and record.get("simcRuntimeRevision") == runtime
        and _valid_subject(record)
        and _canonical_text(record.get("unsupportedReason")) is not None
        and _valid_timestamp(record.get("verifiedAt"))
        and _valid_record_key(record)
    )


def _subject_signature(kind: str, value: Any) -> str:
    return f"{kind}-variant:sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _subjects(exact_item: Any) -> list[dict[str, str]]:
    item = exact_item if isinstance(exact_item, Mapping) else {}
    selection = item.get("enhancementSelection") if isinstance(item.get("enhancementSelection"), Mapping) else {}
    result = [{"subjectKind": "item", "subjectKey": _raw_text(item.get("itemId")), "subjectVariantSignature": _raw_text(item.get("exactVariantSignature"))}]
    gem_ids, bonuses, levels = list(selection.get("gemIds") or []), list(selection.get("gemBonusIds") or []), list(selection.get("gemItemLevels") or [])
    for index, key in enumerate(gem_ids):
        token = _raw_text(key)
        if token:
            bonus = _signature_token(bonuses[index]) if index < len(bonuses) else ""
            level = _signature_token(levels[index]) if index < len(levels) else ""
            result.append({"subjectKind": "gem", "subjectKey": token, "subjectVariantSignature": _subject_signature("gem", [token, bonus, level])})
    enchant = _raw_text(selection.get("enchantId"))
    if enchant:
        result.append({"subjectKind": "enchant", "subjectKey": enchant, "subjectVariantSignature": _subject_signature("enchant", [enchant])})
    for kind, field in (("embellishment", "embellishmentIds"), ("crafted_effect", "craftedStats")):
        values = selection.get(field)
        for key in values or []:
            token = _raw_text(key)
            if token:
                result.append({"subjectKind": kind, "subjectKey": token, "subjectVariantSignature": _subject_signature(kind, [token])})
    return result


def _matching(records: Any, subject: Mapping[str, str]) -> list[Mapping[str, Any]]:
    source = records.get("records") if isinstance(records, Mapping) else records
    identity_fields = ("subjectKind", "subjectKey", "subjectVariantSignature")
    if any(_canonical_text(subject.get(field)) is None for field in identity_fields):
        return []
    return [
        record for record in (source or [])
        if isinstance(record, Mapping)
        and all(
            _canonical_text(record.get(field)) is not None
            and record.get(field) == subject[field]
            for field in identity_fields
        )
    ]


def _subject_status(subject: Mapping[str, str], runtime: str, records: Any) -> dict[str, str]:
    matches = _matching(records, subject)
    if any(_valid_unsupported(record, runtime) for record in matches):
        return {**subject, "status": "unsupported"}
    if any(_valid_static(record, runtime) or _valid_dynamic(record, runtime) for record in matches):
        return {**subject, "status": "verified"}
    return {**subject, "status": "unknown"}


def validate_effect_record(record: Any, *, runtime_revision: str) -> bool:
    """Validate one sealed effect record for its current runtime."""

    if not isinstance(record, Mapping):
        return False
    runtime = runtime_revision if isinstance(runtime_revision, str) else ""
    return _valid_static(record, runtime) or _valid_dynamic(record, runtime) or _valid_unsupported(record, runtime)


def effect_support_key(result: Mapping[str, Any]) -> str:
    payload = {key: result[key] for key in ("schemaRevision", "status", "simcRuntimeRevision", "subjects", "supportRecords", "supportRecordKeys")}
    return "simc-item-effect-support:sha256:" + hashlib.sha256(_canonical(payload)).hexdigest()


def resolve_exact_item_effect_support(exact_item: Any, *, runtime_revision: str, support_records: Any) -> dict[str, Any]:
    """Aggregate Exact-owned subjects into verified, unknown, or unsupported."""

    runtime = runtime_revision if isinstance(runtime_revision, str) else ""
    subjects = _subjects(exact_item)
    resolved = [_subject_status(subject, runtime, support_records) for subject in subjects]
    statuses = {entry["status"] for entry in resolved}
    status = "unsupported" if "unsupported" in statuses else "unknown" if "unknown" in statuses else "verified"
    sealed = []
    for subject in resolved:
        for record in _matching(support_records, subject):
            if _valid_static(record, runtime) or _valid_dynamic(record, runtime) or _valid_unsupported(record, runtime):
                sealed.append(dict(record))
    sealed.sort(key=lambda record: _raw_text(record.get("supportRecordKey")))
    result = {"schemaRevision": EFFECT_SUPPORT_SCHEMA_REVISION, "status": status, "simcRuntimeRevision": runtime, "subjects": resolved, "supportRecords": sealed, "supportRecordKeys": [record["supportRecordKey"] for record in sealed]}
    result["effectSupportKey"] = effect_support_key(result)
    return result


__all__ = ("EFFECT_SUBJECT_KINDS", "EFFECT_SUPPORT_SCHEMA_REVISION", "effect_record_key", "effect_support_key", "resolve_exact_item_effect_support", "seal_effect_record", "valid_effect_tokens", "valid_runtime_revision", "validate_effect_record")

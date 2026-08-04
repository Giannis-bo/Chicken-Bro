#!/usr/bin/env python3
"""Strict, content-addressed authority envelope for a ready Exact item."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping


_EXACT_KEY_PATTERN = re.compile(r"^exact-item-instance:sha256:[0-9a-f]{64}$")
_EFFECT_RECORD_KEY_PATTERN = re.compile(r"^simc-item-effect-record:sha256:[0-9a-f]{64}$")
_FORBIDDEN_FRAGMENTS = ("owner", "catalog", "observ", "provenance", "sourceurl", "profileurl")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            any(fragment in re.sub(r"[^a-z0-9]", "", str(key).lower()) for fragment in _FORBIDDEN_FRAGMENTS)
            or _contains_forbidden(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden(item) for item in value)
    return False


def _blocked(code: str) -> dict[str, Any]:
    return {"schemaRevision": "exact-authority-envelope-v1", "status": "blocked", "problemCodes": [code]}


def _nonempty_mapping(value: Any) -> bool:
    return isinstance(value, Mapping) and bool(value)


def _effect_record_keys(value: Mapping[str, Any]) -> list[str] | None:
    keys = value.get("supportRecordKeys")
    if not isinstance(keys, list) or not keys:
        return None
    normalized = [str(key or "").strip() for key in keys]
    return normalized if all(_EFFECT_RECORD_KEY_PATTERN.fullmatch(key) for key in normalized) else None


def build_exact_authority_envelope(
    *, exact_item: Any, static_facts: Any, serializer_input: Any,
    progression_binding: Any, effect_support: Any, resolver_revision: str,
) -> dict[str, Any]:
    """Return one immutable exact-authority-envelope-v1 when all inputs are ready."""

    if not all(isinstance(value, Mapping) for value in (exact_item, static_facts, serializer_input, progression_binding, effect_support)):
        return _blocked("EXACT_AUTHORITY_FIELDS_INVALID")
    if _contains_forbidden((exact_item, static_facts, serializer_input, progression_binding, effect_support)):
        return _blocked("EXACT_AUTHORITY_PROVENANCE_FORBIDDEN")
    if effect_support.get("status") != "verified":
        return _blocked("EXACT_AUTHORITY_EFFECT_SUPPORT_NOT_READY")
    if not _EXACT_KEY_PATTERN.fullmatch(str(exact_item.get("exactItemInstanceKey") or "")):
        return _blocked("EXACT_AUTHORITY_EXACT_ITEM_INVALID")
    if not _nonempty_mapping(static_facts):
        return _blocked("EXACT_AUTHORITY_STATIC_FACTS_MISSING")
    if not _nonempty_mapping(serializer_input) or not str(serializer_input.get("id") or "").strip() or not str(serializer_input.get("ilevel") or "").strip():
        return _blocked("EXACT_AUTHORITY_SERIALIZER_INPUT_MISSING")
    if not _nonempty_mapping(progression_binding) or not str(progression_binding.get("gearRuleRevision") or progression_binding.get("ruleRevision") or "").strip() or not _nonempty_mapping(progression_binding.get("progressionState")):
        return _blocked("EXACT_AUTHORITY_PROGRESSION_BINDING_MISSING")
    if _effect_record_keys(effect_support) is None:
        return _blocked("EXACT_AUTHORITY_EFFECT_RECORD_MISSING")
    if not str(effect_support.get("simcRuntimeRevision") or "") or not str(resolver_revision or "").strip():
        return _blocked("EXACT_AUTHORITY_REVISION_MISSING")
    payload = {
        "schemaRevision": "exact-authority-envelope-v1", "exactItem": exact_item,
        "staticFacts": static_facts, "serializerInput": serializer_input,
        "progressionBinding": progression_binding, "effectSupport": effect_support,
        "resolverRevision": str(resolver_revision).strip(),
    }
    key = "exact-authority:sha256:" + hashlib.sha256(_canonical(payload)).hexdigest()
    return {"schemaRevision": "exact-authority-envelope-v1", "status": "ready", "exactAuthorityKey": key, "canonicalPayload": json.loads(_canonical(payload))}


__all__ = ("build_exact_authority_envelope",)

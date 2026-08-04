#!/usr/bin/env python3
"""Strict, content-addressed authority envelope for a ready Exact item."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


_FORBIDDEN = frozenset({"owner", "ownerId", "catalog", "catalogRevision", "catalogStatus", "observationCount", "observedAt"})


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(str(key) in _FORBIDDEN or _contains_forbidden(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden(item) for item in value)
    return False


def _blocked(code: str) -> dict[str, Any]:
    return {"schemaRevision": "exact-authority-envelope-v1", "status": "blocked", "problemCodes": [code]}


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
    if not str(exact_item.get("exactItemInstanceKey") or "").startswith("exact-item-instance:sha256:"):
        return _blocked("EXACT_AUTHORITY_EXACT_ITEM_INVALID")
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

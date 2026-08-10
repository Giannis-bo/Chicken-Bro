#!/usr/bin/env python3
"""Canonical admission binding for one server-reloaded remote gear template.

This module deliberately does not query a registry, a catalog, or an API.  Its
caller must first prove one template group and one sealed Authority Bundle per
slot.  The resulting document only records that completed server-owned proof;
it is never a runtime discovery fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Mapping
import uuid

try:
    from .gear_canonical_kernel import (
        CanonicalValueError,
        SealedCanonicalDocument,
        _rehydrate_canonical_document,
        canonical_identity_token,
        canonical_json_bytes,
        canonical_mapping,
        canonical_ordered_list,
        canonical_slot,
        seal_canonical_document,
        verified_payload_copy,
    )
    from .gear_contracts import (
        EXACT_LOADOUT_CORE_SLOTS,
        parse_selection_intent,
        selection_signature,
    )
except ImportError:  # pragma: no cover - script entrypoint compatibility
    from gear_canonical_kernel import (
        CanonicalValueError,
        SealedCanonicalDocument,
        _rehydrate_canonical_document,
        canonical_identity_token,
        canonical_json_bytes,
        canonical_mapping,
        canonical_ordered_list,
        canonical_slot,
        seal_canonical_document,
        verified_payload_copy,
    )
    from gear_contracts import (
        EXACT_LOADOUT_CORE_SLOTS,
        parse_selection_intent,
        selection_signature,
    )


EXACT_TEMPLATE_AUTHORITY_BINDING_SCHEMA_REVISION = "exact-template-authority-binding-v1"
EXACT_TEMPLATE_AUTHORITY_BINDING_DOCUMENT_KIND = "exact_template_authority_binding"
EXACT_TEMPLATE_AUTHORITY_BINDING_KEY_PREFIX = "exact-template-authority-binding:sha256:"
_OWNER_NAMESPACE = "exact-template-owner-v1:"
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_CONFIG_HASH = re.compile(r"^[0-9a-f]{64}$")
_ENVELOPE_KEY = re.compile(r"^exact-authority:sha256:[0-9a-f]{64}$")
_SOURCE_KEYS = frozenset({
    "ownerKeyHash",
    "templateId",
    "templateConfigHash",
    "sourcePayloadHash",
    "selectionSignature",
})
_AUTHORITY_KEYS = frozenset({
    "gearExactRegistryRevision",
    "gearRuleRevision",
    "resolverRevision",
    "simcRuntimeRevision",
    "templateAuthorityIdentity",
    "templateContentHash",
})
_BINDING_KEYS = frozenset({
    "schemaRevision",
    "source",
    "authority",
    "exactAuthorityBySlot",
})
_PAIR_KEYS = frozenset({"slot", "exactAuthorityEnvelopeKey"})


class ExactTemplateAuthorityBindingError(ValueError):
    """A remote template or its already-proven admission closure is unsafe."""


@dataclass(frozen=True)
class RemoteTemplateSource:
    owner_key_hash: str
    template_id: str
    template_config_hash: str
    source_payload_hash: str
    selection_signature: str
    selection_intent: dict[str, Any]


def _error(code: str, path: str) -> ExactTemplateAuthorityBindingError:
    return ExactTemplateAuthorityBindingError(f"{code} at {path}")


def _uuid(value: Any, *, path: str) -> str:
    if type(value) is not str:
        raise _error("INVALID_UUID", path)
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise _error("INVALID_UUID", path) from error
    canonical = str(parsed)
    if value != canonical:
        raise _error("NON_CANONICAL_UUID", path)
    return canonical


def _identity(value: Any, *, path: str) -> str:
    try:
        return canonical_identity_token(value, path=path, max_bytes=256)
    except CanonicalValueError as error:
        raise _error(error.code, path) from error


def _sha256(value: Any, *, path: str) -> str:
    normalized = _identity(value, path=path)
    if _SHA256.fullmatch(normalized) is None:
        raise _error("INVALID_SHA256", path)
    return normalized


def _source_owner_hash(owner_id: str) -> str:
    return "sha256:" + hashlib.sha256(
        (_OWNER_NAMESPACE + owner_id).encode("utf-8"),
    ).hexdigest()


def owner_key_hash_for_user_id(owner_id: Any) -> str:
    """Derive the non-reversible owner scope used by Exact source bindings."""

    return _source_owner_hash(_uuid(owner_id, path="ownerId"))


def _ordered_source_slots(intent: Mapping[str, Any]) -> tuple[str, ...]:
    slots = intent.get("slots") if isinstance(intent.get("slots"), Mapping) else {}
    required = set(EXACT_LOADOUT_CORE_SLOTS)
    if not required.issubset(slots):
        raise _error("EXACT_TEMPLATE_CORE_SLOTS_REQUIRED", "metadata.selectionIntent.slots")
    expected = list(EXACT_LOADOUT_CORE_SLOTS)
    if "off_hand" in slots:
        expected.append("off_hand")
    if set(slots) != set(expected):
        raise _error("EXACT_TEMPLATE_SLOT_SET_INVALID", "metadata.selectionIntent.slots")
    return tuple(expected)


def canonical_remote_template_source(raw: Any) -> RemoteTemplateSource:
    """Canonicalize only a server-reloaded remote ``app.build_templates`` row."""

    if type(raw) is not dict:
        raise _error("INVALID_SOURCE", "source")
    if raw.get("remote") is not True:
        raise _error("REMOTE_SOURCE_REQUIRED", "source.remote")
    if raw.get("templateType") != "gear":
        raise _error("GEAR_TEMPLATE_REQUIRED", "source.templateType")
    owner_id = _uuid(raw.get("ownerId"), path="source.ownerId")
    template_id = _uuid(raw.get("templateId"), path="source.templateId")
    config_hash = _identity(raw.get("configHash"), path="source.configHash")
    if _CONFIG_HASH.fullmatch(config_hash) is None:
        raise _error("INVALID_CONFIG_HASH", "source.configHash")
    raw_string = raw.get("rawString")
    if type(raw_string) is not str or not raw_string or len(raw_string.encode("utf-8")) > 20_000:
        raise _error("INVALID_RAW_STRING", "source.rawString")
    metadata = raw.get("metadata")
    if type(metadata) is not dict:
        raise _error("INVALID_METADATA", "source.metadata")
    selection, issues = parse_selection_intent(metadata.get("selectionIntent"))
    if selection is None or issues:
        raise _error("INVALID_SELECTION_INTENT", "source.metadata.selectionIntent")
    _ordered_source_slots(selection)
    selection_sig = selection_signature(selection, selection["eligibilityContext"])
    payload_hash = "sha256:" + hashlib.sha256(canonical_json_bytes({
        "templateId": template_id,
        "templateConfigHash": config_hash,
        "rawString": raw_string,
        "selectionIntent": selection,
    })).hexdigest()
    return RemoteTemplateSource(
        owner_key_hash=_source_owner_hash(owner_id),
        template_id=template_id,
        template_config_hash=config_hash,
        source_payload_hash=payload_hash,
        selection_signature=selection_sig,
        selection_intent=selection,
    )


def _pair(raw: object, path: str) -> dict[str, str]:
    try:
        pair = canonical_mapping(raw, path=path, exact_keys=_PAIR_KEYS)
        slot = canonical_slot(pair["slot"], path=f"{path}.slot")
    except CanonicalValueError as error:
        raise _error(error.code, path) from error
    key = _identity(pair["exactAuthorityEnvelopeKey"], path=f"{path}.exactAuthorityEnvelopeKey")
    if _ENVELOPE_KEY.fullmatch(key) is None:
        raise _error("INVALID_EXACT_AUTHORITY_ENVELOPE", f"{path}.exactAuthorityEnvelopeKey")
    return {"slot": slot, "exactAuthorityEnvelopeKey": key}


def _binding_payload(value: object) -> dict[str, Any]:
    try:
        raw = canonical_mapping(value, path="binding", exact_keys=_BINDING_KEYS)
        schema = canonical_identity_token(raw["schemaRevision"], path="binding.schemaRevision")
        source = canonical_mapping(raw["source"], path="binding.source", exact_keys=_SOURCE_KEYS)
        authority = canonical_mapping(raw["authority"], path="binding.authority", exact_keys=_AUTHORITY_KEYS)
        pairs = canonical_ordered_list(
            raw["exactAuthorityBySlot"],
            path="binding.exactAuthorityBySlot",
            item_rule=_pair,
            max_items=len(EXACT_LOADOUT_CORE_SLOTS) + 1,
        )
    except CanonicalValueError as error:
        raise _error(error.code, error.path) from error
    if schema != EXACT_TEMPLATE_AUTHORITY_BINDING_SCHEMA_REVISION:
        raise _error("SCHEMA_REVISION_MISMATCH", "binding.schemaRevision")
    normalized_source = {
        "ownerKeyHash": _sha256(source["ownerKeyHash"], path="binding.source.ownerKeyHash"),
        "templateId": _uuid(source["templateId"], path="binding.source.templateId"),
        "templateConfigHash": _identity(source["templateConfigHash"], path="binding.source.templateConfigHash"),
        "sourcePayloadHash": _sha256(source["sourcePayloadHash"], path="binding.source.sourcePayloadHash"),
        "selectionSignature": _sha256(source["selectionSignature"], path="binding.source.selectionSignature"),
    }
    if _CONFIG_HASH.fullmatch(normalized_source["templateConfigHash"]) is None:
        raise _error("INVALID_CONFIG_HASH", "binding.source.templateConfigHash")
    normalized_authority = {
        key: _identity(authority[key], path=f"binding.authority.{key}")
        for key in (
            "gearExactRegistryRevision",
            "gearRuleRevision",
            "resolverRevision",
            "simcRuntimeRevision",
        )
    }
    normalized_authority["templateAuthorityIdentity"] = _sha256(
        authority["templateAuthorityIdentity"],
        path="binding.authority.templateAuthorityIdentity",
    )
    normalized_authority["templateContentHash"] = _sha256(
        authority["templateContentHash"],
        path="binding.authority.templateContentHash",
    )
    normalized_pairs = list(pairs)
    slots = [pair["slot"] for pair in normalized_pairs]
    keys = [pair["exactAuthorityEnvelopeKey"] for pair in normalized_pairs]
    if not slots or len(slots) != len(set(slots)) or len(keys) != len(set(keys)):
        raise _error("EXACT_AUTHORITY_CLOSURE_AMBIGUOUS", "binding.exactAuthorityBySlot")
    if slots != sorted(slots, key=lambda slot: (*EXACT_LOADOUT_CORE_SLOTS, "off_hand").index(slot)):
        raise _error("EXACT_AUTHORITY_SLOT_ORDER_INVALID", "binding.exactAuthorityBySlot")
    return {
        "schemaRevision": schema,
        "source": normalized_source,
        "authority": normalized_authority,
        "exactAuthorityBySlot": normalized_pairs,
    }


def _admission_payload(
    source: RemoteTemplateSource,
    proof: Any,
) -> dict[str, Any]:
    if type(source) is not RemoteTemplateSource:
        raise _error("REMOTE_TEMPLATE_SOURCE_REQUIRED", "source")
    if type(proof) is not dict:
        raise _error("INVALID_ADMISSION_PROOF", "proof")
    expected = set(_AUTHORITY_KEYS) | {"exactAuthorityBySlot"}
    if set(proof) != expected:
        raise _error("ADMISSION_PROOF_KEY_SET_MISMATCH", "proof")
    payload = _binding_payload({
        "schemaRevision": EXACT_TEMPLATE_AUTHORITY_BINDING_SCHEMA_REVISION,
        "source": {
            "ownerKeyHash": source.owner_key_hash,
            "templateId": source.template_id,
            "templateConfigHash": source.template_config_hash,
            "sourcePayloadHash": source.source_payload_hash,
            "selectionSignature": source.selection_signature,
        },
        "authority": {key: proof[key] for key in _AUTHORITY_KEYS},
        "exactAuthorityBySlot": proof["exactAuthorityBySlot"],
    })
    expected_slots = list(_ordered_source_slots(source.selection_intent))
    actual_slots = [pair["slot"] for pair in payload["exactAuthorityBySlot"]]
    if actual_slots != expected_slots:
        raise _error("EXACT_AUTHORITY_SLOT_CLOSURE_INVALID", "proof.exactAuthorityBySlot")
    return payload


def seal_exact_template_authority_binding(
    source: RemoteTemplateSource,
    proof: Any,
) -> SealedCanonicalDocument:
    """Seal one already-proven source-to-bundle closure without any discovery."""

    try:
        payload = _admission_payload(source, proof)
        return seal_canonical_document(
            document_kind=EXACT_TEMPLATE_AUTHORITY_BINDING_DOCUMENT_KIND,
            schema_revision=EXACT_TEMPLATE_AUTHORITY_BINDING_SCHEMA_REVISION,
            payload=payload,
            key_prefix=EXACT_TEMPLATE_AUTHORITY_BINDING_KEY_PREFIX,
        )
    except ExactTemplateAuthorityBindingError:
        raise
    except CanonicalValueError as error:
        raise _error(error.code, error.path) from error


def reload_exact_template_authority_binding(
    binding_key: Any,
    canonical_bytes: Any,
) -> SealedCanonicalDocument:
    """Rehydrate exact binding bytes and key before any later materialization."""

    try:
        return _rehydrate_canonical_document(
            canonical_bytes=canonical_bytes,
            content_key=binding_key,
            document_kind=EXACT_TEMPLATE_AUTHORITY_BINDING_DOCUMENT_KIND,
            schema_revision=EXACT_TEMPLATE_AUTHORITY_BINDING_SCHEMA_REVISION,
            key_prefix=EXACT_TEMPLATE_AUTHORITY_BINDING_KEY_PREFIX,
            payload_validator=_binding_payload,
        )
    except (CanonicalValueError, ExactTemplateAuthorityBindingError) as error:
        raise _error("INVALID_EXACT_TEMPLATE_AUTHORITY_BINDING", "binding") from error


def exact_template_authority_binding_payload(
    document: Any,
) -> dict[str, Any]:
    try:
        return _binding_payload(verified_payload_copy(
            document,
            document_kind=EXACT_TEMPLATE_AUTHORITY_BINDING_DOCUMENT_KIND,
            schema_revision=EXACT_TEMPLATE_AUTHORITY_BINDING_SCHEMA_REVISION,
            key_prefix=EXACT_TEMPLATE_AUTHORITY_BINDING_KEY_PREFIX,
            payload_validator=_binding_payload,
        ))
    except (CanonicalValueError, ExactTemplateAuthorityBindingError) as error:
        raise _error("INVALID_EXACT_TEMPLATE_AUTHORITY_BINDING", "binding") from error


def binding_matches_remote_template_source(
    document: Any,
    source: RemoteTemplateSource,
) -> bool:
    """Check binding/source equality; callers must still reload bundle closure."""

    if type(source) is not RemoteTemplateSource:
        return False
    try:
        saved = exact_template_authority_binding_payload(document)["source"]
    except ExactTemplateAuthorityBindingError:
        return False
    return saved == {
        "ownerKeyHash": source.owner_key_hash,
        "templateId": source.template_id,
        "templateConfigHash": source.template_config_hash,
        "sourcePayloadHash": source.source_payload_hash,
        "selectionSignature": source.selection_signature,
    }


__all__ = (
    "EXACT_TEMPLATE_AUTHORITY_BINDING_DOCUMENT_KIND",
    "EXACT_TEMPLATE_AUTHORITY_BINDING_KEY_PREFIX",
    "EXACT_TEMPLATE_AUTHORITY_BINDING_SCHEMA_REVISION",
    "ExactTemplateAuthorityBindingError",
    "RemoteTemplateSource",
    "binding_matches_remote_template_source",
    "canonical_remote_template_source",
    "exact_template_authority_binding_payload",
    "owner_key_hash_for_user_id",
    "reload_exact_template_authority_binding",
    "seal_exact_template_authority_binding",
)

#!/usr/bin/env python3
"""Strict, cross-bound authority envelope for one ready Exact item."""

from __future__ import annotations

try:
    from .gear_canonical_kernel import (
        CanonicalIssue,
        CanonicalResult,
        CanonicalValueError,
        SealedCanonicalDocument,
        _rehydrate_canonical_document,
        canonical_identity_token,
        canonical_int,
        canonical_json_bytes,
        canonical_mapping,
        canonical_set_list,
        canonical_slot,
        seal_canonical_document,
        verified_payload_copy,
    )
    from .gear_exact_item_instance import (
        EXACT_ITEM_DOCUMENT_KIND,
        EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
        EXACT_ITEM_KEY_PREFIX,
        EXACT_STATIC_FACTS_DOCUMENT_KIND,
        EXACT_STATIC_FACTS_KEY_PREFIX,
        EXACT_STATIC_FACTS_SCHEMA_REVISION,
        _validate_exact_item_payload,
        _validate_exact_static_facts_payload,
        _verified_exact_payload_copy,
        seal_exact_static_facts,
    )
    from .gear_track_authority import resolve_exact_instance_progression
    from .simc_item_effect_support import (
        EFFECT_AGGREGATE_DOCUMENT_KIND,
        EFFECT_AGGREGATE_KEY_PREFIX,
        EFFECT_SUPPORT_SCHEMA_REVISION,
        _validate_effect_aggregate_payload,
    )
except ImportError:
    from gear_canonical_kernel import (
        CanonicalIssue,
        CanonicalResult,
        CanonicalValueError,
        SealedCanonicalDocument,
        _rehydrate_canonical_document,
        canonical_identity_token,
        canonical_int,
        canonical_json_bytes,
        canonical_mapping,
        canonical_set_list,
        canonical_slot,
        seal_canonical_document,
        verified_payload_copy,
    )
    from gear_exact_item_instance import (
        EXACT_ITEM_DOCUMENT_KIND,
        EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
        EXACT_ITEM_KEY_PREFIX,
        EXACT_STATIC_FACTS_DOCUMENT_KIND,
        EXACT_STATIC_FACTS_KEY_PREFIX,
        EXACT_STATIC_FACTS_SCHEMA_REVISION,
        _validate_exact_item_payload,
        _validate_exact_static_facts_payload,
        _verified_exact_payload_copy,
        seal_exact_static_facts,
    )
    from gear_track_authority import resolve_exact_instance_progression
    from simc_item_effect_support import (
        EFFECT_AGGREGATE_DOCUMENT_KIND,
        EFFECT_AGGREGATE_KEY_PREFIX,
        EFFECT_SUPPORT_SCHEMA_REVISION,
        _validate_effect_aggregate_payload,
    )


_SEALED_PROGRESSION_DOCUMENT_KIND = "exact_progression"
_SEALED_PROGRESSION_SCHEMA_REVISION = "exact-progression-binding-v1"
_SEALED_PROGRESSION_KEY_PREFIX = "exact-progression:sha256:"
_SEALED_PROGRESSION_PAYLOAD_KEYS = frozenset({
    "schemaRevision", "exactItemInstanceKey", "gearRuleRevision",
    "trackAuthorityRuleRevision", "trackAuthorityRecordKey",
    "trackAuthorityInput", "progressionState",
})
_SEALED_TRACK_AUTHORITY_INPUT_KEYS = frozenset({
    "seasonRevision", "gearRuleRevision", "rowFamily", "status", "itemId",
    "variantKey", "itemLevel", "bonusIds", "slot", "hasCraftedSource",
})
_SEALED_AUTHORITY_DOCUMENT_KIND = "exact_authority"
_SEALED_AUTHORITY_SCHEMA_REVISION = "exact-authority-envelope-v1"
_SEALED_AUTHORITY_KEY_PREFIX = "exact-authority:sha256:"


def _canonical_progression_identifier(value: object, path: str) -> str:
    return canonical_identity_token(value, path=path)


def _validate_exact_progression_payload(
    value: object,
    *,
    exact: SealedCanonicalDocument,
) -> object:
    """Rebuild decoded progression bytes against one verified sealed Exact."""

    exact_payload = _verified_exact_payload_copy(exact)
    payload = canonical_mapping(
        value,
        path="exactProgression",
        exact_keys=_SEALED_PROGRESSION_PAYLOAD_KEYS,
    )
    if payload["schemaRevision"] != _SEALED_PROGRESSION_SCHEMA_REVISION:
        raise CanonicalValueError(
            "SCHEMA_REVISION_MISMATCH", "exactProgression.schemaRevision",
        )
    if payload["exactItemInstanceKey"] != exact.content_key:
        raise CanonicalValueError(
            "EXACT_ITEM_BINDING_MISMATCH",
            "exactProgression.exactItemInstanceKey",
        )
    gear_rule_revision = canonical_identity_token(
        payload["gearRuleRevision"],
        path="exactProgression.gearRuleRevision",
    )
    track_rule_revision = canonical_identity_token(
        payload["trackAuthorityRuleRevision"],
        path="exactProgression.trackAuthorityRuleRevision",
    )
    track_record_key = canonical_identity_token(
        payload["trackAuthorityRecordKey"],
        path="exactProgression.trackAuthorityRecordKey",
    )
    authority = canonical_mapping(
        payload["trackAuthorityInput"],
        path="exactProgression.trackAuthorityInput",
        exact_keys=_SEALED_TRACK_AUTHORITY_INPUT_KEYS,
    )
    season_revision = canonical_identity_token(
        authority["seasonRevision"],
        path="exactProgression.trackAuthorityInput.seasonRevision",
    )
    authority_rule_revision = canonical_identity_token(
        authority["gearRuleRevision"],
        path="exactProgression.trackAuthorityInput.gearRuleRevision",
    )
    row_family = canonical_identity_token(
        authority["rowFamily"],
        path="exactProgression.trackAuthorityInput.rowFamily",
    )
    status = canonical_identity_token(
        authority["status"],
        path="exactProgression.trackAuthorityInput.status",
    )
    item_id = canonical_identity_token(
        authority["itemId"],
        path="exactProgression.trackAuthorityInput.itemId",
    )
    variant_key = canonical_identity_token(
        authority["variantKey"],
        path="exactProgression.trackAuthorityInput.variantKey",
    )
    item_level = canonical_int(
        authority["itemLevel"],
        path="exactProgression.trackAuthorityInput.itemLevel",
        minimum=1,
        maximum=9999,
    )
    bonus_ids = canonical_set_list(
        authority["bonusIds"],
        path="exactProgression.trackAuthorityInput.bonusIds",
        item_rule=_canonical_progression_identifier,
        max_items=256,
    )
    slot = canonical_slot(
        authority["slot"],
        path="exactProgression.trackAuthorityInput.slot",
    )
    if type(authority["hasCraftedSource"]) is not bool:
        raise CanonicalValueError(
            "INVALID_BOOLEAN",
            "exactProgression.trackAuthorityInput.hasCraftedSource",
        )
    has_crafted_source = authority["hasCraftedSource"]
    if row_family != "exact_instance" or status != "verified":
        raise CanonicalValueError(
            "INVALID_TRACK_AUTHORITY_INPUT",
            "exactProgression.trackAuthorityInput",
        )
    if gear_rule_revision != authority_rule_revision:
        raise CanonicalValueError(
            "GEAR_RULE_REVISION_MISMATCH",
            "exactProgression.gearRuleRevision",
        )
    if (
        item_id != exact_payload["itemId"]
        or variant_key != exact.content_key
        or item_level != exact_payload["itemLevel"]
        or list(bonus_ids) != exact_payload["bonusIds"]
    ):
        raise CanonicalValueError(
            "EXACT_ITEM_BINDING_MISMATCH",
            "exactProgression.trackAuthorityInput",
        )
    canonical_input = {
        "seasonRevision": season_revision,
        "gearRuleRevision": authority_rule_revision,
        "rowFamily": row_family,
        "status": status,
        "itemId": item_id,
        "variantKey": variant_key,
        "itemLevel": item_level,
        "bonusIds": list(bonus_ids),
        "slot": slot,
        "hasCraftedSource": has_crafted_source,
    }
    if dict(authority) != canonical_input:
        raise CanonicalValueError(
            "TRACK_AUTHORITY_INPUT_MISMATCH",
            "exactProgression.trackAuthorityInput",
        )
    resolved = resolve_exact_instance_progression(
        {
            "seasonRevision": season_revision,
            "gearRuleRevision": authority_rule_revision,
        },
        canonical_input,
    )
    if resolved.get("status") != "verified":
        raise CanonicalValueError(
            "TRACK_AUTHORITY_BLOCKED",
            "exactProgression.trackAuthorityInput",
        )
    if track_rule_revision != resolved.get("ruleRevision"):
        raise CanonicalValueError(
            "TRACK_AUTHORITY_RULE_MISMATCH",
            "exactProgression.trackAuthorityRuleRevision",
        )
    if track_record_key != resolved.get("recordKey"):
        raise CanonicalValueError(
            "TRACK_AUTHORITY_RECORD_MISMATCH",
            "exactProgression.trackAuthorityRecordKey",
        )
    if canonical_json_bytes(payload["progressionState"]) != canonical_json_bytes(
        resolved.get("progressionState")
    ):
        raise CanonicalValueError(
            "TRACK_AUTHORITY_STATE_MISMATCH",
            "exactProgression.progressionState",
        )
    return value


def _blocked_progression(error: CanonicalValueError) -> CanonicalResult:
    return CanonicalResult(
        "blocked",
        None,
        (CanonicalIssue(
            error.code,
            error.path,
            "Re-import the exact item and use the current canonical progression inputs.",
        ),),
    )


def seal_exact_progression(
    exact: SealedCanonicalDocument,
    *,
    season_revision: str,
    gear_rule_revision: str,
    slot: str,
    has_crafted_source: bool,
) -> CanonicalResult:
    """Seal only the progression state returned by production Track Authority."""

    try:
        canonical_slot_value = canonical_slot(slot, path="exactProgression.slot")
        canonical_season_revision = canonical_identity_token(
            season_revision, path="exactProgression.seasonRevision",
        )
        canonical_gear_rule_revision = canonical_identity_token(
            gear_rule_revision, path="exactProgression.gearRuleRevision",
        )
        if type(has_crafted_source) is not bool:
            raise CanonicalValueError(
                "INVALID_BOOLEAN", "exactProgression.hasCraftedSource",
            )
        exact_payload = _verified_exact_payload_copy(exact)
        authority_input = {
            "seasonRevision": canonical_season_revision,
            "gearRuleRevision": canonical_gear_rule_revision,
            "rowFamily": "exact_instance",
            "status": "verified",
            "itemId": exact_payload["itemId"],
            "variantKey": exact.content_key,
            "itemLevel": exact_payload["itemLevel"],
            "bonusIds": list(exact_payload["bonusIds"]),
            "slot": canonical_slot_value,
            "hasCraftedSource": has_crafted_source,
        }
        resolved = resolve_exact_instance_progression(
            {
                "seasonRevision": canonical_season_revision,
                "gearRuleRevision": canonical_gear_rule_revision,
            },
            authority_input,
        )
        if resolved.get("status") != "verified":
            issues = tuple(
                CanonicalIssue(
                    problem.get("code")
                    if type(problem.get("code")) is str
                    else "TRACK_AUTHORITY_BLOCKED",
                    "exactProgression.trackAuthorityInput",
                    "Choose an exact item with verified current-season progression evidence.",
                )
                for problem in resolved.get("problems", ())
                if type(problem) is dict
            )
            return CanonicalResult(
                "blocked",
                None,
                issues or (CanonicalIssue(
                    "TRACK_AUTHORITY_BLOCKED",
                    "exactProgression.trackAuthorityInput",
                    "Choose an exact item with verified current-season progression evidence.",
                ),),
            )
        payload = {
            "schemaRevision": _SEALED_PROGRESSION_SCHEMA_REVISION,
            "exactItemInstanceKey": exact.content_key,
            "gearRuleRevision": canonical_gear_rule_revision,
            "trackAuthorityRuleRevision": resolved["ruleRevision"],
            "trackAuthorityRecordKey": resolved["recordKey"],
            "trackAuthorityInput": authority_input,
            "progressionState": resolved["progressionState"],
        }
        _validate_exact_progression_payload(payload, exact=exact)
        document = seal_canonical_document(
            document_kind=_SEALED_PROGRESSION_DOCUMENT_KIND,
            schema_revision=_SEALED_PROGRESSION_SCHEMA_REVISION,
            payload=payload,
            key_prefix=_SEALED_PROGRESSION_KEY_PREFIX,
        )
        return CanonicalResult("verified", document, ())
    except CanonicalValueError as error:
        return _blocked_progression(error)


def reload_exact_progression(
    canonical_bytes: bytes,
    content_key: str,
    *,
    exact: SealedCanonicalDocument,
) -> SealedCanonicalDocument:
    """Reload progression and replay production Track Authority."""

    return _rehydrate_canonical_document(
        canonical_bytes=canonical_bytes,
        content_key=content_key,
        document_kind=_SEALED_PROGRESSION_DOCUMENT_KIND,
        schema_revision=_SEALED_PROGRESSION_SCHEMA_REVISION,
        key_prefix=_SEALED_PROGRESSION_KEY_PREFIX,
        payload_validator=lambda payload: _validate_exact_progression_payload(
            payload,
            exact=exact,
        ),
    )


def _blocked_exact_authority(error: CanonicalValueError) -> CanonicalResult:
    return CanonicalResult(
        "blocked",
        None,
        (CanonicalIssue(
            error.code,
            error.path,
            "Rebuild every authority document from the same sealed Exact item.",
        ),),
    )


def _validate_effect_aggregate_for_envelope(
    value: object,
    *,
    exact: SealedCanonicalDocument,
) -> object:
    runtime_revision = (
        value.get("simcRuntimeRevision")
        if type(value) is dict
        else None
    )
    return _validate_effect_aggregate_payload(
        value,
        exact=exact,
        runtime_revision=runtime_revision,
    )


def seal_exact_authority_envelope(
    *,
    exact: SealedCanonicalDocument,
    static_facts: SealedCanonicalDocument,
    progression: SealedCanonicalDocument,
    effect_support: SealedCanonicalDocument,
    resolver_revision: str,
) -> CanonicalResult:
    """Compose four independently re-verified Exact-bound documents."""

    documents = {
        "exact": exact,
        "static_facts": static_facts,
        "progression": progression,
        "effect_support": effect_support,
    }
    for field, document in documents.items():
        if type(document) is not SealedCanonicalDocument:
            raise TypeError(f"{field} must be an exact SealedCanonicalDocument.")

    try:
        verified_payload_copy(
            exact,
            document_kind=EXACT_ITEM_DOCUMENT_KIND,
            schema_revision=EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
            key_prefix=EXACT_ITEM_KEY_PREFIX,
            payload_validator=_validate_exact_item_payload,
        )
        static_payload = verified_payload_copy(
            static_facts,
            document_kind=EXACT_STATIC_FACTS_DOCUMENT_KIND,
            schema_revision=EXACT_STATIC_FACTS_SCHEMA_REVISION,
            key_prefix=EXACT_STATIC_FACTS_KEY_PREFIX,
            payload_validator=_validate_exact_static_facts_payload,
        )
        progression_payload = verified_payload_copy(
            progression,
            document_kind=_SEALED_PROGRESSION_DOCUMENT_KIND,
            schema_revision=_SEALED_PROGRESSION_SCHEMA_REVISION,
            key_prefix=_SEALED_PROGRESSION_KEY_PREFIX,
            payload_validator=lambda payload: _validate_exact_progression_payload(
                payload,
                exact=exact,
            ),
        )
        effect_payload = verified_payload_copy(
            effect_support,
            document_kind=EFFECT_AGGREGATE_DOCUMENT_KIND,
            schema_revision=EFFECT_SUPPORT_SCHEMA_REVISION,
            key_prefix=EFFECT_AGGREGATE_KEY_PREFIX,
            payload_validator=lambda payload: _validate_effect_aggregate_for_envelope(
                payload,
                exact=exact,
            ),
        )
        exact_key = exact.content_key
        for payload, path in (
            (static_payload, "exactAuthority.staticFacts"),
            (progression_payload, "exactAuthority.progression"),
            (effect_payload, "exactAuthority.effectSupport"),
        ):
            if payload["exactItemInstanceKey"] != exact_key:
                raise CanonicalValueError(
                    "EXACT_ITEM_BINDING_MISMATCH",
                    f"{path}.exactItemInstanceKey",
                )
        if effect_payload["status"] != "verified":
            raise CanonicalValueError(
                "EFFECT_SUPPORT_NOT_VERIFIED",
                "exactAuthority.effectSupport.status",
            )
        resolver = canonical_identity_token(
            resolver_revision,
            path="exactAuthority.resolverRevision",
        )
        document = seal_canonical_document(
            document_kind=_SEALED_AUTHORITY_DOCUMENT_KIND,
            schema_revision=_SEALED_AUTHORITY_SCHEMA_REVISION,
            payload={
                "schemaRevision": _SEALED_AUTHORITY_SCHEMA_REVISION,
                "exactItemInstanceKey": exact_key,
                "staticFactsKey": static_facts.content_key,
                "progressionBindingKey": progression.content_key,
                "effectSupportKey": effect_support.content_key,
                "resolverRevision": resolver,
            },
            key_prefix=_SEALED_AUTHORITY_KEY_PREFIX,
        )
        return CanonicalResult("verified", document, ())
    except CanonicalValueError as error:
        return _blocked_exact_authority(error)


def reload_exact_authority_envelope(
    canonical_bytes: bytes,
    content_key: str,
    *,
    exact: SealedCanonicalDocument,
    static_facts: SealedCanonicalDocument,
    progression: SealedCanonicalDocument,
    effect_support: SealedCanonicalDocument,
    resolver_revision: str,
) -> SealedCanonicalDocument:
    """Reload an authority envelope only with its exact dependency closure."""

    _verified_exact_payload_copy(exact)
    static_payload = verified_payload_copy(
        static_facts,
        document_kind=EXACT_STATIC_FACTS_DOCUMENT_KIND,
        schema_revision=EXACT_STATIC_FACTS_SCHEMA_REVISION,
        key_prefix=EXACT_STATIC_FACTS_KEY_PREFIX,
        payload_validator=_validate_exact_static_facts_payload,
    )
    progression_payload = _validate_exact_progression_payload(
        verified_payload_copy(
            progression,
            document_kind=_SEALED_PROGRESSION_DOCUMENT_KIND,
            schema_revision=_SEALED_PROGRESSION_SCHEMA_REVISION,
            key_prefix=_SEALED_PROGRESSION_KEY_PREFIX,
            payload_validator=lambda payload: _validate_exact_progression_payload(
                payload, exact=exact,
            ),
        ),
        exact=exact,
    )
    effect_payload = verified_payload_copy(
        effect_support,
        document_kind=EFFECT_AGGREGATE_DOCUMENT_KIND,
        schema_revision=EFFECT_SUPPORT_SCHEMA_REVISION,
        key_prefix=EFFECT_AGGREGATE_KEY_PREFIX,
        payload_validator=lambda payload: _validate_effect_aggregate_for_envelope(
            payload, exact=exact,
        ),
    )
    resolver = canonical_identity_token(
        resolver_revision, path="exactAuthority.resolverRevision",
    )
    for payload, path in (
        (static_payload, "exactAuthority.staticFacts"),
        (progression_payload, "exactAuthority.progression"),
        (effect_payload, "exactAuthority.effectSupport"),
    ):
        if payload["exactItemInstanceKey"] != exact.content_key:
            raise CanonicalValueError(
                "EXACT_ITEM_BINDING_MISMATCH", f"{path}.exactItemInstanceKey",
            )
    if effect_payload["status"] != "verified":
        raise CanonicalValueError(
            "EFFECT_SUPPORT_NOT_VERIFIED", "exactAuthority.effectSupport.status",
        )

    def validate(value: object) -> object:
        payload = canonical_mapping(
            value,
            path="exactAuthority",
            exact_keys=frozenset({
                "schemaRevision", "exactItemInstanceKey", "staticFactsKey",
                "progressionBindingKey", "effectSupportKey", "resolverRevision",
            }),
        )
        rebuilt = {
            "schemaRevision": _SEALED_AUTHORITY_SCHEMA_REVISION,
            "exactItemInstanceKey": exact.content_key,
            "staticFactsKey": static_facts.content_key,
            "progressionBindingKey": progression.content_key,
            "effectSupportKey": effect_support.content_key,
            "resolverRevision": resolver,
        }
        if dict(payload) != rebuilt:
            raise CanonicalValueError(
                "EXACT_AUTHORITY_BINDING_MISMATCH", "exactAuthority",
            )
        return rebuilt

    return _rehydrate_canonical_document(
        canonical_bytes=canonical_bytes,
        content_key=content_key,
        document_kind=_SEALED_AUTHORITY_DOCUMENT_KIND,
        schema_revision=_SEALED_AUTHORITY_SCHEMA_REVISION,
        key_prefix=_SEALED_AUTHORITY_KEY_PREFIX,
        payload_validator=validate,
    )


__all__ = (
    "reload_exact_authority_envelope",
    "reload_exact_progression",
    "seal_exact_authority_envelope",
    "seal_exact_progression",
    "seal_exact_static_facts",
)

#!/usr/bin/env python3
"""Pure canonical ExactItemInstance and EnhancementSelection contracts.

The module owns identity and revision-bound validation only. It deliberately
does not access PostgreSQL, files, environment, clock, network, routes, or the
active Manifest pointer.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Iterable, Mapping

try:
    from .gear_canonical_kernel import (
        CanonicalIssue,
        CanonicalResult,
        CanonicalValueError,
        SealedCanonicalDocument,
        canonical_identity_token,
        canonical_int,
        canonical_json_bytes,
        canonical_mapping,
        canonical_ordered_list,
        canonical_set_list,
        seal_canonical_document,
        verified_payload_copy,
    )
    from .gear_track_authority import resolve_exact_instance_progression
except ImportError:
    from gear_canonical_kernel import (
        CanonicalIssue,
        CanonicalResult,
        CanonicalValueError,
        SealedCanonicalDocument,
        canonical_identity_token,
        canonical_int,
        canonical_json_bytes,
        canonical_mapping,
        canonical_ordered_list,
        canonical_set_list,
        seal_canonical_document,
        verified_payload_copy,
    )
    from gear_track_authority import resolve_exact_instance_progression


EXACT_ITEM_INSTANCE_SCHEMA_REVISION = "gear-exact-item-instance-v1"
EXACT_ITEM_IDENTITY_SCHEMA_REVISION = "gear-exact-item-instance-v2"
EXACT_ITEM_VALIDATION_SCHEMA_REVISION = "gear-exact-item-validation-v1"
ENHANCEMENT_SELECTION_SCHEMA_REVISION = "gear-enhancement-selection-v1"
EXACT_ITEM_DOCUMENT_KIND = "exact_item"
EXACT_ITEM_KEY_PREFIX = "exact-item-instance:sha256:"
EXACT_STATIC_FACTS_DOCUMENT_KIND = "exact_static_facts"
EXACT_STATIC_FACTS_SCHEMA_REVISION = "exact-static-facts-v1"
EXACT_STATIC_FACTS_KEY_PREFIX = "exact-static-facts:sha256:"
EXACT_STATIC_FACTS_MAX_COUNT = 128
EXACT_STATIC_FACTS_MAX_ABSOLUTE_NUMBER = (2 ** 53) - 1
EXACT_STATIC_FACTS_MAX_CANONICAL_BYTES = 64 * 1024

CATALOG_REVISION_PATTERN = re.compile(r"^gear-catalog:sha256:[0-9a-f]{64}$")
EXACT_ITEM_INSTANCE_KEY_PATTERN = re.compile(
    r"^exact-item-instance:sha256:[0-9a-f]{64}$"
)
EXACT_VARIANT_SIGNATURE_PATTERN = re.compile(
    r"^exact-variant:sha256:[0-9a-f]{64}$"
)
ENHANCEMENT_SELECTION_KEY_PATTERN = re.compile(
    r"^enhancement-selection:sha256:[0-9a-f]{64}$"
)

_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,256}$")
_NON_IDENTITY_CONTEXT_KEYS = {
    "checkedAt",
    "createdAt",
    "displayLabel",
    "displayName",
    "jobId",
    "logPath",
    "observedAt",
    "profileUrl",
    "sourceProfileUrl",
    "sourceUrl",
    "updatedAt",
    "url",
}
_EXACT_SLOT_INPUT_KEYS = frozenset({
    "itemId", "declaredItemLevel", "bonusIds", "context", "gemIds",
    "gemBonusIds", "gemItemLevels", "enchantId", "craftedStats",
    "embellishmentIds", "redirectedBaseStats",
})
_EXACT_ITEM_PAYLOAD_KEYS = frozenset({
    "schemaRevision", "itemId", "itemLevel", "bonusIds", "context",
    "gemIds", "gemBonusIds", "gemItemLevels", "enchantId",
    "craftedStats", "embellishmentIds", "redirectedBaseStats",
})
_EXACT_STATIC_FACTS_PAYLOAD_KEYS = frozenset({
    "schemaRevision", "exactItemInstanceKey", "facts",
})


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _hash(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0
    return parsed if parsed > 0 else 0


def _problem(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _canonical_context(value: Any) -> Any:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, bool):
        return None
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_context(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in _NON_IDENTITY_CONTEXT_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_context(item) for item in value]
    if isinstance(value, (str, int, float)):
        return str(value).strip() if isinstance(value, str) else value
    return None


def _raw_tokens(value: Any) -> list[str] | None:
    if value in (None, "", []):
        return []
    if isinstance(value, str):
        pieces = value.split("/")
    elif isinstance(value, (list, tuple)):
        pieces = list(value)
    else:
        return None
    result: list[str] = []
    for piece in pieces:
        if isinstance(piece, bool) or not isinstance(piece, (str, int)):
            return None
        token = str(piece).strip()
        if not token or not _TOKEN_PATTERN.fullmatch(token):
            return None
        result.append(token)
    return result


def _ordered_tokens(value: Any) -> list[str] | None:
    return _raw_tokens(value)


def _set_tokens(value: Any) -> list[str] | None:
    tokens = _raw_tokens(value)
    if tokens is None:
        return None
    return sorted(set(tokens))


def _strict_identifier(value: Any) -> str | None:
    if not isinstance(value, str) or value != value.strip():
        return None
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return None
    return value if _TOKEN_PATTERN.fullmatch(value) else None


def _strict_identifier_list(value: Any, *, ordered: bool) -> list[str] | None:
    if not isinstance(value, list):
        return None
    result: list[str] = []
    for raw_token in value:
        token = _strict_identifier(raw_token)
        if token is None:
            return None
        result.append(token)
    if ordered:
        return result
    canonical = sorted(set(result))
    return result if result == canonical else None


def _strict_level_list(value: Any) -> list[int] | None:
    if not isinstance(value, list):
        return None
    if any(type(level) is not int or not 1 <= level <= 9999 for level in value):
        return None
    return list(value)


def _strict_enchant(value: Any) -> str | None:
    if not isinstance(value, str) or value != value.strip():
        return None
    if not value:
        return ""
    pieces = value.split("/")
    if any(_strict_identifier(piece) is None for piece in pieces):
        return None
    return "/".join(pieces)


def _strict_v2_enhancement_selection(raw_selection: Any) -> dict[str, Any]:
    fields = frozenset({
        "gemIds", "gemBonusIds", "gemItemLevels", "enchantId",
        "craftedStats", "embellishmentIds",
    })
    if not isinstance(raw_selection, Mapping):
        return {
            "status": "blocked",
            "schemaRevision": ENHANCEMENT_SELECTION_SCHEMA_REVISION,
            "problemCodes": ["ENHANCEMENT_FIELDS_INVALID"],
            "problems": [_problem(
                "ENHANCEMENT_FIELDS_INVALID", "enhancement",
                "v2 enhancement must be one strict canonical object.",
            )],
        }
    raw = dict(raw_selection)
    if set(raw) != fields:
        return {
            "status": "blocked",
            "schemaRevision": ENHANCEMENT_SELECTION_SCHEMA_REVISION,
            "problemCodes": ["ENHANCEMENT_FIELDS_INVALID"],
            "problems": [_problem(
                "ENHANCEMENT_FIELDS_INVALID", "enhancement",
                "v2 enhancement fields and schema revision must be exact.",
            )],
        }

    gem_ids = _strict_identifier_list(raw.get("gemIds"), ordered=True)
    gem_bonus_ids = _strict_identifier_list(raw.get("gemBonusIds"), ordered=True)
    gem_item_levels = _strict_level_list(raw.get("gemItemLevels"))
    crafted_stats = _strict_identifier_list(raw.get("craftedStats"), ordered=False)
    embellishment_ids = _strict_identifier_list(raw.get("embellishmentIds"), ordered=False)
    enchant_id = _strict_enchant(raw.get("enchantId"))
    values = (
        (gem_ids, "gemIds"), (gem_bonus_ids, "gemBonusIds"),
        (gem_item_levels, "gemItemLevels"),
        (crafted_stats, "craftedStats"),
        (embellishment_ids, "embellishmentIds"),
        (enchant_id, "enchantId"),
    )
    problems = [
        _problem(
            "ENHANCEMENT_VALUE_NON_CANONICAL", f"enhancement.{field}",
            f"{field} must use its strict canonical v2 type and value bounds.",
        )
        for value, field in values if value is None
    ]
    if gem_ids is not None and gem_bonus_ids is not None and (
        gem_bonus_ids and len(gem_bonus_ids) != len(gem_ids)
    ):
        problems.append(_problem(
            "ENHANCEMENT_GEM_SEQUENCE_MISMATCH", "enhancement.gemBonusIds",
            "gemBonusIds must be empty or match gemIds cardinality.",
        ))
    if gem_ids is not None and gem_item_levels is not None and (
        gem_item_levels and len(gem_item_levels) != len(gem_ids)
    ):
        problems.append(_problem(
            "ENHANCEMENT_GEM_SEQUENCE_MISMATCH", "enhancement.gemItemLevels",
            "gemItemLevels must be empty or match gemIds cardinality.",
        ))
    if problems:
        return {
            "status": "blocked",
            "schemaRevision": ENHANCEMENT_SELECTION_SCHEMA_REVISION,
            "problemCodes": sorted({problem["code"] for problem in problems}),
            "problems": problems,
        }

    selection = _enhancement_identity({
        "gemIds": gem_ids, "gemBonusIds": gem_bonus_ids,
        "gemItemLevels": gem_item_levels, "enchantId": enchant_id,
        "craftedStats": crafted_stats, "embellishmentIds": embellishment_ids,
    })
    key = _hash("enhancement-selection:sha256:", selection)
    return {
        "status": "verified",
        "schemaRevision": ENHANCEMENT_SELECTION_SCHEMA_REVISION,
        "enhancementSelectionKey": key,
        "selection": selection,
        "rowHash": "sha256:" + hashlib.sha256(_canonical_bytes({
            "enhancementSelectionKey": key, "selection": selection,
        })).hexdigest(),
        "problemCodes": [],
        "problems": [],
    }


def _static_facts(value: Any) -> dict[str, int | float] | None:
    if not isinstance(value, Mapping) or not value:
        return None
    result: dict[str, int | float] = {}
    for raw_key, amount in value.items():
        key = _text(raw_key)
        if (
            not key
            or isinstance(amount, bool)
            or not isinstance(amount, (int, float))
        ):
            return None
        result[key] = amount
    return dict(sorted(result.items()))


def _enhancement_identity(selection: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schemaRevision": ENHANCEMENT_SELECTION_SCHEMA_REVISION,
        "gemIds": list(selection.get("gemIds") or []),
        "gemBonusIds": list(selection.get("gemBonusIds") or []),
        "gemItemLevels": list(selection.get("gemItemLevels") or []),
        "enchantId": _text(selection.get("enchantId")),
        "craftedStats": list(selection.get("craftedStats") or []),
        "embellishmentIds": list(selection.get("embellishmentIds") or []),
    }


def canonical_enhancement_selection(raw_selection: Any) -> dict[str, Any]:
    """Canonicalize one enhancement selection according to SimC field semantics."""

    raw = raw_selection if isinstance(raw_selection, Mapping) else {}
    problems: list[dict[str, str]] = []
    gem_ids = _ordered_tokens(raw.get("gemIds"))
    gem_bonus_ids = _ordered_tokens(raw.get("gemBonusIds"))
    gem_item_levels = _ordered_tokens(raw.get("gemItemLevels"))
    crafted_stats = _set_tokens(raw.get("craftedStats"))
    embellishment_ids = _set_tokens(raw.get("embellishmentIds"))

    for value, field in (
        (gem_ids, "gemIds"),
        (gem_bonus_ids, "gemBonusIds"),
        (gem_item_levels, "gemItemLevels"),
        (crafted_stats, "craftedStats"),
        (embellishment_ids, "embellishmentIds"),
    ):
        if value is None:
            problems.append(_problem(
                "ENHANCEMENT_TOKEN_SEQUENCE_MALFORMED",
                f"enhancement.{field}",
                f"{field} must be a bounded token sequence.",
            ))

    raw_enchant = raw.get("enchantId")
    enchant_tokens = _raw_tokens(raw_enchant)
    if enchant_tokens is None:
        problems.append(_problem(
            "ENHANCEMENT_SINGLE_VALUE_MALFORMED",
            "enhancement.enchantId",
            "enchantId must be an empty or slash-separated bounded token "
            "sequence.",
        ))
    enchant_id = "/".join(enchant_tokens or [])

    if gem_ids is not None and gem_bonus_ids is not None and (
        gem_bonus_ids and len(gem_bonus_ids) != len(gem_ids)
    ):
        problems.append(_problem(
            "ENHANCEMENT_GEM_SEQUENCE_MISMATCH",
            "enhancement.gemBonusIds",
            "gemBonusIds must be empty or match the ordered gemIds cardinality.",
        ))
    if gem_ids is not None and gem_item_levels is not None and (
        gem_item_levels and len(gem_item_levels) != len(gem_ids)
    ):
        problems.append(_problem(
            "ENHANCEMENT_GEM_SEQUENCE_MISMATCH",
            "enhancement.gemItemLevels",
            "gemItemLevels must be empty or match the ordered gemIds cardinality.",
        ))

    if problems:
        return {
            "status": "blocked",
            "schemaRevision": ENHANCEMENT_SELECTION_SCHEMA_REVISION,
            "problemCodes": sorted({problem["code"] for problem in problems}),
            "problems": problems,
        }

    selection = _enhancement_identity({
        "gemIds": gem_ids or [],
        "gemBonusIds": gem_bonus_ids or [],
        "gemItemLevels": gem_item_levels or [],
        "enchantId": enchant_id,
        "craftedStats": crafted_stats or [],
        "embellishmentIds": embellishment_ids or [],
    })
    key = _hash("enhancement-selection:sha256:", selection)
    return {
        "status": "verified",
        "schemaRevision": ENHANCEMENT_SELECTION_SCHEMA_REVISION,
        "enhancementSelectionKey": key,
        "selection": selection,
        "rowHash": "sha256:" + hashlib.sha256(_canonical_bytes({
            "enhancementSelectionKey": key,
            "selection": selection,
        })).hexdigest(),
        "problemCodes": [],
        "problems": [],
    }


def _enhancement_from_simc_options(value: Any) -> dict[str, Any]:
    options = value if isinstance(value, Mapping) else {}
    return {
        "gemIds": options.get("gem_id"),
        "gemBonusIds": options.get("gem_bonus_id"),
        "gemItemLevels": options.get("gem_ilevel"),
        "enchantId": options.get("enchant_id"),
        "craftedStats": options.get("crafted_stats"),
        "embellishmentIds": options.get("embellishment"),
    }


def _serializer_input(
    item_id: str,
    item_level: int,
    bonus_ids: Iterable[str],
    selection: Mapping[str, Any],
) -> dict[str, str]:
    result = {
        "id": item_id,
        "ilevel": str(item_level),
    }
    values = {
        "bonus_id": list(bonus_ids),
        "gem_id": list(selection.get("gemIds") or []),
        "gem_bonus_id": list(selection.get("gemBonusIds") or []),
        "gem_ilevel": list(selection.get("gemItemLevels") or []),
        "enchant_id": [_text(selection.get("enchantId"))]
        if _text(selection.get("enchantId"))
        else [],
        "crafted_stats": list(selection.get("craftedStats") or []),
        "embellishment": list(selection.get("embellishmentIds") or []),
    }
    for field, tokens in values.items():
        normalized = [str(token) for token in tokens if _text(token)]
        if normalized:
            result[field] = "/".join(normalized)
    return result


def _require_exact_mapping_keys(
    value: object,
    *,
    path: str,
    exact_keys: frozenset[str],
) -> Mapping[str, object]:
    if type(value) is not dict:
        raise CanonicalValueError("INVALID_MAPPING", path)
    if any(type(key) is not str for key in value):
        raise CanonicalValueError("NON_STRING_MAPPING_KEY", path)
    unknown = sorted(set(value).difference(exact_keys))
    if unknown:
        raise CanonicalValueError("UNKNOWN_FIELD", f"{path}.{unknown[0]}")
    missing = sorted(exact_keys.difference(value))
    if missing:
        raise CanonicalValueError("MISSING_FIELD", f"{path}.{missing[0]}")
    return canonical_mapping(value, path=path, exact_keys=exact_keys)


def _canonical_identifier_item(value: object, path: str) -> str:
    return canonical_identity_token(value, path=path)


def _canonical_level_item(value: object, path: str) -> int:
    return canonical_int(value, path=path, minimum=1, maximum=9999)


def _canonical_exact_slot_payload(
    exact_slot_payload: object,
    *,
    path: str = "exactSlot",
) -> dict[str, object]:
    raw = _require_exact_mapping_keys(
        exact_slot_payload,
        path=path,
        exact_keys=_EXACT_SLOT_INPUT_KEYS,
    )
    item_id = canonical_identity_token(raw["itemId"], path=f"{path}.itemId")
    item_level = canonical_int(
        raw["declaredItemLevel"],
        path=f"{path}.declaredItemLevel",
        minimum=1,
        maximum=9999,
    )
    bonus_ids = canonical_set_list(
        raw["bonusIds"], path=f"{path}.bonusIds",
        item_rule=_canonical_identifier_item, max_items=256,
    )
    context = canonical_identity_token(
        raw["context"], path=f"{path}.context", allow_empty=True,
    )
    gem_ids = canonical_ordered_list(
        raw["gemIds"], path=f"{path}.gemIds",
        item_rule=_canonical_identifier_item, max_items=16,
    )
    gem_bonus_ids = canonical_ordered_list(
        raw["gemBonusIds"], path=f"{path}.gemBonusIds",
        item_rule=_canonical_identifier_item, max_items=16,
    )
    gem_item_levels = canonical_ordered_list(
        raw["gemItemLevels"], path=f"{path}.gemItemLevels",
        item_rule=_canonical_level_item, max_items=16,
    )
    if gem_bonus_ids and len(gem_bonus_ids) != len(gem_ids):
        raise CanonicalValueError(
            "GEM_SEQUENCE_MISMATCH", f"{path}.gemBonusIds",
        )
    if gem_item_levels and len(gem_item_levels) != len(gem_ids):
        raise CanonicalValueError(
            "GEM_SEQUENCE_MISMATCH", f"{path}.gemItemLevels",
        )
    enchant_id = canonical_identity_token(
        raw["enchantId"], path=f"{path}.enchantId", allow_empty=True,
    )
    crafted_stats = canonical_set_list(
        raw["craftedStats"], path=f"{path}.craftedStats",
        item_rule=_canonical_identifier_item, max_items=16,
    )
    embellishment_ids = canonical_set_list(
        raw["embellishmentIds"], path=f"{path}.embellishmentIds",
        item_rule=_canonical_identifier_item, max_items=16,
    )
    redirected_base_stats = canonical_set_list(
        raw["redirectedBaseStats"], path=f"{path}.redirectedBaseStats",
        item_rule=_canonical_identifier_item, max_items=16,
    )
    return {
        "schemaRevision": EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
        "itemId": item_id,
        "itemLevel": item_level,
        "bonusIds": list(bonus_ids),
        "context": context,
        "gemIds": list(gem_ids),
        "gemBonusIds": list(gem_bonus_ids),
        "gemItemLevels": list(gem_item_levels),
        "enchantId": enchant_id,
        "craftedStats": list(crafted_stats),
        "embellishmentIds": list(embellishment_ids),
        "redirectedBaseStats": list(redirected_base_stats),
    }


def _validate_exact_item_payload(value: object) -> object:
    raw = _require_exact_mapping_keys(
        value,
        path="exactItem",
        exact_keys=_EXACT_ITEM_PAYLOAD_KEYS,
    )
    if raw["schemaRevision"] != EXACT_ITEM_IDENTITY_SCHEMA_REVISION:
        raise CanonicalValueError(
            "SCHEMA_REVISION_MISMATCH", "exactItem.schemaRevision",
        )
    rebuilt = _canonical_exact_slot_payload(
        {
            "itemId": raw["itemId"],
            "declaredItemLevel": raw["itemLevel"],
            "bonusIds": raw["bonusIds"],
            "context": raw["context"],
            "gemIds": raw["gemIds"],
            "gemBonusIds": raw["gemBonusIds"],
            "gemItemLevels": raw["gemItemLevels"],
            "enchantId": raw["enchantId"],
            "craftedStats": raw["craftedStats"],
            "embellishmentIds": raw["embellishmentIds"],
            "redirectedBaseStats": raw["redirectedBaseStats"],
        },
        path="exactItem",
    )
    if dict(raw) != rebuilt:
        raise CanonicalValueError("EXACT_ITEM_PAYLOAD_MISMATCH", "exactItem")
    return rebuilt


def _verified_exact_payload_copy(exact: object) -> dict[str, object]:
    return verified_payload_copy(
        exact,
        document_kind=EXACT_ITEM_DOCUMENT_KIND,
        schema_revision=EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
        key_prefix=EXACT_ITEM_KEY_PREFIX,
        payload_validator=_validate_exact_item_payload,
    )


def _canonical_exact_static_facts(
    facts: object,
    *,
    path: str = "exactStaticFacts.facts",
) -> dict[str, int | float]:
    if type(facts) is not dict:
        raise CanonicalValueError("INVALID_MAPPING", path)
    if not facts:
        raise CanonicalValueError("STATIC_FACTS_REQUIRED", path)
    if len(facts) > EXACT_STATIC_FACTS_MAX_COUNT:
        raise CanonicalValueError("STATIC_FACT_COUNT_BOUNDS", path)
    result: dict[str, int | float] = {}
    for raw_key, raw_amount in facts.items():
        key = canonical_identity_token(raw_key, path=f"{path}.key")
        amount_path = f"{path}.{key}"
        if type(raw_amount) not in {int, float}:
            raise CanonicalValueError("INVALID_STATIC_FACT_NUMBER", amount_path)
        if type(raw_amount) is int:
            if abs(raw_amount) > EXACT_STATIC_FACTS_MAX_ABSOLUTE_NUMBER:
                raise CanonicalValueError("STATIC_FACT_NUMBER_BOUNDS", amount_path)
        else:
            if not math.isfinite(raw_amount):
                raise CanonicalValueError("INVALID_STATIC_FACT_NUMBER", amount_path)
            if abs(raw_amount) > EXACT_STATIC_FACTS_MAX_ABSOLUTE_NUMBER:
                raise CanonicalValueError("STATIC_FACT_NUMBER_BOUNDS", amount_path)
            if raw_amount.is_integer():
                raise CanonicalValueError(
                    "AMBIGUOUS_INTEGRAL_STATIC_FACT_FLOAT",
                    amount_path,
                )
        result[key] = raw_amount
    return result


def _bounded_exact_static_facts_payload(value: object) -> None:
    try:
        encoded = canonical_json_bytes(value)
    except (ValueError, OverflowError) as error:
        raise CanonicalValueError(
            "STATIC_FACTS_SERIALIZATION_INVALID",
            "exactStaticFacts",
        ) from error
    if len(encoded) > EXACT_STATIC_FACTS_MAX_CANONICAL_BYTES:
        raise CanonicalValueError(
            "STATIC_FACTS_PAYLOAD_BOUNDS",
            "exactStaticFacts",
        )


def _validate_exact_static_facts_payload(value: object) -> object:
    if type(value) is not dict:
        raise CanonicalValueError("INVALID_MAPPING", "exactStaticFacts")
    canonical_facts = _canonical_exact_static_facts(value.get("facts"))
    _bounded_exact_static_facts_payload(value)
    raw = canonical_mapping(
        value,
        path="exactStaticFacts",
        exact_keys=_EXACT_STATIC_FACTS_PAYLOAD_KEYS,
    )
    if raw["schemaRevision"] != EXACT_STATIC_FACTS_SCHEMA_REVISION:
        raise CanonicalValueError(
            "SCHEMA_REVISION_MISMATCH",
            "exactStaticFacts.schemaRevision",
        )
    exact_key = canonical_identity_token(
        raw["exactItemInstanceKey"],
        path="exactStaticFacts.exactItemInstanceKey",
    )
    if EXACT_ITEM_INSTANCE_KEY_PATTERN.fullmatch(exact_key) is None:
        raise CanonicalValueError(
            "INVALID_EXACT_ITEM_KEY",
            "exactStaticFacts.exactItemInstanceKey",
        )
    rebuilt = {
        "schemaRevision": EXACT_STATIC_FACTS_SCHEMA_REVISION,
        "exactItemInstanceKey": exact_key,
        "facts": canonical_facts,
    }
    if dict(raw) != rebuilt:
        raise CanonicalValueError(
            "STATIC_FACTS_PAYLOAD_MISMATCH",
            "exactStaticFacts",
        )
    return rebuilt


def _blocked_canonical_result(error: CanonicalValueError) -> CanonicalResult:
    return CanonicalResult(
        "blocked",
        None,
        (CanonicalIssue(
            error.code,
            error.path,
            "Re-import the exact slot without normalization or extra fields.",
        ),),
    )


def seal_exact_item(exact_slot_payload: object) -> CanonicalResult:
    """Seal exactly one canonical Task 1 v2 slot without Catalog provenance."""

    try:
        payload = _canonical_exact_slot_payload(exact_slot_payload)
        document = seal_canonical_document(
            document_kind=EXACT_ITEM_DOCUMENT_KIND,
            schema_revision=EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
            payload=payload,
            key_prefix=EXACT_ITEM_KEY_PREFIX,
        )
        return CanonicalResult("verified", document, ())
    except CanonicalValueError as error:
        return _blocked_canonical_result(error)


def seal_exact_static_facts(
    exact: SealedCanonicalDocument,
    facts: object,
) -> CanonicalResult:
    """Seal strict finite numeric facts against one re-verified Exact."""

    try:
        _verified_exact_payload_copy(exact)
        payload = {
            "schemaRevision": EXACT_STATIC_FACTS_SCHEMA_REVISION,
            "exactItemInstanceKey": exact.content_key,
            "facts": facts,
        }
        canonical_payload = _validate_exact_static_facts_payload(payload)
        document = seal_canonical_document(
            document_kind=EXACT_STATIC_FACTS_DOCUMENT_KIND,
            schema_revision=EXACT_STATIC_FACTS_SCHEMA_REVISION,
            payload=canonical_payload,
            key_prefix=EXACT_STATIC_FACTS_KEY_PREFIX,
        )
        return CanonicalResult("verified", document, ())
    except CanonicalValueError as error:
        return CanonicalResult(
            "blocked",
            None,
            (CanonicalIssue(
                error.code,
                error.path,
                "Re-resolve finite numeric facts for the sealed Exact item.",
            ),),
        )
    except (ValueError, OverflowError):
        return CanonicalResult(
            "blocked",
            None,
            (CanonicalIssue(
                "STATIC_FACTS_SERIALIZATION_INVALID",
                "exactStaticFacts",
                "Re-resolve finite numeric facts for the sealed Exact item.",
            ),),
        )


def derive_simc_serializer_input(
    exact: SealedCanonicalDocument,
) -> dict[str, str]:
    """Derive SimC fields only from a re-verified sealed Exact document."""

    payload = _verified_exact_payload_copy(exact)
    result = {
        "id": payload["itemId"],
        "ilevel": f'{payload["itemLevel"]:d}',
    }
    for serializer_field, payload_field in (
        ("bonus_id", "bonusIds"),
        ("gem_id", "gemIds"),
        ("gem_bonus_id", "gemBonusIds"),
        ("gem_ilevel", "gemItemLevels"),
        ("crafted_stats", "craftedStats"),
        ("embellishment", "embellishmentIds"),
    ):
        values = payload[payload_field]
        if values:
            if payload_field == "gemItemLevels":
                result[serializer_field] = "/".join(f"{value:d}" for value in values)
            else:
                result[serializer_field] = "/".join(values)
    if payload["enchantId"]:
        result["enchant_id"] = payload["enchantId"]
    return result


def build_exact_item_identity(
    binding: Any,
    exact_row: Any,
    *,
    enhancement_selection: Any = None,
) -> dict[str, Any]:
    """Build a Catalog-independent identity from one v2 Exact slot contract."""

    del binding
    row = dict(exact_row) if isinstance(exact_row, Mapping) else {}
    problems: list[dict[str, str]] = []
    required_fields = {
        "itemId", "declaredItemLevel", "bonusIds", "context", "gemIds",
        "gemBonusIds", "gemItemLevels", "enchantId", "craftedStats",
        "embellishmentIds", "redirectedBaseStats",
    }
    for field in sorted(required_fields.difference(row)):
        problems.append(_problem("EXACT_FIELD_MISSING", f"exactRow.{field}", "Every v2 Exact slot field is required."))
    if "craftedEffectIds" in row:
        problems.append(_problem(
            "EXACT_CRAFTED_EFFECT_IDS_UNSUPPORTED",
            "exactRow.craftedEffectIds",
            "exact-loadout-intent-v2 does not define craftedEffectIds; use its governed craftedStats or embellishmentIds fields.",
        ))
    raw_item_id = row.get("itemId")
    item_id = _strict_identifier(raw_item_id)
    raw_item_level = row.get("declaredItemLevel")
    item_level = raw_item_level if type(raw_item_level) is int and 1 <= raw_item_level <= 9999 else 0
    bonus_ids = _strict_identifier_list(row.get("bonusIds"), ordered=False)
    raw_context = row.get("context")
    context = raw_context if (
        isinstance(raw_context, str)
        and raw_context == raw_context.strip()
        and len(raw_context.encode("utf-8")) <= 256
        and not any(ord(character) < 32 or ord(character) == 127 for character in raw_context)
    ) else None
    redirected_base_stats = _strict_identifier_list(row.get("redirectedBaseStats"), ordered=False)
    if item_id is None:
        problems.append(_problem("EXACT_ITEM_ID_MISSING", "exactRow.itemId", "Exact identity requires itemId."))
    if not item_level:
        problems.append(_problem("EXACT_ILEVEL_MISSING", "exactRow.declaredItemLevel", "Exact identity requires a positive declared item level."))
    if bonus_ids is None:
        problems.append(_problem("EXACT_BONUS_IDS_MALFORMED", "exactRow.bonusIds", "bonusIds must be a bounded token sequence."))
        bonus_ids = []
    if context is None:
        problems.append(_problem("EXACT_CONTEXT_MALFORMED", "exactRow.context", "context must be a bounded newline-free string."))
        context = ""
    if redirected_base_stats is None:
        problems.append(_problem("EXACT_REDIRECTED_BASE_STATS_MALFORMED", "exactRow.redirectedBaseStats", "redirectedBaseStats must be a bounded token sequence."))
        redirected_base_stats = []
    direct_selection_input = {
        "gemIds": row.get("gemIds"),
        "gemBonusIds": row.get("gemBonusIds"),
        "gemItemLevels": row.get("gemItemLevels"),
        "enchantId": row.get("enchantId"),
        "craftedStats": row.get("craftedStats"),
        "embellishmentIds": row.get("embellishmentIds"),
    }
    selection_result = _strict_v2_enhancement_selection(direct_selection_input)
    if selection_result.get("status") != "verified":
        problems.extend(selection_result.get("problems") or [])
    if enhancement_selection is not None:
        if isinstance(enhancement_selection, Mapping) and "craftedEffectIds" in enhancement_selection:
            problems.append(_problem(
                "EXACT_CRAFTED_EFFECT_IDS_UNSUPPORTED",
                "enhancement.craftedEffectIds",
                "exact-loadout-intent-v2 does not define craftedEffectIds; use its governed craftedStats or embellishmentIds fields.",
            ))
        override_result = _strict_v2_enhancement_selection(enhancement_selection)
        if override_result.get("status") != "verified":
            problems.extend(override_result.get("problems") or [])
        elif selection_result.get("status") == "verified" and dict(enhancement_selection) != direct_selection_input:
            problems.append(_problem("EXACT_ENHANCEMENT_OVERRIDE_MISMATCH", "enhancement", "External enhancement selection must match direct v2 fields."))
    if problems:
        return {
            "status": "blocked", "schemaRevision": EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
            "problemCodes": sorted({_text(problem.get("code")) for problem in problems}),
            "problems": _canonical(problems),
        }
    selection = selection_result["selection"]
    variant_identity = {
        "itemId": item_id, "bonusIds": bonus_ids, "context": context,
        "itemLevel": item_level, "redirectedBaseStats": redirected_base_stats,
    }
    instance_identity = {
        "schemaRevision": EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
        **variant_identity, "enhancementSelection": selection,
    }
    exact_variant_signature = _hash("exact-variant:sha256:", variant_identity)
    exact_key = _hash("exact-item-instance:sha256:", instance_identity)
    return {
        "status": "verified",
        "schemaRevision": EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
        "exactItemInstanceKey": exact_key,
        "exactVariantSignature": exact_variant_signature,
        "enhancementSelectionKey": selection_result["enhancementSelectionKey"],
        **variant_identity,
        "enhancementSelection": selection,
        "serializerInput": _serializer_input(item_id, item_level, bonus_ids, selection),
        "problemCodes": [],
        "problems": [],
    }


def build_exact_item_instance(
    binding: Any,
    exact_row: Any,
    *,
    catalog_revision: str,
    enhancement_selection: Any = None,
) -> dict[str, Any]:
    """Build one canonical instance and its Catalog/Rule-bound validation."""

    active = dict(binding) if isinstance(binding, Mapping) else {}
    row = dict(exact_row) if isinstance(exact_row, Mapping) else {}
    payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
    simc_options = (
        row.get("simcOptions")
        if isinstance(row.get("simcOptions"), Mapping)
        else {}
    )
    problems: list[dict[str, str]] = []

    catalog = _text(catalog_revision)
    if not CATALOG_REVISION_PATTERN.fullmatch(catalog):
        problems.append(_problem(
            "EXACT_CATALOG_REVISION_INVALID",
            "catalogRevision",
            "Exact validation requires one canonical CatalogRevision.",
        ))
    gear_rule_revision = _text(active.get("gearRuleRevision"))
    if not gear_rule_revision:
        problems.append(_problem(
            "EXACT_GEAR_RULE_REVISION_MISSING",
            "binding.gearRuleRevision",
            "Exact validation requires a gear rule revision.",
        ))

    item_id = _text(row.get("itemId"))
    variant_key = _text(row.get("variantKey"))
    item_level = _positive_int(row.get("itemLevel"))
    if not item_id or not variant_key:
        problems.append(_problem(
            "EXACT_SOURCE_IDENTITY_MISSING",
            "exactRow",
            "Exact source requires itemId and variantKey.",
        ))
    if _text(row.get("rowFamily")) != "exact_instance":
        problems.append(_problem(
            "EXACT_SOURCE_ROW_FAMILY_INVALID",
            "exactRow.rowFamily",
            "Exact cache accepts only exact_instance rows.",
        ))
    if _text(row.get("status")).lower() != "verified" or row.get("blockers"):
        problems.append(_problem(
            "EXACT_SOURCE_UNVERIFIED",
            "exactRow.status",
            "Exact source must be verified and blocker-free.",
        ))
    if not item_level:
        problems.append(_problem(
            "EXACT_ILEVEL_MISSING",
            "exactRow.itemLevel",
            "Exact identity requires a positive item level.",
        ))

    bonus_ids = _set_tokens(row.get("bonusIds"))
    if bonus_ids is None:
        problems.append(_problem(
            "EXACT_BONUS_IDS_MALFORMED",
            "exactRow.bonusIds",
            "Exact identity requires an explicit bounded bonus ID array.",
        ))
        bonus_ids = []
    simc_bonus_ids = _set_tokens(simc_options.get("bonus_id"))
    if simc_bonus_ids is None:
        problems.append(_problem(
            "EXACT_BONUS_IDS_MALFORMED",
            "exactRow.simcOptions.bonus_id",
            "SimC bonus_id must be a bounded token sequence.",
        ))
    elif simc_bonus_ids and simc_bonus_ids != bonus_ids:
        problems.append(_problem(
            "EXACT_BONUS_SOURCE_MISMATCH",
            "exactRow.simcOptions.bonus_id",
            "Structured and SimC bonus IDs must describe the same exact instance.",
        ))
    simc_level = _positive_int(simc_options.get("ilevel"))
    if simc_level and simc_level != item_level:
        problems.append(_problem(
            "EXACT_ILEVEL_SOURCE_MISMATCH",
            "exactRow.simcOptions.ilevel",
            "Structured and SimC item levels must match.",
        ))

    static_facts = _static_facts(
        row.get("staticStats")
        or payload.get("resolvedStats")
        or payload.get("itemStats")
    )
    if static_facts is None:
        problems.append(_problem(
            "EXACT_STATIC_FACTS_MISSING",
            "exactRow.staticStats",
            "Verified exact static facts are required.",
        ))
        static_facts = {}

    context = _canonical_context(
        row.get("context")
        if row.get("context") not in (None, "")
        else payload.get("context")
    )
    if context is None:
        problems.append(_problem(
            "EXACT_CONTEXT_MALFORMED",
            "exactRow.context",
            "Exact context must be canonical JSON data.",
        ))
        context = ""

    track_result = resolve_exact_instance_progression(active, row)
    if track_result.get("status") != "verified":
        problems.extend(
            dict(problem)
            for problem in track_result.get("problems") or []
            if isinstance(problem, Mapping)
        )
    progression_state = (
        _canonical(track_result.get("progressionState"))
        if isinstance(track_result.get("progressionState"), Mapping)
        else {}
    )

    source_enhancement = canonical_enhancement_selection(
        _enhancement_from_simc_options(simc_options)
    )
    if source_enhancement.get("status") != "verified":
        problems.extend(source_enhancement.get("problems") or [])
        source_selection = _enhancement_identity({})
    else:
        source_selection = source_enhancement["selection"]

    selected_enhancement = source_enhancement
    if enhancement_selection is not None:
        selected_enhancement = canonical_enhancement_selection(
            enhancement_selection
        )
        if selected_enhancement.get("status") != "verified":
            problems.extend(selected_enhancement.get("problems") or [])
        elif selected_enhancement.get("selection") != source_selection:
            problems.append(_problem(
                "EXACT_ENHANCEMENT_SOURCE_MISMATCH",
                "enhancement",
                "Template enhancement values must match the sealed exact source.",
            ))

    if problems or selected_enhancement.get("status") != "verified":
        return {
            "status": "blocked",
            "schemaRevision": EXACT_ITEM_INSTANCE_SCHEMA_REVISION,
            "catalogRevision": catalog,
            "itemId": item_id,
            "variantKey": variant_key,
            "problemCodes": sorted({
                _text(problem.get("code"))
                for problem in problems
                if isinstance(problem, Mapping) and _text(problem.get("code"))
            }),
            "problems": _canonical(problems),
        }

    selection = selected_enhancement["selection"]
    selection_key = selected_enhancement["enhancementSelectionKey"]
    variant_identity = {
        "itemId": item_id,
        "bonusIds": bonus_ids,
        "context": context,
        "progressionState": progression_state,
        "ilevel": item_level,
    }
    exact_variant_signature = _hash(
        "exact-variant:sha256:",
        variant_identity,
    )
    instance_identity = {
        **variant_identity,
        "enhancementSelection": selection,
    }
    exact_key = _hash(
        "exact-item-instance:sha256:",
        instance_identity,
    )
    serializer_input = _serializer_input(
        item_id,
        item_level,
        bonus_ids,
        selection,
    )
    instance_row = {
        "schemaRevision": EXACT_ITEM_INSTANCE_SCHEMA_REVISION,
        "exactItemInstanceKey": exact_key,
        "exactVariantSignature": exact_variant_signature,
        "enhancementSelectionKey": selection_key,
        **instance_identity,
    }
    validation = {
        "schemaRevision": EXACT_ITEM_VALIDATION_SCHEMA_REVISION,
        "exactItemInstanceKey": exact_key,
        "catalogRevision": catalog,
        "gearRuleRevision": gear_rule_revision,
        "status": "verified",
        "staticFacts": static_facts,
        "serializerInput": serializer_input,
    }
    return {
        "status": "verified",
        **instance_row,
        "itemLevel": item_level,
        "enhancementSelection": selection,
        "enhancementSelectionRow": {
            "enhancementSelectionKey": selection_key,
            "selection": selection,
            "rowHash": selected_enhancement["rowHash"],
        },
        "instanceRow": {
            **instance_row,
            "rowHash": "sha256:" + hashlib.sha256(
                _canonical_bytes(instance_row)
            ).hexdigest(),
        },
        "validation": {
            **validation,
            "rowHash": "sha256:" + hashlib.sha256(
                _canonical_bytes(validation)
            ).hexdigest(),
        },
        "staticFacts": static_facts,
        "serializerInput": serializer_input,
        "problemCodes": [],
        "problems": [],
    }


__all__ = (
    "CATALOG_REVISION_PATTERN",
    "ENHANCEMENT_SELECTION_KEY_PATTERN",
    "ENHANCEMENT_SELECTION_SCHEMA_REVISION",
    "EXACT_ITEM_DOCUMENT_KIND",
    "EXACT_ITEM_KEY_PREFIX",
    "EXACT_ITEM_INSTANCE_KEY_PATTERN",
    "EXACT_ITEM_IDENTITY_SCHEMA_REVISION",
    "EXACT_ITEM_INSTANCE_SCHEMA_REVISION",
    "EXACT_ITEM_VALIDATION_SCHEMA_REVISION",
    "EXACT_STATIC_FACTS_DOCUMENT_KIND",
    "EXACT_STATIC_FACTS_KEY_PREFIX",
    "EXACT_STATIC_FACTS_MAX_ABSOLUTE_NUMBER",
    "EXACT_STATIC_FACTS_MAX_CANONICAL_BYTES",
    "EXACT_STATIC_FACTS_MAX_COUNT",
    "EXACT_STATIC_FACTS_SCHEMA_REVISION",
    "EXACT_VARIANT_SIGNATURE_PATTERN",
    "build_exact_item_instance",
    "build_exact_item_identity",
    "canonical_enhancement_selection",
    "derive_simc_serializer_input",
    "seal_exact_item",
    "seal_exact_static_facts",
)

#!/usr/bin/env python3
"""Pure canonical ExactItemInstance and EnhancementSelection contracts.

The module owns identity and revision-bound validation only. It deliberately
does not access PostgreSQL, files, environment, clock, network, routes, or the
active Manifest pointer.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping

try:
    from .gear_track_authority import resolve_exact_instance_progression
except ImportError:
    from gear_track_authority import resolve_exact_instance_progression


EXACT_ITEM_INSTANCE_SCHEMA_REVISION = "gear-exact-item-instance-v1"
EXACT_ITEM_IDENTITY_SCHEMA_REVISION = "gear-exact-item-instance-v2"
EXACT_ITEM_VALIDATION_SCHEMA_REVISION = "gear-exact-item-validation-v1"
ENHANCEMENT_SELECTION_SCHEMA_REVISION = "gear-enhancement-selection-v1"

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


def build_exact_item_identity(
    binding: Any,
    exact_row: Any,
    *,
    enhancement_selection: Any = None,
) -> dict[str, Any]:
    """Build a Catalog-independent v2 Exact identity.

    The frozen v1 builder below remains the only Catalog/Rule validation
    wrapper.  This helper deliberately projects only sealed instance facts;
    listing, Catalog revisions, owners, and observations never enter the
    canonical bytes.
    """

    # v1 already owns the source normalization and progression proof.  A
    # syntactically valid sentinel lets this pure identity reuse that frozen
    # normalization without reading or depending on a Catalog membership.
    normalized = build_exact_item_instance(
        binding,
        exact_row,
        catalog_revision="gear-catalog:sha256:" + ("0" * 64),
        enhancement_selection=enhancement_selection,
    )
    if normalized.get("status") != "verified":
        return {
            "status": "blocked",
            "schemaRevision": EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
            "problemCodes": list(normalized.get("problemCodes") or []),
            "problems": _canonical(normalized.get("problems") or []),
        }

    row = dict(exact_row) if isinstance(exact_row, Mapping) else {}
    redirected_base_stats = row.get("redirectedBaseStats")
    if redirected_base_stats in (None, "", {}, []):
        redirected_base_stats = {}
    else:
        redirected_base_stats = _static_facts(redirected_base_stats)
        if redirected_base_stats is None:
            return {
                "status": "blocked",
                "schemaRevision": EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
                "problemCodes": ["EXACT_REDIRECTED_BASE_STATS_MALFORMED"],
                "problems": [_problem(
                    "EXACT_REDIRECTED_BASE_STATS_MALFORMED",
                    "exactRow.redirectedBaseStats",
                    "redirectedBaseStats must be a non-empty numeric stat map.",
                )],
            }

    variant_identity = {
        "itemId": normalized["itemId"],
        "bonusIds": normalized["bonusIds"],
        "context": normalized["context"],
        "progressionState": normalized["progressionState"],
        "itemLevel": normalized["itemLevel"],
        "redirectedBaseStats": redirected_base_stats,
    }
    instance_identity = {
        "schemaRevision": EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
        **variant_identity,
        "enhancementSelection": normalized["enhancementSelection"],
    }
    exact_variant_signature = _hash("exact-variant:sha256:", variant_identity)
    exact_key = _hash("exact-item-instance:sha256:", instance_identity)
    return {
        "status": "verified",
        "schemaRevision": EXACT_ITEM_IDENTITY_SCHEMA_REVISION,
        "exactItemInstanceKey": exact_key,
        "exactVariantSignature": exact_variant_signature,
        "enhancementSelectionKey": normalized["enhancementSelectionKey"],
        **variant_identity,
        "enhancementSelection": normalized["enhancementSelection"],
        "serializerInput": normalized["serializerInput"],
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
    "EXACT_ITEM_INSTANCE_KEY_PATTERN",
    "EXACT_ITEM_IDENTITY_SCHEMA_REVISION",
    "EXACT_ITEM_INSTANCE_SCHEMA_REVISION",
    "EXACT_ITEM_VALIDATION_SCHEMA_REVISION",
    "EXACT_VARIANT_SIGNATURE_PATTERN",
    "build_exact_item_instance",
    "build_exact_item_identity",
    "canonical_enhancement_selection",
)

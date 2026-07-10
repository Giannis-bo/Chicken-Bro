#!/usr/bin/env python3
"""Pure contracts for the equipment simulator resolver boundary.

This module deliberately has no persistence or runtime integration.  It defines
the client-authored intent shape, the server-owned authority context, and the
signatures future resolver phases will use to make dependency changes explicit.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, NotRequired, TypedDict


SELECTION_INTENT_SCHEMA_REVISION = "selection-intent-v1"
DEPENDENCY_VECTOR_CONTRACT_REVISION = "gear-dependency-vector-v1"
AUTHORITY_CONTEXT_CONTRACT_REVISION = "gear-authority-context-v1"
RESOLVER_CONTRACT_REVISION = "gear-resolver-contract-v1"

CANONICAL_GEAR_SLOTS = (
    "head",
    "neck",
    "shoulder",
    "back",
    "chest",
    "wrist",
    "hands",
    "waist",
    "legs",
    "feet",
    "finger1",
    "finger2",
    "trinket1",
    "trinket2",
    "main_hand",
    "off_hand",
)

_FORBIDDEN_FINAL_FACT_KEYS = {
    "itemSetId",
    "stats",
    "simcOptions",
    "legality",
    "readiness",
    "evidence",
    "claims",
}
_ROOT_KEYS = {"schemaRevision", "authoredAgainst", "eligibilityContext", "slots"}
_SLOT_KEYS = {
    "itemId",
    "variantKey",
    "gemOptionIds",
    "enchantOptionId",
    "embellishmentOptionId",
    "craftedOptionId",
    "catalystOptionId",
}
_REQUIRED_DEPENDENCY_FIELDS = (
    "seasonRevision",
    "gearCatalogReleaseId",
    "gearCatalogRevision",
    "gearRuleRevision",
    "resolverContractRevision",
    "serializerRevision",
    "simcRuntimeRevision",
    "statPolicyRevision",
    "selectionSchemaRevision",
)
_OPTIONAL_COMMUNITY_DEPENDENCY_FIELDS = (
    "communityTemplateReleaseId",
    "communityTemplateRevision",
    "templateOriginSignature",
    "validatedAgainstGearReleaseId",
)
_REQUIRED_AUTHORITY_MAPS = (
    "itemsById",
    "variantsByKey",
    "optionsById",
    "ruleParameters",
    "capabilities",
    "evidenceRecordsById",
)
_MAX_IDENTIFIER_LENGTH = 256


class EligibilityContext(TypedDict):
    classKey: str
    level: int
    specKey: str


class AuthoredAgainst(TypedDict):
    gearCatalogRevision: str
    seasonRevision: str


class SlotSelection(TypedDict):
    catalystOptionId: str
    craftedOptionId: str
    embellishmentOptionId: str
    enchantOptionId: str
    gemOptionIds: list[str]
    itemId: str
    variantKey: str


class SelectionIntent(TypedDict):
    authoredAgainst: AuthoredAgainst
    eligibilityContext: EligibilityContext
    schemaRevision: str
    slots: dict[str, SlotSelection]


class DependencyVector(TypedDict):
    gearCatalogReleaseId: str
    gearCatalogRevision: str
    gearRuleRevision: str
    resolverContractRevision: str
    seasonRevision: str
    selectionSchemaRevision: str
    serializerRevision: str
    simcRuntimeRevision: str
    statPolicyRevision: str
    communityTemplateReleaseId: NotRequired[str]
    communityTemplateRevision: NotRequired[str]
    templateOriginSignature: NotRequired[str]
    validatedAgainstGearReleaseId: NotRequired[str]


class AuthorityItem(TypedDict, total=False):
    itemId: str
    slot: str
    variantKeys: list[str]


class AuthorityContext(TypedDict):
    capabilities: dict[str, Any]
    contractRevision: str
    dependencyVector: DependencyVector
    evidenceRecordsById: dict[str, dict[str, Any]]
    itemsById: dict[str, AuthorityItem]
    manifest: dict[str, str]
    missingFields: list[str]
    optionsById: dict[str, dict[str, Any]]
    ruleParameters: dict[str, Any]
    variantsByKey: dict[str, dict[str, Any]]


def _issue(kind: str, code: str, path: str, message: str) -> dict[str, str]:
    return {"kind": kind, "code": code, "path": path, "message": message}


def _bounded_string(value: Any, *, allow_empty: bool = False) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    normalized = str(value).strip()
    if (not normalized and not allow_empty) or len(normalized) > _MAX_IDENTIFIER_LENGTH:
        return None
    return normalized


def _forbidden_fact_issues(value: dict[str, Any], path: str) -> list[dict[str, str]]:
    return [
        _issue(
            "INVALID_INTENT",
            "FORBIDDEN_CLIENT_FACT",
            f"{path}.{key}" if path else key,
            "Final legality, readiness, evidence, and resolved facts are server-owned.",
        )
        for key in sorted(_FORBIDDEN_FINAL_FACT_KEYS.intersection(value))
    ]


def parse_selection_intent(raw_intent: Any) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """Validate and canonicalize a client-authored selection intent."""

    if not isinstance(raw_intent, dict):
        return None, [
            _issue("INVALID_INTENT", "INTENT_NOT_OBJECT", "intent", "Intent must be an object.")
        ]

    issues = _forbidden_fact_issues(raw_intent, "intent")
    for key in sorted(set(raw_intent).difference(_ROOT_KEYS).difference(_FORBIDDEN_FINAL_FACT_KEYS)):
        issues.append(
            _issue("INVALID_INTENT", "UNKNOWN_FIELD", f"intent.{key}", "Field is not part of selection-intent-v1.")
        )

    if raw_intent.get("schemaRevision") != SELECTION_INTENT_SCHEMA_REVISION:
        issues.append(
            _issue(
                "INVALID_INTENT",
                "SCHEMA_REVISION_MISMATCH",
                "intent.schemaRevision",
                f"schemaRevision must be {SELECTION_INTENT_SCHEMA_REVISION}.",
            )
        )

    authored_raw = raw_intent.get("authoredAgainst")
    authored: dict[str, str] = {}
    if not isinstance(authored_raw, dict):
        issues.append(
            _issue("INVALID_INTENT", "MISSING_AUTHORED_AGAINST", "intent.authoredAgainst", "Authored revisions are required.")
        )
    else:
        for key in sorted(set(authored_raw).difference({"seasonRevision", "gearCatalogRevision"})):
            issues.append(
                _issue("INVALID_INTENT", "UNKNOWN_FIELD", f"intent.authoredAgainst.{key}", "Field is not part of AuthoredAgainst.")
            )
        for field in ("seasonRevision", "gearCatalogRevision"):
            normalized = _bounded_string(authored_raw.get(field))
            if normalized is None:
                issues.append(
                    _issue("INVALID_INTENT", "INVALID_REVISION", f"intent.authoredAgainst.{field}", "Revision must be a bounded string.")
                )
            else:
                authored[field] = normalized

    eligibility_raw = raw_intent.get("eligibilityContext")
    eligibility: dict[str, Any] = {}
    if not isinstance(eligibility_raw, dict):
        issues.append(
            _issue("INVALID_INTENT", "MISSING_ELIGIBILITY", "intent.eligibilityContext", "Eligibility context is required.")
        )
    else:
        for key in sorted(set(eligibility_raw).difference({"classKey", "specKey", "level"})):
            issues.append(
                _issue("INVALID_INTENT", "UNKNOWN_FIELD", f"intent.eligibilityContext.{key}", "Field is not part of EligibilityContext.")
            )
        for field in ("classKey", "specKey"):
            normalized = _bounded_string(eligibility_raw.get(field))
            if normalized is None:
                issues.append(
                    _issue("INVALID_INTENT", "INVALID_ELIGIBILITY", f"intent.eligibilityContext.{field}", "Eligibility identifier must be a bounded string.")
                )
            else:
                eligibility[field] = normalized
        level_raw = eligibility_raw.get("level")
        try:
            if isinstance(level_raw, bool):
                raise ValueError
            level = int(level_raw)
            if level <= 0 or level > 999:
                raise ValueError
            eligibility["level"] = level
        except (TypeError, ValueError, OverflowError):
            issues.append(
                _issue("INVALID_INTENT", "INVALID_ELIGIBILITY", "intent.eligibilityContext.level", "Level must be an integer from 1 to 999.")
            )

    slots_raw = raw_intent.get("slots")
    canonical_slots: dict[str, dict[str, Any]] = {}
    if not isinstance(slots_raw, dict):
        issues.append(_issue("INVALID_INTENT", "SLOTS_NOT_OBJECT", "intent.slots", "Slots must be an object."))
    else:
        for slot in slots_raw:
            if slot not in CANONICAL_GEAR_SLOTS:
                issues.append(
                    _issue("INVALID_INTENT", "UNKNOWN_SLOT", f"intent.slots.{slot}", "Slot is not a canonical gear slot.")
                )
        for slot in CANONICAL_GEAR_SLOTS:
            if slot not in slots_raw:
                continue
            slot_raw = slots_raw[slot]
            path = f"intent.slots.{slot}"
            if not isinstance(slot_raw, dict):
                issues.append(_issue("INVALID_INTENT", "SLOT_NOT_OBJECT", path, "Slot selection must be an object."))
                continue
            issues.extend(_forbidden_fact_issues(slot_raw, path))
            for key in sorted(set(slot_raw).difference(_SLOT_KEYS).difference(_FORBIDDEN_FINAL_FACT_KEYS)):
                issues.append(_issue("INVALID_INTENT", "UNKNOWN_FIELD", f"{path}.{key}", "Field is not part of SlotSelection."))

            canonical_slot: dict[str, Any] = {}
            item_id = _bounded_string(slot_raw.get("itemId"))
            if item_id is None:
                issues.append(_issue("INVALID_INTENT", "MISSING_ITEM_ID", f"{path}.itemId", "A bounded itemId is required."))
            else:
                canonical_slot["itemId"] = item_id

            variant_key = _bounded_string(slot_raw.get("variantKey", ""), allow_empty=True)
            if variant_key is None:
                issues.append(_issue("INVALID_INTENT", "INVALID_OPTION_ID", f"{path}.variantKey", "variantKey must be a bounded string."))
            else:
                canonical_slot["variantKey"] = variant_key

            gem_ids = slot_raw.get("gemOptionIds", [])
            canonical_gems: list[str] = []
            if not isinstance(gem_ids, list):
                issues.append(_issue("INVALID_INTENT", "INVALID_OPTION_LIST", f"{path}.gemOptionIds", "gemOptionIds must be an ordered list."))
            else:
                for index, gem_id in enumerate(gem_ids):
                    normalized = _bounded_string(gem_id)
                    if normalized is None:
                        issues.append(_issue("INVALID_INTENT", "INVALID_OPTION_ID", f"{path}.gemOptionIds.{index}", "Gem option ID must be a bounded string."))
                    else:
                        canonical_gems.append(normalized)
            canonical_slot["gemOptionIds"] = canonical_gems

            for field in ("enchantOptionId", "embellishmentOptionId", "craftedOptionId", "catalystOptionId"):
                normalized = _bounded_string(slot_raw.get(field, ""), allow_empty=True)
                if normalized is None:
                    issues.append(_issue("INVALID_INTENT", "INVALID_OPTION_ID", f"{path}.{field}", "Option ID must be a bounded string."))
                else:
                    canonical_slot[field] = normalized
            canonical_slots[slot] = canonical_slot

    if issues:
        return None, issues
    return {
        "schemaRevision": SELECTION_INTENT_SCHEMA_REVISION,
        "authoredAgainst": authored,
        "eligibilityContext": eligibility,
        "slots": canonical_slots,
    }, []


def validate_dependency_vector(vector: Any) -> list[dict[str, str]]:
    if not isinstance(vector, dict):
        return [_issue("AUTHORITY_UNAVAILABLE", "DEPENDENCY_VECTOR_NOT_OBJECT", "dependencyVector", "Dependency Vector must be an object.")]
    issues: list[dict[str, str]] = []
    for field in _REQUIRED_DEPENDENCY_FIELDS:
        if _bounded_string(vector.get(field)) is None:
            issues.append(
                _issue("AUTHORITY_UNAVAILABLE", "MISSING_DEPENDENCY_REVISION", f"dependencyVector.{field}", "Required dependency revision is unavailable.")
            )
    for field in _OPTIONAL_COMMUNITY_DEPENDENCY_FIELDS:
        if field in vector and _bounded_string(vector.get(field)) is None:
            issues.append(
                _issue("AUTHORITY_UNAVAILABLE", "INVALID_DEPENDENCY_REVISION", f"dependencyVector.{field}", "Optional dependency revision must be a bounded string when present.")
            )
    return issues


def validate_authority_context(intent: Any, authority_context: Any) -> list[dict[str, str]]:
    if not isinstance(authority_context, dict):
        return [_issue("AUTHORITY_UNAVAILABLE", "AUTHORITY_CONTEXT_NOT_OBJECT", "authorityContext", "Authority Context must be an object.")]

    issues: list[dict[str, str]] = []
    if authority_context.get("contractRevision") != AUTHORITY_CONTEXT_CONTRACT_REVISION:
        issues.append(
            _issue("AUTHORITY_UNAVAILABLE", "AUTHORITY_CONTRACT_MISMATCH", "authorityContext.contractRevision", "Authority Context contract revision is unavailable.")
        )
    manifest = authority_context.get("manifest")
    if not isinstance(manifest, dict):
        issues.append(_issue("AUTHORITY_UNAVAILABLE", "MISSING_AUTHORITY_MANIFEST", "authorityContext.manifest", "Authority manifest is required."))
        manifest = {}
    else:
        for field in ("seasonRevision", "gearCatalogReleaseId", "gearCatalogRevision"):
            if _bounded_string(manifest.get(field)) is None:
                issues.append(
                    _issue(
                        "AUTHORITY_UNAVAILABLE",
                        "MISSING_AUTHORITY_MANIFEST_FIELD",
                        f"authorityContext.manifest.{field}",
                        "Required authority manifest field is unavailable.",
                    )
                )
    issues.extend(validate_dependency_vector(authority_context.get("dependencyVector")))
    for field in _REQUIRED_AUTHORITY_MAPS:
        if not isinstance(authority_context.get(field), dict):
            issues.append(
                _issue("AUTHORITY_UNAVAILABLE", "MISSING_AUTHORITY_MAP", f"authorityContext.{field}", "Required authority map is unavailable.")
            )

    missing_fields = authority_context.get("missingFields")
    if not isinstance(missing_fields, list):
        issues.append(_issue("AUTHORITY_UNAVAILABLE", "INVALID_MISSING_FIELDS", "authorityContext.missingFields", "missingFields must be a list."))
    else:
        for path in missing_fields:
            normalized = _bounded_string(path)
            issues.append(
                _issue(
                    "AUTHORITY_UNAVAILABLE",
                    "MISSING_AUTHORITY_FIELD",
                    normalized or "authorityContext.missingFields",
                    "A required authority field is unavailable.",
                )
            )

    authored = intent.get("authoredAgainst") if isinstance(intent, dict) else None
    if isinstance(authored, dict):
        if authored.get("seasonRevision") != manifest.get("seasonRevision"):
            issues.append(
                _issue("REVISION_CONFLICT", "SEASON_REVISION_CONFLICT", "authorityContext.manifest.seasonRevision", "Intent season revision differs from current authority.")
            )
        if authored.get("gearCatalogRevision") != manifest.get("gearCatalogRevision"):
            issues.append(
                _issue("REVISION_CONFLICT", "GEAR_CATALOG_REVISION_CONFLICT", "authorityContext.manifest.gearCatalogRevision", "Intent gear catalog revision differs from current authority.")
            )
    return issues


def _signature(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def selection_signature(intent: dict[str, Any], eligibility_context: dict[str, Any]) -> str:
    return _signature(
        {
            "eligibilityContext": eligibility_context,
            "intent": intent,
            "selectionSchemaRevision": SELECTION_INTENT_SCHEMA_REVISION,
        }
    )


def resolved_gear_signature(selection_signature_value: str, dependency_vector: dict[str, Any]) -> str:
    return _signature(
        {
            "selectionSignature": selection_signature_value,
            "dependencyVector": {
                field: dependency_vector.get(field)
                for field in (
                    "seasonRevision",
                    "gearCatalogReleaseId",
                    "gearCatalogRevision",
                    "gearRuleRevision",
                    "resolverContractRevision",
                    "selectionSchemaRevision",
                )
            },
        }
    )


def profile_signature(
    resolved_signature: str,
    character_context: dict[str, Any],
    talent_hash: str,
    serializer_revision: str,
    simc_runtime_revision: str,
    stat_policy_revision: str,
) -> str:
    return _signature(
        {
            "resolvedGearSignature": resolved_signature,
            "characterContext": character_context,
            "talentHash": talent_hash,
            "serializerRevision": serializer_revision,
            "simcRuntimeRevision": simc_runtime_revision,
            "statPolicyRevision": stat_policy_revision,
        }
    )


__all__ = (
    "parse_selection_intent",
    "validate_dependency_vector",
    "validate_authority_context",
    "selection_signature",
    "resolved_gear_signature",
    "profile_signature",
)

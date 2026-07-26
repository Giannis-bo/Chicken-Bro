#!/usr/bin/env python3
"""Bounded PostgreSQL projection for the canonical gear Authority Context."""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
import re
import threading
from typing import Any, Iterable

try:
    from . import gear_socket_authority
    from .gear_attribute_static_facts import (
        STATIC_FACT_RULE_REVISION,
        option_static_facts,
    )
    from .gear_enhancement_management import (
        project_validated_enhancement_management,
        validated_enhancement_management_fields,
    )
except ImportError:
    import gear_socket_authority
    from gear_attribute_static_facts import STATIC_FACT_RULE_REVISION, option_static_facts
    from gear_enhancement_management import (
        project_validated_enhancement_management,
        validated_enhancement_management_fields,
    )

try:
    from .gear_contracts import parse_selection_intent, selection_signature
except ImportError:
    from gear_contracts import parse_selection_intent, selection_signature

try:
    from .websim_payload import (
        EQUIVALENT_GEAR_SLOTS,
        ITEM_METADATA_SOURCE,
        gear_item_handedness_fields,
        item_mod_capabilities,
        item_slot_from_payload,
        item_type_metadata_from_payload,
    )
except ImportError:
    from websim_payload import (
        EQUIVALENT_GEAR_SLOTS,
        ITEM_METADATA_SOURCE,
        gear_item_handedness_fields,
        item_mod_capabilities,
        item_slot_from_payload,
        item_type_metadata_from_payload,
    )


COMPATIBILITY_MANIFEST_REVISION = "compatibility-pg-live-v1"
AUTHORITY_CONTEXT_CONTRACT_REVISION = "gear-authority-context-v1"
RESOLVER_CONTEXT_CONTRACT_REVISION = "gear-resolver-context-v1"

AUTHORITY_REVISION_SQL = """
/* gear_authority_revision */
SELECT
    COALESCE((
        SELECT season_revision
        FROM cache.websim_season_state
        WHERE key = 'active' AND active = TRUE AND data_status = 'verified'
        LIMIT 1
    ), '') AS season_revision,
    COALESCE((
        SELECT state_json FROM cache.websim_sync_state WHERE id = 'gearCatalog'
    ), '{}'::jsonb) AS gear_catalog_state,
    COALESCE((
        SELECT state_json FROM cache.websim_sync_state WHERE id = 'websim_sync'
    ), '{}'::jsonb) AS websim_sync_state,
    (SELECT COUNT(*) FROM cache.websim_items) AS item_count,
    (SELECT MAX(updated_at)::text FROM cache.websim_items) AS item_max_updated_at,
    (SELECT COUNT(*) FROM cache.websim_gear_variants) AS variant_count,
    (SELECT MAX(updated_at)::text FROM cache.websim_gear_variants) AS variant_max_updated_at,
    (SELECT COUNT(*) FROM cache.websim_gear_mod_options) AS option_count,
    (SELECT MAX(updated_at)::text FROM cache.websim_gear_mod_options) AS option_max_updated_at,
    (SELECT COUNT(*) FROM cache.websim_gear_sources) AS source_count,
    (SELECT MAX(updated_at)::text FROM cache.websim_gear_sources) AS source_max_updated_at
"""

SELECTED_ITEM_VARIANT_SQL = """
/* gear_authority_items_variants */
WITH requested(item_id, variant_key) AS (
    SELECT * FROM unnest(%s::text[], %s::text[])
)
SELECT
    requested.item_id,
    requested.variant_key,
    CASE WHEN item.id IS NULL THEN NULL ELSE jsonb_build_object(
        'id', item.id,
        'name', item.name,
        'slot', item.slot,
        'itemLevel', item.item_level,
        'sourceStatus', item.source_status,
        'itemSetIds', COALESCE((
            SELECT jsonb_agg(DISTINCT COALESCE(
                NULLIF(set_source.payload_json->>'setId', ''),
                NULLIF(set_source.payload_json->>'set_id', ''),
                NULLIF(set_source.payload_json->>'itemSetId', ''),
                NULLIF(set_source.payload_json->>'item_set_id', '')
            ))
            FROM cache.websim_gear_sources set_source
            WHERE set_source.item_id = requested.item_id
              AND set_source.source_type = 'tier_set'
              AND COALESCE(
                  NULLIF(set_source.payload_json->>'setId', ''),
                  NULLIF(set_source.payload_json->>'set_id', ''),
                  NULLIF(set_source.payload_json->>'itemSetId', ''),
                  NULLIF(set_source.payload_json->>'item_set_id', ''),
                  ''
              ) <> ''
              AND (
                  LOWER(COALESCE(set_source.payload_json->>'status', '')) = 'verified'
                  OR LOWER(COALESCE(set_source.payload_json->>'sourceStatus', '')) = 'verified'
                  OR set_source.payload_json->>'authority' = 'Battle.net Game Data API'
              )
        ), '[]'::jsonb),
        'payload', item.payload_json,
        'updatedAt', item.updated_at::text
    ) END AS item_record,
    CASE WHEN variant.id IS NULL THEN NULL ELSE jsonb_build_object(
        'id', variant.id::text,
        'itemId', variant.item_id,
        'slot', variant.slot,
        'variantKey', variant.variant_key,
        'label', variant.label,
        'sourceType', variant.source_type,
        'difficultyKey', variant.difficulty_key,
        'itemLevel', variant.item_level,
        'simcOptions', variant.simc_options_json,
        'status', variant.status,
        'blockers', variant.blockers_json,
        'payload', variant.payload_json,
        'updatedAt', variant.updated_at::text
    ) END AS variant_record,
    COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'id', source.id::text,
            'sourceType', source.source_type,
            'sourceKey', source.source_key,
            'sourceLabel', source.source_label,
            'instanceId', source.instance_id,
            'encounterId', source.encounter_id,
            'difficultyKey', source.difficulty_key,
            'seasonRevision', source.season_revision,
            'status', CASE
                WHEN LOWER(COALESCE(source.payload_json->>'status', '')) = 'verified'
                  OR LOWER(COALESCE(source.payload_json->>'sourceStatus', '')) = 'verified'
                  OR (
                      source.source_type = 'tier_set'
                      AND source.payload_json->>'authority' = 'Battle.net Game Data API'
                      AND COALESCE(
                          NULLIF(source.payload_json->>'setId', ''),
                          NULLIF(source.payload_json->>'set_id', ''),
                          NULLIF(source.payload_json->>'itemSetId', ''),
                          NULLIF(source.payload_json->>'item_set_id', ''),
                          ''
                      ) <> ''
                  )
                THEN 'verified'
                ELSE COALESCE(
                NULLIF(source.payload_json->>'status', ''),
                NULLIF(source.payload_json->>'sourceStatus', ''),
                'unknown'
                )
            END,
            'sourceStatus', COALESCE(
                NULLIF(source.payload_json->>'sourceStatus', ''),
                'unknown'
            ),
            'payload', source.payload_json,
            'updatedAt', source.updated_at::text
        ) ORDER BY
            CASE WHEN source.source_type = variant.source_type THEN 0 ELSE 1 END,
            source.updated_at DESC,
            source.id::text)
        FROM (
            SELECT chosen.*
            FROM (
                SELECT DISTINCT ON (candidate.source_type) candidate.*
                FROM cache.websim_gear_sources candidate
                WHERE candidate.item_id = requested.item_id
                  AND (
                      LOWER(COALESCE(candidate.payload_json->>'status', '')) = 'verified'
                      OR LOWER(COALESCE(candidate.payload_json->>'sourceStatus', '')) = 'verified'
                      OR (
                          candidate.source_type = 'tier_set'
                          AND candidate.payload_json->>'authority' = 'Battle.net Game Data API'
                          AND COALESCE(
                              NULLIF(candidate.payload_json->>'setId', ''),
                              NULLIF(candidate.payload_json->>'set_id', ''),
                              NULLIF(candidate.payload_json->>'itemSetId', ''),
                              NULLIF(candidate.payload_json->>'item_set_id', ''),
                              ''
                          ) <> ''
                      )
                  )
                ORDER BY
                    candidate.source_type,
                    candidate.updated_at DESC,
                    candidate.id::text
            ) chosen
            ORDER BY
                CASE WHEN chosen.source_type = variant.source_type THEN 0 ELSE 1 END,
                chosen.updated_at DESC,
                chosen.id::text
            LIMIT 8
        ) source
    ), '[]'::jsonb) AS source_records
FROM requested
LEFT JOIN cache.websim_items item ON item.id = requested.item_id
LEFT JOIN cache.websim_gear_variants variant
 ON variant.item_id = requested.item_id
 AND requested.variant_key <> ''
 AND (
      variant.variant_key = requested.variant_key
      OR LEFT(
          REGEXP_REPLACE(BTRIM(variant.variant_key), '[^A-Za-z0-9_:/.-]+', '', 'g'),
          240
      ) = requested.variant_key
 )
ORDER BY requested.item_id, requested.variant_key
"""

SELECTED_OPTION_SQL = """
/* gear_authority_options */
SELECT
    option.option_key,
    jsonb_build_object(
        'id', option.id::text,
        'optionKey', option.option_key,
        'optionType', option.option_type,
        'name', option.name,
        'applicableSlots', option.applicable_slots_json,
        'simcOptions', option.simc_options_json,
        'status', option.status,
        'isVisible', option.is_visible,
        'payload', option.payload_json,
        'updatedAt', option.updated_at::text
    ) AS option_record
FROM cache.websim_gear_mod_options option
WHERE option.option_key = ANY(%s::text[])
ORDER BY option.option_key
"""

_REQUIRED_RUNTIME_REVISIONS = (
    "gearRuleRevision",
    "resolverContractRevision",
    "serializerRevision",
    "simcRuntimeRevision",
    "statPolicyRevision",
    "selectionSchemaRevision",
    "capabilityRevision",
)
_OPTION_ALLOW_FIELDS = {
    "gem": "allowedGemOptionIds",
    "enchant": "allowedEnchantOptionIds",
    "runeforge": "allowedEnchantOptionIds",
    "embellishment": "allowedEmbellishmentOptionIds",
    "crafted": "allowedCraftedOptionIds",
    "catalyst": "allowedCatalystOptionIds",
}
_MAX_SOCKET_EVIDENCE_TEXT_CHARS = 240
_OPTION_UNIQUE_GROUP_FIELDS = (
    "uniqueGroupId",
    "unique_group_id",
    "uniqueGroup",
    "unique_group",
    "uniqueKey",
    "unique_key",
)
_OPTION_UNIQUE_LIMIT_FIELDS = (
    "uniqueLimit",
    "unique_limit",
    "uniqueEquippedLimit",
    "unique_equipped_limit",
)
def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    )


def _serialized(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _json_value(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return _canonical(value)
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return _canonical(fallback)
    return _canonical(parsed if parsed is not None else fallback)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _public_variant_alias(value: Any) -> str:
    """Mirror websim_payload.normalize_option_value for public variant keys."""

    return re.sub(r"[^A-Za-z0-9_:/.-]+", "", _text(value))[:240]


def _variant_key_matches(requested: Any, authority: Any) -> bool:
    requested_key = _text(requested)
    authority_key = _text(authority)
    return bool(
        requested_key
        and authority_key
        and (
            authority_key == requested_key
            or _public_variant_alias(authority_key) == requested_key
        )
    )


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _non_negative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    return max(0, _int(value))


def _positive_integer(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value if value > 0 else 0
    if isinstance(value, str) and re.fullmatch(r"[1-9]\d*", value.strip()):
        return int(value.strip())
    return 0


def _strict_unique_group(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _option_unique_groups(record: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    return sorted({
        value.strip()
        for source in (record, payload)
        for field in _OPTION_UNIQUE_GROUP_FIELDS
        for value in (source.get(field),)
        if isinstance(value, str) and value.strip()
    })


def _option_unique_limit(record: dict[str, Any], payload: dict[str, Any]) -> int:
    positive_limits = [
        parsed
        for source in (record, payload)
        for field in _OPTION_UNIQUE_LIMIT_FIELDS
        for parsed in (_positive_integer(source.get(field)),)
        if parsed > 0
    ]
    return min(positive_limits) if positive_limits else 0


def _texts(values: Iterable[Any]) -> list[str]:
    result = {_text(value) for value in values or []}
    result.discard("")
    return sorted(result)


def _static_stats(*candidates: Any) -> dict[str, int | float]:
    """Normalize structured stat facts only; never parse display summaries."""

    for raw in candidates:
        if isinstance(raw, dict):
            result = {
                _text(key): value
                for key, value in raw.items()
                if _text(key)
                and not isinstance(value, bool)
                and isinstance(value, (int, float))
            }
            return {key: result[key] for key in sorted(result)}
        if isinstance(raw, list):
            result: dict[str, int | float] = {}
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                key = _text(entry.get("key"))
                value = entry.get("value")
                if not key or isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                result[key] = result.get(key, 0) + value
            return {key: result[key] for key in sorted(result)}
    return {}


def _authority_stat_map(raw: Any) -> Any:
    """Normalize valid list-shaped facts while preserving invalid authority for Resolver blockers."""

    if isinstance(raw, dict):
        return _canonical(raw)
    if isinstance(raw, list):
        normalized = _static_stats(raw)
        valid = all(
            isinstance(entry, dict)
            and isinstance(entry.get("key"), str)
            and bool(entry.get("key").strip())
            and not isinstance(entry.get("value"), bool)
            and isinstance(entry.get("value"), (int, float))
            for entry in raw
        )
        return normalized if valid else _canonical(raw)
    return []


class AuthorityContextCache:
    """Detached LRU cache bounded by both entry count and serialized bytes."""

    def __init__(self, max_entries: int, max_bytes: int):
        if isinstance(max_entries, bool) or not isinstance(max_entries, int) or max_entries <= 0:
            raise ValueError("max_entries must be a positive integer")
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
            raise ValueError("max_bytes must be a positive integer")
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self._entries: OrderedDict[str, tuple[int, Any]] = OrderedDict()
        self._byte_size = 0
        self._lock = threading.RLock()

    @property
    def entry_count(self) -> int:
        with self._lock:
            return len(self._entries)

    @property
    def byte_size(self) -> int:
        with self._lock:
            return self._byte_size

    def get(self, key: str) -> Any | None:
        normalized = _text(key)
        with self._lock:
            if normalized not in self._entries:
                return None
            size, value = self._entries.pop(normalized)
            self._entries[normalized] = (size, value)
        return _canonical(value)

    def put(self, key: str, value: Any) -> bool:
        normalized = _text(key)
        if not normalized:
            return False
        detached = _canonical(value)
        size = len(_serialized(detached))
        if size > self.max_bytes:
            return False
        with self._lock:
            previous = self._entries.pop(normalized, None)
            if previous:
                self._byte_size -= previous[0]
            self._entries[normalized] = (size, detached)
            self._byte_size += size
            while len(self._entries) > self.max_entries or self._byte_size > self.max_bytes:
                _old_key, (old_size, _old_value) = self._entries.popitem(last=False)
                self._byte_size -= old_size
            return normalized in self._entries


def compatibility_catalog_revision(revision_row: Any) -> str:
    """Return a compatibility fingerprint from bounded current-table identities."""

    row = list(revision_row or [])
    payload = {
        "contractRevision": COMPATIBILITY_MANIFEST_REVISION,
        "seasonRevision": _text(row[0] if len(row) > 0 else ""),
        "gearCatalogState": _json_value(row[1] if len(row) > 1 else {}, {}),
        "websimSyncState": _json_value(row[2] if len(row) > 2 else {}, {}),
        "tables": {
            "items": {
                "count": _int(row[3] if len(row) > 3 else 0),
                "maxUpdatedAt": _text(row[4] if len(row) > 4 else ""),
            },
            "variants": {
                "count": _int(row[5] if len(row) > 5 else 0),
                "maxUpdatedAt": _text(row[6] if len(row) > 6 else ""),
            },
            "options": {
                "count": _int(row[7] if len(row) > 7 else 0),
                "maxUpdatedAt": _text(row[8] if len(row) > 8 else ""),
            },
            "sources": {
                "count": _int(row[9] if len(row) > 9 else 0),
                "maxUpdatedAt": _text(row[10] if len(row) > 10 else ""),
            },
        },
    }
    digest = hashlib.sha256(_serialized(payload)).hexdigest()
    return f"compatibility-pg:{digest}"


def _revision_projection(revision_row: Any, runtime_authority: Any) -> dict[str, Any]:
    row = tuple(revision_row or ())
    runtime = runtime_authority if isinstance(runtime_authority, dict) else {}
    catalog_revision = compatibility_catalog_revision(row)
    season_revision = _text(row[0] if len(row) > 0 else "")
    catalog_state = _json_value(row[1] if len(row) > 1 else {}, {})
    websim_state = _json_value(row[2] if len(row) > 2 else {}, {})
    revisions = runtime.get("dependencyRevisions")
    revisions = revisions if isinstance(revisions, dict) else {}
    release_id = f"compatibility:{catalog_revision.removeprefix('compatibility-pg:')[:16]}"
    dependency_vector = {
        "seasonRevision": season_revision,
        "gearCatalogReleaseId": release_id,
        "gearCatalogRevision": catalog_revision,
        **{field: _text(revisions.get(field)) for field in _REQUIRED_RUNTIME_REVISIONS},
    }
    missing = []
    if not season_revision:
        missing.append("manifest.seasonRevision")
    for field in _REQUIRED_RUNTIME_REVISIONS:
        if not dependency_vector[field]:
            missing.append(f"runtimeAuthority.dependencyRevisions.{field}")
    return {
        "catalogRevision": catalog_revision,
        "seasonRevision": season_revision,
        "catalogState": catalog_state,
        "websimState": websim_state,
        "releaseId": release_id,
        "dependencyVector": dependency_vector,
        "missingFields": sorted(set(missing)),
    }


def resolver_authoring_context(revision_row: Any, runtime_authority: Any) -> dict[str, Any] | None:
    """Project the exact current revisions a client must bind into Selection Intent."""

    projection = _revision_projection(revision_row, runtime_authority)
    if projection["missingFields"]:
        return None
    dependency_vector = projection["dependencyVector"]
    return _canonical(
        {
            "contractRevision": RESOLVER_CONTEXT_CONTRACT_REVISION,
            "formalActiveManifest": False,
            "selectionSchemaRevision": dependency_vector["selectionSchemaRevision"],
            "authoredAgainst": {
                "seasonRevision": projection["seasonRevision"],
                "gearCatalogRevision": projection["catalogRevision"],
            },
            "dependencyRevisions": {
                field: dependency_vector[field]
                for field in _REQUIRED_RUNTIME_REVISIONS
            },
        }
    )


def _cache_key(intent: dict[str, Any], dependency_vector: dict[str, Any]) -> str:
    signature = selection_signature(intent, intent["eligibilityContext"])
    digest = hashlib.sha256(
        _serialized(
            {
                "selectionSignature": signature,
                "dependencyVector": dependency_vector,
            }
        )
    ).hexdigest()
    return f"gear-authority:{digest}"


def candidate_authority_cache_key(
    selection_intent: Any,
    runtime_authority: Any,
    gear_release_id: Any,
) -> str:
    """Return the exact-release cache identity for an internal candidate read."""

    intent, intent_issues = parse_selection_intent(selection_intent)
    if intent_issues:
        paths = ", ".join(issue.get("path", "intent") for issue in intent_issues)
        raise ValueError(f"Invalid Selection Intent: {paths}")
    runtime = runtime_authority if isinstance(runtime_authority, dict) else {}
    revisions = runtime.get("dependencyRevisions")
    revisions = revisions if isinstance(revisions, dict) else {}
    release_id = _text(gear_release_id)
    dependency_vector = {
        "seasonRevision": intent["authoredAgainst"]["seasonRevision"],
        "gearCatalogReleaseId": release_id,
        "gearCatalogRevision": release_id,
        **{field: _text(revisions.get(field)) for field in _REQUIRED_RUNTIME_REVISIONS},
    }
    return _cache_key(intent, dependency_vector)


def _runtime_source_records(runtime_authority: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for raw in runtime_authority.get("sourceRefs", []) if isinstance(runtime_authority, dict) else []:
        if isinstance(raw, dict):
            source_id = _text(raw.get("id"))
            if source_id:
                records[source_id] = _canonical(raw)
    return records


def _runtime_missing(runtime_authority: Any) -> list[str]:
    if not isinstance(runtime_authority, dict):
        return ["runtimeAuthority"]
    missing: list[str] = []
    revisions = runtime_authority.get("dependencyRevisions")
    if not isinstance(revisions, dict):
        revisions = {}
    for field in _REQUIRED_RUNTIME_REVISIONS:
        if not _text(revisions.get(field)):
            missing.append(f"runtimeAuthority.dependencyRevisions.{field}")
    for field in ("ruleParameters", "capabilities", "playableClassSpecs"):
        if not isinstance(runtime_authority.get(field), dict):
            missing.append(f"runtimeAuthority.{field}")
    return missing


def _playable_scope(runtime_authority: dict[str, Any]) -> tuple[list[str], list[str]]:
    playable = runtime_authority.get("playableClassSpecs")
    playable = playable if isinstance(playable, dict) else {}
    classes = _texts(playable)
    specs = _texts(spec for values in playable.values() if isinstance(values, list) for spec in values)
    return classes, specs


def _evidence_id(kind: str, identity: Any) -> str:
    return f"evidence:pg:{kind}:{_text(identity)}"


_RELEASED_FACT_SCHEMA_REVISION = "gear-canonical-fact-v1"
_RELEASED_FACT_STATUSES = {"verified", "unresolved_missing", "unresolved_conflict"}
_CAPABILITY_FACT_SPECS = {
    "socket": ("socket_count", int, "allowedGemOptionIds", {"gem"}),
    "enchant": (
        "enchant_capability",
        bool,
        "allowedEnchantOptionIds",
        {"enchant", "runeforge"},
    ),
    "embellishment": (
        "embellishment_capability",
        bool,
        "allowedEmbellishmentOptionIds",
        {"embellishment", "crafted"},
    ),
}
_EXECUTABLE_SIMC_OPTION_FIELDS = frozenset(
    {
        "bonus_id",
        "crafted_stats",
        "embellishment",
        "enchant_id",
        "gem_bonus_id",
        "gem_id",
        "gem_ilevel",
        "ilevel",
        "redirected_base_stats",
    }
)


def _released_facts(
    payload: dict[str, Any],
    subject_key: str,
    evidence: dict[str, dict[str, Any]],
    release_id: str,
) -> dict[str, dict[str, Any]] | None:
    """Index only sealed Canonical Facts for one exact release subject."""

    raw_facts = payload.get("canonicalFacts")
    if not isinstance(raw_facts, list):
        return None
    indexed: dict[str, dict[str, Any]] = {}
    for raw in raw_facts:
        if not isinstance(raw, dict):
            return None
        fact_type = _text(raw.get("factType"))
        fact_key = _text(raw.get("factKey"))
        status = _text(raw.get("status"))
        if (
            raw.get("schemaRevision") != _RELEASED_FACT_SCHEMA_REVISION
            or _text(raw.get("subjectKey")) != subject_key
            or not fact_type
            or not fact_key
            or status not in _RELEASED_FACT_STATUSES
            or fact_type in indexed
        ):
            return None
        fact = _canonical(raw)
        indexed[fact_type] = fact
        evidence[fact_key] = {
            "id": fact_key,
            "sourceType": "released_canonical_fact",
            "releaseId": release_id,
            "subjectKey": subject_key,
            "factType": fact_type,
            "status": status,
            "compilerRuleRevision": _text(raw.get("compilerRuleRevision")),
        }
    return indexed


def _verified_fact_value(
    facts: dict[str, dict[str, Any]],
    fact_type: str,
) -> Any:
    fact = facts.get(fact_type)
    return fact.get("value") if isinstance(fact, dict) and fact.get("status") == "verified" else None


def _valid_capability_value(fact_type: str, value: Any) -> bool:
    if fact_type == "socket_count":
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0
    return isinstance(value, bool)


def _released_capability_facts(
    facts: dict[str, dict[str, Any]],
    options_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    allowed_fact = facts.get("allowed_enhancement_options")
    allowed_ids = (
        _texts(allowed_fact.get("value") or [])
        if isinstance(allowed_fact, dict)
        and allowed_fact.get("status") == "verified"
        and isinstance(allowed_fact.get("value"), list)
        else None
    )
    projected: dict[str, dict[str, Any]] = {}
    for public_key, (
        fact_type,
        _expected_type,
        _allow_field,
        option_types,
    ) in _CAPABILITY_FACT_SPECS.items():
        fact = facts.get(fact_type)
        value = fact.get("value") if isinstance(fact, dict) else None
        if (
            not isinstance(fact, dict)
            or fact.get("status") != "verified"
            or not _valid_capability_value(fact_type, value)
        ):
            status = "pending"
            value = None
        elif value in (False, 0):
            status = "unavailable"
        elif allowed_ids is None:
            status = "pending"
            value = None
        else:
            status = "verified"
        options = []
        if status == "verified" and allowed_ids is not None and options_by_id is not None:
            options = [
                option_id
                for option_id in allowed_ids
                if isinstance(options_by_id.get(option_id), dict)
                and options_by_id[option_id].get("optionType") in option_types
            ]
        projected[public_key] = {
            "status": status,
            "value": value,
            "options": sorted(options),
        }
    return projected


def _compatibility_capabilities(
    capability_facts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    socket = capability_facts.get("socket") or {}
    enchant = capability_facts.get("enchant") or {}
    embellishment = capability_facts.get("embellishment") or {}
    socket_count = (
        socket.get("value")
        if socket.get("status") in {"verified", "unavailable"}
        and isinstance(socket.get("value"), int)
        and not isinstance(socket.get("value"), bool)
        else 0
    )
    return {
        "socketCount": socket_count,
        "canEnchant": (
            enchant.get("status") == "verified"
            and enchant.get("value") is True
        ),
        "canEmbellish": (
            embellishment.get("status") == "verified"
            and embellishment.get("value") is True
        ),
    }


def _released_fact_refs(facts: dict[str, dict[str, Any]]) -> list[str]:
    return _texts(fact.get("factKey") for fact in facts.values())


def _released_equipment_uniqueness(
    facts: dict[str, dict[str, Any]],
) -> tuple[str, int] | None:
    value = _verified_fact_value(facts, "equipment_uniqueness")
    if not isinstance(value, dict) or not isinstance(
        value.get("isUnique"), bool
    ):
        return None
    if value["isUnique"] is False:
        return ("", 0) if set(value) == {"isUnique"} else None
    group = _strict_unique_group(value.get("groupId"))
    limit = _positive_integer(value.get("limit"))
    if (
        set(value) != {"isUnique", "groupId", "limit"}
        or not group
        or not limit
    ):
        return None
    return group, limit


def _released_executable_item_options(
    facts: dict[str, dict[str, Any]],
    requested_item_id: str,
    requested_variant_key: str,
    item_level: int,
) -> tuple[dict[str, Any], dict[str, Any] | None] | None:
    value = _verified_fact_value(facts, "executable_item_options")
    if (
        not isinstance(value, dict)
        or set(value).difference(
            {
                "itemId",
                "variantKey",
                "options",
                "enhancementManagement",
            }
        )
        or _text(value.get("itemId")) != requested_item_id
        or _text(value.get("variantKey")) != requested_variant_key
    ):
        return None
    options = value.get("options")
    if (
        not isinstance(options, dict)
        or not options
        or set(options).difference(_EXECUTABLE_SIMC_OPTION_FIELDS)
        or not all(
            isinstance(option_value, str) and bool(option_value.strip())
            for option_value in options.values()
        )
        or not _text(options.get("bonus_id"))
        or not _text(options.get("ilevel")).isdigit()
        or int(_text(options.get("ilevel"))) != item_level
    ):
        return None
    management = project_validated_enhancement_management(
        options,
        value.get("enhancementManagement"),
        gear_socket_authority.CAPABILITY_REVISION,
    )
    present_enhancement_fields = {
        field
        for field in (
            "embellishment",
            "enchant_id",
            "gem_bonus_id",
            "gem_id",
            "gem_ilevel",
        )
        if field in options
    }
    if present_enhancement_fields and management is None:
        return None
    if not present_enhancement_fields and "enhancementManagement" in value:
        return None
    return _canonical(options), management


def _released_item_projection(
    requested_item_id: str,
    record: Any,
    runtime_authority: dict[str, Any],
    evidence: dict[str, dict[str, Any]],
    release_id: str,
) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    payload = _json_value(record.get("payload"), {})
    payload = payload if isinstance(payload, dict) else {}
    subject_key = f"item:{requested_item_id}"
    facts = _released_facts(payload, subject_key, evidence, release_id)
    if facts is None:
        return None
    identity = _verified_fact_value(facts, "item_identity")
    allowed_slots = _verified_fact_value(facts, "slot_compatibility")
    if (
        not isinstance(identity, dict)
        or _text(identity.get("itemId")) != requested_item_id
        or not isinstance(allowed_slots, list)
        or not _texts(allowed_slots)
    ):
        return None
    allowed_slots = _texts(allowed_slots)
    playable_classes, playable_specs = _playable_scope(runtime_authority)
    capability_facts = _released_capability_facts(facts)
    compatibility = _compatibility_capabilities(capability_facts)
    item_set = _verified_fact_value(facts, "item_set_membership")
    uniqueness = _released_equipment_uniqueness(facts)
    if uniqueness is None:
        return None
    base_stats = _verified_fact_value(facts, "static_stats")
    base_stats = _authority_stat_map(base_stats) if isinstance(base_stats, dict) else {}
    projected = {
        "itemId": requested_item_id,
        # Display/media fields remain inert transport. They never write static
        # identity, compatibility, capability, or legality facts.
        "displayName": _text(
            payload.get("displayName")
            or payload.get("name")
            or record.get("name")
        ),
        "allowedSlots": allowed_slots,
        "inventoryType": (
            _text(identity.get("inventoryType"))
            or (
                "weapon"
                if set(allowed_slots).intersection({"main_hand", "off_hand"})
                else allowed_slots[0]
            )
        ),
        "allowedClassKeys": playable_classes,
        "allowedSpecKeys": playable_specs,
        "armorType": _text(identity.get("armorType")),
        "weaponType": _text(identity.get("weaponType")),
        "handedness": _text(identity.get("handedness")),
        "uniqueGroupId": uniqueness[0],
        "uniqueLimit": uniqueness[1],
        "equipmentUniqueness": (
            {
                "isUnique": True,
                "groupId": uniqueness[0],
                "limit": uniqueness[1],
            }
            if uniqueness[0]
            else {"isUnique": False}
        ),
        "itemSetId": _text(item_set) if item_set is not False else "",
        "baseStats": base_stats,
        "baseCapabilities": compatibility,
        "socketCount": compatibility["socketCount"],
        "allowedGemOptionIds": [],
        "allowedEnchantOptionIds": [],
        "allowedEmbellishmentOptionIds": [],
        "allowedCraftedOptionIds": [],
        "allowedCatalystOptionIds": [],
        "dynamicEffects": [],
        "capabilityFacts": capability_facts,
        "_releasedFacts": facts,
        "canonicalFactRefIds": _released_fact_refs(facts),
        "sourceRefIds": _released_fact_refs(facts),
    }
    if media := _verified_item_media(payload):
        projected.update(media)
    return projected


def _released_variant_projection(
    requested_item_id: str,
    requested_variant_key: str,
    record: Any,
    evidence: dict[str, dict[str, Any]],
    release_id: str,
) -> dict[str, Any] | None:
    if not requested_variant_key or not isinstance(record, dict):
        return None
    payload = _json_value(record.get("payload"), {})
    payload = payload if isinstance(payload, dict) else {}
    subject_key = f"item:{requested_item_id}/variant:{requested_variant_key}"
    facts = _released_facts(payload, subject_key, evidence, release_id)
    if facts is None:
        return None
    identity = _verified_fact_value(facts, "item_identity")
    allowed_slots = _verified_fact_value(facts, "slot_compatibility")
    if (
        not isinstance(identity, dict)
        or _text(identity.get("itemId")) != requested_item_id
        or _text(identity.get("variantKey")) != requested_variant_key
        or not isinstance(allowed_slots, list)
        or not _texts(allowed_slots)
    ):
        return None
    track = _verified_fact_value(facts, "variant_track")
    stats = _verified_fact_value(facts, "static_stats")
    item_set = _verified_fact_value(facts, "item_set_membership")
    capability_facts = _released_capability_facts(facts)
    compatibility = _compatibility_capabilities(capability_facts)
    item_level = (
        _int(track.get("itemLevel"))
        if isinstance(track, dict)
        and _text(track.get("itemId")) == requested_item_id
        and _text(track.get("variantKey")) == requested_variant_key
        else 0
    )
    executable = _released_executable_item_options(
        facts,
        requested_item_id,
        requested_variant_key,
        item_level,
    )
    if not item_level or executable is None:
        return None
    executable_options, enhancement_management = executable
    projected = {
        "variantKey": requested_variant_key,
        "itemId": requested_item_id,
        "status": "verified",
        "itemLevel": item_level,
        "statDeltas": {},
        "simcOptions": executable_options,
        "itemSetId": _text(item_set) if item_set is not False else "",
        "capabilityOverrides": compatibility,
        "dynamicEffects": [],
        "capabilityFacts": capability_facts,
        "_releasedFacts": facts,
        "canonicalFactRefIds": _released_fact_refs(facts),
        "sourceRefIds": _released_fact_refs(facts),
    }
    if isinstance(stats, dict):
        projected["resolvedStats"] = _authority_stat_map(stats)
    if enhancement_management:
        projected["enhancementManagement"] = enhancement_management
    return projected


def _released_option_projection(
    requested_option_id: str,
    record: Any,
    evidence: dict[str, dict[str, Any]],
    release_id: str,
) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    payload = _json_value(record.get("payload"), {})
    payload = payload if isinstance(payload, dict) else {}
    facts = _released_facts(
        payload,
        f"option:{requested_option_id}",
        evidence,
        release_id,
    )
    if facts is None:
        return None
    value = _verified_fact_value(facts, "enhancement_option")
    if (
        not isinstance(value, dict)
        or _text(value.get("optionId")) != requested_option_id
    ):
        return None
    option_type = _normalized_option_type(value.get("optionType"))
    effect = value.get("effect")
    applicable = value.get("applicableScopes")
    if (
        option_type not in _OPTION_ALLOW_FIELDS
        or not isinstance(effect, dict)
        or not effect
        or not isinstance(applicable, list)
        or not _texts(applicable)
    ):
        return None
    refs = _released_fact_refs(facts)
    stat_deltas = value.get("statDeltas")
    stat_deltas = (
        _authority_stat_map(stat_deltas)
        if isinstance(stat_deltas, dict)
        else {}
    )
    return {
        "optionId": requested_option_id,
        "optionType": option_type,
        "displayName": _text(payload.get("displayName") or record.get("name")),
        "applicableSlots": _texts(applicable),
        "statDeltas": stat_deltas,
        "attributeStaticFactsStatus": (
            "verified" if stat_deltas else "unavailable"
        ),
        "simcOptions": _canonical(effect),
        "uniqueGroupId": _strict_unique_group(value.get("uniqueGroupId")),
        "uniqueLimit": _positive_integer(value.get("uniqueLimit")),
        "canonicalFactRefIds": refs,
        "sourceRefIds": refs,
    }


def _finalize_released_capability_projection(
    owner: dict[str, Any],
    options_by_id: dict[str, dict[str, Any]],
) -> None:
    facts = owner.pop("_releasedFacts", None)
    if not isinstance(facts, dict):
        return
    capability_facts = _released_capability_facts(facts, options_by_id)
    compatibility = _compatibility_capabilities(capability_facts)
    owner["capabilityFacts"] = capability_facts
    if isinstance(owner.get("baseCapabilities"), dict):
        owner["baseCapabilities"] = {
            **owner["baseCapabilities"],
            **compatibility,
        }
        owner["socketCount"] = compatibility["socketCount"]
    elif isinstance(owner.get("capabilityOverrides"), dict):
        owner["capabilityOverrides"] = compatibility
    option_fields = {
        "allowedGemOptionIds": ("socket", {"gem"}),
        "allowedEnchantOptionIds": ("enchant", {"enchant", "runeforge"}),
        "allowedEmbellishmentOptionIds": (
            "embellishment",
            {"embellishment"},
        ),
        "allowedCraftedOptionIds": ("embellishment", {"crafted"}),
    }
    for field, (category, option_types) in option_fields.items():
        values = [
            option_id
            for option_id in capability_facts[category]["options"]
            if options_by_id[option_id]["optionType"] in option_types
        ]
        owner[field] = values
        if isinstance(owner.get("baseCapabilities"), dict):
            owner["baseCapabilities"][field] = list(values)
        if isinstance(owner.get("capabilityOverrides"), dict):
            owner["capabilityOverrides"][field] = list(values)


def _tier_set_id_from_source(source: Any) -> str:
    if not isinstance(source, dict) or _text(source.get("sourceType")) != "tier_set":
        return ""
    payload = _json_value(source.get("payload"), {})
    payload = payload if isinstance(payload, dict) else {}
    if _text(payload.get("authority")) != ITEM_METADATA_SOURCE:
        return ""
    return _text(
        payload.get("setId")
        or payload.get("set_id")
        or payload.get("itemSetId")
        or payload.get("item_set_id")
    )


def _source_is_verified(source: Any) -> bool:
    if not isinstance(source, dict):
        return False
    statuses = {
        _text(source.get("status")).lower(),
        _text(source.get("sourceStatus")).lower(),
    }
    return "verified" in statuses or bool(_tier_set_id_from_source(source))


def _project_base_capabilities(
    payload: dict[str, Any],
    canonical_slot: str,
    type_metadata: dict[str, Any],
    capability_revision: str,
) -> dict[str, Any]:
    explicit = _json_value(payload.get("baseCapabilities"), {})
    explicit = explicit if isinstance(explicit, dict) else {}
    derived = item_mod_capabilities(
        payload=payload,
        slot=canonical_slot,
        item={"slot": canonical_slot, **type_metadata},
    )
    if capability_revision == gear_socket_authority.LEGACY_CAPABILITY_REVISION:
        explicit = {
            **explicit,
            **{
                field: payload[field]
                for field in ("socketCount", "canEnchant", "canEmbellish")
                if field in payload
            },
        }
        socket_count = max(
            _non_negative_int(explicit.get("socketCount")),
            _non_negative_int(derived.get("socketCount")),
        )
    else:
        explicit = {
            **explicit,
            **{
                field: payload[field]
                for field in ("canEnchant", "canEmbellish")
                if field in payload
            },
        }
        socket_count = _v2_materialized_socket_count(
            explicit.get("socketCount"),
            payload.get("socketEvidence"),
            capability_revision,
        )
    return {
        **explicit,
        "socketCount": socket_count if socket_count is not None else 0,
        "canEnchant": explicit.get("canEnchant") is True or derived.get("canEnchant") is True,
        "canEmbellish": explicit.get("canEmbellish") is True or derived.get("canEmbellish") is True,
    }


def _v2_materialized_socket_count(
    value: Any,
    evidence_value: Any,
    capability_revision: str,
) -> int | None:
    if capability_revision != gear_socket_authority.CAPABILITY_REVISION:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    evidence = _json_value(evidence_value, {})
    if not isinstance(evidence, dict):
        return None
    minimum_total = evidence.get("minimumTotal")
    if (
        evidence.get("schemaRevision") != gear_socket_authority.SOCKET_FACT_SCHEMA_REVISION
        or evidence.get("authorityRevision") != gear_socket_authority.CAPABILITY_REVISION
        or isinstance(minimum_total, bool)
        or not isinstance(minimum_total, int)
        or minimum_total < 0
        or minimum_total != value
    ):
        return None
    claims = evidence.get("claims")
    if not isinstance(claims, list):
        return None
    if value == 0:
        return 0 if not claims else None
    if not claims:
        return None
    claim_totals = []
    for claim in claims:
        if not isinstance(claim, dict):
            return None
        claim_total = claim.get("minimumTotal")
        if (
            isinstance(claim_total, bool)
            or not isinstance(claim_total, int)
            or claim_total <= 0
            or any(
                not _valid_socket_evidence_text(claim.get(field))
                for field in ("scope", "source", "sourceRevision")
            )
        ):
            return None
        claim_totals.append(claim_total)
    if max(claim_totals) != value:
        return None
    return value


def _valid_socket_evidence_text(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value == value.strip()
        and 0 < len(value) <= _MAX_SOCKET_EVIDENCE_TEXT_CHARS
    )


def _verified_item_media(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Project the catalog's exact verified icon fact for import display only."""

    metadata = _json_value(payload.get("_metadata"), {})
    metadata = metadata if isinstance(metadata, dict) else {}
    icon_url = _text(metadata.get("iconUrl"))
    game_asset = metadata.get("gameAsset")
    game_asset = game_asset if isinstance(game_asset, dict) else {}
    if (
        not icon_url
        or _text(game_asset.get("status")) != "verified"
        or (
            _text(game_asset.get("iconUrl"))
            and _text(game_asset.get("iconUrl")) != icon_url
        )
        or not _text(game_asset.get("source"))
    ):
        return None
    return {
        "iconUrl": icon_url,
        "gameAsset": {
            "status": "verified",
            "source": _text(game_asset.get("source")),
            "iconUrl": icon_url,
        },
    }


def _project_item(
    requested_item_id: str,
    record: Any,
    source_records: Any,
    runtime_authority: dict[str, Any],
    evidence: dict[str, dict[str, Any]],
    capability_revision: str,
    season_revision: str,
) -> dict[str, Any] | None:
    if not isinstance(record, dict) or _text(record.get("sourceStatus")) != "verified":
        return None
    payload = _json_value(record.get("payload"), {})
    payload = payload if isinstance(payload, dict) else {}
    sources = source_records if isinstance(source_records, list) else []
    verified_sources = [
        source for source in sources
        if isinstance(source, dict)
        and _text(source.get("id"))
        and _source_is_verified(source)
    ]
    if not verified_sources:
        return None
    item_set_ids = _texts(
        [
            *(record.get("itemSetIds") or []),
            payload.get("itemSetId"),
            *(_tier_set_id_from_source(source) for source in verified_sources),
        ]
    )
    if len(item_set_ids) > 1:
        return None
    source_ref_ids = []
    for source in verified_sources:
        source_id = _evidence_id("source", source.get("id"))
        source_ref_ids.append(source_id)
        evidence[source_id] = {
            "id": source_id,
            "sourceType": _text(source.get("sourceType")) or "postgres_gear_source",
            "sourceRevision": _text(source.get("seasonRevision")),
            "sourceKey": _text(source.get("sourceKey")),
            "verificationStatus": "verified",
            "sourceStatus": _text(source.get("sourceStatus")) or "unknown",
            "updatedAt": _text(source.get("updatedAt")),
        }
    playable_classes, playable_specs = _playable_scope(runtime_authority)
    canonical_slot = _text(item_slot_from_payload(payload) or record.get("slot"))
    type_metadata = item_type_metadata_from_payload(payload)
    type_metadata = type_metadata if isinstance(type_metadata, dict) else {}
    weapon_type = _text(payload.get("weaponType") or type_metadata.get("weaponType"))
    handedness = _text(payload.get("handedness"))
    if not handedness and weapon_type:
        handedness = _text(
            gear_item_handedness_fields({"weaponType": weapon_type}).get("handedness")
        )
    requested_spec = _text(runtime_authority.get("requestedClassSpec"))
    weapon_mode = _text(
        (_json_value(runtime_authority.get("ruleParameters"), {}) or {})
        .get("weaponModesByClassSpec", {})
        .get(requested_spec)
    )
    if payload.get("allowedSlots"):
        allowed_slots = _texts(payload.get("allowedSlots"))
    elif handedness == "one_hand":
        allowed_slots = ["main_hand", "off_hand"]
    elif handedness == "two_hand" and weapon_mode == "dual_wield_2h":
        allowed_slots = ["main_hand", "off_hand"]
    else:
        allowed_slots = _texts(EQUIVALENT_GEAR_SLOTS.get(canonical_slot, [canonical_slot]))
    inventory_type = _text(payload.get("inventoryType"))
    if not inventory_type:
        inventory_type = "weapon" if handedness in {"one_hand", "two_hand", "ranged"} else canonical_slot
    base_capabilities = _project_base_capabilities(
        payload,
        canonical_slot,
        type_metadata,
        capability_revision,
    )
    socket_count = base_capabilities["socketCount"]
    item_id = _text(record.get("id")) or requested_item_id
    projected = {
        "itemId": item_id,
        "displayName": _text(payload.get("displayName") or payload.get("name") or record.get("name")),
        "allowedSlots": allowed_slots,
        "inventoryType": inventory_type,
        "allowedClassKeys": _texts(payload.get("allowedClassKeys") or playable_classes),
        "allowedSpecKeys": _texts(payload.get("allowedSpecKeys") or playable_specs),
        "armorType": _text(payload.get("armorType") or type_metadata.get("armorType")),
        "weaponType": weapon_type,
        "handedness": handedness,
        "uniqueGroupId": _strict_unique_group(payload.get("uniqueGroupId")),
        "uniqueLimit": _positive_integer(payload.get("uniqueLimit")),
        "itemSetId": item_set_ids[0] if item_set_ids else "",
        "baseStats": _static_stats(payload.get("baseStats"), payload.get("itemStats")),
        "baseCapabilities": base_capabilities,
        "socketCount": socket_count,
        "allowedGemOptionIds": [],
        "allowedEnchantOptionIds": [],
        "allowedEmbellishmentOptionIds": [],
        "allowedCraftedOptionIds": [],
        "allowedCatalystOptionIds": [],
        "dynamicEffects": _json_value(payload.get("dynamicEffects"), []),
        "sourceRefIds": _texts(source_ref_ids),
    }
    if (
        capability_revision == gear_socket_authority.CAPABILITY_REVISION
        and gear_socket_authority.is_verified_radiant_jewelbinder_socket(
            {"slot": canonical_slot, "payload": payload},
            season_revision,
        )
    ):
        projected["radiantJewelbinderSocketEligibility"] = True
    if media := _verified_item_media(payload):
        projected.update(media)
    return projected


def _variant_capability_overrides(
    payload: dict[str, Any],
    simc_options: dict[str, Any],
    capability_revision: str,
    enhancement_management_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    explicit = _json_value(payload.get("capabilityOverrides"), {})
    explicit = explicit if isinstance(explicit, dict) else {}
    overrides = dict(explicit)
    if capability_revision == gear_socket_authority.LEGACY_CAPABILITY_REVISION:
        gem_count = len(
            [
                token
                for token in _text(simc_options.get("gem_id")).split("/")
                if token.strip()
            ]
        )
        if "socketCount" in explicit or gem_count:
            overrides["socketCount"] = max(
                _non_negative_int(explicit.get("socketCount")),
                gem_count,
            )
    else:
        socket_count = _v2_materialized_socket_count(
            explicit.get("socketCount"),
            payload.get("socketEvidence"),
            capability_revision,
        )
        overrides.pop("socketCount", None)
        if socket_count is not None and socket_count > 0:
            overrides["socketCount"] = socket_count
    management_fields = (
        enhancement_management_fields
        if isinstance(enhancement_management_fields, dict)
        else {}
    )
    raw_embellishment = bool(_text(simc_options.get("embellishment")))
    crafted_stats = bool(_text(simc_options.get("crafted_stats")))
    if (
        capability_revision == gear_socket_authority.CAPABILITY_REVISION
        and management_fields.get("embellishment") == "source_only"
    ):
        overrides["canEmbellish"] = False
        return overrides
    proves_embellishment = crafted_stats or (
        raw_embellishment
        and (
            capability_revision == gear_socket_authority.LEGACY_CAPABILITY_REVISION
            or management_fields.get("embellishment") == "editor_managed"
        )
    )
    if "canEmbellish" in explicit or proves_embellishment:
        overrides["canEmbellish"] = (
            explicit.get("canEmbellish") is True or proves_embellishment
        )
    return overrides


def _project_variant(
    requested_item_id: str,
    requested_variant_key: str,
    record: Any,
    item_source_refs: Iterable[str],
    evidence: dict[str, dict[str, Any]],
    capability_revision: str,
) -> dict[str, Any] | None:
    if (
        not requested_variant_key
        or not isinstance(record, dict)
        or _text(record.get("status")) != "verified"
        or _text(record.get("itemId")) != requested_item_id
        or not _variant_key_matches(requested_variant_key, record.get("variantKey"))
    ):
        return None
    variant_id = _text(record.get("id"))
    if not variant_id:
        return None
    payload = _json_value(record.get("payload"), {})
    payload = payload if isinstance(payload, dict) else {}
    evidence_id = _evidence_id("variant", variant_id)
    evidence[evidence_id] = {
        "id": evidence_id,
        "sourceType": _text(record.get("sourceType")) or "postgres_gear_variant",
        "sourceRevision": _text(record.get("updatedAt")),
        "variantKey": requested_variant_key,
    }
    overlay = _json_value(payload.get("overlay"), {})
    overlay = overlay if isinstance(overlay, dict) else {}
    if capability_revision == gear_socket_authority.CAPABILITY_REVISION:
        overlay_overrides = overlay.get("capabilityOverrides")
        if isinstance(overlay_overrides, dict):
            overlay["capabilityOverrides"] = dict(overlay_overrides)
            overlay["capabilityOverrides"].pop("socketCount", None)
    simc_options = _json_value(record.get("simcOptions"), {})
    simc_options = simc_options if isinstance(simc_options, dict) else {}
    management = project_validated_enhancement_management(
        simc_options,
        payload.get("enhancementManagement"),
        capability_revision,
    )
    validated_classifications = validated_enhancement_management_fields(
        simc_options,
        management,
        capability_revision,
    )
    projected = {
        "variantKey": requested_variant_key,
        "itemId": requested_item_id,
        "status": "verified",
        "itemLevel": _int(record.get("itemLevel")),
        "statDeltas": _authority_stat_map(payload.get("statDeltas"))
        if "statDeltas" in payload
        else {},
        "simcOptions": simc_options,
        "itemSetId": _text(payload.get("itemSetId")),
        "capabilityOverrides": _variant_capability_overrides(
            payload,
            simc_options,
            capability_revision,
            validated_classifications,
        ),
        "dynamicEffects": _json_value(payload.get("dynamicEffects"), []),
        "sourceRefIds": _texts([*item_source_refs, evidence_id]),
    }
    if management:
        projected["enhancementManagement"] = management
    if "resolvedStats" in payload:
        projected["resolvedStats"] = _authority_stat_map(payload.get("resolvedStats"))
    elif "itemStats" in payload:
        projected["resolvedStats"] = _authority_stat_map(payload.get("itemStats"))
    if overlay:
        projected["overlay"] = overlay
    return projected


def _merge_equivalent_variant_candidates(candidates: Iterable[Any]) -> dict[str, Any] | None:
    projected = [candidate for candidate in candidates if isinstance(candidate, dict)]
    if not projected:
        return None
    semantic_values = [
        _canonical({key: value for key, value in candidate.items() if key != "sourceRefIds"})
        for candidate in projected
    ]
    if any(value != semantic_values[0] for value in semantic_values[1:]):
        return None
    merged = dict(projected[0])
    merged["sourceRefIds"] = _texts(
        source
        for candidate in projected
        for source in candidate.get("sourceRefIds", [])
    )
    return _canonical(merged)


def _normalized_option_type(value: Any) -> str:
    normalized = _text(value).lower()
    return {
        "socket": "gem",
        "gem": "gem",
        "enchant": "enchant",
        "runeforge": "runeforge",
        "embellishment": "embellishment",
        "crafted_stats": "crafted",
        "crafted": "crafted",
        "catalyst": "catalyst",
    }.get(normalized, normalized)


def _project_option(
    requested_option_id: str,
    record: Any,
    evidence: dict[str, dict[str, Any]],
    eligibility_context: dict[str, Any],
) -> dict[str, Any] | None:
    if (
        not isinstance(record, dict)
        or _text(record.get("status")) != "verified"
        or record.get("isVisible") is not True
        or _text(record.get("optionKey")) != requested_option_id
    ):
        return None
    option_type = _normalized_option_type(record.get("optionType"))
    if option_type not in _OPTION_ALLOW_FIELDS:
        return None
    payload = _json_value(record.get("payload"), {})
    payload = payload if isinstance(payload, dict) else {}
    unique_groups = _option_unique_groups(record, payload)
    if len(unique_groups) > 1:
        return None
    packaged_facts = None
    if "statDeltas" in payload:
        stat_deltas = _authority_stat_map(payload.get("statDeltas"))
        attribute_static_facts_status = "verified"
    elif "itemStats" in payload:
        stat_deltas = _authority_stat_map(payload.get("itemStats"))
        attribute_static_facts_status = "verified"
    else:
        packaged_facts = option_static_facts(
            option_type,
            _json_value(record.get("simcOptions"), {}),
            eligibility_context,
        )
        if packaged_facts is not None:
            stat_deltas = _authority_stat_map(packaged_facts.get("statDeltas"))
            attribute_static_facts_status = _text(packaged_facts.get("status"))
        else:
            stat_deltas = {}
            attribute_static_facts_status = _text(payload.get("attributeStaticFactsStatus"))
            if attribute_static_facts_status not in {"not_applicable"}:
                attribute_static_facts_status = "unavailable"
    evidence_id = _evidence_id("option", requested_option_id)
    evidence[evidence_id] = {
        "id": evidence_id,
        "sourceType": _text(payload.get("evidenceSource")) or "postgres_gear_option",
        "sourceRevision": _text(record.get("updatedAt")),
        "optionId": requested_option_id,
    }
    projected = {
        "optionId": requested_option_id,
        "optionType": option_type,
        "displayName": _text(payload.get("displayName") or record.get("name")),
        "applicableSlots": _texts(record.get("applicableSlots") or []),
        "statDeltas": stat_deltas,
        "attributeStaticFactsStatus": attribute_static_facts_status,
        "simcOptions": _json_value(record.get("simcOptions"), {}),
        "uniqueGroupId": unique_groups[0] if unique_groups else "",
        "uniqueLimit": _option_unique_limit(record, payload),
        "sourceRefIds": [evidence_id],
    }
    if packaged_facts is not None:
        projected["attributeStaticFactsRevision"] = STATIC_FACT_RULE_REVISION
        projected["attributeStaticFactsSourceRef"] = _text(packaged_facts.get("sourceRef"))
        effect_classification = _text(packaged_facts.get("effectClassification"))
        if effect_classification:
            projected["attributeEffectClassification"] = effect_classification
    return projected


def _selected_option_ids(intent: dict[str, Any]) -> list[str]:
    values = []
    for selection in intent["slots"].values():
        values.extend(selection.get("gemOptionIds", []))
        values.extend(
            selection.get(field, "")
            for field in (
                "enchantOptionId",
                "embellishmentOptionId",
                "craftedOptionId",
                "catalystOptionId",
            )
        )
    return _texts(values)


def _link_allowed_options(
    intent: dict[str, Any],
    items_by_id: dict[str, dict[str, Any]],
    options_by_id: dict[str, dict[str, Any]],
) -> None:
    for slot, selection in intent["slots"].items():
        item = items_by_id.get(selection["itemId"])
        if not isinstance(item, dict):
            continue
        for option_id in _selected_option_ids({**intent, "slots": {slot: selection}}):
            option = options_by_id.get(option_id)
            if not isinstance(option, dict):
                continue
            applicable = option.get("applicableSlots") or []
            if applicable and slot not in applicable and "*" not in applicable:
                continue
            field = _OPTION_ALLOW_FIELDS[option["optionType"]]
            item[field] = _texts([*item.get(field, []), option_id])
            item["baseCapabilities"][field] = list(item[field])


def build_gear_authority_context_from_rows(
    selection_intent: Any,
    runtime_authority: Any,
    *,
    manifest: dict[str, Any],
    dependency_vector: dict[str, Any],
    item_rows: Iterable[Any],
    option_rows: Iterable[Any],
    missing_fields: Iterable[str] = (),
) -> dict[str, Any]:
    """Project one Authority Context from caller-owned, release-scoped rows."""

    intent, intent_issues = parse_selection_intent(selection_intent)
    if intent_issues:
        paths = ", ".join(issue.get("path", "intent") for issue in intent_issues)
        raise ValueError(f"Invalid Selection Intent: {paths}")
    runtime = runtime_authority if isinstance(runtime_authority, dict) else {}
    raw_capability_revision = dependency_vector.get("capabilityRevision")
    capability_revision = (
        raw_capability_revision if isinstance(raw_capability_revision, str) else ""
    )
    missing = [*_runtime_missing(runtime), *(_text(value) for value in missing_fields)]
    missing = [value for value in missing if value]
    evidence = _runtime_source_records(runtime)
    items_by_id: dict[str, dict[str, Any]] = {}
    variants_by_key: dict[str, dict[str, Any]] = {}
    variant_candidates_by_key: dict[str, list[dict[str, Any]]] = {}
    for row in item_rows:
        row = list(row or ())
        requested_item_id = _text(row[0] if len(row) > 0 else "")
        requested_variant_key = _text(row[1] if len(row) > 1 else "")
        if capability_revision == gear_socket_authority.CAPABILITY_REVISION:
            item = _released_item_projection(
                requested_item_id,
                row[2] if len(row) > 2 else None,
                runtime,
                evidence,
                _text(dependency_vector.get("gearCatalogReleaseId")),
            )
        else:
            item = _project_item(
                requested_item_id,
                row[2] if len(row) > 2 else None,
                row[4] if len(row) > 4 else [],
                runtime,
                evidence,
                capability_revision,
                _text(dependency_vector.get("seasonRevision")),
            )
        if item is not None:
            items_by_id[requested_item_id] = item
        if capability_revision == gear_socket_authority.CAPABILITY_REVISION:
            variant = _released_variant_projection(
                requested_item_id,
                requested_variant_key,
                row[3] if len(row) > 3 else None,
                evidence,
                _text(dependency_vector.get("gearCatalogReleaseId")),
            )
        else:
            variant = _project_variant(
                requested_item_id,
                requested_variant_key,
                row[3] if len(row) > 3 else None,
                item.get("sourceRefIds", []) if item else [],
                evidence,
                capability_revision,
            )
        if variant is not None:
            variant_candidates_by_key.setdefault(requested_variant_key, []).append(variant)

    for requested_variant_key, candidates in variant_candidates_by_key.items():
        merged = _merge_equivalent_variant_candidates(candidates)
        if merged is not None:
            variants_by_key[requested_variant_key] = merged

    options_by_id: dict[str, dict[str, Any]] = {}
    for row in option_rows:
        row = list(row or ())
        requested_option_id = _text(row[0] if len(row) > 0 else "")
        if capability_revision == gear_socket_authority.CAPABILITY_REVISION:
            option = _released_option_projection(
                requested_option_id,
                row[1] if len(row) > 1 else None,
                evidence,
                _text(dependency_vector.get("gearCatalogReleaseId")),
            )
        else:
            option = _project_option(
                requested_option_id,
                row[1] if len(row) > 1 else None,
                evidence,
                intent["eligibilityContext"],
            )
        if option is not None:
            options_by_id[requested_option_id] = option
    if capability_revision == gear_socket_authority.CAPABILITY_REVISION:
        for owner in [*items_by_id.values(), *variants_by_key.values()]:
            _finalize_released_capability_projection(owner, options_by_id)
    else:
        _link_allowed_options(intent, items_by_id, options_by_id)

    selections = list(intent["slots"].values())
    option_ids = _selected_option_ids(intent)
    for selection in selections:
        item_id = selection["itemId"]
        variant_key = selection["variantKey"]
        if item_id not in items_by_id:
            missing.append(f"itemsById.{item_id}")
        if variant_key and variant_key not in variants_by_key:
            missing.append(f"variantsByKey.{variant_key}")
    for option_id in option_ids:
        if option_id not in options_by_id:
            missing.append(f"optionsById.{option_id}")

    context = {
        "contractRevision": AUTHORITY_CONTEXT_CONTRACT_REVISION,
        "manifest": _canonical(manifest),
        "dependencyVector": _canonical(dependency_vector),
        "itemsById": {key: items_by_id[key] for key in sorted(items_by_id)},
        "variantsByKey": {key: variants_by_key[key] for key in sorted(variants_by_key)},
        "optionsById": {key: options_by_id[key] for key in sorted(options_by_id)},
        "ruleParameters": _json_value(runtime.get("ruleParameters"), {}),
        "capabilities": _json_value(runtime.get("capabilities"), {}),
        "evidenceRecordsById": {key: evidence[key] for key in sorted(evidence)},
        "missingFields": sorted(set(missing)),
    }
    return _canonical(context)


def load_gear_authority_context(
    cursor: Any,
    selection_intent: Any,
    runtime_authority: Any,
    *,
    cache: AuthorityContextCache | None = None,
) -> dict[str, Any]:
    """Load one canonical Authority Context within a caller-owned transaction."""

    intent, intent_issues = parse_selection_intent(selection_intent)
    if intent_issues:
        paths = ", ".join(issue.get("path", "intent") for issue in intent_issues)
        raise ValueError(f"Invalid Selection Intent: {paths}")
    runtime = runtime_authority if isinstance(runtime_authority, dict) else {}
    runtime_revisions = (
        runtime.get("dependencyRevisions")
        if isinstance(runtime.get("dependencyRevisions"), dict)
        else {}
    )
    if (
        runtime_revisions.get("capabilityRevision")
        == gear_socket_authority.CAPABILITY_REVISION
    ):
        authored = intent.get("authoredAgainst")
        authored = authored if isinstance(authored, dict) else {}
        release_id = _text(authored.get("gearCatalogRevision"))
        dependency_vector = {
            "seasonRevision": _text(authored.get("seasonRevision")),
            "gearCatalogReleaseId": release_id,
            "gearCatalogRevision": release_id,
            **{
                field: _text(runtime_revisions.get(field))
                for field in _REQUIRED_RUNTIME_REVISIONS
            },
        }
        return build_gear_authority_context_from_rows(
            intent,
            runtime,
            manifest={
                "contractRevision": COMPATIBILITY_MANIFEST_REVISION,
                "manifestType": "compatibility_unavailable",
                "formalActiveManifest": False,
                "seasonRevision": dependency_vector["seasonRevision"],
                "gearCatalogReleaseId": release_id,
                "gearCatalogRevision": release_id,
            },
            dependency_vector=dependency_vector,
            item_rows=[],
            option_rows=[],
            missing_fields=["manifest.selectedGearRelease"],
        )

    cursor.execute(AUTHORITY_REVISION_SQL)
    revision_row = cursor.fetchone()
    revision_row = tuple(revision_row or ())
    revision = _revision_projection(revision_row, runtime)
    catalog_revision = revision["catalogRevision"]
    season_revision = revision["seasonRevision"]
    catalog_state = revision["catalogState"]
    websim_state = revision["websimState"]
    release_id = revision["releaseId"]
    dependency_vector = revision["dependencyVector"]
    cache_key = _cache_key(intent, dependency_vector)
    if cache is not None:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    selections = list(intent["slots"].values())
    requested_pairs = list(
        dict.fromkeys(
            (selection["itemId"], selection["variantKey"])
            for selection in selections
        )
    )
    item_ids = [item_id for item_id, _variant_key in requested_pairs]
    variant_keys = [variant_key for _item_id, variant_key in requested_pairs]
    cursor.execute(SELECTED_ITEM_VARIANT_SQL, (item_ids, variant_keys))
    item_rows = cursor.fetchall()
    option_ids = _selected_option_ids(intent)
    cursor.execute(SELECTED_OPTION_SQL, (option_ids,))
    option_rows = cursor.fetchall()

    context = build_gear_authority_context_from_rows(
        intent,
        runtime,
        manifest={
            "contractRevision": COMPATIBILITY_MANIFEST_REVISION,
            "manifestType": "compatibility",
            "formalActiveManifest": False,
            "seasonRevision": season_revision,
            "gearCatalogReleaseId": release_id,
            "gearCatalogRevision": catalog_revision,
            "catalogFingerprint": catalog_revision,
            "sourceStates": {
                "gearCatalog": catalog_state,
                "websimSync": websim_state,
            },
        },
        dependency_vector=dependency_vector,
        item_rows=item_rows,
        option_rows=option_rows,
        missing_fields=[] if season_revision else ["manifest.seasonRevision"],
    )
    if cache is not None and not context["missingFields"]:
        cache.put(cache_key, context)
    return context


__all__ = (
    "COMPATIBILITY_MANIFEST_REVISION",
    "RESOLVER_CONTEXT_CONTRACT_REVISION",
    "AUTHORITY_REVISION_SQL",
    "SELECTED_ITEM_VARIANT_SQL",
    "SELECTED_OPTION_SQL",
    "AuthorityContextCache",
    "build_gear_authority_context_from_rows",
    "candidate_authority_cache_key",
    "compatibility_catalog_revision",
    "resolver_authoring_context",
    "load_gear_authority_context",
)

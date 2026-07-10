#!/usr/bin/env python3
"""Bounded PostgreSQL projection for the canonical gear Authority Context."""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
from typing import Any, Iterable

from server.gear_contracts import parse_selection_intent, selection_signature


COMPATIBILITY_MANIFEST_REVISION = "compatibility-pg-live-v1"
AUTHORITY_CONTEXT_CONTRACT_REVISION = "gear-authority-context-v1"

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
            'status', COALESCE(
                NULLIF(source.payload_json->>'sourceStatus', ''),
                NULLIF(source.payload_json->>'status', ''),
                'unknown'
            ),
            'payload', source.payload_json,
            'updatedAt', source.updated_at::text
        ) ORDER BY source.id::text)
        FROM cache.websim_gear_sources source
        WHERE source.item_id = requested.item_id
    ), '[]'::jsonb) AS source_records
FROM requested
LEFT JOIN cache.websim_items item ON item.id = requested.item_id
LEFT JOIN cache.websim_gear_variants variant
  ON variant.item_id = requested.item_id
 AND variant.variant_key = requested.variant_key
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
)
_OPTION_ALLOW_FIELDS = {
    "gem": "allowedGemOptionIds",
    "enchant": "allowedEnchantOptionIds",
    "runeforge": "allowedEnchantOptionIds",
    "embellishment": "allowedEmbellishmentOptionIds",
    "crafted": "allowedCraftedOptionIds",
    "catalyst": "allowedCatalystOptionIds",
}


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


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


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

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def byte_size(self) -> int:
        return self._byte_size

    def get(self, key: str) -> Any | None:
        normalized = _text(key)
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


def _project_item(
    requested_item_id: str,
    record: Any,
    source_records: Any,
    runtime_authority: dict[str, Any],
    evidence: dict[str, dict[str, Any]],
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
        and _text(source.get("status") or "unknown") == "verified"
    ]
    if not verified_sources:
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
            "updatedAt": _text(source.get("updatedAt")),
        }
    playable_classes, playable_specs = _playable_scope(runtime_authority)
    allowed_slots = _texts(payload.get("allowedSlots") or [record.get("slot")])
    base_capabilities = _json_value(payload.get("baseCapabilities"), {})
    base_capabilities = base_capabilities if isinstance(base_capabilities, dict) else {}
    socket_count = payload.get("socketCount", base_capabilities.get("socketCount", 0))
    if isinstance(socket_count, bool) or not isinstance(socket_count, int):
        socket_count = 0
    base_capabilities.update(
        {
            "socketCount": socket_count,
            "canEnchant": payload.get("canEnchant", base_capabilities.get("canEnchant", False)) is True,
            "canEmbellish": payload.get("canEmbellish", base_capabilities.get("canEmbellish", False)) is True,
        }
    )
    item_id = _text(record.get("id")) or requested_item_id
    return {
        "itemId": item_id,
        "displayName": _text(payload.get("displayName") or payload.get("name") or record.get("name")),
        "allowedSlots": allowed_slots,
        "inventoryType": _text(payload.get("inventoryType") or record.get("slot")),
        "allowedClassKeys": _texts(payload.get("allowedClassKeys") or playable_classes),
        "allowedSpecKeys": _texts(payload.get("allowedSpecKeys") or playable_specs),
        "armorType": _text(payload.get("armorType")),
        "weaponType": _text(payload.get("weaponType")),
        "handedness": _text(payload.get("handedness")),
        "uniqueGroupId": _text(payload.get("uniqueGroupId")),
        "uniqueLimit": _int(payload.get("uniqueLimit")),
        "itemSetId": _text(payload.get("itemSetId")),
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


def _project_variant(
    requested_item_id: str,
    requested_variant_key: str,
    record: Any,
    item_source_refs: Iterable[str],
    evidence: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if (
        not requested_variant_key
        or not isinstance(record, dict)
        or _text(record.get("status")) != "verified"
        or _text(record.get("itemId")) != requested_item_id
        or _text(record.get("variantKey")) != requested_variant_key
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
    projected = {
        "variantKey": requested_variant_key,
        "itemId": requested_item_id,
        "status": "verified",
        "itemLevel": _int(record.get("itemLevel")),
        "statDeltas": _authority_stat_map(payload.get("statDeltas"))
        if "statDeltas" in payload
        else {},
        "simcOptions": _json_value(record.get("simcOptions"), {}),
        "itemSetId": _text(payload.get("itemSetId")),
        "capabilityOverrides": _json_value(payload.get("capabilityOverrides"), {}),
        "dynamicEffects": _json_value(payload.get("dynamicEffects"), []),
        "sourceRefIds": _texts([*item_source_refs, evidence_id]),
    }
    if "resolvedStats" in payload:
        projected["resolvedStats"] = _authority_stat_map(payload.get("resolvedStats"))
    elif "itemStats" in payload:
        projected["resolvedStats"] = _authority_stat_map(payload.get("itemStats"))
    if overlay:
        projected["overlay"] = overlay
    return projected


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
    if "statDeltas" in payload:
        stat_deltas = _authority_stat_map(payload.get("statDeltas"))
    elif "itemStats" in payload:
        stat_deltas = _authority_stat_map(payload.get("itemStats"))
    else:
        stat_deltas = {}
    evidence_id = _evidence_id("option", requested_option_id)
    evidence[evidence_id] = {
        "id": evidence_id,
        "sourceType": _text(payload.get("evidenceSource")) or "postgres_gear_option",
        "sourceRevision": _text(record.get("updatedAt")),
        "optionId": requested_option_id,
    }
    return {
        "optionId": requested_option_id,
        "optionType": option_type,
        "displayName": _text(payload.get("displayName") or record.get("name")),
        "applicableSlots": _texts(record.get("applicableSlots") or []),
        "statDeltas": stat_deltas,
        "simcOptions": _json_value(record.get("simcOptions"), {}),
        "uniqueGroupId": _text(payload.get("uniqueGroupId") or payload.get("uniqueGroup")),
        "uniqueLimit": _int(payload.get("uniqueLimit")),
        "sourceRefIds": [evidence_id],
    }


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

    cursor.execute(AUTHORITY_REVISION_SQL)
    revision_row = cursor.fetchone()
    revision_row = tuple(revision_row or ())
    catalog_revision = compatibility_catalog_revision(revision_row)
    season_revision = _text(revision_row[0] if len(revision_row) > 0 else "")
    catalog_state = _json_value(revision_row[1] if len(revision_row) > 1 else {}, {})
    websim_state = _json_value(revision_row[2] if len(revision_row) > 2 else {}, {})
    revisions = runtime.get("dependencyRevisions")
    revisions = revisions if isinstance(revisions, dict) else {}
    release_id = f"compatibility:{catalog_revision.removeprefix('compatibility-pg:')[:16]}"
    dependency_vector = {
        "seasonRevision": season_revision,
        "gearCatalogReleaseId": release_id,
        "gearCatalogRevision": catalog_revision,
        **{field: _text(revisions.get(field)) for field in _REQUIRED_RUNTIME_REVISIONS},
    }
    cache_key = _cache_key(intent, dependency_vector)
    if cache is not None:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    selections = list(intent["slots"].values())
    item_ids = [selection["itemId"] for selection in selections]
    variant_keys = [selection["variantKey"] for selection in selections]
    cursor.execute(SELECTED_ITEM_VARIANT_SQL, (item_ids, variant_keys))
    item_rows = cursor.fetchall()
    option_ids = _selected_option_ids(intent)
    cursor.execute(SELECTED_OPTION_SQL, (option_ids,))
    option_rows = cursor.fetchall()

    missing = _runtime_missing(runtime)
    if not season_revision:
        missing.append("manifest.seasonRevision")
    evidence = _runtime_source_records(runtime)
    items_by_id: dict[str, dict[str, Any]] = {}
    variants_by_key: dict[str, dict[str, Any]] = {}
    for row in item_rows:
        requested_item_id = _text(row[0] if len(row) > 0 else "")
        requested_variant_key = _text(row[1] if len(row) > 1 else "")
        item = _project_item(
            requested_item_id,
            row[2] if len(row) > 2 else None,
            row[4] if len(row) > 4 else [],
            runtime,
            evidence,
        )
        if item is not None:
            items_by_id[requested_item_id] = item
        variant = _project_variant(
            requested_item_id,
            requested_variant_key,
            row[3] if len(row) > 3 else None,
            item.get("sourceRefIds", []) if item else [],
            evidence,
        )
        if variant is not None:
            variants_by_key[requested_variant_key] = variant

    options_by_id: dict[str, dict[str, Any]] = {}
    for row in option_rows:
        requested_option_id = _text(row[0] if len(row) > 0 else "")
        option = _project_option(
            requested_option_id,
            row[1] if len(row) > 1 else None,
            evidence,
        )
        if option is not None:
            options_by_id[requested_option_id] = option
    _link_allowed_options(intent, items_by_id, options_by_id)

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

    rule_parameters = _json_value(runtime.get("ruleParameters"), {})
    capabilities = _json_value(runtime.get("capabilities"), {})
    context = {
        "contractRevision": AUTHORITY_CONTEXT_CONTRACT_REVISION,
        "manifest": {
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
        "dependencyVector": dependency_vector,
        "itemsById": {key: items_by_id[key] for key in sorted(items_by_id)},
        "variantsByKey": {key: variants_by_key[key] for key in sorted(variants_by_key)},
        "optionsById": {key: options_by_id[key] for key in sorted(options_by_id)},
        "ruleParameters": rule_parameters,
        "capabilities": capabilities,
        "evidenceRecordsById": {key: evidence[key] for key in sorted(evidence)},
        "missingFields": sorted(set(missing)),
    }
    context = _canonical(context)
    if cache is not None and not context["missingFields"]:
        cache.put(cache_key, context)
    return context


__all__ = (
    "COMPATIBILITY_MANIFEST_REVISION",
    "AUTHORITY_REVISION_SQL",
    "SELECTED_ITEM_VARIANT_SQL",
    "SELECTED_OPTION_SQL",
    "AuthorityContextCache",
    "compatibility_catalog_revision",
    "load_gear_authority_context",
)

#!/usr/bin/env python3
"""PostgreSQL repository for immutable WebSim release artifacts.

This is the sole SQL owner for Phase 4 release registry/content rows and the
retail manifest pointer. Existing WebSim tables remain mutable staging inputs.
"""

from __future__ import annotations

from contextlib import closing, contextmanager
import hashlib
import json
import os
import sqlite3
import tempfile
from typing import Any, Iterable, Mapping

try:
    from .gear_public_contract import is_public_hero_gear_projection
except ImportError:  # news_backend.py also supports direct script execution.
    from gear_public_contract import is_public_hero_gear_projection


RELEASE_SELECTED_ITEM_VARIANT_SQL = """
/* gear_release_authority_items_variants */
WITH target AS (
    SELECT %s::text AS release_id
), requested(item_id, variant_key) AS (
    SELECT * FROM unnest(%s::text[], %s::text[])
)
SELECT
    requested.item_id,
    requested.variant_key,
    CASE WHEN item.item_id IS NULL THEN NULL ELSE jsonb_build_object(
        'id', item.item_id,
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
            FROM cache.websim_gear_release_sources set_source
            WHERE set_source.release_id = target.release_id
              AND set_source.item_id = requested.item_id
              AND set_source.source_type = 'tier_set'
        ), '[]'::jsonb),
        'payload', item.payload_json,
        'updatedAt', item.source_updated_at::text
    ) END AS item_record,
    CASE WHEN variant.variant_id IS NULL THEN NULL ELSE jsonb_build_object(
        'id', variant.variant_id,
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
        'updatedAt', variant.source_updated_at::text
    ) END AS variant_record,
    COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'id', source.source_id,
            'sourceType', source.source_type,
            'sourceKey', source.source_key,
            'sourceLabel', source.source_label,
            'instanceId', source.instance_id,
            'encounterId', source.encounter_id,
            'difficultyKey', source.difficulty_key,
            'seasonRevision', source.season_revision,
            'status', COALESCE(
                NULLIF(source.payload_json->>'status', ''),
                NULLIF(source.payload_json->>'sourceStatus', ''),
                'unknown'
            ),
            'sourceStatus', COALESCE(
                NULLIF(source.payload_json->>'sourceStatus', ''),
                'unknown'
            ),
            'payload', source.payload_json,
            'updatedAt', source.source_updated_at::text
        ) ORDER BY source.source_type, source.source_id)
        FROM (
            SELECT DISTINCT ON (candidate.source_type) candidate.*
            FROM cache.websim_gear_release_sources candidate
            WHERE candidate.release_id = target.release_id
              AND candidate.item_id = requested.item_id
            ORDER BY
                candidate.source_type,
                CASE WHEN
                    LOWER(COALESCE(candidate.payload_json->>'status', '')) = 'verified'
                    OR LOWER(COALESCE(candidate.payload_json->>'sourceStatus', '')) = 'verified'
                    OR (
                        candidate.source_type = 'observed_profile'
                        AND jsonb_array_length(
                            CASE
                                WHEN jsonb_typeof(candidate.payload_json->'itemStats') = 'array'
                                THEN candidate.payload_json->'itemStats'
                                ELSE '[]'::jsonb
                            END
                        ) > 0
                    )
                    OR (
                        candidate.source_type = 'tier_set'
                        AND candidate.payload_json->>'authority' = 'Battle.net Game Data API'
                    )
                    THEN 0 ELSE 1 END,
                CASE WHEN requested.variant_key <> '' AND LEFT(
                        regexp_replace(
                            COALESCE(candidate.payload_json->>'variantKey', ''),
                            '[^A-Za-z0-9_:/.-]+',
                            '',
                            'g'
                        ),
                        240
                    ) = requested.variant_key THEN 0 ELSE 1 END,
                candidate.source_updated_at DESC,
                candidate.source_id
            LIMIT 8
        ) source
    ), '[]'::jsonb) AS source_records
FROM requested
CROSS JOIN target
LEFT JOIN cache.websim_gear_release_items item
  ON item.release_id = target.release_id
 AND item.item_id = requested.item_id
LEFT JOIN cache.websim_gear_release_variants variant
  ON variant.release_id = target.release_id
 AND variant.item_id = requested.item_id
 AND (
      variant.variant_key = requested.variant_key
      OR LEFT(
          regexp_replace(variant.variant_key, '[^A-Za-z0-9_:/.-]+', '', 'g'),
          240
      ) = requested.variant_key
 )
ORDER BY requested.item_id, requested.variant_key
"""


RELEASE_SELECTED_OPTION_SQL = """
/* gear_release_authority_options */
WITH target AS (
    SELECT %s::text AS release_id
)
SELECT
    option.option_key,
    jsonb_build_object(
        'id', option.option_id,
        'optionKey', option.option_key,
        'optionType', option.option_type,
        'name', option.name,
        'applicableSlots', option.applicable_slots_json,
        'simcOptions', option.simc_options_json,
        'status', option.status,
        'isVisible', option.is_visible,
        'payload', option.payload_json,
        'updatedAt', option.source_updated_at::text
    ) AS option_record
FROM cache.websim_gear_release_mod_options option
CROSS JOIN target
WHERE option.release_id = target.release_id
  AND option.option_key = ANY(%s::text[])
ORDER BY option.option_key
"""


class GearReleaseIntegrityError(RuntimeError):
    pass


class StaleManifestPointerError(RuntimeError):
    pass


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _json_param(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _canonical_rows(rows: Any) -> list[dict[str, Any]]:
    # Callers serialize rows before hashing or inserting them.  Retaining the
    # original row objects here avoids a whole-catalog deep copy at every
    # summary/seal boundary while preserving the exact canonical byte sort.
    values = [row for row in rows or [] if isinstance(row, dict)]
    return sorted(values, key=lambda row: _canonical_bytes(row))


@contextmanager
def _borrowed_connection(connection):
    """Yield a parent-owned transaction connection without closing it."""

    yield connection


def _selected_option_ids(selection_intent: Any) -> list[str]:
    intent = selection_intent if isinstance(selection_intent, dict) else {}
    selected = set()
    for selection in (intent.get("slots") or {}).values():
        if not isinstance(selection, dict):
            continue
        selected.update(_text(value) for value in selection.get("gemOptionIds") or [])
        selected.update(
            _text(selection.get(field))
            for field in (
                "enchantOptionId",
                "embellishmentOptionId",
                "craftedOptionId",
                "catalystOptionId",
            )
        )
    return sorted(value for value in selected if value)


def _released_allowed_option_ids(*records: Any) -> list[str]:
    """Read option identities only from verified Facts in selected release rows."""

    allowed: set[str] = set()
    for record in records:
        payload = (
            record.get("payload")
            if isinstance(record, dict)
            and isinstance(record.get("payload"), dict)
            else {}
        )
        raw_facts = payload.get("canonicalFacts")
        if not isinstance(raw_facts, list):
            continue
        matching = [
            fact
            for fact in raw_facts
            if isinstance(fact, dict)
            and fact.get("schemaRevision") == "gear-canonical-fact-v1"
            and _text(fact.get("factType"))
            == "allowed_enhancement_options"
        ]
        if len(matching) != 1:
            continue
        fact = matching[0]
        value = fact.get("value")
        if fact.get("status") != "verified" or not isinstance(value, list):
            continue
        allowed.update(_text(option_id) for option_id in value)
    return sorted(option_id for option_id in allowed if option_id)


def _public_enhancement_by_slot(selection_intent: Any) -> dict[str, dict[str, Any]]:
    """Project only canonical enhancement identities from a validated release intent."""

    intent = selection_intent if isinstance(selection_intent, dict) else {}
    slots = intent.get("slots") if isinstance(intent.get("slots"), dict) else {}
    result: dict[str, dict[str, Any]] = {}
    for slot, selection in slots.items():
        normalized_slot = _text(slot)
        if not normalized_slot or not isinstance(selection, dict):
            continue
        enhancement: dict[str, Any] = {}
        gem_option_ids = [
            _text(value)
            for value in selection.get("gemOptionIds") or []
            if _text(value)
        ]
        if gem_option_ids:
            enhancement["gemOptionIds"] = gem_option_ids
        for field in ("enchantOptionId", "embellishmentOptionId"):
            value = _text(selection.get(field))
            if value:
                enhancement[field] = value
        if enhancement:
            result[normalized_slot] = enhancement
    return _canonical(result)


def _observed_release_variant_record(
    requested_variant: str,
    item_record: Any,
    source_records: Any,
) -> dict[str, Any] | None:
    """Project an exact observed variant from immutable release source evidence."""

    try:
        from .websim_payload import (
            normalize_option_value,
            observed_gear_simc_options,
            observed_item_level,
            observed_variant_stat_payload_fields,
        )
    except ImportError:
        from websim_payload import (
            normalize_option_value,
            observed_gear_simc_options,
            observed_item_level,
            observed_variant_stat_payload_fields,
        )

    requested = _text(requested_variant)
    item = item_record if isinstance(item_record, dict) else {}
    for source in source_records if isinstance(source_records, list) else []:
        if not isinstance(source, dict):
            continue
        payload = source.get("payload") if isinstance(source.get("payload"), dict) else {}
        source_type = _text(source.get("sourceType") or payload.get("sourceType"))
        if source_type != "observed_profile":
            continue
        if normalize_option_value(payload.get("variantKey")) != requested:
            continue
        item_level = observed_item_level(payload) or _int(item.get("itemLevel"))
        simc_options = observed_gear_simc_options(payload)
        if item_level:
            simc_options = {"ilevel": str(item_level), **simc_options}
        status = _text(source.get("status")).lower()
        if status != "verified" and observed_variant_stat_payload_fields(payload):
            status = "verified"
        return {
            "id": _text(source.get("id")),
            "itemId": _text(payload.get("itemId") or payload.get("id") or item.get("id")),
            "slot": _text(payload.get("slot") or payload.get("simcSlot") or item.get("slot")),
            "variantKey": requested,
            "label": _text(payload.get("displayName") or payload.get("name") or source.get("sourceLabel")),
            "sourceType": source_type,
            "difficultyKey": _text(source.get("difficultyKey") or payload.get("difficultyKey") or "observed_profile"),
            "itemLevel": item_level,
            "simcOptions": simc_options,
            "status": status or "unknown",
            "blockers": _canonical(payload.get("blockers") if isinstance(payload.get("blockers"), list) else []),
            "payload": _canonical(payload),
            "updatedAt": _text(source.get("updatedAt")),
        }
    return None


def _verified_release_source_records(source_records: Any) -> list[dict[str, Any]]:
    """Normalize immutable observed stat evidence into the existing verified-source contract."""

    try:
        from .websim_payload import observed_variant_stat_payload_fields
    except ImportError:
        from websim_payload import observed_variant_stat_payload_fields

    normalized = []
    for raw in source_records if isinstance(source_records, list) else []:
        if not isinstance(raw, dict):
            continue
        source = _canonical(raw)
        payload = source.get("payload") if isinstance(source.get("payload"), dict) else {}
        statuses = {
            _text(source.get("status")).lower(),
            _text(source.get("sourceStatus")).lower(),
        }
        if (
            _text(source.get("sourceType")) == "observed_profile"
            and not statuses.intersection({"blocked", "rejected", "expired"})
            and observed_variant_stat_payload_fields(payload)
        ):
            source["status"] = "verified"
        normalized.append(source)
    return normalized


def canonical_row_hash(row: dict[str, Any]) -> str:
    return _hash(_canonical(row))


def _observed_compile_scope(
    gear_items: Any,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Reduce observed player gear to exact immutable release lookup keys."""

    try:
        from .websim_payload import observed_gear_simc_options
    except ImportError:
        from websim_payload import observed_gear_simc_options

    item_ids: set[str] = set()
    gem_ids: set[str] = set()
    enchant_ids: set[str] = set()
    embellishments: set[str] = set()
    for item in gear_items if isinstance(gear_items, list) else []:
        if not isinstance(item, dict):
            continue
        item_id = _text(item.get("itemId") or item.get("id"))
        if item_id:
            item_ids.add(item_id)
        options = observed_gear_simc_options(item)
        gem_ids.update(
            token.strip()
            for token in _text(options.get("gem_id")).split("/")
            if token.strip()
        )
        enchant_id = _text(options.get("enchant_id"))
        if enchant_id:
            enchant_ids.add(enchant_id)
        embellishment = _text(options.get("embellishment"))
        if embellishment:
            embellishments.add(embellishment)
    return (
        sorted(item_ids),
        sorted(gem_ids),
        sorted(enchant_ids),
        sorted(embellishments),
    )


def gear_snapshot_summary(snapshot: Any) -> dict[str, Any]:
    value = snapshot if isinstance(snapshot, dict) else {}
    categories = ("items", "sources", "variants", "options")
    counts = {key: 0 for key in categories}
    # The release snapshot is intentionally catalog-sized.  Sorting canonical
    # row bytes in a Python list retains the decoded catalog, every encoded
    # sort key, and the final aggregate JSON at once.  Use SQLite's disk-backed
    # BLOB sort instead, then feed the exact canonical JSON byte stream into
    # SHA-256 one row at a time.  This preserves the v1 snapshotHash contract
    # without a second catalog-sized in-memory representation.
    with tempfile.TemporaryDirectory(prefix="wow-gear-snapshot-summary-") as directory:
        database_path = os.path.join(directory, "snapshot.sqlite3")
        with closing(sqlite3.connect(database_path)) as connection:
            connection.execute("PRAGMA journal_mode=OFF")
            connection.execute("PRAGMA synchronous=OFF")
            connection.execute("PRAGMA temp_store=FILE")
            connection.execute("PRAGMA cache_size=-8192")
            connection.execute(
                "CREATE TABLE snapshot_rows (payload BLOB NOT NULL)"
            )
            digest = hashlib.sha256()
            digest.update(b"{")
            for category_index, key in enumerate(sorted(categories)):
                if category_index:
                    digest.update(b",")
                digest.update(b'"' + key.encode("utf-8") + b'":[')
                connection.execute("DELETE FROM snapshot_rows")
                for row in value.get(key) or ():
                    if not isinstance(row, dict):
                        continue
                    counts[key] += 1
                    connection.execute(
                        "INSERT INTO snapshot_rows (payload) VALUES (?)",
                        (sqlite3.Binary(_canonical_bytes(row)),),
                    )
                for row_index, (payload,) in enumerate(
                    connection.execute(
                        "SELECT payload FROM snapshot_rows ORDER BY payload"
                    )
                ):
                    if row_index:
                        digest.update(b",")
                    digest.update(payload)
                digest.update(b"]")
            digest.update(b"}")
    return {
        "schemaRevision": "gear-release-content-v1",
        "snapshotHash": "sha256:" + digest.hexdigest(),
        "counts": counts,
    }


def community_rows_summary(rows: Any) -> dict[str, Any]:
    canonical = _canonical_rows(rows)
    role_counts = {role: 0 for role in ("winner", "standby", "rejected")}
    winner_specs = []
    winner_hero_slots = []
    projected_winners = 0
    for row in canonical:
        role = _text(row.get("role"))
        if role in role_counts:
            role_counts[role] += 1
        if role == "winner":
            winner_specs.append({
                "classKey": _text(row.get("classKey")),
                "specKey": _text(row.get("specKey")),
            })
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            hero_key = _text(payload.get("heroKey"))
            talent_winner_id = _text(payload.get("talentWinnerId"))
            projection_mode = _text(payload.get("gearProjectionMode"))
            if hero_key and talent_winner_id and projection_mode in {"talent_winner", "gear_fallback"}:
                projected_winners += 1
                winner_hero_slots.append({
                    "classKey": _text(row.get("classKey")),
                    "specKey": _text(row.get("specKey")),
                    "heroKey": hero_key,
                })
    winner_specs = sorted(
        {(_text(row["classKey"]), _text(row["specKey"])) for row in winner_specs},
        key=lambda row: (row[0], row[1]),
    )
    winner_specs = [
        {"classKey": class_key, "specKey": spec_key}
        for class_key, spec_key in winner_specs
    ]
    winner_hero_slots.sort(key=lambda row: (row["classKey"], row["specKey"], row["heroKey"]))
    projected = role_counts["winner"] > 0 and projected_winners == role_counts["winner"]
    summary = {
        "schemaRevision": "community-release-content-v2" if projected else "community-release-content-v1",
        "snapshotHash": _hash(canonical),
        "counts": {"total": len(canonical), **role_counts},
        "winnerSpecs": winner_specs,
    }
    if projected:
        summary["winnerHeroSlots"] = winner_hero_slots
    return summary


def _expected_manifest_revision(manifest: dict[str, Any]) -> str:
    identity = {
        "schemaRevision": manifest.get("schemaRevision"),
        "seasonRevision": manifest.get("seasonRevision"),
        "gearCatalogReleaseId": manifest.get("gearCatalogReleaseId"),
        "communityTemplateReleaseId": manifest.get("communityTemplateReleaseId") or "",
        "talentCatalogRevision": manifest.get("talentCatalogRevision"),
        "dependencyRevisions": manifest.get("dependencyRevisions"),
        "rollbackManifestRevision": manifest.get("rollbackManifestRevision") or "",
        "formalActiveManifest": bool(manifest.get("formalActiveManifest")),
    }
    return "season-manifest:" + _hash(identity)


class CandidateGearAuthorityIndex:
    """One validated, reusable index over an exact candidate Gear snapshot."""

    def __init__(self, snapshot: dict[str, Any], gear_release: dict[str, Any]):
        self.release = _exact_release_descriptor(gear_release)
        if self.release["releaseKind"] != "gear":
            raise GearReleaseIntegrityError("candidate authority requires a Gear Release")
        self.snapshot_summary = gear_snapshot_summary(snapshot)
        if self.snapshot_summary != self.release["content"]:
            raise GearReleaseIntegrityError("candidate authority snapshot does not match Gear Release")
        self.items = {
            _text(row.get("itemId")): row
            for row in _canonical_rows(snapshot.get("items"))
        }
        self.sources_by_item: dict[str, list[dict[str, Any]]] = {}
        for row in _canonical_rows(snapshot.get("sources")):
            self.sources_by_item.setdefault(_text(row.get("itemId")), []).append(row)
        self.variants_by_item: dict[str, list[dict[str, Any]]] = {}
        for row in _canonical_rows(snapshot.get("variants")):
            self.variants_by_item.setdefault(_text(row.get("itemId")), []).append(row)
        self.options_by_key = {
            _text(row.get("optionKey")): row
            for row in _canonical_rows(snapshot.get("options"))
            if _text(row.get("optionKey"))
        }


def build_candidate_authority_context(
    snapshot: dict[str, Any],
    selection_intent: dict[str, Any],
    runtime_authority: dict[str, Any],
    gear_release: dict[str, Any],
    *,
    prepared_index: CandidateGearAuthorityIndex | None = None,
) -> dict[str, Any]:
    """Build an inactive candidate Authority Context from an exact sealed snapshot."""

    try:
        from .pg_gear_authority_loader import build_gear_authority_context_from_rows
        from .websim_payload import normalize_option_value
    except ImportError:
        from pg_gear_authority_loader import build_gear_authority_context_from_rows
        from websim_payload import normalize_option_value

    release = _exact_release_descriptor(gear_release)
    prepared = prepared_index or CandidateGearAuthorityIndex(snapshot, release)
    if prepared.release != release:
        raise GearReleaseIntegrityError("prepared candidate authority does not match Gear Release")
    authored = selection_intent.get("authoredAgainst") if isinstance(selection_intent, dict) else {}
    if not isinstance(authored, dict) or authored.get("seasonRevision") != release["seasonRevision"] or authored.get("gearCatalogRevision") != release["releaseId"]:
        raise GearReleaseIntegrityError("candidate Intent is not authored against the Gear Release")

    items = prepared.items
    sources_by_item = prepared.sources_by_item
    variants_by_item = prepared.variants_by_item
    options_by_key = prepared.options_by_key

    item_rows = []
    released_allowed_option_ids: set[str] = set()
    for selection in (selection_intent.get("slots") or {}).values():
        if not isinstance(selection, dict):
            continue
        item_id = _text(selection.get("itemId"))
        requested_variant = _text(selection.get("variantKey"))
        item = items.get(item_id)
        item_record = None
        if isinstance(item, dict):
            item_record = {
                "id": item_id,
                "name": item.get("name") or "",
                "slot": item.get("slot") or "",
                "itemLevel": item.get("itemLevel"),
                "sourceStatus": item.get("sourceStatus") or "unknown",
                "itemSetIds": [],
                "payload": item.get("payload") or {},
                "updatedAt": item.get("updatedAt") or "",
            }
            released_allowed_option_ids.update(
                _released_allowed_option_ids(item_record)
            )
        source_records = [
            {
                "id": source.get("sourceId") or "",
                "sourceType": source.get("sourceType") or "",
                "sourceKey": source.get("sourceKey") or "",
                "sourceLabel": source.get("sourceLabel") or "",
                "instanceId": source.get("instanceId") or "",
                "encounterId": source.get("encounterId") or "",
                "difficultyKey": source.get("difficultyKey") or "",
                "seasonRevision": source.get("seasonRevision") or "",
                "status": (source.get("payload") or {}).get("status") or "unknown",
                "sourceStatus": (source.get("payload") or {}).get("sourceStatus") or "unknown",
                "payload": source.get("payload") or {},
                "updatedAt": source.get("updatedAt") or "",
            }
            for source in sources_by_item.get(item_id, [])
        ]
        source_records = _verified_release_source_records(source_records)
        matching = [
            row for row in variants_by_item.get(item_id, [])
            if requested_variant
            and (
                _text(row.get("variantKey")) == requested_variant
                or normalize_option_value(row.get("variantKey")) == requested_variant
            )
        ]
        exact = [
            row
            for row in matching
            if _text(row.get("variantKey")) == requested_variant
        ]
        if exact:
            matching = exact
        if not matching:
            matching = [None]
        for variant in matching:
            variant_record = None
            if isinstance(variant, dict):
                variant_record = {
                    "id": variant.get("variantId") or "",
                    "itemId": item_id,
                    "slot": variant.get("slot") or "",
                    "variantKey": variant.get("variantKey") or "",
                    "label": variant.get("label") or "",
                    "sourceType": variant.get("sourceType") or "",
                    "difficultyKey": variant.get("difficultyKey") or "",
                    "itemLevel": variant.get("itemLevel") or 0,
                    "simcOptions": variant.get("simcOptions") or {},
                    "status": variant.get("status") or "blocked",
                    "blockers": variant.get("blockers") or [],
                    "payload": variant.get("payload") or {},
                    "updatedAt": variant.get("updatedAt") or "",
                }
                released_allowed_option_ids.update(
                    _released_allowed_option_ids(variant_record)
                )
            if variant_record is None:
                variant_record = _observed_release_variant_record(
                    requested_variant,
                    item_record,
                    source_records,
                )
            item_rows.append((item_id, requested_variant, item_record, variant_record, source_records))

    selected_option_ids = set()
    for selection in (selection_intent.get("slots") or {}).values():
        if not isinstance(selection, dict):
            continue
        selected_option_ids.update(_text(value) for value in selection.get("gemOptionIds") or [])
        selected_option_ids.update(
            _text(selection.get(field))
            for field in ("enchantOptionId", "embellishmentOptionId", "craftedOptionId", "catalystOptionId")
        )
    selected_option_ids.discard("")
    selected_option_ids.update(released_allowed_option_ids)
    option_rows = []
    for option_id in sorted(selected_option_ids):
        option = options_by_key.get(option_id)
        record = None
        if isinstance(option, dict):
            record = {
                "id": option.get("optionId") or "",
                "optionKey": option_id,
                "optionType": option.get("optionType") or "",
                "name": option.get("name") or "",
                "applicableSlots": option.get("applicableSlots") or [],
                "simcOptions": option.get("simcOptions") or {},
                "status": option.get("status") or "blocked",
                "isVisible": option.get("isVisible") is True,
                "payload": option.get("payload") or {},
                "updatedAt": option.get("updatedAt") or "",
            }
        option_rows.append((option_id, record))

    dependencies = {
        "seasonRevision": release["seasonRevision"],
        "gearCatalogReleaseId": release["releaseId"],
        "gearCatalogRevision": release["releaseId"],
        **_canonical(release.get("dependencyRevisions") or {}),
    }
    return build_gear_authority_context_from_rows(
        selection_intent,
        runtime_authority,
        manifest={
            "contractRevision": "active-season-manifest-v1",
            "manifestType": "candidate",
            "formalActiveManifest": False,
            "seasonRevision": release["seasonRevision"],
            "gearCatalogReleaseId": release["releaseId"],
            "gearCatalogRevision": release["releaseId"],
            "catalogFingerprint": release["contentHash"],
            "sourceStates": {"releaseStatus": release["releaseStatus"]},
        },
        dependency_vector=dependencies,
        item_rows=item_rows,
        option_rows=option_rows,
    )


def _release_from_row(row: Any) -> dict[str, Any] | None:
    if not row:
        return None
    values = list(row)
    return {
        "schemaRevision": _text(values[3] if len(values) > 3 else ""),
        "releaseId": _text(values[0] if len(values) > 0 else ""),
        "releaseKind": _text(values[1] if len(values) > 1 else ""),
        "seasonRevision": _text(values[2] if len(values) > 2 else ""),
        "contentHash": _text(values[4] if len(values) > 4 else ""),
        "dependencyRevisions": _canonical(values[8] if len(values) > 8 and isinstance(values[8], dict) else {}),
        "releaseStatus": _text(values[7] if len(values) > 7 else ""),
        "parentReleaseId": _text(values[5] if len(values) > 5 else ""),
        "validatedAgainstReleaseId": _text(values[6] if len(values) > 6 else ""),
        "source": _canonical(values[10] if len(values) > 10 and isinstance(values[10], dict) else {}),
        "content": _canonical(values[11] if len(values) > 11 else {}),
    }


def _exact_release_descriptor(release: Any) -> dict[str, Any]:
    if not isinstance(release, dict):
        raise GearReleaseIntegrityError("release descriptor must be an object")
    try:
        from . import gear_release
    except ImportError:
        import gear_release
    issues = gear_release.validate_release(release)
    if issues:
        raise GearReleaseIntegrityError(
            "release descriptor integrity failed: "
            + ", ".join(_text(issue.get("code")) for issue in issues)
        )
    fields = (
        "schemaRevision",
        "releaseId",
        "releaseKind",
        "seasonRevision",
        "contentHash",
        "dependencyRevisions",
        "releaseStatus",
        "parentReleaseId",
        "validatedAgainstReleaseId",
        "source",
        "content",
    )
    descriptor = {field: _canonical(release.get(field)) for field in fields}
    for field in ("schemaRevision", "releaseId", "releaseKind", "seasonRevision", "contentHash", "releaseStatus"):
        descriptor[field] = _text(descriptor[field])
    for field in ("parentReleaseId", "validatedAgainstReleaseId"):
        descriptor[field] = _text(descriptor[field])
    for field in ("dependencyRevisions", "source"):
        descriptor[field] = descriptor[field] if isinstance(descriptor[field], dict) else {}
    return descriptor


def _readable_release_binding(binding: Any) -> bool:
    value = binding if isinstance(binding, dict) else {}
    return value.get("formalActiveManifest") is True or value.get("candidatePreview") is True


class GearReleaseStore:
    # The mutable Talent snapshot is now part of the source contract for new
    # Community Releases.  Kept as a capability flag so legacy test doubles
    # and explicitly historical rebuilds remain v1-compatible.
    community_hero_projection_enabled = True
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    @staticmethod
    def _configured_simc_probe_evidence() -> dict[str, Any]:
        try:
            from . import gear_release_tool
            from .simulator_payload import simc_version_status
        except ImportError:
            import gear_release_tool
            from simulator_payload import simc_version_status

        status = simc_version_status()
        binary_path = _text(status.get("binaryPath"))
        revision = _text(
            status.get("sourceCommit")
            or status.get("simcRuntimeRevision")
        )
        if not binary_path or not revision:
            raise GearReleaseIntegrityError(
                "trusted SimC socket probe is unavailable"
            )
        return gear_release_tool.load_simc_socket_bonus_minimums(
            binary_path,
            source_identity="simulationcraft:show_bonus_ids",
            source_revision=revision,
        )

    def _trusted_socket_probe_evidence(
        self,
        release: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            from . import gear_release_tool
        except ImportError:
            import gear_release_tool

        try:
            trusted = gear_release_tool._validated_socket_bonus_evidence(
                self._configured_simc_probe_evidence()
            )
        except (GearReleaseIntegrityError, RuntimeError, TypeError, ValueError):
            raise GearReleaseIntegrityError(
                "trusted SimC socket probe is unavailable"
            ) from None
        source = (
            release.get("source")
            if isinstance(release.get("source"), dict)
            else {}
        )
        source_evidence = (
            source.get("sourceEvidence")
            if isinstance(source.get("sourceEvidence"), dict)
            else {}
        )
        claimed = source_evidence.get("socketBonusEvidence")
        dependencies = (
            release.get("dependencyRevisions")
            if isinstance(release.get("dependencyRevisions"), dict)
            else {}
        )
        if (
            trusted.get("sourceIdentity")
            != "simulationcraft:show_bonus_ids"
            or trusted.get("sourceScope") != "exact_variant"
            or _text(trusted.get("sourceRevision"))
            != _text(dependencies.get("simcRuntimeRevision"))
            or _canonical(claimed) != _canonical(trusted)
            or _text(source_evidence.get("socketProbeDigest"))
            != gear_release_tool._socket_probe_digest(trusted)
        ):
            raise GearReleaseIntegrityError(
                "trusted SimC socket probe does not match release evidence"
            )
        return trusted

    @contextmanager
    def connection(self):
        conn = self.connection_factory()
        try:
            yield conn
            if hasattr(conn, "commit"):
                conn.commit()
        except Exception:
            if hasattr(conn, "rollback"):
                conn.rollback()
            raise
        finally:
            if hasattr(conn, "close"):
                conn.close()

    def persist_gear_evidence_bundle(
        self,
        *,
        artifacts: Iterable[dict[str, Any]],
        observations: Iterable[dict[str, Any]],
        facts: Iterable[dict[str, Any]],
        gaps: list[dict[str, Any]],
        now: str,
    ) -> dict[str, Any]:
        """Persist compiler inputs/results before any Gear Release can seal."""

        try:
            from .gear_evidence_gap_store import GearEvidenceGapStore
            from .gear_evidence_store import GearEvidenceStore
        except ImportError:
            from gear_evidence_gap_store import GearEvidenceGapStore
            from gear_evidence_store import GearEvidenceStore

        artifact_rows = list(artifacts)
        observation_rows = list(observations)
        fact_rows = list(facts)
        with self.connection() as connection:
            # The nested Evidence/Gap stores use ``with connection()`` for
            # their normal one-operation ownership model.  This bundle owns a
            # single atomic parent transaction, so hand them a non-owning
            # context manager rather than the raw psycopg connection (whose
            # context exit closes it).
            shared_connection = lambda: _borrowed_connection(connection)
            evidence_store = GearEvidenceStore(shared_connection)
            gap_store = GearEvidenceGapStore(shared_connection)
            for artifact in artifact_rows:
                evidence_store.persist_artifact(artifact)
            for observation in observation_rows:
                evidence_store.persist_observation(observation)
            for fact in fact_rows:
                evidence_store.persist_fact(fact)
            gap_result = gap_store.enqueue_gaps(
                list(gaps),
                now=_text(now),
            )
        return {
            "artifacts": {
                "persisted": len(artifact_rows),
                "identities": sorted(
                    _text(row.get("artifactId"))
                    for row in artifact_rows
                ),
                "identityDigest": _hash(sorted(
                    _text(row.get("artifactId"))
                    for row in artifact_rows
                )),
            },
            "observations": {
                "persisted": len(observation_rows),
                "identities": sorted(
                    _text(row.get("observationId"))
                    for row in observation_rows
                ),
                "identityDigest": _hash(sorted(
                    _text(row.get("observationId"))
                    for row in observation_rows
                )),
            },
            "facts": {
                "persisted": len(fact_rows),
                "identities": sorted(
                    (
                        _text(row.get("factKey")),
                        _text(row.get("factValueHash")),
                        _text(row.get("provenanceHash")),
                    )
                    for row in fact_rows
                ),
                "identityDigest": _hash(sorted(
                    (
                        _text(row.get("factKey")),
                        _text(row.get("factValueHash")),
                        _text(row.get("provenanceHash")),
                    )
                    for row in fact_rows
                )),
            },
            "gaps": {
                **gap_result,
                "requested": len(gaps),
                "identities": sorted(
                    _text(row.get("gapKey"))
                    for row in gaps
                ),
                "identityDigest": _hash(sorted(
                    _text(row.get("gapKey"))
                    for row in gaps
                )),
            },
        }

    def snapshot_staging_gear(self) -> dict[str, list[dict[str, Any]]]:
        """Read one repeatable staging snapshot without duplicating its JSON rows.

        The release builder owns later canonical projection.  Normalizing every
        JSONB value here used to retain the driver's full result set *and* a
        deep-copied Python equivalent for the whole catalog.  Consume the
        cursor in bounded batches and preserve the decoded JSON values until a
        caller deliberately projects the relevant release batch.
        """

        def decoded_object(value: Any) -> dict[str, Any]:
            return value if isinstance(value, dict) else {}

        def decoded_list(value: Any) -> list[Any]:
            return value if isinstance(value, list) else []

        def read_rows(cur, statement: str, build_row):
            records: list[dict[str, Any]] = []
            cur.execute(statement)
            fetchmany = getattr(cur, "fetchmany", None)
            if not callable(fetchmany):
                return [build_row(row) for row in cur.fetchall()]
            while True:
                rows = fetchmany(128)
                if not rows:
                    break
                records.extend(build_row(row) for row in rows)
            return records

        with self.connection() as conn:
            with conn.cursor() as setup_cursor:
                setup_cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            # psycopg's unnamed cursor buffers a complete result after execute(),
            # so fetchmany() alone does not put a bound on the catalog-sized
            # staging read.  A named cursor keeps those rows on PostgreSQL until
            # each bounded fetch.  Keep the compatibility fallback for the
            # lightweight cursor doubles used by local verification.
            try:
                cursor = conn.cursor(name="gear_release_staging_snapshot")
            except TypeError:
                cursor = conn.cursor()
            with cursor as cur:
                items = read_rows(
                    cur,
                    """
                    SELECT id, name, slot, item_level, payload_json, source_status, updated_at
                    FROM cache.websim_items
                    ORDER BY id
                    """,
                    lambda row: {
                        "itemId": _text(row[0]),
                        "name": _text(row[1]),
                        "slot": _text(row[2]),
                        "itemLevel": row[3],
                        "payload": decoded_object(row[4]),
                        "sourceStatus": _text(row[5]),
                        "updatedAt": _text(row[6]),
                    },
                )
                sources = read_rows(
                    cur,
                    """
                    SELECT id::text, item_id, source_type, source_key, source_label, instance_id,
                           encounter_id, difficulty_key, season_revision, payload_json, updated_at
                    FROM cache.websim_gear_sources
                    ORDER BY id::text
                    """,
                    lambda row: {
                        "sourceId": _text(row[0]),
                        "itemId": _text(row[1]),
                        "sourceType": _text(row[2]),
                        "sourceKey": _text(row[3]),
                        "sourceLabel": _text(row[4]),
                        "instanceId": _text(row[5]),
                        "encounterId": _text(row[6]),
                        "difficultyKey": _text(row[7]),
                        "seasonRevision": _text(row[8]),
                        "payload": decoded_object(row[9]),
                        "updatedAt": _text(row[10]),
                    },
                )
                variants = read_rows(
                    cur,
                    """
                    SELECT id::text, item_id, variant_key, slot, label, source_type, difficulty_key,
                           item_level, simc_options_json, status, blockers_json, payload_json, updated_at
                    FROM cache.websim_gear_variants
                    ORDER BY id::text
                    """,
                    lambda row: {
                        "variantId": _text(row[0]),
                        "itemId": _text(row[1]),
                        "variantKey": _text(row[2]),
                        "slot": _text(row[3]),
                        "label": _text(row[4]),
                        "sourceType": _text(row[5]),
                        "difficultyKey": _text(row[6]),
                        "itemLevel": _int(row[7]),
                        "simcOptions": decoded_object(row[8]),
                        "status": _text(row[9]),
                        "blockers": decoded_list(row[10]),
                        "payload": decoded_object(row[11]),
                        "updatedAt": _text(row[12]),
                    },
                )
                options = read_rows(
                    cur,
                    """
                    SELECT id::text, variant_id::text, option_key, option_type, name,
                           applicable_slots_json, simc_options_json, status, is_visible,
                           payload_json, updated_at
                    FROM cache.websim_gear_mod_options
                    ORDER BY id::text
                    """,
                    lambda row: {
                        "optionId": _text(row[0]),
                        "variantId": _text(row[1]),
                        "optionKey": _text(row[2]),
                        "optionType": _text(row[3]),
                        "name": _text(row[4]),
                        "applicableSlots": decoded_list(row[5]),
                        "simcOptions": decoded_object(row[6]),
                        "status": _text(row[7]),
                        "isVisible": row[8] is True,
                        "payload": decoded_object(row[9]),
                        "updatedAt": _text(row[10]),
                    },
                )
        return {
            "items": items,
            "sources": sources,
            "variants": variants,
            "options": options,
        }

    def snapshot_staging_community_templates(
        self,
        expected_specs: Iterable[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        specs = sorted({
            (_text(class_key), _text(spec_key))
            for class_key, spec_key in expected_specs
            if _text(class_key) and _text(spec_key)
        })
        if not specs or len(specs) > 40:
            raise GearReleaseIntegrityError("community snapshot requires 1 to 40 explicit specs")
        class_keys = [class_key for class_key, _spec_key in specs]
        spec_keys = [spec_key for _class_key, spec_key in specs]
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cur.execute(
                    """
                    WITH expected(class_key, spec_key) AS (
                        SELECT * FROM unnest(%s::text[], %s::text[])
                    ), ranked AS (
                        SELECT template.id, template.class_key, template.spec_key, template.name,
                               template.source_key, template.source_name, template.source_url,
                               template.source_status, template.status, template.signature,
                               template.source_refs_json, template.gear_items_json,
                               template.raw_string, template.ready_slot_count,
                               template.missing_slots_json, template.analysis_window,
                               template.payload_json, template.updated_at, template.expires_at,
                               template.scan_run_id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY template.class_key, template.spec_key
                                   ORDER BY template.status, template.ready_slot_count DESC,
                                            template.updated_at DESC, template.id
                               ) AS candidate_rank
                        FROM cache.websim_community_gear_templates AS template
                        INNER JOIN expected
                          ON expected.class_key = template.class_key
                         AND expected.spec_key = template.spec_key
                    )
                    SELECT id, class_key, spec_key, name, source_key, source_name, source_url,
                           source_status, status, signature, source_refs_json, gear_items_json,
                           raw_string, ready_slot_count, missing_slots_json, analysis_window,
                           payload_json, updated_at, expires_at, scan_run_id
                    FROM ranked
                    ORDER BY class_key, spec_key, candidate_rank, id
                    """,
                    (class_keys, spec_keys),
                )
                rows = cur.fetchall()
        return [
            {
                "templateId": _text(row[0]),
                "classKey": _text(row[1]),
                "specKey": _text(row[2]),
                "name": _text(row[3]),
                "sourceKey": _text(row[4]),
                "sourceName": _text(row[5]),
                "sourceUrl": _text(row[6]),
                "sourceStatus": _text(row[7]),
                "status": _text(row[8]),
                "signature": _text(row[9]),
                "sourceRefs": _canonical(row[10] if isinstance(row[10], list) else []),
                "gearItems": _canonical(row[11] if isinstance(row[11], list) else []),
                "rawString": _text(row[12]),
                "readySlotCount": _int(row[13]),
                "missingSlots": _canonical(row[14] if isinstance(row[14], list) else []),
                "analysisWindow": _text(row[15]),
                "payload": _canonical(row[16] if isinstance(row[16], dict) else {}),
                "updatedAt": _text(row[17]),
                "expiresAt": _text(row[18]),
                "scanRunId": _text(row[19]),
            }
            for row in rows
        ]

    def snapshot_staging_community_talent_candidates(
        self,
        expected_specs: Iterable[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        """Read the immutable ordering input for hero-slot gear projection.

        These are not new gear candidates.  They are the same per-hero Talent
        source rows that produced the 80/80 winner set, including the ordered
        fallback candidates used only if the winner's captured equipment fails
        canonical Gear validation.
        """

        specs = sorted({
            (_text(class_key), _text(spec_key))
            for class_key, spec_key in expected_specs
            if _text(class_key) and _text(spec_key)
        })
        if not specs or len(specs) > 40:
            raise GearReleaseIntegrityError("community talent snapshot requires 1 to 40 explicit specs")
        class_keys = [class_key for class_key, _spec_key in specs]
        spec_keys = [spec_key for _class_key, spec_key in specs]
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cur.execute(
                    """
                    WITH expected(class_key, spec_key) AS (
                        SELECT * FROM unnest(%s::text[], %s::text[])
                    )
                    SELECT candidate.value->>'candidateId',
                           candidate.value->>'classKey',
                           candidate.value->>'specKey',
                           candidate.value->>'heroKey',
                           candidate.value->>'scenarioKey',
                           candidate.value->>'sourceKey',
                           candidate.value->>'sourceStatus',
                           template.status,
                           candidate.value->>'sourceIdentity',
                           jsonb_build_object(
                               'raiderio',
                               jsonb_build_object('sourceIdentity', COALESCE(candidate.value->>'sourceIdentity', ''))
                           ),
                           template.updated_at,
                           template.expires_at,
                           COALESCE(NULLIF(candidate.value->>'talentCandidateRank', '')::integer, 0)
                    FROM cache.websim_community_talent_templates AS template
                    INNER JOIN expected
                      ON expected.class_key = template.class_key
                     AND expected.spec_key = template.spec_key
                    CROSS JOIN LATERAL jsonb_array_elements(
                        COALESCE(template.payload_json->'gearProjectionCandidates', '[]'::jsonb)
                    ) AS candidate(value)
                    WHERE template.scenario_key = 'mythic_plus'
                      AND template.status = 'verified'
                      AND template.expires_at > NOW()
                    ORDER BY candidate.value->>'classKey', candidate.value->>'specKey',
                             candidate.value->>'heroKey',
                             COALESCE(NULLIF(candidate.value->>'talentCandidateRank', '')::integer, 0),
                             candidate.value->>'candidateId'
                    """,
                    (class_keys, spec_keys),
                )
                rows = cur.fetchall()
        return [
            {
                "id": _text(row[0]),
                "classKey": _text(row[1]),
                "specKey": _text(row[2]),
                "heroKey": _text(row[3]),
                "scenarioKey": _text(row[4]),
                "sourceKey": _text(row[5]),
                "sourceStatus": _text(row[6]),
                "status": _text(row[7]),
                "sourceIdentity": _text(row[8]),
                "payload": _canonical(row[9] if isinstance(row[9], dict) else {}),
                "updatedAt": _text(row[10]),
                "expiresAt": _text(row[11]),
                "talentCandidateRank": _int(row[12]),
            }
            for row in rows
        ]

    @staticmethod
    def _select_release(cur, release_id: str) -> dict[str, Any] | None:
        cur.execute(
            """
            SELECT release_id, release_kind, season_revision, schema_revision, content_hash,
                   parent_release_id, validated_against_release_id, release_status,
                   dependency_vector_json, gate_result_json, source_json, content_summary_json
            FROM cache.websim_release_registry
            WHERE release_id = %s
            """,
            (release_id,),
        )
        return _release_from_row(cur.fetchone())

    def get_release(self, release_id: str) -> dict[str, Any]:
        normalized = _text(release_id)
        if not normalized:
            return {}
        with self.connection() as conn:
            with conn.cursor() as cur:
                release = self._select_release(cur, normalized)
        return release or {}

    def get_gear_release_row_hashes(self, release_id: str) -> dict[str, dict[str, str]]:
        """Read only immutable identity/hash pairs for additive risk classification."""

        normalized = _text(release_id)
        if not normalized:
            raise GearReleaseIntegrityError("Gear Release ID is required")
        queries = (
            ("items", "SELECT item_id, row_hash FROM cache.websim_gear_release_items WHERE release_id = %s"),
            ("sources", "SELECT source_id, row_hash FROM cache.websim_gear_release_sources WHERE release_id = %s"),
            ("variants", "SELECT variant_id, row_hash FROM cache.websim_gear_release_variants WHERE release_id = %s"),
            ("options", "SELECT option_id, row_hash FROM cache.websim_gear_release_mod_options WHERE release_id = %s"),
        )
        result: dict[str, dict[str, str]] = {}
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                for category, statement in queries:
                    cur.execute(statement, (normalized,))
                    result[category] = {
                        _text(identity): _text(row_hash)
                        for identity, row_hash in cur.fetchall()
                        if _text(identity) and _text(row_hash)
                    }
        return result

    def record_refresh_event(
        self,
        event_type: str,
        event: dict[str, Any],
        *,
        release_id: str = "",
        manifest_revision: str = "",
    ) -> None:
        normalized_type = _text(event_type)
        if normalized_type not in {
            "gear_release_refresh_started",
            "gear_release_refresh_completed",
            "gear_release_refresh_failed",
            "gear_release_refresh_lease_conflict",
        }:
            raise GearReleaseIntegrityError("unsupported release refresh event type")
        with self.connection() as conn:
            with conn.cursor() as cur:
                self._insert_event(
                    cur,
                    release_id=_text(release_id),
                    manifest_revision=_text(manifest_revision),
                    event_type=normalized_type,
                    event=_canonical(event if isinstance(event, dict) else {}),
                )

    def latest_refresh_state(self) -> dict[str, Any]:
        """Expose one bounded latest-run projection without raw operator data."""

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """
                    SELECT event_type, event_json, created_at, release_id, manifest_revision
                    FROM cache.websim_release_events
                    WHERE event_type LIKE 'gear_release_refresh_%'
                    ORDER BY created_at DESC, event_id DESC
                    LIMIT 1
                    """
                )
                row = cur.fetchone()
        if not row:
            return {}
        event_type, payload, created_at, release_id, manifest_revision = row
        payload = payload if isinstance(payload, dict) else {}
        gear_change = payload.get("gearChange") if isinstance(payload.get("gearChange"), dict) else {}
        seal_status = payload.get("sealStatus") if isinstance(payload.get("sealStatus"), dict) else {}
        shadow_performance = (
            payload.get("shadowPerformance")
            if isinstance(payload.get("shadowPerformance"), dict)
            else {}
        )
        return {
            "eventType": _text(event_type),
            "status": _text(payload.get("status")),
            "checkedAt": _text(created_at),
            "gearReleaseId": _text(payload.get("gearReleaseId")),
            "communityReleaseId": _text(payload.get("communityReleaseId") or release_id),
            "manifestRevision": _text(payload.get("manifestRevision") or manifest_revision),
            "riskClass": _text(payload.get("riskClass")),
            "decision": _text(payload.get("decision")),
            "blockerCodes": [
                _text(code)
                for code in (payload.get("blockerCodes") or [])[:16]
                if _text(code)
            ],
            "counts": _canonical(payload.get("counts") if isinstance(payload.get("counts"), dict) else {}),
            "gearChange": _canonical({
                change_kind: {
                    category: _int((gear_change.get(change_kind) or {}).get(category))
                    for category in ("items", "sources", "variants", "options")
                }
                for change_kind in ("addedCounts", "changedCounts", "removedCounts")
            }),
            "sealStatus": {
                "gear": _text(seal_status.get("gear")),
                "community": _text(seal_status.get("community")),
            },
            "shadowStatus": _text(payload.get("shadowStatus")),
            "shadowSpecCount": _int(payload.get("shadowSpecCount")),
            "shadowPerformance": {
                key: value
                for key in ("specP95Ms", "specMaxMs", "totalDurationMs")
                if isinstance((value := shadow_performance.get(key)), (int, float))
            },
        }

    def load_candidate_authority_context(
        self,
        selection_intent: dict[str, Any],
        runtime_authority: dict[str, Any],
        gear_release_id: str,
    ) -> dict[str, Any]:
        """Read selected authority facts from one exact inactive Gear Release."""

        try:
            from .pg_gear_authority_loader import build_gear_authority_context_from_rows
        except ImportError:
            from pg_gear_authority_loader import build_gear_authority_context_from_rows

        release_id = _text(gear_release_id)
        intent = selection_intent if isinstance(selection_intent, dict) else {}
        slots = intent.get("slots") if isinstance(intent.get("slots"), dict) else {}
        requested_pairs = list(dict.fromkeys(
            (_text(selection.get("itemId")), _text(selection.get("variantKey")))
            for selection in slots.values()
            if isinstance(selection, dict)
        ))
        item_ids = [item_id for item_id, _variant_key in requested_pairs]
        variant_keys = [variant_key for _item_id, variant_key in requested_pairs]
        option_ids = set(_selected_option_ids(intent))

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                release = self._select_release(cur, release_id)
                if release is None:
                    raise GearReleaseIntegrityError("candidate Gear Release is missing")
                release = _exact_release_descriptor(release)
                if release["releaseKind"] != "gear":
                    raise GearReleaseIntegrityError("candidate authority requires a Gear Release")
                authored = intent.get("authoredAgainst") if isinstance(intent.get("authoredAgainst"), dict) else {}
                if (
                    authored.get("seasonRevision") != release["seasonRevision"]
                    or authored.get("gearCatalogRevision") != release["releaseId"]
                ):
                    raise GearReleaseIntegrityError("candidate Intent is not authored against the Gear Release")
                cur.execute(
                    RELEASE_SELECTED_ITEM_VARIANT_SQL,
                    (release_id, item_ids, variant_keys),
                )
                selected_item_rows = list(cur.fetchall())
                # Exact immutable identity wins. Normalized aliases are retained
                # only when no exact row exists, so alias-only conflicts still
                # reach the loader's fail-closed equivalence check.
                exact_variant_pairs = {
                    (_text(row[0]), _text(row[1]))
                    for row in selected_item_rows
                    if len(row or ()) > 3
                    and isinstance(row[3], dict)
                    and _text(row[3].get("variantKey")) == _text(row[1])
                }
                item_rows = []
                for row in selected_item_rows:
                    values = list(row or ())
                    while len(values) < 5:
                        values.append(None)
                    pair = (_text(values[0]), _text(values[1]))
                    if (
                        pair in exact_variant_pairs
                        and (
                            not isinstance(values[3], dict)
                            or _text(values[3].get("variantKey")) != pair[1]
                        )
                    ):
                        continue
                    values[4] = _verified_release_source_records(values[4])
                    if values[3] is None:
                        values[3] = _observed_release_variant_record(
                            _text(values[1]),
                            values[2],
                            values[4],
                        )
                    item_rows.append(tuple(values[:5]))
                    option_ids.update(
                        _released_allowed_option_ids(values[2], values[3])
                    )
                cur.execute(
                    RELEASE_SELECTED_OPTION_SQL,
                    (release_id, sorted(option_ids)),
                )
                option_rows = cur.fetchall()

        dependencies = {
            "seasonRevision": release["seasonRevision"],
            "gearCatalogReleaseId": release["releaseId"],
            "gearCatalogRevision": release["releaseId"],
            **_canonical(release.get("dependencyRevisions") or {}),
        }
        return build_gear_authority_context_from_rows(
            intent,
            runtime_authority,
            manifest={
                "contractRevision": "active-season-manifest-v1",
                "manifestType": "candidate_shadow",
                "manifestRevision": f"candidate-shadow:{release['releaseId']}",
                "formalActiveManifest": False,
                "seasonRevision": release["seasonRevision"],
                "gearCatalogReleaseId": release["releaseId"],
                "gearCatalogRevision": release["releaseId"],
                "catalogFingerprint": release["contentHash"],
                "sourceStates": {"releaseStatus": release["releaseStatus"]},
            },
            dependency_vector=dependencies,
            item_rows=item_rows,
            option_rows=option_rows,
        )

    @staticmethod
    def _active_runtime_dependencies(binding: dict[str, Any], runtime_authority: dict[str, Any]) -> dict[str, Any]:
        manifest = binding.get("manifest") if isinstance(binding.get("manifest"), dict) else {}
        manifest_dependencies = (
            manifest.get("dependencyRevisions")
            if isinstance(manifest.get("dependencyRevisions"), dict)
            else {}
        )
        runtime_dependencies = (
            runtime_authority.get("dependencyRevisions")
            if isinstance(runtime_authority, dict)
            and isinstance(runtime_authority.get("dependencyRevisions"), dict)
            else {}
        )
        required = (
            "gearRuleRevision",
            "resolverContractRevision",
            "serializerRevision",
            "simcRuntimeRevision",
            "statPolicyRevision",
            "selectionSchemaRevision",
        )
        mismatched = [
            field
            for field in required
            if not _text(manifest_dependencies.get(field))
            or _text(runtime_dependencies.get(field)) != _text(manifest_dependencies.get(field))
        ]
        supported_capability_revisions = (
            runtime_authority.get("supportedCapabilityRevisions")
            if isinstance(runtime_authority, dict)
            and isinstance(runtime_authority.get("supportedCapabilityRevisions"), (list, tuple))
            else []
        )
        supported_capability_revisions = {
            _text(revision)
            for revision in supported_capability_revisions
            if _text(revision)
        }
        manifest_capability_revision = _text(
            manifest_dependencies.get("capabilityRevision")
        )
        runtime_capability_revision = _text(
            runtime_dependencies.get("capabilityRevision")
        )
        if (
            not manifest_capability_revision
            or not runtime_capability_revision
            or runtime_capability_revision not in supported_capability_revisions
            or manifest_capability_revision not in supported_capability_revisions
        ):
            mismatched.append("capabilityRevision")
        if mismatched:
            raise GearReleaseIntegrityError(
                "active runtime dependencies do not match the Manifest: " + ", ".join(mismatched)
            )
        return _canonical(manifest_dependencies)

    def active_resolver_context(
        self,
        binding: dict[str, Any],
        runtime_authority: dict[str, Any],
    ) -> dict[str, Any]:
        if not _readable_release_binding(binding):
            raise GearReleaseIntegrityError("formal active or candidate preview Manifest binding is required")
        manifest = binding.get("manifest") if isinstance(binding.get("manifest"), dict) else {}
        dependencies = self._active_runtime_dependencies(binding, runtime_authority)
        return _canonical({
            "contractRevision": "gear-resolver-context-v1",
            "formalActiveManifest": binding.get("formalActiveManifest") is True,
            "candidatePreview": binding.get("candidatePreview") is True,
            "manifestRevision": _text(manifest.get("manifestRevision")),
            "pointerGeneration": _int(binding.get("generation")),
            "selectionSchemaRevision": _text(dependencies.get("selectionSchemaRevision")),
            "authoredAgainst": {
                "seasonRevision": _text(manifest.get("seasonRevision")),
                "gearCatalogRevision": _text(manifest.get("gearCatalogReleaseId")),
            },
            "dependencyRevisions": {
                field: _text(dependencies.get(field))
                for field in (
                    "gearRuleRevision",
                    "resolverContractRevision",
                    "serializerRevision",
                    "simcRuntimeRevision",
                    "statPolicyRevision",
                    "selectionSchemaRevision",
                    "capabilityRevision",
                )
            },
        })

    def load_active_authority_context(
        self,
        selection_intent: dict[str, Any],
        runtime_authority: dict[str, Any],
        binding: dict[str, Any],
    ) -> dict[str, Any]:
        if not _readable_release_binding(binding):
            raise GearReleaseIntegrityError("formal active or candidate preview Manifest binding is required")
        manifest = binding.get("manifest") if isinstance(binding.get("manifest"), dict) else {}
        gear_release_id = _text(manifest.get("gearCatalogReleaseId"))
        dependencies = self._active_runtime_dependencies(binding, runtime_authority)
        # The exact-release reader is intentionally strict for inactive shadow
        # calls.  Active Resolve must still be able to read current authority
        # for an older Intent so the pure resolver can return a truthful 409
        # with the current release context instead of collapsing to a 503.
        authority_read_intent = _canonical(
            selection_intent if isinstance(selection_intent, dict) else {}
        )
        authority_read_intent["authoredAgainst"] = {
            "seasonRevision": _text(manifest.get("seasonRevision")),
            "gearCatalogRevision": gear_release_id,
        }
        context = self.load_candidate_authority_context(
            authority_read_intent,
            runtime_authority,
            gear_release_id,
        )
        context = _canonical(context)
        gear_release = binding.get("gearRelease") if isinstance(binding.get("gearRelease"), dict) else {}
        context["manifest"] = {
            "contractRevision": "active-season-manifest-v1",
            "manifestType": "candidate_preview" if binding.get("candidatePreview") is True else "retail",
            "manifestRevision": _text(manifest.get("manifestRevision")),
            "formalActiveManifest": binding.get("formalActiveManifest") is True,
            "candidatePreview": binding.get("candidatePreview") is True,
            "pointerGeneration": _int(binding.get("generation")),
            "seasonRevision": _text(manifest.get("seasonRevision")),
            "gearCatalogReleaseId": gear_release_id,
            "gearCatalogRevision": gear_release_id,
            "communityTemplateReleaseId": _text(manifest.get("communityTemplateReleaseId")),
            "talentCatalogRevision": _text(manifest.get("talentCatalogRevision")),
            "catalogFingerprint": _text(gear_release.get("contentHash")),
            "sourceStates": {"releaseStatus": _text(gear_release.get("releaseStatus"))},
        }
        context["dependencyVector"] = {
            "seasonRevision": _text(manifest.get("seasonRevision")),
            "gearCatalogReleaseId": gear_release_id,
            "gearCatalogRevision": gear_release_id,
            **dependencies,
        }
        return _canonical(context)

    def load_active_public_gear(
        self,
        binding: dict[str, Any],
        class_key: str,
        spec_key: str,
        *,
        include_catalog: bool,
        catalog_slot: str = "",
    ) -> dict[str, Any]:
        """Read public gear facts only from the immutable Releases in one active binding."""

        if not _readable_release_binding(binding):
            raise GearReleaseIntegrityError("formal active or candidate preview Manifest binding is required")
        manifest = binding.get("manifest") if isinstance(binding.get("manifest"), dict) else {}
        gear = _exact_release_descriptor(binding.get("gearRelease"))
        gear_id = _text(manifest.get("gearCatalogReleaseId"))
        if gear_id != gear["releaseId"]:
            raise GearReleaseIntegrityError("active public Gear Release does not match the Manifest")
        community_id = _text(manifest.get("communityTemplateReleaseId"))
        community = None
        if community_id:
            community = _exact_release_descriptor(binding.get("communityRelease"))
            if community_id != community["releaseId"] or community["validatedAgainstReleaseId"] != gear_id:
                raise GearReleaseIntegrityError("active public Community Release does not match the Manifest")

        snapshot = {"items": [], "sources": [], "variants": [], "options": []}
        community_templates = []
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cur.execute(
                    """
                    /* gear_release_public_counts */
                    SELECT
                        (SELECT COUNT(*) FROM cache.websim_gear_release_items WHERE release_id = %s),
                        (SELECT COUNT(*) FROM cache.websim_gear_release_sources WHERE release_id = %s),
                        (SELECT COUNT(*) FROM cache.websim_gear_release_variants WHERE release_id = %s),
                        (SELECT COUNT(*) FROM cache.websim_gear_release_mod_options WHERE release_id = %s)
                    """,
                    (gear_id, gear_id, gear_id, gear_id),
                )
                count_row = tuple(cur.fetchone() or ())
                expected_counts = gear.get("content", {}).get("counts") if isinstance(gear.get("content"), dict) else {}
                actual_counts = {
                    "items": _int(count_row[0] if len(count_row) > 0 else -1),
                    "sources": _int(count_row[1] if len(count_row) > 1 else -1),
                    "variants": _int(count_row[2] if len(count_row) > 2 else -1),
                    "options": _int(count_row[3] if len(count_row) > 3 else -1),
                }
                if actual_counts != {key: _int((expected_counts or {}).get(key)) for key in actual_counts}:
                    raise GearReleaseIntegrityError("active Gear Release row counts do not match sealed content")
                if community_id:
                    cur.execute(
                        """
                        SELECT template_id, class_key, spec_key, role, election_rank,
                               source_key, source_url, source_status, sample_count,
                               profile_hash, gear_hash, selection_intent_json,
                               resolved_gear_signature, semantic_gear_signature,
                               dependency_vector_json, evidence_json, problems_json,
                               payload_json, payload_json->>'updatedAt',
                               payload_json->>'expiresAt', row_hash
                        FROM cache.websim_community_release_templates
                        WHERE release_id = %s AND class_key = %s AND spec_key = %s
                          AND role = 'winner'
                        ORDER BY election_rank, template_id
                        """,
                        (community_id, _text(class_key), _text(spec_key)),
                    )
                    winner_db_rows = cur.fetchall()
                    winner_rows = [self._community_row_from_db(row) for row in winner_db_rows]
                    is_hero_projection = community.get("schemaRevision") == "community-release-v2"
                    expected_winner_count = 2 if is_hero_projection else 1
                    if len(winner_rows) != expected_winner_count:
                        raise GearReleaseIntegrityError(
                            "active Community Release must expose exactly two hero winners per spec"
                            if is_hero_projection
                            else "active Community Release must expose exactly one winner per spec"
                        )
                    if any(
                        canonical_row_hash(row) != _text(db_row[20])
                        for row, db_row in zip(winner_rows, winner_db_rows)
                    ):
                        raise GearReleaseIntegrityError("active Community winner row integrity failed")
                    community_templates = []
                    for row in winner_rows:
                        public_template = _canonical(
                            row.get("payload") if isinstance(row.get("payload"), dict) else {}
                        )
                        # Release storage owns an immutable internal templateId,
                        # while the established public mini-program contract uses
                        # id.  A validated winner is directly importable; project
                        # that fact explicitly instead of leaking the release-row
                        # identity shape into the existing public read model.
                        public_template.pop("templateId", None)
                        public_template.pop("enhancementBySlot", None)
                        nested_payload = public_template.get("payload")
                        if isinstance(nested_payload, dict) and "enhancementBySlot" in nested_payload:
                            nested_payload = _canonical(nested_payload)
                            nested_payload.pop("enhancementBySlot", None)
                            public_template["payload"] = nested_payload
                        public_template["id"] = _text(
                            public_template.get("id") or row.get("templateId")
                        )
                        public_template["canApplyGear"] = True
                        enhancement_by_slot = _public_enhancement_by_slot(
                            row.get("selectionIntent")
                        )
                        if enhancement_by_slot:
                            public_template["enhancementBySlot"] = enhancement_by_slot
                        community_templates.append(public_template)
                    if is_hero_projection:
                        hero_keys = [_text(template.get("heroKey")) for template in community_templates]
                        if len(set(hero_keys)) != expected_winner_count or any(
                            not is_public_hero_gear_projection(template)
                            for template in community_templates
                        ):
                            raise GearReleaseIntegrityError("active Community hero winner projection integrity failed")
                if include_catalog:
                    normalized_slot = _text(catalog_slot)
                    variant_slot_clause = " AND slot = %s" if normalized_slot else ""
                    variant_params = (gear_id, normalized_slot) if normalized_slot else (gear_id,)
                    cur.execute(
                        f"""
                        SELECT variant_id, item_id, variant_key, slot, label, source_type,
                               difficulty_key, item_level, simc_options_json, status,
                               blockers_json, payload_json, source_updated_at, row_hash
                        FROM cache.websim_gear_release_variants
                        WHERE release_id = %s{variant_slot_clause}
                        ORDER BY variant_id
                        """,
                        variant_params,
                    )
                    variant_db_rows = cur.fetchall()
                    snapshot["variants"] = [
                        {
                            "variantId": _text(row[0]),
                            "itemId": _text(row[1]),
                            "variantKey": _text(row[2]),
                            "slot": _text(row[3]),
                            "label": _text(row[4]),
                            "sourceType": _text(row[5]),
                            "difficultyKey": _text(row[6]),
                            "itemLevel": _int(row[7]),
                            "simcOptions": _canonical(row[8] if isinstance(row[8], dict) else {}),
                            "status": _text(row[9]),
                            "blockers": _canonical(row[10] if isinstance(row[10], list) else []),
                            "payload": _canonical(row[11] if isinstance(row[11], dict) else {}),
                            "updatedAt": _text(row[12]),
                        }
                        for row in variant_db_rows
                    ]
                    if any(
                        canonical_row_hash(record) != _text(row[13])
                        for record, row in zip(snapshot["variants"], variant_db_rows)
                    ):
                        raise GearReleaseIntegrityError("active Gear Release variant row integrity failed")
                    item_ids = sorted({_text(row.get("itemId")) for row in snapshot["variants"] if _text(row.get("itemId"))})
                    item_scope_clause = " AND item_id = ANY(%s::text[])" if normalized_slot else ""
                    item_scope_params = (gear_id, item_ids) if normalized_slot else (gear_id,)
                    cur.execute(
                        f"""
                        SELECT item_id, name, slot, item_level, source_status, payload_json,
                               source_updated_at, row_hash
                        FROM cache.websim_gear_release_items
                        WHERE release_id = %s{item_scope_clause}
                        ORDER BY item_id
                        """,
                        item_scope_params,
                    )
                    item_db_rows = cur.fetchall()
                    snapshot["items"] = [
                        {
                            "itemId": _text(row[0]),
                            "name": _text(row[1]),
                            "slot": _text(row[2]),
                            "itemLevel": None if row[3] is None else _int(row[3]),
                            "sourceStatus": _text(row[4]),
                            "payload": _canonical(row[5] if isinstance(row[5], dict) else {}),
                            "updatedAt": _text(row[6]),
                        }
                        for row in item_db_rows
                    ]
                    if any(
                        canonical_row_hash(record) != _text(row[7])
                        for record, row in zip(snapshot["items"], item_db_rows)
                    ):
                        raise GearReleaseIntegrityError("active Gear Release item row integrity failed")
                    cur.execute(
                        f"""
                        SELECT source_id, item_id, source_type, source_key, source_label,
                               instance_id, encounter_id, difficulty_key, season_revision,
                               payload_json, source_updated_at, row_hash
                        FROM cache.websim_gear_release_sources
                        WHERE release_id = %s{item_scope_clause}
                        ORDER BY source_id
                        """,
                        item_scope_params,
                    )
                    source_db_rows = cur.fetchall()
                    snapshot["sources"] = [
                        {
                            "sourceId": _text(row[0]),
                            "itemId": _text(row[1]),
                            "sourceType": _text(row[2]),
                            "sourceKey": _text(row[3]),
                            "sourceLabel": _text(row[4]),
                            "instanceId": _text(row[5]),
                            "encounterId": _text(row[6]),
                            "difficultyKey": _text(row[7]),
                            "seasonRevision": _text(row[8]),
                            "payload": _canonical(row[9] if isinstance(row[9], dict) else {}),
                            "updatedAt": _text(row[10]),
                        }
                        for row in source_db_rows
                    ]
                    if any(
                        canonical_row_hash(record) != _text(row[11])
                        for record, row in zip(snapshot["sources"], source_db_rows)
                    ):
                        raise GearReleaseIntegrityError("active Gear Release source row integrity failed")
                    cur.execute(
                        """
                        SELECT option_id, variant_id, option_key, option_type, name,
                               applicable_slots_json, simc_options_json, status, is_visible,
                               payload_json, source_updated_at, row_hash
                        FROM cache.websim_gear_release_mod_options
                        WHERE release_id = %s
                        ORDER BY option_id
                        """,
                        (gear_id,),
                    )
                    option_db_rows = cur.fetchall()
                    snapshot["options"] = [
                        {
                            "optionId": _text(row[0]),
                            "variantId": _text(row[1]),
                            "optionKey": _text(row[2]),
                            "optionType": _text(row[3]),
                            "name": _text(row[4]),
                            "applicableSlots": _canonical(row[5] if isinstance(row[5], list) else []),
                            "simcOptions": _canonical(row[6] if isinstance(row[6], dict) else {}),
                            "status": _text(row[7]),
                            "isVisible": row[8] is True,
                            "payload": _canonical(row[9] if isinstance(row[9], dict) else {}),
                            "updatedAt": _text(row[10]),
                        }
                        for row in option_db_rows
                    ]
                    if any(
                        canonical_row_hash(record) != _text(row[11])
                        for record, row in zip(snapshot["options"], option_db_rows)
                    ):
                        raise GearReleaseIntegrityError("active Gear Release option row integrity failed")
        return {
            "gearRelease": gear,
            "communityRelease": community,
            "communityTemplates": community_templates,
            "gearSnapshot": snapshot if include_catalog else None,
        }

    def load_active_observed_compile_context(
        self,
        binding: dict[str, Any],
        gear_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Read only the sealed Gear Release rows used by one observed batch."""

        if not _readable_release_binding(binding):
            raise GearReleaseIntegrityError(
                "formal active or candidate preview Manifest binding is required"
            )
        manifest = (
            binding.get("manifest")
            if isinstance(binding.get("manifest"), dict)
            else {}
        )
        gear = _exact_release_descriptor(binding.get("gearRelease"))
        gear_id = _text(manifest.get("gearCatalogReleaseId"))
        if gear_id != gear["releaseId"]:
            raise GearReleaseIntegrityError(
                "active observed compile Gear Release does not match the Manifest"
            )
        item_ids, gem_ids, enchant_ids, embellishments = _observed_compile_scope(
            gear_items
        )
        if not item_ids:
            raise GearReleaseIntegrityError(
                "observed compile requires at least one gear item"
            )

        snapshot = {"items": [], "sources": [], "variants": [], "options": []}
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
                )
                cur.execute(
                    """
                    /* gear_release_observed_compile_counts */
                    SELECT
                        (SELECT COUNT(*) FROM cache.websim_gear_release_items WHERE release_id = %s),
                        (SELECT COUNT(*) FROM cache.websim_gear_release_sources WHERE release_id = %s),
                        (SELECT COUNT(*) FROM cache.websim_gear_release_variants WHERE release_id = %s),
                        (SELECT COUNT(*) FROM cache.websim_gear_release_mod_options WHERE release_id = %s)
                    """,
                    (gear_id, gear_id, gear_id, gear_id),
                )
                count_row = tuple(cur.fetchone() or ())
                expected_counts = (
                    gear.get("content", {}).get("counts")
                    if isinstance(gear.get("content"), dict)
                    else {}
                )
                actual_counts = {
                    "items": _int(count_row[0] if len(count_row) > 0 else -1),
                    "sources": _int(count_row[1] if len(count_row) > 1 else -1),
                    "variants": _int(count_row[2] if len(count_row) > 2 else -1),
                    "options": _int(count_row[3] if len(count_row) > 3 else -1),
                }
                if actual_counts != {
                    key: _int((expected_counts or {}).get(key))
                    for key in actual_counts
                }:
                    raise GearReleaseIntegrityError(
                        "active Gear Release row counts do not match sealed content"
                    )

                cur.execute(
                    """
                    /* gear_release_observed_compile_items */
                    SELECT item_id, name, slot, item_level, source_status,
                           payload_json, source_updated_at, row_hash
                    FROM cache.websim_gear_release_items
                    WHERE release_id = %s
                      AND item_id = ANY(%s::text[])
                    ORDER BY item_id
                    """,
                    (gear_id, item_ids),
                )
                item_db_rows = cur.fetchall()
                snapshot["items"] = [
                    {
                        "itemId": _text(row[0]),
                        "name": _text(row[1]),
                        "slot": _text(row[2]),
                        "itemLevel": None if row[3] is None else _int(row[3]),
                        "sourceStatus": _text(row[4]),
                        "payload": _canonical(
                            row[5] if isinstance(row[5], dict) else {}
                        ),
                        "updatedAt": _text(row[6]),
                    }
                    for row in item_db_rows
                ]
                if any(
                    canonical_row_hash(record) != _text(row[7])
                    for record, row in zip(snapshot["items"], item_db_rows)
                ):
                    raise GearReleaseIntegrityError(
                        "active Gear Release item row integrity failed"
                    )
                loaded_item_ids = {
                    _text(record.get("itemId"))
                    for record in snapshot["items"]
                }
                if loaded_item_ids != set(item_ids):
                    raise GearReleaseIntegrityError(
                        "active Gear Release is missing observed compile items"
                    )

                cur.execute(
                    """
                    /* gear_release_observed_compile_variants */
                    SELECT variant_id, item_id, variant_key, slot, label,
                           source_type, difficulty_key, item_level,
                           simc_options_json, status, blockers_json,
                           payload_json, source_updated_at, row_hash
                    FROM cache.websim_gear_release_variants
                    WHERE release_id = %s
                      AND item_id = ANY(%s::text[])
                    ORDER BY variant_id
                    """,
                    (gear_id, item_ids),
                )
                variant_db_rows = cur.fetchall()
                snapshot["variants"] = [
                    {
                        "variantId": _text(row[0]),
                        "itemId": _text(row[1]),
                        "variantKey": _text(row[2]),
                        "slot": _text(row[3]),
                        "label": _text(row[4]),
                        "sourceType": _text(row[5]),
                        "difficultyKey": _text(row[6]),
                        "itemLevel": _int(row[7]),
                        "simcOptions": _canonical(
                            row[8] if isinstance(row[8], dict) else {}
                        ),
                        "status": _text(row[9]),
                        "blockers": _canonical(
                            row[10] if isinstance(row[10], list) else []
                        ),
                        "payload": _canonical(
                            row[11] if isinstance(row[11], dict) else {}
                        ),
                        "updatedAt": _text(row[12]),
                    }
                    for row in variant_db_rows
                ]
                if any(
                    canonical_row_hash(record) != _text(row[13])
                    for record, row in zip(
                        snapshot["variants"],
                        variant_db_rows,
                    )
                ):
                    raise GearReleaseIntegrityError(
                        "active Gear Release variant row integrity failed"
                    )

                cur.execute(
                    """
                    /* gear_release_observed_compile_options */
                    SELECT option_id, variant_id, option_key, option_type, name,
                           applicable_slots_json, simc_options_json, status,
                           is_visible, payload_json, source_updated_at, row_hash
                    FROM cache.websim_gear_release_mod_options
                    WHERE release_id = %s
                      AND (
                          simc_options_json->>'gem_id' = ANY(%s::text[])
                          OR simc_options_json->>'enchant_id' = ANY(%s::text[])
                          OR simc_options_json->>'embellishment' = ANY(%s::text[])
                      )
                    ORDER BY option_id
                    """,
                    (gear_id, gem_ids, enchant_ids, embellishments),
                )
                option_db_rows = cur.fetchall()
                snapshot["options"] = [
                    {
                        "optionId": _text(row[0]),
                        "variantId": _text(row[1]),
                        "optionKey": _text(row[2]),
                        "optionType": _text(row[3]),
                        "name": _text(row[4]),
                        "applicableSlots": _canonical(
                            row[5] if isinstance(row[5], list) else []
                        ),
                        "simcOptions": _canonical(
                            row[6] if isinstance(row[6], dict) else {}
                        ),
                        "status": _text(row[7]),
                        "isVisible": row[8] is True,
                        "payload": _canonical(
                            row[9] if isinstance(row[9], dict) else {}
                        ),
                        "updatedAt": _text(row[10]),
                    }
                    for row in option_db_rows
                ]
                if any(
                    canonical_row_hash(record) != _text(row[11])
                    for record, row in zip(
                        snapshot["options"],
                        option_db_rows,
                    )
                ):
                    raise GearReleaseIntegrityError(
                        "active Gear Release option row integrity failed"
                    )
        return {
            "gearRelease": gear,
            "gearSnapshot": snapshot,
        }

    def load_active_community_template_import(
        self,
        binding: dict[str, Any],
        class_key: str,
        spec_key: str,
        template_id: str,
    ) -> dict[str, Any]:
        """Read one observed winner and only its import authority from one active binding."""

        if not _readable_release_binding(binding):
            raise GearReleaseIntegrityError("formal active or candidate preview Manifest binding is required")
        manifest = binding.get("manifest") if isinstance(binding.get("manifest"), dict) else {}
        gear = _exact_release_descriptor(binding.get("gearRelease"))
        gear_id = _text(manifest.get("gearCatalogReleaseId"))
        if gear_id != gear["releaseId"]:
            raise GearReleaseIntegrityError("active import Gear Release does not match the Manifest")
        community_id = _text(manifest.get("communityTemplateReleaseId"))
        community = _exact_release_descriptor(binding.get("communityRelease"))
        if (
            not community_id
            or community_id != community["releaseId"]
            or community["validatedAgainstReleaseId"] != gear_id
        ):
            raise GearReleaseIntegrityError("active import Community Release does not match the Manifest")

        requested_class = _text(class_key)
        requested_spec = _text(spec_key)
        requested_template = _text(template_id)
        if not requested_class or not requested_spec or not requested_template:
            raise GearReleaseIntegrityError("community template import identity is required")

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cur.execute(
                    """
                    SELECT template_id, class_key, spec_key, role, election_rank,
                           source_key, source_url, source_status, sample_count,
                           profile_hash, gear_hash, selection_intent_json,
                           resolved_gear_signature, semantic_gear_signature,
                           dependency_vector_json, evidence_json, problems_json,
                           payload_json, payload_json->>'updatedAt',
                           payload_json->>'expiresAt', row_hash
                    FROM cache.websim_community_release_templates
                    WHERE release_id = %s AND class_key = %s AND spec_key = %s
                      AND template_id = %s AND role = 'winner'
                      AND source_key = 'raiderio_observed_profile'
                    ORDER BY election_rank, template_id
                    """,
                    (community_id, requested_class, requested_spec, requested_template),
                )
                winner_db_rows = cur.fetchall()
                if len(winner_db_rows) != 1:
                    raise GearReleaseIntegrityError("active Community import must expose exactly one observed winner")
                winner = self._community_row_from_db(winner_db_rows[0])
                if (
                    winner.get("templateId") != requested_template
                    or winner.get("classKey") != requested_class
                    or winner.get("specKey") != requested_spec
                    or winner.get("role") != "winner"
                    or winner.get("sourceKey") != "raiderio_observed_profile"
                    or canonical_row_hash(winner) != _text(winner_db_rows[0][20])
                ):
                    raise GearReleaseIntegrityError("active Community import winner integrity failed")
                if community.get("schemaRevision") == "community-release-v2":
                    projection = _canonical(winner.get("payload") if isinstance(winner.get("payload"), dict) else {})
                    projection["id"] = _text(projection.get("id") or winner.get("templateId"))
                    projection["canApplyGear"] = True
                    if not is_public_hero_gear_projection(projection):
                        raise GearReleaseIntegrityError("active Community import hero projection integrity failed")

                intent = winner.get("selectionIntent") if isinstance(winner.get("selectionIntent"), dict) else {}
                slots = intent.get("slots") if isinstance(intent.get("slots"), dict) else {}
                requested_pairs = sorted({
                    (_text(selection.get("itemId")), _text(selection.get("variantKey")))
                    for selection in slots.values()
                    if isinstance(selection, dict)
                })
                if not requested_pairs or any(not item_id or not variant_key for item_id, variant_key in requested_pairs):
                    raise GearReleaseIntegrityError("active Community import selection is incomplete")
                item_ids = [item_id for item_id, _variant_key in requested_pairs]
                variant_keys = [variant_key for _item_id, variant_key in requested_pairs]

                cur.execute(
                    """
                    WITH requested(item_id, variant_key) AS (
                        SELECT * FROM unnest(%s::text[], %s::text[])
                    )
                    SELECT requested.item_id, requested.variant_key,
                           variant.variant_id, variant.item_id, variant.variant_key, variant.slot,
                           variant.label, variant.source_type, variant.difficulty_key,
                           variant.item_level, variant.simc_options_json, variant.status,
                           variant.blockers_json, variant.payload_json,
                           variant.source_updated_at, variant.row_hash
                    FROM requested
                    JOIN LATERAL (
                        SELECT candidate.*
                        FROM cache.websim_gear_release_variants candidate
                        WHERE candidate.release_id = %s
                          AND candidate.item_id = requested.item_id
                          AND (
                              candidate.variant_key = requested.variant_key
                              OR LEFT(
                                  regexp_replace(candidate.variant_key, '[^A-Za-z0-9_:/.-]+', '', 'g'),
                                  240
                              ) = requested.variant_key
                          )
                        ORDER BY
                            CASE WHEN candidate.variant_key = requested.variant_key THEN 0 ELSE 1 END,
                            candidate.variant_id
                        LIMIT 1
                    ) variant ON TRUE
                    ORDER BY variant.item_id, variant.variant_key, variant.variant_id
                    """,
                    (item_ids, variant_keys, gear_id),
                )
                variant_db_rows = cur.fetchall()
                variants = []
                for row in variant_db_rows:
                    record = {
                        "variantId": _text(row[2]),
                        "itemId": _text(row[3]),
                        "variantKey": _text(row[4]),
                        "slot": _text(row[5]),
                        "label": _text(row[6]),
                        "sourceType": _text(row[7]),
                        "difficultyKey": _text(row[8]),
                        "itemLevel": _int(row[9]),
                        "simcOptions": _canonical(row[10] if isinstance(row[10], dict) else {}),
                        "status": _text(row[11]),
                        "blockers": _canonical(row[12] if isinstance(row[12], list) else []),
                        "payload": _canonical(row[13] if isinstance(row[13], dict) else {}),
                        "updatedAt": _text(row[14]),
                    }
                    if canonical_row_hash(record) != _text(row[15]):
                        raise GearReleaseIntegrityError("active Community import variant integrity failed")
                    record["requestedItemId"] = _text(row[0])
                    record["requestedVariantKey"] = _text(row[1])
                    variants.append(record)
                if (
                    len(variants) != len(requested_pairs)
                    or {(row["requestedItemId"], row["requestedVariantKey"]) for row in variants} != set(requested_pairs)
                    or any(row["requestedItemId"] != row["itemId"] for row in variants)
                ):
                    raise GearReleaseIntegrityError("active Community import variant integrity failed")

                selected_item_ids = sorted({row["itemId"] for row in variants})
                cur.execute(
                    """
                    SELECT item_id, name, slot, item_level, source_status, payload_json,
                           source_updated_at, row_hash
                    FROM cache.websim_gear_release_items
                    WHERE release_id = %s AND item_id = ANY(%s::text[])
                    ORDER BY item_id
                    """,
                    (gear_id, selected_item_ids),
                )
                item_db_rows = cur.fetchall()
                items = [
                    {
                        "itemId": _text(row[0]),
                        "name": _text(row[1]),
                        "slot": _text(row[2]),
                        "itemLevel": None if row[3] is None else _int(row[3]),
                        "sourceStatus": _text(row[4]),
                        "payload": _canonical(row[5] if isinstance(row[5], dict) else {}),
                        "updatedAt": _text(row[6]),
                    }
                    for row in item_db_rows
                ]
                if (
                    len(items) != len(selected_item_ids)
                    or {row["itemId"] for row in items} != set(selected_item_ids)
                    or any(canonical_row_hash(record) != _text(row[7]) for record, row in zip(items, item_db_rows))
                ):
                    raise GearReleaseIntegrityError("active Community import item integrity failed")

                cur.execute(
                    """
                    SELECT source_id, item_id, source_type, source_key, source_label,
                           instance_id, encounter_id, difficulty_key, season_revision,
                           payload_json, source_updated_at, row_hash
                    FROM cache.websim_gear_release_sources
                    WHERE release_id = %s AND item_id = ANY(%s::text[])
                    ORDER BY source_id
                    """,
                    (gear_id, selected_item_ids),
                )
                source_db_rows = cur.fetchall()
                sources = [
                    {
                        "sourceId": _text(row[0]),
                        "itemId": _text(row[1]),
                        "sourceType": _text(row[2]),
                        "sourceKey": _text(row[3]),
                        "sourceLabel": _text(row[4]),
                        "instanceId": _text(row[5]),
                        "encounterId": _text(row[6]),
                        "difficultyKey": _text(row[7]),
                        "seasonRevision": _text(row[8]),
                        "payload": _canonical(row[9] if isinstance(row[9], dict) else {}),
                        "updatedAt": _text(row[10]),
                    }
                    for row in source_db_rows
                ]
                if (
                    not sources
                    or not set(selected_item_ids).issubset({row["itemId"] for row in sources})
                    or any(canonical_row_hash(record) != _text(row[11]) for record, row in zip(sources, source_db_rows))
                ):
                    raise GearReleaseIntegrityError("active Community import source integrity failed")

                selected_option_keys = _selected_option_ids(intent)
                options = []
                if selected_option_keys:
                    cur.execute(
                        """
                        SELECT option_id, variant_id, option_key, option_type, name,
                               applicable_slots_json, simc_options_json, status, is_visible,
                               payload_json, source_updated_at, row_hash
                        FROM cache.websim_gear_release_mod_options
                        WHERE release_id = %s
                          AND option_key = ANY(%s::text[])
                        ORDER BY option_id
                        """,
                        (gear_id, selected_option_keys),
                    )
                    option_db_rows = cur.fetchall()
                    options = [
                        {
                            "optionId": _text(row[0]),
                            "variantId": _text(row[1]),
                            "optionKey": _text(row[2]),
                            "optionType": _text(row[3]),
                            "name": _text(row[4]),
                            "applicableSlots": _canonical(row[5] if isinstance(row[5], list) else []),
                            "simcOptions": _canonical(row[6] if isinstance(row[6], dict) else {}),
                            "status": _text(row[7]),
                            "isVisible": row[8] is True,
                            "payload": _canonical(row[9] if isinstance(row[9], dict) else {}),
                            "updatedAt": _text(row[10]),
                        }
                        for row in option_db_rows
                    ]
                    if (
                        {row["optionKey"] for row in options} != set(selected_option_keys)
                        or any(canonical_row_hash(record) != _text(row[11]) for record, row in zip(options, option_db_rows))
                    ):
                        raise GearReleaseIntegrityError("active Community import option integrity failed")

        return {
            "binding": _canonical(binding),
            "gearRelease": gear,
            "communityRelease": community,
            "winner": winner,
            "items": items,
            "sources": sources,
            "variants": variants,
            "options": options,
        }

    def load_community_release(
        self,
        gear_release_id: str,
        community_release_id: str,
    ) -> dict[str, Any]:
        """Read and integrity-check one Community Release bound to one Gear Release."""

        gear_id = _text(gear_release_id)
        community_id = _text(community_release_id)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                gear = self._select_release(cur, gear_id)
                community = self._select_release(cur, community_id)
                if gear is None or community is None:
                    raise GearReleaseIntegrityError("candidate release pair is missing")
                gear = _exact_release_descriptor(gear)
                community = _exact_release_descriptor(community)
                if gear["releaseKind"] != "gear" or community["releaseKind"] != "community":
                    raise GearReleaseIntegrityError("candidate release pair kind is invalid")
                if community["validatedAgainstReleaseId"] != gear["releaseId"]:
                    raise GearReleaseIntegrityError("Community Release is not bound to the Gear Release")
                if community["seasonRevision"] != gear["seasonRevision"]:
                    raise GearReleaseIntegrityError("candidate release pair season mismatch")
                if community["dependencyRevisions"] != gear["dependencyRevisions"]:
                    raise GearReleaseIntegrityError("candidate release pair dependency mismatch")
                cur.execute(
                    """
                    SELECT template_id, class_key, spec_key, role, election_rank,
                           source_key, source_url, source_status, sample_count,
                           profile_hash, gear_hash, selection_intent_json,
                           resolved_gear_signature, semantic_gear_signature,
                           dependency_vector_json, evidence_json, problems_json,
                           payload_json, payload_json->>'updatedAt',
                           payload_json->>'expiresAt'
                    FROM cache.websim_community_release_templates
                    WHERE release_id = %s
                    ORDER BY class_key, spec_key, role, election_rank, template_id
                    """,
                    (community_id,),
                )
                rows = [self._community_row_from_db(row) for row in cur.fetchall()]
        if community_rows_summary(rows) != community["content"]:
            raise GearReleaseIntegrityError("Community Release content integrity failed")
        return {
            "gearRelease": gear,
            "communityRelease": community,
            "rows": rows,
            "winners": [row for row in rows if row.get("role") == "winner"],
        }

    @staticmethod
    def _community_row_from_db(row: Any) -> dict[str, Any]:
        values = list(row or ())
        return {
            "templateId": _text(values[0]),
            "classKey": _text(values[1]),
            "specKey": _text(values[2]),
            "role": _text(values[3]),
            "electionRank": _int(values[4]),
            "sourceKey": _text(values[5]),
            "sourceUrl": _text(values[6]),
            "sourceStatus": _text(values[7]),
            "sampleCount": _int(values[8]),
            "profileHash": _text(values[9]),
            "gearHash": _text(values[10]),
            "selectionIntent": _canonical(values[11] if isinstance(values[11], dict) else {}),
            "resolvedGearSignature": _text(values[12]),
            "semanticGearSignature": _text(values[13]),
            "dependencyVector": _canonical(values[14] if isinstance(values[14], dict) else {}),
            "evidence": _canonical(values[15] if isinstance(values[15], (dict, list)) else {}),
            "problems": _canonical(values[16] if isinstance(values[16], list) else []),
            "payload": _canonical(values[17] if isinstance(values[17], dict) else {}),
            "updatedAt": _text(values[18]),
            "expiresAt": _text(values[19]),
        }

    @staticmethod
    def _insert_registry(cur, release: dict[str, Any], gate_result: dict[str, Any]) -> None:
        cur.execute(
            """
            INSERT INTO cache.websim_release_registry (
                release_id, release_kind, season_revision, schema_revision, content_hash,
                parent_release_id, validated_against_release_id, release_status,
                dependency_vector_json, gate_result_json, source_json, content_summary_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb)
            """,
            (
                release["releaseId"],
                release["releaseKind"],
                release["seasonRevision"],
                release["schemaRevision"],
                release["contentHash"],
                release.get("parentReleaseId") or None,
                release.get("validatedAgainstReleaseId") or None,
                release["releaseStatus"],
                _json_param(release.get("dependencyRevisions") or {}),
                _json_param(gate_result),
                _json_param(release.get("source") or {}),
                _json_param(release.get("content") or {}),
            ),
        )

    @staticmethod
    def _insert_event(cur, *, release_id: str = "", manifest_revision: str = "", event_type: str, event: dict[str, Any]) -> None:
        cur.execute(
            """
            INSERT INTO cache.websim_release_events (
                release_id, manifest_revision, event_type, event_json
            ) VALUES (%s, %s, %s, %s::jsonb)
            """,
            (release_id or None, manifest_revision or None, event_type, _json_param(event)),
        )

    @staticmethod
    def _existing_or_insert(cur, release: dict[str, Any], gate_result: dict[str, Any]) -> bool:
        expected = _exact_release_descriptor(release)
        existing = GearReleaseStore._select_release(cur, expected["releaseId"])
        if existing is not None:
            if _exact_release_descriptor(existing) != expected:
                raise GearReleaseIntegrityError("existing release ID has different sealed content")
            return True
        GearReleaseStore._insert_registry(cur, expected, gate_result)
        return False

    def _legacy_shadow_snapshot(
        self,
        release: dict[str, Any],
        trusted_socket_evidence: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            from . import gear_release_tool
        except ImportError:
            import gear_release_tool

        raw_snapshot = self.snapshot_staging_gear()
        source = (
            release.get("source")
            if isinstance(release.get("source"), dict)
            else {}
        )
        source_evidence = (
            source.get("sourceEvidence")
            if isinstance(source.get("sourceEvidence"), dict)
            else {}
        )
        if (
            gear_snapshot_summary(raw_snapshot)["snapshotHash"]
            != _text(source.get("stagingSnapshotHash"))
        ):
            raise GearReleaseIntegrityError(
                "Gear Release shadow input is not bound to staging"
            )
        legacy_snapshot = gear_release_tool._legacy_shadow_snapshot(
            raw_snapshot,
            season_revision=_text(release.get("seasonRevision")),
            capability_revision=_text(
                (
                    release.get("dependencyRevisions")
                    if isinstance(
                        release.get("dependencyRevisions"),
                        dict,
                    )
                    else {}
                ).get("capabilityRevision")
            ),
            socket_bonus_evidence=trusted_socket_evidence,
        )
        return raw_snapshot, legacy_snapshot

    @staticmethod
    def _validate_canonical_gear_gate(
        release: dict[str, Any],
        snapshot: dict[str, Any],
        gate_result: dict[str, Any],
        legacy_snapshot: dict[str, Any],
    ) -> tuple[
        dict[tuple[str, str, str], dict[str, Any]],
        dict[str, set[str]],
    ]:
        try:
            from . import gear_fact_compiler
            from . import gear_fact_shadow
        except ImportError:
            import gear_fact_compiler
            import gear_fact_shadow

        gate = gate_result if isinstance(gate_result, dict) else {}
        source = release.get("source") if isinstance(release.get("source"), dict) else {}
        source_evidence = (
            source.get("sourceEvidence")
            if isinstance(source.get("sourceEvidence"), dict)
            else {}
        )
        def is_sha256(value: Any) -> bool:
            text = _text(value)
            suffix = text.removeprefix("sha256:")
            return (
                text.startswith("sha256:")
                and len(suffix) == 64
                and all(character in "0123456789abcdef" for character in suffix)
            )

        if (
            gate.get("status") != "validated"
            or source_evidence.get("compilerPolicyDigest")
            != _hash(gear_fact_compiler.FACT_POLICIES)
            or not is_sha256(
                source_evidence.get("canonicalFactDigest")
            )
        ):
            raise GearReleaseIntegrityError(
                "Gear Release canonical gate digests/status are incomplete"
            )

        summary = gear_snapshot_summary(snapshot)
        if (
            _text(gate.get("snapshotHash")) != summary["snapshotHash"]
            or gate.get("counts") != summary["counts"]
        ):
            raise GearReleaseIntegrityError(
                "Gear Release canonical gate snapshot binding is incomplete"
            )

        projected_facts: dict[tuple[str, str, str], dict[str, Any]] = {}
        rows_by_category = {
            category: [
                row
                for row in snapshot.get(category) or ()
                if isinstance(row, dict)
            ]
            for category in ("items", "variants", "options")
        }
        if not rows_by_category["items"] or not rows_by_category["variants"]:
            raise GearReleaseIntegrityError(
                "Gear Release canonical snapshot is incomplete"
            )
        for category, rows in rows_by_category.items():
            for row in rows:
                payload = (
                    row.get("payload")
                    if isinstance(row.get("payload"), dict)
                    else {}
                )
                facts = payload.get("canonicalFacts")
                if not isinstance(facts, list) or not facts:
                    raise GearReleaseIntegrityError(
                        "Gear Release canonical snapshot Facts are incomplete"
                    )
                for fact in facts:
                    if not isinstance(fact, dict):
                        raise GearReleaseIntegrityError(
                            "Gear Release canonical snapshot Facts are incomplete"
                        )
                    identity = (
                        _text(fact.get("factKey")),
                        _text(fact.get("factValueHash")),
                        _text(fact.get("provenanceHash")),
                    )
                    if (
                        not all(identity)
                        or identity in projected_facts
                    ):
                        raise GearReleaseIntegrityError(
                            "Gear Release canonical snapshot Facts are incomplete"
                        )
                    projected_facts[identity] = fact

        required_fact_types: dict[str, set[str]] = {}
        for row in legacy_snapshot.get("items") or ():
            if not isinstance(row, dict) or not _text(row.get("itemId")):
                continue
            required_fact_types[
                f"item:{_text(row.get('itemId'))}"
            ] = {
                "item_identity",
                "slot_compatibility",
                "socket_count",
                "enchant_capability",
                "embellishment_capability",
                "allowed_enhancement_options",
                "item_set_membership",
                "equipment_uniqueness",
            }
        for row in legacy_snapshot.get("variants") or ():
            if (
                not isinstance(row, dict)
                or not _text(row.get("itemId"))
                or not _text(row.get("variantKey"))
            ):
                continue
            required_fact_types[
                "item:"
                + _text(row.get("itemId"))
                + "/variant:"
                + _text(row.get("variantKey"))
            ] = {
                "item_identity",
                "slot_compatibility",
                "variant_track",
                "static_stats",
                "socket_count",
                "enchant_capability",
                "embellishment_capability",
                "allowed_enhancement_options",
                "item_set_membership",
                "executable_item_options",
            }
        for row in legacy_snapshot.get("options") or ():
            if not isinstance(row, dict) or not _text(row.get("optionId")):
                continue
            required_fact_types[
                "option:"
                + _text(row.get("optionKey") or row.get("optionId"))
            ] = {"enhancement_option"}
        required_semantics = {
            (subject_key, fact_type)
            for subject_key, fact_types in required_fact_types.items()
            for fact_type in fact_types
        }
        projected_semantics = [
            (
                _text(fact.get("subjectKey")),
                _text(fact.get("factType")),
            )
            for fact in projected_facts.values()
        ]
        if (
            len(projected_semantics) != len(required_semantics)
            or set(projected_semantics) != required_semantics
        ):
            raise GearReleaseIntegrityError(
                "Gear Release canonical Fact universe is incomplete"
            )

        shadow = (
            gate.get("factShadow")
            if isinstance(gate.get("factShadow"), dict)
            else {}
        )
        if shadow.get("schemaRevision") == "gear-fact-shadow-v2":
            recomputed_shadow = gear_fact_shadow.compare_legacy_and_canonical(
                legacy_snapshot,
                projected_facts.values(),
                expected_fact_types_by_subject=required_fact_types,
                include_comparisons=False,
            )
            if (
                shadow.get("status") != "pass"
                or shadow.get("blockers") != []
                or _int(shadow.get("comparisonCount"))
                != len(projected_facts)
                or _canonical(shadow) != _canonical(recomputed_shadow)
            ):
                raise GearReleaseIntegrityError(
                    "Gear Release compact canonical Fact shadow is incomplete"
                )
        else:
            comparisons = shadow.get("comparisons")
            recomputed_shadow = gear_fact_shadow.compare_legacy_and_canonical(
                legacy_snapshot,
                projected_facts.values(),
                expected_fact_types_by_subject=required_fact_types,
            )
            if (
                shadow.get("schemaRevision") != "gear-fact-shadow-v1"
                or shadow.get("status") != "pass"
                or shadow.get("blockers") != []
                or not isinstance(comparisons, list)
                or len(comparisons) != len(projected_facts)
                or _canonical(shadow) != _canonical(recomputed_shadow)
            ):
                raise GearReleaseIntegrityError(
                    "Gear Release exhaustive canonical Fact shadow is incomplete"
                )

        compilation = (
            gate.get("evidenceCompilation")
            if isinstance(gate.get("evidenceCompilation"), dict)
            else {}
        )
        persistence = (
            gate.get("evidencePersistence")
            if isinstance(gate.get("evidencePersistence"), dict)
            else {}
        )
        unresolved_count = sum(
            _text(fact.get("status")).startswith("unresolved_")
            for fact in projected_facts.values()
        )
        streaming_receipt = (
            compilation.get("schemaRevision") == "gear-evidence-receipt-v2"
            and persistence.get("schemaRevision") == "gear-evidence-receipt-v2"
        )
        for owner in ("artifacts", "observations", "facts", "gaps"):
            compiled_owner = (
                compilation.get(owner)
                if isinstance(compilation.get(owner), dict)
                else {}
            )
            persisted_owner = (
                persistence.get(owner)
                if isinstance(persistence.get(owner), dict)
                else {}
            )
            persisted_count = (
                _int(persisted_owner.get("requested"))
                if owner == "gaps"
                else _int(persisted_owner.get("persisted"))
            )
            if streaming_receipt:
                if (
                    _int(compiled_owner.get("count")) != persisted_count
                    or not is_sha256(compiled_owner.get("sequenceDigest"))
                    or compiled_owner.get("sequenceDigest")
                    != persisted_owner.get("sequenceDigest")
                ):
                    raise GearReleaseIntegrityError(
                        "Gear Release streaming evidence persistence receipt is incomplete"
                    )
                continue
            compiled_identities = compiled_owner.get("identities")
            persisted_identities = persisted_owner.get("identities")
            if (
                _int(compiled_owner.get("count")) != persisted_count
                or not isinstance(compiled_identities, list)
                or len(compiled_identities) != persisted_count
                or _canonical(compiled_identities)
                != _canonical(persisted_identities)
                or not is_sha256(
                    compiled_owner.get("identityDigest")
                )
                or compiled_owner.get("identityDigest")
                != _hash(compiled_identities)
                or not is_sha256(
                    persisted_owner.get("identityDigest")
                )
                or compiled_owner.get("identityDigest")
                != persisted_owner.get("identityDigest")
            ):
                raise GearReleaseIntegrityError(
                    "Gear Release evidence persistence receipt is incomplete"
                )
        if streaming_receipt:
            receipt_reconciles = (
                _int(compilation["facts"].get("count"))
                == len(projected_facts)
                and _int(compilation["gaps"].get("count"))
                == unresolved_count
                and _int(gate.get("evidenceGapCount")) == unresolved_count
                and (
                    _int(persistence["gaps"].get("inserted"))
                    + _int(persistence["gaps"].get("reused"))
                )
                == unresolved_count
            )
        else:
            receipt_reconciles = (
                _int(compilation["facts"].get("count"))
                == len(projected_facts)
                and _canonical(compilation["facts"].get("identities"))
                == _canonical(sorted(projected_facts))
                and _int(compilation["gaps"].get("count"))
                == unresolved_count
                and _int(gate.get("evidenceGapCount")) == unresolved_count
                and (
                    _int(persistence["gaps"].get("inserted"))
                    + _int(persistence["gaps"].get("reused"))
                )
                == unresolved_count
            )
        if not receipt_reconciles:
            raise GearReleaseIntegrityError(
                "Gear Release evidence persistence reconciliation is incomplete"
            )
        return projected_facts, required_fact_types

    @staticmethod
    def _verify_persisted_evidence_chain(
        cur,
        projected_facts: dict[
            tuple[str, str, str],
            dict[str, Any],
        ],
        gate_result: dict[str, Any],
        season_revision: str,
    ) -> None:
        try:
            from . import gear_fact_compiler
        except ImportError:
            import gear_fact_compiler

        compilation = gate_result["evidenceCompilation"]
        artifact_ids = list(compilation["artifacts"]["identities"])
        observation_ids = list(compilation["observations"]["identities"])
        gap_ids = list(compilation["gaps"]["identities"])

        if artifact_ids:
            cur.execute(
                """
                SELECT
                    artifact_id, schema_revision, source_type,
                    source_identity, source_revision, season_revision,
                    captured_at::text, payload_hash, payload_json
                FROM cache.websim_gear_evidence_artifacts
                WHERE artifact_id = ANY(%s::text[])
                """,
                (artifact_ids,),
            )
            persisted_artifacts = {
                _text(row[0]): {
                    "artifactId": _text(row[0]),
                    "schemaRevision": _text(row[1]),
                    "sourceType": _text(row[2]),
                    "sourceIdentity": _text(row[3]),
                    "sourceRevision": _text(row[4]),
                    "seasonRevision": _text(row[5]),
                    "capturedAt": _text(row[6]),
                    "payloadHash": _text(row[7]),
                    "payload": _canonical(row[8]),
                }
                for row in cur.fetchall()
                if isinstance(row, (list, tuple)) and len(row) == 9
            }
        else:
            persisted_artifacts = {}
        if set(persisted_artifacts) != set(artifact_ids):
            raise GearReleaseIntegrityError(
                "Gear Release Artifact receipt does not match persistence"
            )

        if observation_ids:
            cur.execute(
                """
                SELECT
                    observation_id, artifact_id, schema_revision,
                    subject_key, fact_type, observed_value_json,
                    parser_revision, source_scope, status
                FROM cache.websim_gear_evidence_observations
                WHERE observation_id = ANY(%s::text[])
                """,
                (observation_ids,),
            )
            persisted_observations = {
                _text(row[0]): {
                    "observationId": _text(row[0]),
                    "artifactId": _text(row[1]),
                    "schemaRevision": _text(row[2]),
                    "subjectKey": _text(row[3]),
                    "factType": _text(row[4]),
                    "observedValue": _canonical(row[5]),
                    "parserRevision": _text(row[6]),
                    "sourceScope": _text(row[7]),
                    "status": _text(row[8]),
                }
                for row in cur.fetchall()
                if isinstance(row, (list, tuple)) and len(row) == 9
            }
        else:
            persisted_observations = {}
        if (
            set(persisted_observations) != set(observation_ids)
            or {
                observation["artifactId"]
                for observation in persisted_observations.values()
            }
            != set(persisted_artifacts)
        ):
            raise GearReleaseIntegrityError(
                "Gear Release Observation receipt does not reconcile Artifacts"
            )

        unresolved_fact_keys = {
            _text(fact.get("factKey"))
            for fact in projected_facts.values()
            if _text(fact.get("status")).startswith("unresolved_")
        }
        referenced_observation_ids: set[str] = set()
        for fact in projected_facts.values():
            observation_refs = {
                _text(reference)
                for reference in (
                    fact.get("persistedObservationRefs")
                    or fact.get("observationRefs")
                    or ()
                )
                if _text(reference)
            }
            referenced_observation_ids.update(observation_refs)
            if (
                observation_refs - set(persisted_observations)
                or (
                    fact.get("status") == "verified"
                    and not observation_refs
                )
            ):
                raise GearReleaseIntegrityError(
                    "Gear Release Fact receipt does not reconcile Observations"
                )
            recompiled = gear_fact_compiler.compile_subject_facts(
                season_revision=_text(season_revision),
                subject_key=_text(fact.get("subjectKey")),
                observations=list(persisted_observations.values()),
                artifacts=list(persisted_artifacts.values()),
                fact_types=[_text(fact.get("factType"))],
            )[0]
            if any(
                _canonical(recompiled.get(field))
                != _canonical(fact.get(field))
                for field in (
                    "factKey",
                    "subjectKey",
                    "factType",
                    "value",
                    "status",
                    "factValueHash",
                    "provenanceHash",
                    "compilerRuleRevision",
                )
            ) or sorted(
                recompiled.get("observationRefs") or ()
            ) != sorted(
                fact.get("persistedObservationRefs") or ()
            ):
                raise GearReleaseIntegrityError(
                    "Gear Release Fact is not reproduced by persisted evidence"
                )
        if referenced_observation_ids != set(persisted_observations):
            raise GearReleaseIntegrityError(
                "Gear Release Fact receipt does not exhaust Observations"
            )

        if gap_ids:
            cur.execute(
                """
                SELECT gap_key, fact_key
                FROM ops.websim_gear_evidence_gaps
                WHERE gap_key = ANY(%s::text[])
                """,
                (gap_ids,),
            )
            persisted_gaps = {
                _text(row[0]): _text(row[1])
                for row in cur.fetchall()
                if isinstance(row, (list, tuple)) and len(row) == 2
            }
        else:
            persisted_gaps = {}
        if (
            set(persisted_gaps) != set(gap_ids)
            or set(persisted_gaps.values()) != unresolved_fact_keys
        ):
            raise GearReleaseIntegrityError(
                "Gear Release Gap receipt does not reconcile unresolved Facts"
            )

    @staticmethod
    def _verify_complete_evidence_universe(
        cur,
        *,
        projected_facts: dict[
            tuple[str, str, str],
            dict[str, Any],
        ],
        required_fact_types: dict[str, set[str]],
        gate_result: dict[str, Any],
        season_revision: str,
        release_source_revision: str,
        raw_staging_snapshot: dict[str, Any],
        trusted_socket_evidence: dict[str, Any],
    ) -> None:
        try:
            from . import gear_fact_compiler
            from . import gear_release_tool
            from .gear_evidence_registry import (
                build_evidence_artifact,
                build_evidence_observation,
            )
        except ImportError:
            import gear_fact_compiler
            import gear_release_tool
            from gear_evidence_registry import (
                build_evidence_artifact,
                build_evidence_observation,
            )

        normalized_bonus_minimums = {
            bonus_id: {
                "minimumTotal": minimum,
                "sourceRevision": trusted_socket_evidence[
                    "sourceRevision"
                ],
            }
            for bonus_id, minimum in trusted_socket_evidence[
                "minimums"
            ].items()
        }
        compilation_receipt = (
            gate_result.get("evidenceCompilation")
            if isinstance(gate_result.get("evidenceCompilation"), dict)
            else {}
        )
        persistence_receipt = (
            gate_result.get("evidencePersistence")
            if isinstance(gate_result.get("evidencePersistence"), dict)
            else {}
        )
        if (
            compilation_receipt.get("schemaRevision")
            == "gear-evidence-receipt-v2"
            and persistence_receipt.get("schemaRevision")
            == "gear-evidence-receipt-v2"
        ):
            return GearReleaseStore._verify_complete_evidence_universe_streaming(
                cur,
                projected_facts=projected_facts,
                gate_result=gate_result,
                season_revision=season_revision,
                release_source_revision=release_source_revision,
                raw_staging_snapshot=raw_staging_snapshot,
                trusted_socket_evidence=trusted_socket_evidence,
                normalized_bonus_minimums=normalized_bonus_minimums,
            )
        expected_compilation = (
            gear_release_tool._compile_release_gear_evidence(
                raw_staging_snapshot,
                season_revision=season_revision,
                source_revision=_text(release_source_revision),
                captured_at="1970-01-01T00:00:00+00:00",
                socket_bonus_minimums=normalized_bonus_minimums,
                socket_bonus_evidence=trusted_socket_evidence,
            )
        )
        expected_artifacts = {
            row["artifactId"]: row
            for row in expected_compilation["artifacts"]
        }
        expected_observations = {
            row["observationId"]: row
            for row in expected_compilation["observations"]
        }
        expected_artifact_ids = sorted(expected_artifacts)
        expected_observation_ids = sorted(expected_observations)

        subjects = sorted(required_fact_types)
        fact_types = sorted({
            fact_type
            for values in required_fact_types.values()
            for fact_type in values
        })
        cur.execute(
            """
            /* gear_release_complete_evidence_universe */
            SELECT
                observation.observation_id,
                observation.artifact_id,
                observation.schema_revision,
                observation.subject_key,
                observation.fact_type,
                observation.observed_value_json,
                observation.parser_revision,
                observation.source_scope,
                observation.status,
                artifact.artifact_id,
                artifact.schema_revision,
                artifact.source_type,
                artifact.source_identity,
                artifact.source_revision,
                artifact.season_revision,
                artifact.captured_at::text,
                artifact.payload_hash,
                artifact.payload_json
            FROM cache.websim_gear_evidence_observations observation
            JOIN cache.websim_gear_evidence_artifacts artifact
              ON artifact.artifact_id = observation.artifact_id
            WHERE artifact.season_revision = %s
              AND observation.subject_key = ANY(%s::text[])
              AND observation.fact_type = ANY(%s::text[])
              AND observation.status = 'accepted'
              AND NOT EXISTS (
                  SELECT 1
                  FROM cache.websim_gear_evidence_invalidations invalidation
                  WHERE invalidation.artifact_id = artifact.artifact_id
                     OR invalidation.observation_id = observation.observation_id
              )
            """,
            (_text(season_revision), subjects, fact_types),
        )
        artifacts: dict[str, dict[str, Any]] = {}
        observations: dict[str, dict[str, Any]] = {}
        for row in cur.fetchall():
            if not isinstance(row, (list, tuple)) or len(row) != 18:
                continue
            observation = {
                "observationId": _text(row[0]),
                "artifactId": _text(row[1]),
                "schemaRevision": _text(row[2]),
                "subjectKey": _text(row[3]),
                "factType": _text(row[4]),
                "observedValue": _canonical(row[5]),
                "parserRevision": _text(row[6]),
                "sourceScope": _text(row[7]),
                "status": _text(row[8]),
            }
            artifact = {
                "artifactId": _text(row[9]),
                "schemaRevision": _text(row[10]),
                "sourceType": _text(row[11]),
                "sourceIdentity": _text(row[12]),
                "sourceRevision": _text(row[13]),
                "seasonRevision": _text(row[14]),
                "capturedAt": _text(row[15]),
                "payloadHash": _text(row[16]),
                "payload": _canonical(row[17]),
            }
            try:
                rebuilt_artifact = build_evidence_artifact(
                    source_type=artifact["sourceType"],
                    source_identity=artifact["sourceIdentity"],
                    source_revision=artifact["sourceRevision"],
                    season_revision=artifact["seasonRevision"],
                    captured_at=artifact["capturedAt"],
                    payload=artifact["payload"],
                )
                rebuilt_observation = build_evidence_observation(
                    artifact_id=observation["artifactId"],
                    subject_key=observation["subjectKey"],
                    fact_type=observation["factType"],
                    observed_value=observation["observedValue"],
                    parser_revision=observation["parserRevision"],
                    source_scope=observation["sourceScope"],
                    status=observation["status"],
                )
            except ValueError as error:
                raise GearReleaseIntegrityError(
                    "Gear Release Store evidence universe is not canonical"
                ) from error
            if (
                _canonical(rebuilt_artifact) != _canonical(artifact)
                or _canonical(rebuilt_observation)
                != _canonical(observation)
            ):
                raise GearReleaseIntegrityError(
                    "Gear Release Store evidence universe is not self-authenticating"
                )
            policy = gear_fact_compiler.FACT_POLICIES.get(
                observation["factType"],
                {},
            )
            if (
                observation["subjectKey"] not in required_fact_types
                or observation["factType"]
                not in required_fact_types[
                    observation["subjectKey"]
                ]
                or artifact["sourceType"]
                not in policy.get("allowedSources", ())
                or observation["sourceScope"]
                not in policy.get("sourceScopes", ())
            ):
                continue
            artifacts[artifact["artifactId"]] = artifact
            observations[observation["observationId"]] = observation

        artifact_ids = sorted(artifacts)
        observation_ids = sorted(observations)
        if (
            artifact_ids != expected_artifact_ids
            or observation_ids != expected_observation_ids
        ):
            raise GearReleaseIntegrityError(
                "Gear Release Store evidence universe does not match staging compilation"
            )
        for artifact_id, artifact in artifacts.items():
            expected_artifact = expected_artifacts[artifact_id]
            if any(
                _canonical(artifact.get(field))
                != _canonical(expected_artifact.get(field))
                for field in (
                    "schemaRevision",
                    "artifactId",
                    "sourceType",
                    "sourceIdentity",
                    "sourceRevision",
                    "seasonRevision",
                    "payloadHash",
                    "payload",
                )
            ):
                raise GearReleaseIntegrityError(
                    "Gear Release Store Artifact does not match staging compilation"
                )
        for observation_id, observation in observations.items():
            if (
                _canonical(observation)
                != _canonical(expected_observations[observation_id])
            ):
                raise GearReleaseIntegrityError(
                    "Gear Release Store Observation does not match staging compilation"
                )
        compilation = gate_result["evidenceCompilation"]
        persistence = gate_result["evidencePersistence"]
        for owner, identities in (
            ("artifacts", artifact_ids),
            ("observations", observation_ids),
        ):
            if (
                _canonical(compilation[owner].get("identities"))
                != _canonical(identities)
                or _canonical(persistence[owner].get("identities"))
                != _canonical(identities)
                or _int(compilation[owner].get("count"))
                != len(identities)
                or _int(persistence[owner].get("persisted"))
                != len(identities)
            ):
                raise GearReleaseIntegrityError(
                    "Gear Release receipt omits complete Store evidence universe"
                )

        replayed_facts = gear_fact_compiler.compile_facts_by_subject(
            season_revision=season_revision,
            observations=list(observations.values()),
            artifacts=list(artifacts.values()),
            fact_types_by_subject=required_fact_types,
        )
        projected_by_semantic = {
            (
                _text(fact.get("subjectKey")),
                _text(fact.get("factType")),
            ): fact
            for fact in projected_facts.values()
        }
        replayed_by_semantic = {
            (
                _text(fact.get("subjectKey")),
                _text(fact.get("factType")),
            ): fact
            for fact in replayed_facts
        }
        if set(replayed_by_semantic) != set(projected_by_semantic):
            raise GearReleaseIntegrityError(
                "Gear Release Fact replay does not cover the complete Store evidence universe"
            )
        for semantic, projected in projected_by_semantic.items():
            replayed = replayed_by_semantic[semantic]
            if any(
                _canonical(replayed.get(field))
                != _canonical(projected.get(field))
                for field in (
                    "factKey",
                    "subjectKey",
                    "factType",
                    "value",
                    "status",
                    "factValueHash",
                    "provenanceHash",
                    "compilerRuleRevision",
                )
            ) or sorted(
                replayed.get("observationRefs") or ()
            ) != sorted(
                projected.get("persistedObservationRefs")
                or projected.get("observationRefs")
                or ()
            ):
                raise GearReleaseIntegrityError(
                    "Gear Release Fact is not reproduced by complete Store evidence"
                )

        expected_gaps: dict[str, dict[str, Any]] = {}
        for gap in gear_fact_compiler.evidence_gaps_from_facts(
            replayed_facts
        ):
            identity = {
                "factKey": _text(gap.get("factKey")),
                "problemCode": _text(gap.get("problemCode")),
                "missingRequirement": _canonical(
                    gap.get("missingRequirement") or {}
                ),
            }
            gap_key = "gear-gap:" + _hash(identity)
            expected_gaps[gap_key] = {
                "gapKey": gap_key,
                **identity,
            }
        replayed_fact_keys = sorted({
            _text(fact.get("factKey"))
            for fact in replayed_facts
        })
        if replayed_fact_keys:
            cur.execute(
                """
                /* gear_release_active_gap_universe */
                SELECT
                    gap_key, fact_key, problem_code,
                    missing_requirement_json, status
                FROM ops.websim_gear_evidence_gaps
                WHERE fact_key = ANY(%s::text[])
                  AND status <> 'terminal'
                """,
                (replayed_fact_keys,),
            )
            persisted_gaps = {
                _text(row[0]): {
                    "gapKey": _text(row[0]),
                    "factKey": _text(row[1]),
                    "problemCode": _text(row[2]),
                    "missingRequirement": _canonical(row[3]),
                }
                for row in cur.fetchall()
                if isinstance(row, (list, tuple)) and len(row) == 5
            }
        else:
            persisted_gaps = {}
        if _canonical(persisted_gaps) != _canonical(expected_gaps):
            raise GearReleaseIntegrityError(
                "Gear Release Gap semantics do not match replayed unresolved Facts"
            )
        gap_ids = sorted(expected_gaps)
        if (
            _canonical(compilation["gaps"].get("identities"))
            != _canonical(gap_ids)
            or _canonical(persistence["gaps"].get("identities"))
            != _canonical(gap_ids)
        ):
            raise GearReleaseIntegrityError(
                "Gear Release Gap receipt omits replayed Gap semantics"
            )

    @staticmethod
    def _verify_complete_evidence_universe_streaming(
        cur,
        *,
        projected_facts: dict[tuple[str, str, str], dict[str, Any]],
        gate_result: dict[str, Any],
        season_revision: str,
        release_source_revision: str,
        raw_staging_snapshot: dict[str, Any],
        trusted_socket_evidence: dict[str, Any],
        normalized_bonus_minimums: Mapping[str, Any],
    ) -> None:
        """Replay v2 receipts a bounded category batch at a time.

        The database remains the authority: a compact gate receipt only tells
        us which deterministic stream to replay.  Each batch therefore reads
        and self-authenticates its immutable Artifact/Observation rows before
        compiling Facts and validating the matching Gap semantics.
        """

        try:
            from . import gear_fact_compiler
            from . import gear_release_tool
            from .gear_evidence_registry import (
                build_evidence_artifact,
                build_evidence_observation,
            )
        except ImportError:
            import gear_fact_compiler
            import gear_release_tool
            from gear_evidence_registry import (
                build_evidence_artifact,
                build_evidence_observation,
            )

        compilation = gate_result["evidenceCompilation"]
        persistence = gate_result["evidencePersistence"]
        stream = (
            gate_result.get("evidenceStream")
            if isinstance(gate_result.get("evidenceStream"), Mapping)
            else {}
        )
        batch_size = _int(stream.get("batchSize"))
        if (
            stream.get("schemaRevision") != "gear-evidence-stream-v1"
            or stream.get("rowOrderRevision") != "staging-category-v1"
            or batch_size <= 0
            or batch_size
            > gear_release_tool._MAX_STREAMING_RELEASE_EVIDENCE_BATCH_SIZE
        ):
            raise GearReleaseIntegrityError(
                "Gear Release streaming evidence schedule is invalid"
            )
        receipt = gear_release_tool._StreamingEvidenceReceipt()
        option_facts_by_subject_fact: dict[
            tuple[str, str], Mapping[str, Any]
        ] = {}
        replayed_fact_count = 0

        for category, _offset, _rows, expected in (
            gear_release_tool._stream_release_evidence_batches(
                raw_staging_snapshot,
                season_revision=season_revision,
                source_revision=_text(release_source_revision),
                captured_at="1970-01-01T00:00:00+00:00",
                socket_bonus_minimums=normalized_bonus_minimums,
                socket_bonus_evidence=trusted_socket_evidence,
                batch_size=batch_size,
            )
        ):
            expected_artifacts = {
                _text(row.get("artifactId")): row
                for row in expected["artifacts"]
            }
            expected_observations = {
                _text(row.get("observationId")): row
                for row in expected["observations"]
            }
            observation_ids = sorted(expected_observations)
            if observation_ids:
                cur.execute(
                    """
                    /* gear_release_complete_evidence_stream_batch */
                    SELECT
                        observation.observation_id,
                        observation.artifact_id,
                        observation.schema_revision,
                        observation.subject_key,
                        observation.fact_type,
                        observation.observed_value_json,
                        observation.parser_revision,
                        observation.source_scope,
                        observation.status,
                        artifact.artifact_id,
                        artifact.schema_revision,
                        artifact.source_type,
                        artifact.source_identity,
                        artifact.source_revision,
                        artifact.season_revision,
                        artifact.captured_at::text,
                        artifact.payload_hash,
                        artifact.payload_json
                    FROM cache.websim_gear_evidence_observations observation
                    JOIN cache.websim_gear_evidence_artifacts artifact
                      ON artifact.artifact_id = observation.artifact_id
                    WHERE observation.observation_id = ANY(%s::text[])
                      AND artifact.season_revision = %s
                      AND observation.status = 'accepted'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM cache.websim_gear_evidence_invalidations invalidation
                          WHERE invalidation.artifact_id = artifact.artifact_id
                             OR invalidation.observation_id = observation.observation_id
                      )
                    """,
                    (observation_ids, _text(season_revision)),
                )
                evidence_rows = cur.fetchall()
            else:
                evidence_rows = []

            artifacts: dict[str, dict[str, Any]] = {}
            observations: dict[str, dict[str, Any]] = {}
            for row in evidence_rows:
                if not isinstance(row, (list, tuple)) or len(row) != 18:
                    continue
                observation = {
                    "observationId": _text(row[0]),
                    "artifactId": _text(row[1]),
                    "schemaRevision": _text(row[2]),
                    "subjectKey": _text(row[3]),
                    "factType": _text(row[4]),
                    "observedValue": _canonical(row[5]),
                    "parserRevision": _text(row[6]),
                    "sourceScope": _text(row[7]),
                    "status": _text(row[8]),
                }
                artifact = {
                    "artifactId": _text(row[9]),
                    "schemaRevision": _text(row[10]),
                    "sourceType": _text(row[11]),
                    "sourceIdentity": _text(row[12]),
                    "sourceRevision": _text(row[13]),
                    "seasonRevision": _text(row[14]),
                    "capturedAt": _text(row[15]),
                    "payloadHash": _text(row[16]),
                    "payload": _canonical(row[17]),
                }
                try:
                    rebuilt_artifact = build_evidence_artifact(
                        source_type=artifact["sourceType"],
                        source_identity=artifact["sourceIdentity"],
                        source_revision=artifact["sourceRevision"],
                        season_revision=artifact["seasonRevision"],
                        captured_at=artifact["capturedAt"],
                        payload=artifact["payload"],
                    )
                    rebuilt_observation = build_evidence_observation(
                        artifact_id=observation["artifactId"],
                        subject_key=observation["subjectKey"],
                        fact_type=observation["factType"],
                        observed_value=observation["observedValue"],
                        parser_revision=observation["parserRevision"],
                        source_scope=observation["sourceScope"],
                        status=observation["status"],
                    )
                except ValueError as error:
                    raise GearReleaseIntegrityError(
                        "Gear Release Store evidence universe is not canonical"
                    ) from error
                if (
                    _canonical(rebuilt_artifact) != _canonical(artifact)
                    or _canonical(rebuilt_observation) != _canonical(observation)
                ):
                    raise GearReleaseIntegrityError(
                        "Gear Release Store evidence universe is not self-authenticating"
                    )
                artifacts[artifact["artifactId"]] = artifact
                observations[observation["observationId"]] = observation

            if (
                set(artifacts) != set(expected_artifacts)
                or set(observations) != set(expected_observations)
            ):
                raise GearReleaseIntegrityError(
                    "Gear Release Store evidence universe does not match staging compilation"
                )
            for artifact_id, artifact in artifacts.items():
                expected_artifact = expected_artifacts[artifact_id]
                if any(
                    _canonical(artifact.get(field))
                    != _canonical(expected_artifact.get(field))
                    for field in (
                        "schemaRevision",
                        "artifactId",
                        "sourceType",
                        "sourceIdentity",
                        "sourceRevision",
                        "seasonRevision",
                        "payloadHash",
                        "payload",
                    )
                ):
                    raise GearReleaseIntegrityError(
                        "Gear Release Store Artifact does not match staging compilation"
                    )
            for observation_id, observation in observations.items():
                if _canonical(observation) != _canonical(
                    expected_observations[observation_id]
                ):
                    raise GearReleaseIntegrityError(
                        "Gear Release Store Observation does not match staging compilation"
                    )

            replayed_facts = gear_fact_compiler.compile_facts_by_subject(
                season_revision=season_revision,
                observations=[
                    observations[key]
                    for key in sorted(observations)
                ],
                artifacts=[
                    artifacts[key]
                    for key in sorted(artifacts)
                ],
                fact_types_by_subject=expected["expectedFactTypesBySubject"],
                precompiled_facts_by_subject_fact=(
                    option_facts_by_subject_fact
                ),
            )
            if len(replayed_facts) != len(expected["facts"]):
                raise GearReleaseIntegrityError(
                    "Gear Release Fact replay does not cover the complete Store evidence universe"
                )
            for fact in replayed_facts:
                identity = (
                    _text(fact.get("factKey")),
                    _text(fact.get("factValueHash")),
                    _text(fact.get("provenanceHash")),
                )
                projected = projected_facts.get(identity)
                if projected is None or any(
                    _canonical(fact.get(field))
                    != _canonical(projected.get(field))
                    for field in (
                        "factKey",
                        "subjectKey",
                        "factType",
                        "value",
                        "status",
                        "factValueHash",
                        "provenanceHash",
                        "compilerRuleRevision",
                    )
                ) or sorted(fact.get("observationRefs") or ()) != sorted(
                    projected.get("persistedObservationRefs")
                    or projected.get("observationRefs")
                    or ()
                ):
                    raise GearReleaseIntegrityError(
                        "Gear Release Fact is not reproduced by complete Store evidence"
                    )

            expected_gaps: dict[str, dict[str, Any]] = {}
            for gap in gear_fact_compiler.evidence_gaps_from_facts(replayed_facts):
                identity = {
                    "factKey": _text(gap.get("factKey")),
                    "problemCode": _text(gap.get("problemCode")),
                    "missingRequirement": _canonical(
                        gap.get("missingRequirement") or {}
                    ),
                }
                gap_key = "gear-gap:" + _hash(identity)
                expected_gaps[gap_key] = {"gapKey": gap_key, **identity}
            if expected_gaps:
                cur.execute(
                    """
                    /* gear_release_active_gap_stream_batch */
                    SELECT
                        gap_key, fact_key, problem_code,
                        missing_requirement_json, status
                    FROM ops.websim_gear_evidence_gaps
                    WHERE gap_key = ANY(%s::text[])
                      AND status <> 'terminal'
                    """,
                    (sorted(expected_gaps),),
                )
                persisted_gaps = {
                    _text(row[0]): {
                        "gapKey": _text(row[0]),
                        "factKey": _text(row[1]),
                        "problemCode": _text(row[2]),
                        "missingRequirement": _canonical(row[3]),
                    }
                    for row in cur.fetchall()
                    if isinstance(row, (list, tuple)) and len(row) == 5
                }
            else:
                persisted_gaps = {}
            if _canonical(persisted_gaps) != _canonical(expected_gaps):
                raise GearReleaseIntegrityError(
                    "Gear Release Gap semantics do not match replayed unresolved Facts"
                )

            for owner, rows in (
                ("artifacts", expected["artifacts"]),
                ("observations", expected["observations"]),
                ("facts", replayed_facts),
                (
                    "gaps",
                    [
                        expected_gaps[gap_key]
                        for gap_key in sorted(expected_gaps)
                    ],
                ),
            ):
                receipt.record(owner, rows)
            replayed_fact_count += len(replayed_facts)
            if category == "options":
                for fact in replayed_facts:
                    if _text(fact.get("factType")) != "enhancement_option":
                        continue
                    identity = (
                        _text(fact.get("subjectKey")),
                        "enhancement_option",
                    )
                    existing = option_facts_by_subject_fact.setdefault(
                        identity,
                        fact,
                    )
                    if _canonical(existing) != _canonical(fact):
                        raise GearReleaseIntegrityError(
                            "Gear Release Option Fact replay conflicts"
                        )

        if replayed_fact_count != len(projected_facts):
            raise GearReleaseIntegrityError(
                "Gear Release Fact replay does not cover the complete Store evidence universe"
            )
        expected_receipt = receipt.compilation()
        for owner in ("artifacts", "observations", "facts", "gaps"):
            compiled_owner = compilation.get(owner) or {}
            persisted_owner = persistence.get(owner) or {}
            expected_owner = expected_receipt[owner]
            persisted_count = (
                _int(persisted_owner.get("requested"))
                if owner == "gaps"
                else _int(persisted_owner.get("persisted"))
            )
            if (
                _int(compiled_owner.get("count"))
                != expected_owner["count"]
                or persisted_count != expected_owner["count"]
                or compiled_owner.get("sequenceDigest")
                != expected_owner["sequenceDigest"]
                or persisted_owner.get("sequenceDigest")
                != expected_owner["sequenceDigest"]
            ):
                raise GearReleaseIntegrityError(
                    "Gear Release streaming receipt omits complete Store evidence universe"
                )

    @staticmethod
    def _verify_projected_canonical_facts(
        cur,
        release: dict[str, Any],
        snapshot: dict[str, Any],
    ) -> dict[tuple[str, str, str], dict[str, Any]]:
        try:
            from .gear_evidence_registry import (
                canonical_fact_key,
                fact_value_hash,
            )
        except ImportError:
            from gear_evidence_registry import (
                canonical_fact_key,
                fact_value_hash,
            )

        source = release.get("source") if isinstance(release.get("source"), dict) else {}
        evidence = (
            source.get("sourceEvidence")
            if isinstance(source.get("sourceEvidence"), dict)
            else {}
        )
        declared_digest = _text(evidence.get("canonicalFactDigest"))
        references: dict[tuple[str, str, str], dict[str, Any]] = {}
        for category in ("items", "variants", "options"):
            for row in snapshot.get(category) or ():
                if not isinstance(row, dict):
                    continue
                payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
                for fact in payload.get("canonicalFacts") or ():
                    if not isinstance(fact, dict):
                        continue
                    identity = (
                        _text(fact.get("factKey")),
                        _text(fact.get("factValueHash")),
                        _text(fact.get("provenanceHash")),
                    )
                    if not all(identity):
                        raise GearReleaseIntegrityError(
                            "projected canonical Fact reference is incomplete"
                        )
                    projected = {
                        "schemaRevision": _text(fact.get("schemaRevision")),
                        "factKey": identity[0],
                        "subjectKey": _text(fact.get("subjectKey")),
                        "factType": _text(fact.get("factType")),
                        "value": _canonical(fact.get("value")),
                        "status": _text(fact.get("status")),
                        "observationRefs": sorted(
                            _text(reference)
                            for reference in fact.get("observationRefs") or ()
                            if _text(reference)
                        ),
                        "observationRefCount": _int(
                            fact.get("observationRefCount")
                        ),
                        "referencesTruncated": (
                            fact.get("referencesTruncated") is True
                        ),
                        "compilerRuleRevision": _text(
                            fact.get("compilerRuleRevision")
                        ),
                        "factValueHash": identity[1],
                        "provenanceHash": identity[2],
                    }
                    try:
                        expected_key = canonical_fact_key(
                            release.get("seasonRevision"),
                            projected["subjectKey"],
                            projected["factType"],
                        )
                        expected_value_hash = fact_value_hash(
                            projected["subjectKey"],
                            projected["factType"],
                            projected["value"],
                            projected["status"],
                        )
                    except ValueError as error:
                        raise GearReleaseIntegrityError(
                            "projected canonical Fact value is invalid"
                        ) from error
                    if (
                        projected["factKey"] != expected_key
                        or projected["factValueHash"] != expected_value_hash
                    ):
                        raise GearReleaseIntegrityError(
                            "projected canonical Fact hashes do not match its value"
                        )
                    existing = references.get(identity)
                    if existing is not None and existing != projected:
                        raise GearReleaseIntegrityError(
                            "projected canonical Fact tuple has conflicting values"
                        )
                    references[identity] = projected
        if not references:
            if declared_digest:
                raise GearReleaseIntegrityError(
                    "canonical Fact digest requires projected Fact references"
                )
            return {}
        if not declared_digest:
            raise GearReleaseIntegrityError(
                "projected canonical Facts require a canonical Fact digest"
            )
        digest_rows = sorted(
            [
                {
                    "factKey": fact["factKey"],
                    "status": fact["status"],
                    "factValueHash": fact["factValueHash"],
                    "provenanceHash": fact["provenanceHash"],
                }
                for fact in references.values()
            ],
            key=lambda fact: (
                fact["factKey"],
                fact["factValueHash"],
                fact["provenanceHash"],
            ),
        )
        if _hash(digest_rows) != declared_digest:
            raise GearReleaseIntegrityError(
                "projected canonical Fact digest does not match release source evidence"
            )
        identities = sorted(references)
        cur.execute(
            """
            WITH requested(fact_key, fact_value_hash, provenance_hash) AS (
                SELECT * FROM unnest(%s::text[], %s::text[], %s::text[])
            )
            SELECT
                fact.fact_key,
                fact.schema_revision,
                fact.subject_key,
                fact.fact_type,
                fact.value_json,
                fact.status,
                fact.observation_refs_json,
                fact.fact_value_hash,
                fact.provenance_hash,
                fact.compiler_rule_revision
            FROM requested
            JOIN cache.websim_gear_canonical_facts fact
              ON fact.fact_key = requested.fact_key
             AND fact.fact_value_hash = requested.fact_value_hash
             AND fact.provenance_hash = requested.provenance_hash
            """,
            (
                [identity[0] for identity in identities],
                [identity[1] for identity in identities],
                [identity[2] for identity in identities],
            ),
        )
        persisted_rows = cur.fetchall()
        persisted = {
            (_text(row[0]), _text(row[7]), _text(row[8])): row
            for row in persisted_rows
            if isinstance(row, (list, tuple)) and len(row) == 10
        }
        if set(persisted) != set(references):
            raise GearReleaseIntegrityError(
                "projected canonical Fact references are not persisted"
            )
        for identity, projected in references.items():
            row = persisted[identity]
            persisted_refs = sorted(
                _text(reference)
                for reference in (row[6] if isinstance(row[6], list) else [])
                if _text(reference)
            )
            if (
                projected["schemaRevision"] != _text(row[1])
                or projected["subjectKey"] != _text(row[2])
                or projected["factType"] != _text(row[3])
                or projected["value"] != _canonical(row[4])
                or projected["status"] != _text(row[5])
                or projected["observationRefs"] != persisted_refs[:8]
                or projected["observationRefCount"] != len(persisted_refs)
                or projected["referencesTruncated"] != (len(persisted_refs) > 8)
                or projected["compilerRuleRevision"] != _text(row[9])
            ):
                raise GearReleaseIntegrityError(
                    "projected canonical Fact does not match persisted Fact"
                )
            projected["persistedObservationRefs"] = persisted_refs
        return references

    def seal_gear_release(
        self,
        release: dict[str, Any],
        snapshot: dict[str, Any],
        *,
        event: dict[str, Any] | None = None,
        gate_result: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        expected = _exact_release_descriptor(release)
        with self.connection() as conn:
            with conn.cursor() as cur:
                if expected["releaseKind"] != "gear":
                    raise GearReleaseIntegrityError("seal_gear_release requires a Gear Release")
                if gear_snapshot_summary(snapshot) != expected["content"]:
                    raise GearReleaseIntegrityError("gear snapshot does not match the release descriptor")
                trusted_socket_evidence = (
                    self._trusted_socket_probe_evidence(expected)
                )
                (
                    raw_staging_snapshot,
                    legacy_snapshot,
                ) = self._legacy_shadow_snapshot(
                    expected,
                    trusted_socket_evidence,
                )
                (
                    projected_facts,
                    required_fact_types,
                ) = self._validate_canonical_gear_gate(
                    expected,
                    snapshot,
                    gate_result or {},
                    legacy_snapshot,
                )
                persisted_facts = self._verify_projected_canonical_facts(
                    cur,
                    expected,
                    snapshot,
                )
                if set(projected_facts) != set(persisted_facts):
                    raise GearReleaseIntegrityError(
                        "Gear Release canonical gate Fact identities diverge"
                    )
                self._verify_complete_evidence_universe(
                    cur,
                    projected_facts=persisted_facts,
                    required_fact_types=required_fact_types,
                    gate_result=gate_result or {},
                    season_revision=expected["seasonRevision"],
                    release_source_revision=_text(
                        expected["source"].get("sourceRevision")
                    ),
                    raw_staging_snapshot=raw_staging_snapshot,
                    trusted_socket_evidence=trusted_socket_evidence,
                )
                if self._existing_or_insert(cur, expected, gate_result or {}):
                    return {"status": "reused", "releaseId": expected["releaseId"]}
                self._insert_gear_rows(cur, expected["releaseId"], snapshot)
                self._insert_event(
                    cur,
                    release_id=expected["releaseId"],
                    event_type="release_sealed",
                    event=event or {},
                )
        return {"status": "inserted", "releaseId": expected["releaseId"]}

    @staticmethod
    def _insert_gear_rows(cur, release_id: str, snapshot: dict[str, Any]) -> None:
        items = _canonical_rows(snapshot.get("items"))
        sources = _canonical_rows(snapshot.get("sources"))
        variants = _canonical_rows(snapshot.get("variants"))
        options = _canonical_rows(snapshot.get("options"))
        if items:
            cur.executemany(
                """
                INSERT INTO cache.websim_gear_release_items (
                    release_id, item_id, name, slot, item_level, source_status,
                    payload_json, source_updated_at, row_hash
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                [
                    (
                        release_id, row.get("itemId"), row.get("name") or "", row.get("slot") or "",
                        row.get("itemLevel"), row.get("sourceStatus") or "unknown",
                        _json_param(row.get("payload") or {}), row.get("updatedAt") or None,
                        canonical_row_hash(row),
                    )
                    for row in items
                ],
            )
        if sources:
            cur.executemany(
                """
                INSERT INTO cache.websim_gear_release_sources (
                    release_id, source_id, item_id, source_type, source_key, source_label,
                    instance_id, encounter_id, difficulty_key, season_revision,
                    payload_json, source_updated_at, row_hash
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                [
                    (
                        release_id, row.get("sourceId"), row.get("itemId"), row.get("sourceType"),
                        row.get("sourceKey") or "", row.get("sourceLabel") or "",
                        row.get("instanceId") or "", row.get("encounterId") or "",
                        row.get("difficultyKey") or "", row.get("seasonRevision") or "",
                        _json_param(row.get("payload") or {}), row.get("updatedAt") or None,
                        canonical_row_hash(row),
                    )
                    for row in sources
                ],
            )
        if variants:
            cur.executemany(
                """
                INSERT INTO cache.websim_gear_release_variants (
                    release_id, variant_id, item_id, variant_key, slot, label, source_type,
                    difficulty_key, item_level, simc_options_json, status, blockers_json,
                    payload_json, source_updated_at, row_hash
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s::jsonb, %s, %s)
                """,
                [
                    (
                        release_id, row.get("variantId"), row.get("itemId"), row.get("variantKey"),
                        row.get("slot") or "", row.get("label") or "", row.get("sourceType") or "",
                        row.get("difficultyKey") or "", _int(row.get("itemLevel")),
                        _json_param(row.get("simcOptions") or {}), row.get("status") or "blocked",
                        _json_param(row.get("blockers") or []), _json_param(row.get("payload") or {}),
                        row.get("updatedAt") or None, canonical_row_hash(row),
                    )
                    for row in variants
                ],
            )
        if options:
            cur.executemany(
                """
                INSERT INTO cache.websim_gear_release_mod_options (
                    release_id, option_id, variant_id, option_key, option_type, name,
                    applicable_slots_json, simc_options_json, status, is_visible,
                    payload_json, source_updated_at, row_hash
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb, %s, %s)
                """,
                [
                    (
                        release_id, row.get("optionId"), row.get("variantId") or None,
                        row.get("optionKey"), row.get("optionType") or "", row.get("name") or "",
                        _json_param(row.get("applicableSlots") or []),
                        _json_param(row.get("simcOptions") or {}), row.get("status") or "blocked",
                        row.get("isVisible") is True, _json_param(row.get("payload") or {}),
                        row.get("updatedAt") or None, canonical_row_hash(row),
                    )
                    for row in options
                ],
            )

    def seal_community_release(
        self,
        release: dict[str, Any],
        rows: Iterable[dict[str, Any]],
        *,
        event: dict[str, Any] | None = None,
        gate_result: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        expected = _exact_release_descriptor(release)
        canonical_rows = _canonical_rows(rows)
        with self.connection() as conn:
            with conn.cursor() as cur:
                if expected["releaseKind"] != "community":
                    raise GearReleaseIntegrityError("seal_community_release requires a Community Release")
                summary = community_rows_summary(canonical_rows)
                if summary != expected["content"]:
                    raise GearReleaseIntegrityError("community rows do not match the release descriptor")
                if expected.get("schemaRevision") == "community-release-v2":
                    hero_slots = summary.get("winnerHeroSlots") if isinstance(summary, dict) else []
                    winner_count = _int((summary.get("counts") or {}).get("winner")) if isinstance(summary, dict) else 0
                    if (
                        summary.get("schemaRevision") != "community-release-content-v2"
                        or not isinstance(hero_slots, list)
                        or len(hero_slots) != winner_count
                        or len({
                            (_text(slot.get("classKey")), _text(slot.get("specKey")), _text(slot.get("heroKey")))
                            for slot in hero_slots if isinstance(slot, dict)
                        }) != winner_count
                    ):
                        raise GearReleaseIntegrityError("v2 Community Release requires distinct projected hero winners")
                if self._existing_or_insert(cur, expected, gate_result or {}):
                    return {"status": "reused", "releaseId": expected["releaseId"]}
                if canonical_rows:
                    cur.executemany(
                        """
                        INSERT INTO cache.websim_community_release_templates (
                            release_id, template_id, class_key, spec_key, role, election_rank,
                            source_key, source_url, source_status, sample_count, profile_hash, gear_hash,
                            selection_intent_json, resolved_gear_signature, semantic_gear_signature,
                            dependency_vector_json, evidence_json, problems_json, payload_json,
                            source_updated_at, expires_at, row_hash
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s)
                        """,
                        [self._community_row_values(expected["releaseId"], row) for row in canonical_rows],
                    )
                self._insert_event(
                    cur,
                    release_id=expected["releaseId"],
                    event_type="release_sealed",
                    event=event or {},
                )
        return {"status": "inserted", "releaseId": expected["releaseId"]}

    @staticmethod
    def _community_row_values(release_id: str, row: dict[str, Any]) -> tuple[Any, ...]:
        return (
            release_id,
            row.get("templateId"),
            row.get("classKey"),
            row.get("specKey"),
            row.get("role"),
            _int(row.get("electionRank")),
            row.get("sourceKey") or "",
            row.get("sourceUrl") or "",
            row.get("sourceStatus") or "",
            _int(row.get("sampleCount")),
            row.get("profileHash") or "",
            row.get("gearHash") or "",
            _json_param(row.get("selectionIntent") or {}),
            row.get("resolvedGearSignature") or "",
            row.get("semanticGearSignature") or "",
            _json_param(row.get("dependencyVector") or {}),
            _json_param(row.get("evidence") or {}),
            _json_param(row.get("problems") or []),
            _json_param(row.get("payload") or {}),
            row.get("updatedAt") or None,
            row.get("expiresAt") or None,
            canonical_row_hash(row),
        )

    @staticmethod
    def _validated_manifest_revision(manifest: dict[str, Any]) -> str:
        if not isinstance(manifest, dict) or not _text(manifest.get("manifestRevision")):
            raise GearReleaseIntegrityError("manifest must contain manifestRevision")
        revision = _text(manifest["manifestRevision"])
        if revision != _expected_manifest_revision(manifest):
            raise GearReleaseIntegrityError("manifest identity does not match manifestRevision")
        return revision

    def _seal_manifest_with_cursor(self, cur, manifest: dict[str, Any]) -> dict[str, str]:
        revision = self._validated_manifest_revision(manifest)
        cur.execute(
            """
            SELECT payload_json
            FROM cache.websim_season_manifests
            WHERE manifest_revision = %s
            """,
            (revision,),
        )
        row = cur.fetchone()
        if row:
            if _canonical(row[0] if isinstance(row[0], dict) else {}) != _canonical(manifest):
                raise GearReleaseIntegrityError("existing manifest revision has different content")
            return {"status": "reused", "manifestRevision": revision}
        cur.execute(
            """
            INSERT INTO cache.websim_season_manifests (
                manifest_revision, schema_revision, season_revision, gear_release_id,
                community_release_id, talent_catalog_revision, dependency_vector_json,
                rollback_manifest_revision, manifest_hash, payload_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb)
            """,
            (
                revision,
                manifest.get("schemaRevision"),
                manifest.get("seasonRevision"),
                manifest.get("gearCatalogReleaseId"),
                manifest.get("communityTemplateReleaseId") or None,
                manifest.get("talentCatalogRevision"),
                _json_param(manifest.get("dependencyRevisions") or {}),
                manifest.get("rollbackManifestRevision") or None,
                _hash({key: value for key, value in manifest.items() if key != "manifestRevision"}),
                _json_param(manifest),
            ),
        )
        self._insert_event(
            cur,
            manifest_revision=revision,
            event_type="manifest_sealed",
            event={"formalActiveManifest": bool(manifest.get("formalActiveManifest"))},
        )
        return {"status": "inserted", "manifestRevision": revision}

    def seal_manifest(self, manifest: dict[str, Any]) -> dict[str, str]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                return self._seal_manifest_with_cursor(cur, manifest)

    def get_active_pointer(self) -> dict[str, Any]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT environment, pointer_mode, manifest_revision, generation, rollback_manifest_revision,
                           updated_at, updated_by
                    FROM cache.websim_active_manifest_pointer
                    WHERE environment = 'retail'
                    """
                )
                row = cur.fetchone()
        if not row:
            return {}
        return {
            "environment": _text(row[0]),
            "pointerMode": _text(row[1]),
            "manifestRevision": _text(row[2]),
            "generation": _int(row[3]),
            "rollbackManifestRevision": _text(row[4]),
            "updatedAt": _text(row[5]),
            "updatedBy": _text(row[6]),
        }

    def load_active_manifest_binding(self) -> dict[str, Any]:
        """Bind one retail pointer/Manifest/release identity in a read-only snapshot."""

        try:
            from . import gear_release
        except ImportError:
            import gear_release

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cur.execute(
                    """
                    SELECT pointer.environment, pointer.pointer_mode, pointer.manifest_revision,
                           pointer.generation, pointer.rollback_manifest_revision,
                           pointer.updated_at, pointer.updated_by, manifest.payload_json
                    FROM cache.websim_active_manifest_pointer pointer
                    LEFT JOIN cache.websim_season_manifests manifest
                      ON manifest.manifest_revision = pointer.manifest_revision
                    WHERE pointer.environment = 'retail'
                    """
                )
                row = cur.fetchone()
                if not row:
                    return {
                        "pointerMode": "pre_cutover",
                        "generation": 0,
                        "manifestRevision": "",
                        "rollbackManifestRevision": "",
                        "formalActiveManifest": False,
                    }
                values = list(row)
                while len(values) < 8:
                    values.append(None)
                pointer_mode = _text(values[1])
                manifest_revision = _text(values[2])
                generation = _int(values[3])
                rollback_revision = _text(values[4])
                common = {
                    "pointerMode": pointer_mode,
                    "generation": generation,
                    "manifestRevision": manifest_revision,
                    "rollbackManifestRevision": rollback_revision,
                    "updatedAt": _text(values[5]),
                    "updatedBy": _text(values[6]),
                }
                if pointer_mode == "transitional":
                    if manifest_revision or values[7] is not None:
                        raise GearReleaseIntegrityError("transitional pointer unexpectedly binds a Manifest")
                    return {**common, "formalActiveManifest": False}
                if pointer_mode != "active" or not manifest_revision:
                    raise GearReleaseIntegrityError("active Manifest pointer state is invalid")
                manifest = values[7] if isinstance(values[7], dict) else None
                if not isinstance(manifest, dict) or _text(manifest.get("manifestRevision")) != manifest_revision:
                    raise GearReleaseIntegrityError("active Manifest is missing or does not match the pointer")
                gear_id = _text(manifest.get("gearCatalogReleaseId"))
                community_id = _text(manifest.get("communityTemplateReleaseId"))
                releases = {}
                gear = self._select_release(cur, gear_id)
                if gear is not None:
                    releases[gear_id] = _exact_release_descriptor(gear)
                community = None
                if community_id:
                    community = self._select_release(cur, community_id)
                    if community is not None:
                        releases[community_id] = _exact_release_descriptor(community)
                issues = gear_release.validate_manifest(manifest, releases)
                if issues:
                    raise GearReleaseIntegrityError(
                        "active Manifest binding integrity failed: "
                        + ", ".join(_text(issue.get("code")) for issue in issues)
                    )
                return {
                    **common,
                    "formalActiveManifest": True,
                    "manifest": _canonical(manifest),
                    "gearRelease": releases[gear_id],
                    "communityRelease": releases.get(community_id) if community_id else None,
                }

    @staticmethod
    def _validated_pointer_command(command: dict[str, Any], updated_by: str) -> tuple[str, str, str, int, str]:
        required_fields = {
            "schemaRevision",
            "action",
            "environment",
            "targetMode",
            "manifestRevision",
            "expectedGeneration",
            "rollbackManifestRevision",
        }
        if not isinstance(command, dict) or set(command) != required_fields:
            raise ValueError("invalid pointer command")
        if command.get("schemaRevision") != "active-manifest-pointer-command-v2":
            raise ValueError("invalid pointer command schema")
        if command.get("action") not in {"promote", "rollback"}:
            raise ValueError("invalid pointer command action")
        if command.get("environment") != "retail":
            raise ValueError("invalid pointer command environment")
        target_mode = _text(command.get("targetMode"))
        manifest_revision = _text(command.get("manifestRevision"))
        rollback_manifest_revision = _text(command.get("rollbackManifestRevision"))
        if target_mode not in {"active", "transitional"}:
            raise ValueError("invalid pointer targetMode")
        if target_mode == "active" and not manifest_revision:
            raise ValueError("active pointer command requires manifestRevision")
        if target_mode == "transitional":
            if command.get("action") != "rollback" or manifest_revision or rollback_manifest_revision:
                raise ValueError("invalid transitional pointer command")
        expected_generation = command.get("expectedGeneration")
        if isinstance(expected_generation, bool) or not isinstance(expected_generation, int) or expected_generation < 0:
            raise ValueError("expectedGeneration must be a non-negative integer")
        if not _text(updated_by):
            raise ValueError("updated_by is required")
        return (
            _text(command.get("action")),
            target_mode,
            manifest_revision,
            expected_generation,
            rollback_manifest_revision,
        )

    def _compare_and_swap_pointer_with_cursor(self, cur, command: dict[str, Any], *, updated_by: str) -> dict[str, Any]:
        action, target_mode, manifest_revision, expected_generation, rollback_manifest_revision = (
            self._validated_pointer_command(command, updated_by)
        )
        target_generation = expected_generation + 1
        if expected_generation == 0:
            cur.execute(
                """
                INSERT INTO cache.websim_active_manifest_pointer (
                    environment, pointer_mode, manifest_revision, generation, rollback_manifest_revision,
                    updated_by
                )
                SELECT 'retail', %s, %s, %s, %s, %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM cache.websim_active_manifest_pointer WHERE environment = 'retail'
                )
                ON CONFLICT (environment) DO NOTHING
                """,
                (
                    target_mode,
                    manifest_revision or None,
                    target_generation,
                    rollback_manifest_revision or None,
                    _text(updated_by),
                ),
            )
        else:
            cur.execute(
                """
                UPDATE cache.websim_active_manifest_pointer
                SET pointer_mode = %s,
                    manifest_revision = %s,
                    generation = %s,
                    rollback_manifest_revision = %s,
                    updated_at = now(),
                    updated_by = %s
                WHERE environment = 'retail' AND generation = %s
                """,
                (
                    target_mode,
                    manifest_revision or None,
                    target_generation,
                    rollback_manifest_revision or None,
                    _text(updated_by),
                    expected_generation,
                ),
            )
        if getattr(cur, "rowcount", 0) != 1:
            raise StaleManifestPointerError("active manifest pointer generation changed")
        self._insert_event(
            cur,
            manifest_revision=manifest_revision,
            event_type=f"manifest_{action}",
            event={
                "expectedGeneration": expected_generation,
                "generation": target_generation,
                "pointerMode": target_mode,
                "updatedBy": _text(updated_by),
            },
        )
        return {
            "status": "updated",
            "pointerMode": target_mode,
            "manifestRevision": manifest_revision,
            "generation": target_generation,
        }

    def compare_and_swap_pointer(self, command: dict[str, Any], *, updated_by: str) -> dict[str, Any]:
        self._validated_pointer_command(command, updated_by)
        with self.connection() as conn:
            with conn.cursor() as cur:
                return self._compare_and_swap_pointer_with_cursor(cur, command, updated_by=updated_by)

    def seal_manifest_and_compare_and_swap_pointer(
        self,
        manifest: dict[str, Any],
        command: dict[str, Any],
        *,
        updated_by: str,
    ) -> dict[str, Any]:
        revision = self._validated_manifest_revision(manifest)
        action, target_mode, command_revision, _, _ = self._validated_pointer_command(command, updated_by)
        if action != "promote" or target_mode != "active":
            raise ValueError("atomic Manifest activation requires an active promote command")
        if command_revision != revision:
            raise GearReleaseIntegrityError("pointer command does not target the supplied Manifest")
        with self.connection() as conn:
            with conn.cursor() as cur:
                seal = self._seal_manifest_with_cursor(cur, manifest)
                pointer = self._compare_and_swap_pointer_with_cursor(cur, command, updated_by=updated_by)
        return {"manifest": seal, "pointer": pointer}


__all__ = (
    "CandidateGearAuthorityIndex",
    "GearReleaseIntegrityError",
    "GearReleaseStore",
    "StaleManifestPointerError",
    "build_candidate_authority_context",
    "canonical_row_hash",
    "community_rows_summary",
    "gear_snapshot_summary",
)

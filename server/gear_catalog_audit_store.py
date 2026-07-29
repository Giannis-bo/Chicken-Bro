#!/usr/bin/env python3
"""Fixed-query, read-only PostgreSQL projection for gear catalog Phase 0.

The store projects bounded structural inputs only. It owns no migration
classification and never commits or writes runtime state.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping

try:
    from .gear_contracts import community_template_authority_identity
except ImportError:
    from gear_contracts import community_template_authority_identity


_RELATION_ALLOWLIST = (
    "app.build_templates",
    "cache.websim_active_manifest_pointer",
    "cache.websim_community_release_templates",
    "cache.websim_gear_release_items",
    "cache.websim_gear_release_mod_options",
    "cache.websim_gear_release_sources",
    "cache.websim_gear_release_variants",
    "cache.websim_gear_stat_snapshots",
    "cache.websim_release_events",
    "cache.websim_release_registry",
    "cache.websim_season_manifests",
    "ops.websim_gear_stat_jobs",
)
_MAX_ROWS_PER_SECTION = 100_000
_WRITE_PREFIXES = (
    "INSERT ",
    "UPDATE ",
    "DELETE ",
    "MERGE ",
    "TRUNCATE ",
    "ALTER ",
    "CREATE ",
    "DROP ",
    "GRANT ",
    "REVOKE ",
)


class GearCatalogAuditPointerChanged(RuntimeError):
    pass


class GearCatalogAuditQueryFailed(RuntimeError):
    def __init__(self, query_marker: str, sqlstate: str = ""):
        self.query_marker = query_marker
        self.sqlstate = sqlstate
        suffix = f":{sqlstate}" if sqlstate else ""
        super().__init__(f"AUDIT_QUERY_FAILED:{query_marker}{suffix}")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _json_value(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return fallback
    return parsed if isinstance(parsed, type(fallback)) else fallback


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _anonymous_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _split_ids(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [_text(item) for item in value if _text(item)]
    if not isinstance(value, str):
        return []
    return [
        part.strip()
        for part in re.split(r"[/,;]", value)
        if part.strip()
    ]


def _stat_map(value: Any) -> dict[str, int | float]:
    if isinstance(value, Mapping):
        return {
            _text(key): amount
            for key, amount in value.items()
            if _text(key)
            and not isinstance(amount, bool)
            and isinstance(amount, (int, float))
        }
    if isinstance(value, list):
        result: dict[str, int | float] = {}
        for row in value:
            if not isinstance(row, Mapping):
                continue
            key = _text(row.get("key") or row.get("stat"))
            amount = row.get("value")
            if key and not isinstance(amount, bool) and isinstance(amount, (int, float)):
                result[key] = amount
        return result
    return {}


def _normalized_gear_item(slot: Any, value: Any, enhancement: Any = None) -> dict[str, Any]:
    item = _mapping(value)
    simc = _mapping(item.get("simcOptions"))
    enhancements = _mapping(enhancement)

    def first_present(
        *candidates: tuple[Mapping[str, Any], str],
    ) -> tuple[bool, Any]:
        for source, key in candidates:
            if key in source:
                return True, source.get(key)
        return False, None

    bonus_ids = item.get("bonusIds") if "bonusIds" in item else None
    if bonus_ids is None:
        bonus_ids = _split_ids(simc.get("bonus_id"))
    enhancement_values = {
        "gemIds": first_present(
            (item, "gemIds"),
            (enhancements, "gemIds"),
            (enhancements, "gemOptionIds"),
            (simc, "gem_id"),
        ),
        "gemBonusIds": first_present(
            (item, "gemBonusIds"),
            (enhancements, "gemBonusIds"),
            (simc, "gem_bonus_id"),
        ),
        "gemItemLevels": first_present(
            (item, "gemItemLevels"),
            (enhancements, "gemItemLevels"),
            (simc, "gem_ilevel"),
        ),
        "enchantId": first_present(
            (item, "enchantId"),
            (enhancements, "enchantId"),
            (enhancements, "enchantOptionId"),
            (simc, "enchant_id"),
        ),
        "craftedStats": first_present(
            (item, "craftedStats"),
            (enhancements, "craftedStats"),
            (simc, "crafted_stats"),
        ),
        "embellishmentIds": first_present(
            (item, "embellishmentIds"),
            (enhancements, "embellishmentIds"),
            (simc, "embellishment"),
        ),
    }
    result = {
        "slot": _text(slot or item.get("slot")),
        "itemId": _text(item.get("itemId") or item.get("id")),
        "variantKey": _text(item.get("variantKey")),
        "observedItemLevel": _int(item.get("observedItemLevel")),
        "bonusIds": list(bonus_ids) if isinstance(bonus_ids, list) else bonus_ids,
        "trackKey": _text(item.get("trackKey") or item.get("upgradeTrack")),
        "rank": _int(item.get("rank") or item.get("trackRank") or item.get("upgradeRank")),
        "ilevel": _int(item.get("ilevel") or item.get("itemLevel") or simc.get("ilevel")),
    }
    for field, (present, selected) in enhancement_values.items():
        if not present:
            continue
        if field == "enchantId":
            result[field] = selected
        elif isinstance(selected, list):
            result[field] = list(selected)
        elif isinstance(selected, str):
            result[field] = _split_ids(selected)
        else:
            result[field] = selected
    return result


def _gear_items_from_slots(slots: Any, enhancements: Any = None) -> list[dict[str, Any]]:
    slot_rows = _mapping(slots)
    enhancement_rows = _mapping(enhancements)
    return [
        _normalized_gear_item(
            slot,
            slot_rows[slot],
            enhancement_rows.get(slot),
        )
        for slot in sorted(slot_rows)
        if isinstance(slot_rows.get(slot), Mapping)
    ]


def _gear_items_from_template_payload(payload: Any, metadata: Any = None) -> list[dict[str, Any]]:
    source = _mapping(payload)
    meta = _mapping(metadata)
    selection = _mapping(source.get("selectionIntent"))
    if isinstance(selection.get("slots"), Mapping):
        return _gear_items_from_slots(selection.get("slots"))
    if isinstance(source.get("slots"), Mapping):
        return _gear_items_from_slots(source.get("slots"))
    if isinstance(source.get("gearBySlot"), Mapping):
        return _gear_items_from_slots(
            source.get("gearBySlot"),
            source.get("enhancementBySlot"),
        )
    gear_items = source.get("gearItems")
    if isinstance(gear_items, list):
        return [
            _normalized_gear_item(item.get("slot"), item)
            for item in gear_items
            if isinstance(item, Mapping)
        ]
    for candidate in (
        meta.get("gearSnapshot"),
        meta,
    ):
        if not isinstance(candidate, Mapping):
            continue
        if isinstance(candidate.get("gearBySlot"), Mapping):
            return _gear_items_from_slots(
                candidate.get("gearBySlot"),
                candidate.get("enhancementBySlot"),
            )
    raw_string = source.get("rawString")
    parsed = _json_value(raw_string, {}) if isinstance(raw_string, str) else {}
    if isinstance(parsed.get("gearBySlot"), Mapping):
        return _gear_items_from_slots(
            parsed.get("gearBySlot"),
            parsed.get("enhancementBySlot"),
        )
    if parsed and all(isinstance(value, Mapping) for value in parsed.values()):
        return _gear_items_from_slots(parsed)
    return []


def _normalized_sql(sql: Any) -> str:
    return " ".join(str(sql or "").split())


def _statement_kind(sql: Any) -> str:
    normalized = _normalized_sql(sql).upper()
    normalized = re.sub(r"^/\*.*?\*/\s*", "", normalized)
    if normalized.startswith(_WRITE_PREFIXES):
        return "write"
    if normalized.startswith(("BEGIN ", "SET ")):
        return "transaction"
    return "read"


def _query_marker(sql: Any) -> str:
    match = re.search(
        r"/\*\s*(gear_catalog_audit_[a-z0-9_]+)\s*\*/",
        str(sql or ""),
        re.IGNORECASE,
    )
    return match.group(1).lower() if match else "transaction_control"


def _legacy_variant_row_family(difficulty_key: Any) -> str:
    normalized = _text(difficulty_key).lower()
    if normalized == "observed_profile":
        return "exact_instance"
    if normalized in {"needs-variant", "needs_variant"}:
        return "placeholder"
    if normalized == "battle_net_preview":
        return "reference"
    if normalized:
        return "browse"
    return "unclassified"


class GearCatalogAuditStore:
    """Read current catalog migration inputs in one stable read-only snapshot."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory
        self.query_count = 0
        self._read_count = 0
        self._write_count = 0
        self._transaction_count = 0

    def _execute(self, cursor, sql: str, params: Iterable[Any] = ()):
        self.query_count += 1
        kind = _statement_kind(sql)
        if kind == "write":
            self._write_count += 1
            raise RuntimeError("gear catalog audit attempted a write statement")
        if kind == "transaction":
            self._transaction_count += 1
        else:
            self._read_count += 1
        try:
            cursor.execute(sql, tuple(params))
        except Exception as exc:
            sqlstate = _text(
                getattr(exc, "sqlstate", "")
                or getattr(exc, "pgcode", "")
            ).upper()
            if not re.fullmatch(r"[0-9A-Z]{5}", sqlstate):
                sqlstate = ""
            raise GearCatalogAuditQueryFailed(
                _query_marker(sql),
                sqlstate,
            ) from None

    @staticmethod
    def _bounded_rows(cursor, batch_size: int) -> list[Any]:
        fetchmany = getattr(cursor, "fetchmany", None)
        if not callable(fetchmany):
            rows = list(cursor.fetchall())
            if len(rows) > _MAX_ROWS_PER_SECTION:
                raise RuntimeError("gear catalog audit section exceeds row limit")
            return rows
        rows = []
        while True:
            chunk = list(fetchmany(batch_size))
            if not chunk:
                break
            rows.extend(chunk)
            if len(rows) > _MAX_ROWS_PER_SECTION:
                raise RuntimeError("gear catalog audit section exceeds row limit")
        return rows

    def _pointer_binding(self, cursor) -> dict[str, Any]:
        self._execute(
            cursor,
            """
            /* gear_catalog_audit_pointer_binding */
            SELECT
                pointer.generation,
                pointer.manifest_revision,
                pointer.pointer_mode,
                pointer.rollback_manifest_revision,
                manifest.season_revision,
                manifest.gear_release_id,
                manifest.community_release_id,
                manifest.talent_catalog_revision,
                manifest.dependency_vector_json,
                manifest.rollback_manifest_revision,
                gear.dependency_vector_json,
                community.dependency_vector_json,
                gear.schema_revision,
                gear.content_hash,
                gear.source_json,
                gear.content_summary_json,
                gear.release_status
            FROM cache.websim_active_manifest_pointer pointer
            LEFT JOIN cache.websim_season_manifests manifest
              ON manifest.manifest_revision = pointer.manifest_revision
            LEFT JOIN cache.websim_release_registry gear
              ON gear.release_id = manifest.gear_release_id
            LEFT JOIN cache.websim_release_registry community
              ON community.release_id = manifest.community_release_id
            WHERE pointer.environment = 'retail'
            """,
        )
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("active retail Manifest pointer is unavailable")
        return {
            "generation": _int(row[0]),
            "manifestRevision": _text(row[1]),
            "pointerMode": _text(row[2]),
            "rollbackManifestRevision": _text(row[3]),
            "seasonRevision": _text(row[4]),
            "gearReleaseId": _text(row[5]),
            "communityReleaseId": _text(row[6]),
            "talentCatalogRevision": _text(row[7]),
            "manifestDependencyVector": _mapping(row[8]),
            "manifestRollbackRevision": _text(row[9]),
            "gearDependencyVector": _mapping(row[10]),
            "communityDependencyVector": _mapping(row[11]),
            "gearSchemaRevision": _text(row[12]),
            "gearContentHash": _text(row[13]),
            "gearSource": _mapping(row[14]),
            "gearContentSummary": _mapping(row[15]),
            "gearReleaseStatus": _text(row[16]),
        }

    def _items(self, cursor, release_id: str, batch_size: int) -> list[dict[str, Any]]:
        self._execute(
            cursor,
            """
            /* gear_catalog_audit_items */
            SELECT
                item.item_id,
                item.name,
                item.slot,
                item.item_level,
                item.source_status,
                item.payload_json,
                EXISTS (
                    SELECT 1
                    FROM cache.websim_gear_release_sources source
                    WHERE source.release_id = item.release_id
                      AND source.item_id = item.item_id
                ) AS has_source_refs,
                EXISTS (
                    SELECT 1
                    FROM cache.websim_gear_release_variants variant
                    WHERE variant.release_id = item.release_id
                      AND variant.item_id = item.item_id
                ) AS has_variant_refs
            FROM cache.websim_gear_release_items item
            WHERE item.release_id = %s
            ORDER BY item.item_id
            """,
            (release_id,),
        )
        return [
            {
                "itemId": _text(row[0]),
                "name": _text(row[1]),
                "slot": _text(row[2]),
                "itemLevel": _int(row[3]),
                "sourceStatus": _text(row[4]),
                "payload": _mapping(row[5]),
                "hasSourceRefs": row[6] is True,
                "hasVariantRefs": row[7] is True,
            }
            for row in self._bounded_rows(cursor, batch_size)
        ]

    def _variants(self, cursor, release_id: str, batch_size: int) -> list[dict[str, Any]]:
        self._execute(
            cursor,
            """
            /* gear_catalog_audit_variants */
            SELECT
                variant_id,
                item_id,
                variant_key,
                slot,
                difficulty_key,
                item_level,
                simc_options_json,
                status,
                blockers_json,
                payload_json,
                variant.source_type,
                EXISTS (
                    SELECT 1
                    FROM cache.websim_gear_release_sources source
                    WHERE source.release_id = variant.release_id
                      AND source.item_id = variant.item_id
                      AND source.instance_id = '1305'
                ) AS has_void_instance_source,
                EXISTS (
                    SELECT 1
                    FROM cache.websim_gear_release_sources source
                    WHERE source.release_id = variant.release_id
                      AND source.item_id = variant.item_id
                      AND source.source_type = 'crafted'
                      AND (
                          LOWER(COALESCE(source.payload_json->>'status', '')) = 'verified'
                          OR LOWER(COALESCE(source.payload_json->>'sourceStatus', '')) = 'verified'
                      )
                ) AS has_crafted_source
            FROM cache.websim_gear_release_variants variant
            WHERE variant.release_id = %s
            ORDER BY variant.item_id, variant.variant_key, variant.variant_id
            """,
            (release_id,),
        )
        result = []
        for row in self._bounded_rows(cursor, batch_size):
            simc_options = _mapping(row[6])
            payload = _mapping(row[9])
            bonus_ids = payload.get("bonusIds")
            if not isinstance(bonus_ids, list):
                bonus_ids = _split_ids(simc_options.get("bonus_id"))
            static_stats = (
                payload.get("staticStats")
                or payload.get("resolvedStats")
                or _stat_map(payload.get("itemStats"))
            )
            result.append({
                "variantId": _text(row[0]),
                "itemId": _text(row[1]),
                "variantKey": _text(row[2]),
                "slot": _text(row[3]),
                "difficultyKey": _text(row[4]),
                "rowFamily": _legacy_variant_row_family(row[4]),
                "trackKey": _text(
                    payload.get("trackKey")
                    or payload.get("upgradeTrack")
                    or payload.get("itemLevelTrack")
                    or row[4]
                ),
                "trackRank": _int(
                    payload.get("trackRank")
                    or payload.get("upgradeRank")
                ),
                "itemLevel": _int(row[5] or simc_options.get("ilevel")),
                "bonusIds": [_text(value) for value in bonus_ids if _text(value)],
                "simcOptions": simc_options,
                "staticStats": _stat_map(static_stats),
                "context": payload.get("context"),
                "sourceType": _text(row[10]),
                "hasVoidInstanceSource": row[11] is True,
                "hasCraftedSource": len(row) > 12 and row[12] is True,
                "hasTrackEvidence": (
                    isinstance(payload.get("trackEvidence"), list)
                    and bool(payload.get("trackEvidence"))
                ),
                "status": _text(row[7]),
                "blockers": _json_value(row[8], []),
            })
        return result

    def _sources(self, cursor, release_id: str, batch_size: int) -> list[dict[str, Any]]:
        self._execute(
            cursor,
            """
            /* gear_catalog_audit_sources */
            SELECT
                source_id,
                item_id,
                source_type,
                source_key,
                source_label,
                instance_id,
                encounter_id,
                difficulty_key,
                season_revision,
                payload_json
            FROM cache.websim_gear_release_sources
            WHERE release_id = %s
            ORDER BY item_id, source_type, source_key, source_id
            """,
            (release_id,),
        )
        result = []
        for row in self._bounded_rows(cursor, batch_size):
            payload = _mapping(row[9])
            result.append({
                "sourceId": _text(row[0]),
                "itemId": _text(row[1]),
                "sourceType": _text(row[2]),
                "sourceKey": _text(row[3]),
                "sourceLabel": _text(row[4]),
                "instanceId": _text(row[5]),
                "encounterId": _text(row[6]),
                "difficultyKey": _text(row[7]),
                "seasonRevision": _text(row[8]),
                "status": _text(payload.get("status") or "unknown"),
                "sourceStatus": _text(
                    payload.get("sourceStatus") or "unknown"
                ),
            })
        return result

    def _options(self, cursor, release_id: str, batch_size: int) -> list[dict[str, Any]]:
        self._execute(
            cursor,
            """
            /* gear_catalog_audit_options */
            SELECT option_id, option_key, option_type, status, simc_options_json, payload_json
            FROM cache.websim_gear_release_mod_options
            WHERE release_id = %s
            ORDER BY option_key, option_id
            """,
            (release_id,),
        )
        return [
            {
                "optionId": _text(row[0]),
                "optionKey": _text(row[1]),
                "optionType": _text(row[2]),
                "status": _text(row[3]),
                "simcOptions": _mapping(row[4]),
                "payload": _mapping(row[5]),
            }
            for row in self._bounded_rows(cursor, batch_size)
        ]

    def _community_templates(
        self,
        cursor,
        release_id: str,
        batch_size: int,
    ) -> list[dict[str, Any]]:
        self._execute(
            cursor,
            """
            /* gear_catalog_audit_community_templates */
            SELECT
                template_id,
                class_key,
                spec_key,
                selection_intent_json,
                payload_json,
                problems_json
            FROM cache.websim_community_release_templates
            WHERE release_id = %s
              AND role = 'winner'
            ORDER BY class_key, spec_key, template_id
            """,
            (release_id,),
        )
        result = []
        for row in self._bounded_rows(cursor, batch_size):
            selection_intent = _mapping(row[3])
            payload = _mapping(row[4])
            source = {
                **payload,
                "selectionIntent": selection_intent,
            }
            gear_items = _gear_items_from_template_payload(source)
            import_evidence = _mapping(payload.get("importEvidence"))
            evidence_slots = _mapping(import_evidence.get("slots"))
            for item in gear_items:
                slot = _text(item.get("slot"))
                evidence = _mapping(evidence_slots.get(slot))
                if (
                    evidence
                    and _text(evidence.get("itemId")) == _text(item.get("itemId"))
                    and _text(evidence.get("variantKey"))
                    == _text(item.get("variantKey"))
                ):
                    item["observedItemLevel"] = _int(
                        evidence.get("observedItemLevel")
                    )
            result.append({
                "templateIdentity": community_template_authority_identity(
                    row[0]
                ),
                "classKey": _text(row[1]),
                "specKey": _text(row[2]),
                "selectionIntent": selection_intent,
                "gearItems": gear_items,
                "problemCodes": sorted({
                    _text(problem.get("code"))
                    for problem in _json_value(row[5], [])
                    if isinstance(problem, Mapping) and _text(problem.get("code"))
                }),
            })
        return result

    def _personal_templates(self, cursor, batch_size: int) -> list[dict[str, Any]]:
        self._execute(
            cursor,
            """
            /* gear_catalog_audit_personal_templates */
            SELECT config_hash, payload_json, metadata_json
            FROM app.build_templates
            WHERE template_type = 'gear'
            ORDER BY config_hash, id
            """,
        )
        result = []
        for row in self._bounded_rows(cursor, batch_size):
            config_hash = _text(row[0])
            identity = (
                f"sha256:{config_hash}"
                if re.fullmatch(r"[0-9a-f]{64}", config_hash)
                else _anonymous_hash({"source": "personal", "configHash": config_hash})
            )
            result.append({
                "templateIdentity": identity,
                "gearItems": _gear_items_from_template_payload(
                    _mapping(row[1]),
                    _mapping(row[2]),
                ),
            })
        return result

    def _relation_sizes(
        self,
        cursor,
        binding: Mapping[str, Any],
        batch_size: int,
    ) -> list[dict[str, Any]]:
        self._execute(
            cursor,
            """
            /* gear_catalog_audit_relation_sizes */
            WITH relation_names AS (
                SELECT unnest(%s::text[]) AS relation_name
            ), bindings AS (
                SELECT
                    active_manifest.manifest_revision AS active_manifest_revision,
                    active_manifest.gear_release_id AS active_gear_release_id,
                    active_manifest.community_release_id AS active_community_release_id,
                    rollback_manifest.manifest_revision AS rollback_manifest_revision,
                    rollback_manifest.gear_release_id AS rollback_gear_release_id,
                    rollback_manifest.community_release_id AS rollback_community_release_id
                FROM cache.websim_active_manifest_pointer pointer
                LEFT JOIN cache.websim_season_manifests active_manifest
                  ON active_manifest.manifest_revision = pointer.manifest_revision
                LEFT JOIN cache.websim_season_manifests rollback_manifest
                  ON rollback_manifest.manifest_revision = pointer.rollback_manifest_revision
                WHERE pointer.environment = 'retail'
            ), logical_sizes AS (
                SELECT
                    'cache.websim_release_registry'::text AS relation_name,
                    COALESCE(SUM(pg_column_size(release_row)) FILTER (
                        WHERE release_row.release_id IN (
                            bindings.active_gear_release_id,
                            bindings.active_community_release_id
                        )
                    ), 0)::bigint AS active_bytes,
                    COALESCE(SUM(pg_column_size(release_row)) FILTER (
                        WHERE release_row.release_id IN (
                            bindings.rollback_gear_release_id,
                            bindings.rollback_community_release_id
                        )
                    ), 0)::bigint AS rollback_bytes
                FROM cache.websim_release_registry release_row
                CROSS JOIN bindings
                WHERE release_row.release_id = ANY(ARRAY[
                    bindings.active_gear_release_id,
                    bindings.active_community_release_id,
                    bindings.rollback_gear_release_id,
                    bindings.rollback_community_release_id
                ])
                UNION ALL
                SELECT
                    'cache.websim_gear_release_items',
                    COALESCE(SUM(pg_column_size(item_row)) FILTER (
                        WHERE item_row.release_id = bindings.active_gear_release_id
                    ), 0)::bigint,
                    COALESCE(SUM(pg_column_size(item_row)) FILTER (
                        WHERE item_row.release_id = bindings.rollback_gear_release_id
                    ), 0)::bigint
                FROM cache.websim_gear_release_items item_row
                CROSS JOIN bindings
                WHERE item_row.release_id = ANY(ARRAY[
                    bindings.active_gear_release_id,
                    bindings.rollback_gear_release_id
                ])
                UNION ALL
                SELECT
                    'cache.websim_gear_release_sources',
                    COALESCE(SUM(pg_column_size(source_row)) FILTER (
                        WHERE source_row.release_id = bindings.active_gear_release_id
                    ), 0)::bigint,
                    COALESCE(SUM(pg_column_size(source_row)) FILTER (
                        WHERE source_row.release_id = bindings.rollback_gear_release_id
                    ), 0)::bigint
                FROM cache.websim_gear_release_sources source_row
                CROSS JOIN bindings
                WHERE source_row.release_id = ANY(ARRAY[
                    bindings.active_gear_release_id,
                    bindings.rollback_gear_release_id
                ])
                UNION ALL
                SELECT
                    'cache.websim_gear_release_variants',
                    COALESCE(SUM(pg_column_size(variant_row)) FILTER (
                        WHERE variant_row.release_id = bindings.active_gear_release_id
                    ), 0)::bigint,
                    COALESCE(SUM(pg_column_size(variant_row)) FILTER (
                        WHERE variant_row.release_id = bindings.rollback_gear_release_id
                    ), 0)::bigint
                FROM cache.websim_gear_release_variants variant_row
                CROSS JOIN bindings
                WHERE variant_row.release_id = ANY(ARRAY[
                    bindings.active_gear_release_id,
                    bindings.rollback_gear_release_id
                ])
                UNION ALL
                SELECT
                    'cache.websim_gear_release_mod_options',
                    COALESCE(SUM(pg_column_size(option_row)) FILTER (
                        WHERE option_row.release_id = bindings.active_gear_release_id
                    ), 0)::bigint,
                    COALESCE(SUM(pg_column_size(option_row)) FILTER (
                        WHERE option_row.release_id = bindings.rollback_gear_release_id
                    ), 0)::bigint
                FROM cache.websim_gear_release_mod_options option_row
                CROSS JOIN bindings
                WHERE option_row.release_id = ANY(ARRAY[
                    bindings.active_gear_release_id,
                    bindings.rollback_gear_release_id
                ])
                UNION ALL
                SELECT
                    'cache.websim_community_release_templates',
                    COALESCE(SUM(pg_column_size(template_row)) FILTER (
                        WHERE template_row.release_id = bindings.active_community_release_id
                    ), 0)::bigint,
                    COALESCE(SUM(pg_column_size(template_row)) FILTER (
                        WHERE template_row.release_id = bindings.rollback_community_release_id
                    ), 0)::bigint
                FROM cache.websim_community_release_templates template_row
                CROSS JOIN bindings
                WHERE template_row.release_id = ANY(ARRAY[
                    bindings.active_community_release_id,
                    bindings.rollback_community_release_id
                ])
                UNION ALL
                SELECT
                    'cache.websim_season_manifests',
                    COALESCE(SUM(pg_column_size(manifest_row)) FILTER (
                        WHERE manifest_row.manifest_revision = bindings.active_manifest_revision
                    ), 0)::bigint,
                    COALESCE(SUM(pg_column_size(manifest_row)) FILTER (
                        WHERE manifest_row.manifest_revision = bindings.rollback_manifest_revision
                    ), 0)::bigint
                FROM cache.websim_season_manifests manifest_row
                CROSS JOIN bindings
                WHERE manifest_row.manifest_revision = ANY(ARRAY[
                    bindings.active_manifest_revision,
                    bindings.rollback_manifest_revision
                ])
            )
            SELECT
                relation_names.relation_name,
                pg_total_relation_size(relation_names.relation_name::regclass),
                COALESCE(logical_sizes.active_bytes, 0) AS active_logical_bytes,
                COALESCE(logical_sizes.rollback_bytes, 0) AS rollback_logical_bytes
            FROM relation_names
            LEFT JOIN logical_sizes USING (relation_name)
            ORDER BY relation_names.relation_name
            """,
            (list(_RELATION_ALLOWLIST),),
        )
        return [
            {
                "relation": _text(row[0]),
                "totalBytes": _int(row[1]),
                "activeLogicalBytes": _int(row[2]),
                "rollbackLogicalBytes": _int(row[3]),
            }
            for row in self._bounded_rows(cursor, batch_size)
        ]

    def _release_events(
        self,
        cursor,
        binding: Mapping[str, Any],
        batch_size: int,
    ) -> list[dict[str, Any]]:
        self._execute(
            cursor,
            """
            /* gear_catalog_audit_release_events */
            SELECT event_type, COUNT(*), MAX(created_at)::text
            FROM cache.websim_release_events
            WHERE release_id = ANY(%s::text[])
               OR manifest_revision = ANY(%s::text[])
            GROUP BY event_type
            ORDER BY event_type
            """,
            (
                [
                    value
                    for value in (
                        _text(binding.get("gearReleaseId")),
                        _text(binding.get("communityReleaseId")),
                    )
                    if value
                ],
                [
                    value
                    for value in (
                        _text(binding.get("manifestRevision")),
                        _text(binding.get("manifestRollbackRevision")),
                    )
                    if value
                ],
            ),
        )
        return [
            {
                "eventType": _text(row[0]),
                "count": _int(row[1]),
                "latestAt": _text(row[2]),
            }
            for row in self._bounded_rows(cursor, batch_size)
        ]

    @staticmethod
    def _pointer_identity(binding: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "generation": _int(binding.get("generation")),
            "manifestRevision": _text(binding.get("manifestRevision")),
            "pointerMode": _text(binding.get("pointerMode")),
            "rollbackManifestRevision": _text(binding.get("rollbackManifestRevision")),
        }

    def pointer_identity(
        self,
        *,
        statement_timeout_ms: int = 5_000,
        lock_timeout_ms: int = 1_000,
    ) -> dict[str, Any]:
        """Read only the active pointer fence after a dormant seal."""

        if not 1 <= _int(statement_timeout_ms) <= 30_000:
            raise ValueError("statement_timeout_ms must be between 1 and 30000")
        if not 1 <= _int(lock_timeout_ms) <= 5_000:
            raise ValueError("lock_timeout_ms must be between 1 and 5000")
        connection = self._connection_factory()
        try:
            with connection.cursor() as cursor:
                self._execute(cursor, "BEGIN READ ONLY")
                self._execute(
                    cursor,
                    f"SET LOCAL statement_timeout = '{_int(statement_timeout_ms)}ms'",
                )
                self._execute(
                    cursor,
                    f"SET LOCAL lock_timeout = '{_int(lock_timeout_ms)}ms'",
                )
                binding = self._pointer_binding(cursor)
                return self._pointer_identity(binding)
        finally:
            try:
                connection.rollback()
            finally:
                connection.close()

    def snapshot(
        self,
        *,
        statement_timeout_ms: int = 15_000,
        lock_timeout_ms: int = 1_000,
        batch_size: int = 500,
    ) -> dict[str, Any]:
        if not 1 <= _int(statement_timeout_ms) <= 30_000:
            raise ValueError("statement_timeout_ms must be between 1 and 30000")
        if not 1 <= _int(lock_timeout_ms) <= 5_000:
            raise ValueError("lock_timeout_ms must be between 1 and 5000")
        if not 1 <= _int(batch_size) <= 1_000:
            raise ValueError("batch_size must be between 1 and 1000")

        self.query_count = 0
        self._read_count = 0
        self._write_count = 0
        self._transaction_count = 0
        connection = self._connection_factory()
        try:
            with connection.cursor() as cursor:
                self._execute(cursor, "BEGIN READ ONLY")
                self._execute(
                    cursor,
                    f"SET LOCAL statement_timeout = '{_int(statement_timeout_ms)}ms'",
                )
                self._execute(
                    cursor,
                    f"SET LOCAL lock_timeout = '{_int(lock_timeout_ms)}ms'",
                )
                before = self._pointer_binding(cursor)
                gear_release_id = _text(before.get("gearReleaseId"))
                community_release_id = _text(before.get("communityReleaseId"))
                items = self._items(cursor, gear_release_id, batch_size)
                sources = self._sources(cursor, gear_release_id, batch_size)
                variants = self._variants(cursor, gear_release_id, batch_size)
                options = self._options(cursor, gear_release_id, batch_size)
                community = self._community_templates(
                    cursor,
                    community_release_id,
                    batch_size,
                )
                personal = self._personal_templates(cursor, batch_size)
                relation_sizes = self._relation_sizes(cursor, before, batch_size)
                release_events = self._release_events(cursor, before, batch_size)
                after = self._pointer_binding(cursor)

            pointer_before = self._pointer_identity(before)
            pointer_after = self._pointer_identity(after)
            if pointer_before != pointer_after:
                raise GearCatalogAuditPointerChanged(
                    "AUDIT_POINTER_CHANGED: active Manifest pointer changed during read-only audit"
                )
            return {
                "schemaRevision": "gear-catalog-audit-store-snapshot-v2",
                "pointerBefore": pointer_before,
                "activeBinding": {
                    "manifest": {
                        "manifestRevision": _text(before.get("manifestRevision")),
                        "seasonRevision": _text(before.get("seasonRevision")),
                        "talentCatalogRevision": _text(before.get("talentCatalogRevision")),
                        "rollbackManifestRevision": _text(
                            before.get("manifestRollbackRevision")
                        ),
                        "dependencyVector": _mapping(
                            before.get("manifestDependencyVector")
                        ),
                    },
                    "gearRelease": {
                        "releaseId": gear_release_id,
                        "schemaRevision": _text(
                            before.get("gearSchemaRevision")
                        ),
                        "contentHash": _text(before.get("gearContentHash")),
                        "releaseStatus": _text(
                            before.get("gearReleaseStatus")
                        ),
                        "dependencyVector": _mapping(
                            before.get("gearDependencyVector")
                        ),
                        "source": _mapping(before.get("gearSource")),
                        "contentSummary": _mapping(
                            before.get("gearContentSummary")
                        ),
                    },
                    "communityRelease": {
                        "releaseId": community_release_id,
                        "dependencyVector": _mapping(
                            before.get("communityDependencyVector")
                        ),
                    },
                },
                "catalogRows": {
                    "items": items,
                    "sources": sources,
                    "variants": variants,
                    "options": options,
                },
                "communityTemplates": community,
                "personalGearTemplates": personal,
                "relationSizes": relation_sizes,
                "releaseEvents": release_events,
                "pointerAfter": pointer_after,
                "queryMetrics": {
                    "total": self.query_count,
                    "transactionControl": self._transaction_count,
                    "reads": self._read_count,
                    "writes": self._write_count,
                },
            }
        finally:
            try:
                connection.rollback()
            finally:
                connection.close()


__all__ = (
    "GearCatalogAuditPointerChanged",
    "GearCatalogAuditQueryFailed",
    "GearCatalogAuditStore",
)

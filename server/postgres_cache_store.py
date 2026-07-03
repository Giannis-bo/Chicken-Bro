#!/usr/bin/env python3
from contextlib import contextmanager
import copy
import json
import uuid
from datetime import datetime, timezone

try:
    from .websim_payload import (
        CANONICAL_GEAR_SLOTS,
        COMMUNITY_TEMPLATE_REVISION,
        COMMUNITY_TALENT_SYNC_KEY,
        DEFAULT_LOCALE,
        GEAR_CATALOG_REVISION,
        GEAR_SCHEMA_REVISION,
        GEAR_SLOT_LABELS,
        TALENT_SCHEMA_REVISION,
        active_catalog_sources_for_replacement,
        blocked_stat_snapshot,
        class_label,
        classes_payload,
        compact_catalog_health_summary,
        compact_gear_candidates,
        compact_gear_mod_options,
        dedupe_community_talent_templates_for_display,
        dedupe_gear_community_templates,
        dedupe_real_talent_nodes,
        decorate_real_talent_node,
        enrich_catalog_item,
        current_season_payload,
        fallback_text_for,
        fallback_presets,
        game_asset_from_icon_url,
        game_asset_from_registry_row,
        gear_candidate_for_slot,
        gear_candidate_quality_score,
        gear_candidate_slots,
        gear_readiness,
        gear_slot_payload,
        gear_slot_readiness,
        hero_tree_for,
        hero_tree_label,
        localized_difficulty_label,
        normalize_source_refs,
        normalize_slot,
        normalize_current_season_raid_pool_payload,
        normalize_gear_item,
        normalize_community_gear_template,
        normalize_community_talent_template,
        sanitize_gear_candidate_mod_options,
        SCENARIOS,
        scenario_title,
        season_metadata_fields,
        simc_version_payload,
        slugify,
        spec_label,
        talent_readiness_payload,
        websim_talent_import_response,
        talent_spell_display_description,
        talent_tree_sections,
        unique_text_list,
        unique_gear_candidates,
        unique_locale_preferences,
        websim_gear_community_templates,
        websim_gear_community_template_sync_state,
        websim_max_level,
        weapon_equipment_rule_payload,
    )
except ImportError:
    from websim_payload import (
        CANONICAL_GEAR_SLOTS,
        COMMUNITY_TEMPLATE_REVISION,
        COMMUNITY_TALENT_SYNC_KEY,
        DEFAULT_LOCALE,
        GEAR_CATALOG_REVISION,
        GEAR_SCHEMA_REVISION,
        GEAR_SLOT_LABELS,
        TALENT_SCHEMA_REVISION,
        active_catalog_sources_for_replacement,
        blocked_stat_snapshot,
        class_label,
        classes_payload,
        compact_catalog_health_summary,
        compact_gear_candidates,
        compact_gear_mod_options,
        dedupe_community_talent_templates_for_display,
        dedupe_gear_community_templates,
        dedupe_real_talent_nodes,
        decorate_real_talent_node,
        enrich_catalog_item,
        current_season_payload,
        fallback_text_for,
        fallback_presets,
        game_asset_from_icon_url,
        game_asset_from_registry_row,
        gear_candidate_for_slot,
        gear_candidate_quality_score,
        gear_candidate_slots,
        gear_readiness,
        gear_slot_payload,
        gear_slot_readiness,
        hero_tree_for,
        hero_tree_label,
        localized_difficulty_label,
        normalize_source_refs,
        normalize_slot,
        normalize_current_season_raid_pool_payload,
        normalize_gear_item,
        normalize_community_gear_template,
        normalize_community_talent_template,
        sanitize_gear_candidate_mod_options,
        SCENARIOS,
        scenario_title,
        season_metadata_fields,
        simc_version_payload,
        slugify,
        spec_label,
        talent_readiness_payload,
        websim_talent_import_response,
        talent_spell_display_description,
        talent_tree_sections,
        unique_text_list,
        unique_gear_candidates,
        unique_locale_preferences,
        websim_gear_community_templates,
        websim_gear_community_template_sync_state,
        websim_max_level,
        weapon_equipment_rule_payload,
    )

try:
    from .stat_weights_payload import (
        MPLUS_SCENARIOS,
        merge_stat_weight_section,
        scenario_blocked_payload,
        with_cache_freshness,
    )
except ImportError:
    from stat_weights_payload import (
        MPLUS_SCENARIOS,
        merge_stat_weight_section,
        scenario_blocked_payload,
        with_cache_freshness,
    )


def json_param(value):
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


PG_GEAR_PAYLOAD_CACHE = {}
PG_GEAR_PAYLOAD_CACHE_MAX = 80


def _pg_gear_payload_cache_get(fingerprint):
    if not fingerprint or fingerprint not in PG_GEAR_PAYLOAD_CACHE:
        return None
    payload = PG_GEAR_PAYLOAD_CACHE.pop(fingerprint)
    PG_GEAR_PAYLOAD_CACHE[fingerprint] = payload
    return copy.deepcopy(payload)


def _pg_gear_payload_cache_put(fingerprint, payload):
    if not fingerprint or not isinstance(payload, dict):
        return
    if fingerprint in PG_GEAR_PAYLOAD_CACHE:
        PG_GEAR_PAYLOAD_CACHE.pop(fingerprint)
    while len(PG_GEAR_PAYLOAD_CACHE) >= PG_GEAR_PAYLOAD_CACHE_MAX:
        PG_GEAR_PAYLOAD_CACHE.pop(next(iter(PG_GEAR_PAYLOAD_CACHE)))
    PG_GEAR_PAYLOAD_CACHE[fingerprint] = copy.deepcopy(payload)


def _datetime_value(value):
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _timestamp_expired(value, now=None):
    parsed = _datetime_value(value)
    if parsed is None:
        return False
    return parsed <= (now or datetime.now(timezone.utc))


def _json_value(value, fallback):
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed is not None else fallback


def _int_value(value, fallback=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _template_count_bucket(status):
    normalized = str(status or "blocked").strip() or "blocked"
    if normalized in {"verified", "complete"}:
        return "verified"
    if normalized in {"partial", "stale"}:
        return "partial"
    return "blocked"


ADMIN_GATE_QUEUE_STATUSES = {
    "partial",
    "stale",
    "blocked",
    "missing_credentials",
    "pending_official_audit",
    "source_reference",
}


def _admin_gate_queue_summary(rows):
    total = 0
    domain_counts = {}
    blocker_counts = {}
    for domain, status, row_blockers in rows:
        blockers = [str(item or "").strip() for item in (row_blockers or []) if str(item or "").strip()]
        if status not in ADMIN_GATE_QUEUE_STATUSES and not blockers:
            continue
        domain_key = str(domain or "unknown")
        total += 1
        domain_counts[domain_key] = domain_counts.get(domain_key, 0) + 1
        for blocker in blockers:
            blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1
    return {
        "count": total,
        "domainCounts": domain_counts,
        "topBlockers": [
            {"reason": reason, "count": count}
            for reason, count in sorted(blocker_counts.items(), key=lambda item: (-item[1], item[0]))[:8]
        ],
    }


class PostgresCacheStore:
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

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

    def save_sync_state(self, key, value, updated_at=""):
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return {"ok": False, "error": "missing_key"}
        timestamp = updated_at or utc_now()
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cache.websim_sync_state (id, state_json, updated_at)
                    VALUES (%s, %s::jsonb, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        state_json = EXCLUDED.state_json,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (normalized_key, json_param(value), timestamp),
                )
        return {"ok": True, "key": normalized_key, "updatedAt": timestamp}

    def get_sync_state(self, key):
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return {}
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT state_json, updated_at FROM cache.websim_sync_state
                    WHERE id = %s
                    """,
                    (normalized_key,),
                )
                row = cur.fetchone()
        if not row:
            return {}
        state = _json_value(row[0], {})
        if not isinstance(state, dict):
            state = {}
        state["updatedAt"] = str(row[1] or "")
        return state

    def save_raiderio_payload(self, payload):
        payload = payload if isinstance(payload, dict) else {}
        fetched_at = payload.get("checkedAt") or payload.get("updatedAt") or utc_now()
        expires_at = payload.get("expiresAt") or None
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cache.raiderio_cache (cache_key, payload_json, fetched_at, expires_at)
                    VALUES ('raiderio_payload_v1', %s::jsonb, %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE SET
                        payload_json = EXCLUDED.payload_json,
                        fetched_at = EXCLUDED.fetched_at,
                        expires_at = EXCLUDED.expires_at
                    """,
                    (json_param(payload), fetched_at, expires_at),
                )
        return {"ok": True, "cacheKey": "raiderio_payload_v1", "fetchedAt": fetched_at}

    def save_stat_weight_payload(self, payload):
        payload = payload if isinstance(payload, dict) else {}
        cache_key = ":".join(
            [
                slugify(payload.get("classKey"), ""),
                slugify(payload.get("specKey"), ""),
                str(payload.get("scenarioKey") or "").strip(),
            ]
        )
        if cache_key.count(":") != 2 or cache_key.startswith(":") or "::" in cache_key:
            return {"ok": False, "error": "invalid_stat_weight_cache_key"}
        status = payload.get("sourceStatus") or payload.get("status") or "blocked"
        computed_at = payload.get("checkedAt") or payload.get("updatedAt") or utc_now()
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cache.stat_weight_cache (cache_key, payload_json, computed_at, source_status)
                    VALUES (%s, %s::jsonb, %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE SET
                        payload_json = EXCLUDED.payload_json,
                        computed_at = EXCLUDED.computed_at,
                        source_status = EXCLUDED.source_status
                    """,
                    (cache_key, json_param(payload), computed_at, status),
                )
        return {"ok": True, "cacheKey": cache_key, "sourceStatus": status}

    def replace_websim_journal_data(self, data):
        data = data if isinstance(data, dict) else {}
        season = data.get("season") if isinstance(data.get("season"), dict) else {}
        instances = [item for item in (data.get("instances") or []) if isinstance(item, dict)]
        now = utc_now()
        season_id = str(season.get("seasonId") or season.get("id") or "active").strip() or "active"
        season_revision = str(season.get("seasonRevision") or season.get("revision") or season_id).strip() or season_id
        counts = {"dungeons": 0, "instances": 0, "encounters": 0, "items": 0, "loot": 0}
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE cache.websim_season_state SET active = FALSE WHERE active = TRUE")
                cur.execute(
                    """
                    INSERT INTO cache.websim_season_state (
                        key, season_id, season_label, season_revision, locale, data_status,
                        verified_at, expires_at, source_refs_json, payload_json, active, updated_at
                    ) VALUES ('active', %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, TRUE, %s)
                    ON CONFLICT (key) DO UPDATE SET
                        season_id = EXCLUDED.season_id,
                        season_label = EXCLUDED.season_label,
                        season_revision = EXCLUDED.season_revision,
                        locale = EXCLUDED.locale,
                        data_status = EXCLUDED.data_status,
                        verified_at = EXCLUDED.verified_at,
                        expires_at = EXCLUDED.expires_at,
                        source_refs_json = EXCLUDED.source_refs_json,
                        payload_json = EXCLUDED.payload_json,
                        active = TRUE,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        season_id,
                        season.get("seasonLabel") or season.get("label") or season_id,
                        season_revision,
                        season.get("locale") or DEFAULT_LOCALE,
                        season.get("dataStatus") or season.get("status") or "blocked",
                        season.get("verifiedAt") or None,
                        season.get("expiresAt") or None,
                        json_param(season.get("sourceRefs") or []),
                        json_param(season),
                        now,
                    ),
                )
                cur.execute("DELETE FROM cache.websim_loot")
                cur.execute("DELETE FROM cache.websim_encounters")
                cur.execute("DELETE FROM cache.websim_instances")
                cur.execute("DELETE FROM cache.websim_season_dungeons WHERE season_revision = %s", (season_revision,))
                for dungeon in [item for item in (season.get("dungeons") or []) if isinstance(item, dict)]:
                    dungeon_id = str(dungeon.get("dungeonId") or dungeon.get("id") or dungeon.get("instanceId") or "").strip()
                    instance_id = str(dungeon.get("instanceId") or dungeon.get("id") or "").strip()
                    if not dungeon_id and not instance_id:
                        continue
                    cur.execute(
                        """
                        INSERT INTO cache.websim_season_dungeons (
                            id, season_id, season_revision, dungeon_id, instance_id, name,
                            short_name, timer_seconds, payload_json, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            season_id = EXCLUDED.season_id,
                            season_revision = EXCLUDED.season_revision,
                            dungeon_id = EXCLUDED.dungeon_id,
                            instance_id = EXCLUDED.instance_id,
                            name = EXCLUDED.name,
                            short_name = EXCLUDED.short_name,
                            timer_seconds = EXCLUDED.timer_seconds,
                            payload_json = EXCLUDED.payload_json,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            f"{season_revision}:{dungeon_id or instance_id}",
                            season_id,
                            season_revision,
                            dungeon_id or instance_id,
                            instance_id or dungeon_id,
                            dungeon.get("name") or dungeon_id or instance_id,
                            dungeon.get("shortName") or dungeon.get("short_name") or "",
                            _int_value(dungeon.get("timerSeconds") or dungeon.get("timer_seconds")),
                            json_param(dungeon),
                            now,
                        ),
                    )
                    counts["dungeons"] += 1
                for instance in instances:
                    instance_id = str(instance.get("instanceId") or instance.get("id") or "").strip()
                    if not instance_id:
                        continue
                    cur.execute(
                        """
                        INSERT INTO cache.websim_instances (id, name, category, payload_json, updated_at)
                        VALUES (%s, %s, %s, %s::jsonb, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            name = EXCLUDED.name,
                            category = EXCLUDED.category,
                            payload_json = EXCLUDED.payload_json,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            instance_id,
                            instance.get("name") or f"Instance {instance_id}",
                            instance.get("category") or "Dungeon",
                            json_param(instance),
                            now,
                        ),
                    )
                    counts["instances"] += 1
                    encounters = [item for item in (instance.get("encounters") or []) if isinstance(item, dict)]
                    for encounter in encounters:
                        encounter_id = str(encounter.get("encounterId") or encounter.get("id") or "").strip()
                        if not encounter_id:
                            continue
                        cur.execute(
                            """
                            INSERT INTO cache.websim_encounters (id, instance_id, name, payload_json, updated_at)
                            VALUES (%s, %s, %s, %s::jsonb, %s)
                            ON CONFLICT (id) DO UPDATE SET
                                instance_id = EXCLUDED.instance_id,
                                name = EXCLUDED.name,
                                payload_json = EXCLUDED.payload_json,
                                updated_at = EXCLUDED.updated_at
                            """,
                            (
                                encounter_id,
                                instance_id,
                                encounter.get("name") or f"Encounter {encounter_id}",
                                json_param(encounter),
                                now,
                            ),
                        )
                        counts["encounters"] += 1
                        for item in [value for value in (encounter.get("items") or []) if isinstance(value, dict)]:
                            item_id = str(item.get("itemId") or item.get("id") or "").strip()
                            if not item_id:
                                continue
                            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
                            item_level = _int_value(item.get("itemLevel") or payload.get("item_level") or payload.get("level"))
                            cur.execute(
                                """
                                INSERT INTO cache.websim_items (id, name, slot, item_level, payload_json, source_status, updated_at)
                                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                                ON CONFLICT (id) DO UPDATE SET
                                    name = EXCLUDED.name,
                                    slot = EXCLUDED.slot,
                                    item_level = EXCLUDED.item_level,
                                    payload_json = EXCLUDED.payload_json,
                                    source_status = EXCLUDED.source_status,
                                    updated_at = EXCLUDED.updated_at
                                """,
                                (
                                    item_id,
                                    item.get("name") or f"Item {item_id}",
                                    normalize_slot(item.get("slot") or payload.get("slot") or payload.get("inventoryType") or ""),
                                    item_level or None,
                                    json_param({**payload, "quality": item.get("quality") or "", "iconUrl": item.get("iconUrl") or ""}),
                                    item.get("sourceStatus") or item.get("metadataStatus") or "verified",
                                    now,
                                ),
                            )
                            counts["items"] += 1
                            loot_id = str(item.get("lootId") or item.get("id") or f"{instance_id}:{encounter_id}:{item_id}")
                            cur.execute(
                                """
                                INSERT INTO cache.websim_loot (
                                    id, instance_id, encounter_id, item_id, name, slot,
                                    quality, icon_url, payload_json, updated_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                                ON CONFLICT (id) DO UPDATE SET
                                    instance_id = EXCLUDED.instance_id,
                                    encounter_id = EXCLUDED.encounter_id,
                                    item_id = EXCLUDED.item_id,
                                    name = EXCLUDED.name,
                                    slot = EXCLUDED.slot,
                                    quality = EXCLUDED.quality,
                                    icon_url = EXCLUDED.icon_url,
                                    payload_json = EXCLUDED.payload_json,
                                    updated_at = EXCLUDED.updated_at
                                """,
                                (
                                    loot_id,
                                    instance_id,
                                    encounter_id,
                                    item_id,
                                    item.get("name") or f"Item {item_id}",
                                    normalize_slot(item.get("slot") or payload.get("slot") or ""),
                                    item.get("quality") or "",
                                    item.get("iconUrl") or "",
                                    json_param(item),
                                    now,
                                ),
                            )
                            counts["loot"] += 1
        return counts

    def _deterministic_uuid(self, kind, value):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"wow-mini-program:{kind}:{value}"))

    def rebuild_websim_gear_catalog_from_loot(self, season=None):
        season = season if isinstance(season, dict) else {}
        season_revision = season.get("seasonRevision") or season.get("revision") or ""
        now = utc_now()
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT l.id, l.item_id, l.slot, l.name, l.instance_id, COALESCE(i.name, ''),
                           COALESCE(i.category, ''), l.encounter_id, COALESCE(e.name, '')
                    FROM cache.websim_loot l
                    LEFT JOIN cache.websim_instances i ON i.id = l.instance_id
                    LEFT JOIN cache.websim_encounters e ON e.id = l.encounter_id
                    ORDER BY i.name, e.name, l.name
                    """
                )
                rows = cur.fetchall()
                cur.execute("DELETE FROM cache.websim_gear_sources WHERE source_key LIKE 'loot:%'")
                cur.execute(
                    """
                    DELETE FROM cache.websim_gear_variants
                    WHERE variant_key = 'needs-variant'
                      AND COALESCE(payload_json->>'sourceKey', '') LIKE 'loot:%'
                    """
                )
                item_ids = set()
                variant_keys = set()
                source_count = 0
                for row in rows:
                    loot_id = str(row[0] or "")
                    item_id = str(row[1] or "")
                    if not loot_id or not item_id:
                        continue
                    source_count += 1
                    source_type = "raid" if str(row[6] or "").lower() == "raid" else "dungeon"
                    label = " - ".join([part for part in [row[8], row[5]] if part]) or row[3] or "Official loot"
                    source_key = f"loot:{loot_id}"
                    difficulty_key = "needs-variant"
                    source_payload = {
                        "sourceKey": source_key,
                        "sourceType": source_type,
                        "sourceLabel": label,
                        "instanceId": row[4] or "",
                        "encounterId": row[7] or "",
                        "difficultyKey": difficulty_key,
                        "seasonRevision": season_revision,
                        "sourceStatus": "verified",
                    }
                    cur.execute(
                        """
                        INSERT INTO cache.websim_gear_sources (
                            id, item_id, source_type, source_key, source_label, instance_id,
                            encounter_id, difficulty_key, season_revision, payload_json, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            item_id = EXCLUDED.item_id,
                            source_type = EXCLUDED.source_type,
                            source_key = EXCLUDED.source_key,
                            source_label = EXCLUDED.source_label,
                            instance_id = EXCLUDED.instance_id,
                            encounter_id = EXCLUDED.encounter_id,
                            difficulty_key = EXCLUDED.difficulty_key,
                            season_revision = EXCLUDED.season_revision,
                            payload_json = EXCLUDED.payload_json,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            self._deterministic_uuid("gear-source", source_key),
                            item_id,
                            source_type,
                            source_key,
                            label,
                            row[4] or "",
                            row[7] or "",
                            difficulty_key,
                            season_revision,
                            json_param(source_payload),
                            now,
                        ),
                    )
                    slot = normalize_slot(row[2] or "")
                    blockers = ["missing deterministic SimC variant preset"]
                    variant_payload = {
                        **source_payload,
                        "slot": slot,
                        "itemName": row[3] or "",
                        "variantKey": "needs-variant",
                        "difficultyKey": difficulty_key,
                        "itemLevel": 0,
                        "status": "partial",
                        "blockers": blockers,
                    }
                    cur.execute(
                        """
                        INSERT INTO cache.websim_gear_variants (
                            id, item_id, variant_key, readiness, slot, label, source_type,
                            difficulty_key, item_level, simc_options_json, status, blockers_json,
                            payload_json, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s::jsonb, %s)
                        ON CONFLICT (item_id, variant_key) DO UPDATE SET
                            readiness = EXCLUDED.readiness,
                            slot = EXCLUDED.slot,
                            label = EXCLUDED.label,
                            source_type = EXCLUDED.source_type,
                            difficulty_key = EXCLUDED.difficulty_key,
                            item_level = EXCLUDED.item_level,
                            simc_options_json = EXCLUDED.simc_options_json,
                            status = EXCLUDED.status,
                            blockers_json = EXCLUDED.blockers_json,
                            payload_json = EXCLUDED.payload_json,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            self._deterministic_uuid("gear-variant", f"{source_key}:needs-variant"),
                            item_id,
                            "needs-variant",
                            "partial",
                            slot,
                            row[3] or "Needs variant",
                            source_type,
                            difficulty_key,
                            0,
                            json_param({}),
                            "partial",
                            json_param(blockers),
                            json_param(variant_payload),
                            now,
                        ),
                    )
                    item_ids.add(item_id)
                    variant_keys.add((item_id, "needs-variant"))
        has_sources = source_count > 0
        variant_count = len(variant_keys)
        state = {
            "runner": "postgres",
            "status": "partial" if has_sources else "blocked",
            "checkedAt": now,
            "schemaRevision": GEAR_CATALOG_REVISION,
            "itemCount": len(item_ids),
            "sourceCount": source_count,
            "variantCount": variant_count,
            "verifiedCount": 0,
            "partialCount": variant_count,
            "blockedCount": 0,
            "blockers": [] if has_sources else ["PostgreSQL WebSim loot cache is empty"],
            "dataReadiness": {
                "status": "partial" if has_sources else "blocked",
                "sourceStatus": "verified" if has_sources else "blocked",
                "variantStatus": "partial" if has_sources else "blocked",
                "blockers": [] if has_sources else ["PostgreSQL WebSim loot cache is empty"],
            },
        }
        self.save_sync_state("gearCatalog", state, now)
        return state

    def replace_simc_generated_data(self, data):
        data = data if isinstance(data, dict) else {}
        talents = [item for item in (data.get("talents") or []) if isinstance(item, dict)]
        presets = [item for item in (data.get("presets") or []) if isinstance(item, dict)]
        spell_details = [item for item in (data.get("spellDetails") or []) if isinstance(item, dict)]
        now = utc_now()
        with self.connection() as conn:
            with conn.cursor() as cur:
                if data.get("source"):
                    cur.execute("DELETE FROM cache.websim_talents")
                    cur.execute("DELETE FROM cache.websim_profile_presets")
                for talent in talents:
                    payload = dict(talent.get("payload") or talent)
                    cur.execute(
                        """
                        INSERT INTO cache.websim_talents (
                            id, class_key, spec_key, tree_id, row_index, col_index,
                            spell_id, name, payload_json, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            class_key = EXCLUDED.class_key,
                            spec_key = EXCLUDED.spec_key,
                            tree_id = EXCLUDED.tree_id,
                            row_index = EXCLUDED.row_index,
                            col_index = EXCLUDED.col_index,
                            spell_id = EXCLUDED.spell_id,
                            name = EXCLUDED.name,
                            payload_json = EXCLUDED.payload_json,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            str(talent.get("id") or ""),
                            talent.get("classKey") or "",
                            talent.get("specKey") or "",
                            talent.get("treeId") or "",
                            _int_value(talent.get("row")),
                            _int_value(talent.get("col")),
                            _int_value(talent.get("spellId")),
                            talent.get("name") or "",
                            json_param(payload),
                            now,
                        ),
                    )
                for preset in presets:
                    payload = {key: value for key, value in preset.items() if key != "profile"}
                    cur.execute(
                        """
                        INSERT INTO cache.websim_profile_presets (
                            id, class_key, spec_key, name, profile, payload_json, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            class_key = EXCLUDED.class_key,
                            spec_key = EXCLUDED.spec_key,
                            name = EXCLUDED.name,
                            profile = EXCLUDED.profile,
                            payload_json = EXCLUDED.payload_json,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            str(preset.get("id") or ""),
                            preset.get("classKey") or "",
                            preset.get("specKey") or "",
                            preset.get("name") or "",
                            preset.get("profile") or "",
                            json_param(payload),
                            now,
                        ),
                    )
                for detail in spell_details:
                    spell_id = _int_value(detail.get("spellId"))
                    if spell_id <= 0:
                        continue
                    payload = {
                        "source": detail.get("source") or "simulationcraft",
                        "spellId": spell_id,
                        "rank": detail.get("rank") or "",
                        "tooltip": detail.get("tooltip") or "",
                        "spellTextSource": data.get("spellTextSource") or "",
                        "spellLocalizationSource": data.get("spellLocalizationSource") or "",
                    }
                    cur.execute(
                        """
                        INSERT INTO cache.websim_spell_details (
                            id, spell_id, name, description, icon_url, locale, payload_json, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            name = CASE
                                WHEN cache.websim_spell_details.name = ''
                                  OR COALESCE(cache.websim_spell_details.payload_json->>'source', '') = 'simulationcraft'
                                THEN EXCLUDED.name
                                ELSE cache.websim_spell_details.name
                            END,
                            description = CASE
                                WHEN cache.websim_spell_details.description = ''
                                  OR COALESCE(cache.websim_spell_details.payload_json->>'source', '') = 'simulationcraft'
                                THEN EXCLUDED.description
                                ELSE cache.websim_spell_details.description
                            END,
                            icon_url = CASE
                                WHEN cache.websim_spell_details.icon_url = ''
                                  OR COALESCE(cache.websim_spell_details.payload_json->>'source', '') = 'simulationcraft'
                                THEN EXCLUDED.icon_url
                                ELSE cache.websim_spell_details.icon_url
                            END,
                            locale = CASE
                                WHEN COALESCE(cache.websim_spell_details.payload_json->>'source', '') = 'simulationcraft'
                                THEN EXCLUDED.locale
                                ELSE cache.websim_spell_details.locale
                            END,
                            payload_json = CASE
                                WHEN cache.websim_spell_details.description = ''
                                  OR COALESCE(cache.websim_spell_details.payload_json->>'source', '') = 'simulationcraft'
                                THEN EXCLUDED.payload_json
                                ELSE cache.websim_spell_details.payload_json
                            END,
                            updated_at = CASE
                                WHEN cache.websim_spell_details.description = ''
                                  OR COALESCE(cache.websim_spell_details.payload_json->>'source', '') = 'simulationcraft'
                                THEN EXCLUDED.updated_at
                                ELSE cache.websim_spell_details.updated_at
                            END
                        """,
                        (
                            str(spell_id),
                            spell_id,
                            detail.get("name") or "",
                            detail.get("description") or "",
                            detail.get("iconUrl") or "",
                            detail.get("locale") or "en_US",
                            json_param(payload),
                            now,
                        ),
                    )
        return {
            "talents": len(talents),
            "profiles": len(presets),
            "presets": len(presets),
            "spellDetails": len(spell_details),
            "spellIcons": int(data.get("spellIcons") or 0),
            "spellLocalizations": int(data.get("spellLocalizations") or 0),
            "dependencies": int(data.get("dependencies") or 0),
            "build": data.get("build") or "",
            "source": data.get("source") or "",
            "spellTextSource": data.get("spellTextSource") or "",
            "spellIconSource": data.get("spellIconSource") or "",
            "spellLocalizationSource": data.get("spellLocalizationSource") or "",
            "traitEdgeSource": data.get("traitEdgeSource") or "",
        }

    def _status_counts(self, table_name):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT status, COUNT(*)
                    FROM {table_name}
                    WHERE expires_at IS NULL OR expires_at > now()
                    GROUP BY status
                    """
                )
                rows = cur.fetchall()
        counts = {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        for status, count in rows:
            normalized = _template_count_bucket(status)
            value = _int_value(count)
            counts["total"] += value
            counts[normalized] = counts.get(normalized, 0) + value
        return counts

    def community_talent_template_counts(self):
        return self._status_counts("cache.websim_community_talent_templates")

    def community_gear_template_counts(self):
        return self._status_counts("cache.websim_community_gear_templates")

    def replace_community_talent_templates(self, templates, scan_run_id=""):
        counts = {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        normalized_rows = []
        for template in templates or []:
            if not isinstance(template, dict):
                continue
            normalized = normalize_community_talent_template(
                {
                    **template,
                    "scanRunId": template.get("scanRunId") or scan_run_id,
                },
                template.get("sourceKey", "manual_fixture"),
                template.get("sourceStatus", "partial"),
            )
            payload = dict(normalized.get("payload") or {})
            payload.setdefault("legacyId", normalized["id"])
            normalized["payload"] = payload
            bucket = _template_count_bucket(normalized.get("status"))
            counts["total"] += 1
            counts[bucket] += 1
            normalized_rows.append(normalized)
        if not normalized_rows:
            return counts
        with self.connection() as conn:
            with conn.cursor() as cur:
                for normalized in normalized_rows:
                    cur.execute(
                        """
                        INSERT INTO cache.websim_community_talent_templates (
                            id, class_key, spec_key, source_key, payload_json, updated_at,
                            hero_key, scenario_key, name, flow_label, source_name, source_url,
                            raw_import_code, websim_export_code, talent_state_json,
                            sample_count, max_key_level, analysis_window, source_status,
                            status, expires_at, signature, source_refs_json, scan_run_id
                        ) VALUES (
                            %s, %s, %s, %s, %s::jsonb, %s,
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s::jsonb,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s::jsonb, %s
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            class_key = EXCLUDED.class_key,
                            spec_key = EXCLUDED.spec_key,
                            source_key = EXCLUDED.source_key,
                            payload_json = EXCLUDED.payload_json,
                            updated_at = EXCLUDED.updated_at,
                            hero_key = EXCLUDED.hero_key,
                            scenario_key = EXCLUDED.scenario_key,
                            name = EXCLUDED.name,
                            flow_label = EXCLUDED.flow_label,
                            source_name = EXCLUDED.source_name,
                            source_url = EXCLUDED.source_url,
                            raw_import_code = EXCLUDED.raw_import_code,
                            websim_export_code = EXCLUDED.websim_export_code,
                            talent_state_json = EXCLUDED.talent_state_json,
                            sample_count = EXCLUDED.sample_count,
                            max_key_level = EXCLUDED.max_key_level,
                            analysis_window = EXCLUDED.analysis_window,
                            source_status = EXCLUDED.source_status,
                            status = EXCLUDED.status,
                            expires_at = EXCLUDED.expires_at,
                            signature = EXCLUDED.signature,
                            source_refs_json = EXCLUDED.source_refs_json,
                            scan_run_id = EXCLUDED.scan_run_id
                        """,
                        (
                            self._deterministic_uuid("community-talent-template", normalized["id"]),
                            normalized["classKey"],
                            normalized["specKey"],
                            normalized["sourceKey"],
                            json_param(normalized["payload"]),
                            normalized["updatedAt"],
                            normalized["heroKey"],
                            normalized["scenarioKey"],
                            normalized["name"],
                            normalized["flowLabel"],
                            normalized["sourceName"],
                            normalized["sourceUrl"],
                            normalized["rawImportCode"],
                            normalized["websimExportCode"],
                            json_param(normalized["talentState"]),
                            normalized["sampleCount"],
                            normalized["maxKeyLevel"],
                            normalized["analysisWindow"],
                            normalized["sourceStatus"],
                            normalized["status"],
                            normalized["expiresAt"] or None,
                            normalized["signature"],
                            json_param(normalized["sourceRefs"]),
                            normalized["scanRunId"],
                        ),
                    )
        return counts

    def replace_community_gear_templates(self, templates, scan_run_id=""):
        counts = {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        normalized_rows = []
        for template in templates or []:
            if not isinstance(template, dict):
                continue
            normalized = normalize_community_gear_template(
                {
                    **template,
                    "scanRunId": template.get("scanRunId") or scan_run_id,
                }
            )
            bucket = _template_count_bucket(normalized.get("status"))
            counts["total"] += 1
            counts[bucket] += 1
            normalized_rows.append(normalized)
        if not normalized_rows:
            return counts
        with self.connection() as conn:
            with conn.cursor() as cur:
                for normalized in normalized_rows:
                    cur.execute(
                        """
                        INSERT INTO cache.websim_community_gear_templates (
                            id, class_key, spec_key, name, source_key, source_name, source_url,
                            source_status, status, signature, source_refs_json, gear_items_json,
                            raw_string, ready_slot_count, missing_slots_json, analysis_window,
                            payload_json, updated_at, expires_at, scan_run_id
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s::jsonb, %s::jsonb,
                            %s, %s, %s::jsonb, %s,
                            %s::jsonb, %s, %s, %s
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            class_key = EXCLUDED.class_key,
                            spec_key = EXCLUDED.spec_key,
                            name = EXCLUDED.name,
                            source_key = EXCLUDED.source_key,
                            source_name = EXCLUDED.source_name,
                            source_url = EXCLUDED.source_url,
                            source_status = EXCLUDED.source_status,
                            status = EXCLUDED.status,
                            signature = EXCLUDED.signature,
                            source_refs_json = EXCLUDED.source_refs_json,
                            gear_items_json = EXCLUDED.gear_items_json,
                            raw_string = EXCLUDED.raw_string,
                            ready_slot_count = EXCLUDED.ready_slot_count,
                            missing_slots_json = EXCLUDED.missing_slots_json,
                            analysis_window = EXCLUDED.analysis_window,
                            payload_json = EXCLUDED.payload_json,
                            updated_at = EXCLUDED.updated_at,
                            expires_at = EXCLUDED.expires_at,
                            scan_run_id = EXCLUDED.scan_run_id
                        """,
                        (
                            normalized["id"],
                            normalized["classKey"],
                            normalized["specKey"],
                            normalized["name"],
                            normalized["sourceKey"],
                            normalized["sourceName"],
                            normalized["sourceUrl"],
                            normalized["sourceStatus"],
                            normalized["status"],
                            normalized["signature"],
                            json_param(normalized["sourceRefs"]),
                            json_param(normalized["gearItems"]),
                            normalized["rawString"],
                            normalized["readySlotCount"],
                            json_param(normalized["missingSlots"]),
                            normalized["analysisWindow"],
                            json_param(normalized["payload"]),
                            normalized["updatedAt"],
                            normalized["expiresAt"] or None,
                            normalized["scanRunId"],
                        ),
                    )
        return counts

    def build_community_gear_templates(self, scan_run_id=""):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, class_key, spec_key, name, profile, payload_json, updated_at
                    FROM cache.websim_profile_presets
                    WHERE spec_key != 'class'
                    ORDER BY class_key, spec_key, name
                    LIMIT 800
                    """
                )
                rows = cur.fetchall()
        presets_by_spec = {}
        for row in rows:
            class_key = slugify(row[1], "")
            spec_key = slugify(row[2], "")
            if not class_key or not spec_key:
                continue
            presets_by_spec.setdefault((class_key, spec_key), []).append(
                {
                    "id": row[0],
                    "classKey": class_key,
                    "specKey": spec_key,
                    "name": row[3],
                    "profile": row[4],
                    "payload": _json_value(row[5], {}),
                    "updatedAt": str(row[6] or ""),
                }
            )
        templates = []
        for (class_key, spec_key), presets in presets_by_spec.items():
            for template in websim_gear_community_templates(presets, class_key, spec_key):
                templates.append({**template, "scanRunId": scan_run_id})
        return dedupe_gear_community_templates(templates)

    def _backfill_simc_options(self, item, item_level):
        options = {}
        if item_level:
            options["ilevel"] = str(item_level)
        for key in ("bonus_id", "gem_id", "gem_bonus_id", "gem_ilevel", "enchant_id", "crafted_stats", "embellishment"):
            value = item.get(key) or item.get(key.replace("_", ""))
            if value not in (None, "", [], {}):
                options[key] = str(value)
        return options

    def _write_backfill_gear_rows(self, rows):
        counts = {"itemCount": 0, "sourceCount": 0, "variantCount": 0, "partialCount": 0, "blockedCount": 0, "errors": []}
        prepared = []
        seen_variants = set()
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            item_id = str(row.get("itemId") or row.get("item_id") or row.get("id") or "").strip()
            slot = normalize_slot(row.get("slot") or row.get("simcSlot") or "")
            try:
                item_level = int(row.get("itemLevel") or row.get("ilevel") or 0)
            except (TypeError, ValueError):
                item_level = 0
            source_type = str(row.get("sourceType") or "").strip()
            if not item_id or not slot or not item_level or not source_type:
                counts["blockedCount"] += 1
                counts["errors"].append(f"skipped backfill item missing required fields: {item_id or 'unknown'}")
                continue
            simc_options = self._backfill_simc_options(row, item_level)
            status = "verified" if len(simc_options) > 1 else "partial"
            if status == "partial":
                counts["partialCount"] += 1
            difficulty_key = str(row.get("difficultyKey") or source_type).strip()
            variant_key = str(row.get("variantKey") or f"{difficulty_key}-{slot}-{item_level}-{json_param(simc_options)}")
            variant_identity = (item_id, variant_key)
            if variant_identity in seen_variants:
                continue
            seen_variants.add(variant_identity)
            prepared.append(
                {
                    **row,
                    "itemId": item_id,
                    "slot": slot,
                    "itemLevel": item_level,
                    "sourceType": source_type,
                    "sourceKey": str(row.get("sourceKey") or f"{source_type}:{item_id}:{slot}").strip(),
                    "sourceLabel": str(row.get("sourceLabel") or row.get("sourceName") or source_type).strip(),
                    "difficultyKey": difficulty_key,
                    "variantKey": variant_key,
                    "status": str(row.get("status") or status).strip(),
                    "simcOptions": simc_options,
                }
            )
        if not prepared:
            counts["sourceStatus"] = "blocked"
            counts["status"] = "blocked"
            if not counts["errors"]:
                counts["errors"].append("no PG-native gear backfill rows were eligible")
            return counts
        now = utc_now()
        with self.connection() as conn:
            with conn.cursor() as cur:
                for row in prepared:
                    item_id = row["itemId"]
                    item_level = row["itemLevel"]
                    source_type = row["sourceType"]
                    status = row["status"]
                    source_key = row["sourceKey"]
                    variant_key = row["variantKey"]
                    cur.execute(
                        """
                        INSERT INTO cache.websim_items (id, name, slot, item_level, payload_json, source_status, updated_at)
                        VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            name = COALESCE(NULLIF(EXCLUDED.name, ''), cache.websim_items.name),
                            slot = COALESCE(NULLIF(EXCLUDED.slot, ''), cache.websim_items.slot),
                            item_level = COALESCE(EXCLUDED.item_level, cache.websim_items.item_level),
                            payload_json = EXCLUDED.payload_json,
                            source_status = EXCLUDED.source_status,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            item_id,
                            row.get("name") or row.get("itemName") or f"Item {item_id}",
                            row["slot"],
                            item_level,
                            json_param(row),
                            status,
                            now,
                        ),
                    )
                    cur.execute(
                        """
                        INSERT INTO cache.websim_gear_sources (
                            id, item_id, source_type, source_key, payload_json, updated_at,
                            source_label, instance_id, encounter_id, difficulty_key, season_revision
                        ) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            source_type = EXCLUDED.source_type,
                            source_key = EXCLUDED.source_key,
                            payload_json = EXCLUDED.payload_json,
                            updated_at = EXCLUDED.updated_at,
                            source_label = EXCLUDED.source_label,
                            instance_id = EXCLUDED.instance_id,
                            encounter_id = EXCLUDED.encounter_id,
                            difficulty_key = EXCLUDED.difficulty_key,
                            season_revision = EXCLUDED.season_revision
                        """,
                        (
                            self._deterministic_uuid("gear-backfill-source", f"{source_type}:{source_key}"),
                            item_id,
                            source_type,
                            source_key,
                            json_param(row),
                            now,
                            row["sourceLabel"],
                            row.get("instanceId") or "",
                            row.get("encounterId") or "",
                            row["difficultyKey"],
                            row.get("seasonRevision") or "",
                        ),
                    )
                    cur.execute(
                        """
                        INSERT INTO cache.websim_gear_variants (
                            id, item_id, variant_key, readiness, payload_json, updated_at,
                            slot, label, source_type, difficulty_key, item_level,
                            simc_options_json, status, blockers_json
                        ) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb)
                        ON CONFLICT (item_id, variant_key) DO UPDATE SET
                            readiness = EXCLUDED.readiness,
                            payload_json = EXCLUDED.payload_json,
                            updated_at = EXCLUDED.updated_at,
                            slot = EXCLUDED.slot,
                            label = EXCLUDED.label,
                            source_type = EXCLUDED.source_type,
                            difficulty_key = EXCLUDED.difficulty_key,
                            item_level = EXCLUDED.item_level,
                            simc_options_json = EXCLUDED.simc_options_json,
                            status = EXCLUDED.status,
                            blockers_json = EXCLUDED.blockers_json
                        """,
                        (
                            self._deterministic_uuid("gear-backfill-variant", f"{item_id}:{variant_key}"),
                            item_id,
                            variant_key,
                            status,
                            json_param(row),
                            now,
                            row["slot"],
                            row.get("label") or row.get("name") or f"{source_type} {item_id}",
                            source_type,
                            row["difficultyKey"],
                            item_level,
                            json_param(row["simcOptions"]),
                            status,
                            json_param(row.get("blockers") or []),
                        ),
                    )
                    counts["itemCount"] += 1
                    counts["sourceCount"] += 1
                    counts["variantCount"] += 1
        counts["sourceStatus"] = "partial" if counts["partialCount"] or counts["blockedCount"] else "verified"
        counts["status"] = counts["sourceStatus"]
        return counts

    def backfill_observed_gear_from_raiderio(self, raiderio_payload, mode="scheduled"):
        rows = []
        profile_count = 0
        for profile in (raiderio_payload or {}).get("profiles") or []:
            if not isinstance(profile, dict):
                continue
            profile_count += 1
            profile_ref = profile.get("profileUrl") or profile.get("url") or profile.get("name") or ""
            for item in profile.get("gear") or []:
                if not isinstance(item, dict):
                    continue
                rows.append(
                    {
                        **item,
                        "sourceType": "observed_profile",
                        "difficultyKey": "observed_profile",
                        "sourceKey": f"observed:{profile_ref}:{item.get('itemId') or item.get('id')}",
                        "sourceLabel": f"Raider.IO observed profile: {profile.get('name') or 'profile'}",
                        "profileUrl": profile.get("profileUrl") or "",
                        "classKey": profile.get("classKey") or item.get("classKey") or "",
                        "specKey": profile.get("specKey") or item.get("specKey") or "",
                    }
                )
        result = self._write_backfill_gear_rows(rows)
        result["runner"] = "postgres"
        result["mode"] = mode
        result["observedProfileCount"] = profile_count
        return result

    def backfill_crafted_gear_from_seed(self, items, mode="scheduled"):
        rows = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            item_level = item.get("itemLevel") or item.get("ilevel") or 0
            crafted_stats = item.get("crafted_stats") or item.get("craftedStats") or ""
            rows.append(
                {
                    **item,
                    "itemLevel": item_level,
                    "crafted_stats": crafted_stats,
                    "sourceType": "crafted",
                    "difficultyKey": item.get("difficultyKey") or "crafted_myth",
                    "sourceKey": f"crafted:{item.get('itemId') or item.get('id')}:{item_level}:{crafted_stats}",
                    "sourceLabel": item.get("sourceLabel") or "PG-native crafted gear seed",
                    "variantKey": item.get("variantKey") or f"crafted-{item_level}-{crafted_stats or 'fixed'}",
                }
            )
        result = self._write_backfill_gear_rows(rows)
        result["runner"] = "postgres"
        result["mode"] = mode
        result["seedItemCount"] = len(items or [])
        return result

    def get_raiderio_payload(self):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT payload_json, fetched_at, expires_at
                    FROM cache.raiderio_cache
                    WHERE cache_key = 'raiderio_payload_v1'
                    LIMIT 1
                    """
                )
                row = cur.fetchone()
        if not row:
            return {
                "sourceStatus": "blocked",
                "status": "blocked",
                "errors": ["PostgreSQL Raider.IO cache is missing"],
            }
        payload = _json_value(row[0], {})
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("checkedAt", str(row[1] or ""))
        payload.setdefault("updatedAt", str(row[1] or ""))
        payload.setdefault("expiresAt", str(row[2] or ""))
        payload.setdefault("sourceStatus", payload.get("status") or "blocked")
        return payload

    def get_stat_weight_payload(self, class_key, spec_key, scenario_key):
        cache_key = f"{slugify(class_key, '')}:{slugify(spec_key, '')}:{str(scenario_key or '').strip()}"
        if cache_key.count(":") != 2 or cache_key.startswith(":") or "::" in cache_key:
            return None
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT payload_json, source_status, computed_at
                    FROM cache.stat_weight_cache
                    WHERE cache_key = %s
                    LIMIT 1
                    """,
                    (cache_key,),
                )
                row = cur.fetchone()
        if not row:
            return None
        payload = _json_value(row[0], {})
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("classKey", slugify(class_key, ""))
        payload.setdefault("specKey", slugify(spec_key, ""))
        payload.setdefault("scenarioKey", scenario_key)
        payload.setdefault("sourceStatus", row[1] or payload.get("status") or "blocked")
        payload.setdefault("status", payload.get("sourceStatus") or "blocked")
        payload.setdefault("checkedAt", str(row[2] or ""))
        payload.setdefault("updatedAt", str(row[2] or ""))
        return payload

    def latest_stat_weight_run_payload(self):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT source_status, computed_at
                    FROM cache.stat_weight_cache
                    ORDER BY computed_at DESC
                    LIMIT 400
                    """
                )
                rows = cur.fetchall()
        if not rows:
            return {
                "refreshMode": "",
                "refreshedAt": "",
                "status": "blocked",
                "sourceStatus": "blocked",
                "acceptedCount": 0,
                "blockedCount": 0,
                "errors": ["PostgreSQL stat weight cache is empty"],
            }
        accepted_statuses = {"verified", "partial", "stale"}
        accepted = sum(1 for row in rows if str(row[0] or "").strip() in accepted_statuses)
        blocked = len(rows) - accepted
        status = "verified" if accepted and not blocked else ("partial" if accepted else "blocked")
        latest = max((str(row[1] or "") for row in rows), default="")
        return {
            "refreshMode": "postgres_cache",
            "refreshedAt": latest,
            "status": status,
            "sourceStatus": status,
            "acceptedCount": accepted,
            "blockedCount": blocked,
            "specCount": 0,
            "scenarioCount": len(rows),
            "errors": [],
        }

    def enrich_builds_detail_stat_weights(self, payload):
        if not isinstance(payload, dict):
            return payload
        details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
        if "statWeights" not in details:
            return payload
        existing = details.get("statWeights") if isinstance(details.get("statWeights"), dict) else {}
        class_key = payload.get("websimClassKey") or payload.get("classKey") or ""
        spec_key = payload.get("websimSpecKey") or payload.get("specKey") or ""
        if not class_key or not spec_key:
            return payload
        scenario_payloads = []
        for scenario in MPLUS_SCENARIOS:
            cached = with_cache_freshness(self.get_stat_weight_payload(class_key, spec_key, scenario["key"]))
            scenario_payloads.append(cached or scenario_blocked_payload(class_key, spec_key, scenario, "PostgreSQL stat weight cache is empty"))
        next_details = dict(details)
        next_details["statWeights"] = merge_stat_weight_section(existing, scenario_payloads)
        result = dict(payload)
        result["details"] = next_details
        return result

    def get_active_season_payload(self):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT season_id, season_label, season_revision, locale, data_status, verified_at,
                           expires_at, source_refs_json, payload_json
                    FROM cache.websim_season_state
                    WHERE key = 'active'
                      AND active = TRUE
                      AND data_status = 'verified'
                    LIMIT 1
                    """
                )
                row = cur.fetchone()
                if not row:
                    return {}
                payload = _json_value(row[8], {})
                if not isinstance(payload, dict) or not payload.get("seasonRevision"):
                    payload = current_season_payload(
                        season_id=row[0],
                        season_label=row[1],
                        locale=row[3] or DEFAULT_LOCALE,
                        dungeons=[],
                        data_status=row[4],
                        verified_at=str(row[5] or ""),
                        expires_at=str(row[6] or ""),
                        source_refs=_json_value(row[7], []),
                    )
                payload["seasonId"] = row[0]
                payload["id"] = row[0]
                payload["seasonLabel"] = row[1]
                payload["label"] = row[1]
                payload["seasonRevision"] = row[2]
                payload["revision"] = row[2]
                payload["locale"] = row[3] or DEFAULT_LOCALE
                expired = bool(_datetime_value(row[6]) and _datetime_value(row[6]) <= datetime.now(timezone.utc))
                payload["dataStatus"] = "stale" if expired else row[4]
                payload["verifiedAt"] = str(row[5] or "")
                payload["expiresAt"] = str(row[6] or "")
                payload["sourceRefs"] = _json_value(row[7], [])
                if expired:
                    errors = payload.get("errors") if isinstance(payload.get("errors"), list) else []
                    payload["errors"] = [*errors, "season cache expired"]
                cur.execute(
                    """
                    SELECT dungeon_id, instance_id, name, short_name, timer_seconds, payload_json
                    FROM cache.websim_season_dungeons
                    WHERE season_revision = %s
                    ORDER BY name
                    """,
                    (row[2],),
                )
                dungeons = cur.fetchall()
        payload["dungeons"] = [
            {
                "id": dungeon_row[0],
                "dungeonId": dungeon_row[0],
                "instanceId": dungeon_row[1],
                "name": dungeon_row[2],
                "shortName": dungeon_row[3],
                "timerSeconds": dungeon_row[4],
                "sourceRefs": payload["sourceRefs"],
                "payload": _json_value(dungeon_row[5], {}),
            }
            for dungeon_row in dungeons
        ]
        normalize_current_season_raid_pool_payload(payload)
        return payload

    def get_websim_instances(self):
        season = self.get_active_season_payload()
        if season.get("dataStatus") != "verified":
            return []
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, category
                    FROM cache.websim_instances
                    ORDER BY name
                    """
                )
                rows = cur.fetchall()
                if not rows:
                    return []
                cur.execute(
                    """
                    SELECT id, instance_id, name
                    FROM cache.websim_encounters
                    ORDER BY name
                    """
                )
                encounter_rows = cur.fetchall()
        encounters = {}
        for row in encounter_rows:
            encounters.setdefault(row[1], []).append({"id": row[0], "instanceId": row[1], "name": row[2]})
        return [
            {"id": row[0], "name": row[1], "category": row[2], "encounters": encounters.get(row[0], [])}
            for row in rows
        ]

    def get_websim_default_selection(self):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT p.class_key, p.spec_key
                    FROM cache.websim_profile_presets p
                    WHERE p.spec_key != 'class'
                      AND EXISTS (
                        SELECT 1 FROM cache.websim_talents t
                        WHERE t.class_key = p.class_key
                          AND t.spec_key = p.spec_key
                      )
                    ORDER BY p.class_key, p.spec_key
                    LIMIT 1
                    """
                )
                row = cur.fetchone()
                if not row:
                    cur.execute(
                        """
                        SELECT class_key, spec_key, COUNT(*) AS node_count
                        FROM cache.websim_talents
                        WHERE spec_key != 'class'
                        GROUP BY class_key, spec_key
                        ORDER BY node_count DESC, class_key, spec_key
                        LIMIT 1
                        """
                    )
                    row = cur.fetchone()
        return {
            "classKey": row[0] if row else "mage",
            "specKey": row[1] if row else "arcane",
        }

    def get_websim_bootstrap(self):
        season = self.get_active_season_payload()
        season_fields = season_metadata_fields(season)
        return {
            "navTitle": "WebSim",
            "title": "SimC 构筑工坊",
            "region": "us",
            "locale": season_fields["locale"],
            "localeFallbacks": unique_locale_preferences(season_fields["locale"]),
            "classes": classes_payload(),
            "gearSlots": gear_slot_payload(),
            "scenarios": SCENARIOS,
            "instances": self.get_websim_instances(),
            "syncState": self.get_sync_state("websim_sync") or {"ok": False, "errors": ["PostgreSQL websim cache has not been synced"]},
            "defaultSelection": self.get_websim_default_selection(),
            "simcraftVersion": simc_version_payload(),
            **season_fields,
        }

    def get_websim_assets(self, filters=None):
        filters = filters or {}
        where = []
        params = []
        mapping = {
            "entityType": "entity_type",
            "entityId": "entity_id",
            "context": "context_key",
            "contextKey": "context_key",
            "status": "status",
            "source": "source",
        }
        for key, column in mapping.items():
            value = filters.get(key)
            if value in (None, ""):
                continue
            where.append(f"{column} = %s")
            params.append(str(value))
        try:
            limit = max(1, min(int(filters.get("limit") or 200), 1000))
        except (TypeError, ValueError):
            limit = 200
        query = """
            SELECT id, entity_type, entity_id, context_key, asset_type, icon_url, resolution_tier,
                   source, status, semantic_tags_json, usage_json, fallback_text, payload_json
            FROM cache.websim_asset_registry
        """
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY entity_type, entity_id, context_key LIMIT %s"
        try:
            with self.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, [*params, limit])
                    rows = cur.fetchall()
        except Exception as error:
            return {
                "assets": [],
                "counts": {"byStatus": {}, "bySource": {}},
                "status": "blocked",
                "blockers": [f"PostgreSQL WebSim asset registry is not available: {error}"],
            }
        assets = [game_asset_from_registry_row(row) for row in rows]
        counts = {"byStatus": {}, "bySource": {}}
        for asset in assets:
            counts["byStatus"][asset["status"]] = counts["byStatus"].get(asset["status"], 0) + 1
            counts["bySource"][asset["source"]] = counts["bySource"].get(asset["source"], 0) + 1
        return {
            "assets": assets,
            "counts": counts,
            "status": "verified" if assets else "empty",
            "blockers": [],
        }

    def _talent_authority_payload(self, talent_status, season, nodes, sync_state):
        simc_state = sync_state.get("simc") if isinstance(sync_state.get("simc"), dict) else {}
        runtime_source = "fallback" if talent_status == "fallback" else "simc"
        return {
            "schemaRevision": TALENT_SCHEMA_REVISION,
            "runtimeSource": runtime_source,
            "diffStatus": "verified" if talent_status == "verified" else "pending_official_audit",
            "checkedAt": sync_state.get("checkedAt") or sync_state.get("updatedAt") or utc_now(),
            "runtime": {
                "status": talent_status,
                "source": runtime_source,
                "simcBuild": simc_state.get("build") or "",
                "traitEdgeSource": simc_state.get("traitEdgeSource") or "",
                "nodeCount": len(nodes or []),
            },
            "official": {
                "status": "pending_audit",
                "revision": season.get("seasonRevision") or season.get("revision") or "",
                "source": "blizzard-game-data-api",
            },
        }

    def _websim_presets(self, cur, class_key, spec_key):
        cur.execute(
            """
            SELECT id, class_key, spec_key, name, profile, payload_json, updated_at
            FROM cache.websim_profile_presets
            WHERE class_key = %s AND spec_key = %s
            ORDER BY name
            LIMIT 12
            """,
            (class_key, spec_key),
        )
        rows = cur.fetchall()
        if not rows:
            return fallback_presets(class_key, spec_key)
        return [
            {
                "id": row[0],
                "classKey": row[1],
                "specKey": row[2],
                "name": row[3],
                "profile": row[4],
                "payload": _json_value(row[5], {}),
                "updatedAt": str(row[6] or ""),
            }
            for row in rows
        ]

    def _community_talent_templates(self, cur, class_key, spec_key):
        cur.execute(
            """
            SELECT id, class_key, spec_key, hero_key, scenario_key, name, flow_label,
                   source_key, source_name, source_url, raw_import_code, websim_export_code,
                   talent_state_json, sample_count, max_key_level, analysis_window,
                   source_status, status, payload_json, updated_at, expires_at,
                   signature, source_refs_json, scan_run_id
            FROM cache.websim_community_talent_templates
            WHERE class_key = %s
              AND spec_key = %s
              AND status = 'verified'
            ORDER BY max_key_level DESC, sample_count DESC, hero_key, name
            LIMIT 240
            """,
            (class_key, spec_key),
        )
        rows = cur.fetchall()
        templates = []
        for row in rows:
            talent_state = _json_value(row[12], {"selectedNodes": []})
            if not isinstance(talent_state, dict):
                talent_state = {"selectedNodes": []}
            payload = _json_value(row[18], {})
            payload = payload if isinstance(payload, dict) else {}
            websim_export_code = row[11] or ""
            raw_import_code = row[10] or ""
            selected_nodes = talent_state.get("selectedNodes") if isinstance(talent_state.get("selectedNodes"), list) else []
            can_apply_visual = bool(str(websim_export_code).startswith("websim:") and selected_nodes)
            raiderio_payload = payload.get("raiderio") if isinstance(payload.get("raiderio"), dict) else {}
            player_id = str(payload.get("playerId") or raiderio_payload.get("characterName") or "").strip()
            templates.append(
                {
                    "id": str(row[0]),
                    "classKey": row[1],
                    "specKey": row[2],
                    "heroKey": row[3],
                    "scenarioKey": row[4],
                    "name": row[5],
                    "flowLabel": row[6],
                    "sourceKey": row[7],
                    "sourceName": row[8],
                    "sourceUrl": row[9],
                    "rawImportCode": raw_import_code,
                    "websimExportCode": websim_export_code,
                    "talentState": talent_state,
                    "sampleCount": _int_value(row[13]),
                    "maxKeyLevel": _int_value(row[14]),
                    "analysisWindow": row[15],
                    "sourceStatus": row[16],
                    "status": row[17],
                    "payload": payload,
                    "signature": row[21] or "",
                    "sourceRefs": normalize_source_refs(_json_value(row[22], []) or []),
                    "scanRunId": row[23] or "",
                    "playerId": player_id,
                    "classLabel": payload.get("classLabel") or class_label(row[1]),
                    "specLabel": payload.get("specLabel") or spec_label(row[2]),
                    "heroLabel": payload.get("heroLabel") or hero_tree_label(row[3]),
                    "scenarioTitle": payload.get("scenarioTitle") or scenario_title(row[4]),
                    "updatedAt": str(row[19] or ""),
                    "expiresAt": str(row[20] or ""),
                    "canApplyVisual": can_apply_visual,
                    "canUseInSimc": bool(can_apply_visual or raw_import_code),
                }
            )
        return dedupe_community_talent_templates_for_display(templates)

    def get_websim_talents(self, class_key="mage", spec_key="arcane", hero_key=""):
        season = self.get_active_season_payload()
        class_key = slugify(class_key, "mage")
        spec_key = slugify(spec_key, "arcane")
        hero_key = hero_tree_for(class_key, spec_key, slugify(hero_key, ""))
        sync_state = self.get_sync_state("websim_sync")
        community_state = self.get_sync_state(COMMUNITY_TALENT_SYNC_KEY)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT t.id, t.class_key, t.spec_key, t.tree_id, t.row_index, t.col_index,
                           t.spell_id, COALESCE(NULLIF(s.name, ''), t.name) AS name, t.payload_json,
                           s.description, s.icon_url, s.payload_json
                    FROM cache.websim_talents t
                    LEFT JOIN LATERAL (
                        SELECT name, description, icon_url, payload_json
                        FROM cache.websim_spell_details s
                        WHERE s.spell_id = t.spell_id
                        ORDER BY CASE WHEN s.locale = 'zh_CN' THEN 0 ELSE 1 END, s.updated_at DESC
                        LIMIT 1
                    ) s ON TRUE
                    WHERE t.class_key = %s
                      AND (t.spec_key = %s OR t.spec_key = 'class')
                      AND t.spell_id > 0
                    ORDER BY row_index, col_index, name
                    LIMIT 320
                    """,
                    (class_key, spec_key),
                )
                rows = cur.fetchall()
                presets = self._websim_presets(cur, class_key, spec_key)
                community_templates = self._community_talent_templates(cur, class_key, spec_key)
        filtered_rows = []
        for row in rows:
            payload = _json_value(row[8], {})
            tree_type = payload.get("treeType") if isinstance(payload, dict) else ""
            tree_type = tree_type or ("class" if row[2] == "class" else "spec")
            if tree_type == "hero" and payload.get("heroKey") != hero_key:
                continue
            filtered_rows.append(
                (
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                    row[6],
                    row[7],
                    json_param(payload),
                    row[9],
                    row[10],
                    json_param(_json_value(row[11], {})),
                )
            )
        nodes = dedupe_real_talent_nodes([decorate_real_talent_node(row, season) for row in filtered_rows])
        has_spell_details = bool(filtered_rows) and all(
            talent_spell_display_description(row[9] or "")[1] == "ready" and str(row[10] or "").strip()
            for row in filtered_rows
        )
        talent_status = "verified" if nodes and season.get("dataStatus") == "verified" and has_spell_details else "simc"
        tree_sections = talent_tree_sections(class_key, spec_key, hero_key)
        talent_authority = self._talent_authority_payload(talent_status, season, nodes, sync_state)
        talent_readiness = talent_readiness_payload(
            class_key,
            spec_key,
            hero_key,
            talent_status,
            nodes,
            tree_sections,
            talent_authority,
        )
        community_state = dict(community_state) if isinstance(community_state, dict) else {}
        community_state.setdefault(
            "templates",
            {
                "total": len(community_templates),
                "verified": len([item for item in community_templates if item.get("status") == "verified"]),
                "blocked": 0,
            },
        )
        season_blockers = season.get("errors") if isinstance(season.get("errors"), list) else []
        return {
            "classKey": class_key,
            "specKey": spec_key,
            "heroKey": hero_key,
            "talentSchemaRevision": TALENT_SCHEMA_REVISION,
            "talentAuthority": talent_authority,
            "talentReadiness": talent_readiness,
            "blockers": unique_text_list([*(talent_readiness.get("blockers") or []), *season_blockers]),
            "nodes": nodes,
            "presets": presets,
            "communityTemplates": community_templates,
            "communityTemplateSync": community_state,
            "treeSections": tree_sections,
            "talentStatus": talent_status,
            **season_metadata_fields(season),
        }

    def get_websim_talent_import(self, class_key="mage", spec_key="arcane", hero_key=""):
        season = self.get_active_season_payload()
        class_key = slugify(class_key, "mage")
        spec_key = slugify(spec_key, "arcane")
        hero_key = hero_tree_for(class_key, spec_key, slugify(hero_key, ""))
        if season.get("dataStatus") != "verified":
            return websim_talent_import_response(
                class_key,
                spec_key,
                hero_key,
                blockers=season.get("errors") or ["active season is not verified"],
            )
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, class_key, spec_key, hero_key, scenario_key, name,
                           source_key, source_name, source_url, raw_import_code,
                           source_status, status, sample_count, max_key_level,
                           analysis_window, updated_at
                    FROM cache.websim_community_talent_templates
                    WHERE class_key = %s
                      AND spec_key = %s
                      AND status = 'verified'
                      AND raw_import_code <> ''
                    ORDER BY CASE WHEN hero_key = %s THEN 0 ELSE 1 END,
                             max_key_level DESC, sample_count DESC, hero_key, name
                    LIMIT 1
                    """,
                    (class_key, spec_key, hero_key),
                )
                row = cur.fetchone()
        if not row:
            return websim_talent_import_response(class_key, spec_key, hero_key)
        return websim_talent_import_response(
            class_key,
            spec_key,
            hero_key,
            template={
                "id": row[0],
                "classKey": row[1],
                "specKey": row[2],
                "heroKey": row[3],
                "scenarioKey": row[4],
                "name": row[5],
                "sourceKey": row[6],
                "sourceName": row[7],
                "sourceUrl": row[8],
                "rawImportCode": row[9],
                "sourceStatus": row[10],
                "status": row[11],
                "sampleCount": _int_value(row[12]),
                "maxKeyLevel": _int_value(row[13]),
                "analysisWindow": row[14] or "",
                "updatedAt": str(row[15] or ""),
                "canUseInSimc": True,
            },
        )

    def _gear_sources_by_item(self, rows):
        result = {}
        for row in rows:
            payload = _json_value(row[9], {})
            payload = payload if isinstance(payload, dict) else {}
            label = str(row[4] or row[3] or row[2] or "").strip()
            source = {
                "id": str(row[0]),
                "itemId": str(row[1]),
                "sourceType": row[2],
                "sourceKey": row[3],
                "label": label,
                "sourceLabel": label,
                "instanceId": row[5],
                "encounterId": row[6],
                "difficultyKey": row[7],
                "difficultyLabel": localized_difficulty_label(row[7], label, row[2]),
                "seasonRevision": row[8],
                "payload": payload,
                "updatedAt": str(row[10] or ""),
            }
            if payload.get("recommendationScore") is not None:
                source["recommendationScore"] = payload.get("recommendationScore")
            result.setdefault(str(row[1]), []).append(source)
        return result

    def _gear_variants_by_item(self, rows):
        result = {}
        for row in rows:
            simc_options = _json_value(row[8], {})
            if not isinstance(simc_options, dict):
                simc_options = {}
            blockers = _json_value(row[10], [])
            if not isinstance(blockers, list):
                blockers = [str(blockers)]
            payload = _json_value(row[11], {})
            payload = payload if isinstance(payload, dict) else {}
            item_level = _int_value(row[7])
            variant = {
                "id": str(row[0]),
                "itemId": str(row[1]),
                "slot": normalize_slot(row[2]),
                "key": row[3],
                "variantKey": row[3],
                "label": row[4],
                "difficultyLabel": localized_difficulty_label(row[6], row[4], row[5]),
                "sourceType": row[5],
                "difficultyKey": row[6],
                "itemLevel": item_level,
                "ilevel": item_level,
                "simcOptions": simc_options,
                "status": row[9] or "blocked",
                "blockers": [str(item) for item in blockers if str(item or "").strip()],
                "payload": payload,
                "updatedAt": str(row[12] or ""),
            }
            if payload.get("simcIlevelOnly"):
                variant["simcIlevelOnly"] = True
            result.setdefault(str(row[1]), []).append(variant)
        return result

    def _gear_mod_options_by_slot(self, rows):
        result = {slot: [] for slot in CANONICAL_GEAR_SLOTS}
        for row in rows:
            option_type = str(row[1] or "").strip().lower()
            slots = _json_value(row[4], [])
            if isinstance(slots, str):
                slots = [slots]
            if not isinstance(slots, list):
                slots = []
            normalized_slots = [normalize_slot(slot) for slot in slots]
            normalized_slots = [slot for slot in normalized_slots if slot]
            if not normalized_slots or "*" in slots:
                normalized_slots = list(CANONICAL_GEAR_SLOTS)
            simc_options = _json_value(row[5], {})
            if not isinstance(simc_options, dict):
                simc_options = {}
            payload = _json_value(row[7], {})
            payload = payload if isinstance(payload, dict) else {}
            label = str(payload.get("displayLabel") or payload.get("displayName") or row[3] or row[2] or "").strip()
            option = {
                "id": str(row[0]),
                "type": option_type,
                "optionType": option_type,
                "name": label,
                "label": label,
                "rawName": row[3],
                "simcOptions": simc_options,
                "status": row[6] or "blocked",
                "payload": payload,
                "updatedAt": str(row[8] or ""),
            }
            for slot in normalized_slots:
                if slot in result:
                    result[slot].append(option)
        return result

    def _gear_payload_fingerprint(self, cur, class_key, spec_key, compact, season, catalog_state):
        cur.execute(
            """
            /* gear_payload_fingerprint */
            SELECT 'websim_items' AS table_name, COUNT(*) AS row_count, MAX(updated_at)::text AS max_updated_at
            FROM cache.websim_items
            UNION ALL
            SELECT 'websim_gear_sources', COUNT(*), MAX(updated_at)::text
            FROM cache.websim_gear_sources
            UNION ALL
            SELECT 'websim_gear_variants', COUNT(*), MAX(updated_at)::text
            FROM cache.websim_gear_variants
            UNION ALL
            SELECT 'websim_gear_mod_options', COUNT(*), MAX(updated_at)::text
            FROM cache.websim_gear_mod_options
            UNION ALL
            SELECT 'websim_community_gear_templates', COUNT(*), MAX(updated_at)::text
            FROM cache.websim_community_gear_templates
            """
        )
        table_rows = tuple(
            (str(row[0] or ""), _int_value(row[1]), str(row[2] or ""))
            for row in cur.fetchall()
        )
        return (
            "pg-websim-gear-v1",
            class_key,
            spec_key,
            bool(compact),
            season.get("seasonRevision") or season.get("revision") or "",
            catalog_state.get("updatedAt") or catalog_state.get("checkedAt") or "",
            catalog_state.get("status") or catalog_state.get("sourceStatus") or "",
            catalog_state.get("schemaRevision") or "",
            catalog_state.get("itemDatabaseRevision") or "",
            catalog_state.get("variantRevision") or "",
            season.get("dataStatus") or "",
            season.get("expiresAt") or "",
            tuple(str(item) for item in (season.get("errors") or [])),
            table_rows,
        )

    def _gear_catalog_items(self, item_rows, sources_by_item, variants_by_item, mod_options_by_slot, class_key, spec_key, season):
        catalog_items = []
        for row in item_rows:
            payload = _json_value(row[4], {})
            payload = payload if isinstance(payload, dict) else {}
            item_id = str(row[0])
            item_sources = active_catalog_sources_for_replacement(sources_by_item.get(item_id, []), season)
            item_variants = variants_by_item.get(item_id, [])
            if not item_sources:
                continue
            raw_item = {
                "id": item_id,
                "itemId": item_id,
                "name": row[1],
                "displayName": payload.get("displayName") or payload.get("name") or row[1],
                "slot": row[2],
                "itemLevel": row[3],
                "ilevel": row[3],
                "quality": payload.get("quality") or "",
                "iconUrl": payload.get("iconUrl") or "",
                "source": (sources_by_item.get(item_id) or [{}])[0].get("label") or "gear catalog",
                "sourceType": "catalog",
                "payload": payload,
            }
            item = normalize_gear_item(raw_item, class_key, spec_key, "catalog")
            if not item:
                continue
            item = enrich_catalog_item(
                item,
                item_sources,
                item_variants,
                mod_options_by_slot.get("socket", {}).get(item["slot"], []),
                mod_options_by_slot.get("enchant", {}).get(item["slot"], []),
                mod_options_by_slot.get("embellishment", {}).get(item["slot"], []),
                class_key,
                spec_key,
            )
            if item:
                catalog_items.append(sanitize_gear_candidate_mod_options(item))
        return catalog_items

    def _gear_community_templates(self, cur, class_key, spec_key):
        cur.execute(
            """
            SELECT id, class_key, spec_key, name, source_key, source_name, source_url,
                   source_status, status, signature, source_refs_json, gear_items_json,
                   raw_string, ready_slot_count, missing_slots_json, analysis_window,
                   payload_json, updated_at, expires_at, scan_run_id
            FROM cache.websim_community_gear_templates
            WHERE class_key = %s AND spec_key = %s AND status IN ('complete', 'partial')
            ORDER BY status, ready_slot_count DESC, updated_at DESC, name
            LIMIT 80
            """,
            (class_key, spec_key),
        )
        templates = []
        for row in cur.fetchall():
            payload = _json_value(row[16], {})
            gear_items = _json_value(row[11], [])
            template = {
                "id": str(row[0] or ""),
                "classKey": row[1] or "",
                "specKey": row[2] or "",
                "name": row[3] or "",
                "sourceKey": row[4] or "",
                "sourceName": row[5] or "",
                "sourceUrl": row[6] or "",
                "sourceStatus": row[7] or "",
                "status": row[8] or "",
                "signature": row[9] or "",
                "sourceRefs": normalize_source_refs(_json_value(row[10], [])),
                "gearItems": gear_items,
                "rawString": row[12] or "",
                "readySlotCount": _int_value(row[13]),
                "missingSlots": _json_value(row[14], []),
                "analysisWindow": row[15] or "",
                "payload": payload,
                "updatedAt": str(row[17] or ""),
                "expiresAt": str(row[18] or ""),
                "scanRunId": row[19] or "",
                "canApplyGear": bool(row[12] or gear_items),
                "templateRevision": COMMUNITY_TEMPLATE_REVISION,
            }
            scenario_key = payload.get("scenarioKey") if isinstance(payload, dict) else ""
            if scenario_key:
                template["scenarioKey"] = scenario_key
            enhancement_readiness = payload.get("enhancementReadiness") if isinstance(payload, dict) else {}
            if isinstance(enhancement_readiness, dict) and enhancement_readiness:
                template["enhancementReadiness"] = enhancement_readiness
            template_evidence = payload.get("templateEvidence") if isinstance(payload, dict) else {}
            if isinstance(template_evidence, dict) and template_evidence:
                template["templateEvidence"] = template_evidence
            templates.append(template)
        return dedupe_gear_community_templates(templates)

    def get_websim_gear(self, class_key="mage", spec_key="arcane", compact=False):
        season = self.get_active_season_payload()
        class_key = slugify(class_key, "mage")
        spec_key = slugify(spec_key, "arcane")
        compact = bool(compact)
        season_fields = season_metadata_fields(season)
        catalog_state = self.get_sync_state("gearCatalog")
        season_errors = season.get("errors") if isinstance(season.get("errors"), list) else []
        catalog_blockers = [
            *[str(item) for item in (catalog_state.get("blockers") or []) if str(item or "").strip()],
            *[str(item) for item in season_errors if str(item or "").strip()],
        ]
        cache_fingerprint = None
        with self.connection() as conn:
            with conn.cursor() as cur:
                cache_fingerprint = self._gear_payload_fingerprint(cur, class_key, spec_key, compact, season, catalog_state)
                cached_payload = _pg_gear_payload_cache_get(cache_fingerprint)
                if cached_payload is not None:
                    return cached_payload
                cur.execute(
                    """
                    SELECT id, item_id, source_type, source_key, source_label, instance_id,
                           encounter_id, difficulty_key, season_revision, payload_json, updated_at
                    FROM cache.websim_gear_sources
                    ORDER BY item_id, source_type, source_label
                    """
                )
                source_rows = cur.fetchall()
                cur.execute(
                    """
                    SELECT id, item_id, slot, variant_key, label, source_type, difficulty_key,
                           item_level, simc_options_json, status, blockers_json, payload_json, updated_at
                    FROM cache.websim_gear_variants
                    ORDER BY item_id, item_level DESC, label
                    """
                )
                variant_rows = cur.fetchall()
                cur.execute(
                    """
                    SELECT id, option_type, option_key, name, applicable_slots_json,
                           simc_options_json, status, payload_json, updated_at
                    FROM cache.websim_gear_mod_options
                    ORDER BY option_type, status DESC, name
                    """
                )
                mod_option_rows = cur.fetchall()
                item_ids = sorted({str(row[1]) for row in source_rows} | {str(row[1]) for row in variant_rows})
                item_rows = []
                if item_ids:
                    placeholders = ", ".join(["%s"] * len(item_ids))
                    cur.execute(
                        f"""
                        SELECT id, name, slot, item_level, payload_json, source_status
                        FROM cache.websim_items
                        WHERE id IN ({placeholders})
                        ORDER BY name
                        """,
                        item_ids,
                    )
                    item_rows = cur.fetchall()
                community_templates = self._gear_community_templates(cur, class_key, spec_key)
        sources_by_item = self._gear_sources_by_item(source_rows)
        variants_by_item = self._gear_variants_by_item(variant_rows)
        raw_options_by_slot = {
            "socket": self._gear_mod_options_by_slot([row for row in mod_option_rows if str(row[1] or "").lower() == "socket"]),
            "enchant": self._gear_mod_options_by_slot([row for row in mod_option_rows if str(row[1] or "").lower() == "enchant"]),
            "embellishment": self._gear_mod_options_by_slot([row for row in mod_option_rows if str(row[1] or "").lower() == "embellishment"]),
        }
        catalog_items = self._gear_catalog_items(
            item_rows,
            sources_by_item,
            variants_by_item,
            raw_options_by_slot,
            class_key,
            spec_key,
            season,
        )
        catalog_items = sorted(catalog_items, key=gear_candidate_quality_score, reverse=True)
        grouped = {slot: [] for slot in CANONICAL_GEAR_SLOTS}
        for item in catalog_items:
            for candidate_slot in gear_candidate_slots(item, item.get("classKey"), item.get("specKey")):
                if candidate_slot in grouped:
                    grouped[candidate_slot].append(gear_candidate_for_slot(item, candidate_slot))
        candidate_limit = 12 if compact else None
        slot_groups = []
        baseline_candidates_by_slot = {}
        for slot in CANONICAL_GEAR_SLOTS:
            items = sorted(unique_gear_candidates(grouped.get(slot, [])), key=gear_candidate_quality_score, reverse=True)
            if candidate_limit:
                items = items[:candidate_limit]
            baseline_candidates_by_slot[slot] = items
            socket_options = raw_options_by_slot["socket"].get(slot, []) if items else []
            enchant_options = raw_options_by_slot["enchant"].get(slot, []) if items else []
            embellishment_options = raw_options_by_slot["embellishment"].get(slot, []) if items else []
            output_items = compact_gear_candidates(items, include_mod_options=False) if compact else items
            slot_group = {
                "slot": slot,
                "simcSlot": slot,
                "label": GEAR_SLOT_LABELS.get(slot, slot),
                "items": output_items,
            }
            if socket_options:
                slot_group["socketOptions"] = compact_gear_mod_options(socket_options) if compact else socket_options
            if enchant_options:
                slot_group["enchantOptions"] = compact_gear_mod_options(enchant_options) if compact else enchant_options
            if embellishment_options:
                slot_group["embellishmentOptions"] = compact_gear_mod_options(embellishment_options) if compact else embellishment_options
            slot_groups.append(slot_group)
        output_catalog_items = compact_gear_candidates(catalog_items) if compact else catalog_items
        readiness = gear_readiness(catalog_items)
        payload = {
            "classKey": class_key,
            "specKey": spec_key,
            "weaponRule": weapon_equipment_rule_payload(class_key, spec_key),
            "slots": gear_slot_payload(),
            "replacementCandidates": slot_groups,
            "equippedSet": {},
            "slotReadiness": gear_slot_readiness(catalog_items, class_key, spec_key),
            "baselineSet": [],
            "communityTemplates": community_templates,
            "communityTemplateSync": websim_gear_community_template_sync_state(community_templates),
            "readiness": readiness,
            "statSnapshot": blocked_stat_snapshot(
                ["Select complete SimC-ready gear and talents to calculate a verified stat snapshot."],
                class_key=class_key,
                spec_key=spec_key,
                gear_readiness_payload=readiness,
            ),
            "gearSchemaRevision": GEAR_SCHEMA_REVISION,
            "gearCatalogRevision": catalog_state.get("schemaRevision") or GEAR_CATALOG_REVISION,
            "catalogStatus": catalog_state.get("status") or "blocked",
            "catalogHealthSummary": compact_catalog_health_summary(catalog_state),
            "catalogCoverage": {
                "slotCoverage": catalog_state.get("slotCoverage") or {},
                "sourceCoverage": catalog_state.get("sourceCoverage") or {},
                "observedVariantCount": catalog_state.get("observedVariantCount") or 0,
                "verifiedObservedVariantCount": catalog_state.get("verifiedObservedVariantCount") or 0,
                "verifiedVariantCount": catalog_state.get("verifiedCount") or 0,
                "partialVariantCount": catalog_state.get("partialCount") or 0,
                "blockedVariantCount": catalog_state.get("blockedCount") or 0,
            },
            "itemDatabaseRevision": catalog_state.get("itemDatabaseRevision") or "",
            "variantRevision": catalog_state.get("variantRevision") or "",
            "catalogCheckedAt": catalog_state.get("checkedAt") or catalog_state.get("updatedAt") or "",
            "catalogBlockers": catalog_blockers,
            "maxLevel": websim_max_level(),
            "checkedAt": utc_now(),
            **season_fields,
        }
        if not compact:
            payload["slotGroups"] = slot_groups
            payload["presets"] = []
            payload["candidateItems"] = []
        payload["catalogItems"] = output_catalog_items[:120]
        if payload.get("replacementCandidates") or payload.get("dataStatus") in {"stale", "blocked"}:
            _pg_gear_payload_cache_put(cache_fingerprint, payload)
        return payload

    def admin_gate_queue_summary(self):
        rows = []
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 'talents' AS domain, status, payload_json->'blockers' AS blockers
                    FROM cache.websim_community_talent_templates
                    ORDER BY updated_at DESC
                    LIMIT 500
                    """
                )
                rows.extend((row[0], row[1] or "", _json_value(row[2], [])) for row in cur.fetchall())
                cur.execute(
                    """
                    SELECT class_key, spec_key, COUNT(*) AS node_count
                    FROM cache.websim_talents
                    GROUP BY class_key, spec_key
                    """
                )
                rows.extend(
                    ("talents", "verified" if _int_value(row[2]) > 0 else "blocked", [] if _int_value(row[2]) > 0 else ["talent tree has no nodes"])
                    for row in cur.fetchall()
                )
                cur.execute(
                    """
                    SELECT 'gear' AS domain, status, blockers_json
                    FROM cache.websim_gear_variants
                    """
                )
                rows.extend((row[0], row[1] or "", _json_value(row[2], [])) for row in cur.fetchall())
                cur.execute("SELECT to_regclass('cache.websim_community_gear_templates')")
                has_gear_templates = bool((cur.fetchone() or [None])[0])
                if has_gear_templates:
                    cur.execute(
                        """
                        SELECT status, payload_json->'blockers' AS blockers, missing_slots_json
                        FROM cache.websim_community_gear_templates
                        ORDER BY updated_at DESC
                        LIMIT 500
                        """
                    )
                    for row in cur.fetchall():
                        blockers = _json_value(row[1], [])
                        missing_slots = _json_value(row[2], [])
                        if missing_slots:
                            blockers = [*(blockers or []), f"missing slots: {', '.join(str(slot) for slot in missing_slots[:6])}"]
                        rows.append(("gear_templates", row[0] or "", blockers))
        return _admin_gate_queue_summary(rows)

    def admin_gate_talent_records(self):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, class_key, spec_key, hero_key, scenario_key, name,
                           source_key, source_name, source_url, source_status, status,
                           sample_count, max_key_level, analysis_window, payload_json,
                           updated_at, expires_at, signature, source_refs_json, scan_run_id
                    FROM cache.websim_community_talent_templates
                    ORDER BY updated_at DESC
                    LIMIT 500
                    """
                )
                template_rows = cur.fetchall()
                cur.execute(
                    """
                    SELECT class_key, spec_key, COUNT(*) AS node_count, MAX(updated_at)
                    FROM cache.websim_talents
                    GROUP BY class_key, spec_key
                    ORDER BY class_key, spec_key
                    LIMIT 500
                    """
                )
                tree_rows = cur.fetchall()
        now = datetime.now(timezone.utc)
        template_rows = [row for row in template_rows if not _timestamp_expired(row[16], now)]
        return {
            "communityTalentTemplates": [
                {
                    "id": str(row[0] or ""),
                    "classKey": row[1] or "",
                    "specKey": row[2] or "",
                    "heroKey": row[3] or "",
                    "scenarioKey": row[4] or "",
                    "name": row[5] or "",
                    "sourceKey": row[6] or "",
                    "sourceName": row[7] or "",
                    "sourceUrl": row[8] or "",
                    "sourceStatus": row[9] or "",
                    "status": row[10] or "",
                    "sampleCount": _int_value(row[11]),
                    "maxKeyLevel": _int_value(row[12]),
                    "analysisWindow": row[13] or "",
                    "payload": _json_value(row[14], {}),
                    "updatedAt": str(row[15] or ""),
                    "expiresAt": str(row[16] or ""),
                    "signature": row[17] or "",
                    "sourceRefs": _json_value(row[18], []),
                    "scanRunId": row[19] or "",
                }
                for row in template_rows
            ],
            "talentTrees": [
                {
                    "classKey": row[0] or "",
                    "specKey": row[1] or "",
                    "nodeCount": _int_value(row[2]),
                    "updatedAt": str(row[3] or ""),
                }
                for row in tree_rows
            ],
        }

    def admin_gate_gear_template_records(self):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('cache.websim_community_gear_templates')")
                has_gear_templates = bool((cur.fetchone() or [None])[0])
                template_rows = []
                if has_gear_templates:
                    cur.execute(
                        """
                        SELECT id, class_key, spec_key, name, source_key, source_name,
                               source_url, source_status, status, signature, source_refs_json,
                               gear_items_json, raw_string, ready_slot_count, missing_slots_json,
                               analysis_window, payload_json, updated_at, expires_at, scan_run_id
                        FROM cache.websim_community_gear_templates
                        ORDER BY updated_at DESC
                        LIMIT 500
                        """
                    )
                    template_rows = cur.fetchall()
        return {
            "communityGearTemplates": [
                {
                    "id": str(row[0] or ""),
                    "classKey": row[1] or "",
                    "specKey": row[2] or "",
                    "name": row[3] or "",
                    "sourceKey": row[4] or "",
                    "sourceName": row[5] or "",
                    "sourceUrl": row[6] or "",
                    "sourceStatus": row[7] or "",
                    "status": row[8] or "",
                    "signature": row[9] or "",
                    "sourceRefs": _json_value(row[10], []),
                    "gearItems": _json_value(row[11], []),
                    "rawString": row[12] or "",
                    "readySlotCount": _int_value(row[13]),
                    "missingSlots": _json_value(row[14], []),
                    "analysisWindow": row[15] or "",
                    "payload": _json_value(row[16], {}),
                    "updatedAt": str(row[17] or ""),
                    "expiresAt": str(row[18] or ""),
                    "scanRunId": row[19] or "",
                }
                for row in template_rows
            ]
        }

    def admin_gate_gear_variant_records(self):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT v.id, v.item_id, COALESCE(NULLIF(i.name, ''), v.item_id),
                           v.slot, v.label, v.source_type, v.difficulty_key, v.item_level,
                           v.simc_options_json, v.status, v.blockers_json, v.payload_json, i.payload_json,
                           COALESCE((
                               SELECT s.source_label
                               FROM cache.websim_gear_sources s
                               WHERE s.item_id = v.item_id
                                 AND s.source_type = v.source_type
                                 AND (s.difficulty_key = v.difficulty_key OR s.difficulty_key = '' OR v.difficulty_key = '')
                               ORDER BY CASE WHEN s.difficulty_key = v.difficulty_key THEN 0 ELSE 1 END,
                                        NULLIF(s.source_label, '') NULLS LAST,
                                        s.updated_at DESC
                               LIMIT 1
                           ), '') AS source_label,
                           COALESCE((
                               SELECT s.instance_id
                               FROM cache.websim_gear_sources s
                               WHERE s.item_id = v.item_id
                                 AND s.source_type = v.source_type
                                 AND (s.difficulty_key = v.difficulty_key OR s.difficulty_key = '' OR v.difficulty_key = '')
                               ORDER BY CASE WHEN s.difficulty_key = v.difficulty_key THEN 0 ELSE 1 END,
                                        NULLIF(s.source_label, '') NULLS LAST,
                                        s.updated_at DESC
                               LIMIT 1
                           ), '') AS source_instance_id,
                           v.updated_at
                    FROM cache.websim_gear_variants v
                    LEFT JOIN cache.websim_items i ON i.id = v.item_id
                    ORDER BY v.updated_at DESC
                    """
                )
                variant_rows = cur.fetchall()
        return {
            "gearVariants": [
                {
                    "id": str(row[0] or ""),
                    "itemId": str(row[1] or ""),
                    "itemName": str(row[2] or ""),
                    "slot": row[3] or "",
                    "label": row[4] or "",
                    "sourceType": row[5] or "",
                    "difficultyKey": row[6] or "",
                    "itemLevel": _int_value(row[7]),
                    "simcOptions": _json_value(row[8], {}),
                    "status": row[9] or "",
                    "blockers": _json_value(row[10], []),
                    "payload": _json_value(row[11], {}),
                    "itemPayload": _json_value(row[12], {}),
                    "sourceLabel": str(row[13] or ""),
                    "sourceInstanceId": str(row[14] or ""),
                    "updatedAt": str(row[15] or ""),
                }
                for row in variant_rows
            ],
        }

    def admin_gate_gear_variant_records_page(self, limit=20, offset=0):
        limit = max(1, min(_int_value(limit, 20), 200))
        offset = max(0, _int_value(offset, 0))
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM (
                        SELECT 1
                        FROM cache.websim_gear_variants
                        GROUP BY item_id, slot
                    ) grouped
                    """
                )
                total_groups = _int_value((cur.fetchone() or [0])[0])
                cur.execute(
                    """
                    SELECT item_id, slot, MAX(updated_at) AS latest_updated_at
                    FROM cache.websim_gear_variants
                    GROUP BY item_id, slot
                    ORDER BY latest_updated_at DESC NULLS LAST, item_id, slot
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                group_rows = cur.fetchall()
                variant_rows = []
                if group_rows:
                    clauses = []
                    params = []
                    for item_id, slot, _updated_at in group_rows:
                        clauses.append("(v.item_id = %s AND v.slot = %s)")
                        params.extend([item_id, slot])
                    cur.execute(
                        f"""
                        SELECT v.id, v.item_id, COALESCE(NULLIF(i.name, ''), v.item_id),
                               v.slot, v.label, v.source_type, v.difficulty_key, v.item_level,
                               v.simc_options_json, v.status, v.blockers_json, v.payload_json, i.payload_json,
                               COALESCE((
                                   SELECT s.source_label
                                   FROM cache.websim_gear_sources s
                                   WHERE s.item_id = v.item_id
                                     AND s.source_type = v.source_type
                                     AND (s.difficulty_key = v.difficulty_key OR s.difficulty_key = '' OR v.difficulty_key = '')
                                   ORDER BY CASE WHEN s.difficulty_key = v.difficulty_key THEN 0 ELSE 1 END,
                                            NULLIF(s.source_label, '') NULLS LAST,
                                            s.updated_at DESC
                                   LIMIT 1
                               ), '') AS source_label,
                               COALESCE((
                                   SELECT s.instance_id
                                   FROM cache.websim_gear_sources s
                                   WHERE s.item_id = v.item_id
                                     AND s.source_type = v.source_type
                                     AND (s.difficulty_key = v.difficulty_key OR s.difficulty_key = '' OR v.difficulty_key = '')
                                   ORDER BY CASE WHEN s.difficulty_key = v.difficulty_key THEN 0 ELSE 1 END,
                                            NULLIF(s.source_label, '') NULLS LAST,
                                            s.updated_at DESC
                                   LIMIT 1
                               ), '') AS source_instance_id,
                               v.updated_at
                        FROM cache.websim_gear_variants v
                        LEFT JOIN cache.websim_items i ON i.id = v.item_id
                        WHERE {" OR ".join(clauses)}
                        ORDER BY v.updated_at DESC NULLS LAST
                        """,
                        tuple(params),
                    )
                    variant_rows = cur.fetchall()
        return {
            "totalGroups": total_groups,
            "gearVariants": [
                {
                    "id": str(row[0] or ""),
                    "itemId": str(row[1] or ""),
                    "itemName": str(row[2] or ""),
                    "slot": row[3] or "",
                    "label": row[4] or "",
                    "sourceType": row[5] or "",
                    "difficultyKey": row[6] or "",
                    "itemLevel": _int_value(row[7]),
                    "simcOptions": _json_value(row[8], {}),
                    "status": row[9] or "",
                    "blockers": _json_value(row[10], []),
                    "payload": _json_value(row[11], {}),
                    "itemPayload": _json_value(row[12], {}),
                    "sourceLabel": str(row[13] or ""),
                    "sourceInstanceId": str(row[14] or ""),
                    "updatedAt": str(row[15] or ""),
                }
                for row in variant_rows
            ],
        }

    def admin_gate_gear_records(self):
        template_payload = self.admin_gate_gear_template_records()
        variant_payload = self.admin_gate_gear_variant_records()
        return {
            "communityGearTemplates": template_payload.get("communityGearTemplates", []),
            "gearVariants": variant_payload.get("gearVariants", []),
        }

    def get_websim_loot(self, filters=None, limit=120):
        filters = filters or {}
        season = self.get_active_season_payload()
        if season.get("dataStatus") != "verified":
            return {"items": [], "instances": [], **season_metadata_fields(season)}
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT l.id, l.instance_id, i.name, l.encounter_id, e.name, l.item_id,
                           l.name, l.slot, l.quality, l.icon_url, wi.payload_json
                    FROM cache.websim_loot l
                    LEFT JOIN cache.websim_instances i ON i.id = l.instance_id
                    LEFT JOIN cache.websim_encounters e ON e.id = l.encounter_id
                    LEFT JOIN cache.websim_items wi ON wi.id = l.item_id
                    ORDER BY i.name, e.name, l.name
                    LIMIT 500
                    """
                )
                rows = cur.fetchall()
        items = []
        for row in rows:
            item_payload = _json_value(row[10], {})
            item = normalize_gear_item(
                {
                    "id": row[5],
                    "itemId": row[5],
                    "name": row[6],
                    "displayName": row[6],
                    "slot": row[7],
                    "quality": row[8],
                    "iconUrl": row[9],
                    "sourceType": "verifiedLoot",
                    "source": f"{row[4] or 'Unknown Encounter'} - {row[2] or 'Unknown Instance'}",
                    "payload": item_payload,
                },
                default_source_type="verifiedLoot",
            )
            if not item:
                continue
            loot_asset = game_asset_from_icon_url(
                "item",
                row[5],
                "websim-loot",
                row[9],
                source="blizzard",
                status="verified",
                semantic_tags=["game", "gear", "item", "loot", row[7]],
                usage=["websim_loot", "builds_detail"],
                fallback_text=fallback_text_for(row[6]),
            )
            item.update(
                {
                    "id": row[0],
                    "instanceId": row[1],
                    "instanceName": row[2] or "Unknown Instance",
                    "encounterId": row[3],
                    "encounterName": row[4] or "Unknown Encounter",
                    "itemId": row[5],
                    "quality": row[8],
                    "iconUrl": row[9],
                    "gameAsset": loot_asset,
                    "sourceType": "verifiedLoot",
                }
            )
            items.append(item)
        instance_id = str(filters.get("instanceId") or "")
        encounter_id = str(filters.get("encounterId") or "")
        slot = str(filters.get("slot") or "")
        query = str(filters.get("q") or "").strip().lower()
        if instance_id:
            items = [item for item in items if str(item.get("instanceId")) == instance_id]
        if encounter_id:
            items = [item for item in items if str(item.get("encounterId")) == encounter_id]
        if slot:
            items = [item for item in items if item.get("slot") == slot]
        if query:
            items = [
                item for item in items
                if query in str(item.get("name", "")).lower()
                or query in str(item.get("encounterName", "")).lower()
                or query in str(item.get("instanceName", "")).lower()
            ]
        return {"items": items[:limit], "instances": self.get_websim_instances(), **season_metadata_fields(season)}

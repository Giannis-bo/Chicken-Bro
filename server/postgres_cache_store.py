#!/usr/bin/env python3
from contextlib import contextmanager
import json
from datetime import datetime, timezone

try:
    from .websim_payload import (
        CANONICAL_GEAR_SLOTS,
        COMMUNITY_TALENT_SYNC_KEY,
        DEFAULT_LOCALE,
        GEAR_CATALOG_REVISION,
        GEAR_SCHEMA_REVISION,
        GEAR_SLOT_LABELS,
        TALENT_SCHEMA_REVISION,
        active_catalog_sources_for_replacement,
        blocked_stat_snapshot,
        class_label,
        compact_catalog_health_summary,
        compact_gear_candidates,
        compact_gear_mod_options,
        dedupe_community_talent_templates_for_display,
        dedupe_real_talent_nodes,
        decorate_real_talent_node,
        enrich_catalog_item,
        current_season_payload,
        fallback_text_for,
        fallback_presets,
        game_asset_from_icon_url,
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
        sanitize_gear_candidate_mod_options,
        scenario_title,
        season_metadata_fields,
        slugify,
        spec_label,
        talent_readiness_payload,
        talent_spell_display_description,
        talent_tree_sections,
        unique_gear_candidates,
        websim_max_level,
        weapon_equipment_rule_payload,
    )
except ImportError:
    from websim_payload import (
        CANONICAL_GEAR_SLOTS,
        COMMUNITY_TALENT_SYNC_KEY,
        DEFAULT_LOCALE,
        GEAR_CATALOG_REVISION,
        GEAR_SCHEMA_REVISION,
        GEAR_SLOT_LABELS,
        TALENT_SCHEMA_REVISION,
        active_catalog_sources_for_replacement,
        blocked_stat_snapshot,
        class_label,
        compact_catalog_health_summary,
        compact_gear_candidates,
        compact_gear_mod_options,
        dedupe_community_talent_templates_for_display,
        dedupe_real_talent_nodes,
        decorate_real_talent_node,
        enrich_catalog_item,
        current_season_payload,
        fallback_text_for,
        fallback_presets,
        game_asset_from_icon_url,
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
        sanitize_gear_candidate_mod_options,
        scenario_title,
        season_metadata_fields,
        slugify,
        spec_label,
        talent_readiness_payload,
        talent_spell_display_description,
        talent_tree_sections,
        unique_gear_candidates,
        websim_max_level,
        weapon_equipment_rule_payload,
    )


def json_param(value):
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
                      AND (expires_at IS NULL OR expires_at > %s)
                    LIMIT 1
                    """,
                    (utc_now(),),
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
                payload["dataStatus"] = row[4]
                payload["verifiedAt"] = str(row[5] or "")
                payload["expiresAt"] = str(row[6] or "")
                payload["sourceRefs"] = _json_value(row[7], [])
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
        if season.get("dataStatus") != "verified":
            return {
                "classKey": class_key,
                "specKey": spec_key,
                "heroKey": hero_key,
                "nodes": [],
                "talentStatus": "blocked",
                **season_metadata_fields(season),
            }
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
        talent_status = "verified" if nodes and has_spell_details else "simc"
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
        return {
            "classKey": class_key,
            "specKey": spec_key,
            "heroKey": hero_key,
            "talentSchemaRevision": TALENT_SCHEMA_REVISION,
            "talentAuthority": talent_authority,
            "talentReadiness": talent_readiness,
            "blockers": talent_readiness.get("blockers") or [],
            "nodes": nodes,
            "presets": presets,
            "communityTemplates": community_templates,
            "communityTemplateSync": community_state,
            "treeSections": tree_sections,
            "talentStatus": talent_status,
            **season_metadata_fields(season),
        }

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

    def get_websim_gear(self, class_key="mage", spec_key="arcane", compact=False):
        season = self.get_active_season_payload()
        class_key = slugify(class_key, "mage")
        spec_key = slugify(spec_key, "arcane")
        compact = bool(compact)
        season_fields = season_metadata_fields(season)
        catalog_state = self.get_sync_state("gearCatalog")
        if season.get("dataStatus") != "verified":
            return {
                "classKey": class_key,
                "specKey": spec_key,
                "replacementCandidates": [],
                "catalogItems": [],
                "catalogStatus": catalog_state.get("status") or "blocked",
                **season_fields,
            }
        with self.connection() as conn:
            with conn.cursor() as cur:
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
            "communityTemplates": [],
            "communityTemplateSync": {"status": "blocked", "templateCount": 0},
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
            "catalogBlockers": catalog_state.get("blockers") or [],
            "maxLevel": websim_max_level(),
            "checkedAt": utc_now(),
            **season_fields,
        }
        if not compact:
            payload["slotGroups"] = slot_groups
            payload["presets"] = []
            payload["candidateItems"] = []
        payload["catalogItems"] = output_catalog_items[:120]
        return payload

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

    def admin_gate_gear_records(self):
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
            ],
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

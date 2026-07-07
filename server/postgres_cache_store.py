#!/usr/bin/env python3
from contextlib import contextmanager
import copy
import hashlib
import json
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    from .websim_payload import (
        CANONICAL_GEAR_SLOTS,
        COMMUNITY_TEMPLATE_AVAILABILITY_POLICY,
        COMMUNITY_TEMPLATE_REVISION,
        COMMUNITY_TALENT_SYNC_KEY,
        DEFAULT_RACE_BY_CLASS,
        DEFAULT_LOCALE,
        DEFAULT_GEAR_TEMPLATE_SOURCE_KEY,
        SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY,
        GEAR_CATALOG_REVISION,
        GEAR_SCHEMA_REVISION,
        GEAR_SLOT_LABELS,
        ITEM_METADATA_SOURCE,
        TALENT_SCHEMA_REVISION,
        active_catalog_sources_for_replacement,
        apply_gear_mod_option_display_fields,
        apply_item_metadata,
        blocked_baseline_gear_template,
        blocked_stat_snapshot,
        class_label,
        classes_payload,
        compact_catalog_health_summary,
        compact_community_gear_template,
        compact_gear_candidates,
        compact_gear_mod_options,
        community_talent_source_ref,
        community_talent_template_slot_summary,
        community_talent_templates_for_spec_slots,
        community_template_availability_expires_at,
        community_gear_import_coverage_summary,
        dedupe_gear_community_templates,
        dedupe_real_talent_nodes,
        decorate_real_talent_node,
        enrich_catalog_item,
        expected_spec_pairs,
        current_season_payload,
        fallback_text_for,
        fallback_presets,
        game_asset_from_icon_url,
        game_asset_from_registry_row,
        gear_candidate_for_slot,
        gear_candidate_quality_score,
        gear_candidate_slots,
        gear_community_template_from_observed_items,
        gear_variant_slots_are_compatible_for_item,
        gear_mod_option_display_fields,
        gear_mod_option_is_supported_config_option,
        gear_mod_option_payload_with_config_policy,
        gear_readiness,
        gear_template_slot_coverage,
        gear_slot_payload,
        gear_slot_readiness,
        hero_tree_for,
        hero_tree_label,
        icon_url_from_media,
        is_baseline_gear_template,
        is_real_community_gear_template,
        item_level_probe_main_hand_removes_offhand,
        item_level_probe_profile_candidates,
        localized_difficulty_label,
        official_item_level_probe_simc_slot,
        item_slot_from_payload,
        item_type_metadata_from_payload,
        limit_replacement_candidates,
        normalize_source_refs,
        normalize_option_value,
        normalize_slot,
        normalize_current_season_raid_pool_payload,
        normalize_gear_item,
        normalize_websim_gear_items,
        normalize_community_gear_template,
        normalize_community_talent_template,
        observed_gear_simc_options,
        observed_variant_stat_identity_key,
        observed_variant_stat_payload_fields,
        sanitize_gear_candidate_mod_options,
        SCENARIOS,
        SIMC_GEAR_OPTION_KEYS,
        scenario_title,
        season_metadata_fields,
        select_best_baseline_gear_templates,
        select_community_best_gear_templates,
        profile_with_simc_json_output,
        run_websim_simcraft_process,
        simc_json_gear_stats_by_slot,
        simc_observed_variant_stat_payload,
        simc_safe_item_name,
        simc_version_payload,
        slugify,
        spec_label,
        talent_readiness_payload,
        websim_talent_import_response,
        talent_spell_display_description,
        talent_tree_sections,
        unique_text_list,
        validate_community_talent_template,
        unique_gear_candidates,
        unique_locale_preferences,
        websim_simc_binary,
        websim_gear_community_templates,
        websim_gear_community_template_sync_state,
        websim_max_level,
        weapon_equipment_rule_payload,
    )
except ImportError:
    from websim_payload import (
        CANONICAL_GEAR_SLOTS,
        COMMUNITY_TEMPLATE_AVAILABILITY_POLICY,
        COMMUNITY_TEMPLATE_REVISION,
        COMMUNITY_TALENT_SYNC_KEY,
        DEFAULT_RACE_BY_CLASS,
        DEFAULT_LOCALE,
        DEFAULT_GEAR_TEMPLATE_SOURCE_KEY,
        SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY,
        GEAR_CATALOG_REVISION,
        GEAR_SCHEMA_REVISION,
        GEAR_SLOT_LABELS,
        ITEM_METADATA_SOURCE,
        TALENT_SCHEMA_REVISION,
        active_catalog_sources_for_replacement,
        apply_gear_mod_option_display_fields,
        apply_item_metadata,
        blocked_baseline_gear_template,
        blocked_stat_snapshot,
        class_label,
        classes_payload,
        compact_catalog_health_summary,
        compact_community_gear_template,
        compact_gear_candidates,
        compact_gear_mod_options,
        community_talent_source_ref,
        community_talent_template_slot_summary,
        community_talent_templates_for_spec_slots,
        community_template_availability_expires_at,
        community_gear_import_coverage_summary,
        dedupe_gear_community_templates,
        dedupe_real_talent_nodes,
        decorate_real_talent_node,
        enrich_catalog_item,
        expected_spec_pairs,
        current_season_payload,
        fallback_text_for,
        fallback_presets,
        game_asset_from_icon_url,
        game_asset_from_registry_row,
        gear_candidate_for_slot,
        gear_candidate_quality_score,
        gear_candidate_slots,
        gear_community_template_from_observed_items,
        gear_variant_slots_are_compatible_for_item,
        gear_mod_option_display_fields,
        gear_mod_option_is_supported_config_option,
        gear_mod_option_payload_with_config_policy,
        gear_readiness,
        gear_template_slot_coverage,
        gear_slot_payload,
        gear_slot_readiness,
        hero_tree_for,
        hero_tree_label,
        icon_url_from_media,
        is_baseline_gear_template,
        is_real_community_gear_template,
        item_level_probe_main_hand_removes_offhand,
        item_level_probe_profile_candidates,
        localized_difficulty_label,
        official_item_level_probe_simc_slot,
        item_slot_from_payload,
        item_type_metadata_from_payload,
        limit_replacement_candidates,
        normalize_source_refs,
        normalize_option_value,
        normalize_slot,
        normalize_current_season_raid_pool_payload,
        normalize_gear_item,
        normalize_websim_gear_items,
        normalize_community_gear_template,
        normalize_community_talent_template,
        observed_gear_simc_options,
        observed_variant_stat_identity_key,
        observed_variant_stat_payload_fields,
        sanitize_gear_candidate_mod_options,
        SCENARIOS,
        SIMC_GEAR_OPTION_KEYS,
        scenario_title,
        season_metadata_fields,
        select_best_baseline_gear_templates,
        select_community_best_gear_templates,
        profile_with_simc_json_output,
        run_websim_simcraft_process,
        simc_json_gear_stats_by_slot,
        simc_observed_variant_stat_payload,
        simc_safe_item_name,
        simc_version_payload,
        slugify,
        spec_label,
        talent_readiness_payload,
        websim_talent_import_response,
        talent_spell_display_description,
        talent_tree_sections,
        unique_text_list,
        validate_community_talent_template,
        unique_gear_candidates,
        unique_locale_preferences,
        websim_simc_binary,
        websim_gear_community_templates,
        websim_gear_community_template_sync_state,
        websim_max_level,
        weapon_equipment_rule_payload,
    )

try:
    from .season_recommended_gear import build_season_recommended_gear_template
except ImportError:
    from season_recommended_gear import build_season_recommended_gear_template

try:
    from .stat_weights_payload import (
        MPLUS_SCENARIOS,
        merge_stat_weight_section,
        scenario_blocked_payload,
        specialization_role,
        with_cache_freshness,
    )
except ImportError:
    from stat_weights_payload import (
        MPLUS_SCENARIOS,
        merge_stat_weight_section,
        scenario_blocked_payload,
        specialization_role,
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


def _community_talent_slot_key(template):
    class_key = slugify(template.get("classKey"), "")
    spec_key = slugify(template.get("specKey"), "")
    raw_hero_key = slugify(template.get("heroKey"), "")
    hero_key = hero_tree_for(class_key, spec_key, raw_hero_key) if class_key and spec_key else raw_hero_key
    if not class_key or not spec_key or not hero_key:
        return None
    return (class_key, spec_key, hero_key)


def _community_talent_slot_id(slot_key):
    if not slot_key:
        return ""
    return ":".join(slot_key)


def _community_talent_selected_count(template):
    talent_state = template.get("talentState") if isinstance(template.get("talentState"), dict) else {}
    selected = talent_state.get("selectedNodes") if isinstance(talent_state.get("selectedNodes"), list) else []
    return len(selected)


def _community_talent_can_apply_visual(template):
    return bool(str(template.get("websimExportCode") or "").startswith("websim:") and _community_talent_selected_count(template))


COMMUNITY_TALENT_WCL_EVIDENCE_ORDER = {
    "wcl_exact_template": 40,
    "wcl_character_supported": 30,
    "wcl_missing": 10,
    "wcl_blocked": 0,
    "wcl_conflict": 0,
}


def _float_value(value, default=0.0):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return default


def _community_talent_payload(template):
    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    return payload if isinstance(payload, dict) else {}


def _community_talent_wcl_evidence(template):
    payload = _community_talent_payload(template)
    evidence = payload.get("wclEvidence") if isinstance(payload.get("wclEvidence"), dict) else {}
    warcraftlogs = payload.get("warcraftlogs") if isinstance(payload.get("warcraftlogs"), dict) else {}
    tier = str(
        evidence.get("tier")
        or payload.get("evidenceTier")
        or warcraftlogs.get("evidenceTier")
        or warcraftlogs.get("tier")
        or ""
    ).strip()
    if tier not in COMMUNITY_TALENT_WCL_EVIDENCE_ORDER:
        tier = "wcl_missing"
    status = "verified" if tier in {"wcl_exact_template", "wcl_character_supported"} else (
        "blocked" if tier in {"wcl_blocked", "wcl_conflict"} else "missing"
    )
    return {
        **evidence,
        "tier": tier,
        "status": evidence.get("status") or status,
    }


def _community_talent_evidence_tier(template):
    return _community_talent_wcl_evidence(template)["tier"]


def _community_talent_evidence_tier_weight(template):
    return COMMUNITY_TALENT_WCL_EVIDENCE_ORDER.get(_community_talent_evidence_tier(template), 0)


def _community_talent_quality_score(template):
    payload = _community_talent_payload(template)
    if payload.get("qualityScore") is not None:
        return _float_value(payload.get("qualityScore"))
    wcl_evidence = payload.get("wclEvidence") if isinstance(payload.get("wclEvidence"), dict) else {}
    performance = wcl_evidence.get("normalizedPerformance") if isinstance(wcl_evidence.get("normalizedPerformance"), dict) else {}
    if performance.get("score") is not None:
        return _float_value(performance.get("score"))
    return 0.0


def _community_talent_evidence_reason_prefix(template):
    tier = _community_talent_evidence_tier(template)
    if tier == "wcl_exact_template":
        return "WCL exact template evidence"
    if tier == "wcl_character_supported":
        return "WCL character-supported evidence"
    if tier == "wcl_conflict":
        return "WCL conflicting evidence"
    if tier == "wcl_blocked":
        return "WCL evidence blocked"
    return "Raider.IO-only evidence"


def _community_talent_rio_evidence(template):
    payload = _community_talent_payload(template)
    evidence = payload.get("rioEvidence") if isinstance(payload.get("rioEvidence"), dict) else {}
    raiderio = payload.get("raiderio") if isinstance(payload.get("raiderio"), dict) else {}
    if evidence:
        return evidence
    if template.get("sourceKey") != "raiderio" and not raiderio:
        return {}
    return {
        "maxKeyLevel": int(template.get("maxKeyLevel") or 0),
        "sampleCount": int(template.get("sampleCount") or 0),
        "source": raiderio.get("source") or "template",
        "profileUrl": raiderio.get("profileUrl") or template.get("sourceUrl") or "",
    }


def _community_talent_signature(template):
    signature = str(template.get("signature") or "").strip()
    if signature:
        return signature
    slot_id = _community_talent_slot_id(_community_talent_slot_key(template))
    return f"{slot_id}:id:{template.get('id') or ''}"


def _community_talent_candidate_weight(template, signature_support=1):
    return (
        1 if template.get("status") == "verified" else 0,
        1 if _community_talent_can_apply_visual(template) else 0,
        _community_talent_evidence_tier_weight(template),
        _community_talent_quality_score(template),
        int(signature_support or 0),
        int(template.get("maxKeyLevel") or 0),
        int(template.get("sampleCount") or 0),
        str(template.get("updatedAt") or ""),
        str(template.get("id") or ""),
    )


def _with_community_talent_promotion_payload(template, role, promotion_status, slot_key, candidate_count, signature_support, reason, winner_id=""):
    promoted = copy.deepcopy(template)
    payload = dict(promoted.get("payload") or {})
    wcl_evidence = _community_talent_wcl_evidence(promoted)
    rio_evidence = _community_talent_rio_evidence(promoted)
    evidence_tier = wcl_evidence.get("tier") or "wcl_missing"
    reason_prefix = _community_talent_evidence_reason_prefix(promoted)
    promotion_reason = f"{reason_prefix}; {reason}"
    promotion = dict(payload.get("promotion") or {})
    promotion.update(
        {
            "stage": "promotion_dedupe",
            "role": role,
            "status": promotion_status,
            "reason": promotion_reason,
            "slotId": _community_talent_slot_id(slot_key),
            "candidateCount": int(candidate_count or 0),
            "signatureSupportCount": int(signature_support or 0),
            "promotedTemplateId": str(winner_id or promoted.get("id") or ""),
            "evidenceTier": evidence_tier,
            "qualityScore": _community_talent_quality_score(promoted),
        }
    )
    if rio_evidence:
        payload["rioEvidence"] = rio_evidence
    payload["wclEvidence"] = wcl_evidence
    payload["evidenceTier"] = evidence_tier
    payload["qualityScore"] = _community_talent_quality_score(promoted)
    payload["promotionReason"] = promotion_reason
    payload["templateInventoryRole"] = role
    payload["promotionStatus"] = promotion_status
    payload["promotion"] = promotion
    promoted["payload"] = payload
    return promoted


def promote_community_talent_template_inventory(templates):
    """Promote source candidates into the active one-template-per-hero inventory."""
    candidate_rows = [copy.deepcopy(template) for template in templates or [] if isinstance(template, dict)]
    groups = {}
    for row in candidate_rows:
        slot_key = _community_talent_slot_key(row)
        if slot_key:
            row["classKey"], row["specKey"], row["heroKey"] = slot_key
        groups.setdefault(slot_key, []).append(row)

    promoted_identities = set()
    promoted_templates = []
    for slot_key, rows in groups.items():
        if slot_key is None:
            active_pool = [row for row in rows if row.get("status") == "blocked"]
        else:
            verified_pool = [row for row in rows if row.get("status") == "verified"]
            active_pool = verified_pool or [row for row in rows if row.get("status") == "blocked"]
        if not active_pool:
            continue

        signature_support = {}
        signature_rows = {}
        for row in rows:
            signature = _community_talent_signature(row)
            if row.get("status") == "verified":
                signature_support[signature] = signature_support.get(signature, 0) + max(1, int(row.get("dedupedCount") or 1))
            signature_rows.setdefault(signature, []).append(row)

        winner = sorted(
            active_pool,
            key=lambda row: _community_talent_candidate_weight(row, signature_support.get(_community_talent_signature(row), 1)),
            reverse=True,
        )[0]
        winner_signature = _community_talent_signature(winner)
        same_signature_rows = signature_rows.get(winner_signature) or [winner]
        merged_refs = []
        for row in same_signature_rows:
            merged_refs.extend(row.get("sourceRefs") or [])
        winner = copy.deepcopy(winner)
        if winner.get("status") == "verified":
            source_rows = [row for row in same_signature_rows if row.get("status") == "verified"] or [winner]
            winner["sourceRefs"] = normalize_source_refs(
                [community_talent_source_ref(row) for row in source_rows]
            )
        else:
            winner["sourceRefs"] = normalize_source_refs(merged_refs or winner.get("sourceRefs") or [])
        winner["dedupedCount"] = sum(max(1, int(row.get("dedupedCount") or 1)) for row in same_signature_rows)
        winner_id = str(winner.get("id") or "")
        promoted_identities.add((slot_key, winner_id))
        promoted_templates.append(
            _with_community_talent_promotion_payload(
                winner,
                "promoted",
                "promoted",
                slot_key,
                len(rows),
                signature_support.get(winner_signature, len(same_signature_rows)),
                "best verified community candidate for class/spec/hero"
                if winner.get("status") == "verified"
                else "blocked diagnostic retained because no verified community candidate exists for class/spec/hero",
                winner_id=winner_id,
            )
        )

    candidate_templates = []
    for row in candidate_rows:
        slot_key = _community_talent_slot_key(row)
        row_id = str(row.get("id") or "")
        is_promoted = (slot_key, row_id) in promoted_identities
        rows = groups.get(slot_key) or []
        signature = _community_talent_signature(row)
        support = sum(
            max(1, int(candidate.get("dedupedCount") or 1))
            for candidate in rows
            if candidate.get("status") == "verified" and _community_talent_signature(candidate) == signature
        )
        candidate_templates.append(
            _with_community_talent_promotion_payload(
                row,
                "promoted" if is_promoted else "candidate",
                "promoted" if is_promoted else "superseded",
                slot_key,
                len(rows),
                support,
                "promoted into active community talent inventory"
                if is_promoted
                else "candidate archived in sync state; another candidate won promotion for this class/spec/hero",
                winner_id=row_id if is_promoted else "",
            )
        )

    promoted_templates.sort(
        key=lambda row: (
            str(row.get("classKey") or ""),
            str(row.get("specKey") or ""),
            str(row.get("heroKey") or ""),
            str(row.get("sourceKey") or ""),
            str(row.get("id") or ""),
        )
    )
    return {
        "promotedTemplates": promoted_templates,
        "candidateTemplates": candidate_templates,
        "candidateTotal": len(candidate_rows),
        "archivedCandidateTotal": max(0, len(candidate_rows) - len(promoted_templates)),
    }


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
                                    name = CASE
                                        WHEN (
                                            COALESCE(cache.websim_items.payload_json #>> '{_metadata,source}', cache.websim_items.payload_json->>'metadataSource', '') = 'Battle.net Game Data API'
                                            OR (
                                                cache.websim_items.source_status = 'verified'
                                                AND COALESCE(cache.websim_items.payload_json #>> '{_metadata,iconUrl}', cache.websim_items.payload_json->>'iconUrl', '') <> ''
                                                AND (
                                                    cache.websim_items.payload_json ? 'inventory_type'
                                                    OR cache.websim_items.payload_json ? 'inventoryType'
                                                    OR cache.websim_items.payload_json ? 'item_class'
                                                    OR cache.websim_items.payload_json ? 'itemClass'
                                                    OR cache.websim_items.payload_json ? 'item_subclass'
                                                    OR cache.websim_items.payload_json ? 'itemSubclass'
                                                )
                                            )
                                        )
                                        THEN cache.websim_items.name
                                        ELSE EXCLUDED.name
                                    END,
                                    slot = CASE
                                        WHEN (
                                            COALESCE(cache.websim_items.payload_json #>> '{_metadata,source}', cache.websim_items.payload_json->>'metadataSource', '') = 'Battle.net Game Data API'
                                            OR (
                                                cache.websim_items.source_status = 'verified'
                                                AND COALESCE(cache.websim_items.payload_json #>> '{_metadata,iconUrl}', cache.websim_items.payload_json->>'iconUrl', '') <> ''
                                                AND (
                                                    cache.websim_items.payload_json ? 'inventory_type'
                                                    OR cache.websim_items.payload_json ? 'inventoryType'
                                                    OR cache.websim_items.payload_json ? 'item_class'
                                                    OR cache.websim_items.payload_json ? 'itemClass'
                                                    OR cache.websim_items.payload_json ? 'item_subclass'
                                                    OR cache.websim_items.payload_json ? 'itemSubclass'
                                                )
                                            )
                                        )
                                        THEN cache.websim_items.slot
                                        ELSE EXCLUDED.slot
                                    END,
                                    item_level = CASE
                                        WHEN (
                                            COALESCE(cache.websim_items.payload_json #>> '{_metadata,source}', cache.websim_items.payload_json->>'metadataSource', '') = 'Battle.net Game Data API'
                                            OR (
                                                cache.websim_items.source_status = 'verified'
                                                AND COALESCE(cache.websim_items.payload_json #>> '{_metadata,iconUrl}', cache.websim_items.payload_json->>'iconUrl', '') <> ''
                                                AND (
                                                    cache.websim_items.payload_json ? 'inventory_type'
                                                    OR cache.websim_items.payload_json ? 'inventoryType'
                                                    OR cache.websim_items.payload_json ? 'item_class'
                                                    OR cache.websim_items.payload_json ? 'itemClass'
                                                    OR cache.websim_items.payload_json ? 'item_subclass'
                                                    OR cache.websim_items.payload_json ? 'itemSubclass'
                                                )
                                            )
                                        )
                                        THEN cache.websim_items.item_level
                                        ELSE EXCLUDED.item_level
                                    END,
                                    payload_json = CASE
                                        WHEN (
                                            COALESCE(cache.websim_items.payload_json #>> '{_metadata,source}', cache.websim_items.payload_json->>'metadataSource', '') = 'Battle.net Game Data API'
                                            OR (
                                                cache.websim_items.source_status = 'verified'
                                                AND COALESCE(cache.websim_items.payload_json #>> '{_metadata,iconUrl}', cache.websim_items.payload_json->>'iconUrl', '') <> ''
                                                AND (
                                                    cache.websim_items.payload_json ? 'inventory_type'
                                                    OR cache.websim_items.payload_json ? 'inventoryType'
                                                    OR cache.websim_items.payload_json ? 'item_class'
                                                    OR cache.websim_items.payload_json ? 'itemClass'
                                                    OR cache.websim_items.payload_json ? 'item_subclass'
                                                    OR cache.websim_items.payload_json ? 'itemSubclass'
                                                )
                                            )
                                        )
                                        THEN cache.websim_items.payload_json
                                        ELSE EXCLUDED.payload_json
                                    END,
                                    source_status = CASE
                                        WHEN (
                                            COALESCE(cache.websim_items.payload_json #>> '{_metadata,source}', cache.websim_items.payload_json->>'metadataSource', '') = 'Battle.net Game Data API'
                                            OR (
                                                cache.websim_items.source_status = 'verified'
                                                AND COALESCE(cache.websim_items.payload_json #>> '{_metadata,iconUrl}', cache.websim_items.payload_json->>'iconUrl', '') <> ''
                                                AND (
                                                    cache.websim_items.payload_json ? 'inventory_type'
                                                    OR cache.websim_items.payload_json ? 'inventoryType'
                                                    OR cache.websim_items.payload_json ? 'item_class'
                                                    OR cache.websim_items.payload_json ? 'itemClass'
                                                    OR cache.websim_items.payload_json ? 'item_subclass'
                                                    OR cache.websim_items.payload_json ? 'itemSubclass'
                                                )
                                            )
                                        )
                                        THEN cache.websim_items.source_status
                                        ELSE EXCLUDED.source_status
                                    END,
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

    def save_websim_item_metadata(
        self,
        item_id,
        item_payload,
        media_payload=None,
        *,
        fallback_slot="",
        fallback_name="",
        english_payload=None,
        locale=DEFAULT_LOCALE,
        source=ITEM_METADATA_SOURCE,
    ):
        item_id = str(item_id or "").strip()
        if not item_id:
            return None
        item_payload = item_payload if isinstance(item_payload, dict) else {}
        media_payload = media_payload if isinstance(media_payload, dict) else {}
        english_payload = english_payload if isinstance(english_payload, dict) else {}
        display_name = item_payload.get("name") or fallback_name or english_payload.get("name") or f"Item {item_id}"
        english_name = english_payload.get("name") or fallback_name or display_name
        slot = item_slot_from_payload(item_payload) or item_slot_from_payload(english_payload) or normalize_slot(fallback_slot) or ""
        raw_quality = item_payload.get("quality")
        quality = raw_quality.get("name") if isinstance(raw_quality, dict) else str(raw_quality or "")
        icon_url = icon_url_from_media(media_payload)
        game_asset = game_asset_from_icon_url(
            "item",
            item_id,
            "websim-item-metadata",
            icon_url,
            source=source,
            status="verified",
            semantic_tags=["game", "gear", "item", slot],
            usage=["websim_gear", "builds_detail", "websim_loot"],
            fallback_text=fallback_text_for(display_name),
        )
        metadata_payload = dict(item_payload)
        metadata_payload.update(
            {
                "displayName": display_name,
                "localizedName": display_name,
                "iconUrl": icon_url,
                "metadataSource": source,
                "metadataStatus": "verified",
                "metadataLocale": locale,
            }
        )
        metadata_payload["_metadata"] = {
            "source": source,
            "itemId": item_id,
            "locale": locale,
            "englishName": english_name,
            "fallbackName": fallback_name,
            "iconUrl": icon_url,
            "gameAsset": game_asset,
        }
        type_metadata = item_type_metadata_from_payload(metadata_payload)
        item_level = _int_value(item_payload.get("level") or item_payload.get("item_level") or item_payload.get("itemLevel"))
        now = utc_now()
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cache.websim_items (id, name, slot, item_level, payload_json, source_status, updated_at)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        slot = COALESCE(NULLIF(EXCLUDED.slot, ''), cache.websim_items.slot),
                        item_level = COALESCE(EXCLUDED.item_level, cache.websim_items.item_level),
                        payload_json = EXCLUDED.payload_json,
                        source_status = EXCLUDED.source_status,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        item_id,
                        str(display_name)[:220],
                        slot,
                        item_level or None,
                        json_param(metadata_payload),
                        "verified",
                        now,
                    ),
                )
            conn.commit()
        return {
            "itemId": item_id,
            "displayName": display_name,
            "localizedName": display_name,
            "englishName": english_name,
            "slot": slot,
            "itemLevel": item_level,
            "quality": quality,
            "iconUrl": icon_url,
            "gameAsset": game_asset,
            "metadataSource": source,
            "metadataStatus": "verified",
            "metadataLocale": locale,
            **type_metadata,
        }

    def _deterministic_uuid(self, kind, value):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"wow-mini-program:{kind}:{value}"))

    def _promote_official_gear_variants_from_observed(self, cur, season_revision, now):
        cur.execute(
            """
            SELECT v.id, v.item_id, v.slot, v.source_type, v.payload_json, wi.payload_json
            FROM cache.websim_gear_variants v
            LEFT JOIN cache.websim_items wi
              ON wi.id = v.item_id
            WHERE v.status = 'partial'
              AND v.source_type IN ('dungeon', 'raid', 'tier_set')
              AND v.variant_key = 'needs-variant'
              AND COALESCE(v.payload_json->>'seasonRevision', '') = %s
            ORDER BY v.item_id, v.slot, v.id
            """,
            (season_revision or "",),
        )
        partial_rows = cur.fetchall()
        if not partial_rows:
            return {"promotedVariants": 0, "removedPartialVariants": 0}
        cur.execute(
            """
            SELECT id, item_id, slot, variant_key, label, item_level, simc_options_json, payload_json
            FROM cache.websim_gear_variants
            WHERE source_type = 'observed_profile'
              AND status = 'verified'
              AND item_level > 0
            ORDER BY item_id, item_level DESC, id
            """
        )
        observed_rows = cur.fetchall()
        observed_by_item = {}
        for row in observed_rows:
            simc_options = _json_value(row[6], {})
            if not isinstance(simc_options, dict) or not simc_options:
                continue
            observed_payload = _json_value(row[7], {})
            if not observed_variant_stat_payload_fields(observed_payload):
                continue
            observed_by_item.setdefault(str(row[1]), []).append(
                {
                    "id": str(row[0]),
                    "itemId": str(row[1]),
                    "slot": normalize_slot(row[2]),
                    "variantKey": str(row[3] or ""),
                    "label": str(row[4] or ""),
                    "itemLevel": _int_value(row[5]),
                    "simcOptions": {
                        key: normalize_option_value(value)
                        for key, value in simc_options.items()
                        if key in SIMC_GEAR_OPTION_KEYS and normalize_option_value(value)
                    },
                    "payload": observed_payload if isinstance(observed_payload, dict) else {},
                }
            )

        promoted = 0
        removed_partial_ids = []
        for partial_id, item_id, raw_slot, source_type, payload_json, item_payload_json in partial_rows:
            item_id = str(item_id or "")
            source_type = str(source_type or "")
            source_slot = normalize_slot(raw_slot)
            partial_payload = _json_value(payload_json, {})
            partial_payload = partial_payload if isinstance(partial_payload, dict) else {}
            item_payload = _json_value(item_payload_json, {})
            item_payload = item_payload if isinstance(item_payload, dict) else {}
            matches = [
                observed
                for observed in observed_by_item.get(item_id, [])
                if gear_variant_slots_are_compatible_for_item(item_payload, source_slot, observed.get("slot"))
            ]
            if not matches:
                continue
            promoted_for_partial = 0
            for observed in matches:
                simc_options = observed.get("simcOptions") or {}
                observed_payload = observed.get("payload") if isinstance(observed.get("payload"), dict) else {}
                observed_stat_payload = observed_variant_stat_payload_fields(observed_payload)
                if not simc_options or not observed_stat_payload:
                    continue
                observed_class_keys = [
                    str(value)
                    for value in observed_payload.get("classKeys") or observed_payload.get("observedClassKeys") or []
                    if str(value or "").strip()
                ]
                observed_spec_keys = [
                    str(value)
                    for value in observed_payload.get("specKeys") or observed_payload.get("observedSpecKeys") or []
                    if str(value or "").strip()
                ]
                digest = hashlib.sha1(
                    json.dumps(
                        [str(partial_id), observed.get("id"), observed.get("itemLevel"), simc_options],
                        sort_keys=True,
                    ).encode("utf-8")
                ).hexdigest()[:10]
                prefix = "set-observed" if source_type == "tier_set" else "loot-observed"
                variant_payload = {
                    **partial_payload,
                    **observed_stat_payload,
                    "officialVariantSource": source_type,
                    "observedVariantSource": "observed_profile",
                    "observedVariantId": observed.get("id") or "",
                    "observedProfileRefs": observed_payload.get("observedProfileRefs") or [],
                }
                if observed_class_keys:
                    variant_payload["observedClassKeys"] = observed_class_keys
                if observed_spec_keys:
                    variant_payload["observedSpecKeys"] = observed_spec_keys
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
                        self._deterministic_uuid("gear-observed-variant", f"{partial_id}:{observed.get('id')}:{digest}"),
                        item_id,
                        f"observed-{observed.get('itemLevel') or 'unknown'}-{digest}",
                        "verified",
                        source_slot or observed.get("slot") or "",
                        observed.get("label") or f"Observed {observed.get('itemLevel') or 'unknown'}",
                        source_type,
                        "observed_profile",
                        observed.get("itemLevel") or 0,
                        json_param(simc_options),
                        "verified",
                        json_param([]),
                        json_param(variant_payload),
                        now,
                    ),
                )
                promoted += 1
                promoted_for_partial += 1
            if promoted_for_partial:
                removed_partial_ids.append(str(partial_id))
        if removed_partial_ids:
            cur.execute(
                "DELETE FROM cache.websim_gear_variants WHERE id = ANY(%s)",
                (removed_partial_ids,),
            )
        return {"promotedVariants": promoted, "removedPartialVariants": len(removed_partial_ids)}

    def _existing_verified_observed_variant_identities(self):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT item_id, slot, item_level, simc_options_json
                    FROM cache.websim_gear_variants
                    WHERE source_type = 'observed_profile'
                      AND status = 'verified'
                    """
                )
                rows = cur.fetchall()
        identities = set()
        for item_id, slot, item_level, simc_options_json in rows:
            key = observed_variant_stat_identity_key(
                item_id,
                slot,
                item_level,
                _json_value(simc_options_json, {}),
            )
            if key:
                identities.add(key)
        return identities

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
                promotion = self._promote_official_gear_variants_from_observed(cur, season_revision, now)
                promoted_variant_count = int(promotion.get("promotedVariants") or 0)
                removed_partial_count = int(promotion.get("removedPartialVariants") or 0)
        has_sources = source_count > 0
        partial_count = max(0, len(variant_keys) - removed_partial_count)
        verified_count = promoted_variant_count
        variant_count = partial_count + verified_count
        variant_status = "verified" if has_sources and partial_count == 0 else ("partial" if has_sources else "blocked")
        state = {
            "runner": "postgres",
            "status": variant_status,
            "checkedAt": now,
            "schemaRevision": GEAR_CATALOG_REVISION,
            "itemCount": len(item_ids),
            "sourceCount": source_count,
            "variantCount": variant_count,
            "verifiedCount": verified_count,
            "partialCount": partial_count,
            "blockedCount": 0,
            "blockers": [] if has_sources else ["PostgreSQL WebSim loot cache is empty"],
            "observedSync": {
                "officialVariantPromotion": promotion,
            },
            "dataReadiness": {
                "status": variant_status,
                "sourceStatus": "verified" if has_sources else "blocked",
                "variantStatus": variant_status,
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

    def community_gear_template_live_health_summary(self):
        now = datetime.now(timezone.utc)
        templates = [
            template for template in (self.admin_gate_gear_template_records().get("communityGearTemplates") or [])
            if isinstance(template, dict) and not _timestamp_expired(template.get("expiresAt"), now)
        ]
        expected_specs = []
        seen_expected_specs = set()
        for item in expected_spec_pairs():
            class_key = ""
            spec_key = ""
            if isinstance(item, str):
                parts = item.split(":", 1)
                if len(parts) == 2:
                    class_key, spec_key = parts
            elif isinstance(item, (list, tuple)):
                if len(item) >= 3 and isinstance(item[0], str) and ":" in item[0]:
                    class_key, spec_key = item[1], item[2]
                elif len(item) >= 2:
                    class_key, spec_key = item[0], item[1]
            class_key = slugify(class_key, "")
            spec_key = slugify(spec_key, "")
            spec_id = f"{class_key}:{spec_key}" if class_key and spec_key else ""
            if spec_id and spec_id not in seen_expected_specs:
                seen_expected_specs.add(spec_id)
                expected_specs.append((spec_id, class_key, spec_key))
        if not expected_specs:
            seen_specs = sorted({
                f"{template.get('classKey')}:{template.get('specKey')}"
                for template in templates
                if template.get("classKey") and template.get("specKey")
            })
            expected_specs = [
                (spec_id, *spec_id.split(":", 1))
                for spec_id in seen_specs
                if ":" in spec_id
            ]
        grouped = {spec_id: {"community": [], "baseline": []} for spec_id, _, _ in expected_specs}
        counts = {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        for template in templates:
            if not isinstance(template, dict):
                continue
            counts["total"] += 1
            counts[_template_count_bucket(template.get("status"))] += 1
            class_key = slugify(template.get("classKey"), "")
            spec_key = slugify(template.get("specKey"), "")
            spec_id = f"{class_key}:{spec_key}" if class_key and spec_key else ""
            if spec_id not in grouped:
                continue
            if is_baseline_gear_template(template):
                grouped[spec_id]["baseline"].append(template)
            elif is_real_community_gear_template(template):
                grouped[spec_id]["community"].append(template)

        complete_specs = []
        partial_specs = []
        pending_specs = []
        blocked_specs = []
        baseline_available_specs = []
        baseline_blocked_specs = []
        season_recommendation_complete_specs = []
        season_recommendation_verified_specs = []
        season_recommendation_provisional_specs = []
        missing_slot_counts = {slot: 0 for slot in CANONICAL_GEAR_SLOTS}
        ready_slot_count = 0
        latest_scan_run_id = ""
        for template in templates:
            if template.get("scanRunId"):
                latest_scan_run_id = template.get("scanRunId")
                break

        for spec_id, class_key, spec_key in expected_specs:
            community_candidates = grouped.get(spec_id, {}).get("community") or []
            best_community = (
                select_community_best_gear_templates(community_candidates, class_key, spec_key)[0]
                if community_candidates
                else {}
            )
            if best_community:
                missing_slots = [
                    slot for slot in (best_community.get("missingSlots") or [])
                    if slot in CANONICAL_GEAR_SLOTS
                ]
                if best_community.get("status") == "complete" and not missing_slots:
                    complete_specs.append(spec_id)
                elif best_community.get("status") == "blocked":
                    blocked_specs.append(spec_id)
                else:
                    partial_specs.append(spec_id)
                ready_slot_count += len(CANONICAL_GEAR_SLOTS) - len(set(missing_slots))
                for slot in missing_slots:
                    missing_slot_counts[slot] += 1
            else:
                pending_specs.append(spec_id)
                for slot in CANONICAL_GEAR_SLOTS:
                    missing_slot_counts[slot] += 1

            baseline_candidates = grouped.get(spec_id, {}).get("baseline") or []
            best_baseline = select_best_baseline_gear_templates(baseline_candidates)
            if best_baseline and int((best_baseline[0] or {}).get("readySlotCount") or 0) > 0:
                baseline_available_specs.append(spec_id)
                baseline_template = best_baseline[0]
                if baseline_template.get("sourceKey") == SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY:
                    season_recommendation_complete_specs.append(spec_id)
                    payload = baseline_template.get("payload") if isinstance(baseline_template.get("payload"), dict) else {}
                    evidence = payload.get("templateEvidence") if isinstance(payload.get("templateEvidence"), dict) else {}
                    confidence = str(evidence.get("recommendationConfidence") or "").strip()
                    if confidence == "verified":
                        season_recommendation_verified_specs.append(spec_id)
                    elif confidence == "provisional":
                        season_recommendation_provisional_specs.append(spec_id)
            else:
                baseline_blocked_specs.append(spec_id)

        incomplete_specs = [*partial_specs, *pending_specs, *blocked_specs]
        missing_slot_total = sum(missing_slot_counts.values())
        checked_at = utc_now()
        community_import = community_gear_import_coverage_summary(
            len(expected_specs),
            community_complete_specs=complete_specs,
            community_partial_specs=partial_specs,
            community_pending_specs=pending_specs,
            community_blocked_specs=blocked_specs,
            baseline_available_specs=baseline_available_specs,
            baseline_blocked_specs=baseline_blocked_specs,
        )
        preflight = {
            "schemaRevision": "community-gear-template-preflight-v1",
            "scanRunId": latest_scan_run_id,
            "checkedAt": checked_at,
            "status": community_import.get("status") or "partial",
            "totalSpecCount": len(expected_specs),
            "totalDisplaySlotCount": len(expected_specs) * 2,
            "communityBest": {
                "templateSlot": "community_best",
                "totalSpecCount": len(expected_specs),
                "completeSpecCount": len(complete_specs),
                "partialSpecCount": len(partial_specs),
                "pendingSpecCount": len(pending_specs),
                "blockedSpecCount": len(blocked_specs),
                "completeSpecs": complete_specs,
                "partialSpecs": partial_specs,
                "pendingSpecs": pending_specs,
                "blockedSpecs": blocked_specs,
                "countingPolicy": "real community gear subtype under community import; must reach 40/40 specs",
            },
            "baseline": {
                "templateSlot": "baseline",
                "totalSpecCount": len(expected_specs),
                "availableSpecCount": len(baseline_available_specs),
                "blockedSpecCount": len(baseline_blocked_specs),
                "availableSpecs": baseline_available_specs,
                "blockedSpecs": baseline_blocked_specs,
                "countingPolicy": "fallback baseline gear subtype under community import; must reach 40/40 specs",
            },
            "communityImport": community_import,
            "canonicalSlotMatrix": {
                "totalSlotCount": len(expected_specs) * len(CANONICAL_GEAR_SLOTS),
                "readySlotCount": ready_slot_count,
                "missingSlotCount": missing_slot_total,
                "missingBySlot": {
                    slot: count for slot, count in missing_slot_counts.items() if count
                },
            },
        }
        season_recommendation_blocked_specs = [
            spec_id for spec_id, _class_key, _spec_key in expected_specs
            if spec_id not in set(season_recommendation_complete_specs)
        ]
        season_recommendation_status = "partial"
        if expected_specs and len(season_recommendation_complete_specs) == len(expected_specs):
            season_recommendation_status = "verified"
        elif not season_recommendation_complete_specs:
            season_recommendation_status = "blocked"
        return {
            "templates": counts,
            "preflight": preflight,
            "realCommunityTemplates": {
                "templateRevision": preflight["schemaRevision"],
                "totalSpecCount": len(expected_specs),
                "coveredSpecCount": len(complete_specs),
                "missingSpecCount": len(incomplete_specs),
                "partialSpecCount": len(partial_specs),
                "pendingSpecCount": len(pending_specs),
                "blockedSpecCount": len(blocked_specs),
                "coveredSpecs": complete_specs,
                "partialSpecs": partial_specs,
                "missingSpecs": incomplete_specs,
                "topBlockers": [
                    {
                        "stage": "gear_template_preflight",
                        "reason": "missing complete real community gear template",
                        "count": len(incomplete_specs),
                    }
                ] if incomplete_specs else [],
                "lastSyncRun": latest_scan_run_id,
                "countingPolicy": "real samples only; baseline/default templates are excluded",
            },
            "baselineTemplates": preflight["baseline"],
            "communityImportTemplates": preflight["communityImport"],
            "seasonRecommendation": {
                "sourceKey": SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY,
                "sourceName": "当前赛季大秘境 AOE 推荐模板",
                "status": season_recommendation_status,
                "totalSpecCount": len(expected_specs),
                "completeSpecCount": len(season_recommendation_complete_specs),
                "verifiedSpecCount": len(season_recommendation_verified_specs),
                "provisionalSpecCount": len(season_recommendation_provisional_specs),
                "blockedSpecCount": len(season_recommendation_blocked_specs),
                "completeSpecs": season_recommendation_complete_specs,
                "verifiedSpecs": season_recommendation_verified_specs,
                "provisionalSpecs": season_recommendation_provisional_specs,
                "blockedSpecs": season_recommendation_blocked_specs,
                "lastRunId": latest_scan_run_id,
            },
            "scanRunId": latest_scan_run_id,
            "checkedAt": checked_at,
        }

    def community_talent_authority_index(self, class_key, spec_key):
        class_key = slugify(class_key, "mage")
        spec_key = slugify(spec_key, "arcane")
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, spell_id, payload_json
                    FROM cache.websim_talents
                    WHERE class_key = %s
                      AND (spec_key = %s OR spec_key = 'class')
                      AND spell_id > 0
                    ORDER BY row_index, col_index, id
                    LIMIT 640
                    """,
                    (class_key, spec_key),
                )
                rows = cur.fetchall()
        by_id = {}
        for row in rows:
            payload = _json_value(row[2], {})
            if not isinstance(payload, dict):
                payload = {}
            node = {
                **payload,
                "id": row[0],
                "spellId": _int_value(row[1]),
                "treeType": payload.get("treeType") or ("class" if ":class" in str(row[0]) else payload.get("tree")),
            }
            candidate_ids = {
                _int_value(node.get("spellId")),
                _int_value(payload.get("traitId")),
                _int_value(payload.get("traitDefinitionId")),
                _int_value(payload.get("nodeId")),
                _int_value(payload.get("entryId")),
            }
            for rank_entry in payload.get("rankEntries") or []:
                if not isinstance(rank_entry, dict):
                    continue
                for key in ("traitId", "traitDefinitionId", "entryId", "nodeId", "spellId"):
                    candidate_ids.add(_int_value(rank_entry.get(key)))
            for candidate_id in candidate_ids:
                if candidate_id > 0:
                    by_id.setdefault(candidate_id, []).append(node)
        return by_id

    def replace_community_talent_templates(self, templates, scan_run_id="", include_details=False, target_slot_ids=None):
        target_slot_ids = [
            str(slot_id or "").strip()
            for slot_id in (target_slot_ids or [])
            if str(slot_id or "").strip()
        ]
        normalized_rows = []
        for template in templates or []:
            if not isinstance(template, dict):
                continue
            source_template = {
                **template,
                "scanRunId": template.get("scanRunId") or scan_run_id,
            }
            try:
                normalized = validate_community_talent_template(self, source_template)
            except Exception as error:
                normalized = normalize_community_talent_template(
                    source_template,
                    template.get("sourceKey", "unknown"),
                    template.get("sourceStatus", "partial"),
                )
                payload = dict(normalized.get("payload") or {})
                blockers = unique_text_list([*(payload.get("blockers") or []), str(error)])
                payload["blockers"] = blockers
                payload["errors"] = blockers
                normalized["payload"] = payload
                normalized["status"] = "blocked"
            payload = dict(normalized.get("payload") or {})
            payload.setdefault("legacyId", normalized["id"])
            normalized["payload"] = payload
            normalized_rows.append(normalized)
        counts = {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        if not normalized_rows:
            if include_details:
                counts["validatedTemplates"] = []
                counts["promotedTemplates"] = []
                counts["candidateTemplates"] = []
                counts["candidateTotal"] = 0
                counts["archivedCandidateTotal"] = 0
            return counts
        promotion = promote_community_talent_template_inventory(normalized_rows)
        active_rows = promotion["promotedTemplates"]
        for normalized in active_rows:
            bucket = _template_count_bucket(normalized.get("status"))
            counts["total"] += 1
            counts[bucket] += 1
        candidate_counts = {"candidateVerified": 0, "candidatePartial": 0, "candidateBlocked": 0}
        for normalized in normalized_rows:
            bucket = _template_count_bucket(normalized.get("status"))
            if bucket == "verified":
                candidate_counts["candidateVerified"] += 1
            elif bucket == "partial":
                candidate_counts["candidatePartial"] += 1
            else:
                candidate_counts["candidateBlocked"] += 1
        counts.update(
            {
                "candidateTotal": promotion["candidateTotal"],
                "archivedCandidateTotal": promotion["archivedCandidateTotal"],
                "promotedTotal": len(active_rows),
                "duplicateActiveExpired": 0,
                **candidate_counts,
            }
        )
        replace_checked_at = datetime.now(timezone.utc).isoformat()
        current_ids = [
            self._deterministic_uuid("community-talent-template", normalized["id"])
            for normalized in active_rows
            if normalized.get("id")
        ]
        current_source_keys = sorted({
            normalized.get("sourceKey")
            for normalized in normalized_rows
            if normalized.get("sourceKey")
        })
        target_slot_id_set = set(target_slot_ids)
        replacement_slot_ids = set()
        for normalized in active_rows:
            if normalized.get("status") != "verified":
                continue
            slot_parts = [
                str(normalized.get("classKey") or "").strip(),
                str(normalized.get("specKey") or "").strip(),
                str(normalized.get("heroKey") or "").strip(),
            ]
            if not all(slot_parts):
                continue
            slot_id = ":".join(slot_parts)
            if target_slot_id_set and slot_id not in target_slot_id_set:
                continue
            replacement_slot_ids.add(slot_id)
        replacement_slot_ids = sorted(replacement_slot_ids)
        with self.connection() as conn:
            with conn.cursor() as cur:
                for normalized in active_rows:
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
                if current_source_keys:
                    target_filter = bool(target_slot_ids)
                    if current_ids:
                        if target_filter:
                            if replacement_slot_ids:
                                cur.execute(
                                    """
                                    UPDATE cache.websim_community_talent_templates
                                    SET expires_at = %s,
                                        updated_at = %s
                                    WHERE source_key = ANY(%s::text[])
                                      AND CONCAT(class_key, ':', spec_key, ':', hero_key) = ANY(%s::text[])
                                      AND NOT (id = ANY(%s::uuid[]))
                                      AND (expires_at IS NULL OR expires_at > %s)
                                    """,
                                    (
                                        replace_checked_at,
                                        replace_checked_at,
                                        current_source_keys,
                                        replacement_slot_ids,
                                        current_ids,
                                        replace_checked_at,
                                    ),
                                )
                        else:
                            cur.execute(
                                """
                                UPDATE cache.websim_community_talent_templates
                                SET expires_at = %s,
                                    updated_at = %s
                                WHERE source_key = ANY(%s::text[])
                                  AND NOT (id = ANY(%s::uuid[]))
                                  AND (expires_at IS NULL OR expires_at > %s)
                                """,
                                (
                                    replace_checked_at,
                                    replace_checked_at,
                                    current_source_keys,
                                    current_ids,
                                    replace_checked_at,
                                ),
                            )
                    else:
                        if not target_filter:
                            cur.execute(
                                """
                                UPDATE cache.websim_community_talent_templates
                                SET expires_at = %s,
                                    updated_at = %s
                                WHERE source_key = ANY(%s::text[])
                                  AND (expires_at IS NULL OR expires_at > %s)
                                """,
                                (
                                    replace_checked_at,
                                    replace_checked_at,
                                    current_source_keys,
                                    replace_checked_at,
                                ),
                            )
                cur.execute(
                    """
                    WITH ranked AS (
                        SELECT id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY class_key, spec_key, hero_key
                                   ORDER BY
                                       CASE status
                                           WHEN 'verified' THEN 0
                                           WHEN 'partial' THEN 1
                                           ELSE 2
                                       END,
                                       CASE COALESCE(payload_json->>'evidenceTier', '')
                                           WHEN 'wcl_exact_template' THEN 0
                                           WHEN 'wcl_character_supported' THEN 1
                                           WHEN 'wcl_missing' THEN 2
                                           WHEN 'wcl_conflict' THEN 3
                                           WHEN 'wcl_blocked' THEN 4
                                           ELSE 5
                                       END,
                                       COALESCE(max_key_level, 0) DESC,
                                       COALESCE(sample_count, 0) DESC,
                                       updated_at DESC,
                                       id
                               ) AS active_slot_rank
                        FROM cache.websim_community_talent_templates
                        WHERE (expires_at IS NULL OR expires_at > %s)
                          AND COALESCE(class_key, '') <> ''
                          AND COALESCE(spec_key, '') <> ''
                          AND COALESCE(hero_key, '') <> ''
                    )
                    UPDATE cache.websim_community_talent_templates AS template
                    SET expires_at = %s,
                        updated_at = %s
                    FROM ranked
                    WHERE template.id = ranked.id
                      AND ranked.active_slot_rank > 1
                    """,
                    (replace_checked_at, replace_checked_at, replace_checked_at),
                )
                counts["duplicateActiveExpired"] = cur.rowcount
        if target_slot_ids:
            active_counts = self.community_talent_template_counts()
            for key in ("total", "verified", "partial", "blocked"):
                counts[key] = active_counts.get(key, counts.get(key, 0))
        if include_details:
            counts["validatedTemplates"] = promotion["candidateTemplates"]
            counts["promotedTemplates"] = active_rows
            counts["candidateTemplates"] = promotion["candidateTemplates"]
        return counts

    def community_talent_template_coverage_rows(self):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, class_key, spec_key, hero_key, scenario_key, name,
                           source_key, source_name, source_url, raw_import_code, websim_export_code,
                           talent_state_json, sample_count, max_key_level, analysis_window,
                           source_status, status, payload_json, updated_at, expires_at,
                           signature, source_refs_json, scan_run_id
                    FROM cache.websim_community_talent_templates
                    WHERE status IN ('verified', 'blocked')
                      AND (expires_at IS NULL OR expires_at > now())
                    ORDER BY updated_at DESC, max_key_level DESC, sample_count DESC, hero_key, name
                    LIMIT 1000
                    """
                )
                rows = cur.fetchall()
        result = []
        for row in rows:
            payload = _json_value(row[17], {})
            payload = payload if isinstance(payload, dict) else {}
            talent_state = _json_value(row[11], {"selectedNodes": []})
            if not isinstance(talent_state, dict):
                talent_state = {"selectedNodes": []}
            result.append(
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
                    "rawImportCode": row[9] or "",
                    "websimExportCode": row[10] or "",
                    "talentState": talent_state,
                    "sampleCount": _int_value(row[12]),
                    "maxKeyLevel": _int_value(row[13]),
                    "analysisWindow": row[14] or "",
                    "sourceStatus": row[15] or "",
                    "status": row[16] or "",
                    "payload": payload,
                    "updatedAt": str(row[18] or ""),
                    "expiresAt": str(row[19] or ""),
                    "signature": row[20] or "",
                    "sourceRefs": normalize_source_refs(_json_value(row[21], []) or []),
                    "scanRunId": row[22] or "",
                }
            )
        return result

    def expire_community_talent_template_sources(self, source_keys, expired_at=""):
        keys = sorted({str(source_key or "").strip() for source_key in source_keys or [] if str(source_key or "").strip()})
        if not keys:
            return {"expired": 0}
        checked_at = expired_at or datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE cache.websim_community_talent_templates
                    SET expires_at = %s,
                        updated_at = %s
                    WHERE source_key = ANY(%s::text[])
                      AND (expires_at IS NULL OR expires_at > %s)
                    """,
                    (checked_at, checked_at, keys, checked_at),
                )
                return {"expired": cur.rowcount}

    def restore_community_template_availability(self, availability_expires_at="", checked_at=""):
        checked_at = checked_at or datetime.now(timezone.utc).isoformat()
        availability_expires_at = availability_expires_at or community_template_availability_expires_at()
        freshness_payload = {
            "checkedAt": checked_at,
            "freshUntil": checked_at,
            "status": "stale",
            "availabilityPolicy": COMMUNITY_TEMPLATE_AVAILABILITY_POLICY,
            "repairReason": "availability_repair_after_ttl_split",
        }
        blocked_talent_sources = ["manual_fixture", "websim_baseline"]
        blocked_gear_sources = [
            DEFAULT_GEAR_TEMPLATE_SOURCE_KEY,
            "baseline_template",
            "simc_preset",
            "baseline_blocked",
            "manual_fixture",
            "fallback",
            "source_reference",
        ]
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH ranked AS (
                        SELECT id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY class_key, spec_key, hero_key
                                   ORDER BY
                                       CASE COALESCE(payload_json->>'evidenceTier', '')
                                           WHEN 'wcl_exact_template' THEN 0
                                           WHEN 'wcl_character_supported' THEN 1
                                           WHEN 'wcl_missing' THEN 2
                                           WHEN 'wcl_conflict' THEN 3
                                           WHEN 'wcl_blocked' THEN 4
                                           ELSE 5
                                       END,
                                       COALESCE(max_key_level, 0) DESC,
                                       COALESCE(sample_count, 0) DESC,
                                       updated_at DESC,
                                       id
                               ) AS availability_rank
                        FROM cache.websim_community_talent_templates
                        WHERE status = 'verified'
                          AND source_key <> ALL(%s::text[])
                          AND COALESCE(class_key, '') <> ''
                          AND COALESCE(spec_key, '') <> ''
                          AND COALESCE(hero_key, '') <> ''
                    )
                    UPDATE cache.websim_community_talent_templates AS template
                    SET expires_at = %s,
                        updated_at = %s,
                        payload_json = jsonb_set(
                            COALESCE(template.payload_json, '{}'::jsonb),
                            '{communityTemplateFreshness}',
                            %s::jsonb,
                            true
                        )
                    FROM ranked
                    WHERE template.id = ranked.id
                      AND ranked.availability_rank = 1
                      AND (
                          template.expires_at IS NULL
                          OR template.expires_at <= %s
                          OR NOT (COALESCE(template.payload_json, '{}'::jsonb) ? 'communityTemplateFreshness')
                      )
                    """,
                    (
                        blocked_talent_sources,
                        availability_expires_at,
                        checked_at,
                        json_param(freshness_payload),
                        checked_at,
                    ),
                )
                talent_restored = cur.rowcount
                cur.execute(
                    """
                    WITH ranked AS (
                        SELECT id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY class_key, spec_key
                                   ORDER BY
                                       COALESCE(ready_slot_count, 0) DESC,
                                       CASE source_status
                                           WHEN 'synced' THEN 0
                                           WHEN 'verified' THEN 1
                                           WHEN 'partial' THEN 2
                                           ELSE 3
                                       END,
                                       updated_at DESC,
                                       id
                               ) AS availability_rank
                        FROM cache.websim_community_gear_templates
                        WHERE status = 'complete'
                          AND source_key <> ALL(%s::text[])
                          AND COALESCE(class_key, '') <> ''
                          AND COALESCE(spec_key, '') <> ''
                    )
                    UPDATE cache.websim_community_gear_templates AS template
                    SET expires_at = %s,
                        updated_at = %s,
                        payload_json = jsonb_set(
                            COALESCE(template.payload_json, '{}'::jsonb),
                            '{communityTemplateFreshness}',
                            %s::jsonb,
                            true
                        )
                    FROM ranked
                    WHERE template.id = ranked.id
                      AND ranked.availability_rank = 1
                      AND (
                          template.expires_at IS NULL
                          OR template.expires_at <= %s
                          OR NOT (COALESCE(template.payload_json, '{}'::jsonb) ? 'communityTemplateFreshness')
                      )
                    """,
                    (
                        blocked_gear_sources,
                        availability_expires_at,
                        checked_at,
                        json_param(freshness_payload),
                        checked_at,
                    ),
                )
                gear_restored = cur.rowcount
        return {
            "status": "completed",
            "checkedAt": checked_at,
            "availabilityExpiresAt": availability_expires_at,
            "talentRestored": max(0, int(talent_restored or 0)),
            "gearRestored": max(0, int(gear_restored or 0)),
        }

    def _reconcile_community_gear_slot_coverage(self, cur, source_keys, scan_run_id=""):
        if not source_keys:
            return 0
        cur.execute(
            """
            SELECT id, class_key, spec_key, source_status, status, ready_slot_count,
                   missing_slots_json, gear_items_json, payload_json
            FROM cache.websim_community_gear_templates
            WHERE source_key = ANY(%s::text[])
              AND status IN ('complete', 'partial')
            """,
            (list(source_keys),),
        )
        rows = cur.fetchall()
        all_gear_items = []
        for row in rows:
            all_gear_items.extend(
                item for item in _json_value(row[7], []) if isinstance(item, dict)
            )
        official_metadata_by_id = self._official_item_metadata_by_id(cur, all_gear_items)
        reconciled = 0
        checked_at = utc_now()
        for row in rows:
            (
                existing_id,
                class_key,
                spec_key,
                source_status,
                status,
                ready_slot_count,
                missing_slots_json,
                gear_items_json,
                payload_json,
            ) = row
            gear_items = _json_value(gear_items_json, [])
            if official_metadata_by_id:
                gear_items = [
                    apply_item_metadata(
                        item,
                        official_metadata_by_id.get(
                            str((item or {}).get("itemId") or (item or {}).get("id") or "").strip()
                        ),
                    )
                    if isinstance(item, dict)
                    else item
                    for item in gear_items
                ]
            ready_by_slot, occupied_slots, missing_slots = gear_template_slot_coverage(
                gear_items,
                class_key,
                spec_key,
            )
            ready_count = len(CANONICAL_GEAR_SLOTS) - len(missing_slots)
            next_status = "complete" if not missing_slots else "partial"
            next_source_status = "synced" if next_status == "complete" else "partial"
            current_missing_slots = _json_value(missing_slots_json, [])
            if (
                status == next_status
                and source_status == next_source_status
                and _int_value(ready_slot_count) == ready_count
                and current_missing_slots == missing_slots
            ):
                continue
            payload = _json_value(payload_json, {})
            if not isinstance(payload, dict):
                payload = {}
            payload = {
                **payload,
                "readySlotCount": ready_count,
                "missingSlots": missing_slots,
                "occupiedSlots": occupied_slots,
                "slotCoverageAudit": {
                    "status": next_status,
                    "checkedAt": checked_at,
                    "reason": "stored_status_recomputed_from_current_slot_coverage",
                },
            }
            cur.execute(
                """
                UPDATE cache.websim_community_gear_templates
                SET source_status = %s,
                    status = %s,
                    ready_slot_count = %s,
                    missing_slots_json = %s::jsonb,
                    payload_json = %s::jsonb,
                    updated_at = %s,
                    scan_run_id = %s
                WHERE id = %s
                  AND status IN ('complete', 'partial')
                """,
                (
                    next_source_status,
                    next_status,
                    ready_count,
                    json_param(missing_slots),
                    json_param(payload),
                    checked_at,
                    scan_run_id or checked_at,
                    existing_id,
                ),
            )
            reconciled += 1
        return reconciled

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
        candidate_downgrade_ids = [
            row["id"] for row in normalized_rows if row.get("status") != "complete"
        ]
        source_keys = {
            row.get("sourceKey") for row in normalized_rows if row.get("sourceKey")
        }
        with self.connection() as conn:
            with conn.cursor() as cur:
                invalid_existing_complete_ids = set()
                if candidate_downgrade_ids:
                    cur.execute(
                        """
                        SELECT id, class_key, spec_key, gear_items_json
                        FROM cache.websim_community_gear_templates
                        WHERE id = ANY(%s::text[])
                          AND status = 'complete'
                        """,
                        (candidate_downgrade_ids,),
                    )
                    existing_complete_rows = cur.fetchall()
                    all_existing_items = []
                    for row in existing_complete_rows:
                        all_existing_items.extend(
                            item for item in _json_value(row[3], []) if isinstance(item, dict)
                        )
                    official_metadata_by_id = self._official_item_metadata_by_id(cur, all_existing_items)
                    for existing_id, class_key, spec_key, gear_items_json in existing_complete_rows:
                        gear_items = _json_value(gear_items_json, [])
                        if official_metadata_by_id:
                            gear_items = [
                                apply_item_metadata(
                                    item,
                                    official_metadata_by_id.get(
                                        str((item or {}).get("itemId") or (item or {}).get("id") or "").strip()
                                    ),
                                )
                                if isinstance(item, dict)
                                else item
                                for item in gear_items
                            ]
                        _ready_by_slot, _occupied_slots, missing_slots = gear_template_slot_coverage(
                            gear_items,
                            class_key,
                            spec_key,
                        )
                        if missing_slots:
                            invalid_existing_complete_ids.add(existing_id)
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
                        WHERE NOT (
                            cache.websim_community_gear_templates.status = 'complete'
                            AND EXCLUDED.status <> 'complete'
                            AND NOT (
                                cache.websim_community_gear_templates.id = ANY(%s::text[])
                            )
                        )
                          AND NOT (
                            cache.websim_community_gear_templates.status <> 'complete'
                            AND EXCLUDED.status <> 'complete'
                            AND cache.websim_community_gear_templates.ready_slot_count > EXCLUDED.ready_slot_count
                        )
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
                            list(invalid_existing_complete_ids),
                        ),
                    )
                self._reconcile_community_gear_slot_coverage(
                    cur,
                    source_keys,
                    scan_run_id=scan_run_id,
                )
        return self.community_gear_template_counts()

    def _trusted_observed_variant_item(self, row):
        (
            variant_id,
            item_id,
            item_name,
            slot,
            item_level,
            simc_options_json,
            status,
            blockers_json,
            variant_payload_json,
            item_payload_json,
            updated_at,
        ) = row
        variant_payload = _json_value(variant_payload_json, {})
        item_payload = _json_value(item_payload_json, {})
        simc_options = _json_value(simc_options_json, {})
        blockers = _json_value(blockers_json, [])
        class_key = slugify(variant_payload.get("classKey") or item_payload.get("classKey"), "")
        spec_key = slugify(variant_payload.get("specKey") or item_payload.get("specKey"), "")
        stat_source = str(variant_payload.get("statSource") or "").strip().lower()
        trusted_stats = stat_source in {"simulationcraft", "simulationcraft_json"} and bool(
            variant_payload.get("itemStats") or variant_payload.get("stats")
        )
        if not class_key or not spec_key or not trusted_stats:
            return None
        item = {
            **(item_payload if isinstance(item_payload, dict) else {}),
            **(variant_payload if isinstance(variant_payload, dict) else {}),
            **(simc_options if isinstance(simc_options, dict) else {}),
            "id": str(item_id or ""),
            "itemId": str(item_id or ""),
            "name": item_name or f"item_{item_id}",
            "displayName": item_name or str(item_id or ""),
            "slot": normalize_slot(slot),
            "ilevel": _int_value(item_level),
            "itemLevel": _int_value(item_level),
            "sourceType": "observed_profile",
            "source": variant_payload.get("sourceLabel") or "Raider.IO observed gear",
            "classKey": class_key,
            "specKey": spec_key,
            "variantKey": str(variant_payload.get("variantKey") or variant_id or ""),
            "variantSource": "observed_profile",
            "variantStatus": status or "",
            "variantBlockers": blockers,
            "updatedAt": str(updated_at or ""),
            "observedProfileRefs": [
                {
                    "sourceType": "observed_profile",
                    "sourceName": variant_payload.get("sourceLabel") or "Raider.IO observed profile",
                    "profileUrl": variant_payload.get("profileUrl") or "",
                    "classKey": class_key,
                    "specKey": spec_key,
                    "updatedAt": str(updated_at or ""),
                }
            ],
        }
        return normalize_gear_item(item, class_key, spec_key, "observed_profile")

    def _build_observed_community_gear_templates(self, scan_run_id=""):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT v.id, v.item_id, COALESCE(NULLIF(i.name, ''), v.item_id),
                           v.slot, v.item_level, v.simc_options_json, v.status,
                           v.blockers_json, v.payload_json, i.payload_json, v.updated_at
                    FROM cache.websim_gear_variants v
                    LEFT JOIN cache.websim_items i ON i.id = v.item_id
                    WHERE v.source_type = 'observed_profile'
                      AND v.status IN ('verified', 'partial')
                    ORDER BY COALESCE(v.payload_json->>'classKey', ''),
                             COALESCE(v.payload_json->>'specKey', ''),
                             v.updated_at DESC,
                             v.item_id,
                             v.slot
                    """
                )
                rows = cur.fetchall()
        items_by_spec = {}
        for row in rows or []:
            item = self._trusted_observed_variant_item(row)
            if not item:
                continue
            class_key = slugify(item.get("classKey"), "")
            spec_key = slugify(item.get("specKey"), "")
            if not class_key or not spec_key:
                continue
            items_by_spec.setdefault((class_key, spec_key), []).append(item)
        templates = []
        for (class_key, spec_key), items in items_by_spec.items():
            template = gear_community_template_from_observed_items(items, class_key, spec_key)
            if template:
                templates.append({**template, "scanRunId": scan_run_id})
        return templates

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
        templates.extend(self._build_observed_community_gear_templates(scan_run_id=scan_run_id))
        return dedupe_gear_community_templates(templates)

    def _season_recommended_talent_anchor(self, class_key, spec_key):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, class_key, spec_key, hero_key, source_key, source_name,
                           source_status, status, payload_json, updated_at
                    FROM cache.websim_community_talent_templates
                    WHERE class_key = %s
                      AND spec_key = %s
                      AND status = 'verified'
                      AND source_key NOT IN ('websim_baseline', 'manual_fixture', 'fallback')
                      AND (expires_at IS NULL OR expires_at > now())
                    ORDER BY CASE source_key WHEN 'raiderio' THEN 0 WHEN 'warcraftlogs' THEN 1 ELSE 2 END,
                             sample_count DESC,
                             max_key_level DESC,
                             updated_at DESC
                    LIMIT 1
                    """,
                    (class_key, spec_key),
                )
                row = cur.fetchone()
        if not row:
            return {
                "status": "blocked",
                "reason": "missing verified community talent anchor",
                "nextAction": "refresh_community_talent_templates",
            }
        payload = _json_value(row[8], {})
        payload = payload if isinstance(payload, dict) else {}
        return {
            "templateId": str(row[0] or ""),
            "classKey": row[1] or class_key,
            "specKey": row[2] or spec_key,
            "heroKey": row[3] or "",
            "sourceKey": row[4] or "",
            "sourceName": row[5] or "",
            "sourceStatus": row[6] or "",
            "status": row[7] or "",
            "evidenceTier": payload.get("evidenceTier") or row[7] or "",
            "updatedAt": str(row[9] or ""),
        }

    def build_season_recommended_gear_templates(self, scan_run_id=""):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, class_key, spec_key, name, source_key, source_name, source_url,
                           source_status, status, signature, source_refs_json, gear_items_json,
                           raw_string, ready_slot_count, missing_slots_json, analysis_window,
                           payload_json, updated_at, expires_at, scan_run_id
                    FROM cache.websim_community_gear_templates
                    WHERE status = 'complete'
                      AND source_key NOT IN (
                          %s, %s, 'baseline_template', 'simc_preset', 'baseline_blocked'
                      )
                      AND (expires_at IS NULL OR expires_at > now())
                    ORDER BY class_key, spec_key, ready_slot_count DESC, updated_at DESC, name
                    LIMIT 500
                    """,
                    (SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY, DEFAULT_GEAR_TEMPLATE_SOURCE_KEY),
                )
                rows = cur.fetchall()
                all_gear_items = []
                for row in rows or []:
                    all_gear_items.extend(item for item in _json_value(row[11], []) if isinstance(item, dict))
                official_metadata_by_id = self._official_item_metadata_by_id(cur, all_gear_items)

        grouped = {}
        for row in rows or []:
            template = self._community_gear_template_from_row(row, official_metadata_by_id, normalize_coverage=True)
            class_key = slugify(template.get("classKey"), "")
            spec_key = slugify(template.get("specKey"), "")
            if not class_key or not spec_key or not is_real_community_gear_template(template):
                continue
            if template.get("status") != "complete" or template.get("missingSlots"):
                continue
            grouped.setdefault((class_key, spec_key), []).append(template)

        generated = []
        checked_at = utc_now()
        for (class_key, spec_key), candidates in sorted(grouped.items()):
            best = select_community_best_gear_templates(candidates, class_key, spec_key)[0]
            role = specialization_role(class_key, spec_key)
            role_for_policy = role if role in {"tank", "healer", "support"} else ""
            talent_anchor = self._season_recommended_talent_anchor(class_key, spec_key)
            if talent_anchor.get("status") == "blocked":
                continue
            evidence = {
                "optimizerRunId": scan_run_id or checked_at,
                "scenarioKey": "mplus_aoe",
                "checkedAt": checked_at,
                "sourceKey": SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY,
                "candidateCount": len(candidates),
                "simcRunCount": 0,
                "role": role_for_policy,
                "specializationRole": role,
                "talentAnchor": talent_anchor,
                "seedTemplateId": best.get("id") or "",
                "seedTemplateSourceKey": best.get("sourceKey") or "",
                "seedTemplateSignature": best.get("signature") or "",
                "sourceRefs": normalize_source_refs(best.get("sourceRefs") or []),
                "warnings": [
                    "first version uses verified complete community gear winner as current-season recommendation seed before SimC optimizer verification"
                ],
                "blockers": [],
            }
            try:
                template = build_season_recommended_gear_template(
                    class_key,
                    spec_key,
                    best.get("gearItems") or [],
                    evidence=evidence,
                )
            except ValueError:
                continue
            template["scanRunId"] = scan_run_id
            generated.append(template)
        return dedupe_gear_community_templates(generated)

    def community_gear_template_coverage_rows(self):
        return self.admin_gate_gear_template_records().get("communityGearTemplates") or []

    def _backfill_simc_options(self, item, item_level):
        options = {}
        if item_level:
            options["ilevel"] = str(item_level)
        observed_options = observed_gear_simc_options(item)
        if isinstance(observed_options, dict):
            options.update(observed_options)
        for key in ("bonus_id", "gem_id", "gem_bonus_id", "gem_ilevel", "enchant_id", "crafted_stats", "embellishment"):
            value = item.get(key) or item.get(key.replace("_", ""))
            if value not in (None, "", [], {}):
                options[key] = str(value)
        return options

    def _observed_backfill_stat_payload(self, item, profile_simc_gear):
        trusted_payload = observed_variant_stat_payload_fields(item)
        if trusted_payload:
            return trusted_payload
        return simc_observed_variant_stat_payload(item, profile_simc_gear)

    def _observed_profile_simc_text(self, profile):
        profile = profile if isinstance(profile, dict) else {}
        class_key = slugify(profile.get("classKey") or profile.get("classSlug") or profile.get("className"), "mage")
        spec_key = slugify(profile.get("specKey") or profile.get("specSlug") or profile.get("specName"), "")
        character_name = str(profile.get("characterName") or profile.get("name") or "observed_profile").strip() or "observed_profile"
        gear_items = []
        for raw_item in profile.get("gear") or []:
            if not isinstance(raw_item, dict):
                continue
            item = dict(raw_item)
            item["sourceType"] = "manual"
            item["ilevel"] = item.get("ilevel") or item.get("itemLevel") or item.get("item_level")
            item.update(observed_gear_simc_options(item))
            gear_items.append(item)
        lines = []
        for item in normalize_websim_gear_items(gear_items, class_key, spec_key, "manual"):
            if not isinstance(item, dict) or not item.get("simcReady"):
                continue
            item_id = str(item.get("id") or item.get("itemId") or "").strip()
            if not item_id:
                continue
            parts = [f"{item['slot']}=", f"id={item_id}"]
            for key in ("ilevel", "bonus_id", "gem_id", "gem_bonus_id", "gem_ilevel", "enchant_id", "crafted_stats", "embellishment"):
                if item.get(key):
                    parts.append(f"{key}={item[key]}")
            lines.append(",".join(parts))
        if not lines:
            return "", ["observed profile has no SimC-ready gear lines"]
        if not any(line.startswith("main_hand=") for line in lines):
            lines.insert(0, "main_hand=worn_shortsword,id=25")
        profile_lines = [
            f'{class_key}="{character_name}"',
            "level=90",
            f"race={DEFAULT_RACE_BY_CLASS.get(class_key, 'troll')}",
            f"spec={spec_key}" if spec_key else "",
            "iterations=1",
            "default_actions=1",
            *lines,
        ]
        return "\n".join(line for line in profile_lines if line) + "\n", []

    def _run_observed_profile_simc_json(self, profile, timeout_seconds=90):
        profile_text, errors = self._observed_profile_simc_text(profile)
        if errors:
            return {"ok": False, "errors": errors}
        binary = websim_simc_binary()
        if not binary:
            return {"ok": False, "errors": ["simcraft binary not found"]}
        with tempfile.TemporaryDirectory(prefix="wow-pg-observed-simc-") as tmp_dir:
            output_path = Path(tmp_dir) / "observed-profile.json"
            try:
                completed = run_websim_simcraft_process(
                    binary,
                    profile_with_simc_json_output(profile_text, output_path),
                    max(1, int(timeout_seconds or 90)),
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                return {"ok": False, "errors": [str(error)]}
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or f"simc exited {completed.returncode}").strip()
                return {"ok": False, "errors": [detail[:1000] if detail else f"simc exited {completed.returncode}"]}
            if not output_path.exists():
                detail = (completed.stderr or completed.stdout or "SimulationCraft did not write JSON output").strip()
                return {"ok": False, "errors": [detail[:1000]]}
            try:
                return json.loads(output_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                return {"ok": False, "errors": [f"SimulationCraft JSON parse failed: {error}"]}

    def _observed_item_probe_context(self, profiles):
        gear_items = []
        for profile in profiles or []:
            if not isinstance(profile, dict):
                continue
            for item in profile.get("gear") or []:
                if isinstance(item, dict):
                    gear_items.append(item)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT class_key, spec_key, name, profile
                    FROM cache.websim_profile_presets
                    WHERE profile <> ''
                    ORDER BY class_key, spec_key, id
                    """
                )
                profile_rows = cur.fetchall()
                metadata_by_id = self._official_item_metadata_by_id(cur, gear_items)
                cur.execute(
                    """
                    SELECT item_id, slot, item_level, simc_options_json, payload_json
                    FROM cache.websim_gear_variants
                    WHERE source_type = 'observed_profile'
                      AND status = 'verified'
                    """
                )
                existing_stats = {}
                for item_id, slot, item_level, simc_options_json, payload_json in cur.fetchall():
                    payload = _json_value(payload_json, {})
                    stat_payload = observed_variant_stat_payload_fields(payload)
                    if not stat_payload:
                        continue
                    key = observed_variant_stat_identity_key(
                        item_id,
                        slot,
                        item_level,
                        _json_value(simc_options_json, {}),
                    )
                    existing_stats.setdefault(key, stat_payload)
        return {
            "profileRows": profile_rows,
            "metadataById": metadata_by_id,
            "existingStats": existing_stats,
        }

    def _observed_item_probe_simc_profiles(self, item, profile_preset_rows):
        item = item if isinstance(item, dict) else {}
        item_level = _int_value(item.get("itemLevel") or item.get("ilevel") or item.get("item_level"))
        simc_slot = official_item_level_probe_simc_slot(item.get("slot"))
        item_id = str(item.get("itemId") or item.get("item_id") or item.get("id") or "").strip()
        if not item_id or not item_level or not simc_slot:
            return [], "", ["observed item probe missing item id, item level, or slot"]
        by_pair = {}
        profile_order = []
        for row in profile_preset_rows or []:
            if len(row) < 4:
                continue
            class_key = slugify(row[0], "")
            spec_key = slugify(row[1], "")
            profile = str(row[3] or "")
            if not class_key or not spec_key or not profile.strip():
                continue
            pair = (class_key, spec_key)
            if pair not in by_pair:
                by_pair[pair] = profile
                profile_order.append(pair)
        candidates = list(item_level_probe_profile_candidates(item))
        source_class = slugify(item.get("classKey"), "")
        if source_class:
            for pair in profile_order:
                if pair[0] == source_class and pair not in candidates:
                    candidates.insert(0, pair)
        for fallback in profile_order:
            if fallback not in candidates:
                candidates.append(fallback)

        safe_name = simc_safe_item_name(item.get("name") or item.get("displayName") or f"item_{item_id}", item_id)
        simc_options = self._backfill_simc_options(item, item_level)
        options = [f"id={item_id}", f"ilevel={item_level}"]
        for key in ("bonus_id", "gem_id", "gem_bonus_id", "gem_ilevel", "enchant_id", "crafted_stats", "embellishment"):
            value = simc_options.get(key)
            if value:
                options.append(f"{key}={value}")
        item_line = f"{simc_slot}={safe_name},{','.join(options)}"
        remove_slots = {simc_slot}
        if simc_slot == "main_hand" and item_level_probe_main_hand_removes_offhand(item):
            remove_slots.add("off_hand")
        probe_override_keys = {"iterations", "max_time", "target_error", "calculate_scale_factors", "json"}
        profiles = []
        for class_key, spec_key in candidates:
            profile = by_pair.get((class_key, spec_key))
            if not profile:
                continue
            lines = []
            for line in profile.splitlines():
                stripped = line.strip()
                if not stripped or "=" not in stripped:
                    lines.append(line)
                    continue
                head = stripped.split("=", 1)[0].strip()
                if head in probe_override_keys or head in remove_slots:
                    continue
                lines.append(line)
            lines.extend(
                [
                    "iterations=1",
                    "max_time=1",
                    "target_error=0.5",
                    "calculate_scale_factors=0",
                    item_line,
                ]
            )
            profiles.append(("\n".join(lines).strip() + "\n", class_key, spec_key, item_line))
        if profiles:
            return profiles, item_line, []
        return [], item_line, ["no compatible SimC profile preset found for observed item probe"]

    def _observed_item_probe_simc_text(self, item, profile_preset_rows):
        profiles, item_line, errors = self._observed_item_probe_simc_profiles(item, profile_preset_rows)
        if errors:
            return "", "", "", item_line, errors
        profile_text, class_key, spec_key, item_line = profiles[0]
        return profile_text, class_key, spec_key, item_line, []

    def _run_observed_item_probe_simc_json(self, profile_text, timeout_seconds=90):
        binary = websim_simc_binary()
        if not binary:
            return {"ok": False, "errors": ["simcraft binary not found"]}
        with tempfile.TemporaryDirectory(prefix="wow-pg-observed-item-probe-") as tmp_dir:
            output_path = Path(tmp_dir) / "observed-item-probe.json"
            try:
                completed = run_websim_simcraft_process(
                    binary,
                    profile_with_simc_json_output(profile_text, output_path),
                    max(1, int(timeout_seconds or 90)),
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                return {"ok": False, "errors": [str(error)]}
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or f"simc exited {completed.returncode}").strip()
                return {"ok": False, "errors": [detail[:1000] if detail else f"simc exited {completed.returncode}"]}
            if not output_path.exists():
                detail = (completed.stderr or completed.stdout or "SimulationCraft did not write JSON output").strip()
                return {"ok": False, "errors": [detail[:1000]]}
            try:
                return json.loads(output_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                return {"ok": False, "errors": [f"SimulationCraft JSON parse failed: {error}"]}

    def _observed_item_probe_stat_payload(self, item, profile_preset_rows, metadata_by_id=None, timeout_seconds=90):
        item = dict(item) if isinstance(item, dict) else {}
        item_id = str(item.get("itemId") or item.get("item_id") or item.get("id") or "").strip()
        metadata = (metadata_by_id or {}).get(item_id)
        if metadata:
            item = apply_item_metadata(item, metadata)
            if isinstance(metadata.get("payload"), dict):
                item["metadataPayload"] = metadata.get("payload")
        profile_candidates, _item_line, errors = self._observed_item_probe_simc_profiles(item, profile_preset_rows)
        if errors:
            return {}, errors
        probe_errors = []
        for profile_text, class_key, spec_key, item_line in profile_candidates:
            simc_payload = self._run_observed_item_probe_simc_json(profile_text, timeout_seconds=timeout_seconds)
            if isinstance(simc_payload, dict) and simc_payload.get("ok") is False:
                probe_errors.extend(str(error) for error in simc_payload.get("errors") or [] if str(error).strip())
                continue
            stat_payload = simc_observed_variant_stat_payload(item, simc_json_gear_stats_by_slot(simc_payload))
            if not stat_payload:
                probe_errors.append(f"SimC observed item probe did not include matching target item stats for {class_key}:{spec_key}")
                continue
            stat_payload.update(
                {
                    "derivedVariantSource": "simulationcraft_observed_item_probe",
                    "simcProfile": item_line,
                    "probeClassKey": class_key,
                    "probeSpecKey": spec_key,
                    "simcCheckedAt": utc_now(),
                }
            )
            return stat_payload, []
        return {}, probe_errors[:12] or ["SimC observed item probe did not include matching target item stats"]

    def _write_backfill_gear_rows(self, rows):
        counts = {
            "itemCount": 0,
            "sourceCount": 0,
            "variantCount": 0,
            "verifiedCount": 0,
            "partialCount": 0,
            "blockedCount": 0,
            "errors": [],
        }
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
            default_status = "verified" if len(simc_options) > 1 else "partial"
            status = str(row.get("status") or default_status).strip() or default_status
            blockers = unique_text_list(row.get("blockers") or [])
            if source_type == "observed_profile":
                if observed_variant_stat_payload_fields(row):
                    status = "verified" if not blockers else "partial"
                else:
                    status = "partial"
                    if len(simc_options) > 1:
                        blockers = unique_text_list([*blockers, "missing SimulationCraft item stats"])
                    else:
                        blockers = unique_text_list([*blockers, "missing deterministic SimC variant preset"])
            difficulty_key = str(row.get("difficultyKey") or source_type).strip()
            variant_key = str(row.get("variantKey") or f"{difficulty_key}-{slot}-{item_level}-{json_param(simc_options)}")
            variant_identity = (item_id, variant_key)
            if variant_identity in seen_variants:
                continue
            seen_variants.add(variant_identity)
            if status == "verified":
                counts["verifiedCount"] += 1
            elif status == "blocked":
                counts["blockedCount"] += 1
            else:
                counts["partialCount"] += 1
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
                    "status": status,
                    "blockers": blockers,
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
                            name = CASE
                                WHEN (
                                    COALESCE(cache.websim_items.payload_json #>> '{_metadata,source}', cache.websim_items.payload_json->>'metadataSource', '') = 'Battle.net Game Data API'
                                    OR (
                                        cache.websim_items.source_status = 'verified'
                                        AND COALESCE(cache.websim_items.payload_json #>> '{_metadata,iconUrl}', cache.websim_items.payload_json->>'iconUrl', '') <> ''
                                        AND (
                                            cache.websim_items.payload_json ? 'inventory_type'
                                            OR cache.websim_items.payload_json ? 'inventoryType'
                                            OR cache.websim_items.payload_json ? 'item_class'
                                            OR cache.websim_items.payload_json ? 'itemClass'
                                            OR cache.websim_items.payload_json ? 'item_subclass'
                                            OR cache.websim_items.payload_json ? 'itemSubclass'
                                        )
                                    )
                                )
                                THEN cache.websim_items.name
                                ELSE COALESCE(NULLIF(EXCLUDED.name, ''), cache.websim_items.name)
                            END,
                            slot = CASE
                                WHEN (
                                    COALESCE(cache.websim_items.payload_json #>> '{_metadata,source}', cache.websim_items.payload_json->>'metadataSource', '') = 'Battle.net Game Data API'
                                    OR (
                                        cache.websim_items.source_status = 'verified'
                                        AND COALESCE(cache.websim_items.payload_json #>> '{_metadata,iconUrl}', cache.websim_items.payload_json->>'iconUrl', '') <> ''
                                        AND (
                                            cache.websim_items.payload_json ? 'inventory_type'
                                            OR cache.websim_items.payload_json ? 'inventoryType'
                                            OR cache.websim_items.payload_json ? 'item_class'
                                            OR cache.websim_items.payload_json ? 'itemClass'
                                            OR cache.websim_items.payload_json ? 'item_subclass'
                                            OR cache.websim_items.payload_json ? 'itemSubclass'
                                        )
                                    )
                                )
                                THEN cache.websim_items.slot
                                ELSE COALESCE(NULLIF(EXCLUDED.slot, ''), cache.websim_items.slot)
                            END,
                            item_level = CASE
                                WHEN (
                                    COALESCE(cache.websim_items.payload_json #>> '{_metadata,source}', cache.websim_items.payload_json->>'metadataSource', '') = 'Battle.net Game Data API'
                                    OR (
                                        cache.websim_items.source_status = 'verified'
                                        AND COALESCE(cache.websim_items.payload_json #>> '{_metadata,iconUrl}', cache.websim_items.payload_json->>'iconUrl', '') <> ''
                                        AND (
                                            cache.websim_items.payload_json ? 'inventory_type'
                                            OR cache.websim_items.payload_json ? 'inventoryType'
                                            OR cache.websim_items.payload_json ? 'item_class'
                                            OR cache.websim_items.payload_json ? 'itemClass'
                                            OR cache.websim_items.payload_json ? 'item_subclass'
                                            OR cache.websim_items.payload_json ? 'itemSubclass'
                                        )
                                    )
                                )
                                THEN cache.websim_items.item_level
                                ELSE COALESCE(EXCLUDED.item_level, cache.websim_items.item_level)
                            END,
                            payload_json = CASE
                                WHEN (
                                    COALESCE(cache.websim_items.payload_json #>> '{_metadata,source}', cache.websim_items.payload_json->>'metadataSource', '') = 'Battle.net Game Data API'
                                    OR (
                                        cache.websim_items.source_status = 'verified'
                                        AND COALESCE(cache.websim_items.payload_json #>> '{_metadata,iconUrl}', cache.websim_items.payload_json->>'iconUrl', '') <> ''
                                        AND (
                                            cache.websim_items.payload_json ? 'inventory_type'
                                            OR cache.websim_items.payload_json ? 'inventoryType'
                                            OR cache.websim_items.payload_json ? 'item_class'
                                            OR cache.websim_items.payload_json ? 'itemClass'
                                            OR cache.websim_items.payload_json ? 'item_subclass'
                                            OR cache.websim_items.payload_json ? 'itemSubclass'
                                        )
                                    )
                                )
                                THEN cache.websim_items.payload_json
                                ELSE EXCLUDED.payload_json
                            END,
                            source_status = CASE
                                WHEN (
                                    COALESCE(cache.websim_items.payload_json #>> '{_metadata,source}', cache.websim_items.payload_json->>'metadataSource', '') = 'Battle.net Game Data API'
                                    OR (
                                        cache.websim_items.source_status = 'verified'
                                        AND COALESCE(cache.websim_items.payload_json #>> '{_metadata,iconUrl}', cache.websim_items.payload_json->>'iconUrl', '') <> ''
                                        AND (
                                            cache.websim_items.payload_json ? 'inventory_type'
                                            OR cache.websim_items.payload_json ? 'inventoryType'
                                            OR cache.websim_items.payload_json ? 'item_class'
                                            OR cache.websim_items.payload_json ? 'itemClass'
                                            OR cache.websim_items.payload_json ? 'item_subclass'
                                            OR cache.websim_items.payload_json ? 'itemSubclass'
                                        )
                                    )
                                )
                                THEN cache.websim_items.source_status
                                ELSE EXCLUDED.source_status
                            END,
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
                        WHERE NOT (
                            cache.websim_gear_variants.status = 'verified'
                            AND EXCLUDED.status <> 'verified'
                        )
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

    def backfill_observed_gear_from_raiderio(
        self,
        raiderio_payload,
        mode="scheduled",
        target_limit=None,
        profile_limit=None,
        timeout_seconds=None,
        enable_simc_stats=None,
        full_profile_gear=None,
        item_probe_limit=None,
    ):
        rows = []
        profile_count = 0
        available_profile_count = 0
        simc_profile_count = 0
        simc_resolved_profile_count = 0
        simc_resolved_slot_count = 0
        simc_item_probe_count = 0
        simc_item_probe_resolved_count = 0
        simc_errors = []
        target_limit_value = None if target_limit is None else max(0, _int_value(target_limit, 0))
        profile_limit_value = None if profile_limit is None else max(0, _int_value(profile_limit, 0))
        timeout_seconds_value = None if timeout_seconds is None else max(0, _int_value(timeout_seconds, 0))
        item_probe_limit_value = None if item_probe_limit is None else max(0, _int_value(item_probe_limit, 0))
        if target_limit_value == 0:
            stop_reason = "target_limit_reached"
        else:
            stop_reason = ""
        if profile_limit_value == 0 and not stop_reason:
            stop_reason = "profile_limit_reached"
        deadline_at = time.monotonic() + timeout_seconds_value if timeout_seconds_value else None
        profiles = [profile for profile in (raiderio_payload or {}).get("profiles") or [] if isinstance(profile, dict)]
        item_probe_context = None
        item_probe_cache = {}
        existing_verified_identities = self._existing_verified_observed_variant_identities()
        skipped_existing_verified = 0

        def load_item_probe_context():
            nonlocal item_probe_context
            if item_probe_context is None:
                item_probe_context = self._observed_item_probe_context(profiles)
            return item_probe_context

        for profile in profiles:
            if not isinstance(profile, dict):
                continue
            available_profile_count += 1
            if stop_reason in {"target_limit_reached", "profile_limit_reached"}:
                break
            if profile_limit_value is not None and profile_count >= profile_limit_value:
                stop_reason = "profile_limit_reached"
                break
            if deadline_at and time.monotonic() >= deadline_at:
                stop_reason = "timeout_reached"
                break
            profile_count += 1
            profile_ref = profile.get("profileUrl") or profile.get("url") or profile.get("name") or ""
            profile_simc_gear = simc_json_gear_stats_by_slot(profile)
            if enable_simc_stats and not profile_simc_gear:
                simc_profile_count += 1
                simc_payload = self._run_observed_profile_simc_json(profile, timeout_seconds=timeout_seconds_value or 90)
                if isinstance(simc_payload, dict) and simc_payload.get("ok") is False:
                    simc_errors.extend(str(error) for error in simc_payload.get("errors") or [] if str(error).strip())
                else:
                    profile_simc_gear = simc_json_gear_stats_by_slot(simc_payload)
                    if profile_simc_gear:
                        simc_resolved_profile_count += 1
                        simc_resolved_slot_count += len(profile_simc_gear)
                    else:
                        simc_errors.append("SimulationCraft JSON did not include target item stats")
            for item in profile.get("gear") or []:
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("itemId") or item.get("item_id") or item.get("id") or "").strip()
                slot = normalize_slot(item.get("slot") or item.get("simcSlot") or item.get("slotKey") or item.get("equipmentSlot"))
                item_level = _int_value(item.get("itemLevel") or item.get("ilevel") or item.get("item_level"))
                simc_options = self._backfill_simc_options(item, item_level) if item_id and slot and item_level else {}
                identity_key = observed_variant_stat_identity_key(item_id, slot, item_level, simc_options)
                if identity_key in existing_verified_identities:
                    skipped_existing_verified += 1
                    continue
                if target_limit_value is not None and len(rows) >= target_limit_value:
                    stop_reason = "target_limit_reached"
                    break
                row_item = {
                    key: value
                    for key, value in item.items()
                    if key
                    not in {
                        "itemStats",
                        "stats",
                        "statSummary",
                        "statSource",
                        "statSourceDetail",
                        "statDisplayStatus",
                    }
                }
                row = {
                    **row_item,
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "sourceKey": f"observed:{profile_ref}:{item.get('itemId') or item.get('id')}",
                    "sourceLabel": f"Raider.IO observed profile: {profile.get('name') or 'profile'}",
                    "profileUrl": profile.get("profileUrl") or "",
                    "classKey": profile.get("classKey") or item.get("classKey") or "",
                    "specKey": profile.get("specKey") or item.get("specKey") or "",
                }
                stat_payload = self._observed_backfill_stat_payload({**item, **row}, profile_simc_gear)
                if enable_simc_stats and not stat_payload and item_probe_limit_value:
                    context = load_item_probe_context()
                    probe_item = {**item, **row}
                    simc_options = self._backfill_simc_options(
                        probe_item,
                        _int_value(probe_item.get("itemLevel") or probe_item.get("ilevel") or probe_item.get("item_level")),
                    )
                    probe_key = observed_variant_stat_identity_key(
                        probe_item.get("itemId") or probe_item.get("id"),
                        probe_item.get("slot"),
                        probe_item.get("itemLevel") or probe_item.get("ilevel") or probe_item.get("item_level"),
                        simc_options,
                    )
                    cached_payload = (context.get("existingStats") or {}).get(probe_key)
                    if cached_payload:
                        stat_payload = cached_payload
                    elif probe_key in item_probe_cache:
                        stat_payload = item_probe_cache[probe_key]
                    elif simc_item_probe_count < item_probe_limit_value:
                        simc_item_probe_count += 1
                        stat_payload, probe_errors = self._observed_item_probe_stat_payload(
                            probe_item,
                            context.get("profileRows") or [],
                            context.get("metadataById") or {},
                            timeout_seconds=timeout_seconds_value or 90,
                        )
                        item_probe_cache[probe_key] = stat_payload
                        if stat_payload:
                            simc_item_probe_resolved_count += 1
                        else:
                            simc_errors.extend(str(error) for error in (probe_errors or []) if str(error).strip())
                if stat_payload:
                    row.update(stat_payload)
                    row["status"] = "verified"
                else:
                    row["status"] = "partial"
                rows.append(row)
            if stop_reason:
                break
        result = self._write_backfill_gear_rows(rows)
        result["runner"] = "postgres"
        result["mode"] = mode
        result["observedProfileCount"] = profile_count
        result["availableProfileCount"] = available_profile_count
        result["processedProfileCount"] = profile_count
        result["processedItemCount"] = len(rows)
        result["targetLimit"] = target_limit_value
        result["profileLimit"] = profile_limit_value
        result["timeoutSeconds"] = timeout_seconds_value
        result["enableSimcStats"] = bool(enable_simc_stats)
        result["fullProfileGear"] = bool(full_profile_gear)
        result["itemProbeLimit"] = item_probe_limit_value
        result["simcProfileCount"] = simc_profile_count
        result["simcResolvedProfileCount"] = simc_resolved_profile_count
        result["simcResolvedSlotCount"] = simc_resolved_slot_count
        result["simcItemProbeCount"] = simc_item_probe_count
        result["simcItemProbeResolvedCount"] = simc_item_probe_resolved_count
        result["skippedExistingVerifiedVariants"] = skipped_existing_verified
        result["simcErrors"] = simc_errors[:12]
        result["stopReason"] = stop_reason or "completed_cached_payload_window"
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

    def _community_talent_templates(self, cur, class_key, spec_key, hero_key=""):
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
              AND (expires_at IS NULL OR expires_at > now())
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
        return community_talent_templates_for_spec_slots(class_key, spec_key, templates, hero_key)

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
                community_templates = self._community_talent_templates(cur, class_key, spec_key, hero_key)
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
        community_state["activeSpecSlots"] = community_talent_template_slot_summary(community_templates)
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
                      AND hero_key = %s
                      AND status = 'verified'
                      AND raw_import_code <> ''
                      AND (expires_at IS NULL OR expires_at > now())
                    ORDER BY max_key_level DESC, sample_count DESC, name
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
            simc_options = {
                key: normalize_option_value(value)
                for key, value in simc_options.items()
                if key in SIMC_GEAR_OPTION_KEYS
            }
            payload = _json_value(row[7], {})
            payload = payload if isinstance(payload, dict) else {}
            payload = gear_mod_option_payload_with_config_policy(
                option_type,
                row[3],
                simc_options,
                payload,
                normalized_slots,
            )
            if not gear_mod_option_is_supported_config_option(option_type, simc_options, payload, row[3]):
                continue
            display_fields = gear_mod_option_display_fields(option_type, row[3], simc_options, payload)
            label = str(
                display_fields.get("displayLabel")
                or payload.get("displayLabel")
                or payload.get("displayName")
                or row[3]
                or row[2]
                or ""
            ).strip()
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
            option = apply_gear_mod_option_display_fields(option, display_fields)
            for key in (
                "displayName",
                "displayLabel",
                "displayKind",
                "displayStatus",
                "evidenceSource",
                "evidenceRef",
                "iconUrl",
                "quality",
                "gameAsset",
                "metadataStatus",
                "metadataSource",
                "metadataLocale",
                "itemStats",
                "statSummary",
                "slotGroup",
                "slot_group",
                "uniqueEquipped",
                "unique_equipped",
                "uniqueGroup",
                "unique_group",
                "uniqueLimit",
                "unique_limit",
                "uniqueScope",
                "unique_scope",
                "configCategory",
                "config_category",
                "exclusionReason",
                "exclusion_reason",
                "itemTypeRule",
                "item_type_rule",
            ):
                if payload.get(key) not in (None, "", [], {}):
                    if key in {"displayName", "displayLabel", "displayKind", "displayStatus", "evidenceSource", "evidenceRef"} and option.get(key) not in (None, "", [], {}):
                        continue
                    option[key] = payload.get(key)
            for slot in normalized_slots:
                if slot in result:
                    result[slot].append(option)
        return result

    def _gear_payload_fingerprint(self, cur, class_key, spec_key, compact, season, catalog_state, mode="", slot=""):
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
            WHERE expires_at IS NULL OR expires_at > now()
            """
        )
        table_rows = tuple(
            (str(row[0] or ""), _int_value(row[1]), str(row[2] or ""))
            for row in cur.fetchall()
        )
        return (
            "pg-websim-gear-v4",
            class_key,
            spec_key,
            bool(compact),
            str(mode or "").strip().lower(),
            str(slot or "").strip().lower(),
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

    def _compact_initial_gear_item(self, item, compact=False):
        items = compact_gear_candidates([item], include_mod_options=False) if compact else [dict(item)]
        if not items:
            return {}
        output = dict(items[0])
        output["detailMode"] = "summary"
        output["slotDetailAvailable"] = True
        return output

    def _template_gear_by_slot(self, template, compact=False):
        result = {}
        for item in template.get("gearItems") or []:
            if not isinstance(item, dict):
                continue
            slot = normalize_slot(item.get("simcSlot") or item.get("slot"))
            if slot in CANONICAL_GEAR_SLOTS and slot not in result:
                initial_item = self._compact_initial_gear_item(item, compact=compact)
                if initial_item:
                    result[slot] = initial_item
        return result

    def _websim_gear_initial_payload(
        self,
        class_key,
        spec_key,
        compact,
        season,
        season_fields,
        catalog_state,
        catalog_blockers,
        persisted_templates,
    ):
        community_templates = select_community_best_gear_templates(
            [template for template in persisted_templates if is_real_community_gear_template(template)],
            class_key,
            spec_key,
        )
        baseline_templates = select_best_baseline_gear_templates(
            [template for template in persisted_templates if is_baseline_gear_template(template)]
        )
        if not baseline_templates:
            baseline_templates = [blocked_baseline_gear_template(class_key, spec_key)]
        baseline_template = baseline_templates[0] if baseline_templates else {}
        baseline_items = baseline_template.get("gearItems") or []
        equipped_set = self._template_gear_by_slot(baseline_template, compact=compact)
        slot_groups = []
        for slot in CANONICAL_GEAR_SLOTS:
            item = equipped_set.get(slot)
            slot_groups.append(
                {
                    "slot": slot,
                    "simcSlot": slot,
                    "label": GEAR_SLOT_LABELS.get(slot, slot),
                    "items": [item] if item else [],
                    "detailMode": "partial",
                    "fullItemCount": 1 if item else 0,
                }
            )
        output_baseline_set = compact_gear_candidates(baseline_items, include_mod_options=False) if compact else baseline_items
        output_community_templates = (
            [compact_community_gear_template(template) for template in community_templates]
            if compact
            else community_templates
        )
        output_baseline_templates = (
            [compact_community_gear_template(template) for template in baseline_templates]
            if compact
            else baseline_templates
        )
        readiness = gear_readiness(baseline_items)
        payload = {
            "classKey": class_key,
            "specKey": spec_key,
            "gearPayloadMode": "initial",
            "gearInitialCandidateLimit": 1,
            "weaponRule": weapon_equipment_rule_payload(class_key, spec_key),
            "slots": gear_slot_payload(),
            "replacementCandidates": slot_groups,
            "equippedSet": equipped_set,
            "slotReadiness": gear_slot_readiness(baseline_items, class_key, spec_key),
            "baselineSet": output_baseline_set,
            "communityTemplates": output_community_templates,
            "baselineTemplates": output_baseline_templates,
            "communityTemplateSync": websim_gear_community_template_sync_state(
                [*community_templates, *baseline_templates]
            ),
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
            "catalogItems": output_baseline_set[:120],
            "maxLevel": websim_max_level(),
            "checkedAt": utc_now(),
            **season_fields,
        }
        return payload

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

    def _official_item_metadata_by_id(self, cur, gear_items):
        item_ids = sorted({
            str((item or {}).get("itemId") or (item or {}).get("id") or "").strip()
            for item in gear_items or []
            if isinstance(item, dict) and str((item or {}).get("itemId") or (item or {}).get("id") or "").strip()
        })
        if not item_ids:
            return {}
        placeholders = ", ".join(["%s"] * len(item_ids))
        cur.execute(
            f"""
            SELECT id, name, slot, item_level, payload_json, source_status
            FROM cache.websim_items
            WHERE id IN ({placeholders})
            """,
            item_ids,
        )
        metadata_by_id = {}
        for row in cur.fetchall():
            payload = _json_value(row[4], {})
            payload = payload if isinstance(payload, dict) else {}
            metadata = payload.get("_metadata") if isinstance(payload.get("_metadata"), dict) else {}
            metadata_source = str(metadata.get("source") or payload.get("metadataSource") or "").strip()
            source_status = str(row[5] or metadata.get("metadataStatus") or payload.get("sourceStatus") or "").strip()
            has_official_payload_shape = bool(
                payload.get("inventory_type")
                or payload.get("inventoryType")
                or payload.get("item_class")
                or payload.get("itemClass")
                or payload.get("item_subclass")
                or payload.get("itemSubclass")
            )
            if metadata_source != ITEM_METADATA_SOURCE and not (
                source_status == "verified" and has_official_payload_shape
            ):
                continue
            type_metadata = item_type_metadata_from_payload(payload)
            item_id = str(row[0] or "").strip()
            display_name = (
                payload.get("displayName")
                or payload.get("localizedName")
                or payload.get("name")
                or row[1]
                or f"Item {item_id}"
            )
            metadata_by_id[item_id] = {
                "itemId": item_id,
                "displayName": display_name,
                "slot": row[2] or "",
                "itemLevel": _int_value(row[3]),
                "quality": payload.get("quality") or "",
                "iconUrl": metadata.get("iconUrl") or payload.get("iconUrl") or "",
                "payload": payload,
                "metadataStatus": source_status or "verified",
                "metadataSource": metadata_source or ITEM_METADATA_SOURCE,
                "metadataLocale": metadata.get("locale") or "",
                "englishName": metadata.get("englishName") or "",
                **type_metadata,
            }
        return metadata_by_id

    def _hydrated_community_gear_items(self, gear_items, official_metadata_by_id):
        hydrated = []
        for item in _json_value(gear_items, []):
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("itemId") or item.get("id") or "").strip()
            metadata = official_metadata_by_id.get(item_id) if item_id else None
            hydrated.append(apply_item_metadata(item, metadata) if metadata else item)
        return hydrated

    def community_gear_template_item_metadata_gaps(self, limit=200):
        try:
            limit = max(1, min(2000, int(limit or 200)))
        except (TypeError, ValueError):
            limit = 200
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, class_key, spec_key, source_key, status, gear_items_json
                    FROM cache.websim_community_gear_templates
                    WHERE status IN ('complete', 'partial')
                      AND (expires_at IS NULL OR expires_at > now())
                    ORDER BY updated_at DESC, id
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()

                refs_by_id = {}
                for row in rows:
                    template_ref = {
                        "templateId": str(row[0] or ""),
                        "classKey": str(row[1] or ""),
                        "specKey": str(row[2] or ""),
                        "sourceKey": str(row[3] or ""),
                        "status": str(row[4] or ""),
                    }
                    for item in _json_value(row[5], []):
                        if not isinstance(item, dict):
                            continue
                        item_id = str(item.get("itemId") or item.get("id") or "").strip()
                        if not item_id:
                            continue
                        entry = refs_by_id.setdefault(
                            item_id,
                            {
                                "itemId": item_id,
                                "name": str(item.get("displayName") or item.get("localizedName") or item.get("name") or ""),
                                "slot": normalize_slot(item.get("slot") or item.get("simcSlot") or ""),
                                "templates": [],
                            },
                        )
                        if not entry.get("name"):
                            entry["name"] = str(item.get("displayName") or item.get("localizedName") or item.get("name") or "")
                        if not entry.get("slot"):
                            entry["slot"] = normalize_slot(item.get("slot") or item.get("simcSlot") or "")
                        if template_ref not in entry["templates"]:
                            entry["templates"].append(template_ref)

                if not refs_by_id:
                    return []
                item_ids = sorted(refs_by_id)
                placeholders = ", ".join(["%s"] * len(item_ids))
                cur.execute(
                    f"""
                    SELECT id, name, slot, item_level, payload_json, source_status
                    FROM cache.websim_items
                    WHERE id IN ({placeholders})
                    """,
                    item_ids,
                )
                metadata_by_id = {str(row[0]): row for row in cur.fetchall()}

        gaps = []
        for item_id, ref in refs_by_id.items():
            row = metadata_by_id.get(item_id)
            reasons = []
            if not row:
                reasons.append("missing_metadata_row")
                payload = {}
                row_name = ""
                row_slot = ""
                source_status = ""
            else:
                payload = _json_value(row[4], {})
                payload = payload if isinstance(payload, dict) else {}
                row_name = str(row[1] or "")
                row_slot = normalize_slot(row[2] or "")
                source_status = str(row[5] or payload.get("sourceStatus") or "").strip()
            metadata = payload.get("_metadata") if isinstance(payload.get("_metadata"), dict) else {}
            metadata_source = str(metadata.get("source") or payload.get("metadataSource") or "").strip()
            has_official_payload_shape = bool(
                payload.get("inventory_type")
                or payload.get("inventoryType")
                or payload.get("item_class")
                or payload.get("itemClass")
                or payload.get("item_subclass")
                or payload.get("itemSubclass")
            )
            if metadata_source != ITEM_METADATA_SOURCE and not (
                source_status == "verified" and has_official_payload_shape
            ):
                reasons.append("missing_official_payload_shape")
            display_name = payload.get("displayName") or payload.get("localizedName") or payload.get("name") or row_name
            icon_url = metadata.get("iconUrl") or payload.get("iconUrl") or ""
            if not str(display_name or "").strip():
                reasons.append("missing_display_name")
            if not str(icon_url or "").strip():
                reasons.append("missing_icon")
            if reasons:
                gaps.append(
                    {
                        **ref,
                        "name": ref.get("name") or display_name or row_name or f"Item {item_id}",
                        "slot": ref.get("slot") or row_slot,
                        "reasons": unique_text_list(reasons),
                        "metadataSource": metadata_source,
                        "sourceStatus": source_status,
                    }
                )
        return sorted(gaps, key=lambda item: (item.get("itemId") or "", item.get("slot") or ""))[:limit]

    def websim_item_metadata_gaps(self, limit=200):
        try:
            limit = max(1, min(2000, int(limit or 200)))
        except (TypeError, ValueError):
            limit = 200
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH item_usage AS (
                        SELECT item_id, count(*)::integer AS usage_count
                        FROM cache.websim_gear_variants
                        WHERE item_id IS NOT NULL AND item_id <> ''
                        GROUP BY item_id
                        UNION ALL
                        SELECT item_id, count(*)::integer AS usage_count
                        FROM cache.websim_gear_sources
                        WHERE item_id IS NOT NULL AND item_id <> ''
                        GROUP BY item_id
                    ),
                    usage_totals AS (
                        SELECT item_id, sum(usage_count)::integer AS usage_count
                        FROM item_usage
                        GROUP BY item_id
                    )
                    SELECT i.id, i.name, i.slot, i.payload_json, i.source_status, COALESCE(u.usage_count, 0)::integer
                    FROM cache.websim_items i
                    LEFT JOIN usage_totals u ON u.item_id = i.id
                    WHERE COALESCE(u.usage_count, 0) > 0
                      AND (
                        COALESCE(
                            i.payload_json->>'displayName',
                            i.payload_json->>'localizedName',
                            i.payload_json->>'name',
                            i.name,
                            ''
                        ) = ''
                        OR COALESCE(i.payload_json #>> '{_metadata,iconUrl}', i.payload_json->>'iconUrl', '') = ''
                        OR NOT (
                            COALESCE(i.payload_json, '{}'::jsonb) ? 'inventory_type'
                            OR COALESCE(i.payload_json, '{}'::jsonb) ? 'inventoryType'
                            OR COALESCE(i.payload_json, '{}'::jsonb) ? 'item_class'
                            OR COALESCE(i.payload_json, '{}'::jsonb) ? 'itemClass'
                            OR COALESCE(i.payload_json, '{}'::jsonb) ? 'item_subclass'
                            OR COALESCE(i.payload_json, '{}'::jsonb) ? 'itemSubclass'
                        )
                      )
                    ORDER BY
                        (COALESCE(i.payload_json #>> '{_metadata,iconUrl}', i.payload_json->>'iconUrl', '') = '') DESC,
                        (NOT (
                            COALESCE(i.payload_json, '{}'::jsonb) ? 'inventory_type'
                            OR COALESCE(i.payload_json, '{}'::jsonb) ? 'inventoryType'
                            OR COALESCE(i.payload_json, '{}'::jsonb) ? 'item_class'
                            OR COALESCE(i.payload_json, '{}'::jsonb) ? 'itemClass'
                            OR COALESCE(i.payload_json, '{}'::jsonb) ? 'item_subclass'
                            OR COALESCE(i.payload_json, '{}'::jsonb) ? 'itemSubclass'
                        )) DESC,
                        COALESCE(u.usage_count, 0) DESC,
                        i.updated_at DESC,
                        i.id
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()

        gaps = []
        for row in rows:
            item_id = str(row[0] or "").strip()
            if not item_id:
                continue
            row_name = str(row[1] or "")
            row_slot = normalize_slot(row[2] or "")
            payload = _json_value(row[3], {})
            payload = payload if isinstance(payload, dict) else {}
            source_status = str(row[4] or payload.get("sourceStatus") or "").strip()
            usage_count = _int_value(row[5]) or 0
            metadata = payload.get("_metadata") if isinstance(payload.get("_metadata"), dict) else {}
            display_name = payload.get("displayName") or payload.get("localizedName") or payload.get("name") or row_name
            icon_url = metadata.get("iconUrl") or payload.get("iconUrl") or ""
            has_official_payload_shape = bool(
                payload.get("inventory_type")
                or payload.get("inventoryType")
                or payload.get("item_class")
                or payload.get("itemClass")
                or payload.get("item_subclass")
                or payload.get("itemSubclass")
            )
            reasons = []
            if not has_official_payload_shape:
                reasons.append("missing_official_payload_shape")
            if not str(display_name or "").strip():
                reasons.append("missing_display_name")
            if not str(icon_url or "").strip():
                reasons.append("missing_icon")
            if not reasons:
                continue
            gaps.append(
                {
                    "itemId": item_id,
                    "name": display_name or row_name or f"Item {item_id}",
                    "slot": row_slot,
                    "reasons": unique_text_list(reasons),
                    "metadataSource": str(metadata.get("source") or payload.get("metadataSource") or "").strip(),
                    "sourceStatus": source_status,
                    "usageCount": usage_count,
                }
            )
        return gaps[:limit]

    def _repair_template_offhand_occupancy(self, template):
        if not isinstance(template, dict):
            return template
        missing_slots = [
            str(slot or "").strip()
            for slot in (template.get("missingSlots") or [])
            if str(slot or "").strip()
        ]
        if "off_hand" not in missing_slots:
            return template
        _ready_by_slot, occupied_slots, _coverage_missing = gear_template_slot_coverage(
            template.get("gearItems") or [],
            template.get("classKey") or "",
            template.get("specKey") or "",
        )
        if "off_hand" not in occupied_slots:
            return template
        repaired = {**template}
        repaired_missing = [slot for slot in missing_slots if slot != "off_hand"]
        repaired["missingSlots"] = repaired_missing
        repaired["readySlotCount"] = len(CANONICAL_GEAR_SLOTS) - len(set(repaired_missing))
        existing_occupied_slots = repaired.get("occupiedSlots") if isinstance(repaired.get("occupiedSlots"), dict) else {}
        repaired["occupiedSlots"] = {**existing_occupied_slots, "off_hand": occupied_slots["off_hand"]}
        if repaired.get("status") == "partial" and not repaired_missing and repaired.get("gearItems"):
            repaired["status"] = "complete"
        if repaired.get("status") == "complete" and repaired.get("sourceStatus") == "partial":
            repaired["sourceStatus"] = "synced"
        return repaired

    def _community_gear_template_from_row(self, row, official_metadata_by_id=None, normalize_coverage=True):
        payload = _json_value(row[16], {})
        payload = payload if isinstance(payload, dict) else {}
        gear_items = self._hydrated_community_gear_items(row[11], official_metadata_by_id or {})
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
        if normalize_coverage:
            template = self._repair_template_offhand_occupancy(template)
        return template

    def _gear_community_templates(self, cur, class_key, spec_key):
        cur.execute(
            """
            SELECT id, class_key, spec_key, name, source_key, source_name, source_url,
                   source_status, status, signature, source_refs_json, gear_items_json,
                   raw_string, ready_slot_count, missing_slots_json, analysis_window,
                   payload_json, updated_at, expires_at, scan_run_id
            FROM cache.websim_community_gear_templates
            WHERE class_key = %s AND spec_key = %s AND status IN ('complete', 'partial')
              AND (expires_at IS NULL OR expires_at > now())
            ORDER BY status, ready_slot_count DESC, updated_at DESC, name
            LIMIT 80
            """,
            (class_key, spec_key),
        )
        rows = cur.fetchall()
        now = datetime.now(timezone.utc)
        rows = [row for row in rows if not _timestamp_expired(row[18], now)]
        all_gear_items = []
        for row in rows:
            all_gear_items.extend(item for item in _json_value(row[11], []) if isinstance(item, dict))
        official_metadata_by_id = self._official_item_metadata_by_id(cur, all_gear_items)
        templates = []
        for row in rows:
            template = self._community_gear_template_from_row(row, official_metadata_by_id, normalize_coverage=True)
            templates.append(template)
        return dedupe_gear_community_templates(templates)

    def get_websim_gear(self, class_key="mage", spec_key="arcane", compact=False, mode="", slot=""):
        season = self.get_active_season_payload()
        class_key = slugify(class_key, "mage")
        spec_key = slugify(spec_key, "arcane")
        compact = bool(compact)
        mode = str(mode or "").strip().lower()
        slot = normalize_slot(slot) if mode == "slot" else str(slot or "").strip().lower()
        season_fields = season_metadata_fields(season)
        catalog_state = self.get_sync_state("gearCatalog")
        season_errors = season.get("errors") if isinstance(season.get("errors"), list) else []
        catalog_blockers = [
            *[str(item) for item in (catalog_state.get("blockers") or []) if str(item or "").strip()],
            *[str(item) for item in season_errors if str(item or "").strip()],
        ]
        if mode == "initial":
            with self.connection() as conn:
                with conn.cursor() as cur:
                    persisted_templates = self._gear_community_templates(cur, class_key, spec_key)
            return self._websim_gear_initial_payload(
                class_key,
                spec_key,
                compact,
                season,
                season_fields,
                catalog_state,
                catalog_blockers,
                persisted_templates,
            )
        cache_fingerprint = None
        with self.connection() as conn:
            with conn.cursor() as cur:
                cache_fingerprint = self._gear_payload_fingerprint(
                    cur,
                    class_key,
                    spec_key,
                    compact,
                    season,
                    catalog_state,
                    mode=mode,
                    slot=slot,
                )
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
                persisted_templates = self._gear_community_templates(cur, class_key, spec_key)
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
        community_templates = select_community_best_gear_templates(
            [template for template in persisted_templates if is_real_community_gear_template(template)],
            class_key,
            spec_key,
        )
        baseline_templates = select_best_baseline_gear_templates(
            [template for template in persisted_templates if is_baseline_gear_template(template)]
        )
        if not baseline_templates:
            baseline_templates = [blocked_baseline_gear_template(class_key, spec_key)]
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
                items = limit_replacement_candidates(items, candidate_limit)
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
        output_community_templates = (
            [compact_community_gear_template(template) for template in community_templates]
            if compact
            else community_templates
        )
        output_baseline_templates = (
            [compact_community_gear_template(template) for template in baseline_templates]
            if compact
            else baseline_templates
        )
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
            "communityTemplates": output_community_templates,
            "baselineTemplates": output_baseline_templates,
            "communityTemplateSync": websim_gear_community_template_sync_state(
                [*community_templates, *baseline_templates]
            ),
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
                    all_gear_items = []
                    for row in template_rows:
                        all_gear_items.extend(item for item in _json_value(row[11], []) if isinstance(item, dict))
                    official_metadata_by_id = self._official_item_metadata_by_id(cur, all_gear_items)
                    for row in template_rows:
                        template = self._community_gear_template_from_row(row, official_metadata_by_id, normalize_coverage=True)
                        payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
                        blockers = payload.get("blockers") if isinstance(payload.get("blockers"), list) else []
                        missing_slots = template.get("missingSlots") or []
                        if missing_slots:
                            blockers = [*(blockers or []), f"missing slots: {', '.join(str(slot) for slot in missing_slots[:6])}"]
                        rows.append(("gear_templates", template.get("status") or "", blockers))
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

    def _admin_gate_gear_template_display_records(self, templates):
        display_slots = []
        community_groups = {}
        baseline_groups = {}
        seen_community_slots = set()
        seen_baseline_slots = set()
        for template in templates or []:
            if not isinstance(template, dict):
                continue
            class_key = slugify(template.get("classKey"), "")
            spec_key = slugify(template.get("specKey"), "")
            group_key = (class_key, spec_key)
            if class_key and spec_key and is_baseline_gear_template(template):
                baseline_groups.setdefault(group_key, []).append(template)
                if group_key not in seen_baseline_slots:
                    seen_baseline_slots.add(group_key)
                    display_slots.append(("baseline", group_key))
                continue
            if class_key and spec_key and is_real_community_gear_template(template):
                community_groups.setdefault(group_key, []).append(template)
                if group_key not in seen_community_slots:
                    seen_community_slots.add(group_key)
                    display_slots.append(("community", group_key))
                continue
            display_slots.append(("raw", template))

        selected_community = {}
        for (class_key, spec_key), candidates in community_groups.items():
            best = select_community_best_gear_templates(candidates, class_key, spec_key)
            if best:
                selected_community[(class_key, spec_key)] = best[0]
        selected_baseline = {}
        for group_key, candidates in baseline_groups.items():
            best = select_best_baseline_gear_templates(candidates)
            if best:
                selected_baseline[group_key] = best[0]

        display_records = []
        for slot_type, value in display_slots:
            if slot_type == "community":
                selected = selected_community.get(value)
                if selected:
                    display_records.append(selected)
            elif slot_type == "baseline":
                selected = selected_baseline.get(value)
                if selected:
                    display_records.append(selected)
            else:
                display_records.append(value)
        return display_records

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
                        WHERE expires_at IS NULL OR expires_at > now()
                        ORDER BY updated_at DESC
                        LIMIT 500
                        """
                    )
                    template_rows = cur.fetchall()
                    all_gear_items = []
                    for row in template_rows:
                        all_gear_items.extend(_json_value(row[11], []))
                    official_metadata_by_id = self._official_item_metadata_by_id(cur, all_gear_items)
                else:
                    official_metadata_by_id = {}
        templates = [
            self._community_gear_template_from_row(row, official_metadata_by_id, normalize_coverage=True)
            for row in template_rows
        ]
        return {
            "communityGearTemplates": self._admin_gate_gear_template_display_records(templates)
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

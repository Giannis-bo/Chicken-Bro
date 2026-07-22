#!/usr/bin/env python3
import re
from urllib.parse import unquote, urlparse


DEFAULT_GEAR_TEMPLATE_SOURCE_KEY = "default_template"
SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY = "season_recommendation"
RECOMMENDED_BIS_GEAR_TEMPLATE_SOURCE_KEY = "recommended_bis"

BASELINE_GEAR_TEMPLATE_SOURCE_KEYS = {
    RECOMMENDED_BIS_GEAR_TEMPLATE_SOURCE_KEY,
    SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY,
    DEFAULT_GEAR_TEMPLATE_SOURCE_KEY,
    "baseline_template",
    "simc_preset",
    "baseline_blocked",
}

REAL_PLAYER_GEAR_TEMPLATE_PUBLIC_POLICY = "all_specs"
REAL_PLAYER_GEAR_TEMPLATE_PUBLIC_SPECS = set()
REAL_PLAYER_GEAR_TEMPLATE_PILOT_SPECS = {("shaman", "elemental")}
STRICT_COMMUNITY_BEST_V2_ACTIVE_SEED_SPECS = {("shaman", "elemental")}

REAL_PLAYER_GEAR_TEMPLATE_OBSERVED_TEMPLATE_IDS = {
    ("shaman", "elemental"): "observed_profile_shaman_elemental",
}
REAL_PLAYER_GEAR_TEMPLATE_OBSERVED_PROFILE_URLS = {
    ("shaman", "elemental"): "https://raider.io/characters/cn/sylvanas/听凭风引",
}
REAL_PLAYER_GEAR_TEMPLATE_OBSERVED_DISPLAY_NAMES = {
    ("shaman", "elemental"): "听凭风引（元素萨）· 真实高分玩家角色模板",
}
REAL_PLAYER_GEAR_TEMPLATE_OBSERVED_SOURCE_NAMES = {
    ("shaman", "elemental"): "Raider.IO 真实玩家角色装备",
}
REAL_PLAYER_GEAR_TEMPLATE_RECOMMENDED_DISPLAY_NAMES = {
    ("shaman", "elemental"): "元素萨 · 系统评分推荐模板（待 SimC 验证）",
}
REAL_PLAYER_GEAR_TEMPLATE_RECOMMENDED_SOURCE_NAMES = {
    ("shaman", "elemental"): "系统评分推荐模板（projected_bis）",
}
REAL_PLAYER_GEAR_TEMPLATE_LEGACY_SOURCE_KEYS = {
    SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY,
    DEFAULT_GEAR_TEMPLATE_SOURCE_KEY,
    "baseline_template",
    "simc_preset",
    "baseline_blocked",
}

COMMUNITY_GEAR_TEMPLATE_SLOTS_PER_SPEC = 2
PUBLIC_GEAR_PROJECTION_MODES = {"talent_winner", "gear_fallback"}


def slugify(value, fallback="item"):
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
    return text[:80] if text else fallback


def int_or_zero(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def gear_template_source_key(template):
    return str((template or {}).get("sourceKey") or "").strip().lower()


def gear_template_payload(template):
    return (template or {}).get("payload") if isinstance((template or {}).get("payload"), dict) else {}


def gear_template_evidence_payload(template):
    payload = gear_template_payload(template)
    evidence = (template or {}).get("templateEvidence") if isinstance((template or {}).get("templateEvidence"), dict) else {}
    if evidence:
        return evidence
    return payload.get("templateEvidence") if isinstance(payload.get("templateEvidence"), dict) else {}


def gear_template_spec_key(template):
    class_key = slugify((template or {}).get("classKey"), "")
    spec_key = slugify((template or {}).get("specKey"), "")
    return f"{class_key}:{spec_key}" if class_key and spec_key else ""


def real_player_gear_template_pilot_spec(class_key, spec_key):
    return (slugify(class_key, ""), slugify(spec_key, "")) in REAL_PLAYER_GEAR_TEMPLATE_PILOT_SPECS


def real_player_gear_template_public_import_spec(class_key, spec_key):
    class_key = slugify(class_key, "")
    spec_key = slugify(spec_key, "")
    if not class_key or not spec_key:
        return False
    if REAL_PLAYER_GEAR_TEMPLATE_PUBLIC_POLICY == "all_specs":
        return True
    return (class_key, spec_key) in REAL_PLAYER_GEAR_TEMPLATE_PUBLIC_SPECS


def real_player_gear_template_observed_template_id(class_key, spec_key):
    return REAL_PLAYER_GEAR_TEMPLATE_OBSERVED_TEMPLATE_IDS.get(
        (slugify(class_key, ""), slugify(spec_key, "")),
        "",
    )


def real_player_gear_template_observed_profile_url(class_key, spec_key):
    return REAL_PLAYER_GEAR_TEMPLATE_OBSERVED_PROFILE_URLS.get(
        (slugify(class_key, ""), slugify(spec_key, "")),
        "",
    )


def real_player_gear_template_observed_display_name(class_key, spec_key):
    return REAL_PLAYER_GEAR_TEMPLATE_OBSERVED_DISPLAY_NAMES.get(
        (slugify(class_key, ""), slugify(spec_key, "")),
        "",
    )


def real_player_gear_template_observed_source_name(class_key, spec_key):
    return REAL_PLAYER_GEAR_TEMPLATE_OBSERVED_SOURCE_NAMES.get(
        (slugify(class_key, ""), slugify(spec_key, "")),
        "",
    )


def real_player_gear_template_recommended_display_name(class_key, spec_key):
    return REAL_PLAYER_GEAR_TEMPLATE_RECOMMENDED_DISPLAY_NAMES.get(
        (slugify(class_key, ""), slugify(spec_key, "")),
        "",
    )


def real_player_gear_template_recommended_source_name(class_key, spec_key):
    return REAL_PLAYER_GEAR_TEMPLATE_RECOMMENDED_SOURCE_NAMES.get(
        (slugify(class_key, ""), slugify(spec_key, "")),
        "",
    )


def is_baseline_gear_template(template):
    return gear_template_source_key(template) in BASELINE_GEAR_TEMPLATE_SOURCE_KEYS


def is_real_community_gear_template(template):
    if not isinstance(template, dict):
        return False
    if is_baseline_gear_template(template):
        return False
    return str(template.get("status") or "").strip() in {"complete", "partial"}


def community_gear_template_can_apply(template):
    if not isinstance(template, dict):
        return False
    if template.get("canApplyGear") is False:
        return False
    status = str(template.get("status") or "").strip()
    source_status = str(template.get("sourceStatus") or "").strip()
    blocked_statuses = {"blocked", "source_reference", "source-reference", "missing_credentials"}
    if status in blocked_statuses or source_status in blocked_statuses:
        return False
    if not (template.get("rawString") or template.get("gearItems")):
        return False
    if gear_template_source_key(template) == "raiderio_observed_profile":
        missing_slots = [slot for slot in (template.get("missingSlots") or []) if str(slot or "").strip()]
        if status != "complete" or missing_slots:
            return False
    return True


def gear_template_source_url(template):
    if not isinstance(template, dict):
        return ""
    source_url = str(template.get("sourceUrl") or "").strip()
    if source_url:
        return source_url
    payload = gear_template_payload(template)
    for key in ("sourceUrl", "profileUrl", "url"):
        source_url = str(payload.get(key) or "").strip()
        if source_url:
            return source_url
    for ref in template.get("sourceRefs") or []:
        if not isinstance(ref, dict):
            continue
        source_url = str(ref.get("sourceUrl") or ref.get("profileUrl") or ref.get("url") or "").strip()
        if source_url:
            return source_url
    return ""


def gear_template_observed_profile_hash(template):
    payload = gear_template_payload(template)
    evidence = gear_template_evidence_payload(template)
    for source in (template, payload, evidence):
        if not isinstance(source, dict):
            continue
        value = source.get("profileHash")
        if value:
            return str(value)
    return ""


def gear_template_observed_gear_hash(template):
    payload = gear_template_payload(template)
    evidence = gear_template_evidence_payload(template)
    for source in (template, payload, evidence):
        if not isinstance(source, dict):
            continue
        value = source.get("gearHash")
        if value:
            return str(value)
    return ""


def community_observed_character_identity_from_url(source_url):
    try:
        parsed = urlparse(str(source_url or ""))
    except Exception:
        return {}
    parts = [unquote(part) for part in (parsed.path or "").split("/") if part]
    if len(parts) >= 4 and parts[0] == "characters":
        return {
            "region": parts[1],
            "realmSlug": parts[2],
            "name": parts[3],
        }
    return {}


def community_observed_character_identity(template):
    payload = gear_template_payload(template)
    character = payload.get("character") if isinstance(payload.get("character"), dict) else {}
    if character:
        return {
            "name": str(character.get("name") or character.get("characterName") or "").strip(),
            "region": str(character.get("region") or "").strip(),
            "realmSlug": str(character.get("realmSlug") or character.get("realm") or character.get("realmName") or "").strip(),
        }
    for ref in (template or {}).get("sourceRefs") or []:
        if not isinstance(ref, dict):
            continue
        identity = {
            "name": str(ref.get("characterName") or ref.get("character") or ref.get("name") or "").strip(),
            "region": str(ref.get("region") or "").strip(),
            "realmSlug": str(ref.get("realmSlug") or ref.get("realm") or ref.get("realmName") or "").strip(),
        }
        if identity["name"] or identity["region"] or identity["realmSlug"]:
            return identity
    return community_observed_character_identity_from_url(gear_template_source_url(template))


def community_observed_fetched_or_scan_id(template):
    payload = gear_template_payload(template)
    for source in (template, payload):
        if not isinstance(source, dict):
            continue
        value = source.get("fetchedAt") or source.get("scanRunId") or source.get("scan_run_id")
        if value:
            return str(value).strip()
    for ref in (template or {}).get("sourceRefs") or []:
        if not isinstance(ref, dict):
            continue
        value = ref.get("fetchedAt") or ref.get("scanRunId") or ref.get("scan_run_id")
        if value:
            return str(value).strip()
    return ""


def community_observed_ranking_evidence(template):
    payload = gear_template_payload(template)
    evidence = payload.get("rankingEvidence") if isinstance(payload.get("rankingEvidence"), dict) else {}
    if evidence:
        return evidence
    for ref in (template or {}).get("sourceRefs") or []:
        if not isinstance(ref, dict):
            continue
        evidence = ref.get("rankingEvidence") if isinstance(ref.get("rankingEvidence"), dict) else {}
        if evidence:
            return evidence
        if ref.get("rank") or ref.get("score"):
            return {
                "source": "raiderio_spec_ranking",
                "rank": ref.get("rank"),
                "score": ref.get("score"),
                "maxKeyLevel": ref.get("maxKeyLevel"),
                "runId": ref.get("runId"),
                "sourceUrl": ref.get("sourceUrl"),
            }
    return {}


def community_observed_evidence_blockers(template):
    payload = gear_template_payload(template)
    blockers = []
    if not gear_template_source_url(template):
        blockers.append("community_best_v2 requires sourceUrl for the observed character")
    sample_count = int_or_zero((template or {}).get("sampleCount") or payload.get("sampleCount"))
    if sample_count != 1:
        blockers.append("community_best_v2 requires sampleCount=1 for a single observed character")
    if not gear_template_observed_profile_hash(template):
        blockers.append("community_best_v2 requires profileHash")
    if not gear_template_observed_gear_hash(template):
        blockers.append("community_best_v2 requires gearHash")
    identity = community_observed_character_identity(template)
    if not (identity.get("name") and identity.get("region") and identity.get("realmSlug")):
        blockers.append("community_best_v2 requires region, realm, and character identity")
    if not community_observed_fetched_or_scan_id(template):
        blockers.append("community_best_v2 requires fetchedAt or scanRunId")
    class_key = slugify((template or {}).get("classKey"), "")
    spec_key = slugify((template or {}).get("specKey"), "")
    if (class_key, spec_key) in STRICT_COMMUNITY_BEST_V2_ACTIVE_SEED_SPECS:
        ranking_evidence = community_observed_ranking_evidence(template)
        if str(ranking_evidence.get("source") or "") != "raiderio_spec_ranking":
            blockers.append("community_best_v2 requires current Raider.IO spec ranking evidence for elemental shaman")
        elif int_or_zero(ranking_evidence.get("rank")) <= 0 or not ranking_evidence.get("score"):
            blockers.append("community_best_v2 requires rank and score for elemental shaman observed evidence")
    if str((template or {}).get("status") or "") == "blocked" or str((template or {}).get("sourceStatus") or "") == "blocked":
        blockers.append("observed template is blocked")
    return blockers


def community_observed_chain_record(template):
    blockers = community_observed_evidence_blockers(template)
    missing_slots = (template or {}).get("missingSlots") or []
    legality_skipped_slots = (template or {}).get("legalitySkippedSlots") or []
    scenario_results = gear_template_evidence_payload(template).get("scenarioResults")
    scenario_results = scenario_results if isinstance(scenario_results, dict) else {}
    if blockers:
        confidence = "observed_blocked"
    elif missing_slots:
        confidence = "observed_partial"
    elif scenario_results:
        confidence = "observed_verified"
    else:
        confidence = "observed_provisional"
    return {
        "id": str((template or {}).get("id") or ""),
        "spec": gear_template_spec_key(template),
        "templateType": "community_observed",
        "confidence": confidence,
        "status": confidence,
        "sourceUrl": gear_template_source_url(template),
        "profileHash": gear_template_observed_profile_hash(template),
        "gearHash": gear_template_observed_gear_hash(template),
        "readySlotCount": int_or_zero((template or {}).get("readySlotCount")),
        "missingSlots": missing_slots,
        "legalitySkippedSlots": legality_skipped_slots,
        "blockers": blockers,
    }


def is_active_community_observed_template(template, chain_record_factory=None):
    if not is_real_community_gear_template(template):
        return False
    chain_record_factory = chain_record_factory or community_observed_chain_record
    record = chain_record_factory(template)
    if record.get("confidence") not in {"observed_verified", "observed_provisional"}:
        return False
    if not community_gear_template_can_apply(template):
        return False
    return True


def is_public_hero_gear_projection(template, active_observed_predicate=None):
    """Return whether a sealed hero-slot projection is safe for public import."""

    if not isinstance(template, dict):
        return False
    if gear_template_source_key(template) != "raiderio_observed_profile":
        return False
    if slugify(template.get("heroKey"), "") == "":
        return False
    if not str(template.get("talentWinnerId") or "").strip():
        return False
    if str(template.get("gearProjectionMode") or "").strip() not in PUBLIC_GEAR_PROJECTION_MODES:
        return False
    predicate = active_observed_predicate or is_active_community_observed_template
    return bool(predicate(template))


def public_gear_template_visible_for_spec(template, class_key, spec_key, active_observed_predicate=None):
    if not isinstance(template, dict):
        return False
    if not real_player_gear_template_public_import_spec(class_key, spec_key):
        return True
    source_key = gear_template_source_key(template)
    if source_key == RECOMMENDED_BIS_GEAR_TEMPLATE_SOURCE_KEY:
        return False
    if source_key in REAL_PLAYER_GEAR_TEMPLATE_LEGACY_SOURCE_KEYS:
        return False
    if source_key == "raiderio_observed_profile":
        # Hero-slot rows carry an explicit claim that they were projected from
        # a Talent winner.  Do not let that claim use the broader legacy
        # observed-profile gate: it must also prove the winner identity and
        # projection mode.
        if any(key in template for key in ("heroKey", "talentWinnerId", "gearProjectionMode")):
            return is_public_hero_gear_projection(
                template,
                active_observed_predicate=active_observed_predicate,
            )
        predicate = active_observed_predicate or is_active_community_observed_template
        return predicate(template)
    return False


def public_gear_templates_for_spec(templates, class_key, spec_key, active_observed_predicate=None):
    return [
        template
        for template in templates or []
        if public_gear_template_visible_for_spec(
            template,
            class_key,
            spec_key,
            active_observed_predicate=active_observed_predicate,
        )
    ]


def public_baseline_fallback_templates_for_spec(class_key, spec_key, blocked_baseline_factory=None):
    if real_player_gear_template_public_import_spec(class_key, spec_key):
        return []
    if not blocked_baseline_factory:
        return []
    return [blocked_baseline_factory(class_key, spec_key)]

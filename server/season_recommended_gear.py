#!/usr/bin/env python3
import copy
import re

try:
    from .websim_payload import (
        CANONICAL_GEAR_SLOTS,
        COMMUNITY_TEMPLATE_REVISION,
        RECOMMENDED_BIS_GEAR_TEMPLATE_SOURCE_KEY,
        RECOMMENDED_BIS_GEAR_TEMPLATE_SOURCE_NAME,
        RECOMMENDED_BIS_OPTIMIZER_VERSION,
        RECOMMENDED_BIS_SCHEMA_REVISION,
        SEASON_RECOMMENDED_GEAR_SCENARIO_KEY,
        SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY,
        SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_NAME,
        build_websim_gear_lines,
        gear_template_signature,
        gear_template_slot_coverage,
        normalize_source_refs,
        normalize_slot,
        gear_template_source_ref,
        real_player_gear_template_recommended_display_name,
        real_player_gear_template_recommended_source_name,
        selected_gear_weapon_rule_blockers,
        season_expires_at,
        slugify,
        stable_digest,
        utc_now,
    )
except ImportError:
    from websim_payload import (
        CANONICAL_GEAR_SLOTS,
        COMMUNITY_TEMPLATE_REVISION,
        RECOMMENDED_BIS_GEAR_TEMPLATE_SOURCE_KEY,
        RECOMMENDED_BIS_GEAR_TEMPLATE_SOURCE_NAME,
        RECOMMENDED_BIS_OPTIMIZER_VERSION,
        RECOMMENDED_BIS_SCHEMA_REVISION,
        SEASON_RECOMMENDED_GEAR_SCENARIO_KEY,
        SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY,
        SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_NAME,
        build_websim_gear_lines,
        gear_template_signature,
        gear_template_slot_coverage,
        normalize_source_refs,
        normalize_slot,
        gear_template_source_ref,
        real_player_gear_template_recommended_display_name,
        real_player_gear_template_recommended_source_name,
        selected_gear_weapon_rule_blockers,
        season_expires_at,
        slugify,
        stable_digest,
        utc_now,
    )


SEASON_RECOMMENDED_SCORING_VERSION = "season-rec-score-v1"
SEASON_RECOMMENDED_LOW_YIELD_THRESHOLD_RATIO = 0.35
SEASON_RECOMMENDED_LOW_YIELD_PENALTY_MULTIPLIER = 0.9
SEASON_RECOMMENDED_SIMC_GRAY_ZONE_PCT = 0.02
SEASON_RECOMMENDED_TIER_TWO_BONUS = 260.0
SEASON_RECOMMENDED_TIER_FOUR_BONUS = 780.0
SEASON_RECOMMENDED_PRIMARY_STATS = {"intellect", "agility", "strength"}
SEASON_RECOMMENDED_SECONDARY_STATS = {"crit", "haste", "mastery", "versatility"}
SEASON_RECOMMENDED_UNIQUE_ITEM_SLOT_GROUPS = {
    "finger1": "finger",
    "finger2": "finger",
    "trinket1": "trinket",
    "trinket2": "trinket",
}
SEASON_RECOMMENDED_STAT_ALIASES = {
    "critical_strike": "crit",
    "criticalstrike": "crit",
    "crit_rating": "crit",
    "critical_strike_rating": "crit",
    "haste_rating": "haste",
    "mastery_rating": "mastery",
    "vers": "versatility",
    "versatility_rating": "versatility",
    "int": "intellect",
    "intellect_rating": "intellect",
    "agi": "agility",
    "agility_rating": "agility",
    "str": "strength",
    "strength_rating": "strength",
}
SEASON_RECOMMENDED_SPEC_WEIGHT_OVERRIDES = {
    ("shaman", "elemental"): {
        "intellect": 1.5,
        "mastery": 1.08,
        "crit": 0.96,
        "haste": 0.74,
        "versatility": 0.18,
    },
}
RECOMMENDED_BIS_STAT_PRIORS = [
    "mastery_heavy",
    "crit_heavy",
    "haste_heavy",
    "balanced",
    "observed_scale_factor",
    "guide_prior",
    "community_distribution_prior",
]


def season_recommended_stat_key(value):
    key = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")
    return SEASON_RECOMMENDED_STAT_ALIASES.get(key, key)


def season_recommended_float_value(value, default=0.0):
    if value in ("", None):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip().replace("%", "")
    try:
        return float(text)
    except (TypeError, ValueError):
        digits = re.sub(r"[^\d.-]+", "", text)
        try:
            return float(digits)
        except (TypeError, ValueError):
            return default


def season_recommended_primary_stat_key(class_key, spec_key):
    class_key = slugify(class_key, "")
    spec_key = slugify(spec_key, "")
    intellect_specs = {
        ("druid", "balance"),
        ("druid", "restoration"),
        ("evoker", "augmentation"),
        ("evoker", "devastation"),
        ("evoker", "preservation"),
        ("mage", "arcane"),
        ("mage", "fire"),
        ("mage", "frost"),
        ("monk", "mistweaver"),
        ("paladin", "holy"),
        ("priest", "discipline"),
        ("priest", "holy"),
        ("priest", "shadow"),
        ("shaman", "elemental"),
        ("shaman", "restoration"),
        ("warlock", "affliction"),
        ("warlock", "demonology"),
        ("warlock", "destruction"),
    }
    if (class_key, spec_key) in intellect_specs:
        return "intellect"
    if class_key in {"deathknight", "warrior"} or (class_key == "paladin" and spec_key in {"protection", "retribution"}):
        return "strength"
    return "agility"


def normalize_season_recommended_stat_weights(class_key, spec_key, stat_weights=None):
    class_key = slugify(class_key, "")
    spec_key = slugify(spec_key, "")
    primary_key = season_recommended_primary_stat_key(class_key, spec_key)
    weights = {primary_key: 1.45, "crit": 0.72, "haste": 0.78, "mastery": 0.76, "versatility": 0.68}
    weights.update(SEASON_RECOMMENDED_SPEC_WEIGHT_OVERRIDES.get((class_key, spec_key), {}))
    source_status = "default"
    source = stat_weights if isinstance(stat_weights, dict) else {}
    rows = source.get("weights") if isinstance(source.get("weights"), list) else []
    raw_source_status = str(source.get("sourceStatus") or source.get("status") or "").strip().lower()
    accepted_source_statuses = {"verified", "partial", "stale", "synced"}
    source_accepted = not rows or not raw_source_status or raw_source_status in accepted_source_statuses
    parsed_weights = {}
    if rows and not source_accepted:
        source_status = raw_source_status
    else:
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = season_recommended_stat_key(row.get("key") or row.get("statKey") or row.get("name"))
            if key not in SEASON_RECOMMENDED_PRIMARY_STATS and key not in SEASON_RECOMMENDED_SECONDARY_STATS:
                continue
            value = row.get("rawValue")
            if value in ("", None):
                value = row.get("value")
            if value in ("", None):
                value = row.get("percent")
            parsed = season_recommended_float_value(value, None)
            if parsed is not None:
                parsed_weights[key] = parsed
                source_status = str(source.get("sourceStatus") or source.get("status") or "verified")
    secondary_max = max(
        [float(parsed_weights.get(key) or 0) for key in SEASON_RECOMMENDED_SECONDARY_STATS if float(parsed_weights.get(key) or 0) > 0]
        or [0.0]
    )
    scale = secondary_max if secondary_max > 5.0 else 1.0
    for key, parsed in parsed_weights.items():
        weights[key] = parsed / scale
    rounded_weights = {key: round(float(weights.get(key) or 0), 4) for key in sorted(weights)}
    priority_order = [
        key
        for key, _value in sorted(
            ((key, float(weights.get(key) or 0)) for key in SEASON_RECOMMENDED_SECONDARY_STATS),
            key=lambda row: row[1],
            reverse=True,
        )
    ]
    return weights, {
        "sourceStatus": source_status,
        "sourceScenarioKey": str(source.get("scenarioKey") or source.get("scenario") or "").strip(),
        "primaryStat": primary_key,
        "keys": sorted(weights),
        "weights": rounded_weights,
        "priorityOrder": priority_order,
        "ignoredReason": "" if source_accepted else "stat weight source is not accepted for recommendation",
        "normalization": {
            "scale": round(scale, 4),
            "sourceWeightCount": len(parsed_weights),
        },
    }


def season_recommended_stat_weight_scenario_keys(scenario_key=None):
    key = slugify(scenario_key or SEASON_RECOMMENDED_GEAR_SCENARIO_KEY, SEASON_RECOMMENDED_GEAR_SCENARIO_KEY)
    if key in {"mplus_aoe", "mplus_aoe_pack", "aoe_5", "aoe"}:
        return ["mplus_aoe_pack", "mplus_mixed_route"]
    if key in {"mplus_mixed_route", "mythic_plus", "dungeonslice"}:
        return ["mplus_mixed_route"]
    if key in {"mplus_single_boss", "single", "patchwerk"}:
        return ["mplus_single_boss", "mplus_mixed_route"]
    return [key, "mplus_mixed_route"]


def season_recommended_item_stats(item):
    stats = {}
    for stat in (item or {}).get("itemStats") or (item or {}).get("stats") or []:
        if not isinstance(stat, dict):
            continue
        key = season_recommended_stat_key(stat.get("key") or stat.get("statKey") or stat.get("name") or stat.get("label"))
        if key not in SEASON_RECOMMENDED_PRIMARY_STATS and key not in SEASON_RECOMMENDED_SECONDARY_STATS:
            continue
        value = season_recommended_float_value(stat.get("value"), 0.0)
        stats[key] = stats.get(key, 0.0) + value
    return stats


def season_recommended_item_level(item):
    return int(season_recommended_float_value((item or {}).get("ilevel") or (item or {}).get("itemLevel"), 0))


def season_recommended_item_id(item):
    return str((item or {}).get("itemId") or (item or {}).get("id") or "").strip()


def season_recommended_item_name(item):
    return str((item or {}).get("displayName") or (item or {}).get("name") or season_recommended_item_id(item)).strip()


def season_recommended_item_set_key(item):
    payload = (item or {}).get("payload") if isinstance((item or {}).get("payload"), dict) else {}
    value = (
        (item or {}).get("itemSetId")
        or (item or {}).get("itemSetName")
        or payload.get("itemSetId")
        or payload.get("itemSetName")
        or ""
    )
    return str(value or "").strip()


def season_recommended_item_has_special_effect(item):
    if not isinstance(item, dict):
        return False
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    text = " ".join(
        str(value or "")
        for value in (
            item.get("specialEffect"),
            item.get("effect"),
            item.get("equipEffect"),
            item.get("useEffect"),
            item.get("builtInEmbellishment"),
            item.get("embellishment"),
            item.get("embellishmentSource"),
            payload.get("specialEffect"),
            payload.get("effect"),
            payload.get("equipEffect"),
            payload.get("useEffect"),
            payload.get("builtInEmbellishment"),
            payload.get("embellishment"),
        )
    ).strip()
    return bool(text)


def season_recommended_low_yield_stats(stats, weights):
    secondary_weights = [float(weights.get(key) or 0) for key in SEASON_RECOMMENDED_SECONDARY_STATS if float(weights.get(key) or 0) > 0]
    max_secondary = max(secondary_weights or [1.0])
    threshold = max_secondary * SEASON_RECOMMENDED_LOW_YIELD_THRESHOLD_RATIO
    rows = []
    for key, amount in stats.items():
        if key not in SEASON_RECOMMENDED_SECONDARY_STATS:
            continue
        weight = float(weights.get(key) or 0)
        if amount > 0 and weight <= threshold:
            penalty = amount * max(0.0, max_secondary - weight) * SEASON_RECOMMENDED_LOW_YIELD_PENALTY_MULTIPLIER
            rows.append(
                {
                    "key": key,
                    "amount": round(amount, 3),
                    "weight": round(weight, 4),
                    "threshold": round(threshold, 4),
                    "penalty": round(penalty, 3),
                }
            )
    return rows


def season_recommended_item_score(item, weights, slot=""):
    stats = season_recommended_item_stats(item)
    item_level = season_recommended_item_level(item)
    slot = str(slot or (item or {}).get("slot") or "").strip()
    slot_multiplier = 1.35 if slot in {"main_hand", "off_hand"} else (1.1 if slot in {"trinket1", "trinket2"} else 1.0)
    item_level_score = item_level * 60.0 * slot_multiplier
    primary_score = 0.0
    secondary_score = 0.0
    for key, amount in stats.items():
        weight = float(weights.get(key) or 0)
        if key in SEASON_RECOMMENDED_PRIMARY_STATS:
            primary_score += amount * weight
        elif key in SEASON_RECOMMENDED_SECONDARY_STATS:
            secondary_score += amount * weight
    low_yield = season_recommended_low_yield_stats(stats, weights)
    low_yield_penalty = sum(row["penalty"] for row in low_yield)
    special_bonus = 0.0
    if season_recommended_item_has_special_effect(item):
        special_bonus += 90.0
    total = item_level_score + primary_score + secondary_score + special_bonus - low_yield_penalty
    return {
        "score": round(total, 3),
        "itemLevelScore": round(item_level_score, 3),
        "primaryScore": round(primary_score, 3),
        "secondaryScore": round(secondary_score, 3),
        "specialBonus": round(special_bonus, 3),
        "lowYieldPenalty": round(low_yield_penalty, 3),
        "lowYieldStats": low_yield,
        "stats": {key: round(value, 3) for key, value in stats.items()},
        "itemLevel": item_level,
    }


def season_recommended_candidate_allowed(item):
    if not isinstance(item, dict):
        return False
    if item.get("simcReady") is False:
        return False
    if str(item.get("compatibility") or "").strip().lower() == "incompatible":
        return False
    if not season_recommended_item_id(item):
        return False
    return True


def season_recommended_dedupe_candidates(candidates):
    best_by_id = {}
    for item in candidates or []:
        if not season_recommended_candidate_allowed(item):
            continue
        item_id = season_recommended_item_id(item)
        if item_id not in best_by_id:
            best_by_id[item_id] = item
            continue
        current_level = season_recommended_item_level(best_by_id[item_id])
        next_level = season_recommended_item_level(item)
        if next_level >= current_level:
            best_by_id[item_id] = item
    return list(best_by_id.values())


def season_recommended_ranked_candidates(candidates, weights, slot):
    rows = []
    for item in season_recommended_dedupe_candidates(candidates):
        score = season_recommended_item_score(item, weights, slot)
        rows.append({"item": item, "score": score})
    rows.sort(key=lambda row: (row["score"]["score"], row["score"]["itemLevel"], season_recommended_item_name(row["item"])), reverse=True)
    return rows


def season_recommended_candidates_for_slot(candidates_by_slot, slot):
    if not isinstance(candidates_by_slot, dict):
        return []
    collected = []
    for key, raw_candidates in candidates_by_slot.items():
        key_slot = normalize_slot(key)
        raw_candidates = raw_candidates if isinstance(raw_candidates, list) else []
        if key_slot == slot:
            collected.extend(raw_candidates)
            continue
        for item in raw_candidates:
            if isinstance(item, dict) and normalize_slot(item.get("slot") or item.get("simcSlot")) == slot:
                collected.append(item)
    return collected


def season_recommended_combination_set_bonus(items):
    counts = {}
    for item in items or []:
        key = season_recommended_item_set_key(item)
        if key:
            counts[key] = counts.get(key, 0) + 1
    bonus = 0.0
    details = []
    for key, count in sorted(counts.items()):
        set_bonus = 0.0
        if count >= 2:
            set_bonus += SEASON_RECOMMENDED_TIER_TWO_BONUS
        if count >= 4:
            set_bonus += SEASON_RECOMMENDED_TIER_FOUR_BONUS
        if set_bonus:
            details.append({"setKey": key, "selectedCount": count, "bonus": round(set_bonus, 3)})
            bonus += set_bonus
    return bonus, details


def season_recommended_combination_score(items, weights):
    item_total = 0.0
    for item in items or []:
        item_total += season_recommended_item_score(item, weights, item.get("slot") or item.get("simcSlot"))["score"]
    set_bonus, set_details = season_recommended_combination_set_bonus(items)
    return {
        "itemScore": round(item_total, 3),
        "setBonus": round(set_bonus, 3),
        "totalScore": round(item_total + set_bonus, 3),
        "setDetails": set_details,
    }


def season_recommended_apply_tier_four_of_five(selected_by_slot, ranked_by_slot, weights):
    replacements = []
    if not selected_by_slot:
        return selected_by_slot, {"selectedTierCount": 0, "setDetails": [], "replacements": replacements}
    by_set = {}
    for slot, item in selected_by_slot.items():
        set_key = season_recommended_item_set_key(item)
        if set_key:
            by_set.setdefault(set_key, []).append((slot, item))
    for set_key, rows in sorted(by_set.items()):
        if len(rows) < 5:
            continue
        current_items = list(selected_by_slot.values())
        current_score = season_recommended_combination_score(current_items, weights)["totalScore"]
        best_replacement = None
        for slot, current_item in rows:
            alternatives = [
                row
                for row in ranked_by_slot.get(slot, [])
                if season_recommended_item_id(row["item"]) != season_recommended_item_id(current_item)
                and season_recommended_item_set_key(row["item"]) != set_key
            ]
            if not alternatives:
                continue
            alternative = alternatives[0]
            trial = dict(selected_by_slot)
            trial[slot] = alternative["item"]
            trial_score = season_recommended_combination_score(list(trial.values()), weights)["totalScore"]
            gain = trial_score - current_score
            current_low = season_recommended_item_score(current_item, weights, slot).get("lowYieldStats") or []
            if gain > 0 or current_low:
                candidate = {
                    "slot": slot,
                    "fromItemId": season_recommended_item_id(current_item),
                    "toItemId": season_recommended_item_id(alternative["item"]),
                    "scoreDelta": round(gain, 3),
                    "reason": "replace_fifth_tier_low_yield_or_lower_score",
                    "replacedLowYieldStats": current_low,
                    "trialScore": round(trial_score, 3),
                    "currentScore": round(current_score, 3),
                }
                if best_replacement is None or candidate["scoreDelta"] > best_replacement["scoreDelta"]:
                    best_replacement = candidate
        if best_replacement:
            selected_by_slot = dict(selected_by_slot)
            slot = best_replacement["slot"]
            replacement_item = next(
                row["item"]
                for row in ranked_by_slot.get(slot, [])
                if season_recommended_item_id(row["item"]) == best_replacement["toItemId"]
            )
            selected_by_slot[slot] = replacement_item
            replacements.append(best_replacement)
    set_bonus, set_details = season_recommended_combination_set_bonus(selected_by_slot.values())
    selected_tier_count = max([detail["selectedCount"] for detail in set_details] or [0])
    return selected_by_slot, {
        "selectedTierCount": selected_tier_count,
        "setBonus": round(set_bonus, 3),
        "setDetails": set_details,
        "replacements": replacements,
    }


def select_season_recommended_gear(class_key, spec_key, candidates_by_slot, stat_weights=None, scenario_key=None, gray_zone_pct=None):
    class_key = slugify(class_key, "mage")
    spec_key = slugify(spec_key, "arcane")
    scenario_key = scenario_key or SEASON_RECOMMENDED_GEAR_SCENARIO_KEY
    gray_zone_pct = SEASON_RECOMMENDED_SIMC_GRAY_ZONE_PCT if gray_zone_pct is None else float(gray_zone_pct)
    weights, weight_evidence = normalize_season_recommended_stat_weights(class_key, spec_key, stat_weights)
    ranked_by_slot = {}
    selected_by_slot = {}
    slot_decisions = {}
    used_item_ids_by_group = {}
    candidate_count = 0
    simc_reasons = []
    for slot in CANONICAL_GEAR_SLOTS:
        candidates = season_recommended_candidates_for_slot(candidates_by_slot, slot)
        ranked = season_recommended_ranked_candidates(candidates or [], weights, slot)
        if not ranked:
            continue
        candidate_count += len(ranked)
        ranked_by_slot[slot] = ranked
        preferred = ranked[0]
        selected = preferred
        unique_group = SEASON_RECOMMENDED_UNIQUE_ITEM_SLOT_GROUPS.get(slot)
        duplicate_replacement = None
        used_ids = None
        if unique_group:
            used_ids = used_item_ids_by_group.setdefault(unique_group, set())
            replacement = next(
                (
                    row
                    for row in ranked
                    if season_recommended_item_id(row["item"])
                    and season_recommended_item_id(row["item"]) not in used_ids
                ),
                None,
            )
            if replacement:
                selected = replacement
            if selected is not preferred:
                duplicate_replacement = {
                    "blockedItemId": season_recommended_item_id(preferred["item"]),
                    "blockedName": season_recommended_item_name(preferred["item"]),
                    "selectedItemId": season_recommended_item_id(selected["item"]),
                    "selectedName": season_recommended_item_name(selected["item"]),
                    "reason": "same_item_id_already_selected_in_equivalent_slot",
                }

        def row_available_for_equivalent_slot(row):
            if not unique_group:
                return True
            item_id = season_recommended_item_id(row["item"])
            return bool(item_id) and item_id not in used_ids

        alternative = next((row for row in ranked if row is not selected and row_available_for_equivalent_slot(row)), None)
        no_low_yield_alternative = next(
            (
                row
                for row in ranked
                if row is not selected and row_available_for_equivalent_slot(row) and not row["score"].get("lowYieldStats")
            ),
            None,
        )
        low_yield_gray_zone_fallback = None
        if selected["score"].get("lowYieldStats") and no_low_yield_alternative:
            selected_score = float(selected["score"]["score"] or 0)
            alt_score = float(no_low_yield_alternative["score"]["score"] or 0)
            delta_pct = (selected_score - alt_score) / abs(selected_score or 1.0)
            if delta_pct < gray_zone_pct:
                blocked = selected
                selected = no_low_yield_alternative
                alternative = blocked
                simc_reasons.append("low_yield_stat_gray_zone")
                low_yield_gray_zone_fallback = {
                    "blockedItemId": season_recommended_item_id(blocked["item"]),
                    "blockedName": season_recommended_item_name(blocked["item"]),
                    "blockedScore": blocked["score"],
                    "selectedItemId": season_recommended_item_id(selected["item"]),
                    "selectedName": season_recommended_item_name(selected["item"]),
                    "selectedScore": selected["score"],
                    "deltaPct": round(delta_pct, 5),
                    "reason": "low_yield_candidate_within_simc_gray_zone",
                }
        if unique_group:
            selected_item_id = season_recommended_item_id(selected["item"])
            if selected_item_id:
                used_ids.add(selected_item_id)
        selected_by_slot[slot] = selected["item"]
        visible_no_low_yield_alternative = (
            no_low_yield_alternative
            if no_low_yield_alternative is not selected
            else next(
                (
                    row
                    for row in ranked
                    if row is not selected and row_available_for_equivalent_slot(row) and not row["score"].get("lowYieldStats")
                ),
                None,
            )
        )
        penalized_candidates = [row for row in ranked if row["score"].get("lowYieldStats")]
        first_penalized = penalized_candidates[0] if penalized_candidates else None
        low_penalty = {
            "applied": bool(first_penalized),
            "selectedApplied": bool(selected["score"].get("lowYieldStats")),
            "candidateItemId": season_recommended_item_id(first_penalized["item"]) if first_penalized else "",
            "stats": (first_penalized["score"].get("lowYieldStats") if first_penalized else []) or [],
            "totalPenalty": (first_penalized["score"].get("lowYieldPenalty") if first_penalized else 0) or 0,
        }
        if low_penalty["applied"] and no_low_yield_alternative:
            selected_score = float(selected["score"]["score"] or 0)
            alt_score = float(no_low_yield_alternative["score"]["score"] or 0)
            delta_pct = (selected_score - alt_score) / abs(selected_score or 1.0)
            if delta_pct < gray_zone_pct:
                simc_reasons.append("low_yield_stat_gray_zone")
        if slot in {"trinket1", "trinket2", "main_hand", "off_hand"} and alternative:
            selected_score = float(selected["score"]["score"] or 0)
            alt_score = float(alternative["score"]["score"] or 0)
            delta_pct = (selected_score - alt_score) / abs(selected_score or 1.0)
            if delta_pct < gray_zone_pct or season_recommended_item_has_special_effect(selected["item"]) or season_recommended_item_has_special_effect(alternative["item"]):
                simc_reasons.append(f"{slot}_special_rule_review")
        slot_decisions[slot] = {
            "selectedItemId": season_recommended_item_id(selected["item"]),
            "selectedName": season_recommended_item_name(selected["item"]),
            "score": selected["score"],
            "candidateCount": len(ranked),
            "lowYieldStatPenalty": low_penalty,
            "bestAlternative": (
                {
                    "itemId": season_recommended_item_id(alternative["item"]),
                    "name": season_recommended_item_name(alternative["item"]),
                    "score": alternative["score"],
                }
                if alternative
                else None
            ),
            "bestNoLowYieldAlternative": (
                {
                    "itemId": season_recommended_item_id(visible_no_low_yield_alternative["item"]),
                    "name": season_recommended_item_name(visible_no_low_yield_alternative["item"]),
                    "score": visible_no_low_yield_alternative["score"],
                }
                if visible_no_low_yield_alternative
                else None
            ),
        }
        if duplicate_replacement:
            slot_decisions[slot]["duplicateItemReplacement"] = duplicate_replacement
        if low_yield_gray_zone_fallback:
            slot_decisions[slot]["lowYieldGrayZoneFallback"] = low_yield_gray_zone_fallback
    selected_by_slot, tier_decision = season_recommended_apply_tier_four_of_five(selected_by_slot, ranked_by_slot, weights)
    selected_set_counts = {}
    for item in selected_by_slot.values():
        set_key = season_recommended_item_set_key(item)
        if set_key:
            selected_set_counts[set_key] = selected_set_counts.get(set_key, 0) + 1
    for slot, selected_item in selected_by_slot.items():
        selected_set_key = season_recommended_item_set_key(selected_item)
        if selected_set_key:
            continue
        for row in ranked_by_slot.get(slot, [])[1:]:
            alternative_set_key = season_recommended_item_set_key(row["item"])
            if not alternative_set_key or selected_set_counts.get(alternative_set_key) != 4:
                continue
            alternative_score = row.get("score") or {}
            if not alternative_score.get("lowYieldStats"):
                continue
            replacement = {
                "slot": slot,
                "fromItemId": season_recommended_item_id(row["item"]),
                "toItemId": season_recommended_item_id(selected_item),
                "scoreDelta": round(
                    season_recommended_item_score(selected_item, weights, slot)["score"] - alternative_score["score"],
                    3,
                ),
                "reason": "replace_fifth_tier_low_yield_or_lower_score",
                "replacedLowYieldStats": alternative_score.get("lowYieldStats") or [],
            }
            if replacement not in tier_decision["replacements"]:
                tier_decision["replacements"].append(replacement)
            break
    for replacement in tier_decision.get("replacements") or []:
        slot = replacement.get("slot")
        if slot in slot_decisions:
            item = selected_by_slot.get(slot)
            slot_decisions[slot]["selectedItemId"] = season_recommended_item_id(item)
            slot_decisions[slot]["selectedName"] = season_recommended_item_name(item)
            slot_decisions[slot]["score"] = season_recommended_item_score(item, weights, slot)
            slot_decisions[slot]["tierReplacement"] = replacement
            simc_reasons.append("tier_set_four_of_five_replacement")
    weapon_blockers, invalid_weapon_slots = selected_gear_weapon_rule_blockers(
        list(selected_by_slot.values()),
        class_key,
        spec_key,
    )
    weapon_rule_decision = {
        "blockers": weapon_blockers,
        "invalidSlots": sorted(invalid_weapon_slots or []),
        "removedSlots": [],
    }
    if (
        "off_hand" in invalid_weapon_slots
        and "off_hand" in selected_by_slot
        and any("selected two-hand main hand" in blocker for blocker in weapon_blockers)
    ):
        removed_item = selected_by_slot.pop("off_hand")
        removed = {
            "slot": "off_hand",
            "itemId": season_recommended_item_id(removed_item),
            "name": season_recommended_item_name(removed_item),
            "reason": "two_hand_main_hand_occupies_off_hand",
        }
        weapon_rule_decision["removedSlots"].append(removed)
        if "off_hand" in slot_decisions:
            slot_decisions["off_hand"]["removedByWeaponRule"] = removed
        simc_reasons.append("weapon_handedness_rule_review")
        weapon_blockers, invalid_weapon_slots = selected_gear_weapon_rule_blockers(
            list(selected_by_slot.values()),
            class_key,
            spec_key,
        )
        weapon_rule_decision["postRemovalBlockers"] = weapon_blockers
        weapon_rule_decision["postRemovalInvalidSlots"] = sorted(invalid_weapon_slots or [])
    selected = [selected_by_slot[slot] for slot in CANONICAL_GEAR_SLOTS if slot in selected_by_slot]
    combination = season_recommended_combination_score(selected, weights)
    simc_reasons = sorted(set(simc_reasons))
    evidence = {
        "scoringVersion": SEASON_RECOMMENDED_SCORING_VERSION,
        "scenarioKey": scenario_key,
        "candidateCount": candidate_count,
        "statWeights": weight_evidence,
        "slotDecisions": slot_decisions,
        "tierSetDecision": tier_decision,
        "weaponRuleDecision": weapon_rule_decision,
        "combinationScore": combination,
        "simcReview": {
            "triggered": bool(simc_reasons),
            "status": "required" if simc_reasons else "not_run",
            "reasons": simc_reasons,
            "result": {},
            "failureReason": "" if simc_reasons else "not required by rule scoring thresholds",
        },
        "recommendationConfidence": "provisional",
        "finalConfidence": "provisional",
    }
    return selected, evidence


def season_recommended_role_policy(class_key, spec_key, role="", simc_review=None):
    class_key = slugify(class_key, "")
    spec_key = slugify(spec_key, "")
    normalized_role = str(role or "").strip().lower()
    simc_review = simc_review if isinstance(simc_review, dict) else {}
    simc_passed = simc_review.get("status") == "passed"
    if normalized_role in {"tank", "healer", "support"} or (class_key, spec_key) == ("evoker", "augmentation"):
        return {
            "role": normalized_role or "support",
            "objectiveKey": "community_consensus_plus_simc_sanity",
            "recommendationConfidence": "provisional",
            "reason": "non-DPS specs need role-specific scoring before verified recommendation claims",
        }
    if normalized_role in {"damage", "dps"} and simc_passed:
        return {
            "role": "damage",
            "objectiveKey": "dps_mplus_aoe",
            "recommendationConfidence": "verified",
            "reason": "DPS recommendation is ranked by M+ AOE SimC score",
        }
    if normalized_role in {"damage", "dps"}:
        return {
            "role": "damage",
            "objectiveKey": "dps_mplus_aoe_rule_scoring",
            "recommendationConfidence": "provisional",
            "reason": "DPS recommendation is rule-scored; SimC review has not passed",
        }
    return {
        "role": normalized_role or "damage",
        "objectiveKey": "rule_scored_recommendation",
        "recommendationConfidence": "provisional",
        "reason": "recommendation remains provisional until SimC review or a role-specific objective validates the rule-scored result",
    }


def _template_id(class_key, spec_key, gear_items, evidence):
    seed = {
        "classKey": class_key,
        "specKey": spec_key,
        "gearItems": [
            {
                "slot": item.get("slot"),
                "itemId": item.get("itemId") or item.get("id"),
                "ilevel": item.get("ilevel") or item.get("itemLevel"),
                "bonus_id": item.get("bonus_id"),
                "gem_id": item.get("gem_id"),
                "enchant_id": item.get("enchant_id"),
                "crafted_stats": item.get("crafted_stats"),
                "embellishment": item.get("embellishment"),
            }
            for item in gear_items or []
            if isinstance(item, dict)
        ],
        "seedTemplateId": (evidence or {}).get("seedTemplateId") or "",
    }
    return f"season_recommendation_{class_key}_{spec_key}_{stable_digest(seed)}"


def build_season_recommended_gear_template(class_key, spec_key, gear_items, evidence=None):
    class_key = slugify(class_key, "mage")
    spec_key = slugify(spec_key, "arcane")
    evidence = copy.deepcopy(evidence if isinstance(evidence, dict) else {})
    ready_by_slot, occupied_slots, missing_slots = gear_template_slot_coverage(gear_items or [], class_key, spec_key)
    if missing_slots:
        raise ValueError(f"missing canonical gear slots: {', '.join(missing_slots)}")
    ordered_items = [ready_by_slot[slot] for slot in CANONICAL_GEAR_SLOTS if slot in ready_by_slot]
    raw_lines = build_websim_gear_lines(ordered_items)
    if not raw_lines:
        raise ValueError("season recommended gear template has no SimC-ready gear lines")

    simc_review = evidence.get("simcReview") if isinstance(evidence.get("simcReview"), dict) else {}
    if not simc_review:
        simc_review = {
            "triggered": False,
            "status": "not_run",
            "reasons": [],
            "result": {},
            "failureReason": "not run for this recommendation",
        }
        evidence["simcReview"] = simc_review
    role_policy = season_recommended_role_policy(class_key, spec_key, evidence.get("role"), simc_review=simc_review)
    evidence.setdefault("scenarioKey", SEASON_RECOMMENDED_GEAR_SCENARIO_KEY)
    evidence.setdefault("optimizerRunId", "")
    evidence.setdefault("candidateCount", 1)
    evidence.setdefault("simcRunCount", 0)
    evidence.setdefault("blockers", [])
    evidence.setdefault("warnings", [])
    evidence.setdefault("scoringVersion", SEASON_RECOMMENDED_SCORING_VERSION)
    evidence["rolePolicy"] = role_policy
    evidence["recommendationConfidence"] = role_policy["recommendationConfidence"]
    evidence["finalConfidence"] = role_policy["recommendationConfidence"]
    evidence.setdefault("sourceKey", SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY)
    evidence.setdefault("sourceName", SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_NAME)

    template = {
        "id": _template_id(class_key, spec_key, ordered_items, evidence),
        "name": SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_NAME,
        "classKey": class_key,
        "specKey": spec_key,
        "sourceKey": SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY,
        "sourceName": SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_NAME,
        "sourceUrl": "",
        "sourceStatus": "synced",
        "status": "complete",
        "updatedAt": evidence.get("checkedAt") or utc_now(),
        "expiresAt": season_expires_at(),
        "analysisWindow": "Current-season M+ AOE recommendation generated from verified complete gear evidence.",
        "gearItems": ordered_items,
        "rawString": "\n".join(raw_lines),
        "readySlotCount": len(CANONICAL_GEAR_SLOTS),
        "missingSlots": [],
        "canApplyGear": True,
        "scenarioKey": evidence["scenarioKey"],
        "payload": {
            "templateSlot": "baseline",
            "baselineDisplaySlot": True,
            "scenarioKey": evidence["scenarioKey"],
            "templateEvidence": evidence,
            "occupiedSlots": occupied_slots,
            "countingPolicy": "current-season recommendation baseline subtype under community import; does not count as real community gear",
        },
    }
    if occupied_slots:
        template["occupiedSlots"] = occupied_slots
    template["templateEvidence"] = evidence
    gear_signature = gear_template_signature(template)
    evidence.setdefault("gearSignature", gear_signature)
    template["signature"] = f"{SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY}:{gear_signature}"
    template["sourceRefs"] = normalize_source_refs(evidence.get("sourceRefs") or [gear_template_source_ref(template)])
    template["templateRevision"] = COMMUNITY_TEMPLATE_REVISION
    return template


def _recommended_bis_template_id(class_key, spec_key, gear_items, evidence):
    seed = {
        "classKey": class_key,
        "specKey": spec_key,
        "gearItems": [
            {
                "slot": item.get("slot"),
                "itemId": item.get("itemId") or item.get("id"),
                "ilevel": item.get("ilevel") or item.get("itemLevel"),
                "bonus_id": item.get("bonus_id"),
                "gem_id": item.get("gem_id"),
                "enchant_id": item.get("enchant_id"),
                "crafted_stats": item.get("crafted_stats"),
                "embellishment": item.get("embellishment"),
            }
            for item in gear_items or []
            if isinstance(item, dict)
        ],
        "optimizerRunId": (evidence or {}).get("optimizerRunId") or "",
        "status": (evidence or {}).get("status") or "projected_bis",
    }
    return f"recommended_bis_{class_key}_{spec_key}_{stable_digest(seed)}"


def build_recommended_bis_gear_template(class_key, spec_key, gear_items, evidence=None):
    class_key = slugify(class_key, "mage")
    spec_key = slugify(spec_key, "arcane")
    evidence = copy.deepcopy(evidence if isinstance(evidence, dict) else {})
    ready_by_slot, occupied_slots, missing_slots = gear_template_slot_coverage(gear_items or [], class_key, spec_key)
    if missing_slots:
        raise ValueError(f"missing canonical gear slots: {', '.join(missing_slots)}")
    ordered_items = [ready_by_slot[slot] for slot in CANONICAL_GEAR_SLOTS if slot in ready_by_slot]
    raw_lines = build_websim_gear_lines(ordered_items)
    if not raw_lines:
        raise ValueError("recommended_bis gear template has no SimC-ready gear lines")

    candidate_pool = evidence.get("candidatePool") if isinstance(evidence.get("candidatePool"), dict) else {}
    candidate_count = int(candidate_pool.get("candidateCount") or evidence.get("candidateCount") or len(ordered_items))
    kept_count = int(candidate_pool.get("keptCandidateCount") or len(ordered_items))
    evidence["schemaRevision"] = RECOMMENDED_BIS_SCHEMA_REVISION
    evidence["templateType"] = "recommended_bis"
    evidence.setdefault("status", "projected_bis")
    evidence.setdefault("confidence", evidence["status"])
    evidence.setdefault("optimizerVersion", RECOMMENDED_BIS_OPTIMIZER_VERSION)
    evidence.setdefault("scenarioKey", SEASON_RECOMMENDED_GEAR_SCENARIO_KEY)
    evidence["candidatePool"] = {
        "gearCatalogRevision": candidate_pool.get("gearCatalogRevision") or evidence.get("gearCatalogRevision") or "",
        "candidateCount": candidate_count,
        "keptCandidateCount": kept_count,
        "prunedCandidateCount": max(0, int(candidate_pool.get("prunedCandidateCount") or candidate_count - kept_count)),
        "sources": candidate_pool.get("sources") or evidence.get("candidatePoolSources") or [],
    }
    evidence.setdefault(
        "statPriorPolicy",
        {
            "role": "candidate_recall_only",
            "priors": RECOMMENDED_BIS_STAT_PRIORS,
            "finalDecision": "simc_gear_compare_required",
        },
    )
    simc = evidence.get("simc") if isinstance(evidence.get("simc"), dict) else {}
    simc_payload = {
        "status": simc.get("status") or "required",
        "lowIterationRuns": int(simc.get("lowIterationRuns") or 0),
        "highIterationRuns": int(simc.get("highIterationRuns") or 0),
        "pairwiseCompares": int(simc.get("pairwiseCompares") or 0),
        "winnerDps": simc.get("winnerDps"),
        "winnerErrorPct": simc.get("winnerErrorPct"),
    }
    for key in (
        "source",
        "checkedAt",
        "scenarioKey",
        "simcVersion",
        "iterations",
        "targetError",
        "manualCompare",
        "warnings",
    ):
        if key in simc:
            simc_payload[key] = simc.get(key)
    evidence["simc"] = simc_payload
    anchor_validation = evidence.get("anchorValidation") if isinstance(evidence.get("anchorValidation"), dict) else {}
    evidence["anchorValidation"] = {
        "status": anchor_validation.get("status") or "pending",
        "bestObservedCharacter": anchor_validation.get("bestObservedCharacter") or "",
        "bestObservedDps": anchor_validation.get("bestObservedDps"),
        "deltaPctVsBestObserved": anchor_validation.get("deltaPctVsBestObserved"),
        "blockThresholdPct": anchor_validation.get("blockThresholdPct") or 2,
    }
    blockers = [
        blocker for blocker in (evidence.get("blockers") or [])
        if blocker not in {
            "high-iteration SimC compare has not run",
            "recommended_bis enhancement optimization still requires SimC validation",
        } or evidence["simc"]["status"] != "passed"
    ]
    if evidence["simc"]["status"] != "passed":
        blockers.append("high-iteration SimC compare has not run")
    if evidence["simc"]["pairwiseCompares"] <= 0:
        blockers.append("pairwise gear compare has not run")
    if evidence["anchorValidation"]["status"] != "passed":
        blockers.append("observed anchor validation is pending")
    evidence["blockers"] = sorted(set(blockers))
    evidence["warnings"] = sorted(set([
        *(evidence.get("warnings") or []),
        "projected_bis is a DPS optimizer prototype and must not be displayed as verified BiS",
    ]))
    template_name = str(
        evidence.get("templateName")
        or real_player_gear_template_recommended_display_name(class_key, spec_key)
        or RECOMMENDED_BIS_GEAR_TEMPLATE_SOURCE_NAME
    ).strip()
    source_name = str(
        evidence.get("sourceName")
        or real_player_gear_template_recommended_source_name(class_key, spec_key)
        or RECOMMENDED_BIS_GEAR_TEMPLATE_SOURCE_NAME
    ).strip()
    evidence.setdefault("sourceKey", RECOMMENDED_BIS_GEAR_TEMPLATE_SOURCE_KEY)
    evidence["sourceName"] = source_name
    evidence["templateName"] = template_name

    template = {
        "id": _recommended_bis_template_id(class_key, spec_key, ordered_items, evidence),
        "name": template_name,
        "classKey": class_key,
        "specKey": spec_key,
        "sourceKey": RECOMMENDED_BIS_GEAR_TEMPLATE_SOURCE_KEY,
        "sourceName": source_name,
        "sourceUrl": "",
        "sourceStatus": "synced",
        "status": "complete",
        "updatedAt": evidence.get("checkedAt") or utc_now(),
        "expiresAt": season_expires_at(),
        "analysisWindow": "recommended_bis_v1 projected DPS prototype; blocked from verified until SimC, pairwise compare, and observed anchor validation pass.",
        "gearItems": ordered_items,
        "rawString": "\n".join(raw_lines),
        "readySlotCount": len(CANONICAL_GEAR_SLOTS),
        "missingSlots": [],
        "canApplyGear": True,
        "scenarioKey": evidence["scenarioKey"],
        "payload": {
            "templateSlot": "recommended_bis",
            "templateType": "recommended_bis",
            "scenarioKey": evidence["scenarioKey"],
            "templateEvidence": evidence,
            "occupiedSlots": occupied_slots,
            "countingPolicy": "recommended_bis_v1 projected DPS prototype; not legacy fallback and not verified BiS",
        },
    }
    if occupied_slots:
        template["occupiedSlots"] = occupied_slots
    template["templateEvidence"] = evidence
    gear_signature = gear_template_signature(template)
    evidence.setdefault("gearSignature", gear_signature)
    template["signature"] = f"{RECOMMENDED_BIS_GEAR_TEMPLATE_SOURCE_KEY}:{gear_signature}"
    template["sourceRefs"] = normalize_source_refs(evidence.get("sourceRefs") or [gear_template_source_ref(template)])
    template["templateRevision"] = COMMUNITY_TEMPLATE_REVISION
    return template

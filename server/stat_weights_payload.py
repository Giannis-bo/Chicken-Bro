#!/usr/bin/env python3
import json
import os
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from statistics import median

try:
    from .llm_client import call_chat_completion, llm_model
    from .raiderio_payload import (
        aggregate_by_spec,
        get_raiderio_payload,
        iso_after as raiderio_iso_after,
        parse_iso as raiderio_parse_iso,
        public_raiderio_summary,
        redact_secret,
    )
    from .websim_payload import (
        CLASS_LABELS_ZH,
        DEFAULT_RACE_BY_CLASS,
        GEAR_SCHEMA_REVISION,
        SPEC_LABELS,
        SPEC_LABELS_ZH,
        WOW_CLASSES,
        build_websim_gear_lines,
        gear_readiness,
        normalize_websim_gear_items,
        run_websim_simcraft_process,
        slugify,
        websim_simc_binary,
    )
except ImportError:
    from llm_client import call_chat_completion, llm_model
    from raiderio_payload import (
        aggregate_by_spec,
        get_raiderio_payload,
        iso_after as raiderio_iso_after,
        parse_iso as raiderio_parse_iso,
        public_raiderio_summary,
        redact_secret,
    )
    from websim_payload import (
        CLASS_LABELS_ZH,
        DEFAULT_RACE_BY_CLASS,
        GEAR_SCHEMA_REVISION,
        SPEC_LABELS,
        SPEC_LABELS_ZH,
        WOW_CLASSES,
        build_websim_gear_lines,
        gear_readiness,
        normalize_websim_gear_items,
        run_websim_simcraft_process,
        slugify,
        websim_simc_binary,
    )


STAT_WEIGHT_SCHEMA_REVISION = "build-stat-weights-v1"
STAT_WEIGHT_CACHE_TABLE = "build_stat_weight_cache"
STAT_WEIGHT_RUN_TABLE = "build_stat_weight_sync_runs"
STAT_WEIGHT_SOURCE_NAME = "Raider.IO + SimC"
STAT_WEIGHT_SOURCE_URL = "https://raider.io/mythic-plus-rankings"

MPLUS_SCENARIOS = [
    {
        "key": "mplus_single_boss",
        "title": "M+ 单体 Boss",
        "label": "单体",
        "fightStyle": "Patchwerk",
        "targets": 1,
        "durationSeconds": 300,
        "purposeZh": "用于判断 Tyrannical 或高血量首领窗口的副属性方向。",
    },
    {
        "key": "mplus_aoe_pack",
        "title": "M+ 小怪 AoE",
        "label": "AOE",
        "fightStyle": "HecticAddCleave",
        "targets": 5,
        "durationSeconds": 180,
        "purposeZh": "用于判断密集小怪波次、爆发和资源循环下的副属性方向。",
    },
    {
        "key": "mplus_mixed_route",
        "title": "M+ 混合路线",
        "label": "混合",
        "fightStyle": "DungeonSlice",
        "targets": 5,
        "durationSeconds": 300,
        "purposeZh": "用于判断一条大秘境路线里单体、顺劈和小怪波次混合后的参考方向。",
    },
]

STAT_LABELS = {
    "intellect": "智力",
    "agility": "敏捷",
    "strength": "力量",
    "crit": "暴击",
    "haste": "急速",
    "mastery": "精通",
    "versatility": "全能",
}
SIMC_PRIMARY_KEYS = {
    "intellect": "int",
    "agility": "agi",
    "strength": "str",
}
SECONDARY_KEYS = ["crit", "haste", "mastery", "versatility"]
SCALE_FACTOR_ALIASES = {
    "intellect": ["intellect", "int"],
    "agility": ["agility", "agi"],
    "strength": ["strength", "str"],
    "crit": ["critical strike", "critical_strike", "crit"],
    "haste": ["haste"],
    "mastery": ["mastery"],
    "versatility": ["versatility", "vers"],
}
TANK_SPECS = {
    ("deathknight", "blood"),
    ("demonhunter", "vengeance"),
    ("druid", "guardian"),
    ("monk", "brewmaster"),
    ("paladin", "protection"),
    ("warrior", "protection"),
}
HEALER_SPECS = {
    ("druid", "restoration"),
    ("evoker", "preservation"),
    ("monk", "mistweaver"),
    ("paladin", "holy"),
    ("priest", "discipline"),
    ("priest", "holy"),
    ("shaman", "restoration"),
}
INTELLECT_SPECS = {
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
STRENGTH_CLASSES = {"deathknight", "warrior"}
FORBIDDEN_STRONG_COPY = re.compile(r"(最优|毕业|必堆|唯一答案|无脑堆|唯一正确)", re.I)


def utc_now():
    return datetime.now(timezone.utc)


def utc_now_iso():
    return utc_now().isoformat(timespec="seconds")


def iso_after(hours):
    return (utc_now() + timedelta(hours=hours)).isoformat(timespec="seconds")


def parse_iso(value):
    return raiderio_parse_iso(value)


def safe_date(value):
    text = str(value or "")
    return text[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", text) else utc_now_iso()[:10]


def int_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def ensure_stat_weight_tables(conn):
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {STAT_WEIGHT_CACHE_TABLE} (
            class_key TEXT NOT NULL,
            spec_key TEXT NOT NULL,
            scenario_key TEXT NOT NULL,
            status TEXT NOT NULL,
            value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            stale_at TEXT NOT NULL,
            PRIMARY KEY (class_key, spec_key, scenario_key)
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {STAT_WEIGHT_RUN_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            refresh_mode TEXT NOT NULL,
            refreshed_at TEXT NOT NULL,
            status TEXT NOT NULL,
            accepted_count INTEGER NOT NULL,
            blocked_count INTEGER NOT NULL,
            message TEXT NOT NULL
        )
        """
    )


def specialization_role(class_key, spec_key):
    key = (class_key, spec_key)
    if key in TANK_SPECS:
        return "tank"
    if key in HEALER_SPECS:
        return "healer"
    if key == ("evoker", "augmentation"):
        return "support"
    return "dps"


def primary_stat_key(class_key, spec_key):
    if (class_key, spec_key) in INTELLECT_SPECS:
        return "intellect"
    if class_key in STRENGTH_CLASSES or (class_key == "paladin" and spec_key in {"protection", "retribution"}):
        return "strength"
    return "agility"


def simc_role(class_key, spec_key):
    return "spell" if primary_stat_key(class_key, spec_key) == "intellect" else "attack"


def stat_weight_forced_profile_options(spec_meta, scenario):
    class_key = str((spec_meta or {}).get("classKey") or "").strip().lower()
    spec_key = str((spec_meta or {}).get("specKey") or "").strip().lower()
    scenario_key = str((scenario or {}).get("key") or "").strip()
    fight_style = str((scenario or {}).get("fightStyle") or "").strip()
    if (
        class_key == "demonhunter"
        and spec_key == "devourer"
        and scenario_key == "mplus_mixed_route"
        and fight_style == "DungeonSlice"
    ):
        return ["demonhunter.enable_dungeon_slice=1"]
    return []


def specialization_registry():
    specs = []
    for klass in WOW_CLASSES:
        class_key = klass.get("key") or ""
        for spec_key in klass.get("specs") or []:
            specs.append(
                {
                    "classKey": class_key,
                    "specKey": spec_key,
                    "specId": f"{class_key}-{spec_key}",
                    "className": CLASS_LABELS_ZH.get(class_key, klass.get("label") or class_key),
                    "specName": SPEC_LABELS_ZH.get(spec_key, SPEC_LABELS.get(spec_key, spec_key)),
                    "role": specialization_role(class_key, spec_key),
                    "primaryStat": primary_stat_key(class_key, spec_key),
                }
            )
    return specs


def normalize_list_option(values):
    if not isinstance(values, list):
        values = [values] if values else []
    result = []
    for value in values:
        if isinstance(value, dict):
            candidate = (
                value.get("id")
                or value.get("item_id")
                or value.get("itemId")
                or value.get("bonus_id")
                or value.get("bonusId")
                or value.get("enchant_id")
                or value.get("enchantId")
            )
        else:
            candidate = value
        text = str(candidate or "").strip()
        if text and text not in result:
            result.append(text)
    return "/".join(result)


def gear_items_from_profile(profile, class_key, spec_key):
    raw_items = profile.get("gear") or []
    converted = []
    for item in raw_items if isinstance(raw_items, list) else []:
        if not isinstance(item, dict):
            continue
        converted_item = dict(item)
        converted_item.setdefault("sourceType", "manual")
        converted_item.setdefault("source", "Raider.IO")
        if item.get("itemLevel") and not converted_item.get("ilevel"):
            converted_item["ilevel"] = item.get("itemLevel")
        if item.get("bonuses") and not converted_item.get("bonus_id"):
            converted_item["bonus_id"] = normalize_list_option(item.get("bonuses"))
        if item.get("gems") and not converted_item.get("gem_id"):
            converted_item["gem_id"] = normalize_list_option(item.get("gems"))
        if item.get("enchants") and not converted_item.get("enchant_id"):
            converted_item["enchant_id"] = normalize_list_option(item.get("enchants"))
        converted.append(converted_item)
    return normalize_websim_gear_items(converted, class_key, spec_key)


def profile_class_key(profile):
    return str(profile.get("classKey") or slugify(profile.get("className") or profile.get("class") or "", "")).strip()


def profile_spec_key(profile):
    return str(profile.get("specKey") or slugify(profile.get("specName") or profile.get("spec") or "", "")).strip()


def profile_import_code(profile):
    talent = profile.get("talentLoadout") or profile.get("talent_loadout") or {}
    if isinstance(talent, dict):
        return str(talent.get("rawImportCode") or talent.get("loadout_text") or talent.get("importCode") or "").strip()
    return ""


def representative_profile_candidates(raiderio, aggregate, spec_meta):
    class_key = spec_meta["classKey"]
    spec_key = spec_meta["specKey"]
    profiles = [
        profile
        for profile in (raiderio.get("profiles") or [])
        if profile_class_key(profile) == class_key and profile_spec_key(profile) == spec_key and profile_import_code(profile)
    ]
    if not profiles and aggregate:
        for loadout in aggregate.get("talentLoadouts") or []:
            if loadout.get("rawImportCode") and aggregate.get("observedGear"):
                profiles.append(
                    {
                        "name": loadout.get("characterName") or f"{class_key}-{spec_key}",
                        "profileUrl": loadout.get("profileUrl") or "",
                        "classKey": class_key,
                        "specKey": spec_key,
                        "talentLoadout": {"rawImportCode": loadout.get("rawImportCode")},
                        "gear": aggregate.get("observedGear") or [],
                        "itemLevel": aggregate.get("itemLevel") or 0,
                    }
                )
    profiles.sort(key=lambda item: float(item.get("itemLevel") or 0), reverse=True)
    return profiles[: max(1, int_env("WOW_STAT_WEIGHTS_PROFILE_LIMIT", 3))]


def ready_profile_candidate(profile, spec_meta):
    class_key = spec_meta["classKey"]
    spec_key = spec_meta["specKey"]
    gear_items = gear_items_from_profile(profile, class_key, spec_key)
    readiness = gear_readiness(gear_items)
    import_code = profile_import_code(profile)
    blockers = []
    if not import_code:
        blockers.append("missing Raider.IO talent loadout")
    if not readiness.get("fullReady"):
        blockers.extend(readiness.get("warnings") or ["profile gear is not SimC-ready"])
    return {
        "name": profile.get("name") or f"{class_key}-{spec_key}",
        "profileUrl": profile.get("profileUrl") or "",
        "importCode": import_code,
        "gearItems": gear_items,
        "readiness": readiness,
        "blockers": blockers,
        "ready": bool(import_code and readiness.get("fullReady")),
    }


def build_stat_weight_profile(candidate, spec_meta, scenario):
    class_key = spec_meta["classKey"]
    spec_key = spec_meta["specKey"]
    race = DEFAULT_RACE_BY_CLASS.get(class_key, "troll")
    actor = slugify(candidate.get("name") or f"{class_key}_{spec_key}", f"{class_key}_{spec_key}")
    primary = primary_stat_key(class_key, spec_key)
    scale_only = ",".join([SIMC_PRIMARY_KEYS[primary], *SECONDARY_KEYS])
    forced_options = stat_weight_forced_profile_options(spec_meta, scenario)
    lines = [
        f'{class_key}="{actor}"',
        f"level={int_env('WOW_STAT_WEIGHTS_LEVEL', 90)}",
        f"race={race}",
        f"role={simc_role(class_key, spec_key)}",
        f"spec={spec_key}",
        f"talents={candidate['importCode']}",
        *build_websim_gear_lines(candidate.get("gearItems") or []),
        f"iterations={int_env('WOW_STAT_WEIGHTS_SIMC_ITERATIONS', 2000)}",
        f"fight_style={scenario['fightStyle']}",
        f"desired_targets={scenario['targets']}",
        f"max_time={scenario['durationSeconds']}",
        "vary_combat_length=0.2",
        *forced_options,
        "calculate_scale_factors=1",
        f"scale_only={scale_only}",
    ]
    return "\n".join(line for line in lines if line).strip()


def run_stat_weight_simcraft(profile):
    binary = websim_simc_binary()
    if not binary:
        return {"ran": False, "available": False, "rawOutput": "", "error": "simcraft binary not found"}
    try:
        result = run_websim_simcraft_process(
            binary,
            profile,
            int_env("WOW_STAT_WEIGHTS_SIMC_TIMEOUT_SECONDS", 90),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ran": False, "available": True, "rawOutput": "", "error": str(error)}
    output = (result.stdout or result.stderr or "").strip()
    return {
        "ran": result.returncode == 0,
        "available": True,
        "rawOutput": output,
        "error": "" if result.returncode == 0 else (result.stderr or f"simc exited {result.returncode}")[:1000],
    }


def scale_factor_section(output):
    text = str(output or "")
    match = re.search(r"(?im)^\s*scale\s+factors?\s*:?\s*$", text)
    if not match:
        return ""
    section = text[match.start() : match.start() + 3000]
    stop = re.search(r"\n\s*(scale\s+deltas|pawn|plots?|gear\s+ranking|dps\s+ranking)\b", section, flags=re.I)
    if stop:
        section = section[: stop.start()]
    return section


def parse_stat_weight_scale_factors(output):
    section = scale_factor_section(output)
    if not section:
        return {}
    factors = {}
    for key, aliases in SCALE_FACTOR_ALIASES.items():
        for alias in aliases:
            alias_pattern = re.escape(alias).replace("\\ ", r"\s+")
            pattern = rf"(?<![A-Za-z0-9_]){alias_pattern}(?![A-Za-z0-9_])\s*(?:[:=]|rating)?\s*([+-]?\d+(?:\.\d+)?)"
            match = re.search(pattern, section, flags=re.I)
            if match:
                try:
                    factors[key] = float(match.group(1))
                    break
                except (TypeError, ValueError):
                    pass
    if not all(key in factors for key in SECONDARY_KEYS):
        return {}
    return factors


def format_scale_value(value):
    return f"{float(value):.3f}".rstrip("0").rstrip(".")


def weight_rows_from_factors(factors, primary_key):
    rows = []
    if primary_key in factors:
        rows.append(
            {
                "key": primary_key,
                "name": STAT_LABELS.get(primary_key, primary_key),
                "value": format_scale_value(factors[primary_key]),
                "rawValue": factors[primary_key],
                "percent": 100,
                "kind": "primary",
            }
        )
    secondary_values = [factors.get(key, 0) for key in SECONDARY_KEYS]
    max_secondary = max([value for value in secondary_values if value > 0] or [1])
    for key in sorted(SECONDARY_KEYS, key=lambda item: factors.get(item, 0), reverse=True):
        value = float(factors.get(key) or 0)
        rows.append(
            {
                "key": key,
                "name": STAT_LABELS.get(key, key),
                "value": format_scale_value(value),
                "rawValue": value,
                "percent": max(1, round((value / max_secondary) * 100)) if value > 0 else 1,
                "kind": "secondary",
            }
        )
    return rows


def median_factors(results):
    merged = {}
    for key in set().union(*(result.keys() for result in results)):
        values = [result[key] for result in results if key in result]
        if values:
            merged[key] = float(median(values))
    return merged


def simc_build_label():
    path = os.environ.get("WOW_SIMC_VERSION_FILE", "").strip()
    if not path:
        return ""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.loads(handle.read())
    except (OSError, json.JSONDecodeError):
        return ""
    return str(payload.get("localTag") or payload.get("image") or payload.get("latestTag") or "")


def read_cached_stat_weight(conn, class_key, spec_key, scenario_key):
    ensure_stat_weight_tables(conn)
    row = conn.execute(
        f"""
        SELECT value_json, status, updated_at, expires_at, stale_at
        FROM {STAT_WEIGHT_CACHE_TABLE}
        WHERE class_key = ? AND spec_key = ? AND scenario_key = ?
        """,
        (class_key, spec_key, scenario_key),
    ).fetchone()
    if not row:
        return None
    try:
        payload = json.loads(row[0])
    except json.JSONDecodeError:
        return None
    payload.setdefault("sourceStatus", row[1])
    payload.setdefault("updatedAt", row[2])
    payload.setdefault("expiresAt", row[3])
    payload.setdefault("staleAt", row[4])
    return payload


def write_cached_stat_weight(conn, payload):
    ensure_stat_weight_tables(conn)
    conn.execute(
        f"""
        INSERT INTO {STAT_WEIGHT_CACHE_TABLE}
            (class_key, spec_key, scenario_key, status, value_json, updated_at, expires_at, stale_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(class_key, spec_key, scenario_key) DO UPDATE SET
            status=excluded.status,
            value_json=excluded.value_json,
            updated_at=excluded.updated_at,
            expires_at=excluded.expires_at,
            stale_at=excluded.stale_at
        """,
        (
            payload.get("classKey") or "",
            payload.get("specKey") or "",
            payload.get("scenarioKey") or "",
            payload.get("sourceStatus") or payload.get("status") or "blocked",
            json.dumps(payload, ensure_ascii=False),
            payload.get("checkedAt") or utc_now_iso(),
            payload.get("expiresAt") or iso_after(int_env("WOW_STAT_WEIGHTS_TTL_HOURS", 24)),
            payload.get("staleAt") or iso_after(int_env("WOW_STAT_WEIGHTS_STALE_HOURS", 96)),
        ),
    )


def cached_translation_is_fresh(cached):
    if not cached:
        return False
    if cached.get("translationStatus") != "llm":
        return False
    expires_at = parse_iso(cached.get("expiresAt"))
    return bool(expires_at and expires_at > utc_now())


def extract_json_object(text):
    source = str(text or "").strip()
    source = re.sub(r"^```(?:json)?\s*", "", source, flags=re.I).strip()
    source = re.sub(r"\s*```$", "", source).strip()
    try:
        payload = json.loads(source)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", source, flags=re.S)
        if not match:
            return {}
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return payload if isinstance(payload, dict) else {}


def has_cjk(text):
    return bool(re.search(r"[\u4e00-\u9fff]", str(text or "")))


def evidence_allowed_numbers(evidence):
    allowed = set()
    text = json.dumps(evidence, ensure_ascii=False)
    for value in re.findall(r"\d+(?:\.\d+)?", text):
        allowed.add(value.rstrip("0").rstrip(".") if "." in value else value)
    return allowed


def unexpected_numbers(text, allowed):
    unexpected = []
    for value in re.findall(r"\d+(?:\.\d+)?", str(text or "")):
        normalized = value.rstrip("0").rstrip(".") if "." in value else value
        if normalized not in allowed:
            unexpected.append(value)
    return unexpected


def normalize_llm_translation(payload, evidence):
    summary = str(payload.get("summaryZh") or "").strip()
    recommendations = [str(item).strip() for item in payload.get("recommendationsZh") or [] if str(item).strip()]
    warnings = [str(item).strip() for item in payload.get("warningsZh") or [] if str(item).strip()]
    text = "\n".join([summary, *recommendations, *warnings])
    if not summary or not has_cjk(text):
        return None, "invalid_chinese_translation"
    if FORBIDDEN_STRONG_COPY.search(text):
        return None, "strong_claim_blocked"
    unexpected = unexpected_numbers(text, evidence_allowed_numbers(evidence))
    if unexpected:
        return None, f"unexpected_llm_numbers: {', '.join(unexpected[:4])}"
    return {
        "summaryZh": summary,
        "recommendationsZh": recommendations[:4],
        "warningsZh": warnings[:4],
        "translationStatus": "llm",
        "translationModel": llm_model(),
    }, ""


def translate_stat_weight_evidence(evidence):
    prompt = "\n".join(
        [
            "请把下面的魔兽世界属性权重 evidence JSON 翻译并解释成中文。",
            "只返回 JSON，不要 Markdown，不要添加 evidence 之外的数字。",
            "JSON schema: {\"summaryZh\":\"中文摘要\",\"recommendationsZh\":[\"建议\"],\"warningsZh\":[\"边界\"]}",
            "硬规则：只能解释已给出的 Raider.IO 样本、SimC 权重和场景；不要写最优、毕业、必堆、唯一答案。",
            "硬规则：坦克/治疗只能给场景边界，不能把 DPS scale factors 说成生存或治疗权重。",
            json.dumps(evidence, ensure_ascii=False),
        ]
    )
    result = call_chat_completion(
        "你是面向中文魔兽世界玩家的构筑数据翻译员。你只翻译和解释后端 evidence，不生成新数字。",
        prompt,
        temperature=0.1,
    )
    if result.get("error") or not result.get("content"):
        return None, result.get("error") or "empty llm response"
    payload = extract_json_object(result.get("content"))
    if not payload:
        return None, "invalid llm json"
    return normalize_llm_translation(payload, evidence)


def status_from_counts(success_count, translation_status, raiderio_status, sample_count):
    if success_count <= 0:
        return "blocked"
    if raiderio_status == "stale":
        return "stale"
    if (
        sample_count >= int_env("WOW_STAT_WEIGHTS_VERIFIED_MIN_SAMPLES", 3)
        and success_count >= int_env("WOW_STAT_WEIGHTS_VERIFIED_MIN_PROFILES", 2)
        and translation_status in {"llm", "llm_reused"}
    ):
        return "verified"
    return "partial"


def role_boundary_warnings(spec_meta):
    if spec_meta["role"] == "tank":
        return ["坦克属性仍要结合承伤模型、主动减伤覆盖和副本压力；这里不是生存权重。"]
    if spec_meta["role"] == "healer":
        return ["治疗属性仍要结合队伍掉血模型、冷却规划和 HPS/驱散压力；这里不是治疗量权重。"]
    if spec_meta["role"] == "support":
        return ["辅助输出价值会随队友爆发窗口变化；这里只解释当前样本 profile 的 SimC 权重。"]
    return []


def build_scenario_payload(conn, spec_meta, scenario, raiderio, aggregate, ready_profiles, blocked_profile_notes):
    checked_at = utc_now_iso()
    raiderio_summary = public_raiderio_summary(raiderio, aggregate)
    source_status = raiderio.get("sourceStatus") or "blocked"
    forced_options = stat_weight_forced_profile_options(spec_meta, scenario)
    blockers = []
    simc_results = []
    simc_errors = []
    if not aggregate or not int(aggregate.get("sampleCount") or 0):
        blockers.append("Raider.IO has no cached samples for this specialization.")
    sample_count = int((aggregate or {}).get("sampleCount") or 0)
    min_sample_count = int_env("WOW_STAT_WEIGHTS_VERIFIED_MIN_SAMPLES", 3)
    if 0 < sample_count < min_sample_count:
        blockers.append(f"Raider.IO sample count {sample_count} is below verified threshold {min_sample_count}.")
    if source_status in {"missing_credentials", "blocked"}:
        blockers.append(f"Raider.IO source is {source_status}.")
    if not ready_profiles:
        blockers.append("No Raider.IO representative profile has both talent loadout and SimC-ready gear.")
        blockers.extend(blocked_profile_notes[:3])
    for profile in ready_profiles:
        simc_profile = build_stat_weight_profile(profile, spec_meta, scenario)
        result = run_stat_weight_simcraft(simc_profile)
        if not result.get("ran"):
            simc_errors.append(redact_secret(result.get("error") or "SimC failed"))
            continue
        factors = parse_stat_weight_scale_factors(result.get("rawOutput") or "")
        if not factors:
            simc_errors.append("SimC output did not include parseable Scale Factors.")
            continue
        simc_results.append(factors)
    if simc_errors and not simc_results:
        blockers.extend(simc_errors[:3])
    merged_factors = median_factors(simc_results) if simc_results else {}
    primary = spec_meta["primaryStat"]
    weights = weight_rows_from_factors(merged_factors, primary) if merged_factors else []
    evidence = {
        "classKey": spec_meta["classKey"],
        "specKey": spec_meta["specKey"],
        "className": spec_meta["className"],
        "specName": spec_meta["specName"],
        "role": spec_meta["role"],
        "scenarioKey": scenario["key"],
        "scenarioTitle": scenario["title"],
        "sampleCount": int((aggregate or {}).get("sampleCount") or 0),
        "profileCount": len(ready_profiles),
        "simcSuccessCount": len(simc_results),
        "weights": weights,
        "sourceStatus": source_status,
    }
    translation, translation_error = (None, "")
    if weights:
        translation, translation_error = translate_stat_weight_evidence(evidence)
    previous = read_cached_stat_weight(conn, spec_meta["classKey"], spec_meta["specKey"], scenario["key"])
    translation_status = "blocked"
    summary_zh = ""
    recommendations_zh = []
    warnings_zh = role_boundary_warnings(spec_meta)
    if translation:
        translation_status = "llm"
        summary_zh = translation["summaryZh"]
        recommendations_zh = translation["recommendationsZh"]
        warnings_zh = [*translation.get("warningsZh", []), *warnings_zh]
    elif weights and cached_translation_is_fresh(previous):
        translation_status = "llm_reused"
        summary_zh = previous.get("summaryZh") or ""
        recommendations_zh = previous.get("recommendationsZh") or []
        warnings_zh = [*(previous.get("warningsZh") or []), *warnings_zh]
    elif weights:
        blockers.append(f"translation_blocked: {translation_error or 'llm unavailable'}")
    status = status_from_counts(len(simc_results), translation_status, source_status, sample_count)
    if status == "blocked" and not blockers:
        blockers.append("No verified stat weight evidence was produced.")
    payload = {
        "schemaRevision": STAT_WEIGHT_SCHEMA_REVISION,
        "classKey": spec_meta["classKey"],
        "specKey": spec_meta["specKey"],
        "className": spec_meta["className"],
        "specName": spec_meta["specName"],
        "role": spec_meta["role"],
        "scenarioKey": scenario["key"],
        "scenarioTitle": scenario["title"],
        "scenarioLabel": scenario["label"],
        "scenarioPurposeZh": scenario["purposeZh"],
        "sourceName": STAT_WEIGHT_SOURCE_NAME,
        "sourceUrl": raiderio_summary.get("sourceUrl") or STAT_WEIGHT_SOURCE_URL,
        "sourceStatus": status,
        "sourceStatusLabel": status,
        "publishedAt": safe_date(checked_at),
        "checkedAt": checked_at,
        "updatedAt": checked_at,
        "expiresAt": iso_after(int_env("WOW_STAT_WEIGHTS_TTL_HOURS", 24)),
        "staleAt": iso_after(int_env("WOW_STAT_WEIGHTS_STALE_HOURS", 96)),
        "analysisWindow": f"{raiderio.get('region') or 'cn'} {raiderio.get('seasonSlug') or ''} Raider.IO samples + SimC {scenario['label']} scale factors",
        "sourceNote": "Raider.IO provides representative M+ profile samples; SimC produces scale factors; LLM only translates verified evidence.",
        "primaryStat": primary,
        "weights": weights,
        "rawScaleFactors": merged_factors,
        "summaryZh": summary_zh,
        "recommendationsZh": recommendations_zh,
        "warningsZh": warnings_zh[:6],
        "translationStatus": translation_status,
        "translationModel": llm_model(),
        "validation": {
            "sampleCount": int((aggregate or {}).get("sampleCount") or 0),
            "profileCount": len(ready_profiles),
            "profileCandidateCount": len(ready_profiles) + len(blocked_profile_notes),
            "simcSuccessCount": len(simc_results),
            "simcErrorCount": len(simc_errors),
            "requiredSuccessCount": int_env("WOW_STAT_WEIGHTS_VERIFIED_MIN_PROFILES", 2),
            "raiderioStatus": source_status,
            "raiderioCheckedAt": raiderio.get("checkedAt") or "",
            "simcBuild": simc_build_label(),
            "forcedOptions": forced_options,
            "gearSchemaRevision": GEAR_SCHEMA_REVISION,
            "blockers": blockers[:8],
        },
        "blockers": blockers[:8],
    }
    return payload


def sync_stat_weight_cache(conn, raiderio_payload=None, refresh_mode="scheduled"):
    ensure_stat_weight_tables(conn)
    raiderio = raiderio_payload or get_raiderio_payload(conn)
    aggregates = aggregate_by_spec(raiderio)
    accepted = 0
    blocked = 0
    errors = []
    spec_limit = int_env("WOW_STAT_WEIGHTS_SPEC_LIMIT", 0)
    registry = specialization_registry()
    if spec_limit > 0:
        registry = registry[:spec_limit]
    for spec_meta in registry:
        aggregate = aggregates.get(f"{spec_meta['classKey']}:{spec_meta['specKey']}") or {}
        raw_profiles = representative_profile_candidates(raiderio, aggregate, spec_meta)
        ready_profiles = []
        blocked_profile_notes = []
        for raw_profile in raw_profiles:
            candidate = ready_profile_candidate(raw_profile, spec_meta)
            if candidate["ready"]:
                ready_profiles.append(candidate)
            else:
                blocked_profile_notes.extend(candidate.get("blockers") or [])
        for scenario in MPLUS_SCENARIOS:
            try:
                payload = build_scenario_payload(conn, spec_meta, scenario, raiderio, aggregate, ready_profiles, blocked_profile_notes)
                write_cached_stat_weight(conn, payload)
                if payload["sourceStatus"] in {"verified", "partial", "stale"}:
                    accepted += 1
                else:
                    blocked += 1
            except Exception as error:
                blocked += 1
                errors.append(f"{spec_meta['classKey']}:{spec_meta['specKey']}:{scenario['key']}: {error}")
    status = "verified" if accepted and not blocked else ("partial" if accepted else "blocked")
    refreshed_at = utc_now_iso()
    message = {
        "schemaRevision": STAT_WEIGHT_SCHEMA_REVISION,
        "sourceName": STAT_WEIGHT_SOURCE_NAME,
        "sourceStatus": status,
        "specCount": len(registry),
        "scenarioCount": len(MPLUS_SCENARIOS),
        "acceptedCount": accepted,
        "blockedCount": blocked,
        "raiderioStatus": raiderio.get("sourceStatus") or "blocked",
        "raiderioCheckedAt": raiderio.get("checkedAt") or "",
        "errors": errors[:12],
    }
    conn.execute(
        f"""
        INSERT INTO {STAT_WEIGHT_RUN_TABLE}
            (refresh_mode, refreshed_at, status, accepted_count, blocked_count, message)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (refresh_mode, refreshed_at, status, accepted, blocked, json.dumps(message, ensure_ascii=False)),
    )
    return {"refreshMode": refresh_mode, "refreshedAt": refreshed_at, **message}


def scenario_blocked_payload(class_key, spec_key, scenario, reason):
    now = utc_now_iso()
    return {
        "schemaRevision": STAT_WEIGHT_SCHEMA_REVISION,
        "classKey": class_key,
        "specKey": spec_key,
        "scenarioKey": scenario["key"],
        "scenarioTitle": scenario["title"],
        "scenarioLabel": scenario["label"],
        "scenarioPurposeZh": scenario["purposeZh"],
        "sourceName": STAT_WEIGHT_SOURCE_NAME,
        "sourceUrl": STAT_WEIGHT_SOURCE_URL,
        "sourceStatus": "blocked",
        "publishedAt": safe_date(now),
        "checkedAt": now,
        "updatedAt": "",
        "expiresAt": "",
        "staleAt": "",
        "analysisWindow": "stat weight cache unavailable",
        "sourceNote": "No verified Raider.IO + SimC stat weight cache is available.",
        "weights": [],
        "summaryZh": "",
        "recommendationsZh": [],
        "warningsZh": ["属性权重缓存不可用，不能把静态趋势当作当前赛季结论。"],
        "translationStatus": "blocked",
        "validation": {
            "sampleCount": 0,
            "profileCount": 0,
            "simcSuccessCount": 0,
            "blockers": [reason],
        },
        "blockers": [reason],
    }


def with_cache_freshness(payload):
    if not payload:
        return None
    expires_at = parse_iso(payload.get("expiresAt"))
    stale_at = parse_iso(payload.get("staleAt"))
    now = utc_now()
    if expires_at and expires_at > now:
        return payload
    copy = dict(payload)
    if stale_at and stale_at > now:
        copy["sourceStatus"] = "stale"
        copy.setdefault("warningsZh", [])
        copy["warningsZh"] = [*copy["warningsZh"], "属性权重缓存已过期但仍在 stale 窗口内，只能作为临时参考。"]
        return copy
    copy["sourceStatus"] = "blocked"
    copy["blockers"] = [*(copy.get("blockers") or []), "stat weight cache is expired"]
    copy.setdefault("validation", {})
    copy["validation"]["blockers"] = copy["blockers"]
    return copy


def merge_stat_weight_section(existing_section, scenario_payloads):
    section = dict(existing_section or {})
    default_key = "mplus_mixed_route"
    default_payload = next((item for item in scenario_payloads if item.get("scenarioKey") == default_key), None) or scenario_payloads[0]
    fallback_stats = section.get("stats") or []
    stats = default_payload.get("weights") or fallback_stats
    section.update(
        {
            "defaultScenarioKey": default_key,
            "scenarioWeights": scenario_payloads,
            "stats": stats,
            "sourceName": default_payload.get("sourceName") or section.get("sourceName") or STAT_WEIGHT_SOURCE_NAME,
            "sourceUrl": default_payload.get("sourceUrl") or section.get("sourceUrl") or STAT_WEIGHT_SOURCE_URL,
            "sourceStatus": default_payload.get("sourceStatus") or "blocked",
            "publishedAt": default_payload.get("publishedAt") or section.get("publishedAt") or safe_date(""),
            "analysisWindow": default_payload.get("analysisWindow") or section.get("analysisWindow") or "",
            "sourceNote": default_payload.get("sourceNote") or section.get("sourceNote") or "",
            "validation": default_payload.get("validation") or {},
            "recommendationsZh": default_payload.get("recommendationsZh") or [],
            "warningsZh": default_payload.get("warningsZh") or [],
            "translationStatus": default_payload.get("translationStatus") or "blocked",
        }
    )
    return section


def enrich_builds_detail_stat_weights(conn, payload):
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
    ensure_stat_weight_tables(conn)
    scenario_payloads = []
    for scenario in MPLUS_SCENARIOS:
        cached = with_cache_freshness(read_cached_stat_weight(conn, class_key, spec_key, scenario["key"]))
        scenario_payloads.append(cached or scenario_blocked_payload(class_key, spec_key, scenario, "stat weight cache is empty"))
    next_details = dict(details)
    next_details["statWeights"] = merge_stat_weight_section(existing, scenario_payloads)
    result = dict(payload)
    result["details"] = next_details
    return result


def latest_stat_weight_run_payload(conn):
    ensure_stat_weight_tables(conn)
    row = conn.execute(
        f"""
        SELECT refresh_mode, refreshed_at, status, accepted_count, blocked_count, message
        FROM {STAT_WEIGHT_RUN_TABLE}
        ORDER BY id DESC LIMIT 1
        """
    ).fetchone()
    if not row:
        return {
            "refreshMode": "",
            "refreshedAt": "",
            "status": "blocked",
            "acceptedCount": 0,
            "blockedCount": 0,
            "message": {"errors": ["No stat weight sync run has completed."]},
        }
    try:
        message = json.loads(row[5])
    except json.JSONDecodeError:
        message = {}
    return {
        "refreshMode": row[0],
        "refreshedAt": row[1],
        "status": row[2],
        "acceptedCount": row[3],
        "blockedCount": row[4],
        **message,
    }


if __name__ == "__main__":
    with sqlite3.connect(os.environ.get("WOW_NEWS_DB", "server/data/wow_news.sqlite3")) as connection:
        print(json.dumps(sync_stat_weight_cache(connection), ensure_ascii=False, indent=2))

import json
import os
import re
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


RAIDERIO_BASE_URL = "https://raider.io/api/v1"
RAIDERIO_CACHE_KEY = "raiderio_payload_v1"
RAIDERIO_SOURCE_NAME = "Raider.IO"
DEFAULT_REGION = "cn"
DEFAULT_LOCALE = "cn"
DEFAULT_SEASON_SLUG = "season-mn-1"
DEFAULT_EXPANSION_ID = "11"
SPEC_LADDER_REFERENCE_STATUS = "source_reference"
SPEC_LADDER_REFERENCE_LABEL = "Reference only"
SPEC_LADDER_REFERENCE_BLOCKERS = [
    "Spec ladder remains source_reference until an authorized Archon or Warcraft Logs statistics API is connected.",
    "Raider.IO samples may inform Mythic+ trends, but they do not replace WCL combat-log statistics.",
]
SPEC_LADDER_EVIDENCE_REFS = ["pve.specLadder.raiderioTrend", "pve.sourcePolicy.authorizedApiRequired"]

CLASS_ALIASES = {
    "death_knight": "deathknight",
    "demon_hunter": "demonhunter",
}

CLASS_STYLE = {
    "deathknight": {"color": "#c41e3a", "icon": "classicon_deathknight", "fallback": "DK"},
    "demonhunter": {"color": "#a330c9", "icon": "classicon_demonhunter", "fallback": "DH"},
    "druid": {"color": "#ff7c0a", "icon": "classicon_druid", "fallback": "DR"},
    "evoker": {"color": "#33937f", "icon": "classicon_evoker", "fallback": "EV"},
    "hunter": {"color": "#aad372", "icon": "classicon_hunter", "fallback": "HU"},
    "mage": {"color": "#3fc7eb", "icon": "classicon_mage", "fallback": "MA"},
    "monk": {"color": "#00ff98", "icon": "classicon_monk", "fallback": "MO"},
    "paladin": {"color": "#f48cba", "icon": "classicon_paladin", "fallback": "PA"},
    "priest": {"color": "#f0ebe0", "icon": "classicon_priest", "fallback": "PR"},
    "rogue": {"color": "#fff468", "icon": "classicon_rogue", "fallback": "RO"},
    "shaman": {"color": "#0070dd", "icon": "classicon_shaman", "fallback": "SH"},
    "warlock": {"color": "#8788ee", "icon": "classicon_warlock", "fallback": "WL"},
    "warrior": {"color": "#c69b6d", "icon": "classicon_warrior", "fallback": "WA"},
}

SPEC_ROLE = {
    "blood": "tank",
    "vengeance": "tank",
    "guardian": "tank",
    "brewmaster": "tank",
    "protection": "tank",
    "restoration": "healer",
    "preservation": "healer",
    "mistweaver": "healer",
    "holy": "healer",
    "discipline": "healer",
}


class RaiderIOError(RuntimeError):
    pass


def utc_now():
    return datetime.now(timezone.utc)


def utc_now_iso():
    return utc_now().isoformat(timespec="seconds")


def iso_after(hours):
    return (utc_now() + timedelta(hours=max(1, int(hours or 1)))).isoformat(timespec="seconds")


def parse_iso(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def int_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def slugify(value, fallback="item"):
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
    return text or fallback


def safe_int(value, default=0):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def safe_float(value, default=0.0):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return default


def safe_date(value):
    text = str(value or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    return utc_now_iso()[:10]


def normalize_class_key(value):
    key = slugify(value, "")
    return CLASS_ALIASES.get(key, key)


def normalize_spec_key(value):
    return slugify(value, "")


def role_for_spec(spec_key):
    if spec_key in SPEC_ROLE:
        return SPEC_ROLE[spec_key]
    return "dps"


def raiderio_region():
    return os.environ.get("WOW_RAIDERIO_REGION", DEFAULT_REGION).strip() or DEFAULT_REGION


def raiderio_locale():
    return os.environ.get("WOW_RAIDERIO_LOCALE", DEFAULT_LOCALE).strip() or DEFAULT_LOCALE


def raiderio_season_slug():
    return os.environ.get("WOW_RAIDERIO_SEASON", DEFAULT_SEASON_SLUG).strip() or DEFAULT_SEASON_SLUG


def raiderio_api_key():
    return os.environ.get("WOW_RAIDERIO_API_KEY", "").strip()


def raiderio_user_agent():
    return os.environ.get("WOW_RAIDERIO_USER_AGENT", "wow-mini-program/raiderio-sync").strip() or "wow-mini-program/raiderio-sync"


def redact_secret(text):
    secret = raiderio_api_key()
    value = str(text or "")
    if secret:
        value = value.replace(secret, "[redacted]")
    value = re.sub(r"(access_key=)[^&\s]+", r"\1[redacted]", value)
    return value


def ensure_raiderio_tables(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS raiderio_cache (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            stale_at TEXT NOT NULL
        )
        """
    )


def read_cache(conn):
    ensure_raiderio_tables(conn)
    row = conn.execute(
        "SELECT value_json, updated_at, expires_at, stale_at FROM raiderio_cache WHERE key = ?",
        (RAIDERIO_CACHE_KEY,),
    ).fetchone()
    if not row:
        return {}
    try:
        payload = json.loads(row[0] or "{}")
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    payload.setdefault("updatedAt", row[1])
    payload.setdefault("expiresAt", row[2])
    payload.setdefault("staleAt", row[3])
    return payload


def write_cache(conn, payload):
    ensure_raiderio_tables(conn)
    expires_at = payload.get("expiresAt") or iso_after(int_env("WOW_RAIDERIO_TTL_HOURS", 6))
    stale_at = payload.get("staleAt") or iso_after(int_env("WOW_RAIDERIO_STALE_HOURS", 48))
    conn.execute(
        """
        INSERT INTO raiderio_cache (key, value_json, updated_at, expires_at, stale_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value_json=excluded.value_json,
            updated_at=excluded.updated_at,
            expires_at=excluded.expires_at,
            stale_at=excluded.stale_at
        """,
        (
            RAIDERIO_CACHE_KEY,
            json.dumps(payload, ensure_ascii=False),
            payload.get("checkedAt") or utc_now_iso(),
            expires_at,
            stale_at,
        ),
    )


def api_get(path, params=None, api_key=None):
    key = api_key if api_key is not None else raiderio_api_key()
    if not key:
        raise RaiderIOError("WOW_RAIDERIO_API_KEY is not configured")
    query = dict(params or {})
    query["access_key"] = key
    url = f"{RAIDERIO_BASE_URL}{path}?{urlencode(query, doseq=True)}"
    attempts = max(1, int_env("WOW_RAIDERIO_RETRIES", 2))
    last_error = None
    for _attempt in range(attempts):
        request = Request(url, headers={"User-Agent": raiderio_user_agent(), "Accept": "application/json"})
        try:
            with urlopen(request, timeout=int_env("WOW_RAIDERIO_TIMEOUT_SECONDS", 15)) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            body = ""
            try:
                body = error.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                body = ""
            last_error = RaiderIOError(redact_secret(f"Raider.IO HTTP {error.code}: {body}"))
            if 400 <= error.code < 500:
                raise last_error from None
        except URLError as error:
            last_error = RaiderIOError(redact_secret(f"Raider.IO network error: {error}"))
        except json.JSONDecodeError as error:
            raise RaiderIOError(redact_secret(f"Raider.IO invalid JSON: {error}")) from None
    raise last_error or RaiderIOError("Raider.IO request failed")


def dict_name_slug(value):
    if isinstance(value, dict):
        return value.get("name") or value.get("slug") or "", value.get("slug") or value.get("name") or ""
    return str(value or ""), str(value or "")


def character_key(character):
    return "|".join([
        str(character.get("region") or raiderio_region()).lower(),
        str(character.get("realmSlug") or "").lower(),
        str(character.get("name") or "").lower(),
    ])


def expected_spec_pairs():
    try:
        from .websim_payload import WOW_CLASSES
    except ImportError:
        try:
            from websim_payload import WOW_CLASSES
        except ImportError:
            WOW_CLASSES = []
    pairs = []
    for klass in WOW_CLASSES:
        class_key = normalize_class_key(klass.get("key"))
        for spec in klass.get("specs") or []:
            spec_key = normalize_spec_key(spec.get("key") if isinstance(spec, dict) else spec)
            if class_key and spec_key:
                pairs.append(f"{class_key}:{spec_key}")
    return pairs


def spec_pair_key(character):
    class_key = normalize_class_key(character.get("classKey") or character.get("classSlug") or character.get("className"))
    spec_key = normalize_spec_key(character.get("specKey") or character.get("specSlug") or character.get("specName"))
    return f"{class_key}:{spec_key}" if class_key and spec_key else ""


def profile_total_limit():
    per_spec_limit = max(1, int_env("WOW_RAIDERIO_PROFILE_LIMIT_PER_SPEC", 5))
    default_total = per_spec_limit * max(1, len(expected_spec_pairs()) or 40)
    return max(1, int_env("WOW_RAIDERIO_PROFILE_LIMIT", default_total))


def select_profile_candidates_for_runs(runs):
    total_limit = profile_total_limit()
    per_spec_limit = max(1, int_env("WOW_RAIDERIO_PROFILE_LIMIT_PER_SPEC", 5))
    unique = []
    seen_characters = set()
    per_spec_counts = {}
    for run in runs:
        for character in run.get("roster") or []:
            key = character_key(character)
            if key in seen_characters:
                continue
            spec_key = spec_pair_key(character)
            if spec_key and per_spec_counts.get(spec_key, 0) >= per_spec_limit:
                continue
            seen_characters.add(key)
            unique.append(character)
            if spec_key:
                per_spec_counts[spec_key] = per_spec_counts.get(spec_key, 0) + 1
            if len(unique) >= total_limit:
                return unique
    return unique


def spec_coverage_from_runs(runs):
    expected = set(expected_spec_pairs())
    covered = set()
    samples = {}
    for run in runs or []:
        for character in run.get("roster") or []:
            spec_key = spec_pair_key(character)
            if not spec_key:
                continue
            covered.add(spec_key)
            samples[spec_key] = samples.get(spec_key, 0) + 1
    total = len(expected) or len(covered)
    missing = sorted(expected - covered) if expected else []
    return {
        "totalClassCount": 13 if expected else 0,
        "totalSpecCount": total,
        "coveredSpecCount": len(covered & expected) if expected else len(covered),
        "missingSpecs": missing,
        "sampleCounts": samples,
        "profileLimitPerSpec": max(1, int_env("WOW_RAIDERIO_PROFILE_LIMIT_PER_SPEC", 5)),
        "profileRequestLimit": profile_total_limit(),
    }


def simplify_character(raw):
    data = raw.get("character") if isinstance(raw.get("character"), dict) else raw
    realm = data.get("realm") if isinstance(data.get("realm"), dict) else {}
    class_name, class_slug = dict_name_slug(data.get("class") or data.get("class_name"))
    spec_name, spec_slug = dict_name_slug(
        data.get("spec")
        or data.get("spec_name")
        or data.get("active_spec_name")
        or data.get("activeSpecName")
    )
    class_key = normalize_class_key(class_slug or class_name)
    spec_key = normalize_spec_key(spec_slug or spec_name)
    region = data.get("region")
    if isinstance(region, dict):
        region = region.get("slug") or region.get("name")
    return {
        "name": str(data.get("name") or "").strip(),
        "realm": realm.get("name") or data.get("realm_name") or "",
        "realmSlug": realm.get("slug") or data.get("realm_slug") or "",
        "realmAltName": realm.get("altName") or "",
        "region": str(region or raiderio_region()).lower(),
        "className": class_name or class_key,
        "classSlug": class_slug or class_key,
        "classKey": class_key,
        "specName": spec_name or spec_key,
        "specSlug": spec_slug or spec_key,
        "specKey": spec_key,
        "role": role_for_spec(spec_key),
        "profileUrl": data.get("profile_url") or data.get("profileUrl") or "",
    }


def simplify_run(ranking, leaderboard_url=""):
    run = ranking.get("run") if isinstance(ranking.get("run"), dict) else {}
    dungeon_name, dungeon_slug = dict_name_slug(run.get("dungeon"))
    roster = [simplify_character(item) for item in run.get("roster") or []]
    roster = [item for item in roster if item.get("name") and item.get("realmSlug")]
    return {
        "rank": safe_int(ranking.get("rank")),
        "score": safe_float(ranking.get("score")),
        "dungeonName": dungeon_name,
        "dungeonSlug": dungeon_slug or slugify(dungeon_name, ""),
        "mythicLevel": safe_int(run.get("mythic_level") or run.get("mythicLevel")),
        "clearTimeMs": safe_int(run.get("clear_time_ms") or run.get("clearTimeMs")),
        "completedAt": run.get("completed_at") or run.get("completedAt") or "",
        "weeklyModifiers": run.get("weekly_modifiers") or [],
        "roster": roster,
        "sourceUrl": leaderboard_url or ranking.get("leaderboard_url") or "",
    }


def extract_talent_loadout(profile):
    loadout = profile.get("talentLoadout") or profile.get("talent_loadout") or {}
    if not isinstance(loadout, dict):
        return {}
    raw_import = str(
        loadout.get("loadout_text")
        or loadout.get("loadoutText")
        or loadout.get("import_code")
        or loadout.get("importCode")
        or ""
    ).strip()
    return {
        "rawImportCode": raw_import,
        "loadoutSpecId": loadout.get("loadout_spec_id") or loadout.get("loadoutSpecId") or "",
        "loadout": loadout.get("loadout") or [],
    }


def normalize_gear_slot(slot):
    text = slugify(slot, "")
    aliases = {
        "mainhand": "main_hand",
        "offhand": "off_hand",
        "finger1": "finger_1",
        "finger2": "finger_2",
        "trinket1": "trinket_1",
        "trinket2": "trinket_2",
    }
    return aliases.get(text, text)


def extract_gear(profile):
    gear = profile.get("gear") or {}
    items = gear.get("items") if isinstance(gear, dict) else {}
    if not isinstance(items, dict):
        return []
    result = []
    for slot, item in items.items():
        if not isinstance(item, dict):
            continue
        result.append({
            "slot": normalize_gear_slot(slot),
            "name": item.get("name") or "",
            "itemId": safe_int(item.get("item_id") or item.get("itemId")),
            "itemLevel": safe_int(item.get("item_level") or item.get("itemLevel")),
            "quality": item.get("item_quality") or item.get("quality") or "",
            "icon": item.get("icon") or item.get("icon_url") or item.get("iconUrl") or "",
            "bonuses": item.get("bonuses") or [],
            "gems": item.get("gems") or [],
            "enchants": item.get("enchants") or item.get("enchant") or [],
            "sourceName": RAIDERIO_SOURCE_NAME,
            "sourceStatus": "source_reference",
            "simcReady": False,
        })
    return sorted(result, key=lambda item: item.get("slot") or "")


def profile_summary(profile):
    character = simplify_character(profile)
    character["profileUrl"] = profile.get("profile_url") or character.get("profileUrl") or ""
    character["talentLoadout"] = extract_talent_loadout(profile)
    character["gear"] = extract_gear(profile)
    character["itemLevel"] = safe_float((profile.get("gear") or {}).get("item_level_equipped"))
    return character


def fetch_profiles_for_runs(runs):
    unique = select_profile_candidates_for_runs(runs)

    profiles = {}
    errors = []
    fields = "gear,talents,mythic_plus_recent_runs,mythic_plus_best_runs,mythic_plus_scores_by_season"
    for character in unique:
        try:
            raw = api_get("/characters/profile", {
                "region": character.get("region") or raiderio_region(),
                "realm": character.get("realmSlug"),
                "name": character.get("name"),
                "fields": fields,
            })
            summary = profile_summary(raw)
            for key in ("region", "realm", "realmSlug", "className", "classKey", "specName", "specKey", "role"):
                if not summary.get(key) and character.get(key):
                    summary[key] = character.get(key)
            profiles[character_key(summary)] = summary
        except RaiderIOError as error:
            errors.append(str(error))
    return profiles, errors


def aggregate_runs(runs, profiles):
    aggregates = {}
    for run in runs:
        for character in run.get("roster") or []:
            class_key = character.get("classKey") or ""
            spec_key = character.get("specKey") or ""
            if not class_key or not spec_key:
                continue
            key = f"{class_key}:{spec_key}"
            aggregate = aggregates.setdefault(key, {
                "classKey": class_key,
                "specKey": spec_key,
                "specId": f"{class_key}-{spec_key}",
                "className": character.get("className") or class_key,
                "specName": character.get("specName") or spec_key,
                "fullName": f"{character.get('specName') or spec_key} {character.get('className') or class_key}",
                "role": character.get("role") or role_for_spec(spec_key),
                "sampleCount": 0,
                "characterCount": 0,
                "maxKeyLevel": 0,
                "bestScore": 0,
                "topRuns": [],
                "talentLoadouts": [],
                "observedGear": [],
                "observedGearProfiles": [],
            })
            aggregate["sampleCount"] += 1
            aggregate["maxKeyLevel"] = max(aggregate["maxKeyLevel"], safe_int(run.get("mythicLevel")))
            aggregate["bestScore"] = max(aggregate["bestScore"], safe_float(run.get("score")))
            aggregate["topRuns"].append({
                "rank": run.get("rank"),
                "dungeonName": run.get("dungeonName"),
                "mythicLevel": run.get("mythicLevel"),
                "score": run.get("score"),
                "completedAt": run.get("completedAt"),
                "sourceUrl": run.get("sourceUrl"),
            })
            profile = profiles.get(character_key(character))
            if profile:
                talent = profile.get("talentLoadout") or {}
                if talent.get("rawImportCode"):
                    aggregate["talentLoadouts"].append({
                        **talent,
                        "characterName": profile.get("name"),
                        "realmSlug": profile.get("realmSlug"),
                        "profileUrl": profile.get("profileUrl"),
                        "maxKeyLevel": run.get("mythicLevel"),
                    })
                if profile.get("gear"):
                    observed_profile = {
                        "characterName": profile.get("name"),
                        "realmSlug": profile.get("realmSlug"),
                        "profileUrl": profile.get("profileUrl"),
                        "maxKeyLevel": run.get("mythicLevel"),
                        "gear": profile.get("gear"),
                    }
                    aggregate["observedGearProfiles"].append(observed_profile)
                    if not aggregate["observedGear"]:
                        aggregate["observedGear"] = profile.get("gear")

    for aggregate in aggregates.values():
        aggregate["topRuns"] = sorted(
            aggregate["topRuns"],
            key=lambda item: (safe_int(item.get("mythicLevel")), safe_float(item.get("score"))),
            reverse=True,
        )[:5]
        unique_loadouts = []
        seen_loadouts = set()
        for loadout in aggregate["talentLoadouts"]:
            code = loadout.get("rawImportCode") or ""
            character = f"{loadout.get('characterName') or ''}:{loadout.get('realmSlug') or ''}".lower()
            dedupe_key = f"{character}:{code}"
            if not code or dedupe_key in seen_loadouts:
                continue
            seen_loadouts.add(dedupe_key)
            unique_loadouts.append(loadout)
        aggregate["talentLoadouts"] = unique_loadouts[:5]
        unique_gear_profiles = []
        seen_gear_profiles = set()
        for gear_profile in aggregate.get("observedGearProfiles") or []:
            character = f"{gear_profile.get('characterName') or ''}:{gear_profile.get('realmSlug') or ''}".lower()
            if not character or character in seen_gear_profiles:
                continue
            seen_gear_profiles.add(character)
            unique_gear_profiles.append(gear_profile)
        aggregate["observedGearProfiles"] = unique_gear_profiles[:5]
        aggregate["characterCount"] = max(aggregate["characterCount"], len(seen_loadouts) or aggregate["sampleCount"])
    return sorted(
        aggregates.values(),
        key=lambda item: (item.get("role") or "", safe_int(item.get("maxKeyLevel")), safe_float(item.get("bestScore")), safe_int(item.get("sampleCount"))),
        reverse=True,
    )


def build_community_templates(aggregates, checked_at):
    templates = []
    for aggregate in aggregates:
        for index, loadout in enumerate(aggregate.get("talentLoadouts") or []):
            raw_code = loadout.get("rawImportCode") or ""
            if not raw_code:
                continue
            player_id = str(loadout.get("characterName") or f"player-{index + 1}").strip()
            player_slug = slugify(player_id, f"player-{index + 1}")
            code_hash = hashlib.sha1(raw_code.encode("utf-8")).hexdigest()[:8]
            spec_label = aggregate.get("fullName") or f"{aggregate.get('specKey')} {aggregate.get('classKey')}"
            templates.append({
                "id": f"raiderio-{aggregate.get('classKey')}-{aggregate.get('specKey')}-{player_slug}-{code_hash}",
                "classKey": aggregate.get("classKey"),
                "specKey": aggregate.get("specKey"),
                "heroKey": "",
                "scenarioKey": "mythic_plus",
                "name": f"Raider.IO CN +{loadout.get('maxKeyLevel') or aggregate.get('maxKeyLevel')} {spec_label}",
                "flowLabel": "Raider.IO CN",
                "sourceName": RAIDERIO_SOURCE_NAME,
                "sourceUrl": loadout.get("profileUrl") or "https://raider.io/mythic-plus-rankings",
                "rawImportCode": raw_code,
                "playerId": player_id,
                "sampleCount": aggregate.get("sampleCount") or 0,
                "maxKeyLevel": loadout.get("maxKeyLevel") or aggregate.get("maxKeyLevel") or 0,
                "analysisWindow": f"{raiderio_region()} {raiderio_season_slug()} cached at {checked_at}",
                "sourceStatus": "synced",
                "status": "verified",
                "payload": {
                    "raiderio": {
                        "characterName": loadout.get("characterName") or "",
                        "realmSlug": loadout.get("realmSlug") or "",
                        "profileUrl": loadout.get("profileUrl") or "",
                        "loadoutSpecId": loadout.get("loadoutSpecId") or "",
                        "loadout": loadout.get("loadout") or [],
                    }
                },
                "updatedAt": checked_at,
            })
    return templates[:80]


def optional_api_get(path, params, errors):
    try:
        return api_get(path, params)
    except RaiderIOError as error:
        errors.append(str(error))
        return {}


def sync_raiderio_cache(conn, force=False):
    ensure_raiderio_tables(conn)
    if not raiderio_api_key():
        payload = missing_credentials_payload()
        write_cache(conn, payload)
        return payload

    checked_at = utc_now_iso()
    region = raiderio_region()
    season_slug = raiderio_season_slug()
    errors = []
    rankings = []
    leaderboard_url = ""
    pages = max(1, int_env("WOW_RAIDERIO_RUN_PAGES", 8))
    for page in range(pages):
        response = api_get("/mythic-plus/runs", {
            "season": season_slug,
            "region": region,
            "dungeon": "all",
            "page": page,
        })
        leaderboard_url = response.get("leaderboard_url") or leaderboard_url
        page_rankings = response.get("rankings") or []
        if not isinstance(page_rankings, list):
            page_rankings = []
        rankings.extend(page_rankings)
        runs_preview = [simplify_run(item, leaderboard_url) for item in rankings]
        coverage_preview = spec_coverage_from_runs([run for run in runs_preview if run.get("roster")])
        if coverage_preview.get("totalSpecCount") and coverage_preview.get("coveredSpecCount") >= coverage_preview.get("totalSpecCount"):
            break
        if len(page_rankings) < 20:
            break

    runs = [simplify_run(item, leaderboard_url) for item in rankings]
    runs = [run for run in runs if run.get("roster")]
    spec_coverage = spec_coverage_from_runs(runs)
    profiles, profile_errors = fetch_profiles_for_runs(runs)
    errors.extend(profile_errors[:8])
    static_data = optional_api_get(
        "/mythic-plus/static-data",
        {"expansion_id": os.environ.get("WOW_RAIDERIO_EXPANSION_ID", DEFAULT_EXPANSION_ID)},
        errors,
    )
    affixes = optional_api_get("/mythic-plus/affixes", {"region": region, "locale": raiderio_locale()}, errors)
    cutoffs = optional_api_get("/mythic-plus/season-cutoffs", {"season": season_slug, "region": region}, errors)
    aggregates = aggregate_runs(runs, profiles)
    source_status = "synced" if runs else "blocked"
    if runs and errors:
        source_status = "partial"
    payload = {
        "sourceName": RAIDERIO_SOURCE_NAME,
        "sourceStatus": source_status,
        "status": source_status,
        "region": region,
        "locale": raiderio_locale(),
        "seasonSlug": season_slug,
        "leaderboardUrl": leaderboard_url or "https://raider.io/mythic-plus-rankings",
        "checkedAt": checked_at,
        "expiresAt": iso_after(int_env("WOW_RAIDERIO_TTL_HOURS", 6)),
        "staleAt": iso_after(int_env("WOW_RAIDERIO_STALE_HOURS", 48)),
        "staticExpiresAt": iso_after(int_env("WOW_RAIDERIO_STATIC_TTL_HOURS", 24)),
        "errors": errors[:12],
        "runCount": len(runs),
        "profileCount": len(profiles),
        "profileLimitPerSpec": max(1, int_env("WOW_RAIDERIO_PROFILE_LIMIT_PER_SPEC", 5)),
        "specCoverage": spec_coverage,
        "runs": runs[:200],
        "profiles": list(profiles.values())[:profile_total_limit()],
        "specAggregates": aggregates,
        "communityTemplates": build_community_templates(aggregates, checked_at),
        "staticData": static_data,
        "affixes": affixes,
        "cutoffs": cutoffs,
    }
    write_cache(conn, payload)
    return payload


def missing_credentials_payload():
    now = utc_now_iso()
    return {
        "sourceName": RAIDERIO_SOURCE_NAME,
        "sourceStatus": "missing_credentials",
        "status": "missing_credentials",
        "region": raiderio_region(),
        "locale": raiderio_locale(),
        "seasonSlug": raiderio_season_slug(),
        "leaderboardUrl": "https://raider.io/mythic-plus-rankings",
        "checkedAt": now,
        "expiresAt": iso_after(1),
        "staleAt": iso_after(1),
        "errors": ["WOW_RAIDERIO_API_KEY is not configured"],
        "runCount": 0,
        "profileCount": 0,
        "profileLimitPerSpec": max(1, int_env("WOW_RAIDERIO_PROFILE_LIMIT_PER_SPEC", 5)),
        "specCoverage": spec_coverage_from_runs([]),
        "runs": [],
        "profiles": [],
        "specAggregates": [],
        "communityTemplates": [],
        "staticData": {},
        "affixes": {},
        "cutoffs": {},
    }


def blocked_payload(errors):
    now = utc_now_iso()
    return {
        **missing_credentials_payload(),
        "sourceStatus": "blocked",
        "status": "blocked",
        "checkedAt": now,
        "errors": [redact_secret(error) for error in (errors or ["Raider.IO sync failed"])],
    }


def payload_is_fresh(payload):
    expires_at = parse_iso(payload.get("expiresAt"))
    return bool(expires_at and expires_at > utc_now())


def payload_can_stale(payload):
    stale_at = parse_iso(payload.get("staleAt"))
    return bool(stale_at and stale_at > utc_now())


def stale_copy(payload, errors=None):
    copy = dict(payload or {})
    copy["sourceStatus"] = "stale"
    copy["status"] = "stale"
    copy["errors"] = [*(copy.get("errors") or []), *[redact_secret(error) for error in (errors or [])]]
    return copy


def get_raiderio_payload(conn, allow_sync=True):
    ensure_raiderio_tables(conn)
    cached = read_cache(conn)
    if cached and payload_is_fresh(cached):
        return cached
    if allow_sync and raiderio_api_key():
        try:
            return sync_raiderio_cache(conn)
        except RaiderIOError as error:
            if cached and payload_can_stale(cached):
                return stale_copy(cached, [str(error)])
            return blocked_payload([str(error)])
    if cached and payload_can_stale(cached):
        return stale_copy(cached, [] if raiderio_api_key() else ["WOW_RAIDERIO_API_KEY is not configured"])
    if not raiderio_api_key():
        return missing_credentials_payload()
    return blocked_payload(["Raider.IO cache is empty or expired"])


def source_status_label(status):
    return {
        "synced": "Raider.IO synced",
        "partial": "Raider.IO partial",
        "stale": "Raider.IO stale",
        "missing_credentials": "Missing Raider.IO credentials",
        "blocked": "Raider.IO blocked",
        "source_reference": SPEC_LADDER_REFERENCE_LABEL,
    }.get(status or "", "Raider.IO partial")


def spec_ladder_data_trust():
    return {
        "status": SPEC_LADDER_REFERENCE_STATUS,
        "statusLabel": SPEC_LADDER_REFERENCE_LABEL,
        "blockers": list(SPEC_LADDER_REFERENCE_BLOCKERS),
        "evidenceRefs": list(SPEC_LADDER_EVIDENCE_REFS),
    }


def raiderio_spec_ladder_check_status(status):
    if status in {"synced", "verified", "partial"}:
        return "partial"
    if status in {"stale", "missing_credentials", "blocked"}:
        return status
    return "blocked"


def aggregate_by_spec(payload):
    result = {}
    for item in payload.get("specAggregates") or []:
        result[f"{item.get('classKey')}:{item.get('specKey')}"] = item
    return result


def public_raiderio_summary(payload, aggregate=None):
    status = payload.get("sourceStatus") or "blocked"
    summary = {
        "sourceName": RAIDERIO_SOURCE_NAME,
        "sourceStatus": status,
        "sourceStatusLabel": source_status_label(status),
        "seasonSlug": payload.get("seasonSlug") or "",
        "region": payload.get("region") or "",
        "checkedAt": payload.get("checkedAt") or "",
        "expiresAt": payload.get("expiresAt") or "",
        "analysisWindow": f"{payload.get('region') or DEFAULT_REGION} {payload.get('seasonSlug') or DEFAULT_SEASON_SLUG}",
        "sampleCount": 0,
        "maxKeyLevel": 0,
        "bestScore": 0,
        "topRuns": [],
        "observedGear": [],
        "talentLoadouts": [],
        "sourceUrl": payload.get("leaderboardUrl") or "https://raider.io/mythic-plus-rankings",
    }
    if aggregate:
        summary.update({
            "sampleCount": aggregate.get("sampleCount") or 0,
            "maxKeyLevel": aggregate.get("maxKeyLevel") or 0,
            "bestScore": aggregate.get("bestScore") or 0,
            "topRuns": aggregate.get("topRuns") or [],
            "observedGear": aggregate.get("observedGear") or [],
            "talentLoadouts": aggregate.get("talentLoadouts") or [],
        })
    return summary


def aggregate_for_specialization(payload, specialization):
    class_key = specialization.get("websimClassKey") or specialization.get("classKey") or ""
    spec_key = specialization.get("websimSpecKey") or specialization.get("specKey") or ""
    return aggregate_by_spec(payload).get(f"{class_key}:{spec_key}")


def enrich_build_specialization(specialization, payload):
    aggregate = aggregate_for_specialization(payload, specialization)
    summary = public_raiderio_summary(payload, aggregate)
    enriched = dict(specialization)
    enriched["raiderio"] = summary
    enriched["raiderioSourceStatus"] = summary["sourceStatus"]
    enriched["sampleCount"] = summary["sampleCount"] or enriched.get("sampleCount", 0)
    enriched["maxKeyLevel"] = summary["maxKeyLevel"] or enriched.get("maxKeyLevel", 0)
    enriched["bestScore"] = summary["bestScore"] or enriched.get("bestScore", 0)
    return enriched


def enrich_builds_home_payload(payload, raiderio):
    if not isinstance(payload, dict):
        return payload
    result = dict(payload)
    result["raiderio"] = public_raiderio_summary(raiderio)
    for key in ("featuredSpecializations", "specializations"):
        if isinstance(result.get(key), list):
            result[key] = [enrich_build_specialization(item, raiderio) for item in result[key]]
    return result


def enrich_builds_intel_payload(payload, raiderio):
    if not isinstance(payload, dict):
        return payload
    result = dict(payload)
    result["raiderio"] = public_raiderio_summary(raiderio)
    if isinstance(result.get("items"), list):
        result["items"] = [enrich_build_specialization(item, raiderio) for item in result["items"]]
    return result


def enrich_builds_detail_payload(payload, raiderio):
    if not isinstance(payload, dict):
        return payload
    result = enrich_build_specialization(payload, raiderio)
    details = {}
    for key, section in (result.get("details") or {}).items():
        next_section = dict(section)
        if key in {"talents", "gear"}:
            next_section["raiderio"] = result["raiderio"]
            next_section["sourceStatus"] = result["raiderio"]["sourceStatus"] if result["raiderio"]["sampleCount"] else next_section.get("sourceStatus", "source_reference")
            if key == "talents":
                next_section["talentLoadouts"] = result["raiderio"].get("talentLoadouts") or []
            if key == "gear":
                next_section["observedGear"] = result["raiderio"].get("observedGear") or []
        elif "sourceStatus" not in next_section:
            next_section["sourceStatus"] = "source_reference"
        details[key] = next_section
    result["details"] = details
    return result


def run_roster_label(run):
    names = []
    for character in run.get("roster") or []:
        spec = character.get("specName") or character.get("specKey") or ""
        cls = character.get("className") or character.get("classKey") or ""
        if spec or cls:
            names.append(f"{spec} {cls}".strip())
    return " / ".join(names[:5])


def build_team_ladder_items(raiderio):
    items = []
    for run in (raiderio.get("runs") or [])[:5]:
        level = safe_int(run.get("mythicLevel"))
        title = f"+{level} {run.get('dungeonName') or 'Mythic+'}"
        items.append({
            "title": title,
            "value": f"Rank #{run.get('rank') or '-'}",
            "desc": f"CN run completed {safe_date(run.get('completedAt'))}; roster {run_roster_label(run)}.",
            "sourceName": RAIDERIO_SOURCE_NAME,
            "sourceUrl": run.get("sourceUrl") or raiderio.get("leaderboardUrl") or "https://raider.io/mythic-plus-rankings",
            "publishedAt": safe_date(raiderio.get("checkedAt")),
            "analysisWindow": f"{raiderio.get('region') or DEFAULT_REGION} {raiderio.get('seasonSlug') or DEFAULT_SEASON_SLUG} cached runs",
            "sourceStatus": raiderio.get("sourceStatus") or "blocked",
        })
    return items


def static_dungeons(raiderio):
    data = raiderio.get("staticData") or {}
    dungeons = data.get("dungeons") or data.get("seasons") or []
    if isinstance(dungeons, dict):
        dungeons = list(dungeons.values())
    result = []
    for item in dungeons if isinstance(dungeons, list) else []:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("dungeon") or item.get("slug")
        if not name:
            continue
        result.append({
            "name": name,
            "slug": item.get("slug") or slugify(name, ""),
            "timerSeconds": safe_int(item.get("timer_seconds") or item.get("timerSeconds")),
        })
    return result[:12]


def build_season_dungeon_items(raiderio, fallback_items=None):
    dungeons = static_dungeons(raiderio)
    affixes = raiderio.get("affixes") or {}
    affix_details = affixes.get("affix_details") or affixes.get("affixes") or []
    cutoffs = raiderio.get("cutoffs") or {}
    items = []
    if dungeons:
        items.append({
            "title": "Raider.IO dungeon pool",
            "value": f"{len(dungeons)} dungeons",
            "desc": ", ".join(item.get("name") or "" for item in dungeons[:8]),
            "sourceName": RAIDERIO_SOURCE_NAME,
            "sourceUrl": raiderio.get("leaderboardUrl") or "https://raider.io/mythic-plus-rankings",
            "publishedAt": safe_date(raiderio.get("checkedAt")),
            "analysisWindow": f"{raiderio.get('seasonSlug')} static-data",
            "sourceStatus": raiderio.get("sourceStatus") or "blocked",
        })
    if isinstance(affix_details, list) and affix_details:
        names = [item.get("name") for item in affix_details if isinstance(item, dict) and item.get("name")]
        items.append({
            "title": "Current affixes",
            "value": f"{len(names)} affixes",
            "desc": ", ".join(names[:6]),
            "sourceName": RAIDERIO_SOURCE_NAME,
            "sourceUrl": "https://raider.io/mythic-plus-rankings",
            "publishedAt": safe_date(raiderio.get("checkedAt")),
            "analysisWindow": f"{raiderio.get('region')} affixes",
            "sourceStatus": raiderio.get("sourceStatus") or "blocked",
        })
    all_cutoff = (((cutoffs.get("cutoffs") or {}).get("all") or {}).get("p999") or {})
    if all_cutoff:
        items.append({
            "title": "CN title cutoff",
            "value": str(all_cutoff.get("allMinValue") or all_cutoff.get("minValue") or ""),
            "desc": f"Updated at {cutoffs.get('updatedAt') or raiderio.get('checkedAt')}.",
            "sourceName": RAIDERIO_SOURCE_NAME,
            "sourceUrl": "https://raider.io/mythic-plus/cutoffs",
            "publishedAt": safe_date(raiderio.get("checkedAt")),
            "analysisWindow": f"{raiderio.get('seasonSlug')} season-cutoffs",
            "sourceStatus": raiderio.get("sourceStatus") or "blocked",
        })
    return items or list(fallback_items or [])


def tier_for_index(index):
    if index < 3:
        return "S"
    if index < 8:
        return "A"
    if index < 16:
        return "B"
    return "C"


def game_asset_for_aggregate(aggregate, role):
    style = CLASS_STYLE.get(aggregate.get("classKey") or "", {"color": "#8e8e8e", "icon": "inv_misc_questionmark", "fallback": "?"})
    spec_id = aggregate.get("specId") or f"{aggregate.get('classKey')}-{aggregate.get('specKey')}"
    icon = style.get("icon")
    return {
        "entityType": "playable_spec",
        "entityId": spec_id,
        "contextKey": f"pve-spec-ladder:{role}",
        "iconName": icon,
        "iconUrl": f"https://render.worldofwarcraft.com/us/icons/56/{icon}.jpg" if icon else "",
        "source": "static_icon_name",
        "status": "fallback",
        "resolutionTier": "icon_56",
        "semanticTags": ["game", "pve", "mythic_plus", "spec_ladder", role, aggregate.get("classKey") or "", aggregate.get("specKey") or ""],
        "usage": ["pve_spec_ladder", "pve_detail", "raiderio_spec_board"],
        "fallbackText": style.get("fallback") or "?",
    }


def raiderio_spec_item(aggregate, rank, tier, max_score, status):
    role = aggregate.get("role") or "dps"
    style = CLASS_STYLE.get(aggregate.get("classKey") or "", {"color": "#8e8e8e", "fallback": "?"})
    game_asset = game_asset_for_aggregate(aggregate, role)
    score = safe_float(aggregate.get("bestScore")) or safe_int(aggregate.get("maxKeyLevel"))
    score_value = round(score, 2) if isinstance(score, float) else score
    return {
        "role": role,
        "tier": tier,
        "rank": rank,
        "specId": aggregate.get("specId"),
        "className": aggregate.get("className"),
        "specName": aggregate.get("specName"),
        "fullName": aggregate.get("fullName"),
        "classSlug": aggregate.get("classKey"),
        "specSlug": aggregate.get("specKey"),
        "classColor": style.get("color"),
        "fallbackText": game_asset.get("fallbackText"),
        "iconUrl": game_asset.get("iconUrl"),
        "gameAsset": game_asset,
        "score": score_value,
        "scoreLabel": "Best M+ Score",
        "scoreText": str(score_value),
        "sampleCount": safe_int(aggregate.get("sampleCount")),
        "sampleText": f"{safe_int(aggregate.get('sampleCount'))} CN samples",
        "sourceName": RAIDERIO_SOURCE_NAME,
        "sourceUrl": "https://raider.io/mythic-plus-rankings",
        "sourceStatus": status,
        "sourceStatusLabel": source_status_label(status),
        "dataTrust": spec_ladder_data_trust() if status == SPEC_LADDER_REFERENCE_STATUS else {},
        "blockers": list(SPEC_LADDER_REFERENCE_BLOCKERS) if status == SPEC_LADDER_REFERENCE_STATUS else [],
        "maxKeyLevel": safe_int(aggregate.get("maxKeyLevel")),
        "topRuns": aggregate.get("topRuns") or [],
    }


def build_raiderio_spec_summary(raiderio, existing_module=None):
    status = raiderio.get("sourceStatus") or "blocked"
    ladder_status = SPEC_LADDER_REFERENCE_STATUS
    ladder_label = SPEC_LADDER_REFERENCE_LABEL
    ladder_blockers = list(SPEC_LADDER_REFERENCE_BLOCKERS)
    ladder_trust = spec_ladder_data_trust()
    aggregates = [item for item in (raiderio.get("specAggregates") or []) if safe_int(item.get("sampleCount")) > 0]
    if not aggregates:
        return None
    grouped = {"dps": [], "tank": [], "healer": []}
    for aggregate in aggregates:
        grouped.setdefault(aggregate.get("role") or "dps", []).append(aggregate)
    max_score_by_role = {
        role: max([safe_float(item.get("bestScore")) for item in items] or [1])
        for role, items in grouped.items()
    }
    roles = []
    summary = {}
    wcl_details = {}
    for role in ("dps", "tank", "healer"):
        items = sorted(
            grouped.get(role) or [],
            key=lambda item: (safe_int(item.get("maxKeyLevel")), safe_float(item.get("bestScore")), safe_int(item.get("sampleCount"))),
            reverse=True,
        )
        existing_summary = ((existing_module or {}).get("archonTierSummary") or {}).get(role) or {}
        existing_role = next((item for item in ((existing_module or {}).get("roles") or []) if item.get("key") == role), {})
        if not items and existing_summary.get("tiers"):
            summary[role] = {
                **existing_summary,
                "sourceStatus": ladder_status,
                "sourceStatusLabel": ladder_label,
                "dataTrust": spec_ladder_data_trust(),
                "blockers": list(SPEC_LADDER_REFERENCE_BLOCKERS),
                "analysisWindow": "Compatibility fallback; Raider.IO cache has no samples for this role.",
            }
            roles.append({
                **existing_role,
                "key": role,
                "title": existing_role.get("title") or ("DPS" if role == "dps" else ("Tank" if role == "tank" else "Healer")),
                "count": existing_role.get("count") or sum(len(tier.get("items") or []) for tier in existing_summary.get("tiers") or []),
                "updatedAt": safe_date(raiderio.get("checkedAt")),
                "active": role == "dps",
            })
            for tier in existing_summary.get("tiers") or []:
                for spec in tier.get("items") or []:
                    if spec.get("specId") and spec.get("specId") not in wcl_details:
                        wcl_details[spec["specId"]] = {
                            **(((existing_module or {}).get("wclDetailsBySpec") or {}).get(spec["specId"]) or {}),
                            "specId": spec["specId"],
                            "role": role,
                            "sourceStatus": ladder_status,
                            "sourceStatusLabel": ladder_label,
                            "dataTrust": spec_ladder_data_trust(),
                            "blockers": list(SPEC_LADDER_REFERENCE_BLOCKERS),
                        }
            continue
        roles.append({
            "key": role,
            "title": "DPS" if role == "dps" else ("Tank" if role == "tank" else "Healer"),
            "desc": f"Raider.IO {role} CN samples",
            "count": len(items),
            "updatedAt": safe_date(raiderio.get("checkedAt")),
            "active": role == "dps",
        })
        tier_map = {}
        max_score = max_score_by_role.get(role) or 1
        for index, aggregate in enumerate(items):
            tier = tier_for_index(index)
            spec = raiderio_spec_item(aggregate, index + 1, tier, max_score, ladder_status)
            tier_map.setdefault(tier, []).append(spec)
            score = safe_float(aggregate.get("bestScore")) or safe_int(aggregate.get("maxKeyLevel"))
            wcl_details[spec["specId"]] = {
                "specId": spec["specId"],
                "role": role,
                "className": spec["className"],
                "specName": spec["specName"],
                "fullName": spec["fullName"],
                "rank": index + 1,
                "score": score,
                "scoreText": str(round(score, 2)),
                "max": max_score,
                "maxText": str(round(max_score, 2)),
                "parses": safe_int(aggregate.get("sampleCount")),
                "parsesText": str(safe_int(aggregate.get("sampleCount"))),
                "sourceName": RAIDERIO_SOURCE_NAME,
                "sourceUrl": "https://raider.io/mythic-plus-rankings",
                "sourceStatus": ladder_status,
                "sourceStatusLabel": ladder_label,
                "dataTrust": spec_ladder_data_trust(),
                "blockers": list(SPEC_LADDER_REFERENCE_BLOCKERS),
                "metricLabel": "Raider.IO run score",
                "distribution": {
                    "p50": max(0, safe_int(aggregate.get("maxKeyLevel")) - 3),
                    "p75": max(0, safe_int(aggregate.get("maxKeyLevel")) - 1),
                    "p95": safe_int(aggregate.get("maxKeyLevel")),
                    "barPercent": max(18, min(100, round((score / max_score) * 100))) if max_score else 18,
                },
            }
        summary[role] = {
            "sourceName": RAIDERIO_SOURCE_NAME,
            "sourceUrl": "https://raider.io/mythic-plus-rankings",
            "sourceStatus": ladder_status,
            "sourceStatusLabel": ladder_label,
            "dataTrust": spec_ladder_data_trust(),
            "blockers": list(SPEC_LADDER_REFERENCE_BLOCKERS),
            "publishedAt": safe_date(raiderio.get("checkedAt")),
            "checkedAt": raiderio.get("checkedAt") or "",
            "analysisWindow": f"{raiderio.get('region')} {raiderio.get('seasonSlug')} cached CN runs",
            "tiers": [{"tier": tier, "items": tier_map[tier]} for tier in ("S", "A", "B", "C") if tier_map.get(tier)],
        }
    raiderio_check_status = raiderio_spec_ladder_check_status(status)
    source_checks = [
        {
            "key": "raiderio",
            "name": RAIDERIO_SOURCE_NAME,
            "domain": "raider.io",
            "status": raiderio_check_status,
            "statusLabel": source_status_label(raiderio_check_status),
            "checkedAt": raiderio.get("checkedAt") or "",
            "analysisWindow": f"{raiderio.get('region')} {raiderio.get('seasonSlug')}",
            "sampleCount": sum(safe_int(item.get("sampleCount")) for item in aggregates),
            "sourceUrl": "https://raider.io/mythic-plus-rankings",
            "blockers": [SPEC_LADDER_REFERENCE_BLOCKERS[1]],
            "evidenceRefs": ["pve.specLadder.raiderioTrend"],
            "note": "Raider.IO cached CN Mythic+ run samples.",
        },
        {
            "key": "archon",
            "name": "Archon",
            "domain": "archon.gg",
            "status": ladder_status,
            "statusLabel": ladder_label,
            "checkedAt": raiderio.get("checkedAt") or "",
            "analysisWindow": "Retained compatibility field; not refreshed by Raider.IO.",
            "sampleCount": 0,
            "sourceUrl": "https://www.archon.gg/wow",
            "blockers": ladder_blockers,
            "evidenceRefs": ["pve.specLadder.archonFixture"],
            "note": "Kept for front-end compatibility until an authorized Archon data source is added.",
        },
        {
            "key": "warcraftlogs",
            "name": "Warcraft Logs",
            "domain": "warcraftlogs.com",
            "status": ladder_status,
            "statusLabel": ladder_label,
            "checkedAt": raiderio.get("checkedAt") or "",
            "analysisWindow": "Retained compatibility field; not refreshed by Raider.IO.",
            "sampleCount": 0,
            "sourceUrl": "https://www.warcraftlogs.com/zone/rankings/latest",
            "blockers": ladder_blockers,
            "evidenceRefs": ["pve.specLadder.wclFixture"],
            "note": "Raider.IO does not replace WCL combat-log statistics.",
        },
    ]
    return {
        "roles": roles,
        "archonTierSummary": summary,
        "wclDetailsBySpec": wcl_details,
        "sourceChecks": source_checks,
        "selectedSpecId": first_spec_id(summary),
        "sourceStatus": ladder_status,
        "sourceStatusLabel": ladder_label,
        "dataTrust": ladder_trust,
        "blockers": ladder_blockers,
        "items": [
            {
                "title": item.get("fullName"),
                "value": f"+{item.get('maxKeyLevel')} / {item.get('scoreText')}",
                "desc": f"{item.get('sampleText')} from Raider.IO CN cached runs.",
                "sourceName": RAIDERIO_SOURCE_NAME,
                "sourceUrl": item.get("sourceUrl"),
                "publishedAt": safe_date(raiderio.get("checkedAt")),
                "analysisWindow": f"{raiderio.get('region')} {raiderio.get('seasonSlug')} cached CN runs",
                "sourceStatus": ladder_status,
                "sourceStatusLabel": ladder_label,
                "dataTrust": spec_ladder_data_trust(),
                "blockers": list(SPEC_LADDER_REFERENCE_BLOCKERS),
            }
            for item in [spec for role in summary.values() for tier in role.get("tiers", []) for spec in tier.get("items", [])][:6]
        ],
    }


def first_spec_id(summary):
    for role in ("dps", "tank", "healer"):
        for tier in (summary.get(role) or {}).get("tiers") or []:
            for item in tier.get("items") or []:
                if item.get("specId"):
                    return item["specId"]
    return ""


def enrich_pve_module_payload(module, raiderio):
    if not isinstance(module, dict):
        return module
    result = dict(module)
    key = result.get("key")
    result["raiderio"] = public_raiderio_summary(raiderio)
    if key == "teamLadder" and raiderio.get("runs"):
        items = build_team_ladder_items(raiderio)
        if items:
            result.update({
                "items": items,
                "itemCount": len(items),
                "sourceName": RAIDERIO_SOURCE_NAME,
                "sourceUrl": raiderio.get("leaderboardUrl") or "https://raider.io/mythic-plus-rankings",
                "publishedAt": safe_date(raiderio.get("checkedAt")),
                "analysisWindow": f"{raiderio.get('region')} {raiderio.get('seasonSlug')} cached CN runs",
                "sourceStatus": raiderio.get("sourceStatus") or "blocked",
            })
    elif key == "seasonDungeons":
        items = build_season_dungeon_items(raiderio, result.get("items") or [])
        result.update({
            "items": items,
            "itemCount": len(items),
            "sourceName": RAIDERIO_SOURCE_NAME if items else result.get("sourceName"),
            "sourceUrl": raiderio.get("leaderboardUrl") or result.get("sourceUrl"),
            "publishedAt": safe_date(raiderio.get("checkedAt")),
            "analysisWindow": f"{raiderio.get('region')} {raiderio.get('seasonSlug')} static/cutoff cache",
            "sourceStatus": raiderio.get("sourceStatus") or "blocked",
        })
    elif key == "specLadder":
        summary = build_raiderio_spec_summary(raiderio, result)
        if summary:
            result.update(summary)
            result["itemCount"] = sum(role.get("count") or 0 for role in summary["roles"])
            result["sourceName"] = RAIDERIO_SOURCE_NAME
            result["sourceUrl"] = raiderio.get("leaderboardUrl") or "https://raider.io/mythic-plus-rankings"
            result["publishedAt"] = safe_date(raiderio.get("checkedAt"))
            result["analysisWindow"] = f"{raiderio.get('region')} {raiderio.get('seasonSlug')} cached CN runs"
            result["sourceStatus"] = SPEC_LADDER_REFERENCE_STATUS
            result["sourceStatusLabel"] = SPEC_LADDER_REFERENCE_LABEL
            result["dataTrust"] = spec_ladder_data_trust()
            result["blockers"] = list(SPEC_LADDER_REFERENCE_BLOCKERS)
    return result


def enrich_pve_home_payload(payload, raiderio):
    if not isinstance(payload, dict):
        return payload
    result = dict(payload)
    result["raiderio"] = public_raiderio_summary(raiderio)
    zones = []
    for zone in result.get("zones") or []:
        next_zone = dict(zone)
        next_zone["modules"] = [enrich_pve_module_payload(module, raiderio) for module in next_zone.get("modules") or []]
        zones.append(next_zone)
    result["zones"] = zones
    return result


def enrich_game_season_payload(payload, raiderio):
    if not isinstance(payload, dict):
        return payload
    result = dict(payload)
    source_refs = list(result.get("sourceRefs") or [])
    source_refs.append({
        "name": RAIDERIO_SOURCE_NAME,
        "url": raiderio.get("leaderboardUrl") or "https://raider.io/mythic-plus-rankings",
        "note": "Cached Raider.IO CN Mythic+ season, runs, affixes and cutoff data.",
    })
    result.update({
        "sourceRefs": source_refs,
        "raiderio": public_raiderio_summary(raiderio),
        "raiderioSeasonSlug": raiderio.get("seasonSlug") or "",
        "raiderioRegion": raiderio.get("region") or "",
        "raiderioSourceStatus": raiderio.get("sourceStatus") or "blocked",
        "raiderioCheckedAt": raiderio.get("checkedAt") or "",
        "raiderioAffixes": raiderio.get("affixes") or {},
        "raiderioCutoffs": raiderio.get("cutoffs") or {},
    })
    return result


def observed_gear_for_spec(raiderio, class_key, spec_key):
    aggregate = aggregate_by_spec(raiderio).get(f"{class_key}:{spec_key}") or {}
    return aggregate.get("observedGear") or []

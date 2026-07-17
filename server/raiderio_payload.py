import json
import os
import re
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


RAIDERIO_BASE_URL = "https://raider.io/api/v1"
RAIDERIO_WEB_API_BASE_URL = "https://raider.io/api"
RAIDERIO_CACHE_KEY = "raiderio_payload_v1"
RAIDERIO_SOURCE_NAME = "Raider.IO"
RAIDERIO_DEADLINE_ERROR = "Raider.IO sync deadline exceeded"
DEFAULT_REGION = "cn"
DEFAULT_LOCALE = "cn"
DEFAULT_SEASON_SLUG = "season-mn-1"
DEFAULT_EXPANSION_ID = "11"
RAIDERIO_BONUS_EMBELLISHMENTS = {
    "12384": {
        "key": "arcanoweave_lining",
        "label": "奥纹内衬",
    },
}
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


def emit_sync_stage(callback, stage, status, started_at=None, details=None):
    event = {
        "stage": stage,
        "status": status,
        "checkedAt": utc_now_iso(),
    }
    if started_at is not None:
        event["durationSeconds"] = round(max(0.0, time.monotonic() - started_at), 3)
    if isinstance(details, dict) and details:
        event.update(details)
    if callback:
        callback(event)
    return time.monotonic()


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


def normalize_observed_race_key(value):
    race_name, race_slug = dict_name_slug(value)
    key = slugify(race_slug or race_name, "")
    return key[:80] if key else ""


def role_for_spec(spec_key):
    if spec_key in SPEC_ROLE:
        return SPEC_ROLE[spec_key]
    return "dps"


def spec_pair_for_id(spec_id):
    try:
        numeric_id = int(spec_id or 0)
    except (TypeError, ValueError):
        numeric_id = 0
    if numeric_id <= 0:
        return None
    try:
        from .websim_payload import SPEC_ID_TO_KEY
    except ImportError:
        try:
            from websim_payload import SPEC_ID_TO_KEY
        except ImportError:
            SPEC_ID_TO_KEY = {}
    return SPEC_ID_TO_KEY.get(numeric_id)


def spec_id_for_pair(class_key, spec_key):
    expected = f"{normalize_class_key(class_key)}:{normalize_spec_key(spec_key)}"
    try:
        from .websim_payload import SPEC_ID_TO_KEY
    except ImportError:
        try:
            from websim_payload import SPEC_ID_TO_KEY
        except ImportError:
            SPEC_ID_TO_KEY = {}
    for spec_id, pair in SPEC_ID_TO_KEY.items():
        if f"{pair[0]}:{pair[1]}" == expected:
            return spec_id
    return ""


def decode_raw_talent_import_loadout(raw_import, class_key="", spec_key="", source="raw_import_code"):
    code = str(raw_import or "").strip()
    if not code:
        return {}
    result = {
        "rawImportCode": code,
        "loadoutSpecId": spec_id_for_pair(class_key, spec_key),
        "loadout": [],
        "source": source,
    }
    try:
        from .websim_payload import decode_external_talent_import_code
    except ImportError:
        try:
            from websim_payload import decode_external_talent_import_code
        except ImportError:
            decode_external_talent_import_code = None
    if not decode_external_talent_import_code:
        return result
    decoded = decode_external_talent_import_code(code, class_key, spec_key)
    if decoded.get("specId"):
        result["loadoutSpecId"] = decoded.get("specId")
    if decoded.get("status") != "decoded":
        return result
    result.update({
        "loadout": decoded.get("loadout") or [],
        "heroKey": decoded.get("heroKey") or "",
        "heroSubTreeId": decoded.get("heroSubTreeId") or "",
        "selector": decoded.get("selector") or {},
        "decoderSourcePath": decoded.get("sourcePath") or "",
    })
    return result


def talent_loadout_spec_blocker(class_key, spec_key, loadout):
    loadout_spec_id = (loadout or {}).get("loadoutSpecId") or (loadout or {}).get("loadout_spec_id")
    pair = spec_pair_for_id(loadout_spec_id)
    if not pair:
        return ""
    expected = f"{normalize_class_key(class_key)}:{normalize_spec_key(spec_key)}"
    actual = f"{pair[0]}:{pair[1]}"
    if actual == expected:
        return ""
    return (
        f"Raider.IO talent loadout spec id {loadout_spec_id} resolves to {actual}, "
        f"but the run roster template is {expected}; skipping profile-current talent loadout for this spec."
    )


def raiderio_region():
    return os.environ.get("WOW_RAIDERIO_REGION", DEFAULT_REGION).strip().lower() or DEFAULT_REGION


def raiderio_regions():
    raw = os.environ.get("WOW_RAIDERIO_REGIONS", "").strip()
    values = raw.split(",") if raw else [raiderio_region()]
    regions = []
    for value in values:
        region = str(value or "").strip().lower()
        if not region or region in regions:
            continue
        regions.append(region)
    return regions or [raiderio_region()]


def raiderio_locale():
    return os.environ.get("WOW_RAIDERIO_LOCALE", DEFAULT_LOCALE).strip() or DEFAULT_LOCALE


def raiderio_season_slug():
    return os.environ.get("WOW_RAIDERIO_SEASON", DEFAULT_SEASON_SLUG).strip() or DEFAULT_SEASON_SLUG


def raiderio_api_key():
    return os.environ.get("WOW_RAIDERIO_API_KEY", "").strip()


def raiderio_public_fallback_enabled():
    return os.environ.get("WOW_RAIDERIO_PUBLIC_FALLBACK", "0").strip().lower() in {"1", "true", "yes", "on"}


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
    query = dict(params or {})
    if key:
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
        except TimeoutError as error:
            last_error = RaiderIOError(redact_secret(f"Raider.IO network timeout: {error}"))
        except OSError as error:
            last_error = RaiderIOError(redact_secret(f"Raider.IO network error: {error}"))
        except json.JSONDecodeError as error:
            raise RaiderIOError(redact_secret(f"Raider.IO invalid JSON: {error}")) from None
    raise last_error or RaiderIOError("Raider.IO request failed")


def web_api_get(path, params=None):
    query = dict(params or {})
    url = f"{RAIDERIO_WEB_API_BASE_URL}{path}?{urlencode(query, doseq=True)}"
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
            last_error = RaiderIOError(redact_secret(f"Raider.IO web HTTP {error.code}: {body}"))
            if 400 <= error.code < 500:
                raise last_error from None
        except URLError as error:
            last_error = RaiderIOError(redact_secret(f"Raider.IO web network error: {error}"))
        except TimeoutError as error:
            last_error = RaiderIOError(redact_secret(f"Raider.IO web network timeout: {error}"))
        except OSError as error:
            last_error = RaiderIOError(redact_secret(f"Raider.IO web network error: {error}"))
        except json.JSONDecodeError as error:
            raise RaiderIOError(redact_secret(f"Raider.IO web invalid JSON: {error}")) from None
    raise last_error or RaiderIOError("Raider.IO web request failed")


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
    target_raw = os.environ.get("WOW_RAIDERIO_SPEC_RANKING_TARGET_SPECS", "").strip()
    if target_raw:
        target_specs = []
        for token in re.split(r"[\s,;]+", target_raw):
            token = str(token or "").strip().replace("/", ":")
            parts = token.split(":")
            if len(parts) != 2:
                continue
            class_key = normalize_class_key(parts[0])
            spec_key = normalize_spec_key(parts[1])
            spec_id = f"{class_key}:{spec_key}" if class_key and spec_key else ""
            if spec_id and spec_id not in target_specs:
                target_specs.append(spec_id)
        allowed = set(target_specs)
        return [spec_id for spec_id in pairs if spec_id in allowed]
    return pairs


def spec_pair_key(character):
    class_key = normalize_class_key(character.get("classKey") or character.get("classSlug") or character.get("className"))
    spec_key = normalize_spec_key(character.get("specKey") or character.get("specSlug") or character.get("specName"))
    return f"{class_key}:{spec_key}" if class_key and spec_key else ""


def profile_total_limit():
    per_spec_limit = max(1, int_env("WOW_RAIDERIO_PROFILE_LIMIT_PER_SPEC", 5))
    default_total = per_spec_limit * max(1, len(expected_spec_pairs()) or 40)
    return max(1, int_env("WOW_RAIDERIO_PROFILE_LIMIT", default_total))


def target_profile_limit():
    return max(0, int_env("WOW_RAIDERIO_TARGET_PROFILE_LIMIT", 120))


def profile_fetch_workers():
    return max(1, int_env("WOW_RAIDERIO_PROFILE_WORKERS", 1))


def run_detail_limit():
    return max(0, int_env("WOW_RAIDERIO_RUN_DETAIL_LIMIT", 160))


def run_detail_limit_per_spec():
    return max(0, int_env("WOW_RAIDERIO_RUN_DETAIL_LIMIT_PER_SPEC", 3))


def run_detail_fetch_workers():
    return max(1, int_env("WOW_RAIDERIO_RUN_DETAIL_WORKERS", 2))


def gap_fill_run_detail_limit():
    return max(0, int_env("WOW_RAIDERIO_GAP_FILL_RUN_DETAIL_LIMIT", run_detail_limit()))


def gap_fill_run_detail_limit_per_spec():
    return max(0, int_env("WOW_RAIDERIO_GAP_FILL_RUN_DETAIL_LIMIT_PER_SPEC", run_detail_limit_per_spec()))


def gap_fill_run_detail_frontload_per_spec():
    return max(0, int_env("WOW_RAIDERIO_GAP_FILL_RUN_DETAIL_FRONTLOAD_PER_SPEC", run_detail_limit_per_spec()))


def community_template_limit():
    return max(1, int_env("WOW_RAIDERIO_COMMUNITY_TEMPLATE_LIMIT", 240))


def talent_loadout_limit_per_spec():
    return max(1, int_env("WOW_RAIDERIO_TALENT_LOADOUT_LIMIT_PER_SPEC", 5))


def spec_ranking_enabled():
    return os.environ.get("WOW_RAIDERIO_SPEC_RANKING_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}


def spec_ranking_regions():
    raw = os.environ.get("WOW_RAIDERIO_SPEC_RANKING_REGIONS", "world").strip()
    values = raw.split(",") if raw else ["world"]
    regions = []
    for value in values:
        region = str(value or "").strip().lower()
        if region and region not in regions:
            regions.append(region)
    return regions or ["world"]


def spec_ranking_pages():
    return max(1, int_env("WOW_RAIDERIO_SPEC_RANKING_PAGES", 1))


def spec_ranking_page_size():
    return max(1, int_env("WOW_RAIDERIO_SPEC_RANKING_PAGE_SIZE", 20))


def spec_ranking_runs_per_character():
    return max(1, int_env("WOW_RAIDERIO_SPEC_RANKING_RUNS_PER_CHARACTER", 1))


def spec_ranking_gap_fill_enabled():
    return os.environ.get("WOW_RAIDERIO_SPEC_RANKING_GAP_FILL_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}


def spec_ranking_gap_fill_regions():
    raw = os.environ.get("WOW_RAIDERIO_SPEC_RANKING_GAP_FILL_REGIONS", "").strip()
    if not raw:
        return spec_ranking_regions()
    regions = []
    for value in raw.split(","):
        region = str(value or "").strip().lower()
        if region and region not in regions:
            regions.append(region)
    return regions or spec_ranking_regions()


def spec_ranking_gap_fill_pages():
    return max(0, int_env("WOW_RAIDERIO_SPEC_RANKING_GAP_FILL_PAGES", 0))


def spec_ranking_gap_fill_extra_start_pages():
    raw = os.environ.get("WOW_RAIDERIO_SPEC_RANKING_GAP_FILL_EXTRA_START_PAGES", "").strip()
    pages = []
    for value in raw.split(","):
        try:
            page = int(str(value or "").strip())
        except (TypeError, ValueError):
            continue
        if page >= 0 and page not in pages:
            pages.append(page)
    return pages


def spec_ranking_gap_fill_page_size():
    return max(1, int_env("WOW_RAIDERIO_SPEC_RANKING_GAP_FILL_PAGE_SIZE", spec_ranking_page_size()))


def spec_ranking_gap_fill_runs_per_character():
    return max(1, int_env("WOW_RAIDERIO_SPEC_RANKING_GAP_FILL_RUNS_PER_CHARACTER", spec_ranking_runs_per_character()))


def spec_ranking_hero_target_count():
    return max(1, int_env("WOW_RAIDERIO_SPEC_RANKING_HERO_TARGET_COUNT", 2))


def sync_deadline_at():
    seconds = max(0, int_env("WOW_RAIDERIO_SYNC_DEADLINE_SECONDS", 0))
    return time.monotonic() + seconds if seconds else 0


def sync_deadline_expired(deadline_at):
    return bool(deadline_at and time.monotonic() >= deadline_at)


def profile_payload_limit():
    return profile_total_limit() + target_profile_limit()


def is_profile_candidate(character):
    name = str((character or {}).get("name") or "").strip().lower()
    realm = str((character or {}).get("realmSlug") or "").strip().lower()
    if not name or not realm:
        return False
    return name != "anonymous" and realm != "anonymous"


def unique_profile_candidates_for_runs(runs):
    unique = []
    seen_characters = set()
    for run in runs:
        for character in run.get("roster") or []:
            if not is_profile_candidate(character):
                continue
            key = character_key(character)
            if key in seen_characters:
                continue
            seen_characters.add(key)
            unique.append(character)
    return unique


def select_profile_candidates_for_runs(runs):
    total_limit = profile_total_limit()
    per_spec_limit = max(1, int_env("WOW_RAIDERIO_PROFILE_LIMIT_PER_SPEC", 5))
    unique = []
    seen_characters = set()
    per_spec_counts = {}
    for run in runs:
        for character in run.get("roster") or []:
            if not is_profile_candidate(character):
                continue
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


def env_target_item_ids():
    raw = os.environ.get("WOW_RAIDERIO_TARGET_ITEM_IDS", "")
    ids = []
    for value in re.split(r"[\s,;/]+", raw):
        normalized = str(value or "").strip()
        if normalized and re.fullmatch(r"\d+", normalized) and normalized not in ids:
            ids.append(normalized)
    return ids


def sqlite_table_columns(conn, table):
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except Exception:
        return set()
    return {str(row[1]) for row in rows}


def target_source_bucket(source_label, source_type=""):
    text = str(source_label or "").strip()
    if text:
        parts = [part.strip() for part in re.split(r"\s+[-–—]\s+", text) if part.strip()]
        if len(parts) > 1:
            return parts[-1]
        return text
    return str(source_type or "unknown").strip() or "unknown"


def fair_target_item_ids(rows, limit):
    buckets = {}
    bucket_order = []
    for row in rows or []:
        item_id = str(row.get("itemId") or "").strip()
        if not item_id:
            continue
        source_label = target_source_bucket(row.get("sourceLabel"), row.get("sourceType"))
        slot = str(row.get("slot") or "").strip() or "slot"
        bucket_key = (source_label, slot)
        if bucket_key not in buckets:
            buckets[bucket_key] = []
            bucket_order.append(bucket_key)
        buckets[bucket_key].append(item_id)

    result = []
    seen = set()
    while len(result) < limit:
        progressed = False
        for bucket_key in list(bucket_order):
            bucket = buckets.get(bucket_key) or []
            while bucket:
                item_id = bucket.pop(0)
                if item_id in seen:
                    continue
                seen.add(item_id)
                result.append(item_id)
                progressed = True
                break
            if len(result) >= limit:
                break
        if not progressed:
            break
    return result


def db_target_item_ids(conn):
    if conn is None:
        return []
    try:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='websim_gear_variants'"
        ).fetchone()
        if not table_exists:
            return []
        limit = max(1, int_env("WOW_RAIDERIO_TARGET_ITEM_LIMIT", 80))
        variant_columns = sqlite_table_columns(conn, "websim_gear_variants")
        source_columns = sqlite_table_columns(conn, "websim_gear_sources")
        has_slot = "slot" in variant_columns
        has_sources = {"item_id", "source_type", "source_label"}.issubset(source_columns)
        slot_expr = "COALESCE(v.slot, '')" if has_slot else "''"
        if has_sources:
            rows = conn.execute(
                f"""
                SELECT DISTINCT v.item_id, {slot_expr}, COALESCE(s.source_label, ''), v.source_type
                FROM websim_gear_variants v
                LEFT JOIN websim_gear_sources s
                  ON s.item_id = v.item_id
                 AND s.source_type = v.source_type
                WHERE v.status = 'partial'
                  AND v.source_type IN ('dungeon', 'raid', 'tier_set')
                ORDER BY COALESCE(s.source_label, ''), {slot_expr}, CAST(v.item_id AS INTEGER), v.item_id
                """
            ).fetchall()
        else:
            rows = conn.execute(
                f"""
                SELECT DISTINCT v.item_id, {slot_expr}, '', v.source_type
                FROM websim_gear_variants v
                WHERE v.status = 'partial'
                  AND v.source_type IN ('dungeon', 'raid', 'tier_set')
                ORDER BY CAST(v.item_id AS INTEGER), v.item_id
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        if "payload_json" in variant_columns:
            observed_rows = conn.execute(
                f"""
                SELECT v.item_id, MIN({slot_expr}), 'Raider.IO observed profile', v.source_type, COUNT(*) AS missing_count
                FROM websim_gear_variants v
                WHERE v.status = 'verified'
                  AND v.source_type = 'observed_profile'
                  AND COALESCE(json_extract(v.payload_json, '$.statSource'), '') != 'simulationcraft'
                GROUP BY v.item_id, v.source_type
                ORDER BY missing_count DESC, CAST(v.item_id AS INTEGER), v.item_id
                """
            ).fetchall()
            rows = [*observed_rows, *rows]
    except Exception:
        return []
    candidates = [
        {
            "itemId": str(row[0] or "").strip(),
            "slot": str(row[1] or "").strip(),
            "sourceLabel": str(row[2] or "").strip(),
            "sourceType": str(row[3] or "").strip(),
        }
        for row in rows
    ]
    return fair_target_item_ids(candidates, limit)


def raiderio_target_item_ids(conn=None):
    result = []
    for item_id in [*env_target_item_ids(), *db_target_item_ids(conn)]:
        normalized = str(item_id or "").strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def profile_gear_item_ids(profile):
    ids = []
    for item in (profile or {}).get("gear") or []:
        item_id = str(item.get("itemId") or item.get("item_id") or item.get("id") or "").strip()
        if item_id and item_id not in ids:
            ids.append(item_id)
    return ids


def target_item_match_examples(profiles, targets):
    target_set = {str(item_id) for item_id in targets or [] if str(item_id or "").strip()}
    examples = []
    seen = set()
    profile_values = list((profiles or {}).values()) if isinstance(profiles, dict) else list(profiles or [])
    for profile in sorted(profile_values, key=character_key):
        profile_ref = {
            "name": profile.get("name") or "",
            "realmSlug": profile.get("realmSlug") or "",
            "region": profile.get("region") or raiderio_region(),
            "classKey": profile.get("classKey") or "",
            "specKey": profile.get("specKey") or "",
            "profileUrl": profile.get("profileUrl") or "",
        }
        for item in profile.get("gear") or []:
            item_id = str(item.get("itemId") or item.get("item_id") or item.get("id") or "").strip()
            if item_id not in target_set:
                continue
            key = (item_id, profile_ref["region"], profile_ref["realmSlug"], profile_ref["name"], item.get("slot") or "")
            if key in seen:
                continue
            seen.add(key)
            examples.append({
                "itemId": item_id,
                "slot": item.get("slot") or "",
                "name": item.get("name") or "",
                "itemLevel": item.get("itemLevel") or item.get("item_level") or 0,
                "bonuses": item.get("bonuses") if isinstance(item.get("bonuses"), list) else [],
                "gems": item.get("gems") if isinstance(item.get("gems"), list) else [],
                "enchants": item.get("enchants") if isinstance(item.get("enchants"), list) else [],
                "profile": profile_ref,
            })
            if len(examples) >= 40:
                return examples
    return examples


def target_item_coverage(profiles, target_item_ids):
    targets = [str(item_id) for item_id in target_item_ids or [] if str(item_id or "").strip()]
    matched = []
    for profile in (profiles or {}).values():
        for item_id in profile_gear_item_ids(profile):
            if item_id in targets and item_id not in matched:
                matched.append(item_id)
    return {
        "targetItemCount": len(targets),
        "matchedTargetItemIds": sorted(matched),
        "missingTargetItemIds": sorted([item_id for item_id in targets if item_id not in matched]),
        "matchedTargetItemExamples": target_item_match_examples(profiles, targets),
        "targetProfileRequestLimit": target_profile_limit(),
    }


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


def _spec_pair_parts(spec_id):
    parts = str(spec_id or "").split(":", 1)
    if len(parts) != 2:
        return "", ""
    return normalize_class_key(parts[0]), normalize_spec_key(parts[1])


def _count_profiles_by_spec(profiles):
    counts = {}
    for profile in (profiles or {}).values():
        spec_id = spec_pair_key(profile)
        if spec_id:
            counts[spec_id] = counts.get(spec_id, 0) + 1
    return counts


def _count_run_detail_snapshots_by_spec(runs):
    counts = {}
    for run in runs or []:
        for character in run.get("roster") or []:
            spec_id = spec_pair_key(character)
            talent = character.get("talentLoadout") if isinstance(character.get("talentLoadout"), dict) else {}
            if spec_id and talent.get("source") == "run_detail" and talent.get("loadout"):
                counts[spec_id] = counts.get(spec_id, 0) + 1
    return counts


def _count_templates_by_spec(templates):
    counts = {}
    for template in templates or []:
        class_key = normalize_class_key(template.get("classKey"))
        spec_key = normalize_spec_key(template.get("specKey"))
        if class_key and spec_key:
            spec_id = f"{class_key}:{spec_key}"
            counts[spec_id] = counts.get(spec_id, 0) + 1
    return counts


def _target_spec_next_action(attempted_runs, profile_count, run_detail_count, candidate_count):
    if candidate_count > 0:
        return "validate and promote per-spec talent candidates into exact class/spec/hero slots"
    if run_detail_count > 0:
        return "extract and validate run-detail talent snapshots for this spec"
    if profile_count > 0:
        return "fetch run-detail talent snapshots for observed high-score runs in this spec"
    if attempted_runs > 0:
        return "fetch profiles for observed high-score runs in this spec"
    return "fetch Raider.IO class/spec ranking pool for this spec"


def build_target_spec_matrix(runs, profiles, templates, checked_at=""):
    expected = expected_spec_pairs()
    if not expected:
        expected = sorted({spec_pair_key(character) for run in runs or [] for character in run.get("roster") or [] if spec_pair_key(character)})
    spec_coverage = spec_coverage_from_runs(runs)
    run_counts = spec_coverage.get("sampleCounts") if isinstance(spec_coverage.get("sampleCounts"), dict) else {}
    profile_counts = _count_profiles_by_spec(profiles)
    run_detail_counts = _count_run_detail_snapshots_by_spec(runs)
    template_counts = _count_templates_by_spec(templates)
    rows = []
    for spec_id in expected:
        class_key, spec_key = _spec_pair_parts(spec_id)
        attempted_runs = safe_int(run_counts.get(spec_id))
        profile_count = safe_int(profile_counts.get(spec_id))
        run_detail_count = safe_int(run_detail_counts.get(spec_id))
        candidate_count = safe_int(template_counts.get(spec_id))
        if candidate_count:
            status = "candidate_pool"
        elif run_detail_count:
            status = "run_detail_observed"
        elif profile_count:
            status = "profile_observed"
        elif attempted_runs:
            status = "run_observed"
        else:
            status = "pending_collection"
        rows.append(
            {
                "specId": spec_id,
                "classKey": class_key,
                "specKey": spec_key,
                "status": status,
                "attemptedRunCount": attempted_runs,
                "profileCount": profile_count,
                "runDetailSnapshotCount": run_detail_count,
                "candidateCount": candidate_count,
                "nextAction": _target_spec_next_action(attempted_runs, profile_count, run_detail_count, candidate_count),
            }
        )
    attempted = [row for row in rows if row["attemptedRunCount"] > 0]
    candidate_specs = [row for row in rows if row["candidateCount"] > 0]
    pending = [row for row in rows if row["candidateCount"] <= 0]
    return {
        "schemaRevision": "raiderio-target-spec-matrix-v1",
        "checkedAt": checked_at,
        "totalSpecCount": len(rows),
        "attemptedSpecCount": len(attempted),
        "candidateSpecCount": len(candidate_specs),
        "pendingSpecCount": len(pending),
        "profileCount": sum(row["profileCount"] for row in rows),
        "runDetailSnapshotCount": sum(row["runDetailSnapshotCount"] for row in rows),
        "candidateCount": sum(row["candidateCount"] for row in rows),
        "pendingSpecs": [row["specId"] for row in pending],
        "rows": rows,
    }


def simplify_character(raw, default_region=None):
    data = raw.get("character") if isinstance(raw.get("character"), dict) else raw
    realm = data.get("realm") if isinstance(data.get("realm"), dict) else {}
    class_name, class_slug = dict_name_slug(data.get("class") or data.get("class_name"))
    race_key = normalize_observed_race_key(
        data.get("race") or data.get("race_name") or data.get("raceName") or data.get("race_slug")
    )
    spec_source = data.get("spec") or data.get("spec_name") or data.get("active_spec_name") or data.get("activeSpecName")
    spec_name, spec_slug = dict_name_slug(spec_source)
    spec_id = ""
    if isinstance(spec_source, dict):
        spec_id = spec_source.get("id") or spec_source.get("specId") or ""
    class_key = normalize_class_key(class_slug or class_name)
    spec_key = normalize_spec_key(spec_slug or spec_name)
    region = data.get("region")
    if isinstance(region, dict):
        region = region.get("slug") or region.get("name")
    profile_url = data.get("profile_url") or data.get("profileUrl") or ""
    if not profile_url and str(data.get("path") or "").startswith("/"):
        profile_url = f"https://raider.io{data.get('path')}"
    result = {
        "name": str(data.get("name") or "").strip(),
        "realm": realm.get("name") or data.get("realm_name") or "",
        "realmSlug": realm.get("slug") or data.get("realm_slug") or "",
        "realmAltName": realm.get("altName") or "",
        "region": str(region or default_region or raiderio_region()).lower(),
        "className": class_name or class_key,
        "classSlug": class_slug or class_key,
        "classKey": class_key,
        "specName": spec_name or spec_key,
        "specSlug": spec_slug or spec_key,
        "specKey": spec_key,
        "role": role_for_spec(spec_key),
        "profileUrl": profile_url,
    }
    if race_key:
        result["raceKey"] = race_key
    raw_loadout = str(
        raw.get("loadout")
        or data.get("loadout")
        or data.get("talentLoadoutText")
        or data.get("talent_loadout_text")
        or data.get("loadoutText")
        or data.get("loadout_text")
        or ""
    ).strip()
    if raw_loadout:
        decoded_loadout = decode_raw_talent_import_loadout(raw_loadout, class_key, spec_key, "run_roster")
        result["talentLoadout"] = {
            **decoded_loadout,
            "loadoutSpecId": spec_id or decoded_loadout.get("loadoutSpecId") or "",
        }
    return result


def simplify_run(ranking, leaderboard_url="", region=None):
    run = ranking.get("run") if isinstance(ranking.get("run"), dict) else {}
    dungeon_name, dungeon_slug = dict_name_slug(run.get("dungeon"))
    roster = [simplify_character(item, default_region=region) for item in run.get("roster") or []]
    roster = [item for item in roster if is_profile_candidate(item)]
    return {
        "runId": safe_int(run.get("keystone_run_id") or run.get("keystoneRunId") or run.get("id")),
        "region": str(region or raiderio_region()).lower(),
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


def raiderio_class_slug_for_ranking(class_key):
    key = normalize_class_key(class_key)
    aliases = {
        "deathknight": "death-knight",
        "demonhunter": "demon-hunter",
    }
    return aliases.get(key, key.replace("_", "-"))


def raiderio_spec_slug_for_ranking(spec_key):
    return normalize_spec_key(spec_key).replace("_", "-")


def label_from_key(value):
    words = [part for part in str(value or "").replace("-", "_").split("_") if part]
    return " ".join(word.capitalize() for word in words) or str(value or "")


def spec_ranking_source_url(season_slug, region, class_key, spec_key):
    return (
        "https://raider.io/mythic-plus-spec-rankings/"
        f"{season_slug}/{region}/{raiderio_class_slug_for_ranking(class_key)}/{raiderio_spec_slug_for_ranking(spec_key)}"
    )


def simplify_spec_ranking_character(ranked_character, target_class_key, target_spec_key, default_region=None):
    character = simplify_character(ranked_character, default_region=default_region)
    class_payload = {}
    spec_payload = {}
    raw_character = ranked_character.get("character") if isinstance(ranked_character.get("character"), dict) else {}
    if isinstance(raw_character.get("class"), dict):
        class_payload = raw_character.get("class") or {}
    if isinstance(raw_character.get("spec"), dict):
        spec_payload = raw_character.get("spec") or {}
    character.update({
        "classKey": normalize_class_key(target_class_key),
        "classSlug": raiderio_class_slug_for_ranking(target_class_key),
        "className": class_payload.get("name") or label_from_key(target_class_key),
        "specKey": normalize_spec_key(target_spec_key),
        "specSlug": raiderio_spec_slug_for_ranking(target_spec_key),
        "specName": label_from_key(target_spec_key),
        "role": role_for_spec(normalize_spec_key(target_spec_key)),
    })
    if spec_pair_key(character) != f"{normalize_class_key(target_class_key)}:{normalize_spec_key(target_spec_key)}":
        character["specKey"] = normalize_spec_key(target_spec_key)
    if spec_payload:
        character["rankingCharacterSpecId"] = spec_payload.get("id") or ""
        character["rankingCharacterSpecKey"] = normalize_spec_key(spec_payload.get("slug") or spec_payload.get("name"))
    raw_character = ranked_character.get("character") if isinstance(ranked_character.get("character"), dict) else {}
    ranking_import = str(
        raw_character.get("talentLoadoutText")
        or raw_character.get("talent_loadout_text")
        or raw_character.get("loadoutText")
        or raw_character.get("loadout_text")
        or ""
    ).strip()
    if ranking_import:
        character["talentLoadout"] = decode_raw_talent_import_loadout(
            ranking_import,
            target_class_key,
            target_spec_key,
            "spec_ranking_import_code",
        )
    return character


def simplify_spec_ranking_run(ranked_character, run_payload, target_class_key, target_spec_key, ranking_region, source_url):
    character = simplify_spec_ranking_character(
        ranked_character,
        target_class_key,
        target_spec_key,
        default_region=ranking_region,
    )
    if not is_profile_candidate(character):
        return {}
    run = run_payload if isinstance(run_payload, dict) else {}
    return {
        "runId": safe_int(run.get("keystoneRunId") or run.get("keystone_run_id") or run.get("id")),
        "region": str(character.get("region") or ranking_region or raiderio_region()).lower(),
        "rank": safe_int(ranked_character.get("rank")),
        "score": safe_float(ranked_character.get("score") or run.get("score")),
        "dungeonName": run.get("zoneName") or run.get("dungeonName") or "",
        "dungeonSlug": slugify(run.get("zoneName") or run.get("dungeonName") or "", ""),
        "mythicLevel": safe_int(run.get("mythicLevel") or run.get("mythic_level")),
        "clearTimeMs": safe_int(run.get("clearTimeMs") or run.get("clear_time_ms")),
        "completedAt": run.get("completedAt") or run.get("completed_at") or "",
        "weeklyModifiers": run.get("weeklyModifiers") or run.get("weekly_modifiers") or run.get("affixes") or [],
        "roster": [character],
        "sourceUrl": source_url,
        "source": "spec_ranking",
        "specRanking": {
            "region": ranking_region,
            "classKey": normalize_class_key(target_class_key),
            "specKey": normalize_spec_key(target_spec_key),
            "rank": safe_int(ranked_character.get("rank")),
            "score": safe_float(ranked_character.get("score")),
        },
    }


def merge_runs_by_region_id(runs):
    merged = []
    by_key = {}
    for run in runs or []:
        if not isinstance(run, dict):
            continue
        run_id = safe_int(run.get("runId"))
        key = f"{str(run.get('region') or raiderio_region()).lower()}:{run_id}" if run_id > 0 else ""
        if not key or key not in by_key:
            copy = dict(run)
            copy["roster"] = list(run.get("roster") or [])
            merged.append(copy)
            if key:
                by_key[key] = copy
            continue
        existing = by_key[key]
        seen = {f"{character_key(character)}:{spec_pair_key(character)}" for character in existing.get("roster") or []}
        for character in run.get("roster") or []:
            roster_key = f"{character_key(character)}:{spec_pair_key(character)}"
            if roster_key in seen:
                continue
            seen.add(roster_key)
            existing.setdefault("roster", []).append(character)
        existing["mythicLevel"] = max(safe_int(existing.get("mythicLevel")), safe_int(run.get("mythicLevel")))
        existing["score"] = max(safe_float(existing.get("score")), safe_float(run.get("score")))
        if not existing.get("sourceUrl") and run.get("sourceUrl"):
            existing["sourceUrl"] = run.get("sourceUrl")
    return merged


def run_ranking_evidence(run, character=None):
    run = run if isinstance(run, dict) else {}
    character = character if isinstance(character, dict) else {}
    spec_ranking = run.get("specRanking") if isinstance(run.get("specRanking"), dict) else {}
    evidence = {
        "source": "raiderio_spec_ranking" if run.get("source") == "spec_ranking" or spec_ranking else "raiderio_run_ranking",
        "rank": safe_int(run.get("rank") or spec_ranking.get("rank")),
        "score": safe_float(run.get("score") or spec_ranking.get("score")),
        "maxKeyLevel": safe_int(run.get("mythicLevel")),
        "runId": safe_int(run.get("runId")),
        "sourceUrl": run.get("sourceUrl") or "",
        "region": run.get("region") or character.get("region") or "",
    }
    if spec_ranking:
        evidence["specRanking"] = dict(spec_ranking)
    return {key: value for key, value in evidence.items() if value not in (None, "", 0, {}, [])}


def ranking_evidence_sort_key(evidence):
    evidence = evidence if isinstance(evidence, dict) else {}
    rank = safe_int(evidence.get("rank"))
    return (
        1 if evidence.get("source") == "raiderio_spec_ranking" else 0,
        -rank if rank > 0 else -999999,
        safe_float(evidence.get("score")),
        safe_int(evidence.get("maxKeyLevel")),
    )


def ranking_evidence_by_character_from_runs(runs):
    evidence_by_character = {}
    for run in runs or []:
        if not isinstance(run, dict):
            continue
        for character in run.get("roster") or []:
            if not isinstance(character, dict):
                continue
            key = character_key(character)
            if not key:
                continue
            evidence = run_ranking_evidence(run, character)
            if not evidence:
                continue
            existing = evidence_by_character.get(key)
            if not existing or ranking_evidence_sort_key(evidence) > ranking_evidence_sort_key(existing):
                evidence_by_character[key] = evidence
    return evidence_by_character


def empty_spec_ranking_summary(
    enabled=None,
    errors=None,
    regions=None,
    pages=None,
    page_size=None,
    runs_per_character=None,
    start_page=0,
):
    enabled = spec_ranking_enabled() if enabled is None else bool(enabled)
    return {
        "enabled": enabled,
        "regions": (regions if regions is not None else spec_ranking_regions()) if enabled else [],
        "pages": (pages if pages is not None else spec_ranking_pages()) if enabled else 0,
        "pageSize": (page_size if page_size is not None else spec_ranking_page_size()) if enabled else 0,
        "runsPerCharacter": (
            runs_per_character if runs_per_character is not None else spec_ranking_runs_per_character()
        ) if enabled else 0,
        "startPage": max(0, int(start_page or 0)),
        "requestCount": 0,
        "attemptedSpecCount": 0,
        "characterCount": 0,
        "runCount": 0,
        "errors": [redact_secret(error) for error in (errors or [])],
        "perSpec": {},
    }


def fetch_spec_ranking_runs(
    expected_specs=None,
    season_slug=None,
    deadline_at=0,
    stage_callback=None,
    regions=None,
    pages=None,
    page_size=None,
    runs_per_character=None,
    start_page=0,
    stage_name="raiderio_spec_rankings",
):
    if not spec_ranking_enabled():
        return [], empty_spec_ranking_summary(False)
    season_slug = season_slug or raiderio_season_slug()
    specs = [spec_id for spec_id in (expected_specs or expected_spec_pairs()) if _spec_pair_parts(spec_id) != ("", "")]
    regions = regions or spec_ranking_regions()
    pages = spec_ranking_pages() if pages is None else max(0, int(pages or 0))
    page_size = spec_ranking_page_size() if page_size is None else max(1, int(page_size or 0))
    runs_per_character = (
        spec_ranking_runs_per_character()
        if runs_per_character is None
        else max(1, int(runs_per_character or 0))
    )
    start_page = max(0, int(start_page or 0))
    summary = empty_spec_ranking_summary(
        True,
        regions=regions,
        pages=pages,
        page_size=page_size,
        runs_per_character=runs_per_character,
        start_page=start_page,
    )
    per_spec = {}
    runs = []
    errors = []
    seen_run_characters = set()
    stage_started = emit_sync_stage(
        stage_callback,
        stage_name,
        "start",
        details={
            "specCount": len(specs),
            "regions": regions,
            "pages": pages,
            "pageSize": page_size,
            "startPage": start_page,
        },
    )
    for spec_id in specs:
        class_key, spec_key = _spec_pair_parts(spec_id)
        if not class_key or not spec_key:
            continue
        spec_summary = per_spec.setdefault(
            spec_id,
            {"requestCount": 0, "characterCount": 0, "runCount": 0, "regions": {}},
        )
        for region in regions:
            region_summary = spec_summary["regions"].setdefault(region, {"requestCount": 0, "characterCount": 0, "runCount": 0})
            for page in range(start_page, start_page + pages):
                if sync_deadline_expired(deadline_at):
                    errors.append(RAIDERIO_DEADLINE_ERROR)
                    break
                params = {
                    "season": season_slug,
                    "region": region,
                    "class": raiderio_class_slug_for_ranking(class_key),
                    "spec": raiderio_spec_slug_for_ranking(spec_key),
                    "page": page,
                    "pageSize": page_size,
                }
                try:
                    response = web_api_get("/mythic-plus/rankings/specs", params)
                except (RaiderIOError, TimeoutError, OSError) as error:
                    errors.append(redact_secret(f"{spec_id}/{region}/page-{page}: {error}"))
                    break
                summary["requestCount"] += 1
                spec_summary["requestCount"] += 1
                region_summary["requestCount"] += 1
                rankings = response.get("rankings") if isinstance(response.get("rankings"), dict) else {}
                ranked_characters = rankings.get("rankedCharacters") if isinstance(rankings.get("rankedCharacters"), list) else []
                source_url = spec_ranking_source_url(season_slug, region, class_key, spec_key)
                for ranked_character in ranked_characters:
                    if not isinstance(ranked_character, dict):
                        continue
                    summary["characterCount"] += 1
                    spec_summary["characterCount"] += 1
                    region_summary["characterCount"] += 1
                    for run_payload in (ranked_character.get("runs") or [])[:runs_per_character]:
                        run = simplify_spec_ranking_run(
                            ranked_character,
                            run_payload,
                            class_key,
                            spec_key,
                            region,
                            source_url,
                        )
                        if not run.get("runId") or not run.get("roster"):
                            continue
                        character = run["roster"][0]
                        dedupe_key = f"{run_detail_key(run)}:{character_key(character)}:{spec_pair_key(character)}"
                        if dedupe_key in seen_run_characters:
                            continue
                        seen_run_characters.add(dedupe_key)
                        runs.append(run)
                        summary["runCount"] += 1
                        spec_summary["runCount"] += 1
                        region_summary["runCount"] += 1
                if len(ranked_characters) < page_size:
                    break
            if sync_deadline_expired(deadline_at):
                break
        if sync_deadline_expired(deadline_at):
            break
    summary["attemptedSpecCount"] = len([value for value in per_spec.values() if value.get("requestCount")])
    summary["errors"] = errors[:12]
    summary["perSpec"] = per_spec
    emit_sync_stage(
        stage_callback,
        stage_name,
        "complete",
        stage_started,
        {
            "attemptedSpecCount": summary["attemptedSpecCount"],
            "requestCount": summary["requestCount"],
            "characterCount": summary["characterCount"],
            "runCount": summary["runCount"],
            "errors": len(errors),
        },
    )
    return runs, summary


def hero_subtree_coverage_from_runs(runs):
    coverage = {}
    for run in runs or []:
        for character in run.get("roster") or []:
            spec_id = spec_pair_key(character)
            if not spec_id:
                continue
            loadout = character.get("talentLoadout") if isinstance(character.get("talentLoadout"), dict) else {}
            hero_id = str(loadout.get("heroSubTreeId") or loadout.get("hero_sub_tree_id") or "").strip()
            if not hero_id:
                continue
            row = coverage.setdefault(spec_id, set())
            row.add(hero_id)
    return {
        spec_id: {
            "heroSubTreeIds": sorted(values, key=lambda value: (safe_int(value), value)),
            "observedHeroSubTreeCount": len(values),
        }
        for spec_id, values in sorted(coverage.items())
    }


def specs_needing_hero_gap_fill(runs, expected_specs=None):
    if not spec_ranking_gap_fill_enabled() or spec_ranking_gap_fill_pages() <= 0:
        return []
    expected = [spec_id for spec_id in (expected_specs or expected_spec_pairs()) if _spec_pair_parts(spec_id) != ("", "")]
    run_counts = (spec_coverage_from_runs(runs).get("sampleCounts") or {})
    hero_coverage = hero_subtree_coverage_from_runs(runs)
    target_count = spec_ranking_hero_target_count()
    missing = []
    for spec_id in expected:
        if safe_int(run_counts.get(spec_id)) <= 0:
            continue
        observed = safe_int((hero_coverage.get(spec_id) or {}).get("observedHeroSubTreeCount"))
        if observed < target_count:
            missing.append(spec_id)
    return missing


def combine_run_detail_summaries(base_summary, gap_summary=None):
    base = dict(base_summary or {})
    if not gap_summary:
        return base
    gap = dict(gap_summary or {})
    combined = {
        **base,
        "requestedRunCount": safe_int(base.get("requestedRunCount")) + safe_int(gap.get("requestedRunCount")),
        "talentSnapshotCount": safe_int(base.get("talentSnapshotCount")) + safe_int(gap.get("talentSnapshotCount")),
        "errors": [*(base.get("errors") or []), *(gap.get("errors") or [])],
        "gapFill": gap,
    }
    return combined


def extract_talent_loadout(profile, class_key="", spec_key=""):
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
    decoded_loadout = decode_raw_talent_import_loadout(raw_import, class_key, spec_key, "profile_current")
    return {
        "rawImportCode": raw_import,
        "loadoutSpecId": loadout.get("loadout_spec_id") or loadout.get("loadoutSpecId") or decoded_loadout.get("loadoutSpecId") or "",
        "loadout": loadout.get("loadout") or decoded_loadout.get("loadout") or [],
        **({"heroKey": decoded_loadout.get("heroKey")} if decoded_loadout.get("heroKey") else {}),
        **({"heroSubTreeId": decoded_loadout.get("heroSubTreeId")} if decoded_loadout.get("heroSubTreeId") else {}),
        "source": "profile_current",
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


def raiderio_option_id(value, keys=None):
    keys = keys or ("id", "item_id", "itemId", "enchant", "enchant_id", "enchantId", "bonus_id", "bonusId")
    if isinstance(value, dict):
        for key in keys:
            raw = value.get(key)
            if raw not in (None, "", [], {}):
                return str(raw).strip()
        return ""
    if value in (None, "", [], {}):
        return ""
    return str(value).strip()


def raiderio_option_ids(value, keys=None, *, deduplicate=True):
    if isinstance(value, list):
        ids = [raiderio_option_id(item, keys) for item in value]
    else:
        ids = [raiderio_option_id(value, keys)]
    ids = [item for item in ids if item and item != "0"]
    return list(dict.fromkeys(ids)) if deduplicate else ids


def extract_raiderio_item_enhancements(item):
    item = item if isinstance(item, dict) else {}
    bonus_ids = raiderio_option_ids(item.get("bonuses") or item.get("bonusIds"), ("id", "bonus_id", "bonusId"))
    gem_payload = item.get("gems") or item.get("gem") or []
    gem_ids = raiderio_option_ids(
        gem_payload,
        ("item_id", "itemId", "id", "gem_id", "gemId"),
        deduplicate=False,
    )
    enchant_payload = item.get("enchants") or item.get("enchant") or []
    enchant_ids = raiderio_option_ids(enchant_payload, ("enchant", "enchant_id", "enchantId", "id"))
    enhancements = {
        "bonus_id": "/".join(bonus_ids) if bonus_ids else "",
        "gem_id": "/".join(gem_ids) if gem_ids else "",
        "enchant_id": "/".join(enchant_ids) if enchant_ids else "",
        "gemsDetail": item.get("gems_detail") or item.get("gemsDetail") or (gem_payload if isinstance(gem_payload, list) else []),
        "enchantsDetail": item.get("enchants_detail") or item.get("enchantsDetail") or (
            enchant_payload if isinstance(enchant_payload, list) else []
        ),
    }
    embellishment = next(
        (
            RAIDERIO_BONUS_EMBELLISHMENTS[bonus_id]
            for bonus_id in bonus_ids
            if bonus_id in RAIDERIO_BONUS_EMBELLISHMENTS
        ),
        None,
    )
    if embellishment:
        enhancements.update(
            {
                "embellishment": embellishment["key"],
                "embellishmentLabel": embellishment["label"],
                "embellishmentSource": "raiderio_bonus_id",
            }
        )
    if any(enhancements.get(key) for key in ("bonus_id", "gem_id", "enchant_id", "embellishment")):
        enhancements["enhancementSource"] = "raiderio_profile_gear"
    return {key: value for key, value in enhancements.items() if value not in (None, "", [], {})}


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
            **extract_raiderio_item_enhancements(item),
            "sourceName": RAIDERIO_SOURCE_NAME,
            "sourceStatus": "source_reference",
            "simcReady": False,
        })
    return sorted(result, key=lambda item: item.get("slot") or "")


def profile_summary(profile):
    character = simplify_character(profile)
    character["profileUrl"] = profile.get("profile_url") or character.get("profileUrl") or ""
    character["talentLoadout"] = extract_talent_loadout(profile, character.get("classKey"), character.get("specKey"))
    character["gear"] = extract_gear(profile)
    character["itemLevel"] = safe_float((profile.get("gear") or {}).get("item_level_equipped"))
    return character


def fetch_profile_for_character(character, fields):
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
    return summary


def profile_fetch_error_message(error):
    if isinstance(error, RaiderIOError):
        return str(error)
    return redact_secret(f"Raider.IO profile fetch failed: {error}")


def fetch_profile_batch(characters, fields):
    candidates = [character for character in characters or [] if character]
    if not candidates:
        return [], []
    workers = min(profile_fetch_workers(), len(candidates))
    profiles = []
    errors = []
    if workers <= 1:
        for character in candidates:
            try:
                profiles.append(fetch_profile_for_character(character, fields))
            except (RaiderIOError, TimeoutError, OSError) as error:
                errors.append(profile_fetch_error_message(error))
        return profiles, errors

    results = [None] * len(candidates)
    indexed_errors = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_indexes = {
            executor.submit(fetch_profile_for_character, character, fields): index
            for index, character in enumerate(candidates)
        }
        for future in as_completed(future_indexes):
            index = future_indexes[future]
            try:
                results[index] = future.result()
            except (RaiderIOError, TimeoutError, OSError) as error:
                indexed_errors.append((index, profile_fetch_error_message(error)))
    profiles = [profile for profile in results if profile]
    errors = [message for _index, message in sorted(indexed_errors)]
    return profiles, errors


def run_roster_spec_keys(run):
    spec_keys = []
    for character in (run or {}).get("roster") or []:
        spec_key = spec_pair_key(character)
        if spec_key and spec_key not in spec_keys:
            spec_keys.append(spec_key)
    return spec_keys


def run_roster_hero_subtree_pairs(run):
    pairs = []
    for character in (run or {}).get("roster") or []:
        spec_key = spec_pair_key(character)
        talent = character.get("talentLoadout") if isinstance(character.get("talentLoadout"), dict) else {}
        hero_subtree_id = str(talent.get("heroSubTreeId") or talent.get("hero_sub_tree_id") or "").strip()
        if spec_key and hero_subtree_id and (spec_key, hero_subtree_id) not in pairs:
            pairs.append((spec_key, hero_subtree_id))
    return pairs


def run_has_run_detail_snapshot(run):
    roster = (run or {}).get("roster") or []
    if not roster:
        return False
    for character in roster:
        talent = character.get("talentLoadout") if isinstance(character.get("talentLoadout"), dict) else {}
        if not (talent.get("source") == "run_detail" and talent.get("loadout")):
            return False
    return True


def spread_indexes(total_count, limit):
    total_count = max(0, safe_int(total_count))
    limit = max(0, safe_int(limit))
    if total_count <= 0 or limit <= 0:
        return []
    if total_count <= limit:
        return list(range(total_count))
    if limit == 1:
        return [0]
    indexes = []
    seen = set()
    for step in range(limit):
        index = round(step * (total_count - 1) / (limit - 1))
        if index in seen:
            continue
        seen.add(index)
        indexes.append(index)
    return indexes


def spread_indexes_after_frontload(total_count, frontload_count, limit):
    total_count = max(0, safe_int(total_count))
    frontload_count = min(total_count, max(0, safe_int(frontload_count)))
    limit = max(0, safe_int(limit))
    remaining_count = total_count - frontload_count
    if remaining_count <= 0 or limit <= 0:
        return []
    if remaining_count <= limit:
        return list(range(frontload_count, total_count))
    indexes = []
    seen = set()
    for step in range(1, limit + 1):
        index = frontload_count + round(step * (remaining_count - 1) / limit)
        if index in seen:
            continue
        seen.add(index)
        indexes.append(index)
    return indexes


def spread_run_items_by_primary_spec(run_items, counts_by_spec, per_spec_limit, frontload_counts_by_spec=None):
    frontload_counts_by_spec = frontload_counts_by_spec or {}
    groups = {}
    group_order = []
    for item in run_items:
        spec_keys = item[2]
        primary_spec = spec_keys[0] if spec_keys else ""
        if not primary_spec:
            continue
        if primary_spec not in groups:
            groups[primary_spec] = []
            group_order.append(primary_spec)
        groups[primary_spec].append(item)
    ordered = []
    seen_indexes = set()
    for spec_key in group_order:
        remaining = max(0, per_spec_limit - safe_int(counts_by_spec.get(spec_key)))
        if remaining <= 0:
            continue
        group = groups.get(spec_key) or []
        frontloaded = safe_int(frontload_counts_by_spec.get(spec_key))
        positions = (
            spread_indexes_after_frontload(len(group), frontloaded, remaining)
            if frontloaded > 0
            else spread_indexes(len(group), remaining)
        )
        for position in positions:
            item = group[position]
            if item[0] in seen_indexes:
                continue
            seen_indexes.add(item[0])
            ordered.append(item)
    return ordered


def select_run_detail_candidates(runs, limit=None, per_spec_limit=None, spread_by_spec=False, frontload_per_spec=0):
    limit = run_detail_limit() if limit is None else max(0, safe_int(limit))
    per_spec_limit = run_detail_limit_per_spec() if per_spec_limit is None else max(0, safe_int(per_spec_limit))
    frontload_per_spec = max(0, safe_int(frontload_per_spec))
    if limit <= 0 or per_spec_limit <= 0:
        return []
    candidates_by_index = {}
    seen_runs = set()
    counts_by_spec = {}
    seen_hero_subtrees_by_spec = {}
    run_items = []
    for index, run in enumerate(runs or []):
        run_id = safe_int(run.get("runId"))
        run_key = f"{str(run.get('region') or raiderio_region()).lower()}:{run_id}"
        if run_id <= 0 or run_key in seen_runs:
            continue
        seen_runs.add(run_key)
        if run_has_run_detail_snapshot(run):
            continue
        spec_keys = run_roster_spec_keys(run)
        if not spec_keys:
            continue
        run_items.append((index, run, spec_keys, run_roster_hero_subtree_pairs(run)))

    def can_select(spec_keys):
        return any(counts_by_spec.get(spec_key, 0) < per_spec_limit for spec_key in spec_keys)

    def mark_selected(index, run, spec_keys):
        if index in candidates_by_index or len(candidates_by_index) >= limit or not can_select(spec_keys):
            return False
        candidates_by_index[index] = run
        for spec_key in spec_keys:
            counts_by_spec[spec_key] = counts_by_spec.get(spec_key, 0) + 1
        return True

    for index, run, spec_keys, hero_pairs in run_items:
        if len(candidates_by_index) >= limit:
            break
        if not hero_pairs:
            continue
        if not any(
            hero_subtree_id not in seen_hero_subtrees_by_spec.setdefault(spec_key, set())
            for spec_key, hero_subtree_id in hero_pairs
        ):
            continue
        if mark_selected(index, run, spec_keys):
            for spec_key, hero_subtree_id in hero_pairs:
                seen_hero_subtrees_by_spec.setdefault(spec_key, set()).add(hero_subtree_id)

    frontload_counts_by_spec = {}
    if spread_by_spec and frontload_per_spec > 0:
        for index, run, spec_keys, _hero_pairs in run_items:
            if len(candidates_by_index) >= limit:
                break
            if not any(frontload_counts_by_spec.get(spec_key, 0) < frontload_per_spec for spec_key in spec_keys):
                continue
            if mark_selected(index, run, spec_keys):
                for spec_key in spec_keys:
                    frontload_counts_by_spec[spec_key] = frontload_counts_by_spec.get(spec_key, 0) + 1

    if spread_by_spec:
        for index, run, spec_keys, _hero_pairs in spread_run_items_by_primary_spec(
            run_items,
            counts_by_spec,
            per_spec_limit,
            frontload_counts_by_spec=frontload_counts_by_spec,
        ):
            if len(candidates_by_index) >= limit:
                break
            mark_selected(index, run, spec_keys)

    for index, run, spec_keys, _hero_pairs in run_items:
        if len(candidates_by_index) >= limit:
            break
        mark_selected(index, run, spec_keys)

    return [candidates_by_index[index] for index in sorted(candidates_by_index)]


def run_detail_error_message(error):
    if isinstance(error, RaiderIOError):
        return str(error)
    return redact_secret(f"Raider.IO run detail fetch failed: {error}")


def run_detail_key(run):
    return f"{str((run or {}).get('region') or raiderio_region()).lower()}:{safe_int((run or {}).get('runId'))}"


def fetch_run_detail(run, season_slug):
    run_id = safe_int((run or {}).get("runId"))
    if run_id <= 0:
        return {}
    return api_get("/mythic-plus/run-details", {"season": season_slug, "id": run_id})


def run_detail_talent_snapshots(detail):
    snapshots = {}
    for member in (detail or {}).get("roster") or []:
        if not isinstance(member, dict):
            continue
        character = simplify_character(member)
        key = character_key(character)
        if not key:
            continue
        character_payload = member.get("character") if isinstance(member.get("character"), dict) else {}
        talent = character_payload.get("talentLoadout") or member.get("talentLoadout") or {}
        if not isinstance(talent, dict):
            continue
        loadout = talent.get("loadout") if isinstance(talent.get("loadout"), list) else []
        if not loadout:
            continue
        snapshots[key] = {
            "loadoutSpecId": talent.get("specId") or talent.get("loadoutSpecId") or talent.get("loadout_spec_id") or "",
            "heroSubTreeId": talent.get("heroSubTreeId") or talent.get("hero_sub_tree_id") or "",
            "loadout": loadout,
            "source": "run_detail",
        }
    return snapshots


def merge_run_detail_talents(runs, detail_snapshots):
    if not detail_snapshots:
        return runs
    enriched = []
    for run in runs or []:
        run_copy = dict(run)
        roster = []
        for character in run.get("roster") or []:
            character_copy = dict(character)
            snapshot = detail_snapshots.get(run_detail_key(run), {}).get(character_key(character_copy))
            if snapshot:
                existing = character_copy.get("talentLoadout") if isinstance(character_copy.get("talentLoadout"), dict) else {}
                character_copy["talentLoadout"] = {
                    **existing,
                    **snapshot,
                    "rawImportCode": existing.get("rawImportCode") or snapshot.get("rawImportCode") or "",
                    "source": "run_detail",
                }
            roster.append(character_copy)
        run_copy["roster"] = roster
        enriched.append(run_copy)
    return enriched


def fetch_run_details_for_runs(
    runs,
    season_slug=None,
    deadline_at=0,
    stage_callback=None,
    stage_name="raiderio_run_details",
    limit=None,
    per_spec_limit=None,
    spread_by_spec=False,
    frontload_per_spec=0,
):
    season_slug = season_slug or raiderio_season_slug()
    candidate_limit = run_detail_limit() if limit is None else max(0, safe_int(limit))
    candidate_per_spec_limit = run_detail_limit_per_spec() if per_spec_limit is None else max(0, safe_int(per_spec_limit))
    candidates = select_run_detail_candidates(
        runs,
        limit=candidate_limit,
        per_spec_limit=candidate_per_spec_limit,
        spread_by_spec=spread_by_spec,
        frontload_per_spec=frontload_per_spec,
    )
    summary = {
        "requestedRunCount": len(candidates),
        "talentSnapshotCount": 0,
        "errors": [],
        "limit": candidate_limit,
        "limitPerSpec": candidate_per_spec_limit,
        "spreadBySpec": bool(spread_by_spec),
        "frontloadPerSpec": max(0, safe_int(frontload_per_spec)),
    }
    if not candidates:
        return runs, summary
    stage_started = emit_sync_stage(
        stage_callback,
        stage_name,
        "start",
        details={
            "candidateCount": len(candidates),
            "workers": min(run_detail_fetch_workers(), max(1, len(candidates))),
        },
    )
    details_by_run = {}
    errors = []
    workers = min(run_detail_fetch_workers(), len(candidates))
    if workers <= 1:
        for run in candidates:
            if sync_deadline_expired(deadline_at):
                errors.append(RAIDERIO_DEADLINE_ERROR)
                break
            try:
                detail = fetch_run_detail(run, season_slug)
                details_by_run[run_detail_key(run)] = run_detail_talent_snapshots(detail)
            except (RaiderIOError, TimeoutError, OSError) as error:
                errors.append(run_detail_error_message(error))
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_runs = {
                executor.submit(fetch_run_detail, run, season_slug): run
                for run in candidates
                if not sync_deadline_expired(deadline_at)
            }
            if len(future_runs) < len(candidates) and RAIDERIO_DEADLINE_ERROR not in errors:
                errors.append(RAIDERIO_DEADLINE_ERROR)
            for future in as_completed(future_runs):
                run = future_runs[future]
                try:
                    detail = future.result()
                    details_by_run[run_detail_key(run)] = run_detail_talent_snapshots(detail)
                except (RaiderIOError, TimeoutError, OSError) as error:
                    errors.append(run_detail_error_message(error))
    summary["errors"] = errors
    summary["talentSnapshotCount"] = sum(len(snapshots or {}) for snapshots in details_by_run.values())
    enriched_runs = merge_run_detail_talents(runs, details_by_run)
    emit_sync_stage(
        stage_callback,
        stage_name,
        "complete",
        stage_started,
        {
            "requestedRunCount": summary["requestedRunCount"],
            "talentSnapshotCount": summary["talentSnapshotCount"],
            "errors": len(errors),
        },
    )
    return enriched_runs, summary


def fetch_profiles_for_runs(runs, target_item_ids=None, deadline_at=0, stage_callback=None):
    unique = select_profile_candidates_for_runs(runs)
    ranking_evidence_by_character = ranking_evidence_by_character_from_runs(runs)

    profiles = {}
    errors = []
    fields = "gear,talents,mythic_plus_recent_runs,mythic_plus_best_runs,mythic_plus_scores_by_season"
    if sync_deadline_expired(deadline_at):
        errors.append(RAIDERIO_DEADLINE_ERROR)
    else:
        base_stage_started = emit_sync_stage(
            stage_callback,
            "raiderio_base_profiles",
            "start",
            details={"candidateCount": len(unique), "workers": min(profile_fetch_workers(), max(1, len(unique)))},
        )
        summaries, batch_errors = fetch_profile_batch(unique, fields)
        errors.extend(batch_errors)
        for summary in summaries:
            ranking_evidence = ranking_evidence_by_character.get(character_key(summary))
            if ranking_evidence:
                summary["rankingEvidence"] = ranking_evidence
            profiles[character_key(summary)] = summary
        emit_sync_stage(
            stage_callback,
            "raiderio_base_profiles",
            "complete",
            base_stage_started,
            {"profileCount": len(profiles), "errors": len(batch_errors)},
        )
    targets = [str(item_id) for item_id in target_item_ids or [] if str(item_id or "").strip()]
    if targets and target_profile_limit():
        requested = {character_key(character) for character in unique}
        matched = set(target_item_coverage(profiles, targets)["matchedTargetItemIds"])
        target_set = set(targets)
        extra_candidates = []
        for character in unique_profile_candidates_for_runs(runs):
            key = character_key(character)
            if key in requested:
                continue
            requested.add(key)
            extra_candidates.append(character)
            if len(extra_candidates) >= target_profile_limit():
                break
        workers = profile_fetch_workers()
        target_stage_started = emit_sync_stage(
            stage_callback,
            "raiderio_target_profiles",
            "start",
            details={
                "candidateCount": len(extra_candidates),
                "targetItemCount": len(targets),
                "matchedTargetItemCount": len(matched),
                "workers": workers,
            },
        )
        for index in range(0, len(extra_candidates), workers):
            if matched >= target_set:
                break
            if sync_deadline_expired(deadline_at):
                if RAIDERIO_DEADLINE_ERROR not in errors:
                    errors.append(RAIDERIO_DEADLINE_ERROR)
                break
            batch = extra_candidates[index:index + workers]
            batch_stage_started = emit_sync_stage(
                stage_callback,
                "raiderio_target_profile_batch",
                "start",
                details={
                    "offset": index,
                    "batchSize": len(batch),
                    "matchedTargetItemCount": len(matched),
                },
            )
            summaries, batch_errors = fetch_profile_batch(batch, fields)
            errors.extend(batch_errors)
            for summary in summaries:
                ranking_evidence = ranking_evidence_by_character.get(character_key(summary))
                if ranking_evidence:
                    summary["rankingEvidence"] = ranking_evidence
                profiles[character_key(summary)] = summary
                matched.update(item_id for item_id in profile_gear_item_ids(summary) if item_id in targets)
            emit_sync_stage(
                stage_callback,
                "raiderio_target_profile_batch",
                "complete",
                batch_stage_started,
                {
                    "offset": index,
                    "batchSize": len(batch),
                    "profileCount": len(profiles),
                    "matchedTargetItemCount": len(matched),
                    "errors": len(batch_errors),
                },
            )
        emit_sync_stage(
            stage_callback,
            "raiderio_target_profiles",
            "complete",
            target_stage_started,
            {
                "profileCount": len(profiles),
                "matchedTargetItemCount": len(matched),
                "targetItemCount": len(targets),
                "errors": len(errors),
            },
        )
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
                "region": run.get("region") or character.get("region") or "",
                "dungeonName": run.get("dungeonName"),
                "mythicLevel": run.get("mythicLevel"),
                "score": run.get("score"),
                "completedAt": run.get("completedAt"),
                "sourceUrl": run.get("sourceUrl"),
            })
            profile = profiles.get(character_key(character))
            run_talent = character.get("talentLoadout") if isinstance(character.get("talentLoadout"), dict) else {}
            if run_talent.get("loadout"):
                blocker = talent_loadout_spec_blocker(class_key, spec_key, run_talent)
                blockers = [blocker] if blocker else []
                aggregate["talentLoadouts"].append({
                    **run_talent,
                    "characterName": character.get("name"),
                    "realmSlug": character.get("realmSlug"),
                    "region": character.get("region") or run.get("region") or "",
                    "profileUrl": character.get("profileUrl") or (
                        f"https://raider.io/characters/{character.get('region') or raiderio_region()}/{character.get('realmSlug')}/{character.get('name')}"
                        if character.get("realmSlug") and character.get("name")
                        else ""
                    ),
                    "maxKeyLevel": run.get("mythicLevel"),
                    **({"status": "blocked", "blockers": blockers, "errors": blockers} if blockers else {}),
                })
            elif profile:
                talent = profile.get("talentLoadout") or {}
                if talent.get("rawImportCode"):
                    blocker = talent_loadout_spec_blocker(class_key, spec_key, talent)
                    blockers = [blocker] if blocker else []
                    aggregate["talentLoadouts"].append({
                        **talent,
                        "source": talent.get("source") or "profile_current",
                        "characterName": profile.get("name"),
                        "realmSlug": profile.get("realmSlug"),
                        "region": profile.get("region") or character.get("region") or run.get("region") or "",
                        "profileUrl": profile.get("profileUrl"),
                        "maxKeyLevel": run.get("mythicLevel"),
                        **({"status": "blocked", "blockers": blockers, "errors": blockers} if blockers else {}),
                    })
                if profile.get("gear"):
                    observed_profile = {
                        "characterName": profile.get("name"),
                        "realmSlug": profile.get("realmSlug"),
                        "region": profile.get("region") or character.get("region") or run.get("region") or "",
                        "profileUrl": profile.get("profileUrl"),
                        "maxKeyLevel": run.get("mythicLevel"),
                        "rankingEvidence": profile.get("rankingEvidence") or run_ranking_evidence(run, character),
                        "gear": profile.get("gear"),
                    }
                    if profile.get("raceKey"):
                        observed_profile["raceKey"] = profile["raceKey"]
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
            signature_source = talent_loadout_signature_source(loadout)
            character = f"{loadout.get('characterName') or ''}:{loadout.get('realmSlug') or ''}".lower()
            dedupe_key = f"{character}:{signature_source}"
            if not signature_source or dedupe_key in seen_loadouts:
                continue
            seen_loadouts.add(dedupe_key)
            unique_loadouts.append(loadout)
        aggregate["talentLoadouts"] = select_talent_loadouts_for_spec(unique_loadouts, talent_loadout_limit_per_spec())
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


def talent_loadout_signature_source(loadout):
    loadout = loadout if isinstance(loadout, dict) else {}
    code = loadout.get("rawImportCode") or ""
    structured_loadout = loadout.get("loadout") if isinstance(loadout.get("loadout"), list) else []
    hero_subtree_id = loadout.get("heroSubTreeId") or loadout.get("hero_sub_tree_id") or ""
    if structured_loadout and (loadout.get("source") == "run_detail" or hero_subtree_id):
        return json.dumps(
            {
                "loadoutSpecId": loadout.get("loadoutSpecId") or "",
                "heroSubTreeId": hero_subtree_id,
                "loadout": structured_loadout,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    if code:
        return code
    if structured_loadout:
        return json.dumps(
            {
                "loadoutSpecId": loadout.get("loadoutSpecId") or "",
                "heroSubTreeId": hero_subtree_id,
                "loadout": structured_loadout,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    return ""


def select_talent_loadouts_for_spec(loadouts, limit):
    loadouts = list(loadouts or [])
    limit = max(1, safe_int(limit, 1))
    if len(loadouts) <= limit:
        return loadouts
    selected_indexes = set()
    seen_hero_subtrees = set()
    for index, loadout in enumerate(loadouts):
        hero_subtree_id = str((loadout or {}).get("heroSubTreeId") or (loadout or {}).get("hero_sub_tree_id") or "").strip()
        if not hero_subtree_id or hero_subtree_id in seen_hero_subtrees:
            continue
        seen_hero_subtrees.add(hero_subtree_id)
        selected_indexes.add(index)
        if len(selected_indexes) >= limit:
            break
    for index in range(len(loadouts)):
        if len(selected_indexes) >= limit:
            break
        selected_indexes.add(index)
    return [loadouts[index] for index in sorted(selected_indexes)]


def build_community_templates(aggregates, checked_at):
    templates = []
    for aggregate in aggregates:
        for index, loadout in enumerate(aggregate.get("talentLoadouts") or []):
            raw_code = loadout.get("rawImportCode") or ""
            structured_loadout = loadout.get("loadout") if isinstance(loadout.get("loadout"), list) else []
            if not raw_code and not structured_loadout:
                continue
            player_id = str(loadout.get("characterName") or f"player-{index + 1}").strip()
            player_slug = slugify(player_id, f"player-{index + 1}")
            signature_source = talent_loadout_signature_source(loadout)
            code_hash = hashlib.sha1(signature_source.encode("utf-8")).hexdigest()[:8]
            spec_label = aggregate.get("fullName") or f"{aggregate.get('specKey')} {aggregate.get('classKey')}"
            blockers = [str(item) for item in (loadout.get("blockers") or loadout.get("errors") or []) if str(item or "").strip()]
            if blockers:
                continue
            status = loadout.get("status") or "verified"
            payload = {
                "raiderio": {
                    "characterName": loadout.get("characterName") or "",
                    "realmSlug": loadout.get("realmSlug") or "",
                    "region": loadout.get("region") or "",
                    "profileUrl": loadout.get("profileUrl") or "",
                    "loadoutSpecId": loadout.get("loadoutSpecId") or "",
                    "heroSubTreeId": loadout.get("heroSubTreeId") or "",
                    "heroKey": loadout.get("heroKey") or "",
                    "selector": loadout.get("selector") or {},
                    "source": loadout.get("source") or "profile_current",
                    "loadout": structured_loadout,
                }
            }
            templates.append({
                "id": f"raiderio-{aggregate.get('classKey')}-{aggregate.get('specKey')}-{player_slug}-{code_hash}",
                "classKey": aggregate.get("classKey"),
                "specKey": aggregate.get("specKey"),
                "heroKey": loadout.get("heroKey") or "",
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
                "status": status,
                "payload": payload,
                "updatedAt": checked_at,
            })
    return templates[:community_template_limit()]


def optional_api_get(path, params, errors):
    try:
        return api_get(path, params)
    except RaiderIOError as error:
        errors.append(str(error))
        return {}


def sync_raiderio_cache(conn, force=False, stage_callback=None):
    ensure_raiderio_tables(conn)
    sync_stage_started = emit_sync_stage(stage_callback, "raiderio_sync", "start")
    checked_at = utc_now_iso()
    regions = raiderio_regions()
    primary_region = regions[0]
    season_slug = raiderio_season_slug()
    errors = []
    rankings = []
    leaderboard_url = ""
    leaderboard_urls = {}
    region_summaries = {}
    pages = max(0, int_env("WOW_RAIDERIO_RUN_PAGES", 8))
    target_item_ids = raiderio_target_item_ids(conn)
    deadline_at = sync_deadline_at()
    runs_stage_started = emit_sync_stage(
        stage_callback,
        "raiderio_runs",
        "start",
        details={"pages": pages, "regions": regions, "targetItemCount": len(target_item_ids)},
    )
    fetched_pages = 0
    for region in regions:
        region_rankings = []
        region_pages = 0
        for page in range(pages):
            if sync_deadline_expired(deadline_at):
                errors.append(RAIDERIO_DEADLINE_ERROR)
                break
            response = api_get("/mythic-plus/runs", {
                "season": season_slug,
                "region": region,
                "dungeon": "all",
                "page": page,
            })
            region_leaderboard_url = response.get("leaderboard_url") or leaderboard_url
            if region_leaderboard_url:
                leaderboard_url = leaderboard_url or region_leaderboard_url
                leaderboard_urls[region] = region_leaderboard_url
            page_rankings = response.get("rankings") or []
            if not isinstance(page_rankings, list):
                page_rankings = []
            for ranking in page_rankings:
                if isinstance(ranking, dict):
                    ranking = dict(ranking)
                    ranking["_rioRegion"] = region
                region_rankings.append(ranking)
                rankings.append(ranking)
            region_pages += 1
            fetched_pages += 1
            runs_preview = [
                simplify_run(item, leaderboard_urls.get(str(item.get("_rioRegion") or region), leaderboard_url), region=item.get("_rioRegion") or region)
                for item in rankings
                if isinstance(item, dict)
            ]
            coverage_preview = spec_coverage_from_runs([run for run in runs_preview if run.get("roster")])
            if (
                not target_item_ids
                and coverage_preview.get("totalSpecCount")
                and coverage_preview.get("coveredSpecCount") >= coverage_preview.get("totalSpecCount")
            ):
                break
            if len(page_rankings) < 20:
                break
        region_runs = [
            simplify_run(item, leaderboard_urls.get(region) or leaderboard_url, region=region)
            for item in region_rankings
            if isinstance(item, dict)
        ]
        region_runs = [run for run in region_runs if run.get("roster")]
        region_summaries[region] = {
            "pagesFetched": region_pages,
            "rankingCount": len(region_rankings),
            "runCount": len(region_runs),
            "specCoverage": spec_coverage_from_runs(region_runs),
        }
        if sync_deadline_expired(deadline_at):
            break

    runs = [
        simplify_run(item, leaderboard_urls.get(str(item.get("_rioRegion") or "")) or leaderboard_url, region=item.get("_rioRegion"))
        for item in rankings
        if isinstance(item, dict)
    ]
    runs = [run for run in runs if run.get("roster")]
    emit_sync_stage(
        stage_callback,
        "raiderio_runs",
        "complete",
        runs_stage_started,
        {
            "pagesFetched": fetched_pages,
            "regions": regions,
            "regionCount": len(regions),
            "rankingCount": len(rankings),
            "runCount": len(runs),
            "errors": len(errors),
        },
    )
    spec_ranking_runs, spec_ranking_summary = fetch_spec_ranking_runs(
        expected_spec_pairs(),
        season_slug=season_slug,
        deadline_at=deadline_at,
        stage_callback=stage_callback,
    )
    errors.extend((spec_ranking_summary.get("errors") or [])[:8])
    runs = merge_runs_by_region_id([*runs, *spec_ranking_runs])
    runs, run_detail_summary = fetch_run_details_for_runs(
        runs,
        season_slug=season_slug,
        deadline_at=deadline_at,
        stage_callback=stage_callback,
    )
    errors.extend((run_detail_summary.get("errors") or [])[:8])
    gap_fill_specs = specs_needing_hero_gap_fill(runs, expected_spec_pairs())
    if gap_fill_specs and not sync_deadline_expired(deadline_at):
        gap_runs, gap_summary = fetch_spec_ranking_runs(
            gap_fill_specs,
            season_slug=season_slug,
            deadline_at=deadline_at,
            stage_callback=stage_callback,
            regions=spec_ranking_gap_fill_regions(),
            pages=spec_ranking_gap_fill_pages(),
            page_size=spec_ranking_gap_fill_page_size(),
            runs_per_character=spec_ranking_gap_fill_runs_per_character(),
            start_page=spec_ranking_pages(),
            stage_name="raiderio_spec_ranking_gap_fill",
        )
        gap_runs, gap_run_detail_summary = fetch_run_details_for_runs(
            gap_runs,
            season_slug=season_slug,
            deadline_at=deadline_at,
            stage_callback=stage_callback,
            stage_name="raiderio_gap_fill_run_details",
            limit=gap_fill_run_detail_limit(),
            per_spec_limit=gap_fill_run_detail_limit_per_spec(),
            spread_by_spec=True,
            frontload_per_spec=gap_fill_run_detail_frontload_per_spec(),
        )
        errors.extend((gap_summary.get("errors") or [])[:8])
        errors.extend((gap_run_detail_summary.get("errors") or [])[:8])
        runs = merge_runs_by_region_id([*runs, *gap_runs])
        spec_ranking_summary["gapFill"] = {key: value for key, value in gap_summary.items() if key != "errors"}
        spec_ranking_summary["requestCount"] = safe_int(spec_ranking_summary.get("requestCount")) + safe_int(gap_summary.get("requestCount"))
        spec_ranking_summary["characterCount"] = safe_int(spec_ranking_summary.get("characterCount")) + safe_int(gap_summary.get("characterCount"))
        spec_ranking_summary["runCount"] = safe_int(spec_ranking_summary.get("runCount")) + safe_int(gap_summary.get("runCount"))
        run_detail_summary = combine_run_detail_summaries(run_detail_summary, gap_run_detail_summary)
        extra_gap_summaries = []
        extra_gap_run_detail_summaries = []
        for extra_start_page in spec_ranking_gap_fill_extra_start_pages():
            extra_gap_fill_specs = specs_needing_hero_gap_fill(runs, expected_spec_pairs())
            if not extra_gap_fill_specs or sync_deadline_expired(deadline_at):
                break
            extra_gap_runs, extra_gap_summary = fetch_spec_ranking_runs(
                extra_gap_fill_specs,
                season_slug=season_slug,
                deadline_at=deadline_at,
                stage_callback=stage_callback,
                regions=spec_ranking_gap_fill_regions(),
                pages=spec_ranking_gap_fill_pages(),
                page_size=spec_ranking_gap_fill_page_size(),
                runs_per_character=spec_ranking_gap_fill_runs_per_character(),
                start_page=extra_start_page,
                stage_name="raiderio_spec_ranking_gap_fill_extra",
            )
            extra_gap_runs, extra_gap_run_detail_summary = fetch_run_details_for_runs(
                extra_gap_runs,
                season_slug=season_slug,
                deadline_at=deadline_at,
                stage_callback=stage_callback,
                stage_name="raiderio_gap_fill_run_details_extra",
                limit=gap_fill_run_detail_limit(),
                per_spec_limit=gap_fill_run_detail_limit_per_spec(),
                spread_by_spec=True,
                frontload_per_spec=gap_fill_run_detail_frontload_per_spec(),
            )
            errors.extend((extra_gap_summary.get("errors") or [])[:8])
            errors.extend((extra_gap_run_detail_summary.get("errors") or [])[:8])
            runs = merge_runs_by_region_id([*runs, *extra_gap_runs])
            extra_gap_summaries.append({key: value for key, value in extra_gap_summary.items() if key != "errors"})
            extra_gap_run_detail_summaries.append({
                key: value for key, value in extra_gap_run_detail_summary.items() if key != "errors"
            })
            spec_ranking_summary["requestCount"] = safe_int(spec_ranking_summary.get("requestCount")) + safe_int(extra_gap_summary.get("requestCount"))
            spec_ranking_summary["characterCount"] = safe_int(spec_ranking_summary.get("characterCount")) + safe_int(extra_gap_summary.get("characterCount"))
            spec_ranking_summary["runCount"] = safe_int(spec_ranking_summary.get("runCount")) + safe_int(extra_gap_summary.get("runCount"))
            run_detail_summary["requestedRunCount"] = safe_int(run_detail_summary.get("requestedRunCount")) + safe_int(extra_gap_run_detail_summary.get("requestedRunCount"))
            run_detail_summary["talentSnapshotCount"] = safe_int(run_detail_summary.get("talentSnapshotCount")) + safe_int(extra_gap_run_detail_summary.get("talentSnapshotCount"))
            run_detail_summary["errors"] = [
                *(run_detail_summary.get("errors") or []),
                *(extra_gap_run_detail_summary.get("errors") or []),
            ]
        if extra_gap_summaries:
            spec_ranking_summary["extraGapFill"] = extra_gap_summaries
        if extra_gap_run_detail_summaries:
            run_detail_summary["extraGapFill"] = extra_gap_run_detail_summaries
    spec_ranking_summary["heroSubTreeCoverage"] = hero_subtree_coverage_from_runs(runs)
    spec_coverage = spec_coverage_from_runs(runs)
    profiles, profile_errors = fetch_profiles_for_runs(
        runs,
        target_item_ids=target_item_ids,
        deadline_at=deadline_at,
        stage_callback=stage_callback,
    )
    errors.extend(profile_errors[:8])
    if sync_deadline_expired(deadline_at):
        if RAIDERIO_DEADLINE_ERROR not in errors:
            errors.append(RAIDERIO_DEADLINE_ERROR)
        static_data = {}
        affixes = {}
        cutoffs = {}
    else:
        static_stage_started = emit_sync_stage(stage_callback, "raiderio_static", "start")
        static_data = optional_api_get(
            "/mythic-plus/static-data",
            {"expansion_id": os.environ.get("WOW_RAIDERIO_EXPANSION_ID", DEFAULT_EXPANSION_ID)},
            errors,
        )
        affixes = optional_api_get("/mythic-plus/affixes", {"region": primary_region, "locale": raiderio_locale()}, errors)
        cutoffs = optional_api_get("/mythic-plus/season-cutoffs", {"season": season_slug, "region": primary_region}, errors)
        emit_sync_stage(
            stage_callback,
            "raiderio_static",
            "complete",
            static_stage_started,
            {
                "hasStaticData": bool(static_data),
                "hasAffixes": bool(affixes),
                "hasCutoffs": bool(cutoffs),
                "errors": len(errors),
            },
        )
    aggregates = aggregate_runs(runs, profiles)
    community_templates = build_community_templates(aggregates, checked_at)
    target_matrix = build_target_spec_matrix(runs, profiles, community_templates, checked_at)
    source_status = "synced" if runs else "blocked"
    if runs and errors:
        source_status = "partial"
    payload = {
        "sourceName": RAIDERIO_SOURCE_NAME,
        "sourceStatus": source_status,
        "status": source_status,
        "region": primary_region,
        "regions": regions,
        "locale": raiderio_locale(),
        "seasonSlug": season_slug,
        "leaderboardUrl": leaderboard_url or "https://raider.io/mythic-plus-rankings",
        "leaderboardUrls": leaderboard_urls,
        "checkedAt": checked_at,
        "expiresAt": iso_after(int_env("WOW_RAIDERIO_TTL_HOURS", 6)),
        "staleAt": iso_after(int_env("WOW_RAIDERIO_STALE_HOURS", 48)),
        "staticExpiresAt": iso_after(int_env("WOW_RAIDERIO_STATIC_TTL_HOURS", 24)),
        "errors": errors[:12],
        "runCount": len(runs),
        "regionCoverage": region_summaries,
        "profileCount": len(profiles),
        "profileLimitPerSpec": max(1, int_env("WOW_RAIDERIO_PROFILE_LIMIT_PER_SPEC", 5)),
        "specRankingCoverage": {key: value for key, value in spec_ranking_summary.items() if key != "errors"},
        "runDetailCoverage": {key: value for key, value in run_detail_summary.items() if key != "errors"},
        "targetItemCoverage": target_item_coverage(profiles, target_item_ids),
        "targetMatrix": target_matrix,
        "specCoverage": spec_coverage,
        "runs": runs[:200],
        "profiles": list(profiles.values())[:profile_payload_limit()],
        "specAggregates": aggregates,
        "communityTemplates": community_templates,
        "staticData": static_data,
        "affixes": affixes,
        "cutoffs": cutoffs,
    }
    write_cache(conn, payload)
    emit_sync_stage(
        stage_callback,
        "raiderio_sync",
        "complete",
        sync_stage_started,
        {
            "sourceStatus": source_status,
            "runCount": len(runs),
            "profileCount": len(profiles),
            "errors": len(errors),
        },
    )
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
        "specRankingCoverage": {key: value for key, value in empty_spec_ranking_summary(False).items() if key != "errors"},
        "targetMatrix": build_target_spec_matrix([], {}, [], now),
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
    if allow_sync and (raiderio_api_key() or raiderio_public_fallback_enabled()):
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


def public_raiderio_summary(payload, aggregate=None, include_details=False):
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
        "sourceUrl": payload.get("leaderboardUrl") or "https://raider.io/mythic-plus-rankings",
    }
    if include_details:
        summary.update({
            "topRuns": [],
            "observedGear": [],
            "talentLoadouts": [],
        })
    if aggregate:
        summary.update({
            "sampleCount": aggregate.get("sampleCount") or 0,
            "maxKeyLevel": aggregate.get("maxKeyLevel") or 0,
            "bestScore": aggregate.get("bestScore") or 0,
        })
        if include_details:
            summary.update({
                "topRuns": aggregate.get("topRuns") or [],
                "observedGear": aggregate.get("observedGear") or [],
                "talentLoadouts": aggregate.get("talentLoadouts") or [],
            })
    return summary


def aggregate_for_specialization(payload, specialization):
    class_key = specialization.get("websimClassKey") or specialization.get("classKey") or ""
    spec_key = specialization.get("websimSpecKey") or specialization.get("specKey") or ""
    return aggregate_by_spec(payload).get(f"{class_key}:{spec_key}")


def enrich_build_specialization(specialization, payload, include_details=False):
    aggregate = aggregate_for_specialization(payload, specialization)
    summary = public_raiderio_summary(payload, aggregate, include_details=include_details)
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

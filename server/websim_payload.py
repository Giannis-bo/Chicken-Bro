#!/usr/bin/env python3
import base64
import hashlib
import json
import os
import re
import sqlite3
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DEFAULT_REGION = os.environ.get("WOW_BLIZZARD_REGION", "us").strip() or "us"
DEFAULT_LOCALE = os.environ.get("WOW_BLIZZARD_LOCALE", "zh_CN").strip() or "zh_CN"
DEFAULT_LOCALE_FALLBACKS = [
    item.strip()
    for item in os.environ.get("WOW_BLIZZARD_LOCALES", "zh_CN,zh_TW,en_US").split(",")
    if item.strip()
]
DEFAULT_SIMC_ROOT = Path(os.environ.get("WOW_SIMC_ROOT", "/opt/wow-simc"))
DEFAULT_SIMC_VERSION_FILE = Path(os.environ.get("WOW_SIMC_VERSION_FILE", "/var/lib/wow-backend/simc-version.json"))
SEASON_TTL_HOURS = int(os.environ.get("WOW_SEASON_TTL_HOURS", "24"))
MIDNIGHT_SEASON_ONE_DUNGEONS = [
    "Magisters' Terrace",
    "Maisara Caverns",
    "Nexus-Point Xenas",
    "Windrunner Spire",
    "Algeth'ar Academy",
    "Pit of Saron",
    "Seat of the Triumvirate",
    "Skyreach",
]
MIDNIGHT_SEASON_ONE_DUNGEON_IDS = ["558", "560", "559", "557", "402", "556", "239", "161"]
STALE_SEASON_DUNGEON_MARKERS = [
    "ara-kara",
    "arakara",
    "echoing city",
    "city of echoes",
    "艾拉",
    "回响之城",
]
OFFICIAL_SEASON_SOURCE_REFS = [
    {
        "name": "Blizzard News",
        "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
        "note": "Official Midnight Season 1 Mythic+ dungeon rotation.",
    },
    {
        "name": "Battle.net Game Data API",
        "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
        "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data.",
    },
]


WOW_CLASSES = [
    {"key": "deathknight", "label": "Death Knight", "specs": ["blood", "frost", "unholy"]},
    {"key": "demonhunter", "label": "Demon Hunter", "specs": ["havoc", "vengeance"]},
    {"key": "druid", "label": "Druid", "specs": ["balance", "feral", "guardian", "restoration"]},
    {"key": "evoker", "label": "Evoker", "specs": ["devastation", "preservation", "augmentation"]},
    {"key": "hunter", "label": "Hunter", "specs": ["beast_mastery", "marksmanship", "survival"]},
    {"key": "mage", "label": "Mage", "specs": ["arcane", "fire", "frost"]},
    {"key": "monk", "label": "Monk", "specs": ["brewmaster", "mistweaver", "windwalker"]},
    {"key": "paladin", "label": "Paladin", "specs": ["holy", "protection", "retribution"]},
    {"key": "priest", "label": "Priest", "specs": ["discipline", "holy", "shadow"]},
    {"key": "rogue", "label": "Rogue", "specs": ["assassination", "outlaw", "subtlety"]},
    {"key": "shaman", "label": "Shaman", "specs": ["elemental", "enhancement", "restoration"]},
    {"key": "warlock", "label": "Warlock", "specs": ["affliction", "demonology", "destruction"]},
    {"key": "warrior", "label": "Warrior", "specs": ["arms", "fury", "protection"]},
]

SPEC_LABELS = {
    "arcane": "Arcane",
    "fire": "Fire",
    "frost": "Frost",
    "holy": "Holy",
    "protection": "Protection",
    "retribution": "Retribution",
    "elemental": "Elemental",
    "enhancement": "Enhancement",
    "restoration": "Restoration",
    "arms": "Arms",
    "fury": "Fury",
    "blood": "Blood",
    "unholy": "Unholy",
    "havoc": "Havoc",
    "vengeance": "Vengeance",
    "balance": "Balance",
    "feral": "Feral",
    "guardian": "Guardian",
    "devastation": "Devastation",
    "preservation": "Preservation",
    "augmentation": "Augmentation",
    "beast_mastery": "Beast Mastery",
    "marksmanship": "Marksmanship",
    "survival": "Survival",
    "brewmaster": "Brewmaster",
    "mistweaver": "Mistweaver",
    "windwalker": "Windwalker",
    "discipline": "Discipline",
    "shadow": "Shadow",
    "assassination": "Assassination",
    "outlaw": "Outlaw",
    "subtlety": "Subtlety",
    "affliction": "Affliction",
    "demonology": "Demonology",
    "destruction": "Destruction",
}

CLASS_LABELS_ZH = {
    "deathknight": "死亡骑士",
    "demonhunter": "恶魔猎手",
    "druid": "德鲁伊",
    "evoker": "唤魔师",
    "hunter": "猎人",
    "mage": "法师",
    "monk": "武僧",
    "paladin": "圣骑士",
    "priest": "牧师",
    "rogue": "潜行者",
    "shaman": "萨满祭司",
    "warlock": "术士",
    "warrior": "战士",
}

SPEC_LABELS_ZH = {
    "arcane": "奥术",
    "fire": "火焰",
    "frost": "冰霜",
    "holy": "神圣",
    "protection": "防护",
    "retribution": "惩戒",
    "elemental": "元素",
    "enhancement": "增强",
    "restoration": "恢复",
    "arms": "武器",
    "fury": "狂怒",
    "blood": "鲜血",
    "unholy": "邪恶",
    "havoc": "浩劫",
    "vengeance": "复仇",
    "balance": "平衡",
    "feral": "野性",
    "guardian": "守护",
    "devastation": "湮灭",
    "preservation": "恩护",
    "augmentation": "增辉",
    "beast_mastery": "野兽控制",
    "marksmanship": "射击",
    "survival": "生存",
    "brewmaster": "酒仙",
    "mistweaver": "织雾",
    "windwalker": "踏风",
    "discipline": "戒律",
    "shadow": "暗影",
    "assassination": "奇袭",
    "outlaw": "狂徒",
    "subtlety": "敏锐",
    "affliction": "痛苦",
    "demonology": "恶魔学识",
    "destruction": "毁灭",
}

GAME_CLASS_ID_TO_KEY = {
    1: "warrior",
    2: "paladin",
    3: "hunter",
    4: "rogue",
    5: "priest",
    6: "deathknight",
    7: "shaman",
    8: "mage",
    9: "warlock",
    10: "monk",
    11: "druid",
    12: "demonhunter",
    13: "evoker",
}

SPEC_ID_TO_KEY = {
    62: ("mage", "arcane"),
    63: ("mage", "fire"),
    64: ("mage", "frost"),
    65: ("paladin", "holy"),
    66: ("paladin", "protection"),
    70: ("paladin", "retribution"),
    71: ("warrior", "arms"),
    72: ("warrior", "fury"),
    73: ("warrior", "protection"),
    102: ("druid", "balance"),
    103: ("druid", "feral"),
    104: ("druid", "guardian"),
    105: ("druid", "restoration"),
    250: ("deathknight", "blood"),
    251: ("deathknight", "frost"),
    252: ("deathknight", "unholy"),
    253: ("hunter", "beast_mastery"),
    254: ("hunter", "marksmanship"),
    255: ("hunter", "survival"),
    256: ("priest", "discipline"),
    257: ("priest", "holy"),
    258: ("priest", "shadow"),
    259: ("rogue", "assassination"),
    260: ("rogue", "outlaw"),
    261: ("rogue", "subtlety"),
    262: ("shaman", "elemental"),
    263: ("shaman", "enhancement"),
    264: ("shaman", "restoration"),
    265: ("warlock", "affliction"),
    266: ("warlock", "demonology"),
    267: ("warlock", "destruction"),
    268: ("monk", "brewmaster"),
    269: ("monk", "windwalker"),
    270: ("monk", "mistweaver"),
    577: ("demonhunter", "havoc"),
    581: ("demonhunter", "vengeance"),
    1467: ("evoker", "devastation"),
    1468: ("evoker", "preservation"),
    1473: ("evoker", "augmentation"),
}

DEFAULT_RACE_BY_CLASS = {
    "deathknight": "orc",
    "demonhunter": "blood_elf",
    "druid": "night_elf",
    "evoker": "dracthyr",
    "hunter": "orc",
    "mage": "troll",
    "monk": "pandaren",
    "paladin": "human",
    "priest": "void_elf",
    "rogue": "blood_elf",
    "shaman": "tauren",
    "warlock": "orc",
    "warrior": "orc",
}

GEAR_SLOTS = [
    "head",
    "neck",
    "shoulder",
    "back",
    "chest",
    "wrists",
    "hands",
    "waist",
    "legs",
    "feet",
    "finger1",
    "finger2",
    "trinket1",
    "trinket2",
    "main_hand",
    "off_hand",
]

SCENARIOS = [
    {"key": "single", "title": "单体", "fightStyle": "Patchwerk", "targets": 1, "durationSeconds": 300},
    {"key": "mythic_plus", "title": "大秘境", "fightStyle": "DungeonSlice", "targets": 5, "durationSeconds": 360},
    {"key": "cleave", "title": "顺劈", "fightStyle": "HecticAddCleave", "targets": 3, "durationSeconds": 300},
]

FALLBACK_LOOT = [
    {
        "instanceId": "fallback-azj-kahet",
        "instanceName": "Eco-Dome Al'dani",
        "encounterId": "fallback-chimaerus",
        "encounterName": "Chimaerus",
        "itemId": 249343,
        "name": "Gaze of the Alnseer",
        "slot": "trinket1",
        "quality": "Epic",
        "iconUrl": "https://render.worldofwarcraft.com/us/icons/56/inv_misc_eye_04.jpg",
    },
    {
        "instanceId": "fallback-azj-kahet",
        "instanceName": "Eco-Dome Al'dani",
        "encounterId": "fallback-vaelgor",
        "encounterName": "Vaelgor",
        "itemId": 249346,
        "name": "Vaelgor's Final Stare",
        "slot": "trinket2",
        "quality": "Epic",
        "iconUrl": "https://render.worldofwarcraft.com/us/icons/56/inv_misc_orb_05.jpg",
    },
    {
        "instanceId": "fallback-silvermoon",
        "instanceName": "Voidscarred Hold",
        "encounterId": "fallback-zuraal",
        "encounterName": "Zuraal the Ascended",
        "itemId": 258218,
        "name": "Skybreaker's Blade",
        "slot": "main_hand",
        "quality": "Epic",
        "iconUrl": "https://render.worldofwarcraft.com/us/icons/56/inv_sword_1h_artifactfelomelorn_d_06.jpg",
    },
]


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def int_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def slugify(value, fallback="item"):
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
    return text[:80] if text else fallback


def safe_json_loads(value, fallback=None):
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback if fallback is not None else {}


def ensure_websim_tables(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS websim_sync_state (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS websim_instances (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS websim_encounters (
            id TEXT PRIMARY KEY,
            instance_id TEXT NOT NULL,
            name TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS websim_items (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slot TEXT NOT NULL,
            quality TEXT NOT NULL,
            icon_url TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS websim_loot (
            id TEXT PRIMARY KEY,
            instance_id TEXT NOT NULL,
            encounter_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            name TEXT NOT NULL,
            slot TEXT NOT NULL,
            quality TEXT NOT NULL,
            icon_url TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS websim_talents (
            id TEXT PRIMARY KEY,
            class_key TEXT NOT NULL,
            spec_key TEXT NOT NULL,
            tree_id TEXT NOT NULL,
            row_index INTEGER NOT NULL,
            col_index INTEGER NOT NULL,
            spell_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS websim_profile_presets (
            id TEXT PRIMARY KEY,
            class_key TEXT NOT NULL,
            spec_key TEXT NOT NULL,
            name TEXT NOT NULL,
            profile TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS websim_season_state (
            key TEXT PRIMARY KEY,
            season_id TEXT NOT NULL,
            season_label TEXT NOT NULL,
            season_revision TEXT NOT NULL,
            locale TEXT NOT NULL,
            data_status TEXT NOT NULL,
            verified_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            source_refs_json TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS websim_season_dungeons (
            id TEXT PRIMARY KEY,
            season_id TEXT NOT NULL,
            season_revision TEXT NOT NULL,
            dungeon_id TEXT NOT NULL,
            instance_id TEXT NOT NULL,
            name TEXT NOT NULL,
            short_name TEXT NOT NULL,
            timer_seconds INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS websim_spell_details (
            id TEXT PRIMARY KEY,
            spell_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            icon_url TEXT NOT NULL,
            locale TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS websim_media_assets (
            id TEXT PRIMARY KEY,
            media_type TEXT NOT NULL,
            media_id TEXT NOT NULL,
            url TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS websim_translations (
            id TEXT PRIMARY KEY,
            source_locale TEXT NOT NULL,
            target_locale TEXT NOT NULL,
            source_text TEXT NOT NULL,
            translated_text TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def set_sync_state(conn, key, value):
    conn.execute(
        """
        INSERT INTO websim_sync_state (key, value_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value_json=excluded.value_json,
            updated_at=excluded.updated_at
        """,
        (key, json.dumps(value, ensure_ascii=False), utc_now()),
    )


def get_sync_state(conn, key):
    row = conn.execute("SELECT value_json, updated_at FROM websim_sync_state WHERE key = ?", (key,)).fetchone()
    if not row:
        return {}
    value = safe_json_loads(row[0], {})
    if isinstance(value, dict):
        value["updatedAt"] = row[1]
    return value


def season_expires_at(hours=SEASON_TTL_HOURS):
    return (datetime.now(timezone.utc) + timedelta(hours=max(1, hours))).isoformat(timespec="seconds")


def season_revision_for(season_id, locale, dungeons):
    names = "|".join(sorted(str(item.get("name") or "") for item in dungeons or []))
    digest = hashlib.sha256(f"{season_id}|{locale}|{names}".encode("utf-8")).hexdigest()[:12]
    return f"season-{season_id or 'unknown'}-{digest}"


def current_season_payload(
    season_id="midnight-season-1",
    season_label="至暗之夜 Season 1",
    locale=DEFAULT_LOCALE,
    dungeons=None,
    data_status="verified",
    verified_at=None,
    expires_at=None,
    source_refs=None,
    errors=None,
):
    rows = dungeons if isinstance(dungeons, list) else [
        {"id": slugify(name), "dungeonId": slugify(name), "instanceId": "", "name": name, "shortName": name, "timerSeconds": 0}
        for name in MIDNIGHT_SEASON_ONE_DUNGEONS
    ]
    revision = season_revision_for(season_id, locale, rows) if data_status == "verified" else "blocked"
    return {
        "id": str(season_id or ""),
        "seasonId": str(season_id or ""),
        "label": season_label,
        "seasonLabel": season_label,
        "revision": revision,
        "seasonRevision": revision,
        "verifiedAt": verified_at or utc_now(),
        "expiresAt": expires_at or season_expires_at(),
        "locale": locale,
        "dataStatus": data_status,
        "dungeons": rows,
        "sourceRefs": source_refs or OFFICIAL_SEASON_SOURCE_REFS,
        "errors": errors or [],
    }


def blocked_season_payload(errors=None):
    return current_season_payload(
        season_id="",
        season_label="赛季数据未验证",
        dungeons=[],
        data_status="blocked",
        verified_at="",
        expires_at="",
        errors=errors or ["赛季数据尚未通过暴雪官方 API 校验"],
    )


def season_metadata_fields(season):
    payload = season if isinstance(season, dict) else current_season_payload()
    return {
        "currentSeason": payload,
        "seasonId": payload.get("seasonId") or payload.get("id") or "",
        "seasonLabel": payload.get("seasonLabel") or payload.get("label") or "",
        "seasonRevision": payload.get("seasonRevision") or payload.get("revision") or "",
        "verifiedAt": payload.get("verifiedAt") or "",
        "expiresAt": payload.get("expiresAt") or "",
        "locale": payload.get("locale") or DEFAULT_LOCALE,
        "dataStatus": payload.get("dataStatus") or "blocked",
        "sourceRefs": payload.get("sourceRefs") or [],
    }


def get_active_season_payload(conn):
    ensure_websim_tables(conn)
    row = conn.execute(
        """
        SELECT season_id, season_label, season_revision, locale, data_status, verified_at,
               expires_at, source_refs_json, payload_json
        FROM websim_season_state
        WHERE key = 'active' AND active = 1 AND data_status = 'verified' AND expires_at > ?
        LIMIT 1
        """,
        (utc_now(),),
    ).fetchone()
    if not row:
        state = get_sync_state(conn, "websim_sync")
        errors = state.get("errors") if isinstance(state, dict) else []
        return blocked_season_payload(errors or ["websim cache has not been synced"])
    payload = safe_json_loads(row[8], {})
    if not isinstance(payload, dict) or not payload.get("seasonRevision"):
        payload = current_season_payload(
            season_id=row[0],
            season_label=row[1],
            locale=row[3],
            dungeons=[],
            data_status=row[4],
            verified_at=row[5],
            expires_at=row[6],
            source_refs=safe_json_loads(row[7], []),
        )
    payload["seasonId"] = row[0]
    payload["id"] = row[0]
    payload["seasonLabel"] = row[1]
    payload["label"] = row[1]
    payload["seasonRevision"] = row[2]
    payload["revision"] = row[2]
    payload["locale"] = row[3]
    payload["dataStatus"] = row[4]
    payload["verifiedAt"] = row[5]
    payload["expiresAt"] = row[6]
    payload["sourceRefs"] = safe_json_loads(row[7], [])
    dungeons = conn.execute(
        """
        SELECT dungeon_id, instance_id, name, short_name, timer_seconds, payload_json
        FROM websim_season_dungeons
        WHERE season_revision = ?
        ORDER BY name
        """,
        (row[2],),
    ).fetchall()
    payload["dungeons"] = [
        {
            "id": dungeon_row[0],
            "dungeonId": dungeon_row[0],
            "instanceId": dungeon_row[1],
            "name": dungeon_row[2],
            "shortName": dungeon_row[3],
            "timerSeconds": dungeon_row[4],
            "sourceRefs": payload["sourceRefs"],
            "payload": safe_json_loads(dungeon_row[5], {}),
        }
        for dungeon_row in dungeons
    ]
    return payload


def save_active_season_payload(conn, season):
    now = utc_now()
    source_refs_json = json.dumps(season.get("sourceRefs") or [], ensure_ascii=False)
    payload_json = json.dumps(season, ensure_ascii=False)
    conn.execute("UPDATE websim_season_state SET active = 0 WHERE active = 1")
    conn.execute(
        """
        INSERT INTO websim_season_state (
            key, season_id, season_label, season_revision, locale, data_status, verified_at,
            expires_at, source_refs_json, payload_json, active, updated_at
        ) VALUES ('active', ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        ON CONFLICT(key) DO UPDATE SET
            season_id=excluded.season_id,
            season_label=excluded.season_label,
            season_revision=excluded.season_revision,
            locale=excluded.locale,
            data_status=excluded.data_status,
            verified_at=excluded.verified_at,
            expires_at=excluded.expires_at,
            source_refs_json=excluded.source_refs_json,
            payload_json=excluded.payload_json,
            active=1,
            updated_at=excluded.updated_at
        """,
        (
            season.get("seasonId") or season.get("id") or "",
            season.get("seasonLabel") or season.get("label") or "",
            season.get("seasonRevision") or season.get("revision") or "",
            season.get("locale") or DEFAULT_LOCALE,
            season.get("dataStatus") or "blocked",
            season.get("verifiedAt") or now,
            season.get("expiresAt") or season_expires_at(),
            source_refs_json,
            payload_json,
            now,
        ),
    )
    conn.execute("DELETE FROM websim_season_dungeons WHERE season_revision = ?", (season.get("seasonRevision") or "",))
    for dungeon in season.get("dungeons") or []:
        dungeon_id = str(dungeon.get("dungeonId") or dungeon.get("id") or "")
        instance_id = str(dungeon.get("instanceId") or dungeon.get("journalInstanceId") or "")
        conn.execute(
            """
            INSERT INTO websim_season_dungeons (
                id, season_id, season_revision, dungeon_id, instance_id, name, short_name,
                timer_seconds, payload_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                season_id=excluded.season_id,
                season_revision=excluded.season_revision,
                dungeon_id=excluded.dungeon_id,
                instance_id=excluded.instance_id,
                name=excluded.name,
                short_name=excluded.short_name,
                timer_seconds=excluded.timer_seconds,
                payload_json=excluded.payload_json,
                updated_at=excluded.updated_at
            """,
            (
                f"{season.get('seasonRevision')}:{dungeon_id}",
                season.get("seasonId") or season.get("id") or "",
                season.get("seasonRevision") or season.get("revision") or "",
                dungeon_id,
                instance_id,
                dungeon.get("name") or f"Dungeon {dungeon_id}",
                dungeon.get("shortName") or dungeon.get("name") or f"Dungeon {dungeon_id}",
                int(dungeon.get("timerSeconds") or dungeon.get("timer_seconds") or 0),
                json.dumps(dungeon.get("payload") or dungeon, ensure_ascii=False),
                now,
            ),
        )


def blizzard_oauth_host(region):
    return "https://oauth.battle.net"


def blizzard_api_base(region):
    return f"https://{region}.api.blizzard.com"


def blizzard_namespace(region, namespace_type="static"):
    return f"{namespace_type}-{region}"


def get_blizzard_access_token(region=DEFAULT_REGION):
    client_id = os.environ.get("WOW_BLIZZARD_CLIENT_ID") or os.environ.get("WOW_BNET_CLIENT_ID")
    client_secret = os.environ.get("WOW_BLIZZARD_CLIENT_SECRET") or os.environ.get("WOW_BNET_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("missing Blizzard API credentials: set WOW_BLIZZARD_CLIENT_ID and WOW_BLIZZARD_CLIENT_SECRET")
    token = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    request = Request(
        f"{blizzard_oauth_host(region)}/token",
        data=urlencode({"grant_type": "client_credentials"}).encode("utf-8"),
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urlopen(request, timeout=int_env("WOW_BLIZZARD_TIMEOUT_SECONDS", 15)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError("Blizzard OAuth response did not include access_token")
    return access_token


def blizzard_get(path, token, region=DEFAULT_REGION, locale=DEFAULT_LOCALE, params=None, namespace=None):
    query = {
        "namespace": namespace or blizzard_namespace(region),
        "locale": locale,
    }
    query.update(params or {})
    url = f"{blizzard_api_base(region)}{path}?{urlencode(query)}"
    request = Request(url, headers={"Authorization": f"Bearer {token}"})
    with urlopen(request, timeout=int_env("WOW_BLIZZARD_TIMEOUT_SECONDS", 15)) as response:
        return json.loads(response.read().decode("utf-8"))


def list_keyed_values(payload, *keys):
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def extract_id_from_ref(value):
    if isinstance(value, dict):
        if value.get("id"):
            return str(value.get("id"))
        href = ((value.get("key") or {}).get("href") or value.get("href") or "")
    else:
        href = str(value or "")
    match = re.search(r"/(\d+)(?:\?|$)", href)
    return match.group(1) if match else ""


def item_slot_from_payload(payload):
    inventory_type = payload.get("inventory_type") or {}
    item_class = payload.get("item_class") or {}
    name = str(inventory_type.get("name") or item_class.get("name") or "").lower()
    mapping = [
        ("head", "head"),
        ("neck", "neck"),
        ("shoulder", "shoulder"),
        ("cloak", "back"),
        ("chest", "chest"),
        ("robe", "chest"),
        ("wrist", "wrists"),
        ("hand", "hands"),
        ("waist", "waist"),
        ("leg", "legs"),
        ("feet", "feet"),
        ("finger", "finger1"),
        ("trinket", "trinket1"),
        ("weapon", "main_hand"),
        ("held", "off_hand"),
        ("shield", "off_hand"),
        ("off", "off_hand"),
    ]
    for needle, slot in mapping:
        if needle in name:
            return slot
    return "main_hand" if "weapon" in str(item_class.get("name") or "").lower() else "trinket1"


def icon_url_from_media(media_payload):
    for asset in media_payload.get("assets", []) if isinstance(media_payload, dict) else []:
        value = asset.get("value")
        if value:
            return value
    return ""


def unique_locale_preferences(locale=DEFAULT_LOCALE):
    values = [locale, *DEFAULT_LOCALE_FALLBACKS, "en_US"]
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def blizzard_get_localized(path, token, region=DEFAULT_REGION, locale=DEFAULT_LOCALE, params=None, namespace=None):
    errors = []
    for locale_key in unique_locale_preferences(locale):
        try:
            return blizzard_get(path, token, region, locale_key, params=params, namespace=namespace), locale_key
        except Exception as error:
            errors.append(f"{locale_key}: {error}")
    raise RuntimeError("; ".join(errors))


def current_season_ref_from_index(payload):
    for key in ("current_season", "currentSeason", "current"):
        value = payload.get(key) if isinstance(payload, dict) else None
        if value:
            return value
    seasons = list_keyed_values(payload, "seasons")
    current = next((item for item in seasons if item.get("is_current") or item.get("current")), None)
    if current:
        return current
    candidates = [(int(extract_id_from_ref(item) or item.get("id") or 0), item) for item in seasons if isinstance(item, dict)]
    candidates = [item for item in candidates if item[0] > 0]
    if candidates:
        return sorted(candidates, key=lambda item: item[0])[-1][1]
    return {}


def mythic_dungeon_refs_from_season(payload):
    for key in ("dungeons", "mythic_keystone_dungeons", "keystone_dungeons", "season_dungeons"):
        refs = list_keyed_values(payload, key)
        if refs:
            return refs
    return []


def dungeon_id_from_ref(value):
    if isinstance(value, dict):
        for key in ("dungeon", "mythic_keystone_dungeon", "keystone_dungeon", "instance"):
            nested = value.get(key)
            nested_id = extract_id_from_ref(nested)
            if nested_id:
                return nested_id
    return extract_id_from_ref(value)


def normalize_name_key(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def official_dungeon_name_keys():
    return {normalize_name_key(name) for name in MIDNIGHT_SEASON_ONE_DUNGEONS}


def official_dungeon_ids():
    configured = [
        item.strip()
        for item in os.environ.get("WOW_WEBSIM_CURRENT_SEASON_DUNGEON_IDS", "").split(",")
        if item.strip()
    ]
    return configured or MIDNIGHT_SEASON_ONE_DUNGEON_IDS


def nested_ref(payload, *keys):
    for key in keys:
        value = payload.get(key) if isinstance(payload, dict) else None
        if value:
            return value
    return {}


def normalize_mythic_dungeon(dungeon_id, ref, detail, locale):
    instance_ref = nested_ref(detail, "journal_instance", "journalInstance", "instance", "dungeon", "zone", "map")
    instance_id = (
        str(detail.get("journal_instance_id") or detail.get("journalInstanceId") or "")
        or extract_id_from_ref(instance_ref)
        or str(detail.get("instance_id") or detail.get("instanceId") or "")
        or str(dungeon_id)
    )
    name = detail.get("name") or (ref.get("name") if isinstance(ref, dict) else "") or f"Dungeon {dungeon_id}"
    short_name = detail.get("short_name") or detail.get("shortName") or name
    timer_seconds = (
        detail.get("timer_seconds")
        or detail.get("timerSeconds")
        or detail.get("keystone_timer_seconds")
        or detail.get("keystoneTimerSeconds")
        or 0
    )
    return {
        "id": str(dungeon_id),
        "dungeonId": str(dungeon_id),
        "instanceId": str(instance_id),
        "name": name,
        "shortName": short_name,
        "timerSeconds": int(timer_seconds or 0),
        "locale": locale,
        "payload": detail,
        "sourceRefs": OFFICIAL_SEASON_SOURCE_REFS,
    }


def validate_current_season_dungeons(dungeons):
    if len(dungeons) != 8:
        raise RuntimeError(f"official season dungeon pool must contain 8 dungeons, got {len(dungeons)}")
    names = " | ".join(str(item.get("name") or "").lower() for item in dungeons)
    stale_markers = [marker for marker in STALE_SEASON_DUNGEON_MARKERS if marker.lower() in names]
    if stale_markers:
        raise RuntimeError(f"stale Mythic+ dungeon detected in current season pool: {', '.join(stale_markers)}")


def dedupe_dungeons_by_name(dungeons):
    seen = set()
    result = []
    for dungeon in dungeons or []:
        key = normalize_name_key(dungeon.get("name") or dungeon.get("shortName"))
        if not key:
            instance_id = str(dungeon.get("instanceId") or "").strip()
            if instance_id:
                key = f"instance:{instance_id}"
        if not key:
            key = str(dungeon.get("name") or dungeon.get("shortName") or dungeon.get("dungeonId") or "").casefold().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(dungeon)
    return result


def resolve_current_season_dungeons_from_index(token, region=DEFAULT_REGION, locale=DEFAULT_LOCALE):
    dynamic_namespace = blizzard_namespace(region, "dynamic")
    official_names = official_dungeon_name_keys()
    dungeons = []
    for dungeon_id in official_dungeon_ids():
        try:
            english_detail, _ = blizzard_get_localized(
                f"/data/wow/mythic-keystone/dungeon/{dungeon_id}",
                token,
                region,
                "en_US",
                namespace=dynamic_namespace,
            )
            if normalize_name_key(english_detail.get("name")) not in official_names:
                continue
            localized_detail, localized_locale = blizzard_get_localized(
                f"/data/wow/mythic-keystone/dungeon/{dungeon_id}",
                token,
                region,
                locale,
                namespace=dynamic_namespace,
            )
            dungeons.append(normalize_mythic_dungeon(dungeon_id, {}, localized_detail, localized_locale))
        except Exception:
            continue
    dungeons = dedupe_dungeons_by_name(dungeons)
    if len(dungeons) == 8:
        return dungeons

    index_payload, _ = blizzard_get_localized(
        "/data/wow/mythic-keystone/dungeon/index",
        token,
        region,
        "en_US",
        namespace=dynamic_namespace,
    )
    for dungeon_ref in list_keyed_values(index_payload, "dungeons"):
        dungeon_id = dungeon_id_from_ref(dungeon_ref)
        if not dungeon_id:
            continue
        try:
            english_detail, _ = blizzard_get_localized(
                f"/data/wow/mythic-keystone/dungeon/{dungeon_id}",
                token,
                region,
                "en_US",
                namespace=dynamic_namespace,
            )
        except Exception:
            continue
        ref_name = dungeon_ref.get("name") if isinstance(dungeon_ref, dict) else ""
        if normalize_name_key(english_detail.get("name") or ref_name) not in official_names:
            continue
        try:
            localized_detail, localized_locale = blizzard_get_localized(
                f"/data/wow/mythic-keystone/dungeon/{dungeon_id}",
                token,
                region,
                locale,
                namespace=dynamic_namespace,
            )
        except Exception:
            localized_detail, localized_locale = english_detail, "en_US"
        dungeons.append(normalize_mythic_dungeon(dungeon_id, dungeon_ref, localized_detail, localized_locale))
    return dedupe_dungeons_by_name(dungeons)


def resolve_current_mythic_season(token, region=DEFAULT_REGION, locale=DEFAULT_LOCALE):
    dynamic_namespace = blizzard_namespace(region, "dynamic")
    season_index, resolved_locale = blizzard_get_localized(
        "/data/wow/mythic-keystone/season/index",
        token,
        region,
        locale,
        namespace=dynamic_namespace,
    )
    season_ref = current_season_ref_from_index(season_index)
    season_id = extract_id_from_ref(season_ref) or str(season_ref.get("id") or "")
    if not season_id:
        raise RuntimeError("Blizzard Mythic Keystone season index did not expose a current season id")
    season_detail, resolved_locale = blizzard_get_localized(
        f"/data/wow/mythic-keystone/season/{season_id}",
        token,
        region,
        resolved_locale,
        namespace=dynamic_namespace,
    )
    dungeon_refs = mythic_dungeon_refs_from_season(season_detail)
    dungeons = []
    for dungeon_ref in dungeon_refs:
        dungeon_id = dungeon_id_from_ref(dungeon_ref)
        if not dungeon_id:
            continue
        dungeon_detail, dungeon_locale = blizzard_get_localized(
            f"/data/wow/mythic-keystone/dungeon/{dungeon_id}",
            token,
            region,
            resolved_locale,
            namespace=dynamic_namespace,
        )
        dungeons.append(normalize_mythic_dungeon(dungeon_id, dungeon_ref, dungeon_detail, dungeon_locale))
    dungeons = dedupe_dungeons_by_name(dungeons)
    if len(dungeons) != 8:
        dungeons = resolve_current_season_dungeons_from_index(token, region, resolved_locale)
    validate_current_season_dungeons(dungeons)
    label = (
        season_detail.get("name")
        or season_ref.get("name")
        or os.environ.get("WOW_WEBSIM_CURRENT_SEASON_LABEL")
        or "至暗之夜 Season 1"
    )
    payload = current_season_payload(
        season_id=season_id,
        season_label=label,
        locale=resolved_locale,
        dungeons=dungeons,
        data_status="verified",
        verified_at=utc_now(),
        expires_at=season_expires_at(),
        source_refs=OFFICIAL_SEASON_SOURCE_REFS,
    )
    payload["rawSeason"] = season_detail
    return payload


def selected_spell_ids_for_sync(conn, limit):
    if limit <= 0:
        return []
    priority_class = os.environ.get("WOW_WEBSIM_SYNC_PRIORITY_CLASS", "mage").strip()
    priority_spec = os.environ.get("WOW_WEBSIM_SYNC_PRIORITY_SPEC", "arcane").strip()
    spell_ids = []
    seen = set()

    def add_rows(rows):
        for row in rows:
            spell_id = int(row[0] or 0)
            if spell_id > 0 and spell_id not in seen:
                seen.add(spell_id)
                spell_ids.append(spell_id)
            if len(spell_ids) >= limit:
                break

    if priority_class and priority_spec:
        add_rows(
            conn.execute(
                """
                SELECT DISTINCT spell_id, row_index, col_index
                FROM websim_talents
                WHERE spell_id > 0 AND class_key = ? AND spec_key = ?
                ORDER BY row_index, col_index, spell_id
                """,
                (priority_class, priority_spec),
            ).fetchall()
        )
    if len(spell_ids) < limit:
        add_rows(
            conn.execute(
                """
                SELECT DISTINCT spell_id
                FROM websim_talents
                WHERE spell_id > 0
                ORDER BY spell_id
                LIMIT ?
                """,
                (limit * 2,),
            ).fetchall()
        )
    return spell_ids[:limit]


def sync_blizzard_spell_details(conn, token, region=DEFAULT_REGION, locale=DEFAULT_LOCALE):
    limit = int_env("WOW_WEBSIM_SYNC_SPELL_LIMIT", 400)
    spell_ids = selected_spell_ids_for_sync(conn, limit)
    now = utc_now()
    counts = {"spells": 0, "media": 0}
    for spell_id in spell_ids:
        try:
            spell_payload, spell_locale = blizzard_get_localized(
                f"/data/wow/spell/{spell_id}",
                token,
                region,
                locale,
                namespace=blizzard_namespace(region, "static"),
            )
        except Exception:
            continue
        try:
            media_payload, _ = blizzard_get_localized(
                f"/data/wow/media/spell/{spell_id}",
                token,
                region,
                spell_locale,
                namespace=blizzard_namespace(region, "static"),
            )
        except Exception:
            media_payload = {}
        icon_url = icon_url_from_media(media_payload)
        description = spell_payload.get("description") or spell_payload.get("tooltip") or ""
        conn.execute(
            """
            INSERT INTO websim_spell_details (
                id, spell_id, name, description, icon_url, locale, payload_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                description=excluded.description,
                icon_url=excluded.icon_url,
                locale=excluded.locale,
                payload_json=excluded.payload_json,
                updated_at=excluded.updated_at
            """,
            (
                str(spell_id),
                spell_id,
                spell_payload.get("name") or f"Spell {spell_id}",
                description,
                icon_url,
                spell_locale,
                json.dumps(spell_payload, ensure_ascii=False),
                now,
            ),
        )
        counts["spells"] += 1
        if icon_url:
            conn.execute(
                """
                INSERT INTO websim_media_assets (id, media_type, media_id, url, payload_json, updated_at)
                VALUES (?, 'spell', ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    url=excluded.url,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    f"spell:{spell_id}",
                    str(spell_id),
                    icon_url,
                    json.dumps(media_payload, ensure_ascii=False),
                    now,
                ),
            )
            counts["media"] += 1
    return counts


def sync_blizzard_journal(conn, token, region=DEFAULT_REGION, locale=DEFAULT_LOCALE):
    now = utc_now()
    instance_limit = int_env("WOW_WEBSIM_SYNC_INSTANCE_LIMIT", 8)
    encounter_limit = int_env("WOW_WEBSIM_SYNC_ENCOUNTER_LIMIT", 80)
    item_limit = int_env("WOW_WEBSIM_SYNC_ITEM_LIMIT", 300)
    season = resolve_current_mythic_season(token, region, locale)
    save_active_season_payload(conn, season)
    dungeons = (season.get("dungeons") or [])[:instance_limit]
    counts = {
        "instances": 0,
        "encounters": 0,
        "loot": 0,
        "items": 0,
        "seasonId": season.get("seasonId"),
        "seasonLabel": season.get("seasonLabel"),
        "seasonRevision": season.get("seasonRevision"),
        "dataStatus": season.get("dataStatus"),
    }
    fetched_items = set()
    conn.execute("DELETE FROM websim_loot")
    conn.execute("DELETE FROM websim_encounters")
    conn.execute("DELETE FROM websim_instances")

    for dungeon in dungeons:
        instance_id = str(dungeon.get("instanceId") or "")
        if not instance_id:
            continue
        try:
            instance = blizzard_get(
                f"/data/wow/journal-instance/{instance_id}",
                token,
                region,
                season.get("locale") or locale,
                namespace=blizzard_namespace(region, "static"),
            )
        except Exception:
            instance = {"id": instance_id, "name": dungeon.get("name") or f"Instance {instance_id}", "encounters": []}
        instance_name = instance.get("name") or dungeon.get("name") or f"Instance {instance_id}"
        category = (instance.get("category") or {}).get("name") or "Dungeon"
        conn.execute(
            """
            INSERT INTO websim_instances (id, name, category, payload_json, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                category=excluded.category,
                payload_json=excluded.payload_json,
                updated_at=excluded.updated_at
            """,
            (str(instance_id), instance_name, category, json.dumps(instance, ensure_ascii=False), now),
        )
        counts["instances"] += 1

        encounter_refs = list_keyed_values(instance, "encounters")
        for encounter_ref in encounter_refs:
            if counts["encounters"] >= encounter_limit:
                break
            encounter_id = extract_id_from_ref(encounter_ref)
            if not encounter_id:
                continue
            encounter = blizzard_get(
                f"/data/wow/journal-encounter/{encounter_id}",
                token,
                region,
                season.get("locale") or locale,
                namespace=blizzard_namespace(region, "static"),
            )
            encounter_name = encounter.get("name") or f"Encounter {encounter_id}"
            conn.execute(
                """
                INSERT INTO websim_encounters (id, instance_id, name, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    instance_id=excluded.instance_id,
                    name=excluded.name,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (str(encounter_id), str(instance_id), encounter_name, json.dumps(encounter, ensure_ascii=False), now),
            )
            counts["encounters"] += 1
            item_refs = list_keyed_values(encounter, "items", "loot")
            for loot_ref in item_refs:
                item_ref = loot_ref.get("item") if isinstance(loot_ref, dict) else loot_ref
                item_id = extract_id_from_ref(item_ref)
                if not item_id or len(fetched_items) >= item_limit:
                    continue
                item_payload = {}
                media_payload = {}
                if item_id not in fetched_items:
                    item_payload = blizzard_get(
                        f"/data/wow/item/{item_id}",
                        token,
                        region,
                        season.get("locale") or locale,
                        namespace=blizzard_namespace(region, "static"),
                    )
                    try:
                        media_payload = blizzard_get(
                            f"/data/wow/media/item/{item_id}",
                            token,
                            region,
                            season.get("locale") or locale,
                            namespace=blizzard_namespace(region, "static"),
                        )
                    except Exception:
                        media_payload = {}
                    fetched_items.add(item_id)
                    counts["items"] += 1
                item_name = item_payload.get("name") or (item_ref or {}).get("name") or f"Item {item_id}"
                slot = item_slot_from_payload(item_payload)
                quality = (item_payload.get("quality") or {}).get("name") or ""
                icon_url = icon_url_from_media(media_payload)
                conn.execute(
                    """
                    INSERT INTO websim_items (id, name, slot, quality, icon_url, payload_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        slot=excluded.slot,
                        quality=excluded.quality,
                        icon_url=excluded.icon_url,
                        payload_json=excluded.payload_json,
                        updated_at=excluded.updated_at
                    """,
                    (str(item_id), item_name, slot, quality, icon_url, json.dumps(item_payload, ensure_ascii=False), now),
                )
                loot_id = f"{instance_id}:{encounter_id}:{item_id}"
                conn.execute(
                    """
                    INSERT INTO websim_loot (
                        id, instance_id, encounter_id, item_id, name, slot, quality, icon_url, payload_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        slot=excluded.slot,
                        quality=excluded.quality,
                        icon_url=excluded.icon_url,
                        payload_json=excluded.payload_json,
                        updated_at=excluded.updated_at
                    """,
                    (
                        loot_id,
                        str(instance_id),
                        str(encounter_id),
                        str(item_id),
                        item_name,
                        slot,
                        quality,
                        icon_url,
                        json.dumps(loot_ref, ensure_ascii=False),
                        now,
                    ),
                )
                counts["loot"] += 1
    return counts


def selected_journal_instance_refs(token, region=DEFAULT_REGION, locale=DEFAULT_LOCALE):
    expansion_id = os.environ.get("WOW_WEBSIM_JOURNAL_EXPANSION_ID") or os.environ.get("WOW_WEBSIM_SYNC_EXPANSION_ID")
    expansion_name = os.environ.get("WOW_WEBSIM_JOURNAL_EXPANSION_NAME") or "Current Season"
    expansion = None
    selected_name = ""
    if expansion_id:
        expansion = blizzard_get(f"/data/wow/journal-expansion/{slugify(expansion_id, '')}", token, region, locale)
        selected_name = expansion.get("name") or str(expansion_id)
    else:
        index = blizzard_get("/data/wow/journal-expansion/index", token, region, locale)
        refs = list_keyed_values(index, "tiers", "expansions")
        selected = next((ref for ref in refs if str(ref.get("name") or "").lower() == expansion_name.lower()), None)
        selected = selected or next((ref for ref in refs if str(ref.get("name") or "").lower() == "midnight"), None)
        selected = selected or (refs[-1] if refs else None)
        if selected:
            selected_id = extract_id_from_ref(selected) or str(selected.get("id") or "")
            expansion = blizzard_get(f"/data/wow/journal-expansion/{selected_id}", token, region, locale)
            selected_name = expansion.get("name") or selected.get("name") or selected_id
    if expansion:
        rows = []
        for key, category in (("dungeons", "Dungeon"), ("raids", "Raid"), ("instances", "Dungeon")):
            for ref in list_keyed_values(expansion, key):
                rows.append((ref, category))
        if rows:
            return rows, selected_name
    index = blizzard_get("/data/wow/journal-instance/index", token, region, locale)
    return [(ref, "Dungeon") for ref in list_keyed_values(index, "instances")], "All Instances"


def current_simc_source_tar():
    explicit = os.environ.get("WOW_SIMC_SOURCE_TAR", "").strip()
    if explicit and Path(explicit).exists():
        return Path(explicit)
    commit_file = DEFAULT_SIMC_ROOT / ".commit"
    if commit_file.exists():
        commit = commit_file.read_text(encoding="utf-8", errors="ignore").strip()
        tar_path = DEFAULT_SIMC_ROOT / f"source-{commit}.tar.gz"
        if tar_path.exists():
            return tar_path
    candidates = sorted(DEFAULT_SIMC_ROOT.glob("source-*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def tar_member_suffix(tar, suffix):
    for member in tar.getmembers():
        if member.name.endswith(suffix):
            return member
    return None


def parse_ints(value):
    return [int(item) for item in re.findall(r"-?\d+", str(value or ""))]


def parse_trait_data_text(text, limit=6000):
    talents = []
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        name_match = re.search(r'"([^"]+)"', stripped)
        if name_match:
            name = name_match.group(1).strip()
            before = stripped[:name_match.start()] + stripped[name_match.end():]
        elif "//" in stripped:
            name = stripped.split("//", 1)[1].strip()
            before = stripped.split("//", 1)[0]
        else:
            continue
        if not name or name == "0":
            continue
        fields = parse_ints(before)
        if len(fields) < 17:
            continue
        game_class_id = fields[0]
        tree_id = fields[1]
        trait_id = fields[2]
        spell_id = fields[7]
        if spell_id <= 0:
            continue
        row_index = fields[10]
        col_index = fields[11]
        req_specs = []
        for value in fields[13:21]:
            if value > 0 and value not in req_specs:
                req_specs.append(value)
        base_class_key = GAME_CLASS_ID_TO_KEY.get(game_class_id, "")
        target_specs = []
        for spec_id in req_specs:
            spec_info = SPEC_ID_TO_KEY.get(spec_id)
            if spec_info:
                target = (spec_info[0], spec_info[1])
                if target not in target_specs:
                    target_specs.append(target)
        if not target_specs and base_class_key:
            target_specs = [(base_class_key, "class")]
        for class_key, spec_key in target_specs:
            talents.append(
                {
                    "id": f"{trait_id}:{class_key}:{spec_key}",
                    "traitId": trait_id,
                    "classKey": class_key,
                    "specKey": spec_key,
                    "treeId": str(tree_id),
                    "row": row_index,
                    "col": col_index,
                    "spellId": spell_id,
                    "name": name,
                    "rank": fields[4],
                }
            )
            if len(talents) >= limit:
                return talents
    return talents


def parse_profile_preset(path, text):
    actor_class = ""
    actor_name = Path(path).stem
    spec = ""
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"')
        if key in {klass["key"] for klass in WOW_CLASSES}:
            actor_class = key
            actor_name = value or actor_name
        elif key == "spec":
            spec = value
        if actor_class and spec:
            break
    if not actor_class or not spec:
        return None
    return {
        "id": slugify(f"{actor_class}-{spec}-{actor_name}", actor_name),
        "classKey": actor_class,
        "specKey": spec.replace("-", "_"),
        "name": actor_name,
        "profile": text.strip(),
    }


def extract_simc_data_from_tar(tar_path):
    result = {"talents": [], "presets": [], "source": str(tar_path or "")}
    if not tar_path or not Path(tar_path).exists():
        return result
    with tarfile.open(tar_path, "r:gz") as tar:
        trait_member = tar_member_suffix(tar, "engine/dbc/generated/trait_data.inc")
        if trait_member:
            extracted = tar.extractfile(trait_member)
            if extracted:
                result["talents"] = parse_trait_data_text(extracted.read().decode("utf-8", errors="ignore"))
        preset_limit = int_env("WOW_WEBSIM_SIMC_PRESET_LIMIT", 80)
        for member in tar.getmembers():
            if len(result["presets"]) >= preset_limit:
                break
            if not re.search(r"/profiles/(MID|TWW|PR).+\.simc$", member.name):
                continue
            extracted = tar.extractfile(member)
            if not extracted:
                continue
            preset = parse_profile_preset(member.name, extracted.read().decode("utf-8", errors="ignore"))
            if preset:
                result["presets"].append(preset)
    return result


def sync_simc_generated_data(conn):
    now = utc_now()
    data = extract_simc_data_from_tar(current_simc_source_tar())
    if data["source"]:
        conn.execute("DELETE FROM websim_talents")
        conn.execute("DELETE FROM websim_profile_presets")
    for talent in data["talents"]:
        payload = dict(talent)
        conn.execute(
            """
            INSERT INTO websim_talents (
                id, class_key, spec_key, tree_id, row_index, col_index, spell_id, name, payload_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                class_key=excluded.class_key,
                spec_key=excluded.spec_key,
                tree_id=excluded.tree_id,
                row_index=excluded.row_index,
                col_index=excluded.col_index,
                spell_id=excluded.spell_id,
                name=excluded.name,
                payload_json=excluded.payload_json,
                updated_at=excluded.updated_at
            """,
            (
                talent["id"],
                talent["classKey"],
                talent["specKey"],
                talent["treeId"],
                talent["row"],
                talent["col"],
                talent["spellId"],
                talent["name"],
                json.dumps(payload, ensure_ascii=False),
                now,
            ),
        )
    for preset in data["presets"]:
        payload = {key: value for key, value in preset.items() if key != "profile"}
        conn.execute(
            """
            INSERT INTO websim_profile_presets (id, class_key, spec_key, name, profile, payload_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                class_key=excluded.class_key,
                spec_key=excluded.spec_key,
                name=excluded.name,
                profile=excluded.profile,
                payload_json=excluded.payload_json,
                updated_at=excluded.updated_at
            """,
            (
                preset["id"],
                preset["classKey"],
                preset["specKey"],
                preset["name"],
                preset["profile"],
                json.dumps(payload, ensure_ascii=False),
                now,
            ),
        )
    return {"talents": len(data["talents"]), "presets": len(data["presets"]), "source": data["source"]}


def sync_websim_cache(db_path, include_blizzard=True):
    conn = sqlite3.connect(db_path)
    try:
        ensure_websim_tables(conn)
        simc_counts = sync_simc_generated_data(conn)
        blizzard_counts = {"instances": 0, "encounters": 0, "loot": 0, "items": 0}
        spell_counts = {"spells": 0, "media": 0}
        errors = []
        if include_blizzard:
            try:
                token = get_blizzard_access_token(DEFAULT_REGION)
                blizzard_counts = sync_blizzard_journal(conn, token, DEFAULT_REGION, DEFAULT_LOCALE)
                spell_counts = sync_blizzard_spell_details(conn, token, DEFAULT_REGION, DEFAULT_LOCALE)
            except Exception as error:
                errors.append(str(error))
        active_season = get_active_season_payload(conn)
        payload = {
            "ok": not errors and active_season.get("dataStatus") == "verified",
            "checkedAt": utc_now(),
            "region": DEFAULT_REGION,
            "locale": DEFAULT_LOCALE,
            "simc": simc_counts,
            "blizzard": blizzard_counts,
            "spells": spell_counts,
            "currentSeason": active_season,
            "dataStatus": active_season.get("dataStatus") or "blocked",
            "seasonRevision": active_season.get("seasonRevision") or "",
            "errors": errors,
        }
        set_sync_state(conn, "websim_sync", payload)
        conn.commit()
        return payload
    finally:
        conn.close()


def classes_payload():
    return [
        {
            "key": item["key"],
            "label": CLASS_LABELS_ZH.get(item["key"], item["label"]),
            "labelEn": item["label"],
            "specs": [
                {
                    "key": spec,
                    "label": SPEC_LABELS_ZH.get(spec, SPEC_LABELS.get(spec, spec.replace("_", " ").title())),
                    "labelEn": SPEC_LABELS.get(spec, spec.replace("_", " ").title()),
                }
                for spec in item["specs"]
            ],
        }
        for item in WOW_CLASSES
    ]


def simc_version_payload():
    if DEFAULT_SIMC_VERSION_FILE.exists():
        return safe_json_loads(DEFAULT_SIMC_VERSION_FILE.read_text(encoding="utf-8", errors="ignore"), {})
    return {"binary": os.environ.get("WOW_SIMC_BIN", "/opt/wow-simc/current/simc")}


def fallback_instances():
    instances = {}
    for row in FALLBACK_LOOT:
        instances.setdefault(
            row["instanceId"],
            {"id": row["instanceId"], "name": row["instanceName"], "category": "Dungeon", "encounters": []},
        )
        encounter = {"id": row["encounterId"], "name": row["encounterName"], "instanceId": row["instanceId"]}
        if encounter not in instances[row["instanceId"]]["encounters"]:
            instances[row["instanceId"]]["encounters"].append(encounter)
    return list(instances.values())


def fallback_talents(class_key="mage", spec_key="arcane"):
    names = [
        "Arcane Missiles",
        "Arcane Surge",
        "Clearcasting",
        "Touch of the Magi",
        "Nether Precision",
        "Presence of Mind",
        "Arcane Echo",
        "Siphon Storm",
        "Shifting Power",
        "Aether Attunement",
        "High Voltage",
        "Leydrinker",
    ]
    return [
        {
            "id": f"fallback-{class_key}-{spec_key}-{index}",
            "classKey": class_key,
            "specKey": spec_key,
            "treeId": "fallback",
            "row": index // 3 + 1,
            "col": index % 3 + 2,
            "spellId": 0,
            "name": name,
            "rank": 1,
            "selected": index < 5,
        }
        for index, name in enumerate(names)
    ]


def fallback_presets(class_key="mage", spec_key="arcane"):
    profile = "\n".join(
        [
            f'{class_key}="WebSim_{SPEC_LABELS.get(spec_key, spec_key).replace(" ", "_")}"',
            f"spec={spec_key}",
            "level=90",
            f"race={DEFAULT_RACE_BY_CLASS.get(class_key, 'troll')}",
            "role=spell",
            "position=back",
            "talents=C4DAAAAAAAAAAAAAAAAAAAAAAYGGLzMzswMzQzMzAAAwAAgAmZmZZZmZYBAgtxMzMmtFLzMzYmxYMzMGLMzMjZAAGAAAzsAAmBADD",
        ]
    )
    return [{"id": f"fallback-{class_key}-{spec_key}", "classKey": class_key, "specKey": spec_key, "name": "WebSim starter", "profile": profile}]


def get_websim_bootstrap(conn):
    ensure_websim_tables(conn)
    season = get_active_season_payload(conn)
    instances = get_websim_instances(conn)
    season_fields = season_metadata_fields(season)
    return {
        "navTitle": "WebSim",
        "title": "SimC 构筑工坊",
        "region": DEFAULT_REGION,
        "locale": season_fields["locale"],
        "localeFallbacks": unique_locale_preferences(season_fields["locale"]),
        "classes": classes_payload(),
        "gearSlots": GEAR_SLOTS,
        "scenarios": SCENARIOS,
        "instances": instances,
        "syncState": get_sync_state(conn, "websim_sync") or {"ok": False, "errors": ["websim cache has not been synced"]},
        "defaultSelection": get_websim_default_selection(conn),
        "simcraftVersion": simc_version_payload(),
        **season_fields,
    }


def get_websim_default_selection(conn):
    row = conn.execute(
        """
        SELECT p.class_key, p.spec_key
        FROM websim_profile_presets p
        WHERE p.spec_key != 'class'
          AND EXISTS (
            SELECT 1 FROM websim_talents t
            WHERE t.class_key = p.class_key
              AND t.spec_key = p.spec_key
          )
        ORDER BY p.class_key, p.spec_key
        LIMIT 1
        """
    ).fetchone()
    if not row:
        row = conn.execute(
            """
            SELECT class_key, spec_key, COUNT(*) AS node_count
            FROM websim_talents
            WHERE spec_key != 'class'
            GROUP BY class_key, spec_key
            ORDER BY node_count DESC, class_key, spec_key
            LIMIT 1
            """
        ).fetchone()
    return {
        "classKey": row[0] if row else "mage",
        "specKey": row[1] if row else "arcane",
    }


def get_websim_instances(conn):
    ensure_websim_tables(conn)
    season = get_active_season_payload(conn)
    if season.get("dataStatus") != "verified":
        return []
    rows = conn.execute("SELECT id, name, category FROM websim_instances ORDER BY name").fetchall()
    if not rows:
        return []
    encounters = {}
    for row in conn.execute("SELECT id, instance_id, name FROM websim_encounters ORDER BY name").fetchall():
        encounters.setdefault(row[1], []).append({"id": row[0], "instanceId": row[1], "name": row[2]})
    return [
        {"id": row[0], "name": row[1], "category": row[2], "encounters": encounters.get(row[0], [])}
        for row in rows
    ]


def get_websim_talents(conn, class_key="mage", spec_key="arcane"):
    ensure_websim_tables(conn)
    season = get_active_season_payload(conn)
    class_key = slugify(class_key, "mage")
    spec_key = slugify(spec_key, "arcane")
    if season.get("dataStatus") != "verified":
        return {
            "classKey": class_key,
            "specKey": spec_key,
            "nodes": [],
            "presets": get_websim_presets(conn, class_key, spec_key),
            **season_metadata_fields(season),
        }
    rows = conn.execute(
        """
        SELECT t.id, t.class_key, t.spec_key, t.tree_id, t.row_index, t.col_index,
               t.spell_id, COALESCE(NULLIF(s.name, ''), t.name) AS name, t.payload_json,
               s.description, s.icon_url
        FROM websim_talents t
        JOIN websim_spell_details s ON s.spell_id = t.spell_id
        WHERE t.class_key = ?
          AND (t.spec_key = ? OR t.spec_key = 'class')
          AND t.spell_id > 0
          AND s.description != ''
          AND s.icon_url != ''
        ORDER BY row_index, col_index, name
        LIMIT 180
        """,
        (class_key, spec_key),
    ).fetchall()
    nodes = [
        {
            "id": row[0],
            "classKey": row[1],
            "specKey": row[2],
            "treeId": row[3],
            "row": row[4],
            "col": row[5],
            "spellId": row[6],
            "name": row[7],
            "rank": safe_json_loads(row[8], {}).get("rank", 1),
            "description": row[9],
            "iconUrl": row[10],
            "sourceRefs": season.get("sourceRefs") or [],
        }
        for row in rows
    ]
    return {
        "classKey": class_key,
        "specKey": spec_key,
        "nodes": nodes,
        "presets": get_websim_presets(conn, class_key, spec_key),
        **season_metadata_fields(season),
    }


def get_websim_presets(conn, class_key="mage", spec_key="arcane"):
    rows = conn.execute(
        """
        SELECT id, class_key, spec_key, name, profile
        FROM websim_profile_presets
        WHERE class_key = ? AND spec_key = ?
        ORDER BY name
        LIMIT 12
        """,
        (class_key, spec_key),
    ).fetchall()
    if not rows:
        return fallback_presets(class_key, spec_key)
    return [{"id": row[0], "classKey": row[1], "specKey": row[2], "name": row[3], "profile": row[4]} for row in rows]


def get_websim_gear(conn, class_key="mage", spec_key="arcane"):
    season = get_active_season_payload(conn)
    return {
        "classKey": slugify(class_key, "mage"),
        "specKey": slugify(spec_key, "arcane"),
        "slots": GEAR_SLOTS,
        "presets": get_websim_presets(conn, class_key, spec_key),
        "candidateItems": get_websim_loot(conn, {}, limit=24)["items"],
        **season_metadata_fields(season),
    }


def get_websim_loot(conn, filters=None, limit=120):
    ensure_websim_tables(conn)
    filters = filters or {}
    season = get_active_season_payload(conn)
    if season.get("dataStatus") != "verified":
        return {"items": [], "instances": [], **season_metadata_fields(season)}
    rows = conn.execute(
        """
        SELECT l.id, l.instance_id, i.name, l.encounter_id, e.name, l.item_id, l.name, l.slot, l.quality, l.icon_url
        FROM websim_loot l
        LEFT JOIN websim_instances i ON i.id = l.instance_id
        LEFT JOIN websim_encounters e ON e.id = l.encounter_id
        ORDER BY i.name, e.name, l.name
        LIMIT 500
        """
    ).fetchall()
    items = [
        {
            "id": row[0],
            "instanceId": row[1],
            "instanceName": row[2] or "Unknown Instance",
            "encounterId": row[3],
            "encounterName": row[4] or "Unknown Encounter",
            "itemId": row[5],
            "name": row[6],
            "slot": row[7],
            "quality": row[8],
            "iconUrl": row[9],
        }
        for row in rows
    ]
    if not items:
        items = []
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
    return {"items": items[:limit], "instances": get_websim_instances(conn), **season_metadata_fields(season)}


def normalize_option_value(value):
    if isinstance(value, list):
        return "/".join(normalize_option_value(item) for item in value if normalize_option_value(item))
    return re.sub(r"[^A-Za-z0-9_:/.-]+", "", str(value or "").strip())[:240]


def normalize_slot(value):
    slot = re.sub(r"[^a-z0-9_]+", "_", str(value or "").lower()).strip("_")
    slot_aliases = {"wrist": "wrists", "shoulders": "shoulder", "cloak": "back", "weapon": "main_hand"}
    return slot_aliases.get(slot, slot)


def normalize_gear_item(value):
    if not isinstance(value, dict):
        return None
    slot = normalize_slot(value.get("slot") or value.get("slotKey"))
    item_id = normalize_option_value(value.get("id") or value.get("itemId") or value.get("item_id"))
    if not slot or not item_id:
        return None
    item = {
        "slot": slot,
        "name": slugify(value.get("name"), f"item_{item_id}"),
        "id": item_id,
    }
    for key in ["ilevel", "bonus_id", "gem_id", "gem_bonus_id", "gem_ilevel", "enchant_id", "crafted_stats"]:
        value_text = normalize_option_value(value.get(key) or value.get(key.replace("_", "")))
        if value_text:
            item[key] = value_text
    return item


def build_websim_gear_lines(items):
    lines = []
    seen = set()
    for raw_item in items or []:
        item = normalize_gear_item(raw_item)
        if not item or item["slot"] in seen:
            continue
        seen.add(item["slot"])
        parts = [f'{item["slot"]}={item["name"]}', f'id={item["id"]}']
        for key in ["ilevel", "bonus_id", "gem_id", "gem_bonus_id", "gem_ilevel", "enchant_id", "crafted_stats"]:
            if item.get(key):
                parts.append(f"{key}={item[key]}")
        lines.append(",".join(parts))
    return lines


def selected_scenario(value):
    key = str(value or "").strip()
    for scenario in SCENARIOS:
        if scenario["key"] == key:
            return scenario
    return SCENARIOS[0]


def build_websim_profile(payload):
    source = payload if isinstance(payload, dict) else {}
    class_key = slugify(source.get("classKey"), "mage")
    spec_key = slugify(source.get("specKey"), "arcane")
    race = normalize_option_value(source.get("race") or DEFAULT_RACE_BY_CLASS.get(class_key, "troll"))
    level = normalize_option_value(source.get("level") or "90")
    actor_name = slugify(source.get("name") or f"WebSim {SPEC_LABELS.get(spec_key, spec_key)}", "WebSim")
    role = "spell" if class_key in {"mage", "warlock", "priest", "evoker", "shaman", "druid"} else "attack"
    lines = [
        f'{class_key}="{actor_name}"',
        f"spec={spec_key}",
        f"level={level}",
        f"race={race}",
        f"role={role}",
        "position=back",
    ]
    talents = normalize_option_value(source.get("talents") or source.get("talentImport"))
    if talents:
        lines.append(f"talents={talents}")
    gear_selection = source.get("gearSelection") if isinstance(source.get("gearSelection"), dict) else {}
    gear_items = gear_selection.get("items") or source.get("gearItems") or []
    lines.extend(build_websim_gear_lines(gear_items))
    scenario = selected_scenario(source.get("scenarioKey"))
    lines.extend(
        [
            "",
            f"iterations={int_env('WOW_WEBSIM_SIMC_ITERATIONS', 1000)}",
            f"fight_style={scenario['fightStyle']}",
            f"desired_targets={scenario['targets']}",
            f"max_time={scenario['durationSeconds']}",
            "vary_combat_length=0.2",
            "calculate_scale_factors=0",
        ]
    )
    return "\n".join(lines).strip()


def build_websim_simulator_request(payload, guest_id=""):
    profile = build_websim_profile(payload)
    source = payload if isinstance(payload, dict) else {}
    class_key = slugify(source.get("classKey"), "mage")
    spec_key = slugify(source.get("specKey"), "arcane")
    return {
        "mode": "simcraft",
        "profile": profile,
        "prompt": f"WebSim {class_key} {spec_key} simulation",
        "question": "WebSim gear and talent simulation",
        "runSimulation": True,
        "saveTask": bool(source.get("saveTask", True)),
        "guestId": guest_id or str(source.get("guestId") or ""),
        "buildContext": {
            "specId": f"{class_key}-{spec_key}",
            "className": class_key,
            "specName": spec_key,
            "activeQueryKey": "websim",
            "sourceName": "WebSim",
            "details": {
                "talents": {"importCode": str(source.get("talents") or source.get("talentImport") or "")[:400]},
                "gear": {"simcItems": source.get("gearItems") or ((source.get("gearSelection") or {}).get("items") if isinstance(source.get("gearSelection"), dict) else []) or []},
            },
        },
    }

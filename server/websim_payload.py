#!/usr/bin/env python3
import ast
import base64
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

try:
    from .db import require_sqlite_runtime_enabled
except ImportError:
    from db import require_sqlite_runtime_enabled

try:
    from .simc_profile_policy import (
        dk_default_runeforge_enchant_id,
        dk_ordinary_weapon_enchant_blocker,
    )
except ImportError:
    from simc_profile_policy import (
        dk_default_runeforge_enchant_id,
        dk_ordinary_weapon_enchant_blocker,
    )

try:
    from .simc_preparation import apply_simc_preparation_lines, simc_preparation_payload, simc_preparation_report
except ImportError:
    from simc_preparation import apply_simc_preparation_lines, simc_preparation_payload, simc_preparation_report


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
DEFAULT_SIMC_BRANCH = os.environ.get("WOW_SIMC_GITHUB_BRANCH", "midnight").strip() or "midnight"
DEFAULT_SIMC_TRAIT_DATA_URL = os.environ.get(
    "WOW_SIMC_TRAIT_DATA_URL",
    f"https://raw.githubusercontent.com/simulationcraft/simc/{DEFAULT_SIMC_BRANCH}/engine/dbc/generated/trait_data.inc",
).strip()
DEFAULT_SIMC_SPELLTEXT_DATA_URL = os.environ.get(
    "WOW_SIMC_SPELLTEXT_DATA_URL",
    f"https://raw.githubusercontent.com/simulationcraft/simc/{DEFAULT_SIMC_BRANCH}/engine/dbc/generated/spelltext_data.inc",
).strip()
DEFAULT_SIMC_REMOTE_ENABLED = os.environ.get("WOW_WEBSIM_FETCH_SIMC_REMOTE", "1").strip() != "0"
DEFAULT_WAGO_DB2_BASE_URL = os.environ.get("WOW_WAGO_DB2_BASE_URL", "https://wago.tools/db2").strip().rstrip("/")
DEFAULT_WAGO_DB2_ENABLED = (
    os.environ.get("WOW_WEBSIM_FETCH_WAGO_DB2", os.environ.get("WOW_WEBSIM_FETCH_SIMC_REMOTE", "1")).strip() != "0"
)
DEFAULT_WAGO_DB2_TRAIT_EDGE_ENABLED = (
    os.environ.get("WOW_WEBSIM_FETCH_WAGO_DB2_TRAIT_EDGE", "1").strip() != "0"
)
DEFAULT_WAGO_DB2_LOCALIZATION_ENABLED = (
    os.environ.get("WOW_WEBSIM_FETCH_WAGO_DB2_LOCALIZATION", "0").strip() == "1"
)
ITEM_METADATA_SOURCE = "Battle.net Game Data API"
GAME_ASSET_RESOLUTION_TIER = "icon_56"
BLIZZARD_ICON_HOSTS = {"render.worldofwarcraft.com"}
GEAR_CATALOG_SHARED_CACHE_LOCK = threading.Lock()
GEAR_CATALOG_SHARED_CACHE = {}
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
MIDNIGHT_CURRENT_SEASON_RAIDS = [
    "The Voidspire",
    "The Dreamrift",
    "March on Quel'Danas",
    "Sporefall",
]
MIDNIGHT_CURRENT_SEASON_RAID_ALIASES = {
    "The Voidspire": ["虚影尖塔"],
    "The Dreamrift": ["梦境裂隙"],
    "March on Quel'Danas": ["进军奎尔丹纳斯"],
    "Sporefall": ["孢陨幽境"],
}
REUSED_LEGACY_DUNGEON_INSTANCE_IDS = {"278", "476", "945"}
REUSED_LEGACY_DUNGEON_SOURCE_REFERENCE_ITEM_IDS = {
    "278": {
        "49802",
        "49805",
        "49806",
        "49807",
        "49808",
        "49809",
        "49810",
        "49811",
        "49812",
        "49813",
        "49817",
        "49819",
        "49823",
        "49824",
        "49825",
        "50227",
        "50228",
        "50233",
        "50234",
        "50259",
        "50263",
        "50264",
        "50272",
        "252421",
    },
    "476": {
        "252411",
        "252418",
        "252420",
        "258046",
        "258047",
        "258048",
        "258049",
        "258050",
        "258218",
        "258412",
        "258436",
        "258438",
        "258472",
        "258484",
        "258574",
        "258575",
        "258576",
        "258577",
        "258578",
        "258579",
        "258580",
        "258581",
        "258582",
        "258583",
        "258584",
        "258585",
        "258586",
        "258587",
    },
    "945": {
        "151299",
        "151300",
        "151303",
        "151304",
        "151305",
        "151307",
        "151308",
        "151309",
        "151310",
        "151311",
        "151312",
        "151314",
        "151315",
        "151316",
        "151317",
        "151318",
        "151321",
        "151323",
        "151325",
        "151326",
        "151327",
        "151329",
        "151330",
        "151331",
        "151332",
        "151333",
        "151336",
        "151337",
        "151338",
        "151340",
        "258514",
        "258516",
        "258523",
        "258524",
        "258525",
    },
}
REUSED_LEGACY_DUNGEON_SOURCE_DISCREPANCY_ITEM_IDS = {"945": {"258523"}}
SOURCE_VALIDATION_ACCEPTED_STATUSES = {
    "source_reference",
    "source_discrepancy",
    "accepted",
    "verified",
}
SOURCE_VALIDATION_INACTIVE_STATUSES = {
    "raw_journal",
    "journal_candidate",
    "excluded_legacy_bucket",
    "observed_confirmed",
    "manual_review_candidate",
    "blocked",
    "stale",
}
CURRENT_SEASON_RAID_POOL_MISSING_BLOCKER = "current season raid pool missing verified journal refs"
CURRENT_SEASON_RAID_POOL_STALE_BLOCKER = "current season raid pool has stale journal refs"
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
SIMC_TALENT_SOURCE_REFS = [
    {
        "name": "SimulationCraft generated trait data",
        "url": DEFAULT_SIMC_TRAIT_DATA_URL,
        "note": "Generated SimC trait_data.inc used for class, specialization and hero talent node layout.",
    }
]
COMMUNITY_TALENT_SYNC_KEY = "community_talent_templates"
COMMUNITY_TALENT_TEMPLATE_LIMIT_PER_SPEC = 3
COMMUNITY_TEMPLATE_SYNC_RUN_KEY = "community_template_sync_latest"
COMMUNITY_TEMPLATE_REVISION = "community-template-v1"
DEFAULT_GEAR_TEMPLATE_SOURCE_KEY = "default_template"
DEFAULT_GEAR_TEMPLATE_SOURCE_NAME = "默认模板"
DEFAULT_GEAR_TEMPLATE_SCENARIO_KEY = "mplus_mixed_route"
DEFAULT_GEAR_TEMPLATE_ILEVEL_GUARDRAIL = 6
DEFAULT_GEAR_TEMPLATE_TRINKET_WARNING = "trinket effects are not optimized"
TEMPLATE_EVIDENCE_AUDIT_REVISION = "template-evidence-audit-v1"
TALENT_SCHEMA_REVISION = "websim-talent-rules-v1"
TALENT_CATALOG_REVISION = "websim-talent-catalog-v1"
GEAR_SCHEMA_REVISION = "websim-gear-simulator-v1"
GEAR_CATALOG_REVISION = "websim-gear-catalog-v1"
GEAR_OBSERVED_BACKFILL_SYNC_KEY = "gear_observed_backfill"
GEAR_OBSERVED_BACKFILL_SCHEMA_VERSION = 1
STALE_PLACEHOLDER_GEAR_MOD_OPTION_IDS = {"seed-socket-gem-240983", "seed-enchant-8017"}
GEAR_CONFIG_ENCHANT_EXCLUDED_CATEGORIES = {
    "class_only_precombat",
    "class_only_weapon_enchant",
    "combat_preparation",
    "runeforge",
    "temporary_enchant",
}
GEAR_CONFIG_ENCHANT_ID_POLICIES = {
    "3368": {
        "configCategory": "runeforge",
        "exclusionReason": "DK runeforge observed on Frost Death Knight weapons, not a general gear enchant.",
    },
    "6245": {
        "configCategory": "runeforge",
        "exclusionReason": "DK runeforge observed on weapons, not a general gear enchant.",
    },
    "7528": {
        "configCategory": "class_only_precombat",
        "exclusionReason": "Restoration Shaman class-only combat preparation, not a general gear enchant.",
    },
}
GEAR_ENCHANT_LABELS_ZH = {
    "4897": "地精滑翔器",
    "7957": "纳洛拉克印记",
    "7963": "山猫之敏",
    "7967": "鹰眼神视",
    "7969": "祖尔金的精通",
    "7981": "加亚莱的精准",
    "7983": "狂战士之怒",
    "7985": "护根者印记",
    "7987": "世界之魂印记",
    "7993": "莎拉达希尔之根",
    "7997": "自然之怒",
    "8013": "魔导师印记",
    "8019": "远行者的狩猎",
    "8025": "银月城之捷",
    "8027": "银月城之韧",
    "8039": "朗多雷之锐",
    "8041": "奥术精通",
    "7935": "阳炎丝绸魔线",
    "7937": "奥纹魔线",
    "8158": "森林猎手的护甲片",
    "8159": "森林猎手的护甲片",
    "8163": "血骑士的护甲片",
}
GEAR_CONFIG_ENCHANT_NAME_POLICIES = [
    {
        "tokens": ("唤潮者护卫", "唤潮者的护卫", "tideguard"),
        "configCategory": "class_only_precombat",
        "exclusionReason": "Restoration Shaman class-only combat preparation, not a general gear enchant.",
    },
]


WOW_CLASSES = [
    {"key": "deathknight", "label": "Death Knight", "specs": ["blood", "frost", "unholy"]},
    {"key": "demonhunter", "label": "Demon Hunter", "specs": ["havoc", "vengeance", "devourer"]},
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
    "devourer": "Devourer",
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
    "devourer": "噬灭",
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

CLASS_COLORS = {
    "deathknight": "#c41e3a",
    "demonhunter": "#a330c9",
    "druid": "#ff7c0a",
    "evoker": "#33937f",
    "hunter": "#aad372",
    "mage": "#3fc7eb",
    "monk": "#00ff98",
    "paladin": "#f48cba",
    "priest": "#ffffff",
    "rogue": "#fff468",
    "shaman": "#0070dd",
    "warlock": "#8788ee",
    "warrior": "#c69b6d",
}

CLASS_ICON_NAMES = {
    "deathknight": "classicon_deathknight",
    "demonhunter": "classicon_demonhunter",
    "druid": "classicon_druid",
    "evoker": "classicon_evoker",
    "hunter": "classicon_hunter",
    "mage": "classicon_mage",
    "monk": "classicon_monk",
    "paladin": "classicon_paladin",
    "priest": "classicon_priest",
    "rogue": "classicon_rogue",
    "shaman": "classicon_shaman",
    "warlock": "classicon_warlock",
    "warrior": "classicon_warrior",
}

SPEC_ICON_NAMES = {
    "arcane": "spell_holy_magicalsentry",
    "fire": "spell_fire_firebolt02",
    "frost": "spell_frost_frostbolt02",
    "holy": "spell_holy_holybolt",
    "protection": "ability_warrior_defensivestance",
    "retribution": "spell_holy_auraoflight",
    "elemental": "spell_nature_lightning",
    "enhancement": "spell_shaman_improvedstormstrike",
    "restoration": "spell_nature_magicimmunity",
    "arms": "ability_warrior_savageblow",
    "fury": "ability_warrior_innerrage",
    "blood": "spell_deathknight_bloodpresence",
    "unholy": "spell_deathknight_unholypresence",
    "havoc": "ability_demonhunter_specdps",
    "vengeance": "ability_demonhunter_spectank",
    "devourer": "ability_demonhunter_specdevourer",
    "balance": "spell_nature_starfall",
    "feral": "ability_druid_catform",
    "guardian": "ability_racial_bearform",
    "devastation": "classicon_evoker_devastation",
    "preservation": "classicon_evoker_preservation",
    "augmentation": "classicon_evoker_augmentation",
    "beast_mastery": "ability_hunter_bestialdiscipline",
    "marksmanship": "ability_hunter_focusedaim",
    "survival": "ability_hunter_camouflage",
    "brewmaster": "spell_monk_brewmaster_spec",
    "mistweaver": "spell_monk_mistweaver_spec",
    "windwalker": "spell_monk_windwalker_spec",
    "discipline": "spell_holy_powerwordshield",
    "shadow": "spell_shadow_shadowwordpain",
    "assassination": "ability_rogue_eviscerate",
    "outlaw": "ability_rogue_waylay",
    "subtlety": "ability_stealth",
    "affliction": "spell_shadow_deathcoil",
    "demonology": "spell_shadow_metamorphosis",
    "destruction": "spell_shadow_rainoffire",
}

HERO_TREE_LABELS = {
    "deathbringer": "Deathbringer",
    "rider_of_the_apocalypse": "Rider of the Apocalypse",
    "sanlayn": "San'layn",
    "aldrachi_reaver": "Aldrachi Reaver",
    "fel_scarred": "Fel-Scarred",
    "annihilator": "Annihilator",
    "void_scarred": "Void-Scarred",
    "keeper_of_the_grove": "Keeper of the Grove",
    "wildstalker": "Wildstalker",
    "elunes_chosen": "Elune's Chosen",
    "druid_of_the_claw": "Druid of the Claw",
    "flameshaper": "Flameshaper",
    "scalecommander": "Scalecommander",
    "chronowarden": "Chronowarden",
    "dark_ranger": "Dark Ranger",
    "pack_leader": "Pack Leader",
    "sentinel": "Sentinel",
    "spellslinger": "Spellslinger",
    "sunfury": "Sunfury",
    "frostfire": "Frostfire",
    "conduit_of_the_celestials": "Conduit of the Celestials",
    "master_of_harmony": "Master of Harmony",
    "shado_pan": "Shado-Pan",
    "herald_of_the_sun": "Herald of the Sun",
    "lightsmith": "Lightsmith",
    "templar": "Templar",
    "oracle": "Oracle",
    "voidweaver": "Voidweaver",
    "archon": "Archon",
    "deathstalker": "Deathstalker",
    "fatebound": "Fatebound",
    "trickster": "Trickster",
    "farseer": "Farseer",
    "stormbringer": "Stormbringer",
    "totemic": "Totemic",
    "hellcaller": "Hellcaller",
    "soul_harvester": "Soul Harvester",
    "diabolist": "Diabolist",
    "colossus": "Colossus",
    "mountain_thane": "Mountain Thane",
    "slayer": "Slayer",
}

HERO_TREE_LABELS_ZH = {
    "deathbringer": "死亡使者",
    "rider_of_the_apocalypse": "天启骑士",
    "sanlayn": "萨莱茵",
    "aldrachi_reaver": "奥达奇掠夺者",
    "fel_scarred": "邪痕者",
    "annihilator": "歼灭者",
    "void_scarred": "虚痕者",
    "keeper_of_the_grove": "丛林守护者",
    "wildstalker": "野性追猎者",
    "elunes_chosen": "艾露恩钦选者",
    "druid_of_the_claw": "利爪德鲁伊",
    "flameshaper": "塑焰者",
    "scalecommander": "鳞长",
    "chronowarden": "时空守卫",
    "dark_ranger": "黑暗游侠",
    "pack_leader": "兽群领袖",
    "sentinel": "哨兵",
    "spellslinger": "法术投射者",
    "sunfury": "日怒",
    "frostfire": "霜火",
    "conduit_of_the_celestials": "天神御师",
    "master_of_harmony": "和谐宗师",
    "shado_pan": "影踪派",
    "herald_of_the_sun": "旭日使者",
    "lightsmith": "铸光者",
    "templar": "圣殿骑士",
    "oracle": "神谕者",
    "voidweaver": "虚空编织者",
    "archon": "执政官",
    "deathstalker": "死亡猎手",
    "fatebound": "命缚者",
    "trickster": "欺诈者",
    "farseer": "先知",
    "stormbringer": "风暴使者",
    "totemic": "图腾祭司",
    "hellcaller": "地狱召唤者",
    "soul_harvester": "灵魂收割者",
    "diabolist": "恶魔学家",
    "colossus": "巨像",
    "mountain_thane": "山丘领主",
    "slayer": "屠戮者",
}

HERO_BY_CLASS = {
    "deathknight": ["deathbringer", "rider_of_the_apocalypse", "sanlayn"],
    "demonhunter": ["aldrachi_reaver", "fel_scarred", "annihilator", "void_scarred"],
    "druid": ["keeper_of_the_grove", "wildstalker", "elunes_chosen", "druid_of_the_claw"],
    "evoker": ["flameshaper", "scalecommander", "chronowarden"],
    "hunter": ["dark_ranger", "pack_leader", "sentinel"],
    "mage": ["spellslinger", "sunfury", "frostfire"],
    "monk": ["conduit_of_the_celestials", "master_of_harmony", "shado_pan"],
    "paladin": ["herald_of_the_sun", "lightsmith", "templar"],
    "priest": ["oracle", "voidweaver", "archon"],
    "rogue": ["deathstalker", "fatebound", "trickster"],
    "shaman": ["farseer", "stormbringer", "totemic"],
    "warlock": ["hellcaller", "soul_harvester", "diabolist"],
    "warrior": ["colossus", "mountain_thane", "slayer"],
}

HERO_BY_SPEC = {
    ("deathknight", "blood"): ["deathbringer", "sanlayn"],
    ("deathknight", "frost"): ["deathbringer", "rider_of_the_apocalypse"],
    ("deathknight", "unholy"): ["rider_of_the_apocalypse", "sanlayn"],
    ("demonhunter", "havoc"): ["aldrachi_reaver", "fel_scarred"],
    ("demonhunter", "vengeance"): ["aldrachi_reaver", "annihilator"],
    ("demonhunter", "devourer"): ["annihilator", "void_scarred"],
    ("druid", "balance"): ["elunes_chosen", "keeper_of_the_grove"],
    ("druid", "feral"): ["wildstalker", "druid_of_the_claw"],
    ("druid", "guardian"): ["druid_of_the_claw", "elunes_chosen"],
    ("druid", "restoration"): ["keeper_of_the_grove", "wildstalker"],
    ("evoker", "devastation"): ["flameshaper", "scalecommander"],
    ("evoker", "preservation"): ["flameshaper", "chronowarden"],
    ("evoker", "augmentation"): ["scalecommander", "chronowarden"],
    ("hunter", "beast_mastery"): ["dark_ranger", "pack_leader"],
    ("hunter", "marksmanship"): ["dark_ranger", "sentinel"],
    ("hunter", "survival"): ["pack_leader", "sentinel"],
    ("mage", "arcane"): ["spellslinger", "sunfury"],
    ("mage", "fire"): ["sunfury", "frostfire"],
    ("mage", "frost"): ["frostfire", "spellslinger"],
    ("monk", "brewmaster"): ["master_of_harmony", "shado_pan"],
    ("monk", "mistweaver"): ["conduit_of_the_celestials", "master_of_harmony"],
    ("monk", "windwalker"): ["shado_pan", "conduit_of_the_celestials"],
    ("paladin", "holy"): ["herald_of_the_sun", "lightsmith"],
    ("paladin", "protection"): ["lightsmith", "templar"],
    ("paladin", "retribution"): ["herald_of_the_sun", "templar"],
    ("priest", "discipline"): ["oracle", "voidweaver"],
    ("priest", "holy"): ["oracle", "archon"],
    ("priest", "shadow"): ["voidweaver", "archon"],
    ("rogue", "assassination"): ["deathstalker", "fatebound"],
    ("rogue", "outlaw"): ["fatebound", "trickster"],
    ("rogue", "subtlety"): ["deathstalker", "trickster"],
    ("shaman", "elemental"): ["farseer", "stormbringer"],
    ("shaman", "enhancement"): ["stormbringer", "totemic"],
    ("shaman", "restoration"): ["farseer", "totemic"],
    ("warlock", "affliction"): ["hellcaller", "soul_harvester"],
    ("warlock", "demonology"): ["soul_harvester", "diabolist"],
    ("warlock", "destruction"): ["hellcaller", "diabolist"],
    ("warrior", "arms"): ["colossus", "slayer"],
    ("warrior", "fury"): ["slayer", "mountain_thane"],
    ("warrior", "protection"): ["mountain_thane", "colossus"],
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
    1480: ("demonhunter", "devourer"),
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

CANONICAL_GEAR_SLOTS = [
    "head",
    "neck",
    "shoulder",
    "back",
    "chest",
    "wrist",
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

PORTABLE_GEAR_SLOTS = {"neck", "back", "finger1", "finger2", "trinket1", "trinket2"}

ENCHANTABLE_GEAR_SLOTS = {
    "back",
    "chest",
    "wrist",
    "legs",
    "feet",
    "finger1",
    "finger2",
    "main_hand",
    "off_hand",
}
SOCKET_OPTION_GEAR_SLOT_LIST = ["neck", "finger1", "finger2"]
SOCKET_OPTION_GEAR_SLOTS = set(SOCKET_OPTION_GEAR_SLOT_LIST)
SOCKET_OPTION_GEAR_SLOT_CAPACITY = {"neck": 1, "finger1": 1, "finger2": 1}
GEAR_EMBELLISHMENT_ARMOR_SLOTS = ["head", "shoulder", "back", "chest", "wrist", "hands", "waist", "legs", "feet"]
GEAR_EMBELLISHMENT_JEWELRY_SLOTS = ["neck", "finger1", "finger2"]
GEAR_EMBELLISHMENT_WEAPON_SLOTS = ["main_hand", "off_hand"]
GEAR_EMBELLISHMENT_WEAPON_ARMOR_SLOTS = [
    *GEAR_EMBELLISHMENT_ARMOR_SLOTS,
    *GEAR_EMBELLISHMENT_WEAPON_SLOTS,
]
GEAR_EMBELLISHMENT_EQUIPMENT_SLOTS = [
    *GEAR_EMBELLISHMENT_ARMOR_SLOTS,
    *GEAR_EMBELLISHMENT_JEWELRY_SLOTS,
    *GEAR_EMBELLISHMENT_WEAPON_SLOTS,
]
GEAR_EMBELLISHMENT_SLOT_GROUPS = {
    "armor": [*GEAR_EMBELLISHMENT_ARMOR_SLOTS, "off_hand"],
    "jewelry": GEAR_EMBELLISHMENT_JEWELRY_SLOTS,
    "weapon": GEAR_EMBELLISHMENT_WEAPON_SLOTS,
    "weapon_offhand": GEAR_EMBELLISHMENT_WEAPON_SLOTS,
    "weapon_armor": GEAR_EMBELLISHMENT_WEAPON_ARMOR_SLOTS,
    "equipment": GEAR_EMBELLISHMENT_EQUIPMENT_SLOTS,
}

PVE_RANK_TWO_GEM_SEEDS = [
    ("240888", "无瑕迅捷榄石"),
    ("240890", "无瑕致命榄石"),
    ("240892", "无瑕精湛榄石"),
    ("240894", "无瑕万能榄石"),
    ("240896", "无瑕精湛紫晶"),
    ("240898", "无瑕致命紫晶"),
    ("240900", "无瑕迅捷紫晶"),
    ("240902", "无瑕万能紫晶"),
    ("240904", "无瑕致命榴石"),
    ("240906", "无瑕迅捷榴石"),
    ("240908", "无瑕精湛榴石"),
    ("240910", "无瑕万能榴石"),
    ("240912", "无瑕万能青金石"),
    ("240914", "无瑕致命青金石"),
    ("240916", "无瑕迅捷青金石"),
    ("240918", "无瑕精湛青金石"),
    ("240967", "强能之永歌钻石"),
    ("240969", "御土之永歌钻石"),
    ("240971", "坚韧之永歌钻石"),
    ("240983", "费解之永歌钻石"),
]

PVE_RANK_TWO_GEM_LIVE_TOOLTIPS = {
    "240888": "+17急速",
    "240890": "+16急速 +7暴击",
    "240892": "+16急速 +7精通",
    "240894": "+16急速 +7全能",
    "240896": "+17精通",
    "240898": "+16精通 +7暴击",
    "240900": "+16精通 +7急速",
    "240902": "+16精通 +7全能",
    "240904": "+17暴击",
    "240906": "+16暴击 +7急速",
    "240908": "+16暴击 +7精通",
    "240910": "+16暴击 +7全能",
    "240912": "+17全能",
    "240914": "+16全能 +7暴击",
    "240916": "+16全能 +7急速",
    "240918": "+16全能 +7精通",
    "240967": "+23主属性 每种不同的至暗之夜宝石颜色+0.15%暴击效果",
    "240969": "+23主属性 每种不同的至暗之夜宝石颜色+1%最大法力值",
    "240971": "+23主属性 +13护甲",
    "240983": "+32主属性",
}

PRIMARY_STAT_GEM_UNIQUE_GROUP = "primary_stat_gem"
PRIMARY_STAT_GEM_UNIQUE_LIMIT = 1
PRIMARY_STAT_GEM_IDS = frozenset(
    item_id for item_id, tooltip in PVE_RANK_TWO_GEM_LIVE_TOOLTIPS.items() if "主属性" in tooltip
)

MIDNIGHT_OPTIONAL_EMBELLISHMENT_SEEDS = [
    {
        "key": "arcanoweave_lining",
        "name": "奥纹内衬",
        "itemId": "240166",
        "spellId": "1228961",
        "simcDriverSpellIds": ["1283697", "1229511"],
        "wowheadSlug": "arcanoweave-lining",
        "slotGroup": "armor",
        "scopeEvidence": "Usable with Midnight recipes for most unembellished armor.",
    },
    {
        "key": "sunfire_silk_lining",
        "name": "阳炎丝绸内衬",
        "itemId": "240164",
        "spellId": "1228960",
        "simcDriverSpellIds": ["1241711", "1230364"],
        "wowheadSlug": "sunfire-silk-lining",
        "slotGroup": "armor",
        "scopeEvidence": "Usable with Midnight recipes for most unembellished armor.",
    },
    {
        "key": "blessed_pango_charm",
        "name": "圣佑穿山甲护符",
        "itemId": "244603",
        "spellId": "1237577",
        "simcDriverSpellIds": ["1259060", "1244243"],
        "wowheadSlug": "blessed-pango-charm",
        "slotGroup": "equipment",
        "scopeEvidence": "Usable with Midnight recipes for most unembellished equipment.",
        "methodListed": True,
    },
    {
        "key": "prismatic_focusing_iris",
        "name": "棱光聚焦之虹",
        "itemId": "251487",
        "spellId": "1230477",
        "simcDriverSpellIds": ["1251906", "1252383"],
        "wowheadSlug": "prismatic-focusing-iris",
        "slotGroup": "equipment",
        "scopeEvidence": "Usable with Midnight recipes for most unembellished equipment.",
    },
    {
        "key": "stabilizing_gemstone_bandolier",
        "name": "稳定式宝石弹药带",
        "itemId": "251489",
        "spellId": "1230478",
        "simcDriverSpellIds": ["1251905"],
        "wowheadSlug": "stabilizing-gemstone-bandolier",
        "slotGroup": "equipment",
        "scopeEvidence": "Usable with Midnight recipes for most unembellished equipment.",
    },
    {
        "key": "devouring_banding",
        "name": "吞噬绑带",
        "itemId": "244674",
        "spellId": "1237579",
        "simcDriverSpellIds": ["1244238", "1259213"],
        "wowheadSlug": "devouring-banding",
        "slotGroup": "weapon_armor",
        "scopeEvidence": "Usable with Midnight recipes for most unembellished weapons and armor.",
        "methodListed": True,
    },
    {
        "key": "primal_spore_binding",
        "name": "原始孢子缚带",
        "itemId": "244607",
        "spellId": "1237578",
        "simcDriverSpellIds": ["1244276", "1259124"],
        "wowheadSlug": "primal-spore-binding",
        "slotGroup": "weapon_armor",
        "scopeEvidence": "Usable with Midnight recipes for most unembellished weapons and armor.",
        "methodListed": True,
    },
    {
        "key": "darkmoon_sigil_blood",
        "name": "暗月徽记：鲜血",
        "itemId": "245871",
        "spellId": "1230074",
        "simcDriverSpellIds": ["1245001", "1245053"],
        "wowheadSlug": "darkmoon-sigil-blood",
        "slotGroup": "weapon_offhand",
        "scopeEvidence": "Usable with Midnight recipes for most unembellished weapons and off-hands.",
        "methodListed": True,
    },
    {
        "key": "darkmoon_sigil_hunt",
        "name": "暗月徽记：狩猎",
        "itemId": "245875",
        "spellId": "1230076",
        "simcDriverSpellIds": ["1245050", "1245054"],
        "wowheadSlug": "darkmoon-sigil-hunt",
        "slotGroup": "weapon_offhand",
        "scopeEvidence": "Usable with Midnight recipes for most unembellished weapons and off-hands.",
        "methodListed": True,
    },
    {
        "key": "darkmoon_sigil_rot",
        "name": "暗月徽记：腐朽",
        "itemId": "245877",
        "spellId": "1230075",
        "simcDriverSpellIds": ["1245055", "1245051"],
        "wowheadSlug": "darkmoon-sigil-rot",
        "slotGroup": "weapon_offhand",
        "scopeEvidence": "Usable with Midnight recipes for most unembellished weapons and off-hands.",
        "methodListed": True,
    },
    {
        "key": "darkmoon_sigil_void",
        "name": "暗月徽记：虚空",
        "itemId": "245873",
        "spellId": "1230077",
        "simcDriverSpellIds": ["1245052", "1244254"],
        "wowheadSlug": "darkmoon-sigil-void",
        "slotGroup": "weapon_offhand",
        "scopeEvidence": "Usable with Midnight recipes for most unembellished weapons and off-hands.",
        "methodListed": True,
    },
]


def pve_rank_two_gem_seed(item_id, name):
    item_id = str(item_id)
    stat_summary = PVE_RANK_TWO_GEM_LIVE_TOOLTIPS.get(item_id, "")
    payload = {
        "source": "server_owned_midnight_rank_two_gem_seed",
        "status": "verified",
        "itemId": item_id,
        "item_id": item_id,
        "gemItemId": item_id,
        "gem_item_id": item_id,
        "displayName": str(name),
        "displayLabel": stat_summary,
        "displayKind": "stat" if stat_summary else "",
        "displayStatus": "verified" if stat_summary else "",
        "statSummary": stat_summary,
        "statDisplayStatus": "verified_tooltip_override" if stat_summary else "",
        "quality": "Quality 2",
        "qualityRank": 2,
        "usageScope": "pve",
        "usage_scope": "pve",
        "evidenceSource": "wowhead_live_tooltip",
        "fallbackEvidenceSource": "wowhead_item+battle_net_item_metadata",
        "sourceRefs": [f"https://www.wowhead.com/item={item_id}"],
    }
    if item_id in PRIMARY_STAT_GEM_IDS:
        payload.update(
            {
                "uniqueEquipped": True,
                "uniqueGroup": PRIMARY_STAT_GEM_UNIQUE_GROUP,
                "uniqueLimit": PRIMARY_STAT_GEM_UNIQUE_LIMIT,
                "uniqueScope": "gear_socket",
            }
        )
    return {
        "id": f"seed-socket-gem-{item_id}-rank-2",
        "type": "socket",
        "name": str(name),
        "slots": list(SOCKET_OPTION_GEAR_SLOT_LIST),
        "simcOptions": {"gem_id": item_id},
        "status": "verified",
        "payload": payload,
    }


def midnight_optional_embellishment_seed(seed):
    key = str(seed["key"])
    item_id = str(seed["itemId"])
    spell_id = str(seed["spellId"])
    simc_driver_spell_ids = [str(value) for value in seed.get("simcDriverSpellIds") or [] if str(value or "").strip()]
    wowhead_slug = str(seed.get("wowheadSlug") or key.replace("_", "-"))
    slot_group = str(seed.get("slotGroup") or "").strip() or "equipment"
    slots = list(GEAR_EMBELLISHMENT_SLOT_GROUPS.get(slot_group) or [])
    evidence_source = "wowhead_item+simulationcraft+method" if seed.get("methodListed") else "wowhead_item+simulationcraft"
    source_refs = [
        f"https://www.wowhead.com/item={item_id}/{wowhead_slug}",
        f"https://www.wowhead.com/spell={spell_id}/{wowhead_slug}",
        "https://raw.githubusercontent.com/simulationcraft/simc/midnight/engine/player/unique_gear_midnight.cpp",
    ]
    if seed.get("methodListed"):
        source_refs.append("https://www.method.gg/guides/list-of-all-midnight-embellishments")
    return {
        "id": f"seed-embellishment-{key.replace('_', '-')}-rank-2",
        "type": "embellishment",
        "name": str(seed["name"]),
        "slots": slots,
        "simcOptions": {"embellishment": key},
        "status": "verified",
        "payload": {
            "source": "simulationcraft_wowhead_db2_seed",
            "status": "verified",
            "displayName": str(seed["name"]),
            "displayLabel": str(seed["name"]),
            "displayKind": "name",
            "displayStatus": "verified",
            "evidenceSource": evidence_source,
            "itemId": item_id,
            "item_id": item_id,
            "quality": "Quality 2",
            "qualityRank": 2,
            "slotGroup": slot_group,
            "simcKey": key,
            "simc_key": key,
            "bonusId": None,
            "bonus_id": None,
            "effectId": simc_driver_spell_ids[0] if simc_driver_spell_ids else spell_id,
            "effect_id": simc_driver_spell_ids[0] if simc_driver_spell_ids else spell_id,
            "spellId": spell_id,
            "spell_id": spell_id,
            "simcDriverSpellIds": simc_driver_spell_ids,
            "simc_driver_spell_ids": simc_driver_spell_ids,
            "db2Category": "Tradeskill / Optional Reagents",
            "db2_category": "Tradeskill / Optional Reagents",
            "db2ReagentItemId": item_id,
            "db2_reagent_item_id": item_id,
            "db2BonusTreeId": None,
            "db2_bonus_tree_id": None,
            "db2BonusTreeEvidence": (
                f"Wowhead item {item_id} is a Quality 2 +15 Recipe Difficulty optional reagent. "
                f"{str(seed.get('scopeEvidence') or '').strip()} SimulationCraft registers "
                f"Midnight embellishment special effect drivers {', '.join(simc_driver_spell_ids) or spell_id}."
            ),
            "sourceRefs": source_refs,
        },
    }


DEFAULT_GEAR_MOD_SEED = [
    *[pve_rank_two_gem_seed(item_id, name) for item_id, name in PVE_RANK_TWO_GEM_SEEDS],
    *[midnight_optional_embellishment_seed(seed) for seed in MIDNIGHT_OPTIONAL_EMBELLISHMENT_SEEDS],
]

GEAR_EMBELLISHMENT_LABELS_ZH = {
    "blue_silken_lining": "蓝色丝质内衬",
    "arcanoweave_lining": "奥纹内衬",
    "blessed_pango_charm": "圣佑穿山甲护符",
    "dawnthread_lining": "晖晨线内衬",
    "darkmoon_sigil_blood": "暗月徽记：鲜血",
    "darkmoon_sigil_hunt": "暗月徽记：狩猎",
    "darkmoon_sigil_rot": "暗月徽记：腐朽",
    "darkmoon_sigil_void": "暗月徽记：虚空",
    "devouring_banding": "吞噬绑带",
    "duskthread_lining": "萤暮线内衬",
    "elemental_focusing_lens": "元素焦镜",
    "primal_spore_binding": "原始孢子缚带",
    "prismatic_focusing_iris": "棱光聚焦之虹",
    "stabilizing_gemstone_bandolier": "稳定式宝石弹药带",
    "sunfire_silk_lining": "阳炎丝绸内衬",
}

GEAR_EMBELLISHMENT_EVIDENCE_SOURCES = {
    "blue_silken_lining": "server_owned_legacy_evidence_seed",
    "arcanoweave_lining": "wowhead_item+simulationcraft",
    "blessed_pango_charm": "wowhead_item+simulationcraft+method",
    "dawnthread_lining": "wowhead_item+simulationcraft",
    "darkmoon_sigil_blood": "wowhead_item+simulationcraft+method",
    "darkmoon_sigil_hunt": "wowhead_item+simulationcraft+method",
    "darkmoon_sigil_rot": "wowhead_item+simulationcraft+method",
    "darkmoon_sigil_void": "wowhead_item+simulationcraft+method",
    "devouring_banding": "wowhead_item+simulationcraft+method",
    "duskthread_lining": "wowhead_item+simulationcraft",
    "elemental_focusing_lens": "wowhead_item+simulationcraft",
    "primal_spore_binding": "wowhead_item+simulationcraft+method",
    "prismatic_focusing_iris": "wowhead_item+simulationcraft",
    "stabilizing_gemstone_bandolier": "wowhead_item+simulationcraft",
    "sunfire_silk_lining": "wowhead_item+simulationcraft",
}

def gear_embellishment_slot_group(option):
    if not isinstance(option, dict):
        return ""
    payload = option.get("payload") if isinstance(option.get("payload"), dict) else {}
    return str(option.get("slotGroup") or payload.get("slotGroup") or payload.get("slot_group") or "").strip().lower()


def gear_item_type_context(item):
    item = item if isinstance(item, dict) else {}
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    if not payload and isinstance(item.get("metadataPayload"), dict):
        payload = item["metadataPayload"]
    type_metadata = item_type_metadata_from_payload(payload) if payload else {}
    slot = normalize_slot(item.get("slot") or item.get("simcSlot") or type_metadata.get("slot") or "")
    armor_type = str(item.get("armorType") or type_metadata.get("armorType") or "").strip().lower()
    weapon_type = str(item.get("weaponType") or type_metadata.get("weaponType") or "").strip().lower()
    return slot, armor_type, weapon_type


def gear_item_is_shield(item):
    slot, armor_type, weapon_type = gear_item_type_context(item)
    return slot == "off_hand" and (weapon_type == "shield" or armor_type == "shield")


def gear_item_is_held_offhand(item):
    slot, _armor_type, weapon_type = gear_item_type_context(item)
    return slot == "off_hand" and weapon_type == "held in off-hand"


def normalized_config_category(value):
    return re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")


def gear_config_enchant_policy(option_name="", simc_options=None, payload=None):
    simc_options = simc_options if isinstance(simc_options, dict) else {}
    payload = payload if isinstance(payload, dict) else {}
    policy = {}

    def merge_policy(extra):
        if not isinstance(extra, dict):
            return
        for key, value in extra.items():
            if value not in (None, "", [], {}):
                policy[key] = value

    for key in (
        "configCategory",
        "config_category",
        "enchantCategory",
        "enchant_category",
        "category",
    ):
        category = normalized_config_category(payload.get(key))
        if category:
            policy["configCategory"] = category
            break
    for key in ("exclusionReason", "exclusion_reason", "blockReason", "block_reason"):
        reason = str(payload.get(key) or "").strip()
        if reason:
            policy["exclusionReason"] = reason
            break
    for key in ("itemTypeRule", "item_type_rule"):
        rule = normalized_config_category(payload.get(key))
        if rule:
            policy["itemTypeRule"] = rule
            break

    enchant_id = normalize_option_value(
        simc_options.get("enchant_id")
        or payload.get("enchant_id")
        or payload.get("enchantId")
        or payload.get("enchant")
    )
    merge_policy(GEAR_CONFIG_ENCHANT_ID_POLICIES.get(enchant_id))

    text = "\n".join(
        str(value or "")
        for value in (
            option_name,
            payload.get("displayName"),
            payload.get("displayLabel"),
            payload.get("name"),
            payload.get("label"),
        )
    ).lower()
    for rule in GEAR_CONFIG_ENCHANT_NAME_POLICIES:
        tokens = rule.get("tokens") or []
        if any(str(token or "").lower() and str(token or "").lower() in text for token in tokens):
            merge_policy(rule)
    if policy.get("configCategory"):
        policy["configCategory"] = normalized_config_category(policy.get("configCategory"))
    if policy.get("itemTypeRule"):
        policy["itemTypeRule"] = normalized_config_category(policy.get("itemTypeRule"))
    return policy


def gear_config_enchant_exclusion(option_name="", simc_options=None, payload=None):
    payload = payload if isinstance(payload, dict) else {}
    policy = gear_config_enchant_policy(option_name, simc_options, payload)
    category = normalized_config_category(policy.get("configCategory"))
    blocked = bool(
        category in GEAR_CONFIG_ENCHANT_EXCLUDED_CATEGORIES
        or payload.get("excludeFromGearConfig")
        or payload.get("exclude_from_gear_config")
        or payload.get("blocked")
        or policy.get("blocked")
    )
    if not blocked:
        return {}
    if not policy.get("exclusionReason"):
        policy["exclusionReason"] = f"{category or 'blocked'} is not a general gear enchant."
    return policy


def gear_config_enchant_exclusion_example(option_id, option_name, simc_options, payload):
    exclusion = gear_config_enchant_exclusion(option_name, simc_options, payload)
    example = {
        "optionId": str(option_id or "").strip(),
        "name": str(option_name or "").strip(),
    }
    enchant_id = normalize_option_value((simc_options or {}).get("enchant_id"))
    if enchant_id:
        example["simcValue"] = enchant_id
    if exclusion.get("configCategory"):
        example["configCategory"] = exclusion["configCategory"]
    if exclusion.get("exclusionReason"):
        example["exclusionReason"] = exclusion["exclusionReason"]
    return example


def gear_mod_option_payload_with_config_policy(option_type, option_name, simc_options, payload, slots=None):
    option_type = str(option_type or "").strip().lower()
    payload = dict(payload) if isinstance(payload, dict) else {}
    if option_type != "enchant":
        return payload
    slots = [normalize_slot(slot) for slot in (slots or [])]
    policy = gear_config_enchant_policy(option_name, simc_options, payload)
    for key in ("configCategory", "exclusionReason", "itemTypeRule"):
        if policy.get(key) not in (None, "", [], {}) and payload.get(key) in (None, "", [], {}):
            payload[key] = policy[key]
    if payload.get("itemTypeRule") in (None, "", [], {}) and any(slot in {"main_hand", "off_hand"} for slot in slots):
        payload["itemTypeRule"] = "weapon"
    return payload


def dual_wieldable_weapon_type(weapon_type):
    normalized = str(weapon_type or "").strip().lower()
    return normalized in {value.lower() for value in DUAL_WIELDABLE_WEAPON_TYPES}


def gear_item_is_dual_wieldable_offhand_weapon(item):
    slot, _armor_type, weapon_type = gear_item_type_context(item)
    return slot == "off_hand" and dual_wieldable_weapon_type(weapon_type)


def gear_enchant_option_item_type_rule(option):
    if not isinstance(option, dict):
        return ""
    payload = option.get("payload") if isinstance(option.get("payload"), dict) else {}
    policy = gear_config_enchant_policy(
        option.get("rawName") or option.get("name") or option.get("label") or "",
        option.get("simcOptions") if isinstance(option.get("simcOptions"), dict) else {},
        payload,
    )
    return normalized_config_category(
        option.get("itemTypeRule")
        or option.get("item_type_rule")
        or payload.get("itemTypeRule")
        or payload.get("item_type_rule")
        or policy.get("itemTypeRule")
    )


def gear_enchant_option_applies_to_item(option, item):
    if not isinstance(option, dict):
        return False
    payload = option.get("payload") if isinstance(option.get("payload"), dict) else {}
    simc_options = option.get("simcOptions") if isinstance(option.get("simcOptions"), dict) else {}
    option_name = option.get("rawName") or option.get("name") or option.get("label") or ""
    if gear_config_enchant_exclusion(option_name, simc_options, payload):
        return False
    slot, _armor_type, _weapon_type = gear_item_type_context(item)
    if slot != "off_hand":
        return True
    rule = gear_enchant_option_item_type_rule(option)
    if rule in {"any", "any_equipment", "equipment", "gear", "gear_slot"}:
        return True
    if rule in {"shield", "offhand_shield", "off_hand_shield"}:
        return gear_item_is_shield(item)
    if rule in {"held_offhand", "held_off_hand", "holdable", "invtype_holdable"}:
        return gear_item_is_held_offhand(item)
    return gear_item_is_dual_wieldable_offhand_weapon(item)


def gear_embellishment_option_applies_to_item(option, item):
    if not isinstance(option, dict):
        return False
    if item_builtin_embellishment_value(item):
        return False
    slot, _armor_type, _weapon_type = gear_item_type_context(item)
    slot_group = gear_embellishment_slot_group(option)
    if not slot_group:
        return True
    if slot_group == "equipment":
        return slot in GEAR_EMBELLISHMENT_EQUIPMENT_SLOTS
    if slot_group == "jewelry":
        return slot in GEAR_EMBELLISHMENT_JEWELRY_SLOTS
    if slot_group == "armor":
        return slot in GEAR_EMBELLISHMENT_ARMOR_SLOTS or gear_item_is_shield(item)
    if slot_group in {"weapon", "weapon_offhand"}:
        return slot == "main_hand" or gear_item_is_held_offhand(item)
    if slot_group == "weapon_armor":
        return (
            slot in GEAR_EMBELLISHMENT_ARMOR_SLOTS
            or slot == "main_hand"
            or gear_item_is_shield(item)
            or gear_item_is_held_offhand(item)
        )
    return slot in GEAR_EMBELLISHMENT_SLOT_GROUPS.get(slot_group, [])


DIFFICULTY_LABELS_ZH = {
    "normal": "普通",
    "heroic": "英雄",
    "mythic": "史诗",
    "lfr": "随机",
    "raid_finder": "随机",
    "mythic_plus": "大秘境",
    "mythicplus": "大秘境",
    "dungeon": "大秘境",
    "raid": "团本",
    "tier_set": "套装",
    "champion": "勇士",
    "hero": "英雄",
    "myth": "神话",
    "crafted_champion": "勇士",
    "crafted_hero": "英雄",
    "crafted_myth": "神话",
    "crafted_void_upgrade": "虚空晋升",
    "void_upgrade": "虚空晋升",
    "crafted": "制造装备",
    "source_pending": "来源待补",
    "observed_profile": "实装观测",
    "observed": "实装观测",
    "needs_variant": "难度待补",
    "needs-variant": "难度待补",
}

ITEM_STAT_LABELS_ZH = {
    "agiint": "敏捷 or 智力",
    "intagi": "敏捷 or 智力",
    "stragi": "力量 or 敏捷",
    "strint": "力量 or 智力",
    "stragiint": "力量/敏捷/智力",
    "intellect": "智力",
    "int": "智力",
    "agility": "敏捷",
    "agi": "敏捷",
    "strength": "力量",
    "str": "力量",
    "stamina": "耐力",
    "sta": "耐力",
    "crit": "暴击",
    "crit_rating": "暴击",
    "critical_strike": "暴击",
    "critical_strike_rating": "暴击",
    "haste": "急速",
    "haste_rating": "急速",
    "mastery": "精通",
    "mastery_rating": "精通",
    "versatility": "全能",
    "versatility_rating": "全能",
    "armor": "护甲",
    "avoidance": "闪避",
    "avoidance_rating": "闪避",
    "leech": "吸血",
    "leech_rating": "吸血",
    "speed": "速度",
    "speed_rating": "速度",
}

SIMC_GEAR_STAT_KEYS = [
    "stragiint",
    "stragi",
    "strint",
    "agiint",
    "intagi",
    "intellect",
    "agility",
    "strength",
    "stamina",
    "armor",
    "crit_rating",
    "critical_strike_rating",
    "haste_rating",
    "mastery_rating",
    "versatility_rating",
    "leech_rating",
    "avoidance_rating",
    "speed_rating",
    "crit",
    "critical_strike",
    "haste",
    "mastery",
    "versatility",
    "leech",
    "avoidance",
    "speed",
]

EQUIVALENT_GEAR_SLOTS = {
    "finger1": ["finger1", "finger2"],
    "finger2": ["finger1", "finger2"],
    "trinket1": ["trinket1", "trinket2"],
    "trinket2": ["trinket1", "trinket2"],
}

CORE_SIMC_GEAR_SLOTS = [
    slot for slot in CANONICAL_GEAR_SLOTS
    if slot != "off_hand"
]

GEAR_SLOTS = CANONICAL_GEAR_SLOTS

GEAR_SLOT_LABELS = {
    "head": "头部",
    "neck": "颈部",
    "shoulder": "肩部",
    "back": "背部",
    "chest": "胸部",
    "wrist": "腕部",
    "hands": "手部",
    "waist": "腰部",
    "legs": "腿部",
    "feet": "脚部",
    "finger1": "戒指 1",
    "finger2": "戒指 2",
    "trinket1": "饰品 1",
    "trinket2": "饰品 2",
    "main_hand": "主手",
    "off_hand": "副手",
}

GEAR_SLOT_ALIASES = {
    "wrist": "wrist",
    "wrists": "wrist",
    "bracer": "wrist",
    "bracers": "wrist",
    "shoulder": "shoulder",
    "shoulders": "shoulder",
    "cloak": "back",
    "weapon": "main_hand",
    "mainhand": "main_hand",
    "offhand": "off_hand",
    "ring1": "finger1",
    "ring2": "finger2",
    "finger_1": "finger1",
    "finger_2": "finger2",
    "trinket_1": "trinket1",
    "trinket_2": "trinket2",
}

SIMC_GEAR_OPTION_ALIASES = [
    ("ilevel", ["ilevel", "itemLevel", "item_level"]),
    ("bonus_id", ["bonus_id", "bonusId", "bonusIds", "bonusListIDs"]),
    ("gem_id", ["gem_id", "gemId", "gemIds"]),
    ("gem_bonus_id", ["gem_bonus_id", "gemBonusId", "gemBonusIds"]),
    ("gem_ilevel", ["gem_ilevel", "gemIlevel", "gemItemLevel", "gemItemLevels"]),
    ("enchant_id", ["enchant_id", "enchantId", "enchant"]),
    ("crafted_stats", ["crafted_stats", "craftedStats"]),
    ("embellishment", ["embellishment", "embellishmentId", "embellishment_id"]),
]

SIMC_GEAR_OPTION_KEYS = {key for key, _ in SIMC_GEAR_OPTION_ALIASES}
GEAR_MOD_OPTION_TYPES = {"socket", "enchant", "crafted_stats", "embellishment"}
BASE_ITEM_INSTANCE_OPTION_KEYS = ("bonus_id", "gem_id", "enchant_id", "crafted_stats")
ITEM_INSTANCE_OPTION_KEYS = (*BASE_ITEM_INSTANCE_OPTION_KEYS, "embellishment")
GEAR_ENHANCEMENT_SIMC_KEYS = ("gem_id", "gem_bonus_id", "gem_ilevel", "enchant_id", "embellishment")
GEAR_ENHANCEMENT_SNAPSHOT_REVISION = "websim-gear-enhancement-snapshot-v1"
SIMC_READY_SOURCE_TYPES = {"simcPreset"}
OFFICIAL_ITEM_LEVEL_TRACKS = [
    {"difficultyKey": "champion", "label": "勇士 263", "itemLevel": 263},
    {"difficultyKey": "hero", "label": "英雄 276", "itemLevel": 276},
    {"difficultyKey": "myth", "label": "神话 289", "itemLevel": 289},
]
OFFICIAL_VOID_UPGRADE_TRACK = {"difficultyKey": "void_upgrade", "label": "虚空晋升 298", "itemLevel": 298}
OFFICIAL_ITEM_LEVEL_PROBE_SOURCE = "simulationcraft_item_level_probe"
CRAFTED_ITEM_LEVEL_PROBE_SOURCE = "simulationcraft_crafted_item_probe"
PREEMBELLISHED_CRAFTED_ITEM_LEVEL_PROBE_SOURCE = "simulationcraft_preembellished_item_probe"
CRAFTED_PUBLIC_DIFFICULTY_KEYS = {
    "crafted_champion": "champion",
    "crafted_hero": "hero",
    "crafted_myth": "myth",
    "crafted_void_upgrade": "void_upgrade",
}
CRAFTED_ITEM_LEVEL_TRACKS = {
    "crafted_myth": {"difficultyKey": "crafted_myth", "label": "神话 285", "itemLevel": 285},
    "crafted_void_upgrade": {"difficultyKey": "crafted_void_upgrade", "label": "虚空晋升 295", "itemLevel": 295},
}
ENRICHABLE_SOURCE_TYPES = {"manual", "enriched", "manual/enriched", "custom"}

CLASS_ARMOR_TYPES = {
    "deathknight": "Plate",
    "demonhunter": "Leather",
    "druid": "Leather",
    "evoker": "Mail",
    "hunter": "Mail",
    "mage": "Cloth",
    "monk": "Leather",
    "paladin": "Plate",
    "priest": "Cloth",
    "rogue": "Leather",
    "shaman": "Mail",
    "warlock": "Cloth",
    "warrior": "Plate",
}

ARMOR_SLOTS = {"head", "shoulder", "chest", "wrist", "hands", "waist", "legs", "feet"}
ARMOR_ITEM_CLASS_IDS = {4}
ARMOR_CLASS_NAMES = {"armor", "\u62a4\u7532"}
ARMOR_SUBCLASS_TYPES = {
    1: "Cloth",
    2: "Leather",
    3: "Mail",
    4: "Plate",
    5: "Cosmetic",
    6: "Shield",
}
ARMOR_SUBCLASS_NAMES = {
    "cloth": "Cloth",
    "\u5e03\u7532": "Cloth",
    "leather": "Leather",
    "\u76ae\u7532": "Leather",
    "mail": "Mail",
    "\u9501\u7532": "Mail",
    "plate": "Plate",
    "\u677f\u7532": "Plate",
    "miscellaneous": "Miscellaneous",
    "\u5176\u4ed6": "Miscellaneous",
    "cosmetic": "Cosmetic",
    "\u5916\u89c2": "Cosmetic",
    "\u88c5\u9970\u54c1": "Cosmetic",
    "shield": "Shield",
    "\u76fe\u724c": "Shield",
}
WEAPON_SLOTS = {"main_hand", "off_hand"}
WEAPON_ITEM_CLASS_IDS = {2}
WEAPON_CLASS_NAMES = {"weapon", "\u6b66\u5668"}
SHIELD_CLASSES = {"paladin", "shaman", "warrior"}
HELD_OFFHAND_CLASSES = {"evoker", "mage", "priest", "warlock"}
HELD_OFFHAND_SPECS = {
    ("druid", "balance"),
    ("druid", "restoration"),
    ("monk", "mistweaver"),
    ("shaman", "elemental"),
    ("shaman", "restoration"),
}
DUAL_WIELDABLE_WEAPON_TYPES = {
    "Dagger",
    "Fist Weapon",
    "One-Handed Axe",
    "One-Handed Mace",
    "One-Handed Sword",
    "Warglaive",
}
ONE_HAND_WEAPON_TYPES = {
    "Dagger",
    "Fist Weapon",
    "One-Handed Axe",
    "One-Handed Mace",
    "One-Handed Sword",
    "Warglaive",
    "Wand",
}
TWO_HAND_WEAPON_TYPES = {
    "Two-Handed Axe",
    "Two-Handed Mace",
    "Two-Handed Sword",
    "Polearm",
    "Staff",
}
RANGED_WEAPON_TYPES = {"Bow", "Crossbow", "Gun"}
HELD_OFFHAND_WEAPON_TYPES = {"Held In Off-hand"}
SHIELD_WEAPON_TYPES = {"Shield"}
CLASS_WEAPON_TYPES = {
    "deathknight": {
        "One-Handed Axe",
        "Two-Handed Axe",
        "One-Handed Mace",
        "Two-Handed Mace",
        "Polearm",
        "One-Handed Sword",
        "Two-Handed Sword",
    },
    "demonhunter": {
        "Warglaive",
        "Fist Weapon",
        "One-Handed Axe",
        "One-Handed Sword",
    },
    "druid": {
        "Dagger",
        "Fist Weapon",
        "One-Handed Mace",
        "Two-Handed Mace",
        "Polearm",
        "Staff",
    },
    "evoker": {
        "Dagger",
        "Fist Weapon",
        "One-Handed Axe",
        "Two-Handed Axe",
        "One-Handed Mace",
        "Two-Handed Mace",
        "One-Handed Sword",
        "Two-Handed Sword",
        "Staff",
    },
    "hunter": {
        "One-Handed Axe",
        "Two-Handed Axe",
        "Bow",
        "Crossbow",
        "Dagger",
        "Fist Weapon",
        "Gun",
        "Polearm",
        "Staff",
        "One-Handed Sword",
        "Two-Handed Sword",
    },
    "mage": {
        "Wand",
        "Dagger",
        "One-Handed Sword",
        "Staff",
    },
    "monk": {
        "Fist Weapon",
        "One-Handed Axe",
        "One-Handed Mace",
        "One-Handed Sword",
        "Polearm",
        "Staff",
    },
    "paladin": {
        "One-Handed Axe",
        "Two-Handed Axe",
        "One-Handed Mace",
        "Two-Handed Mace",
        "One-Handed Sword",
        "Two-Handed Sword",
        "Polearm",
    },
    "priest": {
        "Dagger",
        "One-Handed Mace",
        "Staff",
        "Wand",
    },
    "rogue": {
        "Dagger",
        "Fist Weapon",
        "One-Handed Axe",
        "One-Handed Mace",
        "One-Handed Sword",
    },
    "shaman": {
        "Dagger",
        "Fist Weapon",
        "One-Handed Axe",
        "Two-Handed Axe",
        "One-Handed Mace",
        "Two-Handed Mace",
        "Staff",
    },
    "warlock": {
        "Dagger",
        "One-Handed Sword",
        "Staff",
        "Wand",
    },
    "warrior": {
        "Dagger",
        "Fist Weapon",
        "One-Handed Axe",
        "Two-Handed Axe",
        "One-Handed Mace",
        "Two-Handed Mace",
        "Polearm",
        "Staff",
        "One-Handed Sword",
        "Two-Handed Sword",
    },
}
SPEC_WEAPON_EQUIPMENT_RULES = {
    ("deathknight", "blood"): {
        "mode": "two_hand",
        "mainHandTypes": {"Two-Handed Axe", "Two-Handed Mace", "Two-Handed Sword", "Polearm"},
        "offHandTypes": set(),
    },
    ("deathknight", "frost"): {
        "mode": "selectable_two_hand_or_dual_wield_1h",
        "mainHandTypes": {
            "One-Handed Axe",
            "One-Handed Mace",
            "One-Handed Sword",
            "Two-Handed Axe",
            "Two-Handed Mace",
            "Two-Handed Sword",
            "Polearm",
        },
        "offHandTypes": {"One-Handed Axe", "One-Handed Mace", "One-Handed Sword"},
    },
    ("deathknight", "unholy"): {
        "mode": "two_hand",
        "mainHandTypes": {"Two-Handed Axe", "Two-Handed Mace", "Two-Handed Sword", "Polearm"},
        "offHandTypes": set(),
    },
    ("demonhunter", "devourer"): {
        "mode": "dual_wield_1h",
        "mainHandTypes": {"Warglaive", "Fist Weapon", "One-Handed Axe", "One-Handed Sword"},
        "offHandTypes": {"Warglaive", "Fist Weapon", "One-Handed Axe", "One-Handed Sword"},
    },
    ("demonhunter", "havoc"): {
        "mode": "dual_wield_1h",
        "mainHandTypes": {"Warglaive", "Fist Weapon", "One-Handed Axe", "One-Handed Sword"},
        "offHandTypes": {"Warglaive", "Fist Weapon", "One-Handed Axe", "One-Handed Sword"},
    },
    ("demonhunter", "vengeance"): {
        "mode": "dual_wield_1h",
        "mainHandTypes": {"Warglaive", "Fist Weapon", "One-Handed Axe", "One-Handed Sword"},
        "offHandTypes": {"Warglaive", "Fist Weapon", "One-Handed Axe", "One-Handed Sword"},
    },
    ("druid", "balance"): {
        "mode": "caster_1h_or_staff",
        "mainHandTypes": {"Staff", "Dagger", "One-Handed Mace"},
        "offHandTypes": {"Held In Off-hand"},
    },
    ("druid", "feral"): {
        "mode": "two_hand_agi",
        "mainHandTypes": {"Staff", "Polearm"},
        "offHandTypes": set(),
    },
    ("druid", "guardian"): {
        "mode": "two_hand_agi",
        "mainHandTypes": {"Staff", "Polearm"},
        "offHandTypes": set(),
    },
    ("druid", "restoration"): {
        "mode": "caster_1h_or_staff",
        "mainHandTypes": {"Staff", "Dagger", "One-Handed Mace"},
        "offHandTypes": {"Held In Off-hand"},
    },
    ("evoker", "augmentation"): {
        "mode": "caster_1h_or_staff",
        "mainHandTypes": {"Staff", "Dagger", "One-Handed Mace", "One-Handed Sword"},
        "offHandTypes": {"Held In Off-hand"},
    },
    ("evoker", "devastation"): {
        "mode": "caster_1h_or_staff",
        "mainHandTypes": {"Staff", "Dagger", "One-Handed Mace", "One-Handed Sword"},
        "offHandTypes": {"Held In Off-hand"},
    },
    ("evoker", "preservation"): {
        "mode": "caster_1h_or_staff",
        "mainHandTypes": {"Staff", "Dagger", "One-Handed Mace", "One-Handed Sword"},
        "offHandTypes": {"Held In Off-hand"},
    },
    ("hunter", "beast_mastery"): {
        "mode": "ranged",
        "mainHandTypes": {"Bow", "Crossbow", "Gun"},
        "offHandTypes": set(),
    },
    ("hunter", "marksmanship"): {
        "mode": "ranged",
        "mainHandTypes": {"Bow", "Crossbow", "Gun"},
        "offHandTypes": set(),
    },
    ("hunter", "survival"): {
        "mode": "melee_weapon",
        "mainHandTypes": {"Polearm", "Staff", "Two-Handed Axe", "Two-Handed Sword", "Dagger", "One-Handed Axe", "One-Handed Sword"},
        "offHandTypes": set(),
    },
    ("mage", "arcane"): {
        "mode": "caster_1h_or_staff",
        "mainHandTypes": {"Staff", "Dagger", "One-Handed Sword", "Wand"},
        "offHandTypes": {"Held In Off-hand"},
    },
    ("mage", "fire"): {
        "mode": "caster_1h_or_staff",
        "mainHandTypes": {"Staff", "Dagger", "One-Handed Sword", "Wand"},
        "offHandTypes": {"Held In Off-hand"},
    },
    ("mage", "frost"): {
        "mode": "caster_1h_or_staff",
        "mainHandTypes": {"Staff", "Dagger", "One-Handed Sword", "Wand"},
        "offHandTypes": {"Held In Off-hand"},
    },
    ("monk", "brewmaster"): {
        "mode": "selectable_two_hand_or_dual_wield_1h",
        "mainHandTypes": {"Staff", "Polearm", "Fist Weapon", "One-Handed Axe", "One-Handed Mace", "One-Handed Sword"},
        "offHandTypes": {"Fist Weapon", "One-Handed Axe", "One-Handed Mace", "One-Handed Sword"},
    },
    ("monk", "mistweaver"): {
        "mode": "healer_1h_or_staff",
        "mainHandTypes": {"Staff", "One-Handed Mace", "One-Handed Sword"},
        "offHandTypes": {"Held In Off-hand"},
    },
    ("monk", "windwalker"): {
        "mode": "selectable_two_hand_or_dual_wield_1h",
        "mainHandTypes": {"Staff", "Polearm", "Fist Weapon", "One-Handed Axe", "One-Handed Mace", "One-Handed Sword"},
        "offHandTypes": {"Fist Weapon", "One-Handed Axe", "One-Handed Mace", "One-Handed Sword"},
    },
    ("paladin", "holy"): {
        "mode": "shield_caster",
        "mainHandTypes": {"One-Handed Mace", "One-Handed Sword"},
        "offHandTypes": {"Shield"},
    },
    ("paladin", "protection"): {
        "mode": "shield_tank",
        "mainHandTypes": {"One-Handed Axe", "One-Handed Mace", "One-Handed Sword"},
        "offHandTypes": {"Shield"},
    },
    ("paladin", "retribution"): {
        "mode": "two_hand",
        "mainHandTypes": {"Two-Handed Axe", "Two-Handed Mace", "Two-Handed Sword", "Polearm"},
        "offHandTypes": set(),
    },
    ("priest", "discipline"): {
        "mode": "caster_1h_or_staff",
        "mainHandTypes": {"Staff", "Dagger", "One-Handed Mace", "Wand"},
        "offHandTypes": {"Held In Off-hand"},
    },
    ("priest", "holy"): {
        "mode": "caster_1h_or_staff",
        "mainHandTypes": {"Staff", "Dagger", "One-Handed Mace", "Wand"},
        "offHandTypes": {"Held In Off-hand"},
    },
    ("priest", "shadow"): {
        "mode": "caster_1h_or_staff",
        "mainHandTypes": {"Staff", "Dagger", "One-Handed Mace", "Wand"},
        "offHandTypes": {"Held In Off-hand"},
    },
    ("rogue", "assassination"): {
        "mode": "dual_wield_dagger",
        "mainHandTypes": {"Dagger"},
        "offHandTypes": {"Dagger"},
    },
    ("rogue", "outlaw"): {
        "mode": "dual_wield_1h",
        "mainHandTypes": {"Fist Weapon", "One-Handed Axe", "One-Handed Mace", "One-Handed Sword"},
        "offHandTypes": {"Fist Weapon", "One-Handed Axe", "One-Handed Mace", "One-Handed Sword"},
    },
    ("rogue", "subtlety"): {
        "mode": "dual_wield_dagger",
        "mainHandTypes": {"Dagger"},
        "offHandTypes": {"Dagger"},
    },
    ("shaman", "elemental"): {
        "mode": "caster_shield_or_holdable",
        "mainHandTypes": {"Staff", "Dagger", "One-Handed Mace"},
        "offHandTypes": {"Shield", "Held In Off-hand"},
    },
    ("shaman", "enhancement"): {
        "mode": "dual_wield_1h",
        "mainHandTypes": {"Fist Weapon", "One-Handed Axe", "One-Handed Mace"},
        "offHandTypes": {"Fist Weapon", "One-Handed Axe", "One-Handed Mace"},
    },
    ("shaman", "restoration"): {
        "mode": "caster_shield_or_holdable",
        "mainHandTypes": {"Staff", "Dagger", "One-Handed Mace"},
        "offHandTypes": {"Shield", "Held In Off-hand"},
    },
    ("warlock", "affliction"): {
        "mode": "caster_1h_or_staff",
        "mainHandTypes": {"Staff", "Dagger", "One-Handed Sword", "Wand"},
        "offHandTypes": {"Held In Off-hand"},
    },
    ("warlock", "demonology"): {
        "mode": "caster_1h_or_staff",
        "mainHandTypes": {"Staff", "Dagger", "One-Handed Sword", "Wand"},
        "offHandTypes": {"Held In Off-hand"},
    },
    ("warlock", "destruction"): {
        "mode": "caster_1h_or_staff",
        "mainHandTypes": {"Staff", "Dagger", "One-Handed Sword", "Wand"},
        "offHandTypes": {"Held In Off-hand"},
    },
    ("warrior", "arms"): {
        "mode": "two_hand",
        "mainHandTypes": {"Two-Handed Axe", "Two-Handed Mace", "Two-Handed Sword", "Polearm"},
        "offHandTypes": set(),
    },
    ("warrior", "fury"): {
        "mode": "dual_wield_2h",
        "mainHandTypes": {"Two-Handed Axe", "Two-Handed Mace", "Two-Handed Sword"},
        "offHandTypes": {"Two-Handed Axe", "Two-Handed Mace", "Two-Handed Sword"},
    },
    ("warrior", "protection"): {
        "mode": "shield_tank",
        "mainHandTypes": {"One-Handed Axe", "One-Handed Mace", "One-Handed Sword"},
        "offHandTypes": {"Shield"},
    },
}
PRIMARY_STAT_LABELS_ZH = {
    "strength": "力量",
    "agility": "敏捷",
    "intellect": "智力",
}
PRIMARY_STAT_KEYS = set(PRIMARY_STAT_LABELS_ZH)
PRIMARY_STAT_HYBRID_PATTERNS = {
    "stragi": {"strength", "agility"},
    "agistr": {"strength", "agility"},
    "strengthagility": {"strength", "agility"},
    "agilitystrength": {"strength", "agility"},
    "strint": {"strength", "intellect"},
    "intstr": {"strength", "intellect"},
    "strengthintellect": {"strength", "intellect"},
    "intellectstrength": {"strength", "intellect"},
    "agiint": {"agility", "intellect"},
    "intagi": {"agility", "intellect"},
    "agilityintellect": {"agility", "intellect"},
    "intellectagility": {"agility", "intellect"},
    "stragiint": {"strength", "agility", "intellect"},
    "strintagi": {"strength", "agility", "intellect"},
    "agistrint": {"strength", "agility", "intellect"},
    "agiintstr": {"strength", "agility", "intellect"},
    "intstragi": {"strength", "agility", "intellect"},
    "intagistr": {"strength", "agility", "intellect"},
    "strengthagilityintellect": {"strength", "agility", "intellect"},
    "strengthintellectagility": {"strength", "agility", "intellect"},
    "agilitystrengthintellect": {"strength", "agility", "intellect"},
    "agilityintellectstrength": {"strength", "agility", "intellect"},
    "intellectstrengthagility": {"strength", "agility", "intellect"},
    "intellectagilitystrength": {"strength", "agility", "intellect"},
}
GEM_ITEM_CLASS_IDS = {3}
GEM_CLASS_NAMES = {"gem", "\u5b9d\u77f3"}
WEAPON_SUBCLASS_TYPES = {
    0: "One-Handed Axe",
    1: "Two-Handed Axe",
    2: "Bow",
    3: "Gun",
    4: "One-Handed Mace",
    5: "Two-Handed Mace",
    6: "Polearm",
    7: "One-Handed Sword",
    8: "Two-Handed Sword",
    9: "Warglaive",
    10: "Staff",
    13: "Fist Weapon",
    15: "Dagger",
    18: "Crossbow",
    19: "Wand",
    20: "Fishing Pole",
}
WEAPON_SUBCLASS_NAMES = {
    "axe": "One-Handed Axe",
    "one_handed_axe": "One-Handed Axe",
    "one-handed axe": "One-Handed Axe",
    "\u5355\u624b\u65a7": "One-Handed Axe",
    "two_handed_axe": "Two-Handed Axe",
    "two-handed axe": "Two-Handed Axe",
    "\u53cc\u624b\u65a7": "Two-Handed Axe",
    "bow": "Bow",
    "\u5f13": "Bow",
    "gun": "Gun",
    "\u67aa": "Gun",
    "mace": "One-Handed Mace",
    "one_handed_mace": "One-Handed Mace",
    "one-handed mace": "One-Handed Mace",
    "\u5355\u624b\u9524": "One-Handed Mace",
    "two_handed_mace": "Two-Handed Mace",
    "two-handed mace": "Two-Handed Mace",
    "\u53cc\u624b\u9524": "Two-Handed Mace",
    "polearm": "Polearm",
    "\u957f\u67c4\u6b66\u5668": "Polearm",
    "sword": "One-Handed Sword",
    "one_handed_sword": "One-Handed Sword",
    "one-handed sword": "One-Handed Sword",
    "\u5355\u624b\u5251": "One-Handed Sword",
    "two_handed_sword": "Two-Handed Sword",
    "two-handed sword": "Two-Handed Sword",
    "\u53cc\u624b\u5251": "Two-Handed Sword",
    "warglaive": "Warglaive",
    "warglaives": "Warglaive",
    "war_glaive": "Warglaive",
    "war_glaives": "Warglaive",
    "war glaive": "Warglaive",
    "war glaives": "Warglaive",
    "\u6218\u5203": "Warglaive",
    "staff": "Staff",
    "\u6cd5\u6756": "Staff",
    "fist_weapon": "Fist Weapon",
    "fist weapon": "Fist Weapon",
    "\u62f3\u5957": "Fist Weapon",
    "dagger": "Dagger",
    "\u5315\u9996": "Dagger",
    "crossbow": "Crossbow",
    "\u5f29": "Crossbow",
    "wand": "Wand",
    "\u9b54\u6756": "Wand",
}

SCENARIOS = [
    {"key": "single", "title": "单体", "fightStyle": "Patchwerk", "targets": 1, "durationSeconds": 300},
    {"key": "aoe_5", "title": "5目标AOE", "fightStyle": "Patchwerk", "targets": 5, "durationSeconds": 300},
    {"key": "mythic_plus", "title": "近似大秘境", "fightStyle": "DungeonSlice", "targets": 5, "durationSeconds": 360},
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


def emit_sync_stage(stages, callback, stage, status, started_at=None, details=None):
    event = {
        "stage": stage,
        "status": status,
        "checkedAt": utc_now(),
    }
    if started_at is not None:
        event["durationSeconds"] = round(max(0.0, time.monotonic() - started_at), 3)
    if isinstance(details, dict) and details:
        event.update(details)
    stages.append(event)
    if callback:
        callback(dict(event))
    return time.monotonic()


def int_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def websim_max_level():
    return int_env("WOW_WEBSIM_MAX_LEVEL", 90)


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def normalized_websim_level(value=None):
    try:
        text = normalize_option_value(value) if value not in (None, "") else ""
        return clamp(int(text or websim_max_level()), 1, websim_max_level())
    except (TypeError, ValueError):
        return clamp(websim_max_level(), 1, websim_max_level())


def slugify(value, fallback="item"):
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
    return text[:80] if text else fallback


def simc_item_name_is_placeholder(value, item_id=""):
    item_id = normalize_option_value(item_id)
    name = slugify(value, "")
    if not name:
        return True
    if name in {"item", "selected_item"}:
        return True
    return bool(item_id and name == f"item_{item_id}")


def canonical_simc_item_name(value, item_id=""):
    name = slugify(str(value or "").replace("'", "").replace("\u2019", ""), "")
    if not name or simc_item_name_is_placeholder(name, item_id):
        return ""
    return name


def canonical_simc_item_name_from_record(record, item_id=""):
    if not isinstance(record, dict):
        return ""
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    metadata = payload.get("_metadata") if isinstance(payload.get("_metadata"), dict) else {}
    candidates = [
        record.get("englishName"),
        metadata.get("englishName"),
        record.get("itemName"),
        record.get("name"),
        record.get("displayName"),
        record.get("localizedName"),
        payload.get("englishName"),
        payload.get("name"),
    ]
    for candidate in candidates:
        name = canonical_simc_item_name(candidate, item_id)
        if name:
            return name
    return ""


def normalized_item_alias(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def safe_json_loads(value, fallback=None):
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback if fallback is not None else {}


def unique_text_list(values):
    result = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def fallback_text_for(value, fallback="?"):
    text = str(value or "").strip()
    if not text:
        return fallback
    if re.match(r"^[A-Za-z]{2,}$", text):
        return text[:2].upper()
    return text[:1].upper()


def normalize_game_asset_source(source):
    text = str(source or "").strip()
    if text == ITEM_METADATA_SOURCE or "battle.net" in text.lower() or "blizzard" in text.lower():
        return "blizzard"
    normalized = re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_")
    return normalized or "unknown"


def is_blizzard_icon_url(icon_url):
    try:
        hostname = (urlparse(str(icon_url or "")).hostname or "").lower()
    except ValueError:
        return False
    return hostname in BLIZZARD_ICON_HOSTS


def spell_icon_asset_source_status(icon_url, spell_detail_payload=None, fallback_source="simulationcraft"):
    detail_payload = spell_detail_payload if isinstance(spell_detail_payload, dict) else {}
    detail_source = str(detail_payload.get("source") or "").strip()
    if detail_source:
        normalized = normalize_game_asset_source(detail_source)
        return detail_source, "verified" if normalized == "blizzard" else "partial"
    if is_blizzard_icon_url(icon_url):
        return "blizzard", "verified"
    return fallback_source or "simulationcraft", "partial" if icon_url else "fallback"


def game_asset_id(entity_type, entity_id, context_key):
    return f"{entity_type}:{entity_id}:{context_key or 'default'}"


def game_asset_from_icon_url(
    entity_type,
    entity_id,
    context_key,
    icon_url,
    *,
    asset_type="icon",
    source="unknown",
    status="fallback",
    semantic_tags=None,
    usage=None,
    fallback_text="?",
):
    entity_type = re.sub(r"[^a-z0-9_]+", "_", str(entity_type or "unknown").lower()).strip("_") or "unknown"
    entity_id = str(entity_id or "unknown").strip() or "unknown"
    context_key = str(context_key or "default").strip() or "default"
    icon_url = str(icon_url or "").strip()
    return {
        "id": game_asset_id(entity_type, entity_id, context_key),
        "entityType": entity_type,
        "entityId": entity_id,
        "contextKey": context_key,
        "assetType": str(asset_type or "icon"),
        "iconUrl": icon_url,
        "resolutionTier": GAME_ASSET_RESOLUTION_TIER,
        "source": normalize_game_asset_source(source),
        "status": status if icon_url else "missing",
        "semanticTags": unique_text_list(semantic_tags or []),
        "usage": unique_text_list(usage or []),
        "fallbackText": str(fallback_text or "?")[:12],
    }


def normalize_game_asset(value, fallback):
    asset = dict(value) if isinstance(value, dict) else {}
    base = dict(fallback or {})
    if not asset:
        return base
    for key, fallback_value in base.items():
        if key not in asset or asset.get(key) in (None, ""):
            asset[key] = fallback_value
    asset["semanticTags"] = unique_text_list(asset.get("semanticTags") or base.get("semanticTags") or [])
    asset["usage"] = unique_text_list(asset.get("usage") or base.get("usage") or [])
    asset["source"] = normalize_game_asset_source(asset.get("source") or base.get("source"))
    asset["resolutionTier"] = asset.get("resolutionTier") or GAME_ASSET_RESOLUTION_TIER
    asset["status"] = asset.get("status") or ("fallback" if asset.get("iconUrl") else "missing")
    return asset


def upsert_websim_asset(conn, asset):
    if not isinstance(asset, dict) or not asset.get("id"):
        return None
    ensure_websim_tables(conn)
    now = utc_now()
    conn.execute(
        """
        INSERT INTO websim_asset_registry (
            id, entity_type, entity_id, context_key, asset_type, icon_url, resolution_tier,
            source, status, semantic_tags_json, usage_json, fallback_text, payload_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            entity_type=excluded.entity_type,
            entity_id=excluded.entity_id,
            context_key=excluded.context_key,
            asset_type=excluded.asset_type,
            icon_url=excluded.icon_url,
            resolution_tier=excluded.resolution_tier,
            source=excluded.source,
            status=excluded.status,
            semantic_tags_json=excluded.semantic_tags_json,
            usage_json=excluded.usage_json,
            fallback_text=excluded.fallback_text,
            payload_json=excluded.payload_json,
            updated_at=excluded.updated_at
        WHERE
            CASE excluded.status
                WHEN 'verified' THEN 4
                WHEN 'partial' THEN 3
                WHEN 'source_reference' THEN 2
                WHEN 'fallback' THEN 1
                ELSE 0
            END >=
            CASE websim_asset_registry.status
                WHEN 'verified' THEN 4
                WHEN 'partial' THEN 3
                WHEN 'source_reference' THEN 2
                WHEN 'fallback' THEN 1
                ELSE 0
            END
        """,
        (
            asset["id"],
            asset.get("entityType") or "",
            asset.get("entityId") or "",
            asset.get("contextKey") or "",
            asset.get("assetType") or "icon",
            asset.get("iconUrl") or "",
            asset.get("resolutionTier") or GAME_ASSET_RESOLUTION_TIER,
            asset.get("source") or "unknown",
            asset.get("status") or "missing",
            json.dumps(asset.get("semanticTags") or [], ensure_ascii=False),
            json.dumps(asset.get("usage") or [], ensure_ascii=False),
            asset.get("fallbackText") or "?",
            json.dumps(asset, ensure_ascii=False),
            now,
        ),
    )
    return asset


def game_asset_from_registry_row(row):
    payload = safe_json_loads(row[12], {}) if len(row) > 12 else {}
    asset = {
        "id": row[0],
        "entityType": row[1],
        "entityId": row[2],
        "contextKey": row[3],
        "assetType": row[4],
        "iconUrl": row[5],
        "resolutionTier": row[6],
        "source": row[7],
        "status": row[8],
        "semanticTags": safe_json_loads(row[9], []),
        "usage": safe_json_loads(row[10], []),
        "fallbackText": row[11],
    }
    if isinstance(payload, dict):
        asset.update({key: value for key, value in payload.items() if key not in asset or asset.get(key) in (None, "")})
        asset["semanticTags"] = unique_text_list(asset.get("semanticTags") or [])
        asset["usage"] = unique_text_list(asset.get("usage") or [])
    return asset


def get_websim_assets(conn, filters=None):
    ensure_websim_tables(conn)
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
        where.append(f"{column} = ?")
        params.append(str(value))
    query = """
        SELECT id, entity_type, entity_id, context_key, asset_type, icon_url, resolution_tier,
               source, status, semantic_tags_json, usage_json, fallback_text, payload_json
        FROM websim_asset_registry
    """
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY entity_type, entity_id, context_key LIMIT ?"
    try:
        limit = max(1, min(int(filters.get("limit") or 200), 1000))
    except (TypeError, ValueError):
        limit = 200
    rows = conn.execute(query, [*params, limit]).fetchall()
    assets = [game_asset_from_registry_row(row) for row in rows]
    counts = {"byStatus": {}, "bySource": {}}
    for asset in assets:
        counts["byStatus"][asset["status"]] = counts["byStatus"].get(asset["status"], 0) + 1
        counts["bySource"][asset["source"]] = counts["bySource"].get(asset["source"], 0) + 1
    return {"assets": assets, "counts": counts}


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
        CREATE TABLE IF NOT EXISTS websim_item_aliases (
            id TEXT PRIMARY KEY,
            alias_key TEXT NOT NULL,
            alias_text TEXT NOT NULL,
            item_id TEXT NOT NULL,
            display_name TEXT NOT NULL,
            icon_url TEXT NOT NULL,
            source_locale TEXT NOT NULL,
            target_locale TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_websim_item_aliases_alias_key ON websim_item_aliases(alias_key)")
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
        CREATE TABLE IF NOT EXISTS websim_gear_sources (
            id TEXT PRIMARY KEY,
            item_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_label TEXT NOT NULL,
            instance_id TEXT NOT NULL DEFAULT '',
            encounter_id TEXT NOT NULL DEFAULT '',
            difficulty_key TEXT NOT NULL DEFAULT '',
            season_revision TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_websim_gear_sources_item
        ON websim_gear_sources (item_id, source_type, difficulty_key)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS websim_gear_variants (
            id TEXT PRIMARY KEY,
            item_id TEXT NOT NULL,
            slot TEXT NOT NULL,
            variant_key TEXT NOT NULL,
            label TEXT NOT NULL,
            source_type TEXT NOT NULL,
            difficulty_key TEXT NOT NULL DEFAULT '',
            item_level INTEGER NOT NULL DEFAULT 0,
            simc_options_json TEXT NOT NULL,
            status TEXT NOT NULL,
            blockers_json TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_websim_gear_variants_item
        ON websim_gear_variants (item_id, slot, status)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS websim_gear_mod_options (
            id TEXT PRIMARY KEY,
            option_type TEXT NOT NULL,
            name TEXT NOT NULL,
            applicable_slots_json TEXT NOT NULL,
            simc_options_json TEXT NOT NULL,
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_websim_gear_mod_options_type
        ON websim_gear_mod_options (option_type, status)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS websim_item_sets (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            season_revision TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS websim_item_set_items (
            id TEXT PRIMARY KEY,
            set_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            name TEXT NOT NULL,
            slot TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_websim_item_set_items_set
        ON websim_item_set_items (set_id, item_id)
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
        CREATE TABLE IF NOT EXISTS websim_community_talent_templates (
            id TEXT PRIMARY KEY,
            class_key TEXT NOT NULL,
            spec_key TEXT NOT NULL,
            hero_key TEXT NOT NULL,
            scenario_key TEXT NOT NULL,
            name TEXT NOT NULL,
            flow_label TEXT NOT NULL,
            source_key TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            raw_import_code TEXT NOT NULL,
            websim_export_code TEXT NOT NULL,
            talent_state_json TEXT NOT NULL,
            sample_count INTEGER NOT NULL DEFAULT 0,
            max_key_level INTEGER NOT NULL DEFAULT 0,
            analysis_window TEXT NOT NULL,
            source_status TEXT NOT NULL,
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_websim_community_talent_templates_selection
        ON websim_community_talent_templates (class_key, spec_key, hero_key, scenario_key, status)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_websim_community_talent_templates_class_status
        ON websim_community_talent_templates (class_key, status, max_key_level, sample_count)
        """
    )
    ensure_table_columns(conn, "websim_community_talent_templates", {
        "signature": "TEXT NOT NULL DEFAULT ''",
        "source_refs_json": "TEXT NOT NULL DEFAULT '[]'",
        "scan_run_id": "TEXT NOT NULL DEFAULT ''",
    })
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_websim_community_talent_templates_signature
        ON websim_community_talent_templates (class_key, spec_key, hero_key, signature, status)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS websim_community_gear_templates (
            id TEXT PRIMARY KEY,
            class_key TEXT NOT NULL,
            spec_key TEXT NOT NULL,
            name TEXT NOT NULL,
            source_key TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_status TEXT NOT NULL,
            status TEXT NOT NULL,
            signature TEXT NOT NULL,
            source_refs_json TEXT NOT NULL,
            gear_items_json TEXT NOT NULL,
            raw_string TEXT NOT NULL,
            ready_slot_count INTEGER NOT NULL DEFAULT 0,
            missing_slots_json TEXT NOT NULL,
            analysis_window TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            scan_run_id TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_websim_community_gear_templates_lookup
        ON websim_community_gear_templates (class_key, spec_key, status, signature)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS community_template_sync_runs (
            id TEXT PRIMARY KEY,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            source_status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            scan_coverage_json TEXT NOT NULL,
            talent_counts_json TEXT NOT NULL,
            gear_counts_json TEXT NOT NULL,
            source_refs_json TEXT NOT NULL,
            payload_json TEXT NOT NULL
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
        CREATE TABLE IF NOT EXISTS websim_asset_registry (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            context_key TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            icon_url TEXT NOT NULL,
            resolution_tier TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            semantic_tags_json TEXT NOT NULL,
            usage_json TEXT NOT NULL,
            fallback_text TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_websim_asset_registry_entity
        ON websim_asset_registry (entity_type, entity_id, context_key)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_websim_asset_registry_status
        ON websim_asset_registry (status, source)
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


def ensure_table_columns(conn, table_name, columns):
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    for column_name, definition in columns.items():
        if column_name in existing:
            continue
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def get_sync_state(conn, key):
    row = conn.execute("SELECT value_json, updated_at FROM websim_sync_state WHERE key = ?", (key,)).fetchone()
    if not row:
        return {}
    value = safe_json_loads(row[0], {})
    if isinstance(value, dict):
        value["updatedAt"] = row[1]
    return value


def gear_observed_backfill_target_ids(target_item_ids):
    result = []
    seen = set()
    for item_id in target_item_ids or []:
        normalized = str(item_id or "").strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def gear_observed_backfill_target_hash(target_item_ids):
    return hashlib.sha256(
        json.dumps(gear_observed_backfill_target_ids(target_item_ids), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def int_or_zero(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def normalize_gear_observed_backfill_state(raw_state=None, target_item_ids=None, provider=None):
    raw_state = raw_state if isinstance(raw_state, dict) else {}
    provider = str(provider or raw_state.get("provider") or "raiderio").strip() or "raiderio"
    raw_cursor = raw_state.get("cursor") if isinstance(raw_state.get("cursor"), dict) else {}
    has_target_item_context = target_item_ids is not None
    target_ids = gear_observed_backfill_target_ids(target_item_ids)
    target_hash = gear_observed_backfill_target_hash(target_ids) if has_target_item_context else (
        raw_cursor.get("targetItemHash") or gear_observed_backfill_target_hash([])
    )
    target_count = len(target_ids) if has_target_item_context else int_or_zero(raw_cursor.get("targetItemCount"))
    reset_cursor = has_target_item_context and raw_cursor.get("targetItemHash") != target_hash
    providers = raw_state.get("providers") if isinstance(raw_state.get("providers"), dict) else {}
    raiderio_provider = providers.get("raiderio") if isinstance(providers.get("raiderio"), dict) else {}
    wcl_provider = providers.get("wcl") if isinstance(providers.get("wcl"), dict) else {}
    state = {
        "schemaVersion": GEAR_OBSERVED_BACKFILL_SCHEMA_VERSION,
        "provider": provider,
        "providers": {
            "raiderio": {"status": raiderio_provider.get("status") or "idle"},
            "wcl": {"status": wcl_provider.get("status") or "not_implemented"},
        },
        "cursor": {
            "targetItemHash": target_hash,
            "targetItemCount": target_count,
            "targetOffset": 0 if reset_cursor else int_or_zero(raw_cursor.get("targetOffset")),
            "profileOffset": 0 if reset_cursor else int_or_zero(raw_cursor.get("profileOffset")),
        },
        "lastRunStatus": raw_state.get("lastRunStatus") or "idle",
        "lastRunStartedAt": raw_state.get("lastRunStartedAt"),
        "lastRunFinishedAt": raw_state.get("lastRunFinishedAt"),
        "processedTargetItemCount": int_or_zero(raw_state.get("processedTargetItemCount")),
        "processedProfileCount": int_or_zero(raw_state.get("processedProfileCount")),
        "simcProfileCount": int_or_zero(raw_state.get("simcProfileCount")),
        "simcResolvedProfileCount": int_or_zero(raw_state.get("simcResolvedProfileCount")),
        "simcResolvedSlotCount": int_or_zero(raw_state.get("simcResolvedSlotCount")),
        "matchedTargetItemIds": [] if reset_cursor else gear_observed_backfill_target_ids(raw_state.get("matchedTargetItemIds")),
        "lastError": raw_state.get("lastError"),
    }
    if raw_state.get("updatedAt"):
        state["updatedAt"] = raw_state.get("updatedAt")
    if raw_state.get("wrappedAt") and not reset_cursor:
        state["wrappedAt"] = raw_state.get("wrappedAt")
    return state


def read_gear_observed_backfill_state(conn, target_item_ids=None, provider=None):
    ensure_websim_tables(conn)
    return normalize_gear_observed_backfill_state(
        get_sync_state(conn, GEAR_OBSERVED_BACKFILL_SYNC_KEY),
        target_item_ids=target_item_ids,
        provider=provider,
    )


def write_gear_observed_backfill_state(conn, state):
    ensure_websim_tables(conn)
    normalized = normalize_gear_observed_backfill_state(
        state,
        target_item_ids=state.get("targetItemIds") or [],
        provider=state.get("provider") or "raiderio",
    )
    if isinstance(state, dict):
        cursor = state.get("cursor") if isinstance(state.get("cursor"), dict) else {}
        if cursor.get("targetItemHash"):
            normalized["cursor"]["targetItemHash"] = cursor.get("targetItemHash")
        if cursor.get("targetItemCount") is not None:
            normalized["cursor"]["targetItemCount"] = int_or_zero(cursor.get("targetItemCount"))
        normalized["cursor"]["targetOffset"] = int_or_zero(cursor.get("targetOffset"))
        normalized["cursor"]["profileOffset"] = int_or_zero(cursor.get("profileOffset"))
        normalized["matchedTargetItemIds"] = gear_observed_backfill_target_ids(state.get("matchedTargetItemIds"))
        for key in (
            "lastRunStatus",
            "lastRunStartedAt",
            "lastRunFinishedAt",
            "processedTargetItemCount",
            "processedProfileCount",
            "simcProfileCount",
            "simcResolvedProfileCount",
            "simcResolvedSlotCount",
            "lastError",
            "wrappedAt",
        ):
            if key in state:
                normalized[key] = state[key]
    set_sync_state(conn, GEAR_OBSERVED_BACKFILL_SYNC_KEY, normalized)
    return normalized


def gear_observed_backfill_slice(values, offset, limit):
    values = list(values or [])
    if not values or limit <= 0:
        return [], 0, False
    offset = int_or_zero(offset) % len(values)
    count = min(max(0, int(limit)), len(values))
    selected = [values[(offset + index) % len(values)] for index in range(count)]
    next_offset = (offset + count) % len(values)
    wrapped = offset + count >= len(values)
    return selected, next_offset, wrapped


def build_gear_observed_backfill_window(target_item_ids, profiles, state=None, *, target_limit=80, profile_limit=40):
    target_ids = gear_observed_backfill_target_ids(target_item_ids)
    profiles = list(profiles or [])
    state = state if isinstance(state, dict) else {}
    cursor = state.get("cursor") if isinstance(state.get("cursor"), dict) else {}
    selected_targets, next_target_offset, target_wrapped = gear_observed_backfill_slice(
        target_ids,
        cursor.get("targetOffset"),
        target_limit,
    )
    selected_profiles, next_profile_offset, profile_wrapped = gear_observed_backfill_slice(
        profiles,
        cursor.get("profileOffset"),
        profile_limit,
    )
    return {
        "targetItemIds": selected_targets,
        "profiles": selected_profiles,
        "cursor": {
            "targetItemHash": gear_observed_backfill_target_hash(target_ids),
            "targetItemCount": len(target_ids),
            "targetOffset": next_target_offset,
            "profileOffset": next_profile_offset,
        },
        "wrapped": bool(target_wrapped or profile_wrapped),
    }


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
    raids=None,
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
    raid_rows = raids if isinstance(raids, list) else (
        official_current_season_raid_refs() if dungeons is None and data_status == "verified" else []
    )
    revision = season_revision_for(season_id, locale, rows) if data_status == "verified" else "blocked"
    payload = {
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
    if raid_rows:
        payload["raids"] = raid_rows
    return payload


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


COMPACT_SEASON_KEYS = {
    "id",
    "seasonId",
    "label",
    "seasonLabel",
    "revision",
    "seasonRevision",
    "verifiedAt",
    "expiresAt",
    "locale",
    "dataStatus",
    "sourceRefs",
    "errors",
    "raids",
    "itemSets",
    "journalExpansionName",
}
COMPACT_SEASON_DUNGEON_KEYS = {
    "id",
    "dungeonId",
    "instanceId",
    "name",
    "shortName",
    "timerSeconds",
    "sourceRefs",
}


def compact_season_payload(season):
    if not isinstance(season, dict):
        return season
    compact = {
        key: season.get(key)
        for key in COMPACT_SEASON_KEYS
        if season.get(key) not in (None, "", [], {})
    }
    dungeons = []
    for dungeon in season.get("dungeons") or []:
        if not isinstance(dungeon, dict):
            continue
        compact_dungeon = {
            key: dungeon.get(key)
            for key in COMPACT_SEASON_DUNGEON_KEYS
            if dungeon.get(key) not in (None, "", [], {})
        }
        if compact_dungeon:
            dungeons.append(compact_dungeon)
    if dungeons:
        compact["dungeons"] = dungeons
    return compact


def current_mythic_season_dungeon_pool_present(season):
    if not isinstance(season, dict):
        return False
    current_ids = {str(item) for item in MIDNIGHT_SEASON_ONE_DUNGEON_IDS}
    current_name_keys = {normalize_name_key(name) for name in MIDNIGHT_SEASON_ONE_DUNGEONS}
    for raw_ref in season.get("dungeons") or []:
        if not isinstance(raw_ref, dict):
            continue
        ref_ids = {
            str(raw_ref.get("instanceId") or raw_ref.get("journalInstanceId") or "").strip(),
            str(raw_ref.get("dungeonId") or raw_ref.get("id") or "").strip(),
        }
        if current_ids.intersection(ref_ids):
            return True
        name_key = normalize_name_key(raw_ref.get("name") or raw_ref.get("shortName") or "")
        if name_key in current_name_keys:
            return True
    label_key = normalize_name_key(
        f"{season.get('seasonLabel') or ''} {season.get('label') or ''} {season.get('seasonId') or season.get('id') or ''}"
    )
    return "midnight" in label_key or "至暗之夜" in str(season.get("seasonLabel") or season.get("label") or "")


def normalize_current_season_raid_pool_payload(season):
    if not isinstance(season, dict) or not current_mythic_season_dungeon_pool_present(season):
        return season
    status = current_season_raid_pool_status(season)
    refs_by_key = {
        normalize_name_key(ref.get("name") or ""): ref
        for ref in status.get("refs") or []
        if isinstance(ref, dict) and normalize_name_key(ref.get("name") or "")
    }
    fallback_refs_by_key = {
        normalize_name_key(ref.get("name") or ""): ref
        for ref in official_current_season_raid_refs()
        if isinstance(ref, dict) and normalize_name_key(ref.get("name") or "")
    }
    season["raids"] = [
        refs_by_key.get(normalize_name_key(name)) or fallback_refs_by_key[normalize_name_key(name)]
        for name in MIDNIGHT_CURRENT_SEASON_RAIDS
    ]
    season["raidPoolStatus"] = status
    return season


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
    normalize_current_season_raid_pool_payload(payload)
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


def blizzard_credentials_configured():
    return bool(
        (os.environ.get("WOW_BLIZZARD_CLIENT_ID") or os.environ.get("WOW_BNET_CLIENT_ID"))
        and (os.environ.get("WOW_BLIZZARD_CLIENT_SECRET") or os.environ.get("WOW_BNET_CLIENT_SECRET"))
    )


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


def exact_item_name_key(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def search_result_item_name(payload):
    name = payload.get("name") if isinstance(payload, dict) else ""
    if isinstance(name, dict):
        return name.get("en_US") or name.get("en_GB") or next((str(value) for value in name.values() if value), "")
    return str(name or "")


def search_blizzard_item_id_by_english_name(token, item_name, region=DEFAULT_REGION):
    target = exact_item_name_key(item_name)
    if not target:
        return ""
    page_size = int_env("WOW_WEBSIM_ITEM_SEARCH_PAGE_SIZE", 1000)
    queries = [str(item_name or "").strip()]
    quoted = f'"{queries[0]}"'
    if quoted not in queries:
        queries.append(quoted)
    for query_name in queries:
        payload = blizzard_get(
            "/data/wow/search/item",
            token,
            region,
            "en_US",
            params={
                "name.en_US": query_name,
                "_pageSize": page_size,
            },
            namespace=blizzard_namespace(region, "static"),
        )
        matches = []
        for row in payload.get("results") or []:
            data = row.get("data") if isinstance(row, dict) else {}
            if exact_item_name_key(search_result_item_name(data)) != target:
                continue
            item_id = str(data.get("id") or "").strip()
            if item_id:
                matches.append(item_id)
        if matches:
            return sorted(matches, key=lambda value: int(value) if value.isdigit() else 0, reverse=True)[0]
    return ""


def gear_slot_payload():
    return [
        {
            "key": slot,
            "slot": slot,
            "simcSlot": slot,
            "label": GEAR_SLOT_LABELS.get(slot, slot),
        }
        for slot in CANONICAL_GEAR_SLOTS
    ]


def canonical_gear_slot(value):
    slot = re.sub(r"[^a-z0-9_]+", "_", str(value or "").lower()).strip("_")
    if not slot:
        return ""
    slot = GEAR_SLOT_ALIASES.get(slot, slot)
    return slot if slot in CANONICAL_GEAR_SLOTS else ""


def item_slot_from_payload(payload):
    if not isinstance(payload, dict):
        return ""
    inventory_type = payload.get("inventory_type") or {}
    item_class = payload.get("item_class") or {}
    item_subclass = payload.get("item_subclass") or {}
    type_key = re.sub(r"[^a-z0-9_]+", "_", str(inventory_type.get("type") or "").lower()).strip("_")
    type_key = re.sub(r"^invtype_", "", type_key)
    type_mapping = {
        "head": "head",
        "neck": "neck",
        "shoulder": "shoulder",
        "body": "chest",
        "chest": "chest",
        "robe": "chest",
        "waist": "waist",
        "legs": "legs",
        "feet": "feet",
        "wrist": "wrist",
        "hand": "hands",
        "hands": "hands",
        "finger": "finger1",
        "trinket": "trinket1",
        "cloak": "back",
        "weapon": "main_hand",
        "main_hand": "main_hand",
        "off_hand": "off_hand",
        "mainhand": "main_hand",
        "offhand": "off_hand",
        "weaponmainhand": "main_hand",
        "2hweapon": "main_hand",
        "twohweapon": "main_hand",
        "ranged": "main_hand",
        "rangedright": "main_hand",
        "thrown": "main_hand",
        "weaponoffhand": "off_hand",
        "shield": "off_hand",
        "holdable": "off_hand",
    }
    if type_key in type_mapping:
        return type_mapping[type_key]

    text_values = [
        inventory_type.get("name"),
        inventory_type.get("display_string"),
        item_class.get("name"),
        item_class.get("type"),
        item_subclass.get("name"),
    ]
    name = " ".join(str(value or "").lower() for value in text_values if value)
    mapping = [
        ("off hand", "off_hand"),
        ("off-hand", "off_hand"),
        ("held", "off_hand"),
        ("shield", "off_hand"),
        ("main hand", "main_hand"),
        ("main-hand", "main_hand"),
        ("two-hand", "main_hand"),
        ("two hand", "main_hand"),
        ("one-hand", "main_hand"),
        ("one hand", "main_hand"),
        ("head", "head"),
        ("neck", "neck"),
        ("shoulder", "shoulder"),
        ("back", "back"),
        ("cloak", "back"),
        ("chest", "chest"),
        ("robe", "chest"),
        ("wrist", "wrist"),
        ("hands", "hands"),
        ("hand", "hands"),
        ("waist", "waist"),
        ("leg", "legs"),
        ("feet", "feet"),
        ("foot", "feet"),
        ("finger", "finger1"),
        ("ring", "finger1"),
        ("trinket", "trinket1"),
        ("weapon", "main_hand"),
    ]
    for needle, slot in mapping:
        if needle in name:
            return slot
    return canonical_gear_slot(payload.get("_fallback_slot") or "")


def normalized_difficulty_key(value):
    key = re.sub(r"[^a-z0-9_+-]+", "_", str(value or "").lower()).strip("_")
    key = key.replace("+", "_plus").replace("-", "_")
    return key


def difficulty_label_from_text(value):
    text = str(value or "").lower()
    checks = [
        ("heroic", "英雄"),
        ("mythic+", "大秘境"),
        ("mythic plus", "大秘境"),
        ("mythic", "史诗"),
        ("normal", "普通"),
        ("raid finder", "随机"),
        ("lfr", "随机"),
        ("英雄", "英雄"),
        ("史诗", "史诗"),
        ("神话", "史诗"),
        ("普通", "普通"),
        ("随机", "随机"),
        ("大秘境", "大秘境"),
    ]
    for needle, label in checks:
        if needle in text:
            return label
    return ""


def localized_difficulty_label(difficulty_key="", fallback_text="", source_type=""):
    key = normalized_difficulty_key(difficulty_key)
    if key in DIFFICULTY_LABELS_ZH:
        return DIFFICULTY_LABELS_ZH[key]
    label = difficulty_label_from_text(fallback_text)
    if label:
        return label
    source_key = normalized_difficulty_key(source_type)
    return DIFFICULTY_LABELS_ZH.get(source_key, "")


def payload_preview_item(payload):
    if not isinstance(payload, dict):
        return {}
    for key in ("preview_item", "previewItem", "preview"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


BUILT_IN_EMBELLISHMENT_VALUE = "built_in"
BUILT_IN_EMBELLISHMENT_LABEL = "美化"
BUILT_IN_EMBELLISHMENT_LIMIT_KEYS = {
    "limit_category",
    "limitCategory",
    "limit_categories",
    "limitCategories",
    "unique_equipped",
    "uniqueEquipped",
    "unique_equipped_category",
    "uniqueEquippedCategory",
    "equip_limit",
    "equipLimit",
}


def text_fragments_from_value(value, depth=0):
    if depth > 6 or value in (None, "", [], {}):
        return []
    if isinstance(value, (str, int, float, bool)):
        text = str(value).strip()
        return [text] if text else []
    if isinstance(value, list):
        fragments = []
        for entry in value:
            fragments.extend(text_fragments_from_value(entry, depth + 1))
        return fragments
    if isinstance(value, dict):
        fragments = []
        for key in ("name", "display_string", "displayString", "type", "label", "description", "text"):
            if key in value:
                fragments.extend(text_fragments_from_value(value.get(key), depth + 1))
        for nested in value.values():
            if isinstance(nested, (dict, list)):
                fragments.extend(text_fragments_from_value(nested, depth + 1))
        return fragments
    return []


def keyed_payload_text_fragments(value, keys, depth=0):
    if depth > 6 or not isinstance(value, dict):
        return []
    fragments = []
    for key, child in value.items():
        if key in keys:
            fragments.extend(text_fragments_from_value(child))
        if isinstance(child, dict):
            fragments.extend(keyed_payload_text_fragments(child, keys, depth + 1))
        elif isinstance(child, list):
            for entry in child:
                if isinstance(entry, dict):
                    fragments.extend(keyed_payload_text_fragments(entry, keys, depth + 1))
    return fragments


def built_in_embellishment_fields_from_payload(payload):
    if not isinstance(payload, dict):
        return {}
    fragments = []
    seen_parents = set()
    for parent in (payload_preview_item(payload), payload):
        if not isinstance(parent, dict):
            continue
        parent_id = id(parent)
        if parent_id in seen_parents:
            continue
        seen_parents.add(parent_id)
        fragments.extend(keyed_payload_text_fragments(parent, BUILT_IN_EMBELLISHMENT_LIMIT_KEYS))
    text = " ".join(fragments).strip().lower()
    if not text:
        return {}
    has_chinese_marker = "美化" in text and ("唯一" in text or "装备唯一" in text)
    has_english_marker = "embellish" in text and ("unique" in text or "equipped" in text)
    if not (has_chinese_marker or has_english_marker):
        return {}
    return {
        "hasBuiltInEmbellishment": True,
        "builtInEmbellishment": BUILT_IN_EMBELLISHMENT_VALUE,
        "builtInEmbellishmentLabel": BUILT_IN_EMBELLISHMENT_LABEL,
        "embellishmentSource": "built_in",
    }


def unique_equipped_fields_from_payload(payload):
    if not isinstance(payload, dict):
        return {}
    fragments = []
    explicit_unique = False
    seen_parents = set()
    for parent in (payload_preview_item(payload), payload):
        if not isinstance(parent, dict):
            continue
        parent_id = id(parent)
        if parent_id in seen_parents:
            continue
        seen_parents.add(parent_id)
        for key in BUILT_IN_EMBELLISHMENT_LIMIT_KEYS:
            if parent.get(key) not in (None, "", [], {}):
                if isinstance(parent.get(key), bool):
                    explicit_unique = explicit_unique or bool(parent.get(key))
                fragments.extend(text_fragments_from_value(parent.get(key)))
        for key in ("is_unique_equipped", "isUniqueEquipped", "unique", "uniqueEquipped"):
            if isinstance(parent.get(key), bool) and parent.get(key):
                explicit_unique = True
    text = " ".join(fragments).strip()
    normalized = text.lower()
    has_marker = (
        explicit_unique
        or "unique-equipped" in normalized
        or "unique equipped" in normalized
        or "unique_equipped" in normalized
        or "\u88c5\u5907\u552f\u4e00" in text
        or "\u552f\u4e00\u88c5\u5907" in text
    )
    if not has_marker:
        return {}
    limit = 0
    match = re.search(r"\((\d+)\)|\uff08(\d+)\uff09", text)
    if match:
        limit = int(match.group(1) or match.group(2) or 0)
    elif explicit_unique:
        limit = 1
    fields = {
        "uniqueEquipped": True,
        "uniqueEquippedLabel": "\u552f\u4e00",
    }
    if limit:
        fields["uniqueLimit"] = limit
    return fields


def positive_int_value(value):
    if isinstance(value, dict):
        value = first_matching_value(value, ["value", "amount", "level", "display_string"], "")
    try:
        normalized = normalize_option_value(value)
        if not normalized:
            return 0
        match = re.search(r"\d+", normalized)
        return int(match.group(0)) if match else 0
    except (TypeError, ValueError):
        return 0


def battle_net_preview_item_level(payload):
    if not isinstance(payload, dict):
        return 0
    preview = payload_preview_item(payload)
    for parent in (payload, preview):
        if not isinstance(parent, dict):
            continue
        value = first_matching_value(parent, ["level", "itemLevel", "item_level", "ilevel"], "")
        item_level = positive_int_value(value)
        if item_level > 0:
            return item_level
    return 0


def battle_net_preview_bonus_ids(payload):
    if not isinstance(payload, dict):
        return []
    preview = payload_preview_item(payload)
    values = []
    for parent in (preview, payload):
        if not isinstance(parent, dict):
            continue
        for key in ("bonus_list", "bonusList", "bonus_lists", "bonusListIDs", "bonusIds", "bonuses"):
            raw = parent.get(key)
            if isinstance(raw, list):
                values.extend(raw)
            elif raw not in (None, "", {}):
                values.append(raw)
    result = []
    seen = set()
    for value in values:
        text = normalize_option_value(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def battle_net_preview_variant_from_metadata(payload, source_type):
    payload = payload if isinstance(payload, dict) else {}
    source_type = raw_source_type(source_type)
    preview = payload_preview_item(payload)
    bonus_ids = battle_net_preview_bonus_ids(payload)
    item_level = battle_net_preview_item_level(preview)
    if item_level <= 0 and bonus_ids:
        item_level = battle_net_preview_item_level(payload)
    if item_level <= 0:
        return None
    if source_type == "dungeon" and item_level < int_env("WOW_WEBSIM_MIN_DUNGEON_PREVIEW_ILEVEL", 500):
        return None
    if source_type in {"raid", "tier_set"} and item_level < int_env("WOW_WEBSIM_MIN_OFFICIAL_PREVIEW_ILEVEL", 100):
        return None
    simc_options = {"bonus_id": "/".join(bonus_ids)} if bonus_ids else {}
    return {
        "itemLevel": item_level,
        "simcOptions": simc_options,
        "simcIlevelOnly": not bool(simc_options),
        "bonusIds": bonus_ids,
    }


def stat_label_from_payload(stat):
    if not isinstance(stat, dict):
        return ""
    type_payload = stat.get("type") if isinstance(stat.get("type"), dict) else {}
    raw_label = (
        stat.get("label")
        or stat.get("name")
        or type_payload.get("name")
        or type_payload.get("type")
        or stat.get("stat")
        or stat.get("key")
    )
    raw_key = type_payload.get("type") or stat.get("key") or stat.get("stat") or raw_label
    key = re.sub(r"[^a-z0-9_]+", "_", str(raw_key or "").lower()).strip("_")
    return ITEM_STAT_LABELS_ZH.get(key) or str(raw_label or "").strip()


def normalize_item_stat(stat):
    if isinstance(stat, str):
        text = stat.strip()
        return {"label": text, "value": "", "display": text} if text else None
    if not isinstance(stat, dict):
        return None
    label = stat_label_from_payload(stat)
    value = first_matching_value(stat, ["value", "amount", "rating", "displayValue"], "")
    display = ""
    display_payload = stat.get("display") if isinstance(stat.get("display"), dict) else {}
    display = str(display_payload.get("display_string") or stat.get("displayString") or stat.get("text") or "").strip()
    if not label and display:
        label = display
    if not label and value in ("", None):
        return None
    type_payload = stat.get("type") if isinstance(stat.get("type"), dict) else {}
    raw_key = type_payload.get("type") or stat.get("key") or stat.get("stat") or label
    return {
        "key": re.sub(r"[^a-z0-9_]+", "_", str(raw_key).lower()).strip("_"),
        "label": label,
        "value": value,
        "display": display,
    }


def normalize_item_stats(values):
    candidates = []
    if isinstance(values, list):
        candidates.extend(values)
    result = []
    seen = set()
    for stat in candidates:
        normalized = normalize_item_stat(stat)
        if not normalized:
            continue
        dedupe_key = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        result.append(normalized)
    return result


def primary_stat_keys_from_text(value):
    text = str(value or "").strip()
    if not text:
        return set()
    lower = text.lower()
    compact = re.sub(r"[\s/_\-\+\|:;\uff1a\uff1b,，/]+", "", lower)
    for pattern, keys in PRIMARY_STAT_HYBRID_PATTERNS.items():
        if pattern in compact:
            return set(keys)
    keys = set()
    if "\u4e3b\u5c5e\u6027" in text or "primary stat" in lower or "primarystat" in compact:
        keys.update(PRIMARY_STAT_KEYS)
    if "\u529b\u91cf" in text or "strength" in lower or compact == "str":
        keys.add("strength")
    if "\u654f\u6377" in text or "agility" in lower or compact == "agi":
        keys.add("agility")
    if "\u667a\u529b" in text or "intellect" in lower or "intelligence" in lower or compact == "int":
        keys.add("intellect")
    return keys


def item_stat_primary_keys(stat):
    if isinstance(stat, dict):
        fragments = [
            stat.get("key"),
            stat.get("label"),
            stat.get("name"),
            stat.get("stat"),
            stat.get("type"),
            stat.get("display"),
            stat.get("displayString"),
            stat.get("text"),
        ]
        type_payload = stat.get("type") if isinstance(stat.get("type"), dict) else {}
        fragments.extend([type_payload.get("type"), type_payload.get("name")])
    else:
        fragments = [stat]
    keys = set()
    for fragment in fragments:
        keys.update(primary_stat_keys_from_text(fragment))
    return keys


def item_stats_primary_compatible(stats, primary_key):
    primary_key = str(primary_key or "").strip()
    if primary_key not in PRIMARY_STAT_KEYS:
        return True
    primary_sets = [item_stat_primary_keys(stat) for stat in stats or []]
    primary_sets = [keys for keys in primary_sets if keys]
    if not primary_sets:
        return True
    return any(primary_key in keys for keys in primary_sets)


def item_stat_summary_primary_compatible(summary, primary_key):
    text = str(summary or "").strip()
    if not text:
        return True
    parts = re.split(r"[\uff1b;，,\n]+", text)
    return item_stats_primary_compatible(parts, primary_key)


def replace_primary_stat_text_for_spec(text, primary_key):
    label = PRIMARY_STAT_LABELS_ZH.get(primary_key)
    if not label:
        return text
    patterns = [
        r"\u529b\u91cf\s*(?:or|/|\u6216|,|\uff0c)\s*\u654f\u6377\s*(?:or|/|\u6216|,|\uff0c)\s*\u667a\u529b",
        r"\u529b\u91cf\s*(?:or|/|\u6216|,|\uff0c)\s*\u667a\u529b\s*(?:or|/|\u6216|,|\uff0c)\s*\u654f\u6377",
        r"\u654f\u6377\s*(?:or|/|\u6216|,|\uff0c)\s*\u529b\u91cf\s*(?:or|/|\u6216|,|\uff0c)\s*\u667a\u529b",
        r"\u654f\u6377\s*(?:or|/|\u6216|,|\uff0c)\s*\u667a\u529b\s*(?:or|/|\u6216|,|\uff0c)\s*\u529b\u91cf",
        r"\u667a\u529b\s*(?:or|/|\u6216|,|\uff0c)\s*\u529b\u91cf\s*(?:or|/|\u6216|,|\uff0c)\s*\u654f\u6377",
        r"\u667a\u529b\s*(?:or|/|\u6216|,|\uff0c)\s*\u654f\u6377\s*(?:or|/|\u6216|,|\uff0c)\s*\u529b\u91cf",
        r"strength\s*(?:or|/|,)\s*agility\s*(?:or|/|,)\s*intellect",
        r"strength\s*(?:or|/|,)\s*intellect\s*(?:or|/|,)\s*agility",
        r"agility\s*(?:or|/|,)\s*strength\s*(?:or|/|,)\s*intellect",
        r"agility\s*(?:or|/|,)\s*intellect\s*(?:or|/|,)\s*strength",
        r"intellect\s*(?:or|/|,)\s*strength\s*(?:or|/|,)\s*agility",
        r"intellect\s*(?:or|/|,)\s*agility\s*(?:or|/|,)\s*strength",
        r"\u529b\u91cf\s*(?:or|/|\u6216|,|\uff0c)\s*\u654f\u6377",
        r"\u654f\u6377\s*(?:or|/|\u6216|,|\uff0c)\s*\u529b\u91cf",
        r"\u529b\u91cf\s*(?:or|/|\u6216|,|\uff0c)\s*\u667a\u529b",
        r"\u667a\u529b\s*(?:or|/|\u6216|,|\uff0c)\s*\u529b\u91cf",
        r"\u654f\u6377\s*(?:or|/|\u6216|,|\uff0c)\s*\u667a\u529b",
        r"\u667a\u529b\s*(?:or|/|\u6216|,|\uff0c)\s*\u654f\u6377",
        r"strength\s*(?:or|/|,)\s*agility",
        r"agility\s*(?:or|/|,)\s*strength",
        r"strength\s*(?:or|/|,)\s*intellect",
        r"intellect\s*(?:or|/|,)\s*strength",
        r"agility\s*(?:or|/|,)\s*intellect",
        r"intellect\s*(?:or|/|,)\s*agility",
    ]
    result = str(text or "")
    for pattern in patterns:
        result = re.sub(pattern, label, result, flags=re.IGNORECASE)
    return result


def filter_item_stat_summary_for_spec(summary, primary_key):
    text = str(summary or "").strip()
    if not text or primary_key not in PRIMARY_STAT_KEYS:
        return text
    filtered = []
    for part in re.split(r"([\uff1b;\n]+)", text):
        if part in {"\uff1b", ";", "\n"}:
            continue
        fragment = part.strip()
        if not fragment:
            continue
        primary_keys = primary_stat_keys_from_text(fragment)
        if primary_keys:
            if primary_key not in primary_keys:
                continue
            fragment = replace_primary_stat_text_for_spec(fragment, primary_key)
        filtered.append(fragment)
    return "\uff1b".join(unique_text_list(filtered))


def filter_item_stats_for_spec(stats, primary_key):
    primary_key = str(primary_key or "").strip()
    normalized_stats = normalize_item_stats(stats)
    if primary_key not in PRIMARY_STAT_KEYS or not normalized_stats:
        return normalized_stats
    filtered = []
    seen = set()
    for stat in normalized_stats:
        primary_keys = item_stat_primary_keys(stat)
        next_stat = dict(stat)
        if primary_keys:
            if primary_key not in primary_keys:
                continue
            next_stat["key"] = primary_key
            next_stat["label"] = PRIMARY_STAT_LABELS_ZH[primary_key]
            display = str(next_stat.get("display") or "").strip()
            if display:
                next_stat["display"] = re.sub(
                    r"(\u529b\u91cf|Strength|\u654f\u6377|Agility|\u667a\u529b|Intellect|Intelligence)(?:\s*(?:or|/|,|\uff0c|\u6216)\s*(\u529b\u91cf|Strength|\u654f\u6377|Agility|\u667a\u529b|Intellect|Intelligence))+",
                    PRIMARY_STAT_LABELS_ZH[primary_key],
                    display,
                    flags=re.IGNORECASE,
                )
        dedupe_key = json.dumps(next_stat, ensure_ascii=False, sort_keys=True)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        filtered.append(next_stat)
    return filtered


def apply_primary_stat_filter_to_stat_payload(payload, primary_key):
    if not isinstance(payload, dict):
        return payload
    primary_key = str(primary_key or "").strip()
    if primary_key not in PRIMARY_STAT_KEYS:
        return payload
    stats = payload.get("itemStats") or payload.get("stats") or []
    if stats:
        if not item_stats_primary_compatible(stats, primary_key):
            return None
        filtered_stats = filter_item_stats_for_spec(stats, primary_key)
        if filtered_stats:
            payload = dict(payload)
            payload["itemStats"] = filtered_stats
            payload["stats"] = filtered_stats
            if payload.get("statSummary"):
                payload["statSummary"] = filter_item_stat_summary_for_spec(payload.get("statSummary"), primary_key)
            else:
                payload["statSummary"] = item_stat_summary(filtered_stats)
    elif payload.get("statSummary") and not item_stat_summary_primary_compatible(payload.get("statSummary"), primary_key):
        return None
    return payload


def direct_item_stats_from_payload(payload):
    if not isinstance(payload, dict):
        return []
    candidates = []
    for key in ("stats", "item_stats", "itemStats", "attributes"):
        values = payload.get(key)
        if isinstance(values, list):
            candidates.extend(values)
    return normalize_item_stats(candidates)


def item_stat_comparison_key(stats):
    normalized = []
    for stat in normalize_item_stats(stats):
        normalized.append(
            {
                "key": str(stat.get("key") or "").strip().lower(),
                "label": str(stat.get("label") or "").strip(),
                "value": str(stat.get("value") or "").strip(),
                "display": str(stat.get("display") or "").strip(),
            }
        )
    return sorted(normalized, key=lambda stat: (stat["key"], stat["label"], stat["value"], stat["display"]))


def extract_item_stats_from_payload(payload):
    if not isinstance(payload, dict):
        return []
    preview_stats = direct_item_stats_from_payload(payload_preview_item(payload))
    if preview_stats:
        return preview_stats
    return direct_item_stats_from_payload(payload)


def item_payload_has_stat_mismatch(payload):
    if not isinstance(payload, dict):
        return False
    official_stats = direct_item_stats_from_payload(payload_preview_item(payload))
    conflicting_stats = direct_item_stats_from_payload(payload)
    return bool(
        official_stats
        and conflicting_stats
        and item_stat_comparison_key(conflicting_stats) != item_stat_comparison_key(official_stats)
    )


def item_payload_has_effect_evidence(payload):
    if not isinstance(payload, dict):
        return False
    for parent in (payload_preview_item(payload), payload):
        if not isinstance(parent, dict):
            continue
        for key in ("spells", "effects", "use_effects", "equip_effects", "item_effects"):
            values = parent.get(key)
            if isinstance(values, list) and values:
                return True
    return False


def item_payload_is_cosmetic_statless(payload):
    if not isinstance(payload, dict):
        return False
    item_class = payload.get("item_class") if isinstance(payload.get("item_class"), dict) else {}
    item_subclass = payload.get("item_subclass") if isinstance(payload.get("item_subclass"), dict) else {}
    if payload_item_class_is_armor(item_class) and normalized_armor_subclass(item_subclass) == "Cosmetic":
        return True
    preview = payload_preview_item(payload)
    if preview and preview is not payload:
        return item_payload_is_cosmetic_statless(preview)
    return False


def item_payload_has_stat_evidence(payload):
    return bool(
        extract_item_stats_from_payload(payload)
        or item_payload_has_effect_evidence(payload)
        or item_payload_is_cosmetic_statless(payload)
    )


def item_stat_summary(stats):
    parts = []
    for stat in stats or []:
        if not isinstance(stat, dict):
            continue
        label = str(stat.get("label") or "").strip()
        value = stat.get("value")
        if label and value not in ("", None):
            parts.append(f"{label} {value}")
        elif label:
            parts.append(label)
        elif stat.get("display"):
            parts.append(str(stat.get("display")))
    return "；".join(unique_text_list(parts))


def normalize_gem_stat_label(label):
    text = str(label or "").strip()
    return text.replace("爆击", "暴击")


def compact_gem_item_stat_summary(stats):
    parts = []
    for stat in normalize_item_stats(stats):
        label = normalize_gem_stat_label(stat.get("label") or stat.get("display") or "")
        value = stat.get("value")
        if not label or value in ("", None):
            continue
        value_text = str(value).strip()
        if re.fullmatch(r"\d+(?:\.\d+)?", value_text):
            value_text = f"+{value_text}"
        parts.append(f"{value_text}{label}")
    return " ".join(unique_text_list(parts))


def normalize_gem_effect_summary(value):
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("爆击", "暴击")
    text = re.sub(r"\s*(?:和|,|，|;|；)\s*", " ", text)
    text = re.sub(r"([+-]?\d+(?:\.\d+)?)\s*([^+\-\d\s][^+\-]*?)(?=\s+[+-]?\d|$)", lambda match: f"{match.group(1)}{match.group(2).strip()}", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if re.search(r"[+-]?\d", text) else ""


def gem_effect_summary_from_payload(payload):
    if not isinstance(payload, dict):
        return ""
    for parent in (payload_preview_item(payload), payload):
        if not isinstance(parent, dict):
            continue
        gem_properties = parent.get("gem_properties") if isinstance(parent.get("gem_properties"), dict) else {}
        effect = gem_properties.get("effect") or gem_properties.get("display_string") or gem_properties.get("displayString")
        summary = normalize_gem_effect_summary(effect)
        if summary:
            return summary
    return ""


def item_stat_summary_for_metadata(payload, item_stats):
    return gem_effect_summary_from_payload(payload) or item_stat_summary(item_stats)


def gem_metadata_stat_summary(metadata):
    if not isinstance(metadata, dict):
        return ""
    payload = metadata.get("payload") if isinstance(metadata.get("payload"), dict) else {}
    return (
        gem_effect_summary_from_payload(payload)
        or compact_gem_item_stat_summary(metadata.get("itemStats") or [])
        or str(metadata.get("statSummary") or "").strip()
    )


def verified_socket_option_payload_stat_summary(payload, gem_item_count):
    if not isinstance(payload, dict) or int(gem_item_count or 0) != 1:
        return ""
    stat_summary = normalize_gem_effect_summary(payload.get("statSummary") or payload.get("displayLabel"))
    if not stat_summary:
        return ""
    display_status = str(payload.get("displayStatus") or "").strip().lower()
    stat_status = str(payload.get("statDisplayStatus") or "").strip().lower()
    evidence_source = str(payload.get("evidenceSource") or "").strip()
    if (
        display_status == "verified"
        or stat_status in {"verified", "verified_tooltip_override"}
        or evidence_source == "wowhead_live_tooltip"
    ):
        return stat_summary
    return ""


def simc_encoded_item_options(value):
    text = str(value or "").strip()
    if not text:
        return {}
    options = {}
    for part in text.split(","):
        if "=" not in part:
            continue
        raw_key, raw_value = part.split("=", 1)
        key = re.sub(r"[^A-Za-z0-9_]+", "", raw_key.strip())
        normalized_value = normalize_option_value(raw_value)
        if not key or not normalized_value:
            continue
        if key in {"id", "item_id", "itemId"}:
            options["id"] = normalized_value
        elif key in SIMC_GEAR_OPTION_KEYS:
            options[key] = normalized_value
    return options


def simc_numeric_stat_value(value):
    if value in ("", None):
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    if number.is_integer():
        return int(number)
    return round(number, 2)


def simc_item_stats_from_gear_entry(entry):
    if not isinstance(entry, dict):
        return []
    stat_sources = [entry]
    nested_stats = entry.get("stats")
    if isinstance(nested_stats, dict):
        stat_sources.insert(0, nested_stats)
    elif isinstance(nested_stats, list):
        normalized = normalize_item_stats(nested_stats)
        if normalized:
            return normalized
    stats = []
    seen = set()
    for stat_source in stat_sources:
        if not isinstance(stat_source, dict):
            continue
        for key in SIMC_GEAR_STAT_KEYS:
            if key in seen or key not in stat_source:
                continue
            value = simc_numeric_stat_value(stat_source.get(key))
            if value is None:
                continue
            label = ITEM_STAT_LABELS_ZH.get(key) or key
            stats.append({"key": key, "label": label, "value": value})
            seen.add(key)
    return stats


def simc_gear_payload_candidates(value, depth=0):
    if depth > 6:
        return []
    candidates = []
    if isinstance(value, dict):
        if isinstance(value.get("gear"), (dict, list)):
            candidates.append(value.get("gear"))
        for key in ("simcJson", "simcGearJson", "simulationcraftJson", "simcOutput", "simcGear"):
            nested = value.get(key)
            if isinstance(nested, (dict, list)) and nested is not value:
                candidates.extend(simc_gear_payload_candidates(nested, depth + 1))
        for key in ("sim", "simulation", "report", "result", "profile"):
            nested = value.get(key)
            if isinstance(nested, (dict, list)) and nested is not value:
                candidates.extend(simc_gear_payload_candidates(nested, depth + 1))
        for key in ("players", "profiles"):
            nested = value.get(key)
            if isinstance(nested, list):
                for item in nested:
                    candidates.extend(simc_gear_payload_candidates(item, depth + 1))
        if any(canonical_gear_slot(key) and isinstance(item, dict) for key, item in value.items()):
            candidates.append(value)
    elif isinstance(value, list):
        if any(isinstance(item, dict) and normalize_slot(first_matching_value(item, ["slot", "simcSlot", "slotKey", "equipmentSlot"])) for item in value):
            candidates.append(value)
        else:
            for item in value:
                candidates.extend(simc_gear_payload_candidates(item, depth + 1))
    return candidates


def simc_gear_entry_identity(raw_slot, entry):
    if not isinstance(entry, dict):
        return None
    slot = normalize_slot(first_matching_value(entry, ["slot", "simcSlot", "slotKey", "equipmentSlot"], raw_slot))
    if not slot:
        return None
    encoded_item = first_matching_value(entry, ["encoded_item", "encodedItem", "simcLine", "simc"], "")
    encoded_options = simc_encoded_item_options(encoded_item)
    item_id = normalize_option_value(
        first_matching_value(entry, ["itemId", "item_id", "id"], encoded_options.get("id") or "")
    )
    item_level = 0
    raw_item_level = first_matching_value(entry, ["itemLevel", "ilevel", "item_level"], encoded_options.get("ilevel") or 0)
    try:
        item_level = int(float(str(raw_item_level).strip()))
    except (TypeError, ValueError):
        item_level = 0
    simc_options = {
        key: value
        for key, value in encoded_options.items()
        if key in SIMC_GEAR_OPTION_KEYS and normalize_option_value(value)
    }
    for key, aliases in SIMC_GEAR_OPTION_ALIASES:
        value = simc_option_value(entry, aliases)
        if value:
            simc_options[key] = value
    stats = simc_item_stats_from_gear_entry(entry)
    result = {
        "slot": slot,
        "itemId": item_id,
        "itemLevel": item_level,
        "simcOptions": simc_options,
        "itemStats": stats,
        "statSummary": item_stat_summary(stats),
    }
    if encoded_item:
        result["simcEncodedItem"] = str(encoded_item).strip()
    return result


def simc_json_gear_stats_by_slot(payload):
    by_slot = {}
    for gear_payload in simc_gear_payload_candidates(payload):
        if isinstance(gear_payload, dict):
            iterable = gear_payload.items()
        elif isinstance(gear_payload, list):
            iterable = ((first_matching_value(item, ["slot", "simcSlot", "slotKey", "equipmentSlot"], ""), item) for item in gear_payload)
        else:
            continue
        for raw_slot, entry in iterable:
            normalized = simc_gear_entry_identity(raw_slot, entry)
            if not normalized or not normalized.get("itemStats"):
                continue
            slot = normalized.get("slot")
            if slot and slot not in by_slot:
                by_slot[slot] = normalized
    return by_slot


def simc_option_segments(value):
    text = normalize_option_value(value)
    if not text:
        return set()
    return {segment for segment in text.split("/") if segment}


def simc_gear_entry_matches_observed_item(item, gear_entry):
    if not isinstance(item, dict) or not isinstance(gear_entry, dict):
        return False
    observed_item_id = normalize_option_value(first_matching_value(item, ["itemId", "item_id", "id"]))
    if observed_item_id and gear_entry.get("itemId") and observed_item_id != str(gear_entry.get("itemId")):
        return False
    observed_level = observed_item_level(item)
    gear_level = int(gear_entry.get("itemLevel") or 0)
    if observed_level and gear_level and observed_level != gear_level:
        return False
    observed_options = observed_gear_simc_options(item)
    gear_options = gear_entry.get("simcOptions") if isinstance(gear_entry.get("simcOptions"), dict) else {}
    for key in ("bonus_id", "gem_id", "gem_bonus_id", "gem_ilevel", "enchant_id", "crafted_stats", "embellishment"):
        observed_value = observed_options.get(key)
        gear_value = gear_options.get(key)
        if observed_value and gear_value and simc_option_segments(observed_value) != simc_option_segments(gear_value):
            return False
    return True


def simc_gear_stats_for_observed_item(item, simc_gear_by_slot):
    if not isinstance(simc_gear_by_slot, dict):
        return None
    slot = normalize_slot(first_matching_value(item, ["simcSlot", "slot", "slotKey", "equipmentSlot"]))
    if not slot:
        return None
    gear_entry = simc_gear_by_slot.get(slot)
    if not gear_entry or not simc_gear_entry_matches_observed_item(item, gear_entry):
        return None
    return gear_entry


def simc_observed_variant_stat_payload(item, simc_gear_by_slot):
    gear_entry = simc_gear_stats_for_observed_item(item, simc_gear_by_slot)
    if not isinstance(gear_entry, dict):
        return {}
    stats = normalize_item_stats(gear_entry.get("itemStats") or [])
    if not stats:
        return {}
    payload = {
        "statSource": "simulationcraft",
        "statSourceDetail": "SimulationCraft JSON gear output",
        "statDisplayStatus": "verified_variant",
        "itemStats": stats,
        "statSummary": gear_entry.get("statSummary") or item_stat_summary(stats),
        "simcItemId": gear_entry.get("itemId") or "",
        "simcItemLevel": gear_entry.get("itemLevel") or 0,
    }
    if gear_entry.get("simcEncodedItem"):
        payload["simcEncodedItem"] = gear_entry.get("simcEncodedItem")
    return payload


def item_payload_has_socket(payload):
    if not isinstance(payload, dict):
        return False
    parents = [payload, payload_preview_item(payload)]
    for parent in parents:
        if not isinstance(parent, dict):
            continue
        for key in ("sockets", "socket", "gem_sockets", "gemSockets"):
            value = parent.get(key)
            if isinstance(value, list) and len(value) > 0:
                return True
            if isinstance(value, dict) and value:
                return True
    return False


def item_socket_capacity(payload=None, slot=""):
    slot = normalize_slot(slot)
    if slot in SOCKET_OPTION_GEAR_SLOT_CAPACITY:
        return SOCKET_OPTION_GEAR_SLOT_CAPACITY[slot]
    return 1 if item_payload_has_socket(payload) else 0


def item_can_enchant_slot(payload=None, slot="", item=None):
    slot = normalize_slot(slot or (item or {}).get("slot") or "")
    if slot not in ENCHANTABLE_GEAR_SLOTS:
        return False
    if slot != "off_hand":
        return True
    context = dict(item) if isinstance(item, dict) else {"slot": slot}
    if isinstance(payload, dict) and payload:
        context.setdefault("payload", payload)
    _slot, armor_type, weapon_type = gear_item_type_context(context)
    if weapon_type in {"held in off-hand", "shield"} or armor_type == "shield":
        return False
    return True


def item_mod_capabilities(payload=None, slot="", variants=None, item=None):
    slot = normalize_slot(slot or (item or {}).get("slot") or "")
    payload = payload if isinstance(payload, dict) else {}
    item = item if isinstance(item, dict) else {}
    variants = [variant for variant in variants or [] if isinstance(variant, dict)]
    socket_count = item_socket_capacity(payload, slot)
    can_enchant = item_can_enchant_slot(payload, slot, item)
    can_embellish = bool(
        item.get("embellishment")
        or item.get("crafted_stats")
        or raw_source_type(item.get("sourceType")).lower() == "crafted"
        or any(
            raw_source_type(variant.get("sourceType")).lower() == "crafted"
            or (variant.get("simcOptions") or {}).get("crafted_stats")
            or (variant.get("simcOptions") or {}).get("embellishment")
            for variant in variants
        )
    )
    capabilities = {
        "hasSocket": bool(socket_count),
        "canEnchant": bool(can_enchant),
        "canEmbellish": bool(can_embellish),
    }
    if socket_count:
        capabilities["socketCount"] = socket_count
    return capabilities


def item_set_name_from_payload(payload):
    if not isinstance(payload, dict):
        return ""
    for key in ("item_set", "itemSet", "set", "set_bonus", "setBonus"):
        value = payload.get(key)
        if isinstance(value, dict):
            name = str(value.get("name") or value.get("display_string") or value.get("slug") or "").strip()
            if name:
                return name
        elif isinstance(value, str) and value.strip():
            return value.strip()
    preview = payload_preview_item(payload)
    if preview and preview is not payload:
        return item_set_name_from_payload(preview)
    return ""


def item_set_ref_from_payload(payload):
    if not isinstance(payload, dict):
        return {}
    for key in ("item_set", "itemSet", "set", "set_bonus", "setBonus"):
        value = payload.get(key)
        if isinstance(value, dict):
            if key not in ("item_set", "itemSet") and any(
                isinstance(value.get(nested_key), dict) for nested_key in ("item_set", "itemSet")
            ):
                nested_ref = item_set_ref_from_payload(value)
                if nested_ref.get("id") or nested_ref.get("name"):
                    return nested_ref
            set_id = str(value.get("id") or extract_id_from_ref(value) or "").strip()
            name = str(value.get("name") or value.get("display_string") or value.get("slug") or "").strip()
            if set_id or name:
                return {"id": set_id, "name": name}
        elif isinstance(value, str) and value.strip():
            return {"id": "", "name": value.strip()}
    preview = payload_preview_item(payload)
    if preview and preview is not payload:
        return item_set_ref_from_payload(preview)
    return {}


def item_set_item_refs_from_payload(payload):
    if not isinstance(payload, dict):
        return []
    refs = []
    for raw_ref in list_keyed_values(payload, "items", "set_items", "setItems", "pieces"):
        if not isinstance(raw_ref, dict):
            raw_ref = {"item": raw_ref}
        item_ref = raw_ref.get("item") if isinstance(raw_ref.get("item"), dict) else raw_ref
        item_id = extract_id_from_ref(item_ref)
        if not item_id:
            continue
        name = ""
        if isinstance(item_ref, dict):
            name = str(item_ref.get("name") or item_ref.get("display_string") or "").strip()
        refs.append(
            {
                "itemId": item_id,
                "name": name or f"Item {item_id}",
                "slot": item_slot_from_payload(raw_ref) or item_slot_from_payload(item_ref),
                "payload": raw_ref,
            }
        )
    return refs


def season_item_set_refs(season):
    refs = {}
    if not isinstance(season, dict):
        return refs
    for raw_ref in season.get("itemSets") or season.get("item_sets") or season.get("tierSets") or season.get("tier_sets") or []:
        if isinstance(raw_ref, dict):
            set_id = str(raw_ref.get("id") or raw_ref.get("setId") or raw_ref.get("itemSetId") or extract_id_from_ref(raw_ref) or "").strip()
            name = str(raw_ref.get("name") or raw_ref.get("setName") or raw_ref.get("itemSetName") or "").strip()
        else:
            set_id = str(raw_ref or "").strip()
            name = ""
        if not (set_id or name):
            continue
        refs[set_id or name] = {"id": set_id, "name": name}
    return refs


def icon_url_from_media(media_payload):
    for asset in media_payload.get("assets", []) if isinstance(media_payload, dict) else []:
        value = asset.get("value")
        if value:
            return value
    return ""


def split_item_name_parts(value):
    text = str(value or "").strip()
    if not text:
        return []
    parts = [part.strip() for part in re.split(r"\s*(?:/|;|\bor\b)\s*", text) if part.strip()]
    return parts if len(parts) > 1 else [text]


def item_alias_candidates(*values):
    aliases = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        variants = [
            text,
            text.replace("_", " "),
            text.replace("'", ""),
            slugify(text, ""),
        ]
        variants.extend(split_item_name_parts(text))
        variants.extend(part.strip() for part in re.split(r"\s*,\s*", text) if part.strip())
        for variant in variants:
            alias_key = normalized_item_alias(variant)
            if not alias_key or alias_key in seen:
                continue
            seen.add(alias_key)
            aliases.append(variant)
    return aliases


def save_item_aliases(
    conn,
    item_id,
    aliases,
    display_name,
    icon_url="",
    source_locale="en_US",
    target_locale=DEFAULT_LOCALE,
    source=ITEM_METADATA_SOURCE,
    now=None,
):
    now = now or utc_now()
    alias_values = list(aliases or [])
    alias_values.append(display_name)
    for alias in item_alias_candidates(*alias_values):
        alias_key = normalized_item_alias(alias)
        if not alias_key:
            continue
        alias_id = f"{target_locale}:{alias_key}"
        conn.execute(
            """
            INSERT INTO websim_item_aliases (
                id, alias_key, alias_text, item_id, display_name, icon_url,
                source_locale, target_locale, source, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                item_id=excluded.item_id,
                display_name=excluded.display_name,
                icon_url=excluded.icon_url,
                source_locale=excluded.source_locale,
                target_locale=excluded.target_locale,
                source=excluded.source,
                updated_at=excluded.updated_at
            """,
            (
                alias_id,
                alias_key,
                str(alias)[:220],
                str(item_id),
                str(display_name or f"Item {item_id}")[:220],
                str(icon_url or "")[:260],
                str(source_locale or "en_US")[:20],
                str(target_locale or DEFAULT_LOCALE)[:20],
                str(source or ITEM_METADATA_SOURCE)[:120],
                now,
            ),
        )
        translation_id = f"item:{target_locale}:{alias_key}"
        conn.execute(
            """
            INSERT INTO websim_translations (
                id, source_locale, target_locale, source_text, translated_text, source, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                translated_text=excluded.translated_text,
                source=excluded.source,
                updated_at=excluded.updated_at
            """,
            (
                translation_id,
                str(source_locale or "en_US")[:20],
                str(target_locale or DEFAULT_LOCALE)[:20],
                str(alias)[:220],
                str(display_name or f"Item {item_id}")[:220],
                str(source or ITEM_METADATA_SOURCE)[:120],
                now,
            ),
        )


def save_websim_item_metadata(
    conn,
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
    now = utc_now()
    item_id = str(item_id or extract_id_from_ref(item_payload) or "").strip()
    if not item_id:
        return None
    item_payload = item_payload if isinstance(item_payload, dict) else {}
    english_payload = english_payload if isinstance(english_payload, dict) else {}
    media_payload = media_payload if isinstance(media_payload, dict) else {}
    display_name = item_payload.get("name") or fallback_name or english_payload.get("name") or f"Item {item_id}"
    english_name = english_payload.get("name") or fallback_name or display_name
    slot = (
        item_slot_from_payload(item_payload)
        or item_slot_from_payload(english_payload)
        or canonical_gear_slot(fallback_slot)
        or ""
    )
    quality = (item_payload.get("quality") or {}).get("name") or ""
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
    metadata_payload["_metadata"] = {
        "source": source,
        "itemId": item_id,
        "locale": locale,
        "englishName": english_name,
        "fallbackName": fallback_name,
        "iconUrl": icon_url,
        "gameAsset": game_asset,
    }
    item_stats = extract_item_stats_from_payload(metadata_payload)
    stat_summary = item_stat_summary_for_metadata(metadata_payload, item_stats)
    mod_capabilities = item_mod_capabilities(metadata_payload, slot)
    type_metadata = item_type_metadata_from_payload(metadata_payload)
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
        (
            item_id,
            str(display_name)[:220],
            slot,
            str(quality)[:80],
            str(icon_url)[:260],
            json.dumps(metadata_payload, ensure_ascii=False),
            now,
        ),
    )
    save_item_aliases(
        conn,
        item_id,
        item_alias_candidates(fallback_name, english_name, display_name),
        display_name,
        icon_url,
        source_locale="en_US",
        target_locale=locale,
        source=source,
        now=now,
    )
    upsert_websim_asset(conn, game_asset)
    return {
        "itemId": item_id,
        "displayName": display_name,
        "englishName": english_name,
        "slot": slot,
        "quality": quality,
        "iconUrl": icon_url,
        "gameAsset": game_asset,
        "itemStats": item_stats,
        "statSummary": stat_summary,
        "modCapabilities": mod_capabilities,
        **type_metadata,
        "metadataStatus": "verified",
        "metadataSource": source,
        "metadataLocale": locale,
    }


def repair_websim_item_slots_from_payload(conn):
    rows = conn.execute("SELECT id, slot, payload_json FROM websim_items").fetchall()
    repaired = 0
    now = utc_now()
    for item_id, raw_slot, payload_json in rows:
        payload = safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        payload_slot = item_slot_from_payload(payload)
        if not payload_slot:
            continue
        if payload_slot == normalize_slot(raw_slot):
            continue
        conn.execute(
            "UPDATE websim_items SET slot = ?, updated_at = ? WHERE id = ?",
            (payload_slot, now, str(item_id)),
        )
        repaired += 1
    return repaired


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


def fetch_blizzard_item_metadata(token, item_id, region=DEFAULT_REGION, locale=DEFAULT_LOCALE, fallback_name="", fallback_slot=""):
    item_path = f"/data/wow/item/{item_id}"
    item_payload, item_locale = blizzard_get_localized(
        item_path,
        token,
        region,
        locale,
        namespace=blizzard_namespace(region, "static"),
    )
    try:
        english_payload, _ = blizzard_get_localized(
            item_path,
            token,
            region,
            "en_US",
            namespace=blizzard_namespace(region, "static"),
        )
    except Exception:
        english_payload = {}
    try:
        media_payload, _ = blizzard_get_localized(
            f"/data/wow/media/item/{item_id}",
            token,
            region,
            item_locale or locale,
            namespace=blizzard_namespace(region, "static"),
        )
    except Exception:
        media_payload = {}
    if fallback_slot and not item_slot_from_payload(item_payload):
        item_payload = dict(item_payload)
        item_payload["_fallback_slot"] = fallback_slot
    return {
        "itemId": str(item_id),
        "payload": item_payload,
        "media": media_payload,
        "englishPayload": english_payload,
        "locale": item_locale or locale,
        "fallbackName": fallback_name,
        "fallbackSlot": fallback_slot,
    }


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


def normalize_localized_name_key(value):
    return re.sub(r"[\W_]+", "", str(value or "").casefold(), flags=re.UNICODE)


def normalized_season_ref(value, default_category=""):
    ref = normalize_journal_instance_ref(value)
    if not ref:
        return {}
    if default_category and not ref.get("category"):
        ref["category"] = default_category
    return {
        **ref,
        "instanceId": str(ref.get("instanceId") or ref.get("id") or "").strip(),
        "name": str(ref.get("name") or "").strip(),
        "category": str(ref.get("category") or default_category or "").strip(),
    }


def official_current_season_raid_refs():
    return [
        {
            "id": "",
            "raidId": "",
            "instanceId": "",
            "name": name,
            "category": "Raid",
        }
        for name in MIDNIGHT_CURRENT_SEASON_RAIDS
    ]


def current_season_raid_name_keys(name):
    aliases = [name, *(MIDNIGHT_CURRENT_SEASON_RAID_ALIASES.get(name) or [])]
    return {normalize_localized_name_key(alias) for alias in aliases if normalize_localized_name_key(alias)}


def canonical_current_season_raid_name(value):
    key = normalize_localized_name_key(value)
    if not key:
        return ""
    for name in MIDNIGHT_CURRENT_SEASON_RAIDS:
        if key in current_season_raid_name_keys(name):
            return name
    return ""


def canonical_current_season_raid_ref(ref):
    if not isinstance(ref, dict):
        return ref
    canonical_name = canonical_current_season_raid_name(ref.get("name") or "")
    if not canonical_name:
        return ref
    current_name = str(ref.get("name") or "")
    normalized = {**ref, "name": canonical_name}
    if current_name and current_name != canonical_name:
        normalized["localizedName"] = current_name
    return normalized


def official_current_season_raid_name_keys():
    return {
        key
        for name in MIDNIGHT_CURRENT_SEASON_RAIDS
        for key in current_season_raid_name_keys(name)
    }


def current_season_raid_pool_status(season):
    raw_raids = []
    if isinstance(season, dict):
        raw_raids = [normalized_season_ref(raw_ref, "Raid") for raw_ref in season.get("raids") or []]
        raw_raids = [ref for ref in raw_raids if ref]
    expected_names = list(MIDNIGHT_CURRENT_SEASON_RAIDS)
    explicit_ids = {
        item.strip()
        for item in os.environ.get("WOW_WEBSIM_CURRENT_SEASON_RAID_INSTANCE_IDS", "").split(",")
        if item.strip()
    }
    if explicit_ids:
        refs = [
            canonical_current_season_raid_ref(ref)
            for ref in raw_raids
            if str(ref.get("instanceId") or ref.get("id") or "").strip() in explicit_ids
        ]
        missing_names = [] if len(refs) == len(explicit_ids) else expected_names
        stale_refs = [
            ref for ref in raw_raids
            if str(ref.get("instanceId") or ref.get("id") or "").strip() not in explicit_ids
        ]
    else:
        refs_by_name = {}
        stale_refs = []
        for ref in raw_raids:
            name_key = normalize_localized_name_key(ref.get("name") or "")
            canonical_name = canonical_current_season_raid_name(ref.get("name") or "")
            if canonical_name:
                refs_by_name.setdefault(canonical_name, canonical_current_season_raid_ref(ref))
            elif name_key:
                stale_refs.append(ref)
        refs = [
            refs_by_name[name]
            for name in expected_names
            if name in refs_by_name
        ]
        missing_names = [
            name
            for name in expected_names
            if name not in refs_by_name
        ]
    unverified_ref_names = [
        ref.get("name") or ref.get("id") or "unknown raid"
        for ref in refs
        if not str(ref.get("instanceId") or ref.get("id") or "").strip()
    ]
    blockers = []
    if missing_names or unverified_ref_names:
        blockers.append(CURRENT_SEASON_RAID_POOL_MISSING_BLOCKER)
    if stale_refs and (missing_names or unverified_ref_names):
        blockers.append(CURRENT_SEASON_RAID_POOL_STALE_BLOCKER)
    return {
        "refs": refs,
        "expectedNames": expected_names,
        "missingNames": unique_text_list([*missing_names, *unverified_ref_names]),
        "staleRefs": [
            {
                "id": str(ref.get("id") or ""),
                "instanceId": str(ref.get("instanceId") or ""),
                "name": str(ref.get("name") or ""),
                "category": str(ref.get("category") or "Raid"),
            }
            for ref in stale_refs
        ],
        "blockers": blockers,
    }


def current_season_raid_refs(season):
    return current_season_raid_pool_status(season).get("refs") or []


def active_season_dungeon_refs(season):
    if not isinstance(season, dict):
        return []
    refs = []
    for raw_ref in season.get("dungeons") or []:
        if not isinstance(raw_ref, dict):
            continue
        instance_id = str(raw_ref.get("instanceId") or raw_ref.get("instance_id") or "").strip()
        dungeon_id = str(raw_ref.get("dungeonId") or raw_ref.get("id") or "").strip()
        name = str(raw_ref.get("name") or raw_ref.get("shortName") or dungeon_id or instance_id or "").strip()
        if not (instance_id or dungeon_id or name):
            continue
        refs.append(
            {
                **raw_ref,
                "instanceId": instance_id,
                "dungeonId": dungeon_id,
                "name": name,
                "category": "Dungeon",
            }
        )
    return refs


def source_matches_season_refs(source, refs):
    if not refs:
        return True
    source = source if isinstance(source, dict) else {}
    source_instance_id = str(source.get("instanceId") or source.get("instance_id") or "").strip()
    source_label_key = normalize_name_key(
        source.get("sourceLabel")
        or source.get("label")
        or source.get("source")
        or source.get("instanceName")
        or ""
    )
    for ref in refs:
        ref_instance_id = str(ref.get("instanceId") or ref.get("instance_id") or ref.get("id") or "").strip()
        if source_instance_id and ref_instance_id and source_instance_id == ref_instance_id:
            return True
        ref_name_key = normalize_name_key(ref.get("name") or ref.get("shortName") or "")
        if ref_name_key and source_label_key and ref_name_key in source_label_key:
            return True
    return False


def normalized_source_validation_status(source):
    source = source if isinstance(source, dict) else {}
    payload = source.get("payload") if isinstance(source.get("payload"), dict) else {}
    candidates = []
    for record in (source, payload):
        for key in (
            "validationStatus",
            "acceptedStatus",
            "candidateStatus",
            "currentSeasonStatus",
            "sourceStatus",
            "metadataStatus",
        ):
            value = str((record or {}).get(key) or "").strip().lower()
            if value:
                candidates.append(value)
    known_statuses = SOURCE_VALIDATION_ACCEPTED_STATUSES | SOURCE_VALIDATION_INACTIVE_STATUSES
    for status in candidates:
        if status in known_statuses:
            return status
    return ""


def source_validation_allows_current_acceptance(source):
    return normalized_source_validation_status(source) not in SOURCE_VALIDATION_INACTIVE_STATUSES


def reused_legacy_dungeon_source_validation_status(instance_id, item_id):
    instance_id = str(instance_id or "").strip()
    item_id = str(item_id or "").strip()
    if item_id in REUSED_LEGACY_DUNGEON_SOURCE_REFERENCE_ITEM_IDS.get(instance_id, set()):
        if item_id in REUSED_LEGACY_DUNGEON_SOURCE_DISCREPANCY_ITEM_IDS.get(instance_id, set()):
            return "source_discrepancy"
        return "source_reference"
    if instance_id == "278":
        return "excluded_legacy_bucket" if item_id.startswith("133") else "journal_candidate"
    if instance_id == "945":
        return "journal_candidate"
    if instance_id == "476":
        return "journal_candidate" if item_id.startswith(("252", "258")) else "excluded_legacy_bucket"
    return ""


def current_season_loot_source_payload(source_type, instance_id, item_id, source_category):
    status = ""
    if raw_source_type(source_type).lower() in {"dungeon", "mythic_plus", "mythicplus"}:
        status = reused_legacy_dungeon_source_validation_status(instance_id, item_id)
    if not status:
        status = "source_reference"
    return {
        "authority": ITEM_METADATA_SOURCE,
        "sourceCategory": source_category,
        "validationStatus": status,
        "candidateStatus": status,
    }


def gear_source_active_for_replacement(source, season):
    source = source if isinstance(source, dict) else {}
    source_type = raw_source_type(source.get("sourceType") or source.get("type")).lower()
    if source_type in {"dungeon", "mythic_plus", "mythicplus", "raid", "tier_set", "verifiedloot", "verified_loot", "loot"}:
        if not source_validation_allows_current_acceptance(source):
            return False
    if source_type in {"dungeon", "mythic_plus", "mythicplus"}:
        return source_matches_season_refs(source, active_season_dungeon_refs(season))
    if source_type == "raid":
        if not (isinstance(season, dict) and season.get("raids")):
            return True
        refs = current_season_raid_refs(season)
        return bool(refs) and source_matches_season_refs(source, refs)
    if source_type in {"verifiedloot", "verified_loot", "loot"} and (
        source.get("instanceId")
        or source.get("instance_id")
        or source.get("instanceName")
        or source.get("source")
    ):
        refs = [*active_season_dungeon_refs(season), *current_season_raid_refs(season)]
        return source_matches_season_refs(source, refs)
    return True


def normalize_item_set_name_key(value):
    text = str(value or "").strip().lower()
    text = re.sub(r"[（(]\s*\d+\s*/\s*\d+\s*[）)]\s*$", "", text).strip()
    return re.sub(r"\s+", "", text)


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


def cached_verified_spell_detail_ids(conn, spell_ids):
    ids = [int(spell_id) for spell_id in spell_ids if int(spell_id or 0) > 0]
    if not ids:
        return set()
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"""
        SELECT spell_id
        FROM websim_spell_details
        WHERE spell_id IN ({placeholders})
          AND name != ''
          AND description != ''
          AND icon_url != ''
          AND payload_json NOT LIKE '%simulationcraft%'
        """,
        ids,
    ).fetchall()
    return {int(row[0]) for row in rows}


def sync_blizzard_spell_details(conn, token, region=DEFAULT_REGION, locale=DEFAULT_LOCALE):
    limit = int_env("WOW_WEBSIM_SYNC_SPELL_LIMIT", 400)
    spell_ids = selected_spell_ids_for_sync(conn, limit)
    cached_spell_ids = cached_verified_spell_detail_ids(conn, spell_ids)
    now = utc_now()
    counts = {"spells": 0, "media": 0, "skipped": 0}
    for spell_id in spell_ids:
        if int(spell_id) in cached_spell_ids:
            counts["skipped"] += 1
            continue
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
            spell_asset = game_asset_from_icon_url(
                "spell",
                spell_id,
                "websim-spell-details",
                icon_url,
                source="blizzard",
                status="verified",
                semantic_tags=["game", "spell", "talent"],
                usage=["talent_simulator", "websim_spell_details"],
                fallback_text=fallback_text_for(spell_payload.get("name") or f"Spell {spell_id}"),
            )
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
            upsert_websim_asset(conn, spell_asset)
            counts["media"] += 1
        if counts["spells"] % 25 == 0:
            conn.commit()
    conn.commit()
    return counts


def normalize_journal_instance_ref(value):
    category = ""
    ref = value
    if isinstance(value, (list, tuple)) and value:
        ref = value[0]
        category = str(value[1] or "") if len(value) > 1 else ""
    if not isinstance(ref, dict):
        return {}
    ref_category = ref.get("category")
    if isinstance(ref_category, dict):
        ref_category = ref_category.get("name") or ref_category.get("type") or ""
    category = category or str(ref_category or "")
    instance_id = str(ref.get("instanceId") or ref.get("id") or extract_id_from_ref(ref) or "").strip()
    return {
        **ref,
        "id": str(ref.get("id") or instance_id),
        "instanceId": instance_id,
        "category": category or "Dungeon",
    }


def limited_sync_items(items, limit):
    rows = list(items or [])
    if limit < 0:
        return rows, 0
    return rows[:limit], max(0, len(rows) - limit)


def item_payload_is_explicit_non_equipment(payload):
    if not isinstance(payload, dict):
        return False
    item_class = payload.get("item_class") if isinstance(payload.get("item_class"), dict) else {}
    return bool(item_class and not (payload_item_class_is_armor(item_class) or payload_item_class_is_weapon(item_class)))


def item_payload_is_equipment_loot(payload, slot=""):
    if not normalize_slot(slot):
        return False
    if item_payload_is_explicit_non_equipment(payload):
        return False
    return True


def sync_blizzard_journal(conn, token, region=DEFAULT_REGION, locale=DEFAULT_LOCALE):
    now = utc_now()
    instance_limit = int_env("WOW_WEBSIM_SYNC_INSTANCE_LIMIT", 20)
    raid_instance_limit = int_env("WOW_WEBSIM_SYNC_RAID_INSTANCE_LIMIT", 8)
    encounter_limit = int_env("WOW_WEBSIM_SYNC_ENCOUNTER_LIMIT", 200)
    item_limit = int_env("WOW_WEBSIM_SYNC_ITEM_LIMIT", 1000)
    season = resolve_current_mythic_season(token, region, locale)
    all_dungeons = [
        {**dungeon, "instanceId": str(dungeon.get("instanceId") or dungeon.get("id") or ""), "category": "Dungeon"}
        for dungeon in (season.get("dungeons") or [])
        if str(dungeon.get("instanceId") or dungeon.get("id") or "").strip()
    ]
    dungeons, truncated_dungeons = limited_sync_items(all_dungeons, instance_limit)
    raid_refs = []
    journal_expansion_name = ""
    raid_selection_failure = None
    try:
        selected_refs = selected_journal_instance_refs(token, region, season.get("locale") or locale)
        if isinstance(selected_refs, tuple) and selected_refs and isinstance(selected_refs[0], list):
            journal_expansion_name = str(selected_refs[1] or "") if len(selected_refs) > 1 else ""
            selected_refs = selected_refs[0]
        for raw_ref in selected_refs or []:
            ref = normalize_journal_instance_ref(raw_ref)
            if str(ref.get("category") or "").lower() == "raid":
                raid_refs.append({
                    **ref,
                    "instanceId": str(ref.get("instanceId") or ref.get("id") or ""),
                    "category": "Raid",
                })
    except Exception as error:
        raid_selection_failure = str(error)
        raid_refs = []
    raid_pool_status = current_season_raid_pool_status({"raids": raid_refs})
    raid_refs = raid_pool_status.get("refs") or []
    season = {
        **season,
        "raids": raid_refs or official_current_season_raid_refs(),
        "raidPoolStatus": raid_pool_status,
    }
    if journal_expansion_name:
        season["journalExpansionName"] = journal_expansion_name
    save_active_season_payload(conn, season)
    conn.commit()
    limited_raid_refs, truncated_raids = limited_sync_items(raid_refs, raid_instance_limit)
    instance_refs = []
    seen_instances = set()
    for ref in [*dungeons, *limited_raid_refs]:
        instance_id = str(ref.get("instanceId") or ref.get("id") or "").strip()
        if not instance_id or instance_id in seen_instances:
            continue
        seen_instances.add(instance_id)
        instance_refs.append({**ref, "instanceId": instance_id})
    counts = {
        "instances": 0,
        "dungeonInstances": 0,
        "raidInstances": 0,
        "encounters": 0,
        "loot": 0,
        "items": 0,
        "seasonId": season.get("seasonId"),
        "seasonLabel": season.get("seasonLabel"),
        "seasonRevision": season.get("seasonRevision"),
        "dataStatus": season.get("dataStatus"),
        "limits": {
            "instances": instance_limit,
            "raidInstances": raid_instance_limit,
            "encounters": encounter_limit,
            "items": item_limit,
        },
        "truncation": {
            "dungeonInstances": truncated_dungeons,
            "raidInstances": truncated_raids,
            "encounters": 0,
            "items": 0,
        },
        "skippedNonGearLoot": 0,
        "skippedNonGearLootExamples": [],
        "cachedItems": 0,
        "fetchFailureCount": 0,
        "fetchFailures": [],
        "truncated": False,
        "blockers": list(raid_pool_status.get("blockers") or []),
    }
    if raid_selection_failure:
        counts["fetchFailures"].append(
            {
                "type": "raid_selection",
                "id": "journal-expansion",
                "name": journal_expansion_name or "Journal expansion",
                "message": raid_selection_failure,
            }
        )
    fetched_items = set()
    discovered_item_sets = season_item_set_refs(season)

    for instance_ref in instance_refs:
        instance_id = str(instance_ref.get("instanceId") or "")
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
        except Exception as error:
            error_message = str(error)
            counts["fetchFailures"].append(
                {
                    "type": "instance",
                    "id": str(instance_id),
                    "name": instance_ref.get("name") or f"Instance {instance_id}",
                    "message": error_message,
                }
            )
            instance = {
                "id": instance_id,
                "name": instance_ref.get("name") or f"Instance {instance_id}",
                "category": {"name": instance_ref.get("category") or "Dungeon"},
                "encounters": [],
                "_syncError": error_message,
            }
        instance_name = instance.get("name") or instance_ref.get("name") or f"Instance {instance_id}"
        category = (instance.get("category") or {}).get("name") or instance_ref.get("category") or "Dungeon"
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
        if str(category).lower() == "raid":
            counts["raidInstances"] += 1
        else:
            counts["dungeonInstances"] += 1

        encounter_refs = list_keyed_values(instance, "encounters")
        remaining_encounter_capacity = encounter_limit - counts["encounters"] if encounter_limit >= 0 else len(encounter_refs)
        if remaining_encounter_capacity <= 0:
            counts["truncation"]["encounters"] += len(encounter_refs)
            continue
        encounter_refs, skipped_encounters = limited_sync_items(encounter_refs, remaining_encounter_capacity)
        counts["truncation"]["encounters"] += skipped_encounters
        for encounter_ref in encounter_refs:
            encounter_id = extract_id_from_ref(encounter_ref)
            if not encounter_id:
                continue
            try:
                encounter = blizzard_get(
                    f"/data/wow/journal-encounter/{encounter_id}",
                    token,
                    region,
                    season.get("locale") or locale,
                    namespace=blizzard_namespace(region, "static"),
                )
            except Exception as error:
                counts["fetchFailures"].append(
                    {
                        "type": "encounter",
                        "id": str(encounter_id),
                        "name": (encounter_ref or {}).get("name") or f"Encounter {encounter_id}",
                        "message": str(error),
                    }
                )
                continue
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
            item_refs = []
            for loot_ref in list_keyed_values(encounter, "items", "loot"):
                item_ref = loot_ref.get("item") if isinstance(loot_ref, dict) else loot_ref
                item_id = extract_id_from_ref(item_ref)
                if not item_id:
                    continue
                item_refs.append((loot_ref, item_ref, item_id))
            remaining_item_capacity = item_limit - len(fetched_items) if item_limit >= 0 else len(item_refs)
            if remaining_item_capacity <= 0:
                counts["truncation"]["items"] += len(item_refs)
                continue
            limited_item_refs, skipped_items = limited_sync_items(item_refs, remaining_item_capacity)
            counts["truncation"]["items"] += skipped_items
            for loot_ref, item_ref, item_id in limited_item_refs:
                item_payload = {}
                media_payload = {}
                saved_metadata = existing_websim_item_metadata(conn, item_id)
                if item_id not in fetched_items:
                    fallback_item_name = (item_ref or {}).get("name") if isinstance(item_ref, dict) else ""
                    try:
                        item_metadata = fetch_blizzard_item_metadata(
                            token,
                            item_id,
                            region,
                            season.get("locale") or locale,
                            fallback_name=fallback_item_name,
                        )
                    except Exception as error:
                        cached_payload = (saved_metadata or {}).get("payload") if isinstance(saved_metadata, dict) else {}
                        cached_slot = (saved_metadata or {}).get("slot") if isinstance(saved_metadata, dict) else ""
                        counts["fetchFailures"].append(
                            {
                                "type": "item",
                                "id": str(item_id),
                                "name": fallback_item_name or f"Item {item_id}",
                                "message": str(error),
                                "encounterId": str(encounter_id),
                                "instanceId": str(instance_id),
                            }
                        )
                        fetched_items.add(item_id)
                        if not (
                            saved_metadata
                            and (saved_metadata.get("metadataStatus") or "") == "verified"
                            and isinstance(cached_payload, dict)
                            and item_payload_is_equipment_loot(cached_payload, cached_slot)
                        ):
                            continue
                        item_payload = cached_payload
                        media_payload = {}
                        counts["cachedItems"] += 1
                        set_ref = item_set_ref_from_payload(item_payload)
                        set_id = set_ref.get("id") or ""
                        set_name = set_ref.get("name") or ""
                        set_key = set_id or set_name
                        if set_key:
                            discovered_item_sets[set_key] = {"id": set_id, "name": set_name}
                    else:
                        item_payload = item_metadata.get("payload") or {}
                        media_payload = item_metadata.get("media") or {}
                        save_websim_item_metadata(
                            conn,
                            item_id,
                            item_payload,
                            media_payload,
                            fallback_name=item_metadata.get("fallbackName") or "",
                            english_payload=item_metadata.get("englishPayload") or {},
                            locale=item_metadata.get("locale") or season.get("locale") or locale,
                        )
                        saved_metadata = existing_websim_item_metadata(conn, item_id)
                        fetched_items.add(item_id)
                        counts["items"] += 1
                        set_ref = item_set_ref_from_payload(item_payload)
                        set_id = set_ref.get("id") or ""
                        set_name = set_ref.get("name") or ""
                        set_key = set_id or set_name
                        if set_key:
                            discovered_item_sets[set_key] = {"id": set_id, "name": set_name}
                item_name = item_payload.get("name") or (item_ref or {}).get("name") or (saved_metadata or {}).get("displayName") or f"Item {item_id}"
                slot = item_slot_from_payload(item_payload) or ((saved_metadata or {}).get("slot") or "")
                quality = (item_payload.get("quality") or {}).get("name") or (saved_metadata or {}).get("quality") or ""
                icon_url = icon_url_from_media(media_payload) or (saved_metadata or {}).get("iconUrl") or ""
                existing_payload = (saved_metadata or {}).get("payload") if isinstance(saved_metadata, dict) else {}
                item_payload_to_store = existing_payload if isinstance(existing_payload, dict) and existing_payload else item_payload
                if not item_payload_is_equipment_loot(item_payload_to_store, slot):
                    counts["skippedNonGearLoot"] += 1
                    if len(counts["skippedNonGearLootExamples"]) < 5:
                        counts["skippedNonGearLootExamples"].append(
                            {
                                "itemId": str(item_id),
                                "name": item_name,
                                "reason": "Battle.net item metadata is not equippable gear",
                            }
                        )
                    continue
                loot_asset = game_asset_from_icon_url(
                    "item",
                    item_id,
                    "websim-loot",
                    icon_url,
                    source="blizzard",
                    status="verified",
                    semantic_tags=["game", "gear", "item", "loot", slot],
                    usage=["websim_loot", "builds_detail"],
                    fallback_text=fallback_text_for(item_name),
                )
                if saved_metadata:
                    conn.execute(
                        """
                        UPDATE websim_items
                        SET name = ?, slot = ?, quality = ?, icon_url = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (item_name, slot, quality, icon_url, now, str(item_id)),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO websim_items (id, name, slot, quality, icon_url, payload_json, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            name=excluded.name,
                            slot=excluded.slot,
                            quality=excluded.quality,
                            icon_url=excluded.icon_url,
                            updated_at=excluded.updated_at
                        """,
                        (str(item_id), item_name, slot, quality, icon_url, json.dumps(item_payload_to_store, ensure_ascii=False), now),
                    )
                saved_metadata = existing_websim_item_metadata(conn, item_id)
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
                upsert_websim_asset(conn, loot_asset)
                counts["loot"] += 1
        conn.commit()
    if discovered_item_sets:
        season = {
            **season,
            "itemSets": sorted(
                (ref for ref in discovered_item_sets.values() if ref.get("id") or ref.get("name")),
                key=lambda ref: (ref.get("name") or "", ref.get("id") or ""),
            ),
        }
        save_active_season_payload(conn, season)
    truncation = counts["truncation"]
    blockers = list(counts.get("blockers") or [])
    if truncation["dungeonInstances"]:
        blockers.append(f"Battle.net journal dungeon instance sync truncated: {truncation['dungeonInstances']} not fetched")
    if truncation["raidInstances"]:
        blockers.append(f"Battle.net journal raid instance sync truncated: {truncation['raidInstances']} not fetched")
    if truncation["encounters"]:
        blockers.append(f"Battle.net journal encounter sync truncated: {truncation['encounters']} not fetched")
    if truncation["items"]:
        blockers.append(f"Battle.net journal item sync truncated: {truncation['items']} not fetched")
    for failure in counts["fetchFailures"]:
        failure_type = failure.get("type") or "resource"
        failure_id = failure.get("id") or "unknown"
        failure_message = failure.get("message") or "unknown error"
        blockers.append(f"Battle.net journal {failure_type} {failure_id} fetch failed: {failure_message}")
    if not blockers:
        for table in ("websim_loot", "websim_encounters", "websim_instances"):
            conn.execute(f"DELETE FROM {table} WHERE updated_at IS NULL OR updated_at != ?", (now,))
    counts["fetchFailureCount"] = len(counts["fetchFailures"])
    counts["blockers"] = blockers
    counts["truncated"] = bool(blockers)
    conn.commit()
    return counts


def discovered_item_set_refs(conn):
    ensure_websim_tables(conn)
    refs = {}
    configured_ids = [
        value.strip()
        for value in os.environ.get("WOW_WEBSIM_SYNC_ITEM_SET_IDS", "").split(",")
        if value.strip()
    ]
    for set_id in configured_ids:
        refs.setdefault(set_id, {"id": set_id, "name": ""})
    rows = conn.execute(
        """
        SELECT DISTINCT payload_json
        FROM websim_items
        WHERE id IN (
            SELECT item_id FROM websim_gear_sources
            UNION
            SELECT item_id FROM websim_gear_variants
            UNION
            SELECT item_id FROM websim_loot
        )
        """
    ).fetchall()
    for (payload_json,) in rows:
        payload = safe_json_loads(payload_json, {})
        ref = item_set_ref_from_payload(payload if isinstance(payload, dict) else {})
        set_id = str(ref.get("id") or "").strip()
        if not set_id:
            continue
        refs[set_id] = {"id": set_id, "name": ref.get("name") or refs.get(set_id, {}).get("name") or ""}
    return refs


def save_websim_item_set(conn, set_id, payload, season_revision=""):
    now = utc_now()
    name = str((payload or {}).get("name") or f"Item Set {set_id}").strip()
    conn.execute(
        """
        INSERT INTO websim_item_sets (id, name, season_revision, source, status, payload_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            season_revision=excluded.season_revision,
            source=excluded.source,
            status=excluded.status,
            payload_json=excluded.payload_json,
            updated_at=excluded.updated_at
        """,
        (
            str(set_id),
            name,
            season_revision or "",
            ITEM_METADATA_SOURCE,
            "verified",
            json.dumps(payload or {}, ensure_ascii=False),
            now,
        ),
    )
    return {"id": str(set_id), "name": name}


def upsert_websim_item_set_item(conn, set_id, item, slot=""):
    now = utc_now()
    item_id = str(item.get("itemId") or "").strip()
    if not item_id:
        return False
    conn.execute(
        """
        INSERT INTO websim_item_set_items (id, set_id, item_id, name, slot, payload_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            set_id=excluded.set_id,
            item_id=excluded.item_id,
            name=excluded.name,
            slot=excluded.slot,
            payload_json=excluded.payload_json,
            updated_at=excluded.updated_at
        """,
        (
            f"{set_id}:{item_id}",
            str(set_id),
            item_id,
            str(item.get("name") or f"Item {item_id}")[:220],
            normalize_slot(slot or item.get("slot")) or "",
            json.dumps(item.get("payload") or item, ensure_ascii=False),
            now,
        ),
    )
    return True


def item_metadata_needs_fetch(metadata):
    if not isinstance(metadata, dict) or not metadata:
        return True
    payload = metadata.get("payload") if isinstance(metadata.get("payload"), dict) else {}
    if not item_payload_has_stat_evidence(payload):
        return True
    type_metadata = item_type_metadata_from_payload(payload)
    slot = normalize_slot(metadata.get("slot") or "")
    if slot in ARMOR_SLOTS and not type_metadata.get("armorType"):
        return True
    if slot in WEAPON_SLOTS and not type_metadata.get("weaponType"):
        return True
    return False


def sync_blizzard_item_sets(conn, token, region=DEFAULT_REGION, locale=DEFAULT_LOCALE, season=None):
    ensure_websim_tables(conn)
    season = season or get_active_season_payload(conn)
    season_revision = (season or {}).get("seasonRevision") or (season or {}).get("revision") or ""
    refs = discovered_item_set_refs(conn)
    refs_by_name = {
        normalize_item_set_name_key(ref.get("name")): set_id
        for set_id, ref in refs.items()
        if normalize_item_set_name_key(ref.get("name"))
    }
    for set_key, set_ref in season_item_set_refs(season).items():
        set_id = set_ref.get("id") or set_key
        name_key = normalize_item_set_name_key(set_ref.get("name") or set_key)
        if not str(set_ref.get("id") or "").strip() and name_key and name_key in refs_by_name:
            continue
        refs.setdefault(set_id, {"id": set_id, "name": set_ref.get("name") or ""})
        if set_ref.get("name") and not refs[set_id].get("name"):
            refs[set_id]["name"] = set_ref.get("name")
        if name_key:
            refs_by_name.setdefault(name_key, set_id)
    limit = int_env("WOW_WEBSIM_SYNC_ITEM_SET_LIMIT", 20)
    counts = {
        "itemSets": 0,
        "setItems": 0,
        "itemMetadata": 0,
        "sources": 0,
        "variants": 0,
        "skipped": 0,
        "errors": [],
    }
    conn.execute("DELETE FROM websim_item_sets")
    conn.execute("DELETE FROM websim_item_set_items")
    conn.execute("DELETE FROM websim_gear_sources WHERE source_type = 'tier_set' OR id LIKE 'set-%'")
    conn.execute("DELETE FROM websim_gear_variants WHERE source_type = 'tier_set' OR id LIKE 'set-partial-%'")
    for set_id, ref in list(refs.items())[:limit]:
        set_id = str(set_id or "").strip()
        if not set_id:
            counts["skipped"] += 1
            continue
        if not re.fullmatch(r"\d+", set_id):
            counts["skipped"] += 1
            set_name = str((ref or {}).get("name") or set_id).strip() or "unknown"
            counts["errors"].append(f"item-set {set_name}: missing numeric Battle.net item-set id")
            continue
        try:
            payload = blizzard_get(
                f"/data/wow/item-set/{set_id}",
                token,
                region,
                locale,
                namespace=blizzard_namespace(region, "static"),
            )
        except Exception as error:
            counts["errors"].append(f"item-set {set_id}: {error}")
            continue
        saved_set = save_websim_item_set(conn, set_id, payload, season_revision)
        set_name = saved_set.get("name") or ref.get("name") or f"Item Set {set_id}"
        counts["itemSets"] += 1
        for set_item in item_set_item_refs_from_payload(payload):
            item_id = set_item.get("itemId") or ""
            if not item_id:
                counts["skipped"] += 1
                continue
            metadata = existing_websim_item_metadata(conn, item_id)
            if item_metadata_needs_fetch(metadata):
                try:
                    item_metadata = fetch_blizzard_item_metadata(
                        token,
                        item_id,
                        region,
                        locale,
                        fallback_name=set_item.get("name") or "",
                        fallback_slot=set_item.get("slot") or "",
                    )
                    save_websim_item_metadata(
                        conn,
                        item_id,
                        item_metadata.get("payload") or {},
                        item_metadata.get("media") or {},
                        fallback_name=item_metadata.get("fallbackName") or set_item.get("name") or "",
                        english_payload=item_metadata.get("englishPayload") or {},
                        locale=item_metadata.get("locale") or locale,
                    )
                    metadata = existing_websim_item_metadata(conn, item_id)
                    counts["itemMetadata"] += 1
                except Exception as error:
                    counts["errors"].append(f"item {item_id}: {error}")
                    metadata = ensure_observed_item_metadata(
                        conn,
                        {
                            "itemId": item_id,
                            "name": set_item.get("name") or f"Item {item_id}",
                            "slot": set_item.get("slot") or "",
                            "sourceName": set_name,
                        },
                        normalize_slot(set_item.get("slot") or ""),
                        source="battle_net_item_set",
                        context_key="websim-item-set-reference",
                    )
            slot = normalize_slot((metadata or {}).get("slot") or set_item.get("slot") or "")
            display_name = (metadata or {}).get("displayName") or set_item.get("name") or f"Item {item_id}"
            upsert_websim_item_set_item(
                conn,
                set_id,
                {**set_item, "name": display_name},
                slot,
            )
            counts["setItems"] += 1
            upsert_gear_source(
                conn,
                {
                    "id": f"set-{set_id}-{item_id}",
                    "itemId": item_id,
                    "sourceType": "tier_set",
                    "sourceLabel": set_name,
                    "seasonRevision": season_revision,
                    "payload": {"authority": ITEM_METADATA_SOURCE, "setId": str(set_id), "setName": set_name},
                },
            )
            counts["sources"] += 1
            upsert_gear_variant(
                conn,
                {
                    "id": f"set-partial-{set_id}-{item_id}-{slot or 'slot'}",
                    "itemId": item_id,
                    "slot": slot,
                    "variantKey": "needs-variant",
                    "label": "套装装等 / 难度待补",
                    "sourceType": "tier_set",
                    "difficultyKey": "needs-variant",
                    "itemLevel": 0,
                    "simcOptions": {},
                    "status": "partial",
                    "blockers": ["missing deterministic SimC variant preset"],
                    "payload": {"seasonRevision": season_revision, "setId": str(set_id), "setName": set_name},
                },
            )
            counts["variants"] += 1
    conn.commit()
    return counts


def journal_expansion_name_key(ref):
    return normalize_localized_name_key(ref.get("name") or "") if isinstance(ref, dict) else ""


def selected_journal_expansion_ref(refs, expansion_name=""):
    rows = [ref for ref in refs or [] if isinstance(ref, dict)]
    preferred_key_groups = [
        {normalize_localized_name_key(expansion_name)} if expansion_name else set(),
        {normalize_localized_name_key(value) for value in ("Current Season", "本赛季")},
        {normalize_localized_name_key(value) for value in ("Midnight", "至暗之夜")},
    ]
    for keys in preferred_key_groups:
        keys = {key for key in keys if key}
        if not keys:
            continue
        selected = next((ref for ref in rows if journal_expansion_name_key(ref) in keys), None)
        if selected:
            return selected
    return None


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
        selected = selected_journal_expansion_ref(refs, expansion_name)
        if not selected and locale != "en_US":
            fallback_index = blizzard_get("/data/wow/journal-expansion/index", token, region, "en_US")
            fallback_refs = list_keyed_values(fallback_index, "tiers", "expansions")
            selected = selected_journal_expansion_ref(fallback_refs, expansion_name)
            refs = fallback_refs if selected else refs
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


def current_simc_trait_data_file():
    explicit = os.environ.get("WOW_SIMC_TRAIT_DATA_FILE", "").strip()
    if explicit and Path(explicit).exists():
        return Path(explicit)
    generated = DEFAULT_SIMC_ROOT / "current" / "engine" / "dbc" / "generated" / "trait_data.inc"
    if generated.exists():
        return generated
    return None


def current_simc_spelltext_data_file():
    explicit = os.environ.get("WOW_SIMC_SPELLTEXT_DATA_FILE", "").strip()
    if explicit and Path(explicit).exists():
        return Path(explicit)
    trait_explicit = os.environ.get("WOW_SIMC_TRAIT_DATA_FILE", "").strip()
    if trait_explicit:
        sibling = Path(trait_explicit).with_name("spelltext_data.inc")
        if sibling.exists():
            return sibling
    generated = DEFAULT_SIMC_ROOT / "current" / "engine" / "dbc" / "generated" / "spelltext_data.inc"
    if generated.exists():
        return generated
    return None


def download_simc_text(url):
    if not DEFAULT_SIMC_REMOTE_ENABLED or not url:
        return "", ""
    request = Request(url, headers={"User-Agent": "wow-websim-sync"})
    with urlopen(request, timeout=int_env("WOW_SIMC_FETCH_TIMEOUT_SECONDS", 30)) as response:
        return response.read().decode("utf-8", errors="ignore"), url


def download_simc_trait_data_text():
    return download_simc_text(DEFAULT_SIMC_TRAIT_DATA_URL)


def download_simc_spelltext_data_text():
    return download_simc_text(DEFAULT_SIMC_SPELLTEXT_DATA_URL)


def simc_build_from_text(text):
    match = re.search(r"wow build(?: level)?\s+([0-9.]+)", str(text or ""), re.IGNORECASE)
    return match.group(1) if match else ""


def wago_db2_locale(locale=DEFAULT_LOCALE):
    normalized = str(locale or "en_US").replace("_", "")
    return normalized or "enUS"


def download_wago_db2_csv(table, build, locale="enUS"):
    if not DEFAULT_WAGO_DB2_ENABLED or not DEFAULT_WAGO_DB2_BASE_URL or not table or not build:
        return "", ""
    query = urlencode({"build": build, "locale": wago_db2_locale(locale)})
    url = f"{DEFAULT_WAGO_DB2_BASE_URL}/{table}/csv?{query}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 wow-websim-sync"})
    with urlopen(request, timeout=int_env("WOW_WAGO_DB2_FETCH_TIMEOUT_SECONDS", 30)) as response:
        return response.read().decode("utf-8", errors="ignore"), url


def download_wago_trait_edge_csv(build):
    if not DEFAULT_WAGO_DB2_TRAIT_EDGE_ENABLED or not DEFAULT_WAGO_DB2_BASE_URL or not build:
        return "", ""
    query = urlencode({"build": build, "locale": "enUS"})
    url = f"{DEFAULT_WAGO_DB2_BASE_URL}/TraitEdge/csv?{query}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 wow-websim-sync"})
    with urlopen(request, timeout=int_env("WOW_WAGO_DB2_TRAIT_EDGE_TIMEOUT_SECONDS", 20)) as response:
        return response.read().decode("utf-8", errors="ignore"), url


def tar_member_suffix(tar, suffix):
    for member in tar.getmembers():
        if member.name.endswith(suffix):
            return member
    return None


def parse_ints(value):
    return [int(item) for item in re.findall(r"-?\d+", str(value or ""))]


SIMC_C_STRING_TOKEN = r'(?:0|"(?:\\.|[^"\\])*")'
SIMC_SPELLTEXT_RECORD_RE = re.compile(
    r"\{\s*(?P<spell_id>\d+)\s*,\s*"
    rf"(?P<desc>{SIMC_C_STRING_TOKEN})\s*,\s*"
    rf"(?P<tooltip>{SIMC_C_STRING_TOKEN})\s*,\s*"
    rf"(?P<rank>{SIMC_C_STRING_TOKEN})\s*\}},?"
)


def parse_simc_c_string(value):
    value = str(value or "").strip()
    if value == "0" or not value:
        return ""
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]
    try:
        return bytes(value, "utf-8").decode("unicode_escape", errors="ignore")
    except Exception:
        return value.replace(r"\r", "\r").replace(r"\n", "\n").replace(r"\"", '"').replace(r"\\", "\\")


def clean_simc_spell_text(value):
    text = parse_simc_c_string(value)
    text = re.sub(r"\|[cC][0-9A-Fa-f]{8}", "", text)
    text = text.replace("|r", "").replace("|R", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\$@spellicon\d+", "", text)
    text = re.sub(r"\$@spellname\d+:?", "", text)
    text = re.sub(r"\$@spelldesc\d+", "", text)
    text = re.sub(r"\$l([^:;\s]+):([^;]+);", r"\1/\2", text)
    conditional = re.compile(r"\$\?[^[]+\[([^\[\]]*)\]\[([^\[\]]*)\]")
    for _ in range(8):
        updated = conditional.sub(
            lambda match: " / ".join(part.strip() for part in match.groups() if part.strip()),
            text,
        )
        if updated == text:
            break
        text = updated
    text = re.sub(r"\$\?[^[]+\[", "", text)
    text = text.replace("][", " / ")
    text = text.replace("[", "").replace("]", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


UNRESOLVED_SPELL_TEXT_RE = re.compile(
    r"\$\?|\$\{|\$@[A-Za-z][A-Za-z0-9_]*\d*|\$\d+[A-Za-z]\d*|\$[A-Za-z][A-Za-z0-9_]*"
)
TALENT_DESCRIPTION_MISSING = "描述待补：当前天赋目录缺少可展示说明。"
TALENT_DESCRIPTION_UNRESOLVED = "描述待补：当前上游说明包含未解析数值，等待法术文本对账。"


def normalize_spell_display_text(value):
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\|[cC][0-9A-Fa-f]{8}", "", text)
    text = text.replace("|r", "").replace("|R", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def spell_text_has_unresolved_tokens(value):
    return bool(UNRESOLVED_SPELL_TEXT_RE.search(str(value or "")))


def talent_spell_display_description(value):
    text = normalize_spell_display_text(value)
    if not text:
        return TALENT_DESCRIPTION_MISSING, "missing"
    if spell_text_has_unresolved_tokens(text):
        return TALENT_DESCRIPTION_UNRESOLVED, "pending_formula_resolution"
    return text, "ready"


def simc_spell_description(desc, tooltip):
    desc_text = clean_simc_spell_text(desc)
    tooltip_text = clean_simc_spell_text(tooltip)
    if desc_text and tooltip_text and tooltip_text not in desc_text:
        return f"{desc_text}\n\n{tooltip_text}"
    return desc_text or tooltip_text


def parse_spelltext_data_text(text, spell_ids=None, limit=50000):
    wanted = {int(spell_id) for spell_id in spell_ids or [] if int(spell_id or 0) > 0}
    details = []
    seen = set()
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        match = SIMC_SPELLTEXT_RECORD_RE.match(stripped)
        if not match:
            continue
        spell_id = int(match.group("spell_id"))
        if wanted and spell_id not in wanted:
            continue
        if spell_id in seen:
            continue
        description = simc_spell_description(match.group("desc"), match.group("tooltip"))
        rank = clean_simc_spell_text(match.group("rank"))
        if not description and not rank:
            continue
        seen.add(spell_id)
        details.append(
            {
                "spellId": spell_id,
                "name": "",
                "description": description,
                "rank": rank,
                "tooltip": clean_simc_spell_text(match.group("tooltip")),
                "iconUrl": "",
                "locale": "en_US",
                "source": "simulationcraft",
            }
        )
        if len(details) >= limit:
            break
    return details


SIMC_TRAIT_TREE_TYPES = {
    1: "class",
    2: "spec",
    3: "hero",
}


def simc_hero_key(label):
    return slugify(str(label or "").replace("'", ""), "hero")


def parse_trait_sub_tree_data(text):
    block_start = str(text or "").find("__trait_sub_tree_data")
    block = str(text or "")[block_start:] if block_start >= 0 else str(text or "")
    subtrees = {}
    for match in re.finditer(r'\{\s*(\d+),\s*"([^"]+)",\s*(\d+)\s*\}', block):
        hero_id = int(match.group(1))
        label = match.group(2).strip()
        class_id = int(match.group(3))
        key = simc_hero_key(label)
        subtrees[hero_id] = {
            "id": hero_id,
            "key": key,
            "label": label,
            "classId": class_id,
            "classKey": GAME_CLASS_ID_TO_KEY.get(class_id, ""),
        }
    return subtrees


def iter_trait_data_records(text):
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        name_match = re.search(r'"([^"]*)"', stripped)
        if name_match:
            name = name_match.group(1).strip()
            before = stripped[:name_match.start()] + stripped[name_match.end():]
        elif "//" in stripped:
            name = stripped.split("//", 1)[1].strip()
            before = stripped.split("//", 1)[0]
        else:
            continue
        fields = parse_ints(before)
        if len(fields) < 23:
            continue
        yield {
            "treeIndex": fields[0],
            "classId": fields[1],
            "traitId": fields[2],
            "nodeId": fields[3],
            "rank": fields[4],
            "pointRequirement": fields[5],
            "traitDefinitionId": fields[6],
            "spellId": fields[7],
            "replaceSpellId": fields[8],
            "overrideSpellId": fields[9],
            "row": fields[10],
            "col": fields[11],
            "selectionIndex": fields[12],
            "name": name,
            "specIds": [value for value in fields[13:17] if value > 0],
            "starterSpecIds": [value for value in fields[17:21] if value > 0],
            "heroId": fields[21],
            "nodeType": fields[22],
        }


def specs_for_class(class_key):
    klass = next((item for item in WOW_CLASSES if item["key"] == class_key), None)
    return list(klass.get("specs", [])) if klass else []


def spec_ids_for_class(class_key):
    return [
        spec_id
        for spec_id, (mapped_class, _spec_key) in SPEC_ID_TO_KEY.items()
        if mapped_class == class_key
    ]


def target_spec_ids_for_record(record, selection_specs_by_hero):
    class_key = GAME_CLASS_ID_TO_KEY.get(record["classId"], "")
    if not class_key:
        return []
    if record["treeIndex"] == 3:
        hero_specs = sorted(selection_specs_by_hero.get(record["heroId"]) or [])
        spec_ids = hero_specs or record["specIds"] or spec_ids_for_class(class_key)
    elif record["specIds"]:
        spec_ids = record["specIds"]
    else:
        spec_ids = spec_ids_for_class(class_key)
    return [
        spec_id
        for spec_id in spec_ids
        if SPEC_ID_TO_KEY.get(spec_id, ("", ""))[0] == class_key
    ]


def simc_shape_for(record):
    if record["row"] >= 11:
        return "apex"
    if record["nodeType"] == 2:
        return "choice"
    if record["treeIndex"] == 3 and record["row"] in {1, 5}:
        return "circle"
    if record["row"] == 1 or record["row"] >= 8:
        return "circle"
    return "square"


def simc_tree_id(record, tree_type, class_key, spec_key, hero_key):
    if tree_type == "class":
        return f"class:{class_key}"
    if tree_type == "hero":
        return f"hero:{hero_key}"
    return f"spec:{class_key}:{spec_key}"


def simc_rank_entry_for(record):
    return {
        "rank": 0,
        "points": max(1, int(record.get("rank") or 1)),
        "pointStart": 0,
        "pointEnd": 0,
        "traitId": record["traitId"],
        "traitDefinitionId": record["traitDefinitionId"],
        "spellId": record["spellId"],
        "selectionIndex": record["selectionIndex"],
        "name": record["name"],
        "description": "",
    }


def normalize_simc_rank_entries(entries):
    normalized = []
    total_points = 0
    seen_spells = set()
    for entry in sorted(
        entries or [],
        key=lambda item: (
            int(item.get("selectionIndex") or 0),
            int(item.get("traitId") or 0),
            int(item.get("spellId") or 0),
        ),
    ):
        spell_id = int(entry.get("spellId") or 0)
        if spell_id in seen_spells:
            continue
        seen_spells.add(spell_id)
        points = max(1, int(entry.get("points") or 1))
        total_points += points
        next_entry = dict(entry)
        next_entry["rank"] = len(normalized) + 1
        next_entry["points"] = points
        next_entry["pointStart"] = total_points - points + 1
        next_entry["pointEnd"] = total_points
        normalized.append(next_entry)
    return normalized, total_points


def refresh_simc_rank_payload(talent):
    payload = talent.setdefault("payload", {})
    entries, total_points = normalize_simc_rank_entries(payload.get("rankEntries") or [])
    if not entries:
        return talent
    payload["rankEntries"] = entries
    payload["rankCount"] = len(entries)
    payload["rank"] = max(1, total_points)
    payload["maxRank"] = max(1, total_points)
    first = entries[0]
    talent["rank"] = payload["rank"]
    talent["maxRank"] = payload["maxRank"]
    talent["spellId"] = int(first.get("spellId") or talent.get("spellId") or 0)
    talent["traitId"] = int(first.get("traitId") or talent.get("traitId") or 0)
    payload["spellId"] = talent["spellId"]
    payload["traitId"] = talent["traitId"]
    payload["traitDefinitionId"] = int(first.get("traitDefinitionId") or payload.get("traitDefinitionId") or 0)
    payload["selectionIndex"] = int(first.get("selectionIndex") or payload.get("selectionIndex") or 0)
    return talent


def parse_trait_data_text(text, limit=20000):
    subtrees = parse_trait_sub_tree_data(text)
    records = list(iter_trait_data_records(text))
    selection_specs_by_hero = {}
    for record in records:
        if record["treeIndex"] != 4 or not record["heroId"]:
            continue
        selection_specs_by_hero.setdefault(record["heroId"], set()).update(record["specIds"])

    talents = []
    seen = set()
    grouped = {}
    for record in records:
        tree_type = SIMC_TRAIT_TREE_TYPES.get(record["treeIndex"])
        if not tree_type or record["spellId"] <= 0 or not record["name"] or record["name"] == "0":
            continue
        class_key = GAME_CLASS_ID_TO_KEY.get(record["classId"], "")
        if not class_key:
            continue
        hero = subtrees.get(record["heroId"], {})
        hero_key = hero.get("key", "")
        hero_label = hero.get("label", "")
        for spec_id in target_spec_ids_for_record(record, selection_specs_by_hero):
            spec_info = SPEC_ID_TO_KEY.get(spec_id)
            if not spec_info:
                continue
            _mapped_class, spec_key = spec_info
            node_key = (
                record["treeIndex"],
                record["traitId"] if record["nodeType"] == 2 else record["nodeId"],
                record["nodeId"],
                class_key,
                spec_key,
                hero_key,
            )
            if node_key in seen:
                if record["nodeType"] != 2 and node_key in grouped:
                    grouped[node_key]["payload"].setdefault("rankEntries", []).append(simc_rank_entry_for(record))
                    refresh_simc_rank_payload(grouped[node_key])
                continue
            seen.add(node_key)
            choice_group = ""
            if record["nodeType"] == 2:
                choice_group = ":".join(
                    [
                        "simc-choice",
                        tree_type,
                        class_key,
                        spec_key,
                        hero_key or "none",
                        str(record["nodeId"]),
                    ]
                )
            selected_rank = 1 if spec_id in record["starterSpecIds"] else 0
            if tree_type == "hero" and record["row"] == 1:
                selected_rank = max(selected_rank, 1)
            granted_rank = selected_rank
            node_id_parts = ["simc", tree_type, str(record["traitId"]), class_key, spec_key]
            if hero_key:
                node_id_parts.append(hero_key)
            payload = {
                "treeType": tree_type,
                "treeIndex": record["treeIndex"],
                "classId": record["classId"],
                "specId": spec_id,
                "traitId": record["traitId"],
                "nodeId": record["nodeId"],
                "traitDefinitionId": record["traitDefinitionId"],
                "replaceSpellId": record["replaceSpellId"],
                "overrideSpellId": record["overrideSpellId"],
                "selectionIndex": record["selectionIndex"],
                "idSpecs": record["specIds"],
                "starterSpecIds": record["starterSpecIds"],
                "heroId": record["heroId"],
                "heroKey": hero_key,
                "heroLabel": hero_label,
                "nodeType": record["nodeType"],
                "rank": max(1, record["rank"]),
                "selectedRank": selected_rank,
                "grantedRank": granted_rank,
                "granted": granted_rank > 0,
                "rankEntries": [simc_rank_entry_for(record)],
                "choiceGroup": choice_group,
                "shape": simc_shape_for(record),
                "pointRequirement": max(0, record["pointRequirement"]),
                "source": "simulationcraft",
            }
            talent = {
                "id": "-".join(node_id_parts),
                "traitId": record["traitId"],
                "classKey": class_key,
                "specKey": spec_key,
                "treeId": simc_tree_id(record, tree_type, class_key, spec_key, hero_key),
                "treeType": tree_type,
                "row": record["row"],
                "col": record["col"],
                "spellId": record["spellId"],
                "name": record["name"],
                "rank": max(1, record["rank"]),
                "selectedRank": selected_rank,
                "grantedRank": granted_rank,
                "granted": granted_rank > 0,
                "payload": payload,
            }
            refresh_simc_rank_payload(talent)
            talents.append(talent)
            if record["nodeType"] != 2:
                grouped[node_key] = talent
            if len(talents) >= limit:
                return talents
    return talents


def parse_trait_edge_data_text(text):
    edges = []
    if not text:
        return edges
    try:
        rows = csv.DictReader(io.StringIO(str(text or "")))
        for row in rows:
            left = int(row.get("LeftTraitNodeID") or 0)
            right = int(row.get("RightTraitNodeID") or 0)
            if left <= 0 or right <= 0 or left == right:
                continue
            edges.append(
                {
                    "leftNodeId": left,
                    "rightNodeId": right,
                    "type": int(row.get("Type") or 0),
                    "visualStyle": int(row.get("VisualStyle") or 0),
                }
            )
    except (csv.Error, TypeError, ValueError):
        return []
    return edges


def talent_edge_parent_child(left, right):
    left_pos = (int(left.get("row") or 0), int(left.get("col") or 0), str(left.get("id") or ""))
    right_pos = (int(right.get("row") or 0), int(right.get("col") or 0), str(right.get("id") or ""))
    return (left, right) if left_pos <= right_pos else (right, left)


def apply_trait_edges_to_talents(talents, edges, source="wago-db2-traitedge"):
    if not talents or not edges:
        return 0
    by_context_and_node = {}
    for talent in talents:
        payload = talent.get("payload") or {}
        node_id = int(payload.get("nodeId") or 0)
        if node_id <= 0:
            continue
        context = (
            talent.get("treeId"),
            talent.get("classKey"),
            talent.get("specKey"),
            payload.get("heroKey", ""),
        )
        by_context_and_node.setdefault((context, node_id), []).append(talent)

    added = 0
    for edge in edges:
        left_node_id = int(edge.get("leftNodeId") or 0)
        right_node_id = int(edge.get("rightNodeId") or 0)
        contexts = {
            context
            for context, node_id in by_context_and_node
            if node_id in {left_node_id, right_node_id}
        }
        for tree_id in contexts:
            left_nodes = by_context_and_node.get((tree_id, left_node_id), [])
            right_nodes = by_context_and_node.get((tree_id, right_node_id), [])
            for left in left_nodes:
                for right in right_nodes:
                    if left.get("treeId") != right.get("treeId"):
                        continue
                    parent, child = talent_edge_parent_child(left, right)
                    payload = child.setdefault("payload", {})
                    parent_ids = list(payload.get("parentIds") or [])
                    if parent["id"] in parent_ids:
                        continue
                    parent_ids.append(parent["id"])
                    payload["parentIds"] = parent_ids
                    payload.setdefault("parentMode", "any")
                    payload["dependencySource"] = source
                    added += 1
    for talent in talents:
        payload = talent.get("payload") or {}
        parent_ids = list(payload.get("parentIds") or [])
        if len(parent_ids) < 2:
            continue
        by_id = {item["id"]: item for item in talents if item.get("id") in parent_ids}
        payload["parentIds"] = sorted(
            parent_ids,
            key=lambda parent_id: (
                int((by_id.get(parent_id) or {}).get("row") or 0),
                int((by_id.get(parent_id) or {}).get("col") or 0),
                parent_id,
            ),
        )
    return added


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


def simc_talent_spell_ids(talents):
    spell_ids = set()
    for talent in talents or []:
        spell_id = int(talent.get("spellId") or 0)
        if spell_id > 0:
            spell_ids.add(spell_id)
        payload = talent.get("payload") or {}
        for entry in payload.get("rankEntries") or talent.get("rankEntries") or []:
            entry_spell_id = int(entry.get("spellId") or 0)
            if entry_spell_id > 0:
                spell_ids.add(entry_spell_id)
    return sorted(spell_ids)


def attach_trait_edges_to_data(data, trait_text):
    build = simc_build_from_text(trait_text)
    data["build"] = build
    data.setdefault("dependencies", 0)
    data.setdefault("traitEdgeSource", "")
    if not data.get("talents") or not build:
        return data
    try:
        edge_text, edge_source = download_wago_trait_edge_csv(build)
    except Exception:
        edge_text, edge_source = "", ""
    edges = parse_trait_edge_data_text(edge_text)
    if edges:
        data["dependencies"] = apply_trait_edges_to_talents(data["talents"], edges)
        data["traitEdgeSource"] = edge_source
    return data


def extract_simc_data_from_tar(tar_path):
    result = {
        "talents": [],
        "presets": [],
        "spellDetails": [],
        "source": str(tar_path or ""),
        "spellTextSource": "",
        "spellIcons": 0,
        "spellIconSource": "",
        "dependencies": 0,
        "traitEdgeSource": "",
        "build": "",
    }
    if not tar_path or not Path(tar_path).exists():
        return result
    with tarfile.open(tar_path, "r:gz") as tar:
        trait_text = ""
        trait_member = tar_member_suffix(tar, "engine/dbc/generated/trait_data.inc")
        if trait_member:
            extracted = tar.extractfile(trait_member)
            if extracted:
                trait_text = extracted.read().decode("utf-8", errors="ignore")
                result["talents"] = parse_trait_data_text(trait_text)
        spelltext_member = tar_member_suffix(tar, "engine/dbc/generated/spelltext_data.inc")
        if spelltext_member and result["talents"]:
            extracted = tar.extractfile(spelltext_member)
            if extracted:
                result["spellDetails"] = parse_spelltext_data_text(
                    extracted.read().decode("utf-8", errors="ignore"),
                    simc_talent_spell_ids(result["talents"]),
                )
                result["spellTextSource"] = f"{tar_path}:engine/dbc/generated/spelltext_data.inc"
        attach_wago_spell_icons_to_data(result, trait_text)
        attach_trait_edges_to_data(result, trait_text)
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


def extract_simc_data_from_trait_text(text, source, spelltext_text="", spelltext_source=""):
    talents = parse_trait_data_text(text)
    data = {
        "talents": talents,
        "presets": [],
        "spellDetails": parse_spelltext_data_text(spelltext_text, simc_talent_spell_ids(talents)) if spelltext_text else [],
        "source": source,
        "spellTextSource": spelltext_source,
        "dependencies": 0,
        "traitEdgeSource": "",
        "build": "",
        "spellIcons": 0,
        "spellIconSource": "",
    }
    attach_wago_spell_icons_to_data(data, text)
    return attach_trait_edges_to_data(data, text)


def extract_simc_generated_data():
    tar_path = current_simc_source_tar()
    if tar_path:
        data = extract_simc_data_from_tar(tar_path)
        if data["talents"]:
            return data

    trait_file = current_simc_trait_data_file()
    if trait_file:
        text = trait_file.read_text(encoding="utf-8", errors="ignore")
        spelltext_file = current_simc_spelltext_data_file()
        spelltext_text = spelltext_file.read_text(encoding="utf-8", errors="ignore") if spelltext_file else ""
        return extract_simc_data_from_trait_text(
            text,
            str(trait_file),
            spelltext_text,
            str(spelltext_file) if spelltext_file else "",
        )

    try:
        text, source = download_simc_trait_data_text()
    except Exception:
        text, source = "", ""
    if text:
        try:
            spelltext_text, spelltext_source = download_simc_spelltext_data_text()
        except Exception:
            spelltext_text, spelltext_source = "", ""
        return extract_simc_data_from_trait_text(text, source, spelltext_text, spelltext_source)

    return {
        "talents": [],
        "presets": [],
        "spellDetails": [],
        "source": str(tar_path or trait_file or ""),
        "spellTextSource": "",
        "dependencies": 0,
        "traitEdgeSource": "",
        "build": "",
    }


PRESERVED_PROFILE_SIMC_PAYLOAD_KEYS = (
    "simcJson",
    "simcGearJson",
    "simulationcraftJson",
    "simcOutput",
    "simcGear",
    "simcStatCheckedAt",
    "simcStatSource",
    "simcStatErrors",
    "simcStatExitCode",
    "simcStatDurationMs",
    "simcStatCommand",
    "simcStatVersion",
)


def existing_profile_preset_payloads(conn):
    rows = conn.execute(
        "SELECT id, profile, payload_json FROM websim_profile_presets"
    ).fetchall()
    presets = {}
    for preset_id, profile, payload_json in rows:
        payload = safe_json_loads(payload_json, {})
        if not isinstance(payload, dict):
            payload = {}
        presets[str(preset_id)] = {
            "profile": profile or "",
            "payload": payload,
        }
    return presets


def preserve_profile_simc_payload(preset, payload, existing_presets):
    existing = existing_presets.get(str(preset.get("id") or ""))
    if not existing:
        return payload
    if (existing.get("profile") or "") != (preset.get("profile") or ""):
        return payload
    existing_payload = existing.get("payload") or {}
    for key in PRESERVED_PROFILE_SIMC_PAYLOAD_KEYS:
        if key in payload:
            continue
        if key in existing_payload:
            payload[key] = existing_payload[key]
    return payload


def sync_simc_generated_data(conn):
    now = utc_now()
    data = extract_simc_generated_data()
    existing_presets = existing_profile_preset_payloads(conn) if data["source"] else {}
    if data["source"]:
        conn.execute("DELETE FROM websim_talents")
        conn.execute("DELETE FROM websim_profile_presets")
    for talent in data["talents"]:
        payload = dict(talent.get("payload") or talent)
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
        payload = preserve_profile_simc_payload(preset, payload, existing_presets)
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
    for detail in data.get("spellDetails", []):
        spell_id = int(detail.get("spellId") or 0)
        if spell_id <= 0:
            continue
        icon_url = detail.get("iconUrl", "")
        payload = {
            "source": detail.get("source", "simulationcraft"),
            "spellId": spell_id,
            "rank": detail.get("rank", ""),
            "tooltip": detail.get("tooltip", ""),
            "spellTextSource": data.get("spellTextSource", ""),
            "spellLocalizationSource": data.get("spellLocalizationSource", ""),
        }
        conn.execute(
            """
            INSERT INTO websim_spell_details (
                id, spell_id, name, description, icon_url, locale, payload_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=CASE
                    WHEN websim_spell_details.name = ''
                      OR websim_spell_details.payload_json LIKE '%simulationcraft%'
                    THEN excluded.name
                    ELSE websim_spell_details.name
                END,
                description=CASE
                    WHEN websim_spell_details.description = ''
                      OR websim_spell_details.payload_json LIKE '%simulationcraft%'
                    THEN excluded.description
                    ELSE websim_spell_details.description
                END,
                icon_url=CASE
                    WHEN websim_spell_details.icon_url = ''
                      OR websim_spell_details.payload_json LIKE '%simulationcraft%'
                    THEN excluded.icon_url
                    ELSE websim_spell_details.icon_url
                END,
                locale=CASE
                    WHEN websim_spell_details.payload_json LIKE '%simulationcraft%'
                    THEN excluded.locale
                    ELSE websim_spell_details.locale
                END,
                payload_json=CASE
                    WHEN websim_spell_details.description = ''
                      OR websim_spell_details.payload_json LIKE '%simulationcraft%'
                    THEN excluded.payload_json
                    ELSE websim_spell_details.payload_json
                END,
                updated_at=CASE
                    WHEN websim_spell_details.description = ''
                      OR websim_spell_details.payload_json LIKE '%simulationcraft%'
                    THEN excluded.updated_at
                    ELSE websim_spell_details.updated_at
                END
            """,
            (
                str(spell_id),
                spell_id,
                detail.get("name", ""),
                detail.get("description", ""),
                icon_url,
                detail.get("locale", "en_US"),
                json.dumps(payload, ensure_ascii=False),
                now,
            ),
        )
        if icon_url:
            upsert_websim_asset(
                conn,
                game_asset_from_icon_url(
                    "spell",
                    spell_id,
                    "websim-spell-details",
                    icon_url,
                    source=detail.get("source", "simulationcraft"),
                    status="partial" if normalize_game_asset_source(detail.get("source")) != "blizzard" else "verified",
                    semantic_tags=["game", "spell", "talent"],
                    usage=["talent_simulator", "websim_spell_details"],
                    fallback_text=fallback_text_for(detail.get("name") or f"Spell {spell_id}"),
                ),
            )
    return {
        "talents": len(data["talents"]),
        "presets": len(data["presets"]),
        "spellDetails": len(data.get("spellDetails", [])),
        "spellIcons": int(data.get("spellIcons", 0) or 0),
        "spellLocalizations": int(data.get("spellLocalizations", 0) or 0),
        "dependencies": int(data.get("dependencies", 0) or 0),
        "build": data.get("build", ""),
        "source": data["source"],
        "spellTextSource": data.get("spellTextSource", ""),
        "spellIconSource": data.get("spellIconSource", ""),
        "spellLocalizationSource": data.get("spellLocalizationSource", ""),
        "traitEdgeSource": data.get("traitEdgeSource", ""),
    }


def websim_item_metadata_is_complete(row):
    if not row:
        return False
    return bool(str(row.get("displayName") or "").strip() and str(row.get("iconUrl") or "").strip())


def existing_websim_item_metadata(conn, item_id):
    row = conn.execute(
        "SELECT id, name, slot, quality, icon_url, payload_json FROM websim_items WHERE id = ?",
        (str(item_id),),
    ).fetchone()
    if not row:
        return None
    payload = safe_json_loads(row[5], {})
    metadata = payload.get("_metadata") if isinstance(payload, dict) else {}
    metadata_status = (metadata or {}).get("metadataStatus") or (metadata or {}).get("status") or "verified"
    item_stats = extract_item_stats_from_payload(payload)
    stat_summary = item_stat_summary_for_metadata(payload, item_stats)
    mod_capabilities = item_mod_capabilities(payload, row[2] or "")
    type_metadata = item_type_metadata_from_payload(payload)
    game_asset = normalize_game_asset(
        (metadata or {}).get("gameAsset") if isinstance(metadata, dict) else {},
        game_asset_from_icon_url(
            "item",
            row[0],
            "websim-item-metadata",
            row[4] or "",
            source=(metadata or {}).get("source") or ITEM_METADATA_SOURCE,
            status=metadata_status,
            semantic_tags=["game", "gear", "item", row[2] or ""],
            usage=["websim_gear", "builds_detail", "websim_loot"],
            fallback_text=fallback_text_for(row[1]),
        ),
    )
    return {
        "itemId": str(row[0]),
        "displayName": row[1] or f"Item {row[0]}",
        "slot": row[2] or "",
        "quality": row[3] or "",
        "iconUrl": row[4] or "",
        "gameAsset": game_asset,
        "payload": payload,
        "itemStats": item_stats,
        "statSummary": stat_summary,
        "modCapabilities": mod_capabilities,
        **type_metadata,
        "metadataStatus": metadata_status,
        "metadataSource": (metadata or {}).get("source") or ITEM_METADATA_SOURCE,
        "metadataLocale": (metadata or {}).get("locale") or DEFAULT_LOCALE,
        "englishName": (metadata or {}).get("englishName") or "",
        **built_in_embellishment_fields_from_payload(payload),
    }


def preset_item_refs(conn):
    rows = conn.execute(
        """
        SELECT id, class_key, spec_key, name, profile
        FROM websim_profile_presets
        ORDER BY class_key, spec_key, name
        """
    ).fetchall()
    refs = {}
    for row in rows:
        preset = {"id": row[0], "classKey": row[1], "specKey": row[2], "name": row[3], "profile": row[4]}
        for item in preset_gear_items(preset):
            item_id = str(item.get("itemId") or item.get("id") or "").strip()
            if not item_id:
                continue
            refs.setdefault(item_id, {"itemId": item_id, "aliases": set(), "slot": item.get("slot") or ""})
            refs[item_id]["aliases"].update(item_alias_candidates(item.get("displayName"), item.get("name")))
            if not refs[item_id].get("slot") and item.get("slot"):
                refs[item_id]["slot"] = item.get("slot")
    return list(refs.values())


def load_build_gear_item_refs():
    module_path = PROJECT_DIR / "server" / "builds" / "home-payload.js"
    script = r"""
const mod = require(process.argv[1])
const refs = []
const home = mod.buildSpecializationHomePayload()
for (const spec of home.specializations || []) {
  const detail = mod.getSpecializationDetail(spec.id)
  const rows = (((detail || {}).details || {}).gear || {}).gear || []
  rows.forEach((row, index) => {
    if (!row || typeof row !== 'object') return
    refs.push({
      specId: spec.id || '',
      specTitle: spec.title || '',
      slot: row.slot || '',
      name: row.name || '',
      displayName: row.displayName || '',
      englishName: row.englishName || '',
      source: row.source || '',
      itemId: row.itemId || row.item_id || row.id || '',
      isReference: Boolean(row.isReference || row.metadataStatus === 'source_reference'),
      index
    })
  })
}
console.log(JSON.stringify(refs))
"""
    completed = subprocess.run(
        ["node", "-e", script, str(module_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=PROJECT_DIR,
        check=False,
        timeout=int_env("WOW_WEBSIM_BUILD_GEAR_LOAD_TIMEOUT_SECONDS", 20),
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "build gear payload load failed").strip())
    payload = json.loads(completed.stdout or "[]")
    return payload if isinstance(payload, list) else []


def merge_item_metadata_counts(*values):
    merged = {"items": 0, "aliases": 0, "skipped": 0, "searched": 0, "resolved": 0, "references": 0, "errors": []}
    for value in values:
        if not isinstance(value, dict):
            continue
        for key in ("items", "aliases", "skipped", "searched", "resolved", "references"):
            merged[key] += int(value.get(key) or 0)
        merged["errors"].extend(value.get("errors") or [])
    return merged


def sync_blizzard_build_gear_item_metadata(conn, token, region=DEFAULT_REGION, locale=DEFAULT_LOCALE):
    limit = int_env("WOW_WEBSIM_SYNC_BUILD_ITEM_LIMIT", 200)
    counts = {"items": 0, "aliases": 0, "skipped": 0, "searched": 0, "resolved": 0, "references": 0, "errors": []}
    try:
        refs = load_build_gear_item_refs()
    except Exception as error:
        counts["errors"].append(f"build gear refs: {error}")
        return counts

    seen = set()
    for ref in refs:
        if counts["searched"] >= limit:
            break
        if not isinstance(ref, dict):
            continue
        name = str(ref.get("name") or ref.get("englishName") or ref.get("displayName") or "").strip()
        if not name:
            continue
        if ref.get("isReference"):
            counts["references"] += 1
            continue
        for item_name in split_item_name_parts(name):
            if counts["searched"] >= limit:
                break
            aliases = item_alias_candidates(item_name, ref.get("displayName"), ref.get("englishName"))
            alias_key = normalized_item_alias(item_name)
            if not alias_key or alias_key in seen:
                continue
            seen.add(alias_key)

            existing = None
            for alias in aliases:
                existing = websim_item_metadata_by_aliases(conn, [alias]).get(normalized_item_alias(alias))
                if existing:
                    break
            if existing and websim_item_metadata_is_complete(existing):
                save_item_aliases(
                    conn,
                    existing.get("itemId"),
                    aliases,
                    existing.get("displayName") or item_name,
                    existing.get("iconUrl") or "",
                    target_locale=existing.get("metadataLocale") or locale,
                )
                counts["aliases"] += len(item_alias_candidates(*aliases))
                counts["skipped"] += 1
                continue

            item_id = str(ref.get("itemId") or "").strip() if exact_item_name_key(item_name) == exact_item_name_key(name) else ""
            try:
                if not item_id:
                    counts["searched"] += 1
                    item_id = search_blizzard_item_id_by_english_name(token, item_name, region)
                if not item_id:
                    counts["errors"].append(f"{item_name}: exact item search did not return a match")
                    continue
                counts["resolved"] += 1
                item_metadata = fetch_blizzard_item_metadata(
                    token,
                    item_id,
                    region,
                    locale,
                    fallback_name=item_name,
                    fallback_slot=ref.get("slot") or "",
                )
                saved = save_websim_item_metadata(
                    conn,
                    item_id,
                    item_metadata.get("payload") or {},
                    item_metadata.get("media") or {},
                    fallback_slot=item_metadata.get("fallbackSlot") or ref.get("slot") or "",
                    fallback_name=item_metadata.get("fallbackName") or item_name,
                    english_payload=item_metadata.get("englishPayload") or {"name": item_name},
                    locale=item_metadata.get("locale") or locale,
                )
                if saved:
                    save_item_aliases(
                        conn,
                        item_id,
                        aliases,
                        saved.get("displayName") or item_name,
                        saved.get("iconUrl") or "",
                        target_locale=saved.get("metadataLocale") or locale,
                    )
                    counts["aliases"] += len(item_alias_candidates(*aliases))
                    counts["items"] += 1
            except Exception as error:
                counts["errors"].append(f"{item_name}: {error}")
    return counts


def sync_blizzard_preset_item_metadata(conn, token, region=DEFAULT_REGION, locale=DEFAULT_LOCALE):
    limit = int_env("WOW_WEBSIM_SYNC_PRESET_ITEM_LIMIT", 500)
    counts = {"items": 0, "aliases": 0, "skipped": 0, "errors": []}
    for ref in preset_item_refs(conn)[:limit]:
        item_id = ref["itemId"]
        aliases = list(ref.get("aliases") or [])
        existing = existing_websim_item_metadata(conn, item_id)
        if websim_item_metadata_is_complete(existing):
            save_item_aliases(
                conn,
                item_id,
                aliases,
                existing.get("displayName") or f"Item {item_id}",
                existing.get("iconUrl") or "",
                target_locale=existing.get("metadataLocale") or locale,
            )
            counts["aliases"] += len(item_alias_candidates(*aliases))
            counts["skipped"] += 1
            continue
        try:
            item_metadata = fetch_blizzard_item_metadata(
                token,
                item_id,
                region,
                locale,
                fallback_name=aliases[0] if aliases else "",
                fallback_slot=ref.get("slot") or "",
            )
        except Exception as error:
            counts["errors"].append(f"{item_id}: {error}")
            continue
        saved = save_websim_item_metadata(
            conn,
            item_id,
            item_metadata.get("payload") or {},
            item_metadata.get("media") or {},
            fallback_slot=item_metadata.get("fallbackSlot") or ref.get("slot") or "",
            fallback_name=item_metadata.get("fallbackName") or "",
            english_payload=item_metadata.get("englishPayload") or {},
            locale=item_metadata.get("locale") or locale,
        )
        if saved:
            save_item_aliases(
                conn,
                item_id,
                aliases,
                saved.get("displayName") or f"Item {item_id}",
                saved.get("iconUrl") or "",
                target_locale=saved.get("metadataLocale") or locale,
            )
            counts["aliases"] += len(item_alias_candidates(*aliases))
            counts["items"] += 1
    return counts


def observed_item_refs(conn, limit=None):
    ensure_websim_tables(conn)
    rows = conn.execute(
        """
        WITH refs AS (
            SELECT item_id
            FROM websim_gear_sources
            WHERE source_type = 'observed_profile'
            UNION
            SELECT item_id
            FROM websim_gear_variants
            WHERE source_type = 'observed_profile'
        )
        SELECT refs.item_id, websim_items.name, websim_items.slot
        FROM refs
        LEFT JOIN websim_items ON websim_items.id = refs.item_id
        WHERE refs.item_id IS NOT NULL AND TRIM(refs.item_id) <> ''
        ORDER BY refs.item_id
        """
    ).fetchall()
    refs = []
    seen = set()
    for item_id, name, slot in rows:
        item_id = normalize_option_value(item_id)
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        refs.append({"itemId": item_id, "name": name or "", "slot": normalize_slot(slot or "")})
        if limit is not None and len(refs) >= limit:
            break
    return refs


def sync_blizzard_observed_item_metadata(conn, token, region=DEFAULT_REGION, locale=DEFAULT_LOCALE):
    limit = int_env("WOW_WEBSIM_SYNC_OBSERVED_ITEM_LIMIT", 120)
    counts = {"items": 0, "aliases": 0, "skipped": 0, "searched": 0, "resolved": 0, "references": 0, "errors": []}
    for ref in observed_item_refs(conn, limit):
        item_id = ref["itemId"]
        existing = existing_websim_item_metadata(conn, item_id)
        if not item_metadata_needs_fetch(existing):
            aliases = item_alias_candidates(ref.get("name"), (existing or {}).get("displayName"), (existing or {}).get("englishName"))
            if aliases:
                save_item_aliases(
                    conn,
                    item_id,
                    aliases,
                    (existing or {}).get("displayName") or ref.get("name") or f"Item {item_id}",
                    (existing or {}).get("iconUrl") or "",
                    target_locale=(existing or {}).get("metadataLocale") or locale,
                )
                counts["aliases"] += len(item_alias_candidates(*aliases))
            counts["skipped"] += 1
            continue
        try:
            item_metadata = fetch_blizzard_item_metadata(
                token,
                item_id,
                region,
                locale,
                fallback_name=ref.get("name") or "",
                fallback_slot=ref.get("slot") or "",
            )
        except Exception as error:
            counts["errors"].append(f"{item_id}: {error}")
            continue
        saved = save_websim_item_metadata(
            conn,
            item_id,
            item_metadata.get("payload") or {},
            item_metadata.get("media") or {},
            fallback_slot=item_metadata.get("fallbackSlot") or ref.get("slot") or "",
            fallback_name=item_metadata.get("fallbackName") or ref.get("name") or "",
            english_payload=item_metadata.get("englishPayload") or {},
            locale=item_metadata.get("locale") or locale,
        )
        if saved:
            aliases = item_alias_candidates(ref.get("name"), saved.get("displayName"), saved.get("englishName"))
            if aliases:
                save_item_aliases(
                    conn,
                    item_id,
                    aliases,
                    saved.get("displayName") or ref.get("name") or f"Item {item_id}",
                    saved.get("iconUrl") or "",
                    target_locale=saved.get("metadataLocale") or locale,
                )
                counts["aliases"] += len(item_alias_candidates(*aliases))
            counts["items"] += 1
    return counts


def gear_mod_seed():
    raw = os.environ.get("WOW_WEBSIM_GEAR_MOD_SEED", "").strip()
    if raw:
        parsed = safe_json_loads(raw, [])
        if isinstance(parsed, list):
            return [dict(option) for option in parsed if isinstance(option, dict)]
    default_options = DEFAULT_GEAR_MOD_SEED
    if os.environ.get("WOW_WEBSIM_DEFAULT_RANK_TWO_GEM_SEED", "1").strip().lower() in {"0", "false", "no", "off"}:
        default_options = [option for option in DEFAULT_GEAR_MOD_SEED if str(option.get("type") or "").lower() != "socket"]
    return [dict(option) for option in default_options]


def upsert_gear_source(conn, source):
    conn.execute(
        """
        INSERT INTO websim_gear_sources
        (id, item_id, source_type, source_label, instance_id, encounter_id,
         difficulty_key, season_revision, payload_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            item_id=excluded.item_id,
            source_type=excluded.source_type,
            source_label=excluded.source_label,
            instance_id=excluded.instance_id,
            encounter_id=excluded.encounter_id,
            difficulty_key=excluded.difficulty_key,
            season_revision=excluded.season_revision,
            payload_json=excluded.payload_json,
            updated_at=excluded.updated_at
        """,
        (
            source["id"],
            str(source["itemId"]),
            source.get("sourceType") or "dungeon",
            source.get("sourceLabel") or "Gear catalog",
            source.get("instanceId") or "",
            source.get("encounterId") or "",
            source.get("difficultyKey") or "",
            source.get("seasonRevision") or "",
            json.dumps(source.get("payload") or {}, ensure_ascii=False),
            utc_now(),
        ),
    )


def upsert_gear_variant(conn, variant):
    conn.execute(
        """
        INSERT INTO websim_gear_variants
        (id, item_id, slot, variant_key, label, source_type, difficulty_key,
         item_level, simc_options_json, status, blockers_json, payload_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            item_id=excluded.item_id,
            slot=excluded.slot,
            variant_key=excluded.variant_key,
            label=excluded.label,
            source_type=excluded.source_type,
            difficulty_key=excluded.difficulty_key,
            item_level=excluded.item_level,
            simc_options_json=excluded.simc_options_json,
            status=excluded.status,
            blockers_json=excluded.blockers_json,
            payload_json=excluded.payload_json,
            updated_at=excluded.updated_at
        """,
        (
            variant["id"],
            str(variant["itemId"]),
            normalize_slot(variant.get("slot")) or "",
            variant.get("variantKey") or variant.get("key") or "default",
            variant.get("label") or "Default",
            variant.get("sourceType") or "dungeon",
            variant.get("difficultyKey") or "",
            int(variant.get("itemLevel") or variant.get("ilevel") or 0),
            json.dumps(variant.get("simcOptions") or {}, ensure_ascii=False),
            variant.get("status") or "blocked",
            json.dumps(variant.get("blockers") or [], ensure_ascii=False),
            json.dumps(variant.get("payload") or {}, ensure_ascii=False),
            utc_now(),
        ),
    )


def delete_pending_gear_variant_placeholders(conn, item_ids, source_type):
    normalized_ids = []
    seen = set()
    for item_id in item_ids or []:
        normalized = str(item_id or "").strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            normalized_ids.append(normalized)
    source_type = raw_source_type(source_type or "").lower()
    if not normalized_ids or not source_type:
        return 0
    deleted = 0
    for index in range(0, len(normalized_ids), 500):
        chunk = normalized_ids[index : index + 500]
        placeholders = ",".join("?" for _ in chunk)
        result = conn.execute(
            f"""
            DELETE FROM websim_gear_variants
            WHERE source_type = ?
              AND item_id IN ({placeholders})
              AND item_level <= 0
              AND (
                    variant_key IN ('needs-variant', 'needs_variant')
                 OR difficulty_key IN ('needs-variant', 'needs_variant')
              )
            """,
            [source_type, *chunk],
        )
        if result.rowcount and result.rowcount > 0:
            deleted += result.rowcount
    return deleted


def official_item_level_probe_simc_slot(slot):
    slot = normalize_slot(slot)
    return {
        "shoulder": "shoulders",
        "wrist": "wrists",
    }.get(slot, slot)


def official_loot_supports_void_upgrade(item):
    item = item if isinstance(item, dict) else {}
    slot = normalize_slot(item.get("slot"))
    if str(item.get("instanceId") or "") == "1305":
        return True
    return slot in {"main_hand", "trinket1", "trinket2"}


def official_item_level_tracks_for_item(item):
    tracks = [dict(track) for track in OFFICIAL_ITEM_LEVEL_TRACKS]
    if official_loot_supports_void_upgrade(item):
        tracks.append(dict(OFFICIAL_VOID_UPGRADE_TRACK))
    return tracks


def tier_set_item_has_void_upgrade_evidence(conn, item_id):
    season = get_active_season_payload(conn)
    active_revision_values = {
        str((season or {}).get(key) or "").strip()
        for key in ("seasonRevision", "revision")
        if str((season or {}).get(key) or "").strip()
    }
    rows = conn.execute(
        """
        SELECT status, payload_json
        FROM websim_gear_variants
        WHERE item_id = ?
          AND item_level = 298
          AND source_type IN ('observed_profile', 'tier_set')
          AND id NOT LIKE 'set-itemlevel-tier_set-%'
        """,
        (str(item_id or ""),),
    ).fetchall()
    for status, payload_json in rows:
        if str(status or "").strip().lower() != "verified":
            continue
        payload = safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        stats = payload.get("itemStats") or payload.get("stats") or []
        if not (stats or payload.get("statSummary")):
            continue
        evidence_revision = str(payload.get("seasonRevision") or payload.get("revision") or "").strip()
        if active_revision_values and evidence_revision not in active_revision_values:
            continue
        return True
    return False


def official_item_level_tracks_for_tier_set_item(conn, item_id):
    tracks = [dict(track) for track in OFFICIAL_ITEM_LEVEL_TRACKS]
    if tier_set_item_has_void_upgrade_evidence(conn, item_id):
        tracks.append(dict(OFFICIAL_VOID_UPGRADE_TRACK))
    return tracks


def crafted_public_difficulty_key(difficulty_key):
    key = normalized_difficulty_key(difficulty_key)
    return CRAFTED_PUBLIC_DIFFICULTY_KEYS.get(key, key)


def crafted_track_from_input(value):
    if isinstance(value, dict):
        key = normalized_difficulty_key(
            value.get("difficultyKey") or value.get("key") or value.get("trackKey") or ""
        )
        item_level = positive_int_value(value.get("itemLevel") or value.get("ilevel"))
        if not key:
            return None
        base = dict(CRAFTED_ITEM_LEVEL_TRACKS.get(key) or {})
        if item_level:
            base["itemLevel"] = item_level
        if not base.get("itemLevel"):
            return None
        base["difficultyKey"] = key
        base["label"] = str(value.get("label") or base.get("label") or f"{localized_difficulty_label(key)} {base['itemLevel']}").strip()
        base["trackEvidence"] = value.get("trackEvidence") or value.get("evidence") or []
        return base
    key = normalized_difficulty_key(value)
    if key in CRAFTED_ITEM_LEVEL_TRACKS:
        return dict(CRAFTED_ITEM_LEVEL_TRACKS[key])
    return None


def crafted_item_supports_void_upgrade(item):
    if not isinstance(item, dict):
        return False
    if not item.get("supportsVoidUpgrade"):
        return False
    return normalize_slot(item.get("slot")) in {"main_hand", "off_hand"}


def crafted_item_level_tracks_for_item(item):
    raw_tracks = item.get("allowedTracks") or item.get("tracks") or ["crafted_myth"]
    if isinstance(raw_tracks, str):
        raw_tracks = [raw_tracks]
    tracks = []
    seen = set()
    for raw_track in raw_tracks or []:
        track = crafted_track_from_input(raw_track)
        if not track:
            continue
        key = normalized_difficulty_key(track.get("difficultyKey"))
        if crafted_public_difficulty_key(key) == "void_upgrade" and not crafted_item_supports_void_upgrade(item):
            continue
        if key in seen:
            continue
        seen.add(key)
        tracks.append(track)
    return tracks


def crafted_stat_option_from_input(value):
    if isinstance(value, dict):
        option_value = normalize_option_value(value.get("value") or value.get("crafted_stats") or value.get("craftedStats"))
        if not option_value:
            simc_options = value.get("simcOptions") if isinstance(value.get("simcOptions"), dict) else {}
            option_value = normalize_option_value(simc_options.get("crafted_stats"))
        if not option_value:
            return None
        key = slugify(value.get("key") or value.get("id") or value.get("label") or option_value, f"crafted-{stable_digest(option_value)}")
        label = str(value.get("label") or value.get("name") or option_value).strip()
        return {
            "key": key,
            "label": label,
            "value": option_value,
            "status": str(value.get("status") or "verified").strip() or "verified",
            "payload": value.get("payload") if isinstance(value.get("payload"), dict) else {},
        }
    option_value = normalize_option_value(value)
    if not option_value:
        return None
    return {
        "key": f"crafted-{stable_digest(option_value)}",
        "label": option_value,
        "value": option_value,
        "status": "verified",
        "payload": {},
    }


def crafted_stat_options_for_item(item):
    raw_options = item.get("allowedCraftedStats") or item.get("craftedStatOptions") or item.get("crafted_stats_options") or []
    if isinstance(raw_options, (str, dict)):
        raw_options = [raw_options]
    options = []
    seen = set()
    for raw_option in raw_options or []:
        option = crafted_stat_option_from_input(raw_option)
        if not option:
            continue
        key = option["key"]
        if key in seen:
            continue
        seen.add(key)
        options.append(option)
    return options


def simc_profile_with_crafted_item_probe(conn, item, item_level, stat_option, track=None):
    candidates = item_level_probe_profile_candidates(item)
    if not candidates:
        return "", "", "", ""
    rows = conn.execute(
        """
        SELECT class_key, spec_key, name, profile
        FROM websim_profile_presets
        WHERE profile <> ''
        ORDER BY class_key, spec_key, id
        """
    ).fetchall()
    by_pair = {}
    for class_key, spec_key, name, profile in rows:
        by_pair.setdefault((str(class_key or ""), str(spec_key or "")), (str(name or ""), str(profile or "")))
    simc_slot = official_item_level_probe_simc_slot(item.get("slot"))
    if not simc_slot:
        return "", "", "", ""
    safe_name = simc_safe_item_name(item.get("name") or f"item_{item.get('itemId')}", item.get("itemId") or "")
    options = [
        f"id={item.get('itemId')}",
        f"ilevel={int(item_level or 0)}",
    ]
    bonus_id = normalize_option_value(item.get("bonus_id") or item.get("bonusId") or (track or {}).get("bonus_id") or (track or {}).get("bonusId"))
    if bonus_id:
        options.append(f"bonus_id={bonus_id}")
    crafted_stats = normalize_option_value((stat_option or {}).get("value") or (stat_option or {}).get("crafted_stats"))
    if crafted_stats:
        options.append(f"crafted_stats={crafted_stats}")
    item_line = f"{simc_slot}={safe_name},{','.join(options)}"
    remove_slots = {simc_slot}
    if simc_slot == "main_hand" and item_level_probe_main_hand_removes_offhand(item):
        remove_slots.add("off_hand")
    for class_key, spec_key in candidates:
        preset = by_pair.get((class_key, spec_key))
        if not preset:
            continue
        _preset_name, profile = preset
        lines = []
        probe_override_keys = {"iterations", "max_time", "target_error", "calculate_scale_factors", "json"}
        for line in str(profile or "").splitlines():
            stripped = line.strip()
            if not stripped or "=" not in stripped:
                lines.append(line)
                continue
            head = stripped.split("=", 1)[0].strip()
            if head in probe_override_keys:
                continue
            if head in remove_slots:
                continue
            lines.append(line)
        lines.extend([
            "iterations=1",
            "max_time=1",
            "target_error=0.5",
            "calculate_scale_factors=0",
        ])
        lines.append(item_line)
        return "\n".join(lines).strip() + "\n", class_key, spec_key, item_line
    return "", "", "", ""


def resolve_crafted_item_level_stat_payload(conn, item, item_level, stat_option, track=None):
    profile, class_key, spec_key, item_line = simc_profile_with_crafted_item_probe(conn, item, item_level, stat_option, track)
    if not profile:
        return {"error": "no compatible SimC profile preset found"}
    result = run_websim_profile_preset_simc_json(profile)
    if not result.get("ok"):
        return {
            "error": str(result.get("error") or "SimC crafted item probe failed")[:1000],
            "simcProfile": item_line,
            "classKey": class_key,
            "specKey": spec_key,
        }
    gear_by_slot = simc_json_gear_stats_by_slot(result.get("payload") or {})
    stat_payload = simc_observed_variant_stat_payload(
        {
            "itemId": item.get("itemId"),
            "slot": item.get("slot"),
            "ilevel": item_level,
        },
        gear_by_slot,
    )
    if not stat_payload:
        return {
            "error": "SimC JSON did not include target item stats",
            "simcProfile": item_line,
            "classKey": class_key,
            "specKey": spec_key,
        }
    stat_payload.update(
        {
            "simcProfile": item_line,
            "probeClassKey": class_key,
            "probeSpecKey": spec_key,
            "simcCheckedAt": result.get("checkedAt") or utc_now(),
            "simcDurationMs": result.get("durationMs", 0),
        }
    )
    return stat_payload


def item_level_probe_profile_candidates(item):
    item = item if isinstance(item, dict) else {}
    slot = normalize_slot(item.get("slot"))
    metadata = item.get("metadataPayload") if isinstance(item.get("metadataPayload"), dict) else {}
    type_metadata = item_type_metadata_from_payload(metadata)
    armor_type = str(item.get("armorType") or type_metadata.get("armorType") or "").strip().lower()
    weapon_type = str(item.get("weaponType") or type_metadata.get("weaponType") or "").strip().lower()
    stats = extract_item_stats_from_payload(metadata)
    stat_keys = {str(stat.get("key") or "").strip().lower() for stat in stats if isinstance(stat, dict)}
    candidates = []

    def add(class_key, spec_key):
        pair = (class_key, spec_key)
        if pair not in candidates:
            candidates.append(pair)

    if armor_type == "cloth":
        add("mage", "frost")
    elif armor_type == "leather":
        add("druid", "balance")
        add("druid", "feral")
        add("rogue", "subtlety")
    elif armor_type == "mail":
        add("shaman", "elemental")
        add("hunter", "beast_mastery")
    elif armor_type == "plate":
        add("warrior", "arms")
        add("paladin", "retribution")

    if slot in {"trinket1", "trinket2", "finger1", "finger2", "neck"}:
        if stat_keys & {"intellect", "int", "intagi", "agiint", "strint", "stragiint"}:
            add("mage", "frost")
            add("shaman", "elemental")
        if stat_keys & {"agility", "agi", "stragi", "stragiint", "intagi", "agiint"}:
            add("rogue", "subtlety")
            add("hunter", "beast_mastery")
        if stat_keys & {"strength", "str", "stragi", "strint", "stragiint"}:
            add("warrior", "arms")
        add("mage", "frost")

    if slot == "main_hand":
        if "warglaive" in weapon_type:
            add("demonhunter", "havoc")
        elif "staff" in weapon_type:
            if stat_keys & {"agility", "agi", "agiint", "intagi"}:
                add("druid", "feral")
            add("druid", "balance")
            add("mage", "frost")
        elif "dagger" in weapon_type:
            if stat_keys & {"intellect", "int"}:
                add("mage", "frost")
                add("shaman", "elemental")
            add("rogue", "subtlety")
        elif "axe" in weapon_type or "sword" in weapon_type or "mace" in weapon_type:
            if stat_keys & {"strength", "str"}:
                add("warrior", "arms")
                add("paladin", "retribution")
            if stat_keys & {"agility", "agi"}:
                add("rogue", "subtlety")
            if stat_keys & {"intellect", "int"}:
                add("shaman", "elemental")
        add("warrior", "arms")
        add("mage", "frost")
    elif slot == "off_hand":
        if "shield" in weapon_type:
            add("paladin", "protection")
            add("shaman", "elemental")
        elif "held" in weapon_type:
            add("mage", "frost")
            add("shaman", "elemental")
        add("mage", "frost")

    for fallback in [("mage", "frost"), ("shaman", "elemental"), ("warrior", "arms"), ("druid", "balance")]:
        add(*fallback)
    return candidates


def simc_safe_item_name(value, item_id=""):
    fallback = f"item_{normalize_option_value(item_id)}" if normalize_option_value(item_id) else "item"
    text = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")
    text = re.sub(r"_+", "_", text)
    return text or fallback


def item_level_probe_main_hand_removes_offhand(item):
    item = item if isinstance(item, dict) else {}
    metadata = item.get("metadataPayload") if isinstance(item.get("metadataPayload"), dict) else {}
    type_metadata = item_type_metadata_from_payload(metadata)
    weapon_type = str(item.get("weaponType") or type_metadata.get("weaponType") or "").strip().lower()
    if not weapon_type:
        return True
    return any(
        marker in weapon_type
        for marker in ("two-handed", "staff", "polearm", "bow", "gun", "crossbow", "wand")
    )


def simc_profile_with_item_level_probe(conn, item, item_level):
    candidates = item_level_probe_profile_candidates(item)
    if not candidates:
        return "", "", "", ""
    rows = conn.execute(
        """
        SELECT class_key, spec_key, name, profile
        FROM websim_profile_presets
        WHERE profile <> ''
        ORDER BY class_key, spec_key, id
        """
    ).fetchall()
    by_pair = {}
    for class_key, spec_key, name, profile in rows:
        by_pair.setdefault((str(class_key or ""), str(spec_key or "")), (str(name or ""), str(profile or "")))
    simc_slot = official_item_level_probe_simc_slot(item.get("slot"))
    if not simc_slot:
        return "", "", "", ""
    safe_name = simc_safe_item_name(item.get("name") or f"item_{item.get('itemId')}", item.get("itemId") or "")
    item_line = f"{simc_slot}={safe_name},id={item.get('itemId')},ilevel={int(item_level or 0)}"
    remove_slots = {simc_slot}
    if simc_slot == "main_hand" and item_level_probe_main_hand_removes_offhand(item):
        remove_slots.add("off_hand")
    for class_key, spec_key in candidates:
        preset = by_pair.get((class_key, spec_key))
        if not preset:
            continue
        _preset_name, profile = preset
        lines = []
        probe_override_keys = {"iterations", "max_time", "target_error", "calculate_scale_factors", "json"}
        for line in str(profile or "").splitlines():
            stripped = line.strip()
            if not stripped or "=" not in stripped:
                lines.append(line)
                continue
            head = stripped.split("=", 1)[0].strip()
            if head in probe_override_keys:
                continue
            if head in remove_slots:
                continue
            lines.append(line)
        lines.extend([
            "iterations=1",
            "max_time=1",
            "target_error=0.5",
            "calculate_scale_factors=0",
        ])
        lines.append(item_line)
        return "\n".join(lines).strip() + "\n", class_key, spec_key, item_line
    return "", "", "", ""


def resolve_item_level_probe_stat_payload(conn, item, item_level, track=None):
    profile, class_key, spec_key, item_line = simc_profile_with_item_level_probe(conn, item, item_level)
    if not profile:
        return {"error": "no compatible SimC profile preset found"}
    result = run_websim_profile_preset_simc_json(profile)
    if not result.get("ok"):
        return {
            "error": str(result.get("error") or "SimC item-level probe failed")[:1000],
            "simcProfile": item_line,
            "classKey": class_key,
            "specKey": spec_key,
        }
    gear_by_slot = simc_json_gear_stats_by_slot(result.get("payload") or {})
    stat_payload = simc_observed_variant_stat_payload(
        {
            "itemId": item.get("itemId"),
            "slot": item.get("slot"),
            "ilevel": item_level,
        },
        gear_by_slot,
    )
    if not stat_payload:
        return {
            "error": "SimC JSON did not include target item stats",
            "simcProfile": item_line,
            "classKey": class_key,
            "specKey": spec_key,
        }
    stat_payload.update(
        {
            "simcProfile": item_line,
            "probeClassKey": class_key,
            "probeSpecKey": spec_key,
            "simcCheckedAt": result.get("checkedAt") or utc_now(),
            "simcDurationMs": result.get("durationMs", 0),
        }
    )
    return stat_payload


def backfill_official_item_level_variants_for_instance(conn, instance_id, source_type="raid", stat_resolver=None):
    ensure_websim_tables(conn)
    instance_id = str(instance_id or "").strip()
    source_type = raw_source_type(source_type or "raid").lower()
    if not instance_id:
        return {"items": 0, "tracks": 0, "verifiedVariants": 0, "partialVariants": 0, "errors": ["missing instance id"]}
    if stat_resolver is None:
        stat_resolver = lambda item, item_level, track: resolve_item_level_probe_stat_payload(conn, item, item_level, track)

    conn.execute(
        "DELETE FROM websim_gear_variants WHERE id LIKE ?",
        (f"loot-itemlevel-{source_type}-{instance_id}-%",),
    )
    rows = conn.execute(
        """
        SELECT s.item_id, s.source_label, s.encounter_id, s.season_revision, s.payload_json,
               l.name, l.slot, l.quality, wi.payload_json
        FROM websim_gear_sources s
        JOIN websim_loot l
          ON l.item_id = s.item_id
         AND l.instance_id = s.instance_id
         AND COALESCE(l.encounter_id, '') = COALESCE(s.encounter_id, '')
        LEFT JOIN websim_items wi ON wi.id = s.item_id
        WHERE s.instance_id = ?
          AND s.source_type = ?
        ORDER BY s.encounter_id, l.name, s.item_id
        """,
        (instance_id, source_type),
    ).fetchall()

    counts = {"items": 0, "tracks": 0, "verifiedVariants": 0, "partialVariants": 0, "errors": []}
    processed_item_ids = []
    for row in rows:
        metadata_payload = safe_json_loads(row[8], {})
        metadata_payload = metadata_payload if isinstance(metadata_payload, dict) else {}
        type_metadata = item_type_metadata_from_payload(metadata_payload)
        slot = normalize_slot(row[6]) or item_slot_from_payload(metadata_payload)
        item = {
            "itemId": str(row[0]),
            "name": str(row[5] or f"item_{row[0]}"),
            "slot": slot,
            "simcSlot": official_item_level_probe_simc_slot(slot),
            "quality": row[7],
            "sourceType": source_type,
            "sourceLabel": row[1],
            "instanceId": instance_id,
            "encounterId": row[2],
            "seasonRevision": row[3],
            "metadataPayload": metadata_payload,
            "armorType": type_metadata.get("armorType") or "",
            "weaponType": type_metadata.get("weaponType") or "",
        }
        if not slot:
            counts["errors"].append(f"{row[0]}: missing slot")
            continue
        counts["items"] += 1
        processed_item_ids.append(item["itemId"])
        source_payload = safe_json_loads(row[4], {})
        source_payload = source_payload if isinstance(source_payload, dict) else {}
        for track in official_item_level_tracks_for_item(item):
            counts["tracks"] += 1
            item_level = int(track.get("itemLevel") or 0)
            difficulty_key = str(track.get("difficultyKey") or "")
            stat_payload = stat_resolver(item, item_level, track) or {}
            stat_payload = stat_payload if isinstance(stat_payload, dict) else {}
            stats = normalize_item_stats(stat_payload.get("itemStats") or stat_payload.get("stats") or [])
            blockers = []
            status = "verified"
            if not stats:
                status = "partial"
                blockers.append(str(stat_payload.get("error") or "SimC item-level probe missing item stats")[:1000])
            payload = {
                **source_payload,
                "seasonRevision": row[3],
                "officialVariantSource": source_type,
                "derivedVariantSource": OFFICIAL_ITEM_LEVEL_PROBE_SOURCE,
                "itemLevelTrack": difficulty_key,
                "simcIlevelOnly": True,
                "statSource": "simulationcraft",
            }
            for key, value in stat_payload.items():
                if value not in (None, "", [], {}):
                    payload[key] = value
            if stats:
                payload["itemStats"] = stats
                payload["stats"] = stats
                payload["statSummary"] = stat_payload.get("statSummary") or item_stat_summary(stats)
                payload["statDisplayStatus"] = stat_payload.get("statDisplayStatus") or "verified_variant"
            variant_id = f"loot-itemlevel-{source_type}-{instance_id}-{item['itemId']}-{slot}-{difficulty_key}-{item_level}"
            upsert_gear_variant(
                conn,
                {
                    "id": variant_id,
                    "itemId": item["itemId"],
                    "slot": slot,
                    "variantKey": f"{difficulty_key}-{item_level}",
                    "label": track.get("label") or f"{difficulty_key} {item_level}",
                    "sourceType": source_type,
                    "difficultyKey": difficulty_key,
                    "itemLevel": item_level,
                    "simcOptions": {"ilevel": str(item_level)},
                    "status": status,
                    "blockers": blockers,
                    "payload": payload,
                },
            )
            if status == "verified":
                counts["verifiedVariants"] += 1
            else:
                counts["partialVariants"] += 1
                counts["errors"].append(f"{item['itemId']}:{item_level}: {blockers[0] if blockers else 'partial'}")
    removed_pending = delete_pending_gear_variant_placeholders(conn, processed_item_ids, source_type)
    if removed_pending:
        counts["removedPendingVariants"] = removed_pending
    conn.commit()
    set_sync_state(conn, "gearCatalog", build_gear_catalog_sync_state(conn, get_active_season_payload(conn)))
    return counts


def backfill_official_item_level_variants_for_tier_sets(conn, set_ids=None, stat_resolver=None):
    ensure_websim_tables(conn)
    requested_set_ids = [str(set_id or "").strip() for set_id in (set_ids or []) if str(set_id or "").strip()]
    if stat_resolver is None:
        stat_resolver = lambda item, item_level, track: resolve_item_level_probe_stat_payload(conn, item, item_level, track)

    if requested_set_ids:
        for set_id in requested_set_ids:
            conn.execute(
                "DELETE FROM websim_gear_variants WHERE id LIKE ?",
                (f"set-itemlevel-tier_set-{set_id}-%",),
            )
        placeholders = ",".join("?" for _ in requested_set_ids)
        rows = conn.execute(
            f"""
            SELECT i.set_id, i.item_id, i.name, i.slot, st.name, st.season_revision,
                   i.payload_json, s.source_label, s.payload_json, wi.payload_json
            FROM websim_item_set_items i
            JOIN websim_item_sets st
              ON st.id = i.set_id
            LEFT JOIN websim_gear_sources s
              ON s.id = 'set-' || i.set_id || '-' || i.item_id
            LEFT JOIN websim_items wi
              ON wi.id = i.item_id
            WHERE i.set_id IN ({placeholders})
            ORDER BY i.set_id, i.slot, i.item_id
            """,
            requested_set_ids,
        ).fetchall()
    else:
        conn.execute("DELETE FROM websim_gear_variants WHERE id LIKE 'set-itemlevel-tier_set-%'")
        rows = conn.execute(
            """
            SELECT i.set_id, i.item_id, i.name, i.slot, st.name, st.season_revision,
                   i.payload_json, s.source_label, s.payload_json, wi.payload_json
            FROM websim_item_set_items i
            JOIN websim_item_sets st
              ON st.id = i.set_id
            LEFT JOIN websim_gear_sources s
              ON s.id = 'set-' || i.set_id || '-' || i.item_id
            LEFT JOIN websim_items wi
              ON wi.id = i.item_id
            ORDER BY i.set_id, i.slot, i.item_id
            """
        ).fetchall()

    counts = {"items": 0, "tracks": 0, "verifiedVariants": 0, "partialVariants": 0, "errors": []}
    processed_item_ids = []
    for row in rows:
        set_id, item_id, name, raw_slot, set_name, season_revision, item_set_payload_json, source_label, source_payload_json, metadata_payload_json = row
        set_id = str(set_id or "").strip()
        item_id = str(item_id or "").strip()
        metadata_payload = safe_json_loads(metadata_payload_json, {})
        metadata_payload = metadata_payload if isinstance(metadata_payload, dict) else {}
        type_metadata = item_type_metadata_from_payload(metadata_payload)
        slot = normalize_slot(raw_slot) or item_slot_from_payload(metadata_payload)
        item = {
            "itemId": item_id,
            "name": str(name or f"item_{item_id}"),
            "slot": slot,
            "simcSlot": official_item_level_probe_simc_slot(slot),
            "quality": (
                metadata_payload.get("quality", {}).get("name")
                if isinstance(metadata_payload.get("quality"), dict)
                else str(metadata_payload.get("quality") or "")
            ),
            "sourceType": "tier_set",
            "sourceLabel": str(source_label or set_name or "套装"),
            "setId": set_id,
            "setName": str(set_name or source_label or "套装"),
            "seasonRevision": season_revision,
            "metadataPayload": metadata_payload,
            "armorType": type_metadata.get("armorType") or "",
            "weaponType": type_metadata.get("weaponType") or "",
        }
        if not slot:
            counts["errors"].append(f"{item_id}: missing slot")
            continue
        counts["items"] += 1
        processed_item_ids.append(item_id)
        source_payload = safe_json_loads(source_payload_json, {})
        source_payload = source_payload if isinstance(source_payload, dict) else {}
        item_set_payload = safe_json_loads(item_set_payload_json, {})
        item_set_payload = item_set_payload if isinstance(item_set_payload, dict) else {}
        for track in official_item_level_tracks_for_tier_set_item(conn, item_id):
            counts["tracks"] += 1
            item_level = int(track.get("itemLevel") or 0)
            difficulty_key = str(track.get("difficultyKey") or "")
            stat_payload = stat_resolver(item, item_level, track) or {}
            stat_payload = stat_payload if isinstance(stat_payload, dict) else {}
            stats = normalize_item_stats(stat_payload.get("itemStats") or stat_payload.get("stats") or [])
            blockers = []
            status = "verified"
            if not stats:
                status = "partial"
                blockers.append(str(stat_payload.get("error") or "SimC item-level probe missing item stats")[:1000])
            payload = {
                **source_payload,
                "seasonRevision": season_revision,
                "officialVariantSource": "tier_set",
                "derivedVariantSource": OFFICIAL_ITEM_LEVEL_PROBE_SOURCE,
                "itemLevelTrack": difficulty_key,
                "simcIlevelOnly": True,
                "statSource": "simulationcraft",
                "setId": set_id,
                "setName": str(set_name or source_label or item_set_payload.get("setName") or "套装"),
            }
            for key, value in stat_payload.items():
                if value not in (None, "", [], {}):
                    payload[key] = value
            if stats:
                payload["itemStats"] = stats
                payload["stats"] = stats
                payload["statSummary"] = stat_payload.get("statSummary") or item_stat_summary(stats)
                payload["statDisplayStatus"] = stat_payload.get("statDisplayStatus") or "verified_variant"
            variant_id = f"set-itemlevel-tier_set-{set_id}-{item_id}-{slot}-{difficulty_key}-{item_level}"
            upsert_gear_variant(
                conn,
                {
                    "id": variant_id,
                    "itemId": item_id,
                    "slot": slot,
                    "variantKey": f"{difficulty_key}-{item_level}",
                    "label": track.get("label") or f"{difficulty_key} {item_level}",
                    "sourceType": "tier_set",
                    "difficultyKey": difficulty_key,
                    "itemLevel": item_level,
                    "simcOptions": {"ilevel": str(item_level)},
                    "status": status,
                    "blockers": blockers,
                    "payload": payload,
                },
            )
            if status == "verified":
                counts["verifiedVariants"] += 1
            else:
                counts["partialVariants"] += 1
                counts["errors"].append(f"{item_id}:{item_level}: {blockers[0] if blockers else 'partial'}")
    removed_pending = delete_pending_gear_variant_placeholders(conn, processed_item_ids, "tier_set")
    if removed_pending:
        counts["removedPendingVariants"] = removed_pending
    conn.commit()
    set_sync_state(conn, "gearCatalog", build_gear_catalog_sync_state(conn, get_active_season_payload(conn)))
    return counts


def backfill_crafted_item_level_variants(conn, items, stat_resolver=None):
    ensure_websim_tables(conn)
    season = get_active_season_payload(conn)
    season_revision = season.get("seasonRevision") or season.get("revision") or ""
    if stat_resolver is None:
        stat_resolver = lambda item, item_level, stat_option, track: resolve_crafted_item_level_stat_payload(
            conn,
            item,
            item_level,
            stat_option,
            track,
        )
    counts = {"items": 0, "tracks": 0, "verifiedVariants": 0, "partialVariants": 0, "skipped": 0, "errors": []}
    for raw_item in items or []:
        if not isinstance(raw_item, dict):
            counts["skipped"] += 1
            continue
        item_id = normalize_option_value(raw_item.get("itemId") or raw_item.get("item_id") or raw_item.get("id"))
        if not item_id:
            counts["skipped"] += 1
            counts["errors"].append("crafted item missing itemId")
            continue
        metadata = existing_websim_item_metadata(conn, item_id) or {}
        metadata_payload = metadata.get("payload") if isinstance(metadata.get("payload"), dict) else {}
        type_metadata = item_type_metadata_from_payload(metadata_payload)
        slot = normalize_slot(raw_item.get("slot")) or normalize_slot(metadata.get("slot")) or item_slot_from_payload(metadata_payload)
        if not slot:
            counts["skipped"] += 1
            counts["errors"].append(f"{item_id}: missing slot")
            continue
        item = {
            **raw_item,
            "itemId": item_id,
            "name": str(raw_item.get("name") or metadata.get("displayName") or metadata.get("name") or f"item_{item_id}"),
            "slot": slot,
            "simcSlot": official_item_level_probe_simc_slot(slot),
            "metadataPayload": metadata_payload,
            "armorType": raw_item.get("armorType") or type_metadata.get("armorType") or "",
            "weaponType": raw_item.get("weaponType") or type_metadata.get("weaponType") or "",
        }
        tracks = crafted_item_level_tracks_for_item(item)
        stat_options = crafted_stat_options_for_item(item)
        if not tracks:
            counts["skipped"] += 1
            counts["errors"].append(f"{item_id}: missing crafted item-level track evidence")
            continue
        if not stat_options:
            counts["skipped"] += 1
            counts["errors"].append(f"{item_id}: missing crafted stat options")
            continue
        conn.execute(
            "DELETE FROM websim_gear_variants WHERE source_type = ? AND item_id = ?",
            ("crafted", item_id),
        )
        counts["items"] += 1
        source_payload = {
            "status": str(raw_item.get("status") or "verified").strip() or "verified",
            "profession": str(raw_item.get("profession") or "").strip(),
            "recipeId": normalize_option_value(raw_item.get("recipeId") or raw_item.get("recipe_id")),
            "seasonRevision": season_revision,
            "sourceRefs": normalize_source_refs(raw_item.get("sourceRefs") or []),
            "trackEvidence": raw_item.get("trackEvidence") or raw_item.get("evidence") or [],
            "supportsVoidUpgrade": bool(crafted_item_supports_void_upgrade(item)),
        }
        upsert_gear_source(
            conn,
            {
                "id": str(raw_item.get("sourceId") or f"crafted-governed-{item_id}"),
                "itemId": item_id,
                "sourceType": "crafted",
                "sourceLabel": str(raw_item.get("sourceLabel") or "制造装备"),
                "seasonRevision": season_revision,
                "payload": source_payload,
            },
        )
        for stat_option in stat_options:
            upsert_gear_mod_option(
                conn,
                {
                    "id": f"crafted-stats-{stat_option['key']}",
                    "type": "crafted_stats",
                    "name": stat_option["label"],
                    "applicableSlots": [slot],
                    "simcOptions": {"crafted_stats": stat_option["value"]},
                    "status": stat_option.get("status") or "verified",
                    "payload": {
                        **(stat_option.get("payload") or {}),
                        "source": "crafted_catalog",
                        "craftedStatKey": stat_option["key"],
                        "craftedStatLabel": stat_option["label"],
                    },
                },
            )
        for track in tracks:
            counts["tracks"] += 1
            difficulty_key = normalized_difficulty_key(track.get("difficultyKey"))
            item_level = positive_int_value(track.get("itemLevel"))
            if not item_level:
                counts["skipped"] += 1
                counts["errors"].append(f"{item_id}:{difficulty_key}: missing item level")
                continue
            for stat_option in stat_options:
                stat_payload = stat_resolver(item, item_level, stat_option, track) or {}
                stat_payload = stat_payload if isinstance(stat_payload, dict) else {}
                stats = normalize_item_stats(stat_payload.get("itemStats") or stat_payload.get("stats") or [])
                blockers = []
                status = "verified"
                if not stats or stat_option.get("status") != "verified":
                    status = "partial"
                    blockers.append(str(stat_payload.get("error") or "SimC crafted item probe missing item stats")[:1000])
                simc_options = {"ilevel": str(item_level), "crafted_stats": stat_option["value"]}
                for key in ("bonus_id", "bonusId"):
                    value = normalize_option_value(raw_item.get(key) or track.get(key))
                    if value:
                        simc_options["bonus_id"] = value
                        break
                payload = {
                    **source_payload,
                    "officialVariantSource": "crafted",
                    "derivedVariantSource": CRAFTED_ITEM_LEVEL_PROBE_SOURCE,
                    "itemLevelTrack": difficulty_key,
                    "publicDifficultyKey": crafted_public_difficulty_key(difficulty_key),
                    "craftedStatKey": stat_option["key"],
                    "craftedStatLabel": stat_option["label"],
                    "crafted_stats": stat_option["value"],
                    "statSource": "simulationcraft",
                }
                for key, value in stat_payload.items():
                    if value not in (None, "", [], {}):
                        payload[key] = value
                if stats:
                    payload["itemStats"] = stats
                    payload["stats"] = stats
                    payload["statSummary"] = stat_payload.get("statSummary") or item_stat_summary(stats)
                    payload["statDisplayStatus"] = stat_payload.get("statDisplayStatus") or "verified_variant"
                variant_id = f"crafted-itemlevel-{item_id}-{slot}-{difficulty_key}-{item_level}-{stat_option['key']}"
                upsert_gear_variant(
                    conn,
                    {
                        "id": variant_id,
                        "itemId": item_id,
                        "slot": slot,
                        "variantKey": f"{crafted_public_difficulty_key(difficulty_key)}-{item_level}-{stat_option['key']}",
                        "label": f"{localized_difficulty_label(difficulty_key, track.get('label'), 'crafted')} {item_level} · {stat_option['label']}",
                        "sourceType": "crafted",
                        "difficultyKey": difficulty_key,
                        "itemLevel": item_level,
                        "simcOptions": simc_options,
                        "status": status,
                        "blockers": blockers,
                        "payload": payload,
                    },
                )
                if status == "verified":
                    counts["verifiedVariants"] += 1
                else:
                    counts["partialVariants"] += 1
                    counts["errors"].append(f"{item_id}:{item_level}:{stat_option['key']}: {blockers[0] if blockers else 'partial'}")
    conn.commit()
    set_sync_state(conn, "gearCatalog", build_gear_catalog_sync_state(conn, season))
    return counts


def gear_mod_option_quality_rank(option):
    option = option if isinstance(option, dict) else {}
    payload = option.get("payload") if isinstance(option.get("payload"), dict) else {}
    for source in (option, payload):
        for key in (
            "qualityRank",
            "quality_rank",
            "rank",
            "craftingQuality",
            "crafting_quality",
            "qualityTier",
            "quality_tier",
            "starRank",
            "star_rank",
        ):
            value = source.get(key)
            if value in (None, "", [], {}):
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                text = str(value or "").strip().lower()
                if text in {"2", "r2", "rank2", "rank_2", "rank-two", "rank_two", "two", "two-star", "two_star", "2-star", "2星", "二星"}:
                    return 2
                if text in {"1", "r1", "rank1", "rank_1", "rank-one", "rank_one", "one", "one-star", "one_star", "1-star", "1星", "一星"}:
                    return 1
    return None


def gear_mod_option_has_supported_quality(option_type, option):
    if option_type == "crafted_stats":
        return True
    rank = gear_mod_option_quality_rank(option)
    if option_type == "socket":
        return rank == 2
    return rank in (None, 2)


def gear_mod_option_has_executable_field(option_type, simc_options):
    if option_type == "socket":
        return bool(normalize_option_value(simc_options.get("gem_id")))
    if option_type == "enchant":
        return bool(normalize_option_value(simc_options.get("enchant_id")))
    if option_type == "embellishment":
        return bool(normalize_option_value(simc_options.get("embellishment")))
    if option_type == "crafted_stats":
        return bool(normalize_option_value(simc_options.get("crafted_stats")))
    return False


def single_numeric_simc_option_value(simc_options, key):
    if not isinstance(simc_options, dict):
        return False
    value = normalize_option_value(simc_options.get(key))
    if not value:
        return False
    parts = [part.strip() for part in value.split("/") if part.strip()]
    return len(parts) == 1 and bool(re.fullmatch(r"\d+", parts[0]))


def gear_mod_option_is_supported_config_option(option_type, simc_options, payload=None, option_name=""):
    option_type = str(option_type or "").strip().lower()
    simc_options = simc_options if isinstance(simc_options, dict) else {}
    if option_type == "enchant":
        if gear_config_enchant_exclusion(option_name, simc_options, payload):
            return False
    return True


def upsert_gear_mod_option(conn, option):
    option_type = str(option.get("optionType") or option.get("type") or "").strip().lower()
    if option_type not in GEAR_MOD_OPTION_TYPES:
        return False
    simc_options = option.get("simcOptions") if isinstance(option.get("simcOptions"), dict) else {}
    simc_options = {key: value for key, value in simc_options.items() if key in SIMC_GEAR_OPTION_KEYS and normalize_option_value(value)}
    payload = option.get("payload") if isinstance(option.get("payload"), dict) else {}
    if not simc_options or not gear_mod_option_has_executable_field(option_type, simc_options):
        return False
    if not gear_mod_option_is_supported_config_option(option_type, simc_options, payload, option.get("name") or option.get("label") or ""):
        return False
    if option_type == "socket" and len(gem_item_ids_from_simc_options(simc_options)) != 1:
        return False
    if option_type == "enchant" and not single_numeric_simc_option_value(simc_options, "enchant_id"):
        return False
    status = str(option.get("status") or "verified").strip().lower()
    if status and status != "verified":
        return False
    if not gear_mod_option_has_supported_quality(option_type, option):
        return False
    option_id = str(option.get("id") or "").strip()
    if not option_id:
        digest = hashlib.sha256(json.dumps([option_type, option.get("name") or option.get("label") or "", simc_options], sort_keys=True).encode("utf-8")).hexdigest()[:12]
        option_id = f"seed-{option_type}-{digest}"
    slots = option.get("applicableSlots") or option.get("slots") or option.get("applicable_slots") or []
    if isinstance(slots, str):
        slots = [slots]
    slots = unique_text_list([normalize_slot(slot) or str(slot or "").strip() for slot in slots])
    payload = gear_mod_option_payload_with_config_policy(
        option_type,
        option.get("name") or option.get("label") or option_id,
        simc_options,
        payload,
        slots,
    )
    if option_type == "crafted_stats" and option_id:
        existing_row = conn.execute(
            "SELECT applicable_slots_json FROM websim_gear_mod_options WHERE id = ?",
            (option_id,),
        ).fetchone()
        if existing_row:
            existing_slots = safe_json_loads(existing_row[0], [])
            if not isinstance(existing_slots, list):
                existing_slots = []
            slots = unique_text_list([*existing_slots, *slots])
    conn.execute(
        """
        INSERT INTO websim_gear_mod_options
        (id, option_type, name, applicable_slots_json, simc_options_json,
         status, payload_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            option_type=excluded.option_type,
            name=excluded.name,
            applicable_slots_json=excluded.applicable_slots_json,
            simc_options_json=excluded.simc_options_json,
            status=excluded.status,
            payload_json=excluded.payload_json,
            updated_at=excluded.updated_at
        """,
        (
            option_id,
            option_type,
            str(option.get("name") or option.get("label") or option_id)[:160],
            json.dumps(slots, ensure_ascii=False),
            json.dumps(simc_options, ensure_ascii=False),
            "verified",
            json.dumps(payload, ensure_ascii=False),
            utc_now(),
        ),
    )
    return True


def observed_variant_socket_mod_options(conn):
    rows = conn.execute(
        """
        SELECT item_id, slot, simc_options_json, payload_json
        FROM websim_gear_variants
        WHERE source_type = 'observed_profile'
          AND status IN ('verified', 'partial')
        ORDER BY item_id, slot
        """
    ).fetchall()
    options = []
    seen = set()
    for item_id, raw_slot, simc_options_json, payload_json in rows:
        simc_options = safe_json_loads(simc_options_json, {})
        if not isinstance(simc_options, dict):
            continue
        gem_id = normalize_option_value(simc_options.get("gem_id"))
        if not gem_id:
            continue
        slot = normalize_slot(raw_slot)
        if not slot:
            continue
        option_simc = {"gem_id": gem_id}
        for key in ("gem_bonus_id", "gem_ilevel"):
            value = normalize_option_value(simc_options.get(key))
            if value:
                option_simc[key] = value
        digest = hashlib.sha1(json.dumps(option_simc, sort_keys=True).encode("utf-8")).hexdigest()[:10]
        option_id = f"observed-socket-{digest}"
        if option_id in seen:
            continue
        seen.add(option_id)
        payload = safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        options.append(
            {
                "id": option_id,
                "type": "socket",
                "name": f"Observed gem {gem_id}",
                "slots": ["*"],
                "simcOptions": option_simc,
                "status": "verified",
                "payload": {
                    "source": "observed_variant",
                    "itemId": str(item_id or ""),
                    "slot": slot,
                    "variantPayload": payload,
                },
            }
        )
    return options


def observed_mod_option_slots(slot, option_type):
    slot = normalize_slot(slot)
    if not slot:
        return []
    slots = EQUIVALENT_GEAR_SLOTS.get(slot, [slot])
    if option_type == "enchant":
        slots = [item for item in slots if item in ENCHANTABLE_GEAR_SLOTS]
    return [item for item in CANONICAL_GEAR_SLOTS if item in set(slots)]


def observed_variant_enchant_mod_options(conn):
    rows = conn.execute(
        """
        SELECT item_id, slot, simc_options_json, payload_json
        FROM websim_gear_variants
        WHERE source_type = 'observed_profile'
          AND status IN ('verified', 'partial')
        ORDER BY item_id, slot
        """
    ).fetchall()
    options = []
    seen = set()
    for item_id, raw_slot, simc_options_json, payload_json in rows:
        simc_options = safe_json_loads(simc_options_json, {})
        if not isinstance(simc_options, dict):
            continue
        enchant_id = normalize_option_value(simc_options.get("enchant_id"))
        if not enchant_id:
            continue
        slots = observed_mod_option_slots(raw_slot, "enchant")
        if not slots:
            continue
        option_simc = {"enchant_id": enchant_id}
        digest = hashlib.sha1(json.dumps([option_simc, slots], sort_keys=True).encode("utf-8")).hexdigest()[:10]
        option_id = f"observed-enchant-{digest}"
        if option_id in seen:
            continue
        seen.add(option_id)
        payload = safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        options.append(
            {
                "id": option_id,
                "type": "enchant",
                "name": f"Observed enchant {enchant_id}",
                "slots": slots,
                "simcOptions": option_simc,
                "status": "verified",
                "payload": {
                    "source": "observed_variant",
                    "itemId": str(item_id or ""),
                    "slot": normalize_slot(raw_slot),
                    "variantPayload": payload,
                },
            }
        )
    return options


def observed_variant_embellishment_mod_options(conn):
    rows = conn.execute(
        """
        SELECT item_id, slot, simc_options_json, payload_json
        FROM websim_gear_variants
        WHERE source_type = 'observed_profile'
          AND status IN ('verified', 'partial')
        ORDER BY item_id, slot
        """
    ).fetchall()
    options = []
    seen = set()
    for item_id, raw_slot, simc_options_json, payload_json in rows:
        simc_options = safe_json_loads(simc_options_json, {})
        if not isinstance(simc_options, dict):
            continue
        embellishment = normalize_option_value(simc_options.get("embellishment"))
        if not embellishment:
            continue
        slots = observed_mod_option_slots(raw_slot, "embellishment")
        if not slots:
            continue
        option_simc = {"embellishment": embellishment}
        digest = hashlib.sha1(json.dumps([option_simc, slots], sort_keys=True).encode("utf-8")).hexdigest()[:10]
        option_id = f"observed-embellishment-{digest}"
        if option_id in seen:
            continue
        seen.add(option_id)
        payload = safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        options.append(
            {
                "id": option_id,
                "type": "embellishment",
                "name": f"Observed embellishment {embellishment}",
                "slots": slots,
                "simcOptions": option_simc,
                "status": "verified",
                "payload": {
                    "source": "observed_variant",
                    "itemId": str(item_id or ""),
                    "slot": normalize_slot(raw_slot),
                    "variantPayload": payload,
                },
            }
        )
    return options


def observed_gear_spec_entries(raiderio):
    if not isinstance(raiderio, dict):
        return []
    entries = []

    def append_profile_entry(profile):
        if not isinstance(profile, dict):
            return
        class_key = slugify(profile.get("classKey") or profile.get("classSlug") or profile.get("className"), "")
        spec_key = slugify(profile.get("specKey") or profile.get("specSlug") or profile.get("specName"), "")
        gear = profile.get("gear") if isinstance(profile.get("gear"), list) else []
        if not class_key or not spec_key or not gear:
            return
        entries.append(
            (
                class_key,
                spec_key,
                {
                    **profile,
                    "characterName": profile.get("characterName") or profile.get("name") or "",
                    "realmSlug": profile.get("realmSlug") or profile.get("realm") or "",
                    "profileUrl": profile.get("profileUrl") or profile.get("profile_url") or "",
                },
                gear,
            )
        )

    for profile in raiderio.get("profiles") or []:
        append_profile_entry(profile)

    for aggregate in raiderio.get("specAggregates") or []:
        if not isinstance(aggregate, dict):
            continue
        class_key = slugify(aggregate.get("classKey"), "")
        spec_key = slugify(aggregate.get("specKey"), "")
        gear = aggregate.get("observedGear") if isinstance(aggregate.get("observedGear"), list) else []
        if class_key and spec_key and gear:
            entries.append((class_key, spec_key, aggregate, gear))
        for profile in aggregate.get("observedGearProfiles") or []:
            if not isinstance(profile, dict):
                continue
            profile_gear = profile.get("gear") if isinstance(profile.get("gear"), list) else []
            if class_key and spec_key and profile_gear:
                entries.append((class_key, spec_key, {**aggregate, **profile}, profile_gear))
    specs = raiderio.get("specs") if isinstance(raiderio.get("specs"), dict) else {}
    for spec_id, aggregate in specs.items():
        if not isinstance(aggregate, dict):
            continue
        class_key = slugify(aggregate.get("classKey"), "")
        spec_key = slugify(aggregate.get("specKey"), "")
        if (not class_key or not spec_key) and ":" in str(spec_id):
            raw_class, raw_spec = str(spec_id).split(":", 1)
            class_key = class_key or slugify(raw_class, "")
            spec_key = spec_key or slugify(raw_spec, "")
        gear = aggregate.get("observedGear") if isinstance(aggregate.get("observedGear"), list) else []
        if class_key and spec_key and gear:
            entries.append((class_key, spec_key, aggregate, gear))
        for profile in aggregate.get("observedGearProfiles") or []:
            if not isinstance(profile, dict):
                continue
            profile_gear = profile.get("gear") if isinstance(profile.get("gear"), list) else []
            if class_key and spec_key and profile_gear:
                entries.append((class_key, spec_key, {**aggregate, **profile}, profile_gear))
    return entries


def observed_id_values(value, keys=None):
    values = []

    def visit(item):
        if item in (None, ""):
            return
        if isinstance(item, list):
            for nested in item:
                visit(nested)
            return
        if isinstance(item, tuple):
            for nested in item:
                visit(nested)
            return
        if isinstance(item, dict):
            for key in keys or []:
                if key in item and item.get(key) not in (None, ""):
                    visit(item.get(key))
                    return
            return
        normalized = normalize_option_value(item)
        if normalized:
            values.append(normalized)

    visit(value)
    unique = []
    seen = set()
    for value_text in values:
        if value_text in seen:
            continue
        seen.add(value_text)
        unique.append(value_text)
    return unique


def observed_dict_field_values(value, keys=None):
    values = []

    def visit(item):
        if item in (None, ""):
            return
        if isinstance(item, list):
            for nested in item:
                visit(nested)
            return
        if isinstance(item, tuple):
            for nested in item:
                visit(nested)
            return
        if not isinstance(item, dict):
            return
        for key in keys or []:
            if key in item and item.get(key) not in (None, ""):
                normalized = normalize_option_value(item.get(key))
                if normalized:
                    values.append(normalized)
                return

    visit(value)
    unique = []
    seen = set()
    for value_text in values:
        if value_text in seen:
            continue
        seen.add(value_text)
        unique.append(value_text)
    return unique


def observed_gear_simc_options(item):
    if not isinstance(item, dict):
        return {}
    options = {}
    bonus_ids = observed_id_values(item.get("bonuses") or item.get("bonusIds") or item.get("bonus_id"), ["id", "bonusId", "bonus_id"])
    if bonus_ids:
        options["bonus_id"] = "/".join(bonus_ids)
    gem_ids = observed_id_values(item.get("gems") or item.get("gemIds") or item.get("gem_id"), ["itemId", "item_id", "id"])
    if gem_ids:
        options["gem_id"] = "/".join(gem_ids)
    gem_bonus_ids = [
        *observed_dict_field_values(item.get("gems"), ["bonusId", "bonus_id", "bonusIds"]),
        *observed_id_values(item.get("gemBonusIds") or item.get("gem_bonus_id"), ["bonusId", "bonus_id", "bonusIds"]),
    ]
    if gem_bonus_ids:
        options["gem_bonus_id"] = "/".join(dict.fromkeys(gem_bonus_ids))
    gem_item_levels = [
        *observed_dict_field_values(item.get("gems"), ["itemLevel", "item_level", "ilevel"]),
        *observed_id_values(item.get("gemItemLevels") or item.get("gem_ilevel"), ["itemLevel", "item_level", "ilevel"]),
    ]
    if gem_item_levels:
        options["gem_ilevel"] = "/".join(dict.fromkeys(gem_item_levels))
    enchant_ids = observed_id_values(item.get("enchants") or item.get("enchant") or item.get("enchant_id"), ["spellId", "spell_id", "enchantId", "enchant_id", "id"])
    if enchant_ids:
        options["enchant_id"] = "/".join(enchant_ids)
    crafted_stats = normalize_option_value(item.get("crafted_stats") or item.get("craftedStats"))
    if crafted_stats:
        options["crafted_stats"] = crafted_stats
    embellishment = normalize_option_value(item.get("embellishment") or item.get("embellishmentId") or item.get("embellishment_id"))
    if embellishment:
        options["embellishment"] = embellishment
    return {key: value for key, value in options.items() if key in SIMC_GEAR_OPTION_KEYS and value}


def observed_item_level(item):
    value = first_matching_value(item, ["itemLevel", "ilevel", "item_level"], 0)
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def observed_variant_stat_identity_key(item_id, slot, item_level, simc_options):
    try:
        normalized_level = int(float(str(item_level or 0).strip()))
    except (TypeError, ValueError):
        normalized_level = 0
    return (
        normalize_option_value(item_id),
        normalize_slot(slot),
        normalized_level,
        simc_options_signature(simc_options),
    )


def existing_observed_variant_stat_payloads_by_identity(conn):
    rows = conn.execute(
        """
        SELECT item_id, slot, item_level, simc_options_json, payload_json
        FROM websim_gear_variants
        WHERE source_type = 'observed_profile'
          AND status = 'verified'
        """
    ).fetchall()
    payloads = {}
    for item_id, slot, item_level, simc_options_json, payload_json in rows:
        stat_payload = observed_variant_stat_payload_fields(safe_json_loads(payload_json, {}))
        if not stat_payload:
            continue
        key = observed_variant_stat_identity_key(
            item_id,
            slot,
            item_level,
            safe_json_loads(simc_options_json, {}),
        )
        payloads.setdefault(key, stat_payload)
    return payloads


def verified_observed_variant_with_stats_count(conn):
    rows = conn.execute(
        """
        SELECT payload_json
        FROM websim_gear_variants
        WHERE source_type = 'observed_profile'
          AND status = 'verified'
        """
    ).fetchall()
    count = 0
    for (payload_json,) in rows:
        if observed_variant_stat_payload_fields(safe_json_loads(payload_json, {})):
            count += 1
    return count


def existing_observed_variant_simc_failure_payloads_by_identity(conn):
    rows = conn.execute(
        """
        SELECT item_id, slot, item_level, simc_options_json, payload_json
        FROM websim_gear_variants
        WHERE source_type = 'observed_profile'
          AND status = 'verified'
        """
    ).fetchall()
    payloads = {}
    for item_id, slot, item_level, simc_options_json, payload_json in rows:
        failure_payload = observed_variant_simc_failure_payload_fields(safe_json_loads(payload_json, {}))
        if not failure_payload:
            continue
        key = observed_variant_stat_identity_key(
            item_id,
            slot,
            item_level,
            safe_json_loads(simc_options_json, {}),
        )
        payloads.setdefault(key, failure_payload)
    return payloads


def ensure_observed_item_metadata(conn, item, slot, source="raiderio_observed_profile", context_key="websim-item-observed-profile"):
    item_id = normalize_option_value(first_matching_value(item, ["itemId", "item_id", "id"]))
    if not item_id:
        return None
    existing = existing_websim_item_metadata(conn, item_id)
    if existing:
        return existing
    display_name = str(item.get("displayName") or item.get("name") or f"Item {item_id}")[:220]
    icon_url = str(item.get("iconUrl") or item.get("icon_url") or item.get("icon") or "")[:260]
    quality = str(item.get("quality") or item.get("item_quality") or "")[:80]
    item_asset = game_asset_from_icon_url(
        "item",
        item_id,
        context_key,
        icon_url,
        source=source,
        status="source_reference",
        semantic_tags=["game", "gear", "item", slot],
        usage=["websim_gear", "builds_detail"],
        fallback_text=fallback_text_for(display_name),
    )
    payload = {
        "id": item_id,
        "name": display_name,
        "inventory_type": {"type": slot.upper(), "name": slot},
        "quality": {"name": quality},
        "_metadata": {
            "source": source,
            "metadataStatus": "source_reference",
            "itemId": item_id,
            "locale": DEFAULT_LOCALE,
            "iconUrl": icon_url,
            "gameAsset": item_asset,
        },
    }
    conn.execute(
        """
        INSERT INTO websim_items (id, name, slot, quality, icon_url, payload_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO NOTHING
        """,
        (item_id, display_name, slot, quality, icon_url, json.dumps(payload, ensure_ascii=False), utc_now()),
    )
    upsert_websim_asset(conn, item_asset)
    return existing_websim_item_metadata(conn, item_id)


def sync_observed_gear_variants(conn, raiderio=None, season=None, *, replace=True):
    ensure_websim_tables(conn)
    season = season or get_active_season_payload(conn)
    entries = observed_gear_spec_entries(raiderio or {})
    counts = {
        "observedSources": 0,
        "observedVariants": 0,
        "verifiedObservedVariants": 0,
        "partialObservedVariants": 0,
        "blockedObservedVariants": 0,
        "skipped": 0,
    }
    if not entries:
        return counts
    source_status = str((raiderio or {}).get("sourceStatus") or (raiderio or {}).get("status") or "").strip()
    if source_status and source_status not in {"verified", "synced"}:
        counts["skipped"] += sum(1 for _class_key, _spec_key, _aggregate, gear_items in entries for item in gear_items if isinstance(item, dict))
        counts["sourceStatus"] = source_status
        return counts
    existing_verified = verified_observed_variant_with_stats_count(conn)
    incoming_verified = 0
    incoming_items = 0
    for _class_key, _spec_key, _aggregate, gear_items in entries:
        aggregate_simc_gear = simc_json_gear_stats_by_slot(_aggregate)
        for item in gear_items:
            if not isinstance(item, dict):
                continue
            item_id = normalize_option_value(first_matching_value(item, ["itemId", "item_id", "id"]))
            slot = normalize_slot(first_matching_value(item, ["simcSlot", "slot", "slotKey", "equipmentSlot"]))
            if not item_id or not slot:
                continue
            incoming_items += 1
            item_simc_gear = simc_json_gear_stats_by_slot(item) or aggregate_simc_gear
            if (
                observed_item_level(item)
                and observed_gear_simc_options(item)
                and simc_observed_variant_stat_payload(item, item_simc_gear)
            ):
                incoming_verified += 1
    allow_downgrade = os.environ.get("WOW_RAIDERIO_ALLOW_OBSERVED_CACHE_DOWNGRADE", "0").strip().lower() in {"1", "true", "yes", "on"}
    if replace and existing_verified and incoming_verified < existing_verified and not allow_downgrade:
        counts["skipped"] += incoming_items
        counts["sourceStatus"] = source_status or ""
        counts["preservedVerifiedObservedVariants"] = existing_verified
        counts["incomingVerifiedObservedVariants"] = incoming_verified
        return counts
    preserved_stat_payloads = existing_observed_variant_stat_payloads_by_identity(conn)
    preserved_failure_payloads = existing_observed_variant_simc_failure_payloads_by_identity(conn)
    if replace:
        conn.execute("DELETE FROM websim_gear_sources WHERE source_type = 'observed_profile' OR id LIKE 'observed-%'")
        conn.execute("DELETE FROM websim_gear_variants WHERE source_type = 'observed_profile' OR id LIKE 'observed-%'")
    checked_at = (raiderio or {}).get("checkedAt") or ""
    season_revision = (season or {}).get("seasonRevision") or (season or {}).get("revision") or ""
    seen_source_ids = set()
    seen_variant_ids = set()
    for class_key, spec_key, aggregate, gear_items in entries:
        aggregate_simc_gear = simc_json_gear_stats_by_slot(aggregate)
        for item in gear_items:
            if not isinstance(item, dict):
                continue
            item_id = normalize_option_value(first_matching_value(item, ["itemId", "item_id", "id"]))
            slot = normalize_slot(first_matching_value(item, ["simcSlot", "slot", "slotKey", "equipmentSlot"]))
            if not item_id or not slot:
                counts["skipped"] += 1
                continue
            item_level = observed_item_level(item)
            simc_options = observed_gear_simc_options(item)
            blockers = []
            if not item_level:
                blockers.append("missing observed item level")
            if not simc_options:
                blockers.append("missing deterministic SimC variant preset")
            if source_status and source_status not in {"verified", "synced"}:
                blockers.append("Raider.IO observed gear source is not verified")
            metadata = ensure_observed_item_metadata(conn, item, slot)
            display_name = (metadata or {}).get("displayName") or item.get("name") or f"Item {item_id}"
            source_ref = {
                "sourceName": item.get("sourceName") or (raiderio or {}).get("sourceName") or "Raider.IO CN profile gear",
                "sourceStatus": source_status or "source_reference",
                "checkedAt": checked_at,
                "classKey": class_key,
                "specKey": spec_key,
                "slot": slot,
                "itemId": item_id,
                "itemLevel": item_level,
                "characterName": item.get("characterName") or aggregate.get("characterName") or "",
                "realmSlug": item.get("realmSlug") or aggregate.get("realmSlug") or "",
                "profileUrl": item.get("profileUrl") or aggregate.get("profileUrl") or "",
            }
            source_id = f"observed-source-{class_key}-{spec_key}-{slot}-{item_id}"
            upsert_gear_source(
                conn,
                {
                    "id": source_id,
                    "itemId": item_id,
                    "sourceType": "observed_profile",
                    "sourceLabel": f"Raider.IO CN observed {class_key} {spec_key}",
                    "seasonRevision": season_revision,
                    "payload": {
                        "classKeys": [class_key],
                        "specKeys": [spec_key],
                        "observedProfileRefs": [source_ref],
                    },
                },
            )
            is_new_source = source_id not in seen_source_ids
            seen_source_ids.add(source_id)
            variant_digest = hashlib.sha1(
                json.dumps([class_key, spec_key, slot, item_id, item_level, simc_options], sort_keys=True).encode("utf-8")
            ).hexdigest()[:10]
            variant_key = f"observed-{item_level or 'unknown'}-{variant_digest}"
            variant_id = f"observed-{class_key}-{spec_key}-{slot}-{item_id}-{variant_digest}"
            item_simc_gear = simc_json_gear_stats_by_slot(item) or aggregate_simc_gear
            variant_payload = {
                "classKeys": [class_key],
                "specKeys": [spec_key],
                "seasonRevision": season_revision,
                "observedProfileRefs": [source_ref],
                "displayName": display_name,
            }
            identity_key = observed_variant_stat_identity_key(item_id, slot, item_level, simc_options)
            stat_payload = simc_observed_variant_stat_payload(item, item_simc_gear)
            if not stat_payload and preserved_stat_payloads:
                stat_payload = preserved_stat_payloads.get(identity_key) or {}
            if stat_payload:
                variant_payload.update(stat_payload)
            else:
                if item_level and simc_options:
                    blockers.append(MISSING_OBSERVED_SIMC_STATS_BLOCKER)
                if preserved_failure_payloads:
                    variant_payload.update(preserved_failure_payloads.get(identity_key) or {})
            blockers = unique_text_list(blockers)
            status = "verified" if not blockers and stat_payload else "partial"
            upsert_gear_variant(
                conn,
                {
                    "id": variant_id,
                    "itemId": item_id,
                    "slot": slot,
                    "variantKey": variant_key,
                    "label": f"Observed {item_level or 'unknown'}",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": item_level,
                    "simcOptions": simc_options,
                    "status": status,
                    "blockers": blockers,
                    "payload": variant_payload,
                },
            )
            if is_new_source:
                counts["observedSources"] += 1
            if variant_id in seen_variant_ids:
                continue
            seen_variant_ids.add(variant_id)
            counts["observedVariants"] += 1
            if status == "verified":
                counts["verifiedObservedVariants"] += 1
            elif status == "partial":
                counts["partialObservedVariants"] += 1
            else:
                counts["blockedObservedVariants"] += 1
    return counts


def gear_variant_slots_are_compatible(source_slot, observed_slot):
    source_slot = normalize_slot(source_slot)
    observed_slot = normalize_slot(observed_slot)
    if not source_slot or not observed_slot:
        return False
    if source_slot == observed_slot:
        return True
    if observed_slot in EQUIVALENT_GEAR_SLOTS.get(source_slot, []):
        return True
    return source_slot in EQUIVALENT_GEAR_SLOTS.get(observed_slot, [])


def gear_variant_slots_are_compatible_for_item(item_payload, source_slot, observed_slot):
    if gear_variant_slots_are_compatible(source_slot, observed_slot):
        return True
    source_slot = normalize_slot(source_slot)
    observed_slot = normalize_slot(observed_slot)
    if {source_slot, observed_slot} != {"main_hand", "off_hand"}:
        return False
    weapon_type = item_type_metadata_from_payload(item_payload).get("weaponType") or ""
    return weapon_type in DUAL_WIELDABLE_WEAPON_TYPES


OFFICIAL_OBSERVED_STAT_PAYLOAD_KEYS = (
    "statSource",
    "statSourceDetail",
    "statDisplayStatus",
    "itemStats",
    "statSummary",
    "simcItemId",
    "simcItemLevel",
    "simcEncodedItem",
)


OBSERVED_VARIANT_SIMC_FAILURE_PAYLOAD_KEYS = (
    "simcStatStatus",
    "simcStatFailureKind",
    "simcStatError",
    "simcStatCheckedAt",
)
MISSING_OBSERVED_SIMC_STATS_BLOCKER = "missing SimulationCraft item stats"


def observed_variant_stat_payload_fields(payload):
    payload = payload if isinstance(payload, dict) else {}
    if payload.get("statSource") != "simulationcraft" or not payload.get("itemStats"):
        return {}
    return {
        key: payload.get(key)
        for key in OFFICIAL_OBSERVED_STAT_PAYLOAD_KEYS
        if payload.get(key) not in (None, "", [])
    }


def observed_variant_simc_failure_payload_fields(payload):
    payload = payload if isinstance(payload, dict) else {}
    if payload.get("simcStatStatus") != "failed":
        return {}
    return {
        key: payload.get(key)
        for key in OBSERVED_VARIANT_SIMC_FAILURE_PAYLOAD_KEYS
        if payload.get(key) not in (None, "", [])
    }


def simc_options_signature(options):
    options = options if isinstance(options, dict) else {}
    result = {}
    for key in SIMC_GEAR_OPTION_KEYS:
        value = normalize_option_value(options.get(key))
        if value:
            result[key] = sorted(simc_option_segments(value))
    return json.dumps(result, sort_keys=True, ensure_ascii=False)


def refresh_official_observed_variant_payloads_from_observed(conn):
    ensure_websim_tables(conn)
    observed_rows = conn.execute(
        """
        SELECT item_id, simc_options_json, payload_json
        FROM websim_gear_variants
        WHERE source_type = 'observed_profile'
          AND status = 'verified'
        """
    ).fetchall()
    observed_payload_by_key = {}
    observed_context_by_key = {}
    for item_id, simc_options_json, payload_json in observed_rows:
        payload = safe_json_loads(payload_json, {})
        stat_payload = observed_variant_stat_payload_fields(payload)
        if not stat_payload:
            continue
        key = (str(item_id), simc_options_signature(safe_json_loads(simc_options_json, {})))
        observed_payload_by_key[key] = stat_payload
        observed_context_by_key[key] = class_spec_context_from_payload(payload)
    if not observed_payload_by_key:
        return {"refreshedOfficialObservedVariants": 0}
    official_rows = conn.execute(
        """
        SELECT id, item_id, simc_options_json, payload_json
        FROM websim_gear_variants
        WHERE source_type IN ('dungeon', 'raid', 'tier_set')
          AND difficulty_key = 'observed_profile'
          AND status = 'verified'
        """
    ).fetchall()
    refreshed = 0
    for row_id, item_id, simc_options_json, payload_json in official_rows:
        key = (str(item_id), simc_options_signature(safe_json_loads(simc_options_json, {})))
        stat_payload = observed_payload_by_key.get(key)
        if not stat_payload:
            continue
        payload = safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        observed_class_keys, observed_spec_keys = observed_context_by_key.get(key) or ([], [])
        payload.pop("classKeys", None)
        payload.pop("specKeys", None)
        payload.update(stat_payload)
        if observed_class_keys:
            payload["observedClassKeys"] = observed_class_keys
        if observed_spec_keys:
            payload["observedSpecKeys"] = observed_spec_keys
        conn.execute(
            """
            UPDATE websim_gear_variants
            SET payload_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (json.dumps(payload, ensure_ascii=False), utc_now(), row_id),
        )
        refreshed += 1
    return {"refreshedOfficialObservedVariants": refreshed}


def prune_official_observed_variants_missing_simc_stats(conn):
    ensure_websim_tables(conn)
    cursor = conn.execute(
        """
        DELETE FROM websim_gear_variants
        WHERE source_type IN ('dungeon', 'raid', 'tier_set')
          AND difficulty_key = 'observed_profile'
          AND status = 'verified'
          AND (
            COALESCE(json_extract(payload_json, '$.statSource'), '') != 'simulationcraft'
            OR COALESCE(json_array_length(json_extract(payload_json, '$.itemStats')), 0) = 0
          )
        """
    )
    return {"officialObservedVariantRowsPrunedMissingStats": max(0, int(cursor.rowcount or 0))}


def promote_official_gear_variants_from_observed(conn):
    ensure_websim_tables(conn)
    partial_rows = conn.execute(
        """
        SELECT v.id, v.item_id, v.slot, v.source_type, v.payload_json, wi.payload_json
        FROM websim_gear_variants v
        LEFT JOIN websim_items wi
          ON wi.id = v.item_id
        WHERE v.status = 'partial'
          AND v.source_type IN ('dungeon', 'raid', 'tier_set')
          AND (v.id LIKE 'loot-partial-%' OR v.id LIKE 'set-partial-%')
        ORDER BY v.item_id, v.slot, v.id
        """
    ).fetchall()
    if not partial_rows:
        return {"promotedVariants": 0, "removedPartialVariants": 0}
    target_item_ids = sorted({str(row[1]) for row in partial_rows if str(row[1] or "").strip()})
    if target_item_ids:
        placeholders = ",".join("?" for _ in target_item_ids)
        conn.execute(
            f"""
            DELETE FROM websim_gear_variants
            WHERE item_id IN ({placeholders})
              AND (id LIKE 'loot-observed-%' OR id LIKE 'set-observed-%')
            """,
            target_item_ids,
        )
    observed_rows = conn.execute(
        """
        SELECT id, item_id, slot, variant_key, label, item_level, simc_options_json, payload_json
        FROM websim_gear_variants
        WHERE source_type = 'observed_profile'
          AND status = 'verified'
          AND item_level > 0
        ORDER BY item_id, item_level DESC, id
        """
    ).fetchall()
    observed_by_item = {}
    for row in observed_rows:
        simc_options = safe_json_loads(row[6], {})
        if not isinstance(simc_options, dict) or not simc_options:
            continue
        observed_by_item.setdefault(str(row[1]), []).append(
            {
                "id": str(row[0]),
                "itemId": str(row[1]),
                "slot": normalize_slot(row[2]),
                "variantKey": str(row[3] or ""),
                "label": str(row[4] or ""),
                "itemLevel": int(row[5] or 0),
                "simcOptions": {
                    key: normalize_option_value(value)
                    for key, value in simc_options.items()
                    if key in SIMC_GEAR_OPTION_KEYS and normalize_option_value(value)
                },
                "payload": safe_json_loads(row[7], {}),
            }
        )

    promoted = 0
    removed_partial_ids = []
    for partial_id, item_id, raw_slot, source_type, payload_json, item_payload_json in partial_rows:
        item_id = str(item_id)
        source_type = str(source_type or "")
        source_slot = normalize_slot(raw_slot)
        item_payload = safe_json_loads(item_payload_json, {})
        item_payload = item_payload if isinstance(item_payload, dict) else {}
        matches = [
            observed
            for observed in observed_by_item.get(item_id, [])
            if gear_variant_slots_are_compatible_for_item(item_payload, source_slot, observed.get("slot"))
        ]
        if not matches:
            continue
        partial_payload = safe_json_loads(payload_json, {})
        partial_payload = partial_payload if isinstance(partial_payload, dict) else {}
        promoted_for_partial = 0
        for observed in matches:
            simc_options = observed.get("simcOptions") or {}
            if not simc_options:
                continue
            observed_payload = observed.get("payload") if isinstance(observed.get("payload"), dict) else {}
            observed_class_keys, observed_spec_keys = class_spec_context_from_payload(observed_payload)
            observed_stat_payload = observed_variant_stat_payload_fields(observed_payload)
            if not observed_stat_payload:
                continue
            digest = hashlib.sha1(
                json.dumps(
                    [partial_id, observed.get("id"), observed.get("itemLevel"), simc_options],
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()[:10]
            prefix = "set-observed" if source_type == "tier_set" else "loot-observed"
            upsert_gear_variant(
                conn,
                {
                    "id": f"{prefix}-{item_id}-{source_slot or observed.get('slot') or 'slot'}-{digest}",
                    "itemId": item_id,
                    "slot": source_slot or observed.get("slot") or "",
                    "variantKey": f"observed-{observed.get('itemLevel') or 'unknown'}-{digest}",
                    "label": observed.get("label") or f"Observed {observed.get('itemLevel') or 'unknown'}",
                    "sourceType": source_type,
                    "difficultyKey": "observed_profile",
                    "itemLevel": observed.get("itemLevel") or 0,
                    "simcOptions": simc_options,
                    "status": "verified",
                    "blockers": [],
                    "payload": {
                        **partial_payload,
                        **observed_stat_payload,
                        "officialVariantSource": source_type,
                        "observedVariantSource": "observed_profile",
                        "observedVariantId": observed.get("id") or "",
                        "observedProfileRefs": observed_payload.get("observedProfileRefs") or [],
                        "observedClassKeys": observed_class_keys,
                        "observedSpecKeys": observed_spec_keys,
                    },
                },
            )
            promoted += 1
            promoted_for_partial += 1
        if promoted_for_partial:
            removed_partial_ids.append(str(partial_id))
    if removed_partial_ids:
        placeholders = ",".join("?" for _ in removed_partial_ids)
        conn.execute(f"DELETE FROM websim_gear_variants WHERE id IN ({placeholders})", removed_partial_ids)
    conn.commit()
    return {"promotedVariants": promoted, "removedPartialVariants": len(removed_partial_ids)}


def promote_official_gear_variants_from_battle_net_preview(conn):
    ensure_websim_tables(conn)
    conn.execute(
        """
        DELETE FROM websim_gear_variants
        WHERE id LIKE 'loot-preview-%'
           OR id LIKE 'set-preview-%'
        """
    )
    partial_rows = conn.execute(
        """
        SELECT v.id, v.item_id, v.slot, v.source_type, v.payload_json, i.payload_json
        FROM websim_gear_variants v
        JOIN websim_items i ON i.id = v.item_id
        WHERE v.status = 'partial'
          AND v.source_type IN ('dungeon', 'raid', 'tier_set')
          AND (v.id LIKE 'loot-partial-%' OR v.id LIKE 'set-partial-%')
        ORDER BY v.item_id, v.slot, v.id
        """
    ).fetchall()
    promoted = 0
    removed_partial_ids = []
    for partial_id, item_id, raw_slot, source_type, partial_payload_json, metadata_payload_json in partial_rows:
        item_id = str(item_id)
        source_type = str(source_type or "")
        source_slot = normalize_slot(raw_slot)
        metadata_payload = safe_json_loads(metadata_payload_json, {})
        preview_variant = battle_net_preview_variant_from_metadata(metadata_payload, source_type)
        if not preview_variant:
            continue
        partial_payload = safe_json_loads(partial_payload_json, {})
        partial_payload = partial_payload if isinstance(partial_payload, dict) else {}
        simc_options = preview_variant.get("simcOptions") or {}
        digest = hashlib.sha1(
            json.dumps(
                [
                    partial_id,
                    item_id,
                    source_slot,
                    source_type,
                    preview_variant.get("itemLevel"),
                    simc_options,
                    preview_variant.get("simcIlevelOnly"),
                ],
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:10]
        prefix = "set-preview" if source_type == "tier_set" else "loot-preview"
        upsert_gear_variant(
            conn,
            {
                "id": f"{prefix}-{item_id}-{source_slot or 'slot'}-{digest}",
                "itemId": item_id,
                "slot": source_slot or "",
                "variantKey": f"battle-net-preview-{preview_variant.get('itemLevel')}-{digest}",
                "label": f"Battle.net preview {preview_variant.get('itemLevel')}",
                "sourceType": source_type,
                "difficultyKey": "battle_net_preview",
                "itemLevel": preview_variant.get("itemLevel") or 0,
                "simcOptions": simc_options,
                "status": "verified",
                "blockers": [],
                "payload": {
                    **partial_payload,
                    "officialVariantSource": source_type,
                    "previewVariantSource": "battle_net_preview",
                    "previewItemLevel": preview_variant.get("itemLevel") or 0,
                    "previewBonusList": preview_variant.get("bonusIds") or [],
                    "simcIlevelOnly": bool(preview_variant.get("simcIlevelOnly")),
                    "metadataSource": ITEM_METADATA_SOURCE,
                },
            },
        )
        promoted += 1
        removed_partial_ids.append(str(partial_id))
    if removed_partial_ids:
        placeholders = ",".join("?" for _ in removed_partial_ids)
        conn.execute(f"DELETE FROM websim_gear_variants WHERE id IN ({placeholders})", removed_partial_ids)
    conn.commit()
    return {"promotedVariants": promoted, "removedPartialVariants": len(removed_partial_ids)}


def sync_websim_gear_mod_options(conn):
    conn.execute(
        """
        DELETE FROM websim_gear_mod_options
        WHERE id LIKE 'seed-%'
           OR id LIKE 'observed-socket-%'
           OR id LIKE 'observed-enchant-%'
           OR id LIKE 'observed-embellishment-%'
        """
    )
    count = 0
    for option in [
        *gear_mod_seed(),
        *observed_variant_socket_mod_options(conn),
        *observed_variant_enchant_mod_options(conn),
        *observed_variant_embellishment_mod_options(conn),
    ]:
        if isinstance(option, dict) and upsert_gear_mod_option(conn, option):
            count += 1
    return count


def gem_item_ids_from_simc_options(simc_options):
    if not isinstance(simc_options, dict):
        return []
    raw_gem_ids = normalize_option_value(simc_options.get("gem_id"))
    if not raw_gem_ids:
        return []
    result = []
    for value in raw_gem_ids.split("/"):
        value = value.strip()
        if value and re.fullmatch(r"\d+", value) and value not in result:
            result.append(value)
    return result


def enchant_ids_from_gear_mod_options(conn):
    ensure_websim_tables(conn)
    rows = conn.execute(
        """
        SELECT simc_options_json
        FROM websim_gear_mod_options
        WHERE option_type = 'enchant'
          AND status = 'verified'
        """
    ).fetchall()
    ids = []
    for (simc_options_json,) in rows:
        simc_options = safe_json_loads(simc_options_json, {})
        if not isinstance(simc_options, dict):
            continue
        enchant_id = normalize_option_value(simc_options.get("enchant_id"))
        if enchant_id and enchant_id not in ids:
            ids.append(enchant_id)
    return ids


def parse_wago_spell_item_enchantment_names_csv(text, enchant_ids=None):
    desired = {str(value or "").strip() for value in (enchant_ids or []) if str(value or "").strip()}
    result = {}
    if not str(text or "").strip():
        return result
    reader = csv.DictReader(io.StringIO(str(text or "")))
    for row in reader:
        row = row if isinstance(row, dict) else {}
        raw_id = str(row.get("ID") or row.get("Id") or row.get("id") or "").strip()
        if not raw_id or (desired and raw_id not in desired):
            continue
        display_name = ""
        for key in (
            "Name_lang",
            "Name",
            "name_lang",
            "name",
            "Description_lang",
            "Description",
            "EffectName_lang",
            "EffectName",
        ):
            candidate = clean_gear_mod_display_label(row.get(key), "enchant")
            if candidate and text_contains_cjk(candidate) and not display_label_looks_like_raw_id(candidate, "enchant"):
                display_name = candidate
                break
        if display_name:
            result[raw_id] = display_name
    return result


def sync_wago_gear_mod_option_display_names(conn, simc_text_or_build="", locale=DEFAULT_LOCALE):
    ensure_websim_tables(conn)
    build = simc_build_from_text(simc_text_or_build) or str(simc_text_or_build or "").strip()
    enchant_ids = enchant_ids_from_gear_mod_options(conn)
    counts = {"updated": 0, "missing": 0, "source": "", "errors": []}
    if not enchant_ids:
        return counts
    if not build:
        counts["missing"] = len(enchant_ids)
        counts["errors"].append("missing SimulationCraft build for Wago SpellItemEnchantment sync")
        return counts
    try:
        text, source = download_wago_db2_csv("SpellItemEnchantment", build, locale)
        counts["source"] = source
    except Exception as error:
        counts["missing"] = len(enchant_ids)
        counts["errors"].append(str(error))
        return counts
    names_by_id = parse_wago_spell_item_enchantment_names_csv(text, enchant_ids)
    rows = conn.execute(
        """
        SELECT id, name, simc_options_json, payload_json
        FROM websim_gear_mod_options
        WHERE option_type = 'enchant'
          AND status = 'verified'
        ORDER BY id
        """
    ).fetchall()
    found_ids = set()
    removed_option_ids = []
    removed_enchant_ids = set()
    for option_id, option_name, simc_options_json, payload_json in rows:
        simc_options = safe_json_loads(simc_options_json, {})
        if not isinstance(simc_options, dict):
            continue
        enchant_id = normalize_option_value(simc_options.get("enchant_id"))
        display_name = names_by_id.get(enchant_id)
        evidence_source = "wago_db2_spell_item_enchantment"
        evidence_ref = source
        if not display_name and enchant_id in GEAR_ENCHANT_LABELS_ZH:
            display_name = GEAR_ENCHANT_LABELS_ZH[enchant_id]
            evidence_source = "server_curated_enchant_label"
            evidence_ref = ""
        if not display_name:
            payload = safe_json_loads(payload_json, {})
            payload = payload if isinstance(payload, dict) else {}
            if str(option_id or "").startswith("observed-enchant-") and payload.get("source") == "observed_variant":
                removed_option_ids.append(str(option_id))
                if enchant_id:
                    removed_enchant_ids.add(enchant_id)
            continue
        payload = safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        payload.update(
            {
                "displayName": display_name,
                "displayLabel": display_name,
                "displayKind": "name",
                "displayStatus": "verified",
                "evidenceSource": evidence_source,
                "evidenceRef": evidence_ref,
                "metadataLocale": locale,
            }
        )
        conn.execute(
            """
            UPDATE websim_gear_mod_options
            SET name = ?, payload_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                display_name[:160],
                json.dumps(payload, ensure_ascii=False),
                utc_now(),
                option_id,
            ),
        )
        found_ids.add(enchant_id)
        counts["updated"] += 1
    if removed_option_ids:
        placeholders = ",".join("?" for _ in removed_option_ids)
        conn.execute(f"DELETE FROM websim_gear_mod_options WHERE id IN ({placeholders})", removed_option_ids)
    counts["removed"] = len(removed_option_ids)
    counts["missing"] = len(
        [
            enchant_id
            for enchant_id in enchant_ids
            if enchant_id not in found_ids and enchant_id not in removed_enchant_ids
        ]
    )
    conn.commit()
    return counts


def sync_blizzard_gear_mod_option_metadata(conn, token, region=DEFAULT_REGION, locale=DEFAULT_LOCALE):
    ensure_websim_tables(conn)
    rows = conn.execute(
        """
        SELECT id, name, simc_options_json, payload_json
        FROM websim_gear_mod_options
        WHERE option_type = 'socket'
        ORDER BY id
        """
    ).fetchall()
    counts = {"items": 0, "skipped": 0, "options": 0, "errors": []}
    metadata_cache = {}
    for option_id, option_name, simc_options_json, payload_json in rows:
        simc_options = safe_json_loads(simc_options_json, {})
        gem_item_ids = gem_item_ids_from_simc_options(simc_options)
        if not gem_item_ids:
            continue
        gem_items = []
        for gem_id in gem_item_ids:
            saved = metadata_cache.get(gem_id)
            if not saved:
                existing = existing_websim_item_metadata(conn, gem_id)
                if websim_item_metadata_is_complete(existing):
                    saved = existing
                    counts["skipped"] += 1
                else:
                    try:
                        item_metadata = fetch_blizzard_item_metadata(
                            token,
                            gem_id,
                            region,
                            locale,
                            fallback_name=option_name or f"Gem {gem_id}",
                        )
                        saved = save_websim_item_metadata(
                            conn,
                            gem_id,
                            item_metadata.get("payload") or {},
                            item_metadata.get("media") or {},
                            fallback_name=item_metadata.get("fallbackName") or option_name or f"Gem {gem_id}",
                            english_payload=item_metadata.get("englishPayload") or {},
                            locale=item_metadata.get("locale") or locale,
                        )
                        if saved:
                            counts["items"] += 1
                    except Exception as error:
                        counts["errors"].append(f"{gem_id}: {error}")
                        continue
                if not saved:
                    counts["errors"].append(f"{gem_id}: Battle.net item metadata unavailable")
                    continue
                metadata_cache[gem_id] = saved
            gem_items.append(
                {
                    "itemId": saved.get("itemId") or gem_id,
                    "displayName": saved.get("displayName") or f"Gem {gem_id}",
                    "iconUrl": saved.get("iconUrl") or "",
                    "quality": saved.get("quality") or "",
                    "gameAsset": saved.get("gameAsset") or {},
                    "metadataStatus": saved.get("metadataStatus") or "verified",
                    "metadataSource": saved.get("metadataSource") or ITEM_METADATA_SOURCE,
                    "metadataLocale": saved.get("metadataLocale") or locale,
                }
            )
        if len(gem_items) != len(gem_item_ids):
            continue

        payload = safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        enriched_payload = dict(payload)
        display_name = " / ".join(
            str(item.get("displayName") or f"Gem {item.get('itemId') or ''}").strip()
            for item in gem_items
            if str(item.get("itemId") or "").strip()
        ) or option_name or f"Gem {gem_item_ids[0]}"
        primary_gem = gem_items[0]
        enriched_payload.update(
            {
                "gemItemId": gem_item_ids[0],
                "gemItemIds": gem_item_ids,
                "gemItems": gem_items,
                "displayName": display_name,
                "iconUrl": primary_gem.get("iconUrl") or "",
                "quality": primary_gem.get("quality") or "",
                "gameAsset": primary_gem.get("gameAsset") or {},
                "metadataStatus": "verified",
                "metadataSource": ITEM_METADATA_SOURCE,
                "metadataLocale": primary_gem.get("metadataLocale") or locale,
            }
        )
        conn.execute(
            """
            UPDATE websim_gear_mod_options
            SET name = ?, payload_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                str(enriched_payload["displayName"])[:160],
                json.dumps(enriched_payload, ensure_ascii=False),
                utc_now(),
                option_id,
            ),
        )
        counts["options"] += 1
    return counts


def governed_crafted_payload(payload):
    payload = payload if isinstance(payload, dict) else {}
    if payload.get("derivedVariantSource") == CRAFTED_ITEM_LEVEL_PROBE_SOURCE:
        return True
    if payload.get("profession") or payload.get("recipeId") or payload.get("recipe_id"):
        return True
    if payload.get("sourceRefs") or payload.get("trackEvidence") or payload.get("craftedStatKey"):
        return True
    return False


def delete_ungoverned_crafted_catalog_rows(conn):
    removed = {"sources": 0, "variants": 0}
    source_rows = conn.execute(
        """
        SELECT id, payload_json
        FROM websim_gear_sources
        WHERE source_type = 'crafted' OR id LIKE 'crafted-%'
        """
    ).fetchall()
    source_ids = [
        row_id
        for row_id, payload_json in source_rows
        if not governed_crafted_payload(safe_json_loads(payload_json, {}))
    ]
    if source_ids:
        placeholders = ",".join("?" for _ in source_ids)
        result = conn.execute(f"DELETE FROM websim_gear_sources WHERE id IN ({placeholders})", source_ids)
        removed["sources"] = result.rowcount if result.rowcount and result.rowcount > 0 else len(source_ids)
    variant_rows = conn.execute(
        """
        SELECT id, payload_json
        FROM websim_gear_variants
        WHERE source_type = 'crafted' OR id LIKE 'crafted-%'
        """
    ).fetchall()
    variant_ids = [
        row_id
        for row_id, payload_json in variant_rows
        if not governed_crafted_payload(safe_json_loads(payload_json, {}))
    ]
    if variant_ids:
        placeholders = ",".join("?" for _ in variant_ids)
        result = conn.execute(f"DELETE FROM websim_gear_variants WHERE id IN ({placeholders})", variant_ids)
        removed["variants"] = result.rowcount if result.rowcount and result.rowcount > 0 else len(variant_ids)
    return removed


def sync_websim_gear_catalog(conn, season=None):
    ensure_websim_tables(conn)
    season = season or get_active_season_payload(conn)
    season_revision = season.get("seasonRevision") or season.get("revision") or ""
    delete_ungoverned_crafted_catalog_rows(conn)
    conn.execute("DELETE FROM websim_gear_sources WHERE id LIKE 'loot-%'")
    conn.execute(
        """
        DELETE FROM websim_gear_variants
        WHERE id LIKE 'loot-partial-%'
           OR id LIKE 'loot-observed-%'
           OR id LIKE 'loot-preview-%'
        """
    )
    rows = conn.execute(
        """
        SELECT l.id, l.item_id, l.slot, l.name, l.instance_id, COALESCE(i.name, ''),
               COALESCE(i.category, ''), l.encounter_id, COALESCE(e.name, '')
        FROM websim_loot l
        LEFT JOIN websim_instances i ON i.id = l.instance_id
        LEFT JOIN websim_encounters e ON e.id = l.encounter_id
        ORDER BY i.name, e.name, l.name
        """
    ).fetchall()
    for row in rows:
        source_type = "raid" if str(row[6]).lower() == "raid" else "dungeon"
        label = " - ".join([part for part in [row[8], row[5]] if part]) or row[3] or "Official loot"
        source_payload = current_season_loot_source_payload(source_type, row[4], row[1], row[6])
        if not gear_source_active_for_replacement(
            {"sourceType": source_type, "instanceId": row[4], "sourceLabel": label, "payload": source_payload},
            season,
        ):
            continue
        upsert_gear_source(
            conn,
            {
                "id": f"loot-{row[0]}",
                "itemId": row[1],
                "sourceType": source_type,
                "sourceLabel": label,
                "instanceId": row[4],
                "encounterId": row[7],
                "seasonRevision": season_revision,
                "payload": source_payload,
            },
        )
        upsert_gear_variant(
            conn,
            {
                "id": f"loot-partial-{row[1]}-{normalize_slot(row[2]) or 'slot'}",
                "itemId": row[1],
                "slot": row[2],
                "variantKey": "needs-variant",
                "label": "难度 / 装等待补",
                "sourceType": source_type,
                "difficultyKey": "needs-variant",
                "itemLevel": 0,
                "simcOptions": {},
                "status": "partial",
                "blockers": ["missing deterministic SimC variant preset"],
                "payload": {**source_payload, "seasonRevision": season_revision},
                    },
                )
    observed_counts = {
        "observedSources": 0,
        "observedVariants": 0,
        "verifiedObservedVariants": 0,
        "partialObservedVariants": 0,
        "blockedObservedVariants": 0,
        "skipped": 0,
    }
    try:
        try:
            from .raiderio_payload import get_raiderio_payload
        except ImportError:
            from raiderio_payload import get_raiderio_payload

        observed_counts = sync_observed_gear_variants(conn, get_raiderio_payload(conn, allow_sync=False), season)
    except Exception as error:
        observed_counts["errors"] = [str(error)]
    observed_counts["profilePresetObservedVariantStats"] = sync_observed_variant_stats_from_profile_presets(conn)
    observed_counts["sameItemLevelObservedVariantStats"] = sync_observed_variant_stats_from_same_item_level_siblings(conn)
    observed_counts["officialVariantPromotion"] = promote_official_gear_variants_from_observed(conn)
    observed_counts["officialObservedVariantRefresh"] = refresh_official_observed_variant_payloads_from_observed(conn)
    observed_counts["battleNetPreviewVariantPromotion"] = promote_official_gear_variants_from_battle_net_preview(conn)
    observed_counts["modOptions"] = sync_websim_gear_mod_options(conn)
    state = build_gear_catalog_sync_state(conn, season)
    state["observedSync"] = observed_counts
    set_sync_state(conn, "gearCatalog", state)
    return state


def gear_catalog_refresh_reason(state):
    if os.environ.get("WOW_WEBSIM_REFRESH_GEAR_CATALOG_ALWAYS", "0").strip() == "1":
        return "forced-gear-catalog-refresh"
    if not isinstance(state, dict) or not state:
        return "missing-gear-catalog"
    if not int(state.get("itemCount") or 0):
        return "empty-gear-catalog"
    if not int(state.get("sourceCount") or 0):
        return "missing-gear-sources"
    if not int(state.get("variantCount") or 0):
        return "missing-gear-variants"
    data_readiness = state.get("dataReadiness") if isinstance(state.get("dataReadiness"), dict) else {}
    data_status = str(data_readiness.get("status") or "").strip()
    if data_status:
        if data_status != "verified":
            substatuses = {
                key: str(data_readiness.get(key) or "").strip()
                for key in ("metadataStatus", "sourceStatus", "modOptionStatus")
            }
            if any(substatuses.values()):
                for key in ("metadataStatus", "sourceStatus"):
                    substatus = substatuses.get(key) or ""
                    if (
                        key == "sourceStatus"
                        and substatus
                        and substatus != "verified"
                        and str(data_readiness.get("seasonSourceStatus") or "").strip() == "verified"
                    ):
                        continue
                    if substatus and substatus != "verified":
                        return f"{substatus}-{key}"
                if data_status == "partial":
                    return ""
            return f"{data_status}-gear-data"
        for key in ("metadataStatus", "sourceStatus", "modOptionStatus"):
            substatus = str(data_readiness.get(key) or "").strip()
            if substatus and substatus != "verified":
                return f"{substatus}-{key}"
        return ""
    status = str(state.get("status") or "").strip()
    if status in {"partial", "blocked", "stale", "missing_credentials"}:
        return f"{status}-gear-catalog"
    if int(state.get("partialCount") or 0) or int(state.get("blockedCount") or 0):
        return "incomplete-gear-variants"
    return ""


def sync_websim_cache(db_path, include_blizzard=True, stage_callback=None):
    require_sqlite_runtime_enabled("websim_payload.sync_websim_cache")
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    stages = []
    try:
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")
        ensure_websim_tables(conn)
        simc_stage_started = emit_sync_stage(stages, stage_callback, "simc", "start")
        simc_counts = sync_simc_generated_data(conn)
        emit_sync_stage(
            stages,
            stage_callback,
            "simc",
            "complete",
            simc_stage_started,
            {
                "talents": simc_counts.get("talents") or 0,
                "profiles": simc_counts.get("profiles") or 0,
                "build": simc_counts.get("build") or "",
            },
        )
        conn.commit()
        simc_season = get_active_season_payload(conn)
        initial_gear_catalog = build_gear_catalog_sync_state(conn, simc_season)
        set_sync_state(conn, "gearCatalog", initial_gear_catalog)
        simc_talent_health = {
            "schemaRevision": TALENT_SCHEMA_REVISION,
            "simcBuild": simc_counts.get("build") or "",
            "traitEdgeSource": simc_counts.get("traitEdgeSource") or "",
            "officialRevision": "",
            "diffStatus": "pending_official_audit" if simc_counts.get("talents") else "blocked",
            "checkedAt": utc_now(),
        }
        set_sync_state(
            conn,
            "websim_sync",
            {
                "ok": False,
                "stage": "simc",
                "checkedAt": utc_now(),
                "region": DEFAULT_REGION,
                "locale": DEFAULT_LOCALE,
                "simc": simc_counts,
                "blizzard": {"instances": 0, "encounters": 0, "loot": 0, "items": 0},
                "itemSets": {
                    "itemSets": 0,
                    "setItems": 0,
                    "itemMetadata": 0,
                    "sources": 0,
                    "variants": 0,
                    "skipped": 0,
                    "errors": [],
                },
                "itemMetadata": {
                    "items": 0,
                    "aliases": 0,
                    "skipped": 0,
                    "searched": 0,
                    "resolved": 0,
                    "references": 0,
                    "errors": [],
                },
                "gearModOptions": {"items": 0, "skipped": 0, "options": 0, "errors": []},
                "gearModDisplayNames": {"updated": 0, "missing": 0, "source": "", "errors": []},
                "spells": {"spells": 0, "media": 0},
                "gearCatalog": initial_gear_catalog,
                "currentSeason": simc_season,
                "dataStatus": simc_season.get("dataStatus") or "blocked",
                "seasonRevision": simc_season.get("seasonRevision") or "",
                "talentSchemaRevision": TALENT_SCHEMA_REVISION,
                "talentHealth": simc_talent_health,
                "stages": list(stages),
                "errors": [],
            },
        )
        conn.commit()
        blizzard_counts = {"instances": 0, "encounters": 0, "loot": 0, "items": 0}
        item_set_counts = {
            "itemSets": 0,
            "setItems": 0,
            "itemMetadata": 0,
            "sources": 0,
            "variants": 0,
            "skipped": 0,
            "errors": [],
        }
        item_metadata_counts = {
            "items": 0,
            "aliases": 0,
            "skipped": 0,
            "searched": 0,
            "resolved": 0,
            "references": 0,
            "errors": [],
        }
        gear_mod_option_counts = {"items": 0, "skipped": 0, "options": 0, "errors": []}
        gear_mod_display_name_counts = {"updated": 0, "missing": 0, "source": "", "errors": []}
        spell_counts = {"spells": 0, "media": 0}
        errors = []
        blizzard_skipped = ""
        blizzard_token = ""
        if include_blizzard:
            blizzard_stage_started = emit_sync_stage(stages, stage_callback, "blizzard", "start")
            refresh_always = os.environ.get("WOW_WEBSIM_REFRESH_BLIZZARD_ALWAYS", "0").strip() == "1"
            gear_refresh_reason = gear_catalog_refresh_reason(initial_gear_catalog)
            if simc_season.get("dataStatus") == "verified" and not refresh_always and not gear_refresh_reason:
                blizzard_skipped = "fresh-season-cache"
                if (
                    os.environ.get("WOW_WEBSIM_SYNC_ITEM_METADATA_ON_FRESH", "1").strip() != "0"
                    and blizzard_credentials_configured()
                ):
                    try:
                        token = get_blizzard_access_token(DEFAULT_REGION)
                        blizzard_token = token
                        preset_metadata_stage_started = emit_sync_stage(
                            stages,
                            stage_callback,
                            "blizzard_preset_item_metadata",
                            "start",
                        )
                        preset_metadata_counts = sync_blizzard_preset_item_metadata(
                            conn,
                            token,
                            DEFAULT_REGION,
                            DEFAULT_LOCALE,
                        )
                        emit_sync_stage(
                            stages,
                            stage_callback,
                            "blizzard_preset_item_metadata",
                            "complete",
                            preset_metadata_stage_started,
                            {
                                "items": preset_metadata_counts.get("items") or 0,
                                "aliases": preset_metadata_counts.get("aliases") or 0,
                                "skipped": preset_metadata_counts.get("skipped") or 0,
                                "errors": len(preset_metadata_counts.get("errors") or []),
                            },
                        )
                        build_metadata_stage_started = emit_sync_stage(
                            stages,
                            stage_callback,
                            "blizzard_build_gear_item_metadata",
                            "start",
                        )
                        build_metadata_counts = sync_blizzard_build_gear_item_metadata(
                            conn,
                            token,
                            DEFAULT_REGION,
                            DEFAULT_LOCALE,
                        )
                        emit_sync_stage(
                            stages,
                            stage_callback,
                            "blizzard_build_gear_item_metadata",
                            "complete",
                            build_metadata_stage_started,
                            {
                                "items": build_metadata_counts.get("items") or 0,
                                "searched": build_metadata_counts.get("searched") or 0,
                                "resolved": build_metadata_counts.get("resolved") or 0,
                                "skipped": build_metadata_counts.get("skipped") or 0,
                                "errors": len(build_metadata_counts.get("errors") or []),
                            },
                        )
                        observed_metadata_stage_started = emit_sync_stage(
                            stages,
                            stage_callback,
                            "blizzard_observed_item_metadata",
                            "start",
                        )
                        observed_metadata_counts = sync_blizzard_observed_item_metadata(
                            conn,
                            token,
                            DEFAULT_REGION,
                            DEFAULT_LOCALE,
                        )
                        emit_sync_stage(
                            stages,
                            stage_callback,
                            "blizzard_observed_item_metadata",
                            "complete",
                            observed_metadata_stage_started,
                            {
                                "items": observed_metadata_counts.get("items") or 0,
                                "skipped": observed_metadata_counts.get("skipped") or 0,
                                "errors": len(observed_metadata_counts.get("errors") or []),
                            },
                        )
                        item_metadata_counts = merge_item_metadata_counts(
                            preset_metadata_counts,
                            build_metadata_counts,
                            observed_metadata_counts,
                        )
                    except Exception as error:
                        item_metadata_counts["errors"].append(str(error))
            else:
                try:
                    token = get_blizzard_access_token(DEFAULT_REGION)
                    blizzard_token = token
                    journal_stage_started = emit_sync_stage(stages, stage_callback, "blizzard_journal", "start")
                    blizzard_counts = sync_blizzard_journal(conn, token, DEFAULT_REGION, DEFAULT_LOCALE)
                    emit_sync_stage(
                        stages,
                        stage_callback,
                        "blizzard_journal",
                        "complete",
                        journal_stage_started,
                        {
                            "instances": blizzard_counts.get("instances") or 0,
                            "encounters": blizzard_counts.get("encounters") or 0,
                            "loot": blizzard_counts.get("loot") or 0,
                            "items": blizzard_counts.get("items") or 0,
                            "blockers": len(blizzard_counts.get("blockers") or []),
                            "truncated": bool(blizzard_counts.get("truncated")),
                        },
                    )
                    errors.extend(blizzard_counts.get("blockers") or [])
                    item_sets_stage_started = emit_sync_stage(stages, stage_callback, "blizzard_item_sets", "start")
                    item_set_counts = sync_blizzard_item_sets(
                        conn,
                        token,
                        DEFAULT_REGION,
                        DEFAULT_LOCALE,
                        get_active_season_payload(conn),
                    )
                    emit_sync_stage(
                        stages,
                        stage_callback,
                        "blizzard_item_sets",
                        "complete",
                        item_sets_stage_started,
                        {
                            "itemSets": item_set_counts.get("itemSets") or 0,
                            "setItems": item_set_counts.get("setItems") or 0,
                            "itemMetadata": item_set_counts.get("itemMetadata") or 0,
                            "sources": item_set_counts.get("sources") or 0,
                            "variants": item_set_counts.get("variants") or 0,
                            "skipped": item_set_counts.get("skipped") or 0,
                            "errors": len(item_set_counts.get("errors") or []),
                        },
                    )
                    errors.extend(item_set_counts.get("errors") or [])
                    preset_metadata_stage_started = emit_sync_stage(
                        stages,
                        stage_callback,
                        "blizzard_preset_item_metadata",
                        "start",
                    )
                    preset_metadata_counts = sync_blizzard_preset_item_metadata(
                        conn,
                        token,
                        DEFAULT_REGION,
                        DEFAULT_LOCALE,
                    )
                    emit_sync_stage(
                        stages,
                        stage_callback,
                        "blizzard_preset_item_metadata",
                        "complete",
                        preset_metadata_stage_started,
                        {
                            "items": preset_metadata_counts.get("items") or 0,
                            "aliases": preset_metadata_counts.get("aliases") or 0,
                            "skipped": preset_metadata_counts.get("skipped") or 0,
                            "errors": len(preset_metadata_counts.get("errors") or []),
                        },
                    )
                    build_metadata_stage_started = emit_sync_stage(
                        stages,
                        stage_callback,
                        "blizzard_build_gear_item_metadata",
                        "start",
                    )
                    build_metadata_counts = sync_blizzard_build_gear_item_metadata(
                        conn,
                        token,
                        DEFAULT_REGION,
                        DEFAULT_LOCALE,
                    )
                    emit_sync_stage(
                        stages,
                        stage_callback,
                        "blizzard_build_gear_item_metadata",
                        "complete",
                        build_metadata_stage_started,
                        {
                            "items": build_metadata_counts.get("items") or 0,
                            "searched": build_metadata_counts.get("searched") or 0,
                            "resolved": build_metadata_counts.get("resolved") or 0,
                            "skipped": build_metadata_counts.get("skipped") or 0,
                            "errors": len(build_metadata_counts.get("errors") or []),
                        },
                    )
                    item_metadata_counts = merge_item_metadata_counts(
                        preset_metadata_counts,
                        build_metadata_counts,
                    )
                    spell_stage_started = emit_sync_stage(stages, stage_callback, "blizzard_spell_details", "start")
                    spell_counts = sync_blizzard_spell_details(conn, token, DEFAULT_REGION, DEFAULT_LOCALE)
                    emit_sync_stage(
                        stages,
                        stage_callback,
                        "blizzard_spell_details",
                        "complete",
                        spell_stage_started,
                        {
                            "spells": spell_counts.get("spells") or 0,
                            "media": spell_counts.get("media") or 0,
                            "skipped": spell_counts.get("skipped") or 0,
                        },
                    )
                except Exception as error:
                    errors.append(str(error))
            emit_sync_stage(
                stages,
                stage_callback,
                "blizzard",
                "complete",
                blizzard_stage_started,
                {
                    "skipped": blizzard_skipped,
                    "errors": len(errors),
                    "loot": blizzard_counts.get("loot") or 0,
                    "items": blizzard_counts.get("items") or 0,
                    "itemSets": item_set_counts.get("itemSets") or 0,
                },
            )
        active_season = get_active_season_payload(conn)
        gear_stage_started = emit_sync_stage(stages, stage_callback, "gear_catalog", "start")
        gear_catalog_state = sync_websim_gear_catalog(conn, active_season)
        emit_sync_stage(
            stages,
            stage_callback,
            "gear_catalog",
            "complete",
            gear_stage_started,
            {
                "gearCatalogStatus": gear_catalog_state.get("status") or "",
                "itemCount": gear_catalog_state.get("itemCount") or 0,
                "sourceCount": gear_catalog_state.get("sourceCount") or 0,
                "variantCount": gear_catalog_state.get("variantCount") or 0,
                "verifiedCount": gear_catalog_state.get("verifiedCount") or 0,
                "partialCount": gear_catalog_state.get("partialCount") or 0,
            },
        )
        try:
            display_name_stage_started = emit_sync_stage(
                stages,
                stage_callback,
                "gear_mod_option_display_names",
                "start",
            )
            gear_mod_display_name_counts = sync_wago_gear_mod_option_display_names(
                conn,
                simc_counts.get("build") or "",
                DEFAULT_LOCALE,
            )
            emit_sync_stage(
                stages,
                stage_callback,
                "gear_mod_option_display_names",
                "complete",
                display_name_stage_started,
                {
                    "updated": gear_mod_display_name_counts.get("updated") or 0,
                    "missing": gear_mod_display_name_counts.get("missing") or 0,
                    "errors": len(gear_mod_display_name_counts.get("errors") or []),
                },
            )
            observed_sync = gear_catalog_state.get("observedSync") if isinstance(gear_catalog_state, dict) else {}
            gear_catalog_state = build_gear_catalog_sync_state(conn, active_season)
            if observed_sync:
                gear_catalog_state["observedSync"] = observed_sync
            set_sync_state(conn, "gearCatalog", gear_catalog_state)
        except Exception as error:
            gear_mod_display_name_counts["errors"].append(str(error))
        if include_blizzard and blizzard_token:
            try:
                observed_metadata_stage_started = emit_sync_stage(
                    stages,
                    stage_callback,
                    "observed_item_metadata",
                    "start",
                )
                observed_item_metadata_counts = sync_blizzard_observed_item_metadata(
                    conn,
                    blizzard_token,
                    DEFAULT_REGION,
                    DEFAULT_LOCALE,
                )
                emit_sync_stage(
                    stages,
                    stage_callback,
                    "observed_item_metadata",
                    "complete",
                    observed_metadata_stage_started,
                    {
                        "items": observed_item_metadata_counts.get("items") or 0,
                        "skipped": observed_item_metadata_counts.get("skipped") or 0,
                        "errors": len(observed_item_metadata_counts.get("errors") or []),
                    },
                )
                item_metadata_counts = merge_item_metadata_counts(item_metadata_counts, observed_item_metadata_counts)
                errors.extend(observed_item_metadata_counts.get("errors") or [])
            except Exception as error:
                message = str(error)
                item_metadata_counts["errors"].append(message)
                errors.append(message)
            try:
                gear_mod_stage_started = emit_sync_stage(
                    stages,
                    stage_callback,
                    "gear_mod_option_metadata",
                    "start",
                )
                gear_mod_option_counts = sync_blizzard_gear_mod_option_metadata(
                    conn,
                    blizzard_token,
                    DEFAULT_REGION,
                    DEFAULT_LOCALE,
                )
                emit_sync_stage(
                    stages,
                    stage_callback,
                    "gear_mod_option_metadata",
                    "complete",
                    gear_mod_stage_started,
                    {
                        "items": gear_mod_option_counts.get("items") or 0,
                        "options": gear_mod_option_counts.get("options") or 0,
                        "skipped": gear_mod_option_counts.get("skipped") or 0,
                        "errors": len(gear_mod_option_counts.get("errors") or []),
                    },
                )
                errors.extend(gear_mod_option_counts.get("errors") or [])
            except Exception as error:
                message = str(error)
                gear_mod_option_counts["errors"].append(message)
                errors.append(message)
            observed_sync = gear_catalog_state.get("observedSync") if isinstance(gear_catalog_state, dict) else {}
            gear_catalog_state = build_gear_catalog_sync_state(conn, active_season)
            if observed_sync:
                gear_catalog_state["observedSync"] = observed_sync
            set_sync_state(conn, "gearCatalog", gear_catalog_state)
        gear_catalog_status = str((gear_catalog_state or {}).get("status") or "").strip()
        gear_catalog_blockers = [
            str(blocker or "").strip()
            for blocker in ((gear_catalog_state or {}).get("blockers") or [])
            if str(blocker or "").strip()
        ]
        if gear_catalog_status != "verified":
            if gear_catalog_blockers:
                errors = unique_text_list([*errors, *gear_catalog_blockers])
            else:
                errors = unique_text_list([*errors, f"gear catalog status is {gear_catalog_status or 'unknown'}"])
        else:
            errors = unique_text_list(errors)
        talent_health = {
            "schemaRevision": TALENT_SCHEMA_REVISION,
            "simcBuild": simc_counts.get("build") or "",
            "traitEdgeSource": simc_counts.get("traitEdgeSource") or "",
            "officialRevision": active_season.get("seasonRevision") or "",
            "diffStatus": "pending_official_audit" if simc_counts.get("talents") else "blocked",
            "checkedAt": utc_now(),
        }
        payload = {
            "ok": not errors and active_season.get("dataStatus") == "verified" and gear_catalog_status == "verified",
            "checkedAt": utc_now(),
            "region": DEFAULT_REGION,
            "locale": DEFAULT_LOCALE,
            "simc": simc_counts,
            "blizzard": blizzard_counts,
            "itemSets": item_set_counts,
            "itemMetadata": item_metadata_counts,
            "gearModOptions": gear_mod_option_counts,
            "gearModDisplayNames": gear_mod_display_name_counts,
            "spells": spell_counts,
            "gearCatalog": gear_catalog_state,
            "currentSeason": active_season,
            "dataStatus": active_season.get("dataStatus") or "blocked",
            "seasonRevision": active_season.get("seasonRevision") or "",
            "talentSchemaRevision": TALENT_SCHEMA_REVISION,
            "talentHealth": talent_health,
            "stages": stages,
            "errors": errors,
        }
        if blizzard_skipped:
            payload["blizzardSkipped"] = blizzard_skipped
        emit_sync_stage(
            stages,
            stage_callback,
            "websim_sync",
            "complete",
            None,
            {"ok": payload["ok"], "errors": len(errors), "gearCatalogStatus": gear_catalog_status},
        )
        payload["stages"] = stages
        set_sync_state(conn, "websim_sync", payload)
        conn.commit()
        return payload
    finally:
        conn.close()


def classes_payload():
    payload = []
    for item in WOW_CLASSES:
        class_key = item["key"]
        class_label = CLASS_LABELS_ZH.get(class_key, item["label"])
        class_icon_url = wow_icon_url(CLASS_ICON_NAMES.get(class_key, "inv_misc_questionmark"))
        class_asset = game_asset_from_icon_url(
            "playable_class",
            class_key,
            "websim-bootstrap-class",
            class_icon_url,
            source="static_icon_name",
            status="fallback",
            semantic_tags=["game", "class", class_key],
            usage=["websim_bootstrap", "talent_simulator"],
            fallback_text=fallback_text_for(class_label),
        )
        specs = []
        for spec in item["specs"]:
            spec_label = SPEC_LABELS_ZH.get(spec, SPEC_LABELS.get(spec, spec.replace("_", " ").title()))
            spec_icon_url = wow_icon_url(SPEC_ICON_NAMES.get(spec, CLASS_ICON_NAMES.get(class_key, "inv_misc_questionmark")))
            spec_asset = game_asset_from_icon_url(
                "playable_spec",
                f"{class_key}:{spec}",
                "websim-bootstrap-spec",
                spec_icon_url,
                source="static_icon_name",
                status="fallback",
                semantic_tags=["game", "class", "spec", class_key, spec],
                usage=["websim_bootstrap", "talent_simulator"],
                fallback_text=fallback_text_for(spec_label),
            )
            specs.append({
                "key": spec,
                "label": spec_label,
                "labelEn": SPEC_LABELS.get(spec, spec.replace("_", " ").title()),
                "iconUrl": spec_icon_url,
                "gameAsset": spec_asset,
                "heroTrees": [hero_tree_payload(hero) for hero in hero_trees_for_spec(class_key, spec)],
            })
        payload.append({
            "key": class_key,
            "label": class_label,
            "labelEn": item["label"],
            "color": CLASS_COLORS.get(class_key, "#f1b94c"),
            "iconUrl": class_icon_url,
            "gameAsset": class_asset,
            "heroTrees": [
                hero_tree_payload(hero)
                for hero in HERO_BY_CLASS.get(class_key, [])
            ],
            "specs": specs,
        })
    return payload


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


def wow_icon_url(icon_name):
    normalized = re.sub(r"[^a-z0-9_]+", "", str(icon_name or "").lower()) or "inv_misc_questionmark"
    return f"https://wow.zamimg.com/images/wow/icons/large/{normalized}.jpg"


def parse_wago_int(value):
    match = re.search(r"-?\d+", str(value or ""))
    return int(match.group(0)) if match else 0


def parse_spell_misc_icon_file_ids_csv(text, spell_ids=None, limit=50000):
    wanted = {int(spell_id) for spell_id in spell_ids or [] if int(spell_id or 0) > 0}
    icon_file_ids = {}
    if not text:
        return icon_file_ids
    try:
        rows = csv.DictReader(io.StringIO(str(text or "")))
        for row in rows:
            spell_id = parse_wago_int(row.get("SpellID"))
            if spell_id <= 0 or (wanted and spell_id not in wanted) or spell_id in icon_file_ids:
                continue
            active_icon = parse_wago_int(row.get("ActiveIconFileDataID"))
            spell_icon = parse_wago_int(row.get("SpellIconFileDataID"))
            icon_file_id = active_icon or spell_icon
            if icon_file_id > 0:
                icon_file_ids[spell_id] = icon_file_id
            if len(icon_file_ids) >= limit:
                break
    except (csv.Error, TypeError, ValueError):
        return {}
    return icon_file_ids


def icon_name_from_manifest_file(file_name):
    name = str(file_name or "").rsplit("\\", 1)[-1].rsplit("/", 1)[-1].strip()
    name = re.sub(r"\.[A-Za-z0-9]+$", "", name)
    return re.sub(r"[^a-z0-9_]+", "", name.lower())


def parse_manifest_interface_icon_names_csv(text, file_data_ids=None, limit=50000):
    wanted = {int(file_id) for file_id in file_data_ids or [] if int(file_id or 0) > 0}
    icon_names = {}
    if not text:
        return icon_names
    try:
        rows = csv.DictReader(io.StringIO(str(text or "")))
        for row in rows:
            file_id = parse_wago_int(row.get("ID"))
            if file_id <= 0 or (wanted and file_id not in wanted) or file_id in icon_names:
                continue
            file_path = str(row.get("FilePath") or "")
            file_name = str(row.get("FileName") or "")
            if "icons" not in file_path.lower() and "icons" not in file_name.lower():
                continue
            icon_name = icon_name_from_manifest_file(file_name)
            if icon_name:
                icon_names[file_id] = icon_name
            if len(icon_names) >= limit:
                break
    except (csv.Error, TypeError, ValueError):
        return {}
    return icon_names


def spell_icon_urls_from_wago_db2(build, spell_ids):
    if not build or not spell_ids:
        return {}, {}
    spell_misc_text, spell_misc_source = download_wago_db2_csv("SpellMisc", build)
    icon_file_ids = parse_spell_misc_icon_file_ids_csv(spell_misc_text, spell_ids)
    if not icon_file_ids:
        return {}, {"spellMisc": spell_misc_source}
    manifest_text, manifest_source = download_wago_db2_csv("ManifestInterfaceData", build)
    icon_names = parse_manifest_interface_icon_names_csv(manifest_text, icon_file_ids.values())
    icon_urls = {
        spell_id: wow_icon_url(icon_names[file_id])
        for spell_id, file_id in icon_file_ids.items()
        if icon_names.get(file_id)
    }
    return icon_urls, {"spellMisc": spell_misc_source, "manifest": manifest_source}


def normalize_wago_spell_text(value):
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return re.sub(r"\n{3,}", "\n\n", text)


def parse_wago_spell_names_csv(text, spell_ids=None, limit=50000):
    wanted = {int(spell_id) for spell_id in spell_ids or [] if int(spell_id or 0) > 0}
    names = {}
    if not text:
        return names
    try:
        rows = csv.DictReader(io.StringIO(str(text or "")))
        for row in rows:
            spell_id = parse_wago_int(row.get("ID"))
            if spell_id <= 0 or (wanted and spell_id not in wanted) or spell_id in names:
                continue
            name = normalize_wago_spell_text(row.get("Name_lang"))
            if name:
                names[spell_id] = name
            if len(names) >= limit:
                break
    except (csv.Error, TypeError, ValueError):
        return {}
    return names


def parse_wago_spell_texts_csv(text, spell_ids=None, limit=50000):
    wanted = {int(spell_id) for spell_id in spell_ids or [] if int(spell_id or 0) > 0}
    details = {}
    if not text:
        return details
    try:
        rows = csv.DictReader(io.StringIO(str(text or "")))
        for row in rows:
            spell_id = parse_wago_int(row.get("ID"))
            if spell_id <= 0 or (wanted and spell_id not in wanted) or spell_id in details:
                continue
            description = normalize_wago_spell_text(row.get("Description_lang"))
            aura = normalize_wago_spell_text(row.get("AuraDescription_lang"))
            if aura and aura not in description:
                description = f"{description}\n\n{aura}".strip()
            details[spell_id] = {
                "description": description,
                "tooltip": aura,
                "rank": normalize_wago_spell_text(row.get("NameSubtext_lang")),
            }
            if len(details) >= limit:
                break
    except (csv.Error, TypeError, ValueError):
        return {}
    return details


def spell_localizations_from_wago_db2(build, spell_ids, locale=DEFAULT_LOCALE):
    if not build or not spell_ids:
        return {}, {}
    if not DEFAULT_WAGO_DB2_LOCALIZATION_ENABLED:
        return {}, {}
    if wago_db2_locale(locale).lower() in {"enus", "en"}:
        return {}, {}
    name_text, name_source = download_wago_db2_csv("SpellName", build, locale)
    names = parse_wago_spell_names_csv(name_text, spell_ids)
    spell_text, spell_source = download_wago_db2_csv("Spell", build, locale)
    texts = parse_wago_spell_texts_csv(spell_text, spell_ids)
    localized = {}
    for spell_id in sorted({*names.keys(), *texts.keys()}):
        detail = dict(texts.get(spell_id) or {})
        if names.get(spell_id):
            detail["name"] = names[spell_id]
        if detail:
            localized[spell_id] = detail
    return localized, {"spellName": name_source, "spell": spell_source}


def attach_wago_spell_icons_to_data(data, trait_text):
    details = data.setdefault("spellDetails", [])
    build = data.get("build") or simc_build_from_text(trait_text)
    data["build"] = build
    talent_names_by_spell = {}
    for talent in data.get("talents") or []:
        spell_id = int(talent.get("spellId") or 0)
        if spell_id > 0 and spell_id not in talent_names_by_spell:
            talent_names_by_spell[spell_id] = talent.get("name", "")
    detail_ids = [int(detail.get("spellId") or 0) for detail in details if int(detail.get("spellId") or 0) > 0]
    spell_ids = sorted({*detail_ids, *talent_names_by_spell.keys()})
    if not spell_ids or not build:
        return data
    try:
        icon_urls, sources = spell_icon_urls_from_wago_db2(build, spell_ids)
    except Exception:
        icon_urls, sources = {}, {}
    try:
        localizations, localization_sources = spell_localizations_from_wago_db2(build, spell_ids, DEFAULT_LOCALE)
    except Exception:
        localizations, localization_sources = {}, {}
    details_by_spell = {
        int(detail.get("spellId") or 0): detail
        for detail in details
        if int(detail.get("spellId") or 0) > 0
    }
    for spell_id, icon_url in icon_urls.items():
        detail = details_by_spell.get(spell_id)
        if detail:
            detail["iconUrl"] = icon_url
            continue
        detail = {
            "spellId": spell_id,
            "name": talent_names_by_spell.get(spell_id, ""),
            "description": "",
            "tooltip": "",
            "rank": "",
            "iconUrl": icon_url,
            "locale": "en_US",
            "source": "wago-db2",
        }
        details.append(detail)
        details_by_spell[spell_id] = detail
    for detail in details:
        spell_id = int(detail.get("spellId") or 0)
        if icon_urls.get(spell_id):
            detail["iconUrl"] = icon_urls[spell_id]
        localization = localizations.get(spell_id) or {}
        if localization.get("name"):
            detail["name"] = localization["name"]
        if localization.get("description"):
            detail["description"] = localization["description"]
        if localization.get("tooltip"):
            detail["tooltip"] = localization["tooltip"]
        if localization.get("rank"):
            detail["rank"] = localization["rank"]
        if localization:
            detail["locale"] = DEFAULT_LOCALE
            detail["source"] = "wago-db2"
    if icon_urls:
        data["spellIcons"] = len(icon_urls)
        data["spellIconSource"] = "; ".join(value for value in sources.values() if value)
    else:
        data.setdefault("spellIcons", 0)
        data.setdefault("spellIconSource", "")
    if localizations:
        data["spellLocalizations"] = len(localizations)
        data["spellLocalizationSource"] = "; ".join(value for value in localization_sources.values() if value)
    else:
        data.setdefault("spellLocalizations", 0)
        data.setdefault("spellLocalizationSource", "")
    return data


def hero_tree_label(hero_key):
    fallback = str(hero_key or "").replace("_", " ").title()
    return HERO_TREE_LABELS_ZH.get(hero_key) or HERO_TREE_LABELS.get(hero_key, fallback)


def hero_tree_payload(hero_key):
    return {
        "key": hero_key,
        "label": hero_tree_label(hero_key),
        "labelEn": HERO_TREE_LABELS.get(hero_key, hero_key.replace("_", " ").title()),
    }


def hero_trees_for_spec(class_key, spec_key):
    return list(HERO_BY_SPEC.get((class_key, spec_key)) or HERO_BY_CLASS.get(class_key) or ["websim_hero"])


def hero_tree_for(class_key, spec_key, hero_key=""):
    heroes = hero_trees_for_spec(class_key, spec_key)
    if hero_key in heroes:
        return hero_key
    return heroes[0]


def talent_tree_sections(class_key="mage", spec_key="arcane", hero_key=""):
    klass = next((item for item in classes_payload() if item["key"] == class_key), {})
    spec = next((item for item in klass.get("specs", []) if item["key"] == spec_key), {})
    hero_key = hero_tree_for(class_key, spec_key, hero_key)
    hero_label = hero_tree_label(hero_key)
    return [
        {
            "key": "class",
            "title": klass.get("label") or class_key.title(),
            "titleEn": klass.get("labelEn") or class_key.title(),
            "pointCap": 34,
            "reqLevel": 10,
            "accent": CLASS_COLORS.get(class_key, "#f1b94c"),
        },
        {
            "key": "spec",
            "title": spec.get("label") or SPEC_LABELS_ZH.get(spec_key, SPEC_LABELS.get(spec_key, spec_key.title())),
            "titleEn": spec.get("labelEn") or SPEC_LABELS.get(spec_key, spec_key.title()),
            "pointCap": 34,
            "reqLevel": 11,
            "accent": CLASS_COLORS.get(class_key, "#f1b94c"),
        },
        {
            "key": "hero",
            "title": hero_label,
            "titleEn": hero_label,
            "pointCap": 13,
            "reqLevel": 71,
            "accent": "#58d3ff",
        },
    ]


def fallback_point_requirement(tree_type, row):
    if tree_type == "hero":
        if row >= 5:
            return 6
        if row >= 4:
            return 4
        if row >= 3:
            return 2
        if row >= 2:
            return 1
        return 0
    if row >= 7:
        return 20
    if row >= 6:
        return 14
    if row >= 5:
        return 8
    return 0


def fallback_node(
    class_key,
    spec_key,
    tree_type,
    key,
    row,
    col,
    name,
    icon_name,
    parents=None,
    max_rank=1,
    selected_rank=0,
    shape="square",
    choice_group="",
):
    node_id = f"fallback-{class_key}-{spec_key}-{tree_type}-{key}"
    parent_ids = [f"fallback-{class_key}-{spec_key}-{tree_type}-{parent}" for parent in parents or []]
    icon_url = wow_icon_url(icon_name)
    game_asset = game_asset_from_icon_url(
        "talent",
        node_id,
        "websim-fallback-talent",
        icon_url,
        source="static_icon_name",
        status="fallback",
        semantic_tags=["game", "talent", tree_type, class_key, spec_key],
        usage=["talent_simulator"],
        fallback_text=fallback_text_for(name),
    )
    return {
        "id": node_id,
        "classKey": class_key,
        "specKey": spec_key if tree_type != "class" else "class",
        "treeId": tree_type,
        "treeType": tree_type,
        "row": row,
        "col": col,
        "spellId": 0,
        "name": name,
        "rank": max_rank,
        "maxRank": max_rank,
        "selectedRank": selected_rank,
        "grantedRank": selected_rank,
        "granted": selected_rank > 0,
        "selected": selected_rank > 0,
        "parentIds": parent_ids,
        "parentMode": "any",
        "shape": shape,
        "choiceGroup": choice_group,
        "pointRequirement": fallback_point_requirement(tree_type, row),
        "entryId": 0,
        "dependencySource": "websim-fallback",
        "schemaRevision": TALENT_SCHEMA_REVISION,
        "description": f"WebSim 可交互占位{tree_type}天赋；同步到 Blizzard / SimC 校验数据后会替换为真实节点。",
        "iconUrl": icon_url,
        "gameAsset": game_asset,
        "source": "websim-fallback",
    }


def fallback_talents(class_key="mage", spec_key="arcane", hero_key=""):
    spec_label = SPEC_LABELS_ZH.get(spec_key, SPEC_LABELS.get(spec_key, spec_key.replace("_", " ").title()))
    hero_key = hero_tree_for(class_key, spec_key, hero_key)
    hero_label = hero_tree_label(hero_key)
    class_icon = CLASS_ICON_NAMES.get(class_key, "inv_misc_questionmark")
    spec_icon = SPEC_ICON_NAMES.get(spec_key, class_icon)
    hero_icon = SPEC_ICON_NAMES.get(spec_key, class_icon)
    class_nodes = [
        ("class-core", 1, 2, "职业核心", class_icon, [], 1, 1, "circle"),
        ("mobility", 1, 4, "机动能力", class_icon, [], 1, 1, "square"),
        ("survival", 1, 6, "生存能力", class_icon, [], 1, 1, "square"),
        ("class-training", 1, 7, "职业训练", class_icon, [], 1, 1, "circle"),
        ("resource", 2, 2, "资源循环", class_icon, ["class-core"], 2, 1, "square"),
        ("tempo", 2, 3, "节奏控制", class_icon, ["class-core", "mobility"], 1, 0, "square"),
        ("interrupt", 2, 4, "打断控制", class_icon, ["mobility"], 1, 1, "choice"),
        ("cleanse", 2, 5, "驱散工具", class_icon, ["mobility", "survival"], 1, 0, "square"),
        ("defense", 2, 6, "防御层级", class_icon, ["survival"], 2, 0, "square"),
        ("raid-buff", 2, 7, "团队增益", class_icon, ["class-training"], 1, 0, "square"),
        ("utility", 3, 3, "功能选择", class_icon, ["resource", "interrupt"], 1, 0, "choice", "class-mid-choice"),
        ("sustain", 3, 5, "续航选择", class_icon, ["interrupt", "defense"], 1, 0, "choice", "class-mid-choice"),
        ("control-suite", 3, 1, "控制组合", class_icon, ["resource"], 1, 0, "square"),
        ("throughput-a", 3, 2, "输出强化 A", class_icon, ["resource"], 2, 0, "square"),
        ("throughput-b", 3, 4, "输出强化 B", class_icon, ["interrupt"], 2, 0, "square"),
        ("group-guard", 3, 6, "团队守护", class_icon, ["defense"], 1, 0, "square"),
        ("support-node", 3, 7, "辅助节点", class_icon, ["raid-buff"], 1, 0, "square"),
        ("capstone-a", 4, 2, "职业终点 A", class_icon, ["utility", "throughput-a"], 1, 0, "circle"),
        ("class-capstone", 4, 4, "职业终点", class_icon, ["utility", "sustain", "throughput-b"], 2, 0, "circle"),
        ("capstone-b", 4, 6, "职业终点 B", class_icon, ["sustain", "group-guard"], 1, 0, "circle"),
        ("recovery", 4, 1, "恢复路径", class_icon, ["control-suite"], 1, 0, "square"),
        ("amplifier", 4, 3, "职业增幅", class_icon, ["throughput-a", "throughput-b"], 1, 0, "square"),
        ("bulwark", 4, 5, "防线强化", class_icon, ["group-guard"], 1, 0, "square"),
        ("teamwork", 4, 7, "团队协作", class_icon, ["support-node"], 1, 0, "square"),
        ("keystone-a", 5, 2, "职业关键 A", class_icon, ["capstone-a", "amplifier"], 1, 0, "circle"),
        ("keystone-b", 5, 4, "职业关键", class_icon, ["class-capstone"], 2, 0, "circle"),
        ("keystone-c", 5, 6, "职业关键 B", class_icon, ["capstone-b", "bulwark"], 1, 0, "circle"),
        ("final-utility", 6, 1, "最终功能", class_icon, ["recovery", "keystone-a"], 1, 0, "square"),
        ("final-power", 6, 4, "最终强化", class_icon, ["keystone-b"], 1, 0, "circle"),
        ("final-defense", 6, 7, "最终防御", class_icon, ["teamwork", "keystone-c"], 1, 0, "square"),
    ]
    spec_nodes = [
        ("opener", 1, 2, f"{spec_label} 起手", spec_icon, [], 1, 1, "circle"),
        ("core", 1, 4, f"{spec_label} 核心", spec_icon, [], 1, 1, "circle"),
        ("control", 1, 6, f"{spec_label} 控制", spec_icon, [], 1, 1, "square"),
        ("identity", 1, 7, f"{spec_label} 标识", spec_icon, [], 1, 1, "circle"),
        ("builder", 2, 2, "主要构筑点", spec_icon, ["opener"], 2, 1, "square"),
        ("proc", 2, 3, "触发引擎", spec_icon, ["opener", "core"], 1, 0, "square"),
        ("spender", 2, 4, "标志消耗", spec_icon, ["core"], 2, 1, "square"),
        ("haste-sync", 2, 5, "急速联动", spec_icon, ["core", "control"], 1, 0, "square"),
        ("cooldown", 2, 6, "冷却同步", spec_icon, ["control"], 1, 0, "square"),
        ("identity-passive", 2, 7, "标识被动", spec_icon, ["identity"], 1, 0, "square"),
        ("aoe", 3, 1, "范围选项", spec_icon, ["builder"], 1, 0, "choice", "spec-output-choice"),
        ("single", 3, 3, "单体选项", spec_icon, ["spender"], 1, 0, "choice", "spec-output-choice"),
        ("def-tech", 3, 5, "防御技巧", spec_icon, ["cooldown"], 1, 0, "choice", "spec-tech-choice"),
        ("utility-tech", 3, 7, "功能技巧", spec_icon, ["cooldown"], 1, 0, "choice", "spec-tech-choice"),
        ("cleave", 3, 2, "顺劈模板", spec_icon, ["builder", "proc"], 1, 0, "square"),
        ("priority", 3, 4, "优先级模板", spec_icon, ["proc", "spender"], 1, 0, "square"),
        ("surge", 3, 6, "爆发窗口", spec_icon, ["haste-sync", "cooldown"], 1, 0, "square"),
        ("engine", 4, 2, f"{spec_label} 引擎", spec_icon, ["aoe", "single", "cleave"], 2, 0, "square"),
        ("mastery", 4, 4, f"{spec_label} 精通", spec_icon, ["single", "priority", "def-tech"], 2, 0, "circle"),
        ("capstone", 4, 6, f"{spec_label} 终点", spec_icon, ["def-tech", "utility-tech", "surge"], 1, 0, "circle"),
        ("rotation-a", 4, 1, "循环分支 A", spec_icon, ["aoe"], 1, 0, "square"),
        ("rotation-b", 4, 3, "循环分支 B", spec_icon, ["cleave", "priority"], 1, 0, "square"),
        ("rotation-c", 4, 5, "循环分支 C", spec_icon, ["surge"], 1, 0, "square"),
        ("rotation-d", 4, 7, "循环分支 D", spec_icon, ["utility-tech", "identity-passive"], 1, 0, "square"),
        ("finisher-a", 5, 2, f"{spec_label} 收尾 A", spec_icon, ["engine", "rotation-b"], 1, 0, "circle"),
        ("finisher-b", 5, 4, f"{spec_label} 收尾", spec_icon, ["mastery"], 2, 0, "circle"),
        ("finisher-c", 5, 6, f"{spec_label} 收尾 B", spec_icon, ["capstone", "rotation-c"], 1, 0, "circle"),
        ("deep-a", 6, 1, "深层天赋 A", spec_icon, ["rotation-a", "finisher-a"], 1, 0, "square"),
        ("deep-b", 6, 3, "深层天赋 B", spec_icon, ["finisher-a", "finisher-b"], 1, 0, "square"),
        ("deep-c", 6, 5, "深层天赋 C", spec_icon, ["finisher-b", "finisher-c"], 1, 0, "square"),
        ("deep-d", 6, 7, "深层天赋 D", spec_icon, ["rotation-d", "finisher-c"], 1, 0, "square"),
        ("final-left", 7, 2, f"{spec_label} 顶点左", spec_icon, ["deep-a", "deep-b"], 1, 0, "circle"),
        ("final", 7, 4, f"{spec_label} 顶点", spec_icon, ["deep-b", "deep-c"], 1, 0, "circle"),
        ("final-right", 7, 6, f"{spec_label} 顶点右", spec_icon, ["deep-c", "deep-d"], 1, 0, "circle"),
    ]
    hero_nodes = [
        ("calling", 1, 2, f"{hero_label} 号召", hero_icon, [], 1, 1, "circle"),
        ("strike", 2, 1, "英雄打击", hero_icon, ["calling"], 1, 1, "square"),
        ("ward", 2, 3, "英雄结界", hero_icon, ["calling"], 1, 0, "square"),
        ("choice-a", 3, 1, "英雄选择 A", hero_icon, ["strike"], 1, 0, "choice", "hero-keystone-choice"),
        ("choice-b", 3, 3, "英雄选择 B", hero_icon, ["ward"], 1, 0, "choice", "hero-keystone-choice"),
        ("keystone", 4, 2, f"{hero_label} 关键", hero_icon, ["choice-a", "choice-b"], 2, 0, "circle"),
        ("hero-focus", 2, 2, "英雄专注", hero_icon, ["calling"], 2, 0, "square"),
        ("hero-tech-a", 3, 2, "英雄技巧", hero_icon, ["hero-focus"], 1, 0, "square"),
        ("hero-tech-b", 4, 1, "英雄技巧 A", hero_icon, ["choice-a", "hero-tech-a"], 1, 0, "square"),
        ("hero-tech-c", 4, 3, "英雄技巧 B", hero_icon, ["choice-b", "hero-tech-a"], 1, 0, "square"),
        ("apex", 5, 2, f"{hero_label} 顶点", hero_icon, ["keystone", "hero-tech-b", "hero-tech-c"], 2, 0, "circle"),
    ]
    nodes = []
    for tree_type, rows in [("class", class_nodes), ("spec", spec_nodes), ("hero", hero_nodes)]:
        for row_data in rows:
            key, row, col, name, icon, parents, max_rank, selected_rank, shape = row_data[:9]
            choice_group = row_data[9] if len(row_data) > 9 else ""
            nodes.append(
                fallback_node(
                    class_key,
                    spec_key,
                    tree_type,
                    key,
                    row,
                    col,
                    name,
                    icon,
                    parents,
                    max_rank,
                    selected_rank,
                    shape,
                    choice_group,
                )
            )
    return nodes


def real_talent_shape(payload, row_index):
    if int(row_index or 0) >= 11:
        return "apex"
    return payload.get("shape", "square")


def decorate_real_talent_node(row, season):
    payload = safe_json_loads(row[8], {})
    tree_type = payload.get("treeType") or ("class" if row[2] == "class" else "spec")
    rank_entries, rank_entry_points = normalize_simc_rank_entries(payload.get("rankEntries") or [])
    max_rank = int(payload.get("maxRank") or payload.get("rank") or rank_entry_points or 1)
    selected_rank = int(payload.get("selectedRank", 0) or 0)
    if tree_type == "hero" and int(row[4] or 0) == 1:
        selected_rank = max(selected_rank, 1)
    granted_rank = int(payload.get("grantedRank", selected_rank) or 0)
    if tree_type == "hero" and int(row[4] or 0) == 1:
        granted_rank = max(granted_rank, 1)
    icon_name = CLASS_ICON_NAMES.get(row[1], "inv_misc_questionmark")
    if tree_type in {"spec", "hero"}:
        icon_name = SPEC_ICON_NAMES.get(row[2], icon_name)
    description, description_status = talent_spell_display_description(row[9] or payload.get("description") or "")
    icon_url = row[10] or wow_icon_url(icon_name)
    spell_detail_payload = safe_json_loads(row[11] if len(row) > 11 else "", {})
    icon_source, icon_status = spell_icon_asset_source_status(
        row[10],
        spell_detail_payload,
        payload.get("source", "simulationcraft"),
    ) if row[10] else ("static_icon_name", "fallback")
    game_asset = game_asset_from_icon_url(
        "talent",
        row[0],
        "websim-talent-node",
        icon_url,
        source=icon_source,
        status=icon_status,
        semantic_tags=["game", "talent", tree_type, row[1], row[2]],
        usage=["talent_simulator"],
        fallback_text=fallback_text_for(row[7]),
    )
    return {
        "id": row[0],
        "classKey": row[1],
        "specKey": row[2],
        "treeId": row[3],
        "treeType": tree_type,
        "row": row[4],
        "col": row[5],
        "spellId": row[6],
        "name": row[7],
        "rank": max_rank,
        "maxRank": max_rank,
        "selectedRank": selected_rank,
        "grantedRank": granted_rank,
        "granted": bool(payload.get("granted") or granted_rank > 0),
        "selected": selected_rank > 0,
        "parentIds": payload.get("parentIds", []),
        "parentMode": "all" if str(payload.get("parentMode") or "").lower() == "all" else "any",
        "shape": real_talent_shape(payload, row[4]),
        "choiceGroup": payload.get("choiceGroup", ""),
        "rankEntries": rank_entries,
        "rankCount": len(rank_entries),
        "pointRequirement": int(payload.get("pointRequirement", 0) or 0),
        "entryId": websim_node_entry_id({"traitId": payload.get("traitId"), "rankEntries": rank_entries}),
        "dependencySource": payload.get("dependencySource", ""),
        "schemaRevision": TALENT_SCHEMA_REVISION,
        "description": description,
        "descriptionStatus": description_status,
        "iconUrl": icon_url,
        "gameAsset": game_asset,
        "source": payload.get("source", "simulationcraft"),
        "traitId": payload.get("traitId"),
        "nodeId": payload.get("nodeId"),
        "selectionIndex": payload.get("selectionIndex"),
        "heroKey": payload.get("heroKey", ""),
        "heroLabel": payload.get("heroLabel", ""),
        "sourceRefs": SIMC_TALENT_SOURCE_REFS + (season.get("sourceRefs") or []),
    }


def dedupe_real_talent_nodes(nodes):
    deduped = []
    seen = set()
    for node in nodes:
        choice_group = node.get("choiceGroup") or ""
        if choice_group or node.get("shape") == "choice":
            key = ("choice", node.get("id"))
        else:
            key = (
                node.get("classKey"),
                node.get("specKey"),
                node.get("treeId"),
                node.get("treeType"),
                node.get("heroKey", ""),
                node.get("nodeId") or node.get("id"),
            )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(node)
    return deduped


def enrich_talent_rank_entries(conn, nodes):
    spell_ids = sorted(
        {
            int(entry.get("spellId") or 0)
            for node in nodes or []
            for entry in node.get("rankEntries") or []
            if int(entry.get("spellId") or 0) > 0
        }
    )
    if not spell_ids:
        return nodes
    placeholders = ",".join("?" for _ in spell_ids)
    rows = conn.execute(
        f"""
        SELECT spell_id, name, description
        FROM websim_spell_details
        WHERE spell_id IN ({placeholders})
        """,
        spell_ids,
    ).fetchall()
    details = {}
    for row in rows:
        description, description_status = talent_spell_display_description(row[2] or "")
        details[int(row[0])] = {
            "name": row[1] or "",
            "description": description,
            "descriptionStatus": description_status,
        }
    for node in nodes or []:
        next_entries = []
        for entry in node.get("rankEntries") or []:
            spell_id = int(entry.get("spellId") or 0)
            detail = details.get(spell_id, {})
            next_entry = dict(entry)
            if detail.get("description"):
                next_entry["description"] = detail["description"]
                next_entry["descriptionStatus"] = detail.get("descriptionStatus") or "missing"
            if detail.get("name"):
                next_entry["spellName"] = detail["name"]
            next_entries.append(next_entry)
        if next_entries:
            node["rankEntries"] = next_entries
    return nodes


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
    return [{"id": f"fallback-{class_key}-{spec_key}", "classKey": class_key, "specKey": spec_key, "name": "WebSim 入门构筑", "profile": profile}]


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
        "gearSlots": gear_slot_payload(),
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


def talent_node_description_status(node):
    status = str((node or {}).get("descriptionStatus") or "").strip()
    if status:
        return status
    return "ready" if str((node or {}).get("description") or "").strip() else "missing"


def talent_node_spell_status_counts(nodes):
    counts = {
        "coveredSpellCount": 0,
        "missingDescriptionCount": 0,
        "unresolvedDescriptionCount": 0,
        "missingIconCount": 0,
    }
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        status = talent_node_description_status(node)
        entry_statuses = [
            str(entry.get("descriptionStatus") or "").strip()
            for entry in node.get("rankEntries") or []
            if isinstance(entry, dict) and str(entry.get("descriptionStatus") or "").strip()
        ]
        has_unresolved = status == "pending_formula_resolution" or any(
            entry_status == "pending_formula_resolution" for entry_status in entry_statuses
        )
        has_missing_description = status == "missing" or any(entry_status == "missing" for entry_status in entry_statuses)
        has_icon = bool(str(node.get("iconUrl") or "").strip())
        if has_unresolved:
            counts["unresolvedDescriptionCount"] += 1
        if has_missing_description:
            counts["missingDescriptionCount"] += 1
        if not has_icon:
            counts["missingIconCount"] += 1
        if status == "ready" and not has_unresolved and not has_missing_description and has_icon:
            counts["coveredSpellCount"] += 1
    return counts


def talent_readiness_payload(class_key, spec_key, hero_key, talent_status, nodes, tree_sections, talent_authority=None):
    node_list = nodes if isinstance(nodes, list) else []
    sections = tree_sections if isinstance(tree_sections, list) else []
    required_trees = {"class", "spec", "hero"}
    section_keys = {
        str(section.get("key") or "").strip()
        for section in sections
        if isinstance(section, dict) and int(section.get("pointCap") or 0) > 0
    }
    node_tree_types = {
        str(node.get("treeType") or "").strip()
        for node in node_list
        if isinstance(node, dict) and str(node.get("treeType") or "").strip()
    }
    node_counts = {
        tree_type: sum(1 for node in node_list if isinstance(node, dict) and node.get("treeType") == tree_type)
        for tree_type in sorted(required_trees)
    }
    entry_counts = {
        tree_type: sum(
            1
            for node in node_list
            if isinstance(node, dict) and node.get("treeType") == tree_type and websim_node_entry_id(node) > 0
        )
        for tree_type in sorted(required_trees)
    }
    missing_trees = sorted(required_trees - (section_keys & node_tree_types))
    tree_ready = not missing_trees
    non_fallback = talent_status != "fallback"
    rule_ready = non_fallback and bool(node_list) and all(
        isinstance(node, dict)
        and node.get("schemaRevision") == TALENT_SCHEMA_REVISION
        and str(node.get("parentMode") or "any") in {"any", "all"}
        and "pointRequirement" in node
        and "grantedRank" in node
        for node in node_list
    )
    spell_counts = talent_node_spell_status_counts(node_list)
    spell_ready = bool(
        non_fallback
        and node_list
        and spell_counts["coveredSpellCount"] == len([node for node in node_list if isinstance(node, dict)])
    )
    encoding_ready = non_fallback and tree_ready and all(entry_counts.get(tree_type, 0) > 0 for tree_type in required_trees)
    diff_status = str(((talent_authority or {}).get("diffStatus") or "")).strip()
    authority_blocked = diff_status == "blocked"
    blockers = []
    if talent_status == "fallback":
        blockers.append("WebSim talent cache is fallback; sync SimulationCraft talent data before running SimC")
    if missing_trees:
        blockers.append(f"talent tree is incomplete for {', '.join(missing_trees)}")
    if not rule_ready:
        blockers.append("talent authority rules are incomplete")
    if not spell_ready:
        blockers.append("talent spell descriptions/icons are incomplete")
    if spell_counts["unresolvedDescriptionCount"]:
        blockers.append(
            "talent spell descriptions contain unresolved formula text for "
            f"{spell_counts['unresolvedDescriptionCount']} talent nodes"
        )
    if not encoding_ready:
        blockers.append("talent nodes cannot produce class/spec/hero SimC talent lines")
    if authority_blocked:
        blockers.append("talent authority diff status is blocked")
    rule_sources = sorted({
        str(node.get("dependencySource") or node.get("source") or "").strip()
        for node in node_list
        if isinstance(node, dict) and str(node.get("dependencySource") or node.get("source") or "").strip()
    })
    return {
        "schemaRevision": TALENT_SCHEMA_REVISION,
        "classKey": class_key,
        "specKey": spec_key,
        "heroKey": hero_key,
        "sourceStatus": talent_status,
        "treeReady": tree_ready,
        "ruleReady": rule_ready,
        "spellReady": spell_ready,
        "encodingReady": encoding_ready,
        "simcReady": bool(non_fallback and tree_ready and rule_ready and encoding_ready and not authority_blocked),
        "treeCoverage": {
            "required": sorted(required_trees),
            "present": sorted(section_keys & node_tree_types),
            "missing": missing_trees,
            "nodeCounts": node_counts,
        },
        "ruleSource": ", ".join(rule_sources) or ("fallback" if talent_status == "fallback" else ""),
        "spellCoverage": {
            **catalog_health_coverage(spell_counts["coveredSpellCount"], len(node_list)),
            "missingDescriptionCount": spell_counts["missingDescriptionCount"],
            "unresolvedDescriptionCount": spell_counts["unresolvedDescriptionCount"],
            "missingIconCount": spell_counts["missingIconCount"],
        },
        "encodingCoverage": {
            "required": sorted(required_trees),
            "covered": sorted(tree_type for tree_type in required_trees if entry_counts.get(tree_type, 0) > 0),
            "entryCounts": entry_counts,
        },
        "blockers": unique_text_list(blockers),
    }


def get_websim_talents(conn, class_key="mage", spec_key="arcane", hero_key=""):
    ensure_websim_tables(conn)
    season = get_active_season_payload(conn)
    class_key = slugify(class_key, "mage")
    spec_key = slugify(spec_key, "arcane")
    hero_key = hero_tree_for(class_key, spec_key, slugify(hero_key, ""))
    rows = conn.execute(
        """
        SELECT t.id, t.class_key, t.spec_key, t.tree_id, t.row_index, t.col_index,
               t.spell_id, COALESCE(NULLIF(s.name, ''), t.name) AS name, t.payload_json,
               s.description, s.icon_url, s.payload_json
        FROM websim_talents t
        LEFT JOIN websim_spell_details s ON s.spell_id = t.spell_id
        WHERE t.class_key = ?
          AND (t.spec_key = ? OR t.spec_key = 'class')
          AND t.spell_id > 0
        ORDER BY row_index, col_index, name
        LIMIT 320
        """,
        (class_key, spec_key),
    ).fetchall()
    filtered_rows = []
    for row in rows:
        payload = safe_json_loads(row[8], {})
        tree_type = payload.get("treeType") or ("class" if row[2] == "class" else "spec")
        if tree_type == "hero" and payload.get("heroKey") != hero_key:
            continue
        filtered_rows.append(row)
    nodes = enrich_talent_rank_entries(
        conn,
        dedupe_real_talent_nodes([decorate_real_talent_node(row, season) for row in filtered_rows]),
    )
    has_spell_details = bool(filtered_rows) and all(
        talent_spell_display_description(row[9] or "")[1] == "ready" and str(row[10] or "").strip()
        for row in filtered_rows
    )
    talent_status = "verified" if nodes and season.get("dataStatus") == "verified" and has_spell_details else "simc"
    if not nodes:
        nodes = fallback_talents(class_key, spec_key, hero_key)
        talent_status = "fallback"
    talent_authority = talent_authority_payload(conn, talent_status, season, nodes)
    tree_sections = talent_tree_sections(class_key, spec_key, hero_key)
    talent_readiness = talent_readiness_payload(
        class_key,
        spec_key,
        hero_key,
        talent_status,
        nodes,
        tree_sections,
        talent_authority,
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
        "presets": get_websim_presets(conn, class_key, spec_key),
        "communityTemplates": get_websim_community_talent_templates(conn, class_key, spec_key, hero_key),
        "communityTemplateSync": community_talent_sync_state(conn),
        "treeSections": tree_sections,
        "talentStatus": talent_status,
        **season_metadata_fields(season),
    }


def get_websim_presets(conn, class_key="mage", spec_key="arcane"):
    rows = conn.execute(
        """
        SELECT id, class_key, spec_key, name, profile, payload_json, updated_at
        FROM websim_profile_presets
        WHERE class_key = ? AND spec_key = ?
        ORDER BY name
        LIMIT 12
        """,
        (class_key, spec_key),
    ).fetchall()
    if not rows:
        return fallback_presets(class_key, spec_key)
    return [
        {
            "id": row[0],
            "classKey": row[1],
            "specKey": row[2],
            "name": row[3],
            "profile": row[4],
            "payload": safe_json_loads(row[5], {}),
            "updatedAt": row[6],
        }
        for row in rows
    ]


def include_manual_fixture_sources():
    return os.environ.get("WOW_INCLUDE_MANUAL_FIXTURES", "").strip().lower() in {"1", "true", "yes", "on"}


def include_websim_baseline_talent_sources():
    return os.environ.get("WOW_INCLUDE_WEBSIM_BASELINE_TALENTS", "").strip().lower() in {"1", "true", "yes", "on"}


def disabled_community_talent_template_source_keys():
    keys = []
    if not include_manual_fixture_sources():
        keys.append("manual_fixture")
    if not include_websim_baseline_talent_sources():
        keys.append("websim_baseline")
    return keys


def ensure_community_talent_templates(conn):
    if get_sync_state(conn, COMMUNITY_TALENT_SYNC_KEY):
        return
    try:
        sync_community_talent_templates(conn)
    except Exception as error:
        sources = {
            "raiderio": {"status": "missing_credentials", "sourceName": "Raider.IO", "errors": []},
            "warcraftlogs": {"status": "missing_credentials", "sourceName": "Warcraft Logs", "errors": []},
        }
        if include_websim_baseline_talent_sources():
            sources["websim_baseline"] = {"status": "blocked", "sourceName": "WebSim 基线模板", "errors": [str(error)]}
        if include_manual_fixture_sources():
            sources["manual_fixture"] = {"status": "blocked", "sourceName": "Manual Fixture", "errors": [str(error)]}
        set_sync_state(conn, COMMUNITY_TALENT_SYNC_KEY, {
            "sourceStatus": "blocked",
            "sources": sources,
            "templates": {"total": 0, "verified": 0, "blocked": 0},
            "checkedAt": utc_now(),
        })


def community_talent_template_stats(conn):
    ensure_websim_tables(conn)
    rows = conn.execute(
        """
        SELECT class_key, spec_key, hero_key, status, signature, talent_state_json,
               raw_import_code, websim_export_code
        FROM websim_community_talent_templates
        WHERE status = 'verified'
          AND expires_at > ?
        """,
        (utc_now(),),
    ).fetchall()
    signatures = set()
    covered = set()
    raw_count = 0
    for row in rows:
        template = {
            "classKey": row[0],
            "specKey": row[1],
            "heroKey": row[2],
            "status": row[3],
            "signature": row[4],
            "talentState": safe_json_loads(row[5], {"selectedNodes": []}),
            "rawImportCode": row[6] or "",
            "websimExportCode": row[7] or "",
        }
        signature = row[4] or community_talent_signature(template)
        signatures.add(signature)
        covered.add(f"{row[0]}:{row[1]}")
        raw_count += 1
    expected = set(expected_spec_pairs())
    total_specs = len(expected) or len(covered)
    missing = sorted(expected - covered) if expected else []
    return {
        "templateRevision": community_template_revision_from_signatures(signatures),
        "dedupedCount": len(signatures),
        "hiddenDuplicateCount": max(0, raw_count - len(signatures)),
        "scanCoverage": {
            "totalClassCount": len(WOW_CLASSES),
            "totalSpecCount": total_specs,
            "coveredSpecCount": len(covered & expected) if expected else len(covered),
            "missingSpecs": missing,
        },
    }


def community_talent_sync_state(conn):
    state = get_sync_state(conn, COMMUNITY_TALENT_SYNC_KEY)
    stats = community_talent_template_stats(conn)
    if state:
        state = {**state}
        state.setdefault("templateRevision", stats["templateRevision"])
        state.setdefault("scanCoverage", stats["scanCoverage"])
        state.setdefault("dedupedCount", stats["dedupedCount"])
        state.setdefault("hiddenDuplicateCount", stats["hiddenDuplicateCount"])
        return state
    sources = {
        "raiderio": {"status": "missing_credentials", "sourceName": "Raider.IO", "errors": []},
        "warcraftlogs": {"status": "missing_credentials", "sourceName": "Warcraft Logs", "errors": []},
    }
    if include_websim_baseline_talent_sources():
        sources["websim_baseline"] = {"status": "missing_credentials", "sourceName": "WebSim 基线模板", "errors": []}
    if include_manual_fixture_sources():
        sources["manual_fixture"] = {"status": "missing_credentials", "sourceName": "Manual Fixture", "errors": []}
    return {
        "sourceStatus": "missing_credentials",
        "sources": sources,
        "templates": {"total": 0, "verified": 0, "blocked": 0},
        "templateRevision": stats["templateRevision"],
        "scanCoverage": stats["scanCoverage"],
        "dedupedCount": stats["dedupedCount"],
        "hiddenDuplicateCount": stats["hiddenDuplicateCount"],
        "checkedAt": "",
    }


def community_talent_selected_nodes(template):
    state = template.get("talentState") if isinstance(template, dict) else {}
    if not isinstance(state, dict):
        state = {}
    selected = state.get("selectedNodes") or template.get("selectedNodes") or []
    if not isinstance(selected, list):
        selected = []
    normalized = []
    for item in selected:
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("id") or "").strip()
        if not node_id:
            continue
        try:
            rank = int(item.get("rank") or 1)
        except (TypeError, ValueError):
            rank = 1
        normalized.append({"id": node_id, "rank": max(1, rank)})
    return normalized[:400]


def community_talent_state(template):
    state = template.get("talentState") if isinstance(template, dict) else {}
    if not isinstance(state, dict):
        state = {}
    return {
        **state,
        "selectedNodes": community_talent_selected_nodes(template),
    }


def community_talent_export_code(template):
    websim_code = str(template.get("websimExportCode") or "").strip()
    if websim_code.startswith("websim:"):
        return websim_code
    selected = community_talent_selected_nodes(template)
    if not selected:
        return ""
    class_key = slugify(template.get("classKey"), "mage")
    spec_key = slugify(template.get("specKey"), "arcane")
    hero_key = hero_tree_for(class_key, spec_key, slugify(template.get("heroKey"), ""))
    entries = ",".join(
        f"{item['id']}:{item['rank']}"
        for item in sorted(selected, key=lambda row: row["id"])
    )
    return f"websim:{class_key}:{spec_key}:{hero_key}:{entries}"


def stable_digest(value):
    return hashlib.sha1(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]


def expected_spec_pairs():
    pairs = []
    for klass in WOW_CLASSES:
        class_key = slugify(klass.get("key"), "")
        for spec in klass.get("specs") or []:
            spec_key = slugify(spec.get("key") if isinstance(spec, dict) else spec, "")
            if class_key and spec_key:
                pairs.append(f"{class_key}:{spec_key}")
    return pairs


def expected_hero_tree_triplets():
    triplets = []
    for klass in WOW_CLASSES:
        class_key = slugify(klass.get("key"), "")
        for spec in klass.get("specs") or []:
            spec_key = slugify(spec.get("key") if isinstance(spec, dict) else spec, "")
            if not class_key or not spec_key:
                continue
            for hero_key in hero_trees_for_spec(class_key, spec_key):
                if hero_key:
                    triplets.append(f"{class_key}:{spec_key}:{hero_key}")
    return triplets


def community_template_revision_from_signatures(signatures):
    values = sorted(str(item or "") for item in signatures or [] if str(item or ""))
    if not values:
        return COMMUNITY_TEMPLATE_REVISION
    return f"{COMMUNITY_TEMPLATE_REVISION}-{hashlib.sha1('|'.join(values).encode('utf-8')).hexdigest()[:10]}"


def normalize_source_refs(refs):
    normalized = []
    seen = set()
    for ref in refs or []:
        if not isinstance(ref, dict):
            continue
        item = {
            "id": str(ref.get("id") or "").strip(),
            "sourceKey": str(ref.get("sourceKey") or "").strip(),
            "sourceName": str(ref.get("sourceName") or "").strip(),
            "sourceUrl": str(ref.get("sourceUrl") or "").strip(),
            "sourceStatus": str(ref.get("sourceStatus") or "").strip(),
            "status": str(ref.get("status") or "").strip(),
            "sampleCount": int(ref.get("sampleCount") or 0),
            "maxKeyLevel": int(ref.get("maxKeyLevel") or 0),
            "updatedAt": str(ref.get("updatedAt") or "").strip(),
            "analysisWindow": str(ref.get("analysisWindow") or "").strip(),
        }
        key = "|".join([item["id"], item["sourceKey"], item["sourceUrl"]])
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return normalized


def community_talent_signature(template):
    class_key = slugify(template.get("classKey"), "mage")
    spec_key = slugify(template.get("specKey"), "arcane")
    hero_key = hero_tree_for(class_key, spec_key, slugify(template.get("heroKey"), ""))
    selected = community_talent_selected_nodes(template)
    if selected:
        nodes = sorted(
            [{"id": str(item.get("id") or ""), "rank": int(item.get("rank") or 1)} for item in selected],
            key=lambda item: (item["id"], item["rank"]),
        )
        return f"talent:{class_key}:{spec_key}:{hero_key}:{stable_digest(nodes)}"
    raw_code = external_talent_import_code({
        "talents": template.get("rawImportCode") or template.get("raw_import_code") or ""
    })
    normalized_raw = re.sub(r"\s+", "", raw_code)
    if normalized_raw:
        return f"talent:{class_key}:{spec_key}:{hero_key}:raw:{hashlib.sha1(normalized_raw.encode('utf-8')).hexdigest()[:16]}"
    return f"talent:{class_key}:{spec_key}:{hero_key}:empty"


def community_talent_source_ref(template):
    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    return {
        "id": str(template.get("id") or "").strip(),
        "sourceKey": str(template.get("sourceKey") or payload.get("sourceKey") or "").strip(),
        "sourceName": str(template.get("sourceName") or "").strip(),
        "sourceUrl": str(template.get("sourceUrl") or "").strip(),
        "sourceStatus": str(template.get("sourceStatus") or "").strip(),
        "status": str(template.get("status") or "").strip(),
        "sampleCount": int(template.get("sampleCount") or 0),
        "maxKeyLevel": int(template.get("maxKeyLevel") or 0),
        "updatedAt": str(template.get("updatedAt") or "").strip(),
        "analysisWindow": str(template.get("analysisWindow") or "").strip(),
    }


def community_talent_template_sort_key(template):
    return (
        1 if template.get("canApplyVisual") else 0,
        1 if template.get("status") == "verified" else 0,
        1 if template.get("sourceStatus") in {"synced", "verified"} else 0,
        int(template.get("maxKeyLevel") or 0),
        int(template.get("sampleCount") or 0),
        str(template.get("updatedAt") or ""),
    )


def dedupe_templates_by_signature(templates, signature_getter, sort_key_getter):
    groups = {}
    for template in templates or []:
        signature = template.get("signature") or signature_getter(template)
        if not signature:
            continue
        template["signature"] = signature
        refs = normalize_source_refs(template.get("sourceRefs") or [])
        if not refs:
            refs = normalize_source_refs([community_talent_source_ref(template)])
        template["sourceRefs"] = refs
        groups.setdefault(signature, []).append(template)
    deduped = []
    for signature, grouped in groups.items():
        winner = sorted(grouped, key=sort_key_getter, reverse=True)[0]
        merged_refs = []
        for item in grouped:
            merged_refs.extend(item.get("sourceRefs") or [])
        winner = {**winner}
        winner["signature"] = signature
        winner["sourceRefs"] = normalize_source_refs(merged_refs)
        winner["dedupedCount"] = sum(max(1, int(item.get("dedupedCount") or 1)) for item in grouped)
        deduped.append(winner)
    return sorted(deduped, key=sort_key_getter, reverse=True)


def community_talent_public_identity(template):
    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    player_id = str(template.get("playerId") or payload.get("playerId") or "").strip()
    visible_name = player_id or str(template.get("name") or template.get("id") or "").strip()
    return "|".join([
        str(template.get("sourceKey") or payload.get("sourceKey") or "").strip().lower(),
        visible_name.lower(),
        slugify(template.get("classKey"), ""),
        slugify(template.get("specKey"), ""),
        slugify(template.get("heroKey"), ""),
        slugify(template.get("scenarioKey"), ""),
    ])


def dedupe_community_talent_templates_for_display(templates):
    by_signature = dedupe_templates_by_signature(
        templates,
        community_talent_signature,
        community_talent_template_sort_key,
    )
    groups = {}
    for template in by_signature:
        identity = community_talent_public_identity(template)
        if not identity:
            continue
        groups.setdefault(identity, []).append(template)
    deduped = []
    for grouped in groups.values():
        winner = sorted(grouped, key=community_talent_template_sort_key, reverse=True)[0]
        merged_refs = []
        deduped_count = 0
        for item in grouped:
            merged_refs.extend(item.get("sourceRefs") or [])
            deduped_count += max(1, int(item.get("dedupedCount") or 1))
        winner = {**winner}
        winner["sourceRefs"] = normalize_source_refs(merged_refs)
        winner["dedupedCount"] = deduped_count
        deduped.append(winner)
    return sorted(deduped, key=community_talent_template_sort_key, reverse=True)


def community_talent_default_state_from_db(conn, class_key, spec_key, hero_key):
    rows = conn.execute(
        """
        SELECT id, spec_key, row_index, col_index, payload_json
        FROM websim_talents
        WHERE class_key = ?
          AND (spec_key = ? OR spec_key = 'class')
          AND spell_id > 0
        ORDER BY row_index, col_index, id
        LIMIT 320
        """,
        (class_key, spec_key),
    ).fetchall()
    selected = []
    selected_ids = set()
    by_tree = {"class": [], "spec": [], "hero": []}
    for row in rows:
        payload = safe_json_loads(row[4], {})
        if not isinstance(payload, dict):
            payload = {}
        tree_type = payload.get("treeType") or ("class" if row[1] == "class" else "spec")
        if tree_type == "hero" and payload.get("heroKey") != hero_key:
            continue
        if tree_type not in by_tree:
            continue
        node = {
            "id": row[0],
            "treeType": tree_type,
            "row": int(row[2] or 0),
            "col": int(row[3] or 0),
            "rank": max(1, int(payload.get("selectedRank") or payload.get("grantedRank") or 1)),
            "selectedRank": int(payload.get("selectedRank") or 0),
            "grantedRank": int(payload.get("grantedRank") or 0),
            "parentIds": payload.get("parentIds") if isinstance(payload.get("parentIds"), list) else [],
            "pointRequirement": int(payload.get("pointRequirement") or 0),
        }
        by_tree[tree_type].append(node)
        if node["selectedRank"] > 0 or node["grantedRank"] > 0:
            selected.append({"id": node["id"], "rank": node["rank"]})
            selected_ids.add(node["id"])

    for tree_type in ("class", "spec", "hero"):
        if any(item["id"] in selected_ids for item in by_tree[tree_type]):
            continue
        roots = [node for node in by_tree[tree_type] if not node["parentIds"] and node["pointRequirement"] <= 0]
        node = (roots or by_tree[tree_type] or [None])[0]
        if node and node["id"] not in selected_ids:
            selected.append({"id": node["id"], "rank": 1})
            selected_ids.add(node["id"])
    return {"selectedNodes": selected}


def community_talent_rows_from_rank_map(ranks):
    return [
        {"id": node_id, "rank": rank}
        for node_id, rank in sorted((str(key), int(value or 0)) for key, value in (ranks or {}).items())
        if node_id and rank > 0
    ]


def community_talent_baseline_state_from_authority(conn, class_key, spec_key, hero_key):
    talent_payload, nodes_by_id = build_websim_authority_nodes(conn, class_key, spec_key, hero_key)
    nodes = [node for node in talent_payload.get("nodes") or [] if isinstance(node, dict) and node.get("id")]
    tree_sections = talent_payload.get("treeSections") or talent_tree_sections(class_key, spec_key, hero_key)
    point_caps = {
        str(section.get("key") or ""): int(section.get("pointCap") or 0)
        for section in tree_sections
        if isinstance(section, dict) and int(section.get("pointCap") or 0) > 0
    }
    tree_order = {"class": 0, "spec": 1, "hero": 2}
    candidates = sorted(
        nodes,
        key=lambda node: (
            tree_order.get(str(node.get("treeType") or ""), 9),
            int(node.get("pointRequirement") or 0),
            int(node.get("row") or 0),
            int(node.get("col") or 0),
            int(node.get("selectionIndex") or 0),
            str(node.get("id") or ""),
        ),
    )
    ranks = {}
    granted_counts = {"class": 0, "spec": 0, "hero": 0}
    for node in candidates:
        node_id = str(node.get("id") or "")
        tree_type = str(node.get("treeType") or "")
        granted_rank = max(0, int(node.get("grantedRank") or 0))
        if node_id and granted_rank > 0:
            ranks[node_id] = granted_rank
            granted_counts[tree_type] = granted_counts.get(tree_type, 0) + granted_rank
    purchased_targets = {
        tree_type: max(0, int(point_caps.get(tree_type) or 0) - int(granted_counts.get(tree_type) or 0))
        for tree_type in ("class", "spec", "hero")
    }

    last_encoding = None
    for tree_type in ("class", "spec", "hero"):
        target = int(purchased_targets.get(tree_type) or 0)
        if target <= 0:
            continue
        for _attempt in range(max(1, target * 4)):
            selected_rows = community_talent_rows_from_rank_map(ranks)
            _encoded, selected_counts, _errors, _warnings = validate_websim_talent_selection(
                nodes_by_id,
                selected_rows,
                tree_sections,
            )
            if int(selected_counts.get(tree_type) or 0) >= target:
                break
            progressed = False
            for node in candidates:
                if (node.get("treeType") or "") != tree_type:
                    continue
                node_id = str(node.get("id") or "")
                if not node_id:
                    continue
                max_rank = max(1, int(node.get("maxRank") or node.get("rank") or 1))
                current_rank = max(0, int(ranks.get(node_id) or 0))
                if current_rank >= max_rank:
                    continue
                trial_ranks = {**ranks, node_id: current_rank + 1}
                trial_rows = community_talent_rows_from_rank_map(trial_ranks)
                encoded, trial_counts, errors, _warnings = validate_websim_talent_selection(
                    nodes_by_id,
                    trial_rows,
                    tree_sections,
                )
                if errors:
                    continue
                if int(trial_counts.get(tree_type) or 0) > target:
                    continue
                ranks = trial_ranks
                last_encoding = {"encoded": encoded, "selectedCounts": trial_counts, "errors": errors}
                progressed = True
                break
            if not progressed:
                break

    selected_rows = community_talent_rows_from_rank_map(ranks)
    encoded, selected_counts, errors, warnings = validate_websim_talent_selection(
        nodes_by_id,
        selected_rows,
        tree_sections,
    )
    active_counts = {"class": 0, "spec": 0, "hero": 0}
    for row in selected_rows:
        node = nodes_by_id.get(row["id"])
        if not node:
            continue
        tree_type = node.get("treeType") or ("class" if node.get("specKey") == "class" else "spec")
        active_counts[tree_type] = active_counts.get(tree_type, 0) + int(row.get("rank") or 0)
    complete = bool(
        selected_rows
        and not errors
        and all(int(active_counts.get(tree_type) or 0) >= int(point_caps.get(tree_type) or 0) for tree_type in ("class", "spec", "hero"))
    )
    blockers = []
    if not selected_rows:
        blockers.append("no WebSim authority nodes available for baseline template")
    for tree_type in ("class", "spec", "hero"):
        target = int(point_caps.get(tree_type) or 0)
        selected = int(active_counts.get(tree_type) or 0)
        if target and selected < target:
            blockers.append(f"{tree_type} baseline only selected {selected}/{target} talent points")
    blockers.extend(errors or [])
    return {
        "selectedNodes": selected_rows if complete else [],
        "baseline": {
            "complete": complete,
            "targetCounts": point_caps,
            "purchasedTargetCounts": purchased_targets,
            "grantedCounts": granted_counts,
            "selectedCounts": selected_counts,
            "activeSelectedCounts": active_counts,
            "warnings": warnings,
            "blockers": unique_text_list(blockers),
            "lastEncoding": last_encoding or {},
        },
    }


def build_websim_baseline_talent_template(conn, class_key, spec_key, hero_key=""):
    class_key = slugify(class_key, "mage")
    spec_key = slugify(spec_key, "arcane")
    hero_key = hero_tree_for(class_key, spec_key, slugify(hero_key, ""))
    state = community_talent_baseline_state_from_authority(conn, class_key, spec_key, hero_key)
    baseline = state.get("baseline") if isinstance(state.get("baseline"), dict) else {}
    status = "verified" if baseline.get("complete") else "blocked"
    return {
        "id": f"websim-baseline-{class_key}-{spec_key}-{hero_key}",
        "classKey": class_key,
        "specKey": spec_key,
        "heroKey": hero_key,
        "scenarioKey": "mythic_plus",
        "name": f"WebSim 基线-{class_label(class_key)}-{spec_label(spec_key)}-{hero_tree_label(hero_key)}",
        "flowLabel": "基线",
        "sourceKey": "websim_baseline",
        "sourceName": "WebSim 基线模板",
        "sourceUrl": "docs/community-template-import-full-chain-runbook.md",
        "sampleCount": 0,
        "maxKeyLevel": 0,
        "analysisWindow": "backend-authority-baseline",
        "sourceStatus": "synced" if baseline.get("complete") else "partial",
        "status": status,
        "talentState": {"selectedNodes": state.get("selectedNodes") or []},
        "payload": {
            "baseline": baseline,
            "sourceType": "backend_authority_baseline",
        },
        "updatedAt": utc_now(),
        "expiresAt": season_expires_at(),
    }


def load_websim_baseline_talent_templates(conn):
    templates = []
    errors = []
    expected = expected_spec_pairs()
    for klass in WOW_CLASSES:
        class_key = slugify(klass.get("key"), "")
        if not class_key:
            continue
        for spec in klass.get("specs") or []:
            spec_key = slugify(spec, "")
            if not spec_key:
                continue
            hero_key = hero_tree_for(class_key, spec_key, "")
            try:
                template = build_websim_baseline_talent_template(conn, class_key, spec_key, hero_key)
                templates.append(template)
                baseline = (template.get("payload") or {}).get("baseline") or {}
                if not baseline.get("complete"):
                    errors.extend(
                        f"{class_key}:{spec_key}: {blocker}"
                        for blocker in baseline.get("blockers") or ["baseline template incomplete"]
                    )
            except Exception as error:
                errors.append(f"{class_key}:{spec_key}: {error}")
    complete_count = sum(
        1
        for template in templates
        if ((template.get("payload") or {}).get("baseline") or {}).get("complete")
    )
    source_status = "synced" if expected and complete_count >= len(expected) and not errors else ("partial" if complete_count else "blocked")
    return {
        "status": source_status,
        "sourceName": "WebSim 基线模板",
        "templates": templates,
        "errors": unique_text_list(errors)[:80],
    }


def community_talent_structured_loadout(template):
    if not isinstance(template, dict):
        return []
    direct = template.get("loadout")
    if isinstance(direct, list):
        return direct
    talent_loadout = template.get("talentLoadout") if isinstance(template.get("talentLoadout"), dict) else {}
    if isinstance(talent_loadout.get("loadout"), list):
        return talent_loadout.get("loadout")
    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    for key in ("raiderio", "talentLoadout"):
        source = payload.get(key) if isinstance(payload.get(key), dict) else {}
        if isinstance(source.get("loadout"), list):
            return source.get("loadout")
    return []


def positive_int(value):
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        number = 0
    return number if number > 0 else 0


def append_positive_id(ids, value):
    number = positive_int(value)
    if number > 0 and number not in ids:
        ids.append(number)


def zero_based_index(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = -1
    return number if number >= 0 else -1


def append_loadout_node_candidate_ids(ids, node_entry):
    if not isinstance(node_entry, dict):
        return
    for key in (
        "id",
        "traitId",
        "trait_id",
        "traitDefinitionId",
        "trait_definition_id",
        "entryId",
        "entry_id",
        "nodeId",
        "node_id",
        "spellId",
        "spell_id",
    ):
        append_positive_id(ids, node_entry.get(key))
    spell = node_entry.get("spell") if isinstance(node_entry.get("spell"), dict) else {}
    append_positive_id(ids, spell.get("id"))


def community_talent_loadout_candidate_ids(entry):
    if not isinstance(entry, dict):
        return []
    ids = []
    for key in (
        "traitId",
        "trait_id",
        "trait",
        "entryId",
        "entry_id",
        "nodeId",
        "node_id",
        "node",
        "spellId",
        "spell_id",
        "id",
    ):
        append_positive_id(ids, entry.get(key))
    node = entry.get("node") if isinstance(entry.get("node"), dict) else {}
    node_entries = node.get("entries") if isinstance(node.get("entries"), list) else []
    entry_index = zero_based_index(entry.get("entryIndex"))
    selected_entry = None
    if entry_index >= 0 and entry_index < len(node_entries):
        selected_entry = node_entries[entry_index]
        append_loadout_node_candidate_ids(ids, selected_entry)
    append_loadout_node_candidate_ids(ids, node)
    for node_entry in node_entries:
        if node_entry is selected_entry:
            continue
        append_loadout_node_candidate_ids(ids, node_entry)
    return ids


def community_talent_loadout_rank(entry):
    if not isinstance(entry, dict):
        return 1
    for key in ("rank", "points", "selectedRank", "selected_rank"):
        try:
            value = int(entry.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    return 1


def is_hero_tree_selector_loadout_entry(entry):
    if not isinstance(entry, dict):
        return False
    node = entry.get("node") if isinstance(entry.get("node"), dict) else {}
    if positive_int(node.get("type")) != 3:
        return False
    node_entries = node.get("entries") if isinstance(node.get("entries"), list) else []
    if not node_entries:
        return False
    for node_entry in node_entries:
        if not isinstance(node_entry, dict):
            continue
        if isinstance(node_entry.get("spell"), dict):
            return False
        if positive_int(node_entry.get("traitSubTreeId")) > 0:
            return True
    return False


def community_talent_authority_index(conn, class_key, spec_key):
    if hasattr(conn, "community_talent_authority_index"):
        return conn.community_talent_authority_index(class_key, spec_key)
    rows = conn.execute(
        """
        SELECT id, spell_id, payload_json
        FROM websim_talents
        WHERE class_key = ?
          AND (spec_key = ? OR spec_key = 'class')
          AND spell_id > 0
        ORDER BY row_index, col_index, id
        LIMIT 640
        """,
        (class_key, spec_key),
    ).fetchall()
    by_id = {}
    for row in rows:
        payload = safe_json_loads(row[2], {})
        if not isinstance(payload, dict):
            payload = {}
        node = {
            **payload,
            "id": row[0],
            "spellId": int(row[1] or 0),
            "treeType": payload.get("treeType") or ("class" if ":class" in str(row[0]) else payload.get("tree")),
        }
        candidate_ids = {
            positive_int(node.get("spellId")),
            positive_int(payload.get("traitId")),
            positive_int(payload.get("traitDefinitionId")),
            positive_int(payload.get("nodeId")),
            positive_int(payload.get("entryId")),
        }
        for rank_entry in payload.get("rankEntries") or []:
            if not isinstance(rank_entry, dict):
                continue
            for key in ("traitId", "traitDefinitionId", "entryId", "nodeId", "spellId"):
                candidate_ids.add(positive_int(rank_entry.get(key)))
        for candidate_id in candidate_ids:
            if candidate_id > 0:
                by_id.setdefault(candidate_id, []).append(node)
    return by_id


def community_talent_payload_error_texts(payload):
    if not isinstance(payload, dict):
        return []
    texts = []
    for key in ("blockers", "errors"):
        value = payload.get(key)
        if isinstance(value, list):
            texts.extend(str(item) for item in value if str(item or "").strip())
        elif str(value or "").strip():
            texts.append(str(value))
    for key in ("talentLoadoutParse", "talentEncoding"):
        section = payload.get(key) if isinstance(payload.get(key), dict) else {}
        value = section.get("errors")
        if isinstance(value, list):
            texts.extend(str(item) for item in value if str(item or "").strip())
        elif str(value or "").strip():
            texts.append(str(value))
    return unique_text_list(texts)


def community_talent_loadout_spec_blockers(template):
    if not isinstance(template, dict):
        return []
    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    raiderio_payload = payload.get("raiderio") if isinstance(payload.get("raiderio"), dict) else {}
    source_key = slugify(template.get("sourceKey") or payload.get("sourceKey") or "", "")
    if source_key and source_key != "raiderio":
        return []
    if source_key != "raiderio" and not raiderio_payload:
        return []
    candidate_sources = [raiderio_payload, payload, template]
    loadout_spec_id = ""
    for source in candidate_sources:
        if not isinstance(source, dict):
            continue
        loadout_spec_id = source.get("loadoutSpecId") or source.get("loadout_spec_id") or ""
        if loadout_spec_id:
            break
    try:
        numeric_spec_id = int(loadout_spec_id or 0)
    except (TypeError, ValueError):
        numeric_spec_id = 0
    if numeric_spec_id <= 0:
        return []
    actual_pair = SPEC_ID_TO_KEY.get(numeric_spec_id)
    if not actual_pair:
        return []
    class_key = slugify(template.get("classKey"), "")
    spec_key = slugify(template.get("specKey"), "")
    if not class_key or not spec_key:
        return []
    expected = f"{class_key}:{spec_key}"
    actual = f"{actual_pair[0]}:{actual_pair[1]}"
    if actual == expected:
        return []
    return [
        (
            f"Raider.IO talent loadout spec id {loadout_spec_id} resolves to {actual}, "
            f"but the run roster template is {expected}; skipping profile-current talent loadout for this spec."
        )
    ]


def block_community_talent_template(normalized, blockers):
    payload = dict(normalized.get("payload") or {})
    blocker_list = unique_text_list(blockers)
    if blocker_list:
        payload["blockers"] = blocker_list
        payload.setdefault("errors", blocker_list)
    normalized["payload"] = payload
    normalized["status"] = "blocked"
    return refresh_community_talent_identity(normalized)


def resolve_community_talent_structured_loadout(conn, template):
    entries = community_talent_structured_loadout(template)
    if not entries:
        return {"selectedNodes": [], "errors": ["missing structured talent loadout"]}
    class_key = slugify(template.get("classKey"), "mage")
    spec_key = slugify(template.get("specKey"), "arcane")
    requested_hero = slugify(template.get("heroKey"), "")
    authority = community_talent_authority_index(conn, class_key, spec_key)
    def match_loadout(hero_filter):
        selected = []
        selected_ids = set()
        hero_keys = set()
        errors = []
        for entry in entries:
            candidates = []
            candidate_node_ids = set()
            for candidate_id in community_talent_loadout_candidate_ids(entry):
                for candidate in authority.get(candidate_id) or []:
                    node_id = candidate.get("id")
                    if not node_id or node_id in candidate_node_ids:
                        continue
                    candidate_node_ids.add(node_id)
                    candidates.append(candidate)
            chosen = None
            for candidate in candidates:
                tree_type = candidate.get("treeType") or candidate.get("tree")
                candidate_hero = candidate.get("heroKey") or ""
                if tree_type == "hero" and hero_filter and candidate_hero != hero_filter:
                    continue
                chosen = candidate
                break
            if not chosen:
                if is_hero_tree_selector_loadout_entry(entry):
                    continue
                errors.append(f"unknown structured talent entry: {entry}")
                continue
            node_id = chosen.get("id")
            if not node_id or node_id in selected_ids:
                continue
            tree_type = chosen.get("treeType") or chosen.get("tree")
            if tree_type == "hero" and chosen.get("heroKey"):
                hero_keys.add(chosen.get("heroKey"))
            selected_ids.add(node_id)
            selected.append({"id": node_id, "rank": community_talent_loadout_rank(entry)})
        return {
            "selected": selected,
            "heroKeys": hero_keys,
            "errors": errors,
        }

    matched = match_loadout(requested_hero)
    if requested_hero:
        fallback = match_loadout("")
        if fallback["heroKeys"] and (not matched["heroKeys"] or len(fallback["errors"]) < len(matched["errors"])):
            matched = fallback
    selected = matched["selected"]
    hero_keys = matched["heroKeys"]
    errors = matched["errors"]
    if not selected:
        return {"selectedNodes": [], "errors": errors or ["structured talent loadout did not match WebSim nodes"]}
    if not hero_keys:
        errors.append("structured talent loadout did not identify a hero talent tree")
    if len(hero_keys) > 1:
        errors.append(f"structured talent loadout matched multiple hero trees: {', '.join(sorted(hero_keys))}")
    resolved_hero = next(iter(hero_keys), requested_hero or "")
    return {
        "selectedNodes": selected,
        "heroKey": resolved_hero,
        "errors": errors,
    }


def normalize_community_talent_template(template, source_key="unknown", source_status="partial"):
    source = template if isinstance(template, dict) else {}
    class_key = slugify(source.get("classKey"), "mage")
    spec_key = slugify(source.get("specKey"), "arcane")
    hero_key = hero_tree_for(class_key, spec_key, slugify(source.get("heroKey"), ""))
    scenario_key = slugify(source.get("scenarioKey"), "mythic_plus")
    payload = dict(source.get("payload") or {})
    raiderio_payload = payload.get("raiderio") if isinstance(payload.get("raiderio"), dict) else {}
    player_id = str(source.get("playerId") or raiderio_payload.get("characterName") or "").strip()
    labels = {
        "playerId": player_id,
        "classLabel": str(source.get("classLabel") or class_label(class_key)).strip(),
        "specLabel": str(source.get("specLabel") or spec_label(spec_key)).strip(),
        "heroLabel": str(source.get("heroLabel") or hero_tree_label(hero_key)).strip(),
        "scenarioTitle": str(source.get("scenarioTitle") or scenario_title(scenario_key)).strip(),
    }
    raw_import_code = external_talent_import_code({
        "talents": source.get("rawImportCode") or source.get("talents") or source.get("talentImport") or ""
    })
    state = community_talent_state(source)
    websim_export_code = community_talent_export_code({
        **source,
        "classKey": class_key,
        "specKey": spec_key,
        "heroKey": hero_key,
        "talentState": state,
    })
    now = utc_now()
    name = str(source.get("name") or "community talent template").strip()
    if source_key == "raiderio" and player_id:
        name = "-".join([
            player_id,
            labels["classLabel"],
            labels["heroLabel"],
            labels["specLabel"],
            labels["scenarioTitle"],
        ])
    status = str(source.get("status") or "blocked").strip()
    if status == "verified" and raw_import_code and not community_talent_selected_nodes({"talentState": state}):
        status = "blocked"
    payload.update({
        "sourceKey": source_key,
        "sourceStatus": source.get("sourceStatus") or source_status,
        **{key: value for key, value in labels.items() if value},
    })
    normalized = {
        "id": slugify(source.get("id"), f"{source_key}-{class_key}-{spec_key}-{hero_key or 'default'}-{scenario_key}"),
        "classKey": class_key,
        "specKey": spec_key,
        "heroKey": hero_key,
        "scenarioKey": scenario_key,
        "flowLabel": str(source.get("flowLabel") or "主流").strip(),
        "sourceKey": source_key,
        "sourceName": str(source.get("sourceName") or source_key).strip(),
        "name": name,
        "sourceUrl": str(source.get("sourceUrl") or "").strip(),
        "rawImportCode": raw_import_code,
        "websimExportCode": websim_export_code,
        "talentState": state,
        "sampleCount": int(source.get("sampleCount") or 0),
        "maxKeyLevel": int(source.get("maxKeyLevel") or 0),
        "analysisWindow": str(source.get("analysisWindow") or "").strip(),
        "sourceStatus": str(source.get("sourceStatus") or source_status or "partial").strip(),
        "status": status,
        "payload": payload,
        "playerId": labels["playerId"],
        "classLabel": labels["classLabel"],
        "specLabel": labels["specLabel"],
        "heroLabel": labels["heroLabel"],
        "scenarioTitle": labels["scenarioTitle"],
        "updatedAt": str(source.get("updatedAt") or now).strip(),
        "expiresAt": str(source.get("expiresAt") or season_expires_at()).strip(),
    }
    normalized["signature"] = str(source.get("signature") or community_talent_signature(normalized)).strip()
    normalized["sourceRefs"] = normalize_source_refs(source.get("sourceRefs") or [community_talent_source_ref(normalized)])
    normalized["scanRunId"] = str(source.get("scanRunId") or source.get("scan_run_id") or "").strip()
    return normalized


def refresh_community_talent_identity(template):
    if not isinstance(template, dict):
        return template
    class_key = slugify(template.get("classKey"), "mage")
    spec_key = slugify(template.get("specKey"), "arcane")
    hero_key = hero_tree_for(class_key, spec_key, slugify(template.get("heroKey"), ""))
    scenario_key = slugify(template.get("scenarioKey"), "mythic_plus")
    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    raiderio_payload = payload.get("raiderio") if isinstance(payload.get("raiderio"), dict) else {}
    player_id = str(template.get("playerId") or payload.get("playerId") or raiderio_payload.get("characterName") or "").strip()
    labels = {
        "playerId": player_id,
        "classLabel": class_label(class_key),
        "specLabel": spec_label(spec_key),
        "heroLabel": hero_tree_label(hero_key),
        "scenarioTitle": scenario_title(scenario_key),
    }
    template["heroKey"] = hero_key
    template.update(labels)
    payload.update({key: value for key, value in labels.items() if value})
    template["payload"] = payload
    if template.get("sourceKey") == "raiderio" and player_id:
        template["name"] = "-".join([
            player_id,
            labels["classLabel"],
            labels["heroLabel"],
            labels["specLabel"],
            labels["scenarioTitle"],
        ])
    template["signature"] = community_talent_signature(template)
    template["sourceRefs"] = normalize_source_refs(template.get("sourceRefs") or [community_talent_source_ref(template)])
    return template


def encoding_has_unknown_talent_nodes(encoding):
    return any(str(error).startswith("unknown talent node:") for error in (encoding or {}).get("errors") or [])


def validate_community_talent_template(conn, template):
    normalized = normalize_community_talent_template(template, template.get("sourceKey", "unknown"), template.get("sourceStatus", "partial"))
    existing_blockers = unique_text_list([
        *community_talent_loadout_spec_blockers(normalized),
        *community_talent_payload_error_texts(normalized.get("payload")),
    ])
    if existing_blockers:
        return block_community_talent_template(normalized, existing_blockers)
    if not community_talent_selected_nodes(normalized):
        parsed_loadout = resolve_community_talent_structured_loadout(conn, normalized)
        if parsed_loadout.get("selectedNodes") and parsed_loadout.get("heroKey") and not parsed_loadout.get("errors"):
            normalized["heroKey"] = parsed_loadout["heroKey"]
            normalized["talentState"] = {"selectedNodes": parsed_loadout["selectedNodes"]}
            normalized["websimExportCode"] = community_talent_export_code({**normalized, "websimExportCode": ""})
            normalized.setdefault("payload", {})["talentLoadoutParse"] = {
                "status": "parsed",
                "source": "structured_loadout",
                "nodeCount": len(parsed_loadout["selectedNodes"]),
                "heroKey": parsed_loadout["heroKey"],
            }
            refresh_community_talent_identity(normalized)
        elif normalized.get("rawImportCode"):
            normalized.setdefault("payload", {})["talentLoadoutParse"] = {
                "status": "blocked",
                "source": "raw_import_code",
                "errors": parsed_loadout.get("errors") or ["raw talent import code could not be parsed into WebSim nodes"],
            }
    if community_talent_selected_nodes(normalized):
        encoding = encode_websim_talents(conn, {
            "classKey": normalized["classKey"],
            "specKey": normalized["specKey"],
            "heroKey": normalized["heroKey"],
            "talentState": normalized["talentState"],
        })
        if normalized["sourceKey"] == "manual_fixture" and encoding_has_unknown_talent_nodes(encoding):
            normalized["talentState"] = community_talent_default_state_from_db(
                conn,
                normalized["classKey"],
                normalized["specKey"],
                normalized["heroKey"],
            )
            normalized["websimExportCode"] = community_talent_export_code({**normalized, "websimExportCode": ""})
            encoding = encode_websim_talents(conn, {
                "classKey": normalized["classKey"],
                "specKey": normalized["specKey"],
                "heroKey": normalized["heroKey"],
                "talentState": normalized["talentState"],
            })
        normalized["payload"]["talentEncoding"] = encoding
        normalized["status"] = "verified" if encoding.get("status") == "encoded" else "blocked"
        if encoding.get("errors"):
            normalized["payload"]["errors"] = encoding.get("errors")
            normalized["payload"]["blockers"] = encoding.get("errors")
    elif normalized["rawImportCode"]:
        normalized["status"] = "blocked"
        normalized["payload"]["errors"] = (
            normalized["payload"].get("talentLoadoutParse", {}).get("errors")
            or ["raw talent import code could not be parsed into WebSim nodes"]
        )
        normalized["payload"]["blockers"] = normalized["payload"]["errors"]
    else:
        normalized["status"] = "blocked"
        normalized["payload"]["errors"] = ["missing WebSim talent state or external talents import code"]
        normalized["payload"]["blockers"] = normalized["payload"]["errors"]
    return refresh_community_talent_identity(normalized)


def upsert_community_talent_template(conn, template):
    ensure_websim_tables(conn)
    normalized = normalize_community_talent_template(
        template,
        template.get("sourceKey", "unknown") if isinstance(template, dict) else "unknown",
        template.get("sourceStatus", "partial") if isinstance(template, dict) else "partial",
    )
    conn.execute(
        """
        INSERT INTO websim_community_talent_templates (
            id, class_key, spec_key, hero_key, scenario_key, name, flow_label,
            source_key, source_name, source_url, raw_import_code, websim_export_code,
            talent_state_json, sample_count, max_key_level, analysis_window,
            source_status, status, payload_json, updated_at, expires_at,
            signature, source_refs_json, scan_run_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            class_key=excluded.class_key,
            spec_key=excluded.spec_key,
            hero_key=excluded.hero_key,
            scenario_key=excluded.scenario_key,
            name=excluded.name,
            flow_label=excluded.flow_label,
            source_key=excluded.source_key,
            source_name=excluded.source_name,
            source_url=excluded.source_url,
            raw_import_code=excluded.raw_import_code,
            websim_export_code=excluded.websim_export_code,
            talent_state_json=excluded.talent_state_json,
            sample_count=excluded.sample_count,
            max_key_level=excluded.max_key_level,
            analysis_window=excluded.analysis_window,
            source_status=excluded.source_status,
            status=excluded.status,
            payload_json=excluded.payload_json,
            updated_at=excluded.updated_at,
            expires_at=excluded.expires_at,
            signature=excluded.signature,
            source_refs_json=excluded.source_refs_json,
            scan_run_id=excluded.scan_run_id
        """,
        (
            normalized["id"],
            normalized["classKey"],
            normalized["specKey"],
            normalized["heroKey"],
            normalized["scenarioKey"],
            normalized["name"],
            normalized["flowLabel"],
            normalized["sourceKey"],
            normalized["sourceName"],
            normalized["sourceUrl"],
            normalized["rawImportCode"],
            normalized["websimExportCode"],
            json.dumps(normalized["talentState"], ensure_ascii=False),
            normalized["sampleCount"],
            normalized["maxKeyLevel"],
            normalized["analysisWindow"],
            normalized["sourceStatus"],
            normalized["status"],
            json.dumps(normalized["payload"], ensure_ascii=False),
            normalized["updatedAt"],
            normalized["expiresAt"],
            normalized["signature"],
            json.dumps(normalized["sourceRefs"], ensure_ascii=False),
            normalized["scanRunId"],
        ),
    )
    return normalized


def get_websim_community_talent_templates(conn, class_key="mage", spec_key="arcane", hero_key=""):
    ensure_websim_tables(conn)
    class_key = slugify(class_key, "mage")
    spec_key = slugify(spec_key, "arcane")
    rows = conn.execute(
        """
        SELECT id, class_key, spec_key, hero_key, scenario_key, name, flow_label,
               source_key, source_name, source_url, raw_import_code, websim_export_code,
               talent_state_json, sample_count, max_key_level, analysis_window,
               source_status, status, payload_json, updated_at, expires_at,
               signature, source_refs_json, scan_run_id
        FROM websim_community_talent_templates
        WHERE class_key = ?
          AND spec_key = ?
          AND status = 'verified'
          AND expires_at > ?
        ORDER BY max_key_level DESC, sample_count DESC, hero_key, name
        LIMIT 240
        """,
        (class_key, spec_key, utc_now()),
    ).fetchall()
    templates = []
    for row in rows:
        talent_state = safe_json_loads(row[12], {"selectedNodes": []})
        if not isinstance(talent_state, dict):
            talent_state = {"selectedNodes": []}
        payload = safe_json_loads(row[18], {})
        websim_export_code = row[11] or ""
        raw_import_code = row[10] or ""
        selected_nodes = talent_state.get("selectedNodes") if isinstance(talent_state.get("selectedNodes"), list) else []
        can_apply_visual = bool(websim_export_code.startswith("websim:") and selected_nodes)
        raiderio_payload = payload.get("raiderio") if isinstance(payload.get("raiderio"), dict) else {}
        player_id = str(payload.get("playerId") or raiderio_payload.get("characterName") or "").strip()
        templates.append({
            "id": row[0],
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
            "sampleCount": int(row[13] or 0),
            "maxKeyLevel": int(row[14] or 0),
            "analysisWindow": row[15],
            "sourceStatus": row[16],
            "status": row[17],
            "payload": payload,
            "signature": row[21] or "",
            "sourceRefs": normalize_source_refs(safe_json_loads(row[22], []) or []),
            "scanRunId": row[23] or "",
            "playerId": player_id,
            "classLabel": payload.get("classLabel") or class_label(row[1]),
            "specLabel": payload.get("specLabel") or spec_label(row[2]),
            "heroLabel": payload.get("heroLabel") or hero_tree_label(row[3]),
            "scenarioTitle": payload.get("scenarioTitle") or scenario_title(row[4]),
            "updatedAt": row[19],
            "expiresAt": row[20],
            "canApplyVisual": can_apply_visual,
            "canUseInSimc": bool(can_apply_visual or raw_import_code),
        })
    deduped = dedupe_community_talent_templates_for_display(templates)
    return deduped[:COMMUNITY_TALENT_TEMPLATE_LIMIT_PER_SPEC]


def websim_talent_import_response(class_key, spec_key, hero_key="", template=None, blockers=None):
    class_key = slugify(class_key, "mage")
    spec_key = slugify(spec_key, "arcane")
    hero_key = hero_tree_for(class_key, spec_key, slugify(hero_key, ""))
    if isinstance(template, dict):
        import_code = str(template.get("rawImportCode") or template.get("importCode") or template.get("talentImport") or "").strip()
        if import_code and template.get("canUseInSimc") is not False and template.get("status") != "blocked":
            return {
                "schemaRevision": "websim-talent-import-v1",
                "classKey": class_key,
                "specKey": spec_key,
                "heroKey": hero_key,
                "importCode": import_code,
                "source": "community_template",
                "sourceKey": template.get("sourceKey") or "",
                "sourceName": template.get("sourceName") or "",
                "templateId": template.get("id") or "",
                "status": "verified",
                "blockers": [],
            }
    return {
        "schemaRevision": "websim-talent-import-v1",
        "classKey": class_key,
        "specKey": spec_key,
        "heroKey": hero_key,
        "importCode": "",
        "source": "community_template",
        "status": "blocked",
        "blockers": blockers or ["no SimC-ready community talent import"],
    }


def get_websim_talent_import(conn, class_key="mage", spec_key="arcane", hero_key=""):
    ensure_websim_tables(conn)
    season = get_active_season_payload(conn)
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
    row = conn.execute(
        """
        SELECT id, class_key, spec_key, hero_key, scenario_key, name,
               source_key, source_name, source_url, raw_import_code,
               source_status, status, sample_count, max_key_level,
               analysis_window, updated_at
        FROM websim_community_talent_templates
        WHERE class_key = ?
          AND spec_key = ?
          AND status = 'verified'
          AND raw_import_code <> ''
          AND expires_at > ?
        ORDER BY CASE WHEN hero_key = ? THEN 0 ELSE 1 END,
                 max_key_level DESC, sample_count DESC, hero_key, name
        LIMIT 1
        """,
        (class_key, spec_key, utc_now(), hero_key),
    ).fetchone()
    template = None
    if row:
        template = {
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
            "sampleCount": int(row[12] or 0),
            "maxKeyLevel": int(row[13] or 0),
            "analysisWindow": row[14] or "",
            "updatedAt": row[15] or "",
            "canUseInSimc": True,
        }
    return websim_talent_import_response(
        class_key,
        spec_key,
        hero_key,
        template=template,
    )


def delete_community_talent_template_sources(conn, source_keys):
    keys = [str(source_key or "").strip() for source_key in source_keys or [] if str(source_key or "").strip()]
    if not keys:
        return {"deleted": 0}
    placeholders = ",".join("?" for _ in keys)
    cursor = conn.execute(
        f"DELETE FROM websim_community_talent_templates WHERE source_key IN ({placeholders})",
        keys,
    )
    return {"deleted": cursor.rowcount if cursor.rowcount is not None else 0}


def sync_community_talent_templates(conn):
    ensure_websim_tables(conn)
    delete_community_talent_template_sources(conn, disabled_community_talent_template_source_keys())
    try:
        from .community_talent_sources import raiderio, warcraftlogs
    except ImportError:
        from community_talent_sources import raiderio, warcraftlogs

    adapters = {
        "raiderio": raiderio.load_templates,
        "warcraftlogs": warcraftlogs.load_templates,
    }
    if include_websim_baseline_talent_sources():
        adapters["websim_baseline"] = load_websim_baseline_talent_templates
    if include_manual_fixture_sources():
        try:
            from .community_talent_sources import manual_fixture
        except ImportError:
            from community_talent_sources import manual_fixture
        adapters = {"manual_fixture": manual_fixture.load_templates, **adapters}
    sources = {}
    verified = 0
    blocked = 0
    total = 0
    for source_key, loader in adapters.items():
        try:
            try:
                result = loader(conn)
            except TypeError:
                result = loader()
        except Exception as error:
            result = {"status": "blocked", "sourceName": source_key, "templates": [], "errors": [str(error)]}
        sources[source_key] = {
            "status": result.get("status") or "blocked",
            "sourceName": result.get("sourceName") or source_key,
            "errors": result.get("errors") or [],
        }
        for raw_template in result.get("templates") or []:
            template = validate_community_talent_template(conn, {
                **raw_template,
                "sourceKey": source_key,
                "sourceStatus": "partial" if result.get("status") == "synced" and source_key == "manual_fixture" else result.get("status"),
            })
            upsert_community_talent_template(conn, template)
            total += 1
            if template["status"] == "verified":
                verified += 1
            else:
                blocked += 1

    missing_external = any(sources[key]["status"] == "missing_credentials" for key in ("raiderio", "warcraftlogs"))
    if verified and missing_external:
        source_status = "partial"
    elif verified:
        source_status = "synced"
    elif missing_external:
        source_status = "missing_credentials"
    else:
        source_status = "blocked"
    stats = community_talent_template_stats(conn)
    payload = {
        "sourceStatus": source_status,
        "sources": sources,
        "templates": {"total": total, "verified": verified, "blocked": blocked},
        "templateRevision": stats["templateRevision"],
        "scanCoverage": stats["scanCoverage"],
        "dedupedCount": stats["dedupedCount"],
        "hiddenDuplicateCount": stats["hiddenDuplicateCount"],
        "checkedAt": utc_now(),
    }
    set_sync_state(conn, COMMUNITY_TALENT_SYNC_KEY, payload)
    return payload


def websim_item_metadata_by_ids(conn, item_ids):
    values = sorted({str(item_id or "").strip() for item_id in item_ids or [] if str(item_id or "").strip()})
    if not values:
        return {}
    placeholders = ",".join("?" for _ in values)
    rows = conn.execute(
        f"""
        SELECT id, name, slot, quality, icon_url, payload_json
        FROM websim_items
        WHERE id IN ({placeholders})
        """,
        values,
    ).fetchall()
    result = {}
    for row in rows:
        payload = safe_json_loads(row[5], {})
        metadata = payload.get("_metadata") if isinstance(payload, dict) else {}
        metadata_status = (metadata or {}).get("metadataStatus") or (metadata or {}).get("status") or "verified"
        item_stats = extract_item_stats_from_payload(payload)
        stat_summary = item_stat_summary(item_stats)
        mod_capabilities = item_mod_capabilities(payload, row[2] or "")
        game_asset = normalize_game_asset(
            (metadata or {}).get("gameAsset") if isinstance(metadata, dict) else {},
            game_asset_from_icon_url(
                "item",
                row[0],
                "websim-item-metadata",
                row[4] or "",
                source=(metadata or {}).get("source") or ITEM_METADATA_SOURCE,
                status=metadata_status,
                semantic_tags=["game", "gear", "item", row[2] or ""],
                usage=["websim_gear", "builds_detail", "websim_loot"],
                fallback_text=fallback_text_for(row[1]),
            ),
        )
        result[str(row[0])] = {
            "itemId": str(row[0]),
            "displayName": row[1] or f"Item {row[0]}",
            "slot": row[2] or "",
            "quality": row[3] or "",
            "iconUrl": row[4] or "",
            "gameAsset": game_asset,
            "payload": payload,
            "itemStats": item_stats,
            "statSummary": stat_summary,
            "modCapabilities": mod_capabilities,
            "metadataStatus": metadata_status,
            "metadataSource": (metadata or {}).get("source") or ITEM_METADATA_SOURCE,
            "metadataLocale": (metadata or {}).get("locale") or DEFAULT_LOCALE,
            "englishName": (metadata or {}).get("englishName") or "",
        }
    return result


def websim_item_metadata_by_aliases(conn, aliases):
    alias_keys = sorted({normalized_item_alias(alias) for alias in aliases or [] if normalized_item_alias(alias)})
    if not alias_keys:
        return {}
    placeholders = ",".join("?" for _ in alias_keys)
    rows = conn.execute(
        f"""
        SELECT a.alias_key, a.item_id, a.display_name, a.icon_url, a.source, a.target_locale,
               i.slot, i.quality, i.payload_json
        FROM websim_item_aliases a
        LEFT JOIN websim_items i ON i.id = a.item_id
        WHERE a.alias_key IN ({placeholders})
        ORDER BY a.updated_at DESC
        """,
        alias_keys,
    ).fetchall()
    result = {}
    for row in rows:
        if row[0] in result:
            continue
        payload = safe_json_loads(row[8], {})
        metadata = payload.get("_metadata") if isinstance(payload, dict) else {}
        metadata_status = (metadata or {}).get("metadataStatus") or (metadata or {}).get("status") or "verified"
        item_stats = extract_item_stats_from_payload(payload)
        stat_summary = item_stat_summary(item_stats)
        mod_capabilities = item_mod_capabilities(payload, row[6] or "")
        type_metadata = item_type_metadata_from_payload(payload)
        game_asset = normalize_game_asset(
            (metadata or {}).get("gameAsset") if isinstance(metadata, dict) else {},
            game_asset_from_icon_url(
                "item",
                row[1],
                "websim-item-metadata",
                row[3] or "",
                source=row[4] or (metadata or {}).get("source") or ITEM_METADATA_SOURCE,
                status=metadata_status,
                semantic_tags=["game", "gear", "item", row[6] or ""],
                usage=["websim_gear", "builds_detail", "websim_loot"],
                fallback_text=fallback_text_for(row[2]),
            ),
        )
        result[row[0]] = {
            "itemId": str(row[1]),
            "displayName": row[2] or f"Item {row[1]}",
            "slot": row[6] or "",
            "quality": row[7] or "",
            "iconUrl": row[3] or "",
            "gameAsset": game_asset,
            "payload": payload,
            "itemStats": item_stats,
            "statSummary": stat_summary,
            "modCapabilities": mod_capabilities,
            **type_metadata,
            "metadataStatus": metadata_status,
            "metadataSource": row[4] or ITEM_METADATA_SOURCE,
            "metadataLocale": row[5] or (metadata or {}).get("locale") or DEFAULT_LOCALE,
            "englishName": (metadata or {}).get("englishName") or "",
        }
    return result


def apply_item_metadata(item, metadata=None):
    if not isinstance(item, dict):
        return item
    enriched = dict(item)
    if enriched.get("isReference") or enriched.get("metadataStatus") == "source_reference":
        enriched.setdefault("displayName", enriched.get("name") or "")
        enriched.setdefault("iconUrl", "")
        enriched["gameAsset"] = normalize_game_asset(
            enriched.get("gameAsset"),
            game_asset_from_icon_url(
                "item",
                enriched.get("itemId") or enriched.get("id") or slugify(enriched.get("displayName"), "reference"),
                "source-reference",
                enriched.get("iconUrl") or "",
                source=enriched.get("sourceName") or enriched.get("metadataSource") or "source_reference",
                status="missing",
                semantic_tags=["game", "gear", "item", "reference"],
                usage=["builds_detail"],
                fallback_text=fallback_text_for(enriched.get("displayName")),
            ),
        )
        enriched["metadataStatus"] = "source_reference"
        enriched["metadataSource"] = enriched.get("metadataSource") or enriched.get("sourceName") or ""
        enriched["metadataLocale"] = ""
        return enriched
    item_id = str(enriched.get("itemId") or enriched.get("item_id") or enriched.get("id") or "").strip()
    if metadata:
        metadata_status = metadata.get("metadataStatus") or "verified"
        enriched["itemId"] = metadata.get("itemId") or item_id
        if not enriched.get("id") or str(enriched.get("id")) == item_id:
            enriched["id"] = enriched["itemId"]
        enriched["displayName"] = metadata.get("displayName") or enriched.get("displayName") or enriched.get("name")
        enriched["localizedName"] = enriched["displayName"]
        game_asset = normalize_game_asset(
            metadata.get("gameAsset"),
            game_asset_from_icon_url(
                "item",
                enriched["itemId"],
                "websim-item-metadata",
                metadata.get("iconUrl") or enriched.get("iconUrl") or enriched.get("icon_url") or "",
                source=metadata.get("metadataSource") or ITEM_METADATA_SOURCE,
                status=metadata_status,
                semantic_tags=["game", "gear", "item", metadata.get("slot") or enriched.get("slot") or ""],
                usage=["websim_gear", "builds_detail", "websim_loot"],
                fallback_text=fallback_text_for(enriched["displayName"]),
            ),
        )
        enriched["gameAsset"] = game_asset
        enriched["iconUrl"] = game_asset.get("iconUrl") or metadata.get("iconUrl") or enriched.get("iconUrl") or enriched.get("icon_url") or ""
        enriched["quality"] = metadata.get("quality") or enriched.get("quality") or ""
        enriched["metadataStatus"] = metadata_status
        enriched["metadataSource"] = metadata.get("metadataSource") or ITEM_METADATA_SOURCE
        enriched["metadataLocale"] = metadata.get("metadataLocale") or DEFAULT_LOCALE
        if isinstance(metadata.get("payload"), dict):
            enriched["payload"] = metadata.get("payload")
        if (
            metadata.get("itemStats")
            and not (
                enriched.get("statDisplayStatus") == "verified_variant"
                and enriched.get("itemStats")
            )
        ):
            enriched["itemStats"] = metadata.get("itemStats")
            enriched["stats"] = metadata.get("itemStats")
            enriched["statSummary"] = metadata.get("statSummary") or item_stat_summary(metadata.get("itemStats"))
        if metadata.get("modCapabilities"):
            enriched["modCapabilities"] = metadata.get("modCapabilities")
        for key in ("armorType", "weaponType", "itemSetName", "supportsSocket"):
            if metadata.get(key) not in (None, "", []):
                enriched[key] = metadata.get(key)
        if metadata.get("englishName"):
            enriched["englishName"] = metadata.get("englishName")
        return enriched
    enriched.setdefault("displayName", enriched.get("name") or (f"Item {item_id}" if item_id else ""))
    enriched.setdefault("iconUrl", enriched.get("icon_url") or "")
    enriched["gameAsset"] = normalize_game_asset(
        enriched.get("gameAsset"),
        game_asset_from_icon_url(
            "item",
            item_id or slugify(enriched.get("displayName"), "item"),
            "websim-item-metadata",
            enriched.get("iconUrl") or "",
            source=enriched.get("metadataSource") or "pending_sync",
            status="pending_sync" if item_id else "missing",
            semantic_tags=["game", "gear", "item", enriched.get("slot") or ""],
            usage=["websim_gear", "builds_detail"],
            fallback_text=fallback_text_for(enriched.get("displayName")),
        ),
    )
    enriched["metadataStatus"] = "pending_sync" if item_id else "missing_item_id"
    enriched["metadataSource"] = ""
    enriched["metadataLocale"] = ""
    return enriched


def hydrate_gear_items_from_metadata(conn, items):
    if not items:
        return []
    ids = [item.get("itemId") or item.get("item_id") or item.get("id") for item in items if isinstance(item, dict)]
    metadata_by_id = websim_item_metadata_by_ids(conn, ids)
    hydrated = []
    for item in items:
        if not isinstance(item, dict):
            hydrated.append(item)
            continue
        item_id = str(item.get("itemId") or item.get("item_id") or item.get("id") or "").strip()
        hydrated.append(apply_item_metadata(item, metadata_by_id.get(item_id)))
    return hydrated


def build_related_item_metadata(row, metadata_by_alias):
    parts = split_item_name_parts(row.get("name") if isinstance(row, dict) else "")
    if len(parts) <= 1:
        return []
    related = []
    seen = set()
    for part in parts:
        metadata = None
        for alias in item_alias_candidates(part):
            metadata = metadata_by_alias.get(normalized_item_alias(alias))
            if metadata:
                break
        if not metadata:
            continue
        item_id = str(metadata.get("itemId") or "")
        if item_id in seen:
            continue
        seen.add(item_id)
        related.append(metadata)
    return related


def apply_related_item_metadata(row, related_items):
    if not related_items:
        return row
    enriched = dict(row)
    enriched["relatedItems"] = [
        {
            "itemId": item.get("itemId") or "",
            "displayName": item.get("displayName") or "",
            "englishName": item.get("englishName") or "",
            "iconUrl": item.get("iconUrl") or "",
            "gameAsset": item.get("gameAsset") or game_asset_from_icon_url(
                "item",
                item.get("itemId") or "",
                "websim-item-metadata",
                item.get("iconUrl") or "",
                source=item.get("metadataSource") or ITEM_METADATA_SOURCE,
                status="verified",
                semantic_tags=["game", "gear", "item"],
                usage=["builds_detail"],
                fallback_text=fallback_text_for(item.get("displayName")),
            ),
            "quality": item.get("quality") or "",
            "metadataStatus": item.get("metadataStatus") or "verified",
            "metadataLocale": item.get("metadataLocale") or DEFAULT_LOCALE,
        }
        for item in related_items
    ]
    display_names = [item.get("displayName") for item in enriched["relatedItems"] if item.get("displayName")]
    if display_names:
        enriched["displayName"] = " / ".join(display_names)
        enriched["localizedName"] = enriched["displayName"]
    if row.get("name"):
        enriched["englishName"] = row.get("name")
    return enriched


def enrich_build_gear_payload(conn, payload):
    if not isinstance(payload, dict):
        return payload
    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    gear_detail = details.get("gear") if isinstance(details.get("gear"), dict) else {}
    rows = gear_detail.get("gear") if isinstance(gear_detail.get("gear"), list) else []
    if not rows:
        return payload
    ids = [row.get("itemId") or row.get("item_id") or row.get("id") for row in rows if isinstance(row, dict)]
    aliases = []
    for row in rows:
        if isinstance(row, dict):
            aliases.extend(item_alias_candidates(row.get("name"), row.get("displayName"), row.get("englishName")))
    metadata_by_id = websim_item_metadata_by_ids(conn, ids)
    metadata_by_alias = websim_item_metadata_by_aliases(conn, aliases)
    enriched_rows = []
    verified_count = 0
    reference_count = 0
    for row in rows:
        if not isinstance(row, dict):
            enriched_rows.append(row)
            continue
        item_id = str(row.get("itemId") or row.get("item_id") or row.get("id") or "").strip()
        metadata = metadata_by_id.get(item_id)
        if not metadata:
            for alias in item_alias_candidates(row.get("name"), row.get("displayName"), row.get("englishName")):
                metadata = metadata_by_alias.get(normalized_item_alias(alias))
                if metadata:
                    break
        enriched = apply_item_metadata(row, metadata)
        related_items = build_related_item_metadata(row, metadata_by_alias)
        if len(related_items) > 1:
            enriched = apply_related_item_metadata(enriched, related_items)
        if metadata:
            verified_count += 1
        if enriched.get("metadataStatus") == "source_reference":
            reference_count += 1
        enriched_rows.append(enriched)
    next_payload = dict(payload)
    next_details = dict(details)
    next_gear_detail = dict(gear_detail)
    next_gear_detail["gear"] = enriched_rows
    next_gear_detail["metadataSummary"] = {
        "verifiedCount": verified_count,
        "totalCount": len(enriched_rows),
        "itemCount": len(enriched_rows) - reference_count,
        "referenceCount": reference_count,
        "source": ITEM_METADATA_SOURCE,
        "locale": DEFAULT_LOCALE,
    }
    next_details["gear"] = next_gear_detail
    next_payload["details"] = next_details
    return next_payload


def catalog_status_from_counts(verified_count, partial_count, blocked_count, item_count):
    if blocked_count:
        return "partial" if verified_count or partial_count else "blocked"
    if partial_count:
        return "partial"
    if verified_count and item_count:
        return "verified"
    return "blocked"


def gear_catalog_slot_coverage(conn):
    rows = conn.execute(
        """
        SELECT item_id, slot FROM websim_gear_variants
        UNION ALL
        SELECT id AS item_id, slot FROM websim_items
        WHERE id IN (
            SELECT item_id FROM websim_gear_sources
            UNION
            SELECT item_id FROM websim_gear_variants
        )
        """
    ).fetchall()
    slot_items = {}
    for item_id, raw_slot in rows:
        slot = normalize_slot(raw_slot)
        if not slot:
            continue
        slot_items.setdefault(slot, set()).add(str(item_id))
    items_by_slot = {slot: len(values) for slot, values in sorted(slot_items.items())}
    covered_slots = [slot for slot in CANONICAL_GEAR_SLOTS if slot in slot_items]
    return {
        "coveredSlotCount": len(covered_slots),
        "totalSlotCount": len(CANONICAL_GEAR_SLOTS),
        "coveredSlots": covered_slots,
        "missingSlots": [slot for slot in CANONICAL_GEAR_SLOTS if slot not in slot_items],
        "itemsBySlot": items_by_slot,
    }


def gear_catalog_source_coverage(conn):
    rows = conn.execute(
        """
        SELECT source_type, COUNT(*)
        FROM websim_gear_sources
        GROUP BY source_type
        ORDER BY source_type
        """
    ).fetchall()
    return {str(source_type or "unknown"): int(count or 0) for source_type, count in rows}


def gear_catalog_slot_matches_item_metadata(payload, expected_slot, catalog_slot):
    expected_slot = normalize_slot(expected_slot)
    catalog_slot = normalize_slot(catalog_slot)
    if not expected_slot or not catalog_slot:
        return True
    if catalog_slot == expected_slot:
        return True
    if catalog_slot in EQUIVALENT_GEAR_SLOTS.get(expected_slot, []):
        return True
    inventory_type = (payload or {}).get("inventory_type") if isinstance(payload, dict) else {}
    inventory_type = inventory_type if isinstance(inventory_type, dict) else {}
    type_key = re.sub(r"[^a-z0-9_]+", "_", str(inventory_type.get("type") or "").lower()).strip("_")
    type_key = re.sub(r"^invtype_", "", type_key)
    if type_key == "weapon" and {expected_slot, catalog_slot} <= {"main_hand", "off_hand"}:
        return True
    return False


def gear_mod_option_is_visible(option_id="", option_name="", payload=None):
    option_id = str(option_id or "").strip()
    option_name = str(option_name or "").strip()
    payload = payload if isinstance(payload, dict) else {}
    if option_id in STALE_PLACEHOLDER_GEAR_MOD_OPTION_IDS:
        return False
    if option_name.lower().startswith("server seed"):
        return False
    if payload.get("source") == "server_default_seed":
        return False
    return True


def gear_catalog_mod_option_coverage(conn):
    rows = conn.execute(
        """
        SELECT id, option_type, name, applicable_slots_json, simc_options_json, payload_json, status
        FROM websim_gear_mod_options
        WHERE option_type IN ('socket', 'enchant', 'crafted_stats', 'embellishment')
        """
    ).fetchall()
    coverage = {
        "socket": {"optionCount": 0, "coveredSlotCount": 0, "coveredSlots": []},
        "enchant": {"optionCount": 0, "coveredSlotCount": 0, "coveredSlots": []},
        "crafted_stats": {"optionCount": 0, "coveredSlotCount": 0, "coveredSlots": []},
        "embellishment": {"optionCount": 0, "coveredSlotCount": 0, "coveredSlots": []},
    }
    slots_by_type = {"socket": set(), "enchant": set(), "crafted_stats": set(), "embellishment": set()}
    missing_socket_metadata = []
    invalid_socket_gem_metadata = []
    missing_socket_stat_display = []
    missing_named_display = {"enchant": [], "embellishment": []}
    excluded_named_options = {"enchant": []}
    for option_id, option_type, option_name, slots_json, simc_options_json, payload_json, option_status in rows:
        payload = safe_json_loads(payload_json, {})
        if not gear_mod_option_is_visible(option_id, option_name, payload):
            continue
        option_key = str(option_type or "").strip()
        if option_key not in coverage:
            continue
        simc_options = safe_json_loads(simc_options_json, {})
        simc_options = simc_options if isinstance(simc_options, dict) else {}
        if not gear_mod_option_is_supported_config_option(option_key, simc_options, payload, option_name):
            if option_key == "enchant":
                excluded_named_options[option_key].append(
                    gear_config_enchant_exclusion_example(option_id, option_name, simc_options, payload)
                )
            continue
        if option_key in {"enchant", "embellishment"}:
            display_fields = gear_mod_option_display_fields(option_key, option_name, simc_options, payload)
            display_option = apply_gear_mod_option_display_fields(
                {
                    "id": option_id,
                    "type": option_key,
                    "name": option_name,
                    "label": option_name,
                    "status": option_status or "blocked",
                },
                display_fields,
            )
            if (
                str(option_status or "").strip().lower() != "verified"
                or not gear_mod_option_has_verified_display_fields(option_key, display_option)
            ):
                missing_example = {
                    "optionId": option_id,
                    "name": option_name,
                }
                simc_key = "enchant_id" if option_key == "enchant" else "embellishment"
                if normalize_option_value(simc_options.get(simc_key)):
                    missing_example["simcValue"] = normalize_option_value(simc_options.get(simc_key))
                missing_named_display[option_key].append(missing_example)
                continue
        coverage[option_key]["optionCount"] += 1
        if option_key == "socket":
            gem_item_ids = gem_item_ids_from_simc_options(simc_options)
            payload_gem_items = payload.get("gemItems") if isinstance(payload.get("gemItems"), list) else []
            payload_gem_items_by_id = {
                str(item.get("itemId") or "").strip(): item
                for item in payload_gem_items
                if isinstance(item, dict) and str(item.get("itemId") or "").strip()
            }
            missing_gem_id = ""
            invalid_gem = None
            statless_gem = None
            for gem_item_id in gem_item_ids:
                gem_metadata = existing_websim_item_metadata(conn, gem_item_id) if gem_item_id else None
                gem_metadata_payload = (gem_metadata or {}).get("payload") if isinstance(gem_metadata, dict) else {}
                gem_metadata_payload = gem_metadata_payload if isinstance(gem_metadata_payload, dict) else {}
                payload_gem_item = payload_gem_items_by_id.get(gem_item_id, {})
                option_icon = str(
                    payload_gem_item.get("iconUrl")
                    or (payload.get("iconUrl") if len(gem_item_ids) == 1 else "")
                    or ""
                ).strip()
                option_status = str(
                    payload_gem_item.get("metadataStatus")
                    or (payload.get("metadataStatus") if len(gem_item_ids) == 1 else "")
                    or ""
                ).strip()
                has_verified_option_metadata = bool(option_icon and option_status == "verified")
                has_verified_tooltip_display = bool(verified_socket_option_payload_stat_summary(payload, len(gem_item_ids)))
                has_verified_metadata = bool(
                    str(gem_item_id or "").strip()
                    and (has_verified_option_metadata or has_verified_tooltip_display)
                    and gem_metadata
                    and str(gem_metadata.get("iconUrl") or "").strip()
                    and str(gem_metadata.get("metadataStatus") or "") == "verified"
                    and str(gem_metadata.get("metadataSource") or "") == ITEM_METADATA_SOURCE
                )
                if not has_verified_metadata:
                    missing_gem_id = str(gem_item_id or "")
                    break
                item_class = gem_metadata_payload.get("item_class") if isinstance(gem_metadata_payload.get("item_class"), dict) else {}
                if not payload_item_class_is_gem(item_class):
                    invalid_gem = (str(gem_item_id or ""), item_class)
                    break
                option_stat_summary = verified_socket_option_payload_stat_summary(payload, len(gem_item_ids))
                stat_summary = option_stat_summary or str(gem_metadata.get("statSummary") or "").strip()
                preview_item = gem_metadata_payload.get("preview_item") if isinstance(gem_metadata_payload.get("preview_item"), dict) else {}
                item_stats = normalize_item_stats(gem_metadata.get("itemStats") or preview_item.get("stats") or [])
                if not stat_summary and not item_stats:
                    statless_gem = str(gem_item_id or "")
            if gem_item_ids and missing_gem_id:
                missing_socket_metadata.append(
                    {
                        "optionId": option_id,
                        "name": option_name,
                        "gemItemId": missing_gem_id or str(gem_item_ids[0]),
                    }
                )
            elif gem_item_ids and invalid_gem:
                invalid_gem_id, item_class = invalid_gem
                invalid_socket_gem_metadata.append(
                    {
                        "optionId": option_id,
                        "name": option_name,
                        "gemItemId": invalid_gem_id or str(gem_item_ids[0]),
                        "itemClass": payload_item_class_display_name(item_class) or "unknown",
                    }
                )
            elif gem_item_ids and statless_gem:
                missing_socket_stat_display.append(
                    {
                        "optionId": option_id,
                        "name": option_name,
                        "gemItemId": statless_gem or str(gem_item_ids[0]),
                    }
                )
        slots = safe_json_loads(slots_json, [])
        if not isinstance(slots, list):
            slots = []
        if "*" in slots:
            slots_by_type[option_key].update(CANONICAL_GEAR_SLOTS)
            continue
        for raw_slot in slots:
            slot = normalize_slot(raw_slot)
            if slot:
                slots_by_type[option_key].add(slot)
    for option_key, slots in slots_by_type.items():
        ordered_slots = [slot for slot in CANONICAL_GEAR_SLOTS if slot in slots]
        coverage[option_key]["coveredSlotCount"] = len(ordered_slots)
        coverage[option_key]["coveredSlots"] = ordered_slots
    if missing_socket_metadata:
        coverage["socket"]["missingMetadataCount"] = len(missing_socket_metadata)
        coverage["socket"]["missingMetadataExamples"] = missing_socket_metadata[:5]
    if invalid_socket_gem_metadata:
        coverage["socket"]["invalidGemMetadataCount"] = len(invalid_socket_gem_metadata)
        coverage["socket"]["invalidGemMetadataExamples"] = invalid_socket_gem_metadata[:5]
    if missing_socket_stat_display:
        coverage["socket"]["missingStatDisplayCount"] = len(missing_socket_stat_display)
        coverage["socket"]["missingStatDisplayExamples"] = missing_socket_stat_display[:5]
    for option_key, examples in missing_named_display.items():
        if examples:
            coverage[option_key]["missingDisplayCount"] = len(examples)
            coverage[option_key]["missingDisplayExamples"] = examples[:5]
    for option_key, examples in excluded_named_options.items():
        if examples:
            coverage[option_key]["excludedOptionCount"] = len(examples)
            coverage[option_key]["excludedExamples"] = examples[:5]
    return coverage


def gear_catalog_item_metadata_audit(conn):
    ensure_websim_tables(conn)
    rows = conn.execute(
        """
        WITH catalog_item_ids AS (
            SELECT item_id AS id FROM websim_gear_sources
            UNION
            SELECT item_id AS id FROM websim_gear_variants
            UNION
            SELECT item_id AS id FROM websim_loot
        )
        SELECT DISTINCT catalog_item_ids.id, wi.name, wi.slot, wi.payload_json
        FROM catalog_item_ids
        LEFT JOIN websim_items wi ON wi.id = catalog_item_ids.id
        WHERE catalog_item_ids.id IS NOT NULL AND catalog_item_ids.id != ''
        ORDER BY catalog_item_ids.id
        """
    ).fetchall()
    variant_rows = conn.execute(
        """
        SELECT item_id, slot, simc_options_json
        FROM websim_gear_variants
        """
    ).fetchall()
    variant_slots_by_item = {}
    catalog_slots_by_item = {}
    catalog_slot_sources_by_item = {}
    socketed_variant_items = set()

    def add_catalog_slot(item_id, raw_slot, source):
        item_key = str(item_id or "")
        slot = normalize_slot(raw_slot)
        if not item_key or not slot:
            return
        catalog_slots_by_item.setdefault(item_key, set()).add(slot)
        catalog_slot_sources_by_item.setdefault(item_key, {}).setdefault(slot, set()).add(source)

    for item_id, raw_slot, simc_options_json in variant_rows:
        item_key = str(item_id)
        slot = normalize_slot(raw_slot)
        if slot:
            variant_slots_by_item.setdefault(item_key, set()).add(slot)
            add_catalog_slot(item_key, slot, "variant")
        simc_options = safe_json_loads(simc_options_json, {})
        if isinstance(simc_options, dict) and (simc_options.get("gem_id") or simc_options.get("gem_bonus_id")):
            socketed_variant_items.add(item_key)
    loot_rows = conn.execute(
        """
        SELECT item_id, slot
        FROM websim_loot
        """
    ).fetchall()
    for item_id, raw_slot in loot_rows:
        add_catalog_slot(item_id, raw_slot, "loot")

    item_count = len(rows)
    verified_item_count = 0
    missing_verified_item_count = 0
    stat_item_count = 0
    missing_stat_item_count = 0
    missing_armor_type_item_count = 0
    missing_weapon_type_item_count = 0
    stat_mismatch_count = 0
    set_item_count = 0
    socket_capable_item_count = 0
    slot_mismatch_count = 0
    armor_type_coverage = {}
    weapon_type_coverage = {}
    source_coverage = {}
    missing_examples = []
    stat_mismatch_examples = []
    slot_mismatch_examples = []

    for item_id, name, raw_slot, payload_json in rows:
        item_key = str(item_id)
        payload = safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        metadata = payload.get("_metadata") if isinstance(payload.get("_metadata"), dict) else {}
        metadata_source = str(metadata.get("source") or "").strip()
        metadata_status = str(metadata.get("metadataStatus") or metadata.get("status") or "verified").strip()
        official_metadata = metadata_source == ITEM_METADATA_SOURCE and metadata_status == "verified"
        if official_metadata:
            verified_item_count += 1
        else:
            missing_verified_item_count += 1
        if metadata_source:
            source_coverage[metadata_source] = source_coverage.get(metadata_source, 0) + 1

        stats = extract_item_stats_from_payload(payload)
        stat_evidence = item_payload_has_stat_evidence(payload)
        if stat_evidence:
            stat_item_count += 1
        else:
            missing_stat_item_count += 1
        official_stats = direct_item_stats_from_payload(payload_preview_item(payload))
        conflicting_stats = direct_item_stats_from_payload(payload)
        if official_metadata and item_payload_has_stat_mismatch(payload):
            stat_mismatch_count += 1
            if len(stat_mismatch_examples) < 5:
                stat_mismatch_examples.append(
                    {
                        "itemId": item_key,
                        "name": name or f"Item {item_key}",
                        "expectedStats": official_stats,
                        "conflictingStats": conflicting_stats,
                    }
                )

        slots = set(catalog_slots_by_item.get(item_key) or variant_slots_by_item.get(item_key) or [])
        slot = item_slot_from_payload(payload) or normalize_slot(raw_slot)
        if slot:
            slots.add(slot)
        mismatched_slots = []
        if official_metadata and slot:
            mismatched_slots = [
                catalog_slot
                for catalog_slot in sorted(catalog_slots_by_item.get(item_key) or [])
                if not gear_catalog_slot_matches_item_metadata(payload, slot, catalog_slot)
            ]
        if mismatched_slots:
            slot_mismatch_count += 1
            if len(slot_mismatch_examples) < 5:
                source_map = catalog_slot_sources_by_item.get(item_key) or {}
                slot_mismatch_examples.append(
                    {
                        "itemId": item_key,
                        "name": name or f"Item {item_key}",
                        "expectedSlot": slot,
                        "catalogSlots": mismatched_slots,
                        "catalogSlotSources": {
                            catalog_slot: sorted(source_map.get(catalog_slot) or [])
                            for catalog_slot in mismatched_slots
                        },
                    }
                )
        type_metadata = item_type_metadata_from_payload(payload)
        armor_type = type_metadata.get("armorType") or ""
        weapon_type = type_metadata.get("weaponType") or ""
        if armor_type:
            armor_type_coverage[armor_type] = armor_type_coverage.get(armor_type, 0) + 1
        if weapon_type:
            weapon_type_coverage[weapon_type] = weapon_type_coverage.get(weapon_type, 0) + 1
        if slots & ARMOR_SLOTS and not armor_type:
            missing_armor_type_item_count += 1
        if slots & WEAPON_SLOTS and not weapon_type:
            missing_weapon_type_item_count += 1
        if type_metadata.get("itemSetName"):
            set_item_count += 1
        if type_metadata.get("supportsSocket") or item_key in socketed_variant_items:
            socket_capable_item_count += 1
        if len(missing_examples) < 5 and (not official_metadata or not stat_evidence):
            missing_examples.append(
                {
                    "itemId": item_key,
                    "name": name or f"Item {item_key}",
                    "metadataSource": metadata_source or "missing",
                    "metadataStatus": metadata_status or "missing",
                    "missingStats": not bool(stat_evidence),
                }
            )

    blockers = []
    if missing_verified_item_count:
        blockers.append(f"{missing_verified_item_count} catalog items missing verified Battle.net metadata")
    if missing_stat_item_count:
        blockers.append(f"{missing_stat_item_count} catalog items missing Battle.net item stats")
    if stat_mismatch_count:
        blockers.append(f"{stat_mismatch_count} catalog items have stat mismatches with Battle.net preview stats")
    if missing_armor_type_item_count:
        blockers.append(f"{missing_armor_type_item_count} armor-slot catalog items missing armor type")
    if missing_weapon_type_item_count:
        blockers.append(f"{missing_weapon_type_item_count} weapon-slot catalog items missing weapon type")
    if slot_mismatch_count:
        blockers.append(f"{slot_mismatch_count} catalog items have slot mismatches with Battle.net metadata")
    status = "blocked" if not item_count else ("partial" if blockers else "verified")
    return {
        "status": status,
        "itemCount": item_count,
        "verifiedItemCount": verified_item_count,
        "missingVerifiedItemCount": missing_verified_item_count,
        "statItemCount": stat_item_count,
        "missingStatItemCount": missing_stat_item_count,
        "statMismatchCount": stat_mismatch_count,
        "statMismatchExamples": stat_mismatch_examples,
        "missingArmorTypeItemCount": missing_armor_type_item_count,
        "missingWeaponTypeItemCount": missing_weapon_type_item_count,
        "setItemCount": set_item_count,
        "socketCapableItemCount": socket_capable_item_count,
        "socketedVariantItemCount": len(socketed_variant_items),
        "slotMismatchCount": slot_mismatch_count,
        "slotMismatchExamples": slot_mismatch_examples,
        "armorTypeCoverage": dict(sorted(armor_type_coverage.items())),
        "weaponTypeCoverage": dict(sorted(weapon_type_coverage.items())),
        "metadataSourceCoverage": dict(sorted(source_coverage.items())),
        "examples": missing_examples,
        "blockers": blockers,
    }


def gear_catalog_journal_loot_cache_coverage(conn, season=None):
    ensure_websim_tables(conn)
    season = season or get_active_season_payload(conn)
    encounter_rows = conn.execute(
        """
        SELECT e.id, e.instance_id, e.name, e.payload_json, COALESCE(i.category, '')
        FROM websim_encounters e
        LEFT JOIN websim_instances i ON i.id = e.instance_id
        ORDER BY e.id
        """
    ).fetchall()
    expected = {}
    for encounter_id, instance_id, encounter_name, payload_json, instance_category in encounter_rows:
        payload = safe_json_loads(payload_json, {})
        if not isinstance(payload, dict):
            continue
        for loot_ref in list_keyed_values(payload, "items", "loot"):
            item_ref = loot_ref.get("item") if isinstance(loot_ref, dict) else loot_ref
            item_id = extract_id_from_ref(item_ref)
            if not item_id:
                continue
            source_type = "raid" if str(instance_category or "").strip().lower() == "raid" else "dungeon"
            source_payload = current_season_loot_source_payload(source_type, instance_id, item_id, instance_category)
            if not gear_source_active_for_replacement(
                {
                    "sourceType": source_type,
                    "instanceId": str(instance_id or ""),
                    "payload": source_payload,
                },
                season,
            ):
                continue
            metadata = existing_websim_item_metadata(conn, item_id)
            metadata_payload = (metadata or {}).get("payload") if isinstance(metadata, dict) else {}
            if item_payload_is_explicit_non_equipment(metadata_payload):
                continue
            item_name = ""
            if isinstance(item_ref, dict):
                item_name = str(item_ref.get("name") or "")
            if not item_name and isinstance(loot_ref, dict):
                item_name = str(loot_ref.get("name") or "")
            expected[(str(encounter_id), str(item_id))] = {
                "encounterId": str(encounter_id),
                "encounterName": str(encounter_name or ""),
                "instanceId": str(instance_id or ""),
                "itemId": str(item_id),
                "itemName": item_name,
            }

    cached = {}
    for loot_id, instance_id, encounter_id, item_id, name in conn.execute(
        """
        SELECT id, instance_id, encounter_id, item_id, name
        FROM websim_loot
        """
    ).fetchall():
        cached[(str(encounter_id or ""), str(item_id or ""))] = {
            "lootId": str(loot_id or ""),
            "instanceId": str(instance_id or ""),
            "encounterId": str(encounter_id or ""),
            "itemId": str(item_id or ""),
            "itemName": str(name or ""),
        }

    source_rows = conn.execute(
        """
        SELECT id, item_id, instance_id, encounter_id, source_type, source_label, payload_json
        FROM websim_gear_sources
        WHERE source_type IN ('dungeon', 'mythic_plus', 'mythicplus', 'raid')
        """
    ).fetchall()
    catalog_sources_by_id = {}
    active_source_rows = []
    for source_id, item_id, instance_id, encounter_id, source_type, source_label, payload_json in source_rows:
        source_payload = safe_json_loads(payload_json, {})
        source_payload = source_payload if isinstance(source_payload, dict) else {}
        source = {
            "id": str(source_id or ""),
            "itemId": str(item_id or ""),
            "instanceId": str(instance_id or ""),
            "encounterId": str(encounter_id or ""),
            "sourceType": str(source_type or ""),
            "sourceLabel": str(source_label or ""),
            "payload": source_payload,
        }
        if gear_source_active_for_replacement(source, season):
            active_source_rows.append(source)
    catalog_source_keys = {
        (source.get("itemId") or "", source.get("instanceId") or "", source.get("encounterId") or "")
        for source in active_source_rows
    }
    for source in active_source_rows:
        source_id = source.get("id") or ""
        source_key = str(source_id or "")
        if not source_key:
            continue
        catalog_sources_by_id[source_key] = source
    missing_catalog_sources = []
    mismatched_catalog_sources = []
    catalog_source_item_count = 0
    for key, entry in expected.items():
        cached_entry = cached.get(key)
        if not cached_entry:
            continue
        source_id = f"loot-{cached_entry.get('lootId') or ''}"
        source_key = (
            entry.get("itemId") or "",
            cached_entry.get("instanceId") or entry.get("instanceId") or "",
            entry.get("encounterId") or "",
        )
        if source_key in catalog_source_keys:
            catalog_source_item_count += 1
            continue
        catalog_source = catalog_sources_by_id.get(source_id)
        if catalog_source:
            mismatched_catalog_sources.append(
                {
                    **entry,
                    "lootId": cached_entry.get("lootId") or "",
                    "itemName": entry.get("itemName") or cached_entry.get("itemName") or "",
                    "sourceId": catalog_source.get("id") or "",
                    "sourceType": catalog_source.get("sourceType") or "",
                    "sourceLabel": catalog_source.get("sourceLabel") or "",
                    "expectedItemId": source_key[0],
                    "expectedInstanceId": source_key[1],
                    "expectedEncounterId": source_key[2],
                    "actualItemId": catalog_source.get("itemId") or "",
                    "actualInstanceId": catalog_source.get("instanceId") or "",
                    "actualEncounterId": catalog_source.get("encounterId") or "",
                }
            )
            continue
        missing_catalog_sources.append(
            {
                **entry,
                "lootId": cached_entry.get("lootId") or "",
                "itemName": entry.get("itemName") or cached_entry.get("itemName") or "",
            }
        )
    missing = [entry for key, entry in expected.items() if key not in cached]
    blockers = []
    if missing:
        blockers.append(f"{len(missing)} Battle.net journal loot items missing from local cache")
    if missing_catalog_sources:
        blockers.append(f"{len(missing_catalog_sources)} Battle.net journal loot items missing gear catalog source")
    if mismatched_catalog_sources:
        blockers.append(f"{len(mismatched_catalog_sources)} Battle.net journal loot items have mismatched gear catalog source context")
    return {
        "status": "partial" if blockers else "verified",
        "expectedEncounterCount": len({encounter_id for encounter_id, _item_id in expected.keys()}),
        "expectedItemCount": len(expected),
        "cachedItemCount": len([key for key in expected.keys() if key in cached]),
        "catalogSourceItemCount": catalog_source_item_count,
        "missingItemCount": len(missing),
        "missingCatalogSourceCount": len(missing_catalog_sources),
        "mismatchedCatalogSourceCount": len(mismatched_catalog_sources),
        "missingExamples": missing[:5],
        "missingCatalogSourceExamples": missing_catalog_sources[:5],
        "mismatchedCatalogSourceExamples": mismatched_catalog_sources[:5],
        "blockers": blockers,
    }


def gear_catalog_season_source_coverage(conn, season=None):
    ensure_websim_tables(conn)
    season = season or get_active_season_payload(conn)
    active_season_revision_values = {
        str((season or {}).get(key) or "").strip()
        for key in ("seasonRevision", "revision", "seasonLabel", "label")
        if str((season or {}).get(key) or "").strip()
    }
    expected_dungeons = []
    for dungeon in (season or {}).get("dungeons") or []:
        if not isinstance(dungeon, dict):
            continue
        instance_id = str(dungeon.get("instanceId") or dungeon.get("instance_id") or "").strip()
        dungeon_id = str(dungeon.get("dungeonId") or dungeon.get("id") or "").strip()
        name = str(dungeon.get("name") or dungeon.get("shortName") or dungeon_id or instance_id or "").strip()
        if not (instance_id or dungeon_id or name):
            continue
        expected_dungeons.append(
            {
                "instanceId": instance_id,
                "dungeonId": dungeon_id,
                "name": name,
            }
        )
    has_raid_pool = isinstance(season, dict) and "raids" in season
    raid_pool_status = current_season_raid_pool_status(season) if has_raid_pool else {
        "refs": [],
        "blockers": [],
    }
    expected_raids = []
    for raid in (raid_pool_status.get("refs") or (official_current_season_raid_refs() if has_raid_pool else [])):
        if not isinstance(raid, dict):
            continue
        instance_id = str(raid.get("instanceId") or raid.get("instance_id") or raid.get("id") or "").strip()
        raid_id = str(raid.get("raidId") or raid.get("id") or "").strip()
        name = str(raid.get("name") or raid_id or instance_id or "").strip()
        if not (instance_id or raid_id or name):
            continue
        expected_raids.append(
            {
                "instanceId": instance_id,
                "raidId": raid_id,
                "name": name,
            }
        )

    source_rows = conn.execute(
        """
        SELECT id, source_type, source_label, instance_id, item_id, season_revision, payload_json
        FROM websim_gear_sources
        ORDER BY source_type, source_label, item_id
        """
    ).fetchall()
    dungeon_sources = []
    raid_sources = []
    tier_set_sources = []
    has_season_tagged_sources = False
    for source_id, source_type, source_label, instance_id, item_id, season_revision, payload_json in source_rows:
        source_payload = safe_json_loads(payload_json, {})
        source_payload = source_payload if isinstance(source_payload, dict) else {}
        source = {
            "id": str(source_id or ""),
            "sourceType": str(source_type or ""),
            "sourceLabel": str(source_label or ""),
            "instanceId": str(instance_id or ""),
            "itemId": str(item_id or ""),
            "seasonRevision": str(season_revision or ""),
            "payload": source_payload,
            "validationStatus": normalized_source_validation_status(source_payload),
        }
        if source["seasonRevision"]:
            has_season_tagged_sources = True
        source_key = source["sourceType"].lower()
        if source_key in {"dungeon", "mythic_plus", "mythicplus"}:
            dungeon_sources.append(source)
        elif source_key == "raid":
            raid_sources.append(source)
        elif source_key == "tier_set":
            tier_set_sources.append(source)

    def source_matches_active_season(source):
        source_revision = str((source or {}).get("seasonRevision") or "").strip()
        return not active_season_revision_values or not source_revision or source_revision in active_season_revision_values

    def source_is_stale_for_active_season(source):
        source_revision = str((source or {}).get("seasonRevision") or "").strip()
        return bool(active_season_revision_values and source_revision and source_revision not in active_season_revision_values)

    def source_summary(source):
        return {
            "id": str((source or {}).get("id") or ""),
            "sourceType": str((source or {}).get("sourceType") or ""),
            "sourceLabel": str((source or {}).get("sourceLabel") or ""),
            "instanceId": str((source or {}).get("instanceId") or ""),
            "itemId": str((source or {}).get("itemId") or ""),
            "seasonRevision": str((source or {}).get("seasonRevision") or ""),
        }

    active_dungeon_sources = [
        source
        for source in dungeon_sources
        if source_matches_active_season(source) and source_validation_allows_current_acceptance(source)
    ]
    active_raid_sources = [
        source
        for source in raid_sources
        if source_matches_active_season(source) and source_validation_allows_current_acceptance(source)
    ]
    stale_dungeon_sources = [source for source in dungeon_sources if source_is_stale_for_active_season(source)]
    stale_raid_sources = [source for source in raid_sources if source_is_stale_for_active_season(source)]

    variant_rows = conn.execute(
        """
        SELECT item_id, source_type, status, blockers_json
        FROM websim_gear_variants
        WHERE source_type IN ('dungeon', 'raid')
        """
    ).fetchall()
    variant_readiness_by_item_source = {}
    for item_id, source_type, status, blockers_json in variant_rows:
        key = (str(item_id or ""), str(source_type or "").lower())
        if not key[0] or not key[1]:
            continue
        blockers_for_variant = safe_json_loads(blockers_json, [])
        if not isinstance(blockers_for_variant, list):
            blockers_for_variant = []
        variant_readiness_by_item_source.setdefault(key, []).append(
            {
                "status": str(status or "").strip() or "partial",
                "blockers": [str(item) for item in blockers_for_variant if str(item or "").strip()],
            }
        )

    def matching_sources_for_instance(sources, instance):
        instance_id = str((instance or {}).get("instanceId") or "").strip()
        name_key = normalize_name_key((instance or {}).get("name") or "")
        matches = []
        for source in sources:
            if instance_id and source.get("instanceId") == instance_id:
                matches.append(source)
                continue
            if name_key and name_key in normalize_name_key(source.get("sourceLabel") or ""):
                matches.append(source)
        return matches

    def readiness_for_instance_sources(sources):
        item_status = {}
        item_blockers = {}
        for source in sources:
            item_id = source.get("itemId") or ""
            if not item_id:
                continue
            source_type = str(source.get("sourceType") or "").lower()
            readiness_rows = variant_readiness_by_item_source.get((item_id, source_type)) or []
            statuses = {row.get("status") or "partial" for row in readiness_rows}
            blockers_for_item = []
            for row in readiness_rows:
                blockers_for_item.extend(row.get("blockers") or [])
            if "verified" in statuses:
                item_status[item_id] = "verified"
            else:
                item_status[item_id] = "partial"
                if not readiness_rows:
                    blockers_for_item.append("missing gear catalog variant")
            if blockers_for_item:
                item_blockers.setdefault(item_id, []).extend(blockers_for_item)
        verified_items = [item_id for item_id, status in item_status.items() if status == "verified"]
        partial_items = [item_id for item_id, status in item_status.items() if status == "partial"]
        blockers = unique_text_list(
            blocker
            for blockers_for_item in item_blockers.values()
            for blocker in blockers_for_item
        )
        return {
            "verifiedItemCount": len(verified_items),
            "partialItemCount": len(partial_items),
            "blockers": blockers,
        }

    instance_rows = []

    def append_instance_row(instance, category, sources, missing_blocker):
        matches = matching_sources_for_instance(sources, instance)
        readiness = readiness_for_instance_sources(matches)
        blockers_for_instance = list(readiness.get("blockers") or [])
        if not matches:
            blockers_for_instance.append(missing_blocker)
        instance_rows.append(
            {
                "instanceId": str((instance or {}).get("instanceId") or ""),
                "name": str((instance or {}).get("name") or ""),
                "category": category,
                "expected": True,
                "covered": bool(matches),
                "sourceItemCount": len({source.get("itemId") for source in matches if source.get("itemId")}),
                "verifiedItemCount": readiness.get("verifiedItemCount") or 0,
                "partialItemCount": readiness.get("partialItemCount") or 0,
                "blockers": unique_text_list(blockers_for_instance),
            }
        )

    for dungeon in expected_dungeons:
        append_instance_row(dungeon, "Dungeon", active_dungeon_sources, "current season dungeon missing gear loot")
    for raid in expected_raids:
        append_instance_row(raid, "Raid", active_raid_sources, "current season raid missing gear loot")

    covered_dungeons = []
    missing_dungeons = []
    for dungeon in expected_dungeons:
        instance_id = dungeon.get("instanceId") or ""
        name_key = normalize_name_key(dungeon.get("name") or "")
        covered = False
        for source in active_dungeon_sources:
            if instance_id and source.get("instanceId") == instance_id:
                covered = True
                break
            if name_key and name_key in normalize_name_key(source.get("sourceLabel") or ""):
                covered = True
                break
        if covered:
            covered_dungeons.append(dungeon.get("name") or dungeon.get("instanceId") or dungeon.get("dungeonId") or "")
        else:
            missing_dungeons.append(dungeon.get("name") or dungeon.get("instanceId") or dungeon.get("dungeonId") or "")

    covered_raids = []
    missing_raids = []
    for raid in expected_raids:
        instance_id = raid.get("instanceId") or ""
        name_key = normalize_name_key(raid.get("name") or "")
        covered = False
        for source in active_raid_sources:
            if instance_id and source.get("instanceId") == instance_id:
                covered = True
                break
            if name_key and name_key in normalize_name_key(source.get("sourceLabel") or ""):
                covered = True
                break
        if covered:
            covered_raids.append(raid.get("name") or raid.get("instanceId") or raid.get("raidId") or "")
        else:
            missing_raids.append(raid.get("name") or raid.get("instanceId") or raid.get("raidId") or "")

    expected_set_refs = season_item_set_refs(season)
    discovered_set_refs = {}
    set_names = []
    set_item_count = 0
    item_rows = conn.execute(
        """
        SELECT DISTINCT wi.id, wi.payload_json
        FROM websim_items wi
        WHERE wi.id IN (
            SELECT item_id FROM websim_gear_sources
            WHERE source_type IN ('dungeon', 'raid', 'tier_set')
            UNION
            SELECT item_id FROM websim_gear_variants
            WHERE source_type IN ('dungeon', 'raid', 'tier_set')
        )
        ORDER BY wi.id
        """
    ).fetchall()
    for _item_id, payload_json in item_rows:
        payload = safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        set_ref = item_set_ref_from_payload(payload)
        set_name = set_ref.get("name") or ""
        if not set_name:
            continue
        set_item_count += 1
        set_names.append(set_name)
        set_key = set_ref.get("id") or set_name
        if set_key:
            discovered_set_refs[set_key] = set_ref
    all_set_refs = {**expected_set_refs, **discovered_set_refs}
    set_rows = conn.execute(
        """
        SELECT id, name, status
        FROM websim_item_sets
        ORDER BY name
        """
    ).fetchall()
    verified_set_ids = set()
    verified_set_names = []
    for set_id, name, status in set_rows:
        if str(status or "") != "verified":
            continue
        verified_set_ids.add(str(set_id))
        if name:
            verified_set_names.append(str(name))
    verified_set_name_keys = {
        normalize_item_set_name_key(name)
        for name in verified_set_names
        if normalize_item_set_name_key(name)
    }
    set_item_rows = conn.execute(
        """
        SELECT DISTINCT set_id, item_id, name, slot
        FROM websim_item_set_items
        ORDER BY set_id, item_id
        """
    ).fetchall()
    tier_set_source_pairs = set()
    tier_set_source_unscoped_item_ids = set()
    tier_set_source_all_item_ids = set()
    for source in tier_set_sources:
        item_id = source.get("itemId") or ""
        if not item_id:
            continue
        tier_set_source_all_item_ids.add(item_id)
        source_payload = source.get("payload") if isinstance(source.get("payload"), dict) else {}
        set_id = str(
            source_payload.get("setId")
            or source_payload.get("set_id")
            or source_payload.get("itemSetId")
            or source_payload.get("item_set_id")
            or ""
        ).strip()
        source_id = source.get("id") or ""
        if not set_id and source_id.startswith("set-") and source_id.endswith(f"-{item_id}"):
            set_id = source_id[4 : -len(f"-{item_id}")].strip()
        if set_id:
            tier_set_source_pairs.add((set_id, item_id))
        else:
            tier_set_source_unscoped_item_ids.add(item_id)
    covered_set_item_catalog_source_keys = set()
    missing_set_item_catalog_sources = []
    for set_id, item_id, name, slot in set_item_rows:
        set_id = str(set_id or "")
        item_id = str(item_id or "")
        if not item_id:
            continue
        covered = False
        if set_id and (set_id, item_id) in tier_set_source_pairs:
            covered = True
        elif item_id in tier_set_source_unscoped_item_ids:
            covered = True
        elif not set_id and item_id in tier_set_source_all_item_ids:
            covered = True
        if covered:
            covered_set_item_catalog_source_keys.add((set_id, item_id))
            continue
        missing_set_item_catalog_sources.append(
            {
                "setId": set_id,
                "itemId": item_id,
                "name": str(name or ""),
                "slot": str(slot or ""),
            }
        )
    set_names = unique_text_list(set_names)
    missing_set_detail_keys = []
    for set_key, set_ref in discovered_set_refs.items():
        set_id = set_ref.get("id") or ""
        if set_id and set_id in verified_set_ids:
            continue
        if not set_id and normalize_item_set_name_key(set_ref.get("name") or set_key) in verified_set_name_keys:
            continue
        missing_set_detail_keys.append(set_key)
    missing_expected_set_keys = []
    missing_expected_set_names = []
    for set_key, set_ref in expected_set_refs.items():
        set_id = set_ref.get("id") or ""
        set_name = set_ref.get("name") or ""
        if set_id and set_id in verified_set_ids:
            continue
        if not set_id and normalize_item_set_name_key(set_name or set_key) in verified_set_name_keys:
            continue
        missing_expected_set_keys.append(set_key)
        missing_expected_set_names.append(set_name or set_id or set_key)

    dungeon_item_ids = {source.get("itemId") for source in active_dungeon_sources if source.get("itemId")}
    raid_item_ids = {source.get("itemId") for source in active_raid_sources if source.get("itemId")}
    journal_loot = gear_catalog_journal_loot_cache_coverage(conn, season)
    blockers = []
    blockers.extend(raid_pool_status.get("blockers") or [])
    if not expected_dungeons and has_season_tagged_sources:
        blockers.append("active season dungeon list is missing")
    if expected_dungeons and missing_dungeons:
        blockers.append(f"{len(missing_dungeons)} current season dungeon missing gear loot")
    if expected_raids and missing_raids:
        blockers.append(f"{len(missing_raids)} current expansion raid missing gear loot")
    if missing_expected_set_keys:
        blockers.append(f"{len(missing_expected_set_keys)} current season item sets missing Battle.net item-set detail")
    if missing_set_detail_keys:
        blockers.append(f"{len(missing_set_detail_keys)} discovered item sets missing Battle.net item-set detail")
    if missing_set_item_catalog_sources:
        blockers.append(f"{len(missing_set_item_catalog_sources)} item set pieces missing gear catalog source")
    blockers.extend(journal_loot.get("blockers") or [])
    status = "partial" if blockers else "verified"
    return {
        "status": status,
        "mythicPlus": {
            "expectedDungeonCount": len(expected_dungeons),
            "coveredDungeonCount": len(covered_dungeons),
            "missingDungeonCount": len(missing_dungeons),
            "coveredDungeons": covered_dungeons,
            "missingDungeons": missing_dungeons,
            "sourceItemCount": len(dungeon_item_ids),
            "staleSourceCount": len(stale_dungeon_sources),
            "staleSourceExamples": [source_summary(source) for source in stale_dungeon_sources[:5]],
        },
        "raid": {
            "expectedInstanceCount": len(expected_raids),
            "coveredInstanceCount": len(covered_raids),
            "missingInstanceCount": len(missing_raids),
            "coveredInstances": covered_raids,
            "missingInstances": missing_raids,
            "instanceCount": len({source.get("instanceId") for source in active_raid_sources if source.get("instanceId")}),
            "sourceItemCount": len(raid_item_ids),
            "staleSourceCount": len(stale_raid_sources),
            "staleSourceExamples": [source_summary(source) for source in stale_raid_sources[:5]],
        },
        "sets": {
            "expectedSetCount": len(expected_set_refs),
            "setItemCount": set_item_count,
            "discoveredSetCount": len(discovered_set_refs),
            "knownSetCount": len(all_set_refs),
            "verifiedSetCount": len(verified_set_ids),
            "missingExpectedSetCount": len(missing_expected_set_keys),
            "missingSetDetailCount": len(missing_set_detail_keys),
            "verifiedSetItemCount": len(set_item_rows),
            "setItemCatalogSourceCount": len(covered_set_item_catalog_source_keys),
            "missingSetItemCatalogSourceCount": len(missing_set_item_catalog_sources),
            "missingSetItemCatalogSourceExamples": missing_set_item_catalog_sources[:5],
            "missingExpectedSets": sorted(unique_text_list(missing_expected_set_names)),
            "setNames": sorted(unique_text_list([*set_names, *verified_set_names])),
        },
        "instances": instance_rows,
        "journalLoot": journal_loot,
        "blockers": blockers,
    }


def gear_catalog_variant_readiness_examples(conn, statuses, limit=8):
    normalized_statuses = [str(status or "").strip() for status in statuses or [] if str(status or "").strip()]
    if not normalized_statuses:
        return []
    placeholders = ",".join("?" for _ in normalized_statuses)
    rows = conn.execute(
        f"""
        SELECT
            v.id,
            v.item_id,
            v.slot,
            v.source_type,
            v.status,
            v.blockers_json,
            COALESCE(MIN(s.source_label), '') AS source_label
        FROM websim_gear_variants v
        LEFT JOIN websim_gear_sources s
          ON s.item_id = v.item_id
         AND s.source_type = v.source_type
        WHERE v.status IN ({placeholders})
          AND COALESCE(v.source_type, '') != 'observed_profile'
        GROUP BY v.id, v.item_id, v.slot, v.source_type, v.status, v.blockers_json
        ORDER BY v.source_type, v.slot, v.item_id, v.id
        LIMIT ?
        """,
        (*normalized_statuses, max(1, int(limit or 8))),
    ).fetchall()
    examples = []
    for variant_id, item_id, slot, source_type, status, blockers_json, source_label in rows:
        examples.append(
            {
                "variantId": str(variant_id or ""),
                "itemId": str(item_id or ""),
                "slot": normalize_slot(slot),
                "sourceType": str(source_type or ""),
                "sourceLabel": str(source_label or ""),
                "status": str(status or ""),
                "blockers": [str(item) for item in (safe_json_loads(blockers_json, []) or []) if str(item or "").strip()],
            }
        )
    return examples


def gear_catalog_observed_stat_coverage(conn, limit=8):
    rows = conn.execute(
        """
        SELECT id, item_id, slot, item_level, payload_json
        FROM websim_gear_variants
        WHERE source_type = 'observed_profile'
        ORDER BY item_id, slot, id
        """
    ).fetchall()
    total = len(rows)
    with_stats = 0
    simulationcraft_stats = 0
    missing_examples = []
    for variant_id, item_id, slot, item_level, payload_json in rows:
        payload = safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        stats = normalize_item_stats(payload.get("itemStats") or payload.get("stats") or [])
        if stats:
            with_stats += 1
            if str(payload.get("statSource") or "").strip() == "simulationcraft":
                simulationcraft_stats += 1
            continue
        if len(missing_examples) < max(1, int(limit or 8)):
            missing_examples.append(
                {
                    "variantId": str(variant_id or ""),
                    "itemId": str(item_id or ""),
                    "slot": normalize_slot(slot),
                    "itemLevel": int_or_zero(item_level),
                    "reason": "missing SimulationCraft gear stat payload",
                }
            )
    missing = max(0, total - with_stats)
    return {
        "totalObservedVariantCount": total,
        "statObservedVariantCount": with_stats,
        "simulationcraftStatObservedVariantCount": simulationcraft_stats,
        "missingStatObservedVariantCount": missing,
        "coverage": catalog_health_coverage(with_stats, total),
        "missingExamples": missing_examples,
    }


GEAR_SOURCE_GAP_UNTRUSTED_SOURCE_TYPES = {"observed_profile", "simcpreset", "simc_preset"}
GEAR_SOURCE_GAP_TRUSTED_SOURCE_TYPES = {
    "dungeon",
    "mythic_plus",
    "mythicplus",
    "raid",
    "tier_set",
    "crafted",
    "loot",
    "verifiedloot",
    "verified_loot",
}
GEAR_SOURCE_GAP_GENERIC_LABELS = {
    "catalog",
    "gear catalog",
    "websim catalog",
    "source reference",
    "unknown",
    "来源待补充",
    "来源未知",
}


def gear_source_gap_normalized_type(value):
    return raw_source_type(value, "").strip().lower()


def gear_source_gap_label(value):
    return str(value or "").strip()


def gear_source_gap_source_label(source):
    if not isinstance(source, dict):
        return ""
    return gear_source_gap_label(source.get("label") or source.get("sourceLabel") or source.get("source"))


def gear_source_gap_label_is_generic(label):
    normalized = re.sub(r"\s+", " ", gear_source_gap_label(label)).strip().lower()
    return not normalized or normalized in GEAR_SOURCE_GAP_GENERIC_LABELS


def gear_source_gap_is_trusted_source(source):
    if not isinstance(source, dict):
        return False
    if not source_validation_allows_current_acceptance(source):
        return False
    source_type = gear_source_gap_normalized_type(source.get("sourceType") or source.get("type"))
    label = gear_source_gap_source_label(source)
    if source_type in GEAR_SOURCE_GAP_UNTRUSTED_SOURCE_TYPES:
        return False
    if gear_observed_source_label(label) or gear_simc_preset_source_label(label):
        return False
    if gear_source_gap_label_is_generic(label):
        return False
    if source_type in GEAR_SOURCE_GAP_TRUSTED_SOURCE_TYPES:
        return True
    return bool(source.get("instanceId") or source.get("instance_id") or source.get("encounterId") or source.get("encounter_id"))


def gear_source_gap_payload_sources(payload):
    if not isinstance(payload, dict):
        return []
    sources = []
    for key in ("sources", "sourceRefs"):
        for source in payload.get(key) or []:
            if isinstance(source, dict):
                sources.append(source)
    label = first_matching_value(
        payload,
        ["source", "sourceName", "sourceLabel", "label", "encounterName", "instanceName"],
        "",
    )
    source_type = payload.get("sourceType") or payload.get("type")
    if label or source_type:
        sources.append(
            {
                "sourceType": source_type,
                "sourceLabel": label,
                "instanceId": payload.get("instanceId") or payload.get("instance_id"),
                "encounterId": payload.get("encounterId") or payload.get("encounter_id"),
            }
        )
    return sources


def gear_catalog_source_gap_coverage(conn, limit=8):
    ensure_websim_tables(conn)
    source_rows = conn.execute(
        """
        SELECT item_id, source_type, source_label, instance_id, encounter_id, payload_json
        FROM websim_gear_sources
        ORDER BY item_id, source_type, source_label, id
        """
    ).fetchall()
    variant_rows = conn.execute(
        """
        SELECT item_id, slot, item_level, source_type, payload_json
        FROM websim_gear_variants
        WHERE status IN ('verified', 'partial')
        ORDER BY item_id, slot, item_level, id
        """
    ).fetchall()
    sources_by_item = {}
    for item_id, source_type, source_label, instance_id, encounter_id, payload_json in source_rows:
        item_id = str(item_id or "").strip()
        if not item_id:
            continue
        payload = safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        source = {
            "sourceType": source_type,
            "sourceLabel": source_label,
            "label": source_label,
            "instanceId": instance_id,
            "encounterId": encounter_id,
        }
        source.update({key: value for key, value in payload.items() if key not in source or source.get(key) in (None, "")})
        sources_by_item.setdefault(item_id, []).append(source)

    by_item = {}
    all_item_ids = set()
    trusted_item_ids = set()
    pending_variant_count = 0
    for item_id, slot, item_level, source_type, payload_json in variant_rows:
        item_id = str(item_id or "").strip()
        if not item_id:
            continue
        all_item_ids.add(item_id)
        payload = safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        sources = [
            *sources_by_item.get(item_id, []),
            *gear_source_gap_payload_sources(payload),
            {
                "sourceType": source_type,
                "sourceLabel": first_matching_value(payload, ["source", "sourceName", "sourceLabel", "label"], ""),
            },
        ]
        source_types = unique_text_list(
            gear_source_gap_normalized_type((source or {}).get("sourceType") or (source or {}).get("type"))
            for source in sources
            if isinstance(source, dict)
        )
        if any(gear_source_gap_is_trusted_source(source) for source in sources):
            trusted_item_ids.add(item_id)
            continue
        pending_variant_count += 1
        entry = by_item.setdefault(
            item_id,
            {
                "itemId": item_id,
                "displayName": "",
                "sourcePendingVariantCount": 0,
                "slots": [],
                "itemLevels": [],
                "sourceTypes": [],
            },
        )
        entry["sourcePendingVariantCount"] += 1
        if not entry["displayName"]:
            entry["displayName"] = first_matching_value(
                payload,
                ["displayName", "localizedName", "name", "englishName"],
                "",
            )
        entry["slots"] = unique_text_list([*entry["slots"], normalize_slot(slot)])
        item_level_value = int_or_zero(item_level)
        if item_level_value:
            entry["itemLevels"] = unique_text_list([*entry["itemLevels"], item_level_value])
        entry["sourceTypes"] = unique_text_list([*entry["sourceTypes"], *source_types])

    examples = list(by_item.values())
    examples.sort(
        key=lambda entry: (
            -int(entry.get("sourcePendingVariantCount") or 0),
            int_or_zero(entry.get("itemId")) if str(entry.get("itemId") or "").isdigit() else 0,
            str(entry.get("itemId") or ""),
        )
    )
    return {
        "totalItemCount": len(all_item_ids),
        "trustedSourceItemCount": len(trusted_item_ids),
        "sourcePendingItemCount": len(by_item),
        "sourcePendingVariantCount": pending_variant_count,
        "coverage": catalog_health_coverage(len(trusted_item_ids), len(all_item_ids)),
        "examples": examples[: max(1, int(limit or 8))],
    }


def compact_catalog_health_summary(catalog_state):
    catalog_state = catalog_state if isinstance(catalog_state, dict) else {}
    source_gap = catalog_state.get("sourceGapCoverage") if isinstance(catalog_state.get("sourceGapCoverage"), dict) else {}
    observed_stats = (
        catalog_state.get("observedStatCoverage") if isinstance(catalog_state.get("observedStatCoverage"), dict) else {}
    )
    simulation_readiness = (
        catalog_state.get("simulationReadiness") if isinstance(catalog_state.get("simulationReadiness"), dict) else {}
    )
    mod_options = catalog_state.get("modOptionCoverage") if isinstance(catalog_state.get("modOptionCoverage"), dict) else {}
    socket_options = mod_options.get("socket") if isinstance(mod_options.get("socket"), dict) else {}
    source_coverage = source_gap.get("coverage") if isinstance(source_gap.get("coverage"), dict) else {}
    observed_stat_coverage = observed_stats.get("coverage") if isinstance(observed_stats.get("coverage"), dict) else {}
    return {
        "status": catalog_state.get("status") or "blocked",
        "sourcePendingItemCount": int_or_zero(source_gap.get("sourcePendingItemCount")),
        "sourcePendingVariantCount": int_or_zero(source_gap.get("sourcePendingVariantCount")),
        "trustedSourceItemCount": int_or_zero(source_gap.get("trustedSourceItemCount")),
        "trustedSourceCoveragePercent": float(source_coverage.get("percent") or 0),
        "missingStatObservedVariantCount": int_or_zero(observed_stats.get("missingStatObservedVariantCount")),
        "observedStatCoveragePercent": float(observed_stat_coverage.get("percent") or 0),
        "socketMissingMetadataCount": int_or_zero(socket_options.get("missingMetadataCount")),
        "socketInvalidGemMetadataCount": int_or_zero(socket_options.get("invalidGemMetadataCount")),
        "partialVariantCount": int_or_zero(catalog_state.get("partialCount")),
        "verifiedVariantCount": int_or_zero(catalog_state.get("verifiedCount")),
        "blockedVariantCount": int_or_zero(catalog_state.get("blockedCount")),
        "sourcePendingExamples": (source_gap.get("examples") or [])[:3],
        "partialVariantExamples": (simulation_readiness.get("partialExamples") or [])[:3],
        "blockedVariantExamples": (simulation_readiness.get("blockedExamples") or [])[:3],
        "blockers": (catalog_state.get("blockers") or [])[:5],
    }


def gear_catalog_counts(conn):
    ensure_websim_tables(conn)
    source_count = conn.execute("SELECT COUNT(*) FROM websim_gear_sources").fetchone()[0]
    source_item_count = conn.execute("SELECT COUNT(DISTINCT item_id) FROM websim_gear_sources").fetchone()[0]
    mod_option_count = conn.execute("SELECT COUNT(*) FROM websim_gear_mod_options").fetchone()[0]
    variant_rows = conn.execute(
        """
        SELECT status, blockers_json
        FROM websim_gear_variants
        WHERE COALESCE(source_type, '') != 'observed_profile'
        """
    ).fetchall()
    verified_count = 0
    partial_count = 0
    blocked_count = 0
    blocker_counts = {}
    for status, blockers_json in variant_rows:
        normalized_status = str(status or "blocked")
        if normalized_status == "verified":
            verified_count += 1
        elif normalized_status == "partial":
            partial_count += 1
        else:
            blocked_count += 1
        for blocker in safe_json_loads(blockers_json, []) or []:
            text = str(blocker or "").strip()
            if text:
                blocker_counts[text] = blocker_counts.get(text, 0) + 1
    variant_count = len(variant_rows)
    item_count = max(
        source_item_count,
        conn.execute(
            """
            SELECT COUNT(DISTINCT item_id)
            FROM websim_gear_variants
            WHERE COALESCE(source_type, '') != 'observed_profile'
            """
        ).fetchone()[0],
    )
    observed_variant_count = conn.execute(
        "SELECT COUNT(*) FROM websim_gear_variants WHERE source_type = 'observed_profile'"
    ).fetchone()[0]
    verified_observed_variant_count = conn.execute(
        "SELECT COUNT(*) FROM websim_gear_variants WHERE source_type = 'observed_profile' AND status = 'verified'"
    ).fetchone()[0]
    partial_observed_variant_count = conn.execute(
        "SELECT COUNT(*) FROM websim_gear_variants WHERE source_type = 'observed_profile' AND status = 'partial'"
    ).fetchone()[0]
    blocked_observed_variant_count = conn.execute(
        """
        SELECT COUNT(*) FROM websim_gear_variants
        WHERE source_type = 'observed_profile'
          AND status NOT IN ('verified', 'partial')
        """
    ).fetchone()[0]
    top_blockers = [
        {"reason": reason, "count": count}
        for reason, count in sorted(blocker_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]
    metadata_audit = gear_catalog_item_metadata_audit(conn)
    season_source_coverage = gear_catalog_season_source_coverage(conn)
    mod_option_coverage = gear_catalog_mod_option_coverage(conn)
    observed_stat_coverage = gear_catalog_observed_stat_coverage(conn)
    source_gap_coverage = gear_catalog_source_gap_coverage(conn)
    metadata_blockers = metadata_audit.get("blockers") or []
    source_blockers = season_source_coverage.get("blockers") or []
    source_gap_blockers = []
    if source_gap_coverage.get("sourcePendingItemCount"):
        source_gap_blockers.append(
            f"{source_gap_coverage.get('sourcePendingItemCount')} gear catalog items missing trusted drop source"
        )
    mod_option_blockers = []
    if (metadata_audit.get("socketCapableItemCount") or 0) > 0 and not (mod_option_coverage.get("socket") or {}).get("optionCount"):
        mod_option_blockers.append("socket-capable catalog items missing socket mod options")
    missing_socket_option_metadata = (mod_option_coverage.get("socket") or {}).get("missingMetadataCount") or 0
    if missing_socket_option_metadata:
        mod_option_blockers.append(f"{missing_socket_option_metadata} socket mod options missing Battle.net gem metadata")
    invalid_socket_gem_metadata = (mod_option_coverage.get("socket") or {}).get("invalidGemMetadataCount") or 0
    if invalid_socket_gem_metadata:
        mod_option_blockers.append(f"{invalid_socket_gem_metadata} socket mod options reference non-gem Battle.net item metadata")
    missing_socket_stat_display = (mod_option_coverage.get("socket") or {}).get("missingStatDisplayCount") or 0
    if missing_socket_stat_display:
        mod_option_blockers.append(f"{missing_socket_stat_display} socket mod options missing gem stat display metadata")
    for option_key, label in (("enchant", "enchant"), ("embellishment", "embellishment")):
        missing_display = (mod_option_coverage.get(option_key) or {}).get("missingDisplayCount") or 0
        if missing_display:
            mod_option_blockers.append(f"{missing_display} {label} mod options missing verified display label")
    observed_stat_blockers = []
    missing_observed_stat_count = int_or_zero(observed_stat_coverage.get("missingStatObservedVariantCount"))
    if missing_observed_stat_count:
        observed_stat_blockers.append(
            f"{missing_observed_stat_count} observed gear variants missing SimulationCraft item stats"
        )
    data_blockers = unique_text_list([*metadata_blockers, *source_blockers, *source_gap_blockers, *mod_option_blockers])
    simulation_blockers = unique_text_list([*[item["reason"] for item in top_blockers], *observed_stat_blockers])
    all_blockers = unique_text_list(
        [*simulation_blockers, *data_blockers]
    )
    variant_status = catalog_status_from_counts(verified_count, partial_count, blocked_count, item_count)
    simulation_status = "partial" if observed_stat_blockers and variant_status == "verified" else variant_status
    metadata_status = metadata_audit.get("status") or "blocked"
    season_source_status = season_source_coverage.get("status") or "blocked"
    source_status = "partial" if source_gap_blockers else season_source_status
    data_status = "blocked" if not item_count else (
        "verified"
        if metadata_status == "verified" and source_status == "verified" and not mod_option_blockers
        else "partial"
    )
    status = "blocked" if not item_count else (
        "verified"
        if simulation_status == "verified" and metadata_status == "verified" and source_status == "verified" and not mod_option_blockers
        else "partial"
    )
    return {
        "itemCount": item_count,
        "sourceCount": source_count,
        "variantCount": variant_count,
        "modOptionCount": mod_option_count,
        "verifiedCount": verified_count,
        "partialCount": partial_count,
        "blockedCount": blocked_count,
        "observedVariantCount": observed_variant_count,
        "verifiedObservedVariantCount": verified_observed_variant_count,
        "partialObservedVariantCount": partial_observed_variant_count,
        "blockedObservedVariantCount": blocked_observed_variant_count,
        "observedStatCoverage": observed_stat_coverage,
        "slotCoverage": gear_catalog_slot_coverage(conn),
        "sourceCoverage": gear_catalog_source_coverage(conn),
        "sourceGapCoverage": source_gap_coverage,
        "modOptionCoverage": mod_option_coverage,
        "itemMetadata": metadata_audit,
        "seasonSourceCoverage": season_source_coverage,
        "topBlockers": top_blockers,
        "dataReadiness": {
            "status": data_status,
            "blockers": data_blockers,
            "metadataStatus": metadata_status,
            "sourceStatus": source_status,
            "seasonSourceStatus": season_source_status,
            "modOptionStatus": "partial" if mod_option_blockers else "verified",
        },
        "simulationReadiness": {
            "status": simulation_status,
            "blockers": simulation_blockers,
            "partialExamples": gear_catalog_variant_readiness_examples(conn, ["partial"]),
            "blockedExamples": gear_catalog_variant_readiness_examples(conn, ["blocked"]),
            "verified": verified_count,
            "partial": partial_count,
            "blocked": blocked_count,
            "total": variant_count,
        },
        "blockers": all_blockers,
        "status": status,
    }


def gear_catalog_revision_from_counts(counts, season=None):
    season_revision = (season or {}).get("seasonRevision") or (season or {}).get("revision") or "unknown"
    digest = hashlib.sha256(
        json.dumps(
            {
                "seasonRevision": season_revision,
                "itemCount": counts.get("itemCount") or 0,
                "sourceCount": counts.get("sourceCount") or 0,
                "variantCount": counts.get("variantCount") or 0,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"{GEAR_CATALOG_REVISION}-{digest}"


def catalog_health_coverage(covered, total):
    covered = int_or_zero(covered)
    total = int_or_zero(total)
    percent = round((covered / total) * 100, 2) if total else 0
    return {"covered": covered, "total": total, "percent": percent}


def catalog_health_contract(
    *,
    status,
    checked_at="",
    schema_revision="",
    revision="",
    source_status="",
    coverage=None,
    top_blockers=None,
    last_error="",
    stale_after="",
):
    return {
        "status": str(status or "blocked").strip() or "blocked",
        "checkedAt": str(checked_at or "").strip(),
        "schemaRevision": str(schema_revision or "").strip(),
        "revision": str(revision or "").strip(),
        "sourceStatus": str(source_status or "").strip(),
        "coverage": coverage or catalog_health_coverage(0, 0),
        "topBlockers": top_blockers or [],
        "lastError": str(last_error or "").strip(),
        "staleAfter": str(stale_after or "").strip(),
    }


def weapon_rule_coverage():
    expected = set(expected_spec_pairs())
    covered = {f"{class_key}:{spec_key}" for class_key, spec_key in SPEC_WEAPON_EQUIPMENT_RULES}
    missing = sorted(expected - covered)
    extra = sorted(covered - expected)
    examples = []
    for class_spec in sorted(covered & expected)[:5]:
        class_key, spec_key = class_spec.split(":", 1)
        rule = weapon_equipment_rule_payload(class_key, spec_key)
        examples.append({
            "classKey": class_key,
            "specKey": spec_key,
            "mode": rule.get("mode") or "",
            "mainHandTypes": rule.get("mainHandTypes") or [],
            "offHandTypes": rule.get("offHandTypes") or [],
        })
    return {
        "totalClassCount": len(WOW_CLASSES),
        "totalSpecCount": len(expected),
        "coveredSpecCount": len(covered & expected),
        "missingRuleCount": len(missing),
        "extraRuleCount": len(extra),
        "missingRules": missing,
        "extraRules": extra,
        "examples": examples,
    }


def build_gear_catalog_sync_state(conn, season=None):
    repair_websim_item_slots_from_payload(conn)
    counts = gear_catalog_counts(conn)
    revision = gear_catalog_revision_from_counts(counts, season)
    return {
        "status": counts["status"],
        "itemDatabaseRevision": revision,
        "variantRevision": revision,
        "checkedAt": utc_now(),
        "schemaRevision": GEAR_CATALOG_REVISION,
        **counts,
    }


def gear_catalog_sync_state(conn):
    ensure_websim_tables(conn)
    counts = gear_catalog_counts(conn)
    state = get_sync_state(conn, "gearCatalog") or {}
    fallback_revision = gear_catalog_revision_from_counts(counts, get_active_season_payload(conn))
    if not state:
        return {
            "status": counts["status"],
            "itemDatabaseRevision": fallback_revision,
            "variantRevision": fallback_revision,
            "checkedAt": "",
            "schemaRevision": GEAR_CATALOG_REVISION,
            **counts,
        }
    merged = {
        **counts,
        "status": counts["status"],
        "itemDatabaseRevision": state.get("itemDatabaseRevision") or fallback_revision,
        "variantRevision": state.get("variantRevision") or state.get("itemDatabaseRevision") or fallback_revision,
        "checkedAt": state.get("checkedAt") or state.get("updatedAt") or "",
        "schemaRevision": state.get("schemaRevision") or GEAR_CATALOG_REVISION,
    }
    return merged


def talent_catalog_spell_detail_coverage(conn):
    rows = conn.execute(
        """
        SELECT talent_spell.spell_id, s.id, s.description, s.icon_url
        FROM (
            SELECT DISTINCT spell_id
            FROM websim_talents
            WHERE spell_id > 0
        ) AS talent_spell
        LEFT JOIN websim_spell_details s ON s.spell_id = talent_spell.spell_id
        ORDER BY talent_spell.spell_id
        """
    ).fetchall()
    talent_spell_count = len(rows)
    covered = 0
    missing_detail = 0
    missing_description = 0
    unresolved_description = 0
    missing_icon = 0
    for row in rows:
        has_detail = bool(row[1])
        description_text = normalize_spell_display_text(row[2] or "")
        has_description = bool(description_text)
        has_unresolved_description = bool(has_description and spell_text_has_unresolved_tokens(description_text))
        has_icon = bool(str(row[3] or "").strip())
        if not has_detail:
            missing_detail += 1
        if not has_description:
            missing_description += 1
        if has_unresolved_description:
            unresolved_description += 1
        if not has_icon:
            missing_icon += 1
        if has_detail and has_description and not has_unresolved_description and has_icon:
            covered += 1
    return {
        "talentSpellCount": talent_spell_count,
        "coveredSpellCount": covered,
        "missingSpellDetailCount": missing_detail,
        "missingDescriptionCount": missing_description,
        "unresolvedDescriptionCount": unresolved_description,
        "missingIconCount": missing_icon,
        "coverage": catalog_health_coverage(covered, talent_spell_count),
    }


def talent_catalog_latest_updated_at(conn):
    values = []
    for table_name in (
        "websim_talents",
        "websim_spell_details",
        "websim_profile_presets",
        "websim_community_talent_templates",
    ):
        row = conn.execute(f"SELECT MAX(updated_at) FROM {table_name}").fetchone()
        if row and row[0]:
            values.append(str(row[0]))
    return max(values) if values else ""


def talent_catalog_counts(conn):
    ensure_websim_tables(conn)
    talent_rows = conn.execute(
        """
        SELECT class_key, spec_key, spell_id, payload_json
        FROM websim_talents
        WHERE spell_id > 0
        """
    ).fetchall()
    class_keys = set()
    spec_pairs = set()
    hero_trees = set()
    hero_tree_triplets = set()
    tree_type_counts = {"class": 0, "spec": 0, "hero": 0, "unknown": 0}
    for class_key, spec_key, _spell_id, payload_json in talent_rows:
        class_key = str(class_key or "").strip()
        spec_key = str(spec_key or "").strip()
        if class_key:
            class_keys.add(class_key)
        payload = safe_json_loads(payload_json, {})
        tree_type = str((payload or {}).get("treeType") or "").strip()
        if tree_type not in tree_type_counts:
            tree_type = "unknown"
        tree_type_counts[tree_type] += 1
        if tree_type == "spec" and class_key and spec_key:
            spec_pairs.add(f"{class_key}:{spec_key}")
        if tree_type == "hero":
            hero_key = str((payload or {}).get("heroKey") or "").strip()
            if hero_key:
                hero_trees.add(hero_key)
                if class_key and spec_key:
                    hero_tree_triplets.add(f"{class_key}:{spec_key}:{hero_key}")
            if class_key and spec_key:
                spec_pairs.add(f"{class_key}:{spec_key}")
    spell_detail_coverage = talent_catalog_spell_detail_coverage(conn)
    profile_preset_count = conn.execute("SELECT COUNT(*) FROM websim_profile_presets").fetchone()[0] or 0
    community_rows = conn.execute(
        """
        SELECT status, source_status
        FROM websim_community_talent_templates
        """
    ).fetchall()
    community_status_counts = {}
    community_source_status_counts = {}
    for status, source_status in community_rows:
        status = str(status or "unknown").strip() or "unknown"
        source_status = str(source_status or "unknown").strip() or "unknown"
        community_status_counts[status] = community_status_counts.get(status, 0) + 1
        community_source_status_counts[source_status] = community_source_status_counts.get(source_status, 0) + 1
    expected_specs = set(expected_spec_pairs())
    covered_expected_specs = spec_pairs & expected_specs if expected_specs else spec_pairs
    missing_specs = sorted(expected_specs - spec_pairs) if expected_specs else []
    expected_heroes = set(expected_hero_tree_triplets())
    covered_expected_heroes = hero_tree_triplets & expected_heroes if expected_heroes else hero_tree_triplets
    missing_heroes = sorted(expected_heroes - hero_tree_triplets) if expected_heroes else []
    return {
        "talentCount": len(talent_rows),
        "classCount": len(class_keys),
        "specCount": len(spec_pairs),
        "heroTreeCount": len(hero_trees),
        "treeTypeCounts": tree_type_counts,
        "profilePresetCount": profile_preset_count,
        "communityTemplateCount": len(community_rows),
        "communityTemplateStatusCounts": community_status_counts,
        "communityTemplateSourceStatusCounts": community_source_status_counts,
        "expectedSpecCount": len(expected_specs),
        "coveredExpectedSpecCount": len(covered_expected_specs),
        "missingSpecCount": len(missing_specs),
        "missingSpecs": missing_specs[:40],
        "expectedHeroTreeCount": len(expected_heroes),
        "coveredExpectedHeroTreeCount": len(covered_expected_heroes),
        "missingHeroTreeCount": len(missing_heroes),
        "missingHeroTrees": missing_heroes[:40],
        "spellDetailCoverage": spell_detail_coverage,
        "updatedAt": talent_catalog_latest_updated_at(conn),
    }


def talent_catalog_revision_from_counts(counts, sync_state=None):
    simc_state = (sync_state or {}).get("simc") if isinstance((sync_state or {}).get("simc"), dict) else {}
    digest = hashlib.sha256(
        json.dumps(
            {
                "talentCount": counts.get("talentCount") or 0,
                "classCount": counts.get("classCount") or 0,
                "specCount": counts.get("specCount") or 0,
                "heroTreeCount": counts.get("heroTreeCount") or 0,
                "profilePresetCount": counts.get("profilePresetCount") or 0,
                "communityTemplateCount": counts.get("communityTemplateCount") or 0,
                "coveredSpellCount": (counts.get("spellDetailCoverage") or {}).get("coveredSpellCount") or 0,
                "unresolvedDescriptionCount": (counts.get("spellDetailCoverage") or {}).get("unresolvedDescriptionCount") or 0,
                "simcBuild": simc_state.get("build") or simc_state.get("version") or "",
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"{TALENT_CATALOG_REVISION}-{digest}"


def talent_catalog_health_payload(conn):
    ensure_websim_tables(conn)
    counts = talent_catalog_counts(conn)
    sync_state = get_sync_state(conn, "websim_sync") or {}
    simc_state = sync_state.get("simc") if isinstance(sync_state.get("simc"), dict) else {}
    community_state = community_talent_sync_state(conn)
    spell_coverage = counts.get("spellDetailCoverage") or {}
    blockers = []
    if not counts.get("talentCount"):
        blockers.append("talent catalog has no local talent nodes")
    if counts.get("missingSpecCount"):
        blockers.append(f"talent catalog missing {counts.get('missingSpecCount')} expected specs")
    if counts.get("missingHeroTreeCount"):
        blockers.append(f"talent catalog missing {counts.get('missingHeroTreeCount')} expected hero trees")
    if spell_coverage.get("missingSpellDetailCount"):
        blockers.append(f"talent spell details missing for {spell_coverage.get('missingSpellDetailCount')} talent spells")
    if spell_coverage.get("missingDescriptionCount"):
        blockers.append(f"talent spell descriptions missing for {spell_coverage.get('missingDescriptionCount')} talent spells")
    if spell_coverage.get("unresolvedDescriptionCount"):
        blockers.append(
            "talent spell descriptions contain unresolved formula text for "
            f"{spell_coverage.get('unresolvedDescriptionCount')} talent spells"
        )
    if spell_coverage.get("missingIconCount"):
        blockers.append(f"talent spell icons missing for {spell_coverage.get('missingIconCount')} talent spells")
    if counts.get("talentCount") and counts.get("profilePresetCount", 0) == 0:
        blockers.append("talent catalog has no SimC profile presets")
    top_blockers = [{"reason": reason, "count": 1} for reason in blockers[:8]]
    status = "blocked" if not counts.get("talentCount") else "partial"
    checked_at = sync_state.get("checkedAt") or sync_state.get("updatedAt") or counts.get("updatedAt") or ""
    revision = talent_catalog_revision_from_counts(counts, sync_state)
    source_status = "simc" if counts.get("talentCount") else "blocked"
    spec_coverage = catalog_health_coverage(counts.get("coveredExpectedSpecCount") or 0, counts.get("expectedSpecCount") or 0)
    hero_coverage = catalog_health_coverage(
        counts.get("coveredExpectedHeroTreeCount") or 0,
        counts.get("expectedHeroTreeCount") or 0,
    )
    tree_type_counts = counts.get("treeTypeCounts") or {}
    tree_ready = bool(
        counts.get("talentCount")
        and not counts.get("missingSpecCount")
        and not counts.get("missingHeroTreeCount")
        and all((tree_type_counts.get(tree_type) or 0) > 0 for tree_type in ("class", "spec", "hero"))
    )
    rule_ready = tree_ready and source_status == "simc"
    spell_ready = bool(
        spell_coverage.get("talentSpellCount")
        and not spell_coverage.get("missingSpellDetailCount")
        and not spell_coverage.get("missingDescriptionCount")
        and not spell_coverage.get("unresolvedDescriptionCount")
        and not spell_coverage.get("missingIconCount")
    )
    preset_ready = counts.get("profilePresetCount", 0) > 0
    encoding_ready = rule_ready
    rule_readiness = {
        "source": "simulationcraft" if counts.get("talentCount") else "none",
        "treeReady": tree_ready,
        "ruleReady": rule_ready,
        "specCoverage": spec_coverage,
        "heroTreeCoverage": hero_coverage,
        "treeTypeCounts": tree_type_counts,
        "edgeSourceCoverage": catalog_health_coverage(counts.get("talentCount") or 0, counts.get("talentCount") or 0),
    }
    source_readiness = {
        "runtimeSource": source_status,
        "simcBuild": simc_state.get("build") or simc_state.get("version") or "",
        "communityTemplateSourceStatus": community_state.get("sourceStatus") or "",
        "officialAuditStatus": "pending_official_audit",
    }
    readiness = {
        "treeReady": tree_ready,
        "ruleReady": rule_ready,
        "spellReady": spell_ready,
        "encodingReady": encoding_ready,
        "presetReady": preset_ready,
        "simcReady": bool(tree_ready and rule_ready and encoding_ready and preset_ready),
        "blockers": unique_text_list(blockers),
    }
    contract = catalog_health_contract(
        status=status,
        checked_at=checked_at,
        schema_revision=TALENT_CATALOG_REVISION,
        revision=revision,
        source_status=source_status,
        coverage=spell_coverage.get("coverage") or catalog_health_coverage(0, 0),
        top_blockers=top_blockers,
        last_error="; ".join(blockers[:3]) if status == "blocked" else "",
    )
    return {
        "status": status,
        "checkedAt": checked_at,
        "details": {
            "schemaRevision": TALENT_CATALOG_REVISION,
            "talentSchemaRevision": TALENT_SCHEMA_REVISION,
            "revision": revision,
            "sourceStatus": source_status,
            "officialAuditStatus": "pending_official_audit",
            "simcBuild": simc_state.get("build") or simc_state.get("version") or "",
            "talentCount": counts.get("talentCount") or 0,
            "classCount": counts.get("classCount") or 0,
            "specCount": counts.get("specCount") or 0,
            "heroTreeCount": counts.get("heroTreeCount") or 0,
            "treeTypeCounts": counts.get("treeTypeCounts") or {},
            "profilePresetCount": counts.get("profilePresetCount") or 0,
            "communityTemplateCount": counts.get("communityTemplateCount") or 0,
            "communityTemplateStatusCounts": counts.get("communityTemplateStatusCounts") or {},
            "communityTemplateSourceStatusCounts": counts.get("communityTemplateSourceStatusCounts") or {},
            "expectedSpecCount": counts.get("expectedSpecCount") or 0,
            "coveredExpectedSpecCount": counts.get("coveredExpectedSpecCount") or 0,
            "missingSpecCount": counts.get("missingSpecCount") or 0,
            "missingSpecs": counts.get("missingSpecs") or [],
            "expectedHeroTreeCount": counts.get("expectedHeroTreeCount") or 0,
            "coveredExpectedHeroTreeCount": counts.get("coveredExpectedHeroTreeCount") or 0,
            "missingHeroTreeCount": counts.get("missingHeroTreeCount") or 0,
            "missingHeroTrees": counts.get("missingHeroTrees") or [],
            "ruleReadiness": rule_readiness,
            "sourceReadiness": source_readiness,
            "readiness": readiness,
            "spellDetailCoverage": spell_coverage,
            "communityTemplateSync": {
                "sourceStatus": community_state.get("sourceStatus") or "",
                "templateRevision": community_state.get("templateRevision") or "",
                "scanCoverage": community_state.get("scanCoverage") or {},
            },
            "topBlockers": top_blockers,
            "catalogContract": contract,
        },
        "blockers": blockers[:8],
    }


def gear_catalog_health_payload(conn):
    state = gear_catalog_sync_state(conn)
    observed_backfill = read_gear_observed_backfill_state(conn)
    variant_readiness = {
        "verified": state.get("verifiedCount") or 0,
        "partial": state.get("partialCount") or 0,
        "blocked": state.get("blockedCount") or 0,
        "total": state.get("variantCount") or 0,
    }
    top_blockers = state.get("topBlockers") or []
    catalog_contract = catalog_health_contract(
        status=state.get("status") or "blocked",
        checked_at=state.get("checkedAt") or "",
        schema_revision=state.get("schemaRevision") or GEAR_CATALOG_REVISION,
        revision=state.get("variantRevision") or state.get("itemDatabaseRevision") or "",
        source_status=state.get("status") or "blocked",
        coverage=catalog_health_coverage(state.get("verifiedCount") or 0, state.get("variantCount") or 0),
        top_blockers=top_blockers,
    )
    return {
        "status": state.get("status") or "blocked",
        "checkedAt": state.get("checkedAt") or "",
        "details": {
            "itemCount": state.get("itemCount") or 0,
            "sourceCount": state.get("sourceCount") or 0,
            "variantCount": state.get("variantCount") or 0,
            "modOptionCount": state.get("modOptionCount") or 0,
            "verifiedCount": state.get("verifiedCount") or 0,
            "partialCount": state.get("partialCount") or 0,
            "blockedCount": state.get("blockedCount") or 0,
            "observedVariantCount": state.get("observedVariantCount") or 0,
            "verifiedObservedVariantCount": state.get("verifiedObservedVariantCount") or 0,
            "partialObservedVariantCount": state.get("partialObservedVariantCount") or 0,
            "blockedObservedVariantCount": state.get("blockedObservedVariantCount") or 0,
            "observedStatCoverage": state.get("observedStatCoverage") or gear_catalog_observed_stat_coverage(conn),
            "variantReadiness": variant_readiness,
            "itemDatabaseRevision": state.get("itemDatabaseRevision") or "",
            "variantRevision": state.get("variantRevision") or "",
            "schemaRevision": state.get("schemaRevision") or GEAR_CATALOG_REVISION,
            "catalogContract": catalog_contract,
            "observedBackfill": {
                "provider": observed_backfill.get("provider") or "raiderio",
                "providers": observed_backfill.get("providers") or {
                    "raiderio": {"status": "idle"},
                    "wcl": {"status": "not_implemented"},
                },
                "lastRunStatus": observed_backfill.get("lastRunStatus") or "idle",
                "lastRunStartedAt": observed_backfill.get("lastRunStartedAt"),
                "lastRunFinishedAt": observed_backfill.get("lastRunFinishedAt"),
                "processedTargetItemCount": observed_backfill.get("processedTargetItemCount") or 0,
                "processedProfileCount": observed_backfill.get("processedProfileCount") or 0,
                "simcProfileCount": observed_backfill.get("simcProfileCount") or 0,
                "simcResolvedProfileCount": observed_backfill.get("simcResolvedProfileCount") or 0,
                "simcResolvedSlotCount": observed_backfill.get("simcResolvedSlotCount") or 0,
                "matchedTargetItemIds": observed_backfill.get("matchedTargetItemIds") or [],
                "matchedTargetItemCount": len(observed_backfill.get("matchedTargetItemIds") or []),
                "lastError": observed_backfill.get("lastError"),
                "updatedAt": observed_backfill.get("updatedAt") or "",
                "cursor": observed_backfill.get("cursor") or {
                    "targetItemHash": gear_observed_backfill_target_hash([]),
                    "targetItemCount": 0,
                    "targetOffset": 0,
                    "profileOffset": 0,
                },
            },
            "slotCoverage": state.get("slotCoverage") or {
                "coveredSlotCount": 0,
                "totalSlotCount": len(CANONICAL_GEAR_SLOTS),
                "coveredSlots": [],
                "missingSlots": list(CANONICAL_GEAR_SLOTS),
                "itemsBySlot": {},
            },
            "sourceCoverage": state.get("sourceCoverage") or {},
            "sourceGapCoverage": state.get("sourceGapCoverage") or gear_catalog_source_gap_coverage(conn),
            "modOptionCoverage": state.get("modOptionCoverage") or gear_catalog_mod_option_coverage(conn),
            "weaponRuleCoverage": state.get("weaponRuleCoverage") or weapon_rule_coverage(),
            "itemMetadata": state.get("itemMetadata") or gear_catalog_item_metadata_audit(conn),
            "seasonSourceCoverage": state.get("seasonSourceCoverage") or gear_catalog_season_source_coverage(conn),
            "topBlockers": top_blockers,
            "dataReadiness": state.get("dataReadiness") or {
                "status": "blocked",
                "blockers": ["gear catalog has not been synced"],
            },
            "simulationReadiness": state.get("simulationReadiness") or {
                "status": "blocked",
                "blockers": ["gear catalog has not been synced"],
                **variant_readiness,
            },
        },
        "blockers": state.get("blockers") or ([] if state.get("itemCount") else ["gear catalog has not been synced"]),
    }


def gear_catalog_sources_by_item(conn):
    ensure_websim_tables(conn)
    rows = conn.execute(
        """
        SELECT id, item_id, source_type, source_label, instance_id, encounter_id,
               difficulty_key, season_revision, payload_json, updated_at
        FROM websim_gear_sources
        ORDER BY item_id, source_type, source_label
        """
    ).fetchall()
    result = {}
    for row in rows:
        payload = safe_json_loads(row[8], {})
        source = {
            "id": row[0],
            "itemId": row[1],
            "sourceType": row[2],
            "label": row[3],
            "sourceLabel": row[3],
            "instanceId": row[4],
            "encounterId": row[5],
            "difficultyKey": row[6],
            "difficultyLabel": localized_difficulty_label(row[6], row[3], row[2]),
            "seasonRevision": row[7],
            "payload": payload if isinstance(payload, dict) else {},
            "updatedAt": row[9],
        }
        if isinstance(payload, dict) and payload.get("recommendationScore") is not None:
            source["recommendationScore"] = payload.get("recommendationScore")
        result.setdefault(str(row[1]), []).append(source)
    return result


def gear_catalog_variants_by_item(conn):
    ensure_websim_tables(conn)
    rows = conn.execute(
        """
        SELECT id, item_id, slot, variant_key, label, source_type, difficulty_key,
               item_level, simc_options_json, status, blockers_json, payload_json, updated_at
        FROM websim_gear_variants
        ORDER BY item_id, item_level DESC, label
        """
    ).fetchall()
    result = {}
    for row in rows:
        simc_options = safe_json_loads(row[8], {})
        if not isinstance(simc_options, dict):
            simc_options = {}
        blockers = safe_json_loads(row[10], [])
        if not isinstance(blockers, list):
            blockers = [str(blockers)]
        payload = safe_json_loads(row[11], {})
        item_level = int(row[7] or 0)
        variant = {
            "id": row[0],
            "itemId": row[1],
            "slot": normalize_slot(row[2]),
            "key": row[3],
            "variantKey": row[3],
            "label": row[4],
            "difficultyLabel": localized_difficulty_label(row[6], row[4], row[5]),
            "sourceType": row[5],
            "difficultyKey": row[6],
            "itemLevel": item_level,
            "ilevel": item_level,
            "simcOptions": {key: normalize_option_value(value) for key, value in simc_options.items() if key in SIMC_GEAR_OPTION_KEYS},
            "status": row[9] or "blocked",
            "blockers": [str(item) for item in blockers if str(item or "").strip()],
            "payload": payload if isinstance(payload, dict) else {},
            "updatedAt": row[12],
        }
        if isinstance(payload, dict) and payload.get("simcIlevelOnly"):
            variant["simcIlevelOnly"] = True
        result.setdefault(str(row[1]), []).append(variant)
    return result


def text_contains_cjk(value):
    return bool(re.search(r"[\u3400-\u9fff]", str(value or "")))


def display_label_looks_like_raw_id(label, option_type):
    label = str(label or "").strip()
    option_type = str(option_type or "").strip().lower()
    if not label:
        return True
    if re.fullmatch(r"[\w-]*\s*(?:gem|enchant|embellishment)\s*[\d/_-]+", label, re.IGNORECASE):
        return True
    if option_type == "enchant" and re.fullmatch(r"(?:附魔|武器附魔|戒指附魔|披风附魔|胸甲附魔|护腕附魔|靴子附魔|腿部强化)\s*[\d/]+", label):
        return True
    if option_type == "socket" and re.fullmatch(r"(?:宝石|gem)\s*[\d/]+", label, re.IGNORECASE):
        return True
    return False


def clean_gear_mod_display_label(label, option_type=""):
    text = str(label or "").strip()
    if not text:
        return ""
    text = re.sub(r"\|A:[^|]+?\|a", "", text)
    text = re.sub(r"\|T[^|]+?\|t", "", text)
    text = re.sub(r"\|[cC][0-9A-Fa-f]{8}", "", text).replace("|r", "")
    text = re.sub(r"\s+", " ", text).strip()
    if "$" in text:
        return ""
    if str(option_type or "").strip().lower() == "enchant":
        text = re.sub(r"^附魔[^-－—]*[-－—]\s*", "", text).strip()
    return text


def gear_mod_option_display_fields(option_type, name="", simc_options=None, payload=None):
    option_type = str(option_type or "").strip().lower()
    name = str(name or "").strip()
    simc_options = simc_options if isinstance(simc_options, dict) else {}
    payload = payload if isinstance(payload, dict) else {}
    payload_status = str(
        payload.get("displayStatus")
        or payload.get("display_status")
        or payload.get("localizationStatus")
        or payload.get("localization_status")
        or ""
    ).strip().lower()
    evidence_source = str(
        payload.get("evidenceSource")
        or payload.get("evidence_source")
        or payload.get("displaySource")
        or payload.get("display_source")
        or payload.get("metadataSource")
        or ""
    ).strip()
    evidence_ref = str(
        payload.get("evidenceRef")
        or payload.get("evidence_ref")
        or payload.get("displaySourceRef")
        or payload.get("display_source_ref")
        or ""
    ).strip()
    for candidate in (
        payload.get("displayLabel"),
        payload.get("display_label"),
        payload.get("localizedName"),
        payload.get("localized_name"),
        payload.get("zhName"),
        payload.get("zh_name"),
        payload.get("displayName"),
        name,
    ):
        candidate = clean_gear_mod_display_label(candidate, option_type)
        if (
            candidate
            and text_contains_cjk(candidate)
            and not display_label_looks_like_raw_id(candidate, option_type)
            and (payload_status == "verified" or evidence_source)
        ):
            result = {
                "displayLabel": candidate,
                "displayName": candidate,
                "displayKind": "name",
                "displayStatus": "verified",
                "evidenceSource": evidence_source or "server_payload",
            }
            if evidence_ref:
                result["evidenceRef"] = evidence_ref
            return result
    if option_type == "enchant":
        enchant_id = normalize_option_value(
            simc_options.get("enchant_id")
            or payload.get("enchant_id")
            or payload.get("enchantId")
            or payload.get("enchant")
        )
        if enchant_id in GEAR_ENCHANT_LABELS_ZH:
            result = {
                "displayLabel": GEAR_ENCHANT_LABELS_ZH[enchant_id],
                "displayName": GEAR_ENCHANT_LABELS_ZH[enchant_id],
                "displayKind": "name",
                "displayStatus": "verified",
                "evidenceSource": evidence_source or "wago_db2_spell_item_enchantment",
            }
            if evidence_ref:
                result["evidenceRef"] = evidence_ref
            return result
    if option_type == "embellishment":
        key = normalize_option_value(
            simc_options.get("embellishment")
            or payload.get("simcKey")
            or payload.get("simc_key")
            or payload.get("embellishment")
        )
        if key in GEAR_EMBELLISHMENT_LABELS_ZH:
            result = {
                "displayLabel": GEAR_EMBELLISHMENT_LABELS_ZH[key],
                "displayName": GEAR_EMBELLISHMENT_LABELS_ZH[key],
                "displayKind": "name",
                "displayStatus": "verified",
                "evidenceSource": evidence_source or GEAR_EMBELLISHMENT_EVIDENCE_SOURCES.get(key) or "server_owned_evidence_seed",
            }
            if evidence_ref:
                result["evidenceRef"] = evidence_ref
            return result
    return {}


def apply_gear_mod_option_display_fields(option, fields):
    if not isinstance(option, dict) or not isinstance(fields, dict) or not fields.get("displayLabel"):
        return option
    enriched = dict(option)
    display_label = str(fields.get("displayLabel") or "").strip()
    enriched["name"] = display_label
    enriched["label"] = display_label
    enriched["displayName"] = str(fields.get("displayName") or display_label).strip()
    for key in ("displayLabel", "displayKind", "displayStatus", "evidenceSource", "evidenceRef"):
        if fields.get(key) not in (None, "", [], {}):
            enriched[key] = fields.get(key)
    return enriched


def gear_mod_option_has_verified_display_fields(option_type, option):
    if not isinstance(option, dict):
        return False
    label = str(option.get("displayLabel") or option.get("label") or option.get("name") or "").strip()
    display_status = str(option.get("displayStatus") or "").strip().lower()
    if display_status != "verified":
        return False
    return bool(label and text_contains_cjk(label) and not display_label_looks_like_raw_id(label, option_type))


def gear_catalog_mod_options_by_slot(conn, option_type):
    ensure_websim_tables(conn)
    rows = conn.execute(
        """
        SELECT id, option_type, name, applicable_slots_json, simc_options_json,
               status, payload_json, updated_at
        FROM websim_gear_mod_options
        WHERE option_type = ?
        ORDER BY status DESC, name
        """,
        (option_type,),
    ).fetchall()
    result = {slot: [] for slot in CANONICAL_GEAR_SLOTS}
    for row in rows:
        slots = safe_json_loads(row[3], [])
        if not isinstance(slots, list):
            slots = []
        normalized_slots = [normalize_slot(slot) for slot in slots]
        normalized_slots = [slot for slot in normalized_slots if slot]
        if not normalized_slots or "*" in slots:
            normalized_slots = list(SOCKET_OPTION_GEAR_SLOT_LIST if option_type == "socket" else CANONICAL_GEAR_SLOTS)
        if option_type == "socket":
            normalized_slots = [slot for slot in normalized_slots if slot in SOCKET_OPTION_GEAR_SLOTS]
            if not normalized_slots:
                continue
        simc_options = safe_json_loads(row[4], {})
        if not isinstance(simc_options, dict):
            simc_options = {}
        payload = safe_json_loads(row[6], {})
        payload = payload if isinstance(payload, dict) else {}
        normalized_simc_options = {
            key: normalize_option_value(value)
            for key, value in simc_options.items()
            if key in SIMC_GEAR_OPTION_KEYS
        }
        payload = gear_mod_option_payload_with_config_policy(
            row[1],
            row[2],
            normalized_simc_options,
            payload,
            normalized_slots,
        )
        if not gear_mod_option_is_supported_config_option(row[1], normalized_simc_options, payload, row[2]):
            continue
        display_fields = gear_mod_option_display_fields(row[1], row[2], normalized_simc_options, payload)
        display_label = str(display_fields.get("displayLabel") or row[2] or row[0]).strip()
        option = {
            "id": row[0],
            "type": row[1],
            "optionType": row[1],
            "name": display_label,
            "label": display_label,
            "rawName": row[2],
            "simcOptions": normalized_simc_options,
            "status": row[5] or "blocked",
            "payload": payload,
            "updatedAt": row[7],
        }
        option = apply_gear_mod_option_display_fields(option, display_fields)
        for key in (
            "gemItemId",
            "gemItemIds",
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
        if row[1] == "socket" and "gemItemId" not in option:
            gem_item_ids = gem_item_ids_from_simc_options(normalized_simc_options)
            if len(gem_item_ids) == 1:
                option["gemItemId"] = gem_item_ids[0]
            elif gem_item_ids:
                option["gemItemIds"] = gem_item_ids
        for slot in normalized_slots:
            result.setdefault(slot, []).append(dict(option))
    return result


def verified_gem_metadata_records_for_socket_option(conn, option):
    if not isinstance(option, dict):
        return []
    payload = option.get("payload") if isinstance(option.get("payload"), dict) else {}
    simc_options = option.get("simcOptions") if isinstance(option.get("simcOptions"), dict) else {}
    gem_item_ids = gem_item_ids_from_simc_options(simc_options)
    if not gem_item_ids:
        fallback_gem_id = normalize_option_value(option.get("gemItemId") or payload.get("gemItemId"))
        gem_item_ids = [fallback_gem_id] if fallback_gem_id else []
    if not gem_item_ids:
        return []
    payload_gem_items = payload.get("gemItems") if isinstance(payload.get("gemItems"), list) else []
    payload_gem_items_by_id = {
        str(item.get("itemId") or "").strip(): item
        for item in payload_gem_items
        if isinstance(item, dict) and str(item.get("itemId") or "").strip()
    }
    records = []
    for gem_item_id in gem_item_ids:
        gem_metadata = existing_websim_item_metadata(conn, gem_item_id)
        if not gem_metadata:
            return []
        gem_payload = gem_metadata.get("payload") if isinstance(gem_metadata.get("payload"), dict) else {}
        gem_item_class = gem_payload.get("item_class") if isinstance(gem_payload.get("item_class"), dict) else {}
        if not payload_item_class_is_gem(gem_item_class):
            return []
        payload_gem_item = payload_gem_items_by_id.get(gem_item_id, {})
        option_icon = str(
            payload_gem_item.get("iconUrl")
            or (option.get("iconUrl") if len(gem_item_ids) == 1 else "")
            or (payload.get("iconUrl") if len(gem_item_ids) == 1 else "")
            or ""
        ).strip()
        option_status = str(
            payload_gem_item.get("metadataStatus")
            or (option.get("metadataStatus") if len(gem_item_ids) == 1 else "")
            or (payload.get("metadataStatus") if len(gem_item_ids) == 1 else "")
            or ""
        ).strip()
        has_verified_option_metadata = bool(option_icon and option_status == "verified")
        has_verified_tooltip_display = bool(verified_socket_option_payload_stat_summary(payload, len(gem_item_ids)))
        has_verified_gem_metadata = bool(
            str(gem_metadata.get("iconUrl") or "").strip()
            and str(gem_metadata.get("metadataStatus") or "") == "verified"
            and str(gem_metadata.get("metadataSource") or "") == ITEM_METADATA_SOURCE
        )
        if not (has_verified_option_metadata or has_verified_tooltip_display) or not has_verified_gem_metadata:
            return []
        records.append(gem_metadata)
    return records


def verified_gem_metadata_for_socket_option(conn, option):
    records = verified_gem_metadata_records_for_socket_option(conn, option)
    return records[0] if records else None


def display_ready_socket_mod_option(conn, option):
    if not isinstance(option, dict):
        return None
    option_id = str(option.get("id") or "").strip()
    option_name = str(option.get("name") or option.get("label") or "").strip()
    payload = option.get("payload") if isinstance(option.get("payload"), dict) else {}
    if not gear_mod_option_is_visible(option_id, option_name, payload):
        return None
    gem_metadata_records = verified_gem_metadata_records_for_socket_option(conn, option)
    if not gem_metadata_records:
        return None
    display_name = " / ".join(
        str(record.get("displayName") or f"Gem {record.get('itemId') or ''}").strip()
        for record in gem_metadata_records
        if str(record.get("itemId") or "").strip()
    )
    gem_metadata = gem_metadata_records[0]
    enriched = dict(option)
    enriched["name"] = display_name or gem_metadata.get("displayName") or enriched.get("name") or enriched.get("label")
    enriched["label"] = display_name or gem_metadata.get("displayName") or enriched.get("label") or enriched.get("name")
    enriched["displayName"] = display_name or gem_metadata.get("displayName") or enriched.get("displayName") or enriched.get("label")
    enriched["iconUrl"] = gem_metadata.get("iconUrl") or enriched.get("iconUrl")
    enriched["gameAsset"] = gem_metadata.get("gameAsset") or enriched.get("gameAsset")
    enriched["metadataStatus"] = gem_metadata.get("metadataStatus") or enriched.get("metadataStatus")
    enriched["metadataSource"] = gem_metadata.get("metadataSource") or enriched.get("metadataSource")
    enriched["gemItemId"] = gem_metadata.get("itemId") or enriched.get("gemItemId")
    enriched["gemItemIds"] = [record.get("itemId") for record in gem_metadata_records if record.get("itemId")]
    option_stat_summary = verified_socket_option_payload_stat_summary(payload, len(gem_metadata_records))
    stat_summaries = (
        [option_stat_summary]
        if option_stat_summary
        else [
            summary
            for record in gem_metadata_records
            for summary in [gem_metadata_stat_summary(record)]
            if summary
        ]
    )
    if not stat_summaries:
        return None
    stat_summary = " / ".join(stat_summaries)
    enriched["statSummary"] = stat_summary
    enriched["displayLabel"] = stat_summary
    enriched["displayKind"] = payload.get("displayKind") or "stat"
    enriched["displayStatus"] = payload.get("displayStatus") or "verified"
    enriched["evidenceSource"] = payload.get("evidenceSource") or ITEM_METADATA_SOURCE
    if payload.get("evidenceRef"):
        enriched["evidenceRef"] = payload.get("evidenceRef")
    if payload.get("statDisplayStatus"):
        enriched["statDisplayStatus"] = payload.get("statDisplayStatus")
    if gem_metadata.get("itemStats"):
        enriched["itemStats"] = gem_metadata.get("itemStats")
    enriched["gemItems"] = [
        {
            "itemId": record.get("itemId"),
            "displayName": record.get("displayName"),
            "iconUrl": record.get("iconUrl"),
            "quality": record.get("quality"),
            "gameAsset": record.get("gameAsset"),
            "itemStats": record.get("itemStats"),
            "statSummary": option_stat_summary if len(gem_metadata_records) == 1 else gem_metadata_stat_summary(record),
            "metadataStatus": record.get("metadataStatus"),
            "metadataSource": record.get("metadataSource"),
            "metadataLocale": record.get("metadataLocale"),
        }
        for record in gem_metadata_records
    ]
    return enriched


def display_ready_named_mod_option(option_type, option):
    if not isinstance(option, dict):
        return None
    option_id = str(option.get("id") or "").strip()
    option_name = str(option.get("name") or option.get("label") or "").strip()
    payload = option.get("payload") if isinstance(option.get("payload"), dict) else {}
    if not gear_mod_option_is_visible(option_id, option_name, payload):
        return None
    option_status = str(option.get("status") or "").strip().lower()
    if option_status != "verified":
        return None
    display_fields = gear_mod_option_display_fields(
        option_type,
        option.get("rawName") or option.get("name") or option.get("label") or "",
        option.get("simcOptions") if isinstance(option.get("simcOptions"), dict) else {},
        payload,
    )
    enriched = apply_gear_mod_option_display_fields(option, display_fields)
    if not gear_mod_option_has_verified_display_fields(option_type, enriched):
        return None
    return enriched


def display_ready_gear_mod_options_by_slot(conn, option_type):
    raw_options = gear_catalog_mod_options_by_slot(conn, option_type)
    if option_type == "socket":
        return {
            slot: [
                ready_option
                for option in options
                for ready_option in [display_ready_socket_mod_option(conn, option)]
                if ready_option
            ]
            for slot, options in raw_options.items()
        }
    if option_type in {"enchant", "embellishment"}:
        return {
            slot: [
                ready_option
                for option in options
                for ready_option in [display_ready_named_mod_option(option_type, option)]
                if ready_option
            ]
            for slot, options in raw_options.items()
        }
    return {slot: visible_gear_mod_options(options) for slot, options in raw_options.items()}


def portable_gear_slot(slot):
    return normalize_slot(slot) in PORTABLE_GEAR_SLOTS


def class_spec_context_from_payload(payload):
    payload = payload if isinstance(payload, dict) else {}
    class_keys = payload.get("classKeys") or payload.get("classes") or []
    spec_keys = payload.get("specKeys") or payload.get("specs") or []
    if isinstance(class_keys, str):
        class_keys = [class_keys]
    if isinstance(spec_keys, str):
        spec_keys = [spec_keys]
    class_values = [str(item or "").strip() for item in class_keys if str(item or "").strip()]
    spec_values = [str(item or "").strip() for item in spec_keys if str(item or "").strip()]
    if payload.get("officialVariantSource"):
        return unique_text_list(class_values), unique_text_list(spec_values)
    for ref in payload.get("observedProfileRefs") or []:
        if not isinstance(ref, dict):
            continue
        class_value = str(ref.get("classKey") or ref.get("class") or "").strip()
        spec_value = str(ref.get("specKey") or ref.get("spec") or "").strip()
        if class_value:
            class_values.append(class_value)
        if spec_value:
            spec_values.append(spec_value)
    return unique_text_list(class_values), unique_text_list(spec_values)


def catalog_context_compatible(row, class_key, spec_key, slot=""):
    if portable_gear_slot(slot):
        return True
    payload = row.get("payload") if isinstance(row, dict) else {}
    if not isinstance(payload, dict):
        return True
    class_keys, spec_keys = class_spec_context_from_payload(payload)
    normalized_classes = {slugify(item, "") for item in class_keys if slugify(item, "")}
    normalized_specs = {slugify(item, "") for item in spec_keys if slugify(item, "")}
    if normalized_classes and class_key not in normalized_classes:
        return False
    if normalized_specs and spec_key not in normalized_specs:
        if payload.get("observedProfileRefs") and normalized_classes and class_key in normalized_classes:
            return True
        return False
    return True


def catalog_variant_compatible(variant, class_key, spec_key, item_slot=""):
    slot = normalize_slot((variant or {}).get("slot") or item_slot)
    return catalog_context_compatible(variant, class_key, spec_key, slot)


def catalog_source_compatible(source, class_key, spec_key, item_slot=""):
    return catalog_context_compatible(source, class_key, spec_key, item_slot)


def catalog_variant_display_key(variant):
    if not isinstance(variant, dict):
        return ("",)
    source_type = raw_source_type(variant.get("sourceType")).lower()
    difficulty_key = str(variant.get("difficultyKey") or "").strip().lower()
    item_level = positive_int_value(variant.get("itemLevel") or variant.get("ilevel"))
    simc_options = variant.get("simcOptions") if isinstance(variant.get("simcOptions"), dict) else {}
    payload = variant.get("payload") if isinstance(variant.get("payload"), dict) else {}
    if source_type == "crafted":
        return (
            source_type,
            difficulty_key,
            item_level,
            normalize_option_value(
                simc_options.get("crafted_stats")
                or payload.get("crafted_stats")
                or payload.get("craftedStats")
                or payload.get("craftedStatKey")
            ),
        )
    if source_type in OFFICIAL_REPLACEMENT_SOURCE_TYPES and item_level > 0:
        return (source_type, item_level)
    if difficulty_key in {"observed_profile", "battle_net_preview"}:
        return (
            source_type,
            difficulty_key,
            item_level,
            normalize_option_value(simc_options.get("bonus_id")),
            normalize_option_value(simc_options.get("crafted_stats")),
        )
    return (
        source_type,
        difficulty_key,
        item_level,
        normalized_candidate_text(variant.get("difficultyLabel") or variant.get("label")),
    )


def catalog_variant_display_score(variant):
    status_rank = {
        "verified": 4,
        "complete": 4,
        "synced": 3,
        "partial": 2,
        "blocked": 0,
    }
    simc_options = (variant or {}).get("simcOptions") if isinstance((variant or {}).get("simcOptions"), dict) else {}
    payload = (variant or {}).get("payload") if isinstance((variant or {}).get("payload"), dict) else {}
    has_variant_stats = bool(
        payload.get("statDisplayStatus") == "verified_variant"
        and (payload.get("itemStats") or payload.get("stats") or payload.get("statSummary"))
    )
    derived_rank = 1 if str(payload.get("derivedVariantSource") or "") == OFFICIAL_ITEM_LEVEL_PROBE_SOURCE else 0
    return (
        status_rank.get(str((variant or {}).get("status") or "").strip().lower(), 0),
        positive_int_value((variant or {}).get("itemLevel") or (variant or {}).get("ilevel")),
        derived_rank,
        1 if has_variant_stats else 0,
        1 if simc_options.get("bonus_id") else 0,
        len([value for value in simc_options.values() if value]),
        str((variant or {}).get("id") or ""),
    )


def catalog_variant_is_pending_placeholder(variant):
    if not isinstance(variant, dict):
        return False
    difficulty_key = str(variant.get("difficultyKey") or "").strip().lower().replace("_", "-")
    variant_key = str(variant.get("variantKey") or variant.get("key") or "").strip().lower().replace("_", "-")
    item_level = positive_int_value(variant.get("itemLevel") or variant.get("ilevel"))
    return item_level <= 0 and (difficulty_key == "needs-variant" or variant_key == "needs-variant")


def catalog_variant_is_official_item_level_probe(variant):
    if not isinstance(variant, dict):
        return False
    source_type = raw_source_type(variant.get("sourceType")).lower()
    payload = variant.get("payload") if isinstance(variant.get("payload"), dict) else {}
    item_level = positive_int_value(variant.get("itemLevel") or variant.get("ilevel"))
    stats = payload.get("itemStats") or payload.get("stats") or []
    return (
        source_type in OFFICIAL_REPLACEMENT_SOURCE_TYPES
        and item_level > 0
        and str(variant.get("status") or "").strip().lower() == "verified"
        and str(payload.get("derivedVariantSource") or "") == OFFICIAL_ITEM_LEVEL_PROBE_SOURCE
        and bool(stats or payload.get("statSummary"))
    )


def collapse_catalog_variants_for_display(variants, limit=0):
    by_key = {}
    for variant in variants or []:
        if not isinstance(variant, dict):
            continue
        key = catalog_variant_display_key(variant)
        if key not in by_key or catalog_variant_display_score(variant) > catalog_variant_display_score(by_key[key]):
            by_key[key] = variant
    collapsed = list(by_key.values())
    if any(positive_int_value(variant.get("itemLevel") or variant.get("ilevel")) > 0 for variant in collapsed):
        collapsed = [variant for variant in collapsed if not catalog_variant_is_pending_placeholder(variant)]
    official_probe_levels = {
        positive_int_value(variant.get("itemLevel") or variant.get("ilevel"))
        for variant in collapsed
        if catalog_variant_is_official_item_level_probe(variant)
    }
    if official_probe_levels:
        collapsed = [
            variant
            for variant in collapsed
            if not (
                raw_source_type(variant.get("sourceType")).lower() == "observed_profile"
                and positive_int_value(variant.get("itemLevel") or variant.get("ilevel")) in official_probe_levels
            )
        ]
    collapsed.sort(key=catalog_variant_display_score, reverse=True)
    if limit and limit > 0:
        return collapsed[:limit]
    return collapsed


def catalog_variant_usable_for_replacement(variant):
    if not isinstance(variant, dict):
        return False
    payload = variant.get("payload") if isinstance(variant.get("payload"), dict) else {}
    source_type = raw_source_type(variant.get("sourceType")).lower()
    difficulty_key = str(variant.get("difficultyKey") or "").strip().lower()
    variant_key = str(variant.get("variantKey") or variant.get("key") or "").strip().lower()
    derived_source = str(payload.get("derivedVariantSource") or "").strip()
    if derived_source == OFFICIAL_ITEM_LEVEL_PROBE_SOURCE:
        status = str(variant.get("status") or payload.get("status") or "").strip().lower()
        stats = payload.get("itemStats") or payload.get("stats") or []
        return status == "verified" and bool(stats)
    if source_type == "crafted" and derived_source == PREEMBELLISHED_CRAFTED_ITEM_LEVEL_PROBE_SOURCE:
        status = str(variant.get("status") or payload.get("status") or "").strip().lower()
        stats = payload.get("itemStats") or payload.get("stats") or []
        return status == "verified" and bool(stats)
    if difficulty_key == "battle_net_preview" or variant_key.startswith("battle-net-preview"):
        return False
    if variant.get("simcIlevelOnly") or payload.get("simcIlevelOnly"):
        return False
    return True


def catalog_variant_has_context(variant):
    payload = variant.get("payload") if isinstance((variant or {}).get("payload"), dict) else {}
    class_keys, spec_keys = class_spec_context_from_payload(payload)
    return bool(class_keys or spec_keys)


def catalog_compatibility(item, sources, variants, class_key, spec_key):
    armor_status = item.get("compatibility") or "unknown"
    item_slot = item.get("slot") or ""
    compatible_sources = [source for source in sources if catalog_source_compatible(source, class_key, spec_key, item_slot)]
    usable_variants = [
        variant
        for variant in variants
        if catalog_variant_usable_for_replacement(variant)
    ]
    compatible_variants = [
        variant
        for variant in usable_variants
        if catalog_variant_compatible(variant, class_key, spec_key, item_slot)
    ]
    scoped_variants = [variant for variant in usable_variants if catalog_variant_has_context(variant)]
    if armor_status == "incompatible" or (sources and not compatible_sources):
        status = "incompatible"
    elif scoped_variants and not compatible_variants:
        status = "incompatible"
    elif compatible_sources or compatible_variants:
        status = "compatible"
    elif usable_variants and not compatible_variants:
        status = "unknown"
    else:
        status = "unknown"
    return {
        "status": status,
        "armorStatus": armor_status,
        "classKey": class_key,
        "specKey": spec_key,
    }


def apply_default_catalog_variant(item, variants, stat_fallback_variants=None):
    if not variants:
        item["defaultVariantKey"] = ""
        item["variantSource"] = ""
        return item
    verified = [variant for variant in variants if variant.get("status") == "verified"]
    default_variant = verified[0] if verified else variants[0]
    item["defaultVariantKey"] = default_variant.get("key") or ""
    item["variantKey"] = default_variant.get("key") or ""
    item["variantLabel"] = default_variant.get("label") or ""
    item["variantDifficultyLabel"] = default_variant.get("difficultyLabel") or localized_difficulty_label(
        default_variant.get("difficultyKey"),
        default_variant.get("label"),
        default_variant.get("sourceType"),
    )
    item["variantDifficultyKey"] = default_variant.get("difficultyKey") or ""
    item["variantSource"] = default_variant.get("sourceType") or ""
    if default_variant.get("itemLevel"):
        item["ilevel"] = default_variant.get("itemLevel")
    variant_payload = default_variant.get("payload") if isinstance(default_variant.get("payload"), dict) else {}
    if default_variant.get("simcIlevelOnly") or variant_payload.get("simcIlevelOnly"):
        item["simcIlevelOnly"] = True
    for key, value in (default_variant.get("simcOptions") or {}).items():
        if key in SIMC_GEAR_OPTION_KEYS and value:
            item[key] = value
    variant_stats = []
    for raw_stat in variant_payload.get("itemStats") or variant_payload.get("stats") or []:
        normalized_stat = normalize_item_stat(raw_stat)
        if normalized_stat:
            variant_stats.append(normalized_stat)
    if variant_stats:
        item["itemStats"] = variant_stats
        item["stats"] = variant_stats
        item["statSummary"] = str(variant_payload.get("statSummary") or item_stat_summary(variant_stats))[:260]
        item["statDisplayStatus"] = str(variant_payload.get("statDisplayStatus") or "verified_variant")[:80]
        item["statSource"] = str(variant_payload.get("statSource") or default_variant.get("sourceType") or "")[:120]
    else:
        for key in OBSERVED_VARIANT_SIMC_FAILURE_PAYLOAD_KEYS:
            if variant_payload.get(key) not in (None, "", [], {}):
                item[key] = variant_payload.get(key)
    item["variantStatus"] = default_variant.get("status") or "blocked"
    item["variantBlockers"] = default_variant.get("blockers") or []
    item["missingFields"] = gear_item_missing_fields(item)
    item["simcReady"] = gear_item_simc_ready(item)
    return item


def catalog_item_trust_blockers(item):
    if not isinstance(item, dict):
        return ["verified Battle.net metadata"]
    blockers = []
    metadata_status = str(item.get("metadataStatus") or "").strip()
    metadata_source = str(item.get("metadataSource") or "").strip()
    if metadata_status != "verified" or metadata_source != ITEM_METADATA_SOURCE:
        blockers.append("verified Battle.net metadata")
    if not item.get("itemStats"):
        blockers.append("Battle.net item stats")
    slot = normalize_slot(item.get("slot"))
    if slot in ARMOR_SLOTS and not item.get("armorType"):
        blockers.append("Battle.net armor type")
    if slot in WEAPON_SLOTS and not item.get("weaponType"):
        blockers.append("Battle.net weapon type")
    return blockers


def text_list_value(value):
    if isinstance(value, list):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    text = str(value or "").strip()
    return [text] if text else []


def catalog_item_should_hide_preview_stats(item):
    if not isinstance(item, dict):
        return False
    if item.get("statDisplayStatus") == "verified_variant" and item.get("itemStats"):
        return False
    if (
        str(item.get("statDisplayStatus") or "").strip() == "battle_net_item_metadata"
        and str(item.get("statSource") or "").strip() in {"", ITEM_METADATA_SOURCE}
        and (item.get("itemStats") or item.get("stats") or item.get("statSummary"))
    ):
        return True
    source_types = {
        raw_source_type(source.get("sourceType"))
        for source in item.get("sources") or []
        if isinstance(source, dict)
    }
    source_types.add(raw_source_type(item.get("variantSource") or item.get("sourceType")))
    normalized_source_types = {source_type.lower() for source_type in source_types if source_type}
    variant_difficulty_key = str(item.get("variantDifficultyKey") or "").strip().lower()
    variant_key = str(item.get("variantKey") or item.get("defaultVariantKey") or "").strip().lower()
    if (
        item.get("simcIlevelOnly")
        or variant_difficulty_key in {"observed_profile", "battle_net_preview"}
        or "observed_profile" in normalized_source_types
        or variant_key.startswith("battle-net-preview")
        or variant_key.startswith("observed-")
    ):
        return True
    if normalized_source_types & {"verifiedloot", "verified_loot", "loot"} and not item.get("simcReady"):
        return True
    if (
        normalized_source_types & {"dungeon", "raid", "tier_set"}
        and str(item.get("statDisplayStatus") or "").strip() == "battle_net_item_metadata"
        and not item.get("simcReady")
    ):
        return True
    if item.get("simcReady") or positive_int_value(item.get("ilevel") or item.get("itemLevel")) > 0:
        return False
    if not (normalized_source_types & {"dungeon", "raid", "tier_set"}):
        return False
    status = str(item.get("variantStatus") or "").strip().lower()
    if status not in {"", "partial", "blocked"}:
        return False
    blockers = [
        *text_list_value(item.get("blockers")),
        *text_list_value(item.get("variantBlockers")),
        *text_list_value(item.get("missingFields")),
    ]
    blocker_text = " ".join(blockers).lower()
    return (
        "deterministic simc variant" in blocker_text
        or "bonus_id/gem_id/enchant_id" in blocker_text
        or "ilevel" in blocker_text
    )


def candidate_uses_observed_current_variant(item):
    if not isinstance(item, dict):
        return False
    variant_source = raw_source_type(item.get("variantSource") or "").lower()
    difficulty_key = str(item.get("variantDifficultyKey") or "").strip().lower()
    variant_key = str(item.get("variantKey") or item.get("defaultVariantKey") or "").strip().lower()
    return variant_source == "observed_profile" or difficulty_key == "observed_profile" or variant_key.startswith("observed-")


def hide_candidate_current_variant_stats(item):
    if not isinstance(item, dict):
        return item
    item.pop("itemStats", None)
    item.pop("stats", None)
    item.pop("statSummary", None)
    item.pop("statSource", None)
    item["statDisplayStatus"] = "pending_current_variant"
    if candidate_uses_observed_current_variant(item):
        item["missingFields"] = unique_text_list([*(item.get("missingFields") or []), "SimulationCraft item stats"])
        item["blockers"] = unique_text_list([*(item.get("blockers") or []), "SimulationCraft item stats"])
    return item


def observed_profile_refs_from_catalog(sources, variants):
    refs = []
    seen = set()
    for row in [*(sources or []), *(variants or [])]:
        payload = row.get("payload") if isinstance(row, dict) else {}
        if not isinstance(payload, dict):
            payload = {}
        for ref in payload.get("observedProfileRefs") or []:
            if not isinstance(ref, dict):
                continue
            key = json.dumps(ref, sort_keys=True, ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            refs.append(ref)
    return refs


OFFICIAL_REPLACEMENT_SOURCE_TYPES = {"dungeon", "mythic_plus", "mythicplus", "raid", "tier_set"}


def active_catalog_sources_for_replacement(sources, season):
    sources = [source for source in sources or [] if isinstance(source, dict)]
    official_sources = [
        source
        for source in sources
        if raw_source_type(source.get("sourceType")).lower() in OFFICIAL_REPLACEMENT_SOURCE_TYPES
    ]
    if not official_sources:
        return sources
    active_official_sources = [
        source
        for source in official_sources
        if gear_source_active_for_replacement(source, season)
    ]
    if not active_official_sources:
        return []
    active_ids = {source.get("id") for source in active_official_sources if source.get("id")}
    return [
        source
        for source in sources
        if raw_source_type(source.get("sourceType")).lower() not in OFFICIAL_REPLACEMENT_SOURCE_TYPES
        or source.get("id") in active_ids
        or gear_source_active_for_replacement(source, season)
    ]


def enrich_catalog_item(item, sources, variants, socket_options, enchant_options, embellishment_options, class_key, spec_key):
    if not item:
        return None
    item_slot = item.get("slot") or ""
    compatible_sources = [source for source in sources if catalog_source_compatible(source, class_key, spec_key, item_slot)]
    compatible_variants = [
        variant
        for variant in variants
        if catalog_variant_compatible(variant, class_key, spec_key, item_slot)
        and catalog_variant_usable_for_replacement(variant)
    ]
    display_variants = collapse_catalog_variants_for_display(compatible_variants)
    base_capabilities = item.get("modCapabilities") if isinstance(item.get("modCapabilities"), dict) else {}
    variant_capabilities = item_mod_capabilities({}, item_slot, compatible_variants, item)
    mod_capabilities = {
        "hasSocket": bool(base_capabilities.get("hasSocket") or variant_capabilities.get("hasSocket")),
        "canEnchant": bool(base_capabilities.get("canEnchant") or variant_capabilities.get("canEnchant")),
        "canEmbellish": bool(base_capabilities.get("canEmbellish") or variant_capabilities.get("canEmbellish")),
    }
    item["sources"] = compatible_sources
    item["sourceRefs"] = compatible_sources
    item["variants"] = display_variants
    item["observedProfileRefs"] = observed_profile_refs_from_catalog(compatible_sources, compatible_variants)
    item["modCapabilities"] = mod_capabilities
    item["socketOptions"] = socket_options if mod_capabilities["hasSocket"] else []
    filtered_enchant_options = [
        option for option in enchant_options if gear_enchant_option_applies_to_item(option, item)
    ]
    item["enchantOptions"] = filtered_enchant_options if mod_capabilities["canEnchant"] else []
    filtered_embellishment_options = [
        option for option in embellishment_options if gear_embellishment_option_applies_to_item(option, item)
    ]
    item["embellishmentOptions"] = filtered_embellishment_options if mod_capabilities["canEmbellish"] else []
    item["recommendationScore"] = max([int(source.get("recommendationScore") or 0) for source in compatible_sources] + [0])
    item["compatibility"] = catalog_compatibility(item, sources, variants, class_key, spec_key)
    if item["compatibility"]["status"] == "incompatible":
        return None
    apply_default_catalog_variant(item, display_variants, variants)
    trust_blockers = catalog_item_trust_blockers(item)
    if trust_blockers:
        item["missingFields"] = unique_text_list([*(item.get("missingFields") or []), *trust_blockers])
        item["simcReady"] = False
    item["blockers"] = sorted(set([*(item.get("variantBlockers") or []), *(item.get("missingFields") or [])]))
    if catalog_item_should_hide_preview_stats(item):
        hide_candidate_current_variant_stats(item)
    return item


def gear_catalog_shared_cache_fingerprint(conn):
    ensure_websim_tables(conn)
    row = conn.execute(
        """
        SELECT
            (SELECT COUNT(*) || ':' || COALESCE(MAX(updated_at), '') FROM websim_gear_sources),
            (SELECT COUNT(*) || ':' || COALESCE(MAX(updated_at), '') FROM websim_gear_variants),
            (SELECT COUNT(*) || ':' || COALESCE(MAX(updated_at), '') FROM websim_gear_mod_options),
            (SELECT COUNT(*) || ':' || COALESCE(MAX(updated_at), '') FROM websim_items)
        """
    ).fetchone()
    return "|".join(str(value or "") for value in (row or ()))


def gear_catalog_base_item_from_row(row):
    item_id = str(row[0])
    payload = safe_json_loads(row[5], {})
    payload = payload if isinstance(payload, dict) else {}
    metadata = payload.get("_metadata") if isinstance(payload.get("_metadata"), dict) else {}
    item_stats = extract_item_stats_from_payload(payload)
    type_metadata = item_type_metadata_from_payload(payload)
    return {
        "id": item_id,
        "itemId": item_id,
        "name": row[1],
        "displayName": row[1],
        "englishName": metadata.get("englishName") or "",
        "slot": row[2],
        "quality": row[3],
        "iconUrl": row[4],
        "sourceType": "catalog",
        "metadataStatus": metadata.get("metadataStatus") or metadata.get("status") or "verified",
        "metadataSource": metadata.get("source") or ITEM_METADATA_SOURCE,
        "metadataLocale": metadata.get("locale") or DEFAULT_LOCALE,
        "itemStats": item_stats,
        "stats": item_stats,
        "statSummary": item_stat_summary(item_stats),
        "modCapabilities": item_mod_capabilities(payload, row[2]),
        **type_metadata,
        "payload": payload,
    }


def shared_gear_catalog_rows(conn):
    cache_key = (str(conn.execute("PRAGMA database_list").fetchone()[2]), gear_catalog_shared_cache_fingerprint(conn))
    with GEAR_CATALOG_SHARED_CACHE_LOCK:
        cached = GEAR_CATALOG_SHARED_CACHE.get(cache_key)
        if cached:
            return cached
        sources_by_item = gear_catalog_sources_by_item(conn)
        variants_by_item = gear_catalog_variants_by_item(conn)
        socket_options_by_slot = display_ready_gear_mod_options_by_slot(conn, "socket")
        enchant_options_by_slot = display_ready_gear_mod_options_by_slot(conn, "enchant")
        embellishment_options_by_slot = display_ready_gear_mod_options_by_slot(conn, "embellishment")
        item_ids = sorted(set(sources_by_item.keys()) | set(variants_by_item.keys()))
        items = []
        if item_ids:
            placeholders = ",".join("?" for _ in item_ids)
            rows = conn.execute(
                f"""
                SELECT id, name, slot, quality, icon_url, payload_json
                FROM websim_items
                WHERE id IN ({placeholders})
                ORDER BY name
                """,
                item_ids,
            ).fetchall()
            items = [gear_catalog_base_item_from_row(row) for row in rows]
        shared = {
            "sourcesByItem": sources_by_item,
            "variantsByItem": variants_by_item,
            "socketOptionsBySlot": socket_options_by_slot,
            "enchantOptionsBySlot": enchant_options_by_slot,
            "embellishmentOptionsBySlot": embellishment_options_by_slot,
            "items": items,
        }
        GEAR_CATALOG_SHARED_CACHE.clear()
        GEAR_CATALOG_SHARED_CACHE[cache_key] = shared
        return shared


def get_websim_gear_catalog_items(conn, class_key, spec_key, season=None):
    ensure_websim_tables(conn)
    season = season or get_active_season_payload(conn)
    shared_catalog = shared_gear_catalog_rows(conn)
    sources_by_item = shared_catalog["sourcesByItem"]
    variants_by_item = shared_catalog["variantsByItem"]
    socket_options_by_slot = shared_catalog["socketOptionsBySlot"]
    enchant_options_by_slot = shared_catalog["enchantOptionsBySlot"]
    embellishment_options_by_slot = shared_catalog["embellishmentOptionsBySlot"]
    if not shared_catalog["items"]:
        return []
    catalog_items = []
    for base_item in shared_catalog["items"]:
        item_id = str(base_item["itemId"])
        item_sources = active_catalog_sources_for_replacement(sources_by_item.get(item_id, []), season)
        item_variants = variants_by_item.get(item_id, [])
        if not item_sources:
            continue
        raw_item = dict(base_item)
        raw_item["source"] = (sources_by_item.get(item_id) or [{}])[0].get("label") or "gear catalog"
        item = normalize_gear_item(raw_item, class_key, spec_key, "catalog")
        if not item:
            continue
        item = enrich_catalog_item(
            item,
            item_sources,
            item_variants,
            socket_options_by_slot.get(item["slot"], []),
            enchant_options_by_slot.get(item["slot"], []),
            embellishment_options_by_slot.get(item["slot"], []),
            class_key,
            spec_key,
        )
        if item:
            catalog_items.append(item)
    return catalog_items


def gear_template_signature(template):
    class_key = slugify(template.get("classKey"), "mage")
    spec_key = slugify(template.get("specKey"), "arcane")
    by_slot = gear_items_by_slot(template.get("gearItems") or [], class_key, spec_key)
    parts = []
    for slot in CANONICAL_GEAR_SLOTS:
        item = by_slot.get(slot)
        if not item:
            continue
        parts.append({
            "slot": slot,
            "itemId": str(item.get("itemId") or item.get("id") or ""),
            "ilevel": str(item.get("ilevel") or item.get("itemLevel") or ""),
            "bonus_id": str(item.get("bonus_id") or ""),
            "gem_id": str(item.get("gem_id") or ""),
            "gem_bonus_id": str(item.get("gem_bonus_id") or ""),
            "gem_ilevel": str(item.get("gem_ilevel") or ""),
            "enchant_id": str(item.get("enchant_id") or ""),
            "crafted_stats": str(item.get("crafted_stats") or ""),
            "embellishment": str(item.get("embellishment") or ""),
        })
    return f"gear:{class_key}:{spec_key}:{stable_digest(parts)}"


def gear_template_source_ref(template):
    return {
        "id": str(template.get("id") or "").strip(),
        "sourceKey": str(template.get("sourceKey") or "").strip(),
        "sourceName": str(template.get("sourceName") or "").strip(),
        "sourceUrl": str(template.get("sourceUrl") or "").strip(),
        "sourceStatus": str(template.get("sourceStatus") or "").strip(),
        "status": str(template.get("status") or "").strip(),
        "sampleCount": int(template.get("sampleCount") or 0),
        "maxKeyLevel": int(template.get("maxKeyLevel") or 0),
        "updatedAt": str(template.get("updatedAt") or "").strip(),
        "analysisWindow": str(template.get("analysisWindow") or "").strip(),
    }


def gear_template_sort_key(template):
    return (
        1 if template.get("status") == "complete" else 0,
        1 if template.get("sourceStatus") in {"synced", "verified"} else 0,
        0 if template.get("sourceKey") == DEFAULT_GEAR_TEMPLATE_SOURCE_KEY else 1,
        int(template.get("readySlotCount") or 0),
        str(template.get("updatedAt") or ""),
        str(template.get("name") or ""),
    )


def dedupe_gear_community_templates(templates):
    prepared = []
    for template in templates or []:
        if not isinstance(template, dict):
            continue
        template = {**template}
        template["signature"] = template.get("signature") or gear_template_signature(template)
        template["sourceRefs"] = normalize_source_refs(template.get("sourceRefs") or [gear_template_source_ref(template)])
        prepared.append(template)
    return dedupe_templates_by_signature(prepared, gear_template_signature, gear_template_sort_key)


def sqlite_table_exists(conn, table_name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (str(table_name or ""),),
    ).fetchone()
    return bool(row)


def default_template_float_value(value):
    if value in ("", None):
        return None
    try:
        return float(str(value).strip().replace("%", ""))
    except (TypeError, ValueError):
        return None


DEFAULT_TEMPLATE_STAT_ALIASES = {
    "critical_strike": "crit",
    "criticalstrike": "crit",
    "crit_rating": "crit",
    "critical_strike_rating": "crit",
    "haste_rating": "haste",
    "mastery_rating": "mastery",
    "vers": "versatility",
    "versatility_rating": "versatility",
}


def default_template_stat_key(value):
    key = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")
    return DEFAULT_TEMPLATE_STAT_ALIASES.get(key, key)


def default_template_secondary_weight_scores(payload):
    weights = {}
    for row in (payload or {}).get("weights") or []:
        if not isinstance(row, dict):
            continue
        key = default_template_stat_key(row.get("key") or row.get("statKey") or row.get("name"))
        if key not in {"crit", "haste", "mastery", "versatility"}:
            continue
        score = default_template_float_value(row.get("percent"))
        if score is None:
            score = default_template_float_value(row.get("value") or row.get("score"))
        if score is None:
            continue
        weights[key] = score
    return weights


def read_default_template_stat_weight(conn, class_key, spec_key, scenario_key=DEFAULT_GEAR_TEMPLATE_SCENARIO_KEY):
    if not sqlite_table_exists(conn, "build_stat_weight_cache"):
        return None, {}, ["missing verified stat weight cache"]
    row = conn.execute(
        """
        SELECT value_json, status, updated_at, expires_at, stale_at
        FROM build_stat_weight_cache
        WHERE class_key = ? AND spec_key = ? AND scenario_key = ?
        """,
        (class_key, spec_key, scenario_key),
    ).fetchone()
    if not row:
        return None, {}, ["missing verified stat weight cache"]
    payload = safe_json_loads(row[0], {})
    payload = payload if isinstance(payload, dict) else {}
    payload.setdefault("sourceStatus", row[1])
    payload.setdefault("updatedAt", row[2])
    payload.setdefault("expiresAt", row[3])
    payload.setdefault("staleAt", row[4])
    status = str(payload.get("sourceStatus") or payload.get("status") or row[1] or "").strip().lower()
    if status != "verified":
        return payload, {}, [f"stat weight cache is not verified: {status or 'unknown'}"]
    weights = default_template_secondary_weight_scores(payload)
    missing = [key for key in ("crit", "haste", "mastery", "versatility") if key not in weights]
    if missing:
        return payload, weights, [f"stat weight cache missing secondary weights: {', '.join(missing)}"]
    return payload, weights, []


def default_template_item_stat_score(item, weights):
    score = 0.0
    for stat in (item or {}).get("itemStats") or (item or {}).get("stats") or []:
        if not isinstance(stat, dict):
            continue
        key = default_template_stat_key(stat.get("key") or stat.get("statKey") or stat.get("name") or stat.get("label"))
        if key not in weights:
            continue
        value = simc_numeric_stat_value(stat.get("value"))
        if value is None:
            value = positive_int_value(stat.get("value"))
        score += float(value or 0) * float(weights.get(key) or 0)
    return score


def default_template_source_reference_blocked(item):
    if not isinstance(item, dict):
        return True
    records = [item]
    for key in ("sources", "sourceRefs", "variants"):
        records.extend(row for row in item.get(key) or [] if isinstance(row, dict))
    for record in records:
        status = normalized_source_validation_status(record)
        if status in {"source_reference", "source_discrepancy"}:
            return True
        raw_status = str(record.get("status") or record.get("sourceStatus") or record.get("variantStatus") or "").strip().lower()
        if raw_status in {"source_reference", "source-reference"}:
            return True
    return False


def default_template_candidate_allowed(item):
    if not isinstance(item, dict):
        return False
    if not item.get("simcReady") or gear_candidate_incompatible(item):
        return False
    if not gear_candidate_visible_for_replacement(item):
        return False
    if default_template_source_reference_blocked(item):
        return False
    source_types = gear_candidate_source_types(item)
    if not (source_types & OFFICIAL_REPLACEMENT_SOURCE_TYPES):
        return False
    status = str(item.get("variantStatus") or "").strip().lower()
    if status != "verified":
        return False
    if not gear_candidate_has_verified_stats(item):
        return False
    return True


def default_template_source_quality_score(item):
    source_types = gear_candidate_source_types(item)
    if source_types & {"raid", "tier_set"}:
        return 4
    if source_types & {"dungeon", "mythic_plus", "mythicplus"}:
        return 3
    return 1


def default_template_candidate_score(item, slot, weights):
    item_level = positive_int_value(item.get("ilevel") or item.get("itemLevel"))
    guardrail_bucket = item_level // DEFAULT_GEAR_TEMPLATE_ILEVEL_GUARDRAIL
    base = (
        guardrail_bucket,
        item_level if slot in {"trinket1", "trinket2"} else default_template_item_stat_score(item, weights),
        default_template_source_quality_score(item),
        gear_candidate_quality_score(item),
    )
    return base


def default_template_unique_key(item):
    if not isinstance(item, dict):
        return ""
    if unique_equipped_bool(item.get("uniqueEquipped") or item.get("unique_equipped")):
        return str(item.get("uniqueGroup") or item.get("uniqueEquippedCategory") or item.get("itemId") or item.get("id") or "").strip()
    return ""


def default_template_unique_limit(item):
    limit = positive_int_value((item or {}).get("uniqueLimit") or (item or {}).get("unique_limit"))
    return limit or 1


def default_template_candidate_unique_allowed(item, unique_counts):
    key = default_template_unique_key(item)
    if not key:
        return True
    return int(unique_counts.get(key) or 0) < default_template_unique_limit(item)


def select_default_template_candidate(slot, candidates, weights, selected_item_ids, unique_counts):
    ordered = sorted(
        [item for item in candidates or [] if default_template_candidate_allowed(item)],
        key=lambda item: default_template_candidate_score(item, slot, weights),
        reverse=True,
    )
    for allow_duplicate in (False, True):
        for item in ordered:
            item_id = str(item.get("itemId") or item.get("id") or "").strip()
            if not allow_duplicate and item_id and item_id in selected_item_ids:
                continue
            if not default_template_candidate_unique_allowed(item, unique_counts):
                continue
            return item
    return None


def default_template_blocker(class_key, spec_key, reason, *, missing_slots=None):
    class_label = CLASS_LABELS_ZH.get(class_key, class_key)
    spec_label = SPEC_LABELS_ZH.get(spec_key, SPEC_LABELS.get(spec_key, spec_key))
    return {
        "classKey": class_key,
        "specKey": spec_key,
        "specId": f"{class_key}:{spec_key}",
        "className": class_label,
        "specName": spec_label,
        "reason": str(reason or "default template evidence missing"),
        "missingSlots": list(missing_slots or []),
        "path": "sync community templates -> default gear template builder",
    }


def default_template_top_blockers(blockers):
    grouped = {}
    for blocker in blockers or []:
        if not isinstance(blocker, dict):
            continue
        reason = str(blocker.get("reason") or "unknown").strip()
        entry = grouped.setdefault(reason, {"reason": reason, "count": 0, "specs": []})
        entry["count"] += 1
        spec_id = blocker.get("specId") or f"{blocker.get('classKey')}:{blocker.get('specKey')}"
        if spec_id and spec_id not in entry["specs"]:
            entry["specs"].append(spec_id)
    return sorted(grouped.values(), key=lambda item: (-item["count"], item["reason"]))[:8]


def default_gear_template_coverage_payload(total_specs, covered_specs, blockers, scan_run_id=""):
    blockers = [item for item in blockers or [] if isinstance(item, dict)]
    missing_specs = [item.get("specId") for item in blockers if item.get("specId")]
    return {
        "sourceKey": DEFAULT_GEAR_TEMPLATE_SOURCE_KEY,
        "sourceName": DEFAULT_GEAR_TEMPLATE_SOURCE_NAME,
        "templateRevision": COMMUNITY_TEMPLATE_REVISION,
        "scenarioKey": DEFAULT_GEAR_TEMPLATE_SCENARIO_KEY,
        "totalSpecCount": int(total_specs or 0),
        "coveredSpecCount": len(covered_specs or []),
        "missingSpecCount": len(missing_specs),
        "blockedSpecCount": len(blockers),
        "coveredSpecs": list(covered_specs or []),
        "missingSpecs": missing_specs,
        "blockedSpecs": missing_specs,
        "blockers": blockers[:80],
        "topBlockers": default_template_top_blockers(blockers),
        "lastSyncRun": scan_run_id,
        "checkedAt": utc_now(),
    }


def template_audit_expected_specs():
    specs = []
    for klass in WOW_CLASSES:
        class_key = str(klass.get("key") or "").strip()
        if not class_key:
            continue
        for raw_spec in klass.get("specs") or []:
            spec_key = str(raw_spec.get("key") if isinstance(raw_spec, dict) else raw_spec or "").strip()
            if not spec_key:
                continue
            specs.append(
                {
                    "classKey": class_key,
                    "specKey": spec_key,
                    "specId": f"{class_key}:{spec_key}",
                    "className": CLASS_LABELS_ZH.get(class_key, klass.get("label") or class_key),
                    "specName": SPEC_LABELS_ZH.get(spec_key, SPEC_LABELS.get(spec_key, spec_key)),
                }
            )
    return specs


def template_audit_gate(status, reason="", reason_category="", counts=None, **extra):
    gate = {
        "status": status,
        "reason": str(reason or ""),
        "reasonCategory": str(reason_category or ""),
    }
    if counts is not None:
        gate["counts"] = counts if isinstance(counts, dict) else {}
    for key, value in extra.items():
        if value is not None:
            gate[key] = value
    return gate


def template_audit_payload_blocker_text(payload):
    if not isinstance(payload, dict):
        return ""
    blockers = []
    if isinstance(payload.get("blockers"), list):
        blockers.extend(str(item or "") for item in payload.get("blockers") or [])
    validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
    if isinstance(validation.get("blockers"), list):
        blockers.extend(str(item or "") for item in validation.get("blockers") or [])
    return " ".join(blockers)


def template_audit_reason_category(reason, payload=None):
    text = " ".join([str(reason or ""), template_audit_payload_blocker_text(payload)]).lower()
    if "dungeon slice is disabled" in text or "enable_dungeon_slice" in text:
        return "simc_dungeon_slice_disabled"
    if "translation_blocked" in text or "strong_claim_blocked" in text:
        return "translation_guard"
    if "missing verified stat weight cache" in text:
        return "missing_stat_weight_cache"
    if "stat weight cache is not verified: partial" in text:
        return "stat_weight_partial"
    if "stat weight cache is not verified" in text:
        return "stat_weight_blocked"
    if "missing verified current-season simc-ready candidates" in text:
        return "missing_simc_ready_gear_candidates"
    if "serializer" in text:
        return "serializer_blocked"
    if "enhancement" in text or "weapon readiness" in text:
        return "enhancement_blocked"
    if "raider.io" in text and "sample" in text:
        return "raiderio_sample_gap"
    if "representative profile" in text or "simc-ready gear" in text:
        return "missing_representative_profile"
    if "missing table" in text or "no such table" in text:
        return "missing_cache_table"
    if "real community" in text:
        return "missing_real_community_gear_template"
    if "community talent" in text:
        return "missing_real_community_talent_template"
    return "unknown"


def template_audit_next_action(reason_category):
    return {
        "simc_dungeon_slice_disabled": "audit_enable_dungeon_slice",
        "missing_stat_weight_cache": "backfill_stat_weight_cache",
        "stat_weight_partial": "refresh_stat_weight_evidence",
        "stat_weight_blocked": "refresh_stat_weight_evidence",
        "translation_guard": "review_translation_guard",
        "missing_simc_ready_gear_candidates": "backfill_simc_ready_gear",
        "serializer_blocked": "fix_simc_serializer_precheck",
        "enhancement_blocked": "backfill_enhancement_options",
        "raiderio_sample_gap": "collect_raiderio_samples",
        "missing_representative_profile": "collect_simc_ready_representative_profiles",
        "missing_cache_table": "run_cache_schema_sync",
        "missing_real_community_gear_template": "collect_real_community_gear_samples",
        "missing_real_community_talent_template": "collect_real_community_talent_templates",
    }.get(reason_category or "", "review_evidence_blocker")


def template_audit_stat_counts(payload, weights):
    payload = payload if isinstance(payload, dict) else {}
    validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
    observed_weights = weights if weights else default_template_secondary_weight_scores(payload)
    return {
        "sampleCount": positive_int_value(validation.get("sampleCount") or payload.get("sampleCount")),
        "profileCount": positive_int_value(validation.get("profileCount") or payload.get("profileCount")),
        "simcSuccessCount": positive_int_value(validation.get("simcSuccessCount") or payload.get("simcSuccessCount")),
        "simcErrorCount": positive_int_value(validation.get("simcErrorCount")),
        "weightCount": len(observed_weights or []),
        "translationStatus": str(payload.get("translationStatus") or "").strip(),
        "sourceStatus": str(payload.get("sourceStatus") or payload.get("status") or "").strip(),
    }


def template_audit_stat_weight_gate(conn, spec):
    payload, weights, blockers = read_default_template_stat_weight(
        conn,
        spec["classKey"],
        spec["specKey"],
        DEFAULT_GEAR_TEMPLATE_SCENARIO_KEY,
    )
    counts = template_audit_stat_counts(payload, weights)
    if not blockers:
        return template_audit_gate(
            "passed",
            reason_category="",
            counts=counts,
            scenarioKey=DEFAULT_GEAR_TEMPLATE_SCENARIO_KEY,
            builderRequired=True,
        )
    reason = blockers[0]
    source_status = counts.get("sourceStatus")
    status = "partial" if source_status in {"partial", "stale"} else "blocked"
    category = template_audit_reason_category(reason, payload)
    return template_audit_gate(
        status,
        reason,
        category,
        counts=counts,
        scenarioKey=DEFAULT_GEAR_TEMPLATE_SCENARIO_KEY,
        builderRequired=True,
        nextAction=template_audit_next_action(category),
    )


def default_template_candidate_rejection_reasons(item):
    reasons = []
    if not isinstance(item, dict):
        return ["invalid_candidate"]
    if gear_candidate_incompatible(item):
        reasons.append("incompatible")
    if not item.get("simcReady"):
        reasons.append("not_simc_ready")
    if not gear_candidate_visible_for_replacement(item):
        reasons.append("not_visible")
    if default_template_source_reference_blocked(item):
        reasons.append("source_reference")
    if not (gear_candidate_source_types(item) & OFFICIAL_REPLACEMENT_SOURCE_TYPES):
        reasons.append("non_official_source")
    if str(item.get("variantStatus") or "").strip().lower() != "verified":
        reasons.append("variant_not_verified")
    if not gear_candidate_has_verified_stats(item):
        reasons.append("stats_not_verified")
    return reasons or ["unknown_rejection"]


def template_audit_top_counts(counts, limit=8):
    rows = [
        {"reasonCategory": str(key), "count": int(value or 0)}
        for key, value in (counts or {}).items()
        if int(value or 0) > 0
    ]
    return sorted(rows, key=lambda item: (-item["count"], item["reasonCategory"]))[:limit]


def default_template_candidate_diagnostic(conn, spec, catalog_items=None, season=None):
    if not sqlite_table_exists(conn, "websim_gear_variants"):
        return {
            "status": "diagnostic",
            "observedStatus": "blocked",
            "reason": "missing table: websim_gear_variants",
            "reasonCategory": "missing_cache_table",
            "totalSlotCount": len(CANONICAL_GEAR_SLOTS),
            "readySlotCount": 0,
            "missingSlots": list(CANONICAL_GEAR_SLOTS),
            "candidateCount": 0,
            "topReasons": [{"reasonCategory": "missing_cache_table", "count": 1}],
        }
    try:
        season = season or get_active_season_payload(conn)
        raw_items = catalog_items if catalog_items is not None else get_websim_gear_catalog_items(
            conn,
            spec["classKey"],
            spec["specKey"],
            season,
        )
    except (sqlite3.Error, ValueError) as error:
        reason = f"gear catalog diagnostic failed: {error}"
        return {
            "status": "diagnostic",
            "observedStatus": "blocked",
            "reason": reason,
            "reasonCategory": template_audit_reason_category(reason),
            "totalSlotCount": len(CANONICAL_GEAR_SLOTS),
            "readySlotCount": 0,
            "missingSlots": list(CANONICAL_GEAR_SLOTS),
            "candidateCount": 0,
            "topReasons": [{"reasonCategory": template_audit_reason_category(reason), "count": 1}],
        }
    prepared_items = apply_spec_primary_stat_display_to_items(
        [sanitize_gear_candidate_mod_options(item) for item in raw_items or [] if isinstance(item, dict)],
        spec["classKey"],
        spec["specKey"],
    )
    grouped = {slot: [] for slot in CANONICAL_GEAR_SLOTS}
    reason_counts = {}
    for item in prepared_items:
        for candidate_slot in gear_candidate_slots(item, item.get("classKey") or spec["classKey"], item.get("specKey") or spec["specKey"]):
            if candidate_slot not in grouped:
                continue
            candidate = gear_candidate_for_slot(item, candidate_slot)
            grouped[candidate_slot].append(candidate)
    slot_rows = []
    for slot in CANONICAL_GEAR_SLOTS:
        candidates = unique_gear_candidates(grouped.get(slot, []))
        allowed_count = 0
        for candidate in candidates:
            if default_template_candidate_allowed(candidate):
                allowed_count += 1
            else:
                for reason in default_template_candidate_rejection_reasons(candidate):
                    reason_counts[reason] = int(reason_counts.get(reason) or 0) + 1
        slot_rows.append(
            {
                "slot": slot,
                "candidateCount": len(candidates),
                "simcReadyCandidateCount": allowed_count,
                "status": "passed" if allowed_count else "blocked",
            }
        )
    missing_slots = [row["slot"] for row in slot_rows if row["status"] != "passed"]
    observed_status = "passed" if not missing_slots else "blocked"
    return {
        "status": "diagnostic",
        "observedStatus": observed_status,
        "reason": "" if observed_status == "passed" else "missing verified current-season SimC-ready candidates",
        "reasonCategory": "" if observed_status == "passed" else "missing_simc_ready_gear_candidates",
        "totalSlotCount": len(CANONICAL_GEAR_SLOTS),
        "readySlotCount": len(CANONICAL_GEAR_SLOTS) - len(missing_slots),
        "missingSlots": missing_slots,
        "candidateCount": sum(row["candidateCount"] for row in slot_rows),
        "topReasons": template_audit_top_counts(reason_counts),
        "slotMatrix": slot_rows,
    }


def template_audit_downstream_gate(previous_gate, gate_name, diagnostic=None):
    reason = f"{previous_gate} did not pass"
    gate = template_audit_gate("not_reached", reason, "not_reached", blockedBy=previous_gate)
    if diagnostic is not None:
        gate["diagnostic"] = diagnostic
    return gate


def default_template_evidence_audit_row(conn, spec, season=None):
    stat_gate = template_audit_stat_weight_gate(conn, spec)
    catalog_items = None
    if sqlite_table_exists(conn, "websim_gear_variants"):
        try:
            catalog_items = get_websim_gear_catalog_items(conn, spec["classKey"], spec["specKey"], season)
        except sqlite3.Error:
            catalog_items = None
    gear_diagnostic = default_template_candidate_diagnostic(conn, spec, catalog_items=catalog_items, season=season)
    gear_gate = template_audit_downstream_gate("statWeightGate", "gearCandidateGate", gear_diagnostic)
    enhancement_gate = template_audit_downstream_gate("gearCandidateGate", "enhancementGate")
    serializer_gate = template_audit_downstream_gate("enhancementGate", "serializerGate")
    first_blocking_gate = "statWeightGate"
    eligible = False
    next_action = stat_gate.get("nextAction") or template_audit_next_action(stat_gate.get("reasonCategory"))

    if stat_gate["status"] == "passed":
        if gear_diagnostic.get("observedStatus") != "passed":
            gear_gate = template_audit_gate(
                "blocked",
                gear_diagnostic.get("reason") or "missing verified current-season SimC-ready candidates",
                gear_diagnostic.get("reasonCategory") or "missing_simc_ready_gear_candidates",
                counts={
                    "readySlotCount": gear_diagnostic.get("readySlotCount") or 0,
                    "totalSlotCount": gear_diagnostic.get("totalSlotCount") or len(CANONICAL_GEAR_SLOTS),
                    "candidateCount": gear_diagnostic.get("candidateCount") or 0,
                },
                missingSlots=gear_diagnostic.get("missingSlots") or [],
                diagnostic=gear_diagnostic,
                nextAction="backfill_simc_ready_gear",
            )
            first_blocking_gate = "gearCandidateGate"
            next_action = "backfill_simc_ready_gear"
        else:
            template, blockers = build_default_community_gear_template(
                conn,
                spec["classKey"],
                spec["specKey"],
                catalog_items=catalog_items,
                season=season,
            )
            if template:
                gear_gate = template_audit_gate(
                    "passed",
                    counts={
                        "readySlotCount": gear_diagnostic.get("readySlotCount") or len(CANONICAL_GEAR_SLOTS),
                        "totalSlotCount": len(CANONICAL_GEAR_SLOTS),
                    },
                    diagnostic=gear_diagnostic,
                )
                enhancement_gate = template_audit_gate("passed", counts=template.get("enhancementReadiness") or {})
                serializer_gate = template_audit_gate(
                    "passed",
                    counts={"rawLineCount": len((template.get("rawString") or "").splitlines())},
                )
                first_blocking_gate = ""
                eligible = True
                next_action = ""
            else:
                blocker = blockers[0] if blockers else default_template_blocker(spec["classKey"], spec["specKey"], "default template blocked")
                reason = blocker.get("reason") or "default template blocked"
                category = template_audit_reason_category(reason)
                gate_name = "gearCandidateGate"
                if category == "enhancement_blocked":
                    gate_name = "enhancementGate"
                elif category == "serializer_blocked":
                    gate_name = "serializerGate"
                gear_gate = template_audit_gate("passed", diagnostic=gear_diagnostic)
                if gate_name == "gearCandidateGate":
                    gear_gate = template_audit_gate(
                        "blocked",
                        reason,
                        category,
                        missingSlots=blocker.get("missingSlots") or [],
                        diagnostic=gear_diagnostic,
                        nextAction=template_audit_next_action(category),
                    )
                elif gate_name == "enhancementGate":
                    enhancement_gate = template_audit_gate("blocked", reason, category, nextAction=template_audit_next_action(category))
                else:
                    enhancement_gate = template_audit_gate("passed")
                    serializer_gate = template_audit_gate("blocked", reason, category, nextAction=template_audit_next_action(category))
                first_blocking_gate = gate_name
                next_action = template_audit_next_action(category)

    return {
        **spec,
        "status": "passed" if eligible else ("partial" if stat_gate["status"] == "partial" else "blocked"),
        "eligible": eligible,
        "firstBlockingGate": first_blocking_gate,
        "statWeightGate": stat_gate,
        "gearCandidateGate": gear_gate,
        "enhancementGate": enhancement_gate,
        "serializerGate": serializer_gate,
        "nextAction": next_action,
    }


def template_audit_top_blockers(rows):
    grouped = {}
    for row in rows or []:
        if row.get("eligible") or row.get("status") == "passed":
            continue
        gate_name = row.get("firstBlockingGate") or "unknown"
        gate = row.get(gate_name) if isinstance(row.get(gate_name), dict) else {}
        category = gate.get("reasonCategory") or row.get("reasonCategory") or "unknown"
        key = f"{gate_name}:{category}"
        entry = grouped.setdefault(
            key,
            {
                "gate": gate_name,
                "reasonCategory": category,
                "count": 0,
                "specs": [],
                "nextAction": row.get("nextAction") or gate.get("nextAction") or template_audit_next_action(category),
            },
        )
        entry["count"] += 1
        if row.get("specId"):
            entry["specs"].append(row["specId"])
    return sorted(grouped.values(), key=lambda item: (-item["count"], item["gate"], item["reasonCategory"]))[:8]


def template_audit_section_summary(rows):
    total = len(rows or [])
    covered = sum(1 for row in rows or [] if row.get("eligible") or row.get("status") == "passed")
    partial = sum(1 for row in rows or [] if row.get("status") == "partial")
    blocked = total - covered
    return {
        "totalSpecCount": total,
        "coveredSpecCount": covered,
        "partialSpecCount": partial,
        "blockedSpecCount": blocked,
        "topBlockers": template_audit_top_blockers(rows),
    }


def default_gear_template_evidence_audit(conn, expected_specs):
    season = get_active_season_payload(conn)
    matrix = [default_template_evidence_audit_row(conn, spec, season=season) for spec in expected_specs]
    summary = template_audit_section_summary(matrix)
    summary["scenarioKey"] = DEFAULT_GEAR_TEMPLATE_SCENARIO_KEY
    stat_matrix = []
    for row in matrix:
        stat_gate = row.get("statWeightGate") or {}
        stat_matrix.append(
            {
                "specId": row.get("specId") or "",
                "status": stat_gate.get("status") or "",
                "reasonCategory": stat_gate.get("reasonCategory") or "",
                "counts": stat_gate.get("counts") or {},
                "nextAction": stat_gate.get("nextAction") or "",
            }
        )
    return {
        "sourceKey": DEFAULT_GEAR_TEMPLATE_SOURCE_KEY,
        "unlockScenarioKey": DEFAULT_GEAR_TEMPLATE_SCENARIO_KEY,
        "statusPolicy": "requires mplus_mixed_route verified stat weights; single and aoe scenarios are diagnostic only",
        "summary": summary,
        "statWeightBlockerMatrix": stat_matrix,
        "matrix": matrix,
    }


def real_community_gear_covered_specs_from_run(community_sync_run):
    gear = community_sync_run.get("gear") if isinstance(community_sync_run, dict) else {}
    gear = gear if isinstance(gear, dict) else {}
    summary = gear.get("realCommunityTemplates") if isinstance(gear.get("realCommunityTemplates"), dict) else {}
    covered = {str(item) for item in summary.get("coveredSpecs") or [] if str(item).strip()}
    missing = {str(item) for item in summary.get("missingSpecs") or [] if str(item).strip()}
    return covered, missing, bool(summary)


def real_community_gear_template_counts(conn):
    if not sqlite_table_exists(conn, "websim_community_gear_templates"):
        return {}
    rows = conn.execute(
        """
        SELECT class_key, spec_key, source_key, status, COUNT(*)
        FROM websim_community_gear_templates
        WHERE source_key != ? AND status IN ('complete', 'partial')
        GROUP BY class_key, spec_key, source_key, status
        """,
        (DEFAULT_GEAR_TEMPLATE_SOURCE_KEY,),
    ).fetchall()
    counts = {}
    for class_key, spec_key, source_key, status, count in rows:
        spec_id = f"{class_key}:{spec_key}"
        entry = counts.setdefault(spec_id, {"total": 0, "sources": {}, "statuses": {}})
        entry["total"] += int(count or 0)
        entry["sources"][source_key] = int(entry["sources"].get(source_key) or 0) + int(count or 0)
        entry["statuses"][status] = int(entry["statuses"].get(status) or 0) + int(count or 0)
    return counts


def real_community_gear_evidence_audit(conn, expected_specs, community_sync_run=None):
    covered_from_run, missing_from_run, has_run_summary = real_community_gear_covered_specs_from_run(community_sync_run or {})
    template_counts = real_community_gear_template_counts(conn)
    covered = covered_from_run if has_run_summary else set(template_counts.keys())
    matrix = []
    for spec in expected_specs:
        spec_id = spec["specId"]
        counts = template_counts.get(spec_id) or {}
        has_real = spec_id in covered and spec_id not in missing_from_run
        status = "passed" if has_real else "blocked"
        category = "" if has_real else "missing_real_community_gear_template"
        matrix.append(
            {
                **spec,
                "status": status,
                "firstBlockingGate": "" if has_real else "realCommunityGearSample",
                "reasonCategory": category,
                "templateCount": int(counts.get("total") or 0),
                "sourceCounts": counts.get("sources") or {},
                "statusCounts": counts.get("statuses") or {},
                "nextAction": "" if has_real else template_audit_next_action(category),
            }
        )
    summary = template_audit_section_summary(matrix)
    summary["missingSpecCount"] = summary["blockedSpecCount"]
    return {
        "countingPolicy": "real samples only; default_template is excluded and cannot fill this coverage",
        "summary": summary,
        "matrix": matrix,
    }


def community_talent_template_counts(conn):
    if not sqlite_table_exists(conn, "websim_community_talent_templates"):
        return {}
    rows = conn.execute(
        """
        SELECT class_key, spec_key, source_key, COUNT(*)
        FROM websim_community_talent_templates
        WHERE status = 'verified'
        GROUP BY class_key, spec_key, source_key
        """
    ).fetchall()
    counts = {}
    for class_key, spec_key, source_key, count in rows:
        spec_id = f"{class_key}:{spec_key}"
        entry = counts.setdefault(spec_id, {"real": 0, "fallback": 0, "sources": {}})
        if source_key == "websim_baseline":
            entry["fallback"] += int(count or 0)
        else:
            entry["real"] += int(count or 0)
        entry["sources"][source_key] = int(entry["sources"].get(source_key) or 0) + int(count or 0)
    return counts


def community_talent_evidence_audit(conn, expected_specs):
    counts_by_spec = community_talent_template_counts(conn)
    matrix = []
    real_covered = 0
    fallback_covered = 0
    fallback_only = 0
    for spec in expected_specs:
        counts = counts_by_spec.get(spec["specId"]) or {"real": 0, "fallback": 0, "sources": {}}
        real_count = int(counts.get("real") or 0)
        fallback_count = int(counts.get("fallback") or 0)
        if real_count:
            status = "passed"
            first_blocking_gate = ""
            category = ""
            next_action = ""
            real_covered += 1
        elif fallback_count:
            status = "partial"
            first_blocking_gate = "realCommunityTalent"
            category = "missing_real_community_talent_template"
            next_action = template_audit_next_action(category)
            fallback_only += 1
        else:
            status = "blocked"
            first_blocking_gate = "communityTalentTemplate"
            category = "missing_real_community_talent_template"
            next_action = template_audit_next_action(category)
        if fallback_count:
            fallback_covered += 1
        matrix.append(
            {
                **spec,
                "status": status,
                "realStatus": "passed" if real_count else "blocked",
                "fallbackStatus": "passed" if fallback_count else "blocked",
                "realTemplateCount": real_count,
                "fallbackTemplateCount": fallback_count,
                "sourceCounts": counts.get("sources") or {},
                "firstBlockingGate": first_blocking_gate,
                "reasonCategory": category,
                "nextAction": next_action,
            }
        )
    summary = template_audit_section_summary(matrix)
    summary.update(
        {
            "realCoveredSpecCount": real_covered,
            "fallbackCoveredSpecCount": fallback_covered,
            "fallbackOnlySpecCount": fallback_only,
            "usableSpecCount": len([row for row in matrix if row["realTemplateCount"] or row["fallbackTemplateCount"]]),
            "countingPolicy": "real community talent coverage is counted separately from websim_baseline fallback",
        }
    )
    return {
        "fallbackSourceKey": "websim_baseline",
        "countingPolicy": "fallback templates do not fill real community template coverage",
        "summary": summary,
        "matrix": matrix,
    }


def template_audit_source_dependencies(community_state):
    sources = community_state.get("sources") if isinstance(community_state, dict) else {}
    wcl = sources.get("warcraftlogs") if isinstance(sources, dict) else {}
    if not isinstance(wcl, dict):
        wcl = {}
    return {
        "warcraftlogs": {
            "status": wcl.get("status") or "missing_credentials",
            "sourceName": wcl.get("sourceName") or "Warcraft Logs",
            "countingPolicy": "independent source dependency; not duplicated as 40 per-spec blockers",
            "errorCount": len(wcl.get("errors") or []) if isinstance(wcl.get("errors"), list) else 0,
        }
    }


def template_evidence_audit_payload(conn, community_state=None, community_sync_run=None):
    expected_specs = template_audit_expected_specs()
    community_state = community_state if isinstance(community_state, dict) else community_talent_sync_state(conn)
    community_sync_run = community_sync_run if isinstance(community_sync_run, dict) else get_sync_state(conn, COMMUNITY_TEMPLATE_SYNC_RUN_KEY) or {}
    default_gear = default_gear_template_evidence_audit(conn, expected_specs)
    real_gear = real_community_gear_evidence_audit(conn, expected_specs, community_sync_run=community_sync_run)
    community_talent = community_talent_evidence_audit(conn, expected_specs)
    return {
        "schemaRevision": TEMPLATE_EVIDENCE_AUDIT_REVISION,
        "checkedAt": utc_now(),
        "status": "diagnostic",
        "summary": {
            "totalSpecCount": len(expected_specs),
            "defaultGearCoveredSpecCount": default_gear["summary"]["coveredSpecCount"],
            "realCommunityGearCoveredSpecCount": real_gear["summary"]["coveredSpecCount"],
            "realCommunityTalentCoveredSpecCount": community_talent["summary"]["realCoveredSpecCount"],
            "fallbackTalentCoveredSpecCount": community_talent["summary"]["fallbackCoveredSpecCount"],
            "topBlockers": default_gear["summary"]["topBlockers"][:4]
            + real_gear["summary"]["topBlockers"][:2]
            + community_talent["summary"]["topBlockers"][:2],
        },
        "defaultGear": default_gear,
        "realCommunityGear": real_gear,
        "communityTalent": community_talent,
        "sourceDependencies": template_audit_source_dependencies(community_state),
    }


def default_template_non_dps_warning(class_key, spec_key):
    if (
        (class_key, spec_key)
        in {
            ("deathknight", "blood"),
            ("demonhunter", "vengeance"),
            ("druid", "guardian"),
            ("monk", "brewmaster"),
            ("paladin", "protection"),
            ("warrior", "protection"),
            ("druid", "restoration"),
            ("evoker", "preservation"),
            ("monk", "mistweaver"),
            ("paladin", "holy"),
            ("priest", "discipline"),
            ("priest", "holy"),
            ("shaman", "restoration"),
            ("evoker", "augmentation"),
        }
    ):
        return "non-pure DPS specs use M+ mixed-route secondary weights; not a survivability, healing, or group-benefit optimum"
    return ""


def build_default_community_gear_template(conn, class_key, spec_key, catalog_items=None, season=None):
    stat_weight, weights, stat_blockers = read_default_template_stat_weight(conn, class_key, spec_key)
    if stat_blockers:
        return None, [default_template_blocker(class_key, spec_key, stat_blockers[0])]

    season = season or get_active_season_payload(conn)
    catalog_items = catalog_items if catalog_items is not None else get_websim_gear_catalog_items(conn, class_key, spec_key, season)
    prepared_items = apply_spec_primary_stat_display_to_items(
        [sanitize_gear_candidate_mod_options(item) for item in catalog_items or []],
        class_key,
        spec_key,
    )
    grouped = {slot: [] for slot in CANONICAL_GEAR_SLOTS}
    for item in prepared_items:
        if not isinstance(item, dict) or gear_candidate_incompatible(item):
            continue
        for candidate_slot in gear_candidate_slots(item, item.get("classKey") or class_key, item.get("specKey") or spec_key):
            if candidate_slot in grouped:
                grouped[candidate_slot].append(gear_candidate_for_slot(item, candidate_slot))

    selected = []
    selected_item_ids = set()
    unique_counts = {}
    missing_slots = []
    for slot in CANONICAL_GEAR_SLOTS:
        candidate = select_default_template_candidate(slot, unique_gear_candidates(grouped.get(slot, [])), weights, selected_item_ids, unique_counts)
        if not candidate:
            missing_slots.append(slot)
            continue
        item_id = str(candidate.get("itemId") or candidate.get("id") or "").strip()
        if item_id:
            selected_item_ids.add(item_id)
        unique_key = default_template_unique_key(candidate)
        if unique_key:
            unique_counts[unique_key] = int(unique_counts.get(unique_key) or 0) + 1
        selected.append(candidate)

    if missing_slots:
        reason = f"missing verified current-season SimC-ready candidates for slots: {', '.join(missing_slots)}"
        return None, [default_template_blocker(class_key, spec_key, reason, missing_slots=missing_slots)]

    enhanced_items, enhancement_readiness = merge_websim_gear_enhancements(selected, {}, conn, class_key, spec_key)
    enhancement_readiness = dict(enhancement_readiness or {})
    enhancement_readiness["status"] = "blocked" if enhancement_readiness.get("blockers") else "partial"
    enhancement_readiness["scope"] = "optional_enhancements"
    ready_by_slot = gear_items_by_slot(enhanced_items, class_key, spec_key)
    enhanced_items = [ready_by_slot[slot] for slot in CANONICAL_GEAR_SLOTS if slot in ready_by_slot]
    missing_after_enhancement = [slot for slot in CANONICAL_GEAR_SLOTS if slot not in ready_by_slot]
    if missing_after_enhancement:
        reason = f"serializer precheck removed slots after enhancement merge: {', '.join(missing_after_enhancement)}"
        return None, [default_template_blocker(class_key, spec_key, reason, missing_slots=missing_after_enhancement)]
    if enhancement_readiness.get("blockers"):
        return None, [
            default_template_blocker(
                class_key,
                spec_key,
                f"enhancement/weapon readiness blocked default template: {enhancement_readiness['blockers'][0]}",
            )
        ]
    raw_lines = build_websim_gear_lines(enhanced_items)
    if len(raw_lines) != len(CANONICAL_GEAR_SLOTS):
        missing_line_slots = [
            slot
            for slot, item in ready_by_slot.items()
            if slot in CANONICAL_GEAR_SLOTS and not item.get("simcReady")
        ]
        reason = "serializer failed to produce 16 SimC-ready gear lines"
        return None, [default_template_blocker(class_key, spec_key, reason, missing_slots=missing_line_slots)]

    warnings = [DEFAULT_GEAR_TEMPLATE_TRINKET_WARNING]
    non_dps_warning = default_template_non_dps_warning(class_key, spec_key)
    if non_dps_warning:
        warnings.append(non_dps_warning)
    catalog_state = gear_catalog_sync_state(conn)
    evidence = {
        "sourceKey": DEFAULT_GEAR_TEMPLATE_SOURCE_KEY,
        "sourceName": DEFAULT_GEAR_TEMPLATE_SOURCE_NAME,
        "scenarioKey": DEFAULT_GEAR_TEMPLATE_SCENARIO_KEY,
        "statWeightRevision": stat_weight.get("schemaRevision") or "",
        "statWeightStatus": stat_weight.get("sourceStatus") or stat_weight.get("status") or "",
        "statWeightCheckedAt": stat_weight.get("checkedAt") or stat_weight.get("updatedAt") or "",
        "gearCatalogRevision": catalog_state.get("schemaRevision") or GEAR_CATALOG_REVISION,
        "gearCatalogStatus": catalog_state.get("status") or "",
        "selectionPolicy": "verified current-season SimC-ready candidates; item-level guardrail plus secondary stat weights",
        "warnings": warnings,
    }
    payload = {
        "scenarioKey": DEFAULT_GEAR_TEMPLATE_SCENARIO_KEY,
        "enhancementReadiness": enhancement_readiness,
        "templateEvidence": evidence,
    }
    class_label = CLASS_LABELS_ZH.get(class_key, class_key)
    spec_label = SPEC_LABELS_ZH.get(spec_key, SPEC_LABELS.get(spec_key, spec_key))
    template = {
        "id": f"default-template-{class_key}-{spec_key}-{DEFAULT_GEAR_TEMPLATE_SCENARIO_KEY}",
        "name": f"{DEFAULT_GEAR_TEMPLATE_SOURCE_NAME} · {class_label}{spec_label}",
        "classKey": class_key,
        "specKey": spec_key,
        "classLabel": class_label,
        "specLabel": spec_label,
        "sourceKey": DEFAULT_GEAR_TEMPLATE_SOURCE_KEY,
        "sourceName": DEFAULT_GEAR_TEMPLATE_SOURCE_NAME,
        "sourceUrl": "",
        "sourceStatus": "verified",
        "status": "complete",
        "updatedAt": utc_now(),
        "analysisWindow": "默认模板由 verified 当前赛季装备候选和 M+ mixed-route 绿字权重生成；不代表真实社区样本或 BiS。",
        "gearItems": enhanced_items,
        "rawString": "\n".join(raw_lines),
        "readySlotCount": len(enhanced_items),
        "missingSlots": [],
        "canApplyGear": True,
        "scenarioKey": DEFAULT_GEAR_TEMPLATE_SCENARIO_KEY,
        "enhancementReadiness": enhancement_readiness,
        "templateEvidence": evidence,
        "payload": payload,
    }
    template["signature"] = gear_template_signature(template)
    template["sourceRefs"] = normalize_source_refs([gear_template_source_ref(template)])
    template["templateRevision"] = COMMUNITY_TEMPLATE_REVISION
    return template, []


def gear_community_template_from_preset(preset, class_key, spec_key):
    if not isinstance(preset, dict):
        return None
    ready_by_slot = gear_items_by_slot(
        [item for item in preset_gear_items(preset) if item.get("simcReady")],
        class_key,
        spec_key,
    )
    gear_items = [ready_by_slot[slot] for slot in CANONICAL_GEAR_SLOTS if slot in ready_by_slot]
    if not gear_items:
        return None
    raw_lines = build_websim_gear_lines(gear_items)
    if not raw_lines:
        return None
    missing_slots = [slot for slot in CANONICAL_GEAR_SLOTS if slot not in ready_by_slot]
    status = "complete" if not missing_slots else "partial"
    source_status = "synced" if status == "complete" else "partial"
    ready_count = len(gear_items)
    template = {
        "id": str(preset.get("id") or f"preset-{class_key}-{spec_key}"),
        "name": str(preset.get("name") or "SimC preset"),
        "classKey": class_key,
        "specKey": spec_key,
        "sourceKey": "simc_preset",
        "sourceName": "SimC preset",
        "sourceUrl": "",
        "sourceStatus": source_status,
        "status": status,
        "updatedAt": str(preset.get("updatedAt") or ""),
        "analysisWindow": f"SimC preset profile; {ready_count}/{len(CANONICAL_GEAR_SLOTS)} canonical gear slots ready.",
        "gearItems": gear_items,
        "rawString": "\n".join(raw_lines),
        "readySlotCount": ready_count,
        "missingSlots": missing_slots,
        "canApplyGear": bool(gear_items),
    }
    template["signature"] = gear_template_signature(template)
    template["sourceRefs"] = normalize_source_refs([gear_template_source_ref(template)])
    template["templateRevision"] = COMMUNITY_TEMPLATE_REVISION
    return template


def observed_item_matches_spec(item, class_key, spec_key):
    if not isinstance(item, dict):
        return False
    for ref in item.get("observedProfileRefs") or []:
        if not isinstance(ref, dict):
            continue
        if slugify(ref.get("classKey"), "") == class_key and slugify(ref.get("specKey"), "") == spec_key:
            return True
    return False


def observed_profile_baseline_items(catalog_items, class_key, spec_key):
    by_slot = {}
    for item in catalog_items or []:
        if not isinstance(item, dict) or not item.get("simcReady"):
            continue
        if item.get("variantSource") != "observed_profile":
            continue
        if not observed_item_matches_spec(item, class_key, spec_key):
            continue
        slot = item.get("slot")
        if slot in CANONICAL_GEAR_SLOTS and slot not in by_slot:
            by_slot[slot] = {
                **item,
                "sourceType": "observed_profile",
                "source": item.get("source") or "Raider.IO observed gear",
            }
    return [by_slot[slot] for slot in CANONICAL_GEAR_SLOTS if slot in by_slot]


def gear_community_template_from_observed_items(items, class_key, spec_key):
    ready_by_slot = gear_items_by_slot(
        [item for item in items or [] if isinstance(item, dict) and item.get("simcReady")],
        class_key,
        spec_key,
    )
    gear_items = [ready_by_slot[slot] for slot in CANONICAL_GEAR_SLOTS if slot in ready_by_slot]
    if not gear_items:
        return None
    raw_lines = build_websim_gear_lines(gear_items)
    if not raw_lines:
        return None
    missing_slots = [slot for slot in CANONICAL_GEAR_SLOTS if slot not in ready_by_slot]
    status = "complete" if not missing_slots else "partial"
    source_status = "synced" if status == "complete" else "partial"
    ready_count = len(gear_items)
    class_label = CLASS_LABELS_ZH.get(class_key, class_key)
    spec_label = SPEC_LABELS_ZH.get(spec_key, SPEC_LABELS.get(spec_key, spec_key.replace("_", " ").title()))
    template = {
        "id": f"observed-profile-{class_key}-{spec_key}",
        "name": f"Raider.IO 观测装备 · {class_label}{spec_label}",
        "classKey": class_key,
        "specKey": spec_key,
        "sourceKey": "raiderio_observed_profile",
        "sourceName": "Raider.IO observed gear",
        "sourceUrl": "",
        "sourceStatus": source_status,
        "status": status,
        "updatedAt": utc_now(),
        "analysisWindow": f"Raider.IO observed profile gear; {ready_count}/{len(CANONICAL_GEAR_SLOTS)} canonical gear slots ready.",
        "gearItems": gear_items,
        "rawString": "\n".join(raw_lines),
        "readySlotCount": ready_count,
        "missingSlots": missing_slots,
        "canApplyGear": bool(gear_items),
    }
    template["signature"] = gear_template_signature(template)
    template["sourceRefs"] = normalize_source_refs([gear_template_source_ref(template)])
    template["templateRevision"] = COMMUNITY_TEMPLATE_REVISION
    return template


def complete_baseline_with_candidate_slots(baseline_items, candidates_by_slot):
    completed = [item for item in baseline_items or [] if isinstance(item, dict)]
    occupied_slots = {
        item.get("slot")
        for item in completed
        if item.get("slot") in CANONICAL_GEAR_SLOTS
    }
    for slot in CORE_SIMC_GEAR_SLOTS:
        if slot in occupied_slots:
            continue
        for candidate in candidates_by_slot.get(slot) or []:
            if not isinstance(candidate, dict):
                continue
            if not candidate.get("simcReady") or gear_candidate_incompatible(candidate):
                continue
            completed.append({**candidate, "baselineFallback": True})
            occupied_slots.add(slot)
            break
    return completed


def websim_gear_community_templates(presets, class_key, spec_key):
    templates = []
    for preset in presets or []:
        template = gear_community_template_from_preset(preset, class_key, spec_key)
        if template:
            templates.append(template)
    return sorted(
        dedupe_gear_community_templates(templates),
        key=lambda item: (
            0 if item.get("status") == "complete" else 1,
            -int(item.get("readySlotCount") or 0),
            item.get("name") or "",
        ),
    )


def websim_gear_community_template_sync_state(templates):
    templates = templates or []
    hidden_duplicate_count = sum(max(0, int(item.get("dedupedCount") or 1) - 1) for item in templates)
    signatures = [item.get("signature") for item in templates if item.get("signature")]
    complete_count = len([item for item in templates if item.get("status") == "complete"])
    partial_count = len([item for item in templates if item.get("status") == "partial"])
    if not templates:
        source_status = "blocked"
    elif partial_count:
        source_status = "partial"
    else:
        source_status = "synced"
    simc_templates = [item for item in templates if item.get("sourceName") == "SimC preset"]
    observed_templates = [item for item in templates if item.get("sourceName") == "Raider.IO observed gear"]
    default_templates = [item for item in templates if item.get("sourceKey") == DEFAULT_GEAR_TEMPLATE_SOURCE_KEY]
    sources = {}
    if simc_templates:
        sources["simc_presets"] = {
            "status": "partial" if any(item.get("status") == "partial" for item in simc_templates) else "synced",
            "sourceName": "SimC preset",
            "errors": [],
        }
    if observed_templates:
        sources["observed_profile"] = {
            "status": "partial" if any(item.get("status") == "partial" for item in observed_templates) else "synced",
            "sourceName": "Raider.IO observed gear",
            "errors": [],
        }
    if default_templates:
        sources[DEFAULT_GEAR_TEMPLATE_SOURCE_KEY] = {
            "status": "partial" if any(item.get("status") == "partial" for item in default_templates) else "verified",
            "sourceName": DEFAULT_GEAR_TEMPLATE_SOURCE_NAME,
            "errors": [],
        }
    if not sources:
        sources["simc_presets"] = {
            "status": source_status,
            "sourceName": "SimC preset",
            "errors": ["no importable SimC gear presets"],
        }
    return {
        "sourceStatus": source_status,
        "sources": sources,
        "templateRevision": community_template_revision_from_signatures(signatures),
        "dedupedCount": len(templates),
        "hiddenDuplicateCount": hidden_duplicate_count,
        "templates": {
            "total": len(templates),
            "rawTotal": len(templates) + hidden_duplicate_count,
            "verified": complete_count,
            "partial": partial_count,
            "blocked": 0,
        },
        "checkedAt": utc_now() if templates else "",
    }


def normalize_community_gear_template(template, class_key="", spec_key=""):
    source = template if isinstance(template, dict) else {}
    class_key = slugify(source.get("classKey") or class_key, "mage")
    spec_key = slugify(source.get("specKey") or spec_key, "arcane")
    payload = source.get("payload") if isinstance(source.get("payload"), dict) else {}
    scenario_key = str(source.get("scenarioKey") or payload.get("scenarioKey") or "").strip()
    enhancement_readiness = source.get("enhancementReadiness") if isinstance(source.get("enhancementReadiness"), dict) else payload.get("enhancementReadiness")
    enhancement_readiness = enhancement_readiness if isinstance(enhancement_readiness, dict) else {}
    template_evidence = source.get("templateEvidence") if isinstance(source.get("templateEvidence"), dict) else payload.get("templateEvidence")
    template_evidence = template_evidence if isinstance(template_evidence, dict) else {}
    if scenario_key or enhancement_readiness or template_evidence:
        payload = dict(payload)
        if scenario_key:
            payload["scenarioKey"] = scenario_key
        if enhancement_readiness:
            payload["enhancementReadiness"] = enhancement_readiness
        if template_evidence:
            payload["templateEvidence"] = template_evidence
    gear_items = normalize_websim_gear_items(source.get("gearItems") or [], class_key, spec_key)
    if not gear_items and source.get("rawString"):
        gear_items = [
            item
            for item in (
                parse_simc_gear_line(line, class_key, spec_key, source.get("sourceName") or "", source.get("id") or "")
                for line in str(source.get("rawString") or "").splitlines()
            )
            if item
        ]
    ready_by_slot = gear_items_by_slot(gear_items, class_key, spec_key)
    gear_items = [ready_by_slot[slot] for slot in CANONICAL_GEAR_SLOTS if slot in ready_by_slot]
    raw_lines = build_websim_gear_lines(gear_items)
    missing_slots = [slot for slot in CANONICAL_GEAR_SLOTS if slot not in ready_by_slot]
    status = str(source.get("status") or ("complete" if not missing_slots and gear_items else "partial")).strip()
    if status == "complete" and missing_slots:
        status = "partial"
    source_status = str(source.get("sourceStatus") or ("synced" if status == "complete" else "partial")).strip()
    normalized = {
        "id": slugify(source.get("id"), f"gear-{class_key}-{spec_key}-{stable_digest(raw_lines)}"),
        "name": str(source.get("name") or "Community gear template").strip(),
        "classKey": class_key,
        "specKey": spec_key,
        "sourceKey": str(source.get("sourceKey") or "community_gear").strip(),
        "sourceName": str(source.get("sourceName") or "Community gear").strip(),
        "sourceUrl": str(source.get("sourceUrl") or "").strip(),
        "sourceStatus": source_status,
        "status": status,
        "updatedAt": str(source.get("updatedAt") or utc_now()).strip(),
        "expiresAt": str(source.get("expiresAt") or season_expires_at()).strip(),
        "analysisWindow": str(source.get("analysisWindow") or "").strip(),
        "gearItems": gear_items,
        "rawString": str(source.get("rawString") or "\n".join(raw_lines)).strip(),
        "readySlotCount": len(gear_items),
        "missingSlots": missing_slots,
        "canApplyGear": bool(gear_items),
        "payload": payload,
        "scanRunId": str(source.get("scanRunId") or source.get("scan_run_id") or "").strip(),
    }
    if scenario_key:
        normalized["scenarioKey"] = scenario_key
    if enhancement_readiness:
        normalized["enhancementReadiness"] = enhancement_readiness
    if template_evidence:
        normalized["templateEvidence"] = template_evidence
    normalized["signature"] = str(source.get("signature") or gear_template_signature(normalized)).strip()
    normalized["sourceRefs"] = normalize_source_refs(source.get("sourceRefs") or [gear_template_source_ref(normalized)])
    normalized["templateRevision"] = COMMUNITY_TEMPLATE_REVISION
    return normalized


def upsert_community_gear_template(conn, template):
    ensure_websim_tables(conn)
    normalized = normalize_community_gear_template(template)
    conn.execute(
        """
        INSERT INTO websim_community_gear_templates (
            id, class_key, spec_key, name, source_key, source_name, source_url,
            source_status, status, signature, source_refs_json, gear_items_json,
            raw_string, ready_slot_count, missing_slots_json, analysis_window,
            payload_json, updated_at, expires_at, scan_run_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            class_key=excluded.class_key,
            spec_key=excluded.spec_key,
            name=excluded.name,
            source_key=excluded.source_key,
            source_name=excluded.source_name,
            source_url=excluded.source_url,
            source_status=excluded.source_status,
            status=excluded.status,
            signature=excluded.signature,
            source_refs_json=excluded.source_refs_json,
            gear_items_json=excluded.gear_items_json,
            raw_string=excluded.raw_string,
            ready_slot_count=excluded.ready_slot_count,
            missing_slots_json=excluded.missing_slots_json,
            analysis_window=excluded.analysis_window,
            payload_json=excluded.payload_json,
            updated_at=excluded.updated_at,
            expires_at=excluded.expires_at,
            scan_run_id=excluded.scan_run_id
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
            json.dumps(normalized["sourceRefs"], ensure_ascii=False),
            json.dumps(normalized["gearItems"], ensure_ascii=False),
            normalized["rawString"],
            normalized["readySlotCount"],
            json.dumps(normalized["missingSlots"], ensure_ascii=False),
            normalized["analysisWindow"],
            json.dumps(normalized["payload"], ensure_ascii=False),
            normalized["updatedAt"],
            normalized["expiresAt"],
            normalized["scanRunId"],
        ),
    )
    return normalized


def get_persisted_community_gear_templates(conn, class_key, spec_key):
    ensure_websim_tables(conn)
    rows = conn.execute(
        """
        SELECT id, class_key, spec_key, name, source_key, source_name, source_url,
               source_status, status, signature, source_refs_json, gear_items_json,
               raw_string, ready_slot_count, missing_slots_json, analysis_window,
               payload_json, updated_at, expires_at, scan_run_id
        FROM websim_community_gear_templates
        WHERE class_key = ? AND spec_key = ? AND status IN ('complete', 'partial')
        ORDER BY status, ready_slot_count DESC, updated_at DESC, name
        LIMIT 80
        """,
        (slugify(class_key, "mage"), slugify(spec_key, "arcane")),
    ).fetchall()
    templates = []
    for row in rows:
        payload = safe_json_loads(row[16], {}) or {}
        templates.append({
            "id": row[0],
            "classKey": row[1],
            "specKey": row[2],
            "name": row[3],
            "sourceKey": row[4],
            "sourceName": row[5],
            "sourceUrl": row[6],
            "sourceStatus": row[7],
            "status": row[8],
            "signature": row[9],
            "sourceRefs": normalize_source_refs(safe_json_loads(row[10], []) or []),
            "gearItems": safe_json_loads(row[11], []) or [],
            "rawString": row[12],
            "readySlotCount": int(row[13] or 0),
            "missingSlots": safe_json_loads(row[14], []) or [],
            "analysisWindow": row[15],
            "payload": payload,
            "scenarioKey": payload.get("scenarioKey") or "",
            "enhancementReadiness": payload.get("enhancementReadiness") if isinstance(payload.get("enhancementReadiness"), dict) else {},
            "templateEvidence": payload.get("templateEvidence") if isinstance(payload.get("templateEvidence"), dict) else {},
            "updatedAt": row[17],
            "expiresAt": row[18],
            "scanRunId": row[19],
            "canApplyGear": bool(row[12]),
            "templateRevision": COMMUNITY_TEMPLATE_REVISION,
        })
    return dedupe_gear_community_templates(templates)


def sync_community_gear_templates(conn, scan_run_id=""):
    ensure_websim_tables(conn)
    total = 0
    complete = 0
    partial = 0
    blocked = 0
    total_specs = 0
    real_covered_specs = []
    real_missing_specs = []
    default_covered_specs = []
    default_blockers = []
    signatures = set()
    season = get_active_season_payload(conn)
    for klass in WOW_CLASSES:
        class_key = klass["key"]
        for spec in klass.get("specs") or []:
            total_specs += 1
            spec_key = spec.get("key") if isinstance(spec, dict) else spec
            rows = conn.execute(
                """
        SELECT id, class_key, spec_key, name, profile, payload_json, updated_at
                FROM websim_profile_presets
                WHERE class_key = ? AND spec_key = ?
                ORDER BY name
                LIMIT 12
                """,
                (class_key, spec_key),
            ).fetchall()
            presets = [
                {
                    "id": row[0],
                    "classKey": row[1],
                    "specKey": row[2],
            "name": row[3],
            "profile": row[4],
            "payload": safe_json_loads(row[5], {}),
            "updatedAt": row[6],
        }
                for row in rows
            ]
            templates = websim_gear_community_templates(presets, class_key, spec_key)
            catalog_items = get_websim_gear_catalog_items(conn, class_key, spec_key, season)
            observed_template = gear_community_template_from_observed_items(
                observed_profile_baseline_items(catalog_items, class_key, spec_key),
                class_key,
                spec_key,
            )
            if observed_template:
                templates.append(observed_template)
            real_templates = dedupe_gear_community_templates(templates)
            if real_templates:
                real_covered_specs.append(f"{class_key}:{spec_key}")
            else:
                real_missing_specs.append(f"{class_key}:{spec_key}")
            default_template, template_blockers = build_default_community_gear_template(
                conn,
                class_key,
                spec_key,
                catalog_items=catalog_items,
                season=season,
            )
            if default_template:
                templates.append(default_template)
                default_covered_specs.append(f"{class_key}:{spec_key}")
            else:
                default_blockers.extend(template_blockers)
            for template in dedupe_gear_community_templates(templates):
                template["scanRunId"] = scan_run_id
                saved = upsert_community_gear_template(conn, template)
                total += 1
                signatures.add(saved["signature"])
                if saved["status"] == "complete":
                    complete += 1
                elif saved["status"] == "partial":
                    partial += 1
                else:
                    blocked += 1
    hidden = 0
    rows = conn.execute(
        """
        SELECT signature, COUNT(*)
        FROM websim_community_gear_templates
        WHERE status IN ('complete', 'partial')
        GROUP BY signature
        """
    ).fetchall()
    for _, count in rows:
        hidden += max(0, int(count or 0) - 1)
    default_templates = default_gear_template_coverage_payload(
        total_specs,
        default_covered_specs,
        default_blockers,
        scan_run_id=scan_run_id,
    )
    if default_templates["blockedSpecCount"]:
        source_status = "partial" if total else "blocked"
    else:
        source_status = "synced" if complete and not partial else ("partial" if total else "blocked")
    return {
        "sourceStatus": source_status,
        "templateRevision": community_template_revision_from_signatures(signatures),
        "templates": {
            "total": total,
            "verified": complete,
            "partial": partial,
            "blocked": blocked,
        },
        "realCommunityTemplates": {
            "templateRevision": COMMUNITY_TEMPLATE_REVISION,
            "totalSpecCount": total_specs,
            "coveredSpecCount": len(real_covered_specs),
            "missingSpecCount": len(real_missing_specs),
            "blockedSpecCount": 0,
            "coveredSpecs": real_covered_specs,
            "missingSpecs": real_missing_specs,
            "topBlockers": [],
            "lastSyncRun": scan_run_id,
        },
        "defaultTemplates": default_templates,
        "dedupedCount": len(signatures),
        "hiddenDuplicateCount": hidden,
        "checkedAt": utc_now(),
    }


def get_websim_gear(conn, class_key="mage", spec_key="arcane", compact=False):
    season = get_active_season_payload(conn)
    class_key = slugify(class_key, "mage")
    spec_key = slugify(spec_key, "arcane")
    compact = bool(compact)
    season_fields = season_metadata_fields(season)
    if compact:
        season_fields["currentSeason"] = compact_season_payload(season_fields.get("currentSeason"))
    catalog_state = gear_catalog_sync_state(conn)
    presets = get_websim_presets(conn, class_key, spec_key)
    community_templates = dedupe_gear_community_templates([
        *websim_gear_community_templates(presets, class_key, spec_key),
        *get_persisted_community_gear_templates(conn, class_key, spec_key),
    ])
    preset_items = []
    for preset in presets:
        preset_items.extend(preset_gear_items(preset))
    baseline_set = []
    for item in preset_gear_items(presets[0] if presets else {}):
        if item.get("slot") not in {entry.get("slot") for entry in baseline_set}:
            baseline_set.append(item)
    candidate_items = get_websim_loot(conn, {}, limit=120)["items"]
    catalog_items = get_websim_gear_catalog_items(conn, class_key, spec_key, season)
    shared_catalog = shared_gear_catalog_rows(conn)
    socket_options_by_slot = shared_catalog["socketOptionsBySlot"]
    enchant_options_by_slot = shared_catalog["enchantOptionsBySlot"]
    embellishment_options_by_slot = shared_catalog["embellishmentOptionsBySlot"]
    baseline_set = hydrate_gear_items_from_metadata(conn, baseline_set)
    preset_items = hydrate_gear_items_from_metadata(conn, preset_items)
    candidate_items = hydrate_gear_items_from_metadata(conn, candidate_items)
    baseline_set = normalize_websim_gear_items(baseline_set, class_key, spec_key)
    preset_items = normalize_gear_item_list(preset_items, class_key, spec_key)
    candidate_items = normalize_gear_item_list(candidate_items, class_key, spec_key)
    candidate_items = [
        item
        for item in candidate_items
        if gear_source_active_for_replacement(item, season)
    ]
    baseline_set = [sanitize_gear_candidate_mod_options(item) for item in baseline_set]
    preset_items = [sanitize_gear_candidate_mod_options(item) for item in preset_items]
    catalog_items = [sanitize_gear_candidate_mod_options(item) for item in catalog_items]
    candidate_items = [sanitize_gear_candidate_mod_options(item) for item in candidate_items]
    baseline_set = enrich_gear_items_with_catalog_records(baseline_set, catalog_items)
    preset_items = enrich_gear_items_with_catalog_records(preset_items, catalog_items)
    baseline_set = apply_spec_primary_stat_display_to_items(baseline_set, class_key, spec_key)
    preset_items = apply_spec_primary_stat_display_to_items(preset_items, class_key, spec_key)
    catalog_items = apply_spec_primary_stat_display_to_items(catalog_items, class_key, spec_key)
    candidate_items = apply_spec_primary_stat_display_to_items(candidate_items, class_key, spec_key)
    observed_baseline_set = observed_profile_baseline_items(catalog_items, class_key, spec_key)
    if not baseline_set and observed_baseline_set:
        baseline_set = observed_baseline_set
    if not community_templates and observed_baseline_set:
        observed_template = gear_community_template_from_observed_items(observed_baseline_set, class_key, spec_key)
        if observed_template:
            community_templates = dedupe_gear_community_templates([observed_template])
    grouped = {slot: [] for slot in CANONICAL_GEAR_SLOTS}
    for item in [*baseline_set, *preset_items, *catalog_items, *candidate_items]:
        if isinstance(item, dict):
            normalized = item
        else:
            normalized = normalize_gear_item(item, class_key, spec_key, item.get("sourceType") if isinstance(item, dict) else "")
        if normalized and normalized.get("slot") in grouped:
            if gear_candidate_incompatible(normalized):
                continue
            for candidate_slot in gear_candidate_slots(normalized, normalized.get("classKey"), normalized.get("specKey")):
                if candidate_slot in grouped:
                    grouped[candidate_slot].append(gear_candidate_for_slot(normalized, candidate_slot))
    candidate_limit = 12 if compact else None
    allow_source_only_fallback = (class_key, spec_key) in SOURCE_ONLY_REPLACEMENT_FALLBACK_SPECS
    slot_groups = []
    baseline_candidates_by_slot = {}
    for slot in CANONICAL_GEAR_SLOTS:
        grouped_items = unique_gear_candidates(grouped.get(slot, []))
        official_ilevel_floor = current_official_replacement_item_level_floor(grouped_items)
        items = [
            item
            for item in grouped_items
            if gear_candidate_visible_for_replacement(item, minimum_observed_ilevel=official_ilevel_floor)
        ]
        if not items and allow_source_only_fallback:
            fallback_limit = min(candidate_limit or 24, 5 if compact else 24)
            items = source_only_replacement_fallback_candidates(grouped_items, season, limit=fallback_limit)
        items = sorted(items, key=gear_candidate_quality_score, reverse=True)
        if candidate_limit:
            items = limit_replacement_candidates(items, candidate_limit)
        baseline_candidates_by_slot[slot] = items
        socket_options = []
        enchant_options = []
        embellishment_options = []
        if compact:
            socket_options = compact_gear_mod_options(
                option
                for item in items
                for option in item.get("socketOptions") or []
            )
            if not socket_options and items and slot in SOCKET_OPTION_GEAR_SLOTS:
                socket_options = compact_gear_mod_options(socket_options_by_slot.get(slot, []))
            enchant_options = compact_gear_mod_options(
                option
                for item in items
                for option in item.get("enchantOptions") or []
            )
            if not enchant_options and items and slot in ENCHANTABLE_GEAR_SLOTS:
                enchant_options = compact_gear_mod_options(
                    option
                    for option in enchant_options_by_slot.get(slot, [])
                    if any(gear_enchant_option_applies_to_item(option, item) for item in items)
                )
            embellishment_options = compact_gear_mod_options(
                option
                for item in items
                for option in item.get("embellishmentOptions") or []
            )
            if not embellishment_options and items and any((item.get("modCapabilities") or {}).get("canEmbellish") for item in items):
                embellishment_options = compact_gear_mod_options(
                    option
                    for option in embellishment_options_by_slot.get(slot, [])
                    if any(gear_embellishment_option_applies_to_item(option, item) for item in items)
                )
            items = compact_gear_candidates(items, include_mod_options=False)
        slot_group = {
            "slot": slot,
            "simcSlot": slot,
            "label": GEAR_SLOT_LABELS.get(slot, slot),
            "items": items,
        }
        if socket_options:
            slot_group["socketOptions"] = socket_options
        if enchant_options:
            slot_group["enchantOptions"] = enchant_options
        if embellishment_options:
            slot_group["embellishmentOptions"] = embellishment_options
        slot_groups.append(slot_group)
    baseline_set = complete_baseline_with_candidate_slots(baseline_set, baseline_candidates_by_slot)
    output_baseline_set = compact_gear_candidates(baseline_set) if compact else baseline_set
    output_community_templates = (
        [compact_community_gear_template(template) for template in community_templates]
        if compact
        else community_templates
    )
    equipped_set = gear_items_by_slot(output_baseline_set, class_key, spec_key)
    readiness = gear_readiness(baseline_set)
    payload = {
        "classKey": class_key,
        "specKey": spec_key,
        "weaponRule": weapon_equipment_rule_payload(class_key, spec_key),
        "slots": gear_slot_payload(),
        "replacementCandidates": slot_groups,
        "equippedSet": equipped_set,
        "slotReadiness": gear_slot_readiness(baseline_set, class_key, spec_key),
        "baselineSet": output_baseline_set,
        "communityTemplates": output_community_templates,
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
        "catalogCheckedAt": catalog_state.get("checkedAt") or "",
        "catalogBlockers": catalog_state.get("blockers") or [],
        "maxLevel": websim_max_level(),
        "checkedAt": utc_now(),
        **season_fields,
    }
    if not compact:
        payload["slotGroups"] = slot_groups
        payload["presets"] = presets
        payload["candidateItems"] = candidate_items[:24]
        payload["catalogItems"] = catalog_items[:120]
        try:
            try:
                from .raiderio_payload import get_raiderio_payload, observed_gear_for_spec
            except ImportError:
                from raiderio_payload import get_raiderio_payload, observed_gear_for_spec

            raiderio = get_raiderio_payload(conn)
            payload["raiderioObservedGear"] = observed_gear_for_spec(raiderio, class_key, spec_key)
            payload["raiderioSourceStatus"] = raiderio.get("sourceStatus") or "blocked"
            payload["raiderioCheckedAt"] = raiderio.get("checkedAt") or ""
        except Exception as error:
            payload["raiderioObservedGear"] = []
            payload["raiderioSourceStatus"] = "blocked"
            payload["raiderioErrors"] = [str(error)]
    return payload


def get_websim_loot(conn, filters=None, limit=120):
    ensure_websim_tables(conn)
    filters = filters or {}
    season = get_active_season_payload(conn)
    if season.get("dataStatus") != "verified":
        return {"items": [], "instances": [], **season_metadata_fields(season)}
    rows = conn.execute(
        """
        SELECT l.id, l.instance_id, i.name, l.encounter_id, e.name, l.item_id, l.name, l.slot, l.quality, l.icon_url, wi.payload_json
        FROM websim_loot l
        LEFT JOIN websim_instances i ON i.id = l.instance_id
        LEFT JOIN websim_encounters e ON e.id = l.encounter_id
        LEFT JOIN websim_items wi ON wi.id = l.item_id
        ORDER BY i.name, e.name, l.name
        LIMIT 500
        """
    ).fetchall()
    items = []
    for row in rows:
        try:
            item_payload = json.loads(row[10] or "{}")
        except Exception:
            item_payload = {}
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
                "source": f"{row[4] or 'Unknown Encounter'} · {row[2] or 'Unknown Instance'}",
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
        item.update({
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
        })
        items.append(item)
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


def first_matching_value(source, keys, default=""):
    if not isinstance(source, dict):
        return default
    for key in keys:
        if key in source and source.get(key) not in (None, ""):
            return source.get(key)
    return default


def normalize_slot(value):
    return canonical_gear_slot(value)


def simc_option_value(source, aliases):
    return normalize_option_value(first_matching_value(source, aliases))


def raw_source_type(value, default=""):
    return re.sub(r"[^A-Za-z0-9_/-]+", "", str(value or default or "").strip())[:40]


def gear_item_missing_fields(item):
    source_type = item.get("sourceType") or ""
    missing = []
    if not item.get("slot"):
        missing.append("slot")
    if not item.get("id"):
        missing.append("itemId")
    if item.get("id") and source_type in SIMC_READY_SOURCE_TYPES:
        return missing
    if item.get("id") and item.get("bonus_id"):
        return missing
    if item.get("id") and item.get("ilevel") and item.get("simcIlevelOnly"):
        return missing
    if source_type in {"verifiedLoot", "loot"}:
        if item.get("variantKey") and item.get("ilevel") and any(item.get(key) for key in BASE_ITEM_INSTANCE_OPTION_KEYS):
            return missing
        missing.extend(["variantKey", "ilevel", "bonus_id/gem_id/enchant_id"])
        return missing
    if item.get("id") and item.get("ilevel") and any(item.get(key) for key in BASE_ITEM_INSTANCE_OPTION_KEYS):
        return missing
    if not item.get("ilevel"):
        missing.append("ilevel")
    if not any(item.get(key) for key in BASE_ITEM_INSTANCE_OPTION_KEYS):
        missing.append("bonus_id/gem_id/enchant_id")
    return missing


def gear_item_simc_ready(item):
    return bool(item.get("slot") and item.get("id") and not gear_item_missing_fields(item))


def payload_item_class_is_armor(item_class):
    if not isinstance(item_class, dict):
        return False
    try:
        if int(item_class.get("id") or 0) in ARMOR_ITEM_CLASS_IDS:
            return True
    except (TypeError, ValueError):
        pass
    names = [
        item_class.get("name"),
        item_class.get("type"),
        item_class.get("display_string"),
    ]
    return any(str(name or "").strip().lower() in ARMOR_CLASS_NAMES for name in names)


def normalized_armor_subclass(item_subclass):
    if not isinstance(item_subclass, dict):
        return ""
    try:
        subclass_id = int(item_subclass.get("id") or 0)
    except (TypeError, ValueError):
        subclass_id = 0
    if subclass_id in ARMOR_SUBCLASS_TYPES:
        return ARMOR_SUBCLASS_TYPES[subclass_id]
    names = [
        item_subclass.get("name"),
        item_subclass.get("type"),
        item_subclass.get("display_string"),
    ]
    for name in names:
        normalized = str(name or "").strip().lower()
        if normalized in ARMOR_SUBCLASS_NAMES:
            return ARMOR_SUBCLASS_NAMES[normalized]
    return ""


def payload_item_class_is_weapon(item_class):
    if not isinstance(item_class, dict):
        return False
    try:
        if int(item_class.get("id") or 0) in WEAPON_ITEM_CLASS_IDS:
            return True
    except (TypeError, ValueError):
        pass
    names = [
        item_class.get("name"),
        item_class.get("type"),
        item_class.get("display_string"),
    ]
    return any(str(name or "").strip().lower() in WEAPON_CLASS_NAMES for name in names)


def payload_item_class_is_gem(item_class):
    if not isinstance(item_class, dict):
        return False
    try:
        if int(item_class.get("id") or 0) in GEM_ITEM_CLASS_IDS:
            return True
    except (TypeError, ValueError):
        pass
    names = [
        item_class.get("name"),
        item_class.get("type"),
        item_class.get("display_string"),
    ]
    return any(str(name or "").strip().lower() in GEM_CLASS_NAMES for name in names)


def payload_item_class_display_name(item_class):
    if not isinstance(item_class, dict):
        return ""
    for key in ("name", "type", "display_string"):
        value = str(item_class.get(key) or "").strip()
        if value:
            return value
    value = item_class.get("id")
    return str(value) if value not in ("", None) else ""


def normalized_weapon_subclass(item_subclass):
    if not isinstance(item_subclass, dict):
        return ""
    try:
        subclass_id = int(item_subclass.get("id")) if item_subclass.get("id") not in (None, "") else -1
    except (TypeError, ValueError):
        subclass_id = -1
    if subclass_id in WEAPON_SUBCLASS_TYPES:
        return WEAPON_SUBCLASS_TYPES[subclass_id]
    names = [
        item_subclass.get("name"),
        item_subclass.get("type"),
        item_subclass.get("display_string"),
    ]
    for name in names:
        normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", str(name or "").strip().lower()).strip("_")
        if normalized in WEAPON_SUBCLASS_NAMES:
            return WEAPON_SUBCLASS_NAMES[normalized]
        text = str(name or "").strip().lower()
        if text in WEAPON_SUBCLASS_NAMES:
            return WEAPON_SUBCLASS_NAMES[text]
    return ""


def item_type_metadata_from_payload(payload):
    payload = payload if isinstance(payload, dict) else {}
    item_class = payload.get("item_class") if isinstance(payload.get("item_class"), dict) else {}
    item_subclass = payload.get("item_subclass") if isinstance(payload.get("item_subclass"), dict) else {}
    slot = item_slot_from_payload(payload)
    armor_type = normalized_armor_subclass(item_subclass) if payload_item_class_is_armor(item_class) else ""
    weapon_type = normalized_weapon_subclass(item_subclass) if payload_item_class_is_weapon(item_class) else ""
    if armor_type == "Shield":
        weapon_type = "Shield"
    if not weapon_type and slot == "off_hand":
        inventory_type = payload.get("inventory_type") if isinstance(payload.get("inventory_type"), dict) else {}
        inventory_key = re.sub(r"[^a-z0-9_]+", "_", str(inventory_type.get("type") or "").lower()).strip("_")
        if inventory_key in {"holdable", "held_in_off_hand", "invtype_holdable"} or inventory_key.endswith("_holdable"):
            weapon_type = "Held In Off-hand"
    return {
        "armorType": armor_type,
        "weaponType": weapon_type,
        "itemSetName": item_set_name_from_payload(payload),
        "supportsSocket": item_payload_has_socket(payload),
    }


def class_spec_can_use_held_offhand(class_key, spec_key=""):
    class_key = slugify(class_key, "")
    spec_key = slugify(spec_key, "")
    rule = weapon_equipment_rule_for_spec(class_key, spec_key)
    if rule:
        return "Held In Off-hand" in set(rule.get("offHandTypes") or [])
    if class_key in HELD_OFFHAND_CLASSES:
        return True
    if spec_key:
        return (class_key, spec_key) in HELD_OFFHAND_SPECS
    return False


def weapon_equipment_rule_for_spec(class_key, spec_key=""):
    class_key = slugify(class_key, "")
    spec_key = slugify(spec_key, "")
    if not class_key:
        return {}
    rule = SPEC_WEAPON_EQUIPMENT_RULES.get((class_key, spec_key))
    if rule:
        return rule
    allowed_types = CLASS_WEAPON_TYPES.get(class_key)
    if not allowed_types:
        return {}
    return {
        "mode": "class_proficiency",
        "mainHandTypes": set(allowed_types),
        "offHandTypes": set(),
    }


def weapon_equipment_rule_payload(class_key, spec_key=""):
    rule = weapon_equipment_rule_for_spec(class_key, spec_key)
    if not rule:
        return {}
    return {
        "mode": str(rule.get("mode") or ""),
        "mainHandTypes": sorted(str(value) for value in rule.get("mainHandTypes") or []),
        "offHandTypes": sorted(str(value) for value in rule.get("offHandTypes") or []),
    }


def primary_stat_key_for_spec(class_key, spec_key=""):
    class_key = slugify(class_key, "")
    spec_key = slugify(spec_key, "")
    if class_key in {"deathknight", "warrior"}:
        return "strength"
    if class_key in {"demonhunter", "hunter", "rogue"}:
        return "agility"
    if class_key in {"evoker", "mage", "priest", "warlock"}:
        return "intellect"
    if class_key == "paladin":
        return "intellect" if spec_key == "holy" else "strength"
    if class_key == "shaman":
        return "agility" if spec_key == "enhancement" else "intellect"
    if class_key == "druid":
        return "agility" if spec_key in {"feral", "guardian"} else "intellect"
    if class_key == "monk":
        return "intellect" if spec_key == "mistweaver" else "agility"
    return ""


def weapon_type_in_class_proficiency(class_key, weapon_type):
    class_key = slugify(class_key, "")
    weapon_type = str(weapon_type or "").strip()
    if not class_key or not weapon_type:
        return True
    if weapon_type in SHIELD_WEAPON_TYPES:
        return class_key in SHIELD_CLASSES
    if weapon_type in HELD_OFFHAND_WEAPON_TYPES:
        return class_spec_can_use_held_offhand(class_key)
    allowed_types = CLASS_WEAPON_TYPES.get(class_key)
    if allowed_types is None:
        return True
    return weapon_type in allowed_types


def weapon_type_allowed_for_slot(class_key, spec_key, simc_slot, weapon_type):
    class_key = slugify(class_key, "")
    spec_key = slugify(spec_key, "")
    simc_slot = normalize_slot(simc_slot)
    weapon_type = str(weapon_type or "").strip()
    if not class_key or not simc_slot or not weapon_type:
        return True
    rule = weapon_equipment_rule_for_spec(class_key, spec_key)
    if not rule:
        return weapon_type_in_class_proficiency(class_key, weapon_type)
    if weapon_type not in SHIELD_WEAPON_TYPES and weapon_type not in HELD_OFFHAND_WEAPON_TYPES:
        if not weapon_type_in_class_proficiency(class_key, weapon_type):
            return False
    if simc_slot == "main_hand":
        return weapon_type in set(rule.get("mainHandTypes") or [])
    if simc_slot == "off_hand":
        return weapon_type in set(rule.get("offHandTypes") or [])
    return False


def class_spec_can_use_weapon_type(class_key, spec_key, weapon_type):
    class_key = slugify(class_key, "")
    weapon_type = str(weapon_type or "").strip()
    if not class_key or not weapon_type:
        return True
    return weapon_type_allowed_for_slot(class_key, spec_key, "main_hand", weapon_type)


def gear_compatibility_from_payload(payload, class_key, simc_slot, spec_key=""):
    if not isinstance(payload, dict) or not class_key:
        return "unknown"
    allowed_class_keys = payload_playable_class_keys(payload)
    if allowed_class_keys and class_key not in allowed_class_keys:
        return "incompatible"
    if simc_slot in WEAPON_SLOTS:
        weapon_type = item_type_metadata_from_payload(payload).get("weaponType") or ""
        if weapon_type == "Shield":
            return "compatible" if weapon_type_allowed_for_slot(class_key, spec_key, simc_slot, weapon_type) else "incompatible"
        if weapon_type == "Held In Off-hand":
            return "compatible" if weapon_type_allowed_for_slot(class_key, spec_key, simc_slot, weapon_type) else "incompatible"
        if weapon_type:
            return "compatible" if weapon_type_allowed_for_slot(class_key, spec_key, simc_slot, weapon_type) else "incompatible"
        return "unknown"
    if simc_slot not in ARMOR_SLOTS:
        return "unknown"
    item_class = payload.get("item_class") or {}
    item_subclass = payload.get("item_subclass") or {}
    expected_armor = CLASS_ARMOR_TYPES.get(class_key)
    actual_armor = normalized_armor_subclass(item_subclass)
    if not payload_item_class_is_armor(item_class) or not expected_armor or not actual_armor:
        return "unknown"
    if actual_armor in {"Miscellaneous", "Cosmetic"}:
        return "unknown"
    return "compatible" if actual_armor.lower() == expected_armor.lower() else "incompatible"


def payload_playable_class_keys(payload):
    result = []
    for parent in (payload_preview_item(payload), payload if isinstance(payload, dict) else {}):
        if not isinstance(parent, dict):
            continue
        requirements = parent.get("requirements") if isinstance(parent.get("requirements"), dict) else {}
        playable_classes = requirements.get("playable_classes") if isinstance(requirements.get("playable_classes"), dict) else {}
        candidates = []
        links = playable_classes.get("links")
        if isinstance(links, list):
            candidates.extend(links)
        classes = playable_classes.get("classes")
        if isinstance(classes, list):
            candidates.extend(classes)
        if isinstance(playable_classes.get("id"), int):
            candidates.append(playable_classes)
        for entry in candidates:
            if not isinstance(entry, dict):
                continue
            raw_id = entry.get("id")
            try:
                class_id = int(raw_id)
            except (TypeError, ValueError):
                class_id = 0
            class_key = GAME_CLASS_ID_TO_KEY.get(class_id, "")
            if class_key and class_key not in result:
                result.append(class_key)
    return result


def normalize_gear_item(value, class_key="", spec_key="", default_source_type=""):
    if not isinstance(value, dict):
        return None
    slot = normalize_slot(first_matching_value(value, ["simcSlot", "slot", "slotKey", "equipmentSlot"]))
    item_id = normalize_option_value(first_matching_value(value, ["itemId", "item_id", "id"]))
    if not slot or not item_id:
        return None
    source_type = raw_source_type(first_matching_value(value, ["sourceType", "type"], default_source_type))
    if not source_type:
        source_type = "manual" if value.get("ilevel") else "candidate"
    simc_item_name = canonical_simc_item_name_from_record(value, item_id) or f"item_{item_id}"
    item = {
        "slot": slot,
        "simcSlot": slot,
        "itemId": item_id,
        "name": simc_item_name,
        "id": item_id,
        "displayName": str(value.get("displayName") or value.get("name") or f"Item {item_id}")[:160],
        "localizedName": str(value.get("localizedName") or value.get("displayName") or "")[:160],
        "englishName": str(value.get("englishName") or "")[:160],
        "iconUrl": str(value.get("iconUrl") or value.get("icon_url") or "")[:260],
        "quality": str(value.get("quality") or "")[:80],
        "sourceType": source_type,
        "source": str(first_matching_value(value, ["source", "sourceName", "encounterName", "instanceName"], ""))[:220],
        "instanceId": str(first_matching_value(value, ["instanceId", "instance_id"], ""))[:80],
        "instanceName": str(first_matching_value(value, ["instanceName", "instance_name"], ""))[:160],
        "encounterId": str(first_matching_value(value, ["encounterId", "encounter_id"], ""))[:80],
        "encounterName": str(first_matching_value(value, ["encounterName", "encounter_name"], ""))[:160],
        "metadataStatus": str(value.get("metadataStatus") or "")[:40],
        "metadataSource": str(value.get("metadataSource") or "")[:120],
        "metadataLocale": str(value.get("metadataLocale") or "")[:20],
        "classKey": slugify(class_key, "") if class_key else str(value.get("classKey") or ""),
        "specKey": slugify(spec_key, "") if spec_key else str(value.get("specKey") or ""),
    }
    payload = value.get("payload") if isinstance(value.get("payload"), dict) else {}
    type_metadata = item_type_metadata_from_payload(payload)
    for key in ("armorType", "weaponType", "itemSetName"):
        text = str(value.get(key) or type_metadata.get(key) or "").strip()
        if text:
            item[key] = text[:120]
    game_asset = normalize_game_asset(
        {},
        game_asset_from_icon_url(
            "item",
            item_id,
            "websim-gear-item",
            item["iconUrl"],
            source=value.get("metadataSource") or value.get("sourceName") or value.get("sourceType") or "websim",
            status="verified" if item["iconUrl"] else (value.get("metadataStatus") or "pending_sync"),
            semantic_tags=["game", "gear", "item", slot, item["classKey"], item["specKey"]],
            usage=["websim_gear", "builds_detail"],
            fallback_text=fallback_text_for(item["displayName"] or item_id),
        ),
    )
    item["gameAsset"] = game_asset
    item["iconUrl"] = game_asset.get("iconUrl") or item["iconUrl"]
    for key, aliases in SIMC_GEAR_OPTION_ALIASES:
        value_text = simc_option_value(value, aliases)
        if value_text:
            item[key] = value_text
    for key in ["variantKey", "defaultVariantKey", "socketOptionId", "enchantOptionId"]:
        option_value = normalize_option_value(value.get(key))
        if option_value:
            item[key] = option_value
    item_stats = value.get("itemStats") or value.get("stats") or extract_item_stats_from_payload(payload)
    if isinstance(item_stats, list) and item_stats:
        normalized_stats = [normalize_item_stat(stat) for stat in item_stats]
        normalized_stats = [stat for stat in normalized_stats if stat]
        if normalized_stats:
            item["itemStats"] = normalized_stats
            item["stats"] = normalized_stats
            item["statSummary"] = str(value.get("statSummary") or item_stat_summary(normalized_stats))[:260]
            stat_display_status = str(value.get("statDisplayStatus") or "").strip()
            stat_source = str(value.get("statSource") or "").strip()
            if not stat_display_status and item["metadataStatus"] == "verified" and item["metadataSource"] == ITEM_METADATA_SOURCE:
                stat_display_status = "battle_net_item_metadata"
            if not stat_source and stat_display_status == "battle_net_item_metadata":
                stat_source = ITEM_METADATA_SOURCE
            if stat_display_status:
                item["statDisplayStatus"] = stat_display_status[:80]
            if stat_source:
                item["statSource"] = stat_source[:120]
    if isinstance(value.get("modCapabilities"), dict):
        computed_capabilities = item_mod_capabilities(payload, slot, item=item)
        source_capabilities = value.get("modCapabilities", {})
        def merged_capability(key):
            if source_capabilities.get(key) is False:
                return False
            return bool(source_capabilities.get(key) or computed_capabilities.get(key))
        item["modCapabilities"] = {
            "hasSocket": merged_capability("hasSocket"),
            "canEnchant": merged_capability("canEnchant"),
            "canEmbellish": merged_capability("canEmbellish"),
        }
        if item["modCapabilities"]["hasSocket"] and computed_capabilities.get("socketCount"):
            item["modCapabilities"]["socketCount"] = computed_capabilities.get("socketCount")
    else:
        item["modCapabilities"] = item_mod_capabilities(payload, slot, item=item)
    for key in ("socketOptions", "enchantOptions", "embellishmentOptions"):
        if isinstance(value.get(key), list):
            item[key] = [option for option in value.get(key) if isinstance(option, dict)]
    for key in (
        "socketOptionId",
        "enchantOptionId",
        "embellishmentOptionId",
        "builtInEmbellishment",
        "intrinsicEmbellishment",
        "inherentEmbellishment",
        "embellishmentSource",
        "builtInEmbellishmentLabel",
        "uniqueEquippedLabel",
        "uniqueGroup",
        "uniqueScope",
    ):
        option_value = normalize_option_value(value.get(key))
        if option_value:
            item[key] = option_value
    for key in ("uniqueEquipped", "unique_equipped"):
        if value.get(key) not in (None, "", [], {}):
            item["uniqueEquipped"] = bool(value.get(key))
    unique_limit = positive_int_value(value.get("uniqueLimit") or value.get("unique_limit"))
    if unique_limit:
        item["uniqueLimit"] = unique_limit
    if value.get("hasBuiltInEmbellishment"):
        item["hasBuiltInEmbellishment"] = True
        item.setdefault("builtInEmbellishment", BUILT_IN_EMBELLISHMENT_VALUE)
        item.setdefault("builtInEmbellishmentLabel", BUILT_IN_EMBELLISHMENT_LABEL)
        item.setdefault("embellishmentSource", "built_in")
    payload_builtin_embellishment = built_in_embellishment_fields_from_payload(payload)
    if payload_builtin_embellishment:
        item.update({key: value for key, value in payload_builtin_embellishment.items() if key not in item})
    payload_unique_equipped = unique_equipped_fields_from_payload(payload)
    if payload_unique_equipped:
        item.update({key: value for key, value in payload_unique_equipped.items() if key not in item})
    if value.get("simcIlevelOnly"):
        item["simcIlevelOnly"] = True
    item["supportsSocket"] = bool(
        value.get("supportsSocket")
        or type_metadata.get("supportsSocket")
        or item.get("modCapabilities", {}).get("hasSocket")
    )
    payload_compatibility = gear_compatibility_from_payload(payload, item["classKey"], slot, item["specKey"])
    existing_compatibility = str(value.get("compatibility") or "")
    item["compatibility"] = (
        payload_compatibility
        if existing_compatibility in {"", "unknown"} and payload_compatibility != "unknown"
        else existing_compatibility or payload_compatibility or "unknown"
    )
    item["missingFields"] = gear_item_missing_fields(item)
    item["simcReady"] = gear_item_simc_ready(item)
    return item


def normalize_websim_gear_items(items, class_key="", spec_key="", default_source_type=""):
    normalized = []
    seen = set()
    for raw_item in items or []:
        item = normalize_gear_item(raw_item, class_key, spec_key, default_source_type)
        if not item or item["slot"] in seen:
            continue
        seen.add(item["slot"])
        normalized.append(item)
    return normalized


def normalize_gear_item_list(items, class_key="", spec_key="", default_source_type=""):
    normalized = []
    for raw_item in items or []:
        item = normalize_gear_item(raw_item, class_key, spec_key, default_source_type)
        if item:
            normalized.append(item)
    return normalized


def gear_item_needs_simc_name_hydration(item):
    if not isinstance(item, dict):
        return False
    item_id = item.get("itemId") or item.get("id")
    return bool(item_id and simc_item_name_is_placeholder(item.get("name"), item_id))


def catalog_simc_item_names_by_id(conn, item_ids):
    if conn is None or not item_ids:
        return {}
    try:
        placeholders = ",".join("?" for _ in item_ids)
        rows = conn.execute(
            f"""
            SELECT id, name, payload_json
            FROM websim_items
            WHERE id IN ({placeholders})
            """,
            [str(item_id) for item_id in item_ids],
        ).fetchall()
    except sqlite3.Error:
        return {}
    names = {}
    for row in rows:
        item_id = str(row[0] or "")
        payload = safe_json_loads(row[2], {})
        record = {
            "itemId": item_id,
            "displayName": row[1] or "",
            "payload": payload if isinstance(payload, dict) else {},
        }
        metadata = record["payload"].get("_metadata") if isinstance(record["payload"].get("_metadata"), dict) else {}
        if metadata.get("englishName"):
            record["englishName"] = metadata.get("englishName")
        name = canonical_simc_item_name_from_record(record, item_id)
        if name:
            names[item_id] = name
    return names


def preset_simc_item_names_by_id(conn, item_ids, class_key="", spec_key=""):
    if conn is None or not item_ids:
        return {}
    try:
        rows = conn.execute(
            """
            SELECT id, class_key, spec_key, name, profile, payload_json
            FROM websim_profile_presets
            WHERE class_key = ? AND spec_key = ?
            """,
            (slugify(class_key, ""), slugify(spec_key, "")),
        ).fetchall()
    except sqlite3.Error:
        return {}
    wanted = {str(item_id) for item_id in item_ids}
    names = {}
    for row in rows:
        preset = {
            "id": row[0],
            "classKey": row[1],
            "specKey": row[2],
            "name": row[3],
            "profile": row[4],
            "payload": safe_json_loads(row[5], {}),
        }
        for item in preset_gear_items(preset):
            item_id = str(item.get("itemId") or item.get("id") or "")
            if item_id not in wanted or item_id in names:
                continue
            name = canonical_simc_item_name_from_record(item, item_id)
            if name:
                names[item_id] = name
    return names


def observed_simc_item_names_by_id(conn, item_ids, class_key="", spec_key=""):
    if conn is None or not item_ids:
        return {}
    try:
        try:
            from .raiderio_payload import get_raiderio_payload
        except ImportError:
            from raiderio_payload import get_raiderio_payload
        raiderio = get_raiderio_payload(conn, allow_sync=False)
    except Exception:
        return {}
    wanted = {str(item_id) for item_id in item_ids}
    class_key = slugify(class_key, "")
    spec_key = slugify(spec_key, "")
    names = {}
    for observed_class, observed_spec, _context, gear in observed_gear_spec_entries(raiderio):
        if observed_class != class_key or observed_spec != spec_key:
            continue
        for item in gear or []:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("itemId") or item.get("item_id") or item.get("id") or "")
            if item_id not in wanted or item_id in names:
                continue
            name = canonical_simc_item_name_from_record(item, item_id)
            if name:
                names[item_id] = name
    return names


def hydrate_simc_item_names(items, class_key="", spec_key="", conn=None):
    if conn is None:
        return items
    needed_ids = []
    seen = set()
    for item in items or []:
        if not gear_item_needs_simc_name_hydration(item):
            continue
        item_id = str(item.get("itemId") or item.get("id") or "")
        if item_id and item_id not in seen:
            seen.add(item_id)
            needed_ids.append(item_id)
    if not needed_ids:
        return items
    names = {}
    for resolver in (
        lambda: catalog_simc_item_names_by_id(conn, needed_ids),
        lambda: preset_simc_item_names_by_id(conn, needed_ids, class_key, spec_key),
        lambda: observed_simc_item_names_by_id(conn, needed_ids, class_key, spec_key),
    ):
        for item_id, name in resolver().items():
            names.setdefault(item_id, name)
    if not names:
        return items
    hydrated = []
    for item in items or []:
        if not gear_item_needs_simc_name_hydration(item):
            hydrated.append(item)
            continue
        item_id = str(item.get("itemId") or item.get("id") or "")
        name = names.get(item_id)
        hydrated.append({**item, "name": name} if name else item)
    return hydrated


def gear_items_by_item_id(items):
    indexed = {}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("itemId") or item.get("id") or "").strip()
        if item_id and item_id not in indexed:
            indexed[item_id] = item
    return indexed


def enrich_gear_items_with_catalog_records(items, catalog_items):
    catalog_by_item_id = gear_items_by_item_id(catalog_items)
    enriched = []
    for item in items or []:
        if not isinstance(item, dict):
            enriched.append(item)
            continue
        catalog_item = catalog_by_item_id.get(str(item.get("itemId") or item.get("id") or "").strip())
        enriched.append(merge_gear_candidate_records(item, catalog_item) if catalog_item else item)
    return enriched


def gear_item_handedness_fields(item):
    if not isinstance(item, dict):
        return {}
    weapon_type = str(item.get("weaponType") or "").strip()
    if not weapon_type:
        return {}
    if weapon_type in RANGED_WEAPON_TYPES:
        return {"handedness": "ranged", "handednessLabel": "\u8fdc\u7a0b"}
    if weapon_type in TWO_HAND_WEAPON_TYPES:
        return {"handedness": "two_hand", "handednessLabel": "\u53cc\u624b"}
    if weapon_type in ONE_HAND_WEAPON_TYPES:
        return {"handedness": "one_hand", "handednessLabel": "\u5355\u624b"}
    if weapon_type in SHIELD_WEAPON_TYPES:
        return {"handedness": "off_hand", "handednessLabel": "\u76fe\u724c"}
    if weapon_type in HELD_OFFHAND_WEAPON_TYPES:
        return {"handedness": "off_hand", "handednessLabel": "\u526f\u624b"}
    return {}


def unique_equipped_bool(value):
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if not text:
        return False
    return text not in {"0", "false", "no", "none", "null"}


def gear_equipment_badges(item):
    badges = []
    if not isinstance(item, dict):
        return badges

    def append_badge(key, label):
        label = str(label or "").strip()
        if not key or not label:
            return
        badge = {"key": key, "label": label}
        if badge not in badges:
            badges.append(badge)

    handedness_label = str(item.get("handednessLabel") or "").strip()
    if handedness_label:
        append_badge("weapon_handedness", handedness_label)
    built_in_label = str(item.get("builtInEmbellishmentLabel") or "").strip()
    if item.get("hasBuiltInEmbellishment") or item.get("builtInEmbellishment"):
        append_badge("built_in_embellishment", built_in_label or BUILT_IN_EMBELLISHMENT_LABEL)
    if unique_equipped_bool(item.get("uniqueEquipped") or item.get("unique_equipped")):
        append_badge("unique_equipped", str(item.get("uniqueEquippedLabel") or "\u552f\u4e00"))
    return badges


def annotate_gear_item_display_fields(item):
    if not isinstance(item, dict):
        return item
    cloned = dict(item)
    for key, value in gear_item_handedness_fields(cloned).items():
        cloned.setdefault(key, value)
    if unique_equipped_bool(cloned.get("uniqueEquipped") or cloned.get("unique_equipped")):
        cloned["uniqueEquipped"] = True
        cloned.setdefault("uniqueEquippedLabel", "\u552f\u4e00")
    badges = gear_equipment_badges(cloned)
    if badges:
        cloned["equipmentBadges"] = badges
    return cloned


def mark_gear_candidate_primary_stat_incompatible(item, primary_key):
    cloned = dict(item)
    reason = f"primary stat incompatible with {primary_key}"
    existing = cloned.get("compatibility")
    if isinstance(existing, dict):
        compatibility = dict(existing)
    else:
        compatibility = {"status": existing or "unknown"}
    compatibility["status"] = "incompatible"
    compatibility["primaryStatStatus"] = "incompatible"
    compatibility["primaryStatKey"] = primary_key
    compatibility["reason"] = reason
    cloned["compatibility"] = compatibility
    cloned["blockers"] = unique_text_list([*(cloned.get("blockers") or []), reason])
    return annotate_gear_item_display_fields(cloned)


def apply_spec_primary_stat_display_fields(item, class_key="", spec_key=""):
    if not isinstance(item, dict):
        return item
    class_key = slugify(class_key or item.get("classKey"), "")
    spec_key = slugify(spec_key or item.get("specKey"), "")
    primary_key = primary_stat_key_for_spec(class_key, spec_key)
    cloned = dict(item)
    if primary_key:
        cloned["primaryStatKey"] = primary_key
    stats = cloned.get("itemStats") or cloned.get("stats") or []
    if primary_key in PRIMARY_STAT_KEYS and stats:
        if not item_stats_primary_compatible(stats, primary_key):
            return mark_gear_candidate_primary_stat_incompatible(cloned, primary_key)
        filtered_stats = filter_item_stats_for_spec(stats, primary_key)
        if filtered_stats:
            cloned["itemStats"] = filtered_stats
            cloned["stats"] = filtered_stats
            if cloned.get("statSummary"):
                cloned["statSummary"] = filter_item_stat_summary_for_spec(cloned.get("statSummary"), primary_key)
            else:
                cloned["statSummary"] = item_stat_summary(filtered_stats)
    elif primary_key in PRIMARY_STAT_KEYS and cloned.get("statSummary"):
        if not item_stat_summary_primary_compatible(cloned.get("statSummary"), primary_key):
            return mark_gear_candidate_primary_stat_incompatible(cloned, primary_key)
        cloned["statSummary"] = filter_item_stat_summary_for_spec(cloned.get("statSummary"), primary_key)
    return annotate_gear_item_display_fields(cloned)


def apply_spec_primary_stat_display_to_items(items, class_key="", spec_key=""):
    return [
        apply_spec_primary_stat_display_fields(item, class_key, spec_key) if isinstance(item, dict) else item
        for item in items or []
    ]


def gear_candidate_slots(item, class_key="", spec_key=""):
    slot = (item or {}).get("slot") or ""
    if slot not in WEAPON_SLOTS:
        return EQUIVALENT_GEAR_SLOTS.get(slot, [slot])
    class_key = slugify(class_key or (item or {}).get("classKey"), "")
    spec_key = slugify(spec_key or (item or {}).get("specKey"), "")
    weapon_type = str((item or {}).get("weaponType") or "").strip()
    if not weapon_type:
        return [slot]
    slots = []
    for candidate_slot in ("main_hand", "off_hand"):
        if weapon_type_allowed_for_slot(class_key, spec_key, candidate_slot, weapon_type):
            if candidate_slot == slot or weapon_type not in SHIELD_WEAPON_TYPES | HELD_OFFHAND_WEAPON_TYPES:
                slots.append(candidate_slot)
    if slots:
        return slots
    return [slot] if not class_key and not spec_key else []


def visible_gear_mod_options(options):
    visible = []
    for option in options or []:
        if not isinstance(option, dict):
            continue
        option_id = str(option.get("id") or "").strip()
        option_name = str(option.get("name") or option.get("label") or "").strip()
        raw_option_name = str(option.get("rawName") or option_name).strip()
        payload = option.get("payload") if isinstance(option.get("payload"), dict) else {}
        if not gear_mod_option_is_visible(option_id, option_name, payload):
            continue
        if (
            payload.get("source") == "observed_variant"
            and raw_option_name.lower().startswith("observed ")
            and not str(payload.get("displayName") or "").strip()
        ):
            continue
        visible.append(option)
    return visible


def hide_candidate_preview_stats(item):
    if not isinstance(item, dict):
        return item
    if not catalog_item_should_hide_preview_stats(item):
        return item
    return hide_candidate_current_variant_stats(item)


def gear_observed_source_label(value):
    return bool(re.search(r"raider\.io.*observed|raider\.io.*观测|实装观测", str(value or ""), flags=re.IGNORECASE))


def gear_simc_preset_source_label(value):
    return str(value or "").strip().lower().startswith("simulationcraft preset")


def gear_candidate_display_source_label(item):
    if not isinstance(item, dict):
        return ""
    official_label = preferred_official_source_label(item)
    if official_label:
        return official_label
    fallback = str(first_matching_value(item, ["source", "sourceName", "encounterName", "instanceName"], "")).strip()
    if gear_observed_source_label(fallback) or gear_simc_preset_source_label(fallback):
        return ""
    return fallback[:220]


def simc_preset_source_label(value):
    label = str(value or "").strip()
    if not label:
        return "SimulationCraft preset"
    if label.lower().startswith("simulationcraft preset"):
        return label[:220]
    return f"SimulationCraft preset: {label}"[:220]


def attach_simc_preset_source_reference(item, display_source=""):
    if not isinstance(item, dict):
        return item
    if raw_source_type(item.get("sourceType")).lower() != "simcpreset":
        return item
    if item.get("sources") or item.get("sourceRefs") or item.get("observedProfileRefs"):
        return item
    source_label = simc_preset_source_label(display_source or item.get("source") or item.get("sourceName"))
    source_ref = {
        "id": f"simc-preset-{stable_digest([item.get('sourceProfileId'), item.get('itemId') or item.get('id'), item.get('slot'), source_label])}",
        "itemId": str(item.get("itemId") or item.get("id") or "").strip(),
        "sourceType": "simc_preset",
        "label": source_label,
        "sourceLabel": source_label,
    }
    item["sources"] = [source_ref]
    item["sourceRefs"] = [source_ref]
    item["source"] = source_label
    return item


def attach_crafted_source_reference(item):
    if not isinstance(item, dict):
        return item
    if not normalize_option_value(item.get("crafted_stats") or item.get("craftedStats")):
        return item
    source_type = raw_source_type(item.get("sourceType")).lower()
    variant_source = raw_source_type(item.get("variantSource")).lower()
    if source_type != "crafted" and variant_source != "crafted":
        return item
    existing_sources = [
        source
        for source in [*(item.get("sources") or []), *(item.get("sourceRefs") or [])]
        if isinstance(source, dict)
    ]
    if any(raw_source_type(source.get("sourceType")).lower() == "crafted" for source in existing_sources):
        return item
    item_id = str(item.get("itemId") or item.get("id") or "").strip()
    source_ref = {
        "id": f"crafted-{stable_digest([item_id, item.get('slot'), item.get('crafted_stats') or item.get('craftedStats')])}",
        "itemId": item_id,
        "sourceType": "crafted",
        "label": "制造装备",
        "sourceLabel": "制造装备",
    }
    sources = merge_keyed_candidate_rows([*existing_sources, source_ref], ("id", "sourceType", "sourceLabel", "label"))
    sources.sort(key=gear_candidate_source_sort_key)
    item["sources"] = sources
    item["sourceRefs"] = sources
    return item


def sanitize_gear_candidate_mod_options(item):
    if not isinstance(item, dict):
        return item
    cloned = dict(item)
    display_source = gear_candidate_display_source_label(cloned)
    cloned = attach_simc_preset_source_reference(cloned, display_source)
    cloned = attach_crafted_source_reference(cloned)
    display_source = gear_candidate_display_source_label(cloned)
    if display_source:
        cloned["source"] = display_source
    else:
        cloned.pop("source", None)
    existing_capabilities = cloned.get("modCapabilities") if isinstance(cloned.get("modCapabilities"), dict) else {}
    computed_capabilities = item_mod_capabilities({}, cloned.get("slot") or "", cloned.get("variants") or [], cloned)
    def merged_capability(key):
        if existing_capabilities.get(key) is False:
            return False
        return bool(existing_capabilities.get(key) or computed_capabilities.get(key))
    capabilities = {
        "hasSocket": merged_capability("hasSocket"),
        "canEnchant": merged_capability("canEnchant"),
        "canEmbellish": merged_capability("canEmbellish"),
    }
    if capabilities["hasSocket"] and computed_capabilities.get("socketCount"):
        capabilities["socketCount"] = computed_capabilities.get("socketCount")
    allow_mod_options = bool(
        cloned.get("simcReady")
        or any(str(variant.get("status") or "").strip().lower() == "verified" for variant in cloned.get("variants") or [])
    )
    cloned["modCapabilities"] = capabilities
    socket_options = visible_gear_mod_options(cloned.get("socketOptions") or [])
    enchant_options = [
        option
        for option in visible_gear_mod_options(cloned.get("enchantOptions") or [])
        if gear_enchant_option_applies_to_item(option, cloned)
    ]
    embellishment_options = [
        option
        for option in visible_gear_mod_options(cloned.get("embellishmentOptions") or [])
        if gear_embellishment_option_applies_to_item(option, cloned)
    ]
    cloned["socketOptions"] = socket_options if capabilities["hasSocket"] and allow_mod_options else []
    cloned["enchantOptions"] = enchant_options if capabilities["canEnchant"] and allow_mod_options else []
    cloned["embellishmentOptions"] = embellishment_options if capabilities["canEmbellish"] and allow_mod_options else []
    return hide_candidate_preview_stats(cloned)


def gear_candidate_for_slot(item, slot):
    if not isinstance(item, dict) or item.get("slot") == slot:
        return sanitize_gear_candidate_mod_options(item)
    cloned = dict(item)
    cloned["slot"] = slot
    cloned["simcSlot"] = slot
    game_asset = dict(cloned.get("gameAsset") or {})
    if game_asset:
        tags = [tag for tag in game_asset.get("semanticTags") or [] if tag not in CANONICAL_GEAR_SLOTS]
        game_asset["semanticTags"] = [*tags, slot]
        cloned["gameAsset"] = game_asset
    return sanitize_gear_candidate_mod_options(cloned)


def gear_candidate_incompatible(item):
    compatibility = (item or {}).get("compatibility")
    if isinstance(compatibility, dict):
        return compatibility.get("status") == "incompatible"
    return compatibility == "incompatible"


def normalized_candidate_text(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def gear_candidate_visible_source_key(item):
    sources = item.get("sources") if isinstance(item, dict) else []
    labels = []
    if isinstance(sources, list):
        for source in sources:
            if not isinstance(source, dict):
                continue
            label = normalized_candidate_text(source.get("label") or source.get("sourceLabel"))
            source_type = normalized_candidate_text(source.get("sourceType"))
            if label:
                labels.append(f"{source_type}:{label}")
    if not labels:
        label = normalized_candidate_text(
            first_matching_value(item or {}, ["source", "sourceName", "encounterName", "instanceName"], "")
        )
        source_type = normalized_candidate_text((item or {}).get("sourceType"))
        if label:
            labels.append(f"{source_type}:{label}")
    return "|".join(unique_text_list(labels[:3]))


def gear_candidate_visible_key(item):
    if not isinstance(item, dict):
        return None
    display_name = normalized_candidate_text(item.get("displayName") or item.get("localizedName") or item.get("name"))
    source_key = gear_candidate_visible_source_key(item)
    if not display_name or not source_key:
        return None
    return (
        normalize_slot(item.get("slot")),
        display_name,
        source_key,
    )


def gear_candidate_item_visible_key(item):
    if not isinstance(item, dict):
        return None
    item_id = normalize_option_value(item.get("itemId") or item.get("id"))
    if not item_id:
        return None
    return (
        normalize_slot(item.get("slot")),
        item_id,
    )


def gear_candidate_has_observed_profile(item):
    if not isinstance(item, dict):
        return False
    if raw_source_type(item.get("variantSource") or item.get("sourceType")).lower() == "observed_profile":
        return True
    for key in ("sources", "variants"):
        for row in item.get(key) or []:
            if isinstance(row, dict) and raw_source_type(row.get("sourceType")).lower() == "observed_profile":
                return True
    return bool(item.get("observedProfileRefs"))


def gear_candidate_stat_score(item):
    total = 0
    for stat in (item or {}).get("itemStats") or (item or {}).get("stats") or []:
        if not isinstance(stat, dict):
            continue
        value = stat.get("value")
        if isinstance(value, (int, float)):
            total += int(value)
            continue
        text = re.sub(r"[^\d-]+", "", str(value or ""))
        if text and text not in {"-", "--"}:
            try:
                total += int(text)
            except ValueError:
                pass
    return total


def gear_candidate_has_verified_stats(item):
    if not isinstance(item, dict):
        return False
    has_stats = bool(item.get("itemStats") or item.get("stats") or item.get("statSummary"))
    status = str(item.get("statDisplayStatus") or "").strip()
    source = str(item.get("statSource") or "").strip()
    return has_stats and (status == "verified_variant" or source == "simulationcraft")


GEAR_CANDIDATE_STATUS_RANK = {
    "verified": 4,
    "complete": 4,
    "synced": 3,
    "partial": 2,
    "source_reference": 1,
    "blocked": 0,
}


def gear_candidate_variant_status_rank(item):
    if not isinstance(item, dict):
        return 0
    status = str(item.get("variantStatus") or item.get("metadataStatus") or "").strip().lower()
    return GEAR_CANDIDATE_STATUS_RANK.get(status, 0)


def gear_candidate_simc_option_quality(item):
    if not isinstance(item, dict):
        return (0, 0, 0, 0)
    return (
        gear_candidate_variant_status_rank(item),
        1 if item.get("simcReady") else 0,
        positive_int_value(item.get("ilevel") or item.get("itemLevel")),
        1 if any(item.get(key) for key in BASE_ITEM_INSTANCE_OPTION_KEYS) else 0,
    )


def gear_candidate_quality_score(item):
    status = str(item.get("variantStatus") or item.get("metadataStatus") or "").strip().lower()
    source_types = gear_candidate_source_types(item)
    official_source = bool(source_types & OFFICIAL_REPLACEMENT_SOURCE_TYPES)
    official_source_label = preferred_official_source_label(item)
    display_source_label = gear_candidate_display_source_label(item)
    observed_profile_evidence = gear_candidate_has_observed_profile(item)
    item_id = positive_int_value(item.get("itemId") or item.get("id"))
    return (
        1 if gear_candidate_has_verified_stats(item) else 0,
        1 if item.get("simcReady") else 0,
        1 if official_source else 0,
        1 if official_source_label else 0,
        1 if display_source_label else 0,
        1 if observed_profile_evidence else 0,
        GEAR_CANDIDATE_STATUS_RANK.get(status, 0),
        positive_int_value(item.get("ilevel") or item.get("itemLevel")),
        1 if any(item.get(key) for key in BASE_ITEM_INSTANCE_OPTION_KEYS) else 0,
        1 if item.get("metadataStatus") == "verified" else 0,
        item_id,
    )


def merge_keyed_candidate_rows(rows, key_fields):
    merged = []
    seen = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        key = tuple(str(row.get(field) or "").strip() for field in key_fields)
        if not any(key):
            key = (json.dumps(row, sort_keys=True, ensure_ascii=False),)
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
    return merged


def gear_candidate_source_sort_key(source):
    source_type = raw_source_type((source or {}).get("sourceType")).lower()
    if source_type in OFFICIAL_REPLACEMENT_SOURCE_TYPES:
        rank = 0
    elif source_type in {"verifiedloot", "verified_loot", "loot"}:
        rank = 1
    elif source_type in {"simcpreset", "simc_preset"}:
        rank = 3
    else:
        rank = 2
    return (
        rank,
        str((source or {}).get("sourceLabel") or (source or {}).get("label") or ""),
        str((source or {}).get("id") or ""),
    )


def gear_candidate_source_types(item):
    source_types = set()
    if not isinstance(item, dict):
        return source_types
    for key in ("sourceType", "variantSource"):
        source_type = raw_source_type(item.get(key)).lower()
        if source_type:
            source_types.add(source_type)
    for collection_key in ("sources", "sourceRefs", "variants"):
        for row in item.get(collection_key) or []:
            if not isinstance(row, dict):
                continue
            source_type = raw_source_type(row.get("sourceType")).lower()
            if source_type:
                source_types.add(source_type)
    return source_types


def preferred_official_source_label(item):
    if not isinstance(item, dict):
        return ""
    sources = []
    for source in [*(item.get("sources") or []), *(item.get("sourceRefs") or [])]:
        if isinstance(source, dict):
            sources.append(source)
    for source in sources:
        source_type = raw_source_type(source.get("sourceType")).lower()
        if source_type in OFFICIAL_REPLACEMENT_SOURCE_TYPES:
            label = str(source.get("label") or source.get("sourceLabel") or "").strip()
            if label:
                return label
    for source in sources:
        source_type = raw_source_type(source.get("sourceType")).lower()
        label = str(source.get("label") or source.get("sourceLabel") or "").strip()
        if source_type in {"observed_profile", "simcpreset", "simc_preset"} or gear_observed_source_label(label) or gear_simc_preset_source_label(label):
            continue
        if label:
            return label
    return ""


def merge_gear_candidate_records(primary, secondary):
    if not isinstance(primary, dict):
        return secondary
    if not isinstance(secondary, dict):
        return primary
    merged = dict(primary)
    merged["sources"] = merge_keyed_candidate_rows(
        [
            *(primary.get("sources") or []),
            *(primary.get("sourceRefs") or []),
            *(secondary.get("sources") or []),
            *(secondary.get("sourceRefs") or []),
        ],
        ("id", "sourceType", "sourceLabel", "label", "instanceId", "encounterId"),
    )
    if merged["sources"]:
        merged["sources"].sort(key=gear_candidate_source_sort_key)
        merged["sourceRefs"] = merged["sources"]
    else:
        merged.pop("sources", None)
    merged["variants"] = merge_keyed_candidate_rows(
        [*(primary.get("variants") or []), *(secondary.get("variants") or [])],
        ("id", "sourceType", "variantKey", "key", "difficultyKey", "itemLevel", "ilevel"),
    )
    if not merged["variants"]:
        merged.pop("variants", None)
    else:
        apply_default_catalog_variant(merged, merged["variants"])
    merged["observedProfileRefs"] = merge_keyed_candidate_rows(
        [*(primary.get("observedProfileRefs") or []), *(secondary.get("observedProfileRefs") or [])],
        ("sourceName", "characterName", "classKey", "specKey", "profileUrl"),
    )
    if not merged["observedProfileRefs"]:
        merged.pop("observedProfileRefs", None)
    primary_caps = primary.get("modCapabilities") if isinstance(primary.get("modCapabilities"), dict) else {}
    secondary_caps = secondary.get("modCapabilities") if isinstance(secondary.get("modCapabilities"), dict) else {}
    if primary_caps or secondary_caps:
        merged["modCapabilities"] = {
            "hasSocket": bool(primary_caps.get("hasSocket") or secondary_caps.get("hasSocket")),
            "canEnchant": bool(primary_caps.get("canEnchant") or secondary_caps.get("canEnchant")),
            "canEmbellish": bool(primary_caps.get("canEmbellish") or secondary_caps.get("canEmbellish")),
        }
    for key, key_fields in [
        ("socketOptions", ("id", "name", "label")),
        ("enchantOptions", ("id", "name", "label")),
        ("embellishmentOptions", ("id", "name", "label")),
    ]:
        values = merge_keyed_candidate_rows(
            [*(primary.get(key) or []), *(secondary.get(key) or [])],
            key_fields,
        )
        merged[key] = values
    for key in [
        "displayName",
        "localizedName",
        "englishName",
        "iconUrl",
        "quality",
        "metadataStatus",
        "metadataSource",
        "metadataLocale",
        "gameAsset",
        "armorType",
        "weaponType",
        "itemSetName",
        "compatibility",
        "recommendationScore",
        "defaultVariantKey",
        "variantKey",
        "variantLabel",
        "variantDifficultyKey",
        "variantDifficultyLabel",
        "variantSource",
        "variantStatus",
        "hasBuiltInEmbellishment",
        "builtInEmbellishment",
        "intrinsicEmbellishment",
        "inherentEmbellishment",
        "builtInEmbellishmentLabel",
        "embellishmentSource",
    ]:
        if merged.get(key) in (None, "", [], {}) and secondary.get(key) not in (None, "", [], {}):
            merged[key] = secondary.get(key)
    if secondary.get("statDisplayStatus") == "verified_variant" and secondary.get("itemStats"):
        for key in ("itemStats", "stats", "statSummary", "statDisplayStatus", "statSource"):
            if secondary.get(key) not in (None, "", [], {}):
                merged[key] = secondary.get(key)
    elif not merged.get("itemStats") and secondary.get("itemStats"):
        for key in ("itemStats", "stats", "statSummary", "statDisplayStatus", "statSource"):
            if secondary.get(key) not in (None, "", [], {}):
                merged[key] = secondary.get(key)
    if gear_candidate_simc_option_quality(secondary) > gear_candidate_simc_option_quality(primary):
        for key in (
            "simcReady",
            "ilevel",
            "itemLevel",
            "bonus_id",
            "gem_id",
            "gem_bonus_id",
            "gem_ilevel",
            "enchant_id",
            "crafted_stats",
            "defaultVariantKey",
            "variantKey",
            "variantLabel",
            "variantDifficultyKey",
            "variantDifficultyLabel",
            "variantSource",
            "variantStatus",
            "variantBlockers",
            "blockers",
        ):
            if secondary.get(key) not in (None, "", [], {}):
                merged[key] = secondary.get(key)
    if not merged.get("simcReady") and secondary.get("simcReady"):
        for key in (
            "simcReady",
            "ilevel",
            "itemLevel",
            "bonus_id",
            "gem_id",
            "gem_bonus_id",
            "gem_ilevel",
            "enchant_id",
            "crafted_stats",
            "simcLine",
            "sourceProfileId",
        ):
            if secondary.get(key) not in (None, "", [], {}):
                merged[key] = secondary.get(key)
        if raw_source_type(secondary.get("sourceType")).lower() == "simcpreset":
            merged["sourceType"] = secondary.get("sourceType")
    for key in ("missingFields", "variantBlockers", "blockers"):
        merged[key] = unique_text_list([*(primary.get(key) or []), *(secondary.get(key) or [])])
    for candidate in (primary, secondary):
        if raw_source_type(candidate.get("sourceType")).lower() == "simcpreset":
            merged["sourceType"] = candidate.get("sourceType")
            break
    source_label = preferred_official_source_label(merged)
    if source_label:
        merged["source"] = source_label
    return sanitize_gear_candidate_mod_options(merged)


def observed_only_replacement_candidate_below_current_floor(item, minimum_observed_ilevel=0):
    if not isinstance(item, dict):
        return False
    source_types = gear_candidate_source_types(item)
    if source_types & OFFICIAL_REPLACEMENT_SOURCE_TYPES:
        return False
    if "crafted" in source_types:
        return False
    if "observed_profile" not in source_types and not gear_candidate_has_observed_profile(item):
        return False
    minimum_ilevel = positive_int_value(minimum_observed_ilevel)
    if minimum_ilevel <= 0:
        return False
    item_level = positive_int_value(item.get("ilevel") or item.get("itemLevel"))
    return item_level > 0 and item_level < minimum_ilevel


def gear_candidate_visible_for_replacement(item, minimum_observed_ilevel=0):
    if not isinstance(item, dict):
        return False
    if gear_candidate_incompatible(item):
        return False
    if observed_only_replacement_candidate_below_current_floor(item, minimum_observed_ilevel):
        return False
    if item.get("simcReady"):
        return True
    source_types = gear_candidate_source_types(item)
    official_source = bool(source_types & OFFICIAL_REPLACEMENT_SOURCE_TYPES)
    status = str(item.get("variantStatus") or "").strip().lower()
    difficulty_key = str(item.get("variantDifficultyKey") or "").strip().lower()
    variant_key = str(item.get("variantKey") or item.get("defaultVariantKey") or "").strip().lower()
    blockers = " ".join(
        [
            *text_list_value(item.get("missingFields")),
            *text_list_value(item.get("blockers")),
            *text_list_value(item.get("variantBlockers")),
        ]
    ).lower()
    if official_source and (
        status in {"", "partial", "blocked"}
        or difficulty_key in {"needs-variant", "needs_variant", "battle_net_preview"}
        or variant_key.startswith("battle-net-preview")
        or "deterministic simc variant" in blockers
        or "bonus_id/gem_id/enchant_id" in blockers
        or "ilevel" in blockers
    ):
        return False
    return True


def limit_replacement_candidates(items, limit):
    if not limit or limit <= 0:
        return list(items or [])
    rows = list(items or [])
    if len(rows) <= limit:
        return rows
    limited = rows[:limit]
    seen = {
        gear_candidate_item_visible_key(item)
        or gear_candidate_visible_key(item)
        or gear_candidate_key(item)
        for item in limited
    }
    for item in rows[limit:]:
        if "crafted" not in gear_candidate_source_types(item):
            continue
        key = gear_candidate_item_visible_key(item) or gear_candidate_visible_key(item) or gear_candidate_key(item)
        if key in seen:
            continue
        limited.append(item)
        seen.add(key)
    return limited


def current_official_replacement_item_level_floor(items):
    levels = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        if not (gear_candidate_source_types(item) & OFFICIAL_REPLACEMENT_SOURCE_TYPES):
            continue
        item_level = positive_int_value(item.get("ilevel") or item.get("itemLevel"))
        if item_level > 0:
            levels.append(item_level)
    return min(levels) if levels else 0


SOURCE_ONLY_REPLACEMENT_FALLBACK_REASON = "source_only_current_season"
SOURCE_ONLY_REPLACEMENT_FALLBACK_BLOCKER = "missing deterministic SimC variant preset"
SOURCE_ONLY_REPLACEMENT_FALLBACK_SPECS = {
    ("druid", "restoration"),
    ("evoker", "preservation"),
    ("evoker", "augmentation"),
    ("monk", "mistweaver"),
    ("paladin", "holy"),
    ("priest", "discipline"),
    ("priest", "holy"),
    ("shaman", "restoration"),
}


def current_official_replacement_sources(item, season):
    if not isinstance(item, dict):
        return []
    rows = []
    for source in [*(item.get("sources") or []), *(item.get("sourceRefs") or [])]:
        if not isinstance(source, dict):
            continue
        source_type = raw_source_type(source.get("sourceType")).lower()
        if source_type not in OFFICIAL_REPLACEMENT_SOURCE_TYPES:
            continue
        if gear_source_active_for_replacement(source, season):
            rows.append(source)
    source_type = raw_source_type(item.get("sourceType")).lower()
    if source_type in OFFICIAL_REPLACEMENT_SOURCE_TYPES and gear_source_active_for_replacement(item, season):
        rows.append(item)
    return merge_keyed_candidate_rows(
        rows,
        ("id", "sourceType", "sourceLabel", "label", "instanceId", "encounterId"),
    )


def source_only_replacement_fallback_candidate(item, season):
    if not isinstance(item, dict):
        return None
    if item.get("simcReady") or gear_candidate_incompatible(item):
        return None
    if str(item.get("metadataStatus") or "").strip() != "verified":
        return None
    if str(item.get("metadataSource") or "").strip() != ITEM_METADATA_SOURCE:
        return None
    current_sources = current_official_replacement_sources(item, season)
    if not current_sources:
        return None
    fallback = dict(item)
    fallback["sources"] = current_sources
    fallback["sourceRefs"] = current_sources
    fallback["source"] = preferred_official_source_label(fallback) or fallback.get("source") or "gear catalog"
    fallback["simcReady"] = False
    fallback["replacementFallback"] = True
    fallback["fallbackReason"] = SOURCE_ONLY_REPLACEMENT_FALLBACK_REASON
    fallback["statDisplayStatus"] = "pending_current_variant"
    fallback["variantStatus"] = fallback.get("variantStatus") or "partial"
    for key in ("itemStats", "stats", "statSummary"):
        fallback.pop(key, None)
    fallback["missingFields"] = unique_text_list(
        [
            *(fallback.get("missingFields") or []),
            "ilevel",
            "bonus_id/gem_id/enchant_id",
        ]
    )
    fallback["variantBlockers"] = unique_text_list(
        [
            *(fallback.get("variantBlockers") or []),
            SOURCE_ONLY_REPLACEMENT_FALLBACK_BLOCKER,
        ]
    )
    fallback["blockers"] = unique_text_list(
        [
            *(fallback.get("blockers") or []),
            *fallback["variantBlockers"],
            SOURCE_ONLY_REPLACEMENT_FALLBACK_BLOCKER,
        ]
    )
    return sanitize_gear_candidate_mod_options(fallback)


def source_only_replacement_fallback_candidates(items, season, limit=None):
    fallbacks = []
    seen = set()
    for item in items or []:
        fallback = source_only_replacement_fallback_candidate(item, season)
        if not fallback:
            continue
        key = gear_candidate_item_visible_key(fallback) or gear_candidate_visible_key(fallback) or gear_candidate_key(fallback)
        if key in seen:
            continue
        seen.add(key)
        fallbacks.append(fallback)
        if limit and limit > 0 and len(fallbacks) >= limit:
            break
    return fallbacks


def gear_candidate_key(item):
    if not isinstance(item, dict):
        return ("",)
    item_id = item.get("itemId") or item.get("id") or item.get("name") or ""
    return tuple(
        str(value or "")
        for value in [
            item.get("slot"),
            item_id,
            item.get("ilevel"),
            item.get("bonus_id"),
            item.get("gem_id"),
            item.get("gem_bonus_id"),
            item.get("gem_ilevel"),
            item.get("enchant_id"),
            item.get("crafted_stats"),
            item.get("embellishment"),
        ]
    )


def unique_gear_candidates(items, limit=None):
    unique_items = []
    seen_exact = set()
    item_indexes = {}
    visible_indexes = {}
    for item in items or []:
        item = sanitize_gear_candidate_mod_options(item)
        key = gear_candidate_key(item)
        item_key = gear_candidate_item_visible_key(item)
        visible_key = gear_candidate_visible_key(item)
        if key in seen_exact:
            existing_index = None
            if item_key and item_key in item_indexes:
                existing_index = item_indexes[item_key]
            elif visible_key and visible_key in visible_indexes:
                existing_index = visible_indexes[visible_key]
            if existing_index is not None:
                if gear_candidate_quality_score(item) > gear_candidate_quality_score(unique_items[existing_index]):
                    unique_items[existing_index] = merge_gear_candidate_records(item, unique_items[existing_index])
                else:
                    unique_items[existing_index] = merge_gear_candidate_records(unique_items[existing_index], item)
            continue
        seen_exact.add(key)
        if item_key and item_key in item_indexes:
            existing_index = item_indexes[item_key]
            if gear_candidate_quality_score(item) > gear_candidate_quality_score(unique_items[existing_index]):
                unique_items[existing_index] = merge_gear_candidate_records(item, unique_items[existing_index])
            else:
                unique_items[existing_index] = merge_gear_candidate_records(unique_items[existing_index], item)
            if visible_key:
                visible_indexes[visible_key] = existing_index
            continue
        if visible_key and visible_key in visible_indexes:
            existing_index = visible_indexes[visible_key]
            if gear_candidate_quality_score(item) > gear_candidate_quality_score(unique_items[existing_index]):
                unique_items[existing_index] = merge_gear_candidate_records(item, unique_items[existing_index])
            else:
                unique_items[existing_index] = merge_gear_candidate_records(unique_items[existing_index], item)
            if item_key:
                item_indexes[item_key] = existing_index
            continue
        if item_key:
            item_indexes[item_key] = len(unique_items)
        if visible_key:
            visible_indexes[visible_key] = len(unique_items)
        unique_items.append(item)
    if limit and limit > 0:
        return unique_items[:limit]
    return unique_items


COMPACT_GEAR_CANDIDATE_KEYS = {
    "slot",
    "simcSlot",
    "itemId",
    "name",
    "id",
    "displayName",
    "iconUrl",
    "sourceType",
    "source",
    "metadataStatus",
    "ilevel",
    "bonus_id",
    "gem_id",
    "gem_bonus_id",
    "gem_ilevel",
    "enchant_id",
    "crafted_stats",
    "embellishment",
    "hasBuiltInEmbellishment",
    "builtInEmbellishment",
    "intrinsicEmbellishment",
    "inherentEmbellishment",
    "builtInEmbellishmentLabel",
    "embellishmentSource",
    "itemStats",
    "statSummary",
    "primaryStatKey",
    "handedness",
    "handednessLabel",
    "uniqueEquipped",
    "unique_equipped",
    "uniqueEquippedLabel",
    "uniqueLimit",
    "uniqueGroup",
    "uniqueScope",
    "equipmentBadges",
    "modCapabilities",
    "armorType",
    "weaponType",
    "itemSetName",
    "supportsSocket",
    "compatibility",
    "missingFields",
    "simcReady",
    "simcIlevelOnly",
    "recommendationScore",
    "defaultVariantKey",
    "variantKey",
    "variantLabel",
    "variantDifficultyKey",
    "variantDifficultyLabel",
    "variantSource",
    "variantStatus",
    "variantBlockers",
    "blockers",
    "statDisplayStatus",
    "statSource",
    "simcStatStatus",
    "simcStatFailureKind",
    "simcStatCheckedAt",
    "replacementFallback",
    "fallbackReason",
}
COMPACT_GEAR_SOURCE_KEYS = {
    "id",
    "itemId",
    "sourceType",
    "label",
    "sourceLabel",
    "instanceId",
    "encounterId",
    "difficultyKey",
    "difficultyLabel",
    "seasonRevision",
    "recommendationScore",
    "updatedAt",
}
COMPACT_GEAR_VARIANT_KEYS = {
    "id",
    "itemId",
    "slot",
    "key",
    "variantKey",
    "label",
    "difficultyLabel",
    "sourceType",
    "difficultyKey",
    "itemLevel",
    "ilevel",
    "simcOptions",
    "status",
    "blockers",
    "simcIlevelOnly",
    "itemStats",
    "stats",
    "statSummary",
    "primaryStatKey",
    "statDisplayStatus",
    "statSource",
    "simcStatStatus",
    "simcStatFailureKind",
    "simcStatCheckedAt",
    "updatedAt",
}
COMPACT_GEAR_MOD_OPTION_KEYS = {
    "id",
    "type",
    "optionType",
    "name",
    "label",
    "displayName",
    "displayLabel",
    "displayKind",
    "displayStatus",
    "evidenceSource",
    "evidenceRef",
    "simcOptions",
    "status",
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
}


def compact_dict(source, allowed_keys):
    if not isinstance(source, dict):
        return {}
    result = {}
    for key in allowed_keys:
        if key not in source:
            continue
        value = source.get(key)
        if value in (None, "", [], {}):
            continue
        result[key] = value
    return result


def compact_gear_mod_options(options):
    compacted = []
    seen = set()
    for option in options or []:
        compact_option = compact_dict(option, COMPACT_GEAR_MOD_OPTION_KEYS)
        if not compact_option:
            continue
        key = json.dumps(compact_option, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        compacted.append(compact_option)
    return compacted


def executable_fallback_gear_mod_options(options, option_type):
    option_type = str(option_type or "").strip().lower()
    if option_type not in {"socket"}:
        return []
    fallback_options = []
    for option in options or []:
        if not isinstance(option, dict):
            continue
        option_status = str(option.get("status") or "").strip().lower()
        if option_status != "verified":
            continue
        option_id = str(option.get("id") or "").strip()
        option_name = str(option.get("name") or option.get("label") or "").strip()
        payload = option.get("payload") if isinstance(option.get("payload"), dict) else {}
        if not gear_mod_option_is_visible(option_id, option_name, payload):
            continue
        simc_options = option.get("simcOptions") if isinstance(option.get("simcOptions"), dict) else {}
        simc_options = {
            key: normalize_option_value(value)
            for key, value in simc_options.items()
            if key in SIMC_GEAR_OPTION_KEYS and normalize_option_value(value)
        }
        if option_type == "socket":
            value = simc_options.get("gem_id")
            label = f"宝石 {value}" if value else ""
        else:
            value = simc_options.get("enchant_id")
            label = str(option.get("label") or option.get("name") or "").strip()
            if not label or re.fullmatch(r"附魔\s*[\d/]+", label):
                label = f"附魔 {value}" if value else ""
        if not label:
            continue
        fallback = dict(option)
        fallback["type"] = option_type
        fallback["optionType"] = option_type
        fallback["name"] = label
        fallback["label"] = label
        fallback["status"] = "verified"
        fallback["simcOptions"] = simc_options
        fallback_options.append(fallback)
    return compact_gear_mod_options(fallback_options)


def compact_gear_sources(sources):
    compacted = []
    for source in sources or []:
        if not isinstance(source, dict):
            continue
        if raw_source_type(source.get("sourceType")).lower() == "observed_profile":
            continue
        compact_source = compact_dict(source, COMPACT_GEAR_SOURCE_KEYS)
        if compact_source:
            compacted.append(compact_source)
    return compacted


def compact_gear_sources_have_drop_source(sources):
    for source in sources or []:
        if not isinstance(source, dict):
            continue
        source_type = raw_source_type(source.get("sourceType")).lower()
        if source_type in {"observed_profile", "simc_preset", "simcpreset"}:
            continue
        label = str(source.get("label") or source.get("sourceLabel") or "").strip()
        if label:
            return True
    return False


def public_variant_source_type_from_sources(item, sources):
    if not isinstance(item, dict):
        return ""
    for source in sources or []:
        if not isinstance(source, dict):
            continue
        source_type = raw_source_type(source.get("sourceType")).lower()
        if source_type in OFFICIAL_REPLACEMENT_SOURCE_TYPES:
            return source_type
    for source in sources or []:
        if not isinstance(source, dict):
            continue
        source_type = raw_source_type(source.get("sourceType")).lower()
        if source_type == "crafted":
            return source_type
    for key in ("variantSource", "sourceType"):
        source_type = raw_source_type(item.get(key)).lower()
        if source_type in OFFICIAL_REPLACEMENT_SOURCE_TYPES:
            return source_type
    source_type = raw_source_type(item.get("sourceType")).lower()
    if source_type and source_type not in {"observed_profile", "simc_preset", "simcpreset"}:
        return source_type
    return ""


def public_variant_difficulty_label(source_type, fallback_text=""):
    return localized_difficulty_label(source_type, fallback_text, source_type) or str(fallback_text or "").strip()


def public_variant_difficulty_key(source_type):
    source_type = raw_source_type(source_type).lower()
    if source_type in OFFICIAL_REPLACEMENT_SOURCE_TYPES:
        return source_type
    if source_type == "crafted":
        return "crafted"
    if source_type == "catalog":
        return "source_pending"
    return ""


def compact_gear_variant(variant, public_source_type="", primary_key=""):
    compact_variant = compact_dict(variant, COMPACT_GEAR_VARIANT_KEYS)
    if not compact_variant:
        return compact_variant
    payload = variant.get("payload") if isinstance(variant.get("payload"), dict) else {}
    for key in (
        "itemStats",
        "stats",
        "statSummary",
        "statDisplayStatus",
        "statSource",
        "simcStatStatus",
        "simcStatFailureKind",
        "simcStatCheckedAt",
    ):
        value = payload.get(key)
        if value not in (None, "", [], {}):
            compact_variant[key] = value
    if primary_key in PRIMARY_STAT_KEYS:
        compact_variant["primaryStatKey"] = primary_key
        compact_variant = apply_primary_stat_filter_to_stat_payload(compact_variant, primary_key)
        if compact_variant is None:
            return None
    public_source_type = raw_source_type(public_source_type).lower()
    variant_source = raw_source_type(compact_variant.get("sourceType")).lower()
    difficulty_key = str(compact_variant.get("difficultyKey") or "").strip().lower()
    public_difficulty_key = public_variant_difficulty_key(public_source_type)
    if public_difficulty_key and (
        variant_source == "observed_profile" or difficulty_key == "observed_profile"
    ):
        compact_variant["sourceType"] = public_source_type
        compact_variant["difficultyKey"] = public_difficulty_key
        compact_variant["difficultyLabel"] = public_variant_difficulty_label(
            public_difficulty_key,
            compact_variant.get("difficultyLabel") or compact_variant.get("label"),
        )
    return compact_variant


def sanitize_compact_candidate_variant_fields(compact_item, public_source_type):
    if not isinstance(compact_item, dict):
        return compact_item
    public_source_type = raw_source_type(public_source_type).lower()
    public_difficulty_key = public_variant_difficulty_key(public_source_type)
    if not public_difficulty_key:
        return compact_item
    variant_source = raw_source_type(compact_item.get("variantSource")).lower()
    difficulty_key = str(compact_item.get("variantDifficultyKey") or "").strip().lower()
    if variant_source == "observed_profile":
        compact_item["variantSource"] = public_source_type
    if difficulty_key == "observed_profile":
        compact_item["variantDifficultyKey"] = public_difficulty_key
        compact_item["variantDifficultyLabel"] = public_variant_difficulty_label(
            public_difficulty_key,
            compact_item.get("variantDifficultyLabel") or compact_item.get("variantLabel"),
        )
    return compact_item


COMPACT_OBSERVED_PROFILE_REF_KEYS = {
    "sourceName",
    "sourceStatus",
    "checkedAt",
    "classKey",
    "specKey",
    "slot",
    "itemId",
    "itemLevel",
}


def compact_observed_profile_refs(refs, limit=3):
    compacted = []
    seen = set()
    for ref in refs or []:
        if not isinstance(ref, dict):
            continue
        compact_ref = compact_dict(ref, COMPACT_OBSERVED_PROFILE_REF_KEYS)
        if not compact_ref:
            continue
        key = json.dumps(compact_ref, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        compacted.append(compact_ref)
        if limit and len(compacted) >= limit:
            break
    return compacted


def crafted_stat_option_key_from_variant(variant):
    payload = variant.get("payload") if isinstance((variant or {}).get("payload"), dict) else {}
    simc_options = variant.get("simcOptions") if isinstance((variant or {}).get("simcOptions"), dict) else {}
    return slugify(
        payload.get("craftedStatKey")
        or payload.get("craftedStatLabel")
        or simc_options.get("crafted_stats")
        or variant.get("variantKey")
        or variant.get("key"),
        f"crafted-{stable_digest([variant.get('id'), simc_options.get('crafted_stats')])}",
    )


def compact_crafted_stat_option(variant, primary_key=""):
    payload = variant.get("payload") if isinstance((variant or {}).get("payload"), dict) else {}
    simc_options = variant.get("simcOptions") if isinstance((variant or {}).get("simcOptions"), dict) else {}
    crafted_stats = normalize_option_value(
        simc_options.get("crafted_stats")
        or payload.get("crafted_stats")
        or payload.get("craftedStats")
    )
    if not crafted_stats:
        return None
    if primary_key in PRIMARY_STAT_KEYS:
        filtered_payload = apply_primary_stat_filter_to_stat_payload(dict(payload), primary_key)
        if filtered_payload is None:
            return None
        payload = filtered_payload
    option = {
        "key": crafted_stat_option_key_from_variant(variant),
        "label": str(payload.get("craftedStatLabel") or crafted_stats),
        "simcOptions": {"crafted_stats": crafted_stats},
        "status": str(variant.get("status") or payload.get("status") or "blocked"),
    }
    for key in (
        "itemStats",
        "stats",
        "statSummary",
        "statDisplayStatus",
        "statSource",
        "simcStatStatus",
        "simcStatFailureKind",
        "simcStatCheckedAt",
    ):
        value = payload.get(key)
        if value not in (None, "", [], {}):
            option[key] = value
    blockers = variant.get("blockers") or []
    if blockers:
        option["blockers"] = blockers
    return option


def compact_crafted_gear_variants(variants, primary_key=""):
    by_track = {}
    order = []
    for variant in variants or []:
        if not isinstance(variant, dict):
            continue
        if raw_source_type(variant.get("sourceType")).lower() != "crafted":
            continue
        public_key = crafted_public_difficulty_key(variant.get("difficultyKey"))
        item_level = positive_int_value(variant.get("itemLevel") or variant.get("ilevel"))
        track_key = (public_key, item_level)
        option = compact_crafted_stat_option(variant, primary_key)
        if track_key not in by_track:
            compact_variant = compact_gear_variant(variant, "crafted", primary_key)
            if not compact_variant:
                continue
            compact_variant["difficultyKey"] = public_key
            compact_variant["difficultyLabel"] = localized_difficulty_label(public_key, variant.get("label"), "crafted")
            compact_variant["key"] = f"crafted-{public_key}-{item_level}" if item_level else f"crafted-{public_key}"
            compact_variant["variantKey"] = compact_variant["key"]
            compact_variant["label"] = f"{compact_variant['difficultyLabel']} {item_level}".strip()
            compact_simc_options = compact_variant.get("simcOptions") if isinstance(compact_variant.get("simcOptions"), dict) else {}
            compact_simc_options = {key: value for key, value in compact_simc_options.items() if key != "crafted_stats"}
            if compact_simc_options:
                compact_variant["simcOptions"] = compact_simc_options
            else:
                compact_variant.pop("simcOptions", None)
            compact_variant["craftedStatOptions"] = []
            by_track[track_key] = compact_variant
            order.append(track_key)
        if option:
            existing_keys = {row.get("key") for row in by_track[track_key]["craftedStatOptions"]}
            if option["key"] not in existing_keys:
                by_track[track_key]["craftedStatOptions"].append(option)
    result = []
    for track_key in order:
        variant = by_track[track_key]
        variant["craftedStatOptions"].sort(
            key=lambda option: (
                0 if str(option.get("status") or "") == "verified" else 1,
                option.get("label") or "",
            )
        )
        result.append(variant)
    result.sort(key=lambda variant: positive_int_value(variant.get("itemLevel") or variant.get("ilevel")), reverse=True)
    return result


def observed_profile_display_source_label(item):
    if not isinstance(item, dict):
        return ""
    source_types = gear_candidate_source_types(item)
    semantic_source_types = {source_type for source_type in source_types if source_type != "catalog"}
    if semantic_source_types:
        if "observed_profile" not in semantic_source_types:
            return ""
        if semantic_source_types - {"observed_profile", "simcpreset", "simc_preset"}:
            return ""
    elif not item.get("observedProfileRefs"):
        return ""
    source_name = ""
    for ref in item.get("observedProfileRefs") or []:
        if not isinstance(ref, dict):
            continue
        source_name = str(ref.get("sourceName") or "").strip()
        if source_name:
            break
    if not source_name:
        for source in item.get("sources") or item.get("sourceRefs") or []:
            if not isinstance(source, dict):
                continue
            if raw_source_type(source.get("sourceType")).lower() != "observed_profile":
                continue
            source_name = str(source.get("sourceName") or source.get("sourceLabel") or source.get("label") or "").strip()
            if source_name:
                break
    if not source_name:
        return "实装观测（Raider.IO）"
    if "raider" in source_name.lower():
        source_name = "Raider.IO"
    return f"实装观测（{source_name[:80]}）"


def compact_gear_candidate(item, include_mod_options=True):
    if not isinstance(item, dict):
        return item
    compact_item = compact_dict(item, COMPACT_GEAR_CANDIDATE_KEYS)
    primary_key = str(item.get("primaryStatKey") or "").strip()
    item_id = normalize_option_value(item.get("itemId") or item.get("id"))
    placeholder_names = {f"item_{item_id}", f"Item {item_id}"} if item_id else set()
    display_name = next(
        (
            str(item.get(key) or "").strip()
            for key in ("displayName", "localizedName", "englishName", "name")
            if str(item.get(key) or "").strip() and str(item.get(key) or "").strip() not in placeholder_names
        ),
        "",
    )
    if display_name:
        compact_item["name"] = display_name
        compact_item.setdefault("displayName", display_name)
    sources = compact_gear_sources(item.get("sources") or [])
    if not compact_item.get("source") and not compact_gear_sources_have_drop_source(sources):
        compact_item["source"] = "来源待补充"
    if sources:
        compact_item["sources"] = sources
        source_type = raw_source_type(sources[0].get("sourceType")).lower()
        if source_type and source_type not in {"observed_profile", "simc_preset", "simcpreset"}:
            compact_item["sourceType"] = source_type
    public_source_type = public_variant_source_type_from_sources(item, sources)
    if not public_source_type and not compact_gear_sources_have_drop_source(sources):
        public_source_type = "catalog"
    current_public_source_type = raw_source_type(compact_item.get("sourceType")).lower()
    if "crafted" in gear_candidate_source_types(item) and (
        raw_source_type(item.get("variantSource")).lower() == "crafted"
        or raw_source_type(item.get("sourceType")).lower() == "crafted"
        or current_public_source_type == "crafted"
    ):
        public_source_type = "crafted"
        compact_item["sourceType"] = "crafted"
        current_public_source_type = "crafted"
    if public_source_type and current_public_source_type in {"", "observed_profile"}:
        compact_item["sourceType"] = public_source_type
    sanitize_compact_candidate_variant_fields(compact_item, public_source_type)
    if public_source_type == "crafted":
        variants = compact_crafted_gear_variants(item.get("variants") or [], primary_key)
    if public_source_type != "crafted" or not variants:
        variants = [
            compact_gear_variant(variant, public_source_type, primary_key)
            for variant in item.get("variants") or []
            if isinstance(variant, dict)
        ]
    variants = [variant for variant in variants if variant]
    if variants:
        compact_item["variants"] = variants
    if public_source_type == "crafted" and any(variant.get("craftedStatOptions") for variant in variants):
        compact_item.pop("crafted_stats", None)
    observed_profile_refs = compact_observed_profile_refs(item.get("observedProfileRefs") or [])
    if observed_profile_refs:
        compact_item["observedProfileRefs"] = observed_profile_refs
    if include_mod_options:
        socket_options = compact_gear_mod_options(item.get("socketOptions") or [])
        enchant_options = compact_gear_mod_options(item.get("enchantOptions") or [])
        embellishment_options = compact_gear_mod_options(item.get("embellishmentOptions") or [])
        if socket_options:
            compact_item["socketOptions"] = socket_options
        if enchant_options:
            compact_item["enchantOptions"] = enchant_options
        if embellishment_options:
            compact_item["embellishmentOptions"] = embellishment_options
    return compact_item


def compact_gear_candidates(items, include_mod_options=True):
    return [
        compact_gear_candidate(item, include_mod_options=include_mod_options)
        for item in items or []
        if isinstance(item, dict)
    ]


def compact_community_gear_template(template):
    if not isinstance(template, dict):
        return template
    compact_template = dict(template)
    compact_template.pop("payload", None)
    compact_template["gearItems"] = compact_gear_candidates(template.get("gearItems") or [])
    return compact_template


def build_websim_gear_lines(items):
    lines = []
    for item in normalize_websim_gear_items(items):
        if not item.get("simcReady"):
            continue
        parts = [f'{item["slot"]}={item["name"]}', f'id={item["id"]}']
        for key in ["ilevel", "bonus_id", "gem_id", "gem_bonus_id", "gem_ilevel", "enchant_id", "crafted_stats", "embellishment"]:
            if item.get(key):
                parts.append(f"{key}={item[key]}")
        lines.append(",".join(parts))
    return lines


def parse_simc_gear_line(line, class_key="", spec_key="", source_name="", source_profile_id=""):
    stripped = str(line or "").strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    head, *option_parts = [part.strip() for part in stripped.split(",") if part.strip()]
    slot, name = head.split("=", 1)
    slot = normalize_slot(slot)
    if not slot:
        return None
    options = {}
    for part in option_parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        options[key.strip()] = value.strip()
    item_id = normalize_option_value(options.get("id"))
    if not item_id:
        return None
    raw_item = {
        "slot": slot,
        "name": name.strip().strip('"'),
        "id": item_id,
        "sourceType": "simcPreset",
        "source": source_name,
        "sourceProfileId": source_profile_id,
    }
    for key in SIMC_GEAR_OPTION_KEYS:
        if options.get(key):
            raw_item[key] = options[key]
    item = normalize_gear_item(raw_item, class_key, spec_key, "simcPreset")
    if item:
        item["sourceProfileId"] = source_profile_id
        item["simcLine"] = ",".join([head, *option_parts])
    return item


def preset_gear_items(preset):
    if not isinstance(preset, dict):
        return []
    payload = preset.get("payload") if isinstance(preset.get("payload"), dict) else {}
    simc_gear_by_slot = simc_json_gear_stats_by_slot(payload)
    items = []
    for line in str(preset.get("profile") or "").splitlines():
        item = parse_simc_gear_line(
            line,
            preset.get("classKey") or "",
            preset.get("specKey") or "",
            preset.get("name") or "SimC preset",
            preset.get("id") or "",
        )
        if item:
            stat_payload = simc_observed_variant_stat_payload(item, simc_gear_by_slot)
            if stat_payload:
                item.update({
                    "itemStats": stat_payload.get("itemStats") or [],
                    "stats": stat_payload.get("itemStats") or [],
                    "statSummary": stat_payload.get("statSummary") or "",
                    "statDisplayStatus": stat_payload.get("statDisplayStatus") or "verified_variant",
                    "statSource": stat_payload.get("statSource") or "simulationcraft",
                })
            items.append(item)
    return items


def profile_preset_observed_stat_payloads_by_identity(conn):
    rows = conn.execute(
        """
        SELECT id, class_key, spec_key, name, profile, payload_json
        FROM websim_profile_presets
        ORDER BY class_key, spec_key, id
        """
    ).fetchall()
    payloads = {}
    for preset_id, class_key, spec_key, name, profile, payload_json in rows:
        payload = safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        simc_gear_by_slot = simc_json_gear_stats_by_slot(payload)
        if not simc_gear_by_slot:
            continue
        for line in str(profile or "").splitlines():
            item = parse_simc_gear_line(line, class_key, spec_key, name or "SimC preset", preset_id)
            if not item:
                continue
            stat_payload = simc_observed_variant_stat_payload(item, simc_gear_by_slot)
            if not stat_payload:
                continue
            item_level = item.get("ilevel") or item.get("itemLevel") or stat_payload.get("simcItemLevel")
            simc_options = {
                key: normalize_option_value(item.get(key))
                for key in SIMC_GEAR_OPTION_KEYS
                if key != "ilevel" and normalize_option_value(item.get(key))
            }
            key = observed_variant_stat_identity_key(
                item.get("itemId") or item.get("id"),
                item.get("slot"),
                item_level,
                simc_options,
            )
            payloads.setdefault(key, stat_payload)
            same_item_level_key = observed_variant_stat_identity_key(
                item.get("itemId") or item.get("id"),
                item.get("slot"),
                item_level,
                {},
            )
            payloads.setdefault(same_item_level_key, stat_payload)
    return payloads


def sync_observed_variant_stats_from_profile_presets(conn):
    ensure_websim_tables(conn)
    stat_payloads = profile_preset_observed_stat_payloads_by_identity(conn)
    counts = {
        "profilePresetStatPayloads": len(stat_payloads),
        "profilePresetObservedVariantsRefreshed": 0,
    }
    if not stat_payloads:
        return counts
    rows = conn.execute(
        """
        SELECT id, item_id, slot, item_level, simc_options_json, blockers_json, payload_json
        FROM websim_gear_variants
        WHERE source_type = 'observed_profile'
          AND status IN ('verified', 'partial')
        """
    ).fetchall()
    for row_id, item_id, slot, item_level, simc_options_json, blockers_json, payload_json in rows:
        payload = safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        if observed_variant_stat_payload_fields(payload):
            continue
        simc_options = safe_json_loads(simc_options_json, {})
        key = observed_variant_stat_identity_key(
            item_id,
            slot,
            item_level,
            simc_options,
        )
        stat_payload = stat_payloads.get(key)
        if not stat_payload and simc_options_allow_item_level_only_stat_fallback(simc_options):
            stat_payload = stat_payloads.get(observed_variant_stat_identity_key(item_id, slot, item_level, {}))
        if not stat_payload:
            stat_payload = stat_payloads.get(observed_variant_stat_identity_key(item_id, slot, item_level, {}))
        if not stat_payload:
            continue
        for failure_key in OBSERVED_VARIANT_SIMC_FAILURE_PAYLOAD_KEYS:
            payload.pop(failure_key, None)
        payload.update(stat_payload)
        blockers = [
            blocker
            for blocker in (safe_json_loads(blockers_json, []) or [])
            if str(blocker or "").strip() and str(blocker or "").strip() != MISSING_OBSERVED_SIMC_STATS_BLOCKER
        ]
        status = "partial" if blockers else "verified"
        conn.execute(
            """
            UPDATE websim_gear_variants
            SET status = ?, blockers_json = ?, payload_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, json.dumps(blockers, ensure_ascii=False), json.dumps(payload, ensure_ascii=False), utc_now(), row_id),
        )
        counts["profilePresetObservedVariantsRefreshed"] += 1
    return counts


def sync_observed_variant_stats_from_same_item_level_siblings(conn):
    ensure_websim_tables(conn)
    rows = conn.execute(
        """
        SELECT id, item_id, slot, item_level, blockers_json, payload_json
        FROM websim_gear_variants
        WHERE source_type = 'observed_profile'
          AND status IN ('verified', 'partial')
        ORDER BY item_id, slot, item_level DESC, id
        """
    ).fetchall()
    stat_payloads = {}
    for _row_id, item_id, slot, item_level, _blockers_json, payload_json in rows:
        stat_payload = observed_variant_stat_payload_fields(safe_json_loads(payload_json, {}))
        if not stat_payload:
            continue
        key = (str(item_id or ""), normalize_slot(slot), int(item_level or 0))
        stat_payloads.setdefault(key, stat_payload)
    counts = {
        "sameItemLevelObservedStatPayloads": len(stat_payloads),
        "sameItemLevelObservedVariantsRefreshed": 0,
    }
    if not stat_payloads:
        return counts
    for row_id, item_id, slot, item_level, blockers_json, payload_json in rows:
        payload = safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        if observed_variant_stat_payload_fields(payload):
            continue
        key = (str(item_id or ""), normalize_slot(slot), int(item_level or 0))
        stat_payload = stat_payloads.get(key)
        if not stat_payload:
            continue
        for failure_key in OBSERVED_VARIANT_SIMC_FAILURE_PAYLOAD_KEYS:
            payload.pop(failure_key, None)
        payload.update(stat_payload)
        blockers = [
            blocker
            for blocker in (safe_json_loads(blockers_json, []) or [])
            if str(blocker or "").strip() and str(blocker or "").strip() != MISSING_OBSERVED_SIMC_STATS_BLOCKER
        ]
        status = "partial" if blockers else "verified"
        conn.execute(
            """
            UPDATE websim_gear_variants
            SET status = ?, blockers_json = ?, payload_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, json.dumps(blockers, ensure_ascii=False), json.dumps(payload, ensure_ascii=False), utc_now(), row_id),
        )
        counts["sameItemLevelObservedVariantsRefreshed"] += 1
    return counts


def simc_options_allow_item_level_only_stat_fallback(options):
    options = options if isinstance(options, dict) else {}
    populated = {
        key
        for key, value in options.items()
        if key in SIMC_GEAR_OPTION_KEYS and normalize_option_value(value)
    }
    return populated.issubset({"bonus_id"})


def gear_item_level_payload(items):
    values = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        raw_value = item.get("ilevel") or item.get("itemLevel") or item.get("item_level")
        try:
            item_level = float(str(raw_value).strip())
        except (TypeError, ValueError):
            continue
        if item_level > 0:
            values.append(item_level)
    if not values:
        return {
            "key": "itemLevel",
            "label": "装备等级",
            "value": "0",
            "rawValue": 0,
            "selectedCount": 0,
            "source": "selected_gear",
        }
    average = sum(values) / len(values)
    rounded = int(round(average))
    return {
        "key": "itemLevel",
        "label": "装备等级",
        "value": str(rounded),
        "rawValue": rounded,
        "average": average,
        "selectedCount": len(values),
        "source": "selected_gear",
    }


def gear_readiness(items):
    ready_slots = {item["slot"] for item in items if item.get("simcReady")}
    warnings = []
    candidate_count = len([item for item in items if item and not item.get("simcReady")])
    missing_core_slots = [slot for slot in CORE_SIMC_GEAR_SLOTS if slot not in ready_slots]
    if candidate_count:
        warnings.append(f"{candidate_count} selected candidate item(s) are missing SimC fields and will not be written to the profile.")
    if not ready_slots:
        warnings.append("No SimC-ready gear selected; add a SimC preset item or enrich selected loot with item level and bonus/gem/enchant data.")
    if missing_core_slots:
        warnings.append(f"Missing core SimC gear slots: {', '.join(missing_core_slots)}.")
    return {
        "simcReadyCount": len(ready_slots),
        "selectedCount": len(items),
        "candidateCount": candidate_count,
        "missingRequiredSlots": [slot for slot in CANONICAL_GEAR_SLOTS if slot not in ready_slots],
        "missingCoreSlots": missing_core_slots,
        "requiredReadyCount": len(CORE_SIMC_GEAR_SLOTS),
        "fullReady": not missing_core_slots and candidate_count == 0,
        "itemLevel": gear_item_level_payload(items),
        "warnings": warnings,
    }


def gear_items_by_slot(items, class_key="", spec_key=""):
    result = {}
    for item in normalize_websim_gear_items(items or [], class_key, spec_key):
        if item.get("slot") and item["slot"] not in result:
            result[item["slot"]] = item
    return result


def gear_slot_readiness(items, class_key="", spec_key=""):
    by_slot = gear_items_by_slot(items, class_key, spec_key)
    readiness = {}
    for slot in CANONICAL_GEAR_SLOTS:
        item = by_slot.get(slot)
        if not item:
            readiness[slot] = {
                "slot": slot,
                "label": GEAR_SLOT_LABELS.get(slot, slot),
                "status": "blocked",
                "simcReady": False,
                "missingFields": ["item"],
                "reason": "missing item",
            }
            continue
        missing = item.get("missingFields") or []
        compatibility = item.get("compatibility") or "unknown"
        compatibility_status = compatibility.get("status") if isinstance(compatibility, dict) else compatibility
        if compatibility_status == "incompatible":
            status = "blocked"
            reason = "incompatible item"
        elif item.get("simcReady"):
            status = "verified"
            reason = "SimC-ready item"
        else:
            status = "partial"
            reason = f"missing {', '.join(missing)}" if missing else "missing SimC fields"
        readiness[slot] = {
            "slot": slot,
            "label": GEAR_SLOT_LABELS.get(slot, slot),
            "status": status,
            "simcReady": bool(item.get("simcReady")),
            "missingFields": missing,
            "reason": reason,
            "itemId": item.get("itemId") or item.get("id") or "",
        }
    return readiness


def blocked_stat_snapshot(blockers, *, class_key="", spec_key="", level=None, gear_readiness_payload=None, talent_encoding=None):
    item_level = (gear_readiness_payload or {}).get("itemLevel") or gear_item_level_payload([])
    return {
        "statStatus": "blocked",
        "classKey": class_key,
        "specKey": spec_key,
        "maxLevel": normalized_websim_level(level),
        "checkedAt": utc_now(),
        "blockers": [str(item) for item in blockers or [] if str(item or "").strip()],
        "primary": None,
        "stamina": None,
        "secondary": [],
        "armor": None,
        "weaponDps": None,
        "itemLevel": item_level,
        "gearReadiness": gear_readiness_payload or {},
        "talentEncoding": talent_encoding or blank_talent_encoding(),
        "gearSchemaRevision": GEAR_SCHEMA_REVISION,
    }


def simc_stat_value(output, names):
    text = str(output or "")
    for name in names:
        match = re.search(rf"\b{re.escape(name)}\b\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if match:
            return f"{float(match.group(1)):.3f}".rstrip("0").rstrip(".")
    return ""


def simc_stat_number(output, names):
    value = simc_stat_value(output, names)
    try:
        return float(value), value
    except (TypeError, ValueError):
        return 0.0, ""


def simc_snapshot_display_number(value, precision=0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "", None
    if not math.isfinite(number):
        return "", None
    if precision <= 0:
        return f"{int(round(number)):,}", number
    text = f"{round(number, precision):,.{precision}f}"
    text = text.rstrip("0").rstrip(".")
    return text, number


def simc_snapshot_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def simc_snapshot_display_max_number(values, precision=0):
    numbers = [number for number in (simc_snapshot_number(value) for value in values) if number is not None]
    if not numbers:
        return "", None
    return simc_snapshot_display_number(max(numbers), precision)


def simc_snapshot_percent_value(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "", None
    if not math.isfinite(number):
        return "", None
    percent = number * 100 if abs(number) <= 2 else number
    text = f"{round(percent, 1):.1f}".rstrip("0").rstrip(".")
    return f"{text}%", percent


def simc_snapshot_percent_display(percent):
    if percent is None or not math.isfinite(percent):
        return "", None
    text = f"{round(percent, 1):.1f}".rstrip("0").rstrip(".")
    return f"{text}%", percent


def simc_snapshot_percent_from_stats(stats, percent_keys, haste_multiplier_keys=None):
    candidates = []
    for percent_key in percent_keys or []:
        _, percent = simc_snapshot_percent_value(stats.get(percent_key))
        if percent is not None:
            candidates.append(percent)
    for haste_key in haste_multiplier_keys or []:
        multiplier = simc_snapshot_number(stats.get(haste_key))
        if multiplier and multiplier > 0:
            candidates.append((1 / multiplier - 1) * 100)
    if not candidates:
        return "", None
    return simc_snapshot_percent_display(max(candidates))


def simc_json_player(payload):
    if not isinstance(payload, dict):
        return {}
    candidates = []
    sim = payload.get("sim") if isinstance(payload.get("sim"), dict) else {}
    candidates.extend(sim.get("players") if isinstance(sim.get("players"), list) else [])
    candidates.extend(payload.get("players") if isinstance(payload.get("players"), list) else [])
    for player in candidates:
        if isinstance(player, dict):
            return player
    return {}


def simc_json_buffed_stats(player):
    collected = player.get("collected_data") if isinstance(player.get("collected_data"), dict) else {}
    buffed = collected.get("buffed_stats") if isinstance(collected.get("buffed_stats"), dict) else {}
    return (
        buffed.get("attribute") if isinstance(buffed.get("attribute"), dict) else {},
        buffed.get("stats") if isinstance(buffed.get("stats"), dict) else {},
    )


def parse_simcraft_json_stat_snapshot(payload):
    player = simc_json_player(payload)
    attributes, stats = simc_json_buffed_stats(player)
    if not player or not attributes or not stats:
        return blocked_stat_snapshot(["SimC JSON did not include a parseable buffed stat snapshot"])

    primary_candidates = [
        ("intellect", "智力"),
        ("strength", "力量"),
        ("agility", "敏捷"),
    ]
    primary = None
    positive_primary_values = []
    for key, label in primary_candidates:
        display, number = simc_snapshot_display_number(attributes.get(key), 0)
        if display and number and number > 0:
            positive_primary_values.append((number, key, label, display))
    if positive_primary_values:
        number, key, label, display = max(positive_primary_values, key=lambda item: item[0])
        primary = {"key": key, "label": label, "value": display, "rawValue": number}

    stamina_display, stamina_number = simc_snapshot_display_number(attributes.get("stamina"), 0)
    secondary = []
    for key, label, rating_keys, percent_keys, haste_multiplier_keys in [
        ("crit", "暴击", ["crit_rating", "melee_crit_rating", "spell_crit_rating"], ["crit_pct", "spell_crit", "attack_crit"], []),
        ("haste", "急速", ["haste_rating", "melee_haste_rating", "spell_haste_rating"], ["haste_pct"], ["attack_haste", "spell_haste"]),
        ("mastery", "精通", ["mastery_rating"], ["mastery_pct", "mastery_value"], []),
        ("versatility", "全能", ["versatility_rating"], ["versatility_pct", "damage_versatility"], []),
    ]:
        rating_display, rating_number = simc_snapshot_display_max_number([stats.get(rating_key) for rating_key in rating_keys], 0)
        percent_display, percent_number = simc_snapshot_percent_from_stats(stats, percent_keys, haste_multiplier_keys)
        if rating_display or percent_display:
            row = {
                "key": key,
                "label": label,
                "value": rating_display or "0",
                "rawValue": rating_number or 0,
                "statSource": "simulationcraft_json",
            }
            if percent_display:
                row["convertedValue"] = percent_display
                row["convertedRawValue"] = percent_number
                row["convertedSourceUnit"] = "percent"
            secondary.append(row)

    armor_display, armor_number = simc_snapshot_display_number(stats.get("armor"), 0)
    if not primary or not stamina_display or len(secondary) < 3:
        return blocked_stat_snapshot(["SimC JSON did not include a parseable stat snapshot"])
    gear_items = [
        item for item in (player.get("gear") or {}).values()
        if isinstance(item, dict)
    ] if isinstance(player.get("gear"), dict) else []
    return {
        "statStatus": "verified",
        "statSource": "simulationcraft_json",
        "simcVersion": str((payload or {}).get("version") or ""),
        "checkedAt": utc_now(),
        "blockers": [],
        "primary": primary,
        "stamina": {"key": "stamina", "label": "耐力", "value": stamina_display, "rawValue": stamina_number},
        "secondary": secondary,
        "armor": {"key": "armor", "label": "护甲", "value": armor_display, "rawValue": armor_number} if armor_display else None,
        "weaponDps": None,
        "itemLevel": gear_item_level_payload(gear_items),
        "gearSchemaRevision": GEAR_SCHEMA_REVISION,
    }


def parse_simcraft_stat_snapshot(output):
    primary_candidates = [
        ("intellect", "智力", ["intellect", "int"]),
        ("strength", "力量", ["strength", "str"]),
        ("agility", "敏捷", ["agility", "agi"]),
    ]
    primary = None
    primary_values = []
    for key, label, aliases in primary_candidates:
        number, value = simc_stat_number(output, aliases)
        if value:
            primary_values.append((number, key, label, value))
    positive_primary_values = [item for item in primary_values if item[0] > 0]
    if positive_primary_values:
        _, key, label, value = max(positive_primary_values, key=lambda item: item[0])
        primary = {"key": key, "label": label, "value": value}
    stamina_value = simc_stat_value(output, ["stamina", "sta"])
    secondary = []
    for key, label, aliases in [
        ("crit", "暴击", ["crit", "critical strike", "critical_strike"]),
        ("haste", "急速", ["haste"]),
        ("mastery", "精通", ["mastery"]),
        ("versatility", "全能", ["versatility", "vers"]),
    ]:
        value = simc_stat_value(output, aliases)
        if value:
            secondary.append({"key": key, "label": label, "value": value})
    armor_value = simc_stat_value(output, ["armor", "armour"])
    weapon_dps_value = simc_stat_value(output, ["weaponDps", "weapon dps", "weapon_dps"])
    if not primary or not stamina_value or len(secondary) < 4:
        return blocked_stat_snapshot(["SimC output did not include a parseable stat snapshot"])
    return {
        "statStatus": "verified",
        "checkedAt": utc_now(),
        "blockers": [],
        "primary": primary,
        "stamina": {"key": "stamina", "label": "耐力", "value": stamina_value},
        "secondary": secondary,
        "armor": {"key": "armor", "label": "护甲", "value": armor_value} if armor_value else None,
        "weaponDps": {"key": "weaponDps", "label": "武器 DPS", "value": weapon_dps_value} if weapon_dps_value else None,
        "gearSchemaRevision": GEAR_SCHEMA_REVISION,
    }


def websim_simc_binary():
    configured = os.environ.get("WOW_SIMC_BIN")
    if configured:
        return configured if os.path.exists(configured) else ""
    return shutil.which("simc") or shutil.which("simulationcraft") or ""


def websim_simc_blizzard_api_credentials():
    client_id = str(os.environ.get("WOW_BLIZZARD_CLIENT_ID") or os.environ.get("WOW_BNET_CLIENT_ID") or "").strip()
    client_secret = str(
        os.environ.get("WOW_BLIZZARD_CLIENT_SECRET") or os.environ.get("WOW_BNET_CLIENT_SECRET") or ""
    ).strip()
    if not client_id or not client_secret:
        return None
    return client_id, client_secret


def run_websim_simcraft_process(binary, profile, timeout_seconds):
    args = [binary, "-"]
    run_kwargs = {
        "input": profile,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "capture_output": True,
        "timeout": timeout_seconds,
        "check": False,
    }
    try:
        credentials = websim_simc_blizzard_api_credentials()
        if credentials:
            with tempfile.TemporaryDirectory(prefix="wow-websim-simc-home-") as simc_home:
                key_path = Path(simc_home) / ".simc_apikey"
                key_path.write_text(f"{credentials[0]}:{credentials[1]}\n", encoding="utf-8")
                key_path.chmod(0o600)
                return subprocess.run(args, env={**os.environ, "HOME": simc_home}, **run_kwargs)
        return subprocess.run(args, **run_kwargs)
    except OSError:
        fallback = run_windows_fake_simc_script(binary, profile)
        if fallback:
            return fallback
        raise


def simcraft_item_resolution_warnings(*texts):
    patterns = [
        "unable to download item id",
        "error retrieving item",
        "document is empty",
        "could not find item",
        "unknown item id",
        "invalid item id",
    ]
    warnings = []
    seen = set()
    for text in texts:
        for line in str(text or "").splitlines():
            stripped = line.strip()
            normalized = stripped.lower()
            if not stripped:
                continue
            if not any(pattern in normalized for pattern in patterns):
                continue
            if "item" not in normalized:
                continue
            if stripped in seen:
                continue
            seen.add(stripped)
            warnings.append(stripped[:400])
    return warnings[:8]


def simcraft_item_name_diagnostics(*texts):
    warnings = []
    seen = set()
    for text in texts:
        for line in str(text or "").splitlines():
            stripped = line.strip()
            normalized = stripped.lower()
            if not stripped:
                continue
            if not normalized.startswith("trivial: player "):
                continue
            if "has inconsistency between name" not in normalized or " for id " not in normalized:
                continue
            if stripped in seen:
                continue
            seen.add(stripped)
            warnings.append(stripped[:400])
    return warnings[:8]


def simcraft_only_item_name_diagnostics(text):
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return False
    diagnostics = simcraft_item_name_diagnostics(text)
    return len(diagnostics) == len(lines)


SIMCRAFT_STAT_SNAPSHOT_CRASH_MESSAGE = "SimC 属性计算崩溃：当前组合暂时无法完成装备属性校验，请稍后重试，或更换天赋、装备或场景。"
SIMCRAFT_UNHOLY_RIDER_CRASH_BLOCKER = (
    "当前 SimC 版本对“邪恶死亡骑士 + 天启骑士”组合存在已知崩溃问题，"
    "暂不能校验或提交；请改用其他英雄天赋，或等待 SimC 上游修复后重新校验。"
)


def simcraft_process_crashed(*texts):
    text = "\n".join(str(item or "") for item in texts)
    return bool(re.search(r"sim_signal_handler|segmentation fault|\bsigsegv\b|\bsignal\s*11\b", text, re.IGNORECASE))


def simcraft_stat_snapshot_error_message(*texts):
    if simcraft_process_crashed(*texts):
        return SIMCRAFT_STAT_SNAPSHOT_CRASH_MESSAGE
    return ""


def simcraft_known_compatibility_blockers(class_key, spec_key, hero_key="", scenario_key=""):
    normalized_class = slugify(class_key, "")
    normalized_spec = slugify(spec_key, "")
    requested_hero = slugify(hero_key, "")
    if not requested_hero:
        return []
    normalized_hero = hero_tree_for(normalized_class, normalized_spec, requested_hero)
    if (
        normalized_class == "deathknight"
        and normalized_spec == "unholy"
        and normalized_hero == "rider_of_the_apocalypse"
    ):
        return [SIMCRAFT_UNHOLY_RIDER_CRASH_BLOCKER]
    return []


def run_windows_fake_simc_script(binary, profile):
    if os.name != "nt":
        return None
    try:
        script = Path(binary).read_text(encoding="utf-8")
    except OSError:
        return None
    first_line = script.splitlines()[0].strip().lower() if script.splitlines() else ""
    if first_line.startswith("#!") and "python" in first_line:
        return subprocess.run(
            [sys.executable, binary, "-"],
            input=profile,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
    if not script.startswith("#!/bin/sh"):
        return None

    stdout = []
    stderr = []
    returncode = 0
    for line in script.splitlines():
        stripped = line.strip()
        if stripped.startswith("cat >"):
            capture_target = stripped.split(">", 1)[1].strip()
            if capture_target and capture_target != "/dev/null":
                Path(capture_target).write_text(profile, encoding="utf-8")
            continue
        if stripped.startswith("printf "):
            match = re.match(r"printf\s+(['\"])(.*?)\1(?:\s+>&2)?\s*$", stripped)
            if match:
                try:
                    text = ast.literal_eval(f"{match.group(1)}{match.group(2)}{match.group(1)}")
                except (SyntaxError, ValueError):
                    text = match.group(2)
                (stderr if stripped.endswith(">&2") else stdout).append(text)
            continue
        if stripped.startswith("python3 - <<"):
            code = script.split(stripped, 1)[1].split("\nPY", 1)[0].lstrip("\n")
            completed = subprocess.run(
                [sys.executable, "-c", code],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
            )
            stdout.append(completed.stdout or "")
            stderr.append(completed.stderr or "")
            returncode = completed.returncode
            continue
        if stripped.startswith("exit "):
            try:
                returncode = int(stripped.split(None, 1)[1])
            except (IndexError, ValueError):
                returncode = 1

    return subprocess.CompletedProcess([binary, "-"], returncode, "".join(stdout), "".join(stderr))


def run_websim_stat_simcraft(profile):
    binary = websim_simc_binary()
    if not binary:
        return {"ran": False, "available": False, "summary": "", "error": "simcraft binary not found"}
    if not str(profile or "").strip():
        return {"ran": False, "available": True, "summary": "", "error": "empty profile"}
    with tempfile.TemporaryDirectory(prefix="wow-websim-gear-stats-") as tmp_dir:
        output_path = Path(tmp_dir) / "gear-stats.json"
        profile_text = profile_with_simc_json_output(profile, output_path)
        try:
            result = run_websim_simcraft_process(
                binary,
                profile_text,
                int_env("WOW_WEBSIM_GEAR_STATS_TIMEOUT_SECONDS", 45),
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return {"ran": False, "available": True, "summary": "", "error": str(error)}
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        output = "\n".join(item for item in [stdout.strip(), stderr.strip()] if item).strip()
        json_payload = None
        json_error = ""
        if output_path.exists():
            try:
                json_payload = json.loads(output_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                json_error = f"invalid simc json output: {error}"
        return {
            "ran": result.returncode == 0,
            "available": True,
            "rawOutput": output,
            "stdout": stdout[:4000],
            "stderr": stderr[:4000],
            "jsonPayload": json_payload,
            "jsonError": json_error,
            "itemResolutionWarnings": simcraft_item_resolution_warnings(stdout, stderr),
            "itemNameDiagnostics": simcraft_item_name_diagnostics(stdout, stderr),
            "summary": output[:4000],
            "error": ""
            if result.returncode == 0
            else (
                simcraft_stat_snapshot_error_message(stderr, stdout)
                or (stderr or stdout or f"simc exited {result.returncode}")[:1000]
            ),
        }


def profile_with_simc_json_output(profile, output_path):
    lines = [
        line
        for line in str(profile or "").splitlines()
        if not re.match(r"^\s*json\s*=", line, re.IGNORECASE)
    ]
    lines.append(f"json={output_path}")
    return "\n".join(lines).strip() + "\n"


def run_websim_profile_preset_simc_json(profile):
    checked_at = utc_now()
    binary = websim_simc_binary()
    if not binary:
        return {"ok": False, "available": False, "checkedAt": checked_at, "error": "simcraft binary not found"}
    if not str(profile or "").strip():
        return {"ok": False, "available": True, "checkedAt": checked_at, "error": "empty profile"}
    timeout_seconds = int_env("WOW_WEBSIM_PROFILE_JSON_TIMEOUT_SECONDS", 45)
    with tempfile.TemporaryDirectory(prefix="wow-websim-simc-json-") as tmp_dir:
        output_path = Path(tmp_dir) / "profile.json"
        profile_text = profile_with_simc_json_output(profile, output_path)
        started = time.monotonic()
        try:
            result = run_websim_simcraft_process(binary, profile_text, timeout_seconds)
        except (OSError, subprocess.TimeoutExpired) as error:
            return {
                "ok": False,
                "available": True,
                "checkedAt": checked_at,
                "durationMs": int((time.monotonic() - started) * 1000),
                "error": str(error),
            }
        duration_ms = int((time.monotonic() - started) * 1000)
        if result.returncode != 0:
            return {
                "ok": False,
                "available": True,
                "checkedAt": checked_at,
                "durationMs": duration_ms,
                "error": (result.stderr or result.stdout or f"simc exited {result.returncode}")[:1000],
            }
        if not output_path.exists():
            return {
                "ok": False,
                "available": True,
                "checkedAt": checked_at,
                "durationMs": duration_ms,
                "error": "simc did not write json output",
                "summary": (result.stdout or result.stderr or "")[:1000],
            }
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            return {
                "ok": False,
                "available": True,
                "checkedAt": checked_at,
                "durationMs": duration_ms,
                "error": f"invalid simc json output: {error}",
            }
        return {
            "ok": True,
            "available": True,
            "checkedAt": checked_at,
            "durationMs": duration_ms,
            "payload": payload,
        }


def backfill_profile_preset_simc_json(conn, class_key="", spec_key="", limit=0, force=False):
    ensure_websim_tables(conn)
    filters = []
    params = []
    class_key = slugify(class_key, "")
    spec_key = slugify(spec_key, "")
    if class_key:
        filters.append("class_key = ?")
        params.append(class_key)
    if spec_key:
        filters.append("spec_key = ?")
        params.append(spec_key)
    where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = conn.execute(
        f"""
        SELECT id, class_key, spec_key, name, profile, payload_json
        FROM websim_profile_presets
        {where_sql}
        ORDER BY class_key, spec_key, id
        """,
        params,
    ).fetchall()
    max_checked = int(limit or 0)
    counts = {
        "checked": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
        "available": bool(websim_simc_binary()),
    }
    updates = []
    for preset_id, _class_key, _spec_key, _name, profile, payload_json in rows:
        payload = safe_json_loads(payload_json, {})
        if not isinstance(payload, dict):
            payload = {}
        if not force and any(payload.get(key) for key in ("simcJson", "simcGearJson", "simulationcraftJson", "simcOutput", "simcGear")):
            counts["skipped"] += 1
            continue
        if max_checked > 0 and counts["checked"] >= max_checked:
            counts["skipped"] += 1
            continue
        counts["checked"] += 1
        result = run_websim_profile_preset_simc_json(profile)
        checked_at = result.get("checkedAt") or utc_now()
        payload["simcStatCheckedAt"] = checked_at
        payload["simcStatSource"] = "simulationcraft"
        if result.get("ok"):
            payload["simcJson"] = result.get("payload") or {}
            payload["simcStatDurationMs"] = result.get("durationMs", 0)
            payload.pop("simcStatErrors", None)
            counts["updated"] += 1
        else:
            payload["simcStatErrors"] = [str(result.get("error") or "simc json backfill failed")[:1000]]
            counts["errors"] += 1
        updates.append((json.dumps(payload, ensure_ascii=False), checked_at, preset_id))
    for update_payload, checked_at, preset_id in updates:
        conn.execute(
            """
            UPDATE websim_profile_presets
            SET payload_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (update_payload, checked_at, preset_id),
        )
    return counts


def selected_scenario(value):
    key = str(value or "").strip()
    for scenario in SCENARIOS:
        if scenario["key"] == key:
            return scenario
    return SCENARIOS[0]


def class_label(class_key):
    key = slugify(class_key, "")
    return CLASS_LABELS_ZH.get(key) or next(
        (item.get("label") for item in WOW_CLASSES if item.get("key") == key),
        key.replace("_", " ").title(),
    )


def spec_label(spec_key):
    key = slugify(spec_key, "")
    return SPEC_LABELS_ZH.get(key) or SPEC_LABELS.get(key, key.replace("_", " ").title())


def scenario_title(scenario_key):
    key = slugify(scenario_key, "mythic_plus")
    scenario = next((item for item in SCENARIOS if item.get("key") == key), None)
    return (scenario or {}).get("title") or key.replace("_", " ").title()


def blank_talent_encoding(status="skipped", source="none"):
    return {
        "status": status,
        "source": source,
        "schemaRevision": TALENT_SCHEMA_REVISION,
        "errors": [],
        "warnings": [],
        "lines": [],
        "selectedCounts": {"class": 0, "spec": 0, "hero": 0},
    }


def websim_selected_talent_nodes(payload):
    if not isinstance(payload, dict):
        return []
    talent_state = payload.get("talentState") if isinstance(payload.get("talentState"), dict) else {}
    selected_nodes = talent_state.get("selectedNodes")
    if not isinstance(selected_nodes, list):
        return []
    normalized = []
    for item in selected_nodes:
        if isinstance(item, dict):
            node_id = str(item.get("id") or "").strip()
            raw_rank = item.get("rank")
        else:
            node_id = str(item or "").strip()
            raw_rank = 1
        if not node_id:
            continue
        try:
            rank = int(raw_rank)
        except (TypeError, ValueError):
            rank = 0
        normalized.append({"id": node_id, "rank": max(0, rank)})
    return normalized[:400]


def external_talent_import_code(payload):
    if not isinstance(payload, dict):
        return ""
    value = str(payload.get("talents") or payload.get("talentImport") or "").strip()
    if not value or value.startswith("websim:"):
        return ""
    if value.startswith("talents="):
        value = value.split("=", 1)[1].strip()
    if value.startswith("websim:"):
        return ""
    return normalize_option_value(value)


def parse_websim_talent_export_code(value):
    text = str(value or "").strip()
    if text.startswith("talents="):
        text = text.split("=", 1)[1].strip()
    if not text.startswith("websim:"):
        return None
    parts = text.split(":")
    if len(parts) < 5:
        return None
    rank_payload = ":".join(parts[4:]).split(";", 1)[0]
    selected_nodes = []
    for entry in rank_payload.split(","):
        if not entry:
            continue
        node_id, _, raw_rank = entry.partition(":")
        node_id = node_id.strip()
        if not node_id:
            continue
        try:
            rank = int(raw_rank or 1)
        except (TypeError, ValueError):
            rank = 1
        selected_nodes.append({"id": node_id, "rank": max(1, rank)})
    return {
        "classKey": parts[1] or "",
        "specKey": parts[2] or "",
        "heroKey": parts[3] or "",
        "talentState": {"selectedNodes": selected_nodes},
    }


def build_websim_talent_export_code(payload):
    source = payload if isinstance(payload, dict) else {}
    parsed = parse_websim_talent_export_code(source.get("websimExportCode") or source.get("talents") or "")
    if parsed:
        return str(source.get("websimExportCode") or source.get("talents") or "").replace("talents=", "", 1).strip()
    class_key = slugify(source.get("classKey"), "mage")
    spec_key = slugify(source.get("specKey"), "arcane")
    hero_key = hero_tree_for(class_key, spec_key, slugify(source.get("heroKey"), ""))
    entries = sorted(
        websim_selected_talent_nodes(source),
        key=lambda item: item["id"],
    )
    rank_payload = ",".join(f"{item['id']}:{max(1, int(item.get('rank') or 1))}" for item in entries if item.get("rank", 0) > 0)
    return f"websim:{class_key}:{spec_key}:{hero_key}:{rank_payload}"


def websim_tree_line_key(tree_type):
    return {
        "class": "class_talents",
        "spec": "spec_talents",
        "hero": "hero_talents",
    }.get(str(tree_type or ""))


def websim_node_entry_id(node):
    for key in ("traitId", "entryId", "entryID"):
        try:
            value = int(node.get(key) or 0)
        except (AttributeError, TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    for entry in node.get("rankEntries") or []:
        try:
            value = int(entry.get("traitId") or entry.get("entryId") or 0)
        except (AttributeError, TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    return 0


def websim_parent_mode(node):
    try:
        value = str(node.get("parentMode") or "").strip().lower()
    except AttributeError:
        value = ""
    return "all" if value == "all" else "any"


def build_websim_authority_nodes(conn, class_key, spec_key, hero_key):
    if hasattr(conn, "get_websim_talents"):
        payload = conn.get_websim_talents(class_key, spec_key, hero_key)
    else:
        payload = get_websim_talents(conn, class_key, spec_key, hero_key)
    nodes = payload.get("nodes") or []
    return payload, {str(node.get("id") or ""): node for node in nodes if node.get("id")}


def talent_dependency_source(nodes):
    sources = sorted({
        str(node.get("dependencySource") or "").strip()
        for node in nodes or []
        if str(node.get("dependencySource") or "").strip()
    })
    return ", ".join(sources)


def talent_authority_payload(conn, talent_status, season, nodes):
    sync_state = get_sync_state(conn, "websim_sync") or {}
    simc_state = sync_state.get("simc") if isinstance(sync_state.get("simc"), dict) else {}
    runtime_source = "fallback" if talent_status == "fallback" else ("simc" if talent_status in {"simc", "verified"} else str(talent_status or "unknown"))
    official_configured = blizzard_credentials_configured()
    official_status = "pending_audit" if official_configured else "not_configured"
    if talent_status == "fallback":
        diff_status = "blocked"
    elif official_status == "not_configured":
        diff_status = "pending_official_audit"
    else:
        diff_status = "verified" if talent_status == "verified" else "pending_official_audit"
    trait_edge_source = str(simc_state.get("traitEdgeSource") or "").strip() or talent_dependency_source(nodes)
    return {
        "schemaRevision": TALENT_SCHEMA_REVISION,
        "runtimeSource": runtime_source,
        "diffStatus": diff_status,
        "checkedAt": sync_state.get("checkedAt") or utc_now(),
        "runtime": {
            "status": talent_status,
            "source": runtime_source,
            "simcBuild": simc_state.get("build") or "",
            "traitEdgeSource": trait_edge_source,
            "nodeCount": len(nodes or []),
        },
        "official": {
            "status": official_status,
            "revision": (season.get("seasonRevision") or season.get("revision") or "") if official_configured else "",
            "source": "blizzard-game-data-api",
        },
    }


def validate_websim_talent_selection(nodes_by_id, selected_rows, tree_sections):
    errors = []
    warnings = []
    selected_by_id = {}
    for row in selected_rows:
        node_id = row["id"]
        if node_id not in nodes_by_id:
            errors.append(f"unknown talent node: {node_id}")
            continue
        selected_by_id[node_id] = max(selected_by_id.get(node_id, 0), row["rank"])

    active_counts = {"class": 0, "spec": 0, "hero": 0}
    purchased_counts = {"class": 0, "spec": 0, "hero": 0}
    selected_choice_groups = {}
    encoded = {"class": [], "spec": [], "hero": []}

    for node_id, selected_rank in selected_by_id.items():
        node = nodes_by_id[node_id]
        tree_type = node.get("treeType") or ("class" if node.get("specKey") == "class" else "spec")
        max_rank = max(1, int(node.get("maxRank") or node.get("rank") or 1))
        granted_rank = max(0, min(max_rank, int(node.get("grantedRank") or 0)))
        if selected_rank < granted_rank:
            errors.append(f"talent rank below granted floor: {node_id}")
            selected_rank = granted_rank
        if selected_rank > max_rank:
            errors.append(f"talent rank exceeds max rank: {node_id}")
            selected_rank = max_rank
        active_counts[tree_type] = active_counts.get(tree_type, 0) + selected_rank
        purchased_rank = max(0, selected_rank - granted_rank)
        if purchased_rank <= 0:
            continue
        entry_id = websim_node_entry_id(node)
        if entry_id <= 0:
            errors.append(f"talent node has no SimC entry id: {node_id}")
            continue
        if not websim_tree_line_key(tree_type):
            errors.append(f"unsupported talent tree type: {node_id}")
            continue
        purchased_counts[tree_type] = purchased_counts.get(tree_type, 0) + purchased_rank
        encoded[tree_type].append({
            "nodeId": node_id,
            "entryId": entry_id,
            "rank": purchased_rank,
            "row": int(node.get("row") or 0),
            "col": int(node.get("col") or 0),
            "selectionIndex": int(node.get("selectionIndex") or 0),
        })
        choice_group = str(node.get("choiceGroup") or "")
        if choice_group:
            selected_choice_groups.setdefault((tree_type, choice_group), []).append(node_id)

    for (_tree_type, choice_group), node_ids in selected_choice_groups.items():
        if len(node_ids) > 1:
            errors.append(f"multiple talents selected in choice group {choice_group}: {', '.join(node_ids)}")

    for node_id, selected_rank in selected_by_id.items():
        if selected_rank <= 0:
            continue
        node = nodes_by_id[node_id]
        max_rank = max(1, int(node.get("maxRank") or node.get("rank") or 1))
        granted_rank = max(0, min(max_rank, int(node.get("grantedRank") or 0)))
        if selected_rank <= granted_rank:
            continue
        parent_ids = [parent_id for parent_id in node.get("parentIds") or [] if parent_id in nodes_by_id]
        if parent_ids:
            selected_parent_ids = [parent_id for parent_id in parent_ids if selected_by_id.get(parent_id, 0) > 0]
            if websim_parent_mode(node) == "all":
                missing_parent_ids = [parent_id for parent_id in parent_ids if parent_id not in selected_parent_ids]
                if missing_parent_ids:
                    errors.append(f"missing parent talent for {node_id}: {', '.join(missing_parent_ids)}")
            elif not selected_parent_ids:
                errors.append(f"missing parent talent for {node_id}")
        requirement = max(0, int(node.get("pointRequirement") or 0))
        tree_type = node.get("treeType") or ("class" if node.get("specKey") == "class" else "spec")
        purchased_rank = max(0, selected_rank - granted_rank)
        gate_counts = active_counts if tree_type == "hero" else purchased_counts
        gate_rank = selected_rank if tree_type == "hero" else purchased_rank
        points_before_node = gate_counts.get(tree_type, 0) - gate_rank
        if requirement and points_before_node < requirement:
            errors.append(f"talent point gate not satisfied for {node_id}: requires {requirement}")

    point_caps = {}
    for section in tree_sections or []:
        key = section.get("key")
        try:
            cap = int(section.get("pointCap") or 0)
        except (AttributeError, TypeError, ValueError):
            cap = 0
        if key and cap > 0:
            point_caps[key] = cap
    for tree_type, points in purchased_counts.items():
        if point_caps.get(tree_type) and points > point_caps[tree_type]:
            errors.append(f"{tree_type} talent points exceed cap: {points}/{point_caps[tree_type]}")

    return encoded, purchased_counts, errors, warnings


def encode_websim_talents(conn, payload):
    source = payload if isinstance(payload, dict) else {}
    selected_rows = websim_selected_talent_nodes(source)
    encoding = blank_talent_encoding()
    external_code = external_talent_import_code(source)
    if not selected_rows:
        parsed_export = parse_websim_talent_export_code(
            source.get("websimExportCode") or source.get("talents") or source.get("talentImport") or ""
        )
        if parsed_export:
            source = {
                **source,
                "classKey": source.get("classKey") or parsed_export.get("classKey") or "",
                "specKey": source.get("specKey") or parsed_export.get("specKey") or "",
                "heroKey": source.get("heroKey") or parsed_export.get("heroKey") or "",
                "talentState": parsed_export.get("talentState") or {},
            }
            selected_rows = websim_selected_talent_nodes(source)
    if not selected_rows:
        if external_code:
            encoding.update({
                "status": "external",
                "source": "talents",
                "lines": [f"talents={external_code}"],
            })
        else:
            encoding["status"] = "failed"
            encoding["errors"].append("no WebSim talent nodes selected")
        return encoding

    class_key = slugify(source.get("classKey"), "mage")
    spec_key = slugify(source.get("specKey"), "arcane")
    hero_key = hero_tree_for(class_key, spec_key, slugify(source.get("heroKey"), ""))
    encoding.update({"classKey": class_key, "specKey": spec_key, "heroKey": hero_key})
    talent_payload, nodes_by_id = build_websim_authority_nodes(conn, class_key, spec_key, hero_key)
    encoding["source"] = talent_payload.get("talentStatus") or "unknown"
    if talent_payload.get("talentStatus") == "fallback":
        encoding["status"] = "failed"
        encoding["errors"].append("WebSim talent cache is fallback; sync SimulationCraft talent data before running SimC")
        return encoding

    encoded, selected_counts, errors, warnings = validate_websim_talent_selection(
        nodes_by_id,
        selected_rows,
        talent_payload.get("treeSections") or talent_tree_sections(class_key, spec_key, hero_key),
    )
    encoding["errors"].extend(errors)
    encoding["warnings"].extend(warnings)
    encoding["selectedCounts"] = selected_counts
    if encoding["errors"]:
        encoding["status"] = "failed"
        return encoding

    lines = []
    for tree_type in ("class", "spec", "hero"):
        entries = sorted(
            encoded.get(tree_type) or [],
            key=lambda item: (item["row"], item["col"], item["selectionIndex"], item["entryId"]),
        )
        if not entries:
            continue
        lines.append(f"{websim_tree_line_key(tree_type)}=" + "/".join(f"{item['entryId']}:{item['rank']}" for item in entries))
    if not lines:
        encoding["status"] = "failed"
        encoding["errors"].append("selected WebSim talents did not produce any purchasable SimC talent entries")
        return encoding
    encoding["status"] = "encoded"
    encoding["lines"] = lines
    return encoding


def validate_talent_api_payload(conn, payload):
    source = payload if isinstance(payload, dict) else {}
    parsed = parse_websim_talent_export_code(source.get("code") or source.get("talents") or source.get("websimExportCode") or "")
    request_payload = {**source, **parsed} if parsed else dict(source)
    class_key = slugify(request_payload.get("classKey"), "mage")
    spec_key = slugify(request_payload.get("specKey"), "arcane")
    hero_key = hero_tree_for(class_key, spec_key, slugify(request_payload.get("heroKey"), ""))
    request_payload.update({"classKey": class_key, "specKey": spec_key, "heroKey": hero_key})
    if hasattr(conn, "get_websim_talents"):
        talent_payload = conn.get_websim_talents(class_key, spec_key, hero_key)
    else:
        talent_payload = get_websim_talents(conn, class_key, spec_key, hero_key)
    encoding = encode_websim_talents(conn, request_payload)
    return {
        **encoding,
        "classKey": class_key,
        "specKey": spec_key,
        "heroKey": hero_key,
        "talentState": {"selectedNodes": websim_selected_talent_nodes(request_payload)},
        "talentSchemaRevision": TALENT_SCHEMA_REVISION,
        "talentAuthority": talent_payload.get("talentAuthority"),
        "talentReadiness": talent_payload.get("talentReadiness"),
        "blockers": talent_payload.get("blockers") or [],
    }


def export_talent_api_payload(conn, payload):
    source = payload if isinstance(payload, dict) else {}
    validation = validate_talent_api_payload(conn, source)
    export_source = {
        **source,
        "classKey": validation["classKey"],
        "specKey": validation["specKey"],
        "heroKey": validation["heroKey"],
        "talentState": validation["talentState"],
    }
    return {
        "classKey": validation["classKey"],
        "specKey": validation["specKey"],
        "heroKey": validation["heroKey"],
        "talentState": validation["talentState"],
        "websimExportCode": build_websim_talent_export_code(export_source),
        "validation": validation,
        "talentSchemaRevision": TALENT_SCHEMA_REVISION,
    }


def import_talent_api_payload(conn, payload):
    source = payload if isinstance(payload, dict) else {}
    code = source.get("code") or source.get("talents") or source.get("websimExportCode") or ""
    parsed = parse_websim_talent_export_code(code)
    if parsed:
        validation = validate_talent_api_payload(conn, parsed)
        return {
            **parsed,
            "validation": validation,
            "talentSchemaRevision": TALENT_SCHEMA_REVISION,
        }
    raw_import_code = external_talent_import_code({"talents": code})
    return {
        "classKey": slugify(source.get("classKey"), ""),
        "specKey": slugify(source.get("specKey"), ""),
        "heroKey": slugify(source.get("heroKey"), ""),
        "rawImportCode": raw_import_code,
        "talentState": {"selectedNodes": []},
        "validation": validate_talent_api_payload(conn, {"talents": raw_import_code} if raw_import_code else {}),
        "talentSchemaRevision": TALENT_SCHEMA_REVISION,
    }


def parse_websim_gear_enhancement_snapshot(value):
    if isinstance(value, dict):
        snapshot = value
    elif isinstance(value, str) and value.strip().startswith("{"):
        snapshot = safe_json_loads(value, {})
    else:
        snapshot = {}
    if not isinstance(snapshot, dict):
        return {}
    if not isinstance(snapshot.get("gearBySlot"), dict) and not isinstance(snapshot.get("enhancementBySlot"), dict):
        return {}
    return snapshot


def websim_gear_enhancement_snapshot_from_source(source):
    source = source if isinstance(source, dict) else {}
    gear_selection = source.get("gearSelection") if isinstance(source.get("gearSelection"), dict) else {}
    metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
    candidates = [
        source.get("gearSnapshot"),
        source.get("snapshot"),
        source.get("rawString"),
        gear_selection.get("gearSnapshot"),
        gear_selection.get("snapshot"),
        gear_selection.get("rawString"),
        metadata.get("gearSnapshot"),
    ]
    for candidate in candidates:
        snapshot = parse_websim_gear_enhancement_snapshot(candidate)
        if snapshot:
            return snapshot
    return {}


def ordered_gear_snapshot_items(gear_by_slot):
    if not isinstance(gear_by_slot, dict):
        return []
    items = []
    seen = set()
    for slot in CANONICAL_GEAR_SLOTS:
        item = gear_by_slot.get(slot)
        if isinstance(item, dict):
            items.append({**item, "slot": item.get("slot") or slot, "simcSlot": item.get("simcSlot") or slot})
            seen.add(slot)
    for slot, item in gear_by_slot.items():
        normalized_slot = normalize_slot(slot)
        if normalized_slot in seen or not isinstance(item, dict):
            continue
        items.append({**item, "slot": item.get("slot") or normalized_slot or slot, "simcSlot": item.get("simcSlot") or normalized_slot or slot})
    return items


def websim_gear_items_and_enhancements_from_source(source):
    source = source if isinstance(source, dict) else {}
    snapshot = websim_gear_enhancement_snapshot_from_source(source)
    if snapshot:
        return ordered_gear_snapshot_items(snapshot.get("gearBySlot") or {}), snapshot.get("enhancementBySlot") or {}
    gear_selection = source.get("gearSelection") if isinstance(source.get("gearSelection"), dict) else {}
    raw_items = gear_selection.get("items") or source.get("gearItems") or source.get("simcGearItems") or []
    raw_enhancements = (
        source.get("enhancementBySlot")
        or gear_selection.get("enhancementBySlot")
        or source.get("enhancementsBySlot")
        or gear_selection.get("enhancementsBySlot")
        or {}
    )
    return raw_items, raw_enhancements


def normalize_enhancement_record(record):
    if not isinstance(record, dict):
        return {}
    aliases = {
        "gem_id": ("gem_id", "gemId"),
        "gem_bonus_id": ("gem_bonus_id", "gemBonusId"),
        "gem_ilevel": ("gem_ilevel", "gemIlevel", "gemItemLevel"),
        "enchant_id": ("enchant_id", "enchantId"),
        "embellishment": ("embellishment", "embellishmentId", "embellishment_id"),
        "socketOptionId": ("socketOptionId", "socket_option_id"),
        "enchantOptionId": ("enchantOptionId", "enchant_option_id"),
        "embellishmentOptionId": ("embellishmentOptionId", "embellishment_option_id"),
    }
    normalized = {}
    for key, names in aliases.items():
        for name in names:
            value = normalize_option_value(record.get(name))
            if value:
                normalized[key] = value
                break
    return normalized


def normalize_enhancement_by_slot(raw_enhancements):
    normalized = {}
    if not isinstance(raw_enhancements, dict):
        return normalized
    for raw_slot, record in raw_enhancements.items():
        slot = normalize_slot(raw_slot)
        enhancement = normalize_enhancement_record(record)
        if slot and enhancement:
            normalized[slot] = enhancement
    return normalized


def item_builtin_embellishment_value(item):
    if not isinstance(item, dict):
        return ""
    if item.get("hasBuiltInEmbellishment"):
        return normalize_option_value(
            item.get("builtInEmbellishment")
            or item.get("intrinsicEmbellishment")
            or item.get("inherentEmbellishment")
            or BUILT_IN_EMBELLISHMENT_VALUE
        )
    for key in ("builtInEmbellishment", "intrinsicEmbellishment", "inherentEmbellishment"):
        value = normalize_option_value(item.get(key))
        if value:
            return value
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    payload_builtin_embellishment = built_in_embellishment_fields_from_payload(payload)
    if payload_builtin_embellishment:
        return payload_builtin_embellishment["builtInEmbellishment"]
    for key in ("builtInEmbellishment", "intrinsicEmbellishment", "inherentEmbellishment"):
        value = normalize_option_value(payload.get(key))
        if value:
            return value
    if str(item.get("embellishmentSource") or "").strip().lower() in {"built_in", "builtin", "intrinsic", "item"}:
        return normalize_option_value(item.get("embellishment"))
    return normalize_option_value(item.get("embellishment"))


def enhancement_options_for_type(item, option_type):
    if option_type == "socket":
        return item.get("socketOptions") or []
    if option_type == "enchant":
        return item.get("enchantOptions") or []
    if option_type == "embellishment":
        return item.get("embellishmentOptions") or []
    return []


def enhancement_option_payload(option):
    if not isinstance(option, dict):
        return {}
    payload = option.get("payload")
    return payload if isinstance(payload, dict) else {}


def enhancement_option_first_value(option, keys):
    if not isinstance(keys, (list, tuple)):
        keys = [keys]
    payload = enhancement_option_payload(option)
    for source in (option if isinstance(option, dict) else {}, payload):
        for key in keys:
            value = source.get(key)
            if value not in (None, "", [], {}):
                return value
    return None


def socket_option_gem_ids(option):
    if not isinstance(option, dict):
        return []
    simc_options = option.get("simcOptions") if isinstance(option.get("simcOptions"), dict) else {}
    gem_ids = gem_item_ids_from_simc_options(simc_options)
    if gem_ids:
        return gem_ids
    value = normalize_option_value(
        option.get("gemItemId")
        or option.get("gem_item_id")
        or enhancement_option_payload(option).get("gemItemId")
        or enhancement_option_payload(option).get("gem_item_id")
    )
    return [value] if value else []


def enhancement_option_unique_group(option, option_type):
    group = normalize_option_value(
        enhancement_option_first_value(option, ("uniqueGroup", "unique_group", "uniqueKey", "unique_key"))
    )
    if group:
        return group
    if option_type == "socket" and any(gem_id in PRIMARY_STAT_GEM_IDS for gem_id in socket_option_gem_ids(option)):
        return PRIMARY_STAT_GEM_UNIQUE_GROUP
    return ""


def enhancement_option_unique_limit(option, option_type):
    raw_limit = enhancement_option_first_value(option, ("uniqueLimit", "unique_limit", "uniqueEquippedLimit", "unique_equipped_limit"))
    if raw_limit not in (None, "", [], {}):
        try:
            limit = int(raw_limit)
            if limit > 0:
                return limit
        except (TypeError, ValueError):
            pass
    if enhancement_option_unique_group(option, option_type):
        return 1
    return 0


def enhancement_option_matches(option, enhancement, option_type):
    if not isinstance(option, dict):
        return False
    if str(option.get("status") or "verified").strip().lower() != "verified":
        return False
    if not gear_mod_option_has_supported_quality(option_type, option):
        return False
    option_id = normalize_option_value(option.get("id"))
    if option_type == "socket" and enhancement.get("socketOptionId") and option_id == enhancement.get("socketOptionId"):
        return True
    if option_type == "enchant" and enhancement.get("enchantOptionId") and option_id == enhancement.get("enchantOptionId"):
        return True
    if option_type == "embellishment" and enhancement.get("embellishmentOptionId") and option_id == enhancement.get("embellishmentOptionId"):
        return True
    simc_options = option.get("simcOptions") if isinstance(option.get("simcOptions"), dict) else {}
    if option_type == "socket":
        return bool(enhancement.get("gem_id") and normalize_option_value(simc_options.get("gem_id")) == enhancement.get("gem_id"))
    if option_type == "enchant":
        return bool(enhancement.get("enchant_id") and normalize_option_value(simc_options.get("enchant_id")) == enhancement.get("enchant_id"))
    if option_type == "embellishment":
        return bool(enhancement.get("embellishment") and normalize_option_value(simc_options.get("embellishment")) == enhancement.get("embellishment"))
    return False


def matching_enhancement_option(item, enhancement, option_type):
    for option in enhancement_options_for_type(item, option_type):
        if enhancement_option_matches(option, enhancement, option_type):
            return option
    return None


def item_has_independent_embellishment_capability(item):
    if not isinstance(item, dict):
        return False
    if normalize_option_value(item.get("crafted_stats") or item.get("craftedStats")):
        return True
    if raw_source_type(item.get("sourceType")).lower() == "crafted":
        return True
    if raw_source_type(item.get("variantSource")).lower() == "crafted":
        return True
    for source in [*(item.get("sources") or []), *(item.get("sourceRefs") or [])]:
        if isinstance(source, dict) and raw_source_type(source.get("sourceType")).lower() == "crafted":
            return True
    for variant in item.get("variants") or []:
        if not isinstance(variant, dict):
            continue
        simc_options = variant.get("simcOptions") if isinstance(variant.get("simcOptions"), dict) else {}
        payload = variant.get("payload") if isinstance(variant.get("payload"), dict) else {}
        if raw_source_type(variant.get("sourceType")).lower() == "crafted":
            return True
        if normalize_option_value(simc_options.get("crafted_stats") or payload.get("crafted_stats") or payload.get("craftedStats")):
            return True
    return False


def item_supports_enhancement_type(item, option_type):
    caps = item.get("modCapabilities") if isinstance(item.get("modCapabilities"), dict) else {}
    catalog_options_attached = bool(item.get("_catalogEnhancementOptionsAttached"))
    if option_type == "socket":
        if caps.get("hasSocket") is False:
            return False
        slot = normalize_slot(item.get("slot") or item.get("simcSlot"))
        return bool(
            caps.get("hasSocket")
            or item.get("supportsSocket")
            or item_socket_capacity({}, slot)
            or (not catalog_options_attached and item.get("socketOptions"))
        )
    if option_type == "enchant":
        slot = normalize_slot(item.get("slot") or item.get("simcSlot"))
        if not item_can_enchant_slot({}, slot, item):
            return False
        if caps.get("canEnchant") is False:
            return False
        return bool(caps.get("canEnchant") or slot in ENCHANTABLE_GEAR_SLOTS or item.get("enchantOptions"))
    if option_type == "embellishment":
        return bool(
            item_has_independent_embellishment_capability(item)
            or (not catalog_options_attached and caps.get("canEmbellish"))
            or (not catalog_options_attached and item.get("embellishmentOptions"))
        )
    return False


def validate_enhancement_option(item, enhancement, option_type):
    if not item_supports_enhancement_type(item, option_type):
        return False, f"{item.get('slot')} {option_type} incompatible with selected gear"
    options = enhancement_options_for_type(item, option_type)
    if not options:
        return False, f"{item.get('slot')} {option_type} option is not in verified rank-two catalog"
    if not matching_enhancement_option(item, enhancement, option_type):
        return False, f"{item.get('slot')} {option_type} option is not in verified rank-two catalog"
    return True, ""


def selected_gear_item_weapon_type(item):
    if not isinstance(item, dict):
        return ""
    weapon_type = str(item.get("weaponType") or "").strip()
    if weapon_type:
        return weapon_type
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    return str(item_type_metadata_from_payload(payload).get("weaponType") or "").strip()


def selected_gear_weapon_rule_blocker(item, class_key, spec_key):
    if not isinstance(item, dict):
        return ""
    slot = normalize_slot(item.get("slot") or item.get("simcSlot"))
    if slot not in WEAPON_SLOTS:
        return ""
    weapon_type = selected_gear_item_weapon_type(item)
    if not weapon_type or weapon_type_allowed_for_slot(class_key, spec_key, slot, weapon_type):
        return ""
    class_spec = f"{slugify(class_key, '')}/{slugify(spec_key, '')}".strip("/")
    return f"{slot} gear incompatible with {class_spec} weapon rule: {weapon_type}"


def selected_gear_weapon_rule_blockers(items, class_key, spec_key):
    if not class_key:
        return [], set()
    normalized_items = [item for item in items or [] if isinstance(item, dict)]
    by_slot = {
        normalize_slot(item.get("slot") or item.get("simcSlot")): item
        for item in normalized_items
        if normalize_slot(item.get("slot") or item.get("simcSlot"))
    }
    blockers = []
    invalid_slots = set()
    for item in normalized_items:
        slot = normalize_slot(item.get("slot") or item.get("simcSlot"))
        blocker = selected_gear_weapon_rule_blocker(item, class_key, spec_key)
        if blocker:
            blockers.append(blocker)
            invalid_slots.add(slot)
    main_hand_type = selected_gear_item_weapon_type(by_slot.get("main_hand"))
    rule = weapon_equipment_rule_for_spec(class_key, spec_key)
    if (
        by_slot.get("off_hand")
        and "off_hand" not in invalid_slots
        and main_hand_type in TWO_HAND_WEAPON_TYPES
        and rule.get("mode") != "dual_wield_2h"
    ):
        blockers.append("off_hand gear incompatible with selected two-hand main hand")
        invalid_slots.add("off_hand")
    return blockers, invalid_slots


def attach_catalog_enhancement_options(conn, items):
    if conn is None:
        return items
    options_by_type = {}
    try:
        options_by_type = {
            "socketOptions": display_ready_gear_mod_options_by_slot(conn, "socket"),
            "enchantOptions": display_ready_gear_mod_options_by_slot(conn, "enchant"),
            "embellishmentOptions": display_ready_gear_mod_options_by_slot(conn, "embellishment"),
        }
    except Exception:
        return items
    enhanced = []
    for item in items:
        if not isinstance(item, dict):
            continue
        slot = item.get("slot") or ""
        next_item = dict(item)
        for key, by_slot in options_by_type.items():
            if key == "enchantOptions":
                next_item[key] = [
                    option
                    for option in by_slot.get(slot) or []
                    if gear_enchant_option_applies_to_item(option, next_item)
                ]
            elif key == "embellishmentOptions":
                next_item[key] = [
                    option
                    for option in by_slot.get(slot) or []
                    if gear_embellishment_option_applies_to_item(option, next_item)
                ]
            else:
                next_item[key] = by_slot.get(slot) or []
        next_item["_catalogEnhancementOptionsAttached"] = True
        enhanced.append(next_item)
    return enhanced


def merge_websim_gear_enhancements(items, raw_enhancements, conn=None, class_key="", spec_key=""):
    items = attach_catalog_enhancement_options(conn, items)
    blockers, invalid_gear_slots = selected_gear_weapon_rule_blockers(items, class_key, spec_key)
    if invalid_gear_slots:
        items = [
            item
            for item in items
            if normalize_slot(item.get("slot") or item.get("simcSlot")) not in invalid_gear_slots
        ]
    normalized_enhancements = normalize_enhancement_by_slot(raw_enhancements)
    by_slot = {item.get("slot"): item for item in items if isinstance(item, dict) and item.get("slot")}
    built_in_count = sum(1 for item in items if item_builtin_embellishment_value(item))
    selected_embellishment_slots = [
        slot
        for slot, enhancement in normalized_enhancements.items()
        if normalize_option_value(enhancement.get("embellishment"))
    ]
    embellishment_total = built_in_count + len(selected_embellishment_slots)
    if embellishment_total > 2:
        blockers.append(f"embellishment limit exceeded: {embellishment_total}/2")
    for slot in normalized_enhancements:
        if slot not in by_slot:
            blockers.append(f"{slot} enhancement has missing selected gear")
    socket_unique_groups = {}
    for slot, enhancement in normalized_enhancements.items():
        if slot not in by_slot or not enhancement.get("gem_id"):
            continue
        matched_option = matching_enhancement_option(by_slot[slot], enhancement, "socket")
        unique_group = enhancement_option_unique_group(matched_option, "socket")
        if not unique_group:
            continue
        unique_limit = enhancement_option_unique_limit(matched_option, "socket") or 1
        state = socket_unique_groups.setdefault(unique_group, {"limit": unique_limit, "slots": []})
        state["limit"] = min(state["limit"], unique_limit)
        state["slots"].append(slot)
    blocked_socket_unique_slots = {}
    for unique_group, state in socket_unique_groups.items():
        unique_limit = state.get("limit") or 1
        slots = state.get("slots") or []
        if len(slots) <= unique_limit:
            continue
        blockers.append(f"{unique_group} gem limit exceeded: {len(slots)}/{unique_limit}")
        for slot in slots:
            blocked_socket_unique_slots[slot] = unique_group
    enhanced = []
    for item in items:
        if not isinstance(item, dict):
            continue
        slot = item.get("slot") or ""
        enhancement = normalized_enhancements.get(slot) or {}
        next_item = dict(item)
        if enhancement.get("gem_id"):
            if slot not in blocked_socket_unique_slots:
                valid, reason = validate_enhancement_option(next_item, enhancement, "socket")
                if valid:
                    for key in ("gem_id", "gem_bonus_id", "gem_ilevel", "socketOptionId"):
                        if enhancement.get(key):
                            next_item[key] = enhancement[key]
                else:
                    blockers.append(reason)
        if enhancement.get("enchant_id"):
            blocker = dk_ordinary_weapon_enchant_blocker(class_key, slot, enhancement.get("enchant_id"))
            if blocker:
                blockers.append(f"{slot} {blocker}")
            else:
                valid, reason = validate_enhancement_option(next_item, enhancement, "enchant")
                if valid:
                    next_item["enchant_id"] = enhancement["enchant_id"]
                    if enhancement.get("enchantOptionId"):
                        next_item["enchantOptionId"] = enhancement["enchantOptionId"]
                else:
                    blockers.append(reason)
        if enhancement.get("embellishment"):
            if item_builtin_embellishment_value(next_item):
                blockers.append(f"{slot} embellishment incompatible with built-in embellishment")
            elif embellishment_total > 2:
                blockers.append(f"{slot} embellishment blocked by 2 embellishment limit")
            else:
                valid, reason = validate_enhancement_option(next_item, enhancement, "embellishment")
                if valid:
                    next_item["embellishment"] = enhancement["embellishment"]
                    if enhancement.get("embellishmentOptionId"):
                        next_item["embellishmentOptionId"] = enhancement["embellishmentOptionId"]
                else:
                    blockers.append(reason)
        built_in_enchant_blocker = dk_ordinary_weapon_enchant_blocker(class_key, slot, next_item.get("enchant_id"))
        if built_in_enchant_blocker:
            blockers.append(f"{slot} {built_in_enchant_blocker}")
            next_item.pop("enchant_id", None)
            next_item.pop("enchantOptionId", None)
        default_runeforge = dk_default_runeforge_enchant_id(class_key, spec_key, slot)
        if default_runeforge and not next_item.get("enchant_id"):
            next_item["enchant_id"] = default_runeforge
            next_item["runeforgeStatus"] = "default_verified"
        next_item["missingFields"] = gear_item_missing_fields(next_item)
        next_item["simcReady"] = gear_item_simc_ready(next_item)
        next_item.pop("_catalogEnhancementOptionsAttached", None)
        enhanced.append(next_item)
    readiness = {
        "schemaRevision": GEAR_ENHANCEMENT_SNAPSHOT_REVISION,
        "embellishmentUsed": embellishment_total,
        "embellishmentMax": 2,
        "builtInEmbellishmentCount": built_in_count,
        "selectedEmbellishmentCount": len(selected_embellishment_slots),
        "blockers": unique_text_list(blockers),
    }
    return enhanced, readiness


def build_websim_profile(payload, conn=None):
    source = payload if isinstance(payload, dict) else {}
    class_key = slugify(source.get("classKey"), "mage")
    spec_key = slugify(source.get("specKey"), "arcane")
    race = normalize_option_value(source.get("race") or DEFAULT_RACE_BY_CLASS.get(class_key, "troll"))
    level = str(normalized_websim_level(source.get("level")))
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
    talent_encoding = encode_websim_talents(conn, source) if conn is not None else blank_talent_encoding()
    if talent_encoding.get("status") in {"encoded", "external"}:
        lines.extend(talent_encoding.get("lines") or [])
    elif conn is None:
        talents = external_talent_import_code(source)
        if talents:
            lines.append(f"talents={talents}")
    gear_payload = websim_selected_gear_payload(source, class_key, spec_key, conn=conn)
    lines.extend(build_websim_gear_lines(gear_payload["simcItems"]))
    preparation = apply_simc_preparation_lines(lines, class_key=class_key, spec_key=spec_key)
    scenario = selected_scenario(source.get("scenarioKey"))
    lines.extend(
        [
            f"iterations={int_env('WOW_WEBSIM_SIMC_ITERATIONS', 1000)}",
            f"fight_style={scenario['fightStyle']}",
            f"desired_targets={scenario['targets']}",
            f"max_time={scenario['durationSeconds']}",
            "vary_combat_length=0.2",
            "calculate_scale_factors=0",
        ]
    )
    return "\n".join(lines).strip()


def websim_profile_readiness_payload(readiness, talent_encoding):
    gear_readiness = readiness if isinstance(readiness, dict) else {}
    talent_payload = talent_encoding if isinstance(talent_encoding, dict) else blank_talent_encoding("failed", "none")
    talent_ready = talent_payload.get("status") in {"encoded", "external"}
    gear_ready = bool(gear_readiness.get("fullReady"))
    blockers = websim_gear_stats_blockers(gear_readiness, talent_payload)
    missing_fields = []
    if not talent_ready:
        missing_fields.append("talents")
    if not gear_ready:
        missing_fields.append("gear")
    return {
        "schemaRevision": TALENT_SCHEMA_REVISION,
        "talentReady": talent_ready,
        "gearReady": gear_ready,
        "simcReady": bool(talent_ready and gear_ready),
        "missingFields": missing_fields,
        "blockers": unique_text_list(blockers),
    }


def build_websim_profile_response(payload, conn=None):
    source = payload if isinstance(payload, dict) else {}
    class_key = slugify(source.get("classKey"), "mage")
    spec_key = slugify(source.get("specKey"), "arcane")
    gear_payload = websim_selected_gear_payload(source, class_key, spec_key, conn=conn)
    talent_encoding = encode_websim_talents(conn, source) if conn is not None else encode_websim_talents(None, source)
    response = {
        "profile": build_websim_profile(payload, conn=conn),
        "gearItems": gear_payload["items"],
        "simcItems": gear_payload["simcItems"],
        "readiness": gear_payload["readiness"],
        "talentEncoding": talent_encoding,
        "profileReadiness": websim_profile_readiness_payload(gear_payload["readiness"], talent_encoding),
    }
    preparation = simc_preparation_payload(class_key, spec_key)
    response["preparation"] = simc_preparation_report(preparation)
    return response


def websim_selected_gear_payload(source, class_key, spec_key, conn=None):
    raw_items, raw_enhancements = websim_gear_items_and_enhancements_from_source(source)
    items = normalize_websim_gear_items(raw_items, class_key, spec_key)
    items = hydrate_simc_item_names(items, class_key, spec_key, conn=conn)
    items, enhancement_readiness = merge_websim_gear_enhancements(
        items,
        raw_enhancements,
        conn=conn,
        class_key=class_key,
        spec_key=spec_key,
    )
    ready_items = [item for item in items if item.get("simcReady")]
    readiness = gear_readiness(items)
    readiness["enhancement"] = enhancement_readiness
    if enhancement_readiness.get("blockers"):
        readiness["fullReady"] = False
        readiness["status"] = "blocked" if not ready_items else "partial"
        readiness["warnings"] = unique_text_list([*(readiness.get("warnings") or []), *enhancement_readiness.get("blockers")])
    return {
        "items": items,
        "simcItems": ready_items,
        "readiness": readiness,
    }


def websim_gear_stats_blockers(readiness, talent_encoding):
    blockers = []
    if talent_encoding.get("status") not in {"encoded", "external"}:
        blockers.extend(talent_encoding.get("errors") or [])
        if not blockers:
            blockers.append("talent encoding failed")
    if not readiness.get("fullReady"):
        blockers.append("selected gear is not fully SimC-ready")
        blockers.extend(readiness.get("warnings") or [])
    return [blocker for blocker in blockers if str(blocker or "").strip()]


def build_websim_gear_stats_response(payload, conn=None):
    source = payload if isinstance(payload, dict) else {}
    class_key = slugify(source.get("classKey"), "mage")
    spec_key = slugify(source.get("specKey"), "arcane")
    level = normalized_websim_level(source.get("level"))
    request_source = {**source, "classKey": class_key, "specKey": spec_key, "level": level}
    gear_payload = websim_selected_gear_payload(request_source, class_key, spec_key, conn=conn)
    readiness = gear_payload["readiness"]
    talent_encoding = encode_websim_talents(conn, request_source) if conn is not None else encode_websim_talents(None, request_source)
    parsed_export = parse_websim_talent_export_code(
        request_source.get("websimExportCode") or request_source.get("talents") or request_source.get("talentImport") or ""
    )
    explicit_hero_key = (
        request_source.get("heroKey")
        or talent_encoding.get("heroKey")
        or ((parsed_export or {}).get("heroKey") if isinstance(parsed_export, dict) else "")
    )
    blockers = websim_gear_stats_blockers(readiness, talent_encoding)
    blockers.extend(simcraft_known_compatibility_blockers(
        class_key,
        spec_key,
        explicit_hero_key,
        request_source.get("scenarioKey"),
    ))
    if blockers:
        return blocked_stat_snapshot(
            blockers,
            class_key=class_key,
            spec_key=spec_key,
            level=level,
            gear_readiness_payload=readiness,
            talent_encoding=talent_encoding,
        )

    profile = build_websim_profile(request_source, conn=conn)
    simc_result = run_websim_stat_simcraft(profile)
    item_name_diagnostics = simc_result.get("itemNameDiagnostics") or []
    can_use_json_after_trivial_exit = (
        simc_result.get("jsonPayload")
        and item_name_diagnostics
        and simcraft_only_item_name_diagnostics(simc_result.get("stderr") or simc_result.get("error") or "")
    )
    if not simc_result.get("ran"):
        if can_use_json_after_trivial_exit:
            pass
        else:
            return blocked_stat_snapshot(
                [simc_result.get("error") or "SimC stat snapshot could not run"],
                class_key=class_key,
                spec_key=spec_key,
                level=level,
                gear_readiness_payload=readiness,
                talent_encoding=talent_encoding,
            )

    item_resolution_warnings = simc_result.get("itemResolutionWarnings") or []
    if item_resolution_warnings:
        snapshot = blocked_stat_snapshot(
            item_resolution_warnings,
            class_key=class_key,
            spec_key=spec_key,
            level=level,
            gear_readiness_payload=readiness,
            talent_encoding=talent_encoding,
        )
        snapshot["statSource"] = "simulationcraft_json"
        snapshot["simcWarnings"] = item_resolution_warnings
    elif simc_result.get("jsonPayload"):
        snapshot = parse_simcraft_json_stat_snapshot(simc_result.get("jsonPayload"))
    else:
        snapshot = parse_simcraft_stat_snapshot(simc_result.get("rawOutput") or simc_result.get("summary") or "")
        if simc_result.get("jsonError"):
            snapshot["simcWarnings"] = [simc_result.get("jsonError")]
    snapshot.update({
        "classKey": class_key,
        "specKey": spec_key,
        "maxLevel": level,
        "itemLevel": readiness.get("itemLevel") or gear_item_level_payload(gear_payload["items"]),
        "gearReadiness": readiness,
        "talentEncoding": talent_encoding,
        "gearItems": gear_payload["items"],
        "simcItems": gear_payload["simcItems"],
        "gearSchemaRevision": GEAR_SCHEMA_REVISION,
    })
    if item_name_diagnostics:
        snapshot["simcWarnings"] = unique_text_list([*(snapshot.get("simcWarnings") or []), *item_name_diagnostics])
    if snapshot.get("statStatus") != "verified":
        snapshot["blockers"] = snapshot.get("blockers") or ["SimC output did not include a parseable stat snapshot"]
        if simc_result.get("jsonError") and simc_result.get("jsonError") not in snapshot["blockers"]:
            snapshot["simcWarnings"] = unique_text_list([*(snapshot.get("simcWarnings") or []), simc_result.get("jsonError")])
    return snapshot


def build_websim_simulator_request(payload, guest_id="", conn=None):
    source = payload if isinstance(payload, dict) else {}
    class_key = slugify(source.get("classKey"), "mage")
    spec_key = slugify(source.get("specKey"), "arcane")
    hero_key = hero_tree_for(class_key, spec_key, slugify(source.get("heroKey"), ""))
    talent_encoding = encode_websim_talents(conn, source) if conn is not None else encode_websim_talents(None, source)
    talents = external_talent_import_code(source)[:400]
    scenario = selected_scenario(source.get("scenarioKey"))
    gear_payload = websim_selected_gear_payload(source, class_key, spec_key, conn=conn)
    readiness = gear_payload["readiness"]
    has_talent_lines = talent_encoding.get("status") in {"encoded", "external"} or bool(talents)
    canonical_profile = (
        build_websim_profile(source, conn=conn)
        if has_talent_lines and readiness.get("fullReady")
        else ""
    )
    message = f"WebSim {class_key} {spec_key} {scenario.get('fightStyle') or ''} gear simulation"
    request = {
        "mode": "simcraft_agent",
        "message": message,
        "prompt": message,
        "question": "WebSim gear and talent simulation",
        "runSimulation": True,
        "saveTask": bool(source.get("saveTask", True)),
        "guestId": guest_id or str(source.get("guestId") or ""),
        "talentEncoding": talent_encoding,
        "buildContext": {
            "specId": f"{class_key}-{spec_key}",
            "className": class_key,
            "specName": spec_key,
            "heroTalentKey": hero_key,
            "heroTalent": hero_tree_label(hero_key),
            "activeQueryKey": "websim",
            "activeQueryTitle": "WebSim gear simulator",
            "sourceName": "WebSim",
            "analysisWindow": "Selected WebSim gear and talent state",
            "details": {
                "talents": {
                    "importCode": talents,
                    "simcLines": talent_encoding.get("lines") or [],
                    "encodingStatus": talent_encoding.get("status", ""),
                },
                "gear": {
                    "gear": [
                        {
                            "slot": item.get("slot"),
                            "name": item.get("displayName") or item.get("name"),
                            "source": item.get("source") or item.get("sourceType"),
                        }
                        for item in gear_payload["items"]
                    ],
                    "simcItems": gear_payload["simcItems"],
                    "readiness": gear_payload["readiness"],
                },
            },
            "simulatorState": {
                "gear": {
                    "selectedItems": gear_payload["simcItems"],
                    "progressText": f"{gear_payload['readiness']['simcReadyCount']} SimC-ready item(s)",
                    "nextAction": "Fill item level and bonus/gem/enchant fields for candidate loot.",
                }
            },
        },
    }
    if canonical_profile:
        request["profile"] = canonical_profile
        request["profileSource"] = "websim"
    return request

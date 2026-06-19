#!/usr/bin/env python3
import ast
import base64
import csv
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse
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
SIMC_TALENT_SOURCE_REFS = [
    {
        "name": "SimulationCraft generated trait data",
        "url": DEFAULT_SIMC_TRAIT_DATA_URL,
        "note": "Generated SimC trait_data.inc used for class, specialization and hero talent node layout.",
    }
]
COMMUNITY_TALENT_SYNC_KEY = "community_talent_templates"
TALENT_SCHEMA_REVISION = "websim-talent-rules-v1"
GEAR_SCHEMA_REVISION = "websim-gear-simulator-v1"
GEAR_CATALOG_REVISION = "websim-gear-catalog-v1"
DEFAULT_GEAR_MOD_SEED = [
    {
        "id": "seed-socket-gem-240983",
        "type": "socket",
        "name": "Server seed gem 240983",
        "slots": ["*"],
        "simcOptions": {"gem_id": "240983"},
        "status": "partial",
        "payload": {
            "source": "server_default_seed",
            "blockers": ["official current-season gem label pending"],
        },
    },
    {
        "id": "seed-enchant-8017",
        "type": "enchant",
        "name": "Server seed enchant 8017",
        "slots": ["head"],
        "simcOptions": {"enchant_id": "8017"},
        "status": "partial",
        "payload": {
            "source": "server_default_seed",
            "blockers": ["official current-season enchant label pending"],
        },
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
]

SIMC_GEAR_OPTION_KEYS = {key for key, _ in SIMC_GEAR_OPTION_ALIASES}
SIMC_READY_SOURCE_TYPES = {"simcPreset"}
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
        ("wrist", "wrist"),
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
    slot = item_slot_from_payload(item_payload) or fallback_slot or "trinket1"
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
        "metadataStatus": "verified",
        "metadataSource": source,
        "metadataLocale": locale,
    }


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


def sync_blizzard_journal(conn, token, region=DEFAULT_REGION, locale=DEFAULT_LOCALE):
    now = utc_now()
    instance_limit = int_env("WOW_WEBSIM_SYNC_INSTANCE_LIMIT", 8)
    raid_instance_limit = int_env("WOW_WEBSIM_SYNC_RAID_INSTANCE_LIMIT", 4)
    encounter_limit = int_env("WOW_WEBSIM_SYNC_ENCOUNTER_LIMIT", 80)
    item_limit = int_env("WOW_WEBSIM_SYNC_ITEM_LIMIT", 300)
    season = resolve_current_mythic_season(token, region, locale)
    save_active_season_payload(conn, season)
    conn.commit()
    dungeons = [
        {**dungeon, "instanceId": str(dungeon.get("instanceId") or dungeon.get("id") or ""), "category": "Dungeon"}
        for dungeon in (season.get("dungeons") or [])[:instance_limit]
        if str(dungeon.get("instanceId") or dungeon.get("id") or "").strip()
    ]
    raid_refs = []
    try:
        for ref in selected_journal_instance_refs(token, region, season.get("locale") or locale):
            if str(ref.get("category") or "").lower() == "raid":
                raid_refs.append({
                    **ref,
                    "instanceId": str(ref.get("instanceId") or ref.get("id") or ""),
                    "category": "Raid",
                })
    except Exception:
        raid_refs = []
    instance_refs = []
    seen_instances = set()
    for ref in [*dungeons, *raid_refs[:raid_instance_limit]]:
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
    }
    fetched_items = set()
    conn.execute("DELETE FROM websim_loot")
    conn.execute("DELETE FROM websim_encounters")
    conn.execute("DELETE FROM websim_instances")
    conn.commit()

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
        except Exception:
            instance = {"id": instance_id, "name": instance_ref.get("name") or f"Instance {instance_id}", "encounters": []}
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
                    item_metadata = fetch_blizzard_item_metadata(
                        token,
                        item_id,
                        region,
                        season.get("locale") or locale,
                        fallback_name=(item_ref or {}).get("name") if isinstance(item_ref, dict) else "",
                    )
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
                    fetched_items.add(item_id)
                    counts["items"] += 1
                item_name = item_payload.get("name") or (item_ref or {}).get("name") or f"Item {item_id}"
                slot = item_slot_from_payload(item_payload)
                quality = (item_payload.get("quality") or {}).get("name") or ""
                icon_url = icon_url_from_media(media_payload)
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
                upsert_websim_asset(conn, loot_asset)
                counts["loot"] += 1
        conn.commit()
    conn.commit()
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


def sync_simc_generated_data(conn):
    now = utc_now()
    data = extract_simc_generated_data()
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
    game_asset = normalize_game_asset(
        (metadata or {}).get("gameAsset") if isinstance(metadata, dict) else {},
        game_asset_from_icon_url(
            "item",
            row[0],
            "websim-item-metadata",
            row[4] or "",
            source=(metadata or {}).get("source") or ITEM_METADATA_SOURCE,
            status="verified",
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
        "metadataStatus": "verified",
        "metadataSource": (metadata or {}).get("source") or ITEM_METADATA_SOURCE,
        "metadataLocale": (metadata or {}).get("locale") or DEFAULT_LOCALE,
        "englishName": (metadata or {}).get("englishName") or "",
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


def crafted_gear_seed():
    raw = os.environ.get("WOW_WEBSIM_CRAFTED_GEAR_SEED", "").strip()
    if not raw:
        return []
    parsed = safe_json_loads(raw, [])
    return parsed if isinstance(parsed, list) else []


def gear_mod_seed():
    seeds = [dict(option) for option in DEFAULT_GEAR_MOD_SEED]
    raw = os.environ.get("WOW_WEBSIM_GEAR_MOD_SEED", "").strip()
    if not raw:
        return seeds
    parsed = safe_json_loads(raw, [])
    if isinstance(parsed, list):
        seeds.extend(parsed)
    return seeds


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


def upsert_gear_mod_option(conn, option):
    option_type = str(option.get("optionType") or option.get("type") or "").strip().lower()
    if option_type not in {"socket", "enchant"}:
        return False
    simc_options = option.get("simcOptions") if isinstance(option.get("simcOptions"), dict) else {}
    simc_options = {key: value for key, value in simc_options.items() if key in SIMC_GEAR_OPTION_KEYS and normalize_option_value(value)}
    if not simc_options:
        return False
    option_id = str(option.get("id") or "").strip()
    if not option_id:
        digest = hashlib.sha256(json.dumps([option_type, option.get("name") or option.get("label") or "", simc_options], sort_keys=True).encode("utf-8")).hexdigest()[:12]
        option_id = f"seed-{option_type}-{digest}"
    slots = option.get("applicableSlots") or option.get("slots") or option.get("applicable_slots") or []
    if isinstance(slots, str):
        slots = [slots]
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
            option.get("status") or "verified",
            json.dumps(option.get("payload") or {}, ensure_ascii=False),
            utc_now(),
        ),
    )
    return True


def sync_websim_gear_mod_options(conn):
    conn.execute("DELETE FROM websim_gear_mod_options WHERE id LIKE 'seed-%'")
    count = 0
    for option in gear_mod_seed():
        if isinstance(option, dict) and upsert_gear_mod_option(conn, option):
            count += 1
    return count


def sync_websim_gear_catalog(conn, season=None):
    ensure_websim_tables(conn)
    season = season or get_active_season_payload(conn)
    season_revision = season.get("seasonRevision") or season.get("revision") or ""
    sync_websim_gear_mod_options(conn)
    conn.execute("DELETE FROM websim_gear_sources WHERE id LIKE 'loot-%' OR id LIKE 'crafted-%'")
    conn.execute("DELETE FROM websim_gear_variants WHERE id LIKE 'loot-partial-%' OR id LIKE 'crafted-%'")
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
                "payload": {"authority": ITEM_METADATA_SOURCE, "sourceCategory": row[6]},
            },
        )
        upsert_gear_variant(
            conn,
            {
                "id": f"loot-partial-{row[1]}-{normalize_slot(row[2]) or 'slot'}",
                "itemId": row[1],
                "slot": row[2],
                "variantKey": "needs-variant",
                "label": "Select difficulty/item level",
                "sourceType": source_type,
                "itemLevel": 0,
                "simcOptions": {},
                "status": "partial",
                "blockers": ["missing deterministic SimC variant preset"],
                "payload": {"seasonRevision": season_revision},
            },
        )
    for entry in crafted_gear_seed():
        if not isinstance(entry, dict):
            continue
        item_id = normalize_option_value(entry.get("itemId") or entry.get("id"))
        if not item_id:
            continue
        metadata = websim_item_metadata_by_ids(conn, [item_id]).get(item_id)
        if not metadata:
            continue
        source_label = str(entry.get("sourceLabel") or entry.get("source") or "Crafted gear")
        upsert_gear_source(
            conn,
            {
                "id": f"crafted-{item_id}",
                "itemId": item_id,
                "sourceType": "crafted",
                "sourceLabel": source_label,
                "seasonRevision": season_revision,
                "payload": {"authority": ITEM_METADATA_SOURCE, "craftedSeed": True},
            },
        )
        variants = entry.get("variants") if isinstance(entry.get("variants"), list) else []
        for index, variant in enumerate(variants, start=1):
            if not isinstance(variant, dict):
                continue
            simc_options = variant.get("simcOptions") if isinstance(variant.get("simcOptions"), dict) else {}
            status = "verified" if simc_options and (variant.get("itemLevel") or variant.get("ilevel")) else "partial"
            upsert_gear_variant(
                conn,
                {
                    "id": f"crafted-{item_id}-{variant.get('key') or index}",
                    "itemId": item_id,
                    "slot": entry.get("slot") or metadata.get("slot") or "",
                    "variantKey": variant.get("key") or f"crafted-{index}",
                    "label": variant.get("label") or f"Crafted {index}",
                    "sourceType": "crafted",
                    "difficultyKey": variant.get("difficultyKey") or "crafted",
                    "itemLevel": variant.get("itemLevel") or variant.get("ilevel") or 0,
                    "simcOptions": simc_options,
                    "status": status,
                    "blockers": [] if status == "verified" else ["crafted variant missing deterministic SimC options"],
                    "payload": {
                        "classKeys": entry.get("classKeys") or [],
                        "specKeys": entry.get("specKeys") or [],
                        "seasonRevision": season_revision,
                    },
                },
            )
    state = build_gear_catalog_sync_state(conn, season)
    set_sync_state(conn, "gearCatalog", state)
    return state


def sync_websim_cache(db_path, include_blizzard=True):
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    try:
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")
        ensure_websim_tables(conn)
        simc_counts = sync_simc_generated_data(conn)
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
                "itemMetadata": {
                    "items": 0,
                    "aliases": 0,
                    "skipped": 0,
                    "searched": 0,
                    "resolved": 0,
                    "references": 0,
                    "errors": [],
                },
                "spells": {"spells": 0, "media": 0},
                "gearCatalog": initial_gear_catalog,
                "currentSeason": simc_season,
                "dataStatus": simc_season.get("dataStatus") or "blocked",
                "seasonRevision": simc_season.get("seasonRevision") or "",
                "talentSchemaRevision": TALENT_SCHEMA_REVISION,
                "talentHealth": simc_talent_health,
                "errors": [],
            },
        )
        conn.commit()
        blizzard_counts = {"instances": 0, "encounters": 0, "loot": 0, "items": 0}
        item_metadata_counts = {
            "items": 0,
            "aliases": 0,
            "skipped": 0,
            "searched": 0,
            "resolved": 0,
            "references": 0,
            "errors": [],
        }
        spell_counts = {"spells": 0, "media": 0}
        errors = []
        blizzard_skipped = ""
        if include_blizzard:
            refresh_always = os.environ.get("WOW_WEBSIM_REFRESH_BLIZZARD_ALWAYS", "0").strip() == "1"
            if simc_season.get("dataStatus") == "verified" and not refresh_always:
                blizzard_skipped = "fresh-season-cache"
                if (
                    os.environ.get("WOW_WEBSIM_SYNC_ITEM_METADATA_ON_FRESH", "1").strip() != "0"
                    and blizzard_credentials_configured()
                ):
                    try:
                        token = get_blizzard_access_token(DEFAULT_REGION)
                        item_metadata_counts = merge_item_metadata_counts(
                            sync_blizzard_preset_item_metadata(conn, token, DEFAULT_REGION, DEFAULT_LOCALE),
                            sync_blizzard_build_gear_item_metadata(conn, token, DEFAULT_REGION, DEFAULT_LOCALE),
                        )
                    except Exception as error:
                        item_metadata_counts["errors"].append(str(error))
            else:
                try:
                    token = get_blizzard_access_token(DEFAULT_REGION)
                    blizzard_counts = sync_blizzard_journal(conn, token, DEFAULT_REGION, DEFAULT_LOCALE)
                    item_metadata_counts = merge_item_metadata_counts(
                        sync_blizzard_preset_item_metadata(conn, token, DEFAULT_REGION, DEFAULT_LOCALE),
                        sync_blizzard_build_gear_item_metadata(conn, token, DEFAULT_REGION, DEFAULT_LOCALE),
                    )
                    spell_counts = sync_blizzard_spell_details(conn, token, DEFAULT_REGION, DEFAULT_LOCALE)
                except Exception as error:
                    errors.append(str(error))
        active_season = get_active_season_payload(conn)
        gear_catalog_state = sync_websim_gear_catalog(conn, active_season)
        talent_health = {
            "schemaRevision": TALENT_SCHEMA_REVISION,
            "simcBuild": simc_counts.get("build") or "",
            "traitEdgeSource": simc_counts.get("traitEdgeSource") or "",
            "officialRevision": active_season.get("seasonRevision") or "",
            "diffStatus": "pending_official_audit" if simc_counts.get("talents") else "blocked",
            "checkedAt": utc_now(),
        }
        payload = {
            "ok": not errors and active_season.get("dataStatus") == "verified",
            "checkedAt": utc_now(),
            "region": DEFAULT_REGION,
            "locale": DEFAULT_LOCALE,
            "simc": simc_counts,
            "blizzard": blizzard_counts,
            "itemMetadata": item_metadata_counts,
            "spells": spell_counts,
            "gearCatalog": gear_catalog_state,
            "currentSeason": active_season,
            "dataStatus": active_season.get("dataStatus") or "blocked",
            "seasonRevision": active_season.get("seasonRevision") or "",
            "talentSchemaRevision": TALENT_SCHEMA_REVISION,
            "talentHealth": talent_health,
            "errors": errors,
        }
        if blizzard_skipped:
            payload["blizzardSkipped"] = blizzard_skipped
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
    description = row[9] or payload.get("description") or (
        f"SimulationCraft {tree_type} talent node for "
        f"{SPEC_LABELS.get(row[2], row[2].replace('_', ' ').title())}."
    )
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
    details = {
        int(row[0]): {"name": row[1] or "", "description": row[2] or ""}
        for row in rows
    }
    for node in nodes or []:
        next_entries = []
        for entry in node.get("rankEntries") or []:
            spell_id = int(entry.get("spellId") or 0)
            detail = details.get(spell_id, {})
            next_entry = dict(entry)
            if detail.get("description"):
                next_entry["description"] = detail["description"]
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


def get_websim_talents(conn, class_key="mage", spec_key="arcane", hero_key=""):
    ensure_websim_tables(conn)
    ensure_community_talent_templates(conn)
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
    has_spell_details = any(row[9] and row[10] for row in filtered_rows)
    talent_status = "verified" if nodes and season.get("dataStatus") == "verified" and has_spell_details else "simc"
    if not nodes:
        nodes = fallback_talents(class_key, spec_key, hero_key)
        talent_status = "fallback"
    talent_authority = talent_authority_payload(conn, talent_status, season, nodes)
    return {
        "classKey": class_key,
        "specKey": spec_key,
        "heroKey": hero_key,
        "talentSchemaRevision": TALENT_SCHEMA_REVISION,
        "talentAuthority": talent_authority,
        "nodes": nodes,
        "presets": get_websim_presets(conn, class_key, spec_key),
        "communityTemplates": get_websim_community_talent_templates(conn, class_key, spec_key, hero_key),
        "communityTemplateSync": community_talent_sync_state(conn),
        "treeSections": talent_tree_sections(class_key, spec_key, hero_key),
        "talentStatus": talent_status,
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


def ensure_community_talent_templates(conn):
    if get_sync_state(conn, COMMUNITY_TALENT_SYNC_KEY):
        return
    try:
        sync_community_talent_templates(conn)
    except Exception as error:
        set_sync_state(conn, COMMUNITY_TALENT_SYNC_KEY, {
            "sourceStatus": "blocked",
            "sources": {
                "manual_fixture": {"status": "blocked", "sourceName": "Manual Fixture", "errors": [str(error)]},
                "raiderio": {"status": "missing_credentials", "sourceName": "Raider.IO", "errors": []},
                "warcraftlogs": {"status": "missing_credentials", "sourceName": "Warcraft Logs", "errors": []},
            },
            "templates": {"total": 0, "verified": 0, "blocked": 0},
            "checkedAt": utc_now(),
        })


def community_talent_sync_state(conn):
    state = get_sync_state(conn, COMMUNITY_TALENT_SYNC_KEY)
    if state:
        return state
    return {
        "sourceStatus": "missing_credentials",
        "sources": {
            "manual_fixture": {"status": "missing_credentials", "sourceName": "Manual Fixture", "errors": []},
            "raiderio": {"status": "missing_credentials", "sourceName": "Raider.IO", "errors": []},
            "warcraftlogs": {"status": "missing_credentials", "sourceName": "Warcraft Logs", "errors": []},
        },
        "templates": {"total": 0, "verified": 0, "blocked": 0},
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


def normalize_community_talent_template(template, source_key="manual_fixture", source_status="partial"):
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
    return {
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
    return template


def encoding_has_unknown_talent_nodes(encoding):
    return any(str(error).startswith("unknown talent node:") for error in (encoding or {}).get("errors") or [])


def validate_community_talent_template(conn, template):
    normalized = normalize_community_talent_template(template, template.get("sourceKey", "manual_fixture"), template.get("sourceStatus", "partial"))
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
    elif normalized["rawImportCode"]:
        normalized["status"] = "blocked"
        normalized["payload"]["errors"] = (
            normalized["payload"].get("talentLoadoutParse", {}).get("errors")
            or ["raw talent import code could not be parsed into WebSim nodes"]
        )
    else:
        normalized["status"] = "blocked"
        normalized["payload"]["errors"] = ["missing WebSim talent state or external talents import code"]
    return refresh_community_talent_identity(normalized)


def upsert_community_talent_template(conn, template):
    ensure_websim_tables(conn)
    normalized = normalize_community_talent_template(
        template,
        template.get("sourceKey", "manual_fixture") if isinstance(template, dict) else "manual_fixture",
        template.get("sourceStatus", "partial") if isinstance(template, dict) else "partial",
    )
    conn.execute(
        """
        INSERT INTO websim_community_talent_templates (
            id, class_key, spec_key, hero_key, scenario_key, name, flow_label,
            source_key, source_name, source_url, raw_import_code, websim_export_code,
            talent_state_json, sample_count, max_key_level, analysis_window,
            source_status, status, payload_json, updated_at, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            expires_at=excluded.expires_at
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
        ),
    )
    return normalized


def get_websim_community_talent_templates(conn, class_key="mage", spec_key="arcane", hero_key=""):
    ensure_websim_tables(conn)
    class_key = slugify(class_key, "mage")
    rows = conn.execute(
        """
        SELECT id, class_key, spec_key, hero_key, scenario_key, name, flow_label,
               source_key, source_name, source_url, raw_import_code, websim_export_code,
               talent_state_json, sample_count, max_key_level, analysis_window,
               source_status, status, payload_json, updated_at, expires_at
        FROM websim_community_talent_templates
        WHERE class_key = ?
          AND status = 'verified'
        ORDER BY max_key_level DESC, sample_count DESC, spec_key, hero_key, name
        LIMIT 60
        """,
        (class_key,),
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
    return templates


def sync_community_talent_templates(conn):
    ensure_websim_tables(conn)
    try:
        from .community_talent_sources import manual_fixture, raiderio, warcraftlogs
    except ImportError:
        from community_talent_sources import manual_fixture, raiderio, warcraftlogs

    adapters = {
        "manual_fixture": manual_fixture.load_templates,
        "raiderio": raiderio.load_templates,
        "warcraftlogs": warcraftlogs.load_templates,
    }
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
    payload = {
        "sourceStatus": source_status,
        "sources": sources,
        "templates": {"total": total, "verified": verified, "blocked": blocked},
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
        game_asset = normalize_game_asset(
            (metadata or {}).get("gameAsset") if isinstance(metadata, dict) else {},
            game_asset_from_icon_url(
                "item",
                row[0],
                "websim-item-metadata",
                row[4] or "",
                source=(metadata or {}).get("source") or ITEM_METADATA_SOURCE,
                status="verified",
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
            "metadataStatus": "verified",
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
        game_asset = normalize_game_asset(
            (metadata or {}).get("gameAsset") if isinstance(metadata, dict) else {},
            game_asset_from_icon_url(
                "item",
                row[1],
                "websim-item-metadata",
                row[3] or "",
                source=row[4] or (metadata or {}).get("source") or ITEM_METADATA_SOURCE,
                status="verified",
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
            "metadataStatus": "verified",
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
                status="verified",
                semantic_tags=["game", "gear", "item", metadata.get("slot") or enriched.get("slot") or ""],
                usage=["websim_gear", "builds_detail", "websim_loot"],
                fallback_text=fallback_text_for(enriched["displayName"]),
            ),
        )
        enriched["gameAsset"] = game_asset
        enriched["iconUrl"] = game_asset.get("iconUrl") or metadata.get("iconUrl") or enriched.get("iconUrl") or enriched.get("icon_url") or ""
        enriched["quality"] = metadata.get("quality") or enriched.get("quality") or ""
        enriched["metadataStatus"] = "verified"
        enriched["metadataSource"] = metadata.get("metadataSource") or ITEM_METADATA_SOURCE
        enriched["metadataLocale"] = metadata.get("metadataLocale") or DEFAULT_LOCALE
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


def gear_catalog_counts(conn):
    ensure_websim_tables(conn)
    source_count = conn.execute("SELECT COUNT(*) FROM websim_gear_sources").fetchone()[0]
    source_item_count = conn.execute("SELECT COUNT(DISTINCT item_id) FROM websim_gear_sources").fetchone()[0]
    mod_option_count = conn.execute("SELECT COUNT(*) FROM websim_gear_mod_options").fetchone()[0]
    variant_rows = conn.execute("SELECT status, blockers_json FROM websim_gear_variants").fetchall()
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
        conn.execute("SELECT COUNT(DISTINCT item_id) FROM websim_gear_variants").fetchone()[0],
    )
    top_blockers = [
        {"reason": reason, "count": count}
        for reason, count in sorted(blocker_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]
    return {
        "itemCount": item_count,
        "sourceCount": source_count,
        "variantCount": variant_count,
        "modOptionCount": mod_option_count,
        "verifiedCount": verified_count,
        "partialCount": partial_count,
        "blockedCount": blocked_count,
        "topBlockers": top_blockers,
        "blockers": [item["reason"] for item in top_blockers],
        "status": catalog_status_from_counts(verified_count, partial_count, blocked_count, item_count),
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


def build_gear_catalog_sync_state(conn, season=None):
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
        "status": state.get("status") or counts["status"],
        "itemDatabaseRevision": state.get("itemDatabaseRevision") or fallback_revision,
        "variantRevision": state.get("variantRevision") or state.get("itemDatabaseRevision") or fallback_revision,
        "checkedAt": state.get("checkedAt") or state.get("updatedAt") or "",
        "schemaRevision": state.get("schemaRevision") or GEAR_CATALOG_REVISION,
    }
    for key in ["itemCount", "sourceCount", "variantCount", "modOptionCount", "verifiedCount", "partialCount", "blockedCount"]:
        if key in state:
            merged[key] = state.get(key) or 0
    if state.get("blockers"):
        merged["blockers"] = state.get("blockers")
    if state.get("topBlockers"):
        merged["topBlockers"] = state.get("topBlockers")
    return merged


def gear_catalog_health_payload(conn):
    state = gear_catalog_sync_state(conn)
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
            "itemDatabaseRevision": state.get("itemDatabaseRevision") or "",
            "variantRevision": state.get("variantRevision") or "",
            "schemaRevision": state.get("schemaRevision") or GEAR_CATALOG_REVISION,
            "topBlockers": state.get("topBlockers") or [],
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
        result.setdefault(str(row[1]), []).append(variant)
    return result


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
            normalized_slots = list(CANONICAL_GEAR_SLOTS)
        simc_options = safe_json_loads(row[4], {})
        if not isinstance(simc_options, dict):
            simc_options = {}
        payload = safe_json_loads(row[6], {})
        option = {
            "id": row[0],
            "type": row[1],
            "optionType": row[1],
            "name": row[2],
            "label": row[2],
            "simcOptions": {key: normalize_option_value(value) for key, value in simc_options.items() if key in SIMC_GEAR_OPTION_KEYS},
            "status": row[5] or "blocked",
            "payload": payload if isinstance(payload, dict) else {},
            "updatedAt": row[7],
        }
        for slot in normalized_slots:
            result.setdefault(slot, []).append(dict(option))
    return result


def catalog_variant_compatible(variant, class_key, spec_key):
    payload = variant.get("payload") if isinstance(variant, dict) else {}
    if not isinstance(payload, dict):
        return True
    class_keys = payload.get("classKeys") or payload.get("classes") or []
    spec_keys = payload.get("specKeys") or payload.get("specs") or []
    if isinstance(class_keys, str):
        class_keys = [class_keys]
    if isinstance(spec_keys, str):
        spec_keys = [spec_keys]
    normalized_classes = {slugify(item, "") for item in class_keys if slugify(item, "")}
    normalized_specs = {slugify(item, "") for item in spec_keys if slugify(item, "")}
    if normalized_classes and class_key not in normalized_classes:
        return False
    if normalized_specs and spec_key not in normalized_specs:
        return False
    return True


def catalog_compatibility(item, variants, class_key, spec_key):
    armor_status = item.get("compatibility") or "unknown"
    compatible_variants = [variant for variant in variants if catalog_variant_compatible(variant, class_key, spec_key)]
    if armor_status == "incompatible" or (variants and not compatible_variants):
        status = "incompatible"
    elif compatible_variants:
        status = "compatible"
    else:
        status = "unknown"
    return {
        "status": status,
        "armorStatus": armor_status,
        "classKey": class_key,
        "specKey": spec_key,
    }


def apply_default_catalog_variant(item, variants):
    if not variants:
        item["defaultVariantKey"] = ""
        return item
    verified = [variant for variant in variants if variant.get("status") == "verified"]
    default_variant = verified[0] if verified else variants[0]
    item["defaultVariantKey"] = default_variant.get("key") or ""
    item["variantKey"] = default_variant.get("key") or ""
    item["variantLabel"] = default_variant.get("label") or ""
    if default_variant.get("itemLevel"):
        item["ilevel"] = default_variant.get("itemLevel")
    for key, value in (default_variant.get("simcOptions") or {}).items():
        if key in SIMC_GEAR_OPTION_KEYS and value:
            item[key] = value
    item["variantStatus"] = default_variant.get("status") or "blocked"
    item["variantBlockers"] = default_variant.get("blockers") or []
    item["missingFields"] = gear_item_missing_fields(item)
    item["simcReady"] = gear_item_simc_ready(item)
    return item


def enrich_catalog_item(item, sources, variants, socket_options, enchant_options, class_key, spec_key):
    if not item:
        return None
    compatible_variants = [variant for variant in variants if catalog_variant_compatible(variant, class_key, spec_key)]
    item["sources"] = sources
    item["variants"] = compatible_variants
    item["socketOptions"] = socket_options
    item["enchantOptions"] = enchant_options
    item["recommendationScore"] = max([int(source.get("recommendationScore") or 0) for source in sources] + [0])
    item["compatibility"] = catalog_compatibility(item, variants, class_key, spec_key)
    if item["compatibility"]["status"] == "incompatible":
        item["missingFields"] = sorted(set((item.get("missingFields") or []) + ["compatibility"]))
        item["simcReady"] = False
        return item
    apply_default_catalog_variant(item, compatible_variants)
    return item


def get_websim_gear_catalog_items(conn, class_key, spec_key):
    ensure_websim_tables(conn)
    sources_by_item = gear_catalog_sources_by_item(conn)
    variants_by_item = gear_catalog_variants_by_item(conn)
    socket_options_by_slot = gear_catalog_mod_options_by_slot(conn, "socket")
    enchant_options_by_slot = gear_catalog_mod_options_by_slot(conn, "enchant")
    item_ids = sorted(set(sources_by_item.keys()) | set(variants_by_item.keys()))
    if not item_ids:
        return []
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
    catalog_items = []
    for row in rows:
        item_id = str(row[0])
        payload = safe_json_loads(row[5], {})
        raw_item = {
            "id": item_id,
            "itemId": item_id,
            "name": row[1],
            "displayName": row[1],
            "slot": row[2],
            "quality": row[3],
            "iconUrl": row[4],
            "sourceType": "catalog",
            "source": (sources_by_item.get(item_id) or [{}])[0].get("label") or "gear catalog",
            "metadataStatus": "verified",
            "metadataSource": ITEM_METADATA_SOURCE,
            "payload": payload if isinstance(payload, dict) else {},
        }
        item = normalize_gear_item(raw_item, class_key, spec_key, "catalog")
        if not item:
            continue
        item = enrich_catalog_item(
            item,
            sources_by_item.get(item_id, []),
            variants_by_item.get(item_id, []),
            socket_options_by_slot.get(item["slot"], []),
            enchant_options_by_slot.get(item["slot"], []),
            class_key,
            spec_key,
        )
        if item:
            catalog_items.append(item)
    return catalog_items


def get_websim_gear(conn, class_key="mage", spec_key="arcane"):
    season = get_active_season_payload(conn)
    class_key = slugify(class_key, "mage")
    spec_key = slugify(spec_key, "arcane")
    catalog_state = gear_catalog_sync_state(conn)
    presets = get_websim_presets(conn, class_key, spec_key)
    preset_items = []
    for preset in presets:
        preset_items.extend(preset_gear_items(preset))
    baseline_set = []
    for item in preset_gear_items(presets[0] if presets else {}):
        if item.get("slot") not in {entry.get("slot") for entry in baseline_set}:
            baseline_set.append(item)
    candidate_items = get_websim_loot(conn, {}, limit=120)["items"]
    catalog_items = get_websim_gear_catalog_items(conn, class_key, spec_key)
    baseline_set = hydrate_gear_items_from_metadata(conn, baseline_set)
    preset_items = hydrate_gear_items_from_metadata(conn, preset_items)
    candidate_items = hydrate_gear_items_from_metadata(conn, candidate_items)
    baseline_set = normalize_websim_gear_items(baseline_set, class_key, spec_key)
    preset_items = normalize_gear_item_list(preset_items, class_key, spec_key)
    candidate_items = normalize_gear_item_list(candidate_items, class_key, spec_key)
    grouped = {slot: [] for slot in CANONICAL_GEAR_SLOTS}
    for item in [*baseline_set, *preset_items, *catalog_items, *candidate_items]:
        if isinstance(item, dict) and ("variants" in item or "sources" in item):
            normalized = item
        else:
            normalized = normalize_gear_item(item, class_key, spec_key, item.get("sourceType") if isinstance(item, dict) else "")
        if normalized and normalized.get("slot") in grouped:
            grouped[normalized["slot"]].append(normalized)
    slot_groups = [
        {
            "slot": slot,
            "simcSlot": slot,
            "label": GEAR_SLOT_LABELS.get(slot, slot),
            "items": unique_gear_candidates(grouped.get(slot, []), limit=None),
        }
        for slot in CANONICAL_GEAR_SLOTS
    ]
    equipped_set = gear_items_by_slot(baseline_set, class_key, spec_key)
    readiness = gear_readiness(baseline_set)
    payload = {
        "classKey": class_key,
        "specKey": spec_key,
        "slots": gear_slot_payload(),
        "slotGroups": slot_groups,
        "replacementCandidates": slot_groups,
        "equippedSet": equipped_set,
        "slotReadiness": gear_slot_readiness(baseline_set, class_key, spec_key),
        "baselineSet": baseline_set,
        "presets": presets,
        "candidateItems": candidate_items[:24],
        "catalogItems": catalog_items[:120],
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
        "itemDatabaseRevision": catalog_state.get("itemDatabaseRevision") or "",
        "variantRevision": catalog_state.get("variantRevision") or "",
        "catalogCheckedAt": catalog_state.get("checkedAt") or "",
        "catalogBlockers": catalog_state.get("blockers") or [],
        "maxLevel": websim_max_level(),
        "checkedAt": utc_now(),
        **season_metadata_fields(season),
    }
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
    if item.get("id") and source_type in SIMC_READY_SOURCE_TYPES:
        return []
    missing = []
    if not item.get("slot"):
        missing.append("slot")
    if not item.get("id"):
        missing.append("itemId")
    if source_type in {"verifiedLoot", "loot"}:
        if item.get("variantKey") and item.get("ilevel") and any(item.get(key) for key in ("bonus_id", "gem_id", "enchant_id", "crafted_stats")):
            return missing
        missing.extend(["variantKey", "ilevel", "bonus_id/gem_id/enchant_id"])
        return missing
    if item.get("id") and item.get("ilevel") and any(item.get(key) for key in ("bonus_id", "gem_id", "enchant_id", "crafted_stats")):
        return missing
    if not item.get("ilevel"):
        missing.append("ilevel")
    if not any(item.get(key) for key in ("bonus_id", "gem_id", "enchant_id", "crafted_stats")):
        missing.append("bonus_id/gem_id/enchant_id")
    return missing


def gear_item_simc_ready(item):
    return bool(item.get("slot") and item.get("id") and not gear_item_missing_fields(item))


def gear_compatibility_from_payload(payload, class_key, simc_slot):
    if not isinstance(payload, dict) or not class_key or simc_slot not in ARMOR_SLOTS:
        return "unknown"
    item_class = payload.get("item_class") or {}
    item_subclass = payload.get("item_subclass") or {}
    item_class_name = str(item_class.get("name") or "").lower()
    subclass_name = str(item_subclass.get("name") or "")
    expected_armor = CLASS_ARMOR_TYPES.get(class_key)
    if "armor" not in item_class_name or not expected_armor or not subclass_name:
        return "unknown"
    if subclass_name.lower() in {"miscellaneous", "cosmetic"}:
        return "unknown"
    return "compatible" if subclass_name.lower() == expected_armor.lower() else "incompatible"


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
    item = {
        "slot": slot,
        "simcSlot": slot,
        "itemId": item_id,
        "name": slugify(value.get("name"), f"item_{item_id}"),
        "id": item_id,
        "displayName": str(value.get("displayName") or value.get("name") or f"Item {item_id}")[:160],
        "localizedName": str(value.get("localizedName") or value.get("displayName") or "")[:160],
        "englishName": str(value.get("englishName") or "")[:160],
        "iconUrl": str(value.get("iconUrl") or value.get("icon_url") or "")[:260],
        "quality": str(value.get("quality") or "")[:80],
        "sourceType": source_type,
        "source": str(first_matching_value(value, ["source", "sourceName", "encounterName", "instanceName"], ""))[:220],
        "metadataStatus": str(value.get("metadataStatus") or "")[:40],
        "metadataSource": str(value.get("metadataSource") or "")[:120],
        "metadataLocale": str(value.get("metadataLocale") or "")[:20],
        "classKey": slugify(class_key, "") if class_key else str(value.get("classKey") or ""),
        "specKey": slugify(spec_key, "") if spec_key else str(value.get("specKey") or ""),
    }
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
    payload = value.get("payload") if isinstance(value.get("payload"), dict) else {}
    item["compatibility"] = str(value.get("compatibility") or gear_compatibility_from_payload(payload, item["classKey"], slot) or "unknown")
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
        ]
    )


def unique_gear_candidates(items, limit=None):
    unique_items = []
    seen = set()
    for item in items or []:
        key = gear_candidate_key(item)
        if key in seen:
            continue
        seen.add(key)
        unique_items.append(item)
        if limit and len(unique_items) >= limit:
            break
    return unique_items


def build_websim_gear_lines(items):
    lines = []
    for item in normalize_websim_gear_items(items):
        if not item.get("simcReady"):
            continue
        parts = [f'{item["slot"]}={item["name"]}', f'id={item["id"]}']
        for key in ["ilevel", "bonus_id", "gem_id", "gem_bonus_id", "gem_ilevel", "enchant_id", "crafted_stats"]:
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
            items.append(item)
    return items


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


def run_websim_simcraft_process(binary, profile, timeout_seconds):
    try:
        return subprocess.run(
            [binary, "-"],
            input=profile,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except OSError:
        fallback = run_windows_fake_simc_script(binary, profile)
        if fallback:
            return fallback
        raise


def run_windows_fake_simc_script(binary, profile):
    if os.name != "nt":
        return None
    try:
        script = Path(binary).read_text(encoding="utf-8")
    except OSError:
        return None
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
    try:
        result = run_websim_simcraft_process(
            binary,
            profile,
            int_env("WOW_WEBSIM_GEAR_STATS_TIMEOUT_SECONDS", 45),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ran": False, "available": True, "summary": "", "error": str(error)}
    output = (result.stdout or result.stderr or "").strip()
    return {
        "ran": result.returncode == 0,
        "available": True,
        "rawOutput": output,
        "summary": output[:4000],
        "error": "" if result.returncode == 0 else (result.stderr or f"simc exited {result.returncode}")[:1000],
    }


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
        points_before_node = purchased_counts.get(tree_type, 0) - purchased_rank
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
    gear_selection = source.get("gearSelection") if isinstance(source.get("gearSelection"), dict) else {}
    gear_items = gear_selection.get("items") or source.get("gearItems") or []
    lines.extend(build_websim_gear_lines(normalize_websim_gear_items(gear_items, class_key, spec_key)))
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


def build_websim_profile_response(payload, conn=None):
    source = payload if isinstance(payload, dict) else {}
    class_key = slugify(source.get("classKey"), "mage")
    spec_key = slugify(source.get("specKey"), "arcane")
    gear_payload = websim_selected_gear_payload(source, class_key, spec_key)
    response = {
        "profile": build_websim_profile(payload, conn=conn),
        "gearItems": gear_payload["items"],
        "simcItems": gear_payload["simcItems"],
        "readiness": gear_payload["readiness"],
    }
    if conn is not None:
        response["talentEncoding"] = encode_websim_talents(conn, source)
    return response


def websim_selected_gear_payload(source, class_key, spec_key):
    gear_selection = source.get("gearSelection") if isinstance(source.get("gearSelection"), dict) else {}
    raw_items = gear_selection.get("items") or source.get("gearItems") or source.get("simcGearItems") or []
    items = normalize_websim_gear_items(raw_items, class_key, spec_key)
    ready_items = [item for item in items if item.get("simcReady")]
    return {
        "items": items,
        "simcItems": ready_items,
        "readiness": gear_readiness(items),
    }


def websim_gear_stats_blockers(readiness, talent_encoding):
    blockers = []
    if talent_encoding.get("status") not in {"encoded", "external"}:
        blockers.extend(talent_encoding.get("errors") or [])
        if not blockers:
            blockers.append("talent encoding failed")
    if not readiness.get("fullReady"):
        blockers.extend(readiness.get("warnings") or [])
        if not readiness.get("warnings"):
            blockers.append("selected gear is not fully SimC-ready")
    return [blocker for blocker in blockers if str(blocker or "").strip()]


def build_websim_gear_stats_response(payload, conn=None):
    source = payload if isinstance(payload, dict) else {}
    class_key = slugify(source.get("classKey"), "mage")
    spec_key = slugify(source.get("specKey"), "arcane")
    level = normalized_websim_level(source.get("level"))
    request_source = {**source, "classKey": class_key, "specKey": spec_key, "level": level}
    gear_payload = websim_selected_gear_payload(request_source, class_key, spec_key)
    readiness = gear_payload["readiness"]
    talent_encoding = encode_websim_talents(conn, request_source) if conn is not None else blank_talent_encoding("failed", "none")
    blockers = websim_gear_stats_blockers(readiness, talent_encoding)
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
    if not simc_result.get("ran"):
        return blocked_stat_snapshot(
            [simc_result.get("error") or "SimC stat snapshot could not run"],
            class_key=class_key,
            spec_key=spec_key,
            level=level,
            gear_readiness_payload=readiness,
            talent_encoding=talent_encoding,
        )

    snapshot = parse_simcraft_stat_snapshot(simc_result.get("rawOutput") or simc_result.get("summary") or "")
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
    if snapshot.get("statStatus") != "verified":
        snapshot["blockers"] = snapshot.get("blockers") or ["SimC output did not include a parseable stat snapshot"]
    return snapshot


def build_websim_simulator_request(payload, guest_id="", conn=None):
    source = payload if isinstance(payload, dict) else {}
    class_key = slugify(source.get("classKey"), "mage")
    spec_key = slugify(source.get("specKey"), "arcane")
    hero_key = hero_tree_for(class_key, spec_key, slugify(source.get("heroKey"), ""))
    talent_encoding = encode_websim_talents(conn, source) if conn is not None else blank_talent_encoding()
    talents = external_talent_import_code(source)[:400]
    scenario = selected_scenario(source.get("scenarioKey"))
    gear_payload = websim_selected_gear_payload(source, class_key, spec_key)
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

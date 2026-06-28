import ast
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from .llm_client import call_chat_completion, llm_configured, llm_model
except ImportError:
    from llm_client import call_chat_completion, llm_configured, llm_model

try:
    from .codex_worker import run_codex_job
except ImportError:
    try:
        from codex_worker import run_codex_job
    except ImportError:
        run_codex_job = None

try:
    from .simc_profile_policy import dk_default_runeforge_enchant_id
except ImportError:
    from simc_profile_policy import dk_default_runeforge_enchant_id

try:
    from .simc_preparation import apply_simc_preparation_lines, simc_preparation_payload, simc_preparation_report
except ImportError:
    from simc_preparation import apply_simc_preparation_lines, simc_preparation_payload, simc_preparation_report


DEFAULT_SIMC_VERSION_FILE = "/var/lib/wow-backend/simc-version.json"
SIMC_AGENT_FORBIDDEN_KEYS = {"html", "json", "output", "save", "xml"}
SIMC_AGENT_TALENT_LINE_KEYS = {"class_talents", "spec_talents", "hero_talents"}
SIMC_AGENT_TALENT_ENTRY_RE = re.compile(r"^\d+:[1-9]\d*$")
SIMC_AGENT_OFF_TOPIC_PATTERNS = [
    "代打",
    "卡bug",
    "卡 bug",
    "外挂",
    "脚本刷",
    "写代码",
    "剧情",
]
SIMC_AGENT_CONFIRMATION_STATUSES = {"needs_clarification", "template_ready", "off_topic"}
SIMC_AGENT_CONFIRMATION_MISSING_SLOTS = {"specialization", "itemLevel", "scenario", "talents", "gear", "profile"}
SIMC_AGENT_GEAR_SLOT_ALIASES = {
    "head": "head",
    "头": "head",
    "头部": "head",
    "neck": "neck",
    "项链": "neck",
    "肩": "shoulder",
    "肩膀": "shoulder",
    "shoulder": "shoulder",
    "shoulders": "shoulder",
    "back": "back",
    "cloak": "back",
    "披风": "back",
    "chest": "chest",
    "胸": "chest",
    "胸甲": "chest",
    "shirt": "shirt",
    "衬衣": "shirt",
    "tabard": "tabard",
    "战袍": "tabard",
    "wrist": "wrist",
    "wrists": "wrist",
    "bracer": "wrist",
    "护腕": "wrist",
    "hands": "hands",
    "hand": "hands",
    "gloves": "hands",
    "手套": "hands",
    "waist": "waist",
    "belt": "waist",
    "腰带": "waist",
    "legs": "legs",
    "leg": "legs",
    "pants": "legs",
    "腿": "legs",
    "腿部": "legs",
    "feet": "feet",
    "boots": "feet",
    "脚": "feet",
    "鞋": "feet",
    "finger1": "finger1",
    "finger_1": "finger1",
    "ring1": "finger1",
    "戒指1": "finger1",
    "戒指 1": "finger1",
    "finger2": "finger2",
    "finger_2": "finger2",
    "ring2": "finger2",
    "戒指2": "finger2",
    "戒指 2": "finger2",
    "trinket1": "trinket1",
    "trinket_1": "trinket1",
    "饰品1": "trinket1",
    "饰品 1": "trinket1",
    "trinket2": "trinket2",
    "trinket_2": "trinket2",
    "饰品2": "trinket2",
    "饰品 2": "trinket2",
    "main_hand": "main_hand",
    "mainhand": "main_hand",
    "main hand": "main_hand",
    "weapon": "main_hand",
    "武器": "main_hand",
    "主手": "main_hand",
    "off_hand": "off_hand",
    "offhand": "off_hand",
    "off hand": "off_hand",
    "副手": "off_hand",
}
SIMC_AGENT_HERO_TALENT_ALIASES = [
    {
        "key": "rider_of_the_apocalypse",
        "label": "天启",
        "class": "deathknight",
        "spec": "unholy",
        "aliases": ["天启", "天启邪dk", "天启邪恶dk", "天启骑士", "天启流派"],
    },
]
WOWGG_MYTHIC_PLUS_SAMPLE_WINDOW = "WoW.gg Midnight Mythic+ All Dungeons, All Keys, Week 12; last update 2026-06-10 10:46."
WOWGG_MYTHIC_PLUS_SNAPSHOT = {
    "deathknight-blood": {"specName": "鲜血死亡骑士", "role": "tank", "avgDps": "105K", "maxDps": "147K", "maxKey": "+22", "sourcePath": "tank"},
    "deathknight-frost": {"specName": "冰霜死亡骑士", "role": "dps", "avgDps": "160K", "maxDps": "255K", "maxKey": "+22", "sourcePath": "dps"},
    "deathknight-unholy": {"specName": "邪恶死亡骑士", "role": "dps", "avgDps": "206K", "maxDps": "299K", "maxKey": "+24", "sourcePath": "dps"},
    "demonhunter-havoc": {"specName": "浩劫恶魔猎手", "role": "dps", "avgDps": "171K", "maxDps": "245K", "maxKey": "+23", "sourcePath": "dps"},
    "demonhunter-vengeance": {"specName": "复仇恶魔猎手", "role": "tank", "avgDps": "104K", "maxDps": "162K", "maxKey": "+22", "sourcePath": "tank"},
    "druid-balance": {"specName": "平衡德鲁伊", "role": "dps", "avgDps": "156K", "maxDps": "231K", "maxKey": "+22", "sourcePath": "dps"},
    "druid-feral": {"specName": "野性德鲁伊", "role": "dps", "avgDps": "175K", "maxDps": "280K", "maxKey": "+24", "sourcePath": "dps"},
    "druid-guardian": {"specName": "守护德鲁伊", "role": "tank", "avgDps": "120K", "maxDps": "213K", "maxKey": "+24", "sourcePath": "tank"},
    "druid-restoration": {"specName": "恢复德鲁伊", "role": "healer", "avgDps": "36K", "avgHps": "93K", "maxDps": "137K", "maxHps": "137K", "maxKey": "+22", "sourcePath": "healer"},
    "evoker-devastation": {"specName": "湮灭唤魔师", "role": "dps", "avgDps": "142K", "maxDps": "201K", "maxKey": "+21", "sourcePath": "dps"},
    "evoker-preservation": {"specName": "恩护唤魔师", "role": "healer", "avgDps": "43K", "avgHps": "84K", "maxDps": "126K", "maxHps": "126K", "maxKey": "+22", "sourcePath": "healer"},
    "evoker-augmentation": {"specName": "增辉唤魔师", "role": "dps", "avgDps": "180K", "maxDps": "291K", "maxKey": "+24", "sourcePath": "dps"},
    "hunter-beast_mastery": {"specName": "野兽控制猎人", "role": "dps", "avgDps": "179K", "maxDps": "264K", "maxKey": "+23", "sourcePath": "dps"},
    "hunter-marksmanship": {"specName": "射击猎人", "role": "dps", "avgDps": "162K", "maxDps": "250K", "maxKey": "+23", "sourcePath": "dps"},
    "hunter-survival": {"specName": "生存猎人", "role": "dps", "avgDps": "174K", "maxDps": "238K", "maxKey": "+23", "sourcePath": "dps"},
    "mage-arcane": {"specName": "奥术法师", "role": "dps", "avgDps": "158K", "maxDps": "235K", "maxKey": "+23", "sourcePath": "dps"},
    "mage-fire": {"specName": "火焰法师", "role": "dps", "avgDps": "146K", "maxDps": "210K", "maxKey": "+21", "sourcePath": "dps"},
    "mage-frost": {"specName": "冰霜法师", "role": "dps", "avgDps": "164K", "maxDps": "222K", "maxKey": "+23", "sourcePath": "dps"},
    "monk-brewmaster": {"specName": "酒仙武僧", "role": "tank", "avgDps": "108K", "maxDps": "154K", "maxKey": "+24", "sourcePath": "tank"},
    "monk-mistweaver": {"specName": "织雾武僧", "role": "healer", "avgDps": "53K", "avgHps": "107K", "maxDps": "161K", "maxHps": "161K", "maxKey": "+24", "sourcePath": "healer"},
    "monk-windwalker": {"specName": "踏风武僧", "role": "dps", "avgDps": "172K", "maxDps": "249K", "maxKey": "+22", "sourcePath": "dps"},
    "paladin-holy": {"specName": "神圣圣骑士", "role": "healer", "avgDps": "31K", "avgHps": "83K", "maxDps": "115K", "maxHps": "115K", "maxKey": "+22", "sourcePath": "healer"},
    "paladin-protection": {"specName": "防护圣骑士", "role": "tank", "avgDps": "104K", "maxDps": "179K", "maxKey": "+22", "sourcePath": "tank"},
    "paladin-retribution": {"specName": "惩戒圣骑士", "role": "dps", "avgDps": "186K", "maxDps": "260K", "maxKey": "+23", "sourcePath": "dps"},
    "priest-discipline": {"specName": "戒律牧师", "role": "healer", "avgDps": "33K", "avgHps": "98K", "maxDps": "141K", "maxHps": "141K", "maxKey": "+23", "sourcePath": "healer"},
    "priest-holy": {"specName": "神圣牧师", "role": "healer", "avgDps": "32K", "avgHps": "79K", "maxDps": "114K", "maxHps": "114K", "maxKey": "+22", "sourcePath": "healer"},
    "priest-shadow": {"specName": "暗影牧师", "role": "dps", "avgDps": "168K", "maxDps": "254K", "maxKey": "+23", "sourcePath": "dps"},
    "rogue-assassination": {"specName": "刺杀潜行者", "role": "dps", "avgDps": "166K", "maxDps": "268K", "maxKey": "+23", "sourcePath": "dps"},
    "rogue-outlaw": {"specName": "狂徒潜行者", "role": "dps", "avgDps": "176K", "maxDps": "280K", "maxKey": "+24", "sourcePath": "dps"},
    "rogue-subtlety": {"specName": "敏锐潜行者", "role": "dps", "avgDps": "173K", "maxDps": "241K", "maxKey": "+23", "sourcePath": "dps"},
    "shaman-elemental": {"specName": "元素萨满祭司", "role": "dps", "avgDps": "168K", "maxDps": "250K", "maxKey": "+23", "sourcePath": "dps"},
    "shaman-enhancement": {"specName": "增强萨满祭司", "role": "dps", "avgDps": "172K", "maxDps": "242K", "maxKey": "+23", "sourcePath": "dps"},
    "shaman-restoration": {"specName": "恢复萨满祭司", "role": "healer", "avgDps": "32K", "avgHps": "88K", "maxDps": "125K", "maxHps": "125K", "maxKey": "+24", "sourcePath": "healer"},
    "warlock-affliction": {"specName": "痛苦术士", "role": "dps", "avgDps": "173K", "maxDps": "243K", "maxKey": "+22", "sourcePath": "dps"},
    "warlock-demonology": {"specName": "恶魔学识术士", "role": "dps", "avgDps": "194K", "maxDps": "277K", "maxKey": "+23", "sourcePath": "dps"},
    "warlock-destruction": {"specName": "毁灭术士", "role": "dps", "avgDps": "148K", "maxDps": "245K", "maxKey": "+21", "sourcePath": "dps"},
    "warrior-arms": {"specName": "武器战士", "role": "dps", "avgDps": "184K", "maxDps": "298K", "maxKey": "+24", "sourcePath": "dps"},
    "warrior-fury": {"specName": "狂怒战士", "role": "dps", "avgDps": "173K", "maxDps": "288K", "maxKey": "+23", "sourcePath": "dps"},
    "warrior-protection": {"specName": "防护战士", "role": "tank", "avgDps": "101K", "maxDps": "167K", "maxKey": "+22", "sourcePath": "tank"},
}


def mythic_plus_source_url(source_path):
    return f"https://wow.gg/meta/mythic-plus/{source_path}"


def mythic_plus_reference_comparison_text(reference):
    if not reference:
        return ""
    if reference.get("role") == "healer":
        return (
            f"Avg DPS {reference.get('avgDps', '')}，"
            f"Avg HPS {reference.get('avgHps', '')}，Max HPS {reference.get('maxHps', '')}"
        )
    return f"Avg DPS {reference.get('avgDps', '')}，Max DPS {reference.get('maxDps', '')}"


def build_wowgg_mythic_plus_reference(spec_key, row):
    comparison = mythic_plus_reference_comparison_text(row)
    role_note = "治疗专精同时展示伤害贡献和治疗吞吐，不能只用 DPS 评价。" if row.get("role") == "healer" else "真实大秘境对标应落在该来源的 Avg/Max 量级附近。"
    reference = {
        "specKey": spec_key,
        "specName": row["specName"],
        "role": row["role"],
        "avgDps": row["avgDps"],
        "maxDps": row["maxDps"],
        "maxKey": row["maxKey"],
        "sampleWindow": WOWGG_MYTHIC_PLUS_SAMPLE_WINDOW,
        "comparisonText": comparison,
        "notes": [
            role_note,
            "最终报告必须先和真实大秘境样本量级比较，禁止输出数百万级或来源不支持的结论。",
        ],
        "sources": [
            {
                "name": f"WoW.gg Mythic+ {row['role'].title()} Tier List",
                "url": mythic_plus_source_url(row["sourcePath"]),
                "evidence": f"{row['specName']}: {comparison}, max key {row['maxKey']}.",
            },
            {
                "name": "WoW.gg Meta FAQ",
                "url": mythic_plus_source_url(row["sourcePath"]),
                "evidence": "All Dungeons merges top Mythic+ players and the meta is based on real in-game statistics; weekly snapshot updates after reset and within-week updates every 8 hours.",
            },
        ],
    }
    if row.get("avgHps"):
        reference["avgHps"] = row["avgHps"]
        reference["maxHps"] = row["maxHps"]
    return reference


MYTHIC_PLUS_DPS_REFERENCES = {
    spec_key: build_wowgg_mythic_plus_reference(spec_key, row)
    for spec_key, row in WOWGG_MYTHIC_PLUS_SNAPSHOT.items()
}

SIMC_AGENT_CLASS_REGISTRY = [
    {
        "label": "死亡骑士",
        "key": "deathknight",
        "aliases": ["死亡骑士", "dk", "death knight"],
        "specs": [
            {"label": "鲜血", "key": "blood", "role": "tank", "aliases": ["血dk", "血死亡骑士", "blood death knight"]},
            {"label": "冰霜", "key": "frost", "role": "attack", "aliases": ["冰dk", "冰霜dk", "frost death knight"]},
            {"label": "邪恶", "key": "unholy", "role": "attack", "aliases": ["邪dk", "邪恶dk", "unholy death knight"]},
        ],
    },
    {
        "label": "恶魔猎手",
        "key": "demonhunter",
        "aliases": ["恶魔猎手", "dh", "demon hunter"],
        "specs": [
            {"label": "浩劫", "key": "havoc", "role": "attack", "aliases": ["浩劫dh", "havoc demon hunter"]},
            {"label": "复仇", "key": "vengeance", "role": "tank", "aliases": ["复仇dh", "vengeance demon hunter"]},
        ],
    },
    {
        "label": "德鲁伊",
        "key": "druid",
        "aliases": ["德鲁伊", "小德", "druid"],
        "specs": [
            {"label": "平衡", "key": "balance", "role": "spell", "aliases": ["鸟德", "平衡德", "balance druid"]},
            {"label": "野性", "key": "feral", "role": "attack", "aliases": ["猫德", "野德", "feral druid"]},
            {"label": "守护", "key": "guardian", "role": "tank", "aliases": ["熊德", "守护德", "guardian druid"]},
            {"label": "恢复", "key": "restoration", "role": "heal", "aliases": ["奶德", "恢复德", "restoration druid"]},
        ],
    },
    {
        "label": "唤魔师",
        "key": "evoker",
        "aliases": ["唤魔师", "龙希尔", "evoker"],
        "specs": [
            {"label": "湮灭", "key": "devastation", "role": "spell", "aliases": ["湮灭龙", "devastation evoker"]},
            {"label": "恩护", "key": "preservation", "role": "heal", "aliases": ["奶龙", "恩护龙", "preservation evoker"]},
            {"label": "增辉", "key": "augmentation", "role": "spell", "aliases": ["增辉龙", "augmentation evoker"]},
        ],
    },
    {
        "label": "猎人",
        "key": "hunter",
        "aliases": ["猎人", "hunter"],
        "specs": [
            {"label": "野兽控制", "key": "beast_mastery", "role": "attack", "aliases": ["兽王", "兽王猎", "beast mastery hunter"]},
            {"label": "射击", "key": "marksmanship", "role": "attack", "aliases": ["射击猎", "marksmanship hunter"]},
            {"label": "生存", "key": "survival", "role": "attack", "aliases": ["生存猎", "survival hunter"]},
        ],
    },
    {
        "label": "法师",
        "key": "mage",
        "aliases": ["法师", "mage"],
        "specs": [
            {"label": "奥术", "key": "arcane", "role": "spell", "aliases": ["奥法", "arcane mage"]},
            {"label": "火焰", "key": "fire", "role": "spell", "aliases": ["火法", "fire mage"]},
            {"label": "冰霜", "key": "frost", "role": "spell", "aliases": ["冰法", "frost mage"]},
        ],
    },
    {
        "label": "武僧",
        "key": "monk",
        "aliases": ["武僧", "monk"],
        "specs": [
            {"label": "酒仙", "key": "brewmaster", "role": "tank", "aliases": ["酒仙武僧", "brewmaster monk"]},
            {"label": "织雾", "key": "mistweaver", "role": "heal", "aliases": ["奶僧", "织雾武僧", "mistweaver monk"]},
            {"label": "踏风", "key": "windwalker", "role": "attack", "aliases": ["踏风武僧", "windwalker monk"]},
        ],
    },
    {
        "label": "圣骑士",
        "key": "paladin",
        "aliases": ["圣骑士", "圣骑", "骑士", "paladin"],
        "specs": [
            {"label": "神圣", "key": "holy", "role": "heal", "aliases": ["奶骑", "神圣骑", "holy paladin"]},
            {"label": "防护", "key": "protection", "role": "tank", "aliases": ["防骑", "防护骑", "protection paladin"]},
            {"label": "惩戒", "key": "retribution", "role": "attack", "aliases": ["惩戒骑", "retribution paladin"]},
        ],
    },
    {
        "label": "牧师",
        "key": "priest",
        "aliases": ["牧师", "priest"],
        "specs": [
            {"label": "戒律", "key": "discipline", "role": "heal", "aliases": ["戒律牧", "discipline priest"]},
            {"label": "神圣", "key": "holy", "role": "heal", "aliases": ["神牧", "神圣牧", "holy priest"]},
            {"label": "暗影", "key": "shadow", "role": "spell", "aliases": ["暗牧", "shadow priest"]},
        ],
    },
    {
        "label": "潜行者",
        "key": "rogue",
        "aliases": ["潜行者", "盗贼", "rogue"],
        "specs": [
            {"label": "刺杀", "key": "assassination", "role": "attack", "aliases": ["刺杀贼", "assassination rogue"]},
            {"label": "狂徒", "key": "outlaw", "role": "attack", "aliases": ["狂徒贼", "outlaw rogue"]},
            {"label": "敏锐", "key": "subtlety", "role": "attack", "aliases": ["敏锐贼", "subtlety rogue"]},
        ],
    },
    {
        "label": "萨满祭司",
        "key": "shaman",
        "aliases": ["萨满祭司", "萨满", "shaman"],
        "specs": [
            {"label": "元素", "key": "elemental", "role": "spell", "aliases": ["元素萨", "风暴元素萨", "elemental shaman"]},
            {"label": "增强", "key": "enhancement", "role": "attack", "aliases": ["增强萨", "enhancement shaman"]},
            {"label": "恢复", "key": "restoration", "role": "heal", "aliases": ["奶萨", "恢复萨", "restoration shaman"]},
        ],
    },
    {
        "label": "术士",
        "key": "warlock",
        "aliases": ["术士", "warlock"],
        "specs": [
            {"label": "痛苦", "key": "affliction", "role": "spell", "aliases": ["痛苦术", "affliction warlock"]},
            {"label": "恶魔学识", "key": "demonology", "role": "spell", "aliases": ["恶魔术", "恶魔术士", "demonology warlock"]},
            {"label": "毁灭", "key": "destruction", "role": "spell", "aliases": ["毁灭术", "destruction warlock"]},
        ],
    },
    {
        "label": "战士",
        "key": "warrior",
        "aliases": ["战士", "warrior"],
        "specs": [
            {"label": "武器", "key": "arms", "role": "attack", "aliases": ["武器战", "arms warrior"]},
            {"label": "狂怒", "key": "fury", "role": "attack", "aliases": ["狂暴战", "狂怒战", "fury warrior"]},
            {"label": "防护", "key": "protection", "role": "tank", "aliases": ["防战", "防护战", "protection warrior"]},
        ],
    },
]


def simc_agent_actor_name(player_class, spec):
    return "Generated_" + "_".join(part.capitalize() for part in f"{spec}_{player_class}".split("_"))


def build_simc_agent_class_patterns():
    return [
        {
            "patterns": entry["aliases"],
            "class": entry["key"],
            "label": entry["label"],
            "specs": [spec["label"] for spec in entry["specs"]],
        }
        for entry in SIMC_AGENT_CLASS_REGISTRY
    ]


def build_simc_agent_spec_patterns():
    patterns = []
    for class_entry in SIMC_AGENT_CLASS_REGISTRY:
        for spec in class_entry["specs"]:
            spec_patterns = [
                f'{spec["label"]}{class_entry["label"]}',
                f'{class_entry["label"]}{spec["label"]}',
                *spec["aliases"],
            ]
            patterns.append({
                "patterns": spec_patterns,
                "class": class_entry["key"],
                "classLabel": class_entry["label"],
                "spec": spec["key"],
                "specLabel": spec["label"],
                "actor": simc_agent_actor_name(class_entry["key"], spec["key"]),
                "role": spec["role"],
            })
    return patterns


SIMC_AGENT_CLASS_PATTERNS = build_simc_agent_class_patterns()
SIMC_AGENT_SPEC_PATTERNS = build_simc_agent_spec_patterns()
SIMC_AGENT_CLASS_KEYS = {entry["key"] for entry in SIMC_AGENT_CLASS_REGISTRY}
SIMC_PROFILE_RACE_KEYS = {
    "blood_elf",
    "dark_iron_dwarf",
    "draenei",
    "dracthyr",
    "dwarf",
    "earthen",
    "gnome",
    "goblin",
    "highmountain_tauren",
    "human",
    "kul_tiran",
    "lightforged_draenei",
    "maghar_orc",
    "mechagnome",
    "night_elf",
    "nightborne",
    "orc",
    "pandaren",
    "pandaren_alliance",
    "pandaren_horde",
    "tauren",
    "troll",
    "undead",
    "void_elf",
    "vulpera",
    "worgen",
    "zandalari_troll",
}
SIMC_PROFILE_RACE_ALIASES = {
    "draenai": "draenei",
}
SIMC_AGENT_DEFAULT_RACE_BY_CLASS = {
    "deathknight": "orc",
    "demonhunter": "night_elf",
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
SIMC_AGENT_SPEC_BY_KEY = {
    f'{entry["key"]}-{spec["key"]}': {
        "class": entry["key"],
        "classLabel": entry["label"],
        "spec": spec["key"],
        "specLabel": spec["label"],
        "role": spec["role"],
        "actor": simc_agent_actor_name(entry["key"], spec["key"]),
    }
    for entry in SIMC_AGENT_CLASS_REGISTRY
    for spec in entry["specs"]
}
SIMC_AGENT_CLASS_QUICK_REPLIES = {
    entry["key"]: [
        f'我是{(spec["aliases"] or [spec["label"] + entry["label"]])[0]}，看大秘境 AOE'
        for spec in entry["specs"]
    ]
    for entry in SIMC_AGENT_CLASS_REGISTRY
}

GENERIC_MYTHIC_PLUS_REFERENCE_SOURCES = [
    {
        "name": "Raider.IO Mythic+ Rankings",
        "url": "https://raider.io/mythic-plus-rankings",
        "evidence": "用于核对高层大秘境角色、队伍和专精样本；精确 DPS 需要按专精与时间窗口实时刷新。",
    },
    {
        "name": "Warcraft Logs Mythic+ Rankings",
        "url": "https://www.warcraftlogs.com/zone/rankings/latest",
        "evidence": "用于核对近两周同专精、相近层数、相近装等的真实战斗日志。",
    },
    {
        "name": "Archon Mythic+ Rankings",
        "url": "https://www.archon.gg/wow",
        "evidence": "基于 Warcraft Logs 聚合职业专精和大秘境样本，适合作为报告前的量级校验。",
    },
]


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def int_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def truthy_env(name):
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def is_simcraft_mode(mode):
    return "simcraft" in str(mode or "").lower()


def simc_binary():
    configured = os.environ.get("WOW_SIMC_BIN")
    if configured:
        return configured if os.path.exists(configured) else ""
    return shutil.which("simc") or shutil.which("simulationcraft") or ""


def simc_version_status():
    path = Path(os.environ.get("WOW_SIMC_VERSION_FILE", DEFAULT_SIMC_VERSION_FILE))
    status = {
        "checkedAt": "",
        "localTag": "",
        "latestTag": "",
        "updateAvailable": False,
        "source": "none",
        "image": "",
    }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return status
    for key in status:
        if key in payload:
            status[key] = payload[key]
    status["updateAvailable"] = bool(status["updateAvailable"])
    return status


def looks_like_simc_profile_line(line):
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    if "=" not in stripped:
        return False
    key = stripped.split("=", 1)[0].strip()
    if key in {"talents", "gear_ilvl", "race", "role", "level", "spec", "profile_set"}:
        return True
    if key == "copy" or key.startswith(("gear_", "profileset.")):
        return True
    return key.replace("_", "").replace("-", "").isalnum() and stripped.count('"') >= 2


def extract_fenced_simc_profile(lines):
    in_simc_fence = False
    profile_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            fence_language = stripped[3:].strip().lower()
            if in_simc_fence:
                break
            in_simc_fence = fence_language in {"simc", "simulationcraft"}
            continue
        if in_simc_fence:
            profile_lines.append(line.rstrip())
    return "\n".join(profile_lines).strip()


def extract_simc_profile_from_prompt(prompt):
    lines = str(prompt or "").splitlines()
    fenced_profile = extract_fenced_simc_profile(lines)
    if fenced_profile:
        return fenced_profile

    start_index = -1
    for index, line in enumerate(lines):
        if looks_like_simc_profile_line(line):
            start_index = index
            break
    if start_index < 0:
        return ""

    profile_lines = []
    for line in lines[start_index:]:
        if line.strip().startswith("```"):
            break
        profile_lines.append(line.rstrip())
    return "\n".join(profile_lines).strip()


def normalize_agent_round(value):
    try:
        round_number = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, min(round_number, 99))


def simc_agent_message(source):
    return str(source.get("message") or source.get("prompt") or source.get("question") or "").strip()


def is_simc_agent_off_topic(text):
    lowered = str(text or "").lower()
    return any(pattern in lowered for pattern in SIMC_AGENT_OFF_TOPIC_PATTERNS)


def infer_simc_agent_intent(text):
    lowered = str(text or "").lower()
    if is_simc_agent_off_topic(lowered):
        return "out_of_scope"
    if any(keyword in lowered for keyword in ["属性", "急速", "精通", "暴击", "全能", "scale", "权重"]):
        return "stat_weights"
    if any(keyword in lowered for keyword in ["饰品", "装备", "武器", "换不换", "配装"]):
        return "gear_compare"
    if "天赋" in lowered:
        return "talent_compare"
    return "baseline"


def infer_simc_agent_scenario(text):
    lowered = str(text or "").lower()
    duration = 300
    duration_match = re.search(r"(\d+)\s*分钟", lowered)
    if duration_match:
        duration = max(60, min(900, int(duration_match.group(1)) * 60))
    if any(keyword in lowered for keyword in ["大秘境", "aoe", "群体", "多目标", "五目标", "5目标"]):
        return {
            "fightStyle": "HecticAddCleave",
            "durationSeconds": duration,
            "targets": 5,
            "label": "大秘境多目标",
        }
    return {
        "fightStyle": "Patchwerk",
        "durationSeconds": duration,
        "targets": 1,
        "label": "单体基准",
    }


def has_explicit_simc_agent_scenario(text):
    lowered = str(text or "").lower()
    return any(keyword in lowered for keyword in [
        "大秘境",
        "aoe",
        "群体",
        "多目标",
        "五目标",
        "5目标",
        "单体",
        "团本",
        "boss",
        "首领",
        "patchwerk",
    ])


def infer_simc_agent_specialization(text):
    lowered = str(text or "").lower()
    compact = re.sub(r"\s+", "", lowered)
    latest_entry = None
    latest_index = -1
    for entry in SIMC_AGENT_SPEC_PATTERNS:
        for pattern in entry["patterns"]:
            index = compact.rfind(pattern.lower().replace(" ", ""))
            if index > latest_index:
                latest_entry = entry
                latest_index = index
    return latest_entry


def infer_simc_agent_class(text):
    lowered = str(text or "").lower()
    compact = re.sub(r"\s+", "", lowered)
    spec_info = infer_simc_agent_specialization(text)
    if spec_info:
        return next((entry for entry in SIMC_AGENT_CLASS_PATTERNS if entry["class"] == spec_info["class"]), None)
    for entry in SIMC_AGENT_CLASS_PATTERNS:
        if any(pattern.lower().replace(" ", "") in compact for pattern in entry["patterns"]):
            return entry
    return None


def infer_simc_agent_item_level(text):
    lowered = str(text or "").lower()
    explicit = re.search(r"(\d{2,4})\s*(?:装等|ilvl|item\s*level)", lowered)
    if explicit:
        return max(1, min(999, int(explicit.group(1))))
    if infer_simc_agent_class(text) or infer_simc_agent_specialization(text):
        generic = re.search(r"(?<!第)([1-9]\d{2})(?!\d)", lowered)
        if generic:
            return max(1, min(999, int(generic.group(1))))
    return int_env("WOW_SIMC_AGENT_DEFAULT_ITEM_LEVEL", 700)


def has_explicit_simc_agent_item_level(text):
    lowered = str(text or "").lower()
    if re.search(r"(\d{2,4})\s*(?:装等|ilvl|item\s*level)", lowered):
        return True
    if infer_simc_agent_class(text) or infer_simc_agent_specialization(text):
        return bool(re.search(r"(?<!第)([1-9]\d{2})(?!\d)", lowered))
    return False


def infer_simc_agent_hero_talent(text, spec_info=None):
    lowered = str(text or "").lower()
    compact = re.sub(r"\s+", "", lowered)
    for entry in SIMC_AGENT_HERO_TALENT_ALIASES:
        if spec_info and entry.get("class") and entry["class"] != spec_info.get("class"):
            continue
        if spec_info and entry.get("spec") and entry["spec"] != spec_info.get("spec"):
            continue
        if any(alias.lower().replace(" ", "") in compact for alias in entry["aliases"]):
            return entry
    return None


def build_agent_filled_slots(text, spec_info, scenario, item_level):
    class_info = infer_simc_agent_class(text)
    hero_talent = infer_simc_agent_hero_talent(text, spec_info)
    slots = {
        "class": (spec_info or {}).get("class") or ((class_info or {}).get("class") or ""),
        "classLabel": (spec_info or {}).get("classLabel") or ((class_info or {}).get("label") or ""),
        "spec": (spec_info or {}).get("spec") or "",
        "specLabel": (spec_info or {}).get("specLabel") or "",
        "itemLevel": item_level,
        "scenario": scenario.get("label", ""),
        "fightStyle": scenario.get("fightStyle", ""),
        "targets": scenario.get("targets", 1),
    }
    if hero_talent:
        slots["heroTalent"] = hero_talent["label"]
        slots["heroTalentKey"] = hero_talent["key"]
    return slots


def clean_context_value(value, limit=240):
    return str(value or "").strip()[:limit]


def normalize_simc_race(value):
    key = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")
    key = SIMC_PROFILE_RACE_ALIASES.get(key, key)
    return key if key in SIMC_PROFILE_RACE_KEYS else ""


def default_simc_race_for_class(class_key):
    return SIMC_AGENT_DEFAULT_RACE_BY_CLASS.get(str(class_key or "").strip(), "troll")


def clean_context_list(values, limit=6):
    if not isinstance(values, list):
        return []
    return [clean_context_value(item, 120) for item in values[:limit] if clean_context_value(item, 120)]


def clean_context_simc_lines(values, limit=8):
    if not isinstance(values, list):
        return []
    lines = []
    for item in values[:limit]:
        line = clean_context_value(item, 6000)
        if line and "=" in line:
            lines.append(line)
    return lines


def clean_context_rows(values, fields, limit=6):
    if not isinstance(values, list):
        return []
    rows = []
    for row in values[:limit]:
        if not isinstance(row, dict):
            continue
        cleaned = {
            field: clean_context_value(row.get(field), 180)
            for field in fields
            if clean_context_value(row.get(field), 180)
        }
        if cleaned:
            rows.append(cleaned)
    return rows


def first_present(source, keys, default=""):
    if not isinstance(source, dict):
        return default
    for key in keys:
        if key in source and source.get(key) not in (None, ""):
            return source.get(key)
    return default


def normalize_simc_slot(value):
    key = re.sub(r"\s+", " ", str(value or "").strip().lower())
    if not key:
        return ""
    return SIMC_AGENT_GEAR_SLOT_ALIASES.get(key) or SIMC_AGENT_GEAR_SLOT_ALIASES.get(key.replace("-", "_")) or ""


def sanitize_simc_item_name(value, item_id=""):
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    if text:
        return text[:80]
    if item_id:
        return f"item_{item_id}"
    return "selected_item"


def normalize_simc_option_value(value):
    if isinstance(value, list):
        values = [normalize_simc_option_value(item) for item in value]
        return "/".join(item for item in values if item)
    text = str(value or "").strip()
    if not text:
        return ""
    return re.sub(r"[^A-Za-z0-9_:/.-]+", "", text)[:240]


def normalize_simc_gear_item(value):
    if not isinstance(value, dict):
        return None
    slot = normalize_simc_slot(first_present(value, ["slot", "slotKey", "equipmentSlot"]))
    item_id = normalize_simc_option_value(first_present(value, ["id", "itemId", "item_id"]))
    if not slot or not item_id:
        return None

    item = {
        "slot": slot,
        "name": sanitize_simc_item_name(first_present(value, ["name", "itemName", "displayName"]), item_id),
        "id": item_id,
    }
    option_fields = [
        ("ilevel", ["ilevel", "itemLevel", "item_level"]),
        ("bonus_id", ["bonus_id", "bonusId", "bonusIds", "bonusListIDs"]),
        ("gem_id", ["gem_id", "gemId", "gemIds"]),
        ("gem_bonus_id", ["gem_bonus_id", "gemBonusId", "gemBonusIds"]),
        ("gem_ilevel", ["gem_ilevel", "gemIlevel", "gemItemLevel", "gemItemLevels"]),
        ("enchant_id", ["enchant_id", "enchantId", "enchant"]),
        ("crafted_stats", ["crafted_stats", "craftedStats"]),
        ("embellishment", ["embellishment"]),
        ("source", ["source", "sourceName"]),
    ]
    for option_key, source_keys in option_fields:
        option_value = normalize_simc_option_value(first_present(value, source_keys))
        if option_value:
            item[option_key] = option_value
    return item


def clean_simc_gear_items(values, limit=20):
    if not isinstance(values, list):
        return []
    items = []
    seen_slots = set()
    for value in values:
        item = normalize_simc_gear_item(value)
        if not item or item["slot"] in seen_slots:
            continue
        seen_slots.add(item["slot"])
        items.append(item)
        if len(items) >= limit:
            break
    return items


def build_simc_gear_lines(items):
    lines = []
    for item in items or []:
        if not isinstance(item, dict) or not item.get("slot") or not item.get("id"):
            continue
        parts = [f'{item["slot"]}={item.get("name") or "selected_item"}', f'id={item["id"]}']
        for option_key in ["ilevel", "bonus_id", "gem_id", "gem_bonus_id", "gem_ilevel", "enchant_id", "crafted_stats", "embellishment", "source"]:
            if item.get(option_key):
                parts.append(f"{option_key}={item[option_key]}")
        lines.append(",".join(parts))
    return lines


def simc_profile_items_with_class_defaults(items, spec_info):
    if not isinstance(spec_info, dict):
        return items or []
    result = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        next_item = dict(item)
        default_runeforge = dk_default_runeforge_enchant_id(
            spec_info.get("class"),
            spec_info.get("spec"),
            next_item.get("slot") or next_item.get("simcSlot"),
        )
        if default_runeforge and not next_item.get("enchant_id"):
            next_item["enchant_id"] = default_runeforge
        result.append(next_item)
    return result


def normalize_build_context(value):
    if not isinstance(value, dict):
        return None
    details = value.get("details") if isinstance(value.get("details"), dict) else {}
    talents = details.get("talents") if isinstance(details.get("talents"), dict) else {}
    gear = details.get("gear") if isinstance(details.get("gear"), dict) else {}
    stat_weights = details.get("statWeights") if isinstance(details.get("statWeights"), dict) else {}
    simulator_state = value.get("simulatorState") if isinstance(value.get("simulatorState"), dict) else {}
    simulator_talent = simulator_state.get("talent") if isinstance(simulator_state.get("talent"), dict) else {}
    simulator_gear = simulator_state.get("gear") if isinstance(simulator_state.get("gear"), dict) else {}
    profile_options = simulator_state.get("profileOptions") if isinstance(simulator_state.get("profileOptions"), dict) else {}
    race_key = normalize_simc_race(
        first_present(value, ["raceKey", "race"])
        or first_present(profile_options, ["raceKey", "race"])
    )
    race_name = clean_context_value(value.get("raceName") or profile_options.get("raceName"), 80)
    gear_items = clean_simc_gear_items(
        first_present(gear, ["simcItems", "selectedItems", "items"], [])
        or first_present(simulator_gear, ["selectedItems", "simcItems", "items"], [])
    )
    return {
        "specId": clean_context_value(value.get("specId"), 80),
        "className": clean_context_value(value.get("className"), 40),
        "specName": clean_context_value(value.get("specName"), 40),
        "raceKey": race_key,
        "raceName": race_name,
        "role": clean_context_value(value.get("role"), 40),
        "activeQueryKey": clean_context_value(value.get("activeQueryKey"), 40),
        "activeQueryTitle": clean_context_value(value.get("activeQueryTitle"), 80),
        "sourceName": clean_context_value(value.get("sourceName"), 80),
        "publishedAt": clean_context_value(value.get("publishedAt"), 40),
        "analysisWindow": clean_context_value(value.get("analysisWindow"), 260),
        "sourceNote": clean_context_value(value.get("sourceNote"), 260),
        "details": {
            "talents": {
                "importCode": clean_context_value(talents.get("importCode"), 400),
                "simcLines": clean_context_simc_lines(talents.get("simcLines"), 8),
                "encodingStatus": clean_context_value(talents.get("encodingStatus"), 40),
                "sourceName": clean_context_value(talents.get("sourceName"), 80),
                "sourceUrl": clean_context_value(talents.get("sourceUrl"), 180),
                "coreTalents": clean_context_list(talents.get("coreTalents"), 8),
            },
            "gear": {
                "gear": clean_context_rows(gear.get("gear"), ["slot", "name", "source"], 8),
                "simcItems": gear_items,
            },
            "statWeights": {
                "stats": clean_context_rows(stat_weights.get("stats"), ["name", "value", "percent"], 6),
            },
        },
        "simulatorState": {
            "profileOptions": {
                "raceKey": race_key,
                "raceName": race_name,
            },
            "talent": {
                "selectedNodes": clean_context_rows(simulator_talent.get("selectedNodes"), ["id", "rank", "tree", "name"], 120),
                "websimExportCode": clean_context_value(simulator_talent.get("websimExportCode"), 1200),
                "heroKey": clean_context_value(simulator_talent.get("heroKey"), 80),
                "scenarioKey": clean_context_value(simulator_talent.get("scenarioKey"), 80),
                "encodingStatus": clean_context_value(simulator_talent.get("encodingStatus"), 40),
                "simcLines": clean_context_simc_lines(simulator_talent.get("simcLines"), 8),
                "importCode": clean_context_value(simulator_talent.get("importCode"), 400),
                "summary": clean_context_value(simulator_talent.get("summary"), 260),
                "simcHint": clean_context_value(simulator_talent.get("simcHint"), 80),
            },
            "gear": {
                "selectedItems": gear_items,
                "progressText": clean_context_value(simulator_gear.get("progressText"), 120),
                "nextAction": clean_context_value(simulator_gear.get("nextAction"), 120),
            }
        },
    }


def spec_info_from_build_context(context):
    if not context:
        return None
    spec_id = context.get("specId", "")
    class_label = context.get("className", "")
    spec_label = context.get("specName", "")
    for key in {
        spec_id,
        f"{class_label}-{spec_label}" if class_label and spec_label else "",
    }:
        if key in SIMC_AGENT_SPEC_BY_KEY:
            return SIMC_AGENT_SPEC_BY_KEY[key]
    for entry in SIMC_AGENT_SPEC_PATTERNS:
        if class_label and spec_label and entry["classLabel"] == class_label and entry["specLabel"] == spec_label:
            return entry
        if spec_id in {f'{entry["classLabel"]}-{entry["specLabel"]}', f'{entry["specLabel"]}{entry["classLabel"]}'}:
            return entry
    return None


def spec_info_from_keys(class_key, spec_key):
    return SIMC_AGENT_SPEC_BY_KEY.get(f"{str(class_key or '').strip()}-{str(spec_key or '').strip()}")


def build_context_talent_import_code(context):
    if not context:
        return ""
    return (((context.get("details") or {}).get("talents") or {}).get("importCode") or "").strip()


def build_context_simc_race(context, class_key):
    race = normalize_simc_race((context or {}).get("raceKey") or (context or {}).get("race"))
    if race:
        return race
    profile_options = (((context or {}).get("simulatorState") or {}).get("profileOptions") or {})
    race = normalize_simc_race(profile_options.get("raceKey") or profile_options.get("race"))
    return race or default_simc_race_for_class(class_key)


def build_context_talent_simc_lines(context):
    if not context:
        return []
    values = (((context.get("details") or {}).get("talents") or {}).get("simcLines") or [])
    return [str(line).strip() for line in values if str(line or "").strip() and "=" in str(line)]


def build_context_has_talents(context):
    return bool(build_context_talent_import_code(context) or build_context_talent_simc_lines(context))


def build_context_gear_items(context):
    if not context:
        return []
    details_items = (((context.get("details") or {}).get("gear") or {}).get("simcItems") or [])
    state_items = (((context.get("simulatorState") or {}).get("gear") or {}).get("selectedItems") or [])
    return clean_simc_gear_items(details_items or state_items)


def request_gear_items(source, build_context=None):
    source_items = []
    if isinstance(source, dict):
        gear_selection = source.get("gearSelection") if isinstance(source.get("gearSelection"), dict) else {}
        source_items = clean_simc_gear_items(
            first_present(gear_selection, ["items", "selectedItems", "simcItems"], [])
            or first_present(source, ["gearItems", "simcGearItems"], [])
        )
    return source_items or build_context_gear_items(build_context)


def build_simc_agent_missing_slots(source_profile, generated_profile, spec_info, message, build_context=None, gear_items=None):
    if source_profile:
        return []
    if not spec_info:
        return ["specialization"]
    missing_slots = []
    if generated_profile and not build_context and not has_explicit_simc_agent_item_level(message):
        missing_slots.append("itemLevel")
    if generated_profile and not has_explicit_simc_agent_scenario(message):
        missing_slots.append("scenario")
    if generated_profile and not build_context_has_talents(build_context):
        missing_slots.append("talents")
    if generated_profile and not (gear_items or []):
        missing_slots.append("gear")
    return missing_slots


def build_generated_simc_profile(spec_info, item_level, build_context=None, gear_items=None):
    if not spec_info:
        return ""
    race = build_context_simc_race(build_context, spec_info["class"])
    lines = [
        f'{spec_info["class"]}="{spec_info["actor"]}"',
        f"level={int_env('WOW_SIMC_AGENT_DEFAULT_LEVEL', 90)}",
        f"race={race}",
        f'role={spec_info["role"]}',
        f'spec={spec_info["spec"]}',
    ]
    if item_level:
        lines.append(f"scale_to_itemlevel={item_level}")
    talent_code = build_context_talent_import_code(build_context)
    if talent_code:
        lines.append(f"talents={talent_code}")
    else:
        lines.extend(build_context_talent_simc_lines(build_context))
    profile_items = simc_profile_items_with_class_defaults(
        gear_items or build_context_gear_items(build_context),
        spec_info,
    )
    lines.extend(build_simc_gear_lines(profile_items))
    return "\n".join(lines)


def append_simc_option(lines, key, value):
    prefix = f"{key}="
    if any(line.strip().startswith(prefix) for line in lines):
        return
    lines.append(f"{key}={value}")


def simc_agent_iterations(profile_source):
    if profile_source == "generated":
        return int_env("WOW_SIMC_AGENT_GENERATED_ITERATIONS", 500)
    return int_env("WOW_SIMC_AGENT_ITERATIONS", 10000)


def build_agent_simc_profile(profile, intent, scenario, profile_source="", temporary_buffs=None):
    lines = [line.rstrip() for line in str(profile or "").splitlines() if line.strip()]
    if not lines:
        return ""
    lines.append("")
    if profile_source not in {"explicit", "prompt"}:
        apply_simc_preparation_lines(lines, temporary_buffs=temporary_buffs)
    append_simc_option(lines, "iterations", simc_agent_iterations(profile_source))
    append_simc_option(lines, "fight_style", scenario["fightStyle"])
    append_simc_option(lines, "desired_targets", scenario["targets"])
    append_simc_option(lines, "max_time", scenario["durationSeconds"])
    append_simc_option(lines, "vary_combat_length", "0.2")
    if intent == "stat_weights":
        append_simc_option(lines, "calculate_scale_factors", "1")
        append_simc_option(lines, "scale_only", "int,crit,haste,mastery,vers")
    return "\n".join(lines).strip()


def simc_profile_spec_key(profile):
    player_class = ""
    spec = ""
    for line in str(profile or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = [part.strip().lower() for part in stripped.split("=", 1)]
        if key in SIMC_AGENT_CLASS_KEYS:
            player_class = key
        elif key == "spec":
            spec = value.strip('"')
    if player_class and spec:
        return f"{player_class}-{spec}"
    return ""


def build_mythic_plus_reference(profile, scenario):
    if not scenario or scenario.get("targets", 1) <= 1:
        return None
    scenario_key = str(scenario.get("key") or "").strip()
    if scenario_key and scenario_key != "mythic_plus":
        return None
    spec_key = simc_profile_spec_key(profile)
    if not spec_key:
        return None
    reference = MYTHIC_PLUS_DPS_REFERENCES.get(spec_key)
    if not reference:
        spec_info = SIMC_AGENT_SPEC_BY_KEY.get(spec_key, {})
        spec_name = f'{spec_info.get("specLabel", spec_key)}{spec_info.get("classLabel", "")}'.strip()
        reference = {
            "specKey": spec_key,
            "specName": spec_name or spec_key,
            "avgDps": "待实时刷新",
            "maxDps": "待实时刷新",
            "maxKey": "高层样本",
            "sampleWindow": "报告生成前必须按 Raider.IO、Warcraft Logs 或 Archon 的近两周大秘境样本刷新。",
            "notes": [
                "该专精尚未写入精确 DPS 快照，不能编造平均值或上限。",
                "最终报告只能把 SimC 结果与实时来源中的同专精、相近层数、相近装等日志并排解释。",
            ],
            "sources": GENERIC_MYTHIC_PLUS_REFERENCE_SOURCES,
        }
    return json.loads(json.dumps(reference, ensure_ascii=False))


def parse_reference_dps_value(value):
    text = str(value or "").strip().upper().replace(",", "")
    match = re.match(r"^(\d+(?:\.\d+)?)(K?)$", text)
    if not match:
        return 0.0
    number = float(match.group(1))
    return number * 1000 if match.group(2) == "K" else number


def build_simc_benchmark(request_data, simulation):
    metrics = simulation.get("metrics") or {}
    dps_text = metrics.get("dps")
    if not dps_text:
        return None
    try:
        dps = float(str(dps_text).replace(",", ""))
    except (TypeError, ValueError):
        return None
    reference = request_data.get("mythicPlusReference") if isinstance(request_data, dict) else None
    if not reference:
        return {
            "status": "unverified",
            "summary": "No external reference is attached for this SimC scenario.",
            "warnings": ["Do not treat this SimC number as externally benchmarked until a same-spec reference window is attached."],
        }
    avg_dps = parse_reference_dps_value(reference.get("avgDps"))
    max_dps = parse_reference_dps_value(reference.get("maxDps"))
    if avg_dps <= 0 and max_dps <= 0:
        return {
            "status": "unverified",
            "specKey": reference.get("specKey", ""),
            "source": (reference.get("sources") or [{}])[0].get("name", ""),
            "summary": "External reference is attached but has no numeric DPS window.",
            "warnings": ["Refresh the external reference before making a pass/fail DPS claim."],
        }
    high_limit = max(max_dps * 1.35, avg_dps * 1.75)
    low_limit = avg_dps * 0.35 if avg_dps else max_dps * 0.2
    if high_limit and dps > high_limit:
        status = "outlier_high"
        summary = "SimC DPS is far above the attached external Mythic+ window; verify profile, fight style, targets, item level, and SimC version before calling it reasonable."
    elif low_limit and dps < low_limit:
        status = "outlier_low"
        summary = "SimC DPS is far below the attached external Mythic+ window; verify profile completeness, talents, gear, and scenario settings."
    else:
        status = "reasonable"
        summary = "SimC DPS falls within a broad sanity window around the attached external Mythic+ reference."
    benchmark = {
        "status": status,
        "specKey": reference.get("specKey", ""),
        "specName": reference.get("specName", ""),
        "simcDps": f"{dps:.3f}".rstrip("0").rstrip("."),
        "referenceAvgDps": reference.get("avgDps", ""),
        "referenceMaxDps": reference.get("maxDps", ""),
        "ratioToAvg": round(dps / avg_dps, 3) if avg_dps else None,
        "sampleWindow": reference.get("sampleWindow", ""),
        "source": (reference.get("sources") or [{}])[0].get("name", ""),
        "summary": summary,
        "warnings": [],
    }
    if status != "reasonable":
        benchmark["warnings"].append(summary)
    return benchmark


def apply_simc_benchmark(request_data, simulation):
    benchmark = build_simc_benchmark(request_data, simulation)
    if benchmark:
        simulation["benchmark"] = benchmark
    return simulation


def build_mythic_plus_reference_from_slots(filled_slots, scenario):
    if not scenario or scenario.get("targets", 1) <= 1:
        return None
    scenario_key = str(scenario.get("key") or "").strip()
    if scenario_key and scenario_key != "mythic_plus":
        return None
    if not filled_slots or not filled_slots.get("class") or not filled_slots.get("spec"):
        return None
    spec_key = f'{filled_slots["class"]}-{filled_slots["spec"]}'
    reference = MYTHIC_PLUS_DPS_REFERENCES.get(spec_key)
    if not reference:
        return None
    return json.loads(json.dumps(reference, ensure_ascii=False))


def extract_json_object(text):
    source = str(text or "").strip()
    if not source:
        return None
    try:
        payload = json.loads(source)
    except json.JSONDecodeError:
        start = source.find("{")
        end = source.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            payload = json.loads(source[start:end + 1])
        except json.JSONDecodeError:
            return None
    return payload if isinstance(payload, dict) else None


def clean_confirmation_quick_replies(values):
    if not isinstance(values, list):
        return []
    replies = []
    for value in values[:3]:
        text = clean_context_value(value, 40)
        if text:
            replies.append(text)
    return replies


def build_simc_confirmation_prompt(request_data, agent, draft_profile):
    schema = {
        "status": "needs_clarification | template_ready | off_topic",
        "intent": "baseline | stat_weights | gear_compare | talent_compare | out_of_scope",
        "filledSlots": {
            "class": "deathknight",
            "classLabel": "死亡骑士",
            "spec": "unholy",
            "specLabel": "邪恶",
            "heroTalent": "天启",
            "itemLevel": 278,
            "scenario": "大秘境多目标",
            "targets": 5,
            "durationSeconds": 300,
        },
        "missingSlots": ["talents", "gear"],
        "question": "下一句只问最少必要信息",
        "quickReplies": ["打开天赋模拟器补天赋", "继续补装备", "我先只看参考区间"],
    }
    return "\n\n".join([
        "你是 SimC 需求确认器，只能输出一个 JSON 对象，不要输出 Markdown。",
        "目标：确认玩家的职业/专精/装等/场景/天赋/装备是否足以生成可复核 SimC profile。",
        "硬规则：如果缺 talents 或真实 gear，不得返回 template_ready；不得编造装备、宝石、附魔、DPS 或角色导出。",
        "硬规则：如果后端 deterministicSlots 已识别职业/专精，你必须保留，不得改成其它职业专精。",
        f"允许的 JSON schema 示例：{json.dumps(schema, ensure_ascii=False)}",
        f"玩家输入：{request_data.get('question') or request_data.get('prompt') or ''}",
        f"deterministicSlots：{json.dumps(agent.get('filledSlots') or {}, ensure_ascii=False)}",
        f"deterministicMissingSlots：{json.dumps(agent.get('missingSlots') or [], ensure_ascii=False)}",
        f"当前 profileSource：{request_data.get('profileSource') or 'none'}",
        f"当前 draftProfile：\n{(draft_profile or '')[:2000]}",
    ]).strip()


def call_simc_confirmation_llm(request_data, agent, draft_profile):
    return call_chat_completion(
        "你是 SimC 需求确认器。你必须只输出合法 JSON，不输出解释。",
        build_simc_confirmation_prompt(request_data, agent, draft_profile),
        temperature=0,
    )


def confirmation_failed_agent(base_agent, error):
    agent = dict(base_agent)
    agent.update({
        "status": "confirmation_failed",
        "confidence": 0,
        "missingSlots": [],
        "question": "后端暂时无法完成 SimC 需求确认，请稍后重试。",
        "quickReplies": [],
        "draftProfile": "",
        "validation": {"passed": False, "errors": ["llm confirmation failed"], "warnings": [clean_context_value(error, 160)] if error else []},
        "canSubmitTask": False,
    })
    return agent


def normalize_confirmation_missing_slots(values, deterministic_missing):
    missing = []
    for slot in list(deterministic_missing or []) + list(values or []):
        if slot in SIMC_AGENT_CONFIRMATION_MISSING_SLOTS and slot not in missing:
            missing.append(slot)
    return missing


def apply_llm_confirmation(agent, llm_result, draft_profile):
    if not llm_result.get("called") or llm_result.get("error"):
        return confirmation_failed_agent(agent, llm_result.get("error") or "llm unavailable")
    confirmation = extract_json_object(llm_result.get("content"))
    if not confirmation:
        return confirmation_failed_agent(agent, "invalid llm confirmation json")

    status = confirmation.get("status")
    if status not in SIMC_AGENT_CONFIRMATION_STATUSES:
        return confirmation_failed_agent(agent, "invalid llm confirmation status")

    deterministic_slots = agent.get("filledSlots") or {}
    llm_slots = confirmation.get("filledSlots") if isinstance(confirmation.get("filledSlots"), dict) else {}
    for key in ["class", "spec"]:
        deterministic_value = deterministic_slots.get(key)
        llm_value = llm_slots.get(key)
        if deterministic_value and llm_value and deterministic_value != llm_value:
            return confirmation_failed_agent(agent, f"llm changed {key}")

    merged_slots = {**llm_slots, **deterministic_slots}
    missing_slots = normalize_confirmation_missing_slots(confirmation.get("missingSlots"), agent.get("missingSlots") or [])
    if missing_slots:
        status = "needs_clarification"
    elif agent.get("validation", {}).get("passed") and status != "off_topic":
        status = "template_ready"

    if missing_slots:
        question = agent.get("question") or clean_context_value(confirmation.get("question"), 220)
        quick_replies = agent.get("quickReplies") or clean_confirmation_quick_replies(confirmation.get("quickReplies"))
    else:
        question = clean_context_value(confirmation.get("question"), 220) or agent.get("question") or ""
        quick_replies = clean_confirmation_quick_replies(confirmation.get("quickReplies")) or agent.get("quickReplies") or []
    confirmed = dict(agent)
    confirmed.update({
        "status": status,
        "intent": agent.get("intent") or confirmation.get("intent"),
        "confidence": 0.9,
        "missingSlots": missing_slots,
        "filledSlots": merged_slots,
        "question": "" if status == "template_ready" else question,
        "quickReplies": [] if status == "template_ready" else quick_replies,
        "draftProfile": draft_profile if status == "template_ready" else agent.get("draftProfile", ""),
        "canSubmitTask": bool(status == "template_ready" and agent.get("validation", {}).get("passed")),
    })
    if status == "needs_clarification":
        confirmed["validation"] = {"passed": False, "errors": missing_slots, "warnings": agent.get("validation", {}).get("warnings", [])}
        confirmed["canSubmitTask"] = False
    return confirmed


def sanitize_simcraft_summary_for_llm(simulation):
    summary = str((simulation or {}).get("summary") or "")
    metrics = (simulation or {}).get("metrics") or {}
    dps = metrics.get("dps", "")
    if not summary:
        return ""

    kept_lines = []
    for line in summary.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if "Generating Baseline:" in stripped or re.match(r"^[=>.\[\]\s]+\d+/\d+\s+\d+(?:\.\d+)?\s+\d+sec", stripped):
            continue
        if stripped.startswith("SimulationCraft") or stripped.startswith("Player:") or stripped.startswith("Scale Factors"):
            kept_lines.append(stripped)
            continue
        if re.search(r"\bDPS(?:=|\b)|\bdps\b", stripped, re.IGNORECASE):
            kept_lines.append(stripped)

    if dps:
        prefix = f"后端解析到最终 DPS：{dps}。"
        return "\n".join([prefix] + kept_lines[:24]).strip()
    return "SimC 已运行，但后端未解析到最终 DPS；已过滤 Generating Baseline 执行进度行，不得从 Generating Baseline 的进度数字推断 DPS。"


def format_mythic_plus_reference_for_prompt(reference):
    if not reference:
        return ""
    comparison = reference.get("comparisonText") or mythic_plus_reference_comparison_text(reference)
    source_lines = [
        f"- {source['name']}：{source['evidence']} 来源：{source['url']}"
        for source in reference.get("sources", [])
    ]
    note_lines = [f"- {note}" for note in reference.get("notes", [])]
    return "\n".join([
        f"专精：{reference.get('specName', '')}",
        f"样本窗口：{reference.get('sampleWindow', '')}",
        f"真实大秘境对标：{comparison}，最高钥石 {reference.get('maxKey', '')}。",
        "来源证据：",
        *source_lines,
        "解释边界：",
        *note_lines,
    ]).strip()


def format_build_context_for_prompt(context):
    if not context:
        return ""
    details = context.get("details") or {}
    talents = details.get("talents") or {}
    gear_rows = (details.get("gear") or {}).get("gear") or []
    stat_rows = (details.get("statWeights") or {}).get("stats") or []
    gear_lines = [
        f"- {row.get('slot', '装备')}：{row.get('name', '')}；{row.get('source', '')}".strip("；")
        for row in gear_rows[:6]
    ]
    stat_line = " > ".join(row.get("name", "") for row in stat_rows[:6] if row.get("name"))
    talent_line = f"天赋导入代码：{talents.get('importCode')}" if talents.get("importCode") else "天赋导入代码：未提供，不能把当前天赋当作已精确模拟。"
    source_line = "；".join(
        item for item in [
            context.get("sourceName", ""),
            context.get("publishedAt", ""),
            context.get("analysisWindow", ""),
        ]
        if item
    )
    return "\n".join([
        f"专精：{context.get('specName', '')}{context.get('className', '')}；角色：{context.get('role', '')}",
        f"入口：{context.get('activeQueryTitle') or context.get('activeQueryKey') or '职业专精详情'}",
        f"来源：{source_line}",
        talent_line,
        "装备候选只能作为比较上下文；没有 item id、bonus id、enchant、gem 和当前角色导出时，不得硬写成 SimC gear 行。",
        "装备候选：",
        *(gear_lines or ["- 未提供装备候选"]),
        f"属性趋势：{stat_line or '未提供'}",
    ]).strip()


def dps_reference_value(value):
    text = str(value or "").strip().lower()
    match = re.match(r"^(\d+(?:\.\d+)?)\s*([km万]?)$", text)
    if not match:
        return 0
    number = float(match.group(1))
    suffix = match.group(2)
    if suffix == "k":
        number *= 1000
    elif suffix == "m":
        number *= 1000000
    elif suffix == "万":
        number *= 10000
    return int(number)


def has_million_scale_dps_claim(content, reference):
    text = str(content or "")
    if not text or not reference:
        return False
    if "百万" in text or "数百万" in text:
        return True

    reference_top = dps_reference_value(reference.get("maxDps"))
    invalid_floor = max(reference_top * 2, 500000)
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:[-–~至到]\s*(\d+(?:\.\d+)?))?\s*万", text):
        upper = float(match.group(2) or match.group(1)) * 10000
        if upper >= invalid_floor:
            return True
    return False


def build_guarded_llm_content(request_data, simulation, llm_result):
    content = str((llm_result or {}).get("content") or "")
    reference = (request_data or {}).get("mythicPlusReference")
    metrics = (simulation or {}).get("metrics") or {}
    dps = metrics.get("dps", "")
    simc_error = str((simulation or {}).get("error") or "").strip()
    needs_backend_guard = bool(content and simc_error and not dps)
    needs_scale_guard = bool(reference and has_million_scale_dps_claim(content, reference))
    if not needs_backend_guard and not needs_scale_guard:
        return content

    if dps:
        simc_line = f"SimC 已产出可解析 DPS：{dps}。"
    else:
        simc_line = "SimC 未产出可用 DPS。"
        if simc_error:
            simc_line += f"后端执行错误：{simc_error}。"

    if dps:
        boundary_line = (
            "3. **当前可给出的判断边界**：SimC 结果只代表本次模板和场景；"
            "真实大秘境部分必须按同专精、相近层数、相近装等的近两周样本刷新后再对照。"
        )
        verify_line = "验证方式：复跑同一 profile 确认 DPS 稳定，再刷新 Raider.IO、Warcraft Logs 或 Archon 的同专精大秘境样本。"
    else:
        boundary_line = (
            "3. **当前可给出的判断边界**：在后端没有生成完整可执行 SimC profile 前，"
            "只能用真实日志对标给保守区间；系统需要补齐武器、装备、饰品和天赋 slot 后，才能把 SimC 数值作为主结论。"
        )
        verify_line = "验证方式：优先对比近两周同专精、相近装等、相近层数的大秘境日志；补齐天赋和手选装备生成完整 SimC profile 后，再把模拟结果和日志区间并排输出。"

    if reference:
        reference_line = (
            f"2. **真实大秘境对标**：{reference.get('specName', '')} 当前高端样本为 "
            f"{reference.get('comparisonText') or mythic_plus_reference_comparison_text(reference)}，"
            f"最高钥石 {reference.get('maxKey', '')}。结论必须围绕这个量级解释。"
        )
    else:
        reference_line = (
            "2. **横向对标状态**：本次请求没有可用的多目标真实日志参考；"
            "不能补写合格 DPS 区间，也不能把 LLM 估算当作来源。"
        )

    return "\n\n".join([
        "## 优先级最高的 3 条结论",
        f"1. **{simc_line}** 本次不能把未完成的 SimC 当作 DPS 标准，也不能从执行进度数字推断输出。",
        reference_line,
        boundary_line,
        f"{verify_line} 请补齐完整 SimC profile 后再复跑。",
    ])


def validate_agent_simc_profile(profile):
    errors = []
    warnings = []
    text = str(profile or "").strip()
    if not text:
        errors.append("missing simc template")
    if len(text) > int_env("WOW_SIMC_AGENT_MAX_PROFILE_CHARS", 12000):
        errors.append("profile too large")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip().lower()
        if key in SIMC_AGENT_FORBIDDEN_KEYS:
            errors.append(f"forbidden simc output option: {key}")
        if key in SIMC_AGENT_TALENT_LINE_KEYS:
            value = stripped.split("=", 1)[1].strip()
            entries = [entry.strip() for entry in value.split("/")]
            if not entries or not any(entries):
                errors.append(f"invalid {key}: missing talent entries")
                continue
            for entry in entries:
                if not entry or not SIMC_AGENT_TALENT_ENTRY_RE.match(entry):
                    errors.append(f"invalid {key} entry: {entry or '<empty>'}")
    has_talent_input = any(
        line.strip().split("=", 1)[0].strip().lower() in {"talents", *SIMC_AGENT_TALENT_LINE_KEYS}
        for line in text.splitlines()
        if "=" in line
    )
    if text and not has_talent_input:
        warnings.append("缺少 talents，模拟可信度会下降")
    if text and not any(looks_like_simc_profile_line(line) for line in text.splitlines()):
        errors.append("profile is not a recognizable SimC template")
    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def build_agent_clarification_question(missing_slots, round_number, filled_slots=None):
    slots = filled_slots or {}
    spec_label = f"{slots.get('specLabel', '')}{slots.get('classLabel', '')}".strip()
    item_label = f"{slots.get('itemLevel')} 装等" if slots.get("itemLevel") else ""
    scenario_label = slots.get("scenario") or "目标场景"
    hero_label = f"（{slots.get('heroTalent')}流派）" if slots.get("heroTalent") else ""
    if "specialization" in missing_slots:
        if slots.get("classLabel"):
            specs = "、".join(next((entry["specs"] for entry in SIMC_AGENT_CLASS_PATTERNS if entry["class"] == slots.get("class")), []))
            return f"已收到：{slots.get('itemLevel')} 装等{slots.get('classLabel')}、{slots.get('scenario') or '目标场景'}。还差专精：{specs or '请补充具体专精'}。"
        return "先告诉我职业和专精，再说想看单体、AOE、属性收益、天赋还是装备对比。"
    if "itemLevel" in missing_slots and "scenario" in missing_slots:
        return f"已收到：{spec_label or '当前专精'}。还差装等和模拟场景，请补充例如“700 装等，单体 5 分钟”或“大秘境多目标”。"
    if "itemLevel" in missing_slots:
        return "还差装等：请告诉我当前角色装等，例如 700、710 或 720。"
    if "talents" in missing_slots and "gear" in missing_slots:
        recognized = "、".join(item for item in [f"{item_label}{spec_label}{hero_label}".strip(), scenario_label] if item)
        return f"已识别：{recognized or '当前需求'}。还差天赋导入码和手选装备数据，才能生成可复核的 SimC profile。"
    if "talents" in missing_slots:
        return f"已识别：{item_label}{spec_label}{hero_label}、{scenario_label}。还差天赋导入码，才能把当前构筑写入 SimC profile。"
    if "gear" in missing_slots:
        return f"已识别：{item_label}{spec_label}{hero_label}、{scenario_label}。还差手选装备数据，包括 item id、装等、宝石和附魔。"
    return "还差一项关键信息：请说明这次要模拟单体、团本 Boss，还是大秘境多目标。"


def build_agent_quick_replies(missing_slots, filled_slots=None):
    slots = filled_slots or {}
    if "specialization" in missing_slots:
        class_replies = SIMC_AGENT_CLASS_QUICK_REPLIES.get(slots.get("class"))
        if class_replies:
            return class_replies
        return ["我是冰法，看单体属性收益", "我是元素萨，看大秘境 AOE", "我是惩戒骑，比较装备收益"]
    if "itemLevel" in missing_slots:
        return ["700 装等，单体 5 分钟", "710 装等，大秘境多目标", "720 装等，比较装备收益"]
    if "talents" in missing_slots and "gear" in missing_slots:
        return ["打开天赋模拟器补天赋", "继续补装备", "我先只看参考区间"]
    if "talents" in missing_slots:
        return ["打开天赋模拟器补天赋", "我先只看参考区间"]
    if "gear" in missing_slots:
        return ["继续补装备", "我先只看参考区间"]
    return ["单体 5 分钟", "大秘境多目标", "比较装备收益"]


def build_agent_summary_cards(request_data, simulation, scenario):
    dps = (simulation.get("metrics") or {}).get("dps", "")
    mythic_reference = request_data.get("mythicPlusReference") if isinstance(request_data, dict) else None
    if simulation.get("ran") and dps:
        conclusion = f"本次 SimC 已跑通，当前模板约为 {dps} DPS。"
    elif simulation.get("ran"):
        conclusion = "本次 SimC 已跑通，但输出摘要中没有解析到 DPS。"
    else:
        conclusion = f"本次没有完成真实 SimC：{simulation.get('error') or '未执行'}。"
    cards = [{"title": "结论", "text": conclusion}]
    if mythic_reference:
        cards.append({
            "title": "真实大秘境对标",
            "text": f"{mythic_reference['specName']} 当前高端样本：{mythic_reference.get('comparisonText') or mythic_plus_reference_comparison_text(mythic_reference)}，最高 {mythic_reference['maxKey']}。",
        })
    cards.append({
        "title": "模拟边界",
        "text": f"{scenario['label']}，{scenario['durationSeconds']} 秒；结论只适用于本次模板和场景。",
    })
    return cards


def skipped_codex_worker_result(error="not executable"):
    return {
        "enabled": truthy_env("WOW_CODEX_SIMULATOR_ENABLED"),
        "called": False,
        "status": "skipped",
        "jobId": "",
        "lastMessage": "",
        "error": error,
    }


def build_simulator_home_payload():
    has_simc = bool(simc_binary())
    has_llm = llm_configured()
    version_status = simc_version_status()
    return {
        "navTitle": "智能分析",
        "kicker": "能力 04",
        "title": "智能分析",
        "desc": "首版智能分析只保留炸鸡队长，围绕已有证据给出下一步建议。",
        "analysisModules": [
            {
                "key": "chickenbro",
                "badge": "01",
                "title": "炸鸡队长",
                "desc": "把已有 SimC 与角色上下文整理成证据受限的下一步建议，缺证据时只列缺失项。",
                "action": "进入教练",
            },
        ],
        "quickActions": [
            {"key": "chickenbro", "title": "炸鸡队长", "desc": "进入证据教练。"},
        ],
        "capabilities": {
            "simcraft": has_simc,
            "llm": has_llm,
            "wcl": False,
        },
        "simcraftVersion": version_status,
        "lastCheckedAt": utc_now(),
    }


def normalize_analysis_request(payload):
    source = payload if isinstance(payload, dict) else {}
    prompt = str(source.get("prompt") or "").strip()
    explicit_profile = str(source.get("profile") or "").strip()
    extracted_profile = extract_simc_profile_from_prompt(prompt)
    profile = explicit_profile or extracted_profile
    mode = source.get("mode") or "simcraft"
    run_simulation = bool(source.get("runSimulation"))
    if run_simulation and not profile:
        run_simulation = False
    if mode == "simcraft" and profile:
        run_simulation = True
    return {
        "mode": mode,
        "character": str(source.get("character") or "").strip(),
        "prompt": prompt,
        "profile": profile,
        "profileSource": "explicit" if explicit_profile else ("prompt" if extracted_profile else "none"),
        "wclUrl": str(source.get("wclUrl") or "").strip(),
        "question": str(source.get("question") or prompt or "").strip(),
        "runSimulation": run_simulation,
        "buildContext": normalize_build_context(source.get("buildContext")),
    }


def warcraftlogs_credentials_state():
    has_v2_credentials = bool(
        os.environ.get("WOW_WARCRAFTLOGS_CLIENT_ID", "").strip()
        and os.environ.get("WOW_WARCRAFTLOGS_CLIENT_SECRET", "").strip()
    )
    if has_v2_credentials:
        return {
            "configured": True,
            "mode": "v2_oauth",
            "api": "warcraftlogs-v2-graphql",
        }
    if os.environ.get("WOW_WARCRAFTLOGS_API_KEY", "").strip():
        return {
            "configured": True,
            "mode": "v1_api_key",
            "api": "warcraftlogs-v1-rest",
        }
    return {
        "configured": False,
        "mode": "none",
        "api": "warcraftlogs-v2-graphql",
    }


def wcl_credentials_configured():
    return warcraftlogs_credentials_state()["configured"]


def redact_wcl_secret(text):
    value = str(text or "")
    for name in (
        "WOW_WARCRAFTLOGS_CLIENT_ID",
        "WOW_WARCRAFTLOGS_CLIENT_SECRET",
        "WOW_WARCRAFTLOGS_API_KEY",
    ):
        secret = os.environ.get(name, "").strip()
        if secret:
            value = value.replace(secret, "[redacted]")
    value = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[redacted]", value)
    value = re.sub(r"(?i)(client_secret=)[^&\s]+", r"\1[redacted]", value)
    return value


def warcraftlogs_oauth_token():
    client_id = os.environ.get("WOW_WARCRAFTLOGS_CLIENT_ID", "").strip()
    client_secret = os.environ.get("WOW_WARCRAFTLOGS_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Warcraft Logs v2 credentials are not configured")
    token_url = os.environ.get("WOW_WARCRAFTLOGS_TOKEN_URL", "https://www.warcraftlogs.com/oauth/token").strip()
    body = urlencode({"grant_type": "client_credentials"}).encode("utf-8")
    request = Request(
        token_url,
        data=body,
        headers={"User-Agent": "wow-mini-program-wcl-sync"},
        method="POST",
    )
    import base64

    raw_auth = f"{client_id}:{client_secret}".encode("utf-8")
    request.add_header("Authorization", f"Basic {base64.b64encode(raw_auth).decode('ascii')}")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urlopen(request, timeout=int_env("WOW_WARCRAFTLOGS_TIMEOUT_SECONDS", 15)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("Warcraft Logs OAuth response did not include an access token")
    return token


def warcraftlogs_graphql(query, variables=None, token=None):
    graphql_url = os.environ.get("WOW_WARCRAFTLOGS_GRAPHQL_URL", "https://www.warcraftlogs.com/api/v2/client").strip()
    body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    request = Request(
        graphql_url,
        data=body,
        headers={
            "Authorization": f"Bearer {token or warcraftlogs_oauth_token()}",
            "Content-Type": "application/json",
            "User-Agent": "wow-mini-program-wcl-sync",
        },
        method="POST",
    )
    with urlopen(request, timeout=int_env("WOW_WARCRAFTLOGS_TIMEOUT_SECONDS", 15)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    errors = payload.get("errors")
    if errors:
        message = "; ".join(str(item.get("message") if isinstance(item, dict) else item) for item in errors)
        raise RuntimeError(redact_wcl_secret(message or "Warcraft Logs GraphQL returned errors"))
    return payload.get("data") or {}


WCL_REPORT_EVIDENCE_QUERY = """
query WowMiniProgramReportEvidence($code: String!, $fightIds: [Int]) {
  reportData {
    report(code: $code) {
      title
      startTime
      endTime
      fights {
        id
        name
        difficulty
        kill
        startTime
        endTime
      }
      events(fightIDs: $fightIds, limit: 300) {
        data
      }
    }
  }
}
"""


def summarize_wcl_events(events):
    summary = {
        "total": 0,
        "casts": 0,
        "buffEvents": 0,
        "deaths": 0,
        "damageEvents": 0,
        "healingEvents": 0,
        "mechanicEvents": 0,
    }
    for event in events or []:
        if not isinstance(event, dict):
            continue
        summary["total"] += 1
        event_type = str(event.get("type") or "").lower()
        if event_type == "cast":
            summary["casts"] += 1
        elif "buff" in event_type:
            summary["buffEvents"] += 1
        elif event_type == "death":
            summary["deaths"] += 1
        elif event_type == "damage":
            summary["damageEvents"] += 1
        elif event_type in {"heal", "healing"}:
            summary["healingEvents"] += 1
        elif event_type:
            summary["mechanicEvents"] += 1
    return summary


def normalize_wcl_fight(fight):
    if not isinstance(fight, dict):
        return {}
    return {
        "id": str(fight.get("id") or ""),
        "name": str(fight.get("name") or ""),
        "difficulty": fight.get("difficulty") or "",
        "kill": bool(fight.get("kill")),
        "startTime": fight.get("startTime") or 0,
        "endTime": fight.get("endTime") or 0,
    }


def fetch_wcl_v2_evidence(reference, credential_state):
    fight_id = str((reference or {}).get("fightId") or "").strip()
    fight_ids = []
    if fight_id.isdigit():
        fight_ids = [int(fight_id)]
    token = warcraftlogs_oauth_token()
    data = warcraftlogs_graphql(
        WCL_REPORT_EVIDENCE_QUERY,
        {"code": reference["reportCode"], "fightIds": fight_ids or None},
        token=token,
    )
    report = (((data.get("reportData") or {}).get("report")) or {})
    if not report:
        raise RuntimeError("Warcraft Logs GraphQL response did not include report data")
    fights = [normalize_wcl_fight(item) for item in report.get("fights") or []]
    selected_fight = {}
    if fight_id:
        selected_fight = next((item for item in fights if item.get("id") == fight_id), {})
    if not selected_fight and fights:
        selected_fight = fights[0]
    events = (((report.get("events") or {}).get("data")) or [])
    event_summary = summarize_wcl_events(events)
    return {
        "schemaRevision": "wcl-log-evidence-v1",
        "status": "ready",
        "sourceStatus": "verified",
        "credentialMode": credential_state["mode"],
        "api": credential_state["api"],
        "reportCode": reference["reportCode"],
        "sourceUrl": reference["sourceUrl"],
        "fightId": selected_fight.get("id") or fight_id,
        "reportTitle": str(report.get("title") or ""),
        "reportWindow": {
            "startTime": report.get("startTime") or 0,
            "endTime": report.get("endTime") or 0,
        },
        "fight": selected_fight,
        "eventSummary": event_summary,
        "missingInputs": [],
        "blockers": [],
        "evidenceRefs": ["wcl.report", "wcl.fight", "wcl.events"],
        "nextActions": [
            "Use this parsed WCL evidence together with the SimC result before making rotation or performance conclusions.",
            "Compare casts, buff uptime, deaths, damage and healing events against a matched sample window before ranking the player.",
        ],
    }


def extract_wcl_reference(request_data):
    parts = [
        str((request_data or {}).get("wclUrl") or ""),
        str((request_data or {}).get("prompt") or ""),
        str((request_data or {}).get("question") or ""),
    ]
    text = "\n".join(part for part in parts if part)
    url_match = re.search(r"https?://(?:www\.)?warcraftlogs\.com/reports/([A-Za-z0-9]+)[^\s<>\"]*", text)
    code = ""
    source_url = ""
    if url_match:
        code = url_match.group(1)
        source_url = url_match.group(0).rstrip(".,)")
    if not code:
        code_match = re.search(r"\b(?:wcl|report)\s*[:#= ]\s*([A-Za-z0-9]{6,})\b", text, re.IGNORECASE)
        if code_match:
            code = code_match.group(1)
    fight_id = ""
    if source_url:
        fight_match = re.search(r"(?:[?#&]|&amp;)fight=([A-Za-z0-9_-]+)", source_url)
        if fight_match:
            fight_id = fight_match.group(1)
    return {
        "reportCode": code,
        "sourceUrl": source_url,
        "fightId": fight_id,
    }


def build_wcl_log_evidence(request_data):
    reference = extract_wcl_reference(request_data)
    credential_state = warcraftlogs_credentials_state()
    missing_inputs = []
    if not reference["reportCode"]:
        missing_inputs.append("wcl.report")
        return {
            "schemaRevision": "wcl-log-evidence-v1",
            "status": "missing_input",
            "sourceStatus": "missing_report",
            "credentialMode": credential_state["mode"],
            "api": credential_state["api"],
            "reportCode": "",
            "sourceUrl": reference["sourceUrl"],
            "fightId": reference["fightId"],
            "missingInputs": missing_inputs,
            "evidenceRefs": ["wcl.report"],
            "nextActions": [
                "Paste a Warcraft Logs report URL or report code before requesting log analysis.",
                "Include fight id, boss, difficulty, class, spec, and the question you want answered.",
            ],
        }
    if not credential_state["configured"]:
        missing_inputs.append("wcl.credentials")
        return {
            "schemaRevision": "wcl-log-evidence-v1",
            "status": "blocked",
            "sourceStatus": "missing_credentials",
            "credentialMode": credential_state["mode"],
            "api": credential_state["api"],
            "reportCode": reference["reportCode"],
            "sourceUrl": reference["sourceUrl"],
            "fightId": reference["fightId"],
            "missingInputs": missing_inputs,
            "evidenceRefs": ["wcl.reportCode", "wcl.credentials"],
            "nextActions": [
                "Configure Warcraft Logs API credentials before fetching report events.",
                "Do not infer rankings, parses, DPS, HPS, or cooldown mistakes until log evidence is fetched.",
            ],
        }
    if credential_state["mode"] == "v2_oauth":
        try:
            return fetch_wcl_v2_evidence(reference, credential_state)
        except Exception as error:
            return {
                "schemaRevision": "wcl-log-evidence-v1",
                "status": "blocked",
                "sourceStatus": "blocked",
                "credentialMode": credential_state["mode"],
                "api": credential_state["api"],
                "reportCode": reference["reportCode"],
                "sourceUrl": reference["sourceUrl"],
                "fightId": reference["fightId"],
                "missingInputs": ["wcl.graphql_fetch"],
                "blockers": [redact_wcl_secret(error)],
                "evidenceRefs": ["wcl.reportCode", "wcl.credentials"],
                "nextActions": [
                    "Retry the Warcraft Logs GraphQL fetch after checking report visibility, fight id and API credentials.",
                    "Do not infer rankings, parses, DPS, HPS, casts, deaths or cooldown mistakes until log evidence is fetched.",
                ],
            }
    return {
        "schemaRevision": "wcl-log-evidence-v1",
        "status": "pending_fetch",
        "sourceStatus": "credentials_configured",
        "credentialMode": credential_state["mode"],
        "api": credential_state["api"],
        "reportCode": reference["reportCode"],
        "sourceUrl": reference["sourceUrl"],
        "fightId": reference["fightId"],
        "missingInputs": ["wcl.graphql_fetch"],
        "evidenceRefs": ["wcl.reportCode", "wcl.credentials"],
        "nextActions": [
            "Fetch Warcraft Logs report metadata and fight events through the credentialed Warcraft Logs API.",
            "Extract deterministic evidence before allowing player ranking or rotation conclusions.",
        ],
    }


def build_wcl_report(log_evidence):
    source_status = (log_evidence or {}).get("sourceStatus") or "missing_report"
    if source_status == "missing_report":
        text = "No Warcraft Logs report was provided, so personal log analysis cannot start."
    elif source_status == "missing_credentials":
        text = "Warcraft Logs credentials are missing, so the backend cannot fetch report evidence yet."
    elif source_status == "blocked":
        text = "Warcraft Logs evidence fetch failed, so no log-derived conclusion is available yet."
    elif source_status == "verified":
        summary = (log_evidence or {}).get("eventSummary") or {}
        fight = (log_evidence or {}).get("fight") or {}
        text = (
            f"Warcraft Logs evidence is parsed for {fight.get('name') or 'the selected fight'}: "
            f"{summary.get('casts', 0)} casts, {summary.get('buffEvents', 0)} buff events, "
            f"{summary.get('deaths', 0)} deaths, {summary.get('damageEvents', 0)} damage events, "
            f"and {summary.get('healingEvents', 0)} healing events."
        )
    else:
        text = "Warcraft Logs report metadata is ready for a credentialed fetch, but no log evidence has been parsed yet."
    return {
        "schemaRevision": "wcl-report-v1",
        "source": (
            "deterministic_evidence"
            if source_status == "verified"
            else ("deterministic_blocked" if source_status in {"missing_report", "missing_credentials", "blocked"} else "deterministic_pending")
        ),
        "topFindings": [
            {
                "text": text,
                "evidenceRefs": list((log_evidence or {}).get("evidenceRefs") or ["wcl.report"]),
            }
        ],
        "nextActions": list((log_evidence or {}).get("nextActions") or []),
        "limitations": [
            "No rankings, percentiles, DPS, HPS, casts, deaths, or cooldown conclusions are available until WCL evidence is fetched." if source_status != "verified" else "Parsed events are evidence, but rankings and percentiles still need a matched sample window.",
            "LLM output is disabled for this WCL bootstrap state to avoid inventing log facts.",
        ],
    }


def build_wcl_stages(log_evidence):
    source_status = (log_evidence or {}).get("sourceStatus") or "missing_report"
    return [
        {
            "key": "wcl_report_input",
            "title": "WCL report input",
            "status": "completed" if (log_evidence or {}).get("reportCode") else "blocked",
            "executor": "backend",
            "summary": (log_evidence or {}).get("reportCode") or "missing report URL or code",
        },
        {
            "key": "wcl_credentials",
            "title": "WCL credentials",
            "status": "completed" if source_status in {"credentials_configured", "verified", "blocked"} else "blocked",
            "executor": "backend",
            "summary": source_status,
        },
        {
            "key": "wcl_evidence",
            "title": "WCL evidence fetch",
            "status": "completed" if source_status == "verified" else ("blocked" if source_status == "blocked" else "skipped"),
            "executor": "warcraftlogs",
            "summary": "parsed GraphQL evidence" if source_status == "verified" else ("GraphQL fetch failed" if source_status == "blocked" else "credentialed GraphQL fetch pending"),
        },
    ]


def build_wcl_analysis_payload(request_data):
    log_evidence = build_wcl_log_evidence(request_data)
    report = build_wcl_report(log_evidence)
    llm_result = skipped_llm_result("wcl log evidence unavailable")
    status = "ready" if log_evidence["status"] in {"pending_fetch", "ready"} else "blocked"
    return {
        "mode": "wcl",
        "status": status,
        "createdAt": utc_now(),
        "capabilities": {
            "simcraft": bool(simc_binary()),
            "llm": llm_configured(),
            "wcl": wcl_credentials_configured(),
        },
        "request": request_data,
        "stages": build_wcl_stages(log_evidence),
        "logEvidence": log_evidence,
        "report": report,
        "recommendations": report["nextActions"][:3],
        "llm": {
            "prompt": "",
            "called": llm_result["called"],
            "model": llm_result.get("model", llm_model()),
            "content": "",
            "error": llm_result["error"],
        },
    }


def append_unique_text(values, text):
    value = clean_report_text(text, 120)
    if value and value not in values:
        values.append(value)


def append_unique_ref(values, ref):
    value = clean_report_text(ref, 80)
    if value and value not in values:
        values.append(value)


def report_evidence_refs(report):
    refs = []
    if not isinstance(report, dict):
        return refs
    for finding in report.get("topFindings") or []:
        if not isinstance(finding, dict):
            continue
        for ref in finding.get("evidenceRefs") or []:
            append_unique_ref(refs, ref)
    return refs


def chickenbro_coach_source_evidence(source):
    evidence = source.get("evidence") if isinstance(source.get("evidence"), dict) else {}
    return {
        "character": evidence.get("character") if isinstance(evidence.get("character"), dict) else (
            source.get("characterContext") if isinstance(source.get("characterContext"), dict) else {}
        ),
        "simc": evidence.get("simc") if isinstance(evidence.get("simc"), dict) else (
            source.get("simcAnalysis") if isinstance(source.get("simcAnalysis"), dict) else {}
        ),
        "wcl": evidence.get("wcl") if isinstance(evidence.get("wcl"), dict) else (
            source.get("wclAnalysis") if isinstance(source.get("wclAnalysis"), dict) else {}
        ),
        "comparison": evidence.get("comparison") if isinstance(evidence.get("comparison"), dict) else (
            evidence.get("comparableSample") if isinstance(evidence.get("comparableSample"), dict) else {}
        ),
    }


def chickenbro_has_character_context(character):
    if not isinstance(character, dict):
        return False
    return bool(
        (character.get("className") or character.get("classKey"))
        and (character.get("specName") or character.get("specKey"))
        and character.get("role")
        and character.get("itemLevel")
        and (character.get("scenario") or character.get("scenarioKey"))
    )


def chickenbro_simc_refs(simc):
    if not isinstance(simc, dict):
        return []
    refs = report_evidence_refs(simc.get("report"))
    for number in simc.get("allowedNumbers") or []:
        if isinstance(number, dict):
            append_unique_ref(refs, number.get("key"))
    if not refs and (simc.get("evidenceState") or {}).get("phase") == "report_ready":
        append_unique_ref(refs, "simc.report")
    return refs


def chickenbro_wcl_refs(wcl):
    if not isinstance(wcl, dict):
        return []
    refs = []
    log_evidence = wcl.get("logEvidence") if isinstance(wcl.get("logEvidence"), dict) else wcl
    for ref in log_evidence.get("evidenceRefs") or []:
        append_unique_ref(refs, ref)
    for ref in report_evidence_refs(wcl.get("report")):
        append_unique_ref(refs, ref)
    return refs


def chickenbro_comparison_ready(comparison):
    if not isinstance(comparison, dict):
        return False
    return str(comparison.get("status") or comparison.get("sourceStatus") or "").lower() in {"ready", "verified"}


def build_chickenbro_coach_payload(source):
    source = source if isinstance(source, dict) else {}
    evidence = chickenbro_coach_source_evidence(source)
    character = evidence["character"]
    simc = evidence["simc"]
    wcl = evidence["wcl"]
    comparison = evidence["comparison"]
    simc_refs = chickenbro_simc_refs(simc)
    wcl_refs = chickenbro_wcl_refs(wcl)
    has_character = chickenbro_has_character_context(character)
    has_simc = bool(simc_refs)
    has_wcl = bool(wcl_refs)
    has_comparison = chickenbro_comparison_ready(comparison)

    evidence_refs = []
    if has_character:
        append_unique_ref(evidence_refs, "character.context")
    for ref in simc_refs + wcl_refs:
        append_unique_ref(evidence_refs, ref)
    if has_comparison:
        append_unique_ref(evidence_refs, "comparable.sample")
    if not evidence_refs:
        append_unique_ref(evidence_refs, "coach.scope")

    missing_inputs = []
    if not has_simc:
        append_unique_text(missing_inputs, "simc.report")
    if not has_wcl:
        append_unique_text(missing_inputs, "wcl.events")
    if not has_character:
        append_unique_text(missing_inputs, "character.context")
    if not has_comparison:
        append_unique_text(missing_inputs, "comparable.sample")

    priority_actions = []
    if has_simc:
        priority_actions.append({
            "title": "Use the completed SimC report as the optimization baseline before changing talents or gear.",
            "evidenceRefs": simc_refs[:3],
        })
    if has_wcl:
        priority_actions.append({
            "title": "Review parsed WCL events before making rotation, death, or cooldown claims.",
            "evidenceRefs": wcl_refs[:3],
        })
    if has_character and (has_simc or has_wcl):
        priority_actions.append({
            "title": "Keep class, spec, role, item level, and scenario attached while iterating on advice.",
            "evidenceRefs": ["character.context"],
        })
    priority_actions = [
        action
        for action in priority_actions[:3]
        if action.get("evidenceRefs") and all(ref in evidence_refs for ref in action["evidenceRefs"])
    ]

    if not priority_actions:
        summary = "chickenbro needs traceable SimC, WCL, character, and comparable sample evidence before coaching."
        confidence = "blocked"
    elif has_simc and has_wcl and has_character:
        summary = "chickenbro can organize the supplied SimC and WCL evidence, while ranking or percentile claims still need a matched sample."
        confidence = "high" if has_comparison else "medium"
    else:
        summary = "chickenbro has partial evidence and can only suggest evidence collection and review order."
        confidence = "low"

    next_steps = []
    if "simc.report" in missing_inputs:
        next_steps.append("Attach a completed SimC report or submit a complete /simc profile through the SimC workflow.")
    if "wcl.events" in missing_inputs:
        next_steps.append("Attach a Warcraft Logs report with fetched fight events before asking for log conclusions.")
    if "character.context" in missing_inputs:
        next_steps.append("Provide class, spec, role, item level, and scenario context.")
    if "comparable.sample" in missing_inputs:
        next_steps.append("Add a matched same-spec, same-role, same-scenario sample before asking for rankings or percentiles.")
    if not next_steps:
        next_steps.append("Review the prioritized actions, then rerun after any talent, gear, or gameplay change.")

    coach = {
        "summary": summary,
        "confidence": confidence,
        "evidenceRefs": evidence_refs,
        "priorityActions": priority_actions,
        "missingInputs": missing_inputs,
        "nextSteps": next_steps[:4],
    }
    llm_result = skipped_llm_result("chickenbro coach v0 deterministic evidence schema")
    return {
        "mode": "chickenbro",
        "status": "ready" if priority_actions else "blocked",
        "schemaRevision": "chickenbro-coach-v0",
        "createdAt": utc_now(),
        "coach": coach,
        "recommendations": [action["title"] for action in priority_actions],
        "llm": {
            "prompt": "",
            "called": llm_result["called"],
            "model": llm_result.get("model", llm_model()),
            "content": "",
            "error": llm_result["error"],
        },
    }


def build_llm_prompt(request_data, simulation):
    mythic_plus_reference = request_data.get("mythicPlusReference") if isinstance(request_data, dict) else None
    build_context = request_data.get("buildContext") if isinstance(request_data, dict) else None
    benchmark = simulation.get("benchmark") if isinstance(simulation, dict) else None
    sections = [
        "你是魔兽世界构筑与日志分析助手，请给玩家可执行、可复核的建议。",
        f"分析模式：{request_data['mode']}",
        f"角色/专精：{request_data['character'] or '未提供'}",
        f"玩家问题：{request_data['question'] or '请给出构筑和输出优化建议'}",
    ]
    if request_data["wclUrl"]:
        sections.append(f"WCL 链接：{request_data['wclUrl']}")
    if request_data["profile"]:
        profile = request_data["profile"][:3000]
        sections.append(f"SimCraft profile 或配装输入：\n{profile}")
    if simulation.get("summary"):
        sections.append(f"SimCraft 执行摘要：\n{sanitize_simcraft_summary_for_llm(simulation)}")
    if simulation.get("error"):
        sections.append(f"SimCraft 执行错误：\n{simulation['error']}")
    if mythic_plus_reference:
        sections.append(f"真实大秘境对标：\n{format_mythic_plus_reference_for_prompt(mythic_plus_reference)}")
    if benchmark:
        sections.append(
            "SimC 横向合理性判定：\n"
            f"状态：{benchmark.get('status', '')}\n"
            f"说明：{benchmark.get('summary', '')}\n"
            f"SimC DPS：{benchmark.get('simcDps', '')}\n"
            f"参考窗口：Avg {benchmark.get('referenceAvgDps', '')}, Max {benchmark.get('referenceMaxDps', '')}"
        )
    if build_context:
        sections.append(f"构筑上下文：\n{format_build_context_for_prompt(build_context)}")
    if request_data["mode"] in {"simcraft", "simcraft_agent", "simcraft_template"} and not request_data["profile"]:
        sections.append("缺少可模拟模板：本次只可做输入说明和模板补全建议，不能声称已经完成 SimC 模拟。")
    if request_data["mode"] in {"simcraft", "simcraft_agent", "simcraft_template"}:
        sections.append("数值规则：不得从 Generating Baseline、迭代进度、耗时或中间估算行推断 DPS；只有后端 metrics.dps 或明确 DPS= / DPS Ranking 行才可作为 SimC DPS。真实大秘境结论必须先和对标区间比较，禁止输出数百万级这类与日志量级冲突的结论。")
    sections.append("如果模拟失败或未执行，请直接说明服务器返回的原因，不要把它描述成无法访问本地工具。")
    sections.append("输出格式：先给 3 条优先级最高的结论，再列验证方式和下一步需要补充的数据。")
    return "\n\n".join(sections)


def build_codex_simulator_prompt(request_data, simulation):
    profile = request_data["profile"][:6000] if request_data["profile"] else "未提供"
    summary = simulation.get("summary") or "无"
    error = simulation.get("error") or "无"
    return "\n\n".join([
        "你是 Codex Agent Worker，负责复核魔兽世界 SimCraft 模拟请求。",
        "后端已经先用服务器本地 simc 执行了一次模拟；请基于真实执行状态输出中文复核结论，不要编造 DPS。",
        f"模式：{request_data['mode']}",
        f"问题：{request_data['question'] or '请复核本次 SimC 模拟'}",
        f"SimC 是否运行：{bool(simulation.get('ran'))}",
        f"SimC 错误：{error}",
        f"SimC 输出摘要：\n{summary[:4000]}",
        f"SimC profile：\n{profile}",
        "请输出：1. 是否真实跑通；2. 关键 DPS/属性证据；3. 如果失败，最可能的 profile 问题和下一步修复。",
    ])


def call_codex_worker(request_data, simulation, codex_runner=None):
    enabled = truthy_env("WOW_CODEX_SIMULATOR_ENABLED")
    if not enabled:
        return {
            "enabled": False,
            "called": False,
            "status": "disabled",
            "jobId": "",
            "lastMessage": "",
            "error": "WOW_CODEX_SIMULATOR_ENABLED is not enabled",
        }
    runner = codex_runner or run_codex_job
    if not runner:
        return {
            "enabled": True,
            "called": False,
            "status": "unavailable",
            "jobId": "",
            "lastMessage": "",
            "error": "codex worker is unavailable",
        }
    prompt = build_codex_simulator_prompt(request_data, simulation)
    try:
        result = runner(
            prompt,
            timeout_seconds=int_env("WOW_CODEX_SIMULATOR_TIMEOUT_SECONDS", 180),
        )
    except Exception as error:
        return {
            "enabled": True,
            "called": True,
            "status": "failed",
            "jobId": "",
            "lastMessage": "",
            "error": str(error),
        }
    return {
        "enabled": True,
        "called": True,
        "status": result.get("status", ""),
        "jobId": result.get("jobId", ""),
        "lastMessage": result.get("lastMessage", ""),
        "error": result.get("stderr", ""),
    }


SIMCRAFT_TEMPLATE_TIMEOUT_DEFAULTS = {
    "single": 120,
    "aoe_5": 180,
    "mythic_plus": 240,
}


def optional_int_env(name):
    if name not in os.environ:
        return None
    return int_env(name, 0)


def simcraft_template_timeout_seconds(source):
    request = source if isinstance(source, dict) else {}
    general_timeout = optional_int_env("WOW_SIMC_TEMPLATE_TIMEOUT_SECONDS")
    analysis_type = str(request.get("analysisType") or "").strip()
    if analysis_type == "stat_weights":
        stat_timeout = optional_int_env("WOW_SIMC_TEMPLATE_STAT_WEIGHTS_TIMEOUT_SECONDS")
        if stat_timeout is not None:
            return stat_timeout
        if general_timeout is not None:
            return general_timeout
        return 360
    scenario_key = str(request.get("scenarioKey") or "single").strip() or "single"
    scenario_env = f"WOW_SIMC_TEMPLATE_{re.sub(r'[^A-Za-z0-9]+', '_', scenario_key).upper()}_TIMEOUT_SECONDS"
    scenario_timeout = optional_int_env(scenario_env)
    if scenario_timeout is not None:
        return scenario_timeout
    if general_timeout is not None:
        return general_timeout
    return SIMCRAFT_TEMPLATE_TIMEOUT_DEFAULTS.get(scenario_key, 180)


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


def run_simcraft(profile, timeout_seconds=None):
    binary = simc_binary()
    if not binary:
        return {"ran": False, "available": False, "summary": "", "error": "simcraft binary not found"}
    if not profile.strip():
        return {"ran": False, "available": True, "summary": "", "error": "empty profile"}

    try:
        result = run_simcraft_process(binary, profile, timeout_seconds=timeout_seconds)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ran": False, "available": True, "summary": "", "error": str(error)}

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    output = (stdout or stderr or "").strip()
    metrics = parse_simcraft_metrics(output)
    item_name_diagnostics = simcraft_item_name_diagnostics(stderr)
    trivial_item_name_exit = (
        result.returncode != 0
        and bool(metrics.get("dps"))
        and bool(item_name_diagnostics)
        and simcraft_only_item_name_diagnostics(stderr)
    )
    ran = result.returncode == 0 or trivial_item_name_exit
    return {
        "ran": ran,
        "available": True,
        "summary": output[:4000],
        "metrics": metrics,
        "error": "" if ran else (stderr or f"simc exited {result.returncode}")[:1000],
        **({"simcWarnings": item_name_diagnostics} if item_name_diagnostics else {}),
    }


def run_simcraft_process(binary, profile, timeout_seconds=None):
    try:
        return subprocess.run(
            [binary, "-"],
            input=profile,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds if timeout_seconds is not None else int_env("WOW_SIMC_TIMEOUT_SECONDS", 45),
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


def call_llm(prompt):
    return call_chat_completion(
        "你是面向中文魔兽世界玩家的构筑、SimCraft 和 WCL 分析助手。",
        prompt,
        temperature=0.2,
    )


def skipped_llm_result(reason):
    return {
        "called": False,
        "model": llm_model(),
        "content": "",
        "error": reason,
    }


def heuristic_recommendations(request_data, simulation):
    recommendations = []
    mythic_reference = request_data.get("mythicPlusReference") if isinstance(request_data, dict) else None
    benchmark = simulation.get("benchmark") if isinstance(simulation, dict) else None
    if request_data["mode"] in {"simcraft", "simcraft_agent"}:
        dps = simulation.get("metrics", {}).get("dps")
        if request_data.get("profileSource") == "generated":
            recommendations.append("已识别 SimC 模板骨架；未执行正式 SimC DPS 模拟。请补齐天赋导入码和手选装备数据，或提供完整 SimC profile 后再给出可用于对比的输出。")
        elif simulation.get("ran") and dps:
            recommendations.append(f"本次 SimC 已跑通，当前 profile 约为 {dps} DPS；先把这个作为基准，再比较装备或天赋变体。")
        elif simulation.get("ran"):
            recommendations.append("本次 SimC 已跑通，先把返回摘要作为基准样本，再逐项比较装备、天赋和属性收益。")
        elif not request_data["profile"]:
            recommendations.append("未执行 SimC：当前输入还缺少职业专精或目标场景，请先用自然语言补充。")
        elif simulation.get("error"):
            recommendations.append(f"SimC 未产出可用 DPS：{simulation.get('error')}。")
        if mythic_reference:
            recommendations.append(
                f"真实大秘境对标：{mythic_reference['specName']} 当前样本为 {mythic_reference.get('comparisonText') or mythic_plus_reference_comparison_text(mythic_reference)}；最终报告必须先和这个来源区间比较。"
            )
        if benchmark and str(benchmark.get("status", "")).startswith("outlier"):
            recommendations.append(f"横向校验异常：{benchmark.get('summary')}。先复核 profile、装备完整性和 SimC 版本。")
        elif benchmark and benchmark.get("status") == "reasonable":
            recommendations.append("横向校验：本次 SimC 数字落在外部参考的宽松合理区间内。")
        recommendations.append("下一步只补充最影响结果的变量：天赋、饰品、武器或目标数量。")
        return recommendations[:3]
    if request_data.get("mode") == "simcraft_template":
        recommendations.append("请选择同职业专精的完整天赋模板和 16 槽装备模板后再提交。")
        return recommendations[:3]
    if request_data["wclUrl"]:
        recommendations.append("把 WCL 链接与具体 boss、难度、尝试编号一起提交，才能对齐技能覆盖和死亡时间线。")
    recommendations.append("下一步建议补充职业专精、目标场景、可替换装备列表和当前痛点。")
    return recommendations[:3]


def build_pipeline_stages(request_data, simulation, llm_result):
    has_profile = bool(request_data.get("profile"))
    profile_source = request_data.get("profileSource") or "none"
    dps = (simulation.get("metrics") or {}).get("dps", "")
    mythic_reference = request_data.get("mythicPlusReference") if isinstance(request_data, dict) else None
    benchmark = simulation.get("benchmark") if isinstance(simulation, dict) else None
    is_preview = profile_source == "generated"

    if has_profile:
        profile_stage = {
            "key": "profile_check",
            "title": "Profile 检查",
            "status": "passed",
            "executor": "backend",
            "summary": f"已识别 {profile_source} SimCraft profile",
        }
    else:
        profile_stage = {
            "key": "profile_check",
            "title": "Profile 检查",
            "status": "blocked",
            "executor": "backend",
            "summary": "缺少完整 SimCraft profile",
        }

    if is_preview:
        simc_stage = {
            "key": "simc_execution",
            "title": "正式 SimC DPS",
            "status": "skipped",
            "executor": "simcraft",
            "summary": "generated 模板仅用于确认已识别槽位；需要天赋导入码和手选装备数据或完整 SimC profile 后才执行正式 DPS 模拟。",
            "metric": "",
        }
    elif simulation.get("ran"):
        simc_summary = "SimC 模板试跑已执行成功" if is_preview else "SimC 已执行成功"
        if dps:
            simc_summary = f"SimC 模板试跑已执行成功，{dps} DPS（伤害/秒）" if is_preview else f"SimC 已执行成功，DPS {dps}"
        simc_stage = {
            "key": "simc_execution",
            "title": "SimC 模板试跑" if is_preview else "SimC 执行",
            "status": "completed",
            "executor": "simcraft",
            "summary": simc_summary,
            "metric": dps,
        }
    elif request_data.get("mode") in {"simcraft", "simcraft_agent", "simcraft_template"} and not has_profile:
        simc_stage = {
            "key": "simc_execution",
            "title": "SimC 执行",
            "status": "skipped",
            "executor": "simcraft",
            "summary": simulation.get("error") or "missing simcraft profile",
            "metric": "",
        }
    else:
        simc_stage = {
            "key": "simc_execution",
            "title": "SimC 执行",
            "status": "failed" if simulation.get("error") else "skipped",
            "executor": "simcraft",
            "summary": simulation.get("error") or "simulation not requested",
            "metric": "",
        }

    ai_stage = {
        "key": "ai_interpretation",
        "title": "AI 解读",
        "status": "completed" if llm_result.get("called") and not llm_result.get("error") else ("failed" if llm_result.get("called") else "skipped"),
        "executor": "llm",
        "summary": "已基于真实执行状态生成建议" if llm_result.get("content") else (llm_result.get("error") or "LLM 未配置"),
    }
    stages = [profile_stage, simc_stage]
    if mythic_reference:
        stages.append({
            "key": "mythic_plus_reference",
            "title": "真实大秘境对标",
            "status": "completed",
            "executor": "backend",
            "summary": f"{mythic_reference['specName']}：{mythic_reference.get('comparisonText') or mythic_plus_reference_comparison_text(mythic_reference)}，来源 {mythic_reference['sources'][0]['name']}",
            "metric": mythic_reference["avgDps"],
        })
    if benchmark and benchmark.get("status") != "unverified":
        stages.append({
            "key": "simc_benchmark",
            "title": "SimC 横向合理性",
            "status": "completed" if benchmark.get("status") == "reasonable" else "blocked" if str(benchmark.get("status", "")).startswith("outlier") else "skipped",
            "executor": "backend",
            "summary": benchmark.get("summary", ""),
            "metric": benchmark.get("simcDps", ""),
        })
    stages.append(ai_stage)
    return stages


def parse_simcraft_metrics(output):
    metrics = {}
    text = str(output or "")
    dps_match = re.search(r"\bDPS=(\d+(?:\.\d+)?)", text)
    if dps_match:
        metrics["dps"] = f"{float(dps_match.group(1)):.3f}".rstrip("0").rstrip(".")
        return metrics
    dps_rank_match = re.search(r"\b(\d+(?:\.\d+)?)\s+dps\b", text.replace(",", ""), re.IGNORECASE)
    if dps_rank_match:
        metrics["dps"] = f"{float(dps_rank_match.group(1)):.3f}".rstrip("0").rstrip(".")
    return metrics


def add_allowed_number(allowed, key, value):
    text = str(value or "").strip()
    if key and text:
        entry = {"key": key, "value": text}
        if entry not in allowed:
            allowed.append(entry)


def build_allowed_numbers(request_data, simulation):
    allowed = []
    metrics = (simulation or {}).get("metrics") or {}
    add_allowed_number(allowed, "simc.dps", metrics.get("dps"))
    benchmark = (simulation or {}).get("benchmark") or {}
    add_allowed_number(allowed, "simc.benchmark.simcDps", benchmark.get("simcDps"))
    add_allowed_number(allowed, "simc.benchmark.ratioToAvg", benchmark.get("ratioToAvg"))
    add_allowed_number(allowed, "reference.avgDps", benchmark.get("referenceAvgDps"))
    add_allowed_number(allowed, "reference.maxDps", benchmark.get("referenceMaxDps"))
    reference = (request_data or {}).get("mythicPlusReference") or {}
    add_allowed_number(allowed, "reference.maxKey", reference.get("maxKey"))
    add_allowed_number(allowed, "reference.avgDps", reference.get("avgDps"))
    add_allowed_number(allowed, "reference.maxDps", reference.get("maxDps"))
    return allowed


def allowed_number_tokens(allowed_numbers):
    tokens = set()
    for entry in allowed_numbers or []:
        value = str((entry or {}).get("value") or "").strip()
        if not value:
            continue
        tokens.add(value)
        tokens.add(value.replace(",", ""))
        for match in re.finditer(r"\d+(?:\.\d+)?", value.replace(",", "")):
            tokens.add(match.group(0))
    return tokens


def text_uses_only_allowed_numbers(text, allowed_numbers):
    allowed = allowed_number_tokens(allowed_numbers)
    for match in re.finditer(r"\d[\d,]*(?:\.\d+)?", str(text or "")):
        token = match.group(0).replace(",", "")
        if len(token.split(".", 1)[0]) < 4:
            continue
        if token not in allowed:
            return False
    return True


def clean_report_text(value, limit=220):
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:limit]


def list_text_values(values, limit=160, count=4):
    if not isinstance(values, list):
        return []
    result = []
    for value in values[:count]:
        text = clean_report_text(value, limit)
        if text:
            result.append(text)
    return result


def deterministic_simc_report(request_data, simulation, recommendations, allowed_numbers, reason="fallback"):
    metrics = (simulation or {}).get("metrics") or {}
    benchmark = (simulation or {}).get("benchmark") or {}
    findings = []
    dps = str(metrics.get("dps") or "").strip()
    simulation_error = str((simulation or {}).get("error") or "").strip()
    template_blocked = (
        (request_data or {}).get("mode") == "simcraft_template"
        and not bool((simulation or {}).get("ran"))
        and not bool((request_data or {}).get("runSimulation"))
        and bool(simulation_error)
    )
    confirm_preview = (
        (request_data or {}).get("mode") == "simcraft_template"
        and bool((request_data or {}).get("confirmOnly"))
        and not bool((simulation or {}).get("ran"))
        and not simulation_error
    )
    if template_blocked:
        findings.append({
            "text": clean_report_text(f"Template validation blocked: {simulation_error}"),
            "evidenceRefs": ["simc.templateValidation"],
        })
    elif confirm_preview:
        findings.append({
            "text": "Template payload validated; confirmOnly did not execute SimC or save a task.",
            "evidenceRefs": ["simc.confirmOnly", "simc.template"],
        })
    elif dps:
        findings.append({
            "text": f"SimC completed with DPS {dps}.",
            "evidenceRefs": ["simc.dps"],
        })
    elif simulation_error:
        findings.append({
            "text": "SimC did not produce a parseable DPS result.",
            "evidenceRefs": ["simc.error"],
        })
    else:
        findings.append({
            "text": "No completed SimC DPS result is available for this request.",
            "evidenceRefs": ["simc.runPolicy"],
        })
    if benchmark.get("summary"):
        findings.append({
            "text": clean_report_text(benchmark.get("summary")),
            "evidenceRefs": ["simc.benchmark"],
        })
    actions = list_text_values(recommendations, count=3) or [
        "Provide a complete /simc profile before treating DPS as a real baseline."
    ]
    return {
        "schemaRevision": "simc-report-v1",
        "source": "deterministic_blocked" if template_blocked else ("deterministic_confirm_preview" if confirm_preview else "deterministic_fallback"),
        "fallbackReason": reason,
        "topFindings": findings[:3],
        "nextActions": actions,
        "limitations": [
            "Only numbers listed in allowedNumbers are treated as evidence.",
            "LLM prose is explanatory and cannot create new numeric facts.",
        ],
    }


def normalize_llm_report(llm_result, allowed_numbers):
    payload = extract_json_object((llm_result or {}).get("content") or "")
    if not isinstance(payload, dict):
        return None, "missing_schema_json"
    raw_findings = payload.get("topFindings")
    if not isinstance(raw_findings, list) or not raw_findings:
        return None, "missing_top_findings"
    findings = []
    for item in raw_findings[:4]:
        if not isinstance(item, dict):
            return None, "invalid_finding"
        text = clean_report_text(item.get("text"))
        refs = item.get("evidenceRefs")
        if not text or not isinstance(refs, list) or not refs:
            return None, "missing_evidence_refs"
        refs = [clean_report_text(ref, 80) for ref in refs if clean_report_text(ref, 80)]
        if not refs:
            return None, "missing_evidence_refs"
        if not text_uses_only_allowed_numbers(text, allowed_numbers):
            return None, "unsupported_number"
        findings.append({"text": text, "evidenceRefs": refs[:5]})
    next_actions = list_text_values(payload.get("nextActions"), count=5)
    limitations = list_text_values(payload.get("limitations"), count=5)
    for text in [item["text"] for item in findings] + next_actions + limitations:
        if not text_uses_only_allowed_numbers(text, allowed_numbers):
            return None, "unsupported_number"
    return {
        "schemaRevision": "simc-report-v1",
        "source": "llm_schema",
        "topFindings": findings,
        "nextActions": next_actions,
        "limitations": limitations,
    }, ""


def build_structured_report(request_data, simulation, llm_result, recommendations, allowed_numbers):
    report, reason = normalize_llm_report(llm_result, allowed_numbers)
    if report:
        return report
    return deterministic_simc_report(request_data, simulation, recommendations, allowed_numbers, reason)


def build_run_policy(request_data, simulation, agent=None):
    agent_status = (agent or {}).get("status", "")
    validation = (agent or {}).get("validation") or {}
    profile_source = (request_data or {}).get("profileSource") or "none"
    did_run = bool((simulation or {}).get("ran"))
    can_run = bool((request_data or {}).get("runSimulation") or did_run)
    if agent_status == "template_ready":
        policy = "confirm_only"
    elif profile_source == "generated":
        policy = "preview_only"
    elif did_run:
        policy = "full_simc"
    elif can_run:
        policy = "full_simc"
    else:
        policy = "blocked"
    return {
        "policy": policy,
        "profileSource": profile_source,
        "canRunSimc": can_run,
        "didRunSimc": did_run,
        "requiresFullProfile": profile_source in {"none", "generated"},
        "validationPassed": bool(validation.get("passed", can_run or did_run)),
        "reason": (simulation or {}).get("error") or agent_status or policy,
    }


def build_evidence_state(request_data, simulation, agent=None):
    agent_status = (agent or {}).get("status", "")
    metrics = (simulation or {}).get("metrics") or {}
    if (simulation or {}).get("ran") and metrics.get("dps"):
        phase = "report_ready"
    elif agent_status in {"needs_clarification", "confirmation_failed"}:
        phase = "clarifying"
    elif agent_status == "template_ready":
        phase = "ready_to_submit"
    elif agent_status in {"template_invalid", "simc_failed", "off_topic"} or (simulation or {}).get("error"):
        phase = "blocked"
    elif (request_data or {}).get("profileSource") == "generated":
        phase = "preview_only"
    else:
        phase = "collecting_evidence"
    return {
        "phase": phase,
        "profileSource": (request_data or {}).get("profileSource") or "none",
        "simcRan": bool((simulation or {}).get("ran")),
        "hasDps": bool(metrics.get("dps")),
        "blockers": ([str((simulation or {}).get("error"))] if (simulation or {}).get("error") else []),
    }


def apply_simulation_metric_metadata(request_data, simulation):
    if request_data.get("profileSource") == "generated":
        simulation["quality"] = "preview"
        simulation["metrics"] = {}
        simulation["metricLabel"] = "正式 SimC DPS"
        simulation["metricUnit"] = "需要完整 /simc 导出"
    else:
        simulation.setdefault("quality", "full")
        simulation.setdefault("metricLabel", "DPS")
        simulation.setdefault("metricUnit", "伤害/秒")
    return simulation


SIMCRAFT_TEMPLATE_SCENARIOS = {
    "single": {
        "fightStyle": "Patchwerk",
        "durationSeconds": 300,
        "targets": 1,
        "label": "单体基准",
    },
    "aoe_5": {
        "fightStyle": "Patchwerk",
        "durationSeconds": 300,
        "targets": 5,
        "label": "5目标AOE基准",
    },
    "mythic_plus": {
        "fightStyle": "DungeonSlice",
        "durationSeconds": 360,
        "targets": 5,
        "label": "近似大秘境",
    },
}


def simcraft_template_scenario(source):
    key = str((source or {}).get("scenarioKey") or "single").strip()
    scenario = dict(SIMCRAFT_TEMPLATE_SCENARIOS.get(key) or SIMCRAFT_TEMPLATE_SCENARIOS["single"])
    scenario["key"] = key if key in SIMCRAFT_TEMPLATE_SCENARIOS else "single"
    return scenario


def simcraft_template_intent(source):
    value = str((source or {}).get("analysisType") or "baseline").strip()
    return "stat_weights" if value == "stat_weights" else "baseline"


def simcraft_template_filled_slots(source, spec_info, scenario):
    context = source.get("templateContext") if isinstance(source.get("templateContext"), dict) else {}
    talent = context.get("talent") if isinstance(context.get("talent"), dict) else {}
    return {
        "class": (spec_info or {}).get("class") or str(talent.get("classKey") or "").strip(),
        "classLabel": (spec_info or {}).get("classLabel") or str(talent.get("className") or "").strip(),
        "spec": (spec_info or {}).get("spec") or str(talent.get("specKey") or "").strip(),
        "specLabel": (spec_info or {}).get("specLabel") or str(talent.get("specName") or "").strip(),
        "scenario": scenario.get("label", ""),
        "fightStyle": scenario.get("fightStyle", ""),
        "targets": scenario.get("targets", 1),
        "durationSeconds": scenario.get("durationSeconds", 300),
    }


def simcraft_template_blocked_payload(source, request_data, errors, scenario, spec_info):
    error_text = "; ".join(errors or ["template validation failed"])
    simulation = {
        "ran": False,
        "available": bool(simc_binary()),
        "summary": "",
        "error": error_text,
        "metrics": {},
    }
    agent = {
        "status": "template_blocked",
        "round": 1,
        "intent": simcraft_template_intent(source),
        "confidence": 1.0,
        "missingSlots": [],
        "filledSlots": simcraft_template_filled_slots(source, spec_info, scenario),
        "question": "",
        "quickReplies": [],
        "draftProfile": "",
        "validation": {"passed": False, "errors": errors or [error_text], "warnings": []},
        "canSubmitTask": False,
        "summaryCards": build_agent_summary_cards(request_data, simulation, scenario),
        "scenario": scenario,
    }
    llm_result = skipped_llm_result("template validation blocked")
    codex_result = skipped_codex_worker_result(error_text)
    return build_simc_agent_payload(request_data, simulation, agent, llm_result, codex_result)


def analyze_simcraft_template_request(payload, codex_runner=None):
    source = payload if isinstance(payload, dict) else {}
    build_context = normalize_build_context(source.get("buildContext"))
    scenario = simcraft_template_scenario(source)
    intent = simcraft_template_intent(source)
    template_context = source.get("templateContext") if isinstance(source.get("templateContext"), dict) else {}
    talent_template = template_context.get("talent") if isinstance(template_context.get("talent"), dict) else {}
    gear_template = template_context.get("gear") if isinstance(template_context.get("gear"), dict) else {}
    spec_info = spec_info_from_keys(talent_template.get("classKey"), talent_template.get("specKey")) or spec_info_from_build_context(build_context)
    validation_source = source.get("templateValidation") if isinstance(source.get("templateValidation"), dict) else {}
    validation_errors = [str(item) for item in validation_source.get("errors") or [] if str(item or "").strip()]
    message = simc_agent_message(source) or "SimC 模板组合基准"

    request_data = {
        "mode": "simcraft_template",
        "character": str(source.get("character") or "").strip() or (
            f"{talent_template.get('specName', '')}{talent_template.get('className', '')}".strip()
        ),
        "prompt": message,
        "profile": "",
        "profileSource": "template",
        "wclUrl": "",
        "question": message,
        "runSimulation": False,
        "buildContext": build_context,
        "templateContext": template_context,
        "raceKey": build_context.get("raceKey", "") if build_context else "",
        "raceName": build_context.get("raceName", "") if build_context else "",
        "scenarioKey": str(source.get("scenarioKey") or "single").strip() or "single",
        "analysisType": intent,
        "temporaryBuffs": source.get("temporaryBuffs") if isinstance(source.get("temporaryBuffs"), dict) else {},
        "confirmOnly": bool(source.get("confirmOnly")),
        "saveTask": bool(source.get("saveTask")),
    }

    if validation_errors:
        return simcraft_template_blocked_payload(source, request_data, validation_errors, scenario, spec_info)
    if not spec_info:
        return simcraft_template_blocked_payload(source, request_data, ["unknown template class/spec"], scenario, spec_info)
    if not build_context_has_talents(build_context):
        return simcraft_template_blocked_payload(source, request_data, ["missing talent template SimC input"], scenario, spec_info)
    gear_items = request_gear_items(source, build_context)
    if not gear_items:
        return simcraft_template_blocked_payload(source, request_data, ["missing gear template SimC items"], scenario, spec_info)

    base_profile = build_generated_simc_profile(spec_info, None, build_context, gear_items)
    temporary_buffs = request_data.get("temporaryBuffs") if isinstance(request_data.get("temporaryBuffs"), dict) else {}
    preparation = simc_preparation_payload(spec_info.get("class"), spec_info.get("spec"), temporary_buffs=temporary_buffs)
    draft_profile = build_agent_simc_profile(base_profile, intent, scenario, "template", temporary_buffs=temporary_buffs)
    validation = validate_agent_simc_profile(draft_profile)
    request_data["profile"] = draft_profile
    request_data["preparation"] = simc_preparation_report(preparation)
    request_data["mythicPlusReference"] = build_mythic_plus_reference(draft_profile, scenario)
    confirm_only = bool(source.get("confirmOnly"))
    execute_simc = bool(source.get("executeSimc") or source.get("_executeSimcTask"))
    request_data["runSimulation"] = validation["passed"] and execute_simc and not confirm_only

    if validation["passed"] and confirm_only:
        simulation = {
            "ran": False,
            "available": bool(simc_binary()),
            "summary": "",
            "error": "",
            "metrics": {},
        }
    elif validation["passed"] and execute_simc:
        simulation = run_simcraft(draft_profile, timeout_seconds=simcraft_template_timeout_seconds(request_data))
    elif validation["passed"]:
        simulation = {
            "ran": False,
            "available": bool(simc_binary()),
            "summary": "",
            "error": "",
            "metrics": {},
        }
    else:
        simulation = {
            "ran": False,
            "available": bool(simc_binary()),
            "summary": "",
            "error": "; ".join(validation["errors"]) or "template invalid",
            "metrics": {},
        }
    simulation = dict(simulation)
    simulation["metrics"] = simulation.get("metrics") or parse_simcraft_metrics(simulation.get("summary", ""))
    simulation = apply_simulation_metric_metadata(request_data, simulation)
    simulation = apply_simc_benchmark(request_data, simulation)
    status = "template_ready" if validation["passed"] and (confirm_only or not execute_simc) else (
        "simc_completed" if simulation.get("ran") else ("template_invalid" if not validation["passed"] else "simc_failed")
    )
    can_submit_task = validation["passed"] if confirm_only else bool(validation["passed"] and simulation.get("ran"))
    agent = {
        "status": status,
        "round": 1,
        "intent": intent,
        "confidence": 1.0,
        "missingSlots": [],
        "filledSlots": simcraft_template_filled_slots(source, spec_info, scenario),
        "question": "",
        "quickReplies": [],
        "draftProfile": draft_profile,
        "validation": validation,
        "canSubmitTask": can_submit_task,
        "summaryCards": build_agent_summary_cards(request_data, simulation, scenario),
        "scenario": scenario,
    }
    llm_result = skipped_llm_result("simcraft template deterministic path")
    codex_result = skipped_codex_worker_result("simcraft template deterministic path")
    return build_simc_agent_payload(request_data, simulation, agent, llm_result, codex_result)


def analyze_simc_agent_request(payload, codex_runner=None):
    source = payload if isinstance(payload, dict) else {}
    build_context = normalize_build_context(source.get("buildContext"))
    message = simc_agent_message(source)
    round_number = normalize_agent_round(source.get("round") or source.get("conversationRound"))
    intent = infer_simc_agent_intent(message)
    scenario = infer_simc_agent_scenario(message)
    spec_info = infer_simc_agent_specialization(message) or spec_info_from_build_context(build_context)
    item_level = infer_simc_agent_item_level(message)
    filled_slots = build_agent_filled_slots(message, spec_info, scenario, item_level)
    explicit_profile = str(source.get("profile") or "").strip()
    explicit_profile_source = str(source.get("profileSource") or "").strip()
    extracted_profile = extract_simc_profile_from_prompt(message)
    source_profile = explicit_profile or extracted_profile
    gear_items = request_gear_items(source, build_context)
    generated_profile = "" if source_profile else build_generated_simc_profile(spec_info, item_level, build_context, gear_items)
    assembled_profile = bool(generated_profile and build_context_has_talents(build_context) and gear_items)
    profile_source = (
        explicit_profile_source
        if explicit_profile and explicit_profile_source in {"websim", "explicit"}
        else ("explicit" if explicit_profile else ("prompt" if extracted_profile else ("assembled" if assembled_profile else ("generated" if generated_profile else "none"))))
    )
    missing_slots = build_simc_agent_missing_slots(source_profile, generated_profile, spec_info, message, build_context, gear_items)

    request_data = {
        "mode": "simcraft_agent",
        "character": str(source.get("character") or "").strip() or (
            f"{build_context.get('specName', '')}{build_context.get('className', '')}" if build_context else ""
        ),
        "prompt": message,
        "profile": "",
        "profileSource": profile_source,
        "wclUrl": str(source.get("wclUrl") or "").strip(),
        "question": message,
        "runSimulation": False,
        "buildContext": build_context,
    }
    confirm_only = bool(source.get("confirmOnly"))

    if intent == "out_of_scope":
        simulation = {
            "ran": False,
            "available": bool(simc_binary()),
            "summary": "",
            "error": "out of scope",
            "metrics": {},
        }
        agent = {
            "status": "off_topic",
            "round": round_number,
            "intent": intent,
            "confidence": 0.95,
            "missingSlots": [],
            "filledSlots": filled_slots,
            "question": "这个问题不属于 SimC 模拟范围。我可以帮你做角色 DPS、装备、饰品、天赋或属性收益模拟。",
            "quickReplies": ["跑当前角色基准", "比较装备收益", "查看属性收益"],
            "draftProfile": "",
            "validation": {"passed": False, "errors": ["out of scope"], "warnings": []},
            "summaryCards": build_agent_summary_cards(request_data, simulation, scenario),
        }
        llm_result = skipped_llm_result("template confirmation") if confirm_only else call_llm(build_llm_prompt(request_data, simulation))
        codex_result = skipped_codex_worker_result("out of scope")
        return build_simc_agent_payload(request_data, simulation, agent, llm_result, codex_result)

    if missing_slots:
        status = "needs_clarification"
        simulation = {
            "ran": False,
            "available": bool(simc_binary()),
            "summary": "",
            "error": "; ".join(f"missing {slot}" for slot in missing_slots),
            "metrics": {},
        }
        request_data["mythicPlusReference"] = build_mythic_plus_reference_from_slots(filled_slots, scenario)
        agent = {
            "status": status,
            "round": round_number,
            "intent": intent,
            "confidence": 0.78,
            "missingSlots": missing_slots,
            "filledSlots": filled_slots,
            "question": build_agent_clarification_question(missing_slots, round_number, filled_slots),
            "quickReplies": build_agent_quick_replies(missing_slots, filled_slots),
            "draftProfile": "",
            "validation": {"passed": False, "errors": missing_slots, "warnings": []},
            "summaryCards": build_agent_summary_cards(request_data, simulation, scenario),
        }
        if confirm_only:
            llm_result = call_simc_confirmation_llm(request_data, agent, generated_profile)
            agent = apply_llm_confirmation(agent, llm_result, generated_profile)
            agent["summaryCards"] = build_agent_summary_cards(request_data, simulation, scenario)
        else:
            llm_result = call_llm(build_llm_prompt(request_data, simulation))
        codex_result = skipped_codex_worker_result("; ".join(f"missing {slot}" for slot in missing_slots))
        return build_simc_agent_payload(request_data, simulation, agent, llm_result, codex_result)

    draft_profile = build_agent_simc_profile(source_profile or generated_profile, intent, scenario, profile_source)
    validation = validate_agent_simc_profile(draft_profile)
    request_data["profile"] = draft_profile
    request_data["mythicPlusReference"] = build_mythic_plus_reference(draft_profile, scenario)
    is_generated_profile = profile_source == "generated"
    request_data["runSimulation"] = validation["passed"] and not confirm_only and not is_generated_profile
    if validation["passed"] and confirm_only:
        simulation = {
            "ran": False,
            "available": bool(simc_binary()),
            "summary": "",
            "error": "",
            "metrics": {},
        }
    elif validation["passed"] and is_generated_profile:
        simulation = {
            "ran": False,
            "available": bool(simc_binary()),
            "summary": "",
            "error": "",
            "metrics": {},
        }
    elif validation["passed"]:
        simulation = run_simcraft(draft_profile)
    else:
        simulation = {
            "ran": False,
            "available": bool(simc_binary()),
            "summary": "",
            "error": "; ".join(validation["errors"]) or "template invalid",
    }
    simulation = dict(simulation)
    simulation["metrics"] = simulation.get("metrics") or parse_simcraft_metrics(simulation.get("summary", ""))
    simulation = apply_simulation_metric_metadata(request_data, simulation)
    simulation = apply_simc_benchmark(request_data, simulation)
    status = "template_ready" if validation["passed"] and confirm_only else (
        "template_preview" if validation["passed"] and is_generated_profile else
        "simc_completed" if simulation.get("ran") else ("template_invalid" if not validation["passed"] else "simc_failed")
    )
    agent = {
        "status": status,
        "round": round_number,
        "intent": intent,
        "confidence": 0.88,
        "missingSlots": [],
        "filledSlots": filled_slots,
        "question": "",
        "quickReplies": [],
        "draftProfile": draft_profile,
        "validation": validation,
        "canSubmitTask": validation["passed"],
        "summaryCards": build_agent_summary_cards(request_data, simulation, scenario),
        "scenario": scenario,
    }
    if validation["passed"] and confirm_only:
        llm_result = call_simc_confirmation_llm(request_data, agent, draft_profile)
        agent = apply_llm_confirmation(agent, llm_result, draft_profile)
        agent["summaryCards"] = build_agent_summary_cards(request_data, simulation, scenario)
    elif validation["passed"] and is_generated_profile:
        llm_result = skipped_llm_result("generated template preview")
    else:
        llm_result = call_llm(build_llm_prompt(request_data, simulation))
    codex_result = call_codex_worker(request_data, simulation, codex_runner=codex_runner) if validation["passed"] and not confirm_only and not is_generated_profile else skipped_codex_worker_result("template confirmation" if confirm_only else ("generated template preview" if is_generated_profile else "template invalid"))
    return build_simc_agent_payload(request_data, simulation, agent, llm_result, codex_result)


def build_simc_agent_payload(request_data, simulation, agent, llm_result, codex_result):
    stages = build_pipeline_stages(request_data, simulation, llm_result)
    recommendations = heuristic_recommendations(request_data, simulation)
    guarded_llm_content = build_guarded_llm_content(request_data, simulation, llm_result)
    if agent["status"] == "needs_clarification":
        recommendations = [agent["question"]]
    elif agent["status"] == "confirmation_failed":
        recommendations = [agent["question"]]
    elif agent["status"] == "off_topic":
        recommendations = [agent["question"]]
    elif agent["status"] == "template_blocked":
        recommendations = list((agent.get("validation") or {}).get("errors") or recommendations)[:3]
    elif agent["status"] == "template_ready":
        if request_data.get("mode") == "simcraft_template":
            recommendations = ["模板组合已确认，可以提交执行 SimC。"]
        elif request_data.get("profileSource") == "generated":
            recommendations = ["需求已确认，当前只能保存 SimC 模板预览；需要天赋导入码和手选装备数据或完整 SimC profile 后才会执行正式 DPS 模拟。"]
        elif request_data.get("profileSource") == "assembled":
            recommendations = ["需求、天赋和手选装备已确认，可以提交执行 SimC。"]
        else:
            recommendations = ["需求和 /simc 输入已确认，可以提交执行 SimC。"]
    allowed_numbers = build_allowed_numbers(request_data, simulation)
    report = build_structured_report(request_data, simulation, llm_result, recommendations, allowed_numbers)
    return {
        "mode": request_data.get("mode") or "simcraft_agent",
        "status": "ready",
        "createdAt": utc_now(),
        "capabilities": {
            "simcraft": bool(simc_binary()),
            "llm": llm_configured(),
            "codex": codex_result["enabled"],
        },
        "request": request_data,
        "agent": agent,
        "stages": stages,
        "simulation": simulation,
        "evidenceState": build_evidence_state(request_data, simulation, agent),
        "runPolicy": build_run_policy(request_data, simulation, agent),
        "allowedNumbers": allowed_numbers,
        "report": report,
        "mythicPlusReference": request_data.get("mythicPlusReference"),
        "codex": codex_result,
        "recommendations": recommendations,
        "llm": {
            "prompt": build_llm_prompt(request_data, simulation),
            "called": llm_result["called"],
            "model": llm_result.get("model", llm_model()),
            "content": guarded_llm_content,
            "error": llm_result["error"],
        },
    }


def analyze_simulator_request(payload, codex_runner=None):
    source = payload if isinstance(payload, dict) else {}
    if (source.get("mode") or "") == "simcraft_template":
        return analyze_simcraft_template_request(source, codex_runner=codex_runner)
    if (source.get("mode") or "") == "simcraft_agent":
        return analyze_simc_agent_request(source, codex_runner=codex_runner)
    if (source.get("mode") or "") == "chickenbro":
        return build_chickenbro_coach_payload(source)

    request_data = normalize_analysis_request(payload)
    if request_data["mode"] == "wcl":
        return build_wcl_analysis_payload(request_data)
    scenario = infer_simc_agent_scenario(request_data["question"] or request_data["prompt"])
    request_data["mythicPlusReference"] = build_mythic_plus_reference(request_data["profile"], scenario)
    if request_data["runSimulation"]:
        simulation = run_simcraft(request_data["profile"])
    else:
        simulation = {
            "ran": False,
            "available": bool(simc_binary()),
            "summary": "",
            "error": "missing simcraft profile" if is_simcraft_mode(request_data["mode"]) and not request_data["profile"] else "simulation not requested",
    }
    simulation = dict(simulation)
    simulation["metrics"] = simulation.get("metrics") or parse_simcraft_metrics(simulation.get("summary", ""))
    simulation = apply_simulation_metric_metadata(request_data, simulation)
    simulation = apply_simc_benchmark(request_data, simulation)
    prompt = build_llm_prompt(request_data, simulation)
    llm_result = call_llm(prompt)
    guarded_llm_content = build_guarded_llm_content(request_data, simulation, llm_result)
    codex_result = call_codex_worker(request_data, simulation, codex_runner=codex_runner)
    stages = build_pipeline_stages(request_data, simulation, llm_result)
    recommendations = heuristic_recommendations(request_data, simulation)
    allowed_numbers = build_allowed_numbers(request_data, simulation)
    report = build_structured_report(request_data, simulation, llm_result, recommendations, allowed_numbers)

    return {
        "mode": request_data["mode"],
        "status": "ready",
        "createdAt": utc_now(),
        "capabilities": {
            "simcraft": bool(simc_binary()),
            "llm": llm_configured(),
            "codex": codex_result["enabled"],
        },
        "request": request_data,
        "stages": stages,
        "simulation": simulation,
        "evidenceState": build_evidence_state(request_data, simulation),
        "runPolicy": build_run_policy(request_data, simulation),
        "allowedNumbers": allowed_numbers,
        "report": report,
        "mythicPlusReference": request_data.get("mythicPlusReference"),
        "codex": codex_result,
        "recommendations": recommendations,
        "llm": {
            "prompt": prompt,
            "called": llm_result["called"],
            "model": llm_result.get("model", llm_model()),
            "content": guarded_llm_content,
            "error": llm_result["error"],
        },
    }

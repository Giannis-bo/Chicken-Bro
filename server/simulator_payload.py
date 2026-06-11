import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

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


DEFAULT_SIMC_VERSION_FILE = "/var/lib/wow-backend/simc-version.json"
SIMC_AGENT_FORBIDDEN_KEYS = {"html", "json", "output", "save", "xml"}
SIMC_AGENT_OFF_TOPIC_PATTERNS = [
    "代打",
    "卡bug",
    "卡 bug",
    "外挂",
    "脚本刷",
    "写代码",
    "剧情",
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
SIMC_AGENT_DEFAULT_RACE_BY_CLASS = {
    "demonhunter": "night_elf",
    "evoker": "dracthyr",
    "paladin": "human",
}
SIMC_AGENT_SPEC_BY_KEY = {
    f'{entry["key"]}-{spec["key"]}': {
        "class": entry["key"],
        "classLabel": entry["label"],
        "spec": spec["key"],
        "specLabel": spec["label"],
        "role": spec["role"],
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


def build_agent_filled_slots(text, spec_info, scenario, item_level):
    class_info = infer_simc_agent_class(text)
    return {
        "class": (spec_info or {}).get("class") or ((class_info or {}).get("class") or ""),
        "classLabel": (spec_info or {}).get("classLabel") or ((class_info or {}).get("label") or ""),
        "spec": (spec_info or {}).get("spec") or "",
        "specLabel": (spec_info or {}).get("specLabel") or "",
        "itemLevel": item_level,
        "scenario": scenario.get("label", ""),
        "fightStyle": scenario.get("fightStyle", ""),
        "targets": scenario.get("targets", 1),
    }


def clean_context_value(value, limit=240):
    return str(value or "").strip()[:limit]


def clean_context_list(values, limit=6):
    if not isinstance(values, list):
        return []
    return [clean_context_value(item, 120) for item in values[:limit] if clean_context_value(item, 120)]


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


def normalize_build_context(value):
    if not isinstance(value, dict):
        return None
    details = value.get("details") if isinstance(value.get("details"), dict) else {}
    talents = details.get("talents") if isinstance(details.get("talents"), dict) else {}
    gear = details.get("gear") if isinstance(details.get("gear"), dict) else {}
    stat_weights = details.get("statWeights") if isinstance(details.get("statWeights"), dict) else {}
    return {
        "specId": clean_context_value(value.get("specId"), 80),
        "className": clean_context_value(value.get("className"), 40),
        "specName": clean_context_value(value.get("specName"), 40),
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
                "sourceName": clean_context_value(talents.get("sourceName"), 80),
                "sourceUrl": clean_context_value(talents.get("sourceUrl"), 180),
                "coreTalents": clean_context_list(talents.get("coreTalents"), 8),
            },
            "gear": {
                "gear": clean_context_rows(gear.get("gear"), ["slot", "name", "source"], 8),
            },
            "statWeights": {
                "stats": clean_context_rows(stat_weights.get("stats"), ["name", "value", "percent"], 6),
            },
        },
    }


def spec_info_from_build_context(context):
    if not context:
        return None
    spec_id = context.get("specId", "")
    class_label = context.get("className", "")
    spec_label = context.get("specName", "")
    for entry in SIMC_AGENT_SPEC_PATTERNS:
        if class_label and spec_label and entry["classLabel"] == class_label and entry["specLabel"] == spec_label:
            return entry
        if spec_id in {f'{entry["classLabel"]}-{entry["specLabel"]}', f'{entry["specLabel"]}{entry["classLabel"]}'}:
            return entry
    return None


def build_simc_agent_missing_slots(source_profile, generated_profile, spec_info, message, build_context=None):
    if source_profile:
        return []
    if not spec_info:
        return ["specialization"]
    missing_slots = []
    if generated_profile and not build_context and not has_explicit_simc_agent_item_level(message):
        missing_slots.append("itemLevel")
    if generated_profile and not has_explicit_simc_agent_scenario(message):
        missing_slots.append("scenario")
    return missing_slots


def build_context_talent_import_code(context):
    if not context:
        return ""
    return (((context.get("details") or {}).get("talents") or {}).get("importCode") or "").strip()


def build_generated_simc_profile(spec_info, item_level, build_context=None):
    if not spec_info:
        return ""
    default_race = SIMC_AGENT_DEFAULT_RACE_BY_CLASS.get(spec_info["class"], "troll")
    lines = [
        f'{spec_info["class"]}="{spec_info["actor"]}"',
        "level=80",
        f"race={default_race}",
        f'role={spec_info["role"]}',
        f'spec={spec_info["spec"]}',
        f"scale_to_itemlevel={item_level}",
    ]
    talent_code = build_context_talent_import_code(build_context)
    if talent_code:
        lines.append(f"talents={talent_code}")
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


def build_agent_simc_profile(profile, intent, scenario, profile_source=""):
    lines = [line.rstrip() for line in str(profile or "").splitlines() if line.strip()]
    if not lines:
        return ""
    lines.append("")
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
    needs_backend_guard = bool(reference and simc_error and not dps)
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
        verify_line = "验证方式：优先对比近两周同专精、相近装等、相近层数的大秘境日志；系统模板修复后再把模拟结果和日志区间并排输出。"

    return "\n\n".join([
        "## 优先级最高的 3 条结论",
        f"1. **{simc_line}** 本次不能把未完成的 SimC 当作 DPS 标准，也不能从执行进度数字推断输出。",
        (
            f"2. **真实大秘境对标**：{reference.get('specName', '')} 当前高端样本为 "
            f"{reference.get('comparisonText') or mythic_plus_reference_comparison_text(reference)}，"
            f"最高钥石 {reference.get('maxKey', '')}。结论必须围绕这个量级解释。"
        ),
        boundary_line,
        verify_line,
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
    if text and "talents=" not in text:
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
    if "specialization" in missing_slots:
        if slots.get("classLabel"):
            specs = "、".join(next((entry["specs"] for entry in SIMC_AGENT_CLASS_PATTERNS if entry["class"] == slots.get("class")), []))
            return f"已收到：{slots.get('itemLevel')} 装等{slots.get('classLabel')}、{slots.get('scenario') or '目标场景'}。还差专精：{specs or '请补充具体专精'}。"
        return "先告诉我职业和专精，再说想看单体、AOE、属性收益、天赋还是装备对比。"
    if "itemLevel" in missing_slots and "scenario" in missing_slots:
        spec_label = f"{slots.get('specLabel', '')}{slots.get('classLabel', '')}".strip()
        return f"已收到：{spec_label or '当前专精'}。还差装等和模拟场景，请补充例如“700 装等，单体 5 分钟”或“大秘境多目标”。"
    if "itemLevel" in missing_slots:
        return "还差装等：请告诉我当前角色装等，例如 700、710 或 720。"
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
        "desc": "把模拟、日志复盘和历史任务收束到同一个入口，先选择分析类型，再进入对应工作台。",
        "analysisModules": [
            {
                "key": "simc",
                "badge": "01",
                "title": "模拟 SimC",
                "desc": "用中文描述职业专精、装等和目标场景，进入专属工作台生成模拟结论。",
                "action": "进入模拟",
            },
            {
                "key": "wcl",
                "badge": "02",
                "title": "分析 WCL",
                "desc": "提交战斗日志链接和问题，复盘输出、爆发、覆盖率与关键失误。",
                "action": "进入分析",
            },
            {
                "key": "tasks",
                "badge": "03",
                "title": "任务列表",
                "desc": "查看最近提交过的模拟和日志分析任务，继续追踪结果。",
                "action": "查看记录",
            },
        ],
        "quickActions": [
            {"key": "simc", "title": "模拟 SimC", "desc": "进入 SimC 工作台。"},
            {"key": "wcl", "title": "分析 WCL", "desc": "进入 WCL 工作台。"},
            {"key": "tasks", "title": "任务列表", "desc": "查看最近任务。"},
        ],
        "tasks": [
            {"title": "SimC 智能模拟", "status": "可提交", "desc": "后端会基于对话生成模板，并返回模拟状态、摘要和 AI prompt。"},
            {"title": "WCL 战斗日志分析", "status": "可分析", "desc": "先结构化日志 URL 和问题，再生成复盘建议。"},
        ],
        "capabilities": {
            "simcraft": has_simc,
            "llm": has_llm,
            "wcl": True,
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


def build_llm_prompt(request_data, simulation):
    mythic_plus_reference = request_data.get("mythicPlusReference") if isinstance(request_data, dict) else None
    build_context = request_data.get("buildContext") if isinstance(request_data, dict) else None
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
    if build_context:
        sections.append(f"构筑上下文：\n{format_build_context_for_prompt(build_context)}")
    if request_data["mode"] in {"simcraft", "simcraft_agent"} and not request_data["profile"]:
        sections.append("缺少可模拟模板：本次只可做输入说明和模板补全建议，不能声称已经完成 SimC 模拟。")
    if request_data["mode"] in {"simcraft", "simcraft_agent"}:
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


def run_simcraft(profile):
    binary = simc_binary()
    if not binary:
        return {"ran": False, "available": False, "summary": "", "error": "simcraft binary not found"}
    if not profile.strip():
        return {"ran": False, "available": True, "summary": "", "error": "empty profile"}

    try:
        result = subprocess.run(
            [binary, "-"],
            input=profile,
            text=True,
            capture_output=True,
            timeout=int_env("WOW_SIMC_TIMEOUT_SECONDS", 45),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ran": False, "available": True, "summary": "", "error": str(error)}

    output = (result.stdout or result.stderr or "").strip()
    metrics = parse_simcraft_metrics(output)
    return {
        "ran": result.returncode == 0,
        "available": True,
        "summary": output[:4000],
        "metrics": metrics,
        "error": "" if result.returncode == 0 else (result.stderr or f"simc exited {result.returncode}")[:1000],
    }


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
    if request_data["mode"] in {"simcraft", "simcraft_agent"}:
        dps = simulation.get("metrics", {}).get("dps")
        if simulation.get("ran") and dps and request_data.get("profileSource") == "generated":
            recommendations.append(f"SimC 模板试跑已跑通，输出为 {dps} DPS（伤害/秒）；这只说明自动生成模板可执行，不能代表真实角色输出。")
        elif simulation.get("ran") and dps:
            recommendations.append(f"本次 SimC 已跑通，当前 profile 约为 {dps} DPS；先把这个作为基准，再比较装备或天赋变体。")
        elif simulation.get("ran") and request_data.get("profileSource") == "generated":
            recommendations.append("SimC 模板试跑已跑通，但未解析到 DPS；它只表示自动生成模板可执行，正式比较仍需要完整 /simc 导出。")
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
        recommendations.append("下一步只补充最影响结果的变量：天赋、饰品、武器或目标数量。")
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

    if simulation.get("ran"):
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
    elif request_data.get("mode") in {"simcraft", "simcraft_agent"} and not has_profile:
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


def apply_simulation_metric_metadata(request_data, simulation):
    if request_data.get("profileSource") == "generated":
        simulation["quality"] = "preview"
        simulation["metricLabel"] = "模板试跑 DPS"
        simulation["metricUnit"] = "伤害/秒"
    else:
        simulation.setdefault("quality", "full")
        simulation.setdefault("metricLabel", "DPS")
        simulation.setdefault("metricUnit", "伤害/秒")
    return simulation


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
    extracted_profile = extract_simc_profile_from_prompt(message)
    source_profile = explicit_profile or extracted_profile
    generated_profile = "" if source_profile else build_generated_simc_profile(spec_info, item_level, build_context)
    profile_source = "explicit" if explicit_profile else ("prompt" if extracted_profile else ("generated" if generated_profile else "none"))
    missing_slots = build_simc_agent_missing_slots(source_profile, generated_profile, spec_info, message, build_context)

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
        llm_result = call_llm(build_llm_prompt(request_data, simulation))
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
        llm_result = call_llm(build_llm_prompt(request_data, simulation))
        codex_result = skipped_codex_worker_result("; ".join(f"missing {slot}" for slot in missing_slots))
        return build_simc_agent_payload(request_data, simulation, agent, llm_result, codex_result)

    draft_profile = build_agent_simc_profile(source_profile or generated_profile, intent, scenario, profile_source)
    validation = validate_agent_simc_profile(draft_profile)
    request_data["profile"] = draft_profile
    request_data["mythicPlusReference"] = build_mythic_plus_reference(draft_profile, scenario)
    request_data["runSimulation"] = validation["passed"] and not confirm_only
    if validation["passed"] and confirm_only:
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
    status = "template_ready" if validation["passed"] and confirm_only else (
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
    llm_result = skipped_llm_result("template confirmation") if validation["passed"] and confirm_only else call_llm(build_llm_prompt(request_data, simulation))
    codex_result = call_codex_worker(request_data, simulation, codex_runner=codex_runner) if validation["passed"] and not confirm_only else skipped_codex_worker_result("template confirmation" if confirm_only else "template invalid")
    return build_simc_agent_payload(request_data, simulation, agent, llm_result, codex_result)


def build_simc_agent_payload(request_data, simulation, agent, llm_result, codex_result):
    stages = build_pipeline_stages(request_data, simulation, llm_result)
    recommendations = heuristic_recommendations(request_data, simulation)
    guarded_llm_content = build_guarded_llm_content(request_data, simulation, llm_result)
    if agent["status"] == "needs_clarification":
        recommendations = [agent["question"]]
    elif agent["status"] == "off_topic":
        recommendations = [agent["question"]]
    elif agent["status"] == "template_ready":
        recommendations = ["需求已确认，可以提交 SimC 任务。"]
    return {
        "mode": "simcraft_agent",
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
    if (source.get("mode") or "") == "simcraft_agent":
        return analyze_simc_agent_request(source, codex_runner=codex_runner)

    request_data = normalize_analysis_request(payload)
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
    prompt = build_llm_prompt(request_data, simulation)
    llm_result = call_llm(prompt)
    guarded_llm_content = build_guarded_llm_content(request_data, simulation, llm_result)
    codex_result = call_codex_worker(request_data, simulation, codex_runner=codex_runner)
    stages = build_pipeline_stages(request_data, simulation, llm_result)

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
        "mythicPlusReference": request_data.get("mythicPlusReference"),
        "codex": codex_result,
        "recommendations": heuristic_recommendations(request_data, simulation),
        "llm": {
            "prompt": prompt,
            "called": llm_result["called"],
            "model": llm_result.get("model", llm_model()),
            "content": guarded_llm_content,
            "error": llm_result["error"],
        },
    }

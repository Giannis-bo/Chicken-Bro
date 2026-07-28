"""Backend-owned specialization support boundary for formal SimC execution."""

SIMC_EXECUTION_SUPPORT_REVISION = "simc-execution-support-v1"
SIMC_SPECIALIZATION_UNSUPPORTED_CODE = "SIMC_SPECIALIZATION_UNSUPPORTED"
SIMC_SPECIALIZATION_UNKNOWN_CODE = "SIMC_SPECIALIZATION_UNKNOWN"

SIMC_EXECUTION_SUPPORTED_SPECIALIZATIONS = frozenset(
    {
        "deathknight:frost",
        "deathknight:unholy",
        "demonhunter:devourer",
        "demonhunter:havoc",
        "druid:balance",
        "druid:feral",
        "evoker:devastation",
        "hunter:beast_mastery",
        "hunter:marksmanship",
        "hunter:survival",
        "mage:arcane",
        "mage:fire",
        "mage:frost",
        "monk:windwalker",
        "paladin:retribution",
        "priest:shadow",
        "rogue:assassination",
        "rogue:outlaw",
        "rogue:subtlety",
        "shaman:elemental",
        "shaman:enhancement",
        "warlock:affliction",
        "warlock:demonology",
        "warlock:destruction",
        "warrior:arms",
        "warrior:fury",
    }
)

SIMC_EXECUTION_UNSUPPORTED_SPECIALIZATIONS = {
    "deathknight:blood": "tank",
    "demonhunter:vengeance": "tank",
    "druid:guardian": "tank",
    "druid:restoration": "healer",
    "evoker:augmentation": "support",
    "evoker:preservation": "healer",
    "monk:brewmaster": "tank",
    "monk:mistweaver": "healer",
    "paladin:holy": "healer",
    "paladin:protection": "tank",
    "priest:discipline": "healer",
    "priest:holy": "healer",
    "shaman:restoration": "healer",
    "warrior:protection": "tank",
}

SIMC_SPECIALIZATION_UNSUPPORTED_MESSAGE = (
    "该专精可以继续浏览、配装和保存模板，但当前正式 SimC 只支持 26 个伤害专精；"
    "坦克、治疗和增辉专精不会进入执行队列。"
)


def _normalize_key(value):
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def simc_execution_support(class_key, spec_key):
    normalized_class = _normalize_key(class_key)
    normalized_spec = _normalize_key(spec_key)
    specialization_id = f"{normalized_class}:{normalized_spec}"
    if specialization_id in SIMC_EXECUTION_SUPPORTED_SPECIALIZATIONS:
        return {
            "contractRevision": SIMC_EXECUTION_SUPPORT_REVISION,
            "classKey": normalized_class,
            "specKey": normalized_spec,
            "specializationId": specialization_id,
            "supported": True,
            "status": "supported",
            "role": "dps",
            "code": "",
            "message": "",
        }
    role = SIMC_EXECUTION_UNSUPPORTED_SPECIALIZATIONS.get(specialization_id)
    if role:
        return {
            "contractRevision": SIMC_EXECUTION_SUPPORT_REVISION,
            "classKey": normalized_class,
            "specKey": normalized_spec,
            "specializationId": specialization_id,
            "supported": False,
            "status": "blocked",
            "role": role,
            "code": SIMC_SPECIALIZATION_UNSUPPORTED_CODE,
            "message": SIMC_SPECIALIZATION_UNSUPPORTED_MESSAGE,
        }
    return {
        "contractRevision": SIMC_EXECUTION_SUPPORT_REVISION,
        "classKey": normalized_class,
        "specKey": normalized_spec,
        "specializationId": specialization_id,
        "supported": False,
        "status": "blocked",
        "role": "unknown",
        "code": SIMC_SPECIALIZATION_UNKNOWN_CODE,
        "message": "未知职业专精不能进入正式 SimC 执行队列。",
    }


def simc_execution_policy_summary():
    return {
        "contractRevision": SIMC_EXECUTION_SUPPORT_REVISION,
        "status": "ready",
        "supportedSpecCount": len(SIMC_EXECUTION_SUPPORTED_SPECIALIZATIONS),
        "unsupportedSpecCount": len(SIMC_EXECUTION_UNSUPPORTED_SPECIALIZATIONS),
        "unsupportedSpecializations": [
            {
                "specializationId": specialization_id,
                "role": role,
                "code": SIMC_SPECIALIZATION_UNSUPPORTED_CODE,
            }
            for specialization_id, role in sorted(
                SIMC_EXECUTION_UNSUPPORTED_SPECIALIZATIONS.items()
            )
        ],
    }

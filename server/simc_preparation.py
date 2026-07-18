SIMC_PREPARATION_REVISION = "simc-preparation-v1"

SELF_CLASS_RAID_BUFFS = {
    "druid": {
        "key": "mark_of_the_wild",
        "label": "Mark of the Wild",
        "profileLine": "override.mark_of_the_wild=1",
        "evidence": "production SimC override.mark_of_the_wild",
    },
    "mage": {
        "key": "arcane_intellect",
        "label": "Arcane Intellect",
        "profileLine": "override.arcane_intellect=1",
        "evidence": "production SimC override.arcane_intellect",
    },
    "priest": {
        "key": "power_word_fortitude",
        "label": "Power Word: Fortitude",
        "profileLine": "override.power_word_fortitude=1",
        "evidence": "production SimC override.power_word_fortitude",
    },
    "shaman": {
        "key": "skyfury",
        "label": "Skyfury",
        "profileLine": "override.skyfury=1",
        "evidence": "production SimC override.skyfury",
    },
    "warrior": {
        "key": "battle_shout",
        "label": "Battle Shout",
        "profileLine": "override.battle_shout=1",
        "evidence": "production SimC override.battle_shout",
    },
}

PENDING_SPEC_PREPARATION = {
    ("shaman", "enhancement"): {
        "key": "enhancement_weapon_imbues",
        "label": "Enhancement weapon imbues",
        "summary": "Windfury Weapon and Flametongue Weapon are pending current-profile SimC smoke before default injection.",
    },
    ("rogue", "assassination"): {
        "key": "rogue_poisons",
        "label": "Rogue poisons",
        "summary": "Rogue poison action syntax is pending class/spec SimC smoke before default injection.",
    },
    ("rogue", "outlaw"): {
        "key": "rogue_poisons",
        "label": "Rogue poisons",
        "summary": "Rogue poison action syntax is pending class/spec SimC smoke before default injection.",
    },
    ("rogue", "subtlety"): {
        "key": "rogue_poisons",
        "label": "Rogue poisons",
        "summary": "Rogue poison action syntax is pending class/spec SimC smoke before default injection.",
    },
}

PROFILE_CLASS_KEYS = set(SELF_CLASS_RAID_BUFFS) | {
    "deathknight",
    "demonhunter",
    "evoker",
    "hunter",
    "monk",
    "paladin",
    "rogue",
    "warlock",
}


def clean_key(value):
    return str(value or "").strip().lower().replace("-", "_")


def profile_line_key(line):
    text = str(line or "").strip()
    if not text or text.startswith("#") or "=" not in text:
        return ""
    return text.split("=", 1)[0].strip().lower()


def parse_profile_class_spec(lines):
    class_key = ""
    spec_key = ""
    for line in lines or []:
        key = profile_line_key(line)
        if key in PROFILE_CLASS_KEYS:
            class_key = key
        elif key == "spec":
            spec_key = clean_key(str(line).split("=", 1)[1].strip().strip('"'))
    return class_key, spec_key


def upsert_profile_line(lines, line):
    key = profile_line_key(line)
    if not key:
        return
    prefix = f"{key}="
    for index, existing in enumerate(lines):
        if str(existing or "").strip().lower().startswith(prefix):
            lines[index] = line
            return
    lines.append(line)


def simc_preparation_payload(class_key="", spec_key="", temporary_buffs=None):
    class_key = clean_key(class_key)
    spec_key = clean_key(spec_key)
    profile_lines = ["optimal_raid=0"]
    items = [
        {
            "key": "optimal_raid",
            "category": "raid_buff_baseline",
            "label": "Full raid buff package",
            "state": "disabled",
            "summary": "SimulationCraft optimal_raid is disabled; only backend-verified self-class buffs may be added.",
            "evidenceState": "verified",
        }
    ]
    warnings = []
    blockers = []

    class_buff = SELF_CLASS_RAID_BUFFS.get(class_key)
    enabled_labels = []
    if class_buff:
        profile_lines.append(class_buff["profileLine"])
        enabled_labels.append(class_buff["label"])
        items.append({
            "key": class_buff["key"],
            "category": "self_class_raid_buff",
            "label": class_buff["label"],
            "state": "enabled",
            "summary": f"Only the player's own class raid buff is enabled: {class_buff['label']}.",
            "evidenceState": "verified",
            "evidence": class_buff["evidence"],
        })
    else:
        items.append({
            "key": "self_class_raid_buff",
            "category": "self_class_raid_buff",
            "label": "Self-class raid buff",
            "state": "not_applicable",
            "summary": "No verified default self-class raid buff mapping is enabled for this class.",
            "evidenceState": "verified",
        })

    pending_spec = PENDING_SPEC_PREPARATION.get((class_key, spec_key))
    evidence_state = "verified"
    if pending_spec:
        evidence_state = "partial"
        warnings.append(pending_spec["summary"])
        items.append({
            "key": pending_spec["key"],
            "category": "spec_combat_preparation",
            "label": pending_spec["label"],
            "state": "pending_evidence",
            "summary": pending_spec["summary"],
            "evidenceState": "partial",
        })

    temporary_source = temporary_buffs if isinstance(temporary_buffs, dict) else {}
    temporary_enabled = [
        label
        for key, label in (
            ("bloodlust", "Bloodlust/Heroism"),
            ("combatPotion", "Combat potion"),
            ("weaponOil", "Weapon oil or sharpening stone"),
        )
        if temporary_source.get(key)
    ]
    if temporary_enabled:
        warnings.append("Temporary combat buffs are structured but not yet serialized into SimC profile lines.")
        evidence_state = "partial"
    items.append({
        "key": "temporary_combat_buffs",
        "category": "temporary_combat_buffs",
        "label": "Temporary combat buffs",
        "state": "enabled" if temporary_enabled else "disabled",
        "summary": ", ".join(temporary_enabled) if temporary_enabled else "Bloodlust/Heroism, combat potion, and temporary weapon buffs are off by default.",
        "evidenceState": "partial" if temporary_enabled else "verified",
    })

    summary_buff = ", ".join(enabled_labels) if enabled_labels else "no class raid buff"
    temporary_summary = (
        f"selected temporary combat buffs: {', '.join(temporary_enabled)}"
        if temporary_enabled
        else "temporary combat buffs are off by default"
    )
    summary = (
        f"SimC buffs: optimal_raid=0; self-class raid buff enabled: {summary_buff}; "
        f"{temporary_summary}."
    )
    if pending_spec:
        summary = f"{summary} Spec combat preparation is pending evidence for this specialization."

    return {
        "schemaRevision": SIMC_PREPARATION_REVISION,
        "classKey": class_key,
        "specKey": spec_key,
        "evidenceState": "blocked" if blockers else evidence_state,
        "summary": summary,
        "items": items,
        "warnings": warnings,
        "blockers": blockers,
        "profileLines": profile_lines,
    }


def simc_preparation_report(preparation):
    source = preparation if isinstance(preparation, dict) else {}
    return {
        "schemaRevision": source.get("schemaRevision") or SIMC_PREPARATION_REVISION,
        "classKey": source.get("classKey", ""),
        "specKey": source.get("specKey", ""),
        "evidenceState": source.get("evidenceState", "verified"),
        "summary": source.get("summary", ""),
        "items": [
            {
                key: item.get(key)
                for key in ("key", "category", "label", "state", "summary", "evidenceState")
                if item.get(key) not in (None, "")
            }
            for item in (source.get("items") or [])
            if isinstance(item, dict)
        ],
        "warnings": [str(item) for item in (source.get("warnings") or []) if str(item or "").strip()],
        "blockers": [str(item) for item in (source.get("blockers") or []) if str(item or "").strip()],
    }


def simc_preparation_options_payload():
    rows = [
        {
            "key": "optimal_raid",
            "category": "raid_buff_baseline",
            "label": "Full raid buff package",
            "defaultState": "disabled",
            "evidenceState": "verified",
            "overrideSupported": True,
        }
    ]
    for class_key, buff in sorted(SELF_CLASS_RAID_BUFFS.items()):
        rows.append(
            {
                "key": buff["key"],
                "category": "self_class_raid_buff",
                "classKey": class_key,
                "label": buff["label"],
                "defaultState": "enabled",
                "evidenceState": "verified",
                "overrideSupported": True,
            }
        )
    for (class_key, spec_key), pending in sorted(PENDING_SPEC_PREPARATION.items()):
        rows.append(
            {
                "key": pending["key"],
                "category": "spec_combat_preparation",
                "classKey": class_key,
                "specKey": spec_key,
                "label": pending["label"],
                "defaultState": "pending_evidence",
                "evidenceState": "partial",
                "overrideSupported": False,
            }
        )
    rows.append(
        {
            "key": "temporary_combat_buffs",
            "category": "temporary_combat_buffs",
            "label": "Temporary combat buffs",
            "defaultState": "disabled",
            "evidenceState": "verified",
            "overrideSupported": False,
        }
    )
    return {
        "schemaRevision": SIMC_PREPARATION_REVISION,
        "status": "ready",
        "rows": rows,
    }


def apply_simc_preparation_lines(lines, class_key="", spec_key="", temporary_buffs=None):
    if not isinstance(lines, list):
        return simc_preparation_payload(class_key, spec_key, temporary_buffs)
    detected_class, detected_spec = parse_profile_class_spec(lines)
    preparation = simc_preparation_payload(
        class_key or detected_class,
        spec_key or detected_spec,
        temporary_buffs=temporary_buffs,
    )
    for line in preparation.get("profileLines") or []:
        upsert_profile_line(lines, line)
    return preparation

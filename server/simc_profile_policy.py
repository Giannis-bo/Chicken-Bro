import re


DK_RUNEFORGE_DEFAULTS_BY_SPEC = {
    "frost": {"main_hand": "3368"},
    "unholy": {"main_hand": "6245"},
}
DK_RUNEFORGE_ENCHANT_IDS = frozenset(
    enchant_id
    for slots in DK_RUNEFORGE_DEFAULTS_BY_SPEC.values()
    for enchant_id in slots.values()
)
DK_RUNEFORGE_BLOCKER = "DK runeforge conflict: ordinary weapon enchant would override DK runeforge."


def _policy_key(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def is_death_knight(class_key):
    return _policy_key(class_key) in {"deathknight", "dk"}


def normalized_policy_slot(value):
    slot = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
    aliases = {
        "mainhand": "main_hand",
        "main_hand": "main_hand",
        "offhand": "off_hand",
        "off_hand": "off_hand",
    }
    return aliases.get(slot, slot)


def dk_default_runeforge_enchant_id(class_key, spec_key, slot):
    if not is_death_knight(class_key):
        return ""
    spec_defaults = DK_RUNEFORGE_DEFAULTS_BY_SPEC.get(_policy_key(spec_key)) or {}
    return spec_defaults.get(normalized_policy_slot(slot), "")


def is_dk_runeforge_enchant_id(enchant_id):
    return str(enchant_id or "").strip() in DK_RUNEFORGE_ENCHANT_IDS


def dk_ordinary_weapon_enchant_blocker(class_key, slot, enchant_id):
    if not is_death_knight(class_key):
        return ""
    if normalized_policy_slot(slot) not in {"main_hand", "off_hand"}:
        return ""
    enchant_id = str(enchant_id or "").strip()
    if enchant_id and not is_dk_runeforge_enchant_id(enchant_id):
        return DK_RUNEFORGE_BLOCKER
    return ""

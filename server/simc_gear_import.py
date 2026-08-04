"""Pure SimulationCraft gear parsing for legacy compatibility and Exact v2 import."""

from __future__ import annotations

from typing import Any

try:
    from .gear_contracts import EXACT_LOADOUT_CORE_SLOTS, parse_exact_loadout_intent
    from .simulator_payload import clean_simc_gear_items, normalize_simc_slot
except ImportError:
    from gear_contracts import EXACT_LOADOUT_CORE_SLOTS, parse_exact_loadout_intent
    from simulator_payload import clean_simc_gear_items, normalize_simc_slot


MAX_RAW_PROFILE_BYTES = 65_536
_KNOWN_PROFILE_OPTIONS = {"id", "ilevel", "bonus_id", "context", "gem_id", "gem_bonus_id", "gem_ilevel", "enchant_id", "crafted_stats", "embellishment", "redirected_base_stats"}
_IGNORED_ASSIGNMENTS = {"spec", "race", "level", "talents", "fight_style", "desired_targets", "iterations", "max_time", "vary_combat_length", "calculate_scale_factors", "role", "position"}


def parse_simcraft_template_gear_line(line: object):
    text = str(line or "").strip()
    if not text or text.startswith("#"):
        return None, ""
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if not parts or "=" not in parts[0]:
        return None, f"invalid gear line: {text[:80]}"
    slot_key, _, name = parts[0].partition("=")
    slot = normalize_simc_slot(slot_key)
    if not slot:
        return None, f"invalid gear slot: {slot_key}"
    item = {"slot": slot, "name": name.strip()}
    for part in parts[1:]:
        key, separator, value = part.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not key or not value:
            continue
        item[key] = value
    normalized = clean_simc_gear_items([item], limit=1)
    if not normalized:
        return None, f"missing item id for gear slot: {slot}"
    return normalized[0], ""


def parse_simcraft_template_gear_raw(raw_string: object, required_slots: list[str]):
    errors: list[str] = []
    items: list[dict[str, Any]] = []
    seen_slots: set[str] = set()
    for line in str(raw_string or "").splitlines():
        item, error = parse_simcraft_template_gear_line(line)
        if error:
            errors.append(error)
            continue
        if not item:
            continue
        if item["slot"] in seen_slots:
            errors.append(f"duplicate gear slot: {item['slot']}")
            continue
        seen_slots.add(item["slot"])
        items.append(item)
    missing_slots = [slot for slot in required_slots if slot not in seen_slots]
    if missing_slots:
        errors.append(f"missing gear slots: {', '.join(missing_slots)}")
    return items if not errors else [], errors


def _problem(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _blocked(problems: list[dict[str, str]]) -> dict[str, object]:
    return {"schemaRevision": "exact-import-parse-v1", "status": "blocked", "problems": problems}


def _text(value: object, path: str, problems: list[dict[str, str]], *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or "\n" in value or "\r" in value or len(value.encode("utf-8")) > 256:
        problems.append(_problem("INVALID_INPUT", path, "Value must be a bounded newline-free string."))
        return ""
    value = value.strip()
    if not value and not allow_empty:
        problems.append(_problem("INVALID_INPUT", path, "Value is required."))
    return value


def _tokens(value: str, path: str, problems: list[dict[str, str]], *, integers: bool = False) -> list[Any]:
    if value == "":
        return []
    values = value.split("/")
    result: list[Any] = []
    for index, token in enumerate(values):
        token = token.strip()
        if not token or "\n" in token or "\r" in token or len(token) > 256:
            problems.append(_problem("INVALID_GEAR_OPTION", f"{path}.{index}", "Option token is invalid."))
            continue
        if integers:
            if not token.isdecimal() or not 1 <= int(token) <= 9999:
                problems.append(_problem("INVALID_GEAR_OPTION", f"{path}.{index}", "Item level must be a finite positive integer."))
                continue
            result.append(int(token))
        else:
            result.append(token)
    return result


def parse_simc_exact_import(raw_profile: object, *, class_key: str, spec_key: str, level: int, season_revision: str, game_build: str) -> dict[str, object]:
    """Return a sanitized Exact v2 intent or structured blocked diagnostics."""

    problems: list[dict[str, str]] = []
    if not isinstance(raw_profile, str):
        return _blocked([_problem("INVALID_INPUT", "rawProfile", "Profile must be text.")])
    if len(raw_profile.encode("utf-8")) > MAX_RAW_PROFILE_BYTES:
        return _blocked([_problem("PROFILE_TOO_LARGE", "rawProfile", "Profile exceeds 65,536 UTF-8 bytes.")])
    class_key = _text(class_key, "intent.eligibilityContext.classKey", problems)
    spec_key = _text(spec_key, "intent.eligibilityContext.specKey", problems)
    season_revision = _text(season_revision, "intent.authoredAgainst.seasonRevision", problems)
    game_build = _text(game_build, "intent.authoredAgainst.gameBuild", problems)
    if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 999:
        problems.append(_problem("INVALID_INPUT", "intent.eligibilityContext.level", "Level must be a finite positive integer."))

    character_sections: list[dict[str, str]] = []
    declared_spec = ""
    slot_rows: dict[str, dict[str, Any]] = {}
    for index, line in enumerate(raw_profile.splitlines()):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        first, *options = [part.strip() for part in text.split(",")]
        key, separator, value = first.partition("=")
        key, value = key.strip(), value.strip()
        if not separator:
            problems.append(_problem("INVALID_LINE", f"profile.lines.{index}", "Profile line must be key=value."))
            continue
        slot = normalize_simc_slot(key)
        if slot:
            if slot in slot_rows:
                problems.append(_problem("DUPLICATE_SLOT", f"intent.slots.{slot}", "A gear slot may appear only once."))
                continue
            parsed_options: dict[str, str] = {}
            for option in options:
                option_key, option_separator, option_value = option.partition("=")
                option_key, option_value = option_key.strip(), option_value.strip()
                if not option_separator or option_key not in _KNOWN_PROFILE_OPTIONS:
                    problems.append(_problem("UNKNOWN_GEAR_OPTION", f"profile.lines.{index}.options.{option_key or 'unknown'}", "Gear option is not supported by Exact import."))
                    continue
                parsed_options[option_key] = option_value
            slot_rows[slot] = {"name": value, "options": parsed_options, "line": index}
            continue
        if key in _IGNORED_ASSIGNMENTS:
            if key == "spec":
                declared_spec = value
            continue
        if options and any(option.partition("=")[0].strip() == "id" for option in options):
            problems.append(_problem("UNKNOWN_SLOT", f"profile.lines.{index}.slot", "Gear slot is not recognized."))
            continue
        if not options and value and key.replace("_", "").isalnum() and key not in _IGNORED_ASSIGNMENTS:
            character_sections.append({"classKey": key, "specKey": "", "index": str(index)})
            continue
        problems.append(_problem("UNKNOWN_PROFILE_LINE", f"profile.lines.{index}", "Profile line is not recognized."))

    if len(character_sections) > 1:
        problems.append(_problem("MULTIPLE_CHARACTERS", "profile.characters.1.classKey", "Only one character section is accepted."))
    for section_index, section in enumerate(character_sections[:1]):
        if section["classKey"] and section["classKey"] != class_key:
            problems.append(_problem("CLASS_KEY_CONFLICT", f"profile.characters.{section_index}.classKey", "Profile class conflicts with caller identity."))
    if declared_spec and declared_spec != spec_key:
        problems.append(_problem("SPEC_KEY_CONFLICT", "profile.characters.0.specKey", "Profile spec conflicts with caller identity."))

    slots: dict[str, dict[str, Any]] = {}
    for slot in EXACT_LOADOUT_CORE_SLOTS:
        row = slot_rows.get(slot)
        if row is None:
            problems.append(_problem("MISSING_SLOT", f"intent.slots.{slot}", "Core Exact loadout slot is required."))
            continue
        options = row["options"]
        item_ids = _tokens(options.get("id", ""), f"intent.slots.{slot}.itemId", problems)
        if len(item_ids) != 1:
            if not item_ids:
                problems.append(_problem("MISSING_ITEM_ID", f"intent.slots.{slot}.itemId", "Exact item id is required."))
            continue
        gem_ids = _tokens(options.get("gem_id", ""), f"intent.slots.{slot}.gemIds", problems)
        gem_bonus = _tokens(options.get("gem_bonus_id", ""), f"intent.slots.{slot}.gemBonusIds", problems)
        gem_levels = _tokens(options.get("gem_ilevel", ""), f"intent.slots.{slot}.gemItemLevels", problems, integers=True)
        if options.get("gem_bonus_id", "") and len(gem_bonus) != len(gem_ids):
            problems.append(_problem("MISALIGNED_GEM_OPTIONS", f"intent.slots.{slot}.gemBonusIds", "gemBonusIds must align with gemIds."))
        if options.get("gem_ilevel", "") and len(gem_levels) != len(gem_ids):
            problems.append(_problem("MISALIGNED_GEM_OPTIONS", f"intent.slots.{slot}.gemItemLevels", "gemItemLevels must align with gemIds."))
        ilevel_values = _tokens(options.get("ilevel", ""), f"intent.slots.{slot}.declaredItemLevel", problems, integers=True)
        if len(ilevel_values) > 1:
            problems.append(_problem("INVALID_GEAR_OPTION", f"intent.slots.{slot}.declaredItemLevel", "Only one declared item level is allowed."))
        slots[slot] = {
            "itemId": item_ids[0], "declaredItemLevel": ilevel_values[0] if ilevel_values else None,
            "bonusIds": _tokens(options.get("bonus_id", ""), f"intent.slots.{slot}.bonusIds", problems),
            "context": options.get("context", ""), "gemIds": gem_ids, "gemBonusIds": gem_bonus,
            "gemItemLevels": gem_levels, "enchantId": options.get("enchant_id", ""),
            "craftedStats": _tokens(options.get("crafted_stats", ""), f"intent.slots.{slot}.craftedStats", problems),
            "embellishmentIds": _tokens(options.get("embellishment", ""), f"intent.slots.{slot}.embellishmentIds", problems),
            "redirectedBaseStats": _tokens(options.get("redirected_base_stats", ""), f"intent.slots.{slot}.redirectedBaseStats", problems),
        }
    if "off_hand" in slot_rows:
        # Full parsing is shared with the core-slot path by treating it as a
        # temporary required slot, then leaving final weapon legality to Resolver.
        raw_with_offhand = dict(slot_rows)
        original = EXACT_LOADOUT_CORE_SLOTS
        # The one-slot duplication below is intentionally avoided: Exact import
        # accepts off-hand only when it satisfies the same strict field shape.
        row = raw_with_offhand["off_hand"]
        options = row["options"]
        ids = _tokens(options.get("id", ""), "intent.slots.off_hand.itemId", problems)
        if len(ids) == 1:
            gem_ids = _tokens(options.get("gem_id", ""), "intent.slots.off_hand.gemIds", problems)
            gem_bonus = _tokens(options.get("gem_bonus_id", ""), "intent.slots.off_hand.gemBonusIds", problems)
            gem_levels = _tokens(options.get("gem_ilevel", ""), "intent.slots.off_hand.gemItemLevels", problems, integers=True)
            if options.get("gem_bonus_id", "") and len(gem_bonus) != len(gem_ids):
                problems.append(_problem("MISALIGNED_GEM_OPTIONS", "intent.slots.off_hand.gemBonusIds", "gemBonusIds must align with gemIds."))
            if options.get("gem_ilevel", "") and len(gem_levels) != len(gem_ids):
                problems.append(_problem("MISALIGNED_GEM_OPTIONS", "intent.slots.off_hand.gemItemLevels", "gemItemLevels must align with gemIds."))
            ilevel = _tokens(options.get("ilevel", ""), "intent.slots.off_hand.declaredItemLevel", problems, integers=True)
            slots["off_hand"] = {"itemId": ids[0], "declaredItemLevel": ilevel[0] if ilevel else None, "bonusIds": _tokens(options.get("bonus_id", ""), "intent.slots.off_hand.bonusIds", problems), "context": options.get("context", ""), "gemIds": gem_ids, "gemBonusIds": gem_bonus, "gemItemLevels": gem_levels, "enchantId": options.get("enchant_id", ""), "craftedStats": _tokens(options.get("crafted_stats", ""), "intent.slots.off_hand.craftedStats", problems), "embellishmentIds": _tokens(options.get("embellishment", ""), "intent.slots.off_hand.embellishmentIds", problems), "redirectedBaseStats": _tokens(options.get("redirected_base_stats", ""), "intent.slots.off_hand.redirectedBaseStats", problems)}
        else:
            problems.append(_problem("MISSING_ITEM_ID", "intent.slots.off_hand.itemId", "Exact item id is required."))
    if problems:
        return _blocked(problems)
    intent, intent_problems = parse_exact_loadout_intent({"schemaRevision": "exact-loadout-intent-v2", "authoredAgainst": {"seasonRevision": season_revision, "gameBuild": game_build}, "eligibilityContext": {"classKey": class_key, "specKey": spec_key, "level": level}, "slots": slots})
    if intent_problems:
        return _blocked(intent_problems)
    return {"schemaRevision": "exact-import-parse-v1", "status": "parsed", "intent": intent, "problems": []}

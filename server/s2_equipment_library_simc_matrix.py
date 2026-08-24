"""Fixed-runtime SimC matrix for the four-source Midnight Season 2 candidate.

This module owns only the execution/evidence layer.  It does not decide which
items, tracks, or crafted options are official.  Those decisions remain in
``s2_equipment_library_closure`` and are carried into this matrix as explicit
candidate records.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shlex
import subprocess
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from .simc_support_policy import SIMC_EXECUTION_SUPPORTED_SPECIALIZATIONS


S2_EQUIPMENT_LIBRARY_SIMC_MATRIX_SCHEMA_REVISION = (
    "s2-equipment-library-simc-matrix-v1"
)
S2_EQUIPMENT_LIBRARY_SIMC_MATRIX_REPORT_PREFIX = (
    "s2-equipment-library-simc-matrix:sha256:"
)

_RUNTIME_PATTERN = re.compile(
    r"^simc:(?P<build>[^:]+):(?P<commit>[0-9a-f]{40}):(?P<binary>[0-9a-f]{64})$"
)
_ID_PATTERN = re.compile(r"(?:^|,)id=(?P<id>[1-9][0-9]*)(?:,|$)")
_BONUS_PATTERN = re.compile(r"(?:^|,)bonus_id=(?P<bonus>[^,]+)(?:,|$)")
_ITEM_LEVEL_PATTERN = re.compile(r"(?:^|,)ilevel=(?P<ilevel>[0-9]+)(?:,|$)")
_SIMC_ENHANCEMENT_FIELDS = (
    "gem_id",
    "enchant_id",
    "crafted_stats",
    "embellishment",
)
_DEFAULT_RACE_BY_CLASS = {
    "deathknight": "human",
    "demonhunter": "night_elf",
    "druid": "night_elf",
    "evoker": "dracthyr",
    "hunter": "human",
    "mage": "human",
    "monk": "human",
    "paladin": "human",
    "priest": "human",
    "rogue": "human",
    "shaman": "orc",
    "warlock": "human",
    "warrior": "human",
}
_PROFILE_SLOTS = (
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
)
_SIMC_SLOT_ALIASES = {
    "shoulder": "shoulders",
    "wrist": "wrists",
}
_CLASS_ARMOR_SUBCLASS_BY_CLASS = {
    "deathknight": 4,
    "demonhunter": 2,
    "druid": 2,
    "evoker": 3,
    "hunter": 3,
    "mage": 1,
    "monk": 2,
    "paladin": 4,
    "priest": 1,
    "rogue": 2,
    "shaman": 3,
    "warlock": 1,
    "warrior": 4,
}
_REPRESENTATIVE_SET_ID_BY_CLASS = {
    "deathknight": "2055",
    "demonhunter": "2056",
    "druid": "2057",
    "evoker": "2058",
    "hunter": "2059",
    "mage": "2060",
    "monk": "2061",
    "paladin": "2062",
    "priest": "2063",
    "rogue": "2064",
    "shaman": "2065",
    "warlock": "2066",
    "warrior": "2067",
}
# These are only deterministic runtime anchors.  Their item identity and
# legality still come from the candidate's public records and DB2 Item facts.
_REPRESENTATIVE_WEAPON_ITEM_ID_BY_SPEC = {
    # These are exact S2 candidate identities, not generic or historical
    # anchors.  The public candidate contains the S2 raid weapon family below;
    # using it keeps representative profiles inside the four-source release.
    "deathknight:frost": "268198",
    "deathknight:unholy": "268198",
    "demonhunter:havoc": "268201",
    "demonhunter:devourer": "268201",
    "druid:balance": "268205",
    "druid:feral": "268205",
    "evoker:devastation": "268206",
    "hunter:beast_mastery": "268207",
    "hunter:marksmanship": "268207",
    "hunter:survival": "268207",
    "mage:arcane": "268204",
    "mage:fire": "268204",
    "mage:frost": "268204",
    "monk:windwalker": "268205",
    "paladin:retribution": "268198",
    "priest:shadow": "268204",
    "rogue:assassination": "268204",
    "rogue:outlaw": "268204",
    "rogue:subtlety": "268204",
    "shaman:elemental": "268206",
    "shaman:enhancement": "268206",
    "warlock:affliction": "268204",
    "warlock:demonology": "268204",
    "warlock:destruction": "268204",
    "warrior:arms": "268198",
    "warrior:fury": "268198",
}
_REPRESENTATIVE_DUAL_WIELD_SPECS = {
    "demonhunter:havoc",
    "demonhunter:devourer",
    "monk:windwalker",
    "rogue:assassination",
    "rogue:outlaw",
    "rogue:subtlety",
    "shaman:enhancement",
    "warrior:fury",
}
_SET_EFFECT_COUNTS = (2, 4)
_DEFAULT_SET_PROBE_SPEC_BY_SET_ID = {
    # Runtime-only probe routing.  The official item-set payload remains the
    # owner of set identity/effect facts; these class/specs only select a
    # fixed SimC actor that can initialize the corresponding class set.
    "2055": ("deathknight", "unholy"),
    "2056": ("demonhunter", "devourer"),
    "2057": ("druid", "restoration"),
    "2058": ("evoker", "devastation"),
    "2059": ("hunter", "marksmanship"),
    "2060": ("mage", "frost"),
    "2061": ("monk", "windwalker"),
    "2062": ("paladin", "retribution"),
    "2063": ("priest", "shadow"),
    "2064": ("rogue", "subtlety"),
    "2065": ("shaman", "restoration"),
    "2066": ("warlock", "demonology"),
    "2067": ("warrior", "protection"),
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed == parsed else None


def _simc_slot(slot: str) -> str:
    return _SIMC_SLOT_ALIASES.get(_text(slot), _text(slot))


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )


def parse_simc_runtime_identity(identity: str) -> dict[str, str] | None:
    match = _RUNTIME_PATTERN.fullmatch(_text(identity))
    if not match:
        return None
    return {
        "identity": _text(identity),
        "build": match.group("build"),
        "commit": match.group("commit"),
        "binarySha256": match.group("binary"),
    }


def _canonical_input(record: Mapping[str, Any]) -> Mapping[str, Any]:
    value = record.get("canonicalSimcInput")
    return value if isinstance(value, Mapping) else {}


def _record_is_public(record: Mapping[str, Any]) -> bool:
    canonical = _canonical_input(record)
    return (
        _text(record.get("status")) == "verified"
        and _text(canonical.get("status")) == "verified"
        and bool(_text(record.get("variantKey")))
        and bool(_text(record.get("itemId")))
        and bool(_text(record.get("itemSlot")))
        and bool(_text(canonical.get("line")))
    )


def _record_is_excluded(record: Mapping[str, Any]) -> bool:
    """Identify an explicit scope exclusion, not an unresolved public fact."""

    canonical = _canonical_input(record)
    return any(
        _text(value) == "excluded"
        for value in (
            record.get("status"),
            record.get("variantStatus"),
            record.get("sourceEligibilityStatus"),
            record.get("trackStatus"),
            canonical.get("status"),
        )
    )


def _line_for_slot(line: str, slot: str) -> str:
    _left, separator, right = _text(line).partition("=")
    if not separator or not _text(right):
        return ""
    return f"{_simc_slot(slot)}={right}"


def _record_expected(record: Mapping[str, Any]) -> dict[str, Any]:
    canonical = _canonical_input(record)
    item_level = _integer(canonical.get("itemLevel"))
    return {
        "itemId": _text(record.get("itemId")) or _text(canonical.get("itemId")),
        "slot": _text(record.get("itemSlot")) or _text(canonical.get("slot")),
        "bonusIds": sorted(
            {
                _text(value)
                for value in canonical.get("bonusIds") or []
                if _text(value)
            },
            key=lambda value: int(value) if value.isdigit() else value,
        ),
        "itemLevel": item_level,
        "contextValues": sorted(
            {
                _text(value)
                for value in canonical.get("itemContextValues") or []
                if _text(value)
            },
            key=lambda value: int(value) if value.isdigit() else value,
        ),
    }


def _safe_player_name(job_key: str) -> str:
    digest = hashlib.sha256(_text(job_key).encode("utf-8")).hexdigest()[:20]
    return f"s2mx_{digest}"


def _profile_header(
    *,
    player_name: str,
    class_key: str,
    spec_key: str,
    disable_set_bonuses: bool = False,
) -> list[str]:
    lines = [
        f'{class_key}="{player_name}"',
        "level=90",
        f"race={_DEFAULT_RACE_BY_CLASS.get(class_key, 'human')}",
        f"spec={spec_key}",
    ]
    if disable_set_bonuses:
        lines.append("disable_set_bonuses=1")
    return lines


def _profile_text(
    *,
    player_name: str,
    class_key: str,
    spec_key: str,
    gear_lines: Mapping[str, str],
    iterations: int = 1,
    max_time: float = 1,
    disable_set_bonuses: bool = False,
    debug: bool = False,
) -> str:
    lines = _profile_header(
        player_name=player_name,
        class_key=class_key,
        spec_key=spec_key,
        disable_set_bonuses=disable_set_bonuses,
    )
    lines.extend(_text(gear_lines.get(slot)) for slot in _PROFILE_SLOTS)
    lines.extend(
        [
            f"iterations={int(iterations)}",
            f"max_time={float(max_time):g}",
            "vary_combat_length=0",
            "calculate_scale_factors=0",
            "default_actions=1",
        ]
    )
    if debug:
        lines.append("debug=1")
    return "\n".join(line for line in lines if line) + "\n"


def _simc_safe_item_name(value: Any, item_id: str) -> str:
    fallback = f"item_{_text(item_id)}" if _text(item_id) else "item"
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", _text(value).lower()).strip("_")
    normalized = re.sub(r"_+", "_", normalized)
    return normalized or fallback


def _candidate_item_names(candidate: Mapping[str, Any]) -> dict[str, str]:
    names: dict[str, str] = {}
    for row in candidate.get("itemDefinitions") or []:
        if not isinstance(row, Mapping):
            continue
        item_id = _text(row.get("itemId"))
        identity = row.get("itemIdentity") if isinstance(row.get("itemIdentity"), Mapping) else {}
        name = _text(identity.get("name")) or _text(row.get("itemName"))
        if item_id and name:
            names[item_id] = name
    return names


def _candidate_item_logical_sources(
    candidate: Mapping[str, Any],
) -> dict[str, set[str]]:
    sources_by_item: dict[str, set[str]] = defaultdict(set)
    for row in candidate.get("itemDefinitions") or []:
        if not isinstance(row, Mapping):
            continue
        item_id = _text(row.get("itemId"))
        if not item_id:
            continue
        sources_by_item[item_id].update(
            _text(source)
            for source in row.get("logicalSources") or []
            if _text(source)
        )
    return sources_by_item


def _record_is_crafted_only(
    record: Mapping[str, Any],
    sources_by_item: Mapping[str, set[str]],
) -> bool:
    sources = set(sources_by_item.get(_text(record.get("itemId")), set()))
    sources.update(
        _text(source)
        for source in record.get("logicalSources") or []
        if _text(source)
    )
    return "crafted" in sources and not sources.intersection({"raid", "mythic_plus"})


def _runtime_safe_item_line(line: str, names: Mapping[str, str]) -> str:
    match = re.match(r"^(?P<prefix>[^=]+=)(?P<name>[^,]+),(?P<rest>.*)$", _text(line))
    if not match:
        return _text(line)
    item_match = re.search(r"(?:^|,)id=(?P<id>[1-9][0-9]*)(?:,|$)", match.group("rest"))
    if not item_match or match.group("name") not in {"s2_item", "s2_crafted", "item"}:
        return _text(line)
    item_id = item_match.group("id")
    safe_name = _simc_safe_item_name(names.get(item_id), item_id)
    return f"{match.group('prefix')}{safe_name},{match.group('rest')}"


def _runtime_safe_gear(
    gear: Mapping[str, str],
    names: Mapping[str, str],
) -> dict[str, str]:
    return {
        slot: _runtime_safe_item_line(line, names)
        for slot, line in gear.items()
        if _text(line)
    }


def _runtime_legalize_weapon_pair(
    gear: Mapping[str, str],
    *,
    target_slot: str = "",
) -> dict[str, str]:
    normalized = dict(gear)
    if _text(target_slot) == "off_hand":
        # The public candidate's deterministic anchor is a two-handed weapon.
        # Use a runtime-only one-handed anchor when the exact target is an
        # off-hand item; this anchor is not catalogued or treated as S2 fact.
        normalized["main_hand"] = "main_hand=worn_shortsword,id=25"
    elif _text(target_slot) == "main_hand":
        normalized.pop("off_hand", None)
    elif "main_hand" in normalized:
        # Keep the common anchor legal for armor/jewellery probes.
        normalized.pop("off_hand", None)
    return normalized


def _public_records(candidate: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    result: list[Mapping[str, Any]] = []
    for key in ("variants", "craftedVariantTemplates"):
        raw = candidate.get(key)
        if not isinstance(raw, list):
            continue
        result.extend(row for row in raw if isinstance(row, Mapping))
    return sorted(
        result,
        key=lambda row: (
            _text(row.get("itemId")),
            _text(row.get("variantKey")),
        ),
    )


def _build_base_gear_lines(candidate: Mapping[str, Any]) -> tuple[dict[str, str], list[dict[str, str]]]:
    by_slot: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in _public_records(candidate):
        if not _record_is_public(record):
            continue
        slot = _text(record.get("itemSlot"))
        canonical = _canonical_input(record)
        line = _line_for_slot(_text(canonical.get("line")), slot)
        if slot and line:
            by_slot[slot].append(record)

    base: dict[str, str] = {}
    missing: list[dict[str, str]] = []
    for slot in _PROFILE_SLOTS:
        source_slot = slot
        if slot == "finger2":
            source_slot = "finger1"
        elif slot == "trinket2":
            source_slot = "trinket1"
        rows = by_slot.get(source_slot) or []
        if not rows:
            missing.append({"slot": slot, "code": "S2_SIMC_BASE_PROFILE_SLOT_MISSING"})
            continue
        source = rows[0]
        line = _line_for_slot(
            _text(_canonical_input(source).get("line")),
            slot,
        )
        if not line:
            missing.append({"slot": slot, "code": "S2_SIMC_BASE_PROFILE_LINE_MISSING"})
            continue
        base[slot] = line
    return base, missing


def _candidate_item_facts(candidate: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    facts_by_item: dict[str, Mapping[str, Any]] = {}
    for row in candidate.get("itemDefinitions") or []:
        if not isinstance(row, Mapping):
            continue
        item_id = _text(row.get("itemId"))
        facts = row.get("db2ItemFacts")
        if item_id and isinstance(facts, Mapping):
            facts_by_item[item_id] = facts
    return facts_by_item


def _public_records_by_item(
    candidate: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    by_item: dict[str, Mapping[str, Any]] = {}
    for record in _public_records(candidate):
        if _record_is_public(record):
            by_item.setdefault(_text(record.get("itemId")), record)
    return by_item


def _public_records_by_slot(
    candidate: Mapping[str, Any],
) -> dict[str, list[Mapping[str, Any]]]:
    by_slot: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in _public_records(candidate):
        if _record_is_public(record):
            slot = _text(record.get("itemSlot"))
            if slot:
                by_slot[slot].append(record)
    return by_slot


def _record_line(record: Mapping[str, Any], slot: str | None = None) -> str:
    record_slot = _text(slot) or _text(record.get("itemSlot"))
    return _line_for_slot(
        _text(_canonical_input(record).get("line")),
        record_slot,
    )


def _select_record_by_item_id(
    by_item: Mapping[str, Mapping[str, Any]],
    item_id: str,
    *,
    slot: str,
) -> Mapping[str, Any] | None:
    record = by_item.get(_text(item_id))
    if not record:
        return None
    return record if _record_line(record, slot) else None


def _select_class_armor_record(
    by_slot: Mapping[str, Sequence[Mapping[str, Any]]],
    facts_by_item: Mapping[str, Mapping[str, Any]],
    *,
    class_key: str,
    slot: str,
) -> Mapping[str, Any] | None:
    expected_subclass = _CLASS_ARMOR_SUBCLASS_BY_CLASS.get(_text(class_key))
    if expected_subclass is None:
        return None
    for record in by_slot.get(slot) or []:
        facts = facts_by_item.get(_text(record.get("itemId")))
        if not facts:
            continue
        if (
            _integer(facts.get("ClassID")) == 4
            and _integer(facts.get("SubclassID")) == expected_subclass
            and _record_line(record, slot)
        ):
            return record
    return None


def _select_representative_profile(
    candidate: Mapping[str, Any],
    *,
    class_key: str,
    spec_key: str,
    base: Mapping[str, str],
) -> tuple[dict[str, str], dict[str, Any]]:
    """Build a class-legal probe profile from exact candidate records.

    The common base profile is sufficient for public item readback, but it is
    intentionally not reused for class-wide DPS probes: it contains a
    plate-only outer armour sample and a shield.  This adapter selects the
    class's own five-piece S2 set, universal jewellery/back slots, class
    armour for wrist/waist/feet, and a deterministic class/spec weapon.
    """

    by_item = _public_records_by_item(candidate)
    by_slot = _public_records_by_slot(candidate)
    facts_by_item = _candidate_item_facts(candidate)
    synthetic_fallback = not bool(candidate.get("itemDefinitions"))
    gear: dict[str, str] = {}
    selected_item_ids: dict[str, str] = {}
    missing: list[dict[str, str]] = []

    # Set pieces are the class-specific identity anchor.  Keep the source
    # record intact; only the SimC slot spelling is adapted for serialization.
    target_set_id = _REPRESENTATIVE_SET_ID_BY_CLASS.get(_text(class_key), "")
    target_set_item_ids: list[str] = []
    for conversion in candidate.get("setConversions") or []:
        if not isinstance(conversion, Mapping):
            continue
        set_id, _set_name, item_ids, _effects = _set_facts(conversion)
        if set_id == target_set_id:
            target_set_item_ids = item_ids
            break
    for item_id in target_set_item_ids:
        record = by_item.get(_text(item_id))
        if not record:
            continue
        slot = _text(record.get("itemSlot"))
        line = _record_line(record, slot)
        if slot and line:
            gear[slot] = line
            selected_item_ids[slot] = _text(item_id)
    if len(selected_item_ids) < 5 and not synthetic_fallback:
        missing.append(
            {
                "component": "tier_set",
                "code": "S2_REPRESENTATIVE_SET_PROFILE_INCOMPLETE",
            }
        )

    # These slots are not restricted by the class armour family.  Reusing the
    # same exact ring/trinket for the second copy is legal for a probe and
    # keeps the profile deterministic.
    for slot in ("neck", "back", "finger1", "finger2", "trinket1", "trinket2"):
        source_slot = "finger1" if slot == "finger2" else slot
        if slot.startswith("trinket"):
            source_slot = "trinket1"
        line = _text(base.get(source_slot))
        if line:
            gear[slot] = _line_for_slot(line, slot)
        else:
            missing.append({"component": slot, "code": "S2_REPRESENTATIVE_UNIVERSAL_SLOT_MISSING"})

    for slot in ("wrist", "waist", "feet"):
        record = _select_class_armor_record(
            by_slot,
            facts_by_item,
            class_key=class_key,
            slot=slot,
        )
        if record:
            item_id = _text(record.get("itemId"))
            gear[slot] = _record_line(record, slot)
            selected_item_ids[slot] = item_id
            continue
        if synthetic_fallback and _text(base.get(slot)):
            gear[slot] = _text(base.get(slot))
            continue
        missing.append(
            {
                "component": slot,
                "code": "S2_REPRESENTATIVE_CLASS_ARMOR_FACT_UNVERIFIED",
            }
        )

    weapon_key = f"{_text(class_key)}:{_text(spec_key)}"
    weapon_id = _REPRESENTATIVE_WEAPON_ITEM_ID_BY_SPEC.get(weapon_key, "")
    weapon = _select_record_by_item_id(by_item, weapon_id, slot="main_hand")
    if weapon is None and synthetic_fallback:
        main_line = _text(base.get("main_hand"))
        if main_line:
            gear["main_hand"] = main_line
    elif weapon is not None:
        gear["main_hand"] = _record_line(weapon, "main_hand")
        selected_item_ids["main_hand"] = _text(weapon.get("itemId"))
    else:
        missing.append(
            {
                "component": "main_hand",
                "code": "S2_REPRESENTATIVE_WEAPON_RECORD_MISSING",
            }
        )

    if weapon is not None and weapon_key in _REPRESENTATIVE_DUAL_WIELD_SPECS:
        gear["off_hand"] = _record_line(weapon, "off_hand")
        selected_item_ids["off_hand"] = _text(weapon.get("itemId"))

    selection_status = "verified"
    if synthetic_fallback:
        selection_status = "synthetic_fallback"
    elif missing:
        selection_status = "blocked"
    return gear, {
        "status": selection_status,
        "setId": target_set_id,
        "setItemIds": sorted(
            target_set_item_ids,
            key=lambda value: int(value) if value.isdigit() else value,
        ),
        "selectedItemIdsBySlot": selected_item_ids,
        "missing": missing,
        "armorSubclassId": _CLASS_ARMOR_SUBCLASS_BY_CLASS.get(_text(class_key)),
        "weaponItemId": weapon_id,
        "dualWield": weapon_key in _REPRESENTATIVE_DUAL_WIELD_SPECS,
    }


def _gear_with_target(
    base: Mapping[str, str],
    record: Mapping[str, Any],
) -> dict[str, str]:
    gear = dict(base)
    slot = _text(record.get("itemSlot"))
    canonical = _canonical_input(record)
    line = _line_for_slot(_text(canonical.get("line")), slot)
    if slot and line:
        gear[slot] = line
    return gear


def _enhancement_selections(
    candidate: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    catalog = _mapping(candidate.get("enhancementCatalog"))
    return sorted(
        (
            row
            for row in catalog.get("canonicalSelections") or []
            if isinstance(row, Mapping)
        ),
        key=lambda row: (
            _text(row.get("optionType")),
            _text(row.get("optionKey")),
        ),
    )


def _find_enhancement_base_record(
    candidate: Mapping[str, Any],
    selection: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    variant_key = _text(selection.get("baseVariantKey"))
    item_id = _text(selection.get("baseItemId"))
    slot = _text(selection.get("slot"))
    records = _public_records(candidate)
    if variant_key:
        for record in records:
            if (
                _text(record.get("variantKey")) == variant_key
                and (not item_id or _text(record.get("itemId")) == item_id)
                and (not slot or _text(record.get("itemSlot")) == slot)
                and _record_is_public(record)
            ):
                return record
    for record in records:
        if (
            _record_is_public(record)
            and (not item_id or _text(record.get("itemId")) == item_id)
            and (not slot or _text(record.get("itemSlot")) == slot)
        ):
            return record
    return None


def _parse_encoded_item_fields(encoded_item: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_part in _text(encoded_item).split(","):
        key, separator, value = raw_part.partition("=")
        if separator and _text(key) and _text(value):
            fields[_text(key)] = _text(value)
    return fields


def _enhancement_expected(
    candidate: Mapping[str, Any],
    selection: Mapping[str, Any],
) -> dict[str, Any]:
    canonical = _mapping(selection.get("canonicalSimcInput"))
    base = _find_enhancement_base_record(candidate, selection)
    expected = _record_expected(base) if base else {
        "itemId": "",
        "slot": "",
        "bonusIds": [],
        "itemLevel": None,
        "contextValues": [],
    }
    line = _text(canonical.get("line"))
    parsed_fields = _parse_encoded_item_fields(line)
    expected["itemId"] = (
        _text(selection.get("baseItemId"))
        or _text(canonical.get("itemId"))
        or expected.get("itemId")
        or _text(parsed_fields.get("id"))
    )
    expected["slot"] = (
        _text(selection.get("slot"))
        or _text(canonical.get("slot"))
        or expected.get("slot")
    )
    if isinstance(canonical.get("bonusIds"), list):
        expected["bonusIds"] = sorted(
            {_text(value) for value in canonical.get("bonusIds") or [] if _text(value)},
            key=lambda value: int(value) if value.isdigit() else value,
        )
    elif not expected.get("bonusIds") and parsed_fields.get("bonus_id"):
        expected["bonusIds"] = sorted(
            {
                _text(value)
                for value in parsed_fields["bonus_id"].split("/")
                if _text(value)
            },
            key=lambda value: int(value) if value.isdigit() else value,
        )
    if _integer(canonical.get("itemLevel")) is not None:
        expected["itemLevel"] = _integer(canonical.get("itemLevel"))
    elif expected.get("itemLevel") is None:
        expected["itemLevel"] = _integer(parsed_fields.get("ilevel"))
    if isinstance(canonical.get("itemContextValues"), list):
        expected["contextValues"] = sorted(
            {_text(value) for value in canonical.get("itemContextValues") or [] if _text(value)},
            key=lambda value: int(value) if value.isdigit() else value,
        )
    expected["simcOptions"] = {
        _text(key): _text(value)
        for key, value in (
            canonical.get("simcOptions")
            if isinstance(canonical.get("simcOptions"), Mapping)
            else {}
        ).items()
        if _text(key) and _text(value)
    }
    expected["canonicalLine"] = line
    expected["baseVariantKey"] = _text(selection.get("baseVariantKey"))
    return expected


def _set_facts(
    conversion: Mapping[str, Any],
) -> tuple[str, str, list[str], list[dict[str, Any]]]:
    preservation = _mapping(conversion.get("preservation"))
    facts = [
        row
        for row in preservation.get("setMembershipFacts") or []
        if isinstance(row, Mapping)
    ]
    if not facts:
        return "", "", [], []
    fact = facts[0]
    set_id = _text(fact.get("setId"))
    set_name = _text(fact.get("setName") or fact.get("name"))
    item_ids = [_text(value) for value in fact.get("itemIds") or [] if _text(value)]
    effects = [
        dict(effect)
        for effect in fact.get("effects") or []
        if isinstance(effect, Mapping)
    ]
    return set_id, set_name, item_ids, effects


def _set_probe_specs(
    set_id: str,
    supported_specs: Sequence[tuple[str, str]],
    explicit_specs: Sequence[tuple[str, str]] | None,
) -> list[tuple[str, str]]:
    if explicit_specs is not None:
        return list(explicit_specs)
    mapped = _DEFAULT_SET_PROBE_SPEC_BY_SET_ID.get(_text(set_id))
    if mapped:
        return [mapped]
    # Keep synthetic/test or newly observed set IDs auditable without
    # pretending that a generic supported spec is an authority for the set.
    return list(supported_specs)


def build_s2_equipment_library_simc_matrix_plan(
    candidate: Mapping[str, Any],
    *,
    runtime_identity: str,
    include_set_probe_specs: Iterable[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Build deterministic remote jobs without executing SimC."""

    runtime = parse_simc_runtime_identity(runtime_identity)
    base, base_blockers = _build_base_gear_lines(candidate)
    item_names = _candidate_item_names(candidate)
    base = _runtime_safe_gear(base, item_names)
    explicit_set_specs = (
        list(include_set_probe_specs)
        if include_set_probe_specs is not None
        else None
    )
    spec_source = (
        explicit_set_specs
        if explicit_set_specs is not None
        else [
            value.split(":", 1)
            for value in SIMC_EXECUTION_SUPPORTED_SPECIALIZATIONS
        ]
    )
    supported_specs = sorted(
        {
            (_text(class_key), _text(spec_key))
            for class_key, spec_key in spec_source
            if _text(class_key) and _text(spec_key)
        }
    )
    jobs: list[dict[str, Any]] = []
    blocked_public: list[dict[str, Any]] = []
    excluded_public: list[dict[str, Any]] = []
    sources_by_item = _candidate_item_logical_sources(candidate)
    public_records = [
        row
        for row in candidate.get("variants") or []
        if isinstance(row, Mapping)
    ]
    crafted_records = [
        row
        for row in candidate.get("craftedVariantTemplates") or []
        if isinstance(row, Mapping)
    ]
    for record in public_records:
        key = _text(record.get("variantKey"))
        if _record_is_crafted_only(record, sources_by_item):
            excluded_public.append(
                {
                    "jobKey": f"public:{key or _text(record.get('itemId'))}",
                    "itemId": _text(record.get("itemId")),
                    "variantKey": key,
                    "code": "S2_CRAFTED_VARIANT_SEPARATE_MATRIX",
                    "reasonCodes": [],
                }
            )
            continue
        if _record_is_excluded(record):
            excluded_public.append(
                {
                    "jobKey": f"public:{key or _text(record.get('itemId'))}",
                    "itemId": _text(record.get("itemId")),
                    "variantKey": key,
                    "code": "S2_PUBLIC_VARIANT_OUT_OF_SCOPE",
                    "reasonCodes": sorted(
                        {
                            _text(code)
                            for code in record.get("reasonCodes") or []
                            if _text(code)
                        }
                    ),
                }
            )
            continue
        if not _record_is_public(record):
            blocked_public.append(
                {
                    "jobKey": f"public:{key or _text(record.get('itemId'))}",
                    "itemId": _text(record.get("itemId")),
                    "variantKey": key,
                    "code": "S2_PUBLIC_VARIANT_CANONICAL_INPUT_UNVERIFIED",
                }
            )
            continue
        expected = _record_expected(record)
        job_key = f"public:{key}"
        player_name = _safe_player_name(job_key)
        public_gear = _gear_with_target(
            {"main_hand": _text(base.get("main_hand"))},
            record,
        )
        public_gear = _runtime_legalize_weapon_pair(
            public_gear,
            target_slot=expected["slot"],
        )
        public_gear = _runtime_safe_gear(public_gear, item_names)
        jobs.append(
            {
                "jobKey": job_key,
                "kind": "public_variant",
                "itemId": expected["itemId"],
                "variantKey": key,
                "slot": expected["slot"],
                "expected": expected,
                "classKey": "warrior",
                "specKey": "arms",
                "probeMode": "readback",
                "playerName": player_name,
                "profile": _profile_text(
                    player_name=player_name,
                    class_key="warrior",
                    spec_key="arms",
                    gear_lines=public_gear,
                    # Public variants are readback probes.  They need enough
                    # runtime for SimC to initialize and emit encoded gear,
                    # but not a DPS-quality combat window.
                    max_time=0.1,
                ),
            }
        )

    crafted_jobs: list[dict[str, Any]] = []
    crafted_blocked: list[dict[str, Any]] = []
    for record in crafted_records:
        key = _text(record.get("variantKey"))
        if not _record_is_public(record):
            crafted_blocked.append(
                {
                    "jobKey": f"crafted:{key or _text(record.get('itemId'))}",
                    "itemId": _text(record.get("itemId")),
                    "variantKey": key,
                    "recipeId": _text(record.get("recipeId")),
                    "code": "S2_CRAFTED_VARIANT_CANONICAL_INPUT_UNVERIFIED",
                }
            )
            continue
        expected = _record_expected(record)
        job_key = f"crafted:{key}"
        player_name = _safe_player_name(job_key)
        crafted_gear = _gear_with_target(
            {"main_hand": _text(base.get("main_hand"))},
            record,
        )
        crafted_gear = _runtime_legalize_weapon_pair(
            crafted_gear,
            target_slot=expected["slot"],
        )
        crafted_gear = _runtime_safe_gear(crafted_gear, item_names)
        crafted_jobs.append(
            {
                "jobKey": job_key,
                "kind": "crafted_variant",
                "itemId": expected["itemId"],
                "variantKey": key,
                "recipeId": _text(record.get("recipeId")),
                "slot": expected["slot"],
                "quality": _canonical(record.get("quality") or {}),
                "craftedTrackKey": _text(record.get("craftedTrackKey")),
                "craftedTrackCurrencyId": _text(record.get("craftedTrackCurrencyId")),
                "expected": expected,
                "classKey": "warrior",
                "specKey": "arms",
                "probeMode": "readback",
                "playerName": player_name,
                "profile": _profile_text(
                    player_name=player_name,
                    class_key="warrior",
                    spec_key="arms",
                    gear_lines=crafted_gear,
                    # Crafted quality/track probes have the same readback
                    # evidence boundary as public variants.
                    max_time=0.1,
                ),
            }
        )

    by_item = _public_records_by_item(candidate)

    set_probe_jobs: list[dict[str, Any]] = []
    set_blockers: list[dict[str, Any]] = []
    for conversion in candidate.get("setConversions") or []:
        if not isinstance(conversion, Mapping):
            continue
        conversion_item_id = _text(conversion.get("itemId"))
        set_id, set_name, item_ids, effects = _set_facts(conversion)
        if _text(conversion.get("status")) != "verified" or not set_id or not item_ids:
            set_blockers.append(
                {
                    "conversionItemId": conversion_item_id,
                    "code": "S2_SET_CONVERSION_FACT_UNVERIFIED",
                }
            )
            continue
        selected_set_specs = _set_probe_specs(
            set_id,
            supported_specs,
            explicit_set_specs,
        )
        if not set_name:
            set_blockers.append(
                {
                    "conversionItemId": conversion_item_id,
                    "setId": set_id,
                    "code": "S2_SET_CONVERSION_SET_NAME_UNVERIFIED",
                }
            )
            continue
        for class_key, spec_key in selected_set_specs:
            for required_count in _SET_EFFECT_COUNTS:
                selected_ids = [conversion_item_id]
                selected_ids.extend(
                    item_id
                    for item_id in item_ids
                    if item_id != conversion_item_id
                )
                selected_ids = selected_ids[:required_count]
                selected_records = [by_item.get(item_id) for item_id in selected_ids]
                if len(selected_records) != required_count or any(
                    record is None for record in selected_records
                ):
                    set_blockers.append(
                        {
                            "conversionItemId": conversion_item_id,
                            "setId": set_id,
                            "setName": set_name,
                            "requiredCount": required_count,
                            "classKey": class_key,
                            "specKey": spec_key,
                            "code": "S2_SET_CONVERSION_VARIANT_CANONICAL_INPUT_UNVERIFIED",
                        }
                    )
                    continue
                # Only the selected set pieces plus a weapon anchor are needed
                # to prove threshold initialization.  Carrying a plate-only
                # crafted base into cloth/leather/mail class probes creates an
                # unrelated SimC item-type failure before the set can load.
                gear = {
                    "main_hand": _text(base.get("main_hand")),
                }
                for selected in selected_records:
                    gear.update(_gear_with_target({}, selected))
                gear = _runtime_safe_gear(gear, item_names)
                pair_key = (
                    f"set:{conversion_item_id}:{set_id}:pc{required_count}:"
                    f"{class_key}:{spec_key}"
                )
                for enabled in (True, False):
                    job_key = f"{pair_key}:{'enabled' if enabled else 'disabled'}"
                    player_name = _safe_player_name(job_key)
                    set_probe_jobs.append(
                        {
                            "jobKey": job_key,
                            "pairKey": pair_key,
                            "kind": "set_conversion_probe",
                            "conversionItemId": conversion_item_id,
                            "setId": set_id,
                            "setName": set_name,
                            "requiredCount": required_count,
                            "setItemIds": selected_ids,
                            "setEffects": effects,
                            "classKey": class_key,
                            "specKey": spec_key,
                            "probeMode": "set_activation",
                            "enabled": enabled,
                            "playerName": player_name,
                            "profile": _profile_text(
                                player_name=player_name,
                                class_key=class_key,
                                spec_key=spec_key,
                                gear_lines=gear,
                                iterations=1,
                                max_time=1,
                                disable_set_bonuses=not enabled,
                                debug=True,
                            ),
                        }
                    )

    representative_jobs: list[dict[str, Any]] = []
    for class_key, spec_key in supported_specs:
        job_key = f"representative:{class_key}:{spec_key}"
        player_name = _safe_player_name(job_key)
        representative_gear, representative_selection = _select_representative_profile(
            candidate,
            class_key=class_key,
            spec_key=spec_key,
            base=base,
        )
        representative_gear = _runtime_safe_gear(
            representative_gear
            if representative_selection.get("dualWield")
            else _runtime_legalize_weapon_pair(representative_gear),
            item_names,
        )
        representative_jobs.append(
            {
                "jobKey": job_key,
                "kind": "representative_profile",
                "classKey": class_key,
                "specKey": spec_key,
                "probeMode": "dps",
                "playerName": player_name,
                "expectedSlotCount": len(representative_gear),
                "profileSelection": representative_selection,
                "profile": _profile_text(
                    player_name=player_name,
                    class_key=class_key,
                    spec_key=spec_key,
                    gear_lines=representative_gear,
                    iterations=1,
                    max_time=10,
                ),
            }
        )

    enhancement_jobs: list[dict[str, Any]] = []
    enhancement_blocked: list[dict[str, Any]] = []
    selections = _enhancement_selections(candidate)
    for selection in selections:
        selection_status = _text(selection.get("status"))
        canonical = _mapping(selection.get("canonicalSimcInput"))
        canonical_status = _text(canonical.get("status"))
        if selection_status != "verified" or canonical_status != "verified":
            enhancement_blocked.append(
                {
                    "optionKey": _text(selection.get("optionKey")),
                    "optionType": _text(selection.get("optionType")),
                    "status": "blocked",
                    "code": _text(selection.get("reasonCode"))
                    or "ENHANCEMENT_CANONICAL_SELECTION_UNVERIFIED",
                }
            )
            continue
        expected = _enhancement_expected(candidate, selection)
        option_key = _text(selection.get("optionKey"))
        job_key = f"enhancement:{option_key}"
        player_name = _safe_player_name(job_key)
        target_slot = _text(expected.get("slot"))
        target_line = _line_for_slot(
            _text(expected.get("canonicalLine")),
            target_slot,
        )
        gear = dict(base)
        if target_slot and target_line:
            gear[target_slot] = target_line
        gear = _runtime_safe_gear(
            _runtime_legalize_weapon_pair(gear, target_slot=target_slot),
            item_names,
        )
        enhancement_jobs.append(
            {
                "jobKey": job_key,
                "kind": "enhancement_probe",
                "optionKey": option_key,
                "optionType": _text(selection.get("optionType")),
                "baseVariantKey": _text(selection.get("baseVariantKey")),
                "baseItemId": _text(selection.get("baseItemId")),
                "slot": target_slot,
                "expected": expected,
                "classKey": "warrior",
                "specKey": "arms",
                "probeMode": "enhancement_readback",
                "playerName": player_name,
                "selectionStatus": selection_status,
                "profile": _profile_text(
                    player_name=player_name,
                    class_key="warrior",
                    spec_key="arms",
                    gear_lines=gear,
                    max_time=0.1,
                ),
            }
        )

    return {
        "schemaRevision": "s2-equipment-library-simc-matrix-plan-v1",
        "runtimeIdentity": _text(runtime_identity),
        "runtimeIdentityStatus": "verified" if runtime else "UNVERIFIED",
        "probeSpecSelection": {
            "source": "explicit" if explicit_set_specs is not None else "default_supported",
            "selected": [f"{class_key}:{spec_key}" for class_key, spec_key in supported_specs],
            "setBySetId": {
                _text(job.get("setId")): [
                    f"{_text(job.get('classKey'))}:{_text(job.get('specKey'))}"
                ]
                for job in set_probe_jobs
                if _text(job.get("setId"))
            },
        },
        "baseProfile": {
            "status": "verified" if not base_blockers else "blocked",
            "slotCount": len(base),
            "expectedSlotCount": len(_PROFILE_SLOTS),
            "missing": base_blockers,
            "slots": list(_PROFILE_SLOTS),
        },
        "publicVariantBlocked": blocked_public,
        "publicVariantExcluded": excluded_public,
        "craftedVariantBlocked": crafted_blocked,
        "setProbeBlocked": set_blockers,
        "jobs": jobs + crafted_jobs + set_probe_jobs + representative_jobs + enhancement_jobs,
        "enhancementProbeBlocked": enhancement_blocked,
        "counts": {
            "publicVariantJobCount": len(jobs),
            "publicVariantBlockedCount": len(blocked_public),
            "publicVariantExcludedCount": len(excluded_public),
            "craftedVariantJobCount": len(crafted_jobs),
            "craftedVariantBlockedCount": len(crafted_blocked),
            "setProbeJobCount": len(set_probe_jobs),
            "setProbeBlockedCount": len(set_blockers),
            "representativeProfileJobCount": len(representative_jobs),
            "enhancementSelectionCount": len(selections),
            "enhancementSelectionVerifiedCount": len(enhancement_jobs),
            "enhancementSelectionBlockedCount": len(enhancement_blocked),
            "enhancementProbeJobCount": len(enhancement_jobs),
            "totalJobCount": len(jobs) + len(crafted_jobs) + len(set_probe_jobs) + len(representative_jobs) + len(enhancement_jobs),
        },
    }


def _parse_encoded_item(encoded_item: str) -> tuple[str, list[str]]:
    text = _text(encoded_item)
    id_match = _ID_PATTERN.search(text)
    bonus_match = _BONUS_PATTERN.search(text)
    item_id = id_match.group("id") if id_match else ""
    bonus_ids = []
    if bonus_match:
        bonus_ids = [
            _text(value)
            for value in bonus_match.group("bonus").split("/")
            if _text(value)
        ]
    return item_id, sorted(set(bonus_ids), key=lambda value: int(value))


def _parse_simc_enhancement_options(encoded_item: str) -> dict[str, str]:
    fields = _parse_encoded_item_fields(encoded_item)
    return {
        field: _text(fields[field])
        for field in _SIMC_ENHANCEMENT_FIELDS
        if _text(fields.get(field))
    }


def validate_s2_item_probe_result(
    job: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate exact item identity/readback; returncode alone never passes."""

    expected = _mapping(job.get("expected"))
    failures: list[str] = []
    probe_mode = _text(job.get("probeMode")) or "dps"
    dps_required = probe_mode not in {"readback", "enhancement_readback"}
    returncode = _integer(result.get("returncode"))
    if returncode != 0:
        failures.append("SIMC_ITEM_PROBE_RETURNCODE_NONZERO")
    gear = _mapping(result.get("gear"))
    slot = _text(expected.get("slot"))
    simc_slot = _simc_slot(slot)
    observed = _mapping(gear.get(simc_slot))
    encoded_item = _text(observed.get("encoded_item"))
    observed_id, observed_bonus_ids = _parse_encoded_item(encoded_item)
    expected_id = _text(expected.get("itemId"))
    expected_bonus_ids = sorted(
        {_text(value) for value in expected.get("bonusIds") or [] if _text(value)},
        key=lambda value: int(value) if value.isdigit() else value,
    )
    if not observed:
        failures.append("SIMC_ITEM_PROBE_GEAR_READBACK_MISSING")
    if observed_id != expected_id:
        failures.append("SIMC_ITEM_PROBE_ITEM_ID_MISMATCH")
    if observed_bonus_ids != expected_bonus_ids:
        failures.append("SIMC_ITEM_PROBE_BONUS_VECTOR_MISMATCH")
    expected_level = _integer(expected.get("itemLevel"))
    observed_level = _integer(observed.get("ilevel"))
    if expected_level is not None and observed_level != expected_level:
        failures.append("SIMC_ITEM_PROBE_ITEM_LEVEL_MISMATCH")
    static_keys = sorted(
        key
        for key, value in observed.items()
        if key not in {"name", "encoded_item", "ilevel"}
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
    )
    if not static_keys:
        failures.append("SIMC_ITEM_PROBE_STATIC_ATTRIBUTE_READBACK_MISSING")
    dps = _number(result.get("dps"))
    if dps_required and dps is None:
        failures.append("SIMC_ITEM_PROBE_DPS_MISSING")
    return {
        "jobKey": _text(job.get("jobKey")),
        "status": "verified" if not failures else "blocked",
        "failureCodes": sorted(set(failures)),
        "returncode": returncode,
        "itemId": expected_id,
        "slot": slot,
        "simcSlot": simc_slot,
        "expectedBonusIds": expected_bonus_ids,
        "observedItemId": observed_id,
        "observedBonusIds": observed_bonus_ids,
        "expectedItemLevel": expected_level,
        "observedItemLevel": observed_level,
        "staticAttributeReadbackStatus": "observed" if static_keys else "UNVERIFIED",
        "staticAttributeKeys": static_keys,
        "probeMode": probe_mode,
        "dpsRequired": dps_required,
        "dps": dps,
        "warnings": list(result.get("warnings") or []),
        "stderr": _text(result.get("stderr"))[:2000],
    }


def validate_s2_enhancement_probe_result(
    job: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate exact item and requested enhancement readback.

    SimC returncode zero is only one input to this result.  The canonical item
    identity, bonus vector, item level, static attributes, and every requested
    enhancement option must all be present in the same actor's gear readback.
    """

    item_result = validate_s2_item_probe_result(job, result)
    failures = list(item_result.get("failureCodes") or [])
    expected = _mapping(job.get("expected"))
    expected_options = {
        _text(key): _text(value)
        for key, value in (_mapping(expected.get("simcOptions"))).items()
        if _text(key) and _text(value)
    }
    gear = _mapping(result.get("gear"))
    observed = _mapping(gear.get(_simc_slot(_text(expected.get("slot")))))
    observed_options = _parse_simc_enhancement_options(
        _text(observed.get("encoded_item"))
    )
    if not expected_options:
        failures.append("SIMC_ENHANCEMENT_OPTIONS_EXPECTED_MISSING")
    for key, value in expected_options.items():
        if key not in observed_options:
            failures.append("SIMC_ENHANCEMENT_OPTION_READBACK_MISSING")
        elif observed_options[key] != value:
            failures.append("SIMC_ENHANCEMENT_OPTION_READBACK_MISMATCH")
    return {
        **item_result,
        "optionKey": _text(job.get("optionKey")),
        "optionType": _text(job.get("optionType")),
        "expectedSimcOptions": expected_options,
        "observedSimcOptions": {
            key: observed_options.get(key)
            for key in expected_options
            if key in observed_options
        },
        "enhancementReadbackStatus": (
            "verified"
            if expected_options
            and all(
                observed_options.get(key) == value
                for key, value in expected_options.items()
            )
            else "UNVERIFIED"
        ),
        "failureCodes": sorted(set(failures)),
        "status": "verified" if not failures else "blocked",
    }


def _validate_representative_result(job: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    selection = _mapping(job.get("profileSelection"))
    selection_status = _text(selection.get("status"))
    if selection_status not in {"verified", "synthetic_fallback"}:
        failures.append("SIMC_REPRESENTATIVE_PROFILE_SELECTION_UNVERIFIED")
    if _integer(result.get("returncode")) != 0:
        failures.append("SIMC_REPRESENTATIVE_PROFILE_RETURNCODE_NONZERO")
    if _number(result.get("dps")) is None:
        failures.append("SIMC_REPRESENTATIVE_PROFILE_DPS_MISSING")
    gear = _mapping(result.get("gear"))
    expected_slots = _integer(job.get("expectedSlotCount")) or len(_PROFILE_SLOTS)
    if len(gear) < expected_slots:
        failures.append("SIMC_REPRESENTATIVE_PROFILE_SLOT_READBACK_INCOMPLETE")
    return {
        "jobKey": _text(job.get("jobKey")),
        "status": "verified" if not failures else "blocked",
        "failureCodes": sorted(set(failures)),
        "returncode": _integer(result.get("returncode")),
        "dps": _number(result.get("dps")),
        "gearSlotCount": len(gear),
        "expectedSlotCount": expected_slots,
        "profileSelectionStatus": selection_status or "UNVERIFIED",
        "profileSelection": selection,
        "warnings": list(result.get("warnings") or []),
        "stderr": _text(result.get("stderr"))[:2000],
    }


def _set_probe_result(
    pair_jobs: Sequence[Mapping[str, Any]],
    results: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    enabled = next(
        (results.get(_text(job.get("jobKey"))) for job in pair_jobs if job.get("enabled") is True),
        None,
    )
    disabled = next(
        (results.get(_text(job.get("jobKey"))) for job in pair_jobs if job.get("enabled") is False),
        None,
    )
    failures: list[str] = []
    if not enabled or not disabled:
        failures.append("SIMC_SET_CONVERSION_CONTROL_PAIR_MISSING")
    enabled_dps = _number((enabled or {}).get("dps"))
    disabled_dps = _number((disabled or {}).get("dps"))
    if enabled_dps is None or disabled_dps is None:
        # Set activation is proved by the runtime initialization trace below;
        # DPS is retained as a diagnostic only because a one-iteration delta
        # is not a valid effect-activation oracle.
        pass
    delta = None
    if enabled_dps is not None and disabled_dps is not None:
        delta = enabled_dps - disabled_dps
    for result in (enabled, disabled):
        if result and _integer(result.get("returncode")) != 0:
            failures.append("SIMC_SET_CONVERSION_RETURNCODE_NONZERO")
    sample = pair_jobs[0] if pair_jobs else {}
    expected_set_item_ids = {
        _text(value) for value in sample.get("setItemIds") or [] if _text(value)
    }
    observed_set_item_ids: dict[str, list[str]] = {}
    for label, result in (("enabled", enabled), ("disabled", disabled)):
        observed: set[str] = set()
        gear = _mapping((result or {}).get("gear"))
        for item in gear.values():
            if not isinstance(item, Mapping):
                continue
            item_id, _bonus_ids = _parse_encoded_item(_text(item.get("encoded_item")))
            if item_id:
                observed.add(item_id)
        observed_set_item_ids[label] = sorted(observed, key=lambda value: int(value))
        if result and not expected_set_item_ids.issubset(observed):
            failures.append("SIMC_SET_CONVERSION_SET_ITEM_READBACK_UNVERIFIED")
    set_item_readback_ok = bool(expected_set_item_ids) and (
        "SIMC_SET_CONVERSION_SET_ITEM_READBACK_UNVERIFIED" not in failures
    )
    expected_set_name = _text(sample.get("setName"))
    required_count = _integer(sample.get("requiredCount"))
    enabled_initialization_lines = [
        _text(value)
        for value in (enabled or {}).get("setBonusInitializationLines") or []
        if _text(value)
    ]
    disabled_initialization_lines = [
        _text(value)
        for value in (disabled or {}).get("setBonusInitializationLines") or []
        if _text(value)
    ]
    expected_marker = (
        f"{expected_set_name},"
        if expected_set_name
        else ""
    )
    expected_threshold_marker = (
        f"{required_count} piece bonus"
        if required_count is not None
        else ""
    )
    enabled_initialization_observed = bool(
        expected_marker
        and expected_threshold_marker
        and any(
            expected_marker in line and expected_threshold_marker in line
            for line in enabled_initialization_lines
        )
    )
    disabled_initialization_observed = any(
        expected_marker and expected_marker in line
        for line in disabled_initialization_lines
    )
    if not enabled_initialization_observed:
        failures.append("SIMC_SET_EFFECT_INITIALIZATION_NOT_OBSERVED")
    if disabled_initialization_observed:
        failures.append("SIMC_SET_EFFECT_DISABLED_CONTROL_NOT_OBSERVED")
    initialization_status = (
        "verified"
        if enabled_initialization_observed and not disabled_initialization_observed
        else "UNVERIFIED"
    )
    return {
        "jobKey": _text(sample.get("pairKey")),
        "status": "verified" if not failures else "blocked",
        "failureCodes": sorted(set(failures)),
        "conversionItemId": _text(sample.get("conversionItemId")),
        "setId": _text(sample.get("setId")),
        "requiredCount": _integer(sample.get("requiredCount")),
        "setName": expected_set_name,
        "classKey": _text(sample.get("classKey")),
        "specKey": _text(sample.get("specKey")),
        "setItemIds": list(sample.get("setItemIds") or []),
        "setItemReadbackStatus": "verified" if set_item_readback_ok else "UNVERIFIED",
        "observedSetItemIds": observed_set_item_ids,
        "enabledDps": enabled_dps,
        "disabledDps": disabled_dps,
        "dpsDelta": delta,
        "effectActivationObserved": bool(delta is not None and abs(delta) >= 0.0001),
        "setBonusInitializationStatus": initialization_status,
        "setBonusInitializationLines": {
            "enabled": enabled_initialization_lines,
            "disabled": disabled_initialization_lines,
        },
    }


def _stable_report_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        key: report.get(key)
        for key in (
            "schemaRevision",
            "status",
            "runtimeIdentity",
            "candidateReportId",
            "probeSpecSelection",
            "counts",
            "blockerCodes",
            "publicVariantMatrix",
            "craftedVariantMatrix",
            "setConversionMatrix",
            "representativeProfileMatrix",
            "enhancementMatrix",
        )
    }
    if report.get("matrixReuse") is not None:
        payload["matrixReuse"] = report.get("matrixReuse")
    return payload


def _matrix_plan_digest(plan: Mapping[str, Any]) -> str:
    """Hash the complete deterministic matrix plan, including blocked jobs."""

    body = json.dumps(
        _canonical(plan),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def rebind_s2_equipment_library_simc_matrix_report(
    candidate: Mapping[str, Any],
    source_report: Mapping[str, Any],
    source_plan: Mapping[str, Any],
    target_plan: Mapping[str, Any],
    *,
    golden_prefix: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Reuse results only when the complete fixed-runtime plan is identical.

    A Candidate report identity may change when only evidence references or
    capture provenance changes.  Re-running identical canonical SimC inputs
    would add no new runtime evidence, so this adapter permits a transparent
    rebind after comparing the complete plan byte-for-byte in canonical JSON.
    It never permits a changed, missing, or reordered blocked/public job set.
    """

    if _canonical(source_plan) != _canonical(target_plan):
        raise ValueError("SIMC_MATRIX_REUSE_PLAN_MISMATCH")
    expected_runtime = _text(target_plan.get("runtimeIdentity"))
    if not expected_runtime or expected_runtime != _text(source_plan.get("runtimeIdentity")):
        raise ValueError("SIMC_MATRIX_REUSE_RUNTIME_IDENTITY_MISMATCH")
    if _text(source_report.get("schemaRevision")) != S2_EQUIPMENT_LIBRARY_SIMC_MATRIX_SCHEMA_REVISION:
        raise ValueError("SIMC_MATRIX_REUSE_SOURCE_SCHEMA_UNSUPPORTED")
    if _text(source_report.get("runtimeIdentity")) != expected_runtime:
        raise ValueError("SIMC_MATRIX_REUSE_SOURCE_RUNTIME_IDENTITY_MISMATCH")
    if _text(source_report.get("runtimeIdentityStatus")) != "verified":
        raise ValueError("SIMC_MATRIX_REUSE_SOURCE_RUNTIME_UNVERIFIED")
    prefix = _mapping(golden_prefix)
    if _text(prefix.get("status")) != "verified":
        raise ValueError("SIMC_MATRIX_REUSE_GOLDEN_PREFIX_UNVERIFIED")
    if _text(prefix.get("runtimeIdentity")) != expected_runtime:
        raise ValueError("SIMC_MATRIX_REUSE_GOLDEN_PREFIX_RUNTIME_IDENTITY_MISMATCH")
    source_status = _text(source_report.get("status"))
    if source_status not in {"partial", "verified"}:
        raise ValueError("SIMC_MATRIX_REUSE_SOURCE_REPORT_UNUSABLE")
    candidate_id = _text(candidate.get("reportId"))
    if not candidate_id:
        raise ValueError("SIMC_MATRIX_REUSE_CANDIDATE_ID_MISSING")

    plan_digest = _matrix_plan_digest(target_plan)
    report = _canonical(source_report)
    source_report_id = _text(report.get("reportId"))
    source_candidate_id = _text(report.get("candidateReportId"))
    report["candidateReportId"] = candidate_id
    report["candidateIdentity"] = candidate_id
    report["runtimeIdentity"] = expected_runtime
    report["runtimeIdentityStatus"] = "verified"
    report["goldenPrefix"] = {
        "status": "verified",
        "runtimeIdentity": expected_runtime,
        "reportId": _text(prefix.get("reportId")),
    }
    report["matrixReuse"] = {
        "mode": "strict_plan_equivalent_reuse",
        "sourceReportId": source_report_id,
        "sourceCandidateReportId": source_candidate_id,
        "sourcePlanDigest": plan_digest,
        "targetPlanDigest": plan_digest,
        "runtimeIdentity": expected_runtime,
        "jobCount": len(target_plan.get("jobs") or []),
    }
    digest = hashlib.sha256(
        json.dumps(
            _stable_report_payload(report),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    report["reportId"] = f"{S2_EQUIPMENT_LIBRARY_SIMC_MATRIX_REPORT_PREFIX}{digest}"
    report["matrixReuse"]["reportId"] = report["reportId"]
    return report


def assemble_s2_equipment_library_simc_matrix_report(
    candidate: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    batch_results: Sequence[Mapping[str, Any]],
    golden_prefix: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a fail-closed report from remote batch results."""

    expected_runtime = _text(plan.get("runtimeIdentity"))
    runtime_statuses = {
        _text(batch.get("runtimeIdentityStatus"))
        for batch in batch_results
        if isinstance(batch, Mapping)
    }
    runtime_identity_ok = bool(batch_results) and runtime_statuses == {"verified"}
    if not batch_results and not plan.get("jobs"):
        runtime_identity_ok = bool(plan.get("runtimeIdentityStatus") == "verified")
    result_by_key: dict[str, Mapping[str, Any]] = {}
    for batch in batch_results:
        for raw_result in batch.get("results") or []:
            if isinstance(raw_result, Mapping) and _text(raw_result.get("jobKey")):
                result_by_key[_text(raw_result.get("jobKey"))] = raw_result

    public_results: list[dict[str, Any]] = []
    crafted_results: list[dict[str, Any]] = []
    set_job_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    representative_results: list[dict[str, Any]] = []
    enhancement_results: list[dict[str, Any]] = []
    for job in plan.get("jobs") or []:
        if not isinstance(job, Mapping):
            continue
        result = result_by_key.get(_text(job.get("jobKey")), {})
        kind = _text(job.get("kind"))
        if kind == "public_variant":
            public_results.append(validate_s2_item_probe_result(job, result))
        elif kind == "crafted_variant":
            crafted_results.append(validate_s2_item_probe_result(job, result))
        elif kind == "set_conversion_probe":
            set_job_groups[_text(job.get("pairKey"))].append(job)
        elif kind == "representative_profile":
            representative_results.append(_validate_representative_result(job, result))
        elif kind == "enhancement_probe":
            enhancement_results.append(validate_s2_enhancement_probe_result(job, result))

    set_results = [
        _set_probe_result(
            pair_jobs,
            result_by_key,
        )
        for _pair_key, pair_jobs in sorted(set_job_groups.items())
    ]
    # A conversion/threshold is closed when at least one supported class/spec
    # pair observes the enabled-vs-disabled set-bonus delta.  The job plan
    # still records every supported pair, so a class-specific runtime mapping
    # remains auditable instead of being inferred from a single sample.
    set_conversion_results: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for result in set_results:
        set_conversion_results[
            (_text(result.get("conversionItemId")), _integer(result.get("requiredCount")) or 0)
        ].append(result)
    set_conversion_matrix: list[dict[str, Any]] = []
    for key, rows in sorted(set_conversion_results.items(), key=lambda value: (value[0][0], value[0][1])):
        passing = [row for row in rows if row.get("status") == "verified"]
        first = rows[0] if rows else {}
        set_conversion_matrix.append(
            {
                "conversionItemId": key[0],
                "setId": _text(first.get("setId")),
                "requiredCount": key[1],
                "status": "verified" if passing else "blocked",
                "passingProbeCount": len(passing),
                "probeCount": len(rows),
                "passingProbe": passing[0] if passing else None,
                "failureCodes": sorted(
                    {
                        code
                        for row in rows
                        for code in row.get("failureCodes") or []
                    }
                ),
            }
        )

    public_blockers = list(plan.get("publicVariantBlocked") or [])
    public_blockers.extend(
        {
            "jobKey": row.get("jobKey"),
            "itemId": row.get("itemId"),
            "variantKey": row.get("variantKey"),
            "code": code,
        }
        for row in public_results
        for code in row.get("failureCodes") or []
    )
    public_status = (
        "verified"
        if public_results
        and all(row.get("status") == "verified" for row in public_results)
        else "blocked"
    )
    crafted_blockers = list(plan.get("craftedVariantBlocked") or [])
    crafted_blockers.extend(
        {
            "jobKey": row.get("jobKey"),
            "itemId": row.get("itemId"),
            "variantKey": row.get("variantKey"),
            "recipeId": row.get("recipeId"),
            "code": code,
        }
        for row in crafted_results
        for code in row.get("failureCodes") or []
    )
    crafted_expected_count = len(crafted_results) + len(
        plan.get("craftedVariantBlocked") or []
    )
    crafted_status = (
        "not_applicable"
        if crafted_expected_count == 0
        else "verified"
        if not plan.get("craftedVariantBlocked")
        and crafted_results
        and all(row.get("status") == "verified" for row in crafted_results)
        else "blocked"
    )
    set_status = (
        "verified"
        if set_conversion_matrix
        and not plan.get("setProbeBlocked")
        and all(row.get("status") == "verified" for row in set_conversion_matrix)
        else "blocked"
    )
    representative_status = (
        "verified"
        if representative_results
        and all(row.get("status") == "verified" for row in representative_results)
        else "blocked"
    )
    selections = _enhancement_selections(candidate)
    selection_blocked = list(plan.get("enhancementProbeBlocked") or [])
    enhancement_probe_count = len(enhancement_results)
    enhancement_verified_count = sum(
        1 for row in enhancement_results if row.get("status") == "verified"
    )
    if not selections:
        enhancement_matrix = {
            "status": "UNVERIFIED",
            "reasonCode": "CRAFTED_ENHANCEMENT_SIMC_INPUT_UNVERIFIED",
            "recipeCompatibilityEdgeCount": sum(
                1
                for row in candidate.get("craftedRelationships") or []
                if isinstance(row, Mapping)
                and _text(row.get("scopeStatus")) == "included"
            ),
            "canonicalSelectionCount": 0,
            "canonicalSelectionVerifiedCount": 0,
            "canonicalSelectionBlockedCount": 0,
            "simcProbeCount": 0,
            "verifiedProbeCount": 0,
            "blockedProbeCount": 0,
            "results": [],
            "blocked": [],
        }
    else:
        enhancement_status = (
            "verified"
            if (
                not selection_blocked
                and enhancement_probe_count == len(selections)
                and enhancement_verified_count == enhancement_probe_count
            )
            else "blocked"
        )
        enhancement_matrix = {
            "status": enhancement_status,
            "reasonCode": None
            if enhancement_status == "verified"
            else "ENHANCEMENT_CANONICAL_SELECTION_OR_SIMC_READBACK_UNVERIFIED",
            "recipeCompatibilityEdgeCount": sum(
                1
                for row in candidate.get("craftedRelationships") or []
                if isinstance(row, Mapping)
                and _text(row.get("scopeStatus")) == "included"
            ),
            "canonicalSelectionCount": len(selections),
            "canonicalSelectionVerifiedCount": len(selections) - len(selection_blocked),
            "canonicalSelectionBlockedCount": len(selection_blocked),
            "simcProbeCount": enhancement_probe_count,
            "verifiedProbeCount": enhancement_verified_count,
            "blockedProbeCount": enhancement_probe_count - enhancement_verified_count,
            "results": sorted(
                enhancement_results,
                key=lambda row: _text(row.get("jobKey")),
            ),
            "blocked": sorted(
                selection_blocked,
                key=lambda row: (_text(row.get("optionType")), _text(row.get("optionKey"))),
            ),
        }
    golden_status = _text(_mapping(golden_prefix).get("status")) or "UNVERIFIED"
    blocker_codes: set[str] = set()
    if not runtime_identity_ok:
        blocker_codes.add("SIMC_RUNTIME_IDENTITY_MISMATCH")
    if _text(expected_runtime) != _text(_mapping(golden_prefix).get("runtimeIdentity")):
        blocker_codes.add("SIMC_GOLDEN_PREFIX_RUNTIME_IDENTITY_MISMATCH")
    if golden_status != "verified":
        blocker_codes.add("SIMC_GOLDEN_PREFIX_UNVERIFIED")
    if public_status != "verified":
        blocker_codes.add("SIMC_PUBLIC_VARIANT_MATRIX_UNVERIFIED")
    if crafted_status not in {"verified", "not_applicable"}:
        blocker_codes.add("SIMC_CRAFTED_VARIANT_MATRIX_UNVERIFIED")
    if set_status != "verified":
        blocker_codes.add("SIMC_SET_CONVERSION_MATRIX_UNVERIFIED")
    if representative_status != "verified":
        blocker_codes.add("SIMC_REPRESENTATIVE_PROFILE_MATRIX_UNVERIFIED")
    if enhancement_matrix.get("status") != "verified":
        blocker_codes.add("SIMC_ENHANCEMENT_MATRIX_UNVERIFIED")
    status = "verified" if not blocker_codes else "partial"
    counts = {
        "publicVariantExpectedCount": len(public_results) + len(plan.get("publicVariantBlocked") or []),
        "publicVariantProbeCount": len(public_results),
        "publicVariantVerifiedCount": sum(
            1 for row in public_results if row.get("status") == "verified"
        ),
        "publicVariantBlockedCount": len(public_blockers),
        "publicVariantExcludedCount": len(plan.get("publicVariantExcluded") or []),
        "craftedVariantExpectedCount": len(crafted_results)
        + len(plan.get("craftedVariantBlocked") or []),
        "craftedVariantProbeCount": len(crafted_results),
        "craftedVariantVerifiedCount": sum(
            1 for row in crafted_results if row.get("status") == "verified"
        ),
        "craftedVariantBlockedCount": len(crafted_blockers),
        "setConversionExpectedCount": len(set_conversion_matrix),
        "setConversionVerifiedCount": sum(
            1 for row in set_conversion_matrix if row.get("status") == "verified"
        ),
        "representativeProfileExpectedCount": len(representative_results),
        "representativeProfileVerifiedCount": sum(
            1 for row in representative_results if row.get("status") == "verified"
        ),
        "enhancementCanonicalSelectionCount": _integer(
            enhancement_matrix.get("canonicalSelectionCount")
        )
        or 0,
        "enhancementCanonicalSelectionVerifiedCount": _integer(
            enhancement_matrix.get("canonicalSelectionVerifiedCount")
        )
        or 0,
        "enhancementCanonicalSelectionBlockedCount": _integer(
            enhancement_matrix.get("canonicalSelectionBlockedCount")
        )
        or 0,
        "enhancementProbeCount": enhancement_probe_count,
        "enhancementVerifiedCount": enhancement_verified_count,
        "enhancementBlockedCount": enhancement_probe_count - enhancement_verified_count,
        "remoteBatchCount": len(batch_results),
    }
    report = {
        "schemaRevision": S2_EQUIPMENT_LIBRARY_SIMC_MATRIX_SCHEMA_REVISION,
        "status": status,
        "runtimeIdentity": expected_runtime,
        "candidateReportId": _text(candidate.get("reportId")),
        "candidateIdentity": _text(candidate.get("reportId")),
        "runtimeIdentityStatus": "verified" if runtime_identity_ok else "UNVERIFIED",
        "goldenPrefix": {
            "status": golden_status,
            "runtimeIdentity": _text(_mapping(golden_prefix).get("runtimeIdentity")),
            "reportId": _text(_mapping(golden_prefix).get("reportId")),
        },
        "baseProfile": _canonical(plan.get("baseProfile") or {}),
        "probeSpecSelection": _canonical(plan.get("probeSpecSelection") or {}),
        "counts": counts,
        "blockerCodes": sorted(blocker_codes),
        "publicVariantMatrix": {
            "status": public_status,
            "results": sorted(public_results, key=lambda row: _text(row.get("jobKey"))),
            "blocked": sorted(
                public_blockers,
                key=lambda row: (_text(row.get("jobKey")), _text(row.get("code"))),
            ),
            "excluded": sorted(
                list(plan.get("publicVariantExcluded") or []),
                key=lambda row: (_text(row.get("jobKey")), _text(row.get("code"))),
            ),
        },
        "craftedVariantMatrix": {
            "status": crafted_status,
            "results": sorted(
                crafted_results,
                key=lambda row: _text(row.get("jobKey")),
            ),
            "blocked": sorted(
                crafted_blockers,
                key=lambda row: (_text(row.get("jobKey")), _text(row.get("code"))),
            ),
            "probeEvidenceBoundary": (
                "exact_crafted_output_item_quality_track_bonus_vector_and_item_level_readback"
            ),
        },
        "setConversionMatrix": {
            "status": set_status,
            "results": set_conversion_matrix,
            "blocked": list(plan.get("setProbeBlocked") or []),
            "probeEvidenceBoundary": (
                "enabled_vs_disabled_set_bonuses_same_exact_item_profile_runtime_initialization_trace"
            ),
        },
        "representativeProfileMatrix": {
            "status": representative_status,
            "results": sorted(
                representative_results,
                key=lambda row: _text(row.get("jobKey")),
            ),
        },
        "enhancementMatrix": enhancement_matrix,
    }
    digest = hashlib.sha256(
        json.dumps(
            _stable_report_payload(report),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    report["reportId"] = f"{S2_EQUIPMENT_LIBRARY_SIMC_MATRIX_REPORT_PREFIX}{digest}"
    return report


_REMOTE_WORKER = r'''
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

RUNTIME_RE = re.compile(r"^simc:(?P<build>[^:]+):(?P<commit>[0-9a-f]{40}):(?P<binary>[0-9a-f]{64})$")

def text(value):
    return str(value or "").strip()

def runtime_identity(expected):
    match = RUNTIME_RE.fullmatch(text(expected))
    if not match:
        return {"status": "UNVERIFIED", "identity": "", "build": "", "commit": "", "binarySha256": "", "versionOutput": ""}
    commit_path = "/opt/wow-simc/.commit"
    binary_path = "/opt/wow-simc/current/simc"
    try:
        commit = open(commit_path, encoding="utf-8").read().strip()
        binary = hashlib.sha256(open(binary_path, "rb").read()).hexdigest()
        version = subprocess.run([binary_path, "--version"], text=True, capture_output=True, timeout=30)
        version_output = (version.stdout or version.stderr or "").strip().splitlines()[0] if (version.stdout or version.stderr) else ""
    except Exception as error:
        return {"status": "UNVERIFIED", "identity": "", "build": "", "commit": "", "binarySha256": "", "versionOutput": "", "error": str(error)}
    build_ok = match.group("build") in version_output
    ok = commit == match.group("commit") and binary == match.group("binary") and build_ok
    identity = "simc:%s:%s:%s" % (match.group("build"), commit, binary)
    return {"status": "verified" if ok else "UNVERIFIED", "identity": identity, "build": match.group("build"), "commit": commit, "binarySha256": binary, "versionOutput": version_output}

def dps_value(player):
    collected = player.get("collected_data") if isinstance(player.get("collected_data"), dict) else {}
    dps = collected.get("dps") if isinstance(collected.get("dps"), dict) else {}
    value = dps.get("mean")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def warnings(stderr):
    return [line.strip() for line in str(stderr or "").splitlines() if "warning" in line.lower() or "trivial" in line.lower()]

def set_bonus_initialization_lines(stdout, stderr):
    text_value = "%s\n%s" % (str(stdout or ""), str(stderr or ""))
    return [
        line.strip()
        for line in text_value.splitlines()
        if "Initialized set bonus:" in line
    ]

payload = json.load(sys.stdin)
runtime = runtime_identity(payload.get("runtimeIdentity"))
jobs = payload.get("jobs") if isinstance(payload.get("jobs"), list) else []
profiles = [text(job.get("profile")) for job in jobs if isinstance(job, dict) and text(job.get("profile"))]
profile = "\n".join(profiles) + "\n"
results = []
with tempfile.TemporaryDirectory(prefix="s2-equipment-matrix-") as directory:
    output_path = os.path.join(directory, "simc.json")
    profile += "json=" + output_path + "\n"
    try:
        executed = subprocess.run(["/opt/wow-simc/current/simc", "-"], input=profile, text=True, capture_output=True, timeout=int(payload.get("timeoutSeconds") or 900))
        payload_json = json.load(open(output_path, encoding="utf-8")) if os.path.exists(output_path) else {}
        players = payload_json.get("sim", {}).get("players", []) if isinstance(payload_json.get("sim"), dict) else []
        by_name = {text(player.get("name")): player for player in players if isinstance(player, dict)}
        for job in jobs:
            job = job if isinstance(job, dict) else {}
            player = by_name.get(text(job.get("playerName")), {})
            results.append({"jobKey": text(job.get("jobKey")), "returncode": executed.returncode, "dps": dps_value(player), "gear": player.get("gear") if isinstance(player.get("gear"), dict) else {}, "warnings": warnings(executed.stderr), "stderr": (executed.stderr or "")[-4000:], "setBonusInitializationLines": set_bonus_initialization_lines(executed.stdout, executed.stderr)})
    except Exception as error:
        for job in jobs:
            job = job if isinstance(job, dict) else {}
            results.append({"jobKey": text(job.get("jobKey")), "returncode": 124, "dps": None, "gear": {}, "warnings": [], "stderr": str(error)})
print(json.dumps({"status": "verified" if runtime.get("status") == "verified" else "blocked", "runtimeIdentityStatus": runtime.get("status"), "runtimeIdentity": runtime.get("identity"), "runtime": runtime, "results": results}, ensure_ascii=False))
'''


def execute_s2_equipment_library_simc_batches(
    plan: Mapping[str, Any],
    *,
    remote: str = "wow-lighthouse",
    batch_size: int = 100,
    timeout_seconds: int = 900,
    workers: int = 3,
    progress_callback: Callable[[int, int], Any] | None = None,
) -> list[dict[str, Any]]:
    """Execute plan jobs on the fixed cloud runtime in bounded batches."""

    if isinstance(batch_size, bool) or int(batch_size) < 1:
        raise ValueError("batch_size must be positive")
    if isinstance(workers, bool) or int(workers) < 1:
        raise ValueError("workers must be positive")
    jobs = [job for job in plan.get("jobs") or [] if isinstance(job, Mapping)]
    encoded_worker = base64.b64encode(_REMOTE_WORKER.encode("utf-8")).decode("ascii")
    expression = f"import base64;exec(base64.b64decode({encoded_worker!r}))"
    remote_command = "python3 -c " + shlex.quote(expression)
    # SimC only emits actor-level debug/readback data reliably for a
    # single-player invocation.  Set activation and representative jobs
    # therefore run as singleton batches; ordinary public readback jobs retain
    # the bounded batching path.  This is an execution-shape constraint, not a
    # change to the evidence owner or to the product scope.
    job_batches: list[list[Mapping[str, Any]]] = []
    normal_batch: list[Mapping[str, Any]] = []
    for job in jobs:
        if _text(job.get("kind")) in {
            "set_conversion_probe",
            "representative_profile",
            "enhancement_probe",
        }:
            if normal_batch:
                job_batches.append(normal_batch)
                normal_batch = []
            job_batches.append([job])
            continue
        normal_batch.append(job)
        if len(normal_batch) >= int(batch_size):
            job_batches.append(normal_batch)
            normal_batch = []
    if normal_batch:
        job_batches.append(normal_batch)

    def run_batch(batch_jobs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        request = {
            "runtimeIdentity": _text(plan.get("runtimeIdentity")),
            "timeoutSeconds": int(timeout_seconds),
            "jobs": batch_jobs,
        }
        completed = subprocess.run(
            ["ssh", remote, remote_command],
            input=json.dumps(request, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=max(int(timeout_seconds) + 60, 120),
            check=False,
        )
        if completed.returncode != 0:
            return {
                "status": "blocked",
                "runtimeIdentityStatus": "UNVERIFIED",
                "runtimeIdentity": "",
                "results": [
                    {
                        "jobKey": _text(job.get("jobKey")),
                        "returncode": completed.returncode,
                        "dps": None,
                        "gear": {},
                        "warnings": [],
                        "stderr": (completed.stderr or "")[-4000:],
                    }
                    for job in batch_jobs
                ],
            }
        try:
            batch = json.loads(completed.stdout)
        except json.JSONDecodeError:
            batch = {
                "status": "blocked",
                "runtimeIdentityStatus": "UNVERIFIED",
                "runtimeIdentity": "",
                "results": [],
            }
        return batch

    batches: list[dict[str, Any] | None] = [None] * len(job_batches)
    completed_count = 0
    with ThreadPoolExecutor(max_workers=min(int(workers), len(job_batches) or 1)) as pool:
        futures = {
            pool.submit(run_batch, batch_jobs): index
            for index, batch_jobs in enumerate(job_batches)
        }
        for future in as_completed(futures):
            index = futures[future]
            batches[index] = future.result()
            completed_count += 1
            if progress_callback is not None:
                progress_callback(completed_count, len(job_batches))
    return [batch for batch in batches if batch is not None]


__all__ = [
    "S2_EQUIPMENT_LIBRARY_SIMC_MATRIX_SCHEMA_REVISION",
    "assemble_s2_equipment_library_simc_matrix_report",
    "build_s2_equipment_library_simc_matrix_plan",
    "execute_s2_equipment_library_simc_batches",
    "parse_simc_runtime_identity",
    "rebind_s2_equipment_library_simc_matrix_report",
    "validate_s2_enhancement_probe_result",
    "validate_s2_item_probe_result",
]

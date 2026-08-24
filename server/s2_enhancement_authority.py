"""Exact-first authority for Midnight Season 2 item enhancements.

This module joins the already-captured official item/DB2 facts with the
existing crafted compatibility edges.  It is intentionally not a source
membership builder: gems, enchants, crafted secondary stats, and embellish-
ments modify an item that already belongs to one of the four product sources.
Unknown semantic tokens stay visible and blocked instead of being inferred
from names or from a successful SimC invocation.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any


SCHEMA_REVISION = "s2-equipment-library-enhancement-authority-v1"
REPORT_PREFIX = "s2-enhancement-authority:sha256:"

_CRAFTED_STAT_CATEGORY_MAP = {
    "809": ("32", "40"),  # Critical Strike + Versatility
    "810": ("32", "49"),  # Critical Strike + Mastery
    "811": ("40", "49"),  # Versatility + Mastery
    "812": ("32", "36"),  # Critical Strike + Haste
    "813": ("36", "49"),  # Haste + Mastery
    "814": ("36", "40"),  # Haste + Versatility
}
_CRAFTED_SINGLE_STAT_CATEGORY_MAP = {
    "869": "32",  # Flux Cogwheel: Critical Strike
    "870": "49",  # Perfected Cogwheel: Mastery
    "871": "36",  # Greased Cogwheel: Haste
    "872": "40",  # Consistent Cogwheel: Versatility
}
_CRAFTED_SINGLE_STAT_SLOTS = ("head", "wrist", "feet", "main_hand")

# These tokens are the existing SimC serializer vocabulary.  A category not
# listed here must not be guessed from its display name.
_EMBELLISHMENT_CATEGORY_TOKEN_MAP = {
    "854": "lucky_keychain",
    "855": "kinetic_ankle_primers",
    # The official modified-crafting category is the identity owner.  The
    # token is the fixed SimC serializer vocabulary and is validated again by
    # the enhancement matrix; it is not inferred from the display name.
    "857": "m3ddy_travel_sized",
    "769": "arcanoweave_lining",
    "770": "sunfire_silk_lining",
    "805": "darkmoon_sigil_blood",
    "806": "darkmoon_sigil_hunt",
    "807": "darkmoon_sigil_rot",
    "808": "darkmoon_sigil_void",
    "830": "devouring_banding",
    "831": "blessed_pango_charm",
    "832": "primal_spore_binding",
    "856": "b1p_scorcher_of_souls",
    "873": "hu5h_nonchalant_pup",
    "860": "prismatic_focusing_iris",
    "861": "stabilizing_gemstone_bandolier",
    "884": "b0p_curator_of_booms",
    "914": "snakeskin_lining",
    "917": "adorned_fang",
    "918": "polished_ammolite",
    "919": "coiled_snakeeye",
    "920": "hunters_ritual_stone",
}

_PROFESSION_ONLY_CATEGORIES = {
    "815",
    "816",
    "817",
    "818",
    "819",
    "820",
    "821",
}
_TRACK_CURRENCY_CATEGORY_IDS = {"911", "912", "913"}
_TRACK_MATERIAL_CATEGORY_IDS = {"909"}
_GEM_SLOTS = ("head", "neck", "wrist", "waist", "finger1", "finger2")
_ENCHANTABLE_SLOTS = (
    "back",
    "chest",
    "wrist",
    "legs",
    "feet",
    "finger1",
    "finger2",
    "main_hand",
    "off_hand",
)
_ENCHANT_SLOT_MAP = {
    "4897": ("back",),
    "7935": ("legs",),
    "7937": ("legs",),
    "7957": ("chest",),
    "7963": ("feet",),
    "7967": ("finger1", "finger2"),
    "7969": ("finger1", "finger2"),
    "7981": ("main_hand", "off_hand"),
    "7983": ("main_hand", "off_hand"),
    "7985": ("chest",),
    "7987": ("chest",),
    "7993": ("feet",),
    "7997": ("finger1", "finger2"),
    "8013": ("chest",),
    "8019": ("feet",),
    "8025": ("finger1", "finger2"),
    "8027": ("finger1", "finger2"),
    "8039": ("main_hand", "off_hand"),
    "8041": ("main_hand", "off_hand"),
}
_ARMOR_KIT_ENCHANT_IDS = {"8158", "8159", "8163"}
# SpellItemEnchantment owns the armor-kit id, name, and stat effects.  The
# bounded slot/token adapter below only records the fixed runtime's accepted
# serializer compatibility.  It must not be used as a general DB2/game-fact
# importer; the full matrix still has to read the exact enchant back.
_ARMOR_KIT_SERIALIZER_COMPATIBILITY = {
    "8158": {
        "slot": "legs",
        "tokenizedName": "forest_hunters_armor_kit",
        "maskInventoryType": "0x00000080",
        "maskItemSubclass": "0x0000001e",
    },
    "8159": {
        "slot": "legs",
        "tokenizedName": "forest_hunters_armor_kit",
        "maskInventoryType": "0x00000080",
        "maskItemSubclass": "0x0000001e",
    },
    "8163": {
        "slot": "legs",
        "tokenizedName": "blood_knights_armor_kit",
        "maskInventoryType": "0x00000080",
        "maskItemSubclass": "0x0000001e",
    },
}
_MARKUP_PATTERN = re.compile(r"\|A:[^|]+\|a")
_SPELL_DESCRIPTION_PATTERN = re.compile(r"\$@spelldesc(?P<id>[1-9][0-9]*)")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _id(value: Any) -> str:
    text = _text(value)
    return str(int(text)) if text.isdigit() and int(text) > 0 else ""


def _index_official_items(value: Any) -> dict[str, dict[str, Any]]:
    if isinstance(value, Mapping):
        return {
            _id(key): dict(payload)
            for key, payload in value.items()
            if _id(key) and isinstance(payload, Mapping)
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return {
            _id(row.get("id") or row.get("itemId")): dict(row)
            for row in value
            if isinstance(row, Mapping)
            and _id(row.get("id") or row.get("itemId"))
        }
    return {}


def _ref_map(value: Any) -> dict[str, set[str]]:
    if not isinstance(value, Mapping):
        return {}
    return {
        _id(key): {_text(ref) for ref in refs if _text(ref)}
        for key, refs in value.items()
        if _id(key) and isinstance(refs, Sequence) and not isinstance(refs, (str, bytes, bytearray))
    }


def _clean_name(value: Any) -> str:
    return _MARKUP_PATTERN.sub("", _text(value)).strip()


def _crafting_option_spell_facts(
    payload: Mapping[str, Any],
    *,
    spell_rows: Sequence[Mapping[str, Any]],
    spell_effect_rows: Sequence[Mapping[str, Any]],
    spell_refs: Mapping[str, Sequence[str]] | None,
    spell_effect_refs: Mapping[str, Sequence[str]] | None,
) -> list[dict[str, Any]]:
    modified = payload.get("modified_crafting") if isinstance(payload.get("modified_crafting"), Mapping) else {}
    descriptions = [
        _text(modified.get("description")),
        _text(payload.get("description")),
    ]
    spell_ids = sorted(
        {
            match.group("id")
            for description in descriptions
            for match in _SPELL_DESCRIPTION_PATTERN.finditer(description)
        },
        key=int,
    )
    spells_by_id: dict[str, Mapping[str, Any]] = {}
    for row in spell_rows or ():
        if isinstance(row, Mapping) and _id(row.get("ID")):
            spells_by_id.setdefault(_id(row.get("ID")), row)
    effects_by_spell: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in spell_effect_rows or ():
        if isinstance(row, Mapping) and _id(row.get("SpellID")):
            effects_by_spell[_id(row.get("SpellID"))].append(row)
    spell_ref_map = _ref_map(spell_refs)
    effect_ref_map = _ref_map(spell_effect_refs)
    facts: list[dict[str, Any]] = []
    for spell_id in spell_ids:
        spell = spells_by_id.get(spell_id)
        effects = sorted(
            effects_by_spell.get(spell_id, []),
            key=lambda row: int(row.get("EffectIndex") or 0),
        )
        refs = set(spell_ref_map.get(spell_id, set())) | set(effect_ref_map.get(spell_id, set()))
        facts.append(
            {
                "spellId": spell_id,
                "status": "verified" if spell else "UNVERIFIED",
                "reasonCode": None if spell else "CRAFTED_OPTION_SPELL_FACT_MISSING",
                "spell": (
                    {
                        "id": _id(spell.get("ID")),
                        "name": _text(spell.get("Name_lang")),
                        "description": _text(spell.get("Description_lang")),
                        "raw": {
                            key: spell.get(key)
                            for key in ("ID", "Name_lang", "Description_lang")
                            if key in spell
                        },
                    }
                    if spell
                    else None
                ),
                "spellEffects": [
                    {
                        "id": _id(row.get("ID")),
                        "spellId": _id(row.get("SpellID")),
                        "effectIndex": row.get("EffectIndex"),
                        "effect": row.get("Effect"),
                        "effectBasePoints": row.get("EffectBasePointsF"),
                        "effectMiscValue0": row.get("EffectMiscValue_0"),
                        "effectMiscValue1": row.get("EffectMiscValue_1"),
                        "effectTriggerSpell": row.get("EffectTriggerSpell"),
                        "raw": dict(row),
                    }
                    for row in effects
                ],
                "evidenceRefs": sorted(refs),
            }
        )
    return facts


def _official_class_id(payload: Mapping[str, Any]) -> str:
    item_class = payload.get("item_class") if isinstance(payload.get("item_class"), Mapping) else {}
    return _id(item_class.get("id"))


def _official_category_id(payload: Mapping[str, Any]) -> str:
    modified = payload.get("modified_crafting") if isinstance(payload.get("modified_crafting"), Mapping) else {}
    category = modified.get("category") if isinstance(modified.get("category"), Mapping) else {}
    return _id(category.get("id"))


def _official_modified_description(payload: Mapping[str, Any]) -> str:
    modified = payload.get("modified_crafting") if isinstance(payload.get("modified_crafting"), Mapping) else {}
    return _text(modified.get("description")) or _text(payload.get("description"))


def _gem_effect(payload: Mapping[str, Any]) -> str:
    preview = payload.get("preview_item") if isinstance(payload.get("preview_item"), Mapping) else {}
    properties = preview.get("gem_properties") if isinstance(preview.get("gem_properties"), Mapping) else {}
    return _text(properties.get("effect"))


def _option_key(option_type: str, token: str, category_id: str = "") -> str:
    if option_type == "crafted_stats":
        return (
            f"crafted-stats-{'-'.join(token.split('/'))}"
            if token
            else f"crafted-stats-category-{category_id}"
        )
    if option_type == "embellishment":
        return f"embellishment-{token}" if token else f"embellishment-unknown-{category_id}"
    return f"{option_type}-{token}"


def _line_with_option(line: str, option_key: str, option_value: str) -> str:
    left, separator, right = _text(line).partition("=")
    if not separator or not _text(right):
        return ""
    return f"{left}={right},{option_key}={option_value}"


def _record_line(record: Mapping[str, Any]) -> str:
    canonical = record.get("canonicalSimcInput")
    if not isinstance(canonical, Mapping):
        return ""
    return _text(canonical.get("line"))


def _record_status(record: Mapping[str, Any]) -> bool:
    canonical = record.get("canonicalSimcInput")
    return (
        _text(record.get("status")) == "verified"
        and isinstance(canonical, Mapping)
        and _text(canonical.get("status")) == "verified"
        and bool(_record_line(record))
    )


def _relationship_options(
    relationships: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    fields = (
        ("secondaryStatCompatibility", "crafted_stats"),
        ("embellishmentCompatibility", "embellishment"),
        ("enhancementCompatibility", "enhancement"),
    )
    for relationship in relationships:
        if not isinstance(relationship, Mapping):
            continue
        for field, edge_kind in fields:
            edge = relationship.get(field)
            if not isinstance(edge, Mapping):
                continue
            for raw_option in edge.get("options") or []:
                if not isinstance(raw_option, Mapping):
                    continue
                category_id = _id(raw_option.get("categoryId") or raw_option.get("modifiedCraftingCategoryId"))
                item_id = _id(raw_option.get("itemId"))
                currency_id = _id(raw_option.get("currencyTypeId"))
                identity = item_id or currency_id
                if not category_id or not identity:
                    continue
                key = (edge_kind, category_id, identity)
                row = result.setdefault(
                    key,
                    {
                        "kind": _text(raw_option.get("kind")) or ("currency" if currency_id and not item_id else "item"),
                        "categoryId": category_id,
                        "itemId": item_id or None,
                        "currencyTypeId": currency_id or None,
                        "name": _text(raw_option.get("name")),
                        "description": _text(raw_option.get("description")),
                        "evidenceStatus": _text(raw_option.get("evidenceStatus")) or _text(edge.get("status")),
                        "evidenceRefs": set(),
                        "edgeKinds": set(),
                        "recipeIds": set(),
                        "itemSlots": set(),
                    },
                )
                row["edgeKinds"].add(edge_kind)
                row["recipeIds"].add(_text(relationship.get("recipeId")))
                row["itemSlots"].add(_text(relationship.get("itemSlot")))
                row["evidenceRefs"].update(
                    _text(ref)
                    for ref in raw_option.get("evidenceRefs") or []
                    if _text(ref)
                )
                row["evidenceRefs"].update(
                    _text(ref) for ref in edge.get("evidenceRefs") or [] if _text(ref)
                )
    return result


def _normalise_row(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    for key in ("evidenceRefs", "edgeKinds", "recipeIds", "itemSlots"):
        value = normalized.get(key)
        if isinstance(value, set):
            normalized[key] = sorted(value)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            normalized[key] = sorted({_text(item) for item in value if _text(item)})
        else:
            normalized[key] = []
    return normalized


def _base_records(
    variants: Sequence[Mapping[str, Any]],
    templates: Sequence[Mapping[str, Any]],
    item_definitions: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    static_socket_counts = {
        _id(row.get("itemId")): int(
            (row.get("db2StaticFacts") or {}).get("socketCount") or 0
        )
        for row in item_definitions
        if isinstance(row, Mapping)
        and _id(row.get("itemId"))
        and isinstance(row.get("db2StaticFacts"), Mapping)
    }
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for raw_record in [*variants, *templates]:
        if not isinstance(raw_record, Mapping) or not _record_status(raw_record):
            continue
        item_id = _id(raw_record.get("itemId"))
        slot = _text(raw_record.get("itemSlot"))
        line = _record_line(raw_record)
        key = (item_id, slot, line)
        if not item_id or not slot or not line or key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "itemId": item_id,
                "slot": slot,
                "line": line,
                "variantKey": _text(raw_record.get("variantKey")),
                "socketCount": static_socket_counts.get(item_id, 0),
                "selectionContract": raw_record.get("selectionContract")
                if isinstance(raw_record.get("selectionContract"), Mapping)
                else {},
            }
        )
    records.sort(key=lambda row: (row["slot"], row["itemId"], row["variantKey"], row["line"]))
    return records, static_socket_counts


def _compatible_template(
    records: Sequence[Mapping[str, Any]],
    *,
    option_type: str,
    category_id: str,
    applicable_slots: Sequence[str],
) -> Mapping[str, Any] | None:
    allowed = set(applicable_slots)
    for record in records:
        if allowed and _text(record.get("slot")) not in allowed:
            continue
        contract = record.get("selectionContract") if isinstance(record.get("selectionContract"), Mapping) else {}
        contract_key = "secondaryStats" if option_type == "crafted_stats" else option_type
        edge = contract.get(contract_key) if isinstance(contract.get(contract_key), Mapping) else {}
        for option in edge.get("options") or []:
            if isinstance(option, Mapping) and _id(option.get("categoryId")) == category_id:
                return record
    return None


def _selection(
    option: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    *,
    option_type: str,
    category_id: str = "",
) -> dict[str, Any]:
    option_key = _text(option.get("optionKey"))
    value_map = option.get("simcOptions") if isinstance(option.get("simcOptions"), Mapping) else {}
    field, value = next(iter(value_map.items()), ("", ""))
    allowed_slots = option.get("applicableSlots") if isinstance(option.get("applicableSlots"), list) else []
    chosen: Mapping[str, Any] | None = None
    if option_type == "gem":
        chosen = next((row for row in records if int(row.get("socketCount") or 0) > 0), None)
    elif option_type == "enchant":
        chosen = next(
            (row for row in records if _text(row.get("slot")) in set(allowed_slots)),
            None,
        )
    else:
        chosen = _compatible_template(
            records,
            option_type=option_type,
            category_id=category_id,
            applicable_slots=allowed_slots,
        )
    if chosen is None:
        return {
            "optionKey": option_key,
            "optionType": option_type,
            "status": "blocked",
            "reasonCode": "ENHANCEMENT_CANONICAL_SELECTION_UNVERIFIED",
            "canonicalSimcInput": {"status": "blocked", "line": ""},
            "evidenceRefs": list(option.get("sourceRefs") or []),
        }
    line = _line_with_option(_text(chosen.get("line")), field, _text(value))
    status = "verified" if line else "blocked"
    return {
        "optionKey": option_key,
        "optionType": option_type,
        "status": status,
        "reasonCode": None if status == "verified" else "ENHANCEMENT_CANONICAL_SELECTION_UNVERIFIED",
        "baseItemId": _text(chosen.get("itemId")),
        "baseVariantKey": _text(chosen.get("variantKey")),
        "slot": _text(chosen.get("slot")),
        "canonicalSimcInput": {
            "status": status,
            "line": line,
            "itemId": _text(chosen.get("itemId")),
            "slot": _text(chosen.get("slot")),
            "simcOptions": {field: _text(value)} if field else {},
        },
        "evidenceRefs": sorted(
            set(option.get("sourceRefs") or [])
            | {
                _text(ref)
                for ref in chosen.get("evidenceRefs") or []
                if _text(ref)
            }
        ),
    }


def _sort_options(options: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (_canonical(option) for option in options),
        key=lambda row: (_text(row.get("optionType")), _text(row.get("optionKey"))),
    )


def build_s2_enhancement_authority(
    *,
    crafted_relationships: Sequence[Mapping[str, Any]] = (),
    variants: Sequence[Mapping[str, Any]] = (),
    crafted_variant_templates: Sequence[Mapping[str, Any]] = (),
    item_definitions: Sequence[Mapping[str, Any]] = (),
    official_option_items: Any = (),
    enchant_rows: Sequence[Mapping[str, Any]] = (),
    official_option_refs: Mapping[str, Sequence[str]] | None = None,
    enchant_refs: Mapping[str, Sequence[str]] | None = None,
    spell_rows: Sequence[Mapping[str, Any]] = (),
    spell_effect_rows: Sequence[Mapping[str, Any]] = (),
    spell_refs: Mapping[str, Sequence[str]] | None = None,
    spell_effect_refs: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Build normalized enhancement options and one canonical probe selection.

    ``official_option_items`` is deliberately separate from the four-source
    item identity map: optional reagents and gems never create a new source
    membership.  ``enchant_rows`` are bounded exact SpellItemEnchantment rows.
    """

    official = _index_official_items(official_option_items)
    official_refs = _ref_map(official_option_refs)
    enchant_ref_map = _ref_map(enchant_refs)
    relationship_map = _relationship_options(
        [row for row in crafted_relationships if isinstance(row, Mapping)]
    )
    records, _socket_counts = _base_records(
        [row for row in variants if isinstance(row, Mapping)],
        [row for row in crafted_variant_templates if isinstance(row, Mapping)],
        [row for row in item_definitions if isinstance(row, Mapping)],
    )

    options: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    track_currencies: list[dict[str, Any]] = []
    blocker_codes: set[str] = set()

    # Gems are official item facts, not crafted compatibility edges.  The
    # capture is intentionally restricted to the 20 authorized S2 seed IDs
    # by the capture manifest, and the gem_properties effect is required.
    for item_id, payload in sorted(official.items(), key=lambda row: int(row[0])):
        if _official_class_id(payload) != "3":
            continue
        effect = _gem_effect(payload)
        option = {
            "optionId": f"s2-gem-{item_id}",
            "optionKey": _option_key("gem", item_id),
            "optionType": "gem",
            "token": item_id,
            "itemId": item_id,
            "itemIds": [item_id],
            "name": _text(payload.get("name")),
            "statSummary": effect,
            "status": "verified" if effect else "UNVERIFIED",
            "reasonCode": None if effect else "OFFICIAL_GEM_EFFECT_MISSING",
            "applicableSlots": list(_GEM_SLOTS),
            "simcOptions": {"gem_id": item_id},
            "sourceRefs": sorted(official_refs.get(item_id, set())),
            "payload": {
                "quality": (payload.get("quality") or {}).get("type")
                if isinstance(payload.get("quality"), Mapping)
                else None,
                "itemLevel": payload.get("level"),
                "gemEffect": effect,
            },
        }
        options.append(option)
        if option["status"] != "verified":
            blocker_codes.add(str(option["reasonCode"]))

    # All crafted identities come from the compatibility edges.  Keep the
    # category edge even when the public SimC token is not yet known.
    # Rank-one/rank-two optional reagents share one SimC semantic identity.
    # Group by category and kind, then retain every official item ID on the
    # normalized option instead of emitting two selectable options.
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for raw_key, raw_row in relationship_map.items():
        _edge_kind, category_id, identity = raw_key
        row = _normalise_row(raw_row)
        grouped[(category_id, _text(row.get("kind")) or "item")].append(row)

    for (category_id, grouped_kind), rows in sorted(
        grouped.items(), key=lambda value: (int(value[0][0]), value[0][1])
    ):
        row = rows[0]
        identities = sorted(
            {
                _text(item.get("itemId")) or _text(item.get("currencyTypeId"))
                for item in rows
                if _text(item.get("itemId")) or _text(item.get("currencyTypeId"))
            },
            key=lambda value: int(value) if value.isdigit() else value,
        )
        identity = identities[0] if identities else ""
        merged_refs = set().union(*(set(item.get("evidenceRefs") or []) for item in rows))
        edge_kinds = set().union(*(set(item.get("edgeKinds") or []) for item in rows))
        recipe_ids = set().union(*(set(item.get("recipeIds") or []) for item in rows))
        item_slots = {slot for item in rows for slot in item.get("itemSlots") or [] if slot}
        kind = grouped_kind or _text(row.get("kind")) or "item"

        if kind == "currency" or category_id in _TRACK_CURRENCY_CATEGORY_IDS:
            track_currencies.append(
                {
                    "categoryId": category_id,
                    "currencyTypeId": _text(row.get("currencyTypeId")) or identity,
                    "name": _text(row.get("name")),
                    "description": _text(row.get("description")),
                    "status": _text(row.get("evidenceStatus")) or "UNVERIFIED",
                    "evidenceRefs": sorted(merged_refs),
                    "recipeIds": sorted(recipe_ids, key=lambda value: int(value) if value.isdigit() else value),
                    "role": "crafted_quality_or_upgrade_track",
                }
            )
            continue

        if category_id in _TRACK_MATERIAL_CATEGORY_IDS:
            exclusions.append(
                {
                    "categoryId": category_id,
                    "itemId": identity,
                    "reasonCode": "CRAFTING_TRACK_MATERIAL_NOT_DIRECT_ENHANCEMENT",
                    "evidenceRefs": sorted(merged_refs),
                }
            )
            continue
        if category_id in _PROFESSION_ONLY_CATEGORIES:
            exclusions.append(
                {
                    "categoryId": category_id,
                    "itemId": identity,
                    "reasonCode": "OUT_OF_SCOPE_PROFESSION_ONLY_CRAFTING_STAT",
                    "evidenceRefs": sorted(merged_refs),
                }
            )
            continue

        payload = official.get(identity, {})
        official_category_id = _official_category_id(payload)
        official_spell_facts = _crafting_option_spell_facts(
            payload,
            spell_rows=spell_rows,
            spell_effect_rows=spell_effect_rows,
            spell_refs=spell_refs,
            spell_effect_refs=spell_effect_refs,
        )
        spell_evidence_refs = {
            _text(ref)
            for fact in official_spell_facts
            for ref in fact.get("evidenceRefs") or []
            if _text(ref)
        }
        if official_category_id and official_category_id != category_id:
            blocker_codes.add("CRAFTED_OPTION_CATEGORY_ID_CONFLICT")
            status = "blocked"
            reason = "CRAFTED_OPTION_CATEGORY_ID_CONFLICT"
        elif _text(row.get("evidenceStatus")) not in {"verified", ""}:
            status = "UNVERIFIED"
            reason = "CRAFTED_OPTION_COMPATIBILITY_UNVERIFIED"
        else:
            status = "verified"
            reason = None

        option_type = "crafted_stats" if category_id in _CRAFTED_STAT_CATEGORY_MAP or category_id in _CRAFTED_SINGLE_STAT_CATEGORY_MAP else "embellishment"
        token = ""
        simc_options: dict[str, str] = {}
        stat_summary = ""
        if option_type == "crafted_stats":
            stat_ids = _CRAFTED_STAT_CATEGORY_MAP.get(category_id)
            if stat_ids is None and category_id in _CRAFTED_SINGLE_STAT_CATEGORY_MAP:
                stat_ids = (_CRAFTED_SINGLE_STAT_CATEGORY_MAP[category_id],)
            if stat_ids:
                token = "/".join(sorted(stat_ids, key=int))
                simc_options = {"crafted_stats": token}
                stat_summary = token
                if _official_modified_description(payload):
                    # The category map is explicit; the API description is
                    # retained as a field-level corroborating fact.
                    pass
                else:
                    status = "UNVERIFIED"
                    reason = "OFFICIAL_CRAFTED_STAT_DESCRIPTION_MISSING"
            else:
                status = "UNVERIFIED"
                reason = "CRAFTED_SECONDARY_STAT_SEMANTICS_UNVERIFIED"
                blocker_codes.add(reason)
        else:
            token = _EMBELLISHMENT_CATEGORY_TOKEN_MAP.get(category_id, "")
            if token:
                simc_options = {"embellishment": token}
            else:
                status = "UNVERIFIED"
                reason = "CRAFTED_EMBELLISHMENT_SIMC_TOKEN_UNVERIFIED"
                blocker_codes.add(reason)

        if not payload:
            status = "UNVERIFIED"
            reason = "OFFICIAL_CRAFTED_OPTION_ITEM_MISSING"
            blocker_codes.add(reason)
        if status != "verified" and reason:
            blocker_codes.add(reason)

        option_key = _option_key(option_type, token, category_id)
        option = {
            "optionId": f"s2-{option_type}-{token or category_id}",
            "optionKey": option_key,
            "optionType": option_type,
            "token": token or None,
            "categoryId": category_id,
            "itemId": identity,
            "itemIds": sorted(
                {
                    _text(item.get("itemId"))
                    for item in rows
                    if _text(item.get("itemId"))
                },
                key=int,
            ),
            "name": _text(payload.get("name")) or _text(row.get("name")),
            "statSummary": stat_summary,
            "status": status,
            "reasonCode": reason,
            "applicableSlots": sorted(
                set(_CRAFTED_SINGLE_STAT_SLOTS)
                if category_id in _CRAFTED_SINGLE_STAT_CATEGORY_MAP
                else item_slots
            ),
            "simcOptions": simc_options,
            "simcSerializerCompatibility": {
                "status": "observed" if token else "UNVERIFIED",
                "authority": "fixed_simc_runtime.embellishment_data",
                "token": token or None,
            },
            "sourceRefs": sorted(
                merged_refs | official_refs.get(identity, set()) | spell_evidence_refs
            ),
            "recipeIds": sorted(recipe_ids, key=lambda value: int(value) if value.isdigit() else value),
            "edgeKinds": sorted(edge_kinds),
            "payload": {
                "officialCategoryId": official_category_id or None,
                "officialDescription": _official_modified_description(payload),
                "officialModifiedCrafting": payload.get("modified_crafting")
                if isinstance(payload.get("modified_crafting"), Mapping)
                else {},
                "officialSpellFacts": official_spell_facts,
            },
        }
        options.append(option)

    # Exact DB2 enchant rows are an independent bounded input.  Armor-kit
    # identity/effect/name remain owned by SpellItemEnchantment.  The fixed
    # serializer compatibility below is deliberately separate: it only tells
    # the canonical SimC writer which equipment slot can carry the id.
    seen_enchants: set[str] = set()
    for raw_row in enchant_rows or []:
        if not isinstance(raw_row, Mapping):
            continue
        enchant_id = _id(raw_row.get("ID"))
        if not enchant_id or enchant_id in seen_enchants:
            continue
        seen_enchants.add(enchant_id)
        name = _clean_name(raw_row.get("Name_lang"))
        slots = list(_ENCHANT_SLOT_MAP.get(enchant_id, ()))
        status = "verified" if slots else "UNVERIFIED"
        reason = None if slots else "ENCHANT_SLOT_SEMANTICS_UNVERIFIED"
        serializer_compatibility = None
        if enchant_id in _ARMOR_KIT_ENCHANT_IDS:
            serializer_compatibility = _ARMOR_KIT_SERIALIZER_COMPATIBILITY.get(enchant_id)
            if serializer_compatibility:
                slots = [_text(serializer_compatibility["slot"])]
                status = "verified"
                reason = None
            else:
                status = "UNVERIFIED"
                reason = "ENCHANT_ARMOR_KIT_SLOT_SEMANTICS_UNVERIFIED"
                slots = []
        if status != "verified" and reason:
            blocker_codes.add(reason)
        options.append(
            {
                "optionId": f"s2-enchant-{enchant_id}",
                "optionKey": f"enchant-{enchant_id}",
                "optionType": "enchant",
                "token": enchant_id,
                "enchantId": enchant_id,
                "name": name or f"Enchant {enchant_id}",
                "status": status,
                "reasonCode": reason,
                "applicableSlots": slots,
                "simcOptions": {"enchant_id": enchant_id},
                "simcSerializerCompatibility": {
                    "status": "observed" if serializer_compatibility else "UNVERIFIED",
                    "authority": "fixed_simc_runtime.permanent_enchant",
                    **(serializer_compatibility or {}),
                },
                "sourceRefs": sorted(enchant_ref_map.get(enchant_id, set())),
                "db2Fact": {
                    key: raw_row.get(key)
                    for key in (
                        "ID",
                        "Effect_0",
                        "Effect_1",
                        "Effect_2",
                        "EffectArg_0",
                        "EffectArg_1",
                        "EffectArg_2",
                        "ItemLevelMin",
                        "ItemLevelMax",
                        "RequiredSkillID",
                        "RequiredSkillRank",
                    )
                    if key in raw_row
                },
            }
        )
    if not enchant_rows:
        blocker_codes.add("OFFICIAL_DB2_ENCHANT_FACTS_MISSING")

    options = _sort_options(options)
    selections: list[dict[str, Any]] = []
    for option in options:
        option_type = _text(option.get("optionType"))
        if option.get("status") != "verified":
            selection = {
                "optionKey": _text(option.get("optionKey")),
                "optionType": option_type,
                "status": "blocked",
                "reasonCode": _text(option.get("reasonCode")) or "ENHANCEMENT_OPTION_UNVERIFIED",
                "canonicalSimcInput": {"status": "blocked", "line": ""},
                "evidenceRefs": list(option.get("sourceRefs") or []),
            }
        elif option_type == "enchant" and not option.get("applicableSlots"):
            selection = {
                "optionKey": _text(option.get("optionKey")),
                "optionType": option_type,
                "status": "blocked",
                "reasonCode": "ENHANCEMENT_CANONICAL_SELECTION_UNVERIFIED",
                "canonicalSimcInput": {"status": "blocked", "line": ""},
                "evidenceRefs": list(option.get("sourceRefs") or []),
            }
        else:
            selection = _selection(
                option,
                records,
                option_type=option_type,
                category_id=_text(option.get("categoryId")),
            )
        if selection.get("status") != "verified":
            blocker_codes.add("ENHANCEMENT_CANONICAL_SELECTION_UNVERIFIED")
        selections.append(selection)

    canonical_selection_by_key = {
        _text(row.get("optionKey")): row for row in selections if _text(row.get("optionKey"))
    }
    for option in options:
        selection = canonical_selection_by_key.get(_text(option.get("optionKey")))
        option["canonicalSelectionStatus"] = _text(selection.get("status")) if selection else "blocked"

    if not official:
        blocker_codes.add("OFFICIAL_ENHANCEMENT_ITEM_CAPTURE_MISSING")
    if not options:
        blocker_codes.add("S2_ENHANCEMENT_OPTION_CATALOG_EMPTY")

    coverage = {
        "optionCount": len(options),
        "verifiedOptionCount": sum(row.get("status") == "verified" for row in options),
        "unverifiedOptionCount": sum(row.get("status") == "UNVERIFIED" for row in options),
        "blockedOptionCount": sum(row.get("status") == "blocked" for row in options),
        "canonicalSelectionCount": len(selections),
        "canonicalSelectionVerifiedCount": sum(row.get("status") == "verified" for row in selections),
        "canonicalSelectionBlockedCount": sum(row.get("status") != "verified" for row in selections),
        "gemOptionCount": sum(row.get("optionType") == "gem" for row in options),
        "enchantOptionCount": sum(row.get("optionType") == "enchant" for row in options),
        "craftedStatOptionCount": sum(row.get("optionType") == "crafted_stats" for row in options),
        "embellishmentOptionCount": sum(row.get("optionType") == "embellishment" for row in options),
        "trackCurrencyCount": len(track_currencies),
        "exclusionCount": len(exclusions),
    }
    status = "verified" if not blocker_codes else "partial"
    report = {
        "schemaRevision": SCHEMA_REVISION,
        "status": status,
        "options": options,
        "canonicalSelections": sorted(
            (_canonical(row) for row in selections),
            key=lambda row: _text(row.get("optionKey")),
        ),
        "trackCurrencies": sorted(
            (_canonical(row) for row in track_currencies),
            key=lambda row: (_text(row.get("categoryId")), _text(row.get("currencyTypeId"))),
        ),
        "exclusions": sorted(
            (_canonical(row) for row in exclusions),
            key=lambda row: (_text(row.get("categoryId")), _text(row.get("itemId")), _text(row.get("reasonCode"))),
        ),
        "coverage": coverage,
        "blockerCodes": sorted(blocker_codes),
        "fieldOwners": {
            "gemIdentity": "official_api_item.preview_item.gem_properties",
            "enchantIdentity": "official_client_db2.SpellItemEnchantment",
            "craftedOptionCompatibility": "official_api_modified_crafting_plus_bounded_db2_compatibility_edges",
            "craftedStatSemantics": "official_api_crafted_option_description_or_explicit_UNVERIFIED",
            "craftedOptionSpellSemantics": "bounded_official_client_db2.Spell_and_SpellEffect_or_explicit_UNVERIFIED",
            "simcSerializer": "existing_simc_options_vocabulary_plus_fixed_runtime_readback",
            "trackCurrency": "official_client_db2_or_official_crafting_category_currency_edge",
        },
        "authorityBoundary": "enhancements_modify_in_scope_items; they never create a fifth source membership",
    }
    report["reportId"] = REPORT_PREFIX + hashlib.sha256(
        _canonical_bytes(
            {
                key: value
                for key, value in report.items()
                if key != "reportId"
            }
        )
    ).hexdigest()
    return report


__all__ = ["SCHEMA_REVISION", "build_s2_enhancement_authority"]

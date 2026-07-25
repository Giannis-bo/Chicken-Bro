#!/usr/bin/env python3
"""Public read models derived from one active observed-build TemplateSet."""

from __future__ import annotations

import copy
from typing import Any

try:
    from .community_template_import import (
        COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION,
    )
    from .observed_build_registry import slot_key
    from .websim_payload import (
        class_label,
        hero_tree_label,
        scenario_title,
        spec_label,
    )
except ImportError:
    from community_template_import import (
        COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION,
    )
    from observed_build_registry import slot_key
    from websim_payload import (
        class_label,
        hero_tree_label,
        scenario_title,
        spec_label,
    )


def _canonical(value: Any) -> Any:
    return copy.deepcopy(value)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _active_parts(record: Any) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    if not isinstance(record, dict):
        raise ValueError("active record must be an object")
    active = record.get("active")
    entry = record.get("entry")
    snapshot = record.get("snapshot")
    projection = record.get("projection")
    if not all(
        isinstance(value, dict)
        for value in (active, entry, snapshot, projection)
    ):
        raise ValueError("active record is incomplete")
    slot = snapshot.get("slot") if isinstance(snapshot.get("slot"), dict) else {}
    source = (
        snapshot.get("source")
        if isinstance(snapshot.get("source"), dict)
        else {}
    )
    source_identity = _text(source.get("sourceIdentity"))
    if (
        entry.get("status") not in {"verified", "stale_lkg"}
        or projection.get("status") != "verified"
        or projection.get("importable") is not True
        or entry.get("slotKey") != slot_key(slot)
        or projection.get("slotKey") != entry.get("slotKey")
        or entry.get("snapshotId") != snapshot.get("snapshotId")
        or projection.get("snapshotId") != snapshot.get("snapshotId")
        or entry.get("projectionId") != projection.get("projectionId")
        or not source_identity
        or entry.get("sourceIdentity") != source_identity
        or projection.get("sourceIdentity") != source_identity
        or not _text(active.get("templateSetId"))
        or not isinstance(active.get("generation"), int)
        or isinstance(active.get("generation"), bool)
        or active.get("generation") < 1
    ):
        raise ValueError("active record identity is inconsistent")
    return active, entry, snapshot, projection


def _common(record: dict[str, Any]) -> dict[str, Any]:
    active, entry, snapshot, projection = _active_parts(record)
    slot = snapshot["slot"]
    source = snapshot["source"]
    evidence = (
        snapshot.get("rankingEvidence")
        if isinstance(snapshot.get("rankingEvidence"), dict)
        else {}
    )
    stale = entry.get("status") == "stale_lkg"
    player_name = _text(source.get("character"))
    hero_label = hero_tree_label(slot.get("heroKey"))
    title = " · ".join(
        value
        for value in (player_name, hero_label)
        if value
    )
    return {
        "id": projection["projectionId"],
        "title": title,
        "name": title,
        "templateSetId": active["templateSetId"],
        "pointerGeneration": active["generation"],
        "snapshotId": snapshot["snapshotId"],
        "sourceIdentity": source["sourceIdentity"],
        "classKey": slot["classKey"],
        "classLabel": class_label(slot["classKey"]),
        "specKey": slot["specKey"],
        "specLabel": spec_label(slot["specKey"]),
        "heroKey": slot["heroKey"],
        "heroLabel": hero_label,
        "scenarioKey": slot["scenarioKey"],
        "scenarioTitle": scenario_title(slot["scenarioKey"]),
        "sourceKey": "raiderio_observed_profile",
        "sourceName": "Raider.IO 真实玩家",
        "sourceUrl": source["profileUrl"],
        "sourceStatus": "synced",
        "playerId": player_name,
        "playerName": player_name,
        "serverName": source["realm"],
        "region": source["region"],
        "mplusScore": evidence.get("score", 0),
        "mplusRank": evidence.get("rank", 0),
        "maxKeyLevel": evidence.get("maxKeyLevel", 0),
        "sampleCount": 1,
        "scanRunId": active["templateSetId"],
        "analysisWindow": snapshot.get("sourceRevision"),
        "status": "verified",
        "slotStatus": entry["status"],
        "freshnessStatus": "stale" if stale else "fresh",
        "isStale": stale,
        "sourceRevision": snapshot.get("sourceRevision"),
    }


def _talent_template(record: dict[str, Any]) -> dict[str, Any]:
    _active, entry, snapshot, projection = _active_parts(record)
    common = _common(record)
    talent = (
        projection.get("talentProjection")
        if isinstance(projection.get("talentProjection"), dict)
        else {}
    )
    observation = (
        snapshot.get("talentObservation")
        if isinstance(snapshot.get("talentObservation"), dict)
        else {}
    )
    source = snapshot["source"]
    return {
        **common,
        "flowLabel": "真实玩家",
        "talentState": _canonical(talent.get("talentState") or {}),
        "rawImportCode": _text(
            talent.get("rawImportCode")
            or observation.get("rawImportCode")
        ),
        "websimExportCode": _text(talent.get("websimExportCode")),
        "signature": _text(talent.get("signature")),
        "canApplyVisual": True,
        "canUseInSimc": True,
        "payload": {
            "raiderio": {
                "sourceIdentity": source["sourceIdentity"],
                "profileUrl": source["profileUrl"],
                "characterName": source["character"],
                "realm": source["realm"],
                "realmSlug": source["realm"],
                "region": source["region"],
                "heroKey": snapshot["slot"]["heroKey"],
                "heroSubTreeId": observation.get("heroSubTreeId"),
                "loadoutSpecId": observation.get("loadoutSpecId"),
                "loadout": _canonical(observation.get("loadout") or []),
                "selector": _canonical(observation.get("selector") or {}),
                "source": observation.get("source")
                or "profile_current",
            },
            "observedBuild": {
                "templateSetId": common["templateSetId"],
                "pointerGeneration": common["pointerGeneration"],
                "snapshotId": common["snapshotId"],
                "sourceRevision": common["sourceRevision"],
                "slotStatus": entry["status"],
                "problem": _canonical(entry.get("problem") or {}),
            },
        },
        "sourceRefs": [
            {
                "id": projection["projectionId"],
                "sourceKey": "raiderio_observed_profile",
                "sourceName": "Raider.IO 真实玩家",
                "sourceUrl": source["profileUrl"],
                "sourceStatus": "synced",
                "status": "verified",
                "sampleCount": 1,
                "maxKeyLevel": common["maxKeyLevel"],
                "rankingEvidence": _canonical(
                    snapshot.get("rankingEvidence") or {}
                ),
            }
        ],
    }


def _projected_gear_items(
    snapshot: dict[str, Any],
    projection: dict[str, Any],
) -> list[dict[str, Any]]:
    observation = (
        snapshot.get("gearObservation")
        if isinstance(snapshot.get("gearObservation"), dict)
        else {}
    )
    gear = (
        projection.get("gearProjection")
        if isinstance(projection.get("gearProjection"), dict)
        else {}
    )
    observed_by_slot = {
        _text(item.get("slot")): item
        for item in observation.get("gearItems") or []
        if isinstance(item, dict) and _text(item.get("slot"))
    }
    projected_items = [
        item
        for item in gear.get("gearItems") or []
        if isinstance(item, dict)
    ]
    output = []
    for projected in projected_items:
        slot = _text(projected.get("slot"))
        if not slot:
            continue
        item = {
            **_canonical(observed_by_slot.get(slot) or {}),
            **_canonical(projected),
            "slot": slot,
            "itemId": _text(projected.get("itemId")),
            "variantKey": _text(projected.get("variantKey")),
        }
        if "itemLevel" in item and "ilevel" not in item:
            item["ilevel"] = item["itemLevel"]
        output.append(item)
    return sorted(output, key=lambda item: item["slot"])


def _has_complete_exact_gear_identity(
    gear: dict[str, Any],
    gear_items: list[dict[str, Any]],
) -> bool:
    intent = gear.get("selectionIntent") if isinstance(gear, dict) else {}
    slots = intent.get("slots") if isinstance(intent, dict) else {}
    if not isinstance(slots, dict) or not slots:
        return False
    items_by_slot = {
        _text(item.get("slot")): item
        for item in gear_items
        if isinstance(item, dict) and _text(item.get("slot"))
    }
    if set(slots) != set(items_by_slot):
        return False
    return all(
        isinstance(selection, dict)
        and _text(selection.get("itemId"))
        and _text(selection.get("variantKey"))
        and _text(items_by_slot[slot].get("itemId"))
        == _text(selection.get("itemId"))
        and _text(items_by_slot[slot].get("variantKey"))
        == _text(selection.get("variantKey"))
        for slot, selection in slots.items()
    )


def _gear_template(record: dict[str, Any]) -> dict[str, Any]:
    _active, entry, snapshot, projection = _active_parts(record)
    common = _common(record)
    gear = (
        projection.get("gearProjection")
        if isinstance(projection.get("gearProjection"), dict)
        else {}
    )
    gear_items = _projected_gear_items(snapshot, projection)
    can_apply_gear = _has_complete_exact_gear_identity(gear, gear_items)
    return {
        **common,
        "status": "complete" if can_apply_gear else "partial",
        "projectionStatus": "verified",
        "talentWinnerId": projection["projectionId"],
        "gearProjectionMode": "talent_winner",
        "profileHash": snapshot.get("profileHash"),
        "gearHash": snapshot.get("gearHash"),
        "signature": snapshot.get("gearHash"),
        "gearItems": gear_items,
        "selectionIntent": _canonical(
            gear.get("selectionIntent") or {}
        ),
        "enhancementBySlot": _canonical(
            gear.get("enhancementBySlot") or {}
        ),
        "resolvedGearSignature": _text(
            gear.get("resolvedGearSignature")
        ),
        "readySlotCount": len(gear_items),
        "missingSlots": [] if can_apply_gear else sorted(
            _text(slot)
            for slot, selection in (gear.get("selectionIntent") or {}).get("slots", {}).items()
            if not isinstance(selection, dict)
            or not _text(selection.get("variantKey"))
        ),
        "canApplyGear": can_apply_gear,
        "payload": {
            "sourceIdentity": common["sourceIdentity"],
            "profileHash": snapshot.get("profileHash"),
            "gearHash": snapshot.get("gearHash"),
            "character": {
                "name": common["playerName"],
                "region": common["region"],
                "realmSlug": common["serverName"],
            },
            "observedBuild": {
                "templateSetId": common["templateSetId"],
                "pointerGeneration": common["pointerGeneration"],
                "snapshotId": common["snapshotId"],
                "sourceRevision": common["sourceRevision"],
                "slotStatus": entry["status"],
                "problem": _canonical(entry.get("problem") or {}),
            }
        },
    }


def talent_templates_from_active_records(
    records: Any,
    hero_key: str = "",
) -> list[dict[str, Any]]:
    """Project exactly one active observed talent template per requested Hero."""

    requested_hero = _text(hero_key)
    templates = [
        _talent_template(record)
        for record in records or []
        if isinstance(record, dict)
    ]
    if requested_hero:
        templates = [
            template
            for template in templates
            if template.get("heroKey") == requested_hero
        ]
    return sorted(
        templates,
        key=lambda value: (
            _text(value.get("classKey")),
            _text(value.get("specKey")),
            _text(value.get("heroKey")),
            _text(value.get("id")),
        ),
    )


def gear_templates_from_active_records(
    records: Any,
) -> list[dict[str, Any]]:
    """Project the two active Hero-bound players for one specialization."""

    return sorted(
        [
            template
            for record in records or []
            if isinstance(record, dict)
            and (template := _gear_template(record)).get("canApplyGear") is True
        ],
        key=lambda value: (
            _text(value.get("classKey")),
            _text(value.get("specKey")),
            _text(value.get("heroKey")),
            _text(value.get("id")),
        ),
    )


def gear_import_source_from_active_record(
    record: dict[str, Any],
) -> dict[str, Any]:
    """Build the exact internal import source for one active projection."""

    _active, _entry, snapshot, projection = _active_parts(record)
    template = _gear_template(record)
    if template.get("canApplyGear") is not True:
        raise ValueError("active gear import exact variant is incomplete")
    intent = template.get("selectionIntent")
    intent = intent if isinstance(intent, dict) else {}
    items_by_slot = {
        _text(item.get("slot")): item
        for item in template.get("gearItems") or []
        if isinstance(item, dict) and _text(item.get("slot"))
    }
    imported = {}
    for slot, selection in sorted((intent.get("slots") or {}).items()):
        if not isinstance(selection, dict):
            continue
        observed = _canonical(items_by_slot.get(slot) or {})
        if not observed:
            continue
        imported[slot] = {
            **observed,
            "slot": slot,
            "itemId": _text(selection.get("itemId")),
            "variantKey": _text(selection.get("variantKey")),
        }
    if not imported or set(imported) != set(intent.get("slots") or {}):
        raise ValueError("active gear import identity is incomplete")
    return {
        "contractRevision": COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION,
        "status": "verified",
        "template": {
            "id": projection["projectionId"],
            "classKey": template["classKey"],
            "specKey": template["specKey"],
            "sourceKey": "raiderio_observed_profile",
            "name": template["name"],
            "profileHash": snapshot.get("profileHash"),
            "gearHash": snapshot.get("gearHash"),
            "sourceIdentity": snapshot["source"]["sourceIdentity"],
        },
        "importedGearBySlot": imported,
        "visibleOptionsBySlot": {},
        "selectionIntent": _canonical(intent),
        "problems": [],
    }


__all__ = (
    "gear_import_source_from_active_record",
    "gear_templates_from_active_records",
    "talent_templates_from_active_records",
)

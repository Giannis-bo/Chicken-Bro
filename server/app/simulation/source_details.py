"""Verified character metadata and fight-specific Warcraft Logs inputs."""

import re
from collections.abc import Mapping
from urllib.parse import quote, unquote

from server.app.simulation.snapshots import sha256_json


def text(value):
    return str(value or "").strip()


def key(value):
    return text(value).casefold().replace("'", "").replace(" ", "-")


def token(value):
    return key(value).replace("-", "_")


def positive(value):
    return type(value) is int and value > 0


def read_character_details(fetch, region, realm, name, expected):
    """Use a fixed provider endpoint; verify identity before consuming fields."""
    endpoint = "https://raider.io/api/characters/" + "/".join(
        quote(text(part), safe="-_.~") for part in (region, realm, name)
    )
    try:
        raw = fetch(endpoint)
    except Exception:
        return None
    details = raw.get("characterDetails") if isinstance(raw, Mapping) else None
    character = details.get("character") if isinstance(details, Mapping) else None
    if not isinstance(character, Mapping):
        return None
    for field in ("region", "realm", "class", "race", "spec"):
        if not isinstance(character.get(field), Mapping):
            return None
    if (
        key(character.get("name")) != key(name)
        or key(character["region"].get("slug")) != key(region)
        or key(character["realm"].get("slug")) != key(realm)
        or key(unquote(text(character.get("path")))) != key(f"/characters/{region}/{realm}/{name}")
        or token(character["class"].get("slug")) != token(expected.get("classKey"))
        or not positive(character.get("level"))
    ):
        return None
    aliases = {key(character["realm"].get(k)) for k in ("slug", "name", "altName", "altSlug")}
    if key(expected.get("realm")) not in aliases or key(expected.get("name")) != key(name):
        return None
    if key(expected.get("region")) != key(region):
        return None
    if expected.get("raceKey") and token(expected["raceKey"]) != token(character["race"].get("slug")):
        return None
    return character, {
        "provider": "raiderio", "endpoint": endpoint,
        "characterPath": character["path"], "rawSha256": sha256_json(raw),
    }


def matching_talent_export(tree, details, spec_key):
    """Accept a current export only when every recorded selection agrees.

    Midnight apex nodes log separate entries; the export stores their total
    purchased ranks. Choice nodes still require the exact selected entry.
    """
    loadout = details.get("talentLoadout")
    if not isinstance(loadout, Mapping) or token(details["spec"].get("slug")) != token(spec_key):
        return ""
    code = text(loadout.get("loadoutText"))
    nodes = loadout.get("nodes")
    if (not re.fullmatch(r"[A-Za-z0-9+/=_-]{4,512}", code)
            or not isinstance(tree, list) or not 1 <= len(tree) <= 256
            or not isinstance(nodes, list) or not 1 <= len(nodes) <= 256):
        return ""
    recorded = {}
    for entry in tree:
        if not isinstance(entry, Mapping) or not all(positive(entry.get(k)) for k in ("id", "rank", "nodeID")):
            return ""
        selections = recorded.setdefault(entry["nodeID"], {})
        if entry["id"] in selections:
            return ""
        selections[entry["id"]] = entry["rank"]
    selected = set()
    for selection in nodes:
        if not isinstance(selection, Mapping):
            return ""
        rank = selection.get("rank")
        if rank == 0 and type(rank) is int:
            continue
        node = selection.get("node")
        if not positive(rank) or not isinstance(node, Mapping) or not positive(node.get("id")):
            return ""
        node_id = node["id"]
        entries = node.get("entries")
        index = selection.get("entryIndex")
        if (node_id in selected or not isinstance(entries, list)
                or type(index) is not int or not 0 <= index < len(entries)):
            return ""
        selected.add(node_id)
        actual = recorded.get(node_id, {})
        if not all(isinstance(e, Mapping) and positive(e.get("id")) and positive(e.get("maxRanks")) for e in entries):
            return ""
        if node.get("type") == 1 and all(e.get("type") == 13 for e in entries):
            # Apex entries accumulate in source order; verify each component.
            remaining = rank
            expected = {}
            last_index = None
            for i, entry in enumerate(entries):
                spent = min(remaining, entry["maxRanks"])
                if spent:
                    expected[entry["id"]] = spent
                    last_index = i
                remaining -= spent
            if remaining or index != last_index or actual != expected:
                return ""
        elif actual != {entries[index]["id"]: rank} or rank > entries[index]["maxRanks"]:
            return ""
    return code if selected == set(recorded) else ""


WCL_SLOTS = {
    0: "head", 1: "neck", 2: "shoulder", 4: "chest", 5: "waist",
    6: "legs", 7: "feet", 8: "wrist", 9: "hands", 10: "finger1",
    11: "finger2", 12: "trinket1", 13: "trinket2", 14: "back",
    15: "main_hand", 16: "off_hand",
}


def combatant_input(report, fight_id, actor_id):
    events = report.get("events")
    data = events.get("data") if isinstance(events, Mapping) else None
    if not isinstance(data, list) or len(data) != 1 or events.get("nextPageTimestamp"):
        return None
    event = data[0]
    if (not isinstance(event, Mapping) or event.get("type") != "combatantinfo"
            or event.get("fight") != fight_id or event.get("sourceID") != actor_id):
        return None
    gear = event.get("gear")
    if not isinstance(gear, list) or len(gear) != 18:
        return None
    items, unequipped = {}, []
    for index, slot in WCL_SLOTS.items():
        item = gear[index]
        if not isinstance(item, Mapping):
            return None
        if type(item.get("id")) is int and item["id"] == 0:
            if slot == "off_hand":
                unequipped.append(slot)
            continue
        if not positive(item.get("id")) or not positive(item.get("itemLevel")):
            return None
        gems = item.get("gems", [])
        if not isinstance(gems, list) or any(not isinstance(g, Mapping) or not positive(g.get("id")) for g in gems):
            return None
        # In combatant events omitted optional fields mean no enchant/gem/bonus.
        items[slot] = {
            "itemId": item["id"], "itemLevel": item["itemLevel"],
            "bonusIds": item.get("bonusIDs", []),
            "gems": [g["id"] for g in gems], "enchant": item.get("permanentEnchant"),
        }
    return {"gear": items, "gearState": {"unequippedSlots": unequipped}}, event

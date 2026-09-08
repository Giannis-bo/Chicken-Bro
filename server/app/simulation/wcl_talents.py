"""Reconstruct recorded Midnight talents using versioned engine trait metadata.

The export is the Blizzard v2 little-endian bit stream (zero tree hash), as
consumed by SimulationCraft. Entry order comes from the pinned engine catalog;
never sort choices by entry id, and never substitute a current character build.
"""
import json
import re
from functools import lru_cache
from pathlib import Path
from collections.abc import Mapping

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


@lru_cache(maxsize=1)
def _catalog():
    raw = json.loads((Path(__file__).parent / "data" / "traits-12.1.0.json").read_text())
    return raw, [dict(zip(raw["columns"], row)) for row in raw["rows"]]


def reconstruct_fight_talents(tree, spec_id, details, spec_key):
    """Return (export, provenance), or None for unsupported/incomplete inputs.

    This catalog supports fully allocated level-90 12.1 builds. Lower levels
    and other versions retain the existing exact-current-export path.
    """
    if not isinstance(details, Mapping) or type(spec_id) is not int:
        return None
    klass = details.get("class", {})
    if (not isinstance(klass, Mapping)
            or type(klass.get("id")) is not int or details.get("level") != 90
            or not isinstance(tree, list) or not 1 <= len(tree) <= 256):
        return None
    try:
        catalog, all_traits = _catalog()
    except (OSError, ValueError):
        return None
    if catalog["specializations"].get(str(spec_id)) != spec_key:
        return None
    traits = [t for t in all_traits if t["classId"] == klass["id"]]
    by_id = {t["entryId"]: t for t in traits}
    chosen = {}
    nodes = {}
    for t in traits:
        nodes.setdefault(t["nodeId"], []).append(t)
    for entry in tree:
        if (not isinstance(entry, Mapping)
                or any(type(entry.get(k)) is not int or entry[k] <= 0 for k in ("id", "rank", "nodeID"))):
            return None
        t = by_id.get(entry["id"])
        if (t is None or entry["id"] in chosen or t["nodeId"] != entry["nodeID"]
                or entry["rank"] > t["maxRanks"]
                or (any(t["specs"]) and spec_id not in t["specs"])):
            return None
        chosen[entry["id"]] = entry["rank"]
    selectors = [by_id[e] for e in chosen if by_id[e]["tree"] == 4]
    if len(selectors) != 1:
        return None
    hero = selectors[0]["subTreeId"]
    if not hero:
        return None
    budgets = {1: 0, 2: 0, 3: 0, 4: 0}
    for t in traits:
        granted = spec_id in t["starterSpecs"] or (
            t["tree"] == 3 and t["subTreeId"] == hero and t["row"] == 1 and t["col"] == 1)
        rank = chosen.get(t["entryId"], 0)
        if granted and not rank:
            return None
        if not rank:
            continue
        if t["tree"] not in budgets or (t["tree"] == 3 and t["subTreeId"] != hero):
            return None
        budgets[t["tree"]] += rank - int(granted)
    # Full level-90 allocation, excluding baseline/free points. Reject truncated
    # logs rather than silently filling missing selections with defaults.
    if budgets != {1: 34, 2: 34, 3: 14, 4: 1}:
        return None
    bits = []
    def put(width, value):
        bits.extend((value >> i) & 1 for i in range(width))
    put(8, 2)
    put(16, spec_id)
    put(128, 0)
    for node_id in sorted(nodes):
        entries = nodes[node_id]
        selected = [(i, t, chosen[t["entryId"]]) for i, t in enumerate(entries) if t["entryId"] in chosen]
        put(1, bool(selected))
        if not selected:
            continue
        tiered = entries[0]["nodeType"] == 1
        if tiered:
            rank = sum(r for _, _, r in selected)
            maximum = sum(t["maxRanks"] for t in entries)
            remaining = rank
            for t in entries:
                spent = min(remaining, t["maxRanks"])
                if chosen.get(t["entryId"], 0) != spent:
                    return None
                remaining -= spent
            granted = False
            index = 0
        else:
            if len(selected) != 1:
                return None
            index, t, rank = selected[0]
            maximum = t["maxRanks"]
            granted = spec_id in t["starterSpecs"] or (
                t["tree"] == 3 and t["row"] == 1 and t["col"] == 1)
        put(1, rank > int(granted))
        if rank <= int(granted):
            continue
        put(1, rank != maximum)
        if rank != maximum:
            if rank > 63:
                return None
            put(6, rank)
        choice = entries[0]["nodeType"] in (2, 3)
        put(1, choice)
        if choice:
            if index > 3:
                return None
            put(2, index)
    code = "".join(_ALPHABET[sum(bit << i for i, bit in enumerate(bits[p:p+6]))]
                   for p in range(0, len(bits), 6))
    return code, {
        "method": "recorded-entries-to-blizzard-v2", "entryCount": len(chosen),
        "specId": spec_id, "heroSubTreeId": hero, "gameBuild": catalog["build"],
        "catalogRuntimeRevision": catalog["revision"], "catalogSourceSha256": catalog["sourceSha256"],
    }


def talent_catalog_matches_runtime(provenance, runtime_revision):
    """Zero-hash reconstructed exports must use their pinned node ordering."""
    if not isinstance(provenance, Mapping):
        return False
    if "wclTalentReconstruction" not in provenance:
        return True
    proof = provenance["wclTalentReconstruction"]
    match = re.fullmatch(r"simc:managed:([0-9a-f]{40}):[0-9a-f]{64}", runtime_revision or "")
    return (isinstance(proof, Mapping) and match is not None
            and proof.get("catalogRuntimeRevision") == match.group(1))

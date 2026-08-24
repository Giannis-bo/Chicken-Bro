"""Classify whether an official M+ item graph belongs to Midnight Season 2.

The official Journal membership list can contain item identities from a
returning dungeon's older seasons.  This adapter makes the item-level scope
decision from the bounded official-client DB2 graph only:

* a complete graph with a current S2 M+ track group is included;
* a complete graph with only historical/non-S2 branches is explicitly
  excluded; and
* a missing or incomplete graph remains ``UNVERIFIED``.

This module does not infer track semantics from SimC, item level, item name,
or a similar item.  A DB2 ``ItemBonusTree`` row with no child nodes is treated
as an official empty tree, which is different from a referenced tree for
which no tree fact was captured.  An exact, captured ``ItemXBonusTree`` query
with zero rows is also retained as a verified empty graph: this is the bounded
case for an official item that has one static identity and no upgrade-tree
relationship at all.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any


_DEFAULT_MPLUS_CONTEXT_VALUES = frozenset({"16", "33", "34", "87"})
_SCOPE_UNVERIFIED = "MYTHIC_PLUS_ITEM_S2_SCOPE_UNVERIFIED"
_HISTORY_EXCLUDED = "OUT_OF_SCOPE_NON_S2_MPLUS_ITEM_VARIANT_GRAPH"
ADAPTER_REVISION = "s2-mythic-plus-item-scope-v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _row_key(row: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _row_refs(
    row: Mapping[str, Any],
    *,
    table: str,
    refs: Mapping[tuple[str, str], Sequence[str]],
) -> set[str]:
    return {
        _text(value)
        for value in refs.get((table, _row_key(row)), [])
        if _text(value)
    }


def _index(
    rows: Mapping[str, Sequence[Mapping[str, Any]]],
    table: str,
    field: str,
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw_row in rows.get(table, []):
        if not isinstance(raw_row, Mapping):
            continue
        value = _text(raw_row.get(field))
        if value and value != "0":
            result[value].append(dict(raw_row))
    return result


def _base_result(item_id: str) -> dict[str, Any]:
    return {
        "status": "UNVERIFIED",
        "includeInMythicPlusMembership": False,
        "reasonCode": _SCOPE_UNVERIFIED,
        "authority": (
            "official_client_db2.ItemXBonusTree_plus_ItemBonusTreeNode_plus_"
            "ItemBonusListGroup"
        ),
        "adapterRevision": ADAPTER_REVISION,
        "itemId": item_id,
        "graphStatus": "missing",
        "rootItemBonusTreeIds": [],
        "reachableTreeIds": [],
        "emptyTreeIds": [],
        "missingTreeFactIds": [],
        "missingTreeNodeIds": [],
        "missingBonusListIds": [],
        "missingBonusListGroupIds": [],
        "missingBonusListGroupEntryIds": [],
        "missingSelectorIds": [],
        "observedGroupIds": [],
        "s2TrackGroupIds": [],
        "currentS2TrackGroupIds": [],
        "observedItemContextValues": [],
        "evidenceRefs": [],
        "graphReasonCodes": [],
    }


def classify_mythic_plus_item_scope(
    item_id: str,
    *,
    db2_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    db2_refs: Mapping[tuple[str, str], Sequence[str]],
    s2_track_group_ids: Sequence[str],
    current_item_context_values: Sequence[str] = tuple(_DEFAULT_MPLUS_CONTEXT_VALUES),
) -> dict[str, Any]:
    """Classify one M+ item identity against the official S2 variant graph."""

    normalized_item_id = _text(item_id)
    result = _base_result(normalized_item_id)
    s2_groups = {_text(value) for value in s2_track_group_ids if _text(value)}
    current_contexts = {
        _text(value) for value in current_item_context_values if _text(value)
    }

    root_rows = [
        dict(row)
        for row in db2_rows.get("ItemXBonusTree", [])
        if isinstance(row, Mapping) and _text(row.get("ItemID")) == normalized_item_id
    ]
    root_ids = sorted(
        {
            _text(row.get("ItemBonusTreeID"))
            for row in root_rows
            if _text(row.get("ItemBonusTreeID"))
            and _text(row.get("ItemBonusTreeID")) != "0"
        },
        key=lambda value: int(value) if value.isdigit() else value,
    )
    result["rootItemBonusTreeIds"] = root_ids
    evidence_refs: set[str] = set()
    for row in root_rows:
        evidence_refs.update(_row_refs(row, table="ItemXBonusTree", refs=db2_refs))

    if not root_rows:
        empty_query_refs = db2_refs.get(
            ("ItemXBonusTree", f"__query__:ItemID:{normalized_item_id}"),
            (),
        )
        if empty_query_refs:
            result.update(
                {
                    "status": "verified",
                    "includeInMythicPlusMembership": True,
                    "reasonCode": None,
                    "graphStatus": "empty",
                    "graphReasonCodes": [
                        "MYTHIC_PLUS_ITEM_VARIANT_GRAPH_EMPTY_STATIC_IDENTITY"
                    ],
                    "evidenceRefs": sorted(
                        {
                            *evidence_refs,
                            *{
                                _text(value)
                                for value in empty_query_refs
                                if _text(value)
                            },
                        }
                    ),
                }
            )
            return result
        result["graphReasonCodes"] = ["MYTHIC_PLUS_ITEM_VARIANT_GRAPH_MISSING"]
        result["evidenceRefs"] = sorted(evidence_refs)
        return result

    if len(root_ids) != len(root_rows):
        result["graphReasonCodes"] = ["MYTHIC_PLUS_ITEM_VARIANT_GRAPH_MISSING"]
        result["evidenceRefs"] = sorted(evidence_refs)
        return result

    tree_facts = _index(db2_rows, "ItemBonusTree", "ID")
    nodes_by_tree = _index(db2_rows, "ItemBonusTreeNode", "ParentItemBonusTreeID")
    group_facts = _index(db2_rows, "ItemBonusListGroup", "ID")
    group_entries = _index(
        db2_rows, "ItemBonusListGroupEntry", "ItemBonusListGroupID"
    )
    bonus_lists = _index(db2_rows, "ItemBonusList", "ID")
    selectors = _index(db2_rows, "ItemLevelSelector", "ID")

    reachable_tree_ids: set[str] = set()
    empty_tree_ids: set[str] = set()
    missing_tree_fact_ids: set[str] = set()
    missing_tree_node_ids: set[str] = set()
    missing_bonus_list_ids: set[str] = set()
    missing_group_ids: set[str] = set()
    missing_group_entry_ids: set[str] = set()
    missing_selector_ids: set[str] = set()
    observed_group_ids: set[str] = set()
    current_s2_group_ids: set[str] = set()
    observed_contexts: set[str] = set()
    graph_reason_codes: set[str] = set()
    active_paths: set[tuple[str, ...]] = set()
    pending: list[tuple[str, tuple[str, ...]]] = [
        (tree_id, tuple()) for tree_id in root_ids
    ]

    while pending:
        tree_id, path = pending.pop()
        if tree_id in path:
            graph_reason_codes.add("MYTHIC_PLUS_ITEM_VARIANT_GRAPH_CYCLE")
            continue
        if tree_id in reachable_tree_ids:
            continue
        reachable_tree_ids.add(tree_id)

        fact_rows = tree_facts.get(tree_id, [])
        for fact in fact_rows:
            evidence_refs.update(_row_refs(fact, table="ItemBonusTree", refs=db2_refs))
        if len(fact_rows) != 1:
            missing_tree_fact_ids.add(tree_id)
            graph_reason_codes.add("MYTHIC_PLUS_ITEM_BONUS_TREE_FACT_UNVERIFIED")
            continue

        nodes = nodes_by_tree.get(tree_id, [])
        for node in nodes:
            evidence_refs.update(
                _row_refs(node, table="ItemBonusTreeNode", refs=db2_refs)
            )
        if not nodes:
            # A root with no children cannot establish an item variant graph.
            # A non-root shared tree with an exact ItemBonusTree fact can be
            # an intentional empty branch (the legacy shared tree 296 is the
            # observed example), which is different from a missing capture.
            if tree_id in root_ids:
                missing_tree_node_ids.add(tree_id)
                graph_reason_codes.add(
                    "MYTHIC_PLUS_ITEM_VARIANT_GRAPH_UNVERIFIED"
                )
            else:
                empty_tree_ids.add(tree_id)
            continue

        for node in nodes:
            context = _text(node.get("ItemContext")) or "0"
            observed_contexts.add(context)
            child_tree_id = _text(node.get("ChildItemBonusTreeID"))
            if child_tree_id and child_tree_id != "0":
                pending.append((child_tree_id, (*path, tree_id)))
                continue

            direct_bonus_list_id = _text(node.get("ChildItemBonusListID"))
            group_id = _text(node.get("ChildItemBonusListGroupID"))
            selector_id = _text(node.get("ChildItemLevelSelectorID"))
            if direct_bonus_list_id and direct_bonus_list_id != "0":
                if len(bonus_lists.get(direct_bonus_list_id, [])) != 1:
                    missing_bonus_list_ids.add(direct_bonus_list_id)
                    graph_reason_codes.add(
                        "MYTHIC_PLUS_ITEM_BONUS_LIST_FACT_UNVERIFIED"
                    )
                continue

            if group_id and group_id != "0":
                observed_group_ids.add(group_id)
                if context in current_contexts and group_id in s2_groups:
                    current_s2_group_ids.add(group_id)
                if len(group_facts.get(group_id, [])) != 1:
                    missing_group_ids.add(group_id)
                    graph_reason_codes.add(
                        "MYTHIC_PLUS_ITEM_BONUS_LIST_GROUP_FACT_UNVERIFIED"
                    )
                entries = group_entries.get(group_id, [])
                if not entries:
                    missing_group_entry_ids.add(group_id)
                    graph_reason_codes.add(
                        "MYTHIC_PLUS_ITEM_BONUS_LIST_GROUP_ENTRY_UNVERIFIED"
                    )
                for entry in entries:
                    evidence_refs.update(
                        _row_refs(
                            entry,
                            table="ItemBonusListGroupEntry",
                            refs=db2_refs,
                        )
                    )
                    entry_id = _text(entry.get("ID"))
                    entry_bonus_list_id = _text(entry.get("ItemBonusListID"))
                    if not entry_bonus_list_id or entry_bonus_list_id == "0":
                        missing_group_entry_ids.add(entry_id or group_id)
                        graph_reason_codes.add(
                            "MYTHIC_PLUS_ITEM_BONUS_LIST_GROUP_ENTRY_UNVERIFIED"
                        )
                    elif len(bonus_lists.get(entry_bonus_list_id, [])) != 1:
                        missing_bonus_list_ids.add(entry_bonus_list_id)
                        graph_reason_codes.add(
                            "MYTHIC_PLUS_ITEM_BONUS_LIST_FACT_UNVERIFIED"
                        )
                    entry_selector_id = _text(entry.get("ItemLevelSelectorID"))
                    if (
                        entry_selector_id
                        and entry_selector_id != "0"
                        and len(selectors.get(entry_selector_id, [])) != 1
                    ):
                        missing_selector_ids.add(entry_selector_id)
                        graph_reason_codes.add(
                            "MYTHIC_PLUS_ITEM_LEVEL_SELECTOR_UNVERIFIED"
                        )
                continue

            if selector_id and selector_id != "0":
                if len(selectors.get(selector_id, [])) != 1:
                    missing_selector_ids.add(selector_id)
                    graph_reason_codes.add(
                        "MYTHIC_PLUS_ITEM_LEVEL_SELECTOR_UNVERIFIED"
                    )
                continue

            # A non-child, non-list node has no public terminal choice in the
            # captured graph.  Keep the item unresolved rather than treating
            # it as an empty historical branch.
            missing_tree_node_ids.add(_text(node.get("ID")) or tree_id)
            graph_reason_codes.add("MYTHIC_PLUS_ITEM_VARIANT_GRAPH_UNVERIFIED")

    result.update(
        {
            "reachableTreeIds": sorted(reachable_tree_ids, key=int),
            "emptyTreeIds": sorted(empty_tree_ids, key=int),
            "missingTreeFactIds": sorted(missing_tree_fact_ids, key=int),
            "missingTreeNodeIds": sorted(missing_tree_node_ids, key=int),
            "missingBonusListIds": sorted(missing_bonus_list_ids, key=int),
            "missingBonusListGroupIds": sorted(missing_group_ids, key=int),
            "missingBonusListGroupEntryIds": sorted(
                missing_group_entry_ids,
                key=lambda value: int(value) if value.isdigit() else value,
            ),
            "missingSelectorIds": sorted(missing_selector_ids, key=int),
            "observedGroupIds": sorted(observed_group_ids, key=int),
            "s2TrackGroupIds": sorted(observed_group_ids & s2_groups, key=int),
            "currentS2TrackGroupIds": sorted(current_s2_group_ids, key=int),
            "observedItemContextValues": sorted(observed_contexts, key=int),
            "evidenceRefs": sorted(evidence_refs),
            "graphReasonCodes": sorted(graph_reason_codes),
        }
    )

    incomplete = bool(
        missing_tree_fact_ids
        or missing_tree_node_ids
        or missing_bonus_list_ids
        or missing_group_ids
        or missing_group_entry_ids
        or missing_selector_ids
        or graph_reason_codes
    )
    if incomplete:
        result["graphStatus"] = "incomplete"
        return result

    result["graphStatus"] = "complete"
    if current_s2_group_ids:
        result.update(
            {
                "status": "verified",
                "includeInMythicPlusMembership": True,
                "reasonCode": None,
            }
        )
    else:
        result.update(
            {
                "status": "excluded",
                "includeInMythicPlusMembership": False,
                "reasonCode": _HISTORY_EXCLUDED,
            }
        )
    return result


__all__ = ["ADAPTER_REVISION", "classify_mythic_plus_item_scope"]

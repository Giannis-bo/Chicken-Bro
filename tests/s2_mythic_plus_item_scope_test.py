import unittest

from server.s2_mythic_plus_item_scope import classify_mythic_plus_item_scope


def _base_rows(item_id: str, *, group_id: str | None = None) -> dict[str, list[dict]]:
    node = {
        "ID": 10,
        "ParentItemBonusTreeID": 1,
        "ItemContext": 16,
        "ChildItemBonusTreeID": 0,
        "ChildItemBonusListID": 0 if group_id else 900,
        "ChildItemBonusListGroupID": group_id or 0,
        "ChildItemLevelSelectorID": 0,
    }
    rows = {
        "ItemXBonusTree": [{"ID": 20, "ItemBonusTreeID": 1, "ItemID": item_id}],
        "ItemBonusTree": [{"ID": 1, "Flags": 0, "InventoryTypeSlotMask": 0}],
        "ItemBonusTreeNode": [node],
        "ItemBonusList": [{"ID": 900}],
    }
    if group_id:
        rows.update(
            {
                "ItemBonusListGroup": [{"ID": int(group_id)}],
                "ItemBonusListGroupEntry": [
                    {
                        "ID": 901,
                        "ItemBonusListGroupID": int(group_id),
                        "ItemBonusListID": 900,
                        "SequenceValue": 1,
                    }
                ],
            }
        )
    return rows


class S2MythicPlusItemScopeTest(unittest.TestCase):
    def test_current_s2_track_graph_is_included(self):
        result = classify_mythic_plus_item_scope(
            "100",
            db2_rows=_base_rows("100", group_id="616"),
            db2_refs={},
            s2_track_group_ids={"614", "615", "616", "617", "618"},
        )

        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["includeInMythicPlusMembership"])
        self.assertEqual(result["s2TrackGroupIds"], ["616"])
        self.assertEqual(result["graphStatus"], "complete")

    def test_complete_history_only_graph_is_explicitly_excluded(self):
        result = classify_mythic_plus_item_scope(
            "101",
            db2_rows=_base_rows("101", group_id="608"),
            db2_refs={},
            s2_track_group_ids={"614", "615", "616", "617", "618"},
        )

        self.assertEqual(result["status"], "excluded")
        self.assertFalse(result["includeInMythicPlusMembership"])
        self.assertEqual(
            result["reasonCode"],
            "OUT_OF_SCOPE_NON_S2_MPLUS_ITEM_VARIANT_GRAPH",
        )

    def test_missing_item_graph_stays_unverified(self):
        result = classify_mythic_plus_item_scope(
            "102",
            db2_rows={},
            db2_refs={},
            s2_track_group_ids={"614", "615", "616", "617", "618"},
        )

        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertFalse(result["includeInMythicPlusMembership"])
        self.assertEqual(result["reasonCode"], "MYTHIC_PLUS_ITEM_S2_SCOPE_UNVERIFIED")
        self.assertEqual(result["graphStatus"], "missing")

    def test_exact_empty_item_graph_is_verified_static_identity(self):
        result = classify_mythic_plus_item_scope(
            "1021",
            db2_rows={},
            db2_refs={
                (
                    "ItemXBonusTree",
                    "__query__:ItemID:1021",
                ): ["db2-query:variant-source/empty.json#/rows"],
            },
            s2_track_group_ids={"614", "615", "616", "617", "618"},
        )

        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["includeInMythicPlusMembership"])
        self.assertEqual(result["graphStatus"], "empty")
        self.assertIn(
            "MYTHIC_PLUS_ITEM_VARIANT_GRAPH_EMPTY_STATIC_IDENTITY",
            result["graphReasonCodes"],
        )
        self.assertEqual(
            result["evidenceRefs"],
            ["db2-query:variant-source/empty.json#/rows"],
        )

    def test_missing_tree_nodes_stay_unverified(self):
        result = classify_mythic_plus_item_scope(
            "103",
            db2_rows={
                "ItemXBonusTree": [
                    {"ID": 20, "ItemBonusTreeID": 1, "ItemID": "103"}
                ],
                "ItemBonusTree": [
                    {"ID": 1, "Flags": 0, "InventoryTypeSlotMask": 0}
                ],
                "ItemBonusTreeNode": [],
            },
            db2_refs={},
            s2_track_group_ids={"614", "615", "616", "617", "618"},
        )

        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertEqual(result["graphStatus"], "incomplete")
        self.assertIn("1", result["missingTreeNodeIds"])

    def test_official_empty_tree_is_complete_history_evidence(self):
        result = classify_mythic_plus_item_scope(
            "104",
            db2_rows={
                "ItemXBonusTree": [
                    {"ID": 20, "ItemBonusTreeID": 296, "ItemID": "104"}
                ],
                "ItemBonusTree": [
                    {"ID": 296, "Flags": 0, "InventoryTypeSlotMask": 0},
                    {"ID": 297, "Flags": 0, "InventoryTypeSlotMask": 0},
                ],
                "ItemBonusTreeNode": [
                    {
                        "ID": 21,
                        "ParentItemBonusTreeID": 296,
                        "ChildItemBonusTreeID": 297,
                    }
                ],
            },
            db2_refs={},
            s2_track_group_ids={"614", "615", "616", "617", "618"},
        )

        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["graphStatus"], "complete")
        self.assertEqual(result["emptyTreeIds"], ["297"])


if __name__ == "__main__":
    unittest.main()

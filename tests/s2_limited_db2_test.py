import copy
import json
import unittest
from pathlib import Path

from server.s2_limited_db2 import (
    LimitedDb2Error,
    build_bounded_db2_query_plan,
    capture_bounded_db2_evidence,
    collect_s2_official_db2_targets,
    expand_bounded_db2_query_plan,
    project_db2_row,
    validate_db2_field_allowlist,
)


ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_PATH = (
    ROOT
    / "server"
    / "data"
    / "midnight-season-2"
    / "db2-field-allowlist-v1.json"
)


def load_allowlist():
    return json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))


class S2LimitedDb2Test(unittest.TestCase):
    def test_allowlist_is_bounded_to_s2_missing_fact_fields(self):
        allowlist = validate_db2_field_allowlist(load_allowlist())

        self.assertEqual(allowlist["seasonKey"], "midnight-season-2")
        self.assertEqual(allowlist["clientBuild"], "12.1.0.69299")
        self.assertEqual(
            set(allowlist["tables"]),
            {
                "Item",
                "ItemSparse",
                "ItemXBonusTree",
                "ItemBonusTree",
                "ItemBonusTreeNode",
                "ItemBonus",
                "ItemConversion",
                "ItemConversionEntry",
                "ItemEffect",
                "ItemXItemEffect",
                "SkillLineAbility",
                "SpellEffect",
                "SpellReagents",
                "SpellItemEnchantment",
                "CraftingData",
                "CraftingDataItemQuality",
                "CraftingDifficulty",
                "CraftingDifficultyQuality",
                "CraftingQuality",
                "ModifiedCraftingSpellSlot",
                "ModifiedCraftingReagentSlot",
                "ModifiedCraftingCategory",
                "ModifiedCraftingReagentItem",
                "ModifiedCraftingItem",
                "CraftingReagentQuality",
                "CurrencyTypes",
                "MythicPlusSeason",
                "DisplaySeason",
                "MythicPlusSeasonRewardLevels",
                "MythicPlusSeasonKeyFloor",
                "ItemBonusSeason",
                "ItemBonusSeasonBonusListGroup",
                "ItemBonusListGroupEntry",
                "ItemExtendedCost",
                "ItemBonusList",
                "ItemBonusListLevelDelta",
                "ItemBonusListGroup",
                "ItemGroupIlvlScalingEntry",
                "PlayerCondition",
                "Spell",
                "SpellName",
                "ItemScalingConfig",
                "ItemOffsetCurve",
                "Curve",
                "CurvePoint",
                "ItemLevelSelector",
                "ItemLevelSelectorQuality",
                "ItemLevelSelectorQualitySet",
                "MapDifficulty",
                "ItemContextPickerEntry",
                "ItemCreationContext",
                "JournalEncounterItem",
            },
        )
        self.assertEqual(
            allowlist["queryContract"]["permittedFilterOperators"],
            ["exact"],
        )
        self.assertFalse(allowlist["queryContract"]["allowFullTableCsv"])
        for table, spec in allowlist["tables"].items():
            self.assertNotIn("*", spec["fields"], table)
            self.assertIn(spec["keyField"], spec["fields"], table)
        self.assertIn(
            "Description_lang",
            allowlist["tables"]["ModifiedCraftingReagentItem"]["fields"],
        )
        self.assertEqual(
            allowlist["tables"]["ItemScalingConfig"]["fields"],
            [
                "ID",
                "ItemOffsetCurveID",
                "ItemLevel",
                "RequiredLevel",
                "ItemSquishEraID",
                "Flags",
            ],
        )

    def test_map_difficulty_graph_is_explicit_and_bounded(self):
        allowlist = load_allowlist()
        plan = build_bounded_db2_query_plan(
            targets={"mapIds": ["2987", "3004"]},
            allowlist=allowlist,
        )
        pairs = {
            (row["table"], row["filterField"], row["targetValue"])
            for row in plan
        }
        self.assertIn(("MapDifficulty", "MapID", "2987"), pairs)
        self.assertIn(("MapDifficulty", "MapID", "3004"), pairs)
        self.assertNotIn(("MapDifficulty", "MapID", "0"), pairs)

        expanded = expand_bounded_db2_query_plan(
            plan,
            captured_rows={
                "MapDifficulty": [
                    {"ID": 1, "MapID": 2987, "ItemContextPickerID": 241},
                    {"ID": 2, "MapID": 3004, "ItemContextPickerID": 0},
                ]
            },
            allowlist=allowlist,
        )
        pairs = {
            (row["table"], row["filterField"], row["targetValue"])
            for row in expanded
        }
        self.assertIn(
            ("ItemContextPickerEntry", "ItemContextPickerID", "241"),
            pairs,
        )

    def test_journal_encounter_item_targets_are_derived_from_official_encounters(self):
        allowlist = load_allowlist()
        plan = build_bounded_db2_query_plan(
            targets={"journalEncounterIds": ["2172", "2172", "2849"]},
            allowlist=allowlist,
        )
        self.assertEqual(
            {
                (row["table"], row["filterField"], row["targetValue"])
                for row in plan
                if row["table"] == "JournalEncounterItem"
            },
            {
                ("JournalEncounterItem", "JournalEncounterID", "2172"),
                ("JournalEncounterItem", "JournalEncounterID", "2849"),
            },
        )

    def test_official_capture_collects_journal_encounter_ids(self):
        manifest = {
            "status": "captured",
            "entries": [
                {"path": "/data/wow/journal-encounter/2172"},
                {"path": "/data/wow/journal-encounter/2172"},
                {"path": "/data/wow/item/158344"},
                {"path": "/data/wow/journal-encounter/2849"},
            ],
        }
        targets = collect_s2_official_db2_targets(manifest)
        self.assertEqual(targets["journalEncounterIds"], ["2172", "2849"])

    def test_display_season_is_a_finite_root_for_item_bonus_season_edges(self):
        plan = build_bounded_db2_query_plan(
            targets={"displaySeasonIds": ["37"]},
            allowlist=load_allowlist(),
        )
        self.assertEqual(
            {
                (row["table"], row["filterField"], row["targetValue"])
                for row in plan
            },
            {
                ("DisplaySeason", "ID", "37"),
                ("ItemBonusSeason", "SeasonID", "37"),
                ("MythicPlusSeasonKeyFloor", "DisplaySeasonID", "37"),
            },
        )

    def test_item_creation_context_targets_are_explicit_and_exact(self):
        plan = build_bounded_db2_query_plan(
            targets={"itemContextValues": ["0", "16", "33", "35", "16"]},
            allowlist=load_allowlist(),
        )
        self.assertEqual(
            {
                (row["table"], row["filterField"], row["targetValue"])
                for row in plan
                if row["table"] == "ItemCreationContext"
            },
            {
                ("ItemCreationContext", "ItemContext", "16"),
                ("ItemCreationContext", "ItemContext", "33"),
                ("ItemCreationContext", "ItemContext", "35"),
                ("ItemCreationContext", "ItemContext", "0"),
            },
        )

    def test_enchant_targets_are_explicit_and_exact(self):
        plan = build_bounded_db2_query_plan(
            targets={"enchantIds": ["8013", "8013"]},
            allowlist=load_allowlist(),
        )
        self.assertEqual(
            {
                (row["table"], row["filterField"], row["targetValue"])
                for row in plan
            },
            {
                ("SpellItemEnchantment", "ID", "8013"),
            },
        )

    def test_crafting_option_spell_targets_are_explicit_and_include_effect_rows(self):
        plan = build_bounded_db2_query_plan(
            targets={"spellIds": ["1246308", "1246309"]},
            allowlist=load_allowlist(),
        )
        self.assertEqual(
            {
                (row["table"], row["filterField"], row["targetValue"], row["targetKind"])
                for row in plan
            },
            {
                ("Spell", "ID", "1246308", "explicit_crafting_option_spell_id"),
                ("Spell", "ID", "1246309", "explicit_crafting_option_spell_id"),
                ("SpellEffect", "SpellID", "1246308", "explicit_crafting_option_spell_id"),
                ("SpellEffect", "SpellID", "1246309", "explicit_crafting_option_spell_id"),
            },
        )

    def test_crafting_data_targets_include_quality_rows_by_crafting_data_id(self):
        plan = build_bounded_db2_query_plan(
            targets={"craftingDataIds": ["2556", "2556"]},
            allowlist=load_allowlist(),
        )
        self.assertEqual(
            {
                (row["table"], row["filterField"], row["targetValue"], row["targetKind"])
                for row in plan
            },
            {
                ("CraftingData", "ID", "2556", "explicit_crafting_data_id"),
                (
                    "CraftingDataItemQuality",
                    "CraftingDataID",
                    "2556",
                    "explicit_crafting_data_id",
                ),
            },
        )
    def test_curve_expansion_is_limited_to_scaling_foreign_keys(self):
        initial_plan = build_bounded_db2_query_plan(
            targets={"itemScalingConfigIds": ["184", "302"]},
            allowlist=load_allowlist(),
        )
        expanded = expand_bounded_db2_query_plan(
            initial_plan,
            captured_rows={
                "ItemScalingConfig": [
                    {"ID": 184, "ItemOffsetCurveID": 49, "ItemLevel": 0},
                    {"ID": 302, "ItemOffsetCurveID": 0, "ItemLevel": 266},
                ]
            },
            allowlist=load_allowlist(),
        )
        pairs = {
            (row["table"], row["filterField"], row["targetValue"])
            for row in expanded
        }
        self.assertIn(("ItemOffsetCurve", "ID", "49"), pairs)
        self.assertNotIn(("ItemOffsetCurve", "ID", "0"), pairs)

        expanded = expand_bounded_db2_query_plan(
            expanded,
            captured_rows={
                "ItemOffsetCurve": [{"ID": 49, "CurveID": 92772, "Offset": 6}]
            },
            allowlist=load_allowlist(),
        )
        pairs = {
            (row["table"], row["filterField"], row["targetValue"])
            for row in expanded
        }
        self.assertIn(("Curve", "ID", "92772"), pairs)

        expanded = expand_bounded_db2_query_plan(
            expanded,
            captured_rows={
                "Curve": [{"ID": 92772, "Type": 0, "Flags": 0}]
            },
            allowlist=load_allowlist(),
        )
        pairs = {
            (row["table"], row["filterField"], row["targetValue"])
            for row in expanded
        }
        self.assertIn(("CurvePoint", "CurveID", "92772"), pairs)

    def test_upgrade_group_expansion_keeps_season_and_condition_edges_bounded(self):
        initial_plan = build_bounded_db2_query_plan(
            targets={"itemIds": ["271472"]},
            allowlist=load_allowlist(),
        )
        expanded = expand_bounded_db2_query_plan(
            initial_plan,
            captured_rows={
                "ItemBonusTreeNode": [
                    {
                        "ID": 1,
                        "ParentItemBonusTreeID": 5935,
                        "ChildItemBonusListGroupID": 614,
                    }
                ]
            },
            allowlist=load_allowlist(),
        )
        pairs = {
            (row["table"], row["filterField"], row["targetValue"])
            for row in expanded
        }
        self.assertIn(("ItemBonusListGroup", "ID", "614"), pairs)

        expanded = expand_bounded_db2_query_plan(
            expanded,
            captured_rows={
                "ItemBonusListGroup": [
                    {
                        "ID": 614,
                        "ItemGroupIlvlScalingID": 12,
                        "PlayerConditionID": 143187,
                        "SequenceSpellID": 1298569,
                    }
                ]
            },
            allowlist=load_allowlist(),
        )
        pairs = {
            (row["table"], row["filterField"], row["targetValue"])
            for row in expanded
        }
        self.assertIn(
            ("ItemGroupIlvlScalingEntry", "ItemGroupIlvlScalingID", "12"),
            pairs,
        )
        self.assertIn(("PlayerCondition", "ID", "143187"), pairs)
        self.assertIn(("Spell", "ID", "1298569"), pairs)

        expanded = expand_bounded_db2_query_plan(
            expanded,
            captured_rows={"Spell": [{"ID": 1298569}]},
            allowlist=load_allowlist(),
        )
        pairs = {
            (row["table"], row["filterField"], row["targetValue"])
            for row in expanded
        }
        self.assertIn(("SpellName", "ID", "1298569"), pairs)

        expanded = expand_bounded_db2_query_plan(
            expanded,
            captured_rows={
                "ItemGroupIlvlScalingEntry": [
                    {
                        "ID": 45,
                        "ItemGroupIlvlScalingID": 12,
                        "CurrencyTypeID": 3442,
                        "PlayerConditionID": 153623,
                    }
                ]
            },
            allowlist=load_allowlist(),
        )
        pairs = {
            (row["table"], row["filterField"], row["targetValue"])
            for row in expanded
        }
        self.assertIn(("PlayerCondition", "ID", "153623"), pairs)
        self.assertIn(("CurrencyTypes", "ID", "3442"), pairs)

    def test_upgrade_group_entry_expands_only_its_exact_extended_cost(self):
        expanded = expand_bounded_db2_query_plan(
            build_bounded_db2_query_plan(
                targets={"itemBonusListGroupIds": ["614"]},
                allowlist=load_allowlist(),
            ),
            captured_rows={
                "ItemBonusListGroupEntry": [
                    {
                        "ID": 4415,
                        "ItemBonusListGroupID": 614,
                        "ItemBonusListID": 12818,
                        "ItemExtendedCostID": 11457,
                    },
                    {
                        "ID": 4420,
                        "ItemBonusListGroupID": 614,
                        "ItemBonusListID": 12823,
                        "ItemExtendedCostID": 0,
                    },
                ]
            },
            allowlist=load_allowlist(),
        )
        self.assertIn(
            ("ItemExtendedCost", "ID", "11457"),
            {
                (row["table"], row["filterField"], row["targetValue"])
                for row in expanded
            },
        )
        self.assertNotIn(
            ("ItemExtendedCost", "ID", "0"),
            {
                (row["table"], row["filterField"], row["targetValue"])
                for row in expanded
            },
        )

    def test_bonus_list_edges_expand_exact_level_delta_facts(self):
        expanded = expand_bounded_db2_query_plan(
            build_bounded_db2_query_plan(
                targets={"itemBonusTreeIds": [6045]},
                allowlist=load_allowlist(),
            ),
            captured_rows={
                "ItemBonusTreeNode": [
                    {
                        "ID": 1,
                        "ParentItemBonusTreeID": 6045,
                        "ChildItemBonusListID": 13440,
                        "ChildItemBonusTreeID": 0,
                        "ChildItemBonusListGroupID": 0,
                    }
                ]
            },
            allowlist=load_allowlist(),
        )
        pairs = {
            (row["table"], row["filterField"], row["targetValue"])
            for row in expanded
        }
        self.assertIn(("ItemBonusListLevelDelta", "ID", "13440"), pairs)

    def test_upgrade_group_expansion_captures_every_currency_band(self):
        expanded = expand_bounded_db2_query_plan(
            build_bounded_db2_query_plan(
                targets={"itemBonusListGroupIds": ["614"]},
                allowlist=load_allowlist(),
            ),
            captured_rows={
                "ItemBonusListGroup": [
                    {"ID": 614, "ItemGroupIlvlScalingID": 12, "PlayerConditionID": 143187}
                ],
                "ItemGroupIlvlScalingEntry": [
                    {"ID": 45, "ItemGroupIlvlScalingID": 12, "CurrencyTypeID": 3442, "PlayerConditionID": 153623},
                    {"ID": 46, "ItemGroupIlvlScalingID": 12, "CurrencyTypeID": 3443, "PlayerConditionID": 153624},
                    {"ID": 47, "ItemGroupIlvlScalingID": 12, "CurrencyTypeID": 3444, "PlayerConditionID": 153625},
                    {"ID": 48, "ItemGroupIlvlScalingID": 12, "CurrencyTypeID": 3445, "PlayerConditionID": 153626},
                    {"ID": 49, "ItemGroupIlvlScalingID": 12, "CurrencyTypeID": 3446, "PlayerConditionID": 153627},
                ],
            },
            allowlist=load_allowlist(),
        )
        currency_queries = {
            (row["table"], row["filterField"], row["targetValue"])
            for row in expanded
        }
        self.assertEqual(
            {
                ("CurrencyTypes", "ID", str(value))
                for value in (3442, 3443, 3444, 3445, 3446)
            },
            {row for row in currency_queries if row[0] == "CurrencyTypes"},
        )

    def test_modifier_item_expands_its_current_category_to_quality(self):
        initial_plan = build_bounded_db2_query_plan(
            targets={"modifiedCraftingReagentItemIds": ["657"]},
            allowlist=load_allowlist(),
        )
        expanded = expand_bounded_db2_query_plan(
            initial_plan,
            captured_rows={
                "ModifiedCraftingReagentItem": [
                    {
                        "ID": 657,
                        "ModifiedCraftingCategoryID": 854,
                        "ItemBonusTreeID": 5650,
                    }
                ]
            },
            allowlist=load_allowlist(),
        )
        pairs = {
            (row["table"], row["filterField"], row["targetValue"])
            for row in expanded
        }
        self.assertIn(
            ("CraftingReagentQuality", "ModifiedCraftingCategoryID", "854"),
            pairs,
        )

    def test_official_slot_category_targets_use_exact_category_filters(self):
        plan = build_bounded_db2_query_plan(
            targets={"modifiedCraftingCategoryIds": ["809", "854"]},
            allowlist=load_allowlist(),
        )
        self.assertEqual(
            {
                (row["table"], row["filterField"], row["targetValue"])
                for row in plan
            },
            {
                ("ModifiedCraftingCategory", "ID", "809"),
                ("ModifiedCraftingCategory", "ID", "854"),
                ("ModifiedCraftingReagentItem", "ModifiedCraftingCategoryID", "809"),
                ("ModifiedCraftingReagentItem", "ModifiedCraftingCategoryID", "854"),
                ("CraftingReagentQuality", "ModifiedCraftingCategoryID", "809"),
                ("CraftingReagentQuality", "ModifiedCraftingCategoryID", "854"),
            },
        )

    def test_modifier_item_expands_its_category_definition(self):
        initial_plan = build_bounded_db2_query_plan(
            targets={"modifiedCraftingReagentItemIds": ["657"]},
            allowlist=load_allowlist(),
        )
        expanded = expand_bounded_db2_query_plan(
            initial_plan,
            captured_rows={
                "ModifiedCraftingReagentItem": [
                    {"ID": 657, "ModifiedCraftingCategoryID": 854}
                ]
            },
            allowlist=load_allowlist(),
        )
        pairs = {
            (row["table"], row["filterField"], row["targetValue"])
            for row in expanded
        }
        self.assertIn(("ModifiedCraftingCategory", "ID", "854"), pairs)

    def test_allowlist_rejects_unbounded_transport_or_unknown_field(self):
        allowlist = load_allowlist()

        unbounded = copy.deepcopy(allowlist)
        unbounded["queryContract"]["allowFullTableCsv"] = True
        with self.assertRaisesRegex(LimitedDb2Error, "full-table"):
            validate_db2_field_allowlist(unbounded)

        unknown_field = copy.deepcopy(allowlist)
        unknown_field["tables"]["Item"]["fields"].append("Display_lang")
        with self.assertRaisesRegex(LimitedDb2Error, "field allowlist"):
            validate_db2_field_allowlist(unknown_field)

    def test_query_plan_uses_only_exact_official_targets(self):
        plan = build_bounded_db2_query_plan(
            targets={
                "itemIds": ["237842", "237842"],
                "recipeIds": ["52446"],
                "mythicPlusSeasonIds": ["18"],
            },
            allowlist=load_allowlist(),
        )

        self.assertEqual(
            len({row["requestKey"] for row in plan}),
            len(plan),
        )
        self.assertTrue(plan)
        for row in plan:
            self.assertEqual(row["operator"], "exact")
            self.assertIn(row["table"], load_allowlist()["tables"])
            self.assertEqual(
                set(row["query"]),
                {"build", f"filter[{row['filterField']}]"},
            )
            self.assertNotIn("csv", row["url"])
            self.assertNotIn("search", row["query"])
        item_rows = [row for row in plan if row["table"] == "Item"]
        self.assertEqual([row["targetValue"] for row in item_rows], ["237842"])

    def test_foreign_key_expansion_is_field_scoped_and_fail_closed(self):
        initial_plan = build_bounded_db2_query_plan(
            targets={"itemIds": ["237842"], "recipeIds": ["52446"]},
            allowlist=load_allowlist(),
        )
        captured_rows = {
            "SkillLineAbility": [
                {"ID": 52446, "SkillLine": 202, "Spell": 1229890}
            ],
            "SpellEffect": [
                {
                    "ID": 1221298,
                    "SpellID": 1229890,
                    "Effect": 288,
                    "EffectMiscValue_0": 2826,
                }
            ],
            "CraftingData": [
                {
                    "ID": 2826,
                    "CraftedItemID": 244767,
                    "CraftingDifficultyID": 33,
                    "ItemBonusTreeID": 5274,
                }
            ],
            "ItemConversionEntry": [
                {"ID": 1, "ItemID": 237842, "ItemConversionID": 77}
            ],
        }

        expanded = expand_bounded_db2_query_plan(
            initial_plan,
            captured_rows=captured_rows,
            allowlist=load_allowlist(),
        )
        pairs = {
            (row["table"], row["filterField"], row["targetValue"])
            for row in expanded
        }
        self.assertIn(
            ("SpellEffect", "SpellID", "1229890"),
            pairs,
        )
        self.assertIn(
            ("CraftingData", "ID", "2826"),
            pairs,
        )
        self.assertIn(
            ("Item", "ID", "244767"),
            pairs,
        )
        self.assertIn(
            ("CraftingDifficultyQuality", "CraftingDifficultyID", "33"),
            pairs,
        )
        self.assertIn(
            ("ItemConversion", "ID", "77"),
            pairs,
        )
        self.assertNotIn(
            ("ItemSparse", "ID", "1229890"),
            pairs,
        )

        item_rows = [
            row
            for row in expanded
            if row["table"] == "Item"
            and row["filterField"] == "ID"
            and row["targetValue"] == "244767"
        ]
        self.assertEqual(len(item_rows), 1)

    def test_item_bonus_scaling_config_edge_is_conditional_and_exact(self):
        initial_plan = build_bounded_db2_query_plan(
            targets={"itemIds": ["271472"]},
            allowlist=load_allowlist(),
        )
        expanded = expand_bounded_db2_query_plan(
            initial_plan,
            captured_rows={
                "ItemBonus": [
                    {
                        "ID": 1,
                        "ParentItemBonusListID": 12825,
                        "Type": 49,
                        "Value_0": 302,
                    },
                    {
                        "ID": 2,
                        "ParentItemBonusListID": 12825,
                        "Type": 51,
                        "Value_0": 484,
                    },
                    {
                        "ID": 3,
                        "ParentItemBonusListID": 12825,
                        "Type": 52,
                        "Value_0": 9,
                    },
                ]
            },
            allowlist=load_allowlist(),
        )
        pairs = {
            (row["table"], row["filterField"], row["targetValue"])
            for row in expanded
        }
        self.assertIn(("ItemScalingConfig", "ID", "302"), pairs)
        self.assertIn(("ItemScalingConfig", "ID", "484"), pairs)
        self.assertNotIn(("ItemScalingConfig", "ID", "9"), pairs)

    def test_item_conversion_expands_its_bonus_tree_for_preservation_evidence(self):
        initial_plan = build_bounded_db2_query_plan(
            targets={"itemIds": ["271472"]},
            allowlist=load_allowlist(),
        )
        expanded = expand_bounded_db2_query_plan(
            initial_plan,
            captured_rows={
                "ItemConversionEntry": [
                    {"ID": 1, "ItemID": 271472, "ItemConversionID": 13}
                ],
                "ItemConversion": [
                    {"ID": 13, "ItemBonusTreeID": 6014}
                ],
            },
            allowlist=load_allowlist(),
        )
        pairs = {
            (row["table"], row["filterField"], row["targetValue"])
            for row in expanded
        }
        self.assertIn(("ItemConversion", "ID", "13"), pairs)
        self.assertIn(("ItemBonusTree", "ID", "6014"), pairs)

    def test_bonus_tree_child_expands_tree_fact_and_nested_nodes(self):
        initial_plan = build_bounded_db2_query_plan(
            targets={"itemIds": [268196]},
            allowlist=load_allowlist(),
        )
        expanded = expand_bounded_db2_query_plan(
            initial_plan,
            captured_rows={
                "ItemXBonusTree": [
                    {"ItemID": 268196, "ItemBonusTreeID": 5996},
                ],
                "ItemBonusTreeNode": [
                    {
                        "ParentItemBonusTreeID": 5996,
                        "ChildItemBonusTreeID": 5998,
                    },
                ],
            },
            allowlist=load_allowlist(),
        )
        pairs = {
            (row["table"], row["filterField"], row["targetValue"])
            for row in expanded
        }
        self.assertIn(("ItemBonusTree", "ID", "5998"), pairs)

    def test_crafted_modifier_graph_expands_category_quality_and_bonus_tree_edges(self):
        initial_plan = build_bounded_db2_query_plan(
            targets={"recipeIds": ["52446"]},
            allowlist=load_allowlist(),
        )
        expanded = expand_bounded_db2_query_plan(
            initial_plan,
            captured_rows={
                "ModifiedCraftingReagentSlot": [
                    {"ID": 459, "Name_lang": "Amplify Secondary Stat"},
                    {"ID": 502, "Name_lang": "Add Embellishment"},
                ],
                "ModifiedCraftingReagentItem": [
                    {
                        "ID": 287,
                        "ItemBonusTreeID": 3986,
                        "ModifiedCraftingCategoryID": 459,
                    },
                    {
                        "ID": 342,
                        "ItemBonusTreeID": 4273,
                        "ModifiedCraftingCategoryID": 502,
                    },
                ],
                "ItemBonusTree": [
                    {"ID": 3986},
                ],
            },
            allowlist=load_allowlist(),
        )
        pairs = {
            (row["table"], row["filterField"], row["targetValue"])
            for row in expanded
        }
        self.assertIn(
            ("CraftingReagentQuality", "ModifiedCraftingCategoryID", "459"),
            pairs,
        )
        self.assertIn(
            ("CraftingReagentQuality", "ModifiedCraftingCategoryID", "502"),
            pairs,
        )
        self.assertIn(("ItemBonusTree", "ID", "3986"), pairs)
        self.assertIn(("ItemBonusTree", "ID", "4273"), pairs)
        self.assertIn(
            ("ItemBonusTreeNode", "ParentItemBonusTreeID", "3986"),
            pairs,
        )

    def test_projection_drops_unapproved_db2_columns(self):
        projected = project_db2_row(
            table="ItemSparse",
            row={
                "ID": 237842,
                "ItemLevel": 197,
                "OverallQualityID": 4,
                "Display_lang": "Bloomforged Greataxe",
                "SellPrice": 123,
            },
            allowlist=load_allowlist(),
        )

        self.assertEqual(
            projected,
            {"ID": 237842, "ItemLevel": 197, "OverallQualityID": 4},
        )
        self.assertNotIn("Display_lang", projected)
        self.assertNotIn("SellPrice", projected)

        modifier = project_db2_row(
            table="ModifiedCraftingReagentItem",
            row={
                "ID": 287,
                "ModifiedCraftingCategoryID": 459,
                "ItemBonusTreeID": 3986,
                "Description_lang": "Amplify a secondary stat",
                "InternalOnly": "must not persist",
            },
            allowlist=load_allowlist(),
        )
        self.assertEqual(modifier["Description_lang"], "Amplify a secondary stat")
        self.assertNotIn("InternalOnly", modifier)

    def test_capture_persists_projected_rows_and_expands_recipe_foreign_keys(self):
        plan = build_bounded_db2_query_plan(
            targets={"recipeIds": ["52446"]},
            allowlist=load_allowlist(),
        )

        class Reader:
            def get(self, request, *, page):
                table = request["table"]
                value = request["targetValue"]
                rows = {
                    ("SkillLineAbility", "52446"): [
                        {
                            "ID": 52446,
                            "SkillLine": 202,
                            "Spell": 1229890,
                            "AbilityVerb_lang": "must not persist",
                        }
                    ],
                    ("SpellEffect", "1229890"): [
                        {
                            "ID": 1221298,
                            "SpellID": 1229890,
                            "Effect": 288,
                            "EffectMiscValue_0": 2826,
                            "EffectTriggerSpell": 0,
                        }
                    ],
                    ("CraftingData", "2826"): [
                        {
                            "ID": 2826,
                            "CraftedItemID": 244767,
                            "CraftingDifficultyID": 33,
                            "ItemBonusTreeID": 5274,
                        }
                    ],
                }.get((table, value), [])
                return {
                    "url": request["url"],
                    "bodySha256": "b" * 64,
                    "bodyBytes": 128,
                    "payload": {
                        "current_page": page,
                        "last_page": 1,
                        "per_page": 25,
                        "total": len(rows),
                        "data": rows,
                    },
                }

        with self.subTest("capture"):
            with __import__("tempfile").TemporaryDirectory() as directory:
                result = capture_bounded_db2_evidence(
                    plan=plan,
                    output_root=Path(directory),
                    reader=Reader(),
                    allowlist=load_allowlist(),
                    captured_at="2026-08-19T01:00:00Z",
                )
                self.assertEqual(result["status"], "captured")
                manifest = json.loads(
                    (Path(directory) / "capture-manifest.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(
                    manifest["adapterRevision"],
                    "s2-limited-db2-capture-adapter-v2",
                )
                self.assertGreater(manifest["requestCount"], 1)
                self.assertEqual(manifest["rawDb2Persisted"], False)
                self.assertIn(
                    ("SpellEffect", "SpellID", "1229890"),
                    {
                        (row["table"], row["filterField"], row["targetValue"])
                        for row in manifest["entries"]
                    },
                )
                record_paths = [
                    Path(directory) / row["responsePath"]
                    for row in manifest["entries"]
                    if row["table"] == "SkillLineAbility"
                ]
                record = json.loads(record_paths[0].read_text(encoding="utf-8"))
                self.assertEqual(record["rows"][0]["ID"], 52446)
                self.assertNotIn("AbilityVerb_lang", record["rows"][0])
                self.assertEqual(record["bodySha256"], "b" * 64)

    def test_capture_accepts_bounded_worker_pool_without_changing_evidence_contract(self):
        plan = build_bounded_db2_query_plan(
            targets={"itemIds": ["237842", "237843"]},
            allowlist=load_allowlist(),
        )

        class Reader:
            def get(self, request, *, page):
                value = request["targetValue"]
                field = request["filterField"]
                return {
                    "url": request["url"],
                    "bodySha256": "c" * 64,
                    "bodyBytes": 64,
                    "payload": {
                        "current_page": page,
                        "last_page": 1,
                        "per_page": 25,
                        "total": 1,
                        "data": [{field: int(value)}],
                    },
                }

        with __import__("tempfile").TemporaryDirectory() as directory:
            result = capture_bounded_db2_evidence(
                plan=plan,
                output_root=Path(directory),
                reader=Reader(),
                allowlist=load_allowlist(),
                captured_at="2026-08-19T01:00:00Z",
                workers=2,
            )

            self.assertEqual(result["status"], "captured")
            manifest = json.loads(
                (Path(directory) / "capture-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["rawDb2Persisted"], False)
            self.assertEqual(manifest["requestCount"], len(plan))
            self.assertEqual(
                {row["targetValue"] for row in manifest["entries"]},
                {"237842", "237843"},
            )

    def test_capture_rejects_invalid_worker_count(self):
        with self.assertRaisesRegex(LimitedDb2Error, "workers"):
            capture_bounded_db2_evidence(
                plan=[],
                output_root=Path(__import__("tempfile").mkdtemp()),
                reader=object(),
                allowlist=load_allowlist(),
                workers=0,
            )

    def test_capture_failure_is_blocked_and_does_not_write_manifest(self):
        plan = build_bounded_db2_query_plan(
            targets={"itemIds": ["237842"]},
            allowlist=load_allowlist(),
        )

        class BrokenReader:
            def get(self, request, *, page):
                raise RuntimeError("403")

        with __import__("tempfile").TemporaryDirectory() as directory:
            with self.assertRaisesRegex(LimitedDb2Error, "REQUEST_FAILED"):
                capture_bounded_db2_evidence(
                    plan=plan,
                    output_root=Path(directory),
                    reader=BrokenReader(),
                    allowlist=load_allowlist(),
                    captured_at="2026-08-19T01:00:00Z",
                )
            failure = json.loads(
                (Path(directory) / "capture-failure.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(failure["status"], "blocked")
            self.assertEqual(
                failure["errorCode"],
                "S2_LIMITED_DB2_REQUEST_FAILED",
            )
            self.assertFalse((Path(directory) / "capture-manifest.json").exists())

    def test_targets_are_derived_only_from_captured_official_api_paths(self):
        targets = collect_s2_official_db2_targets(
            {
                "status": "captured",
                "entries": [
                    {"path": "/data/wow/item/237842"},
                    {"path": "/data/wow/item/237842"},
                    {"path": "/data/wow/recipe/52446"},
                    {"path": "/data/wow/mythic-keystone/season/18"},
                    {"path": "/data/wow/mythic-keystone/period/1076"},
                    {"path": "/data/wow/item-set/2065"},
                ],
            }
        )

        self.assertEqual(
            targets,
            {
                "itemIds": ["237842"],
                "recipeIds": ["52446"],
                "mythicPlusSeasonIds": ["18"],
                "journalEncounterIds": [],
            },
        )

    def test_targets_reject_an_uncaptured_or_missing_manifest(self):
        with self.assertRaisesRegex(LimitedDb2Error, "captured"):
            collect_s2_official_db2_targets({"status": "blocked", "entries": []})


if __name__ == "__main__":
    unittest.main()

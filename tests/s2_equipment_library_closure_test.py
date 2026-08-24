import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from server.s2_equipment_library_closure import (
    S2EquipmentLibraryClosureError,
    _build_crafted_variant_templates,
    _build_item_variant_records,
    _apply_simc_matrix_readiness,
    _candidate_identity_report_id,
    _crafted_quality_facts,
    _conversion_fact,
    _equipment_scope,
    _mythic_plus_cap_track_evidence,
    _raid_base_numeric_evidence,
    _raid_contextual_static_numeric_evidence,
    _requires_track_authority,
    _is_crafted_graph_component,
    _is_uncomposed_raid_component,
    _is_uncomposed_mythic_plus_component,
    _variant_source_eligibility,
    build_s2_equipment_library_closure,
)


ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(body)
    return hashlib.sha256(body).hexdigest(), len(body)


def _official_entry(root: Path, ordinal: int, item_id: str, payload: dict) -> dict:
    response_path = root / "raw" / f"{ordinal:04d}.json"
    response_sha256, response_bytes = _write_json(response_path, payload)
    return {
        "path": f"/data/wow/item/{item_id}",
        "query": {},
        "namespace": "static-us",
        "region": "us",
        "locale": "en_US",
        "responsePath": response_path.relative_to(root).as_posix(),
        "responseSha256": response_sha256,
        "responseBytes": response_bytes,
    }


def _prepare_official_capture(root: Path) -> None:
    set_response = {
        "id": 2001,
        "name": "Tier Set",
        "items": [{"id": 1002, "name": "Tier Helm"}],
        "effects": [
            {
                "required_count": 2,
                "display_string": "Set: Tier effect.",
            }
        ],
    }
    set_response_path = root / "raw" / "0000-set.json"
    set_hash, set_bytes = _write_json(set_response_path, set_response)
    entries = [
        {
            "path": "/data/wow/item-set/2001",
            "query": {},
            "namespace": "static-us",
            "region": "us",
            "locale": "en_US",
            "responsePath": set_response_path.relative_to(root).as_posix(),
            "responseSha256": set_hash,
            "responseBytes": set_bytes,
        },
        _official_entry(
            root,
            1,
            "1001",
            {
                "id": 1001,
                "name": "Raid Blade",
                "is_equippable": True,
                "item_class": {"id": 2, "name": "Weapon"},
                "item_subclass": {"id": 7, "name": "One-Handed Swords"},
                "inventory_type": {"type": "WEAPON", "name": "Weapon"},
                "level": 200,
                "preview_item": {
                    "bonus_list": ["100"],
                    "level": {"value": 200},
                    "stats": [{"type": {"type": "HASTE_RATING"}, "value": 10}],
                },
            },
        ),
        _official_entry(
            root,
            2,
            "1002",
            {
                "id": 1002,
                "name": "Tier Helm",
                "is_equippable": True,
                "item_class": {"id": 4, "name": "Armor"},
                "item_subclass": {"id": 1, "name": "Cloth"},
                "inventory_type": {"type": "HEAD", "name": "Head"},
                "level": 200,
                "preview_item": {
                    "bonus_list": ["200"],
                    "level": {"value": 200},
                    "stats": [{"type": {"type": "CRIT_RATING"}, "value": 12}],
                },
            },
        ),
    ]
    _write_json(
        root / "capture-manifest.json",
        {
            "schemaRevision": "s2-official-api-capture-manifest-v1",
            "status": "captured",
            "entries": entries,
        },
    )


def _prepare_db2_capture(root: Path) -> None:
    responses = [
        (
            "ItemScalingConfig",
            "302",
            [{"ID": 302, "ItemLevel": 266, "RequiredLevel": 90}],
        ),
        (
            "ItemScalingConfig",
            "484",
            [{"ID": 484, "ItemOffsetCurveID": 50, "ItemLevel": 0}],
        ),
        (
            "ItemScalingConfig",
            "303",
            [{"ID": 303, "ItemLevel": 269, "RequiredLevel": 90}],
        ),
        (
            "ItemOffsetCurve",
            "50",
            [{"ID": 50, "CurveID": 92772, "Offset": 13}],
        ),
        (
            "Curve",
            "92772",
            [{"ID": 92772, "Type": 0, "Flags": 0}],
        ),
        (
            "CurvePoint",
            "92772",
            [{"ID": 1, "CurveID": 92772, "OrderIndex": 0, "Pos_0": 80, "Pos_1": 120}],
        ),
        (
            "ItemXBonusTree",
            "1001",
            [{"ID": 1, "ItemID": 1001, "ItemBonusTreeID": 5001}],
        ),
        (
            "ItemBonusTreeNode",
            "5001",
            [
                {
                    "ID": 2,
                    "ParentItemBonusTreeID": 5001,
                    "ChildItemBonusListGroupID": 0,
                    "ChildItemBonusListID": 6001,
                    "ChildItemBonusTreeID": 0,
                    "ChildItemLevelSelectorID": 0,
                },
                {
                    "ID": 5,
                    "ParentItemBonusTreeID": 5001,
                    "ChildItemBonusListGroupID": 7001,
                    "ChildItemBonusListID": 0,
                    "ChildItemBonusTreeID": 0,
                    "ChildItemLevelSelectorID": 0,
                },
            ],
        ),
        (
            "ItemBonusListGroupEntry",
            "7001",
            [
                {
                    "ID": 10,
                    "ItemBonusListGroupID": 7001,
                    "ItemBonusListID": 6002,
                    "SequenceValue": 1,
                    "Flags": 0,
                },
                {
                    "ID": 11,
                    "ItemBonusListGroupID": 7001,
                    "ItemBonusListID": 6003,
                    "SequenceValue": 2,
                    "Flags": 0,
                },
            ],
        ),
        (
            "ItemBonusListGroup",
            "7001",
            [
                {
                    "ID": 7001,
                    "ItemGroupIlvlScalingID": 12,
                    "PlayerConditionID": 143187,
                    "SequenceSpellID": 1298569,
                }
            ],
        ),
        (
            "ItemGroupIlvlScalingEntry",
            "12",
            [
                {
                    "ID": 45,
                    "ItemGroupIlvlScalingID": 12,
                    "CurrencyTypeID": 3442,
                    "PlayerConditionID": 153623,
                }
            ],
        ),
        (
            "PlayerCondition",
            "143187",
            [
                {
                    "ID": 143187,
                    "Failure_description_lang": "The season has ended.",
                }
            ],
        ),
        (
            "PlayerCondition",
            "153623",
            [{"ID": 153623, "Failure_description_lang": "Requires currency."}],
        ),
        (
            "ItemBonus",
            "6001",
            [
                {"ID": 3, "ParentItemBonusListID": 6001, "Type": 49, "Value_0": 302},
                {"ID": 4, "ParentItemBonusListID": 6001, "Type": 51, "Value_0": 484},
            ],
        ),
        (
            "ItemBonus",
            "6002",
            [
                {"ID": 6, "ParentItemBonusListID": 6002, "Type": 49, "Value_0": 303},
                {"ID": 7, "ParentItemBonusListID": 6002, "Type": 50, "Value_0": 13485},
            ],
        ),
        (
            "ItemBonus",
            "6003",
            [{"ID": 8, "ParentItemBonusListID": 6003, "Type": 49, "Value_0": 303}],
        ),
        (
            "ItemBonusListLevelDelta",
            "6001",
            [{"ID": 6001, "ItemLevelDelta": 3}],
        ),
    ]
    entries = []
    for ordinal, (table, target_value, rows) in enumerate(responses, start=1):
        response_path = root / "responses" / f"{ordinal:06d}.json"
        response = {
            "schemaRevision": "s2-limited-db2-response-v1",
            "table": table,
            "filterField": "ID",
            "targetValue": target_value,
            "rows": rows,
        }
        digest, size = _write_json(response_path, response)
        entries.append({
            "table": table,
            "filterField": "ID",
            "targetValue": target_value,
            "responsePath": response_path.relative_to(root).as_posix(),
            "responseSha256": digest,
            "responseBytes": size,
        })
    _write_json(
        root / "capture-manifest.json",
        {
            "schemaRevision": "s2-limited-db2-capture-manifest-v1",
            "status": "captured",
            "clientBuild": "12.1.0.69299",
            "entries": entries,
        },
    )


class S2EquipmentLibraryClosureTest(unittest.TestCase):
    def test_simc_matrix_readiness_marks_exact_public_and_crafted_rows_and_counts(self):
        report = {
            "itemDefinitions": [
                {"itemId": "1001", "simcReadiness": "blocked"},
                {"itemId": "1002", "simcReadiness": "blocked"},
            ],
            "variants": [
                {
                    "itemId": "1001",
                    "variantKey": "public-variant",
                    "status": "verified",
                    "simcReadiness": "blocked",
                },
                {
                    "itemId": "1002",
                    "variantKey": "excluded-variant",
                    "status": "excluded",
                    "simcReadiness": "excluded",
                },
            ],
            "craftedVariantTemplates": [
                {
                    "itemId": "1002",
                    "variantKey": "crafted-variant",
                    "status": "verified",
                    "simcReadiness": "blocked",
                },
            ],
            "coverageCounts": {
                "blockedCount": 2,
                "blockedItemCount": 2,
                "blockedVariantCount": 1,
                "simcReadyCount": 0,
                "craftedVariantTemplateSimcReadyCount": 0,
            },
        }
        matrix = {
            "reportId": "matrix-report",
            "runtimeIdentity": "simc:test",
            "publicVariantMatrix": {
                "results": [
                    {
                        "jobKey": "public:public-variant",
                        "status": "verified",
                        "failureCodes": [],
                    }
                ]
            },
            "craftedVariantMatrix": {
                "results": [
                    {
                        "jobKey": "crafted:crafted-variant",
                        "status": "verified",
                        "failureCodes": [],
                    }
                ]
            },
        }

        _apply_simc_matrix_readiness(report, matrix)

        self.assertEqual(report["variants"][0]["simcReadiness"], "ready")
        self.assertEqual(report["variants"][1]["simcReadiness"], "excluded")
        self.assertEqual(
            report["craftedVariantTemplates"][0]["simcReadiness"],
            "ready",
        )
        self.assertEqual(report["coverageCounts"]["simcReadyCount"], 2)
        self.assertEqual(report["coverageCounts"]["blockedCount"], 0)
        self.assertEqual(
            report["coverageCounts"]["craftedVariantTemplateSimcReadyCount"],
            1,
        )

    def test_equipment_scope_excludes_profession_only_statless_gear_but_keeps_combat_profession_gear(self):
        fishing_hat = {
            "id": 239644,
            "is_equippable": True,
            "item_class": {"id": 4},
            "item_subclass": {"id": 0},
            "inventory_type": {"type": "HEAD"},
            "level": 80,
            "preview_item": {
                "is_subclass_hidden": True,
                "level": {"value": 180},
                "requirements": {"skill": {"profession": {"id": 2911}}},
                "spells": [{"description": "+5 Midnight Fishing Skill"}],
            },
        }
        self.assertEqual(
            _equipment_scope(fishing_hat),
            ("", "OUT_OF_SCOPE_PROFESSION_ONLY_GEAR"),
        )

        engineering_boots = {
            "id": 245337,
            "is_equippable": True,
            "item_class": {"id": 4},
            "item_subclass": {"id": 1},
            "inventory_type": {"type": "FEET"},
            "level": 197,
            "preview_item": {
                "level": {"value": 165},
                "stats": [
                    {"type": {"type": "INTELLECT"}, "value": 29},
                    {"type": {"type": "VERSATILITY_RATING"}, "value": 51},
                ],
                "requirements": {"skill": {"profession": {"id": 2910}}},
            },
        }
        self.assertEqual(_equipment_scope(engineering_boots)[0], "feet")

    def test_equipment_scope_excludes_level_one_statless_item_without_bonus_tree(self):
        statless_item = {
            "id": 258045,
            "is_equippable": True,
            "item_class": {"id": 2},
            "item_subclass": {"id": 9},
            "inventory_type": {"type": "WEAPON"},
            "level": 1,
            "preview_item": {
                "level": {"value": 1},
                "quality": {"type": "RARE"},
                "weapon": {"damage": {"min_value": 1, "max_value": 1}},
            },
        }
        self.assertEqual(
            _equipment_scope(
                statless_item,
                static_row={
                    "ID": 258045,
                    "ItemLevel": 1,
                    **{
                        f"StatModifier_bonusStat_{index}": -1
                        for index in range(10)
                    },
                },
                has_bonus_tree=False,
            ),
            ("", "OUT_OF_SCOPE_STATLESS_LEVEL_ONE_ITEM"),
        )

    def test_raid_base_numeric_evidence_is_limited_to_contextless_zero_delta_branches(self):
        evidence = _raid_base_numeric_evidence(
            {"level": {"value": 219}},
            item_context_values=[],
            scaling_evidence=[],
            bonus_list_level_delta_evidence=[
                {"status": "not_found", "itemLevelDelta": None},
            ],
            bonus_type_ids=[0, 2, 9],
        )
        self.assertEqual(evidence["status"], "verified")
        self.assertEqual(evidence["itemLevel"], 219)
        self.assertEqual(evidence["authority"], "blizzard_game_data_api.item.level")
        self.assertIsNone(
            _raid_base_numeric_evidence(
                {"level": 219},
                item_context_values=["153"],
                scaling_evidence=[],
                bonus_list_level_delta_evidence=[],
                bonus_type_ids=[0],
            )
        )
        self.assertIsNone(
            _raid_base_numeric_evidence(
                {"level": 219},
                item_context_values=[],
                scaling_evidence=[],
                bonus_list_level_delta_evidence=[
                    {"status": "verified", "itemLevelDelta": 3},
                ],
                bonus_type_ids=[0],
            )
        )
        self.assertIsNone(
            _raid_base_numeric_evidence(
                {"level": 219},
                item_context_values=[],
                scaling_evidence=[],
                bonus_list_level_delta_evidence=[],
                bonus_type_ids=[49],
            )
        )

    def test_raid_base_drop_does_not_require_mistcrest_track(self):
        self.assertFalse(
            _requires_track_authority(
                [{"logicalSource": "raid"}],
                {"bonusListGroupId": None},
            )
        )
        self.assertTrue(
            _requires_track_authority(
                [{"logicalSource": "raid"}],
                {"bonusListGroupId": "615"},
            )
        )
        self.assertTrue(
            _requires_track_authority(
                [{"logicalSource": "mythic_plus"}],
                {"bonusListGroupId": None},
            )
        )

    def test_crafted_quality_facts_map_db2_quality_bonus_offsets_to_exact_item_levels(self):
        quality_rows = [
            {
                "ID": 98 + index,
                "_Order": index,
                "CraftingDifficultyID": 34,
                "CraftingQualityID": 4 + index,
                "QualityPercentage": percentage,
            }
            for index, percentage in enumerate((0, 20, 50, 80, 100))
        ]
        bonus_offsets = (0, 3, 6, 9, 13)
        facts = _crafted_quality_facts(
            "5001",
            "1003",
            crafted_recipe_rows={},
            db2_rows={
                "CraftingData": [
                    {
                        "ID": 7001,
                        "CraftedItemID": 1003,
                        "CraftingDifficultyID": 34,
                        "ItemBonusTreeID": 5274,
                    }
                ],
                "CraftingDifficultyQuality": quality_rows,
                "CraftingQuality": [
                    {"ID": 4 + index, "QualityTier": 1 + index}
                    for index in range(5)
                ],
                "ItemSparse": [{"ID": 1003, "ItemLevel": 233}],
                "ItemXBonusTree": [
                    {"ID": 900, "ItemID": 1003, "ItemBonusTreeID": 5102}
                ],
                "ItemBonusTreeNode": [
                    {
                        "ID": 23081,
                        "ParentItemBonusTreeID": 5102,
                        "ChildItemBonusListID": 9001,
                        "ChildItemBonusTreeID": 0,
                        "ChildItemBonusListGroupID": 0,
                    },
                    {
                        "ID": 24336,
                        "ParentItemBonusTreeID": 5274,
                        "ChildItemBonusListGroupID": 591,
                        "ChildItemBonusListID": 0,
                        "ChildItemBonusTreeID": 0,
                    },
                ],
                "ItemBonusListGroupEntry": [
                    {
                        "ID": 4281 + index,
                        "ItemBonusListGroupID": 591,
                        "ItemBonusListID": 12493 + index,
                        "SequenceValue": 1 + index,
                    }
                    for index in range(5)
                ],
                "ItemBonusList": [
                    {"ID": 9001, "Flags": 0},
                    *[
                        {"ID": 12493 + index, "Flags": 0}
                        for index in range(5)
                    ],
                ],
                "ItemBonus": [
                    {
                        "ID": 30001,
                        "ParentItemBonusListID": 9001,
                        "Type": 49,
                        "Value_0": 302,
                    },
                    *[
                        {
                            "ID": 30552 + index,
                            "ParentItemBonusListID": 12493 + index,
                            "Type": 52,
                            "Value_0": bonus_offsets[index],
                            "Value_1": 2,
                            "Value_2": index,
                            "Value_3": 0,
                        }
                        for index in range(5)
                    ],
                ],
                "ItemScalingConfig": [
                    {"ID": 302, "ItemLevel": 246}
                ],
            },
            db2_refs={},
        )

        self.assertEqual(facts["status"], "verified")
        self.assertEqual(
            [row["bonusListIds"] for row in facts["qualityOptions"]],
            [["9001", str(12493 + index)] for index in range(5)],
        )
        self.assertEqual(
            [row["itemLevel"] for row in facts["qualityOptions"]],
            [246, 249, 252, 255, 259],
        )
        self.assertEqual(
            facts["qualityOptions"][4]["itemLevelSource"],
            "ItemScalingConfig_or_ItemSparse_plus_ItemBonus.Type52.Value_0",
        )

    def test_mythic_plus_cap_track_evidence_uses_db2_branch_and_mistcrest_facts(self):
        groups = []
        entries = []
        costs = []
        currencies = []
        for group_id, track, currency_id in (
            (614, "Adventurer", 3442),
            (615, "Veteran", 3443),
            (616, "Champion", 3444),
            (617, "Hero", 3445),
            (618, "Myth", 3446),
        ):
            groups.append(
                {
                    "ID": group_id,
                    "ItemGroupIlvlScalingID": 12,
                    "PlayerConditionID": 143187,
                }
            )
            currencies.append(
                {
                    "ID": currency_id,
                    "Name_lang": f"{track} Mistcrest",
                    "Description_lang": f"Used to upgrade {track} equipment in Midnight Season 2. Mythic Keystone Dungeons (+9 and up).",
                }
            )
            for rank in range(1, 9):
                extended_cost_id = 0 if rank == 1 else 100000 + group_id * 10 + rank
                entries.append(
                    {
                        "ID": group_id * 100 + rank,
                        "ItemBonusListGroupID": group_id,
                        "ItemBonusListID": 13000 + group_id * 10 + rank,
                        "ItemExtendedCostID": extended_cost_id,
                        "SequenceValue": rank,
                    }
                )
                if extended_cost_id:
                    costs.append(
                        {
                            "ID": extended_cost_id,
                            "CurrencyID_0": currency_id,
                            "CurrencyCount_0": 15,
                        }
                    )

        result = _mythic_plus_cap_track_evidence(
            {
                "ItemBonusTreeNode": [
                    {
                        "ID": 1,
                        "ItemContext": 16,
                        "ChildItemBonusListGroupID": 616,
                        "MinMythicPlusLevel": 0,
                        "MaxMythicPlusLevel": 5,
                    },
                    {
                        "ID": 2,
                        "ItemContext": 33,
                        "ChildItemBonusListGroupID": 617,
                        "MinMythicPlusLevel": 6,
                        "MaxMythicPlusLevel": 0,
                    },
                ],
                "ItemBonusListGroup": groups,
                "ItemBonusListGroupEntry": entries,
                "ItemExtendedCost": costs,
                "CurrencyTypes": currencies,
            },
            {},
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["trackKeys"], ["adventurer", "champion", "hero", "myth", "veteran"])
        self.assertEqual(result["mythicPlusLevelRanges"], [[0, 5], [6, None]])
        self.assertEqual(result["authority"], "official_client_db2.ItemBonusTreeNode_plus_upgrade_cost_chain")

    def test_mythic_plus_cap_track_evidence_records_empty_s2_season_bridge(self):
        result = _mythic_plus_cap_track_evidence(
            {
                "DisplaySeason": [{"ID": 37, "Season": 18, "ExpansionID": 11}],
                "ItemBonusSeason": [],
                "ItemBonusTreeNode": [],
                "ItemBonusListGroup": [],
                "ItemBonusListGroupEntry": [],
                "ItemExtendedCost": [],
                "CurrencyTypes": [],
            },
            {
                (
                    "ItemBonusSeason",
                    "__query__:SeasonID:37",
                ): ["db2-query:display-season-db2-v1/responses/000001.json#/rows"],
                (
                    "DisplaySeason",
                    json.dumps(
                        {"ID": 37, "Season": 18, "ExpansionID": 11},
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                ): ["db2-response:display-season-db2-v1/responses/000002.json#/rows/0"],
            },
        )

        self.assertEqual(result["seasonBridge"]["status"], "verified_empty")
        self.assertEqual(
            result["seasonBridge"]["reasonCode"],
            "OFFICIAL_DB2_ITEM_BONUS_SEASON_RELATION_EMPTY",
        )
        self.assertEqual(result["legacyProjectionStatus"], "UNVERIFIED")
        self.assertEqual(
            result["legacyProjectionReasonCode"],
            "OFFICIAL_DB2_ITEM_BONUS_SEASON_RELATION_EMPTY",
        )

    def test_mythic_plus_season_bridge_joins_display_season_value_not_display_row_id(self):
        result = _mythic_plus_cap_track_evidence(
            {
                "DisplaySeason": [{"ID": 37, "Season": 18, "ExpansionID": 11}],
                "ItemBonusSeason": [{"ID": 99, "SeasonID": 18}],
                "ItemBonusSeasonBonusListGroup": [
                    {"ID": 1, "ItemBonusSeasonID": 99, "ItemBonusListGroupID": 614}
                ],
                "ItemBonusTreeNode": [],
                "ItemBonusListGroup": [],
                "ItemBonusListGroupEntry": [],
                "ItemExtendedCost": [],
                "CurrencyTypes": [],
            },
            {
                (
                    "ItemBonusSeason",
                    "__query__:SeasonID:18",
                ): ["db2-query:display-season-db2-v2/responses/000006.json#/rows"],
                (
                    "DisplaySeason",
                    json.dumps(
                        {"ID": 37, "Season": 18, "ExpansionID": 11},
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                ): ["db2-response:display-season-db2-v2/responses/000003.json#/rows/0"],
            },
        )

        self.assertEqual(result["seasonBridge"]["displaySeasonId"], "37")
        self.assertEqual(result["seasonBridge"]["itemBonusSeasonId"], "99")
        self.assertEqual(result["seasonBridge"]["status"], "UNVERIFIED")

    def test_crafted_variant_templates_expand_quality_and_preserve_compatibility_edges(self):
        edge = {
            "recipeId": "5001",
            "itemId": "1003",
            "itemSlot": "head",
            "qualityVariants": {
                "status": "verified",
                "qualityOptions": [
                    {
                        "qualityId": "4",
                        "qualityTier": 1,
                        "qualityPercentage": 0,
                        "itemLevel": 246,
                        "bonusListIds": ["12493"],
                        "status": "verified",
                    },
                    {
                        "qualityId": "8",
                        "qualityTier": 5,
                        "qualityPercentage": 100,
                        "itemLevel": 285,
                        "bonusListIds": ["12497"],
                        "status": "verified",
                    },
                ],
            },
            "secondaryStatCompatibility": {
                "status": "verified",
                "options": [{"itemId": "245791", "simcValue": "haste"}],
            },
            "embellishmentCompatibility": {
                "status": "verified",
                "options": [{"itemId": "240166", "simcValue": "acme"}],
            },
            "enhancementCompatibility": {
                "status": "verified",
                "options": [{"itemId": "240166", "simcValue": "acme"}],
            },
        }

        templates = _build_crafted_variant_templates(edge)

        self.assertEqual(
            [row["variantKey"] for row in templates],
            [
                "s2-crafted:recipe:5001:item:1003:quality:1",
                "s2-crafted:recipe:5001:item:1003:quality:5",
            ],
        )
        self.assertEqual(templates[0]["quality"]["qualityId"], "4")
        self.assertEqual(templates[1]["canonicalSimcInput"]["itemLevel"], 285)
        self.assertEqual(
            templates[0]["selectionContract"]["secondaryStats"]["options"],
            [{"itemId": "245791", "simcValue": "haste"}],
        )
        self.assertEqual(templates[0]["canonicalSimcInput"]["status"], "verified")

    def test_crafted_variant_templates_expand_verified_mistcrest_tracks_without_cartesian_modifiers(self):
        edge = {
            "recipeId": "5002",
            "itemId": "1004",
            "itemSlot": "chest",
            "qualityVariants": {
                "status": "verified",
                "qualityOptions": [
                    {
                        "qualityId": "4",
                        "qualityTier": 1,
                        "qualityPercentage": 0,
                        "itemLevel": 246,
                        "bonusListIds": ["12493"],
                        "status": "verified",
                    },
                    {
                        "qualityId": "8",
                        "qualityTier": 5,
                        "qualityPercentage": 100,
                        "itemLevel": 259,
                        "bonusListIds": ["12497"],
                        "status": "verified",
                    },
                ],
            },
            "secondaryStatCompatibility": {
                "status": "verified",
                "options": [{"itemId": "245791", "simcValue": "haste"}],
            },
            "embellishmentCompatibility": {
                "status": "verified",
                "options": [],
            },
            "enhancementCompatibility": {
                "status": "verified",
                "options": [
                    {
                        "kind": "currency",
                        "currencyTypeId": "3445",
                        "name": "Hero Mistcrest",
                        "description": "When used for crafting, sets the item level of the resulting item to 305-318 based on Quality.",
                        "evidenceStatus": "verified",
                    },
                    {
                        "kind": "currency",
                        "currencyTypeId": "3446",
                        "name": "Myth Mistcrest",
                        "description": "When used for crafting, sets the item level of the resulting item to 318-331 based on Quality.",
                        "evidenceStatus": "verified",
                    },
                ],
            },
        }

        templates = _build_crafted_variant_templates(edge)

        self.assertEqual(len(templates), 4)
        self.assertEqual(
            {row["craftedTrackKey"] for row in templates},
            {"hero", "myth"},
        )
        myth_q5 = next(
            row
            for row in templates
            if row["craftedTrackKey"] == "myth" and row["quality"]["qualityTier"] == 5
        )
        self.assertEqual(myth_q5["canonicalSimcInput"]["itemLevel"], 331)
        self.assertEqual(
            myth_q5["canonicalSimcInput"]["bonusIds"],
            ["12497"],
        )
        self.assertEqual(
            myth_q5["selection"]["enhancement"]["currencyTypeId"],
            "3446",
        )

    def test_variant_source_eligibility_uses_captured_map_difficulty(self):
        rows = {
            "MapDifficulty": [
                *[
                    {
                        "ID": index,
                        "MapID": int(map_id),
                        "DifficultyID": 8,
                        "ItemContext": 16,
                        "ItemContextPickerID": 0,
                    }
                    for index, map_id in enumerate(
                        ("1762", "1877", "2521", "2813", "2825", "2859", "2923", "2993"),
                        start=1,
                    )
                ],
                {
                    "ID": 99,
                    "MapID": 2987,
                    "DifficultyID": 14,
                    "ItemContext": 0,
                    "ItemContextPickerID": 0,
                },
            ]
            ,
            "ItemCreationContext": [
                {"ID": 1, "ItemContext": 16, "ItemCreationContextGroupID": 6},
                {"ID": 2, "ItemContext": 33, "ItemCreationContextGroupID": 6},
                {"ID": 3, "ItemContext": 35, "ItemCreationContextGroupID": 6},
                {"ID": 4, "ItemContext": 17, "ItemCreationContextGroupID": 6},
            ],
        }
        variant = {"itemContextValues": [16]}
        result = _variant_source_eligibility(
            variant,
            memberships=[{"logicalSource": "mythic_plus"}],
            db2_rows=rows,
            db2_refs={},
        )
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["bySource"]["mythic_plus"]["status"], "verified")
        self.assertEqual(
            result["bySource"]["mythic_plus"]["requiredItemContextValues"],
            ["16"],
        )

        challenge_mode_two = _variant_source_eligibility(
            {"itemContextValues": [33]},
            memberships=[{"logicalSource": "mythic_plus"}],
            db2_rows=rows,
            db2_refs={},
        )
        self.assertEqual(challenge_mode_two["status"], "verified")

        great_vault = _variant_source_eligibility(
            {"itemContextValues": [35]},
            memberships=[{"logicalSource": "mythic_plus"}],
            db2_rows=rows,
            db2_refs={},
        )
        self.assertEqual(great_vault["status"], "excluded")
        self.assertIn(
            "OUT_OF_SCOPE_GREAT_VAULT_PROJECTION_VARIANT",
            great_vault["reasonCodes"],
        )

        blocked = _variant_source_eligibility(
            {"itemContextValues": [34]},
            memberships=[{"logicalSource": "mythic_plus"}],
            db2_rows=rows,
            db2_refs={},
        )
        self.assertEqual(blocked["status"], "UNVERIFIED")
        self.assertIn(
            "OFFICIAL_DB2_ITEM_CREATION_CONTEXT_FACT_MISSING",
            blocked["reasonCodes"],
        )

    def test_variant_source_eligibility_uses_frozen_allowed_context_enum_when_db2_enum_row_is_sparse(self):
        rows = {
            "MapDifficulty": [
                {
                    "ID": index,
                    "MapID": int(map_id),
                    "DifficultyID": 8,
                    "ItemContext": 16,
                    "ItemContextPickerID": 0,
                }
                for index, map_id in enumerate(
                    ("1762", "1877", "2521", "2813", "2825", "2859", "2923", "2993"),
                    start=1,
                )
            ],
            "ItemCreationContext": [],
            "ItemBonusTreeNode": [
                {
                    "ID": 7001,
                    "ItemContext": 34,
                    "ParentItemBonusTreeID": 9001,
                },
            ],
        }
        result = _variant_source_eligibility(
            {
                "itemContextValues": [34],
                "nodePath": [{"nodeId": "7001", "itemContext": 34}],
            },
            memberships=[{"logicalSource": "mythic_plus"}],
            db2_rows=rows,
            db2_refs={},
        )
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["bySource"]["mythic_plus"]["status"], "verified")
        self.assertEqual(
            result["bySource"]["mythic_plus"]["itemCreationContextEvidence"][0]["authority"],
            "official_client_db2.ItemBonusTreeNode.ItemContext_plus_frozen_scope_enum",
        )

    def test_variant_source_eligibility_keeps_verified_source_when_other_source_excludes_branch(self):
        rows = {
            "MapDifficulty": [
                *[
                    {
                        "ID": index,
                        "MapID": int(map_id),
                        "DifficultyID": 8,
                        "ItemContext": 16,
                        "ItemContextPickerID": 0,
                    }
                    for index, map_id in enumerate(
                        ("1762", "1877", "2521", "2813", "2825", "2859", "2923", "2993"),
                        start=1,
                    )
                ],
                {"ID": 99, "MapID": 2987, "DifficultyID": 14, "ItemContext": 0},
                {"ID": 100, "MapID": 3004, "DifficultyID": 14, "ItemContext": 0},
            ],
            "ItemCreationContext": [
                {"ID": 1, "ItemContext": 16, "ItemCreationContextGroupID": 6},
            ],
        }
        result = _variant_source_eligibility(
            {"itemContextValues": [16]},
            memberships=[
                {"logicalSource": "mythic_plus"},
                {"logicalSource": "raid"},
            ],
            db2_rows=rows,
            db2_refs={},
        )
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["bySource"]["mythic_plus"]["status"], "verified")
        self.assertEqual(result["bySource"]["raid"]["status"], "excluded")

    def test_variant_source_eligibility_accepts_raid_contexts_and_excludes_world_boss(self):
        rows = {
            "MapDifficulty": [
                *[
                    {
                        "ID": index,
                        "MapID": int(map_id),
                        "DifficultyID": 14,
                        "ItemContext": 0,
                        "ItemContextPickerID": 0,
                    }
                    for index, map_id in enumerate(("2987", "3004"), start=1)
                ],
            ]
            ,
            "ItemCreationContext": [
                {"ID": 1, "ItemContext": 6, "ItemCreationContextGroupID": 6},
                {"ID": 2, "ItemContext": 81, "ItemCreationContextGroupID": 6},
            ],
        }
        raid = _variant_source_eligibility(
            {"itemContextValues": [6]},
            memberships=[{"logicalSource": "raid"}],
            db2_rows=rows,
            db2_refs={},
        )
        self.assertEqual(raid["status"], "verified")

        world_boss = _variant_source_eligibility(
            {"itemContextValues": [81]},
            memberships=[{"logicalSource": "raid"}],
            db2_rows=rows,
            db2_refs={},
        )
        self.assertEqual(world_boss["status"], "excluded")
        self.assertIn(
            "OUT_OF_SCOPE_WORLD_BOSS_VARIANT",
            world_boss["reasonCodes"],
        )

    def test_mplus_raw_component_is_not_a_second_public_variant_after_composition(self):
        self.assertTrue(
            _is_uncomposed_mythic_plus_component(
                {
                    "variantComposition": {"kind": "raw_graph_edge"},
                },
                memberships=[
                    {"logicalSource": "mythic_plus", "scopeStatus": "included"}
                ],
                mythic_plus_item_scope_status="verified",
                has_context_slot_vector=True,
            )
        )
        self.assertFalse(
            _is_uncomposed_mythic_plus_component(
                {
                    "variantComposition": {"kind": "raw_graph_edge"},
                },
                memberships=[
                    {"logicalSource": "mythic_plus", "scopeStatus": "included"}
                ],
                mythic_plus_item_scope_status="UNVERIFIED",
                has_context_slot_vector=True,
            )
        )

        self.assertFalse(
            _is_uncomposed_mythic_plus_component(
                {
                    "variantComposition": {"kind": "db2_context_slot_vector"},
                },
                memberships=[
                    {"logicalSource": "mythic_plus", "scopeStatus": "included"}
                ],
                mythic_plus_item_scope_status="verified",
                has_context_slot_vector=True,
            )
        )

    def test_raid_raw_component_is_excluded_only_when_bonus_is_a_strict_composed_subset(self):
        memberships = [{"logicalSource": "raid", "scopeStatus": "included"}]
        composed = [
            {
                "variantStatus": "verified",
                "bonusListIds": ["13334", "12849"],
                "variantComposition": {"kind": "db2_context_slot_vector"},
            }
        ]
        self.assertTrue(
            _is_uncomposed_raid_component(
                {
                    "bonusListIds": ["13334"],
                    "variantComposition": {"kind": "raw_graph_edge"},
                },
                memberships=memberships,
                composed_variants=composed,
            )
        )
        self.assertFalse(
            _is_uncomposed_raid_component(
                {
                    "bonusListIds": ["11215"],
                    "variantComposition": {"kind": "raw_graph_edge"},
                },
                memberships=memberships,
                composed_variants=composed,
            )
        )

    def test_crafted_graph_is_owned_by_verified_quality_templates(self):
        self.assertTrue(
            _is_crafted_graph_component(
                {
                    "itemId": "2006",
                    "variantComposition": {"kind": "raw_graph_edge"},
                },
                memberships=[
                    {
                        "logicalSource": "crafted",
                        "scopeStatus": "included",
                        "recipeId": "9006",
                    }
                ],
                crafted_templates=[
                    {"itemId": "2006", "recipeId": "9006", "status": "verified"}
                ],
            )
        )

    def test_raid_contextual_static_level_requires_exact_context_and_non_level_bonus_facts(self):
        evidence = _raid_contextual_static_numeric_evidence(
            {"level": 219, "preview_item": {"level": {"value": 219}}},
            static_item_level=219,
            item_context_values=["153"],
            item_creation_context_group_ids=["6"],
            bonus_type_ids=[0, 4, 37],
            scaling_evidence=[],
            bonus_list_level_delta_evidence=[
                {"status": "not_found", "itemLevelDelta": None}
            ],
            db2_rows={
                "ItemCreationContext": [
                    {"ID": 46, "ItemContext": 153, "ItemCreationContextGroupID": 6}
                ]
            },
        )
        self.assertEqual(evidence["status"], "verified")
        self.assertEqual(evidence["itemLevel"], 219)
        self.assertIn("ItemBonus", evidence["authority"])

    def test_official_preview_joins_sibling_bonus_tree_components(self):
        db2_rows = {
            "ItemXBonusTree": [
                {"ID": 1, "ItemID": 2001, "ItemBonusTreeID": 9000},
            ],
            "ItemBonusTree": [
                {"ID": 9000, "Flags": 4, "InventoryTypeSlotMask": 0},
                {"ID": 9001, "Flags": 0, "InventoryTypeSlotMask": 0},
                {"ID": 9002, "Flags": 0, "InventoryTypeSlotMask": 0},
            ],
            "ItemBonusTreeNode": [
                {
                    "ID": 1,
                    "ParentItemBonusTreeID": 9000,
                    "ChildItemBonusTreeID": 9001,
                    "ChildItemBonusListID": 0,
                    "ChildItemBonusListGroupID": 0,
                    "ChildItemLevelSelectorID": 0,
                },
                {
                    "ID": 2,
                    "ParentItemBonusTreeID": 9000,
                    "ChildItemBonusTreeID": 9002,
                    "ChildItemBonusListID": 0,
                    "ChildItemBonusListGroupID": 0,
                    "ChildItemLevelSelectorID": 0,
                },
                {
                    "ID": 3,
                    "ParentItemBonusTreeID": 9001,
                    "ChildItemBonusTreeID": 0,
                    "ChildItemBonusListID": 7101,
                    "ChildItemBonusListGroupID": 0,
                    "ChildItemLevelSelectorID": 0,
                },
                {
                    "ID": 4,
                    "ParentItemBonusTreeID": 9002,
                    "ChildItemBonusTreeID": 0,
                    "ChildItemBonusListID": 7102,
                    "ChildItemBonusListGroupID": 0,
                    "ChildItemLevelSelectorID": 0,
                },
            ],
            "ItemBonusList": [
                {"ID": 7101, "Flags": 0},
                {"ID": 7102, "Flags": 0},
            ],
            "ItemBonus": [
                {"ID": 1, "ParentItemBonusListID": 7101, "Type": 0},
                {"ID": 2, "ParentItemBonusListID": 7102, "Type": 0},
            ],
        }
        variants = _build_item_variant_records(
            "2001",
            db2_rows=db2_rows,
            db2_refs={},
            official_payload={
                "id": 2001,
                "preview_item": {
                    "bonus_list": [7101, 7102],
                    "level": {"value": 219},
                },
            },
        )

        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0]["bonusListIds"], ["7101", "7102"])
        self.assertEqual(
            variants[0]["variantComposition"]["kind"],
            "official_preview_vector",
        )
        self.assertEqual(
            variants[0]["variantComposition"]["componentIds"],
            ["tree:9001", "tree:9002"],
        )
        self.assertEqual(variants[0]["numericVariantEvidenceStatus"], "verified")
        self.assertEqual(
            variants[0]["officialPreviewItemLevelEvidence"],
            {
                "status": "verified",
                "itemLevel": 219,
                "authority": "blizzard_game_data_api.item.preview_item.level",
            },
        )

    def test_official_preview_joins_components_under_nested_composition_tree(self):
        db2_rows = {
            "ItemXBonusTree": [
                {"ID": 1, "ItemID": 2002, "ItemBonusTreeID": 9100},
            ],
            "ItemBonusTree": [
                {"ID": 9100, "Flags": 0, "InventoryTypeSlotMask": 0},
                {"ID": 9101, "Flags": 4, "InventoryTypeSlotMask": 0},
                {"ID": 9102, "Flags": 0, "InventoryTypeSlotMask": 0},
                {"ID": 9103, "Flags": 0, "InventoryTypeSlotMask": 0},
            ],
            "ItemBonusTreeNode": [
                {
                    "ID": 10,
                    "ParentItemBonusTreeID": 9100,
                    "ChildItemBonusTreeID": 9101,
                    "ChildItemBonusListID": 0,
                    "ChildItemBonusListGroupID": 0,
                    "ChildItemLevelSelectorID": 0,
                },
                {
                    "ID": 11,
                    "ParentItemBonusTreeID": 9101,
                    "ChildItemBonusTreeID": 9102,
                    "ChildItemBonusListID": 0,
                    "ChildItemBonusListGroupID": 0,
                    "ChildItemLevelSelectorID": 0,
                },
                {
                    "ID": 12,
                    "ParentItemBonusTreeID": 9101,
                    "ChildItemBonusTreeID": 9103,
                    "ChildItemBonusListID": 0,
                    "ChildItemBonusListGroupID": 0,
                    "ChildItemLevelSelectorID": 0,
                },
                {
                    "ID": 13,
                    "ParentItemBonusTreeID": 9102,
                    "ChildItemBonusTreeID": 0,
                    "ChildItemBonusListID": 7201,
                    "ChildItemBonusListGroupID": 0,
                    "ChildItemLevelSelectorID": 0,
                },
                {
                    "ID": 14,
                    "ParentItemBonusTreeID": 9103,
                    "ChildItemBonusTreeID": 0,
                    "ChildItemBonusListID": 7202,
                    "ChildItemBonusListGroupID": 0,
                    "ChildItemLevelSelectorID": 0,
                },
            ],
            "ItemBonusList": [
                {"ID": 7201, "Flags": 0},
                {"ID": 7202, "Flags": 0},
            ],
            "ItemBonus": [
                {"ID": 1, "ParentItemBonusListID": 7201, "Type": 0},
                {"ID": 2, "ParentItemBonusListID": 7202, "Type": 0},
            ],
        }
        variants = _build_item_variant_records(
            "2002",
            db2_rows=db2_rows,
            db2_refs={},
            official_payload={
                "id": 2002,
                "preview_item": {"bonus_list": [7201, 7202]},
            },
        )

        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0]["bonusListIds"], ["7201", "7202"])
        self.assertEqual(
            variants[0]["variantComposition"]["kind"],
            "official_preview_vector",
        )
        self.assertEqual(
            variants[0]["variantComposition"]["componentIds"],
            ["tree:9102", "tree:9103"],
        )

    def test_db2_context_slot_composition_filters_inventory_type_mask(self):
        db2_rows = {
            "Item": [
                {"ID": 2003, "InventoryType": 3},
            ],
            "ItemXBonusTree": [
                {"ID": 1, "ItemID": 2003, "ItemBonusTreeID": 9200},
            ],
            "ItemBonusTree": [
                {"ID": 9200, "Flags": 4, "InventoryTypeSlotMask": 0},
                # 1 << 3 matches shoulders.
                {"ID": 9201, "Flags": 0, "InventoryTypeSlotMask": 8},
                # 1 << 2 does not match shoulders.
                {"ID": 9202, "Flags": 0, "InventoryTypeSlotMask": 4},
            ],
            "ItemBonusTreeNode": [
                {
                    "ID": 20,
                    "ParentItemBonusTreeID": 9200,
                    "ChildItemBonusTreeID": 9201,
                    "ChildItemBonusListID": 0,
                    "ChildItemBonusListGroupID": 0,
                    "ChildItemLevelSelectorID": 0,
                    "ItemCreationContextGroupID": 9,
                },
                {
                    "ID": 21,
                    "ParentItemBonusTreeID": 9200,
                    "ChildItemBonusTreeID": 9202,
                    "ChildItemBonusListID": 0,
                    "ChildItemBonusListGroupID": 0,
                    "ChildItemLevelSelectorID": 0,
                },
                {
                    "ID": 22,
                    "ParentItemBonusTreeID": 9201,
                    "ChildItemBonusTreeID": 0,
                    "ChildItemBonusListID": 7301,
                    "ChildItemBonusListGroupID": 0,
                    "ChildItemLevelSelectorID": 0,
                },
                {
                    "ID": 23,
                    "ParentItemBonusTreeID": 9202,
                    "ChildItemBonusTreeID": 0,
                    "ChildItemBonusListID": 7302,
                    "ChildItemBonusListGroupID": 0,
                    "ChildItemLevelSelectorID": 0,
                },
            ],
            "ItemBonusList": [
                {"ID": 7301, "Flags": 0},
                {"ID": 7302, "Flags": 0},
            ],
            "ItemBonus": [
                {"ID": 1, "ParentItemBonusListID": 7301, "Type": 0},
                {"ID": 2, "ParentItemBonusListID": 7302, "Type": 0},
            ],
        }

        variants = _build_item_variant_records(
            "2003",
            db2_rows=db2_rows,
            db2_refs={},
            allow_raid_base_numeric_evidence=True,
        )

        composed = [
            variant
            for variant in variants
            if variant["variantComposition"]["kind"] == "db2_context_slot_vector"
        ]
        self.assertEqual(len(composed), 1)
        self.assertEqual(composed[0]["bonusListIds"], ["7301"])
        self.assertEqual(
            composed[0]["variantComposition"]["status"],
            "observed",
        )
        self.assertEqual(
            composed[0]["variantComposition"]["compositionTreeIds"],
            ["9200"],
        )
        self.assertEqual(composed[0]["rawGraphStatus"], "verified")
        self.assertEqual(
            composed[0]["variantComposition"]["defaultContextGroupStatus"],
            "not_required",
        )
        self.assertNotIn(
            "OFFICIAL_DB2_ITEM_BONUS_TREE_COMPOSITION_SEMANTICS_UNVERIFIED",
            composed[0]["reasonCodes"],
        )

    def test_tier_set_default_context_zero_rows_close_context_and_numeric_base(self):
        db2_rows = {
            "Item": [{"ID": 2005, "InventoryType": 3}],
            "ItemXBonusTree": [
                {"ID": 1, "ItemID": 2005, "ItemBonusTreeID": 9200},
            ],
            "ItemBonusTree": [
                {"ID": 9200, "Flags": 4, "InventoryTypeSlotMask": 0},
                {"ID": 9201, "Flags": 0, "InventoryTypeSlotMask": 0},
            ],
            "ItemBonusTreeNode": [
                {
                    "ID": 30,
                    "ParentItemBonusTreeID": 9200,
                    "ChildItemBonusTreeID": 9201,
                    "ChildItemBonusListID": 0,
                    "ChildItemBonusListGroupID": 0,
                    "ChildItemLevelSelectorID": 0,
                },
                {
                    "ID": 31,
                    "ParentItemBonusTreeID": 9201,
                    "ChildItemBonusTreeID": 0,
                    "ChildItemBonusListID": 7305,
                    "ChildItemBonusListGroupID": 0,
                    "ChildItemLevelSelectorID": 0,
                    "ItemCreationContextGroupID": 9,
                },
            ],
            "ItemBonusList": [{"ID": 7305, "Flags": 0}],
            "ItemBonus": [{"ID": 5, "ParentItemBonusListID": 7305, "Type": 0}],
            # The exact ItemCreationContext=0 capture is intentionally empty.
            "ItemCreationContext": [],
        }
        variants = _build_item_variant_records(
            "2005",
            db2_rows=db2_rows,
            db2_refs={},
            official_payload={"level": 219},
            composition_context_values=["0"],
            allow_default_context_group_resolution=True,
            allow_default_context_numeric_evidence=True,
        )
        composed = [
            row
            for row in variants
            if row["variantComposition"]["kind"] == "db2_context_slot_vector"
        ]
        self.assertEqual(len(composed), 1)
        variant = composed[0]
        self.assertEqual(variant["rawGraphStatus"], "verified")
        self.assertEqual(variant["numericVariantEvidenceStatus"], "verified")
        self.assertEqual(
            variant["variantComposition"]["defaultContextGroupStatus"],
            "not_required",
        )
        self.assertEqual(
            variant["officialBaseItemLevelEvidence"]["resolution"],
            "tier_set_default_context_zero_rows_and_static_item_level",
        )
        self.assertNotIn(
            "OFFICIAL_DB2_ITEM_CREATION_CONTEXT_GROUP_SEMANTICS_UNVERIFIED",
            variant["reasonCodes"],
        )

    def test_tier_conversion_resolves_original_special_effect_semantics(self):
        fact = _conversion_fact(
            "2004",
            [{"setId": "2001"}],
            db2_rows={
                "ItemConversionEntry": [
                    {"ID": 1, "ItemID": 2004, "ItemConversionID": 9},
                ],
                "ItemConversion": [
                    {"ID": 9, "ItemBonusTreeID": 9300},
                ],
                "ItemBonusTreeNode": [
                    {
                        "ID": 1,
                        "ParentItemBonusTreeID": 9300,
                        "ChildItemBonusListID": 7301,
                        "ChildItemBonusTreeID": 0,
                    },
                ],
                "ItemBonusList": [{"ID": 7301, "Flags": 0}],
                "ItemBonus": [
                    {"ID": 2, "ParentItemBonusListID": 7301, "Type": 0},
                ],
                "ItemXItemEffect": [
                    {"ID": 40, "ItemID": 2004, "ItemEffectID": 500},
                ],
                "ItemEffect": [
                    {
                        "ID": 500,
                        "SpellID": 600,
                        "TriggerType": 0,
                        "LegacySlotIndex": 1,
                    },
                ],
                "Spell": [
                    {
                        "ID": 600,
                        "Name_lang": "Original proc",
                        "Description_lang": "Original effect text.",
                    },
                ],
                "SpellEffect": [
                    {
                        "ID": 601,
                        "SpellID": 600,
                        "EffectIndex": 0,
                        "Effect": 6,
                        "EffectBasePointsF": 10,
                    },
                ],
            },
            db2_refs={},
            static_row={
                "ID": 2004,
                "ItemLevel": 200,
                "StatModifier_bonusStat_0": 31,
            },
            official_payload={
                "id": 2004,
                "preview_item": {"bonus_list": [7301]},
            },
            official_set_facts={
                "2001": {
                    "setId": "2001",
                    "status": "verified",
                    "effects": [],
                    "evidenceRefs": [],
                },
            },
        )

        preservation = fact["preservation"]
        self.assertEqual(preservation["originalSpecialEffectStatus"], "verified")
        self.assertEqual(
            preservation["originalSpecialEffectFacts"][0]["spellId"],
            "600",
        )
        self.assertEqual(
            preservation["originalSpecialEffectFacts"][0]["spell"]["name"],
            "Original proc",
        )
        self.assertEqual(
            preservation["originalSpecialEffectFacts"][0]["spellEffects"][0]["spellId"],
            "600",
        )
        self.assertEqual(preservation["status"], "verified")

    def _inputs(self, directory: str):
        root = Path(directory)
        official = root / "official"
        crafted_api = root / "crafted-api"
        db2 = root / "db2"
        _prepare_official_capture(official)
        _prepare_official_capture(crafted_api)
        _prepare_db2_capture(db2)
        crafted_item = {
            "id": 1003,
            "name": "Crafted Boots",
            "is_equippable": True,
            "item_class": {"id": 4, "name": "Armor"},
            "item_subclass": {"id": 1, "name": "Cloth"},
            "inventory_type": {"type": "FEET", "name": "Feet"},
            "level": 197,
            "preview_item": {"bonus_list": ["300"]},
        }
        _official_entry(crafted_api, 3, "1003", crafted_item)
        _write_json(
            crafted_api / "capture-manifest.json",
            {
                "schemaRevision": "s2-official-api-item-closure-manifest-v1",
                "status": "captured",
                "sourceDb2Build": "12.1.0.69299",
                "entries": [
                    {
                        "path": "/data/wow/item/1003",
                        "responsePath": "raw/0003.json",
                        "responseBytes": (crafted_api / "raw/0003.json").stat().st_size,
                        "responseSha256": hashlib.sha256(
                            (crafted_api / "raw/0003.json").read_bytes()
                        ).hexdigest(),
                    }
                ],
            },
        )
        inventory = {
            "schemaRevision": "s2-official-capture-inventory-v1",
            "seasonKey": "midnight-season-2",
            "scopeContract": {
                "logicalSources": ["raid", "mythic_plus", "crafted", "tier_set"],
                "raidIncludesLair": True,
                "lairRawSourceTypePreserved": True,
                "tierSetIsIndependentMembershipDimension": True,
                "excludedSourceTypes": ["dungeon", "delve", "prey", "great_vault", "world_content"],
            },
            "sourceMemberships": [
                {
                    "logicalSource": "raid",
                    "rawSourceType": "lair",
                    "rawSourceKey": "lair:1",
                    "itemId": "1001",
                    "sourceMembershipStatus": "verified",
                },
                {
                    "logicalSource": "raid",
                    "rawSourceType": "raid",
                    "rawSourceKey": "raid:1",
                    "itemId": "1001",
                    "sourceMembershipStatus": "verified",
                },
            ],
            "tierSetMemberships": [
                {
                    "logicalSource": "tier_set",
                    "rawSourceType": "tier_set",
                    "rawSourceKey": "tier_set:1",
                    "itemId": "1002",
                    "setId": "2001",
                    "setEffectStatus": "verified",
                    "tierSetMembershipStatus": "verified",
                }
            ],
            "tierSetFacts": [{"setId": "2001", "setEffectStatus": "verified"}],
            "craftedRecipes": [
                {
                    "recipeId": "5001",
                    "logicalSource": "crafted",
                    "status": "blocked",
                    "outputStatus": "blocked",
                }
            ],
        }
        targets = {
            "schemaRevision": "s2-crafted-output-targets-v1",
            "status": "verified",
            "recipeRootCount": 1,
            "recipeOutputEdges": [
                {
                    "recipeId": "5001",
                    "itemId": "1003",
                    "spellId": "9001",
                    "craftingDataIds": ["7001"],
                    "status": "verified",
                }
            ],
        }
        return inventory, targets, official, crafted_api, {"scaling": db2}

    def test_closure_keeps_raw_lair_and_tier_membership_without_duplicate_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            inventory, targets, official, crafted_api, db2 = self._inputs(directory)
            report = build_s2_equipment_library_closure(
                inventory=inventory,
                crafted_targets=targets,
                official_api_captures=[official, crafted_api],
                db2_captures=db2,
            )

            self.assertEqual(report["scopeContract"]["logicalSources"], [
                "raid", "mythic_plus", "crafted", "tier_set"
            ])
            self.assertEqual(len(report["itemDefinitions"]), 3)
            self.assertEqual(
                {(row["rawSourceType"], row["rawSourceKey"]) for row in report["sourceMemberships"]},
                {("lair", "lair:1"), ("raid", "raid:1")},
            )
            self.assertEqual(report["itemDefinitions"][0]["itemId"], "1001")
            self.assertEqual(
                report["itemDefinitions"][0]["sourceMembershipCount"], 2
            )
            self.assertEqual(report["tierSetMemberships"][0]["itemId"], "1002")
            self.assertEqual(report["tierSetFacts"][0]["effects"][0]["requiredCount"], 2)
            self.assertEqual(
                report["tierSetFacts"][0]["effects"][0]["displayString"],
                "Set: Tier effect.",
            )
            self.assertEqual(report["craftedRelationships"][0]["itemId"], "1003")
            self.assertEqual(report["coverageCounts"]["fourSourceCandidateTotal"]["value"], 3)
            self.assertEqual(report["coverageCounts"]["blockedCount"], 3)
            self.assertEqual(
                report["coverageCounts"]["blockerCodeCount"],
                len(report["blockerCodes"]),
            )
            self.assertTrue(report["notARelease"])
            self.assertFalse(report["activeManifestChanged"])

    def test_closure_makes_missing_variant_and_simc_evidence_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            inventory, targets, official, crafted_api, db2 = self._inputs(directory)
            report = build_s2_equipment_library_closure(
                inventory=inventory,
                crafted_targets=targets,
                official_api_captures=[official, crafted_api],
                db2_captures=db2,
            )
            self.assertEqual(report["status"], "partial")
            self.assertEqual(report["coverageCounts"]["simcReadyCount"], 0)
            self.assertIn("VARIANT_TRACK_AUTHORITY_UNVERIFIED", report["blockerCodes"])
            self.assertIn("SIMC_MATRIX_NOT_RUN", report["blockerCodes"])
            self.assertEqual(report["variants"][0]["status"], "UNVERIFIED")
            self.assertEqual(
                report["variants"][0]["canonicalSimcInput"]["itemId"],
                "1001",
            )
            self.assertEqual(
                report["variants"][0]["canonicalSimcInput"]["bonusIds"],
                ["6001"],
            )
            self.assertEqual(
                report["variants"][0]["canonicalSimcInput"]["status"],
                "blocked",
            )
            self.assertEqual(report["variants"][0]["itemScalingEvidence"][0]["itemLevel"], 266)
            curve_evidence = next(
                row for row in report["variants"][0]["itemScalingEvidence"]
                if row["scalingConfigId"] == "484"
            )
            self.assertEqual(curve_evidence["curveEvidenceStatus"], "observed")
            self.assertEqual(curve_evidence["curveId"], "92772")
            self.assertEqual(curve_evidence["curvePointIds"], ["1"])
            item_variants = [
                row for row in report["variants"] if row["itemId"] == "1001"
            ]
            self.assertEqual(len(item_variants), 3)
            self.assertEqual(
                {row["bonusListIds"][-1] for row in item_variants},
                {"6001", "6002", "6003"},
            )
            type50 = next(
                row["bonusType50Evidence"]
                for row in item_variants
                if "6002" in row["bonusListIds"]
            )
            self.assertEqual(type50[0]["value0"], 13485)
            self.assertIn(
                "BONUS_TYPE_50_SEMANTICS_UNVERIFIED",
                next(
                    row["reasonCodes"]
                    for row in item_variants
                    if "6002" in row["bonusListIds"]
                ),
            )
            group_variant = next(
                row for row in item_variants if "6002" in row["bonusListIds"]
            )
            self.assertEqual(
                group_variant["upgradeGroupEvidence"]["groupId"], "7001"
            )
            self.assertEqual(
                group_variant["upgradeGroupEvidence"]["status"], "observed"
            )
            self.assertEqual(
                group_variant["upgradeGroupEvidence"]["groupFact"]["PlayerConditionID"],
                143187,
            )
            delta = next(
                row
                for row in next(
                    variant["bonusListLevelDeltaEvidence"]
                    for variant in item_variants
                    if "6001" in variant["bonusListIds"]
                )
                if row["bonusListId"] == "6001"
            )
            self.assertEqual(delta["status"], "verified")
            self.assertEqual(delta["itemLevelDelta"], 3)

    def test_closure_rejects_scope_expansion(self):
        with tempfile.TemporaryDirectory() as directory:
            inventory, targets, official, crafted_api, db2 = self._inputs(directory)
            inventory["scopeContract"]["logicalSources"].append("world_content")
            with self.assertRaisesRegex(S2EquipmentLibraryClosureError, "logicalSources"):
                build_s2_equipment_library_closure(
                    inventory=inventory,
                    crafted_targets=targets,
                    official_api_captures=[official, crafted_api],
                    db2_captures=db2,
                )

    def test_compact_variant_report_keeps_join_keys_without_repeating_capture_refs(self):
        with tempfile.TemporaryDirectory() as directory:
            inventory, targets, official, crafted_api, db2 = self._inputs(directory)
            report = build_s2_equipment_library_closure(
                inventory=inventory,
                crafted_targets=targets,
                official_api_captures=[official, crafted_api],
                db2_captures=db2,
                detailed_variants=False,
            )
            variant = report["variants"][0]
            self.assertIn("evidenceKeys", variant)
            self.assertNotIn("evidenceRefs", variant)
            self.assertIn("nodeIds", variant["evidenceKeys"])
            self.assertNotIn("evidenceRefs", variant["itemScalingEvidence"][0])

    def test_runtime_identity_is_bound_without_clearing_unrun_simc_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            inventory, targets, official, crafted_api, db2 = self._inputs(directory)
            report = build_s2_equipment_library_closure(
                inventory=inventory,
                crafted_targets=targets,
                official_api_captures=[official, crafted_api],
                db2_captures=db2,
                simc_runtime_identity=(
                    "simc:12.1.0.69299:"
                    "f50a2121bf894570146507496f3e113bff68e445:"
                    "69b3e5fb56f3b7149fa239059cb510f1924ef5cd6690db718812df4d938172da"
                ),
            )
            self.assertEqual(
                report["simcRuntimeIdentity"],
                "simc:12.1.0.69299:f50a2121bf894570146507496f3e113bff68e445:"
                "69b3e5fb56f3b7149fa239059cb510f1924ef5cd6690db718812df4d938172da",
            )
            self.assertNotIn(
                "SIMC_RUNTIME_IDENTITY_UNAVAILABLE",
                report["blockerCodes"],
            )
            self.assertIn("SIMC_MATRIX_NOT_RUN", report["blockerCodes"])

    def test_verified_candidate_matrix_evidence_replaces_unrun_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            inventory, targets, official, crafted_api, db2 = self._inputs(directory)
            runtime = (
                "simc:12.1.0.69299:"
                "f50a2121bf894570146507496f3e113bff68e445:"
                "69b3e5fb56f3b7149fa239059cb510f1924ef5cd6690db718812df4d938172da"
            )
            baseline = build_s2_equipment_library_closure(
                inventory=inventory,
                crafted_targets=targets,
                official_api_captures=[official, crafted_api],
                db2_captures=db2,
                simc_runtime_identity=runtime,
            )
            matrix = {
                "schemaRevision": "s2-equipment-library-simc-matrix-report-v1",
                "reportId": "s2-equipment-library-simc-matrix:test",
                "status": "partial",
                "runtimeIdentity": runtime,
                "runtimeIdentityStatus": "verified",
                "candidateReportId": baseline["reportId"],
                "blockerCodes": ["SIMC_ENHANCEMENT_MATRIX_UNVERIFIED"],
                "counts": {
                    "publicVariantExpectedCount": 3,
                    "publicVariantProbeCount": 3,
                    "publicVariantVerifiedCount": 3,
                    "setConversionExpectedCount": 0,
                    "setConversionVerifiedCount": 0,
                    "representativeProfileExpectedCount": 0,
                    "representativeProfileVerifiedCount": 0,
                },
                "publicVariantMatrix": {"status": "verified"},
                "setConversionMatrix": {"status": "verified"},
                "representativeProfileMatrix": {"status": "verified"},
                "enhancementMatrix": {"status": "UNVERIFIED"},
            }
            report = build_s2_equipment_library_closure(
                inventory=inventory,
                crafted_targets=targets,
                official_api_captures=[official, crafted_api],
                db2_captures=db2,
                simc_runtime_identity=runtime,
                simc_matrix=matrix,
            )
            self.assertNotIn("SIMC_MATRIX_NOT_RUN", report["blockerCodes"])
            self.assertIn("SIMC_ENHANCEMENT_MATRIX_UNVERIFIED", report["blockerCodes"])
            self.assertEqual(
                report["simcMatrixEvidence"]["reportId"],
                "s2-equipment-library-simc-matrix:test",
            )
            self.assertEqual(
                report["coverageCounts"]["simcMatrix"]["publicVariantVerifiedCount"],
                3,
            )

    def test_simc_matrix_attachment_does_not_change_candidate_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            inventory, targets, official, crafted_api, db2 = self._inputs(directory)
            runtime = (
                "simc:12.1.0.69299:"
                "f50a2121bf894570146507496f3e113bff68e445:"
                "69b3e5fb56f3b7149fa239059cb510f1924ef5cd6690db718812df4d938172da"
            )
            baseline = build_s2_equipment_library_closure(
                inventory=inventory,
                crafted_targets=targets,
                official_api_captures=[official, crafted_api],
                db2_captures=db2,
                simc_runtime_identity=runtime,
            )
            self.assertEqual(
                baseline["reportId"],
                _candidate_identity_report_id(baseline),
            )
            matrix = {
                "schemaRevision": "s2-equipment-library-simc-matrix-report-v1",
                "reportId": "s2-equipment-library-simc-matrix:identity-test",
                "status": "verified",
                "runtimeIdentity": runtime,
                "runtimeIdentityStatus": "verified",
                "candidateReportId": "s2-equipment-library-closure:legacy-candidate",
                "candidateIdentity": baseline["reportId"],
                "blockerCodes": [],
                "counts": {
                    "publicVariantExpectedCount": 3,
                    "publicVariantProbeCount": 3,
                    "publicVariantVerifiedCount": 3,
                    "setConversionExpectedCount": 0,
                    "setConversionVerifiedCount": 0,
                    "representativeProfileExpectedCount": 0,
                    "representativeProfileVerifiedCount": 0,
                },
                "publicVariantMatrix": {"status": "verified"},
                "craftedVariantMatrix": {"status": "not_applicable"},
                "setConversionMatrix": {"status": "verified"},
                "representativeProfileMatrix": {"status": "verified"},
                "enhancementMatrix": {"status": "verified"},
            }
            report = build_s2_equipment_library_closure(
                inventory=inventory,
                crafted_targets=targets,
                official_api_captures=[official, crafted_api],
                db2_captures=db2,
                simc_runtime_identity=runtime,
                simc_matrix=matrix,
            )
            self.assertEqual(report["reportId"], baseline["reportId"])
            self.assertEqual(
                report["simcMatrixEvidence"]["baselineCandidateReportId"],
                baseline["reportId"],
            )

    def test_runtime_identity_exposes_db2_build_mismatch_as_a_blocker(self):
        with tempfile.TemporaryDirectory() as directory:
            inventory, targets, official, crafted_api, db2 = self._inputs(directory)
            db2_manifest_path = Path(db2["scaling"]) / "capture-manifest.json"
            db2_manifest = json.loads(db2_manifest_path.read_text(encoding="utf-8"))
            db2_manifest["clientBuild"] = "12.1.0.68914"
            db2_manifest_path.write_text(
                json.dumps(db2_manifest, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            report = build_s2_equipment_library_closure(
                inventory=inventory,
                crafted_targets=targets,
                official_api_captures=[official, crafted_api],
                db2_captures=db2,
                simc_runtime_identity=(
                    "simc:12.1.0.69299:"
                    "f50a2121bf894570146507496f3e113bff68e445:"
                    "69b3e5fb56f3b7149fa239059cb510f1924ef5cd6690db718812df4d938172da"
                ),
            )

            self.assertIn("SIMC_RUNTIME_DB2_BUILD_MISMATCH", report["blockerCodes"])
            self.assertEqual(report["db2ClientBuilds"], ["12.1.0.68914"])

    def test_closure_uses_crafted_compatibility_evidence_for_recipe_edges(self):
        with tempfile.TemporaryDirectory() as directory:
            inventory, targets, official, crafted_api, db2 = self._inputs(directory)
            crafted_compatibility = {
                "schemaRevision": "s2-crafted-compatibility-evidence-v1",
                "status": "verified",
                "blockerCodes": [],
                "recipes": [
                    {
                        "recipeId": "5001",
                        "secondaryStatCompatibility": {
                            "status": "verified",
                            "options": [{"itemId": "9101", "kind": "item"}],
                            "evidenceRefs": ["official-api:/data/wow/modified-crafting/reagent-slot-type/393"],
                        },
                        "embellishmentCompatibility": {
                            "status": "not_applicable",
                            "options": [],
                            "evidenceRefs": [],
                        },
                        "enhancementCompatibility": {
                            "status": "verified",
                            "options": [{"currencyTypeId": "3446", "kind": "currency"}],
                            "evidenceRefs": ["db2-response:crafted-category-db2-v3/response.json"],
                        },
                        "evidenceStatus": "verified",
                    }
                ],
            }
            report = build_s2_equipment_library_closure(
                inventory=inventory,
                crafted_targets=targets,
                official_api_captures=[official, crafted_api],
                db2_captures=db2,
                crafted_compatibility=crafted_compatibility,
            )
            crafted = report["craftedRelationships"][0]
            self.assertEqual(crafted["secondaryStatCompatibility"]["status"], "verified")
            self.assertEqual(crafted["enhancementCompatibility"]["options"][0]["currencyTypeId"], "3446")
            self.assertNotIn("CRAFTED_ENHANCEMENT_SEMANTICS_UNVERIFIED", report["blockerCodes"])
            self.assertEqual(
                report["evidencePacket"]["fieldOwners"]["craftedOptionSemantics"],
                "official_api_slot_type_plus_bounded_db2_currency_or_item_adapter",
            )


if __name__ == "__main__":
    unittest.main()

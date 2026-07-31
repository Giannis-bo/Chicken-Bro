import unittest

from server.season_pve_official_capture import (
    OfficialCaptureContractError,
    bounded_capture_result,
    canonical_official_name,
    equipment_recipe_refs,
    exact_item_search_matches,
    index_official_item_search,
    journal_loot_reference,
    recipe_candidates_from_complete_item_index,
    select_journal_targets,
    validate_official_item_range_page,
)
from server.season_pve_event_schedule import (
    select_active_timewalking_rotation,
)


class SeasonPveOfficialCaptureTest(unittest.TestCase):
    def test_timewalking_rotation_is_selected_by_audit_instant(self):
        rotations = [
            {
                "rotationKey": "battle-for-azeroth",
                "startsAt": "2026-07-07T00:00:00Z",
                "endsAt": "2026-07-14T00:00:00Z",
                "dungeonNames": ["Atal'Dazar", "Freehold"],
            },
            {
                "rotationKey": "the-burning-crusade",
                "startsAt": "2026-07-28T00:00:00Z",
                "endsAt": "2026-08-04T00:00:00Z",
                "dungeonNames": ["Magisters' Terrace", "Mana-Tombs"],
            },
            {
                "rotationKey": "dragonflight-final",
                "startsAt": "2026-08-04T00:00:00Z",
                "endsAt": "2026-08-12T00:00:00Z",
                "dungeonNames": ["Algeth'ar Academy", "Neltharus"],
            },
        ]

        selected = select_active_timewalking_rotation(
            rotations,
            "2026-07-30T10:19:14Z",
        )

        self.assertEqual(selected["rotationKey"], "the-burning-crusade")
        self.assertEqual(
            selected["dungeonNames"],
            ["Magisters' Terrace", "Mana-Tombs"],
        )
        self.assertEqual(
            select_active_timewalking_rotation(
                rotations,
                "2026-08-04T00:00:00Z",
            )["rotationKey"],
            "dragonflight-final",
        )
        with self.assertRaisesRegex(
            OfficialCaptureContractError,
            "exactly one active rotation",
        ):
            select_active_timewalking_rotation(
                rotations,
                "2026-07-20T00:00:00Z",
            )

    def test_canonical_name_normalizes_official_typography(self):
        self.assertEqual(
            canonical_official_name("Response Team’s  Tower\u00a0Shield"),
            canonical_official_name("Response Team's Tower Shield"),
        )
        self.assertEqual(
            canonical_official_name("Rotmire’s Sporeheart"),
            canonical_official_name("Rotmire's Sporeheart"),
        )

    def test_item_search_requires_uncapped_complete_equippable_level_90_page(self):
        payload = {
            "page": 1,
            "pageCount": 1,
            "pageSize": 2,
            "maxPageSize": 1000,
            "resultCountCapped": False,
            "results": [
                {
                    "data": {
                        "id": 237932,
                        "name": {"en_US": "Primalforged Heavy Axe"},
                        "required_level": 90,
                        "is_equippable": True,
                    }
                },
                {
                    "data": {
                        "id": 268291,
                        "name": {"en_US": "Rotmire's Sporeheart"},
                        "required_level": 90,
                        "is_equippable": True,
                    }
                },
            ],
        }

        indexed = index_official_item_search(payload)

        self.assertEqual(
            indexed[canonical_official_name("Rotmire’s Sporeheart")][0]["id"],
            268291,
        )

        for drift in (
            {"resultCountCapped": True},
            {"pageCount": 2},
            {"pageSize": 1},
        ):
            with self.subTest(drift=drift), self.assertRaises(
                OfficialCaptureContractError
            ):
                index_official_item_search({**payload, **drift})

        with self.assertRaises(OfficialCaptureContractError):
            index_official_item_search(
                {
                    **payload,
                    "results": [
                        {
                            "data": {
                                "id": 1,
                                "name": {"en_US": "Not Equipment"},
                                "required_level": 90,
                                "is_equippable": False,
                            }
                        }
                    ],
                    "pageSize": 1,
                }
            )

    def test_equipment_recipe_refs_include_power_gear_and_exclude_pvp_and_profession_tools(self):
        skill_tier = {
            "categories": [
                {
                    "name": "Weapons",
                    "recipes": [
                        {"id": 52349, "name": "Primalforged Heavy Axe"},
                        {
                            "id": 57186,
                            "name": "Thalassian Competitor's Rifle",
                        },
                    ],
                },
                {
                    "name": "Profession Equipment",
                    "recipes": [{"id": 1, "name": "Blacksmith Hammer"}],
                },
                {
                    "name": "Competitor's Plate (PvP)",
                    "recipes": [{"id": 2, "name": "Competitor Plate"}],
                },
            ]
        }

        rows = equipment_recipe_refs(
            "Blacksmithing",
            skill_tier,
        )

        self.assertEqual(
            rows,
            [
                {
                    "profession": "Blacksmithing",
                    "category": "Weapons",
                    "recipeId": "52349",
                    "name": "Primalforged Heavy Axe",
                }
            ],
        )

    def test_exact_item_search_filters_fuzzy_rows_and_rejects_truncation(self):
        payload = {
            "page": 1,
            "pageCount": 1,
            "pageSize": 2,
            "resultCountCapped": False,
            "results": [
                {
                    "data": {
                        "id": 237932,
                        "name": {"en_US": "Primalforged Heavy Axe"},
                        "required_level": 80,
                        "is_equippable": True,
                    }
                },
                {
                    "data": {
                        "id": 100,
                        "name": {"en_US": "Heavy Axe"},
                        "required_level": 1,
                        "is_equippable": True,
                    }
                },
            ],
        }

        matches = exact_item_search_matches(
            payload,
            "Primalforged Heavy Axe",
        )

        self.assertEqual([row["id"] for row in matches], [237932])
        with self.assertRaises(OfficialCaptureContractError):
            exact_item_search_matches(
                {**payload, "resultCountCapped": True},
                "Primalforged Heavy Axe",
            )
        with self.assertRaises(OfficialCaptureContractError):
            exact_item_search_matches(
                {**payload, "pageCount": 2},
                "Primalforged Heavy Axe",
            )

    def test_recipe_candidates_only_use_the_complete_level_90_item_index(self):
        item_index = {
            canonical_official_name("Primalforged Heavy Axe"): [
                {"id": 237932, "name": {"en_US": "Primalforged Heavy Axe"}},
            ],
            canonical_official_name("Duplicate Name"): [
                {"id": 100, "name": {"en_US": "Duplicate Name"}},
                {"id": 101, "name": {"en_US": "Duplicate Name"}},
            ],
        }

        unique = recipe_candidates_from_complete_item_index(
            item_index,
            "Primalforged Heavy Axe",
        )
        ambiguous = recipe_candidates_from_complete_item_index(
            item_index,
            "Duplicate Name",
        )
        missing = recipe_candidates_from_complete_item_index(
            item_index,
            "Blood-Tempered Bracers",
        )

        self.assertEqual(unique["candidateJoinMethod"], "level_90_equippable_name_unique")
        self.assertEqual([row["id"] for row in unique["matches"]], [237932])
        self.assertEqual(
            ambiguous["candidateJoinMethod"],
            "level_90_equippable_name_ambiguous",
        )
        self.assertEqual([row["id"] for row in ambiguous["matches"]], [100, 101])
        self.assertEqual(missing, {"candidateJoinMethod": "none", "matches": []})

    def test_item_range_page_uses_id_cursor_without_accepting_a_cap(self):
        capped = {
            "page": 1,
            "pageCount": 1,
            "pageSize": 2,
            "maxPageSize": 2,
            "resultCountCapped": True,
            "results": [
                {
                    "data": {
                        "id": 230001,
                        "is_equippable": True,
                        "name": {"en_US": "First"},
                    }
                },
                {
                    "data": {
                        "id": 230010,
                        "is_equippable": True,
                        "name": {"en_US": "Second"},
                    }
                },
            ],
        }

        first = validate_official_item_range_page(
            capped,
            start_id=230000,
            end_id=280000,
        )
        bounded_request = validate_official_item_range_page(
            {
                **capped,
                "pageCount": 4,
                "maxPageSize": 1000,
            },
            start_id=230000,
            end_id=280000,
            expected_page_size=2,
        )
        uncapped_payload = {
            **capped,
            "pageCount": 4,
        }
        del uncapped_payload["resultCountCapped"]
        uncapped_multi_page = validate_official_item_range_page(
            uncapped_payload,
            start_id=230000,
            end_id=280000,
            expected_page_size=2,
        )
        terminal = validate_official_item_range_page(
            {
                **capped,
                "pageSize": 1,
                "maxPageSize": 2,
                "resultCountCapped": False,
                "results": [
                    {
                        "data": {
                            "id": 230020,
                            "is_equippable": True,
                            "name": {"en_US": "Last"},
                        }
                    }
                ],
            },
            start_id=230011,
            end_id=280000,
        )
        empty_terminal = validate_official_item_range_page(
            {
                "page": 1,
                "pageCount": 0,
                "pageSize": 0,
                "maxPageSize": 2,
                "resultCountCapped": False,
                "results": [],
            },
            start_id=230021,
            end_id=280000,
        )

        self.assertEqual(first["nextCursor"], 230011)
        self.assertEqual(bounded_request["nextCursor"], 230011)
        self.assertEqual(uncapped_multi_page["nextCursor"], 230011)
        self.assertFalse(first["terminal"])
        self.assertFalse(uncapped_multi_page["terminal"])
        self.assertEqual(terminal["nextCursor"], None)
        self.assertTrue(terminal["terminal"])
        self.assertEqual(empty_terminal["rows"], [])
        self.assertTrue(empty_terminal["terminal"])

        for drift in (
            {"page": 2},
            {"pageSize": 1},
            {"resultCountCapped": None},
            {"results": list(reversed(capped["results"]))},
            {
                "results": [
                    {
                        "data": {
                            "id": 229999,
                            "is_equippable": True,
                            "name": {"en_US": "Outside"},
                        }
                    }
                ],
                "pageSize": 1,
                "resultCountCapped": False,
            },
        ):
            with self.subTest(drift=drift), self.assertRaises(
                OfficialCaptureContractError
            ):
                validate_official_item_range_page(
                    {**capped, **drift},
                    start_id=230000,
                    end_id=280000,
                )
        with self.assertRaises(OfficialCaptureContractError):
            validate_official_item_range_page(
                {
                    **capped,
                    "maxPageSize": 1000,
                },
                start_id=230000,
                end_id=280000,
                expected_page_size=3,
            )

    def test_journal_targets_are_source_partitioned_and_timewalking_is_as_of_specific(self):
        mythic_dungeons = [
            {
                "id": 558,
                "name": "Magisters' Terrace",
                "dungeon": {"id": 1300, "name": "Magisters' Terrace"},
            },
            {
                "id": 402,
                "name": "Algeth'ar Academy",
                "dungeon": {"id": 1201, "name": "Algeth'ar Academy"},
            },
        ]
        midnight_expansion = {
            "dungeons": [
                {"id": 1300, "name": "Magisters' Terrace"},
                {"id": 1304, "name": "Murder Row"},
            ],
            "raids": [
                {"id": 1307, "name": "The Voidspire"},
                {"id": 1312, "name": "Midnight"},
                {"id": 1305, "name": "Sporefall"},
            ],
        }
        journal_index = {
            "instances": [
                {"id": 249, "name": "Magisters' Terrace"},
                {"id": 250, "name": "Mana-Tombs"},
            ]
        }

        result = select_journal_targets(
            mythic_dungeons=mythic_dungeons,
            midnight_expansion=midnight_expansion,
            journal_instance_index=journal_index,
            timewalking_names=["Magisters' Terrace", "Mana-Tombs"],
        )

        self.assertEqual(
            [row["instanceId"] for row in result["mythic_plus"]],
            ["1201", "1300"],
        )
        self.assertEqual(
            [row["instanceId"] for row in result["midnight_dungeon"]],
            ["1300", "1304"],
        )
        self.assertEqual(
            [row["instanceId"] for row in result["midnight_raid"]],
            ["1305", "1307"],
        )
        self.assertEqual(
            [row["instanceId"] for row in result["midnight_world_boss"]],
            ["1312"],
        )
        self.assertEqual(
            [row["instanceId"] for row in result["timewalking"]],
            ["249", "250"],
        )
        self.assertEqual(result["gaps"], [])

        missing = select_journal_targets(
            mythic_dungeons=mythic_dungeons,
            midnight_expansion=midnight_expansion,
            journal_instance_index=journal_index,
            timewalking_names=["The Blood Furnace"],
        )
        self.assertEqual(
            missing["gaps"][0]["reasonCode"],
            "OFFICIAL_JOURNAL_INSTANCE_NOT_FOUND",
        )

    def test_journal_loot_reference_preserves_relation_identity(self):
        first = journal_loot_reference(
            {
                "id": 23199,
                "item": {
                    "id": 109759,
                    "name": "Ro-Ger's Brown Diamond Seal",
                },
            }
        )
        second = journal_loot_reference(
            {
                "id": 46612,
                "item": {
                    "id": 109759,
                    "name": "Ro-Ger's Brown Diamond Seal",
                },
            }
        )

        self.assertEqual(first["itemId"], second["itemId"])
        self.assertNotEqual(first["lootRelationId"], second["lootRelationId"])

        with self.assertRaises(OfficialCaptureContractError):
            journal_loot_reference({"item": {"id": 109759}})

    def test_console_result_is_bounded_and_does_not_repeat_item_contexts(self):
        result = bounded_capture_result(
            {
                "schemaRevision": "season-pve-official-capture-v1",
                "status": "blocked",
                "capturedAt": "2026-07-30T10:08:30Z",
                "asOf": "2026-07-30T10:08:30Z",
                "requestCount": 333,
                "requestBytes": 5208171,
                "officialItemSearch": {"itemCount": 977},
                "mythicSeason": {"seasonId": "17"},
                "journalCapture": {
                    "instanceCount": 23,
                    "encounterCount": 81,
                    "itemCount": 1292,
                    "itemContexts": {"109759": [{"large": "payload"}]},
                },
                "professionCapture": {
                    "recipeCount": 185,
                    "resolvedPveEquipmentRecipeCount": 76,
                },
                "classSetCapture": {"setCount": 13},
                "gaps": [{"reasonCode": "EXAMPLE"}],
            }
        )

        self.assertEqual(
            result["journalCapture"],
            {
                "instanceCount": 23,
                "encounterCount": 81,
                "itemCount": 1292,
            },
        )
        self.assertNotIn("itemContexts", result["journalCapture"])
        self.assertEqual(result["gapCount"], 1)


if __name__ == "__main__":
    unittest.main()

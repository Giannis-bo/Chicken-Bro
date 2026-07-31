import unittest

from server.season_pve_journal_relations import (
    ClientJournalRelationError,
    build_current_client_journal_membership,
)


class SeasonPveJournalRelationsTest(unittest.TestCase):
    def test_builds_source_difficulty_relations_and_uses_raid_restrictions(self):
        journal_capture = {
            "itemContexts": {
                "1001": [
                    {
                        "encounterId": "2001",
                        "encounterName": "Dungeon Boss",
                        "instanceId": "3001",
                        "instanceName": "Dungeon",
                        "lootRelationId": "4001",
                        "sourceGroup": "midnight_dungeon",
                    }
                ],
                "1002": [
                    {
                        "encounterId": "2002",
                        "encounterName": "Raid Boss",
                        "instanceId": "3002",
                        "instanceName": "The Voidspire",
                        "lootRelationId": "4002",
                        "sourceGroup": "midnight_raid",
                    }
                ],
                "1003": [
                    {
                        "encounterId": "2003",
                        "encounterName": "Old Boss",
                        "instanceId": "3003",
                        "instanceName": "Old Dungeon",
                        "lootRelationId": "4003",
                        "sourceGroup": "timewalking",
                    }
                ],
            }
        }
        encounter_items = [
            {"id": "5001", "id_encounter": "2001", "id_item": "1001"},
            {"id": "5002", "id_encounter": "2002", "id_item": "1002"},
            {"id": "5003", "id_encounter": "2003", "id_item": "1003"},
        ]
        item_difficulties = [
            {"id_parent": "5002", "id_difficulty": "15"},
            {"id_parent": "5002", "id_difficulty": "16"},
        ]
        difficulties = [
            {"id": "2", "name": "Heroic"},
            {"id": "14", "name": "Normal Raid"},
            {"id": "15", "name": "Heroic Raid"},
            {"id": "16", "name": "Mythic Raid"},
            {"id": "17", "name": "Raid Finder"},
            {"id": "23", "name": "Mythic"},
            {"id": "24", "name": "Timewalking"},
        ]

        result = build_current_client_journal_membership(
            journal_capture,
            encounter_items,
            item_difficulties,
            difficulties,
            client_build="12.0.7.68887",
        )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["summary"]["relationCount"], 3)
        by_item = {row["itemId"]: row for row in result["relations"]}
        self.assertEqual(
            by_item["1001"]["difficultyKeys"],
            ["heroic", "mythic"],
        )
        self.assertEqual(
            by_item["1002"]["difficultyKeys"],
            ["heroic", "mythic"],
        )
        self.assertEqual(
            by_item["1003"]["difficultyKeys"],
            ["timewalking"],
        )
        self.assertEqual(
            by_item["1002"]["sourceKey"],
            "raid:midnight-season-1-core",
        )

    def test_missing_current_client_relation_blocks_instead_of_falling_back(self):
        journal_capture = {
            "itemContexts": {
                "1001": [
                    {
                        "encounterId": "2001",
                        "encounterName": "Boss",
                        "instanceId": "3001",
                        "instanceName": "Dungeon",
                        "lootRelationId": "4001",
                        "sourceGroup": "mythic_plus",
                    }
                ]
            }
        }

        with self.assertRaisesRegex(
            ClientJournalRelationError,
            "missing current client JournalEncounterItem relation",
        ):
            build_current_client_journal_membership(
                journal_capture,
                [],
                [],
                [],
                client_build="12.0.7.68887",
            )


if __name__ == "__main__":
    unittest.main()

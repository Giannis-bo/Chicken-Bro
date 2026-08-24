import unittest

from server.s2_journal_item_scope import classify_mythic_plus_journal_item_scope


class S2JournalItemScopeTest(unittest.TestCase):
    def test_non_mythic_plus_difficulty_specific_item_is_explicitly_excluded(self):
        result = classify_mythic_plus_journal_item_scope(
            {
                "itemId": "158344",
                "rawSourceKey": "mythic_plus:journal-instance:1041:encounter:2172",
            },
            db2_rows={
                "JournalEncounterItem": [
                    {
                        "ID": 39401,
                        "JournalEncounterID": 2172,
                        "ItemID": 158344,
                        "DifficultyMask": 2,
                        "DisplaySeasonID": 0,
                        "WorldStateExpressionID": 52105,
                    }
                ]
            },
            db2_refs={
                (
                    "JournalEncounterItem",
                    '{"DifficultyMask":2,"DisplaySeasonID":0,"ID":39401,"ItemID":158344,"JournalEncounterID":2172,"WorldStateExpressionID":52105}',
                ): ["db2-response:journal/rows/0"],
            },
        )
        self.assertEqual(result["status"], "excluded")
        self.assertFalse(result["includeInMythicPlusMembership"])
        self.assertEqual(
            result["reasonCode"],
            "OUT_OF_SCOPE_NON_MPLUS_JOURNAL_DIFFICULTY_MASK",
        )
        self.assertEqual(result["evidenceRefs"], ["db2-response:journal/rows/0"])

    def test_all_difficulty_journal_item_is_included_and_keeps_raw_evidence(self):
        result = classify_mythic_plus_journal_item_scope(
            {
                "itemId": "239045",
                "rawSourceKey": "mythic_plus:journal-instance:1041:encounter:2172",
            },
            db2_rows={
                "JournalEncounterItem": [
                    {
                        "ID": 46226,
                        "JournalEncounterID": 2172,
                        "ItemID": 239045,
                        "DifficultyMask": -1,
                        "DisplaySeasonID": 0,
                        "WorldStateExpressionID": 0,
                    }
                ]
            },
            db2_refs={},
        )
        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["includeInMythicPlusMembership"])
        self.assertIsNone(result["reasonCode"])
        self.assertEqual(result["difficultyMasks"], [-1])

    def test_missing_journal_row_stays_unverified(self):
        result = classify_mythic_plus_journal_item_scope(
            {
                "itemId": "239045",
                "rawSourceKey": "mythic_plus:journal-instance:1041:encounter:2172",
            },
            db2_rows={"JournalEncounterItem": []},
            db2_refs={},
        )
        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertFalse(result["includeInMythicPlusMembership"])
        self.assertEqual(
            result["reasonCode"],
            "OFFICIAL_DB2_JOURNAL_ENCOUNTER_ITEM_ROW_MISSING",
        )


if __name__ == "__main__":
    unittest.main()

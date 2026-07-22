import copy
import unittest

from server import community_winner_projection


class CommunityWinnerProjectionTest(unittest.TestCase):
    def candidate(self, candidate_id, rank, **overrides):
        value = {
            "candidateId": candidate_id,
            "classKey": "mage",
            "specKey": "frost",
            "heroKey": "frostfire",
            "scenarioKey": "mythic_plus",
            "talentCandidateRank": rank,
            "sourceKey": "raiderio",
            "sourceUrl": f"https://raider.io/characters/cn/example/{candidate_id}",
            "profileHash": f"profile:{candidate_id}",
            "sourceIdentity": f"raiderio:cn|example|{candidate_id}",
            "playerName": candidate_id,
        }
        value.update(overrides)
        return value

    def validated_template(self, candidate, gear):
        if not gear or gear.get("legal") is not True:
            return {
                "status": "blocked",
                "problems": [{"code": "GEAR_LEGALITY_FAILED"}],
            }
        return {
            "status": "verified",
            "template": {
                "gearHash": gear["gearHash"],
                "selectionIntent": gear["selectionIntent"],
                "importEvidence": gear["importEvidence"],
            },
            "problems": [],
        }

    def gear_by_identity(self, *candidates):
        return {
            community_winner_projection.candidate_identity(candidate): {
                "legal": True,
                "gearHash": f"gear:{candidate['candidateId']}",
                "selectionIntent": {"slots": {"head": {"itemId": "head-1", "variantKey": "head-v1"}}},
                "importEvidence": {"sourceFingerprint": f"source:{candidate['candidateId']}"},
            }
            for candidate in candidates
        }

    def test_projection_reuses_rank_one_talent_winner_when_its_gear_is_legal(self):
        first = self.candidate("talent-rank-1", 1)
        second = self.candidate("talent-rank-2", 2)

        result = community_winner_projection.project_hero_slot(
            [second, first],
            self.gear_by_identity(first, second),
            self.validated_template,
        )

        self.assertEqual(result["slotStatus"], "covered")
        self.assertEqual(result["winner"]["candidateId"], "talent-rank-1")
        self.assertEqual(result["winner"]["talentWinnerId"], "talent-rank-1")
        self.assertEqual(result["winner"]["gearProjectionMode"], "talent_winner")
        self.assertEqual(result["winner"]["heroKey"], "frostfire")
        self.assertEqual(result["rejected"], [])

    def test_projection_uses_next_same_hero_candidate_when_rank_one_gear_is_illegal(self):
        first = self.candidate("talent-rank-1", 1)
        second = self.candidate("talent-rank-2", 2)
        gear = self.gear_by_identity(first, second)
        gear[community_winner_projection.candidate_identity(first)] = {"legal": False}
        original_first = copy.deepcopy(first)

        result = community_winner_projection.project_hero_slot(
            [first, second],
            gear,
            self.validated_template,
        )

        self.assertEqual(first, original_first)
        self.assertEqual(result["winner"]["candidateId"], "talent-rank-2")
        self.assertEqual(result["winner"]["talentWinnerId"], "talent-rank-1")
        self.assertEqual(result["winner"]["gearProjectionMode"], "gear_fallback")
        self.assertEqual(result["rejected"][0]["candidateId"], "talent-rank-1")
        self.assertEqual(result["rejected"][0]["problems"][0]["code"], "GEAR_LEGALITY_FAILED")

    def test_projection_rejects_cross_hero_or_baseline_candidates_and_reports_pending(self):
        frostfire = self.candidate("talent-rank-1", 1)
        different_hero = self.candidate("spellslinger-rank-1", 2, heroKey="spellslinger")
        baseline = self.candidate("baseline", 3, sourceKey="recommended_bis")

        result = community_winner_projection.project_hero_slot(
            [frostfire, different_hero, baseline],
            {},
            self.validated_template,
        )

        self.assertEqual(result["winner"], None)
        self.assertEqual(result["slotStatus"], "pending_collection")
        self.assertEqual(
            [item["problems"][0]["code"] for item in result["rejected"]],
            ["GEAR_LEGALITY_FAILED", "HERO_SLOT_MISMATCH", "TALENT_SOURCE_NOT_RAIDERIO"],
        )


if __name__ == "__main__":
    unittest.main()

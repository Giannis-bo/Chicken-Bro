import copy
import unittest

from server.observed_build_ingest import (
    select_distinct_snapshot_winners,
    snapshot_candidates_from_raiderio,
)


class ObservedBuildIngestTest(unittest.TestCase):
    @staticmethod
    def template(
        *,
        player,
        hero,
        score,
        rank,
        raw_import_code,
        realm="realm-a",
        region="cn",
    ):
        identity = f"raiderio:{region}|{realm}|{player}"
        profile_url = f"https://raider.io/characters/{region}/{realm}/{player}"
        return {
            "id": f"template-{hero}-{player}",
            "classKey": "mage",
            "specKey": "frost",
            "heroKey": hero,
            "scenarioKey": "mythic_plus",
            "sourceKey": "raiderio",
            "sourceUrl": profile_url,
            "rawImportCode": raw_import_code,
            "playerId": player,
            "maxKeyLevel": 20 + rank,
            "status": "verified",
            "payload": {
                "raiderio": {
                    "sourceIdentity": identity,
                    "profileUrl": profile_url,
                    "characterName": player,
                    "realm": realm,
                    "realmSlug": realm,
                    "region": region,
                    "heroKey": hero,
                    "heroSubTreeId": f"hero-{hero}",
                    "loadoutSpecId": 64,
                    "loadout": [{"traitId": 91001 + rank, "rank": 1}],
                    "source": "run_detail",
                },
                "rioEvidence": {
                    "source": "raiderio_spec_ranking",
                    "score": score,
                    "rank": rank,
                    "maxKeyLevel": 20 + rank,
                    "sourceUrl": profile_url,
                    "region": region,
                },
            },
        }

    @staticmethod
    def profile(player, *, item_id, realm="realm-a", region="cn"):
        return {
            "sourceIdentity": f"raiderio:{region}|{realm}|{player}",
            "profileUrl": f"https://raider.io/characters/{region}/{realm}/{player}",
            "name": player,
            "realm": realm,
            "realmSlug": realm,
            "region": region,
            "classKey": "mage",
            "specKey": "frost",
            "raceKey": "human",
            "itemLevel": 710,
            "gear": [
                {
                    "slot": "head",
                    "itemId": item_id,
                    "itemLevel": 710,
                    "bonus_id": "10355",
                }
            ],
        }

    def payload(self):
        return {
            "seasonSlug": "season-tww-3",
            "checkedAt": "2026-07-23T12:00:00+00:00",
            "communityTemplates": [
                self.template(
                    player="player-a",
                    hero="frostfire",
                    score=4200,
                    rank=1,
                    raw_import_code="C4DA",
                ),
                self.template(
                    player="player-b",
                    hero="spellslinger",
                    score=4150,
                    rank=2,
                    raw_import_code="C4DB",
                ),
            ],
            "profiles": [
                self.profile("player-a", item_id=230001),
                self.profile("player-b", item_id=230002),
            ],
        }

    def test_builds_snapshot_candidates_from_exact_template_and_profile(self):
        result = snapshot_candidates_from_raiderio(self.payload())
        slot = "mage:frost:frostfire:mythic_plus"

        snapshot = result["candidatesBySlot"][slot][0]

        self.assertEqual(
            snapshot["source"]["sourceIdentity"],
            "raiderio:cn|realm-a|player-a",
        )
        self.assertEqual(snapshot["talentObservation"]["rawImportCode"], "C4DA")
        self.assertEqual(
            snapshot["gearObservation"]["gearItems"][0]["itemId"],
            230001,
        )
        self.assertEqual(snapshot["sourceRevision"], "raiderio:season-tww-3:observed-profile-v1")

    def test_builds_snapshot_candidates_directly_from_self_contained_profiles(self):
        payload = self.payload()
        payload["communityTemplates"] = []
        for profile, hero, raw_import_code in (
            (payload["profiles"][0], "frostfire", "C4DA"),
            (payload["profiles"][1], "spellslinger", "C4DB"),
        ):
            profile["rankingEvidence"] = {
                "source": "raiderio_spec_ranking",
                "score": 4200 if hero == "frostfire" else 4150,
                "rank": 1 if hero == "frostfire" else 2,
                "maxKeyLevel": 22,
                "sourceUrl": profile["profileUrl"],
            }
            profile["talentLoadout"] = {
                "rawImportCode": raw_import_code,
                "loadoutSpecId": 64,
                "heroSubTreeId": f"hero-{hero}",
                "heroKey": hero,
                "selector": {"heroKey": hero},
                "source": "run_detail",
                "loadout": [{"traitId": 91001, "rank": 1}],
            }

        result = snapshot_candidates_from_raiderio(payload)
        winners = select_distinct_snapshot_winners(
            result["candidatesBySlot"]
        )

        self.assertEqual(len(winners), 2)
        self.assertEqual(
            winners["mage:frost:frostfire:mythic_plus"][
                "source"
            ]["sourceIdentity"],
            "raiderio:cn|realm-a|player-a",
        )
        self.assertEqual(
            winners["mage:frost:spellslinger:mythic_plus"][
                "talentObservation"
            ]["rawImportCode"],
            "C4DB",
        )

    def test_selects_highest_combined_distinct_players_for_two_hero_slots(self):
        payload = self.payload()
        payload["communityTemplates"] = [
            self.template(
                player="player-a",
                hero="frostfire",
                score=4200,
                rank=1,
                raw_import_code="C4DA",
            ),
            self.template(
                player="player-b",
                hero="frostfire",
                score=4100,
                rank=2,
                raw_import_code="C4DB",
            ),
            self.template(
                player="player-a",
                hero="spellslinger",
                score=4190,
                rank=1,
                raw_import_code="C4DC",
            ),
            self.template(
                player="player-c",
                hero="spellslinger",
                score=4050,
                rank=2,
                raw_import_code="C4DD",
            ),
        ]
        payload["profiles"] = [
            self.profile("player-a", item_id=230001),
            self.profile("player-b", item_id=230002),
            self.profile("player-c", item_id=230003),
        ]
        candidates = snapshot_candidates_from_raiderio(payload)["candidatesBySlot"]

        winners = select_distinct_snapshot_winners(candidates)

        self.assertEqual(
            winners["mage:frost:frostfire:mythic_plus"]["source"]["sourceIdentity"],
            "raiderio:cn|realm-a|player-b",
        )
        self.assertEqual(
            winners["mage:frost:spellslinger:mythic_plus"]["source"]["sourceIdentity"],
            "raiderio:cn|realm-a|player-a",
        )

    def test_selection_is_stable_when_template_and_profile_order_changes(self):
        payload = self.payload()
        first = snapshot_candidates_from_raiderio(payload)
        reversed_payload = copy.deepcopy(payload)
        reversed_payload["communityTemplates"].reverse()
        reversed_payload["profiles"].reverse()
        second = snapshot_candidates_from_raiderio(reversed_payload)

        first_winners = select_distinct_snapshot_winners(first["candidatesBySlot"])
        second_winners = select_distinct_snapshot_winners(second["candidatesBySlot"])

        self.assertEqual(
            {
                key: value["snapshotId"]
                for key, value in first_winners.items()
            },
            {
                key: value["snapshotId"]
                for key, value in second_winners.items()
            },
        )

    def test_missing_exact_gear_profile_is_a_problem_not_a_snapshot(self):
        payload = self.payload()
        payload["profiles"] = []

        result = snapshot_candidates_from_raiderio(payload)

        self.assertEqual(result["candidatesBySlot"], {})
        self.assertEqual(
            result["problemsBySlot"]["mage:frost:frostfire:mythic_plus"][0]["code"],
            "exact_profile_gear_missing",
        )

    def test_duplicate_only_player_pair_is_reported_and_not_selected(self):
        payload = self.payload()
        payload["communityTemplates"] = [
            self.template(
                player="player-a",
                hero="frostfire",
                score=4200,
                rank=1,
                raw_import_code="C4DA",
            ),
            self.template(
                player="player-a",
                hero="spellslinger",
                score=4190,
                rank=1,
                raw_import_code="C4DC",
            ),
        ]
        payload["profiles"] = [self.profile("player-a", item_id=230001)]

        result = snapshot_candidates_from_raiderio(payload)
        winners = select_distinct_snapshot_winners(result["candidatesBySlot"])

        self.assertEqual(winners, {})
        for slot in (
            "mage:frost:frostfire:mythic_plus",
            "mage:frost:spellslinger:mythic_plus",
        ):
            self.assertEqual(
                result["problemsBySlot"][slot][-1]["code"],
                "distinct_spec_player_missing",
            )

    def test_never_cross_fills_a_profile_from_another_identity(self):
        payload = self.payload()
        payload["profiles"] = [self.profile("player-b", item_id=230002)]

        result = snapshot_candidates_from_raiderio(payload)

        self.assertNotIn(
            "mage:frost:frostfire:mythic_plus",
            result["candidatesBySlot"],
        )
        self.assertEqual(
            result["problemsBySlot"]["mage:frost:frostfire:mythic_plus"][0]["code"],
            "exact_profile_gear_missing",
        )

    def test_rejects_talent_observation_from_another_hero_slot(self):
        payload = self.payload()
        payload["communityTemplates"][0]["payload"]["raiderio"]["heroKey"] = "spellslinger"

        result = snapshot_candidates_from_raiderio(payload)

        self.assertNotIn(
            "mage:frost:frostfire:mythic_plus",
            result["candidatesBySlot"],
        )
        self.assertEqual(
            result["problemsBySlot"]["mage:frost:frostfire:mythic_plus"][0]["code"],
            "talent_hero_mismatch",
        )


if __name__ == "__main__":
    unittest.main()

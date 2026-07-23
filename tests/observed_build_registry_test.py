import copy
import unittest

from server.observed_build_registry import (
    build_observed_snapshot,
    slot_key,
    snapshot_check,
    validate_observed_snapshot,
)


class ObservedBuildRegistryTest(unittest.TestCase):
    def slot(self, **overrides):
        value = {
            "classKey": "mage",
            "specKey": "frost",
            "heroKey": "frostfire",
            "scenarioKey": "mythic_plus",
        }
        value.update(overrides)
        return value

    def snapshot_input(self):
        return {
            "slot": self.slot(),
            "source": {
                "sourceKey": "raiderio",
                "sourceIdentity": "raiderio:cn|realm-a|player-a",
                "profileUrl": "https://raider.io/characters/cn/realm-a/player-a",
                "region": "cn",
                "realm": "realm-a",
                "character": "player-a",
            },
            "ranking_evidence": {
                "rank": 1,
                "score": 3812.5,
                "season": "season-tww-3",
            },
            "talent_observation": {
                "rawImportCode": "C4DAAAAAAAAAAAAAAAAAAAAAAA",
                "selectedNodes": [
                    {"id": "mage:class:1", "rank": 1},
                    {"id": "mage:frost:2", "rank": 2},
                ],
            },
            "gear_observation": {
                "gearBySlot": {
                    "head": {
                        "itemId": "230001",
                        "bonusIds": [10355, 10299],
                        "gemIds": ["213458"],
                        "enchantIds": [],
                    }
                }
            },
            "source_revision": "raiderio-profile-v1",
        }

    def snapshot(self):
        return build_observed_snapshot(**self.snapshot_input())

    def test_same_observed_content_has_same_snapshot_id(self):
        first = self.snapshot()
        reordered = self.snapshot_input()
        reordered["ranking_evidence"] = {
            "season": "season-tww-3",
            "score": 3812.5,
            "rank": 1,
        }
        second = build_observed_snapshot(**reordered)

        self.assertEqual(first["snapshotId"], second["snapshotId"])
        self.assertRegex(first["snapshotId"], r"^observed-build:sha256:[0-9a-f]{64}$")
        self.assertRegex(first["profileHash"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(first["talentHash"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(first["gearHash"], r"^sha256:[0-9a-f]{64}$")

    def test_observed_content_change_creates_a_new_snapshot(self):
        first = self.snapshot()
        changed = self.snapshot_input()
        changed["gear_observation"]["gearBySlot"]["head"]["itemId"] = "230002"
        second = build_observed_snapshot(**changed)

        self.assertNotEqual(first["snapshotId"], second["snapshotId"])
        self.assertNotEqual(first["profileHash"], second["profileHash"])
        self.assertNotEqual(first["gearHash"], second["gearHash"])
        self.assertEqual(first["talentHash"], second["talentHash"])

    def test_snapshot_rejects_missing_real_source_identity(self):
        value = self.snapshot_input()
        value["source"]["sourceIdentity"] = ""

        with self.assertRaisesRegex(ValueError, "sourceIdentity"):
            build_observed_snapshot(**value)

    def test_snapshot_rejects_non_raiderio_source(self):
        value = self.snapshot_input()
        value["source"]["sourceKey"] = "manual_fixture"
        value["source"]["sourceIdentity"] = "manual:fixture"

        with self.assertRaisesRegex(ValueError, "Raider.IO"):
            build_observed_snapshot(**value)

    def test_slot_key_is_exact_and_rejects_missing_dimensions(self):
        self.assertEqual(slot_key(self.slot()), "mage:frost:frostfire:mythic_plus")

        with self.assertRaisesRegex(ValueError, "heroKey"):
            slot_key(self.slot(heroKey=""))

    def test_source_check_time_is_not_part_of_immutable_snapshot(self):
        observed = self.snapshot()
        check = snapshot_check(
            run_id="run-1",
            slot=observed["slot"],
            checked_at="2026-07-23T10:00:00+08:00",
            status="unchanged",
            snapshot_id=observed["snapshotId"],
        )

        self.assertNotIn("checkedAt", observed)
        self.assertEqual(check["checkedAt"], "2026-07-23T10:00:00+08:00")
        self.assertEqual(check["status"], "unchanged")
        self.assertEqual(check["snapshotId"], observed["snapshotId"])

    def test_failed_source_check_has_problem_without_snapshot(self):
        check = snapshot_check(
            run_id="run-failed",
            slot=self.slot(),
            checked_at="2026-07-23T10:00:00+08:00",
            status="failed",
            problem={"code": "raiderio_unavailable", "retryable": True},
        )

        self.assertEqual(check["snapshotId"], "")
        self.assertEqual(check["problem"]["code"], "raiderio_unavailable")

    def test_unchanged_check_requires_snapshot_id(self):
        with self.assertRaisesRegex(ValueError, "snapshot_id"):
            snapshot_check(
                run_id="run-1",
                slot=self.slot(),
                checked_at="2026-07-23T10:00:00+08:00",
                status="unchanged",
            )

    def test_validation_detects_mutated_content_addressed_record(self):
        observed = self.snapshot()
        tampered = copy.deepcopy(observed)
        tampered["gearObservation"]["gearBySlot"]["head"]["itemId"] = "forged"

        issues = validate_observed_snapshot(tampered)

        self.assertEqual(
            {issue["code"] for issue in issues},
            {"PROFILE_HASH_MISMATCH", "GEAR_HASH_MISMATCH", "SNAPSHOT_ID_MISMATCH"},
        )

    def test_validation_rejects_structurally_empty_observations(self):
        observed = self.snapshot()
        observed["talentObservation"] = {}
        observed["gearObservation"] = {}

        issues = validate_observed_snapshot(observed)

        codes = {issue["code"] for issue in issues}
        self.assertIn("TALENT_OBSERVATION_INVALID", codes)
        self.assertIn("GEAR_OBSERVATION_INVALID", codes)


if __name__ == "__main__":
    unittest.main()

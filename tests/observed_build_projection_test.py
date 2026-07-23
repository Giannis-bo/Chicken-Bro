import copy
import unittest

from server.observed_build_projection import (
    build_dependency_vector,
    build_projection,
    publication_change_kind,
    validate_projection,
)
from server.observed_build_registry import build_observed_snapshot


class ObservedBuildProjectionTest(unittest.TestCase):
    def snapshot(self):
        return build_observed_snapshot(
            slot={
                "classKey": "mage",
                "specKey": "frost",
                "heroKey": "frostfire",
                "scenarioKey": "mythic_plus",
            },
            source={
                "sourceKey": "raiderio",
                "sourceIdentity": "raiderio:cn|realm-a|player-a",
                "profileUrl": "https://raider.io/characters/cn/realm-a/player-a",
                "region": "cn",
                "realm": "realm-a",
                "character": "player-a",
            },
            ranking_evidence={"rank": 1, "score": 3812.5},
            talent_observation={"rawImportCode": "C4DA", "selectedNodes": [{"id": "a", "rank": 1}]},
            gear_observation={"gearBySlot": {"head": {"itemId": "230001"}}},
            source_revision="raiderio-profile-v1",
        )

    def dependencies(self, **overrides):
        values = {
            "season_revision": "season-tww-3",
            "talent_catalog_revision": "talent-catalog-v7",
            "gear_release_id": "gear-release:sha256:" + "1" * 64,
            "gear_rule_revision": "gear-rules-v5",
            "resolver_contract_revision": "gear-resolver-v1",
            "serializer_revision": "simc-serializer-v3",
            "simc_runtime_revision": "simc-runtime-abc",
            "selection_schema_revision": "selection-intent-v1",
            "projection_schema_revision": "observed-build-projection-v1",
        }
        values.update(overrides)
        return build_dependency_vector(**values)

    def verified_projection(self, **overrides):
        values = {
            "snapshot": self.snapshot(),
            "dependency_vector": self.dependencies(),
            "talent_projection": {
                "status": "verified",
                "talentState": {"selectedNodes": [{"id": "a", "rank": 1}]},
                "encoding": {"status": "encoded", "lines": ["class_talents=1:1"]},
            },
            "gear_projection": {
                "status": "verified",
                "selectionIntent": {
                    "schemaRevision": "selection-intent-v1",
                    "classKey": "mage",
                    "specKey": "frost",
                    "slots": {"head": {"itemId": "230001", "variantKey": "hero-1"}},
                },
                "resolvedGearSignature": "sha256:" + "2" * 64,
            },
            "profile_readiness": {
                "status": "ready",
                "simcReady": True,
                "profileSignature": "sha256:" + "3" * 64,
            },
        }
        values.update(overrides)
        return build_projection(**values)

    def test_same_snapshot_and_dependencies_compile_to_same_projection_id(self):
        first = self.verified_projection()
        second = self.verified_projection()

        self.assertEqual(first["projectionId"], second["projectionId"])
        self.assertRegex(first["projectionId"], r"^build-projection:sha256:[0-9a-f]{64}$")
        self.assertEqual(first["status"], "verified")
        self.assertTrue(first["importable"])

    def test_dependency_change_creates_a_new_projection(self):
        first = self.verified_projection()
        second = self.verified_projection(
            dependency_vector=self.dependencies(serializer_revision="simc-serializer-v4")
        )

        self.assertNotEqual(first["projectionId"], second["projectionId"])
        self.assertNotEqual(first["dependencyHash"], second["dependencyHash"])

    def test_blocked_projection_keeps_structured_problems_and_is_not_importable(self):
        value = build_projection(
            snapshot=self.snapshot(),
            dependency_vector=self.dependencies(),
            talent_projection={"status": "blocked"},
            gear_projection={"status": "verified"},
            profile_readiness={"status": "blocked", "simcReady": False},
            problems=[{"code": "talent_mapping_failed", "stage": "talent"}],
        )

        self.assertEqual(value["status"], "blocked")
        self.assertFalse(value["importable"])
        self.assertEqual(value["problems"][0]["code"], "talent_mapping_failed")

    def test_incomplete_verified_parts_are_blocked_even_without_explicit_problem(self):
        value = self.verified_projection(
            gear_projection={"status": "blocked"},
            problems=[],
        )

        self.assertEqual(value["status"], "blocked")
        self.assertFalse(value["importable"])
        self.assertEqual(value["problems"][0]["code"], "projection_not_ready")

    def test_dependency_drift_requires_controlled_cutover(self):
        changed = self.dependencies(serializer_revision="simc-serializer-v4")

        self.assertEqual(
            publication_change_kind(self.dependencies(), changed),
            "dependency_cutover",
        )
        self.assertEqual(
            publication_change_kind(self.dependencies(), self.dependencies()),
            "observed_only",
        )

    def test_dependency_vector_requires_every_authority_revision(self):
        with self.assertRaisesRegex(ValueError, "serializer_revision"):
            self.dependencies(serializer_revision="")

    def test_validation_detects_tampered_projection_payload(self):
        projection = self.verified_projection()
        tampered = copy.deepcopy(projection)
        tampered["gearProjection"]["selectionIntent"]["slots"]["head"]["itemId"] = "forged"

        issues = validate_projection(tampered)

        self.assertEqual(
            {issue["code"] for issue in issues},
            {"PROJECTION_ID_MISMATCH"},
        )

    def test_validation_rejects_slot_key_or_problem_shape_drift(self):
        projection = self.verified_projection()
        projection["slotKey"] = "mage:frost:spellslinger:mythic_plus"
        projection["problems"] = {}

        issues = validate_projection(projection)

        codes = {issue["code"] for issue in issues}
        self.assertIn("PROJECTION_SLOT_MISMATCH", codes)
        self.assertIn("PROJECTION_PROBLEMS_INVALID", codes)


if __name__ == "__main__":
    unittest.main()

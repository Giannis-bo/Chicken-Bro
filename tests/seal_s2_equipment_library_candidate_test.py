import importlib.util
from types import SimpleNamespace
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "seal-s2-equipment-library-candidate.py"
SPEC = importlib.util.spec_from_file_location("seal_s2_equipment_library_candidate", SCRIPT)
seal = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(seal)


class SealS2EquipmentLibraryCandidateTest(unittest.TestCase):
    def test_exact_binding_carries_s2_track_authority_records(self):
        binding = seal._exact_binding(
            {
                "releaseId": "gear-release:sha256:" + "a" * 64,
                "contentHash": "sha256:" + "b" * 64,
                "schemaRevision": "gear-release-v1",
                "seasonRevision": "season-midnight-season-2:test",
            },
            {"gearRuleRevision": "gear-rule-matrix-v1"},
            {
                "trackAuthorityRevision": "midnight-season-2-track-authority-v69",
                "records": [{"recordKey": "s2_myth_1", "publicTrackKey": "myth"}],
            },
        )

        self.assertEqual(
            binding["trackAuthorityRevision"],
            "midnight-season-2-track-authority-v69",
        )
        self.assertEqual(binding["trackRecords"][0]["recordKey"], "s2_myth_1")

    def test_community_release_binding_carries_s2_track_authority_records(self):
        binding = seal._community_release_binding(
            {
                "releaseId": "gear-release:sha256:" + "a" * 64,
                "dependencyRevisions": {
                    "gearRuleRevision": "gear-rule-matrix-v1",
                },
            },
            {
                "trackAuthorityRevision": "midnight-season-2-track-authority-v69",
                "gearRuleRevision": "gear-rule-matrix-v1",
                "records": [{"recordKey": "s2_myth_1"}],
            },
        )

        self.assertEqual(
            binding["trackAuthorityRevision"],
            "midnight-season-2-track-authority-v69",
        )
        self.assertEqual(binding["gearRuleRevision"], "gear-rule-matrix-v1")
        self.assertEqual(binding["trackRecords"][0]["recordKey"], "s2_myth_1")

    def test_community_staging_binding_materializes_variant_keys(self):
        staging = {
            "gear": {
                "items": [{
                    "itemId": "1001",
                    "slot": "head",
                    "payload": {},
                }],
                "variants": [{
                    "itemId": "1001",
                    "slot": "head",
                    "itemLevel": 300,
                    "variantKey": "observed-head-300",
                    "sourceType": "observed_profile",
                    "status": "verified",
                    "payload": {"itemStats": {"intellect": 100}},
                    "simcOptions": {"ilevel": "300"},
                }],
            },
            "templates": [],
        }
        bound = seal._bind_community_staging_templates(
            staging,
            [{
                "templateId": "observed-template",
                "classKey": "mage",
                "specKey": "fire",
                "status": "complete",
                "gearItems": [{
                    "slot": "head",
                    "itemId": "1001",
                    "ilevel": "300",
                }],
            }],
        )

        self.assertEqual(bound[0]["gearItems"][0]["variantKey"], "observed-head-300")

    def test_candidate_staging_overrides_template_hydration_reader(self):
        store = SimpleNamespace()
        staged_templates = [{
            "templateId": "observed-template",
            "classKey": "mage",
            "specKey": "fire",
            "gearItems": [{
                "slot": "head",
                "itemId": "1001",
                "variantKey": "observed-head-300",
            }],
        }]

        seal._install_candidate_community_template_readers(store, staged_templates)

        hydrated = store.snapshot_staging_community_templates_by_ids(["observed-template"])
        self.assertEqual(
            hydrated[0]["gearItems"][0]["variantKey"],
            "observed-head-300",
        )

    def test_candidate_staging_overrides_both_community_template_readers(self):
        class FakeStore:
            def snapshot_staging_community_templates(self, _expected_specs):
                return ["live-v1"]

            def snapshot_staging_community_builder_templates(self, _expected_specs):
                return ["live-v2"]

        store = FakeStore()
        staged = [{"templateId": "candidate-template"}]

        seal._install_candidate_community_template_readers(store, staged)

        self.assertEqual(
            store.snapshot_staging_community_templates([]),
            staged,
        )
        self.assertEqual(
            store.snapshot_staging_community_builder_templates([]),
            staged,
        )


if __name__ == "__main__":
    unittest.main()

import copy
import unittest
from unittest.mock import patch

from server import gear_release, gear_release_shadow


class FakeShadowStore:
    def __init__(self, candidate_row, *, baseline_count=0):
        self.candidate_row = copy.deepcopy(candidate_row)
        self.baseline_count = baseline_count
        self.calls = []

    def get_candidate_community_release(self, gear_release_id, community_release_id):
        self.calls.append(("community", gear_release_id, community_release_id))
        return {
            "gearRelease": {"releaseId": gear_release_id},
            "communityRelease": {
                "releaseId": community_release_id,
                "validatedAgainstReleaseId": gear_release_id,
            },
            "rows": [copy.deepcopy(self.candidate_row)],
            "winners": [copy.deepcopy(self.candidate_row)],
        }

    def get_websim_gear(self, class_key, spec_key, compact=False, mode="", slot=""):
        self.calls.append(("public", class_key, spec_key, compact, mode, slot))
        return {
            "classKey": class_key,
            "specKey": spec_key,
            "communityTemplates": [{
                "id": self.candidate_row["templateId"],
                "classKey": class_key,
                "specKey": spec_key,
                "sourceKey": self.candidate_row["sourceKey"],
                "sourceUrl": self.candidate_row["sourceUrl"],
                "sourceStatus": "synced",
                "signature": self.candidate_row["gearHash"],
                "gearItems": [{
                    "slot": slot,
                    "itemId": selection.get("itemId"),
                    "variantKey": selection.get("variantKey"),
                } for slot, selection in self.candidate_row["selectionIntent"]["slots"].items()],
                "sourceRefs": [{"sampleCount": self.candidate_row["sampleCount"]}],
                "payload": {"templateEvidence": {
                    "profileHash": self.candidate_row["profileHash"],
                    "gearHash": self.candidate_row["gearHash"],
                    "sampleCount": self.candidate_row["sampleCount"],
                }},
            }],
            "baselineTemplates": [{} for _ in range(self.baseline_count)],
        }

    def get_gear_resolver_context(self, runtime_authority):
        self.calls.append(("resolver-context", copy.deepcopy(runtime_authority)))
        return {
            "formalActiveManifest": False,
            "authoredAgainst": {
                "seasonRevision": "season-17",
                "gearCatalogRevision": "compatibility-pg:old",
            },
        }


class GearReleaseShadowTest(unittest.TestCase):
    def intent(self):
        return {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": "season-17",
                "gearCatalogRevision": "gear-release:sha256:target",
            },
            "eligibilityContext": {"classKey": "mage", "specKey": "arcane", "level": 90},
            "slots": {
                "head": {
                    "itemId": "item-a",
                    "variantKey": "variant-a",
                    "gemOptionIds": [],
                    "enchantOptionId": "",
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                }
            },
        }

    def snapshot(self, intent, resolved_signature):
        return {
            "status": "verified",
            "eligibilityContext": intent["eligibilityContext"],
            "resolvedGearSignature": resolved_signature,
            "resolvedSlots": {"head": {"itemId": "item-a", "variantKey": "variant-a"}},
            "staticAttributes": {"intellect": 100},
            "setState": {"itemSetCounts": {}},
            "constraints": {"slots": {}},
            "serializerInput": {"gearItems": [{"slot": "head", "itemId": "item-a"}]},
            "aggregateLegality": {"status": "verified"},
            "profileReadiness": {"simcReady": True},
            "problems": [],
        }

    def candidate_row(self):
        intent = self.intent()
        snapshot = self.snapshot(intent, "sha256:candidate")
        return {
            "templateId": "template-a",
            "classKey": "mage",
            "specKey": "arcane",
            "role": "winner",
            "sourceKey": "raiderio_observed_profile",
            "sourceUrl": "https://raider.io/a",
            "sourceStatus": "synced",
            "sampleCount": 1,
            "profileHash": "profile:a",
            "gearHash": "gear:a",
            "selectionIntent": intent,
            "resolvedGearSignature": "sha256:candidate",
            "semanticGearSignature": gear_release.semantic_gear_signature(intent, snapshot),
            "problems": [],
        }

    def test_internal_shadow_compares_one_release_pair_without_public_cutover(self):
        candidate = self.candidate_row()
        store = FakeShadowStore(candidate)
        transitional_intent = copy.deepcopy(candidate["selectionIntent"])
        transitional_intent["authoredAgainst"]["gearCatalogRevision"] = "compatibility-pg:old"
        old_snapshot = self.snapshot(transitional_intent, "sha256:old")
        candidate_snapshot = self.snapshot(candidate["selectionIntent"], "sha256:candidate")

        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {"status": "resolved", "data": old_snapshot, "problems": []}),
        ) as old_resolve, patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            return_value=(200, {"status": "resolved", "data": candidate_snapshot, "problems": []}),
        ) as candidate_resolve:
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "arcane")],
                gear_release_id="gear-release:sha256:target",
                community_release_id="community-release:sha256:target",
                simc_runtime_revision="simc-r1",
                compare_profiles=False,
            )

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["report"]["diffs"][0]["classification"], "revision_only")
        self.assertEqual(result["publicReadCount"], 1)
        self.assertFalse(result["formalActiveManifest"])
        self.assertEqual(store.calls[0][0], "community")
        old_resolve.assert_called_once()
        candidate_resolve.assert_called_once()
        self.assertEqual(
            old_resolve.call_args.args[0]["authoredAgainst"]["gearCatalogRevision"],
            "compatibility-pg:old",
        )

    def test_internal_shadow_blocks_public_baseline_or_candidate_resolve_failure(self):
        candidate = self.candidate_row()
        store = FakeShadowStore(candidate, baseline_count=1)
        old_snapshot = self.snapshot(candidate["selectionIntent"], "sha256:old")
        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {"status": "resolved", "data": old_snapshot, "problems": []}),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            return_value=(503, {"status": "unavailable", "data": {}, "problems": [{"code": "MISSING"}]}),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "arcane")],
                gear_release_id="gear-release:sha256:target",
                community_release_id="community-release:sha256:target",
                simc_runtime_revision="simc-r1",
                compare_profiles=False,
            )

        self.assertEqual(result["status"], "blocked")
        codes = {problem["code"] for problem in result["blockers"]}
        self.assertIn("PUBLIC_BASELINE_LEAK", codes)
        self.assertIn("CANDIDATE_RESOLVE_FAILED", codes)
        self.assertEqual(
            result["specResults"][0]["candidateProblemCodes"],
            ["MISSING"],
        )

    def test_internal_shadow_fails_closed_when_public_reader_raises(self):
        candidate = self.candidate_row()
        store = FakeShadowStore(candidate)
        store.get_websim_gear = unittest.mock.Mock(side_effect=RuntimeError("database unavailable"))

        result = gear_release_shadow.run_release_shadow(
            store,
            expected_specs=[("mage", "arcane")],
            gear_release_id="gear-release:sha256:target",
            community_release_id="community-release:sha256:target",
            simc_runtime_revision="simc-r1",
            compare_profiles=False,
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["publicReadCount"], 0)
        self.assertIn(
            "TRANSITIONAL_PUBLIC_READ_FAILED",
            {problem["code"] for problem in result["blockers"]},
        )

    def test_internal_shadow_fails_closed_when_candidate_pair_is_not_an_object(self):
        store = FakeShadowStore(self.candidate_row())
        store.get_candidate_community_release = unittest.mock.Mock(return_value=[])

        result = gear_release_shadow.run_release_shadow(
            store,
            expected_specs=[("mage", "arcane")],
            gear_release_id="gear-release:sha256:target",
            community_release_id="community-release:sha256:target",
            simc_runtime_revision="simc-r1",
            compare_profiles=False,
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["blockers"][0]["code"],
            "CANDIDATE_RELEASE_READ_FAILED",
        )

    def test_internal_shadow_rejects_candidate_winner_outside_expected_matrix(self):
        candidate = self.candidate_row()
        store = FakeShadowStore(candidate)
        original_pair_reader = store.get_candidate_community_release

        def pair_with_extra_winner(gear_release_id, community_release_id):
            pair = original_pair_reader(gear_release_id, community_release_id)
            extra = copy.deepcopy(candidate)
            extra["templateId"] = "template-fire"
            extra["specKey"] = "fire"
            extra["selectionIntent"]["eligibilityContext"]["specKey"] = "fire"
            pair["rows"].append(extra)
            pair["winners"].append(extra)
            return pair

        store.get_candidate_community_release = unittest.mock.Mock(side_effect=pair_with_extra_winner)
        transitional_intent = copy.deepcopy(candidate["selectionIntent"])
        transitional_intent["authoredAgainst"]["gearCatalogRevision"] = "compatibility-pg:old"
        old_snapshot = self.snapshot(transitional_intent, "sha256:old")
        candidate_snapshot = self.snapshot(candidate["selectionIntent"], "sha256:candidate")
        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {"status": "resolved", "data": old_snapshot, "problems": []}),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            return_value=(200, {"status": "resolved", "data": candidate_snapshot, "problems": []}),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "arcane")],
                gear_release_id="gear-release:sha256:target",
                community_release_id="community-release:sha256:target",
                simc_runtime_revision="simc-r1",
                compare_profiles=False,
            )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "UNEXPECTED_PUBLIC_SPEC",
            {problem["code"] for problem in result["blockers"]},
        )

    def test_internal_shadow_compares_resolved_profile_content_not_only_status(self):
        candidate = self.candidate_row()
        store = FakeShadowStore(candidate)
        transitional_intent = copy.deepcopy(candidate["selectionIntent"])
        transitional_intent["authoredAgainst"]["gearCatalogRevision"] = "compatibility-pg:old"
        old_snapshot = self.snapshot(transitional_intent, "sha256:old")
        candidate_snapshot = self.snapshot(candidate["selectionIntent"], "sha256:candidate")
        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {"status": "resolved", "data": old_snapshot, "problems": []}),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            return_value=(200, {"status": "resolved", "data": candidate_snapshot, "problems": []}),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_profile_from_selection_intent",
            return_value=(200, {"status": "resolved", "data": {"profile": "mage=old"}, "problems": []}),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_candidate_profile_from_selection_intent",
            return_value=(200, {"status": "resolved", "data": {"profile": "mage=new"}, "problems": []}),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "arcane")],
                gear_release_id="gear-release:sha256:target",
                community_release_id="community-release:sha256:target",
                simc_runtime_revision="simc-r1",
            )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "PROFILE_PARITY_MISMATCH",
            {problem["code"] for problem in result["blockers"]},
        )


if __name__ == "__main__":
    unittest.main()

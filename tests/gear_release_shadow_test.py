import copy
import unittest
from unittest.mock import patch

from server import gear_release, gear_release_shadow
from server import gear_resolver, gear_socket_authority
from tests.gear_release_tool_test import build_midnight_mage_release_fixture


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
        self.assertGreaterEqual(result["performance"]["totalDurationMs"], 0)
        self.assertGreaterEqual(result["performance"]["specP95Ms"], 0)
        self.assertIn("durationMs", result["specResults"][0])
        self.assertEqual(store.calls[0][0], "community")
        old_resolve.assert_called_once()
        candidate_resolve.assert_called_once()
        self.assertEqual(
            old_resolve.call_args.args[0]["authoredAgainst"]["gearCatalogRevision"],
            "compatibility-pg:old",
        )

    def test_refresh_shadow_accepts_expected_formal_active_public_reader(self):
        candidate = self.candidate_row()
        store = FakeShadowStore(candidate)
        store.get_gear_resolver_context = lambda _runtime: {
            "formalActiveManifest": True,
            "authoredAgainst": {
                "seasonRevision": "season-17",
                "gearCatalogRevision": "gear-release:sha256:target",
            },
        }
        snapshot = self.snapshot(candidate["selectionIntent"], "sha256:candidate")
        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {"status": "resolved", "data": snapshot, "problems": []}),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            return_value=(200, {"status": "resolved", "data": snapshot, "problems": []}),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "arcane")],
                gear_release_id="gear-release:sha256:target",
                community_release_id="community-release:sha256:target",
                simc_runtime_revision="simc-r1",
                compare_profiles=False,
                expect_formal_active=True,
            )

        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["formalActiveManifest"])

    def test_refresh_shadow_allows_explicit_degraded_empty_for_policy_gate(self):
        candidate = self.candidate_row()
        store = FakeShadowStore(candidate)
        store.get_candidate_community_release = lambda gear_id, community_id: {
            "gearRelease": {"releaseId": gear_id},
            "communityRelease": {"releaseId": community_id, "validatedAgainstReleaseId": gear_id},
            "rows": [{**candidate, "role": "rejected", "problems": [{"code": "COMMUNITY_SOURCE_STALE"}]}],
            "winners": [],
        }
        store.get_gear_resolver_context = lambda _runtime: {
            "formalActiveManifest": True,
            "authoredAgainst": {
                "seasonRevision": "season-17",
                "gearCatalogRevision": "gear-release:sha256:target",
            },
        }
        result = gear_release_shadow.run_release_shadow(
            store,
            expected_specs=[("mage", "arcane")],
            gear_release_id="gear-release:sha256:target",
            community_release_id="community-release:sha256:target",
            simc_runtime_revision="simc-r1",
            compare_profiles=False,
            expect_formal_active=True,
            allow_degraded_empty=True,
        )

        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["report"]["emptySpecs"], [{"classKey": "mage", "specKey": "arcane"}])
        self.assertEqual(result["specResults"][0]["status"], "degraded_empty")
        self.assertEqual(result["blockers"], [])

    def test_internal_shadow_accepts_legacy_sealed_signature_only_after_live_semantic_parity(self):
        candidate = self.candidate_row()
        candidate["semanticGearSignature"] = "sha256:legacy-evidence-sensitive"
        store = FakeShadowStore(candidate)
        original_pair_reader = store.get_candidate_community_release

        def legacy_pair(gear_release_id, community_release_id):
            pair = original_pair_reader(gear_release_id, community_release_id)
            pair["communityRelease"]["source"] = {"sourceRevision": "legacy-import-r0"}
            return pair

        store.get_candidate_community_release = unittest.mock.Mock(side_effect=legacy_pair)
        old_snapshot = self.snapshot(candidate["selectionIntent"], "sha256:old")
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

        self.assertEqual(result["status"], "pass")

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

    def test_enhancement_migration_does_not_allow_crafted_or_catalyst_changes(self):
        for field in ("craftedOptionId", "catalystOptionId"):
            with self.subTest(field=field):
                candidate = self.candidate_row()
                candidate_intent = candidate["selectionIntent"]
                candidate_intent["slots"]["head"]["gemOptionIds"] = ["gem-a"]
                candidate_intent["slots"]["head"][field] = f"changed-{field}"
                candidate_snapshot = self.snapshot(candidate_intent, "sha256:candidate")
                candidate["resolvedGearSignature"] = candidate_snapshot["resolvedGearSignature"]
                candidate["semanticGearSignature"] = gear_release.semantic_gear_signature(
                    candidate_intent,
                    candidate_snapshot,
                )
                store = FakeShadowStore(candidate)
                transitional_intent = self.intent()
                transitional_intent["authoredAgainst"]["gearCatalogRevision"] = "compatibility-pg:old"
                old_snapshot = self.snapshot(transitional_intent, "sha256:old")
                profile = {
                    "status": "resolved",
                    "data": {"profile": "mage=scope-guard"},
                    "problems": [],
                }

                with patch.object(
                    gear_release_shadow.gear_runtime,
                    "resolve_selection_intent",
                    return_value=(200, {
                        "status": "resolved",
                        "data": old_snapshot,
                        "problems": [],
                    }),
                ), patch.object(
                    gear_release_shadow.gear_runtime,
                    "resolve_candidate_selection_intent",
                    return_value=(200, {
                        "status": "resolved",
                        "data": candidate_snapshot,
                        "problems": [],
                    }),
                ), patch.object(
                    gear_release_shadow.gear_runtime,
                    "build_profile_from_selection_intent",
                    return_value=(200, profile),
                ), patch.object(
                    gear_release_shadow.gear_runtime,
                    "build_candidate_profile_from_selection_intent",
                    return_value=(200, profile),
                ):
                    result = gear_release_shadow.run_release_shadow(
                        store,
                        expected_specs=[("mage", "arcane")],
                        gear_release_id="gear-release:sha256:target",
                        community_release_id="community-release:sha256:target",
                        simc_runtime_revision="simc-r1",
                    )

                self.assertEqual(result["status"], "blocked")
                self.assertEqual(
                    result["specResults"][0]["enhancementMigrationParity"]["status"],
                    "blocked",
                )
                self.assertIn(
                    "PUBLIC_WINNER_SEMANTIC_CHANGE",
                    {problem["code"] for problem in result["blockers"]},
                )

    def test_internal_shadow_proves_exact_mage_enhancement_migration_and_ninth_gem_rejection(self):
        fixture = build_midnight_mage_release_fixture()["resolverFixture"]
        intent = copy.deepcopy(fixture["intent"])
        candidate_snapshot = gear_resolver.resolve(intent, fixture["authorityContext"])
        legacy_intent = copy.deepcopy(intent)
        for selection in legacy_intent["slots"].values():
            selection["gemOptionIds"] = []
            selection["enchantOptionId"] = ""
            selection["embellishmentOptionId"] = ""
        legacy_authority = copy.deepcopy(fixture["authorityContext"])
        legacy_authority["dependencyVector"]["capabilityRevision"] = (
            gear_socket_authority.LEGACY_CAPABILITY_REVISION
        )
        transitional_snapshot = gear_resolver.resolve(
            legacy_intent,
            legacy_authority,
        )
        self.assertNotEqual(
            transitional_snapshot["resolvedSlots"]["head"]["statDeltas"]["enhancements"],
            candidate_snapshot["resolvedSlots"]["head"]["statDeltas"]["enhancements"],
        )
        candidate = {
            "templateId": "observed_profile_mage_frost",
            "classKey": "mage",
            "specKey": "frost",
            "role": "winner",
            "sourceKey": "raiderio_observed_profile",
            "sourceUrl": "https://raider.io/characters/cn/reference-mage",
            "sourceStatus": "synced",
            "sampleCount": 1,
            "profileHash": "profile:mage:frost:reference",
            "gearHash": "gear:mage:frost:reference",
            "selectionIntent": intent,
            "resolvedGearSignature": candidate_snapshot["resolvedGearSignature"],
            "semanticGearSignature": gear_release.semantic_gear_signature(
                intent,
                candidate_snapshot,
            ),
            "problems": [],
        }
        store = FakeShadowStore(candidate)
        candidate_calls = []

        def candidate_resolve(selection_intent, **_kwargs):
            candidate_calls.append(copy.deepcopy(selection_intent))
            if len(candidate_calls) == 1:
                return 200, {
                    "status": "resolved",
                    "data": candidate_snapshot,
                    "problems": [],
                }
            return 422, {
                "status": "blocked",
                "data": {},
                "problems": [{"code": "GEAR_GEM_SOCKET_CAPACITY_EXCEEDED"}],
            }

        profile = {
            "status": "resolved",
            "data": {"profile": "mage=reference\nhead=...,gem_id=240916"},
            "problems": [],
        }
        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {
                "status": "resolved",
                "data": transitional_snapshot,
                "problems": [],
            }),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            side_effect=candidate_resolve,
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_profile_from_selection_intent",
            return_value=(200, profile),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_candidate_profile_from_selection_intent",
            return_value=(200, profile),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "frost")],
                gear_release_id="gear-release-17",
                community_release_id="community-release:sha256:reference",
                simc_runtime_revision="simc-v1",
            )

        self.assertEqual(result["status"], "pass")
        self.assertEqual(
            result["report"]["diffs"][0]["classification"],
            "expected_enhancement_migration",
        )
        self.assertEqual(result["referenceProof"]["status"], "pass")
        self.assertEqual(result["referenceProof"]["gearReleaseId"], "gear-release-17")
        self.assertEqual(
            result["referenceProof"]["communityReleaseId"],
            "community-release:sha256:reference",
        )
        self.assertEqual(result["referenceProof"]["socketVector"], [1, 2, 1, 1, 2, 1])
        self.assertEqual(result["referenceProof"]["gems"], {"used": 8, "max": 8})
        self.assertEqual(result["referenceProof"]["enchants"], {"used": 6, "max": 8})
        self.assertEqual(result["referenceProof"]["embellishments"], {"used": 2, "max": 2})
        self.assertEqual(len(candidate_calls), 2)
        self.assertEqual(
            sum(
                len(selection["gemOptionIds"])
                for selection in candidate_calls[1]["slots"].values()
            ),
            9,
        )

    def test_reference_contract_blocks_wrong_enchant_capacity_even_when_six_are_selected(self):
        fixture = build_midnight_mage_release_fixture()["resolverFixture"]
        intent = copy.deepcopy(fixture["intent"])
        snapshot = gear_resolver.resolve(intent, fixture["authorityContext"])
        candidate = {
            "sourceKey": "raiderio_observed_profile",
            "profileHash": "profile:mage:frost:reference",
            "gearHash": "gear:mage:frost:reference",
        }
        snapshot["constraints"]["slots"]["main_hand"]["canEnchant"] = False

        proof = gear_release_shadow._reference_contract_proof(
            candidate,
            intent,
            snapshot,
        )

        self.assertEqual(proof["status"], "blocked")
        self.assertIn("enchants", proof["failures"])
        self.assertEqual(proof["enchants"], {"used": 6, "max": 7})

    def test_active_v2_shadow_uses_sealed_active_winner_intent_without_public_leak(self):
        fixture = build_midnight_mage_release_fixture()["resolverFixture"]
        intent = copy.deepcopy(fixture["intent"])
        candidate_snapshot = gear_resolver.resolve(intent, fixture["authorityContext"])
        candidate = {
            "templateId": "observed_profile_mage_frost",
            "classKey": "mage",
            "specKey": "frost",
            "role": "winner",
            "sourceKey": "raiderio_observed_profile",
            "sourceUrl": "https://raider.io/characters/cn/reference-mage",
            "sourceStatus": "synced",
            "sampleCount": 1,
            "profileHash": "profile:mage:frost:reference",
            "gearHash": "gear:mage:frost:reference",
            "selectionIntent": intent,
            "resolvedGearSignature": candidate_snapshot["resolvedGearSignature"],
            "semanticGearSignature": gear_release.semantic_gear_signature(
                intent,
                candidate_snapshot,
            ),
            "problems": [],
        }

        class ActiveV2Store(FakeShadowStore):
            def get_gear_resolver_context(self, _runtime_authority):
                return {
                    "formalActiveManifest": True,
                    "authoredAgainst": {
                        "seasonRevision": "season-17-active",
                        "gearCatalogRevision": "gear-release-17",
                    },
                    "dependencyRevisions": {
                        "capabilityRevision": gear_socket_authority.CAPABILITY_REVISION,
                    },
                }

            def get_active_community_release(self):
                return {
                    "formalActiveManifest": True,
                    "gearRelease": {"releaseId": "gear-release-17"},
                    "communityRelease": {"releaseId": "community-release-active-v2"},
                    "winners": [copy.deepcopy(candidate)],
                }

        store = ActiveV2Store(candidate)
        old_intents = []
        candidate_calls = []

        def resolve_active(selection_intent, **_kwargs):
            old_intents.append(copy.deepcopy(selection_intent))
            snapshot = (
                candidate_snapshot
                if selection_intent == intent
                else gear_resolver.resolve(selection_intent, fixture["authorityContext"])
            )
            return 200, {"status": "resolved", "data": snapshot, "problems": []}

        def active_profile(payload, **_kwargs):
            selected = payload.get("selectionIntent") == intent
            return 200, {
                "status": "resolved",
                "data": {"profile": "mage=active-v2" if selected else "mage=missing-enhancements"},
                "problems": [],
            }

        def resolve_candidate(selection_intent, **_kwargs):
            candidate_calls.append(copy.deepcopy(selection_intent))
            if len(candidate_calls) == 1:
                return 200, {
                    "status": "resolved",
                    "data": candidate_snapshot,
                    "problems": [],
                }
            return 422, {
                "status": "blocked",
                "data": {},
                "problems": [{"code": "GEAR_GEM_SOCKET_CAPACITY_EXCEEDED"}],
            }

        profile = {
            "status": "resolved",
            "data": {"profile": "mage=active-v2"},
            "problems": [],
        }
        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            side_effect=resolve_active,
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            side_effect=resolve_candidate,
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_profile_from_selection_intent",
            side_effect=active_profile,
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_candidate_profile_from_selection_intent",
            return_value=(200, profile),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "frost")],
                gear_release_id="gear-release-17",
                community_release_id="community-release-candidate-v2",
                simc_runtime_revision="simc-v1",
                expect_formal_active=True,
            )

        public = store.get_websim_gear("mage", "frost", compact=True, mode="initial")
        self.assertNotIn("selectionIntent", public["communityTemplates"][0])
        self.assertEqual(old_intents, [intent])
        self.assertEqual(result["status"], "pass", result)


if __name__ == "__main__":
    unittest.main()

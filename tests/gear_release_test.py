import copy
import inspect
import unittest

from server import gear_release


class GearReleaseTest(unittest.TestCase):
    maxDiff = None

    def dependency_revisions(self):
        return {
            "gearRuleRevision": "gear-rule-matrix-v1",
            "resolverContractRevision": "gear-resolver-contract-v1",
            "serializerRevision": "websim-profile-compat-v1",
            "simcRuntimeRevision": "simc-midnight-abc",
            "statPolicyRevision": "stat-snapshot-policy-v1",
            "selectionSchemaRevision": "selection-intent-v1",
            "capabilityRevision": "gear-capability-v1",
        }

    def intent(self, class_key="mage", spec_key="arcane", item_id="item-head"):
        return {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": "season-17",
                "gearCatalogRevision": "gear-release:sha256:target",
            },
            "eligibilityContext": {
                "classKey": class_key,
                "specKey": spec_key,
                "level": 90,
            },
            "slots": {
                "head": {
                    "itemId": item_id,
                    "variantKey": "variant-head",
                    "gemOptionIds": [],
                    "enchantOptionId": "",
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                }
            },
        }

    def gear_release(self, content=None, status="validated"):
        return gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=content or {"items": [{"itemId": "item-head"}]},
            dependency_revisions=self.dependency_revisions(),
            release_status=status,
            source={"sourceRevision": "legacy-import-r0"},
        )

    def community_release(self, gear_release_id, content=None, status="validated"):
        return gear_release.build_release(
            release_kind="community",
            season_revision="season-17",
            schema_revision="community-release-v1",
            content=content or {"templates": []},
            dependency_revisions=self.dependency_revisions(),
            release_status=status,
            source={"sourceRevision": "legacy-import-r0"},
            validated_against_release_id=gear_release_id,
        )

    def candidate(self, candidate_id="candidate-a", sample_count=25, **overrides):
        candidate = {
            "id": candidate_id,
            "classKey": "mage",
            "specKey": "arcane",
            "sourceKey": "raiderio_observed_profile",
            "sourceUrl": "https://raider.io/characters/cn/example",
            "sourceStatus": "verified",
            "sampleCount": sample_count,
            "profileHash": "profile-hash-a",
            "gearHash": "gear-hash-a",
            "updatedAt": "2026-07-11T04:00:00+00:00",
            "expiresAt": "2026-07-12T04:00:00+00:00",
            "selectionIntent": self.intent(),
            "importEvidence": {
                "schemaRevision": "community-template-import-evidence-v1",
                "sourceFingerprint": "sha256:" + "a" * 64,
                "slots": {
                    "head": {
                        "itemId": "item-head",
                        "variantKey": "variant-head",
                        "observedItemLevel": 292,
                        "iconUrl": "https://render.worldofwarcraft.com/icons/item-head.jpg",
                    },
                },
            },
        }
        candidate.update(overrides)
        return candidate

    def verified_result(self, gear_release_id="gear-release:sha256:target", **overrides):
        result = {
            "status": "verified",
            "aggregateLegality": {"status": "verified", "problemCodes": []},
            "profileReadiness": {"simcReady": True, "missingSlots": []},
            "resolvedGearSignature": "sha256:resolved-a",
            "dependencyVector": {
                **self.dependency_revisions(),
                "seasonRevision": "season-17",
                "gearCatalogReleaseId": gear_release_id,
                "gearCatalogRevision": gear_release_id,
            },
            "resolvedSlots": {"head": {"itemId": "item-head"}},
            "problems": [],
        }
        result.update(overrides)
        return result

    def test_release_ids_are_hash_addressed_order_stable_and_kind_sensitive(self):
        first = self.gear_release({"items": [{"itemId": "2"}, {"itemId": "1"}]})
        reordered = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content={"items": [{"itemId": "2"}, {"itemId": "1"}]},
            dependency_revisions=dict(reversed(list(self.dependency_revisions().items()))),
            release_status="validated",
            source={"sourceRevision": "legacy-import-r0"},
        )
        community = self.community_release(first["releaseId"], first["content"])

        self.assertRegex(first["releaseId"], r"^gear-release:sha256:[0-9a-f]{64}$")
        self.assertEqual(first["releaseId"], reordered["releaseId"])
        self.assertNotEqual(first["contentHash"], community["contentHash"])
        self.assertEqual(
            set(first),
            {
                "schemaRevision",
                "releaseId",
                "releaseKind",
                "seasonRevision",
                "contentHash",
                "dependencyRevisions",
                "releaseStatus",
                "parentReleaseId",
                "validatedAgainstReleaseId",
                "source",
                "content",
            },
        )

    def test_release_identity_changes_for_content_dependency_or_binding(self):
        baseline = self.gear_release()
        content_changed = self.gear_release({"items": [{"itemId": "other"}]})
        dependency_changed = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=baseline["content"],
            dependency_revisions={**self.dependency_revisions(), "gearRuleRevision": "v2"},
            release_status="validated",
            source=baseline["source"],
        )
        community_a = self.community_release(baseline["releaseId"])
        community_b = self.community_release(content_changed["releaseId"])

        self.assertNotEqual(baseline["releaseId"], content_changed["releaseId"])
        self.assertNotEqual(baseline["releaseId"], dependency_changed["releaseId"])
        self.assertNotEqual(community_a["releaseId"], community_b["releaseId"])

    def test_validate_release_rejects_forged_hash_addressed_identity(self):
        release = self.gear_release()
        self.assertEqual(gear_release.validate_release(release), [])
        forged = {**release, "releaseId": "gear-release:sha256:forged"}
        self.assertTrue(
            any(issue["code"] == "RELEASE_ID_MISMATCH" for issue in gear_release.validate_release(forged))
        )

    def test_release_builder_rejects_invalid_kind_status_or_missing_revision(self):
        for mutation in (
            {"release_kind": "talent"},
            {"release_status": "active"},
            {"season_revision": ""},
            {"schema_revision": ""},
        ):
            with self.subTest(mutation=mutation):
                args = {
                    "release_kind": "gear",
                    "season_revision": "season-17",
                    "schema_revision": "gear-release-v1",
                    "content": {},
                    "dependency_revisions": self.dependency_revisions(),
                    "release_status": "validated",
                    "source": {},
                    **mutation,
                }
                with self.assertRaises(ValueError):
                    gear_release.build_release(**args)

    def test_manifest_is_hash_addressed_and_binds_compatible_releases(self):
        gear = self.gear_release()
        community = self.community_release(gear["releaseId"])
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=community,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependency_revisions(),
            rollback_manifest_revision="season-manifest:sha256:old",
        )

        self.assertRegex(manifest["manifestRevision"], r"^season-manifest:sha256:[0-9a-f]{64}$")
        self.assertEqual(manifest["gearCatalogReleaseId"], gear["releaseId"])
        self.assertEqual(manifest["communityTemplateReleaseId"], community["releaseId"])
        self.assertTrue(manifest["formalActiveManifest"])
        self.assertEqual(gear_release.validate_manifest(manifest, {
            gear["releaseId"]: gear,
            community["releaseId"]: community,
        }), [])

    def test_manifest_allows_gear_only_but_rejects_mixed_or_blocked_releases(self):
        gear = self.gear_release()
        gear_only = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=None,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependency_revisions(),
        )
        self.assertEqual(gear_only["communityTemplateReleaseId"], "")

        wrong_gear = self.gear_release({"items": [{"itemId": "wrong"}]})
        community = self.community_release(wrong_gear["releaseId"])
        issues = gear_release.validate_manifest(
            {**gear_only, "communityTemplateReleaseId": community["releaseId"]},
            {gear["releaseId"]: gear, community["releaseId"]: community},
        )
        self.assertTrue(any(issue["code"] == "COMMUNITY_GEAR_RELEASE_MISMATCH" for issue in issues))

        blocked = self.gear_release(status="blocked")
        with self.assertRaises(ValueError):
            gear_release.build_manifest(
                season_revision="season-17",
                gear_release=blocked,
                community_release=None,
                talent_catalog_revision="talent-r1",
                dependency_revisions=self.dependency_revisions(),
            )

    def test_manifest_rejects_dependency_revisions_that_do_not_match_releases(self):
        gear = self.gear_release()
        community = self.community_release(gear["releaseId"])
        mismatched = {**self.dependency_revisions(), "gearRuleRevision": "gear-rule-matrix-v2"}

        with self.assertRaises(ValueError):
            gear_release.build_manifest(
                season_revision="season-17",
                gear_release=gear,
                community_release=community,
                talent_catalog_revision="talent-r1",
                dependency_revisions=mismatched,
            )

        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=community,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependency_revisions(),
        )
        tampered = {**manifest, "dependencyRevisions": mismatched}
        issues = gear_release.validate_manifest(tampered, {
            gear["releaseId"]: gear,
            community["releaseId"]: community,
        })
        self.assertTrue(any(issue["code"] == "RELEASE_DEPENDENCY_MISMATCH" for issue in issues))

    def test_manifest_validation_fails_closed_for_missing_registry_or_hash_tamper(self):
        gear = self.gear_release()
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=None,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependency_revisions(),
        )
        self.assertTrue(any(
            issue["code"] == "GEAR_RELEASE_MISSING"
            for issue in gear_release.validate_manifest(manifest, {})
        ))

        tampered = copy.deepcopy(gear)
        tampered["content"]["items"][0]["itemId"] = "tampered"
        issues = gear_release.validate_manifest(manifest, {gear["releaseId"]: tampered})
        self.assertTrue(any(issue["code"] == "RELEASE_CONTENT_HASH_MISMATCH" for issue in issues))

    def test_election_selects_one_deterministic_winner_and_internal_standby(self):
        candidates = [
            self.candidate("candidate-low", sample_count=10),
            self.candidate("candidate-high", sample_count=40, profileHash="profile-high"),
        ]
        calls = []

        def resolver(intent):
            calls.append(intent)
            return self.verified_result()

        election = gear_release.elect_community_candidates(
            candidates,
            gear_release_id="gear-release:sha256:target",
            resolver=resolver,
            now="2026-07-11T05:00:00+00:00",
            expected_specs=[("mage", "arcane")],
        )

        self.assertEqual(election["status"], "validated")
        self.assertEqual(election["winners"][0]["candidateId"], "candidate-high")
        self.assertEqual(election["winners"][0]["role"], "winner")
        self.assertEqual(election["standbys"][0]["candidateId"], "candidate-low")
        self.assertEqual(election["standbys"][0]["role"], "standby")
        self.assertEqual(election["rejected"], [])
        self.assertEqual(len(calls), 2)

    def test_election_is_input_order_stable_and_does_not_mutate_candidates(self):
        candidates = [self.candidate("b", 10), self.candidate("a", 10)]
        before = copy.deepcopy(candidates)
        resolver = lambda _intent: self.verified_result()

        first = gear_release.elect_community_candidates(
            candidates,
            gear_release_id="gear-release:sha256:target",
            resolver=resolver,
            now="2026-07-11T05:00:00+00:00",
            expected_specs=[("mage", "arcane")],
        )
        second = gear_release.elect_community_candidates(
            list(reversed(candidates)),
            gear_release_id="gear-release:sha256:target",
            resolver=resolver,
            now="2026-07-11T05:00:00+00:00",
            expected_specs=[("mage", "arcane")],
        )

        self.assertEqual(first, second)
        self.assertEqual(first["winners"][0]["candidateId"], "a")
        self.assertEqual(candidates, before)

    def test_election_rejects_non_observed_missing_provenance_and_stale_sources(self):
        candidates = [
            self.candidate("recommended", sourceKey="recommended_bis"),
            self.candidate("no-url", sourceUrl=""),
            self.candidate("no-sample", sampleCount=0),
            self.candidate("no-hash", profileHash="", gearHash=""),
            self.candidate("stale", expiresAt="2026-07-11T04:59:59+00:00"),
        ]
        resolver_calls = []
        election = gear_release.elect_community_candidates(
            candidates,
            gear_release_id="gear-release:sha256:target",
            resolver=lambda intent: resolver_calls.append(intent) or self.verified_result(),
            now="2026-07-11T05:00:00+00:00",
            expected_specs=[("mage", "arcane")],
        )

        self.assertEqual(election["status"], "degraded")
        self.assertEqual(election["winners"], [])
        self.assertEqual(len(election["rejected"]), 5)
        self.assertEqual(resolver_calls, [])
        codes = {problem["code"] for row in election["rejected"] for problem in row["problems"]}
        self.assertTrue({
            "COMMUNITY_SOURCE_NOT_PUBLIC",
            "COMMUNITY_SOURCE_URL_MISSING",
            "COMMUNITY_SAMPLE_EVIDENCE_MISSING",
            "COMMUNITY_SOURCE_HASH_MISSING",
            "COMMUNITY_SOURCE_STALE",
        }.issubset(codes))

    def test_election_rejects_missing_blocked_or_invalid_freshness_authority(self):
        candidates = [
            self.candidate("no-status", sourceStatus=""),
            self.candidate("blocked", sourceStatus="blocked"),
            self.candidate("no-expiry", expiresAt=""),
            self.candidate("invalid-expiry", expiresAt="not-a-timestamp"),
            self.candidate("naive-expiry", expiresAt="2026-07-12T04:00:00"),
        ]
        election = gear_release.elect_community_candidates(
            candidates,
            gear_release_id="gear-release:sha256:target",
            resolver=lambda _intent: self.verified_result(),
            now="2026-07-11T05:00:00+00:00",
            expected_specs=[("mage", "arcane")],
        )
        codes = {problem["code"] for row in election["rejected"] for problem in row["problems"]}
        self.assertIn("COMMUNITY_SOURCE_STATUS_MISSING", codes)
        self.assertIn("COMMUNITY_SOURCE_BLOCKED", codes)
        self.assertIn("COMMUNITY_SOURCE_EXPIRY_MISSING", codes)
        self.assertIn("COMMUNITY_SOURCE_EXPIRY_INVALID", codes)

    def test_election_rejects_invalid_intent_spec_mismatch_and_client_final_facts(self):
        wrong_spec = self.candidate("wrong-spec")
        wrong_spec["selectionIntent"]["eligibilityContext"]["specKey"] = "fire"
        forged = self.candidate("forged")
        forged["selectionIntent"]["slots"]["head"]["stats"] = {"haste": 999999}

        election = gear_release.elect_community_candidates(
            [wrong_spec, forged],
            gear_release_id="gear-release:sha256:target",
            resolver=lambda _intent: self.verified_result(),
            now="2026-07-11T05:00:00+00:00",
            expected_specs=[("mage", "arcane")],
        )

        codes = {problem["code"] for row in election["rejected"] for problem in row["problems"]}
        self.assertIn("COMMUNITY_INTENT_SPEC_MISMATCH", codes)
        self.assertIn("FORBIDDEN_CLIENT_FACT", codes)

    def test_election_rejects_missing_or_mismatched_import_evidence(self):
        missing = self.candidate("missing-evidence")
        missing.pop("importEvidence")
        mismatched = self.candidate("mismatched-evidence")
        mismatched["importEvidence"]["slots"]["head"]["itemId"] = "item-other"

        election = gear_release.elect_community_candidates(
            [missing, mismatched],
            gear_release_id="gear-release:sha256:target",
            resolver=lambda _intent: self.verified_result(),
            now="2026-07-11T05:00:00+00:00",
            expected_specs=[("mage", "arcane")],
        )

        self.assertEqual(election["status"], "degraded")
        codes = {problem["code"] for row in election["rejected"] for problem in row["problems"]}
        self.assertIn("COMMUNITY_IMPORT_EVIDENCE_MISSING", codes)
        self.assertIn("COMMUNITY_IMPORT_EVIDENCE_IDENTITY_MISMATCH", codes)

    def test_election_rejects_malformed_v2_source_race_evidence_but_retains_v1_compatibility(self):
        malformed = self.candidate("malformed-race")
        malformed["importEvidence"].update({
            "schemaRevision": "community-template-import-evidence-v2",
            "sourceRaceKey": "Night Elf",
            "sourceRaceOrigin": "source_profile",
        })
        legacy = self.candidate("legacy-v1")

        election = gear_release.elect_community_candidates(
            [malformed, legacy],
            gear_release_id="gear-release:sha256:target",
            resolver=lambda _intent: self.verified_result(),
            now="2026-07-11T05:00:00+00:00",
            expected_specs=[("mage", "arcane")],
        )

        self.assertEqual(election["status"], "validated")
        self.assertEqual(election["winners"][0]["candidateId"], "legacy-v1")
        codes = {problem["code"] for row in election["rejected"] for problem in row["problems"]}
        self.assertIn("COMMUNITY_IMPORT_EVIDENCE_INVALID", codes)

    def test_election_rejects_non_human_default_v2_source_race_evidence(self):
        malformed = self.candidate("invalid-default-race")
        malformed["importEvidence"].update({
            "schemaRevision": "community-template-import-evidence-v2",
            "sourceRaceKey": "night_elf",
            "sourceRaceOrigin": "default_human",
        })

        election = gear_release.elect_community_candidates(
            [malformed],
            gear_release_id="gear-release:sha256:target",
            resolver=lambda _intent: self.verified_result(),
            now="2026-07-11T05:00:00+00:00",
            expected_specs=[("mage", "arcane")],
        )

        self.assertEqual(election["status"], "degraded")
        codes = {problem["code"] for row in election["rejected"] for problem in row["problems"]}
        self.assertIn("COMMUNITY_IMPORT_EVIDENCE_INVALID", codes)

    def test_election_rejects_v3_stable_effects_without_a_strict_sealed_context(self):
        malformed = self.candidate("missing-stable-effects")
        malformed["importEvidence"].update({
            "schemaRevision": "community-template-import-evidence-v3",
            "sourceRaceKey": "dwarf",
            "sourceRaceOrigin": "source_profile",
        })
        legacy = self.candidate("legacy-v1")

        election = gear_release.elect_community_candidates(
            [malformed, legacy],
            gear_release_id="gear-release:sha256:target",
            resolver=lambda _intent: self.verified_result(),
            now="2026-07-11T05:00:00+00:00",
            expected_specs=[("mage", "arcane")],
        )

        self.assertEqual(election["status"], "validated")
        self.assertEqual(election["winners"][0]["candidateId"], "legacy-v1")
        rejected = [row for row in election["rejected"] if row["candidateId"] == "missing-stable-effects"]
        self.assertEqual(rejected[0]["problems"][0]["path"], "candidate.importEvidence.sourceStableEffects")

    def test_election_rejects_illegal_unready_or_release_mismatched_resolver_result(self):
        candidates = [
            self.candidate("illegal"),
            self.candidate("unready"),
            self.candidate("mixed"),
        ]

        def resolver(intent):
            item_id = intent["slots"]["head"]["itemId"]
            if item_id == "illegal":
                return self.verified_result(
                    status="blocked",
                    aggregateLegality={"status": "blocked", "problemCodes": ["GEAR_ILLEGAL"]},
                )
            if item_id == "unready":
                return self.verified_result(profileReadiness={"simcReady": False, "missingSlots": ["feet"]})
            return self.verified_result("gear-release:sha256:other")

        for candidate in candidates:
            candidate["selectionIntent"]["slots"]["head"]["itemId"] = candidate["id"]
            candidate["importEvidence"]["slots"]["head"]["itemId"] = candidate["id"]
        election = gear_release.elect_community_candidates(
            candidates,
            gear_release_id="gear-release:sha256:target",
            resolver=resolver,
            now="2026-07-11T05:00:00+00:00",
            expected_specs=[("mage", "arcane")],
        )

        codes = {problem["code"] for row in election["rejected"] for problem in row["problems"]}
        self.assertIn("COMMUNITY_RESOLVER_ILLEGAL", codes)
        self.assertIn("COMMUNITY_PROFILE_NOT_READY", codes)
        self.assertIn("COMMUNITY_GEAR_RELEASE_MISMATCH", codes)

    def test_election_carry_forward_still_calls_current_resolver(self):
        carried = self.candidate("active-winner", carryForward=True)
        calls = []
        election = gear_release.elect_community_candidates(
            [carried],
            gear_release_id="gear-release:sha256:target",
            resolver=lambda intent: calls.append(intent) or self.verified_result(),
            now="2026-07-11T05:00:00+00:00",
            expected_specs=[("mage", "arcane")],
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(election["winners"][0]["candidateId"], "active-winner")
        self.assertTrue(election["winners"][0]["carryForward"])

    def test_semantic_signature_ignores_evidence_identity_only_fields(self):
        intent = self.intent()
        old = self.verified_result()
        old["resolvedSlots"] = {
            "head": {
                "itemId": "item-head",
                "variantKey": "variant-head",
                "sourceRefIds": ["evidence:old"],
                "evidenceClaimIds": ["sha256:old"],
            }
        }
        new = copy.deepcopy(old)
        new["resolvedSlots"]["head"]["sourceRefIds"] = ["evidence:new"]
        new["resolvedSlots"]["head"]["evidenceClaimIds"] = ["sha256:new"]

        self.assertEqual(
            gear_release.semantic_gear_signature(intent, old),
            gear_release.semantic_gear_signature(intent, new),
        )

    def shadow_row(self, **overrides):
        row = {
            "classKey": "mage",
            "specKey": "arcane",
            "selectionIntent": self.intent(),
            "resolvedGearSignature": "sha256:resolved-a",
            "semanticGearSignature": "sha256:semantic-a",
            "aggregateLegality": "verified",
            "sourceKey": "raiderio_observed_profile",
            "sourceUrl": "https://raider.io/characters/cn/example",
            "profileHash": "profile-hash-a",
            "gearHash": "gear-hash-a",
            "sampleCount": 25,
            "baselineCount": 0,
            "validatedAgainstGearReleaseId": "gear-release:sha256:target",
        }
        row.update(overrides)
        return row

    def test_shadow_compare_normalizes_revision_only_changes(self):
        legacy = self.shadow_row()
        candidate = self.shadow_row(resolvedGearSignature="sha256:new-release-bound")
        candidate["selectionIntent"]["authoredAgainst"]["gearCatalogRevision"] = "gear-release:sha256:target"

        report = gear_release.compare_shadow(
            [legacy],
            [candidate],
            expected_specs=[("mage", "arcane")],
            gear_release_id="gear-release:sha256:target",
        )

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["diffs"][0]["classification"], "revision_only")

    def test_shadow_compare_accepts_gear_hash_when_legacy_profile_hash_is_missing(self):
        legacy = self.shadow_row()
        candidate = self.shadow_row(
            profileHash="",
            resolvedGearSignature="sha256:new-release-bound",
        )
        candidate["selectionIntent"]["authoredAgainst"]["gearCatalogRevision"] = "gear-release:sha256:target"

        report = gear_release.compare_shadow(
            [legacy],
            [candidate],
            expected_specs=[("mage", "arcane")],
            gear_release_id="gear-release:sha256:target",
        )

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["diffs"][0]["classification"], "revision_only")

    def test_shadow_compare_blocks_semantic_winner_provenance_or_baseline_regression(self):
        mutations = (
            {"semanticGearSignature": "sha256:different"},
            {"profileHash": "profile-hash-different"},
            {"sourceUrl": "https://different.example"},
            {"baselineCount": 1},
            {"sourceKey": "season_recommendation"},
            {"aggregateLegality": "blocked"},
            {"validatedAgainstGearReleaseId": "gear-release:sha256:other"},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                report = gear_release.compare_shadow(
                    [self.shadow_row()],
                    [self.shadow_row(**mutation)],
                    expected_specs=[("mage", "arcane")],
                    gear_release_id="gear-release:sha256:target",
                )
                self.assertEqual(report["status"], "blocked")
                self.assertTrue(report["blockers"])

    def test_shadow_compare_treats_import_evidence_slot_change_as_semantic_change(self):
        legacy = self.shadow_row(importEvidence={
            "schemaRevision": "community-template-import-evidence-v1",
            "sourceFingerprint": "sha256:" + "a" * 64,
            "slots": {"head": {"itemId": "item-head", "variantKey": "variant-head", "observedItemLevel": 292, "iconUrl": "https://render.worldofwarcraft.com/icons/a.jpg"}},
        })
        candidate = self.shadow_row(importEvidence={
            "schemaRevision": "community-template-import-evidence-v1",
            "sourceFingerprint": "sha256:" + "a" * 64,
            "slots": {"head": {"itemId": "item-head", "variantKey": "variant-head", "observedItemLevel": 293, "iconUrl": "https://render.worldofwarcraft.com/icons/a.jpg"}},
        })

        report = gear_release.compare_shadow(
            [legacy],
            [candidate],
            expected_specs=[("mage", "arcane")],
            gear_release_id="gear-release:sha256:target",
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["diffs"][0]["classification"], "semantic_change")

    def test_shadow_compare_ignores_release_identity_only_import_fingerprint(self):
        legacy = self.shadow_row(importEvidence={
            "schemaRevision": "community-template-import-evidence-v1",
            "sourceFingerprint": "sha256:" + "a" * 64,
            "slots": {"head": {"itemId": "item-head", "variantKey": "variant-head", "observedItemLevel": 292, "iconUrl": "https://render.worldofwarcraft.com/icons/a.jpg"}},
        })
        candidate = self.shadow_row(importEvidence={
            "schemaRevision": "community-template-import-evidence-v1",
            "sourceFingerprint": "sha256:" + "b" * 64,
            "slots": {"head": {"itemId": "item-head", "variantKey": "variant-head", "observedItemLevel": 292, "iconUrl": "https://render.worldofwarcraft.com/icons/a.jpg"}},
        })

        report = gear_release.compare_shadow(
            [legacy],
            [candidate],
            expected_specs=[("mage", "arcane")],
            gear_release_id="gear-release:sha256:target",
        )

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["diffs"][0]["classification"], "match")

    def test_shadow_compare_allows_only_preverified_enhancement_migration_semantics(self):
        legacy = self.shadow_row()
        candidate = self.shadow_row(
            semanticGearSignature="sha256:canonical-enhancement-state",
            resolvedGearSignature="sha256:canonical-release-bound",
        )
        candidate["selectionIntent"]["slots"]["head"]["gemOptionIds"] = ["gem-240892"]

        report = gear_release.compare_shadow(
            [legacy],
            [candidate],
            expected_specs=[("mage", "arcane")],
            gear_release_id="gear-release:sha256:target",
            allowed_semantic_change_specs={("mage", "arcane")},
        )

        self.assertEqual(report["status"], "pass")
        self.assertEqual(
            report["diffs"][0]["classification"],
            "expected_enhancement_migration",
        )
        provenance_change = copy.deepcopy(candidate)
        provenance_change["gearHash"] = "gear-hash-different"
        blocked = gear_release.compare_shadow(
            [legacy],
            [provenance_change],
            expected_specs=[("mage", "arcane")],
            gear_release_id="gear-release:sha256:target",
            allowed_semantic_change_specs={("mage", "arcane")},
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn(
            "PUBLIC_WINNER_SEMANTIC_CHANGE",
            {problem["code"] for problem in blocked["blockers"]},
        )

    def test_observed_import_fidelity_cutover_requires_exact_legacy_source_identity(self):
        legacy = self.candidate()
        legacy.pop("importEvidence")
        legacy["templateId"] = "observed_profile_mage_arcane"
        candidate = self.candidate(templateId="observed_profile_mage_arcane")
        candidate["payload"] = {"importEvidence": candidate.pop("importEvidence")}

        self.assertTrue(
            gear_release.is_observed_import_fidelity_cutover(legacy, candidate)
        )

        profile_hash_missing_on_both_sides = copy.deepcopy(legacy)
        profile_hash_missing_on_both_sides["profileHash"] = ""
        candidate_without_profile_hash = copy.deepcopy(candidate)
        candidate_without_profile_hash["profileHash"] = ""
        self.assertTrue(
            gear_release.is_observed_import_fidelity_cutover(
                profile_hash_missing_on_both_sides,
                candidate_without_profile_hash,
            )
        )

        for mutation in (
            {"gearHash": "gear-hash-different"},
            {"sourceUrl": "https://raider.io/characters/cn/different"},
            {"sampleCount": 24},
            {"profileHash": "profile-hash-different"},
        ):
            with self.subTest(mutation=mutation):
                self.assertFalse(
                    gear_release.is_observed_import_fidelity_cutover(
                        legacy,
                        {**candidate, **mutation},
                    )
                )

        legacy_with_evidence = copy.deepcopy(legacy)
        legacy_with_evidence["importEvidence"] = copy.deepcopy(
            candidate["payload"]["importEvidence"]
        )
        self.assertFalse(
            gear_release.is_observed_import_fidelity_cutover(
                legacy_with_evidence,
                candidate,
            )
        )

    def test_shadow_compare_allows_only_preverified_import_fidelity_cutover(self):
        legacy = self.shadow_row(templateId="observed_profile_mage_arcane")
        candidate = self.shadow_row(
            templateId="observed_profile_mage_arcane",
            semanticGearSignature="sha256:canonical-observed-import",
            resolvedGearSignature="sha256:canonical-release-bound",
            importEvidence=self.candidate()["importEvidence"],
        )
        candidate["selectionIntent"]["slots"]["head"]["gemOptionIds"] = ["gem-240892"]

        report = gear_release.compare_shadow(
            [legacy],
            [candidate],
            expected_specs=[("mage", "arcane")],
            gear_release_id="gear-release:sha256:target",
            allowed_import_fidelity_cutover_specs={("mage", "arcane")},
        )

        self.assertEqual(report["status"], "pass")
        self.assertEqual(
            report["diffs"][0]["classification"],
            "expected_import_fidelity_cutover",
        )

        provenance_changed = copy.deepcopy(candidate)
        provenance_changed["gearHash"] = "gear-hash-different"
        blocked = gear_release.compare_shadow(
            [legacy],
            [provenance_changed],
            expected_specs=[("mage", "arcane")],
            gear_release_id="gear-release:sha256:target",
            allowed_import_fidelity_cutover_specs={("mage", "arcane")},
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn(
            "PUBLIC_WINNER_SEMANTIC_CHANGE",
            {problem["code"] for problem in blocked["blockers"]},
        )

        unsealed = copy.deepcopy(candidate)
        unsealed.pop("importEvidence")
        unsealed_report = gear_release.compare_shadow(
            [legacy],
            [unsealed],
            expected_specs=[("mage", "arcane")],
            gear_release_id="gear-release:sha256:target",
            allowed_import_fidelity_cutover_specs={("mage", "arcane")},
        )
        self.assertEqual(unsealed_report["status"], "blocked")
        self.assertIn(
            "PUBLIC_WINNER_SEMANTIC_CHANGE",
            {problem["code"] for problem in unsealed_report["blockers"]},
        )

    def test_shadow_compare_marks_missing_spec_degraded_and_blocks_public_extra_spec(self):
        degraded = gear_release.compare_shadow(
            [self.shadow_row()],
            [],
            expected_specs=[("mage", "arcane")],
            gear_release_id="gear-release:sha256:target",
        )
        self.assertEqual(degraded["status"], "degraded")
        self.assertEqual(degraded["emptySpecs"], [{"classKey": "mage", "specKey": "arcane"}])

        extra = self.shadow_row(classKey="warrior", specKey="fury")
        blocked = gear_release.compare_shadow(
            [self.shadow_row()],
            [self.shadow_row(), extra],
            expected_specs=[("mage", "arcane")],
            gear_release_id="gear-release:sha256:target",
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertTrue(any(problem["code"] == "UNEXPECTED_PUBLIC_SPEC" for problem in blocked["blockers"]))

    def test_promotion_decision_allows_only_approved_auto_classes(self):
        passing_shadow = {"status": "pass", "blockers": [], "emptySpecs": []}
        same_gear = gear_release.decide_promotion(
            risk_class="same_gear_community",
            shadow_report=passing_shadow,
            coverage_regressions=[],
            full_matrix_passed=True,
        )
        additive = gear_release.decide_promotion(
            risk_class="low_risk_additive_gear",
            shadow_report=passing_shadow,
            coverage_regressions=[],
            full_matrix_passed=True,
        )
        controlled = gear_release.decide_promotion(
            risk_class="new_season",
            shadow_report=passing_shadow,
            coverage_regressions=[],
            full_matrix_passed=True,
        )

        self.assertEqual(same_gear["decision"], "auto_promote")
        self.assertEqual(additive["decision"], "auto_promote")
        self.assertEqual(controlled["decision"], "manual_required")

    def test_promotion_decision_blocks_shadow_matrix_or_coverage_failure(self):
        cases = (
            {
                "shadow_report": {"status": "blocked", "blockers": [{"code": "MIXED"}]},
                "coverage_regressions": [],
                "full_matrix_passed": True,
            },
            {
                "shadow_report": {"status": "pass", "blockers": []},
                "coverage_regressions": [{"classKey": "mage", "specKey": "arcane"}],
                "full_matrix_passed": True,
            },
            {
                "shadow_report": {"status": "pass", "blockers": []},
                "coverage_regressions": [],
                "full_matrix_passed": False,
            },
        )
        for case in cases:
            with self.subTest(case=case):
                result = gear_release.decide_promotion(risk_class="same_gear_community", **case)
                self.assertEqual(result["decision"], "blocked")
                self.assertTrue(result["blockers"])

        not_run = gear_release.decide_promotion(
            risk_class="same_gear_community",
            shadow_report={"status": "not_run", "blockers": []},
            coverage_regressions=[],
            full_matrix_passed=True,
        )
        self.assertEqual(not_run["decision"], "blocked")
        self.assertTrue(any(problem["code"] == "SHADOW_COMPARE_REQUIRED" for problem in not_run["blockers"]))

    def test_pointer_commands_are_exact_compare_and_swap_intents(self):
        promote = gear_release.build_pointer_command(
            action="promote",
            manifest_revision="season-manifest:sha256:new",
            expected_generation=7,
            rollback_manifest_revision="season-manifest:sha256:old",
        )
        rollback = gear_release.build_pointer_command(
            action="rollback",
            manifest_revision="",
            expected_generation=8,
            target_mode="transitional",
        )

        self.assertEqual(promote, {
            "schemaRevision": "active-manifest-pointer-command-v2",
            "action": "promote",
            "environment": "retail",
            "targetMode": "active",
            "manifestRevision": "season-manifest:sha256:new",
            "expectedGeneration": 7,
            "rollbackManifestRevision": "season-manifest:sha256:old",
        })
        self.assertEqual(rollback, {
            "schemaRevision": "active-manifest-pointer-command-v2",
            "action": "rollback",
            "environment": "retail",
            "targetMode": "transitional",
            "manifestRevision": "",
            "expectedGeneration": 8,
            "rollbackManifestRevision": "",
        })
        with self.assertRaises(ValueError):
            gear_release.build_pointer_command("delete", "x", 1)
        with self.assertRaises(ValueError):
            gear_release.build_pointer_command("promote", "x", -1)
        with self.assertRaises(ValueError):
            gear_release.build_pointer_command("promote", "", 1, target_mode="transitional")
        with self.assertRaises(ValueError):
            gear_release.build_pointer_command("rollback", "x", 1, target_mode="transitional")
        with self.assertRaises(ValueError):
            gear_release.build_pointer_command("rollback", "", 1, "x", target_mode="transitional")

    def test_catalyst_allowlist_cannot_produce_verified_capability(self):
        capability = gear_release.validate_capability_proof({
            "capabilityKey": "catalyst_preserve_secondary_stats",
            "parserAllowlisted": True,
            "overlayPolicyVerified": False,
            "resolverFixtureVerified": False,
            "serializerFixtureVerified": False,
            "simcRuntimeFixtureVerified": False,
            "frontendExplanationVerified": False,
            "manifestRevisionBound": False,
        })

        self.assertEqual(capability["status"], "blocked")
        self.assertFalse(capability["capabilityEnabled"])
        self.assertIn("CATALYST_PROOF_MATRIX_INCOMPLETE", capability["blockers"])

    def test_release_domain_is_pure_and_has_no_runtime_or_persistence_access(self):
        source = inspect.getsource(gear_release)
        for forbidden in (
            "sqlite3",
            "psycopg",
            "postgres_cache_store",
            "news_backend",
            "subprocess",
            "requests",
            "urllib",
            "open(",
            "os.environ",
            "datetime.now",
        ):
            self.assertNotIn(forbidden, source)
        for name in gear_release.__all__:
            value = getattr(gear_release, name)
            if callable(value):
                parameters = inspect.signature(value).parameters
                self.assertNotIn("conn", parameters)
                self.assertNotIn("store", parameters)


if __name__ == "__main__":
    unittest.main()

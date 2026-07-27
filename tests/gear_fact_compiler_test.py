import copy
import json
import unittest

from server import gear_evidence_registry, gear_fact_compiler, gear_rule_matrix


SEASON_REVISION = "midnight-season-1"
SUBJECT_KEY = "item:250033/variant:void_upgrade-298"


class GearFactCompilerTest(unittest.TestCase):
    def setUp(self):
        self.artifacts = {}

    def observation(
        self,
        fact_type,
        value,
        *,
        artifact_id=None,
        parser_revision="simc-item-probe-observer-v1",
        source_scope="exact_variant",
        subject_key=SUBJECT_KEY,
        artifact_source_type=None,
    ):
        source_type = artifact_source_type or {
            "battle-net-item-observer-v1": "battle_net_item",
            "simc-item-probe-observer-v1": "simc_item_probe",
            "simc-bonus-probe-observer-v1": "simc_bonus_probe",
            "season-rule-observer-v1": "season_rule",
        }.get(parser_revision, "simc_item_probe")
        marker = artifact_id or f"{fact_type}:{len(self.artifacts)}"
        artifact = gear_evidence_registry.build_evidence_artifact(
            source_type=source_type,
            source_identity=f"fixture:{marker}",
            source_revision=f"{source_type}-revision-1",
            season_revision=SEASON_REVISION,
            captured_at="2026-07-26T00:00:00Z",
            payload={"fixture": marker},
        )
        self.artifacts[artifact["artifactId"]] = artifact
        return gear_evidence_registry.build_evidence_observation(
            artifact_id=artifact["artifactId"],
            subject_key=subject_key,
            fact_type=fact_type,
            observed_value=value,
            parser_revision=parser_revision,
            source_scope=source_scope,
            status="accepted",
        )

    def fact(
        self,
        observations,
        fact_type,
        *,
        policies=None,
        subject_key=SUBJECT_KEY,
        artifacts=None,
    ):
        facts = gear_fact_compiler.compile_subject_facts(
            season_revision=SEASON_REVISION,
            subject_key=subject_key,
            observations=observations,
            artifacts=(
                self.artifacts.values()
                if artifacts is None
                else artifacts
            ),
            fact_types=[fact_type],
            policies=policies,
        )
        self.assertEqual(len(facts), 1)
        return facts[0]

    def test_every_first_stage_policy_declares_all_decision_dimensions(self):
        expected_types = {
            "equipment_uniqueness",
            "executable_item_options",
            "item_identity",
            "slot_compatibility",
            "variant_track",
            "static_stats",
            "socket_count",
            "enchant_capability",
            "embellishment_capability",
            "enhancement_option",
            "allowed_enhancement_options",
            "item_set_membership",
        }
        required_fields = {
            "allowedSources",
            "sourceScopes",
            "combinationMode",
            "closedWorldCondition",
            "conflictPolicy",
            "impactScope",
            "ruleRevision",
        }

        self.assertEqual(set(gear_fact_compiler.FACT_POLICIES), expected_types)
        for fact_type, policy in gear_fact_compiler.FACT_POLICIES.items():
            with self.subTest(fact_type=fact_type):
                self.assertTrue(required_fields.issubset(policy))
                self.assertTrue(policy["allowedSources"])
                self.assertTrue(policy["sourceScopes"])
                self.assertTrue(policy["ruleRevision"])

    def test_each_first_stage_policy_compiles_an_allowed_exact_observation(self):
        fixtures = {
            "item_identity": {"itemId": "250033", "variantKey": "void_upgrade-298"},
            "slot_compatibility": ["head"],
            "variant_track": {
                "itemId": "250033",
                "itemLevel": 289,
                "track": "void_upgrade",
                "variantKey": "void_upgrade-298",
            },
            "static_stats": {"haste": 812, "stamina": 1218},
            "socket_count": 1,
            "enchant_capability": False,
            "embellishment_capability": True,
            "executable_item_options": {
                "itemId": "250033",
                "variantKey": "void_upgrade-298",
                "options": {
                    "bonus_id": "13786/6652",
                    "ilevel": "298",
                },
            },
            "enhancement_option": {
                "applicableScopes": ["head"],
                "effect": {"haste": 147},
                "optionId": "gem:240001",
                "optionType": "gem",
            },
            "item_set_membership": "set:42",
            "equipment_uniqueness": {
                "isUnique": True,
                "groupId": "unique-ring:test",
                "limit": 1,
            },
        }
        parser_revisions = {
            "item_identity": "battle-net-item-observer-v1",
            "slot_compatibility": "battle-net-item-observer-v1",
            "enchant_capability": "season-rule-observer-v1",
            "embellishment_capability": "battle-net-item-observer-v1",
            "allowed_enhancement_options": "season-rule-observer-v1",
            "item_set_membership": "battle-net-item-observer-v1",
            "equipment_uniqueness": "battle-net-item-observer-v1",
        }
        source_scopes = {
            "enchant_capability": "slot_rule",
            "allowed_enhancement_options": "slot_rule",
            "equipment_uniqueness": "base_item",
        }
        subject_keys = {
            "enhancement_option": "option:gem:240001",
            "equipment_uniqueness": "item:250033",
        }

        for fact_type, expected in fixtures.items():
            with self.subTest(fact_type=fact_type):
                subject_key = subject_keys.get(fact_type, SUBJECT_KEY)
                fact = self.fact(
                    [
                        self.observation(
                            fact_type,
                            expected,
                            parser_revision=parser_revisions.get(
                                fact_type, "simc-item-probe-observer-v1"
                            ),
                            source_scope=source_scopes.get(
                                fact_type, "exact_variant"
                            ),
                            subject_key=subject_key,
                        )
                    ],
                    fact_type,
                    subject_key=subject_key,
                )
                self.assertEqual(fact["status"], "verified")
                self.assertEqual(fact["value"], expected)
                self.assertEqual(fact["problemCode"], "")

    def test_executable_item_options_rejects_unknown_or_missing_identity_fields(self):
        malformed_values = [
            {
                "itemId": "250033",
                "variantKey": "void_upgrade-298",
                "options": {"ilevel": "298"},
            },
            {
                "itemId": "250033",
                "variantKey": "void_upgrade-298",
                "options": {
                    "bonus_id": "13786",
                    "ilevel": "298",
                    "private_writer": "must-not-pass",
                },
            },
            {
                "itemId": "250033",
                "variantKey": "void_upgrade-298",
                "options": {
                    "bonus_id": "13786",
                    "embellishment": "built_in",
                    "ilevel": "298",
                },
                "enhancementManagement": "forged",
            },
        ]

        for value in malformed_values:
            with self.subTest(value=value):
                fact = self.fact(
                    [self.observation("executable_item_options", value)],
                    "executable_item_options",
                )
                self.assertEqual(fact["status"], "unresolved_missing")
                self.assertEqual(fact["problemCode"], "parser_unhandled_shape")

    def test_equipment_uniqueness_requires_explicit_nonunique_or_complete_unique_rule(self):
        valid_nonunique = self.fact(
            [
                self.observation(
                    "equipment_uniqueness",
                    {"isUnique": False},
                    parser_revision="battle-net-item-observer-v1",
                    source_scope="base_item",
                    subject_key="item:250033",
                )
            ],
            "equipment_uniqueness",
            subject_key="item:250033",
        )
        self.assertEqual(valid_nonunique["status"], "verified")
        self.assertEqual(valid_nonunique["value"], {"isUnique": False})

        malformed = self.fact(
            [
                self.observation(
                    "equipment_uniqueness",
                    {"isUnique": True, "groupId": "", "limit": 0},
                    parser_revision="battle-net-item-observer-v1",
                    source_scope="base_item",
                    subject_key="item:250033",
                )
            ],
            "equipment_uniqueness",
            subject_key="item:250033",
        )
        self.assertEqual(malformed["status"], "unresolved_missing")
        self.assertEqual(malformed["problemCode"], "parser_unhandled_shape")

    def test_known_exact_variant_compiles_one_verified_socket(self):
        battle_net_without_explicit_socket = self.observation(
            "item_identity",
            {"itemId": "250033", "variantKey": "void_upgrade-298"},
            parser_revision="battle-net-item-observer-v1",
        )
        simc_socket = self.observation("socket_count", 1)

        fact = self.fact(
            [battle_net_without_explicit_socket, simc_socket], "socket_count"
        )

        self.assertEqual(fact["subjectKey"], SUBJECT_KEY)
        self.assertEqual(fact["status"], "verified")
        self.assertEqual(fact["value"], 1)
        self.assertEqual(fact["observationRefs"], [simc_socket["observationId"]])

    def test_explicit_zero_is_verified_but_absence_is_not_zero(self):
        explicit_zero = self.fact(
            [
                self.observation(
                    "socket_count",
                    0,
                    parser_revision="battle-net-item-observer-v1",
                )
            ],
            "socket_count",
        )
        missing = self.fact([], "socket_count")

        self.assertEqual(explicit_zero["status"], "verified")
        self.assertEqual(explicit_zero["value"], 0)
        self.assertEqual(missing["status"], "unresolved_missing")
        self.assertIsNone(missing["value"])
        self.assertEqual(missing["problemCode"], "artifact_missing")

    def test_conflicting_exact_observations_fail_closed(self):
        zero = self.observation(
            "socket_count",
            0,
            artifact_id="gear-artifact:sha256:" + "0" * 64,
            parser_revision="battle-net-item-observer-v1",
        )
        one = self.observation(
            "socket_count",
            1,
            artifact_id="gear-artifact:sha256:" + "1" * 64,
        )

        fact = self.fact([one, zero], "socket_count")

        self.assertEqual(fact["status"], "unresolved_conflict")
        self.assertIsNone(fact["value"])
        self.assertEqual(fact["problemCode"], "observation_conflict")
        self.assertEqual(
            fact["observationRefs"],
            sorted([zero["observationId"], one["observationId"]]),
        )

    def test_socket_lower_bound_sources_combine_by_max_without_summing(self):
        season_floor = self.observation(
            "socket_count",
            1,
            artifact_id="gear-artifact:sha256:" + "a" * 64,
            parser_revision="season-rule-observer-v1",
            source_scope="season_slot",
        )
        bonus_floor = self.observation(
            "socket_count",
            2,
            artifact_id="gear-artifact:sha256:" + "b" * 64,
            parser_revision="simc-bonus-probe-observer-v1",
        )

        fact = self.fact([season_floor, bonus_floor], "socket_count")

        self.assertEqual(fact["status"], "verified")
        self.assertEqual(fact["value"], 2)
        self.assertNotEqual(fact["value"], 3)

    def test_policy_revision_invalidates_provenance_without_changing_fact_identity(self):
        observation = self.observation("socket_count", 1)
        baseline = self.fact([observation], "socket_count")
        policies = copy.deepcopy(gear_fact_compiler.FACT_POLICIES)
        policies["socket_count"]["ruleRevision"] = "gear-socket-policy-v2"

        revised = self.fact(
            [observation], "socket_count", policies=policies
        )

        self.assertEqual(baseline["factKey"], revised["factKey"])
        self.assertEqual(baseline["factValueHash"], revised["factValueHash"])
        self.assertNotEqual(baseline["provenanceHash"], revised["provenanceHash"])
        self.assertNotEqual(
            baseline["compilerRuleRevision"], revised["compilerRuleRevision"]
        )

    def test_recompilation_is_byte_for_byte_deterministic(self):
        observations = [
            self.observation("socket_count", 1),
            self.observation(
                "item_identity",
                {"variantKey": "void_upgrade-298", "itemId": "250033"},
                parser_revision="battle-net-item-observer-v1",
            ),
        ]

        first = gear_fact_compiler.compile_facts(
            season_revision=SEASON_REVISION,
            observations=observations,
            artifacts=self.artifacts.values(),
            subjects=[SUBJECT_KEY],
            fact_types=["socket_count", "item_identity"],
        )
        replay = gear_fact_compiler.compile_facts(
            season_revision=SEASON_REVISION,
            observations=list(reversed(observations)),
            artifacts=reversed(list(self.artifacts.values())),
            subjects=[SUBJECT_KEY],
            fact_types=["item_identity", "socket_count"],
        )

        encoded_first = json.dumps(
            first, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        encoded_replay = json.dumps(
            replay, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        self.assertEqual(encoded_first, encoded_replay)

    def test_batch_compilation_accepts_one_shot_evidence_for_multiple_subjects(self):
        first_subject = SUBJECT_KEY
        second_subject = "item:250034/variant:void_upgrade-299"
        first = self.observation(
            "socket_count",
            1,
            subject_key=first_subject,
        )
        second = self.observation(
            "socket_count",
            0,
            subject_key=second_subject,
            artifact_id="batch-second-socket",
        )

        facts = gear_fact_compiler.compile_facts_by_subject(
            season_revision=SEASON_REVISION,
            observations=(row for row in (first, second)),
            artifacts=(row for row in self.artifacts.values()),
            fact_types_by_subject={
                first_subject: ["socket_count"],
                second_subject: ["socket_count"],
            },
        )

        self.assertEqual(
            {
                (fact["subjectKey"], fact["factType"]): (
                    fact["status"],
                    fact["value"],
                )
                for fact in facts
            },
            {
                (first_subject, "socket_count"): ("verified", 1),
                (second_subject, "socket_count"): ("verified", 0),
            },
        )

    def test_batch_compilation_resolves_cross_subject_option_dependencies(self):
        capability = self.observation("socket_count", 1)
        static_slot = self.observation(
            "slot_compatibility",
            ["head"],
            parser_revision="battle-net-item-observer-v1",
        )
        slot_rule = self.observation(
            "allowed_enhancement_options",
            {
                "capabilityFactType": "socket_count",
                "optionIds": ["gem:240001"],
                "slot": "head",
            },
            parser_revision="season-rule-observer-v1",
            source_scope="slot_rule",
        )
        option = self.observation(
            "enhancement_option",
            {
                "applicableScopes": ["head"],
                "effect": {"haste": 147},
                "optionId": "gem:240001",
                "optionType": "gem",
            },
            subject_key="option:gem:240001",
        )
        conflicting_option = self.observation(
            "enhancement_option",
            {
                "applicableScopes": ["head"],
                "effect": {"haste": 148},
                "optionId": "gem:240001",
                "optionType": "gem",
            },
            artifact_id="batch-conflicting-option",
            subject_key="option:gem:240001",
        )

        def batch_fact(rows):
            facts = gear_fact_compiler.compile_facts_by_subject(
                season_revision=SEASON_REVISION,
                observations=rows,
                artifacts=self.artifacts.values(),
                fact_types_by_subject={
                    SUBJECT_KEY: ["allowed_enhancement_options"],
                },
            )
            self.assertEqual(len(facts), 1)
            return facts[0]

        verified = batch_fact([capability, static_slot, slot_rule, option])
        missing = batch_fact([capability, static_slot, slot_rule])
        conflict = batch_fact(
            [
                capability,
                static_slot,
                slot_rule,
                option,
                conflicting_option,
            ]
        )

        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["value"], ["gem:240001"])
        self.assertEqual(missing["status"], "unresolved_missing")
        self.assertEqual(conflict["status"], "unresolved_conflict")

    def test_incomplete_closed_world_values_remain_unresolved_missing(self):
        cases = {
            "variant_track": {"itemLevel": 289, "track": "void_upgrade"},
            "enhancement_option": {"optionId": "gem:240001"},
        }

        for fact_type, incomplete in cases.items():
            with self.subTest(fact_type=fact_type):
                fact = self.fact(
                    [self.observation(fact_type, incomplete)],
                    fact_type,
                )
                self.assertEqual(fact["status"], "unresolved_missing")
                self.assertIsNone(fact["value"])

    def test_malformed_eligible_sibling_prevents_verified_closed_world_fact(self):
        complete = self.observation(
            "variant_track",
            {
                "itemId": "250033",
                "itemLevel": 289,
                "track": "void_upgrade",
                "variantKey": "void_upgrade-298",
            },
        )
        malformed = self.observation(
            "variant_track",
            {"itemLevel": 289, "track": "void_upgrade"},
            artifact_id="malformed-variant-track-sibling",
        )

        fact = self.fact([complete, malformed], "variant_track")

        self.assertEqual(fact["status"], "unresolved_missing")
        self.assertIsNone(fact["value"])
        self.assertEqual(fact["problemCode"], "parser_unhandled_shape")

    def test_allowed_options_require_verified_capability_option_and_slot_rule_basis(self):
        capability = self.observation("socket_count", 1)
        option = self.observation(
            "enhancement_option",
            {
                "applicableScopes": ["head"],
                "effect": {"haste": 147},
                "optionId": "gem:240001",
                "optionType": "gem",
            },
            subject_key="option:gem:240001",
        )
        slot_rule = self.observation(
            "allowed_enhancement_options",
            {
                "capabilityFactType": "socket_count",
                "optionIds": ["gem:240001"],
                "slot": "head",
            },
            parser_revision="season-rule-observer-v1",
            source_scope="slot_rule",
        )
        static_slot = self.observation(
            "slot_compatibility",
            ["head"],
            parser_revision="battle-net-item-observer-v1",
        )

        verified = self.fact(
            [slot_rule, option, capability, static_slot],
            "allowed_enhancement_options",
        )
        missing_option = self.fact(
            [slot_rule, capability, static_slot],
            "allowed_enhancement_options",
        )
        missing_capability = self.fact(
            [slot_rule, option, static_slot],
            "allowed_enhancement_options",
        )
        missing_static_slot = self.fact(
            [slot_rule, option, capability],
            "allowed_enhancement_options",
        )
        incompatible_slot_rule = self.observation(
            "allowed_enhancement_options",
            {
                "capabilityFactType": "socket_count",
                "optionIds": ["gem:240001"],
                "slot": "head",
            },
            parser_revision="season-rule-observer-v1",
            source_scope="slot_rule",
        )
        wrist_static_slot = self.observation(
            "slot_compatibility",
            ["wrist"],
            artifact_id="wrist-static-slot",
            parser_revision="battle-net-item-observer-v1",
        )
        incompatible_scope = self.fact(
            [
                incompatible_slot_rule,
                option,
                capability,
                wrist_static_slot,
            ],
            "allowed_enhancement_options",
        )
        malformed_rule = self.observation(
            "allowed_enhancement_options",
            {
                "capabilityFactType": "socket_count",
                "optionIds": ["gem:240001"],
            },
            artifact_id="malformed-allowed-rule-sibling",
            parser_revision="season-rule-observer-v1",
            source_scope="slot_rule",
        )
        malformed_sibling = self.fact(
            [slot_rule, malformed_rule, option, capability, static_slot],
            "allowed_enhancement_options",
        )
        mixed_option_ids = self.observation(
            "allowed_enhancement_options",
            {
                "capabilityFactType": "socket_count",
                "optionIds": ["gem:240001", 240002],
                "slot": "head",
            },
            artifact_id="mixed-option-id-rule",
            parser_revision="season-rule-observer-v1",
            source_scope="slot_rule",
        )
        mixed_ids = self.fact(
            [mixed_option_ids, option, capability, static_slot],
            "allowed_enhancement_options",
        )

        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["value"], ["gem:240001"])
        self.assertEqual(missing_option["status"], "unresolved_missing")
        self.assertEqual(missing_capability["status"], "unresolved_missing")
        self.assertEqual(missing_static_slot["status"], "unresolved_missing")
        self.assertEqual(incompatible_scope["status"], "unresolved_missing")
        self.assertEqual(malformed_sibling["status"], "unresolved_missing")
        self.assertEqual(mixed_ids["status"], "unresolved_missing")
        self.assertEqual(
            mixed_ids["problemCode"], "parser_unhandled_shape"
        )

    def test_allowed_options_accept_explicit_wildcard_option_scope(self):
        capability = self.observation("socket_count", 1)
        option = self.observation(
            "enhancement_option",
            {
                "applicableScopes": ["*"],
                "effect": {"gem_id": "240001"},
                "optionId": "gem:240001",
                "optionType": "gem",
            },
            subject_key="option:gem:240001",
        )
        slot_rule = self.observation(
            "allowed_enhancement_options",
            {
                "capabilityFactType": "socket_count",
                "optionIds": ["gem:240001"],
                "slot": "head",
            },
            parser_revision="season-rule-observer-v1",
            source_scope="slot_rule",
        )
        static_slot = self.observation(
            "slot_compatibility",
            ["head"],
            parser_revision="battle-net-item-observer-v1",
        )

        fact = self.fact(
            [slot_rule, option, capability, static_slot],
            "allowed_enhancement_options",
        )

        self.assertEqual(fact["status"], "verified")
        self.assertEqual(fact["value"], ["gem:240001"])

    def test_source_policy_is_anchored_to_referenced_immutable_artifact(self):
        spoofed = self.observation(
            "static_stats",
            {"haste": 812},
            parser_revision="simc-item-probe-observer-v1",
            artifact_source_type="season_rule",
        )
        spoofed["sourceType"] = "simc_item_probe"

        fact = self.fact([spoofed], "static_stats")

        self.assertEqual(fact["status"], "unresolved_missing")
        self.assertIsNone(fact["value"])
        self.assertEqual(fact["problemCode"], "compiler_policy_missing")

    def test_missing_referenced_artifact_fails_closed(self):
        observation = self.observation("socket_count", 1)
        self.artifacts.pop(observation["artifactId"])

        fact = self.fact([observation], "socket_count")

        self.assertEqual(fact["status"], "unresolved_missing")
        self.assertIsNone(fact["value"])
        self.assertEqual(fact["problemCode"], "artifact_missing")

    def test_duplicate_conflicting_artifact_ids_fail_closed_deterministically(self):
        observation = self.observation("static_stats", {"haste": 812})
        artifact = self.artifacts[observation["artifactId"]]
        conflicting = {**artifact, "sourceType": "season_rule"}

        forward = self.fact(
            [observation],
            "static_stats",
            artifacts=[artifact, conflicting],
        )
        reversed_order = self.fact(
            [observation],
            "static_stats",
            artifacts=[conflicting, artifact],
        )

        self.assertEqual(forward["status"], "unresolved_missing")
        self.assertEqual(forward["problemCode"], "artifact_missing")
        self.assertEqual(forward, reversed_order)

    def test_unresolved_facts_project_time_free_gap_requirements(self):
        missing = self.fact([], "socket_count")
        conflict = self.fact(
            [
                self.observation("socket_count", 0),
                self.observation(
                    "socket_count",
                    1,
                    artifact_id="gear-artifact:sha256:" + "f" * 64,
                ),
            ],
            "socket_count",
        )

        gaps = gear_fact_compiler.evidence_gaps_from_facts([conflict, missing])

        self.assertEqual(
            [gap["problemCode"] for gap in gaps],
            ["artifact_missing", "observation_conflict"],
        )
        self.assertTrue(all("nextAttemptAt" not in gap for gap in gaps))
        self.assertTrue(
            all("value" not in gap["missingRequirement"] for gap in gaps)
        )
        missing_gap = next(gap for gap in gaps if gap["problemCode"] == "artifact_missing")
        self.assertEqual(
            missing_gap["missingRequirement"],
            {
                "compilerRuleRevision": "gear-socket-count-policy-v2",
                "factType": "socket_count",
                "requiredInputKey": "allowed_observation",
                "seasonRevision": SEASON_REVISION,
                "sourceScope": "exact_variant",
                "sourceType": "simc_bonus_probe",
                "subjectKey": SUBJECT_KEY,
            },
        )
        conflict_gap = next(gap for gap in gaps if gap["problemCode"] == "observation_conflict")
        self.assertNotIn("sourceType", conflict_gap["missingRequirement"])

    def test_rule_matrix_accepts_verified_canonical_static_capability_inputs_only(self):
        facts = [
            self.fact([self.observation("socket_count", 0)], "socket_count"),
            self.fact(
                [
                    self.observation(
                        "enchant_capability",
                        False,
                        parser_revision="season-rule-observer-v1",
                        source_scope="slot_rule",
                    )
                ],
                "enchant_capability",
            ),
            self.fact([], "embellishment_capability"),
        ]

        capabilities = gear_rule_matrix.canonical_static_capabilities(facts)

        self.assertEqual(
            capabilities,
            {"canEnchant": False, "socketCount": 0},
        )
        self.assertNotIn("canEmbellish", capabilities)

    def test_rule_matrix_rejects_malformed_verified_static_capability_values(self):
        capabilities = gear_rule_matrix.canonical_static_capabilities(
            [
                {
                    "factKey": "gear-fact:sha256:malformed",
                    "factType": "socket_count",
                    "status": "verified",
                    "value": False,
                },
                {
                    "factKey": "gear-fact:sha256:malformed-enchant",
                    "factType": "enchant_capability",
                    "status": "verified",
                    "value": 1,
                },
            ]
        )

        self.assertEqual(capabilities, {})


if __name__ == "__main__":
    unittest.main()

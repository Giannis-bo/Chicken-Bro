import copy
import json
import unittest

from server import gear_evidence_registry, gear_fact_compiler, gear_rule_matrix


SEASON_REVISION = "midnight-season-1"
SUBJECT_KEY = "item:250033/variant:void_upgrade-298"


class GearFactCompilerTest(unittest.TestCase):
    def observation(
        self,
        fact_type,
        value,
        *,
        artifact_id=None,
        parser_revision="simc-item-probe-observer-v1",
        source_scope="exact_variant",
        subject_key=SUBJECT_KEY,
    ):
        return gear_evidence_registry.build_evidence_observation(
            artifact_id=artifact_id
            or f"gear-artifact:sha256:{fact_type.replace('_', ''):0<64}",
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
    ):
        facts = gear_fact_compiler.compile_subject_facts(
            season_revision=SEASON_REVISION,
            subject_key=subject_key,
            observations=observations,
            fact_types=[fact_type],
            policies=policies,
        )
        self.assertEqual(len(facts), 1)
        return facts[0]

    def test_every_first_stage_policy_declares_all_decision_dimensions(self):
        expected_types = {
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
            "variant_track": {"itemLevel": 289, "track": "void_upgrade"},
            "static_stats": {"haste": 812, "stamina": 1218},
            "socket_count": 1,
            "enchant_capability": False,
            "embellishment_capability": True,
            "enhancement_option": {
                "effect": {"haste": 147},
                "optionId": "gem:240001",
                "optionType": "gem",
            },
            "allowed_enhancement_options": ["gem:240001", "gem:240002"],
            "item_set_membership": "set:42",
        }
        parser_revisions = {
            "item_identity": "battle-net-item-observer-v1",
            "slot_compatibility": "battle-net-item-observer-v1",
            "enchant_capability": "season-rule-observer-v1",
            "embellishment_capability": "battle-net-item-observer-v1",
            "allowed_enhancement_options": "season-rule-observer-v1",
            "item_set_membership": "battle-net-item-observer-v1",
        }
        source_scopes = {
            "enchant_capability": "slot_rule",
            "allowed_enhancement_options": "slot_rule",
        }

        for fact_type, expected in fixtures.items():
            with self.subTest(fact_type=fact_type):
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
                        )
                    ],
                    fact_type,
                )
                self.assertEqual(fact["status"], "verified")
                self.assertEqual(fact["value"], expected)
                self.assertEqual(fact["problemCode"], "")

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
            subjects=[SUBJECT_KEY],
            fact_types=["socket_count", "item_identity"],
        )
        replay = gear_fact_compiler.compile_facts(
            season_revision=SEASON_REVISION,
            observations=list(reversed(observations)),
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

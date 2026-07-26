import unittest

from server import gear_evidence_registry


SUBJECT_KEY = "item:250033/variant:void_upgrade-298"
SEASON_REVISION = "midnight-season-1"
FACT_TYPE = "socket_count"


class GearEvidenceRegistryTest(unittest.TestCase):
    def artifact(self, **overrides):
        args = {
            "source_type": "simc_item_probe",
            "source_identity": "simc:item:250033:void_upgrade-298",
            "source_revision": "simc-main-abcdef",
            "season_revision": SEASON_REVISION,
            "captured_at": "2026-07-26T00:00:00Z",
            "payload": {"bonusIds": [298], "itemId": 250033, "sockets": 1},
        }
        args.update(overrides)
        return gear_evidence_registry.build_evidence_artifact(**args)

    def observation(self, **overrides):
        artifact = self.artifact()
        args = {
            "artifact_id": artifact["artifactId"],
            "subject_key": SUBJECT_KEY,
            "fact_type": FACT_TYPE,
            "observed_value": 1,
            "parser_revision": "gear-socket-observer-v1",
            "source_scope": "exact_variant",
            "status": "accepted",
        }
        args.update(overrides)
        return gear_evidence_registry.build_evidence_observation(**args)

    def fact(self, **overrides):
        observation = self.observation()
        args = {
            "season_revision": SEASON_REVISION,
            "subject_key": SUBJECT_KEY,
            "fact_type": FACT_TYPE,
            "value": 1,
            "status": "verified",
            "observation_refs": [observation["observationId"]],
            "compiler_rule_revision": "gear-capability-matrix-v3",
            "impact_scope": "socket_only",
            "problem_code": "",
        }
        args.update(overrides)
        return gear_evidence_registry.build_canonical_fact(**args)

    def test_fact_key_binds_only_season_subject_and_fact_type(self):
        baseline = self.fact()
        changed_value_and_provenance = self.fact(
            value=0,
            observation_refs=["gear-observation:sha256:other"],
            compiler_rule_revision="gear-capability-matrix-v4",
        )

        self.assertEqual(
            baseline["factKey"],
            gear_evidence_registry.canonical_fact_key(
                SEASON_REVISION, SUBJECT_KEY, FACT_TYPE
            ),
        )
        self.assertEqual(baseline["factKey"], changed_value_and_provenance["factKey"])

    def test_fact_value_hash_changes_when_value_or_status_changes(self):
        baseline = self.fact()

        self.assertNotEqual(baseline["factValueHash"], self.fact(value=0)["factValueHash"])
        self.assertNotEqual(
            baseline["factValueHash"],
            self.fact(status="unresolved_missing", value=None)["factValueHash"],
        )

    def test_provenance_hash_depends_only_on_selected_observations_and_policy_revision(self):
        baseline = self.fact()

        self.assertEqual(
            baseline["provenanceHash"],
            self.fact(value=0, status="verified")["provenanceHash"],
        )
        self.assertNotEqual(
            baseline["provenanceHash"],
            self.fact(observation_refs=["gear-observation:sha256:other"])["provenanceHash"],
        )
        self.assertNotEqual(
            baseline["provenanceHash"],
            self.fact(compiler_rule_revision="gear-capability-matrix-v4")["provenanceHash"],
        )

    def test_verified_zero_and_false_are_verified_facts(self):
        zero = self.fact(value=0)
        false = self.fact(fact_type="enchant_capability", value=False)

        self.assertEqual(zero["status"], "verified")
        self.assertEqual(zero["value"], 0)
        self.assertEqual(false["status"], "verified")
        self.assertIs(false["value"], False)

    def test_unresolved_facts_reject_trusted_default_values(self):
        for status in ("unresolved_missing", "unresolved_conflict"):
            with self.subTest(status=status):
                with self.assertRaises(ValueError):
                    self.fact(status=status, value=0)
                with self.assertRaises(ValueError):
                    self.fact(status=status, value=False)
                unresolved = self.fact(status=status, value=None)
                self.assertIsNone(unresolved["value"])

    def test_artifact_identity_is_idempotent_for_identity_revision_season_and_payload(self):
        first = self.artifact()
        repeated = self.artifact(
            payload={"sockets": 1, "itemId": 250033, "bonusIds": [298]},
            captured_at="2026-07-26T01:00:00Z",
        )

        self.assertEqual(first["artifactId"], repeated["artifactId"])
        self.assertEqual(first["payloadHash"], repeated["payloadHash"])
        self.assertEqual(first, self.artifact())
        self.assertNotEqual(
            first["artifactId"],
            self.artifact(season_revision="midnight-season-2")["artifactId"],
        )

    def test_artifact_rejects_secret_shaped_payload_keys_recursively(self):
        for payload in (
            {"accessToken": "secret"},
            {"nested": {"cookie": "session=abc"}},
            {"entries": [{"api_key": "secret"}]},
            ({"api_key": "secret"},),
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    self.artifact(payload=payload)


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest import mock

from server import (
    gear_evidence_observers,
    gear_evidence_registry,
    gear_socket_authority,
)


SEASON_REVISION = "midnight-season-1"
SUBJECT_KEY = "item:250033/variant:void_upgrade-298"


class GearEvidenceObserversTest(unittest.TestCase):
    def artifact(self, source_type, payload, **overrides):
        args = {
            "source_type": source_type,
            "source_identity": f"{source_type}:fixture",
            "source_revision": f"{source_type}-revision-1",
            "season_revision": SEASON_REVISION,
            "captured_at": "2026-07-26T00:00:00Z",
            "payload": payload,
        }
        args.update(overrides)
        return gear_evidence_registry.build_evidence_artifact(**args)

    def test_battle_net_artifact_replay_is_deterministic_and_revision_bound(self):
        artifact = self.artifact(
            "battle_net_item",
            {
                "allowedSlots": ["head"],
                "canEmbellish": False,
                "canEnchant": True,
                "itemId": 250033,
                "setId": 42,
                "sockets": [],
                "staticStats": {"intellect": 100},
            },
        )

        first = gear_evidence_observers.observe_battle_net_item(
            artifact, parser_revision="battle-net-item-observer-v1"
        )
        replayed = gear_evidence_observers.observe_battle_net_item(
            artifact, parser_revision="battle-net-item-observer-v1"
        )
        revised = gear_evidence_observers.observe_battle_net_item(
            artifact, parser_revision="battle-net-item-observer-v2"
        )

        self.assertEqual(first, replayed)
        self.assertEqual(first["status"], "accepted")
        self.assertEqual(first["diagnostics"], [])
        by_type = {
            observation["factType"]: observation
            for observation in first["observations"]
        }
        self.assertEqual(by_type["item_identity"]["observedValue"]["itemId"], "250033")
        self.assertEqual(by_type["socket_count"]["observedValue"], 0)
        self.assertIs(by_type["embellishment_capability"]["observedValue"], False)
        self.assertNotEqual(
            first["observations"][0]["observationId"],
            revised["observations"][0]["observationId"],
        )

    def test_simc_exact_variant_probe_observes_known_socket_capacity(self):
        artifact = self.artifact(
            "simc_item_probe",
            {
                "bonusIds": [298],
                "itemId": 250033,
                "socketCount": 1,
                "staticStats": {"haste": 812, "stamina": 1218},
                "variantKey": "void_upgrade-298",
            },
        )

        result = gear_evidence_observers.observe_simc_item_probe(artifact)

        self.assertEqual(result["status"], "accepted")
        socket = next(
            observation
            for observation in result["observations"]
            if observation["factType"] == "socket_count"
        )
        self.assertEqual(socket["subjectKey"], SUBJECT_KEY)
        self.assertEqual(socket["sourceScope"], "exact_variant")
        self.assertEqual(socket["observedValue"], 1)

    def test_season_rule_artifact_emits_only_declared_rule_observations(self):
        artifact = self.artifact(
            "season_rule",
            {
                "rules": [
                    {
                        "factType": "slot_compatibility",
                        "sourceScope": "slot_rule",
                        "subjectKey": "slot:head",
                        "value": ["head"],
                    },
                    {
                        "factType": "enchant_capability",
                        "sourceScope": "slot_rule",
                        "subjectKey": "slot:head",
                        "value": False,
                    },
                ]
            },
        )

        result = gear_evidence_observers.observe_season_rule(artifact)

        self.assertEqual(result["status"], "accepted")
        self.assertEqual(
            [observation["factType"] for observation in result["observations"]],
            ["enchant_capability", "slot_compatibility"],
        )
        self.assertIs(result["observations"][0]["observedValue"], False)

    def test_simc_bonus_probe_replays_as_a_scoped_observation(self):
        artifact = self.artifact(
            "simc_bonus_probe",
            {
                "bonusId": 298,
                "factType": "socket_count",
                "socketCount": 1,
                "subjectKey": SUBJECT_KEY,
            },
        )

        result = gear_evidence_observers.observe_simc_bonus_probe(artifact)

        self.assertEqual(result["status"], "accepted")
        self.assertEqual(len(result["observations"]), 1)
        self.assertEqual(result["observations"][0]["observedValue"], 1)
        self.assertEqual(result["observations"][0]["sourceScope"], "exact_variant")

    def test_malformed_artifact_returns_diagnostic_without_default_observation(self):
        artifact = self.artifact(
            "battle_net_item",
            {"hasSocket": False, "name": "Missing structured identity"},
        )

        result = gear_evidence_observers.observe_battle_net_item(artifact)

        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["observations"], [])
        self.assertEqual(
            result["diagnostics"][0]["code"], "parser_unhandled_shape"
        )
        self.assertEqual(result["diagnostics"][0]["path"], "payload.itemId")

    def test_malformed_optional_socket_field_is_diagnostic_not_zero(self):
        artifact = self.artifact(
            "battle_net_item",
            {"itemId": 250033, "socketCount": "unknown"},
        )

        result = gear_evidence_observers.observe_battle_net_item(artifact)

        self.assertEqual(result["status"], "accepted")
        self.assertEqual(
            [row["factType"] for row in result["observations"]],
            ["item_identity"],
        )
        self.assertEqual(
            result["diagnostics"][0]["code"], "parser_unhandled_shape"
        )
        self.assertEqual(
            result["diagnostics"][0]["path"], "payload.socketCount"
        )

    def test_observers_do_not_read_clock_or_network(self):
        artifact = self.artifact(
            "simc_item_probe",
            {
                "itemId": 250033,
                "socketCount": 1,
                "variantKey": "void_upgrade-298",
            },
        )

        with mock.patch("time.time", side_effect=AssertionError("clock read")), mock.patch(
            "urllib.request.urlopen", side_effect=AssertionError("network read")
        ):
            result = gear_evidence_observers.observe_artifact(artifact)

        self.assertEqual(result["status"], "accepted")

    def test_legacy_socket_bridge_emits_compiler_inputs_without_consumer_payload(self):
        inputs = gear_socket_authority.derive_variant_socket_observation_inputs(
            {"itemId": "250033", "slot": "head", "payload": {}},
            {
                "itemId": "250033",
                "variantKey": "void_upgrade-298",
                "simcOptions": {"bonus_id": "298"},
            },
            season_revision=SEASON_REVISION,
            socket_bonus_minimums={
                "298": {
                    "minimumTotal": 1,
                    "sourceRevision": "simc-main-abcdef",
                }
            },
        )

        self.assertEqual(
            inputs,
            [
                {
                    "factType": "socket_count",
                    "observedValue": 1,
                    "source": "simc_bonus",
                    "sourceType": "simc_bonus_probe",
                    "sourceRevision": "simc-main-abcdef",
                    "sourceScope": "exact_variant",
                    "subjectKey": SUBJECT_KEY,
                }
            ],
        )
        self.assertNotIn("minimumTotal", inputs[0])
        self.assertNotIn("authorityRevision", inputs[0])


if __name__ == "__main__":
    unittest.main()

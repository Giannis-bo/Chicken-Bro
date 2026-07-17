#!/usr/bin/env python3
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from server import gear_attribute_api


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def valid_intent():
    return {
        "schemaRevision": "selection-intent-v1",
        "authoredAgainst": {
            "seasonRevision": "season-17-active",
            "gearCatalogRevision": "gear-r17",
        },
        "eligibilityContext": {
            "classKey": "mage",
            "specKey": "frost",
            "level": 90,
        },
        "slots": {
            "head": {
                "itemId": "250060",
                "variantKey": "variant-head-289",
                "gemOptionIds": [],
                "enchantOptionId": "",
                "embellishmentOptionId": "",
                "craftedOptionId": "",
                "catalystOptionId": "",
            }
        },
    }


def verified_rulebook():
    rulebook = json.loads((FIXTURE_DIR / "gear-attribute-rulebook-v1.json").read_text(encoding="utf-8"))
    rulebook["contexts"][0]["status"] = "verified"
    rulebook["contexts"][0]["sourceRefs"] = ["test:verified-source"]
    rulebook["contexts"][0]["goldenSampleIds"] = ["test:mage-frost-human"]
    return rulebook


def resolved_envelope(request_id):
    calculator_case = json.loads(
        (FIXTURE_DIR / "gear-attribute-calculator-cases-v1.json").read_text(encoding="utf-8")
    )["cases"][0]
    return {
        "contractRevision": "gear-result-envelope-v1",
        "requestId": request_id,
        "status": "resolved",
        "releaseContext": {"gearCatalogRevision": "gear-r17"},
        "data": {
            "resolvedGearSignature": "sha256:resolved-gear",
            "staticAttributes": calculator_case["staticAttributes"],
            "stableEffects": [],
        },
        "problems": [],
    }


class GearAttributeApiTest(unittest.TestCase):
    def test_audit_calculates_only_from_resolved_static_facts_without_simc(self):
        calls = []

        def fake_resolve(selection_intent, *, store, simc_runtime_revision, request_id):
            calls.append((selection_intent, store, simc_runtime_revision, request_id))
            return 200, resolved_envelope(request_id)

        request = {
            "selectionIntent": valid_intent(),
            "characterContext": {
                "schemaRevision": "gear-attribute-character-v1",
                "raceKey": "human",
            },
        }
        with patch.object(gear_attribute_api, "resolve_selection_intent", side_effect=fake_resolve), patch.object(
            gear_attribute_api,
            "run_websim_stat_simcraft",
            side_effect=AssertionError("attribute audit must not call SimC"),
            create=True,
        ):
            status, envelope = gear_attribute_api.calculate_attributes_for_selection(
                request,
                store=object(),
                simc_runtime_revision="ignored-by-attribute-engine",
                request_id="attribute-test",
                rulebook=verified_rulebook(),
            )

        self.assertEqual(status, 200)
        self.assertEqual(envelope["status"], "resolved")
        self.assertEqual(envelope["data"]["resolvedGearSignature"], "sha256:resolved-gear")
        self.assertEqual(envelope["data"]["attributeCalculation"]["status"], "calculated")
        self.assertEqual(envelope["data"]["attributeCalculation"]["primary"]["rawValue"], 1500)
        self.assertEqual(len(calls), 1)

    def test_client_static_values_and_missing_character_context_are_rejected_before_resolver(self):
        forged_intent = valid_intent()
        forged_intent["staticAttributes"] = {"intellect": 999999}
        requests = (
            {"selectionIntent": forged_intent, "characterContext": {"schemaRevision": "gear-attribute-character-v1", "raceKey": "human"}},
            {"selectionIntent": valid_intent()},
        )
        with patch.object(gear_attribute_api, "resolve_selection_intent") as resolve:
            for request in requests:
                with self.subTest(request=request):
                    status, envelope = gear_attribute_api.calculate_attributes_for_selection(
                        request,
                        store=object(),
                        simc_runtime_revision="simc-v1",
                        request_id="attribute-invalid",
                        rulebook=verified_rulebook(),
                    )
                    self.assertEqual(status, 400)
                    self.assertEqual(envelope["status"], "blocked")
                    self.assertNotIn("staticAttributes", envelope["data"])
            resolve.assert_not_called()

    def test_unverified_rules_return_bounded_audit_without_static_final_panel(self):
        request = {
            "selectionIntent": valid_intent(),
            "characterContext": {
                "schemaRevision": "gear-attribute-character-v1",
                "raceKey": "human",
            },
        }
        with patch.object(
            gear_attribute_api,
            "resolve_selection_intent",
            side_effect=lambda _intent, **kwargs: (200, resolved_envelope(kwargs["request_id"])),
        ):
            status, envelope = gear_attribute_api.calculate_attributes_for_selection(
                request,
                store=object(),
                simc_runtime_revision="simc-v1",
                request_id="attribute-unverified",
                rulebook=json.loads((FIXTURE_DIR / "gear-attribute-rulebook-v1.json").read_text(encoding="utf-8")),
            )

        calculation = envelope["data"]["attributeCalculation"]
        self.assertEqual(status, 200)
        self.assertEqual(calculation["status"], "rule_unavailable")
        self.assertIsNone(calculation["primary"])
        self.assertEqual(calculation["secondary"], [])

    def test_malformed_resolver_stable_effect_facts_fail_closed(self):
        request = {
            "selectionIntent": valid_intent(),
            "characterContext": {
                "schemaRevision": "gear-attribute-character-v1",
                "raceKey": "human",
            },
        }
        resolved = resolved_envelope("attribute-stable-effects")
        resolved["data"]["stableEffects"] = [{"effectId": "fixture:forged", "value": 999999}]
        with patch.object(
            gear_attribute_api,
            "resolve_selection_intent",
            return_value=(200, resolved),
        ):
            status, envelope = gear_attribute_api.calculate_attributes_for_selection(
                request,
                store=object(),
                simc_runtime_revision="simc-v1",
                request_id="attribute-stable-effects",
                rulebook=verified_rulebook(),
            )

        calculation = envelope["data"]["attributeCalculation"]
        self.assertEqual(status, 200)
        self.assertEqual(calculation["status"], "rule_unavailable")
        self.assertIsNone(calculation["primary"])
        self.assertEqual(calculation["problems"][0]["code"], "INVALID_STABLE_EFFECTS")


if __name__ == "__main__":
    unittest.main()

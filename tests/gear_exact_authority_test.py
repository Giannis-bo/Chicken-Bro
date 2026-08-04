import copy
import unittest

from server.gear_exact_authority import build_exact_authority_envelope


EXACT = {"exactItemInstanceKey": "exact-item-instance:sha256:" + ("1" * 64), "itemId": "1001"}
STATIC = {"stats": {"haste_rating": 241}}
SERIALIZER = {"id": "1001", "ilevel": "266"}
PROGRESSION = {"gearRuleRevision": "gear-rule-matrix-v1", "progressionState": {"trackKey": "hero", "rank": 3}}
EFFECT = {"status": "verified", "simcRuntimeRevision": "simc-2026.08.04", "supportRecordKeys": ["simc-item-effect-record:sha256:" + ("2" * 64)]}


class GearExactAuthorityTest(unittest.TestCase):
    def test_ready_envelope_is_strict_content_addressed_and_binds_all_authority_inputs(self):
        first = build_exact_authority_envelope(exact_item=EXACT, static_facts=STATIC, serializer_input=SERIALIZER, progression_binding=PROGRESSION, effect_support=EFFECT, resolver_revision="resolver-v2")
        second = build_exact_authority_envelope(exact_item=copy.deepcopy(EXACT), static_facts=copy.deepcopy(STATIC), serializer_input=copy.deepcopy(SERIALIZER), progression_binding=copy.deepcopy(PROGRESSION), effect_support=copy.deepcopy(EFFECT), resolver_revision="resolver-v2")
        changed = build_exact_authority_envelope(exact_item=EXACT, static_facts={"stats": {"haste_rating": 242}}, serializer_input=SERIALIZER, progression_binding=PROGRESSION, effect_support=EFFECT, resolver_revision="resolver-v2")
        self.assertEqual(first["status"], "ready")
        self.assertEqual(first["exactAuthorityKey"], second["exactAuthorityKey"])
        self.assertNotEqual(first["exactAuthorityKey"], changed["exactAuthorityKey"])
        self.assertRegex(first["exactAuthorityKey"], r"^exact-authority:sha256:[0-9a-f]{64}$")
        self.assertNotIn("owner", first["canonicalPayload"])
        self.assertNotIn("catalogRevision", first["canonicalPayload"])

    def test_unknown_or_unsupported_effect_support_cannot_make_ready_envelope(self):
        for status in ("unknown", "unsupported"):
            result = build_exact_authority_envelope(exact_item=EXACT, static_facts=STATIC, serializer_input=SERIALIZER, progression_binding=PROGRESSION, effect_support={**EFFECT, "status": status}, resolver_revision="resolver-v2")
            self.assertEqual(result["status"], "blocked")

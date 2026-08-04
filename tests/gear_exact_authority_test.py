import copy
import hashlib
import unittest

from server.gear_exact_authority import build_exact_authority_envelope
from server.gear_exact_item_instance import build_exact_item_identity
from server.simc_item_effect_support import (
    resolve_exact_item_effect_support,
    seal_effect_record,
)


RUNTIME = "simc-2026.08.04"
EXACT = build_exact_item_identity({}, {"itemId": "1001", "declaredItemLevel": 266, "bonusIds": ["13334"], "context": "heroic", "gemIds": [], "gemBonusIds": [], "gemItemLevels": [], "enchantId": "", "craftedStats": [], "embellishmentIds": [], "redirectedBaseStats": []})
STATIC = {"schemaRevision": "exact-static-facts-v1", "exactItemInstanceKey": EXACT["exactItemInstanceKey"], "facts": {"haste_rating": 241}}
SERIALIZER = EXACT["serializerInput"]
PROGRESSION_PAYLOAD = {"schemaRevision": "exact-progression-binding-v1", "exactItemInstanceKey": EXACT["exactItemInstanceKey"], "gearRuleRevision": "gear-rule-matrix-v1", "progressionState": {"kind": "upgrade_track", "trackKey": "hero", "rank": 3, "maxRank": 6}}
PROGRESSION = {**PROGRESSION_PAYLOAD, "progressionBindingKey": "exact-progression:sha256:" + hashlib.sha256(__import__("json").dumps(PROGRESSION_PAYLOAD, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
EFFECT = resolve_exact_item_effect_support(EXACT, runtime_revision=RUNTIME, support_records=[seal_effect_record({"schemaRevision": "simc-item-effect-authority-v1", "subjectKind": "item", "subjectKey": "1001", "subjectVariantSignature": EXACT["exactVariantSignature"], "hasDynamicEffect": False, "simcRuntimeRevision": RUNTIME, "verifiedAt": "2026-08-04T00:00:00Z"})])


class GearExactAuthorityTest(unittest.TestCase):
    def test_ready_envelope_is_strict_content_addressed_and_binds_all_authority_inputs(self):
        first = build_exact_authority_envelope(exact_item=EXACT, static_facts=STATIC, serializer_input=SERIALIZER, progression_binding=PROGRESSION, effect_support=EFFECT, resolver_revision="resolver-v2")
        second = build_exact_authority_envelope(exact_item=copy.deepcopy(EXACT), static_facts=copy.deepcopy(STATIC), serializer_input=copy.deepcopy(SERIALIZER), progression_binding=copy.deepcopy(PROGRESSION), effect_support=copy.deepcopy(EFFECT), resolver_revision="resolver-v2")
        changed = build_exact_authority_envelope(exact_item=EXACT, static_facts={**STATIC, "facts": {"haste_rating": 242}}, serializer_input=SERIALIZER, progression_binding=PROGRESSION, effect_support=EFFECT, resolver_revision="resolver-v2")
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

    def test_envelope_rejects_missing_static_serializer_progression_and_effect_record_bindings(self):
        for fields in (
            {"static_facts": {}},
            {"serializer_input": {}},
            {"progression_binding": {}},
            {"effect_support": {"status": "verified", "simcRuntimeRevision": "new", "supportRecordKeys": []}},
        ):
            result = build_exact_authority_envelope(
                **{
                    "exact_item": EXACT, "static_facts": STATIC,
                    "serializer_input": SERIALIZER,
                    "progression_binding": PROGRESSION,
                    "effect_support": EFFECT,
                    "resolver_revision": "resolver-v2", **fields,
                },
            )
            self.assertEqual(result["status"], "blocked")

    def test_envelope_validates_exact_and_effect_record_key_formats(self):
        for exact, effect in (
            ({**EXACT, "exactItemInstanceKey": "exact-item-instance:sha256:not-a-hash"}, EFFECT),
            (EXACT, {**EFFECT, "supportRecordKeys": ["x"]}),
        ):
            result = build_exact_authority_envelope(exact_item=exact, static_facts=STATIC, serializer_input=SERIALIZER, progression_binding=PROGRESSION, effect_support=effect, resolver_revision="resolver-v2")
            self.assertEqual(result["status"], "blocked")

    def test_envelope_recursively_rejects_owner_catalog_observation_and_provenance_aliases(self):
        for key in ("ownerKeyHash", "originCatalogRevision", "observation_count", "sourceUrl"):
            result = build_exact_authority_envelope(exact_item={**EXACT, "nested": {key: "forbidden"}}, static_facts=STATIC, serializer_input=SERIALIZER, progression_binding=PROGRESSION, effect_support=EFFECT, resolver_revision="resolver-v2")
            self.assertEqual(result["status"], "blocked", key)

    def test_envelope_rejects_schema_less_or_cross_bound_authority_inputs(self):
        for fields in (
            {"exact_item": {**EXACT, "schemaRevision": "missing"}},
            {"serializer_input": {"id": "9999", "ilevel": "999"}},
            {"progression_binding": {"gearRuleRevision": "arbitrary", "progressionState": {"rank": 99}}},
            {"effect_support": {**EFFECT, "schemaRevision": "missing"}},
        ):
            result = build_exact_authority_envelope(**{"exact_item": EXACT, "static_facts": STATIC, "serializer_input": SERIALIZER, "progression_binding": PROGRESSION, "effect_support": EFFECT, "resolver_revision": "resolver-v2", **fields})
            self.assertEqual(result["status"], "blocked")

    def test_envelope_rejects_forged_exact_hash_and_non_json_values(self):
        for exact, facts in (({**EXACT, "exactItemInstanceKey": "exact-item-instance:sha256:" + ("f" * 64)}, STATIC), (EXACT, {**STATIC, "facts": {"haste": object()}})):
            result = build_exact_authority_envelope(exact_item=exact, static_facts=facts, serializer_input=SERIALIZER, progression_binding=PROGRESSION, effect_support=EFFECT, resolver_revision="resolver-v2")
            self.assertEqual(result["status"], "blocked")

    def test_envelope_rejects_non_builder_exact_derived_fields_and_nested_schemas(self):
        cases = (
            {"exact_item": {**EXACT, "serializerInput": {"id": "9999", "ilevel": "999"}}},
            {"exact_item": {**EXACT, "enhancementSelectionKey": "enhancement-selection:sha256:" + ("f" * 64)}},
            {"exact_item": {**EXACT, "problemCodes": ["BAD"], "problems": [{"code": "BAD"}]}},
            {"exact_item": {**EXACT, "enhancementSelection": {**EXACT["enhancementSelection"], "schemaRevision": "unknown"}}},
            {"static_facts": {**STATIC, "facts": {"haste_rating": "241"}}},
            {"progression_binding": {**PROGRESSION, "progressionState": {"evil": True}}},
        )
        for fields in cases:
            result = build_exact_authority_envelope(**{"exact_item": EXACT, "static_facts": STATIC, "serializer_input": SERIALIZER, "progression_binding": PROGRESSION, "effect_support": EFFECT, "resolver_revision": "resolver-v2", **fields})
            self.assertEqual(result["status"], "blocked")

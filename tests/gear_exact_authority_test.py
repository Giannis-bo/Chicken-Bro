import inspect
import json
import unittest
from unittest.mock import patch

import server.gear_exact_authority as exact_authority_module
import server.gear_exact_item_instance as exact_item_module
from server.gear_exact_authority import (
    _validate_exact_progression_payload,
    reload_exact_authority_envelope,
    reload_exact_progression,
    seal_exact_progression,
)
from server.gear_canonical_kernel import (
    CanonicalValueError,
    SealedCanonicalDocument,
    seal_canonical_document,
    verify_sealed_document,
)
from server.gear_exact_item_instance import seal_exact_item
from server.simc_item_effect_support import (
    derive_exact_effect_subjects,
    resolve_exact_effect_support,
    seal_effect_record,
)


RUNTIME = "simc-2026.08.04"
SEASON = "season-17-f131dd36ddf1"
RULE = "gear-rule-matrix-v1"
def sealed_exact(**overrides):
    payload = {
        "itemId": "1001", "declaredItemLevel": 266,
        "bonusIds": ["13334"], "context": "heroic",
        "gemIds": [], "gemBonusIds": [], "gemItemLevels": [],
        "enchantId": "", "craftedStats": [], "embellishmentIds": [],
        "redirectedBaseStats": [],
    }
    payload.update(overrides)
    return seal_exact_item(payload).document


def sealed_effect_aggregate(exact, *, status="verified", runtime=RUNTIME):
    records = []
    for index, subject in enumerate(derive_exact_effect_subjects(exact)):
        payload = {
            "schemaRevision": "simc-item-effect-record-v1",
            "status": "verified",
            "subjectKind": subject.kind,
            "subjectKey": subject.key,
            "subjectVariantSignature": subject.variant_signature,
            "hasDynamicEffect": False,
            "simcRuntimeRevision": runtime,
            "verifiedAt": "2026-08-04T00:00:00Z",
        }
        if status == "unsupported" and index == 0:
            payload.update({
                "status": "unsupported",
                "hasDynamicEffect": True,
                "unsupportedReason": "NOT_IMPLEMENTED",
            })
        sealed = seal_effect_record(payload, runtime_revision=runtime)
        if sealed.status != "verified":
            raise AssertionError(sealed.issues)
        records.append(sealed.document)
    outcome = resolve_exact_effect_support(
        exact,
        runtime_revision=runtime,
        records=records,
    )
    if outcome.status != status:
        raise AssertionError((outcome.status, outcome.issues))
    return outcome.document


def sealed_task4_inputs(exact=None, *, facts=None):
    exact = exact or sealed_exact()
    static = exact_item_module.seal_exact_static_facts(
        exact,
        {"haste_rating": 241} if facts is None else facts,
    )
    progression = seal_exact_progression(
        exact,
        season_revision=SEASON,
        gear_rule_revision=RULE,
        slot="head",
        has_crafted_source=False,
    )
    if static.status != "verified" or progression.status != "verified":
        raise AssertionError((static.issues, progression.issues))
    return exact, static.document, progression.document, sealed_effect_aggregate(exact)


def forged_document(document, *, payload=None, kind=None, schema=None, prefix=None):
    return seal_canonical_document(
        document_kind=kind or document.document_kind,
        schema_revision=schema or document.schema_revision,
        payload=json.loads(document.canonical_bytes) if payload is None else payload,
        key_prefix=prefix or {
            "exact_item": "exact-item-instance:sha256:",
            "exact_static_facts": "exact-static-facts:sha256:",
            "exact_progression": "exact-progression:sha256:",
            "effect_aggregate": "simc-item-effect-support:sha256:",
        }[document.document_kind],
    )


def tampered_document(document, *, canonical_bytes=None, content_key=None):
    tampered = object.__new__(SealedCanonicalDocument)
    object.__setattr__(tampered, "document_kind", document.document_kind)
    object.__setattr__(tampered, "schema_revision", document.schema_revision)
    object.__setattr__(
        tampered,
        "canonical_bytes",
        canonical_bytes if canonical_bytes is not None else document.canonical_bytes,
    )
    object.__setattr__(
        tampered,
        "content_key",
        content_key if content_key is not None else document.content_key,
    )
    return tampered


def verify_progression(document, exact):
    return verify_sealed_document(
        document,
        document_kind="exact_progression",
        schema_revision="exact-progression-binding-v1",
        key_prefix="exact-progression:sha256:",
        payload_validator=lambda payload: _validate_exact_progression_payload(
            payload, exact=exact,
        ),
    )


class GearExactAuthorityTest(unittest.TestCase):
    def test_typed_reload_progression_and_envelope_replay_all_authority_bindings(self):
        exact, static, progression, effect = sealed_task4_inputs()
        envelope = exact_authority_module.seal_exact_authority_envelope(
            exact=exact,
            static_facts=static,
            progression=progression,
            effect_support=effect,
            resolver_revision="resolver-v2",
        ).document

        self.assertEqual(
            reload_exact_progression(
                progression.canonical_bytes, progression.content_key, exact=exact,
            ),
            progression,
        )
        self.assertEqual(
            reload_exact_authority_envelope(
                envelope.canonical_bytes,
                envelope.content_key,
                exact=exact,
                static_facts=static,
                progression=progression,
                effect_support=effect,
                resolver_revision="resolver-v2",
            ),
            envelope,
        )
        with self.assertRaises(CanonicalValueError):
            reload_exact_authority_envelope(
                envelope.canonical_bytes,
                envelope.content_key,
                exact=exact,
                static_facts=static,
                progression=progression,
                effect_support=effect,
                resolver_revision="resolver-v3",
            )

    def test_progression_requires_canonical_slot_and_production_track_authority(self):
        exact = sealed_exact()
        ready = seal_exact_progression(
            exact,
            season_revision=SEASON,
            gear_rule_revision=RULE,
            slot="head",
            has_crafted_source=False,
        )
        self.assertEqual(ready.status, "verified")
        self.assertEqual(ready.document.document_kind, "exact_progression")
        self.assertEqual(ready.document.schema_revision, "exact-progression-binding-v1")
        self.assertRegex(
            ready.document.content_key,
            r"^exact-progression:sha256:[0-9a-f]{64}$",
        )
        self.assertTrue(verify_progression(ready.document, exact))
        for slot in ("bogus", "HEAD", "trinket_1", "mainhand"):
            with self.subTest(slot=slot):
                self.assertEqual(
                    seal_exact_progression(
                        exact,
                        season_revision=SEASON,
                        gear_rule_revision=RULE,
                        slot=slot,
                        has_crafted_source=False,
                    ).status,
                    "blocked",
                )
        self.assertEqual(
            seal_exact_progression(
                {"raw": "dict"},
                season_revision=SEASON,
                gear_rule_revision=RULE,
                slot="head",
                has_crafted_source=False,
            ).status,
            "blocked",
        )

    def test_progression_seals_the_full_canonical_track_authority_input(self):
        exact = sealed_exact()
        progression = seal_exact_progression(
            exact,
            season_revision=SEASON,
            gear_rule_revision=RULE,
            slot="head",
            has_crafted_source=False,
        ).document
        payload = json.loads(progression.canonical_bytes)
        self.assertEqual(
            payload["trackAuthorityInput"],
            {
                "seasonRevision": SEASON,
                "gearRuleRevision": RULE,
                "rowFamily": "exact_instance",
                "status": "verified",
                "itemId": "1001",
                "variantKey": exact.content_key,
                "itemLevel": 266,
                "bonusIds": ["13334"],
                "slot": "head",
                "hasCraftedSource": False,
            },
        )
        self.assertEqual(
            payload["progressionState"],
            {"kind": "upgrade_track", "trackKey": "hero", "rank": 3, "maxRank": 6},
        )

    def test_progression_reload_rejects_forged_owner_outputs_and_inputs(self):
        exact = sealed_exact()
        ready = seal_exact_progression(
            exact,
            season_revision=SEASON,
            gear_rule_revision=RULE,
            slot="head",
            has_crafted_source=False,
        ).document
        base = json.loads(ready.canonical_bytes)
        mutations = (
            {**base, "progressionState": {"kind": "upgrade_track", "trackKey": "hero", "rank": 6, "maxRank": 6}},
            {**base, "trackAuthorityRecordKey": "exact_myth_3", "progressionState": {"kind": "upgrade_track", "trackKey": "myth", "rank": 3, "maxRank": 6}},
            {**base, "trackAuthorityRecordKey": "exact_crafted_myth", "progressionState": {"kind": "crafted_quality", "trackKey": "myth", "qualityKey": "radiance_max"}},
            {**base, "trackAuthorityRecordKey": "exact_ascendant_13654", "progressionState": {"kind": "ascendant", "trackKey": "void_upgrade", "originKind": "upgrade_track"}},
            {**base, "trackAuthorityRecordKey": "arbitrary-record"},
            {
                **base,
                "gearRuleRevision": "arbitrary-rule",
                "trackAuthorityInput": {**base["trackAuthorityInput"], "gearRuleRevision": "arbitrary-rule"},
            },
            {
                **base,
                "trackAuthorityInput": {**base["trackAuthorityInput"], "callerRank": 6},
            },
        )
        for payload in mutations:
            with self.subTest(payload=payload):
                forged = seal_canonical_document(
                    document_kind="exact_progression",
                    schema_revision="exact-progression-binding-v1",
                    payload=payload,
                    key_prefix="exact-progression:sha256:",
                )
                self.assertFalse(verify_progression(forged, exact))

    def test_progression_reload_rejects_wrong_seals_tampering_and_cross_exact_reuse(self):
        exact = sealed_exact()
        ready = seal_exact_progression(
            exact,
            season_revision=SEASON,
            gear_rule_revision=RULE,
            slot="head",
            has_crafted_source=False,
        ).document
        payload = json.loads(ready.canonical_bytes)
        wrong_documents = (
            seal_canonical_document(
                document_kind="other", schema_revision=ready.schema_revision,
                payload=payload, key_prefix="exact-progression:sha256:",
            ),
            seal_canonical_document(
                document_kind="exact_progression", schema_revision="wrong-schema",
                payload=payload, key_prefix="exact-progression:sha256:",
            ),
            seal_canonical_document(
                document_kind="exact_progression", schema_revision=ready.schema_revision,
                payload=payload, key_prefix="attacker:sha256:",
            ),
        )
        for document in wrong_documents:
            with self.subTest(document=document):
                self.assertFalse(verify_progression(document, exact))

        tampered = object.__new__(SealedCanonicalDocument)
        object.__setattr__(tampered, "document_kind", ready.document_kind)
        object.__setattr__(tampered, "schema_revision", ready.schema_revision)
        object.__setattr__(tampered, "canonical_bytes", ready.canonical_bytes.replace(b'"rank":3', b'"rank":6'))
        object.__setattr__(tampered, "content_key", ready.content_key)
        self.assertFalse(verify_progression(tampered, exact))
        self.assertFalse(verify_progression(ready, sealed_exact(itemId="1002")))

    def test_progression_reload_rejects_python_equal_noncanonical_numbers(self):
        exact = sealed_exact()
        document = seal_exact_progression(
            exact,
            season_revision=SEASON,
            gear_rule_revision=RULE,
            slot="head",
            has_crafted_source=False,
        ).document
        payload = json.loads(document.canonical_bytes)
        forged = seal_canonical_document(
            document_kind="exact_progression",
            schema_revision="exact-progression-binding-v1",
            payload={
                **payload,
                "progressionState": {
                    **payload["progressionState"],
                    "rank": 3.0,
                },
            },
            key_prefix="exact-progression:sha256:",
        )
        self.assertFalse(verify_progression(forged, exact))

    def test_crafted_stats_require_complete_effect_records_before_verified_envelope(self):
        exact = sealed_exact(craftedStats=["crit"])
        subjects = derive_exact_effect_subjects(exact)
        self.assertEqual(
            [(subject.kind, subject.key) for subject in subjects],
            [("item", "1001"), ("crafted_effect", "crit")],
        )
        item_record = seal_effect_record(
            {
                "schemaRevision": "simc-item-effect-record-v1",
                "status": "verified",
                "subjectKind": subjects[0].kind,
                "subjectKey": subjects[0].key,
                "subjectVariantSignature": subjects[0].variant_signature,
                "hasDynamicEffect": False,
                "simcRuntimeRevision": RUNTIME,
                "verifiedAt": "2026-08-04T00:00:00Z",
            },
            runtime_revision=RUNTIME,
        ).document
        unknown = resolve_exact_effect_support(
            exact, runtime_revision=RUNTIME, records=[item_record],
        )
        self.assertEqual(unknown.status, "unknown")

        static = exact_item_module.seal_exact_static_facts(
            exact, {"haste_rating": 241},
        ).document
        progression = seal_exact_progression(
            exact,
            season_revision=SEASON,
            gear_rule_revision=RULE,
            slot="head",
            has_crafted_source=False,
        ).document
        effect = sealed_effect_aggregate(exact)
        ready = exact_authority_module.seal_exact_authority_envelope(
            exact=exact,
            static_facts=static,
            progression=progression,
            effect_support=effect,
            resolver_revision="resolver-v2",
        )
        self.assertEqual(ready.status, "verified")

    def test_duplicate_gem_effect_evidence_is_ready_only_when_every_position_verified(self):
        exact = sealed_exact(
            gemIds=["240892", "240892"],
            gemBonusIds=["1514", "1514"],
            gemItemLevels=[90, 90],
        )
        subjects = derive_exact_effect_subjects(exact)
        records = []
        for subject in subjects:
            sealed = seal_effect_record(
                {
                    "schemaRevision": "simc-item-effect-record-v1",
                    "status": "verified",
                    "subjectKind": subject.kind,
                    "subjectKey": subject.key,
                    "subjectVariantSignature": subject.variant_signature,
                    "hasDynamicEffect": False,
                    "simcRuntimeRevision": RUNTIME,
                    "verifiedAt": "2026-08-04T00:00:00Z",
                },
                runtime_revision=RUNTIME,
            )
            self.assertEqual(sealed.status, "verified")
            records.append(sealed.document)
        verified_effect = resolve_exact_effect_support(
            exact, runtime_revision=RUNTIME, records=records,
        )
        self.assertEqual(verified_effect.status, "verified")

        mixed_payload = {
            "schemaRevision": "simc-item-effect-record-v1",
            "status": "unsupported",
            "subjectKind": subjects[2].kind,
            "subjectKey": subjects[2].key,
            "subjectVariantSignature": subjects[2].variant_signature,
            "hasDynamicEffect": True,
            "simcRuntimeRevision": RUNTIME,
            "verifiedAt": "2026-08-04T01:00:00Z",
            "unsupportedReason": "NOT_IMPLEMENTED",
        }
        mixed_record = seal_effect_record(
            mixed_payload, runtime_revision=RUNTIME,
        )
        self.assertEqual(mixed_record.status, "verified")
        mixed_effect = resolve_exact_effect_support(
            exact,
            runtime_revision=RUNTIME,
            records=[records[0], records[1], mixed_record.document],
        )
        self.assertEqual(mixed_effect.status, "unsupported")

        static = exact_item_module.seal_exact_static_facts(
            exact, {"haste_rating": 241},
        ).document
        progression = seal_exact_progression(
            exact,
            season_revision=SEASON,
            gear_rule_revision=RULE,
            slot="head",
            has_crafted_source=False,
        ).document
        ready = exact_authority_module.seal_exact_authority_envelope(
            exact=exact,
            static_facts=static,
            progression=progression,
            effect_support=verified_effect.document,
            resolver_revision="resolver-v2",
        )
        blocked = exact_authority_module.seal_exact_authority_envelope(
            exact=exact,
            static_facts=static,
            progression=progression,
            effect_support=mixed_effect.document,
            resolver_revision="resolver-v2",
        )
        self.assertEqual(ready.status, "verified")
        self.assertEqual(blocked.status, "blocked")
        self.assertIsNone(blocked.document)
        self.assertEqual(blocked.issues[0].code, "EFFECT_SUPPORT_NOT_VERIFIED")


class SealedExactAuthorityEnvelopeTest(unittest.TestCase):
    def test_static_facts_require_reverified_exact_and_strict_numeric_mapping(self):
        exact = sealed_exact()
        ready = exact_item_module.seal_exact_static_facts(
            exact,
            {"haste_rating": 241, "crit_pct": 1.5},
        )
        self.assertEqual(ready.status, "verified")
        self.assertEqual(ready.document.document_kind, "exact_static_facts")
        self.assertEqual(
            ready.document.schema_revision,
            "exact-static-facts-v1",
        )
        self.assertRegex(
            ready.document.content_key,
            r"^exact-static-facts:sha256:[0-9a-f]{64}$",
        )
        self.assertEqual(
            json.loads(ready.document.canonical_bytes),
            {
                "schemaRevision": "exact-static-facts-v1",
                "exactItemInstanceKey": exact.content_key,
                "facts": {"haste_rating": 241, "crit_pct": 1.5},
            },
        )

        invalid_facts = (
            {},
            {1: 241},
            {1: 241, "1": 242},
            {" stat": 241},
            {"stat ": 241},
            {"stat\u0085x": 241},
            {"stat\u2028x": 241},
            {"x" * 257: 241},
            {"stat": True},
            {"stat": float("nan")},
            {"stat": float("inf")},
            {"stat": float("-inf")},
            {"stat": "241"},
            {"stat": [241]},
            {"stat": {"nested": 241}},
        )
        for facts in invalid_facts:
            with self.subTest(facts=facts):
                self.assertEqual(
                    exact_item_module.seal_exact_static_facts(exact, facts).status,
                    "blocked",
                )

        payload = json.loads(exact.canonical_bytes)
        invalid_exact_documents = (
            payload,
            forged_document(exact, kind="other"),
            forged_document(exact, schema="wrong-schema"),
            forged_document(exact, prefix="attacker:sha256:"),
            forged_document(exact, payload={**payload, "itemId": " 1001"}),
            tampered_document(
                exact,
                canonical_bytes=exact.canonical_bytes.replace(b'"1001"', b'"1002"'),
            ),
            tampered_document(
                exact,
                content_key="exact-item-instance:sha256:" + "f" * 64,
            ),
        )
        for invalid_exact in invalid_exact_documents:
            with self.subTest(invalid_exact=invalid_exact):
                self.assertEqual(
                    exact_item_module.seal_exact_static_facts(
                        invalid_exact,
                        {"haste_rating": 241},
                    ).status,
                    "blocked",
                )

    def test_static_facts_are_deterministic_and_bind_every_fact_and_exact_identity(self):
        exact = sealed_exact()
        same_a = exact_item_module.seal_exact_static_facts(
            exact, {"haste_rating": 241, "crit_rating": 180},
        ).document
        same_b = exact_item_module.seal_exact_static_facts(
            exact, {"crit_rating": 180, "haste_rating": 241},
        ).document
        changed_key = exact_item_module.seal_exact_static_facts(
            exact, {"haste": 241, "crit_rating": 180},
        ).document
        changed_value = exact_item_module.seal_exact_static_facts(
            exact, {"haste_rating": 242, "crit_rating": 180},
        ).document
        changed_exact = exact_item_module.seal_exact_static_facts(
            sealed_exact(itemId="1002"),
            {"haste_rating": 241, "crit_rating": 180},
        ).document
        self.assertEqual(same_a, same_b)
        for changed in (changed_key, changed_value, changed_exact):
            self.assertNotEqual(same_a.content_key, changed.content_key)

    def test_static_facts_bound_count_numeric_magnitude_and_serialized_payload(self):
        exact = sealed_exact()
        legal = exact_item_module.seal_exact_static_facts(
            exact,
            {
                "minimum": -9007199254740991,
                "maximum": 9007199254740991,
                "fraction": 1.5,
            },
        )
        self.assertEqual(legal.status, "verified")

        invalid = (
            (
                {"stat": 10 ** 4999},
                "STATIC_FACT_NUMBER_BOUNDS",
                "exactStaticFacts.facts.stat",
            ),
            (
                {"stat": 9007199254740992},
                "STATIC_FACT_NUMBER_BOUNDS",
                "exactStaticFacts.facts.stat",
            ),
            (
                {"stat": -9007199254740992},
                "STATIC_FACT_NUMBER_BOUNDS",
                "exactStaticFacts.facts.stat",
            ),
            (
                {"stat": 9007199254740992.0},
                "STATIC_FACT_NUMBER_BOUNDS",
                "exactStaticFacts.facts.stat",
            ),
            (
                {"stat": -9007199254740992.0},
                "STATIC_FACT_NUMBER_BOUNDS",
                "exactStaticFacts.facts.stat",
            ),
            (
                {f"stat_{index:03d}": index for index in range(129)},
                "STATIC_FACT_COUNT_BOUNDS",
                "exactStaticFacts.facts",
            ),
        )
        for facts, expected_code, expected_path in invalid:
            with self.subTest(expected_code=expected_code, expected_path=expected_path):
                try:
                    result = exact_item_module.seal_exact_static_facts(exact, facts)
                except (ValueError, OverflowError) as error:
                    self.fail(
                        f"static fact boundary leaked {type(error).__name__}"
                    )
                self.assertEqual(result.status, "blocked")
                self.assertIsNone(result.document)
                self.assertEqual(result.issues[0].code, expected_code)
                self.assertEqual(result.issues[0].path, expected_path)

        oversize_payload = {
            "schemaRevision": "exact-static-facts-v1",
            "exactItemInstanceKey": exact.content_key,
            "facts": {"stat": 1},
            "padding": "x" * 65536,
        }
        with self.assertRaises(CanonicalValueError) as raised:
            exact_item_module._validate_exact_static_facts_payload(
                oversize_payload
            )
        self.assertEqual(raised.exception.code, "STATIC_FACTS_PAYLOAD_BOUNDS")
        self.assertEqual(raised.exception.path, "exactStaticFacts")

    def test_static_facts_reject_integral_float_and_negative_zero_ambiguity(self):
        exact = sealed_exact()
        for amount in (1.0, -1.0, 0.0, -0.0, 9007199254740991.0):
            with self.subTest(amount=repr(amount)):
                result = exact_item_module.seal_exact_static_facts(
                    exact,
                    {"stat": amount},
                )
                self.assertEqual(result.status, "blocked")
                self.assertEqual(
                    result.issues[0].code,
                    "AMBIGUOUS_INTEGRAL_STATIC_FACT_FLOAT",
                )
                self.assertEqual(
                    result.issues[0].path,
                    "exactStaticFacts.facts.stat",
                )

        first = exact_item_module.seal_exact_static_facts(
            exact, {"stat": 1, "fraction": 1.5},
        ).document
        same = exact_item_module.seal_exact_static_facts(
            exact, {"fraction": 1.5, "stat": 1},
        ).document
        changed = exact_item_module.seal_exact_static_facts(
            exact, {"stat": 2, "fraction": 1.5},
        ).document
        self.assertEqual(first, same)
        self.assertNotEqual(first.content_key, changed.content_key)

    def test_static_facts_serialization_failures_return_blocked_without_broad_catch(self):
        exact = sealed_exact()
        for error in (ValueError("invalid canonical integer"), OverflowError("overflow")):
            with self.subTest(error=type(error).__name__):
                with patch.object(
                    exact_item_module,
                    "canonical_json_bytes",
                    side_effect=error,
                    create=True,
                ):
                    result = exact_item_module.seal_exact_static_facts(
                        exact,
                        {"stat": 1},
                    )
                self.assertEqual(result.status, "blocked")
                self.assertIsNone(result.document)
                self.assertEqual(
                    result.issues[0].code,
                    "STATIC_FACTS_SERIALIZATION_INVALID",
                )
                self.assertEqual(
                    result.issues[0].path,
                    "exactStaticFacts",
                )

    def test_envelope_rejects_raw_types_and_cross_exact_documents(self):
        exact_a, static_a, progression_a, effect_a = sealed_task4_inputs()
        exact_b, static_b, progression_b, effect_b = sealed_task4_inputs(
            sealed_exact(itemId="1002")
        )
        valid = {
            "exact": exact_a,
            "static_facts": static_a,
            "progression": progression_a,
            "effect_support": effect_a,
            "resolver_revision": "resolver-v2",
        }
        for field in ("exact", "static_facts", "progression", "effect_support"):
            with self.subTest(field=field):
                raw = json.loads(valid[field].canonical_bytes)
                with self.assertRaises(TypeError):
                    exact_authority_module.seal_exact_authority_envelope(
                        **{**valid, field: raw}
                    )

        for fields in (
            {"static_facts": static_b},
            {"progression": progression_b},
            {"effect_support": effect_b},
            {"exact": exact_b},
        ):
            with self.subTest(fields=fields):
                self.assertEqual(
                    exact_authority_module.seal_exact_authority_envelope(
                        **{**valid, **fields}
                    ).status,
                    "blocked",
                )

    def test_envelope_composes_only_verified_sealed_identities(self):
        exact, static, progression, effect = sealed_task4_inputs()
        first = exact_authority_module.seal_exact_authority_envelope(
            exact=exact,
            static_facts=static,
            progression=progression,
            effect_support=effect,
            resolver_revision="resolver-v2",
        )
        second = exact_authority_module.seal_exact_authority_envelope(
            exact=exact,
            static_facts=static,
            progression=progression,
            effect_support=effect,
            resolver_revision="resolver-v2",
        )
        self.assertEqual(first.status, "verified")
        self.assertEqual(first.document, second.document)
        self.assertEqual(first.document.document_kind, "exact_authority")
        self.assertEqual(
            first.document.schema_revision,
            "exact-authority-envelope-v1",
        )
        self.assertRegex(
            first.document.content_key,
            r"^exact-authority:sha256:[0-9a-f]{64}$",
        )
        self.assertEqual(
            json.loads(first.document.canonical_bytes),
            {
                "schemaRevision": "exact-authority-envelope-v1",
                "exactItemInstanceKey": exact.content_key,
                "staticFactsKey": static.content_key,
                "progressionBindingKey": progression.content_key,
                "effectSupportKey": effect.content_key,
                "resolverRevision": "resolver-v2",
            },
        )
        self.assertNotIn(
            "serializer_input",
            inspect.signature(
                exact_authority_module.seal_exact_authority_envelope
            ).parameters,
        )
        with self.assertRaises(TypeError):
            exact_authority_module.seal_exact_authority_envelope(
                exact=exact,
                static_facts=static,
                progression=progression,
                effect_support=effect,
                resolver_revision="resolver-v2",
                serializer_input={"id": "9999", "ilevel": "999"},
            )

        changed_static = exact_item_module.seal_exact_static_facts(
            exact, {"haste_rating": 242},
        ).document
        changed_resolver = exact_authority_module.seal_exact_authority_envelope(
            exact=exact,
            static_facts=static,
            progression=progression,
            effect_support=effect,
            resolver_revision="resolver-v3",
        ).document
        changed_facts = exact_authority_module.seal_exact_authority_envelope(
            exact=exact,
            static_facts=changed_static,
            progression=progression,
            effect_support=effect,
            resolver_revision="resolver-v2",
        ).document
        self.assertNotEqual(first.document.content_key, changed_resolver.content_key)
        self.assertNotEqual(first.document.content_key, changed_facts.content_key)

    def test_envelope_blocks_unsupported_unknown_stale_duplicate_and_unrelated_effect_evidence(self):
        exact, static, progression, effect = sealed_task4_inputs()
        unsupported = sealed_effect_aggregate(exact, status="unsupported")
        payload = json.loads(effect.canonical_bytes)
        forged_effects = (
            unsupported,
            forged_document(effect, payload={**payload, "status": "unknown"}),
            forged_document(
                effect,
                payload={**payload, "simcRuntimeRevision": "stale-runtime"},
            ),
            forged_document(
                effect,
                payload={**payload, "subjects": [*payload["subjects"], payload["subjects"][0]]},
            ),
            forged_document(
                effect,
                payload={**payload, "supportRecords": []},
            ),
            sealed_effect_aggregate(sealed_exact(itemId="1002")),
        )
        for invalid_effect in forged_effects:
            with self.subTest(invalid_effect=invalid_effect):
                self.assertEqual(
                    exact_authority_module.seal_exact_authority_envelope(
                        exact=exact,
                        static_facts=static,
                        progression=progression,
                        effect_support=invalid_effect,
                        resolver_revision="resolver-v2",
                    ).status,
                    "blocked",
                )

    def test_envelope_returns_blocked_for_wrong_or_tampered_seals_without_partial_authority(self):
        exact, static, progression, effect = sealed_task4_inputs()
        valid = {
            "exact": exact,
            "static_facts": static,
            "progression": progression,
            "effect_support": effect,
            "resolver_revision": "resolver-v2",
        }
        for field, document in (
            ("exact", exact),
            ("static_facts", static),
            ("progression", progression),
            ("effect_support", effect),
        ):
            candidates = (
                forged_document(document, kind="wrong_kind"),
                forged_document(document, schema="wrong-schema"),
                forged_document(document, prefix="attacker:sha256:"),
                tampered_document(
                    document,
                    content_key=document.content_key[:-1] + (
                        "0" if document.content_key[-1] != "0" else "1"
                    ),
                ),
            )
            for candidate in candidates:
                with self.subTest(field=field, candidate=candidate):
                    result = exact_authority_module.seal_exact_authority_envelope(
                        **{**valid, field: candidate}
                    )
                    self.assertEqual(result.status, "blocked")
                    self.assertIsNone(result.document)
                    self.assertTrue(result.issues)

        for resolver_revision in (" resolver-v2", "resolver-v2\n", False, ""):
            with self.subTest(resolver_revision=resolver_revision):
                result = exact_authority_module.seal_exact_authority_envelope(
                    **{**valid, "resolver_revision": resolver_revision}
                )
                self.assertEqual(result.status, "blocked")

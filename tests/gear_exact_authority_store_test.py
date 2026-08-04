import copy
import json
import unittest

import server.gear_exact_item_instance as exact_item_module
from server.gear_exact_authority import (
    seal_exact_authority_envelope,
    seal_exact_progression,
)
from server.gear_exact_authority_store import (
    ExactAuthorityBundle,
    GearExactAuthorityStore,
    GearExactAuthorityStoreIntegrityError,
)
from server.gear_exact_item_instance import seal_exact_item
from server.simc_item_effect_support import (
    derive_exact_effect_subjects,
    resolve_exact_effect_support,
    seal_effect_record,
)


RUNTIME = "simc-2026.08.04"
RULE = "gear-rule-matrix-v1"
SEASON = "season-17-f131dd36ddf1"
RESOLVER = "resolver-v2"


def authority_bundle(item_id="1001", *, gems=("240892", "240893", "240892")):
    exact = seal_exact_item({
        "itemId": item_id,
        "declaredItemLevel": 266,
        "bonusIds": ["13334"],
        "context": "heroic",
        "gemIds": list(gems),
        "gemBonusIds": ["1514", "1515", "1514"][:len(gems)],
        "gemItemLevels": [90, 91, 90][:len(gems)],
        "enchantId": "",
        "craftedStats": [],
        "embellishmentIds": [],
        "redirectedBaseStats": [],
    }).document
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
    records = []
    for subject in derive_exact_effect_subjects(exact):
        records.append(seal_effect_record({
            "schemaRevision": "simc-item-effect-record-v1",
            "status": "verified",
            "subjectKind": subject.kind,
            "subjectKey": subject.key,
            "subjectVariantSignature": subject.variant_signature,
            "hasDynamicEffect": False,
            "simcRuntimeRevision": RUNTIME,
            "verifiedAt": "2026-08-04T00:00:00Z",
        }, runtime_revision=RUNTIME).document)
    effect = resolve_exact_effect_support(
        exact, runtime_revision=RUNTIME, records=records,
    ).document
    envelope = seal_exact_authority_envelope(
        exact=exact,
        static_facts=static,
        progression=progression,
        effect_support=effect,
        resolver_revision=RESOLVER,
    ).document
    return ExactAuthorityBundle(
        exact_item=exact,
        static_facts=static,
        progression=progression,
        effect_records=tuple(records),
        effect_support=effect,
        envelope=envelope,
    )


class FakeDatabase:
    def __init__(self):
        self.documents = {}
        self.relations = {}
        self.bundles = {}
        self.statements = []
        self.fail_on_bundle_insert = False


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.database = connection.database
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=()):
        normalized = " ".join(str(sql).split())
        self.database.statements.append(normalized)
        self.rows = []
        if "exact_authority_revision_projection" in normalized:
            progression = json.loads(bytes(params[0]))
            effect = json.loads(bytes(params[1]))
            envelope = json.loads(bytes(params[2]))
            self.rows = [(
                progression["gearRuleRevision"],
                effect["simcRuntimeRevision"],
                envelope["resolverRevision"],
            )]
        elif "exact_authority_document_insert" in normalized:
            key, kind, schema, raw = params
            self.database.documents.setdefault(
                key, (key, kind, schema, bytes(raw), True),
            )
        elif "exact_authority_document_load" in normalized:
            row = self.database.documents.get(params[0])
            self.rows = [row] if row else []
        elif "exact_authority_effect_relation_insert" in normalized:
            support_key, ordinal, record_key = params
            self.database.relations.setdefault(
                (support_key, ordinal), record_key,
            )
        elif "exact_authority_effect_relation_load" in normalized:
            support_key = params[0]
            self.rows = [
                (ordinal, record_key)
                for (aggregate_key, ordinal), record_key
                in sorted(self.database.relations.items())
                if aggregate_key == support_key
            ]
        elif "exact_authority_bundle_insert" in normalized:
            if self.database.fail_on_bundle_insert:
                raise RuntimeError("injected bundle insert failure")
            self.database.bundles.setdefault(params[0], tuple(params))
        elif "exact_authority_bundle_load" in normalized:
            row = self.database.bundles.get(params[0])
            self.rows = [row] if row else []

    def fetchone(self):
        row = self.rows[0] if self.rows else None
        self.rows = []
        return row

    def fetchall(self):
        rows = self.rows
        self.rows = []
        return rows


class FakeConnection:
    def __init__(self, database):
        self.database = database
        self.before = None
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        self.before = copy.deepcopy((
            self.database.documents,
            self.database.relations,
            self.database.bundles,
        ))
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            (
                self.database.documents,
                self.database.relations,
                self.database.bundles,
            ) = self.before
            self.rolled_back = True
        else:
            self.committed = True
        return False

    def cursor(self):
        return FakeCursor(self)


class GearExactAuthorityStoreTest(unittest.TestCase):
    def setUp(self):
        self.database = FakeDatabase()
        self.connections = []

        def connection_factory():
            connection = FakeConnection(self.database)
            self.connections.append(connection)
            return connection

        self.store = GearExactAuthorityStore(connection_factory)

    def test_whole_bundle_round_trip_is_frozen_idempotent_and_duplicate_ordered(self):
        bundle = authority_bundle()
        first = self.store.seal_authority_bundle(bundle)
        second = self.store.seal_authority_bundle(bundle)

        self.assertEqual(first, bundle)
        self.assertEqual(second, bundle)
        self.assertEqual(first.effect_records[1], first.effect_records[3])
        self.assertEqual(len(self.database.bundles), 1)
        self.assertEqual(len(self.database.relations), len(bundle.effect_records))
        joined = "\n".join(self.database.statements).upper()
        self.assertIn("ON CONFLICT DO NOTHING", joined)
        self.assertNotIn(" UPDATE ", f" {joined} ")
        self.assertNotIn(" DELETE ", f" {joined} ")

    def test_batch_loads_preserve_a_b_a_order_and_multiplicity(self):
        a = self.store.seal_authority_bundle(authority_bundle("1001"))
        b = self.store.seal_authority_bundle(authority_bundle("1002"))

        loaded = self.store.load_verified_bundles(
            (a.envelope.content_key, b.envelope.content_key, a.envelope.content_key),
            gear_rule_revision=RULE,
            simc_runtime_revision=RUNTIME,
            resolver_revision=RESOLVER,
        )
        records = self.store.load_effect_records(
            (
                a.effect_records[1].content_key,
                a.effect_records[2].content_key,
                a.effect_records[1].content_key,
            ),
            simc_runtime_revision=RUNTIME,
        )
        self.assertEqual(loaded, (a, b, a))
        self.assertEqual(
            records,
            (a.effect_records[1], a.effect_records[2], a.effect_records[1]),
        )

    def test_missing_revision_mismatch_collision_and_ordinal_drift_fail_closed(self):
        sealed = self.store.seal_authority_bundle(authority_bundle())
        key = sealed.envelope.content_key
        for kwargs in (
            {"gear_rule_revision": "wrong", "simc_runtime_revision": RUNTIME, "resolver_revision": RESOLVER},
            {"gear_rule_revision": RULE, "simc_runtime_revision": "wrong", "resolver_revision": RESOLVER},
            {"gear_rule_revision": RULE, "simc_runtime_revision": RUNTIME, "resolver_revision": "wrong"},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(GearExactAuthorityStoreIntegrityError):
                    self.store.load_verified_bundle(key, **kwargs)

        with self.assertRaises(GearExactAuthorityStoreIntegrityError):
            self.store.load_verified_bundle(
                "exact-authority:sha256:" + "0" * 64,
                gear_rule_revision=RULE,
                simc_runtime_revision=RUNTIME,
                resolver_revision=RESOLVER,
            )

        original = self.database.documents[sealed.exact_item.content_key]
        self.database.documents[sealed.exact_item.content_key] = (
            original[0], original[1], original[2], original[3] + b" ", True,
        )
        with self.assertRaises(GearExactAuthorityStoreIntegrityError):
            self.store.load_verified_bundle(
                key,
                gear_rule_revision=RULE,
                simc_runtime_revision=RUNTIME,
                resolver_revision=RESOLVER,
            )

        self.database.documents[sealed.exact_item.content_key] = original
        self.database.documents[sealed.static_facts.content_key] = (
            *self.database.documents[sealed.static_facts.content_key][:4],
            False,
        )
        with self.assertRaises(GearExactAuthorityStoreIntegrityError):
            self.store.load_verified_bundle(
                key,
                gear_rule_revision=RULE,
                simc_runtime_revision=RUNTIME,
                resolver_revision=RESOLVER,
            )
        self.database.documents[sealed.static_facts.content_key] = (
            *self.database.documents[sealed.static_facts.content_key][:4],
            True,
        )
        self.database.relations.pop((sealed.effect_support.content_key, 1))
        with self.assertRaises(GearExactAuthorityStoreIntegrityError):
            self.store.load_verified_bundle(
                key,
                gear_rule_revision=RULE,
                simc_runtime_revision=RUNTIME,
                resolver_revision=RESOLVER,
            )

    def test_partial_transaction_rolls_back_and_bundle_type_is_exact(self):
        bundle = authority_bundle()
        self.database.fail_on_bundle_insert = True
        with self.assertRaises(RuntimeError):
            self.store.seal_authority_bundle(bundle)
        self.assertEqual(self.database.documents, {})
        self.assertEqual(self.database.relations, {})
        self.assertEqual(self.database.bundles, {})
        self.assertTrue(self.connections[-1].rolled_back)

        with self.assertRaises((TypeError, GearExactAuthorityStoreIntegrityError)):
            self.store.seal_authority_bundle({"envelope": bundle.envelope})

    def test_effect_reload_failure_uses_store_integrity_error_and_rolls_back(self):
        bundle = authority_bundle()
        subject = derive_exact_effect_subjects(bundle.exact_item)[0]
        wrong_runtime_record = seal_effect_record({
            "schemaRevision": "simc-item-effect-record-v1",
            "status": "verified",
            "subjectKind": subject.kind,
            "subjectKey": subject.key,
            "subjectVariantSignature": subject.variant_signature,
            "hasDynamicEffect": False,
            "simcRuntimeRevision": "simc-wrong-runtime",
            "verifiedAt": "2026-08-04T00:00:00Z",
        }, runtime_revision="simc-wrong-runtime").document
        invalid = ExactAuthorityBundle(
            exact_item=bundle.exact_item,
            static_facts=bundle.static_facts,
            progression=bundle.progression,
            effect_records=(wrong_runtime_record, *bundle.effect_records[1:]),
            effect_support=bundle.effect_support,
            envelope=bundle.envelope,
        )

        with self.assertRaises(GearExactAuthorityStoreIntegrityError):
            self.store.seal_authority_bundle(invalid)
        self.assertEqual(self.database.documents, {})
        self.assertEqual(self.database.relations, {})
        self.assertEqual(self.database.bundles, {})
        self.assertTrue(self.connections[-1].rolled_back)

    def test_extra_effect_ordinal_and_empty_batch_requests_fail_closed(self):
        sealed = self.store.seal_authority_bundle(authority_bundle())
        self.database.relations[
            (sealed.effect_support.content_key, len(sealed.effect_records))
        ] = sealed.effect_records[0].content_key
        with self.assertRaises(GearExactAuthorityStoreIntegrityError):
            self.store.load_verified_bundle(
                sealed.envelope.content_key,
                gear_rule_revision=RULE,
                simc_runtime_revision=RUNTIME,
                resolver_revision=RESOLVER,
            )
        with self.assertRaises(GearExactAuthorityStoreIntegrityError):
            self.store.load_verified_bundles(
                (),
                gear_rule_revision=RULE,
                simc_runtime_revision=RUNTIME,
                resolver_revision=RESOLVER,
            )
        with self.assertRaises(GearExactAuthorityStoreIntegrityError):
            self.store.load_effect_records((), simc_runtime_revision=RUNTIME)


if __name__ == "__main__":
    unittest.main()

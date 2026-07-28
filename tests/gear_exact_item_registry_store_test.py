import copy
import json
import unittest

from server.gear_exact_item_registry import build_exact_item_registry
from server.gear_exact_item_registry_store import (
    GearExactItemRegistryIntegrityError,
    GearExactItemRegistryStore,
)
from tests.gear_exact_item_instance_test import (
    CATALOG_REVISION,
    CURRENT_BINDING,
    exact_row,
)
from tests.gear_exact_item_registry_test import template


class FakeDatabase:
    def __init__(self):
        self.headers = {}
        self.selections = {}
        self.instances = {}
        self.validations = {}
        self.references = {}
        self.statements = []


class FakeCursor:
    def __init__(self, database):
        self.database = database
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=()):
        normalized = " ".join(str(sql).split())
        self.database.statements.append(normalized)
        self.rows = []
        if "gear_exact_registry_insert_header" in normalized:
            self.database.headers.setdefault(params[0], tuple(params))
        elif "gear_exact_registry_load_header" in normalized:
            row = self.database.headers.get(params[0])
            self.rows = [row] if row else []
        elif "gear_exact_registry_latest_revision" in normalized:
            candidates = {
                revision: row
                for (revision, _), row in self.database.references.items()
            }
            if "catalog_revision = %s" in normalized:
                catalog = params[0]
                candidates = {
                    revision: row
                    for revision, row in candidates.items()
                    if row[1] == catalog
                }
            if "gear_rule_revision = %s" in normalized:
                rule = params[-1]
                candidates = {
                    revision: row
                    for revision, row in candidates.items()
                    if row[3] == rule
                }
            revisions = sorted(candidates, reverse=True)
            self.rows = [(revisions[0],)] if revisions else []
        elif "gear_exact_registry_load_refs" in normalized:
            self.rows = [
                row
                for (revision, _), row in sorted(self.database.references.items())
                if revision == params[0]
            ]
        elif "gear_exact_registry_load_instances" in normalized:
            keys = set(params[0])
            self.rows = [
                row
                for key, row in sorted(self.database.instances.items())
                if key in keys
            ]
        elif "gear_exact_registry_load_selections" in normalized:
            keys = set(params[0])
            self.rows = [
                row
                for key, row in sorted(self.database.selections.items())
                if key in keys
            ]
        elif "gear_exact_registry_load_validations" in normalized:
            keys = set(params[0])
            self.rows = [
                row
                for (exact_key, catalog, rule), row in sorted(
                    self.database.validations.items()
                )
                if exact_key in keys and catalog == params[1] and rule == params[2]
            ]

    def executemany(self, sql, rows):
        normalized = " ".join(str(sql).split())
        materialized = [tuple(row) for row in rows]
        self.database.statements.append(normalized)
        if "gear_exact_registry_insert_selections" in normalized:
            for row in materialized:
                self.database.selections.setdefault(row[0], row)
        elif "gear_exact_registry_insert_instances" in normalized:
            for row in materialized:
                self.database.instances.setdefault(row[0], row)
        elif "gear_exact_registry_insert_validations" in normalized:
            for row in materialized:
                self.database.validations.setdefault((row[0], row[1], row[2]), row)
        elif "gear_exact_registry_insert_refs" in normalized:
            for row in materialized:
                self.database.references.setdefault((row[0], row[16]), row)

    def fetchall(self):
        rows = list(self.rows)
        self.rows = []
        return rows

    def fetchone(self):
        row = self.rows[0] if self.rows else None
        self.rows = []
        return row


class FakeConnection:
    def __init__(self, database):
        self.database = database
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.rolled_back = True
        else:
            self.committed = True
        return False

    def cursor(self):
        return FakeCursor(self.database)


class GearExactItemRegistryStoreTest(unittest.TestCase):
    def setUp(self):
        self.database = FakeDatabase()
        self.connection = FakeConnection(self.database)
        self.store = GearExactItemRegistryStore(lambda: self.connection)
        self.registry = build_exact_item_registry(
            CURRENT_BINDING,
            catalog_revision=CATALOG_REVISION,
            exact_rows=[exact_row()],
            community_templates=[template()],
            personal_templates=[],
        )

    def test_seal_is_idempotent_append_only_and_exactly_reloadable(self):
        first = self.store.seal_registry(self.registry)
        second = self.store.seal_registry(copy.deepcopy(self.registry))

        self.assertEqual(first, second)
        self.assertEqual(first["registryRevision"], self.registry["registryRevision"])
        self.assertEqual(len(self.database.selections), 1)
        self.assertEqual(len(self.database.headers), 1)
        self.assertEqual(len(self.database.instances), 1)
        self.assertEqual(len(self.database.validations), 1)
        self.assertEqual(len(self.database.references), 1)
        joined = "\n".join(self.database.statements).upper()
        self.assertIn("ON CONFLICT DO NOTHING", joined)
        self.assertIn("GEAR_EXACT_REGISTRY_INSERT_HEADER", joined)
        self.assertIn("CONTEXT_JSON::TEXT", joined)
        self.assertIn("VALIDATION_JSON::TEXT", joined)
        self.assertNotIn(" UPDATE ", f" {joined} ")
        self.assertNotIn(" DELETE ", f" {joined} ")
        self.assertTrue(self.connection.committed)
        self.assertFalse(self.connection.rolled_back)

    def test_latest_registry_is_filterable_and_exactly_reloadable(self):
        self.store.seal_registry(self.registry)

        latest = self.store.load_latest_registry(
            catalog_revision=CATALOG_REVISION,
            gear_rule_revision=CURRENT_BINDING["gearRuleRevision"],
        )
        missing = self.store.load_latest_registry(
            catalog_revision="gear-catalog:sha256:" + ("0" * 64),
            gear_rule_revision="",
        )

        self.assertEqual(latest, self.registry)
        self.assertEqual(missing, {})

    def test_tampered_exact_row_is_rejected_not_overwritten(self):
        self.store.seal_registry(self.registry)
        key = self.registry["exactItemInstances"][0]["exactItemInstanceKey"]
        stored = list(self.database.instances[key])
        payload = json.loads(stored[9])
        payload["ilevel"] = 999
        stored[9] = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.database.instances[key] = tuple(stored)

        with self.assertRaisesRegex(
            GearExactItemRegistryIntegrityError,
            "sealed exact instance integrity mismatch",
        ):
            self.store.seal_registry(copy.deepcopy(self.registry))

        self.assertEqual(json.loads(self.database.instances[key][9])["ilevel"], 999)

    def test_tampered_registry_header_is_rejected_not_ignored(self):
        self.store.seal_registry(self.registry)
        revision = self.registry["registryRevision"]
        stored = list(self.database.headers[revision])
        stored[4] = "verified" if stored[4] == "partial" else "partial"
        self.database.headers[revision] = tuple(stored)

        with self.assertRaisesRegex(
            GearExactItemRegistryIntegrityError,
            "sealed exact registry header mismatch",
        ):
            self.store.load_registry(revision)

    def test_partial_evidence_registry_is_append_only_and_reloadable(self):
        unresolved = exact_row()
        unresolved["simcOptions"]["enchant_id"] = "7443/7444"
        partial_template = template()
        partial_template["gearItems"][0].pop("enchantId")
        registry = build_exact_item_registry(
            CURRENT_BINDING,
            catalog_revision=CATALOG_REVISION,
            exact_rows=[unresolved],
            community_templates=[partial_template],
            personal_templates=[],
        )

        sealed = self.store.seal_registry(registry)

        self.assertEqual(sealed["status"], "partial")
        self.assertEqual(
            sealed["problemCodes"],
            ["ENHANCEMENT_SINGLE_VALUE_MALFORMED"],
        )
        self.assertEqual(len(self.database.instances), 0)
        self.assertEqual(len(self.database.validations), 0)
        self.assertEqual(len(self.database.references), 1)
        stored_reference = next(iter(self.database.references.values()))
        self.assertIsNone(stored_reference[12])
        self.assertEqual(
            sealed["templateReferences"][0]["validationStatus"],
            "partial",
        )

    def test_blocked_or_owner_bearing_registry_is_rejected_before_sql(self):
        blocked = copy.deepcopy(self.registry)
        blocked["status"] = "blocked"
        blocked["problemCodes"] = ["SYNTHETIC"]

        with self.assertRaises(GearExactItemRegistryIntegrityError):
            self.store.seal_registry(blocked)

        self.assertEqual(self.database.statements, [])
        owner_bearing = copy.deepcopy(self.registry)
        owner_bearing["ownerName"] = "must-never-be-sealed"

        with self.assertRaisesRegex(
            GearExactItemRegistryIntegrityError,
            "owner",
        ):
            self.store.seal_registry(owner_bearing)

        self.assertEqual(self.database.statements, [])


if __name__ == "__main__":
    unittest.main()

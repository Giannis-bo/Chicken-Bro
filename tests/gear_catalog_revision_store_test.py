import copy
import json
import unittest

from server.gear_catalog_revision import build_catalog_revision
from server.gear_catalog_revision_store import (
    GearCatalogRevisionIntegrityError,
    GearCatalogRevisionStore,
)
from tests.gear_catalog_revision_test import (
    CURRENT_BINDING,
    crafted_rows,
    regular_rows,
)


class FakeDatabase:
    def __init__(self):
        self.catalogs = {}
        self.items = {}
        self.variants = {}
        self.statements = []
        self.executemany_calls = []
        self.reverse_member_load_order = False


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
        if "gear_catalog_revision_insert" in normalized:
            key = params[0]
            self.database.catalogs.setdefault(key, tuple(params))
        elif "gear_catalog_revision_load_catalog" in normalized:
            row = self.database.catalogs.get(params[0])
            self.rows = [row] if row else []
        elif "gear_catalog_revision_load_items" in normalized:
            self.rows = [
                row
                for (catalog_revision, _), row in sorted(
                    self.database.items.items(),
                    reverse=self.database.reverse_member_load_order,
                )
                if catalog_revision == params[0]
            ]
        elif "gear_catalog_revision_load_variants" in normalized:
            self.rows = [
                row
                for (catalog_revision, _), row in sorted(
                    self.database.variants.items(),
                    reverse=self.database.reverse_member_load_order,
                )
                if catalog_revision == params[0]
            ]

    def executemany(self, sql, rows):
        normalized = " ".join(str(sql).split())
        materialized = [tuple(row) for row in rows]
        self.database.statements.append(normalized)
        self.database.executemany_calls.append((normalized, materialized))
        if "gear_catalog_revision_insert_items" in normalized:
            for row in materialized:
                self.database.items.setdefault((row[0], row[1]), row)
        elif "gear_catalog_revision_insert_variants" in normalized:
            for row in materialized:
                self.database.variants.setdefault((row[0], row[1]), row)

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows = list(self.rows)
        self.rows = []
        return rows


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


class GearCatalogRevisionStoreTest(unittest.TestCase):
    def setUp(self):
        self.database = FakeDatabase()
        self.connection = FakeConnection(self.database)
        self.store = GearCatalogRevisionStore(lambda: self.connection)
        self.catalog = build_catalog_revision(CURRENT_BINDING, regular_rows())

    def test_seal_is_idempotent_append_only_and_loads_exact_content(self):
        first = self.store.seal_catalog(self.catalog)
        second = self.store.seal_catalog(copy.deepcopy(self.catalog))

        self.assertEqual(first["catalogRevision"], self.catalog["catalogRevision"])
        self.assertEqual(second, first)
        self.assertEqual(len(self.database.catalogs), 1)
        self.assertEqual(len(self.database.items), 1)
        self.assertEqual(len(self.database.variants), 1)
        joined = "\n".join(self.database.statements).upper()
        self.assertNotIn(" UPDATE ", f" {joined} ")
        self.assertNotIn(" DELETE ", f" {joined} ")
        self.assertIn("ON CONFLICT DO NOTHING", joined)
        self.assertTrue(self.connection.committed)
        self.assertFalse(self.connection.rolled_back)

    def test_conflicting_sealed_membership_is_rejected_not_overwritten(self):
        self.store.seal_catalog(self.catalog)
        key = (
            self.catalog["catalogRevision"],
            self.catalog["itemDefinitions"][0]["itemId"],
        )
        stored = list(self.database.items[key])
        definition = json.loads(stored[6])
        definition["name"] = "Tampered"
        stored[6] = json.dumps(
            definition,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.database.items[key] = tuple(stored)

        with self.assertRaisesRegex(
            GearCatalogRevisionIntegrityError,
            "sealed .* mismatch",
        ):
            self.store.seal_catalog(copy.deepcopy(self.catalog))

        self.assertEqual(
            json.loads(self.database.items[key][6])["name"],
            "Tampered",
        )

    def test_seal_compares_membership_independent_of_database_row_order(self):
        rows = regular_rows()
        crafted = crafted_rows()
        rows["items"].extend(crafted["items"])
        rows["sources"].extend(crafted["sources"])
        rows["variants"].extend(crafted["variants"])
        catalog = build_catalog_revision(CURRENT_BINDING, rows)
        self.database.reverse_member_load_order = True

        sealed = self.store.seal_catalog(catalog)

        self.assertEqual(
            sealed["catalogRevision"],
            catalog["catalogRevision"],
        )
        self.assertEqual(len(sealed["itemDefinitions"]), 2)
        self.assertEqual(len(sealed["browseVariants"]), 2)

    def test_unverified_or_identity_invalid_catalog_is_rejected_before_sql(self):
        invalid = copy.deepcopy(self.catalog)
        invalid["browseVariants"][0]["browseVariantKey"] = (
            "browse-variant:sha256:" + ("f" * 64)
        )

        with self.assertRaises(GearCatalogRevisionIntegrityError):
            self.store.seal_catalog(invalid)

        self.assertEqual(self.database.statements, [])


if __name__ == "__main__":
    unittest.main()

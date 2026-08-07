import copy
import unittest

from server.exact_template_authority_binding import (
    canonical_remote_template_source,
    seal_exact_template_authority_binding,
)
from tests.exact_template_authority_binding_test import (
    OWNER_ID,
    admission_proof,
    remote_source,
)


class FakeCursor:
    def __init__(self, rows):
        self.responses = list(rows)
        self.rows = []
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, _kind, _value, _traceback):
        return False

    def execute(self, statement, parameters=()):
        self.calls.append((" ".join(statement.split()), tuple(parameters)))
        response = self.responses.pop(0) if self.responses else None
        self.rows = list(response) if isinstance(response, list) else (
            [response] if response is not None else []
        )

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows = self.rows
        self.rows = []
        return rows


class FakeConnection:
    def __init__(self, rows):
        self.cursor_value = FakeCursor(rows)

    def __enter__(self):
        return self

    def __exit__(self, _kind, _value, _traceback):
        return False

    def cursor(self):
        return self.cursor_value


class ExactTemplateAuthorityBindingStoreTest(unittest.TestCase):
    def setUp(self):
        self.source = canonical_remote_template_source(remote_source())
        self.document = seal_exact_template_authority_binding(
            self.source,
            admission_proof(),
        )

    def _store(self, rows):
        from server.exact_template_authority_binding_store import (
            ExactTemplateAuthorityBindingStore,
        )

        connection = FakeConnection(rows)
        return ExactTemplateAuthorityBindingStore(lambda: connection), connection

    def test_admit_uses_only_owner_scoped_function_and_reloads_returned_bytes(self):
        store, connection = self._store([(
            self.document.content_key,
            self.document.canonical_bytes,
        )])

        saved = store.admit(OWNER_ID, self.source, self.document)

        self.assertEqual(saved, self.document)
        call = connection.cursor_value.calls[0]
        self.assertIn("ops.websim_exact_template_binding_admit", call[0])
        self.assertEqual(call[1][0], OWNER_ID)
        self.assertEqual(call[1][1], self.source.template_id)
        self.assertEqual(call[1][2], self.source.template_config_hash)
        self.assertEqual(call[1][3], self.source.source_payload_hash)
        self.assertEqual(call[1][4], self.source.selection_signature)
        self.assertEqual(call[1][5], self.document.canonical_bytes)
        self.assertNotIn("rawString", str(call))

    def test_read_requires_current_owner_source_identity_and_never_returns_row_on_absence(self):
        store, connection = self._store([(
            self.document.content_key,
            self.document.canonical_bytes,
        ), None])

        expected = admission_proof()
        kwargs = {
            "gear_exact_registry_revision": expected["gearExactRegistryRevision"],
            "gear_rule_revision": expected["gearRuleRevision"],
            "resolver_revision": expected["resolverRevision"],
            "simc_runtime_revision": expected["simcRuntimeRevision"],
        }
        found = store.read(OWNER_ID, self.source, **kwargs)
        absent = store.read(OWNER_ID, self.source, **kwargs)

        self.assertEqual(found, self.document)
        self.assertIsNone(absent)
        self.assertTrue(all(
            "ops.websim_exact_template_binding_read" in call[0]
            for call in connection.cursor_value.calls
        ))
        self.assertEqual(connection.cursor_value.calls[0][1][5:], (
            expected["gearExactRegistryRevision"],
            expected["gearRuleRevision"],
            expected["resolverRevision"],
            expected["simcRuntimeRevision"],
        ))

    def test_source_or_owner_drift_fails_before_database_function(self):
        from server.exact_template_authority_binding_store import (
            ExactTemplateAuthorityBindingStoreIntegrityError,
        )

        store, connection = self._store([])
        changed = remote_source()
        changed["rawString"] = "changed"
        changed_source = canonical_remote_template_source(changed)

        with self.assertRaises(ExactTemplateAuthorityBindingStoreIntegrityError):
            store.admit(OWNER_ID, changed_source, self.document)
        with self.assertRaises(ExactTemplateAuthorityBindingStoreIntegrityError):
            store.read(
                "12345678-1234-5678-1234-567812345679",
                self.source,
                gear_exact_registry_revision=admission_proof()["gearExactRegistryRevision"],
                gear_rule_revision=admission_proof()["gearRuleRevision"],
                resolver_revision=admission_proof()["resolverRevision"],
                simc_runtime_revision=admission_proof()["simcRuntimeRevision"],
            )
        self.assertEqual(connection.cursor_value.calls, [])

    def test_database_bytes_key_drift_is_an_integrity_error(self):
        from server.exact_template_authority_binding_store import (
            ExactTemplateAuthorityBindingStoreIntegrityError,
        )

        store, _connection = self._store([(
            self.document.content_key,
            self.document.canonical_bytes + b" ",
        )])
        with self.assertRaises(ExactTemplateAuthorityBindingStoreIntegrityError):
            store.read(
                OWNER_ID,
                self.source,
                gear_exact_registry_revision=admission_proof()["gearExactRegistryRevision"],
                gear_rule_revision=admission_proof()["gearRuleRevision"],
                resolver_revision=admission_proof()["resolverRevision"],
                simc_runtime_revision=admission_proof()["simcRuntimeRevision"],
            )

    def test_multiple_rows_for_one_current_source_are_literal_integrity_failure(self):
        from server.exact_template_authority_binding_store import (
            ExactTemplateAuthorityBindingStoreIntegrityError,
        )

        store, _connection = self._store([[
            (self.document.content_key, self.document.canonical_bytes),
            (self.document.content_key, self.document.canonical_bytes),
        ]])
        with self.assertRaisesRegex(
            ExactTemplateAuthorityBindingStoreIntegrityError,
            "not unique",
        ):
            store.read(
                OWNER_ID,
                self.source,
                gear_exact_registry_revision=admission_proof()["gearExactRegistryRevision"],
                gear_rule_revision=admission_proof()["gearRuleRevision"],
                resolver_revision=admission_proof()["resolverRevision"],
                simc_runtime_revision=admission_proof()["simcRuntimeRevision"],
            )


if __name__ == "__main__":
    unittest.main()

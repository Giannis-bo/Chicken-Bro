import json
import unittest

from server.exact_template_authority_binding import (
    canonical_remote_template_source,
    seal_exact_template_authority_binding,
)
from tests.exact_runtime_authority_release_test import (
    first_pass_snapshot,
    release_input,
    resolver_context_input,
    subject_variant_signature,
)
from tests.exact_template_authority_binding_test import (
    OWNER_ID,
    admission_proof,
    remote_source,
)
from tests.gear_loadout_effect_authority_test import records_for


class FakeCursor:
    def __init__(self, responses):
        self.responses = list(responses)
        self.rows = []
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, _kind, _value, _traceback):
        return False

    def execute(self, statement, parameters=()):
        self.calls.append((" ".join(statement.split()), tuple(parameters)))
        response = self.responses.pop(0) if self.responses else []
        self.rows = list(response) if isinstance(response, list) else [response]

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows = self.rows
        self.rows = []
        return rows


class FakeConnection:
    def __init__(self, responses):
        self.cursor_value = FakeCursor(responses)

    def __enter__(self):
        return self

    def __exit__(self, _kind, _value, _traceback):
        return False

    def cursor(self):
        return self.cursor_value


class ExactRuntimeAuthorityReleaseStoreTest(unittest.TestCase):
    def setUp(self):
        from server import exact_runtime_authority_release as release_module

        self.module = release_module
        self.fixture, self.snapshot = first_pass_snapshot()
        self.context = self.module.seal_runtime_resolver_context(
            resolver_context_input(self.fixture, self.snapshot),
        ).document
        self.release = self.module.seal_runtime_authority_release(
            release_input(self.snapshot),
            resolver_context=self.context,
        ).document
        self.binding = seal_exact_template_authority_binding(
            canonical_remote_template_source(remote_source()),
            admission_proof(),
        )
        self.records = records_for(self.snapshot)
        self.entries = tuple(
            self.module.seal_runtime_occurrence_index_entry(
                self.release,
                subject_variant_signature=subject_variant_signature(record),
                resolved_gear_signature=self.snapshot["resolvedGearSignature"],
                effect_record=record,
                producer_identity="task5c-test-producer",
                producer_revision="task5c-source-v1",
            ).document
            for record in {
                record.content_key: record for record in self.records
            }.values()
        )

    def _store(self, responses):
        from server.exact_runtime_authority_release_store import (
            RuntimeAuthorityReleaseStore,
        )

        connection = FakeConnection(responses)
        return RuntimeAuthorityReleaseStore(lambda: connection), connection

    def _membership_row(self):
        return (
            self.context.content_key,
            self.context.canonical_bytes,
            self.release.content_key,
            self.release.canonical_bytes,
        )

    def test_admit_typed_reloads_all_documents_and_uses_only_binding_scoped_function(self):
        store, connection = self._store([self._membership_row()])

        admitted = store.admit(
            OWNER_ID,
            self.binding.content_key,
            resolver_context=self.context,
            release=self.release,
            occurrence_entries=self.entries,
        )

        self.assertEqual(admitted.resolver_context, self.context)
        self.assertEqual(admitted.release, self.release)
        call = connection.cursor_value.calls[0]
        self.assertIn("ops.websim_exact_runtime_authority_release_admit", call[0])
        self.assertEqual(call[1][0], OWNER_ID)
        self.assertEqual(call[1][1], self.binding.content_key)
        self.assertEqual(call[1][2], self.context.canonical_bytes)
        self.assertEqual(call[1][3], self.release.canonical_bytes)
        self.assertEqual(call[1][4], [entry.canonical_bytes for entry in self.entries])
        self.assertNotIn("rawProfile", str(call))

    def test_read_unique_for_binding_blocks_zero_or_multiple_release_memberships(self):
        from server.exact_runtime_authority_release_store import (
            RuntimeAuthorityReleaseIntegrityError,
        )

        for rows, expected in (([], "missing"), ([self._membership_row()] * 2, "not unique")):
            with self.subTest(expected=expected):
                store, _connection = self._store([rows])
                with self.assertRaisesRegex(
                    RuntimeAuthorityReleaseIntegrityError,
                    expected,
                ):
                    store.read_unique_for_binding(OWNER_ID, self.binding.content_key)

    def test_occurrence_read_and_effect_reload_preserve_occurrence_order(self):
        store, connection = self._store([
            list((entry.content_key, entry.canonical_bytes) for entry in self.entries),
        ])

        entries = store.read_occurrences(
            OWNER_ID,
            self.binding.content_key,
            self.release,
        )

        self.assertEqual(entries, self.entries)
        self.assertIn(
            "ops.websim_exact_runtime_authority_release_occurrences_read",
            connection.cursor_value.calls[0][0],
        )
        self.assertEqual(
            tuple(json.loads(entry.canonical_bytes)["effectRecordKey"] for entry in entries),
            tuple(json.loads(entry.canonical_bytes)["effectRecordKey"] for entry in self.entries),
        )

    def test_effect_record_reload_uses_index_keys_and_release_runtime(self):
        records_by_key = {record.content_key: record for record in self.records}
        responses = []
        for entry in self.entries:
            key = json.loads(entry.canonical_bytes)["effectRecordKey"]
            record = records_by_key[key]
            responses.append((
                record.content_key,
                record.document_kind,
                record.schema_revision,
                record.canonical_bytes,
                True,
            ))
        store, connection = self._store(responses)

        records = store.load_effect_records(self.release, self.entries)

        self.assertEqual(
            tuple(record.content_key for record in records),
            tuple(json.loads(entry.canonical_bytes)["effectRecordKey"] for entry in self.entries),
        )
        self.assertTrue(all(
            "cache.websim_canonical_documents" in call[0]
            for call in connection.cursor_value.calls
        ))

    def test_drifted_release_context_or_occurrence_bytes_fail_before_database_function(self):
        from server.exact_runtime_authority_release_store import (
            RuntimeAuthorityReleaseIntegrityError,
        )

        store, connection = self._store([])
        other_context_input = resolver_context_input(self.fixture, self.snapshot)
        other_context_input["resolverAuthorityContext"]["ruleParameters"]["task5c"] = "drift"
        wrong_context = self.module.seal_runtime_resolver_context(
            other_context_input,
        ).document

        with self.assertRaises(RuntimeAuthorityReleaseIntegrityError):
            store.admit(
                OWNER_ID,
                self.binding.content_key,
                resolver_context=wrong_context,
                release=self.release,
                occurrence_entries=self.entries,
            )
        self.assertEqual(connection.cursor_value.calls, [])


if __name__ == "__main__":
    unittest.main()

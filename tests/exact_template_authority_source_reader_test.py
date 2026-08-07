from types import SimpleNamespace
import unittest

from server.exact_template_authority_binding import (
    canonical_remote_template_source,
    seal_exact_template_authority_binding,
)
from tests.exact_template_authority_binding_test import (
    OWNER_ID,
    TEMPLATE_ID,
    admission_proof,
    remote_source,
)


AUTHORITY = {
    "gear_exact_registry_revision": admission_proof()["gearExactRegistryRevision"],
    "gear_rule_revision": admission_proof()["gearRuleRevision"],
    "resolver_revision": admission_proof()["resolverRevision"],
    "simc_runtime_revision": admission_proof()["simcRuntimeRevision"],
}


class FakePersonalStore:
    def __init__(self, source):
        self.source = source
        self.calls = []

    def load_remote_gear_template_for_exact(self, owner_id, template_id):
        self.calls.append((owner_id, template_id))
        if owner_id != OWNER_ID or template_id != TEMPLATE_ID:
            return None
        return self.source


class FakeBindingStore:
    def __init__(self, document):
        self.document = document
        self.calls = []

    def read(self, owner_id, source, **authority):
        self.calls.append((owner_id, source, authority))
        return self.document


class FakeBundleStore:
    def __init__(self, *, mismatched_key=""):
        self.mismatched_key = mismatched_key
        self.calls = []

    def load_verified_bundle(self, envelope_key, **authority):
        self.calls.append((envelope_key, authority))
        return SimpleNamespace(
            envelope=SimpleNamespace(
                content_key=self.mismatched_key or envelope_key,
            ),
        )


class ExactTemplateAuthoritySourceReaderTest(unittest.TestCase):
    def _reader(self, *, source=None, document=None, bundle_store=None):
        from server.exact_template_authority_source_reader import (
            ExactTemplateAuthoritySourceReader,
        )

        source = remote_source() if source is None else source
        if document is None:
            typed = canonical_remote_template_source(source)
            document = seal_exact_template_authority_binding(typed, admission_proof())
        personal = FakePersonalStore(source)
        bindings = FakeBindingStore(document)
        bundles = bundle_store or FakeBundleStore()
        return ExactTemplateAuthoritySourceReader(
            personal_store=personal,
            binding_store=bindings,
            bundle_store=bundles,
        ), personal, bindings, bundles

    def test_owner_scoped_replay_requires_one_binding_and_every_recorded_bundle(self):
        reader, personal, bindings, bundles = self._reader()

        result = reader.read(OWNER_ID, TEMPLATE_ID, **AUTHORITY)

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["problems"], [])
        self.assertEqual(personal.calls, [(OWNER_ID, TEMPLATE_ID)])
        self.assertEqual(len(bindings.calls), 1)
        self.assertEqual(bindings.calls[0][2], AUTHORITY)
        self.assertEqual(len(bundles.calls), len(admission_proof()["exactAuthorityBySlot"]))
        self.assertEqual(
            [row["slot"] for row in result["slotBundles"]],
            [row["slot"] for row in admission_proof()["exactAuthorityBySlot"]],
        )
        self.assertNotIn("rawString", str(result))
        self.assertNotIn("resolvedGearSignature", str(result))

    def test_missing_or_owner_isolated_source_and_missing_binding_are_literal_blocked(self):
        reader, _personal, bindings, _bundles = self._reader()

        isolated = reader.read(
            "12345678-1234-5678-1234-567812345679",
            TEMPLATE_ID,
            **AUTHORITY,
        )
        self.assertEqual(isolated["status"], "blocked")
        self.assertIn("EXACT_SOURCE_AUTHORITY_REQUIRED", isolated["problemCodes"])
        self.assertEqual(bindings.calls, [])

        missing_reader, _personal, missing_bindings, _bundles = self._reader(document=None)
        missing_bindings.document = None
        missing = missing_reader.read(OWNER_ID, TEMPLATE_ID, **AUTHORITY)
        self.assertEqual(missing["status"], "blocked")
        self.assertIn("EXACT_SOURCE_AUTHORITY_REQUIRED", missing["problemCodes"])

    def test_source_or_bundle_drift_blocks_without_registry_or_admission_fallback(self):
        changed = remote_source()
        changed["rawString"] = "changed-after-admission"
        original = canonical_remote_template_source(remote_source())
        document = seal_exact_template_authority_binding(original, admission_proof())
        reader, _personal, _bindings, bundles = self._reader(
            source=changed,
            document=document,
            bundle_store=FakeBundleStore(
                mismatched_key="exact-authority:sha256:" + "f" * 64,
            ),
        )

        source_drift = reader.read(OWNER_ID, TEMPLATE_ID, **AUTHORITY)
        self.assertEqual(source_drift["status"], "blocked")
        self.assertIn("EXACT_SOURCE_AUTHORITY_REQUIRED", source_drift["problemCodes"])
        self.assertEqual(bundles.calls, [])

        reader, _personal, _bindings, bundles = self._reader(
            bundle_store=FakeBundleStore(
                mismatched_key="exact-authority:sha256:" + "f" * 64,
            ),
        )
        bundle_drift = reader.read(OWNER_ID, TEMPLATE_ID, **AUTHORITY)
        self.assertEqual(bundle_drift["status"], "blocked")
        self.assertIn("EXACT_SOURCE_AUTHORITY_REQUIRED", bundle_drift["problemCodes"])
        self.assertEqual(len(bundles.calls), 1)

        reader, _personal, _bindings, bundles = self._reader()
        revision_drift = reader.read(
            OWNER_ID,
            TEMPLATE_ID,
            **{**AUTHORITY, "simc_runtime_revision": "simc-runtime-v2"},
        )
        self.assertEqual(revision_drift["status"], "blocked")
        self.assertIn("EXACT_SOURCE_AUTHORITY_REQUIRED", revision_drift["problemCodes"])
        self.assertEqual(bundles.calls, [])


if __name__ == "__main__":
    unittest.main()

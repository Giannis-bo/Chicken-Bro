import copy
import json
import unittest

from server import gear_resolver
from tests.gear_loadout_effect_authority_test import active_resolver_fixture, records_for


def first_pass_snapshot(*, repeated_subject=False):
    fixture = active_resolver_fixture(repeated_subject=repeated_subject)
    return fixture, gear_resolver.resolve_v2(
        fixture["intent"], fixture["authorityContext"],
    )


def dependency_vector(snapshot):
    source = snapshot["dependencyVector"]
    return {
        "seasonRevision": source["seasonRevision"],
        "gameBuild": "game-build-1",
        "gearRuleRevision": source["gearRuleRevision"],
        "resolverRevision": snapshot["v2EffectBoundary"]["resolverRevision"],
        "compilerRevision": "simc-compiler-v1",
        "workerRevision": "exact-worker-v1",
        "simcRuntimeRevision": source["simcRuntimeRevision"],
        "effectAuthorityRevision": "loadout-effect-authority-v1",
    }


def resolver_context_input(fixture, snapshot):
    vector = dependency_vector(snapshot)
    return {
        "schemaRevision": "exact-runtime-resolver-context-v1",
        "producerIdentity": "task5c-test-producer",
        "producerRevision": "task5c-source-v1",
        "seasonRevision": vector["seasonRevision"],
        "gearRuleRevision": vector["gearRuleRevision"],
        "resolverRevision": vector["resolverRevision"],
        "simcRuntimeRevision": vector["simcRuntimeRevision"],
        "resolverAuthorityContext": {
            "dependencyVector": copy.deepcopy(
                fixture["authorityContext"]["dependencyVector"],
            ),
            "ruleParameters": copy.deepcopy(
                fixture["authorityContext"]["ruleParameters"],
            ),
        },
    }


def release_input(snapshot):
    return {
        "schemaRevision": "exact-runtime-authority-release-v1",
        "producerIdentity": "task5c-test-producer",
        "producerRevision": "task5c-source-v1",
        "dependencyVector": dependency_vector(snapshot),
    }


def subject_variant_signature(record):
    return json.loads(record.canonical_bytes)["subjectVariantSignature"]


class ExactRuntimeAuthorityReleaseTest(unittest.TestCase):
    def _module(self):
        from server import exact_runtime_authority_release

        return exact_runtime_authority_release

    def _sealed_release(self):
        module = self._module()
        fixture, snapshot = first_pass_snapshot()
        context = module.seal_runtime_resolver_context(
            resolver_context_input(fixture, snapshot),
        )
        self.assertEqual(context.status, "verified")
        release = module.seal_runtime_authority_release(
            release_input(snapshot),
            resolver_context=context.document,
        )
        self.assertEqual(release.status, "verified")
        return module, fixture, snapshot, context.document, release.document

    def test_task4l_exports_ordered_subject_variant_signatures(self):
        """Would fail if release lookup copied or privately imported Task 4L signature logic."""
        from server import gear_loadout_effect_authority

        _, snapshot = first_pass_snapshot(repeated_subject=True)
        expected = tuple(
            subject_variant_signature(record)
            for record in records_for(snapshot)
        )

        self.assertEqual(
            gear_loadout_effect_authority.loadout_effect_subject_signatures(snapshot),
            expected,
        )

    def test_release_binds_full_vector_to_exact_reloaded_context(self):
        """Would fail if a release omitted, forged, or drifted from its sealed context."""
        module, _, snapshot, context, release = self._sealed_release()

        payload = module.runtime_authority_release_payload(release)
        self.assertEqual(payload["resolverContextKey"], context.content_key)
        self.assertEqual(payload["dependencyVector"], dependency_vector(snapshot))
        self.assertRegex(payload["resolverContextSha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertTrue(module.verify_runtime_resolver_context(context))
        self.assertTrue(module.verify_runtime_authority_release(release))
        self.assertEqual(
            module.reload_runtime_authority_release(
                release.canonical_bytes,
                release.content_key,
            ),
            release,
        )

        incomplete = release_input(snapshot)
        incomplete["dependencyVector"].pop("workerRevision")
        blocked = module.seal_runtime_authority_release(
            incomplete,
            resolver_context=context,
        )
        self.assertEqual(blocked.status, "blocked")
        self.assertEqual(blocked.document, None)

    def test_resolver_context_rejects_raw_profile_and_owner_identity(self):
        """Would fail if identity-bearing source material could enter a release document."""
        module = self._module()
        fixture, snapshot = first_pass_snapshot()
        raw_profile = resolver_context_input(fixture, snapshot)
        raw_profile["resolverAuthorityContext"]["rawProfile"] = "name=unsafe"
        owner_identity = resolver_context_input(fixture, snapshot)
        owner_identity["resolverAuthorityContext"]["ownerId"] = (
            "12345678-1234-5678-1234-567812345678"
        )

        for value in (raw_profile, owner_identity):
            with self.subTest(value=value["resolverAuthorityContext"]):
                blocked = module.seal_runtime_resolver_context(value)
                self.assertEqual(blocked.status, "blocked")
                self.assertEqual(blocked.document, None)

    def test_occurrence_entry_reloads_only_same_release_record_and_hash(self):
        """Would fail if occurrence bytes could name another release or effect record."""
        module, _, snapshot, _, release = self._sealed_release()
        record = records_for(snapshot)[0]

        sealed = module.seal_runtime_occurrence_index_entry(
            release,
            subject_variant_signature=subject_variant_signature(record),
            resolved_gear_signature=snapshot["resolvedGearSignature"],
            effect_record=record,
            producer_identity="task5c-test-producer",
            producer_revision="task5c-source-v1",
        )

        self.assertEqual(sealed.status, "verified")
        payload = module.runtime_occurrence_index_entry_payload(sealed.document)
        self.assertEqual(payload["runtimeAuthorityReleaseKey"], release.content_key)
        self.assertEqual(payload["effectRecordKey"], record.content_key)
        self.assertRegex(payload["effectRecordSha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertTrue(module.verify_runtime_occurrence_index_entry(sealed.document))
        self.assertEqual(
            module.reload_runtime_occurrence_index_entry(
                sealed.document.canonical_bytes,
                sealed.document.content_key,
            ),
            sealed.document,
        )

        hostile = json.loads(sealed.document.canonical_bytes)
        hostile["runtimeAuthorityReleaseKey"] = "exact-runtime-authority-release:sha256:" + "0" * 64
        with self.assertRaises(module.RuntimeAuthorityReleaseError):
            module.reload_runtime_occurrence_index_entry(
                json.dumps(hostile, sort_keys=True, separators=(",", ":")).encode("utf-8"),
                sealed.document.content_key,
            )

    def test_release_lookup_preserves_repeated_occurrence_order(self):
        """Would fail if repeated effect occurrences were deduplicated or reordered."""
        module = self._module()
        fixture, snapshot = first_pass_snapshot(repeated_subject=True)
        context = module.seal_runtime_resolver_context(
            resolver_context_input(fixture, snapshot),
        )
        release_result = module.seal_runtime_authority_release(
            release_input(snapshot),
            resolver_context=context.document,
        )
        release = release_result.document
        records = records_for(snapshot)
        indexed = {}
        for record in records:
            signature = subject_variant_signature(record)
            indexed.setdefault(
                signature,
                module.seal_runtime_occurrence_index_entry(
                    release,
                    subject_variant_signature=signature,
                    resolved_gear_signature=snapshot["resolvedGearSignature"],
                    effect_record=record,
                    producer_identity="task5c-test-producer",
                    producer_revision="task5c-source-v1",
                ).document,
            )
        records_by_key = {record.content_key: record for record in records}

        resolved = module.resolve_release_effect_records(
            release,
            resolver_snapshot=snapshot,
            index_entries=tuple(indexed.values()),
            record_loader=records_by_key.__getitem__,
        )

        self.assertEqual(
            tuple(record.content_key for record in resolved),
            tuple(record.content_key for record in records),
        )

    def test_release_lookup_rejects_first_pass_dependency_drift(self):
        """Would fail if an index match could bypass release/snapshot revision drift."""
        module, _, snapshot, _, release = self._sealed_release()
        record = records_for(snapshot)[0]
        entry = module.seal_runtime_occurrence_index_entry(
            release,
            subject_variant_signature=subject_variant_signature(record),
            resolved_gear_signature=snapshot["resolvedGearSignature"],
            effect_record=record,
            producer_identity="task5c-test-producer",
            producer_revision="task5c-source-v1",
        ).document
        drifted = copy.deepcopy(snapshot)
        drifted["dependencyVector"]["gearRuleRevision"] = "gear-rule-drifted"

        with self.assertRaisesRegex(
            module.RuntimeAuthorityReleaseError,
            "RELEASE_SNAPSHOT_VECTOR_DRIFT",
        ):
            module.resolve_release_effect_records(
                release,
                resolver_snapshot=drifted,
                index_entries=(entry,),
                record_loader={record.content_key: record}.__getitem__,
            )

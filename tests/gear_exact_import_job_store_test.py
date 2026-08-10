import copy
import json
import unittest
import uuid

from server.gear_exact_import_job_store import (
    ExactImportJobRequestError,
    GearExactImportJobStore,
    GearExactImportJobStoreIntegrityError,
    build_exact_import_job_request,
    reload_exact_import_job_request,
)


CORE_SLOTS = (
    "head", "neck", "shoulder", "back", "chest", "wrist", "hands",
    "waist", "legs", "feet", "finger1", "finger2", "trinket1",
    "trinket2", "main_hand",
)


def exact_intent():
    return {
        "schemaRevision": "exact-loadout-intent-v2",
        "authoredAgainst": {
            "seasonRevision": "season-1",
            "gameBuild": "12.0.1.12345",
        },
        "eligibilityContext": {
            "classKey": "mage",
            "specKey": "frost",
            "level": 90,
        },
        "slots": {
            slot: {
                "itemId": "1001",
                "declaredItemLevel": 700,
                "bonusIds": [],
                "context": "",
                "gemIds": [],
                "gemBonusIds": [],
                "gemItemLevels": [],
                "enchantId": "",
                "craftedStats": [],
                "embellishmentIds": [],
                "redirectedBaseStats": [],
            }
            for slot in CORE_SLOTS
        },
    }


def dependency_vector():
    return {
        "seasonRevision": "season-1",
        "gameBuild": "12.0.1.12345",
        "gearRuleRevision": "gear-rule-v1",
        "resolverRevision": "resolver-v2",
        "compilerRevision": "compiler-v2",
        "workerRevision": "exact-worker-v1",
        "simcRuntimeRevision": "simc-runtime-v1",
        "effectAuthorityRevision": "effect-authority-v1",
    }


def snapshot_reference():
    return {
        "resolvedLoadoutKey": "resolved-loadout-v2:sha256:" + "a" * 64,
        "simulationSnapshotKey": "simulation-snapshot-v2:sha256:" + "b" * 64,
        "snapshotRowHash": "sha256:" + "c" * 64,
    }


def v3_snapshot_reference():
    return {
        "resolvedLoadoutKey": "resolved-loadout-v3:sha256:" + "a" * 64,
        "simulationSnapshotKey": "simulation-snapshot-v3:sha256:" + "b" * 64,
        "snapshotRowHash": "sha256:" + "c" * 64,
        "runtimeAuthorityReleaseKey": "exact-runtime-authority-release:sha256:" + "d" * 64,
        "resolverContextKey": "exact-runtime-resolver-context:sha256:" + "e" * 64,
    }


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, _kind, _value, _traceback):
        return False

    def execute(self, statement, parameters=()):
        self.calls.append((" ".join(statement.split()), parameters))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class FakeConnection:
    def __init__(self, rows):
        self.cursor_value = FakeCursor(rows)

    def __enter__(self):
        return self

    def __exit__(self, _kind, _value, _traceback):
        return False

    def cursor(self):
        return self.cursor_value


class GearExactImportRequestTest(unittest.TestCase):
    def test_builder_seals_v3_release_bound_snapshot_reference_without_changing_v1_v2(self):
        reference = v3_snapshot_reference()
        request = build_exact_import_job_request(
            exact_intent(),
            dependency_vector(),
            snapshot_reference=reference,
        )

        self.assertEqual(request.request_json["schemaRevision"], "exact-import-job-request-v3")
        self.assertEqual(
            {key: request.request_json[key] for key in reference},
            reference,
        )
        self.assertEqual(
            reload_exact_import_job_request(
                request.request_key,
                request.canonical_bytes,
                copy.deepcopy(request.request_json),
            ),
            request,
        )
        rejected = dict(reference)
        rejected["resolvedLoadoutKey"] = "resolved-loadout-v2:sha256:" + "a" * 64
        with self.assertRaises(ExactImportJobRequestError):
            build_exact_import_job_request(
                exact_intent(), dependency_vector(), snapshot_reference=rejected,
            )
    def test_builder_emits_exact_schema_keys_canonical_bytes_and_fixed_hash(self):
        request = build_exact_import_job_request(exact_intent(), dependency_vector())

        self.assertEqual(
            set(request.request_json),
            {"schemaRevision", "exactLoadoutIntent", "dependencyVector"},
        )
        self.assertEqual(
            set(request.request_json["dependencyVector"]),
            {
                "seasonRevision", "gameBuild", "gearRuleRevision",
                "resolverRevision", "compilerRevision", "workerRevision",
                "simcRuntimeRevision", "effectAuthorityRevision",
            },
        )
        self.assertEqual(
            request.request_key,
            "exact-import-request:sha256:"
            "a2d56b35733d52b4a45e12f847ec471bee491c4ef9df148b339723d8d0ba2b50",
        )
        self.assertEqual(len(request.canonical_bytes), 3655)
        self.assertEqual(json.loads(request.canonical_bytes), request.request_json)
        self.assertNotIn(b" ", request.canonical_bytes)
        self.assertTrue(request.canonical_bytes.startswith(b'{"dependencyVector":'))

    def test_builder_seals_v2_snapshot_reference_into_canonical_bytes_and_key(self):
        reference = snapshot_reference()
        request = build_exact_import_job_request(
            exact_intent(),
            dependency_vector(),
            snapshot_reference=reference,
        )

        self.assertEqual(
            request.request_json["schemaRevision"],
            "exact-import-job-request-v2",
        )
        self.assertEqual(
            set(request.request_json),
            {
                "schemaRevision", "exactLoadoutIntent", "dependencyVector",
                "resolvedLoadoutKey", "simulationSnapshotKey", "snapshotRowHash",
            },
        )
        self.assertEqual(
            {
                key: request.request_json[key]
                for key in reference
            },
            reference,
        )
        self.assertIn(
            b'"resolvedLoadoutKey":"resolved-loadout-v2:sha256:',
            request.canonical_bytes,
        )
        self.assertEqual(
            reload_exact_import_job_request(
                request.request_key,
                request.canonical_bytes,
                copy.deepcopy(request.request_json),
            ),
            request,
        )

        drifted = dict(reference)
        drifted["snapshotRowHash"] = "sha256:" + "d" * 64
        changed = build_exact_import_job_request(
            exact_intent(),
            dependency_vector(),
            snapshot_reference=drifted,
        )
        self.assertNotEqual(changed.request_key, request.request_key)
        self.assertNotEqual(changed.canonical_bytes, request.canonical_bytes)

    def test_array_containing_canonical_request_is_accepted_before_sealing(self):
        request = build_exact_import_job_request(exact_intent(), dependency_vector())

        head = request.request_json["exactLoadoutIntent"]["slots"]["head"]
        self.assertEqual(head["bonusIds"], [])
        self.assertEqual(head["gemIds"], [])
        self.assertEqual(head["craftedStats"], [])

    def test_nested_sensitive_identity_and_raw_fields_are_rejected_before_sealing(self):
        for forbidden in (
            "rawProfile", "rawString", "playerName", "characterName",
            "realm", "server",
        ):
            with self.subTest(forbidden=forbidden):
                intent = exact_intent()
                intent["slots"]["head"]["nested"] = {
                    "safe": [{forbidden: "must-never-persist"}],
                }
                with self.assertRaisesRegex(ExactImportJobRequestError, forbidden):
                    build_exact_import_job_request(intent, dependency_vector())

    def test_builder_rejects_noncanonical_intent_and_dependency_key_drift(self):
        intent = exact_intent()
        intent["eligibilityContext"]["classKey"] = " mage"
        with self.assertRaises(ExactImportJobRequestError):
            build_exact_import_job_request(intent, dependency_vector())

        dependencies = dependency_vector()
        dependencies["catalogRevision"] = "must-not-bind-catalog"
        with self.assertRaisesRegex(ExactImportJobRequestError, "dependencyVector"):
            build_exact_import_job_request(exact_intent(), dependencies)

    def test_reload_recomputes_bytes_json_and_request_key(self):
        request = build_exact_import_job_request(exact_intent(), dependency_vector())
        self.assertEqual(
            reload_exact_import_job_request(
                request.request_key,
                request.canonical_bytes,
                copy.deepcopy(request.request_json),
            ),
            request,
        )
        with self.assertRaises(GearExactImportJobStoreIntegrityError):
            reload_exact_import_job_request(
                request.request_key,
                request.canonical_bytes + b" ",
                request.request_json,
            )
        with self.assertRaises(GearExactImportJobStoreIntegrityError):
            reload_exact_import_job_request(
                "exact-import-request:sha256:" + "0" * 64,
                request.canonical_bytes,
                request.request_json,
            )


class GearExactImportJobStoreTest(unittest.TestCase):
    def setUp(self):
        self.request = build_exact_import_job_request(exact_intent(), dependency_vector())

    def store(self, rows):
        connection = FakeConnection(rows)
        return GearExactImportJobStore(lambda: connection), connection

    def test_enqueue_maps_reuse_owner_isolation_and_failed_cooldown_without_raw_payloads(self):
        store, connection = self.store([
            (7, self.request.request_key, "pending", True, None),
            (8, self.request.request_key, "pending", False, None),
            (9, self.request.request_key, "failed", True, "2026-08-06T12:15:00+00:00"),
        ])
        owner_a = "sha256:" + "a" * 64
        owner_b = "sha256:" + "b" * 64

        reused = store.enqueue(owner_a, self.request)
        isolated = store.enqueue(owner_b, self.request)
        cooldown = store.enqueue(owner_a, self.request)

        self.assertEqual((reused["jobId"], reused["reused"]), (7, True))
        self.assertEqual((isolated["jobId"], isolated["reused"]), (8, False))
        self.assertEqual(
            (cooldown["status"], cooldown["cooldownUntil"]),
            ("failed", "2026-08-06T12:15:00+00:00"),
        )
        calls = connection.cursor_value.calls
        self.assertEqual(len(calls), 3)
        self.assertTrue(all("ops.websim_exact_enqueue" in call[0] for call in calls))
        self.assertEqual(calls[0][1][0], owner_a)
        self.assertEqual(calls[1][1][0], owner_b)
        self.assertEqual(calls[0][1][1], self.request.canonical_bytes)
        self.assertNotIn("must-never-persist", str(calls))

    def test_claim_reloads_typed_request_and_rejects_byte_drift(self):
        token = uuid.UUID("12345678-1234-5678-1234-567812345678")
        valid_row = (
            11,
            self.request.request_key,
            self.request.canonical_bytes,
            copy.deepcopy(self.request.request_json),
            token,
            "2026-08-06T12:00:30+00:00",
        )
        store, _connection = self.store([valid_row])
        claimed = store.claim_next("worker-a", "exact-worker-v1", "simc-runtime-v1")
        self.assertEqual(claimed["jobId"], 11)
        self.assertEqual(claimed["lockToken"], str(token))
        self.assertEqual(claimed["request"], self.request)

        drifted = list(valid_row)
        drifted[2] = self.request.canonical_bytes + b" "
        store, _connection = self.store([tuple(drifted)])
        with self.assertRaises(GearExactImportJobStoreIntegrityError):
            store.claim_next("worker-a", "exact-worker-v1", "simc-runtime-v1")

    def test_wrong_or_expired_cas_returns_no_row(self):
        store, connection = self.store([None, None])
        token = uuid.UUID("12345678-1234-5678-1234-567812345678")
        self.assertIsNone(store.heartbeat(11, token))
        self.assertIsNone(
            store.terminalize(
                11,
                token,
                terminal_status="failed",
                terminal_classification="internal_error",
                result_json=None,
                problem_json={"code": "SAFE_FAILURE"},
                catalog_status="unknown",
            )
        )
        self.assertIn("ops.websim_exact_heartbeat", connection.cursor_value.calls[0][0])
        self.assertIn("ops.websim_exact_terminalize", connection.cursor_value.calls[1][0])


if __name__ == "__main__":
    unittest.main()

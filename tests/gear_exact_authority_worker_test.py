import copy
import unittest

from server.gear_exact_authority_worker import (
    WorkerConfigurationError,
    WorkerRoleError,
    establish_exact_worker_role,
    process_claimed_job,
    snapshot_bound_processor,
    worker_database_url_from_env,
)
from tests.gear_exact_import_job_store_test import (
    dependency_vector,
    exact_intent,
    snapshot_reference,
)
from server.gear_exact_import_job_store import build_exact_import_job_request


class RoleCursor:
    def __init__(self, role_row):
        self.role_row = role_row
        self.events = []

    def __enter__(self):
        return self

    def __exit__(self, _kind, _value, _traceback):
        return False

    def execute(self, statement, parameters=()):
        self.events.append((" ".join(statement.split()), parameters))

    def fetchone(self):
        return self.role_row


class RoleConnection:
    def __init__(self, role_row):
        self.cursor_value = RoleCursor(role_row)
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def close(self):
        self.closed = True


class TerminalStore:
    def __init__(self, terminal_result):
        self.terminal_result = terminal_result
        self.calls = []

    def terminalize(self, *args, **kwargs):
        self.calls.append((args, copy.deepcopy(kwargs)))
        return copy.deepcopy(self.terminal_result)


class SnapshotStore:
    def __init__(self, snapshot, bound):
        self.snapshot = copy.deepcopy(snapshot)
        self.bound = copy.deepcopy(bound)
        self.calls = []

    def load_snapshot(self, key, *, include_result=True):
        self.calls.append(("load_snapshot", key, include_result))
        return copy.deepcopy(self.snapshot)

    def bind_result(self, key, result):
        self.calls.append(("bind_result", key, copy.deepcopy(result)))
        return copy.deepcopy(self.bound)


def least_privileged_role_row(session_user="wow_exact_worker_login"):
    return (
        session_user,
        "wow_exact_worker",
        True,
        True,
        True,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    )


class GearExactAuthorityWorkerTest(unittest.TestCase):
    def test_worker_accepts_only_the_dedicated_dsn_and_refuses_public_database_url(self):
        dedicated = "postgresql://worker-login:redacted@candidate/exact"
        self.assertEqual(
            worker_database_url_from_env({"WOW_EXACT_WORKER_DATABASE_URL": dedicated}),
            dedicated,
        )
        with self.assertRaises(WorkerConfigurationError):
            worker_database_url_from_env({})
        with self.assertRaisesRegex(WorkerConfigurationError, "WOW_DATABASE_URL"):
            worker_database_url_from_env({"WOW_DATABASE_URL": "postgresql://app:redacted@candidate/exact"})
        with self.assertRaisesRegex(WorkerConfigurationError, "WOW_DATABASE_URL"):
            worker_database_url_from_env({
                "WOW_DATABASE_URL": "postgresql://app:redacted@candidate/exact",
                "WOW_EXACT_WORKER_DATABASE_URL": dedicated,
            })

    def test_connection_sets_role_before_validating_login_membership_and_current_user(self):
        connection = RoleConnection(least_privileged_role_row())
        establish_exact_worker_role(connection)

        events = connection.cursor_value.events
        self.assertEqual(events[0][0], "SET ROLE wow_exact_worker")
        self.assertIn("session_user", events[1][0])
        self.assertIn("current_user", events[1][0])
        self.assertIn("pg_catalog.pg_has_role", events[1][0])
        for privilege in (
            "rolcanlogin", "rolinherit", "rolsuper", "rolcreatedb",
            "rolcreaterole", "rolreplication", "rolbypassrls",
        ):
            with self.subTest(privilege=privilege):
                self.assertIn(privilege, events[1][0])
        self.assertIn("'wow_app'", events[1][0])
        self.assertIn("'wow_migrator'", events[1][0])

    def test_connection_fails_closed_for_wrong_role_membership_or_login_boundary(self):
        invalid_rows = []
        for label, index, value in (
            ("wrong-current-user", 1, "worker-login"),
            ("not-member", 2, False),
            ("nologin", 3, False),
            ("noinherit", 4, False),
            ("superuser", 5, True),
            ("createdb", 6, True),
            ("createrole", 7, True),
            ("replication", 8, True),
            ("bypassrls", 9, True),
            ("group-login", 10, True),
            ("group-superuser", 11, True),
            ("group-createdb", 12, True),
            ("group-createrole", 13, True),
            ("group-replication", 14, True),
            ("group-bypassrls", 15, True),
            ("wow-app-is-member", 16, True),
            ("wow-migrator-is-member", 17, True),
        ):
            row = list(least_privileged_role_row())
            row[index] = value
            invalid_rows.append((label, tuple(row)))
        invalid_rows.extend(
            (label, least_privileged_role_row(session_user))
            for label, session_user in (
                ("app-login", "wow_app"),
                ("migrator-login", "wow_migrator"),
                ("group-login", "wow_exact_worker"),
            )
        )

        for label, row in invalid_rows:
            with self.subTest(label=label):
                connection = RoleConnection(row)
                with self.assertRaises(WorkerRoleError):
                    establish_exact_worker_role(connection)

    def test_valid_outcome_terminalizes_with_the_claim_token(self):
        request = build_exact_import_job_request(exact_intent(), dependency_vector())
        job = {
            "jobId": 11,
            "requestKey": request.request_key,
            "request": request,
            "lockToken": "12345678-1234-5678-1234-567812345678",
        }
        store = TerminalStore({"jobId": 11, "status": "blocked"})
        seen = []

        outcome = process_claimed_job(
            copy.deepcopy(job),
            store=store,
            processor=lambda typed_request: seen.append(typed_request) or {
                "terminalStatus": "blocked",
                "terminalClassification": "incomplete",
                "resultJson": None,
                "problemJson": {"code": "AUTHORITY_INCOMPLETE"},
                "catalogStatus": "partial",
            },
        )

        self.assertEqual(seen, [request])
        self.assertEqual(outcome, {"status": "blocked", "code": "EXACT_IMPORT_BLOCKED"})
        self.assertEqual(store.calls[0][0], (11, job["lockToken"]))
        self.assertEqual(store.calls[0][1]["terminal_classification"], "incomplete")

    def test_wrong_or_expired_token_abandons_without_claiming_success(self):
        request = build_exact_import_job_request(exact_intent(), dependency_vector())
        store = TerminalStore(None)
        outcome = process_claimed_job(
            {
                "jobId": 11,
                "requestKey": request.request_key,
                "request": request,
                "lockToken": "12345678-1234-5678-1234-567812345678",
            },
            store=store,
            processor=lambda _request: {
                "terminalStatus": "resolved",
                "terminalClassification": "resolved",
                "resultJson": {"status": "resolved"},
                "problemJson": None,
                "catalogStatus": "complete",
            },
        )
        self.assertEqual(
            outcome,
            {"status": "abandoned", "code": "EXACT_IMPORT_LEASE_LOST"},
        )

    def test_processor_failure_is_bounded_and_never_logs_or_persists_exception_text(self):
        request = build_exact_import_job_request(exact_intent(), dependency_vector())
        store = TerminalStore({"jobId": 11, "status": "failed"})

        outcome = process_claimed_job(
            {
                "jobId": 11,
                "requestKey": request.request_key,
                "request": request,
                "lockToken": "12345678-1234-5678-1234-567812345678",
            },
            store=store,
            processor=lambda _request: (_ for _ in ()).throw(
                RuntimeError("private playerName and rawProfile must not escape"),
            ),
        )

        self.assertEqual(outcome["code"], "EXACT_IMPORT_INTERNAL_ERROR")
        persisted = store.calls[0][1]
        self.assertEqual(persisted["problem_json"], {"code": "EXACT_IMPORT_INTERNAL_ERROR"})
        self.assertNotIn("playerName", str(persisted))
        self.assertNotIn("rawProfile", str(persisted))

    def test_snapshot_bound_processor_reloads_only_the_sealed_v2_snapshot_before_runner(self):
        reference = snapshot_reference()
        request = build_exact_import_job_request(
            exact_intent(),
            dependency_vector(),
            snapshot_reference=reference,
        )
        snapshot = {
            "schemaRevision": "simulation-snapshot-v2",
            "status": "ready",
            "simulationSnapshotKey": reference["simulationSnapshotKey"],
            "resolvedLoadoutKey": reference["resolvedLoadoutKey"],
            "rowHash": reference["snapshotRowHash"],
            "simcRuntimeRevision": dependency_vector()["simcRuntimeRevision"],
        }
        bound = {
            **snapshot,
            "status": "executed",
            "snapshotRowHash": reference["snapshotRowHash"],
            "resultIdentity": "simc-result:sha256:" + "d" * 64,
            "result": {
                "resultIdentity": "simc-result:sha256:" + "d" * 64,
                "status": "completed",
            },
        }
        snapshots = SnapshotStore(snapshot, bound)
        seen = []

        outcome = snapshot_bound_processor(
            snapshot_store=snapshots,
            simc_runtime_revision=dependency_vector()["simcRuntimeRevision"],
            runner=lambda sealed_snapshot: seen.append(sealed_snapshot) or bound["result"],
        )(request)

        self.assertEqual(outcome, {
            "terminalStatus": "resolved",
            "terminalClassification": "resolved",
            "resultJson": {
                "resultIdentity": "simc-result:sha256:" + "d" * 64,
                "status": "resolved",
                "simulationSnapshotKey": reference["simulationSnapshotKey"],
            },
            "problemJson": None,
            "catalogStatus": "unknown",
        })
        self.assertEqual(
            snapshots.calls,
            [
                ("load_snapshot", reference["simulationSnapshotKey"], False),
                ("bind_result", reference["simulationSnapshotKey"], bound["result"]),
            ],
        )
        self.assertEqual(seen, [snapshot])

    def test_snapshot_bound_processor_rejects_v1_without_snapshot_discovery_or_runner(self):
        snapshots = SnapshotStore({}, {})
        ran = []
        processor = snapshot_bound_processor(
            snapshot_store=snapshots,
            simc_runtime_revision=dependency_vector()["simcRuntimeRevision"],
            runner=lambda snapshot: ran.append(snapshot),
        )

        outcome = processor(build_exact_import_job_request(
            exact_intent(),
            dependency_vector(),
        ))

        self.assertEqual(outcome, {
            "terminalStatus": "unsupported",
            "terminalClassification": "runtime_gap",
            "resultJson": None,
            "problemJson": {"code": "EXACT_IMPORT_REQUEST_V1_UNSUPPORTED"},
            "catalogStatus": "unknown",
        })
        self.assertEqual(snapshots.calls, [])
        self.assertEqual(ran, [])

    def test_snapshot_bound_processor_fails_closed_for_missing_identity_or_runtime_drift(self):
        reference = snapshot_reference()
        runtime = dependency_vector()["simcRuntimeRevision"]
        request = build_exact_import_job_request(
            exact_intent(),
            dependency_vector(),
            snapshot_reference=reference,
        )
        base_snapshot = {
            "schemaRevision": "simulation-snapshot-v2",
            "status": "ready",
            "simulationSnapshotKey": reference["simulationSnapshotKey"],
            "resolvedLoadoutKey": reference["resolvedLoadoutKey"],
            "rowHash": reference["snapshotRowHash"],
            "simcRuntimeRevision": runtime,
        }
        cases = (
            ("missing", None, "blocked", "EXACT_IMPORT_SNAPSHOT_UNAVAILABLE"),
            ("not-ready", {"status": "blocked"}, "blocked", "EXACT_IMPORT_SNAPSHOT_REFERENCE_MISMATCH"),
            ("key", {"simulationSnapshotKey": "simulation-snapshot-v2:sha256:" + "e" * 64}, "blocked", "EXACT_IMPORT_SNAPSHOT_REFERENCE_MISMATCH"),
            ("loadout", {"resolvedLoadoutKey": "resolved-loadout-v2:sha256:" + "e" * 64}, "blocked", "EXACT_IMPORT_SNAPSHOT_REFERENCE_MISMATCH"),
            ("row-hash", {"rowHash": "sha256:" + "e" * 64}, "blocked", "EXACT_IMPORT_SNAPSHOT_REFERENCE_MISMATCH"),
            ("runtime", {"simcRuntimeRevision": "simc-runtime-other"}, "unsupported", "EXACT_IMPORT_RUNTIME_MISMATCH"),
        )
        for label, mutation, terminal_status, code in cases:
            with self.subTest(label=label):
                snapshot = {} if mutation is None else {**base_snapshot, **mutation}
                snapshots = SnapshotStore(snapshot, {})
                ran = []
                outcome = snapshot_bound_processor(
                    snapshot_store=snapshots,
                    simc_runtime_revision=runtime,
                    runner=lambda candidate: ran.append(candidate),
                )(request)
                self.assertEqual(outcome["terminalStatus"], terminal_status)
                self.assertEqual(outcome["problemJson"], {"code": code})
                self.assertEqual(
                    snapshots.calls,
                    [("load_snapshot", reference["simulationSnapshotKey"], False)],
                )
                self.assertEqual(ran, [])

    def test_snapshot_bound_processor_never_reports_resolved_for_a_bound_failed_runner_result(self):
        reference = snapshot_reference()
        runtime = dependency_vector()["simcRuntimeRevision"]
        request = build_exact_import_job_request(
            exact_intent(),
            dependency_vector(),
            snapshot_reference=reference,
        )
        snapshot = {
            "schemaRevision": "simulation-snapshot-v2",
            "status": "ready",
            "simulationSnapshotKey": reference["simulationSnapshotKey"],
            "resolvedLoadoutKey": reference["resolvedLoadoutKey"],
            "rowHash": reference["snapshotRowHash"],
            "simcRuntimeRevision": runtime,
        }
        failed_result = {
            "resultIdentity": "simc-result:sha256:" + "d" * 64,
            "status": "failed",
        }
        snapshots = SnapshotStore(snapshot, {
            **snapshot,
            "status": "executed",
            "snapshotRowHash": reference["snapshotRowHash"],
            "resultIdentity": failed_result["resultIdentity"],
            "result": failed_result,
        })

        outcome = snapshot_bound_processor(
            snapshot_store=snapshots,
            simc_runtime_revision=runtime,
            runner=lambda _sealed_snapshot: failed_result,
        )(request)

        self.assertEqual(outcome, {
            "terminalStatus": "failed",
            "terminalClassification": "internal_error",
            "resultJson": None,
            "problemJson": {"code": "EXACT_IMPORT_RUNNER_FAILED"},
            "catalogStatus": "unknown",
        })


if __name__ == "__main__":
    unittest.main()

import contextlib
import io
import unittest

from server.migrations.product.postgres_legacy import (
    PostgresMigrationTarget,
    build_parser,
    normalize_legacy_rows,
    validate_local_app_dsn,
)


class PostgresLegacyMigrationTest(unittest.TestCase):
    def test_normalizes_only_the_reviewed_mini_app_identity_context(self):
        rows = {
            "identity.users": [{
                "id": "user-a",
                "display_name": "A",
                "status": "active",
                "created_at": "2026-09-03T00:00:00Z",
                "updated_at": "2026-09-03T00:00:00Z",
            }],
            "identity.user_identities": [
                {
                    "id": "identity-a",
                    "user_id": "user-a",
                    "provider": "wechat_openid",
                    "provider_subject": "openid-a",
                    "profile_json": {"nickname": "A"},
                    "created_at": "2026-09-03T00:00:00Z",
                    "updated_at": "2026-09-03T00:00:00Z",
                },
                {
                    "id": "identity-other-app",
                    "user_id": "user-a",
                    "provider": "wechat_mini",
                    "app_context": "wx-other",
                    "provider_subject": "openid-other",
                    "profile_json": {},
                    "created_at": "2026-09-03T00:00:00Z",
                    "updated_at": "2026-09-03T00:00:00Z",
                },
            ],
        }

        records = normalize_legacy_rows(rows, approved_app_context="wx-reviewed")
        identities = [record for record in records if record["table"] == "identity.user_identities"]

        self.assertEqual(identities[0]["row"]["provider"], "wechat_mini")
        self.assertEqual(identities[0]["row"]["app_context"], "wx-reviewed")
        self.assertEqual(identities[0]["row"]["provider_subject"], "openid-a")
        self.assertEqual(identities[1]["row"]["app_context"], "")
        self.assertNotIn("openid-a", str(identities[0]["pk"]))

    def test_derives_legacy_chat_run_links_without_copying_trace_payloads_or_errors(self):
        rows = {
            "app.chickenbro_sessions": [{
                "id": "session-a", "user_id": "user-a", "title": "A", "status": "active",
                "created_at": "2026-09-03T00:01:00Z", "updated_at": "2026-09-03T00:04:00Z",
            }],
            "app.chickenbro_messages": [
                {
                    "id": "message-user", "session_id": "session-a", "user_id": "user-a",
                    "role": "user", "content": "question",
                    "payload_json": {"clientMessageId": "client-a", "secret": "drop-me"},
                    "agent_job_id": None, "created_at": "2026-09-03T00:02:00Z",
                },
                {
                    "id": "message-assistant", "session_id": "session-a", "user_id": "user-a",
                    "role": "assistant", "content": "answer", "payload_json": {"raw": "drop-me"},
                    "agent_job_id": "job-a", "created_at": "2026-09-03T00:03:00Z",
                },
            ],
            "app.agent_jobs": [{
                "id": "job-a", "user_id": "user-a", "session_id": "session-a",
                "job_type": "chickenbro", "status": "succeeded",
                "request_json": {"clientMessageId": "client-a"},
                "last_error": "credential-shaped raw failure",
                "started_at": "2026-09-03T00:02:01Z", "finished_at": "2026-09-03T00:03:00Z",
                "created_at": "2026-09-03T00:02:01Z", "updated_at": "2026-09-03T00:03:00Z",
            }],
            "app.chickenbro_agent_traces": [{
                "id": "trace-a", "user_id": "user-a", "session_id": "session-a",
                "user_message_id": "message-user", "agent_job_id": "job-a",
                "runtime_version": "codex:reviewed", "payload_json": {"thoughts": "drop-me"},
                "created_at": "2026-09-03T00:03:00Z",
            }],
        }

        records = normalize_legacy_rows(rows, approved_app_context="wx-reviewed")
        messages = [record["row"] for record in records if record["table"] == "app.chickenbro_messages"]
        run = next(record["row"] for record in records if record["table"] == "app.agent_jobs")

        self.assertEqual(messages[0]["client_message_id"], "client-a")
        self.assertNotIn("payload_json", messages[0])
        self.assertEqual(run["user_message_id"], "message-user")
        self.assertEqual(run["assistant_message_id"], "message-assistant")
        self.assertEqual(run["runtime_revision"], "codex:reviewed")
        self.assertEqual(run["public_error_code"], "")
        self.assertNotIn("bounded_context_json", run)
        self.assertNotIn("result_json", run)
        self.assertNotIn("app.chickenbro_agent_traces", {record["table"] for record in records})
        self.assertNotIn("drop-me", str(records))
        self.assertNotIn("credential-shaped", str(records))

    def test_preserves_only_explicit_legacy_simc_execution_evidence(self):
        rows = {
            "app.simulator_tasks": [{
                "id": "task-a", "user_id": "user-a", "mode": "simc", "status": "succeeded",
                "request_json": {"source": {}}, "analysis_json": {"exitCode": 0},
                "summary_json": {"metricName": "dps", "metricValue": 1.0},
                "locked_by": "worker-a", "attempt": 1,
                "queued_at": "2026-09-03T00:00:00Z", "started_at": "2026-09-03T00:00:01Z",
                "finished_at": "2026-09-03T00:00:02Z", "created_at": "2026-09-03T00:00:00Z",
                "updated_at": "2026-09-03T00:00:02Z", "last_error": "drop-me",
            }],
        }

        records = normalize_legacy_rows(rows, approved_app_context="wx-reviewed")
        task = records[0]["row"]

        self.assertEqual(task["exit_code"], 0)
        self.assertNotIn("analysis_json", task)
        self.assertNotIn("last_error", task)
        self.assertNotIn("drop-me", str(task))

    def test_requires_a_non_empty_reviewed_app_context(self):
        with self.assertRaisesRegex(ValueError, "approved_app_context"):
            normalize_legacy_rows({}, approved_app_context="")

    def test_non_chickenbro_agent_job_cannot_be_derived_as_a_formal_run(self):
        rows = {
            "app.agent_jobs": [{
                "id": "job-other", "user_id": "user-a", "session_id": "session-a",
                "job_type": "unrelated", "status": "succeeded", "request_json": {},
                "started_at": "2026-09-03T00:00:00Z", "finished_at": "2026-09-03T00:00:01Z",
                "created_at": "2026-09-03T00:00:00Z", "updated_at": "2026-09-03T00:00:01Z",
            }],
            "app.chickenbro_agent_traces": [{
                "id": "trace-other", "agent_job_id": "job-other", "user_message_id": "message-user",
                "runtime_version": "codex:other", "created_at": "2026-09-03T00:00:01Z",
            }],
            "app.chickenbro_messages": [{
                "id": "message-assistant", "agent_job_id": "job-other", "role": "assistant",
                "session_id": "session-a", "user_id": "user-a", "content": "not Chickenbro",
                "created_at": "2026-09-03T00:00:01Z",
            }],
        }

        records = normalize_legacy_rows(rows, approved_app_context="wx-reviewed")
        run = next(record["row"] for record in records if record["table"] == "app.agent_jobs")

        self.assertEqual(run["status"], "not_migrated")
        self.assertNotIn("runtime_revision", run)
        self.assertNotIn("assistant_message_id", run)

    def test_postgres_target_reads_psycopg_named_description_columns(self):
        class Column:
            def __init__(self, name):
                self.name = name

        class Cursor:
            description = [Column("id"), Column("display_name"), Column("status"), Column("created_at"), Column("updated_at")]

            @staticmethod
            def fetchone():
                return ("user-a", "A", "active", "created", "updated")

        class Connection:
            @staticmethod
            def execute(_query, _params):
                return Cursor()

        row = PostgresMigrationTarget(Connection()).get("identity.users", "user-a")

        self.assertEqual(row, {
            "id": "user-a",
            "display_name": "A",
            "status": "active",
            "created_at": "created",
            "updated_at": "updated",
        })

    def test_cli_cannot_override_the_snapshot_captured_watermark(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            build_parser().parse_args([
                "--mode", "full",
                "--expected-target-database", "chickenbro_candidate",
                "--captured-watermark", "2099-01-01T00:00:00Z",
                "--report-path", "/tmp/report.json",
            ])

    def test_migration_dsn_is_bound_to_the_local_wow_app_socket_identity(self):
        self.assertEqual(
            validate_local_app_dsn(
                "postgresql://wow_app@127.0.0.1:5432/wow_test",
                "wow_test",
            ),
            "wow_test",
        )
        for dsn in (
            "postgresql://wow_app@10.0.0.5:5432/wow_test",
            "postgresql://wow_app:secret@127.0.0.1:5432/wow_test",
            "postgresql://postgres@127.0.0.1:5432/wow_test",
            "postgresql://wow_app@127.0.0.1:6432/wow_test",
            "postgresql://wow_app@127.0.0.1:5432/wow_test?sslmode=disable",
        ):
            with self.subTest(dsn=dsn), self.assertRaisesRegex(ValueError, "reviewed local wow_app"):
                validate_local_app_dsn(dsn, "wow_test")


if __name__ == "__main__":
    unittest.main()

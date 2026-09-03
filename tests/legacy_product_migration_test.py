import json
import unittest
from copy import deepcopy
from pathlib import Path

from server.migrations.product.migrate_legacy import (
    InMemoryMigrationTarget,
    MigrationError,
    MigrationWatermark,
    classify_record,
    migrate_delta,
    migrate_full,
    stable_target_uuid,
)
from server.migrations.product.reconcile_legacy import reconcile


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "legacy_product_migration.json"


def fixture_records():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["records"]


def direct_formal_records():
    timestamp = "2026-09-03T01:00:00Z"
    assistant_timestamp = "2026-09-03T01:00:00.001Z"
    return [
        {
            "table": "identity.users", "pk": {"id": "direct-user"}, "updated_at": timestamp,
            "row": {"id": "direct-user", "display_name": "Direct", "status": "active", "created_at": timestamp, "updated_at": timestamp},
        },
        {
            "table": "identity.user_identities", "pk": {"id": "direct-identity"}, "updated_at": timestamp,
            "row": {"id": "direct-identity", "user_id": "direct-user", "provider": "wechat_mini", "app_context": "wx-approved-mini", "provider_subject": "direct-openid", "union_id": None, "profile_json": {}, "created_at": timestamp, "updated_at": timestamp},
        },
        {
            "table": "chat.conversations", "pk": {"id": "direct-conversation"}, "updated_at": timestamp,
            "row": {"id": "direct-conversation", "user_id": "direct-user", "title": "Direct chat", "status": "active", "created_at": timestamp, "updated_at": timestamp},
        },
        {
            "table": "chat.messages", "pk": {"id": "direct-user-message"}, "updated_at": timestamp,
            "row": {"id": "direct-user-message", "conversation_id": "direct-conversation", "user_id": "direct-user", "role": "user", "content": "question", "client_message_id": "direct-client-message", "created_at": timestamp},
        },
        {
            "table": "chat.messages", "pk": {"id": "direct-assistant-message"}, "updated_at": timestamp,
            "row": {"id": "direct-assistant-message", "conversation_id": "direct-conversation", "user_id": "direct-user", "role": "assistant", "content": "answer", "client_message_id": None, "created_at": assistant_timestamp},
        },
        {
            "table": "chat.agent_runs", "pk": {"id": "direct-run"}, "updated_at": timestamp,
            "row": {"id": "direct-run", "user_id": "direct-user", "conversation_id": "direct-conversation", "user_message_id": "direct-user-message", "assistant_message_id": "direct-assistant-message", "status": "succeeded", "runtime_revision": "codex:fixture", "public_error_code": "", "idempotency_key": "direct-run-key", "started_at": timestamp, "finished_at": timestamp},
        },
        {
            "table": "simc.source_snapshots", "pk": {"id": "direct-snapshot"}, "updated_at": timestamp,
            "row": {"id": "direct-snapshot", "user_id": "direct-user", "provider": "raiderio", "source_url": "https://raider.io/characters/us/illidan/direct", "source_key": "us:illidan:direct", "revision": 1, "readiness": "READY_FOR_SIMC", "snapshot_json": {}, "provenance_json": {"sourceRevision": "direct:1"}, "raw_sha256": "a" * 64, "fetched_at": timestamp, "created_at": timestamp},
        },
        {
            "table": "simc.simulation_jobs", "pk": {"id": "direct-job"}, "updated_at": timestamp,
            "row": {"id": "direct-job", "user_id": "direct-user", "snapshot_id": "direct-snapshot", "scenario_hash": "b" * 64, "compiler_revision": "compiler:direct", "runtime_revision": "simc:direct", "idempotency_key": "direct-job-key", "status": "succeeded", "public_error_code": "", "created_at": timestamp, "updated_at": timestamp},
        },
        {
            "table": "simc.simulation_attempts", "pk": {"id": "direct-attempt"}, "updated_at": timestamp,
            "row": {"id": "direct-attempt", "job_id": "direct-job", "user_id": "direct-user", "attempt_number": 1, "worker_id": "worker:direct", "started_at": timestamp, "finished_at": timestamp, "exit_code": 0, "diagnostic": ""},
        },
        {
            "table": "simc.simulation_results", "pk": {"id": "direct-result"}, "updated_at": timestamp,
            "row": {"id": "direct-result", "job_id": "direct-job", "user_id": "direct-user", "profile_sha256": "c" * 64, "result_json": {"metricName": "dps", "metricValue": 9876.5}, "primary_metric_name": "dps", "primary_metric_value": 9876.5, "compiler_revision": "compiler:direct", "runtime_revision": "simc:direct", "provenance_json": {"snapshotId": stable_target_uuid("simc.source_snapshots", {"id": "direct-snapshot"}), "sourceRevision": "direct:1", "sourceRawSha256": "a" * 64, "profileSha256": "c" * 64, "compilerRevision": "compiler:direct", "runtimeRevision": "simc:direct", "scenarioHash": "b" * 64}, "created_at": timestamp},
        },
    ]


class LegacyProductMigrationTest(unittest.TestCase):
    def test_prototype_auth_and_unrelated_records_are_rejected(self):
        self.assertEqual(
            classify_record({"table": "identity.prototype_sessions"}).reason,
            "PROTOTYPE_NOT_MIGRATED",
        )
        self.assertEqual(
            classify_record({"table": "identity.auth_sessions"}).reason,
            "AUTH_SESSION_NOT_MIGRATED",
        )
        self.assertEqual(
            classify_record({"table": "identity.auth_tokens"}).reason,
            "AUTH_SESSION_NOT_MIGRATED",
        )
        self.assertEqual(
            classify_record({"table": "content.articles"}).reason,
            "DOMAIN_NOT_MIGRATED",
        )

    def test_classifier_has_hashed_source_identity_and_deterministic_uuid5(self):
        record = fixture_records()[2]
        first = classify_record(record)
        second = classify_record(deepcopy(record))

        self.assertEqual(first.status, "accepted")
        self.assertEqual(first.target_table, "chat.conversations")
        self.assertEqual(first.source_primary_key_hash, second.source_primary_key_hash)
        self.assertRegex(first.source_primary_key_hash, r"^[0-9a-f]{64}$")
        self.assertEqual(first.target_id, second.target_id)
        self.assertEqual(
            first.target_id,
            stable_target_uuid("app.chickenbro_sessions", record["pk"]),
        )
        self.assertEqual(
            classify_record({
                "table": "app.simulator_tasks",
                "pk": {"id": "classifier-simc"},
                "row": {"mode": "simcraft_template"},
            }).status,
            "accepted",
        )

    def test_whitelisted_record_requires_an_explicit_non_empty_source_primary_key(self):
        decision = classify_record({
            "table": "chat.conversations",
            "row": {
                "id": "row-id-is-not-an-envelope-primary-key",
                "user_id": "direct-user",
            },
        })

        self.assertEqual(decision.status, "rejected")
        self.assertEqual(decision.reason, "SOURCE_PRIMARY_KEY_REQUIRED")
        self.assertIsNone(decision.target_id)

    def test_owner_bound_chat_is_idempotent_and_public_report_is_redacted(self):
        records = fixture_records()
        target = InMemoryMigrationTarget()
        watermark = MigrationWatermark.through("2026-09-03T00:06:00Z")

        first = migrate_full(records, target, watermark)
        second = migrate_full(records, target, watermark)

        self.assertEqual(first.accepted_hash, second.accepted_hash)
        self.assertEqual(first.rejected_hash, second.rejected_hash)
        self.assertEqual(target.count("identity.users"), 1)
        self.assertEqual(target.count("identity.user_identities"), 1)
        self.assertEqual(target.count("chat.conversations"), 1)
        self.assertEqual(target.count("chat.messages"), 2)
        self.assertEqual(first.accepted_by_source_table["app.chickenbro_messages"], 2)
        self.assertEqual(first.reason_counts["AUTH_SESSION_NOT_MIGRATED"], 1)
        self.assertEqual(first.reason_counts["PROTOTYPE_NOT_MIGRATED"], 3)
        self.assertEqual(first.reason_counts["TERMINAL_STATE_REQUIRED"], 1)
        self.assertEqual(target.count("ops.audit_events"), first.accepted_count)

        public_json = json.dumps(first.to_public_dict(), sort_keys=True)
        self.assertNotIn("fixture-openid-a", public_json)
        self.assertNotIn("legacy-user-a", public_json)
        self.assertNotIn("dddddddddddddddd", public_json)

    def test_target_unique_constraints_stop_duplicate_client_message_ids(self):
        records = direct_formal_records()
        timestamp = "2026-09-03T01:00:00Z"
        records.append({
            "table": "chat.messages", "pk": {"id": "duplicate-client-message"}, "updated_at": timestamp,
            "row": {
                "id": "duplicate-client-message",
                "conversation_id": "direct-conversation",
                "user_id": "direct-user",
                "role": "user",
                "content": "duplicate retry",
                "client_message_id": "direct-client-message",
                "created_at": "2026-09-03T01:00:00.0005Z",
            },
        })

        with self.assertRaisesRegex(MigrationError, "TARGET_UNIQUE_CONFLICT:chat.messages:user_client_message"):
            migrate_full(
                records,
                InMemoryMigrationTarget(),
                MigrationWatermark.through("2026-09-03T01:00:01Z"),
            )

    def test_ambiguous_legacy_agent_run_is_rejected_without_dropping_messages(self):
        records = fixture_records()
        records.append({
            "table": "app.agent_jobs",
            "pk": {"id": "ambiguous-legacy-run"},
            "updated_at": "2026-09-03T00:04:00Z",
            "row": {
                "id": "ambiguous-legacy-run",
                "user_id": "legacy-user-a",
                "session_id": "legacy-chat-a",
                "user_message_id": "legacy-message-a1",
                "assistant_message_id": "legacy-message-a2",
                "status": "succeeded",
                "runtime_revision": "codex:reviewed",
                "public_error_code": "",
                "started_at": "2026-09-03T00:02:01Z",
                "finished_at": "2026-09-03T00:03:00Z",
                "migration_rejection_reason": "AMBIGUOUS_AGENT_RUN",
            },
        })

        target = InMemoryMigrationTarget()
        report = migrate_full(
            records,
            target,
            MigrationWatermark.through("2026-09-03T00:06:00Z"),
        )

        self.assertEqual(report.reason_counts.get("AMBIGUOUS_AGENT_RUN"), 1)
        self.assertEqual(report.accepted_by_source_table.get("app.agent_jobs", 0), 0)
        self.assertEqual(target.count("chat.messages"), 2)

    def test_rerun_cannot_rebind_an_existing_identity_mapping(self):
        records = fixture_records()
        target = InMemoryMigrationTarget()
        watermark = MigrationWatermark.through("2026-09-03T00:06:00Z")
        migrate_full(records, target, watermark)
        identity = next(record for record in records if record["pk"].get("id") == "legacy-identity-a")
        identity["row"]["provider_subject"] = "different-openid"

        with self.assertRaisesRegex(MigrationError, "TARGET_OWNER_CONFLICT:identity.user_identities"):
            migrate_full(records, target, watermark)

    def test_identity_profile_and_simc_result_keep_only_required_product_fields(self):
        records = fixture_records()
        identity = next(record for record in records if record["pk"].get("id") == "legacy-identity-a")
        identity["row"]["profile_json"]["accessToken"] = "must-not-migrate"
        task = next(record for record in records if record["pk"].get("id") == "legacy-simc-a")
        task["row"]["summary_json"]["resultJson"]["providerPayload"] = {"raw": "must-not-migrate"}
        target = InMemoryMigrationTarget()
        migrate_full(
            records,
            target,
            MigrationWatermark.through("2026-09-03T00:06:00Z"),
        )

        profile = target.rows("identity.user_identities")[0]["profile_json"]
        result_json = target.rows("simc.simulation_results")[0]["result_json"]
        self.assertEqual(profile, {"nickname": "Captain A"})
        self.assertEqual(set(result_json), {"metricName", "metricValue", "provenance"})
        self.assertNotIn("must-not-migrate", json.dumps(target.rows("simc.simulation_results")))

    def test_succeeded_legacy_simc_expands_to_semantic_target_records(self):
        target = InMemoryMigrationTarget()
        report = migrate_full(
            fixture_records(),
            target,
            MigrationWatermark.through("2026-09-03T00:06:00Z"),
        )

        self.assertEqual(report.accepted_by_source_table["app.simulator_tasks"], 1)
        self.assertEqual(target.count("simc.source_snapshots"), 1)
        self.assertEqual(target.count("simc.simulation_jobs"), 1)
        self.assertEqual(target.count("simc.simulation_attempts"), 1)
        self.assertEqual(target.count("simc.simulation_results"), 1)
        result = target.rows("simc.simulation_results")[0]
        self.assertEqual(result["primary_metric_name"], "dps")
        self.assertEqual(result["primary_metric_value"], 12345.67)
        self.assertEqual(result["profile_sha256"], "c" * 64)
        self.assertEqual(result["provenance_json"]["scenarioHash"], "b" * 64)

    def test_legacy_completed_simcraft_template_normalizes_to_succeeded(self):
        records = fixture_records()
        task = next(record for record in records if record["pk"].get("id") == "legacy-simc-a")
        task["row"]["mode"] = "simcraft_template"
        task["row"]["status"] = "completed"
        target = InMemoryMigrationTarget()
        report = migrate_full(
            records,
            target,
            MigrationWatermark.through("2026-09-03T00:06:00Z"),
        )

        self.assertEqual(report.accepted_by_source_table["app.simulator_tasks"], 1)
        self.assertEqual(target.rows("simc.simulation_jobs")[0]["status"], "succeeded")

    def test_legacy_simc_does_not_trust_a_provider_label_with_an_unapproved_host(self):
        records = fixture_records()
        task = next(record for record in records if record["pk"].get("id") == "legacy-simc-a")
        task["row"]["request_json"]["source"]["sourceUrl"] = "https://evil.example/characters/us/illidan/captain-a"
        target = InMemoryMigrationTarget()
        report = migrate_full(
            records,
            target,
            MigrationWatermark.through("2026-09-03T00:06:00Z"),
        )

        self.assertEqual(report.reason_counts["INVALID_SOURCE"], 1)
        self.assertEqual(target.count("simc.simulation_jobs"), 0)

    def test_legacy_simc_requires_real_source_revision_instead_of_a_guessed_default(self):
        records = fixture_records()
        task = next(record for record in records if record["pk"].get("id") == "legacy-simc-a")
        task["row"]["request_json"]["source"].pop("sourceRevision")
        target = InMemoryMigrationTarget()
        report = migrate_full(
            records,
            target,
            MigrationWatermark.through("2026-09-03T00:06:00Z"),
        )

        self.assertEqual(report.reason_counts["REQUIRED_INPUT_MISSING"], 1)
        self.assertEqual(target.count("simc.simulation_results"), 0)

    def test_formal_chat_and_simc_tables_migrate_in_dependency_order(self):
        target = InMemoryMigrationTarget()
        report = migrate_full(
            direct_formal_records(),
            target,
            MigrationWatermark.through("2026-09-03T01:00:01Z"),
        )

        self.assertEqual(report.rejected_count, 0)
        self.assertEqual(report.accepted_count, 10)
        self.assertEqual(target.count("chat.agent_runs"), 1)
        self.assertEqual(target.count("simc.simulation_results"), 1)

    def test_duplicate_mini_identity_subject_is_not_used_to_merge_accounts(self):
        records = direct_formal_records()[:2]
        timestamp = "2026-09-03T01:00:00Z"
        records.extend([
            {
                "table": "identity.users", "pk": {"id": "duplicate-user"}, "updated_at": timestamp,
                "row": {"id": "duplicate-user", "display_name": "Duplicate", "status": "active", "created_at": timestamp, "updated_at": timestamp},
            },
            {
                "table": "identity.user_identities", "pk": {"id": "duplicate-identity"}, "updated_at": timestamp,
                "row": {"id": "duplicate-identity", "user_id": "duplicate-user", "provider": "wechat_mini", "app_context": "wx-approved-mini", "provider_subject": "direct-openid", "profile_json": {}, "created_at": timestamp, "updated_at": timestamp},
            },
        ])
        target = InMemoryMigrationTarget()
        report = migrate_full(
            records,
            target,
            MigrationWatermark.through("2026-09-03T01:00:01Z"),
        )

        self.assertEqual(report.reason_counts["AMBIGUOUS_IDENTITY_MAPPING"], 2)
        self.assertEqual(target.count("identity.user_identities"), 0)
        self.assertEqual(target.count("identity.users"), 0)

    def test_assistant_message_before_any_user_message_is_rejected(self):
        records = direct_formal_records()
        user_message = next(record for record in records if record["pk"].get("id") == "direct-user-message")
        assistant_message = next(record for record in records if record["pk"].get("id") == "direct-assistant-message")
        user_message["row"]["created_at"] = "2026-09-03T01:00:00.002Z"
        assistant_message["row"]["created_at"] = "2026-09-03T01:00:00.001Z"
        target = InMemoryMigrationTarget()
        report = migrate_full(
            records,
            target,
            MigrationWatermark.through("2026-09-03T01:00:01Z"),
        )

        self.assertEqual(report.reason_counts["MESSAGE_ORDER_INVALID"], 1)
        self.assertEqual(target.count("chat.messages"), 1)

    def test_agent_run_messages_must_belong_to_the_run_conversation(self):
        records = direct_formal_records()
        timestamp = "2026-09-03T01:00:00Z"
        records.extend([
            {
                "table": "chat.conversations", "pk": {"id": "other-conversation"}, "updated_at": timestamp,
                "row": {"id": "other-conversation", "user_id": "direct-user", "title": "Other", "status": "active", "created_at": timestamp, "updated_at": timestamp},
            },
            {
                "table": "chat.messages", "pk": {"id": "other-user-message"}, "updated_at": timestamp,
                "row": {"id": "other-user-message", "conversation_id": "other-conversation", "user_id": "direct-user", "role": "user", "content": "other question", "client_message_id": "other-user-message", "created_at": "2026-09-03T01:00:00.002Z"},
            },
            {
                "table": "chat.messages", "pk": {"id": "other-assistant-message"}, "updated_at": timestamp,
                "row": {"id": "other-assistant-message", "conversation_id": "other-conversation", "user_id": "direct-user", "role": "assistant", "content": "other answer", "client_message_id": None, "created_at": "2026-09-03T01:00:00.003Z"},
            },
        ])
        run = next(record for record in records if record["table"] == "chat.agent_runs")
        run["row"]["assistant_message_id"] = "other-assistant-message"
        target = InMemoryMigrationTarget()
        report = migrate_full(
            records,
            target,
            MigrationWatermark.through("2026-09-03T01:00:01Z"),
        )

        self.assertEqual(report.reason_counts["RUN_MESSAGE_CONVERSATION_MISMATCH"], 1)
        self.assertEqual(target.count("chat.agent_runs"), 0)

    def test_simc_attempts_and_legacy_results_do_not_fabricate_worker_or_exit_code(self):
        direct_records = direct_formal_records()
        direct_attempt = next(record for record in direct_records if record["table"] == "simc.simulation_attempts")
        direct_attempt["row"].pop("worker_id")
        direct_target = InMemoryMigrationTarget()
        direct_report = migrate_full(
            direct_records,
            direct_target,
            MigrationWatermark.through("2026-09-03T01:00:01Z"),
        )

        legacy_records = fixture_records()
        legacy_task = next(record for record in legacy_records if record["pk"].get("id") == "legacy-simc-a")
        legacy_task["row"].pop("locked_by")
        legacy_task["row"].pop("exit_code")
        legacy_target = InMemoryMigrationTarget()
        legacy_report = migrate_full(
            legacy_records,
            legacy_target,
            MigrationWatermark.through("2026-09-03T00:06:00Z"),
        )

        self.assertEqual(direct_report.reason_counts["REQUIRED_INPUT_MISSING"], 1)
        self.assertEqual(direct_target.count("simc.simulation_attempts"), 0)
        self.assertEqual(legacy_report.reason_counts["REQUIRED_INPUT_MISSING"], 1)
        self.assertEqual(legacy_target.count("simc.simulation_attempts"), 0)
        self.assertEqual(legacy_target.count("simc.simulation_results"), 0)

    def test_successful_simc_history_requires_a_ready_source_snapshot(self):
        direct_records = direct_formal_records()
        direct_snapshot = next(record for record in direct_records if record["table"] == "simc.source_snapshots")
        direct_snapshot["row"]["readiness"] = "INCOMPLETE_FOR_SIMC"
        direct_target = InMemoryMigrationTarget()
        direct_report = migrate_full(
            direct_records,
            direct_target,
            MigrationWatermark.through("2026-09-03T01:00:01Z"),
        )

        legacy_records = fixture_records()
        legacy_task = next(record for record in legacy_records if record["pk"].get("id") == "legacy-simc-a")
        legacy_task["row"]["request_json"]["source"]["readiness"] = "INCOMPLETE_FOR_SIMC"
        legacy_target = InMemoryMigrationTarget()
        legacy_report = migrate_full(
            legacy_records,
            legacy_target,
            MigrationWatermark.through("2026-09-03T00:06:00Z"),
        )

        self.assertEqual(direct_report.reason_counts["SEMANTIC_SOURCE_NOT_READY"], 1)
        self.assertEqual(direct_target.count("simc.simulation_jobs"), 0)
        self.assertEqual(legacy_report.reason_counts["SEMANTIC_SOURCE_NOT_READY"], 1)
        self.assertEqual(legacy_target.count("simc.simulation_results"), 0)

    def test_direct_succeeded_simc_job_requires_one_matching_semantic_result(self):
        records = [
            record
            for record in direct_formal_records()
            if record["table"] != "simc.simulation_results"
        ]
        target = InMemoryMigrationTarget()
        report = migrate_full(
            records,
            target,
            MigrationWatermark.through("2026-09-03T01:00:01Z"),
        )

        self.assertEqual(report.reason_counts["SEMANTIC_RESULT_REQUIRED"], 1)
        self.assertEqual(target.count("simc.simulation_jobs"), 0)
        self.assertEqual(target.count("simc.simulation_attempts"), 0)

    def test_cross_owner_parent_and_mismatched_result_provenance_are_rejected(self):
        records = direct_formal_records()
        timestamp = "2026-09-03T01:00:00Z"
        records.extend([
            {
                "table": "identity.users", "pk": {"id": "other-user"}, "updated_at": timestamp,
                "row": {"id": "other-user", "display_name": "Other", "status": "active", "created_at": timestamp, "updated_at": timestamp},
            },
            {
                "table": "identity.user_identities", "pk": {"id": "other-identity"}, "updated_at": timestamp,
                "row": {"id": "other-identity", "user_id": "other-user", "provider": "wechat_mini", "app_context": "wx-approved-mini", "provider_subject": "other-openid", "profile_json": {}, "created_at": timestamp, "updated_at": timestamp},
            },
            {
                "table": "simc.simulation_jobs", "pk": {"id": "cross-owner-job"}, "updated_at": timestamp,
                "row": {"id": "cross-owner-job", "user_id": "other-user", "snapshot_id": "direct-snapshot", "scenario_hash": "d" * 64, "compiler_revision": "compiler:direct", "runtime_revision": "simc:direct", "idempotency_key": "cross-owner-job", "status": "failed", "public_error_code": "SIMC_FAILED", "created_at": timestamp, "updated_at": timestamp},
            },
        ])
        direct_result = next(record for record in records if record["table"] == "simc.simulation_results")
        direct_result["row"]["provenance_json"]["scenarioHash"] = "d" * 64
        target = InMemoryMigrationTarget()
        report = migrate_full(
            records,
            target,
            MigrationWatermark.through("2026-09-03T01:00:01Z"),
        )

        self.assertEqual(report.reason_counts["OWNER_PARENT_MISMATCH"], 1)
        self.assertEqual(report.reason_counts["RESULT_PROVENANCE_MISMATCH"], 2)
        self.assertEqual(target.count("simc.simulation_jobs"), 0)
        self.assertEqual(target.count("simc.simulation_results"), 0)

    def test_direct_result_columns_and_result_json_must_describe_the_same_metric(self):
        records = direct_formal_records()
        direct_result = next(record for record in records if record["table"] == "simc.simulation_results")
        direct_result["row"]["result_json"]["metricValue"] = 1.0
        target = InMemoryMigrationTarget()
        report = migrate_full(
            records,
            target,
            MigrationWatermark.through("2026-09-03T01:00:01Z"),
        )

        self.assertEqual(report.reason_counts["SEMANTIC_RESULT_REQUIRED"], 2)
        self.assertEqual(target.count("simc.simulation_results"), 0)

    def test_full_watermark_does_not_use_a_future_identity(self):
        records = direct_formal_records()[:2]
        records[0]["updated_at"] = "2026-09-03T02:00:00Z"
        records[0]["row"]["updated_at"] = "2026-09-03T02:00:00Z"
        records[1]["updated_at"] = "2026-09-03T02:10:00Z"
        records[1]["row"]["updated_at"] = "2026-09-03T02:10:00Z"
        target = InMemoryMigrationTarget()
        report = migrate_full(
            records,
            target,
            MigrationWatermark.through("2026-09-03T02:05:00Z"),
        )

        self.assertEqual(report.accepted_count, 0)
        self.assertEqual(report.reason_counts["FORMAL_IDENTITY_REQUIRED"], 1)
        self.assertEqual(target.count("identity.users"), 0)

    def test_missing_owner_and_non_terminal_records_are_not_migrated(self):
        records = fixture_records()
        records.append({
            "table": "app.chickenbro_messages",
            "pk": {"id": "orphan-message"},
            "updated_at": "2026-09-03T00:05:30Z",
            "row": {
                "id": "orphan-message",
                "session_id": "missing-session",
                "user_id": "missing-user",
                "role": "user",
                "content": "orphan",
                "created_at": "2026-09-03T00:05:30Z",
            },
        })
        target = InMemoryMigrationTarget()
        report = migrate_full(
            records,
            target,
            MigrationWatermark.through("2026-09-03T00:06:00Z"),
        )

        self.assertEqual(report.reason_counts["OWNER_NOT_MIGRATED"], 1)
        self.assertEqual(report.reason_counts["TERMINAL_STATE_REQUIRED"], 1)
        self.assertEqual(target.count("chat.messages"), 2)
        self.assertEqual(target.count("simc.simulation_jobs"), 1)

    def test_delta_uses_exclusive_updated_at_and_source_id_watermark(self):
        base = fixture_records()[:3]
        same_time = "2026-09-03T00:02:00Z"
        messages = [
            {
                "table": "app.chickenbro_messages",
                "pk": {"id": message_id},
                "updated_at": same_time,
                "row": {
                    "id": message_id,
                    "session_id": "legacy-chat-a",
                    "user_id": "legacy-user-a",
                    "role": role,
                    "content": content,
                    "created_at": same_time,
                },
            }
            for message_id, role, content in [
                ("message-001", "user", "first"),
                ("message-002", "assistant", "second"),
                ("message-003", "user", "third"),
            ]
        ]
        records = base + messages
        target = InMemoryMigrationTarget()
        full_through = MigrationWatermark.at(same_time, {"id": "message-001"})
        delta_through = MigrationWatermark.at(same_time, {"id": "message-003"})

        full = migrate_full(records, target, full_through)
        delta = migrate_delta(records, target, full_through, delta_through)

        self.assertEqual(full.accepted_by_source_table["app.chickenbro_messages"], 1)
        self.assertEqual(delta.accepted_by_source_table["app.chickenbro_messages"], 2)
        self.assertEqual(target.count("chat.messages"), 3)
        self.assertEqual(delta.from_watermark_hash, full_through.public_hash())
        self.assertEqual(delta.through_watermark_hash, delta_through.public_hash())

    def test_reconciliation_checks_mapping_owner_order_and_semantic_hashes(self):
        records = fixture_records()
        target = InMemoryMigrationTarget()
        report = migrate_full(
            records,
            target,
            MigrationWatermark.through("2026-09-03T00:06:00Z"),
        )

        clean = reconcile(records, target, report)
        self.assertEqual(clean.status, "matched")
        self.assertEqual(clean.owner_violation_count, 0)
        self.assertEqual(clean.mapping_missing_count, 0)
        self.assertEqual(clean.message_order_mismatch_count, 0)
        self.assertEqual(clean.simc_semantic_mismatch_count, 0)

        message = target.rows("chat.messages")[0]
        target.replace_for_test("chat.messages", message["id"], {**message, "user_id": stable_target_uuid("identity.users", {"id": "different"})})
        diverged = reconcile(records, target, report)
        self.assertEqual(diverged.status, "diverged")
        self.assertGreater(diverged.owner_violation_count, 0)

    def test_reconciliation_treats_run_message_roles_and_conversation_as_ownership_contracts(self):
        records = direct_formal_records()
        target = InMemoryMigrationTarget()
        report = migrate_full(
            records,
            target,
            MigrationWatermark.through("2026-09-03T01:00:01Z"),
        )
        run = target.rows("chat.agent_runs")[0]
        user_message = target.get("chat.messages", run["user_message_id"])
        self.assertIsNotNone(user_message)
        target.replace_for_test(
            "chat.messages",
            run["user_message_id"],
            {**user_message, "role": "assistant"},
        )

        diverged = reconcile(records, target, report)
        self.assertEqual(diverged.status, "diverged")
        self.assertGreater(diverged.owner_violation_count, 0)


if __name__ == "__main__":
    unittest.main()

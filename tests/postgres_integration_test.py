import os
import hashlib
import inspect
import json
from pathlib import Path
from queue import Queue
import re
import shutil
import subprocess
import time
from types import SimpleNamespace
from threading import Event
import unittest
from concurrent.futures import ThreadPoolExecutor


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    ROOT / "server" / "migrations" / "postgres" / "0001_identity_app_content_cache_knowledge_analytics_ops.sql",
    ROOT / "server" / "migrations" / "postgres" / "0002_runtime_privileges.sql",
    ROOT / "server" / "migrations" / "postgres" / "0003_build_template_config_hash_unique.sql",
    ROOT / "server" / "migrations" / "postgres" / "0004_chickenbro_runtime_fields.sql",
    ROOT / "server" / "migrations" / "postgres" / "0005_content_runtime_fields.sql",
)

ALL_MIGRATIONS = tuple(sorted(
    (ROOT / "server" / "migrations" / "postgres").glob("[0-9][0-9][0-9][0-9]_*.sql")
))
TASK_3A_MIGRATIONS = tuple(
    migration for migration in ALL_MIGRATIONS
    if migration.name <= "0030_websim_exact_authority_bundle.sql"
)
TASK_3B_MIGRATIONS = tuple(
    migration for migration in ALL_MIGRATIONS
    if migration.name <= "0031_websim_exact_snapshot_v2.sql"
)
TASK_3B_BASELINE_MIGRATIONS = TASK_3B_MIGRATIONS[:-1]
TASK_3A_RUN_ID = os.environ.get("WOW_PG_TEST_RUN_ID_0030", "")
TASK_3A_FRESH_DSN = os.environ.get("WOW_PG_TEST_DSN_FRESH_0030", "")
TASK_3A_UPGRADE_DSN = os.environ.get("WOW_PG_TEST_DSN_UPGRADE_0030", "")
TASK_3A_HISTORICAL_RUN_IDS = frozenset({
    "t3a2608050955",
    "t3a260805111623",
    "t3a260805113656",
    "t3a260805120026",
    "t3a260805125812",
    "t3a260805142130",
    "t3a260805160003",
    "t3a260805163536",
})
TASK_3A_FORBIDDEN_RUN_IDS = TASK_3A_HISTORICAL_RUN_IDS
TASK_3B_FORBIDDEN_RUN_IDS = TASK_3A_HISTORICAL_RUN_IDS | frozenset({
    "t3b260806175347",
    "t3b260806191719",
    "t3b260806191950",
    "t3b260806194346",
})
TASK_3B_RUN_ID = os.environ.get("WOW_PG_TEST_RUN_ID_0031", "")
TASK_3B_FRESH_DSN = os.environ.get("WOW_PG_TEST_DSN_FRESH_0031", "")
TASK_3B_UPGRADE_DSN = os.environ.get("WOW_PG_TEST_DSN_UPGRADE_0031", "")
TASK_4W_MIGRATIONS = tuple(
    migration for migration in ALL_MIGRATIONS
    if migration.name <= "0032_websim_exact_import_jobs.sql"
)
TASK_4W_BASELINE_MIGRATIONS = TASK_4W_MIGRATIONS[:-1]
TASK_5C_MIGRATIONS = tuple(
    migration for migration in ALL_MIGRATIONS
    if migration.name <= "0035_websim_exact_runtime_authority_release.sql"
)
TASK_5C_BASELINE_MIGRATIONS = TASK_5C_MIGRATIONS[:-1]
TASK_4W_RUN_ID = os.environ.get("WOW_PG_TEST_RUN_ID_0032", "")
TASK_4W_FRESH_DSN = os.environ.get("WOW_PG_TEST_DSN_FRESH_0032", "")
TASK_4W_UPGRADE_DSN = os.environ.get("WOW_PG_TEST_DSN_UPGRADE_0032", "")
TASK_4W_MIGRATOR_DSN = os.environ.get("WOW_PG_TEST_DSN_MIGRATOR_0032", "")
TASK_4W_APP_DSN = os.environ.get("WOW_PG_TEST_DSN_APP_0032", "")
TASK_4W_WORKER_DSN = os.environ.get("WOW_PG_TEST_DSN_WORKER_0032", "")
TASK_5C_RUN_ID = os.environ.get("WOW_PG_TEST_RUN_ID_0035", "")
TASK_5C_FRESH_DSN = os.environ.get("WOW_PG_TEST_DSN_FRESH_0035", "")
TASK_5C_UPGRADE_DSN = os.environ.get("WOW_PG_TEST_DSN_UPGRADE_0035", "")
TASK_5C_MIGRATOR_DSN = os.environ.get("WOW_PG_TEST_DSN_MIGRATOR_0035", "")
TASK_5C_APP_DSN = os.environ.get("WOW_PG_TEST_DSN_APP_0035", "")
TASK_5C_WORKER_DSN = os.environ.get("WOW_PG_TEST_DSN_WORKER_0035", "")


def validate_task3a_candidate_run_id(run_id):
    if (
        type(run_id) is not str
        or re.fullmatch(r"[a-z0-9]{8,32}", run_id) is None
        or run_id in TASK_3A_FORBIDDEN_RUN_IDS
    ):
        raise ValueError("invalid or forbidden Task 3A candidate run id")
    return run_id


def validate_task3b_candidate_run_id(run_id):
    if (
        type(run_id) is not str
        or re.fullmatch(r"[a-z0-9]{8,32}", run_id) is None
        or run_id in TASK_3B_FORBIDDEN_RUN_IDS
    ):
        raise ValueError("invalid or reused Task 3B candidate run id")
    return run_id


def task3b_candidate_configured(run_id, fresh_dsn, upgrade_dsn, psql_path):
    """Candidate DDL is opt-in; this harness never provisions databases."""
    return bool(run_id and fresh_dsn and upgrade_dsn and psql_path)


def validate_task4w_candidate_run_id(run_id):
    if type(run_id) is not str or re.fullmatch(r"[a-z0-9]{8,32}", run_id) is None:
        raise ValueError("invalid Task 4W candidate run id")
    return run_id


def validate_task5c_candidate_run_id(run_id):
    if type(run_id) is not str or re.fullmatch(r"[a-z0-9]{8,32}", run_id) is None:
        raise ValueError("invalid Task 5C candidate run id")
    return run_id


def task4w_candidate_configured(
    run_id,
    fresh_dsn,
    upgrade_dsn,
    migrator_dsn,
    app_dsn,
    worker_dsn,
    psql_path,
):
    """Cloud-only candidate is inert until every explicit role/path input exists."""
    values = (
        run_id, fresh_dsn, upgrade_dsn, migrator_dsn, app_dsn, worker_dsn,
        psql_path,
    )
    if not all(values):
        return False
    return (
        fresh_dsn != upgrade_dsn
        and len({migrator_dsn, app_dsn, worker_dsn}) == 3
    )


def task5c_candidate_configured(
    run_id,
    fresh_dsn,
    upgrade_dsn,
    migrator_dsn,
    app_dsn,
    worker_dsn,
    psql_path,
):
    """Task 5C stays inert until every disposable role/path input is explicit."""
    values = (
        run_id, fresh_dsn, upgrade_dsn, migrator_dsn, app_dsn, worker_dsn,
        psql_path,
    )
    if not all(values):
        return False
    return (
        fresh_dsn != upgrade_dsn
        and len({migrator_dsn, app_dsn, worker_dsn}) == 3
    )


TASK_5C_VERIFIED_CHECKS = (
    "exact_disposable_database_identity_and_empty_preflight",
    "fresh_migrations_0001_through_0035",
    "upgrade_migrations_0001_through_0034_then_0035",
    "release_membership_zero_multiple_and_occurrence_fail_closed",
    "v3_snapshot_job_and_worker_processor_contract",
    "v1_v2_nonexecution_provider_disable_and_no_async_backflow",
    "runtime_release_function_acl_boundary",
)


def build_task5c_candidate_attestation(
    *,
    run_id,
    fresh_identity,
    upgrade_identity,
    git_identity,
):
    """Return the sole redacted receipt for a completed 0035 candidate."""
    validate_task5c_candidate_run_id(run_id)
    expected_fresh = (
        f"wow_exact_first_fresh_test_{run_id}",
        f"wow_exact_first_disposable:{run_id}:fresh",
    )
    expected_upgrade = (
        f"wow_exact_first_upgrade_test_{run_id}",
        f"wow_exact_first_disposable:{run_id}:upgrade",
    )
    if fresh_identity != expected_fresh or upgrade_identity != expected_upgrade:
        raise ValueError("Task 5C candidate database identity drift")
    if (
        type(git_identity) is not tuple
        or len(git_identity) != 3
        or re.fullmatch(r"[0-9a-f]{40}", git_identity[0] or "") is None
        or re.fullmatch(r"[0-9a-f]{40}", git_identity[1] or "") is None
        or re.fullmatch(r"[0-9a-f]{64}", git_identity[2] or "") is None
    ):
        raise ValueError("Task 5C candidate Git identity drift")
    return json.dumps({
        "schemaVersion": "task5c-candidate-attestation-v1",
        "task": "equipment-simulator-exact-first-task5c-runtime-authority-release",
        "runId": run_id,
        "passed": True,
        "freshDatabase": {
            "name": fresh_identity[0],
            "comment": fresh_identity[1],
        },
        "upgradeDatabase": {
            "name": upgrade_identity[0],
            "comment": upgrade_identity[1],
        },
        "gitCommit": git_identity[0],
        "gitTree": git_identity[1],
        "migration0035Sha256": git_identity[2],
        "verifiedChecks": list(TASK_5C_VERIFIED_CHECKS),
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def task4w_candidate_has_schema_qualified_coalesce(source):
    return re.search(
        r"\bpg_catalog\s*\.\s*coalesce\s*\(",
        source,
        flags=re.IGNORECASE,
    ) is not None


if TASK_3A_RUN_ID:
    validate_task3a_candidate_run_id(TASK_3A_RUN_ID)
if TASK_3B_RUN_ID:
    validate_task3b_candidate_run_id(TASK_3B_RUN_ID)
if TASK_4W_RUN_ID:
    validate_task4w_candidate_run_id(TASK_4W_RUN_ID)
if TASK_5C_RUN_ID:
    validate_task5c_candidate_run_id(TASK_5C_RUN_ID)
TASK_3A_CANDIDATE_CONFIGURED = bool(
    TASK_3A_RUN_ID
    and TASK_3A_FRESH_DSN
    and TASK_3A_UPGRADE_DSN
    and shutil.which("psql")
)
TASK_3B_CANDIDATE_CONFIGURED = task3b_candidate_configured(
    TASK_3B_RUN_ID,
    TASK_3B_FRESH_DSN,
    TASK_3B_UPGRADE_DSN,
    shutil.which("psql"),
)
TASK_4W_CANDIDATE_CONFIGURED = task4w_candidate_configured(
    TASK_4W_RUN_ID,
    TASK_4W_FRESH_DSN,
    TASK_4W_UPGRADE_DSN,
    TASK_4W_MIGRATOR_DSN,
    TASK_4W_APP_DSN,
    TASK_4W_WORKER_DSN,
    shutil.which("psql"),
)
TASK_5C_CANDIDATE_CONFIGURED = task5c_candidate_configured(
    TASK_5C_RUN_ID,
    TASK_5C_FRESH_DSN,
    TASK_5C_UPGRADE_DSN,
    TASK_5C_MIGRATOR_DSN,
    TASK_5C_APP_DSN,
    TASK_5C_WORKER_DSN,
    shutil.which("psql"),
)
TASK_3A_VERIFIED_CHECKS = (
    "exact_disposable_database_identity_and_empty_preflight",
    "fresh_migrations_0001_through_0030",
    "upgrade_migrations_0001_through_0029_seed_then_0030",
    "v1_full_row_schema_table_default_acl_and_grant_parity",
    "canonical_hash_and_json_projection",
    "six_kind_schema_prefix_closed_matrix",
    "seven_exact_foreign_keys",
    "binding_trigger_first_missing_effect_documents_and_bundle_bindings",
    "three_table_update_delete_truncate_immutability",
    "wow_app_explicit_and_effective_select_only_acl",
    "whole_bundle_typed_readback",
    "absent_row_reverse_shared_effect_concurrency",
    "build_template_0003_semantic_idempotence_and_ledger",
    "unique_0030_migration_ledger_identity",
)


def build_task3a_candidate_attestation(
    *,
    run_id,
    fresh_identity,
    upgrade_identity,
    git_identity,
):
    validate_task3a_candidate_run_id(run_id)
    expected_fresh = (
        f"wow_exact_first_fresh_test_{run_id}",
        f"wow_exact_first_disposable:{run_id}:fresh",
    )
    expected_upgrade = (
        f"wow_exact_first_upgrade_test_{run_id}",
        f"wow_exact_first_disposable:{run_id}:upgrade",
    )
    if fresh_identity != expected_fresh or upgrade_identity != expected_upgrade:
        raise ValueError("Task 3A candidate database identity drift")
    if (
        type(git_identity) is not tuple
        or len(git_identity) != 3
        or re.fullmatch(r"[0-9a-f]{40}", git_identity[0] or "") is None
        or re.fullmatch(r"[0-9a-f]{40}", git_identity[1] or "") is None
        or re.fullmatch(r"[0-9a-f]{64}", git_identity[2] or "") is None
    ):
        raise ValueError("Task 3A candidate Git identity drift")
    import json

    return json.dumps({
        "schemaVersion": "task3a-candidate-attestation-v2",
        "task": "equipment-simulator-exact-first-task-3a",
        "runId": run_id,
        "passed": True,
        "freshDatabase": {
            "name": fresh_identity[0],
            "comment": fresh_identity[1],
        },
        "upgradeDatabase": {
            "name": upgrade_identity[0],
            "comment": upgrade_identity[1],
        },
        "gitCommit": git_identity[0],
        "gitTree": git_identity[1],
        "migration0030Sha256": git_identity[2],
        "verifiedChecks": list(TASK_3A_VERIFIED_CHECKS),
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class Task3ACandidateAttestationTest(unittest.TestCase):
    def test_one_run_id_validator_accepts_valid_ids_and_rejects_all_nonreusable_runs(self):
        validator = globals().get("validate_task3a_candidate_run_id")
        self.assertIsNotNone(validator)
        if validator is None:
            return

        self.assertEqual(
            TASK_3A_FORBIDDEN_RUN_IDS,
            frozenset({
                "t3a2608050955",
                "t3a260805111623",
                "t3a260805113656",
                "t3a260805120026",
                "t3a260805125812",
                "t3a260805142130",
                "t3a260805160003",
                "t3a260805163536",
            }),
        )

        for valid in ("run12345", "t3a2608052000", "a" * 32):
            with self.subTest(valid=valid):
                self.assertEqual(validator(valid), valid)
        for invalid in (
            "t3a2608050955",
            "t3a260805111623",
            "t3a260805113656",
            "t3a260805120026",
            "t3a260805125812",
            "t3a260805142130",
            "t3a260805160003",
            "t3a260805163536",
            "BAD",
            "short",
            "a" * 33,
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validator(invalid)

    def test_builder_rejects_unpromotable_candidate_run_id_with_matching_identities(self):
        failed_run_id = "t3a260805120026"
        with self.assertRaises(ValueError):
            build_task3a_candidate_attestation(
                run_id=failed_run_id,
                fresh_identity=(
                    f"wow_exact_first_fresh_test_{failed_run_id}",
                    f"wow_exact_first_disposable:{failed_run_id}:fresh",
                ),
                upgrade_identity=(
                    f"wow_exact_first_upgrade_test_{failed_run_id}",
                    f"wow_exact_first_disposable:{failed_run_id}:upgrade",
                ),
                git_identity=("a" * 40, "b" * 40, "c" * 64),
            )

    def test_candidate_connection_rejects_unpromotable_run_before_psycopg_connect(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch

        connect_calls = []
        fake_psycopg = SimpleNamespace(
            connect=lambda dsn: connect_calls.append(dsn),
        )
        with patch.dict(sys.modules, {"psycopg": fake_psycopg}):
            with patch.dict(
                globals(),
                {"TASK_3A_RUN_ID": "t3a260805120026"},
            ):
                with self.assertRaises(ValueError):
                    PostgresExactAuthorityCandidateTest._connect("secret-dsn")
        self.assertEqual(connect_calls, [])

    def test_builder_emits_one_strict_single_line_without_connection_secrets(self):
        run_id = "run12345"
        fresh = (
            "wow_exact_first_fresh_test_run12345",
            "wow_exact_first_disposable:run12345:fresh",
        )
        upgrade = (
            "wow_exact_first_upgrade_test_run12345",
            "wow_exact_first_disposable:run12345:upgrade",
        )
        line = build_task3a_candidate_attestation(
            run_id=run_id,
            fresh_identity=fresh,
            upgrade_identity=upgrade,
            git_identity=("a" * 40, "b" * 40, "c" * 64),
        )

        self.assertNotIn("\n", line)
        self.assertNotIn("\r", line)
        self.assertEqual(len(line.splitlines()), 1)
        import json

        payload = json.loads(line)
        self.assertEqual(payload["schemaVersion"], "task3a-candidate-attestation-v2")
        self.assertEqual(payload["task"], "equipment-simulator-exact-first-task-3a")
        self.assertEqual(payload["runId"], run_id)
        self.assertIs(payload["passed"], True)
        self.assertEqual(payload["freshDatabase"], {"name": fresh[0], "comment": fresh[1]})
        self.assertEqual(payload["upgradeDatabase"], {"name": upgrade[0], "comment": upgrade[1]})
        self.assertEqual(payload["gitCommit"], "a" * 40)
        self.assertEqual(payload["gitTree"], "b" * 40)
        self.assertEqual(payload["migration0030Sha256"], "c" * 64)
        self.assertEqual(tuple(payload["verifiedChecks"]), (
            "exact_disposable_database_identity_and_empty_preflight",
            "fresh_migrations_0001_through_0030",
            "upgrade_migrations_0001_through_0029_seed_then_0030",
            "v1_full_row_schema_table_default_acl_and_grant_parity",
            "canonical_hash_and_json_projection",
            "six_kind_schema_prefix_closed_matrix",
            "seven_exact_foreign_keys",
            "binding_trigger_first_missing_effect_documents_and_bundle_bindings",
            "three_table_update_delete_truncate_immutability",
            "wow_app_explicit_and_effective_select_only_acl",
            "whole_bundle_typed_readback",
            "absent_row_reverse_shared_effect_concurrency",
            "build_template_0003_semantic_idempotence_and_ledger",
            "unique_0030_migration_ledger_identity",
        ))
        self.assertEqual(len(payload["verifiedChecks"]), len(set(payload["verifiedChecks"])))
        lowered = line.lower()
        for secret_name in ("dsn", "host", "username", "password"):
            self.assertNotIn(secret_name, lowered)

    def test_builder_rejects_identity_or_hash_drift(self):
        valid = {
            "run_id": "run12345",
            "fresh_identity": (
                "wow_exact_first_fresh_test_run12345",
                "wow_exact_first_disposable:run12345:fresh",
            ),
            "upgrade_identity": (
                "wow_exact_first_upgrade_test_run12345",
                "wow_exact_first_disposable:run12345:upgrade",
            ),
            "git_identity": ("a" * 40, "b" * 40, "c" * 64),
        }
        mutations = (
            {"run_id": "BAD"},
            {"fresh_identity": ("wrong", valid["fresh_identity"][1])},
            {"upgrade_identity": (valid["upgrade_identity"][0], "wrong")},
            {"git_identity": ("a" * 39, "b" * 40, "c" * 64)},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError):
                    build_task3a_candidate_attestation(**(valid | mutation))

    def test_candidate_method_emits_attestation_as_its_final_statement(self):
        import ast
        import inspect
        import textwrap

        source = textwrap.dedent(inspect.getsource(
            PostgresExactAuthorityCandidateTest.
            test_fresh_and_upgrade_candidates_are_distinct_empty_and_append_only,
        ))
        function = ast.parse(source).body[0]
        final = function.body[-1]
        self.assertIsInstance(final, ast.Expr)
        self.assertIsInstance(final.value, ast.Call)
        self.assertIsInstance(final.value.func, ast.Name)
        self.assertEqual(final.value.func.id, "print")
        self.assertEqual(len(final.value.args), 1)
        self.assertIsInstance(final.value.args[0], ast.Name)
        self.assertEqual(final.value.args[0].id, "attestation")
        self.assertEqual(
            [(keyword.arg, getattr(keyword.value, "value", None))
             for keyword in final.value.keywords],
            [("flush", True)],
        )

    def test_candidate_path_exercises_0003_semantics_in_rollback_only_transactions(self):
        import inspect

        helper_method = getattr(
            PostgresExactAuthorityCandidateTest,
            "_assert_build_template_0003_semantics",
            None,
        )
        self.assertIsNotNone(helper_method)
        if helper_method is None:
            return
        helper = inspect.getsource(helper_method)
        candidate = inspect.getsource(
            PostgresExactAuthorityCandidateTest.
            test_fresh_and_upgrade_candidates_are_distinct_empty_and_append_only,
        )
        self.assertIn("DROP CONSTRAINT build_templates_user_id_template_type_config_hash_key", helper)
        self.assertIn("CHECK (config_hash <> '')", helper)
        self.assertIn("UNIQUE (config_hash, template_type, user_id)", helper)
        self.assertIn("SAVEPOINT migration_attempt", helper)
        self.assertIn("ROLLBACK TO SAVEPOINT migration_attempt", helper)
        self.assertIn(
            "ADD CONSTRAINT build_templates_user_id_template_type_name_key",
            helper,
        )
        self.assertIn("wrong_before_attempt = constraint_state(cur)", helper)
        self.assertIn(
            "self.assertEqual(constraint_state(cur), wrong_before_attempt)",
            helper,
        )
        self.assertIn("conn.rollback()", helper)
        self.assertIn('sqlstate, "P0001"', helper)
        self.assertEqual(candidate.count("_assert_build_template_0003_semantics("), 2)

    def test_missing_effect_documents_are_binding_trigger_first_not_fk_runtime(self):
        import inspect

        source = inspect.getsource(
            PostgresExactAuthorityCandidateTest.
            _assert_missing_effect_documents_fail_binding_trigger_first,
        )
        self.assertIn('sqlstate="P0001"', source)
        self.assertNotIn('sqlstate="23503"', source)
        migration = (
            ROOT / "server" / "migrations" / "postgres"
            / "0030_websim_exact_authority_bundle.sql"
        ).read_text(encoding="utf-8")
        normalized = " ".join(migration.split())
        self.assertIn(
            "CREATE TRIGGER trg_websim_effect_aggregate_record_binding "
            "BEFORE INSERT ON cache.websim_effect_aggregate_records",
            normalized,
        )
        self.assertIn(
            "binding_trigger_first_missing_effect_documents_and_bundle_bindings",
            TASK_3A_VERIFIED_CHECKS,
        )
        self.assertNotIn(
            "aggregate_and_bundle_binding_triggers",
            TASK_3A_VERIFIED_CHECKS,
        )


class Task3BCandidateHarnessTest(unittest.TestCase):
    def test_run_id_and_explicit_candidate_gate_fail_closed(self):
        for valid in ("run12345", "t3b2608062000", "a" * 32):
            with self.subTest(valid=valid):
                self.assertEqual(validate_task3b_candidate_run_id(valid), valid)
        for invalid in (
            "t3a2608050955",
            "t3a260805163536",
            "t3b260806175347",
            "t3b260806191719",
            "t3b260806191950",
            "t3b260806194346",
            "BAD",
            "short",
            "a" * 33,
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_task3b_candidate_run_id(invalid)

        configured = task3b_candidate_configured
        self.assertFalse(configured("run12345", "fresh", "upgrade", None))
        self.assertFalse(configured("run12345", "fresh", "", "/usr/bin/psql"))
        self.assertFalse(configured("", "fresh", "upgrade", "/usr/bin/psql"))
        self.assertTrue(configured("run12345", "fresh", "upgrade", "/usr/bin/psql"))

    def test_harness_pins_fresh_and_upgrade_migration_boundaries(self):
        self.assertEqual(
            TASK_3B_MIGRATIONS[-1].name,
            "0031_websim_exact_snapshot_v2.sql",
        )
        self.assertEqual(
            TASK_3B_BASELINE_MIGRATIONS[-1].name,
            "0030_websim_exact_authority_bundle.sql",
        )
        self.assertEqual(TASK_3B_MIGRATIONS[:-1], TASK_3B_BASELINE_MIGRATIONS)


class Task5CV3MigrationBoundaryTest(unittest.TestCase):
    def test_0035_is_the_only_forward_candidate_extension_from_0034(self):
        self.assertEqual(
            TASK_5C_MIGRATIONS[-1].name,
            "0035_websim_exact_runtime_authority_release.sql",
        )
        self.assertEqual(
            TASK_5C_BASELINE_MIGRATIONS[-1].name,
            "0034_websim_exact_job_snapshot_binding.sql",
        )
        self.assertEqual(TASK_5C_MIGRATIONS[:-1], TASK_5C_BASELINE_MIGRATIONS)


class Task5CCandidateHarnessTest(unittest.TestCase):
    def test_cloud_candidate_gate_requires_every_distinct_explicit_input(self):
        self.assertEqual(
            validate_task5c_candidate_run_id("t5c260810120000"),
            "t5c260810120000",
        )
        for invalid in ("short", "BAD", "a" * 33, "contains-hyphen"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_task5c_candidate_run_id(invalid)

        configured = task5c_candidate_configured
        complete = (
            "t5c260810120000", "fresh", "upgrade", "migrator",
            "app", "worker", "/usr/bin/psql",
        )
        self.assertTrue(configured(*complete))
        for index in range(len(complete)):
            candidate = list(complete)
            candidate[index] = ""
            with self.subTest(missing=index):
                self.assertFalse(configured(*candidate))
        self.assertFalse(configured(
            "t5c260810120000", "same", "same", "migrator", "app", "worker",
            "/usr/bin/psql",
        ))
        self.assertFalse(configured(
            "t5c260810120000", "fresh", "upgrade", "same", "same", "worker",
            "/usr/bin/psql",
        ))

    def test_candidate_attestation_is_redacted_and_bound_to_0035_identity(self):
        run_id = "t5c260810120000"
        line = build_task5c_candidate_attestation(
            run_id=run_id,
            fresh_identity=(
                f"wow_exact_first_fresh_test_{run_id}",
                f"wow_exact_first_disposable:{run_id}:fresh",
            ),
            upgrade_identity=(
                f"wow_exact_first_upgrade_test_{run_id}",
                f"wow_exact_first_disposable:{run_id}:upgrade",
            ),
            git_identity=("a" * 40, "b" * 40, "c" * 64),
        )
        self.assertNotIn("\n", line)
        payload = json.loads(line)
        self.assertEqual(payload["schemaVersion"], "task5c-candidate-attestation-v1")
        self.assertEqual(payload["runId"], run_id)
        self.assertEqual(payload["migration0035Sha256"], "c" * 64)
        self.assertEqual(
            payload["verifiedChecks"],
            [
                "exact_disposable_database_identity_and_empty_preflight",
                "fresh_migrations_0001_through_0035",
                "upgrade_migrations_0001_through_0034_then_0035",
                "release_membership_zero_multiple_and_occurrence_fail_closed",
                "v3_snapshot_job_and_worker_processor_contract",
                "v1_v2_nonexecution_provider_disable_and_no_async_backflow",
                "runtime_release_function_acl_boundary",
            ],
        )
        lowered = line.lower()
        for secret_name in ("dsn", "host", "username", "password"):
            self.assertNotIn(secret_name, lowered)

    def test_real_candidate_runner_is_opt_in_and_covers_the_release_boundary(self):
        source = inspect.getsource(PostgresRuntimeAuthorityReleaseCandidateTest)
        for required in (
            "TASK_5C_CANDIDATE_CONFIGURED",
            "TASK_5C_BASELINE_MIGRATIONS",
            "TASK_5C_MIGRATIONS",
            "RuntimeAuthorityReleaseStore",
            "read_unique_for_binding",
            "read_occurrences",
            "snapshot_bound_processor",
            "EXACT_IMPORT_REQUEST_V1_UNSUPPORTED",
            "EXACT_IMPORT_REQUEST_V2_UNSUPPORTED",
            "WOW_DEPLOY_START_ASYNC_SYNCS",
            "build_task5c_candidate_attestation",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        for forbidden in ("CREATE DATABASE", "DROP DATABASE", "CREATE ROLE", "DROP ROLE"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

class Task4WCandidateHarnessTest(unittest.TestCase):
    def test_cloud_candidate_gate_requires_every_distinct_explicit_input(self):
        self.assertEqual(validate_task4w_candidate_run_id("t4w260806210000"), "t4w260806210000")
        for invalid in ("short", "BAD", "a" * 33, "contains-hyphen"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_task4w_candidate_run_id(invalid)

        configured = task4w_candidate_configured
        complete = (
            "t4w260806210000", "fresh", "upgrade", "migrator",
            "app", "worker", "/usr/bin/psql",
        )
        self.assertTrue(configured(*complete))
        for index in range(len(complete)):
            candidate = list(complete)
            candidate[index] = ""
            with self.subTest(missing=index):
                self.assertFalse(configured(*candidate))
        self.assertFalse(configured(
            "t4w260806210000", "same", "same", "migrator", "app", "worker",
            "/usr/bin/psql",
        ))
        self.assertFalse(configured(
            "t4w260806210000", "fresh", "upgrade", "same", "same", "worker",
            "/usr/bin/psql",
        ))

    def test_harness_pins_fresh_and_upgrade_migration_boundaries(self):
        self.assertEqual(
            TASK_4W_MIGRATIONS[-1].name,
            "0032_websim_exact_import_jobs.sql",
        )
        self.assertEqual(
            TASK_4W_BASELINE_MIGRATIONS[-1].name,
            "0031_websim_exact_snapshot_v2.sql",
        )
        self.assertEqual(TASK_4W_MIGRATIONS[:-1], TASK_4W_BASELINE_MIGRATIONS)

    def test_cloud_candidate_contains_reverse_metric_lock_and_real_login_acl_matrix(self):
        source = inspect.getsource(PostgresExactImportJobsCandidateTest)
        for required in (
            "def _assert_reverse_metric_lock_order",
            "wait_event_type = 'Lock'",
            "def _assert_real_login_acl_matrix",
            "has_schema_privilege",
            "has_table_privilege",
            "has_sequence_privilege",
            "has_function_privilege",
            "aclexplode",
            "grantee = 0",
            "TASK_4W_WORKER_DSN",
            "TASK_4W_APP_DSN",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        self.assertFalse(task4w_candidate_has_schema_qualified_coalesce(source))
        for required in (
            "COALESCE(proc.proacl, pg_catalog.acldefault('f', proc.proowner))",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)

    def test_cloud_candidate_contains_array_safe_sensitive_jsonpath_boundary(self):
        source = inspect.getsource(PostgresExactImportJobsCandidateTest)
        for required in (
            "def _assert_sensitive_jsonpath_boundary",
            "self._assert_sensitive_jsonpath_boundary()",
            "jsonpath-array-v1",
            "jsonpath-problem-array-v1",
            "must-never-persist",
            "bonusIds",
            '{"status": "resolved", "items": []}',
            '{"code": "INCOMPLETE", "details": []}',
            '{"status": "idle", "events": []}',
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)

    def test_cloud_candidate_coalesce_guard_rejects_case_and_whitespace_variant(self):
        source = inspect.getsource(PostgresExactImportJobsCandidateTest)
        mutated = source.replace(
            "COALESCE(proc.proacl, pg_catalog.acldefault('f', proc.proowner))",
            "pg_catalog.COALESCE (proc.proacl, pg_catalog.acldefault('f', proc.proowner))",
            1,
        )
        self.assertNotEqual(mutated, source)
        self.assertTrue(task4w_candidate_has_schema_qualified_coalesce(mutated))

    def test_cloud_candidate_contains_blocked_post_lock_expiry_cas(self):
        source = inspect.getsource(PostgresExactImportJobsCandidateTest)
        for required in (
            "def _assert_post_lock_expiry_cas",
            "self._assert_post_lock_expiry_cas()",
            "blocked-heartbeat",
            "blocked-terminalize",
            "time.sleep(31)",
            "wait_event_type = 'Lock'",
            "ops.websim_exact_heartbeat",
            "ops.websim_exact_terminalize",
            "lease_until <= pg_catalog.clock_timestamp()",
            "terminal_metric",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)

    def test_cloud_candidate_contains_enqueue_and_claim_wait_time_boundaries(self):
        source = inspect.getsource(PostgresExactImportJobsCandidateTest)
        for required in (
            "def _assert_enqueue_cooldown_post_wait_boundary",
            "self._assert_enqueue_cooldown_post_wait_boundary()",
            "blocked-enqueue-cooldown",
            "pg_advisory_xact_lock",
            "interval '1 second'",
            "time.sleep(1.25)",
            "new_pending",
            "def _assert_claim_metric_post_wait_lease_window",
            "self._assert_claim_metric_post_wait_lease_window()",
            "blocked-claim-metric",
            "terminal_classification = 'internal_error'",
            "catalog_status = 'unknown'",
            "time.sleep(1.1)",
            "lease_window.total_seconds()",
            "29.0",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)


@unittest.skipUnless(os.environ.get("WOW_PG_TEST_DSN"), "WOW_PG_TEST_DSN is not configured")
class PostgresIntegrationTest(unittest.TestCase):
    def test_postgres_migration_file_applies(self):
        import psycopg

        with psycopg.connect(os.environ["WOW_PG_TEST_DSN"]) as conn:
            with conn.cursor() as cur:
                for migration in MIGRATIONS:
                    cur.execute(migration.read_text(encoding="utf-8"))
                cur.execute(
                    """
                    SELECT schema_name
                    FROM information_schema.schemata
                    WHERE schema_name = 'identity'
                    """
                )
                self.assertIsNotNone(cur.fetchone())
                cur.execute(
                    """
                    SELECT id
                    FROM ops.schema_migrations
                    WHERE id IN (
                        '0001_identity_app_content_cache_knowledge_analytics_ops',
                        '0002_runtime_privileges',
                        '0003_build_template_config_hash_unique',
                        '0004_chickenbro_runtime_fields',
                        '0005_content_runtime_fields'
                    )
                    """
                )
                self.assertEqual(len(cur.fetchall()), 5)


@unittest.skipUnless(
    TASK_3A_CANDIDATE_CONFIGURED,
    "Task 3A requires psql plus two explicit run-id-bound disposable DSNs",
)
class PostgresExactAuthorityCandidateTest(unittest.TestCase):
    PROJECT_SCHEMAS = (
        "identity", "app", "content", "cache", "knowledge", "analytics", "ops",
    )
    AUTHORITY_TABLES = (
        "websim_canonical_documents",
        "websim_effect_aggregate_records",
        "websim_exact_authority_bundles",
    )

    @staticmethod
    def _connect(dsn):
        validate_task3a_candidate_run_id(TASK_3A_RUN_ID)
        import psycopg

        return psycopg.connect(dsn)

    def _database_identity(self, dsn, flavor):
        expected_name = f"wow_exact_first_{flavor}_test_{TASK_3A_RUN_ID}"
        expected_comment = f"wow_exact_first_disposable:{TASK_3A_RUN_ID}:{flavor}"
        with self._connect(dsn) as conn:
            self.assertEqual(conn.info.dbname, expected_name)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_catalog.shobj_description(oid, 'pg_database') "
                    "FROM pg_catalog.pg_database WHERE datname = current_database()"
                )
                self.assertEqual(cur.fetchone()[0], expected_comment)
        return expected_name, expected_comment

    def _assert_empty_disposable(self, dsn, flavor):
        identity = self._database_identity(dsn, flavor)
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT nspname FROM pg_catalog.pg_namespace "
                    "WHERE nspname = ANY(%s)",
                    (list(self.PROJECT_SCHEMAS),),
                )
                self.assertEqual(cur.fetchall(), [])
                cur.execute(
                    "SELECT count(*) FROM pg_catalog.pg_class c "
                    "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = ANY(%s)",
                    (list(self.PROJECT_SCHEMAS),),
                )
                self.assertEqual(cur.fetchone()[0], 0)
        return identity

    def _apply(self, dsn, migrations):
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                for migration in migrations:
                    cur.execute(migration.read_text(encoding="utf-8"))

    def _assert_sqlstate_rejected(self, dsn, sql, params=(), sqlstate=None):
        import psycopg

        with self.assertRaises(psycopg.Error) as raised:
            with self._connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
        if sqlstate is not None:
            self.assertEqual(raised.exception.sqlstate, sqlstate)

    def _assert_build_template_config_hash_constraint(self, dsn):
        target_name = "build_templates_user_id_template_type_config_hash_key"
        legacy_name = "build_templates_user_id_template_type_name_key"
        expected_columns = ("user_id", "template_type", "config_hash")
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT con.conname, con.contype, "
                    "ARRAY(SELECT attr.attname "
                    "FROM pg_catalog.unnest(con.conkey) WITH ORDINALITY "
                    "AS keyed(attnum, ordinal) "
                    "JOIN pg_catalog.pg_attribute attr "
                    "ON attr.attrelid = con.conrelid AND attr.attnum = keyed.attnum "
                    "ORDER BY keyed.ordinal) "
                    "FROM pg_catalog.pg_constraint con "
                    "JOIN pg_catalog.pg_class rel ON rel.oid = con.conrelid "
                    "JOIN pg_catalog.pg_namespace nsp ON nsp.oid = rel.relnamespace "
                    "WHERE nsp.nspname = 'app' AND rel.relname = 'build_templates' "
                    "AND con.conname = ANY(%s) ORDER BY con.conname",
                    ([target_name, legacy_name],),
                )
                rows = cur.fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0][0], target_name)
                self.assertEqual(rows[0][1], "u")
                self.assertEqual(tuple(rows[0][2]), expected_columns)
                cur.execute(
                    "SELECT pg_catalog.count(*) FROM ops.schema_migrations "
                    "WHERE id = '0003_build_template_config_hash_unique'"
                )
                self.assertEqual(cur.fetchone()[0], 1)

    def _assert_build_template_0003_semantics(self, dsn):
        import psycopg

        target_name = "build_templates_user_id_template_type_config_hash_key"
        legacy_name = "build_templates_user_id_template_type_name_key"
        expected_columns = ("user_id", "template_type", "config_hash")
        migration_sql = MIGRATIONS[2].read_text(encoding="utf-8")

        def constraint_state(cur):
            cur.execute(
                "SELECT con.oid, con.conname, con.contype, "
                "ARRAY(SELECT attr.attname "
                "FROM pg_catalog.unnest(con.conkey) WITH ORDINALITY "
                "AS keyed(attnum, ordinal) "
                "JOIN pg_catalog.pg_attribute attr "
                "ON attr.attrelid = con.conrelid AND attr.attnum = keyed.attnum "
                "ORDER BY keyed.ordinal) "
                "FROM pg_catalog.pg_constraint con "
                "JOIN pg_catalog.pg_class rel ON rel.oid = con.conrelid "
                "JOIN pg_catalog.pg_namespace nsp ON nsp.oid = rel.relnamespace "
                "WHERE nsp.nspname = 'app' AND rel.relname = 'build_templates' "
                "AND con.conname = ANY(%s) ORDER BY con.conname",
                ([target_name, legacy_name],),
            )
            constraints = tuple(
                (row[0], row[1], row[2], tuple(row[3]))
                for row in cur.fetchall()
            )
            cur.execute(
                "SELECT pg_catalog.count(*) FROM ops.schema_migrations "
                "WHERE id = '0003_build_template_config_hash_unique'"
            )
            return constraints, cur.fetchone()[0]

        def assert_correct(state):
            constraints, ledger_rows = state
            self.assertEqual(len(constraints), 1)
            self.assertEqual(constraints[0][1:], (
                target_name,
                "u",
                expected_columns,
            ))
            self.assertEqual(ledger_rows, 1)

        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                before = constraint_state(cur)
                assert_correct(before)
                cur.execute(migration_sql)
                after = constraint_state(cur)
                assert_correct(after)
                self.assertEqual(after[0][0][0], before[0][0][0])
            conn.rollback()
            with conn.cursor() as cur:
                self.assertEqual(constraint_state(cur), before)

        def assert_drift_rejected(add_constraint_sql):
            with self._connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "ALTER TABLE app.build_templates "
                        "DROP CONSTRAINT build_templates_user_id_template_type_config_hash_key"
                    )
                    cur.execute(add_constraint_sql)
                    cur.execute(
                        "ALTER TABLE app.build_templates "
                        "ADD CONSTRAINT build_templates_user_id_template_type_name_key "
                        "UNIQUE (user_id, template_type, name)"
                    )
                    wrong_before_attempt = constraint_state(cur)
                    cur.execute("SAVEPOINT migration_attempt")
                    with self.assertRaises(psycopg.Error) as raised:
                        cur.execute(migration_sql)
                    self.assertEqual(raised.exception.sqlstate, "P0001")
                    cur.execute("ROLLBACK TO SAVEPOINT migration_attempt")
                    self.assertEqual(constraint_state(cur), wrong_before_attempt)
                conn.rollback()
                with conn.cursor() as cur:
                    self.assertEqual(constraint_state(cur), before)

        assert_drift_rejected(
            "ALTER TABLE app.build_templates "
            "ADD CONSTRAINT build_templates_user_id_template_type_config_hash_key "
            "CHECK (config_hash <> '')"
        )
        assert_drift_rejected(
            "ALTER TABLE app.build_templates "
            "ADD CONSTRAINT build_templates_user_id_template_type_config_hash_key "
            "UNIQUE (config_hash, template_type, user_id)"
        )

    def _snapshot_existing_v1_state(self, cur):
        excluded = set(self.AUTHORITY_TABLES)

        def rows(sql):
            cur.execute(sql, (list(self.PROJECT_SCHEMAS),))
            return tuple(
                tuple(row)
                for row in cur.fetchall()
                if not (row[0] == "cache" and row[1] in excluded)
            )

        cur.execute(
            "SELECT n.nspname, pg_catalog.pg_get_userbyid(n.nspowner), "
            "COALESCE(n.nspacl::text, '') "
            "FROM pg_catalog.pg_namespace n WHERE n.nspname = ANY(%s) "
            "ORDER BY n.nspname",
            (list(self.PROJECT_SCHEMAS),),
        )
        schemas = tuple(tuple(row) for row in cur.fetchall())
        relations = rows(
            "SELECT n.nspname, c.relname, c.relkind, "
            "pg_catalog.pg_get_userbyid(c.relowner), COALESCE(c.relacl::text, '') "
            "FROM pg_catalog.pg_class c "
            "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = ANY(%s) AND c.relkind IN ('r','p') "
            "ORDER BY n.nspname, c.relname"
        )
        columns = rows(
            "SELECT n.nspname, c.relname, a.attnum, a.attname, "
            "pg_catalog.format_type(a.atttypid, a.atttypmod), a.attnotnull, "
            "COALESCE(pg_catalog.pg_get_expr(d.adbin, d.adrelid), '') "
            "FROM pg_catalog.pg_class c "
            "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
            "JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid "
            "LEFT JOIN pg_catalog.pg_attrdef d "
            "ON d.adrelid = c.oid AND d.adnum = a.attnum "
            "WHERE n.nspname = ANY(%s) AND c.relkind IN ('r','p') "
            "AND a.attnum > 0 AND NOT a.attisdropped "
            "ORDER BY n.nspname, c.relname, a.attnum"
        )
        constraints = rows(
            "SELECT n.nspname, c.relname, con.conname, con.contype, "
            "pg_catalog.pg_get_constraintdef(con.oid, true) "
            "FROM pg_catalog.pg_constraint con "
            "JOIN pg_catalog.pg_class c ON c.oid = con.conrelid "
            "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = ANY(%s) "
            "ORDER BY n.nspname, c.relname, con.conname"
        )
        indexes = rows(
            "SELECT n.nspname, c.relname, i.relname, "
            "pg_catalog.pg_get_indexdef(i.oid) "
            "FROM pg_catalog.pg_index x "
            "JOIN pg_catalog.pg_class c ON c.oid = x.indrelid "
            "JOIN pg_catalog.pg_class i ON i.oid = x.indexrelid "
            "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = ANY(%s) "
            "ORDER BY n.nspname, c.relname, i.relname"
        )
        triggers = rows(
            "SELECT n.nspname, c.relname, t.tgname, "
            "pg_catalog.pg_get_triggerdef(t.oid, true) "
            "FROM pg_catalog.pg_trigger t "
            "JOIN pg_catalog.pg_class c ON c.oid = t.tgrelid "
            "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = ANY(%s) AND NOT t.tgisinternal "
            "ORDER BY n.nspname, c.relname, t.tgname"
        )
        cur.execute(
            "SELECT COALESCE(n.nspname, ''), "
            "pg_catalog.pg_get_userbyid(d.defaclrole), d.defaclobjtype, "
            "COALESCE(d.defaclacl::text, '') "
            "FROM pg_catalog.pg_default_acl d "
            "LEFT JOIN pg_catalog.pg_namespace n ON n.oid = d.defaclnamespace "
            "WHERE n.nspname = ANY(%s) OR d.defaclnamespace = 0 "
            "ORDER BY 1, 2, 3, 4",
            (list(self.PROJECT_SCHEMAS),),
        )
        default_acl = tuple(tuple(row) for row in cur.fetchall())
        effective_grants = rows(
            "SELECT n.nspname, c.relname, "
            "pg_catalog.has_table_privilege('wow_app', c.oid, 'SELECT'), "
            "pg_catalog.has_table_privilege('wow_app', c.oid, 'INSERT'), "
            "pg_catalog.has_table_privilege('wow_app', c.oid, 'UPDATE'), "
            "pg_catalog.has_table_privilege('wow_app', c.oid, 'DELETE'), "
            "pg_catalog.has_table_privilege('wow_app', c.oid, 'TRUNCATE') "
            "FROM pg_catalog.pg_class c "
            "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = ANY(%s) AND c.relkind IN ('r','p') "
            "ORDER BY n.nspname, c.relname"
        )
        return {
            "schemas": schemas,
            "relations": relations,
            "columns": columns,
            "constraints": constraints,
            "indexes": indexes,
            "triggers": triggers,
            "defaultAcl": default_acl,
            "effectiveWowAppGrants": effective_grants,
        }

    @staticmethod
    def _git_identity():
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        if status:
            raise AssertionError("Task 3A candidate requires a clean committed tree")
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        tree = subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        import hashlib

        migration = ROOT / "server" / "migrations" / "postgres" / "0030_websim_exact_authority_bundle.sql"
        return commit, tree, hashlib.sha256(migration.read_bytes()).hexdigest()

    def _assert_closed_document_matrix(self, dsn, bundle):
        import hashlib

        matrix = (
            ("exact_item", "gear-exact-item-instance-v2", "exact-item-instance:sha256:", bundle.exact_item),
            ("exact_static_facts", "exact-static-facts-v1", "exact-static-facts:sha256:", bundle.static_facts),
            ("exact_progression", "exact-progression-binding-v1", "exact-progression:sha256:", bundle.progression),
            ("effect_record", "simc-item-effect-record-v1", "simc-item-effect-record:sha256:", bundle.effect_records[0]),
            ("effect_aggregate", "simc-item-effect-support-v1", "simc-item-effect-support:sha256:", bundle.effect_support),
            ("exact_authority", "exact-authority-envelope-v1", "exact-authority:sha256:", bundle.envelope),
        )
        insert = (
            "INSERT INTO cache.websim_canonical_documents "
            "(content_key, document_kind, schema_revision, canonical_bytes, "
            "canonical_json, canonical_sha256) VALUES (%s, %s, %s, %s, %s::jsonb, %s)"
        )
        for index, (kind, schema, prefix, document) in enumerate(matrix):
            next_kind, next_schema, next_prefix, _ = matrix[(index + 1) % len(matrix)]
            raw = document.canonical_bytes
            digest = hashlib.sha256(raw).hexdigest()
            base = (raw, raw.decode("utf-8"), digest)
            mutations = (
                (prefix + digest, next_kind, schema, *base),
                (prefix + digest, kind, next_schema, *base),
                (next_prefix + digest, kind, schema, *base),
            )
            for params in mutations:
                self._assert_sqlstate_rejected(
                    dsn, insert, params, sqlstate="23514",
                )
        unknown_raw = matrix[0][3].canonical_bytes
        unknown_digest = hashlib.sha256(unknown_raw).hexdigest()
        self._assert_sqlstate_rejected(
            dsn,
            insert,
            (
                "unknown-canonical:sha256:" + unknown_digest,
                "unknown_kind",
                "unknown-schema-v1",
                unknown_raw,
                unknown_raw.decode("utf-8"),
                unknown_digest,
            ),
            sqlstate="23514",
        )

    def _assert_exact_foreign_key_catalog(self, dsn):
        expected = {
            ("websim_effect_aggregate_records", 1, "effect_support_key", "websim_canonical_documents", 1, "content_key", "r"),
            ("websim_effect_aggregate_records", 1, "effect_record_key", "websim_canonical_documents", 1, "content_key", "r"),
            ("websim_exact_authority_bundles", 1, "exact_authority_envelope_key", "websim_canonical_documents", 1, "content_key", "r"),
            ("websim_exact_authority_bundles", 1, "exact_item_instance_key", "websim_canonical_documents", 1, "content_key", "r"),
            ("websim_exact_authority_bundles", 1, "static_facts_key", "websim_canonical_documents", 1, "content_key", "r"),
            ("websim_exact_authority_bundles", 1, "progression_binding_key", "websim_canonical_documents", 1, "content_key", "r"),
            ("websim_exact_authority_bundles", 1, "effect_support_key", "websim_canonical_documents", 1, "content_key", "r"),
        }
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT src.relname, pg_catalog.cardinality(con.conkey), "
                    "src_col.attname, target.relname, "
                    "pg_catalog.cardinality(con.confkey), target_col.attname, "
                    "con.confdeltype "
                    "FROM pg_catalog.pg_constraint con "
                    "JOIN pg_catalog.pg_class src ON src.oid = con.conrelid "
                    "JOIN pg_catalog.pg_namespace src_n ON src_n.oid = src.relnamespace "
                    "JOIN pg_catalog.pg_attribute src_col "
                    "ON src_col.attrelid = src.oid AND src_col.attnum = con.conkey[1] "
                    "JOIN pg_catalog.pg_class target ON target.oid = con.confrelid "
                    "JOIN pg_catalog.pg_namespace target_n ON target_n.oid = target.relnamespace "
                    "JOIN pg_catalog.pg_attribute target_col "
                    "ON target_col.attrelid = target.oid AND target_col.attnum = con.confkey[1] "
                    "WHERE con.contype = 'f' AND src_n.nspname = 'cache' "
                    "AND target_n.nspname = 'cache' AND src.relname = ANY(%s)",
                    (["websim_effect_aggregate_records", "websim_exact_authority_bundles"],),
                )
                self.assertEqual(set(tuple(row) for row in cur.fetchall()), expected)

    def _assert_authority_acl(self, dsn):
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT oid FROM pg_catalog.pg_roles WHERE rolname = 'wow_app'")
                wow_app_oid = cur.fetchone()[0]
                for table_name in self.AUTHORITY_TABLES:
                    table = f"cache.{table_name}"
                    cur.execute(
                        "SELECT pg_catalog.has_table_privilege('wow_app', %s, 'SELECT'), "
                        "pg_catalog.has_table_privilege('wow_app', %s, 'INSERT'), "
                        "pg_catalog.has_table_privilege('wow_app', %s, 'UPDATE'), "
                        "pg_catalog.has_table_privilege('wow_app', %s, 'DELETE'), "
                        "pg_catalog.has_table_privilege('wow_app', %s, 'TRUNCATE')",
                        (table, table, table, table, table),
                    )
                    self.assertEqual(cur.fetchone(), (True, False, False, False, False))
                    cur.execute(
                        "SELECT acl.grantee, acl.privilege_type, acl.is_grantable "
                        "FROM pg_catalog.pg_class c "
                        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
                        "CROSS JOIN LATERAL pg_catalog.aclexplode("
                        "COALESCE(c.relacl, '{}'::aclitem[])) acl "
                        "WHERE n.nspname = 'cache' AND c.relname = %s "
                        "AND acl.grantee = ANY(%s) ORDER BY 1, 2, 3",
                        (table_name, [0, wow_app_oid]),
                    )
                    self.assertEqual(cur.fetchall(), [(wow_app_oid, "SELECT", False)])

    def _assert_absent_row_reverse_shared_record_concurrency(self, dsn):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from server.gear_exact_authority_store import GearExactAuthorityStore
        from tests.gear_exact_authority_store_test import (
            RESOLVER,
            RULE,
            RUNTIME,
            authority_bundle,
        )

        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                for table_name in self.AUTHORITY_TABLES:
                    cur.execute(f"SELECT pg_catalog.count(*) FROM cache.{table_name}")
                    self.assertEqual(cur.fetchone()[0], 0)
        a = authority_bundle(
            "1001",
            gems=("240892", "240893"),
            gem_bonus_ids=("1514", "1515"),
            gem_item_levels=(90, 91),
        )
        b = authority_bundle(
            "1002",
            gems=("240893", "240892"),
            gem_bonus_ids=("1515", "1514"),
            gem_item_levels=(91, 90),
        )
        self.assertEqual(
            tuple(record.content_key for record in a.effect_records[1:]),
            tuple(reversed(tuple(record.content_key for record in b.effect_records[1:]))),
        )
        barrier = Barrier(2)

        def first_write(bundle):
            barrier.wait(timeout=10)
            return GearExactAuthorityStore(
                lambda: self._connect(dsn),
            ).seal_authority_bundle(bundle)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = (pool.submit(first_write, a), pool.submit(first_write, b))
            results = tuple(future.result(timeout=30) for future in futures)
        self.assertEqual(results, (a, b))
        store = GearExactAuthorityStore(lambda: self._connect(dsn))
        for bundle in (a, b):
            self.assertEqual(
                store.load_verified_bundle(
                    bundle.envelope.content_key,
                    gear_rule_revision=RULE,
                    simc_runtime_revision=RUNTIME,
                    resolver_revision=RESOLVER,
                ),
                bundle,
            )
        duplicate_bundle = authority_bundle("1003")
        self.assertEqual(
            store.seal_authority_bundle(duplicate_bundle),
            duplicate_bundle,
        )
        self.assertEqual(
            duplicate_bundle.effect_records[1],
            duplicate_bundle.effect_records[3],
        )
        return duplicate_bundle

    def _assert_three_table_immutability(self, dsn):
        for table_name in self.AUTHORITY_TABLES:
            table = f"cache.{table_name}"
            self._assert_sqlstate_rejected(
                dsn,
                f"UPDATE {table} SET sealed_at = sealed_at",
                sqlstate="P0001",
            )
            self._assert_sqlstate_rejected(
                dsn,
                f"DELETE FROM {table}",
                sqlstate="P0001",
            )
            self._assert_sqlstate_rejected(
                dsn,
                f"TRUNCATE {table} CASCADE",
                sqlstate="P0001",
            )

    def _assert_missing_effect_documents_fail_binding_trigger_first(self, dsn):
        # The BEFORE INSERT binding trigger reads both documents first and raises
        # P0001 for missing kinds. The seven FK definitions are proven separately
        # by _assert_exact_foreign_key_catalog; this probe is not an FK violation.
        self._assert_sqlstate_rejected(
            dsn,
            "INSERT INTO cache.websim_effect_aggregate_records "
            "(effect_support_key, ordinal, effect_record_key) VALUES (%s, 0, %s)",
            (
                "simc-item-effect-support:sha256:" + "1" * 64,
                "simc-item-effect-record:sha256:" + "2" * 64,
            ),
            sqlstate="P0001",
        )

    def _assert_grants_and_bundle_smoke(self, dsn):
        from tests.gear_exact_authority_store_test import authority_bundle

        matrix_bundle = authority_bundle()
        self._assert_closed_document_matrix(dsn, matrix_bundle)
        bad_hash = "0" * 64
        self._assert_sqlstate_rejected(
            dsn,
            "INSERT INTO cache.websim_canonical_documents "
            "(content_key, document_kind, schema_revision, canonical_bytes, "
            "canonical_json, canonical_sha256) "
            "VALUES (%s, 'exact_item', 'gear-exact-item-instance-v2', "
            "%s, %s::jsonb, %s)",
            ("exact-item-instance:sha256:" + bad_hash, b"{}", "{}", bad_hash),
            sqlstate="23514",
        )
        import hashlib

        projection_bytes = b'{"schemaRevision":"gear-exact-item-instance-v2"}'
        projection_hash = hashlib.sha256(projection_bytes).hexdigest()
        self._assert_sqlstate_rejected(
            dsn,
            "INSERT INTO cache.websim_canonical_documents "
            "(content_key, document_kind, schema_revision, canonical_bytes, "
            "canonical_json, canonical_sha256) "
            "VALUES (%s, 'exact_item', 'gear-exact-item-instance-v2', "
            "%s, %s::jsonb, %s)",
            (
                "exact-item-instance:sha256:" + projection_hash,
                projection_bytes,
                "{}",
                projection_hash,
            ),
            sqlstate="23514",
        )
        self._assert_exact_foreign_key_catalog(dsn)
        self._assert_authority_acl(dsn)
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_catalog.count(*) FROM ops.schema_migrations "
                    "WHERE id = '0030_websim_exact_authority_bundle'"
                )
                self.assertEqual(cur.fetchone()[0], 1)
        sealed = self._assert_absent_row_reverse_shared_record_concurrency(dsn)
        self._assert_missing_effect_documents_fail_binding_trigger_first(dsn)
        self._assert_sqlstate_rejected(
            dsn,
            "INSERT INTO cache.websim_effect_aggregate_records "
            "(effect_support_key, ordinal, effect_record_key) VALUES (%s, %s, %s)",
            (
                sealed.effect_support.content_key,
                len(sealed.effect_records),
                sealed.effect_records[0].content_key,
            ),
            sqlstate="P0001",
        )
        self._assert_sqlstate_rejected(
            dsn,
            "INSERT INTO cache.websim_exact_authority_bundles "
            "(exact_authority_envelope_key, exact_item_instance_key, "
            "static_facts_key, progression_binding_key, effect_support_key, "
            "gear_rule_revision, simc_runtime_revision, resolver_revision) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (
                sealed.envelope.content_key,
                sealed.static_facts.content_key,
                sealed.static_facts.content_key,
                sealed.progression.content_key,
                sealed.effect_support.content_key,
                "gear-rule-matrix-v1",
                "simc-2026.08.04",
                "resolver-v2",
            ),
            sqlstate="P0001",
        )
        self._assert_three_table_immutability(dsn)

    def test_fresh_and_upgrade_candidates_are_distinct_empty_and_append_only(self):
        self.assertNotEqual(TASK_3A_FRESH_DSN, TASK_3A_UPGRADE_DSN)
        fresh_identity = self._assert_empty_disposable(TASK_3A_FRESH_DSN, "fresh")
        upgrade_identity = self._assert_empty_disposable(TASK_3A_UPGRADE_DSN, "upgrade")
        self.assertNotEqual(fresh_identity, upgrade_identity)
        git_identity = self._git_identity()
        commit, tree, migration_sha = git_identity
        self.assertRegex(commit, r"^[0-9a-f]{40}$")
        self.assertRegex(tree, r"^[0-9a-f]{40}$")
        self.assertRegex(migration_sha, r"^[0-9a-f]{64}$")
        self.assertEqual(
            TASK_3A_MIGRATIONS[-1].name,
            "0030_websim_exact_authority_bundle.sql",
        )

        self._apply(TASK_3A_FRESH_DSN, TASK_3A_MIGRATIONS)
        self._assert_build_template_config_hash_constraint(TASK_3A_FRESH_DSN)
        self._assert_build_template_0003_semantics(TASK_3A_FRESH_DSN)
        self._assert_grants_and_bundle_smoke(TASK_3A_FRESH_DSN)

        self._apply(TASK_3A_UPGRADE_DSN, TASK_3A_MIGRATIONS[:-1])
        with self._connect(TASK_3A_UPGRADE_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO cache.websim_gear_enhancement_selections "
                    "(enhancement_selection_key, schema_revision, selection_json, row_hash) "
                    "VALUES (%s, %s, %s::jsonb, %s)",
                    (
                        "enhancement-selection:sha256:" + "a" * 64,
                        "gear-enhancement-selection-v1",
                        '{"schemaRevision":"gear-enhancement-selection-v1"}',
                        "sha256:" + "b" * 64,
                    ),
                )
                cur.execute(
                    "SELECT enhancement_selection_key, schema_revision, "
                    "selection_json::text, row_hash, sealed_at "
                    "FROM cache.websim_gear_enhancement_selections ORDER BY 1"
                )
                before_rows = cur.fetchall()
                before_state = self._snapshot_existing_v1_state(cur)
        self._apply(TASK_3A_UPGRADE_DSN, TASK_3A_MIGRATIONS[-1:])
        self._assert_build_template_config_hash_constraint(TASK_3A_UPGRADE_DSN)
        self._assert_build_template_0003_semantics(TASK_3A_UPGRADE_DSN)
        with self._connect(TASK_3A_UPGRADE_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT enhancement_selection_key, schema_revision, "
                    "selection_json::text, row_hash, sealed_at "
                    "FROM cache.websim_gear_enhancement_selections ORDER BY 1"
                )
                self.assertEqual(cur.fetchall(), before_rows)
                self.assertEqual(
                    self._snapshot_existing_v1_state(cur),
                    before_state,
                )
        self._assert_grants_and_bundle_smoke(TASK_3A_UPGRADE_DSN)
        self.assertEqual(self._git_identity(), git_identity)
        self.assertEqual(
            self._database_identity(TASK_3A_FRESH_DSN, "fresh"),
            fresh_identity,
        )
        self.assertEqual(
            self._database_identity(TASK_3A_UPGRADE_DSN, "upgrade"),
            upgrade_identity,
        )
        attestation = build_task3a_candidate_attestation(
            run_id=TASK_3A_RUN_ID,
            fresh_identity=fresh_identity,
            upgrade_identity=upgrade_identity,
            git_identity=git_identity,
        )
        print(attestation, flush=True)


@unittest.skipUnless(
    TASK_3B_CANDIDATE_CONFIGURED,
    "Task 3B requires psql plus two explicit run-id-bound disposable 0031 DSNs",
)
class PostgresExactSnapshotV2CandidateTest(unittest.TestCase):
    """Explicit-only fresh/upgrade harness; it never provisions databases."""

    PROJECT_SCHEMAS = (
        "identity", "app", "content", "cache", "knowledge", "analytics", "ops",
    )

    @staticmethod
    def _connect(dsn):
        validate_task3b_candidate_run_id(TASK_3B_RUN_ID)
        import psycopg

        return psycopg.connect(dsn)

    def _database_identity(self, dsn, flavor):
        expected = (
            f"wow_exact_first_{flavor}_test_{TASK_3B_RUN_ID}",
            f"wow_exact_first_disposable:{TASK_3B_RUN_ID}:{flavor}",
        )
        with self._connect(dsn) as conn:
            self.assertEqual(conn.info.dbname, expected[0])
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_catalog.shobj_description(oid, 'pg_database') "
                    "FROM pg_catalog.pg_database WHERE datname = current_database()"
                )
                self.assertEqual(cur.fetchone()[0], expected[1])
        return expected

    def _assert_empty_disposable(self, dsn, flavor):
        identity = self._database_identity(dsn, flavor)
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT nspname FROM pg_catalog.pg_namespace "
                    "WHERE nspname = ANY(%s)",
                    (list(self.PROJECT_SCHEMAS),),
                )
                self.assertEqual(cur.fetchall(), [])
        return identity

    def _apply(self, dsn, migrations):
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                for migration in migrations:
                    cur.execute(migration.read_text(encoding="utf-8"))

    @staticmethod
    def _git_identity():
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        if status:
            raise AssertionError("Task 3B candidate requires a clean committed tree")
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        migration = ROOT / "server/migrations/postgres/0031_websim_exact_snapshot_v2.sql"
        return commit, hashlib.sha256(migration.read_bytes()).hexdigest()

    def _seed_v1_catalog(self, dsn, catalog_revision):
        release_id = f"task3b-v1-release-{TASK_3B_RUN_ID}"
        digest = "a" * 64
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO cache.websim_release_registry "
                    "(release_id, release_kind, season_revision, schema_revision, "
                    "content_hash, release_status) VALUES "
                    "(%s, 'gear', 'task3b', 'task3b-v1', %s, 'validated')",
                    (release_id, "sha256:" + digest),
                )
                cur.execute(
                    "INSERT INTO cache.websim_gear_catalog_revisions "
                    "(catalog_revision, schema_revision, builder_revision, "
                    "season_revision, source_gear_release_id, source_content_hash, "
                    "dependency_vector_json, source_summary_json, content_summary_json, "
                    "catalog_json, row_hash) VALUES "
                    "(%s, 'gear-catalog-v1', 'task3b', 'task3b', %s, %s, "
                    "'{}'::jsonb, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb, %s)",
                    (
                        catalog_revision,
                        release_id,
                        "sha256:" + digest,
                        "sha256:" + ("b" * 64),
                    ),
                )

    def _seal_v1_pair(self, dsn):
        from server.simulation_snapshot_store import SimulationSnapshotStore
        from tests.simulation_snapshot_store_test import loadout as v1_loadout
        from tests.simulation_snapshot_store_test import snapshot as v1_snapshot

        loadout = v1_loadout()
        snapshot = v1_snapshot()
        self._seed_v1_catalog(dsn, loadout["catalogRevision"])
        store = SimulationSnapshotStore(lambda: self._connect(dsn))
        sealed_loadout = store.seal_loadout(loadout)
        sealed_snapshot = store.seal_snapshot(snapshot)
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT resolved_loadout_key, schema_revision, catalog_revision, "
                    "gear_rule_revision, exact_registry_revision, class_key, spec_key, "
                    "loadout_json::text, row_hash, sealed_at "
                    "FROM cache.websim_gear_resolved_loadouts"
                )
                loadout_row = cur.fetchone()
                cur.execute(
                    "SELECT simulation_snapshot_key, schema_revision, resolved_loadout_key, "
                    "talent_profile_key, compiler_revision, simc_runtime_revision, "
                    "canonical_input_hash, catalog_revision, gear_rule_revision, "
                    "snapshot_json::text, row_hash, sealed_at "
                    "FROM cache.websim_simulation_snapshots"
                )
                snapshot_row = cur.fetchone()
        return sealed_loadout, sealed_snapshot, loadout_row, snapshot_row

    @staticmethod
    def _relation_authority_fixture(*, verified_at="2026-08-06T00:00:00Z"):
        from server.gear_loadout_effect_authority import (
            resolve_loadout_effect_authority,
        )
        from tests.gear_loadout_effect_authority_test import (
            descriptor,
            records_for,
            snapshot_with_descriptors,
        )

        resolver = snapshot_with_descriptors([
            descriptor("set-a", 2, "set-a-2pc"),
            descriptor("set-b", 1, "set-b-1pc"),
        ])
        outcome = resolve_loadout_effect_authority(
            resolver,
            records=records_for(resolver, verified_at=verified_at),
        )
        if outcome.status != "verified" or outcome.document is None:
            raise AssertionError(outcome.issues)
        alternate = records_for(resolver, verified_at="2026-08-06T00:00:59Z")[0]
        return (
            outcome.document,
            tuple(records_for(resolver, verified_at=verified_at)),
            alternate,
        )

    def _seed_effect_documents(self, dsn, documents):
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                for document in documents:
                    raw = document.canonical_bytes
                    cur.execute(
                        "INSERT INTO cache.websim_canonical_documents "
                        "(content_key, document_kind, schema_revision, canonical_bytes, "
                        "canonical_json, canonical_sha256) VALUES "
                        "(%s, %s, %s, %s, %s::jsonb, %s)",
                        (
                            document.content_key,
                            document.document_kind,
                            document.schema_revision,
                            raw,
                            raw.decode("utf-8"),
                            hashlib.sha256(raw).hexdigest(),
                        ),
                    )

    @staticmethod
    def _insert_authority_parent(cur, authority):
        raw = authority.canonical_bytes
        cur.execute(
            "INSERT INTO cache.websim_loadout_effect_authorities "
            "(loadout_effect_authority_key, schema_revision, canonical_bytes, "
            "canonical_json, canonical_sha256) VALUES "
            "(%s, %s, %s, %s::jsonb, %s)",
            (
                authority.content_key,
                authority.schema_revision,
                raw,
                raw.decode("utf-8"),
                hashlib.sha256(raw).hexdigest(),
            ),
        )

    @staticmethod
    def _insert_authority_relation(cur, authority_key, ordinal, record_key):
        cur.execute(
            "INSERT INTO cache.websim_loadout_effect_authority_records "
            "(loadout_effect_authority_key, ordinal, effect_record_key) "
            "VALUES (%s, %s, %s)",
            (authority_key, ordinal, record_key),
        )

    @staticmethod
    def _loadout_occurrences(authority):
        payload = json.loads(authority.canonical_bytes)
        return [
            {
                "scope": "loadout",
                "loadoutEffectAuthorityKey": authority.content_key,
                "recordOrdinal": ordinal,
                "subjectKind": subject["subjectKind"],
                "subjectKey": subject["subjectKey"],
                "subjectVariantSignature": subject["subjectVariantSignature"],
                "supportRecordKey": record["supportRecordKey"],
            }
            for ordinal, (subject, record) in enumerate(zip(
                payload["subjects"], payload["supportRecords"], strict=True,
            ))
        ]

    @staticmethod
    def _v2_loadout_row(key, row_hash, evidence, authority_key=None):
        row = {
            "schemaRevision": "resolved-loadout-v2",
            "status": "ready",
            "resolvedLoadoutKey": key,
            "gearRuleRevision": "gear-rule-matrix-v1",
            "eligibilityContext": {"classKey": "mage", "specKey": "arcane"},
            "rowHash": row_hash,
            "exactAuthorityBySlot": [],
            "effectEvidenceByOccurrence": evidence,
        }
        if authority_key is not None:
            row["loadoutEffectAuthorityKey"] = authority_key
        return row

    @staticmethod
    def _valid_resolver_replay_context(authority_key=None):
        signature = "sha256:" + ("a" * 64)
        subjects = []
        effects = []
        counts = {}
        if authority_key is not None:
            subjects = [{
                "subjectKind": "set_bonus",
                "itemSetId": "set:direct",
                "pieces": 1,
                "subjectKey": "set:direct:effect",
            }]
            effects = [{
                "effectId": "set:direct:effect",
                "itemSetId": "set:direct",
                "pieces": 1,
            }]
            counts = {"set:direct": 1}
        set_state = {
            "itemSetCounts": counts,
            "activeDynamicEffects": effects,
        }
        replay = {
            "schemaRevision": "exact-resolver-replay-context-v1",
            "status": "verified",
            "dependencyVector": {
                "gearRuleRevision": "gear-rule-matrix-v1",
                "resolverContractRevision": "resolver-v2",
                "simcRuntimeRevision": "simc-runtime-v2",
            },
            "resolvedGearSignature": signature,
            "eligibilityContext": {
                "classKey": "mage",
                "specKey": "arcane",
                "level": 90,
            },
            "profileReadiness": {
                "status": "verified",
                "simcReady": True,
                "requiredSlots": ["head"],
                "readySlots": ["head"],
                "simcRuntimeRevision": "simc-runtime-v2",
            },
            "resolvedSlots": {
                "head": {
                    "slot": "head",
                    "itemId": "item-direct",
                    "legality": {"status": "verified"},
                },
            },
            "setState": set_state,
            "loadoutEffectSubjects": subjects,
            "v2EffectBoundary": {
                "schemaRevision": "gear-resolver-v2-effect-boundary-v1",
                "status": "verified",
                "resolvedGearSignature": signature,
                "setState": set_state,
                "subjects": subjects,
                "gearRuleRevision": "gear-rule-matrix-v1",
                "resolverRevision": "resolver-v2",
                "simcRuntimeRevision": "simc-runtime-v2",
            },
        }
        if authority_key is not None:
            replay["v2EffectBoundary"]["loadoutEffectAuthorityKey"] = (
                authority_key
            )
        return replay

    def _insert_v2_loadout(
        self,
        cur,
        *,
        key,
        row_hash,
        evidence,
        authority_key=None,
        replay_context=None,
    ):
        row = self._v2_loadout_row(key, row_hash, evidence, authority_key)
        replay = (
            self._valid_resolver_replay_context(authority_key)
            if replay_context is None
            else replay_context
        )
        cur.execute(
            "INSERT INTO cache.websim_gear_resolved_loadouts "
            "(resolved_loadout_key, schema_revision, catalog_revision, "
            "gear_rule_revision, exact_registry_revision, class_key, spec_key, "
            "loadout_json, row_hash, exact_authority_by_slot_json, "
            "effect_evidence_by_occurrence_json, loadout_effect_authority_key, "
            "resolver_replay_context_json) VALUES "
            "(%s, 'resolved-loadout-v2', NULL, 'gear-rule-matrix-v1', NULL, "
            "'mage', 'arcane', %s::jsonb, %s, '[]'::jsonb, %s::jsonb, %s, "
            "%s::jsonb)",
            (
                key,
                json.dumps(row),
                row_hash,
                json.dumps(evidence),
                authority_key,
                json.dumps(replay),
            ),
        )

    @staticmethod
    def _insert_v2_loadout_representation(cur, row, replay):
        eligibility = row["eligibilityContext"]
        cur.execute(
            "INSERT INTO cache.websim_gear_resolved_loadouts "
            "(resolved_loadout_key, schema_revision, catalog_revision, "
            "gear_rule_revision, exact_registry_revision, class_key, spec_key, "
            "loadout_json, row_hash, exact_authority_by_slot_json, "
            "effect_evidence_by_occurrence_json, loadout_effect_authority_key, "
            "resolver_replay_context_json) VALUES "
            "(%s, 'resolved-loadout-v2', %s, %s, NULL, %s, %s, %s::jsonb, %s, "
            "%s::jsonb, %s::jsonb, %s, %s::jsonb)",
            (
                row["resolvedLoadoutKey"],
                row.get("originCatalogRevision"),
                row["gearRuleRevision"],
                eligibility["classKey"],
                eligibility["specKey"],
                json.dumps(row),
                row["rowHash"],
                json.dumps(row["exactAuthorityBySlot"]),
                json.dumps(row["effectEvidenceByOccurrence"]),
                row.get("loadoutEffectAuthorityKey"),
                json.dumps(replay),
            ),
        )

    @staticmethod
    def _insert_v2_snapshot_representation(cur, row):
        cur.execute(
            "INSERT INTO cache.websim_simulation_snapshots "
            "(simulation_snapshot_key, schema_revision, resolved_loadout_key, "
            "talent_profile_key, compiler_revision, simc_runtime_revision, "
            "canonical_input_hash, catalog_revision, gear_rule_revision, "
            "snapshot_json, row_hash, exact_authority_by_slot_json, "
            "effect_evidence_by_occurrence_json, loadout_effect_authority_key) "
            "VALUES (%s, 'simulation-snapshot-v2', %s, %s, %s, %s, %s, %s, "
            "NULL, %s::jsonb, %s, %s::jsonb, %s::jsonb, %s)",
            (
                row["simulationSnapshotKey"],
                row["resolvedLoadoutKey"],
                row["talentProfileKey"],
                row["compilerRevision"],
                row["simcRuntimeRevision"],
                row["canonicalInputHash"],
                row.get("originCatalogRevision"),
                json.dumps(row),
                row["rowHash"],
                json.dumps(row["exactAuthorityBySlot"]),
                json.dumps(row["effectEvidenceByOccurrence"]),
                row.get("loadoutEffectAuthorityKey"),
            ),
        )

    def _assert_resolver_replay_context_boundary(self, dsn):
        import copy
        import psycopg

        valid = self._valid_resolver_replay_context()

        def identity(label):
            digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
            return (
                "resolved-loadout-v2:sha256:" + digest,
                "sha256:" + digest,
            )

        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT cache.verify_websim_resolver_replay_context(%s::jsonb)",
                    (json.dumps(valid),),
                )
                self.assertIsNotNone(cur.fetchone())

        item_set_id_256_bytes = "a" * 256
        self.assertEqual(len(item_set_id_256_bytes.encode("utf-8")), 256)
        max_item_set_id = copy.deepcopy(valid)
        max_item_set_id["setState"]["itemSetCounts"] = {
            item_set_id_256_bytes: 1,
        }
        max_item_set_id["v2EffectBoundary"]["setState"] = copy.deepcopy(
            max_item_set_id["setState"]
        )
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT cache.verify_websim_resolver_replay_context(%s::jsonb)",
                    (json.dumps(max_item_set_id),),
                )
                self.assertIsNotNone(cur.fetchone())

        over_item_set_id = copy.deepcopy(max_item_set_id)
        over_item_set_id["setState"]["itemSetCounts"] = {
            item_set_id_256_bytes + "a": 1,
        }
        over_item_set_id["v2EffectBoundary"]["setState"] = copy.deepcopy(
            over_item_set_id["setState"]
        )
        over_key, over_hash = identity("task3b-replay-item-set-id-257-bytes")
        with self.assertRaises(psycopg.Error) as raised:
            with self._connect(dsn) as conn:
                with conn.cursor() as cur:
                    self._insert_v2_loadout(
                        cur,
                        key=over_key,
                        row_hash=over_hash,
                        evidence=[],
                        replay_context=over_item_set_id,
                    )
        self.assertEqual(raised.exception.sqlstate, "P0001")
        self.assertEqual(
            raised.exception.diag.message_primary,
            "v2 resolver replay context is invalid",
        )

        authority_key = "loadout-effect-authority:sha256:" + ("e" * 64)

        def replay_with_identity(field, value):
            replay = self._valid_resolver_replay_context(authority_key)
            if field.startswith("dependencyVector."):
                dependency_field = field.split(".", 1)[1]
                replay["dependencyVector"][dependency_field] = value
                boundary_field = {
                    "gearRuleRevision": "gearRuleRevision",
                    "resolverContractRevision": "resolverRevision",
                    "simcRuntimeRevision": "simcRuntimeRevision",
                }[dependency_field]
                replay["v2EffectBoundary"][boundary_field] = value
                if dependency_field == "simcRuntimeRevision":
                    replay["profileReadiness"]["simcRuntimeRevision"] = value
            elif field == "resolvedGearSignature":
                replay[field] = value
                replay["v2EffectBoundary"][field] = value
            elif field.startswith("eligibilityContext."):
                replay["eligibilityContext"][field.split(".", 1)[1]] = value
            elif field == "profileReadiness.slot":
                replay["profileReadiness"]["requiredSlots"] = [value]
                replay["profileReadiness"]["readySlots"] = [value]
                slot = replay["resolvedSlots"].pop("head")
                slot["slot"] = value
                replay["resolvedSlots"][value] = slot
            elif field == "resolvedSlots.itemId":
                replay["resolvedSlots"]["head"]["itemId"] = value
            elif field == "setState.itemSetCounts.key":
                replay["setState"]["itemSetCounts"] = {value: 1}
                replay["v2EffectBoundary"]["setState"] = copy.deepcopy(
                    replay["setState"]
                )
            elif field.startswith("setState.activeDynamicEffects."):
                effect_field = field.rsplit(".", 1)[1]
                replay["setState"]["activeDynamicEffects"][0][
                    effect_field
                ] = value
                replay["v2EffectBoundary"]["setState"] = copy.deepcopy(
                    replay["setState"]
                )
            elif field.startswith("loadoutEffectSubjects."):
                subject_field = field.split(".", 1)[1]
                replay["loadoutEffectSubjects"][0][subject_field] = value
                replay["v2EffectBoundary"]["subjects"] = copy.deepcopy(
                    replay["loadoutEffectSubjects"]
                )
            else:  # pragma: no cover - test table is closed below
                raise AssertionError(f"unknown replay identity field: {field}")
            return replay

        identity_fields = (
            "dependencyVector.gearRuleRevision",
            "dependencyVector.resolverContractRevision",
            "dependencyVector.simcRuntimeRevision",
            "resolvedGearSignature",
            "eligibilityContext.classKey",
            "eligibilityContext.specKey",
            "profileReadiness.slot",
            "resolvedSlots.itemId",
            "setState.itemSetCounts.key",
            "setState.activeDynamicEffects.effectId",
            "setState.activeDynamicEffects.itemSetId",
            "loadoutEffectSubjects.subjectKind",
            "loadoutEffectSubjects.itemSetId",
            "loadoutEffectSubjects.subjectKey",
        )
        invalid_identity_values = (
            ("cjk", "名字"),
            ("non-canonical-ascii", "bad token"),
            ("257-bytes", "a" * 257),
        )
        with self._connect(dsn) as conn:
            for field in identity_fields:
                for invalid_kind, invalid_value in invalid_identity_values:
                    with self.subTest(
                        replay_identity_field=field,
                        invalid_identity_kind=invalid_kind,
                    ):
                        replay = replay_with_identity(field, invalid_value)
                        with self.assertRaises(psycopg.Error) as raised:
                            with conn.transaction():
                                conn.execute(
                                    "SELECT cache."
                                    "verify_websim_resolver_replay_context(%s::jsonb)",
                                    (json.dumps(replay),),
                                )
                        self.assertEqual(raised.exception.sqlstate, "P0001")
                        self.assertEqual(
                            raised.exception.diag.message_primary,
                            "v2 resolver replay context is invalid",
                        )

        forbidden = (
            "Catalog",
            "catalogRevision",
            "rawProfile",
            "rawString",
            "player",
            "playerName",
            "characterName",
            "realm",
            "server",
            "source",
            "sourceRefIds",
            "sourcePayload",
        )
        poisoned = []
        for placement in (
            "root",
            "profileReadiness",
            "resolvedSlots.head",
            "setState.itemSetCounts",
        ):
            for semantic_key in forbidden:
                replay = copy.deepcopy(valid)
                if placement == "root":
                    replay[semantic_key] = {"poison": True}
                elif placement == "profileReadiness":
                    replay["profileReadiness"][semantic_key] = {"poison": True}
                elif placement == "resolvedSlots.head":
                    replay["resolvedSlots"]["head"][semantic_key] = {
                        "poison": True,
                    }
                else:
                    replay["setState"]["itemSetCounts"][semantic_key] = 1
                    replay["v2EffectBoundary"]["setState"] = copy.deepcopy(
                        replay["setState"]
                    )
                poisoned.append((placement, semantic_key, replay))

        structural_drift = []
        missing = copy.deepcopy(valid)
        missing["dependencyVector"].pop("resolverContractRevision")
        structural_drift.append(("missing", missing))
        wrong_type = copy.deepcopy(valid)
        wrong_type["eligibilityContext"]["level"] = "90"
        structural_drift.append(("wrong-type", wrong_type))
        extra_set_state = copy.deepcopy(valid)
        extra_set_state["setState"]["unexpected"] = []
        extra_set_state["v2EffectBoundary"]["setState"] = copy.deepcopy(
            extra_set_state["setState"]
        )
        structural_drift.append(("extra-set-state", extra_set_state))
        structural_drift.append((
            "unexpected-active-boundary",
            self._valid_resolver_replay_context(
                "loadout-effect-authority:sha256:" + ("f" * 64)
            ),
        ))

        for placement, semantic_key, replay in poisoned:
            with self.subTest(
                replay_placement=placement,
                semantic_key=semantic_key,
            ):
                key, row_hash = identity(
                    f"task3b-replay-{placement}-{semantic_key}"
                )
                with self.assertRaises(psycopg.Error) as raised:
                    with self._connect(dsn) as conn:
                        with conn.cursor() as cur:
                            self._insert_v2_loadout(
                                cur,
                                key=key,
                                row_hash=row_hash,
                                evidence=[],
                                replay_context=replay,
                            )
                self.assertEqual(raised.exception.sqlstate, "P0001")
                self.assertEqual(
                    raised.exception.diag.message_primary,
                    "v2 resolver replay context is invalid",
                )

        for label, replay in structural_drift:
            with self.subTest(replay_structure=label):
                key, row_hash = identity(f"task3b-replay-{label}")
                with self.assertRaises(psycopg.Error) as raised:
                    with self._connect(dsn) as conn:
                        with conn.cursor() as cur:
                            self._insert_v2_loadout(
                                cur,
                                key=key,
                                row_hash=row_hash,
                                evidence=[],
                                replay_context=replay,
                            )
                self.assertEqual(raised.exception.sqlstate, "P0001")
                self.assertEqual(
                    raised.exception.diag.message_primary,
                    "v2 resolver replay context is invalid",
                )

    def _assert_pg_rejected(self, cur, sql, params, *, sqlstate, message):
        import psycopg

        with self.assertRaises(psycopg.Error) as raised:
            cur.execute(sql, params)
        self.assertEqual(raised.exception.sqlstate, sqlstate)
        self.assertEqual(raised.exception.diag.message_primary, message)

    @staticmethod
    def _mutated_authority(authority, mutate_subject):
        payload = json.loads(authority.canonical_bytes)
        mutate_subject(payload["subjects"][0])
        raw = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return SimpleNamespace(
            content_key=(
                "loadout-effect-authority:sha256:"
                + hashlib.sha256(raw).hexdigest()
            ),
            schema_revision=authority.schema_revision,
            canonical_bytes=raw,
        )

    def _seed_authority_relations(self, dsn, authority):
        payload = json.loads(authority.canonical_bytes)
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                for ordinal, record in enumerate(payload["supportRecords"]):
                    self._insert_authority_relation(
                        cur,
                        authority.content_key,
                        ordinal,
                        record["supportRecordKey"],
                    )
                self._insert_authority_parent(cur, authority)

    def _assert_relation_closure(self, dsn):
        import psycopg

        authority, records, alternate = self._relation_authority_fixture()
        self._seed_effect_documents(dsn, (*records, alternate))
        record_keys = [record.content_key for record in records]

        def rejected(rows):
            with self.assertRaises(psycopg.Error):
                with self._connect(dsn) as conn:
                    with conn.cursor() as cur:
                        self._insert_authority_parent(cur, authority)
                        for ordinal, key in rows:
                            self._insert_authority_relation(
                                cur, authority.content_key, ordinal, key,
                            )

        cases = {
            "missing": list(enumerate(record_keys[:-1])),
            "extra": [*enumerate(record_keys), (len(record_keys), record_keys[-1])],
            "gap": [(0, record_keys[0]), (2, record_keys[1])],
            "reorder": [(0, record_keys[1]), (1, record_keys[0])],
            "substitution": [(0, alternate.content_key), (1, record_keys[1])],
            "duplicate": [(0, record_keys[0]), (0, record_keys[1])],
        }
        for label, rows in cases.items():
            with self.subTest(label=label):
                rejected(rows)

        parent_first, parent_first_records, _ = self._relation_authority_fixture(
            verified_at="2026-08-06T00:00:02Z",
        )
        self._seed_effect_documents(dsn, parent_first_records)
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                self._insert_authority_parent(cur, parent_first)
                for ordinal, record in enumerate(parent_first_records):
                    self._insert_authority_relation(
                        cur,
                        parent_first.content_key,
                        ordinal,
                        record.content_key,
                    )

        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                for ordinal, key in enumerate(record_keys):
                    self._insert_authority_relation(
                        cur, authority.content_key, ordinal, key,
                    )
                self._insert_authority_parent(cur, authority)
        return authority

    def _assert_null_safe_support_record_key_closure(self, dsn):
        import psycopg

        authority, records, _ = self._relation_authority_fixture(
            verified_at="2026-08-06T00:00:03Z",
        )
        self._seed_effect_documents(dsn, records)
        for label, replacement in (("missing", ...), ("null", None)):
            with self.subTest(support_record_key=label):
                payload = json.loads(authority.canonical_bytes)
                if replacement is ...:
                    payload["supportRecords"][0].pop("supportRecordKey")
                else:
                    payload["supportRecords"][0]["supportRecordKey"] = replacement
                raw = json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                malformed = SimpleNamespace(
                    content_key=(
                        "loadout-effect-authority:sha256:"
                        + hashlib.sha256(raw).hexdigest()
                    ),
                    schema_revision=authority.schema_revision,
                    canonical_bytes=raw,
                )
                with self.assertRaises(psycopg.Error) as raised:
                    with self._connect(dsn) as conn:
                        with conn.cursor() as cur:
                            self._insert_authority_parent(cur, malformed)
                            for ordinal, record in enumerate(records):
                                self._insert_authority_relation(
                                    cur,
                                    malformed.content_key,
                                    ordinal,
                                    record.content_key,
                                )
                self.assertEqual(raised.exception.sqlstate, "P0001")
                self.assertEqual(
                    raised.exception.diag.message_primary,
                    "loadout effect authority relations must exactly match canonical supportRecords",
                )

    def _assert_subject_substitution_rejected(self, dsn, authority):
        import psycopg

        payload = json.loads(authority.canonical_bytes)
        evidence = [
            {
                "scope": "loadout",
                "loadoutEffectAuthorityKey": authority.content_key,
                "recordOrdinal": ordinal,
                "subjectKind": subject["subjectKind"],
                "subjectKey": subject["subjectKey"],
                "subjectVariantSignature": subject["subjectVariantSignature"],
                "supportRecordKey": record["supportRecordKey"],
            }
            for ordinal, (subject, record) in enumerate(zip(
                payload["subjects"], payload["supportRecords"], strict=True,
            ))
        ]
        evidence[0]["subjectKind"] = "substituted"
        key = "resolved-loadout-v2:sha256:" + ("9" * 64)
        row_hash = "sha256:" + ("8" * 64)
        row = {
            "schemaRevision": "resolved-loadout-v2",
            "status": "ready",
            "resolvedLoadoutKey": key,
            "gearRuleRevision": "gear-rule-matrix-v1",
            "eligibilityContext": {"classKey": "mage", "specKey": "arcane"},
            "rowHash": row_hash,
            "exactAuthorityBySlot": [],
            "effectEvidenceByOccurrence": evidence,
            "loadoutEffectAuthorityKey": authority.content_key,
        }
        with self.assertRaises(psycopg.Error):
            with self._connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO cache.websim_gear_resolved_loadouts "
                        "(resolved_loadout_key, schema_revision, catalog_revision, "
                        "gear_rule_revision, exact_registry_revision, class_key, spec_key, "
                        "loadout_json, row_hash, exact_authority_by_slot_json, "
                        "effect_evidence_by_occurrence_json, loadout_effect_authority_key, "
                        "resolver_replay_context_json) VALUES "
                        "(%s, 'resolved-loadout-v2', NULL, 'gear-rule-matrix-v1', NULL, "
                        "'mage', 'arcane', %s::jsonb, %s, '[]'::jsonb, %s::jsonb, %s, "
                        "%s::jsonb)",
                        (
                            key,
                            json.dumps(row),
                            row_hash,
                            json.dumps(evidence),
                            authority.content_key,
                            json.dumps(self._valid_resolver_replay_context(
                                authority.content_key
                            )),
                        ),
                    )

    def _assert_v2_loadout_rejected(
        self,
        dsn,
        *,
        key,
        row_hash,
        evidence,
        authority_key,
        message,
    ):
        import psycopg

        with self.assertRaises(psycopg.Error) as raised:
            with self._connect(dsn) as conn:
                with conn.cursor() as cur:
                    self._insert_v2_loadout(
                        cur,
                        key=key,
                        row_hash=row_hash,
                        evidence=evidence,
                        authority_key=authority_key,
                    )
        self.assertEqual(raised.exception.sqlstate, "P0001")
        self.assertEqual(raised.exception.diag.message_primary, message)

    def _assert_slot_occurrence_boundary(self, dsn):
        valid = {
            "scope": "slot",
            "slot": "head",
            "exactAuthorityEnvelopeKey": "exact-authority:sha256:" + "a" * 64,
            "recordOrdinal": 0,
            "subjectKind": "item",
            "subjectKey": "item:123",
            "subjectVariantSignature": "variant:head",
            "supportRecordKey": "simc-item-effect-record:sha256:" + "b" * 64,
        }
        malformed = (
            ("missing-key", {key: value for key, value in valid.items() if key != "supportRecordKey"}),
            ("null-value", valid | {"subjectKey": None}),
            ("wrong-type-subject", valid | {"subjectKind": True}),
            ("extra-key", valid | {"unexpected": "value"}),
        )
        for ordinal, (label, occurrence) in enumerate(malformed, start=7):
            with self.subTest(slot_occurrence=label):
                self._assert_v2_loadout_rejected(
                    dsn,
                    key="resolved-loadout-v2:sha256:" + format(ordinal, "x") * 64,
                    row_hash="sha256:" + format(ordinal, "x") * 64,
                    evidence=[occurrence],
                    authority_key=None,
                    message="v2 slot effect occurrence is invalid",
                )

    def _assert_conditional_effect_evidence_rejected(self, dsn, authority):
        self._assert_v2_loadout_rejected(
            dsn,
            key="resolved-loadout-v2:sha256:" + "4" * 64,
            row_hash="sha256:" + "4" * 64,
            evidence=[{"scope": "loadout"}],
            authority_key=None,
            message="v2 no-effect rows cannot contain loadout occurrences",
        )
        self._assert_v2_loadout_rejected(
            dsn,
            key="resolved-loadout-v2:sha256:" + "5" * 64,
            row_hash="sha256:" + "5" * 64,
            evidence=[],
            authority_key=authority.content_key,
            message="v2 loadout effect occurrence count mismatch",
        )

    def _assert_task4l_subject_shape_and_binding(self, dsn, authority):
        evidence = self._loadout_occurrences(authority)
        def remove_status(subject):
            subject.pop("status")

        def unverified_status(subject):
            subject["status"] = "partial"

        def null_subject_key(subject):
            subject["subjectKey"] = None

        def extra_subject_key(subject):
            subject["unexpected"] = "value"

        def numeric_subject_key(subject):
            subject["subjectKey"] = 123

        def text_subject_key(subject):
            subject["subjectKey"] = "123"

        def occurrence_subject_key_as_text(evidence):
            evidence[0]["subjectKey"] = "123"

        def occurrence_subject_key_as_number(evidence):
            evidence[0]["subjectKey"] = 123

        for ordinal, (label, mutate_subject, mutate_occurrence, message) in enumerate((
            ("missing-status", remove_status, None, "v2 loadout effect relation mismatch"),
            ("unverified-status", unverified_status, None, "v2 loadout effect relation mismatch"),
            ("null-subject-key", null_subject_key, None, "v2 loadout effect occurrence is invalid"),
            ("extra-subject-key", extra_subject_key, None, "v2 loadout effect relation mismatch"),
            (
                "wrong-type-canonical-subject",
                numeric_subject_key,
                occurrence_subject_key_as_text,
                "v2 loadout effect relation mismatch",
            ),
            (
                "wrong-type-occurrence-subject",
                text_subject_key,
                occurrence_subject_key_as_number,
                "v2 loadout effect occurrence is invalid",
            ),
        ), start=2):
            with self.subTest(task4l_subject=label):
                mutated = self._mutated_authority(authority, mutate_subject)
                self._seed_authority_relations(dsn, mutated)
                mutated_evidence = self._loadout_occurrences(mutated)
                if mutate_occurrence is not None:
                    mutate_occurrence(mutated_evidence)
                self._assert_v2_loadout_rejected(
                    dsn,
                    key="resolved-loadout-v2:sha256:" + format(ordinal, "x") * 64,
                    row_hash="sha256:" + format(ordinal, "x") * 64,
                    evidence=mutated_evidence,
                    authority_key=mutated.content_key,
                    message=message,
                )

    def _assert_v1_catalog_parent_references_rejected(self, dsn, catalog_revision):
        import psycopg

        cases = (
            (
                "delete",
                "DELETE FROM cache.websim_gear_catalog_revisions "
                "WHERE catalog_revision = %s",
                (catalog_revision,),
                "23503",
            ),
            (
                "update",
                "UPDATE cache.websim_gear_catalog_revisions "
                "SET catalog_revision = %s WHERE catalog_revision = %s",
                ("gear-catalog:sha256:" + "f" * 64, catalog_revision),
                "23503",
            ),
            (
                "truncate",
                "TRUNCATE cache.websim_gear_catalog_revisions",
                (),
                "0A000",
            ),
        )
        for label, statement, params, sqlstate in cases:
            with self.subTest(catalog_parent_action=label):
                conn = self._connect(dsn)
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "ALTER TABLE cache.websim_gear_catalog_revisions "
                            "DISABLE TRIGGER trg_websim_gear_catalog_revisions_immutable"
                        )
                        with self.assertRaises(psycopg.Error) as raised:
                            cur.execute(statement, params)
                        self.assertEqual(raised.exception.sqlstate, sqlstate)
                finally:
                    conn.rollback()
                    conn.close()

    def _assert_v1_conditional_integrity_rejected(
        self,
        dsn,
        v1_loadout,
        v1_snapshot,
    ):
        import psycopg

        def rejected_loadout(label, *, payload_field, column_field, value):
            payload = json.loads(json.dumps(v1_loadout))
            payload["resolvedLoadoutKey"] = (
                "resolved-loadout:sha256:" + label * 64
            )
            payload["rowHash"] = "sha256:" + (label * 64)
            payload[payload_field] = (
                value
                if payload_field == "catalogRevision"
                else v1_loadout[payload_field]
            )
            columns = {
                "catalogRevision": payload["catalogRevision"],
                "gearRuleRevision": payload["gearRuleRevision"],
                "exactRegistryRevision": payload["exactRegistryRevision"],
            }
            columns[column_field] = value
            with self.assertRaises(psycopg.Error):
                with self._connect(dsn) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO cache.websim_gear_resolved_loadouts "
                            "(resolved_loadout_key, schema_revision, catalog_revision, "
                            "gear_rule_revision, exact_registry_revision, class_key, spec_key, "
                            "loadout_json, row_hash) VALUES "
                            "(%s, 'resolved-loadout-v1', %s, %s, %s, %s, %s, %s::jsonb, %s)",
                            (
                                payload["resolvedLoadoutKey"],
                                columns["catalogRevision"],
                                columns["gearRuleRevision"],
                                columns["exactRegistryRevision"],
                                payload["eligibilityContext"]["classKey"],
                                payload["eligibilityContext"]["specKey"],
                                json.dumps(payload),
                                payload["rowHash"],
                            ),
                        )

        rejected_loadout(
            "a",
            payload_field="catalogRevision",
            column_field="catalogRevision",
            value="gear-catalog:sha256:" + ("0" * 64),
        )
        rejected_loadout(
            "b",
            payload_field="exactRegistryRevision",
            column_field="exactRegistryRevision",
            value="gear-exact-registry:sha256:" + ("1" * 64),
        )
        rejected_loadout(
            "c",
            payload_field="gearRuleRevision",
            column_field="gearRuleRevision",
            value="gear-rule-matrix-other",
        )

        def rejected_snapshot(label, *, payload_field, column_field, value):
            payload = json.loads(json.dumps(v1_snapshot))
            payload["simulationSnapshotKey"] = (
                "simulation-snapshot:sha256:" + label * 64
            )
            payload["rowHash"] = "sha256:" + label * 64
            payload[payload_field] = (
                value
                if payload_field == "catalogRevision"
                else v1_snapshot[payload_field]
            )
            columns = {
                "catalogRevision": payload["catalogRevision"],
                "gearRuleRevision": payload["gearRuleRevision"],
            }
            columns[column_field] = value
            with self.assertRaises(psycopg.Error):
                with self._connect(dsn) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO cache.websim_simulation_snapshots "
                            "(simulation_snapshot_key, schema_revision, resolved_loadout_key, "
                            "talent_profile_key, compiler_revision, simc_runtime_revision, "
                            "canonical_input_hash, catalog_revision, gear_rule_revision, "
                            "snapshot_json, row_hash) VALUES "
                            "(%s, 'simulation-snapshot-v1', %s, %s, %s, %s, %s, %s, %s, "
                            "%s::jsonb, %s)",
                            (
                                payload["simulationSnapshotKey"],
                                payload["resolvedLoadoutKey"],
                                payload["talentProfileKey"],
                                payload["compilerRevision"],
                                payload["simcRuntimeRevision"],
                                payload["canonicalInputHash"],
                                columns["catalogRevision"],
                                columns["gearRuleRevision"],
                                json.dumps(payload),
                                payload["rowHash"],
                            ),
                        )

        rejected_snapshot(
            "d",
            payload_field="catalogRevision",
            column_field="catalogRevision",
            value="gear-catalog:sha256:" + ("0" * 64),
        )
        rejected_snapshot(
            "e",
            payload_field="gearRuleRevision",
            column_field="gearRuleRevision",
            value="gear-rule-matrix-other",
        )

    def _assert_cross_version_rejected(
        self,
        dsn,
        v1_loadout_key,
        catalog_revision,
        *,
        v2_loadout_key,
    ):
        v2_snapshot_key = "simulation-snapshot-v2:sha256:" + "e" * 64
        v2_snapshot_hash = "sha256:" + "f" * 64
        v1_snapshot_key = "simulation-snapshot:sha256:" + "a" * 64
        v1_snapshot_hash = "sha256:" + "b" * 64
        input_hash = "simc-input:sha256:" + ("0" * 64)
        talent_key = "talent-profile:sha256:" + ("1" * 64)
        v2_snapshot = {
            "schemaRevision": "simulation-snapshot-v2",
            "status": "ready",
            "simulationSnapshotKey": v2_snapshot_key,
            "resolvedLoadoutKey": v1_loadout_key,
            "talentProfileKey": talent_key,
            "compilerRevision": "compiler-v2",
            "simcRuntimeRevision": "simc-runtime-v2",
            "canonicalInputHash": input_hash,
            "exactAuthorityBySlot": [],
            "effectEvidenceByOccurrence": [],
            "rowHash": v2_snapshot_hash,
        }
        v1_snapshot = {
            "schemaRevision": "simulation-snapshot-v1",
            "status": "ready",
            "simulationSnapshotKey": v1_snapshot_key,
            "resolvedLoadoutKey": v2_loadout_key,
            "talentProfileKey": talent_key,
            "compilerRevision": "compiler-v1",
            "simcRuntimeRevision": "simc-runtime-v1",
            "canonicalInputHash": input_hash,
            "catalogRevision": catalog_revision,
            "gearRuleRevision": "gear-rule-matrix-v1",
            "rowHash": v1_snapshot_hash,
        }

        cases = (
            (
                "v2-snapshot-to-v1-loadout",
                "simulation-snapshot-v2",
                (
                    v2_snapshot_key,
                    v1_loadout_key,
                    talent_key,
                    input_hash,
                    json.dumps(v2_snapshot),
                    v2_snapshot_hash,
                ),
                "v2 snapshot must bind its persisted ResolvedLoadout effect relation",
            ),
            (
                "v1-snapshot-to-v2-loadout",
                "simulation-snapshot-v1",
                (
                    v1_snapshot_key,
                    v2_loadout_key,
                    talent_key,
                    input_hash,
                    catalog_revision,
                    json.dumps(v1_snapshot),
                    v1_snapshot_hash,
                ),
                "v1 snapshot must bind its v1 ResolvedLoadout",
            ),
        )
        for label, schema_revision, params, message in cases:
            with self.subTest(cross_version=label):
                conn = self._connect(dsn)
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "ALTER TABLE cache.websim_simulation_snapshots "
                            "DROP CONSTRAINT websim_simulation_snapshots_v1_v2_fields_check"
                        )
                        if schema_revision == "simulation-snapshot-v2":
                            statement = (
                                "INSERT INTO cache.websim_simulation_snapshots "
                                "(simulation_snapshot_key, schema_revision, resolved_loadout_key, "
                                "talent_profile_key, compiler_revision, simc_runtime_revision, "
                                "canonical_input_hash, catalog_revision, gear_rule_revision, "
                                "snapshot_json, row_hash, exact_authority_by_slot_json, "
                                "effect_evidence_by_occurrence_json, loadout_effect_authority_key) "
                                "VALUES (%s, 'simulation-snapshot-v2', %s, %s, 'compiler-v2', "
                                "'simc-runtime-v2', %s, NULL, NULL, %s::jsonb, %s, "
                                "'[]'::jsonb, '[]'::jsonb, NULL)"
                            )
                        else:
                            statement = (
                                "INSERT INTO cache.websim_simulation_snapshots "
                                "(simulation_snapshot_key, schema_revision, resolved_loadout_key, "
                                "talent_profile_key, compiler_revision, simc_runtime_revision, "
                                "canonical_input_hash, catalog_revision, gear_rule_revision, "
                                "snapshot_json, row_hash) VALUES "
                                "(%s, 'simulation-snapshot-v1', %s, %s, 'compiler-v1', "
                                "'simc-runtime-v1', %s, %s, 'gear-rule-matrix-v1', %s::jsonb, %s)"
                            )
                        self._assert_pg_rejected(
                            cur,
                            statement,
                            params,
                            sqlstate="P0001",
                            message=message,
                        )
                finally:
                    conn.rollback()
                    conn.close()

    def _assert_v2_store_round_trips(self, dsn):
        from server.gear_canonical_kernel import canonical_json_bytes
        from server.gear_exact_authority_store import GearExactAuthorityStore
        from server.gear_resolved_loadout import build_resolved_loadout_v2
        from server.simc_item_effect_support import reload_effect_record
        from server.simulation_snapshot import build_simulation_snapshot_v2
        from server.simulation_snapshot_store import SimulationSnapshotStore
        from tests.gear_resolved_loadout_test import (
            active_v2_loadout_fixture,
            v2_bundle,
            v2_resolver_snapshot,
        )
        from tests.simulation_snapshot_test import (
            TALENT_KEY,
            TALENT_LINES,
            character_context,
            scenario,
        )

        authority_store = GearExactAuthorityStore(lambda: self._connect(dsn))
        snapshot_store = SimulationSnapshotStore(lambda: self._connect(dsn))

        no_effect_resolver = v2_resolver_snapshot()
        no_effect_resolver["resolvedSlots"] = {
            "finger1": {
                "slot": "finger1",
                "itemId": "1001",
                "legality": {"status": "verified"},
            },
            "finger2": {
                "slot": "finger2",
                "itemId": "1002",
                "legality": {"status": "verified"},
            },
        }
        no_effect_resolver["profileReadiness"] = {
            "status": "verified",
            "simcReady": True,
            "requiredSlots": ["finger1", "finger2"],
            "readySlots": ["finger1", "finger2"],
            "simcRuntimeRevision": "simc-runtime-v2",
        }
        no_effect_left = v2_bundle("finger1", "1001", ["A"])
        no_effect_right = v2_bundle("finger2", "1002", ["B"])
        no_effect_bundles = {
            no_effect_left.envelope.content_key: no_effect_left,
            no_effect_right.envelope.content_key: no_effect_right,
        }
        no_effect_loadout = build_resolved_loadout_v2(
            resolver_snapshot=no_effect_resolver,
            exact_authority_by_slot=[
                {
                    "slot": "finger2",
                    "exactAuthorityEnvelopeKey": no_effect_right.envelope.content_key,
                },
                {
                    "slot": "finger1",
                    "exactAuthorityEnvelopeKey": no_effect_left.envelope.content_key,
                },
            ],
            authority_bundles=no_effect_bundles,
            gear_rule_revision="gear-rule-matrix-v1",
            resolver_revision="resolver-v2",
            simc_runtime_revision="simc-runtime-v2",
        )
        no_effect_snapshot = build_simulation_snapshot_v2(
            resolved_loadout=no_effect_loadout,
            talent_profile_key=TALENT_KEY,
            talent_lines=TALENT_LINES,
            character_context=character_context(
                no_effect_resolver["eligibilityContext"]["classKey"],
                no_effect_resolver["eligibilityContext"]["specKey"],
            ),
            scenario_options=scenario(),
            preparation_lines=["optimal_raid=0"],
            compiler_revision="simc-profile-compiler-v2",
            simc_runtime_revision="simc-runtime-v2",
            resolver_snapshot=no_effect_resolver,
            authority_bundles=no_effect_bundles,
        )
        no_effect_loadout["originCatalogRevision"] = "task3b-catalog-origin-a"
        no_effect_snapshot["originCatalogRevision"] = "task3b-catalog-origin-a"
        for bundle in no_effect_bundles.values():
            self.assertEqual(authority_store.seal_authority_bundle(bundle), bundle)
        self.assertEqual(
            snapshot_store.seal_loadout(
                no_effect_loadout,
                resolver_snapshot=no_effect_resolver,
                authority_bundles=no_effect_bundles,
            ),
            no_effect_loadout,
        )
        self.assertEqual(
            snapshot_store.seal_snapshot(
                no_effect_snapshot,
                resolved_loadout=no_effect_loadout,
                resolver_snapshot=no_effect_resolver,
                authority_bundles=no_effect_bundles,
                compiler_revision="simc-profile-compiler-v2",
            ),
            no_effect_snapshot,
        )
        self.assertEqual(
            snapshot_store.load_loadout(no_effect_loadout["resolvedLoadoutKey"]),
            no_effect_loadout,
        )
        self.assertEqual(
            snapshot_store.load_snapshot(
                no_effect_snapshot["simulationSnapshotKey"],
                include_result=False,
            ),
            no_effect_snapshot,
        )

        active_resolver, loadout_authority, _, _ = active_v2_loadout_fixture()
        slot = active_resolver["profileReadiness"]["requiredSlots"][0]
        active_bundle = v2_bundle(
            slot,
            active_resolver["resolvedSlots"][slot]["itemId"],
            ["A", "B", "A"],
        )
        active_bundles = {active_bundle.envelope.content_key: active_bundle}
        active_loadout = build_resolved_loadout_v2(
            resolver_snapshot=active_resolver,
            exact_authority_by_slot=[{
                "slot": slot,
                "exactAuthorityEnvelopeKey": active_bundle.envelope.content_key,
            }],
            authority_bundles=active_bundles,
            gear_rule_revision="gear-rule-matrix-v1",
            resolver_revision="resolver-v2",
            simc_runtime_revision="simc-runtime-v2",
            loadout_effect_authority=loadout_authority,
        )
        active_loadout["originCatalogRevision"] = "task3b-catalog-origin-b"
        active_snapshot = build_simulation_snapshot_v2(
            resolved_loadout=active_loadout,
            talent_profile_key=TALENT_KEY,
            talent_lines=TALENT_LINES,
            character_context=character_context(
                active_resolver["eligibilityContext"]["classKey"],
                active_resolver["eligibilityContext"]["specKey"],
            ),
            scenario_options=scenario(),
            preparation_lines=["optimal_raid=0"],
            compiler_revision="simc-profile-compiler-v2",
            simc_runtime_revision="simc-runtime-v2",
            resolver_snapshot=active_resolver,
            authority_bundles=active_bundles,
            loadout_effect_authority=loadout_authority,
        )
        active_snapshot["originCatalogRevision"] = "task3b-catalog-origin-b"
        slot_evidence = [
            occurrence
            for occurrence in active_loadout["effectEvidenceByOccurrence"]
            if occurrence["scope"] == "slot"
            and occurrence["subjectKey"] in {"A", "B"}
        ]
        self.assertEqual(
            [occurrence["subjectKey"] for occurrence in slot_evidence],
            ["A", "B", "A"],
        )
        self.assertEqual(
            slot_evidence[0]["supportRecordKey"],
            slot_evidence[2]["supportRecordKey"],
        )
        self.assertNotEqual(
            slot_evidence[0]["supportRecordKey"],
            slot_evidence[1]["supportRecordKey"],
        )

        self.assertEqual(
            authority_store.seal_authority_bundle(active_bundle),
            active_bundle,
        )
        authority_payload = json.loads(loadout_authority.canonical_bytes)
        loadout_effect_records = {}
        for embedded in authority_payload["supportRecords"]:
            record_payload = dict(embedded)
            record_key = record_payload.pop("supportRecordKey")
            record = reload_effect_record(
                canonical_json_bytes(record_payload),
                record_key,
                runtime_revision=active_resolver["dependencyVector"][
                    "simcRuntimeRevision"
                ],
            )
            self.assertEqual(record.content_key, record_key)
            loadout_effect_records[record.content_key] = record
        self._seed_effect_documents(dsn, loadout_effect_records.values())

        self.assertEqual(
            snapshot_store.seal_loadout(
                active_loadout,
                resolver_snapshot=active_resolver,
                authority_bundles=active_bundles,
                loadout_effect_authority=loadout_authority,
            ),
            active_loadout,
        )
        self.assertEqual(
            snapshot_store.seal_snapshot(
                active_snapshot,
                resolved_loadout=active_loadout,
                resolver_snapshot=active_resolver,
                authority_bundles=active_bundles,
                compiler_revision="simc-profile-compiler-v2",
                loadout_effect_authority=loadout_authority,
            ),
            active_snapshot,
        )
        self.assertEqual(
            snapshot_store.load_loadout(active_loadout["resolvedLoadoutKey"]),
            active_loadout,
        )
        self.assertEqual(
            snapshot_store.load_snapshot(
                active_snapshot["simulationSnapshotKey"],
                include_result=False,
            ),
            active_snapshot,
        )

        stored_replays = {}
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                for loadout, snapshot, origin, authority_key in (
                    (
                        no_effect_loadout,
                        no_effect_snapshot,
                        "task3b-catalog-origin-a",
                        None,
                    ),
                    (
                        active_loadout,
                        active_snapshot,
                        "task3b-catalog-origin-b",
                        loadout_authority.content_key,
                    ),
                ):
                    cur.execute(
                        "SELECT catalog_revision, loadout_effect_authority_key, "
                        "resolver_replay_context_json::text "
                        "FROM cache.websim_gear_resolved_loadouts "
                        "WHERE resolved_loadout_key = %s",
                        (loadout["resolvedLoadoutKey"],),
                    )
                    stored_origin, stored_authority, stored_replay = cur.fetchone()
                    self.assertEqual(stored_origin, origin)
                    self.assertEqual(stored_authority, authority_key)
                    self.assertEqual(
                        json.loads(stored_replay)["schemaRevision"],
                        "exact-resolver-replay-context-v1",
                    )
                    stored_replays[loadout["resolvedLoadoutKey"]] = json.loads(
                        stored_replay
                    )
                    cur.execute(
                        "SELECT catalog_revision, loadout_effect_authority_key "
                        "FROM cache.websim_simulation_snapshots "
                        "WHERE simulation_snapshot_key = %s",
                        (snapshot["simulationSnapshotKey"],),
                    )
                    self.assertEqual(cur.fetchone(), (origin, authority_key))
                cur.execute(
                    "SELECT ordinal, effect_record_key "
                    "FROM cache.websim_effect_aggregate_records "
                    "WHERE effect_support_key = %s ORDER BY ordinal",
                    (active_bundle.effect_support.content_key,),
                )
                exact_relations = cur.fetchall()
                self.assertEqual(
                    exact_relations,
                    [
                        (ordinal, record.content_key)
                        for ordinal, record in enumerate(active_bundle.effect_records)
                    ],
                )
                self.assertEqual(
                    exact_relations[1][1],
                    exact_relations[3][1],
                )
                self.assertNotEqual(
                    exact_relations[0][1],
                    exact_relations[1][1],
                )
                cur.execute(
                    "SELECT ordinal, effect_record_key "
                    "FROM cache.websim_loadout_effect_authority_records "
                    "WHERE loadout_effect_authority_key = %s ORDER BY ordinal",
                    (loadout_authority.content_key,),
                )
                self.assertEqual(
                    cur.fetchall(),
                    [
                        (ordinal, record["supportRecordKey"])
                        for ordinal, record in enumerate(
                            authority_payload["supportRecords"]
                        )
                    ],
                )

        return {
            "no_effect": {
                "resolver": no_effect_resolver,
                "bundles": no_effect_bundles,
                "loadout": no_effect_loadout,
                "snapshot": no_effect_snapshot,
                "replay": stored_replays[no_effect_loadout["resolvedLoadoutKey"]],
            },
            "active": {
                "resolver": active_resolver,
                "bundles": active_bundles,
                "loadout": active_loadout,
                "snapshot": active_snapshot,
                "replay": stored_replays[active_loadout["resolvedLoadoutKey"]],
                "loadoutEffectAuthority": loadout_authority,
            },
        }

    def _assert_v2_pair_representation_boundary(self, dsn, fixtures):
        import copy
        import psycopg

        base = fixtures["no_effect"]
        original_pairs = base["loadout"]["exactAuthorityBySlot"]
        self.assertEqual([pair["slot"] for pair in original_pairs], [
            "finger1",
            "finger2",
        ])
        self.assertIsNone(base["loadout"].get("loadoutEffectAuthorityKey"))

        def loadout_identity(label):
            digest = hashlib.sha256(
                ("task3b-pair-" + label).encode("utf-8")
            ).hexdigest()
            return (
                "resolved-loadout-v2:sha256:" + digest,
                "sha256:" + digest,
            )

        pair_mutations = []
        no_pairs = []
        pair_mutations.append(("no-pairs", no_pairs, None))
        pair_mutations.append(("missing-pair", original_pairs[:1], None))
        pair_mutations.append((
            "extra-pair",
            original_pairs + [copy.deepcopy(original_pairs[0])],
            None,
        ))
        pair_mutations.append(("reordered-pairs", list(reversed(original_pairs)), None))
        substituted = copy.deepcopy(original_pairs)
        substituted[0]["exactAuthorityEnvelopeKey"] = original_pairs[1][
            "exactAuthorityEnvelopeKey"
        ]
        pair_mutations.append(("substituted-pair", substituted, None))
        mismatched_occurrences = copy.deepcopy(
            base["loadout"]["effectEvidenceByOccurrence"]
        )
        first_slot_occurrence = next(
            occurrence
            for occurrence in mismatched_occurrences
            if occurrence["scope"] == "slot"
        )
        first_slot_occurrence["exactAuthorityEnvelopeKey"] = original_pairs[1][
            "exactAuthorityEnvelopeKey"
        ]
        pair_mutations.append((
            "substituted-slot-occurrence-pair",
            original_pairs,
            mismatched_occurrences,
        ))

        for label, pairs, evidence in pair_mutations:
            with self.subTest(v2_pair_representation=label):
                row = copy.deepcopy(base["loadout"])
                row["resolvedLoadoutKey"], row["rowHash"] = loadout_identity(label)
                row["exactAuthorityBySlot"] = copy.deepcopy(pairs)
                if evidence is not None:
                    row["effectEvidenceByOccurrence"] = evidence
                with self.assertRaises(psycopg.Error) as raised:
                    with self._connect(dsn) as conn:
                        with conn.cursor() as cur:
                            self._insert_v2_loadout_representation(
                                cur,
                                row,
                                base["replay"],
                            )
                self.assertEqual(raised.exception.sqlstate, "P0001")
                self.assertEqual(
                    raised.exception.diag.message_primary,
                    "v2 exact authority pairs are inconsistent",
                )

        snapshot = copy.deepcopy(base["snapshot"])
        snapshot_digest = hashlib.sha256(
            b"task3b-snapshot-loadout-pair-mismatch"
        ).hexdigest()
        snapshot["simulationSnapshotKey"] = (
            "simulation-snapshot-v2:sha256:" + snapshot_digest
        )
        snapshot["rowHash"] = "sha256:" + snapshot_digest
        snapshot["exactAuthorityBySlot"] = list(reversed(original_pairs))
        with self.assertRaises(psycopg.Error) as raised:
            with self._connect(dsn) as conn:
                with conn.cursor() as cur:
                    self._insert_v2_snapshot_representation(cur, snapshot)
        self.assertEqual(raised.exception.sqlstate, "P0001")
        self.assertEqual(
            raised.exception.diag.message_primary,
            "v2 snapshot must bind its persisted ResolvedLoadout effect relation",
        )

    def _assert_acl(self, dsn):
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_catalog.has_table_privilege("
                    "'wow_app', 'cache.websim_gear_resolved_loadouts'::regclass, "
                    "'INSERT')"
                )
                self.assertIs(cur.fetchone()[0], True)
                for table in (
                    "websim_loadout_effect_authorities",
                    "websim_loadout_effect_authority_records",
                ):
                    cur.execute(
                        "SELECT pg_catalog.has_table_privilege("
                        "'wow_app', %s::regclass, 'SELECT'), "
                        "pg_catalog.has_table_privilege('wow_app', %s::regclass, 'INSERT'), "
                        "pg_catalog.has_table_privilege('wow_app', %s::regclass, 'UPDATE'), "
                        "pg_catalog.has_table_privilege('wow_app', %s::regclass, 'DELETE'), "
                        "pg_catalog.has_table_privilege('wow_app', %s::regclass, 'TRUNCATE')",
                        tuple([f"cache.{table}"] * 5),
                    )
                    self.assertEqual(cur.fetchone(), (True, False, False, False, False))

    def test_fresh_0031_and_upgrade_0030_to_0031(self):
        self.assertEqual(
            TASK_3B_MIGRATIONS[-1].name,
            "0031_websim_exact_snapshot_v2.sql",
        )
        self.assertEqual(
            TASK_3B_BASELINE_MIGRATIONS[-1].name,
            "0030_websim_exact_authority_bundle.sql",
        )
        self.assertNotEqual(TASK_3B_FRESH_DSN, TASK_3B_UPGRADE_DSN)
        git_identity = self._git_identity()
        fresh_identity = self._assert_empty_disposable(TASK_3B_FRESH_DSN, "fresh")
        upgrade_identity = self._assert_empty_disposable(TASK_3B_UPGRADE_DSN, "upgrade")

        self._apply(TASK_3B_FRESH_DSN, TASK_3B_MIGRATIONS)
        fresh_loadout, fresh_snapshot, _, _ = self._seal_v1_pair(
            TASK_3B_FRESH_DSN,
        )
        authority = self._assert_relation_closure(TASK_3B_FRESH_DSN)
        fresh_v2 = self._assert_v2_store_round_trips(TASK_3B_FRESH_DSN)
        self._assert_v2_pair_representation_boundary(TASK_3B_FRESH_DSN, fresh_v2)
        self._assert_null_safe_support_record_key_closure(TASK_3B_FRESH_DSN)
        self._assert_task4l_subject_shape_and_binding(
            TASK_3B_FRESH_DSN,
            authority,
        )
        self._assert_conditional_effect_evidence_rejected(
            TASK_3B_FRESH_DSN,
            authority,
        )
        self._assert_subject_substitution_rejected(TASK_3B_FRESH_DSN, authority)
        self._assert_slot_occurrence_boundary(TASK_3B_FRESH_DSN)
        self._assert_resolver_replay_context_boundary(TASK_3B_FRESH_DSN)
        self._assert_v1_conditional_integrity_rejected(
            TASK_3B_FRESH_DSN,
            fresh_loadout,
            fresh_snapshot,
        )
        self._assert_v1_catalog_parent_references_rejected(
            TASK_3B_FRESH_DSN,
            fresh_loadout["catalogRevision"],
        )
        self._assert_cross_version_rejected(
            TASK_3B_FRESH_DSN,
            fresh_loadout["resolvedLoadoutKey"],
            fresh_loadout["catalogRevision"],
            v2_loadout_key=fresh_v2["no_effect"]["loadout"][
                "resolvedLoadoutKey"
            ],
        )
        self._assert_acl(TASK_3B_FRESH_DSN)

        self._apply(TASK_3B_UPGRADE_DSN, TASK_3B_BASELINE_MIGRATIONS)
        upgrade_loadout, upgrade_snapshot, before_loadout, before_snapshot = (
            self._seal_v1_pair(TASK_3B_UPGRADE_DSN)
        )
        self._apply(TASK_3B_UPGRADE_DSN, TASK_3B_MIGRATIONS[-1:])
        with self._connect(TASK_3B_UPGRADE_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT resolved_loadout_key, schema_revision, catalog_revision, "
                    "gear_rule_revision, exact_registry_revision, class_key, spec_key, "
                    "loadout_json::text, row_hash, sealed_at "
                    "FROM cache.websim_gear_resolved_loadouts"
                )
                self.assertEqual(cur.fetchone(), before_loadout)
                cur.execute(
                    "SELECT simulation_snapshot_key, schema_revision, resolved_loadout_key, "
                    "talent_profile_key, compiler_revision, simc_runtime_revision, "
                    "canonical_input_hash, catalog_revision, gear_rule_revision, "
                    "snapshot_json::text, row_hash, sealed_at "
                    "FROM cache.websim_simulation_snapshots"
                )
                self.assertEqual(cur.fetchone(), before_snapshot)
                cur.execute(
                    "SELECT exact_authority_by_slot_json, "
                    "effect_evidence_by_occurrence_json, "
                    "loadout_effect_authority_key, resolver_replay_context_json "
                    "FROM cache.websim_gear_resolved_loadouts"
                )
                self.assertEqual(cur.fetchone(), ([], [], None, None))
                cur.execute(
                    "SELECT exact_authority_by_slot_json, "
                    "effect_evidence_by_occurrence_json, "
                    "loadout_effect_authority_key "
                    "FROM cache.websim_simulation_snapshots"
                )
                self.assertEqual(cur.fetchone(), ([], [], None))
                cur.execute(
                    "SELECT count(*) FROM ops.schema_migrations "
                    "WHERE id = '0031_websim_exact_snapshot_v2'"
                )
                self.assertEqual(cur.fetchone()[0], 1)
        upgrade_authority = self._assert_relation_closure(TASK_3B_UPGRADE_DSN)
        upgrade_v2 = self._assert_v2_store_round_trips(TASK_3B_UPGRADE_DSN)
        self._assert_v2_pair_representation_boundary(
            TASK_3B_UPGRADE_DSN,
            upgrade_v2,
        )
        self._assert_null_safe_support_record_key_closure(TASK_3B_UPGRADE_DSN)
        self._assert_conditional_effect_evidence_rejected(
            TASK_3B_UPGRADE_DSN,
            upgrade_authority,
        )
        self._assert_resolver_replay_context_boundary(TASK_3B_UPGRADE_DSN)
        self._assert_cross_version_rejected(
            TASK_3B_UPGRADE_DSN,
            upgrade_loadout["resolvedLoadoutKey"],
            upgrade_loadout["catalogRevision"],
            v2_loadout_key=upgrade_v2["no_effect"]["loadout"][
                "resolvedLoadoutKey"
            ],
        )
        self._assert_v1_conditional_integrity_rejected(
            TASK_3B_UPGRADE_DSN,
            upgrade_loadout,
            upgrade_snapshot,
        )
        self._assert_v1_catalog_parent_references_rejected(
            TASK_3B_UPGRADE_DSN,
            upgrade_loadout["catalogRevision"],
        )
        self._assert_acl(TASK_3B_UPGRADE_DSN)
        self.assertEqual(
            self._database_identity(TASK_3B_FRESH_DSN, "fresh"), fresh_identity,
        )
        self.assertEqual(
            self._database_identity(TASK_3B_UPGRADE_DSN, "upgrade"), upgrade_identity,
        )
        self.assertEqual(upgrade_snapshot["resolvedLoadoutKey"], upgrade_loadout["resolvedLoadoutKey"])
        self.assertEqual(self._git_identity(), git_identity)


@unittest.skipUnless(
    TASK_4W_CANDIDATE_CONFIGURED,
    "Task 4W requires psql plus explicit fresh, upgrade, migrator, app and worker 0032 DSNs",
)
class PostgresExactImportJobsCandidateTest(unittest.TestCase):
    """Cloud-only 0032 candidate; it never provisions, resets, or drops roles/databases."""

    PROJECT_SCHEMAS = (
        "identity", "app", "content", "cache", "knowledge", "analytics", "ops",
    )
    OPS_TABLES = (
        "ops.websim_exact_import_jobs",
        "ops.websim_exact_worker_state",
        "ops.websim_exact_import_metrics_daily",
    )
    AUTHORITY_TABLES = (
        "cache.websim_canonical_documents",
        "cache.websim_effect_aggregate_records",
        "cache.websim_exact_authority_bundles",
    )
    FUNCTION_SIGNATURES = (
        "ops.websim_exact_enqueue(text,bytea,jsonb)",
        "ops.websim_exact_read(text,bigint)",
        "ops.websim_exact_claim(text,text,text)",
        "ops.websim_exact_heartbeat(bigint,uuid)",
        "ops.websim_exact_terminalize(bigint,uuid,text,text,jsonb,jsonb,text)",
        "ops.websim_exact_update_worker_state(text,text,text,text,bigint,jsonb)",
        "ops.websim_exact_prune_jobs(integer)",
        "ops.websim_exact_prune_metrics(integer)",
    )
    APP_FUNCTIONS = frozenset(FUNCTION_SIGNATURES[:2])
    WORKER_FUNCTIONS = frozenset(FUNCTION_SIGNATURES[2:])

    @staticmethod
    def _connect(dsn):
        validate_task4w_candidate_run_id(TASK_4W_RUN_ID)
        import psycopg

        return psycopg.connect(dsn)

    def _database_identity(self, dsn, flavor):
        expected = (
            f"wow_exact_first_{flavor}_test_{TASK_4W_RUN_ID}",
            f"wow_exact_first_disposable:{TASK_4W_RUN_ID}:{flavor}",
        )
        with self._connect(dsn) as conn:
            self.assertEqual(conn.info.dbname, expected[0])
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_catalog.shobj_description(oid, 'pg_database') "
                    "FROM pg_catalog.pg_database WHERE datname = current_database()"
                )
                self.assertEqual(cur.fetchone()[0], expected[1])
        return expected

    def _assert_empty_disposable(self, dsn, flavor):
        identity = self._database_identity(dsn, flavor)
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT nspname FROM pg_catalog.pg_namespace "
                    "WHERE nspname = ANY(%s)",
                    (list(self.PROJECT_SCHEMAS),),
                )
                self.assertEqual(cur.fetchall(), [])
                cur.execute(
                    "SELECT rolname, rolcanlogin, rolinherit, rolsuper, rolcreatedb, "
                    "rolcreaterole, rolreplication, rolbypassrls "
                    "FROM pg_catalog.pg_roles "
                    "WHERE rolname = ANY(%s) ORDER BY rolname",
                    (["wow_app", "wow_exact_worker", "wow_migrator"],),
                )
                roles = {row[0]: row[1:] for row in cur.fetchall()}
                self.assertEqual(
                    set(roles),
                    {"wow_app", "wow_exact_worker", "wow_migrator"},
                )
                for login_role in ("wow_app", "wow_migrator"):
                    self.assertIs(roles[login_role][0], True)
                    self.assertIs(roles[login_role][4], False)
                worker_group = roles["wow_exact_worker"]
                self.assertIs(worker_group[0], False)
                self.assertTrue(all(value is False for value in worker_group[2:]))
        return identity

    def _apply(self, dsn, migrations):
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                for migration in migrations:
                    cur.execute(migration.read_text(encoding="utf-8"))

    @staticmethod
    def _request(worker_revision="exact-worker-v1"):
        from server.gear_exact_import_job_store import build_exact_import_job_request

        slots = {
            slot: {
                "itemId": "1001", "declaredItemLevel": 700,
                "bonusIds": [], "context": "", "gemIds": [],
                "gemBonusIds": [], "gemItemLevels": [], "enchantId": "",
                "craftedStats": [], "embellishmentIds": [],
                "redirectedBaseStats": [],
            }
            for slot in (
                "head", "neck", "shoulder", "back", "chest", "wrist", "hands",
                "waist", "legs", "feet", "finger1", "finger2", "trinket1",
                "trinket2", "main_hand",
            )
        }
        return build_exact_import_job_request(
            {
                "schemaRevision": "exact-loadout-intent-v2",
                "authoredAgainst": {
                    "seasonRevision": "season-1", "gameBuild": "12.0.1.12345",
                },
                "eligibilityContext": {
                    "classKey": "mage", "specKey": "frost", "level": 90,
                },
                "slots": slots,
            },
            {
                "seasonRevision": "season-1", "gameBuild": "12.0.1.12345",
                "gearRuleRevision": "gear-rule-v1", "resolverRevision": "resolver-v2",
                "compilerRevision": "compiler-v2", "workerRevision": worker_revision,
                "simcRuntimeRevision": "simc-runtime-v1",
                "effectAuthorityRevision": "effect-authority-v1",
            },
        )

    def _enqueue(self, owner, request):
        with self._connect(TASK_4W_APP_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM ops.websim_exact_enqueue(%s, %s, %s::jsonb)",
                    (owner, request.canonical_bytes, json.dumps(request.request_json)),
                )
                return cur.fetchone()

    def _assert_sensitive_jsonpath_boundary(self):
        import psycopg

        request = self._request("jsonpath-array-v1")
        head = request.request_json["exactLoadoutIntent"]["slots"]["head"]
        self.assertEqual(head["bonusIds"], [])

        sensitive_request_json = json.loads(request.canonical_bytes.decode("utf-8"))
        sensitive_request_json["exactLoadoutIntent"]["slots"]["head"]["nested"] = {
            "safe": [{"realm": "must-never-persist"}],
        }
        sensitive_request_bytes = json.dumps(
            sensitive_request_json,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            with self._connect(TASK_4W_APP_DSN) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT * FROM ops.websim_exact_enqueue(%s, %s, %s::jsonb)",
                        (
                            "sha256:" + "9" * 64,
                            sensitive_request_bytes,
                            json.dumps(sensitive_request_json),
                        ),
                    )

        resolved = self._enqueue("sha256:" + "7" * 64, request)
        self.assertEqual(
            resolved[1:],
            (request.request_key, "pending", False, None),
        )
        with self._connect(TASK_4W_WORKER_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SET ROLE wow_exact_worker")
                cur.execute(
                    "SELECT * FROM ops.websim_exact_claim(%s, %s, %s)",
                    ("jsonpath-worker", "exact-worker-v1", "simc-runtime-v1"),
                )
                resolved_claim = cur.fetchone()
                self.assertEqual(resolved_claim[1], request.request_key)
                cur.execute(
                    "SELECT * FROM ops.websim_exact_terminalize("
                    "%s, %s, 'resolved', 'resolved', %s::jsonb, NULL, %s)",
                    (
                        resolved_claim[0],
                        resolved_claim[4],
                        json.dumps({"status": "resolved", "items": []}),
                        f"jsonpath-resolved-{TASK_4W_RUN_ID}",
                    ),
                )
                self.assertEqual(cur.fetchone()[1], "resolved")

        problem_request = self._request("jsonpath-problem-array-v1")
        blocked = self._enqueue("sha256:" + "8" * 64, problem_request)
        with self._connect(TASK_4W_WORKER_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SET ROLE wow_exact_worker")
                cur.execute(
                    "SELECT * FROM ops.websim_exact_claim(%s, %s, %s)",
                    ("jsonpath-worker", "exact-worker-v1", "simc-runtime-v1"),
                )
                blocked_claim = cur.fetchone()
                self.assertEqual(blocked_claim[0], blocked[0])
                cur.execute(
                    "SELECT * FROM ops.websim_exact_terminalize("
                    "%s, %s, 'blocked', 'incomplete', NULL, %s::jsonb, %s)",
                    (
                        blocked_claim[0],
                        blocked_claim[4],
                        json.dumps({"code": "INCOMPLETE", "details": []}),
                        f"jsonpath-blocked-{TASK_4W_RUN_ID}",
                    ),
                )
                self.assertEqual(cur.fetchone()[1], "blocked")
                cur.execute(
                    "SELECT ops.websim_exact_update_worker_state("
                    "%s, 'idle', %s, %s, NULL, %s::jsonb)",
                    (
                        "jsonpath-worker",
                        "exact-worker-v1",
                        "simc-runtime-v1",
                        json.dumps({"status": "idle", "events": []}),
                    ),
                )

        with self.assertRaises(psycopg.errors.InvalidParameterValue):
            with self._connect(TASK_4W_WORKER_DSN) as conn:
                with conn.cursor() as cur:
                    cur.execute("SET ROLE wow_exact_worker")
                    cur.execute(
                        "SELECT ops.websim_exact_update_worker_state("
                        "%s, 'idle', %s, %s, NULL, %s::jsonb)",
                        (
                            "jsonpath-worker",
                            "exact-worker-v1",
                            "simc-runtime-v1",
                            json.dumps({"events": [{"realm": "must-never-persist"}]}),
                        ),
                    )

    def _assert_denied(self, dsn, statement, parameters=()):
        import psycopg

        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self._connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(statement, parameters)

    def _assert_role_logins(self):
        from server.gear_exact_authority_worker import establish_exact_worker_role

        expected_database = f"wow_exact_first_fresh_test_{TASK_4W_RUN_ID}"
        for dsn, role in (
            (TASK_4W_MIGRATOR_DSN, "wow_migrator"),
            (TASK_4W_APP_DSN, "wow_app"),
        ):
            with self._connect(dsn) as conn:
                self.assertEqual(conn.info.dbname, expected_database)
                with conn.cursor() as cur:
                    cur.execute("SELECT session_user, current_user")
                    self.assertEqual(cur.fetchone(), (role, role))
        with self._connect(TASK_4W_WORKER_DSN) as conn:
            self.assertEqual(conn.info.dbname, expected_database)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT session_user, current_user, login.rolcanlogin, "
                    "login.rolinherit, login.rolsuper, login.rolcreatedb, "
                    "login.rolcreaterole, login.rolreplication, login.rolbypassrls, "
                    "pg_catalog.pg_has_role(session_user, 'wow_exact_worker', 'MEMBER'), "
                    "pg_catalog.pg_has_role('wow_app', 'wow_exact_worker', 'MEMBER'), "
                    "pg_catalog.pg_has_role('wow_migrator', 'wow_exact_worker', 'MEMBER') "
                    "FROM pg_catalog.pg_roles AS login WHERE login.rolname = session_user"
                )
                row = cur.fetchone()
                self.assertNotIn(row[0], {"wow_app", "wow_migrator", "wow_exact_worker"})
                self.assertEqual(row[1], row[0])
                self.assertEqual(
                    row[2:],
                    (True, True, False, False, False, False, False, True, False, False),
                )
            establish_exact_worker_role(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT session_user, current_user")
                self.assertEqual(cur.fetchone(), (row[0], "wow_exact_worker"))

    def _assert_function_matrix(self, cur, principal, allowed):
        for signature in self.FUNCTION_SIGNATURES:
            cur.execute(
                "SELECT pg_catalog.has_function_privilege(%s, %s, 'EXECUTE')",
                (principal, signature),
            )
            self.assertIs(cur.fetchone()[0], signature in allowed)

    def _assert_public_function_boundary(self, cur):
        for signature in self.FUNCTION_SIGNATURES:
            cur.execute(
                "SELECT NOT EXISTS ("
                "SELECT 1 FROM pg_catalog.pg_proc AS proc "
                "CROSS JOIN LATERAL pg_catalog.aclexplode("
                "COALESCE(proc.proacl, pg_catalog.acldefault('f', proc.proowner))"
                ") AS privilege "
                "WHERE proc.oid = pg_catalog.to_regprocedure(%s) "
                "AND privilege.grantee = 0 "
                "AND privilege.privilege_type = 'EXECUTE'"
                ")",
                (signature,),
            )
            self.assertIs(cur.fetchone()[0], True)

    def _assert_no_direct_ops(self, cur, principal):
        for table in self.OPS_TABLES:
            cur.execute(
                "SELECT "
                "pg_catalog.has_table_privilege(%s, %s, 'SELECT'), "
                "pg_catalog.has_table_privilege(%s, %s, 'INSERT'), "
                "pg_catalog.has_table_privilege(%s, %s, 'UPDATE'), "
                "pg_catalog.has_table_privilege(%s, %s, 'DELETE'), "
                "pg_catalog.has_table_privilege(%s, %s, 'TRUNCATE')",
                (principal, table) * 5,
            )
            self.assertEqual(cur.fetchone(), (False, False, False, False, False))
        sequence = "ops.websim_exact_import_jobs_job_id_seq"
        cur.execute(
            "SELECT "
            "pg_catalog.has_sequence_privilege(%s, %s, 'USAGE'), "
            "pg_catalog.has_sequence_privilege(%s, %s, 'SELECT'), "
            "pg_catalog.has_sequence_privilege(%s, %s, 'UPDATE')",
            (principal, sequence) * 3,
        )
        self.assertEqual(cur.fetchone(), (False, False, False))

    def _assert_worker_authority_bounds(self, cur, principal):
        for schema in ("cache", "ops"):
            cur.execute(
                "SELECT pg_catalog.has_schema_privilege(%s, %s, 'USAGE'), "
                "pg_catalog.has_schema_privilege(%s, %s, 'CREATE')",
                (principal, schema, principal, schema),
            )
            self.assertEqual(cur.fetchone(), (True, False))
        for table in self.AUTHORITY_TABLES:
            cur.execute(
                "SELECT "
                "pg_catalog.has_table_privilege(%s, %s, 'SELECT'), "
                "pg_catalog.has_table_privilege(%s, %s, 'INSERT'), "
                "pg_catalog.has_table_privilege(%s, %s, 'UPDATE'), "
                "pg_catalog.has_table_privilege(%s, %s, 'DELETE'), "
                "pg_catalog.has_table_privilege(%s, %s, 'TRUNCATE')",
                (principal, table) * 5,
            )
            self.assertEqual(cur.fetchone(), (True, True, False, False, False))

    def _assert_real_login_acl_matrix(self):
        expected_database = f"wow_exact_first_fresh_test_{TASK_4W_RUN_ID}"
        with self._connect(TASK_4W_WORKER_DSN) as conn:
            self.assertEqual(conn.info.dbname, expected_database)
            with conn.cursor() as cur:
                cur.execute("SELECT session_user, current_user")
                session, current = cur.fetchone()
                self.assertEqual(current, session)
                self.assertNotIn(
                    session,
                    {"wow_app", "wow_migrator", "wow_exact_worker"},
                )
                self._assert_no_direct_ops(cur, session)
                self._assert_worker_authority_bounds(cur, session)
                self._assert_function_matrix(cur, session, self.WORKER_FUNCTIONS)

                cur.execute("SET ROLE wow_exact_worker")
                self.assertEqual(conn.info.dbname, expected_database)
                self._assert_no_direct_ops(cur, "wow_exact_worker")
                self._assert_worker_authority_bounds(cur, "wow_exact_worker")
                self._assert_function_matrix(
                    cur,
                    "wow_exact_worker",
                    self.WORKER_FUNCTIONS,
                )

        with self._connect(TASK_4W_APP_DSN) as conn:
            self.assertEqual(conn.info.dbname, expected_database)
            with conn.cursor() as cur:
                cur.execute("SELECT session_user, current_user")
                self.assertEqual(cur.fetchone(), ("wow_app", "wow_app"))
                self._assert_no_direct_ops(cur, "wow_app")
                self._assert_function_matrix(cur, "wow_app", self.APP_FUNCTIONS)

        with self._connect(TASK_4W_FRESH_DSN) as conn:
            with conn.cursor() as cur:
                self._assert_public_function_boundary(cur)

        for dsn in (TASK_4W_APP_DSN, TASK_4W_WORKER_DSN):
            self._assert_denied(dsn, "SELECT * FROM ops.websim_exact_import_jobs")
            self._assert_denied(
                dsn,
                "SELECT nextval('ops.websim_exact_import_jobs_job_id_seq')",
            )

    def _assert_acl_isolation(self):
        with self._connect(TASK_4W_FRESH_DSN) as conn:
            with conn.cursor() as cur:
                for role in ("wow_app", "wow_exact_worker"):
                    for table in self.OPS_TABLES:
                        cur.execute(
                            "SELECT pg_catalog.has_table_privilege(%s, %s, 'SELECT'), "
                            "pg_catalog.has_table_privilege(%s, %s, 'INSERT,UPDATE,DELETE,TRUNCATE')",
                            (role, table, role, table),
                        )
                        self.assertEqual(cur.fetchone(), (False, False))
                for function in (
                    "ops.websim_exact_enqueue(text,bytea,jsonb)",
                    "ops.websim_exact_read(text,bigint)",
                ):
                    cur.execute(
                        "SELECT pg_catalog.has_function_privilege('wow_app', %s, 'EXECUTE'), "
                        "pg_catalog.has_function_privilege('wow_exact_worker', %s, 'EXECUTE'), "
                        "pg_catalog.has_function_privilege('public', %s, 'EXECUTE')",
                        (function, function, function),
                    )
                    self.assertEqual(cur.fetchone(), (True, False, False))
                cur.execute(
                    "SELECT pg_catalog.has_table_privilege('wow_exact_worker', "
                    "'cache.websim_canonical_documents', 'SELECT,INSERT'), "
                    "pg_catalog.has_table_privilege('wow_exact_worker', "
                    "'cache.websim_canonical_documents', 'UPDATE,DELETE')"
                )
                self.assertEqual(cur.fetchone(), (True, False))

        self._assert_denied(TASK_4W_APP_DSN, "SELECT * FROM ops.websim_exact_import_jobs")
        self._assert_denied(
            TASK_4W_APP_DSN,
            "SELECT nextval('ops.websim_exact_import_jobs_job_id_seq')",
        )
        self._assert_denied(
            TASK_4W_APP_DSN,
            "SELECT * FROM ops.websim_exact_claim('wrong-role', 'r', 's')",
        )
        self._assert_denied(
            TASK_4W_WORKER_DSN,
            "SELECT * FROM ops.websim_exact_enqueue(%s, %s, %s::jsonb)",
            ("sha256:" + "f" * 64, b"{}", "{}"),
        )

    def _assert_reverse_metric_lock_order(self):
        owner = "sha256:" + "d" * 64
        first_request = self._request("metric-lock-early-v1")
        second_request = self._request("metric-lock-late-v1")
        self._enqueue(owner, first_request)
        self._enqueue(owner, second_request)

        claims = {}
        for _index in range(2):
            with self._connect(TASK_4W_WORKER_DSN) as conn:
                with conn.cursor() as cur:
                    cur.execute("SET ROLE wow_exact_worker")
                    cur.execute(
                        "SELECT * FROM ops.websim_exact_claim(%s, %s, %s)",
                        ("metric-lock-worker", "exact-worker-v1", "simc-runtime-v1"),
                    )
                    claim = cur.fetchone()
                    claims[claim[1]] = claim
        self.assertEqual(
            set(claims),
            {first_request.request_key, second_request.request_key},
        )
        early_claim = claims[first_request.request_key]
        late_claim = claims[second_request.request_key]
        catalog_status = f"metric-reverse-{TASK_4W_RUN_ID}"

        lock_connection = self._connect(TASK_4W_FRESH_DSN)
        lock_cursor = lock_connection.cursor()
        lock_cursor.execute(
            "SELECT job_id FROM ops.websim_exact_import_jobs "
            "WHERE job_id = %s FOR UPDATE",
            (early_claim[0],),
        )
        started = Queue()

        def terminalize_early():
            with self._connect(TASK_4W_WORKER_DSN) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT pg_catalog.set_config('application_name', %s, false)",
                        (f"task4w-metric-early-{TASK_4W_RUN_ID}",),
                    )
                    cur.execute("SET ROLE wow_exact_worker")
                    started.put(conn.info.backend_pid)
                    cur.execute(
                        "SELECT * FROM ops.websim_exact_terminalize("
                        "%s, %s, 'resolved', 'resolved', %s::jsonb, NULL, %s)",
                        (
                            early_claim[0],
                            early_claim[4],
                            '{"status":"resolved"}',
                            catalog_status,
                        ),
                    )
                    return cur.fetchone()

        released = False
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(terminalize_early)
            try:
                early_pid = started.get(timeout=5)
                deadline = time.monotonic() + 10
                observed_lock_wait = False
                while time.monotonic() < deadline:
                    with self._connect(TASK_4W_FRESH_DSN) as observer:
                        with observer.cursor() as cur:
                            cur.execute(
                                "SELECT wait_event_type = 'Lock' "
                                "FROM pg_catalog.pg_stat_activity WHERE pid = %s",
                                (early_pid,),
                            )
                            observed = cur.fetchone()
                    if observed and observed[0] is True:
                        observed_lock_wait = True
                        break
                    if future.done():
                        future.result()
                        break
                    time.sleep(0.02)
                self.assertTrue(observed_lock_wait, "early terminalize never waited on job lock")

                with self._connect(TASK_4W_WORKER_DSN) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SET ROLE wow_exact_worker")
                        cur.execute(
                            "SELECT * FROM ops.websim_exact_terminalize("
                            "%s, %s, 'resolved', 'resolved', %s::jsonb, NULL, %s)",
                            (
                                late_claim[0],
                                late_claim[4],
                                '{"status":"resolved"}',
                                catalog_status,
                            ),
                        )
                        late_result = cur.fetchone()
                self.assertEqual(late_result[1], "resolved")
                lock_connection.commit()
                released = True
                early_result = future.result(timeout=10)
                self.assertEqual(early_result[1], "resolved")
            finally:
                if not released:
                    lock_connection.rollback()
                lock_cursor.close()
                lock_connection.close()

        with self._connect(TASK_4W_FRESH_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT outcome_count, first_outcome_at, last_outcome_at "
                    "FROM ops.websim_exact_import_metrics_daily "
                    "WHERE metric_day = CURRENT_DATE "
                    "AND terminal_classification = 'resolved' AND catalog_status = %s",
                    (catalog_status,),
                )
                metric = cur.fetchone()
                self.assertEqual(metric[0], 2)
                self.assertLessEqual(metric[1], metric[2])
                cur.execute(
                    "SELECT count(*), min(finished_at), max(finished_at) "
                    "FROM ops.websim_exact_import_jobs "
                    "WHERE job_id = ANY(%s) AND status = 'resolved'",
                    ([early_claim[0], late_claim[0]],),
                )
                jobs = cur.fetchone()
                self.assertEqual(jobs[0], 2)
                self.assertEqual(metric[1:], jobs[1:])

    def _assert_claim_metric_post_wait_lease_window(self):
        owner = "sha256:" + "6" * 64
        exhausted_request = self._request("claim-metric-exhausted-v1")
        pending_request = self._request("claim-metric-pending-v1")
        exhausted = self._enqueue(owner, exhausted_request)
        pending = self._enqueue(owner, pending_request)
        with self._connect(TASK_4W_FRESH_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ops.websim_exact_import_jobs SET status = 'running', "
                    "attempt = 3, locked_by = 'claim-metric-exhausted', "
                    "lock_token = pg_catalog.gen_random_uuid(), "
                    "lease_until = observed.at - interval '1 second', "
                    "started_at = observed.at - interval '32 seconds', "
                    "heartbeat_at = observed.at - interval '31 seconds', "
                    "updated_at = observed.at "
                    "FROM (SELECT pg_catalog.clock_timestamp() AS at) observed "
                    "WHERE job_id = %s",
                    (exhausted[0],),
                )
                cur.execute(
                    "INSERT INTO ops.websim_exact_import_metrics_daily ("
                    "metric_day, terminal_classification, catalog_status, "
                    "outcome_count, first_outcome_at, last_outcome_at) "
                    "SELECT CURRENT_DATE, 'internal_error', 'unknown', 1, "
                    "observed.at, observed.at "
                    "FROM (SELECT pg_catalog.clock_timestamp() AS at) observed "
                    "ON CONFLICT (metric_day, terminal_classification, catalog_status) "
                    "DO UPDATE SET outcome_count = 1, "
                    "first_outcome_at = EXCLUDED.first_outcome_at, "
                    "last_outcome_at = EXCLUDED.last_outcome_at"
                )

        started = Queue()

        def blocked_claim():
            with self._connect(TASK_4W_WORKER_DSN) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT pg_catalog.set_config('application_name', %s, false)",
                        (f"blocked-claim-metric-{TASK_4W_RUN_ID}",),
                    )
                    cur.execute("SET ROLE wow_exact_worker")
                    started.put(conn.info.backend_pid)
                    cur.execute(
                        "SELECT * FROM ops.websim_exact_claim(%s, %s, %s)",
                        ("claim-metric-worker", "exact-worker-v1", "simc-runtime-v1"),
                    )
                    claim = cur.fetchone()
                    cur.execute(
                        "SELECT %s::timestamptz - pg_catalog.clock_timestamp()",
                        (claim[5],),
                    )
                    return claim, cur.fetchone()[0]

        lock_connection = self._connect(TASK_4W_FRESH_DSN)
        lock_cursor = lock_connection.cursor()
        pool = None
        released = False
        try:
            lock_cursor.execute(
                "SELECT outcome_count FROM ops.websim_exact_import_metrics_daily "
                "WHERE metric_day = CURRENT_DATE "
                "AND terminal_classification = 'internal_error' "
                "AND catalog_status = 'unknown' FOR UPDATE"
            )
            self.assertEqual(lock_cursor.fetchone()[0], 1)
            pool = ThreadPoolExecutor(max_workers=1)
            future = pool.submit(blocked_claim)
            claim_pid = started.get(timeout=5)
            deadline = time.monotonic() + 10
            observed_lock_wait = False
            while time.monotonic() < deadline:
                with self._connect(TASK_4W_FRESH_DSN) as observer:
                    with observer.cursor() as cur:
                        cur.execute(
                            "SELECT wait_event_type = 'Lock' "
                            "FROM pg_catalog.pg_stat_activity WHERE pid = %s",
                            (claim_pid,),
                        )
                        observed = cur.fetchone()
                if observed and observed[0] is True:
                    observed_lock_wait = True
                    break
                if future.done():
                    future.result()
                    break
                time.sleep(0.02)
            self.assertTrue(observed_lock_wait, "claim never waited on terminal metric row")
            self.assertFalse(future.done())
            time.sleep(1.1)
            lock_connection.rollback()
            released = True
            claim, lease_window = future.result(timeout=10)
        finally:
            if not released:
                lock_connection.rollback()
            if pool is not None:
                pool.shutdown(wait=True, cancel_futures=True)
            lock_cursor.close()
            lock_connection.close()

        self.assertEqual((claim[0], claim[1]), (pending[0], pending_request.request_key))
        self.assertGreater(lease_window.total_seconds(), 29.0)
        with self._connect(TASK_4W_FRESH_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status, attempt, request_key, "
                    "lease_until = heartbeat_at + interval '30 seconds' "
                    "FROM ops.websim_exact_import_jobs WHERE job_id = %s",
                    (pending[0],),
                )
                self.assertEqual(
                    cur.fetchone(),
                    ("running", 1, pending_request.request_key, True),
                )
                cur.execute(
                    "SELECT status, terminal_classification, problem_json->>'code' "
                    "FROM ops.websim_exact_import_jobs WHERE job_id = %s",
                    (exhausted[0],),
                )
                self.assertEqual(
                    cur.fetchone(),
                    ("failed", "internal_error", "ATTEMPT_EXHAUSTED"),
                )
                cur.execute(
                    "SELECT outcome_count FROM ops.websim_exact_import_metrics_daily "
                    "WHERE metric_day = CURRENT_DATE "
                    "AND terminal_classification = 'internal_error' "
                    "AND catalog_status = 'unknown'"
                )
                self.assertEqual(cur.fetchone()[0], 2)

    def _assert_enqueue_cooldown_post_wait_boundary(self):
        owner = "sha256:" + "7" * 64
        request = self._request("enqueue-cooldown-boundary-v1")
        failed = self._enqueue(owner, request)
        with self._connect(TASK_4W_FRESH_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ops.websim_exact_import_jobs SET status = 'failed', "
                    "attempt = 1, terminal_classification = 'internal_error', "
                    "started_at = observed.at - interval '15 minutes', "
                    "finished_at = observed.at - interval '14 minutes', "
                    "cooldown_until = observed.at + interval '1 minute', "
                    "problem_json = '{\"code\":\"COOLDOWN_BOUNDARY\"}'::jsonb, "
                    "updated_at = observed.at "
                    "FROM (SELECT pg_catalog.clock_timestamp() AS at) observed "
                    "WHERE job_id = %s",
                    (failed[0],),
                )

        started = Queue()
        invoke = Event()

        def blocked_enqueue():
            with self._connect(TASK_4W_APP_DSN) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT pg_catalog.set_config('application_name', %s, false)",
                        (f"blocked-enqueue-cooldown-{TASK_4W_RUN_ID}",),
                    )
                    started.put(conn.info.backend_pid)
                    self.assertTrue(invoke.wait(timeout=5))
                    cur.execute(
                        "SELECT * FROM ops.websim_exact_enqueue(%s, %s, %s::jsonb)",
                        (owner, request.canonical_bytes, json.dumps(request.request_json)),
                    )
                    return cur.fetchone()

        lock_connection = self._connect(TASK_4W_FRESH_DSN)
        lock_cursor = lock_connection.cursor()
        pool = None
        released = False
        try:
            lock_cursor.execute(
                "SELECT pg_catalog.pg_advisory_xact_lock("
                "pg_catalog.hashtextextended(%s, 0))",
                (owner + ":" + request.request_key,),
            )
            pool = ThreadPoolExecutor(max_workers=1)
            future = pool.submit(blocked_enqueue)
            enqueue_pid = started.get(timeout=5)
            with self._connect(TASK_4W_FRESH_DSN) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE ops.websim_exact_import_jobs SET "
                        "started_at = boundary.finished_at - interval '1 second', "
                        "finished_at = boundary.finished_at, "
                        "cooldown_until = boundary.finished_at + interval '15 minutes', "
                        "updated_at = pg_catalog.clock_timestamp() "
                        "FROM (SELECT pg_catalog.clock_timestamp() "
                        "- interval '15 minutes' + interval '1 second' "
                        "AS finished_at) boundary WHERE job_id = %s "
                        "RETURNING cooldown_until",
                        (failed[0],),
                    )
                    cooldown_until = cur.fetchone()[0]
                    cur.execute(
                        "SELECT %s::timestamptz - pg_catalog.clock_timestamp()",
                        (cooldown_until,),
                    )
                    cooldown_window = cur.fetchone()[0].total_seconds()
                    self.assertGreater(cooldown_window, 0.5)
                    self.assertLessEqual(cooldown_window, 1.0)
            invoke.set()
            deadline = time.monotonic() + 10
            observed_lock_wait = False
            cooldown_active_while_waiting = False
            while time.monotonic() < deadline:
                with self._connect(TASK_4W_FRESH_DSN) as observer:
                    with observer.cursor() as cur:
                        cur.execute(
                            "SELECT wait_event_type = 'Lock' "
                            "FROM pg_catalog.pg_stat_activity WHERE pid = %s",
                            (enqueue_pid,),
                        )
                        observed = cur.fetchone()
                        cur.execute(
                            "SELECT cooldown_until > pg_catalog.clock_timestamp() "
                            "FROM ops.websim_exact_import_jobs WHERE job_id = %s",
                            (failed[0],),
                        )
                        cooldown_active_while_waiting = cur.fetchone()[0]
                if observed and observed[0] is True:
                    observed_lock_wait = True
                    break
                if future.done():
                    future.result()
                    break
                time.sleep(0.02)
            self.assertTrue(observed_lock_wait, "enqueue never waited on owner/request lock")
            self.assertTrue(cooldown_active_while_waiting)
            self.assertFalse(future.done())
            time.sleep(1.25)
            lock_connection.rollback()
            released = True
            new_pending = future.result(timeout=10)
        finally:
            if not released:
                lock_connection.rollback()
            invoke.set()
            if pool is not None:
                pool.shutdown(wait=True, cancel_futures=True)
            lock_cursor.close()
            lock_connection.close()

        self.assertNotEqual(new_pending[0], failed[0])
        self.assertEqual(
            new_pending[1:],
            (request.request_key, "pending", False, None),
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            concurrent = list(pool.map(lambda _index: self._enqueue(owner, request), range(2)))
        serial = self._enqueue(owner, request)
        for reused in concurrent + [serial]:
            self.assertEqual(reused[0], new_pending[0])
            self.assertEqual(reused[1], request.request_key)
            self.assertEqual(reused[2:], ("pending", True, None))
        with self._connect(TASK_4W_FRESH_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*), count(*) FILTER (WHERE status = 'failed'), "
                    "count(*) FILTER (WHERE status = 'pending') "
                    "FROM ops.websim_exact_import_jobs "
                    "WHERE owner_key_hash = %s AND request_key = %s",
                    (owner, request.request_key),
                )
                self.assertEqual(cur.fetchone(), (2, 1, 1))

    def _assert_job_lifecycle(self):
        request = self._request()
        owner = "sha256:" + "a" * 64
        other_owner = "sha256:" + "b" * 64
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows = list(pool.map(lambda _index: self._enqueue(owner, request), range(2)))
        self.assertEqual(rows[0][0], rows[1][0])
        self.assertEqual(sorted(row[3] for row in rows), [False, True])
        separate = self._enqueue(other_owner, request)
        self.assertNotEqual(separate[0], rows[0][0])

        with self._connect(TASK_4W_APP_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM ops.websim_exact_read(%s, %s)",
                    (other_owner, rows[0][0]),
                )
                self.assertIsNone(cur.fetchone())

        with self._connect(TASK_4W_WORKER_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SET ROLE wow_exact_worker")
                cur.execute(
                    "SELECT * FROM ops.websim_exact_claim(%s, %s, %s)",
                    ("candidate-worker", "exact-worker-v1", "simc-runtime-v1"),
                )
                claimed = cur.fetchone()
        self.assertEqual(claimed[2], request.canonical_bytes)
        old_token = claimed[4]
        with self._connect(TASK_4W_FRESH_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ops.websim_exact_import_jobs SET "
                    "lease_until = observed.at - interval '1 second', "
                    "heartbeat_at = observed.at - interval '31 seconds' "
                    "FROM (SELECT pg_catalog.clock_timestamp() AS at) observed "
                    "WHERE job_id = %s",
                    (claimed[0],),
                )
        with self._connect(TASK_4W_WORKER_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SET ROLE wow_exact_worker")
                cur.execute(
                    "SELECT * FROM ops.websim_exact_heartbeat(%s, %s)",
                    (claimed[0], old_token),
                )
                self.assertIsNone(cur.fetchone())
                cur.execute(
                    "SELECT * FROM ops.websim_exact_claim(%s, %s, %s)",
                    ("candidate-worker", "exact-worker-v1", "simc-runtime-v1"),
                )
                reclaimed = cur.fetchone()
                self.assertNotEqual(reclaimed[4], old_token)
                cur.execute(
                    "SELECT * FROM ops.websim_exact_terminalize("
                    "%s, %s, 'resolved', 'resolved', %s::jsonb, NULL, 'complete')",
                    (reclaimed[0], reclaimed[4], '{"status":"resolved"}'),
                )
                self.assertEqual(cur.fetchone()[1], "resolved")
                cur.execute(
                    "SELECT * FROM ops.websim_exact_terminalize("
                    "%s, %s, 'resolved', 'resolved', %s::jsonb, NULL, 'complete')",
                    (reclaimed[0], old_token, '{"status":"resolved"}'),
                )
                self.assertIsNone(cur.fetchone())

        with self._connect(TASK_4W_WORKER_DSN) as conn:
            with conn.cursor() as cur:
                import psycopg

                cur.execute("SET ROLE wow_exact_worker")
                with self.assertRaises(psycopg.errors.InvalidParameterValue):
                    cur.execute("SELECT ops.websim_exact_prune_jobs(0)")

        with self._connect(TASK_4W_FRESH_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT outcome_count FROM ops.websim_exact_import_metrics_daily "
                    "WHERE metric_day = CURRENT_DATE "
                    "AND terminal_classification = 'resolved' AND catalog_status = 'complete'"
                )
                self.assertEqual(cur.fetchone()[0], 1)
                cur.execute(
                    "UPDATE ops.websim_exact_import_jobs SET "
                    "started_at = pg_catalog.clock_timestamp() - interval '9 days', "
                    "finished_at = pg_catalog.clock_timestamp() - interval '8 days' "
                    "WHERE job_id = %s",
                    (reclaimed[0],),
                )
        with self._connect(TASK_4W_WORKER_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SET ROLE wow_exact_worker")
                cur.execute("SELECT ops.websim_exact_prune_jobs(1)")
                self.assertEqual(cur.fetchone()[0], 1)

    def _assert_post_lock_expiry_cas(self):
        owner = "sha256:" + "e" * 64
        heartbeat_request = self._request("post-lock-heartbeat-v1")
        terminal_request = self._request("post-lock-terminalize-v1")
        self._enqueue(owner, heartbeat_request)
        self._enqueue(owner, terminal_request)
        wanted = {
            heartbeat_request.request_key,
            terminal_request.request_key,
        }
        claims = {}
        for _index in range(12):
            with self._connect(TASK_4W_WORKER_DSN) as conn:
                with conn.cursor() as cur:
                    cur.execute("SET ROLE wow_exact_worker")
                    cur.execute(
                        "SELECT * FROM ops.websim_exact_claim(%s, %s, %s)",
                        ("post-lock-worker", "exact-worker-v1", "simc-runtime-v1"),
                    )
                    claim = cur.fetchone()
            if claim is None:
                break
            if claim[1] in wanted:
                claims[claim[1]] = claim
            if set(claims) == wanted:
                break
        self.assertEqual(set(claims), wanted)
        heartbeat_claim = claims[heartbeat_request.request_key]
        terminal_claim = claims[terminal_request.request_key]
        target_ids = [heartbeat_claim[0], terminal_claim[0]]
        catalog_status = f"post-lock-expiry-{TASK_4W_RUN_ID}"

        lock_connection = self._connect(TASK_4W_FRESH_DSN)
        lock_cursor = lock_connection.cursor()
        try:
            lock_cursor.execute(
                "SELECT job_id, lease_until > pg_catalog.clock_timestamp() "
                "FROM ops.websim_exact_import_jobs "
                "WHERE job_id = ANY(%s) ORDER BY job_id FOR UPDATE",
                (target_ids,),
            )
            locked = lock_cursor.fetchall()
            self.assertEqual([row[0] for row in locked], sorted(target_ids))
            self.assertTrue(all(row[1] is True for row in locked))
        except Exception:
            lock_connection.rollback()
            lock_cursor.close()
            lock_connection.close()
            raise
        started = Queue()

        def blocked_heartbeat():
            with self._connect(TASK_4W_WORKER_DSN) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT pg_catalog.set_config('application_name', %s, false)",
                        (f"blocked-heartbeat-{TASK_4W_RUN_ID}",),
                    )
                    cur.execute("SET ROLE wow_exact_worker")
                    started.put(("heartbeat", conn.info.backend_pid))
                    cur.execute(
                        "SELECT * FROM ops.websim_exact_heartbeat(%s, %s)",
                        (heartbeat_claim[0], heartbeat_claim[4]),
                    )
                    return cur.fetchone()

        def blocked_terminalize():
            with self._connect(TASK_4W_WORKER_DSN) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT pg_catalog.set_config('application_name', %s, false)",
                        (f"blocked-terminalize-{TASK_4W_RUN_ID}",),
                    )
                    cur.execute("SET ROLE wow_exact_worker")
                    started.put(("terminalize", conn.info.backend_pid))
                    cur.execute(
                        "SELECT * FROM ops.websim_exact_terminalize("
                        "%s, %s, 'resolved', 'resolved', %s::jsonb, NULL, %s)",
                        (
                            terminal_claim[0],
                            terminal_claim[4],
                            '{"status":"resolved"}',
                            catalog_status,
                        ),
                    )
                    return cur.fetchone()

        released = False
        with ThreadPoolExecutor(max_workers=2) as pool:
            try:
                heartbeat_future = pool.submit(blocked_heartbeat)
                terminal_future = pool.submit(blocked_terminalize)
                pids = dict(started.get(timeout=5) for _index in range(2))
                deadline = time.monotonic() + 10
                observed_lock_wait = False
                while time.monotonic() < deadline:
                    with self._connect(TASK_4W_FRESH_DSN) as observer:
                        with observer.cursor() as cur:
                            cur.execute(
                                "SELECT count(*) FILTER ("
                                "WHERE wait_event_type = 'Lock') "
                                "FROM pg_catalog.pg_stat_activity "
                                "WHERE pid = ANY(%s)",
                                (list(pids.values()),),
                            )
                            observed_lock_wait = cur.fetchone()[0] == 2
                    if observed_lock_wait:
                        break
                    if heartbeat_future.done() or terminal_future.done():
                        break
                    time.sleep(0.02)
                self.assertTrue(
                    observed_lock_wait,
                    "heartbeat and terminalize never both waited on their job locks",
                )
                self.assertFalse(heartbeat_future.done())
                self.assertFalse(terminal_future.done())
                time.sleep(31)
                lock_connection.rollback()
                released = True
                self.assertIsNone(heartbeat_future.result(timeout=10))
                self.assertIsNone(terminal_future.result(timeout=10))
            finally:
                if not released:
                    lock_connection.rollback()
                lock_cursor.close()
                lock_connection.close()

        with self._connect(TASK_4W_FRESH_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*), bool_and(status = 'running'), "
                    "bool_and(lease_until <= pg_catalog.clock_timestamp()), "
                    "bool_and(lock_token IS NOT NULL), "
                    "count(*) FILTER (WHERE terminal_classification IS NOT NULL), "
                    "count(*) FILTER (WHERE finished_at IS NOT NULL) "
                    "FROM ops.websim_exact_import_jobs WHERE job_id = ANY(%s)",
                    (target_ids,),
                )
                self.assertEqual(cur.fetchone(), (2, True, True, True, 0, 0))
                cur.execute(
                    "SELECT count(*) FROM ops.websim_exact_import_metrics_daily "
                    "WHERE catalog_status = %s",
                    (catalog_status,),
                )
                terminal_metric = cur.fetchone()[0]
                self.assertEqual(terminal_metric, 0)

    def _assert_exhaustion_cooldown_metrics_and_bounded_prune(self):
        request = self._request("exact-worker-exhaustion-v1")
        owner = "sha256:" + "c" * 64
        pending = self._enqueue(owner, request)
        with self._connect(TASK_4W_FRESH_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ops.websim_exact_import_jobs SET status = 'running', attempt = 3, "
                    "locked_by = 'exhausted-worker', lock_token = pg_catalog.gen_random_uuid(), "
                    "lease_until = observed.at - interval '1 second', "
                    "started_at = observed.at - interval '32 seconds', "
                    "heartbeat_at = observed.at - interval '31 seconds', "
                    "updated_at = observed.at "
                    "FROM (SELECT pg_catalog.clock_timestamp() AS at) observed "
                    "WHERE job_id = %s",
                    (pending[0],),
                )
        with self._connect(TASK_4W_WORKER_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SET ROLE wow_exact_worker")
                cur.execute(
                    "SELECT * FROM ops.websim_exact_claim(%s, %s, %s)",
                    ("candidate-worker", "exact-worker-v1", "simc-runtime-v1"),
                )
                cur.fetchone()
        with self._connect(TASK_4W_FRESH_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status, terminal_classification, problem_json->>'code', "
                    "cooldown_until = finished_at + interval '15 minutes' "
                    "FROM ops.websim_exact_import_jobs WHERE job_id = %s",
                    (pending[0],),
                )
                self.assertEqual(
                    cur.fetchone(),
                    ("failed", "internal_error", "ATTEMPT_EXHAUSTED", True),
                )
        cooldown = self._enqueue(owner, request)
        self.assertEqual((cooldown[0], cooldown[2], cooldown[3]), (pending[0], "failed", True))
        with self._connect(TASK_4W_FRESH_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ops.websim_exact_import_jobs SET "
                    "started_at = observed.at - interval '17 minutes', "
                    "finished_at = observed.at - interval '16 minutes', "
                    "cooldown_until = observed.at - interval '1 minute', "
                    "updated_at = observed.at "
                    "FROM (SELECT pg_catalog.clock_timestamp() AS at) observed "
                    "WHERE job_id = %s",
                    (pending[0],),
                )
        with ThreadPoolExecutor(max_workers=2) as pool:
            after = list(pool.map(lambda _index: self._enqueue(owner, request), range(2)))
        self.assertEqual(after[0][0], after[1][0])
        self.assertNotEqual(after[0][0], pending[0])
        self.assertEqual(sorted(row[3] for row in after), [False, True])

        with self._connect(TASK_4W_FRESH_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ops.websim_exact_import_metrics_daily SET metric_day = "
                    "CURRENT_DATE - 91 WHERE terminal_classification = "
                    "'internal_error' AND catalog_status = 'unknown'"
                )
        with self._connect(TASK_4W_WORKER_DSN) as conn:
            with conn.cursor() as cur:
                import psycopg

                cur.execute("SET ROLE wow_exact_worker")
                with self.assertRaises(psycopg.errors.InvalidParameterValue):
                    cur.execute("SELECT ops.websim_exact_prune_metrics(101)")
        with self._connect(TASK_4W_WORKER_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SET ROLE wow_exact_worker")
                cur.execute("SELECT ops.websim_exact_prune_metrics(1)")
                self.assertEqual(cur.fetchone()[0], 1)

    def test_fresh_0032_and_upgrade_0031_to_0032_with_real_roles(self):
        self.assertEqual(TASK_4W_MIGRATIONS[-1].name, "0032_websim_exact_import_jobs.sql")
        self.assertEqual(TASK_4W_BASELINE_MIGRATIONS[-1].name, "0031_websim_exact_snapshot_v2.sql")
        fresh_identity = self._assert_empty_disposable(TASK_4W_FRESH_DSN, "fresh")
        upgrade_identity = self._assert_empty_disposable(TASK_4W_UPGRADE_DSN, "upgrade")

        self._apply(TASK_4W_FRESH_DSN, TASK_4W_MIGRATIONS)
        self._apply(TASK_4W_UPGRADE_DSN, TASK_4W_BASELINE_MIGRATIONS)
        with self._connect(TASK_4W_UPGRADE_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM ops.schema_migrations")
                self.assertEqual(cur.fetchone()[0], 31)
        self._apply(TASK_4W_UPGRADE_DSN, TASK_4W_MIGRATIONS[-1:])
        for dsn in (TASK_4W_FRESH_DSN, TASK_4W_UPGRADE_DSN):
            with self._connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT count(*), count(*) FILTER (WHERE id = "
                        "'0032_websim_exact_import_jobs') FROM ops.schema_migrations"
                    )
                    self.assertEqual(cur.fetchone(), (32, 1))

        self._assert_role_logins()
        self._assert_real_login_acl_matrix()
        self._assert_acl_isolation()
        self._assert_sensitive_jsonpath_boundary()
        self._assert_reverse_metric_lock_order()
        self._assert_claim_metric_post_wait_lease_window()
        self._assert_job_lifecycle()
        self._assert_exhaustion_cooldown_metrics_and_bounded_prune()
        self._assert_enqueue_cooldown_post_wait_boundary()
        self._assert_post_lock_expiry_cas()
        self.assertEqual(self._database_identity(TASK_4W_FRESH_DSN, "fresh"), fresh_identity)
        self.assertEqual(self._database_identity(TASK_4W_UPGRADE_DSN, "upgrade"), upgrade_identity)


@unittest.skipUnless(
    TASK_5C_CANDIDATE_CONFIGURED,
    "Task 5C requires psql plus explicit fresh, upgrade, migrator, app and worker 0035 DSNs",
)
class PostgresRuntimeAuthorityReleaseCandidateTest(unittest.TestCase):
    """One opt-in cloud-only 0035 candidate; it never provisions any resource."""

    PROJECT_SCHEMAS = (
        "identity", "app", "content", "cache", "knowledge", "analytics", "ops",
    )
    OWNER_ID = "12345678-1234-5678-1234-567812345678"
    TEMPLATE_ID = "87654321-4321-8765-4321-876543218765"
    EMPTY_TEMPLATE_ID = "87654321-4321-8765-4321-876543218766"

    @staticmethod
    def _connect(dsn):
        validate_task5c_candidate_run_id(TASK_5C_RUN_ID)
        import psycopg

        return psycopg.connect(dsn)

    def _worker_connection(self):
        from server.gear_exact_authority_worker import establish_exact_worker_role

        connection = self._connect(TASK_5C_WORKER_DSN)
        try:
            establish_exact_worker_role(connection)
        except Exception:
            connection.close()
            raise
        return connection

    def _database_identity(self, dsn, flavor):
        expected = (
            f"wow_exact_first_{flavor}_test_{TASK_5C_RUN_ID}",
            f"wow_exact_first_disposable:{TASK_5C_RUN_ID}:{flavor}",
        )
        with self._connect(dsn) as conn:
            self.assertEqual(conn.info.dbname, expected[0])
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_catalog.shobj_description(oid, 'pg_database') "
                    "FROM pg_catalog.pg_database WHERE datname = current_database()"
                )
                self.assertEqual(cur.fetchone()[0], expected[1])
        return expected

    def _assert_empty_disposable(self, dsn, flavor):
        identity = self._database_identity(dsn, flavor)
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT nspname FROM pg_catalog.pg_namespace "
                    "WHERE nspname = ANY(%s)",
                    (list(self.PROJECT_SCHEMAS),),
                )
                self.assertEqual(cur.fetchall(), [])
                cur.execute(
                    "SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, "
                    "rolcreaterole, rolreplication, rolbypassrls "
                    "FROM pg_catalog.pg_roles WHERE rolname = ANY(%s) "
                    "ORDER BY rolname",
                    (["wow_app", "wow_exact_worker", "wow_migrator"],),
                )
                roles = {row[0]: row[1:] for row in cur.fetchall()}
                self.assertEqual(set(roles), {"wow_app", "wow_exact_worker", "wow_migrator"})
                self.assertEqual(roles["wow_app"], (True, False, False, False, False, False))
                self.assertEqual(roles["wow_migrator"], (True, False, False, False, False, False))
                self.assertEqual(roles["wow_exact_worker"], (False, False, False, False, False, False))
        return identity

    def _apply(self, dsn, migrations):
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                for migration in migrations:
                    cur.execute(migration.read_text(encoding="utf-8"))

    @staticmethod
    def _git_identity():
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout
        if status:
            raise AssertionError("Task 5C candidate requires a clean final head")
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        tree = subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, check=True, text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        migration_hash = hashlib.sha256((
            ROOT / "server" / "migrations" / "postgres"
            / "0035_websim_exact_runtime_authority_release.sql"
        ).read_bytes()).hexdigest()
        return commit, tree, migration_hash

    def _assert_release_acl_boundary(self):
        functions = (
            "ops.websim_exact_runtime_authority_release_admit(uuid,text,bytea,bytea,bytea[])",
            "ops.websim_exact_runtime_authority_release_read(uuid,text)",
            "ops.websim_exact_runtime_authority_release_occurrences_read(uuid,text,text)",
        )
        tables = (
            "ops.websim_exact_runtime_resolver_contexts",
            "ops.websim_exact_runtime_authority_releases",
            "ops.websim_exact_runtime_occurrence_index_entries",
        )
        with self._connect(TASK_5C_FRESH_DSN) as conn:
            with conn.cursor() as cur:
                for principal, allowed in (
                    ("wow_app", (True, True, True)),
                    ("wow_exact_worker", (False, True, True)),
                ):
                    for function, expected in zip(functions, allowed, strict=True):
                        cur.execute(
                            "SELECT pg_catalog.has_function_privilege(%s, %s, 'EXECUTE')",
                            (principal, function),
                        )
                        self.assertIs(cur.fetchone()[0], expected)
                    for table in tables:
                        cur.execute(
                            "SELECT pg_catalog.has_table_privilege(%s, %s, "
                            "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE')",
                            (principal, table),
                        )
                        self.assertIs(cur.fetchone()[0], False)
                for function in functions:
                    cur.execute(
                        "SELECT NOT EXISTS ("
                        "SELECT 1 FROM pg_catalog.pg_proc AS proc "
                        "CROSS JOIN LATERAL pg_catalog.aclexplode("
                        "COALESCE(proc.proacl, pg_catalog.acldefault('f', proc.proowner))"
                        ") AS privilege WHERE proc.oid = pg_catalog.to_regprocedure(%s) "
                        "AND privilege.grantee = 0 AND privilege.privilege_type = 'EXECUTE'"
                        ")",
                        (function,),
                    )
                    self.assertIs(cur.fetchone()[0], True)

    def _assert_role_logins(self):
        expected_database = f"wow_exact_first_fresh_test_{TASK_5C_RUN_ID}"
        for dsn, role in (
            (TASK_5C_MIGRATOR_DSN, "wow_migrator"),
            (TASK_5C_APP_DSN, "wow_app"),
        ):
            with self._connect(dsn) as conn:
                self.assertEqual(conn.info.dbname, expected_database)
                with conn.cursor() as cur:
                    cur.execute("SELECT session_user, current_user")
                    self.assertEqual(cur.fetchone(), (role, role))
        with self._worker_connection() as conn:
            self.assertEqual(conn.info.dbname, expected_database)
            with conn.cursor() as cur:
                cur.execute("SELECT session_user, current_user")
                session_user, current_user = cur.fetchone()
                self.assertNotIn(session_user, {"wow_app", "wow_migrator", "wow_exact_worker"})
                self.assertEqual(current_user, "wow_exact_worker")

    def _seed_binding(self, *, template_id, config_hash, bundles):
        from server.exact_template_authority_binding import (
            canonical_remote_template_source,
            seal_exact_template_authority_binding,
        )
        from server.exact_template_authority_binding_store import (
            ExactTemplateAuthorityBindingStore,
        )
        from tests.exact_template_authority_binding_test import remote_source

        raw_source = remote_source()
        raw_source["templateId"] = template_id
        raw_source["configHash"] = config_hash
        source = canonical_remote_template_source(raw_source)
        with self._connect(TASK_5C_MIGRATOR_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO identity.users (id) VALUES (%s::uuid) "
                    "ON CONFLICT DO NOTHING",
                    (self.OWNER_ID,),
                )
                cur.execute(
                    "INSERT INTO app.build_templates ("
                    "id, user_id, template_type, name, payload_json, metadata_json, config_hash"
                    ") VALUES (%s::uuid, %s::uuid, 'gear', 'Task 5C candidate', "
                    "'{}'::jsonb, '{}'::jsonb, %s) ON CONFLICT DO NOTHING",
                    (template_id, self.OWNER_ID, config_hash),
                )
        proof = {
            "gearExactRegistryRevision": "gear-exact-registry:sha256:" + "1" * 64,
            "gearRuleRevision": "gear-rule-matrix-v1",
            "resolverRevision": "resolver-v2",
            "simcRuntimeRevision": "simc-runtime-v2",
            "templateAuthorityIdentity": "sha256:" + "2" * 64,
            "templateContentHash": "sha256:" + "3" * 64,
            "exactAuthorityBySlot": [
                {
                    "slot": slot,
                    "exactAuthorityEnvelopeKey": bundles[slot].envelope.content_key,
                }
                for slot in bundles
            ],
        }
        document = seal_exact_template_authority_binding(source, proof)
        return ExactTemplateAuthorityBindingStore(
            lambda: self._connect(TASK_5C_APP_DSN),
        ).admit(self.OWNER_ID, source, document)

    def _seed_authority_bundles(self):
        from server.gear_contracts import EXACT_LOADOUT_CORE_SLOTS
        from server.gear_exact_authority_store import GearExactAuthorityStore
        from tests.gear_resolved_loadout_test import v2_bundle

        store = GearExactAuthorityStore(lambda: self._connect(TASK_5C_MIGRATOR_DSN))
        bundles = {}
        for index, slot in enumerate(EXACT_LOADOUT_CORE_SLOTS, start=1):
            bundle = v2_bundle(slot, str(1000 + index), [])
            bundles[slot] = store.seal_authority_bundle(bundle)
        return bundles

    def _assert_v3_job_and_worker_contract(self, binding_key, bundles):
        from server.exact_runtime_authority_release import (
            seal_runtime_occurrence_index_entry,
        )
        from server.exact_runtime_authority_release_store import (
            RuntimeAuthorityReleaseIntegrityError,
            RuntimeAuthorityReleaseStore,
        )
        from server.exact_template_authority_binding import owner_key_hash_for_user_id
        from server.gear_exact_authority_worker import (
            process_claimed_job,
            snapshot_bound_processor,
        )
        from server.gear_exact_import_job_store import (
            GearExactImportJobStore,
            build_exact_import_job_request,
        )
        from server.simulation_snapshot_store import SimulationSnapshotStore
        from tests.gear_exact_import_job_store_test import (
            exact_intent,
            snapshot_reference,
        )
        from tests.simulation_snapshot_store_test import v3_snapshot_fixture

        (
            resolver,
            fixture_bundles,
            context,
            release,
            loadout_row,
            snapshot_row,
        ) = v3_snapshot_fixture()
        fixture_bundle = next(iter(fixture_bundles.values()))
        self.assertEqual(
            bundles["head"].envelope.content_key,
            fixture_bundle.envelope.content_key,
        )
        record = fixture_bundle.effect_records[0]
        signature = json.loads(record.canonical_bytes)["subjectVariantSignature"]
        occurrence = seal_runtime_occurrence_index_entry(
            release,
            subject_variant_signature=signature,
            resolved_gear_signature=resolver["resolvedGearSignature"],
            effect_record=record,
            producer_identity="task5c-candidate",
            producer_revision=TASK_5C_RUN_ID,
        ).document
        release_store = RuntimeAuthorityReleaseStore(
            lambda: self._connect(TASK_5C_APP_DSN),
        )
        admitted = release_store.admit(
            self.OWNER_ID,
            binding_key,
            resolver_context=context,
            release=release,
            occurrence_entries=(occurrence,),
        )
        self.assertEqual(admitted.release.content_key, release.content_key)
        self.assertEqual(
            release_store.read_unique_for_binding(
                self.OWNER_ID, binding_key,
            ).release.content_key,
            release.content_key,
        )
        entries = release_store.read_occurrences(
            self.OWNER_ID, binding_key, release,
        )
        self.assertEqual(tuple(entry.content_key for entry in entries), (occurrence.content_key,))
        self.assertEqual(
            tuple(record.content_key for record in release_store.load_effect_records(release, entries)),
            (record.content_key,),
        )

        empty_binding = self._seed_binding(
            template_id=self.EMPTY_TEMPLATE_ID,
            config_hash="b" * 64,
            bundles=bundles,
        )
        with self.assertRaisesRegex(
            RuntimeAuthorityReleaseIntegrityError,
            "membership is missing",
        ):
            release_store.read_unique_for_binding(self.OWNER_ID, empty_binding.content_key)

        snapshot_store = SimulationSnapshotStore(
            lambda: self._connect(TASK_5C_MIGRATOR_DSN),
        )
        sealed_loadout = snapshot_store.seal_loadout(
            loadout_row,
            resolver_snapshot=resolver,
            authority_bundles=fixture_bundles,
            resolver_context=context,
            runtime_authority_release=release,
        )
        sealed_snapshot = snapshot_store.seal_snapshot(
            snapshot_row,
            resolved_loadout=sealed_loadout,
            resolver_snapshot=resolver,
            authority_bundles=fixture_bundles,
            resolver_context=context,
            runtime_authority_release=release,
        )
        request = build_exact_import_job_request(
            exact_intent(),
            sealed_snapshot["dependencyVector"],
            snapshot_reference={
                "resolvedLoadoutKey": sealed_loadout["resolvedLoadoutKey"],
                "simulationSnapshotKey": sealed_snapshot["simulationSnapshotKey"],
                "snapshotRowHash": sealed_snapshot["rowHash"],
                "runtimeAuthorityReleaseKey": release.content_key,
                "resolverContextKey": context.content_key,
            },
        )
        owner_key_hash = owner_key_hash_for_user_id(self.OWNER_ID)
        app_jobs = GearExactImportJobStore(lambda: self._connect(TASK_5C_APP_DSN))
        enqueued = app_jobs.enqueue(owner_key_hash, request)
        worker_jobs = GearExactImportJobStore(self._worker_connection)
        claimed = worker_jobs.claim_next(
            "task5c-candidate-worker",
            sealed_snapshot["dependencyVector"]["workerRevision"],
            sealed_snapshot["dependencyVector"]["simcRuntimeRevision"],
        )
        self.assertIsNotNone(claimed)
        processor = snapshot_bound_processor(
            snapshot_store=snapshot_store,
            simc_runtime_revision=sealed_snapshot["dependencyVector"]["simcRuntimeRevision"],
            runner=lambda _snapshot: {
                "resultIdentity": "simc-result:sha256:" + "4" * 64,
                "status": "completed",
                "metrics": {"dps": 1},
            },
        )
        outcome = process_claimed_job(claimed, store=worker_jobs, processor=processor)
        self.assertEqual(outcome, {"status": "resolved", "code": "EXACT_IMPORT_RESOLVED"})
        self.assertEqual(app_jobs.read(owner_key_hash, enqueued["jobId"])["status"], "resolved")

        class NoSnapshotStore:
            def load_snapshot(self, *_args, **_kwargs):
                raise AssertionError("v1/v2 must not reload a snapshot")

        no_execution = snapshot_bound_processor(
            snapshot_store=NoSnapshotStore(),
            simc_runtime_revision=sealed_snapshot["dependencyVector"]["simcRuntimeRevision"],
            runner=lambda _snapshot: (_ for _ in ()).throw(
                AssertionError("v1/v2 must not run"),
            ),
        )
        v1 = build_exact_import_job_request(
            exact_intent(), sealed_snapshot["dependencyVector"],
        )
        v2 = build_exact_import_job_request(
            exact_intent(), sealed_snapshot["dependencyVector"],
            snapshot_reference=snapshot_reference(),
        )
        self.assertEqual(
            no_execution(v1)["problemJson"]["code"],
            "EXACT_IMPORT_REQUEST_V1_UNSUPPORTED",
        )
        self.assertEqual(
            no_execution(v2)["problemJson"]["code"],
            "EXACT_IMPORT_REQUEST_V2_UNSUPPORTED",
        )

        from tests.gear_resolved_loadout_test import v3_runtime_authority

        alternate_context, alternate_release = v3_runtime_authority(
            resolver,
            worker_revision="exact-worker-candidate-ambiguous",
        )
        release_store.admit(
            self.OWNER_ID,
            binding_key,
            resolver_context=alternate_context,
            release=alternate_release,
            occurrence_entries=(),
        )
        with self.assertRaisesRegex(
            RuntimeAuthorityReleaseIntegrityError,
            "membership is not unique",
        ):
            release_store.read_unique_for_binding(self.OWNER_ID, binding_key)

    def test_fresh_0035_and_upgrade_0034_to_0035_release_candidate(self):
        self.assertEqual(TASK_5C_MIGRATIONS[-1].name, "0035_websim_exact_runtime_authority_release.sql")
        self.assertEqual(TASK_5C_BASELINE_MIGRATIONS[-1].name, "0034_websim_exact_job_snapshot_binding.sql")
        self.assertEqual(os.environ.get("WOW_DEPLOY_START_ASYNC_SYNCS", "0"), "0")
        fresh_identity = self._assert_empty_disposable(TASK_5C_FRESH_DSN, "fresh")
        upgrade_identity = self._assert_empty_disposable(TASK_5C_UPGRADE_DSN, "upgrade")

        self._apply(TASK_5C_FRESH_DSN, TASK_5C_MIGRATIONS)
        self._apply(TASK_5C_UPGRADE_DSN, TASK_5C_BASELINE_MIGRATIONS)
        with self._connect(TASK_5C_UPGRADE_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM ops.schema_migrations")
                self.assertEqual(cur.fetchone()[0], 34)
        self._apply(TASK_5C_UPGRADE_DSN, TASK_5C_MIGRATIONS[-1:])
        for dsn in (TASK_5C_FRESH_DSN, TASK_5C_UPGRADE_DSN):
            with self._connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT count(*), count(*) FILTER (WHERE id = "
                        "'0035_websim_exact_runtime_authority_release') "
                        "FROM ops.schema_migrations"
                    )
                    self.assertEqual(cur.fetchone(), (35, 1))

        self._assert_release_acl_boundary()
        self._assert_role_logins()
        bundles = self._seed_authority_bundles()
        binding = self._seed_binding(
            template_id=self.TEMPLATE_ID,
            config_hash="a" * 64,
            bundles=bundles,
        )
        self._assert_v3_job_and_worker_contract(binding.content_key, bundles)
        from server.news_backend import exact_simc_api_for_authenticated_user

        self.assertIsNone(exact_simc_api_for_authenticated_user({"id": self.OWNER_ID}))
        self.assertEqual(self._database_identity(TASK_5C_FRESH_DSN, "fresh"), fresh_identity)
        self.assertEqual(self._database_identity(TASK_5C_UPGRADE_DSN, "upgrade"), upgrade_identity)
        git_identity = self._git_identity()
        attestation = build_task5c_candidate_attestation(
            run_id=TASK_5C_RUN_ID,
            fresh_identity=fresh_identity,
            upgrade_identity=upgrade_identity,
            git_identity=git_identity,
        )
        print(attestation, flush=True)


if __name__ == "__main__":
    unittest.main()

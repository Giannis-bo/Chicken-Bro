import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest


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
TASK_3A_RUN_ID = os.environ.get("WOW_PG_TEST_RUN_ID_0030", "")
TASK_3A_FRESH_DSN = os.environ.get("WOW_PG_TEST_DSN_FRESH_0030", "")
TASK_3A_UPGRADE_DSN = os.environ.get("WOW_PG_TEST_DSN_UPGRADE_0030", "")
TASK_3A_FORBIDDEN_RUN_IDS = frozenset({
    "t3a2608050955",
    "t3a260805111623",
    "t3a260805113656",
    "t3a260805120026",
    "t3a260805125812",
    "t3a260805142130",
    "t3a260805160003",
})


def validate_task3a_candidate_run_id(run_id):
    if (
        type(run_id) is not str
        or re.fullmatch(r"[a-z0-9]{8,32}", run_id) is None
        or run_id in TASK_3A_FORBIDDEN_RUN_IDS
    ):
        raise ValueError("invalid or forbidden Task 3A candidate run id")
    return run_id


if TASK_3A_RUN_ID:
    validate_task3a_candidate_run_id(TASK_3A_RUN_ID)
TASK_3A_CANDIDATE_CONFIGURED = bool(
    TASK_3A_RUN_ID
    and TASK_3A_FRESH_DSN
    and TASK_3A_UPGRADE_DSN
    and shutil.which("psql")
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


if __name__ == "__main__":
    unittest.main()

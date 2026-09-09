import importlib
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "server/migrations/product/0001_chickenbro_simc_core.sql"
CHAT_REPLAY_MIGRATION = ROOT / "server/migrations/product/0002_chat_idempotent_replay.sql"

EXPECTED_TABLES = {
    "identity": {"users", "user_identities", "auth_sessions", "web_login_sessions"},
    "chat": {"conversations", "messages", "agent_runs"},
    "simc": {
        "source_snapshots",
        "simulation_jobs",
        "simulation_attempts",
        "simulation_results",
    },
    "ops": {"schema_migrations", "job_queue", "audit_events", "usage_counters"},
}
FORBIDDEN_SCHEMAS = {"app", "content", "cache", "knowledge", "analytics", "websim"}


def _normalized_sql() -> str:
    if not MIGRATION.is_file():
        raise AssertionError("clean product migration is missing")
    return " ".join(MIGRATION.read_text(encoding="utf-8").split())


class ProductSchemaStaticTest(unittest.TestCase):
    def test_chat_replay_migration_persists_both_idempotency_identities(self):
        """Catches replay keys that exist only in process memory or permit duplicate runs."""
        self.assertTrue(
            CHAT_REPLAY_MIGRATION.is_file(),
            "formal Chat idempotency migration is missing",
        )
        sql = " ".join(CHAT_REPLAY_MIGRATION.read_text(encoding="utf-8").split())

        self.assertIn(
            "ALTER TABLE chat.agent_runs ADD COLUMN idempotency_key text",
            sql,
        )
        self.assertIn("ALTER COLUMN idempotency_key SET NOT NULL", sql)
        self.assertIn("CHECK (length(idempotency_key) BETWEEN 1 AND 128)", sql)
        self.assertIn("UNIQUE (user_id, idempotency_key)", sql)
        self.assertIn("UNIQUE (user_id, user_message_id)", sql)

    def test_runtime_role_has_no_destructive_business_table_privileges(self):
        """Catches granting the request runtime direct deletion of user history."""
        sql = _normalized_sql()

        self.assertNotRegex(
            sql,
            re.compile(r"GRANT [^;]*\bDELETE\b[^;]* ON (?:identity|chat|simc)\.", re.I),
        )
        self.assertNotRegex(
            sql,
            re.compile(r"GRANT [^;]*\bDELETE\b[^;]* ON ops\.(?:job_queue|usage_counters)", re.I),
        )
        self.assertIn(
            "GRANT SELECT, INSERT, UPDATE ON identity.users, identity.user_identities, "
            "identity.auth_sessions, identity.web_login_sessions TO wow_app",
            sql,
        )

    def test_runtime_role_cannot_rewrite_immutable_chat_or_source_facts(self):
        """Catches broad UPDATE grants on append-only messages and source snapshots."""
        sql = _normalized_sql()

        self.assertIn("GRANT SELECT, INSERT ON chat.messages TO wow_app", sql)
        self.assertIn("GRANT SELECT, INSERT ON simc.source_snapshots TO wow_app", sql)
        for grant in re.findall(r"GRANT .*? TO wow_app", sql, re.I):
            if "chat.messages" in grant or "simc.source_snapshots" in grant:
                self.assertNotRegex(grant, r"\bUPDATE\b")

    def test_clean_migration_creates_exactly_the_product_schema_and_table_owners(self):
        """Catches adding a legacy owner or omitting a formal product table."""
        sql = _normalized_sql()
        schemas = set(
            re.findall(r"\bCREATE SCHEMA(?: IF NOT EXISTS)? ([a-z_][a-z0-9_]*)", sql, re.I)
        )
        tables: dict[str, set[str]] = {}
        for schema, table in re.findall(
            r"\bCREATE TABLE(?: IF NOT EXISTS)? ([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)",
            sql,
            re.I,
        ):
            tables.setdefault(schema.lower(), set()).add(table.lower())

        self.assertEqual(schemas, set(EXPECTED_TABLES))
        self.assertEqual(tables, EXPECTED_TABLES)
        self.assertTrue(FORBIDDEN_SCHEMAS.isdisjoint(schemas))

    def test_identity_key_includes_app_context_and_formal_sessions_store_only_hashes(self):
        """Catches cross-AppID OpenID merging or reintroducing raw credential columns."""
        sql = _normalized_sql()
        identity_section = sql.split("CREATE TABLE identity.user_identities", 1)[1].split(
            "CREATE TABLE identity.auth_sessions", 1
        )[0]
        session_section = sql.split("CREATE TABLE identity.auth_sessions", 1)[1].split(
            "CREATE TABLE identity.web_login_sessions", 1
        )[0]
        web_login_section = sql.split("CREATE TABLE identity.web_login_sessions", 1)[1].split(
            "CREATE TABLE chat.conversations", 1
        )[0]

        self.assertIn("provider text NOT NULL CHECK (provider = 'wechat_mini')", identity_section)
        self.assertIn("app_context text NOT NULL", identity_section)
        self.assertIn("provider_subject text NOT NULL", identity_section)
        self.assertIn("UNIQUE (provider, app_context, provider_subject)", identity_section)
        self.assertIn("kind IN ('mini_bearer', 'web_cookie')", session_section)
        self.assertIn("token_hash text PRIMARY KEY", session_section)
        self.assertIn(
            "status IN ('pending', 'confirmed', 'consumed', 'cancelled', 'expired')",
            web_login_section,
        )
        self.assertIn("scene_ticket_sha256", web_login_section)
        self.assertIn("browser_verifier_sha256", web_login_section)
        for forbidden_column in (" session_key ", " cookie ", " bearer ", " openid "):
            self.assertNotIn(forbidden_column, f" {session_section.lower()} {web_login_section.lower()} ")

    def test_business_rows_are_owner_scoped_and_simc_results_are_immutable(self):
        """Catches an ownerless Chat/SimC row or a mutable/zero-metric successful result."""
        sql = _normalized_sql()
        for table in (
            "chat.conversations",
            "chat.messages",
            "chat.agent_runs",
            "simc.source_snapshots",
            "simc.simulation_jobs",
            "simc.simulation_attempts",
            "simc.simulation_results",
        ):
            section = sql.split(f"CREATE TABLE {table}", 1)[1].split(";", 1)[0]
            self.assertIn("user_id uuid NOT NULL REFERENCES identity.users(id)", section, table)
        result_section = sql.split("CREATE TABLE simc.simulation_results", 1)[1].split(";", 1)[0]
        self.assertIn("primary_metric_value double precision NOT NULL CHECK (primary_metric_value > 0)", result_section)
        self.assertIn("BEFORE UPDATE OR DELETE ON simc.simulation_results", sql)
        self.assertIn("BEFORE TRUNCATE ON simc.simulation_results", sql)

    def test_ops_payloads_are_bounded_and_runtime_role_has_no_schema_power(self):
        """Catches unbounded audit growth or privilege escalation of the runtime role."""
        sql = _normalized_sql()
        audit_section = sql.split("CREATE TABLE ops.audit_events", 1)[1].split(";", 1)[0]
        usage_section = sql.split("CREATE TABLE ops.usage_counters", 1)[1].split(";", 1)[0]
        self.assertIn("octet_length(payload_json::text) <= 8192", audit_section)
        self.assertIn("UNIQUE (event_type, subject_key)", audit_section)
        self.assertIn("value bigint NOT NULL DEFAULT 0 CHECK (value >= 0)", usage_section)
        self.assertNotRegex(sql, r"\bGRANT\s+(?:CREATE|TRUNCATE|TRIGGER|REFERENCES|ALL)\b")
        self.assertNotIn("DROP DATABASE", sql.upper())
        self.assertNotIn("account_kind", sql)
        self.assertNotIn("prototype_sessions", sql)
        self.assertNotIn("auth_tokens", sql)

    def test_runtime_queue_has_no_partial_cancellation_state(self):
        """Cancellation is not a formal command until one transaction owns queue and domain state."""
        sql = _normalized_sql()
        queue_section = sql.split("CREATE TABLE ops.job_queue", 1)[1].split(";", 1)[0]

        self.assertNotIn("cancel_requested", queue_section)
        self.assertNotIn("'cancelled'", queue_section)

    def test_runtime_can_append_but_not_rewrite_auth_audit_events(self):
        """Catches granting the request role permission to alter authentication evidence."""
        sql = _normalized_sql()
        self.assertIn("GRANT SELECT, INSERT ON ops.audit_events TO wow_app", sql)
        for grant in re.findall(r"GRANT .*? TO wow_app", sql, re.I):
            if "ops.audit_events" in grant:
                self.assertNotRegex(grant, r"\b(?:UPDATE|DELETE|TRUNCATE)\b")

    def test_default_public_schema_cannot_bypass_product_schema_ownership(self):
        """Catches leaving the runtime role able to create ungoverned public objects."""
        sql = _normalized_sql()
        self.assertIn("REVOKE CREATE ON SCHEMA public FROM PUBLIC", sql)


class _Result:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _Transaction:
    def __init__(self, connection):
        self._connection = connection

    def __enter__(self):
        if self._connection.in_transaction:
            raise AssertionError("test connection does not support nested transactions")
        self._connection.in_transaction = True
        self._connection.transaction_entries += 1
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None:
            self._connection.transaction_commits += 1
        else:
            self._connection.transaction_rollbacks += 1
        self._connection.in_transaction = False
        return False


class _MigrationConnection:
    def __init__(self):
        self.registry_exists = False
        self.applied: set[str] = set()
        self.executed_migration_sql: list[str] = []
        self.transaction_entries = 0
        self.transaction_commits = 0
        self.transaction_rollbacks = 0
        self.in_transaction = False
        self.queries_outside_transaction = 0

    def transaction(self):
        return _Transaction(self)

    def execute(self, sql, parameters=None):
        if not self.in_transaction:
            self.queries_outside_transaction += 1
        normalized = " ".join(str(sql).split())
        if normalized.startswith("SELECT pg_catalog.to_regclass"):
            return _Result(("ops.schema_migrations",) if self.registry_exists else (None,))
        if normalized.startswith("SELECT 1 FROM ops.schema_migrations"):
            return _Result((1,) if parameters[0] in self.applied else None)
        if normalized.startswith("INSERT INTO ops.schema_migrations"):
            self.applied.add(parameters[0])
            return _Result()
        self.executed_migration_sql.append(str(sql))
        if "CREATE TABLE ops.schema_migrations" in str(sql):
            self.registry_exists = True
        return _Result()


class ProductMigrationRunnerTest(unittest.TestCase):
    def _load_runner(self):
        try:
            return importlib.import_module("server.migrations.product.apply")
        except ModuleNotFoundError as error:
            self.fail(f"clean product migration runner is missing: {error}")

    def test_runner_applies_sorted_files_once_in_separate_transactions(self):
        """Catches out-of-order, repeated or non-transactional migration execution."""
        runner = self._load_runner()
        connection = _MigrationConnection()
        with tempfile.TemporaryDirectory() as directory:
            migration_dir = Path(directory)
            (migration_dir / "0002_second.sql").write_text("SELECT 'second';", encoding="utf-8")
            (migration_dir / "0001_first.sql").write_text(
                "CREATE TABLE ops.schema_migrations (id text PRIMARY KEY); SELECT 'first';",
                encoding="utf-8",
            )
            (migration_dir / "README.md").write_text("ignored", encoding="utf-8")

            first = runner.apply_product_migrations(connection, migration_dir)
            second = runner.apply_product_migrations(connection, migration_dir)

        self.assertEqual(first, ("0001_first", "0002_second"))
        self.assertEqual(second, ())
        self.assertEqual(connection.executed_migration_sql, [
            "CREATE TABLE ops.schema_migrations (id text PRIMARY KEY); SELECT 'first';",
            "SELECT 'second';",
        ])
        self.assertEqual(connection.applied, {"0001_first", "0002_second"})
        self.assertEqual(connection.transaction_entries, 4)
        self.assertEqual(connection.transaction_commits, 4)
        self.assertEqual(connection.transaction_rollbacks, 0)
        self.assertEqual(connection.queries_outside_transaction, 0)

    def test_runner_rejects_an_empty_or_non_file_migration_directory(self):
        """Catches silently declaring success when no product migration can execute."""
        runner = self._load_runner()
        connection = _MigrationConnection()
        with tempfile.TemporaryDirectory() as directory:
            migration_dir = Path(directory)
            with self.assertRaisesRegex(ValueError, "no product migrations"):
                runner.apply_product_migrations(connection, migration_dir)
        with self.assertRaisesRegex(ValueError, "migration directory"):
            runner.apply_product_migrations(connection, ROOT / "missing-product-migrations")


@unittest.skipUnless(os.environ.get("WOW_PG_TEST_DSN_V2", "").strip(), "WOW_PG_TEST_DSN_V2 is not configured")
class ProductSchemaIntegrationTest(unittest.TestCase):
    def test_dedicated_database_can_apply_the_product_lineage(self):
        """Runs only when an operator provides the dedicated isolated PostgreSQL DSN."""
        try:
            import psycopg
        except ImportError as error:
            raise unittest.SkipTest(f"psycopg is unavailable: {error}")
        runner = importlib.import_module("server.migrations.product.apply")
        connection = psycopg.connect(os.environ["WOW_PG_TEST_DSN_V2"])
        try:
            existing = connection.execute(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name = ANY(%s)",
                (list(EXPECTED_TABLES),),
            ).fetchall()
            if existing:
                self.skipTest("dedicated product test database is not empty")
            applied = runner.apply_product_migrations(
                connection,
                ROOT / "server/migrations/product",
            )
            self.assertEqual(
                applied,
                (
                    "0001_chickenbro_simc_core",
                    "0002_chat_idempotent_replay",
                    "0003_account_avatar",
                    "0004_chat_public_progress",
                    "0005_chat_account_concurrency",
                    "0006_chat_resolution_feedback",
                    "0007_chat_images",
                    "0007_qq_web_login",
                    "0008_chat_durable_execution",
                ),
            )
            avatar_column = connection.execute(
                "SELECT data_type, is_nullable FROM information_schema.columns "
                "WHERE table_schema = 'identity' AND table_name = 'users' "
                "AND column_name = 'avatar_data_url'",
            ).fetchone()
            self.assertEqual(avatar_column, ("text", "YES"))
            actual = connection.execute(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_schema = ANY(%s)",
                (list(EXPECTED_TABLES),),
            ).fetchall()
            by_schema: dict[str, set[str]] = {}
            for schema, table in actual:
                by_schema.setdefault(schema, set()).add(table)
            expected = {schema: set(tables) for schema, tables in EXPECTED_TABLES.items()}
            expected["identity"].add("qq_login_attempts")
            expected["chat"].update(("images", "executions", "tool_results"))
            self.assertEqual(by_schema, expected)
        finally:
            connection.rollback()
            connection.close()


if __name__ == "__main__":
    unittest.main()

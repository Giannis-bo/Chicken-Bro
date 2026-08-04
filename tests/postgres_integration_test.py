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
TASK_3A_RUN_ID = os.environ.get("WOW_PG_TEST_RUN_ID_0026", "")
TASK_3A_FRESH_DSN = os.environ.get("WOW_PG_TEST_DSN_FRESH_0026", "")
TASK_3A_UPGRADE_DSN = os.environ.get("WOW_PG_TEST_DSN_UPGRADE_0026", "")
TASK_3A_CANDIDATE_CONFIGURED = bool(
    re.fullmatch(r"[a-z0-9]{8,32}", TASK_3A_RUN_ID)
    and TASK_3A_FRESH_DSN
    and TASK_3A_UPGRADE_DSN
    and shutil.which("psql")
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

    @staticmethod
    def _connect(dsn):
        import psycopg

        return psycopg.connect(dsn)

    def _assert_empty_disposable(self, dsn, flavor):
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
        return expected_name, expected_comment

    def _apply(self, dsn, migrations):
        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                for migration in migrations:
                    cur.execute(migration.read_text(encoding="utf-8"))

    def _assert_sql_rejected(self, dsn, sql, params=()):
        import psycopg

        with self.assertRaises(psycopg.Error):
            with self._connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)

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

        migration = ROOT / "server" / "migrations" / "postgres" / "0026_websim_exact_authority_bundle.sql"
        return commit, tree, hashlib.sha256(migration.read_bytes()).hexdigest()

    def _assert_grants_and_bundle_smoke(self, dsn):
        from concurrent.futures import ThreadPoolExecutor

        from server.gear_exact_authority_store import GearExactAuthorityStore
        from tests.gear_exact_authority_store_test import authority_bundle

        with self._connect(dsn) as conn:
            with conn.cursor() as cur:
                for table in (
                    "cache.websim_canonical_documents",
                    "cache.websim_effect_aggregate_records",
                    "cache.websim_exact_authority_bundles",
                ):
                    cur.execute(
                        "SELECT has_table_privilege('wow_app', %s, 'SELECT'), "
                        "has_table_privilege('wow_app', %s, 'INSERT'), "
                        "has_table_privilege('wow_app', %s, 'UPDATE'), "
                        "has_table_privilege('wow_app', %s, 'DELETE'), "
                        "has_table_privilege('wow_app', %s, 'TRUNCATE')",
                        (table, table, table, table, table),
                    )
                    self.assertEqual(cur.fetchone(), (True, False, False, False, False))

        bundle = authority_bundle()
        store = GearExactAuthorityStore(lambda: self._connect(dsn))
        sealed = store.seal_authority_bundle(bundle)
        self.assertEqual(sealed, bundle)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = tuple(pool.map(
                lambda _: GearExactAuthorityStore(
                    lambda: self._connect(dsn)
                ).seal_authority_bundle(bundle),
                range(2),
            ))
        self.assertEqual(results, (bundle, bundle))

        bad_hash = "0" * 64
        self._assert_sql_rejected(
            dsn,
            "INSERT INTO cache.websim_canonical_documents "
            "(content_key, document_kind, schema_revision, canonical_bytes, "
            "canonical_json, canonical_sha256) "
            "VALUES (%s, 'exact_item', 'gear-exact-item-instance-v2', "
            "%s, %s::jsonb, %s)",
            ("exact-item-instance:sha256:" + bad_hash, b"{}", "{}", bad_hash),
        )

        import hashlib

        projection_bytes = b'{"schemaRevision":"gear-exact-item-instance-v2"}'
        projection_hash = hashlib.sha256(projection_bytes).hexdigest()
        self._assert_sql_rejected(
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
        )
        self._assert_sql_rejected(
            dsn,
            "INSERT INTO cache.websim_effect_aggregate_records "
            "(effect_support_key, ordinal, effect_record_key) "
            "VALUES (%s, 0, %s)",
            (
                "simc-item-effect-support:sha256:" + "1" * 64,
                "simc-item-effect-record:sha256:" + "2" * 64,
            ),
        )
        self._assert_sql_rejected(
            dsn,
            "INSERT INTO cache.websim_effect_aggregate_records "
            "(effect_support_key, ordinal, effect_record_key) "
            "VALUES (%s, %s, %s)",
            (
                sealed.effect_support.content_key,
                len(sealed.effect_records),
                sealed.effect_records[0].content_key,
            ),
        )
        self._assert_sql_rejected(
            dsn,
            "INSERT INTO cache.websim_exact_authority_bundles "
            "(exact_authority_envelope_key, exact_item_instance_key, "
            "static_facts_key, progression_binding_key, effect_support_key, "
            "gear_rule_revision, simc_runtime_revision, resolver_revision) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT DO NOTHING",
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
        )
        self._assert_sql_rejected(
            dsn,
            "UPDATE cache.websim_canonical_documents "
            "SET sealed_at = sealed_at WHERE content_key = %s",
            (sealed.exact_item.content_key,),
        )
        self._assert_sql_rejected(
            dsn,
            "TRUNCATE cache.websim_exact_authority_bundles",
        )

    def test_fresh_and_upgrade_candidates_are_distinct_empty_and_append_only(self):
        self.assertNotEqual(TASK_3A_FRESH_DSN, TASK_3A_UPGRADE_DSN)
        fresh_identity = self._assert_empty_disposable(TASK_3A_FRESH_DSN, "fresh")
        upgrade_identity = self._assert_empty_disposable(TASK_3A_UPGRADE_DSN, "upgrade")
        self.assertNotEqual(fresh_identity, upgrade_identity)
        commit, tree, migration_sha = self._git_identity()
        self.assertRegex(commit, r"^[0-9a-f]{40}$")
        self.assertRegex(tree, r"^[0-9a-f]{40}$")
        self.assertRegex(migration_sha, r"^[0-9a-f]{64}$")
        self.assertEqual(ALL_MIGRATIONS[-1].name, "0026_websim_exact_authority_bundle.sql")

        self._apply(TASK_3A_FRESH_DSN, ALL_MIGRATIONS)
        self._assert_grants_and_bundle_smoke(TASK_3A_FRESH_DSN)

        self._apply(TASK_3A_UPGRADE_DSN, ALL_MIGRATIONS[:-1])
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
                    "selection_json::text, row_hash "
                    "FROM cache.websim_gear_enhancement_selections ORDER BY 1"
                )
                before = cur.fetchall()
        self._apply(TASK_3A_UPGRADE_DSN, ALL_MIGRATIONS[-1:])
        with self._connect(TASK_3A_UPGRADE_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT enhancement_selection_key, schema_revision, "
                    "selection_json::text, row_hash "
                    "FROM cache.websim_gear_enhancement_selections ORDER BY 1"
                )
                self.assertEqual(cur.fetchall(), before)
        self._assert_grants_and_bundle_smoke(TASK_3A_UPGRADE_DSN)


if __name__ == "__main__":
    unittest.main()

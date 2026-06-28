import os
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    ROOT / "server" / "migrations" / "postgres" / "0001_identity_app_content_cache_knowledge_analytics_ops.sql",
    ROOT / "server" / "migrations" / "postgres" / "0002_runtime_privileges.sql",
    ROOT / "server" / "migrations" / "postgres" / "0003_build_template_config_hash_unique.sql",
    ROOT / "server" / "migrations" / "postgres" / "0004_chickenbro_runtime_fields.sql",
    ROOT / "server" / "migrations" / "postgres" / "0005_content_runtime_fields.sql",
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


if __name__ == "__main__":
    unittest.main()

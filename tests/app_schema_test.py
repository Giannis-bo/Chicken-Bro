from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "server/migrations/postgres/0038_chickenbro_simc_platform_foundation.sql"


class AppSchemaTest(unittest.TestCase):
    def test_platform_schema_has_exact_domain_owners(self):
        self.assertTrue(MIGRATION.is_file(), "v2 platform migration is missing")
        sql = " ".join(MIGRATION.read_text(encoding="utf-8").split())
        for clause in (
            "CREATE SCHEMA IF NOT EXISTS chat",
            "CREATE SCHEMA IF NOT EXISTS simc",
            "CREATE TABLE IF NOT EXISTS chat.conversations",
            "CREATE TABLE IF NOT EXISTS chat.messages",
            "CREATE TABLE IF NOT EXISTS chat.agent_runs",
            "CREATE TABLE IF NOT EXISTS simc.source_snapshots",
            "CREATE TABLE IF NOT EXISTS simc.simulation_jobs",
            "CREATE TABLE IF NOT EXISTS simc.simulation_attempts",
            "CREATE TABLE IF NOT EXISTS simc.simulation_results",
            "CREATE TABLE IF NOT EXISTS ops.job_queue",
        ):
            self.assertIn(clause, sql)
        self.assertNotIn("CREATE SCHEMA IF NOT EXISTS news", sql)
        self.assertNotIn("CREATE SCHEMA IF NOT EXISTS websim", sql)

    def test_every_business_table_is_owner_scoped(self):
        self.assertTrue(MIGRATION.is_file(), "v2 platform migration is missing")
        sql = MIGRATION.read_text(encoding="utf-8")
        self.assertGreaterEqual(sql.count("user_id uuid NOT NULL REFERENCES identity.users(id)"), 5)
        self.assertIn("'0038_chickenbro_simc_platform_foundation'", sql)

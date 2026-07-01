from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "server" / "migrations" / "postgres" / "0001_identity_app_content_cache_knowledge_analytics_ops.sql"
PRIVILEGES = ROOT / "server" / "migrations" / "postgres" / "0002_runtime_privileges.sql"
BUILD_TEMPLATE_DEDUPE = ROOT / "server" / "migrations" / "postgres" / "0003_build_template_config_hash_unique.sql"
CHICKENBRO_RUNTIME = ROOT / "server" / "migrations" / "postgres" / "0004_chickenbro_runtime_fields.sql"
CONTENT_RUNTIME = ROOT / "server" / "migrations" / "postgres" / "0005_content_runtime_fields.sql"
WEBSIM_SEASON_LOOT_CACHE = ROOT / "server" / "migrations" / "postgres" / "0006_websim_season_loot_cache.sql"
WEBSIM_GEAR_CATALOG_CACHE = ROOT / "server" / "migrations" / "postgres" / "0007_websim_gear_catalog_cache.sql"
WEBSIM_TALENT_CACHE = ROOT / "server" / "migrations" / "postgres" / "0008_websim_talent_cache.sql"
RUNTIME_RECONCILE_PRIVILEGES = ROOT / "server" / "migrations" / "postgres" / "0009_runtime_reconcile_privileges.sql"
ADMIN_GATE_DIAGNOSTICS = ROOT / "server" / "migrations" / "postgres" / "0010_admin_gate_diagnostics.sql"
WEBSIM_GEAR_TEMPLATE_CACHE = ROOT / "server" / "migrations" / "postgres" / "0011_websim_gear_template_cache.sql"


class PostgresSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = SCHEMA.read_text(encoding="utf-8")
        cls.privileges_sql = PRIVILEGES.read_text(encoding="utf-8")
        cls.build_template_dedupe_sql = BUILD_TEMPLATE_DEDUPE.read_text(encoding="utf-8")
        cls.chickenbro_runtime_sql = CHICKENBRO_RUNTIME.read_text(encoding="utf-8")
        cls.content_runtime_sql = CONTENT_RUNTIME.read_text(encoding="utf-8")
        cls.websim_season_loot_cache_sql = WEBSIM_SEASON_LOOT_CACHE.read_text(encoding="utf-8")
        cls.websim_gear_catalog_cache_sql = WEBSIM_GEAR_CATALOG_CACHE.read_text(encoding="utf-8")
        cls.websim_talent_cache_sql = WEBSIM_TALENT_CACHE.read_text(encoding="utf-8")
        cls.runtime_reconcile_privileges_sql = RUNTIME_RECONCILE_PRIVILEGES.read_text(encoding="utf-8")
        cls.admin_gate_diagnostics_sql = ADMIN_GATE_DIAGNOSTICS.read_text(encoding="utf-8")

    def table_section(self, table_name):
        start = self.sql.index(f"CREATE TABLE IF NOT EXISTS {table_name}")
        end = self.sql.index("\n);", start)
        return self.sql[start:end]

    def test_declares_required_schemas(self):
        for name in ("identity", "app", "content", "cache", "knowledge", "analytics", "ops"):
            self.assertIn(f"CREATE SCHEMA IF NOT EXISTS {name};", self.sql)

    def test_declares_required_tables(self):
        for table in (
            "identity.users",
            "identity.user_identities",
            "identity.auth_tokens",
            "app.build_templates",
            "app.build_archives",
            "app.simulator_tasks",
            "app.chickenbro_sessions",
            "app.chickenbro_messages",
            "app.chickenbro_actions",
            "app.agent_jobs",
            "content.sources",
            "content.raw_articles",
            "content.article_evidence",
            "content.articles",
            "cache.websim_sync_state",
            "cache.websim_items",
            "cache.websim_gear_sources",
            "cache.websim_gear_variants",
            "cache.websim_gear_mod_options",
            "cache.websim_talents",
            "cache.websim_community_talent_templates",
            "cache.raiderio_cache",
            "cache.stat_weight_cache",
            "knowledge.public_documents",
            "knowledge.public_document_chunks",
            "knowledge.user_context_summaries",
            "analytics.events",
            "analytics.user_links",
            "analytics.daily_metrics",
            "ops.schema_migrations",
            "ops.sync_runs",
            "ops.audit_logs",
            "ops.health_snapshots",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", self.sql)

    def test_user_assets_have_user_id_owner(self):
        for table in (
            "app.build_templates",
            "app.build_archives",
            "app.simulator_tasks",
            "app.chickenbro_sessions",
            "app.chickenbro_messages",
            "app.chickenbro_actions",
            "knowledge.user_context_summaries",
        ):
            section = self.table_section(table)
            self.assertIn("user_id", section)
            self.assertIn("REFERENCES identity.users", section)

    def test_build_templates_dedupe_by_config_hash_not_name(self):
        section = self.table_section("app.build_templates")
        self.assertIn("config_hash", section)
        self.assertIn("UNIQUE (user_id, template_type, config_hash)", section)
        self.assertNotIn("UNIQUE (user_id, template_type, name)", section)

    def test_simc_tasks_have_summary_snapshot_and_worker_ready_fields(self):
        section = self.table_section("app.simulator_tasks")
        for field in (
            "request_json",
            "analysis_json",
            "summary_json",
            "queued_at",
            "started_at",
            "finished_at",
            "attempt",
            "locked_by",
            "heartbeat_at",
            "cancel_requested",
            "last_error",
        ):
            self.assertIn(field, section)

    def test_chickenbro_and_agent_jobs_are_worker_ready(self):
        messages = self.table_section("app.chickenbro_messages")
        self.assertIn("agent_job_id", messages)

        actions = self.table_section("app.chickenbro_actions")
        for field in ("session_id", "user_id", "status", "evidence_refs_json"):
            self.assertIn(field, actions)

        jobs = self.table_section("app.agent_jobs")
        for field in ("bounded_context_json", "attempt", "locked_by", "heartbeat_at", "cancel_requested", "last_error"):
            self.assertIn(field, jobs)

    def test_embedding_is_reserved_not_required(self):
        chunks = self.table_section("knowledge.public_document_chunks")
        self.assertIn("embedding_status", chunks)
        self.assertIn("DEFAULT 'disabled'", chunks)

    def test_initial_schema_records_its_migration_id(self):
        self.assertIn("0001_identity_app_content_cache_knowledge_analytics_ops", self.sql)
        self.assertIn("INSERT INTO ops.schema_migrations", self.sql)

    def test_runtime_privileges_are_declared_for_wow_app(self):
        normalized = " ".join(self.privileges_sql.split())
        self.assertIn("GRANT USAGE ON SCHEMA identity, app, content, cache, knowledge, analytics, ops TO wow_app", normalized)
        self.assertIn("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA identity, app, content, cache, knowledge, analytics, ops TO wow_app", normalized)
        self.assertIn("ALTER DEFAULT PRIVILEGES FOR ROLE wow_migrator IN SCHEMA identity", normalized)
        self.assertIn("INSERT INTO ops.schema_migrations", normalized)

    def test_runtime_reconcile_privileges_are_declared_for_wow_migrator(self):
        normalized = " ".join(self.runtime_reconcile_privileges_sql.split())
        self.assertIn(
            "GRANT USAGE ON SCHEMA identity, app, content, cache, knowledge, analytics, ops TO wow_migrator",
            normalized,
        )
        self.assertIn(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA identity, app, content, cache, knowledge, analytics, ops TO wow_migrator",
            normalized,
        )
        self.assertIn(
            "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA identity, app, content, cache, knowledge, analytics, ops TO wow_migrator",
            normalized,
        )
        self.assertIn(
            "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA cache GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wow_migrator",
            normalized,
        )
        self.assertIn("0009_runtime_reconcile_privileges", normalized)

    def test_build_template_dedupe_migration_replaces_name_unique_constraint(self):
        normalized = " ".join(self.build_template_dedupe_sql.split())
        self.assertIn("DROP CONSTRAINT IF EXISTS build_templates_user_id_template_type_name_key", normalized)
        self.assertIn("UNIQUE (user_id, template_type, config_hash)", normalized)
        self.assertIn("0003_build_template_config_hash_unique", normalized)

    def test_chickenbro_runtime_migration_adds_message_job_and_bounded_context(self):
        normalized = " ".join(self.chickenbro_runtime_sql.split())
        self.assertIn("ADD COLUMN IF NOT EXISTS agent_job_id", normalized)
        self.assertIn("ADD COLUMN IF NOT EXISTS bounded_context_json", normalized)
        self.assertIn("0004_chickenbro_runtime_fields", normalized)

    def test_content_runtime_migration_adds_public_article_queue_and_refresh_runs(self):
        normalized = " ".join(self.content_runtime_sql.split())
        self.assertIn("ALTER TABLE content.articles", normalized)
        self.assertIn("ADD COLUMN IF NOT EXISTS payload_json", normalized)
        self.assertIn("CREATE TABLE IF NOT EXISTS content.discovery_queue", normalized)
        self.assertIn("CREATE TABLE IF NOT EXISTS content.refresh_runs", normalized)
        self.assertIn("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA content TO wow_app", normalized)
        self.assertIn("ALTER DEFAULT PRIVILEGES FOR ROLE wow_migrator IN SCHEMA content GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO wow_app", normalized)
        self.assertIn("0005_content_runtime_fields", normalized)

    def test_websim_season_loot_cache_migration_adds_pg_read_model_tables(self):
        normalized = " ".join(self.websim_season_loot_cache_sql.split())
        for table in (
            "cache.websim_season_state",
            "cache.websim_season_dungeons",
            "cache.websim_instances",
            "cache.websim_encounters",
            "cache.websim_loot",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", normalized)
        self.assertIn("REFERENCES cache.websim_instances(id)", normalized)
        self.assertIn("REFERENCES cache.websim_items(id)", normalized)
        self.assertIn("0006_websim_season_loot_cache", normalized)

    def test_websim_gear_catalog_cache_migration_adds_sqlite_compatible_columns(self):
        normalized = " ".join(self.websim_gear_catalog_cache_sql.split())
        self.assertIn("ALTER TABLE cache.websim_gear_sources", normalized)
        for field in ("source_label", "instance_id", "encounter_id", "difficulty_key", "season_revision"):
            self.assertIn(f"ADD COLUMN IF NOT EXISTS {field}", normalized)
        self.assertIn("ALTER TABLE cache.websim_gear_variants", normalized)
        for field in ("slot", "label", "source_type", "difficulty_key", "item_level", "simc_options_json", "status", "blockers_json"):
            self.assertIn(f"ADD COLUMN IF NOT EXISTS {field}", normalized)
        self.assertIn("ALTER TABLE cache.websim_gear_mod_options", normalized)
        self.assertIn("ALTER COLUMN variant_id DROP NOT NULL", normalized)
        for field in ("option_type", "name", "applicable_slots_json", "simc_options_json", "status"):
            self.assertIn(f"ADD COLUMN IF NOT EXISTS {field}", normalized)
        self.assertIn("0007_websim_gear_catalog_cache", normalized)

    def test_websim_talent_cache_migration_adds_pg_read_model_tables(self):
        normalized = " ".join(self.websim_talent_cache_sql.split())
        self.assertIn("ALTER TABLE cache.websim_talents", normalized)
        for field in ("tree_id", "row_index", "col_index", "spell_id", "name"):
            self.assertIn(f"ADD COLUMN IF NOT EXISTS {field}", normalized)
        self.assertIn("CREATE TABLE IF NOT EXISTS cache.websim_profile_presets", normalized)
        self.assertIn("CREATE TABLE IF NOT EXISTS cache.websim_spell_details", normalized)
        self.assertIn("ALTER TABLE cache.websim_community_talent_templates", normalized)
        for field in ("hero_key", "scenario_key", "raw_import_code", "websim_export_code", "talent_state_json", "source_refs_json"):
            self.assertIn(f"ADD COLUMN IF NOT EXISTS {field}", normalized)
        self.assertIn("0008_websim_talent_cache", normalized)

    def test_admin_gate_diagnostics_migration_adds_pg_ops_table(self):
        normalized = " ".join(self.admin_gate_diagnostics_sql.split())
        self.assertIn("CREATE TABLE IF NOT EXISTS ops.admin_gate_diagnoses", normalized)
        for field in (
            "target_domain",
            "target_type",
            "target_id",
            "diagnosis",
            "gap_type",
            "target_fingerprint",
            "payload_json",
        ):
            self.assertIn(field, normalized)
        self.assertIn("CREATE INDEX IF NOT EXISTS idx_ops_admin_gate_diagnoses_target", normalized)
        self.assertIn("GRANT SELECT, INSERT, UPDATE, DELETE ON ops.admin_gate_diagnoses TO wow_app", normalized)
        self.assertIn("0010_admin_gate_diagnostics", normalized)

    def test_websim_gear_template_cache_migration_adds_pg_read_model_table(self):
        self.assertTrue(WEBSIM_GEAR_TEMPLATE_CACHE.exists(), "missing gear template PG cache migration")
        normalized = " ".join(WEBSIM_GEAR_TEMPLATE_CACHE.read_text(encoding="utf-8").split())
        self.assertIn("CREATE TABLE IF NOT EXISTS cache.websim_community_gear_templates", normalized)
        for field in (
            "class_key",
            "spec_key",
            "source_key",
            "source_name",
            "source_status",
            "status",
            "signature",
            "source_refs_json",
            "gear_items_json",
            "raw_string",
            "ready_slot_count",
            "missing_slots_json",
            "analysis_window",
            "payload_json",
            "scan_run_id",
        ):
            self.assertIn(field, normalized)
        self.assertIn("CREATE INDEX IF NOT EXISTS idx_cache_websim_community_gear_templates_lookup", normalized)
        self.assertIn("GRANT SELECT, INSERT, UPDATE, DELETE ON cache.websim_community_gear_templates TO wow_app", normalized)
        self.assertIn("0011_websim_gear_template_cache", normalized)

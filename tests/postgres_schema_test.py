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
WEBSIM_ASSET_REGISTRY = ROOT / "server" / "migrations" / "postgres" / "0012_websim_asset_registry.sql"
WEBSIM_RELEASE_TRAIN = ROOT / "server" / "migrations" / "postgres" / "0013_websim_release_train.sql"
WEBSIM_POINTER_STATE = ROOT / "server" / "migrations" / "postgres" / "0014_websim_active_manifest_pointer_state.sql"
WEBSIM_GEAR_STAT_SNAPSHOTS = ROOT / "server" / "migrations" / "postgres" / "0015_websim_gear_stat_snapshots.sql"
WEBSIM_ATTRIBUTE_RULE_AUDITS = ROOT / "server" / "migrations" / "postgres" / "0016_websim_attribute_rule_audits.sql"
WEBSIM_HERO_COMMUNITY_RELEASE = ROOT / "server" / "migrations" / "postgres" / "0017_websim_hero_community_release.sql"
OBSERVED_BUILD_REGISTRY = ROOT / "server" / "migrations" / "postgres" / "0018_observed_build_registry.sql"
WEBSIM_GEAR_CATALOG_REVISION = ROOT / "server" / "migrations" / "postgres" / "0019_websim_gear_catalog_revision.sql"
WEBSIM_GEAR_EXACT_ITEM_INSTANCE = ROOT / "server" / "migrations" / "postgres" / "0020_websim_gear_exact_item_instance.sql"
WEBSIM_SIMULATION_SNAPSHOT = ROOT / "server" / "migrations" / "postgres" / "0021_websim_simulation_snapshot.sql"
WEBSIM_MANIFEST_V2 = ROOT / "server" / "migrations" / "postgres" / "0022_websim_manifest_v2.sql"


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
        cls.websim_gear_exact_item_instance_sql = WEBSIM_GEAR_EXACT_ITEM_INSTANCE.read_text(encoding="utf-8")
        cls.websim_simulation_snapshot_sql = WEBSIM_SIMULATION_SNAPSHOT.read_text(encoding="utf-8")
        cls.websim_manifest_v2_sql = WEBSIM_MANIFEST_V2.read_text(encoding="utf-8")

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

    def test_websim_exact_item_migration_is_dormant_append_only_and_owner_safe(self):
        normalized = " ".join(self.websim_gear_exact_item_instance_sql.split())
        for table in (
            "cache.websim_gear_enhancement_selections",
            "cache.websim_gear_exact_item_instances",
            "cache.websim_gear_exact_item_validations",
            "cache.websim_gear_exact_instance_template_refs",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", normalized)
        self.assertIn(
            "REFERENCES cache.websim_gear_catalog_revisions(catalog_revision)",
            normalized,
        )
        self.assertIn("template_scope IN ('community', 'personal')", normalized)
        self.assertIn("reject_websim_gear_exact_mutation", normalized)
        self.assertIn("REVOKE UPDATE, DELETE ON", normalized)
        self.assertIn("GRANT SELECT, INSERT ON", normalized)
        self.assertNotIn("user_id", normalized.lower())
        self.assertNotIn("owner_name", normalized.lower())
        self.assertNotIn("access_token", normalized.lower())
        self.assertNotIn("active_manifest_pointer", normalized)
        self.assertIn("0020_websim_gear_exact_item_instance", normalized)

    def test_websim_simulation_snapshot_migration_is_append_only_and_owner_safe(self):
        normalized = " ".join(self.websim_simulation_snapshot_sql.split())
        for table in (
            "cache.websim_gear_resolved_loadouts",
            "cache.websim_simulation_snapshots",
            "cache.websim_simulation_snapshot_results",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", normalized)
        self.assertEqual(normalized.count("BEFORE UPDATE OR DELETE ON"), 3)
        self.assertIn("GRANT SELECT, INSERT ON", normalized)
        self.assertIn("REVOKE UPDATE, DELETE, TRUNCATE ON", normalized)
        self.assertIn("0021_websim_simulation_snapshot", normalized)

    def test_websim_manifest_v2_migration_binds_catalog_and_exact_registry(self):
        normalized = " ".join(self.websim_manifest_v2_sql.split())
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS cache.websim_gear_exact_registries",
            normalized,
        )
        self.assertIn(
            "ADD COLUMN IF NOT EXISTS gear_catalog_revision text",
            normalized,
        )
        self.assertIn(
            "ADD COLUMN IF NOT EXISTS gear_exact_registry_revision text",
            normalized,
        )
        self.assertIn(
            "REFERENCES cache.websim_gear_catalog_revisions(catalog_revision)",
            normalized,
        )
        self.assertIn(
            "REFERENCES cache.websim_gear_exact_registries(registry_revision)",
            normalized,
        )
        self.assertIn(
            "schema_revision <> 'active-season-manifest-v2'",
            normalized,
        )
        self.assertIn("reject_websim_gear_exact_registry_mutation", normalized)
        self.assertIn("REVOKE UPDATE, DELETE, TRUNCATE ON", normalized)
        self.assertIn("GRANT SELECT, INSERT ON", normalized)
        self.assertIn("0022_websim_manifest_v2", normalized)

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

    def test_websim_asset_registry_migration_adds_pg_read_model_table(self):
        self.assertTrue(WEBSIM_ASSET_REGISTRY.exists(), "missing WebSim asset registry PG cache migration")
        normalized = " ".join(WEBSIM_ASSET_REGISTRY.read_text(encoding="utf-8").split())
        self.assertIn("CREATE TABLE IF NOT EXISTS cache.websim_asset_registry", normalized)
        for field in (
            "entity_type",
            "entity_id",
            "context_key",
            "asset_type",
            "icon_url",
            "resolution_tier",
            "source",
            "status",
            "semantic_tags_json",
            "usage_json",
            "fallback_text",
            "payload_json",
        ):
            self.assertIn(field, normalized)
        self.assertIn("CREATE INDEX IF NOT EXISTS idx_cache_websim_asset_registry_entity", normalized)
        self.assertIn("GRANT SELECT, INSERT, UPDATE, DELETE ON cache.websim_asset_registry TO wow_app", normalized)
        self.assertIn("0012_websim_asset_registry", normalized)

    def test_websim_release_train_migration_adds_immutable_release_registry(self):
        self.assertTrue(WEBSIM_RELEASE_TRAIN.exists(), "missing WebSim release train migration")
        normalized = " ".join(WEBSIM_RELEASE_TRAIN.read_text(encoding="utf-8").split())
        for table in (
            "cache.websim_release_registry",
            "cache.websim_gear_release_items",
            "cache.websim_gear_release_sources",
            "cache.websim_gear_release_variants",
            "cache.websim_gear_release_mod_options",
            "cache.websim_community_release_templates",
            "cache.websim_season_manifests",
            "cache.websim_active_manifest_pointer",
            "cache.websim_release_events",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", normalized)
        self.assertIn("CHECK (release_kind IN ('gear', 'community'))", normalized)
        self.assertIn("CHECK (release_status IN ('validated', 'degraded', 'blocked'))", normalized)
        self.assertIn("PRIMARY KEY (release_id, item_id)", normalized)
        self.assertIn("UNIQUE (release_id, item_id, variant_key)", normalized)
        self.assertIn("UNIQUE (release_id, option_key)", normalized)
        self.assertIn("CHECK (role IN ('winner', 'standby', 'rejected'))", normalized)
        self.assertIn(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_cache_websim_community_release_one_winner ON cache.websim_community_release_templates (release_id, class_key, spec_key) WHERE role = 'winner'",
            normalized,
        )
        self.assertIn("CHECK (environment = 'retail')", normalized)
        self.assertIn("generation bigint NOT NULL", normalized)
        self.assertIn("CREATE OR REPLACE FUNCTION cache.reject_websim_release_mutation", normalized)
        for table in (
            "websim_release_registry",
            "websim_gear_release_items",
            "websim_gear_release_sources",
            "websim_gear_release_variants",
            "websim_gear_release_mod_options",
            "websim_community_release_templates",
            "websim_season_manifests",
            "websim_release_events",
        ):
            self.assertIn(f"BEFORE UPDATE OR DELETE ON cache.{table}", normalized)
        self.assertIn("REVOKE UPDATE, DELETE ON cache.websim_release_registry,", normalized)
        self.assertIn("cache.websim_release_events FROM wow_app", normalized)
        self.assertIn("GRANT SELECT, INSERT ON cache.websim_release_registry,", normalized)
        self.assertIn("cache.websim_release_events TO wow_app", normalized)
        self.assertIn("GRANT SELECT, INSERT, UPDATE ON cache.websim_active_manifest_pointer TO wow_app", normalized)
        self.assertIn("0013_websim_release_train", normalized)

    def test_gear_catalog_revision_migration_is_dormant_append_only_membership(self):
        self.assertTrue(
            WEBSIM_GEAR_CATALOG_REVISION.exists(),
            "missing dormant Gear Catalog revision migration",
        )
        normalized = " ".join(
            WEBSIM_GEAR_CATALOG_REVISION.read_text(encoding="utf-8").split()
        )
        for table in (
            "cache.websim_gear_catalog_revisions",
            "cache.websim_gear_item_definitions",
            "cache.websim_gear_browse_variants",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", normalized)
        self.assertIn("PRIMARY KEY (catalog_revision, item_id)", normalized)
        self.assertIn(
            "UNIQUE (catalog_revision, item_id, progression_key)",
            normalized,
        )
        self.assertIn(
            "CREATE OR REPLACE FUNCTION cache.reject_websim_gear_catalog_mutation",
            normalized,
        )
        for table in (
            "websim_gear_catalog_revisions",
            "websim_gear_item_definitions",
            "websim_gear_browse_variants",
        ):
            self.assertIn(
                f"BEFORE UPDATE OR DELETE ON cache.{table}",
                normalized,
            )
        self.assertIn(
            "REVOKE UPDATE, DELETE ON cache.websim_gear_catalog_revisions,",
            normalized,
        )
        self.assertIn(
            "GRANT SELECT, INSERT ON cache.websim_gear_catalog_revisions,",
            normalized,
        )
        self.assertNotIn("active_catalog_pointer", normalized)
        self.assertNotIn("websim_active_manifest_pointer", normalized)
        self.assertIn("0019_websim_gear_catalog_revision", normalized)

    def test_hero_community_release_migration_allows_two_ranked_winners_per_spec(self):
        self.assertTrue(WEBSIM_HERO_COMMUNITY_RELEASE.exists(), "missing hero community release migration")
        normalized = " ".join(WEBSIM_HERO_COMMUNITY_RELEASE.read_text(encoding="utf-8").split())
        self.assertIn("DROP INDEX IF EXISTS cache.idx_cache_websim_community_release_one_winner", normalized)
        self.assertIn(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_cache_websim_community_release_winner_rank ON cache.websim_community_release_templates (release_id, class_key, spec_key, election_rank) WHERE role = 'winner'",
            normalized,
        )
        self.assertIn("0017_websim_hero_community_release", normalized)

    def test_websim_pointer_state_migration_supports_monotonic_transitional_rollback(self):
        self.assertTrue(WEBSIM_POINTER_STATE.exists(), "missing active Manifest pointer state migration")
        normalized = " ".join(WEBSIM_POINTER_STATE.read_text(encoding="utf-8").split())
        self.assertIn("ALTER COLUMN manifest_revision DROP NOT NULL", normalized)
        self.assertIn("ADD COLUMN IF NOT EXISTS pointer_mode text", normalized)
        self.assertIn("CHECK (pointer_mode IN ('active', 'transitional'))", normalized)
        self.assertIn("pointer_mode = 'active' AND manifest_revision IS NOT NULL", normalized)
        self.assertIn("pointer_mode = 'transitional' AND manifest_revision IS NULL", normalized)
        self.assertIn("GRANT SELECT, INSERT, UPDATE ON cache.websim_active_manifest_pointer TO wow_app", normalized)
        self.assertIn("0014_websim_active_manifest_pointer_state", normalized)

    def test_websim_stat_snapshot_migration_adds_immutable_cache_and_fenced_jobs(self):
        self.assertTrue(WEBSIM_GEAR_STAT_SNAPSHOTS.exists(), "missing async Gear stat snapshot migration")
        normalized = " ".join(WEBSIM_GEAR_STAT_SNAPSHOTS.read_text(encoding="utf-8").split())
        self.assertIn("CREATE TABLE IF NOT EXISTS cache.websim_gear_stat_snapshots", normalized)
        self.assertIn("CREATE TABLE IF NOT EXISTS ops.websim_gear_stat_jobs", normalized)
        self.assertIn("CREATE TABLE IF NOT EXISTS ops.websim_gear_stat_worker_state", normalized)
        self.assertIn("CREATE UNIQUE INDEX IF NOT EXISTS", normalized)
        self.assertIn("WHERE status IN ('queued', 'running')", normalized)
        self.assertIn("lease_until", normalized)
        self.assertIn("heartbeat_at", normalized)
        self.assertIn("lock_token", normalized)
        self.assertIn("BEFORE UPDATE OR DELETE ON cache.websim_gear_stat_snapshots", normalized)
        self.assertIn("REVOKE UPDATE, DELETE ON cache.websim_gear_stat_snapshots FROM wow_app", normalized)
        self.assertIn("REVOKE DELETE ON ops.websim_gear_stat_jobs FROM wow_app", normalized)
        self.assertIn("0015_websim_gear_stat_snapshots", normalized)

    def test_websim_attribute_rule_audit_migration_adds_fenced_operational_ledger(self):
        self.assertTrue(WEBSIM_ATTRIBUTE_RULE_AUDITS.exists(), "missing winner attribute rule audit migration")
        normalized = " ".join(WEBSIM_ATTRIBUTE_RULE_AUDITS.read_text(encoding="utf-8").split())
        self.assertIn("CREATE TABLE IF NOT EXISTS ops.websim_attribute_rule_audits", normalized)
        self.assertIn("attribute-audit:sha256", normalized)
        self.assertIn("idx_ops_websim_attribute_rule_audits_claim", normalized)
        self.assertIn("candidate_community_release_id", normalized)
        self.assertIn("manifest_revision", normalized)
        self.assertIn("input_json", normalized)
        self.assertIn("result_json", normalized)
        self.assertIn("REVOKE DELETE ON ops.websim_attribute_rule_audits FROM wow_app", normalized)
        self.assertIn("0016_websim_attribute_rule_audits", normalized)

    def test_observed_build_registry_migration_adds_immutable_core_and_cas_pointer(self):
        self.assertTrue(OBSERVED_BUILD_REGISTRY.exists(), "missing observed build registry migration")
        normalized = " ".join(OBSERVED_BUILD_REGISTRY.read_text(encoding="utf-8").split())
        for table in (
            "cache.observed_build_snapshots",
            "ops.observed_build_snapshot_checks",
            "cache.observed_build_projections",
            "cache.observed_build_template_sets",
            "cache.observed_build_template_set_slots",
            "cache.observed_build_template_set_pointer",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", normalized)
        self.assertIn("CHECK (status IN ('captured', 'changed', 'unchanged', 'failed'))", normalized)
        self.assertIn("CHECK (status IN ('verified', 'blocked'))", normalized)
        self.assertIn("CHECK (status IN ('verified', 'stale_lkg', 'pending_collection'))", normalized)
        self.assertIn("source_identity text NOT NULL", normalized)
        self.assertIn("source_identity text", normalized)
        self.assertIn(
            "status IN ('verified', 'stale_lkg') AND snapshot_id IS NOT NULL AND projection_id IS NOT NULL AND source_identity IS NOT NULL",
            normalized,
        )
        self.assertIn(
            "status = 'pending_collection' AND snapshot_id IS NULL AND projection_id IS NULL AND source_identity IS NULL",
            normalized,
        )
        self.assertIn("PRIMARY KEY (template_set_id, slot_key)", normalized)
        self.assertIn("ON DELETE RESTRICT", normalized)
        self.assertIn(
            "UNIQUE (snapshot_id, slot_key, source_identity)",
            normalized,
        )
        self.assertIn(
            "FOREIGN KEY (snapshot_id, slot_key, source_identity) REFERENCES cache.observed_build_snapshots(snapshot_id, slot_key, source_identity)",
            normalized,
        )
        self.assertIn(
            "UNIQUE (projection_id, snapshot_id, slot_key, source_identity)",
            normalized,
        )
        self.assertIn(
            "FOREIGN KEY (projection_id, snapshot_id, slot_key, source_identity) REFERENCES cache.observed_build_projections(projection_id, snapshot_id, slot_key, source_identity)",
            normalized,
        )
        self.assertIn("BEFORE UPDATE OR DELETE ON cache.observed_build_snapshots", normalized)
        self.assertIn("BEFORE UPDATE OR DELETE ON ops.observed_build_snapshot_checks", normalized)
        self.assertIn("BEFORE UPDATE OR DELETE ON cache.observed_build_projections", normalized)
        self.assertIn("BEFORE UPDATE OR DELETE ON cache.observed_build_template_sets", normalized)
        self.assertIn("BEFORE UPDATE OR DELETE ON cache.observed_build_template_set_slots", normalized)
        self.assertIn("REVOKE UPDATE, DELETE ON cache.observed_build_snapshots", normalized)
        self.assertIn("generation bigint NOT NULL CHECK (generation >= 1)", normalized)
        self.assertIn("REVOKE DELETE ON cache.observed_build_template_set_pointer FROM wow_app", normalized)
        self.assertIn(
            "GRANT SELECT, INSERT, UPDATE ON cache.observed_build_template_set_pointer TO wow_app",
            normalized,
        )
        self.assertIn("0018_observed_build_registry", normalized)

from pathlib import Path
import re
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
WEBSIM_GEAR_CATALOG_VARIANT_SHAPES = ROOT / "server" / "migrations" / "postgres" / "0023_websim_gear_catalog_variant_shapes.sql"
CHICKENBRO_AGENT_OBSERVABILITY = ROOT / "server" / "migrations" / "postgres" / "0024_chickenbro_agent_observability.sql"
CHICKENBRO_TOOL_REGISTRY = ROOT / "server" / "migrations" / "postgres" / "0025_chickenbro_tool_registry.sql"
WEBSIM_EXACT_AUTHORITY_BUNDLE = ROOT / "server" / "migrations" / "postgres" / "0026_websim_exact_authority_bundle.sql"
POSTGRES_MIGRATIONS_0001_0026 = tuple(sorted(
    (ROOT / "server" / "migrations" / "postgres").glob("[0-9][0-9][0-9][0-9]_*.sql")
))


def _normalized(value):
    return " ".join(value.split())


def _sql_section(sql, start_marker, end_marker):
    start = sql.index(start_marker)
    end = sql.index(end_marker, start) + len(end_marker)
    return _normalized(sql[start:end])


def exact_authority_schema_violations(sql, migrations):
    violations = []
    normalized = _normalized(sql)
    documents = _sql_section(
        sql,
        "CREATE TABLE IF NOT EXISTS cache.websim_canonical_documents",
        "\n);",
    )
    relations = _sql_section(
        sql,
        "CREATE TABLE IF NOT EXISTS cache.websim_effect_aggregate_records",
        "\n);",
    )
    bundles = _sql_section(
        sql,
        "CREATE TABLE IF NOT EXISTS cache.websim_exact_authority_bundles",
        "\n);",
    )
    matrix = (
        ("exact_item", "gear-exact-item-instance-v2", "exact-item-instance:sha256:"),
        ("exact_static_facts", "exact-static-facts-v1", "exact-static-facts:sha256:"),
        ("exact_progression", "exact-progression-binding-v1", "exact-progression:sha256:"),
        ("effect_record", "simc-item-effect-record-v1", "simc-item-effect-record:sha256:"),
        ("effect_aggregate", "simc-item-effect-support-v1", "simc-item-effect-support:sha256:"),
        ("exact_authority", "exact-authority-envelope-v1", "exact-authority:sha256:"),
    )
    if documents.count("document_kind = '") != 6:
        violations.append("closed matrix document_kind count")
    if documents.count("schema_revision = '") != 6:
        violations.append("closed matrix schema_revision count")
    if documents.count("content_key = '") != 6:
        violations.append("closed matrix content_key count")
    for kind, schema, prefix in matrix:
        branch = _normalized(f"""
            (
                document_kind = '{kind}'
                AND schema_revision = '{schema}'
                AND content_key = '{prefix}' || canonical_sha256
            )
        """)
        if documents.count(branch) != 1:
            violations.append(f"closed matrix branch {kind}")

    fk_contract = (
        (relations, "effect_support_key text NOT NULL REFERENCES cache.websim_canonical_documents(content_key) ON DELETE RESTRICT"),
        (relations, "effect_record_key text NOT NULL REFERENCES cache.websim_canonical_documents(content_key) ON DELETE RESTRICT"),
        (bundles, "exact_authority_envelope_key text PRIMARY KEY REFERENCES cache.websim_canonical_documents(content_key) ON DELETE RESTRICT"),
        (bundles, "exact_item_instance_key text NOT NULL REFERENCES cache.websim_canonical_documents(content_key) ON DELETE RESTRICT"),
        (bundles, "static_facts_key text NOT NULL REFERENCES cache.websim_canonical_documents(content_key) ON DELETE RESTRICT"),
        (bundles, "progression_binding_key text NOT NULL REFERENCES cache.websim_canonical_documents(content_key) ON DELETE RESTRICT"),
        (bundles, "effect_support_key text NOT NULL REFERENCES cache.websim_canonical_documents(content_key) ON DELETE RESTRICT"),
    )
    for section, clause in fk_contract:
        if section.count(clause) != 1:
            violations.append(f"exact foreign key {clause.split()[0]}")
    if normalized.count(
        "REFERENCES cache.websim_canonical_documents(content_key) ON DELETE RESTRICT"
    ) != 7:
        violations.append("exact foreign key universe")

    trigger_contract = (
        ("websim_canonical_documents", "trg_websim_canonical_documents_immutable", "trg_websim_canonical_documents_truncate"),
        ("websim_effect_aggregate_records", "trg_websim_effect_aggregate_records_immutable", "trg_websim_effect_aggregate_records_truncate"),
        ("websim_exact_authority_bundles", "trg_websim_exact_authority_bundles_immutable", "trg_websim_exact_authority_bundles_truncate"),
    )
    for table, row_trigger, truncate_trigger in trigger_contract:
        row_clause = (
            f"CREATE TRIGGER {row_trigger} BEFORE UPDATE OR DELETE ON cache.{table} "
            "FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_exact_authority_mutation();"
        )
        truncate_clause = (
            f"CREATE TRIGGER {truncate_trigger} BEFORE TRUNCATE ON cache.{table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION cache.reject_websim_exact_authority_mutation();"
        )
        if normalized.count(row_clause) != 1:
            violations.append(f"immutable row trigger {table}")
        if normalized.count(truncate_clause) != 1:
            violations.append(f"immutable truncate trigger {table}")

    binding_trigger_contract = (
        "CREATE TRIGGER trg_websim_effect_aggregate_record_binding BEFORE INSERT ON cache.websim_effect_aggregate_records FOR EACH ROW EXECUTE FUNCTION cache.verify_websim_effect_aggregate_record_insert();",
        "CREATE TRIGGER trg_websim_exact_authority_bundle_binding BEFORE INSERT ON cache.websim_exact_authority_bundles FOR EACH ROW EXECUTE FUNCTION cache.verify_websim_exact_authority_bundle_insert();",
    )
    for clause in binding_trigger_contract:
        if normalized.count(clause) != 1:
            violations.append(f"binding trigger {clause.split()[2]}")

    function_names = (
        "cache.verify_websim_effect_aggregate_record_insert",
        "cache.verify_websim_exact_authority_bundle_insert",
        "cache.reject_websim_exact_authority_mutation",
    )
    created_function_names = tuple(re.findall(
        r"\bCREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+([^\s(]+)\s*\(",
        normalized,
        flags=re.IGNORECASE,
    ))
    if sorted(created_function_names) != sorted(function_names):
        violations.append(
            f"exact function universe {created_function_names}",
        )
    function_sections = {}
    for function_name in function_names:
        marker = f"CREATE OR REPLACE FUNCTION {function_name}()"
        try:
            section = _sql_section(sql, marker, "$function$;")
        except ValueError:
            violations.append(f"missing function {function_name}")
            continue
        function_sections[function_name] = section
        declaration = _normalized(f"""
            CREATE OR REPLACE FUNCTION {function_name}()
            RETURNS trigger
            LANGUAGE plpgsql
            SECURITY INVOKER
            SET search_path = pg_catalog, pg_temp
            AS $function$
        """)
        if section.count(declaration) != 1:
            violations.append(f"exact function declaration {function_name}")

    aggregate_function = function_sections.get(
        "cache.verify_websim_effect_aggregate_record_insert",
        "",
    )
    aggregate_predicates = (
        "aggregate_kind IS DISTINCT FROM 'effect_aggregate'",
        "record_kind IS DISTINCT FROM 'effect_record'",
        "pg_catalog.jsonb_typeof(aggregate_json -> 'supportRecords') IS DISTINCT FROM 'array'",
        "NEW.ordinal >= pg_catalog.jsonb_array_length( aggregate_json -> 'supportRecords' )",
        "aggregate_json -> 'supportRecords' -> NEW.ordinal ->> 'supportRecordKey' IS DISTINCT FROM NEW.effect_record_key",
    )
    for predicate in aggregate_predicates:
        if aggregate_function.count(predicate) != 1:
            violations.append(f"aggregate binding {predicate}")

    bundle_function = function_sections.get(
        "cache.verify_websim_exact_authority_bundle_insert",
        "",
    )
    bundle_predicates = (
        "envelope_kind IS DISTINCT FROM 'exact_authority'",
        "exact_kind IS DISTINCT FROM 'exact_item'",
        "static_kind IS DISTINCT FROM 'exact_static_facts'",
        "progression_kind IS DISTINCT FROM 'exact_progression'",
        "effect_kind IS DISTINCT FROM 'effect_aggregate'",
        "pg_catalog.jsonb_typeof(effect_json -> 'supportRecords') IS DISTINCT FROM 'array'",
        "effect_relation_count IS DISTINCT FROM pg_catalog.jsonb_array_length( effect_json -> 'supportRecords' )",
        "envelope_json ->> 'exactItemInstanceKey' IS DISTINCT FROM NEW.exact_item_instance_key",
        "envelope_json ->> 'staticFactsKey' IS DISTINCT FROM NEW.static_facts_key",
        "envelope_json ->> 'progressionBindingKey' IS DISTINCT FROM NEW.progression_binding_key",
        "envelope_json ->> 'effectSupportKey' IS DISTINCT FROM NEW.effect_support_key",
        "envelope_json ->> 'resolverRevision' IS DISTINCT FROM NEW.resolver_revision",
        "static_json ->> 'exactItemInstanceKey' IS DISTINCT FROM NEW.exact_item_instance_key",
        "progression_json ->> 'exactItemInstanceKey' IS DISTINCT FROM NEW.exact_item_instance_key",
        "progression_json ->> 'gearRuleRevision' IS DISTINCT FROM NEW.gear_rule_revision",
        "effect_json ->> 'exactItemInstanceKey' IS DISTINCT FROM NEW.exact_item_instance_key",
        "effect_json ->> 'simcRuntimeRevision' IS DISTINCT FROM NEW.simc_runtime_revision",
    )
    for predicate in bundle_predicates:
        if bundle_function.count(predicate) != 1:
            violations.append(f"bundle binding {predicate}")

    authority_tables = (
        "cache.websim_canonical_documents, "
        "cache.websim_effect_aggregate_records, "
        "cache.websim_exact_authority_bundles"
    )
    acl_contract = (
        f"REVOKE ALL ON {authority_tables} FROM PUBLIC;",
        f"REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON {authority_tables} FROM wow_app;",
        f"GRANT SELECT ON {authority_tables} TO wow_app;",
    )
    acl_statements = tuple(re.findall(
        r"\b(?:GRANT|REVOKE)\b[^;]*;",
        normalized,
        flags=re.IGNORECASE,
    ))
    if sorted(acl_statements) != sorted(acl_contract):
        violations.append(f"exact authority ACL universe {acl_statements}")

    migration_names = [name for name, _ in migrations]
    if migration_names.count("0026_websim_exact_authority_bundle.sql") != 1:
        violations.append("0026 filename identity")
    if sum(
        body.count("'0026_websim_exact_authority_bundle'")
        for _, body in migrations
    ) != 1:
        violations.append("0026 ledger identity")
    return violations


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
        cls.websim_gear_catalog_variant_shapes_sql = WEBSIM_GEAR_CATALOG_VARIANT_SHAPES.read_text(encoding="utf-8")
        cls.chickenbro_agent_observability_sql = CHICKENBRO_AGENT_OBSERVABILITY.read_text(encoding="utf-8")
        cls.websim_exact_authority_bundle_sql = WEBSIM_EXACT_AUTHORITY_BUNDLE.read_text(encoding="utf-8")

    def test_exact_authority_bundle_migration_binds_bytes_closure_and_read_only_grants(self):
        normalized = " ".join(self.websim_exact_authority_bundle_sql.split())
        migrations = tuple(
            (path.name, path.read_text(encoding="utf-8"))
            for path in POSTGRES_MIGRATIONS_0001_0026
        )
        self.assertEqual(
            exact_authority_schema_violations(
                self.websim_exact_authority_bundle_sql,
                migrations,
            ),
            [],
        )
        for table in (
            "cache.websim_canonical_documents",
            "cache.websim_effect_aggregate_records",
            "cache.websim_exact_authority_bundles",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", normalized)
        self.assertIn("to_regprocedure('pg_catalog.sha256(bytea)')", normalized)
        self.assertRegex(
            normalized,
            r"canonical_sha256 = pg_catalog\.encode\(\s*pg_catalog\.sha256\(canonical_bytes\), 'hex'\s*\)",
        )
        self.assertIn(
            "canonical_json = pg_catalog.convert_from(canonical_bytes, 'UTF8')::jsonb",
            normalized,
        )
        for kind, schema, prefix in (
            ("exact_item", "gear-exact-item-instance-v2", "exact-item-instance:sha256:"),
            ("exact_static_facts", "exact-static-facts-v1", "exact-static-facts:sha256:"),
            ("exact_progression", "exact-progression-binding-v1", "exact-progression:sha256:"),
            ("effect_record", "simc-item-effect-record-v1", "simc-item-effect-record:sha256:"),
            ("effect_aggregate", "simc-item-effect-support-v1", "simc-item-effect-support:sha256:"),
            ("exact_authority", "exact-authority-envelope-v1", "exact-authority:sha256:"),
        ):
            self.assertIn(f"document_kind = '{kind}'", normalized)
            self.assertIn(f"schema_revision = '{schema}'", normalized)
            self.assertIn(f"'{prefix}' || canonical_sha256", normalized)
        self.assertIn("SECURITY INVOKER SET search_path = pg_catalog, pg_temp", normalized)
        self.assertIn("FOR KEY SHARE", normalized)
        self.assertIn(
            "effect_relation_count IS DISTINCT FROM pg_catalog.jsonb_array_length( effect_json -> 'supportRecords' )",
            normalized,
        )
        self.assertIn(
            "REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON cache.websim_canonical_documents",
            normalized,
        )
        self.assertIn(
            "GRANT SELECT ON cache.websim_canonical_documents",
            normalized,
        )
        self.assertNotIn("GRANT SELECT, INSERT", normalized)
        self.assertIn("0026_websim_exact_authority_bundle", normalized)

    def test_exact_authority_contract_mutations_fail_closed(self):
        migrations = tuple(
            (path.name, path.read_text(encoding="utf-8"))
            for path in POSTGRES_MIGRATIONS_0001_0026
        )
        self.assertEqual(
            exact_authority_schema_violations(
                self.websim_exact_authority_bundle_sql,
                migrations,
            ),
            [],
        )
        acl_tables = (
            "    cache.websim_canonical_documents,\n"
            "    cache.websim_effect_aggregate_records,\n"
            "    cache.websim_exact_authority_bundles"
        )
        acl_starts = tuple(
            match.start()
            for match in re.finditer(
                re.escape(acl_tables),
                self.websim_exact_authority_bundle_sql,
            )
        )
        self.assertEqual(len(acl_starts), 3)

        def shrink_acl(index):
            start = acl_starts[index]
            return (
                self.websim_exact_authority_bundle_sql[:start]
                + "    cache.websim_canonical_documents"
                + self.websim_exact_authority_bundle_sql[start + len(acl_tables):]
            )

        mutations = (
            self.websim_exact_authority_bundle_sql.replace(
                "effect_record_key text NOT NULL",
                "effect_record_key text",
                1,
            ),
            self.websim_exact_authority_bundle_sql.replace(
                "CREATE TRIGGER trg_websim_exact_authority_bundles_truncate",
                "CREATE TRIGGER trg_removed_exact_authority_bundles_truncate",
                1,
            ),
            self.websim_exact_authority_bundle_sql.replace(
                "envelope_json ->> 'resolverRevision'",
                "envelope_json ->> 'ignoredResolverRevision'",
                1,
            ),
            self.websim_exact_authority_bundle_sql.replace(
                "document_kind = 'exact_authority'",
                "document_kind = 'unknown_authority'",
                1,
            ),
            self.websim_exact_authority_bundle_sql.replace(
                "SET search_path = pg_catalog, pg_temp",
                "",
                1,
            ),
            self.websim_exact_authority_bundle_sql.replace(
                "SECURITY INVOKER",
                "",
                1,
            ),
            shrink_acl(0),
            shrink_acl(1),
            shrink_acl(2),
            self.websim_exact_authority_bundle_sql + """
CREATE FUNCTION cache.unsafe_extra_authority_function()
RETURNS trigger
LANGUAGE plpgsql
AS $unsafe$
BEGIN
    RETURN NEW;
END;
$unsafe$;
""",
            self.websim_exact_authority_bundle_sql
            + "\nGRANT INSERT ON cache.websim_canonical_documents TO wow_app;\n",
            self.websim_exact_authority_bundle_sql
            + "\nGRANT ALL ON cache.websim_canonical_documents TO PUBLIC;\n",
        )
        for mutated in mutations:
            with self.subTest(mutated=mutated[:80]):
                self.assertTrue(
                    exact_authority_schema_violations(mutated, migrations),
                )
        for function_name in (
            "cache.verify_websim_effect_aggregate_record_insert",
            "cache.verify_websim_exact_authority_bundle_insert",
            "cache.reject_websim_exact_authority_mutation",
        ):
            start = self.websim_exact_authority_bundle_sql.index(
                f"CREATE OR REPLACE FUNCTION {function_name}()",
            )
            end = self.websim_exact_authority_bundle_sql.index(
                "$function$;",
                start,
            )
            function_sql = self.websim_exact_authority_bundle_sql[start:end]
            for clause in (
                "LANGUAGE plpgsql",
                "SECURITY INVOKER",
                "SET search_path = pg_catalog, pg_temp",
            ):
                with self.subTest(function=function_name, clause=clause):
                    self.assertIn(clause, function_sql)
                    mutated_function = function_sql.replace(clause, "", 1)
                    mutated = (
                        self.websim_exact_authority_bundle_sql[:start]
                        + mutated_function
                        + self.websim_exact_authority_bundle_sql[end:]
                    )
                    self.assertTrue(
                        exact_authority_schema_violations(mutated, migrations),
                    )
        duplicate_identity = migrations + ((
            "9999_duplicate.sql",
            "SELECT '0026_websim_exact_authority_bundle';",
        ),)
        self.assertTrue(exact_authority_schema_violations(
            self.websim_exact_authority_bundle_sql,
            duplicate_identity,
        ))

    def test_migrations_0001_through_0026_never_manage_databases(self):
        self.assertEqual(
            POSTGRES_MIGRATIONS_0001_0026[-1].name,
            "0026_websim_exact_authority_bundle.sql",
        )
        database_ddl = re.compile(
            r"(?i)\b(?:CREATE|DROP|ALTER)\s+DATABASE\b",
        )
        for migration in POSTGRES_MIGRATIONS_0001_0026:
            with self.subTest(migration=migration.name):
                self.assertIsNone(database_ddl.search(
                    migration.read_text(encoding="utf-8"),
                ))

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

    def test_chickenbro_agent_observability_migration_is_owner_bound_and_idempotent(self):
        normalized = " ".join(self.chickenbro_agent_observability_sql.split())
        self.assertIn("CREATE TABLE IF NOT EXISTS app.chickenbro_agent_traces", normalized)
        self.assertIn(
            "user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE",
            normalized,
        )
        self.assertIn(
            "session_id uuid NOT NULL REFERENCES app.chickenbro_sessions(id) ON DELETE CASCADE",
            normalized,
        )
        self.assertIn(
            "user_message_id uuid NOT NULL REFERENCES app.chickenbro_messages(id) ON DELETE CASCADE",
            normalized,
        )
        self.assertIn(
            "agent_job_id uuid NOT NULL REFERENCES app.agent_jobs(id) ON DELETE CASCADE",
            normalized,
        )
        self.assertIn("UNIQUE (agent_job_id)", normalized)
        self.assertIn("payload_json jsonb NOT NULL", normalized)
        self.assertIn("idx_chickenbro_agent_traces_owner_created", normalized)
        self.assertIn("idx_chickenbro_agent_traces_session_created", normalized)
        self.assertIn(
            "REVOKE UPDATE, DELETE ON app.chickenbro_agent_traces FROM wow_app",
            normalized,
        )
        self.assertIn(
            "GRANT SELECT, INSERT ON app.chickenbro_agent_traces TO wow_app",
            normalized,
        )
        self.assertIn("0024_chickenbro_agent_observability", normalized)

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

    def test_websim_catalog_v2_allows_multiple_exact_shapes_per_progression(self):
        normalized = " ".join(
            self.websim_gear_catalog_variant_shapes_sql.split()
        )
        self.assertIn(
            "DROP CONSTRAINT IF EXISTS websim_gear_browse_variants_catalog_revision_item_id_progre_key",
            normalized,
        )
        self.assertIn(
            "CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_browse_variants_progression",
            normalized,
        )
        self.assertIn(
            "0023_websim_gear_catalog_variant_shapes",
            normalized,
        )

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

    def test_chickenbro_tool_registry_migration_is_immutable_and_read_only(self):
        self.assertTrue(CHICKENBRO_TOOL_REGISTRY.exists(), "missing Chickenbro Tool Registry migration")
        normalized = " ".join(CHICKENBRO_TOOL_REGISTRY.read_text(encoding="utf-8").split())
        for table in (
            "ops.chickenbro_tool_manifests",
            "ops.chickenbro_tool_registry_releases",
            "ops.chickenbro_tool_registry_release_manifests",
            "ops.chickenbro_tool_registry_active",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", normalized)
        self.assertIn("PRIMARY KEY (tool_id, version)", normalized)
        self.assertIn("FOREIGN KEY (tool_id, version) REFERENCES ops.chickenbro_tool_manifests (tool_id, version)", normalized)
        self.assertIn("CHECK (singleton_id = 1)", normalized)
        self.assertIn("source:raiderio:v1", normalized)
        self.assertIn("source:warcraftlogs:v1", normalized)
        self.assertIn("sha256:9e14fb40e1ee51ba8820cc498fd90d2aa745d3cf9cf1125d878a003996caea25", normalized)
        self.assertIn("sha256:c532f1760e75612cdf8396af9eaf0484b0f8da04398fb06499c9689efd3a934c", normalized)
        self.assertIn("sha256:c9d49f00695540052d69d8aea15653ffb227dbed4ecdb6db1ebd01f734e4734a", normalized)
        for table in (
            "ops.chickenbro_tool_manifests",
            "ops.chickenbro_tool_registry_releases",
            "ops.chickenbro_tool_registry_release_manifests",
            "ops.chickenbro_tool_registry_active",
        ):
            self.assertIn(f"GRANT SELECT ON {table} TO wow_app", normalized)
            self.assertIn(f"REVOKE INSERT, UPDATE, DELETE ON {table} FROM wow_app", normalized)
        self.assertIn("0025_chickenbro_tool_registry", normalized)

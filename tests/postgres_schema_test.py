import json
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
CHICKENBRO_SMART_QUESTION_CHAIN = ROOT / "server" / "migrations" / "postgres" / "0026_chickenbro_smart_question_chain.sql"
CHICKENBRO_COMMUNITY_STRENGTH = ROOT / "server" / "migrations" / "postgres" / "0027_chickenbro_community_strength_sources.sql"
CHICKENBRO_GENERIC_PUBLIC_WEB = ROOT / "server" / "migrations" / "postgres" / "0028_chickenbro_generic_public_web_research.sql"
CHICKENBRO_PUBLIC_WEB_REPEAT_BUDGET = ROOT / "server" / "migrations" / "postgres" / "0029_chickenbro_public_web_repeat_budget.sql"
WEBSIM_EXACT_AUTHORITY_BUNDLE = ROOT / "server" / "migrations" / "postgres" / "0030_websim_exact_authority_bundle.sql"
WEBSIM_EXACT_SNAPSHOT_V2 = ROOT / "server" / "migrations" / "postgres" / "0031_websim_exact_snapshot_v2.sql"
WEBSIM_EXACT_IMPORT_JOBS = ROOT / "server" / "migrations" / "postgres" / "0032_websim_exact_import_jobs.sql"
WEBSIM_EXACT_TEMPLATE_AUTHORITY_BINDING = ROOT / "server" / "migrations" / "postgres" / "0033_websim_exact_template_authority_binding.sql"
WEBSIM_EXACT_JOB_SNAPSHOT_BINDING = ROOT / "server" / "migrations" / "postgres" / "0034_websim_exact_job_snapshot_binding.sql"
WEBSIM_EXACT_RUNTIME_AUTHORITY_RELEASE = ROOT / "server" / "migrations" / "postgres" / "0035_websim_exact_runtime_authority_release.sql"
TASK_4W_OBJECT_FILTERED_SENSITIVE_JSONPATH = (
    '$.** ? (@.type() == "object").keyvalue() ? ('
    '@.key == "rawProfile" || @.key == "rawString" || '
    '@.key == "playerName" || @.key == "characterName" || '
    '@.key == "realm" || @.key == "server")'
)
TASK_4W_UNGUARDED_SENSITIVE_JSONPATH = (
    '$.**.keyvalue() ? ('
    '@.key == "rawProfile" || @.key == "rawString" || '
    '@.key == "playerName" || @.key == "characterName" || '
    '@.key == "realm" || @.key == "server")'
)
TASK_3A_MIGRATION_CURRENT_TRUTH_FILES = (
    ROOT / "artifacts" / "releases" / "2026-08-04-equipment-simulator-exact-first" / "requirement.json",
    ROOT / "docs" / "backend-owner-map.json",
    ROOT / "docs" / "plans" / "2026-08-04-equipment-simulator-canonical-kernel-implementation.md",
    ROOT / "docs" / "plans" / "2026-08-04-equipment-simulator-canonical-kernel-redesign.md",
    ROOT / "docs" / "plans" / "2026-08-04-equipment-simulator-canonical-owner-change-control.md",
    ROOT / "docs" / "plans" / "2026-08-04-equipment-simulator-duplicate-effect-subject-correction.md",
    ROOT / "docs" / "plans" / "2026-08-04-equipment-simulator-exact-first-implementation.md",
    ROOT / "docs" / "plans" / "2026-08-04-equipment-simulator-exact-first-persistence-resequence.md",
    ROOT / "docs" / "postgres-identity-migration-runbook.md",
    ROOT / "docs" / "project-owner-map.json",
)
TASK_3A_LIFECYCLE_STATUS_FILES = (
    ROOT / "docs" / "plans" / "2026-08-04-equipment-simulator-exact-first-persistence-resequence.md",
    ROOT / "docs" / "plans" / "README.md",
    ROOT / "docs" / "postgres-identity-migration-runbook.md",
    ROOT / "docs" / "roadmap.md",
)
TASK_3A_HISTORICAL_LIFECYCLE_FILES = (
    ROOT / "docs" / "plans" / "2026-08-04-equipment-simulator-exact-first-persistence-resequence.md",
    ROOT / "docs" / "postgres-identity-migration-runbook.md",
)
POSTGRES_MIGRATIONS_0001_0031 = tuple(sorted(
    path
    for path in (ROOT / "server" / "migrations" / "postgres").glob("[0-9][0-9][0-9][0-9]_*.sql")
    if path.name <= "0031_websim_exact_snapshot_v2.sql"
))
POSTGRES_MIGRATIONS_0001_0032 = tuple(sorted(
    path
    for path in (ROOT / "server" / "migrations" / "postgres").glob("[0-9][0-9][0-9][0-9]_*.sql")
    if path.name <= "0032_websim_exact_import_jobs.sql"
))
POSTGRES_MIGRATIONS_0001_0033 = tuple(sorted(
    path
    for path in (ROOT / "server" / "migrations" / "postgres").glob("[0-9][0-9][0-9][0-9]_*.sql")
    if path.name <= "0033_websim_exact_template_authority_binding.sql"
))
POSTGRES_MIGRATIONS_0001_0034 = tuple(sorted(
    path
    for path in (ROOT / "server" / "migrations" / "postgres").glob("[0-9][0-9][0-9][0-9]_*.sql")
    if path.name <= "0034_websim_exact_job_snapshot_binding.sql"
))
POSTGRES_MIGRATIONS_0001_0035 = tuple(sorted(
    path
    for path in (ROOT / "server" / "migrations" / "postgres").glob("[0-9][0-9][0-9][0-9]_*.sql")
    if path.name <= "0035_websim_exact_runtime_authority_release.sql"
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
    if migration_names.count("0030_websim_exact_authority_bundle.sql") != 1:
        violations.append("0030 filename identity")
    if sum(
        body.count("'0030_websim_exact_authority_bundle'")
        for _, body in migrations
    ) != 1:
        violations.append("0030 ledger identity")
    return violations


def exact_snapshot_v2_schema_violations(sql, migrations):
    """Static contract for 0031's deferred closure and conditional rows."""
    normalized = _normalized(sql)
    violations = []
    required = (
        "CREATE TABLE IF NOT EXISTS cache.websim_loadout_effect_authorities",
        "CREATE TABLE IF NOT EXISTS cache.websim_loadout_effect_authority_records",
        "effect_record_key text NOT NULL REFERENCES cache.websim_canonical_documents(content_key) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED",
        "REFERENCES cache.websim_loadout_effect_authorities(loadout_effect_authority_key) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED",
        "schema_revision = 'loadout-effect-authority-v1'",
        "loadout_effect_authority_key = 'loadout-effect-authority:sha256:' || canonical_sha256",
        "PRIMARY KEY (loadout_effect_authority_key, ordinal)",
        "CREATE CONSTRAINT TRIGGER trg_websim_loadout_effect_authorities_complete AFTER INSERT ON cache.websim_loadout_effect_authorities DEFERRABLE INITIALLY DEFERRED FOR EACH ROW",
        "CREATE CONSTRAINT TRIGGER trg_websim_loadout_effect_authority_records_complete AFTER INSERT ON cache.websim_loadout_effect_authority_records DEFERRABLE INITIALLY DEFERRED FOR EACH ROW",
        "pg_catalog.generate_series(0, expected_count - 1)",
        "relation.effect_record_key IS DISTINCT FROM authority_json->'supportRecords'->wanted.ordinal->>'supportRecordKey'",
        "document.document_kind <> 'effect_record'",
        "resolver_replay_context_json jsonb",
        "pg_catalog.octet_length(resolver_replay_context_json::text) <= 1048576",
        "CREATE OR REPLACE FUNCTION cache.verify_websim_resolver_replay_context( p_context jsonb )",
        "forbidden_keys CONSTANT text[] := ARRAY[ 'Catalog', 'catalogRevision', 'rawProfile', 'rawString', 'player', 'playerName', 'characterName', 'realm', 'server', 'source', 'sourceRefIds', 'sourcePayload' ]",
        "(p_context - ARRAY[ 'schemaRevision', 'status', 'dependencyVector', 'resolvedGearSignature', 'eligibilityContext', 'profileReadiness', 'resolvedSlots', 'setState', 'loadoutEffectSubjects', 'v2EffectBoundary' ]) <> '{}'::jsonb",
        "((p_context -> 'dependencyVector') - ARRAY[ 'gearRuleRevision', 'resolverContractRevision', 'simcRuntimeRevision' ]) <> '{}'::jsonb",
        "((p_context -> 'eligibilityContext') - ARRAY[ 'classKey', 'specKey', 'level' ]) <> '{}'::jsonb",
        "((p_context -> 'profileReadiness') - ARRAY[ 'status', 'simcReady', 'requiredSlots', 'readySlots', 'simcRuntimeRevision' ]) <> '{}'::jsonb",
        "(resolved_slot.value - ARRAY[ 'slot', 'itemId', 'legality' ]) <> '{}'::jsonb",
        "((resolved_slot.value -> 'legality') - ARRAY['status']) <> '{}'::jsonb",
        "(p_context -> 'setState') IS DISTINCT FROM (p_context -> 'v2EffectBoundary' -> 'setState')",
        "(p_context -> 'loadoutEffectSubjects') IS DISTINCT FROM (p_context -> 'v2EffectBoundary' -> 'subjects')",
        "identity_tokens text[] := ARRAY[]::text[]",
        "identity_tokens := identity_tokens || ARRAY[ p_context ->> 'resolvedGearSignature' ]",
        "identity_tokens := identity_tokens || ARRAY[ p_context -> 'dependencyVector' ->> 'gearRuleRevision', p_context -> 'dependencyVector' ->> 'resolverContractRevision', p_context -> 'dependencyVector' ->> 'simcRuntimeRevision' ]",
        "identity_tokens := identity_tokens || ARRAY[ p_context -> 'eligibilityContext' ->> 'classKey', p_context -> 'eligibilityContext' ->> 'specKey' ]",
        "identity_tokens := identity_tokens || ARRAY[ p_context -> 'profileReadiness' ->> 'simcRuntimeRevision' ]",
        "identity_tokens := identity_tokens || ARRAY( SELECT required_slot.value #>> '{}' FROM pg_catalog.jsonb_array_elements( p_context -> 'profileReadiness' -> 'requiredSlots' ) AS required_slot(value) )",
        "identity_tokens := identity_tokens || ARRAY[ resolved_slot.value ->> 'itemId' ]",
        "identity_tokens := identity_tokens || ARRAY[set_count.key]",
        "identity_tokens := identity_tokens || ARRAY[ active_effect ->> 'effectId', active_effect ->> 'itemSetId' ]",
        "identity_tokens := identity_tokens || ARRAY[ subject ->> 'subjectKind', subject ->> 'itemSetId', subject ->> 'subjectKey' ]",
        "FROM pg_catalog.unnest(identity_tokens) AS identity_token(value)",
        "pg_catalog.octet_length(identity_token.value) NOT BETWEEN 1 AND 256",
        "identity_token.value !~ '^[A-Za-z0-9][A-Za-z0-9._:/-]*$'",
        "PERFORM cache.verify_websim_resolver_replay_context( NEW.resolver_replay_context_json );",
        "NEW.resolver_replay_context_json -> 'v2EffectBoundary' ->> 'loadoutEffectAuthorityKey' IS DISTINCT FROM NEW.loadout_effect_authority_key",
        "CREATE OR REPLACE FUNCTION cache.verify_websim_v2_exact_authority_pairs( p_pairs jsonb, p_replay jsonb, p_loadout jsonb, p_effect_evidence jsonb )",
        "canonical_slots CONSTANT text[] := ARRAY[ 'head', 'neck', 'shoulder', 'back', 'chest', 'wrist', 'hands', 'waist', 'legs', 'feet', 'finger1', 'finger2', 'trinket1', 'trinket2', 'main_hand', 'off_hand' ]",
        "pg_catalog.jsonb_array_length(p_pairs) IS DISTINCT FROM pg_catalog.jsonb_array_length( p_replay -> 'profileReadiness' -> 'requiredSlots' )",
        "(pair - ARRAY['slot', 'exactAuthorityEnvelopeKey']) <> '{}'::jsonb",
        "pair_slot IS DISTINCT FROM ( p_replay -> 'profileReadiness' -> 'requiredSlots' ->> pair_ordinal )",
        "pair_slot_ordinal IS NULL OR pair_slot_ordinal <= previous_slot_ordinal",
        "WHERE bundle.exact_authority_envelope_key = pair_key FOR KEY SHARE OF bundle, exact_document, progression_document",
        "pg_catalog.jsonb_typeof(exact_json -> 'itemId') IS DISTINCT FROM 'string'",
        "exact_json ->> 'itemId' IS DISTINCT FROM p_replay -> 'resolvedSlots' -> pair_slot ->> 'itemId'",
        "progression_json -> 'trackAuthorityInput' ->> 'slot' IS DISTINCT FROM pair_slot",
        "bundle_gear_rule_revision IS DISTINCT FROM p_loadout ->> 'gearRuleRevision'",
        "bundle_resolver_revision IS DISTINCT FROM p_loadout ->> 'resolverRevision'",
        "bundle_simc_runtime_revision IS DISTINCT FROM p_loadout ->> 'simcRuntimeRevision'",
        "p_loadout ->> 'gearRuleRevision' IS DISTINCT FROM p_replay -> 'dependencyVector' ->> 'gearRuleRevision'",
        "p_loadout ->> 'resolverRevision' IS DISTINCT FROM p_replay -> 'dependencyVector' ->> 'resolverContractRevision'",
        "p_loadout ->> 'simcRuntimeRevision' IS DISTINCT FROM p_replay -> 'dependencyVector' ->> 'simcRuntimeRevision'",
        "p_loadout -> 'eligibilityContext' IS DISTINCT FROM p_replay -> 'eligibilityContext'",
        "WHERE occurrence ->> 'scope' = 'slot' AND NOT EXISTS ( SELECT 1 FROM pg_catalog.jsonb_array_elements(p_pairs) AS stated_pair(value) WHERE stated_pair.value ->> 'slot' IS NOT DISTINCT FROM occurrence ->> 'slot' AND stated_pair.value ->> 'exactAuthorityEnvelopeKey' IS NOT DISTINCT FROM occurrence ->> 'exactAuthorityEnvelopeKey' )",
        "PERFORM cache.verify_websim_v2_exact_authority_pairs( NEW.exact_authority_by_slot_json, NEW.resolver_replay_context_json, NEW.loadout_json, NEW.effect_evidence_by_occurrence_json );",
        "DROP CONSTRAINT IF EXISTS websim_gear_resolved_loadouts_catalog_revision_fkey",
        "DROP CONSTRAINT IF EXISTS websim_simulation_snapshots_catalog_revision_fkey",
        "exact_registry_revision IS NOT NULL",
        "exact_registry_revision IS NOT DISTINCT FROM ( loadout_json ->> 'exactRegistryRevision' )",
        "catalog_revision IS NOT DISTINCT FROM ( loadout_json ->> 'catalogRevision' )",
        "gear_rule_revision IS NOT DISTINCT FROM ( snapshot_json ->> 'gearRuleRevision' )",
        "v1 snapshot must bind its v1 ResolvedLoadout",
        "v1 ResolvedLoadout catalog revision is unavailable",
        "v1 SimulationSnapshot catalog revision is unavailable",
        "v1_catalog_revision_ref text GENERATED ALWAYS AS ( CASE WHEN schema_revision = 'resolved-loadout-v1' THEN catalog_revision ELSE NULL END ) STORED",
        "v1_catalog_revision_ref text GENERATED ALWAYS AS ( CASE WHEN schema_revision = 'simulation-snapshot-v1' THEN catalog_revision ELSE NULL END ) STORED",
        "ADD CONSTRAINT websim_gear_resolved_loadouts_v1_catalog_revision_fkey FOREIGN KEY (v1_catalog_revision_ref) REFERENCES cache.websim_gear_catalog_revisions(catalog_revision) ON DELETE RESTRICT",
        "ADD CONSTRAINT websim_simulation_snapshots_v1_catalog_revision_fkey FOREIGN KEY (v1_catalog_revision_ref) REFERENCES cache.websim_gear_catalog_revisions(catalog_revision) ON DELETE RESTRICT",
        "CREATE TRIGGER trg_websim_resolved_loadout_v1_v2_binding",
        "CREATE TRIGGER trg_websim_simulation_snapshot_v1_v2_binding",
        "loadout_json -> 'exactAuthorityBySlot' IS NOT DISTINCT FROM exact_authority_by_slot_json",
        "loadout_json -> 'effectEvidenceByOccurrence' IS NOT DISTINCT FROM effect_evidence_by_occurrence_json",
        "snapshot_json -> 'exactAuthorityBySlot' IS NOT DISTINCT FROM exact_authority_by_slot_json",
        "snapshot_json -> 'effectEvidenceByOccurrence' IS NOT DISTINCT FROM effect_evidence_by_occurrence_json",
        "NOT (occurrence ?& ARRAY[ 'scope', 'loadoutEffectAuthorityKey', 'recordOrdinal', 'subjectKind', 'subjectKey', 'subjectVariantSignature', 'supportRecordKey' ])",
        "(expected_subject ->> 'subjectKind') IS DISTINCT FROM (occurrence ->> 'subjectKind')",
        "(expected_subject ->> 'subjectKey') IS DISTINCT FROM (occurrence ->> 'subjectKey')",
        "(expected_subject ->> 'subjectVariantSignature') IS DISTINCT FROM (occurrence ->> 'subjectVariantSignature')",
        "(expected_subject ->> 'supportRecordKey') IS DISTINCT FROM (occurrence ->> 'supportRecordKey')",
        "pg_catalog.jsonb_typeof(expected_subject) IS DISTINCT FROM 'object'",
        "NOT (expected_subject ?& ARRAY[ 'subjectKind', 'subjectKey', 'subjectVariantSignature', 'status', 'supportRecordKey' ])",
        "(expected_subject - ARRAY[ 'subjectKind', 'subjectKey', 'subjectVariantSignature', 'status', 'supportRecordKey' ]) <> '{}'::jsonb",
        "(expected_subject ->> 'status') IS DISTINCT FROM 'verified'",
        "(expected_subject ->> 'subjectKind') IS NULL",
        "IF (occurrence ->> 'scope') = 'slot' THEN",
        "IF saw_loadout_scope THEN RAISE EXCEPTION 'v2 no-effect rows cannot contain loadout occurrences';",
        "IF NOT saw_loadout OR loadout_count <> relation_count THEN",
        "IF loadout_schema_revision IS DISTINCT FROM 'resolved-loadout-v2'",
        "loadout_exact_authority_by_slot IS DISTINCT FROM NEW.exact_authority_by_slot_json",
        "IF loadout_schema_revision IS DISTINCT FROM 'resolved-loadout-v1'",
        "REVOKE ALL ON cache.websim_loadout_effect_authorities, cache.websim_loadout_effect_authority_records FROM PUBLIC;",
        "REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON cache.websim_loadout_effect_authorities, cache.websim_loadout_effect_authority_records FROM wow_app;",
        "GRANT SELECT ON cache.websim_loadout_effect_authorities, cache.websim_loadout_effect_authority_records TO wow_app;",
        "CREATE TRIGGER trg_websim_loadout_effect_authorities_immutable BEFORE UPDATE OR DELETE ON cache.websim_loadout_effect_authorities FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_exact_authority_mutation();",
        "CREATE TRIGGER trg_websim_loadout_effect_authorities_truncate BEFORE TRUNCATE ON cache.websim_loadout_effect_authorities FOR EACH STATEMENT EXECUTE FUNCTION cache.reject_websim_exact_authority_mutation();",
        "CREATE TRIGGER trg_websim_loadout_effect_authority_records_immutable BEFORE UPDATE OR DELETE ON cache.websim_loadout_effect_authority_records FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_exact_authority_mutation();",
        "CREATE TRIGGER trg_websim_loadout_effect_authority_records_truncate BEFORE TRUNCATE ON cache.websim_loadout_effect_authority_records FOR EACH STATEMENT EXECUTE FUNCTION cache.reject_websim_exact_authority_mutation();",
    )
    for clause in required:
        if normalized.count(clause) != 1:
            violations.append(clause)
    required_presence = (
        "schema_revision = 'resolved-loadout-v1' AND resolved_loadout_key ~ '^resolved-loadout:sha256:[0-9a-f]{64}$'",
        "schema_revision = 'simulation-snapshot-v1' AND simulation_snapshot_key ~ '^simulation-snapshot:sha256:[0-9a-f]{64}$'",
        "loadout_json ->> 'resolvedLoadoutKey' IS NOT DISTINCT FROM resolved_loadout_key",
        "snapshot_json ->> 'simulationSnapshotKey' IS NOT DISTINCT FROM simulation_snapshot_key",
        "snapshot_json ->> 'resolvedLoadoutKey' IS NOT DISTINCT FROM resolved_loadout_key",
    )
    for clause in required_presence:
        if clause not in normalized:
            violations.append(clause)
    for field in (
        "subjectKind",
        "subjectKey",
        "subjectVariantSignature",
    ):
        occurrence_check = (
            "pg_catalog.jsonb_typeof(occurrence -> '"
            + field
            + "') IS DISTINCT FROM 'string'"
        )
        expected_subject_check = (
            "pg_catalog.jsonb_typeof(expected_subject -> '"
            + field
            + "') IS DISTINCT FROM 'string'"
        )
        if normalized.count(occurrence_check) != 2:
            violations.append(f"occurrence {field} string type")
        if normalized.count(expected_subject_check) != 1:
            violations.append(f"Task4L subject {field} string type")
    if (
        "effect_record_key text NOT NULL REFERENCES "
        "cache.websim_canonical_documents(content_key) "
        "DEFERRABLE INITIALLY DEFERRED ON DELETE RESTRICT"
    ) in normalized:
        violations.append("effect record FK clause order")
    if "UNIQUE (effect_record_key)" in normalized:
        violations.append("duplicate effect record prohibition")
    if "schema_revision = 'resolved-loadout-v2'" not in normalized:
        violations.append("resolved loadout v2 branch")
    if "schema_revision = 'simulation-snapshot-v2'" not in normalized:
        violations.append("snapshot v2 branch")
    slot_validation = normalized.find("IF (occurrence ->> 'scope') = 'slot' THEN")
    no_effect_return = normalized.find("IF p_loadout_effect_authority_key IS NULL THEN")
    if slot_validation == -1 or no_effect_return == -1 or slot_validation > no_effect_return:
        violations.append("slot evidence must validate before no-effect return")
    migration_names = [name for name, _ in migrations]
    if migration_names.count("0031_websim_exact_snapshot_v2.sql") != 1:
        violations.append("0031 filename identity")
    if sum(body.count("'0031_websim_exact_snapshot_v2'") for _, body in migrations) != 1:
        violations.append("0031 ledger identity")
    return violations


def exact_import_jobs_schema_violations(sql, migrations):
    """Static 0032 contract; real role/lease behavior belongs to the cloud candidate."""
    normalized = _normalized(sql)
    violations = []
    if re.search(
        r"\bcurrent_time(?:\s+timestamptz)?\s*:=",
        normalized,
        flags=re.IGNORECASE,
    ):
        violations.append("reserved current_time PL/pgSQL assignment target")
    if re.search(
        r"\bpg_catalog\s*\.\s*coalesce\s*\(",
        normalized,
        flags=re.IGNORECASE,
    ):
        violations.append("SQL special COALESCE must not be schema-qualified")
    if normalized.count(TASK_4W_OBJECT_FILTERED_SENSITIVE_JSONPATH) != 9:
        violations.append("nine object-filtered recursive sensitive-field JSONPaths")
    if TASK_4W_UNGUARDED_SENSITIVE_JSONPATH in normalized:
        violations.append("unguarded recursive keyvalue JSONPath")
    required = (
        "pg_catalog.to_regprocedure('pg_catalog.gen_random_uuid()') IS NULL",
        "FROM pg_catalog.pg_roles WHERE rolname = 'wow_exact_worker'",
        "role_can_login IS DISTINCT FROM false",
        "CREATE TABLE ops.websim_exact_import_jobs",
        "job_id bigserial PRIMARY KEY",
        "owner_key_hash text NOT NULL CHECK (owner_key_hash ~ '^sha256:[0-9a-f]{64}$')",
        "request_key text NOT NULL CHECK (request_key ~ '^exact-import-request:sha256:[0-9a-f]{64}$')",
        "pg_catalog.octet_length(request_bytes) BETWEEN 2 AND 131072",
        "request_json = pg_catalog.convert_from(request_bytes, 'UTF8')::jsonb",
        "request_key = 'exact-import-request:sha256:' || pg_catalog.encode(pg_catalog.sha256(request_bytes), 'hex')",
        "status IN ('pending', 'running', 'resolved', 'blocked', 'unsupported', 'failed')",
        "terminal_classification IN ('resolved', 'incomplete', 'illegal', 'runtime_gap', 'internal_error')",
        "attempt BETWEEN 0 AND 3",
        "lease_until = heartbeat_at + interval '30 seconds'",
        "cooldown_until = finished_at + interval '15 minutes'",
        "retryPolicyRevision=exact-import-retry-policy-v1",
        "CREATE UNIQUE INDEX uq_ops_websim_exact_jobs_deterministic ON ops.websim_exact_import_jobs (owner_key_hash, request_key) WHERE status IN ('pending', 'running', 'resolved', 'blocked', 'unsupported')",
        "CREATE INDEX idx_ops_websim_exact_jobs_failed_cooldown ON ops.websim_exact_import_jobs (owner_key_hash, request_key, cooldown_until DESC, job_id DESC) WHERE status = 'failed'",
        "CREATE INDEX idx_ops_websim_exact_jobs_claim ON ops.websim_exact_import_jobs (status, lease_until, queued_at, job_id)",
        "CREATE INDEX idx_ops_websim_exact_jobs_retention ON ops.websim_exact_import_jobs (finished_at, job_id) WHERE status IN ('resolved', 'blocked', 'unsupported', 'failed')",
        "CREATE TABLE ops.websim_exact_worker_state",
        "CREATE TABLE ops.websim_exact_import_metrics_daily",
        "PRIMARY KEY (metric_day, terminal_classification, catalog_status)",
        "pg_catalog.pg_advisory_xact_lock",
        "FOR UPDATE SKIP LOCKED",
        "pg_catalog.gen_random_uuid()",
        "lease_until = observed_at + interval '30 seconds'",
        "started_at = COALESCE(candidate.started_at, observed_at)",
        "finished_at + interval '7 days'",
        "metric_day < pg_catalog.clock_timestamp()::date - 90",
        "'ATTEMPT_EXHAUSTED'",
        "INSERT INTO ops.schema_migrations (id, description) VALUES ( '0032_websim_exact_import_jobs'",
    )
    for clause in required:
        if clause not in normalized:
            violations.append(f"required: {clause}")
    monotonic_metrics = (
        "first_outcome_at = LEAST(ops.websim_exact_import_metrics_daily.first_outcome_at, EXCLUDED.first_outcome_at)",
        "last_outcome_at = GREATEST(ops.websim_exact_import_metrics_daily.last_outcome_at, EXCLUDED.last_outcome_at)",
    )
    for clause in monotonic_metrics:
        if normalized.count(clause) != 2:
            violations.append(f"two monotonic metric upserts: {clause}")
    if "last_outcome_at = EXCLUDED.last_outcome_at" in normalized:
        violations.append("metric last_outcome_at must never regress")

    enqueue_start = "CREATE OR REPLACE FUNCTION ops.websim_exact_enqueue("
    enqueue_end = "CREATE OR REPLACE FUNCTION ops.websim_exact_read("
    enqueue_segment = normalized[
        normalized.index(enqueue_start):normalized.index(enqueue_end)
    ]
    enqueue_clock = "observed_at := pg_catalog.clock_timestamp();"
    if "observed_at timestamptz := pg_catalog.clock_timestamp()" in enqueue_segment:
        violations.append("enqueue clock sample must not precede advisory lock")
    if not re.search(
        r"PERFORM pg_catalog\.pg_advisory_xact_lock\(.*?\);\s*"
        r"observed_at := pg_catalog\.clock_timestamp\(\);\s*"
        r"SELECT jobs\.\* INTO existing_job",
        enqueue_segment,
    ):
        violations.append("enqueue advisory lock then immediate clock sample")
    if enqueue_segment.count(enqueue_clock) != 1:
        violations.append("enqueue exact one post-lock clock sample")

    claim_start = "CREATE OR REPLACE FUNCTION ops.websim_exact_claim("
    claim_end = "CREATE OR REPLACE FUNCTION ops.websim_exact_heartbeat("
    claim_segment = normalized[
        normalized.index(claim_start):normalized.index(claim_end)
    ]
    claim_entry_clock = "observed_at timestamptz := pg_catalog.clock_timestamp();"
    exhausted_select = "WITH exhausted AS ( SELECT jobs.job_id"
    exhausted_metric_end = (
        "last_outcome_at = GREATEST("
        "ops.websim_exact_import_metrics_daily.last_outcome_at, "
        "EXCLUDED.last_outcome_at);"
    )
    claim_candidate = "SELECT jobs.* INTO candidate"
    claim_order = tuple(
        claim_segment.find(clause)
        for clause in (
            claim_entry_clock,
            exhausted_select,
            exhausted_metric_end,
            enqueue_clock,
            claim_candidate,
        )
    )
    if any(index < 0 for index in claim_order) or claim_order != tuple(sorted(claim_order)):
        violations.append("claim entry clock then exhausted metric then resample then candidate")
    if claim_segment.count(enqueue_clock) != 1:
        violations.append("claim exact one post-metric clock resample")

    cas_functions = (
        ("ops.websim_exact_heartbeat", "ops.websim_exact_terminalize"),
        ("ops.websim_exact_terminalize", "ops.websim_exact_update_worker_state"),
    )
    lock_clause = (
        "SELECT jobs.* INTO candidate "
        "FROM ops.websim_exact_import_jobs AS jobs "
        "WHERE jobs.job_id = p_job_id "
        "AND jobs.status = 'running' "
        "AND jobs.lock_token = p_lock_token "
        "FOR UPDATE;"
    )
    post_lock_clock = "observed_at := pg_catalog.clock_timestamp();"
    post_lock_expiry = "IF candidate.lease_until <= observed_at THEN RETURN; END IF;"
    for function_name, next_function_name in cas_functions:
        start_marker = f"CREATE OR REPLACE FUNCTION {function_name}("
        end_marker = f"CREATE OR REPLACE FUNCTION {next_function_name}("
        if start_marker not in normalized or end_marker not in normalized:
            violations.append(f"post-lock CAS function boundary: {function_name}")
            continue
        segment = normalized[
            normalized.index(start_marker):normalized.index(end_marker)
        ]
        if "observed_at timestamptz := pg_catalog.clock_timestamp()" in segment:
            violations.append(f"pre-lock clock sample forbidden: {function_name}")
        ordered = tuple(
            segment.find(clause)
            for clause in (lock_clause, post_lock_clock, post_lock_expiry)
        )
        if any(index < 0 for index in ordered) or ordered != tuple(sorted(ordered)):
            violations.append(f"lock then clock then expiry order: {function_name}")

    created_tables = tuple(re.findall(
        r"\bCREATE\s+TABLE\s+([^\s(]+)\s*\(",
        normalized,
        flags=re.IGNORECASE,
    ))
    expected_tables = (
        "ops.websim_exact_import_jobs",
        "ops.websim_exact_worker_state",
        "ops.websim_exact_import_metrics_daily",
    )
    if sorted(created_tables) != sorted(expected_tables):
        violations.append(f"exact three-table universe: {created_tables}")

    signatures = (
        "ops.websim_exact_enqueue(text, bytea, jsonb)",
        "ops.websim_exact_read(text, bigint)",
        "ops.websim_exact_claim(text, text, text)",
        "ops.websim_exact_heartbeat(bigint, uuid)",
        "ops.websim_exact_terminalize(bigint, uuid, text, text, jsonb, jsonb, text)",
        "ops.websim_exact_update_worker_state(text, text, text, text, bigint, jsonb)",
        "ops.websim_exact_prune_jobs(integer)",
        "ops.websim_exact_prune_metrics(integer)",
    )
    created = tuple(re.findall(
        r"\bCREATE\s+OR\s+REPLACE\s+FUNCTION\s+([^\s(]+)\s*\(",
        normalized,
        flags=re.IGNORECASE,
    ))
    expected_names = tuple(signature.split("(", 1)[0] for signature in signatures)
    if sorted(created) != sorted(expected_names):
        violations.append(f"exact eight-function universe: {created}")
    if normalized.count("SECURITY DEFINER SET search_path = pg_catalog, pg_temp") != 8:
        violations.append("eight SECURITY DEFINER fixed-search-path declarations")
    for signature in signatures:
        if normalized.count(f"ALTER FUNCTION {signature} OWNER TO wow_migrator;") != 1:
            violations.append(f"wow_migrator function owner: {signature}")
        if normalized.count(
            f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC, wow_app, wow_exact_worker;"
        ) != 1:
            violations.append(f"signature-specific function revoke: {signature}")

    acl_required = (
        "GRANT USAGE ON SCHEMA cache, ops TO wow_exact_worker;",
        "REVOKE ALL ON ops.websim_exact_import_jobs, ops.websim_exact_worker_state, ops.websim_exact_import_metrics_daily FROM PUBLIC, wow_app, wow_exact_worker;",
        "REVOKE ALL ON SEQUENCE ops.websim_exact_import_jobs_job_id_seq FROM PUBLIC, wow_app, wow_exact_worker;",
        "GRANT SELECT, INSERT ON cache.websim_canonical_documents, cache.websim_effect_aggregate_records, cache.websim_exact_authority_bundles TO wow_exact_worker;",
        "GRANT EXECUTE ON FUNCTION ops.websim_exact_enqueue(text, bytea, jsonb), ops.websim_exact_read(text, bigint) TO wow_app;",
        "GRANT EXECUTE ON FUNCTION ops.websim_exact_claim(text, text, text), ops.websim_exact_heartbeat(bigint, uuid), ops.websim_exact_terminalize(bigint, uuid, text, text, jsonb, jsonb, text), ops.websim_exact_update_worker_state(text, text, text, text, bigint, jsonb), ops.websim_exact_prune_jobs(integer), ops.websim_exact_prune_metrics(integer) TO wow_exact_worker;",
    )
    for clause in acl_required:
        if normalized.count(clause) != 1:
            violations.append(f"fixed ACL: {clause}")

    forbidden = (
        "CREATE ROLE", "ALTER ROLE", "CREATEROLE", "CREATE EXTENSION",
        "EXECUTE format", "EXECUTE IMMEDIATE", "WOW_DATABASE_URL", "@.key()",
    )
    for clause in forbidden:
        if clause.lower() in normalized.lower():
            violations.append(f"forbidden SQL: {clause}")

    migration_names = [name for name, _body in migrations]
    if migration_names.count("0032_websim_exact_import_jobs.sql") != 1:
        violations.append("0032 filename identity")
    if sum(body.count("'0032_websim_exact_import_jobs'") for _name, body in migrations) != 1:
        violations.append("0032 ledger identity")
    return violations


def exact_template_authority_binding_schema_violations(sql, migrations):
    """Static 0033 source-binding contract; real DB behavior is candidate-only."""

    normalized = _normalized(sql)
    violations = []
    required = (
        "CREATE TABLE app.websim_exact_template_authority_bindings",
        "binding_key text PRIMARY KEY CHECK (binding_key ~ '^exact-template-authority-binding:sha256:[0-9a-f]{64}$')",
        "user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE",
        "template_id uuid NOT NULL REFERENCES app.build_templates(id) ON DELETE CASCADE",
        "template_config_hash text NOT NULL CHECK (template_config_hash ~ '^[0-9a-f]{64}$')",
        "source_payload_hash text NOT NULL CHECK (source_payload_hash ~ '^sha256:[0-9a-f]{64}$')",
        "selection_signature text NOT NULL CHECK (selection_signature ~ '^sha256:[0-9a-f]{64}$')",
        "binding_json = pg_catalog.convert_from(binding_bytes, 'UTF8')::jsonb",
        "binding_key = 'exact-template-authority-binding:sha256:' || pg_catalog.encode(pg_catalog.sha256(binding_bytes), 'hex')",
        "CREATE TABLE app.websim_exact_template_authority_binding_slots",
        "exact_authority_envelope_key text NOT NULL REFERENCES cache.websim_exact_authority_bundles(exact_authority_envelope_key) ON DELETE RESTRICT",
        "PRIMARY KEY (binding_key, ordinal)",
        "UNIQUE (binding_key, slot)",
        "UNIQUE (binding_key, exact_authority_envelope_key)",
        "CREATE CONSTRAINT TRIGGER trg_websim_exact_template_authority_binding_complete",
        "CREATE CONSTRAINT TRIGGER trg_websim_exact_template_authority_binding_slots_complete",
        "CREATE TRIGGER trg_websim_exact_template_authority_binding_delete",
        "CREATE TRIGGER trg_websim_exact_template_authority_binding_slots_delete",
        "direct deletion of exact template authority bindings is forbidden",
        "CREATE OR REPLACE FUNCTION ops.websim_exact_template_binding_admit(",
        "CREATE OR REPLACE FUNCTION ops.websim_exact_template_binding_read(",
        "SECURITY DEFINER",
        "SET search_path = pg_catalog, app, cache, ops, pg_temp",
        "ALTER FUNCTION ops.websim_exact_template_binding_admit(uuid, uuid, text, text, text, bytea) OWNER TO wow_migrator",
        "ALTER FUNCTION ops.websim_exact_template_binding_read(uuid, uuid, text, text, text, text, text, text, text) OWNER TO wow_migrator",
        "REVOKE ALL ON app.websim_exact_template_authority_bindings, app.websim_exact_template_authority_binding_slots FROM PUBLIC, wow_app, wow_exact_worker",
        "GRANT EXECUTE ON FUNCTION ops.websim_exact_template_binding_admit(uuid, uuid, text, text, text, bytea), ops.websim_exact_template_binding_read(uuid, uuid, text, text, text, text, text, text, text) TO wow_app",
        "'0033_websim_exact_template_authority_binding'",
    )
    for clause in required:
        if clause not in normalized:
            violations.append(f"required: {clause}")
    forbidden = (
        "CREATE ROLE",
        "ALTER ROLE",
        "DROP ROLE",
        "CREATE DATABASE",
        "DROP DATABASE",
        "ALTER DATABASE",
        "UPDATE cache.websim_exact_authority_bundles",
        "INSERT INTO cache.websim_exact_authority_bundles",
        "UPDATE cache.websim_canonical_documents",
        "INSERT INTO cache.websim_canonical_documents",
        "rawProfile",
        "rawString",
        "playerName",
        "characterName",
        "realm",
        "server",
    )
    for clause in forbidden:
        if clause.lower() in normalized.lower():
            violations.append(f"forbidden: {clause}")
    migration_names = [name for name, _body in migrations]
    if migration_names.count("0033_websim_exact_template_authority_binding.sql") != 1:
        violations.append("0033 filename identity")
    if sum(body.count("'0033_websim_exact_template_authority_binding'") for _name, body in migrations) != 1:
        violations.append("0033 ledger identity")
    return violations


def exact_job_snapshot_binding_schema_violations(sql, migrations):
    """Static 0034 contract; database execution remains candidate-only."""

    normalized = _normalized(sql)
    violations = []
    required = (
        "CREATE OR REPLACE FUNCTION ops.websim_exact_import_request_is_valid(",
        "RETURNS boolean",
        "IMMUTABLE",
        "SECURITY INVOKER",
        "SET search_path = pg_catalog, pg_temp",
        "exact-import-job-request-v1",
        "exact-import-job-request-v2",
        "resolvedLoadoutKey",
        "simulationSnapshotKey",
        "snapshotRowHash",
        "^resolved-loadout-v2:sha256:[0-9a-f]{64}$",
        "^simulation-snapshot-v2:sha256:[0-9a-f]{64}$",
        "^sha256:[0-9a-f]{64}$",
        "pg_catalog.pg_get_constraintdef",
        "ALTER TABLE ops.websim_exact_import_jobs DROP CONSTRAINT",
        "ADD CONSTRAINT websim_exact_import_jobs_request_schema_v1_v2_check",
        "ops.websim_exact_import_request_is_valid(request_json)",
        "CREATE OR REPLACE FUNCTION ops.websim_exact_enqueue(",
        "CREATE OR REPLACE FUNCTION ops.websim_exact_claim(",
        "NOT ops.websim_exact_import_request_is_valid(p_request_json)",
        "NOT ops.websim_exact_import_request_is_valid(candidate.request_json)",
        "REVOKE ALL ON FUNCTION ops.websim_exact_import_request_is_valid(jsonb) FROM PUBLIC, wow_app, wow_exact_worker;",
        "@.key == \"rawProfile\"",
        "@.key == \"rawString\"",
        "@.key == \"playerName\"",
        "@.key == \"characterName\"",
        "@.key == \"realm\"",
        "@.key == \"server\"",
        "'0034_websim_exact_job_snapshot_binding'",
    )
    for clause in required:
        if clause not in normalized:
            violations.append(f"required: {clause}")
    forbidden = (
        "CREATE TABLE",
        "GRANT EXECUTE ON FUNCTION ops.websim_exact_import_request_is_valid",
        "CREATE ROLE",
        "ALTER ROLE",
        "CREATE DATABASE",
        "ALTER DATABASE",
    )
    for clause in forbidden:
        if clause.lower() in normalized.lower():
            violations.append(f"forbidden: {clause}")
    if normalized.count("CREATE OR REPLACE FUNCTION ops.websim_exact_enqueue(") != 1:
        violations.append("one unchanged enqueue signature")
    if normalized.count("CREATE OR REPLACE FUNCTION ops.websim_exact_claim(") != 1:
        violations.append("one unchanged claim signature")
    migration_names = [name for name, _body in migrations]
    if migration_names.count("0034_websim_exact_job_snapshot_binding.sql") != 1:
        violations.append("0034 filename identity")
    if sum(body.count("'0034_websim_exact_job_snapshot_binding'") for _name, body in migrations) != 1:
        violations.append("0034 ledger identity")
    return violations


def exact_runtime_authority_release_schema_violations(sql, migrations):
    """Static 0035 release/index contract; database execution is candidate-only."""

    normalized = _normalized(sql)
    violations = []
    required = (
        "CREATE TABLE ops.websim_exact_runtime_resolver_contexts",
        "CREATE TABLE ops.websim_exact_runtime_authority_releases",
        "CREATE TABLE ops.websim_exact_runtime_occurrence_index_entries",
        "runtime_authority_release_key text PRIMARY KEY REFERENCES cache.websim_canonical_documents(content_key) ON DELETE RESTRICT",
        "binding_key text NOT NULL REFERENCES app.websim_exact_template_authority_bindings(binding_key) ON DELETE RESTRICT",
        "effect_record_key text NOT NULL REFERENCES cache.websim_canonical_documents(content_key) ON DELETE RESTRICT",
        "CREATE OR REPLACE FUNCTION ops.websim_exact_runtime_authority_release_admit(",
        "CREATE OR REPLACE FUNCTION ops.websim_exact_runtime_authority_release_read(",
        "CREATE OR REPLACE FUNCTION ops.websim_exact_runtime_authority_release_occurrences_read(",
        "SECURITY DEFINER",
        "OWNER TO wow_migrator",
        "ops.reject_websim_exact_runtime_authority_release_mutation()",
        "BEFORE UPDATE OR DELETE ON ops.%I",
        "BEFORE TRUNCATE ON ops.%I",
        "runtime_authority_release_key text REFERENCES ops.websim_exact_runtime_authority_releases(runtime_authority_release_key) ON DELETE RESTRICT",
        "resolver_context_key text REFERENCES ops.websim_exact_runtime_resolver_contexts(resolver_context_key) ON DELETE RESTRICT",
        "dependency_vector_json jsonb",
        "pg_catalog.jsonb_typeof(resolver_replay_context_json) IS NOT DISTINCT FROM 'object'",
        "PERFORM cache.verify_websim_resolver_replay_context( NEW.resolver_replay_context_json );",
        "NEW.resolver_replay_context_json -> 'dependencyVector' ->> 'gearRuleRevision' IS DISTINCT FROM v_release_vector ->> 'gearRuleRevision'",
        "NEW.resolver_replay_context_json -> 'dependencyVector' ->> 'resolverContractRevision' IS DISTINCT FROM v_release_vector ->> 'resolverRevision'",
        "NEW.resolver_replay_context_json -> 'dependencyVector' ->> 'simcRuntimeRevision' IS DISTINCT FROM v_release_vector ->> 'simcRuntimeRevision'",
        "resolved-loadout-v3",
        "simulation-snapshot-v3",
        "exact-import-job-request-v3",
        "^resolved-loadout-v3:sha256:[0-9a-f]{64}$",
        "^simulation-snapshot-v3:sha256:[0-9a-f]{64}$",
        "^exact-runtime-authority-release:sha256:[0-9a-f]{64}$",
        "^exact-runtime-resolver-context:sha256:[0-9a-f]{64}$",
        "REVOKE ALL ON ops.websim_exact_runtime_resolver_contexts, ops.websim_exact_runtime_authority_releases, ops.websim_exact_runtime_occurrence_index_entries FROM PUBLIC, wow_app, wow_exact_worker",
        "'0035_websim_exact_runtime_authority_release'",
    )
    for clause in required:
        if clause not in normalized:
            violations.append(f"required: {clause}")
    release_tables = (
        "ops.websim_exact_runtime_resolver_contexts",
        "ops.websim_exact_runtime_authority_releases",
        "ops.websim_exact_runtime_occurrence_index_entries",
    )
    for grant in re.finditer(
        r"GRANT\s+(.+?)\s+ON\s+(.+?)\s+TO\s+(\w+)\s*;",
        normalized,
        re.IGNORECASE,
    ):
        privileges, tables, role = grant.groups()
        if role.lower() not in {"wow_app", "wow_exact_worker"}:
            continue
        granted = {token.strip().upper() for token in privileges.split(",")}
        for table in release_tables:
            if table not in tables:
                continue
            for verb in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                if verb in granted or "ALL" in granted:
                    violations.append(f"{role} direct {verb} on {table}")
    forbidden = (
        "CREATE ROLE", "ALTER ROLE", "DROP ROLE", "CREATE DATABASE", "DROP DATABASE",
        "ORDER BY sealed_at DESC", "LIMIT 1",
    )
    for clause in forbidden:
        if clause.lower() in normalized.lower():
            violations.append(f"forbidden: {clause}")
    migration_names = [name for name, _body in migrations]
    if migration_names.count("0035_websim_exact_runtime_authority_release.sql") != 1:
        violations.append("0035 filename identity")
    if sum(body.count("'0035_websim_exact_runtime_authority_release'") for _name, body in migrations) != 1:
        violations.append("0035 ledger identity")
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
        cls.websim_exact_snapshot_v2_sql = WEBSIM_EXACT_SNAPSHOT_V2.read_text(encoding="utf-8")

    def test_exact_authority_bundle_migration_binds_bytes_closure_and_read_only_grants(self):
        normalized = " ".join(self.websim_exact_authority_bundle_sql.split())
        migrations = tuple(
            (path.name, path.read_text(encoding="utf-8"))
            for path in POSTGRES_MIGRATIONS_0001_0031
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
        self.assertIn("0030_websim_exact_authority_bundle", normalized)

    def test_exact_authority_contract_mutations_fail_closed(self):
        migrations = tuple(
            (path.name, path.read_text(encoding="utf-8"))
            for path in POSTGRES_MIGRATIONS_0001_0031
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
            "SELECT '0030_websim_exact_authority_bundle';",
        ),)
        self.assertTrue(exact_authority_schema_violations(
            self.websim_exact_authority_bundle_sql,
            duplicate_identity,
        ))

    def test_exact_snapshot_v2_migration_has_conditional_relations_and_read_only_boundary(self):
        migrations = tuple(
            (path.name, path.read_text(encoding="utf-8"))
            for path in POSTGRES_MIGRATIONS_0001_0031
        )
        self.assertEqual(
            exact_snapshot_v2_schema_violations(
                self.websim_exact_snapshot_v2_sql,
                migrations,
            ),
            [],
        )
        mutations = (
            self.websim_exact_snapshot_v2_sql.replace(
                "effect_record_key text NOT NULL\n"
                "        REFERENCES cache.websim_canonical_documents(content_key)\n"
                "        ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED",
                "effect_record_key text NOT NULL\n"
                "        REFERENCES cache.websim_canonical_documents(content_key)\n"
                "        DEFERRABLE INITIALLY DEFERRED ON DELETE RESTRICT",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "DEFERRABLE INITIALLY DEFERRED", "", 1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "relation.effect_record_key IS DISTINCT FROM\n"
                "                  authority_json->'supportRecords'->wanted.ordinal->>'supportRecordKey'",
                "false",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "REVOKE ALL ON", "REVOKE INSERT ON", 1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "loadout_json -> 'exactAuthorityBySlot'\n                IS NOT DISTINCT FROM exact_authority_by_slot_json",
                "loadout_json -> 'exactAuthorityBySlot'\n                IS NOT DISTINCT FROM ignored_authority_json",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "expected_subject ->> 'subjectKind'",
                "expected_subject ->> 'ignoredSubjectKind'",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "schema_revision = 'resolved-loadout-v1'",
                "schema_revision = 'ignored-loadout-v1'",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "loadout_json ->> 'exactRegistryRevision'",
                "loadout_json ->> 'ignoredExactRegistryRevision'",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "FOREIGN KEY (v1_catalog_revision_ref)\n"
                "        REFERENCES cache.websim_gear_catalog_revisions(catalog_revision)\n"
                "        ON DELETE RESTRICT",
                "FOREIGN KEY (ignored_v1_catalog_revision_ref)\n"
                "        REFERENCES cache.websim_gear_catalog_revisions(catalog_revision)\n"
                "        ON DELETE RESTRICT",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "IF (occurrence ->> 'scope') = 'slot' THEN",
                "IF false THEN",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "        IF saw_loadout_scope THEN\n"
                "            RAISE EXCEPTION "
                "'v2 no-effect rows cannot contain loadout occurrences';\n"
                "        END IF;",
                "        IF false THEN\n"
                "            RAISE EXCEPTION "
                "'v2 no-effect rows cannot contain loadout occurrences';\n"
                "        END IF;",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "IF NOT saw_loadout OR loadout_count <> relation_count THEN",
                "IF false THEN",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "(expected_subject ->> 'status') IS DISTINCT FROM 'verified'",
                "(expected_subject ->> 'status') IS DISTINCT FROM 'ignored'",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "IF loadout_schema_revision IS DISTINCT FROM 'resolved-loadout-v2'",
                "IF false",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "IF loadout_schema_revision IS DISTINCT FROM 'resolved-loadout-v1'",
                "IF false",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "CREATE TRIGGER trg_websim_simulation_snapshot_v1_v2_binding",
                "CREATE TRIGGER trg_removed_simulation_snapshot_v1_v2_binding",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "CREATE TRIGGER trg_websim_resolved_loadout_v1_v2_binding",
                "CREATE TRIGGER trg_removed_resolved_loadout_v1_v2_binding",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "CREATE OR REPLACE FUNCTION cache.verify_websim_resolver_replay_context",
                "CREATE OR REPLACE FUNCTION cache.removed_websim_resolver_replay_context",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "PERFORM cache.verify_websim_resolver_replay_context(\n"
                "            NEW.resolver_replay_context_json\n"
                "        );",
                "PERFORM NULL;",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "NEW.resolver_replay_context_json -> 'v2EffectBoundary'\n"
                "               ->> 'loadoutEffectAuthorityKey'\n"
                "           IS DISTINCT FROM NEW.loadout_effect_authority_key",
                "false",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "CREATE OR REPLACE FUNCTION cache.verify_websim_v2_exact_authority_pairs",
                "CREATE OR REPLACE FUNCTION cache.removed_websim_v2_exact_authority_pairs",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "(pair - ARRAY['slot', 'exactAuthorityEnvelopeKey']) "
                "<> '{}'::jsonb",
                "false",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "pg_catalog.jsonb_array_length(p_pairs) IS DISTINCT FROM\n"
                "          pg_catalog.jsonb_array_length(\n"
                "              p_replay -> 'profileReadiness' -> 'requiredSlots'\n"
                "          )",
                "false",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "pair_slot IS DISTINCT FROM (\n"
                "                p_replay -> 'profileReadiness' -> 'requiredSlots'\n"
                "                    ->> pair_ordinal\n"
                "            )",
                "false",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "progression_json -> 'trackAuthorityInput' ->> 'slot'\n"
                "              IS DISTINCT FROM pair_slot",
                "false",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "exact_json ->> 'itemId' IS DISTINCT FROM\n"
                "              p_replay -> 'resolvedSlots' -> pair_slot ->> 'itemId'",
                "false",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "WHERE stated_pair.value ->> 'slot'\n"
                "                    IS NOT DISTINCT FROM occurrence ->> 'slot'",
                "WHERE false",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "PERFORM cache.verify_websim_v2_exact_authority_pairs(\n"
                "            NEW.exact_authority_by_slot_json,\n"
                "            NEW.resolver_replay_context_json,\n"
                "            NEW.loadout_json,\n"
                "            NEW.effect_evidence_by_occurrence_json\n"
                "        );",
                "PERFORM NULL;",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "loadout_exact_authority_by_slot\n"
                "              IS DISTINCT FROM NEW.exact_authority_by_slot_json",
                "false",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "pg_catalog.octet_length(identity_token.value)\n"
                "              NOT BETWEEN 1 AND 256",
                "false",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "identity_token.value\n"
                "              !~ '^[A-Za-z0-9][A-Za-z0-9._:/-]*$'",
                "false",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "        identity_tokens := identity_tokens || ARRAY[\n"
                "            active_effect ->> 'effectId',\n"
                "            active_effect ->> 'itemSetId'\n"
                "        ];",
                "",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "        identity_tokens := identity_tokens || ARRAY[\n"
                "            subject ->> 'subjectKind',\n"
                "            subject ->> 'itemSetId',\n"
                "            subject ->> 'subjectKey'\n"
                "        ];",
                "",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "        'sourceRefIds',\n"
                "        'sourcePayload'\n"
                "    ];",
                "        'sourceRefIds'\n"
                "    ];",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "pg_catalog.jsonb_typeof(occurrence -> 'subjectKind')\n"
                "                  "
                "IS DISTINCT FROM 'string'",
                "false",
                1,
            ),
            self.websim_exact_snapshot_v2_sql.replace(
                "pg_catalog.jsonb_typeof(expected_subject -> 'subjectKind')\n"
                "                  "
                "IS DISTINCT FROM 'string'",
                "false",
                1,
            ),
        )
        for mutated in mutations:
            with self.subTest(mutated=mutated[:80]):
                self.assertTrue(
                    exact_snapshot_v2_schema_violations(mutated, migrations),
                )

    def test_exact_import_jobs_migration_has_fixed_role_schema_function_and_acl_surface(self):
        self.assertTrue(
            WEBSIM_EXACT_IMPORT_JOBS.exists(),
            "missing static 0032 exact import jobs migration",
        )
        sql = WEBSIM_EXACT_IMPORT_JOBS.read_text(encoding="utf-8")
        migrations = tuple(
            (path.name, path.read_text(encoding="utf-8"))
            for path in POSTGRES_MIGRATIONS_0001_0032
        )
        self.assertEqual(exact_import_jobs_schema_violations(sql, migrations), [])

    def test_exact_template_authority_binding_migration_is_owner_scoped_append_only_and_no_registry_writer(self):
        self.assertTrue(
            WEBSIM_EXACT_TEMPLATE_AUTHORITY_BINDING.exists(),
            "missing static 0033 exact template authority binding migration",
        )
        sql = WEBSIM_EXACT_TEMPLATE_AUTHORITY_BINDING.read_text(encoding="utf-8")
        migrations = tuple(
            (path.name, path.read_text(encoding="utf-8"))
            for path in POSTGRES_MIGRATIONS_0001_0033
        )
        self.assertEqual(
            exact_template_authority_binding_schema_violations(sql, migrations),
            [],
        )

    def test_exact_job_snapshot_binding_preserves_v1_and_accepts_only_sealed_v2_references(self):
        self.assertTrue(
            WEBSIM_EXACT_JOB_SNAPSHOT_BINDING.exists(),
            "missing static 0034 exact job-to-snapshot binding migration",
        )
        sql = WEBSIM_EXACT_JOB_SNAPSHOT_BINDING.read_text(encoding="utf-8")
        migrations = tuple(
            (path.name, path.read_text(encoding="utf-8"))
            for path in POSTGRES_MIGRATIONS_0001_0034
        )
        self.assertEqual(
            exact_job_snapshot_binding_schema_violations(sql, migrations),
            [],
        )

    def test_exact_runtime_authority_release_migration_is_append_only_and_app_worker_have_no_direct_dml(self):
        self.assertTrue(
            WEBSIM_EXACT_RUNTIME_AUTHORITY_RELEASE.exists(),
            "missing static 0035 exact runtime authority release migration",
        )
        sql = WEBSIM_EXACT_RUNTIME_AUTHORITY_RELEASE.read_text(encoding="utf-8")
        migrations = tuple(
            (path.name, path.read_text(encoding="utf-8"))
            for path in POSTGRES_MIGRATIONS_0001_0035
        )
        self.assertEqual(
            exact_runtime_authority_release_schema_violations(sql, migrations),
            [],
        )
        mutations = (
            sql.replace(
                "BEFORE UPDATE OR DELETE ON ops.%I",
                "BEFORE UPDATE ON ops.%I",
                1,
            ),
            sql.replace(
                "REVOKE ALL ON\n    ops.websim_exact_runtime_resolver_contexts,",
                "REVOKE INSERT ON\n    ops.websim_exact_runtime_resolver_contexts,",
                1,
            ),
            sql + "\nGRANT INSERT ON ops.websim_exact_runtime_authority_releases TO wow_app;\n",
            sql.replace(
                "ORDER BY release.runtime_authority_release_key;",
                "ORDER BY release.sealed_at DESC LIMIT 1;",
                1,
            ),
            sql.replace(
                "PERFORM cache.verify_websim_resolver_replay_context(\n"
                "        NEW.resolver_replay_context_json\n"
                "    );",
                "PERFORM NULL;",
                1,
            ),
        )
        for mutated in mutations:
            with self.subTest(mutated=mutated[-100:]):
                self.assertTrue(
                    exact_runtime_authority_release_schema_violations(
                        mutated,
                        migrations,
                    ),
                )

    def test_0035_forward_fix_disambiguates_the_frozen_binding_admit_conflict_target(self):
        sql = WEBSIM_EXACT_RUNTIME_AUTHORITY_RELEASE.read_text(encoding="utf-8")
        normalized = _normalized(sql)
        self.assertIn(
            "CREATE OR REPLACE FUNCTION ops.websim_exact_template_binding_admit(",
            normalized,
        )
        self.assertIn(
            "ON CONFLICT ON CONSTRAINT "
            "websim_exact_template_authority_bindings_pkey DO NOTHING;",
            normalized,
        )

    def test_0035_forward_fix_runs_the_binding_relation_trigger_as_migrator(self):
        sql = WEBSIM_EXACT_RUNTIME_AUTHORITY_RELEASE.read_text(encoding="utf-8")
        normalized = _normalized(sql)
        frozen = _normalized(
            WEBSIM_EXACT_TEMPLATE_AUTHORITY_BINDING.read_text(encoding="utf-8")
        )
        self.assertIn(
            "CREATE OR REPLACE FUNCTION "
            "app.verify_websim_exact_template_authority_binding_relations()",
            frozen,
        )
        self.assertIn(
            "SET search_path = pg_catalog, app, cache, pg_temp",
            frozen,
        )
        self.assertIn(
            "ALTER FUNCTION "
            "app.verify_websim_exact_template_authority_binding_relations() "
            "SECURITY DEFINER;",
            normalized,
        )
        self.assertIn(
            "ALTER FUNCTION "
            "app.verify_websim_exact_template_authority_binding_relations() "
            "OWNER TO wow_migrator;",
            normalized,
        )
        self.assertIn(
            "REVOKE ALL ON FUNCTION "
            "app.verify_websim_exact_template_authority_binding_relations() "
            "FROM PUBLIC, wow_app, wow_exact_worker;",
            normalized,
        )

    def test_0035_forward_extends_historical_snapshot_key_checks_to_v3(self):
        normalized = _normalized(
            WEBSIM_EXACT_RUNTIME_AUTHORITY_RELEASE.read_text(encoding="utf-8")
        )
        for table, constraint, key, prefix in (
            (
                "cache.websim_gear_resolved_loadouts",
                "websim_gear_resolved_loadouts_resolved_loadout_key_check",
                "resolved_loadout_key",
                "resolved-loadout",
            ),
            (
                "cache.websim_simulation_snapshots",
                "websim_simulation_snapshots_simulation_snapshot_key_check",
                "simulation_snapshot_key",
                "simulation-snapshot",
            ),
        ):
            with self.subTest(table=table):
                self.assertIn(
                    f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint}, "
                    f"ADD CONSTRAINT {constraint} CHECK ({key} ~ "
                    f"'^{prefix}(-v[23])?:sha256:[0-9a-f]{{64}}$');",
                    normalized,
                )

    def test_0035_forward_grants_v3_request_validator_only_to_enqueue_owner(self):
        normalized = _normalized(
            WEBSIM_EXACT_RUNTIME_AUTHORITY_RELEASE.read_text(encoding="utf-8")
        )
        self.assertIn(
            "GRANT EXECUTE ON FUNCTION ops.websim_exact_import_request_is_valid(jsonb) "
            "TO wow_migrator;",
            normalized,
        )
        self.assertNotIn(
            "GRANT EXECUTE ON FUNCTION ops.websim_exact_import_request_is_valid(jsonb) "
            "TO wow_app, wow_exact_worker;",
            normalized,
        )

    def test_exact_import_jobs_rejects_schema_qualified_coalesce_variants(self):
        sql = WEBSIM_EXACT_IMPORT_JOBS.read_text(encoding="utf-8")
        migrations = tuple(
            (path.name, path.read_text(encoding="utf-8"))
            for path in POSTGRES_MIGRATIONS_0001_0032
        )
        mutated = sql.replace(
            "COALESCE(candidate.started_at, observed_at)",
            "pg_catalog.COALESCE (candidate.started_at, observed_at)",
            1,
        )
        self.assertNotEqual(mutated, sql)
        self.assertIn(
            "SQL special COALESCE must not be schema-qualified",
            exact_import_jobs_schema_violations(mutated, migrations),
        )

    def test_exact_import_jobs_rejects_unguarded_recursive_keyvalue_jsonpath(self):
        sql = WEBSIM_EXACT_IMPORT_JOBS.read_text(encoding="utf-8")
        migrations = tuple(
            (path.name, path.read_text(encoding="utf-8"))
            for path in POSTGRES_MIGRATIONS_0001_0032
        )
        self.assertEqual(
            sql.count(TASK_4W_OBJECT_FILTERED_SENSITIVE_JSONPATH),
            9,
        )
        mutated = sql.replace(
            TASK_4W_OBJECT_FILTERED_SENSITIVE_JSONPATH,
            TASK_4W_UNGUARDED_SENSITIVE_JSONPATH,
            1,
        )
        self.assertIn(
            "unguarded recursive keyvalue JSONPath",
            exact_import_jobs_schema_violations(mutated, migrations),
        )

    def test_exact_worker_service_deploy_and_runbook_remain_dormant_and_secret_safe(self):
        service_path = ROOT / "server" / "wow-gear-exact-authority-worker.service"
        self.assertTrue(service_path.exists(), "missing dedicated exact worker service")
        service = _normalized(service_path.read_text(encoding="utf-8"))
        self.assertIn("EnvironmentFile=/etc/wow-exact-worker.env", service)
        self.assertNotIn("wow-backend.env", service)
        self.assertIn("ExecStart=/usr/bin/python3 -m server.gear_exact_authority_worker", service)

        deploy = (ROOT / "server" / "deploy_lighthouse.sh").read_text(encoding="utf-8")
        self.assertIn("WOW_DEPLOY_EXACT_WORKER_PREFLIGHT", deploy)
        self.assertIn("wow-gear-exact-authority-worker.service", deploy)
        self.assertIn("/etc/wow-exact-worker.env", deploy)
        self.assertIn("WOW_EXACT_WORKER_DATABASE_URL", deploy)
        self.assertIn("wow_exact_worker", deploy)
        self.assertIn("rolcanlogin", deploy)
        for privilege in (
            "rolinherit", "rolsuper", "rolcreatedb", "rolcreaterole",
            "rolreplication", "rolbypassrls",
        ):
            with self.subTest(deploy_privilege=privilege):
                self.assertIn(privilege, deploy)
        self.assertIn("pg_has_role", deploy)
        self.assertIn("redacted", deploy.lower())
        self.assertIn("rollback", deploy.lower())
        self.assertNotRegex(
            deploy,
            r"systemctl\s+(?:enable|start|restart|enable\s+--now)\s+"
            r"wow-gear-exact-authority-worker\.service",
        )

        runbook = (ROOT / "docs" / "postgres-identity-migration-runbook.md").read_text(encoding="utf-8")
        for value in (
            "wow_exact_worker", "NOLOGIN", "LOGIN INHERIT",
            "/etc/wow-exact-worker.env", "WOW_EXACT_WORKER_DATABASE_URL",
            "WOW_PG_TEST_DSN_MIGRATOR_0032", "WOW_PG_TEST_DSN_APP_0032",
            "WOW_PG_TEST_DSN_WORKER_0032", "SET ROLE wow_exact_worker",
            "0032_websim_exact_import_jobs.sql", "rollback",
        ):
            with self.subTest(value=value):
                self.assertIn(value, runbook)

    def test_migrations_0001_through_0032_never_manage_databases_roles_or_extensions(self):
        self.assertEqual(
            POSTGRES_MIGRATIONS_0001_0032[-1].name,
            "0032_websim_exact_import_jobs.sql",
        )
        database_ddl = re.compile(r"(?i)\b(?:CREATE|DROP|ALTER)\s+DATABASE\b")
        role_ddl = re.compile(r"(?i)\b(?:CREATE|ALTER|DROP)\s+ROLE\b")
        extension_ddl = re.compile(r"(?i)\bCREATE\s+EXTENSION\b")
        for migration in POSTGRES_MIGRATIONS_0001_0032:
            with self.subTest(migration=migration.name):
                body = migration.read_text(encoding="utf-8")
                self.assertIsNone(database_ddl.search(body))
                if migration.name == "0032_websim_exact_import_jobs.sql":
                    self.assertIsNone(role_ddl.search(body))
                    self.assertIsNone(extension_ddl.search(body))

    def test_migrations_0001_through_0031_never_manage_databases(self):
        self.assertEqual(
            POSTGRES_MIGRATIONS_0001_0031[-1].name,
            "0031_websim_exact_snapshot_v2.sql",
        )
        database_ddl = re.compile(
            r"(?i)\b(?:CREATE|DROP|ALTER)\s+DATABASE\b",
        )
        for migration in POSTGRES_MIGRATIONS_0001_0031:
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

    def test_build_template_dedupe_migration_is_fail_closed_semantically_idempotent(self):
        normalized = " ".join(self.build_template_dedupe_sql.split())
        self.assertIn("DROP CONSTRAINT IF EXISTS build_templates_user_id_template_type_name_key", normalized)
        self.assertIn("DO $$", normalized)
        self.assertIn(
            "pg_catalog.pg_constraint con JOIN pg_catalog.pg_class rel ON rel.oid = con.conrelid JOIN pg_catalog.pg_namespace nsp ON nsp.oid = rel.relnamespace",
            normalized,
        )
        self.assertIn("nsp.nspname = 'app'", normalized)
        self.assertIn("rel.relname = 'build_templates'", normalized)
        self.assertIn("con.conname = 'build_templates_user_id_template_type_config_hash_key'", normalized)
        self.assertIn("con.contype = 'u'", normalized)
        self.assertIn("pg_catalog.pg_attribute attr", normalized)
        self.assertIn("WITH ORDINALITY", normalized)
        self.assertIn("SELECT attr.attname::text", normalized)
        self.assertIn("ARRAY['user_id', 'template_type', 'config_hash']", normalized)
        self.assertIn("IF target_constraint_count = 0 THEN", normalized)
        self.assertIn("ADD CONSTRAINT build_templates_user_id_template_type_config_hash_key UNIQUE (user_id, template_type, config_hash)", normalized)
        self.assertIn("IF target_constraint_count <> 1 THEN", normalized)
        self.assertIn("RAISE EXCEPTION", normalized)
        self.assertNotIn("duplicate_object", normalized.lower())
        self.assertIn("0003_build_template_config_hash_unique", normalized)

    def test_task3a_current_truth_tracks_eighth_candidate_delivery_closure(self):
        requirement = json.loads(
            (
                ROOT
                / "artifacts"
                / "releases"
                / "2026-08-04-equipment-simulator-exact-first"
                / "requirement.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(requirement["status"], "implementation_allowed")

        evidence = json.loads(
            (ROOT / "artifacts/releases/2026-08-04-equipment-simulator-exact-first/evidence.json")
            .read_text(encoding="utf-8")
        )
        stage = evidence["status"]
        self.assertIn(
            stage,
            {"implementation_allowed", "local_verified", "runtime_verified"},
        )
        self.assertEqual(stage, evidence["highestEvidenceLevel"])

        backend_owner_map = json.loads(
            (ROOT / "docs" / "backend-owner-map.json").read_text(encoding="utf-8")
        )
        canonical_kernel_hotspot = next(
            hotspot
            for hotspot in backend_owner_map["hotspotFiles"]
            if hotspot["path"] == "server/gear_canonical_kernel.py"
        )
        summary = canonical_kernel_hotspot["summary"]
        self.assertIn("source change-control", summary)
        self.assertIn("0030", summary)
        self.assertNotIn("candidate_rerun_required", summary)
        self.assertNotIn("evidence_promotion_blocked", summary)

        for path in TASK_3A_MIGRATION_CURRENT_TRUTH_FILES:
            with self.subTest(path=path):
                current_truth = path.read_text(encoding="utf-8")
                self.assertIn("0030", current_truth)

        for path in TASK_3A_LIFECYCLE_STATUS_FILES:
            with self.subTest(lifecycle_status_path=path):
                current_truth = path.read_text(encoding="utf-8")
                self.assertIn("t3a260805163536", current_truth)
                self.assertIn("runtime_verified", current_truth)
                self.assertIn("pending", current_truth)

        for path in TASK_3A_HISTORICAL_LIFECYCLE_FILES:
            with self.subTest(historical_lifecycle_path=path):
                current_truth = path.read_text(encoding="utf-8")
                self.assertIn("t3a260805160003", current_truth)
                self.assertIn(
                    "runtime_passed_unpromotable_current_truth_lifecycle_test_regression",
                    current_truth,
                )

        if stage in {"implementation_allowed", "local_verified"}:
            current_risks = {risk["id"]: risk for risk in evidence["risks"]}
            promotion_risk = current_risks[
                "evidence-promotion-and-delivery-closure"
            ]
            self.assertEqual(
                "evidence_promotion_blocked_candidate_rerun_required",
                promotion_risk["status"],
            )
            self.assertNotIn("promotion_review_passed", promotion_risk["status"])
            self.assertNotIn("bound to the fifth", promotion_risk["detail"])
            for path in TASK_3A_LIFECYCLE_STATUS_FILES:
                with self.subTest(pre_runtime_path=path):
                    current_truth = path.read_text(encoding="utf-8")
                    self.assertIn("candidate_rerun_required", current_truth)
                    self.assertIn("evidence_promotion_blocked", current_truth)
        else:
            self.assertEqual(
                "candidate_verified", evidence["candidateDeployment"]["status"]
            )
            self.assertEqual(
                "t3a260805163536", evidence["candidateDeployment"]["runId"]
            )
            self.assertEqual(
                "bound", evidence["identities"]["runtime"]["status"]
            )
            self.assertEqual(
                "pending", evidence["identities"]["closure"]["status"]
            )
            archival = evidence["archival"]
            self.assertEqual(
                "post_merge_scoped_cleanup_recorded_formal_lifecycle_pending",
                archival["status"],
            )
            self.assertEqual("pass", archival["postMergeScopedVerification"]["status"])
            self.assertEqual(
                "verified_before_scoped_cleanup", archival["shaParity"]["status"]
            )

        plan = (
            ROOT
            / "docs/plans/2026-08-04-equipment-simulator-exact-first-persistence-resequence.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Seventh candidate `t3a260805160003`", plan)
        self.assertIn(
            "runtime_passed_unpromotable_current_truth_lifecycle_test_regression",
            plan,
        )
        if stage in {"implementation_allowed", "local_verified"}:
            self.assertIn(
                f"current evidence is `{stage} / candidate_pending`", plan
            )
        self.assertNotIn("final Task 3A code/test state", plan)

    def test_migration_number_prefixes_are_globally_unique(self):
        migrations = POSTGRES_MIGRATIONS_0001_0031
        prefixes = [path.name.split("_", 1)[0] for path in migrations]
        self.assertEqual(len(prefixes), len(set(prefixes)))

    def test_build_template_dedupe_mutation_postcondition_and_ledger_are_one_statement(self):
        atomic_blocks = re.findall(
            r"DO \$\$.*?END \$\$;",
            self.build_template_dedupe_sql,
            flags=re.DOTALL,
        )
        self.assertEqual(len(atomic_blocks), 1)
        atomic_block = atomic_blocks[0]
        self.assertEqual(self.build_template_dedupe_sql.strip(), atomic_block.strip())
        self.assertIn(
            "DROP CONSTRAINT IF EXISTS build_templates_user_id_template_type_name_key",
            atomic_block,
        )
        self.assertIn(
            "ADD CONSTRAINT build_templates_user_id_template_type_config_hash_key",
            atomic_block,
        )
        self.assertIn("RAISE EXCEPTION", atomic_block)
        self.assertIn("INSERT INTO ops.schema_migrations", atomic_block)
        self.assertEqual(
            atomic_block.count("0003_build_template_config_hash_unique"),
            1,
        )

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

    def test_smart_question_chain_appends_immutable_registry_v2_and_moves_only_active_pointer(self):
        self.assertTrue(CHICKENBRO_SMART_QUESTION_CHAIN.exists(), "missing Smart Question Chain migration")
        normalized = " ".join(CHICKENBRO_SMART_QUESTION_CHAIN.read_text(encoding="utf-8").split())
        self.assertIn("source:current-wow-sources:v1", normalized)
        self.assertIn("chickenbro.source.current_wow_sources.v1", normalized)
        self.assertIn("chickenbro-tools-2", normalized)
        self.assertIn("INSERT INTO ops.chickenbro_tool_manifests", normalized)
        self.assertIn("INSERT INTO ops.chickenbro_tool_registry_releases", normalized)
        self.assertIn("INSERT INTO ops.chickenbro_tool_registry_release_manifests", normalized)
        self.assertIn("INSERT INTO ops.chickenbro_tool_registry_active", normalized)
        self.assertIn("0026_chickenbro_smart_question_chain", normalized)

    def test_community_strength_sources_append_registry_v3_without_mutating_prior_releases(self):
        self.assertTrue(CHICKENBRO_COMMUNITY_STRENGTH.exists(), "missing Chickenbro community-strength Registry migration")
        normalized = " ".join(CHICKENBRO_COMMUNITY_STRENGTH.read_text(encoding="utf-8").split())
        self.assertIn("source:raiderio-strength:v1", normalized)
        self.assertIn("source:warcraftlogs-public-rankings:v1", normalized)
        self.assertIn("chickenbro.source.raiderio_strength.v1", normalized)
        self.assertIn("chickenbro.source.warcraftlogs_public_rankings.v1", normalized)
        self.assertIn("chickenbro-tools-3", normalized)
        self.assertIn("active.registry_version = 'chickenbro-tools-2'", normalized)
        self.assertIn("0027_chickenbro_community_strength_sources", normalized)

    def test_generic_public_web_tool_appends_candidate_release_without_moving_shared_active_pointer(self):
        self.assertTrue(CHICKENBRO_GENERIC_PUBLIC_WEB.exists(), "missing generic public-web Registry migration")
        normalized = " ".join(CHICKENBRO_GENERIC_PUBLIC_WEB.read_text(encoding="utf-8").split())
        self.assertIn("source:public-web-research:v1", normalized)
        self.assertIn("chickenbro.source.public_web_research.v1", normalized)
        self.assertIn("chickenbro-tools-4", normalized)
        self.assertIn("0028_chickenbro_generic_public_web_research", normalized)
        self.assertNotIn("UPDATE ops.chickenbro_tool_registry_active", normalized)
        self.assertNotIn("INSERT INTO ops.chickenbro_tool_registry_active", normalized)

    def test_generic_public_web_repeat_budget_is_declared_in_a_new_candidate_release(self):
        self.assertTrue(CHICKENBRO_PUBLIC_WEB_REPEAT_BUDGET.exists(), "missing generic public-web repeat budget migration")
        normalized = " ".join(CHICKENBRO_PUBLIC_WEB_REPEAT_BUDGET.read_text(encoding="utf-8").split())
        self.assertIn("source:public-web-research:v2", normalized)
        self.assertIn("chickenbro.source.public_web_research.v2", normalized)
        self.assertIn("maxCallsPerTurn", normalized)
        self.assertIn("chickenbro-tools-5", normalized)
        self.assertIn("0029_chickenbro_public_web_repeat_budget", normalized)
        self.assertNotIn("UPDATE ops.chickenbro_tool_registry_active", normalized)
        self.assertNotIn("INSERT INTO ops.chickenbro_tool_registry_active", normalized)

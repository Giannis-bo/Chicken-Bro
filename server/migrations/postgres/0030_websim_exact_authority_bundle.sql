DO $preflight$
BEGIN
    IF pg_catalog.to_regprocedure('pg_catalog.sha256(bytea)') IS NULL THEN
        RAISE EXCEPTION 'PostgreSQL core pg_catalog.sha256(bytea) is required';
    END IF;
END;
$preflight$;

CREATE TABLE IF NOT EXISTS cache.websim_canonical_documents (
    content_key text PRIMARY KEY,
    document_kind text NOT NULL,
    schema_revision text NOT NULL,
    canonical_bytes bytea NOT NULL
        CHECK (pg_catalog.octet_length(canonical_bytes) BETWEEN 2 AND 1048576),
    canonical_json jsonb NOT NULL
        CHECK (pg_catalog.jsonb_typeof(canonical_json) = 'object'),
    canonical_sha256 text NOT NULL
        CHECK (canonical_sha256 ~ '^[0-9a-f]{64}$'),
    sealed_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    CHECK (
        canonical_sha256 = pg_catalog.encode(
            pg_catalog.sha256(canonical_bytes), 'hex'
        )
    ),
    CHECK (
        canonical_json = pg_catalog.convert_from(canonical_bytes, 'UTF8')::jsonb
    ),
    CHECK (
        (
            document_kind = 'exact_item'
            AND schema_revision = 'gear-exact-item-instance-v2'
            AND content_key = 'exact-item-instance:sha256:' || canonical_sha256
        )
        OR (
            document_kind = 'exact_static_facts'
            AND schema_revision = 'exact-static-facts-v1'
            AND content_key = 'exact-static-facts:sha256:' || canonical_sha256
        )
        OR (
            document_kind = 'exact_progression'
            AND schema_revision = 'exact-progression-binding-v1'
            AND content_key = 'exact-progression:sha256:' || canonical_sha256
        )
        OR (
            document_kind = 'effect_record'
            AND schema_revision = 'simc-item-effect-record-v1'
            AND content_key = 'simc-item-effect-record:sha256:' || canonical_sha256
        )
        OR (
            document_kind = 'effect_aggregate'
            AND schema_revision = 'simc-item-effect-support-v1'
            AND content_key = 'simc-item-effect-support:sha256:' || canonical_sha256
        )
        OR (
            document_kind = 'exact_authority'
            AND schema_revision = 'exact-authority-envelope-v1'
            AND content_key = 'exact-authority:sha256:' || canonical_sha256
        )
    )
);

CREATE TABLE IF NOT EXISTS cache.websim_effect_aggregate_records (
    effect_support_key text NOT NULL
        REFERENCES cache.websim_canonical_documents(content_key)
        ON DELETE RESTRICT,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 127),
    effect_record_key text NOT NULL
        REFERENCES cache.websim_canonical_documents(content_key)
        ON DELETE RESTRICT,
    sealed_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (effect_support_key, ordinal)
);

CREATE TABLE IF NOT EXISTS cache.websim_exact_authority_bundles (
    exact_authority_envelope_key text PRIMARY KEY
        REFERENCES cache.websim_canonical_documents(content_key)
        ON DELETE RESTRICT,
    exact_item_instance_key text NOT NULL
        REFERENCES cache.websim_canonical_documents(content_key)
        ON DELETE RESTRICT,
    static_facts_key text NOT NULL
        REFERENCES cache.websim_canonical_documents(content_key)
        ON DELETE RESTRICT,
    progression_binding_key text NOT NULL
        REFERENCES cache.websim_canonical_documents(content_key)
        ON DELETE RESTRICT,
    effect_support_key text NOT NULL
        REFERENCES cache.websim_canonical_documents(content_key)
        ON DELETE RESTRICT,
    gear_rule_revision text NOT NULL,
    simc_runtime_revision text NOT NULL,
    resolver_revision text NOT NULL,
    sealed_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp()
);

CREATE OR REPLACE FUNCTION cache.verify_websim_effect_aggregate_record_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $function$
DECLARE
    aggregate_kind text;
    aggregate_json jsonb;
    record_kind text;
BEGIN
    SELECT document_kind, canonical_json
    INTO aggregate_kind, aggregate_json
    FROM cache.websim_canonical_documents
    WHERE content_key = NEW.effect_support_key
    FOR KEY SHARE;

    SELECT document_kind
    INTO record_kind
    FROM cache.websim_canonical_documents
    WHERE content_key = NEW.effect_record_key
    FOR KEY SHARE;

    IF aggregate_kind IS DISTINCT FROM 'effect_aggregate'
       OR record_kind IS DISTINCT FROM 'effect_record'
       OR pg_catalog.jsonb_typeof(aggregate_json -> 'supportRecords')
          IS DISTINCT FROM 'array'
       OR NEW.ordinal >= pg_catalog.jsonb_array_length(
          aggregate_json -> 'supportRecords'
       )
       OR aggregate_json -> 'supportRecords' -> NEW.ordinal
          ->> 'supportRecordKey' IS DISTINCT FROM NEW.effect_record_key
    THEN
        RAISE EXCEPTION 'effect aggregate record binding mismatch';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION cache.verify_websim_exact_authority_bundle_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $function$
DECLARE
    envelope_kind text;
    envelope_json jsonb;
    exact_kind text;
    static_kind text;
    static_json jsonb;
    progression_kind text;
    progression_json jsonb;
    effect_kind text;
    effect_json jsonb;
    effect_relation_count bigint;
BEGIN
    SELECT document_kind, canonical_json
    INTO envelope_kind, envelope_json
    FROM cache.websim_canonical_documents
    WHERE content_key = NEW.exact_authority_envelope_key
    FOR KEY SHARE;

    SELECT document_kind
    INTO exact_kind
    FROM cache.websim_canonical_documents
    WHERE content_key = NEW.exact_item_instance_key
    FOR KEY SHARE;

    SELECT document_kind, canonical_json
    INTO static_kind, static_json
    FROM cache.websim_canonical_documents
    WHERE content_key = NEW.static_facts_key
    FOR KEY SHARE;

    SELECT document_kind, canonical_json
    INTO progression_kind, progression_json
    FROM cache.websim_canonical_documents
    WHERE content_key = NEW.progression_binding_key
    FOR KEY SHARE;

    SELECT document_kind, canonical_json
    INTO effect_kind, effect_json
    FROM cache.websim_canonical_documents
    WHERE content_key = NEW.effect_support_key
    FOR KEY SHARE;

    SELECT pg_catalog.count(*)
    INTO effect_relation_count
    FROM cache.websim_effect_aggregate_records
    WHERE effect_support_key = NEW.effect_support_key;

    IF envelope_kind IS DISTINCT FROM 'exact_authority'
       OR exact_kind IS DISTINCT FROM 'exact_item'
       OR static_kind IS DISTINCT FROM 'exact_static_facts'
       OR progression_kind IS DISTINCT FROM 'exact_progression'
       OR effect_kind IS DISTINCT FROM 'effect_aggregate'
       OR pg_catalog.jsonb_typeof(effect_json -> 'supportRecords')
          IS DISTINCT FROM 'array'
       OR effect_relation_count IS DISTINCT FROM pg_catalog.jsonb_array_length(
          effect_json -> 'supportRecords'
       )
       OR envelope_json ->> 'exactItemInstanceKey'
          IS DISTINCT FROM NEW.exact_item_instance_key
       OR envelope_json ->> 'staticFactsKey'
          IS DISTINCT FROM NEW.static_facts_key
       OR envelope_json ->> 'progressionBindingKey'
          IS DISTINCT FROM NEW.progression_binding_key
       OR envelope_json ->> 'effectSupportKey'
          IS DISTINCT FROM NEW.effect_support_key
       OR envelope_json ->> 'resolverRevision'
          IS DISTINCT FROM NEW.resolver_revision
       OR static_json ->> 'exactItemInstanceKey'
          IS DISTINCT FROM NEW.exact_item_instance_key
       OR progression_json ->> 'exactItemInstanceKey'
          IS DISTINCT FROM NEW.exact_item_instance_key
       OR progression_json ->> 'gearRuleRevision'
          IS DISTINCT FROM NEW.gear_rule_revision
       OR effect_json ->> 'exactItemInstanceKey'
          IS DISTINCT FROM NEW.exact_item_instance_key
       OR effect_json ->> 'simcRuntimeRevision'
          IS DISTINCT FROM NEW.simc_runtime_revision
    THEN
        RAISE EXCEPTION 'Exact Authority Bundle binding mismatch';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION cache.reject_websim_exact_authority_mutation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $function$
BEGIN
    RAISE EXCEPTION 'sealed Exact Authority rows are append-only';
END;
$function$;

DROP TRIGGER IF EXISTS trg_websim_effect_aggregate_record_binding
ON cache.websim_effect_aggregate_records;
CREATE TRIGGER trg_websim_effect_aggregate_record_binding
BEFORE INSERT ON cache.websim_effect_aggregate_records
FOR EACH ROW
EXECUTE FUNCTION cache.verify_websim_effect_aggregate_record_insert();

DROP TRIGGER IF EXISTS trg_websim_exact_authority_bundle_binding
ON cache.websim_exact_authority_bundles;
CREATE TRIGGER trg_websim_exact_authority_bundle_binding
BEFORE INSERT ON cache.websim_exact_authority_bundles
FOR EACH ROW
EXECUTE FUNCTION cache.verify_websim_exact_authority_bundle_insert();

DROP TRIGGER IF EXISTS trg_websim_canonical_documents_immutable
ON cache.websim_canonical_documents;
CREATE TRIGGER trg_websim_canonical_documents_immutable
BEFORE UPDATE OR DELETE ON cache.websim_canonical_documents
FOR EACH ROW
EXECUTE FUNCTION cache.reject_websim_exact_authority_mutation();

DROP TRIGGER IF EXISTS trg_websim_effect_aggregate_records_immutable
ON cache.websim_effect_aggregate_records;
CREATE TRIGGER trg_websim_effect_aggregate_records_immutable
BEFORE UPDATE OR DELETE ON cache.websim_effect_aggregate_records
FOR EACH ROW
EXECUTE FUNCTION cache.reject_websim_exact_authority_mutation();

DROP TRIGGER IF EXISTS trg_websim_exact_authority_bundles_immutable
ON cache.websim_exact_authority_bundles;
CREATE TRIGGER trg_websim_exact_authority_bundles_immutable
BEFORE UPDATE OR DELETE ON cache.websim_exact_authority_bundles
FOR EACH ROW
EXECUTE FUNCTION cache.reject_websim_exact_authority_mutation();

DROP TRIGGER IF EXISTS trg_websim_canonical_documents_truncate
ON cache.websim_canonical_documents;
CREATE TRIGGER trg_websim_canonical_documents_truncate
BEFORE TRUNCATE ON cache.websim_canonical_documents
FOR EACH STATEMENT
EXECUTE FUNCTION cache.reject_websim_exact_authority_mutation();

DROP TRIGGER IF EXISTS trg_websim_effect_aggregate_records_truncate
ON cache.websim_effect_aggregate_records;
CREATE TRIGGER trg_websim_effect_aggregate_records_truncate
BEFORE TRUNCATE ON cache.websim_effect_aggregate_records
FOR EACH STATEMENT
EXECUTE FUNCTION cache.reject_websim_exact_authority_mutation();

DROP TRIGGER IF EXISTS trg_websim_exact_authority_bundles_truncate
ON cache.websim_exact_authority_bundles;
CREATE TRIGGER trg_websim_exact_authority_bundles_truncate
BEFORE TRUNCATE ON cache.websim_exact_authority_bundles
FOR EACH STATEMENT
EXECUTE FUNCTION cache.reject_websim_exact_authority_mutation();

REVOKE ALL ON
    cache.websim_canonical_documents,
    cache.websim_effect_aggregate_records,
    cache.websim_exact_authority_bundles
FROM PUBLIC;

REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON
    cache.websim_canonical_documents,
    cache.websim_effect_aggregate_records,
    cache.websim_exact_authority_bundles
FROM wow_app;

GRANT SELECT ON
    cache.websim_canonical_documents,
    cache.websim_effect_aggregate_records,
    cache.websim_exact_authority_bundles
TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0030_websim_exact_authority_bundle',
    'Add exact-bytes append-only Canonical Authority Bundle persistence with no runtime writer'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = pg_catalog.clock_timestamp();

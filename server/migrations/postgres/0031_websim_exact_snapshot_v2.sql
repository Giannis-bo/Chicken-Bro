DO $preflight$
BEGIN
    IF pg_catalog.to_regprocedure('pg_catalog.sha256(bytea)') IS NULL THEN
        RAISE EXCEPTION 'PostgreSQL core pg_catalog.sha256(bytea) is required';
    END IF;
END;
$preflight$;

CREATE TABLE IF NOT EXISTS cache.websim_loadout_effect_authorities (
    loadout_effect_authority_key text PRIMARY KEY
        CHECK (loadout_effect_authority_key ~ '^loadout-effect-authority:sha256:[0-9a-f]{64}$'),
    schema_revision text NOT NULL CHECK (schema_revision = 'loadout-effect-authority-v1'),
    canonical_bytes bytea NOT NULL CHECK (pg_catalog.octet_length(canonical_bytes) BETWEEN 2 AND 1048576),
    canonical_json jsonb NOT NULL CHECK (pg_catalog.jsonb_typeof(canonical_json) = 'object'),
    canonical_sha256 text NOT NULL CHECK (canonical_sha256 ~ '^[0-9a-f]{64}$'),
    sealed_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    CHECK (canonical_sha256 = pg_catalog.encode(pg_catalog.sha256(canonical_bytes), 'hex')),
    CHECK (canonical_json = pg_catalog.convert_from(canonical_bytes, 'UTF8')::jsonb),
    CHECK (canonical_json ? 'schemaRevision' AND canonical_json->>'schemaRevision' = schema_revision),
    CHECK (loadout_effect_authority_key = 'loadout-effect-authority:sha256:' || canonical_sha256)
);

CREATE TABLE IF NOT EXISTS cache.websim_loadout_effect_authority_records (
    loadout_effect_authority_key text NOT NULL
        REFERENCES cache.websim_loadout_effect_authorities(loadout_effect_authority_key)
        DEFERRABLE INITIALLY DEFERRED ON DELETE RESTRICT,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 127),
    effect_record_key text NOT NULL
        REFERENCES cache.websim_canonical_documents(content_key) ON DELETE RESTRICT,
    sealed_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (loadout_effect_authority_key, ordinal)
);

CREATE OR REPLACE FUNCTION cache.verify_websim_loadout_effect_authority_relations()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $body$
DECLARE
    parent_key text := NEW.loadout_effect_authority_key;
    authority_json jsonb;
    expected_count integer;
    actual_count integer;
BEGIN
    SELECT canonical_json
    INTO authority_json
    FROM cache.websim_loadout_effect_authorities
    WHERE loadout_effect_authority_key = parent_key
    FOR KEY SHARE;
    IF authority_json IS NULL THEN
        RETURN NULL;
    END IF;
    IF pg_catalog.jsonb_typeof(authority_json -> 'supportRecords')
       IS DISTINCT FROM 'array'
    THEN
        RAISE EXCEPTION 'loadout effect authority supportRecords must be an array';
    END IF;
    expected_count := pg_catalog.jsonb_array_length(
        authority_json -> 'supportRecords'
    );
    SELECT pg_catalog.count(*)
    INTO actual_count
    FROM cache.websim_loadout_effect_authority_records
    WHERE loadout_effect_authority_key = parent_key;
    IF expected_count < 1
       OR expected_count > 128
       OR actual_count <> expected_count
       OR EXISTS (
            SELECT 1
            FROM pg_catalog.generate_series(0, expected_count - 1)
                AS wanted(ordinal)
            LEFT JOIN cache.websim_loadout_effect_authority_records relation
                ON relation.loadout_effect_authority_key = parent_key
                AND relation.ordinal = wanted.ordinal
            WHERE relation.ordinal IS NULL
               OR relation.effect_record_key <> authority_json->'supportRecords'->wanted.ordinal->>'supportRecordKey'
       )
       OR EXISTS (
            SELECT 1
            FROM cache.websim_loadout_effect_authority_records relation
            JOIN cache.websim_canonical_documents document
                ON document.content_key = relation.effect_record_key
            WHERE relation.loadout_effect_authority_key = parent_key
              AND document.document_kind <> 'effect_record'
       )
    THEN
        RAISE EXCEPTION
            'loadout effect authority relations must exactly match canonical supportRecords';
    END IF;
    RETURN NULL;
END;
$body$;

CREATE CONSTRAINT TRIGGER trg_websim_loadout_effect_authorities_complete
AFTER INSERT ON cache.websim_loadout_effect_authorities
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION cache.verify_websim_loadout_effect_authority_relations();

CREATE CONSTRAINT TRIGGER trg_websim_loadout_effect_authority_records_complete
AFTER INSERT ON cache.websim_loadout_effect_authority_records
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION cache.verify_websim_loadout_effect_authority_relations();

ALTER TABLE cache.websim_gear_resolved_loadouts
    DROP CONSTRAINT IF EXISTS websim_gear_resolved_loadouts_resolved_loadout_key_check,
    DROP CONSTRAINT IF EXISTS websim_gear_resolved_loadouts_catalog_revision_fkey,
    ADD CONSTRAINT websim_gear_resolved_loadouts_resolved_loadout_key_check
        CHECK (resolved_loadout_key ~ '^resolved-loadout(-v2)?:sha256:[0-9a-f]{64}$'),
    ALTER COLUMN catalog_revision DROP NOT NULL,
    ALTER COLUMN exact_registry_revision DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS exact_authority_by_slot_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS effect_evidence_by_occurrence_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS loadout_effect_authority_key text
        REFERENCES cache.websim_loadout_effect_authorities(loadout_effect_authority_key)
        ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS resolver_replay_context_json jsonb;

ALTER TABLE cache.websim_simulation_snapshots
    DROP CONSTRAINT IF EXISTS websim_simulation_snapshots_simulation_snapshot_key_check,
    DROP CONSTRAINT IF EXISTS websim_simulation_snapshots_catalog_revision_fkey,
    ADD CONSTRAINT websim_simulation_snapshots_simulation_snapshot_key_check
        CHECK (simulation_snapshot_key ~ '^simulation-snapshot(-v2)?:sha256:[0-9a-f]{64}$'),
    ALTER COLUMN catalog_revision DROP NOT NULL,
    ALTER COLUMN gear_rule_revision DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS exact_authority_by_slot_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS effect_evidence_by_occurrence_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS loadout_effect_authority_key text
        REFERENCES cache.websim_loadout_effect_authorities(loadout_effect_authority_key)
        ON DELETE RESTRICT;

ALTER TABLE cache.websim_gear_resolved_loadouts
    DROP CONSTRAINT IF EXISTS websim_gear_resolved_loadouts_v1_v2_fields_check,
    ADD CONSTRAINT websim_gear_resolved_loadouts_v1_v2_fields_check CHECK (
        (
            schema_revision = 'resolved-loadout-v2'
            AND resolved_loadout_key ~ '^resolved-loadout-v2:sha256:[0-9a-f]{64}$'
            AND loadout_json ->> 'schemaRevision'
                IS NOT DISTINCT FROM schema_revision
            AND loadout_json ->> 'resolvedLoadoutKey'
                IS NOT DISTINCT FROM resolved_loadout_key
            AND catalog_revision IS NOT DISTINCT FROM (loadout_json ->> 'originCatalogRevision')
            AND gear_rule_revision IS NOT DISTINCT FROM (
                loadout_json ->> 'gearRuleRevision'
            )
            AND exact_registry_revision IS NULL
            AND class_key IS NOT DISTINCT FROM (
                loadout_json -> 'eligibilityContext' ->> 'classKey'
            )
            AND spec_key IS NOT DISTINCT FROM (
                loadout_json -> 'eligibilityContext' ->> 'specKey'
            )
            AND loadout_json ->> 'rowHash' IS NOT DISTINCT FROM row_hash
            AND pg_catalog.jsonb_typeof(exact_authority_by_slot_json)
                IS NOT DISTINCT FROM 'array'
            AND pg_catalog.jsonb_typeof(effect_evidence_by_occurrence_json)
                IS NOT DISTINCT FROM 'array'
            AND loadout_json -> 'exactAuthorityBySlot'
                IS NOT DISTINCT FROM exact_authority_by_slot_json
            AND loadout_json -> 'effectEvidenceByOccurrence'
                IS NOT DISTINCT FROM effect_evidence_by_occurrence_json
            AND loadout_effect_authority_key IS NOT DISTINCT FROM (
                loadout_json ->> 'loadoutEffectAuthorityKey'
            )
            AND resolver_replay_context_json IS NOT NULL
            AND pg_catalog.jsonb_typeof(resolver_replay_context_json)
                IS NOT DISTINCT FROM 'object'
            AND pg_catalog.octet_length(resolver_replay_context_json::text) <= 1048576
        )
        OR (
            schema_revision <> 'resolved-loadout-v2'
            AND resolved_loadout_key ~ '^resolved-loadout:sha256:[0-9a-f]{64}$'
            AND resolver_replay_context_json IS NULL
            AND exact_authority_by_slot_json = '[]'::jsonb
            AND effect_evidence_by_occurrence_json = '[]'::jsonb
            AND loadout_effect_authority_key IS NULL
        )
    );

ALTER TABLE cache.websim_simulation_snapshots
    DROP CONSTRAINT IF EXISTS websim_simulation_snapshots_v1_v2_fields_check,
    ADD CONSTRAINT websim_simulation_snapshots_v1_v2_fields_check CHECK (
        (
            schema_revision = 'simulation-snapshot-v2'
            AND simulation_snapshot_key ~ '^simulation-snapshot-v2:sha256:[0-9a-f]{64}$'
            AND resolved_loadout_key ~ '^resolved-loadout-v2:sha256:[0-9a-f]{64}$'
            AND snapshot_json ->> 'schemaRevision'
                IS NOT DISTINCT FROM schema_revision
            AND snapshot_json ->> 'simulationSnapshotKey'
                IS NOT DISTINCT FROM simulation_snapshot_key
            AND snapshot_json ->> 'resolvedLoadoutKey'
                IS NOT DISTINCT FROM resolved_loadout_key
            AND snapshot_json ->> 'talentProfileKey'
                IS NOT DISTINCT FROM talent_profile_key
            AND snapshot_json ->> 'compilerRevision'
                IS NOT DISTINCT FROM compiler_revision
            AND snapshot_json ->> 'simcRuntimeRevision'
                IS NOT DISTINCT FROM simc_runtime_revision
            AND snapshot_json ->> 'canonicalInputHash'
                IS NOT DISTINCT FROM canonical_input_hash
            AND catalog_revision IS NOT DISTINCT FROM (snapshot_json ->> 'originCatalogRevision')
            AND gear_rule_revision IS NULL
            AND pg_catalog.jsonb_typeof(exact_authority_by_slot_json)
                IS NOT DISTINCT FROM 'array'
            AND pg_catalog.jsonb_typeof(effect_evidence_by_occurrence_json)
                IS NOT DISTINCT FROM 'array'
            AND snapshot_json -> 'exactAuthorityBySlot'
                IS NOT DISTINCT FROM exact_authority_by_slot_json
            AND snapshot_json -> 'effectEvidenceByOccurrence'
                IS NOT DISTINCT FROM effect_evidence_by_occurrence_json
            AND loadout_effect_authority_key IS NOT DISTINCT FROM (
                snapshot_json ->> 'loadoutEffectAuthorityKey'
            )
            AND snapshot_json ->> 'rowHash' IS NOT DISTINCT FROM row_hash
        )
        OR (
            schema_revision <> 'simulation-snapshot-v2'
            AND simulation_snapshot_key ~ '^simulation-snapshot:sha256:[0-9a-f]{64}$'
            AND exact_authority_by_slot_json = '[]'::jsonb
            AND effect_evidence_by_occurrence_json = '[]'::jsonb
            AND loadout_effect_authority_key IS NULL
        )
    );

CREATE OR REPLACE FUNCTION cache.verify_websim_v2_effect_evidence(
    p_schema_revision text,
    p_effect_evidence jsonb,
    p_loadout_effect_authority_key text
)
RETURNS void
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $body$
DECLARE
    occurrence jsonb;
    expected_ordinal integer := 0;
    relation_key text;
    expected_key text;
    relation_count integer;
    loadout_count integer := 0;
    saw_loadout boolean := false;
BEGIN
    IF pg_catalog.jsonb_typeof(p_effect_evidence) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'v2 effect evidence must be an array';
    END IF;
    IF p_loadout_effect_authority_key IS NULL THEN
        IF pg_catalog.jsonb_path_exists(
            p_effect_evidence,
            '$[*] ? (@.scope == "loadout")'
        ) THEN
            RAISE EXCEPTION 'v2 no-effect rows cannot contain loadout occurrences';
        END IF;
        RETURN;
    END IF;
    FOR occurrence IN
        SELECT value
        FROM pg_catalog.jsonb_array_elements(p_effect_evidence)
    LOOP
        IF occurrence ->> 'scope' = 'loadout' THEN
            saw_loadout := true;
            IF pg_catalog.jsonb_typeof(occurrence -> 'recordOrdinal') <> 'number'
               OR occurrence ->> 'recordOrdinal' !~ '^[0-9]+$'
               OR (occurrence ->> 'recordOrdinal')::integer <> expected_ordinal
               OR occurrence ->> 'loadoutEffectAuthorityKey'
                  <> p_loadout_effect_authority_key
            THEN
                RAISE EXCEPTION 'v2 loadout effect occurrence is invalid';
            END IF;
            SELECT relation.effect_record_key,
                   authority.canonical_json -> 'supportRecords'
                       -> expected_ordinal ->> 'supportRecordKey'
            INTO relation_key, expected_key
            FROM cache.websim_loadout_effect_authorities authority
            JOIN cache.websim_loadout_effect_authority_records relation
                ON relation.loadout_effect_authority_key
                   = authority.loadout_effect_authority_key
               AND relation.ordinal = expected_ordinal
            WHERE authority.loadout_effect_authority_key
                  = p_loadout_effect_authority_key
            FOR KEY SHARE;
            IF relation_key IS NULL
               OR relation_key <> expected_key
               OR occurrence ->> 'supportRecordKey' <> relation_key
            THEN
                RAISE EXCEPTION 'v2 loadout effect relation mismatch';
            END IF;
            expected_ordinal := expected_ordinal + 1;
            loadout_count := loadout_count + 1;
        ELSIF saw_loadout THEN
            RAISE EXCEPTION 'v2 loadout effect occurrences must be a suffix';
        END IF;
    END LOOP;
    SELECT pg_catalog.count(*)
    INTO relation_count
    FROM cache.websim_loadout_effect_authority_records
    WHERE loadout_effect_authority_key = p_loadout_effect_authority_key;
    IF NOT saw_loadout OR loadout_count <> relation_count THEN
        RAISE EXCEPTION 'v2 loadout effect occurrence count mismatch';
    END IF;
END;
$body$;

CREATE OR REPLACE FUNCTION cache.verify_websim_resolved_loadout_v2_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $body$
BEGIN
    IF NEW.schema_revision = 'resolved-loadout-v2' THEN
        PERFORM cache.verify_websim_v2_effect_evidence(
            NEW.schema_revision,
            NEW.effect_evidence_by_occurrence_json,
            NEW.loadout_effect_authority_key
        );
    END IF;
    RETURN NEW;
END;
$body$;

CREATE OR REPLACE FUNCTION cache.verify_websim_simulation_snapshot_v2_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $body$
DECLARE
    loadout_effect_evidence jsonb;
    loadout_authority_key text;
BEGIN
    IF NEW.schema_revision = 'simulation-snapshot-v2' THEN
        SELECT effect_evidence_by_occurrence_json,
               loadout_effect_authority_key
        INTO loadout_effect_evidence, loadout_authority_key
        FROM cache.websim_gear_resolved_loadouts
        WHERE resolved_loadout_key = NEW.resolved_loadout_key
        FOR KEY SHARE;
        IF loadout_effect_evidence IS NULL
           OR loadout_effect_evidence IS DISTINCT FROM NEW.effect_evidence_by_occurrence_json
           OR loadout_authority_key IS DISTINCT FROM NEW.loadout_effect_authority_key
        THEN
            RAISE EXCEPTION 'v2 snapshot must bind its persisted ResolvedLoadout effect relation';
        END IF;
        PERFORM cache.verify_websim_v2_effect_evidence(
            NEW.schema_revision,
            NEW.effect_evidence_by_occurrence_json,
            NEW.loadout_effect_authority_key
        );
    END IF;
    RETURN NEW;
END;
$body$;

CREATE TRIGGER trg_websim_resolved_loadout_v2_binding
BEFORE INSERT ON cache.websim_gear_resolved_loadouts
FOR EACH ROW EXECUTE FUNCTION cache.verify_websim_resolved_loadout_v2_insert();

CREATE TRIGGER trg_websim_simulation_snapshot_v2_binding
BEFORE INSERT ON cache.websim_simulation_snapshots
FOR EACH ROW EXECUTE FUNCTION cache.verify_websim_simulation_snapshot_v2_insert();

CREATE TRIGGER trg_websim_loadout_effect_authorities_immutable
BEFORE UPDATE OR DELETE ON cache.websim_loadout_effect_authorities
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_exact_authority_mutation();

CREATE TRIGGER trg_websim_loadout_effect_authorities_truncate
BEFORE TRUNCATE ON cache.websim_loadout_effect_authorities
FOR EACH STATEMENT EXECUTE FUNCTION cache.reject_websim_exact_authority_mutation();

CREATE TRIGGER trg_websim_loadout_effect_authority_records_immutable
BEFORE UPDATE OR DELETE ON cache.websim_loadout_effect_authority_records
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_exact_authority_mutation();

CREATE TRIGGER trg_websim_loadout_effect_authority_records_truncate
BEFORE TRUNCATE ON cache.websim_loadout_effect_authority_records
FOR EACH STATEMENT EXECUTE FUNCTION cache.reject_websim_exact_authority_mutation();

REVOKE ALL ON
    cache.websim_loadout_effect_authorities,
    cache.websim_loadout_effect_authority_records
FROM PUBLIC;

REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON
    cache.websim_loadout_effect_authorities,
    cache.websim_loadout_effect_authority_records
FROM wow_app;

GRANT SELECT ON
    cache.websim_loadout_effect_authorities,
    cache.websim_loadout_effect_authority_records
TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0031_websim_exact_snapshot_v2',
    'Add conditional v1/v2 snapshot persistence and append-only loadout effect authority relations'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = pg_catalog.clock_timestamp();

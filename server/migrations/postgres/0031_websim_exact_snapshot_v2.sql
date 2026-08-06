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
        ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 127),
    effect_record_key text NOT NULL
        REFERENCES cache.websim_canonical_documents(content_key)
        ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
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
               OR relation.effect_record_key IS DISTINCT FROM
                  authority_json->'supportRecords'->wanted.ordinal->>'supportRecordKey'
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
    ADD COLUMN IF NOT EXISTS resolver_replay_context_json jsonb,
    ADD COLUMN IF NOT EXISTS v1_catalog_revision_ref text
        GENERATED ALWAYS AS (
            CASE
                WHEN schema_revision = 'resolved-loadout-v1'
                THEN catalog_revision
                ELSE NULL
            END
        ) STORED,
    ADD CONSTRAINT websim_gear_resolved_loadouts_v1_catalog_revision_fkey
        FOREIGN KEY (v1_catalog_revision_ref)
        REFERENCES cache.websim_gear_catalog_revisions(catalog_revision)
        ON DELETE RESTRICT;

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
        ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS v1_catalog_revision_ref text
        GENERATED ALWAYS AS (
            CASE
                WHEN schema_revision = 'simulation-snapshot-v1'
                THEN catalog_revision
                ELSE NULL
            END
        ) STORED,
    ADD CONSTRAINT websim_simulation_snapshots_v1_catalog_revision_fkey
        FOREIGN KEY (v1_catalog_revision_ref)
        REFERENCES cache.websim_gear_catalog_revisions(catalog_revision)
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
            schema_revision = 'resolved-loadout-v1'
            AND resolved_loadout_key ~ '^resolved-loadout:sha256:[0-9a-f]{64}$'
            AND catalog_revision IS NOT NULL
            AND gear_rule_revision IS NOT NULL
            AND exact_registry_revision IS NOT NULL
            AND loadout_json ->> 'schemaRevision'
                IS NOT DISTINCT FROM schema_revision
            AND loadout_json ->> 'resolvedLoadoutKey'
                IS NOT DISTINCT FROM resolved_loadout_key
            AND catalog_revision IS NOT DISTINCT FROM (
                loadout_json ->> 'catalogRevision'
            )
            AND gear_rule_revision IS NOT DISTINCT FROM (
                loadout_json ->> 'gearRuleRevision'
            )
            AND exact_registry_revision IS NOT DISTINCT FROM (
                loadout_json ->> 'exactRegistryRevision'
            )
            AND class_key IS NOT DISTINCT FROM (
                loadout_json -> 'eligibilityContext' ->> 'classKey'
            )
            AND spec_key IS NOT DISTINCT FROM (
                loadout_json -> 'eligibilityContext' ->> 'specKey'
            )
            AND loadout_json ->> 'rowHash' IS NOT DISTINCT FROM row_hash
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
            schema_revision = 'simulation-snapshot-v1'
            AND simulation_snapshot_key ~ '^simulation-snapshot:sha256:[0-9a-f]{64}$'
            AND resolved_loadout_key ~ '^resolved-loadout:sha256:[0-9a-f]{64}$'
            AND catalog_revision IS NOT NULL
            AND gear_rule_revision IS NOT NULL
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
            AND catalog_revision IS NOT DISTINCT FROM (
                snapshot_json ->> 'catalogRevision'
            )
            AND gear_rule_revision IS NOT DISTINCT FROM (
                snapshot_json ->> 'gearRuleRevision'
            )
            AND snapshot_json ->> 'rowHash' IS NOT DISTINCT FROM row_hash
            AND exact_authority_by_slot_json = '[]'::jsonb
            AND effect_evidence_by_occurrence_json = '[]'::jsonb
            AND loadout_effect_authority_key IS NULL
        )
    );

CREATE OR REPLACE FUNCTION cache.verify_websim_resolver_replay_context(
    p_context jsonb
)
RETURNS void
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $body$
DECLARE
    forbidden_keys CONSTANT text[] := ARRAY[
        'Catalog',
        'catalogRevision',
        'rawProfile',
        'rawString',
        'player',
        'playerName',
        'characterName',
        'realm',
        'server',
        'source',
        'sourceRefIds',
        'sourcePayload'
    ];
    resolved_slot record;
    set_count record;
    active_effect jsonb;
    subject jsonb;
    required_count integer;
    subject_count integer;
BEGIN
    IF pg_catalog.jsonb_typeof(p_context) IS DISTINCT FROM 'object'
       OR pg_catalog.octet_length(p_context::text) > 1048576
       OR NOT (p_context ?& ARRAY[
            'schemaRevision',
            'status',
            'dependencyVector',
            'resolvedGearSignature',
            'eligibilityContext',
            'profileReadiness',
            'resolvedSlots',
            'setState',
            'loadoutEffectSubjects',
            'v2EffectBoundary'
       ])
       OR (p_context - ARRAY[
            'schemaRevision',
            'status',
            'dependencyVector',
            'resolvedGearSignature',
            'eligibilityContext',
            'profileReadiness',
            'resolvedSlots',
            'setState',
            'loadoutEffectSubjects',
            'v2EffectBoundary'
       ]) <> '{}'::jsonb
       OR p_context ->> 'schemaRevision'
          IS DISTINCT FROM 'exact-resolver-replay-context-v1'
       OR p_context ->> 'status' IS DISTINCT FROM 'verified'
       OR pg_catalog.jsonb_typeof(p_context -> 'resolvedGearSignature')
          IS DISTINCT FROM 'string'
       OR (p_context ->> 'resolvedGearSignature')
          !~ '^sha256:[0-9a-f]{64}$'
    THEN
        RAISE EXCEPTION 'v2 resolver replay context is invalid';
    END IF;

    IF pg_catalog.jsonb_typeof(p_context -> 'dependencyVector')
          IS DISTINCT FROM 'object'
       OR NOT ((p_context -> 'dependencyVector') ?& ARRAY[
            'gearRuleRevision',
            'resolverContractRevision',
            'simcRuntimeRevision'
       ])
       OR ((p_context -> 'dependencyVector') - ARRAY[
            'gearRuleRevision',
            'resolverContractRevision',
            'simcRuntimeRevision'
       ]) <> '{}'::jsonb
       OR EXISTS (
            SELECT 1
            FROM pg_catalog.jsonb_each(
                p_context -> 'dependencyVector'
            ) AS dependency(field, value)
            WHERE pg_catalog.jsonb_typeof(dependency.value)
                  IS DISTINCT FROM 'string'
               OR dependency.value #>> '{}' = ''
       )
    THEN
        RAISE EXCEPTION 'v2 resolver replay context is invalid';
    END IF;

    IF pg_catalog.jsonb_typeof(p_context -> 'eligibilityContext')
          IS DISTINCT FROM 'object'
       OR NOT ((p_context -> 'eligibilityContext') ?& ARRAY[
            'classKey',
            'specKey',
            'level'
       ])
       OR ((p_context -> 'eligibilityContext') - ARRAY[
            'classKey',
            'specKey',
            'level'
       ]) <> '{}'::jsonb
       OR pg_catalog.jsonb_typeof(
            p_context -> 'eligibilityContext' -> 'classKey'
       ) IS DISTINCT FROM 'string'
       OR pg_catalog.jsonb_typeof(
            p_context -> 'eligibilityContext' -> 'specKey'
       ) IS DISTINCT FROM 'string'
       OR (p_context -> 'eligibilityContext' ->> 'classKey') = ''
       OR (p_context -> 'eligibilityContext' ->> 'specKey') = ''
       OR pg_catalog.jsonb_typeof(
            p_context -> 'eligibilityContext' -> 'level'
       ) IS DISTINCT FROM 'number'
       OR (p_context -> 'eligibilityContext' ->> 'level')
          !~ '^[1-9][0-9]*$'
    THEN
        RAISE EXCEPTION 'v2 resolver replay context is invalid';
    END IF;

    IF pg_catalog.jsonb_typeof(p_context -> 'profileReadiness')
          IS DISTINCT FROM 'object'
       OR NOT ((p_context -> 'profileReadiness') ?& ARRAY[
            'status',
            'simcReady',
            'requiredSlots',
            'readySlots',
            'simcRuntimeRevision'
       ])
       OR ((p_context -> 'profileReadiness') - ARRAY[
            'status',
            'simcReady',
            'requiredSlots',
            'readySlots',
            'simcRuntimeRevision'
       ]) <> '{}'::jsonb
       OR p_context -> 'profileReadiness' ->> 'status'
          IS DISTINCT FROM 'verified'
       OR p_context -> 'profileReadiness' -> 'simcReady'
          IS DISTINCT FROM 'true'::jsonb
       OR pg_catalog.jsonb_typeof(
            p_context -> 'profileReadiness' -> 'requiredSlots'
       ) IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_typeof(
            p_context -> 'profileReadiness' -> 'readySlots'
       ) IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_typeof(
            p_context -> 'profileReadiness' -> 'simcRuntimeRevision'
       ) IS DISTINCT FROM 'string'
       OR p_context -> 'profileReadiness' ->> 'simcRuntimeRevision' = ''
    THEN
        RAISE EXCEPTION 'v2 resolver replay context is invalid';
    END IF;
    required_count := pg_catalog.jsonb_array_length(
        p_context -> 'profileReadiness' -> 'requiredSlots'
    );
    IF required_count < 1
       OR required_count > 32
       OR p_context -> 'profileReadiness' -> 'requiredSlots'
          IS DISTINCT FROM p_context -> 'profileReadiness' -> 'readySlots'
       OR EXISTS (
            SELECT 1
            FROM pg_catalog.jsonb_array_elements(
                p_context -> 'profileReadiness' -> 'requiredSlots'
            ) AS required_slot(value)
            WHERE pg_catalog.jsonb_typeof(required_slot.value)
                  IS DISTINCT FROM 'string'
               OR required_slot.value #>> '{}' = ''
       )
       OR (
            SELECT pg_catalog.count(DISTINCT required_slot.value)
            FROM pg_catalog.jsonb_array_elements(
                p_context -> 'profileReadiness' -> 'requiredSlots'
            ) AS required_slot(value)
       ) <> required_count
    THEN
        RAISE EXCEPTION 'v2 resolver replay context is invalid';
    END IF;

    IF pg_catalog.jsonb_typeof(p_context -> 'resolvedSlots')
          IS DISTINCT FROM 'object'
       OR (
            SELECT pg_catalog.count(*)
            FROM pg_catalog.jsonb_object_keys(
                p_context -> 'resolvedSlots'
            ) AS resolved_slot_key
       ) <> required_count
    THEN
        RAISE EXCEPTION 'v2 resolver replay context is invalid';
    END IF;
    FOR resolved_slot IN
        SELECT key, value
        FROM pg_catalog.jsonb_each(p_context -> 'resolvedSlots')
    LOOP
        IF NOT (
                p_context -> 'profileReadiness' -> 'requiredSlots'
            ) ? resolved_slot.key
           OR pg_catalog.jsonb_typeof(resolved_slot.value)
              IS DISTINCT FROM 'object'
           OR NOT (resolved_slot.value ?& ARRAY[
                'slot',
                'itemId',
                'legality'
           ])
           OR (resolved_slot.value - ARRAY[
                'slot',
                'itemId',
                'legality'
           ]) <> '{}'::jsonb
           OR pg_catalog.jsonb_typeof(resolved_slot.value -> 'slot')
              IS DISTINCT FROM 'string'
           OR resolved_slot.value ->> 'slot'
              IS DISTINCT FROM resolved_slot.key
           OR pg_catalog.jsonb_typeof(resolved_slot.value -> 'itemId')
              IS DISTINCT FROM 'string'
           OR resolved_slot.value ->> 'itemId' = ''
           OR pg_catalog.jsonb_typeof(resolved_slot.value -> 'legality')
              IS DISTINCT FROM 'object'
           OR NOT ((resolved_slot.value -> 'legality') ? 'status')
           OR ((resolved_slot.value -> 'legality') - ARRAY['status'])
              <> '{}'::jsonb
           OR resolved_slot.value -> 'legality' ->> 'status'
              IS DISTINCT FROM 'verified'
        THEN
            RAISE EXCEPTION 'v2 resolver replay context is invalid';
        END IF;
    END LOOP;

    IF pg_catalog.jsonb_typeof(p_context -> 'setState')
          IS DISTINCT FROM 'object'
       OR NOT ((p_context -> 'setState') ?& ARRAY[
            'itemSetCounts',
            'activeDynamicEffects'
       ])
       OR ((p_context -> 'setState') - ARRAY[
            'itemSetCounts',
            'activeDynamicEffects'
       ]) <> '{}'::jsonb
       OR pg_catalog.jsonb_typeof(
            p_context -> 'setState' -> 'itemSetCounts'
       ) IS DISTINCT FROM 'object'
       OR pg_catalog.jsonb_typeof(
            p_context -> 'setState' -> 'activeDynamicEffects'
       ) IS DISTINCT FROM 'array'
       OR (
            SELECT pg_catalog.count(*)
            FROM pg_catalog.jsonb_object_keys(
                p_context -> 'setState' -> 'itemSetCounts'
            ) AS item_set_key
       ) > 128
       OR pg_catalog.jsonb_array_length(
            p_context -> 'setState' -> 'activeDynamicEffects'
       ) > 128
    THEN
        RAISE EXCEPTION 'v2 resolver replay context is invalid';
    END IF;
    FOR set_count IN
        SELECT key, value
        FROM pg_catalog.jsonb_each(
            p_context -> 'setState' -> 'itemSetCounts'
        )
    LOOP
        IF set_count.key = ANY(forbidden_keys)
           OR set_count.key = ''
           OR pg_catalog.length(set_count.key) > 128
           OR pg_catalog.jsonb_typeof(set_count.value)
              IS DISTINCT FROM 'number'
           OR set_count.value::text !~ '^[1-9][0-9]*$'
           OR set_count.value::text::numeric NOT BETWEEN 1 AND 16
        THEN
            RAISE EXCEPTION 'v2 resolver replay context is invalid';
        END IF;
    END LOOP;
    FOR active_effect IN
        SELECT value
        FROM pg_catalog.jsonb_array_elements(
            p_context -> 'setState' -> 'activeDynamicEffects'
        )
    LOOP
        IF pg_catalog.jsonb_typeof(active_effect) IS DISTINCT FROM 'object'
           OR NOT (active_effect ?& ARRAY['effectId', 'itemSetId', 'pieces'])
           OR (active_effect - ARRAY['effectId', 'itemSetId', 'pieces'])
              <> '{}'::jsonb
           OR pg_catalog.jsonb_typeof(active_effect -> 'effectId')
              IS DISTINCT FROM 'string'
           OR pg_catalog.jsonb_typeof(active_effect -> 'itemSetId')
              IS DISTINCT FROM 'string'
           OR active_effect ->> 'effectId' = ''
           OR active_effect ->> 'itemSetId' = ''
           OR pg_catalog.jsonb_typeof(active_effect -> 'pieces')
              IS DISTINCT FROM 'number'
           OR active_effect ->> 'pieces' !~ '^[1-9][0-9]*$'
           OR (active_effect ->> 'pieces')::numeric NOT BETWEEN 1 AND 16
        THEN
            RAISE EXCEPTION 'v2 resolver replay context is invalid';
        END IF;
    END LOOP;

    IF pg_catalog.jsonb_typeof(p_context -> 'loadoutEffectSubjects')
          IS DISTINCT FROM 'array'
    THEN
        RAISE EXCEPTION 'v2 resolver replay context is invalid';
    END IF;
    subject_count := pg_catalog.jsonb_array_length(
        p_context -> 'loadoutEffectSubjects'
    );
    IF subject_count > 128
       OR subject_count IS DISTINCT FROM pg_catalog.jsonb_array_length(
            p_context -> 'setState' -> 'activeDynamicEffects'
       )
    THEN
        RAISE EXCEPTION 'v2 resolver replay context is invalid';
    END IF;
    FOR subject IN
        SELECT value
        FROM pg_catalog.jsonb_array_elements(
            p_context -> 'loadoutEffectSubjects'
        )
    LOOP
        IF pg_catalog.jsonb_typeof(subject) IS DISTINCT FROM 'object'
           OR NOT (subject ?& ARRAY[
                'subjectKind',
                'itemSetId',
                'pieces',
                'subjectKey'
           ])
           OR (subject - ARRAY[
                'subjectKind',
                'itemSetId',
                'pieces',
                'subjectKey'
           ]) <> '{}'::jsonb
           OR pg_catalog.jsonb_typeof(subject -> 'subjectKind')
              IS DISTINCT FROM 'string'
           OR pg_catalog.jsonb_typeof(subject -> 'itemSetId')
              IS DISTINCT FROM 'string'
           OR pg_catalog.jsonb_typeof(subject -> 'subjectKey')
              IS DISTINCT FROM 'string'
           OR subject ->> 'subjectKind' = ''
           OR subject ->> 'itemSetId' = ''
           OR subject ->> 'subjectKey' = ''
           OR pg_catalog.jsonb_typeof(subject -> 'pieces')
              IS DISTINCT FROM 'number'
           OR subject ->> 'pieces' !~ '^[1-9][0-9]*$'
           OR (subject ->> 'pieces')::numeric NOT BETWEEN 1 AND 16
        THEN
            RAISE EXCEPTION 'v2 resolver replay context is invalid';
        END IF;
    END LOOP;
    IF pg_catalog.jsonb_typeof(p_context -> 'v2EffectBoundary')
          IS DISTINCT FROM 'object'
       OR NOT ((p_context -> 'v2EffectBoundary') ?& ARRAY[
            'schemaRevision',
            'status',
            'resolvedGearSignature',
            'setState',
            'subjects',
            'gearRuleRevision',
            'resolverRevision',
            'simcRuntimeRevision'
       ])
       OR (
            subject_count = 0
            AND (
                (p_context -> 'v2EffectBoundary') - ARRAY[
                    'schemaRevision',
                    'status',
                    'resolvedGearSignature',
                    'setState',
                    'subjects',
                    'gearRuleRevision',
                    'resolverRevision',
                    'simcRuntimeRevision'
                ]
            ) <> '{}'::jsonb
       )
       OR (
            subject_count > 0
            AND (
                NOT ((p_context -> 'v2EffectBoundary')
                     ? 'loadoutEffectAuthorityKey')
                OR (
                    (p_context -> 'v2EffectBoundary') - ARRAY[
                        'schemaRevision',
                        'status',
                        'resolvedGearSignature',
                        'setState',
                        'subjects',
                        'gearRuleRevision',
                        'resolverRevision',
                        'simcRuntimeRevision',
                        'loadoutEffectAuthorityKey'
                    ]
                ) <> '{}'::jsonb
                OR pg_catalog.jsonb_typeof(
                    p_context -> 'v2EffectBoundary'
                        -> 'loadoutEffectAuthorityKey'
                ) IS DISTINCT FROM 'string'
                OR p_context -> 'v2EffectBoundary'
                       ->> 'loadoutEffectAuthorityKey'
                   !~ '^loadout-effect-authority:sha256:[0-9a-f]{64}$'
            )
       )
       OR p_context -> 'v2EffectBoundary' ->> 'schemaRevision'
          IS DISTINCT FROM 'gear-resolver-v2-effect-boundary-v1'
       OR p_context -> 'v2EffectBoundary' ->> 'status'
          IS DISTINCT FROM 'verified'
       OR p_context -> 'v2EffectBoundary' -> 'resolvedGearSignature'
          IS DISTINCT FROM p_context -> 'resolvedGearSignature'
       OR p_context -> 'v2EffectBoundary' -> 'gearRuleRevision'
          IS DISTINCT FROM p_context -> 'dependencyVector'
              -> 'gearRuleRevision'
       OR p_context -> 'v2EffectBoundary' -> 'resolverRevision'
          IS DISTINCT FROM p_context -> 'dependencyVector'
              -> 'resolverContractRevision'
       OR p_context -> 'v2EffectBoundary' -> 'simcRuntimeRevision'
          IS DISTINCT FROM p_context -> 'dependencyVector'
              -> 'simcRuntimeRevision'
       OR p_context -> 'profileReadiness' -> 'simcRuntimeRevision'
          IS DISTINCT FROM p_context -> 'dependencyVector'
              -> 'simcRuntimeRevision'
       OR (p_context -> 'setState')
          IS DISTINCT FROM (p_context -> 'v2EffectBoundary' -> 'setState')
       OR (p_context -> 'loadoutEffectSubjects')
          IS DISTINCT FROM (p_context -> 'v2EffectBoundary' -> 'subjects')
    THEN
        RAISE EXCEPTION 'v2 resolver replay context is invalid';
    END IF;
END;
$body$;

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
    expected_subject jsonb;
    relation_count integer;
    loadout_count integer := 0;
    saw_loadout boolean := false;
    saw_loadout_scope boolean := false;
BEGIN
    IF pg_catalog.jsonb_typeof(p_effect_evidence) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'v2 effect evidence must be an array';
    END IF;
    FOR occurrence IN
        SELECT value
        FROM pg_catalog.jsonb_array_elements(p_effect_evidence)
    LOOP
        IF pg_catalog.jsonb_typeof(occurrence) IS DISTINCT FROM 'object' THEN
            RAISE EXCEPTION 'v2 effect occurrence must be an object';
        END IF;
        IF (occurrence ->> 'scope') = 'slot' THEN
            IF NOT (occurrence ?& ARRAY[
                    'scope',
                    'slot',
                    'exactAuthorityEnvelopeKey',
                    'recordOrdinal',
                    'subjectKind',
                    'subjectKey',
                    'subjectVariantSignature',
                    'supportRecordKey'
               ])
               OR (occurrence - ARRAY[
                    'scope',
                    'slot',
                    'exactAuthorityEnvelopeKey',
                    'recordOrdinal',
                    'subjectKind',
                    'subjectKey',
                    'subjectVariantSignature',
                    'supportRecordKey'
               ]) <> '{}'::jsonb
               OR pg_catalog.jsonb_typeof(occurrence -> 'recordOrdinal') <> 'number'
               OR (occurrence ->> 'recordOrdinal') !~ '^[0-9]+$'
               OR (occurrence ->> 'slot') IS NULL
               OR (occurrence ->> 'exactAuthorityEnvelopeKey') IS NULL
               OR pg_catalog.jsonb_typeof(occurrence -> 'subjectKind')
                  IS DISTINCT FROM 'string'
               OR pg_catalog.jsonb_typeof(occurrence -> 'subjectKey')
                  IS DISTINCT FROM 'string'
               OR pg_catalog.jsonb_typeof(occurrence -> 'subjectVariantSignature')
                  IS DISTINCT FROM 'string'
               OR (occurrence ->> 'subjectKind') IS NULL
               OR (occurrence ->> 'subjectKey') IS NULL
               OR (occurrence ->> 'subjectVariantSignature') IS NULL
               OR (occurrence ->> 'supportRecordKey') IS NULL
            THEN
                RAISE EXCEPTION 'v2 slot effect occurrence is invalid';
            ELSIF saw_loadout_scope THEN
                RAISE EXCEPTION 'v2 loadout effect occurrences must be a suffix';
            END IF;
        ELSIF (occurrence ->> 'scope') = 'loadout' THEN
            saw_loadout_scope := true;
        ELSE
            RAISE EXCEPTION 'v2 effect occurrence scope is invalid';
        END IF;
    END LOOP;
    IF p_loadout_effect_authority_key IS NULL THEN
        IF saw_loadout_scope THEN
            RAISE EXCEPTION 'v2 no-effect rows cannot contain loadout occurrences';
        END IF;
        RETURN;
    END IF;
    FOR occurrence IN
        SELECT value
        FROM pg_catalog.jsonb_array_elements(p_effect_evidence)
    LOOP
        IF (occurrence ->> 'scope') = 'loadout' THEN
            saw_loadout := true;
            IF NOT (occurrence ?& ARRAY[
                    'scope',
                    'loadoutEffectAuthorityKey',
                    'recordOrdinal',
                    'subjectKind',
                    'subjectKey',
                    'subjectVariantSignature',
                    'supportRecordKey'
               ])
               OR (occurrence - ARRAY[
                    'scope',
                    'loadoutEffectAuthorityKey',
                    'recordOrdinal',
                    'subjectKind',
                    'subjectKey',
                    'subjectVariantSignature',
                    'supportRecordKey'
               ]) <> '{}'::jsonb
               OR pg_catalog.jsonb_typeof(occurrence -> 'recordOrdinal') <> 'number'
               OR (occurrence ->> 'recordOrdinal') !~ '^[0-9]+$'
               OR (occurrence ->> 'recordOrdinal')::integer <> expected_ordinal
               OR (occurrence ->> 'loadoutEffectAuthorityKey')
                  IS DISTINCT FROM p_loadout_effect_authority_key
               OR pg_catalog.jsonb_typeof(occurrence -> 'subjectKind')
                  IS DISTINCT FROM 'string'
               OR pg_catalog.jsonb_typeof(occurrence -> 'subjectKey')
                  IS DISTINCT FROM 'string'
               OR pg_catalog.jsonb_typeof(occurrence -> 'subjectVariantSignature')
                  IS DISTINCT FROM 'string'
            THEN
                RAISE EXCEPTION 'v2 loadout effect occurrence is invalid';
            END IF;
            SELECT relation.effect_record_key,
                   authority.canonical_json -> 'supportRecords'
                       -> expected_ordinal ->> 'supportRecordKey',
                   authority.canonical_json -> 'subjects' -> expected_ordinal
            INTO relation_key, expected_key, expected_subject
            FROM cache.websim_loadout_effect_authorities authority
            JOIN cache.websim_loadout_effect_authority_records relation
                ON relation.loadout_effect_authority_key
                   = authority.loadout_effect_authority_key
               AND relation.ordinal = expected_ordinal
            WHERE authority.loadout_effect_authority_key
                  = p_loadout_effect_authority_key
            FOR KEY SHARE;
            IF relation_key IS NULL
               OR relation_key IS DISTINCT FROM expected_key
               OR (occurrence ->> 'supportRecordKey') IS DISTINCT FROM relation_key
               OR expected_subject IS NULL
               OR pg_catalog.jsonb_typeof(expected_subject) IS DISTINCT FROM 'object'
               OR NOT (expected_subject ?& ARRAY[
                    'subjectKind',
                    'subjectKey',
                    'subjectVariantSignature',
                    'status',
                    'supportRecordKey'
               ])
               OR (expected_subject - ARRAY[
                    'subjectKind',
                    'subjectKey',
                    'subjectVariantSignature',
                    'status',
                    'supportRecordKey'
               ]) <> '{}'::jsonb
               OR (expected_subject ->> 'status') IS DISTINCT FROM 'verified'
               OR pg_catalog.jsonb_typeof(expected_subject -> 'subjectKind')
                  IS DISTINCT FROM 'string'
               OR pg_catalog.jsonb_typeof(expected_subject -> 'subjectKey')
                  IS DISTINCT FROM 'string'
               OR pg_catalog.jsonb_typeof(expected_subject -> 'subjectVariantSignature')
                  IS DISTINCT FROM 'string'
               OR (expected_subject ->> 'subjectKind') IS NULL
               OR (expected_subject ->> 'subjectKey') IS NULL
               OR (expected_subject ->> 'subjectVariantSignature') IS NULL
               OR (expected_subject ->> 'supportRecordKey') IS NULL
               OR (expected_subject ->> 'subjectKind')
                  IS DISTINCT FROM (occurrence ->> 'subjectKind')
               OR (expected_subject ->> 'subjectKey')
                  IS DISTINCT FROM (occurrence ->> 'subjectKey')
               OR (expected_subject ->> 'subjectVariantSignature')
                  IS DISTINCT FROM (occurrence ->> 'subjectVariantSignature')
               OR (expected_subject ->> 'supportRecordKey')
                  IS DISTINCT FROM (occurrence ->> 'supportRecordKey')
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

CREATE OR REPLACE FUNCTION cache.verify_websim_resolved_loadout_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $body$
BEGIN
    IF NEW.schema_revision = 'resolved-loadout-v2' THEN
        PERFORM cache.verify_websim_resolver_replay_context(
            NEW.resolver_replay_context_json
        );
        IF NEW.resolver_replay_context_json -> 'v2EffectBoundary'
               ->> 'loadoutEffectAuthorityKey'
           IS DISTINCT FROM NEW.loadout_effect_authority_key
        THEN
            RAISE EXCEPTION 'v2 resolver replay context is invalid';
        END IF;
        PERFORM cache.verify_websim_v2_effect_evidence(
            NEW.schema_revision,
            NEW.effect_evidence_by_occurrence_json,
            NEW.loadout_effect_authority_key
        );
    ELSIF NEW.schema_revision = 'resolved-loadout-v1' THEN
        PERFORM 1
        FROM cache.websim_gear_catalog_revisions
        WHERE catalog_revision = NEW.catalog_revision
        FOR KEY SHARE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'v1 ResolvedLoadout catalog revision is unavailable';
        END IF;
    END IF;
    RETURN NEW;
END;
$body$;

CREATE OR REPLACE FUNCTION cache.verify_websim_simulation_snapshot_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $body$
DECLARE
    loadout_schema_revision text;
    loadout_effect_evidence jsonb;
    loadout_authority_key text;
BEGIN
    IF NEW.schema_revision = 'simulation-snapshot-v2' THEN
        SELECT schema_revision,
               effect_evidence_by_occurrence_json,
               loadout_effect_authority_key
        INTO loadout_schema_revision,
             loadout_effect_evidence,
             loadout_authority_key
        FROM cache.websim_gear_resolved_loadouts
        WHERE resolved_loadout_key = NEW.resolved_loadout_key
        FOR KEY SHARE;
        IF loadout_schema_revision IS DISTINCT FROM 'resolved-loadout-v2'
           OR loadout_effect_evidence IS NULL
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
    ELSIF NEW.schema_revision = 'simulation-snapshot-v1' THEN
        SELECT schema_revision
        INTO loadout_schema_revision
        FROM cache.websim_gear_resolved_loadouts
        WHERE resolved_loadout_key = NEW.resolved_loadout_key
        FOR KEY SHARE;
        IF loadout_schema_revision IS DISTINCT FROM 'resolved-loadout-v1' THEN
            RAISE EXCEPTION 'v1 snapshot must bind its v1 ResolvedLoadout';
        END IF;
        PERFORM 1
        FROM cache.websim_gear_catalog_revisions
        WHERE catalog_revision = NEW.catalog_revision
        FOR KEY SHARE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'v1 SimulationSnapshot catalog revision is unavailable';
        END IF;
    END IF;
    RETURN NEW;
END;
$body$;

CREATE TRIGGER trg_websim_resolved_loadout_v1_v2_binding
BEFORE INSERT ON cache.websim_gear_resolved_loadouts
FOR EACH ROW EXECUTE FUNCTION cache.verify_websim_resolved_loadout_insert();

CREATE TRIGGER trg_websim_simulation_snapshot_v1_v2_binding
BEFORE INSERT ON cache.websim_simulation_snapshots
FOR EACH ROW EXECUTE FUNCTION cache.verify_websim_simulation_snapshot_insert();

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

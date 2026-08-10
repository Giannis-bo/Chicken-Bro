DO $preflight$
BEGIN
    IF pg_catalog.to_regprocedure('pg_catalog.sha256(bytea)') IS NULL THEN
        RAISE EXCEPTION 'PostgreSQL core pg_catalog.sha256(bytea) is required';
    END IF;
END;
$preflight$;

-- 0030 deliberately closed the canonical-document matrix.  This forward-only
-- replacement retains all six historical branches and admits only Task 5C's
-- three additional sealed document kinds.
DO $canonical_document_matrix$
DECLARE
    v_constraint_name name;
    v_constraint_count integer;
BEGIN
    SELECT pg_catalog.count(*)
    INTO v_constraint_count
    FROM pg_catalog.pg_constraint AS constraint_row
    WHERE constraint_row.conrelid = 'cache.websim_canonical_documents'::pg_catalog.regclass
      AND constraint_row.contype = 'c'
      AND pg_catalog.pg_get_constraintdef(constraint_row.oid) LIKE
          '%gear-exact-item-instance-v2%exact-authority-envelope-v1%';
    IF v_constraint_count IS DISTINCT FROM 1 THEN
        RAISE EXCEPTION 'expected exactly one 0030 canonical document matrix, found %',
            v_constraint_count;
    END IF;
    SELECT constraint_row.conname
    INTO v_constraint_name
    FROM pg_catalog.pg_constraint AS constraint_row
    WHERE constraint_row.conrelid = 'cache.websim_canonical_documents'::pg_catalog.regclass
      AND constraint_row.contype = 'c'
      AND pg_catalog.pg_get_constraintdef(constraint_row.oid) LIKE
          '%gear-exact-item-instance-v2%exact-authority-envelope-v1%';
    EXECUTE pg_catalog.format(
        'ALTER TABLE cache.websim_canonical_documents DROP CONSTRAINT %I',
        v_constraint_name
    );
END;
$canonical_document_matrix$;

ALTER TABLE cache.websim_canonical_documents
ADD CONSTRAINT websim_canonical_documents_exact_matrix_v2_check
CHECK (
    (document_kind = 'exact_item'
        AND schema_revision = 'gear-exact-item-instance-v2'
        AND content_key = 'exact-item-instance:sha256:' || canonical_sha256)
    OR (document_kind = 'exact_static_facts'
        AND schema_revision = 'exact-static-facts-v1'
        AND content_key = 'exact-static-facts:sha256:' || canonical_sha256)
    OR (document_kind = 'exact_progression'
        AND schema_revision = 'exact-progression-binding-v1'
        AND content_key = 'exact-progression:sha256:' || canonical_sha256)
    OR (document_kind = 'effect_record'
        AND schema_revision = 'simc-item-effect-record-v1'
        AND content_key = 'simc-item-effect-record:sha256:' || canonical_sha256)
    OR (document_kind = 'effect_aggregate'
        AND schema_revision = 'simc-item-effect-support-v1'
        AND content_key = 'simc-item-effect-support:sha256:' || canonical_sha256)
    OR (document_kind = 'exact_authority'
        AND schema_revision = 'exact-authority-envelope-v1'
        AND content_key = 'exact-authority:sha256:' || canonical_sha256)
    OR (document_kind = 'exact_runtime_resolver_context'
        AND schema_revision = 'exact-runtime-resolver-context-v1'
        AND content_key = 'exact-runtime-resolver-context:sha256:' || canonical_sha256)
    OR (document_kind = 'exact_runtime_authority_release'
        AND schema_revision = 'exact-runtime-authority-release-v1'
        AND content_key = 'exact-runtime-authority-release:sha256:' || canonical_sha256)
    OR (document_kind = 'exact_runtime_occurrence_index_entry'
        AND schema_revision = 'exact-runtime-occurrence-index-entry-v1'
        AND content_key = 'exact-runtime-occurrence-index-entry:sha256:' || canonical_sha256)
);

CREATE TABLE ops.websim_exact_runtime_resolver_contexts (
    resolver_context_key text PRIMARY KEY
        REFERENCES cache.websim_canonical_documents(content_key)
        ON DELETE RESTRICT,
    resolver_context_sha256 text NOT NULL
        CHECK (resolver_context_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    sealed_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp()
);

CREATE TABLE ops.websim_exact_runtime_authority_releases (
    runtime_authority_release_key text PRIMARY KEY
        REFERENCES cache.websim_canonical_documents(content_key)
        ON DELETE RESTRICT,
    binding_key text NOT NULL
        REFERENCES app.websim_exact_template_authority_bindings(binding_key)
        ON DELETE RESTRICT,
    resolver_context_key text NOT NULL
        REFERENCES ops.websim_exact_runtime_resolver_contexts(resolver_context_key)
        ON DELETE RESTRICT,
    sealed_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    UNIQUE (binding_key, runtime_authority_release_key)
);

CREATE INDEX idx_ops_websim_exact_runtime_release_binding
ON ops.websim_exact_runtime_authority_releases (
    binding_key,
    runtime_authority_release_key
);

CREATE TABLE ops.websim_exact_runtime_occurrence_index_entries (
    runtime_occurrence_index_entry_key text PRIMARY KEY
        REFERENCES cache.websim_canonical_documents(content_key)
        ON DELETE RESTRICT,
    runtime_authority_release_key text NOT NULL
        REFERENCES ops.websim_exact_runtime_authority_releases(runtime_authority_release_key)
        ON DELETE RESTRICT,
    subject_variant_signature text NOT NULL
        CHECK (subject_variant_signature ~ '^[a-z_]+-variant:sha256:[0-9a-f]{64}$'),
    resolved_gear_signature text NOT NULL
        CHECK (resolved_gear_signature ~ '^sha256:[0-9a-f]{64}$'),
    effect_record_key text NOT NULL
        REFERENCES cache.websim_canonical_documents(content_key)
        ON DELETE RESTRICT,
    effect_record_sha256 text NOT NULL
        CHECK (effect_record_sha256 ~ '^sha256:[0-9a-f]{64}$'),
    sealed_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    UNIQUE (runtime_authority_release_key, subject_variant_signature)
);

CREATE OR REPLACE FUNCTION ops.reject_websim_exact_runtime_authority_release_mutation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $function$
BEGIN
    RAISE EXCEPTION 'exact runtime authority release rows are append-only';
END;
$function$;

CREATE OR REPLACE FUNCTION ops.verify_websim_exact_runtime_resolver_context_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, ops, cache, pg_temp
AS $function$
DECLARE
    v_document_kind text;
    v_schema_revision text;
    v_context_bytes bytea;
    v_context_json jsonb;
BEGIN
    SELECT document_kind, schema_revision, canonical_bytes, canonical_json
    INTO v_document_kind, v_schema_revision, v_context_bytes, v_context_json
    FROM cache.websim_canonical_documents
    WHERE content_key = NEW.resolver_context_key
    FOR KEY SHARE;
    IF v_document_kind IS DISTINCT FROM 'exact_runtime_resolver_context'
       OR v_schema_revision IS DISTINCT FROM 'exact-runtime-resolver-context-v1'
       OR NEW.resolver_context_sha256 IS DISTINCT FROM
          'sha256:' || pg_catalog.encode(pg_catalog.sha256(v_context_bytes), 'hex')
       OR pg_catalog.jsonb_typeof(v_context_json) IS DISTINCT FROM 'object'
       OR v_context_json - ARRAY[
            'schemaRevision', 'producerIdentity', 'producerRevision',
            'seasonRevision', 'gearRuleRevision', 'resolverRevision',
            'simcRuntimeRevision', 'resolverAuthorityContext'
          ] <> '{}'::jsonb
       OR v_context_json ->> 'schemaRevision'
          IS DISTINCT FROM 'exact-runtime-resolver-context-v1'
       OR pg_catalog.jsonb_typeof(v_context_json -> 'resolverAuthorityContext')
          IS DISTINCT FROM 'object'
       OR pg_catalog.jsonb_path_exists(
            v_context_json,
            '$.** ? (@.type() == "object").keyvalue() ? (@.key == "rawProfile" || @.key == "rawString" || @.key == "playerName" || @.key == "characterName" || @.key == "realm" || @.key == "server" || @.key == "userId" || @.key == "userUuid" || @.key == "userUUID" || @.key == "ownerId")'::pg_catalog.jsonpath
          )
    THEN
        RAISE EXCEPTION 'exact runtime resolver context binding mismatch';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION ops.verify_websim_exact_runtime_authority_release_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, ops, cache, pg_temp
AS $function$
DECLARE
    v_document_kind text;
    v_schema_revision text;
    v_release_json jsonb;
    v_context_bytes bytea;
    v_context_json jsonb;
BEGIN
    SELECT document_kind, schema_revision, canonical_json
    INTO v_document_kind, v_schema_revision, v_release_json
    FROM cache.websim_canonical_documents
    WHERE content_key = NEW.runtime_authority_release_key
    FOR KEY SHARE;
    SELECT document.canonical_bytes, document.canonical_json
    INTO v_context_bytes, v_context_json
    FROM ops.websim_exact_runtime_resolver_contexts AS context
    JOIN cache.websim_canonical_documents AS document
      ON document.content_key = context.resolver_context_key
    WHERE context.resolver_context_key = NEW.resolver_context_key
    FOR KEY SHARE OF context, document;
    IF v_document_kind IS DISTINCT FROM 'exact_runtime_authority_release'
       OR v_schema_revision IS DISTINCT FROM 'exact-runtime-authority-release-v1'
       OR pg_catalog.jsonb_typeof(v_release_json) IS DISTINCT FROM 'object'
       OR v_release_json - ARRAY[
            'schemaRevision', 'producerIdentity', 'producerRevision',
            'resolverContextKey', 'resolverContextSha256', 'dependencyVector'
          ] <> '{}'::jsonb
       OR v_release_json ->> 'schemaRevision'
          IS DISTINCT FROM 'exact-runtime-authority-release-v1'
       OR v_release_json ->> 'resolverContextKey'
          IS DISTINCT FROM NEW.resolver_context_key
       OR v_release_json ->> 'resolverContextSha256'
          IS DISTINCT FROM 'sha256:' || pg_catalog.encode(pg_catalog.sha256(v_context_bytes), 'hex')
       OR pg_catalog.jsonb_typeof(v_release_json -> 'dependencyVector')
          IS DISTINCT FROM 'object'
       OR (v_release_json -> 'dependencyVector') ?& ARRAY[
            'seasonRevision', 'gameBuild', 'gearRuleRevision',
            'resolverRevision', 'compilerRevision', 'workerRevision',
            'simcRuntimeRevision', 'effectAuthorityRevision'
          ] IS DISTINCT FROM true
       OR (v_release_json -> 'dependencyVector') - ARRAY[
            'seasonRevision', 'gameBuild', 'gearRuleRevision',
            'resolverRevision', 'compilerRevision', 'workerRevision',
            'simcRuntimeRevision', 'effectAuthorityRevision'
          ] <> '{}'::jsonb
       OR v_release_json -> 'dependencyVector' ->> 'seasonRevision'
          IS DISTINCT FROM v_context_json ->> 'seasonRevision'
       OR v_release_json -> 'dependencyVector' ->> 'gearRuleRevision'
          IS DISTINCT FROM v_context_json ->> 'gearRuleRevision'
       OR v_release_json -> 'dependencyVector' ->> 'resolverRevision'
          IS DISTINCT FROM v_context_json ->> 'resolverRevision'
       OR v_release_json -> 'dependencyVector' ->> 'simcRuntimeRevision'
          IS DISTINCT FROM v_context_json ->> 'simcRuntimeRevision'
    THEN
        RAISE EXCEPTION 'exact runtime authority release binding mismatch';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION ops.verify_websim_exact_runtime_occurrence_index_entry_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, ops, cache, pg_temp
AS $function$
DECLARE
    v_document_kind text;
    v_schema_revision text;
    v_entry_json jsonb;
    v_record_kind text;
    v_record_bytes bytea;
    v_record_json jsonb;
    v_release_json jsonb;
BEGIN
    SELECT document_kind, schema_revision, canonical_json
    INTO v_document_kind, v_schema_revision, v_entry_json
    FROM cache.websim_canonical_documents
    WHERE content_key = NEW.runtime_occurrence_index_entry_key
    FOR KEY SHARE;
    SELECT document_kind, canonical_bytes, canonical_json
    INTO v_record_kind, v_record_bytes, v_record_json
    FROM cache.websim_canonical_documents
    WHERE content_key = NEW.effect_record_key
    FOR KEY SHARE;
    SELECT document.canonical_json
    INTO v_release_json
    FROM ops.websim_exact_runtime_authority_releases AS release
    JOIN cache.websim_canonical_documents AS document
      ON document.content_key = release.runtime_authority_release_key
    WHERE release.runtime_authority_release_key = NEW.runtime_authority_release_key
    FOR KEY SHARE OF release, document;
    IF v_document_kind IS DISTINCT FROM 'exact_runtime_occurrence_index_entry'
       OR v_schema_revision IS DISTINCT FROM 'exact-runtime-occurrence-index-entry-v1'
       OR v_record_kind IS DISTINCT FROM 'effect_record'
       OR pg_catalog.jsonb_typeof(v_entry_json) IS DISTINCT FROM 'object'
       OR v_entry_json - ARRAY[
            'schemaRevision', 'producerIdentity', 'producerRevision',
            'runtimeAuthorityReleaseKey', 'subjectVariantSignature',
            'resolvedGearSignature', 'effectRecordKey', 'effectRecordSha256'
          ] <> '{}'::jsonb
       OR v_entry_json ->> 'schemaRevision'
          IS DISTINCT FROM 'exact-runtime-occurrence-index-entry-v1'
       OR v_entry_json ->> 'runtimeAuthorityReleaseKey'
          IS DISTINCT FROM NEW.runtime_authority_release_key
       OR v_entry_json ->> 'subjectVariantSignature'
          IS DISTINCT FROM NEW.subject_variant_signature
       OR v_entry_json ->> 'resolvedGearSignature'
          IS DISTINCT FROM NEW.resolved_gear_signature
       OR v_entry_json ->> 'effectRecordKey'
          IS DISTINCT FROM NEW.effect_record_key
       OR v_entry_json ->> 'effectRecordSha256'
          IS DISTINCT FROM 'sha256:' || pg_catalog.encode(pg_catalog.sha256(v_record_bytes), 'hex')
       OR v_record_json ->> 'subjectVariantSignature'
          IS DISTINCT FROM NEW.subject_variant_signature
       OR v_record_json ->> 'simcRuntimeRevision'
          IS DISTINCT FROM v_release_json -> 'dependencyVector' ->> 'simcRuntimeRevision'
    THEN
        RAISE EXCEPTION 'exact runtime occurrence index binding mismatch';
    END IF;
    RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_websim_exact_runtime_resolver_context_binding
ON ops.websim_exact_runtime_resolver_contexts;
CREATE TRIGGER trg_websim_exact_runtime_resolver_context_binding
BEFORE INSERT ON ops.websim_exact_runtime_resolver_contexts
FOR EACH ROW
EXECUTE FUNCTION ops.verify_websim_exact_runtime_resolver_context_insert();

DROP TRIGGER IF EXISTS trg_websim_exact_runtime_authority_release_binding
ON ops.websim_exact_runtime_authority_releases;
CREATE TRIGGER trg_websim_exact_runtime_authority_release_binding
BEFORE INSERT ON ops.websim_exact_runtime_authority_releases
FOR EACH ROW
EXECUTE FUNCTION ops.verify_websim_exact_runtime_authority_release_insert();

DROP TRIGGER IF EXISTS trg_websim_exact_runtime_occurrence_index_entry_binding
ON ops.websim_exact_runtime_occurrence_index_entries;
CREATE TRIGGER trg_websim_exact_runtime_occurrence_index_entry_binding
BEFORE INSERT ON ops.websim_exact_runtime_occurrence_index_entries
FOR EACH ROW
EXECUTE FUNCTION ops.verify_websim_exact_runtime_occurrence_index_entry_insert();

DO $triggers$
DECLARE
    v_table text;
BEGIN
    FOREACH v_table IN ARRAY ARRAY[
        'websim_exact_runtime_resolver_contexts',
        'websim_exact_runtime_authority_releases',
        'websim_exact_runtime_occurrence_index_entries'
    ]
    LOOP
        EXECUTE pg_catalog.format(
            'DROP TRIGGER IF EXISTS %I ON ops.%I',
            pg_catalog.format('trg_%s_immutable', v_table), v_table
        );
        EXECUTE pg_catalog.format(
            'CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON ops.%I '
            'FOR EACH ROW EXECUTE FUNCTION ops.reject_websim_exact_runtime_authority_release_mutation()',
            pg_catalog.format('trg_%s_immutable', v_table), v_table
        );
        EXECUTE pg_catalog.format(
            'DROP TRIGGER IF EXISTS %I ON ops.%I',
            pg_catalog.format('trg_%s_truncate', v_table), v_table
        );
        EXECUTE pg_catalog.format(
            'CREATE TRIGGER %I BEFORE TRUNCATE ON ops.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION ops.reject_websim_exact_runtime_authority_release_mutation()',
            pg_catalog.format('trg_%s_truncate', v_table), v_table
        );
    END LOOP;
END;
$triggers$;

-- 0033 deliberately keeps its relation validator as SECURITY INVOKER, but the
-- 0033 admission function is a wow_migrator-owned SECURITY DEFINER entrypoint
-- for wow_app. The deferred validator must therefore retain its fixed search
-- path while running under the same least-privileged owner; otherwise a valid
-- app admission cannot read the tables whose direct access is revoked.
ALTER FUNCTION app.verify_websim_exact_template_authority_binding_relations()
SECURITY DEFINER;
ALTER FUNCTION app.verify_websim_exact_template_authority_binding_relations()
OWNER TO wow_migrator;
REVOKE ALL ON FUNCTION app.verify_websim_exact_template_authority_binding_relations()
FROM PUBLIC, wow_app, wow_exact_worker;

-- 0033's RETURNS TABLE output column is also named binding_key.  Preserve that
-- frozen migration verbatim and forward-replace its function with an explicit
-- primary-key conflict target, so PL/pgSQL never has to resolve that output
-- variable against the insert target column.
CREATE OR REPLACE FUNCTION ops.websim_exact_template_binding_admit(
    p_user_id uuid,
    p_template_id uuid,
    p_template_config_hash text,
    p_source_payload_hash text,
    p_selection_signature text,
    p_binding_bytes bytea
)
RETURNS TABLE(binding_key text, binding_bytes bytea)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, app, cache, ops, pg_temp
AS $function$
DECLARE
    v_template_config_hash text;
    v_binding_key text;
    v_binding_json jsonb;
    v_owner_key_hash text;
BEGIN
    IF p_template_config_hash !~ '^[0-9a-f]{64}$'
       OR p_source_payload_hash !~ '^sha256:[0-9a-f]{64}$'
       OR p_selection_signature !~ '^sha256:[0-9a-f]{64}$'
       OR pg_catalog.octet_length(p_binding_bytes) NOT BETWEEN 2 AND 131072
    THEN
        RAISE EXCEPTION 'exact template binding input is invalid';
    END IF;
    SELECT config_hash
    INTO v_template_config_hash
    FROM app.build_templates
    WHERE id = p_template_id
      AND user_id = p_user_id
      AND template_type = 'gear'
    FOR KEY SHARE;
    IF NOT FOUND OR v_template_config_hash IS DISTINCT FROM p_template_config_hash THEN
        RAISE EXCEPTION 'exact template binding source is unavailable';
    END IF;
    BEGIN
        v_binding_json := pg_catalog.convert_from(p_binding_bytes, 'UTF8')::jsonb;
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'exact template binding bytes are invalid';
    END;
    v_owner_key_hash := 'sha256:' || pg_catalog.encode(
        pg_catalog.sha256(
            pg_catalog.convert_to(
                'exact-template-owner-v1:' || p_user_id::text,
                'UTF8'
            )
        ),
        'hex'
    );
    IF pg_catalog.jsonb_typeof(v_binding_json) IS DISTINCT FROM 'object'
       OR v_binding_json - ARRAY[
            'schemaRevision', 'source', 'authority', 'exactAuthorityBySlot'
       ] <> '{}'::jsonb
       OR v_binding_json ->> 'schemaRevision'
          IS DISTINCT FROM 'exact-template-authority-binding-v1'
       OR pg_catalog.jsonb_typeof(v_binding_json -> 'source')
          IS DISTINCT FROM 'object'
       OR pg_catalog.jsonb_typeof(v_binding_json -> 'authority')
          IS DISTINCT FROM 'object'
       OR pg_catalog.jsonb_typeof(v_binding_json -> 'exactAuthorityBySlot')
          IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_array_length(v_binding_json -> 'exactAuthorityBySlot')
          NOT BETWEEN 1 AND 16
       OR v_binding_json #>> '{source,ownerKeyHash}'
          IS DISTINCT FROM v_owner_key_hash
       OR v_binding_json #>> '{source,templateId}'
          IS DISTINCT FROM p_template_id::text
       OR v_binding_json #>> '{source,templateConfigHash}'
          IS DISTINCT FROM p_template_config_hash
       OR v_binding_json #>> '{source,sourcePayloadHash}'
          IS DISTINCT FROM p_source_payload_hash
       OR v_binding_json #>> '{source,selectionSignature}'
          IS DISTINCT FROM p_selection_signature
    THEN
        RAISE EXCEPTION 'exact template binding payload is invalid';
    END IF;
    v_binding_key := 'exact-template-authority-binding:sha256:' ||
        pg_catalog.encode(pg_catalog.sha256(p_binding_bytes), 'hex');
    INSERT INTO app.websim_exact_template_authority_bindings (
        binding_key,
        user_id,
        template_id,
        template_config_hash,
        source_payload_hash,
        selection_signature,
        binding_bytes,
        binding_json,
        binding_sha256
    ) VALUES (
        v_binding_key,
        p_user_id,
        p_template_id,
        p_template_config_hash,
        p_source_payload_hash,
        p_selection_signature,
        p_binding_bytes,
        v_binding_json,
        pg_catalog.encode(pg_catalog.sha256(p_binding_bytes), 'hex')
    )
    ON CONFLICT ON CONSTRAINT websim_exact_template_authority_bindings_pkey
    DO NOTHING;
    INSERT INTO app.websim_exact_template_authority_binding_slots (
        binding_key,
        ordinal,
        slot,
        exact_authority_envelope_key
    )
    SELECT
        v_binding_key,
        (entry.ordinality - 1)::integer,
        entry.value ->> 'slot',
        entry.value ->> 'exactAuthorityEnvelopeKey'
    FROM pg_catalog.jsonb_array_elements(
        v_binding_json -> 'exactAuthorityBySlot'
    ) WITH ORDINALITY AS entry(value, ordinality)
    ON CONFLICT DO NOTHING;
    RETURN QUERY
    SELECT
        binding.binding_key,
        binding.binding_bytes
    FROM app.websim_exact_template_authority_bindings AS binding
    WHERE binding.binding_key = v_binding_key
      AND binding.user_id = p_user_id
      AND binding.template_id = p_template_id
      AND binding.template_config_hash = p_template_config_hash
      AND binding.source_payload_hash = p_source_payload_hash
      AND binding.selection_signature = p_selection_signature;
END;
$function$;

CREATE OR REPLACE FUNCTION ops.websim_exact_runtime_authority_release_admit(
    p_user_id uuid,
    p_binding_key text,
    p_resolver_context_bytes bytea,
    p_runtime_authority_release_bytes bytea,
    p_occurrence_index_entry_bytes bytea[]
)
RETURNS TABLE(
    resolver_context_key text,
    resolver_context_bytes bytea,
    runtime_authority_release_key text,
    runtime_authority_release_bytes bytea
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, app, cache, ops, identity, pg_temp
AS $function$
DECLARE
    v_context_key text;
    v_release_key text;
    v_context_json jsonb;
    v_release_json jsonb;
BEGIN
    IF p_binding_key !~ '^exact-template-authority-binding:sha256:[0-9a-f]{64}$'
       OR pg_catalog.octet_length(p_resolver_context_bytes) NOT BETWEEN 2 AND 1048576
       OR pg_catalog.octet_length(p_runtime_authority_release_bytes) NOT BETWEEN 2 AND 1048576
       OR COALESCE(pg_catalog.cardinality(p_occurrence_index_entry_bytes), 0) > 128
       OR NOT EXISTS (
            SELECT 1
            FROM app.websim_exact_template_authority_bindings AS binding
            WHERE binding.binding_key = p_binding_key
              AND binding.user_id = p_user_id
          )
    THEN
        RAISE EXCEPTION 'exact runtime authority release admission source is unavailable';
    END IF;
    BEGIN
        v_context_json := pg_catalog.convert_from(p_resolver_context_bytes, 'UTF8')::jsonb;
        v_release_json := pg_catalog.convert_from(
            p_runtime_authority_release_bytes, 'UTF8'
        )::jsonb;
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'exact runtime authority release bytes are invalid';
    END;
    v_context_key := 'exact-runtime-resolver-context:sha256:' ||
        pg_catalog.encode(pg_catalog.sha256(p_resolver_context_bytes), 'hex');
    v_release_key := 'exact-runtime-authority-release:sha256:' ||
        pg_catalog.encode(pg_catalog.sha256(p_runtime_authority_release_bytes), 'hex');
    INSERT INTO cache.websim_canonical_documents (
        content_key, document_kind, schema_revision, canonical_bytes,
        canonical_json, canonical_sha256
    ) VALUES
        (v_context_key, 'exact_runtime_resolver_context',
         'exact-runtime-resolver-context-v1', p_resolver_context_bytes,
         v_context_json,
         pg_catalog.encode(pg_catalog.sha256(p_resolver_context_bytes), 'hex')),
        (v_release_key, 'exact_runtime_authority_release',
         'exact-runtime-authority-release-v1', p_runtime_authority_release_bytes,
         v_release_json,
         pg_catalog.encode(pg_catalog.sha256(p_runtime_authority_release_bytes), 'hex'))
    ON CONFLICT DO NOTHING;
    INSERT INTO ops.websim_exact_runtime_resolver_contexts (
        resolver_context_key, resolver_context_sha256
    ) VALUES (
        v_context_key,
        'sha256:' || pg_catalog.encode(pg_catalog.sha256(p_resolver_context_bytes), 'hex')
    ) ON CONFLICT DO NOTHING;
    INSERT INTO ops.websim_exact_runtime_authority_releases (
        runtime_authority_release_key, binding_key, resolver_context_key
    ) VALUES (v_release_key, p_binding_key, v_context_key)
    ON CONFLICT DO NOTHING;
    INSERT INTO cache.websim_canonical_documents (
        content_key, document_kind, schema_revision, canonical_bytes,
        canonical_json, canonical_sha256
    )
    SELECT
        'exact-runtime-occurrence-index-entry:sha256:' ||
            pg_catalog.encode(pg_catalog.sha256(entry.canonical_bytes), 'hex'),
        'exact_runtime_occurrence_index_entry',
        'exact-runtime-occurrence-index-entry-v1',
        entry.canonical_bytes,
        pg_catalog.convert_from(entry.canonical_bytes, 'UTF8')::jsonb,
        pg_catalog.encode(pg_catalog.sha256(entry.canonical_bytes), 'hex')
    FROM pg_catalog.unnest(p_occurrence_index_entry_bytes) AS entry(canonical_bytes)
    ON CONFLICT DO NOTHING;
    INSERT INTO ops.websim_exact_runtime_occurrence_index_entries (
        runtime_occurrence_index_entry_key,
        runtime_authority_release_key,
        subject_variant_signature,
        resolved_gear_signature,
        effect_record_key,
        effect_record_sha256
    )
    SELECT
        'exact-runtime-occurrence-index-entry:sha256:' ||
            pg_catalog.encode(pg_catalog.sha256(entry.canonical_bytes), 'hex'),
        v_release_key,
        entry.payload ->> 'subjectVariantSignature',
        entry.payload ->> 'resolvedGearSignature',
        entry.payload ->> 'effectRecordKey',
        entry.payload ->> 'effectRecordSha256'
    FROM (
        SELECT
            canonical_bytes,
            pg_catalog.convert_from(canonical_bytes, 'UTF8')::jsonb AS payload
        FROM pg_catalog.unnest(p_occurrence_index_entry_bytes) AS entry_source(canonical_bytes)
    ) AS entry
    ON CONFLICT DO NOTHING;
    RETURN QUERY
    SELECT
        context.resolver_context_key,
        context_document.canonical_bytes,
        release.runtime_authority_release_key,
        release_document.canonical_bytes
    FROM ops.websim_exact_runtime_authority_releases AS release
    JOIN ops.websim_exact_runtime_resolver_contexts AS context
      ON context.resolver_context_key = release.resolver_context_key
    JOIN cache.websim_canonical_documents AS context_document
      ON context_document.content_key = context.resolver_context_key
    JOIN cache.websim_canonical_documents AS release_document
      ON release_document.content_key = release.runtime_authority_release_key
    WHERE release.runtime_authority_release_key = v_release_key
      AND release.binding_key = p_binding_key;
END;
$function$;

CREATE OR REPLACE FUNCTION ops.websim_exact_runtime_authority_release_read(
    p_user_id uuid,
    p_binding_key text
)
RETURNS TABLE(
    resolver_context_key text,
    resolver_context_bytes bytea,
    runtime_authority_release_key text,
    runtime_authority_release_bytes bytea
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, app, cache, ops, identity, pg_temp
AS $function$
    SELECT
        context.resolver_context_key,
        context_document.canonical_bytes,
        release.runtime_authority_release_key,
        release_document.canonical_bytes
    FROM ops.websim_exact_runtime_authority_releases AS release
    JOIN app.websim_exact_template_authority_bindings AS binding
      ON binding.binding_key = release.binding_key
     AND binding.user_id = p_user_id
    JOIN ops.websim_exact_runtime_resolver_contexts AS context
      ON context.resolver_context_key = release.resolver_context_key
    JOIN cache.websim_canonical_documents AS context_document
      ON context_document.content_key = context.resolver_context_key
    JOIN cache.websim_canonical_documents AS release_document
      ON release_document.content_key = release.runtime_authority_release_key
    WHERE release.binding_key = p_binding_key
    ORDER BY release.runtime_authority_release_key;
$function$;

CREATE OR REPLACE FUNCTION ops.websim_exact_runtime_authority_release_occurrences_read(
    p_user_id uuid,
    p_binding_key text,
    p_runtime_authority_release_key text
)
RETURNS TABLE(
    runtime_occurrence_index_entry_key text,
    runtime_occurrence_index_entry_bytes bytea
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, app, cache, ops, identity, pg_temp
AS $function$
    SELECT
        entry.runtime_occurrence_index_entry_key,
        document.canonical_bytes
    FROM ops.websim_exact_runtime_occurrence_index_entries AS entry
    JOIN ops.websim_exact_runtime_authority_releases AS release
      ON release.runtime_authority_release_key = entry.runtime_authority_release_key
    JOIN app.websim_exact_template_authority_bindings AS binding
      ON binding.binding_key = release.binding_key
     AND binding.user_id = p_user_id
    JOIN cache.websim_canonical_documents AS document
      ON document.content_key = entry.runtime_occurrence_index_entry_key
    WHERE release.binding_key = p_binding_key
      AND release.runtime_authority_release_key = p_runtime_authority_release_key
    ORDER BY entry.subject_variant_signature, entry.runtime_occurrence_index_entry_key;
$function$;

ALTER FUNCTION ops.websim_exact_runtime_authority_release_admit(uuid, text, bytea, bytea, bytea[])
OWNER TO wow_migrator;
ALTER FUNCTION ops.websim_exact_runtime_authority_release_read(uuid, text)
OWNER TO wow_migrator;
ALTER FUNCTION ops.websim_exact_runtime_authority_release_occurrences_read(uuid, text, text)
OWNER TO wow_migrator;

REVOKE ALL ON FUNCTION ops.websim_exact_runtime_authority_release_admit(uuid, text, bytea, bytea, bytea[])
FROM PUBLIC, wow_app, wow_exact_worker;
REVOKE ALL ON FUNCTION ops.websim_exact_runtime_authority_release_read(uuid, text)
FROM PUBLIC, wow_app, wow_exact_worker;
REVOKE ALL ON FUNCTION ops.websim_exact_runtime_authority_release_occurrences_read(uuid, text, text)
FROM PUBLIC, wow_app, wow_exact_worker;

GRANT SELECT, INSERT, UPDATE, DELETE ON
    ops.websim_exact_runtime_resolver_contexts,
    ops.websim_exact_runtime_authority_releases,
    ops.websim_exact_runtime_occurrence_index_entries
TO wow_migrator;
REVOKE ALL ON
    ops.websim_exact_runtime_resolver_contexts,
    ops.websim_exact_runtime_authority_releases,
    ops.websim_exact_runtime_occurrence_index_entries
FROM PUBLIC, wow_app, wow_exact_worker;

REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON
    cache.websim_canonical_documents,
    cache.websim_effect_aggregate_records,
    cache.websim_exact_authority_bundles
FROM wow_exact_worker;
GRANT SELECT ON
    cache.websim_canonical_documents,
    cache.websim_effect_aggregate_records,
    cache.websim_exact_authority_bundles
TO wow_exact_worker;

GRANT EXECUTE ON FUNCTION
    ops.websim_exact_runtime_authority_release_admit(uuid, text, bytea, bytea, bytea[]),
    ops.websim_exact_runtime_authority_release_read(uuid, text),
    ops.websim_exact_runtime_authority_release_occurrences_read(uuid, text, text)
TO wow_app;
GRANT EXECUTE ON FUNCTION
    ops.websim_exact_runtime_authority_release_read(uuid, text),
    ops.websim_exact_runtime_authority_release_occurrences_read(uuid, text, text)
TO wow_exact_worker;

-- 0035 extends the historical v1/v2 snapshot tables in place.  The prior
-- predicates remain verbatim through their original constraints; this
-- forward-only replacement admits v3 only when the additional constraint
-- below closes every release/context/vector relation.
ALTER TABLE cache.websim_gear_resolved_loadouts
    ADD COLUMN IF NOT EXISTS runtime_authority_release_key text
        REFERENCES ops.websim_exact_runtime_authority_releases(runtime_authority_release_key)
        ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS resolver_context_key text
        REFERENCES ops.websim_exact_runtime_resolver_contexts(resolver_context_key)
        ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS dependency_vector_json jsonb;

ALTER TABLE cache.websim_simulation_snapshots
    ADD COLUMN IF NOT EXISTS runtime_authority_release_key text
        REFERENCES ops.websim_exact_runtime_authority_releases(runtime_authority_release_key)
        ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS resolver_context_key text
        REFERENCES ops.websim_exact_runtime_resolver_contexts(resolver_context_key)
        ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS dependency_vector_json jsonb;

DO $v3_snapshot_constraint_upgrade$
DECLARE
    v_table regclass;
    v_constraint_name name;
    v_constraint_definition text;
    v_expected_count integer;
BEGIN
    FOREACH v_table IN ARRAY ARRAY[
        'cache.websim_gear_resolved_loadouts'::regclass,
        'cache.websim_simulation_snapshots'::regclass
    ]
    LOOP
        SELECT pg_catalog.count(*)
        INTO v_expected_count
        FROM pg_catalog.pg_constraint AS constraint_row
        WHERE constraint_row.conrelid = v_table
          AND constraint_row.contype = 'c'
          AND constraint_row.conname IN (
              'websim_gear_resolved_loadouts_v1_v2_fields_check',
              'websim_simulation_snapshots_v1_v2_fields_check'
          );
        IF v_expected_count IS DISTINCT FROM 1 THEN
            RAISE EXCEPTION 'expected one historical v1/v2 snapshot constraint on %, found %',
                v_table, v_expected_count;
        END IF;
        SELECT constraint_row.conname, pg_catalog.pg_get_constraintdef(constraint_row.oid)
        INTO v_constraint_name, v_constraint_definition
        FROM pg_catalog.pg_constraint AS constraint_row
        WHERE constraint_row.conrelid = v_table
          AND constraint_row.contype = 'c'
          AND constraint_row.conname IN (
              'websim_gear_resolved_loadouts_v1_v2_fields_check',
              'websim_simulation_snapshots_v1_v2_fields_check'
          );
        EXECUTE pg_catalog.format(
            'ALTER TABLE %s DROP CONSTRAINT %I', v_table, v_constraint_name
        );
        IF pg_catalog.right(v_constraint_definition, 1) <> ')' THEN
            RAISE EXCEPTION 'historical v1/v2 snapshot constraint is malformed on %',
                v_table;
        END IF;
        v_constraint_definition := pg_catalog.left(
            v_constraint_definition,
            pg_catalog.length(v_constraint_definition) - 1
        ) || ' OR (schema_revision = ''resolved-loadout-v3''))';
        IF v_table = 'cache.websim_simulation_snapshots'::regclass THEN
            v_constraint_definition := pg_catalog.regexp_replace(
                v_constraint_definition,
                'resolved-loadout-v3',
                'simulation-snapshot-v3'
            );
        END IF;
        EXECUTE pg_catalog.format(
            'ALTER TABLE %s ADD CONSTRAINT %I %s',
            v_table,
            v_constraint_name,
            v_constraint_definition
        );
    END LOOP;
END;
$v3_snapshot_constraint_upgrade$;

ALTER TABLE cache.websim_gear_resolved_loadouts
ADD CONSTRAINT websim_gear_resolved_loadouts_runtime_authority_v3_check CHECK (
    (
        schema_revision IN ('resolved-loadout-v1', 'resolved-loadout-v2')
        AND runtime_authority_release_key IS NULL
        AND resolver_context_key IS NULL
        AND dependency_vector_json IS NULL
    )
    OR (
        schema_revision = 'resolved-loadout-v3'
        AND resolved_loadout_key ~ '^resolved-loadout-v3:sha256:[0-9a-f]{64}$'
        AND catalog_revision IS NULL
        AND exact_registry_revision IS NULL
        AND gear_rule_revision IS NOT DISTINCT FROM (
            loadout_json -> 'dependencyVector' ->> 'gearRuleRevision'
        )
        AND loadout_json ->> 'schemaRevision' IS NOT DISTINCT FROM schema_revision
        AND loadout_json ->> 'resolvedLoadoutKey' IS NOT DISTINCT FROM resolved_loadout_key
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
        AND pg_catalog.jsonb_typeof(resolver_replay_context_json)
            IS NOT DISTINCT FROM 'object'
        AND runtime_authority_release_key
            ~ '^exact-runtime-authority-release:sha256:[0-9a-f]{64}$'
        AND resolver_context_key
            ~ '^exact-runtime-resolver-context:sha256:[0-9a-f]{64}$'
        AND runtime_authority_release_key IS NOT DISTINCT FROM (
            loadout_json ->> 'runtimeAuthorityReleaseKey'
        )
        AND resolver_context_key IS NOT DISTINCT FROM (
            loadout_json ->> 'resolverContextKey'
        )
        AND pg_catalog.jsonb_typeof(dependency_vector_json)
            IS NOT DISTINCT FROM 'object'
        AND dependency_vector_json ?& ARRAY[
            'seasonRevision', 'gameBuild', 'gearRuleRevision',
            'resolverRevision', 'compilerRevision', 'workerRevision',
            'simcRuntimeRevision', 'effectAuthorityRevision'
        ]
        AND dependency_vector_json - ARRAY[
            'seasonRevision', 'gameBuild', 'gearRuleRevision',
            'resolverRevision', 'compilerRevision', 'workerRevision',
            'simcRuntimeRevision', 'effectAuthorityRevision'
        ] = '{}'::jsonb
        AND dependency_vector_json IS NOT DISTINCT FROM (
            loadout_json -> 'dependencyVector'
        )
    )
);

ALTER TABLE cache.websim_simulation_snapshots
ADD CONSTRAINT websim_simulation_snapshots_runtime_authority_v3_check CHECK (
    (
        schema_revision IN ('simulation-snapshot-v1', 'simulation-snapshot-v2')
        AND runtime_authority_release_key IS NULL
        AND resolver_context_key IS NULL
        AND dependency_vector_json IS NULL
    )
    OR (
        schema_revision = 'simulation-snapshot-v3'
        AND simulation_snapshot_key ~ '^simulation-snapshot-v3:sha256:[0-9a-f]{64}$'
        AND resolved_loadout_key ~ '^resolved-loadout-v3:sha256:[0-9a-f]{64}$'
        AND catalog_revision IS NULL
        AND gear_rule_revision IS NOT DISTINCT FROM (
            snapshot_json -> 'dependencyVector' ->> 'gearRuleRevision'
        )
        AND snapshot_json ->> 'schemaRevision' IS NOT DISTINCT FROM schema_revision
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
        AND snapshot_json ->> 'rowHash' IS NOT DISTINCT FROM row_hash
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
        AND runtime_authority_release_key
            ~ '^exact-runtime-authority-release:sha256:[0-9a-f]{64}$'
        AND resolver_context_key
            ~ '^exact-runtime-resolver-context:sha256:[0-9a-f]{64}$'
        AND runtime_authority_release_key IS NOT DISTINCT FROM (
            snapshot_json ->> 'runtimeAuthorityReleaseKey'
        )
        AND resolver_context_key IS NOT DISTINCT FROM (
            snapshot_json ->> 'resolverContextKey'
        )
        AND pg_catalog.jsonb_typeof(dependency_vector_json)
            IS NOT DISTINCT FROM 'object'
        AND dependency_vector_json ?& ARRAY[
            'seasonRevision', 'gameBuild', 'gearRuleRevision',
            'resolverRevision', 'compilerRevision', 'workerRevision',
            'simcRuntimeRevision', 'effectAuthorityRevision'
        ]
        AND dependency_vector_json - ARRAY[
            'seasonRevision', 'gameBuild', 'gearRuleRevision',
            'resolverRevision', 'compilerRevision', 'workerRevision',
            'simcRuntimeRevision', 'effectAuthorityRevision'
        ] = '{}'::jsonb
        AND dependency_vector_json IS NOT DISTINCT FROM (
            snapshot_json -> 'dependencyVector'
        )
    )
);

CREATE OR REPLACE FUNCTION cache.verify_websim_v3_resolved_loadout_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, cache, ops, pg_temp
AS $function$
DECLARE
    v_release_context_key text;
    v_release_vector jsonb;
BEGIN
    IF NEW.schema_revision <> 'resolved-loadout-v3' THEN
        RETURN NEW;
    END IF;
    PERFORM cache.verify_websim_resolver_replay_context(
        NEW.resolver_replay_context_json
    );
    SELECT release.resolver_context_key,
           document.canonical_json -> 'dependencyVector'
    INTO v_release_context_key, v_release_vector
    FROM ops.websim_exact_runtime_authority_releases AS release
    JOIN cache.websim_canonical_documents AS document
      ON document.content_key = release.runtime_authority_release_key
    WHERE release.runtime_authority_release_key = NEW.runtime_authority_release_key
    FOR KEY SHARE OF release, document;
    IF v_release_context_key IS DISTINCT FROM NEW.resolver_context_key
       OR v_release_vector IS DISTINCT FROM NEW.dependency_vector_json
       OR v_release_vector IS DISTINCT FROM NEW.loadout_json -> 'dependencyVector'
       OR NEW.resolver_replay_context_json IS NULL
       OR NEW.resolver_replay_context_json -> 'dependencyVector'
            ->> 'gearRuleRevision'
          IS DISTINCT FROM v_release_vector ->> 'gearRuleRevision'
       OR NEW.resolver_replay_context_json -> 'dependencyVector'
            ->> 'resolverContractRevision'
          IS DISTINCT FROM v_release_vector ->> 'resolverRevision'
       OR NEW.resolver_replay_context_json -> 'dependencyVector'
            ->> 'simcRuntimeRevision'
          IS DISTINCT FROM v_release_vector ->> 'simcRuntimeRevision'
       OR NEW.resolver_replay_context_json -> 'v2EffectBoundary'
            ->> 'loadoutEffectAuthorityKey'
          IS DISTINCT FROM NEW.loadout_effect_authority_key
    THEN
        RAISE EXCEPTION 'v3 ResolvedLoadout must bind one persisted Runtime Authority Release';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION cache.verify_websim_v3_simulation_snapshot_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, cache, ops, pg_temp
AS $function$
DECLARE
    v_loadout_schema_revision text;
    v_loadout_release_key text;
    v_loadout_context_key text;
    v_loadout_vector jsonb;
    v_release_context_key text;
    v_release_vector jsonb;
BEGIN
    IF NEW.schema_revision <> 'simulation-snapshot-v3' THEN
        RETURN NEW;
    END IF;
    SELECT schema_revision,
           runtime_authority_release_key,
           resolver_context_key,
           dependency_vector_json
    INTO v_loadout_schema_revision,
         v_loadout_release_key,
         v_loadout_context_key,
         v_loadout_vector
    FROM cache.websim_gear_resolved_loadouts
    WHERE resolved_loadout_key = NEW.resolved_loadout_key
    FOR KEY SHARE;
    SELECT release.resolver_context_key,
           document.canonical_json -> 'dependencyVector'
    INTO v_release_context_key, v_release_vector
    FROM ops.websim_exact_runtime_authority_releases AS release
    JOIN cache.websim_canonical_documents AS document
      ON document.content_key = release.runtime_authority_release_key
    WHERE release.runtime_authority_release_key = NEW.runtime_authority_release_key
    FOR KEY SHARE OF release, document;
    IF v_loadout_schema_revision IS DISTINCT FROM 'resolved-loadout-v3'
       OR v_loadout_release_key IS DISTINCT FROM NEW.runtime_authority_release_key
       OR v_loadout_context_key IS DISTINCT FROM NEW.resolver_context_key
       OR v_loadout_vector IS DISTINCT FROM NEW.dependency_vector_json
       OR v_release_context_key IS DISTINCT FROM NEW.resolver_context_key
       OR v_release_vector IS DISTINCT FROM NEW.dependency_vector_json
       OR v_release_vector IS DISTINCT FROM NEW.snapshot_json -> 'dependencyVector'
    THEN
        RAISE EXCEPTION 'v3 SimulationSnapshot must bind its persisted Runtime Authority Release Loadout';
    END IF;
    RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_websim_resolved_loadout_v3_binding
ON cache.websim_gear_resolved_loadouts;
CREATE TRIGGER trg_websim_resolved_loadout_v3_binding
BEFORE INSERT ON cache.websim_gear_resolved_loadouts
FOR EACH ROW EXECUTE FUNCTION cache.verify_websim_v3_resolved_loadout_insert();

DROP TRIGGER IF EXISTS trg_websim_simulation_snapshot_v3_binding
ON cache.websim_simulation_snapshots;
CREATE TRIGGER trg_websim_simulation_snapshot_v3_binding
BEFORE INSERT ON cache.websim_simulation_snapshots
FOR EACH ROW EXECUTE FUNCTION cache.verify_websim_v3_simulation_snapshot_insert();

CREATE OR REPLACE FUNCTION ops.websim_exact_import_request_is_valid(
    p_request_json jsonb
)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $function$
    SELECT
        p_request_json IS NOT NULL
        AND pg_catalog.jsonb_typeof(p_request_json) = 'object'
        AND pg_catalog.jsonb_typeof(p_request_json -> 'exactLoadoutIntent') = 'object'
        AND pg_catalog.jsonb_typeof(p_request_json -> 'dependencyVector') = 'object'
        AND (p_request_json -> 'dependencyVector') ?& ARRAY[
            'seasonRevision', 'gameBuild', 'gearRuleRevision',
            'resolverRevision', 'compilerRevision', 'workerRevision',
            'simcRuntimeRevision', 'effectAuthorityRevision'
        ]
        AND (p_request_json -> 'dependencyVector') - ARRAY[
            'seasonRevision', 'gameBuild', 'gearRuleRevision',
            'resolverRevision', 'compilerRevision', 'workerRevision',
            'simcRuntimeRevision', 'effectAuthorityRevision'
        ] = '{}'::jsonb
        AND (
            (
                p_request_json ->> 'schemaRevision' = 'exact-import-job-request-v1'
                AND p_request_json ?& ARRAY[
                    'schemaRevision', 'exactLoadoutIntent', 'dependencyVector'
                ]
                AND p_request_json - ARRAY[
                    'schemaRevision', 'exactLoadoutIntent', 'dependencyVector'
                ] = '{}'::jsonb
            )
            OR (
                p_request_json ->> 'schemaRevision' = 'exact-import-job-request-v2'
                AND p_request_json ?& ARRAY[
                    'schemaRevision', 'exactLoadoutIntent', 'dependencyVector',
                    'resolvedLoadoutKey', 'simulationSnapshotKey', 'snapshotRowHash'
                ]
                AND p_request_json - ARRAY[
                    'schemaRevision', 'exactLoadoutIntent', 'dependencyVector',
                    'resolvedLoadoutKey', 'simulationSnapshotKey', 'snapshotRowHash'
                ] = '{}'::jsonb
                AND pg_catalog.jsonb_typeof(p_request_json -> 'resolvedLoadoutKey') = 'string'
                AND p_request_json ->> 'resolvedLoadoutKey'
                    ~ '^resolved-loadout-v2:sha256:[0-9a-f]{64}$'
                AND pg_catalog.jsonb_typeof(p_request_json -> 'simulationSnapshotKey') = 'string'
                AND p_request_json ->> 'simulationSnapshotKey'
                    ~ '^simulation-snapshot-v2:sha256:[0-9a-f]{64}$'
                AND pg_catalog.jsonb_typeof(p_request_json -> 'snapshotRowHash') = 'string'
                AND p_request_json ->> 'snapshotRowHash'
                    ~ '^sha256:[0-9a-f]{64}$'
            )
            OR (
                p_request_json ->> 'schemaRevision' = 'exact-import-job-request-v3'
                AND p_request_json ?& ARRAY[
                    'schemaRevision', 'exactLoadoutIntent', 'dependencyVector',
                    'resolvedLoadoutKey', 'simulationSnapshotKey', 'snapshotRowHash',
                    'runtimeAuthorityReleaseKey', 'resolverContextKey'
                ]
                AND p_request_json - ARRAY[
                    'schemaRevision', 'exactLoadoutIntent', 'dependencyVector',
                    'resolvedLoadoutKey', 'simulationSnapshotKey', 'snapshotRowHash',
                    'runtimeAuthorityReleaseKey', 'resolverContextKey'
                ] = '{}'::jsonb
                AND p_request_json ->> 'resolvedLoadoutKey'
                    ~ '^resolved-loadout-v3:sha256:[0-9a-f]{64}$'
                AND p_request_json ->> 'simulationSnapshotKey'
                    ~ '^simulation-snapshot-v3:sha256:[0-9a-f]{64}$'
                AND p_request_json ->> 'snapshotRowHash'
                    ~ '^sha256:[0-9a-f]{64}$'
                AND p_request_json ->> 'runtimeAuthorityReleaseKey'
                    ~ '^exact-runtime-authority-release:sha256:[0-9a-f]{64}$'
                AND p_request_json ->> 'resolverContextKey'
                    ~ '^exact-runtime-resolver-context:sha256:[0-9a-f]{64}$'
                AND NOT EXISTS (
                    SELECT 1
                    FROM pg_catalog.jsonb_each(p_request_json -> 'dependencyVector')
                        AS vector_entry(key, value)
                    WHERE pg_catalog.jsonb_typeof(vector_entry.value) <> 'string'
                       OR vector_entry.value #>> '{}' = ''
                )
            )
        )
        AND NOT pg_catalog.jsonb_path_exists(
            p_request_json,
            '$.** ? (@.type() == "object").keyvalue() ? (@.key == "rawProfile" || @.key == "rawString" || @.key == "playerName" || @.key == "characterName" || @.key == "realm" || @.key == "server")'::pg_catalog.jsonpath
        );
$function$;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0035_websim_exact_runtime_authority_release',
    'Add append-only owner-scoped Exact runtime authority release, resolver context and occurrence index persistence'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = pg_catalog.clock_timestamp();

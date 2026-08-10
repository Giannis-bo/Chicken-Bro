DO $preflight$
BEGIN
    IF pg_catalog.to_regprocedure('pg_catalog.sha256(bytea)') IS NULL THEN
        RAISE EXCEPTION 'PostgreSQL core pg_catalog.sha256(bytea) is required';
    END IF;
END;
$preflight$;

CREATE TABLE app.websim_exact_template_authority_bindings (
    binding_key text PRIMARY KEY
        CHECK (binding_key ~ '^exact-template-authority-binding:sha256:[0-9a-f]{64}$'),
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    template_id uuid NOT NULL REFERENCES app.build_templates(id) ON DELETE CASCADE,
    template_config_hash text NOT NULL
        CHECK (template_config_hash ~ '^[0-9a-f]{64}$'),
    source_payload_hash text NOT NULL
        CHECK (source_payload_hash ~ '^sha256:[0-9a-f]{64}$'),
    selection_signature text NOT NULL
        CHECK (selection_signature ~ '^sha256:[0-9a-f]{64}$'),
    binding_bytes bytea NOT NULL
        CHECK (pg_catalog.octet_length(binding_bytes) BETWEEN 2 AND 131072),
    binding_json jsonb NOT NULL
        CHECK (pg_catalog.jsonb_typeof(binding_json) = 'object'),
    binding_sha256 text NOT NULL
        CHECK (binding_sha256 ~ '^[0-9a-f]{64}$'),
    sealed_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    CHECK (binding_sha256 = pg_catalog.encode(pg_catalog.sha256(binding_bytes), 'hex')),
    CHECK (binding_json = pg_catalog.convert_from(binding_bytes, 'UTF8')::jsonb),
    CHECK (binding_key = 'exact-template-authority-binding:sha256:' || pg_catalog.encode(pg_catalog.sha256(binding_bytes), 'hex')),
    CHECK (
        binding_json ?& ARRAY[
            'schemaRevision', 'source', 'authority', 'exactAuthorityBySlot'
        ]
        AND binding_json - ARRAY[
            'schemaRevision', 'source', 'authority', 'exactAuthorityBySlot'
        ] = '{}'::jsonb
        AND binding_json ->> 'schemaRevision' = 'exact-template-authority-binding-v1'
        AND pg_catalog.jsonb_typeof(binding_json -> 'source') = 'object'
        AND (binding_json -> 'source') ?& ARRAY[
            'ownerKeyHash', 'templateId', 'templateConfigHash',
            'sourcePayloadHash', 'selectionSignature'
        ]
        AND (binding_json -> 'source') - ARRAY[
            'ownerKeyHash', 'templateId', 'templateConfigHash',
            'sourcePayloadHash', 'selectionSignature'
        ] = '{}'::jsonb
        AND pg_catalog.jsonb_typeof(binding_json -> 'authority') = 'object'
        AND (binding_json -> 'authority') ?& ARRAY[
            'gearExactRegistryRevision', 'gearRuleRevision',
            'resolverRevision', 'simcRuntimeRevision',
            'templateAuthorityIdentity', 'templateContentHash'
        ]
        AND (binding_json -> 'authority') - ARRAY[
            'gearExactRegistryRevision', 'gearRuleRevision',
            'resolverRevision', 'simcRuntimeRevision',
            'templateAuthorityIdentity', 'templateContentHash'
        ] = '{}'::jsonb
        AND pg_catalog.jsonb_typeof(binding_json -> 'exactAuthorityBySlot') = 'array'
        AND pg_catalog.jsonb_array_length(binding_json -> 'exactAuthorityBySlot') BETWEEN 1 AND 16
        AND binding_json #>> '{source,ownerKeyHash}' =
            'sha256:' || pg_catalog.encode(
                pg_catalog.sha256(
                    pg_catalog.convert_to(
                        'exact-template-owner-v1:' || user_id::text,
                        'UTF8'
                    )
                ),
                'hex'
            )
        AND binding_json #>> '{source,templateId}' = template_id::text
        AND binding_json #>> '{source,templateConfigHash}' = template_config_hash
        AND binding_json #>> '{source,sourcePayloadHash}' = source_payload_hash
        AND binding_json #>> '{source,selectionSignature}' = selection_signature
    ),
    UNIQUE (
        user_id,
        template_id,
        template_config_hash,
        source_payload_hash,
        selection_signature,
        binding_key
    )
);

CREATE INDEX idx_app_websim_exact_template_binding_source
ON app.websim_exact_template_authority_bindings (
    user_id,
    template_id,
    template_config_hash,
    source_payload_hash,
    selection_signature,
    sealed_at DESC,
    binding_key
);

CREATE TABLE app.websim_exact_template_authority_binding_slots (
    binding_key text NOT NULL
        REFERENCES app.websim_exact_template_authority_bindings(binding_key)
        ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 15),
    slot text NOT NULL CHECK (
        slot IN (
            'head', 'neck', 'shoulder', 'back', 'chest', 'wrist', 'hands',
            'waist', 'legs', 'feet', 'finger1', 'finger2', 'trinket1',
            'trinket2', 'main_hand', 'off_hand'
        )
    ),
    exact_authority_envelope_key text NOT NULL
        REFERENCES cache.websim_exact_authority_bundles(exact_authority_envelope_key)
        ON DELETE RESTRICT,
    sealed_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (binding_key, ordinal),
    UNIQUE (binding_key, slot),
    UNIQUE (binding_key, exact_authority_envelope_key)
);

CREATE OR REPLACE FUNCTION app.verify_websim_exact_template_authority_binding_relations()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, app, cache, pg_temp
AS $function$
DECLARE
    parent_key text := NEW.binding_key;
    payload jsonb;
    expected_count integer;
    actual_count integer;
BEGIN
    SELECT binding_json
    INTO payload
    FROM app.websim_exact_template_authority_bindings
    WHERE binding_key = parent_key
    FOR KEY SHARE;
    IF payload IS NULL THEN
        RETURN NULL;
    END IF;
    IF pg_catalog.jsonb_typeof(payload -> 'exactAuthorityBySlot')
       IS DISTINCT FROM 'array'
    THEN
        RAISE EXCEPTION 'exact template authority binding slot closure is invalid';
    END IF;
    expected_count := pg_catalog.jsonb_array_length(
        payload -> 'exactAuthorityBySlot'
    );
    SELECT pg_catalog.count(*)
    INTO actual_count
    FROM app.websim_exact_template_authority_binding_slots
    WHERE binding_key = parent_key;
    IF expected_count < 1
       OR expected_count > 16
       OR actual_count <> expected_count
       OR EXISTS (
            SELECT 1
            FROM pg_catalog.generate_series(0, expected_count - 1)
                AS wanted(ordinal)
            LEFT JOIN app.websim_exact_template_authority_binding_slots AS relation
                ON relation.binding_key = parent_key
                AND relation.ordinal = wanted.ordinal
            WHERE relation.ordinal IS NULL
               OR relation.slot IS DISTINCT FROM
                  payload -> 'exactAuthorityBySlot' -> wanted.ordinal ->> 'slot'
               OR relation.exact_authority_envelope_key IS DISTINCT FROM
                  payload -> 'exactAuthorityBySlot' -> wanted.ordinal
                      ->> 'exactAuthorityEnvelopeKey'
       )
    THEN
        RAISE EXCEPTION
            'exact template authority binding slots must match canonical binding bytes';
    END IF;
    RETURN NULL;
END;
$function$;

CREATE OR REPLACE FUNCTION app.reject_websim_exact_template_authority_binding_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $function$
BEGIN
    RAISE EXCEPTION 'exact template authority bindings are append-only';
END;
$function$;

CREATE OR REPLACE FUNCTION app.reject_websim_exact_template_authority_binding_delete()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, app, identity, pg_temp
AS $function$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM app.build_templates AS template
        JOIN identity.users AS owner
          ON owner.id = template.user_id
        WHERE template.id = OLD.template_id
          AND template.user_id = OLD.user_id
    ) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'direct deletion of exact template authority bindings is forbidden';
END;
$function$;

CREATE OR REPLACE FUNCTION app.reject_websim_exact_template_authority_binding_slot_delete()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, app, identity, pg_temp
AS $function$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM app.websim_exact_template_authority_bindings AS binding
        JOIN app.build_templates AS template
          ON template.id = binding.template_id
         AND template.user_id = binding.user_id
        JOIN identity.users AS owner
          ON owner.id = binding.user_id
        WHERE binding.binding_key = OLD.binding_key
    ) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'direct deletion of exact template authority binding slots is forbidden';
END;
$function$;

DROP TRIGGER IF EXISTS trg_websim_exact_template_authority_binding_complete
ON app.websim_exact_template_authority_bindings;
CREATE CONSTRAINT TRIGGER trg_websim_exact_template_authority_binding_complete
AFTER INSERT ON app.websim_exact_template_authority_bindings
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION app.verify_websim_exact_template_authority_binding_relations();

DROP TRIGGER IF EXISTS trg_websim_exact_template_authority_binding_slots_complete
ON app.websim_exact_template_authority_binding_slots;
CREATE CONSTRAINT TRIGGER trg_websim_exact_template_authority_binding_slots_complete
AFTER INSERT ON app.websim_exact_template_authority_binding_slots
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION app.verify_websim_exact_template_authority_binding_relations();

DROP TRIGGER IF EXISTS trg_websim_exact_template_authority_binding_immutable
ON app.websim_exact_template_authority_bindings;
CREATE TRIGGER trg_websim_exact_template_authority_binding_immutable
BEFORE UPDATE ON app.websim_exact_template_authority_bindings
FOR EACH ROW
EXECUTE FUNCTION app.reject_websim_exact_template_authority_binding_update();

DROP TRIGGER IF EXISTS trg_websim_exact_template_authority_binding_slots_immutable
ON app.websim_exact_template_authority_binding_slots;
CREATE TRIGGER trg_websim_exact_template_authority_binding_slots_immutable
BEFORE UPDATE ON app.websim_exact_template_authority_binding_slots
FOR EACH ROW
EXECUTE FUNCTION app.reject_websim_exact_template_authority_binding_update();

DROP TRIGGER IF EXISTS trg_websim_exact_template_authority_binding_delete
ON app.websim_exact_template_authority_bindings;
CREATE TRIGGER trg_websim_exact_template_authority_binding_delete
BEFORE DELETE ON app.websim_exact_template_authority_bindings
FOR EACH ROW
EXECUTE FUNCTION app.reject_websim_exact_template_authority_binding_delete();

DROP TRIGGER IF EXISTS trg_websim_exact_template_authority_binding_slots_delete
ON app.websim_exact_template_authority_binding_slots;
CREATE TRIGGER trg_websim_exact_template_authority_binding_slots_delete
BEFORE DELETE ON app.websim_exact_template_authority_binding_slots
FOR EACH ROW
EXECUTE FUNCTION app.reject_websim_exact_template_authority_binding_slot_delete();

DROP TRIGGER IF EXISTS trg_websim_exact_template_authority_binding_truncate
ON app.websim_exact_template_authority_bindings;
CREATE TRIGGER trg_websim_exact_template_authority_binding_truncate
BEFORE TRUNCATE ON app.websim_exact_template_authority_bindings
FOR EACH STATEMENT
EXECUTE FUNCTION app.reject_websim_exact_template_authority_binding_update();

DROP TRIGGER IF EXISTS trg_websim_exact_template_authority_binding_slots_truncate
ON app.websim_exact_template_authority_binding_slots;
CREATE TRIGGER trg_websim_exact_template_authority_binding_slots_truncate
BEFORE TRUNCATE ON app.websim_exact_template_authority_binding_slots
FOR EACH STATEMENT
EXECUTE FUNCTION app.reject_websim_exact_template_authority_binding_update();

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
    ON CONFLICT (binding_key) DO NOTHING;
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

CREATE OR REPLACE FUNCTION ops.websim_exact_template_binding_read(
    p_user_id uuid,
    p_template_id uuid,
    p_template_config_hash text,
    p_source_payload_hash text,
    p_selection_signature text,
    p_gear_exact_registry_revision text,
    p_gear_rule_revision text,
    p_resolver_revision text,
    p_simc_runtime_revision text
)
RETURNS TABLE(binding_key text, binding_bytes bytea)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, app, cache, ops, pg_temp
AS $function$
BEGIN
    IF p_template_config_hash !~ '^[0-9a-f]{64}$'
       OR p_source_payload_hash !~ '^sha256:[0-9a-f]{64}$'
       OR p_selection_signature !~ '^sha256:[0-9a-f]{64}$'
       OR p_gear_exact_registry_revision IS NULL
       OR p_gear_rule_revision IS NULL
       OR p_resolver_revision IS NULL
       OR p_simc_runtime_revision IS NULL
    THEN
        RAISE EXCEPTION 'exact template binding read input is invalid';
    END IF;
    RETURN QUERY
    SELECT
        binding.binding_key,
        binding.binding_bytes
    FROM app.websim_exact_template_authority_bindings AS binding
    JOIN app.build_templates AS template
      ON template.id = binding.template_id
     AND template.user_id = binding.user_id
     AND template.template_type = 'gear'
     AND template.config_hash = binding.template_config_hash
    WHERE binding.user_id = p_user_id
      AND binding.template_id = p_template_id
      AND binding.template_config_hash = p_template_config_hash
      AND binding.source_payload_hash = p_source_payload_hash
      AND binding.selection_signature = p_selection_signature
      AND binding.binding_json #>> '{authority,gearExactRegistryRevision}'
          = p_gear_exact_registry_revision
      AND binding.binding_json #>> '{authority,gearRuleRevision}'
          = p_gear_rule_revision
      AND binding.binding_json #>> '{authority,resolverRevision}'
          = p_resolver_revision
      AND binding.binding_json #>> '{authority,simcRuntimeRevision}'
          = p_simc_runtime_revision
    ORDER BY binding.sealed_at DESC, binding.binding_key;
END;
$function$;

ALTER FUNCTION ops.websim_exact_template_binding_admit(uuid, uuid, text, text, text, bytea)
OWNER TO wow_migrator;
ALTER FUNCTION ops.websim_exact_template_binding_read(uuid, uuid, text, text, text, text, text, text, text)
OWNER TO wow_migrator;

REVOKE ALL ON FUNCTION ops.websim_exact_template_binding_admit(uuid, uuid, text, text, text, bytea)
FROM PUBLIC, wow_app, wow_exact_worker;
REVOKE ALL ON FUNCTION ops.websim_exact_template_binding_read(uuid, uuid, text, text, text, text, text, text, text)
FROM PUBLIC, wow_app, wow_exact_worker;

GRANT SELECT, INSERT, UPDATE, DELETE ON
    app.websim_exact_template_authority_bindings,
    app.websim_exact_template_authority_binding_slots
TO wow_migrator;

REVOKE ALL ON
    app.websim_exact_template_authority_bindings,
    app.websim_exact_template_authority_binding_slots
FROM PUBLIC, wow_app, wow_exact_worker;

GRANT EXECUTE ON FUNCTION
    ops.websim_exact_template_binding_admit(uuid, uuid, text, text, text, bytea),
    ops.websim_exact_template_binding_read(uuid, uuid, text, text, text, text, text, text, text)
TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0033_websim_exact_template_authority_binding',
    'Add owner-scoped canonical remote template to Exact Authority Bundle admission binding'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = pg_catalog.clock_timestamp();

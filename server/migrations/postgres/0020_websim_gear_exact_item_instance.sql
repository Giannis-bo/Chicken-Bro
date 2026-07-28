CREATE TABLE IF NOT EXISTS cache.websim_gear_enhancement_selections (
    enhancement_selection_key text PRIMARY KEY
        CHECK (
            enhancement_selection_key
            ~ '^enhancement-selection:sha256:[0-9a-f]{64}$'
        ),
    schema_revision text NOT NULL,
    selection_json jsonb NOT NULL
        CHECK (
            jsonb_typeof(selection_json) = 'object'
            AND octet_length(selection_json::text) <= 131072
        ),
    row_hash text NOT NULL CHECK (row_hash ~ '^sha256:[0-9a-f]{64}$'),
    sealed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cache.websim_gear_exact_item_instances (
    exact_item_instance_key text PRIMARY KEY
        CHECK (
            exact_item_instance_key
            ~ '^exact-item-instance:sha256:[0-9a-f]{64}$'
        ),
    exact_variant_signature text NOT NULL
        CHECK (
            exact_variant_signature
            ~ '^exact-variant:sha256:[0-9a-f]{64}$'
        ),
    enhancement_selection_key text NOT NULL
        REFERENCES cache.websim_gear_enhancement_selections(
            enhancement_selection_key
        ) ON DELETE RESTRICT,
    schema_revision text NOT NULL,
    item_id text NOT NULL,
    item_level integer NOT NULL CHECK (item_level > 0),
    bonus_ids_json jsonb NOT NULL
        CHECK (
            jsonb_typeof(bonus_ids_json) = 'array'
            AND octet_length(bonus_ids_json::text) <= 131072
        ),
    context_json jsonb NOT NULL
        CHECK (octet_length(context_json::text) <= 131072),
    progression_state_json jsonb NOT NULL
        CHECK (
            jsonb_typeof(progression_state_json) = 'object'
            AND progression_state_json <> '{}'::jsonb
            AND octet_length(progression_state_json::text) <= 131072
        ),
    instance_json jsonb NOT NULL
        CHECK (octet_length(instance_json::text) <= 1048576),
    row_hash text NOT NULL CHECK (row_hash ~ '^sha256:[0-9a-f]{64}$'),
    sealed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_exact_instances_variant
ON cache.websim_gear_exact_item_instances (
    item_id,
    exact_variant_signature,
    enhancement_selection_key
);

CREATE TABLE IF NOT EXISTS cache.websim_gear_exact_item_validations (
    exact_item_instance_key text NOT NULL
        REFERENCES cache.websim_gear_exact_item_instances(
            exact_item_instance_key
        ) ON DELETE RESTRICT,
    catalog_revision text NOT NULL
        REFERENCES cache.websim_gear_catalog_revisions(catalog_revision)
        ON DELETE RESTRICT,
    gear_rule_revision text NOT NULL,
    schema_revision text NOT NULL,
    validation_status text NOT NULL
        CHECK (validation_status IN ('verified', 'partial', 'blocked')),
    slot text NOT NULL,
    source_variant_key text NOT NULL,
    static_facts_json jsonb NOT NULL
        CHECK (
            jsonb_typeof(static_facts_json) = 'object'
            AND octet_length(static_facts_json::text) <= 1048576
        ),
    serializer_input_json jsonb NOT NULL
        CHECK (
            jsonb_typeof(serializer_input_json) = 'object'
            AND octet_length(serializer_input_json::text) <= 1048576
        ),
    validation_json jsonb NOT NULL
        CHECK (octet_length(validation_json::text) <= 1048576),
    row_hash text NOT NULL CHECK (row_hash ~ '^sha256:[0-9a-f]{64}$'),
    sealed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (
        exact_item_instance_key,
        catalog_revision,
        gear_rule_revision
    )
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_exact_validations_catalog
ON cache.websim_gear_exact_item_validations (
    catalog_revision,
    gear_rule_revision,
    validation_status,
    exact_item_instance_key
);

CREATE TABLE IF NOT EXISTS cache.websim_gear_exact_instance_template_refs (
    registry_revision text NOT NULL
        CHECK (
            registry_revision
            ~ '^gear-exact-registry:sha256:[0-9a-f]{64}$'
        ),
    catalog_revision text NOT NULL
        REFERENCES cache.websim_gear_catalog_revisions(catalog_revision)
        ON DELETE RESTRICT,
    season_revision text NOT NULL,
    gear_rule_revision text NOT NULL,
    registry_status text NOT NULL
        CHECK (registry_status IN ('verified', 'partial', 'blocked')),
    registry_summary_json jsonb NOT NULL
        CHECK (
            jsonb_typeof(registry_summary_json) = 'object'
            AND octet_length(registry_summary_json::text) <= 131072
        ),
    registry_problem_codes_json jsonb NOT NULL
        CHECK (
            jsonb_typeof(registry_problem_codes_json) = 'array'
            AND octet_length(registry_problem_codes_json::text) <= 131072
        ),
    template_scope text NOT NULL
        CHECK (template_scope IN ('community', 'personal')),
    template_content_hash text NOT NULL
        CHECK (template_content_hash ~ '^sha256:[0-9a-f]{64}$'),
    slot text NOT NULL,
    item_id text NOT NULL,
    source_variant_key text NOT NULL,
    exact_item_instance_key text
        REFERENCES cache.websim_gear_exact_item_instances(
            exact_item_instance_key
        ) ON DELETE RESTRICT,
    validation_status text NOT NULL
        CHECK (validation_status IN ('verified', 'partial', 'blocked')),
    problem_codes_json jsonb NOT NULL
        CHECK (
            jsonb_typeof(problem_codes_json) = 'array'
            AND octet_length(problem_codes_json::text) <= 131072
        ),
    reference_json jsonb NOT NULL
        CHECK (octet_length(reference_json::text) <= 1048576),
    row_hash text NOT NULL CHECK (row_hash ~ '^sha256:[0-9a-f]{64}$'),
    sealed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (
        registry_revision,
        template_scope,
        template_content_hash,
        slot,
        item_id,
        source_variant_key,
        row_hash
    ),
    FOREIGN KEY (
        exact_item_instance_key,
        catalog_revision,
        gear_rule_revision
    ) REFERENCES cache.websim_gear_exact_item_validations (
        exact_item_instance_key,
        catalog_revision,
        gear_rule_revision
    ) ON DELETE RESTRICT,
    CHECK (
        (validation_status = 'verified' AND exact_item_instance_key IS NOT NULL)
        OR validation_status IN ('partial', 'blocked')
    )
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_exact_template_refs_exact
ON cache.websim_gear_exact_instance_template_refs (
    exact_item_instance_key,
    catalog_revision,
    gear_rule_revision
);

CREATE OR REPLACE FUNCTION cache.reject_websim_gear_exact_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'sealed WebSim exact gear rows are append-only';
END;
$$;

DROP TRIGGER IF EXISTS trg_websim_gear_enhancement_selections_immutable
ON cache.websim_gear_enhancement_selections;
CREATE TRIGGER trg_websim_gear_enhancement_selections_immutable
BEFORE UPDATE OR DELETE ON cache.websim_gear_enhancement_selections
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_gear_exact_mutation();

DROP TRIGGER IF EXISTS trg_websim_gear_exact_item_instances_immutable
ON cache.websim_gear_exact_item_instances;
CREATE TRIGGER trg_websim_gear_exact_item_instances_immutable
BEFORE UPDATE OR DELETE ON cache.websim_gear_exact_item_instances
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_gear_exact_mutation();

DROP TRIGGER IF EXISTS trg_websim_gear_exact_item_validations_immutable
ON cache.websim_gear_exact_item_validations;
CREATE TRIGGER trg_websim_gear_exact_item_validations_immutable
BEFORE UPDATE OR DELETE ON cache.websim_gear_exact_item_validations
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_gear_exact_mutation();

DROP TRIGGER IF EXISTS trg_websim_gear_exact_template_refs_immutable
ON cache.websim_gear_exact_instance_template_refs;
CREATE TRIGGER trg_websim_gear_exact_template_refs_immutable
BEFORE UPDATE OR DELETE ON cache.websim_gear_exact_instance_template_refs
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_gear_exact_mutation();

REVOKE UPDATE, DELETE ON
    cache.websim_gear_enhancement_selections,
    cache.websim_gear_exact_item_instances,
    cache.websim_gear_exact_item_validations,
    cache.websim_gear_exact_instance_template_refs
FROM wow_app;

GRANT SELECT, INSERT ON
    cache.websim_gear_enhancement_selections,
    cache.websim_gear_exact_item_instances,
    cache.websim_gear_exact_item_validations,
    cache.websim_gear_exact_instance_template_refs
TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0020_websim_gear_exact_item_instance',
    'Add dormant immutable EnhancementSelection, ExactItemInstance, Catalog-bound validation, and privacy-safe template reference caches'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

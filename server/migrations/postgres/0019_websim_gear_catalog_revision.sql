CREATE TABLE IF NOT EXISTS cache.websim_gear_catalog_revisions (
    catalog_revision text PRIMARY KEY
        CHECK (catalog_revision ~ '^gear-catalog:sha256:[0-9a-f]{64}$'),
    schema_revision text NOT NULL,
    builder_revision text NOT NULL,
    season_revision text NOT NULL,
    source_gear_release_id text NOT NULL
        REFERENCES cache.websim_release_registry(release_id) ON DELETE RESTRICT,
    source_content_hash text NOT NULL
        CHECK (source_content_hash ~ '^sha256:[0-9a-f]{64}$'),
    dependency_vector_json jsonb NOT NULL
        CHECK (octet_length(dependency_vector_json::text) <= 131072),
    source_summary_json jsonb NOT NULL
        CHECK (octet_length(source_summary_json::text) <= 1048576),
    content_summary_json jsonb NOT NULL
        CHECK (octet_length(content_summary_json::text) <= 32768),
    catalog_json jsonb NOT NULL
        CHECK (octet_length(catalog_json::text) <= 1048576),
    row_hash text NOT NULL CHECK (row_hash ~ '^sha256:[0-9a-f]{64}$'),
    sealed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_catalog_revisions_source
ON cache.websim_gear_catalog_revisions (
    season_revision,
    source_content_hash,
    sealed_at DESC
);

CREATE TABLE IF NOT EXISTS cache.websim_gear_item_definitions (
    catalog_revision text NOT NULL
        REFERENCES cache.websim_gear_catalog_revisions(catalog_revision)
        ON DELETE RESTRICT,
    item_id text NOT NULL,
    name text NOT NULL DEFAULT '',
    slot text NOT NULL,
    item_level integer NOT NULL DEFAULT 0 CHECK (item_level >= 0),
    source_status text NOT NULL CHECK (source_status = 'verified'),
    definition_json jsonb NOT NULL
        CHECK (octet_length(definition_json::text) <= 1048576),
    row_hash text NOT NULL CHECK (row_hash ~ '^sha256:[0-9a-f]{64}$'),
    PRIMARY KEY (catalog_revision, item_id)
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_item_definitions_slot
ON cache.websim_gear_item_definitions (catalog_revision, slot, item_id);

CREATE TABLE IF NOT EXISTS cache.websim_gear_browse_variants (
    catalog_revision text NOT NULL,
    browse_variant_key text NOT NULL
        CHECK (browse_variant_key ~ '^browse-variant:sha256:[0-9a-f]{64}$'),
    item_id text NOT NULL,
    progression_kind text NOT NULL
        CHECK (progression_kind IN ('upgrade_track', 'crafted_quality', 'ascendant')),
    progression_key text NOT NULL
        CHECK (progression_key ~ '^progression:sha256:[0-9a-f]{64}$'),
    source_variant_keys_json jsonb NOT NULL
        CHECK (
            jsonb_typeof(source_variant_keys_json) = 'array'
            AND jsonb_array_length(source_variant_keys_json) >= 1
            AND octet_length(source_variant_keys_json::text) <= 1048576
        ),
    item_level integer NOT NULL CHECK (item_level > 0),
    bonus_ids_json jsonb NOT NULL
        CHECK (
            jsonb_typeof(bonus_ids_json) = 'array'
            AND octet_length(bonus_ids_json::text) <= 131072
        ),
    static_facts_json jsonb NOT NULL
        CHECK (
            jsonb_typeof(static_facts_json) = 'object'
            AND static_facts_json <> '{}'::jsonb
            AND octet_length(static_facts_json::text) <= 1048576
        ),
    variant_json jsonb NOT NULL
        CHECK (octet_length(variant_json::text) <= 1048576),
    row_hash text NOT NULL CHECK (row_hash ~ '^sha256:[0-9a-f]{64}$'),
    PRIMARY KEY (catalog_revision, browse_variant_key),
    UNIQUE (catalog_revision, item_id, progression_key),
    FOREIGN KEY (catalog_revision, item_id)
        REFERENCES cache.websim_gear_item_definitions(catalog_revision, item_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_browse_variants_item
ON cache.websim_gear_browse_variants (
    catalog_revision,
    item_id,
    progression_kind
);

CREATE OR REPLACE FUNCTION cache.reject_websim_gear_catalog_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'sealed WebSim Gear Catalog rows are append-only';
END;
$$;

DROP TRIGGER IF EXISTS trg_websim_gear_catalog_revisions_immutable
ON cache.websim_gear_catalog_revisions;
CREATE TRIGGER trg_websim_gear_catalog_revisions_immutable
BEFORE UPDATE OR DELETE ON cache.websim_gear_catalog_revisions
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_gear_catalog_mutation();

DROP TRIGGER IF EXISTS trg_websim_gear_item_definitions_immutable
ON cache.websim_gear_item_definitions;
CREATE TRIGGER trg_websim_gear_item_definitions_immutable
BEFORE UPDATE OR DELETE ON cache.websim_gear_item_definitions
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_gear_catalog_mutation();

DROP TRIGGER IF EXISTS trg_websim_gear_browse_variants_immutable
ON cache.websim_gear_browse_variants;
CREATE TRIGGER trg_websim_gear_browse_variants_immutable
BEFORE UPDATE OR DELETE ON cache.websim_gear_browse_variants
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_gear_catalog_mutation();

REVOKE UPDATE, DELETE ON
    cache.websim_gear_catalog_revisions,
    cache.websim_gear_item_definitions,
    cache.websim_gear_browse_variants
FROM wow_app;

GRANT SELECT, INSERT ON
    cache.websim_gear_catalog_revisions,
    cache.websim_gear_item_definitions,
    cache.websim_gear_browse_variants
TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0019_websim_gear_catalog_revision',
    'Add dormant immutable Gear Catalog revisions, ItemDefinition membership, and canonical BrowseVariant membership without an active pointer'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

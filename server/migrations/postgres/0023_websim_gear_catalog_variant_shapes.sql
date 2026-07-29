ALTER TABLE cache.websim_gear_browse_variants
    DROP CONSTRAINT IF EXISTS
    websim_gear_browse_variants_catalog_revision_item_id_progre_key;

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_browse_variants_progression
ON cache.websim_gear_browse_variants (
    catalog_revision,
    item_id,
    progression_key,
    browse_variant_key
);

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0023_websim_gear_catalog_variant_shapes',
    'Allow immutable Catalog v2 to retain multiple exact static and bonus shapes within one governed item progression'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

ALTER TABLE cache.websim_gear_sources
    ADD COLUMN IF NOT EXISTS source_label text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS instance_id text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS encounter_id text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS difficulty_key text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS season_revision text NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_sources_item
ON cache.websim_gear_sources (item_id, source_type, difficulty_key);

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_sources_season
ON cache.websim_gear_sources (season_revision);

ALTER TABLE cache.websim_gear_variants
    ADD COLUMN IF NOT EXISTS slot text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS label text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS source_type text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS difficulty_key text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS item_level integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS simc_options_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'blocked',
    ADD COLUMN IF NOT EXISTS blockers_json jsonb NOT NULL DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_variants_item
ON cache.websim_gear_variants (item_id, slot, status);

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_variants_source
ON cache.websim_gear_variants (source_type, difficulty_key);

ALTER TABLE cache.websim_gear_mod_options
    ALTER COLUMN variant_id DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS option_type text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS name text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS applicable_slots_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS simc_options_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'blocked';

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_mod_options_type
ON cache.websim_gear_mod_options (option_type, status);

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0007_websim_gear_catalog_cache',
    'Extend PostgreSQL WebSim gear catalog cache tables for sources, variants, and global mod options'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

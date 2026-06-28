ALTER TABLE cache.websim_talents
    ADD COLUMN IF NOT EXISTS tree_id text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS row_index integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS col_index integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS spell_id integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS name text NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_cache_websim_talents_lookup
ON cache.websim_talents (class_key, spec_key, spell_id);

CREATE TABLE IF NOT EXISTS cache.websim_profile_presets (
    id text PRIMARY KEY,
    class_key text NOT NULL,
    spec_key text NOT NULL,
    name text NOT NULL DEFAULT '',
    profile text NOT NULL DEFAULT '',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_profile_presets_spec
ON cache.websim_profile_presets (class_key, spec_key, name);

CREATE TABLE IF NOT EXISTS cache.websim_spell_details (
    id text PRIMARY KEY,
    spell_id integer NOT NULL,
    name text NOT NULL DEFAULT '',
    description text NOT NULL DEFAULT '',
    icon_url text NOT NULL DEFAULT '',
    locale text NOT NULL DEFAULT 'zh_CN',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_spell_details_spell
ON cache.websim_spell_details (spell_id, locale);

ALTER TABLE cache.websim_community_talent_templates
    ADD COLUMN IF NOT EXISTS hero_key text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS scenario_key text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS name text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS flow_label text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS source_name text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS source_url text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS raw_import_code text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS websim_export_code text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS talent_state_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS sample_count integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_key_level integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS analysis_window text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS source_status text NOT NULL DEFAULT 'blocked',
    ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'blocked',
    ADD COLUMN IF NOT EXISTS expires_at timestamptz,
    ADD COLUMN IF NOT EXISTS signature text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS source_refs_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS scan_run_id text NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_cache_websim_community_talent_templates_selection
ON cache.websim_community_talent_templates (class_key, spec_key, hero_key, scenario_key, status);

CREATE INDEX IF NOT EXISTS idx_cache_websim_community_talent_templates_signature
ON cache.websim_community_talent_templates (class_key, spec_key, hero_key, signature, status);

GRANT SELECT, INSERT, UPDATE, DELETE ON
    cache.websim_profile_presets,
    cache.websim_spell_details
TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0008_websim_talent_cache',
    'Extend PostgreSQL WebSim talent cache tables for nodes, spell details, presets, and community templates'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

CREATE TABLE IF NOT EXISTS cache.websim_community_gear_templates (
    id text PRIMARY KEY,
    class_key text NOT NULL,
    spec_key text NOT NULL,
    name text NOT NULL DEFAULT '',
    source_key text NOT NULL DEFAULT '',
    source_name text NOT NULL DEFAULT '',
    source_url text NOT NULL DEFAULT '',
    source_status text NOT NULL DEFAULT 'blocked',
    status text NOT NULL DEFAULT 'blocked',
    signature text NOT NULL DEFAULT '',
    source_refs_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    gear_items_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    raw_string text NOT NULL DEFAULT '',
    ready_slot_count integer NOT NULL DEFAULT 0,
    missing_slots_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    analysis_window text NOT NULL DEFAULT '',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz,
    scan_run_id text NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_community_gear_templates_lookup
ON cache.websim_community_gear_templates (class_key, spec_key, status, signature);

CREATE INDEX IF NOT EXISTS idx_cache_websim_community_gear_templates_source
ON cache.websim_community_gear_templates (source_key, source_status, status);

GRANT SELECT, INSERT, UPDATE, DELETE ON cache.websim_community_gear_templates TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0011_websim_gear_template_cache',
    'Add PostgreSQL WebSim community and default gear template cache table'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

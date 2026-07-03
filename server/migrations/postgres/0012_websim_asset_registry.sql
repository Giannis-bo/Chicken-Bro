CREATE TABLE IF NOT EXISTS cache.websim_asset_registry (
    id text PRIMARY KEY,
    entity_type text NOT NULL,
    entity_id text NOT NULL,
    context_key text NOT NULL,
    asset_type text NOT NULL DEFAULT 'icon',
    icon_url text NOT NULL DEFAULT '',
    resolution_tier text NOT NULL DEFAULT '',
    source text NOT NULL DEFAULT 'unknown',
    status text NOT NULL DEFAULT 'missing',
    semantic_tags_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    usage_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    fallback_text text NOT NULL DEFAULT '?',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_asset_registry_entity
ON cache.websim_asset_registry (entity_type, entity_id, context_key);

CREATE INDEX IF NOT EXISTS idx_cache_websim_asset_registry_status
ON cache.websim_asset_registry (status, source);

GRANT SELECT, INSERT, UPDATE, DELETE ON cache.websim_asset_registry TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0012_websim_asset_registry',
    'Add PostgreSQL WebSim asset registry cache table for PG-only runtime'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

ALTER TABLE content.articles
ADD COLUMN IF NOT EXISTS original_title text NOT NULL DEFAULT '',
ADD COLUMN IF NOT EXISTS translation_status text NOT NULL DEFAULT '',
ADD COLUMN IF NOT EXISTS content_status text NOT NULL DEFAULT 'ready',
ADD COLUMN IF NOT EXISTS tag_items_json jsonb NOT NULL DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS blocked_reason text NOT NULL DEFAULT '',
ADD COLUMN IF NOT EXISTS source_key text NOT NULL DEFAULT '',
ADD COLUMN IF NOT EXISTS source_tier text NOT NULL DEFAULT '',
ADD COLUMN IF NOT EXISTS license_status text NOT NULL DEFAULT '',
ADD COLUMN IF NOT EXISTS verification_status text NOT NULL DEFAULT '',
ADD COLUMN IF NOT EXISTS source_badges_json jsonb NOT NULL DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS body_blocks_zh_json jsonb NOT NULL DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS canonical_topic_id text NOT NULL DEFAULT '',
ADD COLUMN IF NOT EXISTS reading_meta_json jsonb NOT NULL DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS translation_fidelity text NOT NULL DEFAULT '',
ADD COLUMN IF NOT EXISTS payload_json jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS content.discovery_queue (
    id text PRIMARY KEY,
    canonical_topic_id text NOT NULL DEFAULT '',
    source_key text NOT NULL DEFAULT '',
    source_name text NOT NULL DEFAULT '',
    source_tier text NOT NULL DEFAULT '',
    source_url text NOT NULL DEFAULT '',
    original_title text NOT NULL DEFAULT '',
    published_at timestamptz,
    status text NOT NULL DEFAULT 'queued',
    attempts integer NOT NULL DEFAULT 0,
    last_error text NOT NULL DEFAULT '',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    discovered_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_content_discovery_queue_status_updated
ON content.discovery_queue (status, updated_at);

CREATE INDEX IF NOT EXISTS idx_content_discovery_queue_source_status
ON content.discovery_queue (source_key, status);

CREATE TABLE IF NOT EXISTS content.refresh_runs (
    id bigserial PRIMARY KEY,
    refresh_mode text NOT NULL,
    refreshed_at timestamptz NOT NULL,
    accepted_count integer NOT NULL DEFAULT 0,
    rejected_count integer NOT NULL DEFAULT 0,
    message_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_content_refresh_runs_refreshed_at
ON content.refresh_runs (refreshed_at DESC);

GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA content TO wow_app;

ALTER DEFAULT PRIVILEGES FOR ROLE wow_migrator IN SCHEMA content
GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0005_content_runtime_fields',
    'Add PostgreSQL content runtime article fields, discovery queue, and refresh runs'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

CREATE TABLE IF NOT EXISTS cache.websim_season_state (
    key text PRIMARY KEY,
    season_id text NOT NULL DEFAULT '',
    season_label text NOT NULL DEFAULT '',
    season_revision text NOT NULL DEFAULT '',
    locale text NOT NULL DEFAULT 'zh_CN',
    data_status text NOT NULL DEFAULT 'blocked',
    verified_at timestamptz,
    expires_at timestamptz,
    source_refs_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    active boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_season_state_active
ON cache.websim_season_state (active, data_status, expires_at);

CREATE TABLE IF NOT EXISTS cache.websim_season_dungeons (
    id text PRIMARY KEY,
    season_id text NOT NULL DEFAULT '',
    season_revision text NOT NULL DEFAULT '',
    dungeon_id text NOT NULL DEFAULT '',
    instance_id text NOT NULL DEFAULT '',
    name text NOT NULL DEFAULT '',
    short_name text NOT NULL DEFAULT '',
    timer_seconds integer NOT NULL DEFAULT 0,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_season_dungeons_revision
ON cache.websim_season_dungeons (season_revision, name);

CREATE TABLE IF NOT EXISTS cache.websim_instances (
    id text PRIMARY KEY,
    name text NOT NULL DEFAULT '',
    category text NOT NULL DEFAULT '',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_instances_category_name
ON cache.websim_instances (category, name);

CREATE TABLE IF NOT EXISTS cache.websim_encounters (
    id text PRIMARY KEY,
    instance_id text NOT NULL REFERENCES cache.websim_instances(id) ON DELETE CASCADE,
    name text NOT NULL DEFAULT '',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_encounters_instance
ON cache.websim_encounters (instance_id, name);

CREATE TABLE IF NOT EXISTS cache.websim_loot (
    id text PRIMARY KEY,
    instance_id text REFERENCES cache.websim_instances(id) ON DELETE SET NULL,
    encounter_id text REFERENCES cache.websim_encounters(id) ON DELETE SET NULL,
    item_id text REFERENCES cache.websim_items(id) ON DELETE SET NULL,
    name text NOT NULL DEFAULT '',
    slot text NOT NULL DEFAULT '',
    quality text NOT NULL DEFAULT '',
    icon_url text NOT NULL DEFAULT '',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_loot_instance_encounter
ON cache.websim_loot (instance_id, encounter_id);

CREATE INDEX IF NOT EXISTS idx_cache_websim_loot_item
ON cache.websim_loot (item_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON
    cache.websim_season_state,
    cache.websim_season_dungeons,
    cache.websim_instances,
    cache.websim_encounters,
    cache.websim_loot
TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0006_websim_season_loot_cache',
    'Add PostgreSQL WebSim season, journal instance, encounter, and loot cache read-model tables'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

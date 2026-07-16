CREATE TABLE IF NOT EXISTS cache.websim_release_registry (
    release_id text PRIMARY KEY,
    release_kind text NOT NULL CHECK (release_kind IN ('gear', 'community')),
    season_revision text NOT NULL,
    schema_revision text NOT NULL,
    content_hash text NOT NULL,
    parent_release_id text REFERENCES cache.websim_release_registry(release_id) ON DELETE RESTRICT,
    validated_against_release_id text REFERENCES cache.websim_release_registry(release_id) ON DELETE RESTRICT,
    release_status text NOT NULL CHECK (release_status IN ('validated', 'degraded', 'blocked')),
    dependency_vector_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    gate_result_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    content_summary_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    sealed_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (release_kind = 'gear' AND validated_against_release_id IS NULL)
        OR (release_kind = 'community' AND validated_against_release_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_release_registry_content
ON cache.websim_release_registry (release_kind, content_hash, season_revision);

CREATE TABLE IF NOT EXISTS cache.websim_gear_release_items (
    release_id text NOT NULL REFERENCES cache.websim_release_registry(release_id) ON DELETE RESTRICT,
    item_id text NOT NULL,
    name text NOT NULL DEFAULT '',
    slot text NOT NULL DEFAULT '',
    item_level integer,
    source_status text NOT NULL DEFAULT 'unknown',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_updated_at timestamptz,
    row_hash text NOT NULL,
    PRIMARY KEY (release_id, item_id)
);

CREATE TABLE IF NOT EXISTS cache.websim_gear_release_sources (
    release_id text NOT NULL,
    source_id text NOT NULL,
    item_id text NOT NULL,
    source_type text NOT NULL,
    source_key text NOT NULL DEFAULT '',
    source_label text NOT NULL DEFAULT '',
    instance_id text NOT NULL DEFAULT '',
    encounter_id text NOT NULL DEFAULT '',
    difficulty_key text NOT NULL DEFAULT '',
    season_revision text NOT NULL DEFAULT '',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_updated_at timestamptz,
    row_hash text NOT NULL,
    PRIMARY KEY (release_id, source_id),
    FOREIGN KEY (release_id, item_id)
        REFERENCES cache.websim_gear_release_items(release_id, item_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_release_sources_item
ON cache.websim_gear_release_sources (release_id, item_id, source_type);

CREATE TABLE IF NOT EXISTS cache.websim_gear_release_variants (
    release_id text NOT NULL,
    variant_id text NOT NULL,
    item_id text NOT NULL,
    variant_key text NOT NULL,
    slot text NOT NULL DEFAULT '',
    label text NOT NULL DEFAULT '',
    source_type text NOT NULL DEFAULT '',
    difficulty_key text NOT NULL DEFAULT '',
    item_level integer NOT NULL DEFAULT 0,
    simc_options_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'blocked',
    blockers_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_updated_at timestamptz,
    row_hash text NOT NULL,
    PRIMARY KEY (release_id, variant_id),
    UNIQUE (release_id, item_id, variant_key),
    FOREIGN KEY (release_id, item_id)
        REFERENCES cache.websim_gear_release_items(release_id, item_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_release_variants_item
ON cache.websim_gear_release_variants (release_id, item_id, status);

CREATE TABLE IF NOT EXISTS cache.websim_gear_release_mod_options (
    release_id text NOT NULL REFERENCES cache.websim_release_registry(release_id) ON DELETE RESTRICT,
    option_id text NOT NULL,
    variant_id text,
    option_key text NOT NULL,
    option_type text NOT NULL DEFAULT '',
    name text NOT NULL DEFAULT '',
    applicable_slots_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    simc_options_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'blocked',
    is_visible boolean NOT NULL DEFAULT false,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_updated_at timestamptz,
    row_hash text NOT NULL,
    PRIMARY KEY (release_id, option_id),
    UNIQUE (release_id, option_key),
    FOREIGN KEY (release_id, variant_id)
        REFERENCES cache.websim_gear_release_variants(release_id, variant_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_release_options_type
ON cache.websim_gear_release_mod_options (release_id, option_type, status, is_visible);

CREATE TABLE IF NOT EXISTS cache.websim_community_release_templates (
    release_id text NOT NULL REFERENCES cache.websim_release_registry(release_id) ON DELETE RESTRICT,
    template_id text NOT NULL,
    class_key text NOT NULL,
    spec_key text NOT NULL,
    role text NOT NULL CHECK (role IN ('winner', 'standby', 'rejected')),
    election_rank integer NOT NULL DEFAULT 0,
    source_key text NOT NULL DEFAULT '',
    source_url text NOT NULL DEFAULT '',
    source_status text NOT NULL DEFAULT '',
    sample_count integer NOT NULL DEFAULT 0,
    profile_hash text NOT NULL DEFAULT '',
    gear_hash text NOT NULL DEFAULT '',
    selection_intent_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    resolved_gear_signature text NOT NULL DEFAULT '',
    semantic_gear_signature text NOT NULL DEFAULT '',
    dependency_vector_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    evidence_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    problems_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_updated_at timestamptz,
    expires_at timestamptz,
    row_hash text NOT NULL,
    PRIMARY KEY (release_id, template_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cache_websim_community_release_one_winner
ON cache.websim_community_release_templates (release_id, class_key, spec_key)
WHERE role = 'winner';

CREATE INDEX IF NOT EXISTS idx_cache_websim_community_release_templates_lookup
ON cache.websim_community_release_templates (release_id, class_key, spec_key, role);

CREATE TABLE IF NOT EXISTS cache.websim_season_manifests (
    manifest_revision text PRIMARY KEY,
    schema_revision text NOT NULL,
    season_revision text NOT NULL,
    gear_release_id text NOT NULL REFERENCES cache.websim_release_registry(release_id) ON DELETE RESTRICT,
    community_release_id text REFERENCES cache.websim_release_registry(release_id) ON DELETE RESTRICT,
    talent_catalog_revision text NOT NULL,
    dependency_vector_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    rollback_manifest_revision text REFERENCES cache.websim_season_manifests(manifest_revision) ON DELETE RESTRICT,
    manifest_hash text NOT NULL,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cache.websim_active_manifest_pointer (
    environment text PRIMARY KEY CHECK (environment = 'retail'),
    manifest_revision text NOT NULL REFERENCES cache.websim_season_manifests(manifest_revision) ON DELETE RESTRICT,
    generation bigint NOT NULL CHECK (generation >= 0),
    rollback_manifest_revision text REFERENCES cache.websim_season_manifests(manifest_revision) ON DELETE RESTRICT,
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS cache.websim_release_events (
    event_id bigserial PRIMARY KEY,
    release_id text REFERENCES cache.websim_release_registry(release_id) ON DELETE RESTRICT,
    manifest_revision text REFERENCES cache.websim_season_manifests(manifest_revision) ON DELETE RESTRICT,
    event_type text NOT NULL,
    event_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_release_events_release
ON cache.websim_release_events (release_id, created_at DESC);

CREATE OR REPLACE FUNCTION cache.reject_websim_release_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'sealed WebSim release rows are append-only';
END;
$$;

DROP TRIGGER IF EXISTS trg_websim_release_registry_immutable ON cache.websim_release_registry;
CREATE TRIGGER trg_websim_release_registry_immutable
BEFORE UPDATE OR DELETE ON cache.websim_release_registry
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_release_mutation();

DROP TRIGGER IF EXISTS trg_websim_gear_release_items_immutable ON cache.websim_gear_release_items;
CREATE TRIGGER trg_websim_gear_release_items_immutable
BEFORE UPDATE OR DELETE ON cache.websim_gear_release_items
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_release_mutation();

DROP TRIGGER IF EXISTS trg_websim_gear_release_sources_immutable ON cache.websim_gear_release_sources;
CREATE TRIGGER trg_websim_gear_release_sources_immutable
BEFORE UPDATE OR DELETE ON cache.websim_gear_release_sources
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_release_mutation();

DROP TRIGGER IF EXISTS trg_websim_gear_release_variants_immutable ON cache.websim_gear_release_variants;
CREATE TRIGGER trg_websim_gear_release_variants_immutable
BEFORE UPDATE OR DELETE ON cache.websim_gear_release_variants
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_release_mutation();

DROP TRIGGER IF EXISTS trg_websim_gear_release_mod_options_immutable ON cache.websim_gear_release_mod_options;
CREATE TRIGGER trg_websim_gear_release_mod_options_immutable
BEFORE UPDATE OR DELETE ON cache.websim_gear_release_mod_options
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_release_mutation();

DROP TRIGGER IF EXISTS trg_websim_community_release_templates_immutable ON cache.websim_community_release_templates;
CREATE TRIGGER trg_websim_community_release_templates_immutable
BEFORE UPDATE OR DELETE ON cache.websim_community_release_templates
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_release_mutation();

DROP TRIGGER IF EXISTS trg_websim_season_manifests_immutable ON cache.websim_season_manifests;
CREATE TRIGGER trg_websim_season_manifests_immutable
BEFORE UPDATE OR DELETE ON cache.websim_season_manifests
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_release_mutation();

DROP TRIGGER IF EXISTS trg_websim_release_events_immutable ON cache.websim_release_events;
CREATE TRIGGER trg_websim_release_events_immutable
BEFORE UPDATE OR DELETE ON cache.websim_release_events
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_release_mutation();

REVOKE UPDATE, DELETE ON
    cache.websim_release_registry,
    cache.websim_gear_release_items,
    cache.websim_gear_release_sources,
    cache.websim_gear_release_variants,
    cache.websim_gear_release_mod_options,
    cache.websim_community_release_templates,
    cache.websim_season_manifests,
    cache.websim_release_events
FROM wow_app;

GRANT SELECT, INSERT ON
    cache.websim_release_registry,
    cache.websim_gear_release_items,
    cache.websim_gear_release_sources,
    cache.websim_gear_release_variants,
    cache.websim_gear_release_mod_options,
    cache.websim_community_release_templates,
    cache.websim_season_manifests,
    cache.websim_release_events
TO wow_app;

REVOKE DELETE ON cache.websim_active_manifest_pointer FROM wow_app;
GRANT SELECT, INSERT, UPDATE ON cache.websim_active_manifest_pointer TO wow_app;
GRANT USAGE, SELECT ON SEQUENCE cache.websim_release_events_event_id_seq TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0013_websim_release_train',
    'Add immutable Gear and Community Releases, Season Manifests, active retail pointer, and append-only release events'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

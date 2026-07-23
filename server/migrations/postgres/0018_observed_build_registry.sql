CREATE TABLE IF NOT EXISTS cache.observed_build_snapshots (
    snapshot_id text PRIMARY KEY
        CHECK (snapshot_id ~ '^observed-build:sha256:[0-9a-f]{64}$'),
    schema_revision text NOT NULL,
    slot_key text NOT NULL,
    class_key text NOT NULL,
    spec_key text NOT NULL,
    hero_key text NOT NULL,
    scenario_key text NOT NULL,
    source_key text NOT NULL CHECK (source_key = 'raiderio'),
    source_identity text NOT NULL,
    profile_url text NOT NULL,
    profile_hash text NOT NULL CHECK (profile_hash ~ '^sha256:[0-9a-f]{64}$'),
    talent_hash text NOT NULL CHECK (talent_hash ~ '^sha256:[0-9a-f]{64}$'),
    gear_hash text NOT NULL CHECK (gear_hash ~ '^sha256:[0-9a-f]{64}$'),
    source_revision text NOT NULL,
    snapshot_json jsonb NOT NULL
        CHECK (octet_length(snapshot_json::text) <= 1048576),
    row_hash text NOT NULL CHECK (row_hash ~ '^sha256:[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (snapshot_id, slot_key)
);

CREATE INDEX IF NOT EXISTS idx_cache_observed_build_snapshots_slot
ON cache.observed_build_snapshots (slot_key, created_at DESC);

CREATE TABLE IF NOT EXISTS ops.observed_build_snapshot_checks (
    check_id bigserial PRIMARY KEY,
    run_id text NOT NULL,
    schema_revision text NOT NULL,
    slot_key text NOT NULL,
    class_key text NOT NULL,
    spec_key text NOT NULL,
    hero_key text NOT NULL,
    scenario_key text NOT NULL,
    snapshot_id text,
    status text NOT NULL
        CHECK (status IN ('captured', 'changed', 'unchanged', 'failed')),
    checked_at timestamptz NOT NULL,
    problem_json jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (octet_length(problem_json::text) <= 32768),
    check_json jsonb NOT NULL
        CHECK (octet_length(check_json::text) <= 131072),
    row_hash text NOT NULL CHECK (row_hash ~ '^sha256:[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (status = 'failed' AND snapshot_id IS NULL AND problem_json <> '{}'::jsonb)
        OR (status <> 'failed' AND snapshot_id IS NOT NULL AND problem_json = '{}'::jsonb)
    ),
    FOREIGN KEY (snapshot_id, slot_key)
        REFERENCES cache.observed_build_snapshots(snapshot_id, slot_key)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_ops_observed_build_snapshot_checks_run
ON ops.observed_build_snapshot_checks (run_id, slot_key, check_id);

CREATE INDEX IF NOT EXISTS idx_ops_observed_build_snapshot_checks_slot
ON ops.observed_build_snapshot_checks (slot_key, checked_at DESC);

CREATE TABLE IF NOT EXISTS cache.observed_build_projections (
    projection_id text PRIMARY KEY
        CHECK (projection_id ~ '^build-projection:sha256:[0-9a-f]{64}$'),
    snapshot_id text NOT NULL,
    schema_revision text NOT NULL,
    slot_key text NOT NULL,
    dependency_hash text NOT NULL CHECK (dependency_hash ~ '^sha256:[0-9a-f]{64}$'),
    dependency_vector_json jsonb NOT NULL
        CHECK (octet_length(dependency_vector_json::text) <= 65536),
    status text NOT NULL CHECK (status IN ('verified', 'blocked')),
    importable boolean NOT NULL,
    projection_json jsonb NOT NULL
        CHECK (octet_length(projection_json::text) <= 1048576),
    row_hash text NOT NULL CHECK (row_hash ~ '^sha256:[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (status = 'verified' AND importable)
        OR (status = 'blocked' AND NOT importable)
    ),
    UNIQUE (projection_id, snapshot_id, slot_key),
    FOREIGN KEY (snapshot_id, slot_key)
        REFERENCES cache.observed_build_snapshots(snapshot_id, slot_key)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_cache_observed_build_projections_snapshot
ON cache.observed_build_projections (snapshot_id, dependency_hash);

CREATE INDEX IF NOT EXISTS idx_cache_observed_build_projections_slot
ON cache.observed_build_projections (slot_key, created_at DESC);

CREATE TABLE IF NOT EXISTS cache.observed_build_template_sets (
    template_set_id text PRIMARY KEY
        CHECK (template_set_id ~ '^template-set:sha256:[0-9a-f]{64}$'),
    schema_revision text NOT NULL,
    content_hash text NOT NULL CHECK (content_hash ~ '^sha256:[0-9a-f]{64}$'),
    dependency_hash text NOT NULL CHECK (dependency_hash ~ '^sha256:[0-9a-f]{64}$'),
    dependency_vector_json jsonb NOT NULL
        CHECK (octet_length(dependency_vector_json::text) <= 65536),
    source_run_id text NOT NULL,
    counts_json jsonb NOT NULL
        CHECK (octet_length(counts_json::text) <= 4096),
    template_set_json jsonb NOT NULL
        CHECK (octet_length(template_set_json::text) <= 8388608),
    row_hash text NOT NULL CHECK (row_hash ~ '^sha256:[0-9a-f]{64}$'),
    sealed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_observed_build_template_sets_sealed
ON cache.observed_build_template_sets (sealed_at DESC);

CREATE TABLE IF NOT EXISTS cache.observed_build_template_set_slots (
    template_set_id text NOT NULL
        REFERENCES cache.observed_build_template_sets(template_set_id) ON DELETE RESTRICT,
    slot_key text NOT NULL,
    class_key text NOT NULL,
    spec_key text NOT NULL,
    hero_key text NOT NULL,
    scenario_key text NOT NULL,
    status text NOT NULL
        CHECK (status IN ('verified', 'stale_lkg', 'pending_collection')),
    snapshot_id text
        REFERENCES cache.observed_build_snapshots(snapshot_id) ON DELETE RESTRICT,
    projection_id text
        REFERENCES cache.observed_build_projections(projection_id) ON DELETE RESTRICT,
    problem_json jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (octet_length(problem_json::text) <= 32768),
    slot_json jsonb NOT NULL
        CHECK (octet_length(slot_json::text) <= 131072),
    row_hash text NOT NULL CHECK (row_hash ~ '^sha256:[0-9a-f]{64}$'),
    PRIMARY KEY (template_set_id, slot_key),
    CHECK (
        (
            status IN ('verified', 'stale_lkg')
            AND snapshot_id IS NOT NULL
            AND projection_id IS NOT NULL
        )
        OR (
            status = 'pending_collection'
            AND snapshot_id IS NULL
            AND projection_id IS NULL
        )
    ),
    FOREIGN KEY (projection_id, snapshot_id, slot_key)
        REFERENCES cache.observed_build_projections(projection_id, snapshot_id, slot_key)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_cache_observed_build_template_set_slots_projection
ON cache.observed_build_template_set_slots (projection_id);

CREATE TABLE IF NOT EXISTS cache.observed_build_template_set_pointer (
    scope text PRIMARY KEY CHECK (length(scope) BETWEEN 1 AND 80),
    generation bigint NOT NULL CHECK (generation >= 1),
    active_template_set_id text NOT NULL
        REFERENCES cache.observed_build_template_sets(template_set_id) ON DELETE RESTRICT,
    rollback_template_set_id text
        REFERENCES cache.observed_build_template_sets(template_set_id) ON DELETE RESTRICT,
    updated_by text NOT NULL CHECK (length(updated_by) BETWEEN 1 AND 160),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (rollback_template_set_id IS NULL OR rollback_template_set_id <> active_template_set_id)
);

CREATE OR REPLACE FUNCTION cache.reject_observed_build_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'sealed observed build rows are append-only';
END;
$$;

DROP TRIGGER IF EXISTS trg_observed_build_snapshots_immutable
ON cache.observed_build_snapshots;
CREATE TRIGGER trg_observed_build_snapshots_immutable
BEFORE UPDATE OR DELETE ON cache.observed_build_snapshots
FOR EACH ROW EXECUTE FUNCTION cache.reject_observed_build_mutation();

DROP TRIGGER IF EXISTS trg_observed_build_snapshot_checks_immutable
ON ops.observed_build_snapshot_checks;
CREATE TRIGGER trg_observed_build_snapshot_checks_immutable
BEFORE UPDATE OR DELETE ON ops.observed_build_snapshot_checks
FOR EACH ROW EXECUTE FUNCTION cache.reject_observed_build_mutation();

DROP TRIGGER IF EXISTS trg_observed_build_projections_immutable
ON cache.observed_build_projections;
CREATE TRIGGER trg_observed_build_projections_immutable
BEFORE UPDATE OR DELETE ON cache.observed_build_projections
FOR EACH ROW EXECUTE FUNCTION cache.reject_observed_build_mutation();

DROP TRIGGER IF EXISTS trg_observed_build_template_sets_immutable
ON cache.observed_build_template_sets;
CREATE TRIGGER trg_observed_build_template_sets_immutable
BEFORE UPDATE OR DELETE ON cache.observed_build_template_sets
FOR EACH ROW EXECUTE FUNCTION cache.reject_observed_build_mutation();

DROP TRIGGER IF EXISTS trg_observed_build_template_set_slots_immutable
ON cache.observed_build_template_set_slots;
CREATE TRIGGER trg_observed_build_template_set_slots_immutable
BEFORE UPDATE OR DELETE ON cache.observed_build_template_set_slots
FOR EACH ROW EXECUTE FUNCTION cache.reject_observed_build_mutation();

REVOKE UPDATE, DELETE ON
    cache.observed_build_snapshots,
    cache.observed_build_projections,
    cache.observed_build_template_sets,
    cache.observed_build_template_set_slots
FROM wow_app;

REVOKE UPDATE, DELETE ON ops.observed_build_snapshot_checks FROM wow_app;

GRANT SELECT, INSERT ON
    cache.observed_build_snapshots,
    cache.observed_build_projections,
    cache.observed_build_template_sets,
    cache.observed_build_template_set_slots,
    ops.observed_build_snapshot_checks
TO wow_app;

REVOKE DELETE ON cache.observed_build_template_set_pointer FROM wow_app;
GRANT SELECT, INSERT, UPDATE ON cache.observed_build_template_set_pointer TO wow_app;
GRANT USAGE, SELECT ON SEQUENCE ops.observed_build_snapshot_checks_check_id_seq TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0018_observed_build_registry',
    'Add immutable observed player snapshots and projections, atomic 80-slot TemplateSets, source checks, and a CAS publication pointer'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

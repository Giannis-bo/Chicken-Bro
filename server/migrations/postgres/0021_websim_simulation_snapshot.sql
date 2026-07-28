CREATE TABLE IF NOT EXISTS cache.websim_gear_resolved_loadouts (
    resolved_loadout_key text PRIMARY KEY
        CHECK (
            resolved_loadout_key
            ~ '^resolved-loadout:sha256:[0-9a-f]{64}$'
        ),
    schema_revision text NOT NULL,
    catalog_revision text NOT NULL
        REFERENCES cache.websim_gear_catalog_revisions(catalog_revision)
        ON DELETE RESTRICT,
    gear_rule_revision text NOT NULL,
    exact_registry_revision text NOT NULL
        CHECK (
            exact_registry_revision
            ~ '^gear-exact-registry:sha256:[0-9a-f]{64}$'
        ),
    class_key text NOT NULL,
    spec_key text NOT NULL,
    loadout_json jsonb NOT NULL
        CHECK (
            jsonb_typeof(loadout_json) = 'object'
            AND loadout_json->>'status' = 'ready'
            AND octet_length(loadout_json::text) <= 4194304
        ),
    row_hash text NOT NULL CHECK (row_hash ~ '^sha256:[0-9a-f]{64}$'),
    sealed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_resolved_loadouts_revision
ON cache.websim_gear_resolved_loadouts (
    catalog_revision,
    gear_rule_revision,
    class_key,
    spec_key
);

CREATE TABLE IF NOT EXISTS cache.websim_simulation_snapshots (
    simulation_snapshot_key text PRIMARY KEY
        CHECK (
            simulation_snapshot_key
            ~ '^simulation-snapshot:sha256:[0-9a-f]{64}$'
        ),
    schema_revision text NOT NULL,
    resolved_loadout_key text NOT NULL
        REFERENCES cache.websim_gear_resolved_loadouts(resolved_loadout_key)
        ON DELETE RESTRICT,
    talent_profile_key text NOT NULL
        CHECK (
            talent_profile_key
            ~ '^talent-profile:sha256:[0-9a-f]{64}$'
        ),
    compiler_revision text NOT NULL,
    simc_runtime_revision text NOT NULL,
    canonical_input_hash text NOT NULL
        CHECK (
            canonical_input_hash
            ~ '^simc-input:sha256:[0-9a-f]{64}$'
        ),
    catalog_revision text NOT NULL
        REFERENCES cache.websim_gear_catalog_revisions(catalog_revision)
        ON DELETE RESTRICT,
    gear_rule_revision text NOT NULL,
    snapshot_json jsonb NOT NULL
        CHECK (
            jsonb_typeof(snapshot_json) = 'object'
            AND snapshot_json->>'status' = 'ready'
            AND octet_length(snapshot_json::text) <= 4194304
        ),
    row_hash text NOT NULL CHECK (row_hash ~ '^sha256:[0-9a-f]{64}$'),
    sealed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_simulation_snapshots_loadout
ON cache.websim_simulation_snapshots (
    resolved_loadout_key,
    compiler_revision,
    simc_runtime_revision
);

CREATE TABLE IF NOT EXISTS cache.websim_simulation_snapshot_results (
    simulation_snapshot_key text PRIMARY KEY
        REFERENCES cache.websim_simulation_snapshots(simulation_snapshot_key)
        ON DELETE RESTRICT,
    result_identity text NOT NULL
        CHECK (result_identity ~ '^simc-result:sha256:[0-9a-f]{64}$'),
    result_status text NOT NULL CHECK (result_status IN ('completed', 'failed')),
    result_json jsonb NOT NULL
        CHECK (
            jsonb_typeof(result_json) = 'object'
            AND octet_length(result_json::text) <= 4194304
        ),
    row_hash text NOT NULL CHECK (row_hash ~ '^sha256:[0-9a-f]{64}$'),
    sealed_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION cache.reject_websim_simulation_snapshot_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'sealed WebSim loadout and simulation rows are append-only';
END;
$$;

DROP TRIGGER IF EXISTS trg_websim_gear_resolved_loadouts_immutable
ON cache.websim_gear_resolved_loadouts;
CREATE TRIGGER trg_websim_gear_resolved_loadouts_immutable
BEFORE UPDATE OR DELETE ON cache.websim_gear_resolved_loadouts
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_simulation_snapshot_mutation();

DROP TRIGGER IF EXISTS trg_websim_simulation_snapshots_immutable
ON cache.websim_simulation_snapshots;
CREATE TRIGGER trg_websim_simulation_snapshots_immutable
BEFORE UPDATE OR DELETE ON cache.websim_simulation_snapshots
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_simulation_snapshot_mutation();

DROP TRIGGER IF EXISTS trg_websim_simulation_snapshot_results_immutable
ON cache.websim_simulation_snapshot_results;
CREATE TRIGGER trg_websim_simulation_snapshot_results_immutable
BEFORE UPDATE OR DELETE ON cache.websim_simulation_snapshot_results
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_simulation_snapshot_mutation();

REVOKE UPDATE, DELETE, TRUNCATE ON
    cache.websim_gear_resolved_loadouts,
    cache.websim_simulation_snapshots,
    cache.websim_simulation_snapshot_results
FROM wow_app;

GRANT SELECT, INSERT ON
    cache.websim_gear_resolved_loadouts,
    cache.websim_simulation_snapshots,
    cache.websim_simulation_snapshot_results
TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0021_websim_simulation_snapshot',
    'Add append-only exact ResolvedLoadout, immutable canonical SimulationSnapshot, and terminal result binding caches'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

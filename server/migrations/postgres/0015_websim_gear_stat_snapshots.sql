CREATE TABLE IF NOT EXISTS cache.websim_gear_stat_snapshots (
    stat_signature text PRIMARY KEY
        CHECK (stat_signature ~ '^stat-snapshot:sha256:[0-9a-f]{64}$'),
    schema_revision text NOT NULL,
    resolved_gear_signature text NOT NULL,
    manifest_revision text NOT NULL
        REFERENCES cache.websim_season_manifests(manifest_revision) ON DELETE RESTRICT,
    gear_release_id text NOT NULL
        REFERENCES cache.websim_release_registry(release_id) ON DELETE RESTRICT,
    simc_runtime_revision text NOT NULL,
    dependency_vector_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    profile_hash text NOT NULL CHECK (profile_hash ~ '^sha256:[0-9a-f]{64}$'),
    snapshot_hash text NOT NULL CHECK (snapshot_hash ~ '^sha256:[0-9a-f]{64}$'),
    snapshot_json jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (octet_length(snapshot_json::text) <= 65536),
    verified_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_stat_snapshots_manifest
ON cache.websim_gear_stat_snapshots (manifest_revision, verified_at DESC);

CREATE TABLE IF NOT EXISTS ops.websim_gear_stat_jobs (
    job_id bigserial PRIMARY KEY,
    stat_signature text NOT NULL
        CHECK (stat_signature ~ '^stat-snapshot:sha256:[0-9a-f]{64}$'),
    status text NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'blocked', 'failed')),
    request_json jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (octet_length(request_json::text) <= 131072),
    release_context_json jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (octet_length(release_context_json::text) <= 16384),
    client_key_hash text NOT NULL DEFAULT ''
        CHECK (client_key_hash = '' OR client_key_hash ~ '^sha256:[0-9a-f]{64}$'),
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt >= 0 AND attempt <= 20),
    locked_by text NOT NULL DEFAULT '' CHECK (length(locked_by) <= 160),
    lock_token text NOT NULL DEFAULT '' CHECK (length(lock_token) <= 160),
    lease_until timestamptz,
    queued_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    heartbeat_at timestamptz,
    finished_at timestamptz,
    cooldown_until timestamptz,
    problem_json jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (octet_length(problem_json::text) <= 16384),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (status = 'running' AND locked_by <> '' AND lock_token <> '' AND lease_until IS NOT NULL)
        OR (status <> 'running' AND lease_until IS NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ops_websim_gear_stat_jobs_active_signature
ON ops.websim_gear_stat_jobs (stat_signature)
WHERE status IN ('queued', 'running');

CREATE INDEX IF NOT EXISTS idx_ops_websim_gear_stat_jobs_claim
ON ops.websim_gear_stat_jobs (status, queued_at, job_id);

CREATE INDEX IF NOT EXISTS idx_ops_websim_gear_stat_jobs_client_active
ON ops.websim_gear_stat_jobs (client_key_hash, status, queued_at);

CREATE INDEX IF NOT EXISTS idx_ops_websim_gear_stat_jobs_signature_history
ON ops.websim_gear_stat_jobs (stat_signature, job_id DESC);

CREATE TABLE IF NOT EXISTS ops.websim_gear_stat_worker_state (
    worker_id text PRIMARY KEY CHECK (length(worker_id) BETWEEN 1 AND 160),
    status text NOT NULL CHECK (status IN ('starting', 'idle', 'running', 'stopping', 'failed')),
    worker_revision text NOT NULL DEFAULT '',
    simc_runtime_revision text NOT NULL DEFAULT '',
    current_job_id bigint REFERENCES ops.websim_gear_stat_jobs(job_id) ON DELETE RESTRICT,
    heartbeat_at timestamptz NOT NULL,
    last_outcome_json jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (octet_length(last_outcome_json::text) <= 16384),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ops_websim_gear_stat_worker_heartbeat
ON ops.websim_gear_stat_worker_state (heartbeat_at DESC);

CREATE TABLE IF NOT EXISTS ops.websim_gear_stat_metrics (
    metric_key text PRIMARY KEY CHECK (metric_key = 'global'),
    request_count bigint NOT NULL DEFAULT 0 CHECK (request_count >= 0),
    cache_hit_count bigint NOT NULL DEFAULT 0 CHECK (cache_hit_count >= 0),
    queue_miss_count bigint NOT NULL DEFAULT 0 CHECK (queue_miss_count >= 0),
    legacy_request_count bigint NOT NULL DEFAULT 0 CHECK (legacy_request_count >= 0),
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO ops.websim_gear_stat_metrics (metric_key)
VALUES ('global')
ON CONFLICT (metric_key) DO NOTHING;

CREATE OR REPLACE FUNCTION cache.reject_websim_stat_snapshot_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'verified WebSim Gear stat snapshots are immutable';
END;
$$;

DROP TRIGGER IF EXISTS trg_websim_gear_stat_snapshots_immutable
ON cache.websim_gear_stat_snapshots;
CREATE TRIGGER trg_websim_gear_stat_snapshots_immutable
BEFORE UPDATE OR DELETE ON cache.websim_gear_stat_snapshots
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_stat_snapshot_mutation();

REVOKE UPDATE, DELETE ON cache.websim_gear_stat_snapshots FROM wow_app;
GRANT SELECT, INSERT ON cache.websim_gear_stat_snapshots TO wow_app;

REVOKE DELETE ON ops.websim_gear_stat_jobs FROM wow_app;
REVOKE DELETE ON ops.websim_gear_stat_worker_state FROM wow_app;
REVOKE DELETE ON ops.websim_gear_stat_metrics FROM wow_app;

GRANT SELECT, INSERT, UPDATE ON
    ops.websim_gear_stat_jobs,
    ops.websim_gear_stat_worker_state,
    ops.websim_gear_stat_metrics
TO wow_app;

GRANT USAGE, SELECT ON SEQUENCE ops.websim_gear_stat_jobs_job_id_seq TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0015_websim_gear_stat_snapshots',
    'Add immutable verified Gear stat snapshots plus fenced single-flight jobs, worker state and bounded metrics'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

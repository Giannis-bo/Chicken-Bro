CREATE TABLE IF NOT EXISTS cache.websim_gear_evidence_artifacts (
    artifact_id text PRIMARY KEY
        CHECK (artifact_id ~ '^gear-artifact:sha256:[0-9a-f]{64}$'),
    schema_revision text NOT NULL
        CHECK (schema_revision = 'gear-evidence-artifact-v1'),
    source_type text NOT NULL CHECK (length(source_type) BETWEEN 1 AND 120),
    source_identity text NOT NULL CHECK (length(source_identity) BETWEEN 1 AND 1024),
    source_revision text NOT NULL CHECK (length(source_revision) BETWEEN 1 AND 256),
    season_revision text NOT NULL CHECK (length(season_revision) BETWEEN 1 AND 256),
    captured_at timestamptz NOT NULL,
    payload_hash text NOT NULL CHECK (payload_hash ~ '^sha256:[0-9a-f]{64}$'),
    payload_json jsonb NOT NULL
        CHECK (octet_length(payload_json::text) <= 1048576),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_evidence_artifacts_source
ON cache.websim_gear_evidence_artifacts (
    season_revision,
    source_type,
    source_identity,
    source_revision
);

CREATE TABLE IF NOT EXISTS cache.websim_gear_evidence_observations (
    observation_id text PRIMARY KEY
        CHECK (observation_id ~ '^gear-observation:sha256:[0-9a-f]{64}$'),
    artifact_id text NOT NULL
        REFERENCES cache.websim_gear_evidence_artifacts(artifact_id) ON DELETE RESTRICT,
    schema_revision text NOT NULL
        CHECK (schema_revision = 'gear-evidence-observation-v1'),
    subject_key text NOT NULL CHECK (length(subject_key) BETWEEN 1 AND 512),
    fact_type text NOT NULL CHECK (length(fact_type) BETWEEN 1 AND 120),
    observed_value_json jsonb NOT NULL,
    parser_revision text NOT NULL CHECK (length(parser_revision) BETWEEN 1 AND 256),
    source_scope text NOT NULL CHECK (length(source_scope) BETWEEN 1 AND 120),
    status text NOT NULL CHECK (status = 'accepted'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_evidence_observations_subject
ON cache.websim_gear_evidence_observations (subject_key, fact_type, artifact_id);

CREATE TABLE IF NOT EXISTS cache.websim_gear_canonical_facts (
    fact_key text NOT NULL CHECK (fact_key ~ '^gear-fact:sha256:[0-9a-f]{64}$'),
    schema_revision text NOT NULL
        CHECK (schema_revision = 'gear-canonical-fact-v1'),
    season_revision text NOT NULL CHECK (length(season_revision) BETWEEN 1 AND 256),
    subject_key text NOT NULL CHECK (length(subject_key) BETWEEN 1 AND 512),
    fact_type text NOT NULL CHECK (length(fact_type) BETWEEN 1 AND 120),
    value_json jsonb NOT NULL,
    status text NOT NULL CHECK (status IN (
        'verified', 'unresolved_missing', 'unresolved_conflict'
    )),
    observation_refs_json jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(observation_refs_json) = 'array')
        CHECK (octet_length(observation_refs_json::text) <= 262144),
    fact_value_hash text NOT NULL CHECK (fact_value_hash ~ '^sha256:[0-9a-f]{64}$'),
    provenance_hash text NOT NULL CHECK (provenance_hash ~ '^sha256:[0-9a-f]{64}$'),
    compiler_rule_revision text NOT NULL
        CHECK (length(compiler_rule_revision) BETWEEN 1 AND 256),
    impact_scope text NOT NULL CHECK (length(impact_scope) BETWEEN 1 AND 120),
    problem_code text NOT NULL DEFAULT '' CHECK (length(problem_code) <= 120),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (fact_key, fact_value_hash, provenance_hash),
    CHECK (
        (status = 'verified' AND value_json <> 'null'::jsonb)
        OR (status <> 'verified' AND value_json = 'null'::jsonb)
    )
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_canonical_facts_subject
ON cache.websim_gear_canonical_facts (season_revision, subject_key, fact_type);

CREATE TABLE IF NOT EXISTS cache.websim_gear_evidence_invalidations (
    invalidation_id text PRIMARY KEY
        CHECK (invalidation_id ~ '^gear-invalidation:sha256:[0-9a-f]{64}$'),
    schema_revision text NOT NULL
        CHECK (schema_revision = 'gear-evidence-invalidation-v1'),
    artifact_id text
        REFERENCES cache.websim_gear_evidence_artifacts(artifact_id) ON DELETE RESTRICT,
    observation_id text
        REFERENCES cache.websim_gear_evidence_observations(observation_id) ON DELETE RESTRICT,
    reason_code text NOT NULL CHECK (length(reason_code) BETWEEN 1 AND 120),
    detail_json jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(detail_json) = 'object')
        CHECK (octet_length(detail_json::text) <= 65536),
    invalidated_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(artifact_id, observation_id) = 1)
);

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_evidence_invalidations_artifact
ON cache.websim_gear_evidence_invalidations (artifact_id, invalidated_at DESC)
WHERE artifact_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cache_websim_gear_evidence_invalidations_observation
ON cache.websim_gear_evidence_invalidations (observation_id, invalidated_at DESC)
WHERE observation_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS ops.websim_gear_evidence_gaps (
    gap_key text PRIMARY KEY CHECK (gap_key ~ '^gear-gap:sha256:[0-9a-f]{64}$'),
    fact_key text NOT NULL CHECK (fact_key ~ '^gear-fact:sha256:[0-9a-f]{64}$'),
    schema_revision text NOT NULL CHECK (schema_revision = 'gear-evidence-gap-v1'),
    status text NOT NULL CHECK (status IN ('pending', 'running', 'retryable', 'terminal')),
    problem_code text NOT NULL CHECK (problem_code IN (
        'artifact_missing',
        'source_unavailable',
        'parser_unhandled_shape',
        'observation_conflict',
        'compiler_policy_missing',
        'projection_contract_regression'
    )),
    missing_requirement_json jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(missing_requirement_json) = 'object')
        CHECK (octet_length(missing_requirement_json::text) <= 65536),
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt BETWEEN 0 AND 3),
    locked_by text NOT NULL DEFAULT '' CHECK (length(locked_by) <= 160),
    lock_token text NOT NULL DEFAULT '' CHECK (length(lock_token) <= 160),
    lease_until timestamptz,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    queued_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (
            status = 'running'
            AND locked_by <> ''
            AND lock_token <> ''
            AND lease_until IS NOT NULL
        )
        OR (
            status <> 'running'
            AND locked_by = ''
            AND lock_token = ''
            AND lease_until IS NULL
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_ops_websim_gear_evidence_gaps_claim
ON ops.websim_gear_evidence_gaps (
    status,
    next_attempt_at,
    queued_at,
    gap_key
);

CREATE INDEX IF NOT EXISTS idx_ops_websim_gear_evidence_gaps_problem
ON ops.websim_gear_evidence_gaps (problem_code, status, updated_at DESC);

CREATE OR REPLACE FUNCTION cache.reject_websim_gear_evidence_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Gear Evidence Registry rows are append-only';
END;
$$;

DROP TRIGGER IF EXISTS trg_websim_gear_evidence_artifacts_immutable
ON cache.websim_gear_evidence_artifacts;
CREATE TRIGGER trg_websim_gear_evidence_artifacts_immutable
BEFORE UPDATE OR DELETE ON cache.websim_gear_evidence_artifacts
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_gear_evidence_mutation();

DROP TRIGGER IF EXISTS trg_websim_gear_evidence_observations_immutable
ON cache.websim_gear_evidence_observations;
CREATE TRIGGER trg_websim_gear_evidence_observations_immutable
BEFORE UPDATE OR DELETE ON cache.websim_gear_evidence_observations
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_gear_evidence_mutation();

DROP TRIGGER IF EXISTS trg_websim_gear_canonical_facts_immutable
ON cache.websim_gear_canonical_facts;
CREATE TRIGGER trg_websim_gear_canonical_facts_immutable
BEFORE UPDATE OR DELETE ON cache.websim_gear_canonical_facts
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_gear_evidence_mutation();

DROP TRIGGER IF EXISTS trg_websim_gear_evidence_invalidations_immutable
ON cache.websim_gear_evidence_invalidations;
CREATE TRIGGER trg_websim_gear_evidence_invalidations_immutable
BEFORE UPDATE OR DELETE ON cache.websim_gear_evidence_invalidations
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_gear_evidence_mutation();

REVOKE UPDATE, DELETE ON cache.websim_gear_evidence_artifacts FROM wow_app;
GRANT SELECT, INSERT ON cache.websim_gear_evidence_artifacts TO wow_app;

REVOKE UPDATE, DELETE ON cache.websim_gear_evidence_observations FROM wow_app;
GRANT SELECT, INSERT ON cache.websim_gear_evidence_observations TO wow_app;

REVOKE UPDATE, DELETE ON cache.websim_gear_canonical_facts FROM wow_app;
GRANT SELECT, INSERT ON cache.websim_gear_canonical_facts TO wow_app;

REVOKE UPDATE, DELETE ON cache.websim_gear_evidence_invalidations FROM wow_app;
GRANT SELECT, INSERT ON cache.websim_gear_evidence_invalidations TO wow_app;

REVOKE DELETE ON ops.websim_gear_evidence_gaps FROM wow_app;
GRANT SELECT, INSERT, UPDATE ON ops.websim_gear_evidence_gaps TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0019_gear_evidence_registry',
    'Add immutable Gear Evidence Registry rows and fenced operational Evidence Gap queue'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

ALTER TABLE ops.websim_gear_evidence_gaps
    DROP CONSTRAINT IF EXISTS websim_gear_evidence_gaps_status_check;

ALTER TABLE ops.websim_gear_evidence_gaps
    DROP CONSTRAINT IF EXISTS websim_gear_evidence_gaps_check;

ALTER TABLE ops.websim_gear_evidence_gaps
    ADD COLUMN IF NOT EXISTS candidate_request_key text;

ALTER TABLE ops.websim_gear_evidence_gaps
    ADD CONSTRAINT websim_gear_evidence_gaps_status_check
    CHECK (status IN (
        'pending', 'running', 'retryable', 'candidate_pending',
        'candidate_running', 'terminal'
    ));

ALTER TABLE ops.websim_gear_evidence_gaps
    DROP CONSTRAINT IF EXISTS websim_gear_evidence_gaps_lock_state_check;

ALTER TABLE ops.websim_gear_evidence_gaps
    ADD CONSTRAINT websim_gear_evidence_gaps_lock_state_check
    CHECK (
        (
            status IN ('running', 'candidate_running')
            AND locked_by <> ''
            AND lock_token <> ''
            AND lease_until IS NOT NULL
        )
        OR (
            status NOT IN ('running', 'candidate_running')
            AND locked_by = ''
            AND lock_token = ''
            AND lease_until IS NULL
        )
    );

CREATE TABLE IF NOT EXISTS ops.websim_gear_evidence_candidate_requests (
    request_key text PRIMARY KEY
        CHECK (request_key ~ '^gear-candidate-request:sha256:[0-9a-f]{64}$'),
    schema_revision text NOT NULL
        CHECK (schema_revision = 'gear-evidence-candidate-request-v1'),
    gap_key text NOT NULL
        REFERENCES ops.websim_gear_evidence_gaps(gap_key) ON DELETE RESTRICT,
    artifact_id text NOT NULL
        REFERENCES cache.websim_gear_evidence_artifacts(artifact_id) ON DELETE RESTRICT,
    observation_ids_json jsonb NOT NULL
        CHECK (jsonb_typeof(observation_ids_json) = 'array')
        CHECK (jsonb_array_length(observation_ids_json) BETWEEN 1 AND 8)
        CHECK (octet_length(observation_ids_json::text) <= 2048),
    season_revision text NOT NULL CHECK (length(season_revision) BETWEEN 1 AND 256),
    subject_key text NOT NULL CHECK (length(subject_key) BETWEEN 1 AND 512),
    fact_type text NOT NULL CHECK (length(fact_type) BETWEEN 1 AND 120),
    source_type text NOT NULL CHECK (length(source_type) BETWEEN 1 AND 120),
    status text NOT NULL CHECK (status IN (
        'candidate_pending', 'candidate_running', 'terminal'
    )),
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt BETWEEN 0 AND 3),
    locked_by text NOT NULL DEFAULT '' CHECK (length(locked_by) <= 160),
    lock_token text NOT NULL DEFAULT '' CHECK (length(lock_token) <= 160),
    lease_until timestamptz,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    candidate_gear_release_id text NOT NULL DEFAULT '',
    last_problem_code text NOT NULL DEFAULT '' CHECK (length(last_problem_code) <= 120),
    queued_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (
            status = 'candidate_running'
            AND locked_by <> ''
            AND lock_token <> ''
            AND lease_until IS NOT NULL
        )
        OR (
            status <> 'candidate_running'
            AND locked_by = ''
            AND lock_token = ''
            AND lease_until IS NULL
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ops_gear_evidence_candidate_request_gap
ON ops.websim_gear_evidence_candidate_requests (gap_key);

CREATE INDEX IF NOT EXISTS idx_ops_gear_evidence_candidate_request_claim
ON ops.websim_gear_evidence_candidate_requests (
    status, next_attempt_at, queued_at, request_key
);

ALTER TABLE ops.websim_gear_evidence_gaps
    DROP CONSTRAINT IF EXISTS websim_gear_evidence_gaps_candidate_request_fk;

ALTER TABLE ops.websim_gear_evidence_gaps
    ADD CONSTRAINT websim_gear_evidence_gaps_candidate_request_fk
    FOREIGN KEY (candidate_request_key)
    REFERENCES ops.websim_gear_evidence_candidate_requests(request_key)
    ON DELETE RESTRICT;

REVOKE DELETE ON ops.websim_gear_evidence_candidate_requests FROM wow_app;
GRANT SELECT, INSERT, UPDATE ON ops.websim_gear_evidence_candidate_requests TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0020_gear_evidence_candidate_recompile',
    'Add fenced candidate-only Gear Evidence recompile handoff requests'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

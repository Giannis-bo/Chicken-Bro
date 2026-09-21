CREATE SCHEMA IF NOT EXISTS poe2;

CREATE TABLE IF NOT EXISTS poe2.builds (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 128),
    source_xml text NOT NULL,
    game_version text NOT NULL,
    league text NOT NULL,
    input_sha256 text NOT NULL CHECK (char_length(input_sha256) = 64),
    engine_version text NOT NULL,
    export_code text NOT NULL,
    summary_json jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS poe2_builds_owner_created_idx
    ON poe2.builds(user_id, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS poe2.jobs (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    build_id uuid NOT NULL REFERENCES poe2.builds(id) ON DELETE RESTRICT,
    idempotency_key text NOT NULL CHECK (char_length(idempotency_key) BETWEEN 1 AND 128),
    request_hash text NOT NULL CHECK (char_length(request_hash) = 64),
    changes_json jsonb NOT NULL,
    status text NOT NULL CHECK (status IN ('queued','running','succeeded','failed')),
    result_json jsonb,
    public_error_code text NOT NULL DEFAULT '',
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count BETWEEN 0 AND 3),
    lease_owner text NOT NULL DEFAULT '',
    lease_expires_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS poe2_jobs_owner_created_idx
    ON poe2.jobs(user_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS poe2_jobs_claim_idx
    ON poe2.jobs(status, lease_expires_at, created_at) WHERE status IN ('queued','running');

GRANT USAGE ON SCHEMA poe2 TO wow_app;
GRANT SELECT, INSERT ON poe2.builds TO wow_app;
GRANT SELECT, INSERT, UPDATE ON poe2.jobs TO wow_app;

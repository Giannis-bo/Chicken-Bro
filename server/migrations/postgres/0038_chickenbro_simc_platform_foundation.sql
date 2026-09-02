-- 0038: additive platform foundation for the next-generation Chickenbro and SimC paths.
--
-- This migration is intentionally parallel to the legacy app/cache/websim owners.
-- It creates no compatibility view and changes no existing table or pointer.

CREATE SCHEMA IF NOT EXISTS chat;
CREATE SCHEMA IF NOT EXISTS simc;

CREATE TABLE IF NOT EXISTS chat.conversations (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    title text NOT NULL DEFAULT '',
    status text NOT NULL CHECK (status IN ('active', 'archived')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_conversations_user_updated
ON chat.conversations (user_id, updated_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS chat.messages (
    id uuid PRIMARY KEY,
    conversation_id uuid NOT NULL,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('user', 'assistant')),
    content text NOT NULL CHECK (length(content) > 0),
    client_message_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, client_message_id),
    UNIQUE (id, user_id),
    FOREIGN KEY (conversation_id, user_id)
        REFERENCES chat.conversations(id, user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_created
ON chat.messages (conversation_id, created_at, id);

CREATE TABLE IF NOT EXISTS chat.agent_runs (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    conversation_id uuid NOT NULL,
    user_message_id uuid NOT NULL,
    assistant_message_id uuid,
    status text NOT NULL CHECK (status IN ('streaming', 'succeeded', 'failed')),
    runtime_revision text NOT NULL DEFAULT '',
    public_error_code text NOT NULL DEFAULT '',
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    CHECK (status <> 'succeeded' OR assistant_message_id IS NOT NULL),
    FOREIGN KEY (conversation_id, user_id)
        REFERENCES chat.conversations(id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (user_message_id, user_id)
        REFERENCES chat.messages(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (assistant_message_id, user_id)
        REFERENCES chat.messages(id, user_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_chat_agent_runs_user_started
ON chat.agent_runs (user_id, started_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS simc.source_snapshots (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    provider text NOT NULL CHECK (provider IN ('raiderio', 'warcraftlogs')),
    source_url text NOT NULL,
    source_key text NOT NULL,
    revision integer NOT NULL CHECK (revision > 0),
    readiness text NOT NULL CHECK (
        readiness IN (
            'INVALID_LINK',
            'CHARACTER_NOT_FOUND',
            'ACCESS_RESTRICTED',
            'SNAPSHOT_UNAVAILABLE',
            'INCOMPLETE_FOR_SIMC',
            'READY_FOR_SIMC'
        )
    ),
    snapshot_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    provenance_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    raw_sha256 text NOT NULL CHECK (raw_sha256 ~ '^[0-9a-fA-F]{64}$'),
    fetched_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, provider, source_key, revision),
    UNIQUE (id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_simc_source_snapshots_user_fetched
ON simc.source_snapshots (user_id, fetched_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS simc.simulation_jobs (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    snapshot_id uuid NOT NULL,
    scenario_hash text NOT NULL,
    compiler_revision text NOT NULL,
    runtime_revision text NOT NULL,
    idempotency_key text NOT NULL,
    status text NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    public_error_code text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, idempotency_key),
    UNIQUE (id, user_id),
    FOREIGN KEY (snapshot_id, user_id)
        REFERENCES simc.source_snapshots(id, user_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_simc_simulation_jobs_user_updated
ON simc.simulation_jobs (user_id, updated_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS simc.simulation_attempts (
    id uuid PRIMARY KEY,
    job_id uuid NOT NULL,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    attempt_number integer NOT NULL CHECK (attempt_number > 0),
    worker_id text NOT NULL DEFAULT '',
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    exit_code integer,
    diagnostic text NOT NULL DEFAULT '' CHECK (length(diagnostic) <= 4096),
    UNIQUE (job_id, attempt_number),
    FOREIGN KEY (job_id, user_id)
        REFERENCES simc.simulation_jobs(id, user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_simc_simulation_attempts_job_started
ON simc.simulation_attempts (job_id, started_at, id);

CREATE TABLE IF NOT EXISTS simc.simulation_results (
    id uuid PRIMARY KEY,
    job_id uuid NOT NULL,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    profile_sha256 text NOT NULL CHECK (profile_sha256 ~ '^[0-9a-fA-F]{64}$'),
    result_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    primary_metric_name text NOT NULL,
    primary_metric_value double precision NOT NULL,
    compiler_revision text NOT NULL,
    runtime_revision text NOT NULL,
    provenance_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (job_id),
    FOREIGN KEY (job_id, user_id)
        REFERENCES simc.simulation_jobs(id, user_id) ON DELETE RESTRICT
);

CREATE OR REPLACE FUNCTION simc.reject_simulation_result_mutation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, simc, pg_temp
AS $simulation_result_immutable$
BEGIN
    RAISE EXCEPTION 'simc.simulation_results is immutable';
END;
$simulation_result_immutable$;

DROP TRIGGER IF EXISTS trg_simulation_results_immutable ON simc.simulation_results;
CREATE TRIGGER trg_simulation_results_immutable
BEFORE UPDATE OR DELETE ON simc.simulation_results
FOR EACH ROW EXECUTE FUNCTION simc.reject_simulation_result_mutation();

DROP TRIGGER IF EXISTS trg_simulation_results_truncate ON simc.simulation_results;
CREATE TRIGGER trg_simulation_results_truncate
BEFORE TRUNCATE ON simc.simulation_results
FOR EACH STATEMENT EXECUTE FUNCTION simc.reject_simulation_result_mutation();

CREATE TABLE IF NOT EXISTS ops.job_queue (
    id uuid PRIMARY KEY,
    domain text NOT NULL CHECK (domain IN ('identity', 'chat', 'simc')),
    command_type text NOT NULL,
    aggregate_id uuid,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
    available_at timestamptz NOT NULL DEFAULT now(),
    lease_owner text NOT NULL DEFAULT '',
    lease_expires_at timestamptz,
    heartbeat_at timestamptz,
    cancel_requested boolean NOT NULL DEFAULT false,
    public_error_code text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ops_job_queue_claim
ON ops.job_queue (available_at, created_at)
WHERE status = 'queued';

CREATE INDEX IF NOT EXISTS idx_ops_job_queue_expired_lease
ON ops.job_queue (lease_expires_at, available_at, created_at)
WHERE status = 'running';

GRANT USAGE ON SCHEMA chat, simc TO wow_app;

GRANT SELECT, INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA chat, simc
TO wow_app;

GRANT SELECT, INSERT, UPDATE, DELETE
ON ops.job_queue
TO wow_app;

ALTER DEFAULT PRIVILEGES FOR ROLE wow_migrator IN SCHEMA chat
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wow_app;

ALTER DEFAULT PRIVILEGES FOR ROLE wow_migrator IN SCHEMA simc
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0038_chickenbro_simc_platform_foundation',
    'Create isolated Chickenbro, SimC and worker platform foundation owners'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

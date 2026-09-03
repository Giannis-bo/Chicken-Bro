-- Product-only baseline for Chickenbro Chat and SimC.
-- Apply only to an empty, capacity-approved chickenbro_prod database.
-- Existing objects are an error: this lineage must never merge into legacy schemas.

CREATE SCHEMA identity;
CREATE SCHEMA chat;
CREATE SCHEMA simc;
CREATE SCHEMA ops;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

CREATE TABLE identity.users (
    id uuid PRIMARY KEY,
    display_name text NOT NULL DEFAULT '' CHECK (length(display_name) <= 256),
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled', 'deleted')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE identity.user_identities (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    provider text NOT NULL CHECK (provider = 'wechat_mini'),
    app_context text NOT NULL CHECK (length(app_context) BETWEEN 1 AND 128),
    provider_subject text NOT NULL CHECK (length(provider_subject) BETWEEN 1 AND 256),
    union_id text CHECK (union_id IS NULL OR length(union_id) BETWEEN 1 AND 256),
    profile_json jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (
        jsonb_typeof(profile_json) = 'object'
        AND octet_length(profile_json::text) <= 8192
    ),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, app_context, provider_subject),
    UNIQUE (id, user_id)
);

CREATE INDEX idx_identity_user_identities_user
ON identity.user_identities (user_id, created_at, id);

CREATE TABLE identity.auth_sessions (
    token_hash text PRIMARY KEY CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    kind text NOT NULL CHECK (kind IN ('mini_bearer', 'web_cookie')),
    issued_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (
        jsonb_typeof(metadata_json) = 'object'
        AND octet_length(metadata_json::text) <= 2048
    ),
    CHECK (expires_at > issued_at),
    CHECK (revoked_at IS NULL OR revoked_at >= issued_at)
);

CREATE INDEX idx_identity_auth_sessions_user_kind
ON identity.auth_sessions (user_id, kind, expires_at DESC)
WHERE revoked_at IS NULL;

CREATE TABLE identity.web_login_sessions (
    id uuid PRIMARY KEY,
    scene_ticket_sha256 text NOT NULL UNIQUE CHECK (scene_ticket_sha256 ~ '^[0-9a-f]{64}$'),
    browser_verifier_sha256 text NOT NULL CHECK (browser_verifier_sha256 ~ '^[0-9a-f]{64}$'),
    idempotency_key_sha256 text CHECK (
        idempotency_key_sha256 IS NULL OR idempotency_key_sha256 ~ '^[0-9a-f]{64}$'
    ),
    user_id uuid REFERENCES identity.users(id) ON DELETE CASCADE,
    status text NOT NULL CHECK (
        status IN ('pending', 'confirmed', 'consumed', 'cancelled', 'expired')
    ),
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (expires_at > created_at),
    CHECK (status NOT IN ('confirmed', 'consumed') OR user_id IS NOT NULL),
    CHECK (status <> 'consumed' OR consumed_at IS NOT NULL)
);

CREATE UNIQUE INDEX idx_identity_web_login_idempotency
ON identity.web_login_sessions (browser_verifier_sha256, idempotency_key_sha256)
WHERE idempotency_key_sha256 IS NOT NULL;

CREATE INDEX idx_identity_web_login_expiry
ON identity.web_login_sessions (expires_at, status);

CREATE TABLE chat.conversations (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    title text NOT NULL DEFAULT '' CHECK (length(title) <= 256),
    status text NOT NULL CHECK (status IN ('active', 'archived')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, user_id)
);

CREATE INDEX idx_chat_conversations_user_updated
ON chat.conversations (user_id, updated_at DESC, id DESC);

CREATE TABLE chat.messages (
    id uuid PRIMARY KEY,
    conversation_id uuid NOT NULL,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('user', 'assistant')),
    content text NOT NULL CHECK (length(content) BETWEEN 1 AND 100000),
    client_message_id text CHECK (
        client_message_id IS NULL OR length(client_message_id) BETWEEN 1 AND 128
    ),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, client_message_id),
    UNIQUE (id, user_id),
    FOREIGN KEY (conversation_id, user_id)
        REFERENCES chat.conversations(id, user_id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_messages_conversation_created
ON chat.messages (conversation_id, created_at, id);

CREATE TABLE chat.agent_runs (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    conversation_id uuid NOT NULL,
    user_message_id uuid NOT NULL,
    assistant_message_id uuid,
    status text NOT NULL CHECK (status IN ('streaming', 'succeeded', 'failed')),
    runtime_revision text NOT NULL CHECK (length(runtime_revision) BETWEEN 1 AND 160),
    public_error_code text NOT NULL DEFAULT '' CHECK (length(public_error_code) <= 128),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    CHECK (status <> 'succeeded' OR assistant_message_id IS NOT NULL),
    CHECK (status = 'streaming' OR finished_at IS NOT NULL),
    FOREIGN KEY (conversation_id, user_id)
        REFERENCES chat.conversations(id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (user_message_id, user_id)
        REFERENCES chat.messages(id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (assistant_message_id, user_id)
        REFERENCES chat.messages(id, user_id) ON DELETE RESTRICT
);

CREATE INDEX idx_chat_agent_runs_user_started
ON chat.agent_runs (user_id, started_at DESC, id DESC);

CREATE TABLE simc.source_snapshots (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    provider text NOT NULL CHECK (provider IN ('raiderio', 'warcraftlogs')),
    source_url text NOT NULL CHECK (length(source_url) BETWEEN 1 AND 2048),
    source_key text NOT NULL CHECK (length(source_key) BETWEEN 1 AND 512),
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
    snapshot_json jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (
        jsonb_typeof(snapshot_json) = 'object'
        AND octet_length(snapshot_json::text) <= 1048576
    ),
    provenance_json jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (
        jsonb_typeof(provenance_json) = 'object'
        AND octet_length(provenance_json::text) <= 65536
    ),
    raw_sha256 text NOT NULL CHECK (raw_sha256 ~ '^[0-9a-f]{64}$'),
    fetched_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, provider, source_key, revision),
    UNIQUE (id, user_id)
);

CREATE INDEX idx_simc_source_snapshots_user_fetched
ON simc.source_snapshots (user_id, fetched_at DESC, id DESC);

CREATE TABLE simc.simulation_jobs (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    snapshot_id uuid NOT NULL,
    scenario_hash text NOT NULL CHECK (scenario_hash ~ '^[0-9a-f]{64}$'),
    compiler_revision text NOT NULL CHECK (length(compiler_revision) BETWEEN 1 AND 160),
    runtime_revision text NOT NULL CHECK (length(runtime_revision) BETWEEN 1 AND 160),
    idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 128),
    status text NOT NULL CHECK (
        status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')
    ),
    public_error_code text NOT NULL DEFAULT '' CHECK (length(public_error_code) <= 128),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, idempotency_key),
    UNIQUE (id, user_id),
    FOREIGN KEY (snapshot_id, user_id)
        REFERENCES simc.source_snapshots(id, user_id) ON DELETE RESTRICT
);

CREATE INDEX idx_simc_simulation_jobs_user_updated
ON simc.simulation_jobs (user_id, updated_at DESC, id DESC);

CREATE TABLE simc.simulation_attempts (
    id uuid PRIMARY KEY,
    job_id uuid NOT NULL,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    attempt_number integer NOT NULL CHECK (attempt_number > 0),
    worker_id text NOT NULL CHECK (length(worker_id) BETWEEN 1 AND 160),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    exit_code integer,
    diagnostic text NOT NULL DEFAULT '' CHECK (length(diagnostic) <= 4096),
    UNIQUE (job_id, attempt_number),
    FOREIGN KEY (job_id, user_id)
        REFERENCES simc.simulation_jobs(id, user_id) ON DELETE CASCADE
);

CREATE INDEX idx_simc_simulation_attempts_job_started
ON simc.simulation_attempts (job_id, started_at, id);

CREATE TABLE simc.simulation_results (
    id uuid PRIMARY KEY,
    job_id uuid NOT NULL,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    profile_sha256 text NOT NULL CHECK (profile_sha256 ~ '^[0-9a-f]{64}$'),
    result_json jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (
        jsonb_typeof(result_json) = 'object'
        AND octet_length(result_json::text) <= 1048576
    ),
    primary_metric_name text NOT NULL CHECK (length(primary_metric_name) BETWEEN 1 AND 64),
    primary_metric_value double precision NOT NULL CHECK (primary_metric_value > 0),
    compiler_revision text NOT NULL CHECK (length(compiler_revision) BETWEEN 1 AND 160),
    runtime_revision text NOT NULL CHECK (length(runtime_revision) BETWEEN 1 AND 160),
    provenance_json jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (
        jsonb_typeof(provenance_json) = 'object'
        AND octet_length(provenance_json::text) <= 65536
    ),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (job_id),
    FOREIGN KEY (job_id, user_id)
        REFERENCES simc.simulation_jobs(id, user_id) ON DELETE RESTRICT
);

CREATE FUNCTION simc.reject_simulation_result_mutation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, simc, pg_temp
AS $simulation_result_immutable$
BEGIN
    RAISE EXCEPTION 'simc.simulation_results is immutable';
END;
$simulation_result_immutable$;

CREATE TRIGGER trg_simulation_results_immutable
BEFORE UPDATE OR DELETE ON simc.simulation_results
FOR EACH ROW EXECUTE FUNCTION simc.reject_simulation_result_mutation();

CREATE TRIGGER trg_simulation_results_truncate
BEFORE TRUNCATE ON simc.simulation_results
FOR EACH STATEMENT EXECUTE FUNCTION simc.reject_simulation_result_mutation();

CREATE TABLE ops.schema_migrations (
    id text PRIMARY KEY CHECK (id ~ '^[0-9]{4}_[a-z0-9_]+$'),
    description text NOT NULL DEFAULT '' CHECK (length(description) <= 512),
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ops.job_queue (
    id uuid PRIMARY KEY,
    domain text NOT NULL CHECK (domain IN ('identity', 'chat', 'simc')),
    command_type text NOT NULL CHECK (length(command_type) BETWEEN 1 AND 128),
    aggregate_id uuid,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (
        jsonb_typeof(payload_json) = 'object'
        AND octet_length(payload_json::text) <= 65536
    ),
    status text NOT NULL CHECK (
        status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')
    ),
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
    available_at timestamptz NOT NULL DEFAULT now(),
    lease_owner text NOT NULL DEFAULT '' CHECK (length(lease_owner) <= 160),
    lease_expires_at timestamptz,
    heartbeat_at timestamptz,
    cancel_requested boolean NOT NULL DEFAULT false,
    public_error_code text NOT NULL DEFAULT '' CHECK (length(public_error_code) <= 128),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (status <> 'running' OR (lease_owner <> '' AND lease_expires_at IS NOT NULL))
);

CREATE INDEX idx_ops_job_queue_claim
ON ops.job_queue (available_at, created_at)
WHERE status = 'queued';

CREATE INDEX idx_ops_job_queue_expired_lease
ON ops.job_queue (lease_expires_at, available_at, created_at)
WHERE status = 'running';

CREATE TABLE ops.audit_events (
    id uuid PRIMARY KEY,
    user_id uuid REFERENCES identity.users(id) ON DELETE SET NULL,
    event_type text NOT NULL CHECK (length(event_type) BETWEEN 1 AND 128),
    subject_key text NOT NULL CHECK (length(subject_key) BETWEEN 1 AND 256),
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (
        jsonb_typeof(payload_json) = 'object'
        AND octet_length(payload_json::text) <= 8192
    ),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (event_type, subject_key)
);

CREATE INDEX idx_ops_audit_events_created
ON ops.audit_events (created_at DESC, id DESC);

CREATE TABLE ops.usage_counters (
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    counter_key text NOT NULL CHECK (length(counter_key) BETWEEN 1 AND 128),
    window_start timestamptz NOT NULL,
    window_end timestamptz NOT NULL,
    value bigint NOT NULL DEFAULT 0 CHECK (value >= 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, counter_key, window_start),
    CHECK (window_end > window_start)
);

GRANT USAGE ON SCHEMA identity, chat, simc, ops TO wow_app;

GRANT SELECT, INSERT, UPDATE
ON identity.users, identity.user_identities, identity.auth_sessions, identity.web_login_sessions
TO wow_app;

GRANT SELECT, INSERT, UPDATE
ON chat.conversations, chat.agent_runs
TO wow_app;

GRANT SELECT, INSERT
ON chat.messages
TO wow_app;

GRANT SELECT, INSERT, UPDATE
ON simc.simulation_jobs, simc.simulation_attempts
TO wow_app;

GRANT SELECT, INSERT
ON simc.source_snapshots
TO wow_app;

GRANT SELECT, INSERT
ON simc.simulation_results
TO wow_app;

GRANT SELECT
ON ops.schema_migrations
TO wow_app;

GRANT SELECT, INSERT, UPDATE
ON ops.job_queue
TO wow_app;

GRANT SELECT, INSERT, UPDATE
ON ops.usage_counters
TO wow_app;

GRANT SELECT, INSERT
ON ops.audit_events
TO wow_app;

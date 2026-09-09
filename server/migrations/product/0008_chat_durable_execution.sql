-- Additive only: old runtime can ignore these tables after a drained rollback.
CREATE TABLE chat.executions (
    run_id uuid PRIMARY KEY REFERENCES chat.agent_runs(id),
    user_id uuid NOT NULL REFERENCES identity.users(id),
    stage text NOT NULL DEFAULT 'pending' CHECK (stage IN ('pending','running','succeeded','failed')),
    lease_token uuid,
    lease_expires_at timestamptz,
    heartbeat_at timestamptz,
    execution_started_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    draft_answer text NOT NULL DEFAULT '' CHECK (char_length(draft_answer) <= 8000),
    interruption_reason text NOT NULL DEFAULT '',
    CHECK ((stage = 'running') = (lease_token IS NOT NULL AND lease_expires_at IS NOT NULL))
);
CREATE INDEX chat_executions_pending ON chat.executions(created_at) WHERE stage='pending';
CREATE INDEX chat_executions_lease ON chat.executions(lease_expires_at) WHERE stage='running';

CREATE TABLE chat.tool_results (
    run_id uuid NOT NULL REFERENCES chat.executions(run_id),
    call_id uuid NOT NULL,
    operation text NOT NULL,
    request_hash text NOT NULL,
    state text NOT NULL CHECK (state IN ('started','completed','failed')),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    result_json jsonb,
    PRIMARY KEY(run_id, call_id),
    CHECK (octet_length(result_json::text) <= 1048576)
);
GRANT SELECT, INSERT, UPDATE ON chat.executions, chat.tool_results TO wow_app;

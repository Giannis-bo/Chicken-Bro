CREATE TABLE IF NOT EXISTS app.chickenbro_agent_traces (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    session_id uuid NOT NULL REFERENCES app.chickenbro_sessions(id) ON DELETE CASCADE,
    user_message_id uuid NOT NULL REFERENCES app.chickenbro_messages(id) ON DELETE CASCADE,
    agent_job_id uuid NOT NULL REFERENCES app.agent_jobs(id) ON DELETE CASCADE,
    schema_revision text NOT NULL,
    runtime_version text NOT NULL,
    answer_status text NOT NULL,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (agent_job_id)
);

CREATE INDEX IF NOT EXISTS idx_chickenbro_agent_traces_owner_created
ON app.chickenbro_agent_traces (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chickenbro_agent_traces_session_created
ON app.chickenbro_agent_traces (session_id, created_at);

REVOKE UPDATE, DELETE ON app.chickenbro_agent_traces FROM wow_app;
GRANT SELECT, INSERT ON app.chickenbro_agent_traces TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0024_chickenbro_agent_observability',
    'Add owner-bound Chickenbro agent traces for bounded observability'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

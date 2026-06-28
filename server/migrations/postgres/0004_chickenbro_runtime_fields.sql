ALTER TABLE app.chickenbro_messages
ADD COLUMN IF NOT EXISTS agent_job_id uuid;

ALTER TABLE app.agent_jobs
ADD COLUMN IF NOT EXISTS bounded_context_json jsonb NOT NULL DEFAULT '{}'::jsonb;

DO $$
BEGIN
    ALTER TABLE app.chickenbro_messages
    ADD CONSTRAINT chickenbro_messages_agent_job_id_fkey
    FOREIGN KEY (agent_job_id) REFERENCES app.agent_jobs(id) ON DELETE SET NULL;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0004_chickenbro_runtime_fields',
    'Add Chickenbro message agent-job link and bounded context runtime fields'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

ALTER TABLE chat.agent_runs
ADD COLUMN idempotency_key text;

UPDATE chat.agent_runs
SET idempotency_key = 'legacy-' || id::text
WHERE idempotency_key IS NULL;

ALTER TABLE chat.agent_runs
ALTER COLUMN idempotency_key SET NOT NULL;

ALTER TABLE chat.agent_runs
ADD CONSTRAINT chat_agent_runs_idempotency_key_length
    CHECK (length(idempotency_key) BETWEEN 1 AND 128),
ADD CONSTRAINT chat_agent_runs_user_idempotency_unique
    UNIQUE (user_id, idempotency_key),
ADD CONSTRAINT chat_agent_runs_user_message_unique
    UNIQUE (user_id, user_message_id);

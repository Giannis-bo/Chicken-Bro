-- Additive lifecycle state; old releases can coexist and rollback without data loss.
CREATE TABLE chat.research_sessions (
    id uuid PRIMARY KEY,
    ordinal bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    user_id uuid NOT NULL REFERENCES identity.users(id),
    conversation_id uuid NOT NULL REFERENCES chat.conversations(id),
    state text NOT NULL CHECK (state IN ('active', 'ended')),
    budget jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    ended_at timestamptz,
    UNIQUE (id, user_id, conversation_id)
);
CREATE UNIQUE INDEX research_one_active_conversation
    ON chat.research_sessions(conversation_id) WHERE state='active';
CREATE TABLE chat.research_runs (
    run_id uuid PRIMARY KEY REFERENCES chat.agent_runs(id),
    research_id uuid NOT NULL,
    user_id uuid NOT NULL,
    conversation_id uuid NOT NULL,
    FOREIGN KEY (research_id, user_id, conversation_id)
        REFERENCES chat.research_sessions(id, user_id, conversation_id)
);

GRANT SELECT, INSERT, UPDATE ON chat.research_sessions, chat.research_runs TO wow_app;
GRANT USAGE, SELECT ON SEQUENCE chat.research_sessions_ordinal_seq TO wow_app;

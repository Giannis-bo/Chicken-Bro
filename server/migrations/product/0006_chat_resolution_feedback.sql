-- Feedback belongs to the completed answer's run, which already binds its
-- owner, question, answer, conversation and runtime revision. NULL = unrated.
ALTER TABLE chat.agent_runs
    ADD COLUMN resolved boolean,
    ADD COLUMN feedback_updated_at timestamptz,
    ADD CONSTRAINT agent_runs_feedback_completed CHECK (
        (resolved IS NULL AND feedback_updated_at IS NULL)
        OR (resolved IS NOT NULL AND feedback_updated_at IS NOT NULL AND status = 'succeeded')
    );

CREATE INDEX agent_runs_unresolved_feedback
    ON chat.agent_runs (feedback_updated_at DESC, id) WHERE resolved = false;

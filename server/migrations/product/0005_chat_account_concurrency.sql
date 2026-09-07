-- Reject overlapping replies across all conversations and client transports.
-- If old concurrent runs exist, migration fails without rewriting user history.
-- Drain active replies before applying; do not forcibly terminate them here.
CREATE UNIQUE INDEX agent_runs_one_streaming_per_user
    ON chat.agent_runs (user_id) WHERE status = 'streaming';

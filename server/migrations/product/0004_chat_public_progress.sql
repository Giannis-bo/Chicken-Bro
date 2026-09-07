-- Public summaries only. Raw model reasoning and tool payloads are never stored.
ALTER TABLE chat.agent_runs ADD COLUMN public_progress text NOT NULL DEFAULT ''
    CHECK (length(public_progress) <= 16000);

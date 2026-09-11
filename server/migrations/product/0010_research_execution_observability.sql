-- Additive: old runtime ignores these per-run execution counters and receipts.
ALTER TABLE chat.research_runs ADD COLUMN work jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE chat.agent_runs ADD COLUMN model_usage jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE chat.tool_results ADD COLUMN request_json jsonb;
CREATE INDEX chat_tool_results_request_lookup ON chat.tool_results(operation,request_hash,started_at DESC)
    WHERE state='completed';

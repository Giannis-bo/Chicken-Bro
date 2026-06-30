CREATE TABLE IF NOT EXISTS ops.admin_gate_diagnoses (
    id text PRIMARY KEY,
    target_domain text NOT NULL,
    target_type text NOT NULL,
    target_id text NOT NULL,
    diagnosis text NOT NULL,
    gap_type text NOT NULL,
    reason text NOT NULL,
    note text NOT NULL DEFAULT '',
    actor text NOT NULL DEFAULT '',
    target_fingerprint text NOT NULL DEFAULT '',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_ops_admin_gate_diagnoses_target
ON ops.admin_gate_diagnoses (target_domain, target_type, target_id, created_at DESC);

GRANT SELECT, INSERT, UPDATE, DELETE ON ops.admin_gate_diagnoses TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0010_admin_gate_diagnostics',
    'Add PostgreSQL ops admin gate diagnosis records for the admin gate governance runtime'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

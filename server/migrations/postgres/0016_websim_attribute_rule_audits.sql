CREATE TABLE IF NOT EXISTS ops.websim_attribute_rule_audits (
    audit_key text PRIMARY KEY
        CHECK (audit_key ~ '^attribute-audit:sha256:[0-9a-f]{64}$'),
    candidate_community_release_id text NOT NULL
        REFERENCES cache.websim_release_registry(release_id) ON DELETE RESTRICT,
    candidate_gear_release_id text NOT NULL
        REFERENCES cache.websim_release_registry(release_id) ON DELETE RESTRICT,
    manifest_revision text NOT NULL
        REFERENCES cache.websim_season_manifests(manifest_revision) ON DELETE RESTRICT,
    attribute_rule_revision text NOT NULL CHECK (length(attribute_rule_revision) BETWEEN 1 AND 256),
    context_key text NOT NULL CHECK (length(context_key) BETWEEN 1 AND 256),
    status text NOT NULL CHECK (status IN (
        'pending', 'running', 'not_applicable', 'blocked_missing_evidence',
        'blocked_source_unavailable', 'inconclusive_input_mismatch', 'pass', 'confirmed_mismatch'
    )),
    canonical_input_signature text NOT NULL
        CHECK (canonical_input_signature ~ '^sha256:[0-9a-f]{64}$'),
    input_json jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (octet_length(input_json::text) <= 131072),
    result_json jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (octet_length(result_json::text) <= 65536),
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt BETWEEN 0 AND 3),
    locked_by text NOT NULL DEFAULT '' CHECK (length(locked_by) <= 160),
    lock_token text NOT NULL DEFAULT '' CHECK (length(lock_token) <= 160),
    lease_until timestamptz,
    queued_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (status = 'running' AND locked_by <> '' AND lock_token <> '' AND lease_until IS NOT NULL)
        OR (status <> 'running' AND lease_until IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_ops_websim_attribute_rule_audits_claim
ON ops.websim_attribute_rule_audits (status, queued_at, audit_key);

CREATE INDEX IF NOT EXISTS idx_ops_websim_attribute_rule_audits_findings
ON ops.websim_attribute_rule_audits (attribute_rule_revision, status, finished_at DESC);

REVOKE DELETE ON ops.websim_attribute_rule_audits FROM wow_app;
GRANT SELECT, INSERT, UPDATE ON ops.websim_attribute_rule_audits TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0016_websim_attribute_rule_audits',
    'Add fenced winner-driven attribute rule audit ledger with bounded input and result evidence'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

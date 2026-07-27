ALTER TABLE ops.websim_gear_evidence_gaps
    DROP CONSTRAINT IF EXISTS websim_gear_evidence_gaps_status_check;

ALTER TABLE ops.websim_gear_evidence_gaps
    ADD CONSTRAINT websim_gear_evidence_gaps_status_check
    CHECK (status IN (
        'pending', 'running', 'retryable', 'candidate_pending',
        'candidate_running', 'manual_pending', 'terminal'
    ));

ALTER TABLE ops.websim_gear_evidence_gaps
    DROP CONSTRAINT IF EXISTS websim_gear_evidence_gaps_problem_code_check;

ALTER TABLE ops.websim_gear_evidence_gaps
    ADD CONSTRAINT websim_gear_evidence_gaps_problem_code_check
    CHECK (problem_code IN (
        'artifact_missing',
        'source_unavailable',
        'parser_unhandled_shape',
        'observation_conflict',
        'compiler_policy_missing',
        'projection_contract_regression',
        'unverified_observed_capacity'
    ));

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0021_gear_evidence_manual_pending',
    'Keep unresolved raw gem occupancy open for a trusted exact-item socket probe'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

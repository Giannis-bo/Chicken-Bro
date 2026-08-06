DO $preflight$
DECLARE
    role_can_login boolean;
BEGIN
    SELECT rolcanlogin
    INTO role_can_login
    FROM pg_catalog.pg_roles
    WHERE rolname = 'wow_exact_worker';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'pre-provisioned wow_exact_worker role is required';
    END IF;
    IF role_can_login IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'wow_exact_worker must remain NOLOGIN';
    END IF;
    IF pg_catalog.to_regprocedure('pg_catalog.gen_random_uuid()') IS NULL THEN
        RAISE EXCEPTION 'PostgreSQL core pg_catalog.gen_random_uuid() is required';
    END IF;
END;
$preflight$;

CREATE TABLE ops.websim_exact_import_jobs (
    job_id bigserial PRIMARY KEY,
    owner_key_hash text NOT NULL
        CHECK (owner_key_hash ~ '^sha256:[0-9a-f]{64}$'),
    request_key text NOT NULL
        CHECK (request_key ~ '^exact-import-request:sha256:[0-9a-f]{64}$'),
    request_bytes bytea NOT NULL
        CHECK (pg_catalog.octet_length(request_bytes) BETWEEN 2 AND 131072),
    request_json jsonb NOT NULL
        CHECK (pg_catalog.jsonb_typeof(request_json) = 'object')
        CHECK (pg_catalog.octet_length(request_json::text) <= 131072),
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'resolved', 'blocked', 'unsupported', 'failed')),
    terminal_classification text
        CHECK (
            terminal_classification IS NULL
            OR terminal_classification IN ('resolved', 'incomplete', 'illegal', 'runtime_gap', 'internal_error')
        ),
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt BETWEEN 0 AND 3),
    locked_by text
        CHECK (
            locked_by IS NULL
            OR (
                pg_catalog.octet_length(locked_by) BETWEEN 1 AND 160
                AND locked_by = pg_catalog.btrim(locked_by)
            )
        ),
    lock_token uuid,
    lease_until timestamptz,
    queued_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    started_at timestamptz,
    heartbeat_at timestamptz,
    finished_at timestamptz,
    cooldown_until timestamptz,
    result_json jsonb
        CHECK (
            result_json IS NULL
            OR (
                pg_catalog.jsonb_typeof(result_json) = 'object'
                AND pg_catalog.octet_length(result_json::text) <= 131072
                AND NOT pg_catalog.jsonb_path_exists(
                    result_json,
                    '$.**.keyvalue() ? (@.key == "rawProfile" || @.key == "rawString" || @.key == "playerName" || @.key == "characterName" || @.key == "realm" || @.key == "server")'::pg_catalog.jsonpath
                )
            )
        ),
    problem_json jsonb
        CHECK (
            problem_json IS NULL
            OR (
                pg_catalog.jsonb_typeof(problem_json) = 'object'
                AND pg_catalog.octet_length(problem_json::text) <= 16384
                AND NOT pg_catalog.jsonb_path_exists(
                    problem_json,
                    '$.**.keyvalue() ? (@.key == "rawProfile" || @.key == "rawString" || @.key == "playerName" || @.key == "characterName" || @.key == "realm" || @.key == "server")'::pg_catalog.jsonpath
                )
            )
        ),
    created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    CHECK (
        request_json = pg_catalog.convert_from(request_bytes, 'UTF8')::jsonb
    ),
    CHECK (
        request_key = 'exact-import-request:sha256:' ||
            pg_catalog.encode(pg_catalog.sha256(request_bytes), 'hex')
    ),
    CHECK (
        request_json ?& ARRAY[
            'schemaRevision', 'exactLoadoutIntent', 'dependencyVector'
        ]
        AND request_json - ARRAY[
            'schemaRevision', 'exactLoadoutIntent', 'dependencyVector'
        ] = '{}'::jsonb
        AND request_json ->> 'schemaRevision' = 'exact-import-job-request-v1'
        AND pg_catalog.jsonb_typeof(request_json -> 'exactLoadoutIntent') = 'object'
        AND pg_catalog.jsonb_typeof(request_json -> 'dependencyVector') = 'object'
        AND request_json -> 'dependencyVector' ?& ARRAY[
            'seasonRevision', 'gameBuild', 'gearRuleRevision',
            'resolverRevision', 'compilerRevision', 'workerRevision',
            'simcRuntimeRevision', 'effectAuthorityRevision'
        ]
        AND (request_json -> 'dependencyVector') - ARRAY[
            'seasonRevision', 'gameBuild', 'gearRuleRevision',
            'resolverRevision', 'compilerRevision', 'workerRevision',
            'simcRuntimeRevision', 'effectAuthorityRevision'
        ] = '{}'::jsonb
    ),
    CHECK (
        NOT pg_catalog.jsonb_path_exists(
            request_json,
            '$.**.keyvalue() ? (@.key == "rawProfile" || @.key == "rawString" || @.key == "playerName" || @.key == "characterName" || @.key == "realm" || @.key == "server")'::pg_catalog.jsonpath
        )
    ),
    CHECK (
        (
            status = 'pending'
            AND attempt = 0
            AND locked_by IS NULL
            AND lock_token IS NULL
            AND lease_until IS NULL
            AND started_at IS NULL
            AND heartbeat_at IS NULL
            AND finished_at IS NULL
            AND cooldown_until IS NULL
            AND terminal_classification IS NULL
            AND result_json IS NULL
            AND problem_json IS NULL
        )
        OR (
            status = 'running'
            AND attempt BETWEEN 1 AND 3
            AND locked_by IS NOT NULL
            AND lock_token IS NOT NULL
            AND lease_until IS NOT NULL
            AND started_at IS NOT NULL
            AND heartbeat_at IS NOT NULL
            AND lease_until = heartbeat_at + interval '30 seconds'
            AND finished_at IS NULL
            AND cooldown_until IS NULL
            AND terminal_classification IS NULL
            AND result_json IS NULL
            AND problem_json IS NULL
        )
        OR (
            status = 'resolved'
            AND attempt BETWEEN 1 AND 3
            AND locked_by IS NULL
            AND lock_token IS NULL
            AND lease_until IS NULL
            AND started_at IS NOT NULL
            AND finished_at IS NOT NULL
            AND cooldown_until IS NULL
            AND terminal_classification = 'resolved'
        )
        OR (
            status = 'blocked'
            AND attempt BETWEEN 1 AND 3
            AND locked_by IS NULL
            AND lock_token IS NULL
            AND lease_until IS NULL
            AND started_at IS NOT NULL
            AND finished_at IS NOT NULL
            AND cooldown_until IS NULL
            AND terminal_classification IN ('incomplete', 'illegal')
        )
        OR (
            status = 'unsupported'
            AND attempt BETWEEN 1 AND 3
            AND locked_by IS NULL
            AND lock_token IS NULL
            AND lease_until IS NULL
            AND started_at IS NOT NULL
            AND finished_at IS NOT NULL
            AND cooldown_until IS NULL
            AND terminal_classification = 'runtime_gap'
        )
        OR (
            status = 'failed'
            AND attempt BETWEEN 1 AND 3
            AND locked_by IS NULL
            AND lock_token IS NULL
            AND lease_until IS NULL
            AND started_at IS NOT NULL
            AND finished_at IS NOT NULL
            AND terminal_classification = 'internal_error'
            AND cooldown_until = finished_at + interval '15 minutes'
        )
    ),
    CHECK (
        status NOT IN ('resolved', 'blocked', 'unsupported', 'failed')
        OR finished_at >= started_at
    ),
    CHECK (updated_at >= created_at)
);

COMMENT ON TABLE ops.websim_exact_import_jobs IS
    'retryPolicyRevision=exact-import-retry-policy-v1; totalClaims=3; lease=30 seconds; failedCooldown=15 minutes';

CREATE UNIQUE INDEX uq_ops_websim_exact_jobs_deterministic
ON ops.websim_exact_import_jobs (owner_key_hash, request_key)
WHERE status IN ('pending', 'running', 'resolved', 'blocked', 'unsupported');

CREATE INDEX idx_ops_websim_exact_jobs_failed_cooldown
ON ops.websim_exact_import_jobs (owner_key_hash, request_key, cooldown_until DESC, job_id DESC)
WHERE status = 'failed';

CREATE INDEX idx_ops_websim_exact_jobs_claim
ON ops.websim_exact_import_jobs (status, lease_until, queued_at, job_id);

CREATE INDEX idx_ops_websim_exact_jobs_retention
ON ops.websim_exact_import_jobs (finished_at, job_id)
WHERE status IN ('resolved', 'blocked', 'unsupported', 'failed');

CREATE TABLE ops.websim_exact_worker_state (
    worker_id text PRIMARY KEY
        CHECK (
            pg_catalog.octet_length(worker_id) BETWEEN 1 AND 160
            AND worker_id = pg_catalog.btrim(worker_id)
        ),
    worker_revision text NOT NULL
        CHECK (pg_catalog.octet_length(worker_revision) BETWEEN 1 AND 256),
    simc_runtime_revision text NOT NULL
        CHECK (pg_catalog.octet_length(simc_runtime_revision) BETWEEN 1 AND 256),
    current_job_id bigint
        REFERENCES ops.websim_exact_import_jobs(job_id) ON DELETE SET NULL,
    status text NOT NULL
        CHECK (status IN ('starting', 'idle', 'running', 'stopped', 'failed')),
    heartbeat_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    last_outcome_json jsonb
        CHECK (
            last_outcome_json IS NULL
            OR (
                pg_catalog.jsonb_typeof(last_outcome_json) = 'object'
                AND pg_catalog.octet_length(last_outcome_json::text) <= 16384
                AND NOT pg_catalog.jsonb_path_exists(
                    last_outcome_json,
                    '$.**.keyvalue() ? (@.key == "rawProfile" || @.key == "rawString" || @.key == "playerName" || @.key == "characterName" || @.key == "realm" || @.key == "server")'::pg_catalog.jsonpath
                )
            )
        ),
    updated_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp()
);

CREATE TABLE ops.websim_exact_import_metrics_daily (
    metric_day date NOT NULL,
    terminal_classification text NOT NULL
        CHECK (terminal_classification IN ('resolved', 'incomplete', 'illegal', 'runtime_gap', 'internal_error')),
    catalog_status text NOT NULL
        CHECK (
            pg_catalog.octet_length(catalog_status) BETWEEN 1 AND 256
            AND catalog_status = pg_catalog.btrim(catalog_status)
        ),
    outcome_count bigint NOT NULL CHECK (outcome_count >= 1),
    first_outcome_at timestamptz NOT NULL,
    last_outcome_at timestamptz NOT NULL,
    PRIMARY KEY (metric_day, terminal_classification, catalog_status),
    CHECK (last_outcome_at >= first_outcome_at)
);

CREATE OR REPLACE FUNCTION ops.websim_exact_enqueue(
    p_owner_key_hash text,
    p_request_bytes bytea,
    p_request_json jsonb
)
RETURNS TABLE(
    job_id bigint,
    request_key text,
    status text,
    reused boolean,
    cooldown_until timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
DECLARE
    observed_at timestamptz;
    computed_request_key text;
    existing_job ops.websim_exact_import_jobs%ROWTYPE;
BEGIN
    IF p_owner_key_hash IS NULL
       OR p_owner_key_hash !~ '^sha256:[0-9a-f]{64}$'
       OR p_request_bytes IS NULL
       OR pg_catalog.octet_length(p_request_bytes) NOT BETWEEN 2 AND 131072
       OR pg_catalog.jsonb_typeof(p_request_json) IS DISTINCT FROM 'object'
       OR pg_catalog.octet_length(p_request_json::text) > 131072
       OR p_request_json IS DISTINCT FROM
          pg_catalog.convert_from(p_request_bytes, 'UTF8')::jsonb
       OR p_request_json ->> 'schemaRevision'
          IS DISTINCT FROM 'exact-import-job-request-v1'
       OR NOT p_request_json ?& ARRAY[
          'schemaRevision', 'exactLoadoutIntent', 'dependencyVector'
       ]
       OR p_request_json - ARRAY[
          'schemaRevision', 'exactLoadoutIntent', 'dependencyVector'
       ] <> '{}'::jsonb
       OR pg_catalog.jsonb_typeof(p_request_json -> 'exactLoadoutIntent')
          IS DISTINCT FROM 'object'
       OR pg_catalog.jsonb_typeof(p_request_json -> 'dependencyVector')
          IS DISTINCT FROM 'object'
       OR NOT (p_request_json -> 'dependencyVector') ?& ARRAY[
          'seasonRevision', 'gameBuild', 'gearRuleRevision',
          'resolverRevision', 'compilerRevision', 'workerRevision',
          'simcRuntimeRevision', 'effectAuthorityRevision'
       ]
       OR (p_request_json -> 'dependencyVector') - ARRAY[
          'seasonRevision', 'gameBuild', 'gearRuleRevision',
          'resolverRevision', 'compilerRevision', 'workerRevision',
          'simcRuntimeRevision', 'effectAuthorityRevision'
       ] <> '{}'::jsonb
       OR pg_catalog.jsonb_path_exists(
          p_request_json,
          '$.**.keyvalue() ? (@.key == "rawProfile" || @.key == "rawString" || @.key == "playerName" || @.key == "characterName" || @.key == "realm" || @.key == "server")'::pg_catalog.jsonpath
       )
    THEN
        RAISE EXCEPTION 'invalid exact import request'
            USING ERRCODE = '22023';
    END IF;

    computed_request_key := 'exact-import-request:sha256:' ||
        pg_catalog.encode(pg_catalog.sha256(p_request_bytes), 'hex');
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            p_owner_key_hash || ':' || computed_request_key,
            0
        )
    );
    observed_at := pg_catalog.clock_timestamp();

    SELECT jobs.*
    INTO existing_job
    FROM ops.websim_exact_import_jobs AS jobs
    WHERE jobs.owner_key_hash = p_owner_key_hash
      AND jobs.request_key = computed_request_key
      AND jobs.status IN ('pending', 'running', 'resolved', 'blocked', 'unsupported')
    ORDER BY jobs.job_id DESC
    LIMIT 1;
    IF FOUND THEN
        IF existing_job.request_bytes IS DISTINCT FROM p_request_bytes
           OR existing_job.request_json IS DISTINCT FROM p_request_json
        THEN
            RAISE EXCEPTION 'exact import request byte collision'
                USING ERRCODE = '22000';
        END IF;
        RETURN QUERY SELECT
            existing_job.job_id,
            existing_job.request_key,
            existing_job.status,
            true,
            existing_job.cooldown_until;
        RETURN;
    END IF;

    SELECT jobs.*
    INTO existing_job
    FROM ops.websim_exact_import_jobs AS jobs
    WHERE jobs.owner_key_hash = p_owner_key_hash
      AND jobs.request_key = computed_request_key
      AND jobs.status = 'failed'
      AND jobs.cooldown_until > observed_at
    ORDER BY jobs.cooldown_until DESC, jobs.job_id DESC
    LIMIT 1;
    IF FOUND THEN
        IF existing_job.request_bytes IS DISTINCT FROM p_request_bytes
           OR existing_job.request_json IS DISTINCT FROM p_request_json
        THEN
            RAISE EXCEPTION 'exact import failed request byte collision'
                USING ERRCODE = '22000';
        END IF;
        RETURN QUERY SELECT
            existing_job.job_id,
            existing_job.request_key,
            existing_job.status,
            true,
            existing_job.cooldown_until;
        RETURN;
    END IF;

    RETURN QUERY
    WITH inserted AS (
        INSERT INTO ops.websim_exact_import_jobs (
            owner_key_hash,
            request_key,
            request_bytes,
            request_json,
            status,
            attempt,
            queued_at,
            created_at,
            updated_at
        )
        VALUES (
            p_owner_key_hash,
            computed_request_key,
            p_request_bytes,
            p_request_json,
            'pending',
            0,
            observed_at,
            observed_at,
            observed_at
        )
        RETURNING
            websim_exact_import_jobs.job_id,
            websim_exact_import_jobs.request_key,
            websim_exact_import_jobs.status,
            websim_exact_import_jobs.cooldown_until
    )
    SELECT
        inserted.job_id,
        inserted.request_key,
        inserted.status,
        false,
        inserted.cooldown_until
    FROM inserted;
END;
$function$;

CREATE OR REPLACE FUNCTION ops.websim_exact_read(
    p_owner_key_hash text,
    p_job_id bigint
)
RETURNS TABLE(
    job_id bigint,
    request_key text,
    status text,
    result_json jsonb,
    problem_json jsonb,
    queued_at timestamptz,
    started_at timestamptz,
    finished_at timestamptz,
    cooldown_until timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
BEGIN
    IF p_owner_key_hash IS NULL
       OR p_owner_key_hash !~ '^sha256:[0-9a-f]{64}$'
       OR p_job_id IS NULL
       OR p_job_id <= 0
    THEN
        RAISE EXCEPTION 'invalid exact import read identity'
            USING ERRCODE = '22023';
    END IF;
    RETURN QUERY
    SELECT
        jobs.job_id,
        jobs.request_key,
        jobs.status,
        jobs.result_json,
        jobs.problem_json,
        jobs.queued_at,
        jobs.started_at,
        jobs.finished_at,
        jobs.cooldown_until
    FROM ops.websim_exact_import_jobs AS jobs
    WHERE jobs.owner_key_hash = p_owner_key_hash
      AND jobs.job_id = p_job_id;
END;
$function$;

CREATE OR REPLACE FUNCTION ops.websim_exact_claim(
    p_worker_id text,
    p_worker_revision text,
    p_simc_runtime_revision text
)
RETURNS TABLE(
    job_id bigint,
    request_key text,
    request_bytes bytea,
    request_json jsonb,
    lock_token uuid,
    lease_until timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
DECLARE
    observed_at timestamptz := pg_catalog.clock_timestamp();
    candidate ops.websim_exact_import_jobs%ROWTYPE;
BEGIN
    IF p_worker_id IS NULL
       OR pg_catalog.octet_length(p_worker_id) NOT BETWEEN 1 AND 160
       OR p_worker_id <> pg_catalog.btrim(p_worker_id)
       OR p_worker_revision IS NULL
       OR pg_catalog.octet_length(p_worker_revision) NOT BETWEEN 1 AND 256
       OR p_simc_runtime_revision IS NULL
       OR pg_catalog.octet_length(p_simc_runtime_revision) NOT BETWEEN 1 AND 256
    THEN
        RAISE EXCEPTION 'invalid exact import worker identity'
            USING ERRCODE = '22023';
    END IF;

    WITH exhausted AS (
        SELECT jobs.job_id
        FROM ops.websim_exact_import_jobs AS jobs
        WHERE jobs.status = 'running'
          AND jobs.attempt = 3
          AND jobs.lease_until <= observed_at
        ORDER BY jobs.lease_until, jobs.queued_at, jobs.job_id
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    ), terminal AS (
        UPDATE ops.websim_exact_import_jobs AS jobs
        SET status = 'failed',
            terminal_classification = 'internal_error',
            locked_by = NULL,
            lock_token = NULL,
            lease_until = NULL,
            finished_at = observed_at,
            cooldown_until = observed_at + interval '15 minutes',
            result_json = NULL,
            problem_json = pg_catalog.jsonb_build_object(
                'code', 'ATTEMPT_EXHAUSTED'
            ),
            updated_at = observed_at
        FROM exhausted
        WHERE jobs.job_id = exhausted.job_id
        RETURNING jobs.terminal_classification
    )
    INSERT INTO ops.websim_exact_import_metrics_daily (
        metric_day,
        terminal_classification,
        catalog_status,
        outcome_count,
        first_outcome_at,
        last_outcome_at
    )
    SELECT
        observed_at::date,
        terminal.terminal_classification,
        'unknown',
        1,
        observed_at,
        observed_at
    FROM terminal
    ON CONFLICT (metric_day, terminal_classification, catalog_status)
    DO UPDATE SET
        outcome_count =
            ops.websim_exact_import_metrics_daily.outcome_count + 1,
        first_outcome_at = LEAST(ops.websim_exact_import_metrics_daily.first_outcome_at, EXCLUDED.first_outcome_at),
        last_outcome_at = GREATEST(ops.websim_exact_import_metrics_daily.last_outcome_at, EXCLUDED.last_outcome_at);

    observed_at := pg_catalog.clock_timestamp();

    SELECT jobs.*
    INTO candidate
    FROM ops.websim_exact_import_jobs AS jobs
    WHERE (
            jobs.status = 'pending'
            AND jobs.attempt < 3
        )
       OR (
            jobs.status = 'running'
            AND jobs.attempt < 3
            AND jobs.lease_until <= observed_at
        )
    ORDER BY
        CASE WHEN jobs.status = 'running' THEN 0 ELSE 1 END,
        jobs.lease_until NULLS LAST,
        jobs.queued_at,
        jobs.job_id
    FOR UPDATE SKIP LOCKED
    LIMIT 1;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    IF candidate.request_key IS DISTINCT FROM
       'exact-import-request:sha256:' ||
           pg_catalog.encode(pg_catalog.sha256(candidate.request_bytes), 'hex')
       OR candidate.request_json IS DISTINCT FROM
          pg_catalog.convert_from(candidate.request_bytes, 'UTF8')::jsonb
       OR candidate.request_json ->> 'schemaRevision'
          IS DISTINCT FROM 'exact-import-job-request-v1'
       OR candidate.request_json - ARRAY[
          'schemaRevision', 'exactLoadoutIntent', 'dependencyVector'
       ] <> '{}'::jsonb
       OR (candidate.request_json -> 'dependencyVector') - ARRAY[
          'seasonRevision', 'gameBuild', 'gearRuleRevision',
          'resolverRevision', 'compilerRevision', 'workerRevision',
          'simcRuntimeRevision', 'effectAuthorityRevision'
       ] <> '{}'::jsonb
       OR pg_catalog.jsonb_path_exists(
          candidate.request_json,
          '$.**.keyvalue() ? (@.key == "rawProfile" || @.key == "rawString" || @.key == "playerName" || @.key == "characterName" || @.key == "realm" || @.key == "server")'::pg_catalog.jsonpath
       )
    THEN
        RAISE EXCEPTION 'claimed exact import request drift'
            USING ERRCODE = '22000';
    END IF;

    RETURN QUERY
    UPDATE ops.websim_exact_import_jobs AS jobs
    SET status = 'running',
        attempt = candidate.attempt + 1,
        locked_by = p_worker_id,
        lock_token = pg_catalog.gen_random_uuid(),
        lease_until = observed_at + interval '30 seconds',
        started_at = COALESCE(candidate.started_at, observed_at),
        heartbeat_at = observed_at,
        finished_at = NULL,
        cooldown_until = NULL,
        terminal_classification = NULL,
        result_json = NULL,
        problem_json = NULL,
        updated_at = observed_at
    WHERE jobs.job_id = candidate.job_id
    RETURNING
        jobs.job_id,
        jobs.request_key,
        jobs.request_bytes,
        jobs.request_json,
        jobs.lock_token,
        jobs.lease_until;
END;
$function$;

CREATE OR REPLACE FUNCTION ops.websim_exact_heartbeat(
    p_job_id bigint,
    p_lock_token uuid
)
RETURNS TABLE(job_id bigint, lease_until timestamptz)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
DECLARE
    observed_at timestamptz;
    candidate record;
BEGIN
    IF p_job_id IS NULL OR p_job_id <= 0 OR p_lock_token IS NULL THEN
        RAISE EXCEPTION 'invalid exact import heartbeat identity'
            USING ERRCODE = '22023';
    END IF;

    SELECT jobs.* INTO candidate
    FROM ops.websim_exact_import_jobs AS jobs
    WHERE jobs.job_id = p_job_id
      AND jobs.status = 'running'
      AND jobs.lock_token = p_lock_token
    FOR UPDATE;
    IF NOT FOUND THEN
        RETURN;
    END IF;
    observed_at := pg_catalog.clock_timestamp();
    IF candidate.lease_until <= observed_at THEN
        RETURN;
    END IF;

    RETURN QUERY
    UPDATE ops.websim_exact_import_jobs AS jobs
    SET lease_until = observed_at + interval '30 seconds',
        heartbeat_at = observed_at,
        updated_at = observed_at
    WHERE jobs.job_id = p_job_id
      AND jobs.status = 'running'
      AND jobs.lock_token = p_lock_token
      AND jobs.lease_until > observed_at
    RETURNING jobs.job_id, jobs.lease_until;
END;
$function$;

CREATE OR REPLACE FUNCTION ops.websim_exact_terminalize(
    p_job_id bigint,
    p_lock_token uuid,
    p_terminal_status text,
    p_terminal_classification text,
    p_result_json jsonb,
    p_problem_json jsonb,
    p_catalog_status text
)
RETURNS TABLE(
    job_id bigint,
    status text,
    finished_at timestamptz,
    cooldown_until timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
DECLARE
    observed_at timestamptz;
    candidate record;
BEGIN
    IF p_job_id IS NULL
       OR p_job_id <= 0
       OR p_lock_token IS NULL
       OR p_terminal_status IS NULL
       OR p_terminal_classification IS NULL
       OR p_terminal_status NOT IN ('resolved', 'blocked', 'unsupported', 'failed')
       OR (
            p_terminal_status = 'resolved'
            AND p_terminal_classification IS DISTINCT FROM 'resolved'
       )
       OR (
            p_terminal_status = 'blocked'
            AND p_terminal_classification NOT IN ('incomplete', 'illegal')
       )
       OR (
            p_terminal_status = 'unsupported'
            AND p_terminal_classification IS DISTINCT FROM 'runtime_gap'
       )
       OR (
            p_terminal_status = 'failed'
            AND p_terminal_classification IS DISTINCT FROM 'internal_error'
       )
       OR (
            p_result_json IS NOT NULL
            AND (
                pg_catalog.jsonb_typeof(p_result_json) IS DISTINCT FROM 'object'
                OR pg_catalog.octet_length(p_result_json::text) > 131072
                OR pg_catalog.jsonb_path_exists(
                    p_result_json,
                    '$.**.keyvalue() ? (@.key == "rawProfile" || @.key == "rawString" || @.key == "playerName" || @.key == "characterName" || @.key == "realm" || @.key == "server")'::pg_catalog.jsonpath
                )
            )
       )
       OR (
            p_problem_json IS NOT NULL
            AND (
                pg_catalog.jsonb_typeof(p_problem_json) IS DISTINCT FROM 'object'
                OR pg_catalog.octet_length(p_problem_json::text) > 16384
                OR pg_catalog.jsonb_path_exists(
                    p_problem_json,
                    '$.**.keyvalue() ? (@.key == "rawProfile" || @.key == "rawString" || @.key == "playerName" || @.key == "characterName" || @.key == "realm" || @.key == "server")'::pg_catalog.jsonpath
                )
            )
       )
       OR p_catalog_status IS NULL
       OR pg_catalog.octet_length(p_catalog_status) NOT BETWEEN 1 AND 256
       OR p_catalog_status <> pg_catalog.btrim(p_catalog_status)
    THEN
        RAISE EXCEPTION 'invalid exact import terminal outcome'
            USING ERRCODE = '22023';
    END IF;

    SELECT jobs.* INTO candidate
    FROM ops.websim_exact_import_jobs AS jobs
    WHERE jobs.job_id = p_job_id
      AND jobs.status = 'running'
      AND jobs.lock_token = p_lock_token
    FOR UPDATE;
    IF NOT FOUND THEN
        RETURN;
    END IF;
    observed_at := pg_catalog.clock_timestamp();
    IF candidate.lease_until <= observed_at THEN
        RETURN;
    END IF;

    RETURN QUERY
    WITH terminal AS (
        UPDATE ops.websim_exact_import_jobs AS jobs
        SET status = p_terminal_status,
            terminal_classification = p_terminal_classification,
            locked_by = NULL,
            lock_token = NULL,
            lease_until = NULL,
            finished_at = observed_at,
            cooldown_until = CASE
                WHEN p_terminal_status = 'failed'
                THEN observed_at + interval '15 minutes'
                ELSE NULL
            END,
            result_json = p_result_json,
            problem_json = p_problem_json,
            updated_at = observed_at
        WHERE jobs.job_id = p_job_id
          AND jobs.status = 'running'
          AND jobs.lock_token = p_lock_token
          AND jobs.lease_until > observed_at
        RETURNING
            jobs.job_id,
            jobs.status,
            jobs.terminal_classification,
            jobs.finished_at,
            jobs.cooldown_until
    ), metric AS (
        INSERT INTO ops.websim_exact_import_metrics_daily (
            metric_day,
            terminal_classification,
            catalog_status,
            outcome_count,
            first_outcome_at,
            last_outcome_at
        )
        SELECT
            observed_at::date,
            terminal.terminal_classification,
            p_catalog_status,
            1,
            observed_at,
            observed_at
        FROM terminal
        ON CONFLICT (metric_day, terminal_classification, catalog_status)
        DO UPDATE SET
            outcome_count =
                ops.websim_exact_import_metrics_daily.outcome_count + 1,
            first_outcome_at = LEAST(ops.websim_exact_import_metrics_daily.first_outcome_at, EXCLUDED.first_outcome_at),
            last_outcome_at = GREATEST(ops.websim_exact_import_metrics_daily.last_outcome_at, EXCLUDED.last_outcome_at)
        RETURNING 1
    )
    SELECT
        terminal.job_id,
        terminal.status,
        terminal.finished_at,
        terminal.cooldown_until
    FROM terminal
    CROSS JOIN metric;
END;
$function$;

CREATE OR REPLACE FUNCTION ops.websim_exact_update_worker_state(
    p_worker_id text,
    p_status text,
    p_worker_revision text,
    p_simc_runtime_revision text,
    p_current_job_id bigint,
    p_last_outcome_json jsonb
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
DECLARE
    observed_at timestamptz := pg_catalog.clock_timestamp();
BEGIN
    IF p_worker_id IS NULL
       OR pg_catalog.octet_length(p_worker_id) NOT BETWEEN 1 AND 160
       OR p_worker_id <> pg_catalog.btrim(p_worker_id)
       OR p_status IS NULL
       OR p_status NOT IN ('starting', 'idle', 'running', 'stopped', 'failed')
       OR p_worker_revision IS NULL
       OR pg_catalog.octet_length(p_worker_revision) NOT BETWEEN 1 AND 256
       OR p_simc_runtime_revision IS NULL
       OR pg_catalog.octet_length(p_simc_runtime_revision) NOT BETWEEN 1 AND 256
       OR (
            p_current_job_id IS NOT NULL
            AND p_current_job_id <= 0
       )
       OR (
            p_last_outcome_json IS NOT NULL
            AND (
                pg_catalog.jsonb_typeof(p_last_outcome_json)
                    IS DISTINCT FROM 'object'
                OR pg_catalog.octet_length(p_last_outcome_json::text) > 16384
                OR pg_catalog.jsonb_path_exists(
                    p_last_outcome_json,
                    '$.**.keyvalue() ? (@.key == "rawProfile" || @.key == "rawString" || @.key == "playerName" || @.key == "characterName" || @.key == "realm" || @.key == "server")'::pg_catalog.jsonpath
                )
            )
       )
    THEN
        RAISE EXCEPTION 'invalid exact worker state'
            USING ERRCODE = '22023';
    END IF;

    INSERT INTO ops.websim_exact_worker_state (
        worker_id,
        worker_revision,
        simc_runtime_revision,
        current_job_id,
        status,
        heartbeat_at,
        last_outcome_json,
        updated_at
    )
    VALUES (
        p_worker_id,
        p_worker_revision,
        p_simc_runtime_revision,
        p_current_job_id,
        p_status,
        observed_at,
        p_last_outcome_json,
        observed_at
    )
    ON CONFLICT (worker_id)
    DO UPDATE SET
        worker_revision = EXCLUDED.worker_revision,
        simc_runtime_revision = EXCLUDED.simc_runtime_revision,
        current_job_id = EXCLUDED.current_job_id,
        status = EXCLUDED.status,
        heartbeat_at = EXCLUDED.heartbeat_at,
        last_outcome_json = EXCLUDED.last_outcome_json,
        updated_at = EXCLUDED.updated_at;
END;
$function$;

CREATE OR REPLACE FUNCTION ops.websim_exact_prune_jobs(
    p_limit_rows integer
)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
DECLARE
    deleted_count integer;
BEGIN
    IF p_limit_rows IS NULL OR p_limit_rows NOT BETWEEN 1 AND 100 THEN
        RAISE EXCEPTION 'exact job prune limit must be 1..100'
            USING ERRCODE = '22023';
    END IF;
    WITH doomed AS (
        SELECT jobs.job_id
        FROM ops.websim_exact_import_jobs AS jobs
        WHERE jobs.status IN ('resolved', 'blocked', 'unsupported', 'failed')
          AND jobs.finished_at + interval '7 days' < pg_catalog.clock_timestamp()
        ORDER BY jobs.finished_at, jobs.job_id
        FOR UPDATE SKIP LOCKED
        LIMIT p_limit_rows
    ), deleted AS (
        DELETE FROM ops.websim_exact_import_jobs AS jobs
        USING doomed
        WHERE jobs.job_id = doomed.job_id
        RETURNING jobs.job_id
    )
    SELECT pg_catalog.count(*)::integer
    INTO deleted_count
    FROM deleted;
    RETURN deleted_count;
END;
$function$;

CREATE OR REPLACE FUNCTION ops.websim_exact_prune_metrics(
    p_limit_rows integer
)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
DECLARE
    deleted_count integer;
BEGIN
    IF p_limit_rows IS NULL OR p_limit_rows NOT BETWEEN 1 AND 100 THEN
        RAISE EXCEPTION 'exact metrics prune limit must be 1..100'
            USING ERRCODE = '22023';
    END IF;
    WITH doomed AS (
        SELECT
            metrics.metric_day,
            metrics.terminal_classification,
            metrics.catalog_status
        FROM ops.websim_exact_import_metrics_daily AS metrics
        WHERE metrics.metric_day < pg_catalog.clock_timestamp()::date - 90
        ORDER BY
            metrics.metric_day,
            metrics.terminal_classification,
            metrics.catalog_status
        FOR UPDATE SKIP LOCKED
        LIMIT p_limit_rows
    ), deleted AS (
        DELETE FROM ops.websim_exact_import_metrics_daily AS metrics
        USING doomed
        WHERE metrics.metric_day = doomed.metric_day
          AND metrics.terminal_classification = doomed.terminal_classification
          AND metrics.catalog_status = doomed.catalog_status
        RETURNING metrics.metric_day
    )
    SELECT pg_catalog.count(*)::integer
    INTO deleted_count
    FROM deleted;
    RETURN deleted_count;
END;
$function$;

ALTER FUNCTION ops.websim_exact_enqueue(text, bytea, jsonb)
OWNER TO wow_migrator;
ALTER FUNCTION ops.websim_exact_read(text, bigint)
OWNER TO wow_migrator;
ALTER FUNCTION ops.websim_exact_claim(text, text, text)
OWNER TO wow_migrator;
ALTER FUNCTION ops.websim_exact_heartbeat(bigint, uuid)
OWNER TO wow_migrator;
ALTER FUNCTION ops.websim_exact_terminalize(bigint, uuid, text, text, jsonb, jsonb, text)
OWNER TO wow_migrator;
ALTER FUNCTION ops.websim_exact_update_worker_state(text, text, text, text, bigint, jsonb)
OWNER TO wow_migrator;
ALTER FUNCTION ops.websim_exact_prune_jobs(integer)
OWNER TO wow_migrator;
ALTER FUNCTION ops.websim_exact_prune_metrics(integer)
OWNER TO wow_migrator;

REVOKE ALL ON FUNCTION ops.websim_exact_enqueue(text, bytea, jsonb)
FROM PUBLIC, wow_app, wow_exact_worker;
REVOKE ALL ON FUNCTION ops.websim_exact_read(text, bigint)
FROM PUBLIC, wow_app, wow_exact_worker;
REVOKE ALL ON FUNCTION ops.websim_exact_claim(text, text, text)
FROM PUBLIC, wow_app, wow_exact_worker;
REVOKE ALL ON FUNCTION ops.websim_exact_heartbeat(bigint, uuid)
FROM PUBLIC, wow_app, wow_exact_worker;
REVOKE ALL ON FUNCTION ops.websim_exact_terminalize(bigint, uuid, text, text, jsonb, jsonb, text)
FROM PUBLIC, wow_app, wow_exact_worker;
REVOKE ALL ON FUNCTION ops.websim_exact_update_worker_state(text, text, text, text, bigint, jsonb)
FROM PUBLIC, wow_app, wow_exact_worker;
REVOKE ALL ON FUNCTION ops.websim_exact_prune_jobs(integer)
FROM PUBLIC, wow_app, wow_exact_worker;
REVOKE ALL ON FUNCTION ops.websim_exact_prune_metrics(integer)
FROM PUBLIC, wow_app, wow_exact_worker;

GRANT USAGE ON SCHEMA cache, ops TO wow_exact_worker;
GRANT USAGE ON SCHEMA cache, ops TO wow_migrator;

GRANT SELECT, INSERT, UPDATE, DELETE ON
    ops.websim_exact_import_jobs,
    ops.websim_exact_worker_state,
    ops.websim_exact_import_metrics_daily
TO wow_migrator;

GRANT USAGE, SELECT, UPDATE ON SEQUENCE
    ops.websim_exact_import_jobs_job_id_seq
TO wow_migrator;

REVOKE ALL ON
    ops.websim_exact_import_jobs,
    ops.websim_exact_worker_state,
    ops.websim_exact_import_metrics_daily
FROM PUBLIC, wow_app, wow_exact_worker;

REVOKE ALL ON SEQUENCE ops.websim_exact_import_jobs_job_id_seq
FROM PUBLIC, wow_app, wow_exact_worker;

REVOKE ALL ON
    cache.websim_canonical_documents,
    cache.websim_effect_aggregate_records,
    cache.websim_exact_authority_bundles
FROM PUBLIC, wow_exact_worker;

REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON
    cache.websim_canonical_documents,
    cache.websim_effect_aggregate_records,
    cache.websim_exact_authority_bundles
FROM wow_app;

GRANT SELECT, INSERT ON
    cache.websim_canonical_documents,
    cache.websim_effect_aggregate_records,
    cache.websim_exact_authority_bundles
TO wow_exact_worker;

GRANT EXECUTE ON FUNCTION
    ops.websim_exact_enqueue(text, bytea, jsonb),
    ops.websim_exact_read(text, bigint)
TO wow_app;

GRANT EXECUTE ON FUNCTION
    ops.websim_exact_claim(text, text, text),
    ops.websim_exact_heartbeat(bigint, uuid),
    ops.websim_exact_terminalize(bigint, uuid, text, text, jsonb, jsonb, text),
    ops.websim_exact_update_worker_state(text, text, text, text, bigint, jsonb),
    ops.websim_exact_prune_jobs(integer),
    ops.websim_exact_prune_metrics(integer)
TO wow_exact_worker;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0032_websim_exact_import_jobs',
    'Add owner-scoped canonical exact import jobs and dedicated-role worker functions'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = pg_catalog.clock_timestamp();

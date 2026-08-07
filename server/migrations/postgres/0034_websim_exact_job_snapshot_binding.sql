CREATE OR REPLACE FUNCTION ops.websim_exact_import_request_is_valid(
    p_request_json jsonb
)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $function$
    SELECT
        p_request_json IS NOT NULL
        AND pg_catalog.jsonb_typeof(p_request_json) = 'object'
        AND pg_catalog.jsonb_typeof(p_request_json -> 'exactLoadoutIntent') = 'object'
        AND pg_catalog.jsonb_typeof(p_request_json -> 'dependencyVector') = 'object'
        AND (p_request_json -> 'dependencyVector') ?& ARRAY[
            'seasonRevision', 'gameBuild', 'gearRuleRevision',
            'resolverRevision', 'compilerRevision', 'workerRevision',
            'simcRuntimeRevision', 'effectAuthorityRevision'
        ]
        AND (p_request_json -> 'dependencyVector') - ARRAY[
            'seasonRevision', 'gameBuild', 'gearRuleRevision',
            'resolverRevision', 'compilerRevision', 'workerRevision',
            'simcRuntimeRevision', 'effectAuthorityRevision'
        ] = '{}'::jsonb
        AND (
            (
                p_request_json ->> 'schemaRevision' = 'exact-import-job-request-v1'
                AND p_request_json ?& ARRAY[
                    'schemaRevision', 'exactLoadoutIntent', 'dependencyVector'
                ]
                AND p_request_json - ARRAY[
                    'schemaRevision', 'exactLoadoutIntent', 'dependencyVector'
                ] = '{}'::jsonb
            )
            OR (
                p_request_json ->> 'schemaRevision' = 'exact-import-job-request-v2'
                AND p_request_json ?& ARRAY[
                    'schemaRevision', 'exactLoadoutIntent', 'dependencyVector',
                    'resolvedLoadoutKey', 'simulationSnapshotKey', 'snapshotRowHash'
                ]
                AND p_request_json - ARRAY[
                    'schemaRevision', 'exactLoadoutIntent', 'dependencyVector',
                    'resolvedLoadoutKey', 'simulationSnapshotKey', 'snapshotRowHash'
                ] = '{}'::jsonb
                AND pg_catalog.jsonb_typeof(p_request_json -> 'resolvedLoadoutKey') = 'string'
                AND p_request_json ->> 'resolvedLoadoutKey'
                    ~ '^resolved-loadout-v2:sha256:[0-9a-f]{64}$'
                AND pg_catalog.jsonb_typeof(p_request_json -> 'simulationSnapshotKey') = 'string'
                AND p_request_json ->> 'simulationSnapshotKey'
                    ~ '^simulation-snapshot-v2:sha256:[0-9a-f]{64}$'
                AND pg_catalog.jsonb_typeof(p_request_json -> 'snapshotRowHash') = 'string'
                AND p_request_json ->> 'snapshotRowHash'
                    ~ '^sha256:[0-9a-f]{64}$'
            )
        )
        AND NOT pg_catalog.jsonb_path_exists(
            p_request_json,
            '$.** ? (@.type() == "object").keyvalue() ? (@.key == "rawProfile" || @.key == "rawString" || @.key == "playerName" || @.key == "characterName" || @.key == "realm" || @.key == "server")'::pg_catalog.jsonpath
        );
$function$;

DO $migration$
DECLARE
    request_constraint_name name;
    request_constraint_count integer;
BEGIN
    SELECT pg_catalog.count(*)
    INTO request_constraint_count
    FROM pg_catalog.pg_constraint AS constraint_row
    WHERE constraint_row.conrelid = 'ops.websim_exact_import_jobs'::pg_catalog.regclass
      AND constraint_row.contype = 'c'
      AND pg_catalog.pg_get_constraintdef(constraint_row.oid) LIKE
          '%exact-import-job-request-v1%';

    IF request_constraint_count IS DISTINCT FROM 1 THEN
        RAISE EXCEPTION
            'expected exactly one v1 exact import request constraint, found %',
            request_constraint_count;
    END IF;

    SELECT constraint_row.conname
    INTO request_constraint_name
    FROM pg_catalog.pg_constraint AS constraint_row
    WHERE constraint_row.conrelid = 'ops.websim_exact_import_jobs'::pg_catalog.regclass
      AND constraint_row.contype = 'c'
      AND pg_catalog.pg_get_constraintdef(constraint_row.oid) LIKE
          '%exact-import-job-request-v1%';

    EXECUTE pg_catalog.format(
        'ALTER TABLE ops.websim_exact_import_jobs DROP CONSTRAINT %I',
        request_constraint_name
    );
END;
$migration$;

ALTER TABLE ops.websim_exact_import_jobs
ADD CONSTRAINT websim_exact_import_jobs_request_schema_v1_v2_check
CHECK (ops.websim_exact_import_request_is_valid(request_json));

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
       OR NOT ops.websim_exact_import_request_is_valid(p_request_json)
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
       OR NOT ops.websim_exact_import_request_is_valid(candidate.request_json)
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

REVOKE ALL ON FUNCTION ops.websim_exact_import_request_is_valid(jsonb)
FROM PUBLIC, wow_app, wow_exact_worker;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0034_websim_exact_job_snapshot_binding',
    'Accept canonical exact import v2 jobs bound to one sealed SimulationSnapshot'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = pg_catalog.clock_timestamp();

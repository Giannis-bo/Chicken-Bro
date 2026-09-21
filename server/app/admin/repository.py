"""Aggregates only; never fetch conversation bodies or provider credentials."""
from datetime import datetime, timezone
from server.app.identity.test_accounts import TEST_ACCOUNT_IDS
from server.app.admin.application import DateWindow

# Historical acceptance identities are operator-created, not provider-authenticated QQ users.
SYNTHETIC_SUBJECTS = ['inline-acceptance-%', 'first-chat-acceptance-%', 'simc-all-smoke-%', 'g2-synthetic-%', 'poe2-release-smoke-%']

# All aggregates share one snapshot and one eligible-owner cohort. No per-user data leaves SQL.
OVERVIEW_SQL = """
WITH owners AS MATERIALIZED (
 SELECT u.id, min(i.created_at) AS joined_at FROM identity.users u
 JOIN identity.user_identities i ON i.user_id=u.id AND i.provider='qq' AND i.app_context=%(appid)s
 WHERE u.status <> 'deleted' AND NOT (u.id=ANY(%(tests)s::uuid[]))
 AND NOT (i.provider_subject LIKE ANY(%(synthetic)s::text[]))
 GROUP BY u.id
), c AS MATERIALIZED (
 SELECT r.* FROM chat.agent_runs r JOIN owners o ON o.id=r.user_id
 JOIN chat.conversations conv ON conv.id=r.conversation_id AND conv.user_id=r.user_id
 WHERE conv.game=%(game)s AND r.started_at >= %(start)s AND r.started_at < %(end)s
), wow_jobs AS MATERIALIZED (
 SELECT j.*, s.snapshot_json,
   CASE WHEN j.status='succeeded' AND (
     r.id IS NOT NULL AND r.primary_metric_value > 0 AND r.primary_metric_value < 'Infinity'::float8
     AND r.provenance_json->>'snapshotId'=j.snapshot_id::text
     AND r.provenance_json->>'profileSha256'=r.profile_sha256
     AND r.provenance_json->>'scenarioHash'=j.scenario_hash
     AND r.provenance_json->>'runtimeRevision'=r.runtime_revision
     AND r.provenance_json->>'compilerRevision'=r.compiler_revision
     AND COALESCE(r.provenance_json->>'sourceRawSha256','') ~ '^[0-9a-f]{64}$'
   ) IS NOT TRUE THEN 'invalid' ELSE j.status END AS checked_status,
   CASE WHEN j.status IN ('succeeded','failed','cancelled') AND j.updated_at >= j.created_at
     THEN EXTRACT(EPOCH FROM j.updated_at-j.created_at) END AS elapsed
 FROM simc.simulation_jobs j JOIN owners o ON o.id=j.user_id
 JOIN simc.source_snapshots s ON s.id=j.snapshot_id AND s.user_id=j.user_id
 LEFT JOIN simc.simulation_results r ON r.job_id=j.id AND r.user_id=j.user_id
 WHERE %(game)s='wow' AND j.created_at >= %(start)s AND j.created_at < %(end)s
), builds AS MATERIALIZED (
 SELECT b.* FROM poe2.builds b JOIN owners o ON o.id=b.user_id
 WHERE %(game)s='poe2' AND b.created_at >= %(start)s AND b.created_at < %(end)s
), poe_jobs AS MATERIALIZED (
 SELECT j.user_id,j.created_at,j.status,
 CASE WHEN j.status='succeeded' AND (
   jsonb_typeof(j.result_json->'stats')='object'
   AND j.result_json->>'inputSha256'=b.input_sha256
   AND COALESCE(j.result_json->>'engineVersion','') NOT IN ('','unverified')
   AND COALESCE(j.result_json->>'exportCode','') <> ''
   AND EXISTS (SELECT 1 FROM jsonb_each(CASE WHEN jsonb_typeof(j.result_json->'stats')='object'
     THEN j.result_json->'stats' ELSE '{}'::jsonb END) m
     WHERE m.key IN ('Life','EnergyShield') AND CASE WHEN jsonb_typeof(m.value)='number' THEN m.value::text::numeric > 0 ELSE false END)
   AND NOT EXISTS (SELECT 1 FROM jsonb_each(CASE WHEN jsonb_typeof(j.result_json->'stats')='object'
     THEN j.result_json->'stats' ELSE '{}'::jsonb END) m WHERE jsonb_typeof(m.value) <> 'number')
 ) IS NOT TRUE THEN 'invalid' ELSE j.status END AS checked_status,
 CASE WHEN j.status IN ('succeeded','failed') AND j.updated_at>=j.created_at
   THEN EXTRACT(EPOCH FROM j.updated_at-j.created_at) END AS elapsed
 FROM poe2.jobs j JOIN owners o ON o.id=j.user_id
 JOIN poe2.builds b ON b.id=j.build_id AND b.user_id=j.user_id
 WHERE %(game)s='poe2' AND j.created_at >= %(start)s AND j.created_at < %(end)s
), j AS MATERIALIZED (
 SELECT user_id,created_at,checked_status,elapsed,snapshot_json FROM wow_jobs
 UNION ALL SELECT user_id,created_at,checked_status,elapsed,'{}'::jsonb FROM poe_jobs
), activity AS MATERIALIZED (
 SELECT user_id, (started_at AT TIME ZONE 'Asia/Shanghai')::date AS day FROM c
 UNION SELECT user_id, (created_at AT TIME ZONE 'Asia/Shanghai')::date FROM j
 UNION SELECT user_id, (created_at AT TIME ZONE 'Asia/Shanghai')::date FROM builds
), days AS (
 SELECT generate_series(%(first)s::date,%(last)s::date,interval '1 day')::date AS day
), daily AS (
 SELECT d.day::text AS date,
 (SELECT count(*) FROM owners WHERE (joined_at AT TIME ZONE 'Asia/Shanghai')::date=d.day) AS "newUsers",
 (SELECT count(*) FROM activity WHERE day=d.day) AS "activeUsers",
 (SELECT count(*) FROM c WHERE (started_at AT TIME ZONE 'Asia/Shanghai')::date=d.day) AS questions,
 (SELECT count(*) FROM j WHERE (created_at AT TIME ZONE 'Asia/Shanghai')::date=d.day) AS simulations,
 (SELECT count(*) FROM builds WHERE (created_at AT TIME ZONE 'Asia/Shanghai')::date=d.day) AS builds
 FROM days d ORDER BY d.day
), specs AS (
 SELECT COALESCE(NULLIF(snapshot_json#>>'{character,classKey}',''),'unknown') AS class,
 COALESCE(NULLIF(snapshot_json#>>'{character,specKey}',''),'unknown') AS spec,
 count(*) AS count FROM wow_jobs GROUP BY 1,2 ORDER BY count(*) DESC,1,2
)
SELECT jsonb_build_object(
 'users', (SELECT jsonb_build_object(
   'total',count(*) FILTER (WHERE joined_at < %(end)s),
   'new',count(*) FILTER (WHERE joined_at >= %(start)s AND joined_at < %(end)s),
   'active',(SELECT count(DISTINCT user_id) FROM activity)) FROM owners),
 'chat', (SELECT jsonb_build_object(
   'total',count(*),'succeeded',count(*) FILTER (WHERE status='succeeded'),
   'failed',count(*) FILTER (WHERE status='failed'),'running',count(*) FILTER (WHERE status='streaming'),
   'successRate',count(*) FILTER (WHERE status='succeeded')::float8/NULLIF(count(*) FILTER (WHERE status IN ('succeeded','failed')),0),
   'resolved',count(*) FILTER (WHERE resolved=true AND status='succeeded'),
   'unresolved',count(*) FILTER (WHERE resolved=false AND status='succeeded'),
   'feedbackRate',count(*) FILTER (WHERE resolved IS NOT NULL AND status='succeeded')::float8/NULLIF(count(*) FILTER (WHERE status='succeeded'),0),
   'resolutionRate',count(*) FILTER (WHERE resolved=true AND status='succeeded')::float8/NULLIF(count(*) FILTER (WHERE resolved IS NOT NULL AND status='succeeded'),0),
   'avgSeconds',avg(EXTRACT(EPOCH FROM finished_at-started_at)) FILTER (WHERE status IN ('succeeded','failed') AND finished_at>=started_at),
   'p95Seconds',percentile_cont(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM finished_at-started_at)) FILTER (WHERE status IN ('succeeded','failed') AND finished_at>=started_at)
 ) FROM c),
 %(task_key)s::text, (SELECT jsonb_build_object(
   'total',count(*),'succeeded',count(*) FILTER (WHERE checked_status='succeeded'),
   'failed',count(*) FILTER (WHERE checked_status='failed'),'queued',count(*) FILTER (WHERE checked_status='queued'),
   'running',count(*) FILTER (WHERE checked_status='running'),'cancelled',count(*) FILTER (WHERE checked_status='cancelled'),
   'invalidResults',count(*) FILTER (WHERE checked_status='invalid'),
   'successRate',count(*) FILTER (WHERE checked_status='succeeded')::float8/NULLIF(count(*) FILTER (WHERE checked_status IN ('succeeded','failed','invalid')),0),
   'avgSeconds',avg(elapsed),'p95Seconds',percentile_cont(0.95) WITHIN GROUP (ORDER BY elapsed)
 ) FROM j),
 'builds',(SELECT count(*) FROM builds),
 'daily',COALESCE((SELECT jsonb_agg(to_jsonb(daily)) FROM daily),'[]'::jsonb),
 'specializations',COALESCE((SELECT jsonb_agg(to_jsonb(specs)) FROM specs),'[]'::jsonb)
)
"""

class PostgresAnalyticsRepository:
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    def is_qq_owner(self, user_id, appid):
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""SELECT 1 FROM identity.users u JOIN identity.user_identities i ON i.user_id=u.id
                 WHERE u.id=%s AND u.status='active' AND i.provider='qq' AND i.app_context=%s AND NOT (i.provider_subject LIKE ANY(%s::text[]))""", (user_id,appid,SYNTHETIC_SUBJECTS))
                return cursor.fetchone() is not None

    def overview(self, window: DateWindow, appid: str, game: str = 'wow') -> dict:
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                cursor.execute("SET LOCAL statement_timeout='5000ms'")
                cursor.execute(OVERVIEW_SQL, {'appid':appid,'game':game,'task_key':'simc' if game=='wow' else 'poe2','tests':list(TEST_ACCOUNT_IDS.values()), 'synthetic':SYNTHETIC_SUBJECTS,
                    'start':window.start,'end':window.end,'first':window.start_date,'last':window.end_date})
                result = cursor.fetchone()[0]
        return {**result, 'game':game, 'start':window.start_date, 'end':window.end_date, 'timezone':'Asia/Shanghai',
                'generatedAt':datetime.now(timezone.utc).isoformat(), 'scope':'current_qq_users'}

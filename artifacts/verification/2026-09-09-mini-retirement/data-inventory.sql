\set ON_ERROR_STOP on
BEGIN ISOLATION LEVEL REPEATABLE READ;
CREATE TEMP TABLE cleanup_users AS
SELECT u.id FROM identity.users u
WHERE EXISTS (SELECT 1 FROM identity.user_identities i WHERE i.user_id=u.id AND i.provider='wechat_mini')
AND NOT EXISTS (SELECT 1 FROM identity.user_identities i WHERE i.user_id=u.id AND i.provider<>'wechat_mini');
SELECT json_build_object('scope','prospective_wechat_only_owners_not_approved','database',current_database(),'observedAt',now(),'users',coalesce(json_agg(id ORDER BY id),'[]'::json)) FROM cleanup_users;
SELECT format($query$
SELECT json_build_object('table',%L,'targetRows',count(*) FILTER (WHERE user_id IN (SELECT id FROM cleanup_users)),
  'targetFingerprint',md5(coalesce(string_agg(md5(row_to_json(t)::text),'' ORDER BY md5(row_to_json(t)::text)) FILTER (WHERE user_id IN (SELECT id FROM cleanup_users)),'')),
  'retainedRows',count(*) FILTER (WHERE user_id NOT IN (SELECT id FROM cleanup_users) OR user_id IS NULL),
  'retainedFingerprint',md5(coalesce(string_agg(md5(row_to_json(t)::text),'' ORDER BY md5(row_to_json(t)::text)) FILTER (WHERE user_id NOT IN (SELECT id FROM cleanup_users) OR user_id IS NULL),''))) FROM %I.%I t;
$query$,table_schema||'.'||table_name,table_schema,table_name)
FROM information_schema.columns WHERE table_schema IN ('identity','chat','simc','ops') AND column_name='user_id' ORDER BY table_schema,table_name
\gexec
SELECT json_build_object('table','chat.tool_results','targetRows',count(*)) FROM chat.tool_results WHERE run_id IN (SELECT run_id FROM chat.executions WHERE user_id IN (SELECT id FROM cleanup_users));
SELECT json_build_object('table','ops.job_queue','targetRows',count(*),'active',count(*) FILTER (WHERE status IN ('queued','running'))) FROM ops.job_queue WHERE aggregate_id IN (SELECT id FROM simc.simulation_jobs WHERE user_id IN (SELECT id FROM cleanup_users)) OR payload_json->>'user_id' IN (SELECT id::text FROM cleanup_users);
SELECT json_build_object('activeChatRuns', (SELECT count(*) FROM chat.agent_runs WHERE user_id IN (SELECT id FROM cleanup_users) AND status NOT IN ('succeeded','failed')),
 'activeSimcJobs',(SELECT count(*) FROM simc.simulation_jobs WHERE user_id IN (SELECT id FROM cleanup_users) AND status NOT IN ('succeeded','failed')),
 'liveExecutionLeases',(SELECT count(*) FROM chat.executions WHERE user_id IN (SELECT id FROM cleanup_users) AND lease_expires_at>now()),
 'mixedWechatOtherProviderOwners',(SELECT count(*) FROM identity.users u WHERE EXISTS(SELECT 1 FROM identity.user_identities i WHERE i.user_id=u.id AND provider='wechat_mini') AND EXISTS(SELECT 1 FROM identity.user_identities i WHERE i.user_id=u.id AND provider<>'wechat_mini')));
ROLLBACK;

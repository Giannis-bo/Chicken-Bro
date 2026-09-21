"""Read-only aggregate reconciliation and public artifact checks; temporary non-admin session revoked."""
import hashlib,json,secrets,sys,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
import httpx,psycopg
sys.path.insert(0,'/opt/chickenbro')
from server.app.admin.application import date_window
from server.app.admin.repository import PostgresAnalyticsRepository,SYNTHETIC_SUBJECTS
from server.app.identity.repository import PostgresIdentityRepository
from server.app.identity.test_accounts import TEST_ACCOUNT_IDS
PACK=Path('/var/lib/chickenbro/releases/admin-games-20260921-final')
e=json.loads((PACK/'private-environments.json').read_text())['chickenbro-api']
def connect():return psycopg.connect(e['WOW_DATABASE_URL'],passfile=e.get('PGPASSFILE'))
repo=PostgresAnalyticsRepository(connect);window=date_window('2026-09-15','2026-09-21')
report={'range':[window.start_date,window.end_date],'aggregates':{}}
# Independent raw counts, no reuse of the analytics CTEs.
with connect() as conn:
 conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
 owners=[r[0] for r in conn.execute("""SELECT DISTINCT u.id FROM identity.users u JOIN identity.user_identities i ON i.user_id=u.id
 WHERE u.status<>'deleted' AND i.provider='qq' AND i.app_context=%s AND NOT(u.id=ANY(%s::uuid[]))
 AND NOT(i.provider_subject LIKE ANY(%s::text[]))""",(e['WOW_QQ_APPID'],list(TEST_ACCOUNT_IDS.values()),SYNTHETIC_SUBJECTS))]
 for game in ('wow','poe2'):
  data=repo.overview(window,e['WOW_QQ_APPID'],game)
  runs=conn.execute("""SELECT r.user_id FROM chat.agent_runs r JOIN chat.conversations c ON c.id=r.conversation_id AND c.user_id=r.user_id
   WHERE c.game=%s AND r.user_id=ANY(%s::uuid[]) AND r.started_at >= %s AND r.started_at < %s""",(game,owners,window.start,window.end)).fetchall()
  table='simc.simulation_jobs' if game=='wow' else 'poe2.jobs'
  jobs=conn.execute('SELECT user_id FROM '+table+' WHERE user_id=ANY(%s::uuid[]) AND created_at >= %s AND created_at < %s',(owners,window.start,window.end)).fetchall()
  builds=conn.execute('SELECT user_id FROM poe2.builds WHERE user_id=ANY(%s::uuid[]) AND created_at >= %s AND created_at < %s',(owners,window.start,window.end)).fetchall() if game=='poe2' else []
  tasks=data['simc' if game=='wow' else 'poe2']
  assert data['chat']['total']==len(runs) and tasks['total']==len(jobs) and data['builds']==len(builds)
  assert data['users']['active']==len({r[0] for r in runs+jobs+builds})
  report['aggregates'][game]={'users':data['users'],'chat':data['chat'],'tasks':tasks,'builds':data['builds'],'independentCountsMatched':True}
# Existing synthetic release account, never the configured QQ administrator.
user=json.loads(Path('/var/lib/chickenbro/releases/poe2-20260921/private-smoke-sessions.json').read_text())['B']['userId']
assert user!=e['WOW_ADMIN_USER_ID']
token=secrets.token_urlsafe(40);token_hash=hashlib.sha256(token.encode()).hexdigest();identity=PostgresIdentityRepository(connect)
identity.issue_auth_session(token_hash=token_hash,user_id=user,kind='web_cookie',expires_at=datetime.now(timezone.utc)+timedelta(minutes=5))
try:
 with httpx.Client(base_url='https://www.chickenbro.cloud',trust_env=False,timeout=20) as client:
  statuses={}
  for game in ('wow','poe2'):
   url='/api/v2/admin/overview?game='+game
   anon=client.get(url);assert anon.status_code==401 and anon.headers['cache-control']=='no-store'
   other=client.get(url,headers={'Cookie':'__Host-chickenbro-session='+token});assert other.status_code==403 and other.headers['cache-control']=='no-store'
   statuses[game]={'anonymous':401,'nonAdmin':403}
  report['access']=statuses
  m=json.loads((PACK/'manifest.json').read_text());verified=0
  for file,expected in m['webFiles'].items():
   response=client.get('/'+file);assert response.status_code==200
   assert hashlib.sha256(response.content).hexdigest()==expected,file
   verified+=1
  report['publicFilesVerified']=verified
  checks=[]
  for i in range(3):
   response=client.get('/api/v2/health/readiness');assert response.status_code==200
   checks.append({'status':response.status_code,'at':datetime.now(timezone.utc).isoformat()})
   if i<2:time.sleep(10)
  report['readinessObservation']=checks
finally:identity.revoke_auth_session(token_hash=token_hash,kind='web_cookie',now=datetime.now(timezone.utc))
report['temporaryNonAdminSessionRevoked']=True
(PACK/'live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));(PACK/'live.json').chmod(0o600)
print(json.dumps(report,ensure_ascii=False))

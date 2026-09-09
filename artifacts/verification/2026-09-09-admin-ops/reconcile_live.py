"""Independent production counts, runtime hashes, and administrator audit evidence."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
import psycopg,httpx
payload=Path(sys.argv[1]);m=json.loads((payload/'manifest.json').read_text())
webm=json.loads(Path(sys.argv[2]).read_text())
base=Path('/opt/chickenbro').resolve();web=Path('/var/www/chickenbro-web/current').resolve()
assert str(base).endswith(m['sourceCommit']) and str(web).endswith(webm['sourceCommit'])
for name,sha in m['files'].items():assert hashlib.sha256((base/name).read_bytes()).hexdigest()==sha
services={}
for unit in ['chickenbro-api','chickenbro-worker']:
 pid=subprocess.check_output(['systemctl','show',unit,'-p','MainPID','--value'],text=True).strip()
 env=dict(v.split('=',1) for v in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in v)
 assert Path('/proc/'+pid+'/cwd').resolve()==base
 assert env.get('WOW_ADMIN_USER_ID') and hashlib.sha256(env['WOW_ADMIN_USER_ID'].encode()).hexdigest()=='bc7a60967cb4e3130d943e2fc9a8c1e15b925f0f7f384e9bdebbab2787dd0226'
 services[unit]={'source':str(base),'administratorConfigured':True}
 if unit=='chickenbro-api':api_env=env
os.environ.update(api_env);sys.path.insert(0,str(base))
from server.app.admin.application import date_window
from server.app.admin.repository import OVERVIEW_SQL,SYNTHETIC_SUBJECTS
from server.app.identity.test_accounts import TEST_ACCOUNT_IDS
w=date_window(None,None)
with psycopg.connect(api_env['WOW_DATABASE_URL']) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
 ids=[r[0] for r in c.execute("SELECT DISTINCT user_id FROM identity.user_identities WHERE provider='qq' AND app_context=%s AND provider_subject ~ '^[0-9A-Fa-f]{32}$'",(api_env['WOW_QQ_APPID'],))]
 chats=c.execute('SELECT count(*) FROM chat.agent_runs WHERE user_id=ANY(%s) AND started_at>=%s AND started_at<%s',(ids,w.start,w.end)).fetchone()[0]
 sims=c.execute('SELECT count(*) FROM simc.simulation_jobs WHERE user_id=ANY(%s) AND created_at>=%s AND created_at<%s',(ids,w.start,w.end)).fetchone()[0]
 active=c.execute('''SELECT count(DISTINCT user_id) FROM (
  SELECT user_id FROM chat.agent_runs WHERE started_at>=%s AND started_at<%s
  UNION ALL SELECT user_id FROM simc.simulation_jobs WHERE created_at>=%s AND created_at<%s) q WHERE user_id=ANY(%s)''',(w.start,w.end,w.start,w.end,ids)).fetchone()[0]
 result=c.execute(OVERVIEW_SQL,{'appid':api_env['WOW_QQ_APPID'],'tests':list(TEST_ACCOUNT_IDS.values()),'synthetic':SYNTHETIC_SUBJECTS,'start':w.start,'end':w.end,'first':w.start_date,'last':w.end_date}).fetchone()[0]
 assert result['users']['total']==len(ids) and result['users']['active']==active
 assert result['chat']['total']==chats and result['simc']['total']==sims
 audit=c.execute("SELECT payload_json->>'statusCode',count(*) FROM ops.audit_events WHERE event_type='admin.access' GROUP BY 1").fetchall()
 assert {'200','403'} <= {r[0] for r in audit}
with httpx.Client(base_url=api_env['WOW_WEB_ORIGIN'],timeout=30) as client:
 denied=client.get('/api/v2/admin/overview');assert denied.status_code==401 and denied.headers['Cache-Control']=='no-store'
 for name,sha in webm['webFiles'].items():
  r=client.get('/'+name,headers={'Accept-Encoding':'identity','Cache-Control':'no-cache'})
  assert r.status_code==200 and hashlib.sha256(r.content).hexdigest()==sha
for parent,key in [(Path(m['expectedBackend']),'baseInventory'),(Path(m['expectedWeb']),'oldWebInventory')]:
 for name,sha in m[key].items():
  p=parent/name
  assert ('link:'+os.readlink(p) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest())==sha
print(json.dumps({'backendSourceCommit':m['sourceCommit'],'webSourceCommit':webm['sourceCommit'],'services':services,'independentCountsMatched':{'users':len(ids),'activeUsers':active,'questions':chats,'simulations':sims},'adminAuditStatuses':dict(audit),'anonymousStatus':401,'publicWebFilesMatched':len(webm['webFiles']),'originalBackendAndWebUnchanged':True},indent=2))

"""Bind the operator-confirmed current QQ browser owner; no self-enrollment endpoint."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
from uuid import UUID
import psycopg
from urllib.request import urlopen
m=json.loads(Path(sys.argv[1]).read_text());uid=UUID(sys.argv[2]);commit=m['sourceCommit']
assert str(Path('/opt/chickenbro').resolve()).endswith(commit)
config=Path('/etc/chickenbro-admin-ops-'+commit[:12]+'.env')
prior=config.read_text();assert prior=='WOW_ADMIN_USER_ID=\n' or prior=='WOW_ADMIN_USER_ID='+str(uid)+'\n'
def environment(unit):
 p=subprocess.check_output(['systemctl','show',unit,'-p','MainPID','--value'],text=True).strip()
 return dict(v.split('=',1) for v in Path('/proc/'+p+'/environ').read_text().split('\0') if '=' in v)
env=environment('chickenbro-api');os.environ.update(env)
assert not env.get('WOW_ADMIN_USER_ID') or env['WOW_ADMIN_USER_ID']==str(uid)
with psycopg.connect(env['WOW_DATABASE_URL']) as c:
 c.execute("SET LOCAL lock_timeout='5s'")
 c.execute('LOCK TABLE chat.agent_runs,simc.simulation_jobs,ops.job_queue IN SHARE MODE')
 counts=[c.execute(q).fetchone()[0] for q in ["SELECT count(*) FROM chat.agent_runs WHERE status='streaming'","SELECT count(*) FROM simc.simulation_jobs WHERE status IN ('queued','running')","SELECT count(*) FROM ops.job_queue WHERE status IN ('queued','running')"]]
 assert not any(counts),'active work prevents binding restart'
 assert str(Path('/opt/chickenbro').resolve()).endswith(commit), 'backend changed under fence'
 assert c.execute("""SELECT 1 FROM identity.users u JOIN identity.user_identities i ON i.user_id=u.id
  WHERE u.id=%s AND u.status='active' AND i.provider='qq' AND i.app_context=%s
  AND i.provider_subject ~ '^[0-9A-Fa-f]{32}$'""",(uid,env['WOW_QQ_APPID'])).fetchone(), 'confirmed owner must be a real QQ identity'
 subprocess.run(['systemctl','stop','chickenbro-api','chickenbro-worker'],check=True)
 next_path=config.with_suffix('.next');next_path.write_text('WOW_ADMIN_USER_ID='+str(uid)+'\n');next_path.chmod(0o600);os.replace(next_path,config)
subprocess.run(['systemctl','start','chickenbro-worker'],check=True)
for _ in range(25):
 p=subprocess.check_output(['systemctl','show','chickenbro-worker','-p','MainPID','--value'],text=True).strip()
 if p!='0' and ('pid='+p+',') in subprocess.check_output(['ss','-ltnp','sport = :28794'],text=True):break
 time.sleep(1)
else:raise RuntimeError('worker tool endpoint not ready; API stays closed')
subprocess.run(['systemctl','start','chickenbro-api'],check=True)
for _ in range(30):
 try:
  with urlopen('http://127.0.0.1:8790/api/v2/health/readiness',timeout=3) as r:
   if json.load(r)['status']=='ready':break
 except Exception:pass
 time.sleep(1)
else:raise RuntimeError('readiness failed')
for unit in ('chickenbro-api','chickenbro-worker'):assert environment(unit)['WOW_ADMIN_USER_ID']==str(uid)
print(json.dumps({'administratorBound':True,'ownerSha256':hashlib.sha256(str(uid).encode()).hexdigest(),'realBrowserOwnerConfirmedByUser':True,'configMode':oct(config.stat().st_mode&0o777),'readiness':'ready','sourceCommit':commit}))

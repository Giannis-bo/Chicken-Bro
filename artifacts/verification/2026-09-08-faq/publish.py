"""Scoped production overlay; no database or SimC binary mutation."""
import hashlib,json,os,shutil,subprocess,sys,time,urllib.request
from pathlib import Path as P
C=P('/opt/chickenbro');W=P('/var/www/chickenbro-web/current')
U=['chickenbro-api.service','chickenbro-worker.service']
F={'server/app/chickenbro/agent/AGENTS.md','server/app/chickenbro/simulation_tools.py','server/app/simulation/compiler.py','server/app/simulation/readiness.py','server/app/simulation/worker.py','server/chickenbro_native_mcp.py','server/app/api/routes/simc.py'}
def run(*a):return subprocess.check_output(a,text=True,stderr=subprocess.PIPE).strip()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def hashes(p):return {str(f.relative_to(p)):digest(f) for f in p.rglob('*') if f.is_file() and not f.is_symlink() and '__pycache__' not in f.parts}
def sql(q):return run('sudo','-u','postgres','psql','-X','-v','ON_ERROR_STOP=1','-At','-d','chickenbro_prod','-c',q)
def active():return int(sql("SELECT (SELECT count(*) FROM chat.agent_runs WHERE status='streaming')+(SELECT count(*) FROM simc.simulation_jobs WHERE status IN ('queued','running'))+(SELECT count(*) FROM ops.job_queue WHERE status IN ('queued','running'))"))
def ready():
 try:
  with urllib.request.urlopen('http://127.0.0.1:8790/api/v2/health/readiness',timeout=5) as r:return json.load(r)['status']=='ready'
 except Exception:return False
def wait_ready():
 for _ in range(45):
  if ready():return
  time.sleep(1)
 raise RuntimeError('readiness failed')
def switch(link,target):
 p=link.with_name(link.name+'.faq-next');assert not p.exists() and not p.is_symlink();p.symlink_to(target);p.replace(link)
def effective(unit):
 pid=run('systemctl','show',unit,'-p','MainPID','--value')
 env=dict(x.split('=',1) for x in P('/proc/'+pid+'/environ').read_text().split('\0') if '=' in x)
 return env.get('WOW_SIMC_COMPILER_REVISION')
mfile=P(sys.argv[1]);assert os.geteuid()==0 and digest(mfile)==sys.argv[2]
m=json.loads(mfile.read_text());sha=m['patchCommit'];assert len(sha)==40 and all(c in '0123456789abcdef' for c in sha)
assert set(m['files'])==set(m['beforeFiles'])==F
assert str(C.resolve())==m['previousCode'] and str(W.resolve())==m['previousWeb']
base=P(m['previousCode']);payload=P('/opt/chickenbro-test/releases')/sha;target=P('/opt/chickenbro-releases')/('faq-'+sha);web=P('/var/www/chickenbro-web/releases')/('faq-'+sha)
original=hashes(base);assert all(original.get(p)==h for p,h in m['beforeFiles'].items());assert all(digest(payload/p)==h for p,h in m['files'].items())
expected={**original,**m['files']}
if not target.exists():
 shutil.copytree(base,target,symlinks=True,ignore=shutil.ignore_patterns('__pycache__'))
 for p in F:
  assert not (target/p).is_symlink();shutil.copyfile(payload/p,target/p);(target/p).chmod(0o644)
assert hashes(target)==expected and hashes(web)==m['webFiles']
assert sql('SELECT id FROM ops.schema_migrations ORDER BY id').splitlines()==m['migrations']
assert ready() and active()==0
for u in U:assert run('systemctl','show',u,'-p','WorkingDirectory','--value')==str(C)
env=P('/etc/chickenbro-faq-20260908.env');drops=[P('/etc/systemd/system')/(u+'.d')/'99-zz-faq-rerun-20260908.conf' for u in U]
assert not env.exists() and not any(p.exists() for p in drops)
if '--apply' not in sys.argv:
 print(json.dumps({'status':'dry_run_verified','target':str(target),'web':str(web)}));sys.exit()
created=[]
try:
 run('systemctl','stop',U[0])
 for _ in range(60):
  if active()==0:break
  time.sleep(1)
 assert active()==0
 run('systemctl','stop',U[1])
 env.write_text('WOW_SIMC_COMPILER_REVISION=chickenbro-simc-compiler-v4\n');env.chmod(0o644);created.append(env)
 for p in drops:
  p.parent.mkdir(exist_ok=True);p.write_text('[Service]\nEnvironmentFile='+str(env)+'\n');created.append(p)
 switch(C,target);switch(W,web);run('systemctl','daemon-reload');run('systemctl','start',*U);wait_ready()
 assert all(run('systemctl','is-active',u)=='active' and effective(u)=='chickenbro-simc-compiler-v4' for u in U)
 assert hashes(target)==expected and hashes(web)==m['webFiles']
 proof={'status':'published','patchCommit':sha,'codeRoot':str(target),'webRoot':str(web),'rollbackCode':m['previousCode'],'rollbackWeb':m['previousWeb'],'compilerRevision':'chickenbro-simc-compiler-v4','database':'chickenbro_prod','databaseChanged':False,'simcBinaryChanged':False,'dropins':[str(p) for p in drops]}
 P('/tmp/chickenbro-faq-production-publish.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof))
except Exception:
 # Drain new work before restoring an old compiler. Never abandon v4 jobs.
 run('systemctl','stop',U[0])
 for _ in range(180):
  if active()==0:break
  time.sleep(1)
 if active()!=0:raise RuntimeError('rollback requires attention: active work retained, API stopped')
 run('systemctl','stop',U[1]);switch(C,m['previousCode']);switch(W,m['previousWeb'])
 for p in reversed(created):p.unlink()
 run('systemctl','daemon-reload');run('systemctl','start',*U);wait_ready();raise

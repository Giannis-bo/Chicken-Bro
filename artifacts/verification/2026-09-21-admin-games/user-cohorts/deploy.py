"""Cloud-only exact-file admin release with retained application recovery."""
import fcntl,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
from urllib.request import urlopen
SRC=Path('/opt/chickenbro-candidates/admin-users-20260921')
PACK=Path('/var/lib/chickenbro/releases/admin-users-20260921')
TARGET=Path('/opt/chickenbro-releases/admin-users-20260921')
WEB=Path('/var/www/chickenbro-web/releases/admin-users-20260921')
LINK=Path('/opt/chickenbro');WLINK=Path('/var/www/chickenbro-web/current')
UNITS=('chickenbro-api','chickenbro-worker')
FILES=('server/app/admin/repository.py',)
def run(args):subprocess.run(args,check=True,stdout=subprocess.DEVNULL)
def inventory(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
def env(unit):
 pid=subprocess.check_output(['systemctl','show',unit,'-p','MainPID','--value'],text=True).strip()
 return dict(x.split('=',1) for x in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in x)
def digest(e):return hashlib.sha256(json.dumps({k:v for k,v in e.items() if k not in ('INVOCATION_ID','JOURNAL_STREAM','SYSTEMD_EXEC_PID')},sort_keys=True).encode()).hexdigest()
def write(name,data):
 p=PACK/name;p.write_text(json.dumps(data,indent=2));p.chmod(0o600)
def switch(link,target):
 tmp=link.with_name(link.name+'.admin-games-next');assert not tmp.exists();tmp.symlink_to(target);os.replace(tmp,link)
def ready():
 for _ in range(30):
  try:
   with urlopen('http://127.0.0.1:8790/api/v2/health/readiness',timeout=3) as r:
    if r.status==200:return
  except Exception:pass
  time.sleep(1)
 raise RuntimeError('readiness timeout')
def drain_stop():
 import psycopg
 e=env(UNITS[0]);deadline=time.monotonic()+120
 while True:
  with psycopg.connect(e['WOW_DATABASE_URL'],passfile=e.get('PGPASSFILE')) as c:
   c.execute("SET LOCAL lock_timeout='3000ms'")
   c.execute('LOCK TABLE chat.agent_runs,chat.executions,simc.simulation_jobs,ops.job_queue,poe2.jobs,poe2.character_imports IN SHARE MODE')
   active=sum(c.execute('SELECT count(*) FROM '+q).fetchone()[0] for q in ["chat.agent_runs WHERE status='streaming'","chat.executions WHERE stage IN ('pending','queued','running')","simc.simulation_jobs WHERE status IN ('queued','running')","ops.job_queue WHERE status IN ('queued','running')","poe2.jobs WHERE status IN ('queued','running')","poe2.character_imports WHERE status IN ('queued','fetching','mapping','validating')"])
   if not active:run(['systemctl','stop',*UNITS]);return
  if time.monotonic()>=deadline:raise RuntimeError('active work prevents release')
  time.sleep(1)
def start():
 run(['systemctl','start','chickenbro-worker']);run(['systemctl','start','chickenbro-api']);ready()
assert os.geteuid()==0
mode=sys.argv[1];PACK.mkdir(parents=True,exist_ok=True);PACK.chmod(0o700)
with open('/run/lock/chickenbro-release.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if mode=='prepare':
  assert not (PACK/'manifest.json').exists() and not TARGET.exists() and not WEB.exists()
  before={u:env(u) for u in UNITS};assert all('chickenbro_prod' in e['WOW_DATABASE_URL'] for e in before.values())
  old=LINK.resolve();oldweb=WLINK.resolve();base=inventory(old);baseweb=inventory(oldweb)
  expected=json.loads((SRC/'artifacts/verification/2026-09-21-admin-games/user-cohorts/source-sha256.json').read_text())['files']
  assert all(hashlib.sha256((SRC/f).read_bytes()).hexdigest()==expected[f] for f in FILES)
  shutil.copytree(old,TARGET,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
  for f in FILES:shutil.copyfile(SRC/f,TARGET/f)
  shutil.copytree(SRC/'apps/mini-taro/dist/h5',WEB)
  current=inventory(TARGET);changed={f for f in base if base[f]!=current.get(f)};assert changed and changed<=set(FILES) and base.keys()==current.keys()
  shutil.copyfile(__file__,PACK/'deploy.py')
  write('private-environments.json',before)
  write('manifest.json',{'backendBase':str(old),'webBase':str(oldweb),'backend':str(TARGET),'web':str(WEB),'backendBaseFiles':base,'webBaseFiles':baseweb,'backendFiles':current,'webFiles':inventory(WEB),'changedBackendFiles':sorted(changed),'environmentDigests':{u:digest(e) for u,e in before.items()},'databaseMigration':False})
  print(json.dumps({'prepared':True,'backendChangedFiles':len(changed),'webFiles':len(inventory(WEB))}))
 elif mode in ('promote','rollback'):
  m=json.loads((PACK/'manifest.json').read_text());forward=mode=='promote'
  expected_backend=m['backendBase'] if forward else m['backend'];expected_web=m['webBase'] if forward else m['web']
  assert str(LINK.resolve())==expected_backend and str(WLINK.resolve())==expected_web
  for key in ('backendBase','webBase','backend','web'):assert inventory(Path(m[key]))==m[key+'Files']
  assert all(digest(env(u))==m['environmentDigests'][u] for u in UNITS)
  drain_stop()
  dest=m['backend'] if forward else m['backendBase'];wdest=m['web'] if forward else m['webBase']
  try:switch(LINK,dest);switch(WLINK,wdest);start()
  except Exception:
   # Startup failed before accepting traffic: restore this batch's original pointers.
   run(['systemctl','stop',*UNITS]);switch(LINK,expected_backend);switch(WLINK,expected_web);start();raise
  assert all(digest(env(u))==m['environmentDigests'][u] for u in UNITS)
  write(mode+'.json',{'passed':True,'backend':str(LINK.resolve()),'web':str(WLINK.resolve()),'environmentPreserved':True})
  print(json.dumps({'mode':mode,'passed':True,'businessVerification':'pending'}))
 else:raise ValueError('invalid mode')

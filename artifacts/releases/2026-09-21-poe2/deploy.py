"""Cloud-only POE2 release: exact identities, additive migration, retained recovery."""
import fcntl, hashlib, importlib, json, os, shutil, subprocess, sys, time
from pathlib import Path
from urllib.request import urlopen

BASE=Path('/opt/chickenbro-candidates/poe2-20260918')
SRC=BASE/'release-integration'
PACK=Path('/var/lib/chickenbro/releases/poe2-20260921')
TARGET=Path('/opt/chickenbro-releases/poe2-77cee1603')
WEB=Path('/var/www/chickenbro-web/releases/poe2-77cee1603')
RUNTIME=Path('/opt/chickenbro-poe2-runtime/7d6f530c')
LINK=Path('/opt/chickenbro'); WLINK=Path('/var/www/chickenbro-web/current')
UNITS=('chickenbro-api','chickenbro-worker')
DROP='99-poe2-20260921.conf'
VERIFY_DB='chickenbro_poe2_release_verify_20260921'

def call(args,**kwargs):return subprocess.run(args,check=True,**kwargs)
def inventory(path):return {str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(path.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
def write(name,data):
 p=PACK/name;p.write_text(json.dumps(data,indent=2));p.chmod(0o600)
def env(unit):
 pid=subprocess.check_output(['systemctl','show',unit,'-p','MainPID','--value'],text=True).strip()
 return dict(x.split('=',1) for x in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in x)
def digest(e):return hashlib.sha256(json.dumps({k:v for k,v in e.items() if k not in ('INVOCATION_ID','JOURNAL_STREAM','SYSTEMD_EXEC_PID')},sort_keys=True).encode()).hexdigest()
def switch(link,dest):
 temp=link.with_name(link.name+'.poe2-next');temp.symlink_to(dest);os.replace(temp,link)
def migration(db):
 sys.path.insert(0,str(TARGET));import psycopg
 with psycopg.connect('dbname='+db) as conn:importlib.import_module('server.migrations.product.apply').apply_product_migrations(conn,TARGET/'server/migrations/product')
def dbcommand(db,sql):
 return subprocess.check_output(['sudo','-u','postgres','psql','-At',db,'-v','ON_ERROR_STOP=1','-c',sql],text=True).strip()
def ready():
 for _ in range(30):
  try:
   with urlopen('http://127.0.0.1:8790/api/v2/health/readiness',timeout=5) as r:
    if r.status==200:return
  except Exception:pass
  time.sleep(1)
 raise RuntimeError('readiness failed')

mode=sys.argv[1]
if mode=='migrate':migration(sys.argv[2]);sys.exit()
assert os.geteuid()==0
PACK.mkdir(parents=True,exist_ok=True);PACK.chmod(0o700)
with open('/run/lock/chickenbro-release.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if mode=='prepare':
  assert not (PACK/'manifest.json').exists()
  before={u:env(u) for u in UNITS}
  assert all('chickenbro_prod' in e.get('WOW_DATABASE_URL','') for e in before.values())
  write('private-environments.json',before)
  assert not TARGET.exists() and not WEB.exists() and not RUNTIME.exists()
  shutil.copytree(SRC,TARGET,ignore=shutil.ignore_patterns('node_modules','__pycache__','*.pyc'))
  shutil.copytree(BASE/'release-web',WEB)
  shutil.copytree(BASE/'upstream/pob',RUNTIME/'pob')
  shutil.copytree(BASE/'runtime/root',RUNTIME/'root',symlinks=True)
  for unit in UNITS:assert not (Path('/etc/systemd/system')/(unit+'.service.d')/DROP).exists()
  config='[Service]\n'+''.join('Environment="'+k+'='+v+'"\n' for k,v in {
   'POE2_POB_ROOT':str(RUNTIME/'pob'),'POE2_LUAJIT':str(RUNTIME/'root/usr/bin/luajit'),
   'POE2_ENGINE_VERSION':'v0.23.1@7d6f530cbdab20389ff8bc6ba97a37ac27f74e41',
   'POE2_ENGINE_LOCK':'/var/lib/chickenbro/poe2-engine.lock',
   'POE2_LD_LIBRARY_PATH':str(RUNTIME/'root/usr/lib/x86_64-linux-gnu'),
   'POE2_LUA_PATH':str(RUNTIME/'pob/runtime/lua/?.lua')+';'+str(RUNTIME/'pob/runtime/lua/?/init.lua')+';;',
   'POE2_LUA_CPATH':str(RUNTIME/'root/usr/lib/x86_64-linux-gnu/lua/5.1/?.so')+';;'}.items())
  (PACK/'dropin.conf').write_text(config)
  with (PACK/'production.dump').open('wb') as out:call(['sudo','-u','postgres','pg_dump','-Fc','chickenbro_prod'],stdout=out)
  (PACK/'production.dump').chmod(0o600)
  call(['sudo','-u','postgres','createdb',VERIFY_DB])
  with (PACK/'production.dump').open('rb') as data:call(['sudo','-u','postgres','pg_restore','--exit-on-error','-d',VERIFY_DB],stdin=data)
  call(['sudo','-u','postgres','/opt/chickenbro-runtime/bin/python',__file__,'migrate',VERIFY_DB])
  assert dbcommand(VERIFY_DB,"SELECT count(*) FROM information_schema.columns WHERE table_schema='poe2' AND table_name='builds' AND column_name='deleted_at'")=='1'
  manifest={'sourceCommit':'77cee1603','backendBase':str(LINK.resolve()),'webBase':str(WLINK.resolve()),'backend':str(TARGET),'web':str(WEB),
   'backendBaseFiles':inventory(LINK.resolve()),'webBaseFiles':inventory(WLINK.resolve()),'backendFiles':inventory(TARGET),'webFiles':inventory(WEB),
   'environmentDigests':{u:digest(e) for u,e in before.items()},'restoreDatabase':VERIFY_DB,'restoreAndMigrationPassed':True,
   'dumpSha256':hashlib.sha256((PACK/'production.dump').read_bytes()).hexdigest()}
  write('manifest.json',manifest);print(json.dumps({'prepared':True,'restoredAndMigrated':True,'backendFiles':len(manifest['backendFiles']),'webFiles':len(manifest['webFiles'])}))
 elif mode=='promote':
  m=json.loads((PACK/'manifest.json').read_text())
  assert str(LINK.resolve())==m['backendBase'] and str(WLINK.resolve())==m['webBase']
  assert inventory(LINK.resolve())==m['backendBaseFiles'] and inventory(WLINK.resolve())==m['webBaseFiles']
  assert inventory(TARGET)==m['backendFiles'] and inventory(WEB)==m['webFiles']
  assert all(digest(env(u))==m['environmentDigests'][u] for u in UNITS)
  sys.path.insert(0,str(TARGET));from scripts.badcase_deploy import database_connector
  e=env(UNITS[0]);connect=lambda:database_connector(e)(e['WOW_DATABASE_URL'])
  deadline=time.monotonic()+120
  stopped=False
  try:
   while True:
    with connect() as conn:
     conn.execute("SET LOCAL lock_timeout='5000ms'")
     conn.execute('LOCK TABLE chat.agent_runs,chat.executions,simc.simulation_jobs,ops.job_queue IN SHARE MODE')
     active=sum(conn.execute('SELECT count(*) FROM '+q).fetchone()[0] for q in ["chat.agent_runs WHERE status='streaming'","chat.executions WHERE stage IN ('pending','queued','running')","simc.simulation_jobs WHERE status IN ('queued','running')","ops.job_queue WHERE status IN ('queued','running')"])
     if not active:
      call(['systemctl','stop',*UNITS]);stopped=True;break
    assert time.monotonic()<deadline,'active jobs prevent release'
    time.sleep(1)
   call(['sudo','-u','postgres','/opt/chickenbro-runtime/bin/python',__file__,'migrate','chickenbro_prod'])
   for unit in UNITS:
    p=Path('/etc/systemd/system')/(unit+'.service.d')/DROP;p.parent.mkdir(exist_ok=True);shutil.copyfile(PACK/'dropin.conf',p)
   switch(LINK,TARGET);switch(WLINK,WEB);call(['systemctl','daemon-reload']);call(['systemctl','start','chickenbro-worker']);call(['systemctl','start','chickenbro-api']);ready()
   for u in UNITS:
    current=env(u);old=json.loads((PACK/'private-environments.json').read_text())[u]
    assert all(current.get(k)==v for k,v in old.items() if k not in ('INVOCATION_ID','JOURNAL_STREAM','SYSTEMD_EXEC_PID'))
    assert current['POE2_POB_ROOT']==str(RUNTIME/'pob')
   write('promoted.json',{'passed':True,'sourceCommit':m['sourceCommit'],'backend':str(LINK.resolve()),'web':str(WLINK.resolve()),'database':'chickenbro_prod','existingEnvironmentPreserved':True})
   print(json.dumps({'promoted':True,'businessVerification':'pending'}))
  except Exception:
   # Do not interrupt post-start work automatically; retained pointers allow controlled recovery.
   write('failed.json',{'failed':True,'stopped':stopped,'backend':str(LINK.resolve()),'web':str(WLINK.resolve())})
   raise
 else:raise ValueError('unknown mode')

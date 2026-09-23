"""QQ-only cutover with pinned base, shared lock and restore-verified backup."""
import fcntl,hashlib,json,os,shutil,subprocess,time,urllib.request
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/opt/chickenbro-qq-releases/20260923-companion-active-v4')
OLD=Path('/opt/chickenbro-qq-releases/20260923-companion-social-v3')
CONFIG=Path('/etc/chickenbro-qq-channel/channel.json')
ENV=Path('/etc/chickenbro-qq-channel/production.env')
EVIDENCE=Path('/var/lib/chickenbro/qq-companion-activation-release.json')
def run(*args,**kw):return subprocess.run(args,check=True,**kw)
def output(*args):return subprocess.check_output(args,text=True).strip()
def sql(db,q):return output('sudo','-u','postgres','psql','-d',db,'-At','-v','ON_ERROR_STOP=1','-c',q)
def counts(db):
 tables=sql(db,"SELECT table_schema||'.'||table_name FROM information_schema.tables WHERE table_type='BASE TABLE' AND table_schema IN ('qq_channel','chat','identity','simc','jobs') ORDER BY 1").splitlines()
 return {t:int(sql(db,'SELECT count(*) FROM '+t)) for t in tables}
def website():return {'apiPid':output('systemctl','show','chickenbro-api','-p','MainPID','--value'),'workerPid':output('systemctl','show','chickenbro-worker','-p','MainPID','--value'),'code':str(Path('/opt/chickenbro').resolve()),'web':str(Path('/var/www/chickenbro-web/current').resolve()),'napcatStarted':output('docker','inspect','--format','{{.State.StartedAt}}','chickenbro-napcat')}
def pending():
 return int(sql('chickenbro_qq_channel',"SELECT (SELECT count(*) FROM qq_channel.inbox WHERE state IN ('pending','running'))+(SELECT count(*) FROM qq_channel.companion_responses WHERE state IN ('pending','running'))+(SELECT count(*) FROM qq_channel.outbox WHERE state IN ('pending','sending'))"))
def atomic(path,data):
 temp=path.with_name(path.name+'.activation-tmp');assert not temp.exists()
 with temp.open('x') as f:os.chmod(temp,0o600);f.write(data);f.flush();os.fsync(f.fileno())
 temp.replace(path)
def point(target):
 temp=Path('/opt/chickenbro-qq-activation-next');assert not temp.exists();temp.symlink_to(target);temp.replace('/opt/chickenbro-qq-current')
def healthy():
 for _ in range(40):
  if output('systemctl','is-active','chickenbro-qq-channel')=='active':
   p=Path('/var/lib/chickenbro/qq-channel/health.json')
   if p.exists():
    h=json.loads(p.read_text())
    if h.get('qqOnline') and h.get('runtimeRevision')=='qq-companion-20260923-active-v4' and time.time()-h['observedAt']<8:return h
  time.sleep(.5)
 raise AssertionError('QQ fresh online health not observed')
with open('/run/lock/chickenbro-release.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert Path('/opt/chickenbro-qq-current').resolve()==OLD,'production baseline changed'
 m=json.loads((ROOT/'release-manifest.json').read_text())
 for p,h in m['files'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
 baseline=json.loads((OLD/'release-manifest.json').read_text())
 for p,h in baseline['files'].items():assert hashlib.sha256((OLD/p).read_bytes()).hexdigest()==h,p
 raw=json.loads(CONFIG.read_text());assert raw['mode']=='companion' and raw['proactiveEnabled'] is False
 before=website();deadline=time.monotonic()+90
 while pending() and time.monotonic()<deadline:time.sleep(2)
 assert pending()==0,'QQ tasks still active; no cutover'
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
 backup=Path('/var/backups/chickenbro')/('qq-activation-'+stamp);backup.mkdir(mode=0o700,parents=True)
 for p in (CONFIG,ENV):shutil.copy2(p,backup/p.name);(backup/p.name).chmod(0o600)
 state={'oldRelease':str(OLD),'newRelease':str(ROOT),'backup':str(backup),'websiteBefore':before,'manifestFiles':len(m['files']),'userAcceptedScope':'mention_text_and_expression_visible','proactiveGroupAcceptance':'pending_natural_group_traffic'}
 stopped=False;switched=False
 try:
  run('systemctl','stop','chickenbro-qq-channel');stopped=True
  assert pending()==0,'new work appeared; resume old service'
  run('systemctl','stop','chickenbro-qq-worker')
  with (backup/'qq.dump').open('wb') as f:run('sudo','-u','postgres','pg_dump','-Fc','chickenbro_qq_channel',stdout=f)
  restore='chickenbro_qq_activation_restore_'+stamp.lower().replace('t','_').replace('z','')
  run('sudo','-u','postgres','createdb',restore)
  with (backup/'qq.dump').open('rb') as f:run('sudo','-u','postgres','pg_restore','--exit-on-error','--no-owner','-d',restore,stdin=f)
  original=counts('chickenbro_qq_channel');assert original==counts(restore)
  state.update(recoveryDatabase=restore,restoredCountsMatch=True,tableCounts=original,dumpSha256=hashlib.sha256((backup/'qq.dump').read_bytes()).hexdigest())
  (backup/'recovery.json').write_text(json.dumps(state,indent=2))
  # No schema changes in this release; same QQ database, current writes retained.
  env=[x for x in ENV.read_text().splitlines() if not x.startswith('WOW_CODEX_RUNTIME_REVISION=')]
  env.append('WOW_CODEX_RUNTIME_REVISION=qq-companion-20260923-active-v4');atomic(ENV,'\n'.join(env)+'\n')
  point(ROOT);switched=True
  # Verify the passive mode remains online first, then turn on new participation.
  run('systemctl','start','chickenbro-qq-worker','chickenbro-qq-channel');state['passiveModeOnline']=healthy()['qqOnline']
  deadline=time.monotonic()+60
  while pending() and time.monotonic()<deadline:time.sleep(2)
  assert pending()==0,'QQ work active before enabling'
  run('systemctl','stop','chickenbro-qq-channel');assert pending()==0
  raw['proactiveEnabled']=True;raw.setdefault('knownBotQQs',[]);atomic(CONFIG,json.dumps(raw))
  run('systemctl','start','chickenbro-qq-channel');state['health']=healthy()
  assert output('systemctl','is-active','chickenbro-qq-worker')=='active'
  assert website()==before,'unrelated runtime identity changed'
  state.update(websiteAfter=website(),proactiveEnabled=True,mode='companion',status='deployed',observedAt=datetime.now(timezone.utc).isoformat())
  state['websiteReady']=json.loads(urllib.request.urlopen('http://127.0.0.1:8790/api/v2/health/readiness',timeout=5).read())['status']
  EVIDENCE.write_text(json.dumps(state,ensure_ascii=False,indent=2))
  print(json.dumps({k:state[k] for k in ('status','newRelease','manifestFiles','restoredCountsMatch','passiveModeOnline','proactiveEnabled','websiteReady')},ensure_ascii=False))
 except Exception as exc:
  if switched:
   run('systemctl','stop','chickenbro-qq-channel','chickenbro-qq-worker')
   point(OLD)
   for p in (CONFIG,ENV):atomic(p,(backup/p.name).read_text())
  if stopped:run('systemctl','start','chickenbro-qq-worker','chickenbro-qq-channel')
  state.update(status='failed_restored_previous_configuration',errorType=type(exc).__name__)
  EVIDENCE.write_text(json.dumps(state,ensure_ascii=False,indent=2))
  raise

"""Publish immutable QQ code with both business services stopped throughout.
No DB mutation, service start/restart, NapCat or website changes are permitted.
"""
import fcntl,hashlib,json,os,shutil,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path('/opt/chickenbro-candidates/qq-badcase-20260924')
OLD=Path('/opt/chickenbro-qq-releases/20260923-companion-persona-v6')
NEW=Path('/opt/chickenbro-qq-releases/20260924-badcase-v7')
LINK=Path('/opt/chickenbro-qq-current')
ENV=Path('/etc/chickenbro-qq-channel/production.env')
CONFIG=Path('/etc/chickenbro-qq-channel/channel.json')
SPEC=json.loads((ROOT/'deploy-spec.json').read_text())
CHANGED=SPEC['changedFiles'];REVISION='qq-badcase-20260924-v7'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def out(*args):return subprocess.check_output(args,text=True).strip()
def state(unit):return out('systemctl','show',unit,'-p','ActiveState','--value')
def run(*args):subprocess.run(args,check=True,timeout=30)
def atomic(path,data):
 tmp=path.with_name(path.name+'.qq-badcase-tmp');assert not tmp.exists()
 fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
def point(target):
 tmp=Path('/opt/chickenbro-qq-badcase-next');assert not tmp.exists()
 tmp.symlink_to(target);os.replace(tmp,LINK)
def website():
 return {'apiPid':out('systemctl','show','chickenbro-api','-p','MainPID','--value'),'workerPid':out('systemctl','show','chickenbro-worker','-p','MainPID','--value'),'code':str(Path('/opt/chickenbro').resolve()),'web':str(Path('/var/www/chickenbro-web/current').resolve()),'napcatStarted':out('docker','inspect','--format','{{.State.StartedAt}}','chickenbro-napcat')}
def pending():
 sql="BEGIN READ ONLY; SET LOCAL statement_timeout='10s'; SELECT (SELECT count(*) FROM qq_channel.inbox WHERE state IN ('pending','running'))+(SELECT count(*) FROM qq_channel.companion_responses WHERE state IN ('pending','running'))+(SELECT count(*) FROM qq_channel.outbox WHERE state IN ('pending','sending'))+(SELECT count(*) FROM chat.executions WHERE stage IN ('pending','running')); COMMIT;"
 return int(out('sudo','-u','postgres','psql','-X','-qAt','-v','ON_ERROR_STOP=1','chickenbro_qq_channel','-c',sql))
with open('/run/lock/chickenbro-release.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert state('chickenbro-qq-channel')=='inactive','QQBot must already be stopped'
 assert LINK.resolve()==OLD and digest(OLD/'release-manifest.json')==SPEC['baselineManifestSha256'],'baseline changed'
 baseline=json.loads((OLD/'release-manifest.json').read_text())
 for p,h in baseline['files'].items():assert digest(OLD/p)==h,p
 for p,h in CHANGED.items():assert p in baseline['files'] and digest(ROOT/p)==h,p
 assert SPEC['candidateVerified'] and SPEC['reviewPassed']
 assert not NEW.exists(),'Existing release requires reconciliation, not retry'
 assert pending()==0,'QQ work active; keep existing state'
 before=website();original_env=ENV.read_bytes();original_config=CONFIG.read_bytes()
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
 backup=Path('/var/backups/chickenbro')/('qq-badcase-'+stamp);backup.mkdir(mode=0o700)
 atomic(backup/'production.env',original_env);atomic(backup/'channel.json',original_config)
 assert (backup/'production.env').read_bytes()==original_env and (backup/'channel.json').read_bytes()==original_config
 shutil.copytree(OLD,NEW,ignore=shutil.ignore_patterns('__pycache__'))
 for p in CHANGED:shutil.copyfile(ROOT/p,NEW/p)
 files={p:digest(NEW/p) for p in baseline['files']}
 assert set(p for p in files if files[p]!=baseline['files'][p])==set(CHANGED)
 manifest={'release':NEW.name,'createdAt':datetime.now(timezone.utc).isoformat(),'sourceCommit':SPEC['sourceCommit'],'baseRelease':OLD.name,'files':files,'changedFiles':list(CHANGED),'preservedPersonaSha256':files['server/app/channels/qq/persona.md'],'sourceScope':'five QQ repair files; remaining runtime files preserved from verified persona-v6'}
 (NEW/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 run('systemctl','stop','chickenbro-qq-worker')
 assert state('chickenbro-qq-channel')=='inactive' and state('chickenbro-qq-worker')=='inactive'
 assert pending()==0
 switched=False
 try:
  env=[line for line in original_env.decode().splitlines() if not line.startswith('WOW_CODEX_RUNTIME_REVISION=')]
  env.append('WOW_CODEX_RUNTIME_REVISION='+REVISION)
  atomic(ENV,('\n'.join(env)+'\n').encode());point(NEW);switched=True
  assert LINK.resolve()==NEW and CONFIG.read_bytes()==original_config
  assert state('chickenbro-qq-channel')=='inactive' and state('chickenbro-qq-worker')=='inactive'
  assert website()==before
  for p,h in files.items():assert digest(NEW/p)==h,p
  evidence={'status':'deployed_stopped_pending_live_acceptance','observedAt':datetime.now(timezone.utc).isoformat(),'release':str(NEW),'previousRelease':str(OLD),'sourceCommit':SPEC['sourceCommit'],'changedFiles':list(CHANGED),'manifestFiles':len(files),'manifestSha256':digest(NEW/'release-manifest.json'),'runtimeRevision':REVISION,'channelState':state('chickenbro-qq-channel'),'workerState':state('chickenbro-qq-worker'),'groupMessagesSent':0,'databaseChanged':False,'groupConfigUnchanged':True,'websiteBefore':before,'websiteAfter':website(),'recovery':{'oldTreeVerified':True,'configurationBackup':str(backup),'configurationReadbackVerified':True,'rollbackMustKeepStopped':True},'liveBusinessAcceptance':'not_run_user_requires_stopped'}
  atomic(Path('/var/lib/chickenbro/qq-badcase-20260924-release.json'),(json.dumps(evidence,indent=2)+'\n').encode());print(json.dumps(evidence))
 except BaseException:
  if switched:
   assert LINK.resolve()==NEW,'unexpected pointer; refuse overwrite'
   point(OLD)
  atomic(ENV,original_env)
  assert LINK.resolve()==OLD and ENV.read_bytes()==original_env
  assert state('chickenbro-qq-channel')=='inactive' and state('chickenbro-qq-worker')=='inactive'
  raise

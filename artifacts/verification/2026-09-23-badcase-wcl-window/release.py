"""Pinned orchestration with one lock through promotion, semantic review and observation."""
import fcntl,hashlib,importlib.util,json,os,subprocess,time
from datetime import datetime,timezone
from urllib.request import urlopen
from urllib.parse import quote
from pathlib import Path
os.umask(0o077)
root=Path('/var/lib/chickenbro-badcase-wcl-window-20260923')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
frozen=json.loads((root/'frozen-release-v2.json').read_text())
for name,value in frozen['files'].items():assert digest(root/name)==value,'pinned file changed'
spec=importlib.util.spec_from_file_location('deploy',root/'deploy.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
state={'status':'publishing','sourceCommit':frozen['sourceCommit']}
def save(): (root/'release-state.json').write_text(json.dumps(state,indent=2))
class SmokeStillRunning(RuntimeError):pass
def smoke(label,source,before=False):
 args=['/opt/chickenbro-runtime/bin/python',str(root/'smoke.py'),'production',str(source),'--label',label]
 if before:args.append('--before')
 p=subprocess.Popen(args,stdout=open(root/(label+'-output.log'),'w'),stderr=subprocess.STDOUT)
 try:
  result=p.wait(timeout=600)
 except subprocess.TimeoutExpired:
  (root/(label+'-stop')).touch()
  try:p.wait(timeout=480)
  except subprocess.TimeoutExpired:raise SmokeStillRunning('smoke still active; no rollback or concurrent recovery until it exits')
  raise RuntimeError('smoke timed out and drained; receipts preserved')
 assert result==0,'business smoke failed; inspect preserved receipt'
with open('/run/lock/chickenbro-release.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 release=m.Release(root/'manifest.json');release.run('preflight');release.run('stage')
 save();cutover_attempted=False
 try:
  cutover_attempted=True;release.run('promote');promoted_at=datetime.now(timezone.utc);print('promoted; live smoke started',flush=True)
  smoke('live',release.target)
  print('live receipts ready; awaiting bound semantic verdict',flush=True)
  deadline=time.monotonic()+180
  while not (root/'live-verdict.json').exists() and time.monotonic()<deadline:time.sleep(1)
  verdict=json.loads((root/'live-verdict.json').read_text())
  assert verdict['receiptSha256']==digest(root/'live-private.json') and verdict['corePassed'] is True,'semantic acceptance not passed'
  started=time.monotonic()
  while time.monotonic()-started<60:
   release.run('verify')
   with release.connect() as c:
    errors=c.execute("SELECT count(*) FROM chat.agent_runs WHERE started_at>%s AND status='failed'",(promoted_at,)).fetchone()[0]
    assert errors==0,'new Chat failures in bounded observation'
   time.sleep(10)
  public={}
  for name,expected in release.m['webFiles'].items():
   with urlopen('https://www.chickenbro.cloud/'+quote(name)+'?badcase='+frozen['sourceCommit'][:12],timeout=20) as response:
    actual=hashlib.sha256(response.read()).hexdigest()
   public[name]=actual==expected
   assert public[name],'public Web artifact mismatch'
  state.update(publicWebHashes=public)
  state.update(status='released',coreSemanticVerdict=verdict,observationSeconds=60);save();print('released with core live verification',flush=True)
 except SmokeStillRunning:
  state.update(status='failed',recovery='pending: smoke child remains active; stop marker prevents further submissions');save();raise
 except BaseException:
  state['status']='failed';save()
  if cutover_attempted:
   current=release.link.resolve()
   assert current in (release.base,release.target),'foreign runtime prevents recovery'
   if current==release.target:release.run('rollback')
   else:
    release.runtime(allow_recovery=True);release.verify(release.base)
   smoke('recovery',release.base,before=True)
   state['recovery']='baseline pointer/runtime and real WCL Chat smoke restored';save();print('rolled back; recovery receipts require semantic readback',flush=True)
  raise

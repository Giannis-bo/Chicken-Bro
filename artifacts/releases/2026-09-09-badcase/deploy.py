"""Exact ten-file overlay; PostgreSQL admission fence protects API/worker restart."""
import hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
from urllib.request import urlopen
CODE=Path('/opt/chickenbro')
WEB=Path('/var/www/chickenbro-web/current')
UNITS=('chickenbro-api.service','chickenbro-worker.service')
FILES={'server/app/api/routes/chat.py','server/app/chickenbro/agent/AGENTS.md','server/app/chickenbro/application.py','server/app/chickenbro/codex_adapter.py','server/app/chickenbro/raiderio_research.py','server/app/chickenbro/source_gateway.py','server/app/chickenbro/wcl_source.py','server/chickenbro_native_mcp.py','server/app/chickenbro/character_discovery.py','server/app/chickenbro/delivery.py'}
COUNT="SELECT (SELECT count(*) FROM chat.agent_runs WHERE status='streaming')+(SELECT count(*) FROM simc.simulation_jobs WHERE status IN ('queued','running'))+(SELECT count(*) FROM ops.job_queue WHERE status IN ('queued','running'));"
def run(*args):return subprocess.check_output(args,text=True,stderr=subprocess.PIPE).strip()
def hashes(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts}
def ready():
 try:
  with urlopen('http://127.0.0.1:8790/api/v2/health/readiness',timeout=5) as r:return json.load(r).get('status')=='ready'
 except Exception:return False
def switch(target):
 pending=CODE.with_name('chickenbro.badcase-next')
 if pending.exists() or pending.is_symlink():raise RuntimeError('unfinished switch')
 pending.symlink_to(target);pending.replace(CODE)
def stop_idle():
 # Hold table locks while stopping: racing requests cannot persist new accepted runs.
 # No locks remain across restart; existing jobs are never killed to meet a deadline.
 gate=subprocess.Popen(['sudo','-n','-u','postgres','psql','-X','-qAt','-v','ON_ERROR_STOP=1','-d','chickenbro_prod'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 try:
  gate.stdin.write("BEGIN; SET lock_timeout='3s'; LOCK TABLE chat.agent_runs,simc.simulation_jobs,ops.job_queue IN ACCESS EXCLUSIVE MODE; "+COUNT+'\n');gate.stdin.flush()
  count=gate.stdout.readline().strip()
  if count!='0':raise RuntimeError('production_not_idle_or_lock_unavailable')
  for unit in UNITS:run('systemctl','stop',unit)
 finally:
  if gate.poll() is None:
   gate.stdin.write('ROLLBACK;\n');gate.stdin.close()
  gate.wait(timeout=5)
def start_ready():
 for unit in UNITS:run('systemctl','start',unit)
 deadline=time.monotonic()+45
 while not ready():
  if time.monotonic()>deadline:raise RuntimeError('readiness_failed')
  time.sleep(1)
 if any(run('systemctl','is-active',u)!='active' for u in UNITS):raise RuntimeError('unit_inactive')
def main():
 manifest,payload,sha,mode=sys.argv[1:5];p=Path(manifest)
 if os.geteuid()!=0 or hashlib.sha256(p.read_bytes()).hexdigest()!=sha:raise RuntimeError('manifest_or_admin_mismatch')
 m=json.loads(p.read_text());target=Path('/opt/chickenbro-releases')/('badcase-'+m['commit'])
 if len(m['commit'])!=40 or any(c not in '0123456789abcdef' for c in m['commit']):raise RuntimeError('invalid_commit')
 if set(m['files'])!=FILES or set(m['beforeFiles'])!=FILES:raise RuntimeError('scope_mismatch')
 before=Path(m['previousCode']);original=hashes(before)
 if any(original.get(f)!=h for f,h in m['beforeFiles'].items()):raise RuntimeError('base_changed')
 if hashes(Path(payload))!=m['files']:raise RuntimeError('payload_mismatch')
 expected={**original,**m['files']}
 if not target.exists():
  shutil.copytree(before,target,symlinks=True,ignore=shutil.ignore_patterns('__pycache__'))
  for f in FILES:
   dest=target/f
   if dest.is_symlink():raise RuntimeError('symlink_destination')
   dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(Path(payload)/f,dest);dest.chmod(0o644)
 if hashes(target)!=expected:raise RuntimeError('staged_hash_mismatch')
 if mode=='stage':
  print(json.dumps({'status':'staged_verified','target':str(target),'fileCount':len(expected)}));return
 if str(CODE.resolve())!=m['previousCode'] or str(WEB.resolve())!=m['previousWeb'] or not ready():raise RuntimeError('production_precondition_changed')
 for unit in UNITS:
  if run('systemctl','show',unit,'-p','WorkingDirectory','--value')!=str(CODE):raise RuntimeError('working_directory_changed')
 if run('sudo','-n','-u','postgres','psql','-X','-qAt','-d','chickenbro_prod','-c','SELECT id FROM ops.schema_migrations ORDER BY id').splitlines()!=m['migrations']:raise RuntimeError('migrations_changed')
 if mode=='dry-run':print(json.dumps({'status':'preflight_verified'}));return
 if mode not in {'promote','rollback'}:raise RuntimeError('unknown_mode')
 if mode=='rollback':raise RuntimeError('use rollback manifest with expected current identity')
 stopped=False
 try:
  stop_idle();stopped=True
  switch(target);start_ready()
  if hashes(target)!=expected or str(WEB.resolve())!=m['previousWeb']:raise RuntimeError('post_switch_mismatch')
 except Exception:
  # stop_idle can stop one unit before failing; always restore the previous services.
  if str(CODE.resolve())==str(target):
   stop_idle();switch(before)
  elif str(CODE.resolve())!=str(before):raise RuntimeError('concurrent_release_requires_attention') from None
  start_ready()
  raise
 print(json.dumps({'status':'switched_health_verified','commit':m['commit'],'codeRoot':str(target),'rollbackCode':str(before),'webUnchanged':m['previousWeb'],'databaseChanged':False}))
if __name__=='__main__':main()

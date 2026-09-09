"""Exact-overlay, idle-fenced G2 backend release on the known host.

Run as root with the installed runtime. No downloads, Web changes or reverse
migrations. stdout is restricted to identities, counts and outcome literals.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.request import urlopen
from uuid import uuid4

p=argparse.ArgumentParser()
p.add_argument('manifest')
p.add_argument('action',choices=['preflight','stage','promote','rollback'])
a=p.parse_args()
m=json.loads(Path(a.manifest).read_text())
commit=m['sourceCommit']
if len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit):raise RuntimeError('exact commit required')
base=Path(m['expectedBase'])
target=Path('/opt/chickenbro-releases/g2-'+commit)
overlay=Path(a.manifest).parent/'overlay'
drop_name='99-g2-durable-'+commit[:12]+'.conf'
drops=[Path('/etc/systemd/system')/(unit+'.service.d')/drop_name for unit in ('chickenbro-api','chickenbro-worker')]
worker_env=Path('/etc/chickenbro-g2-'+commit[:12]+'.env')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def service(*args):subprocess.run(['systemctl',*args],check=True,stdout=subprocess.DEVNULL)
def environment(unit):
    pid=subprocess.check_output(['systemctl','show',unit,'-p','MainPID','--value'],text=True).strip()
    if pid=='0':raise RuntimeError('service is not running: '+unit)
    return dict(item.split('=',1) for item in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in item)
def scoped(root,name):
    relative=Path(name)
    if not name.startswith('server/') or relative.is_absolute() or '..' in relative.parts:
        raise RuntimeError('invalid overlay scope')
    path=root/relative
    if not path.resolve().is_relative_to(root.resolve()) or any((root/Path(*relative.parts[:i])).is_symlink() for i in range(1,len(relative.parts)+1)):
        raise RuntimeError('symlink in overlay scope')
    return path
def inspect_base():
    if set(m['files'])!=set(m['baseHashes']):raise RuntimeError('manifest path sets differ')
    if Path('/opt/chickenbro').resolve()!=base:raise RuntimeError('production pointer drifted')
    for name,expected in m['baseHashes'].items():
        path=scoped(base,name)
        if expected is None:
            if path.exists():raise RuntimeError('new overlay path already exists: '+name)
        elif not path.is_file() or sha(path)!=expected:
            raise RuntimeError('production file drift: '+name)
    for name,expected in m['files'].items():
        if sha(scoped(overlay,name))!=expected:raise RuntimeError('overlay hash mismatch')
def connect_from(env):
    os.environ.update(env)
    sys.path.insert(0,str(target if target.exists() else base))
    from server.app.platform.config import AppSettings
    from server.app.platform.postgres import PostgresConnectionFactory
    return PostgresConnectionFactory(AppSettings.from_env(env)).connection
def active(conn):
    counts={}
    for name,sql in {
        'chat':"SELECT count(*) FROM chat.agent_runs WHERE status='streaming'",
        'simc':"SELECT count(*) FROM simc.simulation_jobs WHERE status IN ('queued','running')",
        'queue':"SELECT count(*) FROM ops.job_queue WHERE status IN ('queued','running')"}.items():
        counts[name]=conn.execute(sql).fetchone()[0]
    return counts
def idle_fence(conn):
    conn.execute("SET LOCAL lock_timeout='5s'")
    conn.execute('LOCK TABLE chat.agent_runs,simc.simulation_jobs,ops.job_queue IN SHARE MODE')
    counts=active(conn)
    if any(counts.values()):raise RuntimeError('active tasks prevent release: '+json.dumps(counts))
    return counts
def switch(path):
    temporary=Path('/opt/.chickenbro-g2-'+str(uuid4()))
    temporary.symlink_to(path)
    os.replace(temporary,'/opt/chickenbro')
def ready():
    for _ in range(30):
        try:
            with urlopen('http://127.0.0.1:8790/api/v2/health/readiness',timeout=3) as response:
                if json.load(response).get('status')=='ready':return True
        except Exception:pass
        time.sleep(1)
    return False

if a.action in ('preflight','stage','promote'):
    inspect_base()
    api_env=environment('chickenbro-api')
    old_worker_env=environment('chickenbro-worker')
    if api_env['WOW_DATABASE_URL']!=old_worker_env['WOW_DATABASE_URL']:
        raise RuntimeError('API and worker database identities differ')
    connect=connect_from(api_env)
    with connect() as conn:counts=active(conn)
    print(json.dumps({'action':a.action,'expectedBase':str(base),'target':str(target),'active':counts,
        'rootFreeBytes':shutil.disk_usage('/opt').free,'web':str(Path('/var/www/chickenbro-web/current').resolve())}),flush=True)
    if a.action=='preflight':raise SystemExit(0)
    if not target.exists():
        shutil.copytree(base,target,symlinks=True)
        for name in m['files']:
            path=scoped(target,name)
            path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(scoped(overlay,name),path)
        (target/'G2_MANIFEST.json').write_text(json.dumps(m,indent=2))
    if json.loads((target/'G2_MANIFEST.json').read_text())!=m:
        raise RuntimeError('staged manifest differs from this release')
    def retained_files(root):
        return {str(path.relative_to(root)) for path in root.rglob('*')
            if (path.is_file() or path.is_symlink()) and '__pycache__' not in path.parts
            and path.suffix!='.pyc' and str(path.relative_to(root)) not in m['files']
            and str(path.relative_to(root))!='G2_MANIFEST.json'}
    if retained_files(base)!=retained_files(target):raise RuntimeError('non-overlay file set drift')
    for name,expected in m['files'].items():
        if sha(scoped(target,name))!=expected:raise RuntimeError('staged file mismatch')
    # The base release is retained and must remain immutable between staging and promotion.
    for path in base.rglob('*'):
        relative=str(path.relative_to(base))
        if relative in m['files'] or '__pycache__' in path.parts or path.suffix=='.pyc':continue
        staged=target/relative
        if path.is_symlink():
            if not staged.is_symlink() or os.readlink(path)!=os.readlink(staged):raise RuntimeError('base symlink drift: '+relative)
        elif path.is_file() and (staged.is_symlink() or not staged.is_file() or sha(path)!=sha(staged)):
            raise RuntimeError('non-overlay base drift: '+relative)
    if a.action=='stage':
        print(json.dumps({'staged':True,'sourceCommit':commit,'runtimeFiles':len(m['files'])}),flush=True)
        raise SystemExit(0)
    selected={key:value for key,value in api_env.items() if key.startswith('WOW_WARCRAFTLOGS_') or key in {
        'CODEX_HOME','WOW_CODEX_HOME','WOW_CODEX_BIN','WOW_CODEX_JOBS_DIR','WOW_CODEX_PROFILE',
        'WOW_CODEX_RUNTIME_REVISION','WOW_CHICKENBRO_CODEX_ENABLED','CHICKENBRO_CHAT_IMAGES_ENABLED',
        'HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','all_proxy','no_proxy'}}
    if selected.get('WOW_CHICKENBRO_CODEX_ENABLED')!='1':raise RuntimeError('native model is not enabled')
    if any('\n' in value or '\0' in value for value in selected.values()):raise RuntimeError('invalid environment value')
    env_text=''.join(key+'="'+value.replace('\\','\\\\').replace('"','\\"')+'"\n' for key,value in sorted(selected.items()))
    if worker_env.exists():
        if worker_env.is_symlink() or worker_env.stat().st_mode & 0o077 or worker_env.read_text()!=env_text:
            raise RuntimeError('existing release environment differs or is not private')
    else:
        fd=os.open(worker_env,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as output:output.write(env_text)
    if any(path.exists() for path in drops):raise RuntimeError('release drop-in already exists')
    api_start_attempted=False
    stopped=False
    try:
        with connect() as conn:
            idle_fence(conn)
            stopped=True
            service('stop','chickenbro-api')
            service('stop','chickenbro-worker')
            importlib.import_module('server.migrations.product.apply').apply_product_migrations(conn,target/'server/migrations/product')
        for index,path in enumerate(drops):
            path.parent.mkdir(parents=True,exist_ok=True)
            text='[Service]\nEnvironment=WOW_CHAT_DURABLE_ENABLED=1\n'
            if index==1:
                text+=f'EnvironmentFile={worker_env}\nEnvironment=WOW_CHAT_WORKER_TOOL_PORT=8794\nProtectHome=read-only\nReadWritePaths=/home/ubuntu/.codex\n'
            path.write_text(text)
        switch(target)
        service('daemon-reload')
        service('start','chickenbro-worker')
        api_start_attempted=True
        service('start','chickenbro-api')
    except Exception:
        # Before opening API admission there can be no newly accepted work.
        # Restore the old topology; after admission starts require idle fencing.
        if stopped and not api_start_attempted:
            service('stop','chickenbro-worker')
            switch(base)
            for path in drops:
                if path.exists():path.unlink()
            service('daemon-reload')
            service('start','chickenbro-worker')
            service('start','chickenbro-api')
        raise
    if not ready():raise RuntimeError('readiness failed; inspect active admissions before the explicit rollback action')
    print(json.dumps({'promoted':True,'sourceCommit':commit,'runtimeFiles':len(m['files']),
        'pointer':str(Path('/opt/chickenbro').resolve()),'readiness':'ready','businessRegression':'required'}),flush=True)
else:
    if Path('/opt/chickenbro').resolve()!=target:raise RuntimeError('rollback target is not current')
    try:
        rollback_env=environment('chickenbro-api')
    except RuntimeError:
        rollback_env=environment('chickenbro-worker')
    connect=connect_from(rollback_env)
    with connect() as conn:
        idle_fence(conn)
        service('stop','chickenbro-api')
        service('stop','chickenbro-worker')
        switch(base)
        for path in drops:
            if path.exists():path.unlink()
    service('daemon-reload')
    service('start','chickenbro-worker')
    service('start','chickenbro-api')
    if not ready():raise RuntimeError('rollback readiness failed')
    print(json.dumps({'rolledBack':True,'pointer':str(base),'schema':'additive migration retained'}),flush=True)

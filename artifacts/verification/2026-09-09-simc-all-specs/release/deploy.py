"""Exact, idle-fenced SimC release. No migrations or engine changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.request import urlopen
from uuid import uuid4

parser = argparse.ArgumentParser()
parser.add_argument('manifest')
parser.add_argument('action', choices=('preflight', 'stage', 'promote', 'rollback'))
args = parser.parse_args()
manifest_path = Path(args.manifest)
m = json.loads(manifest_path.read_text())
commit = m['sourceCommit']
assert len(commit) == 40 and all(c in '0123456789abcdef' for c in commit)
source_link = Path('/opt/chickenbro')
web_link = Path('/var/www/chickenbro-web/current')
base, old_web = Path(m['expectedBackend']), Path(m['expectedWeb'])
target = Path('/opt/chickenbro-releases/simc-all-' + commit)
web = Path('/var/www/chickenbro-web/releases/simc-all-' + commit)
payload = manifest_path.parent
env_file = Path('/etc/chickenbro-simc-all-' + commit[:12] + '.env')
drops = [Path('/etc/systemd/system') / (unit + '.service.d') / ('99-zzzz-simc-all-' + commit[:12] + '.conf')
         for unit in ('chickenbro-api', 'chickenbro-worker')]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def scoped(root, relative):
    p = Path(relative)
    assert not p.is_absolute() and '..' not in p.parts
    result = root / p
    assert result.resolve().is_relative_to(root.resolve())
    assert not any((root / Path(*p.parts[:i])).is_symlink() for i in range(1, len(p.parts) + 1))
    return result

def environment(unit):
    pid = subprocess.check_output(['systemctl', 'show', unit, '-p', 'MainPID', '--value'], text=True).strip()
    assert pid != '0', 'service is not running'
    return dict(v.split('=', 1) for v in Path('/proc/' + pid + '/environ').read_text().split('\0') if '=' in v)

def service(*args):
    subprocess.run(['systemctl', *args], check=True, stdout=subprocess.DEVNULL)

def switch(link, destination):
    temporary = link.with_name('.simc-next-' + uuid4().hex)
    temporary.symlink_to(destination)
    os.replace(temporary, link)

def inventory(root):
    return {str(p.relative_to(root)): ('link:' + os.readlink(p) if p.is_symlink() else sha(p))
            for p in root.rglob('*') if (p.is_file() or p.is_symlink())
            and '__pycache__' not in p.parts and p.suffix != '.pyc'}

def active(conn):
    return {name: conn.execute(sql).fetchone()[0] for name, sql in {
        'chat': "SELECT count(*) FROM chat.agent_runs WHERE status='streaming'",
        'simc': "SELECT count(*) FROM simc.simulation_jobs WHERE status IN ('queued','running')",
        'queue': "SELECT count(*) FROM ops.job_queue WHERE status IN ('queued','running')"}.items()}

def fence(conn):
    conn.execute("SET LOCAL lock_timeout='5s'")
    conn.execute('LOCK TABLE chat.agent_runs,simc.simulation_jobs,ops.job_queue IN SHARE MODE')
    counts = active(conn)
    assert not any(counts.values()), 'active tasks prevent release: ' + json.dumps(counts)

def start_services():
    service('start', 'chickenbro-worker')
    for _ in range(20):
        pid = subprocess.check_output(['systemctl', 'show', 'chickenbro-worker', '-p', 'MainPID', '--value'], text=True).strip()
        listeners = subprocess.check_output(['ss', '-ltnp', 'sport = :28794'], text=True)
        if pid != '0' and ('pid=' + pid + ',') in listeners:
            break
        time.sleep(1)
    else:
        raise RuntimeError('worker tool listener not ready; admission stays closed')
    service('start', 'chickenbro-api')

def ready():
    for _ in range(30):
        try:
            with urlopen('http://127.0.0.1:8790/api/v2/health/readiness', timeout=3) as response:
                if json.load(response).get('status') == 'ready':
                    return all(subprocess.run(['systemctl', 'is-active', '--quiet', u]).returncode == 0
                               for u in ('chickenbro-api', 'chickenbro-worker'))
        except Exception:
            pass
        time.sleep(1)
    return False

api_env = environment('chickenbro-api')
worker_env = environment('chickenbro-worker')
assert api_env['WOW_DATABASE_URL'] == worker_env['WOW_DATABASE_URL']
os.environ.update(api_env)
sys.path.insert(0, str(base))
from server.app.platform.config import AppSettings
from server.app.platform.postgres import PostgresConnectionFactory
connect = PostgresConnectionFactory(AppSettings.from_env(api_env)).connection

if args.action == 'rollback':
    assert source_link.resolve() == target and web_link.resolve() == web
    with connect() as conn:
        fence(conn)
        service('stop', 'chickenbro-api')
        service('stop', 'chickenbro-worker')
    switch(source_link, base)
    switch(web_link, old_web)
    for drop in drops:
        assert drop.read_text() == '[Service]\nEnvironmentFile=' + str(env_file) + '\n'
        drop.unlink()
    service('daemon-reload')
    start_services()
    assert ready()
    print(json.dumps({'rolledBack': True, 'backend': str(base), 'web': str(old_web)}))
    raise SystemExit(0)

assert source_link.resolve() == base and web_link.resolve() == old_web, 'production pointers drifted'
assert inventory(base) == m['baseInventory'], 'base release drifted'
assert set(m['files']) == set(m['baseHashes'])
for name, expected in m['files'].items():
    assert name.startswith('server/'), 'overlay scope invalid'
    assert sha(scoped(payload / 'overlay', name)) == expected
    current = scoped(base, name)
    assert (sha(current) if current.exists() else None) == m['baseHashes'][name]
assert inventory(payload / 'web') == m['webFiles']
assert all(not value.startswith('link:') for value in m['webFiles'].values())
with connect() as conn:
    counts = active(conn)
print(json.dumps({'action': args.action, 'base': str(base), 'previousWeb': str(old_web),
                  'target': str(target), 'active': counts, 'freeBytes': shutil.disk_usage('/opt').free}), flush=True)
if args.action == 'preflight':
    raise SystemExit(0)
assert shutil.disk_usage('/opt').free > 1024 ** 3
if not target.exists():
    shutil.copytree(base, target, symlinks=True)
    for name in m['files']:
        path = scoped(target, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(scoped(payload / 'overlay', name), path)
expected_inventory = {**m['baseInventory'], **m['files']}
assert inventory(target) == expected_inventory, 'staged backend drifted'
if not web.exists():
    shutil.copytree(payload / 'web', web)
assert inventory(web) == m['webFiles'], 'staged web drifted'
if args.action == 'stage':
    print(json.dumps({'staged': True, 'backend': str(target), 'web': str(web), 'sourceCommit': commit}))
    raise SystemExit(0)

assert not env_file.exists() and not any(p.exists() for p in drops)
stopped = False
admission_attempted = False
try:
    with connect() as conn:
        fence(conn)
        stopped = True
        service('stop', 'chickenbro-api')
        service('stop', 'chickenbro-worker')
    with os.fdopen(os.open(env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as output:
        output.write('WOW_SIMC_SUPPORTED_SPECS=all\n')
    for drop in drops:
        drop.parent.mkdir(parents=True, exist_ok=True)
        drop.write_text('[Service]\nEnvironmentFile=' + str(env_file) + '\n')
    switch(source_link, target)
    switch(web_link, web)
    service('daemon-reload')
    # If API start is attempted, rollback must first re-check newly admitted work.
    admission_attempted = True
    start_services()
except Exception:
    if stopped and not admission_attempted:
        service('stop', 'chickenbro-worker')
        switch(source_link, base)
        switch(web_link, old_web)
        for drop in drops:
            if drop.exists():
                drop.unlink()
        service('daemon-reload')
        start_services()
    raise
assert ready(), 'readiness failed; explicit idle-fenced rollback required'
assert source_link.resolve() == target and web_link.resolve() == web
for unit in ('chickenbro-api', 'chickenbro-worker'):
    assert environment(unit).get('WOW_SIMC_SUPPORTED_SPECS') == 'all', 'effective capability override failed'
print(json.dumps({'promoted': True, 'sourceCommit': commit, 'backend': str(target), 'web': str(web),
                  'capabilities': 'all', 'readiness': 'ready', 'businessSmoke': 'required'}), flush=True)

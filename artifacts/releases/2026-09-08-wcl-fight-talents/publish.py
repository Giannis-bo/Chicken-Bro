"""Exact-file backend overlay with idle gate, atomic switch and rollback."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

CODE = Path('/opt/chickenbro')
WEB = Path('/var/www/chickenbro-web/current')
UNITS = ('chickenbro-api.service', 'chickenbro-worker.service')
FILES = {'server/app/simulation/' + p for p in (
    'sources.py', 'wcl_talents.py', 'compiler.py', 'readiness.py', 'data/traits-12.1.0.json')}


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE).strip()


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts}


def ready():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8790/api/v2/health/readiness', timeout=5) as r:
            return json.load(r).get('status') == 'ready'
    except Exception:
        return False


def active_jobs():
    sql = "SELECT (SELECT count(*) FROM chat.agent_runs WHERE status='streaming') + (SELECT count(*) FROM simc.simulation_jobs WHERE status IN ('queued','running')) + (SELECT count(*) FROM ops.job_queue WHERE status IN ('queued','running'));"
    return int(run('sudo', '-u', 'postgres', 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-At', '-d', 'chickenbro_prod', '-c', sql))


def switch(target):
    pending = CODE.with_name('chickenbro.wcl-next')
    if pending.exists() or pending.is_symlink():
        raise ValueError('unfinished switch')
    pending.symlink_to(target)
    try:
        pending.replace(CODE)
    finally:
        if pending.is_symlink():
            pending.unlink()


def stage(m, payload, target):
    if set(m['files']) != FILES or set(m['beforeFiles']) != FILES:
        raise ValueError('unexpected patch scope')
    before = Path(m['previousCode'])
    original = hashes(before)
    if any(original.get(p) != value for p, value in m['beforeFiles'].items()):
        raise ValueError('production inputs changed')
    if any(hashlib.sha256((payload / p).read_bytes()).hexdigest() != value for p, value in m['files'].items()):
        raise ValueError('payload hashes differ')
    expected = {**original, **m['files']}
    # Composite identity is in the manifest; retain the base's original marker.
    if not target.exists():
        shutil.copytree(before, target, symlinks=True, ignore=shutil.ignore_patterns('__pycache__'))
        for p in FILES:
            dest = target / p
            if dest.is_symlink():
                raise ValueError('patch destination is a symlink')
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(payload / p, dest)
            dest.chmod(0o644)
    if hashes(target) != expected:
        raise ValueError('staged release differs from exact overlay')
    return expected


def promote(m, target, expected, apply):
    if str(CODE.resolve()) != m['previousCode'] or str(WEB.resolve()) != m['previousWeb']:
        raise ValueError('production pointers changed')
    if hashes(target) != expected or not ready() or active_jobs():
        raise ValueError('release must match and production must be ready and idle')
    for unit in UNITS:
        if run('systemctl', 'show', unit, '-p', 'WorkingDirectory', '--value') != str(CODE):
            raise ValueError('effective runtime differs')
    if run('sudo', '-u', 'postgres', 'psql', '-X', '-At', '-d', 'chickenbro_prod', '-c',
           'SELECT id FROM ops.schema_migrations ORDER BY id').splitlines() != m['migrations']:
        raise ValueError('migrations changed')
    if not apply:
        return {'status': 'dry_run_verified', 'target': str(target)}
    try:
        run('systemctl', 'stop', UNITS[0])
        deadline = time.monotonic() + 60
        while active_jobs():
            if time.monotonic() >= deadline:
                raise RuntimeError('jobs did not drain')
            time.sleep(1)
        run('systemctl', 'stop', UNITS[1])
        switch(target)
        for unit in UNITS:
            run('systemctl', 'start', unit)
        deadline = time.monotonic() + 45
        while not ready():
            if time.monotonic() >= deadline:
                raise RuntimeError('readiness failed')
            time.sleep(1)
        if any(run('systemctl', 'is-active', unit) != 'active' for unit in UNITS):
            raise RuntimeError('service did not remain active')
        if hashes(target) != expected or str(WEB.resolve()) != m['previousWeb']:
            raise RuntimeError('post-switch identity differs')
        return {'status': 'published', 'patchCommit': m['patchCommit'], 'codeRoot': str(target),
                'rollbackCode': m['previousCode'], 'webUnchanged': m['previousWeb'], 'databaseChanged': False}
    except Exception:
        errors = []
        for action in [lambda: switch(m['previousCode'])] + [lambda u=u: run('systemctl', 'restart', u) for u in UNITS]:
            try:
                action()
            except Exception as error:
                errors.append(type(error).__name__)
        deadline = time.monotonic() + 45
        while not ready() and time.monotonic() < deadline:
            time.sleep(1)
        if not ready():
            errors.append('readiness')
        for unit in UNITS:
            try:
                if run('systemctl', 'is-active', unit) != 'active':
                    errors.append(unit)
            except Exception:
                errors.append(unit)
        if errors:
            raise RuntimeError('rollback needs attention: ' + ','.join(errors)) from None
        raise


if __name__ == '__main__':
    manifest = Path(sys.argv[1]); payload = Path(sys.argv[2]); sha = sys.argv[3]
    if os.geteuid() != 0 or hashlib.sha256(manifest.read_bytes()).hexdigest() != sha:
        raise SystemExit('manifest identity or admin check failed')
    m = json.loads(manifest.read_text())
    import re
    if not re.fullmatch(r'[0-9a-f]{40}', m['patchCommit']):
        raise SystemExit('invalid patch identity')
    target = Path('/opt/chickenbro-releases') / ('wcl-' + m['patchCommit'])
    expected = stage(m, payload, target)
    print(json.dumps(promote(m, target, expected, '--apply' in sys.argv)))

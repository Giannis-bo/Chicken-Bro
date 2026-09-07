"""Commit-bound production promotion; retain old roots/config, never change data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import time
import urllib.request

CODE = Path('/opt/chickenbro')
WEB = Path('/var/www/chickenbro-web/current')
UNITS = ('chickenbro-api.service', 'chickenbro-worker.service')
DROPINS = tuple(Path('/etc/systemd/system') / (u + '.d') / '99-brand-release-20260907.conf' for u in UNITS)
CONFIG = '[Service]\nWorkingDirectory=/opt/chickenbro\nEnvironment=PYTHONPATH=/opt/chickenbro\n'

def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE).strip()

def files(root):
    result = {}
    for p in sorted(root.rglob('*')):
        if '__pycache__' in p.parts or p.is_symlink():
            continue
        if p.is_file():
            result[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result

def ready():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8790/api/v2/health/readiness', timeout=5) as r:
            return json.load(r).get('status') == 'ready'
    except Exception:
        return False

def active_jobs():
    sql = "SELECT (SELECT count(*) FROM chat.agent_runs WHERE status='streaming') + (SELECT count(*) FROM simc.simulation_jobs WHERE status IN ('queued','running')) + (SELECT count(*) FROM ops.job_queue WHERE status IN ('queued','running'));"
    return int(run('sudo', '-u', 'postgres', 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-At', '-d', 'chickenbro_prod', '-c', sql))

def switch(link, target):
    pending = link.with_name(link.name + '.brand-next')
    if pending.exists() or pending.is_symlink():
        raise ValueError('unfinished link switch')
    if link.is_symlink() and link.resolve() == Path(target).resolve():
        return
    pending.symlink_to(target)
    try:
        pending.replace(link)
    finally:
        if pending.is_symlink():
            pending.unlink()

def validate(manifest, root):
    if not re.fullmatch('[a-f0-9]{40}', manifest['commit']):
        raise ValueError('invalid commit')
    if root != Path('/opt/chickenbro-releases') / manifest['commit'] or root.is_symlink():
        raise ValueError('unexpected release root')
    if set(manifest['modes']) != set(manifest['files']) or any(m not in (0o644, 0o755) for m in manifest['modes'].values()):
        raise ValueError('invalid file modes')
    if any((root / name).stat().st_mode & 0o7777 != mode for name, mode in manifest['modes'].items()):
        raise ValueError('release file modes differ')
    if files(root) != manifest['files']:
        raise ValueError('release file hashes differ')
    if (root / 'BRANCH_COMMIT').read_text().strip() != manifest['commit']:
        raise ValueError('commit marker differs')
    if json.loads((root / 'weapp/wow-build.json').read_text())['gitHead'] != manifest['commit']:
        raise ValueError('Mini build identity differs')
    links = {str(p.relative_to(root / 'web')): str(p.resolve()) for p in (root / 'web').rglob('*') if p.is_symlink()}
    if links != manifest['previewLinks']:
        raise ValueError('preview links differ')

def stage(manifest, archive, root):
    if root.exists() or root.is_symlink():
        validate(manifest, root)
        return
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest['archiveSha256']:
        raise ValueError('archive identity differs')
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        if len({m.name for m in members}) != len(members):
            raise ValueError('duplicate archive member')
        if {m.name for m in members} != set(manifest['files']):
            raise ValueError('archive file list differs')
        if any(not m.isfile() or Path(m.name).is_absolute() or '..' in Path(m.name).parts for m in members):
            raise ValueError('unsafe archive member')
        root.mkdir(mode=0o755)
        for m in members:
            dest = root / m.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open('xb') as out:
                out.write(tar.extractfile(m).read())
            mode = manifest['modes'][m.name]
            if mode not in (0o644, 0o755):
                raise ValueError('unsafe file mode')
            dest.chmod(mode)
    for relative, target in manifest['previewLinks'].items():
        if not relative.startswith('previews/') or '..' in Path(relative).parts:
            raise ValueError('unexpected preview path')
        link = root / 'web' / relative
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
    validate(manifest, root)

def promote(manifest, root, apply):
    validate(manifest, root)
    for link, key in ((CODE, 'previousCode'), (WEB, 'previousWeb')):
        if not link.is_symlink() or str(link.resolve()) != manifest[key]:
            raise ValueError('production pointer moved')
    if any(p.exists() or p.is_symlink() for p in DROPINS):
        raise ValueError('release override already exists')
    if any(p.with_name(p.name + '.brand-next').exists() or p.with_name(p.name + '.brand-next').is_symlink() for p in (CODE, WEB)):
        raise ValueError('unfinished link switch')
    if not ready() or active_jobs():
        raise ValueError('production must be ready and idle')
    if run('sudo', '-u', 'postgres', 'psql', '-X', '-At', '-d', 'chickenbro_prod', '-c', 'SELECT id FROM ops.schema_migrations ORDER BY id').splitlines() != manifest['migrations']:
        raise ValueError('migration state changed')
    if not apply:
        return {'status': 'dry_run', 'commit': manifest['commit'], 'payloadHashesVerified': True}
    created = []
    try:
        run('systemctl', 'stop', UNITS[0])
        deadline = time.monotonic() + 540
        while active_jobs():
            if time.monotonic() >= deadline:
                raise ValueError('work did not drain')
            time.sleep(2)
        run('systemctl', 'stop', UNITS[1])
        for p in DROPINS:
            p.parent.mkdir(exist_ok=True)
            with p.open('x') as f:
                created.append(p)
                f.write(CONFIG)
            p.chmod(0o644)
        switch(CODE, root)
        switch(WEB, root / 'web')
        run('systemctl', 'daemon-reload')
        run('systemctl', 'start', *UNITS)
        for _ in range(30):
            if ready():
                break
            time.sleep(2)
        else:
            raise ValueError('readiness failed')
        for u in UNITS:
            if run('systemctl', 'is-active', u) != 'active' or run('systemctl', 'show', u, '--property=WorkingDirectory', '--value') != str(CODE):
                raise ValueError('effective runtime differs')
        validate(manifest, root)
        return {'status': 'published', 'commit': manifest['commit'], 'codeRoot': str(root), 'webRoot': str(root / 'web'), 'rollbackCode': manifest['previousCode'], 'rollbackWeb': manifest['previousWeb'], 'preservedAvatarOverride': True, 'newDropins': [str(p) for p in DROPINS]}
    except Exception as original:
        failures = []
        recovery = [
            ('code pointer', lambda: switch(CODE, manifest['previousCode'])),
            ('web pointer', lambda: switch(WEB, manifest['previousWeb'])),
        ]
        recovery.extend((str(p), lambda p=p: p.unlink(missing_ok=True)) for p in created)
        recovery.append(('daemon reload', lambda: run('systemctl', 'daemon-reload')))
        recovery.extend((u, lambda u=u: run('systemctl', 'restart', u)) for u in UNITS)
        for label, action in recovery:
            try:
                action()
            except Exception as failure:
                failures.append(label + ': ' + type(failure).__name__)
        if failures:
            raise RuntimeError('rollback needs attention: ' + '; '.join(failures)) from original
        raise

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha', required=True)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    raw = args.manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.manifest_sha or os.geteuid() != 0:
        raise SystemExit('manifest mismatch or administrator required')
    manifest = json.loads(raw)
    if not re.fullmatch('[a-f0-9]{40}', manifest['commit']):
        raise SystemExit('invalid commit')
    root = Path('/opt/chickenbro-releases') / manifest['commit']
    try:
        if args.archive:
            stage(manifest, args.archive, root)
        print(json.dumps(promote(manifest, root, args.apply)))
    except Exception as error:
        raise SystemExit('release failed: ' + type(error).__name__ + ': ' + str(error)) from None

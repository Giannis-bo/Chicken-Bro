"""Exact-target code/Web promotion. Keeps production DB and old code for rollback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request

RELEASES = Path('/opt/chickenbro-releases')
CODE = Path('/opt/chickenbro')
WEB = Path('/var/www/chickenbro-web/current')
UNITS = ('chickenbro-api.service', 'chickenbro-worker.service')
CONF = Path('/etc/chickenbro-release-20260907.env')
DROPINS = [Path('/etc/systemd/system') / (u + '.d') / '90-release-20260907.conf' for u in UNITS]
SETTINGS = ('WOW_SIMC_COMPILER_REVISION=chickenbro-simc-compiler-v3\n'
            'WOW_SIMC_SUPPORTED_SPECS=shaman:elemental,shaman:enhancement\n'
            'WOW_TEST_LOGIN_ENABLED=0\n')


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE).strip()


def inventory(root):
    result = {}
    for file in sorted(root.rglob('*')):
        if '__pycache__' in file.parts:
            continue
        if file.is_symlink():
            raise ValueError('unexpected symlink in code or build')
        if file.is_file():
            result[str(file.relative_to(root))] = hashlib.sha256(file.read_bytes()).hexdigest()
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_payload(manifest, payload):
    if not re.fullmatch('[a-f0-9]{40}', manifest['commit']):
        raise ValueError('invalid commit')
    actual = inventory(payload)
    if actual != manifest['files']:
        raise ValueError('payload file identity mismatch')
    for entry in ('server/app/main.py', 'server/app/worker/main.py', 'web/index.html', 'weapp/app.json'):
        if entry not in actual:
            raise ValueError('missing release entry')
    if (payload / 'BRANCH_COMMIT').read_text().strip() != manifest['commit']:
        raise ValueError('commit marker mismatch')
    if json.loads((payload / 'weapp/wow-build.json').read_text())['gitHead'] != manifest['commit']:
        raise ValueError('Mini build commit mismatch')


def active_jobs():
    sql = "SELECT (SELECT count(*) FROM chat.agent_runs WHERE status='streaming') + (SELECT count(*) FROM simc.simulation_jobs WHERE status IN ('queued','running')) + (SELECT count(*) FROM ops.job_queue WHERE status IN ('queued','running'));"
    return int(run('sudo', '-u', 'postgres', 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-At', '-d', 'chickenbro_prod', '-c', sql))


def ready():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8790/api/v2/health/readiness', timeout=5) as response:
            data = json.load(response)
        return data.get('status') == 'ready'
    except Exception:
        return False


def switch_link(path, target):
    pending = path.with_name(path.name + '.release-next')
    if pending.exists() or pending.is_symlink():
        raise ValueError('unfinished switch')
    pending.symlink_to(target)
    try:
        pending.replace(path)
    finally:
        if pending.is_symlink() and os.readlink(pending) == str(target):
            pending.unlink()


def rollback(old_code, old_web):
    try:
        if CODE.is_symlink():
            CODE.unlink()
        if not CODE.exists() and old_code.is_dir():
            old_code.rename(CODE)
        if not WEB.is_symlink() or WEB.resolve() != Path(old_web):
            switch_link(WEB, old_web)
    finally:
        for file in [CONF, *DROPINS]:
            if file.exists():
                file.unlink()
        run('systemctl', 'daemon-reload')
        run('systemctl', 'restart', *UNITS)


def promote(manifest, payload, apply=False):
    validate_payload(manifest, payload)
    commit = manifest['commit']
    expected_release = RELEASES / commit
    old_code = CODE.with_name('chickenbro-before-' + commit)
    if payload != expected_release or payload.is_symlink():
        raise ValueError('unexpected staged directory')
    if CODE.is_symlink() or not CODE.is_dir() or old_code.exists():
        raise ValueError('unexpected production code or rollback path')
    if not WEB.is_symlink() or str(WEB.resolve()) != manifest['previousWeb']:
        raise ValueError('production Web moved')
    if digest(inventory(CODE)) != manifest['previousCodeHash']:
        raise ValueError('production code changed since review')
    if any(p.exists() or p.is_symlink() for p in [CONF, *DROPINS]):
        raise ValueError('release config already exists')
    pending = WEB.with_name(WEB.name + '.release-next')
    if pending.exists() or pending.is_symlink():
        raise ValueError('unfinished Web switch requires inspection')
    if active_jobs():
        raise ValueError('active production work; retry after drain')
    if not ready():
        raise ValueError('production is not ready before release')
    if not apply:
        return {'status': 'dry_run', 'commit': commit, 'rollbackCode': str(old_code), 'rollbackWeb': manifest['previousWeb']}
    if os.geteuid() != 0:
        raise ValueError('administrator required')
    before = inventory(CODE)
    try:
        CONF.write_text(SETTINGS)
        CONF.chmod(0o600)
        for file in DROPINS:
            file.parent.mkdir(exist_ok=True)
            file.write_text('[Service]\nEnvironmentFile=' + str(CONF) + '\nTimeoutStopSec=540\n')
        run('systemctl', 'daemon-reload')
        run('systemctl', 'stop', UNITS[0])
        # API is drained first; the worker can finish any job accepted during stop.
        deadline = time.monotonic() + 540
        while active_jobs():
            if time.monotonic() > deadline:
                raise ValueError('work did not drain')
            time.sleep(2)
        run('systemctl', 'stop', UNITS[1])
        CODE.rename(old_code)
        if inventory(old_code) != before:
            raise ValueError('rollback copy verification failed')
        CODE.symlink_to(payload)
        switch_link(WEB, payload / 'web')
        run('systemctl', 'start', *UNITS)
        for _ in range(30):
            if ready():
                break
            time.sleep(2)
        else:
            raise ValueError('release readiness failed')
        if inventory(payload) != manifest['files']:
            raise ValueError('deployed files changed')
        return {'status': 'code_web_promoted', 'commit': commit, 'rollbackCode': str(old_code),
                'rollbackWeb': manifest['previousWeb'], 'rollbackCodeHash': digest(before),
                'database': 'chickenbro_prod', 'businessSmoke': 'pending', 'wechatPublication': 'not_run'}
    except Exception:
        rollback(old_code, manifest['previousWeb'])
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    raw = args.manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.manifest_sha:
        raise SystemExit('manifest hash mismatch')
    data = json.loads(raw)
    try:
        result = promote(data, Path('/opt/chickenbro-releases') / data['commit'], args.apply)
    except Exception as error:
        raise SystemExit('release failed: ' + type(error).__name__ + '; inspect without printing credentials') from None
    print(json.dumps(result))

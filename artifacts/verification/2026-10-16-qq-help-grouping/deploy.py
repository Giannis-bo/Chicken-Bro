"""Apply the two help-grouping files to the existing isolated QQ Candidate."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from datetime import datetime, timezone

ROOT = Path('/opt/chickenbro-qq-official-candidate-20261014')
STAGING = Path('/opt/chickenbro-qq-official-query-staging-20261014')
MANIFEST = Path('/tmp/qq-help-grouping-runtime-20261016.json')
RECEIPT = Path('/var/lib/chickenbro/qq-official/help-grouping-deployment-20261016.json')
HEALTH = Path('/var/lib/chickenbro/qq-official/channel-health.json')
SERVICE = 'chickenbro-qq-official.service'
OTHER = ['chickenbro-api.service', 'chickenbro-worker.service', 'chickenbro-qq-official-worker.service']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    return subprocess.check_output(args, text=True).strip()


def pids():
    return {s: run(['systemctl', 'show', s, '-p', 'MainPID', '--value']) for s in OTHER}


def idle():
    sql = "SELECT (SELECT count(*) FROM qq_channel.inbox WHERE state IN ('pending','running')) + (SELECT count(*) FROM qq_channel.outbox WHERE state IN ('pending','sending'))"
    return run(['runuser', '-u', 'postgres', '--', 'psql', '-d', 'chickenbro_qq_official_candidate', '-Atc', sql]) == '0'


def replace(source, dest, stat):
    temp = dest.with_suffix('.help-grouping-tmp')
    shutil.copy2(source, temp)
    os.chown(temp, stat.st_uid, stat.st_gid)
    os.chmod(temp, stat.st_mode & 0o777)
    os.replace(temp, dest)


if __name__ == '__main__':
    manifest = json.loads(MANIFEST.read_text())
    files = manifest['files']
    changed = [f for f in files if f['changed']]
    assert len(files) == 26
    assert {f['path'] for f in changed} == {
        'server/app/channels/qq_official/query_commands.py',
        'server/app/channels/qq_official/battle_commands.py'}
    assert run(['systemctl', 'show', SERVICE, '-p', 'WorkingDirectory', '--value']) == str(ROOT)
    for f in files:
        assert sha(ROOT / f['path']) == f['previousSha256'], f['path'] + ' Candidate drift'
        assert sha(STAGING / f['path']) == f['sha256'], f['path'] + ' staging drift'
    web = Path('/opt/chickenbro/server/app/chickenbro/wcl_source.py')
    web_before = sha(web)
    before = pids()
    assert all(before[s] != '0' and run(['systemctl', 'is-active', s]) == 'active' for s in OTHER)
    assert run(['systemctl', 'is-active', SERVICE]) == 'active'
    config_path = Path('/etc/chickenbro-qq-official/channel.json')
    config_before = sha(config_path)
    config = json.loads(config_path.read_text())
    assert config['enabled'] and config['testGroupNumber'] == '1127827451'
    assert len(config['allowedGroupOpenIds']) == 1
    assert idle(), 'Candidate has active queries or sends'
    backup = Path('/etc/chickenbro-qq-official/help-grouping-backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700)
    stats = {}
    for f in changed:
        name = f['path']
        stats[name] = (ROOT / name).stat()
        dest = backup / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, dest)
        assert sha(dest) == f['previousSha256']
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    subprocess.check_call(['systemctl', 'stop', SERVICE])
    try:
        assert idle(), 'queue changed before stop'
        for f in files:
            assert sha(ROOT / f['path']) == f['previousSha256'], f['path'] + ' concurrent drift'
        for f in changed:
            replace(STAGING / f['path'], ROOT / f['path'], stats[f['path']])
        for f in files:
            assert sha(ROOT / f['path']) == f['sha256']
        started = time.time()
        subprocess.check_call(['systemctl', 'start', SERVICE])
        for _ in range(45):
            health = json.loads(HEALTH.read_text())
            if health.get('observedAt', 0) > started and health.get('gatewayReady'):
                break
            time.sleep(1)
        else:
            raise RuntimeError('fresh gateway readiness not confirmed')
        assert health['queryOnly'] and health['allowedGroupCount'] == 1
        assert health['battlePresentation'] == 'single_summary_evidence_narrative_zhcn_v8'
        assert pids() == before
        assert sha(web) == web_before and sha(config_path) == config_before
        receipt = {'runtimeFilesMatched': len(files), 'changedFiles': len(changed),
                   'gatewayReady': True, 'queryOnly': True, 'allowedGroupCount': 1,
                   'battlePresentation': health['battlePresentation'], 'unchangedServicePids': before,
                   'webSourceSha256Unchanged': web_before, 'configSha256Unchanged': config_before,
                   'rollbackDirectory': str(backup), 'rollbackDrill': False,
                   'databaseSchemaChanged': False, 'credentialsChanged': False,
                   'qqValidationMessagesSent': 0, 'sourceDelivery': manifest['sourceDelivery']}
        RECEIPT.write_text(json.dumps(receipt, indent=2))
        print(json.dumps(receipt), flush=True)
    except Exception:
        subprocess.check_call(['systemctl', 'stop', SERVICE])
        for f in changed:
            replace(backup / f['path'], ROOT / f['path'], stats[f['path']])
        subprocess.check_call(['systemctl', 'start', SERVICE])
        raise

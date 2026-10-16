"""Run as root on the existing official QQ Candidate only. No Git operations."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tarfile
import time
from uuid import uuid4

ROOT = Path('/opt/chickenbro-qq-official-candidate-20261014')
STATE = Path('/var/lib/chickenbro/qq-official')
CONFIG = Path('/etc/chickenbro-qq-official')
SERVICE = 'chickenbro-qq-official.service'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pid(service):
    return int(subprocess.check_output(['systemctl','show',service,'-p','MainPID','--value'],text=True).strip())


def main():
    if os.geteuid() != 0 or not ROOT.is_dir(): raise SystemExit('dedicated Candidate root required')
    from server.app.channels.qq_official.policy import require_test_group
    from server.app.channels.qq_official.deployment import character_query_credentials
    channel = json.loads((CONFIG/'channel.json').read_text())
    require_test_group(channel)
    manifest = json.loads((STATE/'query-source-manifest.json').read_text())
    assert manifest['runtimeDirectory'] == str(ROOT) and manifest['testGroupNumber'] == '1127827451'
    expected = {x['path']:x['sha256'] for x in manifest['files']}
    assert all(p.startswith('server/app/channels/qq_official/') or p in
               ('server/qq-official/001_transport.sql','server/qq-official/002_queries.sql') for p in expected)
    active = subprocess.check_output(['sudo','-u','postgres','psql','-d','chickenbro_qq_official_candidate','-Atc',
        "SELECT count(*) FROM qq_channel.inbox WHERE state IN ('pending','running')"],text=True).strip()
    if active != '0': raise SystemExit('Candidate has active inbox jobs; drain before deployment')
    baseline = {s:pid(s) for s in ('chickenbro-api.service','chickenbro-worker.service',
                                  'chickenbro-qq-official-worker.service')}
    assert baseline['chickenbro-api.service'] > 0 and baseline['chickenbro-worker.service'] > 0
    api_env = dict(s.split('=',1) for s in Path(f'/proc/{baseline["chickenbro-api.service"]}/environ').read_text().split('\0') if '=' in s)
    source_env = character_query_credentials(api_env)
    assert source_env.get('WOW_WARCRAFTLOGS_CLIENT_ID') and source_env.get('WOW_WARCRAFTLOGS_CLIENT_SECRET')
    backup = CONFIG / ('query-backup-' + time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()))
    backup.mkdir(mode=0o700)
    before = {}
    for name in expected:
        path = ROOT/name
        assert path.resolve().is_relative_to(ROOT)
        if path.exists():
            target = backup/'source'/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target); before[name]=digest(path)
            assert digest(target) == before[name]
    env_path = CONFIG/'runtime.env'
    shutil.copy2(env_path,backup/'runtime.env')
    assert digest(env_path) == digest(backup/'runtime.env')
    (backup/'manifest.json').write_text(json.dumps({'files':before,'runtimeEnvSha256':digest(env_path)},indent=2))
    subprocess.run(['systemctl','stop',SERVICE],check=True)
    account = pwd.getpwnam('ubuntu')
    try:
        with tarfile.open(STATE/'qq-character-query-20261014.tar') as archive:
            members = archive.getmembers()
            assert {m.name for m in members} == set(expected) and all(m.isfile() for m in members)
            for member in members:
                content = archive.extractfile(member).read()
                assert hashlib.sha256(content).hexdigest() == expected[member.name]
                target = ROOT/member.name;target.parent.mkdir(parents=True,exist_ok=True)
                temp = target.with_name(target.name+'.'+uuid4().hex+'.tmp')
                temp.write_bytes(content);os.chmod(temp,0o644);os.chown(temp,account.pw_uid,account.pw_gid)
                temp.replace(target)
        lines = [line for line in env_path.read_text().splitlines() if line.split('=',1)[0] not in source_env]
        lines.extend(k+'='+json.dumps(v) for k,v in source_env.items())
        temp = CONFIG/('runtime.'+uuid4().hex+'.tmp')
        temp.write_text('\n'.join(lines)+'\n');os.chmod(temp,0o600);temp.replace(env_path)
        subprocess.run(['sudo','-u','postgres','psql','-v','ON_ERROR_STOP=1','-d',
                        'chickenbro_qq_official_candidate','-f',str(ROOT/'server/qq-official/002_queries.sql')],check=True)
        for name,sha in expected.items(): assert digest(ROOT/name) == sha
        started = time.time()
        subprocess.run(['systemctl','start',SERVICE],check=True)
        health = {}
        for _ in range(30):
            health_path=STATE/'channel-health.json'
            if health_path.exists():
                health=json.loads(health_path.read_text())
                if health.get('observedAt',0) >= started and health.get('gatewayReady') and health.get('queryOnly'): break
            time.sleep(1)
        assert health.get('gatewayReady') and health.get('queryOnly') and health.get('allowedGroupCount') == 1
        after = {s:pid(s) for s in baseline}
        assert baseline == after
        result = {'scope':'official_qq_query_candidate_only','sourceFilesMatched':len(expected),
                  'gatewayReady':True,'queryOnly':True,'allowedGroupCount':1,'testGroupNumber':'1127827451',
                  'officialChannelPid':pid(SERVICE),'unchangedServicePids':after,'rollbackDirectory':str(backup),
                  'credentialKeysAdded':sorted(source_env),'manualGroupAcceptance':'pending'}
        (STATE/'query-deployment-result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
    except Exception:
        # Preserve source, data and exact backup; stop the entry if delivery verification fails.
        subprocess.run(['systemctl','stop',SERVICE],check=False)
        raise


if __name__ == '__main__': main()

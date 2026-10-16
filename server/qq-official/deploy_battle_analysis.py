"""Exact additive update of the existing official Candidate; no Git operations."""
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

ROOT=Path('/opt/chickenbro-qq-official-candidate-20261014')
STATE=Path('/var/lib/chickenbro/qq-official')
CONFIG=Path('/etc/chickenbro-qq-official')
SERVICE='chickenbro-qq-official.service'
DB='chickenbro_qq_official_candidate'
CHANGED={f'server/app/channels/qq_official/{n}.py' for n in
         ('battle_commands','battle_source','battle_analysis','query_commands','query_service','query_repository','runtime')}
CHANGED.add('server/qq-official/003_battles.sql')


def sha(data):return hashlib.sha256(data).hexdigest()


def pids():
    return {s:subprocess.check_output(['systemctl','show',s,'-p','MainPID','--value'],text=True).strip()
            for s in ('chickenbro-api.service','chickenbro-worker.service','chickenbro-qq-official-worker.service')}


def busy():
    sql="SELECT (SELECT count(*) FROM qq_channel.inbox WHERE state IN ('pending','running'))+(SELECT count(*) FROM qq_channel.outbox WHERE state IN ('pending','sending'))"
    return subprocess.check_output(['sudo','-u','postgres','psql','-d',DB,'-Atc',sql],text=True).strip()!='0'


def replace(name,data,owner):
    path=ROOT/name;path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid4().hex+'.tmp')
    temp.write_bytes(data);os.chmod(temp,0o644);os.chown(temp,*owner);temp.replace(path)


def main():
    assert os.geteuid()==0 and ROOT.is_dir()
    from server.app.channels.qq_official.policy import require_test_group
    channel=json.loads((CONFIG/'channel.json').read_text());require_test_group(channel)
    manifest=json.loads((STATE/'battle-manifest-20261015.json').read_text())
    assert manifest['runtimeDirectory']==str(ROOT) and manifest['testGroupNumber']=='1127827451'
    assert manifest['cloudTestsPassed']>=175
    records={r['path']:r for r in manifest['files']}
    changes={p:r for p,r in records.items() if r.get('changed')}
    assert set(changes)==CHANGED
    for name,r in records.items():
        path=ROOT/name
        assert path.resolve().is_relative_to(ROOT)
        if r.get('previousSha256') is not None:
            assert path.is_file() and sha(path.read_bytes())==r['previousSha256'],name
        else:assert not path.exists(),name
    contents={}
    with tarfile.open(STATE/'battle-source-20261015.tar') as archive:
        members=archive.getmembers()
        assert len(members)==len(CHANGED) and {m.name for m in members}==CHANGED and all(m.isfile() for m in members)
        for m in members:
            data=archive.extractfile(m).read();assert sha(data)==changes[m.name]['sha256']
            if m.name.endswith('.py'):compile(data,m.name,'exec')
            contents[m.name]=data
    if busy():raise SystemExit('Candidate has active work; drain before update')
    before=pids();assert all(int(v)>0 for v in before.values())
    config_hashes={p.name:sha(p.read_bytes()) for p in (CONFIG/'runtime.env',CONFIG/'channel.json',CONFIG/'credentials.json')}
    backup=CONFIG/('battle-backup-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()))
    backup.mkdir(mode=0o700)
    for name,r in changes.items():
        if r.get('previousSha256') is not None:
            dest=backup/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/name,dest);assert sha(dest.read_bytes())==r['previousSha256']
    (backup/'manifest.json').write_text(json.dumps(manifest,indent=2))
    account=pwd.getpwnam('ubuntu');owner=(account.pw_uid,account.pw_gid)
    subprocess.run(['systemctl','stop',SERVICE],check=True)
    try:
        if busy():raise RuntimeError('Message arrived while stopping; keep previous source and drain')
        for name,data in contents.items():replace(name,data,owner)
        subprocess.run(['sudo','-u','postgres','psql','-v','ON_ERROR_STOP=1','-d',DB,
                        '-f',str(ROOT/'server/qq-official/003_battles.sql')],check=True,capture_output=True)
        assert all(sha((ROOT/name).read_bytes())==r['sha256'] for name,r in records.items())
        started=time.time();subprocess.run(['systemctl','start',SERVICE],check=True)
        for _ in range(40):
            health=json.loads((STATE/'channel-health.json').read_text())
            if (health.get('observedAt',0)>=started and health.get('gatewayReady') and
                health.get('battlePresentation')=='single_summary_evidence_v1'):break
            time.sleep(1)
        else:raise RuntimeError('Updated gateway did not become ready')
        assert health['queryOnly'] and health['allowedGroupCount']==1
        assert pids()==before
        assert config_hashes=={p.name:sha(p.read_bytes()) for p in (CONFIG/'runtime.env',CONFIG/'channel.json',CONFIG/'credentials.json')}
        result={'runtimeFilesMatched':len(records),'changedFiles':len(changes),'gatewayReady':True,
                'allowedGroupCount':1,'queryOnly':True,'battlePresentation':health['battlePresentation'],
                'cloudTestsPassed':manifest['cloudTestsPassed'],'unchangedServicePids':before,
                'configAndCredentialsUnchanged':True,'databaseChange':'additive_result_packet_column_only',
                'rollbackDirectory':str(backup),'rollbackDrill':False,'manualGroupAcceptance':'pending',
                'sourceDelivery':'uncommitted_not_pushed_not_integrated'}
        (STATE/'battle-deployment-20261015.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
    except Exception:
        subprocess.run(['systemctl','stop',SERVICE],check=False)
        for name,r in changes.items():
            if r.get('previousSha256') is not None:replace(name,(backup/name).read_bytes(),owner)
        # Added modules and the nullable column remain recoverable and unused
        # by previous code. No data, evidence, or new files are removed.
        subprocess.run(['systemctl','start',SERVICE],check=True)
        raise


if __name__=='__main__':main()

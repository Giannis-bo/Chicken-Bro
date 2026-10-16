"""Apply the five verified presentation files to the existing QQ Candidate."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time
from uuid import uuid4

ROOT=Path('/opt/chickenbro-qq-official-candidate-20261014')
STATE=Path('/var/lib/chickenbro/qq-official')
CONFIG=Path('/etc/chickenbro-qq-official')
SERVICE='chickenbro-qq-official.service'
FILES={f'server/app/channels/qq_official/{name}.py' for name in
       ('character_source','query_commands','client','query_repository','runtime')}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pids():
    return {s:subprocess.check_output(['systemctl','show',s,'-p','MainPID','--value'],text=True).strip()
            for s in ('chickenbro-api.service','chickenbro-worker.service','chickenbro-qq-official-worker.service')}


def apply_file(name,content,stat):
    target=ROOT/name
    temp=target.with_name(target.name+'.'+uuid4().hex+'.tmp')
    temp.write_bytes(content)
    os.chmod(temp,stat.st_mode & 0o777)
    os.chown(temp,stat.st_uid,stat.st_gid)
    temp.replace(target)


def main():
    assert os.geteuid()==0 and ROOT.is_dir()
    from server.app.channels.qq_official.policy import require_test_group
    require_test_group(json.loads((CONFIG/'channel.json').read_text()))
    manifest=json.loads((STATE/'presentation-manifest-20261015.json').read_text())
    assert manifest['testGroupNumber']=='1127827451' and manifest['cloudTestsPassed']==82
    expected={f['path']:f for f in manifest['files']}
    assert set(expected)==FILES
    content={}
    with tarfile.open(STATE/'presentation-20261015.tar') as archive:
        members=archive.getmembers()
        assert len(members)==len(FILES) and {m.name for m in members}==FILES
        assert all(m.isfile() for m in members)
        for member in members:
            data=archive.extractfile(member).read()
            assert digest(data)==expected[member.name]['sha256']
            assert (ROOT/member.name).resolve().is_relative_to(ROOT)
            assert digest((ROOT/member.name).read_bytes())==expected[member.name]['previousSha256']
            compile(data,member.name,'exec')
            content[member.name]=data
    # Check both query drain and provider sends before stopping the only channel.
    sql="SELECT (SELECT count(*) FROM qq_channel.inbox WHERE state IN ('pending','running'))+(SELECT count(*) FROM qq_channel.outbox WHERE state IN ('pending','sending'))"
    busy=subprocess.check_output(['sudo','-u','postgres','psql','-d','chickenbro_qq_official_candidate','-Atc',sql],text=True).strip()
    if busy!='0': raise SystemExit('Candidate has active work; drain before applying')
    before=pids()
    backup=CONFIG/('presentation-backup-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()))
    backup.mkdir(mode=0o700)
    stats={}
    for name in FILES:
        stats[name]=(ROOT/name).stat()
        path=backup/name;path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/name,path)
        assert digest(path.read_bytes())==expected[name]['previousSha256']
    (backup/'manifest.json').write_text(json.dumps(manifest,indent=2))
    subprocess.run(['systemctl','stop',SERVICE],check=True)
    try:
        for name,data in content.items(): apply_file(name,data,stats[name])
        for name in FILES: assert digest((ROOT/name).read_bytes())==expected[name]['sha256']
        started=time.time()
        subprocess.run(['systemctl','start',SERVICE],check=True)
        for _ in range(35):
            health=json.loads((STATE/'channel-health.json').read_text())
            if (health.get('observedAt',0)>=started and health.get('gatewayReady')
                and health.get('queryPresentation')=='markdown_recent5_v1'): break
            time.sleep(1)
        else: raise RuntimeError('new presentation gateway not ready')
        assert health.get('queryOnly') and health.get('allowedGroupCount')==1
        assert pids()==before
        result={'filesMatched':len(FILES),'presentation':health['queryPresentation'],
                'gatewayReady':True,'allowedGroupCount':1,'queryOnly':True,
                'unchangedServicePids':before,'rollbackDirectory':str(backup),
                'cloudTestsPassed':82,'groupPresentationAcceptance':'pending',
                'configDatabaseAndCredentialsChanged':False}
        (STATE/'presentation-deployment-20261015.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result))
    except Exception:
        subprocess.run(['systemctl','stop',SERVICE],check=False)
        for name in FILES: apply_file(name,(backup/name).read_bytes(),stats[name])
        subprocess.run(['systemctl','start',SERVICE],check=True)
        raise


if __name__=='__main__': main()

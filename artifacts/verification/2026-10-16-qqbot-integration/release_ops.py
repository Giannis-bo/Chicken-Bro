"""Cloud root-only, manifest-bound official Candidate maintenance. No QQ sends."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time

LIVE=Path('/opt/chickenbro-qq-official-candidate-20261014')
STAGE=Path('/opt/chickenbro-candidates/qqbot-integration-20261016')
REC=Path('/var/lib/chickenbro-retirement/qqbot-integration-20261016')
DB='chickenbro_qq_official_candidate'
RESTORE='chickenbro_qq_official_restore_20261016'
SERVICES=('chickenbro-qq-official','chickenbro-qq-official-worker')
EVIDENCE=STAGE/'artifacts/verification/2026-10-16-qqbot-integration'

def run(args,**kwargs):return subprocess.run(args,check=True,**kwargs)
def output(args):return subprocess.check_output(args,text=True).strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def psql(db,sql):return output(['sudo','-u','postgres','psql','-XAt','-v','ON_ERROR_STOP=1','-d',db,'-c',sql])
def fingerprint(db):
    tables=psql(db,"SELECT quote_ident(schemaname)||'.'||quote_ident(tablename) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1").splitlines()
    return {t:psql(db,"SELECT count(*)::text||':'||COALESCE(md5(string_agg(row_to_json(t)::text,E'\\n' ORDER BY row_to_json(t)::text)),'empty') FROM "+t+' t') for t in tables}
def quiet():
    assert psql(DB,"SELECT count(*) FROM qq_channel.inbox WHERE state IN ('pending','running')")=='0','active inbox'
    assert psql(DB,"SELECT count(*) FROM qq_channel.outbox WHERE state IN ('pending','sending')")=='0','active outbox'
def web_identity():
    d=json.loads((STAGE/'artifacts/verification/2026-10-16-simc-characters/release/live/manifest.json').read_text())
    root=Path('/opt/chickenbro').resolve();web=Path('/var/www/chickenbro-web/current').resolve()
    inventory={**d['baseInventory'],**d['files']}
    assert all(sha(root/p)==h for p,h in inventory.items()),'Web backend bytes changed'
    assert all(sha(web/p)==h for p,h in d['newWebFiles'].items()),'Web artifact bytes changed'
    return {'backendPath':str(root),'webPath':str(web),'apiPid':output(['systemctl','show','chickenbro-api','-p','MainPID','--value']),
            'workerPid':output(['systemctl','show','chickenbro-worker','-p','MainPID','--value']),
            'backendFiles':len(inventory),'webFiles':len(d['newWebFiles']),
            'configHashes':{str(p):sha(p) for p in Path('/etc/chickenbro-qq-official').glob('*') if p.is_file()}}
def files(root):return {str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
def prepare():
    assert not REC.exists(),'recovery already exists'
    quiet();before=web_identity();REC.mkdir(mode=0o700,parents=True)
    desired=json.loads((EVIDENCE/'desired-runtime-files.json').read_text())
    wanted={p:h for p,h in desired.items() if p.startswith(('server/app/channels/qq_official/','server/qq-official/')) or p in (
        'server/app/identity/domain.py','server/app/platform/config.py','server/app/chickenbro/worker.py',
        'server/app/chickenbro/durable.py','server/app/chickenbro/worker_gateway.py','server/app/chickenbro/application.py',
        'server/app/chickenbro/codex_adapter.py','server/app/chickenbro/repository.py')}
    cleanup=[p for p in files(LIVE) if p.startswith(('server/app/channels/qq/','server/qq-channel/')) or
             p.startswith('server/migrations/product/') and Path(p).name[:4] in ('0015','0016','0017','0018','0019','0020')]
    old=files(LIVE)
    manifest={'target':str(LIVE),'files':wanted,'before':old,'quarantine':cleanup,'webBefore':before}
    (REC/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    with tarfile.open(REC/'runtime.tar.gz','w:gz') as t:t.add(LIVE,arcname='runtime')
    with tarfile.open(REC/'runtime.tar.gz') as t:t.extractall(REC/'independent-restore',filter='data')
    assert files(REC/'independent-restore/runtime')==old,'file recovery mismatch'
    with (REC/'database.dump').open('wb') as f:run(['sudo','-u','postgres','pg_dump','-Fc',DB],stdout=f)
    assert psql('postgres',"SELECT count(*) FROM pg_database WHERE datname='"+RESTORE+"'")=='0'
    run(['sudo','-u','postgres','createdb',RESTORE])
    with (REC/'database.dump').open('rb') as f:run(['sudo','-u','postgres','pg_restore','--exit-on-error','-d',RESTORE],stdin=f,stdout=subprocess.DEVNULL)
    fingerprints=fingerprint(DB);assert fingerprints==fingerprint(RESTORE),'DB recovery mismatch'
    (REC/'database-fingerprints.json').write_text(json.dumps(fingerprints,indent=2)+'\n')
    result={'fileRestoreVerified':len(old),'databaseRestoreVerified':len(fingerprints),'runtimeFiles':len(wanted),
            'quarantineFiles':len(cleanup),'recoveryPath':str(REC),'restoreDatabase':RESTORE,
            'archiveSha256':sha(REC/'runtime.tar.gz'),'databaseDumpSha256':sha(REC/'database.dump'),'webBefore':before}
    (EVIDENCE/'recovery.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
def apply():
    m=json.loads((REC/'manifest.json').read_text());assert web_identity()==m['webBefore'];quiet()
    assert files(LIVE)==m['before'],'runtime changed since recovery'
    assert all(sha(STAGE/p)==h for p,h in m['files'].items()),'staging source changed'
    old_pids={svc:output(['systemctl','show',svc,'-p','MainPID','--value']) for svc in SERVICES}
    try:
        for svc in SERVICES:run(['systemctl','stop',svc])
        quiet()
        assert fingerprint(DB)==json.loads((REC/'database-fingerprints.json').read_text()),'DB changed since recovery'
        assert psql('postgres',"SELECT count(*) FROM pg_stat_activity WHERE datname='"+DB+"'")=='0','live DB connections'
        for p in m['files']:
            target=LIVE/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(STAGE/p,target)
        for p in m['quarantine']:
            dest=REC/'retired-source'/p;dest.parent.mkdir(parents=True,exist_ok=True);shutil.move(LIVE/p,dest)
        # Remove only empty retired directories; all bytes remain in verified recovery.
        for prefix in ('server/app/channels/qq','server/qq-channel'):
            root=LIVE/prefix
            if root.exists():
                for d in sorted(root.rglob('*'),key=lambda p:len(p.parts),reverse=True):
                    if d.is_dir():d.rmdir()
                root.rmdir()
        run(['sudo','-u','postgres','psql','-X','-v','ON_ERROR_STOP=1','-d',DB,'-f',str(STAGE/'server/qq-official/004_group_revocations.sql')],stdout=subprocess.DEVNULL)
        rollout_started=time.time()
        for svc in reversed(SERVICES):run(['systemctl','start',svc])
        health=None
        for _ in range(25):
            time.sleep(1)
            health=json.loads(Path('/var/lib/chickenbro/qq-official/channel-health.json').read_text())
            if health.get('gatewayReady') and rollout_started<=health['observedAt'] and time.time()-health['observedAt']<15:break
        assert health['gatewayReady'] and rollout_started<=health['observedAt'] and time.time()-health['observedAt']<15,'gateway not ready'
        assert health['allowedGroupCount']==1 and health['queryOnly'] is True and health['guidanceToolAccess'] is False
        assert all(output(['systemctl','is-active',svc])=='active' for svc in SERVICES)
        assert all(output(['systemctl','show',svc,'-p','MainPID','--value']) not in ('0',old_pids[svc]) for svc in SERVICES),'PID did not change'
        assert all(sha(LIVE/p)==h for p,h in m['files'].items())
        assert web_identity()==m['webBefore'],'Web changed'
        result={'runtimeFilesMatched':len(m['files']),'quarantinedLegacyFiles':len(m['quarantine']),
                'officialPids':{svc:output(['systemctl','show',svc,'-p','MainPID','--value']) for svc in SERVICES},
                'health':health,'webUnchanged':True,'configurationUnchanged':True,'qqMessagesSentByVerification':0,
                'files':m['files']}
        (EVIDENCE/'deployment.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    except BaseException:
        for svc in SERVICES:subprocess.run(['systemctl','stop',svc])
        restored=REC/'independent-restore/runtime'
        candidates=set(m['files'])|set(m['quarantine'])
        candidates.update(p for p in files(LIVE) if '/__pycache__/' in p)
        candidates.update(p for p in m['before'] if '/__pycache__/' in p)
        for p in candidates:
            if (restored/p).is_file():
                (LIVE/p).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(restored/p,LIVE/p)
            elif (LIVE/p).is_file():
                dest=REC/'failed-new-source'/p;dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.move(LIVE/p,dest)
        assert files(LIVE)==m['before'],'rollback source mismatch; services remain stopped'
        for svc in reversed(SERVICES):run(['systemctl','start',svc])
        assert all(output(['systemctl','is-active',svc])=='active' for svc in SERVICES)
        (EVIDENCE/'rollback.json').write_text(json.dumps({'sourceRestoreVerified':True,
            'databaseAdditiveMigrationRetained':True,'databaseRestored':False})+'\n')
        raise
if __name__=='__main__':
    assert os.geteuid()==0
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply']);args=parser.parse_args()
    lock=Path('/var/lock/chickenbro-qqbot-integration.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    {'prepare':prepare,'apply':apply}[args.action]()

"""Apply only the exact QQ Candidate manifest after hashes and queues match."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from datetime import datetime,timezone

ROOT=Path('/opt/chickenbro-qq-official-candidate-20261014')
STAGING=Path('/opt/chickenbro-qq-official-query-staging-20261014')
SERVICE='chickenbro-qq-official.service'
OTHER=['chickenbro-api.service','chickenbro-worker.service','chickenbro-qq-official-worker.service']


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args):return subprocess.check_output(args,text=True).strip()
def pid(service):return run(['systemctl','show',service,'--property=MainPID','--value'])
def idle():
    sql="SELECT (SELECT count(*) FROM qq_channel.inbox WHERE state IN ('pending','running')) + (SELECT count(*) FROM qq_channel.outbox WHERE state IN ('pending','sending'))"
    return run(['runuser','-u','postgres','--','psql','-d','chickenbro_qq_official_candidate','-Atc',sql])=='0'


if __name__=='__main__':
    manifest=json.loads(Path('/tmp/qq-battle-team-report-runtime-20261016.json').read_text())
    files=manifest['files'];changed=[f for f in files if f['changed']]
    assert {f['path'] for f in changed}=={
        'server/app/channels/qq_official/battle_causes.py',
        'server/app/channels/qq_official/battle_analysis.py',
        'server/app/channels/qq_official/battle_report.py',
        'server/app/channels/qq_official/battle_source.py',
        'server/app/channels/qq_official/battle_commands.py',
        'server/app/channels/qq_official/runtime.py'}
    for f in files:
        dest=ROOT/f['path'];previous=f['previousSha256']
        assert (sha(dest)==previous if previous else not dest.exists()),f['path']+' candidate drift'
        assert sha(STAGING/f['path'])==f['sha256'],f['path']+' staging drift'
    web=Path('/opt/chickenbro/server/app/chickenbro/wcl_source.py')
    web_before=sha(web)
    assert web_before=='b525e2fb883108c0fd5d2132381556b543688f7d7f15614ca7d4bfa6e1d783d4'
    before={s:pid(s) for s in OTHER}
    assert run(['systemctl','is-active',SERVICE])=='active'
    assert idle(),'queries or sends active'
    backup=Path('/etc/chickenbro-qq-official/battle-team-report-backup-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700)
    for f in changed:
        old=ROOT/f['path']
        if old.exists():
            dest=backup/f['path'];dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(old,dest)
            assert sha(dest)==f['previousSha256']
    (backup/'manifest.json').write_text(json.dumps(manifest,indent=2))
    subprocess.check_call(['systemctl','stop',SERVICE])
    try:
        assert idle(),'queue changed while draining'
        for f in changed:
            dest=ROOT/f['path'];temp=dest.with_suffix('.depth-tmp')
            shutil.copy2(STAGING/f['path'],temp)
            os.chmod(temp,0o644)
            os.replace(temp,dest)
        for f in files:assert sha(ROOT/f['path'])==f['sha256']
        subprocess.check_call(['systemctl','start',SERVICE])
        ready=None
        for _ in range(45):
            health=json.loads(Path('/var/lib/chickenbro/qq-official/channel-health.json').read_text())
            if (health.get('gatewayReady') and health.get('battlePresentation')=='single_summary_team_report_zhcn_v5'
                    and health.get('observedAt',0)>time.time()-20):
                ready=health;break
            time.sleep(1)
        assert ready,'gateway readiness not confirmed'
        assert ready['queryOnly'] and ready['allowedGroupCount']==1
        after={s:pid(s) for s in OTHER};assert before==after,'unrelated service changed'
        assert run(['systemctl','is-active',SERVICE])=='active'
        assert sha(web)==web_before,'website source changed'
        receipt={'webSourceSha256Unchanged':web_before,'runtimeFilesMatched':len(files),'changedFiles':len(changed),
                 'gatewayReady':True,'queryOnly':True,'allowedGroupCount':1,
                 'battlePresentation':ready['battlePresentation'],'unchangedServicePids':after,
                 'rollbackDirectory':str(backup),'rollbackDrill':False,'databaseChanged':False,
                 'configAndCredentialsChanged':False,'sourceDelivery':'uncommitted_not_pushed_not_integrated'}
        out=Path('/var/lib/chickenbro/qq-official/battle-team-report-deployment-20261016.json')
        out.write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt),flush=True)
    except Exception:
        for f in changed:
            old=backup/f['path']
            if old.exists():shutil.copy2(old,ROOT/f['path'])
        subprocess.check_call(['systemctl','start',SERVICE])
        raise

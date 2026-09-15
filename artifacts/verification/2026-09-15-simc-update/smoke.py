"""Isolated and live HTTP smoke. No new production identities; tokens never printed."""
import argparse,atexit,base64,hashlib,io,json,os,pwd,re,secrets,signal,socket,subprocess,sys,time
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,unquote,parse_qs
from uuid import uuid4
import httpx,psycopg
os.umask(0o077)
from PIL import Image,ImageDraw,ImageFont
p=argparse.ArgumentParser();p.add_argument('mode',choices=['candidate','production']);p.add_argument('source');p.add_argument('--remaining',action='store_true');p.add_argument('--label',required=True);p.add_argument('--before',action='store_true');p.add_argument('--resume-job');a=p.parse_args()
prod_pid=subprocess.check_output(['systemctl','show','chickenbro-api','-p','MainPID','--value'],text=True).strip()
env=dict(v.split('=',1) for v in Path('/proc/'+prod_pid+'/environ').read_text().split('\0') if '=' in v)
assert urlsplit(env['WOW_DATABASE_URL']).path=='/chickenbro_prod'
children=[];tokens=[];report={'phase':'before' if a.before else 'after','mode':a.mode,'source':str(Path(a.source).resolve()),'checks':{}}
if a.mode=='candidate':
    for port in (18890,18794):
        with socket.socket() as s:
            s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',port))
    dsn=urlsplit(env['WOW_DATABASE_URL']);db='chickenbro_badcase_candidate_20260909'
    for line in Path(env['PGPASSFILE']).read_text().splitlines():
        f=[re.sub(r'\\(.)',r'\1',v) for v in re.split(r'(?<!\\):',line)]
        if len(f)==5 and f[2]==dsn.path.lstrip('/') and f[3]==unquote(dsn.username):env['PGPASSWORD']=f[4];break
    assert env.get('PGPASSWORD')
    exists=subprocess.check_output(['sudo','-n','-u','postgres','psql','-XAt','-c',"SELECT count(*) FROM pg_database WHERE datname='"+db+"'"],text=True).strip()
    assert exists=='1','existing isolated database required'
    private=Path('/var/lib/chickenbro-simc-update-candidate-20260915');private.mkdir(mode=0o700,exist_ok=True)
    u=pwd.getpwnam('ubuntu');os.chown(private,u.pw_uid,u.pw_gid)
    env.update(WOW_DATABASE_URL=urlunsplit(dsn._replace(path='/'+db)),WOW_APP_ENV='test',WOW_API_V2_PORT='18890',
        WOW_CHAT_WORKER_TOOL_PORT='18794',WOW_TEST_LOGIN_ENABLED='0',WOW_WORKER_V2_HEARTBEAT_PATH=str(private/'heartbeat.json'),
        WOW_CODEX_JOBS_DIR=str(private/'jobs'),WOW_WEB_COOKIE_NAME='__Host-badcase-session',WOW_WEB_CSRF_COOKIE_NAME='__Host-badcase-csrf',
        WOW_QQ_REDIRECT_URI=env['WOW_WEB_ORIGIN']+'/test/api/v2/auth/qq/callback',PYTHONPATH=a.source,WOW_SIMC_BIN='/opt/wow-simc/candidate-20260915/simc')
    os.environ.update(env);sys.path.insert(0,a.source)
    import importlib
    with psycopg.connect(env['WOW_DATABASE_URL']) as c:
        assert c.execute("SELECT count(*) FROM chat.agent_runs WHERE status='streaming'").fetchone()[0]==0
        assert c.execute("SELECT count(*) FROM ops.job_queue WHERE status IN ('queued','running')").fetchone()[0]==0
else:os.environ.update(env);sys.path.insert(0,a.source)
def cleanup():
    if tokens:
        with psycopg.connect(env['WOW_DATABASE_URL']) as c:
            for t in tokens:c.execute('UPDATE identity.auth_sessions SET revoked_at=now() WHERE token_hash=%s',(hashlib.sha256(t.encode()).hexdigest(),))
    if children:
        for _ in range(30):
            with psycopg.connect(env['WOW_DATABASE_URL']) as c:
                active=c.execute("SELECT (SELECT count(*) FROM chat.agent_runs WHERE status='streaming')+(SELECT count(*) FROM chat.executions WHERE stage IN ('pending','running'))+(SELECT count(*) FROM ops.job_queue WHERE status IN ('queued','running'))").fetchone()[0]
            if not active:break
            time.sleep(1)
        if active:
            print(json.dumps({'cleanup':'active_candidate_left_running_for_safe_completion'}),flush=True);return
    for child in children:
        if child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=15)
            except subprocess.TimeoutExpired:raise RuntimeError('candidate termination timeout; retained for inspection')
atexit.register(lambda target=Path(__file__).parent/(a.label+'-private.json'),data=report:target.write_text(json.dumps(data,ensure_ascii=False,indent=2)))
atexit.register(cleanup)
import fcntl
lock=open('/run/lock/chickenbro-candidate-validation.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB) if a.mode=='candidate' else None
with psycopg.connect(env['WOW_DATABASE_URL']) as c:
    if a.mode=='candidate':
        owners=[r[0] for r in c.execute("SELECT DISTINCT j.user_id FROM simc.simulation_jobs j JOIN identity.user_identities i ON i.user_id=j.user_id JOIN ops.job_queue q ON q.id=j.id AND q.aggregate_id=j.id WHERE j.status='succeeded' AND q.domain='simc' AND q.command_type='run_simulation' AND i.provider='qq' AND EXISTS (SELECT 1 FROM simc.source_snapshots s WHERE s.user_id=j.user_id AND s.snapshot_json->'character'->>'classKey'='shaman' AND s.snapshot_json->'character'->>'specKey'='elemental') ORDER BY j.user_id LIMIT 2").fetchall()]
        assert len(owners)==2, 'existing candidate simulation owners required'
    else:
        owners=[r[0] for r in c.execute("SELECT user_id FROM identity.user_identities WHERE provider='qq' AND provider_subject LIKE 'simc-all-smoke-%%' ORDER BY user_id LIMIT 2").fetchall()]
        assert len(owners)==2,'dedicated prior synthetic smoke owners required'
    for uid in owners:
        t=secrets.token_urlsafe(32);tokens.append(t)
        c.execute("INSERT INTO identity.auth_sessions(token_hash,user_id,kind,expires_at) VALUES (%s,%s,'web_cookie',now()+interval '90 minutes')",(hashlib.sha256(t.encode()).hexdigest(),uid))
if a.mode=='candidate':
    u=pwd.getpwnam('ubuntu')
    for kind,command in [('worker',['-m','server.app.worker.main','--worker-id','simc-quota-candidate']),('api',['-m','uvicorn','server.app.main:app','--host','127.0.0.1','--port','18890','--log-level','warning'])]:
        log=open('/var/lib/chickenbro-simc-update-candidate-20260915/'+kind+'.log','ab')
        children.append(subprocess.Popen(['/opt/chickenbro-runtime/bin/python',*command],cwd=a.source,env=env,user=u.pw_uid,group=u.pw_gid,start_new_session=True,stdout=log,stderr=log))
base='http://127.0.0.1:18890' if a.mode=='candidate' else 'https://www.chickenbro.cloud'
csrf=secrets.token_urlsafe(24);cookie=env.get('WOW_WEB_COOKIE_NAME','__Host-chickenbro-session');csrf_cookie=env.get('WOW_WEB_CSRF_COOKIE_NAME','__Host-chickenbro-csrf')
headers={'Host':'www.chickenbro.cloud','Origin':'https://www.chickenbro.cloud','Cookie':f'{cookie}={tokens[0]}; {csrf_cookie}={csrf}','X-CSRF-Token':csrf}
other={'Host':'www.chickenbro.cloud','Cookie':cookie+'='+tokens[1]}
with httpx.Client(base_url=base,timeout=20) as client:
    def req(method,path,status=200,**kwargs):
        r=client.request(method,'/api/v2'+path,headers=kwargs.pop('headers',headers),**kwargs)
        assert r.status_code==status,(method,path,r.status_code,r.text[:200])
        return r
    for i in range(30):
        try:
            if req('GET','/simc/runtime').status_code==200:break
        except (httpx.TransportError,AssertionError):time.sleep(1)
    else:raise RuntimeError('API startup failed')
    runtime=req('GET','/simc/runtime').json()
    assert runtime['sourceCommit']=='ac0f3a3c7ff9e521137c0ca1760d548330c697f3',runtime
    report['runtime']=runtime
    req('GET','/simc/jobs',401,headers={})
    with psycopg.connect(env['WOW_DATABASE_URL']) as c:
        row=c.execute("""SELECT s.id,s.snapshot_json FROM simc.source_snapshots s
        WHERE s.user_id=%s AND s.snapshot_json->'character'->>'classKey'='shaman'
          AND s.snapshot_json->'character'->>'specKey'='elemental'
          AND NOT (s.provenance_json ? 'wclTalentReconstruction')
          AND EXISTS (SELECT 1 FROM simc.simulation_jobs j JOIN ops.job_queue q ON q.id=j.id
          WHERE j.snapshot_id=s.id AND j.status='succeeded' AND q.domain='simc')
        ORDER BY s.created_at DESC LIMIT 1""",(owners[0],)).fetchone()
        assert row,'dedicated usable snapshot required'
        sid=str(row[0]);snapshot=row[1]
    req('GET','/simc/snapshots/'+sid,404,headers=other)
    results=[]
    for case in (['talent'] if a.remaining else ['single','multi','talent']):
        targets=5 if case=='multi' else 1
        key='runtime-upgrade-'+uuid4().hex
        body={'snapshotId':sid,'scenario':{'iterations':100,'maxTime':60,'fightStyle':'Patchwerk','desiredTargets':targets,'varyCombatLength':0.2,'raidBuffs':True,'bloodlust':True}}
        if case=='talent':
            from server.app.simulation.talent_editor import talent_options,edit_talents,TalentEditError
            options=talent_options(snapshot['character'],snapshot['talents'],runtime['runtimeRevision'])
            assert options['catalogRevision']==runtime['sourceCommit']
            changes=[]
            for node in options['nodes']:
                selected=next((e for e in node['entries'] if e['selectedRank']>0),None)
                alternative=next((e for e in node['entries'] if not e['selectedRank'] and e['tree'] in (1,2)),None)
                if node['nodeType']==2 and selected and alternative:
                    override={'nodes':[{'nodeId':node['nodeId'],'entryId':alternative['entryId'],'rank':selected['selectedRank']}]}
                    try:
                        edited=edit_talents(snapshot['talents'],snapshot['character'],runtime['runtimeRevision'],override)
                    except TalentEditError:continue
                    assert len(edited['changes'])==1
                    body['scenario']['talentOverrides']=override;changes=edited['changes'];break
            assert changes,'a valid selected choice node is required'
        if a.resume_job:
            with psycopg.connect(env['WOW_DATABASE_URL']) as c:
                resumed=c.execute('SELECT idempotency_key FROM simc.simulation_jobs WHERE id=%s AND user_id=%s AND snapshot_id=%s',(a.resume_job,owners[0],sid)).fetchone()
            assert resumed
            job=req('POST','/simc/jobs',202,json=body,headers={**headers,'Idempotency-Key':resumed[0]}).json()
            assert job['id']==a.resume_job
        else:
            job=req('POST','/simc/jobs',202,json=body,headers={**headers,'Idempotency-Key':key}).json()
            assert req('POST','/simc/jobs',202,json=body,headers={**headers,'Idempotency-Key':key}).json()['id']==job['id']
        report['lastJobId']=job['id']
        req('GET','/simc/jobs/'+job['id'],404,headers=other)
        for _ in range(120):
            detail=req('GET','/simc/jobs/'+job['id']+'?view=workbench&scenarioVersion=4&reportLocale=zhCN').json()
            if detail['status']=='succeeded':break
            assert detail['status'] in ('queued','running'),detail
            time.sleep(1)
        assert detail['status']=='succeeded'
        assert detail['result']['metricValue']>0
        with psycopg.connect(env['WOW_DATABASE_URL']) as c:
            proof=c.execute('SELECT result_json FROM simc.simulation_results WHERE job_id=%s',(job['id'],)).fetchone()[0]
            identity=c.execute('SELECT runtime_revision,compiler_revision FROM simc.simulation_jobs WHERE id=%s',(job['id'],)).fetchone()
        assert identity[0]==runtime['runtimeRevision']
        assert proof['effectiveConfig']['status']=='verified'
        assert 'talents' in proof['effectiveConfig']['checked']
        loc=detail['result']['report']['localization']
        assert loc['catalogRevision'] and loc['gameVersion']=='12.1.0.69814'
        assert loc['status'] not in ('unavailable','legacy')
        record={'case':case,'localizationStatus':loc['status'],'localizationRevision':loc['catalogRevision'],'jobId':job['id'],'targets':targets,'dps':detail['result']['metricValue'],'runtimeRevision':identity[0],
            'compilerRevision':identity[1],'effectiveConfigStatus':proof['effectiveConfig']['status'],
            'resultKeys':list(proof),'publicReportKeys':list(detail.get('result',{}))}
        results.append(record);report['cases']=results
        print(json.dumps(record),flush=True)
    if not a.remaining:assert results[0]['dps']!=results[1]['dps']
    report['checks'].update(realQueueWorkerPositiveMetrics=True,sourceAndEngineIdentity=True,
        effectiveConfigVerified=True,idempotency=True,secondOwnerIsolation=True,unauthenticatedDenied=True,scenarioDifference=not a.remaining,talentChoiceChangeVerified=True,localizedNewBuild=True)
cleanup();tokens.clear();report.update(passed=True,sessionsRevoked=True,productionIdentitiesCreated=0)
print(json.dumps(report,ensure_ascii=False),flush=True)

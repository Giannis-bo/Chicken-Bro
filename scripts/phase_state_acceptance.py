"""Isolated and live HTTP smoke. No new production identities; tokens never printed."""
import argparse,atexit,base64,hashlib,io,json,os,pwd,re,secrets,signal,socket,subprocess,sys,time
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,unquote,parse_qs
from uuid import uuid4
import httpx,psycopg
os.umask(0o077)

p=argparse.ArgumentParser();p.add_argument('mode',choices=['candidate','production']);p.add_argument('source');p.add_argument('--remaining',action='store_true');p.add_argument('--label',required=True);p.add_argument('--before',action='store_true');p.add_argument('--resume-job');a=p.parse_args()
prod_pid=subprocess.check_output(['systemctl','show','chickenbro-api','-p','MainPID','--value'],text=True).strip()
env=dict(v.split('=',1) for v in Path('/proc/'+prod_pid+'/environ').read_text().split('\0') if '=' in v)
assert urlsplit(env['WOW_DATABASE_URL']).path=='/chickenbro_prod'
children=[];tokens=[];report={'phase':'before' if a.before else 'after','mode':a.mode,'source':str(Path(a.source).resolve()),'checks':{}}
if a.mode=='candidate':
    for port in (18895,):
        with socket.socket() as s:
            s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',port))
    dsn=urlsplit(env['WOW_DATABASE_URL']);db='chickenbro_badcase_candidate_20260909'
    for line in Path(env['PGPASSFILE']).read_text().splitlines():
        f=[re.sub(r'\\(.)',r'\1',v) for v in re.split(r'(?<!\\):',line)]
        if len(f)==5 and f[2]==dsn.path.lstrip('/') and f[3]==unquote(dsn.username):env['PGPASSWORD']=f[4];break
    assert env.get('PGPASSWORD')
    exists=subprocess.check_output(['sudo','-n','-u','postgres','psql','-XAt','-c',"SELECT count(*) FROM pg_database WHERE datname='"+db+"'"],text=True).strip()
    assert exists=='1','existing isolated database required'
    private=Path('/var/lib/chickenbro-phase-state-candidate-20260920');private.mkdir(mode=0o700,exist_ok=True)
    u=pwd.getpwnam('ubuntu');os.chown(private,u.pw_uid,u.pw_gid)
    env.update(WOW_DATABASE_URL=urlunsplit(dsn._replace(path='/'+db)),WOW_APP_ENV='test',WOW_API_V2_PORT='18895',
        WOW_CHAT_WORKER_TOOL_PORT='18794',WOW_CHAT_DURABLE_ENABLED='0',WOW_TEST_LOGIN_ENABLED='0',WOW_WORKER_V2_HEARTBEAT_PATH=str(private/'heartbeat.json'),
        WOW_CODEX_JOBS_DIR=str(private/'jobs'),WOW_WEB_COOKIE_NAME='__Host-badcase-session',WOW_WEB_CSRF_COOKIE_NAME='__Host-badcase-csrf',
        WOW_QQ_REDIRECT_URI=env['WOW_WEB_ORIGIN']+'/test/api/v2/auth/qq/callback',PYTHONPATH=a.source,WOW_SIMC_BIN='/opt/wow-simc/current/simc')
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
    for kind,command in [('worker',['-m','server.app.worker.main','--worker-id','phase-state-candidate']),('api',['-m','uvicorn','server.app.main:app','--host','127.0.0.1','--port','18895','--log-level','warning'])]:
        log=open('/var/lib/chickenbro-phase-state-candidate-20260920/'+kind+'.log','ab')
        children.append(subprocess.Popen(['/opt/chickenbro-runtime/bin/python',*command],cwd=a.source,env=env,user=u.pw_uid,group=u.pw_gid,start_new_session=True,stdout=log,stderr=log))
base='http://127.0.0.1:18895' if a.mode=='candidate' else 'https://www.chickenbro.cloud'
csrf=secrets.token_urlsafe(24);cookie=env.get('WOW_WEB_COOKIE_NAME','__Host-chickenbro-session');csrf_cookie=env.get('WOW_WEB_CSRF_COOKIE_NAME','__Host-chickenbro-csrf')
headers={'Host':'www.chickenbro.cloud','Origin':'https://www.chickenbro.cloud','Cookie':f'{cookie}={tokens[0]}; {csrf_cookie}={csrf}','X-CSRF-Token':csrf}
other={'Host':'www.chickenbro.cloud','Cookie':cookie+'='+tokens[1]}
with httpx.Client(base_url=base,timeout=30) as client:
    def req(method,path,status=200,**kwargs):
        r=client.request(method,'/api/v2'+path,headers=kwargs.pop('headers',headers),**kwargs)
        assert r.status_code==status,(method,path,r.status_code)
        return r
    for i in range(30):
        try:
            if req('GET','/simc/runtime').status_code==200:break
        except (httpx.TransportError,AssertionError):time.sleep(1)
    else:raise RuntimeError('API startup failed')
    runtime=req('GET','/simc/runtime').json();report['runtime']=runtime
    req('GET','/simc/jobs',401,headers={})
    source=req('POST','/simc/snapshots',201,json={'sourceUrl':'https://raider.io/cn/characters/cn/silver-hand/Giannis'}).json()
    assert source['readiness']=='READY_FOR_SIMC',source['blockers']
    sid=source['id'];req('GET','/simc/snapshots/'+sid,404,headers=other)
    report['source']={'url':source['sourceUrl'],'revision':source['provenance']['sourceRevision'],'sha256':source['provenance']['sourceRawSha256']}
    results=[]
    cases=['light','reckless'] if a.mode=='candidate' else ['light','reckless']
    for case in cases:
        scenario=json.loads((Path(__file__).parent/(case+'-accepted-scenario.json')).read_text())
        scenario['iterations']=32 if a.mode=='candidate' else 8
        key='phase-state-'+uuid4().hex
        body={'snapshotId':sid,'scenario':scenario}
        job=req('POST','/simc/jobs',202,json=body,headers={**headers,'Idempotency-Key':key}).json()
        assert req('POST','/simc/jobs',202,json=body,headers={**headers,'Idempotency-Key':key}).json()['id']==job['id']
        req('GET','/simc/jobs/'+job['id'],404,headers=other)
        for _ in range(120):
            detail=req('GET','/simc/jobs/'+job['id']+'?view=workbench&scenarioVersion=6&reportLocale=zhCN').json()
            if detail['status'] in ('succeeded','failed'):break
            time.sleep(1)
        assert detail['status']=='succeeded',(case,detail['status'],detail.get('errorCode'))
        assert detail['compilerRevision']=='chickenbro-simc-compiler-v7'
        assert detail['scenario']['initialState']['resources']['maelstrom']=='max'
        with psycopg.connect(env['WOW_DATABASE_URL']) as c:
            proof=c.execute('SELECT result_json FROM simc.simulation_results WHERE job_id=%s',(job['id'],)).fetchone()[0]
        phase=proof['phaseEvidence'];assert phase['status']=='satisfied' and phase['allInitialStatesVerified']
        assert phase['iterations']==scenario['iterations']
        assert detail['result']['report']['statistics']['iterations']==scenario['iterations']
        assert abs(detail['result']['metricValue']-phase['damage']['mean']/20)<1e-6
        assert proof['effectiveConfig']['status']=='verified'
        record={'case':case,'jobId':job['id'],'scenario':scenario,'phase':phase,
                'metric':detail['result']['metricValue'],'compilerRevision':detail['compilerRevision'],
                'runtimeRevision':detail['runtimeRevision'],'profileSha256':detail['result']['profileSha256']}
        results.append(record);report['cases']=results
        print(json.dumps({'case':case,'jobId':job['id'],'damage':phase['damage'],'actions':phase['actions'],'overflow':phase['resourceOverflow'].get('maelstrom')},ensure_ascii=False),flush=True)
    if a.mode=='candidate':
        bad=json.loads(json.dumps(scenario));bad['iterations']=1
        bad['initialState']['buffs']={'nonexistent_phase_probe':{'stacks':1,'remainingSeconds':10}}
        job=req('POST','/simc/jobs',202,json={'snapshotId':sid,'scenario':bad},headers={**headers,'Idempotency-Key':'phase-negative-'+uuid4().hex}).json()
        for _ in range(45):
            detail=req('GET','/simc/jobs/'+job['id']).json()
            if detail['status']=='failed':break
            time.sleep(1)
        assert detail['status']=='failed' and detail['result'] is None
        report['negative']={'jobId':job['id'],'code':detail['errorCode']}
    # Real owner-scoped gateway read/compare, using the same application and stored reports.
    from server.app.main import app
    from server.app.chickenbro.simulation_tools import SimulationToolGateway,SimulationToolContext
    from server.app.identity.domain import Principal
    gateway=SimulationToolGateway(app.state.chickenbro_simulation_gateway._application)
    capability=gateway.issue_capability(SimulationToolContext(Principal(owners[0],'web_cookie'),uuid4(),uuid4()))
    try:
        packet=gateway.execute(capability,'get',{'jobId':results[0]['jobId']})
        assert packet['result']['phaseEvidence']['allInitialStatesVerified']
        comparison=gateway.execute(capability,'compare',{'baselineJobId':results[0]['jobId'],'variantJobId':results[1]['jobId']})
        assert comparison['status']=='ready',comparison
        report['comparison']=comparison['comparison']
        options=gateway.execute(capability,'options',{'snapshotId':sid,'kind':'effects','query':'flowing_elements'})
        assert options['status']=='ready',options
        report['checks']['chatGatewayReadCompareOptions']=True
    finally:gateway.revoke(capability)
    report['checks'].update(realQueueWorker=True,sourceAndEngineIdentity=True,effectiveConfigVerified=True,
        idempotency=True,secondOwnerIsolation=True,unauthenticatedDenied=True,allIterationsVerified=True)
cleanup();tokens.clear();report.update(passed=True,sessionsRevoked=True,productionIdentitiesCreated=0)
print(json.dumps({'passed':True,'mode':a.mode,'checks':report['checks']},ensure_ascii=False),flush=True)

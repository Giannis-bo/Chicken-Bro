"""Isolated and live HTTP smoke. No new production identities; tokens never printed."""
import argparse,atexit,base64,hashlib,io,json,os,pwd,re,secrets,signal,socket,subprocess,sys,time
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,unquote,parse_qs
from uuid import uuid4
import httpx,psycopg
from PIL import Image,ImageDraw,ImageFont
p=argparse.ArgumentParser();p.add_argument('mode',choices=['candidate','production']);p.add_argument('source');a=p.parse_args()
prod_pid=subprocess.check_output(['systemctl','show','chickenbro-api','-p','MainPID','--value'],text=True).strip()
env=dict(v.split('=',1) for v in Path('/proc/'+prod_pid+'/environ').read_text().split('\0') if '=' in v)
assert urlsplit(env['WOW_DATABASE_URL']).path=='/chickenbro_prod'
children=[];tokens=[];report={'mode':a.mode,'source':str(Path(a.source).resolve()),'checks':{}}
if a.mode=='candidate':
    for port in (18790,18794):
        with socket.socket() as s:s.bind(('127.0.0.1',port))
    dsn=urlsplit(env['WOW_DATABASE_URL']);db='chickenbro_badcase_candidate_20260909'
    for line in Path(env['PGPASSFILE']).read_text().splitlines():
        f=[re.sub(r'\\(.)',r'\1',v) for v in re.split(r'(?<!\\):',line)]
        if len(f)==5 and f[2]==dsn.path.lstrip('/') and f[3]==unquote(dsn.username):env['PGPASSWORD']=f[4];break
    assert env.get('PGPASSWORD')
    exists=subprocess.check_output(['sudo','-n','-u','postgres','psql','-XAt','-c',"SELECT count(*) FROM pg_database WHERE datname='"+db+"'"],text=True).strip()
    assert exists=='1','existing isolated database required'
    private=Path('/var/lib/chickenbro-custom-apl-release-candidate');private.mkdir(mode=0o700,exist_ok=True)
    u=pwd.getpwnam('ubuntu');os.chown(private,u.pw_uid,u.pw_gid)
    env.update(WOW_DATABASE_URL=urlunsplit(dsn._replace(path='/'+db)),WOW_APP_ENV='test',WOW_API_V2_PORT='18790',
        WOW_CHAT_WORKER_TOOL_PORT='18794',WOW_SIMC_COMPILER_REVISION='chickenbro-simc-compiler-v6',WOW_TEST_LOGIN_ENABLED='0',WOW_WORKER_V2_HEARTBEAT_PATH=str(private/'heartbeat.json'),
        WOW_CODEX_JOBS_DIR=str(private/'jobs'),WOW_WEB_COOKIE_NAME='__Host-badcase-general-session',WOW_WEB_CSRF_COOKIE_NAME='__Host-badcase-general-csrf',
        WOW_QQ_REDIRECT_URI=env['WOW_WEB_ORIGIN']+'/test/api/v2/auth/qq/callback',PYTHONPATH=a.source)
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
        with psycopg.connect(env['WOW_DATABASE_URL']) as c:
            active=c.execute("SELECT count(*) FROM chat.agent_runs WHERE status='streaming'").fetchone()[0]+c.execute("SELECT count(*) FROM simc.simulation_jobs WHERE status IN ('queued','running')").fetchone()[0]
        if active:
            print(json.dumps({'cleanup':'active_candidate_left_running_for_safe_completion'}),flush=True);return
    for child in children:
        if child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=15)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
atexit.register(cleanup)
with psycopg.connect(env['WOW_DATABASE_URL']) as c:
    if a.mode=='candidate':
        owners=[uuid4(),uuid4()]
        for uid in owners:
            c.execute('INSERT INTO identity.users(id) VALUES (%s)',(uid,))
            c.execute("INSERT INTO identity.user_identities(id,user_id,provider,app_context,provider_subject) VALUES (%s,%s,'qq',%s,%s)",(uuid4(),uid,env['WOW_QQ_APPID'],'badcase-general-isolated-'+uuid4().hex))
    else:
        owners=[r[0] for r in c.execute("SELECT user_id FROM identity.user_identities WHERE provider='qq' AND provider_subject LIKE 'simc-all-smoke-%%' ORDER BY user_id LIMIT 2").fetchall()]
        assert len(owners)==2,'dedicated prior synthetic smoke owners required'
    for uid in owners:
        t=secrets.token_urlsafe(32);tokens.append(t)
        c.execute("INSERT INTO identity.auth_sessions(token_hash,user_id,kind,expires_at) VALUES (%s,%s,'web_cookie',now()+interval '20 minutes')",(hashlib.sha256(t.encode()).hexdigest(),uid))
if a.mode=='candidate':
    u=pwd.getpwnam('ubuntu')
    for kind,command in [('worker',['-m','server.app.worker.main','--worker-id','badcase-general-candidate']),('api',['-m','uvicorn','server.app.main:app','--host','127.0.0.1','--port','18790','--log-level','warning'])]:
        log=open('/var/lib/chickenbro-custom-apl-release-candidate/'+kind+'.log','ab')
        children.append(subprocess.Popen(['/opt/chickenbro-runtime/bin/python',*command],cwd=a.source,env=env,user=u.pw_uid,group=u.pw_gid,start_new_session=True,stdout=log,stderr=log))
base='http://127.0.0.1:18790' if a.mode=='candidate' else 'https://www.chickenbro.cloud'
csrf=secrets.token_urlsafe(24);cookie=env.get('WOW_WEB_COOKIE_NAME','__Host-chickenbro-session');csrf_cookie=env.get('WOW_WEB_CSRF_COOKIE_NAME','__Host-chickenbro-csrf')
headers={'Host':'www.chickenbro.cloud','Origin':'https://www.chickenbro.cloud','Cookie':f'{cookie}={tokens[0]}; {csrf_cookie}={csrf}','X-CSRF-Token':csrf}
other={'Host':'www.chickenbro.cloud','Cookie':cookie+'='+tokens[1]}
with httpx.Client(base_url=base,timeout=510) as client:
    def req(method,path,status=200,**kwargs):
        r=client.request(method,'/api/v2'+path,headers=kwargs.pop('headers',headers),**kwargs)
        assert r.status_code==status,(method,path,r.status_code)
        return r
    for i in range(30):
        try:
            if req('GET','/chat/conversations').status_code==200:break
        except (httpx.TransportError,AssertionError):time.sleep(1)
    else:raise RuntimeError('API failed to start')
    req('GET','/chat/conversations',401,headers={'Authorization':'Bearer retired-mini-token'})
    req('POST','/chat/conversations',403,headers={'Cookie':cookie+'='+tokens[0],'Origin':headers['Origin']},json={'title':'must reject'})
    req('POST','/auth/mini/login',404,headers={},json={'code':'retired'})
    report['checks']['retiredBearerAndEndpointCsrf']=True
    # Authorization URL creation only; no claim of a fresh interactive QQ login.
    login=req('POST','/auth/qq/login',json={},headers={'Host':'www.chickenbro.cloud','Origin':'https://www.chickenbro.cloud'})
    login_data=login.json(); url=login_data.get('authorizationUrl') or login_data.get('url')
    assert url and urlsplit(url).hostname=='graph.qq.com'
    assert parse_qs(urlsplit(url).query)['client_id']==[env['WOW_QQ_APPID']]
    report['checks']['qqAuthorizationUrl']=True
    source=req('POST','/simc/snapshots?view=workbench',201,json={'sourceUrl':'https://raider.io/characters/cn/alar/fusionbolt'}).json()
    assert source['readiness']=='READY_FOR_SIMC',source.get('readiness')
    req('GET','/simc/snapshots/'+source['id'],404,headers=other)
    # Two complete runtime-bound APLs already proven to execute the intended orders.
    import tarfile
    from server.app.simulation.readiness import inspect_managed_simc_runtime
    from server.app.chickenbro.simulation_tools import SimulationToolGateway,SimulationToolContext
    from server.app.identity.domain import Principal
    from server.app.platform.config import AppSettings
    from server.app.platform.postgres import PostgresConnectionFactory
    from server.app.simulation.application import SimulationApplication
    from server.app.simulation.repository import PostgresSimulationRepository
    identity=inspect_managed_simc_runtime()
    with tarfile.open('/opt/wow-simc/source-'+identity.source_commit+'.tar.gz') as t:
        apl=t.extractfile('simc-'+identity.source_commit+'/ActionPriorityLists/default/shaman_elemental.simc').read().decode()
    lists={}
    for line in apl.splitlines():
        match=re.fullmatch(r'actions(?:\.([a-z_0-9]+))?\+?=(.*)',line)
        if match:lists.setdefault(match[1] or 'default',[]).append(match[2].removeprefix('/'))
    for name in lists:lists[name]=[x for x in lists[name] if x.split(',',1)[0] not in {'stormkeeper','ascendance'}]
    import copy
    jobs=[]
    for order in ('stormkeeper:ascendance','ascendance:stormkeeper'):
        variant=copy.deepcopy(lists)
        variant['default'][0:0]=(['stormkeeper,if=cooldown.ascendance.ready','ascendance,if=buff.stormkeeper.up'] if order.startswith('stormkeeper') else ['ascendance','stormkeeper,if=buff.ascendance.up'])
        key='apl-smoke-'+uuid4().hex
        body={'snapshotId':source['id'],'scenario':{'actionLists':variant,'iterations':100,'maxTime':60,'desiredTargets':1,'varyCombatLength':0}}
        job=req('POST','/simc/jobs',202,json=body,headers={**headers,'Idempotency-Key':key}).json()
        assert req('POST','/simc/jobs',202,json=body,headers={**headers,'Idempotency-Key':key}).json()['id']==job['id']
        req('GET','/simc/jobs/'+job['id'],404,headers=other)
        for _ in range(120):
            detail=req('GET','/simc/jobs/'+job['id']+'?view=workbench&scenarioVersion=4').json()
            if detail['status']=='succeeded':break
            assert detail['status'] in ('queued','running'),(detail['status'],detail.get('errorCode'))
            time.sleep(2)
        assert detail['status']=='succeeded'
        assert detail['scenario']['actionLists']==variant
        result=detail['result'];assert result['metricValue']>0 and result['runtimeRevision']==identity.runtime_revision
        with psycopg.connect(env['WOW_DATABASE_URL']) as c:
            row=c.execute('SELECT result_json FROM simc.simulation_results WHERE job_id=%s AND user_id=%s',(job['id'],owners[0])).fetchone()
        stored=row[0];proof=stored['effectiveConfig'];evidence=stored['actionEvidence']
        assert proof['status']=='verified' and proof['profileSha256']==result['profileSha256']==evidence['profileSha256']
        observed=[x for x in evidence['sample'] if x['name'] in ('stormkeeper','ascendance')]
        assert len(observed)>=2 and ':'.join(x['name'] for x in observed[:2])==order and observed[0]['time']<observed[1]['time'],observed
        jobs.append({'id':job['id'],'order':order,'dps':result['metricValue'],'profileSha256':result['profileSha256'],'observedActions':observed,'runtimeRevision':result['runtimeRevision']})
        print(json.dumps({'step':'simc','mode':a.mode,**jobs[-1]}),flush=True)
    # Read the persisted jobs through the same trusted host gateway used by Chat.
    from server.app.main import app
    gateway=SimulationToolGateway(app.state.simulation_application)
    token=gateway.issue_capability(SimulationToolContext(Principal(owners[0],'web_cookie'),uuid4(),uuid4()))
    try:
        comparison=gateway.execute(token,'compare',{'baselineJobId':jobs[0]['id'],'variantJobId':jobs[1]['id']})
        assert comparison['status']=='ready',comparison.get('errorCode')
        assert 'actionLists' in comparison['comparison']['changes']
        read=gateway.execute(token,'get',{'jobId':jobs[0]['id']})
        assert read['result']['actionEvidence']['sample']
        report['comparison']=comparison['comparison']
        report['checks']['chatGatewayComparisonAndActionEvidence']=True
    finally:gateway.revoke(token)
    report['jobs']=jobs;report['checks'].update(realCustomAplQueueWorkerResult=True,actualOppositeCastOrders=True,simcIdempotencyAndIsolation=True,effectiveConfig=True)
    # Original player wording: must research, must not invent a completed experiment.
    conv=req('POST','/chat/conversations',201,json={'title':'Custom APL release terminology smoke'},headers={**headers,'Idempotency-Key':uuid4().hex}).json()
    path='/chat/conversations/'+conv['id'];key='apl-chat-'+uuid4().hex
    question='元素萨玩家说的“神器”是什么？四件套和升腾有什么关系？先核对当前版本，没查到的不要猜。这轮只问机制，不要提交模拟。'
    response=req('POST',path+'/messages/stream?includeProgress=true',json={'content':question,'clientMessageId':key},headers={**headers,'Idempotency-Key':key})
    events=[json.loads(line[5:]) for line in response.text.splitlines() if line.startswith('data:')]
    started=next(e for e in events if e.get('type')=='started')
    assert any(e.get('type')=='completed' for e in events),'no completed SSE'
    history=req('GET',path+'?includeProgress=true').json();answer=[m['content'] for m in history['messages'] if m['role']=='assistant'][-1]
    req('GET',path,404,headers=other)
    with psycopg.connect(env['WOW_DATABASE_URL']) as c:
        calls=c.execute('SELECT operation,state FROM chat.tool_results WHERE run_id=%s ORDER BY started_at',(started['runId'],)).fetchall()
        assert any(op=='source.public_web' and state=='completed' for op,state in calls),calls
        c.execute("UPDATE chat.conversations SET status='archived' WHERE id=%s AND user_id=%s",(conv['id'],owners[0]))
    report.update(chatRunId=started['runId'],chatAnswer=answer,chatTools=[{'operation':op,'state':state} for op,state in calls])
    report['checks'].update(chatResearchFirst=True,chatSseHistoryAndIsolation=True)
cleanup();tokens.clear();report.update(passed=True,sessionsRevoked=True,productionIdentitiesCreated=0)
print(json.dumps(report,ensure_ascii=False),flush=True)
(Path(__file__).parent/(a.mode+'-business.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

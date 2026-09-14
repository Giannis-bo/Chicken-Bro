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
    private=Path('/var/lib/chickenbro-simc-quota-candidate-20260914');private.mkdir(mode=0o700,exist_ok=True)
    u=pwd.getpwnam('ubuntu');os.chown(private,u.pw_uid,u.pw_gid)
    env.update(WOW_DATABASE_URL=urlunsplit(dsn._replace(path='/'+db)),WOW_APP_ENV='test',WOW_API_V2_PORT='18890',
        WOW_CHAT_WORKER_TOOL_PORT='18794',WOW_TEST_LOGIN_ENABLED='0',WOW_WORKER_V2_HEARTBEAT_PATH=str(private/'heartbeat.json'),
        WOW_CODEX_JOBS_DIR=str(private/'jobs'),WOW_WEB_COOKIE_NAME='__Host-badcase-session',WOW_WEB_CSRF_COOKIE_NAME='__Host-badcase-csrf',
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
        owners=[r[0] for r in c.execute("SELECT DISTINCT j.user_id FROM simc.simulation_jobs j JOIN identity.user_identities i ON i.user_id=j.user_id JOIN ops.job_queue q ON q.id=j.id AND q.aggregate_id=j.id WHERE j.status='succeeded' AND q.domain='simc' AND q.command_type='run_simulation' AND i.provider='qq' ORDER BY j.user_id LIMIT 2").fetchall()]
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
        log=open('/var/lib/chickenbro-simc-quota-candidate-20260914/'+kind+'.log','ab')
        children.append(subprocess.Popen(['/opt/chickenbro-runtime/bin/python',*command],cwd=a.source,env=env,user=u.pw_uid,group=u.pw_gid,start_new_session=True,stdout=log,stderr=log))
base='http://127.0.0.1:18890' if a.mode=='candidate' else 'https://www.chickenbro.cloud'
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
    canvas=Image.new('RGB',(64,64),'white');buffer=io.BytesIO();canvas.save(buffer,format='PNG')
    encoded='data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode()
    uploaded=req('POST','/chat/images',201,json={'dataUrl':encoded},headers={**headers,'Idempotency-Key':str(uuid4())}).json()
    image_id=uploaded.get('id') or uploaded.get('imageId')
    assert image_id
    restored=req('GET','/chat/images/'+str(image_id)).json()
    assert restored.get('dataUrl','').startswith('data:image/')
    req('GET','/chat/images/'+str(image_id),404,headers=other)
    report['checks']['privateImageReadAndIsolation']=True
    def create(title):
        return req('POST','/chat/conversations',201,json={'title':title},headers={**headers,'Idempotency-Key':str(uuid4())}).json()['id']
    def ask(cid,prompt):
        key=str(uuid4());mid=str(uuid4());before_dirs=set(Path(env['WOW_CODEX_JOBS_DIR']).glob('*/native-tool-observations.jsonl'));started=time.monotonic()
        response=req('POST','/chat/conversations/'+cid+'/messages/stream',json={'content':prompt,'clientMessageId':mid},headers={**headers,'Idempotency-Key':key})
        with psycopg.connect(env['WOW_DATABASE_URL']) as c:
            row=c.execute("SELECT id,status,public_error_code,model_usage FROM chat.agent_runs WHERE user_id=%s AND conversation_id=%s ORDER BY started_at DESC LIMIT 1",(owners[0],cid)).fetchone()
            messages=c.execute("SELECT content FROM chat.messages WHERE conversation_id=%s AND role='assistant' ORDER BY created_at DESC LIMIT 1",(cid,)).fetchone()
            tools=c.execute("SELECT operation,result_json FROM chat.tool_results WHERE run_id=%s ORDER BY started_at",(row[0],)).fetchall()
        native=[]
        for f in set(Path(env['WOW_CODEX_JOBS_DIR']).glob('*/native-tool-observations.jsonl'))-before_dirs:
            identity=f.parent/'run-identity.json'
            if identity.is_file() and json.loads(identity.read_text()).get('runId')==str(row[0]):
                native.extend(json.loads(line) for line in f.read_text().splitlines() if line.strip())
        record={'observationBinding':'exact_run_id','elapsedSeconds':round(time.monotonic()-started,3),'nativeObservations':native,'runId':str(row[0]),'runStatus':row[1],'errorCode':row[2],'modelUsage':row[3],'finalAnswer':messages[0] if messages else '',
            'toolObservations':[{'tool':op,'status':(r or {}).get('status'),'evidenceRefs':(r or {}).get('evidenceRefs',[])} for op,r in tools],
            'conversationId':cid,'sseCompleted':'event: completed' in response.text}
        report.setdefault('cases',[]).append(record)
        (Path(__file__).parent/(a.label+'-private.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(json.dumps({'case':len(report['cases']),'runId':record['runId'],'status':record['runStatus'],'tools':len(tools)}),flush=True)
        assert row[1]=='succeeded' and record['sseCompleted'],record['errorCode']
        # Stored answer and replay should match without issuing a second run.
        req('GET','/chat/conversations/'+cid,404,headers=other)
        replay=req('POST','/chat/conversations/'+cid+'/messages/stream',json={'content':prompt,'clientMessageId':mid},headers={**headers,'Idempotency-Key':key})
        assert 'event: completed' in replay.text
        with psycopg.connect(env['WOW_DATABASE_URL']) as c:
            assert c.execute('SELECT count(*) FROM chat.agent_runs WHERE conversation_id=%s',(cid,)).fetchone()[0]==1
            assert c.execute("SELECT count(*) FROM chat.messages WHERE conversation_id=%s AND role='assistant'",(cid,)).fetchone()[0]==1
        return record
    cid=create('simc-quota:continuation')
    with psycopg.connect(env['WOW_DATABASE_URL']) as c:
        base_job=c.execute("SELECT j.id FROM simc.simulation_jobs j JOIN ops.job_queue q ON q.id=j.id AND q.aggregate_id=j.id WHERE j.user_id=%s AND j.status='succeeded' AND q.domain='simc' AND q.command_type='run_simulation' ORDER BY j.created_at DESC LIMIT 1",(owners[0],)).fetchone()[0]
        before_jobs={str(row[0]) for row in c.execute('SELECT id FROM simc.simulation_jobs WHERE user_id=%s',(owners[0],)).fetchall()}
        c.execute("INSERT INTO chat.research_sessions(id,user_id,conversation_id,state,budget) VALUES (%s,%s,%s,'active',%s::jsonb)",(uuid4(),owners[0],cid,json.dumps({'submissions':['historical-fixture-'+str(n) for n in range(4)]})))
    report['fixture']={'historicalReservations':4,'syntheticConversation':True,'newSimulationLimitForSmoke':1}
    prompt=f"前面提示本研究累计4次模拟额度已用完。现在请继续使用我已有任务 {base_job} 的角色快照和其他配置，把模拟时长改为61秒、迭代次数改为100，实际重跑一次并读取DPS结果。只新增这一个任务，不做其他研究。"
    record=ask(cid,prompt);record['caseId']='continue-after-four'
    with psycopg.connect(env['WOW_DATABASE_URL']) as c:
        added=[row for row in c.execute('SELECT id,status FROM simc.simulation_jobs WHERE user_id=%s',(owners[0],)).fetchall() if str(row[0]) not in before_jobs]
        assert len(added)==1, 'expected exactly one actual new simulation'
        jid,status=added[0]
        assert status=='succeeded'
        used=c.execute('SELECT budget FROM chat.research_sessions WHERE user_id=%s AND conversation_id=%s',(owners[0],cid)).fetchone()[0]
        assert len(used['submissions'])==5, 'fifth reservation missing'
    job=req('GET','/simc/jobs/'+str(jid)+'?view=workbench&scenarioVersion=5').json()
    assert job['scenario']['iterations']==100 and job['scenario']['maxTime']==61
    assert job['result']['metricValue']>0 and job['result']['provenance']
    req('GET','/simc/jobs/'+str(jid),404,headers=other)
    report['simulation']=job
    report['checks'].update(fifthSubmissionSucceeded=True,secondOwnerSimulationDenied=True,historicalReservationsRetained=True)
    report['checks'].update(ownerIsolation=True,idempotentReplay=True)
cleanup();tokens.clear();children.clear()
(Path(__file__).parent/(a.label+'-private.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'mode':a.mode,'checks':report['checks'],'cases':len(report.get('cases',[]))}),flush=True)

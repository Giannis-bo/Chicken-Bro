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
    private=Path('/var/lib/chickenbro-wcl-release-candidate');private.mkdir(mode=0o700,exist_ok=True)
    u=pwd.getpwnam('ubuntu');os.chown(private,u.pw_uid,u.pw_gid)
    env.update(WOW_DATABASE_URL=urlunsplit(dsn._replace(path='/'+db)),WOW_APP_ENV='test',WOW_API_V2_PORT='18790',
        WOW_CHAT_WORKER_TOOL_PORT='18794',WOW_TEST_LOGIN_ENABLED='0',WOW_WORKER_V2_HEARTBEAT_PATH=str(private/'heartbeat.json'),
        WOW_CODEX_JOBS_DIR=str(private/'jobs'),WOW_WEB_COOKIE_NAME='__Host-badcase-general-session',WOW_WEB_CSRF_COOKIE_NAME='__Host-badcase-general-csrf',
        WOW_QQ_REDIRECT_URI=env['WOW_WEB_ORIGIN']+'/test/api/v2/auth/qq/callback',PYTHONPATH=a.source)
    os.environ.update(env);sys.path.insert(0,a.source)
    import importlib
    with psycopg.connect(env['WOW_DATABASE_URL']) as c:importlib.import_module('server.migrations.product.apply').apply_product_migrations(c,Path(a.source)/'server/migrations/product')
else:os.environ.update(env);sys.path.insert(0,a.source)
def cleanup():
    if tokens:
        with psycopg.connect(env['WOW_DATABASE_URL']) as c:
            for t in tokens:c.execute('UPDATE identity.auth_sessions SET revoked_at=now() WHERE token_hash=%s',(hashlib.sha256(t.encode()).hexdigest(),))
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
        log=open('/var/lib/chickenbro-wcl-release-candidate/'+kind+'.log','ab')
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
    if a.mode=='candidate':
        code=secrets.token_hex(4).upper();pic=Image.new('RGB',(850,250),'white')
        ImageDraw.Draw(pic).text((30,60),code,fill='black',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',100))
        buf=io.BytesIO();pic.save(buf,format='PNG');data='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
        key='retire-image-'+uuid4().hex
        uploaded=req('POST','/chat/images',201,json={'dataUrl':data},headers={**headers,'Idempotency-Key':key}).json()
        assert req('POST','/chat/images',201,json={'dataUrl':data},headers={**headers,'Idempotency-Key':key}).json()==uploaded
        req('GET','/chat/images/'+uploaded['id'],404,headers=other)
        conv=req('POST','/chat/conversations',201,json={'title':'Web Badcase 通用验证（复用测试账号）'},headers={**headers,'Idempotency-Key':uuid4().hex}).json()
        path='/chat/conversations/'+conv['id'];key='retire-chat-'+uuid4().hex
        body={'content':'这是魔兽插件报错截图。只抄出八位错误码。','imageIds':[uploaded['id']],'clientMessageId':key}
        with client.stream('POST','/api/v2'+path+'/messages/stream?includeProgress=true',json=body,headers={**headers,'Idempotency-Key':key}) as response:
            assert response.status_code==200
            first=next(json.loads(line[5:]) for line in response.iter_lines() if line.startswith('data:'))
            assert first['type']=='started'
        req('POST',path+'/messages/stream',409,json={'content':'魔兽并发验证','clientMessageId':uuid4().hex},headers={**headers,'Idempotency-Key':uuid4().hex})
        for _ in range(240):
            history=req('GET',path+'?includeImages=true&includeProgress=true').json()
            answers=[m for m in history['messages'] if m['role']=='assistant']
            if answers:break
            with psycopg.connect(env['WOW_DATABASE_URL']) as c:
                row=c.execute('SELECT status FROM chat.agent_runs WHERE id=%s',(first['runId'],)).fetchone()
                assert row[0] in ('streaming','succeeded'),'model failed'
            time.sleep(2)
        assert answers and code in answers[-1]['content'],'image was not recognized'
        req('GET',path,404,headers=other)
        replay=req('POST',path+'/messages/stream?includeProgress=true',json=body,headers={**headers,'Idempotency-Key':key})
        assert code in replay.text and 'event: completed' in replay.text
        report['checks'].update(trueVision=True,detachedGeneration=True,accountConcurrency=True,ownerIsolation=True,idempotentReplay=True)
        report['chatRunId']=first['runId'];print(json.dumps({'step':'chat','mode':a.mode,'passed':True}),flush=True)
        source=req('POST','/simc/snapshots?view=workbench',201,json={'sourceUrl':'https://raider.io/cn/characters/cn/the-masters-glaive/魔魔糊胡萝卜'}).json()
        assert source['readiness']=='READY_FOR_SIMC'
        req('GET','/simc/snapshots/'+source['id'],404,headers=other)
        key='retire-simc-'+uuid4().hex;body={'snapshotId':source['id'],'scenario':{'iterations':100,'maxTime':60,'fightStyle':'Patchwerk','desiredTargets':1}}
        job=req('POST','/simc/jobs',202,json=body,headers={**headers,'Idempotency-Key':key}).json()
        assert req('POST','/simc/jobs',202,json=body,headers={**headers,'Idempotency-Key':key}).json()['id']==job['id']
        req('GET','/simc/jobs/'+job['id'],404,headers=other)
        for _ in range(150):
            detail=req('GET','/simc/jobs/'+job['id']+'?view=workbench').json()
            if detail['status']=='succeeded':break
            assert detail['status'] in ('queued','running'),detail['status'];time.sleep(2)
        assert detail['status']=='succeeded'
        result=detail['result'];assert result['metricName']=='dps' and result['metricValue']>0 and result['report']
        assert result['provenance']['snapshotId']==source['id'] and result['provenance']['profileSha256']==result['profileSha256'] and result['runtimeRevision']==detail['runtimeRevision']
        report.update(jobId=job['id'],dps=result['metricValue'],runtimeRevision=result['runtimeRevision'])
        report['checks'].update(realSimcQueueWorkerResult=True,simcProvenance=True,simcIdempotencyAndIsolation=True)
    conv=req('POST','/chat/conversations',201,json={'title':'WCL 工具效率发布验证'},headers={**headers,'Idempotency-Key':uuid4().hex}).json()
    path='/chat/conversations/'+conv['id'];key='wcl-efficiency-'+uuid4().hex
    prompt='请分析 https://www.warcraftlogs.com/reports/ZgdALDkX48af26KN?fight=8&source=12 。只统计该角色战斗内2:13到2:33的圣能浪费，共浪费几点？请区分资源统计与是否损失有效治疗，不扩展为全场复盘。这个窗口对应报告相对毫秒2712438到2732438。'
    began=time.monotonic()
    response=req('POST',path+'/messages/stream?includeProgress=true',json={'content':prompt,'clientMessageId':key},headers={**headers,'Idempotency-Key':key})
    events=[json.loads(line[5:]) for line in response.text.splitlines() if line.startswith('data:')]
    first=next(e for e in events if e.get('type')=='started')
    assert any(e.get('type')=='completed' for e in events),'no completed SSE terminal'
    history=req('GET',path+'?includeProgress=true').json()
    answer=[m['content'] for m in history['messages'] if m['role']=='assistant'][-1]
    assert re.search(r'9\s*(?:点|[**]|$)',answer) or '九点' in answer,answer
    assert '治疗' in answer and any(word in answer for word in ('不等','不能','并不','不直接','不代表','无法')),'missing interpretation boundary'
    req('GET',path,404,headers=other)
    with psycopg.connect(env['WOW_DATABASE_URL']) as c:
        run_status=c.execute('SELECT status FROM chat.agent_runs WHERE id=%s',(first['runId'],)).fetchone()[0]
        tools=c.execute('SELECT operation,state,result_json FROM chat.tool_results WHERE run_id=%s ORDER BY started_at',(first['runId'],)).fetchall()
    assert run_status=='succeeded'
    stats=[f['statistics'] for _,state,result in tools if state=='completed' and isinstance(result,dict) for f in result.get('facts',[]) if isinstance(f,dict) and f.get('statistics')]
    assert stats,'real persisted statistics tool result required'
    report.update(wclRunId=first['runId'],wclSeconds=round(time.monotonic()-began,3),wclAnswer=answer,wclStatistics=stats,wclTools=[{'operation':op,'state':st} for op,st,_ in tools])
    report['checks'].update(wclHttpSseTerminal=True,wclStatisticsTool=True,wclExpectedNineWaste=True,wclInterpretationBoundary=True,wclOwnerIsolation=True)
cleanup();tokens.clear();report.update(passed=True,sessionsRevoked=True,productionIdentitiesCreated=0)
print(json.dumps(report),flush=True)

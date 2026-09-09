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
    dsn=urlsplit(env['WOW_DATABASE_URL']);db='chickenbro_simc_exp_candidate_20260909'
    for line in Path(env['PGPASSFILE']).read_text().splitlines():
        f=[re.sub(r'\\(.)',r'\1',v) for v in re.split(r'(?<!\\):',line)]
        if len(f)==5 and f[2]==dsn.path.lstrip('/') and f[3]==unquote(dsn.username):env['PGPASSWORD']=f[4];break
    assert env.get('PGPASSWORD')
    exists=subprocess.check_output(['sudo','-n','-u','postgres','psql','-XAt','-c',"SELECT count(*) FROM pg_database WHERE datname='"+db+"'"],text=True).strip()
    if exists=='0':subprocess.run(['sudo','-n','-u','postgres','createdb','-O',unquote(dsn.username),db],check=True,stdout=subprocess.DEVNULL)
    private=Path('/var/lib/chickenbro-simc-experiments-candidate');private.mkdir(mode=0o700,exist_ok=True)
    u=pwd.getpwnam('ubuntu');os.chown(private,u.pw_uid,u.pw_gid)
    env.update(WOW_DATABASE_URL=urlunsplit(dsn._replace(path='/'+db)),WOW_APP_ENV='test',WOW_API_V2_PORT='18790',
        WOW_CHAT_WORKER_TOOL_PORT='18794',WOW_TEST_LOGIN_ENABLED='0',WOW_WORKER_V2_HEARTBEAT_PATH=str(private/'heartbeat.json'),
        WOW_CODEX_JOBS_DIR=str(private/'jobs'),WOW_WEB_COOKIE_NAME='__Host-simc-experiments-session',WOW_WEB_CSRF_COOKIE_NAME='__Host-simc-experiments-csrf',
        WOW_QQ_REDIRECT_URI=env['WOW_WEB_ORIGIN']+'/test/api/v2/auth/qq/callback',PYTHONPATH=a.source,WOW_SIMC_COMPILER_REVISION='chickenbro-simc-compiler-v5')
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
            c.execute("INSERT INTO identity.user_identities(id,user_id,provider,app_context,provider_subject) VALUES (%s,%s,'qq',%s,%s)",(uuid4(),uid,env['WOW_QQ_APPID'],'simc-experiments-isolated-'+uuid4().hex))
    else:
        owners=[r[0] for r in c.execute("SELECT user_id FROM identity.user_identities WHERE provider='qq' AND provider_subject LIKE 'simc-all-smoke-%%' ORDER BY user_id LIMIT 2").fetchall()]
        assert len(owners)==2,'dedicated prior synthetic smoke owners required'
    for uid in owners:
        t=secrets.token_urlsafe(32);tokens.append(t)
        c.execute("INSERT INTO identity.auth_sessions(token_hash,user_id,kind,expires_at) VALUES (%s,%s,'web_cookie',now()+interval '20 minutes')",(hashlib.sha256(t.encode()).hexdigest(),uid))
if a.mode=='candidate':
    u=pwd.getpwnam('ubuntu')
    for kind,command in [('worker',['-m','server.app.worker.main','--worker-id','simc-experiments-candidate']),('api',['-m','uvicorn','server.app.main:app','--host','127.0.0.1','--port','18790','--log-level','warning'])]:
        log=open('/var/lib/chickenbro-simc-experiments-candidate/'+kind+'.log','ab')
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
    def completed_job(job_id):
        for _ in range(150):
            detail=req('GET','/simc/jobs/'+job_id+'?view=workbench&scenarioVersion=3').json()
            if detail['status']=='succeeded':
                assert detail['result']['metricValue']>0
                with psycopg.connect(env['WOW_DATABASE_URL']) as c:
                    proof=c.execute('SELECT result_json FROM simc.simulation_results WHERE job_id=%s',(job_id,)).fetchone()[0]
                assert proof['effectiveConfig']['status']=='verified'
                return detail
            assert detail['status'] in ('queued','running'),detail
            time.sleep(2)
        raise AssertionError('simulation did not finish')
    def chat_check(prompt, case):
        conv=req('POST','/chat/conversations',201,json={'title':'SimC 场景实验发布验证 '+case},headers={**headers,'Idempotency-Key':uuid4().hex}).json()
        path='/chat/conversations/'+conv['id'];key='simc-exp-chat-'+uuid4().hex
        body={'content':prompt,'clientMessageId':key}
        with client.stream('POST','/api/v2'+path+'/messages/stream?includeProgress=true',json=body,headers={**headers,'Idempotency-Key':key}) as response:
            assert response.status_code==200
            first=next(json.loads(line[5:]) for line in response.iter_lines() if line.startswith('data:'))
            assert first['type']=='started'
        for _ in range(240):
            history=req('GET',path+'?includeProgress=true').json()
            answers=[m for m in history['messages'] if m['role']=='assistant']
            if answers:break
            with psycopg.connect(env['WOW_DATABASE_URL']) as c:
                row=c.execute('SELECT status FROM chat.agent_runs WHERE id=%s',(first['runId'],)).fetchone()
                assert row[0] in ('streaming','succeeded'),'model failed'
            time.sleep(2)
        assert answers,'model response timeout'
        req('GET',path,404,headers=other)
        with psycopg.connect(env['WOW_DATABASE_URL']) as c:
            rows=c.execute('SELECT operation,result_json FROM chat.tool_results WHERE run_id=%s ORDER BY started_at',(first['runId'],)).fetchall()
        operations=[x[0] for x in rows]
        payload={'step':'model','case':case,'runId':first['runId'],'operations':operations,'answer':answers[-1]['content'],
                 'results':[{'operation':op,'status':r.get('status'),'errorCode':r.get('errorCode'),'jobId':r.get('jobId'),'comparison':r.get('comparison')} for op,r in rows if isinstance(r,dict)]}
        print(json.dumps(payload,ensure_ascii=False),flush=True)
        assert {'simc.options','simc.preview','simc.submit','simc.compare'} <= set(operations),'missing actual model operations'
        comparison=next(r['comparison'] for op,r in reversed(rows) if op=='simc.compare' and r.get('status')=='ready')
        variant=completed_job(comparison['variantJobId'])
        req('GET','/simc/jobs/'+comparison['variantJobId'],404,headers=other)
        return comparison
    report['cases']={}
    for case,url,instruction in [
        ('fusionbolt','https://raider.io/cn/characters/cn/alar/Fusionbolt','请只把元素宗师换成 Molten Wrath，其他装备、天赋和入参不变，实际重跑并和原任务比较，告诉我是否提升。'),
        ('giannis','https://raider.io/cn/characters/cn/silver-hand/Giannis','请把唤波石换成无底袋，沿用唤波石的升级进度和装等，其他装备、天赋和入参不变，实际重跑并和原任务比较，告诉我提升多少。')]:
        source=req('POST','/simc/snapshots?view=workbench',201,json={'sourceUrl':url}).json()
        assert source['readiness']=='READY_FOR_SIMC'
        req('GET','/simc/snapshots/'+source['id'],404,headers=other)
        key='simc-exp-'+uuid4().hex
        body={'snapshotId':source['id'],'scenario':{'iterations':300,'maxTime':300,'fightStyle':'Patchwerk','desiredTargets':5,'varyCombatLength':0.2,'raidBuffs':True,'bloodlust':True}}
        job=req('POST','/simc/jobs',202,json=body,headers={**headers,'Idempotency-Key':key}).json()
        assert req('POST','/simc/jobs',202,json=body,headers={**headers,'Idempotency-Key':key}).json()['id']==job['id']
        req('GET','/simc/jobs/'+job['id'],404,headers=other)
        detail=completed_job(job['id'])
        print(json.dumps({'step':'baseline','case':case,'jobId':job['id'],'dps':detail['result']['metricValue']}),flush=True)
        report['cases'][case]=chat_check('这是我的基准模拟任务 '+job['id']+'。'+instruction,case)
    report['checks'].update(realModelExperiments=True,realSimcQueueWorkerResult=True,simcIdempotencyAndIsolation=True,effectiveConfigVerified=True)
cleanup();tokens.clear();report.update(passed=True,sessionsRevoked=True,productionIdentitiesCreated=0)
print(json.dumps(report,ensure_ascii=False),flush=True)

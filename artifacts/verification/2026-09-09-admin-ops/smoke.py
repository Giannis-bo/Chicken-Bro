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
    dsn=urlsplit(env['WOW_DATABASE_URL']);db='chickenbro_admin_candidate_20260909'
    for line in Path(env['PGPASSFILE']).read_text().splitlines():
        f=[re.sub(r'\\(.)',r'\1',v) for v in re.split(r'(?<!\\):',line)]
        if len(f)==5 and f[2]==dsn.path.lstrip('/') and f[3]==unquote(dsn.username):env['PGPASSWORD']=f[4];break
    assert env.get('PGPASSWORD')
    exists=subprocess.check_output(['sudo','-n','-u','postgres','psql','-XAt','-c',"SELECT count(*) FROM pg_database WHERE datname='"+db+"'"],text=True).strip()
    if exists=='0':subprocess.run(['sudo','-n','-u','postgres','createdb','-O',unquote(dsn.username),db],check=True,stdout=subprocess.DEVNULL)
    private=Path('/var/lib/chickenbro-admin-ops-candidate');private.mkdir(mode=0o700,exist_ok=True)
    u=pwd.getpwnam('ubuntu');os.chown(private,u.pw_uid,u.pw_gid)
    env.update(WOW_DATABASE_URL=urlunsplit(dsn._replace(path='/'+db)),WOW_APP_ENV='test',WOW_API_V2_PORT='18790',
        WOW_CHAT_WORKER_TOOL_PORT='18794',WOW_TEST_LOGIN_ENABLED='0',WOW_WORKER_V2_HEARTBEAT_PATH=str(private/'heartbeat.json'),
        WOW_CODEX_JOBS_DIR=str(private/'jobs'),WOW_WEB_COOKIE_NAME='__Host-admin-ops-session',WOW_WEB_CSRF_COOKIE_NAME='__Host-admin-ops-csrf',
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
            c.execute("INSERT INTO identity.user_identities(id,user_id,provider,app_context,provider_subject) VALUES (%s,%s,'qq',%s,%s)",(uuid4(),uid,env['WOW_QQ_APPID'],'admin-ops-isolated-'+uuid4().hex))
    else:
        owners=[r[0] for r in c.execute("SELECT user_id FROM identity.user_identities WHERE provider='qq' AND provider_subject LIKE 'simc-all-smoke-%%' ORDER BY user_id LIMIT 2").fetchall()]
        assert len(owners)==2,'dedicated prior synthetic smoke owners required'
    for uid in owners:
        t=secrets.token_urlsafe(32);tokens.append(t)
        c.execute("INSERT INTO identity.auth_sessions(token_hash,user_id,kind,expires_at) VALUES (%s,%s,'web_cookie',now()+interval '20 minutes')",(hashlib.sha256(t.encode()).hexdigest(),uid))
if a.mode=='candidate':
    env['WOW_ADMIN_USER_ID']=str(owners[0])
    u=pwd.getpwnam('ubuntu')
    for kind,command in [('worker',['-m','server.app.worker.main','--worker-id','admin-ops-candidate']),('api',['-m','uvicorn','server.app.main:app','--host','127.0.0.1','--port','18790','--log-level','warning'])]:
        log=open('/var/lib/chickenbro-admin-ops-candidate/'+kind+'.log','ab')
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
    req('GET','/admin/overview',401,headers={})
    req('GET','/admin/overview',403,headers=other)
    expected_admin = a.mode=='candidate'
    access=req('GET','/admin/access').json()
    assert access['isAdmin']==expected_admin
    if expected_admin:
        overview=req('GET','/admin/overview').json()
        assert overview['users']['total']>=2
        assert req('GET','/admin/overview').headers['cache-control']=='no-store'
        req('GET','/admin/overview?start=2020-01-01&end=2026-09-09',400)
    else:
        req('GET','/admin/overview',403)
    report['checks']['adminAuthorizationAndCache']=True
    source=req('POST','/simc/snapshots?view=workbench',201,json={'sourceUrl':'https://raider.io/cn/characters/cn/silver-hand/Giannis'}).json()
    assert source['readiness']=='READY_FOR_SIMC'
    req('GET','/simc/snapshots/'+source['id'],404,headers=other)
    key='admin-simc-'+uuid4().hex
    body={'snapshotId':source['id'],'scenario':{'iterations':300,'maxTime':300,'fightStyle':'Patchwerk','desiredTargets':1,'varyCombatLength':0.2,'raidBuffs':True,'bloodlust':True}}
    job=req('POST','/simc/jobs',202,json=body,headers={**headers,'Idempotency-Key':key}).json()
    assert req('POST','/simc/jobs',202,json=body,headers={**headers,'Idempotency-Key':key}).json()['id']==job['id']
    detail=completed_job(job['id'])
    req('GET','/simc/jobs/'+job['id'],404,headers=other)
    report['checks']['realSimc']={'jobId':job['id'],'metricValue':detail['result']['metricValue'],'isolation':True,'idempotent':True}
    picture=Image.new('RGB',(600,240),'white');ImageDraw.Draw(picture).text((40,80),'ADMIN CHECK 4729',fill='black',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',42))
    buffer=io.BytesIO();picture.save(buffer,format='PNG')
    upload=req('POST','/chat/images',201,json={'dataUrl':'data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode()},headers={**headers,'Idempotency-Key':uuid4().hex}).json()
    image_id=upload['id']
    req('GET','/chat/images/'+image_id,404,headers=other)
    conv=req('POST','/chat/conversations',201,json={'title':'运营后台发布验收'},headers={**headers,'Idempotency-Key':uuid4().hex}).json()
    path='/chat/conversations/'+conv['id'];key=uuid4().hex
    with client.stream('POST','/api/v2'+path+'/messages/stream?includeProgress=true',json={'content':'请只读出图片中的文字和数字。','imageIds':[image_id],'clientMessageId':key},headers={**headers,'Idempotency-Key':key}) as response:
        assert response.status_code==200
        first=next(json.loads(line[5:]) for line in response.iter_lines() if line.startswith('data:'))
        assert first['type']=='started'
    for _ in range(150):
        history=req('GET',path+'?includeProgress=true&includeImages=true').json()
        answers=[m for m in history['messages'] if m['role']=='assistant']
        if answers:break
        time.sleep(2)
    assert answers and '4729' in answers[-1]['content'], 'image response did not match'
    req('GET',path,404,headers=other)
    report['checks']['chatImageWorkerAndIsolation']={'runId':first['runId'],'imageReadCorrectly':True}
    if expected_admin:
        overview=req('GET','/admin/overview').json()
        assert overview['chat']['succeeded']>=1 and overview['simc']['succeeded']>=1
        report['checks']['aggregateAfterWrites']=True
cleanup();tokens.clear();report.update(passed=True,sessionsRevoked=True,productionIdentitiesCreated=0)
print(json.dumps(report,ensure_ascii=False),flush=True)

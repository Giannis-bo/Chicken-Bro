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
    private=Path('/var/lib/chickenbro-research-player-identity-candidate-20260917');private.mkdir(mode=0o700,exist_ok=True)
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
    for kind,command in [('worker',['-m','server.app.worker.main','--worker-id','research-player-identity-candidate']),('api',['-m','uvicorn','server.app.main:app','--host','127.0.0.1','--port','18890','--log-level','warning'])]:
        log=open('/var/lib/chickenbro-research-player-identity-candidate-20260917/'+kind+'.log','ab')
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
    def create(title):
        return req('POST','/chat/conversations',201,json={'title':title},headers={**headers,'Idempotency-Key':str(uuid4())}).json()['id']
    def ask(cid,prompt):
        key=str(uuid4());mid=str(uuid4());before_dirs=set(Path(env['WOW_CODEX_JOBS_DIR']).glob('*/native-tool-observations.jsonl'));started=time.monotonic()
        response=req('POST','/chat/conversations/'+cid+'/messages/stream',json={'content':prompt,'clientMessageId':mid},headers={**headers,'Idempotency-Key':key})
        with psycopg.connect(env['WOW_DATABASE_URL']) as c:
            row=c.execute("SELECT id,status,public_error_code,model_usage FROM chat.agent_runs WHERE user_id=%s AND conversation_id=%s ORDER BY started_at DESC LIMIT 1",(owners[0],cid)).fetchone()
            messages=c.execute("SELECT content FROM chat.messages WHERE conversation_id=%s AND role='assistant' ORDER BY created_at DESC LIMIT 1",(cid,)).fetchone()
            tools=c.execute("SELECT operation,result_json,request_json FROM chat.tool_results WHERE run_id=%s ORDER BY started_at",(row[0],)).fetchall()
        native=[]
        for f in set(Path(env['WOW_CODEX_JOBS_DIR']).glob('*/native-tool-observations.jsonl'))-before_dirs:
            identity=f.parent/'run-identity.json'
            if identity.is_file() and json.loads(identity.read_text()).get('runId')==str(row[0]):
                native.extend(json.loads(line) for line in f.read_text().splitlines() if line.strip())
        record={'observationBinding':'exact_run_id','elapsedSeconds':round(time.monotonic()-started,3),'nativeObservations':native,'runId':str(row[0]),'runStatus':row[1],'errorCode':row[2],'modelUsage':row[3],'finalAnswer':messages[0] if messages else '',
            'toolObservations':[{'tool':op,'status':(r or {}).get('status'),'evidenceRefs':(r or {}).get('evidenceRefs',[]),'request':request,'result':r} for op,r,request in tools],
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
    cid=create('research-player-identity:known-player-continuation')
    source = {'players':['character:us:bleeding-hollow:shadarek'] + [
        f'character:us:illidan:quota-fixture-{n}' for n in range(9)],
        'fights':['pXVZNkL2Hf8g7a6d:10'],
        'report_actors':{'pXVZNkL2Hf8g7a6d:10:472':'character:us:bleedinghollow:shadarek'}}
    with psycopg.connect(env['WOW_DATABASE_URL']) as c:
        c.execute("INSERT INTO chat.research_sessions(id,user_id,conversation_id,state,budget) VALUES (%s,%s,%s,'active',%s::jsonb)",
                  (uuid4(),owners[0],cid,json.dumps({'source':source})))
    report['fixture']={'preexistingPlayerCount':10,'syntheticConversation':True,
                       'legacyRealmSpellings':['bleeding-hollow','bleedinghollow'],
                       'note':'Nine placeholder reservations plus the already researched Shadarek; not ten actual ranking queries.'}
    prompt="继续分析已研究的 Shadarek（US Bleeding Hollow）。请实际读取 https://www.warcraftlogs.com/reports/pXVZNkL2Hf8g7a6d?fight=10&source=472 的 overview 技能伤害表，列出前三项伤害来源及数值，并简要解释已取得证据能支持的伤害构成。只查询这一个已有玩家和这场战斗，不扩展榜单，不读取事件，不运行模拟。"
    record=ask(cid,prompt);record['caseId']='known-player-at-ten'
    receipts=[t for t in record['toolObservations'] if t['tool']=='source.warcraftlogs']
    assert receipts, 'no actual WCL source call'
    assert all((t['result'] or {}).get('errorCode') not in ('RESEARCH_BUDGET_EXCEEDED','RESEARCH_TURN_BUDGET_EXCEEDED') for t in receipts)
    facts=[fact for t in receipts for fact in (t['result'] or {}).get('facts',[]) if str(fact.get('sourceId'))=='472']
    assert facts, 'no selected player result'
    report['selectedPlayerFacts']=facts
    assert any(f.get('damage') for f in facts), 'damage table missing'
    with psycopg.connect(env['WOW_DATABASE_URL']) as c:
        budget=c.execute('SELECT budget FROM chat.research_sessions WHERE user_id=%s AND conversation_id=%s',(owners[0],cid)).fetchone()[0]
        assert len(budget['source']['players'])==10, 'existing player charged twice'
    report['checks'].update(selectedPlayerSourceRead=True,damageTableReturned=True,
        playerCountRemainsTen=True,ownerIsolation=True,idempotentReplay=True)
cleanup();tokens.clear();children.clear()
(Path(__file__).parent/(a.label+'-private.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'mode':a.mode,'checks':report['checks'],'cases':len(report.get('cases',[]))}),flush=True)

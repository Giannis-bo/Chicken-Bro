"""Isolated cloud HTTP/PG process faults with deterministic model and real SimC admission.

The model double pauses after two identical submissions through the actual
Simulation application/repository. It never runs SimulationCraft. No production
records are touched; source credentials are inherited without being printed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import secrets
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from uuid import uuid4

p=argparse.ArgumentParser()
p.add_argument('--source',required=True)
p.add_argument('--database',default='chickenbro_g2_candidate_20260909')
p.add_argument('--child',choices=['api','worker'])
a=p.parse_args()
os.chdir(a.source)
sys.path.insert(0,a.source)
if not a.database.startswith('chickenbro_g2_candidate_'):
    raise RuntimeError('isolated database required')

if a.child:
    if a.child=='api':
        import uvicorn
        uvicorn.run('server.app.main:app',host='127.0.0.1',port=18790,log_level='warning')
    else:
        from server.app.platform.postgres import PostgresConnectionFactory
        from server.app.platform.config import AppSettings
        from server.app.chickenbro.worker import ChatWorker
        from server.app.chickenbro.worker_gateway import ToolRecorder
        from server.app.chickenbro.simulation_tools import SimulationToolGateway,SimulationToolContext
        from server.app.simulation.application import SimulationApplication
        from server.app.simulation.repository import PostgresSimulationRepository
        from tests.app_simulation_application_test import SimulationApplicationTest
        connect=PostgresConnectionFactory(AppSettings.from_env(os.environ)).connection
        class DeterministicModel:
            runtime_revision='codex:fault-fixture'
            def __init__(self,claim,guarded):
                fixture=SimulationApplicationTest()
                fixture.setUp()
                base=fixture.application
                self.sim=SimulationApplication(repository=PostgresSimulationRepository(guarded),
                    source_router=base._source_router,readiness_validator=base._readiness_validator,
                    compiler=base._compiler,runtime_capabilities=base._runtime_capabilities)
                self.recorder=ToolRecorder(guarded,claim['run_id'])
            def stream_for_chat(self,*,principal,conversation_id,run_id,**kwargs):
                gateway=SimulationToolGateway(self.sim)
                token=gateway.issue_capability(SimulationToolContext(principal,conversation_id,run_id))
                try:
                    prepared=gateway.execute(token,'prepare',{'sourceUrl':'https://raider.io/characters/us/area-52/Stormsample'})
                    args={'snapshotId':prepared['snapshotId'],'scenario':{}}
                    one=self.recorder.execute('simc.submit',args,lambda:gateway.execute(token,'submit',args))
                    two=self.recorder.execute('simc.submit',args,lambda:gateway.execute(token,'submit',args))
                    assert one['jobId']==two['jobId']
                    yield {'type':'progress','text':'已记录同一模拟任务'}
                    time.sleep(12)
                    yield {'type':'completed','text':'隔离测试的唯一回答'}
                finally:
                    gateway.revoke(token)
        worker=ChatWorker(connect,codex_factory=DeterministicModel,lease_seconds=3)
        while True:
            if not worker.run_once():time.sleep(.1)
    raise SystemExit(0)

pid=subprocess.check_output(['systemctl','show','chickenbro-api.service','-p','MainPID','--value'],text=True).strip()
env=dict(e.split('=',1) for e in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in e)
from urllib.parse import urlsplit,urlunsplit
dsn=urlsplit(env['WOW_DATABASE_URL'])
# Reuse only the configured production role credential for its isolated DB.
# libpq's existing passfile is database-scoped; never change that file or log it.
import re
from urllib.parse import unquote
for line in Path(env['PGPASSFILE']).read_text().splitlines():
    fields=re.split(r'(?<!\\):',line)
    fields=[re.sub(r'\\(.)',r'\1',field) for field in fields]
    if len(fields)==5 and fields[2]==dsn.path.lstrip('/') and fields[3]==unquote(dsn.username):
        env['PGPASSWORD']=fields[4]
        break
if 'PGPASSWORD' not in env:
    raise RuntimeError('configured database role credential unavailable')
env.update(WOW_DATABASE_URL=urlunsplit(dsn._replace(path='/'+a.database)),WOW_APP_ENV='test',
    WOW_API_V2_PORT='18790',WOW_CHAT_DURABLE_ENABLED='1',WOW_TEST_LOGIN_ENABLED='0',
    WOW_WORKER_V2_HEARTBEAT_PATH='/var/lib/chickenbro/g2-fault-worker-heartbeat.json',PYTHONPATH=a.source)
env['WOW_QQ_REDIRECT_URI']=env.get('WOW_WEB_ORIGIN','https://www.chickenbro.cloud').rstrip('/')+'/test/api/v2/auth/qq/callback'
os.environ.update(env)
from server.app.platform.postgres import PostgresConnectionFactory
from server.app.platform.config import AppSettings
connect=PostgresConnectionFactory(AppSettings.from_env(env)).connection
import importlib
with connect() as conn:
    importlib.import_module('server.migrations.product.apply').apply_product_migrations(conn,Path(a.source)/'server/migrations/product')
u=pwd.getpwnam('ubuntu')
children=[]
def launch(kind):
    logfile=open('/var/tmp/g2-fault-'+kind+'.log','ab')
    child=subprocess.Popen(['/opt/chickenbro-runtime/bin/python',__file__,'--source',a.source,'--database',a.database,'--child',kind],
        cwd=a.source,env=env,user=u.pw_uid,group=u.pw_gid,start_new_session=True,stdout=logfile,stderr=logfile)
    children.append(child)
    return child
def kill(child):
    if child.poll() is None:
        os.killpg(child.pid,signal.SIGKILL)
        child.wait(timeout=10)
def wait(predicate,seconds=25):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        try:
            result=predicate()
            if result:return result
        except (HTTPError,OSError):pass
        time.sleep(.2)
    raise RuntimeError('bounded fault verification condition timed out')

owner,other=uuid4(),uuid4()
mini,web,other_token=[secrets.token_urlsafe(32) for _ in range(3)]
with connect() as conn:
    conn.execute('INSERT INTO identity.users(id) VALUES (%s),(%s)',(owner,other))
    for token,user,kind in [(mini,owner,'web_cookie'),(web,owner,'web_cookie'),(other_token,other,'web_cookie')]:
        conn.execute("INSERT INTO identity.auth_sessions(token_hash,user_id,kind,expires_at) VALUES (%s,%s,%s,now()+interval '15 minutes')",(hashlib.sha256(token.encode()).hexdigest(),user,kind))
def request(path,body=None,key=None,transport='mini'):
    headers={'Content-Type':'application/json','Host':'www.chickenbro.cloud','Origin':'https://www.chickenbro.cloud','X-CSRF-Token':'g2-candidate-csrf'}
    if transport=='web':headers['Cookie']='__Host-chickenbro-session='+web
    else:headers['Cookie']='__Host-chickenbro-session='+(other_token if transport=='other' else mini)
    headers['Cookie']+='; __Host-chickenbro-csrf=g2-candidate-csrf'
    if key:headers['Idempotency-Key']=key
    return urlopen(Request('http://127.0.0.1:18790/api/v2'+path,headers=headers,
        data=json.dumps(body).encode() if body is not None else None),timeout=20)
def api(*args,**kwargs):
    with request(*args,**kwargs) as response:return json.load(response)
def count_jobs():
    with connect() as conn:return conn.execute('SELECT count(*) FROM simc.simulation_jobs WHERE user_id=%s',(owner,)).fetchone()[0]
def start(message):
    conv=api('/chat/conversations',{'title':'G2 isolated process fault'},key=str(uuid4()))['id']
    path='/chat/conversations/'+conv
    body={'content':message,'clientMessageId':str(uuid4())}
    key=str(uuid4())
    with request(path+'/messages/stream?includeProgress=true',body,key=key) as response:
        while True:
            line=response.readline()
            if line.startswith(b'data:'):
                first=json.loads(line[5:]);break
    assert first['type']=='started'
    return path,body,key,first['runId']
try:
    api_process=launch('api')
    wait(lambda:api('/chat/conversations'))
    # Admission before the worker exists survives an API crash.
    path,body,key,run_id=start('API重启验证')
    assert count_jobs()==0
    kill(api_process)
    api_process=launch('api')
    wait(lambda:api('/chat/conversations'))
    worker_process=launch('worker')
    wait(lambda:count_jobs()==1)
    try:
        api(path+'/messages/stream',{'content':'互斥检查','clientMessageId':str(uuid4())},key=str(uuid4()))
        raise RuntimeError('account guard missing')
    except HTTPError as error:
        assert error.code==409 and json.load(error)['error']['code']=='CHAT_ACCOUNT_BUSY'
    # Restart while the worker has already made its durable side effect.
    kill(api_process)
    api_process=launch('api')
    def answer():
        items=api(path+'?includeProgress=true',transport='web')['messages']
        return next((x for x in items if x['role']=='assistant'),None)
    reply=wait(answer)
    assert reply['content']=='隔离测试的唯一回答'
    with request(path+'/messages/stream',body,key=key) as response:
        assert 'event: completed' in response.read().decode()
    assert count_jobs()==1
    try:api(path,transport='other');raise RuntimeError('isolation missing')
    except HTTPError as error:assert error.code==404
    print(json.dumps({'phase':'api_restart','passed':True,'pendingAdmissionSurvived':True,'activeGenerationSurvived':True,
        'singleAnswer':True,'singleSimulationSubmission':True,'idempotentReplay':True,'ownerIsolation':True,'accountExclusion':True}),flush=True)
    path2,_,_,run2=start('Worker终止验证')
    wait(lambda:count_jobs()==2)
    # A committed simulation can become visible before its tool receipt commits.
    # This scenario deliberately interrupts after the durable receipt.
    def recorded():
        with connect() as conn:
            return conn.execute("SELECT count(*) FROM chat.tool_results WHERE run_id=%s AND operation='simc.submit' AND state='completed'",(run2,)).fetchone()[0]==2
    wait(recorded)
    kill(worker_process)
    # API resolves expired execution even while worker is still stopped.
    def failed():
        items=api(path2+'?includeProgress=true',transport='web')['messages']
        return next((x for x in items if x.get('progress',{}).get('status')=='failed'),None)
    wait(failed,10)
    worker_process=launch('worker')
    time.sleep(4)
    assert count_jobs()==2
    with connect() as conn:
        state=conn.execute('SELECT status,assistant_message_id FROM chat.agent_runs WHERE id=%s',(run2,)).fetchone()
        receipts=conn.execute("SELECT count(DISTINCT result_json->>'jobId') FROM chat.tool_results WHERE run_id=%s AND operation='simc.submit'",(run2,)).fetchone()[0]
    assert state==('failed',None) and receipts==1
    print(json.dumps({'phase':'worker_killed','passed':True,'failedWithoutWorkerRestart':True,
        'restartedWorkerDidNotReplay':True,'noDuplicateAnswer':True,'noDuplicateSimulation':True,'simulationExecution':'not_run'}),flush=True)
finally:
    for child in children:kill(child)
    with connect() as conn:
        conn.execute('UPDATE identity.auth_sessions SET revoked_at=now() WHERE user_id IN (%s,%s)',(owner,other))
    print(json.dumps({'database':a.database,'source':str(Path(a.source).resolve()),'childrenStopped':True}),flush=True)

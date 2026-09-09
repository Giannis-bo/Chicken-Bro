"""Real model/WCL through isolated PostgreSQL, API and independent Worker.

Only aggregate evidence is printed. The source conversation and resulting
answers remain private on the cloud host. API faults never target production.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import signal
import subprocess
import sys
import time
from urllib.parse import urlsplit,urlunsplit,unquote
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from uuid import uuid4

p=argparse.ArgumentParser()
p.add_argument('--source',required=True)
p.add_argument('--case',choices=['original','similar','short','image'],default='original')
p.add_argument('--database',default='chickenbro_g2_candidate_live_20260909')
a=p.parse_args()
if not a.database.startswith('chickenbro_g2_candidate_'):
    raise RuntimeError('isolated database required')
os.chdir(a.source)
sys.path.insert(0,a.source)
pid=subprocess.check_output(['systemctl','show','chickenbro-api.service','-p','MainPID','--value'],text=True).strip()
env=dict(e.split('=',1) for e in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in e)
dsn=urlsplit(env['WOW_DATABASE_URL'])
for line in Path(env['PGPASSFILE']).read_text().splitlines():
    fields=[re.sub(r'\\(.)',r'\1',x) for x in re.split(r'(?<!\\):',line)]
    if len(fields)==5 and fields[2]==dsn.path.lstrip('/') and fields[3]==unquote(dsn.username):
        env['PGPASSWORD']=fields[4]
        break
if 'PGPASSWORD' not in env:raise RuntimeError('configured role credential unavailable')
env.update(WOW_DATABASE_URL=urlunsplit(dsn._replace(path='/'+a.database)),WOW_APP_ENV='test',
    WOW_API_V2_PORT='18790',WOW_CHAT_WORKER_TOOL_PORT='28794',WOW_CHAT_DURABLE_ENABLED='1',WOW_TEST_LOGIN_ENABLED='0',
    WOW_WORKER_V2_HEARTBEAT_PATH='/var/lib/chickenbro/g2-live-worker-heartbeat.json',PYTHONPATH=a.source)
env['WOW_QQ_REDIRECT_URI']=env.get('WOW_WEB_ORIGIN','https://www.chickenbro.cloud').rstrip('/')+'/test/api/v2/auth/qq/callback'
os.environ.update(env)
from server.app.platform.postgres import PostgresConnectionFactory
from server.app.platform.config import AppSettings
connect=PostgresConnectionFactory(AppSettings.from_env(env)).connection
with connect() as conn:
    importlib.import_module('server.migrations.product.apply').apply_product_migrations(conn,Path(a.source)/'server/migrations/product')

sql="""BEGIN READ ONLY; SELECT json_agg(x ORDER BY x.created_at,x.id) FROM (
 SELECT m.id,m.role,m.content,m.created_at FROM chat.messages m
 JOIN chat.agent_runs r ON r.conversation_id=m.conversation_id AND r.user_id=m.user_id
 JOIN chat.messages q ON q.id=r.user_message_id
 WHERE r.id::text LIKE '3a92aaf7%' AND m.created_at<=q.created_at
 ORDER BY m.created_at DESC,m.id DESC LIMIT 20) x; COMMIT;"""
history=json.loads(subprocess.check_output(['sudo','-n','-u','postgres','psql','-X','-qAt','-d','chickenbro_prod','-v','ON_ERROR_STOP=1'],input=sql,text=True))
message=history[-1]['content'][:4000]
if a.case=='similar':
    message='请基于上面的同一场战斗，复盘奶骑的美德与鸣钟衔接、血线危险窗口和主要治疗技能时机，给出最值得改进的三点。区分已核验事实与尚缺证据，不要把资源溢出直接换算成有效治疗损失。'
if a.case in ('short','image'):
    history=[]
    message='请查询国服凤凰之神 Fusionbolt 的职业和专精，简短回答。'
u=pwd.getpwnam('ubuntu')
children=[]
def launch(kind):
    command=(['-m','uvicorn','server.app.main:app','--host','127.0.0.1','--port','18790','--log-level','warning']
        if kind=='api' else ['-m','server.app.worker.main','--worker-id','g2-isolated-worker'])
    log=open('/var/tmp/g2-real-'+kind+'.log','ab')
    child=subprocess.Popen(['/opt/chickenbro-runtime/bin/python',*command],cwd=a.source,env=env,
        user=u.pw_uid,group=u.pw_gid,start_new_session=True,stdout=log,stderr=log)
    children.append(child)
    return child
def kill(child):
    if child.poll() is None:
        os.killpg(child.pid,signal.SIGKILL)
        child.wait(timeout=10)
def wait(predicate,seconds):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        try:
            result=predicate()
            if result:return result
        except (HTTPError,OSError):pass
        time.sleep(.5)
    raise RuntimeError('real Candidate bounded condition timed out')
owner,other=uuid4(),uuid4()
mini,web,other_token=[secrets.token_urlsafe(32) for _ in range(3)]
with connect() as conn:
    conn.execute('INSERT INTO identity.users(id) VALUES (%s),(%s)',(owner,other))
    for uid in (owner,other):
        conn.execute("INSERT INTO identity.user_identities(id,user_id,provider,app_context,provider_subject) VALUES (%s,%s,'qq',%s,%s)",(uuid4(),uid,env['WOW_QQ_APPID'],'g2-synthetic-'+uuid4().hex))
    for token,user,kind in [(mini,owner,'web_cookie'),(web,owner,'web_cookie'),(other_token,other,'web_cookie')]:
        conn.execute("INSERT INTO identity.auth_sessions(token_hash,user_id,kind,expires_at) VALUES (%s,%s,%s,now()+interval '20 minutes')",(hashlib.sha256(token.encode()).hexdigest(),user,kind))
def request(path,body=None,key=None,transport='mini'):
    headers={'Content-Type':'application/json','Host':'www.chickenbro.cloud','Origin':'https://www.chickenbro.cloud','X-CSRF-Token':'g2-candidate-csrf'}
    if transport=='web':headers['Cookie']='__Host-chickenbro-session='+web
    else:headers['Cookie']='__Host-chickenbro-session='+(other_token if transport=='other' else mini)
    headers['Cookie']+='; __Host-chickenbro-csrf=g2-candidate-csrf'
    if key:headers['Idempotency-Key']=key
    return urlopen(Request('http://127.0.0.1:18790/api/v2'+path,headers=headers,
        data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None),timeout=30)
def api(*args,**kwargs):
    with request(*args,**kwargs) as response:return json.load(response)
run_id=None
try:
    worker=launch('worker')
    api_process=launch('api')
    wait(lambda:api('/chat/conversations'),25)
    conversation=api('/chat/conversations',{'title':'G2 private complex replay'},key=str(uuid4()))['id']
    path='/chat/conversations/'+conversation
    with connect() as conn:
        for old in history[:-1]:
            conn.execute('INSERT INTO chat.messages(id,conversation_id,user_id,role,content,created_at) VALUES (%s,%s,%s,%s,%s,%s)',
                (uuid4(),conversation,owner,old['role'],old['content'][:4000],old['created_at']))
    body={'content':message,'clientMessageId':str(uuid4())}
    if a.case=='image':
        import io,base64
        from PIL import Image,ImageDraw,ImageFont
        code=secrets.token_hex(4).upper()
        pic=Image.new('RGB',(850,250),'white')
        ImageDraw.Draw(pic).text((30,60),code,fill='black',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',100))
        data=io.BytesIO();pic.save(data,format='PNG')
        uploaded=api('/chat/images',{'dataUrl':'data:image/png;base64,'+base64.b64encode(data.getvalue()).decode()},key=str(uuid4()))
        body.update(content='这是魔兽插件报错截图。只抄出八位错误码。',imageIds=[uploaded['id']])
    key=str(uuid4())
    started=time.monotonic()
    with request(path+'/messages/stream?includeProgress=true',body,key=key) as response:
        while True:
            line=response.readline()
            if not line:raise RuntimeError('missing admission event')
            if line.startswith(b'data:'):
                first=json.loads(line[5:]);break
    run_id=first['runId']
    def tool_started():
        with connect() as conn:
            return conn.execute('SELECT count(*) FROM chat.tool_results WHERE run_id=%s',(run_id,)).fetchone()[0]>0
    if a.case!='image':wait(tool_started,120)
    else:time.sleep(2)
    with connect() as conn:
        assert conn.execute('SELECT status FROM chat.agent_runs WHERE id=%s',(run_id,)).fetchone()[0]=='streaming'
    kill(api_process)
    api_process=launch('api')
    wait(lambda:api('/chat/conversations'),25)
    try:
        api(path+'/messages/stream',{'content':'并发检查','clientMessageId':str(uuid4())},key=str(uuid4()))
        raise RuntimeError('account guard missing')
    except HTTPError as error:assert error.code==409
    print(json.dumps({'phase':'real_generation_api_restarted','case':a.case,'runId':run_id}),flush=True)
    def terminal():
        with connect() as conn:
            row=conn.execute('SELECT status,assistant_message_id,public_error_code FROM chat.agent_runs WHERE id=%s',(run_id,)).fetchone()
            return row if row[0]!='streaming' else None
    state=wait(terminal,500)
    elapsed=time.monotonic()-started
    with connect() as conn:
        calls=conn.execute('SELECT operation,state,extract(epoch from started_at),extract(epoch from finished_at),octet_length(result_json::text) FROM chat.tool_results WHERE run_id=%s ORDER BY started_at',(run_id,)).fetchall()
    summed=sum(float(c[3]-c[2]) for c in calls if c[3] is not None)
    end=union=0
    for _,_,begin,finish,_ in calls:
        if finish is not None:
            union+=max(0,float(finish)-max(end,float(begin)))
            end=max(end,float(finish))
    evidence={'case':a.case,'source':str(Path(a.source).resolve()),'database':a.database,'runId':run_id,
        'terminal':state[0],'errorCode':state[2],'seconds':elapsed,'toolWallSeconds':union,
        'toolSumSeconds':summed,'nonToolWallSeconds':elapsed-union,'calls':len(calls),
        'apiRestartDuringGeneration':True,'model':'real','wcl':'real'}
    if state[0]=='succeeded':
        mini_view=api(path+'?includeProgress=true')
        web_view=api(path+'?includeProgress=true',transport='web')
        assert mini_view==web_view
        answers=[m for m in web_view['messages'] if m['id']==str(state[1])]
        assert len(answers)==1 and answers[0]['content']
        if a.case=='image':assert code in answers[0]['content'],'actual image code was not recognized'
        try:api(path,transport='other');raise RuntimeError('owner isolation missing')
        except HTTPError as error:assert error.code==404
        with request(path+'/messages/stream',body,key=key) as response:
            assert 'event: completed' in response.read().decode()
        output=Path('/var/tmp/chickenbro-g2-real-'+a.case+'-'+run_id)
        output.mkdir(mode=0o700)
        (output/'answer.txt').write_text(answers[0]['content'])
        evidence.update(sharedHistory=True,ownerIsolation=True,idempotentReplay=True,answerChars=len(answers[0]['content']))
        (output/'metrics.json').write_text(json.dumps(evidence,indent=2))
    print(json.dumps(evidence),flush=True)
    assert state[0]=='succeeded','real model failed; no business acceptance'
finally:
    for child in children:kill(child)
    with connect() as conn:
        conn.execute('UPDATE identity.auth_sessions SET revoked_at=now() WHERE user_id IN (%s,%s)',(owner,other))

"""Real HTTP disconnect + DB terminal + shared history and source/model acceptance."""
import hashlib,json,os,pwd,secrets,subprocess,sys,time,uuid
from pathlib import Path
from datetime import datetime,timedelta,timezone
from urllib.request import Request,urlopen
from urllib.error import HTTPError
root,base,mode=sys.argv[1:4]
pid=subprocess.check_output(['systemctl','show','chickenbro-api.service','-p','MainPID','--value'],text=True).strip()
env=dict(e.split('=',1) for e in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in e)
os.environ.update(env);sys.path.insert(0,root)
from server.app.platform.config import AppSettings
from server.app.platform.postgres import PostgresConnectionFactory
factory=PostgresConnectionFactory(AppSettings.from_env(os.environ)).connection
child=None
if mode=='candidate':
 child_env=dict(env,WOW_API_V2_PORT='8791');u=pwd.getpwnam('ubuntu')
 child=subprocess.Popen(['/opt/chickenbro-runtime/bin/python','-m','uvicorn','server.app.main:app','--host','127.0.0.1','--port','8791'],cwd=root,env=child_env,stdout=subprocess.DEVNULL,stderr=open('/tmp/chickenbro-badcase-candidate.log','w'),user=u.pw_uid,group=u.pw_gid,start_new_session=True)
 for _ in range(30):
  try:
   with urlopen(base+'/health/readiness',timeout=3) as r:
    if json.load(r).get('status')=='ready':break
  except Exception:time.sleep(1)
 else:
  child.terminate()
  try:
   with urlopen(base+'/health/readiness',timeout=3) as r:print(json.dumps({'candidateReadiness':json.load(r)}),flush=True)
  except Exception as e:print(json.dumps({'candidateReadinessError':type(e).__name__}),flush=True)
  raise RuntimeError('candidate_not_ready')
owner,other=uuid.uuid4(),uuid.uuid4();mini,web,other_token=[secrets.token_urlsafe(32) for _ in range(3)]
tokens=[(mini,owner,'mini_bearer'),(web,owner,'web_cookie'),(other_token,other,'mini_bearer')]
now=datetime.now(timezone.utc);conversations=[]
with factory() as c:
 c.execute("INSERT INTO identity.users(id,display_name) VALUES (%s,'Badcase release acceptance'),(%s,'Badcase isolation acceptance')",(owner,other))
 for token,user,kind in tokens:
  c.execute("INSERT INTO identity.auth_sessions(token_hash,user_id,kind,issued_at,expires_at,metadata_json) VALUES(%s,%s,%s,%s,%s,%s::jsonb)",(hashlib.sha256(token.encode()).hexdigest(),user,kind,now,now+timedelta(minutes=20),json.dumps({'purpose':'badcase_release_acceptance'})))
def request(path,body=None,transport='mini',key=None):
 headers={'Content-Type':'application/json'}
 if transport=='web':headers['Cookie']='__Host-chickenbro-session='+web
 else:headers['Authorization']='Bearer '+(other_token if transport=='other' else mini)
 if key:headers['Idempotency-Key']=key
 return urlopen(Request(base+path,data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,headers=headers),timeout=240)
def api(*args,**kwargs):
 with request(*args,**kwargs) as r:return json.load(r)
try:
 conv=api('/chat/conversations',{'title':'Badcase release regression'},key='release-create-'+str(uuid.uuid4()))['id'];conversations.append(conv)
 path='/chat/conversations/'+conv
 body={'content':'请查询国服凤凰之神 Fusionbolt 的职业和专精，简短回答。','clientMessageId':'release-detach'};key='release-detach-'+str(uuid.uuid4());start=time.monotonic()
 response=request(path+'/messages/stream?includeProgress=true',body,key=key)
 first=None
 while True:
  line=response.readline()
  if not line:raise RuntimeError('missing_started')
  if line.startswith(b'data:'):
   first=json.loads(line[5:]);break
 assert first['type']=='started'
 response.close()
 try:
  api(path+'/messages/stream',{'content':'你好','clientMessageId':'release-busy'},key='release-busy-'+str(uuid.uuid4()))
  raise RuntimeError('account_guard_missing')
 except HTTPError as e:
  assert e.code==409 and json.load(e)['error']['code']=='CHAT_ACCOUNT_BUSY'
 print(json.dumps({'phase':'disconnected','mode':mode,'runId':first['runId'],'accountBusyVerified':True}),flush=True)
 answer=None
 deadline=time.monotonic()+230
 while time.monotonic()<deadline:
  detail=api(path+'?includeProgress=true',transport='web')
  answers=[m for m in detail['messages'] if m['role']=='assistant']
  if answers:
   answer=answers[-1];break
  if any((m.get('progress') or {}).get('status')=='failed' for m in detail['messages']):raise RuntimeError('detached_run_failed')
  time.sleep(2)
 assert answer and ('萨' in answer['content'] or 'Shaman' in answer['content'])
 with factory() as c:
  row=c.execute('SELECT status,assistant_message_id FROM chat.agent_runs WHERE id=%s',(first['runId'],)).fetchone()
  assert row[0]=='succeeded' and str(row[1])==answer['id']
 try:api(path,transport='other');raise RuntimeError('owner_isolation_missing')
 except HTTPError as e:assert e.code==404
 with request(path+'/messages/stream',body,key=key) as r:
  replay=r.read().decode()
  assert 'event: completed' in replay
 assert len([m for m in api(path)['messages'] if m['role']=='assistant'])==1
 from server.app.chickenbro.source_gateway import ServerConfiguredSourceQuery
 sources=ServerConfiguredSourceQuery()
 discovery=sources.query('warcraftlogs_character','character',{'name':'桃花别死','realm':'阿古斯','region':'cn','limit':2})
 assert discovery['status']=='source_reference' and discovery['facts'][0]['reports']
 report=discovery['facts'][0]['reports'][0]['url']
 metadata=sources.query('warcraftlogs',report+'?type=summary')
 assert metadata['status']=='source_reference' or metadata['status']=='verified',metadata['status']
 assert metadata['facts'], 'no_report_facts'
 # One independent short G3 behavioral smoke after release rules are loaded.
 with request(path+'/messages/stream',{'content':'奶骑复盘只有9点圣能溢出记录，没有血线、承伤、治疗明细。能确定因此损失了三次有效治疗吗？','clientMessageId':'release-g3'},key='release-g3-'+str(uuid.uuid4())) as r:
  frames=r.read().decode();completed=[json.loads(l[5:]) for l in frames.splitlines() if l.startswith('data:') and json.loads(l[5:]).get('type')=='completed']
 assert completed and completed[-1]['text']
 print(json.dumps({'status':'business_smoke_passed','mode':mode,'seconds':round(time.monotonic()-start,2),'disconnectedRunSucceeded':True,'webHistoryMatches':True,'otherOwnerDenied':True,'idempotentReplayNoDuplicate':True,'g1ReportStatus':metadata['status'],'g5DiscoveryStatus':discovery['status'],'answer':answer['content'],'g3Answer':completed[-1]['text']},ensure_ascii=False),flush=True)
finally:
 with factory() as c:
  for token,_,_ in tokens:c.execute('UPDATE identity.auth_sessions SET revoked_at=now() WHERE token_hash=%s',(hashlib.sha256(token.encode()).hexdigest(),))
  c.execute("UPDATE identity.users SET status='disabled',updated_at=now() WHERE id IN (%s,%s)",(owner,other))
  for conv in conversations:c.execute("UPDATE chat.conversations SET status='archived' WHERE id=%s AND NOT EXISTS (SELECT 1 FROM chat.agent_runs WHERE conversation_id=%s AND status='streaming')",(conv,conv))
 if child:
  # Only stop once any accepted background request has finished or failed.
  with factory() as c:active=c.execute("SELECT count(*) FROM chat.agent_runs WHERE user_id=%s AND status='streaming'",(owner,)).fetchone()[0]
  if active:print(json.dumps({'candidatePid':child.pid,'cleanup':'left_running_for_active_generation'}),flush=True)
  else:child.terminate();child.wait(timeout=30)

"""Production smoke with two newly created isolated verification owners."""
import hashlib,json,secrets,sys,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
import httpx,psycopg
ROOT=Path('/var/lib/chickenbro/releases/poe2-20260921')
sys.path.insert(0,'/opt/chickenbro')
from server.app.identity.repository import PostgresIdentityRepository

environment=json.loads((ROOT/'private-environments.json').read_text())['chickenbro-api']
def connect():return psycopg.connect(environment['WOW_DATABASE_URL'],passfile=environment.get('PGPASSFILE'))
def save(name,data):
 p=ROOT/name;p.write_text(json.dumps(data,ensure_ascii=False,indent=2));p.chmod(0o600)
def packet(r,status=200):
 assert r.status_code==status, f'HTTP {r.status_code}: {r.text[:150]}'
 return r.json()
session_file=ROOT/'private-smoke-sessions.json'
rows=json.loads(session_file.read_text()) if session_file.exists() else {}
for name in ('A','B'):
 if name not in rows:
  user=uuid4();token=secrets.token_urlsafe(40);csrf=secrets.token_urlsafe(32)
  with connect() as conn:conn.execute('INSERT INTO identity.users(id,display_name) VALUES (%s,%s)',(user,'POE2 发布验证 '+name))
  PostgresIdentityRepository(connect).issue_auth_session(token_hash=hashlib.sha256(token.encode()).hexdigest(),user_id=user,kind='web_cookie',expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
  rows[name]={'token':token,'csrf':csrf,'userId':str(user)}
 # Reserved release verification identity, never an actual QQ provider account.
 with connect() as conn:
  conn.execute("INSERT INTO identity.user_identities(id,user_id,provider,app_context,provider_subject,profile_json) VALUES (%s,%s,'qq',%s,%s,'{}'::jsonb) ON CONFLICT DO NOTHING",(uuid4(),rows[name]['userId'],environment['WOW_QQ_APPID'],'poe2-release-smoke-'+rows[name]['userId']))
save('private-smoke-sessions.json',rows)
ids=[row['userId'] for row in rows.values()]
def client(row):return httpx.Client(base_url='http://127.0.0.1:8790/api/v2',trust_env=False,timeout=90,headers={'Host':'www.chickenbro.cloud','Origin':'https://www.chickenbro.cloud','Cookie':f'__Host-chickenbro-session={row["token"]}; __Host-chickenbro-csrf={row["csrf"]}','X-CSRF-Token':row['csrf']})
a,b=client(rows['A']),client(rows['B'])
packet(a.get('/me'));packet(b.get('/me'))
xml=Path('/opt/chickenbro-candidates/poe2-20260918/evidence/fixtures/build-1.xml').read_text()
build=packet(a.post('/poe2/builds',json={'source':xml,'title':'发布验证 · 火球构筑'}),201)
baseline=packet(a.get('/poe2/jobs',params={'buildId':build['id']}))['items'][0]
assert baseline['status']=='succeeded' and baseline['result']['stats']['Life']>0
job=packet(a.post('/poe2/jobs',json={'buildId':build['id'],'changes':{'level':95},'idempotencyKey':str(uuid4())}),202)
for _ in range(60):
 job=packet(a.get('/poe2/jobs/'+job['id']))
 if job['status'] in ('succeeded','failed'):break
 time.sleep(1)
assert job['status']=='succeeded',job.get('errorCode')
comparison=packet(a.post('/poe2/compare',json={'jobIds':[baseline['id'],job['id']]}))
assert 'Life' in comparison['metrics']
tree=packet(a.get('/poe2/builds/'+build['id']+'/tree'));assert tree['nodes']
export=packet(a.get('/poe2/builds/'+build['id']+'/export'))
save('private-build-code.json',{'code':export['exportCode']})
assert b.get('/poe2/builds/'+build['id']).status_code==404
assert b.post('/poe2/builds/'+build['id']+'/delete',json={}).status_code==404
assert b.get('/poe2/jobs/'+job['id']).status_code==404
assert httpx.get('http://127.0.0.1:8790/api/v2/poe2/builds',trust_env=False).status_code==401
runtime=packet(a.get('/simc/runtime'))
conv=packet(a.post('/chat/conversations',json={'game':'poe2','title':'POE2 正式发布验证'},headers={'Idempotency-Key':str(uuid4())}),201)['id']
start=time.monotonic()
r=a.post('/chat/conversations/'+conv+'/messages/stream',json={'content':f'构筑 ID：{build["id"]}。把等级调整到95级后生命有什么变化？请用计算结果比较。','clientMessageId':str(uuid4())},headers={'Idempotency-Key':str(uuid4())},timeout=420)
assert r.status_code==200
save('private-chat.json',packet(a.get('/chat/conversations/'+conv,params={'includeProgress':'true'})))
detail=json.loads((ROOT/'private-chat.json').read_text());answers=[m['content'] for m in detail['messages'] if m['role']=='assistant'];assert answers and '生命' in answers[-1]
report={'passed':True,'buildId':build['id'],'baselineJobId':baseline['id'],'candidateJobId':job['id'],'conversationId':conv,'verificationOwners':ids,'engineVersion':job['result']['engineVersion'],'treeNodes':len(tree['nodes']),'checks':{'realImport':True,'realWorkerCalculation':True,'compare':True,'tree':True,'export':True,'ownerIsolation':True,'anonymousDenied':True,'chatAnswer':True,'wowRuntimeReadable':True},'chatSeconds':round(time.monotonic()-start,1)}
save('business.json',report);print(json.dumps({k:v for k,v in report.items() if k!='verificationOwners'}))

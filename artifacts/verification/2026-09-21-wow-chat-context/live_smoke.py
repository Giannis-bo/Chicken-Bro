"""Real production Chat to SimC with two dedicated verification identities."""
import hashlib,json,secrets,sys,time,subprocess
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
import httpx,psycopg
ROOT=Path('/var/lib/chickenbro/releases/wow-chat-context-20260921')
sys.path.insert(0,'/opt/chickenbro')
from server.app.identity.repository import PostgresIdentityRepository
pid=subprocess.check_output(['systemctl','show','chickenbro-api','-p','MainPID','--value'],text=True).strip()
env=dict(x.split('=',1) for x in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in x)
def connect():return psycopg.connect(env['WOW_DATABASE_URL'],passfile=env.get('PGPASSFILE'))
def save(name,data):
 p=ROOT/name;p.write_text(json.dumps(data,ensure_ascii=False,indent=2));p.chmod(0o600)
def packet(r,status=200):
 assert r.status_code==status, f'HTTP {r.status_code}'
 return r.json()
rows=[]
for label in ('A','B'):
 user=uuid4();token=secrets.token_urlsafe(40);csrf=secrets.token_urlsafe(32)
 with connect() as c:
  c.execute('INSERT INTO identity.users(id,display_name) VALUES (%s,%s)',(user,'WoW Chat 修复验证 '+label))
  c.execute("INSERT INTO identity.user_identities(id,user_id,provider,app_context,provider_subject,profile_json) VALUES (%s,%s,'qq',%s,%s,'{}'::jsonb)",(uuid4(),user,env['WOW_QQ_APPID'],'wow-chat-repair-smoke-'+str(user)))
 PostgresIdentityRepository(connect).issue_auth_session(token_hash=hashlib.sha256(token.encode()).hexdigest(),user_id=user,kind='web_cookie',expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
 rows.append({'token':token,'csrf':csrf,'userId':str(user)})
save('private-sessions.json',rows)
def client(row):return httpx.Client(base_url='https://www.chickenbro.cloud/api/v2',timeout=90,headers={'Origin':'https://www.chickenbro.cloud','Cookie':f'__Host-chickenbro-session={row["token"]}; __Host-chickenbro-csrf={row["csrf"]}','X-CSRF-Token':row['csrf']})
a,b=map(client,rows)
try:
 packet(a.get('/me'));packet(b.get('/me'))
 source=packet(a.post('/simc/snapshots',json={'sourceUrl':'https://raider.io/cn/characters/cn/silver-hand/Giannis'}),201)
 assert source['readiness']=='READY_FOR_SIMC'
 conv=packet(a.post('/chat/conversations',json={'game':'wow','title':'WoW Chat 修复验证'},headers={'Idempotency-Key':str(uuid4())}),201)['id']
 prompt=f'这是一次链路验证。使用我的现有快照 ID {source["id"]}，准备并提交一次常规单目标 Patchwerk 模拟，iterations=8，其他默认。不查外部资料，不再导入角色，不做方案对比。等待任务完成，告诉我这次 DPS 和任务 ID。'
 started=time.monotonic()
 response=a.post('/chat/conversations/'+conv+'/messages/stream',json={'content':prompt,'clientMessageId':str(uuid4())},headers={'Idempotency-Key':str(uuid4())},timeout=420)
 assert response.status_code==200
 detail=packet(a.get('/chat/conversations/'+conv,params={'includeProgress':'true'}));save('private-chat.json',detail)
 answers=[m['content'] for m in detail['messages'] if m['role']=='assistant'];assert answers
 with connect() as c:
  runs=c.execute('SELECT id,status,public_error_code FROM chat.agent_runs WHERE conversation_id=%s ORDER BY started_at',(conv,)).fetchall()
  assert runs and runs[-1][1]=='succeeded',[(str(x[0]),x[1],x[2]) for x in runs]
  calls=c.execute('SELECT operation,state FROM chat.tool_results WHERE run_id=%s ORDER BY started_at',(runs[-1][0],)).fetchall()
  jobs=c.execute('SELECT id FROM simc.simulation_jobs WHERE user_id=%s ORDER BY created_at DESC',(rows[0]['userId'],)).fetchall()
 assert jobs and any('submit' in x[0] for x in calls),calls
 job=packet(a.get('/simc/jobs/'+str(jobs[0][0])))
 assert job['status']=='succeeded' and job['result']['metricValue']>0
 assert str(job['id']) in answers[-1] and ('DPS' in answers[-1] or '伤害' in answers[-1])
 assert b.get('/chat/conversations/'+conv).status_code==404
 assert b.get('/simc/jobs/'+job['id']).status_code==404
 result={'passed':True,'conversationId':conv,'runId':str(runs[-1][0]),'jobId':job['id'],'compilerRevision':job['compilerRevision'],'runtimeRevision':job['runtimeRevision'],'positiveMetric':True,'assistantAnswerPersisted':True,'ownerIsolation':True,'toolCalls':calls,'seconds':round(time.monotonic()-started,1)}
 save('live.json',result);print(json.dumps(result))
finally:
 with connect() as c:
  for row in rows:c.execute('UPDATE identity.auth_sessions SET revoked_at=now() WHERE token_hash=%s',(hashlib.sha256(row['token'].encode()).hexdigest(),))
 a.close();b.close()

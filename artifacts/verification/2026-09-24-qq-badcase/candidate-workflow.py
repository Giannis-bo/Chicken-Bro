"""True isolated DB -> social routing -> professional Worker -> recorded outbox."""
import os,time,json,hashlib,sys
from pathlib import Path
from threading import Event
import psycopg
from server.app.channels.qq.companion_domain import GroupEvent
from server.app.channels.qq.companion_repository import CompanionRepository
from server.app.channels.qq.observation_repository import ObservationRepository
from server.app.channels.qq.companion_model import CompanionModel,PERSONA_PATH,SCHEMA_RULES
from server.app.channels.qq.repository import QqRepository
from server.app.channels.qq.service import QqService
from server.app.chickenbro.application import ChatApplication,ChatApplicationError
from server.app.chickenbro.repository import PostgresChatRepository
from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
from server.app.chickenbro.worker import start_chat_workers
from server.app.identity.domain import Principal
from uuid import uuid4
connect=lambda:psycopg.connect(os.environ['WOW_DATABASE_URL'])
with connect() as c:assert c.execute('select current_database()').fetchone()[0]=='chickenbro_qq_badcase_candidate_20260924'
phase=sys.argv[1] if len(sys.argv)>1 else 'initial'
bot,group,sender=('91550025' if phase=='final' else '91550024'),'92550024','93550024';r=CompanionRepository(connect,bot,(group,));o=ObservationRepository(connect)
q=QqRepository(connect,bot,(group,));app=ChatApplication(repository=PostgresChatRepository(connect,durable=True,actor_kind='qq_group'),codex=NativeCodexChatAdapter())
service=QqService(q,app,companion=True)
url=Path('/tmp/qq-badcase-source-url.txt').read_text().strip()
e=GroupEvent(bot,group,sender,'1001',time.time(),url+' 看看这场。只需查询一次战斗概况，回答首领、时长和是否击杀，不扩展玩家排名或死亡归因。','候选成员',True)
o.append(e);r.ensure_response(e,kind='mention');job=r.claim_response()
assert job
budget=Path('evidence/professional-budget.jsonl')
def charge(stage):
 with budget.open('a') as f:f.write(json.dumps({'group':'Q1','stage':stage,'time':time.time()})+'\n')
charge('social_model')
model=CompanionModel(NativeCodexChatAdapter(qq_scope='social',qq_rules=PERSONA_PATH.read_text()+SCHEMA_RULES))
d=model.decide([e],must_reply=True,target=e.message_id)
assert d.action=='wow_read',d
assert r.prepare_professional(job,d.action);assert not r.prepare_professional(job,d.action)
service.advance();charge('professional_model')
stop=Event();host,threads=start_chat_workers(None,connect,stop)
start=time.monotonic();state=None
try:
 while time.monotonic()-start<180:
  service.advance()
  with connect() as c:state=c.execute('SELECT state,run_id,user_id,conversation_id FROM qq_channel.inbox WHERE bot_id=%s AND message_id=%s',(bot,'1001')).fetchone()
  if state and state[0] in ('done','failed'):break
  time.sleep(.5)
 assert state and state[0]=='done',str(state[0] if state else None)
 with connect() as c:
  calls=c.execute('SELECT operation,state,result_json FROM chat.tool_results WHERE run_id=%s',(state[1],)).fetchall()
  scopes=c.execute('SELECT scope,user_id FROM qq_channel.run_scopes WHERE run_id=%s',(state[1],)).fetchall()
  answers=c.execute("SELECT content,state FROM qq_channel.outbox WHERE inbox_id=(SELECT id FROM qq_channel.inbox WHERE run_id=%s) AND kind='answer' ORDER BY part",(state[1],)).fetchall()
 assert scopes==[('wow_read',state[2])]
 assert 1<=len(calls)<=6 and all(x[0].startswith('source.') for x in calls)
 assert any(x[2].get('status')=='verified' and x[2].get('facts') for x in calls),[(x[0],x[2].get('status')) for x in calls]
 assert answers and all(x[1]=='pending' for x in answers)
 try:app.load_conversation(Principal(uuid4(),'qq_group'),state[3])
 except ChatApplicationError:isolated=True
 else:isolated=False
 assert isolated
 # Private answer is retained for semantic review, never sent or committed.
 private={'answers':[x[0] for x in answers],'tools':[x[2] for x in calls]}
 p=Path('evidence/professional-'+phase+'-private.json');p.write_text(json.dumps(private,ensure_ascii=False,indent=2));p.chmod(0o600)
 result={'status':'candidate_passed','database':'chickenbro_qq_badcase_candidate_20260924','socialAction':d.action,'inboxState':state[0],'scope':'wow_read','toolCalls':len(calls),'verifiedToolCalls':sum(x[2].get('status')=='verified' for x in calls),'answerParts':len(answers),'answerSha256':hashlib.sha256(''.join(x[0] for x in answers).encode()).hexdigest(),'outboxState':'pending_recording_only','secondOwnerDenied':isolated,'onebotStarted':False,'groupMessagesSent':0,'elapsedSeconds':round(time.monotonic()-start,2)}
 Path('evidence/professional-'+phase+'.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
finally:
 stop.set()
 for t in threads:t.join(timeout=10)
 host.close()

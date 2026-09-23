"""Synthetic isolated group; outputs are recorded, never sent to OneBot."""
import json,os,time
from collections import Counter
from pathlib import Path
from server.app.platform.config import AppSettings
from server.app.platform.postgres import PostgresConnectionFactory
from server.app.chickenbro import codex_adapter as adapter
from server.app.channels.qq.companion_domain import GroupEvent
from server.app.channels.qq.companion_model import CompanionModel,PERSONA_PATH,SCHEMA_RULES
from server.app.channels.qq.companion_repository import CompanionRepository
from server.app.channels.qq.observation_repository import ObservationRepository
from server.app.channels.qq.companion_service import CompanionService
from server.app.channels.qq.memory import MemoryRepository
connect=PostgresConnectionFactory(AppSettings.from_env(os.environ)).connection
with connect() as c:assert c.execute('select current_database()').fetchone()[0]=='chickenbro_qq_companion_candidate_20260923'
counts=Counter();original=adapter._ResearchSession._item_event
def track(self,method,params):
 if method=='item/completed':counts[str(params.get('item',{}).get('type'))]+=1
 return original(self,method,params)
adapter._ResearchSession._item_event=track
bot='95550123';group=str(int(time.time()));sender='96660123'
repo=CompanionRepository(connect,bot,(group,));obs=ObservationRepository(connect);mem=MemoryRepository(connect)
model=CompanionModel(adapter.NativeCodexChatAdapter(qq_scope='social',qq_rules=PERSONA_PATH.read_text()+SCHEMA_RULES))
svc=CompanionService(repo,obs,model,memory=mem,proactive=True)
results=[]
try:
 for mid,text,mention,enabled in [('801','鸡哥，今天打本被地板烫成脆皮鸡了哈哈',False,True),('802','以后叫我阿原，刚下班来打个招呼。',True,False)]:
  svc.proactive=enabled;e=GroupEvent(bot,group,sender,mid,time.time(),text,'候选群友',mention);svc.observe(e)
  deadline=time.monotonic()+65
  while time.monotonic()<deadline:
   svc.tick()
   with connect() as c:row=c.execute('select state from qq_channel.companion_responses where bot_id=%s and group_id=%s and message_id=%s',(bot,group,mid)).fetchone()
   if row and row[0] in ('done','silent','failed','professional'):break
   time.sleep(.2)
  assert row and row[0] in ('done','silent'),row
  with connect() as c:outputs=c.execute('select o.content from qq_channel.outbox o join qq_channel.inbox i on i.id=o.inbox_id where i.bot_id=%s and i.group_id=%s and i.message_id=%s',(bot,group,mid)).fetchall()
  if mention:assert outputs
  results.append({'case':'mention_with_proactive_disabled' if mention else 'fresh_proactive','state':row[0],'outputs':[x[0] for x in outputs]})
  print(json.dumps(results[-1],ensure_ascii=False),flush=True)
 assert not (set(counts)-{'reasoning','agentMessage','userMessage'})
 evidence={'results':results,'itemTypes':dict(counts),'facts':mem.facts(bot,group,(sender,)),'transport':'record_only_no_onebot'}
 Path('/var/lib/chickenbro/qq-companion-candidate/activation-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
finally:svc.close()

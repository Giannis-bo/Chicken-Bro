import json,time,os
from collections import Counter
from server.app.platform.config import AppSettings
from server.app.platform.postgres import PostgresConnectionFactory
from server.app.chickenbro import codex_adapter as a
from server.app.channels.qq.companion_domain import GroupEvent
from server.app.channels.qq.companion_model import CompanionModel,PERSONA_PATH,SCHEMA_RULES
from server.app.channels.qq.companion_repository import CompanionRepository
from server.app.channels.qq.observation_repository import ObservationRepository
from server.app.channels.qq.companion_service import CompanionService
from server.app.channels.qq.memory import MemoryRepository
from server.app.channels.qq.stickers import StickerCatalog
from pathlib import Path
counts=Counter();original=a._ResearchSession._item_event
def track(self,method,params):
 if method=='item/completed':counts[str(params.get('item',{}).get('type'))]+=1
 return original(self,method,params)
a._ResearchSession._item_event=track
connect=PostgresConnectionFactory(AppSettings.from_env(os.environ)).connection
bot='95550001';group=str(int(time.time()));sender='96660001'
repo=CompanionRepository(connect,bot,(group,));obs=ObservationRepository(connect);mem=MemoryRepository(connect)
model=CompanionModel(a.NativeCodexChatAdapter(qq_scope='social',qq_rules=PERSONA_PATH.read_text()+SCHEMA_RULES))
cat=StickerCatalog(Path.cwd()/'server/qq-channel/stickers')
svc=CompanionService(repo,obs,model,memory=mem,stickers=cat,proactive=True)
results=[]
for i,(text,mentioned) in enumerate([('鸡哥你好，我叫阿强，以后叫我阿强。',True),('还记得我叫什么吗？',True),('来个围观表情',True),('鸡哥，今天打本被地板烫成脆皮鸡了哈哈',False)]):
 e=GroupEvent(bot,group,sender,str(100+i),time.time(),text,'候选群友',mentioned)
 svc.observe(e);deadline=time.time()+60
 while time.time()<deadline:
  svc.tick()
  with connect() as c:
   row=c.execute('SELECT state FROM qq_channel.companion_responses WHERE bot_id=%s AND group_id=%s AND message_id=%s',(bot,group,e.message_id)).fetchone()
  if row and row[0] in ('done','silent','failed','professional'):break
  time.sleep(.2)
 else:raise AssertionError('social decision timeout')
 with connect() as c:
  outputs=c.execute('SELECT o.content,o.sticker_id FROM qq_channel.outbox o JOIN qq_channel.inbox i ON i.id=o.inbox_id WHERE i.bot_id=%s AND i.group_id=%s AND i.message_id=%s ORDER BY o.part',(bot,group,e.message_id)).fetchall()
 assert not mentioned or outputs
 results.append({'case':i,'mentioned':mentioned,'state':row[0],'outputs':outputs})
 print(json.dumps(results[-1],ensure_ascii=False),flush=True)
svc.close()
assert not (set(counts)-{'reasoning','agentMessage','userMessage'})
print(json.dumps({'bot':bot,'group':group,'toolEventTypes':dict(counts),'facts':mem.facts(bot,group,(sender,))},ensure_ascii=False),flush=True)
Path('/var/lib/chickenbro/qq-companion-candidate/social-evidence.json').write_text(json.dumps({'results':results,'itemTypes':dict(counts),'facts':mem.facts(bot,group,(sender,))},ensure_ascii=False,indent=2))

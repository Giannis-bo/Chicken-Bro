import os,time,json,hashlib
from pathlib import Path
from server.app.platform.config import AppSettings
from server.app.platform.postgres import PostgresConnectionFactory
from server.app.channels.qq.group_memes import GroupMemeCatalog
from server.app.channels.qq.companion_model import CompanionModel,PERSONA_PATH,SCHEMA_RULES
from server.app.channels.qq.companion_service import CompanionService
from server.app.channels.qq.companion_repository import CompanionRepository
from server.app.channels.qq.observation_repository import ObservationRepository
from server.app.channels.qq.companion_domain import GroupEvent
from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
c=PostgresConnectionFactory(AppSettings.from_env(os.environ)).connection
bot='95550003';group=str(int(time.time()));sender='96660003'
r=CompanionRepository(c,bot,(group,));obs=ObservationRepository(c);media=GroupMemeCatalog(c,bot,(group,))
original_search=media.search
def trace_search(event,query):
 print(json.dumps({'search_query':query},ensure_ascii=False),flush=True)
 result=original_search(event,query)
 print(json.dumps({'candidates':result[0]},ensure_ascii=False),flush=True)
 return result
media.search=trace_search
model=CompanionModel(NativeCodexChatAdapter(qq_scope='social',qq_rules=PERSONA_PATH.read_text()+SCHEMA_RULES))
svc=CompanionService(r,obs,model,stickers=media,proactive=False)
e=GroupEvent(bot,group,sender,'301',time.time(),'鸡哥，来张吃瓜表情包看戏，直接发图就行。','候选群友',True)
svc.observe(e);start=time.time()
while time.time()-start<170:
 svc.tick()
 with c() as conn:
  row=conn.execute('SELECT state FROM qq_channel.companion_responses WHERE bot_id=%s AND group_id=%s AND message_id=%s',(bot,group,e.message_id)).fetchone()
 if row and row[0] in ('done','failed'):break
 time.sleep(.3)
with c() as conn:
 rows=conn.execute('''SELECT o.content,o.sticker_id,m.mime,m.sha256,octet_length(m.content),m.source
 FROM qq_channel.outbox o JOIN qq_channel.inbox i ON i.id=o.inbox_id
 LEFT JOIN qq_channel.memes m ON m.id=o.sticker_id AND m.bot_id=i.bot_id AND m.group_id=i.group_id
 WHERE i.bot_id=%s AND i.group_id=%s''',(bot,group)).fetchall()
result={'elapsed':round(time.time()-start),'group':group,'state':row[0],'outputs':rows}
print(json.dumps(result,ensure_ascii=False),flush=True)
Path('/var/lib/chickenbro/qq-companion-candidate/meme-evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
svc.close();assert rows and rows[0][1] and rows[0][5]=='web'

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
previous=json.loads(Path('/var/lib/chickenbro/qq-companion-candidate/meme-evidence.json').read_text())
with c() as conn:
 data=bytes(conn.execute('SELECT content FROM qq_channel.memes WHERE bot_id=%s AND group_id=%s AND id=%s',('95550003',previous['group'],previous['outputs'][0][1])).fetchone()[0])
bot='95550004';group=str(int(time.time()));sender='96660003'
r=CompanionRepository(c,bot,(group,));obs=ObservationRepository(c);media=GroupMemeCatalog(c,bot,(group,))
class Client:
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def call(self,action,params):return {'group_id':group,'message':[{'type':'image','data':{'file':'friend.gif','url':'https://gchat.qpic.cn/image'}}]}
media.onebot_factory=Client
media.fetch=lambda *args,**kwargs:data
model=CompanionModel(NativeCodexChatAdapter(qq_scope='social',qq_rules=PERSONA_PATH.read_text()+SCHEMA_RULES))
svc=CompanionService(r,obs,model,stickers=media,proactive=False)
source=GroupEvent(bot,group,sender,'300',time.time(),'[图片]','候选群友',False)
media.observe(source,{'message':[{'type':'image','data':{'file':'friend.gif','summary':'[动画表情]'}}]})
svc.observe(source)
e=GroupEvent(bot,group,sender,'301',time.time(),'鸡哥，借用一下群友刚才的吃瓜表情，直接发图就行。','候选群友',True)
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
from server.app.channels.qq.stickers import render_reply
from server.app.channels.qq.companion_domain import ReplyDraft
import base64
segments=render_reply(e.message_id,ReplyDraft(rows[0][0],rows[0][1]),media.for_group(group))
transport=next(x['data']['file'] for x in segments if x['type']=='image')
assert base64.b64decode(transport.removeprefix('base64://'))==data
result={'transport_original_bytes_match':True,'elapsed':round(time.time()-start),'group':group,'state':row[0],'outputs':rows}
print(json.dumps(result,ensure_ascii=False),flush=True)
Path('/var/lib/chickenbro/qq-companion-candidate/meme-reuse-evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
svc.close();assert rows and rows[0][1] and rows[0][5]=='group'

import os,json,time
from pathlib import Path
from server.app.platform.config import AppSettings
from server.app.platform.postgres import PostgresConnectionFactory
from server.app.channels.qq.policy import ChannelConfig,parse_group_event
from server.app.channels.qq.companion_model import CompanionModel,PERSONA_PATH,SCHEMA_RULES
from server.app.channels.qq.observation_repository import ObservationRepository
from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
connect=PostgresConnectionFactory(AppSettings.from_env(os.environ)).connection
obs=ObservationRepository(connect)
model=CompanionModel(NativeCodexChatAdapter(qq_scope='social',qq_rules=PERSONA_PATH.read_text()+SCHEMA_RULES))
results=[]
for i,segments in enumerate(([{'type':'face','data':{'id':'355'}}],[{'type':'text','data':{'text':'哈哈哈哈'}}],[{'type':'text','data':{'text':'终于下班了'}}])):
 group=str(int(time.time())+i);config=ChannelConfig('95550005',(group,),True)
 raw={'post_type':'message','message_type':'group','self_id':95550005,'group_id':int(group),'user_id':96660005,'message_id':str(501+i),'time':time.time(),'sender':{'nickname':'候选群友'},'message':[{'type':'at','data':{'qq':'95550005'}},*segments]}
 event=parse_group_event(raw,config);obs.append(event)
 context=obs.context(config.bot_qq,group,now=time.time())
 start=time.time();d=model.decide(context,must_reply=True,target=event.message_id)
 text=d.draft.text if d.draft else ''
 row={'input':event.text,'attachment':event.attachment,'action':d.action,'reply':text,'elapsed':round(time.time()-start,2)}
 results.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
 assert d.action=='reply' and text and len(text)<120
 assert not any(x in text for x in ('附件','具体描述','处理中','排队','有什么可以帮','任务完成'))
Path('/var/lib/chickenbro/qq-companion-candidate/natural-evidence.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))

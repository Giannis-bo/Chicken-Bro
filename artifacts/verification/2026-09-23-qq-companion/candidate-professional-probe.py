import json,time,os
from pathlib import Path
from threading import Event,Thread
from server.app.platform.config import AppSettings
from server.app.platform.postgres import PostgresConnectionFactory
from server.app.channels.qq.companion_domain import GroupEvent
from server.app.channels.qq.companion_repository import CompanionRepository
from server.app.channels.qq.observation_repository import ObservationRepository
from server.app.channels.qq.companion_model import CompanionModel,PERSONA_PATH,SCHEMA_RULES
from server.app.channels.qq.companion_service import CompanionService
from server.app.channels.qq.repository import QqRepository
from server.app.channels.qq.service import QqService
from server.app.chickenbro.application import ChatApplication
from server.app.chickenbro.repository import PostgresChatRepository
from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
from server.app.chickenbro.worker import start_chat_workers
from server.app.worker.main import build_worker
settings=AppSettings.from_env(os.environ);connect=PostgresConnectionFactory(settings).connection
stop=Event();host,threads=start_chat_workers(settings,connect,stop)
worker=build_worker(worker_id='qq-companion-candidate',lease_seconds=30)
sim_thread=Thread(target=lambda:worker.run_forever(stop.is_set),daemon=True);sim_thread.start()
bot='95550002';group=str(int(time.time()));sender='96660002'
r=CompanionRepository(connect,bot,(group,));o=ObservationRepository(connect)
q=QqRepository(connect,bot,(group,));app=ChatApplication(repository=PostgresChatRepository(connect,durable=True,actor_kind='qq_group'),codex=NativeCodexChatAdapter())
service=QqService(q,app,companion=True)
e=GroupEvent(bot,group,sender,'201',time.time(),'我的魔兽角色是 https://raider.io/cn/characters/cn/silver-hand/Giannis 。请用 SimC 比较开启和关闭嗜血的 DPS，两个方案各100次迭代、60秒、单目标木桩。实际运行后报告数值。','候选群友',True)
o.append(e);r.ensure_response(e,kind='mention');job=r.claim_response();assert r.prepare_professional(job,'wow_sim');service.advance()
model=CompanionModel(NativeCodexChatAdapter(qq_scope='social',qq_rules=PERSONA_PATH.read_text()+SCHEMA_RULES))
social=CompanionService(r,o,model,proactive=False)
social.observe(GroupEvent(bot,group,sender,'202',time.time(),'鸡哥你先忙，陪我随便聊一句，今天下班想吃炸鸡哈哈','候选群友',True))
start=time.time();last=0;result=None
while time.time()-start<480:
 service.advance();social.tick()
 with connect() as c:
  state=c.execute("SELECT message_id,state,run_id FROM qq_channel.inbox WHERE bot_id=%s AND group_id=%s ORDER BY message_id",(bot,group)).fetchall()
 if time.time()-last>30:
  print(json.dumps({'elapsed':round(time.time()-start),'inbox':[(x[0],x[1]) for x in state]}),flush=True);last=time.time()
 if any(x[0]=='201' and x[1] in ('done','failed') for x in state) and any(x[0]=='202' and x[1]=='done' for x in state):break
 time.sleep(.3)
with connect() as c:
 rows=c.execute('''SELECT i.message_id,i.state,o.content FROM qq_channel.inbox i LEFT JOIN qq_channel.outbox o ON o.inbox_id=i.id
  WHERE i.bot_id=%s AND i.group_id=%s ORDER BY i.message_id,o.part''',(bot,group)).fetchall()
 jobs=c.execute('''SELECT j.id,j.status,r.primary_metric_name,r.primary_metric_value,r.runtime_revision FROM simc.simulation_jobs j
  LEFT JOIN simc.simulation_results r ON r.job_id=j.id AND r.user_id=j.user_id WHERE j.user_id IN (SELECT user_id FROM qq_channel.principals WHERE bot_id=%s AND group_id=%s)''',(bot,group)).fetchall()
 evidence={'bot':bot,'group':group,'elapsed':round(time.time()-start),'responses':rows,'simulations':jobs}
print(json.dumps(evidence,ensure_ascii=False,default=str),flush=True)
Path('/var/lib/chickenbro/qq-companion-candidate/professional-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,default=str,indent=2))
stop.set();social.close()
assert any(x[0]=='202' and x[1]=='done' for x in rows)
assert len(jobs)>=2 and all(float(x[3] or 0)>0 for x in jobs)

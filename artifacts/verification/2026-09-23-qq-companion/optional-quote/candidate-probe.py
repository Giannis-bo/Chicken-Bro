import os,json,time
from pathlib import Path
from server.app.platform.config import AppSettings
from server.app.platform.postgres import PostgresConnectionFactory
from server.app.channels.qq.companion_domain import GroupEvent
from server.app.channels.qq.companion_model import CompanionModel,PERSONA_PATH,SCHEMA_RULES
from server.app.channels.qq.companion_repository import CompanionRepository
from server.app.channels.qq.repository import QqRepository
from server.app.channels.qq.runtime import deliver_one
from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
connect=PostgresConnectionFactory(AppSettings.from_env(os.environ)).connection
with connect() as c:assert c.execute('select current_database()').fetchone()[0]=='chickenbro_qq_companion_candidate_20260923'
e=GroupEvent('95550124',str(int(time.time())),'96660124','901',time.time(),'鸡哥鸡哥','候选群友',False)
model=CompanionModel(NativeCodexChatAdapter(qq_scope='social',qq_rules=PERSONA_PATH.read_text()+SCHEMA_RULES))
d=model.decide([e],must_reply=False,target=e.message_id)
assert d.action=='reply' and d.draft and not d.draft.quote,d
r=CompanionRepository(connect,e.bot,(e.group,));r.ensure_response(e,kind='mention');job=r.claim_response();r.complete_response(job['id'],job['lease_token'],d.draft)
class RecordTransport:
 def __init__(self):self.sent=[]
 def call(self,action,params):self.sent.append(params['message']);return {'message_id':9901}
t=RecordTransport();assert deliver_one(QqRepository(connect,e.bot,(e.group,)),t,(e.group,))
assert all(s['type']!='reply' for s in t.sent[0])
out={'input':e.text,'text':d.draft.text,'quote':d.draft.quote,'segments':t.sent[0],'transport':'record_only_no_onebot','scope':'model_to_persisted_queue_to_transport'}
Path('/var/lib/chickenbro/qq-companion-candidate/optional-quote-evidence.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False))

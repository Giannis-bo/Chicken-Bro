"""One cloud-only real Chat read, no external collection or research."""
import json
from uuid import uuid4
from tests.poe2_candidate_smoke import ROOT, PRIVATE, client, packet
rows=json.loads((PRIVATE/'sessions.json').read_text()); a=client(rows['A'])
import_id=(ROOT/'evidence/task6/wegame-id.txt').read_text().strip()
conv=packet(a.post('/chat/conversations',json={'game':'poe2','title':'Task6 既有导入仅读取验收'},headers={'Idempotency-Key':str(uuid4())}),201)['id']
prompt=f'请只调用一次 poe2_character_get 工具读取我的既有导入任务 {import_id}，告诉我其当前状态及来源。不要新建、取消、重试、补充、计算、搜索或读取外部网页。只根据工具结果简短回答。'
r=a.post('/chat/conversations/'+conv+'/messages/stream',json={'content':prompt,'clientMessageId':str(uuid4())},headers={'Idempotency-Key':str(uuid4())},timeout=420)
assert r.status_code==200,r.status_code
p=PRIVATE/'task6-chat.sse';p.write_text(r.text);p.chmod(0o600)
detail=packet(a.get('/chat/conversations/'+conv,params={'includeProgress':'true'}))
p=PRIVATE/'task6-chat-detail.json';p.write_text(json.dumps(detail,ensure_ascii=False));p.chmod(0o600)
report={'conversationId':conv,'importId':import_id,'httpStatus':r.status_code,'streamCompleted':'event: completed' in r.text or '"type":"completed"' in r.text or '"type": "completed"' in r.text,'detailTopKeys':list(detail),'scope':'single real Chat request; private raw detail retained only on cloud; tool invocation evidence pending persisted trace check'}
(ROOT/'evidence/task6/chat.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report))

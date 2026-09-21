"""Cloud Candidate: one real bounded chat, reuse existing build baseline."""
import json
from pathlib import Path
from uuid import uuid4
from tests.poe2_candidate_smoke import client, packet

ROOT=Path('/opt/chickenbro-candidates/poe2-20260918')
OUT=ROOT/'evidence/research-budget'
OUT.mkdir(exist_ok=True)
a=client(json.loads((ROOT/'runtime/browser/compare-cleanup-sessions.json').read_text())['A'])
build=next(b for b in packet(a.get('/poe2/builds'))['items'] if b['summary'].get('level')==96)
before=packet(a.get('/poe2/jobs',params={'buildId':build['id']}))['items']
conv=packet(a.post('/chat/conversations',json={'game':'poe2','title':'基线复用与研究预算验收'},headers={'Idempotency-Key':str(uuid4())}),201)['id']
r=a.post('/chat/conversations/'+conv+'/messages/stream',json={'content':f'构筑 ID：{build["id"]}。把角色等级提高到 97 级，对比生命和魔力的变化，帮我算一下。','clientMessageId':str(uuid4())},headers={'Idempotency-Key':str(uuid4())},timeout=420)
assert r.status_code==200
private=OUT/'chat-private.sse';private.write_text(r.text);private.chmod(0o600)
detail=packet(a.get('/chat/conversations/'+conv,params={'includeProgress':'true'}))
private=OUT/'chat-private.json';private.write_text(json.dumps(detail,ensure_ascii=False));private.chmod(0o600)
answers=[m['content'] for m in detail['messages'] if m['role']=='assistant']
assert answers and '生命' in answers[-1] and '魔力' in answers[-1]
after=packet(a.get('/poe2/jobs',params={'buildId':build['id']}))['items']
assert {j['id'] for j in before if not j['changes']}=={j['id'] for j in after if not j['changes']}
new=[j for j in after if j['id'] not in {x['id'] for x in before}]
assert len(new)<=1 and all(j['changes']=={'level':97} and j['status']=='succeeded' for j in new)
report={'passed':True,'conversationId':conv,'baselineUnchanged':True,'newCandidateJobs':len(new),'answerCharacters':len(answers[-1]),'traceVerification':'pending'}
(OUT/'chat.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))

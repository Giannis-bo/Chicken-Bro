"""Cloud-only: verify a new candidate in the same persisted research."""
import json
from uuid import uuid4
from tests.poe2_candidate_smoke import client, packet, ROOT
out=ROOT/'evidence/research-budget'
prior=json.loads((out/'chat.json').read_text()); conv=prior['conversationId']
a=client(json.loads((ROOT/'runtime/browser/compare-cleanup-sessions.json').read_text())['A'])
build=next(b for b in packet(a.get('/poe2/builds'))['items'] if b['summary'].get('level')==96)
before=packet(a.get('/poe2/jobs',params={'buildId':build['id'],'limit':100}))['items']
level=next(n for n in [98,99,95,94] if not any(j['changes']=={'level':n} for j in before))
r=a.post('/chat/conversations/'+conv+'/messages/stream',json={'content':f'继续对比：再算一下 {level} 级相对原始 96 级的生命和魔力变化。','clientMessageId':str(uuid4())},headers={'Idempotency-Key':str(uuid4())},timeout=420)
assert r.status_code==200
p=out/'followup-private.sse';p.write_text(r.text);p.chmod(0o600)
detail=packet(a.get('/chat/conversations/'+conv,params={'includeProgress':'true'}))
p=out/'followup-private.json';p.write_text(json.dumps(detail,ensure_ascii=False));p.chmod(0o600)
after=packet(a.get('/poe2/jobs',params={'buildId':build['id'],'limit':100}))['items']
new=[j for j in after if j['id'] not in {x['id'] for x in before}]
assert len(new)==1 and new[0]['changes']=={'level':level} and new[0]['status']=='succeeded'
assert {j['id'] for j in before if not j['changes']}=={j['id'] for j in after if not j['changes']}
result={'passed':True,'conversationId':conv,'newCandidateJobs':1,'baselineUnchanged':True,'candidateLevel':level,'traceVerification':'pending'}
(out/'followup.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

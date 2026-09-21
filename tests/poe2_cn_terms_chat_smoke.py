"""Cloud-only real default-language check using the user's already imported build."""
import json
import hashlib
import time
from uuid import uuid4
from tests.poe2_candidate_smoke import ROOT, PRIVATE, client, packet, sessions
from server.app.poe2.engine import decode_build

rows = sessions()
a = client(rows['A'])
builds = packet(a.get('/poe2/builds'))['items']
source = (PRIVATE / 'cn-terms-user-code.txt').read_text()
# import_build passes decoded XML into the engine, whose XML path trims it.
input_hash = hashlib.sha256(decode_build(decode_build(source)).encode()).hexdigest()
build = next(b for b in builds if b['inputSha256'] == input_hash)
conv = packet(a.post('/chat/conversations', json={'game': 'poe2', 'title': '构筑术语默认语言验收'}, headers={'Idempotency-Key': str(uuid4())}), 201)['id']
prompt = f'看看这份构筑搭载了哪些技能，搭配什么辅助宝石。构筑 ID：{build["id"]}。读取已有资料即可，不需要重新导入或计算。'
start = time.monotonic()
r = a.post('/chat/conversations/' + conv + '/messages/stream', json={'content': prompt, 'clientMessageId': str(uuid4())}, headers={'Idempotency-Key': str(uuid4())}, timeout=420)
assert r.status_code == 200
detail = packet(a.get('/chat/conversations/' + conv, params={'includeProgress': 'true'}))
for name, data in [('cn-terms-chat.sse', r.text), ('cn-terms-chat-detail.json', json.dumps(detail, ensure_ascii=False))]:
    p = PRIVATE / name
    p.write_text(data)
    p.chmod(0o600)
answers = [m['content'] for m in detail['messages'] if m['role'] == 'assistant']
answer = '\n'.join(answers)
assert answer, 'missing assistant answer'
report = {'conversationId': conv, 'buildId': build['id'], 'elapsedSeconds': round(time.monotonic()-start, 3),
          'defaultLanguagePrompt': True, 'containsShieldWallChinese': '盾墙' in answer,
          'unexpectedEnglish': [n for n in ['Shield Wall', 'Sunder', 'Herald of Blood', 'Bleed III', 'Poison III', 'Rapid Attacks II'] if n in answer],
          'answerCharacters': len(answer), 'toolTraceVerification': 'pending', 'passed': False}
(ROOT / 'evidence/cn-terms/chat.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(report, ensure_ascii=False))

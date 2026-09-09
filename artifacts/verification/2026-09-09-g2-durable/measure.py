"""Run on the known cloud host only; stdout contains aggregate timings, no chat text.

sudo python3 measure.py --output /var/tmp/... --source /opt/chickenbro
Private answers stay on the host for quality inspection; never commit them.
"""
import argparse
import hashlib
import json
import os
import pwd
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--output', required=True)
p.add_argument('--source', default='/opt/chickenbro')
p.add_argument('--case', choices=['original', 'similar'], default='original')
p.add_argument('--port', type=int, default=8791)
p.add_argument('--optimized', action='store_true')
a = p.parse_args()
pid = subprocess.check_output(['systemctl', 'show', 'chickenbro-api.service', '-p', 'MainPID', '--value'], text=True).strip()
for item in Path('/proc/' + pid + '/environ').read_bytes().split(b'\0'):
    if b'=' in item:
        key, value = item.split(b'=', 1)
        os.environ[key.decode()] = value.decode()
sql = """BEGIN READ ONLY;
SELECT json_agg(x ORDER BY x.created_at,x.id) FROM (
 SELECT m.id,m.role,m.content,m.created_at FROM chat.messages m
 JOIN chat.agent_runs r ON r.conversation_id=m.conversation_id AND r.user_id=m.user_id
 JOIN chat.messages q ON q.id=r.user_message_id
 WHERE r.id::text LIKE '3a92aaf7%' AND m.created_at<=q.created_at
 ORDER BY m.created_at DESC,m.id DESC LIMIT 20) x; COMMIT;"""
history = json.loads(subprocess.check_output(['sudo', '-n', '-u', 'postgres', 'psql', '-X', '-qAt', '-d', 'chickenbro_prod', '-v', 'ON_ERROR_STOP=1'], input=sql, text=True))
messages = [{'role': r['role'], 'content': r['content'][:4000]} for r in history]
if a.case == 'similar':
    messages[-1] = {'role': 'user', 'content': '请基于上面的同一场战斗，复盘奶骑的美德与鸣钟衔接、血线危险窗口和主要治疗技能时机，给出最值得改进的三点。区分已核验事实与尚缺证据，不要把资源溢出直接换算成有效治疗损失。'}
prompt = json.dumps({'messages': messages}, ensure_ascii=False)
identity = str(Path(a.source).resolve())
os.chdir(a.source)
sys.path.insert(0, os.getcwd())
u = pwd.getpwnam('ubuntu')
root = Path(a.output)
root.mkdir(mode=0o700, parents=True, exist_ok=True)
os.chown(root, u.pw_uid, u.pw_gid)
os.setgid(u.pw_gid)
os.setuid(u.pw_uid)
from server.app.chickenbro.source_gateway import ChickenbroSourceGateway
from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
from server.app.chickenbro import codex_stdio
import traceback
protocol_failures=[]
original_invalid=codex_stdio.invalid
def diagnosed_invalid():
    protocol_failures.append([{'file':Path(f.filename).name,'line':f.lineno,'function':f.name}
                              for f in traceback.extract_stack(limit=4)[:-1]])
    return original_invalid()
codex_stdio.invalid=diagnosed_invalid

if a.optimized:
    from server.app.chickenbro.source_gateway import ServerConfiguredSourceQuery
    from server.app.chickenbro.wcl_source import WclRunReader
    gateway = ChickenbroSourceGateway(query_service=ServerConfiguredSourceQuery(wcl_reader=WclRunReader()))
else:
    gateway = ChickenbroSourceGateway()
calls = []
lock = threading.Lock()
started = time.monotonic()
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def do_POST(self):
        begin = time.monotonic() - started
        status = 'error'
        key = ''
        try:
            b = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if b['provider'] not in ('warcraftlogs','warcraftlogs_batch'):
                raise ValueError('read-only WCL measurement')
            key = hashlib.sha256(json.dumps({k: b.get(k) for k in ('provider', 'target', 'options')}, sort_keys=True).encode()).hexdigest()
            result = gateway.query(self.headers.get('X-Chickenbro-Source-Gateway', ''), b['provider'], b['target'], b.get('options'))
            status = result.get('status', 'unknown')
            data = json.dumps(result, ensure_ascii=False).encode()
            self.send_response(200)
        except Exception as error:
            status = type(error).__name__
            data = b'{}'
            self.send_response(422)
        finally:
            with lock:
                calls.append({'start': begin, 'end': time.monotonic() - started, 'key': key, 'status': status})
        self.end_headers()
        self.wfile.write(data)

http = ThreadingHTTPServer(('127.0.0.1', a.port), Handler)
threading.Thread(target=http.serve_forever, daemon=True).start()
adapter = NativeCodexChatAdapter(jobs_dir=root / 'jobs', source_gateway=gateway,
    source_gateway_url=f'http://127.0.0.1:{a.port}/api/v2/internal/chickenbro/source-query')
answer = []
terminal = 'missing'
try:
    for event in adapter.stream(prompt=prompt, timeout_seconds=480):
        if event['type'] == 'delta':
            answer.append(event.get('text', ''))
        if event['type'] == 'completed':
            terminal = 'completed'
            if not answer:
                answer.append(event.get('text', ''))
except Exception as error:
    terminal = type(error).__name__
elapsed = time.monotonic() - started
http.shutdown()
union = 0
end = 0
for call in sorted(calls, key=lambda x: x['start']):
    union += max(0, call['end'] - max(end, call['start']))
    end = max(end, call['end'])
metrics = {'case': a.case, 'source': identity, 'terminal': terminal, 'seconds': elapsed,
    'toolWallSeconds': union, 'nonToolWallSeconds': elapsed - union,
    'toolSumSeconds': sum(c['end'] - c['start'] for c in calls),
    'calls': calls, 'answerChars': sum(map(len, answer)), 'protocolFailureSites':protocol_failures}
(root / 'answer.txt').write_text(''.join(answer))
(root / 'metrics.json').write_text(json.dumps(metrics, indent=2))
print(json.dumps(metrics), flush=True)

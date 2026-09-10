"""Isolated actual NativeCodex comparison, no production Chat or SimC writes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

mode, case = sys.argv[1:3]
root = Path('/tmp/chickenbro-wcl-efficiency-20260910') if mode=='candidate' else Path('/opt/chickenbro')
pid = subprocess.check_output(['systemctl','show','chickenbro-api.service','-p','MainPID','--value'],text=True).strip()
env = dict(x.split('=',1) for x in Path('/proc',pid,'environ').read_bytes().decode().split('\0') if '=' in x)
os.environ.update({k:v for k,v in env.items() if k.startswith('WOW_WARCRAFTLOGS_') or k in (
    'CODEX_HOME','WOW_CODEX_BIN','WOW_CODEX_PROFILE','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY')})
sys.path.insert(0,str(root))
from server.app.chickenbro.wcl_source import WclRunReader
from server.app.chickenbro.source_gateway import ChickenbroSourceGateway, ServerConfiguredSourceQuery
from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
from server.app.chickenbro.worker_gateway import WorkerToolServer

receipts = []
class Recorder:
    def execute(self, operation, arguments, invoke):
        start = time.monotonic()
        result = invoke()
        receipts.append({'operation':operation, 'options':arguments.get('options'),
                         'status':result.get('status'), 'seconds':round(time.monotonic()-start,3),
                         'bytes':len(json.dumps(result,ensure_ascii=False).encode()),
                         'statistics':[(f.get('statistics')) for f in result.get('facts',[]) if isinstance(f,dict) and f.get('statistics')]})
        return result

prompts = {
 'resources':'请分析 https://www.warcraftlogs.com/reports/ZgdALDkX48af26KN?fight=8&source=12 。只统计该角色战斗内2:13到2:33的圣能浪费，共浪费几点？请区分资源统计与是否损失有效治疗，不扩展为全场复盘。这个窗口对应报告相对毫秒2712438到2732438。',
 'casts':'请统计 https://www.warcraftlogs.com/reports/LPZNxhXGgdmDH6Cq?fight=2&source=5 中，这名角色战斗开始后第10到30秒的各技能施法次数，技能ID即可。对应报告相对毫秒2178308到2198308。只给这个窗口的统计和来源范围，不需要全场攻略。',
}
server = None
for port in (18794, 8791, 8792, 28794):
    try:
        server = WorkerToolServer(port)
        break
    except OSError:
        continue
if server is None:
    raise RuntimeError('No free allowlisted isolated tool port')
server.start()
gateway = server.register(ChickenbroSourceGateway(query_service=ServerConfiguredSourceQuery(wcl_reader=WclRunReader())),Recorder(),'source')
adapter = NativeCodexChatAdapter(enabled=True, jobs_dir=Path('/tmp/chickenbro-wcl-efficiency-20260910/model-jobs'),
    source_gateway=gateway, source_gateway_url=f'http://127.0.0.1:{port}/api/v2/internal/chickenbro/source-query')
began = time.monotonic()
answer, error = '', None
try:
    for event in adapter.stream(prompt=json.dumps({'messages':[{'role':'user','content':prompts[case]}]},ensure_ascii=False),timeout_seconds=240):
        if event.get('type')=='completed':
            answer = event.get('text','')
except Exception as exc:
    error = getattr(exc,'code',type(exc).__name__)
finally:
    server.close()
print(json.dumps({'mode':mode,'case':case,'seconds':round(time.monotonic()-began,3),'error':error,
                  'answer':answer,'tools':receipts},ensure_ascii=False,indent=2))

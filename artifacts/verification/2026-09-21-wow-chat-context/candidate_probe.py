"""Cloud isolated startup probe through the real capability gateway and model."""
import json,os,subprocess,sys,threading
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
root=Path('/opt/chickenbro-candidates/wow-chat-context-20260921')
sys.path.insert(0,str(root))
pid=subprocess.check_output(['systemctl','show','chickenbro-worker','-p','MainPID','--value'],text=True).strip()
env=dict(x.split('=',1) for x in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in x)
os.environ.update(env)
os.environ['WOW_CODEX_JOBS_DIR']=str(root/'probe-jobs')
Path(os.environ['WOW_CODEX_JOBS_DIR']).mkdir(exist_ok=True)
from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
from server.app.chickenbro.simulation_tools import SimulationToolGateway
from server.app.chickenbro.worker_gateway import RegisteredGateway
from server.app.identity.domain import Principal
host=SimpleNamespace(lock=threading.RLock(),routes={})
gateway=RegisteredGateway(host,SimulationToolGateway(None),None,'simc')
adapter=NativeCodexChatAdapter(simulation_gateway=gateway)
events=list(adapter.stream_for_chat(principal=Principal(uuid4(),'web_cookie'),conversation_id=uuid4(),run_id=uuid4(),game='wow',prompt=json.dumps({'messages':[{'role':'user','content':'你好，请简短打个招呼。不需要调用工具。'}]},ensure_ascii=False),timeout_seconds=120))
assert events[-1]['type']=='completed' and events[-1]['text'].strip()
assert not host.routes
result={'passed':True,'realModelCompleted':True,'realWorkerGatewayAccepted':True,'capabilityRevoked':True,'scope':'isolated cloud adapter startup; no simulation submitted'}
(root/'probe.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))

"""Preregistered read-only model trials; no production conversation writes."""
import os,sys,json,subprocess,pwd,tempfile,threading,time,hashlib
from pathlib import Path
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from concurrent.futures import ThreadPoolExecutor
source=sys.argv[1];version=sys.argv[2]
samples=json.loads(Path('/var/tmp/chickenbro-badcase-20260909/suite-samples.json').read_text())
out=Path('/var/tmp/chickenbro-badcase-suite-'+version);out.mkdir(mode=0o700,exist_ok=True)
u=pwd.getpwnam('ubuntu');os.chown(out,u.pw_uid,u.pw_gid)
pid=subprocess.check_output(['systemctl','show','chickenbro-api','-p','MainPID','--value'],text=True).strip()
os.environ.update(dict(v.split('=',1) for v in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in v))
os.chdir(source);sys.path.insert(0,source)
from server.app.chickenbro import source_gateway as g,codex_adapter as a
from server.app.chickenbro.wcl_source import WclRunReader
os.setgid(u.pw_gid);os.setuid(u.pw_uid)
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
config=a._load_profile(os.environ.get('WOW_CODEX_PROFILE'));config=dict(config)
# Release-specific MCP path is source identity, not a changed model setting.
config['mcp_servers']['chickenbro_toolbox']['args']=['<release>/server/chickenbro_native_mcp.py']
configsha=digest(config);promptsha=hashlib.sha256(a._load_agent_rules().encode()).hexdigest()
conditions={'model_config_sha256':configsha,'timeout_seconds':480,'wcl_reader_budget_seconds':360,'source_access':'existing_server_public_read_only','harness':'suite-v1','parallel_trials':2}
conditionhash=digest(conditions);routes={};lock=threading.Lock()
class Gateway(g.ChickenbroSourceGateway):
 def __init__(self,record):super().__init__(query_service=g.ServerConfiguredSourceQuery(wcl_reader=WclRunReader()));self.record=record
 def issue_capability(self):
  token=super().issue_capability()
  with lock:routes[token]=self
  return token
 def revoke(self,token):
  super().revoke(token)
  with lock:routes.pop(token,None)
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  gateway=None;start=time.monotonic()
  try:
   token=self.headers.get('X-Chickenbro-Source-Gateway','')
   with lock:gateway=routes.get(token)
   if gateway is None:raise PermissionError()
   body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
   result=gateway.query(token,body['provider'],body['target'],body.get('options'))
   gateway.record.append({'provider':body['provider'],'target':body['target'],'options':body.get('options'),'seconds':round(time.monotonic()-start,3),'result':result})
   self.send_response(200);self.end_headers();self.wfile.write(json.dumps(result,ensure_ascii=False).encode())
  except Exception as e:
   if gateway:gateway.record.append({'error':type(e).__name__})
   self.send_response(422);self.end_headers();self.wfile.write(b'{}')
http=ThreadingHTTPServer(('127.0.0.1',8791),Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
def trial(job):
 sample,repeat=job;sid=sample['id'];record=[];start=time.monotonic();observed=datetime.now(timezone.utc).isoformat()
 result={'sample_id':sid,'category':sample['category'],'repeat':repeat,'version':version,'source':source,'observed_at':observed,
  'input_sha256':digest(sample['messages']),'model_config_sha256':configsha,'prompt_sha256':promptsha,'conditions_sha256':conditionhash,'conditions':conditions}
 with tempfile.TemporaryDirectory(prefix='badcase-suite-') as jobroot:
  gateway=Gateway(record)
  adapter=a.NativeCodexChatAdapter(jobs_dir=jobroot,source_gateway=gateway,source_gateway_url='http://127.0.0.1:8791/api/v2/internal/chickenbro/source-query')
  try:
   events=list(adapter.stream(prompt=json.dumps({'messages':sample['messages']},ensure_ascii=False),timeout_seconds=480))
   result['answers']=[e['text'] for e in events if e.get('type')=='completed'];result['terminal']='completed' if result['answers'] else 'missing'
  except Exception as e:result['terminal']='failed';result['error']=type(e).__name__
 result['duration_seconds']=round(time.monotonic()-start,3);result['cost']={'tool_calls':len(record),'provider_tokens':None,'provider_cost':None,'provider_cost_unit':None};result['calls']=record
 path=out/(sid+'-'+str(repeat)+'.json');path.write_text(json.dumps(result,ensure_ascii=False));path.chmod(0o600)
 print(json.dumps({k:result.get(k) for k in ('sample_id','repeat','terminal','error','duration_seconds','cost')},ensure_ascii=False),flush=True)
 return result['terminal']
print(json.dumps({'version':version,'conditions_sha256':conditionhash,'model_config_sha256':configsha,'prompt_sha256':promptsha,'trial_count':len(samples)*2}),flush=True)
try:
 list(ThreadPoolExecutor(max_workers=2).map(trial,[(s,n) for s in samples for n in [1,2]]))
finally:http.shutdown();http.server_close()

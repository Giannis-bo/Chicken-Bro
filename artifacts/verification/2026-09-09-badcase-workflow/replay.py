import os,sys,json,subprocess,pwd,tempfile,threading,time,hashlib
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
source=sys.argv[1];mode=sys.argv[2]
pid=subprocess.check_output(['systemctl','show','chickenbro-api','-p','MainPID','--value'],text=True).strip()
os.environ.update(dict(v.split('=',1) for v in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in v))
os.chdir(source);sys.path.insert(0,source)
from server.app.chickenbro import source_gateway as g,codex_adapter as a
u=pwd.getpwnam('ubuntu');os.setgid(u.pw_gid);os.setuid(u.pw_uid)
gateway=g.ChickenbroSourceGateway();calls=[]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  try:
   b=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
   r=gateway.query(self.headers.get('X-Chickenbro-Source-Gateway',''),b['provider'],b['target'],b.get('options'))
   calls.append({'provider':b['provider'],'target':b['target'],'options':b.get('options'),'status':r.get('status'),'scope':r.get('scope'),'returned':len(r.get('rankings',[]))})
   self.send_response(200);self.end_headers();self.wfile.write(json.dumps(r,ensure_ascii=False).encode())
  except Exception as e:
   calls.append({'error':type(e).__name__,'request':b});self.send_response(422);self.end_headers();self.wfile.write(b'{}')
http=ThreadingHTTPServer(('127.0.0.1',8791),Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
packets=json.loads(Path('/var/tmp/chickenbro-badcase-20260909/packets.json').read_text())
packet=next(p for p in packets if p['case']==('top100' if mode.endswith('100') else 'top10'))
messages=[{k:m[k] for k in ('role','content')} for m in packet['context']]+[{'role':'user','content':packet['question']}]
with tempfile.TemporaryDirectory(prefix='badcase-replay-') as root:
 adapter=a.NativeCodexChatAdapter(jobs_dir=root,source_gateway=gateway,source_gateway_url='http://127.0.0.1:8791/api/v2/internal/chickenbro/source-query')
 start=time.monotonic();print(json.dumps({'mode':mode,'source':source,'started':time.time()}),flush=True)
 try:
  es=list(adapter.stream(prompt=json.dumps({'messages':messages},ensure_ascii=False),timeout_seconds=480))
  print(json.dumps({'mode':mode,'seconds':round(time.monotonic()-start,2),'answers':[e.get('text') for e in es if e.get('type')=='completed'],'calls':calls},ensure_ascii=False),flush=True)
 except Exception as e:print(json.dumps({'mode':mode,'error':type(e).__name__,'calls':calls}),flush=True)
http.shutdown()

"""Loopback-only worker tools; capabilities and execution survive API restart."""
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

from server.app.chickenbro.durable import ChatLeaseLost


class ToolRecorder:
    def __init__(self, guarded_connection, run_id):
        self.connect = guarded_connection
        self.run_id = run_id

    def execute(self, operation, arguments, invoke):
        call_id = uuid4()
        digest = hashlib.sha256(json.dumps(arguments,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT count(*) FROM chat.tool_results WHERE run_id=%s', (self.run_id,))
                if cur.fetchone()[0] >= 128:
                    return {'status':'blocked','facts':[], 'errorCode':'CHAT_TOOL_BUDGET_EXCEEDED',
                        'limitations':['Research budget exhausted; explain evidence gaps without further calls.']}
                cur.execute("""INSERT INTO chat.tool_results(run_id,call_id,operation,request_hash,state)
                    VALUES (%s,%s,%s,%s,'started')""",(self.run_id,call_id,operation,digest))
        try:
            result = invoke()
            encoded = json.dumps(result,ensure_ascii=False)
            if len(encoded.encode()) > 180000:
                result = {'status':'partial','facts':[], 'limitations':['Tool result exceeded the bounded response size. Narrow the query.']}
                encoded = json.dumps(result)
            with self.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("""UPDATE chat.tool_results SET state='completed',finished_at=now(),result_json=%s::jsonb
                        WHERE run_id=%s AND call_id=%s""", (encoded,self.run_id,call_id))
            return result
        except Exception:
            try:
                with self.connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""UPDATE chat.tool_results SET state='failed',finished_at=now()
                            WHERE run_id=%s AND call_id=%s""", (self.run_id,call_id))
            except ChatLeaseLost:
                pass
            raise


class RegisteredGateway:
    def __init__(self, host, gateway, recorder, kind):
        self.host, self.gateway, self.recorder, self.kind = host,gateway,recorder,kind

    def issue_capability(self, *args):
        token = self.gateway.issue_capability(*args)
        with self.host.lock:
            self.host.routes[token] = self
        return token

    def revoke(self, token):
        self.gateway.revoke(token)
        with self.host.lock:
            self.host.routes.pop(token,None)

    def execute(self, token, body):
        if self.kind == 'source':
            if set(body)-{'provider','target','options'}:
                raise ValueError('invalid source arguments')
            provider,target = body['provider'],body['target']
            return self.recorder.execute('source.'+str(provider)[:40],body,
                lambda:self.gateway.query(token,provider,target,body.get('options')))
        if set(body)-{'operation','arguments'}:
            raise ValueError('invalid simulation arguments')
        return self.recorder.execute('simc.'+str(body['operation'])[:40],body,
            lambda:self.gateway.execute(token,body['operation'],body.get('arguments',{})))


class WorkerToolServer:
    def __init__(self, port):
        self.routes = {}
        self.lock = threading.RLock()
        host = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):
                pass
            def do_POST(self):
                status = 200
                try:
                    kinds = {'/api/v2/internal/chickenbro/source-query':('source','X-Chickenbro-Source-Gateway'),
                             '/api/v2/internal/chickenbro/simc-tool':('simc','X-Chickenbro-Simulation-Gateway')}
                    kind,header = kinds[self.path]
                    token = self.headers.get(header,'')
                    with host.lock:
                        gateway = host.routes.get(token)
                    if gateway is None or gateway.kind != kind:
                        raise ChatLeaseLost('capability unavailable')
                    size = int(self.headers.get('Content-Length','0'))
                    if not 1 <= size <= 32768:
                        raise ValueError('request exceeds limit')
                    body = json.loads(self.rfile.read(size))
                    if not isinstance(body,dict):
                        raise ValueError('object required')
                    result = gateway.execute(token,body)
                except ChatLeaseLost:
                    status,result = 401,{'errorCode':'CHAT_EXECUTION_INACTIVE'}
                except Exception:
                    status,result = 422,{'errorCode':'CHAT_TOOL_UNAVAILABLE'}
                data = json.dumps(result,ensure_ascii=False).encode()
                self.send_response(status)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(data)))
                self.end_headers()
                try:
                    self.wfile.write(data)
                except OSError:
                    pass
        self.server = ThreadingHTTPServer(('127.0.0.1',port),Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True,name='chat-tools')

    def start(self):
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def register(self,gateway,recorder,kind):
        return RegisteredGateway(self,gateway,recorder,kind)

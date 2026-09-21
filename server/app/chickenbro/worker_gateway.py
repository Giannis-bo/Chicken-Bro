"""Loopback-only worker tools; capabilities and execution survive API restart."""
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

from server.app.chickenbro.durable import ChatLeaseLost


def tool_request_limit(kind):
    return 4_100_000 if kind == 'poe2' else 32_768


def tool_response_limit(operation):
    return 180_000


def source_request_hashes(operation, arguments):
    def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    raw=digest(arguments)
    if operation != 'source.warcraftlogs' or set(arguments)-{'provider','target','options'}:return raw,raw
    try:
        from server.app.chickenbro.wcl_source import normalize_wcl_report_url,validate_wcl_options
        from server.app.simulation.sources import parse_character_source_url
        parsed=parse_character_source_url(normalize_wcl_report_url(arguments['target']))
        options=validate_wcl_options(arguments.get('options'))
        if options.get('view') not in ('overview','healing'):return raw,raw
        target='https://www.warcraftlogs.com/reports/'+parsed.report_code
        params=[]
        if parsed.fight_id:params.append('fight='+str(parsed.fight_id))
        if parsed.actor_id:params.append('source='+str(parsed.actor_id))
        if params:target+='?'+'&'.join(params)
        return raw,digest({'provider':'warcraftlogs','target':target,'options':options})
    except (ValueError,TypeError,KeyError,AttributeError):return raw,raw


class ToolRecorder:
    def __init__(self, guarded_connection, run_id):
        self.connect = guarded_connection
        self.run_id = run_id

    def execute(self, operation, arguments, invoke, admit_reuse=None):
        call_id = uuid4()
        raw_digest,digest = source_request_hashes(operation,arguments)
        reused = None
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT count(*) FROM chat.tool_results WHERE run_id=%s', (self.run_id,))
                if cur.fetchone()[0] >= 128:
                    return {'status':'blocked','facts':[], 'errorCode':'CHAT_TOOL_BUDGET_EXCEEDED',
                        'limitations':['Research budget exhausted; explain evidence gaps without further calls.']}
                if operation == 'source.warcraftlogs' and (arguments.get('options') or {}).get('view') in ('overview','healing'):
                    cur.execute("""SELECT t.run_id,t.result_json FROM chat.tool_results t
                        JOIN chat.agent_runs prior ON prior.id=t.run_id
                        JOIN chat.agent_runs current ON current.id=%s AND current.user_id=prior.user_id
                            AND current.conversation_id=prior.conversation_id
                        WHERE t.operation=%s AND t.request_hash IN (%s,%s) AND t.state='completed'
                            AND t.started_at>now()-interval '6 hours'
                            AND t.result_json->>'status'='verified'
                            AND t.result_json @? '$.facts[*].fight ? (@.kill == true)'
                            AND NOT (t.result_json ? 'reuse')
                        ORDER BY t.started_at DESC LIMIT 1""",(self.run_id,operation,raw_digest,digest))
                    row=cur.fetchone()
                    if row:
                        reused=row[1]
                        reused['reuse']={'runId':str(row[0]),'upstreamCalls':0,'scope':'same account and conversation; completed fight; original result less than 6h old'}
                cur.execute("""INSERT INTO chat.tool_results(run_id,call_id,operation,request_hash,state,request_json)
                    VALUES (%s,%s,%s,%s,'started',%s::jsonb)""",(self.run_id,call_id,operation,digest,json.dumps(arguments,ensure_ascii=False) if operation.startswith('source.') else None))
        try:
            if reused is not None and admit_reuse is not None:
                error = admit_reuse()
                if error: reused = error
            result = reused if reused is not None else invoke()
            encoded = json.dumps(result,ensure_ascii=False)
            response_limit = tool_response_limit(operation)
            if len(encoded.encode()) > response_limit:
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

    def seed_evidence(self, token, evidence):
        return self.gateway.seed_evidence(token,evidence)

    def usage_recorder(self, token):
        return self.gateway.usage_recorder(token)

    def record_usage(self, token, usage):
        return self.gateway.record_usage(token,usage)

    def research_status(self, token):
        return self.gateway.research_status(token)

    def answer_evidence(self, token):
        return self.gateway.answer_evidence(token)

    def execute(self, token, body):
        if self.kind == 'source':
            if set(body)-{'provider','target','options'}:
                raise ValueError('invalid source arguments')
            provider,target = body['provider'],body['target']
            result = self.recorder.execute('source.'+str(provider)[:40],body,
                lambda:self.gateway.query(token,provider,target,body.get('options')),
                admit_reuse=lambda:self.gateway.reserve_scope(token,provider,target,body.get('options')))
            if result.get('reuse'):
                result = self.gateway.seed_evidence(token,result)
            return result
        if set(body)-{'operation','arguments'}:
            raise ValueError('invalid simulation arguments')
        prefix = 'poe2.' if self.kind == 'poe2' else 'simc.'
        return self.recorder.execute(prefix+str(body['operation'])[:40],body,
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
                             '/api/v2/internal/chickenbro/simc-tool':('simc','X-Chickenbro-Simulation-Gateway'),
                             '/api/v2/internal/chickenbro/poe2-tool':('poe2','X-Chickenbro-POE2-Gateway')}
                    kind,header = kinds[self.path]
                    token = self.headers.get(header,'')
                    with host.lock:
                        gateway = host.routes.get(token)
                    if gateway is None or gateway.kind != kind:
                        raise ChatLeaseLost('capability unavailable')
                    size = int(self.headers.get('Content-Length','0'))
                    request_limit = tool_request_limit(kind)
                    if not 1 <= size <= request_limit:
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

"""Cloud-only, isolated paired evaluation. Replay tools never call real providers.

Run and case modes require fresh empty output directories; interrupted campaigns
are retained as evidence and must never resume into their previous fixture state.
Only MCP mode restores fixture state, intentionally between turns of one case.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from uuid import uuid4


def schedule(case_ids, trials):
    rows=[]
    for trial in range(1,trials+1):
        for index,case in enumerate(case_ids):
            order=('old','new') if (trial+index)%2 else ('new','old')
            rows.extend({'caseId':case,'trial':trial,'variant':v} for v in order)
    return rows


def case_result(case_id,category,variant,trial,turns,expected_turns=None):
    expected_turns=len(turns) if expected_turns is None else expected_turns
    statuses=[t['status'] for t in turns]
    complete=bool(turns) and len(turns)==expected_turns and all(s=='succeeded' for s in statuses)
    return {'caseId':case_id,'category':category,'variant':variant,'trial':trial,
            'status':'timeout' if 'timeout' in statuses else 'failed' if 'failed' in statuses else 'succeeded' if complete else 'in_progress',
            'completeCase':complete,'expectedTurns':expected_turns,'completedTurns':statuses.count('succeeded'),
            'totalMs':sum(t['totalMs'] for t in turns),'quality':'unreviewed','turns':turns}


def tool_event(method,params,at_ms):
    item=params.get('item',{})
    if method not in ('item/started','item/completed') or item.get('type') not in ('mcpToolCall','webSearch'):
        return None
    return {'id':item.get('id'),'type':item['type'],'name':item.get('tool',item.get('name','webSearch')),
            'args':item.get('arguments',{}),'event':'start' if method=='item/started' else 'end','atMs':at_ms}


def replay_profile(original,repair_profile,command_args,definitions):
    # The adapter merges global config and explicitly disables all inherited
    # MCP servers/features. Preserve the experiment's original model effort.
    isolated=repair_profile(original)
    if 'model_reasoning_effort' in original:
        isolated['model_reasoning_effort']=original['model_reasoning_effort']
    else:isolated.pop('model_reasoning_effort',None)
    isolated['mcp_servers']['chickenbro_toolbox']={
        'enabled':True,'command':sys.executable,'args':command_args,'tool_timeout_sec':90,
        'tools':{t['name']:{'approval_mode':'approve'} for t in definitions}}
    return isolated


def timed_session_class(base,phase,sessions,epoch):
    class Timed(base):
        def __init__(self,*a,**kw):
            super().__init__(*a,**kw)
            self.phase=phase;self.events=[];self.phaseEvents=[];self.itemKinds=[]
            self.turnStartMs=None;self.firstDraftMs=None
            self.benchmarkSessionId=f'{phase}-{len(sessions)}';sessions.append(self)
        def send(self,message):
            if message.get('method')=='turn/start':self.turnStartMs=(time.monotonic()-epoch[0])*1000
            return super().send(message)
        def stream(self,**kwargs):
            self.phaseEvents.append({'phase':phase,'event':'start','atMs':(time.monotonic()-epoch[0])*1000})
            try:yield from super().stream(**kwargs)
            finally:self.phaseEvents.append({'phase':phase,'event':'end','atMs':(time.monotonic()-epoch[0])*1000})
        def _item_event(self,method,params):
            at=(time.monotonic()-epoch[0])*1000
            event=tool_event(method,params,at)
            if event:
                if event['id'] is not None:event['id']=self.benchmarkSessionId+':'+str(event['id'])
                event['phase']=phase;self.events.append(event)
            kind=params.get('item',{}).get('type')
            if kind and kind not in self.itemKinds:self.itemKinds.append(kind)
            result=super()._item_event(method,params)
            if result and result.get('type')=='delta' and self.firstDraftMs is None:self.firstDraftMs=at
            return result
    return Timed


def write_result(path,result):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)


def mcp(args):
    sys.path.insert(0,str(Path(args.source).resolve()))
    from server.chickenbro_native_mcp import TOOL_DEFINITIONS
    from agent_benchmark_fixtures import FixtureSession
    session=FixtureSession(args.case)
    state=Path(args.output)/'fixture-state.json'
    if state.exists():session.__dict__.update(json.loads(state.read_text()))
    definitions={d['name']:d for d in TOOL_DEFINITIONS}
    log=Path(args.output)/'receipts.jsonl'
    for line in sys.stdin:
        request=json.loads(line);ident=request.get('id');method=request.get('method');result={}
        if method=='initialize':result={'protocolVersion':'2025-03-26','capabilities':{'tools':{}},'serverInfo':{'name':'chickenbro-fixed-replay','version':'1'}}
        elif method=='tools/list':result={'tools':list(definitions.values())}
        elif method=='tools/call':
            params=request.get('params',{});name=params.get('name');arguments=params.get('arguments',{})
            started=time.monotonic()
            if name not in definitions:
                packet={'status':'unavailable','errorCode':'FIXTURE_TOOL_UNKNOWN'}
            elif name=='read_chickenbro_skill':
                from server.app.chickenbro.agent_skills import read_chickenbro_skill
                packet=read_chickenbro_skill(arguments)
            else:packet=session.call(name,arguments)
            state.write_text(json.dumps(session.__dict__,ensure_ascii=False))
            observed={k:v for k,v in packet.items() if k!='content'} if name=='read_chickenbro_skill' else packet
            with log.open('a') as handle:handle.write(json.dumps({'tool':name,'arguments':arguments,'result':observed,'elapsedMs':(time.monotonic()-started)*1000},ensure_ascii=False)+'\n')
            result={'content':[{'type':'text','text':json.dumps(packet,ensure_ascii=False)}],'isError':False}
        elif ident is None:continue
        print(json.dumps({'jsonrpc':'2.0','id':ident,'result':result},ensure_ascii=False),flush=True)


def production_environment():
    pid=subprocess.check_output(['systemctl','show','chickenbro-api','-p','MainPID','--value'],text=True).strip()
    assert pid.isdigit() and int(pid)>0
    env=dict(v.split('=',1) for v in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in v)
    os.environ.update(env)


def fresh_output(value):
    path=Path(value)
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError('Benchmark output must be a fresh empty directory')
    path.mkdir(parents=True,exist_ok=True)
    # Exclusive ownership also rejects simultaneous starters of an empty root.
    try:
        with (path/'.benchmark-started').open('x',encoding='utf-8') as handle:
            handle.write('Fresh campaign or case; resumption is not supported.\n')
    except FileExistsError:
        raise ValueError('Benchmark output must be a fresh empty directory') from None
    os.chmod(path,0o700)
    return path


def run_case(args):
    out=fresh_output(args.output)
    production_environment()
    source=Path(args.source).resolve();sys.path.insert(0,str(source))
    from server.app.chickenbro import codex_adapter as adapter
    from server.app.chickenbro.answer_grounding import collect_evidence
    from server.app.chickenbro.simulation_grounding import collect_simulation_evidence
    from agent_benchmark_fixtures import CASES
    from agent_benchmark_metrics import summarize_timing
    case=next(c for c in CASES if c['id']==args.case)
    profile_original=adapter._load_profile
    def profile(name,**kwargs):
        p=profile_original(name,**kwargs)
        from server.chickenbro_native_mcp import TOOL_DEFINITIONS
        return replay_profile(p,adapter._repair_profile,
            [str(Path(__file__).resolve()),'mcp','--source',str(source),'--case',args.case,'--output',str(out)],
            TOOL_DEFINITIONS)
    adapter._load_profile=profile
    sessions=[];epoch=[time.monotonic()]
    adapter._ResearchSession=timed_session_class(adapter._ResearchSession,'primary',sessions,epoch)
    adapter._RepairSession=timed_session_class(adapter._RepairSession,'repair',sessions,epoch)
    class Gateway:
        def issue_capability(self,*a):return 'isolated-fixture-capability'
        def revoke(self,*a):pass
        def answer_evidence(self,*a):
            evidence=None
            if (out/'receipts.jsonl').exists():
                for line in (out/'receipts.jsonl').read_text().splitlines():
                    evidence=collect_evidence(evidence,json.loads(line)['result'])
            return evidence or {'reports':[],'groups':[],'truncated':False}
    class SimGateway(Gateway):
        def answer_evidence(self,*a):
            evidence=None
            if (out/'receipts.jsonl').exists():
                for line in (out/'receipts.jsonl').read_text().splitlines():evidence=collect_simulation_evidence(evidence,json.loads(line)['result'])
            return evidence or {}
    runtime=adapter.NativeCodexChatAdapter(enabled=True,jobs_dir=out/'jobs',source_gateway=Gateway(),simulation_gateway=SimGateway(),runtime_revision='benchmark:'+args.variant)
    history=[];turns=[]
    for index,prompt in enumerate(case['turns']):
        epoch[0]=time.monotonic();sessions.clear();history.append({'role':'user','content':prompt})
        result={'status':'failed','errorCode':'','answer':'','events':[], 'startedAt':datetime.now(timezone.utc).isoformat()};run_id=uuid4()
        try:
            for event in runtime.stream(prompt=json.dumps({'messages':history,'benchmarkScope':'All provider results in this run are fixed synthetic test fixtures, not live game or actual engine evidence.'},ensure_ascii=False),timeout_seconds=args.timeout,tool_context=SimpleNamespace(run_id=run_id)):
                if event['type']=='completed':result.update(status='succeeded',answer=event['text'])
        except Exception as exc:
            code=str(getattr(exc,'code',type(exc).__name__));result.update(status='timeout' if 'TIMEOUT' in code else 'failed',errorCode=code)
        result['totalMs']=round((time.monotonic()-epoch[0])*1000,3)
        result['finishedAt']=datetime.now(timezone.utc).isoformat()
        result['runId']=str(run_id);result['turnIndex']=index
        result['events']=[e for session in sessions for e in session.events]
        result['modelUsage']=[{'phase':session.phase,'sessionId':session.benchmarkSessionId,'usage':session.token_usage} for session in sessions]
        result['phaseEvents']=[e for session in sessions for e in session.phaseEvents]
        result['runtimeItemKinds']=sorted({k for session in sessions for k in session.itemKinds})
        result['startupMs']=sessions[0].turnStartMs if sessions else None
        result['firstDraftMs']=sessions[0].firstDraftMs if sessions else None
        result['timing']=summarize_timing(result['events'],result['totalMs'])
        turns.append(result)
        output=case_result(case['id'],case['category'],args.variant,args.trial,turns,expected_turns=len(case['turns']))
        output.update(source=str(source),coreSha256=hashlib.sha256((source/'server/app/chickenbro/agent/AGENTS.md').read_bytes()).hexdigest(),fixtureSha256=hashlib.sha256(Path(__file__).with_name('agent_benchmark_fixtures.py').read_bytes()).hexdigest(),rubric=case['rubric'],requiredEvidence=case.get('requiredEvidence',[]),configuration={k:profile_original(os.environ['WOW_CODEX_PROFILE']).get(k) for k in ('model','model_reasoning_effort')})
        write_result(out/'result.json',output)
        print(json.dumps({'caseId':args.case,'variant':args.variant,'trial':args.trial,'turn':index,'status':result['status'],'totalMs':result['totalMs']},ensure_ascii=False),flush=True)
        if result['status']!='succeeded':break
        history.append({'role':'assistant','content':result['answer']})


def orchestrate(args):
    root=fresh_output(args.output)
    fixture_source=getattr(args,'new',None) or getattr(args,'old',None)
    if fixture_source:sys.path.insert(0,str(Path(fixture_source).resolve()))
    from agent_benchmark_fixtures import CASES
    selected=args.cases or [c['id'] for c in CASES]
    planned=schedule(selected,args.trials)
    (root/'schedule.json').write_text(json.dumps(planned,indent=2))
    repeated=0;last_error=None
    for index,row in enumerate(planned):
        dest=root/(row['caseId']+'-'+str(row['trial'])+'-'+row['variant'])
        result_path=dest/'result.json'
        proc=subprocess.run([sys.executable,str(Path(__file__).resolve()),'case','--source',args.old if row['variant']=='old' else args.new,'--variant',row['variant'],'--case',row['caseId'],'--trial',str(row['trial']),'--output',str(dest),'--timeout',str(args.timeout)],check=False)
        result=json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else {**row,'quality':'unreviewed','totalMs':None}
        if result.get('status') not in ('failed','timeout') and not (result.get('status')=='succeeded' and result.get('completeCase')):
            result.update(status='failed',completeCase=False,errorCode='RUNNER_PROCESS_FAILURE')
            result['processExitCode']=proc.returncode
            dest.mkdir(exist_ok=True);write_result(result_path,result)
        if result.get('status') in ('failed','timeout'):
            error=result.get('errorCode') or next((t.get('errorCode') for t in reversed(result.get('turns',[])) if t.get('errorCode')),result['status'])
            repeated=repeated+1 if error==last_error else 1;last_error=error
            if repeated>=getattr(args,'max_consecutive_failures',2):
                write_result(root/'stopped.json',{'reason':'repeated_failure','errorCode':error,'consecutiveFailures':repeated,'remainingCount':len(planned)-index-1,'lastRun':row})
                break
        else:repeated=0;last_error=None


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('mcp','case','run'))
    p.add_argument('--source');p.add_argument('--variant',choices=('old','new'));p.add_argument('--case');p.add_argument('--trial',type=int,default=1)
    p.add_argument('--output',required=True);p.add_argument('--old');p.add_argument('--new');p.add_argument('--cases',nargs='+');p.add_argument('--trials',type=int,default=3);p.add_argument('--timeout',type=int,default=240)
    p.add_argument('--max-consecutive-failures',type=int,default=2)
    args=p.parse_args()
    {'mcp':mcp,'case':run_case,'run':orchestrate}[args.mode](args)


if __name__=='__main__':main()

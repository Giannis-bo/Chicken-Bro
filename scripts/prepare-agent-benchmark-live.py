"""Prepare, but never launch, the bounded cloud HTTP A/B diagnostic.

Run on the cloud host with its existing runtime Python. This writes live.py and
worker.py under --output. Invoke live.py separately for each pinned release:
  python live.py candidate SOURCE --label old-1 --variant old
  python live.py candidate SOURCE --label current-1 --variant current
Reverse order for a second pair if authorized. The first invocation selects and
pins an existing synthetic-owner SimC pair; every later invocation reuses it.
The existing candidate validation lock and ports are shared with other smokes.
No production mode, engine submission, new production identity or model call is
performed by this preparer. Raw reports stay private; do not publish them whole.
"""
import argparse
import ast
from pathlib import Path


PIN_SOURCE = r'''
# LF-normalized hashes read from the two exact Git commits, before any launch.
source_names=['server/app/chickenbro/agent/AGENTS.md','server/app/chickenbro/codex_adapter.py','server/chickenbro_native_mcp.py']
expected_source={'old':['0be8630a5f86dac8119456b6d81e88799aa172878efdddf96d1bdcb7081c2762',
    '26cea28ec960d27dc0fdec0666a8f6530b58d0cd01b660bc761cfa4b82e88932',
    'a6b301f58290743a2442cd25b6e8063b07a27d2998817df9b8d02630a1ed3838'],
    'current':['5371395db69edd75440429b570e419dc4f682ff0b6d1122b198867a98dc60742',
    '2ca8a046dc0c36ed89b77a881a09dae36542e2e222b3f11b349b971e7c228f12',
    '46da9d913dc1ba4926eafbad1aa55e4bd3d740afd141a90e8602363af9b8dbaa']}
for name,digest in zip(source_names,expected_source[a.variant]):
    assert hashlib.sha256((Path(a.source)/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==digest, 'Pinned source mismatch: '+name
'''


WORKER = r'''"""Benchmark-only process wrapper; source releases are never edited."""
import runpy
from server.app.chickenbro.simulation_tools import SimulationToolGateway
original = SimulationToolGateway._execute
def readonly(self, token, operation, arguments):
    self._authorized(token)
    if operation not in {'get', 'list', 'compare'}:
        return {'sourceKey':'simc','status':'blocked','errorCode':'BENCHMARK_READ_ONLY',
                'facts':[], 'evidenceRefs':[], 'limitations':['This diagnostic permits completed result reads and comparison only.']}
    return original(self, token, operation, arguments)
SimulationToolGateway._execute = readonly
runpy.run_module('server.app.worker.main', run_name='__main__')
'''


PIN_FIXTURES = r'''
    fixture_path=Path(a.fixtures)
    if fixture_path.exists():
        fixture=json.loads(fixture_path.read_text())
    else:
        # Only already-existing synthetic identities; no accounts are created.
        rows=c.execute("""SELECT j.id,j.user_id,j.snapshot_id,j.runtime_revision,j.compiler_revision,
                   q.payload_json,r.primary_metric_value
            FROM simc.simulation_jobs j JOIN simc.simulation_results r ON r.job_id=j.id AND r.user_id=j.user_id
            JOIN ops.job_queue q ON q.id=j.id AND q.aggregate_id=j.id
            WHERE j.status='succeeded' AND r.primary_metric_value>0
              AND q.domain='simc' AND q.command_type='run_simulation'
              AND EXISTS (SELECT 1 FROM identity.user_identities i WHERE i.user_id=j.user_id
                AND i.provider='qq' AND (i.provider_subject LIKE 'simc%%smoke%%' OR i.provider_subject LIKE 'badcase%%'))
            ORDER BY j.updated_at DESC,j.id LIMIT 100""").fetchall()
        variant_fields={'equipmentOverrides','gemOverrides','talentOverrides','actionLists','food','statBonuses'}
        groups={}; pair=None
        for row in rows:
            payload=row[5] if isinstance(row[5],dict) else json.loads(row[5])
            scenario=payload.get('scenario')
            if not isinstance(scenario,dict):continue
            controls={k:v for k,v in scenario.items() if k not in variant_fields}
            key=tuple(str(v) for v in row[1:5])+(json.dumps(controls,sort_keys=True),)
            if key in groups:
                pair=(groups[key],row);break
            groups[key]=row
        assert pair, 'No completed synthetic same-owner/snapshot/runtime/control pair; no jobs will be created'
        owner=pair[0][1]
        other_owner=c.execute("""SELECT DISTINCT i.user_id FROM identity.user_identities i
            WHERE i.provider='qq' AND i.user_id<>%s
            AND (i.provider_subject LIKE 'simc%%smoke%%' OR i.provider_subject LIKE 'badcase%%')
            ORDER BY i.user_id LIMIT 1""",(owner,)).fetchone()
        assert other_owner, 'Existing second synthetic owner required'
        scenarios=[v[5]['scenario'] if isinstance(v[5],dict) else json.loads(v[5])['scenario'] for v in pair]
        fixture={'schemaVersion':1,'owner':str(owner),'otherOwner':str(other_owner[0]),
            'jobs':[str(v[0]) for v in pair],'snapshotId':str(pair[0][2]),
            'runtimeRevision':str(pair[0][3]),'compilerRevision':str(pair[0][4]),
            'controls':{k:v for k,v in scenarios[0].items() if k not in variant_fields},
            'changes':{k:{'baseline':scenarios[0].get(k),'variant':scenarios[1].get(k)}
                       for k in sorted(variant_fields) if scenarios[0].get(k)!=scenarios[1].get(k)},
            'wcl':{'code':'LPV3pf4nM9yhKw1Y','fightId':7,'actors':[3,481],
                   'relativeStartMs':1250000,'relativeEndMs':1265000}}
        fixture_path.write_text(json.dumps(fixture,indent=2))
        fixture_path.chmod(0o600)
    from uuid import UUID
    owners=[UUID(fixture['owner']),UUID(fixture['otherOwner'])]
    assert owners[0]!=owners[1] and len(fixture['jobs'])==2 and len(set(fixture['jobs']))==2
    for owner in owners:
        assert c.execute("""SELECT count(*) FROM identity.user_identities WHERE user_id=%s AND provider='qq'
            AND (provider_subject LIKE 'simc%%smoke%%' OR provider_subject LIKE 'badcase%%')""",(owner,)).fetchone()[0]>0
    for job_id in fixture['jobs']:
        row=c.execute('SELECT user_id,snapshot_id,status,runtime_revision,compiler_revision FROM simc.simulation_jobs WHERE id=%s',(UUID(job_id),)).fetchone()
        assert row and row[0]==owners[0] and str(row[1])==fixture['snapshotId'] and row[2]=='succeeded'
        assert str(row[3])==fixture['runtimeRevision'] and str(row[4])==fixture['compilerRevision']
    report['fixtureSha256']=hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    report['fixture']=fixture
'''


HTTP_CASES = r'''
base='http://127.0.0.1:18890'
csrf=secrets.token_urlsafe(24);cookie=env['WOW_WEB_COOKIE_NAME'];csrf_cookie=env['WOW_WEB_CSRF_COOKIE_NAME']
headers={'Host':'www.chickenbro.cloud','Origin':'https://www.chickenbro.cloud',
    'Cookie':f'{cookie}={tokens[0]}; {csrf_cookie}={csrf}','X-CSRF-Token':csrf}
other={'Host':'www.chickenbro.cloud','Cookie':cookie+'='+tokens[1]}
report.update(variant=a.variant,requestedCommit={'old':'b406fc9155a03edba9e95912713606736fb2a1bd',
    'current':'2294cb95095a3822e1f4e2c43e225bf0bfdb2f63'}[a.variant],cases=[],
    limitations=['Real upstream/cache state is not controlled. This is not the fixed replay benchmark.',
    'HTTP elapsed includes server queue, model, tools, validation and SSE delivery; provider reasoning breakdown is unknown.',
    'Tool receipt intervals include gateway work and may overlap; they exclude native search and local workflow reads.',
    'Semantic quality requires manual review of answer and actual receipts. A succeeded run alone is not acceptance.'])
report['sourceHashes']={name:hashlib.sha256((Path(a.source)/name).read_bytes()).hexdigest() for name in
    ['server/app/chickenbro/agent/AGENTS.md','server/app/chickenbro/codex_adapter.py','server/chickenbro_native_mcp.py']}
from server.app.chickenbro.codex_adapter import _load_profile
model_profile=_load_profile(env.get('WOW_CODEX_PROFILE'),allow_simulation=True)
report['modelProfile']={k:model_profile.get(k) for k in ('model','model_reasoning_effort','model_provider','web_search')}
assert model_profile.get('model')=='gpt-6-astra' and model_profile.get('model_reasoning_effort')=='low', 'Expected Astra/low profile'
report_path=Path(__file__).parent/(a.label+'-private.json')
def save():
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str));report_path.chmod(0o600)
atexit.register(save)
with httpx.Client(base_url=base,timeout=510) as client:
    def req(method,path,status=200,**kwargs):
        r=client.request(method,'/api/v2'+path,headers=kwargs.pop('headers',headers),**kwargs)
        assert r.status_code==status,(method,path,r.status_code)
        return r
    for i in range(30):
        try:
            req('GET','/chat/conversations');break
        except (httpx.TransportError,AssertionError):time.sleep(1)
    else:raise RuntimeError('Candidate API failed to start')
    def create(title):
        return req('POST','/chat/conversations',201,json={'title':title},
                   headers={**headers,'Idempotency-Key':str(uuid4())}).json()['id']
    # Fixture reads and public overview are preflight, excluded from measured asks.
    for job_id in fixture['jobs']:
        result=req('GET','/simc/jobs/'+job_id).json()
        assert result['status']=='succeeded' and result['result']['metricValue']>0
        assert result['snapshotId']==fixture['snapshotId']
        req('GET','/simc/jobs/'+job_id,404,headers=other)
    report['checks']['positiveOwnedResultsAndSecondOwner404']=True
    with psycopg.connect(env['WOW_DATABASE_URL']) as c:
        initial_jobs=c.execute('SELECT count(*) FROM simc.simulation_jobs').fetchone()[0]
    wcl=fixture['wcl']; wcl_ok=False
    try:
        from server.app.chickenbro.wcl_source import _graphql
        query='query($code:String!){reportData{report(code:$code){code fights(fightIDs:[7]){id name startTime endTime friendlyPlayers} masterData{actors{id name type subType}}}}}'
        packet=_graphql(query,{'code':wcl['code']})
        data=(packet.get('reportData') or {}).get('report') or {}
        fight=next(f for f in data.get('fights',[]) if f.get('id')==wcl['fightId'])
        actors=[v for v in (data.get('masterData') or {}).get('actors',[]) if v.get('id') in wcl['actors']]
        assert len(actors)==2 and all(v['type']=='Player' for v in actors)
        assert set(wcl['actors']).issubset(set(fight['friendlyPlayers']))
        assert 0<=wcl['relativeStartMs']<wcl['relativeEndMs']<=fight['endTime']-fight['startTime']
        report['wclPreflight']={'code':data['code'],'fight':fight,'actors':actors};wcl_ok=True
    except Exception as exc:
        report['wclPreflight']={'status':'failed','errorType':type(exc).__name__}
    save()
    prompts=[('wcl-two-actors-window',
        '查询公开日志 https://www.warcraftlogs.com/reports/LPV3pf4nM9yhKw1Y?fight=7 。只比较本场actor 3 Giannis与actor 481 Fusionbolt，在战斗相对20:50到21:05的施法记录。先核对角色与战斗身份，用这个15秒窗口的施法事件比较频次和先后，列出关键相对时间；不遍历整场，不查榜单，不提交模拟。相同时间不能判定先后，缺少需求与替代收益证据时不要直接判定操作错误；取不到明确说明。'),
        ('simc-completed-pair',
        '读取我已有的两份模拟任务 '+fixture['jobs'][0]+' 和 '+fixture['jobs'][1]+
        '，核对是否同快照、引擎和场景控制条件，再使用比较工具报告实际DPS差值、百分比与误差边界；说明这两份实际改变了什么。只读取和比较已完成任务，不准备角色、不创建或重跑模拟、不查询攻略。')]
    for case_id,prompt in prompts:
        if case_id.startswith('wcl') and not wcl_ok:
            report['cases'].append({'caseId':case_id,'status':'preflight_failed','measured':False});save();continue
        cid=create('live-benchmark:'+a.label+':'+case_id);key=str(uuid4());mid=str(uuid4())
        record={'caseId':case_id,'prompt':prompt,'conversationId':cid,'status':'started','qualityStatus':'pending_manual_review'}
        report['cases'].append(record);save()
        before=set(Path(env['WOW_CODEX_JOBS_DIR']).glob('*/native-tool-observations.jsonl'))
        started=time.monotonic();response=None
        try:
            response=req('POST','/chat/conversations/'+cid+'/messages/stream',
                json={'content':prompt,'clientMessageId':mid},headers={**headers,'Idempotency-Key':key})
        except Exception as exc:record['transportErrorType']=type(exc).__name__
        record['elapsedSeconds']=round(time.monotonic()-started,6)
        with psycopg.connect(env['WOW_DATABASE_URL']) as c:
            row=c.execute('SELECT id,status,public_error_code,model_usage FROM chat.agent_runs WHERE user_id=%s AND conversation_id=%s ORDER BY started_at DESC LIMIT 1',(owners[0],cid)).fetchone()
            answer=c.execute("SELECT content FROM chat.messages WHERE conversation_id=%s AND role='assistant' ORDER BY created_at DESC LIMIT 1",(cid,)).fetchone()
            tools=c.execute('SELECT operation,state,started_at,finished_at,result_json FROM chat.tool_results WHERE run_id=%s ORDER BY started_at',(row[0],)).fetchall() if row else []
        record.update(runId=str(row[0]) if row else None,runStatus=row[1] if row else None,
            errorCode=row[2] if row else None,modelUsage=row[3] if row else None,finalAnswer=answer[0] if answer else '',
            sseCompleted=response is not None and 'event: completed' in response.text,
            toolReceipts=[{'tool':op,'state':state,'startedAt':start.isoformat(),'finishedAt':end.isoformat() if end else None,'result':result}
                for op,state,start,end,result in tools])
        # Old lacks run-identity files: no broad fallback collection is allowed.
        native=[]
        for path in set(Path(env['WOW_CODEX_JOBS_DIR']).glob('*/native-tool-observations.jsonl'))-before:
            identity=path.parent/'run-identity.json'
            if identity.is_file() and json.loads(identity.read_text()).get('runId')==record['runId']:
                native.extend(json.loads(line) for line in path.read_text().splitlines() if line.strip())
        record['nativeObservations']=native
        record['nativeBinding']='exact_run_id' if a.variant=='current' else 'unavailable_in_old_version'
        record['status']='completed' if record['runStatus']=='succeeded' and record['sseCompleted'] else 'failed'
        try:
            req('GET','/chat/conversations/'+cid,404,headers=other)
            record['secondOwner404']=True
            # Replay only terminal executions; retrying an unfinished transport is not a second benchmark.
            if record['runStatus'] in {'succeeded','failed'}:
                replay=req('POST','/chat/conversations/'+cid+'/messages/stream',
                    json={'content':prompt,'clientMessageId':mid},headers={**headers,'Idempotency-Key':key})
                with psycopg.connect(env['WOW_DATABASE_URL']) as c:
                    count=c.execute('SELECT count(*) FROM chat.agent_runs WHERE conversation_id=%s',(cid,)).fetchone()[0]
                record['idempotentReplay']=count==1
                assert count==1
        except Exception as exc:record['verificationErrorType']=type(exc).__name__;record['status']='failed'
        save();print(json.dumps({'caseId':case_id,'status':record['status'],'elapsedSeconds':record['elapsedSeconds']}),flush=True)
        if record['runStatus'] not in {'succeeded','failed'}:
            report['stoppedForActiveRun']=True;break
    with psycopg.connect(env['WOW_DATABASE_URL']) as c:
        report['checks']['noNewSimcJobs']=c.execute('SELECT count(*) FROM simc.simulation_jobs').fetchone()[0]==initial_jobs
    save()
    assert report['checks']['noNewSimcJobs']
cleanup();tokens.clear();children.clear();save()
'''


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Reviewed smoke anchor changed: ' + old[:70])
    return text.replace(old, new, 1)


def build(source, output):
    prefix = source[:source.index("base='http://127.0.0.1:18890'")]
    prefix = replace_once(prefix, "p.add_argument('mode',choices=['candidate','production'])", "p.add_argument('mode',choices=['candidate'])")
    prefix = replace_once(prefix, "p.add_argument('--label',required=True);a=p.parse_args()",
        "p.add_argument('--label',required=True);p.add_argument('--variant',required=True,choices=['old','current']);"
        "p.add_argument('--fixtures',default=str(Path(__file__).parent/'fixtures-private.json'));a=p.parse_args();"
        "assert re.fullmatch(r'[A-Za-z0-9_-]{1,70}',a.label)")
    prefix = replace_once(prefix, 'prod_pid=subprocess.check_output', PIN_SOURCE+'\nprod_pid=subprocess.check_output')
    prefix = replace_once(prefix, "assert urlsplit(env['WOW_DATABASE_URL']).path=='/chickenbro_prod'",
        "assert urlsplit(env['WOW_DATABASE_URL']).path=='/chickenbro_prod'\n"
        "assert env.get('WOW_CHAT_DURABLE_ENABLED')=='1', 'Read-only wrapper requires durable worker routing'")
    prefix = prefix.replace('/var/lib/chickenbro-skills-candidate-20260912', '/var/lib/chickenbro-agent-benchmark-live-candidate-20260912')
    prefix = replace_once(prefix,
        'assert c.execute("SELECT count(*) FROM chat.agent_runs WHERE status=\'streaming\'").fetchone()[0]==0',
        'assert c.execute("SELECT (SELECT count(*) FROM chat.agent_runs WHERE status=\'streaming\')+'
        '(SELECT count(*) FROM chat.executions WHERE stage IN (\'pending\',\'running\'))").fetchone()[0]==0')
    start = prefix.index("    if a.mode=='candidate':\n        owners=[uuid4(),uuid4()]")
    end = prefix.index('    for uid in owners:', prefix.index('    else:', start))
    prefix = prefix[:start] + PIN_FIXTURES + prefix[end:]
    prefix = replace_once(prefix, "['-m','server.app.worker.main','--worker-id','badcase-general-candidate']",
                          repr(['-c', WORKER, '--worker-id', 'benchmark-live-candidate']))
    # Each invocation has a private job directory; do not inherit old observations.
    prefix = replace_once(prefix, "WOW_CODEX_JOBS_DIR=str(private/'jobs')", "WOW_CODEX_JOBS_DIR=str(private/('jobs-'+a.label))")
    script = prefix + HTTP_CASES
    ast.parse(script)
    ast.parse(WORKER)
    return script


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('/var/lib/chickenbro-agent-benchmark-20260912/live'))
    parser.add_argument('--smoke-source', type=Path, default=Path('/var/lib/chickenbro-skills-release-20260912/smoke.py'))
    args = parser.parse_args()
    script = build(args.smoke_source.read_text(), args.output)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name, content in [('live.py', script), ('worker.py', WORKER)]:
        path = args.output/name
        path.write_text(content, encoding='utf-8');path.chmod(0o600)
    print('Prepared live.py and worker.py; no services or model tests started.')


if __name__ == '__main__':
    main()

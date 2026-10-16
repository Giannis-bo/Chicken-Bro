"""Actual source -> restricted model -> formatter; no inbox/outbox writes."""
import json,os,subprocess,time
from pathlib import Path
from dataclasses import asdict

pid=subprocess.check_output(['systemctl','show','chickenbro-qq-official.service','--property=MainPID','--value'],text=True).strip()
for item in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0'):
    if b'=' not in item:continue
    k,v=item.decode().split('=',1)
    if k.startswith(('WOW_CODEX_','WOW_CHICKENBRO_CODEX_','WOW_WARCRAFTLOGS_')) or k in ('CODEX_HOME','HOME','PATH','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY'):os.environ[k]=v
from server.app.channels.qq_official.battle_narrative import BattleNarrative
from server.app.channels.qq_official.battle_commands import parse_battle,format_battle
from server.app.channels.qq_official.query_service import QueryService

class Count:
    def __init__(self,adapter):self.adapter=adapter;self.calls=0
    def stream(self,**kwargs):
        self.calls+=1
        yield from self.adapter.stream(**kwargs)

results=[]
for name,url in [('raid_kill','https://www.warcraftlogs.com/reports/mZBg8DbyNdTrXcFL?fight=3'),('key_last','https://cn.warcraftlogs.com/reports/kNBvnCLXjqPQZhdg/#type=damage-done&fight=last&source=all')]:
    writer=BattleNarrative.configured();count=Count(writer.adapter);writer.adapter=count
    service=QueryService(None,None,battle_writer=writer)
    start=time.monotonic()
    try:p=service._query({'request':asdict(parse_battle('/战斗分析 '+url))})
    finally:service.close()
    messages={k:format_battle(p,k) for k in ('battle_summary','battle_good','battle_review')}
    before=count.calls
    # JSON round-trip is the actual persistent-context boundary.
    detail=writer.apply(json.loads(json.dumps(p)))
    cache_calls=count.calls-before
    result={'name':name,'packet':p,'messages':messages,'seconds':round(time.monotonic()-start,2),'modelCalls':count.calls,'detailAdditionalModelCalls':cache_calls}
    results.append(result)
    output=Path('/tmp/qq-battle-narrative-source-'+str(os.getpid())+'.json')
    output.write_text(json.dumps({'qqMessagesSent':0,'inboxWrites':0,'root':os.getcwd(),'results':results},ensure_ascii=False,indent=2))
    print(json.dumps({'name':name,'status':p.get('status'),'narrative':p.get('narrative',{}).get('status'),'errorCode':p.get('narrative',{}).get('errorCode'),'sourceCalls':p.get('sourceCalls'),'seconds':result['seconds'],'modelCalls':count.calls,'cacheAdditionalModelCalls':cache_calls,'lengths':{k:len(v) for k,v in messages.items()},'evidence':str(output)},ensure_ascii=False),flush=True)
    assert p['status']=='ready' and p['narrative']['status']=='ready'
    assert count.calls==1 and cache_calls==0
    assert all(len(v)<=1200 for v in messages.values())
    print(json.dumps(messages,ensure_ascii=False),flush=True)

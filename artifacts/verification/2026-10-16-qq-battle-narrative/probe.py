"""Cloud evidence replay through the actual restricted writer; never sends QQ."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

pid=subprocess.check_output(['systemctl','show','chickenbro-qq-official.service','--property=MainPID','--value'],text=True).strip()
for item in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0'):
    if b'=' not in item:continue
    k,v=item.decode().split('=',1)
    if k.startswith(('WOW_CODEX_','WOW_CHICKENBRO_CODEX_')) or k in ('CODEX_HOME','HOME','PATH','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY'):
        os.environ[k]=v
from server.app.channels.qq_official.battle_narrative import BattleNarrative
from server.app.channels.qq_official.battle_commands import format_battle

class Recording:
    def __init__(self,adapter):self.adapter=adapter;self.raw=None;self.error=None
    def stream(self,**kwargs):
        try:
            for event in self.adapter.stream(**kwargs):
                if event.get('type')=='completed':self.raw=event.get('text')
                yield event
        except Exception as e:
            self.error=type(e).__name__;raise

base=json.loads(Path('/tmp/qq-battle-narrative-cases.json').read_text())
results=[]
for case in base['results']:
    if sys.argv[1:] and case['name'] not in sys.argv[1:]:continue
    writer=BattleNarrative.configured();capture=Recording(writer.adapter);writer.adapter=capture
    start=time.monotonic();p=writer.apply(case['packet'])
    texts={k:format_battle(p,k) for k in ('battle_summary','battle_good','battle_review')}
    result={'name':case['name'],'packet':p,'messages':texts,'raw':capture.raw,'errorType':capture.error}
    results.append(result)
    print(json.dumps({'name':case['name'],'status':p['narrative']['status'],'seconds':round(time.monotonic()-start,2),'errorType':capture.error},ensure_ascii=False),flush=True)
    if p['narrative']['status']=='ready':print(json.dumps(texts,ensure_ascii=False),flush=True)
    else:print(json.dumps({'raw':capture.raw},ensure_ascii=False),flush=True)
output=Path('/tmp/qq-battle-narrative-probe-'+str(os.getpid())+'.json')
output.write_text(json.dumps({'qqMessagesSent':0,'results':results},ensure_ascii=False,indent=2))
print('evidence='+str(output),flush=True)

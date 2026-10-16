"""Cloud model replay from the exact failed source packet, no QQ writes."""
import json,os,subprocess,sys,time
from pathlib import Path
pid=subprocess.check_output(['systemctl','show','chickenbro-qq-official.service','--property=MainPID','--value'],text=True).strip()
for item in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0'):
 if b'=' not in item:continue
 key,value=item.decode().split('=',1)
 if key.startswith(('WOW_CODEX_','WOW_CHICKENBRO_CODEX_')) or key in ('CODEX_HOME','HOME','PATH','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY'):os.environ[key]=value
from server.app.channels.qq_official.battle_narrative import BattleNarrative
from server.app.channels.qq_official.battle_commands import format_battle
class Recording:
 def __init__(self,adapter):self.adapter=adapter;self.raw=None;self.calls=0
 def stream(self,**kwargs):
  self.calls+=1
  for e in self.adapter.stream(**kwargs):
   if e.get('type')=='completed':self.raw=e.get('text')
   yield e
p=json.loads(Path('/tmp/qq-battle-summary-binding-case.json').read_text())
writer=BattleNarrative.configured();capture=Recording(writer.adapter);writer.adapter=capture
start=time.monotonic();writer.apply(p)
texts={k:format_battle(p,k) for k in ('battle_summary','battle_good','battle_review')}
if p['narrative']['status']=='ready':writer.apply(json.loads(json.dumps(p)))
output=Path('/tmp/qq-battle-summary-binding-probe-'+str(os.getpid())+'.json')
output.write_text(json.dumps({'root':os.getcwd(),'packet':p,'messages':texts,'raw':capture.raw,'modelCalls':capture.calls,'qqMessagesSent':0},ensure_ascii=False,indent=2))
print(json.dumps({'status':p['narrative']['status'],'errorCode':p['narrative'].get('errorCode'),'seconds':round(time.monotonic()-start,2),'modelCalls':capture.calls,'lengths':{k:len(v) for k,v in texts.items()},'evidence':str(output)},ensure_ascii=False),flush=True)
print(json.dumps(texts,ensure_ascii=False),flush=True)
if p['narrative']['status']!='ready':print(json.dumps({'raw':capture.raw},ensure_ascii=False),flush=True)
assert p['narrative']['status']=='ready'
assert capture.calls==1

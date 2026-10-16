import json
from pathlib import Path
from server.app.channels.qq_official.battle_narrative import BattleNarrative
from server.app.channels.qq_official.battle_commands import format_battle
from server.app.channels.qq_official.query_service import QueryService
class Forbidden:
 calls=0
 def stream(self,**kwargs):
  self.calls+=1
  raise AssertionError('unexpected model call')
case=json.loads(Path('/tmp/qq-battle-summary-binding-probe-2339381.json').read_text())
a=Forbidden();service=QueryService(None,None,battle_writer=BattleNarrative(a))
try:
 for kind in ('battle_good','battle_review'):
  p=service._query({'request':{'kind':kind},'battle_context':case['packet']})
  assert p['narrative']['status']=='ready'
  assert format_battle(p,kind)==case['messages'][kind]
 assert a.calls==0
finally:service.close()
print(json.dumps({'root':str(Path.cwd()),'reportCode':p['reportCode'],'fightId':p['fightId'],'narrativeVersion':p['narrative']['version'],'sameMessages':True,'additionalSourceCalls':0,'additionalModelCalls':a.calls,'qqMessagesSent':0},indent=2))

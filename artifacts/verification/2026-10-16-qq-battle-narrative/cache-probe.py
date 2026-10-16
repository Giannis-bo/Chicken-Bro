import json
from pathlib import Path
from server.app.channels.qq_official.query_service import QueryService
from server.app.channels.qq_official.battle_narrative import BattleNarrative
from server.app.channels.qq_official.battle_commands import format_battle

class Forbidden:
    calls=0
    def stream(self,**kwargs):
        self.calls+=1
        raise AssertionError('cached detail must not call model')

cases=json.loads(Path('/tmp/qq-battle-narrative-source-2269024.json').read_text())['results']
results=[]
for case in cases:
    context=json.loads(json.dumps(case['packet']))
    adapter=Forbidden();service=QueryService(None,None,battle_writer=BattleNarrative(adapter))
    try:
        for kind in ('battle_good','battle_review'):
            p=service._query({'request':{'kind':kind},'battle_context':context})
            assert p['narrative']['status']=='ready'
            assert format_battle(p,kind)==case['messages'][kind]
        assert adapter.calls==0
        results.append({'name':case['name'],'sameMessages':True,'additionalSourceCalls':0,'additionalModelCalls':adapter.calls})
    finally:service.close()
print(json.dumps({'root':str(Path.cwd()),'qqMessagesSent':0,'results':results},ensure_ascii=False,indent=2))

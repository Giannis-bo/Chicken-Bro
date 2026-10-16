"""Cloud-only bounded read/model verification; never constructs a QQ client."""
import json
from pathlib import Path
from server.app.channels.qq_official.query_commands import parse_query,format_result,markdown_parts
from server.app.channels.qq_official.character_source import CharacterQuerySource
from server.app.channels.qq_official.battle_commands import parse_battle,format_battle
from server.app.channels.qq_official.battle_source import BattleSource
from server.app.channels.qq_official.battle_narrative import BattleNarrative
from server.app.channels.qq_official.guidance import DefaultGuidance

character=CharacterQuerySource().query(parse_query('/角色查询 Giannis 白银之手'))
text=format_result(character)
assert character['sections'] and len(markdown_parts(text))<=5
battle=BattleSource().query(parse_battle('/战斗分析 https://www.warcraftlogs.com/reports/mZBg8DbyNdTrXcFL 场次=3'))
assert battle['status']=='ready' and battle['fightId']==3
battle=BattleNarrative.configured().apply(battle)
assert battle['narrative']['status']=='ready',battle['narrative']
texts={kind:format_battle(battle,kind) for kind in ('battle_summary','battle_good','battle_review')}
assert all(len(t)<=1200 and len(markdown_parts(t))==1 for t in texts.values())
guidance=DefaultGuidance.configured().reply('鸡哥，我想查自己的大米成绩，怎么发命令？')
assert guidance['status']=='ready',guidance
result={'qqMessagesSent':0,'modelCalls':2,'realPublicSources':True,
        'character':{'identity':character['identity'],'sections':character['sections'],'message':text},
        'battle':{'reportCode':battle['reportCode'],'fightId':battle['fightId'],'coverage':battle['coverage'],
                  'narrative':battle['narrative'],'messages':texts},'guidance':guidance}
Path('/tmp/qqbot-source-model-20261016.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'characterSections':len(character['sections']),'battleStatus':battle['narrative']['status'],'guidance':guidance,'qqMessagesSent':0},ensure_ascii=False))

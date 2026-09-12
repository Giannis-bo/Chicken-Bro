"""Fixed synthetic benchmark corpus. No network, clock, engine, or account access.

REFERENCE_CALLS is a coverage oracle for tests, never included in model prompts.
Receipts record acquisition, not answer quality; rubrics require separate review.
"""
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_REPO_ROOT = Path(__file__).resolve().parents[1]
if (_REPO_ROOT / 'server' / 'chickenbro_native_mcp.py').is_file():
    sys.path.insert(0, str(_REPO_ROOT))
# Cloud runner supplies the selected release package on sys.path. Do not import
# an unrelated top-level chickenbro_native_mcp from the host environment.
from server.chickenbro_native_mcp import TOOL_DEFINITIONS

SCHEMAS = {t['name']: t['inputSchema'] for t in TOOL_DEFINITIONS}
WCL_URL = 'https://www.warcraftlogs.com/reports/aB3dE5fG7hJ9kL2m'
PROFILE = 'https://raider.io/characters/eu/silvermoon/Fixturealpha'
PROFILE_B = 'https://raider.io/characters/eu/silvermoon/Fixturebeta'
SNAPSHOT = '11111111-1111-4111-8111-111111111111'
BASE_JOB = '22222222-2222-4222-8222-222222222222'
VAR_JOB = '33333333-3333-4333-8333-333333333333'
PREFIX = '这是固定合成资料基准，不是真实游戏资料或真实引擎结果。只调用本会话fixture工具取得资料，禁止外网/原生web访问。请基于取到的证据解答并明确范围。'


def case(id, category, turns, rubric, evidence):
    return dict(id=id, category=category, turns=[PREFIX + turns[0]] + turns[1:], rubric=rubric, requiredEvidence=evidence)


CASES = [
    case('wcl_healing', 'wcl', [f'分析合成日志 {WCL_URL}?fight=7 的雨和云：有效治疗、过量率及主要差异技能，先定位角色。'],
         ['雨(actor11)有效800000/原始1000000，过量20%；云(actor22)有效600000/原始1000000，过量40%。', '雨多200000有效治疗；主要差异为治疗波200000对50000，贡献150000差距。', '不能由治疗量单独断言操作或团队价值优劣。'], ['wcl.overview','healing.11','healing.22']),
    case('wcl_timeline', 'wcl', [f'合成日志 {WCL_URL}?fight=7 中雨前30秒治疗波放了几次，能推断按键习惯吗？', '更正：只看30到60秒，比较雨和云；不要沿用前30秒结论。'],
         ['前0-30秒雨治疗波1次；修正30-60秒雨1次、云2次。', '窗口使用报告相对30000-60000毫秒；不能把施法次数当作按键习惯或因果。'], ['wcl.overview','casts.11.0.30000','casts.11.30000.60000','casts.22.30000.60000']),
    case('rankings_mplus', 'rankings', ['查合成当前世界元素萨大秘境榜前两名，读两人的装备/天赋；他们是否足以证明精通收益最高？'],
         ['两名有效匹配样本Fixturealpha/Fixturebeta，积分3500/3480，均Elemental。', '两人都选节点101；饰品900001/900002分别出现，统计属性缺失不能算精通收益。', '覆盖2人，榜单流行度不是个人模拟收益，不外推全部玩家。'], ['mplus.rankings','profile.alpha','profile.beta']),
    case('rankings_raid', 'rankings', ['查看合成团本正式服史诗元素萨DPS榜，首领甲和乙各取第一名，定位日志角色并比较治疗波次数；别混入PTR。'],
         ['选择zone99、partition1正式服、difficulty5；encounter901和902各1人。', '甲Fixturealpha(actor11)治疗波2次；乙Fixturebeta(actor22)3次；同名不同服actor33不是榜单角色。', '两组各1人，次数受时长/遭遇影响，不推断按键或全榜习惯。'], ['raid.catalog','raid.901','raid.902','raid.actor11','raid.actor22']),
    case('mechanics_alias', 'mechanics', ['合成资料里“蓝羽毛”和“蓝眼睛”是同一饰品吗？先找正式身份，再讲触发方式。'],
         ['蓝羽毛=潮汐羽饰(item900001)，蓝眼睛=湛蓝凝视(item900002)，不是同一物品。', '羽饰为装备被动触发；凝视为主动使用20秒；不得混同触发。', '引用两个已读取fixture详情页面，标明合成资料。'], ['web.alias-search','web.feather','web.eye']),
    case('mechanics_version', 'mechanics', ['合成资料“潮汐羽饰”触发急速到底1000还是1200？核对正式服版本与PTR。', '那旧攻略写1000算写错吗？请按当时版本重新判断。'],
         ['正式服12.0.1(2026-09-10)为1200；12.0.0旧攻略(2026-08-20)为1000；PTR12.0.2为1500不能当现服。', '旧攻略对当时版本成立，不把后来的改动当当时错误。', '明确合成语料，读取补丁页与旧攻略，而非仅信搜索摘要。'], ['web.version-search','web.patch','web.old','web.ptr']),
    case('simc_equipment', 'simc', [f'合成基线任务{BASE_JOB}，同快照用“湛蓝凝视”替换trinket1，做有限对照。通过fixture模拟提交即可，不运行真实引擎。'],
         ['同snapshot11111111-1111-4111-8111-111111111111/runtime fixture-engine-v1，单目标300秒10000次。', '基线1000000±1000，替换1005000±1200；+5000/+0.5%，保守误差2200，超过误差。', '仅一个装备候选、固定装等321；回放数值不是实际SimulationCraft运行，也不是全局最优。'], ['simc.baseline','simc.items','simc.preview','simc.submitted','simc.variant','simc.compare']),
    case('simc_apl', 'simc', [f'合成任务{BASE_JOB}：想把开场闪电箭→熔岩爆裂改成熔岩爆裂→闪电箭，其余循环保留。同快照比较并检查实际动作；fixture模拟提交即可。'],
         ['使用strict_sequence而非仅换优先级；保留其余lightning_bolt循环。', '合成采样开场原lightning_bolt/lava_burst，变体lava_burst/lightning_bolt。', '基线1000000±1000、变体1000800±1200，+800/+0.08%，在2200保守误差内，无明确提升。', '同快照/环境；动作样本证明该合成样本顺序，不是所有战斗顺序保证或真实引擎测速。'], ['simc.baseline','web.apl','simc.preview','simc.submitted','simc.variant','simc.compare']),
]
ITEM = dict(itemId=900002, itemLevel=321, bonusIds=[12345], gems=[], enchant=None)
APL = {'default': ['strict_sequence,name=opener:lava_burst:lightning_bolt', 'lightning_bolt']}
CONTROLS = dict(fightStyle='Patchwerk', desiredTargets=1, maxTime=300, iterations=10000, varyCombatLength=0, targetError=0, raidBuffs=True, bloodlust=True)
PAGES = {
    'feather': ('潮汐羽饰 item900001', '正式名潮汐羽饰，俗称蓝羽毛，itemId=900001。装备被动触发急速，当前正式服12.0.1急速1200。'),
    'eye': ('湛蓝凝视 item900002', '正式名湛蓝凝视，俗称蓝眼睛，itemId=900002。主动使用持续20秒，与潮汐羽饰不是同一物品。'),
    'patch': ('正式服12.0.1补丁 2026-09-10', '2026-09-10正式服12.0.1：潮汐羽饰item900001的触发急速由1000提高至1200。'),
    'old': ('旧攻略12.0.0 2026-08-20', '2026-08-20正式服12.0.0攻略：潮汐羽饰item900001触发1000急速。本页未更新到12.0.1。'),
    'ptr': ('PTR12.0.2 2026-09-11', '测试服PTR12.0.2：潮汐羽饰触发1500急速；并非正式服数值。'),
    'apl': ('fixture-engine-v1 action catalog', '闪电箭=lightning_bolt；熔岩爆裂=lava_burst。strict_sequence,name=opener:lava_burst:lightning_bolt在动作均可用时严格按序。保留后续lightning_bolt循环。'),
}


def page_url(key):
    return 'https://docs.fixture.invalid/' + key


def validate(value, schema, path='arguments'):
    """Validate the native schema subset, including nested additionalProperties."""
    if 'oneOf' in schema:
        matches = 0
        for choice in schema['oneOf']:
            try:
                validate(value, choice, path)
                matches += 1
            except ValueError:
                pass
        if matches != 1:
            raise ValueError(path + ': no unique schema match')
    kinds = schema.get('type', [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    checks = {'object': isinstance(value, dict), 'array': isinstance(value, list), 'string': isinstance(value, str), 'integer': isinstance(value, int) and not isinstance(value, bool), 'number': isinstance(value, (int,float)) and not isinstance(value,bool), 'boolean': isinstance(value,bool), 'null': value is None}
    if kinds and not any(checks[k] for k in kinds):
        raise ValueError(path + ': wrong type')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError(path + ': invalid enum')
    if isinstance(value, dict):
        props = schema.get('properties', {})
        if any(k not in value for k in schema.get('required', [])):
            raise ValueError(path + ': missing required field')
        for k,v in value.items():
            if k in props:
                validate(v, props[k], path+'.'+k)
            elif schema.get('additionalProperties') is False:
                raise ValueError(path + ': unexpected '+k)
            elif isinstance(schema.get('additionalProperties'), dict):
                validate(v, schema['additionalProperties'], path+'.'+k)
    if isinstance(value, list):
        for v in value:
            validate(v, schema.get('items', {}), path+'[]')
    if isinstance(value, (int,float)) and not isinstance(value,bool):
        if value < schema.get('minimum', float('-inf')) or value > schema.get('maximum', float('inf')):
            raise ValueError(path + ': outside bounds')
    for lo,hi in [('minLength','maxLength'), ('minItems','maxItems'), ('minProperties','maxProperties')]:
        if lo in schema and len(value) < schema[lo] or hi in schema and len(value) > schema[hi]:
            raise ValueError(path + ': invalid length')
    if isinstance(value,str) and 'pattern' in schema and not re.search(schema['pattern'],value):
        raise ValueError(path + ': invalid pattern')


def packet(facts, keys):
    return dict(status='ok', sourceKey='benchmark_fixture', facts=facts, evidenceKeys=keys,
                evidenceRefs=['fixture:'+k for k in keys], evidence=[{'ref':'fixture:'+k,'source':'synthetic corpus'} for k in keys], limitations=['固定合成资料回放；不是实时游戏事实或真实引擎运行。'], fixture={'synthetic':True,'revision':'corpus-v1','engineExecuted':False})


def native_packet(name, arguments, response):
    """Project returned corpus fields onto native gateway contracts (no extra facts)."""
    response['nextActions'] = []
    facts = response.get('facts', [])
    first = facts[0] if facts else {}
    if name=='query_warcraftlogs_batch':
        response.update(sourceKey='warcraftlogs',status='verified')
        response['results']=[native_packet('query_warcraftlogs_report',query,result) for query,result in zip(arguments['queries'],response['results'])]
        return response
    if name in ('query_warcraftlogs_report','query_warcraftlogs_batch'):
        response.update(sourceKey='warcraftlogs', status='verified')
        for fact in facts:
            fact.update(sourceStatus='verified', queryScope='scoped_analysis', queryMode='server_configured_warcraftlogs_api')
            if 'healing' in fact:
                healing=fact['healing']
                effective=healing['effective']['total']
                wave=healing['effective']['entries'][0]['total']
                fact['healing']={'complete':True,'totalTimeMs':60000,'rowsTruncated':False,'totals':{'effective':effective,'raw':1000000,'overheal':1000000-effective,'grossEffective':effective,'grossRaw':1000000,'signedAdjustments':{'effective':0,'raw':0},'effectiveHps':effective/60,'rawHps':1000000/60},'entries':[{'guid':77472,'name':'治疗波','total':350000,'overheal':350000-wave},{'guid':61295,'name':'激流','total':650000,'overheal':650000-(effective-wave)}],'coverage':'Paired effective/raw synthetic tables for identical fight and actor; entries are raw totals including overheal.'}
            statistics = fact.get('statistics')
            if statistics:
                page=fact['eventPage']
                count=statistics['casts']['total']
                statistics.update(startTime=page['startTime'],endTime=page['endTime'],observedThrough=page['endTime'],dataType='Casts',sourceId=fact['sourceId'],eventCount=count,pagesRead=1,nextPageTimestamp=None,intervalConvention='[startTime,endTime)')
                statistics['casts']=[{'abilityId':77472,'count':count}]
            for row in fact.get('casts',{}).get('entries',[]):
                row['guid']=row['id']
        response['evidence']=[{'id':f"wcl:{f['reportCode']}:{f['fightId']}",'sourceName':'Warcraft Logs fixture','sourceUrl':WCL_URL+f"?fight={f['fightId']}"+(f"&source={f['sourceId']}" if f.get('sourceId') else ''),'reportCode':f['reportCode'],'fightId':str(f['fightId']),'sourceStatus':'verified','checkedAt':'2026-09-12T00:00:00Z'} for f in facts]
    elif name=='query_warcraftlogs_rankings':
        response.update(sourceKey='warcraftlogs_rankings',status='source_reference',queriedAt='2026-09-12T00:00:00Z')
        if 'zones' in first:
            response['facts']=first['zones']
        else:
            rows=copy.deepcopy(first['rankings'])
            for row in rows:
                row['server']={'name':row['server'],'region':row.pop('region')}
                row.update(identityStatus='named',analysisEligible=True,className='Shaman',specName='Elemental')
            response.update(rankings=rows,scope={k:v for k,v in arguments.items() if k in ('zoneId','encounterId','partition','difficulty','className','specName','metric','region')},pagination={'page':1,'offset':0,'limit':arguments.get('limit',10),'returned':len(rows),'skippedInvalid':0,'hasMore':False,'nextPage':None,'nextOffset':None})
    elif name.startswith('query_raiderio'):
        response.update(sourceKey='raiderio_rankings' if name=='query_raiderio_rankings' else 'raiderio',status='source_reference')
        if name=='query_raiderio_rankings':
            response.update(rankings=first['rankings'],season=first['season'],pagination={'nextPage':first['nextPage'],'nextOffset':first['nextOffset']})
    elif name=='research_public_web':
        response.update(sourceKey='public_web_research',status='source_reference')
    elif 'simulation' in name:
        response.update(sourceKey='simc',status='ready')
        if name=='compare_simulation_jobs':
            response['comparison']={**first,'metricName':'dps','baseline':first['baselineDps'],'variant':first['variantDps'],'delta':first['deltaDps'],'deltaPct':first['deltaPercent'],'combinedErrorBound':first['conservativeError'],'assessment':'within_reported_error' if first['withinError'] else 'higher'}
        elif name=='query_simulation_options':
            response.update(options=first,runtimeRevision=first['runtimeRevision'])
        else:
            response.update(copy.deepcopy(first))
        if name=='get_simulation_job':
            response['result'].update(metricName='dps',provenance=copy.deepcopy(first['provenance']))
            response.update(gear={'items':[{'slot':k,**v} for k,v in first['equipment'].items()]},source={'url':first['sourceUrl']},runtimeRevision=first['provenance']['runtimeRevision'],compilerRevision='chickenbro-simc-compiler-v6',scenarioHash=first['provenance']['scenarioHash'])
            response['result']['actionEvidence']={'scope':'synthetic_sample_only','sampledActions':[{'time':i*1.5,'name':action} for i,action in enumerate(first['result']['sampledActions'])]}
        if name=='list_simulation_jobs':
            for job in response['jobs']:
                job['result'].update(metricName='dps',provenance=copy.deepcopy(job['provenance']))
        response['facts']=['Synthetic fixture observation; no engine executed.']
    return response


class FixtureSession:
    def __init__(self, case_id):
        if case_id not in {c['id'] for c in CASES}:
            raise ValueError('unknown case')
        self.case_id = case_id
        self.receipts = []
        self.previews = []
        self.submitted = False
        self.cache = {}

    def call(self, tool_name, arguments):
        key = json.dumps([tool_name,arguments],sort_keys=True,ensure_ascii=False)
        try:
            if tool_name not in SCHEMAS:
                raise ValueError('unknown fixture tool')
            validate(arguments,SCHEMAS[tool_name])
            if key in self.cache:
                result = copy.deepcopy(self.cache[key])
            else:
                result = native_packet(tool_name,arguments,self._route(tool_name,arguments))
                self.cache[key] = copy.deepcopy(result)
        except (ValueError, KeyError, TypeError) as exc:
            result = packet([], [])
            result.update(status='error',errorCode='FIXTURE_UNAVAILABLE',message=str(exc))
        self.receipts.append({'tool':tool_name,'arguments':copy.deepcopy(arguments),'evidenceKeys':result.get('evidenceKeys',[]),'status':result['status']})
        return result

    def _route(self, name, a):
        if name == 'research_public_web':
            return self._web(a)
        if name == 'query_warcraftlogs_batch':
            results = [self._report(q) for q in a['queries']]
            result = packet([], [k for r in results for k in r['evidenceKeys']])
            result['results']=results
            return result
        if name == 'query_warcraftlogs_report':
            return self._report(a)
        if name == 'query_raiderio_rankings' and self.case_id == 'rankings_mplus':
            if a['className'].lower() != 'shaman' or a['spec'].lower() != 'elemental' or a.get('season','current') not in ('current','fixture-season-1') or a.get('region','world') != 'world' or a.get('page',0) != 0 or a.get('offset',0) not in (0,1):
                raise ValueError('Only current world elemental shaman first page in corpus')
            rows = [dict(rank=i+1,score=score,name=n,region='eu',realm='silvermoon',className='Shaman',spec='Elemental',url=url,profileUrl=url) for i,(n,score,url) in enumerate([('Fixturealpha',3500,PROFILE),('Fixturebeta',3480,PROFILE_B)])]
            offset=a.get('offset',0)
            stop=offset+a.get('limit',10)
            return packet([{'season':'fixture-season-1','rankings':rows[offset:stop],'nextPage':0 if stop<2 else None,'nextOffset':stop if stop<2 else None}], ['mplus.rankings'])
        if name in ('query_raiderio_character','query_raiderio_characters') and self.case_id == 'rankings_mplus':
            targets = a.get('targets',[a.get('target')])
            facts,keys = [],[]
            for target in targets:
                if target not in (PROFILE,PROFILE_B):
                    raise ValueError('profile outside fixed sample')
                alpha = target == PROFILE
                facts.append(dict(sourceUrl=target,name='Fixturealpha' if alpha else 'Fixturebeta',region='eu',realm='silvermoon',className='Shaman',spec='Elemental',snapshotDate='2026-09-10T00:00:00Z',gear={'items':[{'slot':'trinket1','itemId':900001 if alpha else 900002}]},talents={'selectedNodes':[101]},stats=None,missingFields=['secondaryStats']))
                keys.append('profile.alpha' if alpha else 'profile.beta')
            return packet(facts,keys)
        if name == 'query_warcraftlogs_rankings' and self.case_id == 'rankings_raid':
            if 'encounterId' not in a:
                if a.get('zoneId',99) != 99 or set(a)-{'zoneId'}:
                    raise ValueError('Catalog takes empty arguments or zoneId99; ranking filters require encounterId')
                return packet([{'zones':[{'id':99,'name':'合成团本','partitions':[{'id':1,'name':'Live 12.0.1'},{'id':2,'name':'PTR 12.0.2'}],'encounters':[{'id':901,'name':'首领甲'},{'id':902,'name':'首领乙'}]}]}],['raid.catalog'])
            if a.get('zoneId',99) != 99 or a.get('partition') != 1 or a.get('difficulty') != 5 or a.get('className','').lower() != 'shaman' or a.get('specName','').lower() != 'elemental' or a['encounterId'] not in (901,902) or a.get('metric','dps') != 'dps' or a.get('region','world') != 'world' or a.get('page',1) != 1 or a.get('offset',0) != 0:
                raise ValueError('Use catalog: live partition1, mythic5, Shaman Elemental DPS encounters901/902')
            actor = 11 if a['encounterId']==901 else 22
            return packet([{'rankings':[{'rank':1,'name':'Fixturealpha' if actor==11 else 'Fixturebeta','server':'silvermoon','region':'eu','report':{'code':'aB3dE5fG7hJ9kL2m','fightID':7 if actor==11 else 8},'reportUrl':WCL_URL+('?fight=7' if actor==11 else '?fight=8'),'sourceId':actor}],'pagination':{'nextPage':None}}],['raid.'+str(a['encounterId'])])
        if 'simulation' in name and self.case_id.startswith('simc_'):
            return self._simc(name,a)
        raise ValueError('Tool/resource not present in this case corpus')

    def _web(self,a):
        target = a['target']
        allowed = {'mechanics_alias':['feather','eye'], 'mechanics_version':['patch','old','ptr'], 'simc_apl':['apl']}.get(self.case_id,[])
        if not allowed:
            raise ValueError('No web corpus for this case')
        if target.startswith('https://'):
            keys = [k for k in allowed if target == page_url(k)]
            if not keys or a.get('start',0) != 0:
                raise ValueError('Unknown page or offset; corpus pages are complete')
            k = keys[0]
            title,body = PAGES[k]
            if a.get('match') and a['match'].lower() not in (title+body).lower():
                raise ValueError('Match not found in fixture page')
            return packet([{'url':target,'title':title,'text':body,'content':body,'complete':True,'nextStart':None}],['web.'+k])
        if not any(term.lower() in target.lower() for term in ['羽','眼','潮汐','湛蓝','feather','eye','APL','strict_sequence','熔岩','闪电','lava_burst','lightning_bolt']):
            raise ValueError('No matching fixed search; query item name or APL action')
        key = 'alias-search' if self.case_id=='mechanics_alias' else 'version-search' if self.case_id=='mechanics_version' else 'apl-search'
        return packet([{'query':target,'results':[{'title':PAGES[k][0],'url':page_url(k),'snippet':'合成资料条目；打开页面核对全文和版本。'} for k in allowed]}],['web.'+key])

    def _report(self,a):
        if self.case_id not in ('wcl_healing','wcl_timeline','rankings_raid'):
            raise ValueError('No report in this case')
        parsed = urlparse(a['target'])
        expected = urlparse(WCL_URL)
        if parsed.hostname not in ('www.warcraftlogs.com','warcraftlogs.com') or parsed.path != expected.path or parsed.scheme != 'https':
            raise ValueError('Unknown report')
        q = parse_qs(parsed.query or parsed.fragment)
        if set(q)-{'fight','source','type'} or any(len(v)!=1 for v in q.values()) or q.get('fight',['7'])[0] not in (('7','8') if self.case_id=='rankings_raid' else ('7',)):
            raise ValueError('Unknown report selector')
        fight_id = int(q.get('fight',['7'])[0])
        source = int(q['source'][0]) if 'source' in q else None
        if source not in (None,11,22,33):
            raise ValueError('Unknown actor')
        o = a.get('options',{})
        view = o.get('view','full')
        start,end = o.get('startTime',0),o.get('endTime',60000)
        if not 0 <= start < end <= 60000:
            raise ValueError('Window outside fixture fight 0..60000ms')
        players = [{'id':11,'name':'Fixturealpha' if self.case_id=='rankings_raid' else '雨','server':'silvermoon','region':'eu','type':'Shaman'}, {'id':22,'name':'Fixturebeta' if self.case_id=='rankings_raid' else '云','server':'silvermoon','region':'eu','type':'Shaman'}, {'id':33,'name':'Fixturealpha','server':'other-realm','region':'eu','type':'Shaman'}]
        fact = {'reportCode':'aB3dE5fG7hJ9kL2m','fightId':fight_id,'sourceId':source,'fight':{'id':fight_id,'startTime':0,'endTime':60000,'kill':True},'players':players}
        # This corpus returns fight and actor identity with every view, so an
        # events-first acquisition has the same identity evidence as overview.
        keys = ['wcl.overview']
        if view in ('full','overview'):
            if self.case_id == 'rankings_raid' and source in (11,22):
                fact['casts'] = {'entries':[{'id':77472,'name':'治疗波','total':2 if source==11 else 3}], 'rowsTruncated':False}
                keys.append('raid.actor'+str(source))
        if view == 'healing':
            if source not in (11,22) or start!=0 or end!=60000 or self.case_id!='wcl_healing':
                raise ValueError('Healing corpus requires source11/22 and complete fight')
            eff = 800000 if source==11 else 600000
            fact['healing'] = {'effective':{'total':eff,'entries':[{'id':77472,'name':'治疗波','total':200000 if source==11 else 50000}]},'raw':{'total':1000000},'overheal':1000000-eff,'overhealPercent':(1000000-eff)/10000,'complete':True}
            keys.append('healing.'+str(source))
        if view in ('events','statistics','full'):
            kind=o.get('dataType','All')
            if kind not in ('All','Casts'):
                raise ValueError('Only Casts event corpus available; unavailable is not zero')
            events=[{'type':'cast','timestamp':t,'sourceID':actor,'abilityGameID':77472,'name':'治疗波'} for actor,t in [(11,5000),(11,35000),(22,10000),(22,40000),(22,55000),(33,45000)] if start<=t<end and (source is None or actor==source)]
            events.sort(key=lambda e:e['timestamp'])
            limit=o.get('limit',1000)
            fact['events']=events[:limit]
            fact['eventPage']={'dataType':kind,'startTime':start,'endTime':end,'complete':len(events)<=limit,'nextPageTimestamp':events[limit]['timestamp'] if len(events)>limit else None}
            if view=='statistics':
                fact['statistics']={'complete':True,'metricsComplete':True,'casts':{'total':len(events),'byAbility':[{'abilityGameID':77472,'name':'治疗波','count':len(events)}]}}
                fact['events']=[]
            if source in (11,22) and (view=='statistics' or len(events)<=limit):
                keys.append(f'casts.{source}.{int(start)}.{int(end)}')
            if view!='statistics' and len(events)<=limit:
                # Complete returned events support contained actor/time slices;
                # aggregate statistics cannot be split into smaller windows.
                for actor in (11,22):
                    if source not in (None,actor):
                        continue
                    for lo,hi in ((0,30000),(30000,60000)):
                        if start<=lo and end>=hi:
                            keys.append(f'casts.{actor}.{lo}.{hi}')
            if self.case_id=='rankings_raid' and start==0 and end==60000 and (view=='statistics' or len(events)<=limit):
                for actor in (11,22):
                    if source==actor or source is None and view!='statistics':
                        keys.append('raid.actor'+str(actor))
        return packet([fact],keys)

    def _simc(self,name,a):
        variant = {'equipmentOverrides':{'trinket1':ITEM}} if self.case_id=='simc_equipment' else {'actionLists':APL}
        baseline_scenario = {**CONTROLS,'actionLists':{'default':['strict_sequence,name=opener:lightning_bolt:lava_burst','lightning_bolt']}}
        scenario = {**baseline_scenario, **variant}
        def job(is_variant):
            actions = ['lava_burst','lightning_bolt'] if is_variant and self.case_id=='simc_apl' else ['lightning_bolt','lava_burst']
            value = 1000000+(5000 if self.case_id=='simc_equipment' else 800) if is_variant else 1000000
            return {'jobId':VAR_JOB if is_variant else BASE_JOB,'snapshotId':SNAPSHOT,'status':'succeeded','sourceUrl':PROFILE,'scenario':scenario if is_variant else baseline_scenario,'effectiveConfig':scenario if is_variant else baseline_scenario,'character':{'name':'Fixturealpha','class':'Shaman','spec':'Elemental'},'equipment':{'trinket1':ITEM if is_variant and self.case_id=='simc_equipment' else {**ITEM,'itemId':900001}},'result':{'metric':'dps','metricValue':value,'metricError':1200 if is_variant else 1000,'dps':value,'sampledActions':actions},'provenance':{'snapshotId':SNAPSHOT,'runtimeRevision':'fixture-engine-v1','compilerVersion':6,'sourceRevision':'fixture-snapshot-v1','scenarioHash':hashlib.sha256(json.dumps(scenario if is_variant else baseline_scenario,sort_keys=True).encode()).hexdigest(),'synthetic':True,'engineExecuted':False}}
        if name=='get_simulation_job':
            if a['jobId'] not in (BASE_JOB,VAR_JOB) or a['jobId']==VAR_JOB and not self.submitted:
                raise ValueError('Unknown/unsubmitted owned fixture job')
            is_variant=a['jobId']==VAR_JOB
            return packet([job(is_variant)],['simc.variant' if is_variant else 'simc.baseline'])
        if name=='list_simulation_jobs':
            if a.get('cursor'):
                raise ValueError('No further fixture pages')
            return packet([{'jobs':[job(False)],'nextCursor':None}],['simc.baseline'])
        if name=='query_simulation_options' and self.case_id=='simc_equipment':
            if a.get('baseJobId',BASE_JOB)!=BASE_JOB or a.get('snapshotId',SNAPSHOT)!=SNAPSHOT or a['kind']!='items':
                raise ValueError('Unknown snapshot or option kind')
            return packet([{'items':[{'name':'湛蓝凝视','itemId':900002,'sameUpgradeVariants':[ITEM]}],'runtimeRevision':'fixture-engine-v1'}],['simc.items'])
        if name in ('preview_simulation','submit_simulation'):
            if ('snapshotId' in a)==('baseJobId' in a) or a.get('baseJobId',BASE_JOB)!=BASE_JOB or a.get('snapshotId',SNAPSHOT)!=SNAPSHOT:
                raise ValueError('Choose exactly one owned snapshot/baseJob')
            proposed=a['scenario']
            effective=copy.deepcopy({**baseline_scenario,**proposed})
            # A sequence label only names the identical sequence. Do not accept
            # changed conditions, list structure, action order or rotation tail.
            for actions in effective.get('actionLists',{}).values():
                for index,action in enumerate(actions):
                    actions[index]=re.sub(r'^strict_sequence,name=[A-Za-z][A-Za-z0-9_]*(?=:)', 'strict_sequence,name=opener',action)
            if effective!=scenario:
                raise ValueError('Only the requested single variant with identical controls is available; use verified item or strict_sequence and preserve lightning_bolt tail')
            fingerprint=json.dumps(effective,sort_keys=True)
            if name=='preview_simulation':
                if fingerprint not in self.previews:
                    self.previews.append(fingerprint)
                return packet([{'valid':True,'snapshotId':SNAPSHOT,'scenario':scenario,'effectiveConfig':scenario,'changes':variant,'runtimeRevision':'fixture-engine-v1','blockers':[]}],['simc.preview'])
            if fingerprint not in self.previews:
                raise ValueError('Preview exact variant before fixture submission')
            self.submitted=True
            return packet([{'jobId':VAR_JOB,'snapshotId':SNAPSHOT,'status':'queued','simulatedSubmission':True}],['simc.submitted'])
        if name=='compare_simulation_jobs':
            if a['baselineJobId']!=BASE_JOB or a['variantJobId']!=VAR_JOB or not self.submitted:
                raise ValueError('Need known same-snapshot completed baseline and submitted variant')
            delta=5000 if self.case_id=='simc_equipment' else 800
            return packet([{'comparable':True,'baselineJobId':BASE_JOB,'variantJobId':VAR_JOB,'snapshotId':SNAPSHOT,'runtimeRevision':'fixture-engine-v1','controls':CONTROLS,'baselineDps':1000000,'variantDps':1000000+delta,'deltaDps':delta,'deltaPercent':delta/10000,'baselineError':1000,'variantError':1200,'conservativeError':2200,'withinError':delta<=2200,'changes':variant,'provenance':{'snapshotId':SNAPSHOT,'runtimeRevision':'fixture-engine-v1','synthetic':True,'engineExecuted':False}}],['simc.compare','simc.variant'])
        raise ValueError('Simulation operation unavailable in fixed corpus')


def report(source=None,view='overview',fight=7,**options):
    return ('query_warcraftlogs_report', {'target':WCL_URL+f'?fight={fight}'+(f'&source={source}' if source else ''),'options':{'view':view,**options}})


REFERENCE_CALLS = {
    'wcl_healing':[report(),report(11,'healing'),report(22,'healing')],
    'wcl_timeline':[report(),report(11,'statistics',startTime=0,endTime=30000),report(11,'statistics',startTime=30000,endTime=60000),report(22,'statistics',startTime=30000,endTime=60000)],
    'rankings_mplus':[('query_raiderio_rankings',{'className':'shaman','spec':'elemental','limit':2}),('query_raiderio_character',{'target':PROFILE}),('query_raiderio_character',{'target':PROFILE_B})],
    'rankings_raid':[('query_warcraftlogs_rankings',{})]+[('query_warcraftlogs_rankings',{'zoneId':99,'encounterId':e,'partition':1,'difficulty':5,'className':'Shaman','specName':'Elemental','limit':1}) for e in (901,902)]+[report(11),report(22,fight=8)],
    'mechanics_alias':[('research_public_web',{'target':'蓝羽毛 蓝眼睛'})]+[('research_public_web',{'target':page_url(k)}) for k in ('feather','eye')],
    'mechanics_version':[('research_public_web',{'target':'潮汐羽饰 版本'})]+[('research_public_web',{'target':page_url(k)}) for k in ('patch','old','ptr')],
}
for _id,_variant in [('simc_equipment',{'equipmentOverrides':{'trinket1':ITEM}}),('simc_apl',{'actionLists':APL})]:
    REFERENCE_CALLS[_id]=[('get_simulation_job',{'jobId':BASE_JOB})]+([('query_simulation_options',{'baseJobId':BASE_JOB,'kind':'items','query':'湛蓝凝视'})] if _id=='simc_equipment' else [('research_public_web',{'target':'APL 熔岩爆裂 闪电箭'}),('research_public_web',{'target':page_url('apl')})])+[(n,{'baseJobId':BASE_JOB,'scenario':_variant}) for n in ('preview_simulation','submit_simulation')]+[('get_simulation_job',{'jobId':VAR_JOB}),('compare_simulation_jobs',{'baselineJobId':BASE_JOB,'variantJobId':VAR_JOB})]

"""Bounded, server-authenticated public raid reads; no AI or general URL fetch."""
from datetime import datetime,timezone
from time import monotonic
from functools import partial

from server.app.chickenbro.wcl_source import _graphql
from .battle_analysis import analyze_battle, select_windows
from .battle_causes import apply_causes, select_deaths
from .battle_report import build_team_report, pressure_window, REPORT_VERSION
from .battle_profile import PROFILE_QUERY, CONSUMABLE_FILTER
from .battle_commentary import apply_commentary, COMMENTARY_VERSION

CONTEXT_QUERY='''query QqBattleContext($code:String!){reportData{report(code:$code){
 code visibility title fights(translate:true){id name encounterID difficulty kill startTime endTime
 friendlyPlayers inProgress keystoneLevel gameZone{id name}}
 masterData(translate:true){actors{id name type subType gameID petOwner} abilities{gameID name}}}}}'''
TABLES_QUERY='''query QqBattleTables($code:String!,$ids:[Int]){reportData{report(code:$code){
 playerDetails(fightIDs:$ids,includeCombatantInfo:false)
 damage:table(fightIDs:$ids,dataType:DamageDone)
 healing:table(fightIDs:$ids,dataType:Healing)}}}'''
EVENTS_QUERY='''query QqBattleEvents($code:String!,$ids:[Int],$type:EventDataType,
 $start:Float,$end:Float,$limit:Int){reportData{report(code:$code){
 events(fightIDs:$ids,dataType:$type,startTime:$start,endTime:$end,limit:$limit){data nextPageTimestamp}}}}'''
FOCUS_QUERY='''query QqBattleFocus($code:String!,$ids:[Int],$start:Float,$end:Float,
 $castStart:Float,$actor:Int,$filter:String){reportData{report(code:$code){
 incoming:events(fightIDs:$ids,dataType:All,startTime:$start,endTime:$end,filterExpression:$filter,limit:1000,includeResources:true){data nextPageTimestamp}
 damage:events(fightIDs:$ids,dataType:DamageTaken,startTime:$start,endTime:$end,sourceID:$actor,limit:1000,includeResources:true){data nextPageTimestamp}
 casts:events(fightIDs:$ids,dataType:Casts,startTime:$castStart,endTime:$end,sourceID:$actor,limit:1000,includeResources:true){data nextPageTimestamp}}}}'''
FOCUSED_EVENTS_QUERY='''query QqBattleFocusedEvents($code:String!,$ids:[Int],$type:EventDataType,
 $start:Float,$end:Float,$limit:Int,$actor:Int,$filter:String){reportData{report(code:$code){
 events(fightIDs:$ids,dataType:$type,startTime:$start,endTime:$end,limit:$limit,
 sourceID:$actor,filterExpression:$filter,includeResources:true){data nextPageTimestamp}}}}'''

PERFORMANCE_QUERY='''query QqBattlePerformance($code:String!,$ids:[Int],$start:Float,$end:Float){reportData{report(code:$code){
 interrupts:events(fightIDs:$ids,dataType:Interrupts,limit:1000){data nextPageTimestamp}
 dispels:events(fightIDs:$ids,dataType:Dispels,limit:1000){data nextPageTimestamp}
 pressureHealing:table(fightIDs:$ids,dataType:Healing,startTime:$start,endTime:$end)}}}'''


def number(value):
    from math import isfinite
    return type(value) in (int,float) and isfinite(value)


def read_events(fetch,variables,*,max_pages=4):
    start,end=variables['start'],variables['end'];cursor=start;rows=[];complete=False;pages=0;semantic_complete=True
    for _ in range(max_pages):
        try:page=fetch({**variables,'start':cursor,'limit':1000})
        except Exception:break
        pages+=1
        if not isinstance(page,dict) or not isinstance(page.get('data'),list) or 'nextPageTimestamp' not in page:break
        next_cursor=page['nextPageTimestamp']
        if next_cursor is not None and (not number(next_cursor) or not cursor<next_cursor<=end):break
        boundary=next_cursor if next_cursor is not None else end
        events=page['data']
        if len(events)>1000 or any(not isinstance(e,dict) or not number(e.get('timestamp')) for e in events):break
        # A continuation boundary belongs only to the following page. Identical
        # events inside one page remain distinct legitimate log events.
        for event in events:
            if not cursor<=event['timestamp']<boundary:continue
            semantic=True
            if variables.get('type') in ('Deaths','DamageTaken'):
                expected='death' if variables['type']=='Deaths' else 'damage'
                semantic=(event.get('type')==expected and type(event.get('targetID')) is int)
                if variables['type']=='DamageTaken':semantic=semantic and number(event.get('amount')) and event['amount']>=0
                if 'fight' in event:semantic=semantic and event['fight'] in variables.get('ids',[])
            if 'fight' in event:semantic=semantic and event['fight'] in variables.get('ids',[])
            if variables.get('targetActor') is not None:
                semantic=semantic and event.get('targetID')==variables['targetActor']
            if variables.get('sourceActor') is not None:
                semantic=semantic and event.get('sourceID')==variables['sourceActor']
            if semantic:rows.append(event)
            else:semantic_complete=False
        cursor=boundary
        if next_cursor is None:complete=semantic_complete;break
    return {'events':rows,'complete':complete,'pages':pages,'startTime':start,'endTime':end,
            'observedThrough':cursor,'dataType':variables.get('type')}


class BattleSource:
    def __init__(self,*,graphql=None,clock=monotonic):
        self.graphql=graphql or partial(_graphql,locale='zhCN');self.clock=clock

    def query(self,request,*,context=None):
        if not request.url:
            if isinstance(context,dict) and context.get('schema')=='qq-battle-v1' and context.get('status')=='ready':
                if context.get('analysisVersion')!='death-causes-v2' or context.get('localizationLocale')!='zhCN' or context.get('reportVersion')!=REPORT_VERSION or context.get('commentaryVersion')!=COMMENTARY_VERSION:return {'status':'stale_context'}
                return context
            return {'status':'missing_context'}
        deadline=self.clock()+110;calls=0
        def read(query,variables):
            nonlocal calls
            remaining=deadline-self.clock()
            if calls>=32 or remaining<=0:raise TimeoutError()
            calls+=1
            data=self.graphql(query,variables,timeout_seconds=min(15,remaining))
            if data.get('_fieldErrors'):raise ValueError('partial GraphQL fields')
            result=(data.get('reportData') or {}).get('report')
            if not isinstance(result,dict):raise ValueError('missing report')
            return result
        code=request.url.rsplit('/',1)[-1]
        try:
            raw=read(CONTEXT_QUERY,{'code':code})
            if raw.get('code')!=code or raw.get('visibility') not in ('public','unlisted'):
                return {'status':'blocked','message':'只支持可公开读取的 WCL 报告。'}
            def supported(f):
                if type(f.get('encounterID')) is not int or f['encounterID']<=0:return False
                if f.get('difficulty')==10:
                    return type(f.get('keystoneLevel')) is int and f['keystoneLevel']>0
                return f.get('difficulty') in (1,3,4,5) and not f.get('keystoneLevel')
            candidates=[f for f in raw.get('fights',[]) if isinstance(f,dict) and
                    type(f.get('id')) is int and supported(f)]
            fights=[f for f in candidates if
                    type(f.get('kill')) is bool and f.get('inProgress') is False and
                    number(f.get('startTime')) and number(f.get('endTime')) and 0<=f['startTime']<f['endTime']]
            selector=request.fight_id
            if selector=='last':
                latest=max(candidates,key=lambda f:f['id'],default=None)
                selector=latest['id'] if latest else None
            multi=isinstance(selector,str) and ',' in selector
            if selector is None or selector=='all' or multi:
                choices=fights
                if multi:
                    selected={int(i) for i in selector.split(',')}
                    choices=[f for f in choices if f['id'] in selected]
                if not choices:return {'status':'blocked','message':'所选范围没有可分析的已结束团本首领或大秘境记录。'}
                return {'status':'selection','sourceUrl':request.url,'fights':sorted(choices,key=lambda f:f['startTime'],reverse=True)[:5]}
            fight=next((f for f in fights if f['id']==selector),None)
            if fight is None:
                selected=next((f for f in raw.get('fights',[]) if isinstance(f,dict) and f.get('id')==selector),None)
                if selected is None:message='报告中不存在第'+str(selector)+'场，请确认场次编号。'
                elif selected.get('inProgress') is True:message='第'+str(selector)+'场仍在进行，结束后可分析。'
                elif not supported(selected):message='第'+str(selector)+'场属于暂不支持的战斗类型；当前支持团本首领和大秘境整趟记录。'
                else:message='第'+str(selector)+'场的战斗起止或完成状态不完整，暂不能分析。'
                return {'status':'blocked','message':message}
            variables={'code':code,'ids':[fight['id']],'start':fight['startTime'],'end':fight['endTime']}
            tables={}
            try:tables=read(TABLES_QUERY,{'code':code,'ids':[fight['id']]})
            except Exception:pass
            def fetch(v):return read(EVENTS_QUERY,v).get('events')
            deaths=read_events(fetch,{**variables,'type':'Deaths'},max_pages=3)
            windows=[]
            for start,end in select_windows(fight,deaths['events']):
                page=read_events(fetch,{**variables,'type':'DamageTaken','start':start,'end':end},max_pages=4)
                windows.append(page)
            packet=analyze_battle(code,request.url,fight,raw.get('masterData') or {},tables,deaths,windows)
            # Each focus request returns three independently paged viewpoints.
            # Name filters are validated again against actor ID; duplicate names
            # and upstream filter changes can never prove a causal conclusion.
            import json
            master=raw.get('masterData') or {}
            actor_map={a['id']:a for a in master.get('actors',[]) if type(a.get('id')) is int}
            bundles=[]
            for death in select_deaths(fight,deaths['events']):
                actor=death['targetID'];t=death['timestamp'];name=actor_map.get(actor,{}).get('name')
                if not isinstance(name,str):continue
                name_filter='target.name = '+json.dumps(name,ensure_ascii=False)
                v={**variables,'start':max(fight['startTime'],t-10000),
                   'end':min(fight['endTime'],t+1000),'castStart':max(fight['startTime'],t-30000),
                   'actor':actor,'filter':name_filter}
                try:initial=read(FOCUS_QUERY,v)
                except Exception:break
                bundle={'actorId':actor,'deathTimestamp':t}
                for key,view in [('incoming','All'),('damage','DamageTaken'),('casts','Casts')]:
                    page=initial.get(key);first=[page]
                    opts={'code':code,'ids':variables['ids'],'start':v['castStart'] if key=='casts' else v['start'],
                          'end':v['end'],'type':view,'actor':None if key=='incoming' else actor,
                          'filter':name_filter if key=='incoming' else None,
                          **({'sourceActor':actor} if key=='casts' else {'targetActor':actor})}
                    def focus_fetch(options,first=first):
                        if first:return first.pop()
                        allowed={'code','ids','start','end','type','actor','filter','limit'}
                        return read(FOCUSED_EVENTS_QUERY,{k:v for k,v in options.items() if k in allowed}).get('events')
                    bundle[key]=read_events(focus_fetch,opts,max_pages=3)
                bundles.append(bundle)
            # Fetch NPC casts only where they can establish a resumed-melee
            # pattern. Different NPC instances remain distinct in the analyzer.
            for bundle in bundles:
                events=bundle['damage']['events']
                fatal=next((e for e in reversed(events) if e.get('timestamp',0)<=bundle['deathTimestamp'] and
                            e.get('abilityGameID')==1 and e.get('overkill',-1)>=0),None)
                if not fatal:continue
                npc=fatal.get('sourceID')
                if actor_map.get(npc,{}).get('type')!='NPC':continue
                game_id=actor_map[npc].get('gameID')
                if type(game_id) is not int or game_id<=0:continue
                opts={**variables,'type':'All','actor':None,
                      'filter':'source.id = '+str(game_id),'sourceActor':npc,
                      'start':max(fight['startTime'],bundle['deathTimestamp']-20000),
                      'end':min(fight['endTime'],bundle['deathTimestamp']+1000)}
                def npc_fetch(options):
                    allowed={'code','ids','start','end','type','actor','filter','limit'}
                    return read(FOCUSED_EVENTS_QUERY,{k:v for k,v in options.items() if k in allowed}).get('events')
                bundle['npcId']=npc;bundle['npcCasts']=read_events(npc_fetch,opts,max_pages=2)
            packet=apply_causes(packet,bundles,master,tables)
            # Optional enrichment comes after lethal reconstruction so the
            # existing deadline/call budget always prioritizes causal evidence.
            w=pressure_window(packet);extra={}
            try:
                extra=read(PERFORMANCE_QUERY,{**variables,
                    'start':w['startTime'] if w else max(fight['startTime'],fight['endTime']-10000),
                    'end':w['endTime'] if w else fight['endTime']})
            except Exception:pass
            packet=build_team_report(packet,tables,master,extra)
            profile={}
            try:profile=read(PROFILE_QUERY,{'code':code,'ids':variables['ids'],'consumableFilter':CONSUMABLE_FILTER})
            except Exception:pass
            packet=apply_commentary(packet,tables,master,profile)
            if not (packet['good'] or packet['deaths'] or packet['damageWindows'] or
                    (packet['coverage']['actors'] and packet['coverage']['deaths'])):
                return {'status':'unavailable'}
            packet.update(readAt=datetime.now(timezone.utc).isoformat(),sourceCalls=calls,localizationLocale='zhCN')
            return packet
        except Exception:
            return {'status':'unavailable'}

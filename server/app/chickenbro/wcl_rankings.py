"""Public WCL ranking discovery. Scope and pagination are evidence, not analysis."""
from datetime import datetime, timezone
import math
import re
from server.app.chickenbro.wcl_source import _graphql
from server.app.simulation.sources import InvalidSourceLink

_ZONE_FIELDS = 'id name encounters{id name} partitions{id name default} difficulties{id name}'
CATALOG_QUERY = '{worldData{zones{' + _ZONE_FIELDS + '}}}'
ZONE_QUERY = 'query($id:Int!){worldData{zone(id:$id){' + _ZONE_FIELDS + '}}}'
RANKINGS_QUERY = '''query($id:Int!,$difficulty:Int!,$className:String!,$specName:String!,$page:Int!,$partition:Int!,$region:String,$metric:CharacterRankingMetricType!){
 worldData{encounter(id:$id){id name zone{''' + _ZONE_FIELDS + '''}
 characterRankings(difficulty:$difficulty,className:$className,specName:$specName,page:$page,
 partition:$partition,serverRegion:$region,metric:$metric,includeCombatantInfo:false)}}}'''
_REGIONS={'world','us','eu','kr','tw','cn'}
_ALLOWED={'zoneId','encounterId','difficulty','className','specName','page','offset','limit','partition','region','metric'}


def _integer(options,key,minimum,maximum,default=None):
    value=options.get(key,default)
    if type(value) is not int or not minimum<=value<=maximum:raise InvalidSourceLink()
    return value


def _packet(status,**fields):
    return {'sourceKey':'warcraftlogs_rankings','status':status,'queriedAt':datetime.now(timezone.utc).isoformat(),
        'facts':[],'limitations':[] if status=='source_reference' else [status],**fields}


def _zone(value):
    if not isinstance(value,dict) or type(value.get('id')) is not int:raise ValueError('invalid zone')
    result={'id':value['id'],'name':str(value.get('name') or '')[:160],
        'sourceUrl':f"https://www.warcraftlogs.com/zone/rankings/{value['id']}/"}
    for field in ('encounters','partitions','difficulties'):
        entries=value.get(field)
        if not isinstance(entries,list) or len(entries)>200:raise ValueError('invalid catalog')
        result[field]=[{k:v for k,v in item.items() if k in ('id','name','default')} for item in entries]
    return result


def query_wcl_rankings(options):
    if not isinstance(options,dict) or set(options)-_ALLOWED:raise InvalidSourceLink()
    region=options.get('region','world')
    if region not in _REGIONS:raise InvalidSourceLink()
    page=_integer(options,'page',1,20,1);offset=_integer(options,'offset',0,99,0);limit=_integer(options,'limit',1,10,10)
    eid=_integer(options,'encounterId',1,1000000) if 'encounterId' in options else None
    zid=_integer(options,'zoneId',1,10000) if 'zoneId' in options else None
    if eid is None and set(options)-{'zoneId'}:raise InvalidSourceLink()
    if eid is not None:
        difficulty=_integer(options,'difficulty',1,5)
        partition=_integer(options,'partition',1,100)
        class_name=options.get('className');spec_name=options.get('specName');metric=options.get('metric','dps')
        if any(not isinstance(v,str) or not re.fullmatch(r'[A-Za-z][A-Za-z ]{0,30}',v) for v in (class_name,spec_name)) or metric not in ('dps','hps','bossdps'):raise InvalidSourceLink()
    try:
        if eid is None:
            data=_graphql(ZONE_QUERY,{'id':zid}) if zid else _graphql(CATALOG_QUERY,{})
            world=data.get('worldData') or {}
            entries=[world.get('zone')] if zid else world.get('zones')
            if not isinstance(entries,list):return _packet('unavailable')
            if entries==[None]:return _packet('not_found')
            return _packet('partial' if data.get('_fieldErrors') else 'source_reference',facts=[_zone(z) for z in entries],
                nextActions=['Choose the live zone and partition from this catalog. PTR is not live. Select an encounter, difficulty, className, specName and partition; never infer identifiers.'])
        variables={'id':eid,'difficulty':difficulty,'className':class_name,'specName':spec_name,'page':page,'partition':partition,'region':None if region=='world' else region,'metric':metric}
        data=_graphql(RANKINGS_QUERY,variables);encounter=(data.get('worldData') or {}).get('encounter')
        if encounter is None:return _packet('not_found')
        if encounter.get('id')!=eid:return _packet('identity_mismatch')
        zone=_zone(encounter['zone'])
        if zid is not None and zid!=zone['id']:return _packet('scope_mismatch')
        if difficulty not in [d['id'] for d in zone['difficulties']] or partition not in [p['id'] for p in zone['partitions']]:return _packet('scope_mismatch')
        ranking=encounter.get('characterRankings')
        if not isinstance(ranking,dict) or ranking.get('page')!=page or not isinstance(ranking.get('rankings'),list) or type(ranking.get('hasMorePages')) is not bool:return _packet('unavailable')
        raw=ranking['rankings']
        if len(raw)>100:return _packet('unavailable')
        results=[];invalid=0
        for index,r in enumerate(raw[offset:offset+limit],offset):
            if not isinstance(r,dict):
                invalid+=1;continue
            report=r.get('report');server=r.get('server')
            if (not isinstance(report,dict)
                or any(not isinstance(r.get(k),str) or not r[k].strip() for k in ('name','class','spec'))):
                invalid+=1;continue
            code=report.get('code');fight=report.get('fightID');amount=r.get('amount')
            anonymous = (server is None and isinstance(code,str)
                         and re.fullmatch(r'a:[A-Za-z0-9]{16}',code) is not None)
            if (r['class'].casefold()!=class_name.casefold() or r['spec'].casefold()!=spec_name.casefold()
                or type(fight) is not int or fight<1
                or type(amount) not in (int,float) or not math.isfinite(amount) or amount<=0):
                invalid+=1;continue
            if not anonymous and (not isinstance(server,dict)
                or not isinstance(server.get('name'),str) or not server['name'].strip()
                or not isinstance(server.get('region'),str) or server['region'].lower() not in _REGIONS-{'world'}
                or not isinstance(code,str) or not re.fullmatch(r'[A-Za-z0-9]{16}',code)
                or (region!='world' and server['region'].lower()!=region)):
                invalid+=1;continue
            results.append({'rank':(page-1)*100+index+1,'name':str(r.get('name') or '')[:100],
                'class':r['class'],'spec':r['spec'],'amount':amount,'durationMs':r.get('duration'),
                'startTime':r.get('startTime'),
                'identityStatus':'anonymous' if anonymous else 'named', 'analysisEligible':not anonymous,
                'server':None if anonymous else {k:server.get(k) for k in ('id','name','region')},
                'report':{'code':code,'fightID':fight},
                'reportUrl':None if anonymous else f'https://www.warcraftlogs.com/reports/{code}?fight={fight}'})
        next_offset=offset+min(limit,max(0,len(raw)-offset))
        same_page=next_offset<len(raw)
        has_more=same_page or ranking['hasMorePages']
        next_page=page if same_page else page+1 if ranking['hasMorePages'] and page<20 else None
        return _packet('partial' if invalid or data.get('_fieldErrors') else 'source_reference',facts=[zone],
            scope={'encounterId':eid,'encounterName':encounter.get('name'),'zoneId':zone['id'],'difficulty':difficulty,
                'partition':partition,'partitionName':next(p['name'] for p in zone['partitions'] if p['id']==partition),
                'className':class_name,'specName':spec_name,'region':region,'metric':metric},rankings=results,
            pagination={'page':page,'offset':offset,'limit':limit,'returned':len(results),'upstreamCount':len(raw),
                'namedReturned':sum(r['identityStatus']=='named' for r in results),
                'anonymousReturned':sum(r['identityStatus']=='anonymous' for r in results),
                'skippedInvalid':invalid,'hasMore':has_more,'paginationCapReached':bool(has_more and next_page is None),'nextPage':next_page,'nextOffset':next_offset if same_page else 0 if next_page else None},
            limitations=['Rank is the ordinal within the exact requested leaderboard, not parse percentile. Ranking snapshot can change between pages. Rankings alone do not establish rotation commonalities. Empty/invalid samples are not successful analysis. Anonymous rows preserve leaderboard ordinal only: analysisEligible=false, identity is unavailable and opaque report.code is not a readable report URL.'],
            nextActions=['Select only analysisEligible=true rows for report analysis; do not infer an anonymous identity or alter its opaque reference. Read selected reportUrl with query_warcraftlogs_report, match actor by name AND server, then inspect casts/events. State sampled ranks and coverage; do not claim all top N were analyzed without evidence.'])
    except Exception:
        return _packet('unavailable')

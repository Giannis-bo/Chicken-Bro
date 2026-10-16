"""Optional per-fight profiles; global character IDs are never report actor IDs."""
from collections import Counter, defaultdict
from .battle_analysis import finite

# Spell IDs from the pinned zhCN 12.1.0.69933 catalog. Positive cast records
# establish use only; an absent cast never establishes what was carried.
STONES={6262,452930,285194,285206}
HEALTH_POTIONS={1238009,1238010,1262857,415569,415628,430590,431416}
CONSUMABLES=STONES|HEALTH_POTIONS
PROFILE_QUERY='''query QqBattleProfiles($code:String!,$ids:[Int],$consumableFilter:String){reportData{report(code:$code){
 damageRankings:rankings(fightIDs:$ids,playerMetric:dps,compare:Rankings,timeframe:Historical)
 healingRankings:rankings(fightIDs:$ids,playerMetric:hps,compare:Rankings,timeframe:Historical)
 profileDetails:playerDetails(fightIDs:$ids,includeCombatantInfo:true)
 casts:table(fightIDs:$ids,dataType:Casts)
 consumables:events(fightIDs:$ids,dataType:Casts,filterExpression:$consumableFilter,limit:1000){data nextPageTimestamp}
}}}'''
CONSUMABLE_FILTER='ability.id IN ('+','.join(str(i) for i in sorted(CONSUMABLES))+')'
CORE_SLOTS={0:'头部',1:'颈部',2:'肩部',4:'胸部',5:'腰部',6:'腿部',7:'脚部',8:'手腕',9:'手部',
            10:'第一枚戒指',11:'第二枚戒指',12:'第一件饰品',13:'第二件饰品',14:'背部',15:'主手'}


def mapping(value):return value if isinstance(value,dict) else {}
def rows(value):return value if isinstance(value,list) else []
def norm(value):return ''.join(c for c in str(value or '').casefold() if c.isalnum())


def evidence(packet,view,actor,**extra):
    return dict(reportCode=packet['reportCode'],fightId=packet['fightId'],view=view,actorId=actor,
                startTime=packet['fight']['startTime'],endTime=packet['fight']['endTime'],**extra)


def _details(value):
    return mapping(mapping(mapping(value).get('data')).get('playerDetails'))


def _scores(packet,supplement,metadata):
    roles=packet.get('playerRoles',{});scores={}
    def report_identity(m):
        specs=rows(m.get('specs'))
        spec=specs[0].get('spec') if len(specs)==1 and isinstance(specs[0],dict) else None
        fields=(m.get('name'),m.get('type'),spec,m.get('server'))
        return (fields[0],norm(fields[1]),norm(fields[2]),fields[3]) if all(isinstance(v,str) and v for v in fields) else None
    identities=Counter((roles.get(actor),report_identity(m)) for actor,m in metadata.items())
    for field,metric,wanted in [('damageRankings','dps',('dps','tanks')),('healingRankings','hps',('healers',))]:
        data=rows(mapping(supplement.get(field)).get('data'))
        matched=[r for r in data if isinstance(r,dict) and type(r.get('fightID')) is int and r.get('fightID')==packet['fightId'] and
                 r.get('difficulty')==packet['fight']['difficulty'] and type(r.get('kill')) in (int,bool) and
                 bool(r['kill'])==packet['fight']['kill'] and r['kill'] in (0,1)]
        if len(matched)!=1 or not packet['fight']['kill']:continue
        fight=matched[0]
        if packet['fight'].get('keystoneLevel') and fight.get('bracketData')!=packet['fight']['keystoneLevel']:continue
        for role in wanted:
            characters=rows(mapping(mapping(fight.get('roles')).get(role)).get('characters'))
            def key(c):return (c.get('name'),norm(c.get('class')),norm(c.get('spec')),mapping(c.get('server')).get('name'))
            indexed=defaultdict(list)
            for c in characters:
                if isinstance(c,dict) and all(isinstance(c.get(k),str) and c[k] for k in ('name','class','spec')) and isinstance(mapping(c.get('server')).get('name'),str):indexed[key(c)].append(c)
            for actor,m in metadata.items():
                if roles.get(actor)!=role:continue
                identity=report_identity(m)
                if identity is None or identities[(role,identity)]!=1:continue
                values=indexed.get(identity,[])
                if len(values)!=1:continue
                value=values[0].get('rankPercent')
                if not finite(value) or value>100:continue
                scores[actor]={'score':value,'scoreMetric':metric,'scoreEvidence':evidence(packet,'rankings',actor,
                               metric=metric,compare='Rankings',timeframe='Historical',complete=True)}
    return scores


def collect_profiles(packet,tables,supplement):
    supplement=mapping(supplement);roles=packet.get('playerRoles',{});metadata={}
    # Invalid or duplicate metadata is not repaired by name-only matching.
    details=_details(supplement.get('profileDetails')) or _details(tables.get('playerDetails'))
    groups=defaultdict(list)
    for role in ('dps','healers','tanks'):
        for r in rows(details.get(role)):
            if isinstance(r,dict) and type(r.get('id')) is int and r.get('id') in roles and roles[r['id']]==role:groups[r['id']].append(r)
    baseline={}
    for role in ('dps','healers','tanks'):
        for row in rows(_details(tables.get('playerDetails')).get(role)):
            if isinstance(row,dict) and type(row.get('id')) is int:baseline[row['id']]=row
    for actor,values in groups.items():
        if len(values)!=1:continue
        value=values[0];base=baseline.get(actor,{})
        if any(value.get(k) is not None and not isinstance(value[k],str) for k in ('name','type','server')):continue
        specs=rows(value.get('specs'))
        if any(not isinstance(v,dict) or not isinstance(v.get('spec'),str) for v in specs):continue
        if any(base.get(k) and value.get(k) and str(base[k]).strip().casefold()!=value[k].strip().casefold() for k in ('name','server')):continue
        if base.get('type') and value.get('type') and norm(base['type'])!=norm(value['type']):continue
        metadata[actor]=value
    scores=_scores(packet,supplement,metadata) if packet['coverage'].get('roles') else {}
    result={actor:{**scores.get(actor,{}),'emptySlots':[],'evidence':[]} for actor in roles}
    for actor,m in metadata.items():
        specs=rows(m.get('specs'))
        result[actor].update(className=m.get('type'),spec=specs[0].get('spec') if len(specs)==1 and isinstance(specs[0],dict) else None)
        info=mapping(m.get('combatantInfo'));level=mapping(mapping(info.get('stats')).get('Item Level'))
        if finite(level.get('min')) and level['min']>0 and level.get('max')==level['min']:
            result[actor]['itemLevel']=level['min']
        gear=rows(info.get('gear'));slots={}
        if len(gear)==18 and all(isinstance(g,dict) and type(g.get('slot')) is int for g in gear):
            slots={g['slot']:g for g in gear}
            if set(slots)!=set(range(18)):slots={}
        if slots and result[actor].get('itemLevel'):
            result[actor]['emptySlots']=[name for slot,name in CORE_SLOTS.items() if type(slots[slot].get('id')) is int and slots[slot]['id']==0]
            weapon=slots[15]
            if type(weapon.get('permanentEnchant')) is int and weapon['permanentEnchant']>0 and weapon.get('permanentEnchantName'):
                result[actor]['weaponEnchant']=weapon['permanentEnchantName']
        if result[actor].get('itemLevel'):result[actor]['evidence'].append(evidence(packet,'playerDetails',actor,complete=True))
        if actor in scores:result[actor]['evidence'].append(scores[actor]['scoreEvidence'])
    cast_data=mapping(mapping(supplement.get('casts')).get('data'));casts=rows(cast_data.get('entries'))
    seen=Counter(r.get('id') for r in casts if isinstance(r,dict) and type(r.get('id')) is int)
    for r in casts:
        if (not isinstance(r,dict) or type(r.get('id')) is not int or r.get('id') not in result or seen[r['id']]!=1 or
            not finite(r.get('total')) or int(r['total'])!=r['total'] or cast_data.get('rowsTruncated')):continue
        actor=r['id'];result[actor]['cpm']=r['total']*60/packet['duration']
        result[actor]['evidence'].append(evidence(packet,'Casts',actor,complete=True,count=r['total']))
    page=mapping(supplement.get('consumables'));events=page.get('data');valid=isinstance(events,list) and len(events)<=1000 and 'nextPageTimestamp' in page and page['nextPageTimestamp'] is None
    counts=defaultdict(Counter);start,end=packet['fight']['startTime'],packet['fight']['endTime']
    for e in rows(events):
        if (not isinstance(e,dict) or e.get('type')!='cast' or type(e.get('sourceID')) is not int or e.get('sourceID') not in result or
            e.get('abilityGameID') not in CONSUMABLES or not finite(e.get('timestamp')) or
            not start<=e['timestamp']<end or ('fight' in e and e['fight']!=packet['fightId'])):
            valid=False;continue
        counts[e['sourceID']]['stone' if e['abilityGameID'] in STONES else 'healthPotion']+=1
    for actor in result:
        result[actor]['consumables']=dict(counts[actor]) if valid else None
        if valid and counts[actor]:result[actor]['evidence'].append(evidence(packet,'Casts',actor,complete=True,filterExpression=CONSUMABLE_FILTER))
    return result

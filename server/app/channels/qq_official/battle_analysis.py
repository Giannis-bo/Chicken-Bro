"""Deterministic raid observations, each retaining scope and source evidence."""
from collections import Counter
from math import isfinite

from .query_labels import label


def finite(value):
    return type(value) in (int,float) and isfinite(value) and value>=0


def select_windows(fight,deaths):
    start,end=fight['startTime'],fight['endTime'];ids=set(fight.get('friendlyPlayers') or [])
    events=sorted((e for e in deaths if e.get('type')=='death' and
                 e.get('targetID') in ids and finite(e.get('timestamp')) and start<=e['timestamp']<end)
                  ,key=lambda e:e['timestamp'])
    requested=[]
    seen=set()
    for event in events:
        if event['targetID'] in seen:continue
        seen.add(event['targetID']);t=event['timestamp']
        requested.append((max(start,t-5000),min(end,t+1000)))
        if len(requested)==3:break
    if not requested:requested.append((max(start,end-10000),end))
    merged=[]
    for a,b in sorted(requested):
        if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
        else:merged.append((a,b))
    return merged[:3]


def analyze_battle(code,url,fight,master,tables,death_page,windows):
    from .battle_commands import clock_text,amount_text,battle_kind,battle_detail_limit
    from .query_commands import markdown_text as md
    start,end=fight['startTime'],fight['endTime'];fight_id=fight['id'];limit=battle_detail_limit(fight)
    actors={a['id']:a for a in master.get('actors',[]) if isinstance(a,dict) and type(a.get('id')) is int}
    ids=set(i for i in fight.get('friendlyPlayers',[]) if type(i) is int)
    players={i:actors[i] for i in ids if i in actors and actors[i].get('type')=='Player'}
    abilities={a['gameID']:str(a.get('name') or '') for a in master.get('abilities',[])
               if isinstance(a,dict) and type(a.get('gameID')) is int}
    def spell(value):return '普通攻击' if value==1 else abilities.get(value) or '技能#'+str(value or '未知')
    def evidence(view,**fields):
        return {'reportCode':code,'fightId':fight_id,'view':view,**fields}
    details=((tables.get('playerDetails') or {}).get('data') or {}).get('playerDetails') or {}
    roles={};role_labels={'dps':'输出','healers':'治疗','tanks':'坦克'};ambiguous_roles=False
    for role in role_labels:
        for row in details.get(role,[]):
            if isinstance(row,dict) and row.get('id') in players:
                if row['id'] in roles:ambiguous_roles=True
                roles[row['id']]=role
    coverage={'actors':len(players)==len(ids) and bool(ids),'deaths':death_page['complete']}
    coverage['roles']=coverage['actors'] and not ambiguous_roles and set(roles)==set(players)
    good=[];grouped={}
    for field,metric,role in [('damage','damage','dps'),('healing','effective_healing','healers')]:
        data=(tables.get(field) or {}).get('data');rows=data.get('entries') if isinstance(data,dict) else None
        valid=isinstance(rows,list) and not data.get('rowsTruncated',False)
        candidates=[];seen=set()
        for row in rows or []:
            if not isinstance(row,dict):valid=False;continue
            actor=row.get('id')
            if roles.get(actor)!=role:continue
            if actor in seen or not finite(row.get('total')):valid=False;continue
            seen.add(actor);candidates.append((actor,row['total']))
        expected={i for i,r in roles.items() if r==role}
        # An absent table row could be zero or omitted: rank only complete groups.
        valid=valid and bool(expected) and seen==expected and coverage['roles']
        coverage[field]=valid
        grouped[field]=[]
        if valid:
            candidates.sort(key=lambda x:(-x[1],x[0]));total=sum(v for i,v in candidates)
            for actor,amount in candidates:
                if not amount or not total:continue
                rank=1+sum(v>amount for i,v in candidates)
                grouped[field].append({'actorId':actor,'name':players[actor]['name'],'metric':metric,
                    'roleLabel':role_labels[role],'amount':amount,'share':amount/total*100,
                    'rank':rank,'roleCount':len(candidates),
                    'evidence':[evidence(field,actorId=actor,startTime=start,endTime=end,complete=True)]})
    # Give both output and healing evidence room; a global DPS/HPS score would
    # conflate different duties. No tank quality score is inferred from damage.
    damage,healing=grouped['damage'],grouped['healing']
    if damage:good.append(damage[0])
    if healing:good.append(healing[0])
    if len(damage)>1:good.append(damage[1])
    elif len(healing)>1:good.append(healing[1])
    deaths=[]
    for event in death_page['events']:
        actor=event.get('targetID');timestamp=event.get('timestamp')
        if event.get('type')!='death' or actor not in players or not finite(timestamp) or not start<=timestamp<end:continue
        deaths.append({'actorId':actor,'name':players[actor]['name'],'timestamp':timestamp,
            'time':(timestamp-start)/1000,'ability':spell(event.get('killingAbilityGameID')),
            'abilityId':event.get('killingAbilityGameID'),'killerId':event.get('killerID'),
            'evidence':[evidence('Deaths',actorId=actor,timestamp=timestamp,complete=death_page['complete'])]})
    deaths.sort(key=lambda d:(d['timestamp'],d['actorId']))
    damage_windows=[]
    for window in windows:
        targets=set();totals=Counter();known=True
        for event in window['events']:
            if event.get('type')!='damage' or event.get('targetID') not in players:continue
            if not finite(event.get('amount')):known=False;continue
            if event['amount']<=0:continue
            targets.add(event['targetID']);totals[event.get('abilityGameID')]+=event['amount']
        if totals:
            damage_windows.append({'startTime':window['startTime'],'endTime':window['endTime'],
                'amount':sum(totals.values()),'targetCount':len(targets),
                'complete':window['complete'] and known and coverage['actors'],
                'abilities':[{'abilityId':a,'ability':spell(a),'amount':v} for a,v in totals.most_common(3)],
                'evidence':[evidence('DamageTaken',startTime=window['startTime'],endTime=window['endTime'],
                                     complete=window['complete'] and known)]})
    counts=Counter(d['actorId'] for d in deaths);review=[];seen=set()
    for death in deaths:
        actor,timestamp=death['actorId'],death['timestamp']
        if actor in seen:continue
        relevant=[w for w in windows if w['startTime']<=max(start,timestamp-5000) and w['endTime']>timestamp]
        window=next((w for w in relevant if w['complete']),next(iter(relevant),None))
        if not window:continue
        hits=[]
        for event in window['events']:
            if (event.get('type')!='damage' or event.get('targetID')!=actor or
                not max(start,timestamp-5000)<=event['timestamp']<=timestamp or not finite(event.get('amount')) or event['amount']<=0):continue
            hits.append({'time':(event['timestamp']-start)/1000,'timestamp':event['timestamp'],
                'ability':spell(event.get('abilityGameID')),'abilityId':event.get('abilityGameID'),
                'amount':event['amount'],'sourceId':event.get('sourceID')})
        hits.sort(key=lambda h:h['timestamp'])
        if not hits:continue
        seen.add(actor)
        review.append({'actorId':actor,'name':death['name'],'death':death,'deathCount':counts[actor],
            'hits':hits[-3:],'complete':window['complete'] and death_page['complete'],
            'evidence':death['evidence']+[evidence('DamageTaken',actorId=actor,
                startTime=max(start,timestamp-5000),endTime=timestamp,complete=window['complete'])]})
        if len(review)==limit:break
    highlights=[]
    if deaths:
        first=deaths[0];simultaneous=[d for d in deaths if d['timestamp']==first['timestamp']]
        highlights.append('**死亡记录**\n'+('本场' if death_page['complete'] and coverage['actors'] else '已核验玩家中')+
            f'死亡{len(deaths)}次；首次{clock_text(first["time"])}，'+
            '、'.join(md(d['name'],25) for d in simultaneous[:3])+('等' if len(simultaneous)>3 else '')+'。')
    elif death_page['complete'] and coverage['actors']:highlights.append('**死亡记录**\n本场未记录玩家死亡。')
    if damage:
        row=damage[0];highlights.append('**输出贡献**\n'+md(row['name'],35)+'记录伤害'+amount_text(row['amount'])+
            f'，占输出职责已核验总量{row["share"]:.1f}%。')
    if healing:
        row=healing[0];highlights.append('**治疗贡献**\n'+md(row['name'],35)+'有效治疗'+amount_text(row['amount'])+
            f'，占治疗职责已核验总量{row["share"]:.1f}%。')
    # A verified window is a sampled observation, not a whole-fight peak claim.
    if damage_windows:
        window=max(damage_windows,key=lambda w:w['amount']);ability=window['abilities'][0]
        highlights=highlights[:2]+['**承伤片段**\n'+clock_text((window['startTime']-start)/1000)+'–'+
            clock_text((window['endTime']-start)/1000)+'，'+str(window['targetCount'])+'名玩家'+
            ('合计承伤' if window['complete'] else '已读取承伤')+amount_text(window['amount'])+
            '；主要来源'+md(ability['ability'],40)+'。']
    gaps=[]
    for key,name in [('actors','参战成员映射'),('roles','参战职责映射'),('damage','输出职责伤害表'),('healing','治疗职责有效治疗表'),('deaths','死亡事件')]:
        if not coverage[key]:gaps.append(name)
    if any(not w['complete'] for w in windows):gaps.append('部分承伤窗口')
    if not highlights:highlights=['当前只取得战斗身份信息，尚无足够完整的统计证据。']
    return {'schema':'qq-battle-v1','status':'ready','reportCode':code,'sourceUrl':url,'fightId':fight_id,
        'fight':{k:v for k,v in fight.items() if k in ('id','name','difficulty','kill','startTime','endTime','keystoneLevel','gameZone')},
        'battleType':'mythic_plus' if fight.get('keystoneLevel') else 'raid',
        'detailMaxPlayers':limit,
        'difficulty':battle_kind(fight),
        'duration':(end-start)/1000,'playerCount':len(ids),'coverage':coverage,'gaps':gaps,
        'playerRoles':roles if coverage['roles'] else {},'roleContributions':grouped,
        'deaths':deaths,'good':good[:limit],'review':review,'highlights':highlights[:3],'damageWindows':damage_windows,
        'windows':[{k:v for k,v in w.items() if k!='events'} for w in windows]}

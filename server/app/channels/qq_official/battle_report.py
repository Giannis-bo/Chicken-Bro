"""One evidence-bound team report for raids and whole Mythic+ runs."""
from collections import Counter, defaultdict

from .battle_analysis import finite
from .battle_commands import amount_text, clock_text, battle_detail_limit
from .query_commands import markdown_text as md

REPORT_VERSION = 'team-report-v5'


def pressure_window(packet):
    return max((w for w in packet.get('damageWindows', []) if w.get('complete')),
               key=lambda w: w['amount'], default=None)


def sentences(text, limit=150):
    """Keep complete conclusions; never slice a number or its qualification."""
    kept = ''
    for part in text.split('。'):
        if not part: continue
        if kept and len(kept)+len(part)+1 > limit: break
        kept += part+'。'
    return kept


def _evidence(packet, view, **extra):
    return dict(dict(reportCode=packet['reportCode'], fightId=packet['fightId'], view=view,
                startTime=packet['fight']['startTime'], endTime=packet['fight']['endTime'],
                complete=True), **extra)


def _utility(packet, master, extra):
    players = set(packet.get('playerRoles', {})); abilities = {
        a['gameID']: a.get('name') for a in master.get('abilities', []) if type(a.get('gameID')) is int}
    result = {}
    actors={a['id']:a for a in master.get('actors',[]) if type(a.get('id')) is int}
    def owner(source):
        if source in players:return source
        actor=actors.get(source,{})
        return actor.get('petOwner') if actor.get('type')=='Pet' and actor.get('petOwner') in players else None
    start,end=packet['fight']['startTime'],packet['fight']['endTime']
    for key,event_type in [('interrupts','interrupt'),('dispels','dispel')]:
        page=extra.get(key) or {};events=page.get('data');counts=Counter();spells=defaultdict(Counter)
        valid=(isinstance(events,list) and len(events)<=1000 and
               'nextPageTimestamp' in page and page['nextPageTimestamp'] is None and
               packet['coverage'].get('actors') and packet['coverage'].get('roles'))
        for e in events or []:
            if not isinstance(e,dict):valid=False;continue
            # WCL's Interrupts view also contains applydebuff control records.
            # Those cannot be counted as completed interrupt events.
            if e.get('type')!=event_type:continue
            actor=owner(e.get('sourceID'))
            if (actor is None or
                not finite(e.get('timestamp')) or not start<=e['timestamp']<end or
                ('fight' in e and e['fight']!=packet['fightId'])):
                valid=False;continue
            counts[actor]+=1
            spell=e.get('extraAbilityGameID')
            if type(spell) is int:spells[actor][spell]+=1
        result[key]={'complete':bool(valid),'total':sum(counts.values()) if valid else None,
                     'actors':dict(counts) if valid else {},'spells':{
                         actor:[{'abilityId':i,'name':abilities.get(i) or '技能#'+str(i),'count':n}
                                for i,n in values.most_common(2)] for actor,values in spells.items()} if valid else {}}
    return result


def _pressure(packet, extra):
    window=pressure_window(packet)
    if not window:return None
    value=dict(window);data=(extra.get('pressureHealing') or {}).get('data');rows=data.get('entries') if isinstance(data,dict) else None
    roles=packet.get('playerRoles',{});known=set(roles);heals={};valid=isinstance(rows,list) and not data.get('rowsTruncated',False)
    for row in rows or []:
        if (not isinstance(row,dict) or row.get('id') not in known or row['id'] in heals or
                not finite(row.get('total'))):
            valid=False;continue
        heals[row['id']]=row['total']
    if valid and packet['coverage'].get('roles'):
        value['healing']=sum(heals.values());value['healers']=heals
        value['healingEvidence']=_evidence(packet,'Healing',startTime=window['startTime'],endTime=window['endTime'])
    return value


def _timeline(packet):
    deaths=packet.get('deaths',[]);full=packet['coverage'].get('deaths') and packet['coverage'].get('actors')
    if not full:return '已读取'+str(len(deaths))+'次死亡；减员时间线未完整。'
    if not deaths:return '本场未记录玩家死亡。'
    first,last=deaths[0]['time'],deaths[-1]['time'];count=len(deaths);people=len({d['actorId'] for d in deaths})
    text=f'本场死亡{count}次，涉及{people}人；'
    if count==1:text+=clock_text(first)+'出现唯一一次减员，'
    else:text+='首次'+clock_text(first)+'，最后一次'+clock_text(last)+'；'
    rest=packet['duration']-last
    if rest>=30:text+='后续'+clock_text(rest)+'未再记录死亡。'
    else:text+='最后一次减员距战斗结束'+clock_text(rest)+'。'
    return text


def _person_rows(packet,tables):
    counts=Counter(d['actorId'] for d in packet.get('deaths',[]))
    full=packet['coverage'].get('deaths') and packet['coverage'].get('actors')
    utility=packet['teamReport']['utility'];pressure=packet['teamReport']['pressure']
    by_actor={};duration=packet['duration']
    for field in ('damage','healing'):
        source=((tables.get(field) or {}).get('data') or {}).get('entries',[])
        by_actor[field]={r['id']:r for r in source if isinstance(r,dict) and type(r.get('id')) is int}
    for row in packet.get('good',[]):
        healing=row['metric']=='effective_healing';field='healing' if healing else 'damage'
        metric='有效治疗' if healing else '伤害';rate='HPS' if healing else 'DPS';analysis=[]
        count=row['roleCount'];actor=row['actorId'];raw=by_actor[field].get(actor,{})
        if healing and count==1:
            conclusion='本场唯一治疗。'
            if pressure and pressure.get('healing',0)>0 and actor in pressure.get('healers',{}):
                conclusion+='关键窗口承担玩家有效治疗的'+f'{pressure["healers"][actor]/pressure["healing"]*100:.1f}%'+'。'
        else:
            conclusion=('治疗' if healing else '输出')+f'职责第{row["rank"]}/{count}，承担同职责总量{row["share"]:.1f}%。'
        analysis.append('贡献结论：'+conclusion)
        detail=f'证据：整场{metric}{amount_text(row["amount"])}'
        if duration>0:detail+='，按全程时长折算'+rate+' '+amount_text(row['amount']/duration)
        peers=packet.get('roleContributions',{}).get(field,[])
        if not healing and row['rank']==1 and len(peers)>1:
            gap=row['amount']-peers[1]['amount']
            detail+='；'+('与第二名并列' if gap==0 else '比第二名多'+amount_text(gap))
        detail+='。';analysis.append(detail)
        abilities=raw.get('abilities')
        valid=[a for a in abilities or [] if isinstance(a,dict) and isinstance(a.get('name'),str) and finite(a.get('total')) and a['total']>0]
        if valid:
            a=max(valid,key=lambda a:a['total'])
            if a['total']<=row['amount']:
                name='普通攻击' if a.get('guid')==1 else a['name']
                analysis.append('主要技能：'+md(name,24)+'贡献'+amount_text(a['total'])+f'，占本人{metric}{a["total"]/row["amount"]*100:.1f}%。')
        if healing and pressure and actor in pressure.get('healers',{}) and pressure['healers'][actor]>0:
            a,b=pressure['startTime'],pressure['endTime'];start=packet['fight']['startTime']
            analysis.append('关键窗口：'+clock_text((a-start)/1000)+'–'+clock_text((b-start)/1000)+
                            '，本人有效治疗'+amount_text(pressure['healers'][actor])+'；该段队伍承伤'+amount_text(pressure['amount'])+'。')
            row['evidence'].append(pressure['healingEvidence'])
        jobs=[]
        for key,name in [('interrupts','中断施法'),('dispels','驱散')]:
            u=utility[key];n=u['actors'].get(actor,0)
            if u['complete'] and n:
                text=name+str(n)+'次'
                spells=u['spells'].get(actor,[])
                if spells:text+='（'+md(spells[0]['name'],18)+str(spells[0]['count'])+'次）'
                jobs.append(text);row['evidence'].append(_evidence(packet,key,actorId=actor))
        if jobs:analysis.append('机制贡献：'+'；'.join(jobs)+'。')
        if full:analysis.append('生存记录：'+('本场已记录死亡'+str(counts[actor])+'次。' if counts[actor] else '本场未记录死亡。'))
        row['analysis']=analysis


def _review_rows(packet):
    counts=Counter((r['sourceId'],r['abilityId']) for r in packet.get('causes',[]))
    full=packet['coverage'].get('deaths') and packet['coverage'].get('actors')
    roles=packet.get('playerRoles',{});names={'dps':'输出','healers':'治疗','tanks':'坦克'}
    for row in packet.get('review',[]):
        if not row.get('conclusion'):continue
        process=[]
        if row.get('healthBeforeBurst') is not None and row.get('maxHealth'):
            process.append('伤前生命'+amount_text(row['healthBeforeBurst'])+'/'+amount_text(row['maxHealth']))
        if finite(row.get('healingLast2Seconds')):
            process.append('致死前2秒有效治疗'+amount_text(row['healingLast2Seconds']))
        if row.get('recordedDefensives'):process.append('已有'+'、'.join(row['recordedDefensives'][:2]))
        impact=clock_text(row['death']['time'])+'损失1名'+names.get(roles.get(row['actorId']),'队员')
        if full:impact+='；该角色本场死亡'+str(row.get('deathCount',1))+'次'
        n=counts[(row['sourceId'],row['abilityId'])]
        if n>1:impact+='；同来源同技能关联'+str(n)+'次已核验减员'
        row['analysis']=['结论：'+row['conclusion'], '过程证据：'+'，'.join(process)+'。', '战斗影响：'+impact+'。']


def build_team_report(packet,tables,master,extra):
    """Retain whole-fight observations even when the death analyzer found a cause."""
    packet['reportVersion']=REPORT_VERSION
    utility=_utility(packet,master,extra);pressure=_pressure(packet,extra)
    packet['teamReport']={'timeline':_timeline(packet),'utility':utility,'pressure':pressure}
    _person_rows(packet,tables);_review_rows(packet)
    blocks=['**整场结论**\n'+packet['teamReport']['timeline']]
    contributions=[]
    for row in packet.get('good',[])[:2]:
        if row['metric']=='effective_healing' and row['roleCount']==1:
            contributions.append(md(row['name'],22)+'为唯一治疗，整场有效治疗'+amount_text(row['amount']))
        else:
            contributions.append(md(row['name'],22)+('有效治疗' if row['metric']=='effective_healing' else '伤害')+
                                 amount_text(row['amount'])+f'，占同职责{row["share"]:.1f}%')
    jobs=[]
    for key,name in [('interrupts','中断施法'),('dispels','驱散')]:
        u=utility[key]
        if u['complete'] and u['total']:jobs.append(name+str(u['total'])+'次')
    if jobs:contributions.append('队伍'+'、'.join(jobs))
    if contributions:blocks.append('**队伍表现**\n'+'；'.join(contributions)+'。')
    causes=packet.get('causes',[])
    if causes:
        groups={}
        priority={'non_tank_melee':5,'repeated_hits':4,'over_max_health':3,'dot_finisher':2,'lethal_hit':1}
        ordered=sorted(causes,key=lambda r:(-priority.get(r.get('cause'),0),r['death']['timestamp']))
        for r in ordered:
            if r.get('conclusion'):groups.setdefault((r['sourceId'],r['abilityId']),r)
        details=[]
        for r in list(groups.values())[:3]:
            details.append(clock_text(r['death']['time'])+' '+md(r['name'],20)+'：'+sentences(r['conclusion'],145))
        if details:blocks.append('**减员原因**\n'+'\n'.join(details))
    elif packet.get('deaths'):
        d=packet['deaths'][0]
        blocks.append('**减员记录**\n'+clock_text(d['time'])+' '+md(d['name'],22)+'；已核验致死过程不足，保留死亡与承伤事实。')
    if pressure:
        start=packet['fight']['startTime'];top=pressure['abilities'][0];name='普通攻击' if top['abilityId']==1 else top['ability']
        text=clock_text((pressure['startTime']-start)/1000)+'–'+clock_text((pressure['endTime']-start)/1000)+f'，{pressure["targetCount"]}人合计承伤'+amount_text(pressure['amount'])+'；主要来源'+md(name,25)+amount_text(top['amount'])+'。'
        if 'healing' in pressure:text+='同窗玩家有效治疗'+amount_text(pressure['healing'])+'。'
        blocks.append('**关键承伤片段**\n'+text)
    # Evidence budget gives every main section space; no arbitrary character cut.
    packet['highlights']=blocks
    return packet

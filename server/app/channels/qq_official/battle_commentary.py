"""Specific player commentary from source facts, with restrained game-only banter."""
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from .battle_profile import collect_profiles
from .battle_commands import amount_text,clock_text,battle_detail_limit
from .query_commands import markdown_text as md
from .query_labels import label
from .battle_report import sentences

COMMENTARY_VERSION='battle-commentary-v6'


def number(value):return str(int(Decimal(str(value)).quantize(Decimal('1'),rounding=ROUND_HALF_UP)))
def amount(value):return f'{value/100000000:.2f}亿' if value>=100000000 else amount_text(value)


def identity(profile):
    parts=[]
    if profile.get('score') is not None:
        parts.append('WCL分数'+number(profile['score'])+'（'+('治疗' if profile['scoreMetric']=='hps' else '输出')+'）')
    cls={'DeathKnight':'Death Knight','DemonHunter':'Demon Hunter'}.get(profile.get('className'),profile.get('className'))
    spec={'BeastMastery':'Beast Mastery'}.get(profile.get('spec'),profile.get('spec'))
    if spec and label(spec)!=spec:parts.append(label(spec)+(label(cls) if cls and label(cls)!=cls else ''))
    if profile.get('itemLevel'):parts.append('装等'+number(profile['itemLevel']))
    return '，'.join(parts)


def _extras(profile):
    values=[]
    if profile.get('cpm') is not None:values.append(f'全程CPM {profile["cpm"]:.1f}')
    uses=profile.get('consumables') or {};used=[]
    for key,name in [('stone','治疗石'),('healthPotion','治疗药水')]:
        if uses.get(key):used.append(name+str(uses[key])+'次')
    if used:values.append('本场使用'+'、'.join(used))
    return '；'.join(values)+('。' if values else '')


def _utility(packet,actor):
    values=[]
    for key,name in [('interrupts','中断施法'),('dispels','驱散')]:
        data=packet['teamReport']['utility'][key];count=data['actors'].get(actor,0)
        if data['complete'] and count:
            text=name+str(count)+'次';spells=data['spells'].get(actor,[])
            if spells:text+='，其中'+md(spells[0]['name'],18)+str(spells[0]['count'])+'次'
            values.append(text)
    return '；'.join(values)+('。' if values else '')


def _good(packet,row,profile,counts,full,profiles):
    actor=row['actorId'];healing=row['metric']=='effective_healing';opening=identity(profile)
    metric='有效治疗' if healing else '伤害'
    text=(opening+'，' if opening else '')+amount(row['amount'])+metric
    if healing and row['roleCount']==1:text+='，是本场唯一治疗。'
    else:text+='，'+('治疗' if healing else '输出')+f'第{row["rank"]}/{row["roleCount"]}，占同职责{row["share"]:.1f}%。'
    peers=packet.get('roleContributions',{}).get('healing' if healing else 'damage',[])
    if row['rank']==1 and len(peers)>1:
        gap=row['amount']-peers[1]['amount']
        text+=('与第二名并列。' if gap==0 else '领先第二名'+amount(gap)+'。')
    units=[text];pressure=packet['teamReport']['pressure']
    if healing and pressure and pressure.get('healers',{}).get(actor,0)>0:
        a=clock_text((pressure['startTime']-packet['fight']['startTime'])/1000);b=clock_text((pressure['endTime']-packet['fight']['startTime'])/1000)
        units.append(a+'–'+b+'队伍承伤'+amount(pressure['amount'])+'，你提供'+amount(pressure['healers'][actor])+'有效治疗。')
    utility=_utility(packet,actor)
    if utility:units.append(utility)
    if full:units.append('本场'+('记录死亡'+str(counts[actor])+'次。' if counts[actor] else '没有死亡。'))
    extras=_extras(profile)
    if extras:units.append(extras)
    if profile.get('emptySlots'):units.append('日志装备快照中'+ '、'.join(profile['emptySlots'][:2])+'栏为空。')
    # A low score can coexist with the highest team total; neither rewrites the
    # other. Utility and survival determine the closing observation as well.
    if full and counts[actor]:quip='贡献排得上号，减员这笔账也得一起记。'
    elif healing and packet['teamReport']['utility']['dispels']['actors'].get(actor,0)>0:quip='治疗和驱散两份活都交了作业，这份贡献得记。'
    elif not healing and row['rank']==1 and row['roleCount']>1 and utility:quip='伤害榜顶上有你，处理机制的名单里也有你，这个第一拿得有内容。'
    elif not healing and row['rank']==1 and full:quip='队内伤害排第一，全程也站住了，这两项表现都交了账。'
    elif healing and pressure and pressure.get('healers',{}).get(actor,0)>0:quip='治疗榜的贡献落在了实际承伤窗口，这份成绩有具体落点。'
    else:quip=''
    if not healing and row['rank']>1 and profile.get('score',0)>=75:
        same=[r for r in peers if r['actorId']!=actor and r['amount']>=row['amount'] and
              profile.get('spec') and profiles.get(r['actorId'],{}).get('spec')==profile['spec'] and
              profiles.get(r['actorId'],{}).get('className')==profile.get('className')]
        if same:
            best=max(same,key=lambda r:r['amount'])
            gap=(best['amount']-row['amount'])/best['amount']*100 if best['amount'] else 100
            if gap<=10:quip=f'离本场同专精第一只差{gap:.1f}%，第一梯队咬得很紧。'
    if not healing and row['rank']==1 and full and not counts[actor] and any((profile.get('consumables') or {}).values()):
        quip='伤害榜第一，全程没有死亡，保命手段也有实际使用记录，这份输出是站着打出来的。'
    # Put the verdict beside its evidence before optional activity statistics.
    if quip:units.insert(min(3,len(units)),quip)
    row['analysis']=units;row['requiredAnalysis']=[0];row['prose']=True;row['evidence']+=profile.get('evidence',[])
    return row


def _death(row,profile):
    prefix=identity(profile);units=[]
    if prefix:units.append(prefix+'。')
    cause_index=len(units)
    conclusion=row['conclusion']
    first,sep,rest=conclusion.partition('。')
    if sep and '已被补满' in first:
        conclusion=rest+first+'。'
    units.append(clock_text(row['death']['time'])+'：'+conclusion)
    process=[]
    if row.get('healthBeforeBurst') is not None and row.get('maxHealth'):
        process.append('伤前生命'+amount(row['healthBeforeBurst'])+'/'+amount(row['maxHealth']))
    if row.get('healingLast2Seconds') is not None:process.append('致死伤害前2秒实际有效治疗'+amount(row['healingLast2Seconds']))
    if process:units.append('，'.join(process)+'。')
    if row.get('cause')=='non_tank_melee' and row.get('maxHealth') and row['fatalDamage']>row['maxHealth']:
        units.append('这一下超过整条血量上限，单靠把血补满挡不住。')
    elif row.get('cause')=='repeated_hits':units.append('问题落在这次伤害叠加，已有减伤和实际治疗也要一起算进判断。' if row.get('recordedDefensives') else '这次减员的关键，是连续伤害叠在同一个人身上。')
    if row.get('deathCount',0)>1:units.append('这个角色本场共记录死亡'+str(row['deathCount'])+'次。')
    extras=_extras(profile)
    if extras:units.append(extras)
    row['analysis']=units;row['requiredAnalysis']=[cause_index]+([cause_index+1] if process and row.get('cause')!='over_max_health' else []);row['prose']=True;row['evidence']+=profile.get('evidence',[])
    return row


def _contribution_targets(packet,profiles):
    peers=packet.get('roleContributions',{}).get('damage',[]);result=[]
    for row in peers:
        p=profiles.get(row['actorId'],{})
        if p.get('score') is None or p['score']>25 or not p.get('spec') or not p.get('itemLevel'):continue
        matches=[r for r in peers if r['actorId']!=row['actorId'] and
                 profiles.get(r['actorId'],{}).get('className')==p.get('className') and
                 profiles.get(r['actorId'],{}).get('spec')==p['spec'] and
                 profiles.get(r['actorId'],{}).get('itemLevel') and
                 abs(profiles[r['actorId']]['itemLevel']-p['itemLevel'])<=5]
        if not matches:continue
        peer=max(matches,key=lambda r:r['amount'])
        if peer['amount']<=0 or row['amount']>peer['amount']*.75:continue
        deficit=(peer['amount']-row['amount'])/peer['amount']*100
        text=identity(p)+'，整场伤害'+amount(row['amount'])+'。'
        comparison='同专精'+md(peer['name'],20)+'打了'+amount(peer['amount'])+f'，两人装等差不超过5，你的伤害少{deficit:.1f}%。'
        closing='同专精队友已经交卷，你这份伤害还差一大截。'
        empty=p.get('emptySlots',[])
        if empty:closing+='日志里'+ '、'.join(empty[:2])+'装备栏为空，开打前的准备也有明确缺口。'
        result.append({**row,'reviewCategory':'contribution','analysis':[text,comparison,closing],'requiredAnalysis':[0,1],
                       'prose':True,'evidence':row['evidence']+p.get('evidence',[])+peer['evidence']})
    return sorted(result,key=lambda r:profiles[r['actorId']]['score'])


def apply_commentary(packet,tables,master,supplement):
    try:profiles=collect_profiles(packet,tables,supplement)
    except (TypeError,ValueError,KeyError,OverflowError):
        profiles=collect_profiles(packet,tables,{})
        packet['optionalProfileRejected']=True
    packet['playerAssessments']=profiles
    packet['commentaryVersion']=COMMENTARY_VERSION
    full=packet['coverage'].get('deaths') and packet['coverage'].get('actors')
    counts=Counter(d['actorId'] for d in packet['deaths']);limit=battle_detail_limit(packet['fight'])
    for row in packet['good'][:limit]:_good(packet,row,profiles.get(row['actorId'],{}),counts,full,profiles)
    packet['good']=packet['good'][:limit]
    for row in packet['review']:
        if row.get('conclusion'):_death(row,profiles.get(row['actorId'],{}))
    targets=[r for r in _contribution_targets(packet,profiles) if r['actorId'] not in {r['actorId'] for r in packet['review']}]
    if targets:
        packet['review']=packet['review'][:max(0,limit-1)]+targets[:1]
    packet['review']=packet['review'][:limit]
    original=packet['highlights'];blocks=[original[0]]
    if packet['good']:
        parts=[]
        for row in packet['good'][:2]:
            # Short prose retains the leading quantitative statement and one
            # specific secondary contribution; the command holds full details.
            content=row['analysis'][0]
            utility=_utility(packet,row['actorId'])
            if utility:content+=utility
            elif row['metric']=='effective_healing':
                content+=next((v for v in row['analysis'] if '队伍承伤' in v),'')
            if full:content+='本场'+('记录死亡'+str(counts[row['actorId']])+'次。' if counts[row['actorId']] else '没有死亡。')
            parts.append('**'+md(row['name'],22)+'**：'+content)
        blocks.append('**队伍表现**\n'+'\n'.join(parts))
    # The independent cause grouping remains intact; no actor-limit projection
    # may silently hide a different failure mechanism from the summary.
    blocks.extend(b for b in original[1:] if b.startswith('**减员'))
    pressure=next((b for b in original if b.startswith('**关键承伤')),None)
    if pressure:
        conclusion='本场最值得盯住的是已出现的重复承伤。' if any(r.get('cause')=='repeated_hits' for r in packet.get('causes',[])) else '本场明确的减员问题是非坦承接致死普攻。' if any(r.get('cause')=='non_tank_melee' for r in packet.get('causes',[])) else '整场评价结合实际贡献与这些关键时点。'
        blocks.append(pressure+'\n'+conclusion)
    packet['highlights']=blocks
    return packet

"""Evidence-bound death reconstruction. No report IDs or player-name rules."""
from collections import defaultdict
from math import ceil

from .battle_analysis import finite
from .battle_commands import amount_text, clock_text, battle_detail_limit
from .query_commands import markdown_text as md

# Reviewed spell semantics, independent of any one report. Other spells use
# numerical reconstruction only; names never decide whether damage is avoidable.
GROUND_IMPACTS = {1286885}
PURGE = 1305878
PURGE_MARK = 1312967
COILS = {1308927, 1287265, 1299010}
MECHANIC_SOURCE = 'https://www.method.gg/guides/the-venomous-abyss/ulatek-heroic'
DEFENSIVES = {97463: '集结呐喊', 325174: '灵魂链接', 386208: '防御姿态',
              871: '盾墙', 498: '圣佑术', 642: '圣盾术', 22812: '树皮术',
              61336: '生存本能', 33206: '痛苦压制', 47788: '守护之魂',
              48792: '冰封之韧', 1966: '佯攻', 31224: '暗影斗篷',
              363916: '黑曜鳞片', 198589: '疾影'}


def select_deaths(fight, events):
    players = set(fight.get('friendlyPlayers') or [])
    rows = sorted((e for e in events if e.get('type') == 'death' and
                   e.get('targetID') in players and finite(e.get('timestamp')) and
                   fight['startTime'] <= e['timestamp'] < fight['endTime']),
                  key=lambda e: (e['timestamp'], e['targetID']))
    return rows if len(rows) <= 12 else rows[:6] + rows[-6:]


def hit_damage(event):
    """Post-mitigation damage includes lethal overkill, never counts absorbs twice."""
    amount = event.get('amount')
    if not finite(amount):
        return None
    if event.get('hitPoints') == 0 and not finite(event.get('overkill')):
        fields = [event.get(k) for k in ('unmitigatedAmount', 'mitigated', 'absorbed')]
        if not all(finite(v) for v in fields):
            return None
        reconstructed = fields[0]-fields[1]-fields[2]
        return reconstructed if reconstructed >= amount else None
    overkill = event.get('overkill', 0)
    if type(overkill) not in (int, float) or not finite(max(0, overkill)):
        return None
    return amount + max(0, overkill)


def analyze_death(death, bundle, master, roles, start, report, fight_id):
    actor, timestamp = death['actorId'], death['timestamp']
    if bundle.get('actorId') != actor or bundle.get('deathTimestamp') != timestamp:
        return None
    damage, incoming = bundle.get('damage', {}), bundle.get('incoming', {})
    if not damage.get('complete') or not incoming.get('complete'):
        return None
    if any(e.get('targetID') != actor for p in (damage, incoming) for e in p.get('events', [])):
        return None
    hits = sorted((e for e in damage.get('events', []) if e.get('type') == 'damage' and
                   finite(e.get('timestamp')) and timestamp - 10000 <= e['timestamp'] <= timestamp and
                   hit_damage(e) is not None and hit_damage(e) > 0), key=lambda e: e['timestamp'])
    if not hits:
        return None
    fatal = hits[-1]
    # Mere proximity to a death is insufficient. Require the actual killing
    # record, consistent spell/killer identity and an unambiguous lethal marker.
    if timestamp - fatal['timestamp'] > 500 or not (
        (finite(fatal.get('overkill')) and fatal['overkill'] > 0) or fatal.get('hitPoints') == 0
    ):
        return None
    if death.get('abilityId') and fatal.get('abilityGameID') != death['abilityId']:
        return None
    if death.get('killerId') and fatal.get('sourceID') != death['killerId']:
        return None
    abilities = {a['gameID']: a.get('name') or '技能#' + str(a['gameID'])
                 for a in master.get('abilities', []) if type(a.get('gameID')) is int}
    actors = {a['id']: a for a in master.get('actors', []) if type(a.get('id')) is int}
    ability = fatal.get('abilityGameID'); source = fatal.get('sourceID')
    spell = '普通攻击' if ability == 1 else abilities.get(ability, '技能#' + str(ability))
    source_name = actors.get(source, {}).get('name') or '来源#' + str(source)
    cluster = [fatal]
    if not fatal.get('tick'):
        for e in reversed(hits[:-1]):
            if fatal['timestamp'] - e['timestamp'] > 100:
                break
            if (e.get('abilityGameID') == ability and e.get('sourceID') == source and
                e.get('sourceInstance') == fatal.get('sourceInstance') and not e.get('tick')):
                cluster.insert(0, e)
    total = sum(hit_damage(e) for e in cluster)
    maximum = fatal.get('maxHitPoints')
    maximum = maximum if finite(maximum) and maximum > 0 else None
    first = cluster[0]
    before = first.get('hitPoints')
    before = before + first['amount'] if finite(before) else None
    heal_rows = [e for e in incoming['events'] if e.get('type') == 'heal' and
                 finite(e.get('timestamp')) and first['timestamp'] - 2000 <= e['timestamp'] <= first['timestamp']]
    last_heal = max(heal_rows, key=lambda e: e['timestamp'], default=None)
    buff_string = fatal.get('buffs')
    buff_ids = ([int(x) for x in buff_string.split('.') if x.isdigit()]
                if isinstance(buff_string, str) else None)
    defensives = [abilities.get(i) or DEFENSIVES[i] for i in (buff_ids or []) if i in DEFENSIVES]
    evidence = [{'reportCode': report, 'fightId': fight_id, 'actorId': actor,
                 'view': view, 'startTime': p.get('startTime'), 'endTime': p.get('endTime'),
                 'complete': p.get('complete'), 'targetFilter': actor}
                for view, p in [('DamageTaken', damage), ('All', incoming)]]
    r = {'actorId': actor, 'name': death['name'], 'death': death, 'abilityId': ability,
         'ability': spell, 'sourceId': source, 'sourceName': source_name,
         'fatalDamage': hit_damage(fatal), 'maxHealth': maximum,
         'healthBeforeBurst': before, 'burstDamage': total, 'burstCount': len(cluster),
         'burstMilliseconds': fatal['timestamp'] - first['timestamp'],
         'recordedDefensives': defensives, 'buffCoverage': buff_ids,
         'healingLast2Seconds': sum(e['amount'] for e in heal_rows) if all(finite(e.get('amount')) for e in heal_rows) else None,
         'lastHeal': last_heal, 'fatalEvent': fatal, 'hitEvents': cluster,
         'complete': True, 'evidence': evidence, 'extraReduction': None,
         'hits': [{'timestamp': e['timestamp'], 'time': (e['timestamp']-start)/1000,
                   'ability': spell, 'amount': hit_damage(e), 'sourceId': source} for e in cluster]}
    # Order matters: a single-hit threshold cannot explain the second of two
    # simultaneous impacts, and a DoT finisher is not a fresh ground impact.
    if fatal.get('tick'):
        r['cause'] = 'dot_finisher'
        conclusion = '持续伤害收尾：'+md(spell, 30)+'最后一跳'+amount_text(r['fatalDamage'])+'致死。'
        direct = [e for e in hits[:-1] if e.get('abilityGameID') == ability and not e.get('tick')]
        if direct:
            e = direct[-1]
            conclusion += clock_text((e['timestamp']-start)/1000)+'先受同技能直击'+amount_text(hit_damage(e))+'，随后持续伤害造成减员。'
    elif len(cluster) > 1:
        r['cause'] = 'repeated_hits'
        conclusion = (str(len(cluster))+'次'+md(spell, 30)+'在'+str(round(r['burstMilliseconds']))+
                      '毫秒内命中，合计'+amount_text(total)+'。')
        if before is not None:
            conclusion += '伤前生命'+amount_text(before)+'。'
            intervening = any(e.get('type') == 'damage' and
                              first['timestamp'] <= e.get('timestamp', -1) <= fatal['timestamp'] and
                              e not in cluster for e in damage['events'])
            if not intervening and all(total-hit_damage(e) < before for e in cluster):
                conclusion += '避开任意一次命中即可保住这次生命。' if ability in GROUND_IMPACTS else '少承受任意一次，按当时血量即可存活。'
        if maximum and total > maximum:
            conclusion += '叠加伤害超过满血'+amount_text(maximum)+'。'
        if ability == PURGE:
            conclusion += '该轮爆炸发生重复承伤，分担后分散必须避免爆炸叠加。'
        elif ability in GROUND_IMPACTS:
            conclusion += '直接改进点是躲避落点，消除重复命中。'
    elif ability == 1 and roles.get(actor) in ('dps', 'healers') and actors.get(source, {}).get('type') == 'NPC':
        r['cause'] = 'non_tank_melee'
        conclusion = '非坦克承接'+md(source_name, 25)+'普攻'+amount_text(r['fatalDamage'])+'。'
        casts = bundle.get('npcCasts', {})
        if casts.get('complete'):
            relevant = sorted((e for e in casts.get('events', []) if e.get('sourceID') == source and
                               e.get('sourceInstance') == fatal.get('sourceInstance') and
                               e.get('type') == 'cast' and e.get('timestamp', timestamp+1) <= fatal['timestamp']),
                              key=lambda e: e['timestamp'])
            melee = next((e for e in reversed(relevant) if e.get('abilityGameID') == 1 and
                          e.get('targetID') == actor and fatal['timestamp']-e['timestamp'] <= 100), None)
            before_melee = [e for e in relevant if melee and e['timestamp'] < melee['timestamp']]
            if before_melee and before_melee[-1].get('abilityGameID') in COILS:
                conclusion += '这是分摊后恢复的第一下普攻，需让坦克承接这个时点。'
                evidence.append({'reportCode': report, 'fightId': fight_id, 'view': casts.get('dataType','All'),
                                 'eventType': 'cast',
                                 'sourceId': source, 'complete': True,
                                 'startTime': casts.get('startTime'), 'endTime': casts.get('endTime')})
        if maximum and r['fatalDamage'] > maximum:
            conclusion += '一击超过满血'+amount_text(maximum)+'，按现有防护补满仍无法存活。'
        elif maximum and before is not None:
            conclusion += '伤前生命'+amount_text(before)+'，满血'+amount_text(maximum)+'；该次伤害超过当时剩余生命。'
        elif actors.get(source, {}).get('gameID') == 259555:
            conclusion += '尾巴的普攻需由坦克承接。'
    elif maximum and r['fatalDamage'] > maximum:
        r['cause'] = 'over_max_health'
        ratio = (r['fatalDamage'] - maximum + 1) / r['fatalDamage']; r['extraReduction'] = ratio
        conclusion = ('单次'+md(spell, 30)+'造成'+amount_text(r['fatalDamage'])+'，超过满血'+
                      amount_text(maximum)+'；需额外降低约'+f'{ceil(ratio*1000)/10:.1f}%'+
                      '该次伤害，或补充至少'+amount_text(ceil((r['fatalDamage']-maximum+1)/1000)*1000
                          if r['fatalDamage']-maximum+1 >= 10000 else ceil(r['fatalDamage']-maximum+1))+'有效吸收。')
        if (last_heal and last_heal.get('hitPoints') == last_heal.get('maxHitPoints') == maximum
                and finite(last_heal.get('amount')) and last_heal['amount'] > 0):
            conclusion = '致死前'+str(round(first['timestamp']-last_heal['timestamp']))+'毫秒已被补满。'+conclusion
    else:
        r['cause'] = 'lethal_hit'
        conclusion = '直接致死：'+md(spell, 30)+'完整一击'+amount_text(r['fatalDamage'])+'。'
        if before is not None:
            conclusion += '命中前剩余生命'+amount_text(before)+'，伤害超过当时生命。'
        if ability in GROUND_IMPACTS:
            conclusion += '此次为落石直击，避开落点即可消除这次致死伤害。'
    if defensives:
        conclusion += '致死时已有'+ '、'.join(defensives[:3])+'。'
    elif buff_ids is not None and buff_ids and all(i == 1235108 for i in buff_ids):
        conclusion += '致死时增益栏仅记录合剂。'
    if ability == PURGE:
        marks = [e for e in incoming['events'] if e.get('type') == 'applydebuff' and
                 e.get('abilityGameID') == PURGE_MARK and
                 4500 <= fatal['timestamp']-e.get('timestamp', 0) <= 6000]
        if marks:
            r['markTime'] = (marks[-1]['timestamp']-start)/1000
            conclusion += clock_text(r['markTime'])+'已获得爆炸前标记。'
    if ability in GROUND_IMPACTS or ability == PURGE:
        r['mechanicSource'] = MECHANIC_SOURCE
    r['conclusion'] = conclusion
    return r


def apply_causes(packet, bundles, master, tables):
    details = ((tables.get('playerDetails') or {}).get('data') or {}).get('playerDetails') or {}
    roles = {r['id']: role for role in ('dps', 'healers', 'tanks') for r in details.get(role, [])
             if isinstance(r, dict) and type(r.get('id')) is int} if packet['coverage'].get('roles') else {}
    indexed = {(b['actorId'], b['deathTimestamp']): b for b in bundles}
    causes = []
    for death in packet['deaths']:
        bundle = indexed.get((death['actorId'], death['timestamp']))
        if bundle:
            result = analyze_death(death, bundle, master, roles, packet['fight']['startTime'],
                                   packet['reportCode'], packet['fightId'])
            if result:
                causes.append(result)
    packet.update(analysisVersion='death-causes-v2', causes=causes,
                  causalCoverage={'selectedDeaths': len(bundles), 'analyzedDeaths': len(causes),
                                  'recordedDeaths': len(packet['deaths']),
                                  'completeDeathList': packet['coverage']['deaths']})
    if len(causes) < len(packet['deaths']):
        packet['gaps'].append('深度归因已完成'+str(len(causes))+'/'+str(len(packet['deaths']))+'次死亡')
    if not causes:
        return packet
    groups = defaultdict(list)
    for row in causes:
        key = (row['sourceId'], row['abilityId'])
        groups[key].append(row)
    # One summary paragraph per failure mechanism, with a representative for
    # each in the detail command. Later failures are not displaced by repeats.
    priority = {'non_tank_melee': 5, 'repeated_hits': 4, 'over_max_health': 3,
                'dot_finisher': 2, 'lethal_hit': 1}
    ordered = sorted(groups.values(), key=lambda g: (-max(priority[r['cause']] for r in g),
                                                    min(r['death']['timestamp'] for r in g)))
    blocks = []
    for group in ordered[:3]:
        title = ('非坦承接普攻' if all(r['cause']=='non_tank_melee' for r in group) else '普通攻击') if group[0]['abilityId'] == 1 else md(group[0]['ability'], 30)
        body = []
        for row in group[:2]:
            body.append(clock_text(row['death']['time'])+' '+md(row['name'], 20)+'：'+row['conclusion'])
        if len(group) > 2:
            body.append('同来源同技能共关联'+str(len(group))+'次已核验死亡。')
        blocks.append('**'+title+'**\n'+'\n'.join(body))
    count_prefix = '本场' if packet['coverage']['deaths'] and packet['coverage']['actors'] else '已读取'
    overview = count_prefix+'死亡'+str(len(packet['deaths']))+'次；已完成'+str(len(causes))+'次致死过程核验。'
    packet['highlights'] = [overview]+blocks
    # The formatter budgets three mechanism blocks plus the short overview.
    packet['review'] = []
    seen = set()
    counts = defaultdict(int)
    for death in packet['deaths']:
        counts[death['actorId']] += 1
    candidates = [max(g, key=lambda r: priority[r['cause']]) for g in ordered]
    candidates += sorted(causes, key=lambda r: -priority[r['cause']])
    for row in candidates:
        if row['actorId'] in seen:
            continue
        seen.add(row['actorId']); row['deathCount'] = counts[row['actorId']]
        packet['review'].append(row)
        if len(packet['review']) == battle_detail_limit(packet['fight']):
            break
    return packet

"""Evidence-only battle writing; model prose never supplies numbers or links."""
import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path

from .battle_commands import battle_detail_limit, clock_text
from .battle_commentary import amount, identity
from .query_commands import markdown_text as md

VERSION = 'battle-narrative-v8'
COMMON_TERMS = {'伤害','治疗','满血','输出','坦克','减伤','普攻','落石','打断','驱散','分摊','队友','血条','队伍','死亡'}
TOKEN = re.compile(r'\[\[([a-zA-Z0-9_]+)\]\]')
RULES = Path(__file__).with_name('battle_narrative.md').read_text()


def _plain(value):
    return md(str(value), 500).replace('**', '').strip('。')


def evidence_pack(packet):
    cards = {}; groups = {'good': [], 'review': []}
    def card(key, text):
        cards[key] = _plain(text)
        return key
    complete=packet.get('coverage',{}).get('deaths') and packet.get('coverage',{}).get('actors')
    deaths=packet.get('deaths',[])
    overview=('本场死亡' if complete else '已读取死亡')+str(len(deaths))+'次，涉及'+str(len({d['actorId'] for d in deaths}))+'人'
    if not complete:overview+='，死亡记录范围未完整'
    card('overview', overview)
    profiles = packet.get('playerAssessments', {})
    counts = Counter(d['actorId'] for d in packet.get('deaths', []))
    for kind in groups:
        for row in packet.get(kind, [])[:battle_detail_limit(packet['fight'])]:
            actor = row['actorId']; prefix = kind + str(actor)
            profile = profiles.get(actor, profiles.get(str(actor), {}))
            ids = []
            def add(suffix, text):
                key = card(prefix + '_' + suffix, text);ids.append(key);return key
            if identity(profile):add('identity', identity(profile))
            if row.get('death'):
                conclusions = [s for s in row.get('conclusion', '').split('。') if s]
                # Prefer the lethal event over a preceding healing observation.
                if conclusions and '已被补满' in conclusions[0]:conclusions = conclusions[1:] + conclusions[:1]
                required = add('cause', clock_text(row['death']['time']) + '，' + (conclusions[0] if conclusions else '记录死亡'))
                for i, text in enumerate(conclusions[1:]):add('process' + str(i), text)
                allowed = row.get('conclusion', '')
            else:
                required = add('performance', amount(row['amount']) + ('有效治疗' if row['metric'] == 'effective_healing' else '伤害') +
                               ('，本场唯一治疗' if row['metric'] == 'effective_healing' and row['roleCount'] == 1 else
                                '，同职责第' + str(row['rank']) + '/' + str(row['roleCount'])))
                allowed = ''
                if row.get('reviewCategory') == 'contribution':
                    required = add('comparison', row['analysis'][1]);allowed = row['analysis'][1]
                else:
                    for i, line in enumerate(row.get('analysis', [])[1:]):
                        if any(term in line for term in ('队伍承伤', '中断施法', '驱散', '离本场同专精')):add('extra' + str(i), line)
                    peers = packet.get('roleContributions', {}).get('healing' if row['metric'] == 'effective_healing' else 'damage', [])
                    if row['rank'] == 1 and len(peers) > 1:
                        gap = row['amount'] - peers[1]['amount']
                        if gap > 0:add('lead', '领先同职责第二名' + amount(gap))
            if packet.get('coverage', {}).get('deaths') and packet.get('coverage', {}).get('actors'):
                add('survival', '本场死亡' + str(counts[actor]) + '次')
            uses = profile.get('consumables') or {}
            if uses.get('stone'):add('stone', '本场使用治疗石' + str(uses['stone']) + '次')
            if uses.get('healthPotion'):add('potion', '本场使用治疗药水' + str(uses['healthPotion']) + '次')
            groups[kind].append({'actorId': actor, 'name': _plain(row['name']), 'required': required,
                                 'facts': ids, 'verifiedConclusion': allowed})
    # Other verified death types remain available to the whole-fight summary,
    # independent of the capped player selection.
    events = [];summary_review = {}
    for i, row in enumerate(sorted(packet.get('causes', []),key=lambda r:r['death']['time'])):
        if row.get('conclusion'):
            card('event' + str(i), clock_text(row['death']['time']) + '，' + next((part for part in row['conclusion'].split('。') if part and '已被补满' not in part), row['conclusion']))
            key='event'+str(i)
            events.append({'fact':key,'actorId':row['actorId'],'verifiedConclusion':row['conclusion']})
            subject=summary_review.setdefault(row['actorId'],{'actorId':row['actorId'],'name':_plain(row['name']),'facts':[],'required':key})
            subject['facts'].append(key)
    for row in groups['review']:
        if row['actorId'] in summary_review:summary_review[row['actorId']]['facts'].extend(row['facts'])
        else:summary_review[row['actorId']]=dict(row)
    return {'cards': cards, **groups, 'summarySubjects':{'good':groups['good'],'review':list(summary_review.values())}, 'outcome': bool(packet['fight']['kill']),
            'mode': 'mythic_plus' if battle_detail_limit(packet['fight']) == 2 else 'raid',
            'gaps': packet.get('gaps', []), 'verifiedEvents':events,
            'summaryRequired':['overview']+(['event0'] if not packet['fight']['kill'] and events else [])}


def _fingerprint(packet, pack):
    data = [VERSION, packet['reportCode'], packet['fightId'], packet['fight'], RULES, pack]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _expand(text, pack, allowed, required=(), *, limit):
    if not isinstance(text, str) or not text or len(text) > 2000:raise ValueError('text')
    refs = TOKEN.findall(text)
    if len(refs) != len(set(refs)) or not set(required) <= set(refs) or not set(refs) <= set(allowed):raise ValueError('facts')
    prose = TOKEN.sub('', text)
    if re.search(r'[零〇一二三四五六七八九十百千万亿两]+(?:万|亿|次|人|秒|毫秒|分钟|名|位|个|层|伤害|治疗量|血)', prose):raise ValueError('quantity')
    if re.search(r'[0-9０-９]|\[|\]|https?://|<|>|P分|应核对|值得检查|补查|治疗失误|没带药|没附魔|循环错误', prose):raise ValueError('unsupported')
    result = TOKEN.sub(lambda m: pack['cards'][m[1]], text).strip()
    if len(result) > limit:raise ValueError('budget')
    return result


def _subject_text(value,row,pack,*,limit):
    if not isinstance(value,dict) or set(value)!={'actorId','text'} or type(value['actorId']) is not int or value['actorId']!=row['actorId']:raise ValueError('actor')
    text=value['text']
    if not isinstance(text,str):raise ValueError('text')
    if any(r['name'] not in COMMON_TERMS and r['name'] in text for k in ('good','review') for r in pack['summarySubjects'][k]):raise ValueError('named actor')
    return _expand(text,pack,row['facts'],[row['required']],limit=limit)


def _summary(value,pack):
    if not isinstance(value,dict) or set(value)!={'opening','good','review','closing'}:raise ValueError('summary schema')
    blocks=[_expand(value['opening'],pack,['overview'],['overview'],limit=150)]
    cited=set(TOKEN.findall(value['opening']))
    for kind,title in (('good','🏆 扛住场面的'),('review','💀 这场的失分点')):
        rows={r['actorId']:r for r in pack['summarySubjects'][kind]}
        entries=value[kind]
        if not isinstance(entries,list) or len(entries)>2 or (rows and not entries):raise ValueError('summary actors')
        seen=set();parts=[]
        for entry in entries:
            if not isinstance(entry,dict) or type(entry.get('actorId')) is not int or entry['actorId'] not in rows or entry['actorId'] in seen:raise ValueError('summary actor')
            row=rows[entry['actorId']];seen.add(row['actorId'])
            text=_subject_text(entry,row,pack,limit=230)
            cited.update(TOKEN.findall(entry['text']))
            parts.append('**'+row['name']+'**：'+text)
        if parts:blocks.append(title+'\n'+'\n'.join(parts))
        elif kind=='review':blocks.append('本场暂无已核验的具体问题。')
    if not set(pack['summaryRequired'])<=cited:raise ValueError('facts')
    blocks.append(_expand(value['closing'],pack,[],limit=120))
    summary='\n\n'.join(blocks)
    if len(summary)>650:raise ValueError('budget')
    return summary


def parse_narrative(raw, pack):
    if not isinstance(raw, str) or len(raw) > 16000:raise ValueError('output')
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) != {'summary', 'good', 'review'}:raise ValueError('schema')
    result = {'summary': _summary(data['summary'],pack)}
    for kind in ('good', 'review'):
        values = data[kind];rows = pack[kind]
        if not isinstance(values, list) or len(values) != len(rows):raise ValueError('actors')
        result[kind] = []
        for value, row in zip(values, rows):
            text = _subject_text(value,row,pack,limit=230)
            result[kind].append({'actorId': row['actorId'], 'text': text})
    return result


class BattleNarrative:
    def __init__(self, adapter):self.adapter = adapter

    @classmethod
    def configured(cls):
        from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
        return cls(NativeCodexChatAdapter(tool_free_instructions=RULES))

    def apply(self, packet, *, timeout_seconds=60):
        if packet.get('status') != 'ready':return packet
        pack = evidence_pack(packet);fingerprint = _fingerprint(packet, pack)
        previous = packet.get('narrative', {})
        if previous.get('version') == VERSION and previous.get('fingerprint') == fingerprint and previous.get('status') == 'ready':return packet
        start = time.monotonic();attempted = 0
        try:
            if timeout_seconds < 5:raise ValueError('deadline')
            terminal = None;attempted = 1
            for event in self.adapter.stream(prompt=json.dumps(pack, ensure_ascii=False), timeout_seconds=min(60, int(timeout_seconds))):
                if event.get('type') == 'completed':terminal = event.get('text')
            narrative = parse_narrative(terminal, pack)
            narrative.update(status='ready', version=VERSION, fingerprint=fingerprint)
            packet['narrative'] = narrative
            # Verify all selected people fit before storing a successful context.
            from .battle_commands import format_battle
            for kind in ('battle_summary', 'battle_good', 'battle_review'):
                format_battle(packet, kind)
        except Exception as error:
            reason=error.args[0] if type(error) is ValueError and error.args and error.args[0] in {'text','facts','quantity','unsupported','budget','output','schema','actors','actor','named actor','summary actor','summary actors','summary schema','message budget','deadline'} else type(error).__name__
            packet['narrative'] = {'status': 'unavailable', 'version': VERSION, 'fingerprint': fingerprint, 'errorCode':reason}
        packet['narrative']['modelCalls'] = attempted
        packet['narrative']['seconds'] = round(time.monotonic() - start, 2)
        return packet


def render_narrative(packet, kind, header, footer):
    narrative = packet['narrative']
    if narrative.get('status') != 'ready':
        code=narrative.get('errorCode')
        reason='生成超时' if code in ('CodexTimeout','deadline') else '结果未通过证据校验' if code in {'text','facts','quantity','unsupported','budget','output','schema','actors','actor','named actor','summary actor','summary actors','summary schema','message budget','JSONDecodeError'} else '生成服务异常'
        return header+'\n\n战斗日志已读取，点评生成失败（'+reason+'）。本次处理已结束，可重新发送本场分析命令。\n\n'+footer
    url = packet['sourceUrl'] + '?fight=' + str(packet['fightId'])
    if kind == 'battle_summary':blocks = [narrative['summary']]
    else:
        field = 'good' if kind == 'battle_good' else 'review'
        blocks = []
        rows = {r['actorId']: r for r in packet[field]}
        for i, value in enumerate(narrative[field], 1):
            row = rows[value['actorId']]
            view = 'deaths' if row.get('death') else 'healing' if row.get('metric') == 'effective_healing' else 'damage-done'
            blocks.append('**' + str(i) + '. ' + md(row['name'], 25) + '**\n' + value['text'] + '\n[日志证据](' + url + '&type=' + view + '&source=' + str(row['actorId']) + ')')
        if not blocks:blocks = ['本场暂无证据充分的' + ('贡献点评对象。' if field == 'good' else '问题点评对象。')]
    if packet.get('gaps'):blocks.append('读取范围未完整：' + '；'.join(packet['gaps'][:3]) + '。')
    text = header + '\n\n' + '\n\n'.join(blocks) + '\n\n' + footer
    if len(text) > 1200:raise ValueError('message budget')
    return text

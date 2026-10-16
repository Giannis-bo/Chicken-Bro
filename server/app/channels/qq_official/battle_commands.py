"""Fixed battle commands and paragraph-budgeted single-message presentation."""
from dataclasses import dataclass
import re
from .battle_links import parse_report_link

BATTLE_COMMANDS = {'/战斗分析':'battle_summary', '/战斗详情-大腿':'battle_good',
                   '/战斗分析-菜鸡':'battle_review'}
BATTLE_ALIASES = {'/战斗详情-毒瘤': '/战斗分析-菜鸡'}
BATTLE_HELP = ('**整场摘要**\n'
               '/战斗分析 WCL报告链接 [场次=5]\n'
               '支持团本和大秘境，链接可用 fight=last。\n\n'
               '**人物详情**\n'
               '/战斗详情-大腿：看贡献亮点\n'
               '/战斗分析-菜鸡：看失误与问题\n'
               '默认查看你上次分析的战斗；每类团本最多3人、大秘境最多2人。\n'
               '两个详情命令后也可加 WCL报告链接 [场次=5]。\n'
               '分析范围为整场，网页视图与角色筛选不缩小范围。')
MESSAGE_LIMIT = 1200


@dataclass(frozen=True)
class BattleRequest:
    kind: str
    url: str = ''
    fight_id: int | str | None = None


def parse_battle(text):
    from .query_commands import QueryInputError
    if not isinstance(text,str) or len(text)>4000:
        raise QueryInputError('战斗指令请控制在4000字符内。')
    parts=text.strip().split(maxsplit=1)
    command=BATTLE_ALIASES.get(parts[0],parts[0]) if parts else ''
    if command not in BATTLE_COMMANDS:
        raise QueryInputError(BATTLE_HELP)
    kind=BATTLE_COMMANDS[command]
    if len(parts)==1 and kind!='battle_summary':return BattleRequest(kind)
    if len(parts)!=2:raise QueryInputError(BATTLE_HELP)
    try:
        value=parts[1];explicit=re.search(r'\s+场次=([1-9][0-9]{0,8})\s*$',value)
        if explicit:value=value[:explicit.start()]
        url,fight=parse_report_link(value)
        if explicit:fight=int(explicit[1])
        return BattleRequest(kind,url,fight)
    except (ValueError,TypeError,AttributeError):
        raise QueryInputError('请填写有效的 WCL 报告链接，场次支持数字、last、all；可补充 场次=5，冲突场次或非WCL地址不接受。') from None


def battle_kind(fight):
    level=fight.get('keystoneLevel')
    return '大秘境+'+str(level) if type(level) is int and level>0 else {1:'随机团队',3:'普通',4:'英雄',5:'史诗'}.get(fight.get('difficulty'),'难度#'+str(fight.get('difficulty')))


def battle_outcome(fight):
    if type(fight.get('keystoneLevel')) is int and fight['keystoneLevel']>0:
        return '已完成' if fight['kill'] else '未完成'
    return '已击杀' if fight['kill'] else '灭团'


def battle_detail_limit(fight):
    return 2 if type(fight.get('keystoneLevel')) is int and fight['keystoneLevel']>0 else 3


def battle_name(fight):
    zone=fight.get('gameZone')
    return zone['name'] if battle_detail_limit(fight)==2 and isinstance(zone,dict) and isinstance(zone.get('name'),str) and zone['name'] else fight['name']


def clock_text(seconds):
    value=max(0,int(seconds))
    return f'{value//60:02d}:{value%60:02d}'


def amount_text(value):
    return f'{value/10000:.1f}万' if value>=10000 else str(round(value))


def format_battle(packet,kind='battle_summary'):
    from .query_commands import markdown_text as md
    from .query_labels import label
    status=packet.get('status')
    if status=='missing_context':return '请先发送 /战斗分析 WCL报告链接，选择一场战斗后再查看详情。'
    if status=='stale_context':return '战斗分析已升级整场复盘，请重新发送 /战斗分析 WCL报告链接，再查看本场深度详情。'
    if status=='unavailable':return 'WCL 日志读取失败或超时，请稍后重试。'
    if status=='blocked':return packet.get('message','当前报告或场次不可分析。')[:MESSAGE_LIMIT]
    if status=='selection':
        header='# 请选择战斗场次'
        blocks=[f'**第{f["id"]}场 · {md(label(battle_name(f)),45)}**｜'+battle_kind(f)+'｜'+battle_outcome(f)+
                '｜'+clock_text((f['endTime']-f['startTime'])/1000) for f in packet['fights'][:5]]
        footer='发送：/战斗分析 '+packet['sourceUrl']+' 场次=编号\n展示最近最多5场；可填写日志中的实际场次编号。'
    else:
        fight=packet['fight'];url=packet['sourceUrl']+'?fight='+str(packet['fightId']);limit=battle_detail_limit(fight)
        titles={'battle_summary':'战斗分析','battle_good':'战斗详情·大腿','battle_review':'战斗分析·菜鸡'}
        header='# '+md(label(battle_name(fight)),45)+' · '+titles[kind]+'\n**'+packet['difficulty']+'｜'+battle_outcome(fight)+'｜'+clock_text(packet['duration'])+'｜'+str(packet['playerCount'])+'人**'
        if packet.get('narrative'):
            from .battle_narrative import render_narrative
            footer=f'[WCL原始日志]({url}) · 第{packet["fightId"]}场'
            if kind=='battle_summary':footer+='\n详情：/战斗详情-大腿 · /战斗分析-菜鸡'
            return render_narrative(packet,kind,header,footer)
        if kind=='battle_summary':
            blocks=list(packet.get('highlights',[]))[:4]
        elif kind=='battle_good':
            blocks=[]
            rows=packet.get('good',[])[:limit]
            full=_full_detail_fits(rows,url,header,review=False)
            for i,row in enumerate(rows,1):
                if row.get('analysis'):
                    blocks.append(_person_block(row,i,url,header,footer_length=110,count=1 if full else len(rows)))
                    continue
                metric='记录伤害' if row['metric']=='damage' else '有效治疗'
                blocks.append(f'**{i}. {md(row["name"],35)}｜{row["roleLabel"]}贡献**\n'+
                    f'{metric}{amount_text(row["amount"])}，占同职责已核验总量{row["share"]:.1f}%；同职责第{row["rank"]}/{row["roleCount"]}。\n'+
                    f'[整场{metric}记录]({url}&source={row["actorId"]})')
            if not blocks:blocks=['暂无足够完整的职责贡献证据。']
        else:
            blocks=[]
            rows=packet.get('review',[])[:limit]
            full=_full_detail_fits(rows,url,header,review=True)
            for i,row in enumerate(rows,1):
                if row.get('analysis'):
                    blocks.append(_person_block(row,i,url,header,footer_length=140,count=1 if full else len(rows),review=True))
                    continue
                death=row['death'];hits=row.get('hits',[])
                if row.get('conclusion'):
                    blocks.append(f'**{i}. {md(row["name"],35)}｜{clock_text(death["time"])}**\n'+
                                  row['conclusion']+'\n'+
                                  f'[致死记录]({url}&type=deaths&source={row["actorId"]})')
                    continue
                detail='；'.join(clock_text(h['time'])+' '+md(h['ability'],30)+' '+amount_text(h['amount']) for h in hits[-3:])
                blocks.append(f'**{i}. {md(row["name"],35)}｜减员复盘**\n'+
                    f'{clock_text(death["time"])}死亡，本场已记录死亡{row["deathCount"]}次。\n'+
                    ('死亡前5秒已读取伤害：'+detail+'。\n' if hits else '')+
                    f'[查看本场日志]({url})')
            if not blocks:blocks=['暂无可展开的死亡前承伤证据。']
            blocks.append('选人依据：已核验的致死过程，优先展示不同类型的代表角色；死亡本身不等于责任。' if packet.get('causes') else
                          '选人依据：已读取的死亡前承伤与减员事件，按首次死亡时间排序。')
        if kind=='battle_review' and packet.get('reportVersion') and packet.get('causes'):
            blocks[-1]='依据：展示已核验致死过程的代表角色，按不同问题选人；死亡次数不作为责任排名。'
        if kind=='battle_review' and packet.get('commentaryVersion'):
            blocks[-1]='点评依据：本场同职责表现与已核验事件；单纯减员不直接定责。'
        gaps=packet.get('gaps',[])
        if gaps:blocks.append('读取范围未完整：'+'；'.join(gaps[:3])+'。')
        footer=f'[WCL原始日志]({url}) · 第{packet["fightId"]}场'
        if kind=='battle_summary':footer+='\n详情：/战斗详情-大腿 · /战斗分析-菜鸡'
    # Reserve footer and only include whole evidence-bearing paragraphs.
    output=header
    for block in blocks:
        if len(output)+len(block)+len(footer)+4<=MESSAGE_LIMIT:output+='\n\n'+block
    return output+'\n\n'+footer


def _person_block(row,index,url,header,*,footer_length,count,review=False):
    from .query_commands import markdown_text as md
    name=md(row['name'],25)
    title=f'**{index}. {name}｜'+((clock_text(row['death']['time']) if row.get('death') else '输出差距') if review else row['roleLabel']+'贡献')+'**'
    view='deaths' if review and row.get('death') else 'damage-done' if row.get('metric')=='damage' else 'healing'
    link_title='致死证据' if review and row.get('death') else '贡献证据'
    link=f'[{link_title}]({url}&type={view}&source={row["actorId"]})'
    reserve=len(header)+footer_length+(60 if review else 0)+8
    budget=(MESSAGE_LIMIT-reserve)//max(1,count)-len(title)-len(link)-6
    parts=[]
    for text in row['analysis']:
        prefix,sep,rest=text.partition('：')
        units=[part+'。' for part in (rest if sep else text).split('。') if part]
        parts.append([prefix+'：' if sep else '',units])
    body=['' for _ in parts]
    if review or row.get('requiredAnalysis'):
        required=row.get('requiredAnalysis',list(range(len(parts))) if review else [])
        for i in required:
            prefix,units=parts[i]
            if units:body[i]=prefix+units.pop(0)
    used=sum(len(v)+1 for v in body if v)
    for i,(prefix,units) in enumerate(parts):
        for part in units:
            candidate=(prefix if not body[i] else '')+part
            if used+len(candidate)+1>budget:break
            body[i]+=candidate;used+=len(candidate)+1
    return title+'\n'+('' if row.get('prose') else '\n').join(v for v in body if v)+'\n'+link


def _full_detail_fits(rows,url,header,*,review):
    if not rows or not all(r.get('analysis') for r in rows):return False
    blocks=[_person_block(r,i,url,header,footer_length=140,count=1,review=review)
            for i,r in enumerate(rows,1)]
    return len(header)+sum(len(b)+2 for b in blocks)+200<=MESSAGE_LIMIT

"""Fixed, read-only QQ character commands and deterministic text rendering."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import math
import re
import shlex

COMMANDS = {'/角色查询': 'character', '/角色团本查询': 'raid', '/角色大米查询': 'mplus'}
DEFAULT_RECENT_LIMIT = 3
REGIONS = {'cn':'国服', 'us':'美服', 'eu':'欧服', 'tw':'台服', 'kr':'韩服'}
REGION_ALIASES = {**{k:k for k in REGIONS}, **{v:k for k,v in REGIONS.items()}}
HELP = ('首版提供魔兽世界角色数据查询，结果在本群公开。\n'
        '/角色查询 角色名 服务器名 [地域=国服]\n'
        '/角色团本查询 角色名 服务器名 [团本=名称] [Boss=名称] [难度=英雄] [地域=国服]\n'
        '/角色大米查询 角色名 服务器名 [副本=名称] [层数=12] [地域=国服]\n'
        '快捷写法：H乌拉特克、H8/H9/H10（H英雄/N普通/M史诗）；大米可写 诸王+12。\n'
        '带空格的名称使用双引号。地域支持国服/美服/欧服/台服/韩服，默认国服。\n'
        '/状态：查看自己的最近查询；/帮助：查看用法。')
from .battle_commands import BATTLE_HELP
HELP += '\n\n战斗日志分析：\n' + BATTLE_HELP
DIFFICULTIES = {'普通':3,'英雄':4,'史诗':5,'随机':1,'随机团队':1,
                'normal':3,'heroic':4,'mythic':5,'lfr':1,'n':3,'h':4,'m':5}


class QueryInputError(ValueError):
    pass


@dataclass(frozen=True)
class QueryRequest:
    kind: str
    name: str
    realm: str
    region: str = 'cn'
    raid: str = ''
    boss: str = ''
    boss_index: int | None = None
    difficulty: int | None = None
    dungeon: str = ''
    level: int | None = None


def shorthand_options(kind, part):
    token=part.casefold()
    if token in REGION_ALIASES: return [('region',part)]
    if kind=='raid':
        if token in DIFFICULTIES: return [('difficulty',part)]
        if part.isdigit(): return [('boss_index',part)]
        match=re.fullmatch(r'(普通|英雄|史诗|[NHMnhm])(.+)',part)
        if match and (len(match[1])>1 or re.match(r'[\u3400-\u9fff0-9]',match[2])):
            key='boss_index' if match[2].isdigit() else 'boss'
            return [('difficulty',match[1]),(key,match[2])]
        return [('boss',part)]
    if kind=='mplus':
        match=re.fullmatch(r'(.*?)\+([0-9]+)',part)
        if match:
            return ([('dungeon',match[1])] if match[1] else [])+[('level',match[2])]
        return [('dungeon',part)]
    raise QueryInputError('可选条件请写成 地域=国服、Boss=名称 或 副本=名称。')


def parse_query(text: str) -> QueryRequest:
    from .battle_commands import BATTLE_COMMANDS, parse_battle
    if isinstance(text,str) and text.split() and text.split()[0] in BATTLE_COMMANDS:
        return parse_battle(text)
    if not isinstance(text, str) or len(text) > 512:
        raise QueryInputError('查询指令过长，请缩短到 512 字以内。')
    try:
        parts = shlex.split(text)
    except ValueError:
        raise QueryInputError('名称引号未闭合；带空格的名称请使用一对双引号。') from None
    if not parts or parts[0] not in COMMANDS:
        raise QueryInputError('请使用已开放的魔兽查询或战斗分析命令。\n' + HELP)
    command = parts[0]
    if len(parts) < 3:
        raise QueryInputError('请补充角色名和服务器名。\n用法：' + command + ' 角色名 服务器名 [地域=国服]')
    name, realm = parts[1:3]
    if any(not re.fullmatch(r"[\w .’'\-]{1,80}", value) for value in (name, realm)):
        raise QueryInputError('角色名或服务器名格式不正确，请填写名称。')
    kind = COMMANDS[command]
    keys = {'地域':'region', '团本':'raid', 'boss':'boss', '难度':'difficulty', '副本':'dungeon', '层数':'level'}
    allowed = {'region'} | ({'raid','boss','boss_index','difficulty'} if kind == 'raid' else {'dungeon','level'} if kind == 'mplus' else set())
    options=[]
    for part in parts[3:]:
        if '=' not in part:
            options.extend(shorthand_options(kind,part))
        else:
            raw_key, value = part.split('=', 1)
            options.append((keys.get(raw_key.casefold()),value))
    opts = {}
    for key,value in options:
        if key not in allowed or key in opts or not value or len(value) > 100:
            raise QueryInputError('条件不适用、重复或为空，请按 /帮助 中的格式填写。')
        if (key=='boss' and 'boss_index' in opts) or (key=='boss_index' and 'boss' in opts):
            raise QueryInputError('Boss 名称和序号请只填写一种，不能同时指定。')
        if key == 'region':
            value = REGION_ALIASES.get(value.casefold())
            if value is None:
                raise QueryInputError('地域支持国服/美服/欧服/台服/韩服。')
        elif key == 'difficulty':
            value = DIFFICULTIES.get(value.casefold())
            if value is None:
                raise QueryInputError('难度支持普通、英雄、史诗、随机团队。')
        elif key == 'level':
            if not re.fullmatch(r'[0-9]{1,2}', value) or not 2 <= int(value) <= 99:
                raise QueryInputError('大米层数请填写 2–99 的整数。')
            value = int(value)
        elif key == 'boss_index':
            if not re.fullmatch(r'[0-9]{1,2}',value) or not 1<=int(value)<=99:
                raise QueryInputError('Boss 序号请填写 1–99，例如 H8；实际范围以所选团本为准。')
            value=int(value)
        elif not re.fullmatch(r"[\w .’'\-,:：()（）?]{1,100}", value):
            raise QueryInputError('Boss、团本或副本名称格式不正确。')
        opts[key] = value
    return QueryRequest(kind, name, realm, **opts)


def score_text(score) -> str:
    if type(score) not in (int,float) or not math.isfinite(score) or not 0 <= score <= 100:
        return '暂无数据'
    color = next(name for lower,name in ((100,'金分'),(99,'粉分'),(95,'橙分'),(75,'紫分'),(50,'蓝分'),(25,'绿分'),(0,'灰分')) if score >= lower)
    displayed = int(Decimal(str(score)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    return f'{displayed}（{color}）'


def clean(value, limit=100):
    return re.sub(r'[\x00-\x1f<>]', ' ', str(value or '')).strip()[:limit]


def time_text(value):
    try:
        if type(value) in (int,float):
            from datetime import timezone
            dt = datetime.fromtimestamp(value / 1000, timezone.utc)
        else:
            dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            return clean(value)
        from zoneinfo import ZoneInfo
        return dt.astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M 北京时间')
    except (ValueError, TypeError, OverflowError, OSError):
        return clean(value) or '来源未提供'


def markdown_text(value, limit=100):
    return re.sub(r'([\\`*_{}\[\]()#+|>~-])', r'\\\1', clean(value, limit))


def markdown_parts(text, limit=1500):
    """Split at whole lines so a record link or emphasis is never sliced."""
    parts=[]; current=''
    for line in text.split('\n'):
        if len(line)>limit:
            # Only unformatted command/error text can reach this branch.
            if current: parts.append(current); current=''
            while len(line)>limit:
                parts.append(line[:limit]); line=line[limit:]
        candidate=current+'\n'+line if current else line
        if len(candidate)>limit:
            parts.append(current); current=line
        else: current=candidate
    if current: parts.append(current)
    if len(parts)>5:
        return ['结果过长，请指定 Boss、副本或层数后重新查询。']
    return parts


def format_result(packet: dict) -> str:
    md=markdown_text
    lines = ['# '+md(packet.get('identity'),250)]
    profile = packet.get('profile')
    if profile is not None:
        fact=lambda key: md(profile.get(key)) or '暂无数据'
        lines += ['', '**角色资料**',
                  '种族：'+fact('race')+' · 职业：'+fact('class'),
                  '专精：'+fact('spec')+' · 英雄天赋：'+fact('hero'),
                  '**装备等级：'+(md(profile.get('itemLevel')) or '暂无数据')+'**',
                  '资料：'+md(profile.get('source'))+' · '+time_text(profile.get('sourceTime'))]
        if profile.get('heroSourceTime'):
            lines.append('英雄天赋来源：WCL · '+time_text(profile['heroSourceTime']))
    for section in packet.get('sections', []):
        rows=section.get('rows',[])[:DEFAULT_RECENT_LIMIT]
        lines += ['', '## '+md(section.get('title'))+(' · 最近 '+str(len(rows))+' 场' if rows else '')]
        if section.get('scope'):
            lines.append(md(section['scope'],250))
        status=section.get('status')
        if status not in ('ok','no_records') or not rows:
            message={'no_records':'暂无公开记录', 'not_found':'未找到角色', 'hidden':'角色公开查询不可用',
                     'unavailable':'查询失败，请稍后重试', 'partial':f'来源返回不完整，以下仅展示已核实记录，无法确认完整的最近 {DEFAULT_RECENT_LIMIT} 场',
                     'identity_mismatch':'来源角色身份不一致，未展示数据'}.get(status,section.get('message') or '暂无数据')
            lines.append(md(message,400))
        if rows:
            lines.append('历史 WCL 排名百分位'+('（同层）' if any(r.get('level') is not None for r in rows) else ''))
            lines.append('')
        for i,row in enumerate(rows,1):
            title=md(row.get('name'))
            if row.get('level') is not None: title+=' +'+str(row['level'])
            elif row.get('difficulty'): title+=' · '+md(row['difficulty'])
            # Literal numbers prevent QQ from continuing a previous category's list.
            lines.append(f'**{i}. {title}**')
            fields=[md(row.get('spec')) or '专精未知',md(row.get('metric')), '**'+score_text(row.get('percentile'))+'**']
            if row.get('level') is not None:
                fields.append({True:'限时',False:'未限时',None:'限时状态未知'}[row.get('timed')])
            lines.append('   '+' · '.join(f for f in fields if f))
            report=row.get('reportUrl')
            link=' · [日志]('+report+')' if isinstance(report,str) and re.fullmatch(r'https://www\.warcraftlogs\.com/reports/[A-Za-z0-9]{16}\?fight=[1-9][0-9]*',report) else ''
            lines.append('   '+time_text(row.get('recordedAt'))+link)
        if section.get('coverage'): lines.append(md(section['coverage'],180))
    links=[]
    for source in packet.get('sources',[]):
        if not isinstance(source,str): continue
        if re.fullmatch(r'https://www\.warcraftlogs\.com/character/[A-Za-z0-9%/_.~-]+',source):
            links.append('[WCL 角色]('+source+')')
        elif re.fullmatch(r'https://raider\.io/characters/[A-Za-z0-9%/_.~-]+',source):
            links.append('[Raider.IO]('+source+')')
    if links: lines += ['', '来源：'+' · '.join(links)]
    lines += ['', '查询时间：'+time_text(packet.get('queriedAt'))]
    return '\n'.join(lines)

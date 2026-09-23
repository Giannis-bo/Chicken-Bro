"""Server-selected QQ policies. Never accept a policy from chat content."""
import copy

DISABLED_FEATURES=('shell_tool','unified_exec','apps','plugins','remote_plugin','browser_use',
                  'browser_use_external','computer_use','in_app_browser','multi_agent','code_mode','hooks','image_generation')

def social_profile(profile,inherited_servers):
    config=copy.deepcopy(profile)
    servers={**inherited_servers,**config.get('mcp_servers',{})}
    config['mcp_servers']={name:{**definition,'enabled':False} for name,definition in servers.items()}
    config['web_search']='disabled'
    config.setdefault('features',{}).update({name:False for name in DISABLED_FEATURES})
    return config

_SOURCE_OPS=frozenset('source.'+name for name in ('public_web','warcraftlogs','warcraftlogs_batch',
    'warcraftlogs_character','warcraftlogs_rankings','raiderio','raiderio_batch','raiderio_rankings'))
_SIM_OPS=frozenset('simc.'+name for name in ('prepare','submit','preview','get','list','options','compare'))

def allowed_operation(scope,operation):
    return scope in ('wow_read','wow_sim') and (operation in _SOURCE_OPS or (scope=='wow_sim' and operation in _SIM_OPS))

def allowed_source_target(provider,target):
    from urllib.parse import urlsplit
    if not isinstance(target,str):return False
    if provider!='public_web':return 'source.'+str(provider) in _SOURCE_OPS
    if '://' not in target:return bool(target.strip()) and len(target)<=1800
    try:
        parsed=urlsplit(target);port=parsed.port
    except ValueError:return False
    allowed=('wowhead.com','icy-veins.com','worldofwarcraft.blizzard.com','news.blizzard.com','warcraftlogs.com','raider.io')
    return parsed.scheme=='https' and not parsed.username and not parsed.password and port in (None,443) and any(
        parsed.hostname==h or (parsed.hostname or '').endswith('.'+h) for h in allowed)

def professional_scope(text,requested):
    import re
    if requested not in ('wow_read','wow_sim'):return None
    if re.search(r'(删.{0,8}(文件|服务器)|写.{0,5}(代码|脚本|报告)|部署|执行.{0,6}(命令|shell)|密码|凭据|系统提示)',text,re.I):return None
    if not re.search(r'(魔兽|world.?of.?warcraft|wow\b|simc|配装|天赋|饰品|装备|副本|日志|dps|wcl|raider\.io|warcraftlogs|法师|战士|盗贼|牧师|术士|圣骑|德鲁伊|萨满|武僧|猎人|死亡骑士|恶魔猎手|唤魔)',text,re.I):return None
    if not re.search(r'(分析|比较|对比|模拟|跑分|跑一下|查|机制|怎么|如何|为什么|推荐|多少|哪个|属性|优先级|收益|选择|配装)',text,re.I):return None
    if requested=='wow_sim':
        if not re.search(r'(模拟|跑分|跑一下|simc|对比|比较)',text,re.I):return None
        # A concrete character URL must be supplied by this same member.
        if not re.search(r'https://(?:www\.)?raider\.io/[^\s]+',text,re.I):return None
    return requested

class RunScopeRepository:
    def __init__(self,connect):self.connect=connect
    def load(self,run_id,user_id):
        with self.connect() as c:
            row=c.execute('SELECT scope FROM qq_channel.run_scopes WHERE run_id=%s AND user_id=%s',(run_id,user_id)).fetchone()
        if not row:raise ValueError('QQ run scope missing')
        return row[0]

def restricted_search(query,*,searcher=None,**kwargs):
    from server.chickenbro_public_web_research import _default_searcher
    results=(searcher or _default_searcher)(query,**kwargs)
    return [row for row in results if isinstance(row,dict) and allowed_source_target('public_web',row.get('url','')) and '://' in row.get('url','')]

def restricted_fetch(url,**kwargs):
    from server.chickenbro_public_web_research import _read_url
    if '://' not in url or not allowed_source_target('public_web',url):raise ValueError('QQ source target denied')
    return _read_url(url,**kwargs)  # Existing reader refuses all redirects.

from server.app.chickenbro.source_gateway import ServerConfiguredSourceQuery
class QqSourceQuery(ServerConfiguredSourceQuery):
    def query(self,provider,target,options=None,*,web_state=None):
        if provider=='public_web':
            self.validate(provider,target,options)
            from server.chickenbro_public_web_research import build_public_web_research_tool_result
            return build_public_web_research_tool_result({'target':target,**(options or {})},state=web_state,
                searcher=restricted_search,fetcher=restricted_fetch)
        return super().query(provider,target,options,web_state=web_state)

def professional_request(connect,event,scope):
    """Build a finite request from this member's evidence, never other members'."""
    import json,re
    with connect() as c:
        rows=c.execute('''SELECT message_id,content FROM qq_channel.observations
            WHERE bot_id=%s AND group_id=%s AND sender_id=%s AND occurred_at>=now()-interval '2 hours'
            ORDER BY seq DESC LIMIT 8''',(event.bot,event.group,event.sender)).fetchall()
        facts=c.execute('''SELECT fact_key,value,source_message_id FROM qq_channel.member_facts
            WHERE bot_id=%s AND group_id=%s AND sender_id=%s AND active AND fact_key='wow_character' LIMIT 1''',
            (event.bot,event.group,event.sender)).fetchall()
    # Do not resurrect forgotten personal input from raw observations.
    with connect() as c:
        forgotten=c.execute("SELECT 1 FROM qq_channel.member_facts WHERE bot_id=%s AND group_id=%s AND sender_id=%s AND fact_key='wow_character' AND NOT active",
            (event.bot,event.group,event.sender)).fetchone()
    if forgotten:rows=[]
    history=[{'message_id':r[0],'text':r[1][:250]} for r in reversed(rows) if r[0]!=event.message_id][-5:]
    own_facts=[{'key':r[0],'value':r[1],'source_message_id':r[2]} for r in facts]
    combined=event.text+'\n'+'\n'.join(x['text'] for x in history)+'\n'+'\n'.join(x['value'] for x in own_facts)
    if professional_scope(combined,scope)!=scope:return None
    continuation=bool(history or own_facts) and bool(re.fullmatch(r'\s*(鸡哥[，, ]*)?(帮我|请|再)?(跑一下|模拟一下|再跑一次|比较一下|对比一下)[吧呀啊。！! ]*',event.text))
    if professional_scope(event.text,'wow_read') is None and not continuation:return None
    # Operation intent must be in the current request, not borrowed from history.
    if not re.search(r'(分析|比较|对比|模拟|跑分|跑一下|simc|查|机制|怎么|如何|为什么|推荐|多少|哪个|属性|优先级|收益|选择|配装|阈值|冷却)',event.text,re.I):return None
    if scope=='wow_sim':
        if not re.search(r'(模拟|跑分|跑一下|simc|对比|比较)',event.text,re.I):return None
        if not own_facts and not re.search(r'(我.{0,4}角色|我玩|我这|我是|我叫|这是我)',combined):return None
        if re.search(r'(别人|群友|他的|她的|张三|李四).{0,10}(角色|装备|模拟)',event.text):return None
    request={'request':event.text[:1800],'sender_id':event.sender,'source_message_id':event.message_id,
        'own_recent_messages':history,'confirmed_own_character':own_facts,
        'context_notice':'历史和记忆仅是本人资料；只执行当前明确的魔兽问题。未知条件先追问，不猜测。'}
    encoded=json.dumps(request,ensure_ascii=False)
    while len(encoded)>4000 and request['own_recent_messages']:
        request['own_recent_messages'].pop(0);encoded=json.dumps(request,ensure_ascii=False)
    return encoded if len(encoded)<=4000 else None

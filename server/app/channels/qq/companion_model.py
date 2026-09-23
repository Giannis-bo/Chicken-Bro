"""A bounded structured social decision, using the existing model runtime."""
from dataclasses import asdict
import json
from pathlib import Path
import re
from server.app.channels.qq.companion_domain import CompanionDecision,ReplyDraft

PERSONA_PATH=Path(__file__).with_name('persona.md')
SCHEMA_RULES='''\n本次只回应输入target_message_id指定的消息，历史其他消息仅作上下文；不替旧问题再发起任务。输出仅一个 JSON 对象，不要 Markdown。字段：quote 为布尔值，默认 false。普通招呼、紧接话题、接梗和表情直接发，不因被 @ 就引用；只有多人交错会产生指代歧义、需要明确回应输入目标哪句话时设 true。引用目标始终由后端绑定当前目标消息。action 为 silent/reply/wow_read/wow_sim；text 为自然群聊文字；sticker_id 为提供的图片中适合当前接梗的表情ID或 null；可查看images按image_index与stickers对应，普通照片/聊天截图/私人信息不可用来斗图。没有合适表情且meme_search_available=true时，可填写meme_query（只写一个2至8字的核心情绪或动作词，如“吃瓜”“笑死”“无语”“熊猫头”；不拼接多种动作，不附加“表情包”字样，不得URL）寻找网上表情；最多一轮，找到后再决定是否发送，不向群里预告搜索过程；target_message_id 为输入目标消息ID的字符串或 null；memories 为至多3条明确本人事实的候选列表。每条记忆字段 sender,source_message_id,key,value,evidence,intent(assert/correct/forget)，key只能是preferred_name、wow_character或preference_加英文短名。只记录本人明确陈述的称呼、偏好、角色；玩笑/转述不记。没有则空列表。must_reply=true 时不能 silent；普通回应不能用排队提示充数。专业建议可不带text。silent 不带文字或表情。'''

def parse_decision(raw):
    if not isinstance(raw,str) or len(raw)>16000:raise ValueError('invalid decision')
    data=json.loads(raw)
    if not isinstance(data,dict) or set(data)-{'action','text','sticker_id','target_message_id','memories','meme_query','quote'}:raise ValueError('unknown decision fields')
    quote=data.get('quote',False)
    if type(quote) is not bool:raise ValueError('invalid quote choice')
    action=data.get('action');text=data.get('text','');sticker=data.get('sticker_id');target=data.get('target_message_id')
    if action not in {'silent','reply','wow_read','wow_sim'}:raise ValueError('invalid action')
    if not isinstance(text,str) or len(text)>4000:raise ValueError('invalid text')
    if sticker is not None and (not isinstance(sticker,str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,39}',sticker)):raise ValueError('invalid sticker')
    if target is not None and (not isinstance(target,str) or not re.fullmatch(r'-?[0-9]{1,20}',target)):raise ValueError('invalid target')
    query=data.get('meme_query')
    if query is not None:
        from server.app.channels.qq.group_memes import meme_search_query
        meme_search_query(query)
    if action=='silent' and (text or sticker or query):raise ValueError('silent with output')
    if action=='reply' and not (text.strip() or sticker or query):raise ValueError('empty reply')
    memories=data.get('memories',[])
    if not isinstance(memories,list) or len(memories)>3 or any(not isinstance(m,dict) for m in memories):raise ValueError('invalid memories')
    return CompanionDecision(action,ReplyDraft(text.strip(),sticker,quote) if text.strip() or sticker else None,target,tuple(memories),query)

class CompanionModel:
    def __init__(self,adapter):self.adapter=adapter
    def decide(self,context,*,must_reply,facts=(),stickers=(),target=None,recent_replies=(),images=(),meme_search_available=False):
        rows=[];remaining=18000
        for e in reversed(context):
            row=asdict(e);row['text']=row['text'][:min(2000,remaining)];remaining-=len(row['text'])
            rows.append(row)
            if remaining<=0:break
        prompt=json.dumps({'messages':list(reversed(rows)),'must_reply':must_reply,
            'meme_search_available':meme_search_available,'recent_bot_replies':list(recent_replies)[-12:],'target_message_id':target,'member_facts':list(facts)[:30],'stickers':list(stickers)},ensure_ascii=False)
        parts=[];terminal=None
        for event in self.adapter.stream(prompt=prompt,timeout_seconds=45,**({'images':tuple(images)} if images else {})):
            if event.get('type')=='delta':parts.append(event.get('text',''))
            if event.get('type')=='completed':terminal=event.get('text')
        decision=parse_decision(terminal or ''.join(parts))
        if decision.target_message_id not in (None,target):raise ValueError('unexpected decision target')
        return decision

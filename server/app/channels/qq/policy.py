"""Pure, fail-closed event policy. Never fetches media or interprets CQ strings."""
from dataclasses import dataclass
import json
from pathlib import Path
import re
import time

# Names extracted from the deployed QQ NT system-face resource, not message fields.
FACE_NAMES=json.loads(Path(__file__).with_name('face_names.json').read_text())

def social_segment_text(segment):
    if segment.get('type')=='text':return segment['data']['text']
    if segment.get('type')=='face':
        name=FACE_NAMES.get(str(segment['data'].get('id','')))
        return '[QQ表情：'+name+']' if name else '[QQ表情]'
    return ''

@dataclass(frozen=True)
class ChannelConfig:
    bot_qq: str
    allowed_groups: tuple[str, ...]
    enabled: bool = False
    known_bot_qqs: tuple[str, ...] = ()

    def __post_init__(self):
        if not re.fullmatch(r'[1-9][0-9]{4,15}', self.bot_qq):
            raise ValueError('invalid bot identity')
        if not self.allowed_groups or any(not re.fullmatch(r'[1-9][0-9]{4,15}', g) for g in self.allowed_groups):
            raise ValueError('explicit group allowlist required')
        if type(self.enabled) is not bool:
            raise ValueError('enabled must be boolean')
        if any(not isinstance(q,str) or not re.fullmatch(r'[1-9][0-9]{4,15}',q) for q in self.known_bot_qqs):
            raise ValueError('invalid known bot identity')


@dataclass(frozen=True)
class Trigger:
    bot: str
    group: str
    sender: str
    message_id: str
    text: str
    error: str = ''


def parse_event(event, config, *, now=None):
    if not config.enabled or not isinstance(event, dict):
        return None
    if (event.get('post_type') != 'message' or event.get('message_type') != 'group'
            or str(event.get('self_id')) != config.bot_qq
            or str(event.get('group_id')) not in config.allowed_groups):
        return None
    sender = str(event.get('user_id', ''))
    message_id = str(event.get('message_id', ''))
    timestamp = event.get('time')
    if (not re.fullmatch(r'[1-9][0-9]{4,15}', sender) or sender == config.bot_qq
            or not re.fullmatch(r'-?[0-9]{1,20}', message_id)
            or type(timestamp) not in (int, float)
            or not -10 <= (time.time() if now is None else now) - timestamp <= 120):
        return None
    segments = event.get('message')
    if not isinstance(segments, list) or len(segments) > 100:
        return None
    if any(not isinstance(s, dict) or not isinstance(s.get('data'), dict) for s in segments):
        return None
    if not any(s.get('type') == 'at' and str(s['data'].get('qq')) == config.bot_qq for s in segments):
        return None
    text = ''.join(s['data'].get('text', '') for s in segments
                   if s.get('type') == 'text' and isinstance(s['data'].get('text'), str)).strip()
    error = ''
    if any(s.get('type') not in {'text', 'at', 'reply'} for s in segments):
        error = '当前群聊先支持文字提问，请把图片或文件中的问题转成文字。'
    elif len(text) > 4000:
        error = '问题过长，请缩短到 4000 字以内。'
    elif not text:
        text = '/帮助'
    return Trigger(config.bot_qq, str(event['group_id']), sender, message_id, text[:4000], error)


def split_reply(text):
    text = str(text).strip() or '本次没有生成有效回答，请稍后重新提问。'
    if len(text) > 7500:
        text = text[:7440] + '\n回答过长，已截取前文；请缩小问题范围继续提问。'
    parts = []
    while text:
        end = min(1500, len(text))
        if end < len(text):
            paragraph = text.rfind('\n', 750, end)
            if paragraph > 0 and len(parts) < 4 and len(text) - paragraph <= (4-len(parts))*1500:
                end = paragraph+1
        parts.append(text[:end])
        text = text[end:]
    return parts


def reply_segments(message_id, text, *, quote=True):
    return ([{'type':'reply','data':{'id':str(message_id)}}] if quote else []) + ([{'type':'text','data':{'text':text}}] if text else [])


def parse_group_event(event, config, *, now=None):
    """Observe valid new group traffic; a mention is a property, not admission."""
    import math
    from server.app.channels.qq.companion_domain import GroupEvent
    if not config.enabled or not isinstance(event, dict):return None
    if (event.get('post_type')!='message' or event.get('message_type')!='group'
        or str(event.get('self_id'))!=config.bot_qq
        or str(event.get('group_id')) not in config.allowed_groups):return None
    sender=str(event.get('user_id',''));mid=str(event.get('message_id',''));ts=event.get('time')
    if (not re.fullmatch(r'[1-9][0-9]{4,15}',sender) or sender==config.bot_qq or sender in config.known_bot_qqs
        or not re.fullmatch(r'-?[0-9]{1,20}',mid) or type(ts) not in (int,float)
        or not math.isfinite(ts) or not -10 <= (time.time() if now is None else now)-ts <=120):return None
    segments=event.get('message')
    if not isinstance(segments,list) or len(segments)>100:return None
    if any(not isinstance(s,dict) or not isinstance(s.get('data'),dict) for s in segments):return None
    if any(s.get('type')=='text' and not isinstance(s['data'].get('text'),str) for s in segments):return None
    text=''.join(social_segment_text(s) for s in segments).strip()[:4000]
    mentioned=any(s.get('type')=='at' and str(s['data'].get('qq'))==config.bot_qq for s in segments)
    reply=next((str(s['data'].get('id')) for s in segments if s.get('type')=='reply'),None)
    if reply is not None and not re.fullmatch(r'-?[0-9]{1,20}',reply):reply=None
    info=event.get('sender') if isinstance(event.get('sender'),dict) else {}
    name=info.get('card') or info.get('nickname') or sender
    name=name[:80] if isinstance(name,str) else sender
    return GroupEvent(config.bot_qq,str(event['group_id']),sender,mid,float(ts),text,name,mentioned,reply,
        any(s.get('type') not in {'text','at','reply','face'} for s in segments))

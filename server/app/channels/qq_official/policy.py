"""Pure policy for authenticated official QQ group events."""
from dataclasses import dataclass
from datetime import datetime
import re
import time

@dataclass(frozen=True)
class Trigger:
    bot: str
    group: str
    sender: str
    message_id: str
    text: str
    error: str = ''


ID = re.compile(r'[A-Za-z0-9_-]{1,256}\Z')
MESSAGE_ID = re.compile(r'[!-~]{1,1024}\Z')


def valid_id(value):
    return isinstance(value, str) and bool(ID.fullmatch(value))


def valid_message_id(value):
    # Opaque IDs enter parameterized SQL and JSON bodies, never paths or URLs.
    return isinstance(value, str) and bool(MESSAGE_ID.fullmatch(value))


def require_test_group(raw):
    if (raw.get('testGroupNumber') != '1127827451'
        or not isinstance(raw.get('allowedGroupOpenIds'),list)
        or len(raw['allowedGroupOpenIds']) != 1):
        raise ValueError('official query release requires the single approved test group')


@dataclass(frozen=True)
class OfficialConfig:
    app_id: str
    allowed_groups: tuple[str, ...]

    def __post_init__(self):
        if not re.fullmatch(r'[1-9][0-9]{4,19}', self.app_id):
            raise ValueError('invalid official AppID')
        if not self.allowed_groups or any(not valid_id(g) for g in self.allowed_groups):
            raise ValueError('explicit official group allowlist required')

    @property
    def bot(self):
        return 'official:' + self.app_id


def parse_event(packet, config, *, now=None):
    if not isinstance(packet, dict) or packet.get('op') != 0 or packet.get('t') != 'GROUP_AT_MESSAGE_CREATE':
        return None
    d = packet.get('d')
    if not isinstance(d, dict) or d.get('group_openid') not in config.allowed_groups:
        return None
    author = d.get('author')
    sender = author.get('member_openid') if isinstance(author, dict) else None
    if not valid_id(sender) or not valid_message_id(d.get('id')):
        return None
    content = d.get('content')
    if not isinstance(content, str) or not isinstance(d.get('timestamp'), str):
        return None
    try:
        timestamp = datetime.fromisoformat(d['timestamp'].replace('Z', '+00:00'))
        if timestamp.tzinfo is None:
            return None
        age = (time.time() if now is None else now) - timestamp.timestamp()
    except (ValueError, OverflowError):
        return None
    if not -10 <= age <= 240:
        return None
    # The trusted event type determines @ admission; text cannot impersonate it.
    text = re.sub(r'^\s*<@!?[A-Za-z0-9_-]+>\s*', '', content).strip()
    if text in ('帮助', '状态'):
        text = '/' + text
    error = ''
    if d.get('attachments'):
        error = '角色查询支持文字命令，请使用 /角色查询、/角色团本查询 或 /角色大米查询。'
    elif len(text) > 4000:
        error = '问题过长，请缩短到 4000 字以内。'
    return Trigger(config.bot, d['group_openid'], sender, d['id'], text[:4000] or '/帮助', error)


def occurred_at(packet):
    return datetime.fromisoformat(packet['d']['timestamp'].replace('Z', '+00:00'))

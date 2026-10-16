"""Per-message capability guidance with the existing tool-free model adapter."""
from dataclasses import dataclass
import json
from pathlib import Path
import re
import time

from .battle_commands import BATTLE_COMMANDS
from .query_commands import COMMANDS

VERSION = 'bounded-model-guidance-v2'
RULES = Path(__file__).with_name('guidance.md').read_text()
ALLOWED_COMMANDS = set(COMMANDS) | set(BATTLE_COMMANDS) | {'/帮助', '/状态'}
FALLBACK = '鸡哥刚卡了一下，具体用法先看 /帮助。'


@dataclass(frozen=True)
class GuidanceRequest:
    message: str
    kind: str = 'guidance'


def fallback_packet(reason='unavailable'):
    return {'schema': 'qq-guidance-v1', 'version': VERSION, 'status': 'fallback',
            'text': FALLBACK, 'errorCode': reason, 'modelCalls': 0}


def parse_reply(raw):
    if not isinstance(raw, str) or len(raw) > 2000:
        raise ValueError('output')
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) != {'reply'} or not isinstance(data['reply'], str):
        raise ValueError('schema')
    text = data['reply'].strip()
    if not 1 <= len(text) <= 80 or text.count('/帮助') > 1 or text.count('\n') > 2:
        raise ValueError('budget or help')
    commands = set(re.findall(r'/[A-Za-z0-9_\-\u3400-\u9fff]+', text))
    if not commands <= ALLOWED_COMMANDS or re.search(r'https?://|www\.|[<>]|```', text, re.I):
        raise ValueError('unsupported')
    return text


class DefaultGuidance:
    def __init__(self, adapter):
        self.adapter = adapter

    @classmethod
    def configured(cls):
        from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
        return cls(NativeCodexChatAdapter(tool_free_instructions=RULES))

    def reply(self, message):
        started = time.monotonic()
        calls = 0
        try:
            if not isinstance(message, str) or not 1 <= len(message) <= 512:
                raise ValueError('input')
            terminal = None
            calls = 1
            for event in self.adapter.stream(prompt=json.dumps({'message': message}, ensure_ascii=False), timeout_seconds=20):
                if event.get('type') == 'completed':
                    terminal = event.get('text')
            packet = {'schema': 'qq-guidance-v1', 'version': VERSION, 'status': 'ready', 'text': parse_reply(terminal)}
        except Exception as error:
            packet = fallback_packet(type(error).__name__)
        packet.update(modelCalls=calls, seconds=round(time.monotonic() - started, 2))
        return packet

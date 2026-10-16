"""Single official QQ sender restricted to explicitly approved test groups."""
import json
import logging
import os
from pathlib import Path
import signal
import time

import psycopg

from server.app.platform.config import AppSettings
from server.app.platform.postgres import PostgresConnectionFactory
from .client import OfficialClient, OfficialError
from .gateway import GatewaySession, Reconnect, connect_gateway, poll_gateway
from .policy import OfficialConfig, occurred_at, parse_event, require_test_group
from .repository import deliver_one
from .query_repository import QueryRepository
from .query_service import QueryService
from .character_source import CharacterQuerySource

LOG = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    # Third-party HTTP/WS debug logs must never reveal authentication payloads.
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('websockets').setLevel(logging.WARNING)
    credentials_dir = Path(os.environ.get('CREDENTIALS_DIRECTORY', '/etc/chickenbro-qq-official'))
    credentials = json.loads((credentials_dir / 'credentials.json').read_text())
    raw = json.loads((credentials_dir / 'channel.json').read_text())
    if raw.get('enabled') is not True:
        raise SystemExit('official QQ channel is disabled')
    require_test_group(raw)
    config = OfficialConfig(credentials['appId'], tuple(raw['allowedGroupOpenIds']))
    settings = AppSettings.from_env(os.environ)
    if os.environ.get('WOW_WORKER_V2_SCOPE') != 'qq_official':
        raise SystemExit('official QQ requires its isolated runtime scope')
    connect = PostgresConnectionFactory(settings).connection
    repository = QueryRepository(connect, config.bot, config.allowed_groups, proactive_enabled=False)
    from .battle_narrative import BattleNarrative
    from .guidance import DefaultGuidance
    service = QueryService(repository, CharacterQuerySource(), battle_writer=BattleNarrative.configured(),
                           guidance_writer=DefaultGuidance.configured())
    client = OfficialClient(config.app_id, credentials['appSecret'], markdown=True)
    state = GatewaySession()
    stop = False
    def request_stop(*_):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    health_path = Path('/var/lib/chickenbro/qq-official/channel-health.json')
    def health(online):
        temp = health_path.with_suffix('.tmp')
        temp.write_text(json.dumps({'observedAt': time.time(), 'gatewayReady': online,
                                   'allowedGroupCount': len(config.allowed_groups),
                                   'queryOnly': True,
                                   'defaultReplyPresentation': 'bounded-model-guidance-v2',
                                   'guidanceModelEnabled': True,
                                   'guidanceToolAccess': False,
                                   'queryPresentation': 'markdown_recent3_v1',
                                   'battlePresentation': 'single_summary_evidence_narrative_zhcn_v8',
                                   'runtimeRevision': os.environ.get('WOW_CODEX_RUNTIME_REVISION', 'unknown')}))
        temp.replace(health_path)
    def persist(packet):
        d = packet.get('d')
        if packet.get('t') == 'GROUP_DEL_ROBOT' and isinstance(d, dict):
            if d.get('group_openid') in config.allowed_groups:
                repository.revoke_group(d['group_openid'])
            return
        event = parse_event(packet, config)
        if event:
            accepted = repository.accept_official(event, occurred_at(packet))
            if accepted: LOG.info('official_qq_message_admitted')
        elif packet.get('t') == 'GROUP_AT_MESSAGE_CREATE' and isinstance(d, dict):
            from .policy import valid_id, valid_message_id
            author = d.get('author')
            LOG.warning('official_qq_message_rejected shape=%s', json.dumps({
                'groupAllowed': d.get('group_openid') in config.allowed_groups,
                'messageIdValid': valid_message_id(d.get('id')),
                'messageIdLength': len(d['id']) if isinstance(d.get('id'), str) else None,
                'messageIdPunctuation': sorted(set(c for c in d.get('id', '') if not c.isalnum())) if isinstance(d.get('id'), str) else None,
                'authorKeys': sorted(author) if isinstance(author, dict) else None,
                'memberIdValid': valid_id(author.get('member_openid')) if isinstance(author, dict) else False,
                'timestamp': d.get('timestamp') if isinstance(d.get('timestamp'), str) else None,
                'contentType': type(d.get('content')).__name__,
            }))
    with psycopg.connect(settings.database_url, autocommit=True) as lock:
        if not lock.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,719620260923))',
                            ('qq-channel-' + config.bot,)).fetchone()[0]:
            raise SystemExit('official QQ already has an active sender')
        repository.recover_sends()
        delay = 1
        try:
            while not stop:
                health(False)
                try:
                    with connect_gateway(client.gateway_url()) as socket:
                        next_send = next_health = 0
                        while not stop:
                            lock.execute('SELECT 1')
                            poll_gateway(socket, state, persist, client.access_token())
                            service.advance()
                            now = time.monotonic()
                            if now >= next_health:
                                health(state.ready); next_health = now + 10
                            if state.ready and now >= next_send:
                                try:
                                    if deliver_one(repository, client): LOG.info('official_qq_reply_sent')
                                except OfficialError as error:
                                    LOG.warning('official_qq_reply_failed code=%s', error.code)
                                next_send = now + 3.2
                            if state.ready: delay = 1
                except Exception as error:
                    # Provider bodies and websocket exception strings may contain secrets.
                    LOG.warning('official_qq_disconnected kind=%s', type(error).__name__)
                    health(False)
                    until = time.monotonic() + delay
                    while not stop and time.monotonic() < until: time.sleep(0.2)
                    delay = min(60, delay * 2)
        finally:
            service.close()
            client.close()
            health(False)


if __name__ == '__main__': main()

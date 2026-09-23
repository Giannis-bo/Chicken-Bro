"""Single active channel daemon. Business storage is independent of the socket."""
import json
import logging
import os
from pathlib import Path
import re
import time

from server.app.channels.qq.onebot import OneBot,OneBotError,OneBotRejected
from server.app.channels.qq.policy import ChannelConfig,parse_event,reply_segments
from server.app.channels.qq.repository import QqRepository
from server.app.channels.qq.service import QqService
from server.app.chickenbro.application import ChatApplication
from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
from server.app.chickenbro.repository import PostgresChatRepository
from server.app.platform.config import AppSettings
from server.app.platform.postgres import PostgresConnectionFactory

LOG=logging.getLogger(__name__)


def companion_options(raw,env):
    mode=raw.get('mode','legacy');proactive=raw.get('proactiveEnabled',False)
    if mode not in ('legacy','companion') or type(proactive) is not bool:raise ValueError('invalid companion options')
    enabled=mode=='companion'
    if enabled!=(env.get('WOW_QQ_COMPANION_ENABLED')=='1'):raise ValueError('channel and worker mode mismatch')
    return enabled,proactive if enabled else False


def deliver_one(repository,client,allowed_groups,catalog=None):
    for item in repository.pending_outbox():
        if not repository.begin_send(item['id']):continue
        if item['group_id'] not in allowed_groups:
            repository.finish_send(item['id'])
            continue
        try:
            from server.app.channels.qq.companion_domain import ReplyDraft
            from server.app.channels.qq.stickers import render_reply
            draft=ReplyDraft(item['text'],item.get('sticker_id'),item.get('quote_reply',True))
            try:
                segments=render_reply(item['message_id'],draft,catalog.for_group(item['group_id']) if hasattr(catalog,'for_group') else catalog) if catalog else reply_segments(item['message_id'],draft.text,quote=draft.quote)
            except (ValueError,OSError):
                segments=reply_segments(item['message_id'],draft.text or '这表情没发出来，鸡哥先用文字顶一下。',quote=draft.quote)
            try:
                data=client.call('send_group_msg',{'group_id':int(item['group_id']),'message':segments})
            except OneBotRejected:
                if not any(s['type']=='image' for s in segments):raise
                # 1400 is NapCat's pre-handler schema rejection; 1200 may follow partial side effects.
                data=client.call('send_group_msg',{'group_id':int(item['group_id']),
                    'message':reply_segments(item['message_id'],draft.text or '表情发不出来，鸡哥只好用文字了。',quote=draft.quote)})
            receipt=data.get('message_id') if isinstance(data,dict) else None
            if type(receipt) not in (int,str) or not re.fullmatch(r'-?[0-9]{1,20}',str(receipt)) or int(receipt)==0:
                raise OneBotError('Missing send receipt')
        except Exception:
            repository.finish_send(item['id'])
            raise
        repository.finish_send(item['id'],receipt)
        return True
    return False


def verify_peer(client,config):
    login=client.call('get_login_info')
    if not isinstance(login,dict) or str(login.get('user_id'))!=config.bot_qq:
        raise OneBotError('Unexpected QQ identity')
    status=client.call('get_status')
    if not isinstance(status,dict) or status.get('online') is not True:
        raise OneBotError('QQ is offline')
    groups=client.call('get_group_list')
    if not isinstance(groups,list) or not set(config.allowed_groups).issubset({str(g.get('group_id')) for g in groups if isinstance(g,dict)}):
        raise OneBotError('Configured QQ group not joined')


def main():
    import psycopg
    logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
    credentials_dir=Path(os.environ.get('CREDENTIALS_DIRECTORY','/etc/chickenbro-qq-channel'))
    raw=json.loads((credentials_dir/'channel.json').read_text())
    config=ChannelConfig(str(raw['botQQ']),tuple(map(str,raw['allowedGroups'])),raw['enabled'],
        known_bot_qqs=tuple(map(str,raw.get('knownBotQQs',()))))
    if not config.enabled:
        raise SystemExit('QQ channel is disabled')
    token=json.loads((credentials_dir/'credentials.json').read_text())['onebotToken']
    settings=AppSettings.from_env(os.environ)
    connect=PostgresConnectionFactory(settings).connection
    enabled,proactive=companion_options(raw,os.environ)
    repository=QqRepository(connect,config.bot_qq,config.allowed_groups,proactive_enabled=proactive)
    # This adapter supplies the same revision metadata; durable admission never
    # invokes the model here. The ordinary Worker owns model/tool composition.
    chat=ChatApplication(repository=PostgresChatRepository(connect,durable=True,actor_kind='qq_group'),
                         codex=NativeCodexChatAdapter(),images_enabled=False)
    service=QqService(repository,chat,companion=enabled)
    companion=None;catalog=None
    if enabled:
        from server.app.channels.qq.companion_model import CompanionModel,PERSONA_PATH,SCHEMA_RULES
        from server.app.channels.qq.companion_repository import CompanionRepository
        from server.app.channels.qq.companion_service import CompanionService
        from server.app.channels.qq.observation_repository import ObservationRepository
        from server.app.channels.qq.memory import MemoryRepository
        from server.app.channels.qq.group_memes import GroupMemeCatalog
        responses=CompanionRepository(connect,config.bot_qq,config.allowed_groups)
        catalog=GroupMemeCatalog(connect,config.bot_qq,config.allowed_groups,onebot_factory=lambda:OneBot(token))
        social=NativeCodexChatAdapter(qq_scope='social',qq_rules=PERSONA_PATH.read_text()+SCHEMA_RULES)
        companion=CompanionService(responses,ObservationRepository(connect),CompanionModel(social),
            proactive=proactive,professional=lambda job,decision:responses.prepare_professional(job,decision.action),
            memory=MemoryRepository(connect),stickers=catalog)
    health_path=Path(os.environ.get('QQ_CHANNEL_HEALTH_PATH','/var/lib/chickenbro/qq-channel/health.json'))
    def health(online):
        health_path.parent.mkdir(parents=True,exist_ok=True)
        temp=health_path.with_suffix('.tmp')
        temp.write_text(json.dumps({'observedAt':time.time(),'qqOnline':online,'businessEnabled':True,
            'runtimeRevision':os.environ.get('WOW_CODEX_RUNTIME_REVISION','unknown')}))
        temp.replace(health_path)
    # A session advisory lock prevents concurrent daemons from claiming sends
    # or starting admissions, including deployment overlap. Loss exits the process.
    with psycopg.connect(settings.database_url,autocommit=True) as lock:
        if not lock.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,719620260923))',('qq-channel-'+config.bot_qq,)).fetchone()[0]:
            raise SystemExit('QQ channel already has an active daemon')
        repository.recover_sends()
        delay=1
        while True:
            lock.execute('SELECT 1')
            health(False)
            try:
                with OneBot(token) as client:
                    verify_peer(client,config)
                    def persist_event(raw_event):
                        if companion:
                            from server.app.channels.qq.policy import parse_group_event
                            event=parse_group_event(raw_event,config)
                            if event:
                                catalog.observe(event,raw_event)
                                companion.observe(event)
                        else:
                            event=parse_event(raw_event,config)
                            if event:repository.accept(event)
                    client.on_event=persist_event
                    while client.events:persist_event(client.events.popleft())
                    delay=1;next_check=time.monotonic()+30;next_send=0
                    health(True)
                    LOG.info('qq_channel_connected')
                    while True:
                        lock.execute('SELECT 1')
                        client.poll(.5)
                        service.advance()
                        if companion:companion.tick()
                        now=time.monotonic()
                        if now>=next_check:
                            verify_peer(client,config);health(True);next_check=now+30
                        if now>=next_send:
                            deliver_one(repository,client,config.allowed_groups,catalog);next_send=now+2
            except (OneBotError,OSError,ValueError,TimeoutError) as error:
                LOG.warning('qq_channel_disconnected reason=%s',str(error) if isinstance(error,OneBotError) else type(error).__name__)
                health(False)
                time.sleep(delay);delay=min(60,delay*2)


if __name__=='__main__':main()

"""Admit through the existing Chat application; model work stays in its Worker."""
import logging
from uuid import UUID
from server.app.identity.domain import Principal
from server.app.chickenbro.application import ChatApplicationError

LOG=logging.getLogger(__name__)


class QqService:
    def __init__(self,repository,chat,*,companion=False):
        self.repository,self.chat=repository,chat
        self.companion=companion

    def advance(self):
        self.repository.reconcile(companion=self.companion)
        item=self.repository.next_pending()
        if not item:return
        principal=Principal(item['user_id'],'qq_group')
        chat=self.chat
        if self.companion:
            from server.app.chickenbro.application import ChatApplication
            from server.app.chickenbro.repository import PostgresChatRepository
            with self.repository.connect() as c:
                scope=c.execute("SELECT requested_scope FROM qq_channel.companion_responses WHERE inbox_id=%s AND state='professional'",(item['id'],)).fetchone()
            if not scope or scope[0] not in ('wow_read','wow_sim'):
                self.repository.fail(item['id']);return
            chat=ChatApplication(repository=PostgresChatRepository(self.repository.connect,durable=True,actor_kind='qq_group',
                qq_scope=scope[0],qq_inbox_id=item['id']),codex=self.chat._codex)
        try:
            conversation=chat.create_conversation(principal,title='QQ群里的鸡哥',game=item['game'],
                idempotency_key=f"qq-conv-{item['game']}-{item['generation']}")
            existing=self.repository.admitted_run(item,conversation.id)
            if existing:
                self.repository.bind_run(item,conversation.id,existing)
                return
            key='qq-inbox-'+str(item['id'])
            stream=chat.start_delivery(principal,conversation.id,item['content'],
                client_message_id=key,idempotency_key=key)
            try:first=next(stream)
            finally:stream.close()
            self.repository.bind_run(item,conversation.id,UUID(str(first.run_id)))
        except ChatApplicationError as error:
            # Queue or an existing admission can become available on the next tick.
            if error.code in {'CHAT_ACCOUNT_BUSY','CODEX_UNAVAILABLE'}:return
            LOG.warning('qq_admission_failed inbox_id=%s code=%s',item['id'],error.code)
            self.repository.fail(item['id'])

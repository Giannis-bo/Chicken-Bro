import importlib
import os
from pathlib import Path
import unittest
from uuid import uuid4
from server.app.chickenbro.application import ChatApplication, ChatApplicationError
from server.app.chickenbro.repository import PostgresChatRepository
from server.app.chickenbro.worker import ChatWorker
from server.app.identity.domain import Principal
from server.app.channels.qq.policy import Trigger
from tests.app_chickenbro_application_test import FakeCodex


@unittest.skipUnless(os.environ.get('WOW_PG_TEST_DSN_V2'),'isolated PostgreSQL required')
class QqChannelPostgresTest(unittest.TestCase):
    def setUp(self):
        import psycopg
        self.connect=lambda:psycopg.connect(os.environ['WOW_PG_TEST_DSN_V2'])
        with psycopg.connect(os.environ['WOW_PG_TEST_DSN_V2'],autocommit=True) as conn:
            importlib.import_module('server.migrations.product.apply').apply_product_migrations(conn,Path(__file__).resolve().parents[1]/'server/migrations/product')
        from server.app.channels.qq.repository import QqRepository
        from server.app.channels.qq.service import QqService
        self.bot=str(100000+uuid4().int%1000000000)
        self.repo=QqRepository(self.connect,self.bot,('22222','44444'))
        self.codex=FakeCodex([{'type':'delta','text':'答案 [CQ:at,qq=all]'}, {'type':'completed'}])
        self.chat=ChatApplication(repository=PostgresChatRepository(self.connect,durable=True,actor_kind='qq_group'),codex=self.codex)
        self.service=QqService(self.repo,self.chat)

    def event(self,sender='11111',group='22222',text='问题',mid=None):
        return Trigger(self.bot,group,sender,str(mid or uuid4().int%1000000000),text)

    def tearDown(self):
        with self.connect() as conn:
            conn.execute("UPDATE chat.executions SET stage='failed',lease_token=NULL,lease_expires_at=NULL WHERE user_id IN (SELECT user_id FROM qq_channel.principals WHERE bot_id=%s) AND stage IN ('pending','running')",(self.bot,))
            conn.execute("UPDATE chat.agent_runs SET status='failed',finished_at=now() WHERE user_id IN (SELECT user_id FROM qq_channel.principals WHERE bot_id=%s) AND status='streaming'",(self.bot,))

    def test_at_admission_worker_final_reply_and_restart_dedup(self):
        event=self.event(mid=42)
        self.assertTrue(self.repo.accept(event))
        self.assertFalse(self.repo.accept(event))
        self.service.advance()
        with self.connect() as c:
            run=c.execute('SELECT run_id,user_id FROM qq_channel.inbox WHERE bot_id=%s AND message_id=%s',(self.bot,'42')).fetchone()
            kind=c.execute('SELECT actor_kind FROM chat.executions WHERE run_id=%s',(run[0],)).fetchone()[0]
        self.assertEqual(kind,'qq_group')
        self.assertEqual(self.codex.calls,0)
        self.assertTrue(ChatWorker(self.connect,self.codex).run_once())
        self.service.advance()
        replies=self.repo.pending_outbox()
        self.assertIn('答案 [CQ:at,qq=all]',[r['text'] for r in replies])
        self.assertFalse(self.repo.accept(event))
        self.service.advance()
        self.assertEqual(self.codex.calls,1)
        with self.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM chat.agent_runs WHERE user_id=%s',(run[1],)).fetchone()[0],1)
            self.assertEqual(c.execute('SELECT count(*) FROM identity.auth_sessions WHERE user_id=%s',(run[1],)).fetchone()[0],0)

    def test_sender_group_game_and_new_conversation_are_isolated(self):
        for event in [self.event(),self.event(sender='33333'),self.event(group='44444')]:self.repo.accept(event)
        self.service.advance();ChatWorker(self.connect,self.codex).run_once();self.service.advance()
        with self.connect() as c:
            rows=c.execute('SELECT DISTINCT user_id FROM qq_channel.inbox WHERE bot_id=%s',(self.bot,)).fetchall()
        self.assertEqual(len(rows),3)
        # Finish queued questions to test game switching on the first sender.
        for _ in range(3):self.service.advance();ChatWorker(self.connect,self.codex).run_once()
        self.service.advance()
        self.repo.accept(self.event(text='/游戏 poe2'));self.repo.accept(self.event(text='POE2 问题'));self.service.advance()
        with self.connect() as c:
            row=c.execute("SELECT i.user_id,i.conversation_id,c.game FROM qq_channel.inbox i JOIN chat.conversations c ON c.id=i.conversation_id WHERE i.bot_id=%s AND i.content='POE2 问题'",(self.bot,)).fetchone()
        self.assertEqual(row[2],'poe2')
        with self.assertRaises(ChatApplicationError):self.chat.load_conversation(Principal(next(r[0] for r in rows if r[0]!=row[0]),'qq_group'),row[1])
        ChatWorker(self.connect,self.codex).run_once();self.service.advance()
        self.repo.accept(self.event(text='/新会话'));self.repo.accept(self.event(text='新问题'));self.service.advance()
        with self.connect() as c:
            new=c.execute("SELECT conversation_id FROM qq_channel.inbox WHERE bot_id=%s AND content='新问题'",(self.bot,)).fetchone()[0]
        self.assertNotEqual(new,row[1])

    def test_uncertain_send_is_not_replayed_and_status_can_retrieve_answer(self):
        self.repo.accept(self.event());self.service.advance();ChatWorker(self.connect,self.codex).run_once();self.service.advance()
        pending=self.repo.pending_outbox();target=next(r for r in pending if r['kind']=='answer')
        self.assertTrue(self.repo.begin_send(target['id']))
        self.repo.recover_sends()
        self.assertNotIn(target['id'],[r['id'] for r in self.repo.pending_outbox()])
        self.repo.accept(self.event(text='/状态'))
        self.assertTrue(any('答案' in r['text'] for r in self.repo.pending_outbox() if r['kind']=='command'))

    def test_queue_is_bounded_per_sender_and_only_one_run_is_admitted(self):
        self.repo.accept(self.event());self.service.advance()
        self.repo.accept(self.event(text='等候问题'));self.repo.accept(self.event(text='超限问题'))
        self.service.advance()
        with self.connect() as c:
            count=c.execute("SELECT count(*) FROM qq_channel.inbox WHERE bot_id=%s AND state='running'",(self.bot,)).fetchone()[0]
            queued=c.execute("SELECT count(*) FROM qq_channel.inbox WHERE bot_id=%s AND state='pending'",(self.bot,)).fetchone()[0]
        self.assertEqual((count,queued),(1,1))
        self.assertTrue(any('稍后' in r['text'] for r in self.repo.pending_outbox()))

if __name__=='__main__':unittest.main()

@unittest.skipUnless(os.environ.get('WOW_PG_TEST_DSN_V2'),'isolated PostgreSQL required')
class QqBridgePostgresTest(unittest.TestCase):
    setUp=QqChannelPostgresTest.setUp
    tearDown=QqChannelPostgresTest.tearDown
    event=QqChannelPostgresTest.event
    def test_bridge_only_sends_persisted_reply_and_records_real_receipt(self):
        from server.app.channels.qq.runtime import deliver_one
        self.repo.accept(self.event())
        class Transport:
            def call(inner,action,params):
                self.assertEqual(action,'send_group_msg')
                self.assertEqual(params['group_id'],22222)
                self.assertEqual(params['message'][1]['type'],'text')
                return {'message_id':9001}
        self.assertTrue(deliver_one(self.repo,Transport(),('22222',)))
        self.assertFalse(deliver_one(self.repo,Transport(),('22222',)))
        with self.connect() as c:
            self.assertEqual(c.execute("SELECT o.state,o.receipt FROM qq_channel.outbox o JOIN qq_channel.inbox i ON i.id=o.inbox_id WHERE i.bot_id=%s",(self.bot,)).fetchone(),('sent','9001'))

    def test_invalid_receipt_and_removed_group_never_get_retried(self):
        from server.app.channels.qq.runtime import deliver_one
        self.repo.accept(self.event())
        class Transport:
            def call(inner,action,params):return {'message_id':None}
        with self.assertRaises(RuntimeError):deliver_one(self.repo,Transport(),('22222',))
        self.assertFalse(deliver_one(self.repo,Transport(),('22222',)))
        self.repo.accept(self.event(sender='44444',group='33333'))
        self.assertFalse(deliver_one(self.repo,Transport(),('22222',)))

    def test_worker_preserves_qq_actor_and_group_product_context(self):
        import json
        seen=[]
        class Capture(FakeCodex):
            def stream_for_chat(inner,**kwargs):
                seen.append(kwargs)
                yield from inner.stream(prompt=kwargs['prompt'],timeout_seconds=kwargs['timeout_seconds'])
        codex=Capture([{'type':'delta','text':'群里回复'}, {'type':'completed'}])
        self.repo.accept(self.event());self.service.advance()
        ChatWorker(self.connect,codex).run_once()
        self.assertEqual(seen[0]['principal'].session_kind,'qq_group')
        capabilities=json.loads(seen[0]['prompt'])['productCapabilities']
        self.assertEqual(capabilities['channel'],'qq_group')
        self.assertFalse(capabilities['imageInputEnabled'])
        self.assertIn('群内',capabilities['instruction'])

    def test_crash_after_chat_admission_before_inbox_binding_reuses_same_run(self):
        from unittest.mock import patch
        self.repo.accept(self.event())
        with patch.object(self.repo,'bind_run',side_effect=RuntimeError('simulated crash')):
            with self.assertRaises(RuntimeError):self.service.advance()
        self.service.advance()
        ChatWorker(self.connect,self.codex).run_once();self.service.advance()
        with self.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM chat.agent_runs WHERE user_id IN (SELECT user_id FROM qq_channel.principals WHERE bot_id=%s)',(self.bot,)).fetchone()[0],1)
        self.assertEqual(self.codex.calls,1)
        self.assertTrue(any(r['kind']=='answer' and '答案' in r['text'] for r in self.repo.pending_outbox()))

    def test_revoked_group_and_disabled_principal_cannot_dispatch_queued_work(self):
        self.repo.accept(self.event())
        self.repo.allowed_groups=('44444',)
        self.service.advance()
        with self.connect() as c:
            self.assertEqual(c.execute("SELECT state,run_id FROM qq_channel.inbox WHERE bot_id=%s",(self.bot,)).fetchone(),('failed',None))
        self.repo.allowed_groups=('22222','44444')
        self.repo.accept(self.event(sender='66666'))
        with self.connect() as c:
            c.execute("UPDATE qq_channel.principals SET enabled=false WHERE bot_id=%s AND sender_id='66666'",(self.bot,))
        self.service.advance()
        with self.connect() as c:
            self.assertEqual(c.execute("SELECT state,run_id FROM qq_channel.inbox WHERE bot_id=%s AND sender_id='66666'",(self.bot,)).fetchone(),('failed',None))

    def test_slow_run_emits_at_most_one_progress_notice(self):
        self.repo.accept(self.event());self.service.advance()
        with self.connect() as c:
            c.execute("UPDATE chat.agent_runs SET started_at=now()-interval '35 seconds',public_progress='正在核对资料' WHERE user_id IN (SELECT user_id FROM qq_channel.principals WHERE bot_id=%s)",(self.bot,))
        self.repo.reconcile();self.repo.reconcile()
        progress=[r for r in self.repo.pending_outbox() if r['kind']=='progress']
        self.assertEqual(len(progress),1)
        self.assertIn('核对资料',progress[0]['text'])

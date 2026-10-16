"""Official transport contracts using fixed queries, never general Chat."""
import importlib
import os
from pathlib import Path
import unittest
from uuid import uuid4
from server.app.channels.qq_official.policy import Trigger

@unittest.skipUnless(os.environ.get('QQ_OFFICIAL_TEST_DSN'), 'isolated official QQ test database required')
class OfficialPostgresTest(unittest.TestCase):
    def setUp(self):
        import psycopg
        self.connect = lambda: psycopg.connect(os.environ['QQ_OFFICIAL_TEST_DSN'])
        self.bot = 'official:test_' + uuid4().hex
        with self.connect() as c:
            self.assertIn(c.execute('SELECT current_database()').fetchone()[0],
                          ('chickenbro_qq_official_tests','chickenbro_qq_official_integration_tests_20261016'))
            importlib.import_module('server.migrations.product.apply').apply_product_migrations(c, Path('server/migrations/product'))
            for p in sorted(Path('server/qq-official').glob('*.sql')):
                c.execute(p.read_text())
        from server.app.channels.qq_official.query_repository import QueryRepository
        self.repo = QueryRepository(self.connect, self.bot, ('group_A','group_B'))

    def event(self, mid=None, group='group_A', sender='member_A', text='/角色查询 Alice 服'):
        return Trigger(self.bot, group, sender, mid or 'msg_' + uuid4().hex, text)

    def tearDown(self):
        with self.connect() as c:
            c.execute("UPDATE qq_channel.inbox SET state='failed' WHERE bot_id=%s AND state IN ('pending','running')", (self.bot,))
            c.execute("UPDATE qq_channel.outbox SET state='failed' WHERE inbox_id IN (SELECT id FROM qq_channel.inbox WHERE bot_id=%s) AND state IN ('pending','sending')", (self.bot,))

    def admit(self, event, *, age=0):
        from datetime import datetime, timezone, timedelta
        return self.repo.accept_official(event, datetime.now(timezone.utc)-timedelta(seconds=age))

    def test_fixed_queries_are_idempotent_and_sender_group_scoped_without_chat_runs(self):
        event=self.event();self.assertTrue(self.admit(event));self.assertFalse(self.admit(event))
        self.admit(self.event(sender='member_B'));self.admit(self.event(group='group_B'))
        with self.connect() as c:
            owners=c.execute('SELECT user_id FROM qq_channel.principals WHERE bot_id=%s',(self.bot,)).fetchall()
            self.assertEqual(len(owners),3)
            self.assertEqual(c.execute('SELECT count(*) FROM chat.agent_runs WHERE user_id=ANY(%s)',([x[0] for x in owners],)).fetchone()[0],0)
        results=[]
        while job:=self.repo.claim_query():
            self.assertTrue(self.repo.finish_query(job,'本人结果'));results.append(job['user_id'])
        self.assertEqual(len(set(results)),3)

    def test_shared_five_reply_budget_and_expired_answer_is_retrievable(self):
        event=self.event(text='/帮助');self.admit(event)
        with self.connect() as c:
            inbox=c.execute('SELECT id FROM qq_channel.inbox WHERE bot_id=%s',(self.bot,)).fetchone()[0]
            self.repo._reply(c.cursor(),inbox,'extra','x'*7500)
        sequences=[]
        while item:=self.repo.claim_send():
            sequences.append(item['sequence']);self.repo.finish_send(item['id'],'receipt_'+str(item['sequence']))
        self.assertEqual(sequences,[1,2,3,4,5]);self.assertIsNone(self.repo.claim_send())
        old=self.event();self.admit(old,age=400)
        self.assertTrue(self.repo.finish_query(self.repo.claim_query(),'本人旧结果'))
        self.assertIsNone(self.repo.claim_send())
        self.admit(self.event(text='/状态'));self.assertEqual(self.repo.claim_send()['text'],'本人旧结果')

    def test_uncertain_sends_are_not_replayed_after_restart(self):
        self.admit(self.event(text='/帮助'));item=self.repo.claim_send();self.assertIsNotNone(item)
        self.repo.recover_sends();self.assertIsNone(self.repo.claim_send())
        with self.connect() as c:self.assertEqual(c.execute('SELECT state FROM qq_channel.outbox WHERE id=%s',(item['id'],)).fetchone()[0],'uncertain')

    def test_guidance_has_no_canned_queue_reply_and_no_general_chat(self):
        self.admit(self.event(text='你好'));self.assertEqual(self.repo.pending_outbox(),[])
        job=self.repo.claim_query();self.assertEqual(job['request']['kind'],'guidance')
        self.assertTrue(self.repo.finish_query(job,'鸡哥在这儿。'))
        item=self.repo.claim_send();self.assertEqual((item['text'],item['sequence']),('鸡哥在这儿。',1))

    def test_revoked_group_cannot_start_queries_or_send_results(self):
        self.admit(self.event());self.repo.revoke_group('group_A')
        self.assertIsNone(self.repo.claim_query());self.assertIsNone(self.repo.claim_send())

    def test_revocation_also_rejects_new_members_and_survives_repository_restart(self):
        self.admit(self.event());self.repo.revoke_group('group_A')
        from server.app.channels.qq_official.query_repository import QueryRepository
        restarted=QueryRepository(self.connect,self.bot,('group_A',))
        self.assertFalse(restarted.accept_official(self.event(sender='new_member'),__import__('datetime').datetime.now(__import__('datetime').timezone.utc)))
        self.assertIsNone(restarted.claim_query());self.assertIsNone(restarted.claim_send())

    def test_runtime_role_can_complete_queries_and_persist_revocation_without_ddl(self):
        import psycopg
        self.repo.connect = lambda: psycopg.connect(os.environ['QQ_OFFICIAL_TEST_DSN'], options='-c role=wow_app')
        event=self.event();self.assertTrue(self.admit(event))
        job=self.repo.claim_query();self.assertIsNotNone(job)
        self.assertTrue(self.repo.finish_query(job,'最小权限结果'))
        item=self.repo.claim_send();self.assertEqual(item['text'],'最小权限结果')
        self.repo.finish_send(item['id'],'test_receipt')
        self.repo.revoke_group('group_A');self.assertFalse(self.admit(self.event(sender='new_member')))
        with self.repo.connect() as c:
            self.assertEqual(c.execute('SELECT current_user').fetchone()[0],'wow_app')
            self.assertFalse(c.execute("SELECT has_schema_privilege(current_user,'qq_channel','CREATE')").fetchone()[0])

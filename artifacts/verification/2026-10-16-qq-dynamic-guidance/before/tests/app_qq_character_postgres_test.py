import importlib
import os
from pathlib import Path
import threading
import time
import unittest
from tests import app_qq_official_postgres_test as transport


@unittest.skipUnless(os.environ.get('QQ_OFFICIAL_TEST_DSN'), 'isolated official QQ test database required')
class CharacterQueryPostgresTest(unittest.TestCase):
    event = transport.OfficialPostgresTest.event
    admit = transport.OfficialPostgresTest.admit
    tearDown = transport.OfficialPostgresTest.tearDown

    def setUp(self):
        transport.OfficialPostgresTest.setUp(self)
        try:
            module = importlib.import_module('server.app.channels.qq_official.query_repository')
        except ImportError:
            self.fail('durable fixed query route not implemented')
        with self.connect() as c:
            c.execute(Path('server/qq-official/002_queries.sql').read_text())
            c.execute(Path('server/qq-official/003_battles.sql').read_text())
        self.repo = module.QueryRepository(self.connect, self.bot, ('group_A',))

    def test_only_three_commands_are_admitted_and_never_create_ai_run(self):
        for text in ('你好','/游戏 poe2','/新会话','帮我跑 SimC','/角色查询'):
            self.assertTrue(self.admit(self.event(text=text)))
        self.assertIsNone(self.repo.claim_query())
        e = self.event(text='/角色查询 Giannis 白银之手')
        self.assertTrue(self.admit(e)); self.assertFalse(self.admit(e))
        job = self.repo.claim_query()
        self.assertEqual((job['request']['name'],job['request']['region']),('Giannis','cn'))
        self.assertTrue(self.repo.finish_query(job,'客观结果'))
        with self.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM chat.agent_runs WHERE user_id IN (SELECT user_id FROM qq_channel.principals WHERE bot_id=%s)',(self.bot,)).fetchone()[0],0)
            self.assertEqual(c.execute('SELECT count(*) FROM qq_channel.official_queries q JOIN qq_channel.inbox i ON i.id=q.inbox_id WHERE i.bot_id=%s',(self.bot,)).fetchone()[0],1)

    def test_second_user_results_and_status_are_owner_scoped(self):
        self.admit(self.event(text='/角色查询 Alice 服'))
        self.admit(self.event(text='/角色查询 Bob 服',sender='member_B'))
        a = self.repo.claim_query(); b = self.repo.claim_query()
        self.assertNotEqual(a['user_id'],b['user_id'])
        self.repo.finish_query(b,'Bob 结果'); self.repo.finish_query(a,'Alice 结果')
        e = self.event(text='/状态')
        self.admit(e)
        with self.connect() as c:
            reply=c.execute('SELECT o.content FROM qq_channel.outbox o JOIN qq_channel.inbox i ON i.id=o.inbox_id WHERE i.bot_id=%s AND i.message_id=%s',(self.bot,e.message_id)).fetchone()[0]
        self.assertEqual(reply,'Alice 结果')

    def test_expired_lease_is_reclaimed_and_old_worker_cannot_finish(self):
        self.admit(self.event(text='/角色查询 玩家 服'))
        old = self.repo.claim_query()
        with self.connect() as c:
            c.execute("UPDATE qq_channel.official_queries SET lease_expires_at=now()-interval '1 second' WHERE inbox_id=%s",(old['id'],))
        new = self.repo.claim_query()
        self.assertNotEqual(new['lease_token'],old['lease_token'])
        self.assertFalse(self.repo.finish_query(old,'旧结果'))
        self.assertTrue(self.repo.finish_query(new,'新结果'))
        with self.connect() as c:
            self.assertEqual(c.execute('SELECT result_text FROM qq_channel.official_queries WHERE inbox_id=%s',(old['id'],)).fetchone()[0],'新结果')

    def test_revoked_or_disallowed_group_cannot_be_claimed_or_sent(self):
        self.assertFalse(self.admit(self.event(group='group_B',text='/角色查询 玩家 服')))
        self.admit(self.event(text='/角色查询 玩家 服'))
        self.repo.revoke_group('group_A')
        self.assertIsNone(self.repo.claim_query())
        self.assertIsNone(self.repo.claim_send())

    def test_expired_reply_can_be_retrieved_and_one_user_cannot_flood_queue(self):
        self.admit(self.event(text='/角色查询 玩家 服'),age=400)
        self.admit(self.event(text='/角色查询 第二个 服'))
        job = self.repo.claim_query()
        self.assertEqual(job['request']['name'],'玩家')
        self.repo.finish_query(job,'结果已保存')
        self.assertIsNone(self.repo.claim_query())
        while item := self.repo.claim_send(): self.repo.finish_send(item['id'],'test_receipt')
        e=self.event(text='/状态');self.admit(e)
        self.assertEqual(self.repo.claim_send()['text'],'结果已保存')

    def test_two_source_reads_do_not_block_gateway_thread(self):
        from server.app.channels.qq_official.query_service import QueryService
        entered = threading.Event(); release = threading.Event()
        class Source:
            def query(inner, request):
                entered.set(); release.wait(3)
                return {'identity':request.name,'queriedAt':'now','sections':[]}
        self.admit(self.event(text='/角色查询 Alice 服'))
        self.admit(self.event(text='/角色查询 Bob 服',sender='member_B'))
        service=QueryService(self.repo,Source())
        started=time.monotonic();service.advance()
        self.assertLess(time.monotonic()-started,1)
        self.assertTrue(entered.wait(1))
        with self.connect() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM qq_channel.inbox WHERE bot_id=%s AND state='running'",(self.bot,)).fetchone()[0],2)
        release.set()
        try:
            deadline=time.monotonic()+3
            while service.active and time.monotonic()<deadline:
                service.advance();time.sleep(.01)
            self.assertFalse(service.active)
        finally:service.close()


if __name__ == '__main__': unittest.main()

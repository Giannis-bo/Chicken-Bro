"""Durable battle context isolation in the dedicated cloud PostgreSQL test DB."""
import os
from pathlib import Path
import time
import unittest

from tests.app_qq_character_postgres_test import CharacterQueryPostgresTest
from tests.app_qq_battle_analysis_test import URL


@unittest.skipUnless(os.environ.get('QQ_OFFICIAL_TEST_DSN'),'isolated official QQ test database required')
class BattlePostgresTest(unittest.TestCase):
    event=CharacterQueryPostgresTest.event
    admit=CharacterQueryPostgresTest.admit
    tearDown=CharacterQueryPostgresTest.tearDown

    def setUp(self):
        CharacterQueryPostgresTest.setUp(self)
        with self.connect() as c:c.execute(Path('server/qq-official/003_battles.sql').read_text())

    def finish_battle(self,name='Alice',sender='member_A',fight=5):
        self.admit(self.event(text='/战斗分析 '+URL+' 场次='+str(fight),sender=sender))
        job=self.repo.claim_query()
        packet={'schema':'qq-battle-v1','status':'ready','reportCode':'ABCDEFGHIJKLMNOP',
                'fightId':fight,'sourceUrl':URL,'name':name}
        self.assertTrue(self.repo.finish_query(job,name+'摘要',packet=packet))
        return job

    def test_detail_context_is_owned_and_character_query_does_not_replace_it(self):
        self.finish_battle()
        self.admit(self.event(text='/角色查询 Giannis 白银之手'))
        self.repo.finish_query(self.repo.claim_query(),'角色结果')
        self.admit(self.event(text='/战斗详情-大腿'))
        detail=self.repo.claim_query()
        self.assertEqual(detail['battle_context']['name'],'Alice')
        self.repo.finish_query(detail,'Alice详情')
        self.admit(self.event(text='/战斗详情-毒瘤',sender='member_B'))
        other=self.repo.claim_query()
        self.assertIsNone(other['battle_context'])
        with self.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM chat.agent_runs WHERE user_id IN (SELECT user_id FROM qq_channel.principals WHERE bot_id=%s)',(self.bot,)).fetchone()[0],0)

    def test_failed_and_selection_results_do_not_replace_successful_battle(self):
        self.finish_battle()
        for packet,failed in [({'status':'unavailable'},True),({'status':'selection'},False)]:
            self.admit(self.event(text='/战斗分析 '+URL+' 场次=6'))
            self.repo.finish_query(self.repo.claim_query(),'未完成',failed=failed,packet=packet)
        self.admit(self.event(text='/战斗详情-毒瘤'))
        self.assertEqual(self.repo.claim_query()['battle_context']['fightId'],5)

    def test_recovered_detail_narrative_is_reused_only_for_current_owned_summary(self):
        self.finish_battle()
        self.admit(self.event(text='/战斗详情-大腿'))
        detail=self.repo.claim_query();p=detail['battle_context']
        p['narrative']={'status':'ready','version':'test','summary':'已恢复'}
        self.repo.finish_query(detail,'详情恢复',packet=p)
        self.admit(self.event(text='/战斗详情-毒瘤'))
        next_job=self.repo.claim_query()
        self.assertEqual(next_job['battle_context']['narrative']['summary'],'已恢复')
        self.repo.finish_query(next_job,'复用',packet=next_job['battle_context'])
        self.finish_battle(fight=6)
        self.admit(self.event(text='/战斗详情-大腿'))
        fresh=self.repo.claim_query()['battle_context']
        self.assertEqual(fresh['fightId'],6)
        self.assertNotIn('narrative',fresh)

    def test_late_lease_cannot_overwrite_battle_context(self):
        self.admit(self.event(text='/战斗分析 '+URL+' 场次=5'))
        old=self.repo.claim_query()
        with self.connect() as c:c.execute("UPDATE qq_channel.official_queries SET lease_expires_at=now()-interval '1 second' WHERE inbox_id=%s",(old['id'],))
        current=self.repo.claim_query()
        packet={'schema':'qq-battle-v1','status':'ready','reportCode':'ABCDEFGHIJKLMNOP','fightId':5}
        self.assertFalse(self.repo.finish_query(old,'过期摘要',packet=packet))
        self.assertTrue(self.repo.finish_query(current,'有效摘要',packet=packet))
        self.admit(self.event(text='/战斗详情-大腿'))
        self.assertEqual(self.repo.claim_query()['battle_context']['fightId'],5)

    def test_single_battle_reply_and_status_recover_the_same_summary(self):
        job=self.finish_battle()
        with self.connect() as c:
            rows=c.execute('SELECT content FROM qq_channel.outbox WHERE inbox_id=%s',(job['id'],)).fetchall()
        self.assertEqual(rows,[('Alice摘要',)])
        e=self.event(text='/状态');self.admit(e)
        with self.connect() as c:
            content=c.execute('SELECT o.content FROM qq_channel.outbox o JOIN qq_channel.inbox i ON i.id=o.inbox_id WHERE i.bot_id=%s AND i.message_id=%s',(self.bot,e.message_id)).fetchone()[0]
        self.assertEqual(content,'Alice摘要')

    def test_service_dispatches_battle_and_persists_packet_without_ai(self):
        from server.app.channels.qq_official.query_service import QueryService
        from tests.app_qq_battle_analysis_test import BattleAnalysisTest
        from server.app.channels.qq_official.battle_commands import format_battle
        fixture=BattleAnalysisTest();fixture.setUp();packet=fixture.read()
        class Battle:
            def query(inner,request,*,context=None):return packet
        class Character:
            def query(inner,request):raise AssertionError('wrong source')
        self.admit(self.event(text='/战斗分析 '+URL+' 场次=5'))
        service=QueryService(self.repo,Character(),battle_source=Battle())
        try:
            service.advance()
            deadline=time.monotonic()+3
            while service.active and time.monotonic()<deadline:
                service.advance();time.sleep(.01)
            self.assertFalse(service.active)
        finally:service.close()
        self.admit(self.event(text='/战斗详情-大腿'))
        detail=self.repo.claim_query()
        self.assertEqual(detail['battle_context']['fightId'],5)
        self.assertLessEqual(len(format_battle(detail['battle_context'],'battle_good')),1200)


if __name__=='__main__':unittest.main()

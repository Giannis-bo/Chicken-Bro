"""Short default introduction and explicit full help; run only on cloud."""
import os
import unittest

from server.app.channels.qq_official.query_commands import HELP, GuidanceInput, QueryInputError, parse_query
from tests import app_qq_character_postgres_test as fixtures


class DefaultReplyTest(unittest.TestCase):
    def test_unrecognized_input_signals_guidance_with_short_fallback(self):
        for text in ('你都能干啥？', '你能做什么', '你好', '/未知命令'):
            with self.subTest(text=text), self.assertRaises(GuidanceInput) as raised:
                parse_query(text)
            reply = str(raised.exception)
            self.assertLessEqual(len(reply), 150)
            for word in ('炸鸡', '角色', '团本', '大米', 'WCL', '大腿', '毒瘤', '/帮助'):
                self.assertIn(word, reply)
            self.assertNotIn('[', reply)
            self.assertNotIn('请使用已开放', reply)

    def test_valid_commands_and_missing_parameters_keep_existing_routes(self):
        self.assertEqual(parse_query('/角色查询 Giannis 白银之手').kind, 'character')
        with self.assertRaisesRegex(QueryInputError, '请补充角色名和服务器名'):
            parse_query('/角色查询')
        self.assertIn('/角色查询 角色名 服务器名', HELP)
        self.assertIn('/战斗分析 WCL报告链接', HELP)


@unittest.skipUnless(os.environ.get('QQ_OFFICIAL_TEST_DSN'), 'isolated official QQ test database required')
class DefaultReplyPostgresTest(unittest.TestCase):
    setUp = fixtures.CharacterQueryPostgresTest.setUp
    tearDown = fixtures.CharacterQueryPostgresTest.tearDown
    event = fixtures.CharacterQueryPostgresTest.event
    admit = fixtures.CharacterQueryPostgresTest.admit

    def reply(self, text):
        event = self.event(text=text)
        self.assertTrue(self.admit(event))
        with self.connect() as c:
            rows = c.execute('''SELECT o.content FROM qq_channel.outbox o
                JOIN qq_channel.inbox i ON i.id=o.inbox_id
                WHERE i.bot_id=%s AND i.message_id=%s ORDER BY o.part''',
                (self.bot, event.message_id)).fetchall()
        self.assertEqual(len(rows), 1)
        return rows[0][0]

    def test_explicit_help_does_not_create_query_or_ai_work(self):
        self.assertEqual(self.reply('/帮助'), HELP)
        with self.connect() as c:
            self.assertEqual(c.execute('''SELECT count(*) FROM qq_channel.official_queries q
                JOIN qq_channel.inbox i ON i.id=q.inbox_id WHERE i.bot_id=%s''', (self.bot,)).fetchone()[0], 0)
            self.assertEqual(c.execute('''SELECT count(*) FROM chat.agent_runs
                WHERE user_id IN (SELECT user_id FROM qq_channel.principals WHERE bot_id=%s)''',
                (self.bot,)).fetchone()[0], 0)
        self.assertIsNone(self.repo.claim_query())

    def test_empty_status_points_to_help_without_full_command_formats(self):
        reply = self.reply('/状态')
        self.assertIn('还没有', reply)
        self.assertIn('/帮助', reply)
        self.assertLessEqual(len(reply), 80)
        self.assertNotIn('[地域=', reply)


if __name__ == '__main__':
    unittest.main()

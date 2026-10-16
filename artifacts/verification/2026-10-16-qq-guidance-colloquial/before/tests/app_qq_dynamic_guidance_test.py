"""Bounded per-message model wording, async delivery and query-state isolation."""
import json
import os
import threading
import time
import unittest
from unittest.mock import patch

from tests import app_qq_character_postgres_test as fixtures


class Adapter:
    def __init__(self, reply=None, *, fail=False):
        self.reply, self.fail, self.calls = reply, fail, []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise TimeoutError('private details must not reach replies')
        yield {'type': 'completed', 'text': json.dumps({'reply': self.reply}, ensure_ascii=False)}


class DynamicGuidanceTest(unittest.TestCase):
    def writer(self, adapter):
        from server.app.channels.qq_official.guidance import DefaultGuidance
        return DefaultGuidance(adapter)

    def test_current_message_only_one_call_and_short_contextual_reply(self):
        reply = '闲聊暂时还没开放，鸡哥能帮你查魔兽成绩、复盘战斗；用法看 /帮助。'
        adapter = Adapter(reply)
        packet = self.writer(adapter).reply('能聊天吗')
        self.assertEqual(packet['status'], 'ready')
        self.assertEqual(packet['text'], reply)
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(json.loads(adapter.calls[0]['prompt']), {'message': '能聊天吗'})
        self.assertLessEqual(adapter.calls[0]['timeout_seconds'], 20)
        self.assertNotIn('tool_context', adapter.calls[0])

    def test_different_model_outputs_are_used_without_template_selection(self):
        for reply in ('鸡哥负责魔兽查询和战斗复盘，具体看 /帮助。', '想查角色还是复盘战斗？入口都在 /帮助。'):
            self.assertEqual(self.writer(Adapter(reply)).reply('你能干啥')['text'], reply)

    def test_invalid_or_failed_output_falls_back_once_without_leaking_it(self):
        from server.app.channels.qq_official.query_commands import INTRO
        for adapter in (Adapter('x' * 161), Adapter('用 /跑分 帮你模拟。/帮助'),
                        Adapter('访问 https://evil.invalid /帮助'), Adapter('没有帮助入口'),
                        Adapter(fail=True)):
            with self.subTest(reply=adapter.reply):
                packet = self.writer(adapter).reply('你好')
                self.assertEqual(packet['status'], 'fallback')
                self.assertEqual(packet['text'], INTRO)
                self.assertEqual(len(adapter.calls), 1)
                self.assertNotIn('private', str(packet))

    def test_configured_writer_uses_existing_no_tool_adapter(self):
        from server.app.channels.qq_official.guidance import DefaultGuidance, RULES
        with patch('server.app.chickenbro.codex_adapter.NativeCodexChatAdapter') as ctor:
            DefaultGuidance.configured()
        self.assertEqual(ctor.call_args.kwargs, {'qq_scope': 'social', 'qq_rules': RULES})
        for term in ('自由聊天', '当前', '不调用工具', '不读取历史', '/帮助'):
            self.assertIn(term, RULES)


@unittest.skipUnless(os.environ.get('QQ_OFFICIAL_TEST_DSN'), 'isolated official QQ test database required')
class DynamicGuidancePostgresTest(unittest.TestCase):
    setUp = fixtures.CharacterQueryPostgresTest.setUp
    tearDown = fixtures.CharacterQueryPostgresTest.tearDown
    event = fixtures.CharacterQueryPostgresTest.event
    admit = fixtures.CharacterQueryPostgresTest.admit

    def test_guidance_jobs_are_idempotent_and_never_become_general_chat(self):
        event = self.event(text='能聊天吗')
        self.assertTrue(self.admit(event))
        self.assertFalse(self.admit(event))
        job = self.repo.claim_query()
        self.assertIsNotNone(job)
        self.assertEqual(job['request'], {'kind': 'guidance', 'message': '能聊天吗'})
        self.assertIsNone(job['battle_context'])
        self.assertTrue(self.repo.finish_query(job, '功能引导，查看 /帮助。'))
        with self.connect() as c:
            row = c.execute('''SELECT i.conversation_id,i.run_id FROM qq_channel.inbox i
                WHERE i.id=%s''', (job['id'],)).fetchone()
            self.assertEqual(row, (None, None))
            self.assertEqual(c.execute('''SELECT count(*) FROM chat.agent_runs WHERE user_id=%s''',
                (job['user_id'],)).fetchone()[0], 0)

    def test_guidance_does_not_replace_query_status_and_help_stays_immediate(self):
        self.admit(self.event(text='/角色查询 Alice 服'))
        self.repo.finish_query(self.repo.claim_query(), 'Alice 结果')
        self.admit(self.event(text='你能做啥'))
        self.repo.finish_query(self.repo.claim_query(), '功能引导')
        status = self.event(text='/状态'); self.admit(status)
        help_event = self.event(text='/帮助'); self.admit(help_event)
        with self.connect() as c:
            def text(event):
                return c.execute('''SELECT o.content FROM qq_channel.outbox o
                    JOIN qq_channel.inbox i ON i.id=o.inbox_id
                    WHERE i.bot_id=%s AND i.message_id=%s ORDER BY o.part''',
                    (self.bot, event.message_id)).fetchone()[0]
            self.assertEqual(text(status), 'Alice 结果')
            self.assertIn('## 角色查询', text(help_event))
        self.assertIsNone(self.repo.claim_query())

    def test_expired_guidance_falls_back_without_model_retry_or_stale_finish(self):
        self.admit(self.event(text='能聊天吗'))
        job = self.repo.claim_query()
        with self.connect() as c:
            c.execute("UPDATE qq_channel.official_queries SET lease_expires_at=now()-interval '1 second' WHERE inbox_id=%s", (job['id'],))
        self.assertIsNone(self.repo.claim_query())
        self.assertFalse(self.repo.finish_query(job, '过期模型结果'))
        with self.connect() as c:
            row = c.execute('''SELECT i.state,q.attempts,q.result_packet->>'status' FROM qq_channel.official_queries q
                JOIN qq_channel.inbox i ON i.id=q.inbox_id WHERE i.id=%s''', (job['id'],)).fetchone()
        self.assertEqual(row, ('done', 1, 'fallback'))

    def test_slow_guidance_leaves_gateway_free_and_never_reads_game_source(self):
        from server.app.channels.qq_official.query_service import QueryService
        entered = threading.Event(); release = threading.Event()
        class Writer:
            def reply(inner, message):
                self.assertEqual(message, '能聊天吗')
                entered.set(); release.wait(3)
                return {'schema': 'qq-guidance-v1', 'status': 'ready', 'text': '闲聊暂未开放，用法看 /帮助。'}
        class Source:
            def query(inner, *args, **kwargs):
                raise AssertionError('guidance must not read character or battle sources')
        event = self.event(text='能聊天吗'); self.admit(event)
        service = QueryService(self.repo, Source(), battle_source=Source(), guidance_writer=Writer())
        try:
            start = time.monotonic(); service.advance()
            self.assertLess(time.monotonic() - start, 1)
            self.assertTrue(entered.wait(1))
            release.set()
            deadline = time.monotonic() + 3
            while service.active and time.monotonic() < deadline:
                service.advance(); time.sleep(.01)
            self.assertFalse(service.active)
            with self.connect() as c:
                row = c.execute('''SELECT q.result_text,q.result_packet->>'schema' FROM qq_channel.official_queries q
                    JOIN qq_channel.inbox i ON i.id=q.inbox_id WHERE i.bot_id=%s AND i.message_id=%s''',
                    (self.bot, event.message_id)).fetchone()
                self.assertEqual(row, ('闲聊暂未开放，用法看 /帮助。', 'qq-guidance-v1'))
        finally:
            release.set(); service.close()

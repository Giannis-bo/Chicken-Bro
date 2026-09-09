import importlib
import os
from pathlib import Path
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from server.app.chickenbro.application import ChatApplication
from server.app.chickenbro.repository import PostgresChatRepository
from server.app.identity.domain import Principal
from tests.app_chickenbro_application_test import FakeCodex


@unittest.skipUnless(os.environ.get('WOW_PG_TEST_DSN_V2'), 'isolated PostgreSQL DSN is not configured')
class ChatProgressPostgresTest(unittest.TestCase):
    def test_background_delivery_survives_disconnect_and_reopens_from_database(self):
        import psycopg
        from threading import Event
        from server.app.chickenbro.application import ChatApplicationError

        connect = lambda: psycopg.connect(os.environ['WOW_PG_TEST_DSN_V2'])
        with psycopg.connect(os.environ['WOW_PG_TEST_DSN_V2'], autocommit=True) as connection:
            importlib.import_module('server.migrations.product.apply').apply_product_migrations(
                connection, Path(__file__).resolve().parents[1] / 'server/migrations/product')
        owner, other = uuid4(), uuid4()
        with connect() as connection:
            connection.execute('INSERT INTO identity.users (id) VALUES (%s), (%s)', (owner, other))
        principal = Principal(user_id=owner, session_kind='mini_bearer')
        release = Event()
        class SlowCodex(FakeCodex):
            def stream(self, **kwargs):
                if not release.wait(5):
                    raise TimeoutError()
                yield {'type': 'completed', 'text': '数据库中保存的断线回答'}
        app = ChatApplication(repository=PostgresChatRepository(connect), codex=SlowCodex())
        conversation = app.create_conversation(principal, idempotency_key='postgres-detach-create')
        second = app.create_conversation(principal, idempotency_key='postgres-detach-second')
        delivery = app.start_delivery(principal, conversation.id, '问题',
                                      client_message_id='detach-client', idempotency_key='postgres-detach-send')
        next(delivery)
        delivery.close()
        try:
            with self.assertRaises(ChatApplicationError) as error:
                app.start_delivery(principal, second.id, '另一个问题',
                                   client_message_id='second-client', idempotency_key='postgres-detach-other')
            self.assertEqual(error.exception.code, 'CHAT_ACCOUNT_BUSY')
        finally:
            release.set()
        self.assertTrue(delivery.finished.wait(5))
        restored = ChatApplication(repository=PostgresChatRepository(connect), codex=FakeCodex())
        web_owner = Principal(user_id=owner, session_kind='web_cookie')
        reply = restored.load_conversation(web_owner, conversation.id)['messages'][-1]
        self.assertEqual(reply['reply_status'], 'completed')
        self.assertEqual(reply['content'], '数据库中保存的断线回答')
        with self.assertRaises(ChatApplicationError) as error:
            restored.load_conversation(Principal(user_id=other, session_kind='web_cookie'), conversation.id)
        self.assertEqual(error.exception.code, 'CONVERSATION_NOT_FOUND')
        replay = list(restored.start_delivery(principal, conversation.id, '问题',
                      client_message_id='detach-client', idempotency_key='postgres-detach-send'))
        self.assertEqual(replay[-1].text, reply['content'])
        self.assertEqual(restored._codex.calls, 0)

    def test_public_progress_survives_repository_restart_and_is_owner_scoped(self):
        import psycopg
        connect = lambda: psycopg.connect(os.environ['WOW_PG_TEST_DSN_V2'])
        with psycopg.connect(os.environ['WOW_PG_TEST_DSN_V2'], autocommit=True) as connection:
            importlib.import_module('server.migrations.product.apply').apply_product_migrations(
                connection, Path(__file__).resolve().parents[1] / 'server/migrations/product')
        owner, other = uuid4(), uuid4()
        with connect() as connection:
            connection.execute('INSERT INTO identity.users (id) VALUES (%s), (%s)', (owner, other))
        now = datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc)
        clock = [now]
        principal = Principal(user_id=owner, session_kind='mini_bearer')
        repository = PostgresChatRepository(connect)
        class ProgressCodex(FakeCodex):
            def stream(self, **kwargs):
                yield {'type': 'progress', 'text': '公开摘要'}
                clock[0] += timedelta(seconds=18)
                yield {'type': 'completed', 'text': '结论'}
        app = ChatApplication(repository=repository, codex=ProgressCodex(), clock=lambda: clock[0])
        conversation = app.create_conversation(principal, idempotency_key='postgres-progress-create')
        events = list(app.stream_message(principal, conversation.id, '问题',
            client_message_id='postgres-client', idempotency_key='postgres-progress-send'))
        run_id = events[0].run_id
        from uuid import UUID
        restarted = PostgresChatRepository(connect)
        self.assertEqual(restarted.list_run_presentations(other, conversation.id), [])
        with self.assertRaises(RuntimeError):
            restarted.append_public_progress(other, UUID(run_id), 'forged')
        with self.assertRaises(RuntimeError):
            restarted.append_public_progress(owner, UUID(run_id), 'after completion')
        restored = ChatApplication(repository=restarted, codex=FakeCodex(), clock=lambda: clock[0])
        reply = restored.load_conversation(principal, conversation.id)['messages'][-1]
        self.assertEqual(reply['progress_text'], '公开摘要')
        self.assertEqual(reply['duration_ms'], 18000)
        self.assertEqual(reply['content'], '结论')
        self.assertEqual(reply['reply_status'], 'completed')
        # A failed reply is a presentation of its run, not a fabricated assistant answer.
        restored._codex = FakeCodex([{'type': 'progress', 'text': '部分摘要'}, {'type': 'failed'}])
        list(restored.stream_message(principal, conversation.id, '第二次',
             client_message_id='failed-client', idempotency_key='postgres-failed-send'))
        failed = [row for row in restored.load_conversation(principal, conversation.id)['messages']
                  if row.get('reply_status') == 'failed']
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]['progress_text'], '部分摘要')
        self.assertEqual(failed[0]['content'], '')
        self.assertEqual(len(restarted.list_messages(owner, conversation.id)), 3)

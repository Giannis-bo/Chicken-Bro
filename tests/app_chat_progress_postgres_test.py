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

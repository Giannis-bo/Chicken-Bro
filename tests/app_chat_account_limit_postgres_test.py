import importlib
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
import unittest
from uuid import uuid4

from server.app.chickenbro.application import ChatApplication, ChatApplicationError
from server.app.chickenbro.repository import PostgresChatRepository
from server.app.identity.domain import Principal
from tests.app_chickenbro_application_test import FakeCodex


@unittest.skipUnless(os.environ.get('WOW_PG_TEST_DSN_V2'), 'isolated PostgreSQL DSN is not configured')
class ChatAccountLimitPostgresTest(unittest.TestCase):
    def setUp(self):
        import psycopg
        self.connect = lambda: psycopg.connect(os.environ['WOW_PG_TEST_DSN_V2'])
        with psycopg.connect(os.environ['WOW_PG_TEST_DSN_V2'], autocommit=True) as connection:
            importlib.import_module('server.migrations.product.apply').apply_product_migrations(
                connection, Path(__file__).resolve().parents[1] / 'server/migrations/product')
        self.owner = Principal(user_id=uuid4(), session_kind='web_cookie')
        self.web = Principal(user_id=self.owner.user_id, session_kind='web_cookie')
        self.other = Principal(user_id=uuid4(), session_kind='web_cookie')
        with self.connect() as connection:
            connection.execute('INSERT INTO identity.users (id) VALUES (%s), (%s)',
                               (self.owner.user_id, self.other.user_id))
        self.now = datetime.now(timezone.utc)
        self.repository = PostgresChatRepository(self.connect)
        self.app = self.application()
        self.a = self.app.create_conversation(self.owner, idempotency_key='create-account-a').id
        self.b = self.app.create_conversation(self.web, idempotency_key='create-account-b').id

    def application(self, codex=None):
        return ChatApplication(repository=PostgresChatRepository(self.connect),
            codex=codex or FakeCodex([{'type': 'completed', 'text': '回复'}]),
            clock=lambda: self.now, timeout_seconds=10, stale_run_grace_seconds=5)

    def stream(self, conversation, key, principal=None, app=None):
        return (app or self.app).stream_message(principal or self.owner, conversation, '问题',
            client_message_id=key, idempotency_key=key)

    def test_cross_client_rejection_does_not_persist_message_and_completion_unlocks(self):
        first = self.stream(self.a, 'request-first')
        next(first)
        self.addCleanup(first.close)
        with self.assertRaises(ChatApplicationError) as rejected:
            next(self.stream(self.b, 'request-second', self.web, self.application()))
        self.assertEqual(rejected.exception.code, 'CHAT_ACCOUNT_BUSY')
        self.assertIn('等待', rejected.exception.message)
        self.assertEqual(self.repository.list_messages(self.owner.user_id, self.b), [])
        self.assertEqual(list(first)[-1].event_type, 'completed')
        self.assertEqual(list(self.stream(self.b, 'request-second', self.web))[-1].event_type, 'completed')

    def test_simultaneous_requests_only_start_one_run(self):
        barrier = Barrier(2)
        def send(conversation, key):
            stream = self.stream(conversation, key, app=self.application())
            barrier.wait(timeout=5)
            try:
                return next(stream), stream
            except ChatApplicationError as error:
                return error.code, None
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(send, conversation, key) for conversation, key in
                       [(self.a, 'parallel-first'), (self.b, 'parallel-second')]]
            outcomes = [future.result(timeout=10) for future in futures]
        for _, stream in outcomes:
            if stream:
                self.addCleanup(stream.close)
        self.assertEqual(sum(stream is not None for _, stream in outcomes), 1)
        self.assertIn(('CHAT_ACCOUNT_BUSY', None), outcomes)
        with self.connect() as connection:
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM chat.agent_runs WHERE user_id=%s AND status='streaming'",
                (self.owner.user_id,)).fetchone()[0], 1)
            self.assertEqual(connection.execute('SELECT count(*) FROM chat.messages WHERE user_id=%s',
                (self.owner.user_id,)).fetchone()[0], 1)

    def test_same_conversation_is_restricted_but_other_account_is_independent(self):
        first = self.stream(self.a, 'same-first')
        next(first)
        self.addCleanup(first.close)
        with self.assertRaisesRegex(ChatApplicationError, 'CHAT_ACCOUNT_BUSY'):
            next(self.stream(self.a, 'same-second'))
        other = self.app.create_conversation(self.other, idempotency_key='other-create')
        self.assertEqual(list(self.stream(other.id, 'other-request', self.other))[-1].event_type, 'completed')

    def test_failure_and_disconnect_release_account(self):
        failing = self.application(FakeCodex([{'type': 'failed'}]))
        self.assertEqual(list(self.stream(self.a, 'failing-request', app=failing))[-1].event_type, 'failed')
        abandoned = self.stream(self.b, 'abandoned-request')
        next(abandoned)
        abandoned.close()
        self.assertEqual(list(self.stream(self.a, 'after-failure'))[-1].event_type, 'completed')

    def test_stale_run_in_another_conversation_is_recovered(self):
        first = self.stream(self.a, 'stale-first')
        event = next(first)
        self.addCleanup(first.close)
        self.now += timedelta(seconds=16)
        self.assertEqual(list(self.stream(self.b, 'after-stale', self.web))[-1].event_type, 'completed')
        with self.connect() as connection:
            self.assertEqual(connection.execute('SELECT status FROM chat.agent_runs WHERE id=%s',
                (event.run_id,)).fetchone()[0], 'failed')
        # A late completion from the expired run cannot become a successful answer.
        self.assertEqual(list(first)[-1].event_type, 'failed')

    def test_idempotent_replay_is_preserved_while_another_conversation_is_busy(self):
        original = list(self.stream(self.a, 'replay-first'))
        active = self.stream(self.b, 'replay-second')
        next(active)
        self.addCleanup(active.close)
        replay = list(self.stream(self.a, 'replay-first', self.web))
        self.assertEqual(replay[-1].text, original[-1].text)
        self.assertEqual(replay[0].run_id, original[0].run_id)
        with self.assertRaisesRegex(ChatApplicationError, 'CHAT_RUN_IN_PROGRESS'):
            next(self.stream(self.b, 'replay-second', self.web))

    def test_api_rejects_with_public_409_before_opening_sse(self):
        from fastapi.testclient import TestClient
        from server.app.main import create_app
        from server.app.platform.config import AppSettings
        from server.app.platform.health import ReadinessRegistry
        principal = self.web
        class Auth:
            def resolve_principal(self, credential, kind):
                return principal
        first = self.stream(self.a, 'api-first')
        next(first)
        self.addCleanup(first.close)
        app = create_app(settings=AppSettings(environment='test', database_url='postgresql://redacted',
            web_origin='https://www.chickenbro.cloud'), readiness_registry=ReadinessRegistry({}),
            web_auth_application=Auth(), chat_application=self.application(), simulation_application=object())
        with TestClient(app, base_url='https://www.chickenbro.cloud') as client:
            client.cookies.set('__Host-chickenbro-session', 'test-session')
            client.cookies.set('__Host-chickenbro-csrf', 'test-csrf')
            response = client.post(f'/api/v2/chat/conversations/{self.b}/messages/stream',
                headers={'Origin': 'https://www.chickenbro.cloud', 'X-CSRF-Token': 'test-csrf',
                         'Idempotency-Key': 'api-second'}, json={'content': '问题', 'clientMessageId': 'api-second'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error']['code'], 'CHAT_ACCOUNT_BUSY')
        self.assertIn('等待', response.json()['error']['message'])
        self.assertEqual(self.repository.list_messages(self.owner.user_id, self.b), [])

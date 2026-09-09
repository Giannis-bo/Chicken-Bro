import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta
from uuid import uuid4

from server.app.chickenbro.application import ChatApplicationError
from tests import app_chat_account_limit_postgres_test as fixture


@unittest.skipUnless(os.environ.get('WOW_PG_TEST_DSN_V2'), 'isolated PostgreSQL DSN is not configured')
class ChatFeedbackPostgresTest(unittest.TestCase):
    setUp = fixture.ChatAccountLimitPostgresTest.setUp
    application = fixture.ChatAccountLimitPostgresTest.application
    stream = fixture.ChatAccountLimitPostgresTest.stream

    def reply(self):
        list(self.stream(self.a, 'feedback-first'))
        return next(row for row in self.app.load_conversation(self.owner, self.a)['messages']
                    if row['role'] == 'assistant')['id']

    def test_feedback_is_persistent_immutable_and_shared_between_clients(self):
        message = self.reply()
        self.app.set_feedback(self.owner, self.a, message, False)
        first_saved = self.now
        self.now += timedelta(seconds=1)
        self.app.set_feedback(self.owner, self.a, message, False)
        reply = next(row for row in self.application().load_conversation(self.web, self.a)['messages']
                     if row['id'] == message)
        self.assertIs(reply['resolved'], False)
        with self.connect() as connection:
            row = connection.execute('SELECT resolved, user_message_id, runtime_revision FROM chat.agent_runs WHERE assistant_message_id=%s', (message,)).fetchone()
            self.assertIs(row[0], False)
            self.assertIsNotNone(row[1])
            self.assertTrue(row[2])
            self.assertEqual(connection.execute('SELECT count(*) FROM chat.agent_runs WHERE assistant_message_id=%s', (message,)).fetchone()[0], 1)
            self.assertEqual(connection.execute('SELECT feedback_updated_at FROM chat.agent_runs WHERE assistant_message_id=%s', (message,)).fetchone()[0], first_saved)
        with self.assertRaisesRegex(ChatApplicationError, 'FEEDBACK_ALREADY_SUBMITTED'):
            self.app.set_feedback(self.web, self.a, message, True)
        reply = next(row for row in self.app.load_conversation(self.owner, self.a)['messages'] if row['id'] == message)
        self.assertIs(reply['resolved'], False)

    def test_failed_and_streaming_runs_do_not_offer_or_accept_feedback(self):
        from tests.app_chickenbro_application_test import FakeCodex
        app = self.application(FakeCodex([{'type': 'failed'}]))
        stream = self.stream(self.a, 'feedback-failed', app=app)
        started = next(stream)
        with self.assertRaisesRegex(ChatApplicationError, 'FEEDBACK_MESSAGE_NOT_FOUND'):
            app.set_feedback(self.owner, self.a, started.run_id, False)
        list(stream)
        failed = next(row for row in app.load_conversation(self.owner, self.a)['messages'] if row.get('reply_status') == 'failed')
        self.assertNotIn('resolved', failed)
        with self.assertRaisesRegex(ChatApplicationError, 'FEEDBACK_MESSAGE_NOT_FOUND'):
            app.set_feedback(self.owner, self.a, failed['id'], False)

    def test_owner_message_conversation_and_completion_are_enforced(self):
        message = self.reply()
        user_message = next(row for row in self.app.load_conversation(self.owner, self.a)['messages'] if row['role'] == 'user')['id']
        for principal, conversation, target in [(self.other, self.a, message),
                (self.owner, self.b, message), (self.owner, self.a, user_message), (self.owner, self.a, uuid4())]:
            with self.subTest(target=target), self.assertRaisesRegex(ChatApplicationError, 'FEEDBACK_MESSAGE_NOT_FOUND'):
                self.app.set_feedback(principal, conversation, target, False)
        with self.assertRaisesRegex(ChatApplicationError, 'FEEDBACK_INVALID'):
            self.app.set_feedback(self.owner, self.a, message, 'false')
        self.app.delete_conversation(self.owner, self.a)
        with self.assertRaisesRegex(ChatApplicationError, 'FEEDBACK_MESSAGE_NOT_FOUND'):
            self.app.set_feedback(self.owner, self.a, message, False)

    def test_api_auth_csrf_strict_boolean_and_history(self):
        from fastapi.testclient import TestClient
        from server.app.main import create_app
        from server.app.platform.config import AppSettings
        from server.app.platform.health import ReadinessRegistry
        from server.app.identity.domain import Principal
        message = self.reply()
        owner, other = self.owner.user_id, self.other.user_id
        class Auth:
            def resolve_principal(self, credential, kind):
                return Principal(user_id=owner if credential == 'owner' else other, session_kind=kind) if credential in {'owner', 'other'} else None
        app = create_app(settings=AppSettings(environment='test', database_url='postgresql://redacted', web_origin='https://www.chickenbro.cloud'),
            readiness_registry=ReadinessRegistry({}), web_auth_application=Auth(), chat_application=self.app, simulation_application=object())
        route = f'/api/v2/chat/conversations/{self.a}/messages/{message}/feedback'
        with TestClient(app, base_url='https://www.chickenbro.cloud') as client:
            self.assertEqual(client.post(route, json={'resolved': False}).status_code, 401)
            self.assertEqual(client.post(route, headers={'Cookie': '__Host-chickenbro-session=other; __Host-chickenbro-csrf=csrf', 'Origin': 'https://www.chickenbro.cloud', 'X-CSRF-Token': 'csrf'}, json={'resolved': False}).status_code, 404)
            headers = {'Cookie': '__Host-chickenbro-session=owner; __Host-chickenbro-csrf=csrf', 'Origin': 'https://www.chickenbro.cloud', 'X-CSRF-Token': 'csrf'}
            for body in ({'resolved': 'false'}, {'resolved': 0}, {'resolved': None}, {}, {'resolved': False, 'user_id': str(other)}):
                self.assertEqual(client.post(route, headers=headers, json=body).status_code, 422)
            self.assertEqual(client.post(route, headers=headers, json={'resolved': False}).json(), {'resolved': False})
            client.cookies.set('__Host-chickenbro-session', 'owner')
            self.assertEqual(client.post(route, headers={'Origin': 'https://www.chickenbro.cloud'}, json={'resolved': True}).status_code, 403)
            legacy = client.get(f'/api/v2/chat/conversations/{self.a}?includeProgress=true').json()
            self.assertTrue(all('resolved' not in row for row in legacy['messages']))
            detail = client.get(f'/api/v2/chat/conversations/{self.a}?includeProgress=true&includeFeedback=true').json()
            self.assertIs(next(row for row in detail['messages'] if row['id'] == str(message))['resolved'], False)
            client.cookies.set('__Host-chickenbro-csrf', 'csrf')
            response = client.post(route, headers={'Origin': 'https://www.chickenbro.cloud', 'X-CSRF-Token': 'csrf'}, json={'resolved': True})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()['error']['code'], 'FEEDBACK_ALREADY_SUBMITTED')

    def test_concurrent_opposite_choices_only_accept_the_first_commit(self):
        message = self.reply()
        barrier = Barrier(2)
        def submit(choice):
            barrier.wait(timeout=5)
            try:
                return self.application().set_feedback(self.web if choice else self.owner, self.a, message, choice)
            except ChatApplicationError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(submit, choice) for choice in (True, False)]
            results = [future.result(timeout=5) for future in futures]
        self.assertEqual(results.count('FEEDBACK_ALREADY_SUBMITTED'), 1)
        winner = next(value for value in results if type(value) is bool)
        reply = next(row for row in self.app.load_conversation(self.owner, self.a)['messages'] if row['id'] == message)
        self.assertIs(reply['resolved'], winner)

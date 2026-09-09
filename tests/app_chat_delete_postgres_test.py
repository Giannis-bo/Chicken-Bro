import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from server.app.chickenbro.application import ChatApplicationError
from tests import app_chat_account_limit_postgres_test as fixture


@unittest.skipUnless(os.environ.get('WOW_PG_TEST_DSN_V2'), 'isolated PostgreSQL DSN is not configured')
class ChatDeletePostgresTest(unittest.TestCase):
    setUp = fixture.ChatAccountLimitPostgresTest.setUp
    application = fixture.ChatAccountLimitPostgresTest.application
    stream = fixture.ChatAccountLimitPostgresTest.stream

    def test_delete_hides_history_and_detail_across_clients_without_erasing_messages(self):
        list(self.stream(self.a, 'delete-first'))
        self.app.delete_conversation(self.web, self.a)
        self.app.delete_conversation(self.web, self.a)
        self.assertNotIn(self.a, [row.id for row in self.app.list_conversations(self.owner).items])
        with self.assertRaisesRegex(ChatApplicationError, 'CONVERSATION_NOT_FOUND'):
            self.app.load_conversation(self.owner, self.a)
        with self.assertRaisesRegex(ChatApplicationError, 'CONVERSATION_NOT_FOUND'):
            next(self.stream(self.a, 'delete-first'))
        with self.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM chat.messages WHERE conversation_id=%s',(self.a,)).fetchone()[0], 2)
        with self.assertRaisesRegex(ChatApplicationError, 'CONVERSATION_NOT_FOUND'):
            self.app.create_conversation(self.owner, idempotency_key='create-account-a')

    def test_other_owner_cannot_delete(self):
        with self.assertRaisesRegex(ChatApplicationError, 'CONVERSATION_NOT_FOUND'):
            self.app.delete_conversation(self.other, self.a)
        self.assertIsNotNone(self.app.load_conversation(self.owner, self.a))

    def test_streaming_cannot_be_deleted_but_other_conversation_can(self):
        stream = self.stream(self.a, 'delete-running')
        next(stream)
        self.addCleanup(stream.close)
        with self.assertRaisesRegex(ChatApplicationError, 'CHAT_CONVERSATION_BUSY'):
            self.app.delete_conversation(self.web, self.a)
        self.app.delete_conversation(self.web, self.b)
        list(stream)
        self.app.delete_conversation(self.web, self.a)

    def test_delete_and_start_race_never_archives_a_streaming_conversation(self):
        barrier = Barrier(2)
        def delete():
            barrier.wait()
            try:
                self.application().delete_conversation(self.web, self.a)
                return 'deleted'
            except ChatApplicationError as e:
                return e.code
        def start():
            stream = self.stream(self.a, 'delete-race', app=self.application())
            barrier.wait()
            try:
                next(stream)
                return stream
            except ChatApplicationError as e:
                return e.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            d, s = pool.submit(delete), pool.submit(start)
            deletion, stream = d.result(timeout=5), s.result(timeout=5)
        if not isinstance(stream,str):
            self.addCleanup(stream.close)
            self.assertEqual(deletion,'CHAT_CONVERSATION_BUSY')
        else:
            self.assertEqual((deletion,stream),('deleted','CONVERSATION_NOT_FOUND'))

    def test_delete_api_requires_owner_and_web_csrf_and_hides_other_browser_detail(self):
        from fastapi.testclient import TestClient
        from server.app.main import create_app
        from server.app.platform.config import AppSettings
        from server.app.platform.health import ReadinessRegistry
        from server.app.identity.domain import Principal
        owner, other = self.owner.user_id, self.other.user_id
        class Auth:
            def resolve_principal(self, credential, kind):
                return Principal(user_id=owner if credential == 'owner' else other, session_kind=kind) if credential in {'owner','other'} else None
        app = create_app(settings=AppSettings(environment='test',database_url='postgresql://redacted',web_origin='https://www.chickenbro.cloud'),
            readiness_registry=ReadinessRegistry({}), web_auth_application=Auth(), chat_application=self.app, simulation_application=object())
        route = f'/api/v2/chat/conversations/{self.a}'
        with TestClient(app, base_url='https://www.chickenbro.cloud') as client:
            self.assertEqual(client.delete(route).status_code,401)
            self.assertEqual(client.delete(route,headers={'Cookie': '__Host-chickenbro-session=other; __Host-chickenbro-csrf=csrf', 'Origin': 'https://www.chickenbro.cloud', 'X-CSRF-Token': 'csrf'}).status_code,404)
            client.cookies.set('__Host-chickenbro-session','owner')
            self.assertEqual(client.delete(route,headers={'Origin':'https://www.chickenbro.cloud'}).status_code,403)
            client.cookies.set('__Host-chickenbro-csrf','csrf')
            headers={'Origin':'https://www.chickenbro.cloud','X-CSRF-Token':'csrf'}
            stream=self.stream(self.a,'api-delete-stream')
            next(stream)
            try:
                response=client.delete(route,headers=headers)
                self.assertEqual(response.status_code,409)
                self.assertEqual(response.json()['error']['code'],'CHAT_CONVERSATION_BUSY')
            finally:
                stream.close()
            self.assertEqual(client.delete(route,headers=headers).json(),{'deleted':True})
            self.assertEqual(client.delete(route,headers=headers).status_code,200)
            client.cookies.clear()
            self.assertEqual(client.get(route,headers={'Cookie': '__Host-chickenbro-session=owner; __Host-chickenbro-csrf=csrf', 'Origin': 'https://www.chickenbro.cloud', 'X-CSRF-Token': 'csrf'}).status_code,404)

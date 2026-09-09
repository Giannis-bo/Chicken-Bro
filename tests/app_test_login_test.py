from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from server.app.identity.qq_application import QqAuthApplication
from server.app.identity.domain import digest
from server.app.identity.ports import PublicUser
from server.app.main import create_app
from server.app.platform.config import AppSettings
from server.app.platform.health import ReadinessRegistry
from tests.app_chat_api_test import build_chat_test_client
from tests.identity_fakes import InMemoryIdentityRepository


KEY_A = 'test-only-credential-A-' + 'a' * 32
KEY_B = 'test-only-credential-B-' + 'b' * 32
ORIGIN = 'https://www.chickenbro.cloud'


def settings(**overrides):
    env = {
        'WOW_APP_ENV': 'test', 'WOW_DATABASE_URL': 'postgresql://localhost/chickenbro_test',
        'WOW_WORKER_V2_HEARTBEAT_PATH': str(Path(__file__).resolve().parent / 'heartbeat.json'),
        'WOW_TEST_LOGIN_ENABLED': '1',
        'WOW_TEST_LOGIN_A_SHA256': digest(KEY_A), 'WOW_TEST_LOGIN_B_SHA256': digest(KEY_B),
    }
    env.update(overrides)
    return AppSettings.from_env(env)


class MemoryTestIdentity(InMemoryIdentityRepository):
    def has_qq_identity(self, *, user_id, appid):
        return False

    def get_qq_profile(self, *, user_id, appid):
        return {}

    def ensure_test_user(self, *, user_id, display_name, now):
        self.users.setdefault(user_id, PublicUser(user_id=user_id, display_name=display_name))


class TestLoginTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.repository = MemoryTestIdentity()
        self.config = settings()
        self.auth = QqAuthApplication(repository=self.repository, qq_gateway=object(),
                                       settings=self.config, clock=lambda: self.now)
        previous, _, _ = build_chat_test_client()
        self.app = create_app(self.config, readiness_registry=ReadinessRegistry({}),
                             web_auth_application=self.auth,
                             chat_application=previous.app.state.chat_application,
                             simulation_application=object())
        previous.close()
        self.client = TestClient(self.app, base_url=ORIGIN)
        self.addCleanup(self.client.close)

    def login(self, kind='web', account='A', credential=KEY_A, **extra):
        return self.client.post('/api/v2/auth/test/' + kind,
                                headers={'Origin': ORIGIN},
                                json={'account': account, 'credential': credential, **extra})

    def test_web_sessions_retain_chat_owner_and_other_account_is_isolated(self):
        web = self.login()
        self.assertEqual(web.status_code, 200)
        self.assertNotIn('accessToken', web.json())
        self.assertIn('HttpOnly', web.headers['set-cookie'])
        self.assertIn('Secure', web.headers['set-cookie'])
        csrf = self.client.cookies.get('__Host-chickenbro-csrf')
        created = self.client.post('/api/v2/chat/conversations',
            headers={'Origin': ORIGIN, 'X-CSRF-Token':csrf, 'Idempotency-Key':'test-login-chat-1'},
            json={'title':'测试 Web 历史'})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(self.login().status_code, 200)
        self.assertIn(created.json()['id'], [r['id'] for r in self.client.get('/api/v2/chat/conversations').json()['items']])
        self.assertEqual(self.client.get('/api/v2/me').json()['displayName'], '测试账号 A')
        self.assertEqual(self.client.post('/api/v2/chat/conversations', json={'title':'no csrf'}).status_code, 403)
        csrf = self.client.cookies.get('__Host-chickenbro-csrf')
        self.assertEqual(self.client.post('/api/v2/auth/logout', headers={'Origin':ORIGIN, 'X-CSRF-Token':csrf}).status_code, 200)
        self.assertEqual(self.client.get('/api/v2/me').status_code, 401)
        self.assertEqual(self.login(account='B', credential=KEY_B).status_code, 200)
        self.assertEqual(self.client.get('/api/v2/chat/conversations/' + created.json()['id']).status_code, 404)
        self.assertEqual(len(self.repository.identities), 0)
        self.assertEqual(self.login('mini').status_code, 404)

    def test_wrong_credential_unknown_account_and_client_owner_are_rejected_without_writes(self):
        for args in ({'credential': KEY_B}, {'account': 'real-user'}, {'user_id': str(uuid4())}):
            with self.subTest(args=args):
                response = self.login(**args)
                self.assertIn(response.status_code, (401, 422))
                self.assertNotIn(KEY_A, response.text)
        self.assertEqual(self.repository.auth_sessions, {})
        self.assertEqual(self.repository.users, {})

    def test_web_login_requires_exact_origin(self):
        response = self.client.post('/api/v2/auth/test/web', headers={'Origin': 'https://evil.example'},
                                    json={'account': 'A', 'credential': KEY_A})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.repository.auth_sessions, {})

    def test_disabled_and_expired_test_sessions_and_legacy_sessions_fail(self):
        self.assertEqual(self.login().status_code, 200)
        token = self.client.cookies.get('__Host-chickenbro-session')
        self.assertIsNotNone(self.auth.resolve_principal(token, 'web_cookie'))
        disabled = QqAuthApplication(repository=self.repository, qq_gateway=object(),
            settings=replace(self.config, test_login_enabled=False), clock=lambda:self.now)
        self.assertIsNone(disabled.resolve_principal(token, 'web_cookie'))
        self.assertIsNone(self.auth.resolve_principal(token, 'mini_bearer'))
        self.repository.issue_auth_session(token_hash=digest('legacy-token'), user_id=uuid4(),
            kind='web_cookie', expires_at=self.now + timedelta(hours=1))
        self.assertIsNone(disabled.resolve_principal('legacy-token', 'web_cookie'))
        self.now += timedelta(days=2)
        self.assertIsNone(self.auth.resolve_principal(token, 'web_cookie'))


class TestLoginConfigurationTest(unittest.TestCase):
    def test_feature_is_default_off(self):
        self.assertFalse(settings(WOW_TEST_LOGIN_ENABLED='0').test_login_enabled)

    def test_direct_production_configuration_cannot_enable_test_login(self):
        with self.assertRaises(ValueError):
            replace(settings(), environment='production')

    def test_production_and_non_test_databases_are_rejected(self):
        for overrides in ({'WOW_APP_ENV': 'production'},
                          {'WOW_DATABASE_URL': 'postgresql://localhost/chickenbro_prod'},
                          {'WOW_DATABASE_URL': 'postgresql://localhost/chickenbro_test?dbname=chickenbro_prod'},
                          {'WOW_TEST_LOGIN_A_SHA256': ''},
                          {'WOW_TEST_LOGIN_A_SHA256': digest(KEY_B)},
                          {'WOW_TEST_LOGIN_ENABLED': 'yes'}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                settings(**overrides)

    def test_disabled_routes_are_not_exposed(self):
        app = create_app(settings(WOW_TEST_LOGIN_ENABLED='0'), readiness_registry=ReadinessRegistry({}),
                         web_auth_application=object(), chat_application=object(), simulation_application=object())
        with TestClient(app) as client:
            self.assertEqual(client.post('/api/v2/auth/test/mini', json={}).status_code, 404)


if __name__ == '__main__':
    unittest.main()

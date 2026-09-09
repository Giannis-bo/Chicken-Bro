"""QQ Web auth contracts. Provider is faked only at the external HTTP boundary."""
import importlib.util
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Lock
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from server.app.platform.config import AppSettings
from server.app.identity.domain import Principal
from server.app.identity.ports import PublicUser

ORIGIN = 'https://www.chickenbro.cloud'
CALLBACK = ORIGIN + '/api/v2/auth/qq/callback'
NOW = datetime(2026, 9, 9, tzinfo=timezone.utc)


class MemoryRepository:
    def __init__(self):
        self.attempts, self.identities, self.sessions, self.users = {}, {}, {}, {}
        self.lock = Lock()

    def insert_qq_login_attempt(self, *, state_hash, browser_hash, expires_at, now):
        self.attempts[state_hash] = (browser_hash, expires_at, False)

    def consume_qq_login_attempt(self, *, state_hash, browser_hash, now):
        with self.lock:
            row = self.attempts.get(state_hash)
            if not row or row[0] != browser_hash or row[1] <= now or row[2]:
                return False
            self.attempts[state_hash] = (*row[:2], True)
            return True

    def upsert_qq_identity(self, *, appid, openid, now, profile=None):
        self.profile = profile or {}
        with self.lock:
            key = (appid, openid)
            if key not in self.identities:
                self.identities[key] = uuid4()
                self.users[self.identities[key]] = PublicUser(self.identities[key], 'QQ 账号')
            return self.identities[key]

    def issue_auth_session(self, *, token_hash, user_id, kind, expires_at):
        self.sessions[token_hash] = (user_id, kind, expires_at)

    def resolve_auth_session(self, *, token_hash, kind, now):
        row = self.sessions.get(token_hash)
        return Principal(user_id=row[0], session_kind=kind) if row and row[1] == kind and row[2] > now else None

    def has_qq_identity(self, *, user_id, appid):
        return any(owner == user_id and key[0] == appid for key, owner in self.identities.items())

    def get_qq_profile(self, *, user_id, appid):
        return getattr(self, "profile", {})

    def get_public_user(self, user_id):
        return self.users.get(user_id)

    def get_avatar(self, user_id):
        return None

    def revoke_auth_session(self, *, token_hash, kind, now):
        self.sessions.pop(token_hash, None)


class QqLoginTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('server.app.identity.qq_application'), 'QQ application must exist')
        from server.app.identity.qq_application import QqAuthApplication
        from server.app.integrations.qq_connect import QqConnectClient
        self.now = NOW
        self.repository = MemoryRepository()
        self.settings = AppSettings(environment='production', database_url='postgresql://redacted', qq_appid='1905584243',
                                    qq_app_key='test-key', qq_redirect_uri=CALLBACK)
        self.calls = []
        self.openid = 'A' * 32
        self.token_reply = {'access_token': 'T' * 32, 'expires_in': 3600}
        self.me_reply = None
        def provider(request):
            self.calls.append(request)
            self.assertEqual(request.url.host, 'graph.qq.com')
            self.assertEqual(request.url.params['fmt'], 'json')
            if request.url.path.endswith('/token'):
                self.assertEqual(request.url.params['redirect_uri'], CALLBACK)
                return httpx.Response(200, json=self.token_reply)
            if request.url.path.endswith('/get_user_info'):
                return httpx.Response(200, json=getattr(self, 'profile_reply', {'ret':0}))
            return httpx.Response(200, json=self.me_reply if self.me_reply is not None else
                                  {'client_id': '1905584243', 'openid': self.openid})
        self.gateway = QqConnectClient(self.settings, transport=httpx.MockTransport(provider))
        self.auth = QqAuthApplication(repository=self.repository, qq_gateway=self.gateway,
                                      settings=self.settings, clock=lambda: self.now)
        from server.app.main import create_app
        from server.app.platform.health import ReadinessRegistry
        self.app = create_app(self.settings, web_auth_application=self.auth, chat_application=object(),
                              simulation_application=object(), readiness_registry=ReadinessRegistry({}))
        self.client = TestClient(self.app, base_url=ORIGIN)
        self.addCleanup(self.client.close)

    def start(self, client=None):
        client = client or self.client
        response = client.post('/api/v2/auth/qq/login', json={}, headers={'Origin': ORIGIN})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(set(response.json()), {'authorizationUrl', 'requestId'})
        url = urlsplit(response.json()['authorizationUrl'])
        self.assertEqual(url.netloc, 'graph.qq.com')
        query = parse_qs(url.query)
        self.assertEqual(query['redirect_uri'], [CALLBACK])
        return query['state'][0], response

    def callback(self, state, client=None, **query):
        return (client or self.client).get('/api/v2/auth/qq/callback', params={'state': state, 'code': 'C'*32, **query}, follow_redirects=False)

    def test_success_cookie_csrf_logout_and_separate_qq_owners(self):
        state, started = self.start()
        binding = started.headers['set-cookie'].lower()
        for expected in ['secure', 'httponly', 'samesite=lax', 'path=/']:
            self.assertIn(expected, binding)
        response = self.callback(state)
        self.assertEqual(response.headers['location'], ORIGIN + '/')
        self.assertEqual(self.client.get('/api/v2/me').json()['displayName'], 'QQ 账号')
        owner = next(iter(self.repository.identities.values()))
        with TestClient(self.app, base_url=ORIGIN) as other:
            self.openid = 'B'*32
            state2, _ = self.start(other)
            self.assertEqual(self.callback(state2, other).status_code, 303)
        self.assertEqual(len(set(self.repository.identities.values())), 2)
        self.assertIn(owner, self.repository.identities.values())
        self.assertEqual(self.client.post('/api/v2/auth/logout', json={}, headers={'Origin': ORIGIN}).status_code, 403)
        csrf = self.client.cookies.get(self.settings.web_csrf_cookie_name)
        self.assertEqual(self.client.post('/api/v2/auth/logout', json={}, headers={'Origin': ORIGIN, 'X-CSRF-Token': csrf}).status_code, 200)
        self.assertEqual(self.client.get('/api/v2/me').status_code, 401)

    def test_state_cookie_mismatch_expiry_and_replay_do_not_call_provider(self):
        state, _ = self.start()
        self.assertIn('loginError=QQ_LOGIN_INVALID', self.callback('X'*43).headers['location'])
        self.assertFalse(self.calls)
        state, _ = self.start()
        with TestClient(self.app, base_url=ORIGIN) as other:
            self.assertIn('QQ_LOGIN_INVALID', self.callback(state, other).headers['location'])
        self.assertFalse(self.calls)
        self.now += timedelta(seconds=300)
        self.assertIn('QQ_LOGIN_INVALID', self.callback(state).headers['location'])
        self.assertFalse(self.calls)
        state, _ = self.start()
        self.assertEqual(self.callback(state).headers['location'], ORIGIN + '/')
        count = len(self.calls)
        self.assertIn('QQ_LOGIN_INVALID', self.callback(state).headers['location'])
        self.assertEqual(len(self.calls), count)

    def test_concurrent_consume_allows_one_provider_exchange(self):
        from server.app.identity.application import AuthApplicationError
        created = self.auth.create_qq_login()
        def finish(_):
            try:
                return self.auth.finish_qq_login(state=created.state, browser_binding=created.browser_binding, code='C'*32)
            except AuthApplicationError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(finish, range(2)))
        self.assertEqual(sum(value is not None for value in outcomes), 1)
        self.assertEqual(len(self.calls), 3)

    def test_malformed_provider_identity_and_token_fail_closed(self):
        for payload in [{}, {'client_id':'wrong', 'openid':'A'*32}, {'client_id':1905584243, 'openid':'A'*32},
                        {'client_id':'1905584243', 'openid':''}, {'client_id':'1905584243', 'openid':[]},
                        {'client_id':'1905584243', 'openid':'A'*32, 'error':1}]:
            with self.subTest(payload=payload):
                self.me_reply = payload
                state, _ = self.start()
                self.assertIn('QQ_PROVIDER_UNAVAILABLE', self.callback(state).headers['location'])
                self.assertFalse(self.repository.sessions)
        self.me_reply = None
        for payload in [{}, {'access_token':[]}, {'access_token':'a b', 'expires_in':3600},
                        {'access_token':'T'*32, 'expires_in':0}, {'access_token':'T'*32,'expires_in':True}]:
            self.token_reply = payload
            state, _ = self.start()
            self.assertIn('QQ_PROVIDER_UNAVAILABLE', self.callback(state).headers['location'])
            self.assertFalse(self.repository.sessions)

    def test_cancel_origin_host_and_legacy_routes(self):
        self.assertEqual(self.client.post('/api/v2/auth/qq/login', json={}).status_code, 403)
        self.assertEqual(self.client.post('/api/v2/auth/qq/login', json={}, headers={'Origin':ORIGIN, 'Host':'evil.example'}).status_code, 403)
        state, _ = self.start()
        response = self.callback(state, error='access_denied', error_description='private-provider-message')
        self.assertEqual(response.headers['location'], ORIGIN + '/?loginError=QQ_LOGIN_CANCELLED')
        self.assertFalse(self.calls)
        state, _ = self.start()
        response = self.client.get('/api/v2/auth/qq/callback', params={'state':state, 'code':'C'*32}, headers={'Host':'evil.example'}, follow_redirects=False)
        self.assertIn('QQ_LOGIN_INVALID', response.headers['location'])
        self.assertFalse(self.calls)
        for path in ['/api/v2/auth/wechat/mini/exchange', '/api/v2/auth/wechat/web/login-sessions', '/api/v2/auth/test/mini']:
            self.assertEqual(self.client.post(path, json={}).status_code, 404)

    def test_old_wechat_web_and_bearer_credentials_are_rejected(self):
        from server.app.identity.domain import digest
        for kind in ['web_cookie', 'mini_bearer']:
            self.repository.issue_auth_session(token_hash=digest('old-token'), user_id=uuid4(), kind=kind, expires_at=NOW+timedelta(days=1))
            self.assertIsNone(self.auth.resolve_principal('old-token', kind))
        state, _ = self.start()
        self.callback(state)
        token = self.client.cookies.get(self.settings.web_cookie_name)
        self.assertIsNone(self.auth.resolve_principal(token, 'mini_bearer'))

    def test_config_requires_exact_https_callback_and_hides_key(self):
        self.assertNotIn('test-key', repr(self.settings))
        for callback in ['http://www.chickenbro.cloud/api/v2/auth/qq/callback', CALLBACK+'?x=1', CALLBACK+'/', 'https://evil.example/api/v2/auth/qq/callback']:
            with self.assertRaises(ValueError):
                AppSettings(environment='production', database_url='postgresql://redacted', qq_appid='1905584243', qq_app_key='secret', qq_redirect_uri=callback)


    def test_profile_is_sanitized_optional_and_unsafe_avatar_not_exposed(self):
        self.profile_reply = {'ret':0, 'nickname':'  QQ\x00用户  ', 'figureurl_qq_2':'https://thirdqq.qlogo.cn/g?b=qq&k=public&s=100'}
        state, _ = self.start()
        self.callback(state)
        me = self.client.get('/api/v2/me').json()
        self.assertEqual(me.get('avatarUrl'), self.profile_reply['figureurl_qq_2'])
        self.assertEqual(self.repository.profile['nickname'], 'QQ用户')
        for avatar in ['http://q.qlogo.cn/x', 'https://q.qlogo.cn.evil.example/x', 'https://user@q.qlogo.cn/x', 'data:image/png;base64,AAAA']:
            self.profile_reply = {'ret':0, 'nickname':'ok', 'figureurl_qq_2':avatar}
            state, _ = self.start()
            self.assertEqual(self.callback(state).headers['location'], ORIGIN + '/')
            self.assertNotIn('avatarUrl', self.client.get('/api/v2/me').json())
        self.profile_reply = {'ret':100, 'msg':'private'}
        state, _ = self.start()
        self.assertEqual(self.callback(state).headers['location'], ORIGIN + '/')

    def test_callback_access_log_redacts_queries(self):
        import logging
        from server.app.main import QqCallbackAccessFilter
        record = logging.LogRecord('uvicorn.access', logging.INFO, '', 1, '%s - "%s %s HTTP/%s" %d',
                                   ('127.0.0.1', 'GET', '/api/v2/auth/qq/callback?code=private&state=private', '1.1', 303), None)
        self.assertTrue(QqCallbackAccessFilter().filter(record))
        self.assertNotIn('private', record.getMessage())


    def test_isolated_environment_callbacks_landing_and_binding_cookie(self):
        from dataclasses import replace
        for environment, prefix, landing in [('test','/test/api/v2','/test/'), ('candidate','/api/v2-candidate','/web-candidate/')]:
            callback = ORIGIN + prefix + '/auth/qq/callback'
            config = replace(self.settings, environment=environment,
                web_cookie_name='__Host-chickenbro-' + environment, qq_redirect_uri=callback)
            self.assertEqual(config.qq_landing_path, landing)
            self.assertNotEqual(config.qq_binding_cookie_name, self.settings.qq_binding_cookie_name)
            with self.assertRaises(ValueError):
                replace(config, qq_redirect_uri=CALLBACK)

    def test_provider_transport_failures_redirects_and_logs_are_safe(self):
        import logging
        from server.app.identity.ports import QqProviderError
        from server.app.integrations.qq_connect import QqConnectClient
        # Transport exceptions never expose credential-bearing requests or bodies.
        for mode in ['timeout', 'redirect', 'invalid_json', 'oversize']:
            requests = []
            def provider(request):
                requests.append(request)
                self.assertLessEqual(request.extensions['timeout']['read'], 8)
                self.assertLessEqual(request.extensions['timeout']['connect'], 3)
                if mode == 'timeout':
                    raise httpx.ReadTimeout('private token in provider request', request=request)
                if mode == 'redirect':
                    return httpx.Response(302, headers={'Location':'https://evil.example/'})
                return httpx.Response(200, content=b'x' * (17000 if mode == 'oversize' else 5))
            gateway = QqConnectClient(self.settings, transport=httpx.MockTransport(provider))
            with self.subTest(mode=mode), self.assertRaises(QqProviderError) as failure:
                gateway.exchange_code('C'*32)
            self.assertEqual(str(failure.exception), 'QQ provider unavailable')
            self.assertIsNone(failure.exception.__cause__)
            self.assertEqual(len(requests), 1)
        logger = logging.getLogger('httpx')
        class Capture(logging.Handler):
            def __init__(self):
                super().__init__()
                self.messages = []
            def emit(self, record):
                self.messages.append(record.getMessage())
        capture = Capture()
        old_level = logger.level
        logger.setLevel(logging.DEBUG)
        logger.addHandler(capture)
        try:
            self.gateway.exchange_code('C'*32)
        finally:
            logger.removeHandler(capture)
            logger.setLevel(old_level)
        self.assertEqual(capture.messages, [])

    def test_duplicate_callback_parameters_and_unconfigured_login_fail_closed(self):
        state, _ = self.start()
        response = self.client.get('/api/v2/auth/qq/callback', params=[('state',state),('state',state),('code','C'*32)], follow_redirects=False)
        self.assertIn('QQ_LOGIN_INVALID', response.headers['location'])
        self.assertFalse(self.calls)
        from dataclasses import replace
        from server.app.identity.qq_application import QqAuthApplication
        self.app.state.web_auth_application = QqAuthApplication(repository=self.repository,
            qq_gateway=self.gateway, settings=replace(self.settings, qq_app_key=''))
        response = self.client.post('/api/v2/auth/qq/login', json={}, headers={'Origin':ORIGIN})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('test-key', response.text)

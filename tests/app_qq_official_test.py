import copy
from datetime import datetime, timezone
import json
import unittest

import httpx


class OfficialPolicyTest(unittest.TestCase):
    def setUp(self):
        from server.app.channels.qq_official import policy
        self.policy = policy
        self.config = policy.OfficialConfig('102828220', ('group_A',))
        self.packet = {'op': 0, 't': 'GROUP_AT_MESSAGE_CREATE', 's': 42, 'd': {
            'id': 'msg_A-42', 'timestamp': '2026-10-14T12:00:00+08:00',
            'group_openid': 'group_A', 'group_id': '1127827451',
            'author': {'member_openid': 'member_A'},
            'content': '<@!bot_id> 怎样提升伤害？', 'attachments': []}}
        self.now = datetime(2026, 10, 14, 4, 0, 1, tzinfo=timezone.utc).timestamp()

    def test_official_at_event_preserves_opaque_identity_and_text(self):
        result = self.policy.parse_event(self.packet, self.config, now=self.now)
        self.assertEqual((result.bot, result.group, result.sender, result.message_id),
                         ('official:102828220', 'group_A', 'member_A', 'msg_A-42'))
        self.assertEqual(result.text, '怎样提升伤害？')

    def test_documented_robot_message_id_and_help_alias_are_supported(self):
        self.packet['d']['id'] = 'ROBOT1.0_message-A+/=='
        self.packet['d']['content'] = '<@!bot_id> 帮助'
        result = self.policy.parse_event(self.packet, self.config, now=self.now)
        self.assertIsNotNone(result)
        self.assertEqual(result.message_id, 'ROBOT1.0_message-A+/==')
        self.assertEqual(result.text, '/帮助')

    def test_other_groups_private_nonmention_stale_and_malformed_are_rejected(self):
        for key, value in [('group_openid', 'group_B'), ('author', None),
                           ('id', 'invalid\nmessage'), ('timestamp', 'bad')]:
            packet = copy.deepcopy(self.packet); packet['d'][key] = value
            self.assertIsNone(self.policy.parse_event(packet, self.config, now=self.now))
        for event in ('GROUP_MESSAGE_CREATE', 'C2C_MESSAGE_CREATE'):
            self.assertIsNone(self.policy.parse_event({**self.packet, 't': event}, self.config, now=self.now))
        self.assertIsNone(self.policy.parse_event(self.packet, self.config, now=self.now + 301))

    def test_attachment_gets_explicit_rejection_without_fetching_it(self):
        self.packet['d']['attachments'] = [{'url': 'http://127.0.0.1/secret'}]
        self.assertTrue(self.policy.parse_event(self.packet, self.config, now=self.now).error)

    def test_empty_allowlist_is_closed_and_secrets_are_not_configurable_as_ids(self):
        with self.assertRaises(ValueError): self.policy.OfficialConfig('102828220', ())
        with self.assertRaises(ValueError): self.policy.OfficialConfig('bad', ('group_A',))


class OfficialClientTest(unittest.TestCase):
    def setUp(self):
        from server.app.channels.qq_official.client import OfficialClient, OfficialError
        self.Client, self.Error = OfficialClient, OfficialError

    def client(self, handler, clock=lambda: 1000):
        return self.Client('102828220', 'test-secret',
                           http=httpx.Client(transport=httpx.MockTransport(handler)), clock=clock)

    def test_token_is_cached_refreshed_and_never_exposed_in_repr(self):
        calls = []; now = [1000]
        def handler(request):
            calls.append(request)
            if request.url.path == '/app/getAppAccessToken':
                return httpx.Response(200, json={'access_token': 'private-token', 'expires_in': '7200'})
            return httpx.Response(200, json={'url': 'wss://api.bot.qq.com/websocket/'})
        client = self.client(handler, lambda: now[0])
        client.gateway_url(); client.gateway_url()
        self.assertEqual(sum(r.url.path == '/app/getAppAccessToken' for r in calls), 1)
        self.assertEqual(calls[-1].headers['Authorization'], 'QQBot private-token')
        now[0] += 7141; client.gateway_url()
        self.assertEqual(sum(r.url.path == '/app/getAppAccessToken' for r in calls), 2)
        self.assertNotIn('test-secret', repr(client))
        self.assertNotIn('private-token', repr(client))

    def test_http_200_provider_error_and_unsafe_gateway_are_rejected(self):
        for response in ({'code': 100016, 'message': 'private-token test-secret'},
                         {'access_token': '', 'expires_in': 7200}):
            client = self.client(lambda request: httpx.Response(200, json=response))
            with self.assertRaises(self.Error) as got: client.access_token()
            self.assertNotIn('test-secret', str(got.exception))
        def handler(request):
            return httpx.Response(200, json=({'access_token': 'token', 'expires_in': 7200}
                if request.url.path.endswith('getAppAccessToken') else {'url': 'wss://evil.example/ws'}))
        with self.assertRaises(self.Error): self.client(handler).gateway_url()

    def test_live_legacy_qq_gateway_host_is_allowed_but_lookalikes_are_rejected(self):
        for host in ('api.sgroup.qq.com', 'api.sgroup.qq.com.evil.example'):
            def handler(request):
                return httpx.Response(200, json=({'access_token': 'token', 'expires_in': 7200}
                    if request.url.path.endswith('getAppAccessToken') else {'url': 'wss://' + host + '/websocket'}))
            if host == 'api.sgroup.qq.com':
                self.assertEqual(self.client(handler).gateway_url(), 'wss://api.sgroup.qq.com/websocket')
            else:
                with self.assertRaises(self.Error): self.client(handler).gateway_url()

    def test_reply_has_original_message_sequence_and_validates_receipt(self):
        sent = []
        def handler(request):
            if request.url.path.endswith('getAppAccessToken'):
                return httpx.Response(200, json={'access_token': 'token', 'expires_in': 7200})
            sent.append(request)
            return httpx.Response(200, json={'id': 'receipt_A'})
        client = self.client(handler)
        self.assertEqual(client.send_group('group_A', 'msg_A', '答案', 3), 'receipt_A')
        self.assertEqual(json.loads(sent[0].content),
                         {'msg_type': 0, 'content': '答案', 'msg_id': 'msg_A', 'msg_seq': 3})
        self.assertEqual(sent[0].url.path, '/v2/groups/group_A/messages')

    def test_send_timeout_is_never_retried(self):
        calls = []
        def handler(request):
            if request.url.path.endswith('getAppAccessToken'):
                return httpx.Response(200, json={'access_token': 'token', 'expires_in': 7200})
            calls.append(request)
            raise httpx.ReadTimeout('private-token', request=request)
        with self.assertRaises(self.Error) as got:
            self.client(handler).send_group('group_A', 'msg_A', '答案', 1)
        self.assertEqual(len(calls), 1)
        self.assertNotIn('private-token', str(got.exception))


class GatewayTest(unittest.TestCase):
    def test_identify_heartbeat_resume_and_persist_before_sequence(self):
        from server.app.channels.qq_official.gateway import GatewaySession
        sent = []; delivered = []; state = GatewaySession()
        state.handle({'op': 10, 'd': {'heartbeat_interval': 45000}}, sent.append,
                     delivered.append, 'test-token', now=1)
        self.assertEqual(sent[0], {'op': 2, 'd': {'token': 'QQBot test-token', 'intents': 33554432, 'shard': [0, 1]}})
        state.handle({'op': 0, 't': 'READY', 's': 1, 'd': {'session_id': 'session_A'}},
                     sent.append, delivered.append, 'test-token', now=2)
        state.heartbeat(sent.append, now=47)
        self.assertEqual(sent[-1], {'op': 1, 'd': 1})
        state.handle({'op': 11}, sent.append, delivered.append, 'test-token', now=48)
        def failed(packet): raise RuntimeError('persistence failed')
        with self.assertRaises(RuntimeError):
            state.handle({'op': 0, 't': 'GROUP_AT_MESSAGE_CREATE', 's': 2, 'd': {}},
                         sent.append, failed, 'test-token', now=49)
        self.assertEqual(state.seq, 1)
        state.handle({'op': 10, 'd': {'heartbeat_interval': 45000}}, sent.append,
                     delivered.append, 'test-token', now=50)
        self.assertEqual(sent[-1], {'op': 6, 'd': {'token': 'QQBot test-token', 'session_id': 'session_A', 'seq': 1}})

    def test_missing_ack_forces_reconnect_and_invalid_session_clears_resume(self):
        from server.app.channels.qq_official.gateway import GatewaySession, Reconnect
        state = GatewaySession(); sent = []
        state.handle({'op': 10, 'd': {'heartbeat_interval': 1000}}, sent.append, lambda p: None, 'token', now=0)
        state.heartbeat(sent.append, now=1)
        with self.assertRaises(Reconnect): state.heartbeat(sent.append, now=2.1)
        state.session_id = 'old'; state.seq = 9
        with self.assertRaises(Reconnect):
            state.handle({'op': 9, 'd': False}, sent.append, lambda p: None, 'token', now=3)
        self.assertIsNone(state.session_id)
        self.assertIsNone(state.seq)


class DeploymentTest(unittest.TestCase):
    def test_model_proxy_and_auth_home_are_preserved_but_web_identity_is_not(self):
        from server.app.channels.qq_official.deployment import runtime_environment
        env = runtime_environment({'WOW_DATABASE_URL': 'postgresql://wow_app@localhost/chickenbro_qq_channel',
            'HTTPS_PROXY': 'http://127.0.0.1:7890', 'NO_PROXY': 'localhost,127.0.0.1',
            'CODEX_HOME': '/home/ubuntu/.codex', 'WOW_CODEX_HOME': '/home/ubuntu/.codex',
            'WOW_CODEX_JOBS_DIR': '/old/jobs', 'WOW_QQ_APP_KEY': 'website-secret',
            'WOW_SIMC_SUPPORTED_SPECS': 'mage:fire'})
        self.assertEqual(env['HTTPS_PROXY'], 'http://127.0.0.1:7890')
        self.assertEqual(env['NO_PROXY'], 'localhost,127.0.0.1')
        self.assertEqual(env['CODEX_HOME'], '/home/ubuntu/.codex')
        self.assertEqual(env['WOW_CODEX_JOBS_DIR'], '/var/lib/chickenbro/qq-official/codex-jobs')
        self.assertEqual(env['WOW_DATABASE_URL'], 'postgresql://wow_app@localhost/chickenbro_qq_official_candidate')
        self.assertEqual(env['PGPASSFILE'], '/var/lib/chickenbro/qq-official/pgpass')
        self.assertNotIn('WOW_QQ_APP_KEY', env)


if __name__ == '__main__': unittest.main()

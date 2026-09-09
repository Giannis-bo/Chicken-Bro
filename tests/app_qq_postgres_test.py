import importlib
import os
from pathlib import Path
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

from server.app.identity.repository import PostgresIdentityRepository
from server.app.identity.domain import Principal, digest


@unittest.skipUnless(os.environ.get('WOW_PG_TEST_DSN_V2'), 'isolated PostgreSQL DSN is not configured')
class QqPostgresTest(unittest.TestCase):
    def setUp(self):
        import psycopg
        def runtime_connection():
            connection = psycopg.connect(os.environ['WOW_PG_TEST_DSN_V2'])
            connection.execute('SET ROLE wow_app')
            return connection
        self.connect = runtime_connection
        with psycopg.connect(os.environ['WOW_PG_TEST_DSN_V2'], autocommit=True) as connection:
            importlib.import_module('server.migrations.product.apply').apply_product_migrations(
                connection, Path(__file__).resolve().parents[1] / 'server/migrations/product')
        self.repository = PostgresIdentityRepository(self.connect)
        self.now = datetime.now(timezone.utc)

    def test_attempt_consume_is_atomic_bound_expiring_and_grant_limited(self):
        self.assertTrue(hasattr(self.repository, 'insert_qq_login_attempt'), 'QQ repository must support attempts')
        state, browser = digest(str(uuid4())), digest(str(uuid4()))
        self.repository.insert_qq_login_attempt(state_hash=state, browser_hash=browser, now=self.now, expires_at=self.now+timedelta(seconds=300))
        self.assertFalse(self.repository.consume_qq_login_attempt(state_hash=state, browser_hash='0'*64, now=self.now))
        self.assertFalse(self.repository.consume_qq_login_attempt(state_hash=state, browser_hash=browser, now=self.now+timedelta(seconds=300)))
        barrier = Barrier(2)
        def consume(_):
            barrier.wait(timeout=5)
            return PostgresIdentityRepository(self.connect).consume_qq_login_attempt(state_hash=state, browser_hash=browser, now=self.now)
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(consume, range(2))), [False, True])
        with self.connect() as connection:
            self.assertFalse(connection.execute("SELECT has_table_privilege('wow_app', 'identity.qq_login_attempts', 'DELETE')").fetchone()[0])
            connection.execute('SET ROLE wow_app')
            self.assertEqual(connection.execute('SELECT count(*) FROM identity.qq_login_attempts WHERE state_sha256=%s AND consumed_at IS NOT NULL', (state,)).fetchone()[0], 1)

    def test_concurrent_identity_upsert_has_one_owner_and_never_merges_wechat(self):
        self.assertTrue(hasattr(self.repository, 'upsert_qq_identity'), 'QQ repository must support identity')
        subject = uuid4().hex
        # Historical rows remain valid migration input; no retired provider code is invoked.
        old = uuid4()
        with self.connect() as connection:
            connection.execute("INSERT INTO identity.users(id,status) VALUES (%s,'active')", (old,))
            connection.execute("INSERT INTO identity.user_identities(id,user_id,provider,app_context,provider_subject) VALUES (%s,%s,'wechat_mini','1905584243',%s)", (uuid4(), old, subject))
        barrier = Barrier(2)
        def create(_):
            barrier.wait(timeout=5)
            return PostgresIdentityRepository(self.connect).upsert_qq_identity(appid='1905584243', openid=subject, profile={'nickname':'QQ 用户','avatarUrl':'https://q.qlogo.cn/headimg_dl?dst_uin=1'}, now=self.now)
        with ThreadPoolExecutor(max_workers=2) as pool:
            owners = list(pool.map(create, range(2)))
        self.assertEqual(owners[0], owners[1])
        self.assertNotEqual(old, owners[0])
        other = self.repository.upsert_qq_identity(appid='1905584243', openid=uuid4().hex, profile={}, now=self.now)
        self.assertNotEqual(other, owners[0])
        from server.app.chickenbro.repository import PostgresChatRepository
        from server.app.chickenbro.application import ChatApplication, ChatApplicationError
        from tests.app_chickenbro_application_test import FakeCodex
        chat = ChatApplication(repository=PostgresChatRepository(self.connect), codex=FakeCodex([]))
        first = Principal(user_id=owners[0], session_kind='web_cookie')
        second = Principal(user_id=other, session_kind='web_cookie')
        conversation = chat.create_conversation(first, idempotency_key='qq-isolation')
        with self.assertRaises(ChatApplicationError):
            chat.load_conversation(second, conversation.id)
        self.assertFalse(self.repository.has_qq_identity(user_id=old, appid='1905584243'))
        self.assertTrue(self.repository.has_qq_identity(user_id=first.user_id, appid='1905584243'))
        with self.connect() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM identity.user_identities WHERE provider='qq' AND app_context='1905584243' AND provider_subject=%s", (subject,)).fetchone()[0], 1)
            self.assertEqual(connection.execute('SELECT count(*) FROM identity.users WHERE id=%s', (old,)).fetchone()[0], 1)

import unittest
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4
from fastapi.testclient import TestClient
from server.app.identity.domain import Principal
from server.app.identity.test_accounts import TEST_ACCOUNT_IDS
from server.app.platform.config import AppSettings
from server.app.platform.health import ReadinessRegistry
from server.app.admin.application import AdminApplication, AdminError, date_window
from server.app.main import create_app

class Repository:
    def __init__(self, owner): self.owner, self.calls = owner, 0
    def is_qq_owner(self, user_id, appid): return user_id == self.owner and appid == '123'
    def overview(self, window, appid, game='wow'):
        self.calls += 1
        return {'window': window.start.isoformat(), 'appid': appid, 'game': game}

class AdminTest(unittest.TestCase):
    def setUp(self):
        self.owner, self.other = uuid4(), uuid4()
        self.repo = Repository(self.owner)
        self.settings = AppSettings(environment='production', database_url='postgresql://unused',
            qq_appid='123', qq_redirect_uri='https://www.chickenbro.cloud/api/v2/auth/qq/callback', admin_user_id=str(self.owner))
        self.admin = AdminApplication(repository=self.repo, settings=self.settings)
    def test_default_deny_wrong_owner_and_nonqq(self):
        for admin, owner in [(AdminApplication(repository=self.repo, settings=replace(self.settings,admin_user_id='')), self.owner),
                             (self.admin,self.other), (self.admin,next(iter(TEST_ACCOUNT_IDS.values())))]:
            self.assertFalse(admin.allowed(Principal(owner,'web_cookie')))
            with self.assertRaises(AdminError): admin.overview(Principal(owner,'web_cookie'),'2026-09-01','2026-09-09')
        self.assertEqual(self.repo.calls,0)
    def test_only_real_qq_owner_and_web_session(self):
        self.assertTrue(self.admin.allowed(Principal(self.owner,'web_cookie')))
        self.repo.owner=self.other
        self.assertFalse(self.admin.allowed(Principal(self.owner,'web_cookie')))
    def test_dates_beijing_end_exclusive_and_bounded(self):
        w=date_window('2026-09-01','2026-09-09',datetime(2026,9,9,tzinfo=timezone.utc))
        self.assertEqual(w.start.isoformat(),'2026-08-31T16:00:00+00:00')
        self.assertEqual(w.end.isoformat(),'2026-09-09T16:00:00+00:00')
        for a,b in [('2026-09-10','2026-09-09'),('2026-2-1','2026-02-02'),('2025-01-01','2026-09-09'),('2026-09-01','2026-09-10')]:
            with self.subTest(a=a,b=b), self.assertRaises(AdminError): date_window(a,b,datetime(2026,9,9,tzinfo=timezone.utc))
    def test_game_is_validated_and_forwarded(self):
        principal = Principal(self.owner, 'web_cookie')
        self.assertEqual(self.admin.overview(principal, None, None, 'poe2')['game'], 'poe2')
        self.assertEqual(self.admin.overview(principal, None, None)['game'], 'wow')
        with self.assertRaises(AdminError) as error:
            self.admin.overview(principal, None, None, 'other')
        self.assertEqual(error.exception.code, 'ADMIN_GAME_INVALID')
        self.assertEqual(self.repo.calls, 2)

    def test_bad_admin_configuration_fails_closed(self):
        for value in ['396318352','*',str(self.owner)+','+str(self.other),str(next(iter(TEST_ACCOUNT_IDS.values())))]:
            with self.assertRaises(ValueError): replace(self.settings,admin_user_id=value)
    def test_routes_require_session_before_query_and_no_store_even_errors(self):
        owner,other=self.owner,self.other
        class Auth:
            def resolve_principal(self,credential,kind):
                return Principal(owner if credential=='owner' else other,kind) if credential in {'owner','other'} else None
        app=create_app(self.settings,web_auth_application=Auth(),chat_application=object(),simulation_application=object(),readiness_registry=ReadinessRegistry({}),admin_application=self.admin)
        with TestClient(app,base_url='https://www.chickenbro.cloud') as client:
            for cookie,headers,status in [('',{},401),('other',{},403),('owner',{'Authorization':'Bearer anything'},400),('owner',{},200)]:
                client.cookies.clear()
                if cookie: client.cookies.set(self.settings.web_cookie_name,cookie)
                r=client.get('/api/v2/admin/overview?start=2026-09-01&end=2026-09-09&userId='+str(owner),headers=headers)
                self.assertEqual(r.status_code,status,r.text)
                self.assertEqual(r.headers['cache-control'],'no-store')
            client.cookies.set(self.settings.web_cookie_name,'other')
            access=client.get('/api/v2/admin/access').json()
            self.assertFalse(access['isAdmin'])
            self.assertEqual(access['accountId'],str(other))
            self.assertNotIn(str(owner),str(access))
        self.assertEqual(self.repo.calls,1)

    def test_query_failure_returns_generic_unavailable(self):
        def fail(*args): raise RuntimeError('private database diagnostic')
        self.repo.overview=fail
        with self.assertRaises(AdminError) as error:
            self.admin.overview(Principal(self.owner,'web_cookie'),'2026-09-01','2026-09-09')
        self.assertEqual(error.exception.status,503)
        self.assertNotIn('private',str(error.exception))

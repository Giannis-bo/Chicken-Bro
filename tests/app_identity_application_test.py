from datetime import datetime, timezone
from uuid import uuid4
import unittest

from server.app.identity.application import AuthApplicationError, WebAuthApplication
import server.app.identity.domain as identity_domain
from server.app.identity.domain import Principal, WebLoginSessionStatus, digest
from server.app.identity.ports import PublicUser, WechatIdentity
from server.app.platform.config import AppSettings


NOW = datetime(2026, 9, 2, 14, 30, tzinfo=timezone.utc)
PNG = b"\x89PNG\r\n\x1a\nformal"


class InMemoryIdentityRepository:
    def __init__(self):
        self.identities = {}
        self.identity_metadata = {}
        self.users = {}
        self.auth_sessions = {}
        self.web_login_sessions = {}
        self.revocations = []

    def get_user(self, user_id):
        return Principal(user_id=user_id, session_kind="mini_bearer") if user_id in self.users else None

    def upsert_wechat_mini_identity(self, *, app_context, provider_subject, union_id, now):
        key = ("wechat_mini", app_context, provider_subject)
        if key not in self.identities:
            user_id = uuid4()
            self.identities[key] = user_id
            self.users[user_id] = PublicUser(user_id=user_id, display_name="")
        self.identity_metadata[key] = {"union_id": union_id, "updated_at": now}
        return self.identities[key]

    def issue_auth_session(self, *, token_hash, user_id, kind, expires_at):
        self.auth_sessions[token_hash] = {
            "user_id": user_id,
            "kind": kind,
            "expires_at": expires_at,
            "revoked_at": None,
        }

    def resolve_auth_session(self, *, token_hash, kind, now):
        record = self.auth_sessions.get(token_hash)
        if (
            record is None
            or record["kind"] != kind
            or record["expires_at"] <= now
            or record["revoked_at"] is not None
        ):
            return None
        return Principal(user_id=record["user_id"], session_kind=kind)

    def revoke_auth_session(self, *, token_hash, kind, now):
        record = self.auth_sessions.get(token_hash)
        if record is not None and record["kind"] == kind:
            record["revoked_at"] = now
            self.revocations.append((token_hash, kind))

    def insert_web_login_session(self, session, *, now):
        self.web_login_sessions[session.id] = session

    def get_web_login_session(self, *, session_id, for_update=False):
        return self.web_login_sessions.get(session_id)

    def get_web_login_session_by_scene(self, *, scene_ticket_sha256, for_update=False):
        return next(
            (
                session
                for session in self.web_login_sessions.values()
                if session.scene_ticket_sha256 == scene_ticket_sha256
            ),
            None,
        )

    def get_web_login_session_by_idempotency(
        self,
        *,
        browser_verifier_sha256,
        idempotency_key_sha256,
        for_update=False,
    ):
        return next(
            (
                session
                for session in self.web_login_sessions.values()
                if session.browser_verifier_sha256 == browser_verifier_sha256
                and session.idempotency_key_sha256 == idempotency_key_sha256
            ),
            None,
        )

    def save_web_login_session(self, session, *, now):
        self.web_login_sessions[session.id] = session

    def get_public_user(self, user_id):
        return self.users.get(user_id)


class FixedWechatGateway:
    def __init__(self, *, openid="same-openid", unionid="optional-union"):
        self.identity = WechatIdentity(openid=openid, unionid=unionid)
        self.scenes = []

    def exchange_code(self, code):
        return self.identity

    def create_mini_code(self, *, scene, page, env_version):
        self.scenes.append(scene)
        return PNG


def settings(app_context):
    return AppSettings(
        environment="test",
        database_url="postgresql://redacted",
        web_origin="https://testserver",
        web_cookie_name="__Host-chickenbro-session",
        web_login_ttl_seconds=300,
        web_session_ttl_seconds=3600,
        wechat_appid=app_context,
        wechat_secret="configured-not-logged",
        wechat_page="pages/auth/web-login-confirm",
        wechat_env_version="trial",
    )


class AppIdentityApplicationTest(unittest.TestCase):
    def _application(self, repository, gateway, app_context="wx-primary"):
        return WebAuthApplication(
            repository=repository,
            wechat_gateway=gateway,
            settings=settings(app_context),
            clock=lambda: NOW,
        )

    def test_mini_exchange_and_confirmed_web_exchange_share_one_formal_user(self):
        """Catches creating a second owner when the browser consumes Mini confirmation."""
        repository = InMemoryIdentityRepository()
        gateway = FixedWechatGateway()
        application = self._application(repository, gateway)

        created = application.create_web_login("A" * 43, idempotency_key="formal-login")
        mini = application.exchange_mini_code("wx-code")
        application.confirm_mini_web_login(gateway.scenes[0], mini.principal)
        web = application.exchange_web_login(created.session.id, "A" * 43)

        self.assertEqual(mini.principal.user_id, web.principal.user_id)
        self.assertEqual(mini.principal.session_kind, "mini_bearer")
        self.assertEqual(web.principal.session_kind, "web_cookie")
        self.assertEqual(
            repository.web_login_sessions[created.session.id].status,
            WebLoginSessionStatus.CONSUMED,
        )

    def test_same_provider_subject_in_different_app_contexts_is_not_guessed_as_one_user(self):
        """Catches merging identical OpenID strings issued under different Mini Program AppIDs."""
        repository = InMemoryIdentityRepository()
        first = self._application(repository, FixedWechatGateway(), "wx-app-a").exchange_mini_code("a")
        second = self._application(repository, FixedWechatGateway(), "wx-app-b").exchange_mini_code("b")

        self.assertNotEqual(first.principal.user_id, second.principal.user_id)
        self.assertEqual(len(repository.identities), 2)
        self.assertEqual(
            set(repository.identities),
            {
                ("wechat_mini", "wx-app-a", "same-openid"),
                ("wechat_mini", "wx-app-b", "same-openid"),
            },
        )

    def test_mini_and_web_session_revocation_are_independent(self):
        """Catches logout revoking every credential or changing the shared business owner."""
        repository = InMemoryIdentityRepository()
        gateway = FixedWechatGateway()
        application = self._application(repository, gateway)
        created = application.create_web_login("B" * 43, idempotency_key="formal-login")
        mini = application.exchange_mini_code("wx-code")
        application.confirm_mini_web_login(gateway.scenes[0], mini.principal)
        web = application.exchange_web_login(created.session.id, "B" * 43)
        owner = mini.principal.user_id

        application.logout(mini.principal, mini.token)

        self.assertIsNone(application.resolve_principal(mini.token, "mini_bearer"))
        self.assertEqual(application.resolve_principal(web.token, "web_cookie"), web.principal)
        self.assertIn(owner, repository.users)

        application.logout(web.principal, web.token)

        self.assertIsNone(application.resolve_principal(web.token, "web_cookie"))
        self.assertIn(owner, repository.users)
        self.assertEqual(
            repository.revocations,
            [
                (digest(mini.token), "mini_bearer"),
                (digest(web.token), "web_cookie"),
            ],
        )

    def test_provider_identity_conflict_is_a_stable_public_auth_failure(self):
        """Catches leaking a repository error or silently relinking a conflicting identity."""
        conflict_type = getattr(identity_domain, "IdentityConflictError", None)
        if conflict_type is None:
            self.fail("formal identity conflict type is missing")

        class ConflictingRepository(InMemoryIdentityRepository):
            def upsert_wechat_mini_identity(self, **kwargs):
                raise conflict_type("identity conflict")

        application = self._application(ConflictingRepository(), FixedWechatGateway())

        with self.assertRaises(AuthApplicationError) as caught:
            application.exchange_mini_code("wx-code")

        self.assertEqual(caught.exception.code, "IDENTITY_CONFLICT")
        self.assertNotIn("same-openid", caught.exception.message)


if __name__ == "__main__":
    unittest.main()

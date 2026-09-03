from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import replace
from datetime import datetime, timezone
from threading import Event, Lock
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
        self.atomic_web_exchanges = 0
        self.atomic_web_confirmations = 0
        self.atomic_web_cancellations = 0
        self.atomic_web_expirations = 0

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

    def consume_web_login_session_and_issue_auth_session(
        self,
        *,
        session_id,
        browser_verifier_sha256,
        expected_user_id,
        token_hash,
        now,
        expires_at,
    ):
        session = self.web_login_sessions.get(session_id)
        if session is None or session.user_id != expected_user_id:
            return None
        try:
            consumed = identity_domain.consume_web_login_session(
                session,
                verifier_sha256=browser_verifier_sha256,
                now=now,
            )
        except ValueError:
            return None
        self.web_login_sessions[session_id] = consumed
        self.issue_auth_session(
            token_hash=token_hash,
            user_id=expected_user_id,
            kind="web_cookie",
            expires_at=expires_at,
        )
        self.atomic_web_exchanges += 1
        return expected_user_id

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
        return True

    def confirm_web_login_session(self, *, scene_ticket_sha256, user_id, now):
        session = next(
            (
                candidate
                for candidate in self.web_login_sessions.values()
                if candidate.scene_ticket_sha256 == scene_ticket_sha256
            ),
            None,
        )
        if session is None:
            return False
        try:
            confirmed = identity_domain.confirm_web_login_session(
                session,
                scene_ticket_sha256=scene_ticket_sha256,
                user_id=user_id,
                now=now,
            )
        except ValueError:
            return False
        self.web_login_sessions[session.id] = confirmed
        self.atomic_web_confirmations += 1
        return True

    def cancel_web_login_session(self, *, session_id, browser_verifier_sha256, now):
        session = self.web_login_sessions.get(session_id)
        if session is None or session.browser_verifier_sha256 != browser_verifier_sha256:
            return False
        try:
            cancelled = identity_domain.cancel_web_login_session(session, now=now)
        except ValueError:
            return False
        if cancelled.status is WebLoginSessionStatus.EXPIRED:
            return False
        self.web_login_sessions[session.id] = cancelled
        self.atomic_web_cancellations += 1
        return True

    def expire_web_login_session(self, *, session_id, now):
        session = self.web_login_sessions.get(session_id)
        if (
            session is None
            or session.status not in {WebLoginSessionStatus.PENDING, WebLoginSessionStatus.CONFIRMED}
            or now < session.expires_at
        ):
            return False
        self.web_login_sessions[session.id] = replace(
            session,
            status=WebLoginSessionStatus.EXPIRED,
        )
        self.atomic_web_expirations += 1
        return True

    def get_web_login_session(self, *, session_id):
        return self.web_login_sessions.get(session_id)

    def get_web_login_session_by_scene(self, *, scene_ticket_sha256):
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

    def get_public_user(self, user_id):
        return self.users.get(user_id)


class CompetingInsertIdentityRepository(InMemoryIdentityRepository):
    def insert_web_login_session(self, session, *, now):
        competing = replace(
            session,
            id=uuid4(),
            scene_ticket_sha256=digest("competing-process-scene"),
        )
        self.web_login_sessions[competing.id] = competing
        return False


class FixedWechatGateway:
    def __init__(self, *, openid="same-openid", unionid="optional-union"):
        self.identity = WechatIdentity(openid=openid, unionid=unionid)
        self.scenes = []

    def exchange_code(self, code):
        return self.identity

    def create_mini_code(self, *, scene, page, env_version):
        self.scenes.append(scene)
        return PNG


class BlockingWechatGateway(FixedWechatGateway):
    def __init__(self):
        super().__init__()
        self.first_started = Event()
        self.release_first = Event()
        self._calls_lock = Lock()
        self.create_calls = 0

    def create_mini_code(self, *, scene, page, env_version):
        with self._calls_lock:
            self.create_calls += 1
            call_number = self.create_calls
        if call_number == 1:
            self.first_started.set()
            if not self.release_first.wait(timeout=2):
                raise RuntimeError("test did not release the first QR creation")
        return super().create_mini_code(scene=scene, page=page, env_version=env_version)


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

    def test_expired_idempotent_create_returns_the_original_result_without_reinserting(self):
        """Catches a unique-key failure when a client retries its original create request."""
        repository = InMemoryIdentityRepository()
        gateway = FixedWechatGateway()
        application = self._application(repository, gateway)
        created = application.create_web_login("V" * 43, idempotency_key="stable-create")
        repository.web_login_sessions[created.session.id] = replace(
            created.session,
            expires_at=NOW,
        )

        retried = application.create_web_login("V" * 43, idempotency_key="stable-create")

        self.assertEqual(retried.session.id, created.session.id)
        self.assertEqual(len(repository.web_login_sessions), 1)
        self.assertEqual(len(gateway.scenes), 1)

    def test_process_restart_requires_a_new_qr_request_identity_without_persisting_scene_data(self):
        repository = InMemoryIdentityRepository()
        gateway = FixedWechatGateway()
        first_process = self._application(repository, gateway)
        created = first_process.create_web_login("R" * 43, idempotency_key="restart-create")
        restarted_process = self._application(repository, gateway)

        with self.assertRaises(AuthApplicationError) as caught:
            restarted_process.create_web_login("R" * 43, idempotency_key="restart-create")

        self.assertEqual(caught.exception.code, "WEB_LOGIN_RESTART_REQUIRED")
        self.assertEqual(len(repository.web_login_sessions), 1)
        self.assertEqual(len(repository.web_login_sessions[created.session.id].scene_ticket_sha256), 64)
        self.assertFalse(hasattr(created, "scene_ticket"))

    def test_cross_process_insert_race_fails_as_a_restart_instead_of_returning_an_unstored_qr(self):
        repository = CompetingInsertIdentityRepository()
        gateway = FixedWechatGateway()
        application = self._application(repository, gateway)

        with self.assertRaises(AuthApplicationError) as caught:
            application.create_web_login("P" * 43, idempotency_key="process-race")

        self.assertEqual(caught.exception.code, "WEB_LOGIN_RESTART_REQUIRED")
        self.assertEqual(len(repository.web_login_sessions), 1)
        stored = next(iter(repository.web_login_sessions.values()))
        self.assertNotEqual(stored.scene_ticket_sha256, digest(gateway.scenes[0]))

    def test_concurrent_idempotent_creates_share_one_process_local_qr(self):
        repository = InMemoryIdentityRepository()
        gateway = BlockingWechatGateway()
        application = self._application(repository, gateway)

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                application.create_web_login,
                "C" * 43,
                idempotency_key="concurrent-create",
            )
            self.assertTrue(gateway.first_started.wait(timeout=1))
            second = executor.submit(
                application.create_web_login,
                "C" * 43,
                idempotency_key="concurrent-create",
            )
            try:
                with self.assertRaises(FutureTimeoutError):
                    second.result(timeout=0.1)
            finally:
                gateway.release_first.set()
            first_result = first.result(timeout=1)
            second_result = second.result(timeout=1)

        self.assertEqual(first_result.session.id, second_result.session.id)
        self.assertEqual(first_result.qr_data_url, second_result.qr_data_url)
        self.assertEqual(gateway.create_calls, 1)
        self.assertEqual(len(repository.web_login_sessions), 1)

    def test_terminal_login_releases_process_local_qr_replay(self):
        repository = InMemoryIdentityRepository()
        gateway = FixedWechatGateway()
        application = self._application(repository, gateway)
        verifier = "T" * 43
        created = application.create_web_login(verifier, idempotency_key="terminal-create")

        application.cancel_web_login(created.session.id, verifier)

        with self.assertRaises(AuthApplicationError) as caught:
            application.create_web_login(verifier, idempotency_key="terminal-create")
        self.assertEqual(caught.exception.code, "WEB_LOGIN_RESTART_REQUIRED")

    def test_qr_replay_cache_has_a_fixed_process_memory_bound(self):
        repository = InMemoryIdentityRepository()
        gateway = FixedWechatGateway()
        application = self._application(repository, gateway)
        verifier = "M" * 43
        first = application.create_web_login(verifier, idempotency_key="bounded-000")
        for index in range(1, 257):
            application.create_web_login(verifier, idempotency_key=f"bounded-{index:03d}")

        with self.assertRaises(AuthApplicationError) as caught:
            application.create_web_login(verifier, idempotency_key="bounded-000")

        self.assertEqual(caught.exception.code, "WEB_LOGIN_RESTART_REQUIRED")
        self.assertIn(first.session.id, repository.web_login_sessions)
        self.assertEqual(len(repository.web_login_sessions), 257)

    def test_web_exchange_uses_atomic_consume_and_session_issue_port(self):
        """Catches consuming a ticket and issuing its Web credential in separate commits."""
        repository = InMemoryIdentityRepository()
        gateway = FixedWechatGateway()
        application = self._application(repository, gateway)
        created = application.create_web_login("Z" * 43, idempotency_key="atomic-login")
        mini = application.exchange_mini_code("wx-code")
        application.confirm_mini_web_login(gateway.scenes[0], mini.principal)

        application.exchange_web_login(created.session.id, "Z" * 43)

        self.assertEqual(repository.atomic_web_exchanges, 1)
        with self.assertRaises(AuthApplicationError) as caught:
            application.create_web_login("Z" * 43, idempotency_key="atomic-login")
        self.assertEqual(caught.exception.code, "WEB_LOGIN_RESTART_REQUIRED")

    def test_mini_confirmation_claims_the_web_ticket_atomically(self):
        """Catches two Mini users overwriting one QR login owner after a stale read."""
        repository = InMemoryIdentityRepository()
        gateway = FixedWechatGateway()
        application = self._application(repository, gateway)
        application.create_web_login("Y" * 43, idempotency_key="atomic-confirm")
        mini = application.exchange_mini_code("wx-code")

        application.confirm_mini_web_login(gateway.scenes[0], mini.principal)

        self.assertEqual(repository.atomic_web_confirmations, 1)

    def test_web_cancel_uses_a_conditional_verifier_bound_transition(self):
        """Catches a stale cancellation overwriting a terminal login state."""
        repository = InMemoryIdentityRepository()
        gateway = FixedWechatGateway()
        application = self._application(repository, gateway)
        created = application.create_web_login("X" * 43, idempotency_key="atomic-cancel")

        application.cancel_web_login(created.session.id, "X" * 43)

        self.assertEqual(repository.atomic_web_cancellations, 1)

    def test_status_expiry_uses_a_conditional_terminal_state_transition(self):
        """Catches an expiry write overwriting a concurrently consumed login."""
        repository = InMemoryIdentityRepository()
        gateway = FixedWechatGateway()
        application = self._application(repository, gateway)
        created = application.create_web_login("W" * 43, idempotency_key="atomic-expiry")
        repository.web_login_sessions[created.session.id] = replace(
            created.session,
            expires_at=NOW,
        )

        status = application.get_web_login_status(created.session.id, "W" * 43)

        self.assertEqual(status.status, WebLoginSessionStatus.EXPIRED)
        self.assertEqual(repository.atomic_web_expirations, 1)
        with self.assertRaises(AuthApplicationError) as caught:
            application.create_web_login("W" * 43, idempotency_key="atomic-expiry")
        self.assertEqual(caught.exception.code, "WEB_LOGIN_RESTART_REQUIRED")

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

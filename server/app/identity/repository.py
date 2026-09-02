from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from server.app.identity.domain import (
    Principal,
    SessionKind,
    WebLoginSession,
    WebLoginSessionStatus,
)
from server.app.identity.prototype import PrototypeSession
from server.app.identity.ports import PublicUser


def _row_value(row: Any, key: str, index: int) -> Any:
    if isinstance(row, Mapping):
        return row[key]
    return row[index]


class PostgresIdentityRepository:
    """PostgreSQL-only v2 identity and login-session owner."""

    def __init__(self, connection_factory: Callable[[], Any]):
        self._connection_factory = connection_factory

    def get_user(self, user_id: UUID) -> Principal | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM identity.users WHERE id = %s AND status = 'active'",
                    (user_id,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return Principal(user_id=UUID(str(_row_value(row, "id", 0))), session_kind="mini_bearer")

    def upsert_wechat_mini_identity(self, *, provider_subject: str, now: datetime) -> UUID:
        if not provider_subject or len(provider_subject) > 256:
            raise ValueError("provider subject is invalid")
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (provider_subject,),
                )
                cursor.execute(
                    """
                    SELECT user_id
                    FROM identity.user_identities
                    WHERE provider = %s AND provider_subject = %s
                    FOR UPDATE
                    """,
                    ("wechat_openid", provider_subject),
                )
                row = cursor.fetchone()
                if row is not None:
                    return UUID(str(_row_value(row, "user_id", 0)))

                user_id = uuid4()
                cursor.execute(
                    """
                    INSERT INTO identity.users (id, display_name, status, created_at, updated_at)
                    VALUES (%s, %s, 'active', %s, %s)
                    """,
                    (user_id, "", now, now),
                )
                cursor.execute(
                    """
                    INSERT INTO identity.user_identities (
                        id, user_id, provider, provider_subject, profile_json, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, '{}'::jsonb, %s, %s)
                    ON CONFLICT (provider, provider_subject) DO NOTHING
                    """,
                    (uuid4(), user_id, "wechat_openid", provider_subject, now, now),
                )
                cursor.execute(
                    """
                    SELECT user_id
                    FROM identity.user_identities
                    WHERE provider = %s AND provider_subject = %s
                    """,
                    ("wechat_openid", provider_subject),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("wechat identity upsert did not return an owner")
                return UUID(str(_row_value(row, "user_id", 0)))

    def issue_auth_session(
        self,
        *,
        token_hash: str,
        user_id: UUID,
        kind: SessionKind,
        expires_at: datetime,
    ) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO identity.auth_sessions (
                        token_hash, user_id, kind, expires_at, metadata_json
                    )
                    VALUES (%s, %s, %s, %s, '{}'::jsonb)
                    """,
                    (token_hash, user_id, kind, expires_at),
                )

    def resolve_auth_session(self, *, token_hash: str, kind: SessionKind, now: datetime) -> Principal | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id
                    FROM identity.auth_sessions
                    WHERE token_hash = %s
                      AND kind = %s
                      AND revoked_at IS NULL
                      AND expires_at > %s
                    """,
                    (token_hash, kind, now),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return Principal(
            user_id=UUID(str(_row_value(row, "user_id", 0))),
            session_kind=kind,
        )

    def revoke_auth_session(self, *, token_hash: str, kind: SessionKind, now: datetime) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE identity.auth_sessions
                    SET revoked_at = COALESCE(revoked_at, %s)
                    WHERE token_hash = %s AND kind = %s
                    """,
                    (now, token_hash, kind),
                )

    def create_prototype_user(self, *, user_id: UUID, now: datetime) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO identity.users (
                        id, display_name, status, account_kind, created_at, updated_at
                    )
                    VALUES (%s, '', 'active', 'prototype', %s, %s)
                    """,
                    (user_id, now, now),
                )

    def insert_prototype_session(self, session: PrototypeSession, *, now: datetime) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO identity.prototype_sessions (
                        id, user_id, token_sha256, expires_at, revoked_at, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        session.id,
                        session.user_id,
                        session.token_sha256,
                        session.expires_at,
                        session.revoked_at,
                        now,
                    ),
                )

    def get_prototype_session_by_token_hash(
        self,
        *,
        token_sha256: str,
        for_update: bool = False,
    ) -> PrototypeSession | None:
        lock_clause = " FOR UPDATE" if for_update else ""
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT ps.id, ps.user_id, ps.token_sha256, ps.expires_at, ps.revoked_at
                    FROM identity.prototype_sessions AS ps
                    JOIN identity.users AS u ON u.id = ps.user_id
                    WHERE ps.token_sha256 = %s
                      AND u.account_kind = 'prototype'
                      AND u.status = 'active'{lock_clause}
                    """,
                    (token_sha256,),
                )
                row = cursor.fetchone()
        return self._prototype_session_from_row(row) if row is not None else None

    def get_prototype_session(
        self,
        *,
        session_id: UUID,
        for_update: bool = False,
    ) -> PrototypeSession | None:
        lock_clause = " FOR UPDATE" if for_update else ""
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT ps.id, ps.user_id, ps.token_sha256, ps.expires_at, ps.revoked_at
                    FROM identity.prototype_sessions AS ps
                    JOIN identity.users AS u ON u.id = ps.user_id
                    WHERE ps.id = %s
                      AND u.account_kind = 'prototype'
                      AND u.status = 'active'{lock_clause}
                    """,
                    (session_id,),
                )
                row = cursor.fetchone()
        return self._prototype_session_from_row(row) if row is not None else None

    def save_prototype_session(self, session: PrototypeSession, *, now: datetime) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE identity.prototype_sessions
                    SET revoked_at = %s
                    WHERE id = %s AND user_id = %s
                    """,
                    (session.revoked_at, session.id, session.user_id),
                )

    def insert_web_login_session(self, session: WebLoginSession, *, now: datetime) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO identity.web_login_sessions (
                        id, scene_ticket_sha256, browser_verifier_sha256,
                        idempotency_key_sha256, user_id, status, expires_at,
                        exchanged_at, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        session.id,
                        session.scene_ticket_sha256,
                        session.browser_verifier_sha256,
                        session.idempotency_key_sha256,
                        session.user_id,
                        session.status.value,
                        session.expires_at,
                        session.exchanged_at,
                        now,
                        now,
                    ),
                )

    def get_web_login_session(self, *, session_id: UUID, for_update: bool = False) -> WebLoginSession | None:
        lock_clause = " FOR UPDATE" if for_update else ""
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT id, scene_ticket_sha256, browser_verifier_sha256,
                           idempotency_key_sha256, user_id, status, expires_at, exchanged_at
                    FROM identity.web_login_sessions
                    WHERE id = %s{lock_clause}
                    """,
                    (session_id,),
                )
                row = cursor.fetchone()
        return self._web_login_session_from_row(row) if row is not None else None

    def get_web_login_session_by_scene(
        self,
        *,
        scene_ticket_sha256: str,
        for_update: bool = False,
    ) -> WebLoginSession | None:
        lock_clause = " FOR UPDATE" if for_update else ""
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT id, scene_ticket_sha256, browser_verifier_sha256,
                           idempotency_key_sha256, user_id, status, expires_at, exchanged_at
                    FROM identity.web_login_sessions
                    WHERE scene_ticket_sha256 = %s{lock_clause}
                    """,
                    (scene_ticket_sha256,),
                )
                row = cursor.fetchone()
        return self._web_login_session_from_row(row) if row is not None else None

    def get_web_login_session_by_idempotency(
        self,
        *,
        browser_verifier_sha256: str,
        idempotency_key_sha256: str,
        for_update: bool = False,
    ) -> WebLoginSession | None:
        lock_clause = " FOR UPDATE" if for_update else ""
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT id, scene_ticket_sha256, browser_verifier_sha256,
                           idempotency_key_sha256, user_id, status, expires_at, exchanged_at
                    FROM identity.web_login_sessions
                    WHERE browser_verifier_sha256 = %s
                      AND idempotency_key_sha256 = %s{lock_clause}
                    """,
                    (browser_verifier_sha256, idempotency_key_sha256),
                )
                row = cursor.fetchone()
        return self._web_login_session_from_row(row) if row is not None else None

    def save_web_login_session(self, session: WebLoginSession, *, now: datetime) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE identity.web_login_sessions
                    SET user_id = %s,
                        status = %s,
                        exchanged_at = %s,
                        updated_at = %s
                    WHERE id = %s
                    """,
                    (
                        session.user_id,
                        session.status.value,
                        session.exchanged_at,
                        now,
                        session.id,
                    ),
                )

    def get_public_user(self, user_id: UUID) -> PublicUser | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, display_name
                    FROM identity.users
                    WHERE id = %s AND status = 'active'
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return PublicUser(
            user_id=UUID(str(_row_value(row, "id", 0))),
            display_name=str(_row_value(row, "display_name", 1) or ""),
        )

    @staticmethod
    def _web_login_session_from_row(row: Any) -> WebLoginSession:
        return WebLoginSession(
            id=UUID(str(_row_value(row, "id", 0))),
            scene_ticket_sha256=str(_row_value(row, "scene_ticket_sha256", 1)),
            browser_verifier_sha256=str(_row_value(row, "browser_verifier_sha256", 2)),
            idempotency_key_sha256=_row_value(row, "idempotency_key_sha256", 3),
            user_id=(
                UUID(str(_row_value(row, "user_id", 4)))
                if _row_value(row, "user_id", 4) is not None
                else None
            ),
            status=WebLoginSessionStatus(str(_row_value(row, "status", 5))),
            expires_at=_row_value(row, "expires_at", 6),
            exchanged_at=_row_value(row, "exchanged_at", 7),
        )

    @staticmethod
    def _prototype_session_from_row(row: Any) -> PrototypeSession:
        return PrototypeSession(
            id=UUID(str(_row_value(row, "id", 0))),
            user_id=UUID(str(_row_value(row, "user_id", 1))),
            token_sha256=str(_row_value(row, "token_sha256", 2)),
            expires_at=_row_value(row, "expires_at", 3),
            revoked_at=_row_value(row, "revoked_at", 4),
        )

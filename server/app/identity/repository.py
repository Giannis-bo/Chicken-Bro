from collections.abc import Callable, Mapping
from datetime import datetime
import json
from typing import Any
from uuid import UUID, uuid4

from server.app.identity.domain import (
    IdentityConflictError,
    Principal,
    SessionKind,
    WebLoginSession,
    WebLoginSessionStatus,
)
from server.app.identity.audit import AuthAuditEvent
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

    def record_auth_audit(self, event: AuthAuditEvent) -> None:
        payload = json.dumps(
            event.payload(),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ops.audit_events (
                        id, user_id, event_type, subject_key, payload_json, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (event_type, subject_key) DO NOTHING
                    """,
                    (
                        uuid4(),
                        event.user_id,
                        event.event_type,
                        event.subject_key,
                        payload,
                        event.timestamp,
                    ),
                )

    def upsert_wechat_mini_identity(
        self,
        *,
        app_context: str,
        provider_subject: str,
        union_id: str | None,
        now: datetime,
    ) -> UUID:
        if not app_context or len(app_context) > 128:
            raise ValueError("app context is invalid")
        if not provider_subject or len(provider_subject) > 256:
            raise ValueError("provider subject is invalid")
        if union_id is not None and (not union_id or len(union_id) > 256):
            raise ValueError("union id is invalid")
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"wechat_mini:{app_context}:{provider_subject}",),
                )
                cursor.execute(
                    """
                    SELECT user_id, union_id
                    FROM identity.user_identities
                    WHERE provider = %s
                      AND app_context = %s
                      AND provider_subject = %s
                    FOR UPDATE
                    """,
                    ("wechat_mini", app_context, provider_subject),
                )
                row = cursor.fetchone()
                if row is not None:
                    existing_union_id = _row_value(row, "union_id", 1)
                    if existing_union_id is not None and union_id is not None and existing_union_id != union_id:
                        raise IdentityConflictError("identity conflict")
                    cursor.execute(
                        """
                        UPDATE identity.user_identities
                        SET union_id = COALESCE(union_id, %s),
                            updated_at = %s
                        WHERE provider = %s
                          AND app_context = %s
                          AND provider_subject = %s
                        """,
                        (union_id, now, "wechat_mini", app_context, provider_subject),
                    )
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
                        id, user_id, provider, app_context, provider_subject,
                        union_id, profile_json, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, '{}'::jsonb, %s, %s)
                    RETURNING user_id, union_id
                    """,
                    (
                        uuid4(),
                        user_id,
                        "wechat_mini",
                        app_context,
                        provider_subject,
                        union_id,
                        now,
                        now,
                    ),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("wechat identity upsert did not return an owner")
                resolved_user_id = UUID(str(_row_value(row, "user_id", 0)))
                resolved_union_id = _row_value(row, "union_id", 1)
                if resolved_union_id is not None and union_id is not None and resolved_union_id != union_id:
                    raise IdentityConflictError("identity conflict")
                return resolved_user_id

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

    def consume_web_login_session_and_issue_auth_session(
        self,
        *,
        session_id: UUID,
        browser_verifier_sha256: str,
        expected_user_id: UUID,
        token_hash: str,
        now: datetime,
        expires_at: datetime,
    ) -> UUID | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH consumed AS (
                        UPDATE identity.web_login_sessions
                        SET status = 'consumed',
                            consumed_at = %s,
                            updated_at = %s
                        WHERE id = %s
                          AND status = 'confirmed'
                          AND browser_verifier_sha256 = %s
                          AND user_id = %s
                          AND consumed_at IS NULL
                          AND expires_at > %s
                        RETURNING user_id
                    )
                    INSERT INTO identity.auth_sessions (
                        token_hash, user_id, kind, issued_at, expires_at, metadata_json
                    )
                    SELECT %s, user_id, 'web_cookie', %s, %s, '{}'::jsonb
                    FROM consumed
                    RETURNING user_id
                    """,
                    (
                        now,
                        now,
                        session_id,
                        browser_verifier_sha256,
                        expected_user_id,
                        now,
                        token_hash,
                        now,
                        expires_at,
                    ),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return UUID(str(_row_value(row, "user_id", 0)))

    def resolve_auth_session(self, *, token_hash: str, kind: SessionKind, now: datetime) -> Principal | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT sessions.user_id
                    FROM identity.auth_sessions AS sessions
                    JOIN identity.users AS users ON users.id = sessions.user_id
                    WHERE sessions.token_hash = %s
                      AND sessions.kind = %s
                      AND sessions.revoked_at IS NULL
                      AND sessions.expires_at > %s
                      AND users.status = 'active'
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
                        consumed_at, created_at, updated_at
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
                        session.consumed_at,
                        now,
                        now,
                    ),
                )

    def confirm_web_login_session(
        self,
        *,
        scene_ticket_sha256: str,
        user_id: UUID,
        now: datetime,
    ) -> bool:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE identity.web_login_sessions
                    SET user_id = %s,
                        status = 'confirmed',
                        updated_at = %s
                    WHERE scene_ticket_sha256 = %s
                      AND status = 'pending'
                      AND user_id IS NULL
                      AND consumed_at IS NULL
                      AND expires_at > %s
                    RETURNING id
                    """,
                    (user_id, now, scene_ticket_sha256, now),
                )
                row = cursor.fetchone()
        return row is not None

    def cancel_web_login_session(
        self,
        *,
        session_id: UUID,
        browser_verifier_sha256: str,
        now: datetime,
    ) -> bool:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE identity.web_login_sessions
                    SET status = 'cancelled',
                        updated_at = %s
                    WHERE id = %s
                      AND browser_verifier_sha256 = %s
                      AND status IN ('pending', 'confirmed')
                      AND consumed_at IS NULL
                      AND expires_at > %s
                    RETURNING id
                    """,
                    (now, session_id, browser_verifier_sha256, now),
                )
                row = cursor.fetchone()
        return row is not None

    def expire_web_login_session(self, *, session_id: UUID, now: datetime) -> bool:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE identity.web_login_sessions
                    SET status = 'expired',
                        updated_at = %s
                    WHERE id = %s
                      AND status IN ('pending', 'confirmed')
                      AND consumed_at IS NULL
                      AND expires_at <= %s
                    RETURNING id
                    """,
                    (now, session_id, now),
                )
                row = cursor.fetchone()
        return row is not None

    def get_web_login_session(self, *, session_id: UUID) -> WebLoginSession | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, scene_ticket_sha256, browser_verifier_sha256,
                           idempotency_key_sha256, user_id, status, expires_at, consumed_at
                    FROM identity.web_login_sessions
                    WHERE id = %s
                    """,
                    (session_id,),
                )
                row = cursor.fetchone()
        return self._web_login_session_from_row(row) if row is not None else None

    def get_web_login_session_by_scene(
        self,
        *,
        scene_ticket_sha256: str,
    ) -> WebLoginSession | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, scene_ticket_sha256, browser_verifier_sha256,
                           idempotency_key_sha256, user_id, status, expires_at, consumed_at
                    FROM identity.web_login_sessions
                    WHERE scene_ticket_sha256 = %s
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
    ) -> WebLoginSession | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, scene_ticket_sha256, browser_verifier_sha256,
                           idempotency_key_sha256, user_id, status, expires_at, consumed_at
                    FROM identity.web_login_sessions
                    WHERE browser_verifier_sha256 = %s
                      AND idempotency_key_sha256 = %s
                    """,
                    (browser_verifier_sha256, idempotency_key_sha256),
                )
                row = cursor.fetchone()
        return self._web_login_session_from_row(row) if row is not None else None

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
            consumed_at=_row_value(row, "consumed_at", 7),
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

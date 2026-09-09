from collections.abc import Callable, Mapping
from datetime import datetime
import json
from typing import Any
from uuid import UUID, uuid4

from server.app.identity.domain import (
    IdentityConflictError,
    Principal,
    SessionKind,
)
from server.app.identity.audit import AuthAuditEvent
from server.app.identity.ports import PublicUser
from server.app.identity.test_accounts import TEST_ACCOUNT_IDS


def _row_value(row: Any, key: str, index: int) -> Any:
    if isinstance(row, Mapping):
        return row[key]
    return row[index]


class PostgresIdentityRepository:
    """PostgreSQL-only v2 identity and login-session owner."""

    def __init__(self, connection_factory: Callable[[], Any]):
        self._connection_factory = connection_factory

    def insert_qq_login_attempt(self, *, state_hash: str, browser_hash: str,
                               expires_at: datetime, now: datetime) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""INSERT INTO identity.qq_login_attempts
                    (state_sha256, browser_sha256, expires_at, created_at)
                    VALUES (%s, %s, %s, %s)""", (state_hash, browser_hash, expires_at, now))

    def consume_qq_login_attempt(self, *, state_hash: str, browser_hash: str, now: datetime) -> bool:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""UPDATE identity.qq_login_attempts SET consumed_at=%s
                    WHERE state_sha256=%s AND browser_sha256=%s
                    AND consumed_at IS NULL AND expires_at > %s RETURNING state_sha256""",
                    (now, state_hash, browser_hash, now))
                return cursor.fetchone() is not None

    def upsert_qq_identity(self, *, appid: str, openid: str, profile: dict, now: datetime) -> UUID:
        if not appid or len(appid) > 128 or not openid or len(openid) > 256:
            raise ValueError("QQ identity is invalid")
        from server.app.identity.qq_application import sanitize_qq_profile
        public = sanitize_qq_profile(profile)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"qq:{appid}:{openid}",))
                cursor.execute("""SELECT user_id FROM identity.user_identities
                    WHERE provider='qq' AND app_context=%s AND provider_subject=%s FOR UPDATE""", (appid, openid))
                row = cursor.fetchone()
                if row is not None:
                    user_id = UUID(str(_row_value(row, "user_id", 0)))
                    # An optional profile failure does not erase a saved public profile.
                    if public:
                        cursor.execute("""UPDATE identity.user_identities
                            SET profile_json=profile_json || %s::jsonb, updated_at=%s
                            WHERE provider='qq' AND app_context=%s AND provider_subject=%s""",
                            (json.dumps(public), now, appid, openid))
                        if public.get('nickname'):
                            cursor.execute("UPDATE identity.users SET display_name=%s, updated_at=%s WHERE id=%s",
                                           (public['nickname'], now, user_id))
                    return user_id
                user_id = uuid4()
                cursor.execute("""INSERT INTO identity.users (id, display_name, status, created_at, updated_at)
                    VALUES (%s, %s, 'active', %s, %s)""", (user_id, public.get('nickname', 'QQ 账号'), now, now))
                cursor.execute("""INSERT INTO identity.user_identities
                    (id, user_id, provider, app_context, provider_subject, profile_json, created_at, updated_at)
                    VALUES (%s, %s, 'qq', %s, %s, %s::jsonb, %s, %s)""",
                    (uuid4(), user_id, appid, openid, json.dumps(public), now, now))
                return user_id

    def has_qq_identity(self, *, user_id: UUID, appid: str) -> bool:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""SELECT 1 FROM identity.user_identities
                    WHERE user_id=%s AND provider='qq' AND app_context=%s""", (user_id, appid))
                return cursor.fetchone() is not None

    def get_qq_profile(self, *, user_id: UUID, appid: str) -> dict:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""SELECT profile_json FROM identity.user_identities
                    WHERE user_id=%s AND provider='qq' AND app_context=%s""", (user_id, appid))
                row = cursor.fetchone()
        return _row_value(row, 'profile_json', 0) if row is not None else {}

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


    def ensure_test_user(self, *, user_id: UUID, display_name: str, now: datetime) -> None:
        if user_id not in TEST_ACCOUNT_IDS.values():
            raise IdentityConflictError("test owner is not reserved")
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO identity.users (id, display_name, status, created_at, updated_at)
                       VALUES (%s, %s, 'active', %s, %s) ON CONFLICT (id) DO NOTHING""",
                    (user_id, display_name, now, now),
                )
                cursor.execute(
                    """SELECT id FROM identity.users u
                       WHERE id = %s AND display_name = %s AND status = 'active'
                       AND NOT EXISTS (SELECT 1 FROM identity.user_identities i WHERE i.user_id = u.id)
                       FOR UPDATE OF u""",
                    (user_id, display_name),
                )
                if cursor.fetchone() is None:
                    raise IdentityConflictError("test owner conflicts with an existing user")

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


    def get_avatar(self, user_id: UUID) -> str | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT avatar_data_url FROM identity.users WHERE id = %s AND status = 'active'", (user_id,))
                row = cursor.fetchone()
        return _row_value(row, "avatar_data_url", 0) if row is not None else None


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

#!/usr/bin/env python3
from contextlib import contextmanager
import hashlib
import json
import secrets
import uuid

try:
    from .chickenbro_observability import validate_chickenbro_agent_trace
except ImportError:  # pragma: no cover - script entrypoint compatibility
    from chickenbro_observability import validate_chickenbro_agent_trace


IDENTITY_NAMESPACE = uuid.UUID("b8589a4f-2d8f-4d34-82a8-f2f29d3e7ed6")
CHICKENBRO_JOB_STATUSES = {"queued", "running", "succeeded", "failed", "timed_out", "cancelled"}


def auth_token_hash(token):
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def build_template_config_hash(template_type, raw_string):
    digest = hashlib.sha256()
    digest.update(str(template_type or "").encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(raw_string or "").encode("utf-8"))
    return digest.hexdigest()


def json_param(value):
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def _json_value(value, fallback):
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed is not None else fallback


def _public_user_from_pg_row(row):
    if not row:
        return None
    return {
        "id": str(row[0]),
        "openid": row[1] or "",
        "unionid": row[2] or "",
        "nickname": row[3] or "",
        "avatarUrl": row[4] or "",
        "createdAt": str(row[5] or ""),
        "updatedAt": str(row[6] or ""),
    }


def _public_build_template_from_pg_row(row):
    if not row:
        return None
    simc_lines = _json_value(row[13], [])
    metadata = _json_value(row[17], {})
    if not isinstance(simc_lines, list):
        simc_lines = []
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "id": str(row[0]),
        "clientId": row[1] or "",
        "type": row[2] or "",
        "title": row[3] or "",
        "classKey": row[4] or "",
        "className": row[5] or "",
        "specKey": row[6] or "",
        "specName": row[7] or "",
        "heroKey": row[8] or "",
        "heroLabel": row[9] or "",
        "scenarioKey": row[10] or "",
        "scenarioTitle": row[11] or "",
        "rawString": row[12] or "",
        "simcLines": simc_lines,
        "status": row[14] or "",
        "statusLabel": row[15] or "",
        "source": row[16] or "",
        "metadata": metadata,
        "schemaVersion": row[18] or 1,
        "createdAt": str(row[19] or ""),
        "updatedAt": str(row[20] or ""),
        "remote": True,
    }


def _public_chickenbro_session_from_pg_row(row):
    if not row:
        return None
    context = _json_value(row[4], {})
    if not isinstance(context, dict):
        context = {}
    metadata = context.get("metadata") if isinstance(context.get("metadata"), dict) else {}
    return {
        "sessionId": str(row[0]),
        "title": row[2] or "",
        "productPhase": context.get("productPhase") or "retail",
        "metadata": metadata,
        "createdAt": str(row[5] or ""),
        "updatedAt": str(row[6] or ""),
    }


def _public_chickenbro_session_summary_from_pg_row(row):
    if not row:
        return None
    return {
        "sessionId": str(row[0]),
        "title": row[1] or "",
        "productPhase": row[2] or "retail",
        "createdAt": str(row[3] or ""),
        "updatedAt": str(row[4] or ""),
    }


def _public_chickenbro_message_from_pg_row(row):
    if not row:
        return None
    payload = _json_value(row[5], {})
    if not isinstance(payload, dict):
        payload = {}
    return {
        "messageId": str(row[0]),
        "sessionId": str(row[1]),
        "role": row[3] or "",
        "content": row[4] or "",
        "payload": payload,
        "agentJobId": str(row[6] or ""),
        "createdAt": str(row[7] or ""),
    }


def _public_chickenbro_job_from_pg_row(row):
    if not row:
        return None
    return {
        "jobId": str(row[0]),
        "sessionId": str(row[2] or ""),
        "kind": row[3] or "",
        "status": row[4] or "",
        "request": _json_value(row[5], {}),
        "boundedContext": _json_value(row[6], {}),
        "result": _json_value(row[7], {}),
        "error": row[8] or "",
        "createdAt": str(row[9] or ""),
        "updatedAt": str(row[10] or ""),
        "startedAt": str(row[11] or ""),
        "finishedAt": str(row[12] or ""),
    }


def _payload_evidence_refs(payload):
    payload = payload if isinstance(payload, dict) else {}
    refs = []
    for ref in payload.get("evidenceRefs") or []:
        if ref:
            refs.append(str(ref))
    for action in payload.get("priorityActions") or []:
        if not isinstance(action, dict):
            continue
        for ref in action.get("evidenceRefs") or []:
            if ref:
                refs.append(str(ref))
    return list(dict.fromkeys(refs))


class PostgresPersonalStore:
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    @contextmanager
    def connection(self):
        conn = self.connection_factory()
        try:
            yield conn
            if hasattr(conn, "commit"):
                conn.commit()
        except Exception:
            if hasattr(conn, "rollback"):
                conn.rollback()
            raise

    def upsert_wechat_user(self, openid, unionid="", now=""):
        normalized_openid = str(openid or "").strip()
        normalized_unionid = str(unionid or "").strip()
        if not normalized_openid:
            raise ValueError("openid is required")
        user_id = str(uuid.uuid5(IDENTITY_NAMESPACE, f"identity.users:wechat_openid:{normalized_openid}"))
        openid_identity_id = str(uuid.uuid5(IDENTITY_NAMESPACE, f"identity.user_identities:wechat_openid:{normalized_openid}"))
        unionid_identity_id = str(uuid.uuid5(IDENTITY_NAMESPACE, f"identity.user_identities:wechat_unionid:{normalized_unionid}"))
        profile = {"openid": normalized_openid}
        if normalized_unionid:
            profile["unionid"] = normalized_unionid
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH existing AS (
                        SELECT user_id
                        FROM identity.user_identities
                        WHERE provider = 'wechat_openid' AND provider_subject = %s
                    ),
                    inserted_user AS (
                        INSERT INTO identity.users (id, display_name, status, created_at, updated_at)
                        SELECT %s, '', 'active', %s, %s
                        WHERE NOT EXISTS (SELECT 1 FROM existing)
                        ON CONFLICT (id) DO UPDATE SET updated_at = EXCLUDED.updated_at
                        RETURNING id
                    ),
                    target_user AS (
                        SELECT user_id AS id FROM existing
                        UNION
                        SELECT id FROM inserted_user
                        LIMIT 1
                    )
                    INSERT INTO identity.user_identities (
                        id, user_id, provider, provider_subject, profile_json, created_at, updated_at
                    )
                    SELECT %s, id, 'wechat_openid', %s, %s::jsonb, %s, %s
                    FROM target_user
                    ON CONFLICT (provider, provider_subject) DO UPDATE SET
                        profile_json = EXCLUDED.profile_json,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        normalized_openid,
                        user_id,
                        now,
                        now,
                        openid_identity_id,
                        normalized_openid,
                        json_param(profile),
                        now,
                        now,
                    ),
                )
                if normalized_unionid:
                    cur.execute(
                        """
                        INSERT INTO identity.user_identities (
                            id, user_id, provider, provider_subject, profile_json, created_at, updated_at
                        )
                        SELECT %s, user_id, 'wechat_unionid', %s, %s::jsonb, %s, %s
                        FROM identity.user_identities
                        WHERE provider = 'wechat_openid' AND provider_subject = %s
                        ON CONFLICT (provider, provider_subject) DO UPDATE SET
                            profile_json = EXCLUDED.profile_json,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            unionid_identity_id,
                            normalized_unionid,
                            json_param({"unionid": normalized_unionid}),
                            now,
                            now,
                            normalized_openid,
                        ),
                    )
                cur.execute(
                    """
                    SELECT u.id,
                           openid.provider_subject AS openid,
                           COALESCE(unionid.provider_subject, '') AS unionid,
                           u.display_name,
                           COALESCE(openid.profile_json->>'avatarUrl', '') AS avatar_url,
                           u.created_at,
                           u.updated_at
                    FROM identity.users u
                    JOIN identity.user_identities openid
                        ON openid.user_id = u.id AND openid.provider = 'wechat_openid'
                    LEFT JOIN identity.user_identities unionid
                        ON unionid.user_id = u.id AND unionid.provider = 'wechat_unionid'
                    WHERE openid.provider_subject = %s
                    """,
                    (normalized_openid,),
                )
                return _public_user_from_pg_row(cur.fetchone())

    def create_auth_token(self, user_id, token=None, issued_at="", expires_at=""):
        access_token = token or f"wow_{secrets.token_urlsafe(32)}"
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO identity.auth_tokens (
                        token_hash, user_id, issued_at, expires_at, metadata_json
                    ) VALUES (%s, %s, %s, %s, '{}'::jsonb)
                    """,
                    (auth_token_hash(access_token), user_id, issued_at, expires_at),
                )
        return access_token

    def authenticate_token(self, token, now):
        if not token:
            return None
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.id,
                           openid.provider_subject AS openid,
                           COALESCE(unionid.provider_subject, '') AS unionid,
                           u.display_name,
                           COALESCE(openid.profile_json->>'avatarUrl', '') AS avatar_url,
                           u.created_at,
                           u.updated_at
                    FROM identity.auth_tokens t
                    JOIN identity.users u ON u.id = t.user_id
                    LEFT JOIN identity.user_identities openid
                        ON openid.user_id = u.id AND openid.provider = 'wechat_openid'
                    LEFT JOIN identity.user_identities unionid
                        ON unionid.user_id = u.id AND unionid.provider = 'wechat_unionid'
                    WHERE t.token_hash = %s
                      AND t.expires_at > %s
                      AND t.revoked_at IS NULL
                    """,
                    (auth_token_hash(token), now),
                )
                return _public_user_from_pg_row(cur.fetchone())

    def update_user_profile(self, user_id, nickname, avatar_url, now):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE identity.users
                    SET display_name = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (nickname, now, user_id),
                )
                cur.execute(
                    """
                    UPDATE identity.user_identities
                    SET profile_json = profile_json || jsonb_build_object('avatarUrl', %s::text),
                        updated_at = %s
                    WHERE user_id = %s AND provider = 'wechat_openid'
                    """,
                    (avatar_url, now, user_id),
                )
                cur.execute(
                    """
                    SELECT u.id,
                           openid.provider_subject AS openid,
                           COALESCE(unionid.provider_subject, '') AS unionid,
                           u.display_name,
                           COALESCE(openid.profile_json->>'avatarUrl', '') AS avatar_url,
                           u.created_at,
                           u.updated_at
                    FROM identity.users u
                    JOIN identity.user_identities openid
                        ON openid.user_id = u.id AND openid.provider = 'wechat_openid'
                    LEFT JOIN identity.user_identities unionid
                        ON unionid.user_id = u.id AND unionid.provider = 'wechat_unionid'
                    WHERE u.id = %s
                    """,
                    (user_id,),
                )
                return _public_user_from_pg_row(cur.fetchone())

    def save_build_template(self, user_id, normalized):
        template_id = str(uuid.uuid4())
        payload = {
            "clientId": normalized["client_id"],
            "title": normalized["title"],
            "classKey": normalized["class_key"],
            "className": normalized["class_name"],
            "specKey": normalized["spec_key"],
            "specName": normalized["spec_name"],
            "heroKey": normalized["hero_key"],
            "heroLabel": normalized["hero_label"],
            "scenarioKey": normalized["scenario_key"],
            "scenarioTitle": normalized["scenario_title"],
            "rawString": normalized["raw_string"],
            "simcLines": _json_value(normalized["simc_lines_json"], []),
            "status": normalized["status"],
            "statusLabel": normalized["status_label"],
            "source": normalized["source"],
            "schemaVersion": normalized["schema_version"],
        }
        metadata = _json_value(normalized["metadata_json"], {})
        config_hash = build_template_config_hash(normalized["template_type"], normalized["raw_string"])
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO app.build_templates (
                        id, user_id, template_type, name, payload_json, metadata_json,
                        config_hash, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s)
                    ON CONFLICT (user_id, template_type, config_hash) DO UPDATE SET
                        name = EXCLUDED.name,
                        payload_json = EXCLUDED.payload_json,
                        metadata_json = EXCLUDED.metadata_json,
                        updated_at = EXCLUDED.updated_at
                    RETURNING
                        id,
                        payload_json->>'clientId',
                        template_type,
                        name,
                        payload_json->>'classKey',
                        payload_json->>'className',
                        payload_json->>'specKey',
                        payload_json->>'specName',
                        payload_json->>'heroKey',
                        payload_json->>'heroLabel',
                        payload_json->>'scenarioKey',
                        payload_json->>'scenarioTitle',
                        payload_json->>'rawString',
                        payload_json->'simcLines',
                        payload_json->>'status',
                        payload_json->>'statusLabel',
                        payload_json->>'source',
                        metadata_json,
                        COALESCE((payload_json->>'schemaVersion')::integer, 1),
                        created_at,
                        updated_at
                    """,
                    (
                        template_id,
                        user_id,
                        normalized["template_type"],
                        normalized["title"],
                        json_param(payload),
                        json_param(metadata),
                        config_hash,
                        normalized["created_at"],
                        normalized["updated_at"],
                    ),
                )
                return _public_build_template_from_pg_row(cur.fetchone())

    def list_build_templates(self, user_id, template_type=""):
        params = [user_id]
        type_clause = ""
        if template_type:
            type_clause = "AND template_type = %s"
            params.append(template_type)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        id,
                        payload_json->>'clientId',
                        template_type,
                        name,
                        payload_json->>'classKey',
                        payload_json->>'className',
                        payload_json->>'specKey',
                        payload_json->>'specName',
                        payload_json->>'heroKey',
                        payload_json->>'heroLabel',
                        payload_json->>'scenarioKey',
                        payload_json->>'scenarioTitle',
                        payload_json->>'rawString',
                        payload_json->'simcLines',
                        payload_json->>'status',
                        payload_json->>'statusLabel',
                        payload_json->>'source',
                        metadata_json,
                        COALESCE((payload_json->>'schemaVersion')::integer, 1),
                        created_at,
                        updated_at
                    FROM app.build_templates
                    WHERE user_id = %s {type_clause}
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT 200
                    """,
                    tuple(params),
                )
                return [_public_build_template_from_pg_row(row) for row in cur.fetchall()]

    def delete_build_template(self, user_id, template_id):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM app.build_templates
                    WHERE user_id = %s AND id = %s
                    RETURNING id
                    """,
                    (user_id, template_id),
                )
                row = cur.fetchone()
        if not row:
            raise KeyError("build template not found")
        return {"id": str(row[0]), "deleted": True}

    def insert_simulator_task(self, task):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO app.simulator_tasks (
                        id, user_id, mode, status, request_json, analysis_json, summary_json,
                        queued_at, started_at, finished_at, attempt, locked_by, heartbeat_at,
                        cancel_requested, last_error, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        task["id"],
                        task["user_id"],
                        task["mode"],
                        task["status"],
                        json_param(task.get("request_json")),
                        json_param(task.get("analysis_json")),
                        json_param(task.get("summary_json")),
                        task.get("queued_at"),
                        task.get("started_at"),
                        task.get("finished_at"),
                        task.get("attempt", 0),
                        task.get("locked_by", ""),
                        task.get("heartbeat_at"),
                        bool(task.get("cancel_requested", False)),
                        task.get("last_error", ""),
                        task.get("created_at"),
                        task.get("updated_at"),
                    ),
                )

    def list_simulator_task_rows(self, user_id):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, mode, status, request_json, analysis_json, summary_json, created_at, updated_at
                    FROM app.simulator_tasks
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 50
                    """,
                    (user_id,),
                )
                return cur.fetchall()

    def active_simulator_task_rows(self, user_id):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, status, request_json, analysis_json, created_at, updated_at
                    FROM app.simulator_tasks
                    WHERE user_id = %s AND mode = 'simcraft_template' AND status IN ('queued', 'running')
                    ORDER BY created_at DESC
                    LIMIT 20
                    """,
                    (user_id,),
                )
                return cur.fetchall()

    def get_simulator_task_row(self, user_id, task_id):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, mode, status, request_json, analysis_json, created_at, updated_at
                    FROM app.simulator_tasks
                    WHERE user_id = %s AND id = %s
                    """,
                    (user_id, task_id),
                )
                return cur.fetchone()

    def get_simcraft_template_task_for_runner(self, task_id):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id, mode, status, request_json, analysis_json, created_at, updated_at
                    FROM app.simulator_tasks
                    WHERE id = %s AND mode = 'simcraft_template'
                    """,
                    (task_id,),
                )
                return cur.fetchone()

    def mark_simcraft_template_task_running(self, task_id, running_analysis, running_summary, started_at):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE app.simulator_tasks
                    SET status = 'running',
                        analysis_json = %s::jsonb,
                        summary_json = %s::jsonb,
                        started_at = %s,
                        attempt = attempt + 1,
                        updated_at = %s
                    WHERE id = %s AND mode = 'simcraft_template'
                    """,
                    (
                        json_param(running_analysis),
                        json_param(running_summary),
                        started_at,
                        started_at,
                        task_id,
                    ),
                )

    def finish_simcraft_template_task(
        self,
        task_id,
        final_status,
        analysis,
        final_summary,
        finished_at,
        final_error="",
    ):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE app.simulator_tasks
                    SET status = %s,
                        analysis_json = %s::jsonb,
                        summary_json = %s::jsonb,
                        finished_at = %s,
                        last_error = %s,
                        updated_at = %s
                    WHERE id = %s AND mode = 'simcraft_template'
                    """,
                    (
                        final_status,
                        json_param(analysis),
                        json_param(final_summary),
                        finished_at,
                        final_error,
                        finished_at,
                        task_id,
                    ),
                )

    def find_wechat_user_by_openid(self, openid):
        normalized_openid = str(openid or "").strip()
        if not normalized_openid:
            return None
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.id,
                           openid.provider_subject AS openid,
                           COALESCE(unionid.provider_subject, '') AS unionid,
                           u.display_name,
                           COALESCE(openid.profile_json->>'avatarUrl', '') AS avatar_url,
                           u.created_at,
                           u.updated_at
                    FROM identity.user_identities openid
                    JOIN identity.users u ON u.id = openid.user_id
                    LEFT JOIN identity.user_identities unionid
                        ON unionid.user_id = u.id AND unionid.provider = 'wechat_unionid'
                    WHERE openid.provider = 'wechat_openid'
                      AND openid.provider_subject = %s
                    """,
                    (normalized_openid,),
                )
                return _public_user_from_pg_row(cur.fetchone())

    def load_chickenbro_user_profile(self, user_id):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT summary_json
                    FROM knowledge.user_context_summaries
                    WHERE user_id = %s AND context_type = %s
                    """,
                    (user_id, "chickenbro_user_profile"),
                )
                row = cur.fetchone()
        return _json_value(row[0], {}) if row else {}

    def upsert_chickenbro_user_profile(self, user_id, profile, now):
        profile_id = str(uuid.uuid5(IDENTITY_NAMESPACE, f"knowledge.user_context_summaries:{user_id}:chickenbro_user_profile"))
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO knowledge.user_context_summaries (
                        id, user_id, context_type, summary_json, source_refs_json, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s::jsonb, '[]'::jsonb,
                        COALESCE(%s::timestamptz, now()), COALESCE(%s::timestamptz, now())
                    )
                    ON CONFLICT (user_id, context_type) DO UPDATE SET
                        summary_json = EXCLUDED.summary_json,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        profile_id,
                        user_id,
                        "chickenbro_user_profile",
                        json_param(profile if isinstance(profile, dict) else {}),
                        now or None,
                        now or None,
                    ),
                )
        return profile if isinstance(profile, dict) else {}

    def create_chickenbro_session(self, user_id, title, product_phase, metadata, now):
        session_id = str(uuid.uuid4())
        context = {
            "productPhase": product_phase or "retail",
            "metadata": metadata if isinstance(metadata, dict) else {},
        }
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO app.chickenbro_sessions (
                        id, user_id, title, status, context_json, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, 'active', %s::jsonb,
                        COALESCE(%s::timestamptz, now()), COALESCE(%s::timestamptz, now())
                    )
                    RETURNING id, user_id, title, status, context_json, created_at, updated_at
                    """,
                    (
                        session_id,
                        user_id,
                        title or "",
                        json_param(context),
                        now or None,
                        now or None,
                    ),
                )
                return _public_chickenbro_session_from_pg_row(cur.fetchone())

    def insert_chickenbro_message(self, user_id, session_id, role, content, payload=None, agent_job_id="", now=""):
        message_id = str(uuid.uuid4())
        payload = payload if isinstance(payload, dict) else {}
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO app.chickenbro_messages (
                        id, session_id, user_id, role, content, payload_json,
                        evidence_refs_json, agent_job_id, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s::jsonb,
                        %s::jsonb, %s, COALESCE(%s::timestamptz, now())
                    )
                    """,
                    (
                        message_id,
                        session_id,
                        user_id,
                        role,
                        str(content or "").strip()[:4000],
                        json_param(payload),
                        json_param(_payload_evidence_refs(payload)),
                        agent_job_id or None,
                        now or None,
                    ),
                )
        return {
            "messageId": message_id,
            "sessionId": session_id,
            "role": role,
            "content": str(content or "").strip()[:4000],
            "payload": payload,
            "agentJobId": agent_job_id or "",
            "createdAt": str(now or ""),
        }

    def insert_agent_job(self, user_id, session_id, request_payload, bounded_context, now):
        job_id = str(uuid.uuid4())
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO app.agent_jobs (
                        id, user_id, session_id, task_id, job_type, status,
                        request_json, bounded_context_json, result_json,
                        queued_at, attempt, locked_by, heartbeat_at, cancel_requested,
                        last_error, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, NULL, 'chickenbro', 'queued',
                        %s::jsonb, %s::jsonb, '{}'::jsonb,
                        COALESCE(%s::timestamptz, now()), 0, '', NULL, false,
                        '', COALESCE(%s::timestamptz, now()), COALESCE(%s::timestamptz, now())
                    )
                    """,
                    (
                        job_id,
                        user_id,
                        session_id,
                        json_param(request_payload if isinstance(request_payload, dict) else {}),
                        json_param(bounded_context if isinstance(bounded_context, dict) else {}),
                        now or None,
                        now or None,
                        now or None,
                    ),
                )
        return job_id

    def insert_chickenbro_agent_trace(
        self,
        user_id,
        session_id,
        user_message_id,
        agent_job_id,
        trace,
        now,
    ):
        payload = validate_chickenbro_agent_trace(trace)
        trace_id = str(uuid.uuid4())
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO app.chickenbro_agent_traces (
                        id, user_id, session_id, user_message_id, agent_job_id,
                        schema_revision, runtime_version, answer_status, payload_json, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
                        COALESCE(%s::timestamptz, now())
                    )
                    ON CONFLICT (agent_job_id) DO NOTHING
                    RETURNING id
                    """,
                    (
                        trace_id,
                        user_id,
                        session_id,
                        user_message_id,
                        agent_job_id,
                        payload["schemaRevision"],
                        payload["runtimeVersion"],
                        payload["answerStatus"],
                        json_param(payload),
                        now or None,
                    ),
                )
                row = cur.fetchone()
                if row:
                    return str(row[0])
                cur.execute(
                    """
                    SELECT id
                    FROM app.chickenbro_agent_traces
                    WHERE user_id = %s AND agent_job_id = %s
                    """,
                    (user_id, agent_job_id),
                )
                row = cur.fetchone()
                if not row:
                    raise PermissionError("chickenbro trace job owner mismatch")
                return str(row[0])

    def get_chickenbro_agent_trace(self, user_id, agent_job_id):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, session_id, user_message_id, agent_job_id, payload_json, created_at
                    FROM app.chickenbro_agent_traces
                    WHERE user_id = %s AND agent_job_id = %s
                    """,
                    (user_id, agent_job_id),
                )
                row = cur.fetchone()
        if not row:
            raise KeyError("chickenbro agent trace not found")
        payload = _json_value(row[4], {})
        return {
            "traceId": str(row[0]),
            "sessionId": str(row[1]),
            "userMessageId": str(row[2]),
            "agentJobId": str(row[3]),
            "payload": payload if isinstance(payload, dict) else {},
            "createdAt": str(row[5]),
        }

    def update_agent_job(
        self,
        user_id,
        job_id,
        status,
        result=None,
        error="",
        started_at=None,
        finished_at=None,
        now="",
    ):
        if status not in CHICKENBRO_JOB_STATUSES:
            raise ValueError(f"unsupported agent job status: {status}")
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE app.agent_jobs
                    SET status = %s,
                        result_json = %s::jsonb,
                        last_error = %s,
                        updated_at = COALESCE(%s::timestamptz, now()),
                        started_at = COALESCE(%s::timestamptz, started_at),
                        finished_at = COALESCE(%s::timestamptz, finished_at)
                    WHERE user_id = %s AND id = %s AND job_type = 'chickenbro'
                    """,
                    (
                        status,
                        json_param(result if isinstance(result, dict) else {}),
                        error or "",
                        now or None,
                        started_at or None,
                        finished_at or None,
                        user_id,
                        job_id,
                    ),
                )

    def touch_chickenbro_session(self, user_id, session_id, updated_at):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE app.chickenbro_sessions
                    SET updated_at = COALESCE(%s::timestamptz, now())
                    WHERE user_id = %s AND id = %s
                    """,
                    (updated_at or None, user_id, session_id),
                )

    def list_chickenbro_sessions(self, user_id, limit, cursor=None):
        cursor = cursor if isinstance(cursor, dict) else None
        where = ["user_id = %s"]
        params = [user_id]
        if cursor:
            where.append("(updated_at < %s::timestamptz OR (updated_at = %s::timestamptz AND id::text < %s))")
            params.extend([cursor.get("updatedAt") or "", cursor.get("updatedAt") or "", cursor.get("sessionId") or ""])
        params.append(int(limit))
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, title,
                           COALESCE(NULLIF(context_json ->> 'productPhase', ''), 'retail') AS product_phase,
                           created_at, updated_at
                    FROM app.chickenbro_sessions
                    WHERE {' AND '.join(where)}
                    ORDER BY updated_at DESC, id DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                rows = cur.fetchall()
        return [_public_chickenbro_session_summary_from_pg_row(row) for row in rows]

    def get_chickenbro_session(self, user_id, session_id):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id, title, status, context_json, created_at, updated_at
                    FROM app.chickenbro_sessions
                    WHERE user_id = %s AND id = %s
                    """,
                    (user_id, session_id),
                )
                row = cur.fetchone()
                if not row:
                    raise KeyError("chickenbro session not found")
                cur.execute(
                    """
                    SELECT id, session_id, user_id, role, content, payload_json, agent_job_id, created_at
                    FROM app.chickenbro_messages
                    WHERE user_id = %s AND session_id = %s
                    ORDER BY created_at
                    """,
                    (user_id, session_id),
                )
                message_rows = cur.fetchall()
        return {
            "session": _public_chickenbro_session_from_pg_row(row),
            "messages": [_public_chickenbro_message_from_pg_row(message_row) for message_row in message_rows],
        }

    def find_chickenbro_message_by_client_id(self, user_id, client_message_id, session_id=""):
        if not client_message_id:
            return None
        where = ["user_id = %s", "role = 'user'", "payload_json ->> 'clientMessageId' = %s"]
        params = [user_id, client_message_id]
        if session_id:
            where.append("session_id = %s")
            params.append(session_id)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, session_id, user_id, role, content, payload_json, agent_job_id, created_at
                    FROM app.chickenbro_messages
                    WHERE {' AND '.join(where)}
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
        return _public_chickenbro_message_from_pg_row(row)

    def find_chickenbro_completed_response_by_client_id(self, user_id, client_message_id, session_id=""):
        if not client_message_id:
            return None
        where = [
            "jobs.user_id = %s",
            "jobs.job_type = 'chickenbro'",
            "jobs.status = 'succeeded'",
            "jobs.request_json ->> 'clientMessageId' = %s",
        ]
        params = [user_id, client_message_id]
        if session_id:
            where.append("jobs.session_id = %s")
            params.append(session_id)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT jobs.id, jobs.user_id, jobs.session_id, jobs.job_type, jobs.status,
                           jobs.request_json, jobs.bounded_context_json, jobs.result_json,
                           jobs.last_error, jobs.created_at, jobs.updated_at, jobs.started_at, jobs.finished_at,
                           messages.id, messages.session_id, messages.user_id, messages.role,
                           messages.content, messages.payload_json, messages.agent_job_id, messages.created_at
                    FROM app.agent_jobs AS jobs
                    JOIN app.chickenbro_messages AS messages
                      ON messages.user_id = jobs.user_id
                     AND messages.agent_job_id = jobs.id
                     AND messages.role = 'assistant'
                    WHERE {' AND '.join(where)}
                    ORDER BY jobs.created_at ASC
                    LIMIT 1
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
        if not row:
            return None
        return {
            "job": _public_chickenbro_job_from_pg_row(row[:13]),
            "assistantMessage": _public_chickenbro_message_from_pg_row(row[13:]),
        }

    def get_chickenbro_job(self, user_id, job_id):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id, session_id, job_type, status, request_json, bounded_context_json,
                           result_json, last_error, created_at, updated_at, started_at, finished_at
                    FROM app.agent_jobs
                    WHERE user_id = %s AND id = %s AND job_type = 'chickenbro'
                    """,
                    (user_id, job_id),
                )
                row = cur.fetchone()
        if not row:
            raise KeyError("agent job not found")
        return _public_chickenbro_job_from_pg_row(row)

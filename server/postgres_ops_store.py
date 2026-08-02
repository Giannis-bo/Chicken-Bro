#!/usr/bin/env python3
from contextlib import contextmanager
import json
import uuid


def json_param(value):
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def _text(value):
    return str(value or "")


def _json_value(value, fallback):
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed is not None else fallback


def _diagnosis_from_row(row):
    return {
        "id": _text(row[0]),
        "targetDomain": _text(row[1]),
        "targetType": _text(row[2]),
        "targetId": _text(row[3]),
        "diagnosis": _text(row[4]),
        "gapType": _text(row[5]),
        "reason": _text(row[6]),
        "note": _text(row[7]),
        "actor": _text(row[8]),
        "targetFingerprint": _text(row[9]),
        "createdAt": _text(row[10]),
        "payload": _json_value(row[11], {}),
        "updatedAt": _text(row[12]),
        "expiresAt": _text(row[13]),
    }


class PostgresOpsStore:
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

    def create_admin_gate_diagnosis(self, entry, audit_payload):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ops.admin_gate_diagnoses (
                        id, target_domain, target_type, target_id, diagnosis, gap_type,
                        reason, note, actor, target_fingerprint, payload_json,
                        created_at, updated_at, expires_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                    """,
                    (
                        entry["id"],
                        entry["targetDomain"],
                        entry["targetType"],
                        entry["targetId"],
                        entry["diagnosis"],
                        entry["gapType"],
                        entry["reason"],
                        entry.get("note", ""),
                        entry.get("actor", ""),
                        entry.get("targetFingerprint", ""),
                        json_param(audit_payload),
                        entry["createdAt"],
                        entry["updatedAt"],
                        entry.get("expiresAt") or None,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO ops.audit_logs (
                        id, actor_user_id, action, target_type, target_id, payload_json, created_at
                    ) VALUES (%s, NULL, %s, %s, %s, %s::jsonb, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        "admin_gate.diagnose",
                        entry["targetType"],
                        entry["targetId"],
                        json_param({"actor": entry.get("actor", ""), "diagnosisId": entry["id"], **audit_payload}),
                        entry["createdAt"],
                    ),
                )
        return {**entry, "payload": audit_payload}

    def list_admin_gate_diagnoses(self):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, target_domain, target_type, target_id, diagnosis, gap_type,
                           reason, note, actor, target_fingerprint, created_at, payload_json,
                           updated_at, COALESCE(expires_at::text, '')
                    FROM ops.admin_gate_diagnoses
                    ORDER BY created_at DESC
                    LIMIT 500
                    """
                )
                rows = cur.fetchall()
        return [_diagnosis_from_row(row) for row in rows]

    def load_active_chickenbro_registry_release(self):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT release.registry_version,
                           release.manifest_refs_json,
                           release.release_hash,
                           release.provenance_json,
                           release.created_at::text,
                           active.activated_at::text
                    FROM ops.chickenbro_tool_registry_active AS active
                    JOIN ops.chickenbro_tool_registry_releases AS release
                      ON release.registry_version = active.registry_version
                    WHERE active.singleton_id = 1
                    """
                )
                release_rows = cur.fetchall()
                if not release_rows:
                    raise KeyError("active chickenbro registry release not found")
                if len(release_rows) > 1:
                    raise RuntimeError("multiple active chickenbro registry releases")
                release_row = release_rows[0]
                cur.execute(
                    """
                    SELECT membership.ordinal, manifest.manifest_json
                    FROM ops.chickenbro_tool_registry_release_manifests AS membership
                    JOIN ops.chickenbro_tool_manifests AS manifest
                      ON manifest.tool_id = membership.tool_id
                     AND manifest.version = membership.version
                     AND manifest.content_hash = membership.content_hash
                    WHERE membership.registry_version = %s
                    ORDER BY membership.ordinal ASC
                    """,
                    (release_row[0],),
                )
                manifest_rows = cur.fetchall()
        return {
            "registryVersion": _text(release_row[0]),
            "manifestRefs": _json_value(release_row[1], []),
            "releaseHash": _text(release_row[2]),
            "status": "active",
            "provenance": _json_value(release_row[3], {}),
            "createdAt": _text(release_row[4]),
            "activatedAt": _text(release_row[5]),
            "manifests": [_json_value(row[1], {}) for row in manifest_rows],
        }

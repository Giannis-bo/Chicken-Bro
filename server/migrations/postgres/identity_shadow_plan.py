#!/usr/bin/env python3
import json
import sqlite3
import sys
import uuid
from pathlib import Path


SCHEMA_REVISION = "postgres-identity-shadow-plan-v1"
PG_NAMESPACE = uuid.UUID("b8589a4f-2d8f-4d34-82a8-f2f29d3e7ed6")
GUEST_OPENID_PREFIX = "guest-simulator-"
GUEST_OPENID_EXACT = "guest-simulator"
OWNER_TABLES = (
    "user_build_templates",
    "simulator_tasks",
    "chickenbro_sessions",
    "chickenbro_messages",
    "agent_jobs",
    "chickenbro_user_profiles",
)


def stable_pg_uuid(scope, value):
    return str(uuid.uuid5(PG_NAMESPACE, f"{scope}:{value}"))


def is_guest_openid(openid):
    normalized = str(openid or "")
    return normalized == GUEST_OPENID_EXACT or normalized.startswith(GUEST_OPENID_PREFIX)


def table_exists(conn, table_name):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return bool(row)


def load_legacy_users(conn):
    rows = conn.execute(
        """
        SELECT id, openid, unionid, nickname, avatar_url, created_at, updated_at
        FROM wechat_users
        ORDER BY id
        """
    ).fetchall()
    users = []
    guest_users = []
    formal_ids = set()
    guest_ids = set()
    for row in rows:
        record = {
            "sqliteUserId": row[0],
            "openid": row[1],
            "unionid": row[2],
            "nickname": row[3],
            "avatarUrl": row[4],
            "createdAt": row[5],
            "updatedAt": row[6],
        }
        if is_guest_openid(row[1]):
            guest_users.append(record)
            guest_ids.add(row[0])
        else:
            users.append(record)
            formal_ids.add(row[0])
    return users, guest_users, formal_ids, guest_ids


def build_user_rows(legacy_users):
    users = []
    identities = []
    for user in legacy_users:
        sqlite_user_id = user["sqliteUserId"]
        pg_user_id = stable_pg_uuid("identity.users", f"wechat_users:{sqlite_user_id}")
        users.append(
            {
                "sqliteUserId": sqlite_user_id,
                "pgUserId": pg_user_id,
                "displayName": user["nickname"],
                "status": "active",
                "createdAt": user["createdAt"],
                "updatedAt": user["updatedAt"],
            }
        )
        if user["openid"]:
            identities.append(
                {
                    "sqliteUserId": sqlite_user_id,
                    "pgIdentityId": stable_pg_uuid("identity.user_identities", f"wechat_openid:{user['openid']}"),
                    "pgUserId": pg_user_id,
                    "provider": "wechat_openid",
                    "providerSubject": user["openid"],
                    "profile": {
                        "avatarUrl": user["avatarUrl"],
                        "nickname": user["nickname"],
                    },
                }
            )
        if user["unionid"]:
            identities.append(
                {
                    "sqliteUserId": sqlite_user_id,
                    "pgIdentityId": stable_pg_uuid("identity.user_identities", f"wechat_unionid:{user['unionid']}"),
                    "pgUserId": pg_user_id,
                    "provider": "wechat_unionid",
                    "providerSubject": user["unionid"],
                    "profile": {},
                }
            )
    return users, identities


def count_auth_tokens(conn):
    if not table_exists(conn, "auth_tokens"):
        return 0
    return conn.execute("SELECT COUNT(*) FROM auth_tokens").fetchone()[0]


def owner_table_counts(conn, formal_ids, guest_ids):
    counts = {}
    guest_owned_rows = 0
    formal_placeholders = ",".join("?" for _ in formal_ids)
    guest_placeholders = ",".join("?" for _ in guest_ids)
    for table in OWNER_TABLES:
        if not table_exists(conn, table):
            counts[table] = {
                "totalRows": 0,
                "formalRows": 0,
                "guestRows": 0,
                "migratableRows": 0,
            }
            continue
        total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        formal = 0
        guest = 0
        if formal_ids:
            formal = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE user_id IN ({formal_placeholders})",
                tuple(sorted(formal_ids)),
            ).fetchone()[0]
        if guest_ids:
            guest = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE user_id IN ({guest_placeholders})",
                tuple(sorted(guest_ids)),
            ).fetchone()[0]
        guest_owned_rows += guest
        counts[table] = {
            "totalRows": total,
            "formalRows": formal,
            "guestRows": guest,
            "migratableRows": formal,
        }
    return counts, guest_owned_rows


def build_identity_shadow_plan(conn):
    legacy_users, guest_users, formal_ids, guest_ids = load_legacy_users(conn)
    users, identities = build_user_rows(legacy_users)
    owner_counts, guest_owned_rows = owner_table_counts(conn, formal_ids, guest_ids)
    return {
        "schemaRevision": SCHEMA_REVISION,
        "users": users,
        "userIdentities": identities,
        "ownerTables": owner_counts,
        "skipped": {
            "guestUsers": [
                {
                    "sqliteUserId": user["sqliteUserId"],
                    "openid": user["openid"],
                    "reason": "guest_identity_not_migrated",
                }
                for user in guest_users
            ],
            "guestOwnedRows": guest_owned_rows,
            "authTokens": count_auth_tokens(conn),
            "authTokenReason": "legacy_tokens_not_migrated",
        },
        "totals": {
            "formalUsers": len(users),
            "guestUsers": len(guest_users),
            "userIdentities": len(identities),
            "migratableOwnerRows": sum(item["migratableRows"] for item in owner_counts.values()),
        },
        "errors": [],
    }


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) != 1:
        print("usage: identity_shadow_plan.py path/to/wow_news.sqlite3", file=sys.stderr)
        return 2
    db_path = Path(argv[0])
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        plan = build_identity_shadow_plan(conn)
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

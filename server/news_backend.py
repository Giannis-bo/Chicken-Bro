#!/usr/bin/env python3
import hashlib
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen

try:
    from .news_collector import canonical_article_key, collect_feed_articles, merge_articles
    from .news_translator import localize_article, visible_translation_issues
    from .simulator_payload import analyze_simulator_request, build_simulator_home_payload
except ImportError:
    from news_collector import canonical_article_key, collect_feed_articles, merge_articles
    from news_translator import localize_article, visible_translation_issues
    from simulator_payload import analyze_simulator_request, build_simulator_home_payload

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
SEED_PATH = BASE_DIR / "news" / "articles.seed.json"
DB_PATH = Path(os.environ.get("WOW_NEWS_DB", BASE_DIR / "data" / "wow_news.sqlite3"))
HOST = os.environ.get("WOW_NEWS_HOST", "0.0.0.0")
PORT = int(os.environ.get("WOW_NEWS_PORT", "8787"))
ENABLE_COLLECTORS = os.environ.get("WOW_NEWS_ENABLE_COLLECTORS", "0") == "1"
PUBLIC_REFRESH_MODES = {"manual", "scheduled"}
AUTH_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60
GUEST_SIMULATOR_OPENID = "guest-simulator"

CHANNELS = [
    {"id": "retail", "title": "正式服动态", "desc": "官方公告、热修、活动与正式服版本内容"},
    {"id": "ptr", "title": "测试服前瞻", "desc": "PTR / Beta 改动、前瞻与开发说明"},
    {"id": "class", "title": "职业强度变化", "desc": "职业调优、套装修正与强度趋势"},
]

TRUSTED_SOURCES = {
    "Blizzard News": {"worldofwarcraft.blizzard.com", "news.blizzard.com"},
    "Wowhead": {"www.wowhead.com"},
    "Icy Veins": {"www.icy-veins.com"},
}

FEED_SOURCES = [
    {
        "type": "blizzard_html",
        "sourceName": "Blizzard News",
        "sourceUrl": "https://worldofwarcraft.blizzard.com/en-us/news",
        "sourceNote": "Blizzard official World of Warcraft news listing.",
        "baseImportance": 86,
    },
]


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def int_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


@contextmanager
def db_connection():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news_articles (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                channel TEXT NOT NULL,
                category TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                importance INTEGER NOT NULL,
                source_name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                published_at TEXT NOT NULL,
                source_note TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        ensure_article_columns(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news_refresh_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                refresh_mode TEXT NOT NULL,
                refreshed_at TEXT NOT NULL,
                accepted_count INTEGER NOT NULL,
                rejected_count INTEGER NOT NULL,
                message TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wechat_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                openid TEXT NOT NULL UNIQUE,
                unionid TEXT NOT NULL DEFAULT '',
                nickname TEXT NOT NULL DEFAULT '',
                avatar_url TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES wechat_users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS simulator_tasks (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                request_json TEXT NOT NULL,
                analysis_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES wechat_users(id)
            )
            """
        )
        ensure_auth_token_columns(conn)
        prune_expired_auth_tokens(conn)


def ensure_article_columns(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(news_articles)").fetchall()}
    for name in ("body_zh", "original_title", "original_summary", "original_body"):
        if name not in columns:
            conn.execute(f"ALTER TABLE news_articles ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")


def ensure_auth_token_columns(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(auth_tokens)").fetchall()}
    if "expires_at" not in columns:
        conn.execute("ALTER TABLE auth_tokens ADD COLUMN expires_at TEXT NOT NULL DEFAULT ''")
    conn.execute(
        "UPDATE auth_tokens SET expires_at = ? WHERE expires_at = ''",
        (auth_token_expires_at(),),
    )


def auth_token_expires_at():
    return (datetime.now(timezone.utc) + timedelta(seconds=AUTH_TOKEN_TTL_SECONDS)).isoformat(timespec="seconds")


def auth_expires_at_ms(expires_at):
    try:
        return int(datetime.fromisoformat(expires_at).timestamp() * 1000)
    except (TypeError, ValueError):
        return 0


def prune_expired_auth_tokens(conn):
    conn.execute("DELETE FROM auth_tokens WHERE expires_at <= ?", (utc_now(),))


def load_seed_articles():
    with SEED_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def hostname_for(url):
    parsed = urlparse(url or "")
    return parsed.hostname or ""


def is_valid_article(article):
    if article.get("channel") not in {channel["title"] for channel in CHANNELS}:
        return False
    source_name = article.get("sourceName")
    if hostname_for(article.get("sourceUrl")) not in TRUSTED_SOURCES.get(source_name, set()):
        return False
    required = ["id", "title", "summary", "sourceName", "sourceUrl", "publishedAt", "sourceNote"]
    return all(article.get(key) for key in required)


def normalize_refresh_mode(value):
    return value if value in PUBLIC_REFRESH_MODES else None


def refresh_articles(refresh_mode):
    init_db()
    seed_articles = load_seed_articles()
    collected_articles = []
    collector_errors = []
    if ENABLE_COLLECTORS:
        collected_articles, collector_errors = collect_feed_articles(FEED_SOURCES)

    accepted = []
    rejected = 0
    for article in merge_articles(seed_articles, collected_articles):
        localized_article = localize_article(article)
        if is_valid_article(localized_article):
            accepted.append(localized_article)
        else:
            rejected += 1

    refreshed_at = utc_now()
    accepted_ids = [article["id"] for article in accepted]
    translation_issues = visible_translation_issues(accepted)
    with db_connection() as conn:
        for article in accepted:
            conn.execute(
                """
                INSERT INTO news_articles (
                    id, title, summary, channel, category, tags_json, importance,
                    source_name, source_url, published_at, source_note,
                    body_zh, original_title, original_summary, original_body, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    summary=excluded.summary,
                    channel=excluded.channel,
                    category=excluded.category,
                    tags_json=excluded.tags_json,
                    importance=excluded.importance,
                    source_name=excluded.source_name,
                    source_url=excluded.source_url,
                    published_at=excluded.published_at,
                    source_note=excluded.source_note,
                    body_zh=excluded.body_zh,
                    original_title=excluded.original_title,
                    original_summary=excluded.original_summary,
                    original_body=excluded.original_body,
                    updated_at=excluded.updated_at
                """,
                (
                    article["id"],
                    article["title"],
                    article["summary"],
                    article["channel"],
                    article["category"],
                    json.dumps(article.get("tags", []), ensure_ascii=False),
                    int(article.get("importance", 0)),
                    article["sourceName"],
                    article["sourceUrl"],
                    article["publishedAt"],
                    article["sourceNote"],
                    article.get("bodyZh", ""),
                    article.get("originalTitle", ""),
                    article.get("originalSummary", ""),
                    article.get("originalBody", ""),
                    refreshed_at,
                ),
            )
        if accepted_ids:
            placeholders = ",".join("?" for _ in accepted_ids)
            conn.execute(f"DELETE FROM news_articles WHERE id NOT IN ({placeholders})", accepted_ids)
        conn.execute(
            """
            INSERT INTO news_refresh_runs (refresh_mode, refreshed_at, accepted_count, rejected_count, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                refresh_mode,
                refreshed_at,
                len(accepted),
                rejected,
                json.dumps(
                    {
                        "seedCount": len(seed_articles),
                        "collectorEnabled": ENABLE_COLLECTORS,
                        "collectedCount": len(collected_articles),
                        "collectorErrors": collector_errors,
                        "translationIssueCount": len(translation_issues),
                        "translationIssues": translation_issues[:20],
                    },
                    ensure_ascii=False,
                ),
            ),
        )
    return {"refreshMode": refresh_mode, "lastRefreshedAt": refreshed_at}


def latest_refresh_state():
    init_db()
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT refresh_mode, refreshed_at FROM news_refresh_runs
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
    if not row:
        return refresh_articles("bootstrap")
    return {"refreshMode": row[0], "lastRefreshedAt": row[1]}


def latest_refresh_run_payload():
    init_db()
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT refresh_mode, refreshed_at, accepted_count, rejected_count, message
            FROM news_refresh_runs
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
    if not row:
        latest_refresh_state()
        return latest_refresh_run_payload()

    message = safe_json_loads(row[4], {}, "latest news refresh run message")
    return {
        "refreshMode": row[0],
        "refreshedAt": row[1],
        "acceptedCount": row[2],
        "rejectedCount": row[3],
        "collectorEnabled": bool(message.get("collectorEnabled")),
        "collectedCount": int(message.get("collectedCount", 0) or 0),
        "collectorErrors": message.get("collectorErrors", []),
        "translationIssueCount": int(message.get("translationIssueCount", 0) or 0),
        "translationIssues": message.get("translationIssues", []),
    }


def public_user_from_row(row):
    if not row:
        return None
    return {
        "id": row[0],
        "openid": row[1],
        "unionid": row[2],
        "nickname": row[3],
        "avatarUrl": row[4],
        "createdAt": row[5],
        "updatedAt": row[6],
    }


def exchange_wechat_code(code):
    if not code:
        raise ValueError("missing wechat login code")
    appid = os.environ.get("WOW_WECHAT_APPID", "").strip()
    secret = os.environ.get("WOW_WECHAT_SECRET", "").strip()
    if not appid or not secret:
        raise RuntimeError("wechat app credentials are not configured")

    query = urlencode(
        {
            "appid": appid,
            "secret": secret,
            "js_code": code,
            "grant_type": "authorization_code",
        }
    )
    url = f"https://api.weixin.qq.com/sns/jscode2session?{query}"
    with urlopen(url, timeout=int_env("WOW_WECHAT_TIMEOUT_SECONDS", 8)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("errcode"):
        raise RuntimeError(payload.get("errmsg") or f"wechat code2Session failed: {payload['errcode']}")
    if not payload.get("openid"):
        raise RuntimeError("wechat code2Session response did not include openid")
    return payload


def upsert_wechat_user(openid, unionid=""):
    now = utc_now()
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO wechat_users (openid, unionid, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(openid) DO UPDATE SET
                unionid=COALESCE(NULLIF(excluded.unionid, ''), wechat_users.unionid),
                updated_at=excluded.updated_at
            """,
            (openid, unionid or "", now, now),
        )
        row = conn.execute(
            """
            SELECT id, openid, unionid, nickname, avatar_url, created_at, updated_at
            FROM wechat_users WHERE openid = ?
            """,
            (openid,),
        ).fetchone()
    return public_user_from_row(row)


def create_auth_token(user_id):
    token = f"wow_{secrets.token_urlsafe(32)}"
    created_at = utc_now()
    expires_at = auth_token_expires_at()
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO auth_tokens (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, created_at, expires_at),
        )
    return token, expires_at


def login_with_wechat_code(code, exchange_code=exchange_wechat_code):
    payload = exchange_code(code)
    openid = (payload.get("openid") or "").strip()
    if not openid:
        raise ValueError("wechat login did not return openid")

    user = upsert_wechat_user(openid, (payload.get("unionid") or "").strip())
    token, expires_at = create_auth_token(user["id"])
    return {
        "accessToken": token,
        "tokenType": "Bearer",
        "expiresAt": auth_expires_at_ms(expires_at),
        "user": user,
    }


def bearer_token_from_headers(headers):
    authorization = headers.get("Authorization", "") if headers else ""
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def authenticate_token(token):
    if not token:
        return None
    init_db()
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.openid, u.unionid, u.nickname, u.avatar_url, u.created_at, u.updated_at
            FROM auth_tokens t
            JOIN wechat_users u ON u.id = t.user_id
            WHERE t.token = ? AND t.expires_at > ?
            """,
            (token, utc_now()),
        ).fetchone()
    return public_user_from_row(row)


def guest_openid_from_id(guest_id):
    normalized = str(guest_id or "").strip()[:128]
    if not normalized:
        return ""
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
    return f"{GUEST_SIMULATOR_OPENID}-{digest}"


def guest_simulator_user(guest_id=""):
    guest_openid = guest_openid_from_id(guest_id)
    if not guest_openid:
        return None
    return upsert_wechat_user(guest_openid)


def find_guest_simulator_user(guest_id=""):
    guest_openid = guest_openid_from_id(guest_id)
    if not guest_openid:
        return None
    init_db()
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT id, openid, unionid, nickname, avatar_url, created_at, updated_at
            FROM wechat_users WHERE openid = ?
            """,
            (guest_openid,),
        ).fetchone()
    return public_user_from_row(row)


def clean_text(value, limit):
    return str(value or "").strip()[:limit]


def safe_json_loads(value, fallback, label):
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError) as error:
        print(f"warning: failed to decode {label}: {error}", file=sys.stderr)
        return fallback


def update_user_profile(access_token, profile):
    user = authenticate_token(access_token)
    if not user:
        raise PermissionError("invalid auth token")

    nickname = clean_text(profile.get("nickname"), 64)
    avatar_url = clean_text(profile.get("avatarUrl") or profile.get("avatar_url"), 500)
    now = utc_now()
    with db_connection() as conn:
        conn.execute(
            """
            UPDATE wechat_users
            SET nickname = ?, avatar_url = ?, updated_at = ?
            WHERE id = ?
            """,
            (nickname, avatar_url, now, user["id"]),
        )
        row = conn.execute(
            """
            SELECT id, openid, unionid, nickname, avatar_url, created_at, updated_at
            FROM wechat_users WHERE id = ?
            """,
            (user["id"],),
        ).fetchone()
    return public_user_from_row(row)


def analyze_and_store_simulator_task(request_data, access_token=""):
    request_payload = dict(request_data or {})
    analysis = analyze_simulator_request(request_payload)
    user = authenticate_token(access_token)
    if not user and request_payload.get("saveTask"):
        user = guest_simulator_user(request_payload.get("guestId"))
    if not user:
        return analysis

    task_id = uuid.uuid4().hex
    now = utc_now()
    stored_request = dict(request_payload)
    stored_request.pop("guestId", None)
    analysis = dict(analysis)
    analysis["taskId"] = task_id
    analysis["owner"] = {
        "id": user["id"],
        "openid": user["openid"],
        "nickname": user["nickname"],
        "avatarUrl": user["avatarUrl"],
    }
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO simulator_tasks (
                id, user_id, mode, status, request_json, analysis_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                user["id"],
                analysis.get("mode", ""),
                analysis.get("status", ""),
                json.dumps(stored_request, ensure_ascii=False),
                json.dumps(analysis, ensure_ascii=False),
                now,
                now,
            ),
        )
    return analysis


def list_simulator_tasks(access_token, allow_guest=False, guest_id=""):
    user = authenticate_token(access_token)
    if not user and allow_guest:
        user = find_guest_simulator_user(guest_id)
    if not user:
        raise PermissionError("invalid auth token")

    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, mode, status, request_json, analysis_json, created_at, updated_at
            FROM simulator_tasks
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (user["id"],),
        ).fetchall()
    tasks = []
    for row in rows:
        request_payload = safe_json_loads(row[3], {}, f"simulator task request {row[0]}")
        analysis_payload = safe_json_loads(row[4], {}, f"simulator task analysis {row[0]}")
        question = (
            request_payload.get("question")
            or request_payload.get("prompt")
            or request_payload.get("message")
            or ""
        )
        tasks.append(
            {
                "taskId": row[0],
                "mode": row[1],
                "status": row[2],
                "question": question,
                "recommendations": analysis_payload.get("recommendations", []),
                "createdAt": row[5],
                "updatedAt": row[6],
            }
        )
    return {"user": user, "tasks": tasks}


def get_simulator_task(access_token, task_id, allow_guest=False, guest_id=""):
    user = authenticate_token(access_token)
    if not user and allow_guest:
        user = find_guest_simulator_user(guest_id)
    if not user:
        raise PermissionError("invalid auth token")

    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT id, mode, status, request_json, analysis_json, created_at, updated_at
            FROM simulator_tasks
            WHERE user_id = ? AND id = ?
            """,
            (user["id"], task_id),
        ).fetchone()
    if not row:
        raise KeyError("simulator task not found")

    request_payload = safe_json_loads(row[3], {}, f"simulator task request {row[0]}")
    analysis_payload = safe_json_loads(row[4], {}, f"simulator task analysis {row[0]}")
    question = (
        request_payload.get("question")
        or request_payload.get("prompt")
        or request_payload.get("message")
        or ""
    )
    return {
        "user": user,
        "task": {
            "taskId": row[0],
            "mode": row[1],
            "status": row[2],
            "question": question,
            "recommendations": analysis_payload.get("recommendations", []),
            "request": request_payload,
            "analysis": analysis_payload,
            "createdAt": row[5],
            "updatedAt": row[6],
        },
    }


def load_articles():
    init_db()
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, summary, channel, category, tags_json, importance,
                   source_name, source_url, published_at, source_note,
                   body_zh, original_title, original_summary, original_body
            FROM news_articles
            ORDER BY importance DESC, published_at DESC
            """
        ).fetchall()
    if not rows:
        refresh_articles("bootstrap")
        return load_articles()
    articles = []
    for row in rows:
        articles.append(
            {
                "id": row[0],
                "title": row[1],
                "summary": row[2],
                "channel": row[3],
                "category": row[4],
                "tags": json.loads(row[5]),
                "importance": row[6],
                "sourceName": row[7],
                "sourceUrl": row[8],
                "publishedAt": row[9],
                "sourceNote": row[10],
                "bodyZh": row[11],
                "originalTitle": row[12],
                "originalSummary": row[13],
                "originalBody": row[14],
            }
        )
    return articles


def dedupe_articles(articles):
    by_key = {}
    for article in articles:
        key = canonical_article_key(article)
        current = by_key.get(key)
        if not current or (article.get("importance", 0), article.get("publishedAt", "")) > (current.get("importance", 0), current.get("publishedAt", "")):
            by_key[key] = article
    return sorted(
        by_key.values(),
        key=lambda item: (item.get("importance", 0), item.get("publishedAt", "")),
        reverse=True,
    )


def row_to_article(row):
    return {
        "id": row[0],
        "title": row[1],
        "summary": row[2],
        "channel": row[3],
        "category": row[4],
        "tags": json.loads(row[5]),
        "importance": row[6],
        "sourceName": row[7],
        "sourceUrl": row[8],
        "publishedAt": row[9],
        "sourceNote": row[10],
        "bodyZh": row[11],
        "originalTitle": row[12],
        "originalSummary": row[13],
        "originalBody": row[14],
    }


def get_article_detail(article_id):
    init_db()
    if not article_id:
        return None
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT id, title, summary, channel, category, tags_json, importance,
                   source_name, source_url, published_at, source_note,
                   body_zh, original_title, original_summary, original_body
            FROM news_articles
            WHERE id = ?
            """,
            (article_id,),
        ).fetchone()
    if not row:
        return None
    article = row_to_article(row)
    if not is_valid_article(article):
        return None
    return article


def count_by_tag(articles, tag):
    return sum(1 for article in articles if tag in article.get("tags", []))


def article_list_title(query):
    if query.get("type") == "channel":
        return query.get("value") or "资讯列表"
    key = query.get("key")
    if key == "class-change":
        return "职业变动"
    if key == "ptr":
        return "测试服重点"
    return "今日更新"


def filter_articles(articles, query):
    if query.get("type") == "channel":
        return [article for article in articles if article.get("channel") == query.get("value")]
    key = query.get("key")
    if key == "class-change":
        return [article for article in articles if "class-change" in article.get("tags", [])]
    if key == "ptr":
        return [article for article in articles if article.get("channel") == "测试服前瞻"]
    return articles


def build_article_list_payload(query):
    articles = dedupe_articles([article for article in load_articles() if is_valid_article(article)])
    filtered = filter_articles(articles, query)
    return {
        "title": article_list_title(query),
        "type": query.get("type", "metric"),
        "key": query.get("key", ""),
        "value": query.get("value", ""),
        "count": len(filtered),
        "articles": filtered,
    }


def build_home_payload():
    state = latest_refresh_state()
    articles = dedupe_articles([article for article in load_articles() if is_valid_article(article)])
    articles.sort(key=lambda item: (item.get("importance", 0), item.get("publishedAt", "")), reverse=True)
    return {
        "navTitle": "最新资讯",
        "heroNews": articles[:3],
        "metrics": [
            {"key": "today", "value": str(len(articles)), "label": "今日更新"},
            {"key": "class-change", "value": str(count_by_tag(articles, "class-change")), "label": "职业变动"},
            {"key": "ptr", "value": str(sum(1 for article in articles if article.get("channel") == "测试服前瞻")), "label": "测试服重点"},
        ],
        "channels": CHANNELS,
        "highlights": articles[:6],
        "lastRefreshedAt": state["lastRefreshedAt"],
        "refreshMode": state["refreshMode"],
    }


def load_js_payload(module_path, export_name, *args):
    script = """
const modulePath = process.argv[1]
const exportName = process.argv[2]
const args = process.argv.slice(3).map((value) => JSON.parse(value))
const mod = require(modulePath)
const target = mod[exportName]
if (typeof target !== 'function') {
  throw new Error(`Missing export ${exportName}`)
}
const result = target(...args)
process.stdout.write(JSON.stringify(result))
"""
    command = [
        "node",
        "-e",
        script,
        str(PROJECT_DIR / module_path),
        export_name,
        *[json.dumps(arg, ensure_ascii=False) for arg in args],
    ]
    completed = subprocess.run(command, capture_output=True, text=True, cwd=PROJECT_DIR, check=False, timeout=15)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "node payload failed").strip())
    return json.loads(completed.stdout)


def get_builds_home_payload():
    return load_js_payload("server/builds/home-payload.js", "buildSpecializationHomePayload")


def get_builds_intel_payload():
    return load_js_payload("server/builds/home-payload.js", "buildSpecializationIntelPayload")


def get_builds_detail_payload(spec_id):
    return load_js_payload("server/builds/home-payload.js", "getSpecializationDetail", spec_id)


def get_pve_home_payload():
    return load_js_payload("server/pve/home-payload.js", "buildPveHomePayload")


def get_pve_module_payload(module_key):
    return load_js_payload("server/pve/home-payload.js", "getPveModuleDetail", module_key)


def json_response(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json_body(handler):
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    raw_body = handler.rfile.read(length)
    try:
        return json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        json_response(self, 200, {"ok": True})

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            json_response(self, 200, {"ok": True, "service": "wow-backend"})
            return
        if path == "/api/news/home":
            json_response(self, 200, build_home_payload())
            return
        if path == "/api/news/refresh-runs/latest":
            json_response(self, 200, latest_refresh_run_payload())
            return
        if path == "/api/builds/home":
            json_response(self, 200, get_builds_home_payload())
            return
        if path == "/api/builds/intel":
            json_response(self, 200, get_builds_intel_payload())
            return
        if path == "/api/builds/detail":
            query = parse_qs(urlparse(self.path).query)
            detail = get_builds_detail_payload(query.get("id", [""])[0])
            if detail:
                json_response(self, 200, detail)
            else:
                json_response(self, 404, {"error": "specialization_not_found"})
            return
        if path == "/api/pve/home":
            json_response(self, 200, get_pve_home_payload())
            return
        if path == "/api/pve/module":
            query = parse_qs(urlparse(self.path).query)
            json_response(self, 200, get_pve_module_payload(query.get("key", ["teamLadder"])[0]))
            return
        if path == "/api/simulator/home":
            json_response(self, 200, build_simulator_home_payload())
            return
        if path == "/api/simulator/tasks":
            query = parse_qs(urlparse(self.path).query)
            try:
                json_response(
                    self,
                    200,
                    list_simulator_tasks(
                        bearer_token_from_headers(self.headers),
                        allow_guest=query.get("guest", ["0"])[0] == "1",
                        guest_id=query.get("guestId", [""])[0],
                    ),
                )
            except PermissionError:
                json_response(self, 401, {"error": "unauthorized"})
            return
        if path == "/api/simulator/task":
            query = parse_qs(urlparse(self.path).query)
            try:
                json_response(
                    self,
                    200,
                    get_simulator_task(
                        bearer_token_from_headers(self.headers),
                        query.get("id", [""])[0],
                        allow_guest=query.get("guest", ["0"])[0] == "1",
                        guest_id=query.get("guestId", [""])[0],
                    ),
                )
            except PermissionError:
                json_response(self, 401, {"error": "unauthorized"})
            except KeyError:
                json_response(self, 404, {"error": "simulator_task_not_found"})
            return
        if path == "/api/news/article":
            query = parse_qs(urlparse(self.path).query)
            article = get_article_detail(query.get("id", [""])[0])
            if article:
                json_response(self, 200, article)
            else:
                json_response(self, 404, {"error": "article_not_found"})
            return
        if path == "/api/news/list":
            query = parse_qs(urlparse(self.path).query)
            payload = build_article_list_payload({
                "type": query.get("type", ["metric"])[0],
                "key": query.get("key", ["today"])[0],
                "value": query.get("value", [""])[0],
            })
            json_response(self, 200, payload)
            return
        json_response(self, 404, {"error": "not_found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/auth/wechat-login":
            try:
                json_response(self, 200, login_with_wechat_code(read_json_body(self).get("code", "")))
            except (ValueError, RuntimeError) as error:
                json_response(self, 400, {"error": "wechat_login_failed", "message": str(error)})
            return
        if parsed.path == "/api/me/profile":
            try:
                json_response(
                    self,
                    200,
                    update_user_profile(bearer_token_from_headers(self.headers), read_json_body(self)),
                )
            except PermissionError:
                json_response(self, 401, {"error": "unauthorized"})
            return
        if parsed.path == "/api/simulator/analyze":
            json_response(
                self,
                200,
                analyze_and_store_simulator_task(
                    read_json_body(self),
                    access_token=bearer_token_from_headers(self.headers),
                ),
            )
            return
        if parsed.path == "/api/news/refresh":
            query = parse_qs(parsed.query)
            mode = normalize_refresh_mode(query.get("mode", ["manual"])[0])
            if not mode:
                json_response(self, 400, {"error": "invalid_refresh_mode", "allowedModes": sorted(PUBLIC_REFRESH_MODES)})
                return
            try:
                refresh_articles(mode)
                json_response(self, 200, build_home_payload())
            except Exception as error:
                json_response(self, 500, {"error": "refresh_failed", "message": str(error)})
            return
        json_response(self, 404, {"error": "not_found"})

    def log_message(self, format, *args):
        print("%s - %s" % (self.log_date_time_string(), format % args))


def main():
    init_db()
    latest_refresh_state()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"wow-backend listening on {HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()

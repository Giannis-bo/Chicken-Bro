#!/usr/bin/env python3
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    from .news_collector import canonical_article_key, collect_feed_articles, merge_articles
    from .news_translator import localize_article
except ImportError:
    from news_collector import canonical_article_key, collect_feed_articles, merge_articles
    from news_translator import localize_article

BASE_DIR = Path(__file__).resolve().parent
SEED_PATH = BASE_DIR / "news" / "articles.seed.json"
DB_PATH = Path(os.environ.get("WOW_NEWS_DB", BASE_DIR / "data" / "wow_news.sqlite3"))
HOST = os.environ.get("WOW_NEWS_HOST", "0.0.0.0")
PORT = int(os.environ.get("WOW_NEWS_PORT", "8787"))
ENABLE_COLLECTORS = os.environ.get("WOW_NEWS_ENABLE_COLLECTORS", "0") == "1"
PUBLIC_REFRESH_MODES = {"manual", "scheduled"}

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


def ensure_article_columns(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(news_articles)").fetchall()}
    for name in ("body_zh", "original_title", "original_summary", "original_body"):
        if name not in columns:
            conn.execute(f"ALTER TABLE news_articles ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")


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


def json_response(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        json_response(self, 200, {"ok": True})

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            json_response(self, 200, {"ok": True, "service": "wow-news-backend"})
            return
        if path == "/api/news/home":
            json_response(self, 200, build_home_payload())
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
    print(f"wow-news-backend listening on {HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()

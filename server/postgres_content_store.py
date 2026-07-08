#!/usr/bin/env python3
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import re
import uuid


CONTENT_NAMESPACE = uuid.UUID("6b2a62a6-2662-4d4d-82e3-fde04856716f")


def json_param(value):
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def content_uuid(kind, key):
    return str(uuid.uuid5(CONTENT_NAMESPACE, f"{kind}:{key}"))


def _json_value(value, fallback):
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed is not None else fallback


ADMIN_GATE_QUEUE_STATUSES = {
    "partial",
    "stale",
    "blocked",
    "missing_credentials",
    "pending_official_audit",
    "source_reference",
}


def _admin_gate_queue_summary(rows):
    total = 0
    blockers = {}
    for status, row_blockers in rows:
        blocker_values = [str(item or "").strip() for item in (row_blockers or []) if str(item or "").strip()]
        if status not in ADMIN_GATE_QUEUE_STATUSES and not blocker_values:
            continue
        total += 1
        for blocker in blocker_values:
            blockers[blocker] = blockers.get(blocker, 0) + 1
    return {
        "count": total,
        "domainCounts": {"news": total} if total else {},
        "topBlockers": [
            {"reason": reason, "count": count}
            for reason, count in sorted(blockers.items(), key=lambda item: (-item[1], item[0]))[:8]
        ],
    }


def _text(value):
    return str(value or "")


def _timestamp_or_none(value):
    text = _text(value).strip()
    return text or None


def _parse_iso_datetime(value):
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _source_key(article):
    return _text(article.get("sourceId") or article.get("sourceKey") or article.get("sourceName", "").lower().replace(" ", "-"))


def _canonical_topic_id(article):
    existing = _text(article.get("canonicalTopicId"))
    if existing:
        return existing
    url = _text(article.get("sourceUrl"))
    match = re.search(r"/(?:news|article)/(\d+)", url)
    if match:
        return f"news:{match.group(1)}"
    return _text(article.get("id"))


def _article_from_row(row):
    if not row:
        return None
    tags = _json_value(row[5], [])
    tag_items = _json_value(row[15], [])
    source_badges = _json_value(row[21], [])
    body_blocks = _json_value(row[22], [])
    reading_meta = _json_value(row[24], {})
    return {
        "id": _text(row[0]),
        "title": _text(row[1]),
        "summary": _text(row[2]),
        "channel": _text(row[3]),
        "category": _text(row[4]),
        "tags": tags if isinstance(tags, list) else [],
        "importance": int(row[6] or 0),
        "sourceName": _text(row[7]),
        "sourceUrl": _text(row[8]),
        "publishedAt": _text(row[9]),
        "sourceNote": _text(row[10]),
        "bodyZh": _text(row[11]),
        "originalTitle": _text(row[12]),
        "translationStatus": _text(row[13]),
        "contentStatus": _text(row[14]),
        "tagItems": tag_items if isinstance(tag_items, list) else [],
        "blockedReason": _text(row[16]),
        "sourceId": _text(row[17]),
        "sourceTier": _text(row[18]),
        "licenseStatus": _text(row[19]),
        "verificationStatus": _text(row[20]),
        "sourceBadges": source_badges if isinstance(source_badges, list) else [],
        "bodyBlocksZh": body_blocks if isinstance(body_blocks, list) else [],
        "canonicalTopicId": _text(row[23]),
        "readingMeta": reading_meta if isinstance(reading_meta, dict) else {},
        "translationFidelity": _text(row[25]),
    }


def _refresh_payload_from_row(row):
    if not row:
        return None
    message = _json_value(row[4], {})
    if not isinstance(message, dict):
        message = {}
    return {
        "refreshMode": _text(row[0]),
        "refreshedAt": _text(row[1]),
        "acceptedCount": int(row[2] or 0),
        "rejectedCount": int(row[3] or 0),
        "collectorEnabled": bool(message.get("collectorEnabled")),
        "seedEnabled": bool(message.get("seedEnabled", True)),
        "queueEnabled": bool(message.get("queueEnabled", message.get("collectorEnabled"))),
        "collectorLimit": int(message.get("collectorLimit", 0) or 0),
        "discoveryLimit": int(message.get("discoveryLimit", message.get("collectorLimit", 0)) or 0),
        "processLimit": int(message.get("processLimit", 0) or 0),
        "discoveredCount": int(message.get("discoveredCount", message.get("collectedDiscoveredCount", 0)) or 0),
        "queuedCount": int(message.get("queuedCount", 0) or 0),
        "processedCount": int(message.get("processedCount", 0) or 0),
        "publishedCount": int(message.get("publishedCount", message.get("acceptedCount", row[2])) or 0),
        "blockedCount": int(message.get("blockedCount", message.get("blockedArticleCount", 0)) or 0),
        "retryableCount": int(message.get("retryableCount", 0) or 0),
        "oldestBacklogAge": int(message.get("oldestBacklogAge", 0) or 0),
        "sourceCoverage": message.get("sourceCoverage", {}),
        "collectedDiscoveredCount": int(message.get("collectedDiscoveredCount", message.get("collectedCount", 0)) or 0),
        "collectedCount": int(message.get("collectedCount", 0) or 0),
        "collectorDuplicateSeedSkippedCount": int(message.get("collectorDuplicateSeedSkippedCount", 0) or 0),
        "collectorErrors": message.get("collectorErrors", []),
        "sourceFetchErrors": message.get("sourceFetchErrors", message.get("collectorErrors", [])),
        "translationIssueCount": int(message.get("translationIssueCount", 0) or 0),
        "translationIssues": message.get("translationIssues", []),
        "blockedArticleCount": int(message.get("blockedArticleCount", 0) or 0),
        "blockedArticles": message.get("blockedArticles", []),
        "verificationCounts": message.get("verificationCounts", {}),
        "licenseBlockedCount": int(message.get("licenseBlockedCount", 0) or 0),
        "conflictArticles": message.get("conflictArticles", []),
    }


class PostgresContentStore:
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

    def _upsert_source_from_article(self, cur, article, now):
        key = _source_key(article)
        if not key:
            return None
        metadata = {
            "sourceTier": article.get("sourceTier", ""),
            "licenseStatus": article.get("licenseStatus", ""),
        }
        source_id = content_uuid("content.sources", key)
        cur.execute(
            """
            INSERT INTO content.sources (
                id, source_key, name, url, source_type, status, metadata_json, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, 'active', %s::jsonb, %s, %s)
            ON CONFLICT (source_key) DO UPDATE SET
                name = EXCLUDED.name,
                url = EXCLUDED.url,
                source_type = EXCLUDED.source_type,
                metadata_json = content.sources.metadata_json || EXCLUDED.metadata_json,
                updated_at = EXCLUDED.updated_at
            """,
            (
                source_id,
                key,
                article.get("sourceName", "") or key,
                article.get("sourceUrl", ""),
                article.get("sourceTier", ""),
                json_param(metadata),
                now,
                now,
            ),
        )
        return source_id

    def seed_sources(self, sources, now):
        with self.connection() as conn:
            with conn.cursor() as cur:
                for source in sources:
                    key = source.get("sourceId", "")
                    if not key:
                        continue
                    metadata = {
                        "fetchMode": source.get("fetchMode", ""),
                        "retailOnly": bool(source.get("retailOnly")),
                        "licenseStatus": source.get("licenseStatus", ""),
                        "rateLimit": source.get("rateLimit", ""),
                        "enabled": bool(source.get("enabled")),
                        "hostnames": source.get("hostnames", []),
                    }
                    cur.execute(
                        """
                        INSERT INTO content.sources (
                            id, source_key, name, url, source_type, status,
                            metadata_json, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                        ON CONFLICT (source_key) DO UPDATE SET
                            name = EXCLUDED.name,
                            url = EXCLUDED.url,
                            source_type = EXCLUDED.source_type,
                            status = EXCLUDED.status,
                            metadata_json = EXCLUDED.metadata_json,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            content_uuid("content.sources", key),
                            key,
                            source.get("sourceName", ""),
                            source.get("sourceUrl", ""),
                            source.get("tier", ""),
                            "active" if source.get("enabled") else "disabled",
                            json_param(metadata),
                            now,
                            now,
                        ),
                    )

    def persist_news_raw_article(self, article, fetched_at):
        with self.connection() as conn:
            with conn.cursor() as cur:
                source_id = self._upsert_source_from_article(cur, article, fetched_at)
                cur.execute(
                    """
                    INSERT INTO content.raw_articles (
                        id, source_id, source_url, title, summary, body, payload_json,
                        discovered_at, published_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        source_id = EXCLUDED.source_id,
                        source_url = EXCLUDED.source_url,
                        title = EXCLUDED.title,
                        summary = EXCLUDED.summary,
                        body = EXCLUDED.body,
                        payload_json = EXCLUDED.payload_json,
                        published_at = EXCLUDED.published_at,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        article.get("id", ""),
                        source_id,
                        article.get("sourceUrl", ""),
                        article.get("originalTitle") or article.get("title", ""),
                        article.get("originalSummary") or article.get("summary", ""),
                        article.get("originalBody") or article.get("bodyZh", ""),
                        json_param(article),
                        fetched_at,
                        _timestamp_or_none(article.get("publishedAt")),
                        fetched_at,
                    ),
                )

    def persist_news_evidence(self, article, checked_at):
        evidence_key = f"{article.get('id', '')}:{article.get('sourceUrl', '')}:{checked_at}"
        payload = {
            "canonicalTopicId": _canonical_topic_id(article),
            "sourceKey": _source_key(article),
            "sourceName": article.get("sourceName", ""),
            "sourceTier": article.get("sourceTier", ""),
            "evidenceUrl": article.get("sourceUrl", ""),
            "conflictReason": article.get("conflictReason", ""),
        }
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO content.article_evidence (
                        id, article_id, evidence_type, status, payload_json, created_at
                    ) VALUES (%s, %s, 'source_verification', %s, %s::jsonb, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        payload_json = EXCLUDED.payload_json
                    """,
                    (
                        content_uuid("content.article_evidence", evidence_key),
                        article.get("id", ""),
                        article.get("verificationStatus", "") or "pending",
                        json_param(payload),
                        checked_at,
                    ),
                )

    def save_public_article(self, article, updated_at):
        source_key = _source_key(article)
        with self.connection() as conn:
            with conn.cursor() as cur:
                self._upsert_source_from_article(cur, article, updated_at)
                cur.execute(
                    """
                    INSERT INTO content.articles (
                        id, raw_article_id, title, summary, body_zh, channel, category,
                        tags_json, importance, source_name, source_url, source_note,
                        published_at, updated_at, original_title, translation_status,
                        content_status, tag_items_json, blocked_reason, source_key,
                        source_tier, license_status, verification_status, source_badges_json,
                        body_blocks_zh_json, canonical_topic_id, reading_meta_json,
                        translation_fidelity, payload_json
                    ) VALUES (
                        %s, (SELECT id FROM content.raw_articles WHERE id = %s), %s, %s, %s, %s, %s,
                        %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s,
                        %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s, %s::jsonb
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        raw_article_id = EXCLUDED.raw_article_id,
                        title = EXCLUDED.title,
                        summary = EXCLUDED.summary,
                        body_zh = EXCLUDED.body_zh,
                        channel = EXCLUDED.channel,
                        category = EXCLUDED.category,
                        tags_json = EXCLUDED.tags_json,
                        importance = EXCLUDED.importance,
                        source_name = EXCLUDED.source_name,
                        source_url = EXCLUDED.source_url,
                        source_note = EXCLUDED.source_note,
                        published_at = EXCLUDED.published_at,
                        updated_at = EXCLUDED.updated_at,
                        original_title = EXCLUDED.original_title,
                        translation_status = EXCLUDED.translation_status,
                        content_status = EXCLUDED.content_status,
                        tag_items_json = EXCLUDED.tag_items_json,
                        blocked_reason = EXCLUDED.blocked_reason,
                        source_key = EXCLUDED.source_key,
                        source_tier = EXCLUDED.source_tier,
                        license_status = EXCLUDED.license_status,
                        verification_status = EXCLUDED.verification_status,
                        source_badges_json = EXCLUDED.source_badges_json,
                        body_blocks_zh_json = EXCLUDED.body_blocks_zh_json,
                        canonical_topic_id = EXCLUDED.canonical_topic_id,
                        reading_meta_json = EXCLUDED.reading_meta_json,
                        translation_fidelity = EXCLUDED.translation_fidelity,
                        payload_json = EXCLUDED.payload_json
                    """,
                    (
                        article.get("id", ""),
                        article.get("id", ""),
                        article.get("title", ""),
                        article.get("summary", ""),
                        article.get("bodyZh", ""),
                        article.get("channel", ""),
                        article.get("category", ""),
                        json_param(article.get("tags", [])),
                        int(article.get("importance", 0) or 0),
                        article.get("sourceName", ""),
                        article.get("sourceUrl", ""),
                        article.get("sourceNote", ""),
                        _timestamp_or_none(article.get("publishedAt")),
                        updated_at,
                        article.get("originalTitle", ""),
                        article.get("translationStatus", ""),
                        article.get("contentStatus", ""),
                        json_param(article.get("tagItems", [])),
                        article.get("blockedReason", ""),
                        source_key,
                        article.get("sourceTier", ""),
                        article.get("licenseStatus", ""),
                        article.get("verificationStatus", ""),
                        json_param(article.get("sourceBadges", [])),
                        json_param(article.get("bodyBlocksZh", [])),
                        _canonical_topic_id(article),
                        json_param(article.get("readingMeta", {})),
                        article.get("translationFidelity", ""),
                        json_param(article),
                    ),
                )

    def delete_public_articles_not_in(self, accepted_ids):
        ids = [str(article_id) for article_id in accepted_ids if article_id]
        if not ids:
            return
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM content.articles WHERE NOT (id = ANY(%s))", (ids,))

    def delete_public_articles(self, article_ids):
        ids = [str(article_id) for article_id in article_ids if article_id]
        if not ids:
            return
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM content.articles WHERE id = ANY(%s)", (ids,))

    def mark_published_queue_retryable(self, article_updates):
        updates = [(reason, updated_at, article_id) for reason, updated_at, article_id in article_updates if article_id]
        if not updates:
            return
        with self.connection() as conn:
            with conn.cursor() as cur:
                for reason, updated_at, article_id in updates:
                    cur.execute(
                        """
                        UPDATE content.discovery_queue
                        SET status = 'retryable', last_error = %s, updated_at = %s
                        WHERE id = %s AND status = 'published'
                        """,
                        (reason, updated_at, article_id),
                    )

    def _article_select_sql(self):
        return """
            SELECT id, title, summary, channel, category, tags_json, importance,
                   source_name, source_url, published_at, source_note,
                   body_zh, original_title, translation_status, content_status,
                   tag_items_json, blocked_reason, source_key, source_tier,
                   license_status, verification_status, source_badges_json,
                   body_blocks_zh_json, canonical_topic_id, reading_meta_json,
                   translation_fidelity
            FROM content.articles
        """

    def load_articles(self):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    self._article_select_sql()
                    + """
                    WHERE content_status = 'ready'
                    ORDER BY published_at DESC NULLS LAST, importance DESC
                    """
                )
                rows = cur.fetchall()
        return [_article_from_row(row) for row in rows]

    def load_public_articles_for_audit(self):
        return self.load_articles()

    def get_article(self, article_id):
        if not article_id:
            return None
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    self._article_select_sql()
                    + """
                    WHERE id = %s
                    """,
                    (article_id,),
                )
                row = cur.fetchone()
        return _article_from_row(row)

    def admin_gate_news_records(self):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, canonical_topic_id, source_key, source_name, source_tier,
                           source_url, original_title, published_at, status, attempts,
                           last_error, payload_json, discovered_at, updated_at, processed_at
                    FROM content.discovery_queue
                    ORDER BY updated_at DESC, discovered_at DESC
                    LIMIT 500
                    """
                )
                queue_rows = cur.fetchall()
                cur.execute(
                    """
                    SELECT id, title, source_name, source_url, published_at, updated_at,
                           content_status, translation_status, license_status,
                           verification_status, translation_fidelity, blocked_reason,
                           channel, category, tags_json
                    FROM content.articles
                    ORDER BY updated_at DESC
                    LIMIT 500
                    """
                )
                article_rows = cur.fetchall()
        return {
            "discoveryQueue": [
                {
                    "id": _text(row[0]),
                    "canonicalTopicId": _text(row[1]),
                    "sourceId": _text(row[2]),
                    "sourceName": _text(row[3]),
                    "sourceTier": _text(row[4]),
                    "sourceUrl": _text(row[5]),
                    "originalTitle": _text(row[6]),
                    "publishedAt": _text(row[7]),
                    "status": _text(row[8]),
                    "attempts": int(row[9] or 0),
                    "lastError": _text(row[10]),
                    "payload": _json_value(row[11], {}),
                    "discoveredAt": _text(row[12]),
                    "updatedAt": _text(row[13]),
                    "processedAt": _text(row[14]),
                }
                for row in queue_rows
            ],
            "articles": [
                {
                    "id": _text(row[0]),
                    "title": _text(row[1]),
                    "sourceName": _text(row[2]),
                    "sourceUrl": _text(row[3]),
                    "publishedAt": _text(row[4]),
                    "updatedAt": _text(row[5]),
                    "contentStatus": _text(row[6]),
                    "translationStatus": _text(row[7]),
                    "licenseStatus": _text(row[8]),
                    "verificationStatus": _text(row[9]),
                    "translationFidelity": _text(row[10]),
                    "blockedReason": _text(row[11]),
                    "channel": _text(row[12]),
                    "category": _text(row[13]),
                    "tags": _json_value(row[14], []),
                }
                for row in article_rows
            ],
        }

    def admin_gate_queue_summary(self):
        rows = []
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status, last_error
                    FROM content.discovery_queue
                    ORDER BY updated_at DESC, discovered_at DESC
                    LIMIT 500
                    """
                )
                rows.extend((row[0] or "", [row[1]] if row[1] else []) for row in cur.fetchall())
                cur.execute(
                    """
                    SELECT CASE WHEN content_status = 'ready' THEN 'published' ELSE content_status END,
                           blocked_reason
                    FROM content.articles
                    ORDER BY updated_at DESC
                    LIMIT 500
                    """
                )
                rows.extend((row[0] or "", [row[1]] if row[1] else []) for row in cur.fetchall())
        return _admin_gate_queue_summary(rows)

    def enqueue_discovered_articles(self, articles, discovered_at):
        with self.connection() as conn:
            with conn.cursor() as cur:
                for article in articles:
                    queued = dict(article)
                    queued["canonicalTopicId"] = _canonical_topic_id(queued)
                    source_key = _source_key(queued)
                    self._upsert_source_from_article(cur, queued, discovered_at)
                    cur.execute(
                        """
                        INSERT INTO content.discovery_queue (
                            id, canonical_topic_id, source_key, source_name, source_tier,
                            source_url, original_title, published_at, status, attempts,
                            last_error, payload_json, discovered_at, updated_at, processed_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'queued', 0, '', %s::jsonb, %s, %s, NULL)
                        ON CONFLICT (id) DO UPDATE SET
                            canonical_topic_id = EXCLUDED.canonical_topic_id,
                            source_key = EXCLUDED.source_key,
                            source_name = EXCLUDED.source_name,
                            source_tier = EXCLUDED.source_tier,
                            source_url = EXCLUDED.source_url,
                            original_title = EXCLUDED.original_title,
                            published_at = EXCLUDED.published_at,
                            status = CASE
                                WHEN content.discovery_queue.status = 'published'
                                     AND EXISTS (
                                         SELECT 1 FROM content.articles
                                         WHERE content.articles.id = EXCLUDED.id
                                           AND content.articles.content_status = 'ready'
                                     )
                                THEN content.discovery_queue.status
                                ELSE 'queued'
                            END,
                            last_error = CASE
                                WHEN content.discovery_queue.status = 'published'
                                     AND EXISTS (
                                         SELECT 1 FROM content.articles
                                         WHERE content.articles.id = EXCLUDED.id
                                           AND content.articles.content_status = 'ready'
                                     )
                                THEN content.discovery_queue.last_error
                                ELSE ''
                            END,
                            payload_json = EXCLUDED.payload_json,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            queued.get("id", ""),
                            queued.get("canonicalTopicId", ""),
                            source_key,
                            queued.get("sourceName", ""),
                            queued.get("sourceTier", ""),
                            queued.get("sourceUrl", ""),
                            queued.get("originalTitle") or queued.get("title", ""),
                            _timestamp_or_none(queued.get("publishedAt")),
                            json_param(queued),
                            discovered_at,
                            discovered_at,
                        ),
                    )

    def mark_queue_article(self, article, status, error="", processed_at=None, increment_attempts=True):
        attempts_sql = "attempts + 1" if increment_attempts else "attempts"
        now = processed_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE content.discovery_queue
                    SET status = %s, last_error = %s, processed_at = %s, updated_at = %s,
                        attempts = {attempts_sql}
                    WHERE id = %s
                    """,
                    (status, error or "", now, now, article.get("id", "")),
                )

    def load_queued_articles(self, limit):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT payload_json, attempts, last_error
                    FROM content.discovery_queue
                    WHERE status IN ('queued', 'retryable')
                    ORDER BY published_at DESC NULLS LAST, discovered_at ASC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
        articles = []
        for row in rows:
            article = _json_value(row[0], {})
            if isinstance(article, dict) and article:
                article["_queueAttempts"] = int(row[1] or 0)
                article["_queueLastError"] = _text(row[2])
                articles.append(article)
        return articles

    def queue_summary(self, collector_errors=None):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status, COUNT(*)
                    FROM content.discovery_queue
                    GROUP BY status
                    """
                )
                status_rows = cur.fetchall()
                cur.execute(
                    """
                    SELECT source_key, source_name, source_tier, status, COUNT(*)
                    FROM content.discovery_queue
                    GROUP BY source_key, source_name, source_tier, status
                    """
                )
                coverage_rows = cur.fetchall()
                cur.execute(
                    """
                    SELECT MIN(discovered_at)
                    FROM content.discovery_queue
                    WHERE status IN ('queued', 'retryable')
                    """
                )
                oldest_row = cur.fetchone()
        status_counts = {row[0]: row[1] for row in status_rows}
        coverage = {}
        for source_key, source_name, source_tier, status, count in coverage_rows:
            key = source_key or source_name
            item = coverage.setdefault(
                key,
                {
                    "sourceName": source_name,
                    "sourceTier": source_tier,
                    "discovered": 0,
                    "queued": 0,
                    "processed": 0,
                    "published": 0,
                    "blocked": 0,
                    "retryable": 0,
                    "errors": 0,
                },
            )
            item["discovered"] += count
            if status in item:
                item[status] += count
            if status in {"published", "blocked", "retryable"}:
                item["processed"] += count
        for error in collector_errors or []:
            source_name = error.get("sourceName", "")
            key = error.get("sourceId") or source_name or "unknown"
            item = coverage.setdefault(
                key,
                {
                    "sourceName": source_name,
                    "sourceTier": error.get("sourceTier", ""),
                    "discovered": 0,
                    "queued": 0,
                    "processed": 0,
                    "published": 0,
                    "blocked": 0,
                    "retryable": 0,
                    "errors": 0,
                },
            )
            item["errors"] += 1
        oldest_age = 0
        oldest_value = oldest_row[0] if oldest_row else None
        oldest_dt = _parse_iso_datetime(oldest_value)
        if oldest_dt:
            oldest_age = max(0, int((datetime.now(timezone.utc) - oldest_dt).total_seconds()))
        return {
            "queuedCount": int(status_counts.get("queued", 0) or 0),
            "retryableCount": int(status_counts.get("retryable", 0) or 0),
            "publishedQueueCount": int(status_counts.get("published", 0) or 0),
            "blockedQueueCount": int(status_counts.get("blocked", 0) or 0),
            "oldestBacklogAge": oldest_age,
            "sourceCoverage": coverage,
        }

    def audit_existing_public_articles(self, quality_issue):
        blocked = []
        delete_ids = []
        queue_updates = []
        checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for article in self.load_public_articles_for_audit():
            reason = quality_issue(article)
            if not reason:
                continue
            delete_ids.append(article["id"])
            queue_updates.append((reason, checked_at, article["id"]))
            blocked.append(
                {
                    "id": article.get("id", ""),
                    "title": article.get("originalTitle") or article.get("title", ""),
                    "sourceName": article.get("sourceName", ""),
                    "reason": reason,
                    "translationStatus": article.get("translationStatus", ""),
                    "contentStatus": "blocked",
                    "verificationStatus": article.get("verificationStatus", ""),
                    "licenseStatus": article.get("licenseStatus", ""),
                    "sourceTier": article.get("sourceTier", ""),
                }
            )
        self.delete_public_articles(delete_ids)
        self.mark_published_queue_retryable(queue_updates)
        return blocked

    def record_refresh_run(self, refresh_mode, refreshed_at, accepted_count, rejected_count, message):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO content.refresh_runs (
                        refresh_mode, refreshed_at, accepted_count, rejected_count, message_json
                    ) VALUES (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (refresh_mode, refreshed_at, accepted_count, rejected_count, json_param(message)),
                )

    def latest_refresh_state(self):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT refresh_mode, refreshed_at
                    FROM content.refresh_runs
                    ORDER BY id DESC LIMIT 1
                    """
                )
                row = cur.fetchone()
        if not row:
            return None
        return {"refreshMode": _text(row[0]), "lastRefreshedAt": _text(row[1])}

    def latest_refresh_run_payload(self):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT refresh_mode, refreshed_at, accepted_count, rejected_count, message_json
                    FROM content.refresh_runs
                    ORDER BY id DESC LIMIT 1
                    """
                )
                row = cur.fetchone()
        return _refresh_payload_from_row(row)

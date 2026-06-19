import hashlib
import html
import json
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

try:
    from .news_sources.version_classifier import classify_version_event
except ImportError:
    from news_sources.version_classifier import classify_version_event

CHANNEL_RETAIL = "正式服动态"
CHANNEL_PTR = "测试服前瞻"
CHANNEL_CLASS = "职业强度变化"

PTR_KEYWORDS = ("ptr", "public test realm", "beta", "development notes", "测试服")
CLASS_KEYWORDS = (
    "class tuning",
    "class changes",
    "class update",
    "class set",
    "classes",
    "tuning",
    "hotfix",
    "balance",
    "druid",
    "warrior",
    "mage",
    "hunter",
    "paladin",
    "priest",
    "rogue",
    "shaman",
    "warlock",
    "monk",
    "demon hunter",
    "death knight",
    "evoker",
    "职业",
    "调优",
    "平衡",
)


def strip_html(value):
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def strip_unwanted_html(value):
    text = re.sub(r"<script\b.*?</script>", " ", value or "", flags=re.S | re.I)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<nav\b.*?</nav>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<aside\b.*?</aside>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<footer\b.*?</footer>", " ", text, flags=re.S | re.I)
    return text


def html_blocks_to_text(value):
    return body_blocks_to_text(html_blocks_to_body_blocks(value))


def clean_block_text(value):
    text = re.sub(r"<(br|br/|br /)>", "\n", value or "", flags=re.I)
    text = strip_html(text)
    return re.sub(r"\s+", " ", text).strip()


def body_blocks_to_text(blocks):
    lines = []
    for block in blocks or []:
        block_type = block.get("type")
        if block_type == "list":
            lines.extend(item for item in block.get("items", []) if item)
            continue
        text = clean_block_text(block.get("text", ""))
        if text:
            lines.append(text)
    deduped = []
    seen = set()
    for line in lines:
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(line)
    return "\n\n".join(deduped)


def html_blocks_to_body_blocks(value):
    text = strip_unwanted_html(value)
    blocks = []
    pattern = re.compile(
        r"<(h1|h2|h3|p|blockquote)\b[^>]*>(.*?)</\1>|<(ul|ol)\b[^>]*>(.*?)</\3>",
        flags=re.S | re.I,
    )
    for match in pattern.finditer(text or ""):
        tag = (match.group(1) or match.group(3) or "").lower()
        content = match.group(2) if match.group(1) else match.group(4)
        if tag in {"h1", "h2", "h3"}:
            block_text = clean_block_text(content)
            if block_text:
                blocks.append({"type": "heading", "text": block_text})
        elif tag == "p":
            block_text = clean_block_text(content)
            if block_text:
                blocks.append({"type": "paragraph", "text": block_text})
        elif tag == "blockquote":
            block_text = clean_block_text(content)
            if block_text:
                blocks.append({"type": "quote", "text": block_text})
        elif tag in {"ul", "ol"}:
            items = [
                clean_block_text(item_match.group(1))
                for item_match in re.finditer(r"<li\b[^>]*>(.*?)</li>", content or "", flags=re.S | re.I)
            ]
            items = [item for item in items if item]
            if items:
                blocks.append({"type": "list", "items": items})

    if blocks:
        return blocks

    fallback = strip_html(text)
    return [
        {"type": "paragraph", "text": line.strip(" -\t")}
        for line in re.split(r"\n+", fallback)
        if line.strip(" -\t")
    ]


def summarize(value, limit=140):
    text = strip_html(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def parse_date(value):
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return ""


def classify(title, summary):
    text = f"{title} {summary}".lower()
    tags = []
    channel = CHANNEL_RETAIL
    category = "正式服"

    if any(keyword in text for keyword in PTR_KEYWORDS):
        channel = CHANNEL_PTR
        category = "测试服"
        tags.append("ptr")

    if any(keyword in text for keyword in CLASS_KEYWORDS):
        tags.append("class-change")
        if channel != CHANNEL_PTR:
            channel = CHANNEL_CLASS

    if "hotfix" in text:
        tags.append("hotfix")
    if "trading post" in text or "traveler's log" in text:
        tags.append("trading-post")
    if "content update" in text or "update" in text:
        tags.append("content-update")
    if "raid" in text:
        tags.append("raid")
    if "reward" in text:
        tags.append("rewards")
    if "this week in wow" in text or "weekly" in text:
        tags.append("weekly")

    return channel, category, list(dict.fromkeys(tags))


def classify(title, summary):
    text = f"{title} {summary}".lower()
    version_event = classify_version_event(title, summary)
    tags = []
    channel = CHANNEL_RETAIL
    category = CHANNEL_RETAIL

    if version_event["productPhase"] in {"ptr", "beta", "alpha"} or any(keyword in text for keyword in PTR_KEYWORDS):
        channel = CHANNEL_PTR
        category = CHANNEL_PTR
        phase_tag = version_event["productPhase"] if version_event["productPhase"] in {"ptr", "beta", "alpha"} else "ptr"
        tags.append(phase_tag)
    if version_event["needsClassificationReview"]:
        tags.append("needs_classification_review")

    if any(keyword in text for keyword in CLASS_KEYWORDS) or version_event["contentType"] == "class_tuning":
        tags.append("class-change")
        if channel != CHANNEL_PTR:
            channel = CHANNEL_CLASS

    if version_event["contentType"] == "hotfix" or "hotfix" in text:
        tags.append("hotfix")
    if "trading post" in text or "traveler's log" in text:
        tags.append("trading-post")
    if version_event["contentType"] == "content_update" or "content update" in text or "update" in text:
        tags.append("content-update")
    if version_event["contentType"] == "raid_testing" or "raid" in text:
        tags.append("raid")
    if "reward" in text:
        tags.append("rewards")
    if "this week in wow" in text or "weekly" in text:
        tags.append("weekly")

    return channel, category, list(dict.fromkeys(tags))


def article_id(source_name, url):
    digest = hashlib.sha1(f"{source_name}:{url}".encode("utf-8")).hexdigest()[:12]
    hostname = urlparse(url).hostname or "source"
    return f"{hostname.replace('.', '-')}-{digest}"


def canonical_article_key(article):
    url = article.get("sourceUrl", "")
    match = re.search(r"/news/(\d+)", url)
    if match:
        hostname = urlparse(url).hostname or article.get("sourceName", "")
        return f"{hostname.replace('www.', '')}:news:{match.group(1)}"
    if url:
        return f"{article.get('sourceName', '')}:url:{url}"
    title = re.sub(r"\W+", "", (article.get("title") or "").lower())
    if title:
        return f"{article.get('sourceName', '')}:title:{title}"
    return f"{article.get('sourceName', '')}:id:{article.get('id', '')}"


def child_text(node, tag_names):
    for tag_name in tag_names:
        found = node.find(tag_name)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def atom_link(node):
    link = node.find("{http://www.w3.org/2005/Atom}link")
    if link is None:
        link = node.find("link")
    if link is None:
        return ""
    return (link.get("href") or link.text or "").strip()


def feed_items(root):
    rss_items = root.findall(".//item")
    if rss_items:
        return rss_items, "rss"
    atom_items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    if atom_items:
        return atom_items, "atom"
    return [], "rss"


def parse_feed_articles(feed_text, source):
    root = ElementTree.fromstring(feed_text)
    nodes, feed_type = feed_items(root)
    articles = []

    for node in nodes:
        if feed_type == "atom":
            title = child_text(node, ["{http://www.w3.org/2005/Atom}title", "title"])
            url = atom_link(node)
            summary = child_text(
                node,
                [
                    "{http://www.w3.org/2005/Atom}summary",
                    "{http://www.w3.org/2005/Atom}content",
                    "summary",
                    "content",
                ],
            )
            published_at = parse_date(child_text(node, ["{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated", "published", "updated"]))
        else:
            title = child_text(node, ["title"])
            url = child_text(node, ["link"])
            summary = child_text(node, ["description", "summary"])
            published_at = parse_date(child_text(node, ["pubDate", "published", "updated"]))

        if not title or not url or not published_at:
            continue

        clean_summary = summarize(summary or title)
        channel, category, tags = classify(title, clean_summary)
        version_event = classify_version_event(title, clean_summary, url)
        importance = int(source.get("baseImportance", 70))
        if channel == CHANNEL_PTR:
            importance += 8
        if "class-change" in tags:
            importance += 6

        articles.append(
            {
                "id": article_id(source["sourceName"], url),
                "title": strip_html(title),
                "summary": clean_summary,
                "channel": channel,
                "category": category,
                "tags": tags,
                "importance": importance,
                "sourceName": source["sourceName"],
                "sourceId": source.get("sourceId", source["sourceName"].lower().replace(" ", "-")),
                "sourceTier": source.get("sourceTier", "trusted_media"),
                "licenseStatus": source.get("licenseStatus", "reference_only"),
                "sourceUrl": url,
                "publishedAt": published_at,
                "sourceNote": f"{source['sourceNote']} 原始条目：{source.get('sourceUrl', url)}",
                "originalTitle": strip_html(title),
                "originalSummary": clean_summary,
                "originalBody": clean_summary,
                "bodyBlocks": [{"type": "paragraph", "text": clean_summary}],
                "bodySourceKind": "feed_excerpt",
                "versionEvent": version_event,
                "requiresLlmTranslation": True,
                "contentStatus": "discovered",
            }
        )

    return articles


def extract_attr(value, attr_name):
    match = re.search(rf'{attr_name}="([^"]+)"', value or "")
    if not match:
        return ""
    return html.unescape(match.group(1))


def absolute_blizzard_url(url):
    if url.startswith("https://"):
        return url
    if url.startswith("/"):
        return f"https://worldofwarcraft.blizzard.com{url}"
    return f"https://worldofwarcraft.blizzard.com/{url}"


def absolute_blizzard_forum_url(url):
    if url.startswith("https://"):
        return url
    if url.startswith("/"):
        return f"https://us.forums.blizzard.com{url}"
    return f"https://us.forums.blizzard.com/{url}"


def blizzard_forum_json_url(url):
    clean_url = (url or "").rstrip("/")
    if clean_url.endswith(".json"):
        return clean_url
    return f"{clean_url}.json"


def parse_blizzard_forum_topic_json(page_text, source_url=""):
    payload = json.loads(page_text or "{}")
    title = strip_html(payload.get("title") or payload.get("fancy_title") or "")
    posts = payload.get("post_stream", {}).get("posts", [])
    first_post = next((post for post in posts if int(post.get("post_number") or 0) == 1), posts[0] if posts else {})
    body_html = first_post.get("cooked") or first_post.get("raw") or ""
    body_blocks = html_blocks_to_body_blocks(body_html)
    if title and body_blocks:
        first = body_blocks[0]
        first_text = first.get("text", "") if first.get("type") != "list" else " ".join(first.get("items", []))
        if clean_block_text(first_text).lower() == title.lower():
            body_blocks = body_blocks[1:]
    original_body = body_blocks_to_text(body_blocks)
    published_at = parse_date(first_post.get("created_at") or payload.get("created_at"))
    return {
        "originalTitle": title,
        "originalBody": original_body,
        "bodyBlocks": body_blocks,
        "publishedAt": published_at,
        "sourceUrl": source_url,
        "bodySourceKind": "detail_body" if original_body and body_blocks else "forum_excerpt",
    }


def parse_blizzard_forum_topic_html(page_text, source_url=""):
    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", page_text or "", flags=re.S | re.I)
    if not title_match:
        title_match = re.search(r"<title[^>]*>(.*?)</title>", page_text or "", flags=re.S | re.I)
    title = strip_html(title_match.group(1)) if title_match else ""
    title = re.sub(r"\s+-\s+World of Warcraft Forums\s*$", "", title).strip()
    post_match = re.search(r'<div\b[^>]*class="[^"]*\bcooked\b[^"]*"[^>]*>(.*?)</div>', page_text or "", flags=re.S | re.I)
    body_html = post_match.group(1) if post_match else page_text
    body_blocks = html_blocks_to_body_blocks(body_html)
    original_body = body_blocks_to_text(body_blocks)
    published_at = ""
    date_match = re.search(r'(?:datetime|data-time)="([^"]+)"', page_text or "", flags=re.S | re.I)
    if date_match:
        published_at = parse_date(date_match.group(1))
    return {
        "originalTitle": title,
        "originalBody": original_body,
        "bodyBlocks": body_blocks,
        "publishedAt": published_at,
        "sourceUrl": source_url,
        "bodySourceKind": "detail_body" if original_body and body_blocks else "forum_excerpt",
    }


def parse_blizzard_article_html(page_text, source_url=""):
    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", page_text or "", flags=re.S | re.I)
    if not title_match:
        title_match = re.search(r"<title[^>]*>(.*?)</title>", page_text or "", flags=re.S | re.I)
    title = strip_html(title_match.group(1)) if title_match else ""
    title = re.sub(r"\s+-\s+WoW.*$", "", title).strip()

    data_props = ""
    date_match = re.search(r'data-props="([^"]*iso8601[^"]*)"', page_text or "", flags=re.S | re.I)
    if date_match:
        data_props = html.unescape(date_match.group(1))
    published_at = ""
    iso_match = re.search(r'"iso8601"\s*:\s*"([^"]+)"', data_props)
    if iso_match:
        published_at = parse_date(iso_match.group(1))

    article_match = re.search(r"<article\b[^>]*>(.*?)</article>", page_text or "", flags=re.S | re.I)
    if article_match:
        body_html = article_match.group(1)
    else:
        main_match = re.search(r"<main\b[^>]*>(.*?)</main>", page_text or "", flags=re.S | re.I)
        body_html = main_match.group(1) if main_match else page_text
    body_blocks = html_blocks_to_body_blocks(body_html)
    if title and body_blocks:
        first = body_blocks[0]
        first_text = first.get("text", "") if first.get("type") != "list" else " ".join(first.get("items", []))
        if clean_block_text(first_text).lower() == title.lower():
            body_blocks = body_blocks[1:]
    original_body = body_blocks_to_text(body_blocks)

    return {
        "originalTitle": title,
        "originalBody": original_body,
        "bodyBlocks": body_blocks,
        "publishedAt": published_at,
        "sourceUrl": source_url,
        "bodySourceKind": "detail_body" if original_body and body_blocks else "listing_excerpt",
    }


def parse_blizzard_news_html(page_text, detail_pages=None, max_articles=None):
    articles = []
    for match in re.finditer(r'<article class="NewsBlog".*?</article>', page_text, flags=re.S):
        block = match.group(0)
        title_match = re.search(r'<div class="NewsBlog-title">(.*?)</div>', block, flags=re.S)
        desc_match = re.search(r'<p class="NewsBlog-desc[^"]*">(.*?)</p>', block, flags=re.S)
        date_match = re.search(r'<div class="NewsBlog-date[^"]*"[^>]*data-props="([^"]+)"', block, flags=re.S)
        link_match = re.search(r'<a class="Link NewsBlog-link" href="([^"]+)"', block)
        if not title_match or not link_match:
            continue

        title = strip_html(title_match.group(1))
        summary = summarize(desc_match.group(1) if desc_match else title)
        data_props = html.unescape(date_match.group(1)) if date_match else ""
        published_at = ""
        iso_match = re.search(r'"iso8601"\s*:\s*"([^"]+)"', data_props)
        if iso_match:
            published_at = parse_date(iso_match.group(1))
        if not published_at:
            continue

        url = absolute_blizzard_url(html.unescape(link_match.group(1)))
        detail = {}
        if detail_pages and url in detail_pages:
            detail = parse_blizzard_article_html(detail_pages[url], url)
        body_blocks = detail.get("bodyBlocks") or [{"type": "paragraph", "text": summary}]
        body_source_kind = detail.get("bodySourceKind") if detail.get("bodyBlocks") else "listing_excerpt"
        channel, category, tags = classify(title, summary)
        version_event = classify_version_event(title, summary, url)
        importance = 86
        if channel == CHANNEL_PTR:
            importance += 8
        if "class-change" in tags:
            importance += 6

        articles.append(
            {
                "id": article_id("Blizzard News", url),
                "title": title,
                "summary": summary,
                "channel": channel,
                "category": category,
                "tags": tags,
                "importance": importance,
                "sourceName": "Blizzard News",
                "sourceId": "blizzard",
                "sourceTier": "official",
                "licenseStatus": "approved",
                "sourceUrl": url,
                "publishedAt": detail.get("publishedAt") or published_at,
                "sourceNote": "暴雪官方 World of Warcraft 新闻列表页自动采集，保留原文链接和页面发布日期。",
                "originalTitle": detail.get("originalTitle") or title,
                "originalSummary": summary,
                "originalBody": detail.get("originalBody") or summary,
                "bodyBlocks": body_blocks,
                "bodySourceKind": body_source_kind,
                "versionEvent": version_event,
                "requiresLlmTranslation": True,
                "contentStatus": "discovered",
            }
        )
        if max_articles is not None and len(articles) >= max_articles:
            break
    return articles


def parse_blizzard_forum_html(page_text, source, max_articles=None):
    articles = []
    pattern = re.compile(
        r'<a\b[^>]*(?:raw-topic-link|topic-link|title)[^>]*href="([^"]+/t/[^"]+)"[^>]*>(.*?)</a>(.*?)(?=<a\b[^>]*(?:raw-topic-link|topic-link|title)[^>]*href="[^"]+/t/|$)',
        flags=re.S | re.I,
    )
    for match in pattern.finditer(page_text or ""):
        url = absolute_blizzard_forum_url(html.unescape(match.group(1)))
        title = strip_html(match.group(2))
        tail = match.group(3) or ""
        if not title or not url:
            continue

        date_match = re.search(r'(?:data-time|datetime)="([^"]+)"', tail, flags=re.S | re.I)
        published_at = parse_date(date_match.group(1)) if date_match else ""
        if not published_at:
            published_at = parse_date(datetime.utcnow().isoformat())
        excerpt_match = re.search(r'<div\b[^>]*class="[^"]*excerpt[^"]*"[^>]*>(.*?)</div>', tail, flags=re.S | re.I)
        summary = summarize(excerpt_match.group(1) if excerpt_match else title)
        channel, category, tags = classify(title, summary)
        version_event = classify_version_event(title, summary, url)
        importance = int(source.get("baseImportance", 84))
        if channel == CHANNEL_PTR:
            importance += 8
        if "class-change" in tags:
            importance += 6

        articles.append(
            {
                "id": article_id(source.get("sourceName", "Blizzard Forums"), url),
                "title": title,
                "summary": summary,
                "channel": channel,
                "category": category,
                "tags": tags,
                "importance": importance,
                "sourceName": source.get("sourceName", "Blizzard Forums"),
                "sourceId": source.get("sourceId", "blizzard-forums"),
                "sourceTier": source.get("sourceTier", "official"),
                "licenseStatus": source.get("licenseStatus", "approved"),
                "sourceUrl": url,
                "publishedAt": published_at,
                "sourceNote": f"{source.get('sourceNote', 'Blizzard official forum discovery.')} Original topic list: {source.get('sourceUrl', url)}",
                "originalTitle": title,
                "originalSummary": summary,
                "originalBody": summary,
                "bodyBlocks": [{"type": "paragraph", "text": summary}],
                "bodySourceKind": "forum_excerpt",
                "versionEvent": version_event,
                "requiresLlmTranslation": True,
                "contentStatus": "discovered",
            }
        )
        if max_articles is not None and len(articles) >= max_articles:
            break
    return articles


def parse_blizzard_forum_json(page_text, source, max_articles=None):
    payload = json.loads(page_text or "{}")
    users = {user.get("id"): user for user in payload.get("users", [])}
    topics = payload.get("topic_list", {}).get("topics", [])
    articles = []

    for topic in topics:
        posters = topic.get("posters", [])
        original_poster = next((poster for poster in posters if "Original Poster" in (poster.get("description") or "")), None)
        original_poster = original_poster or (posters[0] if posters else {})
        user = users.get(original_poster.get("user_id"), {})
        if not (user.get("admin") or user.get("moderator")):
            continue

        title = strip_html(topic.get("title") or topic.get("fancy_title") or "")
        topic_id = topic.get("id")
        slug = topic.get("slug") or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        if not title or not topic_id:
            continue

        url = absolute_blizzard_forum_url(f"/en/wow/t/{slug}/{topic_id}")
        summary = summarize(topic.get("excerpt") or title)
        classification_summary = f"{summary} {source.get('sourceUrl', '')}"
        channel, category, tags = classify(title, classification_summary)
        version_event = classify_version_event(title, classification_summary, url)
        published_at = parse_date(topic.get("created_at") or topic.get("last_posted_at"))
        if not published_at:
            published_at = parse_date(datetime.utcnow().isoformat())
        importance = int(source.get("baseImportance", 84))
        if channel == CHANNEL_PTR:
            importance += 8
        if "class-change" in tags:
            importance += 6

        articles.append(
            {
                "id": article_id(source.get("sourceName", "Blizzard Forums"), url),
                "title": title,
                "summary": summary,
                "channel": channel,
                "category": category,
                "tags": tags,
                "importance": importance,
                "sourceName": source.get("sourceName", "Blizzard Forums"),
                "sourceId": source.get("sourceId", "blizzard-forums"),
                "sourceTier": source.get("sourceTier", "official"),
                "licenseStatus": source.get("licenseStatus", "approved"),
                "sourceUrl": url,
                "publishedAt": published_at,
                "sourceNote": f"{source.get('sourceNote', 'Blizzard official forum discovery.')} Original topic list: {source.get('sourceUrl', url)}",
                "originalTitle": title,
                "originalSummary": summary,
                "originalBody": summary,
                "bodyBlocks": [{"type": "paragraph", "text": summary}],
                "bodySourceKind": "forum_excerpt",
                "versionEvent": version_event,
                "requiresLlmTranslation": True,
                "contentStatus": "discovered",
            }
        )
        if max_articles is not None and len(articles) >= max_articles:
            break
    return articles


def fetch_url(url, accept, timeout=15):
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 wow-mini-program-news-backend/0.1",
            "Accept": accept,
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_blizzard_news_articles(source, timeout=15, max_articles=None):
    body = fetch_url(source["sourceUrl"], "text/html,*/*", timeout=timeout)
    articles = parse_blizzard_news_html(body, max_articles=max_articles)
    enriched = []
    for article in articles:
        try:
            detail_body = fetch_url(article["sourceUrl"], "text/html,*/*", timeout=timeout)
            detail = parse_blizzard_article_html(detail_body, article["sourceUrl"])
            article.update(
                {
                    "originalTitle": detail.get("originalTitle") or article.get("originalTitle", ""),
                    "originalBody": detail.get("originalBody") or article.get("originalBody", ""),
                    "bodyBlocks": detail.get("bodyBlocks") or article.get("bodyBlocks", []),
                    "bodySourceKind": detail.get("bodySourceKind") or article.get("bodySourceKind", ""),
                    "publishedAt": detail.get("publishedAt") or article.get("publishedAt", ""),
                }
            )
        except Exception as error:  # detail fetch must not abort the whole list
            article["detailError"] = str(error)
        enriched.append(article)
    return enriched


def fetch_blizzard_forum_topic_detail(source_url, timeout=15):
    try:
        body = fetch_url(blizzard_forum_json_url(source_url), "application/json,*/*", timeout=timeout)
        detail = parse_blizzard_forum_topic_json(body, source_url)
        if detail.get("bodySourceKind") == "detail_body":
            return detail
    except Exception as json_error:
        last_error = json_error
    else:
        last_error = ValueError("forum topic json did not include a publishable first post body")

    try:
        body = fetch_url(source_url, "text/html,*/*", timeout=timeout)
        detail = parse_blizzard_forum_topic_html(body, source_url)
        if detail.get("bodySourceKind") == "detail_body":
            return detail
        raise ValueError("forum topic html did not include a publishable first post body")
    except Exception as html_error:
        raise RuntimeError(f"{last_error}; {html_error}") from html_error


def enrich_blizzard_forum_article(article, timeout=15):
    enriched = dict(article)
    try:
        detail = fetch_blizzard_forum_topic_detail(article["sourceUrl"], timeout=timeout)
        enriched.update(
            {
                "originalTitle": detail.get("originalTitle") or article.get("originalTitle", ""),
                "originalBody": detail.get("originalBody") or article.get("originalBody", ""),
                "bodyBlocks": detail.get("bodyBlocks") or article.get("bodyBlocks", []),
                "bodySourceKind": detail.get("bodySourceKind") or article.get("bodySourceKind", ""),
                "publishedAt": detail.get("publishedAt") or article.get("publishedAt", ""),
            }
        )
    except Exception as error:
        enriched["detailError"] = str(error)
        enriched["bodySourceKind"] = enriched.get("bodySourceKind") or "forum_excerpt"
    return enriched


def fetch_blizzard_forum_articles(source, timeout=15, max_articles=None):
    try:
        body = fetch_url(blizzard_forum_json_url(source["sourceUrl"]), "application/json,*/*", timeout=timeout)
        articles = parse_blizzard_forum_json(body, source, max_articles=max_articles)
    except Exception:
        body = fetch_url(source["sourceUrl"], "text/html,*/*", timeout=timeout)
        articles = parse_blizzard_forum_html(body, source, max_articles=max_articles)
    return [enrich_blizzard_forum_article(article, timeout=timeout) for article in articles]


def merge_articles(seed_articles, collected_articles):
    by_key = {}
    for article in seed_articles:
        by_key[canonical_article_key(article)] = article
    for article in collected_articles:
        by_key[canonical_article_key(article)] = article
    return sorted(
        by_key.values(),
        key=lambda item: (item.get("importance", 0), item.get("publishedAt", "")),
        reverse=True,
    )


def fetch_feed_articles(source, timeout=15, max_articles=None):
    body = fetch_url(source["sourceUrl"], "application/rss+xml, application/atom+xml, application/xml, text/xml, */*", timeout=timeout)
    articles = parse_feed_articles(body, source)
    return articles[:max_articles] if max_articles is not None else articles


def collect_feed_articles(sources, timeout=15, max_articles_per_source=None):
    articles = []
    errors = []
    for source in sources:
        try:
            if source.get("type") == "blizzard_html":
                articles.extend(fetch_blizzard_news_articles(source, timeout=timeout, max_articles=max_articles_per_source))
            elif source.get("type") == "blizzard_forum":
                articles.extend(fetch_blizzard_forum_articles(source, timeout=timeout, max_articles=max_articles_per_source))
            else:
                articles.extend(fetch_feed_articles(source, timeout=timeout, max_articles=max_articles_per_source))
        except Exception as error:  # network collectors must fail soft
            errors.append({"sourceName": source.get("sourceName", ""), "sourceUrl": source.get("sourceUrl", ""), "error": str(error)})
    return articles, errors

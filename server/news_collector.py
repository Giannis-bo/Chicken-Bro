import hashlib
import html
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

try:
    from .news_translator import localize_article
except ImportError:
    from news_translator import localize_article

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


def summarize(value, limit=96):
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

    return channel, category, tags


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
        importance = int(source.get("baseImportance", 70))
        if channel == CHANNEL_PTR:
            importance += 8
        if "class-change" in tags:
            importance += 6

        articles.append(
            localize_article(
                {
                "id": article_id(source["sourceName"], url),
                "title": strip_html(title),
                "summary": clean_summary,
                "channel": channel,
                "category": category,
                "tags": tags,
                "importance": importance,
                "sourceName": source["sourceName"],
                "sourceUrl": url,
                "publishedAt": published_at,
                "sourceNote": f"{source['sourceNote']} 原始条目：{source.get('sourceUrl', url)}",
                "originalTitle": strip_html(title),
                "originalSummary": clean_summary,
                "originalBody": clean_summary,
                }
            )
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


def parse_blizzard_news_html(page_text):
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
        channel, category, tags = classify(title, summary)
        importance = 86
        if channel == CHANNEL_PTR:
            importance += 8
        if "class-change" in tags:
            importance += 6

        articles.append(
            localize_article(
                {
                "id": article_id("Blizzard News", url),
                "title": title,
                "summary": summary,
                "channel": channel,
                "category": category,
                "tags": tags,
                "importance": importance,
                "sourceName": "Blizzard News",
                "sourceUrl": url,
                "publishedAt": published_at,
                "sourceNote": "暴雪官方 World of Warcraft 新闻列表页自动采集，保留原文链接和页面发布日期。",
                "originalTitle": title,
                "originalSummary": summary,
                "originalBody": summary,
                }
            )
        )
    return articles


def fetch_blizzard_news_articles(source, timeout=15):
    request = Request(
        source["sourceUrl"],
        headers={
            "User-Agent": "Mozilla/5.0 wow-mini-program-news-backend/0.1",
            "Accept": "text/html,*/*",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    return parse_blizzard_news_html(body)


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


def fetch_feed_articles(source, timeout=15):
    request = Request(
        source["sourceUrl"],
        headers={
            "User-Agent": "wow-mini-program-news-backend/0.1",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    return parse_feed_articles(body, source)


def collect_feed_articles(sources, timeout=15):
    articles = []
    errors = []
    for source in sources:
        try:
            if source.get("type") == "blizzard_html":
                articles.extend(fetch_blizzard_news_articles(source, timeout=timeout))
            else:
                articles.extend(fetch_feed_articles(source, timeout=timeout))
        except Exception as error:  # network collectors must fail soft
            errors.append({"sourceName": source.get("sourceName", ""), "sourceUrl": source.get("sourceUrl", ""), "error": str(error)})
    return articles, errors

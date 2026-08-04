"""Generic bounded public-web research for Chickenbro's agentic ToolBox.

This module has no game-, class-, patch-, provider-, or answer-specific
selection logic. Codex supplies either a bounded research query or a safe
public HTTPS URL it has selected; the tool reads at most two public pages and
returns only small text projections and citations. It retains neither page
bodies nor search result pages after a request completes.
"""

from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import ipaddress
import re
import socket
from threading import RLock
from time import monotonic
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


PUBLIC_WEB_SOURCE_KEY = "public_web_research"
PUBLIC_WEB_SEARCH_URL = "https://html.duckduckgo.com/html/?q="
PUBLIC_WEB_TIMEOUT_SECONDS = 5
PUBLIC_WEB_MAX_RESPONSE_BYTES = 750_000
PUBLIC_WEB_MAX_QUERY_CHARS = 240
PUBLIC_WEB_MAX_RESULTS = 2
PUBLIC_WEB_CACHE_TTL_SECONDS = 60
PUBLIC_WEB_MAX_REQUESTS_PER_WINDOW = 8
PUBLIC_WEB_RATE_WINDOW_SECONDS = 60
_PUBLIC_WEB_LOCK = RLock()
_PUBLIC_WEB_CACHE = {}
_PUBLIC_WEB_INFLIGHT = set()
_PUBLIC_WEB_REQUEST_TIMES = deque()
_TAG_PATTERN = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_PATTERN = re.compile(r"<(?:script|style)[^>]*>.*?</(?:script|style)>", re.IGNORECASE | re.DOTALL)
_BLOCK_BOUNDARY_PATTERN = re.compile(r"</(?:article|div|h[1-6]|li|p|section|td|th|tr|br)\s*>", re.IGNORECASE)
_SPACE_PATTERN = re.compile(r"\s+")
_NUMBER_PATTERN = re.compile(r"(?<![\w.])\+?\d{1,8}(?:[,.]\d{1,4})?%?")
_SAFE_HOST_PATTERN = re.compile(r"^[a-z0-9.-]{1,253}$", re.IGNORECASE)


class _NoRedirect(HTTPRedirectHandler):
    """Keep the validated public URL as the only network target for a read."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _text(value):
    return str(value or "").strip()


def _normalized(value):
    return _text(value).lower()


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "-", _normalized(value)).strip("-")[:120]


def _plain_text(page):
    without_noncontent = _SCRIPT_STYLE_PATTERN.sub(" ", str(page or ""))
    return _SPACE_PATTERN.sub(" ", unescape(_TAG_PATTERN.sub(" ", without_noncontent))).strip()


def _page_title(page):
    match = re.search(r"<title[^>]*>(.*?)</title>", str(page or ""), re.IGNORECASE | re.DOTALL)
    return _plain_text(match.group(1))[:180] if match else "Public community page"


def _safe_public_url(value):
    parsed = urlparse(_text(value))
    host = _normalized(parsed.hostname)
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username
        or parsed.password
        or not _SAFE_HOST_PATTERN.fullmatch(host)
        or host in {"localhost", "localhost.localdomain"}
        or host.endswith(".local")
        or parsed.port not in {None, 443}
    ):
        return ""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_unspecified):
        return ""
    normalized = parsed._replace(fragment="").geturl()
    return normalized if len(normalized) <= 2000 else ""


def _resolved_host_is_public(host):
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return False
    values = []
    for entry in addresses:
        try:
            values.append(ipaddress.ip_address(entry[4][0]))
        except (IndexError, ValueError):
            return False
    return bool(values) and all(
        not (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_unspecified)
        for address in values
    )


def _read_url(url, timeout_seconds=None):
    safe_url = _safe_public_url(url)
    host = urlparse(safe_url).hostname if safe_url else ""
    if not safe_url or not host or not _resolved_host_is_public(host):
        raise ValueError("unsafe public web target")
    request = Request(
        safe_url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "wow-mini-program-chickenbro/1.0 public-web-research",
        },
    )
    # Do not follow a redirect after validating the initial host: otherwise a
    # public URL could redirect this read into a private address.
    opener = build_opener(_NoRedirect())
    with opener.open(
        request,
        timeout=max(1, int(timeout_seconds or PUBLIC_WEB_TIMEOUT_SECONDS)),
    ) as response:
        body = response.read(PUBLIC_WEB_MAX_RESPONSE_BYTES + 1)
    if len(body) > PUBLIC_WEB_MAX_RESPONSE_BYTES:
        raise ValueError("public web response exceeded bounded read budget")
    return body.decode("utf-8", errors="replace")


class _SearchResultParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self._active = None

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attributes = dict(attrs)
        classes = _text(attributes.get("class"))
        href = _text(attributes.get("href"))
        if "result__a" in classes and href:
            self._active = {"url": href, "title": ""}

    def handle_data(self, data):
        if self._active is not None:
            self._active["title"] += str(data or "")

    def handle_endtag(self, tag):
        if tag == "a" and self._active is not None:
            self.results.append(self._active)
            self._active = None


def _search_target_url(value):
    raw = _text(value)
    parsed = urlparse(raw)
    if parsed.hostname and "duckduckgo.com" in _normalized(parsed.hostname):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target)
    return raw


def _default_searcher(query, timeout_seconds=None):
    search_page = _read_url(PUBLIC_WEB_SEARCH_URL + quote_plus(query), timeout_seconds=timeout_seconds)
    parser = _SearchResultParser()
    parser.feed(search_page)
    output = []
    seen = set()
    for item in parser.results:
        url = _safe_public_url(_search_target_url(item.get("url")))
        if not url or url in seen:
            continue
        seen.add(url)
        output.append({"title": _plain_text(item.get("title"))[:180], "url": url, "snippet": ""})
        if len(output) >= PUBLIC_WEB_MAX_RESULTS * 3:
            break
    return output


def reset_public_web_research_state():
    """Clear process-local request state for deterministic tests only."""
    with _PUBLIC_WEB_LOCK:
        _PUBLIC_WEB_CACHE.clear()
        _PUBLIC_WEB_INFLIGHT.clear()
        _PUBLIC_WEB_REQUEST_TIMES.clear()


def _cached_or_permitted_request(cache_key, now):
    with _PUBLIC_WEB_LOCK:
        cached = _PUBLIC_WEB_CACHE.get(cache_key)
        if cached and cached[0] > now:
            return "cached", deepcopy(cached[1])
        if cached:
            _PUBLIC_WEB_CACHE.pop(cache_key, None)
        if cache_key in _PUBLIC_WEB_INFLIGHT:
            return "inflight", None
        while _PUBLIC_WEB_REQUEST_TIMES and _PUBLIC_WEB_REQUEST_TIMES[0] <= now - PUBLIC_WEB_RATE_WINDOW_SECONDS:
            _PUBLIC_WEB_REQUEST_TIMES.popleft()
        if len(_PUBLIC_WEB_REQUEST_TIMES) >= PUBLIC_WEB_MAX_REQUESTS_PER_WINDOW:
            return "rate_limited", None
        _PUBLIC_WEB_INFLIGHT.add(cache_key)
        _PUBLIC_WEB_REQUEST_TIMES.append(now)
        return "permitted", None


def _finish_request(cache_key, now, result):
    with _PUBLIC_WEB_LOCK:
        _PUBLIC_WEB_INFLIGHT.discard(cache_key)
        if result.get("status") == "source_reference":
            _PUBLIC_WEB_CACHE[cache_key] = (now + PUBLIC_WEB_CACHE_TTL_SECONDS, deepcopy(result))


def _partial_result(limitation):
    return {
        "sourceKey": PUBLIC_WEB_SOURCE_KEY,
        "status": "partial",
        "facts": [],
        "evidence": [],
        "evidenceRefs": [],
        "limitations": [limitation],
        "nextActions": [],
    }


def _allowed_numbers(value):
    output = []
    for match in _NUMBER_PATTERN.finditer(_text(value)):
        number = match.group(0)
        if number not in output:
            output.append(number)
        if len(output) >= 60:
            break
    return output


def _public_summary(page):
    without_noncontent = _SCRIPT_STYLE_PATTERN.sub(" ", str(page or ""))
    blocks = []
    for raw_block in _BLOCK_BOUNDARY_PATTERN.sub("\n", without_noncontent).splitlines():
        block = _SPACE_PATTERN.sub(" ", unescape(_TAG_PATTERN.sub(" ", raw_block))).strip()
        if block and block not in blocks:
            blocks.append(block)
    selected = list(blocks[:18])
    for index, block in enumerate(blocks):
        if not _NUMBER_PATTERN.search(block):
            continue
        for nearby in blocks[max(0, index - 1): index + 1]:
            if nearby not in selected:
                selected.append(nearby)
        if len(selected) >= 48:
            break
    return " ".join(selected)[:4200]


def _search_hits(searcher, query):
    try:
        loaded = searcher(query, timeout_seconds=PUBLIC_WEB_TIMEOUT_SECONDS)
    except Exception as error:
        return [], f"Public web search failed: {type(error).__name__}."
    hits = []
    seen = set()
    for raw in loaded if isinstance(loaded, (list, tuple)) else []:
        item = raw if isinstance(raw, dict) else {}
        url = _safe_public_url(item.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        hits.append({"url": url, "title": _text(item.get("title"))[:180], "snippet": _text(item.get("snippet"))[:400]})
        if len(hits) >= PUBLIC_WEB_MAX_RESULTS:
            break
    return hits, ""


def build_public_web_research_tool_result(
    intent,
    *,
    searcher=_default_searcher,
    fetcher=_read_url,
    clock=monotonic,
    checked_at_factory=lambda: datetime.now(timezone.utc).isoformat(),
):
    """Read a small public-web snapshot for a Codex-selected target."""
    request = intent if isinstance(intent, dict) else {}
    target = _text(request.get("target") or request.get("query"))
    if not target or len(target) > PUBLIC_WEB_MAX_QUERY_CHARS:
        return _partial_result("Public web research requires a bounded non-empty query or safe public HTTPS URL.")
    now = float(clock())
    cache_key = target.casefold()
    admission, cached = _cached_or_permitted_request(cache_key, now)
    if admission == "cached":
        return cached
    if admission == "inflight":
        return _partial_result("An identical public web research request is already in progress; no duplicate request was sent.")
    if admission == "rate_limited":
        return _partial_result("Public web research rate budget is exhausted; no external request was sent.")
    direct_url = _safe_public_url(target)
    if direct_url:
        hits, search_error = ([{"url": direct_url, "title": "", "snippet": ""}], "")
    else:
        hits, search_error = _search_hits(searcher, target)
    if not hits:
        result = _partial_result(search_error or "Public web search returned no safe HTTPS result pages for this research query.")
        _finish_request(cache_key, now, result)
        return result

    facts = []
    evidence = []
    refs = []
    numbers = []
    for hit in hits:
        try:
            page = fetcher(hit["url"], timeout_seconds=PUBLIC_WEB_TIMEOUT_SECONDS)
        except Exception:
            continue
        if not isinstance(page, str):
            continue
        summary = _public_summary(page)
        if not summary:
            continue
        parsed = urlparse(hit["url"])
        host = _normalized(parsed.hostname)
        reference = f"public-web:{_slug(host)}-{_slug(parsed.path) or 'page'}"
        if reference in refs:
            reference = f"{reference}-{len(refs) + 1}"
        title = _page_title(page) or hit["title"] or "Public community page"
        facts.append({
            "sourceHost": host,
            "title": title,
            "summary": summary,
            "sourceScope": "public_community_web",
        })
        evidence.append({
            "id": reference,
            "sourceName": host,
            "sourceUrl": hit["url"],
            "title": title,
            "checkedAt": _text(checked_at_factory()),
            "sourceScope": "public_community_web",
        })
        refs.append(reference)
        for number in _allowed_numbers(summary):
            if number not in numbers:
                numbers.append(number)

    if not facts:
        result = _partial_result("Public web research could not read a bounded factual snapshot from safe search results.")
    else:
        result = {
            "sourceKey": PUBLIC_WEB_SOURCE_KEY,
            "status": "source_reference",
            "facts": facts,
            "evidence": evidence,
            "evidenceRefs": refs,
            "allowedNumbers": numbers[:60],
            "limitations": [
                "Public community pages are source-scoped snapshots. Their data window and metrics must be stated with the conclusion; they do not by themselves establish a universal balance or personal-performance verdict.",
            ],
            "nextActions": [],
        }
    _finish_request(cache_key, now, result)
    return result

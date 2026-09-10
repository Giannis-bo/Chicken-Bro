"""Generic bounded public-web research for Chickenbro's agentic ToolBox.

This module has no game-, class-, patch-, provider-, or answer-specific
selection logic. Codex supplies either a bounded research query or a safe
public HTTPS URL it has selected; the tool reads at most two public pages and
returns only small text projections and citations. It retains neither page
bodies nor search result pages after a request completes.
"""

from collections import deque
import base64
from copy import deepcopy
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import http.client
import ipaddress
from queue import Queue
import re
import socket
import ssl
from threading import Event, RLock, Thread, Timer
from time import monotonic
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import getproxies_environment, proxy_bypass_environment


PUBLIC_WEB_SOURCE_KEY = "public_web_research"
# Search providers are transport fallbacks only: the tool still returns the
# public pages selected by their results, never provider-specific game data.
# A challenged search page must not make every generic research question look
# as though the public web is unavailable.
PUBLIC_WEB_SEARCH_URLS = (
    "https://html.duckduckgo.com/html/?q=",
    "https://cn.bing.com/search?q=",
)
PUBLIC_WEB_TIMEOUT_SECONDS = 5
PUBLIC_WEB_MAX_RESPONSE_BYTES = 750_000
PUBLIC_WEB_MAX_QUERY_CHARS = 240
PUBLIC_WEB_MAX_URL_CHARS = 2048
PUBLIC_WEB_MAX_MATCH_CHARS = 120
PUBLIC_WEB_MAX_SUMMARY_CHARS = 6000
PUBLIC_WEB_MAX_RESULTS = 2
PUBLIC_WEB_CACHE_TTL_SECONDS = 60
PUBLIC_WEB_MAX_CACHE_ENTRIES = 128
PUBLIC_WEB_MAX_REQUESTS_PER_WINDOW = 8
PUBLIC_WEB_RATE_WINDOW_SECONDS = 60
_PUBLIC_WEB_LOCK = RLock()
_PUBLIC_WEB_CACHE = {}
_PUBLIC_WEB_INFLIGHT = set()
_PUBLIC_WEB_REQUEST_TIMES = deque()

class PublicWebState:
    """Cache and rate admission owned by one authenticated research generation."""
    def __init__(self):
        self.lock = RLock()
        self.cache = {}
        self.inflight = set()
        self.times = deque()

_DEFAULT_STATE = PublicWebState()
_DEFAULT_STATE.lock = _PUBLIC_WEB_LOCK
_DEFAULT_STATE.cache = _PUBLIC_WEB_CACHE
_DEFAULT_STATE.inflight = _PUBLIC_WEB_INFLIGHT
_DEFAULT_STATE.times = _PUBLIC_WEB_REQUEST_TIMES

_TAG_PATTERN = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_PATTERN = re.compile(r"<(?:script|style)[^>]*>.*?</(?:script|style)>", re.IGNORECASE | re.DOTALL)
_BLOCK_BOUNDARY_PATTERN = re.compile(r"</(?:article|div|h[1-6]|li|p|section|td|th|tr|br)\s*>", re.IGNORECASE)
_SPACE_PATTERN = re.compile(r"\s+")
_NUMBER_PATTERN = re.compile(r"(?<![\w.])\+?\d{1,8}(?:[,.]\d{1,4})?%?")
_SAFE_HOST_PATTERN = re.compile(r"^[a-z0-9.-]{1,253}$", re.IGNORECASE)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect to a validated address while retaining hostname TLS checks."""

    def __init__(self, host, pinned_address, *, port=443, timeout=None):
        super().__init__(host, port=port, timeout=timeout, context=ssl.create_default_context())
        self._pinned_address = pinned_address

    def connect(self):
        proxies = getproxies_environment()
        proxy_url = proxies.get("https")
        if proxy_url and not proxy_bypass_environment(self.host, proxies):
            # Configuration is server-owned. The proxy does not resolve the
            # user-selected destination: CONNECT retains its validated IP.
            try:
                proxy = urlparse(proxy_url)
                proxy_port = proxy.port or 80
                if (proxy.scheme != "http" or not proxy.hostname
                        or proxy.path not in ("", "/") or proxy.query or proxy.fragment):
                    raise ValueError()
            except ValueError:
                raise ValueError("unsupported HTTPS proxy configuration") from None
            deadline = monotonic() + self.timeout
            proxy_address = proxy.hostname
            try:
                ipaddress.ip_address(proxy_address)
            except ValueError:
                resolved = _run_until_deadline(
                    lambda: socket.getaddrinfo(proxy.hostname, proxy_port, type=socket.SOCK_STREAM),
                    deadline,
                )
                proxy_address = resolved[0][4][0]
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError("public web overall deadline exceeded")
            headers = {}
            if proxy.username is not None:
                credentials = unquote(proxy.username) + ":" + unquote(proxy.password or "")
                headers["Proxy-Authorization"] = "Basic " + base64.b64encode(credentials.encode()).decode("ascii")
            self.set_tunnel(self._pinned_address, self.port, headers=headers)
            self.sock = socket.create_connection(
                (proxy_address, proxy_port), remaining, self.source_address
            )
            self._tunnel()
            self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)
            return
        self.sock = socket.create_connection(
            (self._pinned_address, self.port), self.timeout, self.source_address
        )
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


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
    try:
        port = parsed.port
    except ValueError:
        return ""
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username
        or parsed.password
        or not _SAFE_HOST_PATTERN.fullmatch(host)
        or host in {"localhost", "localhost.localdomain"}
        or host.endswith(".local")
        or port not in {None, 443}
    ):
        return ""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_unspecified):
        return ""
    normalized = parsed._replace(fragment="").geturl()
    return normalized if len(normalized) <= PUBLIC_WEB_MAX_URL_CHARS else ""


def _run_until_deadline(operation, deadline):
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise TimeoutError("public web overall deadline exceeded")
    completed = Queue(maxsize=1)

    def run():
        try:
            completed.put((True, operation()))
        except BaseException as error:
            completed.put((False, error))

    worker = Thread(target=run, name="public-web-dns", daemon=True)
    worker.start()
    worker.join(remaining)
    if worker.is_alive():
        raise TimeoutError("public web DNS deadline exceeded")
    succeeded, value = completed.get_nowait()
    if not succeeded:
        raise value
    return value


def _resolve_public_addresses(host, deadline=None):
    try:
        if deadline is None:
            addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        else:
            addresses = _run_until_deadline(
                lambda: socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM), deadline
            )
    except TimeoutError:
        raise
    except OSError:
        return []
    values = []
    for entry in addresses:
        try:
            values.append(ipaddress.ip_address(entry[4][0]))
        except (IndexError, ValueError):
            return []
    if not values or any(not address.is_global or address.is_multicast for address in values):
        return []
    return [str(address) for address in values]


def _resolved_host_is_public(host):
    return bool(_resolve_public_addresses(host))


def _read_url(url, timeout_seconds=None):
    timeout = max(1, int(timeout_seconds or PUBLIC_WEB_TIMEOUT_SECONDS))
    deadline = monotonic() + timeout
    safe_url = _safe_public_url(url)
    host = urlparse(safe_url).hostname if safe_url else ""
    addresses = _resolve_public_addresses(host, deadline) if host else []
    if not safe_url or not host or not addresses:
        raise ValueError("unsafe public web target")
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise TimeoutError("public web overall deadline exceeded")
    parsed = urlparse(safe_url)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    connection = _PinnedHTTPSConnection(host, addresses[0], timeout=remaining)
    deadline_expired = Event()

    def interrupt_at_deadline():
        deadline_expired.set()
        active_socket = connection.sock
        if active_socket is None:
            return
        try:
            active_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            active_socket.close()
        except OSError:
            pass

    deadline_timer = Timer(max(0, deadline - monotonic()), interrupt_at_deadline)
    deadline_timer.daemon = True
    deadline_timer.start()
    try:
        connection.request("GET", path, headers={
            "Accept": "text/html,application/xhtml+xml",
            "Host": host,
            "User-Agent": "wow-mini-program-chickenbro/1.0 public-web-research",
        })
        if monotonic() >= deadline:
            raise TimeoutError("public web overall deadline exceeded")
        response = connection.getresponse()
        if 300 <= response.status < 400:
            raise ValueError("public web redirects are not followed")
        if not 200 <= response.status < 300:
            raise OSError("public web returned a non-success status")
        chunks = []
        total = 0
        while True:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError("public web overall deadline exceeded")
            if connection.sock is not None:
                connection.sock.settimeout(remaining)
            chunk = response.read(min(64 * 1024, PUBLIC_WEB_MAX_RESPONSE_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > PUBLIC_WEB_MAX_RESPONSE_BYTES:
                raise ValueError("public web response exceeded bounded read budget")
        return b"".join(chunks).decode("utf-8", errors="replace")
    except Exception as error:
        if deadline_expired.is_set() or monotonic() >= deadline:
            raise TimeoutError("public web overall deadline exceeded") from error
        raise
    finally:
        deadline_timer.cancel()
        connection.close()


class _SearchResultParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self._active = None
        self._bing_result_depth = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = _text(attributes.get("class"))
        if tag == "li" and "b_algo" in classes:
            self._bing_result_depth = 1
        elif self._bing_result_depth:
            self._bing_result_depth += 1
        if tag != "a":
            return
        href = _text(attributes.get("href"))
        if ("result__a" in classes or self._bing_result_depth) and href:
            self._active = {"url": href, "title": ""}

    def handle_data(self, data):
        if self._active is not None:
            self._active["title"] += str(data or "")

    def handle_endtag(self, tag):
        if tag == "a" and self._active is not None:
            self.results.append(self._active)
            self._active = None
        if self._bing_result_depth:
            self._bing_result_depth -= 1


class _ContentParser(HTMLParser):
    _IGNORED = {"head", "script", "style", "nav", "header", "footer", "aside", "noscript"}
    _BLOCKS = {"article", "blockquote", "dd", "div", "dl", "dt", "h1", "h2", "h3", "h4", "h5", "h6", "li", "main", "p", "pre", "section", "td", "th"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self._preferred_depth = 0
        self._link_depth = 0
        self._link_chars = 0
        self._non_link_chars = 0
        self._all = []
        self._preferred = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self._IGNORED:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        if tag == "a":
            self._link_depth += 1
        if tag in {"main", "article"}:
            self._preferred_depth += 1
        if tag in self._BLOCKS or tag == "br":
            self._append(" ")

    def handle_startendtag(self, tag, attrs):
        if not self._ignored_depth and tag.lower() == "br":
            self._append(" ")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self._IGNORED:
            if self._ignored_depth:
                self._ignored_depth -= 1
            return
        if self._ignored_depth:
            return
        if tag == "a" and self._link_depth:
            self._link_depth -= 1
        if tag in self._BLOCKS:
            self._append(" ")
        if tag in {"main", "article"} and self._preferred_depth:
            self._preferred_depth -= 1

    def handle_data(self, data):
        if not self._ignored_depth:
            self._append(data)
            if self._link_depth:
                self._link_chars += len(str(data or "").strip())
            else:
                self._non_link_chars += len(str(data or "").strip())

    def _append(self, value):
        self._all.append(value)
        if self._preferred_depth:
            self._preferred.append(value)

    def text(self):
        preferred = _SPACE_PATTERN.sub(" ", "".join(self._preferred)).strip()
        fallback = _SPACE_PATTERN.sub(" ", "".join(self._all)).strip()
        return preferred or fallback

    def navigation_only(self):
        return self._link_chars > 0 and self._non_link_chars == 0


def _search_target_url(value):
    raw = _text(value)
    parsed = urlparse(raw)
    if parsed.hostname and "duckduckgo.com" in _normalized(parsed.hostname):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target)
    return raw


def _default_searcher(query, timeout_seconds=None):
    failures = []
    for base_url in PUBLIC_WEB_SEARCH_URLS:
        try:
            search_page = _read_url(base_url + quote_plus(query), timeout_seconds=timeout_seconds)
        except Exception as error:
            failures.append(error)
            continue
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
        if output:
            return output
    if failures and len(failures) == len(PUBLIC_WEB_SEARCH_URLS):
        raise failures[-1]
    return []


def reset_public_web_research_state():
    """Clear process-local request state for deterministic tests only."""
    with _PUBLIC_WEB_LOCK:
        _PUBLIC_WEB_CACHE.clear()
        _PUBLIC_WEB_INFLIGHT.clear()
        _PUBLIC_WEB_REQUEST_TIMES.clear()


def _cached_or_permitted_request(cache_key, now, state=_DEFAULT_STATE):
    with state.lock:
        cached = state.cache.get(cache_key)
        if cached and cached[0] > now:
            return "cached", deepcopy(cached[1])
        if cached:
            state.cache.pop(cache_key, None)
        if cache_key in state.inflight:
            return "inflight", None
        while state.times and state.times[0] <= now - PUBLIC_WEB_RATE_WINDOW_SECONDS:
            state.times.popleft()
        if len(state.times) >= PUBLIC_WEB_MAX_REQUESTS_PER_WINDOW:
            return "rate_limited", None
        state.inflight.add(cache_key)
        state.times.append(now)
        return "permitted", None


def _finish_request(cache_key, now, result, state=_DEFAULT_STATE):
    with state.lock:
        state.inflight.discard(cache_key)
        if result.get("status") == "source_reference":
            while len(state.cache) >= PUBLIC_WEB_MAX_CACHE_ENTRIES:
                state.cache.pop(next(iter(state.cache)))
            state.cache[cache_key] = (now + PUBLIC_WEB_CACHE_TTL_SECONDS, deepcopy(result))


def _partial_result(limitation, reason_code="NO_CONTENT", next_actions=None, **metadata):
    result = {
        "sourceKey": PUBLIC_WEB_SOURCE_KEY,
        "status": "partial",
        "reasonCode": reason_code,
        "facts": [],
        "evidence": [],
        "evidenceRefs": [],
        "limitations": [limitation],
        "nextActions": list(next_actions or []),
    }
    result.update(metadata)
    return result


def _allowed_numbers(value):
    output = []
    for match in _NUMBER_PATTERN.finditer(_text(value)):
        number = match.group(0)
        if number not in output:
            output.append(number)
        if len(output) >= 60:
            break
    return output


def _public_content(page):
    parser = _ContentParser()
    try:
        parser.feed(str(page or ""))
        parser.close()
    except Exception:
        return "", False
    return parser.text(), parser.navigation_only()


def _content_problem(page, content, navigation_only=False):
    lowered = _normalized(content)
    raw = _normalized(page)
    challenge_phrases = (
        "verify you are human", "checking your browser", "attention required",
        "just a moment", "complete the security check", "please complete the captcha",
    )
    leading = lowered[:240]
    challenge_heading = re.match(r"^(?:captcha|access denied|security check)(?:\s*[:.!…-]|$)", lowered)
    if any(phrase in leading for phrase in challenge_phrases) or challenge_heading:
        return "ACCESS_CHALLENGE"
    empty_mount = re.search(r"<(?:div|main)[^>]+(?:id|class)=[\"'][^\"']*(?:app|root)[^\"']*[\"'][^>]*>\s*</(?:div|main)>", raw)
    if empty_mount and "<script" in raw and len(content) < 120:
        return "JS_SHELL"
    if not content or navigation_only:
        return "NO_CONTENT"
    return ""


def _snapshot(content, start, match):
    actual_start = start
    if match:
        located = content.casefold().find(match.casefold(), start)
        actual_start = located
    actual_start = min(actual_start, len(content))
    end = min(len(content), actual_start + PUBLIC_WEB_MAX_SUMMARY_CHARS)
    return content[actual_start:end], actual_start, end


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
    state=None,
    searcher=_default_searcher,
    fetcher=_read_url,
    clock=monotonic,
    checked_at_factory=lambda: datetime.now(timezone.utc).isoformat(),
):
    """Read a small public-web snapshot for a Codex-selected target."""
    state = state if state is not None else _DEFAULT_STATE
    request = intent if isinstance(intent, dict) else {}
    target = _text(request.get("target") or request.get("query"))
    parsed_target = urlparse(target)
    looks_like_url = bool(parsed_target.scheme or parsed_target.netloc)
    if not target:
        return _partial_result("Public web research requires a non-empty target.", "INVALID_TARGET")
    if looks_like_url and not _safe_public_url(target):
        return _partial_result("The selected page must be a safe public HTTPS URL of at most 2048 characters.", "INVALID_TARGET")
    if not looks_like_url and len(target) > PUBLIC_WEB_MAX_QUERY_CHARS:
        return _partial_result("The public web search query exceeds 240 characters.", "INVALID_QUERY")
    start = request.get("start", 0)
    if isinstance(start, bool) or not isinstance(start, int) or start < 0:
        return _partial_result("Continuation start must be a non-negative integer.", "INVALID_START")
    match = request.get("match", "")
    if match is None:
        match = ""
    if not isinstance(match, str) or len(match.strip()) > PUBLIC_WEB_MAX_MATCH_CHARS:
        return _partial_result("Match must be text of at most 120 characters.", "INVALID_MATCH")
    match = match.strip()
    now = float(clock())
    cache_key = (target.casefold(), start, match.casefold())
    admission, cached = _cached_or_permitted_request(cache_key, now, state)
    if admission == "cached":
        return cached
    if admission == "inflight":
        return _partial_result("An identical public web research request is already in progress; no duplicate request was sent.", "INFLIGHT")
    if admission == "rate_limited":
        return _partial_result("Public web research rate budget is exhausted; no external request was sent.", "RATE_LIMITED")
    direct_url = _safe_public_url(target)
    if direct_url:
        hits, search_error = ([{"url": direct_url, "title": "", "snippet": ""}], "")
    else:
        hits, search_error = _search_hits(searcher, target)
    if not hits:
        result = _partial_result(search_error or "Public web search returned no safe HTTPS result pages for this research query.", "SEARCH_FAILED" if search_error else "NO_RESULTS", ["Try a narrower query or provide a specific public HTTPS page."])
        _finish_request(cache_key, now, result, state)
        return result

    facts = []
    evidence = []
    refs = []
    numbers = []
    failures = []
    for hit in hits:
        try:
            page = fetcher(hit["url"], timeout_seconds=PUBLIC_WEB_TIMEOUT_SECONDS)
        except TimeoutError:
            failures.append(("READ_TIMEOUT", {}))
            continue
        except Exception:
            failures.append(("READ_ERROR", {}))
            continue
        if not isinstance(page, str):
            failures.append(("READ_ERROR", {}))
            continue
        content, navigation_only = _public_content(page)
        problem = _content_problem(page, content, navigation_only)
        if problem:
            failures.append((problem, {}))
            continue
        if start >= len(content):
            failures.append(("END_OF_CONTENT", {
                "totalChars": len(content), "requestedStart": start, "end": len(content),
            }))
            continue
        if match and content.casefold().find(match.casefold(), start) < 0:
            failures.append(("MATCH_NOT_FOUND", {
                "totalChars": len(content), "requestedStart": start, "match": match,
            }))
            continue
        summary, actual_start, end = _snapshot(content, start, match)
        if not summary:
            failures.append(("NO_CONTENT", {}))
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
            "start": actual_start,
            "end": end,
            "totalChars": len(content),
            "truncated": end < len(content),
            "nextStart": end if end < len(content) else None,
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
        reason, failure_metadata = failures[0] if failures else ("NO_CONTENT", {})
        messages = {
            "JS_SHELL": "The selected page is a JavaScript-only shell with no readable article content.",
            "ACCESS_CHALLENGE": "The selected page returned an access challenge instead of article content.",
            "READ_TIMEOUT": "The selected page did not respond within the bounded read time.",
            "READ_ERROR": "The selected page could not be read within the public web safety limits.",
            "NO_CONTENT": "The selected page contained no readable article content.",
            "MATCH_NOT_FOUND": "The requested match text was not found in the readable content.",
            "END_OF_CONTENT": "The requested continuation starts at or after the end of the readable content.",
        }
        actions = {
            "JS_SHELL": ["Select a public server-rendered article or an official API source."],
            "ACCESS_CHALLENGE": ["Select another public source that does not require an interactive challenge."],
            "READ_TIMEOUT": ["Retry once or select a faster public source."],
            "READ_ERROR": ["Select another public HTTPS source."],
            "NO_CONTENT": ["Select a page with readable article text."],
            "MATCH_NOT_FOUND": ["Use a shorter match term or continue from a known offset."],
            "END_OF_CONTENT": ["Use an earlier continuation start."],
        }
        result = _partial_result(messages[reason], reason, actions[reason], **failure_metadata)
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
    _finish_request(cache_key, now, result, state)
    return result

"""Bounded, official-current-source adapter for Chickenbro."""

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

try:
    from .simulator_payload import SIMC_AGENT_CLASS_REGISTRY
except ImportError:
    from simulator_payload import SIMC_AGENT_CLASS_REGISTRY


CURRENT_SOURCE_KEY = "current_wow_sources"
CURRENT_SOURCE_TIMEOUT_SECONDS = 2
CURRENT_SOURCE_TOTAL_BUDGET_SECONDS = 10
CURRENT_SOURCE_CACHE_MAX_AGE_SECONDS = 900
_APPROVED_SOURCE_IDS = {"blizzard", "blizzard-forums"}
_APPROVED_SOURCE_HOSTS = {
    "blizzard": {"worldofwarcraft.blizzard.com", "news.blizzard.com"},
    "blizzard-forums": {"us.forums.blizzard.com"},
}
_PATCH_PATTERN = re.compile(r"(?<!\d)(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)(?!\d)")
_PTR_MARKERS = ("ptr", "public test realm", "测试服", "测试版", "beta")


def _normalized(value):
    return str(value or "").strip().lower()


def _utc_now(value=None):
    current = value if value is not None else datetime.now(timezone.utc)
    if not isinstance(current, datetime):
        raise ValueError("current-source clock must be a datetime")
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("current-source clock must be timezone-aware")
    return current.astimezone(timezone.utc)


def _parse_timestamp(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _approved_sources(sources):
    output = []
    for source in sources if isinstance(sources, (list, tuple)) else []:
        if not isinstance(source, dict):
            continue
        source_id = _normalized(source.get("sourceId"))
        if (
            source_id in _APPROVED_SOURCE_IDS
            and _normalized(source.get("sourceTier")) == "official"
            and _normalized(source.get("licenseStatus")) == "approved"
            and source.get("type") in {"blizzard_html", "blizzard_forum"}
        ):
            output.append(dict(source))
    return output


def _article_phase(article):
    event = article.get("versionEvent") if isinstance(article.get("versionEvent"), dict) else {}
    phase = _normalized(event.get("productPhase"))
    if phase in {"retail", "ptr"}:
        return phase
    text = " ".join(
        _normalized(article.get(field))
        for field in ("title", "summary", "originalTitle", "originalSummary", "originalBody", "channel")
    )
    tags = " ".join(_normalized(item) for item in (article.get("tags") or []))
    return "ptr" if any(marker in f"{text} {tags}" for marker in _PTR_MARKERS) else "retail"


def _article_patch_version(article):
    event = article.get("versionEvent") if isinstance(article.get("versionEvent"), dict) else {}
    patch = str(event.get("patchVersion") or "").strip()
    if patch:
        return patch
    text = " ".join(str(article.get(field) or "") for field in ("title", "summary", "originalTitle", "originalSummary"))
    match = _PATCH_PATTERN.search(text)
    return match.group(1) if match else ""


def _article_is_approved(article):
    source_id = _normalized(article.get("sourceId")) if isinstance(article, dict) else ""
    source_url = str(article.get("sourceUrl") or "") if isinstance(article, dict) else ""
    parsed = urlparse(source_url)
    return (
        isinstance(article, dict)
        and source_id in _APPROVED_SOURCE_IDS
        and _normalized(article.get("sourceTier")) == "official"
        and _normalized(article.get("licenseStatus")) == "approved"
        and parsed.scheme == "https"
        and _normalized(parsed.hostname) in _APPROVED_SOURCE_HOSTS[source_id]
    )


def _subject_terms(class_key, spec_key):
    for class_entry in SIMC_AGENT_CLASS_REGISTRY:
        if _normalized(class_entry.get("key")) != class_key:
            continue
        class_terms = {
            _normalized(value)
            for value in (class_entry.get("key"), class_entry.get("label"), *(class_entry.get("aliases") or []))
            if _normalized(value)
        }
        for spec_entry in class_entry.get("specs") or []:
            if _normalized(spec_entry.get("key")) != spec_key:
                continue
            spec_terms = {
                _normalized(value)
                for value in (spec_entry.get("key"), spec_entry.get("label"), *(spec_entry.get("aliases") or []))
                if _normalized(value)
            }
            return class_terms, spec_terms
    return set(), set()


def _article_matches_subject(article, subject):
    class_key = _normalized(subject.get("classKey"))
    spec_key = _normalized(subject.get("specKey"))
    if not class_key or not spec_key:
        return False
    class_terms, spec_terms = _subject_terms(class_key, spec_key)
    text = " ".join(
        _normalized(article.get(field))
        for field in ("title", "summary", "originalTitle", "originalSummary", "originalBody")
    )
    return bool(class_terms and spec_terms and any(term in text for term in class_terms) and any(term in text for term in spec_terms))


def _frame_scope(frame):
    frame = frame if isinstance(frame, dict) else {}
    subject = frame.get("subject") if isinstance(frame.get("subject"), dict) else {}
    scope = frame.get("scope") if isinstance(frame.get("scope"), dict) else {}
    return subject, {
        "productPhase": _normalized(scope.get("productPhase")) or "retail",
        "patchVersion": str(scope.get("patchVersion") or "").strip(),
    }


def _scope_matches(article, scope):
    if _article_phase(article) != scope["productPhase"]:
        return False
    article_patch = _article_patch_version(article)
    return not scope["patchVersion"] or article_patch == scope["patchVersion"]


def _cached_articles(article_loader, scope, now):
    if not callable(article_loader):
        return []
    try:
        loaded = article_loader()
    except Exception:
        return []
    eligible = []
    for article in loaded if isinstance(loaded, (list, tuple)) else []:
        if not _article_is_approved(article) or not _scope_matches(article, scope):
            continue
        captured_at = _parse_timestamp(article.get("checkedAt") or article.get("capturedAt"))
        if captured_at is None or (now - captured_at).total_seconds() < 0 or (now - captured_at).total_seconds() > CURRENT_SOURCE_CACHE_MAX_AGE_SECONDS:
            continue
        eligible.append(dict(article))
    return eligible


def _collect_articles(collector, approved_sources):
    if not callable(collector) or not approved_sources:
        return [], "current_source_unavailable"
    try:
        collected = collector(
            approved_sources,
            timeout=CURRENT_SOURCE_TIMEOUT_SECONDS,
            max_articles_per_source=1,
        )
    except TimeoutError:
        return [], "current_source_timeout"
    except Exception:
        return [], "current_source_unavailable"
    if isinstance(collected, tuple) and len(collected) == 2:
        articles, errors = collected
    else:
        articles, errors = collected, []
    normalized_articles = [dict(article) for article in articles if _article_is_approved(article)] if isinstance(articles, (list, tuple)) else []
    if normalized_articles:
        return normalized_articles, ""
    if any("timeout" in _normalized(error.get("error")) for error in errors if isinstance(error, dict)):
        return [], "current_source_timeout"
    return [], "current_source_unavailable"


def _safe_evidence_id(article):
    source_id = re.sub(r"[^a-z0-9-]+", "-", _normalized(article.get("sourceId"))).strip("-")
    article_id = re.sub(r"[^a-z0-9-]+", "-", _normalized(article.get("id"))).strip("-")
    return f"current.{source_id or 'official'}.{article_id or 'article'}"


def _summary(article):
    title = str(article.get("title") or article.get("originalTitle") or "Official current source").strip()
    body = str(article.get("summary") or article.get("originalSummary") or article.get("originalBody") or "").strip()
    return f"{title}: {body}"[:520].strip(": ")


def _source_reference_result(matching_articles, subject, scope, checked_at):
    facts = []
    evidence = []
    refs = []
    for article in matching_articles[:3]:
        evidence_id = _safe_evidence_id(article)
        facts.append(
            {
                "kind": "official_change",
                "classKey": _normalized(subject.get("classKey")),
                "specKey": _normalized(subject.get("specKey")),
                "productPhase": scope["productPhase"],
                "patchVersion": scope["patchVersion"],
                "summary": _summary(article),
                "checkedAt": checked_at,
            }
        )
        evidence.append(
            {
                "id": evidence_id,
                "sourceName": str(article.get("sourceName") or "Blizzard official source"),
                "sourceUrl": str(article.get("sourceUrl") or ""),
                "publishedAt": str(article.get("publishedAt") or ""),
                "checkedAt": checked_at,
                "productPhase": scope["productPhase"],
                "patchVersion": scope["patchVersion"],
                "sourceStatus": "official_current",
            }
        )
        refs.append(evidence_id)
    return {
        "sourceKey": CURRENT_SOURCE_KEY,
        "status": "source_reference",
        "facts": facts,
        "evidence": evidence,
        "evidenceRefs": refs,
        "limitations": ["comparative_strength_signal_missing"],
        "nextActions": [],
    }


def build_current_wow_sources_tool_result(
    frame,
    *,
    article_loader=None,
    collector=None,
    approved_sources=None,
    now=None,
):
    """Fetch only bounded approved official facts for a current-research frame."""
    current = _utc_now(now)
    subject, scope = _frame_scope(frame)
    if _normalized(frame.get("questionType") if isinstance(frame, dict) else "") != "current_research":
        return {
            "sourceKey": CURRENT_SOURCE_KEY,
            "status": "failed",
            "facts": [],
            "evidence": [],
            "evidenceRefs": [],
            "limitations": ["invalid_current_research_frame"],
            "nextActions": [],
        }
    approved = _approved_sources(approved_sources)
    articles = _cached_articles(article_loader, scope, current)
    collection_failure = ""
    if not articles:
        articles, collection_failure = _collect_articles(collector, approved)
    scoped_articles = [article for article in articles if _scope_matches(article, scope)]
    checked_at = current.isoformat().replace("+00:00", "Z")
    matching_articles = [article for article in scoped_articles if _article_matches_subject(article, subject)]
    if matching_articles:
        return _source_reference_result(matching_articles, subject, scope, checked_at)
    if scoped_articles:
        return {
            "sourceKey": CURRENT_SOURCE_KEY,
            "status": "partial",
            "facts": [
                {
                    "kind": "official_scope_checked",
                    "productPhase": scope["productPhase"],
                    "patchVersion": scope["patchVersion"],
                    "checkedAt": checked_at,
                }
            ],
            "evidence": [],
            "evidenceRefs": [],
            "limitations": ["subject_specific_official_change_missing", "comparative_strength_signal_missing"],
            "nextActions": [],
        }
    return {
        "sourceKey": CURRENT_SOURCE_KEY,
        "status": "failed",
        "facts": [],
        "evidence": [],
        "evidenceRefs": [],
        "limitations": [collection_failure or "current_source_unavailable"],
        "nextActions": [],
    }

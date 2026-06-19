import re
from urllib.parse import urlparse


PHASE_RULES = (
    ("ptr", ("ptr", "public test realm", "test realm", "/in-development", "/ptr")),
    ("beta", ("beta",)),
    ("alpha", ("alpha",)),
)

CONTENT_TYPE_RULES = (
    ("development_notes", ("development notes", "developer notes", "dev notes")),
    ("raid_testing", ("raid testing", "testing schedule")),
    ("class_tuning", ("class tuning", "class changes", "tuning")),
    ("hotfix", ("hotfix",)),
    ("content_update", ("content update",)),
)


def classify_version_event(title, summary="", source_url=""):
    text = f"{title or ''} {summary or ''} {source_url or ''}".lower()
    patch_version = ""
    patch_match = re.search(r"\b(?:patch\s*)?(\d{1,2}(?:\.\d+){1,2})\b", text)
    if patch_match:
        patch_version = patch_match.group(1)
    else:
        slug_match = re.search(r"\bpatch[-_/](\d{1,2})[-_/](\d{1,2})(?:[-_/](\d{1,2}))?\b", text)
        if slug_match:
            patch_version = ".".join(part for part in slug_match.groups() if part)
        elif re.search(r"\bmidnight\b", text):
            patch_version = "midnight"

    product_phase = ""
    for phase, terms in PHASE_RULES:
        if any(term in text for term in terms):
            product_phase = phase
            break
    if not product_phase and patch_version:
        product_phase = "live"

    content_type = ""
    for candidate, terms in CONTENT_TYPE_RULES:
        if any(term in text for term in terms):
            content_type = candidate
            break

    hostname = urlparse(source_url or "").hostname or ""
    if product_phase in {"ptr", "beta", "alpha"} and ("blizzard.com" in hostname or "forums.blizzard.com" in hostname):
        source_intent = "official_test_realm"
    elif product_phase in {"ptr", "beta", "alpha"}:
        source_intent = "test_realm_reference"
    elif "wowhead.com" in hostname or "icy-veins.com" in hostname:
        source_intent = "reference_media"
    elif "blizzard.com" in hostname:
        source_intent = "official_news"
    else:
        source_intent = "unknown"

    needs_review = not (patch_version or product_phase or content_type or source_intent in {"official_news", "reference_media"})
    return {
        "patchVersion": patch_version,
        "productPhase": product_phase or "unknown",
        "sourceIntent": source_intent,
        "contentType": content_type or "unknown",
        "needsClassificationReview": needs_review,
    }

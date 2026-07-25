"""Deterministic bounded rotation for observed-gear evidence work."""

from __future__ import annotations

from bisect import bisect_right
from typing import Any


def profile_identity(profile: Any) -> str:
    value = profile if isinstance(profile, dict) else {}
    existing = str(value.get("sourceIdentity") or "").strip()
    if existing.startswith("raiderio:") and len(existing) <= 512:
        return existing
    region = str(value.get("region") or "").strip().lower()
    realm = str(value.get("realmSlug") or value.get("realm") or "").strip().lower()
    character = str(value.get("characterName") or value.get("name") or "").strip().lower()
    if region and realm and character:
        return f"raiderio:{region}|{realm}|{character}"
    profile_url = str(value.get("profileUrl") or value.get("url") or "").strip().lower()
    return f"raiderio:url:{profile_url}" if profile_url else ""


def _unique_profiles_sorted_by_identity(profiles: Any) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for profile in profiles or []:
        if not isinstance(profile, dict):
            continue
        identity = profile_identity(profile)
        if identity and identity not in selected:
            selected[identity] = profile
    return [selected[identity] for identity in sorted(selected)]


def _next_profile_index(ordered: list[dict[str, Any]], after_profile_identity: str) -> int:
    if not ordered:
        return 0
    identities = [profile_identity(profile) for profile in ordered]
    after = str(after_profile_identity or "").strip()
    if not after:
        return 0
    if after in identities:
        return (identities.index(after) + 1) % len(identities)
    next_index = bisect_right(identities, after)
    return next_index if next_index < len(identities) else 0


def build_observed_profile_window(
    profiles: Any,
    *,
    after_profile_identity: str = "",
    profile_limit: int | None = None,
) -> dict[str, Any]:
    ordered = _unique_profiles_sorted_by_identity(profiles)
    if not ordered:
        return {
            "profiles": [],
            "availableProfileCount": 0,
            "cursor": {"afterProfileIdentity": str(after_profile_identity or "").strip()},
            "wrapped": False,
        }
    start = _next_profile_index(ordered, after_profile_identity)
    limit = len(ordered) if profile_limit is None else max(0, int(profile_limit))
    count = min(len(ordered), limit)
    selected = [ordered[(start + offset) % len(ordered)] for offset in range(count)]
    return {
        "profiles": selected,
        "availableProfileCount": len(ordered),
        "cursor": {
            "afterProfileIdentity": profile_identity(selected[-1]) if selected else str(after_profile_identity or "").strip()
        },
        "wrapped": bool(selected and start + len(selected) > len(ordered)),
    }

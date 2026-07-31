#!/usr/bin/env python3
"""Canonical identities for editable SimulationCraft crafted-stat options."""

from __future__ import annotations

import re
from typing import Any


CRAFTED_STAT_ID_LABELS = {
    "32": ("crit", "暴击"),
    "36": ("haste", "急速"),
    "40": ("versatility", "全能"),
    "49": ("mastery", "精通"),
}


def canonical_crafted_stats_value(
    value: Any,
    *,
    expected_count: int | None = None,
) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parts = [part.strip() for part in raw.split("/")]
    if (
        any(not part or not re.fullmatch(r"\d+", part) for part in parts)
        or len(set(parts)) != len(parts)
        or any(part not in CRAFTED_STAT_ID_LABELS for part in parts)
    ):
        return ""
    if expected_count is not None and len(parts) != expected_count:
        return ""
    if len(parts) not in {1, 2}:
        return ""
    return "/".join(sorted(parts, key=int))


def crafted_stats_option_identity(
    value: Any,
    *,
    expected_count: int | None = None,
) -> dict[str, Any] | None:
    canonical = canonical_crafted_stats_value(
        value,
        expected_count=expected_count,
    )
    if not canonical:
        return None
    stat_ids = canonical.split("/")
    keys = [CRAFTED_STAT_ID_LABELS[stat_id][0] for stat_id in stat_ids]
    labels = [CRAFTED_STAT_ID_LABELS[stat_id][1] for stat_id in stat_ids]
    key = "-".join(keys)
    return {
        "key": key,
        "optionId": f"crafted-stats-{key}",
        "label": " + ".join(labels),
        "value": canonical,
        "statIds": stat_ids,
    }

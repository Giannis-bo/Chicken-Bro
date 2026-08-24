"""Pure adapter for the S2 community-observed Exact pool.

Community rows are deliberately merged into the Gear snapshot only as
``exact_instance`` rows referenced by a sealed template.  They are never
eligible for ``project_s2_catalog_rows`` and carry an explicit observed truth
scope so a successful SimC replay cannot become an official Catalog fact.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

try:
    from .websim_payload import (
        normalize_item_stats,
        normalize_option_value,
        normalize_slot,
        observed_gear_simc_options,
    )
except ImportError:
    from websim_payload import (
        normalize_item_stats,
        normalize_option_value,
        normalize_slot,
        observed_gear_simc_options,
    )


class S2CommunityExactError(ValueError):
    """The community source cannot be bound to one immutable exact identity."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )


def _tokens(value: Any) -> list[str]:
    if isinstance(value, str):
        values = value.replace(",", "/").split("/")
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        values = value
    else:
        return []
    return [_text(item) for item in values if _text(item)]


def _simc_options(value: Any) -> dict[str, str]:
    raw = value if isinstance(value, Mapping) else {}
    options = observed_gear_simc_options(dict(raw))
    normalized = {}
    for key, item in options.items():
        token = normalize_option_value(item)
        if token:
            normalized[_text(key)] = token
    return dict(sorted(normalized.items()))


def _item_id(value: Mapping[str, Any]) -> str:
    return _text(value.get("itemId") or value.get("id"))


def _verified_staging_item_metadata(value: Mapping[str, Any], item_id: str) -> dict[str, Any]:
    payload = value.get("payload") if isinstance(value.get("payload"), Mapping) else {}
    metadata = payload.get("_metadata") if isinstance(payload.get("_metadata"), Mapping) else {}
    metadata_asset = metadata.get("gameAsset") if isinstance(metadata.get("gameAsset"), Mapping) else {}
    top_level_asset = payload.get("gameAsset") if isinstance(payload.get("gameAsset"), Mapping) else {}
    for source, asset in ((metadata, metadata_asset), (payload, top_level_asset)):
        icon_url = _text(source.get("iconUrl") or asset.get("iconUrl"))
        if (
            _text(asset.get("status")).lower() == "verified"
            and _text(asset.get("source")).lower() == "blizzard"
            and icon_url
        ):
            return {
                "iconUrl": icon_url,
                "gameAsset": {
                    "status": "verified",
                    "source": "blizzard",
                    "iconUrl": icon_url,
                },
                "itemId": item_id,
            }
    return {}


def _apply_verified_staging_item_metadata(
    item: dict[str, Any],
    staging_item: Mapping[str, Any],
    item_id: str,
) -> None:
    media = _verified_staging_item_metadata(staging_item, item_id)
    if not media:
        return
    payload = item.get("payload") if isinstance(item.get("payload"), Mapping) else {}
    payload = copy.deepcopy(dict(payload))
    metadata = (
        copy.deepcopy(dict(payload.get("_metadata")))
        if isinstance(payload.get("_metadata"), Mapping)
        else {}
    )
    existing_icon_url = _text(metadata.get("iconUrl"))
    if existing_icon_url and existing_icon_url != media["iconUrl"]:
        return
    metadata.update(media)
    payload["_metadata"] = metadata
    item["payload"] = payload


def _slot(value: Mapping[str, Any]) -> str:
    return normalize_slot(value.get("slot") or value.get("simcSlot"))


def _item_level(value: Mapping[str, Any]) -> int:
    return _int(value.get("itemLevel") or value.get("ilevel") or value.get("item_level"))


def _identity(value: Mapping[str, Any]) -> tuple[str, str, int, tuple[tuple[str, str], ...]]:
    options = _simc_options(value.get("simcOptions") or value)
    return (
        _item_id(value),
        _slot(value),
        _item_level(value),
        tuple(sorted(options.items())),
    )


def _stat_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    text = _text(value)
    if not text:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError, OverflowError):
        return None
    return int(number) if number.is_integer() else number


def _stats(value: Mapping[str, Any]) -> dict[str, int | float]:
    payload = value.get("payload") if isinstance(value.get("payload"), Mapping) else {}
    candidates = (
        payload.get("resolvedStats"),
        payload.get("itemStats"),
        value.get("staticStats"),
    )
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            result = {}
            for key, amount in candidate.items():
                key = _text(key)
                amount = _stat_number(amount)
                if key and amount is not None:
                    result[key] = amount
        elif isinstance(candidate, Sequence) and not isinstance(candidate, (bytes, bytearray, str)):
            result = {}
            for stat in normalize_item_stats(list(candidate)):
                key = _text(stat.get("key") or stat.get("label"))
                amount = _stat_number(stat.get("value"))
                if key and amount is not None:
                    result[key] = amount
        else:
            continue
        if result:
            return dict(sorted(result.items()))
    return {}


def _profile_urls(value: Mapping[str, Any]) -> set[str]:
    payload = value.get("payload") if isinstance(value.get("payload"), Mapping) else {}
    urls = set()
    for source in (value, payload):
        for key in ("profileUrl", "sourceProfileUrl", "sourceUrl", "url"):
            token = _text(source.get(key))
            if token:
                urls.add(token)
        for ref in source.get("observedProfileRefs") or []:
            if not isinstance(ref, Mapping):
                continue
            for key in ("profileUrl", "sourceProfileUrl", "sourceUrl", "url"):
                token = _text(ref.get(key))
                if token:
                    urls.add(token)
    return urls


def _staging_variant_index(
    staging_variants: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], list[Mapping[str, Any]]]:
    index: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for raw in staging_variants:
        if not isinstance(raw, Mapping):
            continue
        if _text(raw.get("sourceType")).lower() != "observed_profile":
            continue
        if _text(raw.get("status")).lower() != "verified" or raw.get("blockers"):
            continue
        if not _stats(raw):
            continue
        key = (_item_id(raw), _slot(raw))
        if all(key):
            index.setdefault(key, []).append(raw)
    return index


def _parse_datetime(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _variant_identity_hash(row: Mapping[str, Any]) -> str:
    payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
    capability_overrides = payload.get("capabilityOverrides") or {}
    if isinstance(capability_overrides, Mapping):
        capability_overrides = {
            _text(key): value
            for key, value in capability_overrides.items()
            if _text(key) and value is not False and value is not None
        }
    return "sha256:" + hashlib.sha256(
        json.dumps(
            {
                "identity": _identity(row),
                "stats": _stats(row),
                "capabilityOverrides": capability_overrides,
                "enhancementManagement": payload.get("enhancementManagement") or {},
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _template_items(templates: Sequence[Any]) -> list[tuple[int, int, dict[str, Any]]]:
    result = []
    for template_index, raw_template in enumerate(templates):
        if not isinstance(raw_template, Mapping):
            continue
        items = raw_template.get("gearItems")
        if not isinstance(items, list):
            continue
        for item_index, raw_item in enumerate(items):
            if isinstance(raw_item, Mapping):
                result.append((template_index, item_index, dict(raw_item)))
    return result


def _choose_variant(
    raw_item: Mapping[str, Any],
    staging_variants: Sequence[Mapping[str, Any]],
    *,
    staging_index: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]] | None = None,
) -> Mapping[str, Any]:
    item_id = _item_id(raw_item)
    slot = _slot(raw_item)
    requested_key = _text(raw_item.get("variantKey"))
    target_identity = _identity(raw_item)
    candidates = []
    rows = (
        staging_index.get((item_id, slot), [])
        if staging_index is not None
        else staging_variants
    )
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        if _text(raw.get("sourceType")).lower() != "observed_profile":
            continue
        if _text(raw.get("status")).lower() != "verified" or raw.get("blockers"):
            continue
        if _item_id(raw) != item_id or _slot(raw) != slot:
            continue
        if not _stats(raw):
            continue
        if requested_key:
            if _text(raw.get("variantKey")) != requested_key:
                continue
        elif _identity(raw) != target_identity:
            continue
        candidates.append(raw)
    if requested_key and not candidates:
        raise S2CommunityExactError(
            f"community exact source missing for {item_id}/{requested_key}"
        )
    if not requested_key and not candidates:
        raise S2CommunityExactError(
            f"community exact identity missing for {item_id}/{slot}/{_item_level(raw_item)}"
        )
    by_identity = {_variant_identity_hash(row): row for row in candidates}
    if len(by_identity) != 1:
        profile_urls = _profile_urls(raw_item)
        scoped = [
            row for row in candidates
            if profile_urls.intersection(_profile_urls(row))
        ]
        scoped_identity = {_variant_identity_hash(row): row for row in scoped}
        if len(scoped_identity) == 1:
            return next(iter(scoped_identity.values()))
        raise S2CommunityExactError(
            f"community exact identity is ambiguous for {item_id}/{slot}"
        )
    return next(iter(by_identity.values()))


def select_s2_bindable_community_templates(
    templates: Sequence[Any],
    staging_variants: Sequence[Mapping[str, Any]],
    *,
    now: Any = None,
) -> list[dict[str, Any]]:
    """Keep only fresh, complete templates whose observed rows are bindable.

    Community template completeness is a slot-level claim.  Exact Registry
    publication additionally requires every referenced observed variant to be
    verified with stats, so stale or unbindable templates must not enter a
    release candidate merely because their slot coverage is complete.
    """

    current = _parse_datetime(now) if now is not None else datetime.now(timezone.utc)
    if current is None:
        current = datetime.now(timezone.utc)
    staging_index = _staging_variant_index(staging_variants)
    selected: list[dict[str, Any]] = []
    for raw_template in templates or []:
        if not isinstance(raw_template, Mapping):
            continue
        if _text(raw_template.get("status")).lower() != "complete":
            continue
        expires_at = _parse_datetime(raw_template.get("expiresAt"))
        if expires_at is None or expires_at <= current:
            continue
        items = raw_template.get("gearItems")
        if not isinstance(items, list) or not items:
            continue
        try:
            for raw_item in items:
                if not isinstance(raw_item, Mapping):
                    raise S2CommunityExactError("community template item is invalid")
                _choose_variant(
                    raw_item,
                    staging_variants,
                    staging_index=staging_index,
                )
        except S2CommunityExactError:
            continue
        selected.append(copy.deepcopy(dict(raw_template)))
    return selected


def _normalize_exact_variant(raw: Mapping[str, Any]) -> dict[str, Any]:
    row = copy.deepcopy(dict(raw))
    payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
    payload = copy.deepcopy(dict(payload))
    stats = _stats(row)
    options = _simc_options(row.get("simcOptions"))
    row.update({
        "rowFamily": "exact_instance",
        "sourceVariantKey": _text(row.get("variantKey")),
        "bonusIds": _tokens(options.get("bonus_id")),
        "staticStats": stats,
        "status": "verified",
        "blockers": [],
    })
    payload.update({
        "truthScope": "community_observed",
        "officialFactStatus": "UNVERIFIED",
        "membershipKind": "imported_exact",
        "editable": False,
        "resolvedStats": stats,
        "itemStats": stats,
        "simcOptions": options,
    })
    gem_count = len(_tokens(options.get("gem_id")))
    if gem_count:
        capability_overrides = (
            copy.deepcopy(dict(payload.get("capabilityOverrides")))
            if isinstance(payload.get("capabilityOverrides"), Mapping)
            else {}
        )
        existing_socket_count = _int(capability_overrides.get("socketCount"))
        if existing_socket_count < gem_count:
            capability_overrides["socketCount"] = gem_count
        payload["capabilityOverrides"] = capability_overrides
        payload["socketEvidence"] = {
            "schemaRevision": "gear-socket-fact-v1",
            "authorityRevision": "gear-capability-matrix-v2",
            "minimumTotal": max(existing_socket_count, gem_count),
            "claims": [{
                "minimumTotal": gem_count,
                "scope": "exact_variant",
                "source": "observed_gem_occupancy",
                "sourceRevision": _text(row.get("updatedAt")) or "community-observed",
            }],
        }
    row["payload"] = payload
    row["simcOptions"] = options
    return row


def _normalize_source(raw: Mapping[str, Any], item_id: str) -> dict[str, Any]:
    row = copy.deepcopy(dict(raw))
    row["itemId"] = item_id
    row["sourceType"] = "observed_profile"
    row["sourceKey"] = _text(row.get("sourceKey")) or "community_observed"
    payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
    payload = copy.deepcopy(dict(payload))
    payload.update({
        "truthScope": "community_observed",
        "officialFactStatus": "UNVERIFIED",
        "membershipKind": "imported_exact",
        "status": "verified",
    })
    row["payload"] = payload
    return row


def _source_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        _text(row.get("sourceId")),
        _text(row.get("itemId")),
        _text(row.get("sourceKey")),
    )


def merge_s2_community_exact_snapshot(
    base_snapshot: Mapping[str, Any],
    community_snapshot: Mapping[str, Any],
    community_templates: Sequence[Any],
) -> dict[str, Any]:
    """Bind current community templates to staging exact rows and merge them.

    The returned snapshot contains only rows referenced by the supplied
    templates.  Unreferenced observed rows are deliberately dropped so the
    immutable candidate cannot silently grow an observed equipment catalog.
    """

    base = copy.deepcopy(dict(base_snapshot))
    source = community_snapshot if isinstance(community_snapshot, Mapping) else {}
    staging_variants = [
        dict(row) for row in source.get("variants") or [] if isinstance(row, Mapping)
    ]
    staging_items = {
        _item_id(row): dict(row)
        for row in source.get("items") or []
        if isinstance(row, Mapping) and _item_id(row)
    }
    staging_sources = [
        dict(row) for row in source.get("sources") or [] if isinstance(row, Mapping)
    ]
    staging_index = _staging_variant_index(staging_variants)

    bound_templates = copy.deepcopy(list(community_templates or []))
    selected_variants: dict[tuple[str, str], dict[str, Any]] = {}
    selected_item_ids: set[str] = set()
    for template_index, item_index, raw_item in _template_items(bound_templates):
        selected = _normalize_exact_variant(
            _choose_variant(
                raw_item,
                staging_variants,
                staging_index=staging_index,
            )
        )
        item_id = _item_id(selected)
        variant_key = _text(selected.get("variantKey"))
        selected_key = (item_id, variant_key)
        existing = selected_variants.get(selected_key)
        if existing is not None and _variant_identity_hash(existing) != _variant_identity_hash(selected):
            raise S2CommunityExactError(
                f"community exact identity conflicts for {item_id}/{variant_key}"
            )
        selected_variants[selected_key] = selected
        selected_item_ids.add(item_id)
        item = bound_templates[template_index]["gearItems"][item_index]
        item["variantKey"] = variant_key
        if not _item_level(item):
            item["itemLevel"] = _int(selected.get("itemLevel"))

    existing_variant_keys = {
        (_item_id(row), _text(row.get("variantKey")))
        for row in base.get("variants") or []
        if isinstance(row, Mapping)
    }
    for key, row in sorted(selected_variants.items()):
        if key in existing_variant_keys:
            raise S2CommunityExactError(
                f"community exact variant collides with base snapshot: {key[0]}/{key[1]}"
            )
        base.setdefault("variants", []).append(row)

    existing_item_ids = {
        _item_id(row) for row in base.get("items") or [] if isinstance(row, Mapping)
    }
    base_items_by_id = {
        _item_id(row): row
        for row in base.get("items") or []
        if isinstance(row, Mapping) and _item_id(row)
    }
    for item_id in sorted(selected_item_ids - existing_item_ids):
        item = copy.deepcopy(staging_items.get(item_id) or {})
        if not item:
            raise S2CommunityExactError(f"community exact item source missing for {item_id}")
        payload = item.get("payload") if isinstance(item.get("payload"), Mapping) else {}
        payload = copy.deepcopy(dict(payload))
        payload.update({
            "truthScope": "community_observed",
            "officialFactStatus": "UNVERIFIED",
            "membershipKind": "imported_exact",
            "editable": False,
        })
        item["payload"] = payload
        _apply_verified_staging_item_metadata(item, item, item_id)
        base.setdefault("items", []).append(item)

    # Selected community rows may refer to an item already present in the
    # official base snapshot.  Preserve the existing item facts, but carry
    # forward only an exact, verified Blizzard media assertion from staging so
    # downstream community-import evidence can prove the rendered identity.
    for item_id in sorted(selected_item_ids & existing_item_ids):
        staging_item = staging_items.get(item_id)
        target = base_items_by_id.get(item_id)
        if not isinstance(staging_item, Mapping) or not isinstance(target, dict):
            continue
        _apply_verified_staging_item_metadata(target, staging_item, item_id)

    existing_source_keys = {_source_key(row) for row in base.get("sources") or [] if isinstance(row, Mapping)}
    selected_source_rows = [
        _normalize_source(row, _item_id(row))
        for row in staging_sources
        if _item_id(row) in selected_item_ids
        and _text(row.get("sourceType")).lower() == "observed_profile"
    ]
    for row in sorted(selected_source_rows, key=lambda value: _source_key(value)):
        key = _source_key(row)
        if key in existing_source_keys:
            continue
        if not key[0]:
            continue
        base.setdefault("sources", []).append(row)
        existing_source_keys.add(key)

    base["items"] = sorted(base.get("items") or [], key=lambda row: _item_id(row))
    base["sources"] = sorted(base.get("sources") or [], key=lambda row: _source_key(row))
    base["variants"] = sorted(
        base.get("variants") or [],
        key=lambda row: (_item_id(row), _text(row.get("variantKey")), _text(row.get("variantId"))),
    )
    return {
        "snapshot": base,
        "templates": bound_templates,
        "binding": {
            "schemaRevision": "s2-community-exact-binding-v1",
            "templateCount": len(bound_templates),
            "selectedExactRowCount": len(selected_variants),
            "selectedItemCount": len(selected_item_ids),
            "selectedSourceCount": len(selected_source_rows),
            "truthScope": "community_observed",
            "catalogExpansion": False,
        },
    }


__all__ = (
    "S2CommunityExactError",
    "merge_s2_community_exact_snapshot",
    "select_s2_bindable_community_templates",
)

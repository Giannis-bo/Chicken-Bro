"""Candidate-only Season 2 gem, enchant, and embellishment option catalog."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


SCHEMA_REVISION = "gear-enhancement-option-catalog-v1"
OPTION_REVISION_PREFIX = "s2-options:sha256:"
S2_SEASON_PREFIX = "season-midnight-season-2:"
_OPTION_FIELDS = (
    ("gem_id", "socket"),
    ("enchant_id", "enchant"),
    ("embellishment", "embellishment"),
)


def _text(value: Any) -> str:
    return str(value or "").strip()


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


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _tokens(value: Any) -> list[str]:
    if isinstance(value, str):
        raw = value.split("/")
    elif isinstance(value, (list, tuple)):
        raw = list(value)
    else:
        return []
    return [_text(token) for token in raw if _text(token)]


def _binding(binding: Any) -> tuple[str, list[dict[str, str]]]:
    row = binding if isinstance(binding, Mapping) else {}
    season_revision = _text(row.get("seasonRevision"))
    problems: list[dict[str, str]] = []
    if _text(row.get("seasonId")) != "midnight-season-2":
        problems.append({
            "code": "ENHANCEMENT_SEASON_ID_INVALID",
            "message": "Enhancement catalog requires midnight-season-2.",
        })
    if not season_revision.startswith(S2_SEASON_PREFIX):
        problems.append({
            "code": "ENHANCEMENT_SEASON_REVISION_INVALID",
            "message": "Enhancement catalog requires an S2 season revision.",
        })
    if _text(row.get("scope")) != "end_game":
        problems.append({
            "code": "ENHANCEMENT_SCOPE_INVALID",
            "message": "Enhancement catalog requires end_game scope.",
        })
    if _text(row.get("status")).lower() != "verified":
        problems.append({
            "code": "ENHANCEMENT_BINDING_NOT_VERIFIED",
            "message": "Enhancement catalog binding is not verified.",
        })
    return season_revision, problems


def _official_index(official_items: Any) -> dict[str, dict[str, Any]]:
    if isinstance(official_items, Mapping):
        return {
            _text(key): dict(value)
            for key, value in official_items.items()
            if _text(key) and isinstance(value, Mapping)
        }
    if isinstance(official_items, list):
        return {
            _text(row.get("itemId") or row.get("id")): dict(row)
            for row in official_items
            if isinstance(row, Mapping)
            and _text(row.get("itemId") or row.get("id"))
        }
    return {}


def _option_from_item(
    token: str,
    option_type: str,
    item: Mapping[str, Any],
    *,
    season_revision: str,
) -> dict[str, Any]:
    management_mode = _text(item.get("managementMode")).lower()
    if option_type == "embellishment" and not management_mode:
        management_mode = "editor_managed"
    editor_managed = management_mode == "editor_managed"
    option_key_type = "gem" if option_type == "socket" else option_type
    return {
        "optionId": f"s2-{option_type}-{token}",
        "optionKey": f"{option_key_type}-{token}",
        "optionType": option_type,
        "token": token,
        "seasonRevision": season_revision,
        "name": _text(item.get("name")) or token,
        "statSummary": _text(item.get("statSummary")),
        "sourceStatus": _text(item.get("sourceStatus")).lower(),
        "status": "verified",
        "managementMode": management_mode,
        "editorManaged": editor_managed,
        "isVisible": editor_managed,
        "simcOptions": {
            "gem_id": token
        }
        if option_type == "socket"
        else {
            "enchant_id": token
        }
        if option_type == "enchant"
        else {"embellishment": token},
        "sourceRefs": sorted(
            {
                _text(value)
                for value in item.get("sourceRefs") or []
                if _text(value)
            }
        ),
        "payload": {
            "displayName": _text(item.get("name")) or token,
            "displayLabel": _text(item.get("statSummary")),
            "statSummary": _text(item.get("statSummary")),
            "metadataStatus": "verified",
        },
    }


def build_enhancement_option_catalog(
    *,
    season_binding: Any,
    official_items: Any,
    variants: Any,
) -> dict[str, Any]:
    """Build one normalized S2 enhancement catalog; never drop raw tokens."""

    season_revision, problems = _binding(season_binding)
    official = _official_index(official_items)
    rows = variants if isinstance(variants, list) else []
    if not isinstance(variants, list):
        problems.append({
            "code": "ENHANCEMENT_VARIANTS_MALFORMED",
            "message": "Enhancement variants must be a list.",
        })
    option_map: dict[str, dict[str, Any]] = {}
    blocked_options: list[dict[str, Any]] = []
    observed_pairs: set[tuple[str, str]] = set()
    for raw_variant in rows:
        variant = dict(raw_variant) if isinstance(raw_variant, Mapping) else {}
        variant_revision = _text(variant.get("seasonRevision"))
        if variant_revision != season_revision:
            problems.append({
                "code": "ENHANCEMENT_SEASON_REVISION_MISMATCH",
                "message": "Enhancement variant belongs to another season revision.",
            })
            continue
        simc_options = variant.get("simcOptions")
        if not isinstance(simc_options, Mapping):
            continue
        socket_count = variant.get("socketCount")
        try:
            capacity = int(socket_count)
        except (TypeError, ValueError):
            capacity = 0
        gem_tokens = _tokens(simc_options.get("gem_id"))
        if len(gem_tokens) > capacity:
            blocked_options.append({
                "variantKey": _text(variant.get("variantKey")),
                "code": "ENHANCEMENT_SOCKET_CAPACITY_EXCEEDED",
                "token": _text(simc_options.get("gem_id")),
            })
            problems.append({
                "code": "ENHANCEMENT_SOCKET_CAPACITY_EXCEEDED",
                "message": "Gem sequence exceeds the official socket capacity.",
            })
            continue
        for field, option_type in _OPTION_FIELDS:
            tokens = _tokens(simc_options.get(field))
            for token in tokens:
                pair = (option_type, token)
                if pair in observed_pairs:
                    continue
                observed_pairs.add(pair)
                item = official.get(token)
                if not item:
                    blocked_options.append({
                        "variantKey": _text(variant.get("variantKey")),
                        "code": "ENHANCEMENT_OFFICIAL_METADATA_MISSING",
                        "optionType": option_type,
                        "token": token,
                    })
                    problems.append({
                        "code": "ENHANCEMENT_OFFICIAL_METADATA_MISSING",
                        "message": f"Official metadata is missing for {option_type} {token}.",
                    })
                    continue
                item_revision = _text(item.get("seasonRevision"))
                item_status = _text(item.get("sourceStatus")).lower()
                item_class = _text(item.get("itemClass")).lower()
                if item_revision != season_revision:
                    problems.append({
                        "code": "ENHANCEMENT_SEASON_REVISION_MISMATCH",
                        "message": f"Official metadata for {token} belongs to another season revision.",
                    })
                    continue
                if item_status != "verified":
                    problems.append({
                        "code": "ENHANCEMENT_OFFICIAL_METADATA_NOT_VERIFIED",
                        "message": f"Official metadata for {token} is not verified.",
                    })
                    continue
                if item_class != option_type and not (
                    option_type == "socket" and item_class == "gem"
                ):
                    problems.append({
                        "code": "ENHANCEMENT_OFFICIAL_TYPE_MISMATCH",
                        "message": f"Official metadata type for {token} does not match {option_type}.",
                    })
                    continue
                option = _option_from_item(
                    token,
                    option_type,
                    item,
                    season_revision=season_revision,
                )
                option_map[option["optionKey"]] = option

    options = [option_map[key] for key in sorted(option_map)]
    option_identity = {
        "schemaRevision": SCHEMA_REVISION,
        "seasonRevision": season_revision,
        "options": options,
        "blockedOptions": sorted(
            (_canonical(row) for row in blocked_options),
            key=lambda row: (
                _text(row.get("code")),
                _text(row.get("optionType")),
                _text(row.get("token")),
                _text(row.get("variantKey")),
            ),
        ),
    }
    option_revision = OPTION_REVISION_PREFIX + hashlib.sha256(
        _canonical_bytes(option_identity)
    ).hexdigest()
    blocker_codes = sorted(
        {
            _text(problem.get("code"))
            for problem in problems
            if _text(problem.get("code"))
        }
    )
    return {
        "schemaRevision": SCHEMA_REVISION,
        "status": "verified" if not blocker_codes else "blocked",
        "seasonRevision": season_revision,
        "optionRevision": option_revision,
        "options": options,
        "blockedOptions": sorted(
            (_canonical(row) for row in blocked_options),
            key=lambda row: (
                _text(row.get("code")),
                _text(row.get("optionType")),
                _text(row.get("token")),
                _text(row.get("variantKey")),
            ),
        ),
        "blockerCodes": blocker_codes,
        "problems": sorted(
            (_canonical(problem) for problem in problems),
            key=lambda problem: (
                _text(problem.get("code")),
                _text(problem.get("message")),
            ),
        )[:40],
        "coverage": {
            "observedVariantCount": len(rows),
            "optionCount": len(options),
            "blockedOptionCount": len(blocked_options),
        },
        "management": {
            "socket": "editor_managed",
            "enchant": "editor_managed",
            "embellishment": "editor_managed_or_source_only",
        },
    }


def validate_enhancement_option_catalog(value: Any) -> list[dict[str, str]]:
    row = value if isinstance(value, Mapping) else {}
    problems: list[dict[str, str]] = []
    if _text(row.get("schemaRevision")) != SCHEMA_REVISION:
        problems.append({"code": "ENHANCEMENT_CATALOG_SCHEMA_INVALID", "message": "Schema revision is invalid."})
    if not _text(row.get("seasonRevision")).startswith(S2_SEASON_PREFIX):
        problems.append({"code": "ENHANCEMENT_SEASON_REVISION_INVALID", "message": "Season revision is invalid."})
    if not _text(row.get("optionRevision")).startswith(OPTION_REVISION_PREFIX):
        problems.append({"code": "ENHANCEMENT_OPTION_REVISION_INVALID", "message": "Option revision is invalid."})
    if not isinstance(row.get("options"), list):
        problems.append({"code": "ENHANCEMENT_OPTIONS_MALFORMED", "message": "Options must be a list."})
    return problems


__all__ = (
    "OPTION_REVISION_PREFIX",
    "SCHEMA_REVISION",
    "build_enhancement_option_catalog",
    "validate_enhancement_option_catalog",
)

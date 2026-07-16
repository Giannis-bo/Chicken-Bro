"""Pure, release-time socket capacity fact derivation.

Every evidence source contributes a proven lower bound for total socket capacity.
Compatible claims are merged with ``max`` and are never added together.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Mapping


LEGACY_CAPABILITY_REVISION = "gear-capability-matrix-v1"
CAPABILITY_REVISION = "gear-capability-matrix-v2"
SUPPORTED_CAPABILITY_REVISIONS = (LEGACY_CAPABILITY_REVISION, CAPABILITY_REVISION)
SOCKET_FACT_SCHEMA_REVISION = "gear-socket-fact-v1"
SOCKET_ELIGIBILITY_SCHEMA_REVISION = "gear-socket-eligibility-v1"

__all__ = (
    "LEGACY_CAPABILITY_REVISION",
    "CAPABILITY_REVISION",
    "SUPPORTED_CAPABILITY_REVISIONS",
    "SOCKET_FACT_SCHEMA_REVISION",
    "SOCKET_ELIGIBILITY_SCHEMA_REVISION",
    "is_verified_radiant_jewelbinder_socket",
    "count_payload_socket_entries",
    "parse_simc_socket_bonus_minimums",
    "derive_item_socket_fact",
    "derive_variant_socket_fact",
    "materialize_gear_socket_facts",
)


_MIDNIGHT_SEASON_ONE_REVISIONS = frozenset(
    {
        "midnight-1",
        "midnight-1-r1",
        "midnight-season-1",
        "retail-12.0-s1-active",
        "season-mn-1",
    }
)
_MIDNIGHT_SEASON_ONE_REVISION_PATTERNS = (
    re.compile(r"season-midnight-season-1-[0-9a-f]{12}"),
    re.compile(r"season-17-[0-9a-f]{12}"),
)
_MIDNIGHT_JEWELRY_SLOTS = frozenset({"neck", "finger", "finger1", "finger2"})
_RADIANT_JEWELBINDER_SLOTS = frozenset({"head", "wrist", "waist"})
_ACTIVE_PVE_CATALOG_SOURCE_TYPES = frozenset(
    {"dungeon", "mythic_plus", "mythicplus", "raid", "tier_set"}
)
_SOCKET_PAYLOAD_KEYS = frozenset({"socket", "sockets", "gemsockets"})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _minimum_total(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        total = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return total if total > 0 else 0


def _normalized_key(value: Any) -> str:
    return re.sub(r"[\s_-]+", "", _text(value).lower())


def _normalized_slot(value: Any) -> str:
    slot = re.sub(r"[\s-]+", "_", _text(value).lower())
    aliases = {
        "belt": "waist",
        "bracer": "wrist",
        "bracers": "wrist",
        "helm": "head",
        "helmet": "head",
        "ring": "finger",
        "ring1": "finger1",
        "ring2": "finger2",
    }
    return aliases.get(slot, slot)


def _is_midnight_season_one_revision(value: Any) -> bool:
    revision = _text(value)
    return revision in _MIDNIGHT_SEASON_ONE_REVISIONS or any(
        pattern.fullmatch(revision)
        for pattern in _MIDNIGHT_SEASON_ONE_REVISION_PATTERNS
    )


def _row_slot(row: Mapping[str, Any]) -> str:
    return _normalized_slot(
        row.get("slot")
        or row.get("simcSlot")
        or row.get("slotKey")
        or row.get("equipmentSlot")
    )


def _claim(
    *,
    minimum_total: Any,
    scope: str,
    source: str,
    source_revision: Any,
) -> dict[str, Any] | None:
    total = _minimum_total(minimum_total)
    if not total:
        return None
    return {
        "minimumTotal": total,
        "scope": scope,
        "source": source,
        "sourceRevision": _text(source_revision),
    }


def _socket_fact(claims: list[dict[str, Any]]) -> dict[str, Any]:
    valid_claims = [claim for claim in claims if _minimum_total(claim.get("minimumTotal"))]
    return {
        "schemaRevision": SOCKET_FACT_SCHEMA_REVISION,
        "authorityRevision": CAPABILITY_REVISION,
        "minimumTotal": max(
            (_minimum_total(claim.get("minimumTotal")) for claim in valid_claims),
            default=0,
        ),
        "claims": valid_claims,
    }


def _source_revision(row: Mapping[str, Any], fallback: str) -> str:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    return _text(
        row.get("sourceRevision")
        or row.get("payloadRevision")
        or payload.get("sourceRevision")
        or row.get("updatedAt")
        or fallback
    )


def _pvp_flags(item: Mapping[str, Any]) -> list[Any]:
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    flags: list[Any] = []
    for parent in (item, payload):
        for key in ("isPvp", "isPvP", "pvp"):
            if key in parent:
                flags.append(parent.get(key))
    return flags


def _socket_eligibility_proves_non_pvp(
    value: Any,
    season_revision: str,
) -> bool:
    eligibility = value if isinstance(value, dict) else {}
    revision = _text(season_revision)
    source_ids = eligibility.get("sourceIds")
    source_types = eligibility.get("sourceTypes")
    return (
        bool(revision)
        and eligibility.get("schemaRevision") == SOCKET_ELIGIBILITY_SCHEMA_REVISION
        and eligibility.get("status") == "verified"
        and eligibility.get("eligibility") == "active_pve_catalog"
        and _text(eligibility.get("sourceRevision")) == revision
        and isinstance(source_ids, list)
        and bool(source_ids)
        and all(bool(_text(source_id)) for source_id in source_ids)
        and isinstance(source_types, list)
        and bool(source_types)
        and all(
            _text(source_type).lower() in _ACTIVE_PVE_CATALOG_SOURCE_TYPES
            for source_type in source_types
        )
    )


def is_verified_radiant_jewelbinder_socket(
    item: Any,
    season_revision: str,
) -> bool:
    """Verify one sealed current-season Radiant Jewelbinder socket fact.

    This deliberately recognizes only the seasonal, PvE-catalog-backed
    Jewelbinder slot.  It does not turn a generic one-socket item into a
    special puncher slot, and it never infers eligibility from an observed gem.
    """

    row = item if isinstance(item, Mapping) else {}
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    revision = _text(season_revision)
    eligibility = (
        row.get("socketEligibility")
        if isinstance(row.get("socketEligibility"), dict)
        else payload.get("socketEligibility")
    )
    evidence = (
        row.get("socketEvidence")
        if isinstance(row.get("socketEvidence"), dict)
        else payload.get("socketEvidence")
    )
    claims = evidence.get("claims") if isinstance(evidence, dict) else []
    return (
        _row_slot(row) in _RADIANT_JEWELBINDER_SLOTS
        and _socket_eligibility_proves_non_pvp(eligibility, revision)
        and isinstance(evidence, dict)
        and evidence.get("schemaRevision") == SOCKET_FACT_SCHEMA_REVISION
        and evidence.get("authorityRevision") == CAPABILITY_REVISION
        and _minimum_total(evidence.get("minimumTotal")) == 1
        and isinstance(claims, list)
        and any(
            isinstance(claim, dict)
            and _minimum_total(claim.get("minimumTotal")) == 1
            and claim.get("scope") == "season_slot"
            and claim.get("source") == "midnight_s1_radiant_jewelbinder"
            and _text(claim.get("sourceRevision")) == revision
            for claim in claims
        )
    )


def _explicitly_non_pvp(item: Mapping[str, Any], season_revision: str) -> bool:
    flags = _pvp_flags(item)
    if flags:
        return all(flag is False for flag in flags)
    return _socket_eligibility_proves_non_pvp(
        item.get("socketEligibility"),
        season_revision,
    )


def _needs_radiant_jewelbinder_eligibility(
    item: Mapping[str, Any],
    season_revision: str,
) -> bool:
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    return (
        _is_midnight_season_one_revision(season_revision)
        and _row_slot(item) in _RADIANT_JEWELBINDER_SLOTS
        and count_payload_socket_entries(payload) == 0
        and not _pvp_flags(item)
    )


def _active_pve_catalog_socket_eligibility(
    item: Mapping[str, Any],
    sources: list[Mapping[str, Any]],
    season_revision: str,
) -> dict[str, Any] | None:
    """Return release-time non-PvP evidence for current PvE catalog items.

    Raw PvP flags retain priority when present.  When they are absent, only an
    exact current-season source from the restricted official PvE catalog may
    certify the item's eligibility for the seasonal Jewelbinder rule.
    """

    revision = _text(season_revision)
    if not _needs_radiant_jewelbinder_eligibility(item, revision):
        return None
    source_ids: set[str] = set()
    source_types: set[str] = set()
    for source in sources:
        source_id = _text(source.get("sourceId"))
        source_type = _text(source.get("sourceType")).lower()
        source_revision = _text(source.get("seasonRevision"))
        statuses = {
            _text(source.get("status")).lower(),
            _text(source.get("sourceStatus")).lower(),
        }
        if (
            not source_id
            or source_type not in _ACTIVE_PVE_CATALOG_SOURCE_TYPES
            or source_revision != revision
            or statuses.intersection({"blocked", "rejected", "expired"})
        ):
            continue
        source_ids.add(source_id)
        source_types.add(source_type)
    if not source_ids or not source_types:
        return None
    return {
        "schemaRevision": SOCKET_ELIGIBILITY_SCHEMA_REVISION,
        "status": "verified",
        "eligibility": "active_pve_catalog",
        "sourceRevision": revision,
        "sourceIds": sorted(source_ids),
        "sourceTypes": sorted(source_types),
    }


def _id_tokens(value: Any) -> list[str]:
    if isinstance(value, str):
        candidates = [token.strip() for token in value.split("/")]
    elif isinstance(value, (list, tuple)):
        candidates = [_text(token) for token in value]
    else:
        candidates = []
    identifiers: list[str] = []
    for token in candidates:
        if not token.isdigit() or int(token) <= 0:
            return []
        identifiers.append(str(int(token)))
    return identifiers


def count_payload_socket_entries(payload: Any) -> int:
    """Return the strongest explicit socket-array count in a JSON-like payload."""

    counts: list[int] = []
    seen: set[int] = set()

    def visit(value: Any) -> None:
        if isinstance(value, (dict, list, tuple)):
            identity = id(value)
            if identity in seen:
                return
            seen.add(identity)
        if isinstance(value, dict):
            for key, child in value.items():
                if _normalized_key(key) in _SOCKET_PAYLOAD_KEYS:
                    if isinstance(child, (list, tuple)):
                        counts.append(len(child))
                    elif isinstance(child, dict) and child:
                        counts.append(1)
                visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)

    visit(payload)
    return max(counts, default=0)


def parse_simc_socket_bonus_minimums(output: Any) -> dict[str, int]:
    """Parse socket-producing bonus lines into bonus-id total lower bounds.

    Lines without both a concrete bonus ID and an explicit socket effect are
    ignored. A socket effect without an explicit count proves a total of one.
    """

    if not isinstance(output, str):
        return {}
    parsed: dict[str, int] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.search(
            r"\b(?:no|not|without|remove(?:d|s|ing)?|disable(?:d|s|ing)?)"
            r"[\s_-]+(?:an?[\s_-]+)?sockets?\b"
            r"|\bsockets?[\s_-]+(?:removed|disabled|none)\b",
            line,
            flags=re.IGNORECASE,
        ):
            continue
        positive_socket_effect = re.search(
            r"\beffect\s*[:=]\s*(?:(?:add|adds|added)[\s_-]+)?sockets?\b",
            line,
            flags=re.IGNORECASE,
        ) or re.search(
            r"(?:^|[:|,;\t-])\s*(?:(?:add|adds|added)[\s_-]+)?sockets?"
            r"(?=\s*(?:[:=(+]|$))",
            line,
            flags=re.IGNORECASE,
        )
        if not positive_socket_effect:
            continue
        bonus_match = re.search(
            r"\bbonus[\s_-]*id\s*(?:[:=]|\s)\s*\{\s*(\d+)\s*\}"
            r"(?=\s*(?:[:,;|\-]|$)|\s+[A-Za-z_][\w-]*\s*[:=])",
            line,
            flags=re.IGNORECASE,
        )
        if not bonus_match:
            bonus_match = re.search(
                r"\bbonus[\s_-]*id\s*(?:[:=]|\s)\s*(\d+)\b"
                r"(?=\s*(?:[:,;|\-]|$)|\s+[A-Za-z_][\w-]*\s*[:=])",
                line,
                flags=re.IGNORECASE,
            )
        if not bonus_match:
            bonus_match = re.match(r"^(\d+)\s*(?:[:|,\t-])", line)
        if not bonus_match:
            continue
        minimum_candidates: list[int] = []
        invalid_socket_assignment = False
        for assignment_marker in re.finditer(
            r"\bsockets?\s*=",
            line,
            flags=re.IGNORECASE,
        ):
            assignment_tail = line[assignment_marker.end() :]
            if re.match(r"\s*\{", assignment_tail):
                assigned_token = re.match(
                    r"\s*\{\s*([+-]?\d+)\s*\}"
                    r"(?=\s*(?:[:,;|\-]|$)|\s+[A-Za-z_][\w-]*\s*[:=])",
                    assignment_tail,
                )
            else:
                assigned_token = re.match(
                    r"\s*([^\s,;|()\[\]{}]+)"
                    r"(?=\s*(?:[:,;|\-]|$)|\s+[A-Za-z_][\w-]*\s*[:=])",
                    assignment_tail,
                )
            if not assigned_token or not re.fullmatch(r"[+-]?\d+", assigned_token.group(1)):
                invalid_socket_assignment = True
                break
            assigned_minimum = _minimum_total(assigned_token.group(1))
            if not assigned_minimum:
                invalid_socket_assignment = True
                break
            minimum_candidates.append(assigned_minimum)
        if invalid_socket_assignment:
            continue
        minimum_candidates.extend(
            _minimum_total(match)
            for match in re.findall(
                r"\b(?:minimum[\s_-]*total|socket[\s_-]*count)"
                r"\s*(?:[:=]|\s)\s*(\d+)\b",
                line,
                flags=re.IGNORECASE,
            )
        )
        minimum_candidates.extend(
            _minimum_total(match)
            for match in re.findall(
                r"\b(\d+)\s+sockets?\b",
                line,
                flags=re.IGNORECASE,
            )
        )
        minimum = max(minimum_candidates, default=1)
        if not minimum:
            continue
        bonus_id = bonus_match.group(1)
        parsed[bonus_id] = max(parsed.get(bonus_id, 0), minimum)
    return {bonus_id: parsed[bonus_id] for bonus_id in sorted(parsed, key=int)}


def derive_item_socket_fact(
    item: Any,
    season_revision: str = "",
) -> dict[str, Any]:
    """Derive an exact-item socket fact from explicit item and season evidence."""

    row = item if isinstance(item, dict) else {}
    claims: list[dict[str, Any]] = []
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    official_total = count_payload_socket_entries(payload)
    official_claim = _claim(
        minimum_total=official_total,
        scope="exact_item",
        source="official_item_payload",
        source_revision=_source_revision(row, "official-item-payload"),
    )
    if official_claim:
        claims.append(official_claim)

    revision = _text(season_revision)
    is_midnight_season_one = _is_midnight_season_one_revision(revision)
    slot = _row_slot(row)
    if is_midnight_season_one and slot in _MIDNIGHT_JEWELRY_SLOTS:
        claims.append(
            _claim(
                minimum_total=1,
                scope="season_slot",
                source="midnight_s1_jewelry_floor",
                source_revision=revision,
            )
        )
    elif (
        is_midnight_season_one
        and slot in _RADIANT_JEWELBINDER_SLOTS
        and official_total == 0
        and _explicitly_non_pvp(row, revision)
    ):
        claims.append(
            _claim(
                minimum_total=1,
                scope="season_slot",
                source="midnight_s1_radiant_jewelbinder",
                source_revision=revision,
            )
        )
    return _socket_fact([claim for claim in claims if claim])


def _bonus_minimum(
    socket_bonus_minimums: Mapping[str, Any],
    bonus_id: str,
) -> tuple[int, str]:
    raw = socket_bonus_minimums.get(bonus_id)
    if isinstance(raw, dict):
        return (
            _minimum_total(raw.get("minimumTotal")),
            _text(raw.get("sourceRevision") or f"simc-bonus:{bonus_id}"),
        )
    return _minimum_total(raw), f"simc-bonus:{bonus_id}"


def derive_variant_socket_fact(
    item: Any,
    variant: Any,
    season_revision: str = "",
    socket_bonus_minimums: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive a final exact-variant lower bound without widening its scope."""

    item_row = item if isinstance(item, dict) else {}
    variant_row = variant if isinstance(variant, dict) else {}
    claims = list(derive_item_socket_fact(item_row, season_revision).get("claims") or [])

    payload = variant_row.get("payload") if isinstance(variant_row.get("payload"), dict) else {}
    variant_payload_total = count_payload_socket_entries(payload)
    payload_claim = _claim(
        minimum_total=variant_payload_total,
        scope="exact_variant",
        source="official_item_payload",
        source_revision=_source_revision(variant_row, "official-variant-payload"),
    )
    if payload_claim:
        claims.append(payload_claim)

    simc_options = (
        variant_row.get("simcOptions")
        if isinstance(variant_row.get("simcOptions"), dict)
        else {}
    )
    known_bonuses = socket_bonus_minimums if isinstance(socket_bonus_minimums, Mapping) else {}
    for bonus_id in _id_tokens(simc_options.get("bonus_id")):
        minimum, source_revision = _bonus_minimum(known_bonuses, bonus_id)
        bonus_claim = _claim(
            minimum_total=minimum,
            scope="exact_variant",
            source="simc_bonus",
            source_revision=source_revision,
        )
        if bonus_claim:
            claims.append(bonus_claim)

    occupied_gem_total = len(_id_tokens(simc_options.get("gem_id")))
    gem_claim = _claim(
        minimum_total=occupied_gem_total,
        scope="exact_variant",
        source="observed_gem_occupancy",
        source_revision=_source_revision(variant_row, "observed-gear-variant"),
    )
    if gem_claim:
        claims.append(gem_claim)
    return _socket_fact(claims)


def materialize_gear_socket_facts(
    snapshot: Any,
    season_revision: str = "",
    socket_bonus_minimums: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a copied Gear snapshot with item and exact-variant socket facts."""

    materialized = copy.deepcopy(snapshot) if isinstance(snapshot, dict) else {}
    items = [row for row in materialized.get("items") or [] if isinstance(row, dict)]
    sources = [row for row in materialized.get("sources") or [] if isinstance(row, dict)]
    variants = [row for row in materialized.get("variants") or [] if isinstance(row, dict)]
    items_by_id: dict[str, dict[str, Any]] = {}
    sources_by_item_id: dict[str, list[Mapping[str, Any]]] = {}

    for source in sources:
        item_id = _text(source.get("itemId"))
        if item_id:
            sources_by_item_id.setdefault(item_id, []).append(source)

    for item in items:
        item_id = _text(item.get("itemId"))
        item.pop("socketEligibility", None)
        eligibility = _active_pve_catalog_socket_eligibility(
            item,
            sources_by_item_id.get(item_id, []),
            _text(season_revision),
        )
        if eligibility:
            item["socketEligibility"] = eligibility
        fact = derive_item_socket_fact(item, season_revision)
        capabilities = item.get("baseCapabilities")
        if not isinstance(capabilities, dict):
            capabilities = {}
            item["baseCapabilities"] = capabilities
        capabilities["socketCount"] = fact["minimumTotal"]
        item["socketEvidence"] = fact
        if item_id:
            items_by_id[item_id] = item

    for variant in variants:
        item = items_by_id.get(_text(variant.get("itemId")), {})
        fact = derive_variant_socket_fact(
            item,
            variant,
            season_revision,
            socket_bonus_minimums,
        )
        capabilities = variant.get("capabilityOverrides")
        if not isinstance(capabilities, dict):
            capabilities = {}
            variant["capabilityOverrides"] = capabilities
        capabilities["socketCount"] = fact["minimumTotal"]
        variant["socketEvidence"] = fact
    return materialized

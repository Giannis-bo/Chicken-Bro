"""Adapt the verified S2 equipment-library evidence into the Candidate v1 inputs."""

from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

try:
    from .season_set_membership import build_set_membership
except ImportError:
    from season_set_membership import build_set_membership


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


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
    return sorted({_text(item) for item in values if _text(item)})


def _row_payload(row: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = row.get("payload")
    return payload if isinstance(payload, Mapping) else {}


def _canonical_input(row: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = _row_payload(row)
    value = payload.get("canonicalSimcInput")
    return value if isinstance(value, Mapping) else {}


def _candidate_canonical_input(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("canonicalSimcInput")
    return value if isinstance(value, Mapping) else _canonical_input(row)


def _static_stats(row: Mapping[str, Any]) -> dict[str, int | float]:
    payload = _row_payload(row)
    value = payload.get("resolvedStats") or payload.get("staticStats")
    if not isinstance(value, Mapping):
        return {}
    return {
        _text(key): amount
        for key, amount in value.items()
        if _text(key)
        and isinstance(amount, (int, float))
        and not isinstance(amount, bool)
        and amount >= 0
    }


def _row_track_key(row: Mapping[str, Any]) -> str:
    payload = _row_payload(row)
    return _text(payload.get("trackKey") or row.get("trackKey"))


def _row_rank(row: Mapping[str, Any], field: str) -> int | None:
    payload = _row_payload(row)
    return _int(payload.get(field) if payload.get(field) is not None else row.get(field))


def _catalog_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    item_id = _text(row.get("itemId"))
    variant_key = _text(row.get("variantKey"))
    canonical = _canonical_input(row)
    item_level = _int(row.get("itemLevel")) or _int(canonical.get("itemLevel"))
    static_stats = _static_stats(row)
    if not item_id or not variant_key or not item_level or not static_stats:
        return None
    if _text(row.get("sourceType")).lower() == "crafted":
        selection_only = {
            "crit",
            "crit_rating",
            "critical_strike",
            "critical_strike_rating",
            "haste",
            "haste_rating",
            "mastery",
            "mastery_rating",
            "versatility",
            "versatility_rating",
        }
        if not any(key.lower() not in selection_only for key in static_stats):
            # There is no selection-independent fact from which a Browse
            # variant can be built.  Keep the verified row in Gear/Exact,
            # but do not publish a synthetic Catalog identity.
            return None
    bonus_ids = _tokens(canonical.get("bonusIds"))
    payload = _row_payload(row)
    track_key = _row_track_key(row)
    result = copy.deepcopy(dict(row))
    result.update({
        "rowFamily": "browse",
        "itemLevel": item_level,
        "bonusIds": bonus_ids,
        "staticStats": static_stats,
        "status": "verified",
        "blockers": [],
        "sourceVariantKey": variant_key,
        "trackKey": track_key,
        "sourceType": _text(row.get("sourceType")),
    })
    result["trackRank"] = _row_rank(row, "rank")
    result["trackRankMax"] = _row_rank(row, "maxRank")
    result["hasCraftedStats"] = bool(
        isinstance(row.get("simcOptions"), Mapping)
        and _text(row["simcOptions"].get("crafted_stats"))
    )
    result["payload"] = _canonical(payload)
    return result


def project_s2_catalog_rows(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Keep canonical Browse rows while leaving every exact row in Gear Release."""

    variants = [
        row
        for row in snapshot.get("variants") or []
        if isinstance(row, Mapping)
        and _text(row.get("status")).lower() == "verified"
    ]
    selected: dict[tuple[str, str], Mapping[str, Any]] = {}
    normal_groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    crafted_rows: list[Mapping[str, Any]] = []
    tier_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in variants:
        # Community-observed rows are immutable Exact evidence only.  Keep
        # this guard explicit so a future source/track field cannot promote
        # an imported instance into the finite official Catalog by accident.
        if _text(row.get("rowFamily")) == "exact_instance":
            continue
        source_type = _text(row.get("sourceType")).lower()
        track_key = _row_track_key(row)
        if source_type == "crafted":
            crafted_rows.append(row)
        elif track_key and _row_rank(row, "rank") == _row_rank(row, "maxRank"):
            normal_groups[(_text(row.get("itemId")), track_key)].append(row)
        elif source_type == "tier_set" and not track_key:
            tier_groups[_text(row.get("itemId"))].append(row)

    for identity, rows in normal_groups.items():
        selected[identity] = min(rows, key=lambda row: _text(row.get("variantKey")))
    for row in crafted_rows:
        selected[(
            _text(row.get("itemId")),
            f"crafted:{_text(row.get('variantKey'))}",
        )] = row
    for item_id, rows in tier_groups.items():
        if item_id:
            selected[(item_id, "tier_set_static")] = min(
                rows,
                key=lambda row: _text(row.get("variantKey")),
            )

    output = []
    for row in sorted(
        selected.values(),
        key=lambda value: (_text(value.get("itemId")), _text(value.get("variantKey"))),
    ):
        projected = _catalog_row(row)
        if projected is not None:
            output.append(projected)
    return output


def _source_refs(candidate: Mapping[str, Any], extra: Sequence[str] = ()) -> list[str]:
    refs = {_text(value) for value in extra if _text(value)}
    refs.update(_text(value) for value in candidate.get("evidenceRefs") or [] if _text(value))
    report_id = _text(candidate.get("reportId"))
    if report_id:
        refs.add(report_id)
    return sorted(refs)


def build_s2_track_authority(
    candidate: Mapping[str, Any],
    *,
    season_revision: str,
    gear_rule_revision: str,
    track_authority_revision: str,
    snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build explicit max-rank, crafted-quality and tier-static Track records."""

    candidate_value = candidate if isinstance(candidate, Mapping) else {}
    problems: list[dict[str, str]] = []
    rows = [
        row
        for row in candidate_value.get("variants") or []
        if isinstance(row, Mapping)
        and _text(row.get("simcReadiness")) == "ready"
    ]
    normal_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        track_key = _text(row.get("trackKey"))
        if track_key and _int(row.get("rank")) == _int(row.get("maxRank")):
            normal_groups[track_key].append(row)

    track_facts = {
        _text(row.get("trackKey")): row
        for row in candidate_value.get("mythicPlusCapTrackEvidence", {}).get("trackFacts", [])
        if isinstance(row, Mapping) and _text(row.get("trackKey"))
    }
    records: list[dict[str, Any]] = []
    for track_key in sorted(normal_groups):
        group = normal_groups[track_key]
        levels = {
            _int((_candidate_canonical_input(row)).get("itemLevel"))
            for row in group
            if _int((_candidate_canonical_input(row)).get("itemLevel"))
        }
        max_ranks = {_int(row.get("maxRank")) for row in group if _int(row.get("maxRank"))}
        if len(levels) != 1 or len(max_ranks) != 1:
            problems.append({
                "code": "S2_TRACK_MAX_LEVEL_CONFLICT",
                "message": f"Track {track_key} does not have one verified max-rank level.",
            })
            continue
        exemplar = min(group, key=lambda row: _text(row.get("variantKey")))
        fact = track_facts.get(track_key, {})
        source_types = sorted({
            _text(row.get("sourceEligibilityEvidence", {}).get("bySource", {}).get(source, {}).get("status"))
            and source
            for row in group
            for source in (
                row.get("sourceEligibilityEvidence", {}).get("bySource", {})
                if isinstance(row.get("sourceEligibilityEvidence"), Mapping)
                and isinstance(row.get("sourceEligibilityEvidence", {}).get("bySource"), Mapping)
                else {}
            )
            if _text(row.get("sourceEligibilityEvidence", {}).get("bySource", {}).get(source, {}).get("status")) == "verified"
        })
        if not source_types:
            source_types = ["raid", "mythic_plus"]
        bonus_ids = _tokens(_candidate_canonical_input(exemplar).get("bonusIds"))
        if not bonus_ids:
            problems.append({
                "code": "S2_TRACK_BONUS_EVIDENCE_MISSING",
                "message": f"Track {track_key} has no verified bonus evidence.",
            })
            continue
        records.append({
            "recordKey": f"s2_{track_key}_max_rank",
            "publicTrackKey": track_key,
            "progressionKind": "upgrade_track",
            "itemLevel": next(iter(levels)),
            "maxRank": next(iter(max_ranks)),
            "rank": next(iter(max_ranks)),
            "eligibleSourceTypes": source_types,
            "eligibleSlots": sorted({_text(row.get("itemSlot")) for row in group if _text(row.get("itemSlot"))}),
            "sourceRefIds": _source_refs(candidate_value, [*_source_refs(fact), _text(exemplar.get("variantKey"))]),
            "evidenceStatus": "verified",
            "bonusIds": bonus_ids,
            "seasonRevision": season_revision,
            "gearRuleRevision": gear_rule_revision,
            "trackAuthorityRevision": track_authority_revision,
        })

    crafted_groups: dict[tuple[str, int], list[Mapping[str, Any]]] = defaultdict(list)
    for row in candidate_value.get("craftedVariantTemplates") or []:
        if not isinstance(row, Mapping) or _text(row.get("simcReadiness")) != "ready":
            continue
        canonical = row.get("canonicalSimcInput")
        canonical = canonical if isinstance(canonical, Mapping) else {}
        track_key = _text(row.get("craftedTrackKey")) or "crafted_quality"
        item_level = _int(canonical.get("itemLevel"))
        if item_level:
            crafted_groups[(track_key, item_level)].append(row)
    for (track_key, item_level), group in sorted(crafted_groups.items()):
        quality = group[0].get("quality")
        quality = quality if isinstance(quality, Mapping) else {}
        records.append({
            "recordKey": f"s2_crafted_{track_key}_{item_level}",
            "publicTrackKey": track_key,
            "progressionKind": "crafted_quality",
            "itemLevel": item_level,
            "eligibleSourceTypes": ["crafted"],
            "eligibleSlots": sorted({_text(row.get("itemSlot")) for row in group if _text(row.get("itemSlot"))}),
            "originKind": "crafted_quality",
            "qualityKey": _text(quality.get("qualityId")),
            "sourceRefIds": _source_refs(candidate_value, [
                ref
                for row in group
                for ref in row.get("evidenceRefs") or []
            ]),
            "evidenceStatus": "verified",
            "seasonRevision": season_revision,
            "gearRuleRevision": gear_rule_revision,
            "trackAuthorityRevision": track_authority_revision,
        })

    if snapshot:
        tier_rows = [
            row
            for row in snapshot.get("variants") or []
            if isinstance(row, Mapping)
            and _text(row.get("sourceType")).lower() == "tier_set"
            and not _row_track_key(row)
        ]
        levels = {
            _int(row.get("itemLevel"))
            for row in tier_rows
            if _int(row.get("itemLevel"))
        }
        if len(levels) == 1:
            records.append({
                "recordKey": "s2_tier_set_static",
                "publicTrackKey": "tier_set_static",
                "progressionKind": "season_special",
                "itemLevel": next(iter(levels)),
                "eligibleSourceTypes": ["tier_set"],
                "eligibleSlots": sorted({_text(row.get("slot")) for row in tier_rows if _text(row.get("slot"))}),
                "sourceRefIds": _source_refs(candidate_value),
                "evidenceStatus": "verified",
                "seasonRevision": season_revision,
                "gearRuleRevision": gear_rule_revision,
                "trackAuthorityRevision": track_authority_revision,
            })

    records.sort(key=lambda row: (_text(row.get("publicTrackKey")), _int(row.get("itemLevel")) or 0, _text(row.get("recordKey"))))
    return {
        "schemaRevision": "gear-track-authority-v1",
        "status": "verified" if records and not problems else "blocked",
        "seasonRevision": season_revision,
        "gearRuleRevision": gear_rule_revision,
        "ruleRevision": track_authority_revision,
        "trackAuthorityRevision": track_authority_revision,
        "sourceRefs": _source_refs(candidate_value),
        "records": records,
        "problems": sorted(problems, key=lambda row: (_text(row.get("code")), _text(row.get("message")))),
    }


def build_s2_set_membership(candidate: Mapping[str, Any], *, season_revision: str) -> dict[str, Any]:
    rows = []
    for raw in candidate.get("tierSetFacts") or []:
        if not isinstance(raw, Mapping):
            continue
        evidence_refs = [
            *_tokens(raw.get("officialEvidenceRefs")),
            *_tokens(raw.get("evidenceRefs")),
        ]
        effects = []
        for effect in raw.get("effects") or []:
            if not isinstance(effect, Mapping):
                continue
            effects.append({
                "effectId": f"{_text(raw.get('setId'))}:{_int(effect.get('requiredCount')) or 0}",
                "pieces": _int(effect.get("requiredCount")) or 0,
                "displayString": _text(effect.get("displayString")),
                "sourceRefs": evidence_refs,
            })
        rows.append({
            "setId": _text(raw.get("setId")),
            "setName": _text(raw.get("name")),
            "itemIds": _tokens(raw.get("itemIds")),
            "sourceRefs": evidence_refs,
            "setBonusEvidence": effects,
            "seasonRevision": season_revision,
            "evidenceStatus": "verified" if _text(raw.get("status")) == "verified" else "blocked",
        })
    return build_set_membership({
        "seasonId": "midnight-season-2",
        "scope": "end_game",
        "seasonRevision": season_revision,
        "status": "verified",
    }, rows)


def build_s2_option_catalog(candidate: Mapping[str, Any], *, season_revision: str) -> dict[str, Any]:
    options = []
    for raw in candidate.get("enhancementCatalog", {}).get("options", []):
        if not isinstance(raw, Mapping):
            continue
        source_type = _text(raw.get("optionType")).lower()
        option_type = {
            "gem": "socket",
            "crafted_stats": "crafted",
        }.get(source_type, source_type)
        if not _text(raw.get("optionId")) or not _text(raw.get("optionKey")) or not option_type:
            continue
        options.append({
            "optionId": _text(raw.get("optionId")),
            "optionKey": _text(raw.get("optionKey")),
            "optionType": option_type,
            "token": _text(raw.get("simcOptions", {}).get(next(iter(raw.get("simcOptions", {})), ""))) if isinstance(raw.get("simcOptions"), Mapping) else "",
            "seasonRevision": season_revision,
            "name": _text(raw.get("name")) or _text(raw.get("optionKey")),
            "statSummary": _text(raw.get("statSummary")),
            "sourceStatus": "verified",
            "status": "verified",
            "managementMode": "editor_managed",
            "editorManaged": True,
            "isVisible": True,
            "simcOptions": _canonical(raw.get("simcOptions") if isinstance(raw.get("simcOptions"), Mapping) else {}),
            "sourceRefs": _tokens(raw.get("sourceRefs")),
            "payload": _canonical(raw.get("payload") if isinstance(raw.get("payload"), Mapping) else {}),
        })
    options.sort(key=lambda row: _text(row.get("optionKey")))
    identity = {
        "schemaRevision": "gear-enhancement-option-catalog-v1",
        "seasonRevision": season_revision,
        "options": options,
        "blockedOptions": [],
    }
    revision = "s2-options:sha256:" + hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        **identity,
        "status": "verified",
        "optionRevision": revision,
        "blockerCodes": [],
        "problems": [],
        "coverage": {
            "observedVariantCount": _int(candidate.get("coverageCounts", {}).get("simcReadyCount")) or 0,
            "optionCount": len(options),
            "blockedOptionCount": 0,
        },
        "management": {
            "socket": "editor_managed",
            "enchant": "editor_managed",
            "embellishment": "editor_managed_or_source_only",
        },
    }


__all__ = (
    "build_s2_option_catalog",
    "build_s2_set_membership",
    "build_s2_track_authority",
    "project_s2_catalog_rows",
)

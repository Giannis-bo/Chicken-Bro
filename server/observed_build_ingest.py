#!/usr/bin/env python3
"""Fail-closed Raider.IO adapter for immutable observed-build snapshots."""

from __future__ import annotations

import itertools
import json
import re
from collections import defaultdict
from typing import Any, Callable, Mapping

try:
    from .observed_build_registry import build_observed_snapshot, slot_key
    from .websim_payload import expected_hero_tree_triplets
except ImportError:
    from observed_build_registry import build_observed_snapshot, slot_key
    from websim_payload import expected_hero_tree_triplets


_SOURCE_IDENTITY = re.compile(r"raiderio:([a-z]{2})\|([^|\s]+)\|([^|\s]+)")


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


def _canonical_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _expected_slots_by_key() -> dict[str, dict[str, str]]:
    expected: dict[str, dict[str, str]] = {}
    for triplet in expected_hero_tree_triplets():
        class_key, spec_key, hero_key = triplet.split(":")
        slot = {
            "classKey": class_key,
            "specKey": spec_key,
            "heroKey": hero_key,
            "scenarioKey": "mythic_plus",
        }
        expected[slot_key(slot)] = slot
    return expected


def _source_identity_parts(value: Any) -> tuple[str, str, str] | None:
    identity = _text(value)
    matched = _SOURCE_IDENTITY.fullmatch(identity)
    if not matched or identity != identity.lower():
        return None
    return matched.group(1), matched.group(2), matched.group(3)


def _profile_identity(profile: Mapping[str, Any]) -> str:
    explicit = _text(profile.get("sourceIdentity"))
    if _source_identity_parts(explicit):
        return explicit
    region = _text(profile.get("region")).lower()
    realm = _text(profile.get("realmSlug") or profile.get("realm")).lower()
    player = _text(
        profile.get("name")
        or profile.get("characterName")
        or profile.get("playerId")
    ).lower()
    identity = f"raiderio:{region}|{realm}|{player}"
    return identity if _source_identity_parts(identity) else ""


def _normalized_gear(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_gear = profile.get("gear")
    if not isinstance(raw_gear, list):
        return []
    gear: list[dict[str, Any]] = []
    for raw_item in raw_gear:
        if not isinstance(raw_item, dict):
            continue
        slot = _text(raw_item.get("slot"))
        item_id = _int(raw_item.get("itemId") or raw_item.get("item_id"))
        if not slot or item_id <= 0:
            continue
        item = _canonical(raw_item)
        item["slot"] = slot
        item["itemId"] = item_id
        gear.append(item)
    return sorted(
        gear,
        key=lambda item: (
            _text(item.get("slot")),
            _int(item.get("itemId")),
            _canonical_text(item),
        ),
    )


def _profile_sort_key(profile: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        -len(_normalized_gear(profile)),
        -_float(profile.get("itemLevel")),
        _canonical_text(profile),
    )


def _profiles_by_identity(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw_profile in payload.get("profiles") or []:
        if not isinstance(raw_profile, dict):
            continue
        identity = _profile_identity(raw_profile)
        if identity:
            grouped[identity].append(raw_profile)
    return {
        identity: _canonical(sorted(profiles, key=_profile_sort_key)[0])
        for identity, profiles in grouped.items()
    }


def _template_slot(
    template: Mapping[str, Any],
    expected: Mapping[str, dict[str, str]],
) -> dict[str, str] | None:
    slot = {
        "classKey": _text(template.get("classKey")),
        "specKey": _text(template.get("specKey")),
        "heroKey": _text(template.get("heroKey")),
        "scenarioKey": _text(template.get("scenarioKey")),
    }
    key = ":".join(slot.values())
    return expected.get(key)


def _problem(code: str, *, stage: str, source_identity: str = "") -> dict[str, Any]:
    problem = {"code": code, "stage": stage}
    if source_identity:
        problem["sourceIdentity"] = source_identity
    return problem


def _profile_candidate_template(
    profile: Mapping[str, Any],
    hero_resolver: Callable[
        [str, str, list[dict[str, Any]], str],
        str,
    ]
    | None = None,
) -> dict[str, Any] | None:
    """Project one self-contained Raider.IO profile into the template adapter."""

    talent = profile.get("talentLoadout")
    talent = talent if isinstance(talent, dict) else {}
    class_key = _text(profile.get("classKey"))
    spec_key = _text(profile.get("specKey"))
    hero_key = _resolved_hero_key(
        class_key,
        spec_key,
        talent.get("loadout"),
        talent.get("heroKey"),
        hero_resolver,
    )
    identity = _profile_identity(profile)
    profile_url = _text(profile.get("profileUrl"))
    if (
        not hero_key
        or not identity
        or not profile_url.startswith("https://raider.io/")
    ):
        return None
    ranking = profile.get("rankingEvidence")
    ranking = ranking if isinstance(ranking, dict) else {}
    return {
        "id": f"observed-profile:{identity}:{hero_key}",
        "classKey": class_key,
        "specKey": spec_key,
        "heroKey": hero_key,
        "scenarioKey": "mythic_plus",
        "sourceKey": "raiderio",
        "sourceUrl": profile_url,
        "rawImportCode": _text(talent.get("rawImportCode")),
        "playerId": _text(
            profile.get("name")
            or profile.get("characterName")
        ),
        "maxKeyLevel": _int(ranking.get("maxKeyLevel")),
        "status": "verified",
        "payload": {
            "raiderio": {
                "sourceIdentity": identity,
                "profileUrl": profile_url,
                "characterName": _text(
                    profile.get("name")
                    or profile.get("characterName")
                ),
                "realm": _text(
                    profile.get("realm")
                    or profile.get("realmSlug")
                ),
                "realmSlug": _text(
                    profile.get("realmSlug")
                    or profile.get("realm")
                ),
                "region": _text(profile.get("region")).lower(),
                "heroKey": hero_key,
                "heroSubTreeId": talent.get("heroSubTreeId") or "",
                "loadoutSpecId": talent.get("loadoutSpecId") or "",
                "selector": _canonical(
                    talent.get("selector")
                    if isinstance(talent.get("selector"), dict)
                    else {}
                ),
                "source": _text(
                    talent.get("source")
                    or "profile_current"
                ),
                "loadout": _canonical(
                    talent.get("loadout")
                    if isinstance(talent.get("loadout"), list)
                    else []
                ),
            },
            "rioEvidence": _canonical(ranking),
        },
    }


def _resolved_hero_key(
    class_key: Any,
    spec_key: Any,
    loadout: Any,
    declared_hero: Any,
    hero_resolver: Callable[
        [str, str, list[dict[str, Any]], str],
        str,
    ]
    | None,
) -> str:
    declared = _text(declared_hero)
    structured = [
        _canonical(entry)
        for entry in (loadout if isinstance(loadout, list) else [])
        if isinstance(entry, dict)
    ]
    if not callable(hero_resolver) or not structured:
        return declared
    try:
        resolved = _text(
            hero_resolver(
                _text(class_key),
                _text(spec_key),
                structured,
                declared,
            )
        )
    except Exception:
        return declared
    return resolved or declared


def _template_with_resolved_hero(
    template: Mapping[str, Any],
    hero_resolver: Callable[
        [str, str, list[dict[str, Any]], str],
        str,
    ]
    | None,
) -> dict[str, Any]:
    normalized = _canonical(template)
    payload = normalized.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    rio = payload.get("raiderio")
    rio = rio if isinstance(rio, dict) else {}
    declared = _text(rio.get("heroKey") or normalized.get("heroKey"))
    hero_key = _resolved_hero_key(
        normalized.get("classKey"),
        normalized.get("specKey"),
        rio.get("loadout"),
        declared,
        hero_resolver,
    )
    if not hero_key or hero_key == declared:
        return normalized
    rio = {**rio, "heroKey": hero_key}
    normalized["heroKey"] = hero_key
    normalized["payload"] = {**payload, "raiderio": rio}
    return normalized


def _template_snapshot(
    template: Mapping[str, Any],
    *,
    slot: dict[str, str],
    profile: Mapping[str, Any],
    season_slug: str,
) -> dict[str, Any]:
    payload = template.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    rio = payload.get("raiderio")
    rio = rio if isinstance(rio, dict) else {}
    evidence = payload.get("rioEvidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    identity = _text(rio.get("sourceIdentity"))
    identity_parts = _source_identity_parts(identity)
    if not identity_parts:
        raise ValueError("source_identity_invalid")
    region, identity_realm, identity_player = identity_parts
    profile_url = _text(
        rio.get("profileUrl")
        or template.get("sourceUrl")
        or profile.get("profileUrl")
    )
    player = _text(
        rio.get("characterName")
        or template.get("playerId")
        or profile.get("name")
    )
    realm = _text(rio.get("realmSlug") or rio.get("realm") or identity_realm)
    observed_region = _text(rio.get("region") or region).lower()
    if (
        not profile_url.startswith("https://raider.io/")
        or player.lower() != identity_player
        or realm.lower() != identity_realm
        or observed_region != region
    ):
        raise ValueError("source_identity_metadata_mismatch")
    profile_class = _text(profile.get("classKey"))
    profile_spec = _text(profile.get("specKey"))
    if (
        profile_class
        and profile_class != slot["classKey"]
    ) or (
        profile_spec
        and profile_spec != slot["specKey"]
    ):
        raise ValueError("exact_profile_spec_mismatch")
    if _text(rio.get("heroKey")) != slot["heroKey"]:
        raise ValueError("talent_hero_mismatch")
    raw_import_code = _text(template.get("rawImportCode"))
    structured_loadout = (
        rio.get("loadout")
        if isinstance(rio.get("loadout"), list)
        else []
    )
    if not raw_import_code and not structured_loadout:
        raise ValueError("talent_observation_missing")
    gear = _normalized_gear(profile)
    if not gear:
        raise ValueError("exact_profile_gear_missing")
    ranking_evidence = {
        "source": _text(evidence.get("source") or "raiderio_spec_ranking"),
        "score": _float(evidence.get("score")),
        "rank": _int(evidence.get("rank")),
        "maxKeyLevel": _int(
            evidence.get("maxKeyLevel") or template.get("maxKeyLevel")
        ),
        "sourceUrl": _text(evidence.get("sourceUrl") or profile_url),
    }
    talent_observation = {
        "rawImportCode": raw_import_code,
        "loadoutSpecId": rio.get("loadoutSpecId") or "",
        "heroSubTreeId": rio.get("heroSubTreeId") or "",
        "heroKey": slot["heroKey"],
        "selector": _canonical(
            rio.get("selector") if isinstance(rio.get("selector"), dict) else {}
        ),
        "source": _text(rio.get("source") or "profile_current"),
        "loadout": _canonical(structured_loadout),
    }
    gear_observation = {
        "gearItems": gear,
        "itemLevel": _float(profile.get("itemLevel")),
        "raceKey": _text(profile.get("raceKey")),
        "gearSnapshotEvidence": _canonical(
            profile.get("gearSnapshotEvidence")
            if isinstance(profile.get("gearSnapshotEvidence"), dict)
            else {}
        ),
    }
    return build_observed_snapshot(
        slot=slot,
        source={
            "sourceKey": "raiderio",
            "sourceIdentity": identity,
            "profileUrl": profile_url,
            "region": region,
            "realm": identity_realm,
            "character": player,
        },
        ranking_evidence=ranking_evidence,
        talent_observation=talent_observation,
        gear_observation=gear_observation,
        source_revision=f"raiderio:{season_slug}:observed-profile-v1",
    )


def _candidate_sort_key(snapshot: Mapping[str, Any]) -> tuple[Any, ...]:
    evidence = snapshot.get("rankingEvidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    rank = _int(evidence.get("rank"))
    return (
        -_float(evidence.get("score")),
        rank if rank > 0 else 2**31 - 1,
        -_int(evidence.get("maxKeyLevel")),
        _text((snapshot.get("source") or {}).get("sourceIdentity")),
        _text(snapshot.get("snapshotId")),
    )


def _spec_id(snapshot: Mapping[str, Any]) -> str:
    slot = snapshot.get("slot")
    slot = slot if isinstance(slot, dict) else {}
    return f"{_text(slot.get('classKey'))}:{_text(slot.get('specKey'))}"


def _pair_sort_key(pair: tuple[dict[str, Any], dict[str, Any]]) -> tuple[Any, ...]:
    evidences = [
        item.get("rankingEvidence")
        if isinstance(item.get("rankingEvidence"), dict)
        else {}
        for item in pair
    ]
    positive_ranks = [
        _int(evidence.get("rank"))
        if _int(evidence.get("rank")) > 0
        else 2**31 - 1
        for evidence in evidences
    ]
    return (
        -sum(_float(evidence.get("score")) for evidence in evidences),
        sum(positive_ranks),
        -sum(_int(evidence.get("maxKeyLevel")) for evidence in evidences),
        *(_candidate_sort_key(item) for item in pair),
    )


def select_distinct_snapshot_winners(
    candidates_by_slot: Mapping[str, list[dict[str, Any]]],
    *,
    eligible_snapshot_ids: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Choose the highest deterministic distinct-identity pair per spec."""

    eligible = (
        {_text(snapshot_id) for snapshot_id in eligible_snapshot_ids}
        if eligible_snapshot_ids is not None
        else None
    )
    normalized: dict[str, list[dict[str, Any]]] = {}
    for raw_slot_key, raw_candidates in candidates_by_slot.items():
        candidates = [
            _canonical(candidate)
            for candidate in raw_candidates or []
            if isinstance(candidate, dict)
            and (
                eligible is None
                or _text(candidate.get("snapshotId")) in eligible
            )
        ]
        if candidates:
            normalized[_text(raw_slot_key)] = sorted(
                candidates,
                key=_candidate_sort_key,
            )
    slots_by_spec: dict[str, list[str]] = defaultdict(list)
    for key, candidates in normalized.items():
        spec_id = _spec_id(candidates[0])
        if spec_id != ":":
            slots_by_spec[spec_id].append(key)
    winners: dict[str, dict[str, Any]] = {}
    for spec_id in sorted(slots_by_spec):
        slot_keys = sorted(set(slots_by_spec[spec_id]))
        if len(slot_keys) != 2:
            continue
        pairs = [
            pair
            for pair in itertools.product(
                normalized[slot_keys[0]],
                normalized[slot_keys[1]],
            )
            if _text((pair[0].get("source") or {}).get("sourceIdentity"))
            != _text((pair[1].get("source") or {}).get("sourceIdentity"))
        ]
        if not pairs:
            continue
        selected = min(pairs, key=_pair_sort_key)
        winners[slot_keys[0]] = selected[0]
        winners[slot_keys[1]] = selected[1]
    return winners


def snapshot_candidates_from_raiderio(
    payload: dict[str, Any],
    *,
    hero_resolver: Callable[
        [str, str, list[dict[str, Any]], str],
        str,
    ]
    | None = None,
) -> dict[str, Any]:
    """Build real snapshot candidates; never invent or cross-fill a slot."""

    if not isinstance(payload, dict):
        raise ValueError("Raider.IO payload must be an object")
    season_slug = _text(payload.get("seasonSlug"))
    if not season_slug:
        raise ValueError("Raider.IO payload seasonSlug is required")
    expected = _expected_slots_by_key()
    profiles = _profiles_by_identity(payload)
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    problems: dict[str, list[dict[str, Any]]] = defaultdict(list)
    attempted_specs: set[str] = set()
    for profile in profiles.values():
        profile_template = _profile_candidate_template(
            profile,
            hero_resolver,
        )
        if profile_template is None:
            continue
        slot = _template_slot(profile_template, expected)
        if slot is None:
            continue
        key = slot_key(slot)
        attempted_specs.add(f"{slot['classKey']}:{slot['specKey']}")
        try:
            candidates[key].append(
                _template_snapshot(
                    profile_template,
                    slot=slot,
                    profile=profile,
                    season_slug=season_slug,
                )
            )
        except ValueError as error:
            problems[key].append(
                _problem(
                    _text(error) or "snapshot_extraction_failed",
                    stage="collection",
                    source_identity=_profile_identity(profile),
                )
            )
    for raw_template in payload.get("communityTemplates") or []:
        if not isinstance(raw_template, dict):
            continue
        raw_template = _template_with_resolved_hero(
            raw_template,
            hero_resolver,
        )
        source_key = _text(raw_template.get("sourceKey"))
        if source_key not in {"", "raiderio"}:
            continue
        slot = _template_slot(raw_template, expected)
        if slot is None:
            continue
        key = slot_key(slot)
        attempted_specs.add(f"{slot['classKey']}:{slot['specKey']}")
        template_payload = raw_template.get("payload")
        template_payload = (
            template_payload if isinstance(template_payload, dict) else {}
        )
        rio = template_payload.get("raiderio")
        rio = rio if isinstance(rio, dict) else {}
        identity = _text(rio.get("sourceIdentity"))
        if not _source_identity_parts(identity):
            problems[key].append(
                _problem(
                    "source_identity_invalid",
                    stage="collection",
                )
            )
            continue
        profile = profiles.get(identity)
        if profile is None or not _normalized_gear(profile):
            problems[key].append(
                _problem(
                    "exact_profile_gear_missing",
                    stage="collection",
                    source_identity=identity,
                )
            )
            continue
        try:
            snapshot = _template_snapshot(
                raw_template,
                slot=slot,
                profile=profile,
                season_slug=season_slug,
            )
        except ValueError as error:
            problems[key].append(
                _problem(
                    _text(error) or "snapshot_extraction_failed",
                    stage="collection",
                    source_identity=identity,
                )
            )
            continue
        candidates[key].append(snapshot)

    normalized_candidates: dict[str, list[dict[str, Any]]] = {}
    for key, values in candidates.items():
        by_snapshot_id = {
            _text(snapshot.get("snapshotId")): snapshot
            for snapshot in values
        }
        normalized_candidates[key] = sorted(
            by_snapshot_id.values(),
            key=_candidate_sort_key,
        )

    winners = select_distinct_snapshot_winners(normalized_candidates)
    expected_slots_by_spec: dict[str, list[str]] = defaultdict(list)
    for key, slot in expected.items():
        expected_slots_by_spec[f"{slot['classKey']}:{slot['specKey']}"].append(key)
    for spec_id in sorted(attempted_specs):
        spec_slots = expected_slots_by_spec.get(spec_id) or []
        if len(spec_slots) == 2 and all(key in winners for key in spec_slots):
            continue
        for key in spec_slots:
            problems[key].append(
                _problem(
                    "distinct_spec_player_missing",
                    stage="selection",
                )
            )

    return {
        "candidatesBySlot": {
            key: normalized_candidates[key]
            for key in sorted(normalized_candidates)
        },
        "problemsBySlot": {
            key: problems[key]
            for key in sorted(problems)
        },
    }


__all__ = (
    "select_distinct_snapshot_winners",
    "snapshot_candidates_from_raiderio",
)

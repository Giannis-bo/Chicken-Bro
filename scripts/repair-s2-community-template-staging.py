#!/usr/bin/env python3
"""Build a fresh, explicitly derived community-template staging bundle.

The source bundle may contain fresh slot-complete templates whose individual
observed variants are still missing SimC stats.  This script only repairs
missing spec coverage from verified observed rows belonging to one real
profile; it never invents stats or promotes rows into the public Catalog.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.s2_community_exact import (  # noqa: E402
    _item_id,
    _profile_urls,
    _slot,
    _stats,
    select_s2_bindable_community_templates,
)
from server.websim_payload import (  # noqa: E402
    CANONICAL_GEAR_SLOTS,
    gear_template_signature,
    gear_template_slot_coverage,
    observed_profile_hash,
)


SHANGHAI = timezone(timedelta(hours=8))


def _text(value: Any) -> str:
    return str(value or "").strip()


def _load(path: Path) -> Any:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    target = path.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = handle.name
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        temporary = ""
    finally:
        if temporary:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def _expected_specs(bundle: Mapping[str, Any], templates: list[Mapping[str, Any]]) -> set[tuple[str, str]]:
    expected: set[tuple[str, str]] = set()
    for raw in bundle.get("expectedSpecs") or []:
        token = _text(raw)
        if ":" in token:
            class_key, spec_key = token.split(":", 1)
            if class_key and spec_key:
                expected.add((class_key, spec_key))
    if expected:
        return expected
    return {
        (_text(row.get("classKey")), _text(row.get("specKey")))
        for row in templates
        if _text(row.get("classKey")) and _text(row.get("specKey"))
    }


def _profile_rank(row: Mapping[str, Any]) -> tuple[float, int, str]:
    payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
    evidence = payload.get("rankingEvidence") if isinstance(payload.get("rankingEvidence"), Mapping) else {}
    try:
        score = float(payload.get("score") or evidence.get("score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    try:
        rank = int(payload.get("rank") or evidence.get("rank") or 0)
    except (TypeError, ValueError):
        rank = 0
    return score, -rank, _text(row.get("updatedAt"))


def _profile_ref(row: Mapping[str, Any], profile_url: str) -> dict[str, Any]:
    payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
    ranking_evidence = (
        payload.get("rankingEvidence")
        if isinstance(payload.get("rankingEvidence"), Mapping)
        else {}
    )
    if not ranking_evidence and any(
        payload.get(key) not in (None, "")
        for key in ("rank", "score", "maxKeyLevel", "runId")
    ):
        ranking_evidence = {
            "source": "raiderio_spec_ranking",
            **{
                key: payload.get(key)
                for key in ("rank", "score", "maxKeyLevel", "runId")
                if payload.get(key) not in (None, "")
            },
        }
    ref = {
        "id": f"observed-profile-{hashlib.sha1(profile_url.encode('utf-8')).hexdigest()[:16]}",
        "sourceKey": "raiderio_observed_profile",
        "sourceName": "Raider.IO observed profile",
        "profileUrl": profile_url,
        "sourceUrl": profile_url,
        "sourceStatus": "synced",
        "status": "verified",
        "sampleCount": 1,
        "analysisWindow": "Raider.IO observed profile gear",
    }
    for key in (
        "sourceIdentity",
        "characterName",
        "region",
        "realmSlug",
        "classKey",
        "specKey",
    ):
        value = _text(payload.get(key))
        if value:
            ref[key] = value
    for key in ("maxKeyLevel", "runId", "rank"):
        if payload.get(key) not in (None, ""):
            ref[key] = payload.get(key)
    if payload.get("score") not in (None, ""):
        ref["score"] = payload.get("score")
    if ranking_evidence:
        ref["rankingEvidence"] = copy.deepcopy(dict(ranking_evidence))
    return ref


def _repair_template(
    class_key: str,
    spec_key: str,
    profile_url: str,
    rows_by_slot: Mapping[str, Mapping[str, Any]],
    *,
    updated_at: str,
    expires_at: str,
) -> dict[str, Any]:
    candidate_items = []
    profile_refs = []
    for slot in sorted(rows_by_slot):
        row = rows_by_slot[slot]
        options = row.get("simcOptions") if isinstance(row.get("simcOptions"), Mapping) else {}
        profile_ref = _profile_ref(row, profile_url)
        item = {
            "slot": slot,
            "itemId": _item_id(row),
            "itemLevel": row.get("itemLevel") or row.get("ilevel"),
            "ilevel": str(row.get("itemLevel") or row.get("ilevel") or ""),
            "simcOptions": copy.deepcopy(dict(options)),
            "variantKey": _text(row.get("variantKey")),
            "observedProfileRefs": [copy.deepcopy(profile_ref)],
            "simcReady": True,
        }
        for key in (
            "bonus_id",
            "gem_id",
            "gem_bonus_id",
            "gem_ilevel",
            "enchant_id",
            "crafted_stats",
            "embellishment",
        ):
            if options.get(key) not in (None, ""):
                item[key] = options.get(key)
        payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
        if _text(payload.get("weaponType")):
            item["weaponType"] = _text(payload.get("weaponType"))
        icon_url = _text(payload.get("iconUrl") or payload.get("icon"))
        game_asset = payload.get("gameAsset") if isinstance(payload.get("gameAsset"), Mapping) else {}
        if not icon_url:
            icon_url = _text(game_asset.get("iconUrl"))
        if icon_url:
            item["iconUrl"] = icon_url
            item["gameAsset"] = {
                "entityId": _text(game_asset.get("entityId") or _item_id(row)),
                "entityType": _text(game_asset.get("entityType") or "item"),
                "iconUrl": icon_url,
                "status": "verified",
            }
        candidate_items.append(item)
        profile_refs.append(profile_ref)
    ready_by_slot, occupied_slots, missing_slots = gear_template_slot_coverage(
        candidate_items,
        class_key,
        spec_key,
    )
    if missing_slots:
        raise ValueError(
            f"verified profile remains incomplete for {class_key}:{spec_key}: "
            f"{','.join(missing_slots)}"
        )
    # Keep the original staging identity fields.  The coverage helper returns
    # a display-normalized copy whose fallback variant key is intentionally not
    # the immutable source variant key required by Exact binding.
    gear_items = sorted(
        candidate_items,
        key=lambda item: (
            CANONICAL_GEAR_SLOTS.index(item.get("slot"))
            if item.get("slot") in CANONICAL_GEAR_SLOTS
            else len(CANONICAL_GEAR_SLOTS),
            item.get("slot") or "",
        ),
    )
    ranking_evidence = {}
    for ref in profile_refs:
        if isinstance(ref.get("rankingEvidence"), Mapping):
            ranking_evidence = copy.deepcopy(dict(ref["rankingEvidence"]))
            break
    result = {
        "classKey": class_key,
        "specKey": spec_key,
        "gearItems": gear_items,
    }
    gear_hash = gear_template_signature(result)
    profile_hash = observed_profile_hash(
        class_key,
        spec_key,
        [profile_url],
        gear_hash,
        ranking_evidence,
    )
    profile_token = hashlib.sha1(profile_url.encode("utf-8")).hexdigest()[:12]
    template_id = f"codex-derived-observed-{class_key}-{spec_key}-{profile_token}"
    source_ref = copy.deepcopy(profile_refs[0])
    source_ref.update({"profileHash": profile_hash, "gearHash": gear_hash})
    source_refs = [source_ref]
    variant_keys = [_text(item.get("variantKey")) for item in gear_items]
    result = {
        "templateId": template_id,
        "name": f"{class_key}:{spec_key} · verified observed profile",
        "classKey": class_key,
        "specKey": spec_key,
        "sourceKey": "raiderio_observed_profile",
        "sourceName": "Raider.IO verified observed profile",
        "sourceUrl": profile_url,
        "sourceStatus": "synced",
        "status": "complete",
        "sampleCount": 1,
        "profileHash": profile_hash,
        "gearHash": gear_hash,
        "signature": gear_hash,
        "updatedAt": updated_at,
        "expiresAt": expires_at,
        "readySlotCount": len(CANONICAL_GEAR_SLOTS),
        "missingSlots": [],
        "gearItems": gear_items,
        "sourceRefs": source_refs,
        "payload": {
            "sampleCount": 1,
            "profileHash": profile_hash,
            "gearHash": gear_hash,
            "rankingEvidence": ranking_evidence,
            "truthScope": "community_observed",
            "officialFactStatus": "UNVERIFIED",
            "membershipKind": "derived_verified_observed_profile",
            "templateDerivation": {
                "schemaRevision": "s2-community-template-derivation-v1",
                "reason": "fresh source templates referenced observed rows without SimC stats",
                "sourceProfileUrl": profile_url,
                "sourceVariantKeys": variant_keys,
                "catalogExpansion": False,
            },
            "templateEvidence": {
                "sampleCount": 1,
                "profileHash": profile_hash,
                "gearHash": gear_hash,
                "sourceRefs": source_refs,
            },
        },
    }
    if occupied_slots:
        result["occupiedSlots"] = occupied_slots
    return result


def _derived_repairs(
    variants: list[Mapping[str, Any]],
    missing_specs: set[tuple[str, str]],
    *,
    updated_at: str,
    expires_at: str,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, list[Mapping[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in variants:
        if not isinstance(row, Mapping):
            continue
        if _text(row.get("sourceType")).lower() != "observed_profile":
            continue
        if _text(row.get("status")).lower() != "verified" or row.get("blockers"):
            continue
        if not _stats(row):
            continue
        class_key = _text((row.get("payload") or {}).get("classKey"))
        spec_key = _text((row.get("payload") or {}).get("specKey"))
        slot = _slot(row)
        profiles = sorted(_profile_urls(row))
        if not class_key or not spec_key or not slot or not profiles:
            continue
        for profile_url in profiles:
            grouped[(class_key, spec_key, profile_url)][slot].append(row)

    repairs = []
    for class_key, spec_key in sorted(missing_specs):
        candidates = []
        for (candidate_class, candidate_spec, profile_url), rows_by_slot in grouped.items():
            if (candidate_class, candidate_spec) != (class_key, spec_key):
                continue
            if len(rows_by_slot) >= len(CANONICAL_GEAR_SLOTS) - 1:
                chosen = {
                    slot: max(rows_by_slot[slot], key=lambda row: (_profile_rank(row), _text(row.get("variantKey"))))
                    for slot in rows_by_slot
                }
                try:
                    _repair_template(
                        class_key,
                        spec_key,
                        profile_url,
                        chosen,
                        updated_at=updated_at,
                        expires_at=expires_at,
                    )
                except ValueError:
                    continue
                score = max((_profile_rank(row) for row in chosen.values()), default=(0.0, 0, ""))
                candidates.append((score, profile_url, chosen))
        if not candidates:
            raise ValueError(f"no verified 16-slot observed profile for {class_key}:{spec_key}")
        _score, profile_url, rows_by_slot = max(candidates, key=lambda value: (value[0], value[1]))
        repairs.append(_repair_template(
            class_key,
            spec_key,
            profile_url,
            rows_by_slot,
            updated_at=updated_at,
            expires_at=expires_at,
        ))
    return repairs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    bundle = _load(args.input)
    if not isinstance(bundle, Mapping):
        raise ValueError("staging bundle must be an object")
    gear = bundle.get("gear") if isinstance(bundle.get("gear"), Mapping) else {}
    variants = [row for row in gear.get("variants") or [] if isinstance(row, Mapping)]
    templates = [row for row in bundle.get("templates") or [] if isinstance(row, Mapping)]
    now = datetime.now(SHANGHAI)
    updated_at = now.isoformat(timespec="seconds")
    expires_at = (now + timedelta(days=14)).isoformat(timespec="seconds")
    bindable = select_s2_bindable_community_templates(
        templates,
        variants,
        now=updated_at,
    )
    expected = _expected_specs(bundle, templates)
    present = {(_text(row.get("classKey")), _text(row.get("specKey"))) for row in bindable}
    missing = expected - present
    repairs = _derived_repairs(
        variants,
        missing,
        updated_at=updated_at,
        expires_at=expires_at,
    )
    repaired = [*bindable, *repairs]
    repaired_specs = {(_text(row.get("classKey")), _text(row.get("specKey"))) for row in repaired}
    if repaired_specs != expected:
        raise ValueError(f"community template coverage remains incomplete: {len(repaired_specs)}/{len(expected)}")
    output = {
        "schemaRevision": bundle.get("schemaRevision") or "s2-community-exact-staging-v1",
        "expectedSpecs": sorted(f"{class_key}:{spec_key}" for class_key, spec_key in expected),
        "gear": copy.deepcopy(dict(gear)),
        "templates": repaired,
        "repairMetadata": {
            "schemaRevision": "s2-community-template-repair-v1",
            "generatedAt": updated_at,
            "expiresAt": expires_at,
            "sourceBundle": str(args.input.expanduser().resolve().relative_to(ROOT)),
            "bindableSourceTemplateCount": len(bindable),
            "derivedTemplateCount": len(repairs),
            "derivedSpecs": sorted(f"{class_key}:{spec_key}" for class_key, spec_key in missing),
            "truthScope": "community_observed",
            "catalogExpansion": False,
        },
    }
    _atomic_write(args.output, output)
    print(json.dumps({
        "status": "verified",
        "expectedSpecCount": len(expected),
        "templateCount": len(repaired),
        "bindableSourceTemplateCount": len(bindable),
        "derivedTemplateCount": len(repairs),
        "derivedSpecs": sorted(f"{class_key}:{spec_key}" for class_key, spec_key in missing),
        "output": str(args.output.expanduser().resolve()),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)

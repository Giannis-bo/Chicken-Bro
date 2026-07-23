#!/usr/bin/env python3
"""Compile one immutable observed player through existing backend authorities."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

try:
    from . import gear_resolver
    from .gear_contracts import parse_selection_intent
    from .gear_release_tool import selection_intent_from_template
    from .observed_build_projection import build_projection
    from .websim_payload import (
        gear_resolver_runtime_authority,
        normalized_websim_level,
        validate_community_talent_template,
    )
except ImportError:
    import gear_resolver
    from gear_contracts import parse_selection_intent
    from gear_release_tool import selection_intent_from_template
    from observed_build_projection import build_projection
    from websim_payload import (
        gear_resolver_runtime_authority,
        normalized_websim_level,
        validate_community_talent_template,
    )


_RUNTIME_DEPENDENCIES = {
    "gearRuleRevision": "gearRuleRevision",
    "resolverContractRevision": "resolverContractRevision",
    "serializerRevision": "serializerRevision",
    "simcRuntimeRevision": "simcRuntimeRevision",
    "selectionSchemaRevision": "selectionSchemaRevision",
}


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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bounded_text(value: Any, limit: int) -> str:
    return _text(value)[:limit]


def _safe_problem(
    problem: Any,
    *,
    default_code: str,
    default_stage: str,
    default_message: str = "",
) -> dict[str, str]:
    source = problem if isinstance(problem, dict) else {}
    normalized = {
        "code": _bounded_text(source.get("code") or default_code, 120),
        "stage": _bounded_text(source.get("stage") or default_stage, 80),
    }
    message = _bounded_text(source.get("message") or default_message, 320)
    if message:
        normalized["message"] = message
    return normalized


def _adapter_failure(stage: str) -> dict[str, str]:
    subject = "Talent" if stage == "talent_projection" else "Gear"
    return {
        "code": f"{stage}_failed",
        "stage": stage,
        "message": f"{subject} projection failed unexpectedly.",
    }


def _run_adapter(
    snapshot: dict[str, Any],
    compiler: Callable[[dict[str, Any]], Any],
    *,
    stage: str,
) -> dict[str, Any]:
    try:
        result = compiler(snapshot)
    except Exception:
        return {
            "status": "blocked",
            "problems": [_adapter_failure(stage)],
        }
    if not isinstance(result, dict):
        return {
            "status": "blocked",
            "problems": [_adapter_failure(stage)],
        }
    return _canonical(result)


def _profile_signature(
    snapshot: dict[str, Any],
    dependency_vector: dict[str, Any],
    talent: dict[str, Any],
    gear: dict[str, Any],
) -> str:
    payload = {
        "snapshotId": snapshot.get("snapshotId"),
        "dependencyVector": dependency_vector,
        "talentSignature": talent.get("signature"),
        "resolvedGearSignature": gear.get("resolvedGearSignature"),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def compile_observed_build(
    snapshot: dict[str, Any],
    dependency_vector: dict[str, Any],
    talent_compiler: Callable[[dict[str, Any]], Any],
    gear_compiler: Callable[[dict[str, Any]], Any],
) -> dict[str, Any]:
    """Compile talent and gear atomically into one projection.

    Adapter exceptions deliberately become fixed, bounded problems. Exception
    strings may contain credentials or raw source payloads and are never copied
    into the immutable projection.
    """

    talent = _run_adapter(
        snapshot,
        talent_compiler,
        stage="talent_projection",
    )
    gear = _run_adapter(
        snapshot,
        gear_compiler,
        stage="gear_projection",
    )
    problems = [
        _safe_problem(
            problem,
            default_code=f"{stage}_blocked",
            default_stage=stage,
        )
        for section, stage in (
            (talent, "talent_projection"),
            (gear, "gear_projection"),
        )
        for problem in section.get("problems") or []
    ]
    ready = (
        talent.get("status") == "verified"
        and gear.get("status") == "verified"
        and not problems
    )
    profile_readiness = {
        "status": "ready" if ready else "blocked",
        "simcReady": ready,
    }
    if ready:
        profile_readiness["profileSignature"] = _profile_signature(
            snapshot,
            dependency_vector,
            talent,
            gear,
        )
    return build_projection(
        snapshot=snapshot,
        dependency_vector=dependency_vector,
        talent_projection=talent,
        gear_projection=gear,
        profile_readiness=profile_readiness,
        problems=problems,
    )


def _talent_candidate(snapshot: dict[str, Any]) -> dict[str, Any]:
    slot = snapshot.get("slot") if isinstance(snapshot.get("slot"), dict) else {}
    source = (
        snapshot.get("source")
        if isinstance(snapshot.get("source"), dict)
        else {}
    )
    observation = (
        snapshot.get("talentObservation")
        if isinstance(snapshot.get("talentObservation"), dict)
        else {}
    )
    evidence = (
        snapshot.get("rankingEvidence")
        if isinstance(snapshot.get("rankingEvidence"), dict)
        else {}
    )
    return {
        "id": snapshot.get("snapshotId"),
        "classKey": slot.get("classKey"),
        "specKey": slot.get("specKey"),
        "heroKey": slot.get("heroKey"),
        "scenarioKey": slot.get("scenarioKey"),
        "sourceKey": "raiderio",
        "sourceName": "Raider.IO",
        "sourceStatus": "synced",
        "sourceUrl": source.get("profileUrl"),
        "status": "verified",
        "rawImportCode": observation.get("rawImportCode"),
        "playerId": source.get("character"),
        "maxKeyLevel": evidence.get("maxKeyLevel") or 0,
        "sampleCount": 1,
        "payload": {
            "raiderio": {
                "sourceIdentity": source.get("sourceIdentity"),
                "profileUrl": source.get("profileUrl"),
                "characterName": source.get("character"),
                "realm": source.get("realm"),
                "realmSlug": source.get("realm"),
                "region": source.get("region"),
                "heroKey": slot.get("heroKey"),
                "heroSubTreeId": observation.get("heroSubTreeId"),
                "loadoutSpecId": observation.get("loadoutSpecId"),
                "loadout": _canonical(observation.get("loadout") or []),
                "selector": _canonical(observation.get("selector") or {}),
                "source": observation.get("source") or "profile_current",
            },
            "rioEvidence": _canonical(evidence),
            "observedBuild": {
                "snapshotId": snapshot.get("snapshotId"),
                "sourceRevision": snapshot.get("sourceRevision"),
            },
        },
    }


def _compile_talent_with_postgres(
    store: Any,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    validated = validate_community_talent_template(
        store,
        _talent_candidate(snapshot),
    )
    validated = validated if isinstance(validated, dict) else {}
    talent_state = (
        validated.get("talentState")
        if isinstance(validated.get("talentState"), dict)
        else {}
    )
    selected_nodes = talent_state.get("selectedNodes")
    export_code = _text(validated.get("websimExportCode"))
    slot = snapshot.get("slot") if isinstance(snapshot.get("slot"), dict) else {}
    if (
        validated.get("status") != "verified"
        or not isinstance(selected_nodes, list)
        or not selected_nodes
        or not export_code.startswith("websim:")
        or _text(validated.get("heroKey")) != _text(slot.get("heroKey"))
    ):
        return {
            "status": "blocked",
            "problems": [
                {
                    "code": "talent_mapping_failed",
                    "stage": "talent_projection",
                    "message": "Observed talents did not map to a verified Hero loadout.",
                }
            ],
        }
    source = snapshot.get("source") if isinstance(snapshot.get("source"), dict) else {}
    return {
        "status": "verified",
        "heroKey": _text(validated.get("heroKey")),
        "talentState": _canonical(talent_state),
        "websimExportCode": export_code,
        "rawImportCode": _text(validated.get("rawImportCode")),
        "signature": _text(validated.get("signature")),
        "provenance": {
            "snapshotId": snapshot.get("snapshotId"),
            "sourceIdentity": source.get("sourceIdentity"),
            "profileUrl": source.get("profileUrl"),
            "sourceRevision": snapshot.get("sourceRevision"),
        },
    }


def _active_gear_compile_context(
    store: Any,
    class_key: str,
    spec_key: str,
) -> dict[str, Any]:
    """Read the current sealed Gear Release through one narrow adapter seam."""

    public_loader = getattr(
        store,
        "get_observed_build_gear_compile_context",
        None,
    )
    if callable(public_loader):
        context = public_loader(class_key, spec_key)
        if isinstance(context, dict):
            return context
        raise ValueError("current Gear Release context is invalid")

    binding_loader = getattr(store, "_active_manifest_binding_for_authority", None)
    release_store = getattr(store, "_gear_release_store", None)
    catalog_loader = getattr(release_store, "load_active_public_gear", None)
    if not callable(binding_loader) or not callable(catalog_loader):
        raise ValueError("current Gear Release context is unavailable")
    binding = binding_loader()
    binding = binding if isinstance(binding, dict) else {}
    data = catalog_loader(
        binding,
        class_key,
        spec_key,
        include_catalog=True,
    )
    data = data if isinstance(data, dict) else {}
    return {
        "manifest": _canonical(
            binding.get("manifest")
            if isinstance(binding.get("manifest"), dict)
            else {}
        ),
        "gearRelease": _canonical(
            data.get("gearRelease")
            if isinstance(data.get("gearRelease"), dict)
            else {}
        ),
        "gearSnapshot": _canonical(
            data.get("gearSnapshot")
            if isinstance(data.get("gearSnapshot"), dict)
            else {}
        ),
    }


def _require_current_dependencies(
    dependency_vector: dict[str, Any],
    simc_runtime_revision: str,
    release_context: dict[str, Any],
    runtime_authority: dict[str, Any],
) -> None:
    if _text(simc_runtime_revision) != _text(
        dependency_vector.get("simcRuntimeRevision")
    ):
        raise ValueError("SimulationCraft runtime dependency drifted")
    manifest = (
        release_context.get("manifest")
        if isinstance(release_context.get("manifest"), dict)
        else {}
    )
    release = (
        release_context.get("gearRelease")
        if isinstance(release_context.get("gearRelease"), dict)
        else {}
    )
    gear_release_id = _text(
        release.get("releaseId")
        or manifest.get("gearCatalogReleaseId")
    )
    if gear_release_id != _text(dependency_vector.get("gearReleaseId")):
        raise ValueError("Gear Release dependency drifted")
    if _text(manifest.get("seasonRevision")) != _text(
        dependency_vector.get("seasonRevision")
    ):
        raise ValueError("season dependency drifted")
    runtime_dependencies = (
        runtime_authority.get("dependencyRevisions")
        if isinstance(runtime_authority.get("dependencyRevisions"), dict)
        else {}
    )
    for runtime_field, projection_field in _RUNTIME_DEPENDENCIES.items():
        if _text(runtime_dependencies.get(runtime_field)) != _text(
            dependency_vector.get(projection_field)
        ):
            raise ValueError(f"{runtime_field} dependency drifted")


def _profile_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    source = snapshot.get("source") if isinstance(snapshot.get("source"), dict) else {}
    slot = snapshot.get("slot") if isinstance(snapshot.get("slot"), dict) else {}
    observation = (
        snapshot.get("gearObservation")
        if isinstance(snapshot.get("gearObservation"), dict)
        else {}
    )
    return {
        "sourceIdentity": source.get("sourceIdentity"),
        "profileUrl": source.get("profileUrl"),
        "name": source.get("character"),
        "realm": source.get("realm"),
        "realmSlug": source.get("realm"),
        "region": source.get("region"),
        "classKey": slot.get("classKey"),
        "specKey": slot.get("specKey"),
        "raceKey": observation.get("raceKey"),
        "itemLevel": observation.get("itemLevel"),
        "rankingEvidence": _canonical(snapshot.get("rankingEvidence") or {}),
        "gear": _canonical(observation.get("gearItems") or []),
    }


def prepare_observed_gear_with_postgres(
    store: Any,
    snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    """Backfill only the exact profiles selected for this observed-build run."""

    profiles = [
        _profile_from_snapshot(snapshot)
        for snapshot in snapshots
        if isinstance(snapshot, dict)
    ]
    if not profiles:
        return {
            "status": "verified",
            "sourceStatus": "verified",
            "profileCount": 0,
        }
    result = store.backfill_observed_gear_from_raiderio(
        {"profiles": profiles},
        mode="observed_build_compile",
        profile_limit=len(profiles),
        enable_simc_stats=False,
    )
    result = result if isinstance(result, dict) else {}
    status = _text(result.get("status") or result.get("sourceStatus"))
    if status in {"blocked", "failed"}:
        raise ValueError("observed gear authority backfill failed")
    return _canonical(result)


def _gear_template(snapshot: dict[str, Any]) -> dict[str, Any]:
    source = snapshot.get("source") if isinstance(snapshot.get("source"), dict) else {}
    slot = snapshot.get("slot") if isinstance(snapshot.get("slot"), dict) else {}
    observation = (
        snapshot.get("gearObservation")
        if isinstance(snapshot.get("gearObservation"), dict)
        else {}
    )
    profile_url = _text(source.get("profileUrl"))
    gear_items = []
    for raw_item in observation.get("gearItems") or []:
        if not isinstance(raw_item, dict):
            continue
        item = _canonical(raw_item)
        refs = [
            ref
            for ref in item.get("observedProfileRefs") or []
            if isinstance(ref, dict)
        ]
        if profile_url and not any(
            _text(ref.get("profileUrl")) == profile_url
            for ref in refs
        ):
            refs.append({"profileUrl": profile_url})
        if refs:
            item["observedProfileRefs"] = refs
        gear_items.append(item)
    return {
        "id": snapshot.get("snapshotId"),
        "templateId": snapshot.get("snapshotId"),
        "classKey": slot.get("classKey"),
        "specKey": slot.get("specKey"),
        "heroKey": slot.get("heroKey"),
        "scenarioKey": slot.get("scenarioKey"),
        "sourceKey": "raiderio",
        "sourceUrl": profile_url,
        "sourceStatus": "verified",
        "profileHash": snapshot.get("profileHash"),
        "gearHash": snapshot.get("gearHash"),
        "gearItems": gear_items,
        "payload": {
            "sourceIdentity": source.get("sourceIdentity"),
            "snapshotId": snapshot.get("snapshotId"),
        },
    }


def _enhancement_by_slot(intent: dict[str, Any]) -> dict[str, Any]:
    output = {}
    for slot, selection in sorted((intent.get("slots") or {}).items()):
        if not isinstance(selection, dict):
            continue
        enhancements = {
            "gemOptionIds": _canonical(selection.get("gemOptionIds") or []),
            "enchantOptionId": _text(selection.get("enchantOptionId")),
            "embellishmentOptionId": _text(
                selection.get("embellishmentOptionId")
            ),
        }
        if (
            enhancements["gemOptionIds"]
            or enhancements["enchantOptionId"]
            or enhancements["embellishmentOptionId"]
        ):
            output[slot] = enhancements
    return output


def _compile_gear_with_postgres(
    store: Any,
    snapshot: dict[str, Any],
    dependency_vector: dict[str, Any],
    simc_runtime_revision: str,
    *,
    gear_prepared: bool = False,
) -> dict[str, Any]:
    slot = snapshot.get("slot") if isinstance(snapshot.get("slot"), dict) else {}
    class_key = _text(slot.get("classKey"))
    spec_key = _text(slot.get("specKey"))
    runtime_authority = gear_resolver_runtime_authority(
        class_key,
        spec_key,
        simc_runtime_revision=simc_runtime_revision,
    )
    release_context = _active_gear_compile_context(
        store,
        class_key,
        spec_key,
    )
    _require_current_dependencies(
        dependency_vector,
        simc_runtime_revision,
        release_context,
        runtime_authority,
    )
    if not gear_prepared:
        prepare_observed_gear_with_postgres(store, [snapshot])
    release = release_context["gearRelease"]
    release_dependencies = (
        release.get("dependencyRevisions")
        if isinstance(release.get("dependencyRevisions"), dict)
        else {}
    )
    manifest = release_context["manifest"]
    intent = selection_intent_from_template(
        _gear_template(snapshot),
        gear_release_id=_text(release.get("releaseId")),
        season_revision=_text(manifest.get("seasonRevision")),
        level=normalized_websim_level(
            (snapshot.get("gearObservation") or {}).get("level")
        ),
        gear_snapshot=release_context["gearSnapshot"],
        capability_revision=_text(
            release_dependencies.get("capabilityRevision")
            or (runtime_authority.get("dependencyRevisions") or {}).get(
                "capabilityRevision"
            )
        ),
    )
    parsed_intent, intent_issues = parse_selection_intent(intent)
    if intent_issues or not isinstance(parsed_intent, dict):
        return {
            "status": "blocked",
            "problems": [
                {
                    "code": "gear_selection_intent_invalid",
                    "stage": "gear_projection",
                    "message": "Observed gear did not map to a valid SelectionIntent.",
                }
            ],
        }
    authority_context = store.get_gear_authority_context(
        parsed_intent,
        runtime_authority,
    )
    resolved = gear_resolver.resolve(parsed_intent, authority_context)
    resolved = resolved if isinstance(resolved, dict) else {}
    readiness = (
        resolved.get("profileReadiness")
        if isinstance(resolved.get("profileReadiness"), dict)
        else {}
    )
    resolved_slots = (
        resolved.get("resolvedSlots")
        if isinstance(resolved.get("resolvedSlots"), dict)
        else {}
    )
    serializer_input = (
        resolved.get("serializerInput")
        if isinstance(resolved.get("serializerInput"), dict)
        else {}
    )
    serializer_items = serializer_input.get("gearItems")
    if (
        resolved.get("status") != "verified"
        or resolved.get("problems")
        or readiness.get("status") != "ready"
        or readiness.get("simcReady") is not True
        or not _text(resolved.get("resolvedGearSignature"))
        or not resolved_slots
        or not isinstance(serializer_items, list)
        or len(serializer_items) != len(resolved_slots)
    ):
        return {
            "status": "blocked",
            "problems": [
                {
                    "code": "gear_mapping_failed",
                    "stage": "gear_projection",
                    "message": "Observed gear did not resolve to a complete canonical profile.",
                }
            ],
        }
    source = snapshot.get("source") if isinstance(snapshot.get("source"), dict) else {}
    return {
        "status": "verified",
        "selectionIntent": _canonical(parsed_intent),
        "gearItems": _canonical(serializer_items),
        "enhancementBySlot": _enhancement_by_slot(parsed_intent),
        "resolvedGearSignature": _text(
            resolved.get("resolvedGearSignature")
        ),
        "profileReadiness": _canonical(readiness),
        "resolverDependencyVector": _canonical(
            resolved.get("dependencyVector") or {}
        ),
        "provenance": {
            "snapshotId": snapshot.get("snapshotId"),
            "sourceIdentity": source.get("sourceIdentity"),
            "profileUrl": source.get("profileUrl"),
            "sourceRevision": snapshot.get("sourceRevision"),
        },
    }


def compile_with_postgres(
    store: Any,
    snapshot: dict[str, Any],
    dependency_vector: dict[str, Any],
    simc_runtime_revision: str,
    *,
    gear_prepared: bool = False,
) -> dict[str, Any]:
    """Compile one shared player through current PG talent and gear authorities."""

    return compile_observed_build(
        snapshot,
        dependency_vector,
        talent_compiler=lambda value: _compile_talent_with_postgres(
            store,
            value,
        ),
        gear_compiler=lambda value: _compile_gear_with_postgres(
            store,
            value,
            dependency_vector,
            simc_runtime_revision,
            gear_prepared=gear_prepared,
        ),
    )


__all__ = (
    "compile_observed_build",
    "compile_with_postgres",
    "prepare_observed_gear_with_postgres",
)

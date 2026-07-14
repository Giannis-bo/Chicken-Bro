#!/usr/bin/env python3
"""Internal read-only old/new shadow orchestration for inactive releases."""

from __future__ import annotations

import copy
import time
from typing import Any, Iterable

try:
    from . import gear_release, gear_runtime, gear_socket_authority, pg_gear_read_model_selectors
    from .websim_payload import gear_resolver_runtime_authority, normalize_slot
except ImportError:
    import gear_release
    import gear_runtime
    import gear_socket_authority
    import pg_gear_read_model_selectors
    from websim_payload import gear_resolver_runtime_authority, normalize_slot


_REFERENCE_TEMPLATE_ID = "observed_profile_mage_frost"
_REFERENCE_SPEC = ("mage", "frost")
_REFERENCE_SOCKET_SLOTS = ("head", "neck", "wrist", "waist", "finger1", "finger2")
_REFERENCE_SOCKET_VECTOR = [1, 2, 1, 1, 2, 1]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _blocker(code: str, class_key: str = "", spec_key: str = "", detail: str = "") -> dict[str, Any]:
    path = "shadow"
    if class_key or spec_key:
        path = f"specs.{class_key}.{spec_key}"
    return {
        "kind": "SHADOW_COMPARE_BLOCKED",
        "code": code,
        "title": "Release shadow comparison blocked.",
        "detail": detail,
        "path": path,
        "retryable": False,
        "meta": {},
    }


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _selection_intent_from_template(
    template: dict[str, Any],
    *,
    gear_release_id: str,
    season_revision: str,
    level: int,
) -> dict[str, Any]:
    slots: dict[str, dict[str, Any]] = {}
    for raw in template.get("gearItems") or []:
        if not isinstance(raw, dict):
            continue
        slot = normalize_slot(raw.get("slot") or raw.get("simcSlot"))
        item_id = _text(raw.get("itemId") or raw.get("id"))
        if not slot or not item_id or slot in slots:
            continue
        slots[slot] = {
            "itemId": item_id,
            "variantKey": _text(raw.get("variantKey")),
            "gemOptionIds": [],
            "enchantOptionId": "",
            "embellishmentOptionId": "",
            "craftedOptionId": "",
            "catalystOptionId": "",
        }
    return {
        "schemaRevision": "selection-intent-v1",
        "authoredAgainst": {
            "seasonRevision": _text(season_revision),
            "gearCatalogRevision": _text(gear_release_id),
        },
        "eligibilityContext": {
            "classKey": _text(template.get("classKey")),
            "specKey": _text(template.get("specKey")),
            "level": _int(level),
        },
        "slots": {key: slots[key] for key in sorted(slots)},
    }


def _resolved_snapshot(http_status: int, envelope: Any) -> dict[str, Any] | None:
    value = envelope if isinstance(envelope, dict) else {}
    data = value.get("data") if isinstance(value.get("data"), dict) else {}
    if http_status == 200 and value.get("status") == "resolved" and data.get("status") == "verified":
        return data
    return None


def _problem_codes(envelope: Any) -> list[str]:
    value = envelope if isinstance(envelope, dict) else {}
    problems = value.get("problems") if isinstance(value.get("problems"), list) else []
    return sorted({
        _text(problem.get("code"))
        for problem in problems
        if isinstance(problem, dict) and _text(problem.get("code"))
    })


def _profile_outcome(http_status: int, envelope: Any) -> dict[str, Any]:
    """Normalize user-visible canonical Profile output while ignoring release-only metadata."""

    value = envelope if isinstance(envelope, dict) else {}
    data = value.get("data") if isinstance(value.get("data"), dict) else {}
    return {
        "httpStatus": http_status,
        "status": _text(value.get("status")),
        "problemCodes": _problem_codes(value),
        "data": {
            field: data.get(field)
            for field in (
                "profile",
                "gearItems",
                "simcItems",
                "readiness",
                "talentEncoding",
                "preparation",
                "profileReadiness",
            )
            if field in data
        },
    }


def _enhancement_selection_projection(intent: Any) -> dict[str, dict[str, Any]]:
    value = intent if isinstance(intent, dict) else {}
    result = {}
    for slot, selection in (value.get("slots") or {}).items():
        if not isinstance(selection, dict):
            continue
        result[_text(slot)] = {
            "gemOptionIds": list(selection.get("gemOptionIds") or []),
            "enchantOptionId": _text(selection.get("enchantOptionId")),
            "embellishmentOptionId": _text(selection.get("embellishmentOptionId")),
        }
    return result


def _non_enhancement_selection_projection(intent: Any) -> dict[str, Any]:
    """Retain every Intent field outside the three approved migration fields."""

    value = intent if isinstance(intent, dict) else {}
    projected = {
        key: copy.deepcopy(field_value)
        for key, field_value in value.items()
        if key not in {"authoredAgainst", "slots"}
    }
    projected_slots = {}
    for slot, selection in (value.get("slots") or {}).items():
        if not isinstance(selection, dict):
            projected_slots[_text(slot)] = copy.deepcopy(selection)
            continue
        projected_slots[_text(slot)] = {
            key: copy.deepcopy(field_value)
            for key, field_value in selection.items()
            if key not in {
                "gemOptionIds",
                "enchantOptionId",
                "embellishmentOptionId",
            }
        }
    projected["slots"] = projected_slots
    return projected


def _enhancement_migration_projection(snapshot: Any) -> dict[str, Any]:
    """Compare resolved function while excluding only canonical editor occupancy state."""

    value = snapshot if isinstance(snapshot, dict) else {}
    resolved_slots = {}
    for slot, resolved in (value.get("resolvedSlots") or {}).items():
        if not isinstance(resolved, dict):
            continue
        projected = {}
        for key, field_value in resolved.items():
            if key in {
                "selectedOptions",
                "sourceRefIds",
                "evidenceClaimIds",
                "resolutionStages",
            }:
                continue
            if key == "statDeltas" and isinstance(field_value, dict):
                projected[key] = {
                    delta_key: copy.deepcopy(delta_value)
                    for delta_key, delta_value in field_value.items()
                    if delta_key != "enhancements"
                }
                continue
            projected[key] = copy.deepcopy(field_value)
        resolved_slots[_text(slot)] = projected
    raw_constraints = value.get("constraints") if isinstance(value.get("constraints"), dict) else {}
    constraint_slots = {}
    for slot, constraint in (raw_constraints.get("slots") or {}).items():
        if not isinstance(constraint, dict):
            continue
        constraint_slots[_text(slot)] = {
            key: copy.deepcopy(field_value)
            for key, field_value in constraint.items()
            if key not in {
                "socketRemaining",
                "hasSelectedEnchant",
                "hasSelectedEmbellishment",
            }
        }
    constraints = {
        key: copy.deepcopy(field_value)
        for key, field_value in raw_constraints.items()
        if key not in {
            "slots",
            "embellishmentSelectedUsed",
            "embellishmentUsed",
        }
    }
    constraints["slots"] = constraint_slots
    return {
        "eligibilityContext": copy.deepcopy(value.get("eligibilityContext") or {}),
        "resolvedSlots": resolved_slots,
        "staticAttributes": copy.deepcopy(value.get("staticAttributes") or {}),
        "setState": copy.deepcopy(value.get("setState") or {}),
        "constraints": constraints,
        "serializerInput": copy.deepcopy(value.get("serializerInput") or {}),
        "profileReadiness": copy.deepcopy(value.get("profileReadiness") or {}),
    }


def _reference_contract_proof(
    candidate: dict[str, Any],
    intent: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    slots = intent.get("slots") if isinstance(intent.get("slots"), dict) else {}
    resolved_slots = (
        snapshot.get("resolvedSlots")
        if isinstance(snapshot.get("resolvedSlots"), dict)
        else {}
    )
    constraints = snapshot.get("constraints") if isinstance(snapshot.get("constraints"), dict) else {}
    constraint_slots = constraints.get("slots") if isinstance(constraints.get("slots"), dict) else {}
    socket_vector = [
        _int((constraint_slots.get(slot) or {}).get("socketCount"))
        for slot in _REFERENCE_SOCKET_SLOTS
    ]

    def selected(slot: str) -> dict[str, Any]:
        row = resolved_slots.get(slot) if isinstance(resolved_slots.get(slot), dict) else {}
        selected_options = row.get("selectedOptions") if isinstance(row.get("selectedOptions"), dict) else {}
        return selected_options

    intent_gems = sum(
        len(selection.get("gemOptionIds") or [])
        for selection in slots.values()
        if isinstance(selection, dict)
    )
    resolved_gems = sum(
        len(selected(slot).get("gemOptionIds") or [])
        for slot in resolved_slots
    )
    intent_enchants = sum(
        bool(_text(selection.get("enchantOptionId")))
        for selection in slots.values()
        if isinstance(selection, dict)
    )
    resolved_enchants = sum(
        bool(_text(selected(slot).get("enchantOptionId")))
        for slot in resolved_slots
    )
    enchant_max = sum(
        constraint.get("canEnchant") is True
        for constraint in constraint_slots.values()
        if isinstance(constraint, dict)
    )
    intent_embellishments = sum(
        bool(_text(selection.get("embellishmentOptionId")))
        for selection in slots.values()
        if isinstance(selection, dict)
    )
    resolved_embellishments = sum(
        bool(_text(selected(slot).get("embellishmentOptionId")))
        for slot in resolved_slots
    )
    failures = []
    if (
        _text(candidate.get("sourceKey")) != "raiderio_observed_profile"
        or not _text(candidate.get("profileHash"))
        or not _text(candidate.get("gearHash"))
    ):
        failures.append("identity")
    if (
        (intent.get("eligibilityContext") or {}).get("classKey") != "mage"
        or (intent.get("eligibilityContext") or {}).get("specKey") != "frost"
        or len(slots) != 15
    ):
        failures.append("gear")
    if socket_vector != _REFERENCE_SOCKET_VECTOR:
        failures.append("socket_vector")
    if intent_gems != 8 or resolved_gems != 8 or sum(socket_vector) != 8:
        failures.append("gems")
    if intent_enchants != 6 or resolved_enchants != 6 or enchant_max != 8:
        failures.append("enchants")
    if (
        intent_embellishments != 2
        or resolved_embellishments != 2
        or _int(constraints.get("embellishmentMax")) != 2
    ):
        failures.append("embellishments")
    return {
        "status": "blocked" if failures else "pass",
        "templateId": _REFERENCE_TEMPLATE_ID,
        "sourceKey": _text(candidate.get("sourceKey")),
        "profileHash": _text(candidate.get("profileHash")),
        "gearHash": _text(candidate.get("gearHash")),
        "socketSlots": list(_REFERENCE_SOCKET_SLOTS),
        "socketVector": socket_vector,
        "gems": {"used": resolved_gems, "max": sum(socket_vector)},
        "enchants": {"used": resolved_enchants, "max": enchant_max},
        "embellishments": {
            "used": resolved_embellishments,
            "max": _int(constraints.get("embellishmentMax")),
        },
        "failures": failures,
        "ninthGem": {"status": "not_run", "problemCodes": []},
    }


def run_release_shadow(
    store: Any,
    *,
    expected_specs: Iterable[tuple[str, str]],
    gear_release_id: str,
    community_release_id: str,
    simc_runtime_revision: str,
    level: int = 90,
    profile_context_by_spec: dict[str, dict[str, Any]] | None = None,
    compare_profiles: bool = True,
    expect_formal_active: bool = False,
    allow_degraded_empty: bool = False,
) -> dict[str, Any]:
    """Run an internal shadow matrix without changing public routing or state."""

    shadow_started = time.perf_counter()
    expected = sorted({
        (_text(class_key), _text(spec_key))
        for class_key, spec_key in expected_specs
        if _text(class_key) and _text(spec_key)
    })
    gear_id = _text(gear_release_id)
    community_id = _text(community_release_id)
    blockers: list[dict[str, Any]] = []
    if not expected or len(expected) > 40:
        blockers.append(_blocker("EXPECTED_SPEC_MATRIX_INVALID", detail="Expected matrix must contain 1 to 40 specs."))
    if not gear_id or not community_id:
        blockers.append(_blocker("CANDIDATE_RELEASE_BINDING_MISSING", detail="Both candidate release IDs are required."))
    if blockers:
        return {
            "schemaRevision": "gear-release-shadow-execution-v1",
            "status": "blocked",
            "gearReleaseId": gear_id,
            "communityReleaseId": community_id,
            "report": {},
            "blockers": blockers,
            "specResults": [],
            "publicReadCount": 0,
            "formalActiveManifest": False,
        }

    try:
        pair = store.get_candidate_community_release(gear_id, community_id)
    except Exception:
        return {
            "schemaRevision": "gear-release-shadow-execution-v1",
            "status": "blocked",
            "gearReleaseId": gear_id,
            "communityReleaseId": community_id,
            "report": {},
            "blockers": [_blocker("CANDIDATE_RELEASE_READ_FAILED", detail="Candidate release pair is unavailable or invalid.")],
            "specResults": [],
            "publicReadCount": 0,
            "formalActiveManifest": False,
        }
    if not isinstance(pair, dict):
        return {
            "schemaRevision": "gear-release-shadow-execution-v1",
            "status": "blocked",
            "gearReleaseId": gear_id,
            "communityReleaseId": community_id,
            "report": {},
            "blockers": [_blocker("CANDIDATE_RELEASE_READ_FAILED", detail="Candidate release pair is unavailable or invalid.")],
            "specResults": [],
            "publicReadCount": 0,
            "formalActiveManifest": False,
        }

    winners_by_spec: dict[tuple[str, str], dict[str, Any]] = {}
    for winner in pair.get("winners") or []:
        if not isinstance(winner, dict):
            continue
        key = (_text(winner.get("classKey")), _text(winner.get("specKey")))
        if key in winners_by_spec:
            blockers.append(_blocker("DUPLICATE_CANDIDATE_WINNER", *key))
        winners_by_spec[key] = winner

    gear_descriptor = (
        pair.get("gearRelease")
        if isinstance(pair.get("gearRelease"), dict)
        else {}
    )
    gear_dependencies = (
        gear_descriptor.get("dependencyRevisions")
        if isinstance(gear_descriptor.get("dependencyRevisions"), dict)
        else {}
    )
    candidate_capability_revision = _text(
        gear_dependencies.get("capabilityRevision")
    )
    reference_proof_required = (
        candidate_capability_revision == gear_socket_authority.CAPABILITY_REVISION
    )
    if not candidate_capability_revision:
        blockers.append(_blocker(
            "CANDIDATE_CAPABILITY_REVISION_MISSING",
            detail="Candidate Gear Release capability revision is required.",
        ))
    elif (
        candidate_capability_revision
        not in gear_socket_authority.SUPPORTED_CAPABILITY_REVISIONS
    ):
        blockers.append(_blocker(
            "CANDIDATE_CAPABILITY_REVISION_UNSUPPORTED",
            detail="Candidate Gear Release capability revision is unsupported.",
        ))

    legacy_rows = []
    candidate_rows = [
        pg_gear_read_model_selectors.build_candidate_release_shadow_row(
            winner,
            gear_release_id=gear_id,
        )
        for winner in pair.get("winners") or []
        if isinstance(winner, dict)
    ]
    candidate_rows_by_spec = {
        (_text(row.get("classKey")), _text(row.get("specKey"))): row
        for row in candidate_rows
    }
    community_descriptor = pair.get("communityRelease") if isinstance(pair.get("communityRelease"), dict) else {}
    community_source = community_descriptor.get("source") if isinstance(community_descriptor.get("source"), dict) else {}
    # The first legacy import sealed evidence-sensitive slot hashes. Its immutable
    # content hash remains verified, while live old/new parity uses the corrected
    # user-visible semantic signature that excludes source/evidence identities.
    legacy_sealed_semantic = _text(community_source.get("sourceRevision")) == "legacy-import-r0"
    active_release_pair: dict[str, Any] = {}
    active_release_reader = getattr(store, "get_active_community_release", None)
    if callable(active_release_reader):
        try:
            loaded_active_pair = active_release_reader()
            if isinstance(loaded_active_pair, dict):
                active_release_pair = loaded_active_pair
        except Exception:
            active_release_pair = {}
    active_winners_by_spec = {
        (_text(winner.get("classKey")), _text(winner.get("specKey"))): winner
        for winner in active_release_pair.get("winners") or []
        if isinstance(winner, dict)
    }
    spec_results = []
    formal_active = False
    public_read_count = 0
    allowed_enhancement_migrations: set[tuple[str, str]] = set()
    reference_seen = False
    reference_proof: dict[str, Any] = {
        "status": (
            "not_run"
            if reference_proof_required
            else (
                "not_applicable"
                if candidate_capability_revision
                == gear_socket_authority.LEGACY_CAPABILITY_REVISION
                else "blocked"
            )
        ),
        "capabilityRevision": candidate_capability_revision,
    }
    profile_contexts = profile_context_by_spec if isinstance(profile_context_by_spec, dict) else {}
    for class_key, spec_key in expected:
        spec_started = time.perf_counter()
        key = (class_key, spec_key)
        spec_reference_proof = None
        candidate = winners_by_spec.get(key)
        try:
            public = store.get_websim_gear(
                class_key,
                spec_key,
                compact=True,
                mode="initial",
            )
        except Exception:
            blockers.append(_blocker(
                "TRANSITIONAL_PUBLIC_READ_FAILED",
                class_key,
                spec_key,
                "Transitional public reader is unavailable.",
            ))
            spec_results.append({
                "classKey": class_key,
                "specKey": spec_key,
                "status": "blocked",
                "durationMs": round((time.perf_counter() - spec_started) * 1000, 3),
            })
            continue
        public_read_count += 1
        public_templates = public.get("communityTemplates") if isinstance(public, dict) else []
        public_templates = public_templates if isinstance(public_templates, list) else []
        baselines = public.get("baselineTemplates") if isinstance(public, dict) else []
        baselines = baselines if isinstance(baselines, list) else []
        try:
            resolver_context = store.get_gear_resolver_context(
                gear_resolver_runtime_authority(
                    class_key,
                    spec_key,
                    simc_runtime_revision=simc_runtime_revision,
                )
            )
        except Exception:
            resolver_context = {}
        resolver_context = resolver_context if isinstance(resolver_context, dict) else {}
        formal_active = formal_active or resolver_context.get("formalActiveManifest") is True

        if baselines:
            blockers.append(_blocker("PUBLIC_BASELINE_LEAK", class_key, spec_key, "Transitional public baseline is not empty."))
        if len(public_templates) != 1:
            blockers.append(_blocker("TRANSITIONAL_WINNER_COUNT_INVALID", class_key, spec_key, "Transitional public winner count must equal one."))
        if candidate is None and not allow_degraded_empty:
            blockers.append(_blocker("CANDIDATE_WINNER_MISSING", class_key, spec_key, "Candidate Community Release has no winner."))
        if len(public_templates) != 1:
            spec_results.append({
                "classKey": class_key,
                "specKey": spec_key,
                "status": "blocked",
                "durationMs": round((time.perf_counter() - spec_started) * 1000, 3),
            })
            continue

        public_template = public_templates[0]
        authored = resolver_context.get("authoredAgainst") if isinstance(resolver_context.get("authoredAgainst"), dict) else {}
        active_capability_revision = _text(
            (resolver_context.get("dependencyRevisions") or {}).get(
                "capabilityRevision"
            )
        )
        if active_capability_revision == gear_socket_authority.CAPABILITY_REVISION:
            active_winner = active_winners_by_spec.get(key)
            active_gear = (
                active_release_pair.get("gearRelease")
                if isinstance(active_release_pair.get("gearRelease"), dict)
                else {}
            )
            active_community = (
                active_release_pair.get("communityRelease")
                if isinstance(active_release_pair.get("communityRelease"), dict)
                else {}
            )
            active_intent = (
                active_winner.get("selectionIntent")
                if isinstance(active_winner, dict)
                and isinstance(active_winner.get("selectionIntent"), dict)
                else {}
            )
            active_eligibility = (
                active_intent.get("eligibilityContext")
                if isinstance(active_intent.get("eligibilityContext"), dict)
                else {}
            )
            active_binding_valid = (
                active_release_pair.get("formalActiveManifest") is True
                and _text(active_gear.get("releaseId"))
                == _text(authored.get("gearCatalogRevision"))
                and bool(_text(active_community.get("releaseId")))
                and isinstance(active_winner, dict)
                and _text(active_winner.get("templateId"))
                == _text(public_template.get("id"))
                and _text(active_eligibility.get("classKey")) == class_key
                and _text(active_eligibility.get("specKey")) == spec_key
            )
            if not active_binding_valid:
                blockers.append(_blocker(
                    "TRANSITIONAL_INTERNAL_WINNER_UNAVAILABLE",
                    class_key,
                    spec_key,
                    "Active v2 shadow requires the exact sealed active Community winner Intent.",
                ))
                spec_results.append({
                    "classKey": class_key,
                    "specKey": spec_key,
                    "status": "blocked",
                    "durationMs": round((time.perf_counter() - spec_started) * 1000, 3),
                })
                continue
            legacy_intent = copy.deepcopy(active_intent)
        else:
            legacy_intent = _selection_intent_from_template(
                public_template,
                gear_release_id=_text(authored.get("gearCatalogRevision")),
                season_revision=_text(authored.get("seasonRevision")),
                level=level,
            )
        if candidate is None:
            legacy_rows.append(
                pg_gear_read_model_selectors.build_transitional_release_shadow_row(
                    public_template,
                    legacy_intent,
                    {},
                    gear_release_id=gear_id,
                    baseline_count=len(baselines),
                )
            )
            spec_results.append({
                "classKey": class_key,
                "specKey": spec_key,
                "status": "degraded_empty",
                "transitionalHttpStatus": 200,
                "candidateHttpStatus": 200,
                "profileParity": {"status": "not_run"},
                "durationMs": round((time.perf_counter() - spec_started) * 1000, 3),
            })
            continue
        if _text(public_template.get("id")) != _text(candidate.get("templateId")):
            blockers.append(_blocker("PUBLIC_WINNER_ID_MISMATCH", class_key, spec_key, "Candidate winner identity differs from public."))
        candidate_intent = candidate.get("selectionIntent") if isinstance(candidate.get("selectionIntent"), dict) else {}
        old_status, old_envelope = gear_runtime.resolve_selection_intent(
            legacy_intent,
            store=store,
            simc_runtime_revision=simc_runtime_revision,
            request_id=f"shadow-old-{class_key}-{spec_key}",
        )
        new_status, new_envelope = gear_runtime.resolve_candidate_selection_intent(
            candidate_intent,
            store=store,
            gear_release_id=gear_id,
            simc_runtime_revision=simc_runtime_revision,
            request_id=f"shadow-new-{class_key}-{spec_key}",
        )
        old_snapshot = _resolved_snapshot(old_status, old_envelope)
        new_snapshot = _resolved_snapshot(new_status, new_envelope)
        if old_snapshot is None:
            blockers.append(_blocker("TRANSITIONAL_RESOLVE_FAILED", class_key, spec_key, "Transitional winner did not resolve."))
        if new_snapshot is None:
            blockers.append(_blocker("CANDIDATE_RESOLVE_FAILED", class_key, spec_key, "Candidate winner did not resolve."))
        if old_snapshot is None or new_snapshot is None:
            spec_results.append({
                "classKey": class_key,
                "specKey": spec_key,
                "status": "blocked",
                "transitionalHttpStatus": old_status,
                "candidateHttpStatus": new_status,
                "transitionalProblemCodes": _problem_codes(old_envelope),
                "candidateProblemCodes": _problem_codes(new_envelope),
                "durationMs": round((time.perf_counter() - spec_started) * 1000, 3),
            })
            continue

        live_candidate_semantic = gear_release.semantic_gear_signature(candidate_intent, new_snapshot)
        candidate_shadow_row = candidate_rows_by_spec.get(key)
        if isinstance(candidate_shadow_row, dict):
            candidate_shadow_row["semanticGearSignature"] = live_candidate_semantic
        if (
            not legacy_sealed_semantic
            and live_candidate_semantic != _text(candidate.get("semanticGearSignature"))
        ):
            blockers.append(_blocker("CANDIDATE_SEALED_RESULT_MISMATCH", class_key, spec_key, "Current release reader result differs from the sealed winner."))
        if (
            reference_proof_required
            and _text(candidate.get("templateId")) == _REFERENCE_TEMPLATE_ID
        ):
            reference_seen = True
            spec_reference_proof = _reference_contract_proof(
                candidate,
                candidate_intent,
                new_snapshot,
            )
            spec_reference_proof["capabilityRevision"] = (
                candidate_capability_revision
            )
            spec_reference_proof["gearReleaseId"] = gear_id
            spec_reference_proof["communityReleaseId"] = community_id
            overflow_intent = copy.deepcopy(candidate_intent)
            overflow_slot = ""
            for reference_slot in _REFERENCE_SOCKET_SLOTS:
                selection = (overflow_intent.get("slots") or {}).get(reference_slot)
                constraint = (new_snapshot.get("constraints") or {}).get("slots", {}).get(reference_slot)
                if not isinstance(selection, dict) or not isinstance(constraint, dict):
                    continue
                selected_gems = selection.get("gemOptionIds")
                if (
                    isinstance(selected_gems, list)
                    and selected_gems
                    and len(selected_gems) == _int(constraint.get("socketCount"))
                ):
                    selection["gemOptionIds"] = [*selected_gems, selected_gems[0]]
                    overflow_slot = reference_slot
                    break
            overflow_codes = []
            if overflow_slot:
                overflow_status, overflow_envelope = gear_runtime.resolve_candidate_selection_intent(
                    overflow_intent,
                    store=store,
                    gear_release_id=gear_id,
                    simc_runtime_revision=simc_runtime_revision,
                    request_id=f"shadow-reference-ninth-gem-{class_key}-{spec_key}",
                )
                overflow_codes = _problem_codes(overflow_envelope)
                overflow_blocked = (
                    _resolved_snapshot(overflow_status, overflow_envelope) is None
                    and "GEAR_GEM_SOCKET_CAPACITY_EXCEEDED" in overflow_codes
                )
                spec_reference_proof["ninthGem"] = {
                    "status": "pass" if overflow_blocked else "blocked",
                    "slot": overflow_slot,
                    "problemCodes": overflow_codes,
                }
                if not overflow_blocked:
                    spec_reference_proof["status"] = "blocked"
                    spec_reference_proof["failures"].append("ninth_gem")
            else:
                spec_reference_proof["status"] = "blocked"
                spec_reference_proof["failures"].append("ninth_gem_fixture")
            reference_proof = spec_reference_proof
            if spec_reference_proof["status"] != "pass":
                blockers.append(_blocker(
                    "REFERENCE_ENHANCEMENT_CONTRACT_MISMATCH",
                    class_key,
                    spec_key,
                    "Frozen Mage enhancement counts, capacity vector, or ninth-gem rejection did not match.",
                ))
        profile_result = {"status": "not_run"}
        migration_result = {"status": "not_run"}
        if compare_profiles:
            profile_context = profile_contexts.get(f"{class_key}:{spec_key}")
            profile_context = profile_context if isinstance(profile_context, dict) else {}
            old_profile_status, old_profile = gear_runtime.build_profile_from_selection_intent(
                {"selectionIntent": legacy_intent, "profileContext": profile_context},
                store=store,
                simc_runtime_revision=simc_runtime_revision,
                request_id=f"shadow-old-profile-{class_key}-{spec_key}",
            )
            new_profile_status, new_profile = gear_runtime.build_candidate_profile_from_selection_intent(
                {"selectionIntent": candidate_intent, "profileContext": profile_context},
                store=store,
                gear_release_id=gear_id,
                simc_runtime_revision=simc_runtime_revision,
                request_id=f"shadow-new-profile-{class_key}-{spec_key}",
            )
            old_profile_state = _text(old_profile.get("status")) if isinstance(old_profile, dict) else ""
            new_profile_state = _text(new_profile.get("status")) if isinstance(new_profile, dict) else ""
            old_profile_outcome = _profile_outcome(old_profile_status, old_profile)
            new_profile_outcome = _profile_outcome(new_profile_status, new_profile)
            profile_result = {
                "status": "pass" if old_profile_outcome == new_profile_outcome else "blocked",
                "transitionalHttpStatus": old_profile_status,
                "transitionalStatus": old_profile_state,
                "candidateHttpStatus": new_profile_status,
                "candidateStatus": new_profile_state,
            }
            if profile_result["status"] != "pass":
                blockers.append(_blocker("PROFILE_PARITY_MISMATCH", class_key, spec_key, "Candidate Profile outcome differs from transitional Profile."))
            enhancement_selection_changed = (
                _enhancement_selection_projection(legacy_intent)
                != _enhancement_selection_projection(candidate_intent)
            )
            migration_equivalent = (
                _enhancement_migration_projection(old_snapshot)
                == _enhancement_migration_projection(new_snapshot)
            )
            migration_scope_equal = (
                _non_enhancement_selection_projection(legacy_intent)
                == _non_enhancement_selection_projection(candidate_intent)
            )
            if not enhancement_selection_changed:
                migration_result = {"status": "not_required"}
            elif (
                profile_result["status"] == "pass"
                and migration_equivalent
                and migration_scope_equal
            ):
                migration_result = {"status": "pass"}
                allowed_enhancement_migrations.add(key)
            else:
                migration_result = {"status": "blocked"}
        legacy_rows.append(
            pg_gear_read_model_selectors.build_transitional_release_shadow_row(
                public_template,
                legacy_intent,
                old_snapshot,
                gear_release_id=gear_id,
                baseline_count=len(baselines),
            )
        )
        spec_results.append({
            "classKey": class_key,
            "specKey": spec_key,
            "status": "pass",
            "transitionalHttpStatus": old_status,
            "candidateHttpStatus": new_status,
            "profileParity": profile_result,
            "enhancementMigrationParity": migration_result,
            **({"referenceProof": spec_reference_proof} if spec_reference_proof else {}),
            "durationMs": round((time.perf_counter() - spec_started) * 1000, 3),
        })

    if (
        reference_proof_required
        and _REFERENCE_SPEC in set(expected)
        and not reference_seen
    ):
        blockers.append(_blocker(
            "REFERENCE_TEMPLATE_MISSING",
            *_REFERENCE_SPEC,
            "Frozen observed_profile_mage_frost winner is required for the candidate shadow.",
        ))
    if formal_active is not bool(expect_formal_active):
        blockers.append(_blocker(
            "PUBLIC_FORMAL_MANIFEST_STATE_MISMATCH",
            detail="Public reader formal Manifest state does not match the shadow contract.",
        ))
    report = gear_release.compare_shadow(
        legacy_rows,
        candidate_rows,
        expected_specs=expected,
        gear_release_id=gear_id,
        allowed_semantic_change_specs=allowed_enhancement_migrations,
    )
    blockers.extend(report.get("blockers") or [])
    status = "blocked" if blockers else report.get("status", "blocked")
    spec_durations = sorted(
        float(row.get("durationMs") or 0)
        for row in spec_results
        if isinstance(row, dict)
    )
    p95_index = max(0, ((len(spec_durations) * 95 + 99) // 100) - 1)
    return {
        "schemaRevision": "gear-release-shadow-execution-v1",
        "status": status,
        "gearReleaseId": gear_id,
        "communityReleaseId": community_id,
        "report": report,
        "blockers": blockers,
        "specResults": spec_results,
        "publicReadCount": public_read_count,
        "formalActiveManifest": formal_active,
        "referenceProof": reference_proof,
        "sealedSemanticMode": (
            "legacy_evidence_identity_v1"
            if legacy_sealed_semantic
            else "current"
        ),
        "performance": {
            "totalDurationMs": round((time.perf_counter() - shadow_started) * 1000, 3),
            "specP95Ms": spec_durations[p95_index] if spec_durations else 0,
            "specMaxMs": spec_durations[-1] if spec_durations else 0,
        },
    }


__all__ = ("run_release_shadow",)

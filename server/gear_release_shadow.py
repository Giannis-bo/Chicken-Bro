#!/usr/bin/env python3
"""Internal read-only old/new shadow orchestration for inactive releases."""

from __future__ import annotations

from typing import Any, Iterable

try:
    from . import gear_release, gear_runtime, pg_gear_read_model_selectors
    from .websim_payload import normalize_slot
except ImportError:
    import gear_release
    import gear_runtime
    import pg_gear_read_model_selectors
    from websim_payload import normalize_slot


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


def _profile_outcome(http_status: int, envelope: Any) -> dict[str, Any]:
    """Normalize user-visible canonical Profile output while ignoring release-only metadata."""

    value = envelope if isinstance(envelope, dict) else {}
    data = value.get("data") if isinstance(value.get("data"), dict) else {}
    problems = value.get("problems") if isinstance(value.get("problems"), list) else []
    return {
        "httpStatus": http_status,
        "status": _text(value.get("status")),
        "problemCodes": sorted({
            _text(problem.get("code"))
            for problem in problems
            if isinstance(problem, dict) and _text(problem.get("code"))
        }),
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
) -> dict[str, Any]:
    """Run an internal shadow matrix without changing public routing or state."""

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

    legacy_rows = []
    candidate_rows = [
        pg_gear_read_model_selectors.build_candidate_release_shadow_row(
            winner,
            gear_release_id=gear_id,
        )
        for winner in pair.get("winners") or []
        if isinstance(winner, dict)
    ]
    spec_results = []
    formal_active = False
    public_read_count = 0
    profile_contexts = profile_context_by_spec if isinstance(profile_context_by_spec, dict) else {}
    for class_key, spec_key in expected:
        key = (class_key, spec_key)
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
            })
            continue
        public_read_count += 1
        public_templates = public.get("communityTemplates") if isinstance(public, dict) else []
        public_templates = public_templates if isinstance(public_templates, list) else []
        baselines = public.get("baselineTemplates") if isinstance(public, dict) else []
        baselines = baselines if isinstance(baselines, list) else []
        resolver_context = public.get("resolverContext") if isinstance(public, dict) and isinstance(public.get("resolverContext"), dict) else {}
        formal_active = formal_active or resolver_context.get("formalActiveManifest") is True

        if baselines:
            blockers.append(_blocker("PUBLIC_BASELINE_LEAK", class_key, spec_key, "Transitional public baseline is not empty."))
        if len(public_templates) != 1:
            blockers.append(_blocker("TRANSITIONAL_WINNER_COUNT_INVALID", class_key, spec_key, "Transitional public winner count must equal one."))
        if candidate is None:
            blockers.append(_blocker("CANDIDATE_WINNER_MISSING", class_key, spec_key, "Candidate Community Release has no winner."))
        if len(public_templates) != 1 or candidate is None:
            spec_results.append({
                "classKey": class_key,
                "specKey": spec_key,
                "status": "blocked",
            })
            continue

        public_template = public_templates[0]
        if _text(public_template.get("id")) != _text(candidate.get("templateId")):
            blockers.append(_blocker("PUBLIC_WINNER_ID_MISMATCH", class_key, spec_key, "Candidate winner identity differs from public."))
        authored = resolver_context.get("authoredAgainst") if isinstance(resolver_context.get("authoredAgainst"), dict) else {}
        legacy_intent = _selection_intent_from_template(
            public_template,
            gear_release_id=_text(authored.get("gearCatalogRevision")),
            season_revision=_text(authored.get("seasonRevision")),
            level=level,
        )
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
            })
            continue

        live_candidate_semantic = gear_release.semantic_gear_signature(candidate_intent, new_snapshot)
        if live_candidate_semantic != _text(candidate.get("semanticGearSignature")):
            blockers.append(_blocker("CANDIDATE_SEALED_RESULT_MISMATCH", class_key, spec_key, "Current release reader result differs from the sealed winner."))
        profile_result = {"status": "not_run"}
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
        })

    if formal_active:
        blockers.append(_blocker("PUBLIC_FORMAL_MANIFEST_PREMATURE", detail="Public reader activated a formal Manifest during shadow."))
    report = gear_release.compare_shadow(
        legacy_rows,
        candidate_rows,
        expected_specs=expected,
        gear_release_id=gear_id,
    )
    blockers.extend(report.get("blockers") or [])
    status = "blocked" if blockers else report.get("status", "blocked")
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
    }


__all__ = ("run_release_shadow",)

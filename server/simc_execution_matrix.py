"""Aggregate-only 26/14 specialization matrix for the formal SimC boundary."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Iterable
from urllib.parse import urlencode

from .simc_support_policy import (
    SIMC_SPECIALIZATION_UNSUPPORTED_CODE,
    simc_execution_support,
)


RequestJson = Callable[
    [str, str, dict[str, Any] | None, dict[str, str]],
    tuple[int, dict[str, Any], float],
]
ExecuteProfile = Callable[[str], dict[str, Any]]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _integer(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _failure(code: str, class_key: str, spec_key: str) -> dict[str, str]:
    return {
        "code": _text(code) or "SIMC_EXECUTION_MATRIX_BLOCKED",
        "classKey": _text(class_key),
        "specKey": _text(spec_key),
    }


def _percentile(values: list[float], percentile: int) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    index = max(
        0,
        min(len(ordered) - 1, ((len(ordered) * percentile + 99) // 100) - 1),
    )
    return round(ordered[index], 3)


def _selection_intent_from_snapshot(
    snapshot: dict[str, Any],
    *,
    class_key: str,
    spec_key: str,
) -> dict[str, Any] | None:
    dependency = (
        snapshot.get("dependencyVector")
        if isinstance(snapshot.get("dependencyVector"), dict)
        else {}
    )
    eligibility = (
        snapshot.get("eligibilityContext")
        if isinstance(snapshot.get("eligibilityContext"), dict)
        else {}
    )
    resolved_slots = (
        snapshot.get("resolvedSlots")
        if isinstance(snapshot.get("resolvedSlots"), dict)
        else {}
    )
    if (
        snapshot.get("contractRevision") != "gear-resolved-snapshot-v1"
        or snapshot.get("status") != "verified"
        or _text(eligibility.get("classKey")) != class_key
        or _text(eligibility.get("specKey")) != spec_key
        or _integer(eligibility.get("level")) <= 0
        or not _text(dependency.get("seasonRevision"))
        or not _text(dependency.get("gearCatalogRevision"))
        or not resolved_slots
    ):
        return None
    slots: dict[str, dict[str, Any]] = {}
    for slot, raw in sorted(resolved_slots.items()):
        resolved = raw if isinstance(raw, dict) else {}
        selected = (
            resolved.get("selectedOptions")
            if isinstance(resolved.get("selectedOptions"), dict)
            else {}
        )
        item_id = _text(resolved.get("itemId"))
        variant_key = _text(resolved.get("variantKey"))
        gem_option_ids = selected.get("gemOptionIds")
        if (
            not _text(slot)
            or not item_id
            or not variant_key
            or not isinstance(gem_option_ids, list)
            or any(not _text(value) for value in gem_option_ids)
        ):
            return None
        slots[_text(slot)] = {
            "itemId": item_id,
            "variantKey": variant_key,
            "gemOptionIds": [_text(value) for value in gem_option_ids],
            "enchantOptionId": _text(selected.get("enchantOptionId")),
            "embellishmentOptionId": _text(selected.get("embellishmentOptionId")),
            "craftedOptionId": _text(selected.get("craftedOptionId")),
            "catalystOptionId": _text(selected.get("catalystOptionId")),
        }
    return {
        "schemaRevision": "selection-intent-v1",
        "authoredAgainst": {
            "seasonRevision": _text(dependency.get("seasonRevision")),
            "gearCatalogRevision": _text(dependency.get("gearCatalogRevision")),
        },
        "eligibilityContext": {
            "classKey": class_key,
            "specKey": spec_key,
            "level": _integer(eligibility.get("level")),
        },
        "slots": slots,
    }


def _choose_template(payload: dict[str, Any], class_key: str, spec_key: str) -> dict[str, Any]:
    templates = (
        payload.get("communityTemplates")
        if isinstance(payload.get("communityTemplates"), list)
        else []
    )
    candidates = [
        template
        for template in templates
        if (
            isinstance(template, dict)
            and _text(template.get("id"))
            and _text(template.get("heroKey"))
            and _text(template.get("classKey")) == class_key
            and _text(template.get("specKey")) == spec_key
            and template.get("canApplyGear") is True
        )
    ]
    candidates.sort(key=lambda row: _text(row.get("heroKey")))
    if class_key == "deathknight" and spec_key == "unholy":
        compatible = [
            row
            for row in candidates
            if _text(row.get("heroKey")) != "rider_of_the_apocalypse"
        ]
        if compatible:
            return compatible[0]
    return candidates[0] if candidates else {}


def run_simc_execution_matrix(
    request_json: RequestJson,
    execute_profile: ExecuteProfile,
    *,
    expected_specs: Iterable[tuple[str, str]],
    manifest_revision: str,
    pointer_generation: int,
    gear_release_id: str,
    community_release_id: str,
    simc_runtime_revision: str,
    observed_at: str,
) -> dict[str, Any]:
    expected = sorted({
        (_text(class_key), _text(spec_key))
        for class_key, spec_key in expected_specs
        if _text(class_key) and _text(spec_key)
    })
    failures: list[dict[str, str]] = []
    profile_latencies: list[float] = []
    simc_latencies: list[float] = []
    profile_ready_count = 0
    executed_count = 0
    dps_metric_count = 0
    unsupported_blocked_count = 0

    try:
        options_status, options_payload, _options_ms = request_json(
            "GET",
            "/api/simulator/simc/options",
            None,
            {},
        )
    except Exception:
        options_status, options_payload = 0, {}
    policy = (
        options_payload.get("specializationPolicy")
        if isinstance(options_payload.get("specializationPolicy"), dict)
        else {}
    )
    races = (
        options_payload.get("races")
        if isinstance(options_payload.get("races"), dict)
        else {}
    )
    default_races = (
        races.get("defaultByClass")
        if isinstance(races.get("defaultByClass"), dict)
        else {}
    )
    if (
        options_status != 200
        or options_payload.get("contractRevision") != "simc-options-v1"
        or options_payload.get("status") != "ready"
        or policy.get("contractRevision") != "simc-execution-support-v1"
        or policy.get("status") != "ready"
        or _integer(policy.get("supportedSpecCount")) != 26
        or _integer(policy.get("unsupportedSpecCount")) != 14
    ):
        failures.append(_failure("SIMC_OPTIONS_POLICY_INVALID", "", ""))

    supported_expected = sum(
        1
        for class_key, spec_key in expected
        if simc_execution_support(class_key, spec_key).get("supported")
    )
    unsupported_expected = len(expected) - supported_expected

    for class_key, spec_key in expected:
        spec_failures: list[dict[str, str]] = []
        query = urlencode({
            "class": class_key,
            "spec": spec_key,
            "compact": "1",
            "mode": "initial",
        })
        try:
            browse_status, browse, _browse_ms = request_json(
                "GET",
                f"/api/websim/gear?{query}",
                None,
                {"X-Wow-Platform": "miniprogram"},
            )
        except Exception:
            browse_status, browse = 0, {}
        if (
            browse_status != 200
            or browse.get("formalActiveManifest") is not True
            or _text(browse.get("manifestRevision")) != manifest_revision
            or _integer(browse.get("pointerGeneration")) != pointer_generation
            or _text(browse.get("gearCatalogReleaseId")) != gear_release_id
            or _text(browse.get("communityTemplateReleaseId")) != community_release_id
        ):
            spec_failures.append(_failure("SIMC_BROWSE_IDENTITY_MISMATCH", class_key, spec_key))
        template = _choose_template(browse, class_key, spec_key)
        if not template:
            spec_failures.append(_failure("SIMC_COMMUNITY_TEMPLATE_UNAVAILABLE", class_key, spec_key))
        if spec_failures:
            failures.extend(spec_failures)
            continue

        try:
            import_status, imported_envelope, _import_ms = request_json(
                "POST",
                "/api/websim/gear/community-import",
                {
                    "classKey": class_key,
                    "specKey": spec_key,
                    "templateId": _text(template.get("id")),
                    "expectedManifestRevision": manifest_revision,
                },
                {"Content-Type": "application/json"},
            )
        except Exception:
            import_status, imported_envelope = 0, {}
        imported_data = (
            imported_envelope.get("data")
            if isinstance(imported_envelope.get("data"), dict)
            else {}
        )
        snapshot = (
            imported_data.get("resolvedSnapshot")
            if isinstance(imported_data.get("resolvedSnapshot"), dict)
            else {}
        )
        intent = _selection_intent_from_snapshot(
            snapshot,
            class_key=class_key,
            spec_key=spec_key,
        )
        if (
            import_status != 200
            or imported_envelope.get("status") != "verified"
            or imported_data.get("status") != "verified"
            or intent is None
        ):
            failures.append(_failure("SIMC_COMMUNITY_IMPORT_INVALID", class_key, spec_key))
            continue

        hero_key = _text(template.get("heroKey"))
        talent_query = urlencode({
            "class": class_key,
            "spec": spec_key,
            "hero": hero_key,
        })
        try:
            talent_status, talent_payload, _talent_ms = request_json(
                "GET",
                f"/api/websim/talents/import?{talent_query}",
                None,
                {},
            )
        except Exception:
            talent_status, talent_payload = 0, {}
        talent_import = _text(talent_payload.get("importCode"))
        if (
            talent_status != 200
            or talent_payload.get("status") not in {"verified", "ready"}
            or not talent_import
        ):
            failures.append(_failure("SIMC_TALENT_IMPORT_INVALID", class_key, spec_key))
            continue

        profile_context = {
            "classKey": class_key,
            "specKey": spec_key,
            "race": _text(default_races.get(class_key)),
            "scenarioKey": "single",
            "heroKey": hero_key,
            "talents": talent_import,
        }
        support = simc_execution_support(class_key, spec_key)
        if support.get("supported"):
            try:
                profile_status, profile_envelope, profile_ms = request_json(
                    "POST",
                    "/api/websim/profile",
                    {
                        "selectionIntent": intent,
                        "profileContext": profile_context,
                    },
                    {"Content-Type": "application/json"},
                )
            except Exception:
                profile_status, profile_envelope, profile_ms = 0, {}, 0.0
            profile_latencies.append(float(profile_ms or 0))
            release_context = (
                profile_envelope.get("releaseContext")
                if isinstance(profile_envelope.get("releaseContext"), dict)
                else {}
            )
            profile_data = (
                profile_envelope.get("data")
                if isinstance(profile_envelope.get("data"), dict)
                else {}
            )
            readiness = (
                profile_data.get("profileReadiness")
                if isinstance(profile_data.get("profileReadiness"), dict)
                else {}
            )
            raw_profile = profile_data.get("profile")
            profile = raw_profile if isinstance(raw_profile, str) else ""
            if (
                profile_status != 200
                or profile_envelope.get("status") != "resolved"
                or profile_data.get("status") != "resolved"
                or readiness.get("status") != "verified"
                or readiness.get("simcReady") is not True
                or _text(release_context.get("manifestRevision")) != manifest_revision
                or _integer(release_context.get("pointerGeneration")) != pointer_generation
                or _text(release_context.get("gearCatalogRevision")) != gear_release_id
                or _text(release_context.get("simcRuntimeRevision")) != simc_runtime_revision
                or not profile.strip()
            ):
                failures.append(_failure("SIMC_PROFILE_NOT_READY", class_key, spec_key))
                continue
            profile_ready_count += 1
            try:
                executed = execute_profile(profile)
            except Exception:
                executed = {}
            simc_latencies.append(float(executed.get("durationMs") or 0))
            if executed.get("ran") is not True or executed.get("timedOut") is True:
                failures.append(_failure("SIMC_EXECUTION_FAILED", class_key, spec_key))
                continue
            executed_count += 1
            if executed.get("hasDps") is not True:
                failures.append(_failure("SIMC_DPS_METRIC_MISSING", class_key, spec_key))
                continue
            dps_metric_count += 1
            continue

        try:
            block_status, block_payload, _block_ms = request_json(
                "POST",
                "/api/simulator/analyze",
                {
                    "mode": "simcraft_template",
                    "confirmOnly": True,
                    "saveTask": False,
                    "selectionIntent": intent,
                    "profileContext": profile_context,
                },
                {"Content-Type": "application/json"},
            )
        except Exception:
            block_status, block_payload = 0, {}
        agent = block_payload.get("agent") if isinstance(block_payload.get("agent"), dict) else {}
        validation = (
            agent.get("validation")
            if isinstance(agent.get("validation"), dict)
            else {}
        )
        problems = (
            validation.get("problems")
            if isinstance(validation.get("problems"), list)
            else []
        )
        problem_codes = {
            _text(problem.get("code"))
            for problem in problems
            if isinstance(problem, dict)
        }
        simulation = (
            block_payload.get("simulation")
            if isinstance(block_payload.get("simulation"), dict)
            else {}
        )
        if (
            block_status != 200
            or validation.get("passed") is not False
            or SIMC_SPECIALIZATION_UNSUPPORTED_CODE not in problem_codes
            or simulation.get("ran") is not False
            or _text(block_payload.get("taskId"))
        ):
            failures.append(_failure("SIMC_UNSUPPORTED_BLOCK_INVALID", class_key, spec_key))
            continue
        unsupported_blocked_count += 1

    failure_codes: dict[str, int] = {}
    for failure in failures:
        code = failure["code"]
        failure_codes[code] = failure_codes.get(code, 0) + 1
    status = (
        "pass"
        if (
            not failures
            and profile_ready_count == supported_expected
            and executed_count == supported_expected
            and dps_metric_count == supported_expected
            and unsupported_blocked_count == unsupported_expected
        )
        else "blocked"
    )
    stable = {
        "schemaRevision": "simc-execution-matrix-v1",
        "status": status,
        "manifestRevision": _text(manifest_revision),
        "pointerGeneration": _integer(pointer_generation),
        "gearReleaseId": _text(gear_release_id),
        "communityReleaseId": _text(community_release_id),
        "simcRuntimeRevision": _text(simc_runtime_revision),
        "totalSpecCount": len(expected),
        "supported": {
            "expectedSpecCount": supported_expected,
            "profileReadySpecCount": profile_ready_count,
            "executedSpecCount": executed_count,
            "dpsMetricSpecCount": dps_metric_count,
        },
        "unsupported": {
            "expectedSpecCount": unsupported_expected,
            "deterministicallyBlockedSpecCount": unsupported_blocked_count,
        },
        "failureCount": len(failures),
        "failureCodes": {
            code: failure_codes[code]
            for code in sorted(failure_codes)
        },
        "failureSamples": failures[:20],
    }
    report_hash = hashlib.sha256(
        json.dumps(
            stable,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        **stable,
        "reportId": f"simc-execution-matrix:sha256:{report_hash}",
        "observedAt": _text(observed_at),
        "performance": {
            "profiles": {
                "sampleCount": len(profile_latencies),
                "p50Ms": _percentile(profile_latencies, 50),
                "p95Ms": _percentile(profile_latencies, 95),
                "maxMs": round(max(profile_latencies), 3) if profile_latencies else 0,
            },
            "simc": {
                "sampleCount": len(simc_latencies),
                "p50Ms": _percentile(simc_latencies, 50),
                "p95Ms": _percentile(simc_latencies, 95),
                "maxMs": round(max(simc_latencies), 3) if simc_latencies else 0,
            },
        },
    }


__all__ = ("run_simc_execution_matrix",)

"""Aggregate-only HTTP acceptance matrix for one active Gear/Community pair."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlencode


RequestJson = Callable[
    [str, str, dict[str, Any] | None, dict[str, str]],
    tuple[int, dict[str, Any], float],
]


def validate_http_matrix_report(
    report: Any,
    *,
    manifest_revision: str,
    pointer_generation: int,
    gear_release_id: str,
    community_release_id: str,
    expected_spec_count: int,
    candidate_preview: bool = False,
) -> list[str]:
    """Validate one aggregate matrix against an exact runtime binding."""

    if not isinstance(report, Mapping):
        return ["HTTP_MATRIX_REPORT_MALFORMED"]
    browse = report.get("browse")
    imports = report.get("imports")
    if not isinstance(browse, Mapping) or not isinstance(imports, Mapping):
        return ["HTTP_MATRIX_REPORT_MALFORMED"]
    stable = {
        "schemaRevision": _text(report.get("schemaRevision")),
        "status": _text(report.get("status")),
        "manifestRevision": _text(report.get("manifestRevision")),
        "pointerGeneration": _integer(report.get("pointerGeneration")),
        "gearReleaseId": _text(report.get("gearReleaseId")),
        "communityReleaseId": _text(report.get("communityReleaseId")),
        "browse": dict(browse),
        "imports": dict(imports),
        "failureCount": _integer(report.get("failureCount")),
        "failureCodes": dict(report.get("failureCodes") or {}),
        "failureSamples": list(report.get("failureSamples") or []),
    }
    if stable["schemaRevision"] == "gear-release-http-matrix-v2":
        stable["bindingMode"] = _text(report.get("bindingMode"))
    digest = hashlib.sha256(
        json.dumps(
            stable,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    issues = []
    expected_schema = (
        "gear-release-http-matrix-v2"
        if candidate_preview
        else "gear-release-http-matrix-v1"
    )
    if (
        stable["schemaRevision"] != expected_schema
        or _text(report.get("reportId"))
        != f"gear-release-http-matrix:sha256:{digest}"
    ):
        issues.append("HTTP_MATRIX_IDENTITY_INVALID")
    expected_hero_slots = int(expected_spec_count) * 2
    if (
        stable["manifestRevision"] != _text(manifest_revision)
        or stable["pointerGeneration"] != int(pointer_generation)
        or stable["gearReleaseId"] != _text(gear_release_id)
        or stable["communityReleaseId"] != _text(community_release_id)
        or (
            candidate_preview
            and stable.get("bindingMode") != "candidate_preview"
        )
    ):
        issues.append("HTTP_MATRIX_BINDING_MISMATCH")
    if (
        stable["status"] != "pass"
        or stable["failureCount"] != 0
        or stable["failureCodes"]
        or stable["failureSamples"]
        or _integer(browse.get("expectedSpecCount")) != int(expected_spec_count)
        or _integer(browse.get("passingSpecCount")) != int(expected_spec_count)
        or _integer(imports.get("expectedHeroSlotCount")) != expected_hero_slots
        or _integer(imports.get("observedHeroSlotCount")) != expected_hero_slots
        or _integer(imports.get("passingHeroSlotCount")) != expected_hero_slots
    ):
        issues.append("HTTP_MATRIX_COVERAGE_INCOMPLETE")
    return sorted(set(issues))


def _text(value: Any) -> str:
    return str(value or "").strip()


def _integer(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _percentile(values: list[float], percentile: int) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    index = max(
        0,
        min(
            len(ordered) - 1,
            ((len(ordered) * percentile + 99) // 100) - 1,
        ),
    )
    return round(ordered[index], 3)


def _failure(
    code: str,
    class_key: str,
    spec_key: str,
    *,
    hero_key: str = "",
) -> dict[str, str]:
    return {
        "code": _text(code) or "HTTP_MATRIX_BLOCKED",
        "classKey": _text(class_key),
        "specKey": _text(spec_key),
        **({"heroKey": _text(hero_key)} if _text(hero_key) else {}),
    }


def _browse_failures(
    payload: dict[str, Any],
    *,
    class_key: str,
    spec_key: str,
    manifest_revision: str,
    pointer_generation: int,
    gear_release_id: str,
    community_release_id: str,
    candidate_preview: bool,
) -> tuple[list[dict[str, str]], dict[str, dict[str, Any]]]:
    failures: list[dict[str, str]] = []

    def require(condition: bool, code: str) -> None:
        if not condition:
            failures.append(_failure(code, class_key, spec_key))

    if candidate_preview:
        require(
            payload.get("formalActiveManifest") is False,
            "FORMAL_ACTIVE_MANIFEST_LEAK",
        )
        require(
            payload.get("candidatePreview") is True,
            "CANDIDATE_PREVIEW_REQUIRED",
        )
    else:
        require(
            payload.get("formalActiveManifest") is True,
            "FORMAL_ACTIVE_MANIFEST_REQUIRED",
        )
        require(
            payload.get("candidatePreview") is not True,
            "CANDIDATE_PREVIEW_LEAK",
        )
    require(
        _text(payload.get("manifestRevision")) == manifest_revision,
        "MANIFEST_REVISION_MISMATCH",
    )
    require(
        _integer(payload.get("pointerGeneration"))
        == pointer_generation,
        "POINTER_GENERATION_MISMATCH",
    )
    require(
        _text(payload.get("gearCatalogReleaseId"))
        == gear_release_id,
        "GEAR_RELEASE_MISMATCH",
    )
    require(
        _text(payload.get("communityTemplateReleaseId"))
        == community_release_id,
        "COMMUNITY_RELEASE_MISMATCH",
    )
    baselines = (
        payload.get("baselineTemplates")
        if isinstance(payload.get("baselineTemplates"), list)
        else []
    )
    require(not baselines, "PUBLIC_BASELINE_LEAK")

    templates = (
        payload.get("communityTemplates")
        if isinstance(payload.get("communityTemplates"), list)
        else []
    )
    by_hero: dict[str, dict[str, Any]] = {}
    for template in templates:
        if not isinstance(template, dict):
            continue
        hero_key = _text(template.get("heroKey"))
        template_id = _text(template.get("id"))
        if (
            not hero_key
            or hero_key in by_hero
            or not template_id
            or _text(template.get("classKey")) != class_key
            or _text(template.get("specKey")) != spec_key
            or _text(template.get("sourceKey"))
            != "raiderio_observed_profile"
            or template.get("canApplyGear") is not True
        ):
            failures.append(_failure(
                "PUBLIC_HERO_TEMPLATE_INVALID",
                class_key,
                spec_key,
                hero_key=hero_key,
            ))
            continue
        by_hero[hero_key] = template
    require(
        len(by_hero) == 2 and len(templates) == 2,
        "PUBLIC_HERO_TEMPLATE_COUNT_INVALID",
    )
    return failures, by_hero


def _import_failures(
    http_status: int,
    envelope: dict[str, Any],
    *,
    class_key: str,
    spec_key: str,
    hero_key: str,
    manifest_revision: str,
    pointer_generation: int,
) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    problems = (
        envelope.get("problems")
        if isinstance(envelope.get("problems"), list)
        else []
    )
    problem_codes = [
        _text(problem.get("code"))
        for problem in problems
        if isinstance(problem, dict) and _text(problem.get("code"))
    ]
    for problem_code in problem_codes:
        failures.append(_failure(
            problem_code,
            class_key,
            spec_key,
            hero_key=hero_key,
        ))

    data = (
        envelope.get("data")
        if isinstance(envelope.get("data"), dict)
        else {}
    )
    manifest = (
        data.get("manifest")
        if isinstance(data.get("manifest"), dict)
        else {}
    )
    imported = (
        data.get("importedGearBySlot")
        if isinstance(data.get("importedGearBySlot"), dict)
        else {}
    )
    snapshot = (
        data.get("resolvedSnapshot")
        if isinstance(data.get("resolvedSnapshot"), dict)
        else {}
    )
    resolved_slots = (
        snapshot.get("resolvedSlots")
        if isinstance(snapshot.get("resolvedSlots"), dict)
        else {}
    )
    readiness = (
        snapshot.get("profileReadiness")
        if isinstance(snapshot.get("profileReadiness"), dict)
        else {}
    )
    snapshot_problems = (
        snapshot.get("problems")
        if isinstance(snapshot.get("problems"), list)
        else []
    )
    checks = (
        (http_status == 200, "COMMUNITY_IMPORT_HTTP_FAILED"),
        (
            _text(envelope.get("status")) == "verified",
            "COMMUNITY_IMPORT_NOT_VERIFIED",
        ),
        (
            _text(data.get("status")) == "verified",
            "COMMUNITY_IMPORT_DATA_NOT_VERIFIED",
        ),
        (
            _text(data.get("contractRevision"))
            == "websim-community-template-import-v2",
            "COMMUNITY_IMPORT_CONTRACT_MISMATCH",
        ),
        (
            _text(manifest.get("manifestRevision"))
            == manifest_revision,
            "COMMUNITY_IMPORT_MANIFEST_MISMATCH",
        ),
        (
            _integer(manifest.get("pointerGeneration"))
            == pointer_generation,
            "COMMUNITY_IMPORT_GENERATION_MISMATCH",
        ),
        (bool(imported), "COMMUNITY_IMPORT_GEAR_EMPTY"),
        (
            _text(snapshot.get("status")) == "verified",
            "COMMUNITY_IMPORT_SNAPSHOT_BLOCKED",
        ),
        (
            bool(resolved_slots)
            and set(resolved_slots) == set(imported),
            "COMMUNITY_IMPORT_SLOT_MISMATCH",
        ),
        (
            _text(readiness.get("status")) == "verified"
            and readiness.get("simcReady") is True,
            "COMMUNITY_IMPORT_PROFILE_NOT_READY",
        ),
        (
            not snapshot_problems,
            "COMMUNITY_IMPORT_SNAPSHOT_PROBLEMS",
        ),
    )
    existing_codes = {failure["code"] for failure in failures}
    for condition, code in checks:
        if not condition and code not in existing_codes:
            failures.append(_failure(
                code,
                class_key,
                spec_key,
                hero_key=hero_key,
            ))
    return failures


def run_http_matrix(
    request_json: RequestJson,
    *,
    expected_specs: Iterable[tuple[str, str]],
    manifest_revision: str,
    pointer_generation: int,
    gear_release_id: str,
    community_release_id: str,
    observed_at: str,
    candidate_preview: bool = False,
) -> dict[str, Any]:
    expected = sorted({
        (_text(class_key), _text(spec_key))
        for class_key, spec_key in expected_specs
        if _text(class_key) and _text(spec_key)
    })
    failures: list[dict[str, str]] = []
    browse_latencies: list[float] = []
    import_latencies: list[float] = []
    browse_pass_count = 0
    import_pass_count = 0
    observed_hero_slot_count = 0

    for class_key, spec_key in expected:
        query = urlencode({
            "class": class_key,
            "spec": spec_key,
            "compact": "1",
            "mode": "initial",
        })
        try:
            status, payload, duration_ms = request_json(
                "GET",
                f"/api/websim/gear?{query}",
                None,
                {"X-Wow-Platform": "miniprogram"},
            )
        except Exception:
            status, payload, duration_ms = 0, {}, 0.0
        browse_latencies.append(float(duration_ms or 0))
        spec_failures = []
        if status != 200:
            spec_failures.append(_failure(
                "BROWSE_HTTP_FAILED",
                class_key,
                spec_key,
            ))
        topology_failures, templates_by_hero = _browse_failures(
            payload if isinstance(payload, dict) else {},
            class_key=class_key,
            spec_key=spec_key,
            manifest_revision=manifest_revision,
            pointer_generation=pointer_generation,
            gear_release_id=gear_release_id,
            community_release_id=community_release_id,
            candidate_preview=candidate_preview,
        )
        spec_failures.extend(topology_failures)
        failures.extend(spec_failures)
        if not spec_failures:
            browse_pass_count += 1
        observed_hero_slot_count += len(templates_by_hero)

        for hero_key, template in sorted(templates_by_hero.items()):
            try:
                import_status, envelope, duration_ms = request_json(
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
                import_status, envelope, duration_ms = 0, {}, 0.0
            import_latencies.append(float(duration_ms or 0))
            hero_failures = _import_failures(
                import_status,
                envelope if isinstance(envelope, dict) else {},
                class_key=class_key,
                spec_key=spec_key,
                hero_key=hero_key,
                manifest_revision=manifest_revision,
                pointer_generation=pointer_generation,
            )
            failures.extend(hero_failures)
            if not hero_failures:
                import_pass_count += 1

    failure_codes: dict[str, int] = {}
    for failure in failures:
        code = failure["code"]
        failure_codes[code] = failure_codes.get(code, 0) + 1
    expected_hero_slots = len(expected) * 2
    status = (
        "pass"
        if (
            not failures
            and browse_pass_count == len(expected)
            and observed_hero_slot_count == expected_hero_slots
            and import_pass_count == expected_hero_slots
        )
        else "blocked"
    )
    identity = {
        "manifestRevision": _text(manifest_revision),
        "pointerGeneration": _integer(pointer_generation),
        "gearReleaseId": _text(gear_release_id),
        "communityReleaseId": _text(community_release_id),
    }
    stable = {
        "schemaRevision": (
            "gear-release-http-matrix-v2"
            if candidate_preview
            else "gear-release-http-matrix-v1"
        ),
        "status": status,
        **identity,
        "browse": {
            "expectedSpecCount": len(expected),
            "passingSpecCount": browse_pass_count,
        },
        "imports": {
            "expectedHeroSlotCount": expected_hero_slots,
            "observedHeroSlotCount": observed_hero_slot_count,
            "passingHeroSlotCount": import_pass_count,
        },
        "failureCount": len(failures),
        "failureCodes": {
            code: failure_codes[code]
            for code in sorted(failure_codes)
        },
        "failureSamples": failures[:20],
    }
    if candidate_preview:
        stable["bindingMode"] = "candidate_preview"
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
        "reportId": f"gear-release-http-matrix:sha256:{report_hash}",
        "observedAt": _text(observed_at),
        "performance": {
            "browse": {
                "sampleCount": len(browse_latencies),
                "p50Ms": _percentile(browse_latencies, 50),
                "p95Ms": _percentile(browse_latencies, 95),
                "maxMs": (
                    round(max(browse_latencies), 3)
                    if browse_latencies
                    else 0
                ),
            },
            "imports": {
                "sampleCount": len(import_latencies),
                "p50Ms": _percentile(import_latencies, 50),
                "p95Ms": _percentile(import_latencies, 95),
                "maxMs": (
                    round(max(import_latencies), 3)
                    if import_latencies
                    else 0
                ),
            },
        },
    }


__all__ = ("run_http_matrix",)

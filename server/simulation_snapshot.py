#!/usr/bin/env python3
"""Pure immutable SimulationSnapshot and canonical SimC compiler."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping

try:
    from .gear_contracts import CANONICAL_GEAR_SLOTS
    from .gear_resolved_loadout import (
        RESOLVED_LOADOUT_KEY_PATTERN,
        RESOLVED_LOADOUT_V2_KEY_PATTERN,
        SIMC_OPTION_ORDER,
        verify_resolved_loadout,
        verify_resolved_loadout_v2,
    )
    from .simc_support_policy import simc_execution_support
except ImportError:
    from gear_contracts import CANONICAL_GEAR_SLOTS
    from gear_resolved_loadout import (
        RESOLVED_LOADOUT_KEY_PATTERN,
        RESOLVED_LOADOUT_V2_KEY_PATTERN,
        SIMC_OPTION_ORDER,
        verify_resolved_loadout,
        verify_resolved_loadout_v2,
    )
    from simc_support_policy import simc_execution_support


SIMULATION_SNAPSHOT_SCHEMA_REVISION = "simulation-snapshot-v1"
SIMULATION_SNAPSHOT_KEY_PATTERN = re.compile(
    r"^simulation-snapshot:sha256:[0-9a-f]{64}$"
)
TALENT_PROFILE_KEY_PATTERN = re.compile(
    r"^talent-profile:sha256:[0-9a-f]{64}$"
)
SIMULATION_SNAPSHOT_V2_SCHEMA_REVISION = "simulation-snapshot-v2"
SIMULATION_SNAPSHOT_V2_KEY_PATTERN = re.compile(
    r"^simulation-snapshot-v2:sha256:[0-9a-f]{64}$"
)

_CHARACTER_KEYS = {
    "classKey",
    "specKey",
    "name",
    "race",
    "level",
    "role",
    "position",
}
_SCENARIO_KEYS = {
    "scenarioKey",
    "fightStyle",
    "desiredTargets",
    "maxTime",
    "iterations",
    "varyCombatLength",
    "calculateScaleFactors",
}
_TALENT_LINE_PATTERN = re.compile(
    r"^(talents|hero_talents|class_talents|spec_talents)=[A-Za-z0-9_:/+.-]{1,8192}$"
)
_OPTION_LINE_PATTERN = re.compile(r"^[A-Za-z0-9_.]+=[A-Za-z0-9_:/+.-]+$")


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


def _hash(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _problem(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _blocked(
    status: str,
    problems: Iterable[Mapping[str, Any]],
    support: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = sorted(
        [_canonical(problem) for problem in problems],
        key=lambda problem: json.dumps(
            problem, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ),
    )
    return {
        "schemaRevision": SIMULATION_SNAPSHOT_SCHEMA_REVISION,
        "status": status,
        "executionSupport": _canonical(support or {}),
        "problemCodes": sorted(
            {_text(problem.get("code")) for problem in normalized if problem.get("code")}
        ),
        "problems": normalized,
    }


def _blocked_v2(
    status: str,
    problems: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    normalized = sorted(
        [_canonical(problem) for problem in problems],
        key=lambda problem: json.dumps(problem, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )
    return {
        "schemaRevision": SIMULATION_SNAPSHOT_V2_SCHEMA_REVISION,
        "status": status,
        "problemCodes": sorted({_text(problem.get("code")) for problem in normalized if problem.get("code")}),
        "problems": normalized,
    }


def _normalized_lines(values: Any, pattern: re.Pattern[str]) -> list[str] | None:
    if not isinstance(values, (list, tuple)):
        return None
    result: list[str] = []
    for raw in values:
        line = _text(raw)
        if (
            not line
            or "\n" in line
            or "\r" in line
            or not pattern.fullmatch(line)
        ):
            return None
        result.append(line)
    return result


def talent_profile_key(talent_lines: Any) -> str:
    lines = _normalized_lines(talent_lines, _TALENT_LINE_PATTERN)
    if not lines:
        return ""
    return _hash("talent-profile:sha256:", {"talentLines": lines})


def _slug(value: Any, fallback: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", _text(value).lower()).strip("_")
    return normalized[:80] or fallback


def _valid_character_context(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping) or set(value).difference(_CHARACTER_KEYS):
        return None
    source = dict(value)
    class_key = _slug(source.get("classKey"), "")
    spec_key = _slug(source.get("specKey"), "")
    race = _slug(source.get("race"), "")
    role = _slug(source.get("role"), "")
    position = _slug(source.get("position"), "")
    try:
        level = int(source.get("level") or 0)
    except (TypeError, ValueError, OverflowError):
        level = 0
    if (
        not class_key
        or not spec_key
        or not race
        or role not in {"attack", "spell", "heal", "tank"}
        or position not in {"back", "front", "ranged_back"}
        or level <= 0
    ):
        return None
    return {
        "classKey": class_key,
        "specKey": spec_key,
        "name": _slug(source.get("name"), "test"),
        "race": race,
        "level": level,
        "role": role,
        "position": position,
    }


def _valid_scenario_options(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping) or set(value).difference(_SCENARIO_KEYS):
        return None
    source = dict(value)
    try:
        targets = int(source.get("desiredTargets") or 0)
        max_time = int(source.get("maxTime") or 0)
        iterations = int(source.get("iterations") or 0)
        scale_factors = int(source.get("calculateScaleFactors") or 0)
        vary = str(float(source.get("varyCombatLength")))
    except (TypeError, ValueError, OverflowError):
        return None
    if (
        not _text(source.get("scenarioKey"))
        or not re.fullmatch(r"[A-Za-z0-9_]{1,64}", _text(source.get("fightStyle")))
        or targets <= 0
        or max_time <= 0
        or iterations <= 0
        or scale_factors not in {0, 1}
    ):
        return None
    return {
        "scenarioKey": _text(source.get("scenarioKey")),
        "fightStyle": _text(source.get("fightStyle")),
        "desiredTargets": targets,
        "maxTime": max_time,
        "iterations": iterations,
        "varyCombatLength": vary,
        "calculateScaleFactors": scale_factors,
    }


def _gear_line(item: Mapping[str, Any]) -> str | None:
    slot = _text(item.get("slot"))
    item_id = _text(item.get("itemId"))
    options = item.get("simcOptions")
    if not slot or not item_id or not isinstance(options, Mapping):
        return None
    if _text(options.get("id")) != item_id:
        return None
    parts = [f"{slot}=item_{item_id}"]
    for field in SIMC_OPTION_ORDER:
        value = _text(options.get(field))
        if value:
            parts.append(f"{field}={value}")
    return ",".join(parts)


def compile_canonical_simc_input(
    resolved_loadout: Mapping[str, Any],
    *,
    talent_lines: Any,
    character_context: Any,
    scenario_options: Any,
    preparation_lines: Any,
) -> tuple[str, list[dict[str, str]], dict[str, Any]]:
    """Return canonical LF bytes as text, problems and normalized compiler input."""

    problems: list[dict[str, str]] = []
    character = _valid_character_context(character_context)
    scenario = _valid_scenario_options(scenario_options)
    talents = _normalized_lines(talent_lines, _TALENT_LINE_PATTERN)
    preparations = _normalized_lines(preparation_lines, _OPTION_LINE_PATTERN)
    if character is None:
        problems.append(
            _problem(
                "SIMULATION_CHARACTER_CONTEXT_INVALID",
                "characterContext",
                "Canonical character context is invalid.",
            )
        )
    if scenario is None:
        problems.append(
            _problem(
                "SIMULATION_SCENARIO_OPTIONS_INVALID",
                "scenarioOptions",
                "Canonical scenario options are invalid.",
            )
        )
    if not talents:
        problems.append(
            _problem(
                "SIMULATION_TALENT_PROFILE_INVALID",
                "talentLines",
                "At least one canonical talent line is required.",
            )
        )
    if preparations is None:
        problems.append(
            _problem(
                "SIMULATION_PREPARATION_INVALID",
                "preparationLines",
                "Preparation lines must be bounded server-owned SimC options.",
            )
        )
    gear_items = (
        resolved_loadout.get("serializerInput", {}).get("gearItems")
        if isinstance(resolved_loadout.get("serializerInput"), Mapping)
        else None
    )
    gear_lines: list[str] = []
    if not isinstance(gear_items, list) or not gear_items:
        problems.append(
            _problem(
                "SIMULATION_GEAR_SERIALIZER_INPUT_INVALID",
                "resolvedLoadout.serializerInput",
                "Ready loadout has no canonical gear serializer input.",
            )
        )
    else:
        for index, item in enumerate(gear_items):
            line = _gear_line(item) if isinstance(item, Mapping) else None
            if not line:
                problems.append(
                    _problem(
                        "SIMULATION_GEAR_SERIALIZER_INPUT_INVALID",
                        f"resolvedLoadout.serializerInput.gearItems[{index}]",
                        "Canonical gear item serializer input is invalid.",
                    )
                )
            else:
                gear_lines.append(line)
    if problems or character is None or scenario is None or not talents:
        return "", problems, {}

    lines = [
        f'{character["classKey"]}="{character["name"]}"',
        f'spec={character["specKey"]}',
        f'level={character["level"]}',
        f'race={character["race"]}',
        f'role={character["role"]}',
        f'position={character["position"]}',
        *talents,
        *gear_lines,
        *(preparations or []),
        f'iterations={scenario["iterations"]}',
        f'fight_style={scenario["fightStyle"]}',
        f'desired_targets={scenario["desiredTargets"]}',
        f'max_time={scenario["maxTime"]}',
        f'vary_combat_length={scenario["varyCombatLength"]}',
        f'calculate_scale_factors={scenario["calculateScaleFactors"]}',
    ]
    canonical_input = "\n".join(line.rstrip() for line in lines) + "\n"
    return canonical_input, [], {
        "characterContext": character,
        "scenarioOptions": scenario,
        "talentLines": talents,
        "preparationLines": preparations or [],
    }


def build_simulation_snapshot(
    *,
    resolved_loadout: Any,
    talent_profile_key: str,
    talent_lines: Any,
    character_context: Any,
    scenario_options: Any,
    preparation_lines: Any,
    compiler_revision: str,
    simc_runtime_revision: str,
) -> dict[str, Any]:
    """Build one immutable canonical SimC execution snapshot."""

    loadout = dict(resolved_loadout) if isinstance(resolved_loadout, Mapping) else {}
    eligibility = (
        dict(loadout.get("eligibilityContext"))
        if isinstance(loadout.get("eligibilityContext"), Mapping)
        else {}
    )
    support = simc_execution_support(
        eligibility.get("classKey"),
        eligibility.get("specKey"),
    )
    if support.get("status") == "blocked":
        status = "unsupported" if support.get("role") != "unknown" else "blocked"
        return _blocked(
            status,
            [
                _problem(
                    _text(support.get("code")),
                    "resolvedLoadout.eligibilityContext.specKey",
                    _text(support.get("message")),
                )
            ],
            support,
        )

    problems: list[dict[str, str]] = []
    if (
        loadout.get("status") != "ready"
        or not RESOLVED_LOADOUT_KEY_PATTERN.fullmatch(
            _text(loadout.get("resolvedLoadoutKey"))
        )
        or verify_resolved_loadout(loadout)
    ):
        problems.append(
            _problem(
                "SIMULATION_LOADOUT_NOT_READY",
                "resolvedLoadout",
                "Only one verified ready ResolvedLoadout can be snapshotted.",
            )
        )
    provided_talent_key = _text(talent_profile_key)
    expected_talent_key = talent_profile_key_for_lines(talent_lines)
    if (
        not TALENT_PROFILE_KEY_PATTERN.fullmatch(provided_talent_key)
        or provided_talent_key != expected_talent_key
    ):
        problems.append(
            _problem(
                "SIMULATION_TALENT_PROFILE_KEY_MISMATCH",
                "talentProfileKey",
                "Talent profile key must content-address the canonical talent lines.",
            )
        )
    compiler_revision = _text(compiler_revision)
    simc_runtime_revision = _text(simc_runtime_revision)
    if not compiler_revision:
        problems.append(
            _problem(
                "SIMULATION_COMPILER_REVISION_MISSING",
                "compilerRevision",
                "Compiler revision is required.",
            )
        )
    if not simc_runtime_revision:
        problems.append(
            _problem(
                "SIMULATION_RUNTIME_REVISION_MISSING",
                "simcRuntimeRevision",
                "SimC runtime revision is required.",
            )
        )

    canonical_input, compiler_problems, compiler_input = (
        compile_canonical_simc_input(
            loadout,
            talent_lines=talent_lines,
            character_context=character_context,
            scenario_options=scenario_options,
            preparation_lines=preparation_lines,
        )
    )
    problems.extend(compiler_problems)
    normalized_character = compiler_input.get("characterContext", {})
    if normalized_character and (
        normalized_character.get("classKey") != eligibility.get("classKey")
        or normalized_character.get("specKey") != eligibility.get("specKey")
    ):
        problems.append(
            _problem(
                "SIMULATION_CHARACTER_LOADOUT_MISMATCH",
                "characterContext",
                "Character class/spec must match the resolved loadout.",
            )
        )
    if problems:
        return _blocked("blocked", problems, support)

    identity_character = {
        **compiler_input["characterContext"],
        "talentLinesHash": _hash(
            "sha256:", {"talentLines": compiler_input["talentLines"]}
        ),
    }
    identity_scenario = {
        **compiler_input["scenarioOptions"],
        "preparationLines": compiler_input["preparationLines"],
    }
    identity = {
        "resolvedLoadoutKey": loadout["resolvedLoadoutKey"],
        "talentProfileKey": provided_talent_key,
        "characterContext": identity_character,
        "scenarioOptions": identity_scenario,
        "compilerRevision": compiler_revision,
        "simcRuntimeRevision": simc_runtime_revision,
    }
    snapshot_key = _hash("simulation-snapshot:sha256:", identity)
    row = {
        "schemaRevision": SIMULATION_SNAPSHOT_SCHEMA_REVISION,
        "status": "ready",
        "simulationSnapshotKey": snapshot_key,
        "resolvedLoadoutKey": loadout["resolvedLoadoutKey"],
        "talentProfileKey": provided_talent_key,
        "talentLinesHash": identity_character["talentLinesHash"],
        "catalogRevision": _text(loadout.get("catalogRevision")),
        "gearRuleRevision": _text(loadout.get("gearRuleRevision")),
        "exactRegistryRevision": _text(loadout.get("exactRegistryRevision")),
        "characterContext": compiler_input["characterContext"],
        "scenarioOptions": compiler_input["scenarioOptions"],
        "preparationLines": compiler_input["preparationLines"],
        "compilerRevision": compiler_revision,
        "simcRuntimeRevision": simc_runtime_revision,
        "canonicalSimcInput": canonical_input,
        "canonicalInputHash": "simc-input:sha256:"
        + hashlib.sha256(canonical_input.encode("utf-8")).hexdigest(),
        "executionSupport": _canonical(support),
        "resultIdentity": "",
        "problemCodes": [],
        "problems": [],
    }
    row["rowHash"] = _hash(
        "sha256:",
        {key: value for key, value in row.items() if key != "rowHash"},
    )
    return row


def talent_profile_key_for_lines(talent_lines: Any) -> str:
    return talent_profile_key(talent_lines)


def verify_simulation_snapshot(value: Any) -> list[str]:
    row = dict(value) if isinstance(value, Mapping) else {}
    issues: list[str] = []
    if row.get("schemaRevision") != SIMULATION_SNAPSHOT_SCHEMA_REVISION:
        issues.append("SIMULATION_SNAPSHOT_SCHEMA_INVALID")
    if row.get("status") not in {"ready", "executed"}:
        issues.append("SIMULATION_SNAPSHOT_NOT_EXECUTABLE")
        return issues
    if not SIMULATION_SNAPSHOT_KEY_PATTERN.fullmatch(
        _text(row.get("simulationSnapshotKey"))
    ):
        issues.append("SIMULATION_SNAPSHOT_KEY_INVALID")
    talent_key = _text(row.get("talentProfileKey"))
    talent_lines_hash = _text(row.get("talentLinesHash"))
    if (
        not TALENT_PROFILE_KEY_PATTERN.fullmatch(talent_key)
        or not re.fullmatch(r"^sha256:[0-9a-f]{64}$", talent_lines_hash)
        or talent_key.split(":")[-1] != talent_lines_hash.split(":")[-1]
    ):
        issues.append("SIMULATION_TALENT_IDENTITY_MISMATCH")
    character = (
        row.get("characterContext")
        if isinstance(row.get("characterContext"), Mapping)
        else {}
    )
    scenario = (
        row.get("scenarioOptions")
        if isinstance(row.get("scenarioOptions"), Mapping)
        else {}
    )
    preparations = (
        row.get("preparationLines")
        if isinstance(row.get("preparationLines"), list)
        else []
    )
    expected_snapshot_key = _hash(
        "simulation-snapshot:sha256:",
        {
            "resolvedLoadoutKey": _text(row.get("resolvedLoadoutKey")),
            "talentProfileKey": talent_key,
            "characterContext": {
                **_canonical(character),
                "talentLinesHash": talent_lines_hash,
            },
            "scenarioOptions": {
                **_canonical(scenario),
                "preparationLines": _canonical(preparations),
            },
            "compilerRevision": _text(row.get("compilerRevision")),
            "simcRuntimeRevision": _text(row.get("simcRuntimeRevision")),
        },
    )
    if _text(row.get("simulationSnapshotKey")) != expected_snapshot_key:
        issues.append("SIMULATION_SNAPSHOT_IDENTITY_MISMATCH")
    canonical_input = row.get("canonicalSimcInput")
    if not isinstance(canonical_input, str) or not canonical_input.endswith("\n"):
        issues.append("SIMULATION_CANONICAL_INPUT_INVALID")
    else:
        expected_input_hash = "simc-input:sha256:" + hashlib.sha256(
            canonical_input.encode("utf-8")
        ).hexdigest()
        if _text(row.get("canonicalInputHash")) != expected_input_hash:
            issues.append("SIMULATION_CANONICAL_INPUT_HASH_INVALID")
    expected_row_hash = _hash(
        "sha256:",
        {key: value for key, value in row.items() if key != "rowHash"},
    )
    if _text(row.get("rowHash")) != expected_row_hash:
        issues.append("SIMULATION_SNAPSHOT_ROW_HASH_INVALID")
    return issues


def build_simulation_snapshot_v2(
    *,
    resolved_loadout: Any,
    talent_profile_key: str,
    talent_lines: Any,
    character_context: Any,
    scenario_options: Any,
    preparation_lines: Any,
    compiler_revision: str,
    simc_runtime_revision: str,
    authority_bundles: Any = None,
    origin_catalog_revision: str = "",
) -> dict[str, Any]:
    """Build the catalog-independent immutable v2 snapshot branch."""
    loadout = dict(resolved_loadout) if isinstance(resolved_loadout, Mapping) else {}
    problems: list[dict[str, str]] = []
    if (loadout.get("status") != "ready" or not RESOLVED_LOADOUT_V2_KEY_PATTERN.fullmatch(_text(loadout.get("resolvedLoadoutKey"))) or verify_resolved_loadout_v2(loadout, authority_bundles=authority_bundles)):
        problems.append(_problem("SIMULATION_V2_LOADOUT_NOT_READY", "resolvedLoadout", "Only a verified ready v2 loadout can be snapshotted."))
    if _text(loadout.get("simcRuntimeRevision")) != _text(simc_runtime_revision):
        problems.append(_problem("SIMULATION_V2_RUNTIME_MISMATCH", "simcRuntimeRevision", "Snapshot runtime must match every v2 authority bundle."))
    provided_talent_key = _text(talent_profile_key)
    if provided_talent_key != talent_profile_key_for_lines(talent_lines):
        problems.append(_problem("SIMULATION_TALENT_PROFILE_KEY_MISMATCH", "talentProfileKey", "Talent profile key must address canonical talent lines."))
    character = _valid_character_context(character_context)
    scenario = _valid_scenario_options(scenario_options)
    talents = _normalized_lines(talent_lines, _TALENT_LINE_PATTERN)
    preparations = _normalized_lines(preparation_lines, _OPTION_LINE_PATTERN)
    if character is None or scenario is None or not talents or preparations is None or not _text(compiler_revision):
        problems.append(_problem("SIMULATION_V2_COMPILER_INPUT_INVALID", "compilerInput", "V2 compiler input is invalid."))
    eligibility = loadout.get("eligibilityContext") if isinstance(loadout.get("eligibilityContext"), Mapping) else {}
    if character and (character.get("classKey") != eligibility.get("classKey") or character.get("specKey") != eligibility.get("specKey")):
        problems.append(_problem("SIMULATION_CHARACTER_LOADOUT_MISMATCH", "characterContext", "Character class/spec must match the resolved loadout."))
    if problems:
        return _blocked_v2("blocked", problems)
    gear_items = []
    for item in loadout.get("orderedSlots", []):
        if not isinstance(item, Mapping) or not _text(item.get("slot")) or not _text(item.get("itemId")):
            return _blocked_v2("blocked", [_problem("SIMULATION_V2_GEAR_INPUT_INVALID", "resolvedLoadout.orderedSlots", "V2 gear input is invalid.")])
        gear_items.append({"slot": _text(item.get("slot")), "itemId": _text(item.get("itemId")), "exactAuthorityEnvelopeKey": _text(item.get("exactAuthorityEnvelopeKey")), "simcOptions": _canonical(item.get("simcOptions") or {})})
    canonical_input = _v2_canonical_simc_input(character, scenario, talents, preparations or [], gear_items)
    if canonical_input is None:
        return _blocked_v2("blocked", [_problem("SIMULATION_V2_GEAR_INPUT_INVALID", "resolvedLoadout.orderedSlots", "V2 gear serializer input is invalid.")])
    identity = {"resolvedLoadoutKey": loadout["resolvedLoadoutKey"], "exactAuthorityBySlot": _canonical(loadout.get("exactAuthorityBySlot") or []), "effectEvidenceByOccurrence": _canonical(loadout.get("effectEvidenceByOccurrence") or []), "talentProfileKey": provided_talent_key, "characterContext": {**character, "talentLinesHash": _hash("sha256:", {"talentLines": talents})}, "scenarioOptions": {**scenario, "preparationLines": preparations or []}, "serializerInput": {"gearItems": gear_items}, "compilerRevision": _text(compiler_revision), "simcRuntimeRevision": _text(simc_runtime_revision)}
    row = {"schemaRevision": SIMULATION_SNAPSHOT_V2_SCHEMA_REVISION, "status": "ready", "simulationSnapshotKey": _hash("simulation-snapshot-v2:sha256:", identity), "resolvedLoadoutKey": loadout["resolvedLoadoutKey"], "exactAuthorityBySlot": _canonical(loadout.get("exactAuthorityBySlot") or []), "effectEvidenceByOccurrence": _canonical(loadout.get("effectEvidenceByOccurrence") or []), "talentProfileKey": provided_talent_key, "talentLinesHash": identity["characterContext"]["talentLinesHash"], "talentLines": talents, "characterContext": character, "scenarioOptions": scenario, "preparationLines": preparations or [], "serializerInput": {"gearItems": gear_items}, "compilerRevision": _text(compiler_revision), "simcRuntimeRevision": _text(simc_runtime_revision), "canonicalSimcInput": canonical_input, "canonicalInputHash": "simc-input:sha256:" + hashlib.sha256(canonical_input.encode("utf-8")).hexdigest(), "problemCodes": [], "problems": []}
    if _text(origin_catalog_revision):
        row["originCatalogRevision"] = _text(origin_catalog_revision)
    row["rowHash"] = _hash("sha256:", {key: value for key, value in row.items() if key not in {"rowHash", "originCatalogRevision"}})
    return row


def verify_simulation_snapshot_v2(
    value: Any,
    *,
    resolved_loadout: Any = None,
    authority_bundles: Any = None,
) -> list[str]:
    row = dict(value) if isinstance(value, Mapping) else {}
    if row.get("schemaRevision") != SIMULATION_SNAPSHOT_V2_SCHEMA_REVISION:
        return ["SIMULATION_SNAPSHOT_V2_SCHEMA_INVALID"]
    if row.get("status") not in {"ready", "executed"}:
        return ["SIMULATION_SNAPSHOT_V2_NOT_EXECUTABLE"]
    raw_occurrences = row.get("effectEvidenceByOccurrence")
    if not isinstance(raw_occurrences, list):
        return ["SIMULATION_V2_EFFECT_EVIDENCE_INVALID"]
    issues: list[str] = []
    loadout = dict(resolved_loadout) if isinstance(resolved_loadout, Mapping) else None
    if loadout is None:
        issues.append("SIMULATION_V2_RESOLVED_LOADOUT_CONTEXT_REQUIRED")
    elif authority_bundles is None:
        issues.append("SIMULATION_V2_AUTHORITY_CONTEXT_REQUIRED")
    elif verify_resolved_loadout_v2(loadout, authority_bundles=authority_bundles):
        issues.append("SIMULATION_V2_RESOLVED_LOADOUT_CONTEXT_INVALID")
    else:
        if (
            _text(row.get("resolvedLoadoutKey")) != _text(loadout.get("resolvedLoadoutKey"))
            or row.get("exactAuthorityBySlot") != loadout.get("exactAuthorityBySlot")
        ):
            issues.append("SIMULATION_V2_RESOLVED_LOADOUT_CONTEXT_MISMATCH")
        if raw_occurrences != loadout.get("effectEvidenceByOccurrence"):
            issues.append("SIMULATION_V2_EFFECT_EVIDENCE_CONTEXT_MISMATCH")
    if not SIMULATION_SNAPSHOT_V2_KEY_PATTERN.fullmatch(_text(row.get("simulationSnapshotKey"))):
        issues.append("SIMULATION_SNAPSHOT_V2_KEY_INVALID")
    identity = {"resolvedLoadoutKey": _text(row.get("resolvedLoadoutKey")), "exactAuthorityBySlot": _canonical(row.get("exactAuthorityBySlot") or []), "effectEvidenceByOccurrence": _canonical(row.get("effectEvidenceByOccurrence") or []), "talentProfileKey": _text(row.get("talentProfileKey")), "characterContext": {**_canonical(row.get("characterContext") or {}), "talentLinesHash": _text(row.get("talentLinesHash"))}, "scenarioOptions": {**_canonical(row.get("scenarioOptions") or {}), "preparationLines": _canonical(row.get("preparationLines") or [])}, "serializerInput": _canonical(row.get("serializerInput") or {}), "compilerRevision": _text(row.get("compilerRevision")), "simcRuntimeRevision": _text(row.get("simcRuntimeRevision"))}
    if _text(row.get("simulationSnapshotKey")) != _hash("simulation-snapshot-v2:sha256:", identity):
        issues.append("SIMULATION_SNAPSHOT_V2_IDENTITY_MISMATCH")
    character = _valid_character_context(row.get("characterContext"))
    scenario = _valid_scenario_options(row.get("scenarioOptions"))
    talents = _normalized_lines(row.get("talentLines"), _TALENT_LINE_PATTERN)
    preparations = _normalized_lines(row.get("preparationLines"), _OPTION_LINE_PATTERN)
    serializer = row.get("serializerInput") if isinstance(row.get("serializerInput"), Mapping) else {}
    gear_items = serializer.get("gearItems") if isinstance(serializer.get("gearItems"), list) else []
    authority_pairs = row.get("exactAuthorityBySlot") if isinstance(row.get("exactAuthorityBySlot"), list) else []
    authority_slots = [_text(pair.get("slot")) for pair in authority_pairs if isinstance(pair, Mapping)]
    authority_keys = [_text(pair.get("exactAuthorityEnvelopeKey")) for pair in authority_pairs if isinstance(pair, Mapping)]
    if (not authority_pairs or any(not isinstance(pair, Mapping) or set(pair) != {"slot", "exactAuthorityEnvelopeKey"} or _text(pair.get("slot")) not in CANONICAL_GEAR_SLOTS or not re.fullmatch(r"exact-authority:sha256:[0-9a-f]{64}", _text(pair.get("exactAuthorityEnvelopeKey"))) for pair in authority_pairs) or authority_slots != sorted(authority_slots, key=CANONICAL_GEAR_SLOTS.index) or len(set(authority_slots)) != len(authority_slots) or len(set(authority_keys)) != len(authority_keys)):
        issues.append("SIMULATION_V2_EXACT_AUTHORITY_INVALID")
    expected_pairs = [
        (_text(pair.get("slot")), _text(pair.get("exactAuthorityEnvelopeKey")))
        for pair in authority_pairs if isinstance(pair, Mapping)
    ]
    actual_pairs = [
        (_text(item.get("slot")), _text(item.get("exactAuthorityEnvelopeKey")))
        for item in gear_items if isinstance(item, Mapping)
    ]
    if (len(actual_pairs) != len(gear_items) or actual_pairs != expected_pairs or any(not slot or not key for slot, key in actual_pairs)):
        issues.append("SIMULATION_V2_SERIALIZER_AUTHORITY_MISMATCH")
    occurrences = raw_occurrences
    pair_by_slot = dict(expected_pairs)
    next_ordinal: dict[str, int] = {}
    prior_order = (-1, -1)
    for occurrence in occurrences:
        current = dict(occurrence) if isinstance(occurrence, Mapping) else {}
        slot = _text(current.get("slot"))
        ordinal = current.get("recordOrdinal")
        order = (CANONICAL_GEAR_SLOTS.index(slot) if slot in CANONICAL_GEAR_SLOTS else len(CANONICAL_GEAR_SLOTS), ordinal if type(ordinal) is int else -1)
        if (set(current) != {"scope", "slot", "exactAuthorityEnvelopeKey", "recordOrdinal", "subjectKind", "subjectKey", "subjectVariantSignature", "supportRecordKey"} or current.get("scope") != "slot" or pair_by_slot.get(slot) != _text(current.get("exactAuthorityEnvelopeKey")) or type(ordinal) is not int or ordinal != next_ordinal.get(slot, 0) or order < prior_order or not _text(current.get("subjectKind")) or not _text(current.get("subjectKey")) or not _text(current.get("subjectVariantSignature")) or not re.fullmatch(r"simc-item-effect-record:sha256:[0-9a-f]{64}", _text(current.get("supportRecordKey")))):
            issues.append("SIMULATION_V2_EFFECT_EVIDENCE_INVALID")
            break
        next_ordinal[slot] = ordinal + 1
        prior_order = order
    if (not talents or _text(row.get("talentProfileKey")) != talent_profile_key(talents) or _text(row.get("talentLinesHash")) != _hash("sha256:", {"talentLines": talents})):
        issues.append("SIMULATION_V2_TALENT_IDENTITY_MISMATCH")
    expected_input = _v2_canonical_simc_input(character, scenario, talents or [], preparations or [], gear_items) if character and scenario and talents and preparations is not None else None
    if expected_input is None or row.get("canonicalSimcInput") != expected_input:
        issues.append("SIMULATION_V2_CANONICAL_INPUT_INVALID")
    elif _text(row.get("canonicalInputHash")) != "simc-input:sha256:" + hashlib.sha256(expected_input.encode("utf-8")).hexdigest():
        issues.append("SIMULATION_V2_CANONICAL_INPUT_HASH_INVALID")
    expected_hash = _hash("sha256:", {key: value for key, value in row.items() if key not in {"rowHash", "originCatalogRevision"}})
    if _text(row.get("rowHash")) != expected_hash:
        issues.append("SIMULATION_SNAPSHOT_V2_ROW_HASH_INVALID")
    return issues


def _v2_canonical_simc_input(
    character: Mapping[str, Any] | None,
    scenario: Mapping[str, Any] | None,
    talents: list[str],
    preparations: list[str],
    gear_items: Any,
) -> str | None:
    if not character or not scenario or not talents or not isinstance(gear_items, list):
        return None
    gear_lines: list[str] = []
    for item in gear_items:
        line = _gear_line(item) if isinstance(item, Mapping) else None
        if not line:
            return None
        gear_lines.append(line)
    return "\n".join([f'{character["classKey"]}="{character["name"]}"', f'spec={character["specKey"]}', f'level={character["level"]}', f'race={character["race"]}', f'role={character["role"]}', f'position={character["position"]}', *talents, *gear_lines, *preparations, f'iterations={scenario["iterations"]}', f'fight_style={scenario["fightStyle"]}', f'desired_targets={scenario["desiredTargets"]}', f'max_time={scenario["maxTime"]}', f'vary_combat_length={scenario["varyCombatLength"]}', f'calculate_scale_factors={scenario["calculateScaleFactors"]}']) + "\n"


__all__ = (
    "SIMULATION_SNAPSHOT_SCHEMA_REVISION",
    "SIMULATION_SNAPSHOT_V2_SCHEMA_REVISION",
    "build_simulation_snapshot",
    "build_simulation_snapshot_v2",
    "compile_canonical_simc_input",
    "talent_profile_key",
    "talent_profile_key_for_lines",
    "verify_simulation_snapshot",
    "verify_simulation_snapshot_v2",
)

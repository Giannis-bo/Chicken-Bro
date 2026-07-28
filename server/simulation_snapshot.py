#!/usr/bin/env python3
"""Pure immutable SimulationSnapshot and canonical SimC compiler."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping

try:
    from .gear_resolved_loadout import (
        RESOLVED_LOADOUT_KEY_PATTERN,
        SIMC_OPTION_ORDER,
        verify_resolved_loadout,
    )
    from .simc_support_policy import simc_execution_support
except ImportError:
    from gear_resolved_loadout import (
        RESOLVED_LOADOUT_KEY_PATTERN,
        SIMC_OPTION_ORDER,
        verify_resolved_loadout,
    )
    from simc_support_policy import simc_execution_support


SIMULATION_SNAPSHOT_SCHEMA_REVISION = "simulation-snapshot-v1"
SIMULATION_SNAPSHOT_KEY_PATTERN = re.compile(
    r"^simulation-snapshot:sha256:[0-9a-f]{64}$"
)
TALENT_PROFILE_KEY_PATTERN = re.compile(
    r"^talent-profile:sha256:[0-9a-f]{64}$"
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


__all__ = (
    "SIMULATION_SNAPSHOT_SCHEMA_REVISION",
    "build_simulation_snapshot",
    "compile_canonical_simc_input",
    "talent_profile_key",
    "talent_profile_key_for_lines",
    "verify_simulation_snapshot",
)

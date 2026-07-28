#!/usr/bin/env python3
"""Compatibility bridge from the verified legacy profile to compiler v1."""

from __future__ import annotations

import re
from typing import Any, Mapping

try:
    from .gear_contracts import CANONICAL_GEAR_SLOTS
    from .simulation_snapshot import (
        SIMULATION_SNAPSHOT_SCHEMA_REVISION,
        build_simulation_snapshot,
        talent_profile_key,
    )
except ImportError:
    from gear_contracts import CANONICAL_GEAR_SLOTS
    from simulation_snapshot import (
        SIMULATION_SNAPSHOT_SCHEMA_REVISION,
        build_simulation_snapshot,
        talent_profile_key,
    )


_TALENT_KEYS = {
    "talents",
    "hero_talents",
    "class_talents",
    "spec_talents",
}
_CHARACTER_KEYS = {"spec", "level", "race", "role", "position"}
_SCENARIO_KEYS = {
    "iterations",
    "fight_style",
    "desired_targets",
    "max_time",
    "vary_combat_length",
    "calculate_scale_factors",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _blocked(code: str, path: str, message: str) -> dict[str, Any]:
    return {
        "schemaRevision": SIMULATION_SNAPSHOT_SCHEMA_REVISION,
        "status": "blocked",
        "executionSupport": {},
        "problemCodes": [code],
        "problems": [{"code": code, "path": path, "message": message}],
    }


def _parse_profile(profile: Any, scenario_key: str) -> dict[str, Any] | None:
    text = str(profile or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = [line.rstrip() for line in text.split("\n") if line.strip()]
    if not lines:
        return None
    actor = re.fullmatch(r'([a-z0-9_]+)="([a-z0-9_]+)"', lines[0])
    if not actor:
        return None
    character: dict[str, Any] = {
        "classKey": actor.group(1),
        "name": actor.group(2),
    }
    scenario: dict[str, Any] = {"scenarioKey": _text(scenario_key)}
    talents: list[str] = []
    preparations: list[str] = []
    gear_slots: set[str] = set()
    for line in lines[1:]:
        if "=" not in line:
            return None
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in CANONICAL_GEAR_SLOTS:
            if key in gear_slots or not value or ",id=" not in line:
                return None
            gear_slots.add(key)
        elif key in _TALENT_KEYS:
            talents.append(line)
        elif key in _CHARACTER_KEYS:
            if key == "spec":
                character["specKey"] = value
            elif key == "level":
                character["level"] = value
            else:
                character[key] = value
        elif key in _SCENARIO_KEYS:
            mapped = {
                "fight_style": "fightStyle",
                "desired_targets": "desiredTargets",
                "max_time": "maxTime",
                "vary_combat_length": "varyCombatLength",
                "calculate_scale_factors": "calculateScaleFactors",
            }.get(key, key)
            scenario[mapped] = value
        elif key == "optimal_raid" or key.startswith("override."):
            preparations.append(line)
        else:
            return None
    if not gear_slots or not talents:
        return None
    return {
        "canonicalInput": "\n".join(lines) + "\n",
        "characterContext": character,
        "scenarioOptions": scenario,
        "talentLines": talents,
        "preparationLines": preparations,
    }


def snapshot_from_compatibility_profile(
    resolved_loadout: Any,
    canonical_profile: Any,
    *,
    scenario_key: str,
    compiler_revision: str,
    simc_runtime_revision: str,
) -> dict[str, Any]:
    """Recompile a backend-owned profile and require byte-for-byte parity."""

    parsed = _parse_profile(canonical_profile, scenario_key)
    if not parsed:
        return _blocked(
            "SIMULATION_COMPATIBILITY_PROFILE_INVALID",
            "canonicalProfile",
            "Compatibility profile contains an unknown or malformed line.",
        )
    snapshot = build_simulation_snapshot(
        resolved_loadout=resolved_loadout,
        talent_profile_key=talent_profile_key(parsed["talentLines"]),
        talent_lines=parsed["talentLines"],
        character_context=parsed["characterContext"],
        scenario_options=parsed["scenarioOptions"],
        preparation_lines=parsed["preparationLines"],
        compiler_revision=compiler_revision,
        simc_runtime_revision=simc_runtime_revision,
    )
    if snapshot.get("status") != "ready":
        return snapshot
    if snapshot.get("canonicalSimcInput") != parsed["canonicalInput"]:
        return _blocked(
            "SIMULATION_COMPILER_COMPATIBILITY_MISMATCH",
            "canonicalProfile",
            "Compiler v1 output differs from the verified compatibility profile.",
        )
    return snapshot


__all__ = ("snapshot_from_compatibility_profile",)

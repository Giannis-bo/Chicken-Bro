import hashlib
import math
import re
from dataclasses import dataclass
from typing import Mapping
from uuid import UUID

from server.app.simulation.domain import SourceReadiness, SourceSnapshot
from server.app.simulation.readiness import SimcRuntimeCapabilities
from server.app.simulation.snapshots import REQUIRED_GEAR_SLOTS, canonical_json


class SimcCompileError(ValueError):
    def __init__(self, code: str, message: str = "SimC input cannot be compiled"):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class CompiledSimcInput:
    snapshot_id: UUID
    actor_name: str
    class_key: str
    spec_key: str
    race_key: str
    profile: str
    profile_sha256: str
    scenario: Mapping[str, object]
    scenario_hash: str
    compiler_revision: str
    runtime_revision: str
    provenance: Mapping[str, object]


SUPPORTED_FIGHT_STYLES = frozenset({"Patchwerk", "HecticAddCleave", "LightMovement", "HeavyMovement"})


def normalize_scenario(scenario: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(scenario, Mapping):
        raise SimcCompileError("SCENARIO_INVALID")
    allowed = {"fightStyle", "desiredTargets", "iterations", "maxTime", "gemOverrides",
               "varyCombatLength", "targetError", "raidBuffs", "bloodlust"}
    if any(key not in allowed for key in scenario):
        raise SimcCompileError("SCENARIO_INVALID")
    fight_style = scenario.get("fightStyle", "Patchwerk")
    if not isinstance(fight_style, str) or fight_style not in SUPPORTED_FIGHT_STYLES:
        raise SimcCompileError("SCENARIO_INVALID")
    desired_targets = scenario.get("desiredTargets", 1)
    iterations = scenario.get("iterations", 300)
    if (type(desired_targets) is not int or type(iterations) is not int
            or not 1 <= desired_targets <= 20 or not 1 <= iterations <= 10000):
        raise SimcCompileError("SCENARIO_INVALID")
    normalized: dict[str, object] = {
        "fightStyle": fight_style,
        "desiredTargets": desired_targets,
        "iterations": iterations,
    }
    # Optional fields stay absent for legacy requests, preserving their hashes.
    for key, maximum in (("varyCombatLength", 0.5), ("targetError", 5)):
        if key in scenario:
            value = scenario[key]
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
                raise SimcCompileError("SCENARIO_INVALID")
            normalized[key] = float(value)
    for key in ("raidBuffs", "bloodlust"):
        if key in scenario:
            if type(scenario[key]) is not bool:
                raise SimcCompileError("SCENARIO_INVALID")
            normalized[key] = scenario[key]
    if "maxTime" in scenario:
        max_time = scenario["maxTime"]
        if type(max_time) is not int or not 30 <= max_time <= 600:
            raise SimcCompileError("SCENARIO_INVALID")
        normalized["maxTime"] = max_time
    if "gemOverrides" in scenario:
        overrides = scenario["gemOverrides"]
        if not isinstance(overrides, Mapping) or len(overrides) > len(REQUIRED_GEAR_SLOTS):
            raise SimcCompileError("SCENARIO_INVALID")
        copied_overrides = {}
        for slot, gems in overrides.items():
            if (
                slot not in REQUIRED_GEAR_SLOTS
                or not isinstance(gems, list)
                or not 1 <= len(gems) <= 32
                or any(type(gem) is not int or not 1 <= gem <= 2147483647 for gem in gems)
            ):
                raise SimcCompileError("SCENARIO_INVALID")
            copied_overrides[slot] = list(gems)
        normalized["gemOverrides"] = copied_overrides
    return normalized


def scenario_hash(scenario: Mapping[str, object]) -> str:
    normalized = normalize_scenario(scenario)
    return hashlib.sha256(canonical_json(normalized).encode("utf-8")).hexdigest()


class SimcProfileCompiler:
    def __init__(self, *, capabilities: SimcRuntimeCapabilities):
        self._capabilities = capabilities

    def compile(self, snapshot: SourceSnapshot, scenario: Mapping[str, object]) -> CompiledSimcInput:
        readiness = getattr(snapshot, "readiness", SourceReadiness.INCOMPLETE_FOR_SIMC)
        if not isinstance(readiness, SourceReadiness):
            readiness = SourceReadiness(str(readiness))
        if readiness is not SourceReadiness.READY_FOR_SIMC:
            raise SimcCompileError("SNAPSHOT_NOT_READY")
        normalized_scenario = normalize_scenario(scenario)
        raw_snapshot = snapshot.snapshot if isinstance(snapshot.snapshot, Mapping) else {}
        character = raw_snapshot.get("character") if isinstance(raw_snapshot.get("character"), Mapping) else {}
        gear = raw_snapshot.get("gear") if isinstance(raw_snapshot.get("gear"), Mapping) else {}
        gear_state = raw_snapshot.get("gearState") if isinstance(raw_snapshot.get("gearState"), Mapping) else {}
        talents = raw_snapshot.get("talents") if isinstance(raw_snapshot.get("talents"), Mapping) else {}
        profile_source = str(raw_snapshot.get("profileSource") or "").strip().lower()
        if profile_source != snapshot.provider.value:
            raise SimcCompileError("PROFILE_NOT_REAL_SOURCE")

        name = self._profile_name(character.get("name"))
        level = character.get("level")
        if not isinstance(level, int) or isinstance(level, bool) or level <= 0:
            raise SimcCompileError("MISSING_LEVEL", "character level is missing")
        class_key = self._token(character.get("classKey"), "class", "MISSING_CLASS")
        spec_key = self._token(character.get("specKey"), "spec", "MISSING_SPEC")
        race_key = self._token(character.get("raceKey"), "race", "MISSING_RACE")
        region = self._token(character.get("region"), "region", "MISSING_REGION")
        realm = self._server_token(character.get("realm"))
        if self._capabilities.compiler_revision not in {
            "chickenbro-simc-compiler-v1", "chickenbro-simc-compiler-v2", "chickenbro-simc-compiler-v3"
        }:
            raise SimcCompileError("COMPILER_UNAVAILABLE")
        if (
            {"maxTime", "gemOverrides"}.intersection(normalized_scenario)
            and self._capabilities.compiler_revision == "chickenbro-simc-compiler-v1"
        ):
            raise SimcCompileError("COMPILER_UNAVAILABLE")
        if ({"varyCombatLength", "targetError", "raidBuffs", "bloodlust"}.intersection(normalized_scenario)
                and self._capabilities.compiler_revision != "chickenbro-simc-compiler-v3"):
            raise SimcCompileError("COMPILER_UNAVAILABLE")
        if not self._capabilities.runtime_revision or not self._capabilities.supports(class_key, spec_key):
            raise SimcCompileError("RUNTIME_UNAVAILABLE")
        lines = [
            f'{class_key}="{name}"',
            f"level={level}",
            f"race={race_key}",
            f"region={region}",
            f"server={realm}",
            f"spec={spec_key}",
        ]
        talent_string = str(talents.get("string") or "").strip()
        if talent_string and re.fullmatch(r"[A-Za-z0-9+/=_-]{4,512}", talent_string):
            lines.append(f"talents={talent_string}")
        else:
            loadout = talents.get("loadout") if isinstance(talents.get("loadout"), list) else []
            normalized_loadout = []
            for entry in loadout:
                if not isinstance(entry, Mapping):
                    continue
                talent_id = entry.get("id") or entry.get("talentId")
                rank = entry.get("rank") or entry.get("points")
                if (
                    isinstance(talent_id, int)
                    and not isinstance(talent_id, bool)
                    and talent_id > 0
                    and isinstance(rank, int)
                    and not isinstance(rank, bool)
                    and rank > 0
                ):
                    normalized_loadout.append(f"{talent_id}:{rank}")
            if not normalized_loadout:
                raise SimcCompileError("MISSING_TALENTS")
            if len(normalized_loadout) != len(loadout):
                raise SimcCompileError("TALENTS_INVALID")
            lines.append("talents=" + ",".join(normalized_loadout))

        unequipped_slots = {
            str(slot)
            for slot in gear_state.get("unequippedSlots", ())
            if isinstance(slot, str)
        }
        gem_overrides = normalized_scenario.get("gemOverrides", {})
        for slot, replacement in gem_overrides.items():
            item = gear.get(slot)
            original_gems = item.get("gems") if isinstance(item, Mapping) else None
            if not isinstance(original_gems, (list, tuple)) or len(replacement) != len(original_gems):
                raise SimcCompileError("GEM_OVERRIDE_SOCKET_MISMATCH")
        for slot in REQUIRED_GEAR_SLOTS:
            item = gear.get(slot)
            if slot == "off_hand" and item is None and slot in unequipped_slots:
                continue
            if not isinstance(item, Mapping):
                raise SimcCompileError(f"MISSING_GEAR_{slot.upper()}")
            item_id = item.get("itemId")
            if not isinstance(item_id, int) or isinstance(item_id, bool) or item_id <= 0:
                raise SimcCompileError(f"MISSING_GEAR_{slot.upper()}")
            item_level = item.get("itemLevel")
            if not isinstance(item_level, int) or isinstance(item_level, bool) or item_level <= 0:
                raise SimcCompileError(f"MISSING_GEAR_{slot.upper()}_ITEMLEVEL")
            for semantic in ("bonusIds", "gems", "enchant"):
                if semantic not in item:
                    raise SimcCompileError(f"MISSING_GEAR_{slot.upper()}_{semantic.upper()}")
            for semantic in ("bonusIds", "gems"):
                raw_values = item.get(semantic)
                if (
                    not isinstance(raw_values, (list, tuple))
                    or len(raw_values) > 32
                    or any(
                        not isinstance(value, int) or isinstance(value, bool) or value <= 0
                        for value in raw_values
                    )
                ):
                    raise SimcCompileError(f"INVALID_GEAR_{slot.upper()}_{semantic.upper()}")
            enchant = item.get("enchant")
            if not (
                enchant is None
                or enchant == ""
                or (isinstance(enchant, int) and not isinstance(enchant, bool) and enchant > 0)
                or (isinstance(enchant, str) and enchant.isdigit() and int(enchant) > 0)
            ):
                raise SimcCompileError(f"INVALID_GEAR_{slot.upper()}_ENCHANT")
            line = f"{slot}=,id={item_id}"
            bonus_ids = self._positive_ints(item.get("bonusIds"))
            gems = gem_overrides.get(slot, self._positive_ints(item.get("gems")))
            enchant = item.get("enchant")
            if bonus_ids:
                line += ",bonus_id=" + "/".join(str(value) for value in bonus_ids)
            if gems:
                line += ",gem_id=" + "/".join(str(value) for value in gems)
            if isinstance(enchant, int) and enchant > 0:
                line += f",enchant_id={enchant}"
            elif isinstance(enchant, str) and enchant.isdigit() and int(enchant) > 0:
                line += f",enchant_id={int(enchant)}"
            lines.append(line)

        lines.extend([
            f"iterations={normalized_scenario['iterations']}",
            f"fight_style={normalized_scenario['fightStyle']}",
            f"desired_targets={normalized_scenario['desiredTargets']}",
        ])
        if "maxTime" in normalized_scenario:
            lines.extend([
                f"max_time={normalized_scenario['maxTime']}",
                "fixed_time=1",
                "vary_combat_length=0",
            ])
        for key, option in (("varyCombatLength", "vary_combat_length"), ("targetError", "target_error")):
            if key in normalized_scenario:
                lines.append(f"{option}={normalized_scenario[key]:g}")
        for key, option in (("raidBuffs", "optimal_raid"), ("bloodlust", "override.bloodlust")):
            if key in normalized_scenario:
                lines.append(f"{option}={int(normalized_scenario[key])}")
        profile = "\n".join(lines) + "\n"
        if len(profile) > 24000:
            raise SimcCompileError("PROFILE_TOO_LARGE")
        compiled_scenario_hash = scenario_hash(normalized_scenario)
        profile_sha256 = hashlib.sha256(profile.encode("utf-8")).hexdigest()
        provenance = {
            "provider": snapshot.provider.value,
            "sourceUrl": snapshot.source_url,
            "sourceRevision": snapshot.provenance.get("sourceRevision", ""),
            "sourceRawSha256": snapshot.raw_sha256,
            "snapshotRevision": snapshot.revision,
        }
        return CompiledSimcInput(
            snapshot_id=snapshot.id,
            actor_name=name,
            class_key=class_key,
            spec_key=spec_key,
            race_key=race_key,
            profile=profile,
            profile_sha256=profile_sha256,
            scenario=normalized_scenario,
            scenario_hash=compiled_scenario_hash,
            compiler_revision=self._capabilities.compiler_revision,
            runtime_revision=self._capabilities.runtime_revision,
            provenance=provenance,
        )

    @staticmethod
    def _token(value: object, field: str, error_code: str = "SNAPSHOT_NOT_READY") -> str:
        token = str(value or "").strip()
        if not token or re.fullmatch(r"[A-Za-z0-9_-]{1,80}", token) is None:
            raise SimcCompileError(error_code, f"{field} is invalid")
        return token

    @staticmethod
    def _server_token(value: object) -> str:
        token = re.sub(r"\s+", "-", str(value or "").strip().lower())
        token = re.sub(r"[^a-z0-9_-]", "", token)
        if not token or len(token) > 80:
            raise SimcCompileError("MISSING_REALM", "server is invalid")
        return token

    @staticmethod
    def _profile_name(value: object) -> str:
        name = str(value or "").strip().replace("\\", "\\\\").replace('"', '\\"')
        name = "".join(character for character in name if ord(character) >= 0x20)
        if not name or len(name) > 80:
            raise SimcCompileError("MISSING_CHARACTER_NAME")
        return name

    @staticmethod
    def _positive_ints(value: object) -> list[int]:
        if not isinstance(value, (list, tuple)):
            return []
        return [item for item in value if isinstance(item, int) and item > 0][:32]


__all__ = (
    "CompiledSimcInput",
    "SimcCompileError",
    "SimcProfileCompiler",
    "normalize_scenario",
    "scenario_hash",
)

import hashlib
import re
from dataclasses import dataclass
from typing import Mapping
from uuid import UUID

from server.app.simulation.domain import SourceReadiness, SourceSnapshot
from server.app.simulation.readiness import PROTOTYPE_MAX_CHARACTER_LEVEL, SimcRuntimeCapabilities
from server.app.simulation.snapshots import canonical_json


class SimcCompileError(ValueError):
    def __init__(self, code: str, message: str = "SimC input cannot be compiled"):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class CompiledSimcInput:
    snapshot_id: UUID
    profile: str
    profile_sha256: str
    scenario: Mapping[str, object]
    scenario_hash: str
    compiler_revision: str
    runtime_revision: str
    provenance: Mapping[str, object]


_SAFE_SCENARIO_TEXT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,63}$")
_GEAR_SLOTS = (
    "head",
    "neck",
    "shoulder",
    "back",
    "chest",
    "wrist",
    "hands",
    "waist",
    "legs",
    "feet",
    "finger1",
    "finger2",
    "trinket1",
    "trinket2",
    "main_hand",
    "off_hand",
)


class SimcProfileCompiler:
    def __init__(self, *, capabilities: SimcRuntimeCapabilities):
        self._capabilities = capabilities

    def compile(self, snapshot: SourceSnapshot, scenario: Mapping[str, object]) -> CompiledSimcInput:
        readiness = getattr(snapshot, "readiness", SourceReadiness.INCOMPLETE_FOR_SIMC)
        if not isinstance(readiness, SourceReadiness):
            readiness = SourceReadiness(str(readiness))
        if readiness is not SourceReadiness.READY_FOR_SIMC:
            raise SimcCompileError("SNAPSHOT_NOT_READY")
        if not isinstance(scenario, Mapping):
            raise SimcCompileError("SCENARIO_INVALID")
        normalized_scenario = self._normalize_scenario(scenario)
        raw_snapshot = snapshot.snapshot if isinstance(snapshot.snapshot, Mapping) else {}
        character = raw_snapshot.get("character") if isinstance(raw_snapshot.get("character"), Mapping) else {}
        gear = raw_snapshot.get("gear") if isinstance(raw_snapshot.get("gear"), Mapping) else {}
        talents = raw_snapshot.get("talents") if isinstance(raw_snapshot.get("talents"), Mapping) else {}

        name = self._profile_name(character.get("name"))
        lines = [
            f'{character.get("classKey")}="{name}"',
            f"level={PROTOTYPE_MAX_CHARACTER_LEVEL}",
            f'race={self._token(character.get("raceKey"), "race")}',
            f'region={self._token(character.get("region"), "region")}',
            f"server={self._server_token(character.get('realm'))}",
            f'spec={self._token(character.get("specKey"), "spec")}',
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
                rank = entry.get("rank") or entry.get("points") or 1
                if isinstance(talent_id, int) and talent_id > 0 and isinstance(rank, int) and rank > 0:
                    normalized_loadout.append(f"{talent_id}:{rank}")
            if not normalized_loadout:
                raise SimcCompileError("TALENTS_INVALID")
            lines.append("talents=" + ",".join(normalized_loadout))

        for slot in _GEAR_SLOTS:
            item = gear.get(slot)
            if slot == "off_hand" and item is None:
                continue
            if not isinstance(item, Mapping):
                raise SimcCompileError("SNAPSHOT_NOT_READY")
            item_id = item.get("itemId")
            if not isinstance(item_id, int) or item_id <= 0:
                raise SimcCompileError("SNAPSHOT_NOT_READY")
            line = f"{slot}=,id={item_id}"
            bonus_ids = self._positive_ints(item.get("bonusIds"))
            gems = self._positive_ints(item.get("gems"))
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
        profile = "\n".join(lines) + "\n"
        if len(profile) > 24000:
            raise SimcCompileError("PROFILE_TOO_LARGE")
        scenario_hash = hashlib.sha256(canonical_json(normalized_scenario).encode("utf-8")).hexdigest()
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
            profile=profile,
            profile_sha256=profile_sha256,
            scenario=normalized_scenario,
            scenario_hash=scenario_hash,
            compiler_revision=self._capabilities.compiler_revision,
            runtime_revision=self._capabilities.runtime_revision,
            provenance=provenance,
        )

    @staticmethod
    def _normalize_scenario(scenario: Mapping[str, object]) -> dict[str, object]:
        allowed = {"fightStyle", "desiredTargets", "iterations"}
        if any(key not in allowed for key in scenario):
            raise SimcCompileError("SCENARIO_INVALID")
        fight_style = str(scenario.get("fightStyle", "Patchwerk"))
        if _SAFE_SCENARIO_TEXT.fullmatch(fight_style) is None:
            raise SimcCompileError("SCENARIO_INVALID")
        try:
            desired_targets = int(scenario.get("desiredTargets", 1))
            iterations = int(scenario.get("iterations", 300))
        except (TypeError, ValueError):
            raise SimcCompileError("SCENARIO_INVALID") from None
        if not 1 <= desired_targets <= 20 or not 1 <= iterations <= 10000:
            raise SimcCompileError("SCENARIO_INVALID")
        return {
            "fightStyle": fight_style,
            "desiredTargets": desired_targets,
            "iterations": iterations,
        }

    @staticmethod
    def _token(value: object, field: str) -> str:
        token = str(value or "").strip()
        if not token or re.fullmatch(r"[A-Za-z0-9_-]{1,80}", token) is None:
            raise SimcCompileError("SNAPSHOT_NOT_READY", f"{field} is invalid")
        return token

    @staticmethod
    def _server_token(value: object) -> str:
        token = re.sub(r"\s+", "-", str(value or "").strip().lower())
        token = re.sub(r"[^a-z0-9_-]", "", token)
        if not token or len(token) > 80:
            raise SimcCompileError("SNAPSHOT_NOT_READY", "server is invalid")
        return token

    @staticmethod
    def _profile_name(value: object) -> str:
        name = str(value or "").strip().replace("\\", "\\\\").replace('"', '\\"')
        name = "".join(character for character in name if ord(character) >= 0x20)
        if not name or len(name) > 80:
            raise SimcCompileError("SNAPSHOT_NOT_READY")
        return name

    @staticmethod
    def _positive_ints(value: object) -> list[int]:
        if not isinstance(value, (list, tuple)):
            return []
        return [item for item in value if isinstance(item, int) and item > 0][:32]


__all__ = ("CompiledSimcInput", "SimcCompileError", "SimcProfileCompiler")

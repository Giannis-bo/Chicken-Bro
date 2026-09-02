import os
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from server.app.simulation.domain import SourceReadiness, SourceSnapshot


PROTOTYPE_MAX_CHARACTER_LEVEL = 90


@dataclass(frozen=True)
class SimcRuntimeCapabilities:
    runtime_revision: str
    compiler_revision: str
    supported_specs: frozenset[tuple[str, str]]

    def supports(self, class_key: str, spec_key: str) -> bool:
        return (class_key, spec_key) in self.supported_specs or ("*", "*") in self.supported_specs

    @classmethod
    def from_env(cls) -> "SimcRuntimeCapabilities":
        raw_specs = os.environ.get("WOW_SIMC_SUPPORTED_SPECS", "").strip()
        supported: set[tuple[str, str]] = set()
        for value in raw_specs.split(","):
            parts = [part.strip().lower() for part in value.split(":")]
            if len(parts) == 2 and all(parts):
                supported.add((parts[0], parts[1]))
        runtime_revision = os.environ.get("WOW_SIMC_RUNTIME_REVISION", "").strip()
        if not runtime_revision:
            state_path = os.environ.get("WOW_SIMC_VERSION_FILE", "/var/lib/wow-backend/simc-version.json").strip()
            try:
                state = json.loads(Path(state_path).read_text(encoding="utf-8"))
                runtime_revision = str(state.get("simcRuntimeRevision") or "").strip()
            except (OSError, TypeError, ValueError, UnicodeError):
                runtime_revision = ""
        return cls(
            runtime_revision=runtime_revision,
            compiler_revision=os.environ.get("WOW_SIMC_COMPILER_REVISION", "chickenbro-simc-compiler-v1").strip(),
            supported_specs=frozenset(supported),
        )


@dataclass(frozen=True)
class ReadinessReport:
    readiness: SourceReadiness
    blockers: tuple[str, ...]
    checks: Mapping[str, bool]

    @property
    def ready(self) -> bool:
        return self.readiness is SourceReadiness.READY_FOR_SIMC

    def public(self) -> dict[str, object]:
        return {
            "readiness": self.readiness.value,
            "blockers": list(self.blockers),
            "checks": dict(self.checks),
        }


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_GEAR_SLOTS = (
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


class SimcReadinessValidator:
    def validate(
        self,
        snapshot: SourceSnapshot | object,
        runtime_capabilities: SimcRuntimeCapabilities,
    ) -> ReadinessReport:
        upstream = getattr(snapshot, "readiness", SourceReadiness.INCOMPLETE_FOR_SIMC)
        if not isinstance(upstream, SourceReadiness):
            upstream = SourceReadiness(str(upstream))
        if upstream not in {SourceReadiness.INCOMPLETE_FOR_SIMC, SourceReadiness.READY_FOR_SIMC}:
            return ReadinessReport(upstream, (upstream.value,), {})

        raw_snapshot = getattr(snapshot, "snapshot", {})
        raw_provenance = getattr(snapshot, "provenance", {})
        character = raw_snapshot.get("character") if isinstance(raw_snapshot, Mapping) else {}
        character = character if isinstance(character, Mapping) else {}
        gear = raw_snapshot.get("gear") if isinstance(raw_snapshot, Mapping) else {}
        gear = gear if isinstance(gear, Mapping) else {}
        talents = raw_snapshot.get("talents") if isinstance(raw_snapshot, Mapping) else {}
        talents = talents if isinstance(talents, Mapping) else {}

        checks: dict[str, bool] = {}
        blockers: list[str] = []

        def require(name: str, condition: bool, blocker: str) -> None:
            checks[name] = bool(condition)
            if not condition:
                blockers.append(blocker)

        require("identity", bool(str(character.get("name") or "").strip()), "CHARACTER_IDENTITY_MISSING")
        require("class", bool(str(character.get("classKey") or "").strip()), "CHARACTER_CLASS_MISSING")
        require("spec", bool(str(character.get("specKey") or "").strip()), "CHARACTER_SPEC_MISSING")
        require("race", bool(str(character.get("raceKey") or "").strip()), "CHARACTER_RACE_MISSING")
        level = character.get("level")
        # The Web prototype intentionally simulates max-level characters. A
        # missing level in an older persisted snapshot is therefore acceptable;
        # the compiler applies PROTOTYPE_MAX_CHARACTER_LEVEL below.
        require(
            "level",
            level is None or (isinstance(level, int) and level > 0),
            "CHARACTER_LEVEL_MISSING",
        )

        for slot in _REQUIRED_GEAR_SLOTS:
            item = gear.get(slot)
            if slot == "off_hand" and item is None:
                # Raider.IO omits this slot when the character has no equipped
                # offhand (for example, a two-handed caster weapon). The
                # absence is a valid observed state, not a missing item to
                # synthesize.
                checks[f"gear.{slot}"] = True
                continue
            valid_item = isinstance(item, Mapping) and isinstance(item.get("itemId"), int) and item.get("itemId", 0) > 0
            require(f"gear.{slot}", valid_item, f"GEAR_{slot.upper()}_MISSING")
            if valid_item:
                require(
                    f"gear.{slot}.itemLevel",
                    isinstance(item.get("itemLevel"), int) and item.get("itemLevel", 0) > 0,
                    f"GEAR_{slot.upper()}_ITEMLEVEL_MISSING",
                )
                for semantic in ("bonusIds", "gems", "enchant"):
                    require(
                        f"gear.{slot}.{semantic}",
                        semantic in item,
                        f"GEAR_{slot.upper()}_{semantic.upper()}_MISSING",
                    )

        has_talents = bool(talents.get("loadout")) or bool(str(talents.get("string") or "").strip())
        require("talents", has_talents, "TALENTS_MISSING")
        require(
            "provenance",
            isinstance(raw_provenance, Mapping)
            and bool(str(raw_provenance.get("sourceUrl") or "").strip())
            and bool(str(raw_provenance.get("sourceRevision") or "").strip())
            and bool(str(raw_provenance.get("fetchedAt") or "").strip()),
            "SOURCE_PROVENANCE_MISSING",
        )
        raw_sha256 = str(getattr(snapshot, "raw_sha256", ""))
        require("rawHash", _SHA256.fullmatch(raw_sha256) is not None, "SOURCE_HASH_MISSING")

        profile_source = str(raw_snapshot.get("profileSource") or "").strip().lower()
        require(
            "realSource",
            profile_source not in {"generated", "preview", "template", "client"}
            and profile_source in {"raiderio", "warcraftlogs"},
            "PROFILE_NOT_REAL_SOURCE",
        )

        class_key = str(character.get("classKey") or "").strip().lower()
        spec_key = str(character.get("specKey") or "").strip().lower()
        require(
            "compiler",
            runtime_capabilities.compiler_revision == "chickenbro-simc-compiler-v1",
            "COMPILER_UNAVAILABLE",
        )
        require(
            "runtime",
            bool(runtime_capabilities.runtime_revision) and runtime_capabilities.supports(class_key, spec_key),
            "RUNTIME_UNAVAILABLE",
        )

        unique_blockers = tuple(dict.fromkeys(blockers))
        return ReadinessReport(
            SourceReadiness.READY_FOR_SIMC if not unique_blockers else SourceReadiness.INCOMPLETE_FOR_SIMC,
            unique_blockers,
            checks,
        )


__all__ = (
    "PROTOTYPE_MAX_CHARACTER_LEVEL",
    "ReadinessReport",
    "SimcReadinessValidator",
    "SimcRuntimeCapabilities",
)

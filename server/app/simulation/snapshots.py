import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping
from uuid import UUID

from server.app.simulation.domain import SourceProvider, SourceReadiness, SourceSnapshot


REQUIRED_CHARACTER_PATHS = (
    "character.name",
    "character.region",
    "character.realm",
    "character.level",
    "character.classKey",
    "character.specKey",
    "character.raceKey",
)

REQUIRED_GEAR_SLOTS = (
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

_TALENT_STRING = re.compile(r"^[A-Za-z0-9+/=_-]{4,512}$")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def missing_snapshot_fields(snapshot: Mapping[str, object]) -> tuple[str, ...]:
    character = snapshot.get("character") if isinstance(snapshot.get("character"), Mapping) else {}
    gear = snapshot.get("gear") if isinstance(snapshot.get("gear"), Mapping) else {}
    gear_state = snapshot.get("gearState") if isinstance(snapshot.get("gearState"), Mapping) else {}
    talents = snapshot.get("talents") if isinstance(snapshot.get("talents"), Mapping) else {}
    unequipped_slots = {
        str(slot)
        for slot in gear_state.get("unequippedSlots", ())
        if isinstance(slot, str)
    }
    missing: list[str] = []

    for path in REQUIRED_CHARACTER_PATHS:
        field = path.split(".", 1)[1]
        value = character.get(field)
        present = (
            isinstance(value, int) and not isinstance(value, bool) and value > 0
            if field == "level"
            else bool(str(value or "").strip())
        )
        if not present:
            missing.append(path)

    loadout = talents.get("loadout")
    has_valid_loadout = (
        isinstance(loadout, list)
        and bool(loadout)
        and all(
            isinstance(entry, Mapping)
            and isinstance(entry.get("id") or entry.get("talentId"), int)
            and not isinstance(entry.get("id") or entry.get("talentId"), bool)
            and int(entry.get("id") or entry.get("talentId")) > 0
            and isinstance(entry.get("rank") or entry.get("points"), int)
            and not isinstance(entry.get("rank") or entry.get("points"), bool)
            and int(entry.get("rank") or entry.get("points")) > 0
            for entry in loadout
        )
    )
    talent_string = str(talents.get("string") or "").strip()
    has_talents = has_valid_loadout or _TALENT_STRING.fullmatch(talent_string) is not None
    if not has_talents:
        missing.append("talents.loadout")

    for slot in REQUIRED_GEAR_SLOTS:
        item = gear.get(slot)
        if slot == "off_hand" and slot in unequipped_slots:
            if item is not None:
                missing.append(f"gearState.unequippedSlots.{slot}")
            continue
        if not isinstance(item, Mapping):
            missing.append(f"gear.{slot}")
            continue
        item_id = item.get("itemId")
        if not isinstance(item_id, int) or isinstance(item_id, bool) or item_id <= 0:
            missing.append(f"gear.{slot}.itemId")
        item_level = item.get("itemLevel")
        if not isinstance(item_level, int) or isinstance(item_level, bool) or item_level <= 0:
            missing.append(f"gear.{slot}.itemLevel")
        for semantic in ("bonusIds", "gems"):
            value = item.get(semantic)
            if (
                semantic not in item
                or not isinstance(value, (list, tuple))
                or len(value) > 32
                or any(
                    not isinstance(entry, int) or isinstance(entry, bool) or entry <= 0
                    for entry in value
                )
            ):
                missing.append(f"gear.{slot}.{semantic}")
        enchant = item.get("enchant")
        valid_enchant = (
            enchant is None
            or enchant == ""
            or (isinstance(enchant, int) and not isinstance(enchant, bool) and enchant > 0)
            or (isinstance(enchant, str) and enchant.isdigit() and int(enchant) > 0)
        )
        if "enchant" not in item or not valid_enchant:
            missing.append(f"gear.{slot}.enchant")

    return tuple(missing)


@dataclass(frozen=True)
class CharacterSnapshotCandidate:
    provider: SourceProvider
    source_url: str
    source_key: str
    snapshot: Mapping[str, object]
    provenance: Mapping[str, object]
    raw_sha256: str
    fetched_at: datetime
    readiness: SourceReadiness = SourceReadiness.INCOMPLETE_FOR_SIMC
    blockers: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()

    def to_source_snapshot(
        self,
        *,
        user_id: UUID | str,
        snapshot_id: UUID | str,
        readiness_report: object | None = None,
        revision: int = 1,
    ) -> SourceSnapshot:
        readiness = self.readiness
        blockers = self.blockers
        if readiness_report is not None:
            readiness = getattr(readiness_report, "readiness", readiness)
            blockers = tuple(getattr(readiness_report, "blockers", blockers))
        serialized_snapshot = dict(self.snapshot)
        if blockers:
            serialized_snapshot["readinessBlockers"] = list(blockers)
        if self.missing_fields:
            serialized_snapshot["missingFields"] = list(self.missing_fields)
        return SourceSnapshot(
            id=snapshot_id if isinstance(snapshot_id, UUID) else UUID(str(snapshot_id)),
            user_id=user_id if isinstance(user_id, UUID) else UUID(str(user_id)),
            provider=self.provider,
            source_url=self.source_url,
            source_key=self.source_key,
            revision=max(1, int(revision)),
            readiness=readiness if isinstance(readiness, SourceReadiness) else SourceReadiness(str(readiness)),
            snapshot=serialized_snapshot,
            provenance=dict(self.provenance),
            raw_sha256=self.raw_sha256,
            fetched_at=self.fetched_at,
        )


__all__ = (
    "CharacterSnapshotCandidate",
    "REQUIRED_CHARACTER_PATHS",
    "REQUIRED_GEAR_SLOTS",
    "canonical_json",
    "missing_snapshot_fields",
    "sha256_json",
)

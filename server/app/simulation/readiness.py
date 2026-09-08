import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from server.app.simulation.wcl_talents import talent_catalog_matches_runtime
from server.app.simulation.domain import SourceReadiness, SourceSnapshot
from server.app.simulation.snapshots import (
    REQUIRED_CHARACTER_PATHS,
    REQUIRED_GEAR_SLOTS,
    missing_snapshot_fields,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SOURCE_ARCHIVE_IDENTITY = re.compile(r"^(?:[0-9a-f]{64}|legacy-unavailable)$")


class ManagedSimcRuntimeError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ManagedSimcRuntimeIdentity:
    binary_path: Path
    source_commit: str
    binary_sha256: str
    runtime_revision: str


def _read_runtime_metadata(path: Path) -> str:
    try:
        path_state = path.lstat()
    except OSError as error:
        raise ManagedSimcRuntimeError("SIMC_IDENTITY_INVALID") from error
    if not stat.S_ISREG(path_state.st_mode) or path_state.st_size > 256:
        raise ManagedSimcRuntimeError("SIMC_IDENTITY_INVALID")
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as error:
        raise ManagedSimcRuntimeError("SIMC_IDENTITY_INVALID") from error


@lru_cache(maxsize=8)
def _cached_binary_sha256(
    path_text: str,
    device: int,
    inode: int,
    size: int,
    modified_ns: int,
) -> str:
    path = Path(path_text)
    digest = hashlib.sha256()
    with path.open("rb") as binary:
        opened = os.fstat(binary.fileno())
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != (
            device,
            inode,
            size,
            modified_ns,
        ):
            raise OSError("SimulationCraft binary changed during identity check")
        for chunk in iter(lambda: binary.read(1024 * 1024), b""):
            digest.update(chunk)
        closed = os.fstat(binary.fileno())
    if (closed.st_dev, closed.st_ino, closed.st_size, closed.st_mtime_ns) != (
        device,
        inode,
        size,
        modified_ns,
    ):
        raise OSError("SimulationCraft binary changed during identity check")
    return digest.hexdigest()


def inspect_managed_simc_runtime(
    env: Mapping[str, str] | None = None,
) -> ManagedSimcRuntimeIdentity:
    source_env = os.environ if env is None else env
    raw_binary = Path(source_env.get("WOW_SIMC_BIN", "/opt/wow-simc/current/simc").strip())
    if not raw_binary.is_absolute() or raw_binary.name != "simc":
        raise ManagedSimcRuntimeError("SIMC_IDENTITY_INVALID")
    current_link = raw_binary.parent
    try:
        current_state = current_link.lstat()
    except OSError as error:
        raise ManagedSimcRuntimeError("SIMC_UNAVAILABLE") from error
    if not stat.S_ISLNK(current_state.st_mode):
        raise ManagedSimcRuntimeError("SIMC_IDENTITY_INVALID")
    try:
        release_dir = current_link.resolve(strict=True)
        binary_path = raw_binary.resolve(strict=True)
    except OSError as error:
        raise ManagedSimcRuntimeError("SIMC_UNAVAILABLE") from error
    if binary_path != release_dir / "simc" or release_dir.parent.name != "releases":
        raise ManagedSimcRuntimeError("SIMC_IDENTITY_INVALID")
    source_commit = _read_runtime_metadata(release_dir / ".commit")
    recorded_sha = _read_runtime_metadata(release_dir / "binary.sha256")
    source_archive_identity = _read_runtime_metadata(release_dir / "source-archive.sha256")
    if (
        _COMMIT.fullmatch(source_commit) is None
        or release_dir.name != source_commit
        or _SHA256.fullmatch(recorded_sha) is None
        or _SOURCE_ARCHIVE_IDENTITY.fullmatch(source_archive_identity) is None
    ):
        raise ManagedSimcRuntimeError("SIMC_IDENTITY_INVALID")
    try:
        before = binary_path.stat()
        if not stat.S_ISREG(before.st_mode) or not os.access(binary_path, os.X_OK):
            raise ManagedSimcRuntimeError("SIMC_UNAVAILABLE")
        actual_sha = _cached_binary_sha256(
            str(binary_path),
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        )
        after = binary_path.stat()
    except ManagedSimcRuntimeError:
        raise
    except OSError as error:
        raise ManagedSimcRuntimeError("SIMC_UNAVAILABLE") from error
    if (
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    ):
        raise ManagedSimcRuntimeError("SIMC_IDENTITY_INVALID")
    if actual_sha != recorded_sha:
        raise ManagedSimcRuntimeError("SIMC_IDENTITY_MISMATCH")
    return ManagedSimcRuntimeIdentity(
        binary_path=binary_path,
        source_commit=source_commit,
        binary_sha256=actual_sha,
        runtime_revision=f"simc:managed:{source_commit}:{actual_sha}",
    )


def runtime_revision_matches_identity(
    runtime_revision: str,
    identity: ManagedSimcRuntimeIdentity,
) -> bool:
    value = str(runtime_revision or "").strip()
    if value == identity.runtime_revision:
        return True
    return re.fullmatch(
        rf"simc:[^:\s]{{1,32}}:{re.escape(identity.source_commit)}:{re.escape(identity.binary_sha256)}",
        value,
    ) is not None


@dataclass(frozen=True)
class SimcRuntimeCapabilities:
    runtime_revision: str
    compiler_revision: str
    supported_specs: frozenset[tuple[str, str]]

    def supports(self, class_key: str, spec_key: str) -> bool:
        return (class_key, spec_key) in self.supported_specs or ("*", "*") in self.supported_specs

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "SimcRuntimeCapabilities":
        source_env = os.environ if env is None else env
        raw_specs = source_env.get("WOW_SIMC_SUPPORTED_SPECS", "").strip()
        supported: set[tuple[str, str]] = set()
        for value in raw_specs.split(","):
            parts = [part.strip().lower() for part in value.split(":")]
            if len(parts) == 2 and all(parts):
                supported.add((parts[0], parts[1]))
        runtime_revision = source_env.get("WOW_SIMC_RUNTIME_REVISION", "").strip()
        managed_path = Path(source_env.get("WOW_SIMC_BIN", "/opt/wow-simc/current/simc").strip()).parent
        managed_runtime_expected = (
            source_env.get("WOW_APP_ENV", "").strip() in {"candidate", "production"}
            or managed_path.is_symlink()
        )
        try:
            managed_identity = inspect_managed_simc_runtime(source_env)
        except ManagedSimcRuntimeError:
            managed_identity = None
        if managed_runtime_expected and managed_identity is None:
            runtime_revision = ""
        elif managed_identity is not None:
            if runtime_revision and not runtime_revision_matches_identity(runtime_revision, managed_identity):
                runtime_revision = ""
            elif not runtime_revision:
                runtime_revision = managed_identity.runtime_revision
        if not runtime_revision:
            if not managed_runtime_expected:
                state_path = source_env.get(
                    "WOW_SIMC_VERSION_FILE",
                    "/var/lib/chickenbro/simc-version.json",
                ).strip()
                try:
                    state = json.loads(Path(state_path).read_text(encoding="utf-8"))
                    runtime_revision = str(state.get("simcRuntimeRevision") or "").strip()
                except (OSError, TypeError, ValueError, UnicodeError):
                    runtime_revision = ""
        return cls(
            runtime_revision=runtime_revision,
            compiler_revision=source_env.get(
                "WOW_SIMC_COMPILER_REVISION",
                "chickenbro-simc-compiler-v1",
            ).strip(),
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
        missing_fields = set(
            missing_snapshot_fields(raw_snapshot)
            if isinstance(raw_snapshot, Mapping)
            else REQUIRED_CHARACTER_PATHS
        )
        gear_state = raw_snapshot.get("gearState") if isinstance(raw_snapshot, Mapping) else {}
        gear_state = gear_state if isinstance(gear_state, Mapping) else {}
        unequipped_slots = {
            str(slot)
            for slot in gear_state.get("unequippedSlots", ())
            if isinstance(slot, str)
        }

        checks: dict[str, bool] = {}
        blockers: list[str] = []

        def require(name: str, condition: bool, blocker: str) -> None:
            checks[name] = bool(condition)
            if not condition:
                blockers.append(blocker)

        character_requirements = {
            "character.name": ("identity", "CHARACTER_IDENTITY_MISSING"),
            "character.region": ("region", "CHARACTER_REGION_MISSING"),
            "character.realm": ("realm", "CHARACTER_REALM_MISSING"),
            "character.level": ("level", "CHARACTER_LEVEL_MISSING"),
            "character.classKey": ("class", "CHARACTER_CLASS_MISSING"),
            "character.specKey": ("spec", "CHARACTER_SPEC_MISSING"),
            "character.raceKey": ("race", "CHARACTER_RACE_MISSING"),
        }
        for path in REQUIRED_CHARACTER_PATHS:
            check_name, blocker = character_requirements[path]
            require(check_name, path not in missing_fields, blocker)

        for slot in REQUIRED_GEAR_SLOTS:
            item = gear.get(slot)
            if slot == "off_hand" and item is None and slot in unequipped_slots:
                checks[f"gear.{slot}"] = True
                continue
            valid_item = (
                isinstance(item, Mapping)
                and f"gear.{slot}" not in missing_fields
                and f"gear.{slot}.itemId" not in missing_fields
            )
            require(f"gear.{slot}", valid_item, f"GEAR_{slot.upper()}_MISSING")
            if valid_item:
                require(
                    f"gear.{slot}.itemLevel",
                    f"gear.{slot}.itemLevel" not in missing_fields,
                    f"GEAR_{slot.upper()}_ITEMLEVEL_MISSING",
                )
                for semantic in ("bonusIds", "gems", "enchant"):
                    require(
                        f"gear.{slot}.{semantic}",
                        f"gear.{slot}.{semantic}" not in missing_fields,
                        f"GEAR_{slot.upper()}_{semantic.upper()}_MISSING",
                    )

        require("talents", "talents.loadout" not in missing_fields, "TALENTS_MISSING")
        require("talentRuntime", talent_catalog_matches_runtime(raw_provenance, runtime_capabilities.runtime_revision),
                "TALENTS_INVALID")
        provenance_present = (
            isinstance(raw_provenance, Mapping)
            and bool(str(raw_provenance.get("sourceUrl") or "").strip())
            and bool(str(raw_provenance.get("sourceRevision") or "").strip())
            and bool(str(raw_provenance.get("fetchedAt") or "").strip())
        )
        require("provenance", provenance_present, "SOURCE_PROVENANCE_MISSING")
        if provenance_present:
            source_revision = raw_provenance.get("sourceRevision")
            require(
                "sourceRevision",
                isinstance(source_revision, str) and 1 <= len(source_revision) <= 160,
                "SOURCE_PROVENANCE_INVALID",
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
            runtime_capabilities.compiler_revision in {"chickenbro-simc-compiler-v1", "chickenbro-simc-compiler-v2", "chickenbro-simc-compiler-v3"},
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
    "ManagedSimcRuntimeError",
    "ManagedSimcRuntimeIdentity",
    "ReadinessReport",
    "SimcReadinessValidator",
    "SimcRuntimeCapabilities",
    "inspect_managed_simc_runtime",
    "runtime_revision_matches_identity",
)

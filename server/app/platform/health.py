import hashlib
import importlib.util
import os
import re
import shutil
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal

from server.app.integrations.warcraftlogs import warcraftlogs_credentials_state
from server.app.platform.config import AppSettings
from server.app.platform.postgres import PostgresConnectionFactory
from server.app.platform.worker_heartbeat import WorkerHeartbeatError, read_worker_heartbeat
from server.app.simulation.readiness import (
    ManagedSimcRuntimeError,
    SimcRuntimeCapabilities,
    inspect_managed_simc_runtime,
    runtime_revision_matches_identity,
)


ComponentStatus = Literal["ready", "partial", "blocked", "unconfigured"]
OverallReadinessStatus = Literal["ready", "partial", "blocked"]
_COMPONENT_STATUSES = {"ready", "partial", "blocked", "unconfigured"}
_CODEX_REVISION = re.compile(r"^codex:sha256:([0-9a-f]{64})$")


@dataclass(frozen=True)
class ComponentState:
    status: ComponentStatus
    code: str

    def __post_init__(self) -> None:
        if self.status not in _COMPONENT_STATUSES:
            raise ValueError("component status is not supported")
        if not isinstance(self.code, str):
            raise ValueError("component code must be a string")


class ReadinessRegistry:
    def __init__(self, probes: Mapping[str, Callable[[], ComponentState]]):
        self._probes = dict(probes)

    def check_all(self) -> Mapping[str, ComponentState]:
        result: dict[str, ComponentState] = {}
        for name, probe in self._probes.items():
            try:
                state = probe()
                if not isinstance(state, ComponentState):
                    raise TypeError("readiness probe must return ComponentState")
                result[name] = state
            except Exception:
                result[name] = ComponentState("blocked", "PROBE_FAILED")
        return result

    @staticmethod
    def overall_status(states: Mapping[str, ComponentState]) -> OverallReadinessStatus:
        if not states:
            return "partial"
        if any(state.status == "blocked" for state in states.values()):
            return "blocked"
        if all(state.status == "ready" for state in states.values()):
            return "ready"
        return "partial"


def database_probe(factory: PostgresConnectionFactory) -> Callable[[], ComponentState]:
    def probe() -> ComponentState:
        try:
            with factory.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute("SELECT 1")
                    row = cursor.fetchone()
                    value = row[0] if isinstance(row, (tuple, list)) else row
                    if value != 1:
                        raise RuntimeError("database probe returned an unexpected value")
        except Exception:
            return ComponentState("blocked", "DATABASE_UNAVAILABLE")
        return ComponentState("ready", "")

    return probe


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def worker_probe(
    settings: AppSettings,
    *,
    now: Callable[[], datetime] = _utc_now,
) -> ComponentState:
    expected_worker_id = {
        "candidate": "chickenbro-simc-candidate-worker",
        "production": "chickenbro-simc-worker",
    }.get(settings.environment)
    try:
        read_worker_heartbeat(
            path=(
                settings.worker_heartbeat_path
                or f"/var/lib/chickenbro/{settings.environment}-worker-heartbeat.json"
            ),
            expected_environment=settings.environment,
            expected_worker_id=expected_worker_id,
            max_age_seconds=settings.worker_heartbeat_ttl_seconds,
            now=now,
        )
    except WorkerHeartbeatError as error:
        if error.code == "WORKER_HEARTBEAT_MISSING" and settings.environment in {"local", "test"}:
            return ComponentState("unconfigured", "WORKER_NOT_CONFIGURED")
        return ComponentState("blocked", error.code)
    return ComponentState("ready", "")


@lru_cache(maxsize=16)
def _cached_executable_sha256(
    path_text: str,
    device: int,
    inode: int,
    size: int,
    modified_ns: int,
) -> str:
    path = Path(path_text)
    digest = hashlib.sha256()
    with path.open("rb") as source:
        opened = os.fstat(source.fileno())
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != (
            device,
            inode,
            size,
            modified_ns,
        ):
            raise OSError("executable changed during identity check")
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
        closed = os.fstat(source.fileno())
    if (closed.st_dev, closed.st_ino, closed.st_size, closed.st_mtime_ns) != (
        device,
        inode,
        size,
        modified_ns,
    ):
        raise OSError("executable changed during identity check")
    return digest.hexdigest()


def _executable_sha256(command: str, env: Mapping[str, str]) -> str:
    raw = str(command or "").strip()
    if not raw:
        raise OSError("executable is not configured")
    candidate = raw if Path(raw).is_absolute() else shutil.which(raw, path=env.get("PATH"))
    if not candidate:
        raise OSError("executable is unavailable")
    path = Path(candidate).resolve(strict=True)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or not os.access(path, os.X_OK):
        raise OSError("executable is unavailable")
    digest = _cached_executable_sha256(
        str(path),
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    after = path.stat()
    if (
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    ):
        raise OSError("executable changed during identity check")
    return digest


def codex_probe(env: Mapping[str, str] | None = None) -> ComponentState:
    source_env = os.environ if env is None else env
    enabled = source_env.get("WOW_CHICKENBRO_CODEX_ENABLED", "0").strip()
    if enabled in {"", "0"}:
        return ComponentState("unconfigured", "CODEX_NOT_CONFIGURED")
    if enabled != "1":
        return ComponentState("blocked", "CODEX_CONFIGURATION_INVALID")
    revision = source_env.get("WOW_CODEX_RUNTIME_REVISION", "").strip()
    match = _CODEX_REVISION.fullmatch(revision)
    if match is None:
        return ComponentState("blocked", "CODEX_IDENTITY_INVALID")
    try:
        actual_sha = _executable_sha256(source_env.get("WOW_CODEX_BIN", "codex"), source_env)
    except (OSError, ValueError):
        return ComponentState("blocked", "CODEX_UNAVAILABLE")
    if actual_sha != match.group(1):
        return ComponentState("blocked", "CODEX_IDENTITY_MISMATCH")
    return ComponentState("ready", "")


def raiderio_probe(
    *,
    module_available: Callable[[str], bool] | None = None,
) -> ComponentState:
    available = module_available or (lambda name: importlib.util.find_spec(name) is not None)
    try:
        if not available("httpx"):
            return ComponentState("blocked", "RAIDERIO_DEPENDENCY_MISSING")
    except Exception:
        return ComponentState("blocked", "RAIDERIO_DEPENDENCY_MISSING")
    return ComponentState("ready", "")


def warcraftlogs_probe(env: Mapping[str, str] | None = None) -> ComponentState:
    source_env = os.environ if env is None else env
    state = warcraftlogs_credentials_state(source_env)
    if state["configured"] and state["mode"] == "v2_oauth":
        return ComponentState("ready", "")
    has_client_id = bool(source_env.get("WOW_WARCRAFTLOGS_CLIENT_ID", "").strip())
    has_client_secret = bool(source_env.get("WOW_WARCRAFTLOGS_CLIENT_SECRET", "").strip())
    if has_client_id or has_client_secret:
        return ComponentState("blocked", "WARCRAFTLOGS_CREDENTIALS_INVALID")
    return ComponentState("unconfigured", "WARCRAFTLOGS_NOT_CONFIGURED")


def simc_probe(env: Mapping[str, str] | None = None) -> ComponentState:
    source_env = os.environ if env is None else env
    if not source_env.get("WOW_SIMC_SUPPORTED_SPECS", "").strip():
        return ComponentState("unconfigured", "SIMC_NOT_CONFIGURED")
    try:
        identity = inspect_managed_simc_runtime(source_env)
    except ManagedSimcRuntimeError as error:
        return ComponentState("blocked", error.code)
    capabilities = SimcRuntimeCapabilities.from_env(source_env)
    if (
        not capabilities.runtime_revision
        or not capabilities.compiler_revision
        or not capabilities.supported_specs
        or not runtime_revision_matches_identity(capabilities.runtime_revision, identity)
    ):
        return ComponentState("blocked", "SIMC_IDENTITY_MISMATCH")
    return ComponentState("ready", "")


def default_readiness_registry(
    settings: AppSettings,
    env: Mapping[str, str] | None = None,
) -> ReadinessRegistry:
    source_env = os.environ if env is None else env
    database = database_probe(PostgresConnectionFactory(settings))
    qq = (
        ComponentState("ready", "")
        if settings.qq_appid and settings.qq_app_key and settings.qq_redirect_uri
        else ComponentState("unconfigured", "QQ_NOT_CONFIGURED")
    )
    return ReadinessRegistry({
        "database": database,
        "worker": lambda: worker_probe(settings),
        "codex": lambda: codex_probe(source_env),
        "raiderio": raiderio_probe,
        "warcraftlogs": lambda: warcraftlogs_probe(source_env),
        "simc": lambda: simc_probe(source_env),
        "qq_connect": lambda: qq,
    })

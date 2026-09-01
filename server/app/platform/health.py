from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from server.app.platform.config import AppSettings
from server.app.platform.postgres import PostgresConnectionFactory


ComponentStatus = Literal["ready", "partial", "blocked", "unconfigured"]
OverallReadinessStatus = Literal["ready", "partial", "blocked"]
_COMPONENT_STATUSES = {"ready", "partial", "blocked", "unconfigured"}


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


def default_readiness_registry(settings: AppSettings) -> ReadinessRegistry:
    database = database_probe(PostgresConnectionFactory(settings))
    return ReadinessRegistry({
        "database": database,
        "worker": lambda: ComponentState("unconfigured", "WORKER_NOT_CONFIGURED"),
        "codex": lambda: ComponentState("unconfigured", "CODEX_NOT_CONFIGURED"),
        "raiderio": lambda: ComponentState("unconfigured", "RAIDERIO_NOT_CONFIGURED"),
        "warcraftlogs": lambda: ComponentState("unconfigured", "WARCRAFTLOGS_NOT_CONFIGURED"),
        "simc": lambda: ComponentState("unconfigured", "SIMC_NOT_CONFIGURED"),
    })

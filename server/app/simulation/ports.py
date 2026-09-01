from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from server.app.simulation.domain import (
    SimulationJob,
    SimulationResult,
    SourceSnapshot,
)


class CharacterSourcePort(Protocol):
    def resolve(self, source_url: str) -> SourceSnapshot:
        raise NotImplementedError


class SnapshotRepository(Protocol):
    def save(self, snapshot: SourceSnapshot) -> None:
        raise NotImplementedError

    def list_for_user(self, user_id: UUID) -> Sequence[SourceSnapshot]:
        raise NotImplementedError


class SimulationJobRepository(Protocol):
    def save(self, job: SimulationJob) -> None:
        raise NotImplementedError

    def get_for_user(self, user_id: UUID, job_id: UUID) -> SimulationJob | None:
        raise NotImplementedError


class SimulationReadPort(Protocol):
    def result_for_user(self, user_id: UUID, result_id: UUID) -> SimulationResult | None:
        raise NotImplementedError


class SimcCompilerPort(Protocol):
    def compile(self, snapshot: SourceSnapshot, scenario_hash: str) -> tuple[str, str]:
        raise NotImplementedError

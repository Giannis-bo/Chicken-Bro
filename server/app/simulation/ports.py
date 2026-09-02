from collections.abc import Sequence
from datetime import datetime
from typing import Mapping, Protocol
from uuid import UUID

from server.app.simulation.domain import (
    SimulationJob,
    SimulationResult,
    SourceSnapshot,
)
from server.app.simulation.compiler import CompiledSimcInput
from server.app.simulation.readiness import ReadinessReport, SimcRuntimeCapabilities
from server.app.simulation.worker import RawSimulationExecution


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

    def list_jobs(
        self,
        user_id: UUID,
        boundary: tuple[datetime, UUID] | None,
        limit: int,
    ) -> Sequence[SimulationJob]:
        raise NotImplementedError


class SimulationReadPort(Protocol):
    def result_for_user(self, user_id: UUID, result_id: UUID) -> SimulationResult | None:
        raise NotImplementedError


class SimcCompilerPort(Protocol):
    def compile(self, snapshot: SourceSnapshot, scenario: Mapping[str, object]) -> CompiledSimcInput:
        raise NotImplementedError


class SimcReadinessPort(Protocol):
    def validate(self, snapshot: SourceSnapshot, runtime_capabilities: SimcRuntimeCapabilities) -> ReadinessReport:
        raise NotImplementedError


class SimulationCraftPort(Protocol):
    def run(self, compiled_input: CompiledSimcInput, runtime_revision: str) -> RawSimulationExecution:
        raise NotImplementedError

import math
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from uuid import UUID, uuid4

from server.app.simulation.compiler import SimcCompileError, SimcProfileCompiler
from server.app.simulation.domain import SimulationJobStatus, SimulationResult
from server.app.simulation.readiness import ReadinessReport, SimcReadinessValidator, SimcRuntimeCapabilities
from server.app.worker.leases import JobLease
from server.app.worker.handlers import RetryableJobError


class SimulationWorkerError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False):
        self.code = code
        self.retryable = retryable
        super().__init__(code)


@dataclass(frozen=True)
class RawSimulationExecution:
    return_code: int
    stdout: str
    stderr: str
    runtime_revision: str
    timed_out: bool = False


class SimulationCraftPort(Protocol):
    def run(self, compiled_input: Any, runtime_revision: str) -> RawSimulationExecution:
        raise NotImplementedError


class LocalSimulationCraftPort:
    """Execute the already-installed cloud SimC runtime; never downloads or builds it."""

    def __init__(
        self,
        *,
        binary: str | None = None,
        runtime_revision: str | None = None,
        timeout_seconds: int = 45,
        runner: Callable[..., Any] = subprocess.run,
    ):
        self._binary = binary or os.environ.get("WOW_SIMC_BIN", "/opt/wow-simc/current/simc")
        self._runtime_revision = runtime_revision or os.environ.get("WOW_SIMC_RUNTIME_REVISION", "").strip()
        self._timeout_seconds = max(1, int(timeout_seconds))
        self._runner = runner

    def run(self, compiled_input: Any, runtime_revision: str) -> RawSimulationExecution:
        if not runtime_revision or not self._runtime_revision or runtime_revision != self._runtime_revision:
            raise SimulationWorkerError("SIMC_RUNTIME_REVISION_STALE")
        binary = self._binary
        if not (os.path.isfile(binary) and os.access(binary, os.X_OK)):
            binary = shutil.which(binary) or ""
        if not binary:
            raise SimulationWorkerError("SIMC_UNAVAILABLE", retryable=True)
        try:
            completed = self._runner(
                [binary, "-"],
                input=compiled_input.profile,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise SimulationWorkerError("SIMC_TIMEOUT", retryable=True) from None
        except OSError:
            raise SimulationWorkerError("SIMC_UNAVAILABLE", retryable=True) from None
        return RawSimulationExecution(
            return_code=int(completed.returncode),
            stdout=str(completed.stdout or "")[:12000],
            stderr=str(completed.stderr or "")[:4000],
            runtime_revision=runtime_revision,
        )


@dataclass(frozen=True)
class SemanticSimulationMetric:
    name: str
    value: float


class SimulationResultParser:
    _METRIC_PATTERN = re.compile(r"\b(DPS|HPS)\s*(?:=|:)\s*([0-9]+(?:\.[0-9]+)?)\b", re.IGNORECASE)

    def parse(self, execution: RawSimulationExecution) -> SemanticSimulationMetric:
        if execution.timed_out:
            raise SimulationWorkerError("SIMC_TIMEOUT", retryable=True)
        if execution.return_code != 0:
            raise SimulationWorkerError("SIMC_EXECUTION_FAILED")
        matches = list(self._METRIC_PATTERN.finditer(execution.stdout or ""))
        if not matches:
            raise SimulationWorkerError("SIMC_METRIC_MISSING")
        selected = matches[-1]
        value = float(selected.group(2))
        if not math.isfinite(value) or value <= 0:
            raise SimulationWorkerError("SIMC_METRIC_INVALID")
        return SemanticSimulationMetric(name=selected.group(1).lower(), value=value)


class SimulationWorker:
    def __init__(
        self,
        *,
        repository: object,
        simc: SimulationCraftPort,
        worker_id: str,
        compiler: SimcProfileCompiler,
        readiness_validator: SimcReadinessValidator,
        runtime_capabilities: SimcRuntimeCapabilities,
        result_parser: SimulationResultParser,
        clock: Callable[[], datetime] | None = None,
    ):
        self._repository = repository
        self._simc = simc
        self._worker_id = worker_id
        self._compiler = compiler
        self._readiness_validator = readiness_validator
        self._runtime_capabilities = runtime_capabilities
        self._result_parser = result_parser
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def handle(self, lease: JobLease) -> SimulationJobStatus:
        if lease.domain != "simc" or lease.command_type != "run_simulation" or lease.aggregate_id not in {None, lease.id}:
            raise SimulationWorkerError("JOB_PAYLOAD_INVALID")
        job = self._repository.get_job_by_id(lease.id)
        if job is None or job.id != lease.id:
            raise SimulationWorkerError("SIMULATION_NOT_FOUND")
        if lease.aggregate_id is not None and lease.aggregate_id != job.id:
            raise SimulationWorkerError("JOB_PAYLOAD_INVALID")
        self._repository.update_job(job.user_id, job.id, SimulationJobStatus.RUNNING, "")
        attempt_id = self._repository.start_attempt(
            job.id,
            job.user_id,
            self._worker_id,
            lease.attempt,
            self._utc_now(),
        )
        try:
            compiled = self._compile_for_job(job, lease.payload)
            execution = self._simc.run(compiled, job.runtime_revision)
            if execution.runtime_revision != job.runtime_revision:
                raise SimulationWorkerError("SIMC_RUNTIME_REVISION_STALE")
            metric = self._result_parser.parse(execution)
            result = SimulationResult(
                id=uuid4(),
                job_id=job.id,
                user_id=job.user_id,
                profile_sha256=compiled.profile_sha256,
                result={
                    "metricName": metric.name,
                    "metricValue": metric.value,
                    "provenance": {
                        "snapshotId": str(job.snapshot_id),
                        "sourceUrl": str(compiled.provenance.get("sourceUrl", "")),
                        "sourceRevision": str(compiled.provenance.get("sourceRevision", "")),
                        "sourceRawSha256": str(compiled.provenance.get("sourceRawSha256", "")),
                        "profileSha256": compiled.profile_sha256,
                        "compilerRevision": compiled.compiler_revision,
                        "runtimeRevision": compiled.runtime_revision,
                    },
                },
                primary_metric_name=metric.name,
                primary_metric_value=metric.value,
                compiler_revision=compiled.compiler_revision,
                runtime_revision=compiled.runtime_revision,
                created_at=self._utc_now(),
            )
            self._repository.save_result(result)
            self._repository.finish_attempt(
                attempt_id,
                return_code=execution.return_code,
                diagnostic="succeeded",
                finished_at=self._utc_now(),
            )
            self._repository.update_job(job.user_id, job.id, SimulationJobStatus.SUCCEEDED, "")
            return SimulationJobStatus.SUCCEEDED
        except SimulationWorkerError as error:
            return self._record_failure(job, lease, attempt_id, error)
        except SimcCompileError as error:
            return self._record_failure(job, lease, attempt_id, SimulationWorkerError(error.code))
        except Exception:
            return self._record_failure(job, lease, attempt_id, SimulationWorkerError("SIMC_EXECUTION_FAILED"))

    def _compile_for_job(self, job: Any, payload: Mapping[str, object]) -> Any:
        snapshot_id = payload.get("snapshotId")
        try:
            parsed_snapshot_id = snapshot_id if isinstance(snapshot_id, UUID) else UUID(str(snapshot_id))
        except (TypeError, ValueError):
            raise SimulationWorkerError("JOB_PAYLOAD_INVALID") from None
        if parsed_snapshot_id != job.snapshot_id:
            raise SimulationWorkerError("JOB_PAYLOAD_INVALID")
        snapshot = self._repository.get_snapshot(job.user_id, parsed_snapshot_id)
        if snapshot is None:
            raise SimulationWorkerError("SNAPSHOT_NOT_FOUND")
        report = self._readiness_validator.validate(snapshot, self._runtime_capabilities)
        if not report.ready:
            raise SimulationWorkerError("SNAPSHOT_NOT_READY")
        scenario = payload.get("scenario")
        compiled = self._compiler.compile(snapshot, scenario if isinstance(scenario, Mapping) else {})
        if compiled.compiler_revision != job.compiler_revision or compiled.runtime_revision != job.runtime_revision:
            raise SimulationWorkerError("SIMC_RUNTIME_REVISION_STALE")
        expected_scenario_hash = str(payload.get("scenarioHash") or "")
        if expected_scenario_hash and expected_scenario_hash != compiled.scenario_hash:
            raise SimulationWorkerError("JOB_PAYLOAD_INVALID")
        return compiled

    def _record_failure(
        self,
        job: Any,
        lease: JobLease,
        attempt_id: UUID,
        error: SimulationWorkerError,
    ) -> SimulationJobStatus:
        terminal = not error.retryable or lease.attempt >= lease.max_attempts
        status = SimulationJobStatus.FAILED if terminal else SimulationJobStatus.QUEUED
        self._repository.finish_attempt(
            attempt_id,
            return_code=None,
            diagnostic=error.code,
            finished_at=self._utc_now(),
        )
        self._repository.update_job(job.user_id, job.id, status, error.code)
        if error.retryable and not terminal:
            raise RetryableJobError(error.code)
        return status

    def _utc_now(self) -> datetime:
        value = self._clock()
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


__all__ = (
    "LocalSimulationCraftPort",
    "RawSimulationExecution",
    "SemanticSimulationMetric",
    "SimulationCraftPort",
    "SimulationResultParser",
    "SimulationWorker",
    "SimulationWorkerError",
)

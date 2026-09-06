import math
import os
import re
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol
from uuid import UUID, uuid4

from server.app.simulation.compiler import SimcCompileError, SimcProfileCompiler
from server.app.simulation.domain import SimulationJobStatus, SimulationResult
from server.app.simulation.readiness import (
    ManagedSimcRuntimeError, SimcReadinessValidator, SimcRuntimeCapabilities,
    inspect_managed_simc_runtime, runtime_revision_matches_identity,
)
from server.app.simulation.report import MAX_REPORT_BYTES, SimulationReportError, normalize_simc_report
from server.app.worker.handlers import RetryableJobError
from server.app.worker.leases import JobLease, LostLeaseError


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
    report_json: str | bytes | None = None
    requires_json: bool = False


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
        try:
            identity = inspect_managed_simc_runtime({"WOW_SIMC_BIN": self._binary})
        except ManagedSimcRuntimeError as error:
            raise SimulationWorkerError(error.code, retryable=error.code == "SIMC_UNAVAILABLE") from None
        if not runtime_revision_matches_identity(runtime_revision, identity):
            raise SimulationWorkerError("SIMC_RUNTIME_REVISION_STALE")
        # Pin the verified release target instead of following a movable current link.
        binary = str(identity.binary_path)
        try:
            with tempfile.TemporaryDirectory(prefix="chickenbro-simc-") as private_dir:
                output = Path(private_dir) / "report.json"
                completed = self._runner(
                    [binary, "-", f"json={output},full_states=0", "report_details=1"],
                    input=compiled_input.profile,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    timeout=self._timeout_seconds,
                    check=False,
                    cwd=private_dir,
                )
                try:
                    after_identity = inspect_managed_simc_runtime({"WOW_SIMC_BIN": self._binary})
                except ManagedSimcRuntimeError:
                    raise SimulationWorkerError("SIMC_RUNTIME_REVISION_STALE") from None
                if after_identity != identity:
                    raise SimulationWorkerError("SIMC_RUNTIME_REVISION_STALE")
                report_json = None
                if int(completed.returncode) == 0:
                    try:
                        if output.is_symlink() or not output.is_file() or output.stat().st_size > MAX_REPORT_BYTES:
                            raise SimulationWorkerError("SIMC_REPORT_INVALID")
                        with output.open("rb") as report_file:
                            report_json = report_file.read(MAX_REPORT_BYTES + 1)
                        if len(report_json) > MAX_REPORT_BYTES:
                            raise SimulationWorkerError("SIMC_REPORT_INVALID")
                    except OSError:
                        raise SimulationWorkerError("SIMC_REPORT_INVALID") from None
        except subprocess.TimeoutExpired:
            raise SimulationWorkerError("SIMC_TIMEOUT", retryable=True) from None
        except OSError:
            raise SimulationWorkerError("SIMC_UNAVAILABLE", retryable=True) from None
        return RawSimulationExecution(
            return_code=int(completed.returncode),
            stdout=str(completed.stdout or "")[:12000],
            stderr=str(completed.stderr or "")[:4000],
            runtime_revision=runtime_revision,
            report_json=report_json,
            requires_json=True,
        )


@dataclass(frozen=True)
class SemanticSimulationMetric:
    name: str
    value: float
    error: float | None = None
    error_pct: float | None = None
    report: dict | None = None


class SimulationResultParser:
    _METRIC_PATTERN = re.compile(
        r"^[ \t]*(DPS|HPS)[ \t]*(?:=|:)[ \t]*"
        r"([+-]?(?:(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?|nan|inf(?:inity)?))(?=\s|$)",
        re.IGNORECASE | re.MULTILINE,
    )
    _ACTOR_PATTERN = re.compile(r"^\s*Player:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
    _PLACEHOLDER_ACTOR = re.compile(
        r"^(?:none|null|unknown|unnamed)\b|\b(?:actor|race|class|spec)\s*=\s*(?:none|null|unknown|0)\b",
        re.IGNORECASE,
    )
    _FATAL_DIAGNOSTIC = re.compile(
        r"\bfatal(?:\s+error)?\b|\b(?:unable|failed)\s+to\s+(?:initialize|create|parse)\b",
        re.IGNORECASE,
    )

    def parse(
        self,
        execution: RawSimulationExecution,
        *,
        expected_actor: str,
    ) -> SemanticSimulationMetric:
        if execution.timed_out:
            raise SimulationWorkerError("SIMC_TIMEOUT", retryable=True)
        if execution.return_code != 0:
            raise SimulationWorkerError("SIMC_EXECUTION_FAILED")
        combined_diagnostics = "\n".join((execution.stdout or "", execution.stderr or ""))
        if self._FATAL_DIAGNOSTIC.search(combined_diagnostics):
            raise SimulationWorkerError("SIMC_FATAL_DIAGNOSTIC")
        if execution.requires_json or execution.report_json is not None:
            try:
                report = normalize_simc_report(execution.report_json, expected_actor=expected_actor)
            except SimulationReportError as error:
                raise SimulationWorkerError(error.code) from None
            metric = report["metric"]
            error = metric["error"]
            error_pct = error / metric["value"] * 100 if error is not None else None
            if error_pct is not None and not math.isfinite(error_pct):
                raise SimulationWorkerError("SIMC_REPORT_INVALID")
            return SemanticSimulationMetric(
                name=metric["name"], value=metric["value"], error=error,
                error_pct=error_pct,
                report=report,
            )
        actor_matches = list(self._ACTOR_PATTERN.finditer(execution.stdout or ""))
        actors = [match.group(1).strip() for match in actor_matches]
        normalized_expected_actor = str(expected_actor or "").strip().casefold()
        normalized_actor = actors[0].casefold() if len(actors) == 1 else ""
        if (
            not normalized_expected_actor
            or len(actors) != 1
            or self._PLACEHOLDER_ACTOR.search(actors[0])
            or not (
                normalized_actor == normalized_expected_actor
                or normalized_actor.startswith(normalized_expected_actor + " ")
            )
        ):
            raise SimulationWorkerError("SIMC_ACTOR_INVALID")
        # Only the player's summary immediately after its header is a metric.
        # Action/pet rows, targets and diagnostics must not replace that result.
        summary_lines = []
        for line in execution.stdout[actor_matches[0].end():].splitlines():
            if not line.strip():
                if summary_lines:
                    break
                continue
            if self._METRIC_PATTERN.match(line) is None:
                break
            summary_lines.append(line)
        summary = "\n".join(summary_lines)
        matches = list(self._METRIC_PATTERN.finditer(summary))
        if not matches:
            raise SimulationWorkerError("SIMC_METRIC_MISSING")
        selected = next((match for match in matches if match.group(1).lower() == "dps"), matches[0])
        value = float(selected.group(2))
        if not math.isfinite(value) or value <= 0:
            raise SimulationWorkerError("SIMC_METRIC_INVALID")
        name = selected.group(1).lower()
        metric_line = summary[selected.start():].splitlines()[0]
        # SimC report_text.cpp prints <metric>-Error=<absolute>/<percent>%.
        # Preserve only an unambiguous finite pair from that same summary row.
        number = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
        error_matches = list(re.finditer(
            rf"\b{name}-Error=({number})/({number})%(?=\s|$)", metric_line, re.IGNORECASE
        ))
        error = error_pct = None
        error_label_count = len(re.findall(rf"\b{name}-Error=", metric_line, re.IGNORECASE))
        if len(error_matches) == 1 and error_label_count == 1:
            raw_error, raw_pct = map(float, error_matches[0].groups())
            if math.isfinite(raw_error) and math.isfinite(raw_pct) and raw_error >= 0 and raw_pct >= 0:
                error, error_pct = raw_error, raw_pct
        return SemanticSimulationMetric(name=name, value=value, error=error, error_pct=error_pct)


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
        if lease.attempt > lease.max_attempts:
            try:
                exhausted_status = self._repository.exhaust_job_after_attempt_limit(
                    lease.id,
                    worker_id=self._worker_id,
                    finished_at=self._utc_now(),
                )
            except LostLeaseError as error:
                raise RetryableJobError("LEASE_LOST") from error
            except Exception as error:
                raise RetryableJobError("SIMC_PERSISTENCE_FAILED") from error
            if exhausted_status is None:
                raise SimulationWorkerError("SIMULATION_NOT_FOUND")
            return exhausted_status
        try:
            started = self._repository.begin_job_attempt(
                lease.id,
                worker_id=self._worker_id,
                attempt_number=lease.attempt,
                now=self._utc_now(),
            )
        except LostLeaseError as error:
            raise RetryableJobError("LEASE_LOST") from error
        except Exception as error:
            raise RetryableJobError("SIMC_PERSISTENCE_FAILED") from error
        if started is None:
            raise SimulationWorkerError("SIMULATION_NOT_FOUND")
        job, attempt_id = started
        if attempt_id is None:
            if job.status not in {
                SimulationJobStatus.SUCCEEDED,
                SimulationJobStatus.FAILED,
                SimulationJobStatus.CANCELLED,
            }:
                raise RetryableJobError("SIMC_PERSISTENCE_FAILED")
            return job.status
        execution: RawSimulationExecution | None = None
        try:
            compiled = self._compile_for_job(job, lease.payload)
            execution = self._simc.run(compiled, job.runtime_revision)
            if execution.runtime_revision != job.runtime_revision:
                raise SimulationWorkerError("SIMC_RUNTIME_REVISION_STALE")
            metric = self._result_parser.parse(execution, expected_actor=compiled.actor_name)
        except SimulationWorkerError as error:
            return self._record_failure(
                job,
                lease,
                attempt_id,
                error,
                return_code=execution.return_code if execution is not None else None,
            )
        except SimcCompileError as error:
            return self._record_failure(
                job,
                lease,
                attempt_id,
                SimulationWorkerError(error.code),
                return_code=None,
            )
        except Exception:
            return self._record_failure(
                job,
                lease,
                attempt_id,
                SimulationWorkerError("SIMC_EXECUTION_FAILED"),
                return_code=execution.return_code if execution is not None else None,
            )

        provenance = {
            "snapshotId": str(job.snapshot_id),
            "sourceRevision": str(compiled.provenance.get("sourceRevision", "")),
            "sourceRawSha256": str(compiled.provenance.get("sourceRawSha256", "")),
            "profileSha256": compiled.profile_sha256,
            "compilerRevision": compiled.compiler_revision,
            "runtimeRevision": compiled.runtime_revision,
            "scenarioHash": compiled.scenario_hash,
        }
        result = SimulationResult(
            id=uuid4(),
            job_id=job.id,
            user_id=job.user_id,
            profile_sha256=compiled.profile_sha256,
            result={
                "metricName": metric.name,
                "metricValue": metric.value,
                **({"report": metric.report} if metric.report is not None else {}),
                **({"metricError": metric.error, "metricErrorPct": metric.error_pct} if metric.error is not None else {}),
                "provenance": {
                    **provenance,
                    "sourceUrl": str(compiled.provenance.get("sourceUrl", "")),
                },
            },
            primary_metric_name=metric.name,
            primary_metric_value=metric.value,
            compiler_revision=compiled.compiler_revision,
            runtime_revision=compiled.runtime_revision,
            provenance=provenance,
            created_at=self._utc_now(),
        )
        try:
            return self._repository.complete_job_success(
                job,
                attempt_id,
                result,
                worker_id=self._worker_id,
                return_code=execution.return_code,
                finished_at=self._utc_now(),
            )
        except LostLeaseError as error:
            raise RetryableJobError("LEASE_LOST") from error
        except Exception as error:
            raise RetryableJobError("SIMC_PERSISTENCE_FAILED") from error

    def _compile_for_job(self, job: Any, payload: Mapping[str, object]) -> Any:
        if set(payload) != {
            "snapshotId",
            "scenario",
            "scenarioHash",
            "compilerRevision",
            "runtimeRevision",
        }:
            raise SimulationWorkerError("JOB_PAYLOAD_INVALID")
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
        if not isinstance(scenario, Mapping):
            raise SimulationWorkerError("JOB_PAYLOAD_INVALID")
        expected_scenario_hash = str(payload.get("scenarioHash") or "")
        expected_compiler_revision = str(payload.get("compilerRevision") or "")
        expected_runtime_revision = str(payload.get("runtimeRevision") or "")
        if (
            expected_scenario_hash != job.scenario_hash
            or expected_compiler_revision != job.compiler_revision
            or expected_runtime_revision != job.runtime_revision
        ):
            raise SimulationWorkerError("JOB_PAYLOAD_INVALID")
        compiler = self._compiler
        if (
            type(compiler) is SimcProfileCompiler
            and (job.compiler_revision, self._runtime_capabilities.compiler_revision) in {
                ("chickenbro-simc-compiler-v1", "chickenbro-simc-compiler-v2"),
                ("chickenbro-simc-compiler-v1", "chickenbro-simc-compiler-v3"),
                ("chickenbro-simc-compiler-v2", "chickenbro-simc-compiler-v3"),
            }
            and job.runtime_revision == self._runtime_capabilities.runtime_revision
        ):
            compiler = SimcProfileCompiler(capabilities=replace(
                self._runtime_capabilities, compiler_revision=job.compiler_revision
            ))
        compiled = compiler.compile(snapshot, scenario)
        if compiled.compiler_revision != job.compiler_revision or compiled.runtime_revision != job.runtime_revision:
            raise SimulationWorkerError("SIMC_RUNTIME_REVISION_STALE")
        if expected_scenario_hash != compiled.scenario_hash:
            raise SimulationWorkerError("JOB_PAYLOAD_INVALID")
        return compiled

    def _record_failure(
        self,
        job: Any,
        lease: JobLease,
        attempt_id: UUID,
        error: SimulationWorkerError,
        *,
        return_code: int | None,
    ) -> SimulationJobStatus:
        terminal = not error.retryable or lease.attempt >= lease.max_attempts
        status = SimulationJobStatus.FAILED if terminal else SimulationJobStatus.QUEUED
        try:
            committed_status = self._repository.complete_job_failure(
                job,
                attempt_id,
                worker_id=self._worker_id,
                status=status,
                error_code=error.code,
                return_code=return_code,
                finished_at=self._utc_now(),
            )
        except LostLeaseError as lease_error:
            raise RetryableJobError("LEASE_LOST") from lease_error
        except Exception as persistence_error:
            raise RetryableJobError("SIMC_PERSISTENCE_FAILED") from persistence_error
        if committed_status is SimulationJobStatus.QUEUED and error.retryable and not terminal:
            raise RetryableJobError(error.code)
        return committed_status

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

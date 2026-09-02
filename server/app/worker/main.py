import argparse
import logging
import os
import re
import time
from collections.abc import Callable

from server.app.platform.config import AppSettings
from server.app.platform.postgres import PostgresConnectionFactory
from server.app.simulation.compiler import SimcProfileCompiler
from server.app.simulation.readiness import SimcReadinessValidator, SimcRuntimeCapabilities
from server.app.simulation.repository import PostgresSimulationRepository
from server.app.simulation.worker import LocalSimulationCraftPort, SimulationResultParser, SimulationWorker
from server.app.worker.handlers import HandlerRegistry, RetryableJobError, UnknownJobHandler
from server.app.worker.leases import JobLease, PostgresJobQueue


LOGGER = logging.getLogger(__name__)
_WORKER_ID = re.compile(r"[a-zA-Z0-9._:-]{1,64}\Z")


class Worker:
    def __init__(
        self,
        *,
        queue: PostgresJobQueue,
        handlers: HandlerRegistry,
        worker_id: str,
        lease_seconds: int = 30,
        poll_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if _WORKER_ID.fullmatch(worker_id) is None:
            raise ValueError("worker_id must match [a-zA-Z0-9._:-]{1,64}")
        if not 1 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 1 and 3600")
        if not 0.1 <= poll_seconds <= 30:
            raise ValueError("poll_seconds must be between 0.1 and 30")
        self.queue = queue
        self.handlers = handlers
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.poll_seconds = poll_seconds
        self.sleep = sleep

    def run_once(self) -> bool:
        lease = self.queue.claim(worker_id=self.worker_id, lease_seconds=self.lease_seconds)
        if lease is None:
            return False
        try:
            handler = self.handlers.resolve(lease.domain, lease.command_type)
            handler(lease)
        except UnknownJobHandler:
            self.queue.fail(
                lease.id,
                worker_id=self.worker_id,
                error_code="UNKNOWN_JOB_HANDLER",
                retryable=False,
            )
        except RetryableJobError as error:
            self.queue.fail(
                lease.id,
                worker_id=self.worker_id,
                error_code=error.code,
                retryable=True,
            )
        except Exception as error:
            LOGGER.warning(
                "v2 worker handler failed",
                extra={
                    "jobId": str(lease.id),
                    "workerId": self.worker_id,
                    "exceptionClass": error.__class__.__name__,
                },
            )
            self.queue.fail(
                lease.id,
                worker_id=self.worker_id,
                error_code="JOB_HANDLER_FAILED",
                retryable=False,
            )
        else:
            self.queue.succeed(lease.id, worker_id=self.worker_id)
        return True

    def run_forever(self, stop_requested: Callable[[], bool]) -> None:
        while not stop_requested():
            if not self.run_once():
                self.sleep(self.poll_seconds)


def build_worker(*, worker_id: str, lease_seconds: int) -> Worker:
    settings = AppSettings.from_env(os.environ)
    connection_factory = PostgresConnectionFactory(settings).connection
    queue = PostgresJobQueue(connection_factory)
    runtime_capabilities = SimcRuntimeCapabilities.from_env()
    simulation_worker = SimulationWorker(
        repository=PostgresSimulationRepository(connection_factory),
        simc=LocalSimulationCraftPort(runtime_revision=runtime_capabilities.runtime_revision),
        worker_id=worker_id,
        compiler=SimcProfileCompiler(capabilities=runtime_capabilities),
        readiness_validator=SimcReadinessValidator(),
        runtime_capabilities=runtime_capabilities,
        result_parser=SimulationResultParser(),
    )
    handlers = HandlerRegistry()
    handlers.register("simc", "run_simulation", simulation_worker.handle)
    return Worker(
        queue=queue,
        handlers=handlers,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
        poll_seconds=settings.worker_poll_seconds,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the isolated v2 PostgreSQL worker")
    parser.add_argument("--once", action="store_true", help="claim at most one job and exit")
    parser.add_argument("--worker-id", default=os.environ.get("HOSTNAME", "worker-v2"))
    parser.add_argument("--lease-seconds", type=int, default=30)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        worker = build_worker(worker_id=args.worker_id, lease_seconds=args.lease_seconds)
    except ValueError as error:
        build_parser().error(str(error))
    if args.once:
        worker.run_once()
        return 0
    worker.run_forever(lambda: False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

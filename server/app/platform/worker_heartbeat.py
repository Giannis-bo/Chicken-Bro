import json
import os
import re
import secrets
import stat
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "chickenbro-worker-heartbeat-v1"
_WORKER_ID = re.compile(r"[a-zA-Z0-9._:-]{1,64}\Z")
_MAX_HEARTBEAT_BYTES = 4096
_FUTURE_SKEW_SECONDS = 5


class WorkerHeartbeatError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("worker heartbeat clock must return an aware datetime")
    return value.astimezone(timezone.utc)


class WorkerHeartbeatWriter:
    def __init__(
        self,
        *,
        path: str | Path,
        environment: str,
        worker_id: str,
        clock: Callable[[], datetime] = _utc_now,
    ):
        self._path = Path(path)
        self._environment = str(environment)
        self._worker_id = str(worker_id)
        self._clock = clock
        if not self._path.is_absolute():
            raise ValueError("worker heartbeat path must be absolute")
        if self._environment not in {"local", "test", "candidate", "production"}:
            raise ValueError("worker heartbeat environment is invalid")
        if _WORKER_ID.fullmatch(self._worker_id) is None:
            raise ValueError("worker heartbeat id is invalid")

    def write(self) -> None:
        now = _aware_utc(self._clock())
        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "environment": self._environment,
            "workerId": self._worker_id,
            "updatedAt": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        }
        encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        parent = self._path.parent
        try:
            parent_state = parent.lstat()
        except OSError as error:
            raise WorkerHeartbeatError("WORKER_HEARTBEAT_WRITE_FAILED") from error
        if not stat.S_ISDIR(parent_state.st_mode) or parent.is_symlink():
            raise WorkerHeartbeatError("WORKER_HEARTBEAT_WRITE_FAILED")
        try:
            target_state = self._path.lstat()
        except FileNotFoundError:
            target_state = None
        except OSError as error:
            raise WorkerHeartbeatError("WORKER_HEARTBEAT_WRITE_FAILED") from error
        if target_state is not None and not stat.S_ISREG(target_state.st_mode):
            raise WorkerHeartbeatError("WORKER_HEARTBEAT_WRITE_FAILED")

        temporary = parent / f".{self._path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
        descriptor: int | None = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(temporary, flags, 0o600)
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb", closefd=True) as output:
                descriptor = None
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self._path)
        except OSError as error:
            raise WorkerHeartbeatError("WORKER_HEARTBEAT_WRITE_FAILED") from error
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


def read_worker_heartbeat(
    *,
    path: str | Path,
    expected_environment: str,
    expected_worker_id: str | None = None,
    max_age_seconds: int,
    now: Callable[[], datetime] = _utc_now,
) -> Mapping[str, Any]:
    heartbeat_path = Path(path)
    if not heartbeat_path.is_absolute():
        raise WorkerHeartbeatError("WORKER_HEARTBEAT_INVALID")
    try:
        path_state = heartbeat_path.lstat()
    except FileNotFoundError as error:
        raise WorkerHeartbeatError("WORKER_HEARTBEAT_MISSING") from error
    except OSError as error:
        raise WorkerHeartbeatError("WORKER_HEARTBEAT_INVALID") from error
    if not stat.S_ISREG(path_state.st_mode) or path_state.st_size > _MAX_HEARTBEAT_BYTES:
        raise WorkerHeartbeatError("WORKER_HEARTBEAT_INVALID")

    descriptor: int | None = None
    try:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(heartbeat_path, flags)
        opened_state = os.fstat(descriptor)
        if not stat.S_ISREG(opened_state.st_mode) or opened_state.st_size > _MAX_HEARTBEAT_BYTES:
            raise WorkerHeartbeatError("WORKER_HEARTBEAT_INVALID")
        with os.fdopen(descriptor, "rb", closefd=True) as source:
            descriptor = None
            raw = source.read(_MAX_HEARTBEAT_BYTES + 1)
    except WorkerHeartbeatError:
        raise
    except OSError as error:
        raise WorkerHeartbeatError("WORKER_HEARTBEAT_INVALID") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if len(raw) > _MAX_HEARTBEAT_BYTES:
        raise WorkerHeartbeatError("WORKER_HEARTBEAT_INVALID")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as error:
        raise WorkerHeartbeatError("WORKER_HEARTBEAT_INVALID") from error
    if not isinstance(payload, dict) or set(payload) != {
        "schemaVersion",
        "environment",
        "workerId",
        "updatedAt",
    }:
        raise WorkerHeartbeatError("WORKER_HEARTBEAT_INVALID")
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise WorkerHeartbeatError("WORKER_HEARTBEAT_INVALID")
    if payload.get("environment") != expected_environment:
        raise WorkerHeartbeatError("WORKER_HEARTBEAT_INVALID")
    worker_id = payload.get("workerId")
    if not isinstance(worker_id, str) or _WORKER_ID.fullmatch(worker_id) is None:
        raise WorkerHeartbeatError("WORKER_HEARTBEAT_INVALID")
    if expected_worker_id is not None and worker_id != expected_worker_id:
        raise WorkerHeartbeatError("WORKER_HEARTBEAT_INVALID")
    updated_at = payload.get("updatedAt")
    if not isinstance(updated_at, str) or not updated_at.endswith("Z"):
        raise WorkerHeartbeatError("WORKER_HEARTBEAT_INVALID")
    try:
        observed_at = datetime.fromisoformat(updated_at[:-1] + "+00:00")
        current = _aware_utc(now())
    except (TypeError, ValueError) as error:
        raise WorkerHeartbeatError("WORKER_HEARTBEAT_INVALID") from error
    age_seconds = (current - observed_at).total_seconds()
    if age_seconds < -_FUTURE_SKEW_SECONDS:
        raise WorkerHeartbeatError("WORKER_HEARTBEAT_INVALID")
    if age_seconds > max_age_seconds:
        raise WorkerHeartbeatError("WORKER_HEARTBEAT_STALE")
    return payload


__all__ = (
    "SCHEMA_VERSION",
    "WorkerHeartbeatError",
    "WorkerHeartbeatWriter",
    "read_worker_heartbeat",
)

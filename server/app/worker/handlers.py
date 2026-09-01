import re
from collections.abc import Callable

from server.app.worker.leases import JobLease


JobHandler = Callable[[JobLease], None]


class UnknownJobHandler(LookupError):
    def __init__(self, domain: str, command_type: str):
        super().__init__(f"unknown job handler: {domain}/{command_type}")


class RetryableJobError(RuntimeError):
    def __init__(self, code: str):
        if re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", code) is None:
            raise ValueError("retryable error code must be a stable public literal")
        self.code = code
        super().__init__(code)


class HandlerRegistry:
    def __init__(self):
        self._handlers: dict[tuple[str, str], JobHandler] = {}

    def register(self, domain: str, command_type: str, handler: JobHandler) -> None:
        key = (domain, command_type)
        if key in self._handlers:
            raise ValueError(f"duplicate job handler: {domain}/{command_type}")
        self._handlers[key] = handler

    def resolve(self, domain: str, command_type: str) -> JobHandler:
        try:
            return self._handlers[(domain, command_type)]
        except KeyError as error:
            raise UnknownJobHandler(domain, command_type) from error

"""Shared Web authentication results and errors."""
from dataclasses import dataclass
from datetime import datetime
from server.app.identity.domain import Principal


class AuthApplicationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class IssuedSession:
    token: str
    expires_at: datetime
    principal: Principal

import hashlib
import secrets
from dataclasses import dataclass
from typing import Literal
from uuid import UUID


SessionKind = Literal["web_cookie"]


@dataclass(frozen=True)
class Principal:
    """Authenticated internal identity; provider subjects stay outside the domain object."""

    user_id: UUID
    session_kind: SessionKind


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_opaque_token(byte_length: int = 32) -> str:
    if byte_length < 16:
        raise ValueError("opaque token length must be at least 16 bytes")
    return secrets.token_urlsafe(byte_length)


class IdentityConflictError(ValueError):
    """A provider identity has contradictory immutable ownership metadata."""

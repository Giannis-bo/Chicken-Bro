from dataclasses import dataclass
from typing import Literal
from uuid import UUID


SessionKind = Literal["mini_bearer", "web_cookie"]


@dataclass(frozen=True)
class Principal:
    """Authenticated internal identity; provider subjects stay outside the domain object."""

    user_id: UUID
    session_kind: SessionKind

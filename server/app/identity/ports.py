from typing import Protocol
from uuid import UUID

from server.app.identity.domain import Principal


class PrincipalResolver(Protocol):
    def resolve(self, credential: str) -> Principal | None:
        raise NotImplementedError


class IdentityRepository(Protocol):
    def get_user(self, user_id: UUID) -> Principal | None:
        raise NotImplementedError

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping
from uuid import UUID

from server.app.simulation.domain import SourceProvider, SourceReadiness, SourceSnapshot


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CharacterSnapshotCandidate:
    provider: SourceProvider
    source_url: str
    source_key: str
    snapshot: Mapping[str, object]
    provenance: Mapping[str, object]
    raw_sha256: str
    fetched_at: datetime
    readiness: SourceReadiness = SourceReadiness.INCOMPLETE_FOR_SIMC
    blockers: tuple[str, ...] = ()

    def to_source_snapshot(
        self,
        *,
        user_id: UUID | str,
        snapshot_id: UUID | str,
        readiness_report: object | None = None,
        revision: int = 1,
    ) -> SourceSnapshot:
        readiness = self.readiness
        blockers = self.blockers
        if readiness_report is not None:
            readiness = getattr(readiness_report, "readiness", readiness)
            blockers = tuple(getattr(readiness_report, "blockers", blockers))
        serialized_snapshot = dict(self.snapshot)
        if blockers:
            serialized_snapshot["readinessBlockers"] = list(blockers)
        return SourceSnapshot(
            id=snapshot_id if isinstance(snapshot_id, UUID) else UUID(str(snapshot_id)),
            user_id=user_id if isinstance(user_id, UUID) else UUID(str(user_id)),
            provider=self.provider,
            source_url=self.source_url,
            source_key=self.source_key,
            revision=max(1, int(revision)),
            readiness=readiness if isinstance(readiness, SourceReadiness) else SourceReadiness(str(readiness)),
            snapshot=serialized_snapshot,
            provenance=dict(self.provenance),
            raw_sha256=self.raw_sha256,
            fetched_at=self.fetched_at,
        )


__all__ = ("CharacterSnapshotCandidate", "canonical_json", "sha256_json")

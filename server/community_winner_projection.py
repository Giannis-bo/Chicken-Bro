"""Pure projection of ordered talent candidates into legal community gear winners."""

from __future__ import annotations

import copy
from typing import Any, Callable, Iterable, Mapping


PUBLIC_OBSERVED_SOURCE_KEY = "raiderio_observed_profile"
PUBLIC_TALENT_SOURCE_KEY = "raiderio"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _rank(candidate: Mapping[str, Any]) -> int:
    try:
        return int(candidate.get("talentCandidateRank") or 0)
    except (TypeError, ValueError):
        return 0


def candidate_identity(candidate: Mapping[str, Any]) -> str:
    """Return the immutable observed-profile identity shared by talent and gear."""

    source_identity = _text(candidate.get("sourceIdentity"))
    return source_identity if source_identity.startswith("raiderio:") else ""


def _problem(code: str, candidate: Mapping[str, Any], **details: Any) -> dict[str, Any]:
    return {
        "code": code,
        "candidateId": _text(candidate.get("candidateId")),
        **details,
    }


def _slot_identity(candidate: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return tuple(
        _text(candidate.get(key))
        for key in ("classKey", "specKey", "heroKey", "scenarioKey")
    )


def _candidate_problem(candidate: Mapping[str, Any], expected_slot: tuple[str, str, str, str]) -> dict[str, Any] | None:
    if _slot_identity(candidate) != expected_slot:
        return _problem(
            "HERO_SLOT_MISMATCH",
            candidate,
            expectedSlot={
                "classKey": expected_slot[0],
                "specKey": expected_slot[1],
                "heroKey": expected_slot[2],
                "scenarioKey": expected_slot[3],
            },
        )
    if _text(candidate.get("sourceKey")) != PUBLIC_TALENT_SOURCE_KEY:
        return _problem("TALENT_SOURCE_NOT_RAIDERIO", candidate)
    if not candidate_identity(candidate):
        return _problem("SOURCE_IDENTITY_MISSING", candidate)
    return None


def project_hero_slot(
    candidates: Iterable[Mapping[str, Any]],
    gear_by_identity: Mapping[str, Any],
    validate: Callable[[Mapping[str, Any], Any], Mapping[str, Any]],
) -> dict[str, Any]:
    """Select one legal gear winner without changing the ordered talent winner.

    The first ordered candidate is the immutable talent winner.  An invalid gear
    snapshot can only advance to the next candidate in the same hero slot.
    """

    ranked = sorted(
        (copy.deepcopy(dict(candidate)) for candidate in candidates if isinstance(candidate, Mapping)),
        key=lambda candidate: (_rank(candidate) if _rank(candidate) > 0 else 2**31, _text(candidate.get("candidateId"))),
    )
    if not ranked:
        return {"winner": None, "standbys": [], "rejected": [], "slotStatus": "pending_collection"}

    expected_slot = _slot_identity(ranked[0])
    talent_winner_id = _text(ranked[0].get("candidateId"))
    rejected: list[dict[str, Any]] = []

    for candidate in ranked:
        problem = _candidate_problem(candidate, expected_slot)
        if problem:
            rejected.append({**candidate, "problems": [problem]})
            continue
        try:
            verdict = validate(candidate, gear_by_identity.get(candidate_identity(candidate)))
        except Exception as error:  # validator failures must not create a public winner
            rejected.append({
                **candidate,
                "problems": [_problem("GEAR_VALIDATION_FAILED", candidate, detail=str(error))],
            })
            continue
        if not isinstance(verdict, Mapping) or _text(verdict.get("status")) != "verified":
            problems = verdict.get("problems") if isinstance(verdict, Mapping) else None
            if not isinstance(problems, list) or not problems:
                problems = [_problem("GEAR_LEGALITY_FAILED", candidate)]
            rejected.append({**candidate, "problems": copy.deepcopy(problems)})
            continue
        template = verdict.get("template")
        if not isinstance(template, Mapping):
            rejected.append({
                **candidate,
                "problems": [_problem("GEAR_TEMPLATE_MISSING", candidate)],
            })
            continue
        winner = {
            **candidate,
            **copy.deepcopy(dict(template)),
            "talentWinnerId": talent_winner_id,
            "gearProjectionMode": "talent_winner"
            if _text(candidate.get("candidateId")) == talent_winner_id
            else "gear_fallback",
        }
        return {"winner": winner, "standbys": [], "rejected": rejected, "slotStatus": "covered"}

    return {"winner": None, "standbys": [], "rejected": rejected, "slotStatus": "pending_collection"}


__all__ = (
    "PUBLIC_OBSERVED_SOURCE_KEY",
    "PUBLIC_TALENT_SOURCE_KEY",
    "candidate_identity",
    "project_hero_slot",
)

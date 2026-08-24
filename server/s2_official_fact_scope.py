"""S2 product-scope loading and official-relation classification.

The classifier only decides whether an already captured official relation is
inside the frozen four-category boundary.  It does not infer item identity,
tracks, or loot from names or downstream tools.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

try:
    from .s2_official_api_fact_snapshot import (
        LAIR_ENCOUNTER_ID,
        LAIR_INSTANCE_ID,
        MYTHIC_PLUS_INSTANCE_IDS,
        RAID_INSTANCE_ID,
        OfficialFactSnapshotContractError,
        validate_official_fact_scope,
        validate_product_content_scope,
    )
except ImportError:  # pragma: no cover - supports direct module execution
    from s2_official_api_fact_snapshot import (
        LAIR_ENCOUNTER_ID,
        LAIR_INSTANCE_ID,
        MYTHIC_PLUS_INSTANCE_IDS,
        RAID_INSTANCE_ID,
        OfficialFactSnapshotContractError,
        validate_official_fact_scope,
        validate_product_content_scope,
    )


class S2OfficialFactScopeError(OfficialFactSnapshotContractError):
    """Raised when scope loading or official relation classification fails."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise S2OfficialFactScopeError(f"{label} must be an object")
    return dict(value)


def _load_json(path: str | Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise S2OfficialFactScopeError(f"unable to load {label}") from error
    return _mapping(payload, label)


def load_product_content_scope(path: str | Path) -> dict[str, Any]:
    try:
        return validate_product_content_scope(
            _load_json(path, "product content scope")
        )
    except OfficialFactSnapshotContractError as error:
        raise S2OfficialFactScopeError(str(error)) from error


def load_official_fact_scope(path: str | Path) -> dict[str, Any]:
    try:
        return validate_official_fact_scope(
            _load_json(path, "official fact scope")
        )
    except OfficialFactSnapshotContractError as error:
        raise S2OfficialFactScopeError(str(error)) from error


def _member_status(relation: Mapping[str, Any]) -> str:
    count = relation.get("memberCount")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        return "UNVERIFIED"
    return "verified_empty" if count == 0 else "verified_nonempty"


def _constraint_mismatch(reason_code: str) -> dict[str, str]:
    return {
        "status": "UNVERIFIED",
        "reasonCode": reason_code,
    }


def _selected_relation(
    *,
    logical_source: str,
    raw_source_type: str,
    relation: Mapping[str, Any],
    expected_category: str,
    expected_mode: str,
) -> dict[str, Any]:
    if (
        _text(relation.get("journalCategory")) != expected_category
        or _text(relation.get("mode")) != expected_mode
        or _text(relation.get("rawSourceType")) != raw_source_type
    ):
        return _constraint_mismatch("OFFICIAL_RELATION_CONSTRAINT_MISMATCH")
    status = _member_status(relation)
    if status == "UNVERIFIED":
        return {
            "status": "UNVERIFIED",
            "reasonCode": "OFFICIAL_MEMBER_RELATION_MISSING",
        }
    result = {
        "status": status,
        "logicalSource": logical_source,
        "rawSourceType": raw_source_type,
    }
    if _text(relation.get("rawSourceKey")):
        result["rawSourceKey"] = _text(relation["rawSourceKey"])
    if _text(relation.get("officialEvidenceRef")):
        result["officialEvidenceRef"] = _text(relation["officialEvidenceRef"])
    return result


def classify_official_source(
    *,
    official_relation: Mapping[str, Any],
    product_scope: Mapping[str, Any],
    scope: Mapping[str, Any],
) -> dict[str, Any]:
    """Classify one captured official relation without name-based inference."""

    try:
        normalized_product_scope = validate_product_content_scope(product_scope)
        normalized_scope = validate_official_fact_scope(scope)
    except OfficialFactSnapshotContractError as error:
        raise S2OfficialFactScopeError(str(error)) from error
    relation = _mapping(official_relation, "official relation")
    source_kind = _text(relation.get("sourceKind"))
    excluded = normalized_scope["excludedSourceKinds"]
    if source_kind in excluded:
        return {
            "status": "excluded",
            "reasonCode": excluded[source_kind],
        }
    if source_kind in normalized_scope["nonMembershipKinds"]:
        return {
            "status": "excluded",
            "reasonCode": "NON_MEMBERSHIP_GREAT_VAULT",
        }

    instance_id = relation.get("journalInstanceId")
    encounter_id = relation.get("encounterId")
    expected_constraints = normalized_product_scope["expectedOfficialConstraints"]
    if instance_id in MYTHIC_PLUS_INSTANCE_IDS:
        return _selected_relation(
            logical_source="mythic_plus",
            raw_source_type="mythic_plus",
            relation=relation,
            expected_category=expected_constraints["mythic_plus"]["journalCategory"],
            expected_mode=expected_constraints["mythic_plus"]["mode"],
        )
    if instance_id == LAIR_INSTANCE_ID:
        if encounter_id != LAIR_ENCOUNTER_ID:
            return _constraint_mismatch("OFFICIAL_LAIR_ENCOUNTER_MISMATCH")
        return _selected_relation(
            logical_source="raid",
            raw_source_type="lair",
            relation=relation,
            expected_category=expected_constraints["lair"]["journalCategory"],
            expected_mode=expected_constraints["lair"]["mode"],
        )
    if instance_id == RAID_INSTANCE_ID:
        return _selected_relation(
            logical_source="raid",
            raw_source_type="raid",
            relation=relation,
            expected_category=expected_constraints["raid"]["journalCategory"],
            expected_mode=expected_constraints["raid"]["mode"],
        )
    if instance_id is not None or _text(relation.get("sourceKind")) == "journal":
        return {
            "status": "excluded",
            "reasonCode": "OUT_OF_SCOPE_PRODUCT_CONTENT",
        }
    return _constraint_mismatch("OFFICIAL_SOURCE_RELATION_UNIDENTIFIED")


def require_official_mythic_cap(official_track: Mapping[str, Any] | None) -> dict[str, str]:
    """Require an explicit official track fact before admitting an item."""

    if not isinstance(official_track, Mapping) or "mythicCapable" not in official_track:
        return {
            "status": "UNVERIFIED",
            "reasonCode": "S2_OFFICIAL_TRACK_UNAVAILABLE",
        }
    if official_track.get("mythicCapable") is True:
        return {"status": "verified"}
    if official_track.get("mythicCapable") is False:
        return {
            "status": "excluded",
            "reasonCode": "EXCLUDED_NOT_MYTHIC_CAPABLE",
        }
    return {
        "status": "UNVERIFIED",
        "reasonCode": "S2_OFFICIAL_TRACK_UNAVAILABLE",
    }

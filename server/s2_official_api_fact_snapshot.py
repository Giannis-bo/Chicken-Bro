"""Offline contracts for the Midnight Season 2 official-fact snapshot.

This module does not fetch Blizzard data and does not write a Catalog, Exact
registry, Manifest, candidate, or active pointer.  It validates the frozen
four-category product boundary, an immutable capture manifest, and the small
fact graph that a later API normalizer may produce.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping


SEASON_KEY = "midnight-season-2"
PRODUCT_SCOPE_SCHEMA_REVISION = "s2-product-content-scope-v1"
FACT_SCOPE_SCHEMA_REVISION = "s2-official-fact-scope-v1"
CAPTURE_MANIFEST_SCHEMA_REVISION = "s2-official-api-capture-manifest-v1"
SNAPSHOT_SCHEMA_REVISION = "s2-official-api-fact-snapshot-v1"
SNAPSHOT_REVISION_PREFIX = "s2-official-api-fact-snapshot:sha256:"

LOGICAL_SOURCE_KINDS = ("raid", "mythic_plus", "crafted", "tier_set")
LOGICAL_SOURCE_KEYS = tuple(
    f"{kind}:{SEASON_KEY}" for kind in LOGICAL_SOURCE_KINDS
)
MYTHIC_PLUS_INSTANCE_IDS = (1030, 1041, 1202, 1304, 1309, 1311, 1313, 1322)
LAIR_INSTANCE_ID = 1317
LAIR_ENCOUNTER_ID = 2849
RAID_INSTANCE_ID = 1320
ALLOWED_FACT_STATUSES = frozenset({"verified", "partial", "UNVERIFIED", "blocked"})

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_SELECTOR_KEYS = frozenset(
    {
        "apiBuild",
        "bonusIds",
        "effects",
        "encounterId",
        "encounterIds",
        "itemId",
        "itemIds",
        "itemLevel",
        "itemName",
        "items",
        "loot",
        "recipeId",
        "setId",
        "staticStats",
        "trackKey",
        "variantKey",
    }
)
_SENSITIVE_KEYS = frozenset(
    {
        "accessToken",
        "authorization",
        "clientSecret",
        "password",
        "token",
    }
)


class OfficialFactSnapshotContractError(ValueError):
    """Raised when an offline S2 official-fact contract is not fail-closed."""


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    """Return the stable SHA-256 identity for canonical JSON content."""

    return f"sha256:{_hash(value)}"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OfficialFactSnapshotContractError(f"{label} must be an object")
    return dict(value)


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise OfficialFactSnapshotContractError(f"{label} must be a list")
    return list(value)


def _require_text(value: Any, label: str) -> str:
    text = _text(value)
    if not text:
        raise OfficialFactSnapshotContractError(f"{label} is required")
    return text


def _require_positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise OfficialFactSnapshotContractError(f"{label} must be a positive integer")
    return value


def _instant(value: Any, label: str) -> str:
    raw = _require_text(value, label)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise OfficialFactSnapshotContractError(
            f"{label} must be an ISO-8601 instant"
        ) from error
    if parsed.tzinfo is None:
        raise OfficialFactSnapshotContractError(
            f"{label} must include a timezone"
        )
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _walk_forbidden_keys(value: Any, path: str = "scope") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text in _FORBIDDEN_SELECTOR_KEYS:
                raise OfficialFactSnapshotContractError(
                    f"{path}.{key_text} must not contain game facts"
                )
            _walk_forbidden_keys(child, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_forbidden_keys(child, f"{path}[{index}]")


def _walk_sensitive_keys(value: Any, path: str = "manifest") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).casefold() in {item.casefold() for item in _SENSITIVE_KEYS}:
                raise OfficialFactSnapshotContractError(
                    f"{path}.{key} must not contain credentials"
                )
            _walk_sensitive_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_sensitive_keys(child, f"{path}[{index}]")


def _validate_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing={','.join(missing)}")
        if extra:
            details.append(f"extra={','.join(extra)}")
        raise OfficialFactSnapshotContractError(
            f"{label} keys mismatch ({'; '.join(details)})"
        )


def _validate_logical_source_keys(value: Any) -> list[str]:
    rows = _list(value, "logicalSourceKeys")
    normalized = sorted({_require_text(row, "logicalSourceKey") for row in rows})
    if len(rows) != 4 or normalized != sorted(LOGICAL_SOURCE_KEYS):
        raise OfficialFactSnapshotContractError(
            "scope must declare exactly four logical sources"
        )
    return normalized


def validate_product_content_scope(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize the user-confirmed four-category selector."""

    scope = _mapping(value, "product content scope")
    _walk_forbidden_keys(scope)
    if scope.get("schemaVersion") != 1:
        raise OfficialFactSnapshotContractError(
            "product content scope requires schemaVersion=1"
        )
    if _text(scope.get("productContentScopeRevision")) != PRODUCT_SCOPE_SCHEMA_REVISION:
        raise OfficialFactSnapshotContractError(
            "product content scope revision is not recognized"
        )
    if _text(scope.get("seasonKey")) != SEASON_KEY:
        raise OfficialFactSnapshotContractError(
            "product content scope must be bound to midnight-season-2"
        )
    logical_keys = _validate_logical_source_keys(scope.get("logicalSourceKeys"))
    if scope.get("logicalSourceCount") != 4:
        raise OfficialFactSnapshotContractError(
            "product content scope requires logicalSourceCount=4"
        )
    for field in (
        "raidIncludesLair",
        "lairRawSourceTypePreserved",
        "tierSetIsIndependentMembershipDimension",
    ):
        if scope.get(field) is not True:
            raise OfficialFactSnapshotContractError(
                f"product content scope requires {field}=true"
            )

    logical_sources = _list(scope.get("logicalSources"), "logicalSources")
    logical_source_rows = {}
    for row in logical_sources:
        source = _mapping(row, "logical source")
        key = _require_text(source.get("logicalSourceKey"), "logical source key")
        if key in logical_source_rows:
            raise OfficialFactSnapshotContractError(
                f"logicalSources has duplicate {key}"
            )
        raw_types = sorted(
            {
                _require_text(raw_type, f"{key}.rawSourceTypes[]")
                for raw_type in _list(source.get("rawSourceTypes"), f"{key}.rawSourceTypes")
            }
        )
        if key == f"raid:{SEASON_KEY}" and raw_types != ["lair", "raid"]:
            raise OfficialFactSnapshotContractError(
                "raid logical source must preserve raw raid and lair types"
            )
        if key == f"tier_set:{SEASON_KEY}" and raw_types != ["tier_set"]:
            raise OfficialFactSnapshotContractError(
                "tier_set logical source must remain an independent membership"
            )
        if key not in logical_keys:
            raise OfficialFactSnapshotContractError(
                f"logical source {key} is outside the four-category scope"
            )
        _require_text(source.get("productLabel"), f"{key}.productLabel")
        logical_source_rows[key] = {
            **source,
            "logicalSourceKey": key,
            "rawSourceTypes": raw_types,
        }
    if sorted(logical_source_rows) != sorted(logical_keys):
        raise OfficialFactSnapshotContractError(
            "logicalSources must cover exactly the four logical sources"
        )

    selections = _mapping(
        scope.get("journalInstanceSelections"),
        "journalInstanceSelections",
    )
    _validate_exact_keys(
        selections,
        {"mythic_plus", "lair", "raid"},
        "journalInstanceSelections",
    )
    mythic_plus = _list(selections["mythic_plus"], "mythic_plus selections")
    if (
        len(mythic_plus) != len(set(mythic_plus))
        or sorted(mythic_plus) != list(MYTHIC_PLUS_INSTANCE_IDS)
        or any(isinstance(item, bool) or not isinstance(item, int) for item in mythic_plus)
    ):
        raise OfficialFactSnapshotContractError(
            "mythic_plus selections must be the eight fixed Journal instance ids"
        )
    lair_rows = _list(selections["lair"], "lair selections")
    if len(lair_rows) != 1:
        raise OfficialFactSnapshotContractError(
            "lair selections must contain exactly one Journal instance"
        )
    lair = _mapping(lair_rows[0], "lair selection")
    if lair.get("journalInstanceId") != LAIR_INSTANCE_ID:
        raise OfficialFactSnapshotContractError(
            "lair selection must target Journal instance 1317"
        )
    if lair.get("journalEncounterIds") != [LAIR_ENCOUNTER_ID]:
        raise OfficialFactSnapshotContractError(
            "lair selection must target encounter 2849"
        )
    raid_rows = _list(selections["raid"], "raid selections")
    if len(raid_rows) != 1:
        raise OfficialFactSnapshotContractError(
            "raid selections must contain exactly one Journal instance"
        )
    raid = _mapping(raid_rows[0], "raid selection")
    if raid.get("journalInstanceId") != RAID_INSTANCE_ID:
        raise OfficialFactSnapshotContractError(
            "raid selection must target Journal instance 1320"
        )
    if _text(raid.get("journalEncounterSelection")) != "all":
        raise OfficialFactSnapshotContractError(
            "raid selection must select all encounters"
        )

    crafted = _mapping(scope.get("craftedSelection"), "craftedSelection")
    if _text(crafted.get("kind")) != "official_recipe_output_relations":
        raise OfficialFactSnapshotContractError(
            "crafted selection must use official recipe/output relations"
        )
    constraints = _mapping(
        scope.get("expectedOfficialConstraints"),
        "expectedOfficialConstraints",
    )
    expected_constraints = {
        "mythic_plus": {"journalCategory": "DUNGEON", "mode": "MYTHIC_KEYSTONE"},
        "lair": {"journalCategory": "RAID", "mode": "MYTHIC"},
        "raid": {"journalCategory": "RAID", "mode": "MYTHIC"},
    }
    if constraints != expected_constraints:
        raise OfficialFactSnapshotContractError(
            "expected official constraints do not match the four-category scope"
        )

    return {
        "schemaVersion": 1,
        "productContentScopeRevision": PRODUCT_SCOPE_SCHEMA_REVISION,
        "seasonKey": SEASON_KEY,
        "logicalSourceCount": 4,
        "logicalSourceKeys": logical_keys,
        "logicalSources": [logical_source_rows[key] for key in logical_keys],
        "raidIncludesLair": True,
        "lairRawSourceTypePreserved": True,
        "tierSetIsIndependentMembershipDimension": True,
        "journalInstanceSelections": {
            "mythic_plus": sorted(mythic_plus),
            "lair": [{"journalInstanceId": LAIR_INSTANCE_ID, "journalEncounterIds": [LAIR_ENCOUNTER_ID]}],
            "raid": [{"journalInstanceId": RAID_INSTANCE_ID, "journalEncounterSelection": "all"}],
        },
        "craftedSelection": {"kind": "official_recipe_output_relations"},
        "expectedOfficialConstraints": expected_constraints,
    }


def validate_official_fact_scope(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate generic exclusion and official-owner rules."""

    scope = _mapping(value, "official fact scope")
    if scope.get("schemaVersion") != 1:
        raise OfficialFactSnapshotContractError(
            "official fact scope requires schemaVersion=1"
        )
    if _text(scope.get("scopePolicyRevision")) != FACT_SCOPE_SCHEMA_REVISION:
        raise OfficialFactSnapshotContractError(
            "official fact scope revision is not recognized"
        )
    if _text(scope.get("seasonKey")) != SEASON_KEY:
        raise OfficialFactSnapshotContractError(
            "official fact scope must be bound to midnight-season-2"
        )
    authority = _mapping(scope.get("authority"), "official fact scope authority")
    if _text(authority.get("kind")) != "blizzard_game_data_api":
        raise OfficialFactSnapshotContractError(
            "official fact scope authority must be blizzard_game_data_api"
        )
    excluded = _mapping(scope.get("excludedSourceKinds"), "excludedSourceKinds")
    required_exclusions = {
        "dungeon": "OUT_OF_SCOPE_DUNGEON",
        "delve": "OUT_OF_SCOPE_DELVE",
        "prey": "OUT_OF_SCOPE_PREY",
        "world_content": "OUT_OF_SCOPE_WORLD_CONTENT",
    }
    for source_kind, reason in required_exclusions.items():
        if _text(excluded.get(source_kind)) != reason:
            raise OfficialFactSnapshotContractError(
                f"official fact scope requires exclusion {source_kind}={reason}"
            )
    non_membership = _list(scope.get("nonMembershipKinds"), "nonMembershipKinds")
    if non_membership != ["great_vault"]:
        raise OfficialFactSnapshotContractError(
            "great_vault must remain a non-membership projection"
        )
    if scope.get("requiresOfficialMythicCap") is not True:
        raise OfficialFactSnapshotContractError(
            "official fact scope requires official mythic-capability proof"
        )
    return {
        "schemaVersion": 1,
        "scopePolicyRevision": FACT_SCOPE_SCHEMA_REVISION,
        "seasonKey": SEASON_KEY,
        "authority": {"kind": "blizzard_game_data_api"},
        "excludedSourceKinds": dict(excluded),
        "nonMembershipKinds": ["great_vault"],
        "requiresOfficialMythicCap": True,
    }


def request_key(
    path: str,
    query: Mapping[str, Any] | None = None,
    *,
    namespace: str,
    region: str,
    locale: str,
) -> str:
    """Build a stable request identity without retaining credentials."""

    identity = {
        "path": _require_text(path, "request path"),
        "query": _canonical(dict(query or {})),
        "namespace": _require_text(namespace, "request namespace"),
        "region": _require_text(region, "request region"),
        "locale": _require_text(locale, "request locale"),
    }
    return f"request:sha256:{_hash(identity)}"


def validate_capture_manifest(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a raw-response manifest before any normalizer consumes it."""

    manifest = _mapping(value, "capture manifest")
    _walk_sensitive_keys(manifest)
    if _text(manifest.get("schemaRevision")) != CAPTURE_MANIFEST_SCHEMA_REVISION:
        raise OfficialFactSnapshotContractError(
            "capture manifest revision is not recognized"
        )
    if _text(manifest.get("seasonKey")) != SEASON_KEY:
        raise OfficialFactSnapshotContractError(
            "capture manifest must be bound to midnight-season-2"
        )
    status = _text(manifest.get("status"))
    if status not in {"captured", "partial", "blocked"}:
        raise OfficialFactSnapshotContractError(
            "capture manifest status must be captured, partial, or blocked"
        )
    region = _require_text(manifest.get("region"), "capture manifest region")
    locale = _require_text(manifest.get("locale"), "capture manifest locale")
    namespace = _require_text(manifest.get("namespace"), "capture manifest namespace")
    raw_namespaces = manifest.get("namespaces")
    if raw_namespaces is None:
        namespaces = [namespace]
    else:
        namespace_rows = _list(raw_namespaces, "capture manifest namespaces")
        namespaces = sorted(
            {_require_text(row, "capture manifest namespace") for row in namespace_rows}
        )
        if not namespaces:
            raise OfficialFactSnapshotContractError(
                "capture manifest namespaces must not be empty"
            )
        if namespace == "multiple":
            if len(namespaces) < 2:
                raise OfficialFactSnapshotContractError(
                    "capture manifest namespace=multiple requires multiple namespaces"
                )
        elif namespaces != [namespace]:
            raise OfficialFactSnapshotContractError(
                "capture manifest namespace and namespaces drifted"
            )
    entries = _list(manifest.get("entries"), "capture manifest entries")
    if not entries:
        raise OfficialFactSnapshotContractError(
            "capture manifest requires at least one entry"
        )
    normalized_entries = []
    seen_request_keys = set()
    seen_response_paths = set()
    for index, raw_entry in enumerate(entries):
        entry = _mapping(raw_entry, f"capture manifest entry {index}")
        entry_namespace = _require_text(entry.get("namespace"), "entry namespace")
        entry_region = _require_text(entry.get("region"), "entry region")
        entry_locale = _require_text(entry.get("locale"), "entry locale")
        if entry_namespace not in namespaces or (namespace != "multiple" and entry_namespace != namespace):
            raise OfficialFactSnapshotContractError(
                "capture manifest entry namespace is not declared"
            )
        if (entry_region, entry_locale) != (region, locale):
            raise OfficialFactSnapshotContractError(
                "capture manifest entry namespace/region/locale drifted"
            )
        path = _require_text(entry.get("path"), "entry path")
        query = _mapping(entry.get("query", {}), "entry query")
        computed_key = request_key(
            path,
            query,
            namespace=entry_namespace,
            region=region,
            locale=locale,
        )
        if _text(entry.get("requestKey")) != computed_key:
            raise OfficialFactSnapshotContractError(
                f"entry requestKey does not match canonical request identity at index {index}"
            )
        if computed_key in seen_request_keys:
            raise OfficialFactSnapshotContractError(
                f"capture manifest has duplicate requestKey {computed_key}"
            )
        seen_request_keys.add(computed_key)
        response_path = _require_text(entry.get("responsePath"), "entry responsePath")
        if response_path in seen_response_paths:
            raise OfficialFactSnapshotContractError(
                f"capture manifest has duplicate responsePath {response_path}"
            )
        seen_response_paths.add(response_path)
        response_hash = _text(entry.get("responseSha256"))
        if not _HASH_RE.fullmatch(response_hash):
            raise OfficialFactSnapshotContractError(
                "entry responseSha256 must be a lowercase SHA-256 digest"
            )
        response_bytes = _require_positive_int(entry.get("responseBytes"), "entry responseBytes")
        captured_at = _instant(entry.get("capturedAt"), "entry capturedAt")
        pagination = _mapping(entry.get("pagination"), "entry pagination")
        page = _require_positive_int(pagination.get("page"), "pagination.page")
        page_count = _require_positive_int(pagination.get("pageCount"), "pagination.pageCount")
        if pagination.get("complete") is not True:
            raise OfficialFactSnapshotContractError(
                "capture manifest pagination must be complete"
            )
        if page > page_count:
            raise OfficialFactSnapshotContractError(
                "capture manifest pagination page exceeds pageCount"
            )
        parent = entry.get("paginationParentRequestKey")
        if parent is not None and not _text(parent):
            raise OfficialFactSnapshotContractError(
                "paginationParentRequestKey must be null or non-empty"
            )
        normalized_entries.append(
            {
                "requestKey": computed_key,
                "path": path,
                "query": _canonical(query),
                "namespace": entry_namespace,
                "region": region,
                "locale": locale,
                "responsePath": response_path,
                "responseSha256": response_hash,
                "responseBytes": response_bytes,
                "capturedAt": captured_at,
                "pagination": {
                    "page": page,
                    "pageCount": page_count,
                    "complete": True,
                },
                "paginationParentRequestKey": _text(parent) or None,
            }
        )
    normalized_entries.sort(key=lambda row: row["requestKey"])
    return {
        "schemaRevision": CAPTURE_MANIFEST_SCHEMA_REVISION,
        "seasonKey": SEASON_KEY,
        "status": status,
        "region": region,
        "locale": locale,
        "namespace": namespace,
        "namespaces": namespaces,
        "entries": normalized_entries,
    }


def _manifest_identity(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Exclude capture timestamps and local response filenames from identity."""

    return {
        "schemaRevision": manifest["schemaRevision"],
        "seasonKey": manifest["seasonKey"],
        "status": manifest["status"],
        "region": manifest["region"],
        "locale": manifest["locale"],
        "namespace": manifest["namespace"],
        "namespaces": manifest.get("namespaces", [manifest["namespace"]]),
        "entries": [
            {
                key: entry[key]
                for key in (
                    "requestKey",
                    "path",
                    "query",
                    "namespace",
                    "region",
                    "locale",
                    "responseSha256",
                    "responseBytes",
                    "pagination",
                    "paginationParentRequestKey",
                )
            }
            for entry in manifest["entries"]
        ],
    }


def _validate_status(value: Any, label: str) -> str:
    status = _text(value)
    if status not in ALLOWED_FACT_STATUSES:
        raise OfficialFactSnapshotContractError(
            f"{label} has unsupported fact status {status or '<empty>'}"
        )
    return status


def _evidence_refs(value: Any, label: str) -> list[str]:
    refs = [
        _text(ref)
        for ref in _list(value, f"{label}.officialEvidenceRefs")
        if _text(ref)
    ]
    if not refs:
        raise OfficialFactSnapshotContractError(
            f"{label} requires officialEvidenceRefs"
        )
    return sorted(set(refs))


def _validate_source_membership(value: Any, label: str) -> dict[str, Any]:
    row = _mapping(value, label)
    logical_source = _require_text(row.get("logicalSource"), f"{label}.logicalSource")
    raw_type = _require_text(row.get("rawSourceType"), f"{label}.rawSourceType")
    raw_key = _require_text(row.get("rawSourceKey"), f"{label}.rawSourceKey")
    expected_raw_types = {
        "raid": {"raid", "lair"},
        "mythic_plus": {"mythic_plus"},
        "crafted": {"crafted"},
        "tier_set": {"tier_set"},
    }
    if logical_source not in expected_raw_types:
        raise OfficialFactSnapshotContractError(
            f"{label}.logicalSource is outside the four-category scope"
        )
    if raw_type not in expected_raw_types[logical_source]:
        raise OfficialFactSnapshotContractError(
            f"{label}.rawSourceType is incompatible with logicalSource"
        )
    if logical_source == "raid" and not raw_key.startswith(f"{raw_type}:"):
        raise OfficialFactSnapshotContractError(
            f"{label}.rawSourceKey must preserve the raw {raw_type} prefix"
        )
    if logical_source != "raid" and not raw_key.startswith(f"{raw_type}:"):
        raise OfficialFactSnapshotContractError(
            f"{label}.rawSourceKey must match rawSourceType"
        )
    return {
        "logicalSource": logical_source,
        "rawSourceType": raw_type,
        "rawSourceKey": raw_key,
        "officialEvidenceRefs": _evidence_refs(
            row.get("officialEvidenceRefs"),
            label,
        ),
    }


def _validate_source_fact(value: Any, index: int) -> dict[str, Any]:
    label = f"sourceFacts[{index}]"
    row = _mapping(value, label)
    fact_owner = _require_text(row.get("factOwner", "blizzard_game_data_api"), f"{label}.factOwner")
    if fact_owner != "blizzard_game_data_api":
        raise OfficialFactSnapshotContractError(
            f"{label}.factOwner must be blizzard_game_data_api"
        )
    membership = _validate_source_membership(row, label)
    return {
        **membership,
        "factOwner": fact_owner,
        "status": _validate_status(row.get("status"), label),
    }


def _validate_item_fact(value: Any, index: int) -> dict[str, Any]:
    label = f"itemFacts[{index}]"
    row = _mapping(value, label)
    item_id = _require_text(row.get("itemId"), f"{label}.itemId")
    fact_owner = _require_text(row.get("factOwner"), f"{label}.factOwner")
    if fact_owner != "blizzard_game_data_api":
        raise OfficialFactSnapshotContractError(
            f"{label}.factOwner must be blizzard_game_data_api"
        )
    memberships = _list(row.get("sourceMemberships"), f"{label}.sourceMemberships")
    normalized_memberships = [
        _validate_source_membership(member, f"{label}.sourceMemberships[{member_index}]")
        for member_index, member in enumerate(memberships)
    ]
    identities = {
        (member["logicalSource"], member["rawSourceType"], member["rawSourceKey"])
        for member in normalized_memberships
    }
    if len(identities) != len(normalized_memberships):
        raise OfficialFactSnapshotContractError(
            f"{label}.sourceMemberships contains duplicate membership"
        )
    field_statuses = _mapping(row.get("fieldStatuses"), f"{label}.fieldStatuses")
    normalized_field_statuses = {
        _require_text(field, f"{label}.fieldStatuses key"): _validate_status(
            field_status,
            f"{label}.fieldStatuses.{field}",
        )
        for field, field_status in field_statuses.items()
    }
    return {
        "itemId": item_id,
        "factOwner": fact_owner,
        "status": _validate_status(row.get("status"), label),
        "sourceMemberships": normalized_memberships,
        "fieldStatuses": normalized_field_statuses,
        "officialEvidenceRefs": _evidence_refs(row.get("officialEvidenceRefs"), label),
    }


def _validate_unresolved(value: Any, index: int) -> dict[str, Any]:
    label = f"unresolvedFacts[{index}]"
    row = _mapping(value, label)
    return {
        "subjectKey": _require_text(row.get("subjectKey"), f"{label}.subjectKey"),
        "field": _require_text(row.get("field"), f"{label}.field"),
        "status": _validate_status(row.get("status"), label),
        "reasonCode": _require_text(row.get("reasonCode"), f"{label}.reasonCode"),
        "officialEvidenceRefs": _evidence_refs(row.get("officialEvidenceRefs"), label),
    }


def _validate_exclusion(value: Any, index: int) -> dict[str, Any]:
    label = f"exclusionLedger[{index}]"
    row = _mapping(value, label)
    return {
        "subjectKey": _require_text(row.get("subjectKey"), f"{label}.subjectKey"),
        "sourceKind": _require_text(row.get("sourceKind"), f"{label}.sourceKind"),
        "reasonCode": _require_text(row.get("reasonCode"), f"{label}.reasonCode"),
        "officialEvidenceRefs": _evidence_refs(row.get("officialEvidenceRefs"), label),
    }


def _validate_count_map(value: Any, label: str) -> dict[str, int]:
    row = _mapping(value, label)
    expected = set(LOGICAL_SOURCE_KINDS)
    if set(row) != expected:
        raise OfficialFactSnapshotContractError(
            f"{label} must contain exactly the four logical source kinds"
        )
    normalized = {}
    for kind in LOGICAL_SOURCE_KINDS:
        count = row[kind]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise OfficialFactSnapshotContractError(
                f"{label}.{kind} must be a non-negative integer"
            )
        normalized[kind] = count
    return normalized


def validate_official_api_fact_snapshot(
    snapshot: Mapping[str, Any],
    *,
    scope: Mapping[str, Any] | None = None,
) -> None:
    """Revalidate a generated snapshot and its deterministic revision."""

    row = _mapping(snapshot, "official API fact snapshot")
    if _text(row.get("schemaRevision")) != SNAPSHOT_SCHEMA_REVISION:
        raise OfficialFactSnapshotContractError(
            "official API fact snapshot revision is not recognized"
        )
    if _text(row.get("seasonKey")) != SEASON_KEY:
        raise OfficialFactSnapshotContractError(
            "official API fact snapshot must be bound to midnight-season-2"
        )
    if _text(row.get("status")) not in {"verified", "partial", "blocked"}:
        raise OfficialFactSnapshotContractError(
            "official API fact snapshot status is invalid"
        )
    if scope is not None:
        normalized_scope = validate_product_content_scope(scope)
        if row.get("productContentScopeRevision") != normalized_scope[
            "productContentScopeRevision"
        ]:
            raise OfficialFactSnapshotContractError(
                "official API fact snapshot product scope revision does not match"
            )
    capture_identity = _mapping(
        row.get("captureIdentity"),
        "official API fact snapshot captureIdentity",
    )
    for field in (
        "captureManifestSha256",
        "region",
        "locale",
        "parserRevision",
    ):
        _require_text(capture_identity.get(field), f"captureIdentity.{field}")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", capture_identity["captureManifestSha256"]):
        raise OfficialFactSnapshotContractError(
            "captureIdentity.captureManifestSha256 is invalid"
        )
    for field in ("productContentScopeSha256", "scopePolicySha256"):
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", _text(capture_identity.get(field))):
            raise OfficialFactSnapshotContractError(
                f"captureIdentity.{field} is invalid"
            )
    _list(capture_identity.get("namespaces"), "captureIdentity.namespaces")
    captured_range = _mapping(
        capture_identity.get("capturedAtRange"),
        "captureIdentity.capturedAtRange",
    )
    _instant(captured_range.get("first"), "captureIdentity.capturedAtRange.first")
    _instant(captured_range.get("last"), "captureIdentity.capturedAtRange.last")

    normalized_source_facts = [
        _validate_source_fact(raw_row, index)
        for index, raw_row in enumerate(_list(row.get("sourceFacts"), "sourceFacts"))
    ]
    normalized_item_facts = [
        _validate_item_fact(raw_row, index)
        for index, raw_row in enumerate(_list(row.get("itemFacts"), "itemFacts"))
    ]
    normalized_exclusions = [
        _validate_exclusion(raw_row, index)
        for index, raw_row in enumerate(
            _list(row.get("exclusionLedger"), "exclusionLedger")
        )
    ]
    normalized_unresolved = [
        _validate_unresolved(raw_row, index)
        for index, raw_row in enumerate(
            _list(row.get("unresolvedFacts"), "unresolvedFacts")
        )
    ]
    counts = _mapping(row.get("counts"), "counts")
    candidate_counts = _validate_count_map(
        counts.get("officialScopeCandidateCountByKind"),
        "counts.officialScopeCandidateCountByKind",
    )
    admitted_counts = _validate_count_map(
        counts.get("officialScopeAdmittedCountByKind"),
        "counts.officialScopeAdmittedCountByKind",
    )
    for field in ("verifiedFactCount", "unverifiedCount", "blockedCount", "simcReadyCount"):
        value = counts.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise OfficialFactSnapshotContractError(
                f"counts.{field} must be a non-negative integer"
            )
    simc_ready_by_kind = _mapping(
        counts.get("simcReadyCountByKind"),
        "counts.simcReadyCountByKind",
    )
    if set(simc_ready_by_kind) != set(LOGICAL_SOURCE_KINDS) or any(
        value is not None for value in simc_ready_by_kind.values()
    ):
        raise OfficialFactSnapshotContractError(
            "stage 1 snapshot must not claim SimC-ready facts"
        )
    if counts.get("publicSimcReadyRate") is not None:
        raise OfficialFactSnapshotContractError(
            "stage 1 snapshot must not claim publicSimcReadyRate"
        )
    revision_identity = {
        "schemaRevision": SNAPSHOT_SCHEMA_REVISION,
        "productContentScopeRevision": row["productContentScopeRevision"],
        "scopePolicyRevision": row["scopePolicyRevision"],
        "productContentScopeSha256": capture_identity.get(
            "productContentScopeSha256"
        ),
        "scopePolicySha256": capture_identity.get("scopePolicySha256"),
        "captureManifestSha256": capture_identity["captureManifestSha256"],
        "parserRevision": capture_identity["parserRevision"],
        "sourceFacts": normalized_source_facts,
        "itemFacts": normalized_item_facts,
        "exclusionLedger": normalized_exclusions,
        "unresolvedFacts": normalized_unresolved,
        "counts": {
            "officialScopeCandidateCountByKind": candidate_counts,
            "officialScopeAdmittedCountByKind": admitted_counts,
            "verifiedFactCount": counts["verifiedFactCount"],
            "unverifiedCount": counts["unverifiedCount"],
            "blockedCount": counts["blockedCount"],
            "excludedCountByReason": counts.get("excludedCountByReason", {}),
            "simcReadyCountByKind": {kind: None for kind in LOGICAL_SOURCE_KINDS},
            "simcReadyCount": 0,
            "publicSimcReadyRate": None,
        },
    }
    expected_revision = SNAPSHOT_REVISION_PREFIX + _hash(revision_identity)
    if _text(row.get("officialApiFactSnapshotRevision")) != expected_revision:
        raise OfficialFactSnapshotContractError(
            "official API fact snapshot revision does not match canonical content"
        )


def build_official_api_fact_snapshot(
    *,
    product_scope: Mapping[str, Any],
    fact_scope: Mapping[str, Any],
    capture_manifest: Mapping[str, Any],
    scope_counts: Mapping[str, Any],
    source_facts: list[Mapping[str, Any]],
    item_facts: list[Mapping[str, Any]],
    exclusion_ledger: list[Mapping[str, Any]] | None = None,
    unresolved_facts: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build an immutable, SimC-independent official fact snapshot."""

    normalized_scope = validate_product_content_scope(product_scope)
    normalized_fact_scope = validate_official_fact_scope(fact_scope)
    normalized_manifest = validate_capture_manifest(capture_manifest)
    counts_input = _mapping(scope_counts, "scope_counts")
    candidate_counts = _validate_count_map(
        counts_input.get("candidate"),
        "scope_counts.candidate",
    )
    admitted_counts = _validate_count_map(
        counts_input.get("admitted"),
        "scope_counts.admitted",
    )
    normalized_source_facts = [
        _validate_source_fact(row, index)
        for index, row in enumerate(source_facts or [])
    ]
    normalized_item_facts = [
        _validate_item_fact(row, index)
        for index, row in enumerate(item_facts or [])
    ]
    normalized_exclusions = [
        _validate_exclusion(row, index)
        for index, row in enumerate(exclusion_ledger or [])
    ]
    normalized_unresolved = [
        _validate_unresolved(row, index)
        for index, row in enumerate(unresolved_facts or [])
    ]

    statuses = [
        row["status"] for row in normalized_source_facts + normalized_item_facts
    ]
    if normalized_manifest["status"] == "blocked" or "blocked" in statuses:
        snapshot_status = "blocked"
    elif normalized_manifest["status"] == "partial" or normalized_unresolved:
        snapshot_status = "partial"
    else:
        snapshot_status = "verified"

    verified_fact_count = statuses.count("verified")
    unverified_count = statuses.count("UNVERIFIED") + len(
        [row for row in normalized_unresolved if row["status"] == "UNVERIFIED"]
    )
    blocked_count = statuses.count("blocked") + len(
        [row for row in normalized_unresolved if row["status"] == "blocked"]
    )
    excluded_by_reason: dict[str, int] = {}
    for row in normalized_exclusions:
        reason = row["reasonCode"]
        excluded_by_reason[reason] = excluded_by_reason.get(reason, 0) + 1

    entries = normalized_manifest["entries"]
    captured_times = [row["capturedAt"] for row in entries]
    namespaces = sorted({row["namespace"] for row in entries})
    capture_identity = {
        "captureManifestSha256": canonical_json_sha256(
            _manifest_identity(normalized_manifest)
        ),
        "region": normalized_manifest["region"],
        "locale": normalized_manifest["locale"],
        "namespaces": namespaces,
        "parserRevision": SNAPSHOT_SCHEMA_REVISION,
        "productContentScopeSha256": canonical_json_sha256(normalized_scope),
        "scopePolicySha256": canonical_json_sha256(normalized_fact_scope),
        "capturedAtRange": {
            "first": min(captured_times),
            "last": max(captured_times),
        },
    }
    payload = {
        "schemaRevision": SNAPSHOT_SCHEMA_REVISION,
        "status": snapshot_status,
        "seasonKey": SEASON_KEY,
        "productContentScopeRevision": normalized_scope[
            "productContentScopeRevision"
        ],
        "scopePolicyRevision": normalized_fact_scope["scopePolicyRevision"],
        "captureIdentity": capture_identity,
        "sourceFacts": normalized_source_facts,
        "itemFacts": normalized_item_facts,
        "exclusionLedger": normalized_exclusions,
        "unresolvedFacts": normalized_unresolved,
        "counts": {
            "officialScopeCandidateCountByKind": candidate_counts,
            "officialScopeAdmittedCountByKind": admitted_counts,
            "verifiedFactCount": verified_fact_count,
            "unverifiedCount": unverified_count,
            "blockedCount": blocked_count,
            "excludedCountByReason": dict(sorted(excluded_by_reason.items())),
            "simcReadyCountByKind": {kind: None for kind in LOGICAL_SOURCE_KINDS},
            "simcReadyCount": 0,
            "publicSimcReadyRate": None,
        },
    }
    revision_identity = {
        "schemaRevision": SNAPSHOT_SCHEMA_REVISION,
        "productContentScopeRevision": normalized_scope[
            "productContentScopeRevision"
        ],
        "scopePolicyRevision": normalized_fact_scope["scopePolicyRevision"],
        "productContentScopeSha256": capture_identity[
            "productContentScopeSha256"
        ],
        "scopePolicySha256": capture_identity["scopePolicySha256"],
        "captureManifestSha256": capture_identity["captureManifestSha256"],
        "parserRevision": capture_identity["parserRevision"],
        "sourceFacts": normalized_source_facts,
        "itemFacts": normalized_item_facts,
        "exclusionLedger": normalized_exclusions,
        "unresolvedFacts": normalized_unresolved,
        "counts": payload["counts"],
    }
    payload["officialApiFactSnapshotRevision"] = (
        SNAPSHOT_REVISION_PREFIX + _hash(revision_identity)
    )
    return payload

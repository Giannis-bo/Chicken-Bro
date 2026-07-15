#!/usr/bin/env python3
"""PostgreSQL repository for immutable WebSim release artifacts.

This is the sole SQL owner for Phase 4 release registry/content rows and the
retail manifest pointer. Existing WebSim tables remain mutable staging inputs.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from typing import Any, Iterable


RELEASE_SELECTED_ITEM_VARIANT_SQL = """
/* gear_release_authority_items_variants */
WITH target AS (
    SELECT %s::text AS release_id
), requested(item_id, variant_key) AS (
    SELECT * FROM unnest(%s::text[], %s::text[])
)
SELECT
    requested.item_id,
    requested.variant_key,
    CASE WHEN item.item_id IS NULL THEN NULL ELSE jsonb_build_object(
        'id', item.item_id,
        'name', item.name,
        'slot', item.slot,
        'itemLevel', item.item_level,
        'sourceStatus', item.source_status,
        'itemSetIds', COALESCE((
            SELECT jsonb_agg(DISTINCT COALESCE(
                NULLIF(set_source.payload_json->>'setId', ''),
                NULLIF(set_source.payload_json->>'set_id', ''),
                NULLIF(set_source.payload_json->>'itemSetId', ''),
                NULLIF(set_source.payload_json->>'item_set_id', '')
            ))
            FROM cache.websim_gear_release_sources set_source
            WHERE set_source.release_id = target.release_id
              AND set_source.item_id = requested.item_id
              AND set_source.source_type = 'tier_set'
        ), '[]'::jsonb),
        'payload', item.payload_json,
        'updatedAt', item.source_updated_at::text
    ) END AS item_record,
    CASE WHEN variant.variant_id IS NULL THEN NULL ELSE jsonb_build_object(
        'id', variant.variant_id,
        'itemId', variant.item_id,
        'slot', variant.slot,
        'variantKey', variant.variant_key,
        'label', variant.label,
        'sourceType', variant.source_type,
        'difficultyKey', variant.difficulty_key,
        'itemLevel', variant.item_level,
        'simcOptions', variant.simc_options_json,
        'status', variant.status,
        'blockers', variant.blockers_json,
        'payload', variant.payload_json,
        'updatedAt', variant.source_updated_at::text
    ) END AS variant_record,
    COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'id', source.source_id,
            'sourceType', source.source_type,
            'sourceKey', source.source_key,
            'sourceLabel', source.source_label,
            'instanceId', source.instance_id,
            'encounterId', source.encounter_id,
            'difficultyKey', source.difficulty_key,
            'seasonRevision', source.season_revision,
            'status', COALESCE(
                NULLIF(source.payload_json->>'status', ''),
                NULLIF(source.payload_json->>'sourceStatus', ''),
                'unknown'
            ),
            'sourceStatus', COALESCE(
                NULLIF(source.payload_json->>'sourceStatus', ''),
                'unknown'
            ),
            'payload', source.payload_json,
            'updatedAt', source.source_updated_at::text
        ) ORDER BY source.source_type, source.source_id)
        FROM (
            SELECT DISTINCT ON (candidate.source_type) candidate.*
            FROM cache.websim_gear_release_sources candidate
            WHERE candidate.release_id = target.release_id
              AND candidate.item_id = requested.item_id
            ORDER BY
                candidate.source_type,
                CASE WHEN
                    LOWER(COALESCE(candidate.payload_json->>'status', '')) = 'verified'
                    OR LOWER(COALESCE(candidate.payload_json->>'sourceStatus', '')) = 'verified'
                    OR (
                        candidate.source_type = 'observed_profile'
                        AND jsonb_array_length(
                            CASE
                                WHEN jsonb_typeof(candidate.payload_json->'itemStats') = 'array'
                                THEN candidate.payload_json->'itemStats'
                                ELSE '[]'::jsonb
                            END
                        ) > 0
                    )
                    OR (
                        candidate.source_type = 'tier_set'
                        AND candidate.payload_json->>'authority' = 'Battle.net Game Data API'
                    )
                    THEN 0 ELSE 1 END,
                CASE WHEN requested.variant_key <> '' AND LEFT(
                        regexp_replace(
                            COALESCE(candidate.payload_json->>'variantKey', ''),
                            '[^A-Za-z0-9_:/.-]+',
                            '',
                            'g'
                        ),
                        240
                    ) = requested.variant_key THEN 0 ELSE 1 END,
                candidate.source_updated_at DESC,
                candidate.source_id
            LIMIT 8
        ) source
    ), '[]'::jsonb) AS source_records
FROM requested
CROSS JOIN target
LEFT JOIN cache.websim_gear_release_items item
  ON item.release_id = target.release_id
 AND item.item_id = requested.item_id
LEFT JOIN cache.websim_gear_release_variants variant
  ON variant.release_id = target.release_id
 AND variant.item_id = requested.item_id
 AND (
      variant.variant_key = requested.variant_key
      OR LEFT(
          regexp_replace(variant.variant_key, '[^A-Za-z0-9_:/.-]+', '', 'g'),
          240
      ) = requested.variant_key
 )
ORDER BY requested.item_id, requested.variant_key
"""


RELEASE_SELECTED_OPTION_SQL = """
/* gear_release_authority_options */
WITH target AS (
    SELECT %s::text AS release_id
)
SELECT
    option.option_key,
    jsonb_build_object(
        'id', option.option_id,
        'optionKey', option.option_key,
        'optionType', option.option_type,
        'name', option.name,
        'applicableSlots', option.applicable_slots_json,
        'simcOptions', option.simc_options_json,
        'status', option.status,
        'isVisible', option.is_visible,
        'payload', option.payload_json,
        'updatedAt', option.source_updated_at::text
    ) AS option_record
FROM cache.websim_gear_release_mod_options option
CROSS JOIN target
WHERE option.release_id = target.release_id
  AND option.option_key = ANY(%s::text[])
ORDER BY option.option_key
"""


class GearReleaseIntegrityError(RuntimeError):
    pass


class StaleManifestPointerError(RuntimeError):
    pass


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _json_param(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _canonical_rows(rows: Any) -> list[dict[str, Any]]:
    values = [_canonical(row) for row in rows or [] if isinstance(row, dict)]
    return sorted(values, key=lambda row: _canonical_bytes(row))


def _selected_option_ids(selection_intent: Any) -> list[str]:
    intent = selection_intent if isinstance(selection_intent, dict) else {}
    selected = set()
    for selection in (intent.get("slots") or {}).values():
        if not isinstance(selection, dict):
            continue
        selected.update(_text(value) for value in selection.get("gemOptionIds") or [])
        selected.update(
            _text(selection.get(field))
            for field in (
                "enchantOptionId",
                "embellishmentOptionId",
                "craftedOptionId",
                "catalystOptionId",
            )
        )
    return sorted(value for value in selected if value)


def _public_enhancement_by_slot(selection_intent: Any) -> dict[str, dict[str, Any]]:
    """Project only canonical enhancement identities from a validated release intent."""

    intent = selection_intent if isinstance(selection_intent, dict) else {}
    slots = intent.get("slots") if isinstance(intent.get("slots"), dict) else {}
    result: dict[str, dict[str, Any]] = {}
    for slot, selection in slots.items():
        normalized_slot = _text(slot)
        if not normalized_slot or not isinstance(selection, dict):
            continue
        enhancement: dict[str, Any] = {}
        gem_option_ids = [
            _text(value)
            for value in selection.get("gemOptionIds") or []
            if _text(value)
        ]
        if gem_option_ids:
            enhancement["gemOptionIds"] = gem_option_ids
        for field in ("enchantOptionId", "embellishmentOptionId"):
            value = _text(selection.get(field))
            if value:
                enhancement[field] = value
        if enhancement:
            result[normalized_slot] = enhancement
    return _canonical(result)


def _observed_release_variant_record(
    requested_variant: str,
    item_record: Any,
    source_records: Any,
) -> dict[str, Any] | None:
    """Project an exact observed variant from immutable release source evidence."""

    try:
        from .websim_payload import (
            normalize_option_value,
            observed_gear_simc_options,
            observed_item_level,
            observed_variant_stat_payload_fields,
        )
    except ImportError:
        from websim_payload import (
            normalize_option_value,
            observed_gear_simc_options,
            observed_item_level,
            observed_variant_stat_payload_fields,
        )

    requested = _text(requested_variant)
    item = item_record if isinstance(item_record, dict) else {}
    for source in source_records if isinstance(source_records, list) else []:
        if not isinstance(source, dict):
            continue
        payload = source.get("payload") if isinstance(source.get("payload"), dict) else {}
        source_type = _text(source.get("sourceType") or payload.get("sourceType"))
        if source_type != "observed_profile":
            continue
        if normalize_option_value(payload.get("variantKey")) != requested:
            continue
        item_level = observed_item_level(payload) or _int(item.get("itemLevel"))
        simc_options = observed_gear_simc_options(payload)
        if item_level:
            simc_options = {"ilevel": str(item_level), **simc_options}
        status = _text(source.get("status")).lower()
        if status != "verified" and observed_variant_stat_payload_fields(payload):
            status = "verified"
        return {
            "id": _text(source.get("id")),
            "itemId": _text(payload.get("itemId") or payload.get("id") or item.get("id")),
            "slot": _text(payload.get("slot") or payload.get("simcSlot") or item.get("slot")),
            "variantKey": requested,
            "label": _text(payload.get("displayName") or payload.get("name") or source.get("sourceLabel")),
            "sourceType": source_type,
            "difficultyKey": _text(source.get("difficultyKey") or payload.get("difficultyKey") or "observed_profile"),
            "itemLevel": item_level,
            "simcOptions": simc_options,
            "status": status or "unknown",
            "blockers": _canonical(payload.get("blockers") if isinstance(payload.get("blockers"), list) else []),
            "payload": _canonical(payload),
            "updatedAt": _text(source.get("updatedAt")),
        }
    return None


def _verified_release_source_records(source_records: Any) -> list[dict[str, Any]]:
    """Normalize immutable observed stat evidence into the existing verified-source contract."""

    try:
        from .websim_payload import observed_variant_stat_payload_fields
    except ImportError:
        from websim_payload import observed_variant_stat_payload_fields

    normalized = []
    for raw in source_records if isinstance(source_records, list) else []:
        if not isinstance(raw, dict):
            continue
        source = _canonical(raw)
        payload = source.get("payload") if isinstance(source.get("payload"), dict) else {}
        statuses = {
            _text(source.get("status")).lower(),
            _text(source.get("sourceStatus")).lower(),
        }
        if (
            _text(source.get("sourceType")) == "observed_profile"
            and not statuses.intersection({"blocked", "rejected", "expired"})
            and observed_variant_stat_payload_fields(payload)
        ):
            source["status"] = "verified"
        normalized.append(source)
    return normalized


def canonical_row_hash(row: dict[str, Any]) -> str:
    return _hash(_canonical(row))


def gear_snapshot_summary(snapshot: Any) -> dict[str, Any]:
    value = snapshot if isinstance(snapshot, dict) else {}
    canonical = {
        key: _canonical_rows(value.get(key))
        for key in ("items", "sources", "variants", "options")
    }
    return {
        "schemaRevision": "gear-release-content-v1",
        "snapshotHash": _hash(canonical),
        "counts": {key: len(canonical[key]) for key in canonical},
    }


def community_rows_summary(rows: Any) -> dict[str, Any]:
    canonical = _canonical_rows(rows)
    role_counts = {role: 0 for role in ("winner", "standby", "rejected")}
    winner_specs = []
    for row in canonical:
        role = _text(row.get("role"))
        if role in role_counts:
            role_counts[role] += 1
        if role == "winner":
            winner_specs.append({
                "classKey": _text(row.get("classKey")),
                "specKey": _text(row.get("specKey")),
            })
    winner_specs.sort(key=lambda row: (row["classKey"], row["specKey"]))
    return {
        "schemaRevision": "community-release-content-v1",
        "snapshotHash": _hash(canonical),
        "counts": {"total": len(canonical), **role_counts},
        "winnerSpecs": winner_specs,
    }


def _expected_manifest_revision(manifest: dict[str, Any]) -> str:
    identity = {
        "schemaRevision": manifest.get("schemaRevision"),
        "seasonRevision": manifest.get("seasonRevision"),
        "gearCatalogReleaseId": manifest.get("gearCatalogReleaseId"),
        "communityTemplateReleaseId": manifest.get("communityTemplateReleaseId") or "",
        "talentCatalogRevision": manifest.get("talentCatalogRevision"),
        "dependencyRevisions": manifest.get("dependencyRevisions"),
        "rollbackManifestRevision": manifest.get("rollbackManifestRevision") or "",
        "formalActiveManifest": bool(manifest.get("formalActiveManifest")),
    }
    return "season-manifest:" + _hash(identity)


class CandidateGearAuthorityIndex:
    """One validated, reusable index over an exact candidate Gear snapshot."""

    def __init__(self, snapshot: dict[str, Any], gear_release: dict[str, Any]):
        self.release = _exact_release_descriptor(gear_release)
        if self.release["releaseKind"] != "gear":
            raise GearReleaseIntegrityError("candidate authority requires a Gear Release")
        self.snapshot_summary = gear_snapshot_summary(snapshot)
        if self.snapshot_summary != self.release["content"]:
            raise GearReleaseIntegrityError("candidate authority snapshot does not match Gear Release")
        self.items = {
            _text(row.get("itemId")): row
            for row in _canonical_rows(snapshot.get("items"))
        }
        self.sources_by_item: dict[str, list[dict[str, Any]]] = {}
        for row in _canonical_rows(snapshot.get("sources")):
            self.sources_by_item.setdefault(_text(row.get("itemId")), []).append(row)
        self.variants_by_item: dict[str, list[dict[str, Any]]] = {}
        for row in _canonical_rows(snapshot.get("variants")):
            self.variants_by_item.setdefault(_text(row.get("itemId")), []).append(row)
        self.options_by_key = {
            _text(row.get("optionKey")): row
            for row in _canonical_rows(snapshot.get("options"))
            if _text(row.get("optionKey"))
        }


def build_candidate_authority_context(
    snapshot: dict[str, Any],
    selection_intent: dict[str, Any],
    runtime_authority: dict[str, Any],
    gear_release: dict[str, Any],
    *,
    prepared_index: CandidateGearAuthorityIndex | None = None,
) -> dict[str, Any]:
    """Build an inactive candidate Authority Context from an exact sealed snapshot."""

    try:
        from .pg_gear_authority_loader import build_gear_authority_context_from_rows
        from .websim_payload import normalize_option_value
    except ImportError:
        from pg_gear_authority_loader import build_gear_authority_context_from_rows
        from websim_payload import normalize_option_value

    release = _exact_release_descriptor(gear_release)
    prepared = prepared_index or CandidateGearAuthorityIndex(snapshot, release)
    if prepared.release != release:
        raise GearReleaseIntegrityError("prepared candidate authority does not match Gear Release")
    authored = selection_intent.get("authoredAgainst") if isinstance(selection_intent, dict) else {}
    if not isinstance(authored, dict) or authored.get("seasonRevision") != release["seasonRevision"] or authored.get("gearCatalogRevision") != release["releaseId"]:
        raise GearReleaseIntegrityError("candidate Intent is not authored against the Gear Release")

    items = prepared.items
    sources_by_item = prepared.sources_by_item
    variants_by_item = prepared.variants_by_item
    options_by_key = prepared.options_by_key

    item_rows = []
    for selection in (selection_intent.get("slots") or {}).values():
        if not isinstance(selection, dict):
            continue
        item_id = _text(selection.get("itemId"))
        requested_variant = _text(selection.get("variantKey"))
        item = items.get(item_id)
        item_record = None
        if isinstance(item, dict):
            item_record = {
                "id": item_id,
                "name": item.get("name") or "",
                "slot": item.get("slot") or "",
                "itemLevel": item.get("itemLevel"),
                "sourceStatus": item.get("sourceStatus") or "unknown",
                "itemSetIds": [],
                "payload": item.get("payload") or {},
                "updatedAt": item.get("updatedAt") or "",
            }
        source_records = [
            {
                "id": source.get("sourceId") or "",
                "sourceType": source.get("sourceType") or "",
                "sourceKey": source.get("sourceKey") or "",
                "sourceLabel": source.get("sourceLabel") or "",
                "instanceId": source.get("instanceId") or "",
                "encounterId": source.get("encounterId") or "",
                "difficultyKey": source.get("difficultyKey") or "",
                "seasonRevision": source.get("seasonRevision") or "",
                "status": (source.get("payload") or {}).get("status") or "unknown",
                "sourceStatus": (source.get("payload") or {}).get("sourceStatus") or "unknown",
                "payload": source.get("payload") or {},
                "updatedAt": source.get("updatedAt") or "",
            }
            for source in sources_by_item.get(item_id, [])
        ]
        source_records = _verified_release_source_records(source_records)
        matching = [
            row for row in variants_by_item.get(item_id, [])
            if requested_variant
            and (
                _text(row.get("variantKey")) == requested_variant
                or normalize_option_value(row.get("variantKey")) == requested_variant
            )
        ]
        exact = [
            row
            for row in matching
            if _text(row.get("variantKey")) == requested_variant
        ]
        if exact:
            matching = exact
        if not matching:
            matching = [None]
        for variant in matching:
            variant_record = None
            if isinstance(variant, dict):
                variant_record = {
                    "id": variant.get("variantId") or "",
                    "itemId": item_id,
                    "slot": variant.get("slot") or "",
                    "variantKey": variant.get("variantKey") or "",
                    "label": variant.get("label") or "",
                    "sourceType": variant.get("sourceType") or "",
                    "difficultyKey": variant.get("difficultyKey") or "",
                    "itemLevel": variant.get("itemLevel") or 0,
                    "simcOptions": variant.get("simcOptions") or {},
                    "status": variant.get("status") or "blocked",
                    "blockers": variant.get("blockers") or [],
                    "payload": variant.get("payload") or {},
                    "updatedAt": variant.get("updatedAt") or "",
                }
            if variant_record is None:
                variant_record = _observed_release_variant_record(
                    requested_variant,
                    item_record,
                    source_records,
                )
            item_rows.append((item_id, requested_variant, item_record, variant_record, source_records))

    selected_option_ids = set()
    for selection in (selection_intent.get("slots") or {}).values():
        if not isinstance(selection, dict):
            continue
        selected_option_ids.update(_text(value) for value in selection.get("gemOptionIds") or [])
        selected_option_ids.update(
            _text(selection.get(field))
            for field in ("enchantOptionId", "embellishmentOptionId", "craftedOptionId", "catalystOptionId")
        )
    selected_option_ids.discard("")
    option_rows = []
    for option_id in sorted(selected_option_ids):
        option = options_by_key.get(option_id)
        record = None
        if isinstance(option, dict):
            record = {
                "id": option.get("optionId") or "",
                "optionKey": option_id,
                "optionType": option.get("optionType") or "",
                "name": option.get("name") or "",
                "applicableSlots": option.get("applicableSlots") or [],
                "simcOptions": option.get("simcOptions") or {},
                "status": option.get("status") or "blocked",
                "isVisible": option.get("isVisible") is True,
                "payload": option.get("payload") or {},
                "updatedAt": option.get("updatedAt") or "",
            }
        option_rows.append((option_id, record))

    dependencies = {
        "seasonRevision": release["seasonRevision"],
        "gearCatalogReleaseId": release["releaseId"],
        "gearCatalogRevision": release["releaseId"],
        **_canonical(release.get("dependencyRevisions") or {}),
    }
    return build_gear_authority_context_from_rows(
        selection_intent,
        runtime_authority,
        manifest={
            "contractRevision": "active-season-manifest-v1",
            "manifestType": "candidate",
            "formalActiveManifest": False,
            "seasonRevision": release["seasonRevision"],
            "gearCatalogReleaseId": release["releaseId"],
            "gearCatalogRevision": release["releaseId"],
            "catalogFingerprint": release["contentHash"],
            "sourceStates": {"releaseStatus": release["releaseStatus"]},
        },
        dependency_vector=dependencies,
        item_rows=item_rows,
        option_rows=option_rows,
    )


def _release_from_row(row: Any) -> dict[str, Any] | None:
    if not row:
        return None
    values = list(row)
    return {
        "schemaRevision": _text(values[3] if len(values) > 3 else ""),
        "releaseId": _text(values[0] if len(values) > 0 else ""),
        "releaseKind": _text(values[1] if len(values) > 1 else ""),
        "seasonRevision": _text(values[2] if len(values) > 2 else ""),
        "contentHash": _text(values[4] if len(values) > 4 else ""),
        "dependencyRevisions": _canonical(values[8] if len(values) > 8 and isinstance(values[8], dict) else {}),
        "releaseStatus": _text(values[7] if len(values) > 7 else ""),
        "parentReleaseId": _text(values[5] if len(values) > 5 else ""),
        "validatedAgainstReleaseId": _text(values[6] if len(values) > 6 else ""),
        "source": _canonical(values[10] if len(values) > 10 and isinstance(values[10], dict) else {}),
        "content": _canonical(values[11] if len(values) > 11 else {}),
    }


def _exact_release_descriptor(release: Any) -> dict[str, Any]:
    if not isinstance(release, dict):
        raise GearReleaseIntegrityError("release descriptor must be an object")
    try:
        from . import gear_release
    except ImportError:
        import gear_release
    issues = gear_release.validate_release(release)
    if issues:
        raise GearReleaseIntegrityError(
            "release descriptor integrity failed: "
            + ", ".join(_text(issue.get("code")) for issue in issues)
        )
    fields = (
        "schemaRevision",
        "releaseId",
        "releaseKind",
        "seasonRevision",
        "contentHash",
        "dependencyRevisions",
        "releaseStatus",
        "parentReleaseId",
        "validatedAgainstReleaseId",
        "source",
        "content",
    )
    descriptor = {field: _canonical(release.get(field)) for field in fields}
    for field in ("schemaRevision", "releaseId", "releaseKind", "seasonRevision", "contentHash", "releaseStatus"):
        descriptor[field] = _text(descriptor[field])
    for field in ("parentReleaseId", "validatedAgainstReleaseId"):
        descriptor[field] = _text(descriptor[field])
    for field in ("dependencyRevisions", "source"):
        descriptor[field] = descriptor[field] if isinstance(descriptor[field], dict) else {}
    return descriptor


class GearReleaseStore:
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    @contextmanager
    def connection(self):
        conn = self.connection_factory()
        try:
            yield conn
            if hasattr(conn, "commit"):
                conn.commit()
        except Exception:
            if hasattr(conn, "rollback"):
                conn.rollback()
            raise
        finally:
            if hasattr(conn, "close"):
                conn.close()

    def snapshot_staging_gear(self) -> dict[str, list[dict[str, Any]]]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cur.execute(
                    """
                    SELECT id, name, slot, item_level, payload_json, source_status, updated_at
                    FROM cache.websim_items
                    ORDER BY id
                    """
                )
                item_rows = cur.fetchall()
                cur.execute(
                    """
                    SELECT id::text, item_id, source_type, source_key, source_label, instance_id,
                           encounter_id, difficulty_key, season_revision, payload_json, updated_at
                    FROM cache.websim_gear_sources
                    ORDER BY id::text
                    """
                )
                source_rows = cur.fetchall()
                cur.execute(
                    """
                    SELECT id::text, item_id, variant_key, slot, label, source_type, difficulty_key,
                           item_level, simc_options_json, status, blockers_json, payload_json, updated_at
                    FROM cache.websim_gear_variants
                    ORDER BY id::text
                    """
                )
                variant_rows = cur.fetchall()
                cur.execute(
                    """
                    SELECT id::text, variant_id::text, option_key, option_type, name,
                           applicable_slots_json, simc_options_json, status, is_visible,
                           payload_json, updated_at
                    FROM cache.websim_gear_mod_options
                    ORDER BY id::text
                    """
                )
                option_rows = cur.fetchall()
        return {
            "items": [
                {
                    "itemId": _text(row[0]),
                    "name": _text(row[1]),
                    "slot": _text(row[2]),
                    "itemLevel": row[3],
                    "payload": _canonical(row[4] if isinstance(row[4], dict) else {}),
                    "sourceStatus": _text(row[5]),
                    "updatedAt": _text(row[6]),
                }
                for row in item_rows
            ],
            "sources": [
                {
                    "sourceId": _text(row[0]),
                    "itemId": _text(row[1]),
                    "sourceType": _text(row[2]),
                    "sourceKey": _text(row[3]),
                    "sourceLabel": _text(row[4]),
                    "instanceId": _text(row[5]),
                    "encounterId": _text(row[6]),
                    "difficultyKey": _text(row[7]),
                    "seasonRevision": _text(row[8]),
                    "payload": _canonical(row[9] if isinstance(row[9], dict) else {}),
                    "updatedAt": _text(row[10]),
                }
                for row in source_rows
            ],
            "variants": [
                {
                    "variantId": _text(row[0]),
                    "itemId": _text(row[1]),
                    "variantKey": _text(row[2]),
                    "slot": _text(row[3]),
                    "label": _text(row[4]),
                    "sourceType": _text(row[5]),
                    "difficultyKey": _text(row[6]),
                    "itemLevel": _int(row[7]),
                    "simcOptions": _canonical(row[8] if isinstance(row[8], dict) else {}),
                    "status": _text(row[9]),
                    "blockers": _canonical(row[10] if isinstance(row[10], list) else []),
                    "payload": _canonical(row[11] if isinstance(row[11], dict) else {}),
                    "updatedAt": _text(row[12]),
                }
                for row in variant_rows
            ],
            "options": [
                {
                    "optionId": _text(row[0]),
                    "variantId": _text(row[1]),
                    "optionKey": _text(row[2]),
                    "optionType": _text(row[3]),
                    "name": _text(row[4]),
                    "applicableSlots": _canonical(row[5] if isinstance(row[5], list) else []),
                    "simcOptions": _canonical(row[6] if isinstance(row[6], dict) else {}),
                    "status": _text(row[7]),
                    "isVisible": row[8] is True,
                    "payload": _canonical(row[9] if isinstance(row[9], dict) else {}),
                    "updatedAt": _text(row[10]),
                }
                for row in option_rows
            ],
        }

    def snapshot_staging_community_templates(
        self,
        expected_specs: Iterable[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        specs = sorted({
            (_text(class_key), _text(spec_key))
            for class_key, spec_key in expected_specs
            if _text(class_key) and _text(spec_key)
        })
        if not specs or len(specs) > 40:
            raise GearReleaseIntegrityError("community snapshot requires 1 to 40 explicit specs")
        class_keys = [class_key for class_key, _spec_key in specs]
        spec_keys = [spec_key for _class_key, spec_key in specs]
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cur.execute(
                    """
                    WITH expected(class_key, spec_key) AS (
                        SELECT * FROM unnest(%s::text[], %s::text[])
                    ), ranked AS (
                        SELECT template.id, template.class_key, template.spec_key, template.name,
                               template.source_key, template.source_name, template.source_url,
                               template.source_status, template.status, template.signature,
                               template.source_refs_json, template.gear_items_json,
                               template.raw_string, template.ready_slot_count,
                               template.missing_slots_json, template.analysis_window,
                               template.payload_json, template.updated_at, template.expires_at,
                               template.scan_run_id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY template.class_key, template.spec_key
                                   ORDER BY template.status, template.ready_slot_count DESC,
                                            template.updated_at DESC, template.id
                               ) AS candidate_rank
                        FROM cache.websim_community_gear_templates AS template
                        INNER JOIN expected
                          ON expected.class_key = template.class_key
                         AND expected.spec_key = template.spec_key
                    )
                    SELECT id, class_key, spec_key, name, source_key, source_name, source_url,
                           source_status, status, signature, source_refs_json, gear_items_json,
                           raw_string, ready_slot_count, missing_slots_json, analysis_window,
                           payload_json, updated_at, expires_at, scan_run_id
                    FROM ranked
                    WHERE candidate_rank <= 10
                    ORDER BY class_key, spec_key, candidate_rank, id
                    LIMIT 400
                    """,
                    (class_keys, spec_keys),
                )
                rows = cur.fetchall()
        return [
            {
                "templateId": _text(row[0]),
                "classKey": _text(row[1]),
                "specKey": _text(row[2]),
                "name": _text(row[3]),
                "sourceKey": _text(row[4]),
                "sourceName": _text(row[5]),
                "sourceUrl": _text(row[6]),
                "sourceStatus": _text(row[7]),
                "status": _text(row[8]),
                "signature": _text(row[9]),
                "sourceRefs": _canonical(row[10] if isinstance(row[10], list) else []),
                "gearItems": _canonical(row[11] if isinstance(row[11], list) else []),
                "rawString": _text(row[12]),
                "readySlotCount": _int(row[13]),
                "missingSlots": _canonical(row[14] if isinstance(row[14], list) else []),
                "analysisWindow": _text(row[15]),
                "payload": _canonical(row[16] if isinstance(row[16], dict) else {}),
                "updatedAt": _text(row[17]),
                "expiresAt": _text(row[18]),
                "scanRunId": _text(row[19]),
            }
            for row in rows
        ]

    @staticmethod
    def _select_release(cur, release_id: str) -> dict[str, Any] | None:
        cur.execute(
            """
            SELECT release_id, release_kind, season_revision, schema_revision, content_hash,
                   parent_release_id, validated_against_release_id, release_status,
                   dependency_vector_json, gate_result_json, source_json, content_summary_json
            FROM cache.websim_release_registry
            WHERE release_id = %s
            """,
            (release_id,),
        )
        return _release_from_row(cur.fetchone())

    def get_release(self, release_id: str) -> dict[str, Any]:
        normalized = _text(release_id)
        if not normalized:
            return {}
        with self.connection() as conn:
            with conn.cursor() as cur:
                release = self._select_release(cur, normalized)
        return release or {}

    def get_gear_release_row_hashes(self, release_id: str) -> dict[str, dict[str, str]]:
        """Read only immutable identity/hash pairs for additive risk classification."""

        normalized = _text(release_id)
        if not normalized:
            raise GearReleaseIntegrityError("Gear Release ID is required")
        queries = (
            ("items", "SELECT item_id, row_hash FROM cache.websim_gear_release_items WHERE release_id = %s"),
            ("sources", "SELECT source_id, row_hash FROM cache.websim_gear_release_sources WHERE release_id = %s"),
            ("variants", "SELECT variant_id, row_hash FROM cache.websim_gear_release_variants WHERE release_id = %s"),
            ("options", "SELECT option_id, row_hash FROM cache.websim_gear_release_mod_options WHERE release_id = %s"),
        )
        result: dict[str, dict[str, str]] = {}
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                for category, statement in queries:
                    cur.execute(statement, (normalized,))
                    result[category] = {
                        _text(identity): _text(row_hash)
                        for identity, row_hash in cur.fetchall()
                        if _text(identity) and _text(row_hash)
                    }
        return result

    def record_refresh_event(
        self,
        event_type: str,
        event: dict[str, Any],
        *,
        release_id: str = "",
        manifest_revision: str = "",
    ) -> None:
        normalized_type = _text(event_type)
        if normalized_type not in {
            "gear_release_refresh_started",
            "gear_release_refresh_completed",
            "gear_release_refresh_failed",
            "gear_release_refresh_lease_conflict",
        }:
            raise GearReleaseIntegrityError("unsupported release refresh event type")
        with self.connection() as conn:
            with conn.cursor() as cur:
                self._insert_event(
                    cur,
                    release_id=_text(release_id),
                    manifest_revision=_text(manifest_revision),
                    event_type=normalized_type,
                    event=_canonical(event if isinstance(event, dict) else {}),
                )

    def latest_refresh_state(self) -> dict[str, Any]:
        """Expose one bounded latest-run projection without raw operator data."""

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """
                    SELECT event_type, event_json, created_at, release_id, manifest_revision
                    FROM cache.websim_release_events
                    WHERE event_type LIKE 'gear_release_refresh_%'
                    ORDER BY created_at DESC, event_id DESC
                    LIMIT 1
                    """
                )
                row = cur.fetchone()
        if not row:
            return {}
        event_type, payload, created_at, release_id, manifest_revision = row
        payload = payload if isinstance(payload, dict) else {}
        gear_change = payload.get("gearChange") if isinstance(payload.get("gearChange"), dict) else {}
        seal_status = payload.get("sealStatus") if isinstance(payload.get("sealStatus"), dict) else {}
        shadow_performance = (
            payload.get("shadowPerformance")
            if isinstance(payload.get("shadowPerformance"), dict)
            else {}
        )
        return {
            "eventType": _text(event_type),
            "status": _text(payload.get("status")),
            "checkedAt": _text(created_at),
            "gearReleaseId": _text(payload.get("gearReleaseId")),
            "communityReleaseId": _text(payload.get("communityReleaseId") or release_id),
            "manifestRevision": _text(payload.get("manifestRevision") or manifest_revision),
            "riskClass": _text(payload.get("riskClass")),
            "decision": _text(payload.get("decision")),
            "blockerCodes": [
                _text(code)
                for code in (payload.get("blockerCodes") or [])[:16]
                if _text(code)
            ],
            "counts": _canonical(payload.get("counts") if isinstance(payload.get("counts"), dict) else {}),
            "gearChange": _canonical({
                change_kind: {
                    category: _int((gear_change.get(change_kind) or {}).get(category))
                    for category in ("items", "sources", "variants", "options")
                }
                for change_kind in ("addedCounts", "changedCounts", "removedCounts")
            }),
            "sealStatus": {
                "gear": _text(seal_status.get("gear")),
                "community": _text(seal_status.get("community")),
            },
            "shadowStatus": _text(payload.get("shadowStatus")),
            "shadowSpecCount": _int(payload.get("shadowSpecCount")),
            "shadowPerformance": {
                key: value
                for key in ("specP95Ms", "specMaxMs", "totalDurationMs")
                if isinstance((value := shadow_performance.get(key)), (int, float))
            },
        }

    def load_candidate_authority_context(
        self,
        selection_intent: dict[str, Any],
        runtime_authority: dict[str, Any],
        gear_release_id: str,
    ) -> dict[str, Any]:
        """Read selected authority facts from one exact inactive Gear Release."""

        try:
            from .pg_gear_authority_loader import build_gear_authority_context_from_rows
        except ImportError:
            from pg_gear_authority_loader import build_gear_authority_context_from_rows

        release_id = _text(gear_release_id)
        intent = selection_intent if isinstance(selection_intent, dict) else {}
        slots = intent.get("slots") if isinstance(intent.get("slots"), dict) else {}
        requested_pairs = list(dict.fromkeys(
            (_text(selection.get("itemId")), _text(selection.get("variantKey")))
            for selection in slots.values()
            if isinstance(selection, dict)
        ))
        item_ids = [item_id for item_id, _variant_key in requested_pairs]
        variant_keys = [variant_key for _item_id, variant_key in requested_pairs]
        option_ids = _selected_option_ids(intent)

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                release = self._select_release(cur, release_id)
                if release is None:
                    raise GearReleaseIntegrityError("candidate Gear Release is missing")
                release = _exact_release_descriptor(release)
                if release["releaseKind"] != "gear":
                    raise GearReleaseIntegrityError("candidate authority requires a Gear Release")
                authored = intent.get("authoredAgainst") if isinstance(intent.get("authoredAgainst"), dict) else {}
                if (
                    authored.get("seasonRevision") != release["seasonRevision"]
                    or authored.get("gearCatalogRevision") != release["releaseId"]
                ):
                    raise GearReleaseIntegrityError("candidate Intent is not authored against the Gear Release")
                cur.execute(
                    RELEASE_SELECTED_ITEM_VARIANT_SQL,
                    (release_id, item_ids, variant_keys),
                )
                selected_item_rows = list(cur.fetchall())
                # Exact immutable identity wins. Normalized aliases are retained
                # only when no exact row exists, so alias-only conflicts still
                # reach the loader's fail-closed equivalence check.
                exact_variant_pairs = {
                    (_text(row[0]), _text(row[1]))
                    for row in selected_item_rows
                    if len(row or ()) > 3
                    and isinstance(row[3], dict)
                    and _text(row[3].get("variantKey")) == _text(row[1])
                }
                item_rows = []
                for row in selected_item_rows:
                    values = list(row or ())
                    while len(values) < 5:
                        values.append(None)
                    pair = (_text(values[0]), _text(values[1]))
                    if (
                        pair in exact_variant_pairs
                        and (
                            not isinstance(values[3], dict)
                            or _text(values[3].get("variantKey")) != pair[1]
                        )
                    ):
                        continue
                    values[4] = _verified_release_source_records(values[4])
                    if values[3] is None:
                        values[3] = _observed_release_variant_record(
                            _text(values[1]),
                            values[2],
                            values[4],
                        )
                    item_rows.append(tuple(values[:5]))
                cur.execute(RELEASE_SELECTED_OPTION_SQL, (release_id, option_ids))
                option_rows = cur.fetchall()

        dependencies = {
            "seasonRevision": release["seasonRevision"],
            "gearCatalogReleaseId": release["releaseId"],
            "gearCatalogRevision": release["releaseId"],
            **_canonical(release.get("dependencyRevisions") or {}),
        }
        return build_gear_authority_context_from_rows(
            intent,
            runtime_authority,
            manifest={
                "contractRevision": "active-season-manifest-v1",
                "manifestType": "candidate_shadow",
                "manifestRevision": f"candidate-shadow:{release['releaseId']}",
                "formalActiveManifest": False,
                "seasonRevision": release["seasonRevision"],
                "gearCatalogReleaseId": release["releaseId"],
                "gearCatalogRevision": release["releaseId"],
                "catalogFingerprint": release["contentHash"],
                "sourceStates": {"releaseStatus": release["releaseStatus"]},
            },
            dependency_vector=dependencies,
            item_rows=item_rows,
            option_rows=option_rows,
        )

    @staticmethod
    def _active_runtime_dependencies(binding: dict[str, Any], runtime_authority: dict[str, Any]) -> dict[str, Any]:
        manifest = binding.get("manifest") if isinstance(binding.get("manifest"), dict) else {}
        manifest_dependencies = (
            manifest.get("dependencyRevisions")
            if isinstance(manifest.get("dependencyRevisions"), dict)
            else {}
        )
        runtime_dependencies = (
            runtime_authority.get("dependencyRevisions")
            if isinstance(runtime_authority, dict)
            and isinstance(runtime_authority.get("dependencyRevisions"), dict)
            else {}
        )
        required = (
            "gearRuleRevision",
            "resolverContractRevision",
            "serializerRevision",
            "simcRuntimeRevision",
            "statPolicyRevision",
            "selectionSchemaRevision",
        )
        mismatched = [
            field
            for field in required
            if not _text(manifest_dependencies.get(field))
            or _text(runtime_dependencies.get(field)) != _text(manifest_dependencies.get(field))
        ]
        supported_capability_revisions = (
            runtime_authority.get("supportedCapabilityRevisions")
            if isinstance(runtime_authority, dict)
            and isinstance(runtime_authority.get("supportedCapabilityRevisions"), (list, tuple))
            else []
        )
        supported_capability_revisions = {
            _text(revision)
            for revision in supported_capability_revisions
            if _text(revision)
        }
        manifest_capability_revision = _text(
            manifest_dependencies.get("capabilityRevision")
        )
        runtime_capability_revision = _text(
            runtime_dependencies.get("capabilityRevision")
        )
        if (
            not manifest_capability_revision
            or not runtime_capability_revision
            or runtime_capability_revision not in supported_capability_revisions
            or manifest_capability_revision not in supported_capability_revisions
        ):
            mismatched.append("capabilityRevision")
        if mismatched:
            raise GearReleaseIntegrityError(
                "active runtime dependencies do not match the Manifest: " + ", ".join(mismatched)
            )
        return _canonical(manifest_dependencies)

    def active_resolver_context(
        self,
        binding: dict[str, Any],
        runtime_authority: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(binding, dict) or binding.get("formalActiveManifest") is not True:
            raise GearReleaseIntegrityError("formal active Manifest binding is required")
        manifest = binding.get("manifest") if isinstance(binding.get("manifest"), dict) else {}
        dependencies = self._active_runtime_dependencies(binding, runtime_authority)
        return _canonical({
            "contractRevision": "gear-resolver-context-v1",
            "formalActiveManifest": True,
            "manifestRevision": _text(manifest.get("manifestRevision")),
            "pointerGeneration": _int(binding.get("generation")),
            "selectionSchemaRevision": _text(dependencies.get("selectionSchemaRevision")),
            "authoredAgainst": {
                "seasonRevision": _text(manifest.get("seasonRevision")),
                "gearCatalogRevision": _text(manifest.get("gearCatalogReleaseId")),
            },
            "dependencyRevisions": {
                field: _text(dependencies.get(field))
                for field in (
                    "gearRuleRevision",
                    "resolverContractRevision",
                    "serializerRevision",
                    "simcRuntimeRevision",
                    "statPolicyRevision",
                    "selectionSchemaRevision",
                    "capabilityRevision",
                )
            },
        })

    def load_active_authority_context(
        self,
        selection_intent: dict[str, Any],
        runtime_authority: dict[str, Any],
        binding: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(binding, dict) or binding.get("formalActiveManifest") is not True:
            raise GearReleaseIntegrityError("formal active Manifest binding is required")
        manifest = binding.get("manifest") if isinstance(binding.get("manifest"), dict) else {}
        gear_release_id = _text(manifest.get("gearCatalogReleaseId"))
        dependencies = self._active_runtime_dependencies(binding, runtime_authority)
        # The exact-release reader is intentionally strict for inactive shadow
        # calls.  Active Resolve must still be able to read current authority
        # for an older Intent so the pure resolver can return a truthful 409
        # with the current release context instead of collapsing to a 503.
        authority_read_intent = _canonical(
            selection_intent if isinstance(selection_intent, dict) else {}
        )
        authority_read_intent["authoredAgainst"] = {
            "seasonRevision": _text(manifest.get("seasonRevision")),
            "gearCatalogRevision": gear_release_id,
        }
        context = self.load_candidate_authority_context(
            authority_read_intent,
            runtime_authority,
            gear_release_id,
        )
        context = _canonical(context)
        gear_release = binding.get("gearRelease") if isinstance(binding.get("gearRelease"), dict) else {}
        context["manifest"] = {
            "contractRevision": "active-season-manifest-v1",
            "manifestType": "retail",
            "manifestRevision": _text(manifest.get("manifestRevision")),
            "formalActiveManifest": True,
            "pointerGeneration": _int(binding.get("generation")),
            "seasonRevision": _text(manifest.get("seasonRevision")),
            "gearCatalogReleaseId": gear_release_id,
            "gearCatalogRevision": gear_release_id,
            "communityTemplateReleaseId": _text(manifest.get("communityTemplateReleaseId")),
            "talentCatalogRevision": _text(manifest.get("talentCatalogRevision")),
            "catalogFingerprint": _text(gear_release.get("contentHash")),
            "sourceStates": {"releaseStatus": _text(gear_release.get("releaseStatus"))},
        }
        context["dependencyVector"] = {
            "seasonRevision": _text(manifest.get("seasonRevision")),
            "gearCatalogReleaseId": gear_release_id,
            "gearCatalogRevision": gear_release_id,
            **dependencies,
        }
        return _canonical(context)

    def load_active_public_gear(
        self,
        binding: dict[str, Any],
        class_key: str,
        spec_key: str,
        *,
        include_catalog: bool,
        catalog_slot: str = "",
    ) -> dict[str, Any]:
        """Read public gear facts only from the immutable Releases in one active binding."""

        if not isinstance(binding, dict) or binding.get("formalActiveManifest") is not True:
            raise GearReleaseIntegrityError("formal active Manifest binding is required")
        manifest = binding.get("manifest") if isinstance(binding.get("manifest"), dict) else {}
        gear = _exact_release_descriptor(binding.get("gearRelease"))
        gear_id = _text(manifest.get("gearCatalogReleaseId"))
        if gear_id != gear["releaseId"]:
            raise GearReleaseIntegrityError("active public Gear Release does not match the Manifest")
        community_id = _text(manifest.get("communityTemplateReleaseId"))
        community = None
        if community_id:
            community = _exact_release_descriptor(binding.get("communityRelease"))
            if community_id != community["releaseId"] or community["validatedAgainstReleaseId"] != gear_id:
                raise GearReleaseIntegrityError("active public Community Release does not match the Manifest")

        snapshot = {"items": [], "sources": [], "variants": [], "options": []}
        community_templates = []
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cur.execute(
                    """
                    /* gear_release_public_counts */
                    SELECT
                        (SELECT COUNT(*) FROM cache.websim_gear_release_items WHERE release_id = %s),
                        (SELECT COUNT(*) FROM cache.websim_gear_release_sources WHERE release_id = %s),
                        (SELECT COUNT(*) FROM cache.websim_gear_release_variants WHERE release_id = %s),
                        (SELECT COUNT(*) FROM cache.websim_gear_release_mod_options WHERE release_id = %s)
                    """,
                    (gear_id, gear_id, gear_id, gear_id),
                )
                count_row = tuple(cur.fetchone() or ())
                expected_counts = gear.get("content", {}).get("counts") if isinstance(gear.get("content"), dict) else {}
                actual_counts = {
                    "items": _int(count_row[0] if len(count_row) > 0 else -1),
                    "sources": _int(count_row[1] if len(count_row) > 1 else -1),
                    "variants": _int(count_row[2] if len(count_row) > 2 else -1),
                    "options": _int(count_row[3] if len(count_row) > 3 else -1),
                }
                if actual_counts != {key: _int((expected_counts or {}).get(key)) for key in actual_counts}:
                    raise GearReleaseIntegrityError("active Gear Release row counts do not match sealed content")
                if community_id:
                    cur.execute(
                        """
                        SELECT template_id, class_key, spec_key, role, election_rank,
                               source_key, source_url, source_status, sample_count,
                               profile_hash, gear_hash, selection_intent_json,
                               resolved_gear_signature, semantic_gear_signature,
                               dependency_vector_json, evidence_json, problems_json,
                               payload_json, payload_json->>'updatedAt',
                               payload_json->>'expiresAt', row_hash
                        FROM cache.websim_community_release_templates
                        WHERE release_id = %s AND class_key = %s AND spec_key = %s
                          AND role = 'winner'
                        ORDER BY election_rank, template_id
                        """,
                        (community_id, _text(class_key), _text(spec_key)),
                    )
                    winner_db_rows = cur.fetchall()
                    winner_rows = [self._community_row_from_db(row) for row in winner_db_rows]
                    if len(winner_rows) != 1:
                        raise GearReleaseIntegrityError("active Community Release must expose exactly one winner per spec")
                    if canonical_row_hash(winner_rows[0]) != _text(winner_db_rows[0][20]):
                        raise GearReleaseIntegrityError("active Community winner row integrity failed")
                    community_templates = []
                    for row in winner_rows:
                        public_template = _canonical(
                            row.get("payload") if isinstance(row.get("payload"), dict) else {}
                        )
                        # Release storage owns an immutable internal templateId,
                        # while the established public mini-program contract uses
                        # id.  A validated winner is directly importable; project
                        # that fact explicitly instead of leaking the release-row
                        # identity shape into the existing public read model.
                        public_template.pop("templateId", None)
                        public_template.pop("enhancementBySlot", None)
                        nested_payload = public_template.get("payload")
                        if isinstance(nested_payload, dict) and "enhancementBySlot" in nested_payload:
                            nested_payload = _canonical(nested_payload)
                            nested_payload.pop("enhancementBySlot", None)
                            public_template["payload"] = nested_payload
                        public_template["id"] = _text(
                            public_template.get("id") or row.get("templateId")
                        )
                        public_template["canApplyGear"] = True
                        enhancement_by_slot = _public_enhancement_by_slot(
                            row.get("selectionIntent")
                        )
                        if enhancement_by_slot:
                            public_template["enhancementBySlot"] = enhancement_by_slot
                        community_templates.append(public_template)
                if include_catalog:
                    normalized_slot = _text(catalog_slot)
                    variant_slot_clause = " AND slot = %s" if normalized_slot else ""
                    variant_params = (gear_id, normalized_slot) if normalized_slot else (gear_id,)
                    cur.execute(
                        f"""
                        SELECT variant_id, item_id, variant_key, slot, label, source_type,
                               difficulty_key, item_level, simc_options_json, status,
                               blockers_json, payload_json, source_updated_at, row_hash
                        FROM cache.websim_gear_release_variants
                        WHERE release_id = %s{variant_slot_clause}
                        ORDER BY variant_id
                        """,
                        variant_params,
                    )
                    variant_db_rows = cur.fetchall()
                    snapshot["variants"] = [
                        {
                            "variantId": _text(row[0]),
                            "itemId": _text(row[1]),
                            "variantKey": _text(row[2]),
                            "slot": _text(row[3]),
                            "label": _text(row[4]),
                            "sourceType": _text(row[5]),
                            "difficultyKey": _text(row[6]),
                            "itemLevel": _int(row[7]),
                            "simcOptions": _canonical(row[8] if isinstance(row[8], dict) else {}),
                            "status": _text(row[9]),
                            "blockers": _canonical(row[10] if isinstance(row[10], list) else []),
                            "payload": _canonical(row[11] if isinstance(row[11], dict) else {}),
                            "updatedAt": _text(row[12]),
                        }
                        for row in variant_db_rows
                    ]
                    if any(
                        canonical_row_hash(record) != _text(row[13])
                        for record, row in zip(snapshot["variants"], variant_db_rows)
                    ):
                        raise GearReleaseIntegrityError("active Gear Release variant row integrity failed")
                    item_ids = sorted({_text(row.get("itemId")) for row in snapshot["variants"] if _text(row.get("itemId"))})
                    item_scope_clause = " AND item_id = ANY(%s::text[])" if normalized_slot else ""
                    item_scope_params = (gear_id, item_ids) if normalized_slot else (gear_id,)
                    cur.execute(
                        f"""
                        SELECT item_id, name, slot, item_level, source_status, payload_json,
                               source_updated_at, row_hash
                        FROM cache.websim_gear_release_items
                        WHERE release_id = %s{item_scope_clause}
                        ORDER BY item_id
                        """,
                        item_scope_params,
                    )
                    item_db_rows = cur.fetchall()
                    snapshot["items"] = [
                        {
                            "itemId": _text(row[0]),
                            "name": _text(row[1]),
                            "slot": _text(row[2]),
                            "itemLevel": None if row[3] is None else _int(row[3]),
                            "sourceStatus": _text(row[4]),
                            "payload": _canonical(row[5] if isinstance(row[5], dict) else {}),
                            "updatedAt": _text(row[6]),
                        }
                        for row in item_db_rows
                    ]
                    if any(
                        canonical_row_hash(record) != _text(row[7])
                        for record, row in zip(snapshot["items"], item_db_rows)
                    ):
                        raise GearReleaseIntegrityError("active Gear Release item row integrity failed")
                    cur.execute(
                        f"""
                        SELECT source_id, item_id, source_type, source_key, source_label,
                               instance_id, encounter_id, difficulty_key, season_revision,
                               payload_json, source_updated_at, row_hash
                        FROM cache.websim_gear_release_sources
                        WHERE release_id = %s{item_scope_clause}
                        ORDER BY source_id
                        """,
                        item_scope_params,
                    )
                    source_db_rows = cur.fetchall()
                    snapshot["sources"] = [
                        {
                            "sourceId": _text(row[0]),
                            "itemId": _text(row[1]),
                            "sourceType": _text(row[2]),
                            "sourceKey": _text(row[3]),
                            "sourceLabel": _text(row[4]),
                            "instanceId": _text(row[5]),
                            "encounterId": _text(row[6]),
                            "difficultyKey": _text(row[7]),
                            "seasonRevision": _text(row[8]),
                            "payload": _canonical(row[9] if isinstance(row[9], dict) else {}),
                            "updatedAt": _text(row[10]),
                        }
                        for row in source_db_rows
                    ]
                    if any(
                        canonical_row_hash(record) != _text(row[11])
                        for record, row in zip(snapshot["sources"], source_db_rows)
                    ):
                        raise GearReleaseIntegrityError("active Gear Release source row integrity failed")
                    cur.execute(
                        """
                        SELECT option_id, variant_id, option_key, option_type, name,
                               applicable_slots_json, simc_options_json, status, is_visible,
                               payload_json, source_updated_at, row_hash
                        FROM cache.websim_gear_release_mod_options
                        WHERE release_id = %s
                        ORDER BY option_id
                        """,
                        (gear_id,),
                    )
                    option_db_rows = cur.fetchall()
                    snapshot["options"] = [
                        {
                            "optionId": _text(row[0]),
                            "variantId": _text(row[1]),
                            "optionKey": _text(row[2]),
                            "optionType": _text(row[3]),
                            "name": _text(row[4]),
                            "applicableSlots": _canonical(row[5] if isinstance(row[5], list) else []),
                            "simcOptions": _canonical(row[6] if isinstance(row[6], dict) else {}),
                            "status": _text(row[7]),
                            "isVisible": row[8] is True,
                            "payload": _canonical(row[9] if isinstance(row[9], dict) else {}),
                            "updatedAt": _text(row[10]),
                        }
                        for row in option_db_rows
                    ]
                    if any(
                        canonical_row_hash(record) != _text(row[11])
                        for record, row in zip(snapshot["options"], option_db_rows)
                    ):
                        raise GearReleaseIntegrityError("active Gear Release option row integrity failed")
        return {
            "gearRelease": gear,
            "communityRelease": community,
            "communityTemplates": community_templates,
            "gearSnapshot": snapshot if include_catalog else None,
        }

    def load_active_community_template_import(
        self,
        binding: dict[str, Any],
        class_key: str,
        spec_key: str,
        template_id: str,
    ) -> dict[str, Any]:
        """Read one observed winner and only its import authority from one active binding."""

        if not isinstance(binding, dict) or binding.get("formalActiveManifest") is not True:
            raise GearReleaseIntegrityError("formal active Manifest binding is required")
        manifest = binding.get("manifest") if isinstance(binding.get("manifest"), dict) else {}
        gear = _exact_release_descriptor(binding.get("gearRelease"))
        gear_id = _text(manifest.get("gearCatalogReleaseId"))
        if gear_id != gear["releaseId"]:
            raise GearReleaseIntegrityError("active import Gear Release does not match the Manifest")
        community_id = _text(manifest.get("communityTemplateReleaseId"))
        community = _exact_release_descriptor(binding.get("communityRelease"))
        if (
            not community_id
            or community_id != community["releaseId"]
            or community["validatedAgainstReleaseId"] != gear_id
        ):
            raise GearReleaseIntegrityError("active import Community Release does not match the Manifest")

        requested_class = _text(class_key)
        requested_spec = _text(spec_key)
        requested_template = _text(template_id)
        if not requested_class or not requested_spec or not requested_template:
            raise GearReleaseIntegrityError("community template import identity is required")

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cur.execute(
                    """
                    SELECT template_id, class_key, spec_key, role, election_rank,
                           source_key, source_url, source_status, sample_count,
                           profile_hash, gear_hash, selection_intent_json,
                           resolved_gear_signature, semantic_gear_signature,
                           dependency_vector_json, evidence_json, problems_json,
                           payload_json, payload_json->>'updatedAt',
                           payload_json->>'expiresAt', row_hash
                    FROM cache.websim_community_release_templates
                    WHERE release_id = %s AND class_key = %s AND spec_key = %s
                      AND template_id = %s AND role = 'winner'
                      AND source_key = 'raiderio_observed_profile'
                    ORDER BY election_rank, template_id
                    """,
                    (community_id, requested_class, requested_spec, requested_template),
                )
                winner_db_rows = cur.fetchall()
                if len(winner_db_rows) != 1:
                    raise GearReleaseIntegrityError("active Community import must expose exactly one observed winner")
                winner = self._community_row_from_db(winner_db_rows[0])
                if (
                    winner.get("templateId") != requested_template
                    or winner.get("classKey") != requested_class
                    or winner.get("specKey") != requested_spec
                    or winner.get("role") != "winner"
                    or winner.get("sourceKey") != "raiderio_observed_profile"
                    or canonical_row_hash(winner) != _text(winner_db_rows[0][20])
                ):
                    raise GearReleaseIntegrityError("active Community import winner integrity failed")

                intent = winner.get("selectionIntent") if isinstance(winner.get("selectionIntent"), dict) else {}
                slots = intent.get("slots") if isinstance(intent.get("slots"), dict) else {}
                requested_pairs = sorted({
                    (_text(selection.get("itemId")), _text(selection.get("variantKey")))
                    for selection in slots.values()
                    if isinstance(selection, dict)
                })
                if not requested_pairs or any(not item_id or not variant_key for item_id, variant_key in requested_pairs):
                    raise GearReleaseIntegrityError("active Community import selection is incomplete")
                item_ids = [item_id for item_id, _variant_key in requested_pairs]
                variant_keys = [variant_key for _item_id, variant_key in requested_pairs]

                cur.execute(
                    """
                    WITH requested(item_id, variant_key) AS (
                        SELECT * FROM unnest(%s::text[], %s::text[])
                    )
                    SELECT requested.item_id, requested.variant_key,
                           variant.variant_id, variant.item_id, variant.variant_key, variant.slot,
                           variant.label, variant.source_type, variant.difficulty_key,
                           variant.item_level, variant.simc_options_json, variant.status,
                           variant.blockers_json, variant.payload_json,
                           variant.source_updated_at, variant.row_hash
                    FROM requested
                    JOIN LATERAL (
                        SELECT candidate.*
                        FROM cache.websim_gear_release_variants candidate
                        WHERE candidate.release_id = %s
                          AND candidate.item_id = requested.item_id
                          AND (
                              candidate.variant_key = requested.variant_key
                              OR LEFT(
                                  regexp_replace(candidate.variant_key, '[^A-Za-z0-9_:/.-]+', '', 'g'),
                                  240
                              ) = requested.variant_key
                          )
                        ORDER BY
                            CASE WHEN candidate.variant_key = requested.variant_key THEN 0 ELSE 1 END,
                            candidate.variant_id
                        LIMIT 1
                    ) variant ON TRUE
                    ORDER BY variant.item_id, variant.variant_key, variant.variant_id
                    """,
                    (item_ids, variant_keys, gear_id),
                )
                variant_db_rows = cur.fetchall()
                variants = []
                for row in variant_db_rows:
                    record = {
                        "variantId": _text(row[2]),
                        "itemId": _text(row[3]),
                        "variantKey": _text(row[4]),
                        "slot": _text(row[5]),
                        "label": _text(row[6]),
                        "sourceType": _text(row[7]),
                        "difficultyKey": _text(row[8]),
                        "itemLevel": _int(row[9]),
                        "simcOptions": _canonical(row[10] if isinstance(row[10], dict) else {}),
                        "status": _text(row[11]),
                        "blockers": _canonical(row[12] if isinstance(row[12], list) else []),
                        "payload": _canonical(row[13] if isinstance(row[13], dict) else {}),
                        "updatedAt": _text(row[14]),
                    }
                    if canonical_row_hash(record) != _text(row[15]):
                        raise GearReleaseIntegrityError("active Community import variant integrity failed")
                    record["requestedItemId"] = _text(row[0])
                    record["requestedVariantKey"] = _text(row[1])
                    variants.append(record)
                if (
                    len(variants) != len(requested_pairs)
                    or {(row["requestedItemId"], row["requestedVariantKey"]) for row in variants} != set(requested_pairs)
                    or any(row["requestedItemId"] != row["itemId"] for row in variants)
                ):
                    raise GearReleaseIntegrityError("active Community import variant integrity failed")

                selected_item_ids = sorted({row["itemId"] for row in variants})
                cur.execute(
                    """
                    SELECT item_id, name, slot, item_level, source_status, payload_json,
                           source_updated_at, row_hash
                    FROM cache.websim_gear_release_items
                    WHERE release_id = %s AND item_id = ANY(%s::text[])
                    ORDER BY item_id
                    """,
                    (gear_id, selected_item_ids),
                )
                item_db_rows = cur.fetchall()
                items = [
                    {
                        "itemId": _text(row[0]),
                        "name": _text(row[1]),
                        "slot": _text(row[2]),
                        "itemLevel": None if row[3] is None else _int(row[3]),
                        "sourceStatus": _text(row[4]),
                        "payload": _canonical(row[5] if isinstance(row[5], dict) else {}),
                        "updatedAt": _text(row[6]),
                    }
                    for row in item_db_rows
                ]
                if (
                    len(items) != len(selected_item_ids)
                    or {row["itemId"] for row in items} != set(selected_item_ids)
                    or any(canonical_row_hash(record) != _text(row[7]) for record, row in zip(items, item_db_rows))
                ):
                    raise GearReleaseIntegrityError("active Community import item integrity failed")

                cur.execute(
                    """
                    SELECT source_id, item_id, source_type, source_key, source_label,
                           instance_id, encounter_id, difficulty_key, season_revision,
                           payload_json, source_updated_at, row_hash
                    FROM cache.websim_gear_release_sources
                    WHERE release_id = %s AND item_id = ANY(%s::text[])
                    ORDER BY source_id
                    """,
                    (gear_id, selected_item_ids),
                )
                source_db_rows = cur.fetchall()
                sources = [
                    {
                        "sourceId": _text(row[0]),
                        "itemId": _text(row[1]),
                        "sourceType": _text(row[2]),
                        "sourceKey": _text(row[3]),
                        "sourceLabel": _text(row[4]),
                        "instanceId": _text(row[5]),
                        "encounterId": _text(row[6]),
                        "difficultyKey": _text(row[7]),
                        "seasonRevision": _text(row[8]),
                        "payload": _canonical(row[9] if isinstance(row[9], dict) else {}),
                        "updatedAt": _text(row[10]),
                    }
                    for row in source_db_rows
                ]
                if (
                    not sources
                    or not set(selected_item_ids).issubset({row["itemId"] for row in sources})
                    or any(canonical_row_hash(record) != _text(row[11]) for record, row in zip(sources, source_db_rows))
                ):
                    raise GearReleaseIntegrityError("active Community import source integrity failed")

                selected_option_keys = _selected_option_ids(intent)
                options = []
                if selected_option_keys:
                    cur.execute(
                        """
                        SELECT option_id, variant_id, option_key, option_type, name,
                               applicable_slots_json, simc_options_json, status, is_visible,
                               payload_json, source_updated_at, row_hash
                        FROM cache.websim_gear_release_mod_options
                        WHERE release_id = %s
                          AND option_key = ANY(%s::text[])
                        ORDER BY option_id
                        """,
                        (gear_id, selected_option_keys),
                    )
                    option_db_rows = cur.fetchall()
                    options = [
                        {
                            "optionId": _text(row[0]),
                            "variantId": _text(row[1]),
                            "optionKey": _text(row[2]),
                            "optionType": _text(row[3]),
                            "name": _text(row[4]),
                            "applicableSlots": _canonical(row[5] if isinstance(row[5], list) else []),
                            "simcOptions": _canonical(row[6] if isinstance(row[6], dict) else {}),
                            "status": _text(row[7]),
                            "isVisible": row[8] is True,
                            "payload": _canonical(row[9] if isinstance(row[9], dict) else {}),
                            "updatedAt": _text(row[10]),
                        }
                        for row in option_db_rows
                    ]
                    if (
                        {row["optionKey"] for row in options} != set(selected_option_keys)
                        or any(canonical_row_hash(record) != _text(row[11]) for record, row in zip(options, option_db_rows))
                    ):
                        raise GearReleaseIntegrityError("active Community import option integrity failed")

        return {
            "binding": _canonical(binding),
            "gearRelease": gear,
            "communityRelease": community,
            "winner": winner,
            "items": items,
            "sources": sources,
            "variants": variants,
            "options": options,
        }

    def load_community_release(
        self,
        gear_release_id: str,
        community_release_id: str,
    ) -> dict[str, Any]:
        """Read and integrity-check one Community Release bound to one Gear Release."""

        gear_id = _text(gear_release_id)
        community_id = _text(community_release_id)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                gear = self._select_release(cur, gear_id)
                community = self._select_release(cur, community_id)
                if gear is None or community is None:
                    raise GearReleaseIntegrityError("candidate release pair is missing")
                gear = _exact_release_descriptor(gear)
                community = _exact_release_descriptor(community)
                if gear["releaseKind"] != "gear" or community["releaseKind"] != "community":
                    raise GearReleaseIntegrityError("candidate release pair kind is invalid")
                if community["validatedAgainstReleaseId"] != gear["releaseId"]:
                    raise GearReleaseIntegrityError("Community Release is not bound to the Gear Release")
                if community["seasonRevision"] != gear["seasonRevision"]:
                    raise GearReleaseIntegrityError("candidate release pair season mismatch")
                if community["dependencyRevisions"] != gear["dependencyRevisions"]:
                    raise GearReleaseIntegrityError("candidate release pair dependency mismatch")
                cur.execute(
                    """
                    SELECT template_id, class_key, spec_key, role, election_rank,
                           source_key, source_url, source_status, sample_count,
                           profile_hash, gear_hash, selection_intent_json,
                           resolved_gear_signature, semantic_gear_signature,
                           dependency_vector_json, evidence_json, problems_json,
                           payload_json, payload_json->>'updatedAt',
                           payload_json->>'expiresAt'
                    FROM cache.websim_community_release_templates
                    WHERE release_id = %s
                    ORDER BY class_key, spec_key, role, election_rank, template_id
                    """,
                    (community_id,),
                )
                rows = [self._community_row_from_db(row) for row in cur.fetchall()]
        if community_rows_summary(rows) != community["content"]:
            raise GearReleaseIntegrityError("Community Release content integrity failed")
        return {
            "gearRelease": gear,
            "communityRelease": community,
            "rows": rows,
            "winners": [row for row in rows if row.get("role") == "winner"],
        }

    @staticmethod
    def _community_row_from_db(row: Any) -> dict[str, Any]:
        values = list(row or ())
        return {
            "templateId": _text(values[0]),
            "classKey": _text(values[1]),
            "specKey": _text(values[2]),
            "role": _text(values[3]),
            "electionRank": _int(values[4]),
            "sourceKey": _text(values[5]),
            "sourceUrl": _text(values[6]),
            "sourceStatus": _text(values[7]),
            "sampleCount": _int(values[8]),
            "profileHash": _text(values[9]),
            "gearHash": _text(values[10]),
            "selectionIntent": _canonical(values[11] if isinstance(values[11], dict) else {}),
            "resolvedGearSignature": _text(values[12]),
            "semanticGearSignature": _text(values[13]),
            "dependencyVector": _canonical(values[14] if isinstance(values[14], dict) else {}),
            "evidence": _canonical(values[15] if isinstance(values[15], (dict, list)) else {}),
            "problems": _canonical(values[16] if isinstance(values[16], list) else []),
            "payload": _canonical(values[17] if isinstance(values[17], dict) else {}),
            "updatedAt": _text(values[18]),
            "expiresAt": _text(values[19]),
        }

    @staticmethod
    def _insert_registry(cur, release: dict[str, Any], gate_result: dict[str, Any]) -> None:
        cur.execute(
            """
            INSERT INTO cache.websim_release_registry (
                release_id, release_kind, season_revision, schema_revision, content_hash,
                parent_release_id, validated_against_release_id, release_status,
                dependency_vector_json, gate_result_json, source_json, content_summary_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb)
            """,
            (
                release["releaseId"],
                release["releaseKind"],
                release["seasonRevision"],
                release["schemaRevision"],
                release["contentHash"],
                release.get("parentReleaseId") or None,
                release.get("validatedAgainstReleaseId") or None,
                release["releaseStatus"],
                _json_param(release.get("dependencyRevisions") or {}),
                _json_param(gate_result),
                _json_param(release.get("source") or {}),
                _json_param(release.get("content") or {}),
            ),
        )

    @staticmethod
    def _insert_event(cur, *, release_id: str = "", manifest_revision: str = "", event_type: str, event: dict[str, Any]) -> None:
        cur.execute(
            """
            INSERT INTO cache.websim_release_events (
                release_id, manifest_revision, event_type, event_json
            ) VALUES (%s, %s, %s, %s::jsonb)
            """,
            (release_id or None, manifest_revision or None, event_type, _json_param(event)),
        )

    @staticmethod
    def _existing_or_insert(cur, release: dict[str, Any], gate_result: dict[str, Any]) -> bool:
        expected = _exact_release_descriptor(release)
        existing = GearReleaseStore._select_release(cur, expected["releaseId"])
        if existing is not None:
            if _exact_release_descriptor(existing) != expected:
                raise GearReleaseIntegrityError("existing release ID has different sealed content")
            return True
        GearReleaseStore._insert_registry(cur, expected, gate_result)
        return False

    def seal_gear_release(
        self,
        release: dict[str, Any],
        snapshot: dict[str, Any],
        *,
        event: dict[str, Any] | None = None,
        gate_result: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        expected = _exact_release_descriptor(release)
        with self.connection() as conn:
            with conn.cursor() as cur:
                if expected["releaseKind"] != "gear":
                    raise GearReleaseIntegrityError("seal_gear_release requires a Gear Release")
                if gear_snapshot_summary(snapshot) != expected["content"]:
                    raise GearReleaseIntegrityError("gear snapshot does not match the release descriptor")
                if self._existing_or_insert(cur, expected, gate_result or {}):
                    return {"status": "reused", "releaseId": expected["releaseId"]}
                self._insert_gear_rows(cur, expected["releaseId"], snapshot)
                self._insert_event(
                    cur,
                    release_id=expected["releaseId"],
                    event_type="release_sealed",
                    event=event or {},
                )
        return {"status": "inserted", "releaseId": expected["releaseId"]}

    @staticmethod
    def _insert_gear_rows(cur, release_id: str, snapshot: dict[str, Any]) -> None:
        items = _canonical_rows(snapshot.get("items"))
        sources = _canonical_rows(snapshot.get("sources"))
        variants = _canonical_rows(snapshot.get("variants"))
        options = _canonical_rows(snapshot.get("options"))
        if items:
            cur.executemany(
                """
                INSERT INTO cache.websim_gear_release_items (
                    release_id, item_id, name, slot, item_level, source_status,
                    payload_json, source_updated_at, row_hash
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                [
                    (
                        release_id, row.get("itemId"), row.get("name") or "", row.get("slot") or "",
                        row.get("itemLevel"), row.get("sourceStatus") or "unknown",
                        _json_param(row.get("payload") or {}), row.get("updatedAt") or None,
                        canonical_row_hash(row),
                    )
                    for row in items
                ],
            )
        if sources:
            cur.executemany(
                """
                INSERT INTO cache.websim_gear_release_sources (
                    release_id, source_id, item_id, source_type, source_key, source_label,
                    instance_id, encounter_id, difficulty_key, season_revision,
                    payload_json, source_updated_at, row_hash
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                [
                    (
                        release_id, row.get("sourceId"), row.get("itemId"), row.get("sourceType"),
                        row.get("sourceKey") or "", row.get("sourceLabel") or "",
                        row.get("instanceId") or "", row.get("encounterId") or "",
                        row.get("difficultyKey") or "", row.get("seasonRevision") or "",
                        _json_param(row.get("payload") or {}), row.get("updatedAt") or None,
                        canonical_row_hash(row),
                    )
                    for row in sources
                ],
            )
        if variants:
            cur.executemany(
                """
                INSERT INTO cache.websim_gear_release_variants (
                    release_id, variant_id, item_id, variant_key, slot, label, source_type,
                    difficulty_key, item_level, simc_options_json, status, blockers_json,
                    payload_json, source_updated_at, row_hash
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s::jsonb, %s, %s)
                """,
                [
                    (
                        release_id, row.get("variantId"), row.get("itemId"), row.get("variantKey"),
                        row.get("slot") or "", row.get("label") or "", row.get("sourceType") or "",
                        row.get("difficultyKey") or "", _int(row.get("itemLevel")),
                        _json_param(row.get("simcOptions") or {}), row.get("status") or "blocked",
                        _json_param(row.get("blockers") or []), _json_param(row.get("payload") or {}),
                        row.get("updatedAt") or None, canonical_row_hash(row),
                    )
                    for row in variants
                ],
            )
        if options:
            cur.executemany(
                """
                INSERT INTO cache.websim_gear_release_mod_options (
                    release_id, option_id, variant_id, option_key, option_type, name,
                    applicable_slots_json, simc_options_json, status, is_visible,
                    payload_json, source_updated_at, row_hash
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb, %s, %s)
                """,
                [
                    (
                        release_id, row.get("optionId"), row.get("variantId") or None,
                        row.get("optionKey"), row.get("optionType") or "", row.get("name") or "",
                        _json_param(row.get("applicableSlots") or []),
                        _json_param(row.get("simcOptions") or {}), row.get("status") or "blocked",
                        row.get("isVisible") is True, _json_param(row.get("payload") or {}),
                        row.get("updatedAt") or None, canonical_row_hash(row),
                    )
                    for row in options
                ],
            )

    def seal_community_release(
        self,
        release: dict[str, Any],
        rows: Iterable[dict[str, Any]],
        *,
        event: dict[str, Any] | None = None,
        gate_result: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        expected = _exact_release_descriptor(release)
        canonical_rows = _canonical_rows(rows)
        with self.connection() as conn:
            with conn.cursor() as cur:
                if expected["releaseKind"] != "community":
                    raise GearReleaseIntegrityError("seal_community_release requires a Community Release")
                if community_rows_summary(canonical_rows) != expected["content"]:
                    raise GearReleaseIntegrityError("community rows do not match the release descriptor")
                if self._existing_or_insert(cur, expected, gate_result or {}):
                    return {"status": "reused", "releaseId": expected["releaseId"]}
                if canonical_rows:
                    cur.executemany(
                        """
                        INSERT INTO cache.websim_community_release_templates (
                            release_id, template_id, class_key, spec_key, role, election_rank,
                            source_key, source_url, source_status, sample_count, profile_hash, gear_hash,
                            selection_intent_json, resolved_gear_signature, semantic_gear_signature,
                            dependency_vector_json, evidence_json, problems_json, payload_json,
                            source_updated_at, expires_at, row_hash
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s)
                        """,
                        [self._community_row_values(expected["releaseId"], row) for row in canonical_rows],
                    )
                self._insert_event(
                    cur,
                    release_id=expected["releaseId"],
                    event_type="release_sealed",
                    event=event or {},
                )
        return {"status": "inserted", "releaseId": expected["releaseId"]}

    @staticmethod
    def _community_row_values(release_id: str, row: dict[str, Any]) -> tuple[Any, ...]:
        return (
            release_id,
            row.get("templateId"),
            row.get("classKey"),
            row.get("specKey"),
            row.get("role"),
            _int(row.get("electionRank")),
            row.get("sourceKey") or "",
            row.get("sourceUrl") or "",
            row.get("sourceStatus") or "",
            _int(row.get("sampleCount")),
            row.get("profileHash") or "",
            row.get("gearHash") or "",
            _json_param(row.get("selectionIntent") or {}),
            row.get("resolvedGearSignature") or "",
            row.get("semanticGearSignature") or "",
            _json_param(row.get("dependencyVector") or {}),
            _json_param(row.get("evidence") or {}),
            _json_param(row.get("problems") or []),
            _json_param(row.get("payload") or {}),
            row.get("updatedAt") or None,
            row.get("expiresAt") or None,
            canonical_row_hash(row),
        )

    @staticmethod
    def _validated_manifest_revision(manifest: dict[str, Any]) -> str:
        if not isinstance(manifest, dict) or not _text(manifest.get("manifestRevision")):
            raise GearReleaseIntegrityError("manifest must contain manifestRevision")
        revision = _text(manifest["manifestRevision"])
        if revision != _expected_manifest_revision(manifest):
            raise GearReleaseIntegrityError("manifest identity does not match manifestRevision")
        return revision

    def _seal_manifest_with_cursor(self, cur, manifest: dict[str, Any]) -> dict[str, str]:
        revision = self._validated_manifest_revision(manifest)
        cur.execute(
            """
            SELECT payload_json
            FROM cache.websim_season_manifests
            WHERE manifest_revision = %s
            """,
            (revision,),
        )
        row = cur.fetchone()
        if row:
            if _canonical(row[0] if isinstance(row[0], dict) else {}) != _canonical(manifest):
                raise GearReleaseIntegrityError("existing manifest revision has different content")
            return {"status": "reused", "manifestRevision": revision}
        cur.execute(
            """
            INSERT INTO cache.websim_season_manifests (
                manifest_revision, schema_revision, season_revision, gear_release_id,
                community_release_id, talent_catalog_revision, dependency_vector_json,
                rollback_manifest_revision, manifest_hash, payload_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb)
            """,
            (
                revision,
                manifest.get("schemaRevision"),
                manifest.get("seasonRevision"),
                manifest.get("gearCatalogReleaseId"),
                manifest.get("communityTemplateReleaseId") or None,
                manifest.get("talentCatalogRevision"),
                _json_param(manifest.get("dependencyRevisions") or {}),
                manifest.get("rollbackManifestRevision") or None,
                _hash({key: value for key, value in manifest.items() if key != "manifestRevision"}),
                _json_param(manifest),
            ),
        )
        self._insert_event(
            cur,
            manifest_revision=revision,
            event_type="manifest_sealed",
            event={"formalActiveManifest": bool(manifest.get("formalActiveManifest"))},
        )
        return {"status": "inserted", "manifestRevision": revision}

    def seal_manifest(self, manifest: dict[str, Any]) -> dict[str, str]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                return self._seal_manifest_with_cursor(cur, manifest)

    def get_active_pointer(self) -> dict[str, Any]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT environment, pointer_mode, manifest_revision, generation, rollback_manifest_revision,
                           updated_at, updated_by
                    FROM cache.websim_active_manifest_pointer
                    WHERE environment = 'retail'
                    """
                )
                row = cur.fetchone()
        if not row:
            return {}
        return {
            "environment": _text(row[0]),
            "pointerMode": _text(row[1]),
            "manifestRevision": _text(row[2]),
            "generation": _int(row[3]),
            "rollbackManifestRevision": _text(row[4]),
            "updatedAt": _text(row[5]),
            "updatedBy": _text(row[6]),
        }

    def load_active_manifest_binding(self) -> dict[str, Any]:
        """Bind one retail pointer/Manifest/release identity in a read-only snapshot."""

        try:
            from . import gear_release
        except ImportError:
            import gear_release

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cur.execute(
                    """
                    SELECT pointer.environment, pointer.pointer_mode, pointer.manifest_revision,
                           pointer.generation, pointer.rollback_manifest_revision,
                           pointer.updated_at, pointer.updated_by, manifest.payload_json
                    FROM cache.websim_active_manifest_pointer pointer
                    LEFT JOIN cache.websim_season_manifests manifest
                      ON manifest.manifest_revision = pointer.manifest_revision
                    WHERE pointer.environment = 'retail'
                    """
                )
                row = cur.fetchone()
                if not row:
                    return {
                        "pointerMode": "pre_cutover",
                        "generation": 0,
                        "manifestRevision": "",
                        "rollbackManifestRevision": "",
                        "formalActiveManifest": False,
                    }
                values = list(row)
                while len(values) < 8:
                    values.append(None)
                pointer_mode = _text(values[1])
                manifest_revision = _text(values[2])
                generation = _int(values[3])
                rollback_revision = _text(values[4])
                common = {
                    "pointerMode": pointer_mode,
                    "generation": generation,
                    "manifestRevision": manifest_revision,
                    "rollbackManifestRevision": rollback_revision,
                    "updatedAt": _text(values[5]),
                    "updatedBy": _text(values[6]),
                }
                if pointer_mode == "transitional":
                    if manifest_revision or values[7] is not None:
                        raise GearReleaseIntegrityError("transitional pointer unexpectedly binds a Manifest")
                    return {**common, "formalActiveManifest": False}
                if pointer_mode != "active" or not manifest_revision:
                    raise GearReleaseIntegrityError("active Manifest pointer state is invalid")
                manifest = values[7] if isinstance(values[7], dict) else None
                if not isinstance(manifest, dict) or _text(manifest.get("manifestRevision")) != manifest_revision:
                    raise GearReleaseIntegrityError("active Manifest is missing or does not match the pointer")
                gear_id = _text(manifest.get("gearCatalogReleaseId"))
                community_id = _text(manifest.get("communityTemplateReleaseId"))
                releases = {}
                gear = self._select_release(cur, gear_id)
                if gear is not None:
                    releases[gear_id] = _exact_release_descriptor(gear)
                community = None
                if community_id:
                    community = self._select_release(cur, community_id)
                    if community is not None:
                        releases[community_id] = _exact_release_descriptor(community)
                issues = gear_release.validate_manifest(manifest, releases)
                if issues:
                    raise GearReleaseIntegrityError(
                        "active Manifest binding integrity failed: "
                        + ", ".join(_text(issue.get("code")) for issue in issues)
                    )
                return {
                    **common,
                    "formalActiveManifest": True,
                    "manifest": _canonical(manifest),
                    "gearRelease": releases[gear_id],
                    "communityRelease": releases.get(community_id) if community_id else None,
                }

    @staticmethod
    def _validated_pointer_command(command: dict[str, Any], updated_by: str) -> tuple[str, str, str, int, str]:
        required_fields = {
            "schemaRevision",
            "action",
            "environment",
            "targetMode",
            "manifestRevision",
            "expectedGeneration",
            "rollbackManifestRevision",
        }
        if not isinstance(command, dict) or set(command) != required_fields:
            raise ValueError("invalid pointer command")
        if command.get("schemaRevision") != "active-manifest-pointer-command-v2":
            raise ValueError("invalid pointer command schema")
        if command.get("action") not in {"promote", "rollback"}:
            raise ValueError("invalid pointer command action")
        if command.get("environment") != "retail":
            raise ValueError("invalid pointer command environment")
        target_mode = _text(command.get("targetMode"))
        manifest_revision = _text(command.get("manifestRevision"))
        rollback_manifest_revision = _text(command.get("rollbackManifestRevision"))
        if target_mode not in {"active", "transitional"}:
            raise ValueError("invalid pointer targetMode")
        if target_mode == "active" and not manifest_revision:
            raise ValueError("active pointer command requires manifestRevision")
        if target_mode == "transitional":
            if command.get("action") != "rollback" or manifest_revision or rollback_manifest_revision:
                raise ValueError("invalid transitional pointer command")
        expected_generation = command.get("expectedGeneration")
        if isinstance(expected_generation, bool) or not isinstance(expected_generation, int) or expected_generation < 0:
            raise ValueError("expectedGeneration must be a non-negative integer")
        if not _text(updated_by):
            raise ValueError("updated_by is required")
        return (
            _text(command.get("action")),
            target_mode,
            manifest_revision,
            expected_generation,
            rollback_manifest_revision,
        )

    def _compare_and_swap_pointer_with_cursor(self, cur, command: dict[str, Any], *, updated_by: str) -> dict[str, Any]:
        action, target_mode, manifest_revision, expected_generation, rollback_manifest_revision = (
            self._validated_pointer_command(command, updated_by)
        )
        target_generation = expected_generation + 1
        if expected_generation == 0:
            cur.execute(
                """
                INSERT INTO cache.websim_active_manifest_pointer (
                    environment, pointer_mode, manifest_revision, generation, rollback_manifest_revision,
                    updated_by
                )
                SELECT 'retail', %s, %s, %s, %s, %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM cache.websim_active_manifest_pointer WHERE environment = 'retail'
                )
                ON CONFLICT (environment) DO NOTHING
                """,
                (
                    target_mode,
                    manifest_revision or None,
                    target_generation,
                    rollback_manifest_revision or None,
                    _text(updated_by),
                ),
            )
        else:
            cur.execute(
                """
                UPDATE cache.websim_active_manifest_pointer
                SET pointer_mode = %s,
                    manifest_revision = %s,
                    generation = %s,
                    rollback_manifest_revision = %s,
                    updated_at = now(),
                    updated_by = %s
                WHERE environment = 'retail' AND generation = %s
                """,
                (
                    target_mode,
                    manifest_revision or None,
                    target_generation,
                    rollback_manifest_revision or None,
                    _text(updated_by),
                    expected_generation,
                ),
            )
        if getattr(cur, "rowcount", 0) != 1:
            raise StaleManifestPointerError("active manifest pointer generation changed")
        self._insert_event(
            cur,
            manifest_revision=manifest_revision,
            event_type=f"manifest_{action}",
            event={
                "expectedGeneration": expected_generation,
                "generation": target_generation,
                "pointerMode": target_mode,
                "updatedBy": _text(updated_by),
            },
        )
        return {
            "status": "updated",
            "pointerMode": target_mode,
            "manifestRevision": manifest_revision,
            "generation": target_generation,
        }

    def compare_and_swap_pointer(self, command: dict[str, Any], *, updated_by: str) -> dict[str, Any]:
        self._validated_pointer_command(command, updated_by)
        with self.connection() as conn:
            with conn.cursor() as cur:
                return self._compare_and_swap_pointer_with_cursor(cur, command, updated_by=updated_by)

    def seal_manifest_and_compare_and_swap_pointer(
        self,
        manifest: dict[str, Any],
        command: dict[str, Any],
        *,
        updated_by: str,
    ) -> dict[str, Any]:
        revision = self._validated_manifest_revision(manifest)
        action, target_mode, command_revision, _, _ = self._validated_pointer_command(command, updated_by)
        if action != "promote" or target_mode != "active":
            raise ValueError("atomic Manifest activation requires an active promote command")
        if command_revision != revision:
            raise GearReleaseIntegrityError("pointer command does not target the supplied Manifest")
        with self.connection() as conn:
            with conn.cursor() as cur:
                seal = self._seal_manifest_with_cursor(cur, manifest)
                pointer = self._compare_and_swap_pointer_with_cursor(cur, command, updated_by=updated_by)
        return {"manifest": seal, "pointer": pointer}


__all__ = (
    "CandidateGearAuthorityIndex",
    "GearReleaseIntegrityError",
    "GearReleaseStore",
    "StaleManifestPointerError",
    "build_candidate_authority_context",
    "canonical_row_hash",
    "community_rows_summary",
    "gear_snapshot_summary",
)

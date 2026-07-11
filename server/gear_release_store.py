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


def build_candidate_authority_context(
    snapshot: dict[str, Any],
    selection_intent: dict[str, Any],
    runtime_authority: dict[str, Any],
    gear_release: dict[str, Any],
) -> dict[str, Any]:
    """Build an inactive candidate Authority Context from an exact sealed snapshot."""

    try:
        from .pg_gear_authority_loader import build_gear_authority_context_from_rows
        from .websim_payload import normalize_option_value
    except ImportError:
        from pg_gear_authority_loader import build_gear_authority_context_from_rows
        from websim_payload import normalize_option_value

    release = _exact_release_descriptor(gear_release)
    if release["releaseKind"] != "gear":
        raise GearReleaseIntegrityError("candidate authority requires a Gear Release")
    if gear_snapshot_summary(snapshot) != release["content"]:
        raise GearReleaseIntegrityError("candidate authority snapshot does not match Gear Release")
    authored = selection_intent.get("authoredAgainst") if isinstance(selection_intent, dict) else {}
    if not isinstance(authored, dict) or authored.get("seasonRevision") != release["seasonRevision"] or authored.get("gearCatalogRevision") != release["releaseId"]:
        raise GearReleaseIntegrityError("candidate Intent is not authored against the Gear Release")

    items = {row.get("itemId"): row for row in _canonical_rows(snapshot.get("items"))}
    sources_by_item: dict[str, list[dict[str, Any]]] = {}
    for row in _canonical_rows(snapshot.get("sources")):
        sources_by_item.setdefault(_text(row.get("itemId")), []).append(row)
    variants_by_item: dict[str, list[dict[str, Any]]] = {}
    for row in _canonical_rows(snapshot.get("variants")):
        variants_by_item.setdefault(_text(row.get("itemId")), []).append(row)
    options_by_key = {
        _text(row.get("optionKey")): row
        for row in _canonical_rows(snapshot.get("options"))
        if _text(row.get("optionKey"))
    }

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
        matching = [
            row for row in variants_by_item.get(item_id, [])
            if requested_variant
            and (
                _text(row.get("variantKey")) == requested_variant
                or normalize_option_value(row.get("variantKey")) == requested_variant
            )
        ]
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

    def snapshot_staging_community_templates(self, limit: int = 400) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(_int(limit), 400))
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cur.execute(
                    """
                    SELECT id, class_key, spec_key, name, source_key, source_name, source_url,
                           source_status, status, signature, source_refs_json, gear_items_json,
                           raw_string, ready_slot_count, missing_slots_json, analysis_window,
                           payload_json, updated_at, expires_at, scan_run_id
                    FROM cache.websim_community_gear_templates
                    ORDER BY class_key, spec_key, status, ready_slot_count DESC, updated_at DESC, id
                    LIMIT 400
                    """
                )
                rows = cur.fetchall()[:bounded_limit]
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

    def seal_manifest(self, manifest: dict[str, Any]) -> dict[str, str]:
        if not isinstance(manifest, dict) or not _text(manifest.get("manifestRevision")):
            raise GearReleaseIntegrityError("manifest must contain manifestRevision")
        revision = _text(manifest["manifestRevision"])
        if revision != _expected_manifest_revision(manifest):
            raise GearReleaseIntegrityError("manifest identity does not match manifestRevision")
        with self.connection() as conn:
            with conn.cursor() as cur:
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

    def get_active_pointer(self) -> dict[str, Any]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT environment, manifest_revision, generation, rollback_manifest_revision,
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
            "manifestRevision": _text(row[1]),
            "generation": _int(row[2]),
            "rollbackManifestRevision": _text(row[3]),
            "updatedAt": _text(row[4]),
            "updatedBy": _text(row[5]),
        }

    def compare_and_swap_pointer(self, command: dict[str, Any], *, updated_by: str) -> dict[str, Any]:
        required_fields = {
            "schemaRevision",
            "action",
            "environment",
            "manifestRevision",
            "expectedGeneration",
            "rollbackManifestRevision",
        }
        if not isinstance(command, dict) or set(command) != required_fields:
            raise ValueError("invalid pointer command")
        if command.get("schemaRevision") != "active-manifest-pointer-command-v1":
            raise ValueError("invalid pointer command schema")
        if command.get("action") not in {"promote", "rollback"}:
            raise ValueError("invalid pointer command action")
        if command.get("environment") != "retail":
            raise ValueError("invalid pointer command environment")
        if not _text(command.get("manifestRevision")):
            raise ValueError("pointer command requires manifestRevision")
        expected_generation = command.get("expectedGeneration")
        if isinstance(expected_generation, bool) or not isinstance(expected_generation, int) or expected_generation < 0:
            raise ValueError("expectedGeneration must be a non-negative integer")
        if not _text(updated_by):
            raise ValueError("updated_by is required")
        target_generation = expected_generation + 1
        with self.connection() as conn:
            with conn.cursor() as cur:
                if expected_generation == 0:
                    cur.execute(
                        """
                        INSERT INTO cache.websim_active_manifest_pointer (
                            environment, manifest_revision, generation, rollback_manifest_revision,
                            updated_by
                        )
                        SELECT 'retail', %s, %s, %s, %s
                        WHERE NOT EXISTS (
                            SELECT 1 FROM cache.websim_active_manifest_pointer WHERE environment = 'retail'
                        )
                        """,
                        (
                            command.get("manifestRevision"),
                            target_generation,
                            command.get("rollbackManifestRevision") or None,
                            _text(updated_by),
                        ),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE cache.websim_active_manifest_pointer
                        SET manifest_revision = %s,
                            generation = %s,
                            rollback_manifest_revision = %s,
                            updated_at = now(),
                            updated_by = %s
                        WHERE environment = 'retail' AND generation = %s
                        """,
                        (
                            command.get("manifestRevision"),
                            target_generation,
                            command.get("rollbackManifestRevision") or None,
                            _text(updated_by),
                            expected_generation,
                        ),
                    )
                if getattr(cur, "rowcount", 0) != 1:
                    raise StaleManifestPointerError("active manifest pointer generation changed")
                self._insert_event(
                    cur,
                    manifest_revision=_text(command.get("manifestRevision")),
                    event_type=f"manifest_{command.get('action')}",
                    event={
                        "expectedGeneration": expected_generation,
                        "generation": target_generation,
                        "updatedBy": _text(updated_by),
                    },
                )
        return {
            "status": "updated",
            "manifestRevision": _text(command.get("manifestRevision")),
            "generation": target_generation,
        }


__all__ = (
    "GearReleaseIntegrityError",
    "GearReleaseStore",
    "StaleManifestPointerError",
    "build_candidate_authority_context",
    "canonical_row_hash",
    "community_rows_summary",
    "gear_snapshot_summary",
)

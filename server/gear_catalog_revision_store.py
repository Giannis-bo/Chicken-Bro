#!/usr/bin/env python3
"""Single PostgreSQL owner for dormant immutable Gear Catalog revisions."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .gear_catalog_revision import verify_catalog_revision


class GearCatalogRevisionIntegrityError(RuntimeError):
    pass


def _text(value: Any) -> str:
    return str(value or "").strip()


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _row_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _header(catalog: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schemaRevision": _text(catalog.get("schemaRevision")),
        "status": _text(catalog.get("status")),
        "catalogRevision": _text(catalog.get("catalogRevision")),
        "builderRevision": _text(catalog.get("builderRevision")),
        "seasonRevision": _text(catalog.get("seasonRevision")),
        "dependencyVector": _canonical(_mapping(catalog.get("dependencyVector"))),
        "sourceSummary": _canonical(_mapping(catalog.get("sourceSummary"))),
        "contentSummary": _canonical(_mapping(catalog.get("contentSummary"))),
        "problemCodes": [],
        "problems": [],
    }


def _catalog_semantics(catalog: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **_header(catalog),
        "itemDefinitions": _canonical(catalog.get("itemDefinitions") or []),
        "browseVariants": _canonical(catalog.get("browseVariants") or []),
    }


class GearCatalogRevisionStore:
    """Seal, load and byte-verify one dormant Catalog identity."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def connection(self):
        return self._connection_factory()

    @staticmethod
    def _validate(catalog: Any) -> dict[str, Any]:
        if not isinstance(catalog, Mapping):
            raise GearCatalogRevisionIntegrityError(
                "verified catalog object is required"
            )
        normalized = _canonical(catalog)
        issues = verify_catalog_revision(normalized)
        if issues:
            raise GearCatalogRevisionIntegrityError(
                "catalog integrity check failed: " + ",".join(issues)
            )
        provenance = _mapping(normalized.get("provenance"))
        if not _text(provenance.get("sourceGearReleaseId")):
            raise GearCatalogRevisionIntegrityError(
                "source Gear Release provenance is required"
            )
        return normalized

    @staticmethod
    def _load_with_cursor(cur: Any, catalog_revision: str) -> dict[str, Any]:
        cur.execute(
            """
            /* gear_catalog_revision_load_catalog */
            SELECT
                catalog_revision,
                schema_revision,
                builder_revision,
                season_revision,
                source_gear_release_id,
                source_content_hash,
                dependency_vector_json,
                source_summary_json,
                content_summary_json,
                catalog_json,
                row_hash
            FROM cache.websim_gear_catalog_revisions
            WHERE catalog_revision = %s
            """,
            (catalog_revision,),
        )
        row = cur.fetchone()
        if not row:
            return {}
        header = _canonical(
            row[9] if isinstance(row[9], Mapping) else json.loads(row[9])
        )
        if (
            _row_hash(header) != _text(row[10])
            or _text(header.get("catalogRevision")) != _text(row[0])
            or _text(header.get("schemaRevision")) != _text(row[1])
            or _text(header.get("builderRevision")) != _text(row[2])
            or _text(header.get("seasonRevision")) != _text(row[3])
            or _canonical(header.get("dependencyVector") or {})
            != _canonical(row[6] if isinstance(row[6], Mapping) else json.loads(row[6]))
            or _canonical(header.get("sourceSummary") or {})
            != _canonical(row[7] if isinstance(row[7], Mapping) else json.loads(row[7]))
            or _canonical(header.get("contentSummary") or {})
            != _canonical(row[8] if isinstance(row[8], Mapping) else json.loads(row[8]))
            or _text(
                _mapping(header.get("sourceSummary")).get(
                    "gearReleaseContentHash"
                )
            )
            != _text(row[5])
        ):
            raise GearCatalogRevisionIntegrityError(
                "sealed catalog header integrity mismatch"
            )

        cur.execute(
            """
            /* gear_catalog_revision_load_items */
            SELECT
                catalog_revision,
                item_id,
                name,
                slot,
                item_level,
                source_status,
                definition_json,
                row_hash
            FROM cache.websim_gear_item_definitions
            WHERE catalog_revision = %s
            ORDER BY item_id
            """,
            (catalog_revision,),
        )
        definitions = []
        for item_row in cur.fetchall():
            definition = _canonical(
                item_row[6]
                if isinstance(item_row[6], Mapping)
                else json.loads(item_row[6])
            )
            if (
                _row_hash(definition) != _text(item_row[7])
                or _text(item_row[0]) != catalog_revision
                or _text(definition.get("itemId")) != _text(item_row[1])
                or _text(definition.get("name")) != _text(item_row[2])
                or _text(definition.get("slot")) != _text(item_row[3])
                or int(definition.get("itemLevel") or 0)
                != int(item_row[4] or 0)
                or _text(definition.get("sourceStatus"))
                != _text(item_row[5])
            ):
                raise GearCatalogRevisionIntegrityError(
                    "sealed item definition integrity mismatch"
                )
            definitions.append(definition)

        cur.execute(
            """
            /* gear_catalog_revision_load_variants */
            SELECT
                catalog_revision,
                browse_variant_key,
                item_id,
                progression_kind,
                progression_key,
                source_variant_keys_json,
                item_level,
                bonus_ids_json,
                static_facts_json,
                variant_json,
                row_hash
            FROM cache.websim_gear_browse_variants
            WHERE catalog_revision = %s
            ORDER BY item_id, progression_key, browse_variant_key
            """,
            (catalog_revision,),
        )
        variants = []
        for variant_row in cur.fetchall():
            variant = _canonical(
                variant_row[9]
                if isinstance(variant_row[9], Mapping)
                else json.loads(variant_row[9])
            )
            source_keys = _canonical(
                variant_row[5]
                if isinstance(variant_row[5], list)
                else json.loads(variant_row[5])
            )
            bonus_ids = _canonical(
                variant_row[7]
                if isinstance(variant_row[7], list)
                else json.loads(variant_row[7])
            )
            static_facts = _canonical(
                variant_row[8]
                if isinstance(variant_row[8], Mapping)
                else json.loads(variant_row[8])
            )
            if (
                _row_hash(variant) != _text(variant_row[10])
                or _text(variant_row[0]) != catalog_revision
                or _text(variant.get("browseVariantKey"))
                != _text(variant_row[1])
                or _text(variant.get("itemId")) != _text(variant_row[2])
                or _text(variant.get("progressionKind"))
                != _text(variant_row[3])
                or _text(variant.get("progressionKey"))
                != _text(variant_row[4])
                or _canonical(variant.get("sourceVariantKeys") or [])
                != source_keys
                or int(variant.get("itemLevel") or 0)
                != int(variant_row[6] or 0)
                or _canonical(variant.get("bonusIds") or []) != bonus_ids
                or _canonical(variant.get("staticFacts") or {})
                != static_facts
            ):
                raise GearCatalogRevisionIntegrityError(
                    "sealed BrowseVariant integrity mismatch"
                )
            variants.append(variant)

        result = {
            **header,
            "itemDefinitions": definitions,
            "browseVariants": variants,
            "provenance": {
                "sourceGearReleaseId": _text(row[4]),
            },
        }
        issues = verify_catalog_revision(result)
        if issues:
            raise GearCatalogRevisionIntegrityError(
                "sealed catalog content mismatch: " + ",".join(issues)
            )
        return result

    def load_catalog(self, catalog_revision: str) -> dict[str, Any]:
        revision = _text(catalog_revision)
        with self.connection() as conn:
            with conn.cursor() as cur:
                return self._load_with_cursor(cur, revision)

    def seal_catalog(self, catalog: Any) -> dict[str, Any]:
        expected = self._validate(catalog)
        header = _header(expected)
        provenance = _mapping(expected.get("provenance"))
        revision = _text(expected.get("catalogRevision"))
        source_summary = _mapping(expected.get("sourceSummary"))
        definitions = expected.get("itemDefinitions") or []
        variants = expected.get("browseVariants") or []

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    /* gear_catalog_revision_insert */
                    INSERT INTO cache.websim_gear_catalog_revisions (
                        catalog_revision,
                        schema_revision,
                        builder_revision,
                        season_revision,
                        source_gear_release_id,
                        source_content_hash,
                        dependency_vector_json,
                        source_summary_json,
                        content_summary_json,
                        catalog_json,
                        row_hash
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        revision,
                        _text(expected.get("schemaRevision")),
                        _text(expected.get("builderRevision")),
                        _text(expected.get("seasonRevision")),
                        _text(provenance.get("sourceGearReleaseId")),
                        _text(source_summary.get("gearReleaseContentHash")),
                        _json(expected.get("dependencyVector") or {}),
                        _json(source_summary),
                        _json(expected.get("contentSummary") or {}),
                        _json(header),
                        _row_hash(header),
                    ),
                )
                cur.executemany(
                    """
                    /* gear_catalog_revision_insert_items */
                    INSERT INTO cache.websim_gear_item_definitions (
                        catalog_revision,
                        item_id,
                        name,
                        slot,
                        item_level,
                        source_status,
                        definition_json,
                        row_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    [
                        (
                            revision,
                            _text(definition.get("itemId")),
                            _text(definition.get("name")),
                            _text(definition.get("slot")),
                            int(definition.get("itemLevel") or 0),
                            _text(definition.get("sourceStatus")),
                            _json(definition),
                            _row_hash(definition),
                        )
                        for definition in definitions
                    ],
                )
                cur.executemany(
                    """
                    /* gear_catalog_revision_insert_variants */
                    INSERT INTO cache.websim_gear_browse_variants (
                        catalog_revision,
                        browse_variant_key,
                        item_id,
                        progression_kind,
                        progression_key,
                        source_variant_keys_json,
                        item_level,
                        bonus_ids_json,
                        static_facts_json,
                        variant_json,
                        row_hash
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s::jsonb, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    [
                        (
                            revision,
                            _text(variant.get("browseVariantKey")),
                            _text(variant.get("itemId")),
                            _text(variant.get("progressionKind")),
                            _text(variant.get("progressionKey")),
                            _json(variant.get("sourceVariantKeys") or []),
                            int(variant.get("itemLevel") or 0),
                            _json(variant.get("bonusIds") or []),
                            _json(variant.get("staticFacts") or {}),
                            _json(variant),
                            _row_hash(variant),
                        )
                        for variant in variants
                    ],
                )
                sealed = self._load_with_cursor(cur, revision)
                if _catalog_semantics(sealed) != _catalog_semantics(expected):
                    raise GearCatalogRevisionIntegrityError(
                        "sealed catalog content mismatch"
                    )
                return sealed


__all__ = (
    "GearCatalogRevisionIntegrityError",
    "GearCatalogRevisionStore",
)

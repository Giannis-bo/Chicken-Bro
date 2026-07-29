#!/usr/bin/env python3
"""Single PostgreSQL owner for dormant immutable exact gear registries."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

try:
    from .gear_exact_item_registry import (
        EXACT_REGISTRY_EVIDENCE_GAP_CODES,
        verify_exact_item_registry,
    )
except ImportError:
    from gear_exact_item_registry import (
        EXACT_REGISTRY_EVIDENCE_GAP_CODES,
        verify_exact_item_registry,
    )


class GearExactItemRegistryIntegrityError(RuntimeError):
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


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return _canonical(value)
    return json.loads(value)


def _contains_private_owner_key(value: Any) -> bool:
    forbidden = {
        "accesstoken",
        "charactername",
        "owner",
        "ownerid",
        "ownername",
        "playerid",
        "profileurl",
        "sourcetemplateid",
        "templateid",
        "templateidentity",
        "token",
        "userid",
    }
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).replace("_", "").replace("-", "").lower()
            if normalized in forbidden or _contains_private_owner_key(item):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_private_owner_key(item) for item in value)
    return False


class GearExactItemRegistryStore:
    """Seal, load and byte-verify one dormant exact registry."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def connection(self):
        return self._connection_factory()

    def latest_registry_revision(
        self,
        *,
        catalog_revision: str = "",
        gear_rule_revision: str = "",
    ) -> str:
        catalog = _text(catalog_revision)
        rule = _text(gear_rule_revision)
        where = []
        params: list[str] = []
        if catalog:
            where.append("catalog_revision = %s")
            params.append(catalog)
        if rule:
            where.append("gear_rule_revision = %s")
            params.append(rule)
        predicate = "WHERE " + " AND ".join(where) if where else ""
        with self.connection() as connection:
            with connection.cursor() as cur:
                cur.execute(
                    f"""
                    /* gear_exact_registry_latest_revision */
                    SELECT registry_revision
                    FROM cache.websim_gear_exact_instance_template_refs
                    {predicate}
                    GROUP BY registry_revision
                    ORDER BY MAX(sealed_at) DESC, registry_revision DESC
                    LIMIT 1
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
                return _text(row[0]) if row else ""

    def load_latest_registry(
        self,
        *,
        catalog_revision: str,
        gear_rule_revision: str,
    ) -> dict[str, Any]:
        revision = self.latest_registry_revision(
            catalog_revision=catalog_revision,
            gear_rule_revision=gear_rule_revision,
        )
        return self.load_registry(revision) if revision else {}

    @staticmethod
    def _validate(registry: Any) -> dict[str, Any]:
        if not isinstance(registry, Mapping):
            raise GearExactItemRegistryIntegrityError(
                "verified exact registry object is required"
            )
        normalized = dict(registry)
        if _contains_private_owner_key(normalized):
            raise GearExactItemRegistryIntegrityError(
                "personal owner or source template identity is forbidden"
            )
        issues = verify_exact_item_registry(normalized)
        if issues:
            raise GearExactItemRegistryIntegrityError(
                "exact registry integrity check failed: " + ",".join(issues)
            )
        status = _text(normalized.get("status"))
        problem_codes = {
            _text(code)
            for code in normalized.get("problemCodes") or []
            if _text(code)
        }
        if status not in {"verified", "partial"}:
            raise GearExactItemRegistryIntegrityError(
                "blocked exact registries may not be sealed"
            )
        if (
            (status == "verified" and problem_codes)
            or (
                status == "partial"
                and (
                    not problem_codes
                    or not problem_codes <= EXACT_REGISTRY_EVIDENCE_GAP_CODES
                )
            )
        ):
            raise GearExactItemRegistryIntegrityError(
                "exact registry status and evidence gaps are inconsistent"
            )
        references = normalized.get("templateReferences") or []
        if not references:
            raise GearExactItemRegistryIntegrityError(
                "exact registry requires template references"
            )
        for row in references:
            reference_status = _text(row.get("validationStatus"))
            exact_key = _text(row.get("exactItemInstanceKey"))
            reference_codes = {
                _text(code)
                for code in row.get("problemCodes") or []
                if _text(code)
            }
            if (
                reference_status == "verified"
                and exact_key
                and not reference_codes
            ):
                continue
            if (
                reference_status == "partial"
                and not exact_key
                and reference_codes
                and reference_codes <= EXACT_REGISTRY_EVIDENCE_GAP_CODES
            ):
                continue
            raise GearExactItemRegistryIntegrityError(
                "exact registry contains unsafe template references"
            )
        return normalized

    @staticmethod
    def _load_header_with_cursor(
        cur: Any,
        registry_revision: str,
    ) -> dict[str, Any]:
        cur.execute(
            """
            /* gear_exact_registry_load_header */
            SELECT
                registry_revision,
                catalog_revision,
                season_revision,
                gear_rule_revision,
                registry_status,
                registry_summary_json::text,
                registry_problem_codes_json::text
            FROM cache.websim_gear_exact_registries
            WHERE registry_revision = %s
            """,
            (registry_revision,),
        )
        header = cur.fetchone()
        if not header:
            return {}
        return {
            "schemaRevision": "gear-exact-item-registry-header-v1",
            "status": _text(header[4]),
            "registryRevision": _text(header[0]),
            "catalogRevision": _text(header[1]),
            "seasonRevision": _text(header[2]),
            "gearRuleRevision": _text(header[3]),
            "summary": _json_value(header[5]),
            "problemCodes": _json_value(header[6]),
            "problems": [],
        }

    @staticmethod
    def _load_with_cursor(cur: Any, registry_revision: str) -> dict[str, Any]:
        header = GearExactItemRegistryStore._load_header_with_cursor(
            cur,
            registry_revision,
        )
        if not header:
            return {}
        cur.execute(
            """
            /* gear_exact_registry_load_refs */
            SELECT
                registry_revision,
                catalog_revision,
                season_revision,
                gear_rule_revision,
                registry_status,
                registry_summary_json::text,
                registry_problem_codes_json::text,
                template_scope,
                template_content_hash,
                slot,
                item_id,
                source_variant_key,
                exact_item_instance_key,
                validation_status,
                problem_codes_json::text,
                reference_json::text,
                row_hash
            FROM cache.websim_gear_exact_instance_template_refs
            WHERE registry_revision = %s
            ORDER BY
                template_scope,
                template_content_hash,
                slot,
                item_id,
                source_variant_key,
                row_hash
            """,
            (registry_revision,),
        )
        ref_rows = cur.fetchall()
        if not ref_rows:
            raise GearExactItemRegistryIntegrityError(
                "sealed exact registry header mismatch"
            )

        first = ref_rows[0]
        catalog_revision = _text(first[1])
        season_revision = _text(first[2])
        gear_rule_revision = _text(first[3])
        status = _text(first[4])
        summary = _json_value(first[5])
        problem_codes = _json_value(first[6])
        if (
            _text(header.get("registryRevision")) != registry_revision
            or _text(header.get("catalogRevision")) != catalog_revision
            or _text(header.get("seasonRevision")) != season_revision
            or _text(header.get("gearRuleRevision")) != gear_rule_revision
            or _text(header.get("status")) != status
            or _canonical(header.get("summary") or {}) != summary
            or _canonical(header.get("problemCodes") or [])
            != problem_codes
        ):
            raise GearExactItemRegistryIntegrityError(
                "sealed exact registry header mismatch"
            )
        references: list[dict[str, Any]] = []
        exact_keys: set[str] = set()
        for stored in ref_rows:
            reference = _json_value(stored[15])
            if (
                _text(stored[0]) != registry_revision
                or _text(stored[1]) != catalog_revision
                or _text(stored[2]) != season_revision
                or _text(stored[3]) != gear_rule_revision
                or _text(stored[4]) != status
                or _json_value(stored[5]) != summary
                or _json_value(stored[6]) != problem_codes
                or _text(reference.get("templateScope")) != _text(stored[7])
                or _text(reference.get("templateContentHash"))
                != _text(stored[8])
                or _text(reference.get("slot")) != _text(stored[9])
                or _text(reference.get("itemId")) != _text(stored[10])
                or _text(reference.get("sourceVariantKey")) != _text(stored[11])
                or _text(reference.get("exactItemInstanceKey"))
                != _text(stored[12])
                or _text(reference.get("validationStatus"))
                != _text(stored[13])
                or _canonical(reference.get("problemCodes") or [])
                != _json_value(stored[14])
                or _row_hash({
                    key: value
                    for key, value in reference.items()
                    if key != "rowHash"
                })
                != _text(stored[16])
                or _text(reference.get("rowHash")) != _text(stored[16])
            ):
                raise GearExactItemRegistryIntegrityError(
                    "sealed template reference integrity mismatch"
                )
            references.append(reference)
            if _text(stored[12]):
                exact_keys.add(_text(stored[12]))

        cur.execute(
            """
            /* gear_exact_registry_load_instances */
            SELECT
                exact_item_instance_key,
                exact_variant_signature,
                enhancement_selection_key,
                schema_revision,
                item_id,
                item_level,
                bonus_ids_json::text,
                context_json::text,
                progression_state_json::text,
                instance_json::text,
                row_hash
            FROM cache.websim_gear_exact_item_instances
            WHERE exact_item_instance_key = ANY(%s)
            ORDER BY exact_item_instance_key
            """,
            (sorted(exact_keys),),
        )
        instances: list[dict[str, Any]] = []
        selection_keys: set[str] = set()
        for stored in cur.fetchall():
            instance = _json_value(stored[9])
            if (
                _text(instance.get("exactItemInstanceKey")) != _text(stored[0])
                or _text(instance.get("exactVariantSignature")) != _text(stored[1])
                or _text(instance.get("enhancementSelectionKey")) != _text(stored[2])
                or _text(instance.get("schemaRevision")) != _text(stored[3])
                or _text(instance.get("itemId")) != _text(stored[4])
                or int(instance.get("ilevel") or 0) != int(stored[5] or 0)
                or _canonical(instance.get("bonusIds") or [])
                != _json_value(stored[6])
                or _canonical(instance.get("context"))
                != _json_value(stored[7])
                or _canonical(instance.get("progressionState") or {})
                != _json_value(stored[8])
                or _row_hash({
                    key: value
                    for key, value in instance.items()
                    if key != "rowHash"
                })
                != _text(stored[10])
                or _text(instance.get("rowHash")) != _text(stored[10])
            ):
                raise GearExactItemRegistryIntegrityError(
                    "sealed exact instance integrity mismatch"
                )
            instances.append(instance)
            selection_keys.add(_text(stored[2]))
        if {row["exactItemInstanceKey"] for row in instances} != exact_keys:
            raise GearExactItemRegistryIntegrityError(
                "sealed exact instance membership mismatch"
            )

        cur.execute(
            """
            /* gear_exact_registry_load_selections */
            SELECT
                enhancement_selection_key,
                schema_revision,
                selection_json::text,
                row_hash
            FROM cache.websim_gear_enhancement_selections
            WHERE enhancement_selection_key = ANY(%s)
            ORDER BY enhancement_selection_key
            """,
            (sorted(selection_keys),),
        )
        selections: list[dict[str, Any]] = []
        for stored in cur.fetchall():
            selection = _json_value(stored[2])
            row = {
                "enhancementSelectionKey": _text(stored[0]),
                "selection": selection,
                "rowHash": _text(stored[3]),
            }
            if (
                _text(selection.get("schemaRevision")) != _text(stored[1])
                or _row_hash({
                    "enhancementSelectionKey": row["enhancementSelectionKey"],
                    "selection": selection,
                })
                != row["rowHash"]
            ):
                raise GearExactItemRegistryIntegrityError(
                    "sealed enhancement selection integrity mismatch"
                )
            selections.append(row)
        if {
            row["enhancementSelectionKey"] for row in selections
        } != selection_keys:
            raise GearExactItemRegistryIntegrityError(
                "sealed enhancement selection membership mismatch"
            )

        cur.execute(
            """
            /* gear_exact_registry_load_validations */
            SELECT
                exact_item_instance_key,
                catalog_revision,
                gear_rule_revision,
                schema_revision,
                validation_status,
                slot,
                source_variant_key,
                static_facts_json::text,
                serializer_input_json::text,
                validation_json::text,
                row_hash
            FROM cache.websim_gear_exact_item_validations
            WHERE exact_item_instance_key = ANY(%s)
              AND catalog_revision = %s
              AND gear_rule_revision = %s
            ORDER BY exact_item_instance_key
            """,
            (sorted(exact_keys), catalog_revision, gear_rule_revision),
        )
        validations: list[dict[str, Any]] = []
        for stored in cur.fetchall():
            validation = _json_value(stored[9])
            if (
                _text(validation.get("exactItemInstanceKey")) != _text(stored[0])
                or _text(validation.get("catalogRevision")) != _text(stored[1])
                or _text(validation.get("gearRuleRevision")) != _text(stored[2])
                or _text(validation.get("schemaRevision")) != _text(stored[3])
                or _text(validation.get("status")) != _text(stored[4])
                or _text(stored[5])
                or _text(stored[6])
                or _canonical(validation.get("staticFacts") or {})
                != _json_value(stored[7])
                or _canonical(validation.get("serializerInput") or {})
                != _json_value(stored[8])
                or _row_hash({
                    key: value
                    for key, value in validation.items()
                    if key != "rowHash"
                })
                != _text(stored[10])
                or _text(validation.get("rowHash")) != _text(stored[10])
            ):
                raise GearExactItemRegistryIntegrityError(
                    "sealed exact validation integrity mismatch"
                )
            validations.append(validation)
        if {
            row["exactItemInstanceKey"] for row in validations
        } != exact_keys:
            raise GearExactItemRegistryIntegrityError(
                "sealed exact validation membership mismatch"
            )

        result = {
            "schemaRevision": "gear-exact-item-registry-v1",
            "status": status,
            "registryRevision": registry_revision,
            "catalogRevision": catalog_revision,
            "seasonRevision": season_revision,
            "gearRuleRevision": gear_rule_revision,
            "enhancementSelections": selections,
            "exactItemInstances": instances,
            "validations": validations,
            "templateReferences": references,
            "summary": summary,
            "problemCodes": problem_codes,
            "problems": [],
        }
        issues = verify_exact_item_registry(result)
        if issues:
            raise GearExactItemRegistryIntegrityError(
                "sealed exact registry content mismatch: " + ",".join(issues)
            )
        return result

    def load_registry(self, registry_revision: str) -> dict[str, Any]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                return self._load_with_cursor(cur, _text(registry_revision))

    def seal_registry(self, registry: Any) -> dict[str, Any]:
        expected = self._validate(registry)
        revision = _text(expected.get("registryRevision"))
        catalog = _text(expected.get("catalogRevision"))
        season = _text(expected.get("seasonRevision"))
        rule = _text(expected.get("gearRuleRevision"))
        status = _text(expected.get("status"))
        summary = expected.get("summary") or {}
        problem_codes = expected.get("problemCodes") or []

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    /* gear_exact_registry_insert_header */
                    INSERT INTO cache.websim_gear_exact_registries (
                        registry_revision,
                        catalog_revision,
                        season_revision,
                        gear_rule_revision,
                        registry_status,
                        registry_summary_json,
                        registry_problem_codes_json
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        revision,
                        catalog,
                        season,
                        rule,
                        status,
                        _json(summary),
                        _json(problem_codes),
                    ),
                )
                cur.executemany(
                    """
                    /* gear_exact_registry_insert_selections */
                    INSERT INTO cache.websim_gear_enhancement_selections (
                        enhancement_selection_key,
                        schema_revision,
                        selection_json,
                        row_hash
                    ) VALUES (%s, %s, %s::jsonb, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    [
                        (
                            row["enhancementSelectionKey"],
                            _text(row.get("selection", {}).get("schemaRevision")),
                            _json(row.get("selection") or {}),
                            row["rowHash"],
                        )
                        for row in expected.get("enhancementSelections") or []
                    ],
                )
                cur.executemany(
                    """
                    /* gear_exact_registry_insert_instances */
                    INSERT INTO cache.websim_gear_exact_item_instances (
                        exact_item_instance_key,
                        exact_variant_signature,
                        enhancement_selection_key,
                        schema_revision,
                        item_id,
                        item_level,
                        bonus_ids_json,
                        context_json,
                        progression_state_json,
                        instance_json,
                        row_hash
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    [
                        (
                            row["exactItemInstanceKey"],
                            row["exactVariantSignature"],
                            row["enhancementSelectionKey"],
                            row["schemaRevision"],
                            row["itemId"],
                            int(row.get("ilevel") or 0),
                            _json(row.get("bonusIds") or []),
                            _json(row.get("context")),
                            _json(row.get("progressionState") or {}),
                            _json(row),
                            row["rowHash"],
                        )
                        for row in expected.get("exactItemInstances") or []
                    ],
                )
                cur.executemany(
                    """
                    /* gear_exact_registry_insert_validations */
                    INSERT INTO cache.websim_gear_exact_item_validations (
                        exact_item_instance_key,
                        catalog_revision,
                        gear_rule_revision,
                        schema_revision,
                        validation_status,
                        slot,
                        source_variant_key,
                        static_facts_json,
                        serializer_input_json,
                        validation_json,
                        row_hash
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s::jsonb, %s::jsonb, %s::jsonb, %s
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    [
                        (
                            row["exactItemInstanceKey"],
                            row["catalogRevision"],
                            row["gearRuleRevision"],
                            row["schemaRevision"],
                            row["status"],
                            "",
                            "",
                            _json(row.get("staticFacts") or {}),
                            _json(row.get("serializerInput") or {}),
                            _json(row),
                            row["rowHash"],
                        )
                        for row in expected.get("validations") or []
                    ],
                )
                cur.executemany(
                    """
                    /* gear_exact_registry_insert_refs */
                    INSERT INTO cache.websim_gear_exact_instance_template_refs (
                        registry_revision,
                        catalog_revision,
                        season_revision,
                        gear_rule_revision,
                        registry_status,
                        registry_summary_json,
                        registry_problem_codes_json,
                        template_scope,
                        template_content_hash,
                        slot,
                        item_id,
                        source_variant_key,
                        exact_item_instance_key,
                        validation_status,
                        problem_codes_json,
                        reference_json,
                        row_hash
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                        %s, %s, %s, %s, %s, %s, %s,
                        %s::jsonb, %s::jsonb, %s
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    [
                        (
                            revision,
                            catalog,
                            season,
                            rule,
                            status,
                            _json(summary),
                            _json(problem_codes),
                            row["templateScope"],
                            row["templateContentHash"],
                            row["slot"],
                            row["itemId"],
                            row["sourceVariantKey"],
                            _text(row.get("exactItemInstanceKey")) or None,
                            row["validationStatus"],
                            _json(row.get("problemCodes") or []),
                            _json(row),
                            row["rowHash"],
                        )
                        for row in expected.get("templateReferences") or []
                    ],
                )
                # The revision verifier binds the complete row set. Release
                # the owned input before the byte-verified PostgreSQL reload.
                del expected, registry
                sealed = self._load_with_cursor(cur, revision)
                if _text(sealed.get("registryRevision")) != revision:
                    raise GearExactItemRegistryIntegrityError(
                        "sealed exact registry content mismatch"
                    )
                return sealed


__all__ = (
    "GearExactItemRegistryIntegrityError",
    "GearExactItemRegistryStore",
)

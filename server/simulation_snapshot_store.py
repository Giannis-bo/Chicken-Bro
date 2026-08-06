#!/usr/bin/env python3
"""Append-only PostgreSQL owner for ResolvedLoadout and SimulationSnapshot."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

try:
    from .gear_canonical_kernel import (
        CanonicalValueError,
        canonical_identity_token,
        canonical_int,
    )
    from .gear_exact_authority_store import (
        GearExactAuthorityStore,
        GearExactAuthorityStoreIntegrityError,
    )
    from .gear_loadout_effect_authority import (
        reload_loadout_effect_authority,
    )
    from .gear_resolved_loadout import (
        RESOLVED_LOADOUT_V2_SCHEMA_REVISION,
        verify_resolved_loadout,
        verify_resolved_loadout_v2,
    )
    from .simc_item_effect_support import reload_effect_record
    from .simulation_snapshot import (
        SIMULATION_SNAPSHOT_V2_SCHEMA_REVISION,
        verify_simulation_snapshot,
        verify_simulation_snapshot_v2,
    )
except ImportError:
    from gear_canonical_kernel import (
        CanonicalValueError,
        canonical_identity_token,
        canonical_int,
    )
    from gear_exact_authority_store import (
        GearExactAuthorityStore,
        GearExactAuthorityStoreIntegrityError,
    )
    from gear_loadout_effect_authority import reload_loadout_effect_authority
    from gear_resolved_loadout import (
        RESOLVED_LOADOUT_V2_SCHEMA_REVISION,
        verify_resolved_loadout,
        verify_resolved_loadout_v2,
    )
    from simulation_snapshot import (
        SIMULATION_SNAPSHOT_V2_SCHEMA_REVISION,
        verify_simulation_snapshot,
        verify_simulation_snapshot_v2,
    )
    from simc_item_effect_support import reload_effect_record


RESULT_IDENTITY_PATTERN = re.compile(r"^simc-result:sha256:[0-9a-f]{64}$")
_LOADOUT_V2_KEY_PATTERN = re.compile(r"^resolved-loadout-v2:sha256:[0-9a-f]{64}$")
_SNAPSHOT_V2_KEY_PATTERN = re.compile(r"^simulation-snapshot-v2:sha256:[0-9a-f]{64}$")
_LOADOUT_EFFECT_AUTHORITY_KEY_PATTERN = re.compile(
    r"^loadout-effect-authority:sha256:[0-9a-f]{64}$"
)
_RESOLVER_REPLAY_CONTEXT_SCHEMA_REVISION = "exact-resolver-replay-context-v1"
_MAX_RESOLVER_REPLAY_CONTEXT_BYTES = 1048576
_FORBIDDEN_RESOLVER_REPLAY_SEMANTIC_KEYS = frozenset({
    "Catalog",
    "catalogRevision",
    "rawProfile",
    "rawString",
    "player",
    "playerName",
    "characterName",
    "realm",
    "server",
    "source",
    "sourceRefIds",
    "sourcePayload",
})


class SimulationSnapshotIntegrityError(RuntimeError):
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


def _require_native_v2_json(value: Any, *, field: str) -> None:
    """Reject lossy Python values before a v2 verifier sees canonical JSON."""
    value_type = type(value)
    if value_type is dict:
        for key, nested in value.items():
            if type(key) is not str:
                raise SimulationSnapshotIntegrityError(
                    f"{field} must contain only native JSON values"
                )
            _require_native_v2_json(nested, field=field)
        return
    if value_type is list:
        for nested in value:
            _require_native_v2_json(nested, field=field)
        return
    if value is None or value_type in {str, int, float, bool}:
        return
    raise SimulationSnapshotIntegrityError(
        f"{field} must contain only native JSON values"
    )


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return _canonical(value)
    return json.loads(value)


def _row_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


class SimulationSnapshotStore:
    """Seal and exactly reload immutable execution inputs and result bindings."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def connection(self):
        return self._connection_factory()

    @staticmethod
    def _validate_loadout(
        value: Any,
        *,
        resolver_snapshot: Any = None,
        authority_bundles: Any = None,
        loadout_effect_authority: Any = None,
    ) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise SimulationSnapshotIntegrityError("ready ResolvedLoadout is required")
        if value.get("schemaRevision") == RESOLVED_LOADOUT_V2_SCHEMA_REVISION:
            _require_native_v2_json(value, field="v2 ResolvedLoadout")
            _require_native_v2_json(
                resolver_snapshot,
                field="v2 resolver snapshot",
            )
        row = _canonical(value)
        if row.get("schemaRevision") == RESOLVED_LOADOUT_V2_SCHEMA_REVISION:
            if resolver_snapshot is None or authority_bundles is None:
                raise SimulationSnapshotIntegrityError(
                    "v2 ResolvedLoadout verifier context is required"
                )
            issues = verify_resolved_loadout_v2(
                row,
                resolver_snapshot=resolver_snapshot,
                authority_bundles=authority_bundles,
                loadout_effect_authority=loadout_effect_authority,
            )
        else:
            issues = verify_resolved_loadout(row)
        if issues:
            raise SimulationSnapshotIntegrityError(
                "ResolvedLoadout integrity check failed: " + ",".join(issues)
            )
        return row

    @staticmethod
    def _validate_snapshot(
        value: Any,
        *,
        resolved_loadout: Any = None,
        resolver_snapshot: Any = None,
        authority_bundles: Any = None,
        compiler_revision: Any = None,
        loadout_effect_authority: Any = None,
    ) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise SimulationSnapshotIntegrityError(
                "ready SimulationSnapshot is required"
            )
        if value.get("schemaRevision") == SIMULATION_SNAPSHOT_V2_SCHEMA_REVISION:
            _require_native_v2_json(value, field="v2 SimulationSnapshot")
            _require_native_v2_json(
                resolved_loadout,
                field="v2 ResolvedLoadout context",
            )
            _require_native_v2_json(
                resolver_snapshot,
                field="v2 resolver snapshot",
            )
        row = _canonical(value)
        if row.get("status") != "ready" or row.get("resultIdentity"):
            raise SimulationSnapshotIntegrityError(
                "only an unexecuted ready SimulationSnapshot may be sealed"
            )
        if row.get("schemaRevision") == SIMULATION_SNAPSHOT_V2_SCHEMA_REVISION:
            if (
                resolved_loadout is None
                or resolver_snapshot is None
                or authority_bundles is None
                or compiler_revision is None
            ):
                raise SimulationSnapshotIntegrityError(
                    "v2 SimulationSnapshot verifier context is required"
                )
            issues = verify_simulation_snapshot_v2(
                row,
                resolved_loadout=resolved_loadout,
                resolver_snapshot=resolver_snapshot,
                authority_bundles=authority_bundles,
                compiler_revision=compiler_revision,
                loadout_effect_authority=loadout_effect_authority,
            )
        else:
            issues = verify_simulation_snapshot(row)
        if issues:
            raise SimulationSnapshotIntegrityError(
                "SimulationSnapshot integrity check failed: " + ",".join(issues)
            )
        return row

    @staticmethod
    def _load_loadout_with_cursor(cur: Any, key: str) -> dict[str, Any]:
        if _LOADOUT_V2_KEY_PATTERN.fullmatch(key):
            raise SimulationSnapshotIntegrityError(
                "v2 ResolvedLoadout reload requires the store instance"
            )
        cur.execute(
            """
            /* simulation_snapshot_loadout_load */
            SELECT
                resolved_loadout_key,
                schema_revision,
                catalog_revision,
                gear_rule_revision,
                exact_registry_revision,
                class_key,
                spec_key,
                loadout_json::text,
                row_hash
            FROM cache.websim_gear_resolved_loadouts
            WHERE resolved_loadout_key = %s
            """,
            (key,),
        )
        stored = cur.fetchone()
        if not stored:
            return {}
        row = _json_value(stored[7])
        if (
            _text(row.get("resolvedLoadoutKey")) != _text(stored[0])
            or _text(row.get("schemaRevision")) != _text(stored[1])
            or _text(row.get("catalogRevision")) != _text(stored[2])
            or _text(row.get("gearRuleRevision")) != _text(stored[3])
            or _text(row.get("exactRegistryRevision")) != _text(stored[4])
            or _text(row.get("eligibilityContext", {}).get("classKey"))
            != _text(stored[5])
            or _text(row.get("eligibilityContext", {}).get("specKey"))
            != _text(stored[6])
            or _text(row.get("rowHash")) != _text(stored[8])
            or verify_resolved_loadout(row)
        ):
            raise SimulationSnapshotIntegrityError(
                "sealed ResolvedLoadout integrity mismatch"
            )
        return row

    @staticmethod
    def _load_snapshot_with_cursor(cur: Any, key: str) -> dict[str, Any]:
        if _SNAPSHOT_V2_KEY_PATTERN.fullmatch(key):
            raise SimulationSnapshotIntegrityError(
                "v2 SimulationSnapshot reload requires the store instance"
            )
        cur.execute(
            """
            /* simulation_snapshot_load */
            SELECT
                simulation_snapshot_key,
                schema_revision,
                resolved_loadout_key,
                talent_profile_key,
                compiler_revision,
                simc_runtime_revision,
                canonical_input_hash,
                catalog_revision,
                gear_rule_revision,
                snapshot_json::text,
                row_hash
            FROM cache.websim_simulation_snapshots
            WHERE simulation_snapshot_key = %s
            """,
            (key,),
        )
        stored = cur.fetchone()
        if not stored:
            return {}
        row = _json_value(stored[9])
        if (
            _text(row.get("simulationSnapshotKey")) != _text(stored[0])
            or _text(row.get("schemaRevision")) != _text(stored[1])
            or _text(row.get("resolvedLoadoutKey")) != _text(stored[2])
            or _text(row.get("talentProfileKey")) != _text(stored[3])
            or _text(row.get("compilerRevision")) != _text(stored[4])
            or _text(row.get("simcRuntimeRevision")) != _text(stored[5])
            or _text(row.get("canonicalInputHash")) != _text(stored[6])
            or _text(row.get("catalogRevision")) != _text(stored[7])
            or _text(row.get("gearRuleRevision")) != _text(stored[8])
            or _text(row.get("rowHash")) != _text(stored[10])
            or verify_simulation_snapshot(row)
        ):
            raise SimulationSnapshotIntegrityError(
                "sealed simulation snapshot integrity mismatch"
            )
        return row

    @staticmethod
    def _resolver_replay_set_state(value: Any) -> dict[str, Any]:
        """Project only the typed set-state values consumed by v2 verifiers."""
        if type(value) is not dict or set(value) != {
            "itemSetCounts",
            "activeDynamicEffects",
        }:
            raise SimulationSnapshotIntegrityError(
                "v2 resolver replay context is invalid"
            )
        raw_counts = value.get("itemSetCounts")
        raw_effects = value.get("activeDynamicEffects")
        if type(raw_counts) is not dict or type(raw_effects) is not list:
            raise SimulationSnapshotIntegrityError(
                "v2 resolver replay context is invalid"
            )

        counts: dict[str, int] = {}
        try:
            for raw_set_id, raw_count in raw_counts.items():
                set_id = canonical_identity_token(
                    raw_set_id,
                    path="resolverSnapshot.setState.itemSetCounts",
                )
                if set_id in _FORBIDDEN_RESOLVER_REPLAY_SEMANTIC_KEYS:
                    raise CanonicalValueError(
                        "FORBIDDEN_REPLAY_SEMANTIC",
                        f"resolverSnapshot.setState.itemSetCounts.{set_id}",
                    )
                counts[set_id] = canonical_int(
                    raw_count,
                    path=f"resolverSnapshot.setState.itemSetCounts.{set_id}",
                    minimum=1,
                    maximum=16,
                )

            effects: list[dict[str, Any]] = []
            for index, raw_effect in enumerate(raw_effects):
                if type(raw_effect) is not dict or set(raw_effect) != {
                    "effectId",
                    "itemSetId",
                    "pieces",
                    "sourceRefIds",
                }:
                    raise CanonicalValueError(
                        "INVALID_MAPPING",
                        f"resolverSnapshot.setState.activeDynamicEffects[{index}]",
                    )
                source_refs = raw_effect.get("sourceRefIds")
                if type(source_refs) is not list or any(
                    type(source_ref) is not str for source_ref in source_refs
                ):
                    raise CanonicalValueError(
                        "INVALID_ORDERED_LIST",
                        f"resolverSnapshot.setState.activeDynamicEffects[{index}].sourceRefIds",
                    )
                effects.append({
                    "effectId": canonical_identity_token(
                        raw_effect.get("effectId"),
                        path=f"resolverSnapshot.setState.activeDynamicEffects[{index}].effectId",
                    ),
                    "itemSetId": canonical_identity_token(
                        raw_effect.get("itemSetId"),
                        path=f"resolverSnapshot.setState.activeDynamicEffects[{index}].itemSetId",
                    ),
                    "pieces": canonical_int(
                        raw_effect.get("pieces"),
                        path=f"resolverSnapshot.setState.activeDynamicEffects[{index}].pieces",
                        minimum=1,
                        maximum=16,
                    ),
                })
        except CanonicalValueError as error:
            raise SimulationSnapshotIntegrityError(
                "v2 resolver replay context is invalid"
            ) from error
        return {
            "itemSetCounts": counts,
            "activeDynamicEffects": effects,
        }

    @staticmethod
    def _strict_resolver_replay_projection(value: Any) -> dict[str, Any]:
        """Validate and rebuild the one exact persisted replay projection."""

        def invalid() -> None:
            raise SimulationSnapshotIntegrityError(
                "v2 resolver replay context is invalid"
            )

        def exact_mapping(raw: Any, keys: set[str]) -> dict[str, Any]:
            if type(raw) is not dict or set(raw) != keys:
                invalid()
            return raw

        def identity(raw: Any, *, path: str) -> str:
            if type(raw) is not str:
                invalid()
            try:
                canonical = canonical_identity_token(raw, path=path)
            except CanonicalValueError:
                invalid()
            if canonical != raw:
                invalid()
            return canonical

        def integer(raw: Any, *, path: str) -> int:
            if type(raw) is not int:
                invalid()
            try:
                return canonical_int(raw, path=path, minimum=1, maximum=16)
            except CanonicalValueError:
                invalid()

        try:
            _require_native_v2_json(value, field="v2 resolver replay context")
        except SimulationSnapshotIntegrityError:
            invalid()
        replay = _canonical(value)
        exact_mapping(replay, {
            "schemaRevision",
            "status",
            "dependencyVector",
            "resolvedGearSignature",
            "eligibilityContext",
            "profileReadiness",
            "resolvedSlots",
            "setState",
            "loadoutEffectSubjects",
            "v2EffectBoundary",
        })
        if (
            replay["schemaRevision"]
            != _RESOLVER_REPLAY_CONTEXT_SCHEMA_REVISION
            or replay["status"] != "verified"
            or len(_json(replay).encode("utf-8"))
            > _MAX_RESOLVER_REPLAY_CONTEXT_BYTES
        ):
            invalid()

        dependency = exact_mapping(replay["dependencyVector"], {
            "gearRuleRevision",
            "resolverContractRevision",
            "simcRuntimeRevision",
        })
        safe_dependency = {
            field: identity(
                dependency[field],
                path=f"resolverReplay.dependencyVector.{field}",
            )
            for field in (
                "gearRuleRevision",
                "resolverContractRevision",
                "simcRuntimeRevision",
            )
        }
        resolved_signature = identity(
            replay["resolvedGearSignature"],
            path="resolverReplay.resolvedGearSignature",
        )

        eligibility = exact_mapping(replay["eligibilityContext"], {
            "classKey",
            "specKey",
            "level",
        })
        if type(eligibility["level"]) is not int or eligibility["level"] < 1:
            invalid()
        safe_eligibility = {
            "classKey": identity(
                eligibility["classKey"],
                path="resolverReplay.eligibilityContext.classKey",
            ),
            "specKey": identity(
                eligibility["specKey"],
                path="resolverReplay.eligibilityContext.specKey",
            ),
            "level": eligibility["level"],
        }

        readiness = exact_mapping(replay["profileReadiness"], {
            "status",
            "simcReady",
            "requiredSlots",
            "readySlots",
            "simcRuntimeRevision",
        })
        if (
            readiness["status"] != "verified"
            or readiness["simcReady"] is not True
            or type(readiness["requiredSlots"]) is not list
            or type(readiness["readySlots"]) is not list
            or not readiness["requiredSlots"]
            or len(readiness["requiredSlots"]) > 32
        ):
            invalid()
        required_slots = [
            identity(slot, path=f"resolverReplay.profileReadiness.requiredSlots[{index}]")
            for index, slot in enumerate(readiness["requiredSlots"])
        ]
        ready_slots = [
            identity(slot, path=f"resolverReplay.profileReadiness.readySlots[{index}]")
            for index, slot in enumerate(readiness["readySlots"])
        ]
        if (
            ready_slots != required_slots
            or len(set(required_slots)) != len(required_slots)
        ):
            invalid()
        safe_readiness = {
            "status": "verified",
            "simcReady": True,
            "requiredSlots": required_slots,
            "readySlots": ready_slots,
            "simcRuntimeRevision": identity(
                readiness["simcRuntimeRevision"],
                path="resolverReplay.profileReadiness.simcRuntimeRevision",
            ),
        }

        raw_slots = replay["resolvedSlots"]
        if type(raw_slots) is not dict or set(raw_slots) != set(required_slots):
            invalid()
        safe_slots: dict[str, Any] = {}
        for slot in required_slots:
            raw_slot = exact_mapping(raw_slots[slot], {"slot", "itemId", "legality"})
            legality = exact_mapping(raw_slot["legality"], {"status"})
            if raw_slot["slot"] != slot or legality["status"] != "verified":
                invalid()
            safe_slots[slot] = {
                "slot": slot,
                "itemId": identity(
                    raw_slot["itemId"],
                    path=f"resolverReplay.resolvedSlots.{slot}.itemId",
                ),
                "legality": {"status": "verified"},
            }

        raw_set_state = exact_mapping(replay["setState"], {
            "itemSetCounts",
            "activeDynamicEffects",
        })
        raw_counts = raw_set_state["itemSetCounts"]
        raw_effects = raw_set_state["activeDynamicEffects"]
        if (
            type(raw_counts) is not dict
            or type(raw_effects) is not list
            or len(raw_counts) > 128
            or len(raw_effects) > 128
        ):
            invalid()
        safe_counts: dict[str, int] = {}
        for raw_set_id, raw_count in raw_counts.items():
            set_id = identity(
                raw_set_id,
                path="resolverReplay.setState.itemSetCounts",
            )
            if set_id in _FORBIDDEN_RESOLVER_REPLAY_SEMANTIC_KEYS:
                invalid()
            safe_counts[set_id] = integer(
                raw_count,
                path=f"resolverReplay.setState.itemSetCounts.{set_id}",
            )
        safe_effects: list[dict[str, Any]] = []
        for index, raw_effect in enumerate(raw_effects):
            effect = exact_mapping(raw_effect, {"effectId", "itemSetId", "pieces"})
            safe_effects.append({
                "effectId": identity(
                    effect["effectId"],
                    path=f"resolverReplay.setState.activeDynamicEffects[{index}].effectId",
                ),
                "itemSetId": identity(
                    effect["itemSetId"],
                    path=f"resolverReplay.setState.activeDynamicEffects[{index}].itemSetId",
                ),
                "pieces": integer(
                    effect["pieces"],
                    path=f"resolverReplay.setState.activeDynamicEffects[{index}].pieces",
                ),
            })
        safe_set_state = {
            "itemSetCounts": safe_counts,
            "activeDynamicEffects": safe_effects,
        }

        raw_subjects = replay["loadoutEffectSubjects"]
        if type(raw_subjects) is not list or len(raw_subjects) > 128:
            invalid()
        safe_subjects: list[dict[str, Any]] = []
        for index, raw_subject in enumerate(raw_subjects):
            subject = exact_mapping(
                raw_subject,
                {"subjectKind", "itemSetId", "pieces", "subjectKey"},
            )
            safe_subjects.append({
                "subjectKind": identity(
                    subject["subjectKind"],
                    path=f"resolverReplay.loadoutEffectSubjects[{index}].subjectKind",
                ),
                "itemSetId": identity(
                    subject["itemSetId"],
                    path=f"resolverReplay.loadoutEffectSubjects[{index}].itemSetId",
                ),
                "pieces": integer(
                    subject["pieces"],
                    path=f"resolverReplay.loadoutEffectSubjects[{index}].pieces",
                ),
                "subjectKey": identity(
                    subject["subjectKey"],
                    path=f"resolverReplay.loadoutEffectSubjects[{index}].subjectKey",
                ),
            })
        if len(safe_effects) != len(safe_subjects):
            invalid()

        raw_boundary = replay["v2EffectBoundary"]
        boundary_keys = {
            "schemaRevision",
            "status",
            "resolvedGearSignature",
            "setState",
            "subjects",
            "gearRuleRevision",
            "resolverRevision",
            "simcRuntimeRevision",
        }
        if safe_subjects:
            boundary_keys.add("loadoutEffectAuthorityKey")
        boundary = exact_mapping(raw_boundary, boundary_keys)
        if (
            boundary["schemaRevision"] != "gear-resolver-v2-effect-boundary-v1"
            or boundary["status"] != "verified"
            or boundary["resolvedGearSignature"] != resolved_signature
            or boundary["setState"] != safe_set_state
            or boundary["subjects"] != safe_subjects
            or boundary["gearRuleRevision"]
            != safe_dependency["gearRuleRevision"]
            or boundary["resolverRevision"]
            != safe_dependency["resolverContractRevision"]
            or boundary["simcRuntimeRevision"]
            != safe_dependency["simcRuntimeRevision"]
            or safe_readiness["simcRuntimeRevision"]
            != safe_dependency["simcRuntimeRevision"]
        ):
            invalid()
        safe_boundary = {
            "schemaRevision": "gear-resolver-v2-effect-boundary-v1",
            "status": "verified",
            "resolvedGearSignature": resolved_signature,
            "setState": safe_set_state,
            "subjects": safe_subjects,
            "gearRuleRevision": safe_dependency["gearRuleRevision"],
            "resolverRevision": safe_dependency["resolverContractRevision"],
            "simcRuntimeRevision": safe_dependency["simcRuntimeRevision"],
        }
        if safe_subjects:
            authority_key = boundary["loadoutEffectAuthorityKey"]
            if (
                type(authority_key) is not str
                or not _LOADOUT_EFFECT_AUTHORITY_KEY_PATTERN.fullmatch(authority_key)
            ):
                invalid()
            safe_boundary["loadoutEffectAuthorityKey"] = authority_key

        safe = _canonical({
            "schemaRevision": _RESOLVER_REPLAY_CONTEXT_SCHEMA_REVISION,
            "status": "verified",
            "dependencyVector": safe_dependency,
            "resolvedGearSignature": resolved_signature,
            "eligibilityContext": safe_eligibility,
            "profileReadiness": safe_readiness,
            "resolvedSlots": safe_slots,
            "setState": safe_set_state,
            "loadoutEffectSubjects": safe_subjects,
            "v2EffectBoundary": safe_boundary,
        })
        if replay != safe:
            invalid()
        return safe

    @staticmethod
    def _resolver_replay_projection(value: Any) -> dict[str, Any]:
        """Persist the only resolver facts needed to re-run the typed v2 checks."""
        snapshot = dict(value) if isinstance(value, Mapping) else {}
        dependency = (
            snapshot.get("dependencyVector")
            if isinstance(snapshot.get("dependencyVector"), Mapping)
            else {}
        )
        readiness = (
            snapshot.get("profileReadiness")
            if isinstance(snapshot.get("profileReadiness"), Mapping)
            else {}
        )
        eligibility = (
            snapshot.get("eligibilityContext")
            if isinstance(snapshot.get("eligibilityContext"), Mapping)
            else {}
        )
        required_slots = readiness.get("requiredSlots")
        resolved_slots = (
            snapshot.get("resolvedSlots")
            if isinstance(snapshot.get("resolvedSlots"), Mapping)
            else {}
        )
        slots = {}
        for slot in required_slots if isinstance(required_slots, list) else []:
            resolved = (
                resolved_slots.get(slot)
                if isinstance(resolved_slots.get(slot), Mapping)
                else {}
            )
            legality = (
                resolved.get("legality")
                if isinstance(resolved.get("legality"), Mapping)
                else {}
            )
            slots[slot] = {
                "slot": resolved.get("slot"),
                "itemId": resolved.get("itemId"),
                "legality": {"status": legality.get("status")},
            }
        boundary = (
            snapshot.get("v2EffectBoundary")
            if isinstance(snapshot.get("v2EffectBoundary"), Mapping)
            else {}
        )
        raw_set_state = snapshot.get("setState")
        if boundary.get("setState") != raw_set_state:
            raise SimulationSnapshotIntegrityError(
                "v2 resolver replay context is invalid"
            )
        set_state = SimulationSnapshotStore._resolver_replay_set_state(
            raw_set_state
        )
        replay = {
            "schemaRevision": _RESOLVER_REPLAY_CONTEXT_SCHEMA_REVISION,
            "status": snapshot.get("status"),
            "dependencyVector": {
                "gearRuleRevision": dependency.get("gearRuleRevision"),
                "resolverContractRevision": dependency.get("resolverContractRevision"),
                "simcRuntimeRevision": dependency.get("simcRuntimeRevision"),
            },
            "resolvedGearSignature": snapshot.get("resolvedGearSignature"),
            "eligibilityContext": {
                "classKey": eligibility.get("classKey"),
                "specKey": eligibility.get("specKey"),
                "level": eligibility.get("level"),
            },
            "profileReadiness": {
                "status": readiness.get("status"),
                "simcReady": readiness.get("simcReady"),
                "requiredSlots": required_slots,
                "readySlots": readiness.get("readySlots"),
                "simcRuntimeRevision": readiness.get("simcRuntimeRevision"),
            },
            "resolvedSlots": slots,
            "setState": set_state,
            "loadoutEffectSubjects": snapshot.get("loadoutEffectSubjects"),
            "v2EffectBoundary": {
                key: boundary.get(key)
                for key in (
                    "schemaRevision",
                    "status",
                    "resolvedGearSignature",
                    "subjects",
                    "gearRuleRevision",
                    "resolverRevision",
                    "simcRuntimeRevision",
                    "loadoutEffectAuthorityKey",
                )
                if key in boundary
            },
        }
        replay["v2EffectBoundary"]["setState"] = set_state
        return SimulationSnapshotStore._strict_resolver_replay_projection(replay)

    @staticmethod
    def _stored_resolver_replay_context(value: Any) -> dict[str, Any]:
        try:
            replay = _json_value(value)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise SimulationSnapshotIntegrityError(
                "stored v2 resolver replay context is invalid"
            ) from error
        try:
            return SimulationSnapshotStore._strict_resolver_replay_projection(replay)
        except SimulationSnapshotIntegrityError as error:
            raise SimulationSnapshotIntegrityError(
                "stored v2 resolver replay context is invalid"
            ) from error

    @staticmethod
    def _blocked_authority_replay_context(replay: Mapping[str, Any]) -> dict[str, Any]:
        """Adapt the saved verified projection only for Task 4L owner reload."""
        blocked = _canonical(replay)
        boundary = blocked.get("v2EffectBoundary")
        if type(blocked) is not dict or type(boundary) is not dict:
            raise SimulationSnapshotIntegrityError(
                "stored v2 resolver replay context is invalid"
            )
        blocked["status"] = "blocked"
        boundary["status"] = "blocked"
        boundary.pop("loadoutEffectAuthorityKey", None)
        return blocked

    def _reload_exact_authority_bundles(
        self,
        row: Mapping[str, Any],
    ) -> dict[str, Any]:
        pairs = row.get("exactAuthorityBySlot")
        if not isinstance(pairs, list):
            raise SimulationSnapshotIntegrityError("v2 Exact Authority pairs are invalid")
        store = GearExactAuthorityStore(self._connection_factory)
        bundles: dict[str, Any] = {}
        try:
            for pair in pairs:
                key = pair.get("exactAuthorityEnvelopeKey") if isinstance(pair, Mapping) else None
                bundle = store.load_verified_bundle(
                    key,
                    gear_rule_revision=row.get("gearRuleRevision"),
                    simc_runtime_revision=row.get("simcRuntimeRevision"),
                    resolver_revision=row.get("resolverRevision"),
                )
                if bundle.envelope.content_key != key or key in bundles:
                    raise SimulationSnapshotIntegrityError(
                        "v2 Exact Authority Bundle relation is invalid"
                    )
                bundles[key] = bundle
        except (GearExactAuthorityStoreIntegrityError, TypeError, ValueError) as error:
            raise SimulationSnapshotIntegrityError(
                "v2 Exact Authority Bundle typed reload failed"
            ) from error
        return bundles

    @staticmethod
    def _load_effect_record_with_cursor(
        cur: Any,
        key: str,
        *,
        simc_runtime_revision: str,
    ) -> Any:
        cur.execute(
            """
            /* simulation_snapshot_effect_record_load */
            SELECT
                content_key,
                document_kind,
                schema_revision,
                canonical_bytes,
                canonical_sha256 = pg_catalog.encode(
                    pg_catalog.sha256(canonical_bytes), 'hex'
                ) AND canonical_json = pg_catalog.convert_from(
                    canonical_bytes, 'UTF8'
                )::jsonb AS projection_valid
            FROM cache.websim_canonical_documents
            WHERE content_key = %s
            """,
            (key,),
        )
        stored = cur.fetchone()
        if (
            not stored
            or len(stored) != 5
            or stored[0] != key
            or stored[1:3] != ("effect_record", "simc-item-effect-record-v1")
            or stored[4] is not True
        ):
            raise SimulationSnapshotIntegrityError(
                "loadout effect authority record is unavailable"
            )
        try:
            return reload_effect_record(
                bytes(stored[3]), stored[0],
                runtime_revision=simc_runtime_revision,
            )
        except (TypeError, ValueError) as error:
            raise SimulationSnapshotIntegrityError(
                "loadout effect authority record typed reload failed"
            ) from error

    def _load_loadout_effect_authority_with_cursor(
        self,
        cur: Any,
        key: str,
        *,
        replay: Mapping[str, Any],
        simc_runtime_revision: str,
    ) -> Any:
        if not _LOADOUT_EFFECT_AUTHORITY_KEY_PATTERN.fullmatch(_text(key)):
            raise SimulationSnapshotIntegrityError("loadout effect authority key is invalid")
        cur.execute(
            """
            /* simulation_snapshot_loadout_effect_authority_document_load */
            SELECT
                loadout_effect_authority_key,
                schema_revision,
                canonical_bytes,
                canonical_sha256 = pg_catalog.encode(
                    pg_catalog.sha256(canonical_bytes), 'hex'
                ) AND canonical_json = pg_catalog.convert_from(
                    canonical_bytes, 'UTF8'
                )::jsonb AS projection_valid
            FROM cache.websim_loadout_effect_authorities
            WHERE loadout_effect_authority_key = %s
            """,
            (key,),
        )
        stored = cur.fetchone()
        if (
            not stored
            or len(stored) != 4
            or stored[0] != key
            or stored[1] != "loadout-effect-authority-v1"
            or stored[3] is not True
        ):
            raise SimulationSnapshotIntegrityError(
                "loadout effect authority is unavailable"
            )
        try:
            authority = reload_loadout_effect_authority(
                bytes(stored[2]), stored[0],
                resolver_snapshot=self._blocked_authority_replay_context(replay),
            )
            payload = json.loads(authority.canonical_bytes)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise SimulationSnapshotIntegrityError(
                "loadout effect authority typed reload failed"
            ) from error
        cur.execute(
            """
            /* simulation_snapshot_loadout_effect_authority_relation_load */
            SELECT ordinal, effect_record_key
            FROM cache.websim_loadout_effect_authority_records
            WHERE loadout_effect_authority_key = %s
            ORDER BY ordinal
            """,
            (key,),
        )
        relations = tuple(cur.fetchall())
        records = payload.get("supportRecords") if isinstance(payload, Mapping) else None
        if not isinstance(records, list) or len(relations) != len(records):
            raise SimulationSnapshotIntegrityError(
                "loadout effect authority relation cardinality mismatch"
            )
        for ordinal, (relation, expected) in enumerate(zip(relations, records, strict=True)):
            if (
                type(relation) not in {tuple, list}
                or len(relation) != 2
                or relation[0] != ordinal
                or not isinstance(expected, Mapping)
                or relation[1] != expected.get("supportRecordKey")
            ):
                raise SimulationSnapshotIntegrityError(
                    "loadout effect authority relation order mismatch"
                )
            record = self._load_effect_record_with_cursor(
                cur,
                relation[1],
                simc_runtime_revision=simc_runtime_revision,
            )
            expected_payload = dict(expected)
            expected_payload.pop("supportRecordKey", None)
            if json.loads(record.canonical_bytes) != expected_payload:
                raise SimulationSnapshotIntegrityError(
                    "loadout effect authority relation record mismatch"
                )
        return authority

    def _seal_loadout_effect_authority_with_cursor(
        self,
        cur: Any,
        authority: Any,
        *,
        replay: Mapping[str, Any],
        simc_runtime_revision: str,
    ) -> Any:
        if authority is None:
            return None
        key = getattr(authority, "content_key", None)
        canonical_bytes = getattr(authority, "canonical_bytes", None)
        schema_revision = getattr(authority, "schema_revision", None)
        if (
            not _LOADOUT_EFFECT_AUTHORITY_KEY_PATTERN.fullmatch(_text(key))
            or schema_revision != "loadout-effect-authority-v1"
            or type(canonical_bytes) is not bytes
        ):
            raise SimulationSnapshotIntegrityError("loadout effect authority is invalid")
        try:
            verified = reload_loadout_effect_authority(
                canonical_bytes,
                key,
                resolver_snapshot=self._blocked_authority_replay_context(replay),
            )
            payload = json.loads(verified.canonical_bytes)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise SimulationSnapshotIntegrityError(
                "loadout effect authority typed reload failed"
            ) from error
        records = payload.get("supportRecords") if isinstance(payload, Mapping) else None
        if not isinstance(records, list):
            raise SimulationSnapshotIntegrityError("loadout effect authority records are invalid")
        for ordinal, record in enumerate(records):
            record_key = record.get("supportRecordKey") if isinstance(record, Mapping) else None
            reloaded = self._load_effect_record_with_cursor(
                cur,
                record_key,
                simc_runtime_revision=simc_runtime_revision,
            )
            expected_payload = dict(record)
            expected_payload.pop("supportRecordKey", None)
            if json.loads(reloaded.canonical_bytes) != expected_payload:
                raise SimulationSnapshotIntegrityError(
                    "loadout effect authority record mismatch"
                )
            cur.execute(
                """
                /* simulation_snapshot_loadout_effect_authority_relation_insert */
                INSERT INTO cache.websim_loadout_effect_authority_records (
                    loadout_effect_authority_key, ordinal, effect_record_key
                ) VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (key, ordinal, record_key),
            )
        cur.execute(
            """
            /* simulation_snapshot_loadout_effect_authority_parent_insert */
            INSERT INTO cache.websim_loadout_effect_authorities (
                loadout_effect_authority_key,
                schema_revision,
                canonical_bytes,
                canonical_json,
                canonical_sha256
            ) VALUES (
                %s,
                %s,
                %s,
                pg_catalog.convert_from(%s, 'UTF8')::jsonb,
                pg_catalog.encode(pg_catalog.sha256(%s), 'hex')
            )
            ON CONFLICT DO NOTHING
            """,
            (key, schema_revision, canonical_bytes, canonical_bytes, canonical_bytes),
        )
        return self._load_loadout_effect_authority_with_cursor(
            cur,
            key,
            replay=replay,
            simc_runtime_revision=simc_runtime_revision,
        )

    def _rehydrate_v2_loadout_with_cursor(
        self,
        cur: Any,
        key: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Any]:
        cur.execute(
            """
            /* simulation_snapshot_loadout_v2_load */
            SELECT
                resolved_loadout_key,
                schema_revision,
                catalog_revision,
                gear_rule_revision,
                exact_registry_revision,
                class_key,
                spec_key,
                loadout_json::text,
                row_hash,
                exact_authority_by_slot_json::text,
                effect_evidence_by_occurrence_json::text,
                loadout_effect_authority_key,
                resolver_replay_context_json::text
            FROM cache.websim_gear_resolved_loadouts
            WHERE resolved_loadout_key = %s
            """,
            (key,),
        )
        stored = cur.fetchone()
        if not stored:
            return {}, {}, {}, None
        row = _json_value(stored[7])
        replay = self._stored_resolver_replay_context(stored[12])
        bundles = self._reload_exact_authority_bundles(row)
        authority = None
        if stored[11] is not None:
            authority = self._load_loadout_effect_authority_with_cursor(
                cur,
                stored[11],
                replay=replay,
                simc_runtime_revision=row.get("simcRuntimeRevision"),
            )
        if (
            not _LOADOUT_V2_KEY_PATTERN.fullmatch(_text(stored[0]))
            or row.get("schemaRevision") != RESOLVED_LOADOUT_V2_SCHEMA_REVISION
            or row.get("resolvedLoadoutKey") != stored[0]
            or _text(row.get("originCatalogRevision")) != _text(stored[2])
            or _text(row.get("gearRuleRevision")) != _text(stored[3])
            or stored[4] is not None
            or _text(row.get("eligibilityContext", {}).get("classKey")) != _text(stored[5])
            or _text(row.get("eligibilityContext", {}).get("specKey")) != _text(stored[6])
            or row.get("rowHash") != stored[8]
            or row.get("exactAuthorityBySlot") != _json_value(stored[9])
            or row.get("effectEvidenceByOccurrence") != _json_value(stored[10])
            or row.get("loadoutEffectAuthorityKey") != stored[11]
            or verify_resolved_loadout_v2(
                row,
                resolver_snapshot=replay,
                authority_bundles=bundles,
                loadout_effect_authority=authority,
            )
        ):
            raise SimulationSnapshotIntegrityError(
                "sealed v2 ResolvedLoadout integrity mismatch"
            )
        return row, replay, bundles, authority

    def _load_v2_loadout_with_cursor(self, cur: Any, key: str) -> dict[str, Any]:
        return self._rehydrate_v2_loadout_with_cursor(cur, key)[0]

    def _load_v2_snapshot_with_cursor(self, cur: Any, key: str) -> dict[str, Any]:
        cur.execute(
            """
            /* simulation_snapshot_v2_load */
            SELECT
                simulation_snapshot_key,
                schema_revision,
                resolved_loadout_key,
                talent_profile_key,
                compiler_revision,
                simc_runtime_revision,
                canonical_input_hash,
                catalog_revision,
                gear_rule_revision,
                snapshot_json::text,
                row_hash,
                exact_authority_by_slot_json::text,
                effect_evidence_by_occurrence_json::text,
                loadout_effect_authority_key
            FROM cache.websim_simulation_snapshots
            WHERE simulation_snapshot_key = %s
            """,
            (key,),
        )
        stored = cur.fetchone()
        if not stored:
            return {}
        row = _json_value(stored[9])
        loadout, replay, bundles, authority = self._rehydrate_v2_loadout_with_cursor(
            cur, stored[2]
        )
        if (
            not _SNAPSHOT_V2_KEY_PATTERN.fullmatch(_text(stored[0]))
            or row.get("schemaRevision") != SIMULATION_SNAPSHOT_V2_SCHEMA_REVISION
            or row.get("simulationSnapshotKey") != stored[0]
            or row.get("resolvedLoadoutKey") != stored[2]
            or _text(row.get("talentProfileKey")) != _text(stored[3])
            or _text(row.get("compilerRevision")) != _text(stored[4])
            or _text(row.get("simcRuntimeRevision")) != _text(stored[5])
            or _text(row.get("canonicalInputHash")) != _text(stored[6])
            or _text(row.get("originCatalogRevision")) != _text(stored[7])
            or stored[8] is not None
            or row.get("rowHash") != stored[10]
            or row.get("exactAuthorityBySlot") != _json_value(stored[11])
            or row.get("effectEvidenceByOccurrence") != _json_value(stored[12])
            or row.get("loadoutEffectAuthorityKey") != stored[13]
            or verify_simulation_snapshot_v2(
                row,
                resolved_loadout=loadout,
                resolver_snapshot=replay,
                authority_bundles=bundles,
                compiler_revision=row.get("compilerRevision"),
                loadout_effect_authority=authority,
            )
        ):
            raise SimulationSnapshotIntegrityError(
                "sealed v2 SimulationSnapshot integrity mismatch"
            )
        return row

    @staticmethod
    def _load_result_with_cursor(cur: Any, key: str) -> dict[str, Any]:
        cur.execute(
            """
            /* simulation_snapshot_result_load */
            SELECT
                simulation_snapshot_key,
                result_identity,
                result_status,
                result_json::text,
                row_hash
            FROM cache.websim_simulation_snapshot_results
            WHERE simulation_snapshot_key = %s
            """,
            (key,),
        )
        stored = cur.fetchone()
        if not stored:
            return {}
        result = _json_value(stored[3])
        semantics = {
            "simulationSnapshotKey": _text(stored[0]),
            "resultIdentity": _text(stored[1]),
            "status": _text(stored[2]),
            "result": result,
        }
        if (
            _text(result.get("resultIdentity")) != semantics["resultIdentity"]
            or _text(result.get("status")) != semantics["status"]
            or _row_hash(semantics) != _text(stored[4])
        ):
            raise SimulationSnapshotIntegrityError(
                "sealed simulation result integrity mismatch"
            )
        return semantics

    def load_loadout(self, key: str) -> dict[str, Any]:
        with self.connection() as connection:
            with connection.cursor() as cur:
                normalized_key = _text(key)
                if _LOADOUT_V2_KEY_PATTERN.fullmatch(normalized_key):
                    return self._load_v2_loadout_with_cursor(cur, normalized_key)
                return self._load_loadout_with_cursor(cur, normalized_key)

    def load_snapshot(self, key: str, *, include_result: bool = True) -> dict[str, Any]:
        with self.connection() as connection:
            with connection.cursor() as cur:
                normalized_key = _text(key)
                if _SNAPSHOT_V2_KEY_PATTERN.fullmatch(normalized_key):
                    row = self._load_v2_snapshot_with_cursor(cur, normalized_key)
                else:
                    row = self._load_snapshot_with_cursor(cur, normalized_key)
                if not row or not include_result:
                    return row
                result = self._load_result_with_cursor(cur, _text(key))
                if not result:
                    return row
                return {
                    **row,
                    "status": "executed",
                    "snapshotRowHash": row["rowHash"],
                    "resultIdentity": result["resultIdentity"],
                    "result": result["result"],
                }

    def seal_loadout(
        self,
        value: Any,
        *,
        resolver_snapshot: Any = None,
        authority_bundles: Any = None,
        loadout_effect_authority: Any = None,
    ) -> dict[str, Any]:
        row = self._validate_loadout(
            value,
            resolver_snapshot=resolver_snapshot,
            authority_bundles=authority_bundles,
            loadout_effect_authority=loadout_effect_authority,
        )
        if row.get("schemaRevision") == RESOLVED_LOADOUT_V2_SCHEMA_REVISION:
            return self._seal_loadout_v2(
                row, resolver_snapshot=resolver_snapshot,
                authority_bundles=authority_bundles,
                loadout_effect_authority=loadout_effect_authority,
            )
        eligibility = row["eligibilityContext"]
        params = (
            row["resolvedLoadoutKey"],
            row["schemaRevision"],
            row["catalogRevision"],
            row["gearRuleRevision"],
            row["exactRegistryRevision"],
            _text(eligibility.get("classKey")),
            _text(eligibility.get("specKey")),
            _json(row),
            row["rowHash"],
        )
        with self.connection() as connection:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    /* simulation_snapshot_loadout_insert */
                    INSERT INTO cache.websim_gear_resolved_loadouts (
                        resolved_loadout_key,
                        schema_revision,
                        catalog_revision,
                        gear_rule_revision,
                        exact_registry_revision,
                        class_key,
                        spec_key,
                        loadout_json,
                        row_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    params,
                )
                sealed = self._load_loadout_with_cursor(
                    cur, row["resolvedLoadoutKey"]
                )
                if sealed != row:
                    raise SimulationSnapshotIntegrityError(
                        "sealed ResolvedLoadout identity conflict"
                    )
                return sealed

    def _seal_loadout_v2(
        self,
        row: dict[str, Any],
        *,
        resolver_snapshot: Any,
        authority_bundles: Any,
        loadout_effect_authority: Any,
    ) -> dict[str, Any]:
        replay = self._resolver_replay_projection(resolver_snapshot)
        eligibility = row["eligibilityContext"]
        with self.connection() as connection:
            with connection.cursor() as cur:
                reloaded_bundles = self._reload_exact_authority_bundles(row)
                authority = self._seal_loadout_effect_authority_with_cursor(
                    cur,
                    loadout_effect_authority,
                    replay=replay,
                    simc_runtime_revision=row["simcRuntimeRevision"],
                )
                if verify_resolved_loadout_v2(
                    row,
                    resolver_snapshot=replay,
                    authority_bundles=reloaded_bundles,
                    loadout_effect_authority=authority,
                ):
                    raise SimulationSnapshotIntegrityError(
                        "v2 ResolvedLoadout typed replay verification failed"
                    )
                params = (
                    row["resolvedLoadoutKey"],
                    row["schemaRevision"],
                    row.get("originCatalogRevision"),
                    row["gearRuleRevision"],
                    None,
                    _text(eligibility.get("classKey")),
                    _text(eligibility.get("specKey")),
                    _json(row),
                    row["rowHash"],
                    _json(row["exactAuthorityBySlot"]),
                    _json(row["effectEvidenceByOccurrence"]),
                    row.get("loadoutEffectAuthorityKey"),
                    _json(replay),
                )
                cur.execute(
                    """
                    /* simulation_snapshot_loadout_v2_insert */
                    INSERT INTO cache.websim_gear_resolved_loadouts (
                        resolved_loadout_key,
                        schema_revision,
                        catalog_revision,
                        gear_rule_revision,
                        exact_registry_revision,
                        class_key,
                        spec_key,
                        loadout_json,
                        row_hash,
                        exact_authority_by_slot_json,
                        effect_evidence_by_occurrence_json,
                        loadout_effect_authority_key,
                        resolver_replay_context_json
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s,
                        %s::jsonb, %s::jsonb, %s, %s::jsonb
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    params,
                )
                sealed = self._load_v2_loadout_with_cursor(
                    cur, row["resolvedLoadoutKey"]
                )
                if sealed != row:
                    raise SimulationSnapshotIntegrityError(
                        "sealed v2 ResolvedLoadout identity conflict"
                    )
                return sealed

    def seal_snapshot(
        self,
        value: Any,
        *,
        resolved_loadout: Any = None,
        resolver_snapshot: Any = None,
        authority_bundles: Any = None,
        compiler_revision: Any = None,
        loadout_effect_authority: Any = None,
    ) -> dict[str, Any]:
        row = self._validate_snapshot(
            value,
            resolved_loadout=resolved_loadout,
            resolver_snapshot=resolver_snapshot,
            authority_bundles=authority_bundles,
            compiler_revision=compiler_revision,
            loadout_effect_authority=loadout_effect_authority,
        )
        if row.get("schemaRevision") == SIMULATION_SNAPSHOT_V2_SCHEMA_REVISION:
            return self._seal_snapshot_v2(row, resolved_loadout=resolved_loadout,
                resolver_snapshot=resolver_snapshot, authority_bundles=authority_bundles,
                compiler_revision=compiler_revision, loadout_effect_authority=loadout_effect_authority)
        params = (
            row["simulationSnapshotKey"],
            row["schemaRevision"],
            row["resolvedLoadoutKey"],
            row["talentProfileKey"],
            row["compilerRevision"],
            row["simcRuntimeRevision"],
            row["canonicalInputHash"],
            row["catalogRevision"],
            row["gearRuleRevision"],
            _json(row),
            row["rowHash"],
        )
        with self.connection() as connection:
            with connection.cursor() as cur:
                if not self._load_loadout_with_cursor(
                    cur, row["resolvedLoadoutKey"]
                ):
                    raise SimulationSnapshotIntegrityError(
                        "sealed ResolvedLoadout is required before snapshot"
                    )
                cur.execute(
                    """
                    /* simulation_snapshot_insert */
                    INSERT INTO cache.websim_simulation_snapshots (
                        simulation_snapshot_key,
                        schema_revision,
                        resolved_loadout_key,
                        talent_profile_key,
                        compiler_revision,
                        simc_runtime_revision,
                        canonical_input_hash,
                        catalog_revision,
                        gear_rule_revision,
                        snapshot_json,
                        row_hash
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    params,
                )
                sealed = self._load_snapshot_with_cursor(
                    cur, row["simulationSnapshotKey"]
                )
                if sealed != row:
                    raise SimulationSnapshotIntegrityError(
                        "sealed simulation snapshot identity conflict"
                    )
                return sealed

    def _seal_snapshot_v2(
        self,
        row: dict[str, Any],
        *,
        resolved_loadout: Any,
        resolver_snapshot: Any,
        authority_bundles: Any,
        compiler_revision: Any,
        loadout_effect_authority: Any,
    ) -> dict[str, Any]:
        with self.connection() as connection:
            with connection.cursor() as cur:
                loadout, replay, bundles, authority = (
                    self._rehydrate_v2_loadout_with_cursor(
                        cur, row["resolvedLoadoutKey"]
                    )
                )
                if not loadout:
                    raise SimulationSnapshotIntegrityError(
                        "sealed ResolvedLoadout is required before snapshot"
                    )
                if verify_simulation_snapshot_v2(
                    row,
                    resolved_loadout=loadout,
                    resolver_snapshot=replay,
                    authority_bundles=bundles,
                    compiler_revision=row["compilerRevision"],
                    loadout_effect_authority=authority,
                ):
                    raise SimulationSnapshotIntegrityError(
                        "v2 SimulationSnapshot typed replay verification failed"
                    )
                params = (
                    row["simulationSnapshotKey"],
                    row["schemaRevision"],
                    row["resolvedLoadoutKey"],
                    row["talentProfileKey"],
                    row["compilerRevision"],
                    row["simcRuntimeRevision"],
                    row["canonicalInputHash"],
                    row.get("originCatalogRevision"),
                    None,
                    _json(row),
                    row["rowHash"],
                    _json(row["exactAuthorityBySlot"]),
                    _json(row["effectEvidenceByOccurrence"]),
                    row.get("loadoutEffectAuthorityKey"),
                )
                cur.execute(
                    """
                    /* simulation_snapshot_v2_insert */
                    INSERT INTO cache.websim_simulation_snapshots (
                        simulation_snapshot_key,
                        schema_revision,
                        resolved_loadout_key,
                        talent_profile_key,
                        compiler_revision,
                        simc_runtime_revision,
                        canonical_input_hash,
                        catalog_revision,
                        gear_rule_revision,
                        snapshot_json,
                        row_hash,
                        exact_authority_by_slot_json,
                        effect_evidence_by_occurrence_json,
                        loadout_effect_authority_key
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
                        %s, %s::jsonb, %s::jsonb, %s
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    params,
                )
                sealed = self._load_v2_snapshot_with_cursor(
                    cur, row["simulationSnapshotKey"]
                )
                if sealed != row:
                    raise SimulationSnapshotIntegrityError(
                        "sealed v2 SimulationSnapshot identity conflict"
                    )
                return sealed

    def bind_result(self, snapshot_key: str, result_value: Any) -> dict[str, Any]:
        key = _text(snapshot_key)
        result = _canonical(result_value) if isinstance(result_value, Mapping) else {}
        result_identity = _text(result.get("resultIdentity"))
        status = _text(result.get("status"))
        if (
            not RESULT_IDENTITY_PATTERN.fullmatch(result_identity)
            or status not in {"completed", "failed"}
        ):
            raise SimulationSnapshotIntegrityError(
                "terminal content-addressed SimC result is required"
            )
        semantics = {
            "simulationSnapshotKey": key,
            "resultIdentity": result_identity,
            "status": status,
            "result": result,
        }
        params = (
            key,
            result_identity,
            status,
            _json(result),
            _row_hash(semantics),
        )
        with self.connection() as connection:
            with connection.cursor() as cur:
                if _SNAPSHOT_V2_KEY_PATTERN.fullmatch(key):
                    snapshot = self._load_v2_snapshot_with_cursor(cur, key)
                else:
                    snapshot = self._load_snapshot_with_cursor(cur, key)
                if not snapshot:
                    raise SimulationSnapshotIntegrityError(
                        "sealed simulation snapshot is required before result"
                    )
                cur.execute(
                    """
                    /* simulation_snapshot_result_insert */
                    INSERT INTO cache.websim_simulation_snapshot_results (
                        simulation_snapshot_key,
                        result_identity,
                        result_status,
                        result_json,
                        row_hash
                    ) VALUES (%s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    params,
                )
                sealed = self._load_result_with_cursor(cur, key)
                if sealed != semantics:
                    raise SimulationSnapshotIntegrityError(
                        "result binding conflict"
                    )
                return {
                    **snapshot,
                    "status": "executed",
                    "snapshotRowHash": snapshot["rowHash"],
                    "resultIdentity": result_identity,
                    "result": result,
                }


__all__ = (
    "SimulationSnapshotIntegrityError",
    "SimulationSnapshotStore",
)

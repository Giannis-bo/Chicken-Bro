import copy
import unittest

import server.simulation_snapshot as simulation_snapshot_module

from server.simulation_snapshot import (
    build_simulation_snapshot,
    build_simulation_snapshot_v2,
    talent_profile_key,
    verify_simulation_snapshot_v2,
)
from tests.gear_resolved_loadout_test import (
    TEMPLATE_HASH,
    exact_registry,
    resolver_snapshot,
    v2_resolver_snapshot,
)
from server.gear_resolved_loadout import build_resolved_loadout, build_resolved_loadout_v2
from tests.gear_resolved_loadout_test import v2_bundle


TALENT_LINES = ["talents=CYQAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"]
TALENT_KEY = talent_profile_key(TALENT_LINES)


def ready_loadout(class_key="mage", spec_key="arcane"):
    snapshot = resolver_snapshot()
    snapshot["eligibilityContext"]["classKey"] = class_key
    snapshot["eligibilityContext"]["specKey"] = spec_key
    return build_resolved_loadout(
        resolver_snapshot=snapshot,
        exact_registry=exact_registry(),
        template_scope="community",
        template_content_hash=TEMPLATE_HASH,
    )


def character_context(class_key="mage", spec_key="arcane"):
    return {
        "classKey": class_key,
        "specKey": spec_key,
        "name": "确定性 测试",
        "race": "troll",
        "level": 90,
        "role": "spell",
        "position": "back",
    }


def scenario():
    return {
        "scenarioKey": "single",
        "fightStyle": "Patchwerk",
        "desiredTargets": 1,
        "maxTime": 300,
        "iterations": 1000,
        "varyCombatLength": "0.2",
        "calculateScaleFactors": 0,
    }


def v2_snapshot_fixture():
    source = v2_resolver_snapshot()
    source["resolvedSlots"] = {
        "head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}},
    }
    source["profileReadiness"] = {
        "status": "verified",
        "simcReady": True,
        "requiredSlots": ["head"],
        "readySlots": ["head"],
        "simcRuntimeRevision": "simc-runtime-v2",
    }
    bundle = v2_bundle("head", "1001", ["A"])
    key = bundle.envelope.content_key
    bundles = {key: bundle}
    loadout = build_resolved_loadout_v2(
        resolver_snapshot=source,
        exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
        authority_bundles=bundles,
        gear_rule_revision="gear-rule-matrix-v1",
        resolver_revision="resolver-v2",
        simc_runtime_revision="simc-runtime-v2",
    )
    snapshot = build_simulation_snapshot_v2(
        resolved_loadout=loadout,
        talent_profile_key=TALENT_KEY,
        talent_lines=TALENT_LINES,
        character_context=character_context(),
        scenario_options=scenario(),
        preparation_lines=["optimal_raid=0"],
        compiler_revision="simc-profile-compiler-v2",
        simc_runtime_revision="simc-runtime-v2",
        resolver_snapshot=source,
        authority_bundles=bundles,
    )
    return source, bundles, loadout, snapshot


def rehash_v2_snapshot(snapshot):
    character = snapshot.get("characterContext") if isinstance(snapshot.get("characterContext"), dict) else {}
    scenario_options = snapshot.get("scenarioOptions") if isinstance(snapshot.get("scenarioOptions"), dict) else {}
    identity = {
        "resolvedLoadoutKey": snapshot["resolvedLoadoutKey"],
        "exactAuthorityBySlot": simulation_snapshot_module._canonical(snapshot["exactAuthorityBySlot"] or []),
        "effectEvidenceByOccurrence": simulation_snapshot_module._canonical(snapshot["effectEvidenceByOccurrence"] or []),
        "talentProfileKey": snapshot["talentProfileKey"],
        "characterContext": {**simulation_snapshot_module._canonical(character), "talentLinesHash": snapshot["talentLinesHash"]},
        "scenarioOptions": {**simulation_snapshot_module._canonical(scenario_options), "preparationLines": simulation_snapshot_module._canonical(snapshot["preparationLines"] or [])},
        "serializerInput": simulation_snapshot_module._canonical(snapshot["serializerInput"] or {}),
        "compilerRevision": str(snapshot.get("compilerRevision") or "").strip(),
        "simcRuntimeRevision": str(snapshot.get("simcRuntimeRevision") or "").strip(),
    }
    snapshot["simulationSnapshotKey"] = simulation_snapshot_module._hash("simulation-snapshot-v2:sha256:", identity)
    snapshot["rowHash"] = simulation_snapshot_module._hash("sha256:", {key: value for key, value in snapshot.items() if key not in {"rowHash", "originCatalogRevision"}})


class SimulationSnapshotTest(unittest.TestCase):
    def build(self, **overrides):
        values = {
            "resolved_loadout": ready_loadout(),
            "talent_profile_key": TALENT_KEY,
            "talent_lines": TALENT_LINES,
            "character_context": character_context(),
            "scenario_options": scenario(),
            "preparation_lines": ["optimal_raid=0", "override.arcane_intellect=1"],
            "compiler_revision": "simc-profile-compiler-v1",
            "simc_runtime_revision": "simc-runtime-v1",
        }
        values.update(overrides)
        return build_simulation_snapshot(**values)

    def test_snapshot_and_profile_bytes_are_deterministic(self):
        first = self.build()
        second = self.build(
            character_context={
                "position": "back",
                "role": "spell",
                "level": 90,
                "race": "troll",
                "name": "确定性 测试",
                "specKey": "arcane",
                "classKey": "mage",
            },
            scenario_options={
                "maxTime": 300,
                "iterations": 1000,
                "fightStyle": "Patchwerk",
                "desiredTargets": 1,
                "scenarioKey": "single",
                "calculateScaleFactors": 0,
                "varyCombatLength": "0.2",
            },
        )

        self.assertEqual(first["status"], "ready")
        self.assertEqual(first, second)
        self.assertRegex(
            first["simulationSnapshotKey"],
            r"^simulation-snapshot:sha256:[0-9a-f]{64}$",
        )
        self.assertRegex(first["canonicalInputHash"], r"^simc-input:sha256:[0-9a-f]{64}$")
        self.assertTrue(first["canonicalSimcInput"].endswith("\n"))
        self.assertNotIn("\r", first["canonicalSimcInput"])
        self.assertEqual(
            first["canonicalSimcInput"].splitlines()[:8],
            [
                'mage="test"',
                "spec=arcane",
                "level=90",
                "race=troll",
                "role=spell",
                "position=back",
                "talents=CYQAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "head=item_1001,id=1001,ilevel=266,bonus_id=9001/9002",
            ],
        )
        self.assertIn(
            "main_hand=item_1002,id=1002,ilevel=272,bonus_id=9010,enchant_id=7443",
            first["canonicalSimcInput"],
        )

    def test_identity_changes_for_talent_scenario_compiler_or_runtime(self):
        baseline = self.build()
        mutations = [
            {
                "talent_profile_key": talent_profile_key(
                    ["talents=DIFFERENT"]
                ),
                "talent_lines": ["talents=DIFFERENT"],
            },
            {"scenario_options": {**scenario(), "desiredTargets": 5}},
            {"compiler_revision": "simc-profile-compiler-v2"},
            {"simc_runtime_revision": "simc-runtime-v2"},
        ]

        keys = {
            self.build(**mutation).get("simulationSnapshotKey")
            for mutation in mutations
        }

        self.assertNotIn(baseline["simulationSnapshotKey"], keys)
        self.assertEqual(len(keys), len(mutations))

    def test_unsupported_and_unknown_specs_block_before_compilation(self):
        unsupported = self.build(
            resolved_loadout=ready_loadout("warrior", "protection"),
            character_context=character_context("warrior", "protection"),
        )
        unknown = self.build(
            resolved_loadout=ready_loadout("mage", "unknown"),
            character_context=character_context("mage", "unknown"),
        )

        self.assertEqual(unsupported["status"], "unsupported")
        self.assertEqual(unsupported["problemCodes"], ["SIMC_SPECIALIZATION_UNSUPPORTED"])
        self.assertNotIn("canonicalSimcInput", unsupported)
        self.assertEqual(unknown["status"], "blocked")
        self.assertEqual(unknown["problemCodes"], ["SIMC_SPECIALIZATION_UNKNOWN"])

    def test_non_ready_loadout_and_character_mismatch_fail_closed(self):
        blocked_loadout = copy.deepcopy(ready_loadout())
        blocked_loadout["status"] = "blocked"
        blocked_loadout.pop("resolvedLoadoutKey", None)
        blocked = self.build(resolved_loadout=blocked_loadout)
        mismatch = self.build(
            character_context=character_context("mage", "fire"),
        )

        self.assertIn("SIMULATION_LOADOUT_NOT_READY", blocked["problemCodes"])
        self.assertIn("SIMULATION_CHARACTER_LOADOUT_MISMATCH", mismatch["problemCodes"])

    def test_v2_snapshot_binds_v2_loadout_without_catalog_provenance(self):
        """Would fail if provenance entered the v2 snapshot identity or v1 verifier accepted v2."""
        source = v2_resolver_snapshot()
        source["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        source["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-runtime-v2"}
        bundle = v2_bundle("head", "1001", ["A"])
        key = bundle.envelope.content_key
        loadout = build_resolved_loadout_v2(
            resolver_snapshot=source,
            exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: bundle},
            gear_rule_revision="gear-rule-matrix-v1",
            resolver_revision="resolver-v2",
            simc_runtime_revision="simc-runtime-v2",
            origin_catalog_revision="gear-catalog:sha256:" + "a" * 64,
        )
        snapshot = build_simulation_snapshot_v2(
            resolved_loadout=loadout,
            talent_profile_key=TALENT_KEY,
            talent_lines=TALENT_LINES,
            character_context=character_context(),
            scenario_options=scenario(),
            preparation_lines=["optimal_raid=0"],
            compiler_revision="simc-profile-compiler-v2",
            simc_runtime_revision="simc-runtime-v2",
            resolver_snapshot=source,
            authority_bundles={key: bundle},
            origin_catalog_revision="gear-catalog:sha256:" + "b" * 64,
        )
        self.assertEqual(snapshot["status"], "ready")
        self.assertEqual(verify_simulation_snapshot_v2(snapshot, resolved_loadout=loadout, resolver_snapshot=source, authority_bundles={key: bundle}, compiler_revision="simc-profile-compiler-v2"), [])
        self.assertNotEqual(snapshot["simulationSnapshotKey"], self.build()["simulationSnapshotKey"])

    def test_v2_snapshot_keeps_exact_serializer_facts_for_same_item_id(self):
        """Would fail if two Exact instances with one itemId compiled identically."""
        source = v2_resolver_snapshot()
        source["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        source["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-runtime-v2"}
        def snapshot_for(*bonus_ids):
            bundle = v2_bundle("head", "1001", [], exact_fields={"bonusIds": list(bonus_ids)})
            key = bundle.envelope.content_key
            loadout = build_resolved_loadout_v2(
                resolver_snapshot=source,
                exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
                authority_bundles={key: bundle},
                gear_rule_revision="gear-rule-matrix-v1", resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
            )
            return build_simulation_snapshot_v2(
                resolved_loadout=loadout, talent_profile_key=TALENT_KEY, talent_lines=TALENT_LINES,
                character_context=character_context(), scenario_options=scenario(), preparation_lines=["optimal_raid=0"],
                compiler_revision="simc-profile-compiler-v2", simc_runtime_revision="simc-runtime-v2",
                resolver_snapshot=source,
                authority_bundles={key: bundle},
            )
        first = snapshot_for("13334")
        second = snapshot_for("13334", "13335")
        self.assertEqual(first["status"], "ready")
        self.assertNotEqual(first["canonicalSimcInput"], second["canonicalSimcInput"])
        self.assertIn("bonus_id=13334", first["canonicalSimcInput"])

    def test_v2_snapshot_verifier_rejects_rehashed_canonical_input_tampering(self):
        """Would fail if a recomputed row hash could bless altered SimC bytes."""
        source = v2_resolver_snapshot()
        source["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        source["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-runtime-v2"}
        bundle = v2_bundle("head", "1001", [])
        key = bundle.envelope.content_key
        loadout = build_resolved_loadout_v2(
            resolver_snapshot=source, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: bundle}, gear_rule_revision="gear-rule-matrix-v1",
            resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        snapshot = build_simulation_snapshot_v2(
            resolved_loadout=loadout, talent_profile_key=TALENT_KEY, talent_lines=TALENT_LINES,
            character_context=character_context(), scenario_options=scenario(), preparation_lines=["optimal_raid=0"],
            compiler_revision="simc-profile-compiler-v2", simc_runtime_revision="simc-runtime-v2",
            resolver_snapshot=source,
            authority_bundles={key: bundle},
        )
        snapshot["canonicalSimcInput"] = snapshot["canonicalSimcInput"].replace("bonus_id=13334", "bonus_id=9999")
        snapshot["canonicalInputHash"] = "simc-input:sha256:" + __import__("hashlib").sha256(snapshot["canonicalSimcInput"].encode("utf-8")).hexdigest()
        snapshot["rowHash"] = simulation_snapshot_module._hash("sha256:", {key: value for key, value in snapshot.items() if key not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("SIMULATION_V2_CANONICAL_INPUT_INVALID", verify_simulation_snapshot_v2(snapshot, resolved_loadout=loadout, resolver_snapshot=source, authority_bundles={key: bundle}))

    def test_v2_snapshot_verifier_binds_rehashed_serializer_and_talent_inputs(self):
        """Would fail if a v2 key ignored divergent Exact-derived compiler inputs."""
        source = v2_resolver_snapshot()
        source["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        source["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-runtime-v2"}
        bundle = v2_bundle("head", "1001", [])
        key = bundle.envelope.content_key
        loadout = build_resolved_loadout_v2(
            resolver_snapshot=source, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: bundle}, gear_rule_revision="gear-rule-matrix-v1",
            resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        baseline = build_simulation_snapshot_v2(
            resolved_loadout=loadout, talent_profile_key=TALENT_KEY, talent_lines=TALENT_LINES,
            character_context=character_context(), scenario_options=scenario(), preparation_lines=["optimal_raid=0"],
            compiler_revision="simc-profile-compiler-v2", simc_runtime_revision="simc-runtime-v2",
            resolver_snapshot=source,
            authority_bundles={key: bundle},
        )
        serializer = copy.deepcopy(baseline)
        serializer["serializerInput"]["gearItems"][0]["simcOptions"]["bonus_id"] = "9999"
        serializer["canonicalSimcInput"] = simulation_snapshot_module._v2_canonical_simc_input(
            serializer["characterContext"], serializer["scenarioOptions"], serializer["talentLines"],
            serializer["preparationLines"], serializer["serializerInput"]["gearItems"],
        )
        serializer["canonicalInputHash"] = "simc-input:sha256:" + __import__("hashlib").sha256(serializer["canonicalSimcInput"].encode("utf-8")).hexdigest()
        serializer["rowHash"] = simulation_snapshot_module._hash("sha256:", {key: value for key, value in serializer.items() if key not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("SIMULATION_SNAPSHOT_V2_IDENTITY_MISMATCH", verify_simulation_snapshot_v2(serializer, resolved_loadout=loadout, resolver_snapshot=source, authority_bundles={key: bundle}))

        talents = copy.deepcopy(baseline)
        talents["talentLines"] = ["talents=DIFFERENT"]
        talents["canonicalSimcInput"] = simulation_snapshot_module._v2_canonical_simc_input(
            talents["characterContext"], talents["scenarioOptions"], talents["talentLines"],
            talents["preparationLines"], talents["serializerInput"]["gearItems"],
        )
        talents["canonicalInputHash"] = "simc-input:sha256:" + __import__("hashlib").sha256(talents["canonicalSimcInput"].encode("utf-8")).hexdigest()
        talents["rowHash"] = simulation_snapshot_module._hash("sha256:", {key: value for key, value in talents.items() if key not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("SIMULATION_V2_TALENT_IDENTITY_MISMATCH", verify_simulation_snapshot_v2(talents, resolved_loadout=loadout, resolver_snapshot=source, authority_bundles={key: bundle}))

    def test_v2_snapshot_verifier_rejects_rehashed_non_mapping_authority_pair(self):
        """Would fail if a malformed authority entry were filtered before comparison."""
        source = v2_resolver_snapshot()
        source["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        source["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-runtime-v2"}
        bundle = v2_bundle("head", "1001", [])
        key = bundle.envelope.content_key
        loadout = build_resolved_loadout_v2(
            resolver_snapshot=source, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: bundle}, gear_rule_revision="gear-rule-matrix-v1",
            resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        tampered = build_simulation_snapshot_v2(
            resolved_loadout=loadout, talent_profile_key=TALENT_KEY, talent_lines=TALENT_LINES,
            character_context=character_context(), scenario_options=scenario(), preparation_lines=["optimal_raid=0"],
            compiler_revision="simc-profile-compiler-v2", simc_runtime_revision="simc-runtime-v2",
            resolver_snapshot=source,
            authority_bundles={key: bundle},
        )
        tampered["exactAuthorityBySlot"].append("not-a-pair")
        tampered["rowHash"] = simulation_snapshot_module._hash("sha256:", {key: value for key, value in tampered.items() if key not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("SIMULATION_V2_EXACT_AUTHORITY_INVALID", verify_simulation_snapshot_v2(tampered, resolved_loadout=loadout, resolver_snapshot=source, authority_bundles={key: bundle}))

    def test_v2_snapshot_verifier_rejects_duplicate_effect_and_isolated_serializer_slot(self):
        """Would fail if mutable occurrence or slot rows could outlive loadout binding."""
        source = v2_resolver_snapshot()
        source["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        source["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-runtime-v2"}
        bundle = v2_bundle("head", "1001", ["A"])
        key = bundle.envelope.content_key
        loadout = build_resolved_loadout_v2(
            resolver_snapshot=source, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: bundle}, gear_rule_revision="gear-rule-matrix-v1",
            resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        baseline = build_simulation_snapshot_v2(
            resolved_loadout=loadout, talent_profile_key=TALENT_KEY, talent_lines=TALENT_LINES,
            character_context=character_context(), scenario_options=scenario(), preparation_lines=["optimal_raid=0"],
            compiler_revision="simc-profile-compiler-v2", simc_runtime_revision="simc-runtime-v2",
            resolver_snapshot=source,
            authority_bundles={key: bundle},
        )
        occurrence = copy.deepcopy(baseline)
        occurrence["effectEvidenceByOccurrence"].append(copy.deepcopy(occurrence["effectEvidenceByOccurrence"][0]))
        occurrence["rowHash"] = simulation_snapshot_module._hash("sha256:", {key: value for key, value in occurrence.items() if key not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("SIMULATION_V2_EFFECT_EVIDENCE_INVALID", verify_simulation_snapshot_v2(occurrence, resolved_loadout=loadout, resolver_snapshot=source, authority_bundles={key: bundle}))
        isolated = copy.deepcopy(baseline)
        isolated["serializerInput"]["gearItems"][0]["slot"] = "off_hand"
        isolated["rowHash"] = simulation_snapshot_module._hash("sha256:", {key: value for key, value in isolated.items() if key not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("SIMULATION_V2_SERIALIZER_AUTHORITY_MISMATCH", verify_simulation_snapshot_v2(isolated, resolved_loadout=loadout, resolver_snapshot=source, authority_bundles={key: bundle}))

    def test_v2_snapshot_verifier_rejects_rehashed_nonlist_and_boolean_effect_evidence(self):
        """Would fail if snapshot verification normalized hostile occurrence types."""
        source = v2_resolver_snapshot()
        source["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        source["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-runtime-v2"}
        bundle = v2_bundle("head", "1001", ["A"])
        key = bundle.envelope.content_key
        loadout = build_resolved_loadout_v2(
            resolver_snapshot=source, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: bundle}, gear_rule_revision="gear-rule-matrix-v1",
            resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        baseline = build_simulation_snapshot_v2(
            resolved_loadout=loadout, talent_profile_key=TALENT_KEY, talent_lines=TALENT_LINES,
            character_context=character_context(), scenario_options=scenario(), preparation_lines=["optimal_raid=0"],
            compiler_revision="simc-profile-compiler-v2", simc_runtime_revision="simc-runtime-v2",
            resolver_snapshot=source,
            authority_bundles={key: bundle},
        )

        def rehash(snapshot):
            identity = {
                "resolvedLoadoutKey": snapshot["resolvedLoadoutKey"],
                "exactAuthorityBySlot": simulation_snapshot_module._canonical(snapshot["exactAuthorityBySlot"] or []),
                "effectEvidenceByOccurrence": simulation_snapshot_module._canonical(snapshot["effectEvidenceByOccurrence"] or []),
                "talentProfileKey": snapshot["talentProfileKey"],
                "characterContext": {**simulation_snapshot_module._canonical(snapshot["characterContext"] or {}), "talentLinesHash": snapshot["talentLinesHash"]},
                "scenarioOptions": {**simulation_snapshot_module._canonical(snapshot["scenarioOptions"] or {}), "preparationLines": simulation_snapshot_module._canonical(snapshot["preparationLines"] or [])},
                "serializerInput": simulation_snapshot_module._canonical(snapshot["serializerInput"] or {}),
                "compilerRevision": snapshot["compilerRevision"],
                "simcRuntimeRevision": snapshot["simcRuntimeRevision"],
            }
            snapshot["simulationSnapshotKey"] = simulation_snapshot_module._hash("simulation-snapshot-v2:sha256:", identity)
            snapshot["rowHash"] = simulation_snapshot_module._hash("sha256:", {field: value for field, value in snapshot.items() if field not in {"rowHash", "originCatalogRevision"}})

        for hostile in ({}, None, "not-a-list"):
            tampered = copy.deepcopy(baseline)
            tampered["effectEvidenceByOccurrence"] = hostile
            rehash(tampered)
            self.assertIn("SIMULATION_V2_EFFECT_EVIDENCE_INVALID", verify_simulation_snapshot_v2(tampered, resolved_loadout=loadout, resolver_snapshot=source, authority_bundles={key: bundle}))

        boolean_ordinal = copy.deepcopy(baseline)
        boolean_ordinal["effectEvidenceByOccurrence"][0]["recordOrdinal"] = False
        rehash(boolean_ordinal)
        self.assertIn("SIMULATION_V2_EFFECT_EVIDENCE_INVALID", verify_simulation_snapshot_v2(boolean_ordinal, resolved_loadout=loadout, resolver_snapshot=source, authority_bundles={key: bundle}))

    def test_v2_snapshot_verifier_rejects_rehashed_deleted_genuine_trailing_occurrence(self):
        """Would fail if a rehashed snapshot could truncate a sealed A/B/A list."""
        source = v2_resolver_snapshot()
        source["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        source["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-runtime-v2"}
        bundle = v2_bundle("head", "1001", ["A", "B", "A"])
        key = bundle.envelope.content_key
        bundles = {key: bundle}
        loadout = build_resolved_loadout_v2(
            resolver_snapshot=source, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles=bundles, gear_rule_revision="gear-rule-matrix-v1", resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        snapshot = build_simulation_snapshot_v2(
            resolved_loadout=loadout, talent_profile_key=TALENT_KEY, talent_lines=TALENT_LINES,
            character_context=character_context(), scenario_options=scenario(), preparation_lines=["optimal_raid=0"],
            compiler_revision="simc-profile-compiler-v2", simc_runtime_revision="simc-runtime-v2",
            resolver_snapshot=source,
            authority_bundles=bundles,
        )
        self.assertIn("SIMULATION_V2_RESOLVED_LOADOUT_CONTEXT_REQUIRED", verify_simulation_snapshot_v2(snapshot))
        self.assertIn("SIMULATION_V2_AUTHORITY_CONTEXT_REQUIRED", verify_simulation_snapshot_v2(snapshot, resolved_loadout=loadout))
        self.assertIn("SIMULATION_V2_RESOLVER_CONTEXT_REQUIRED", verify_simulation_snapshot_v2(snapshot, resolved_loadout=loadout, authority_bundles=bundles))
        tampered = copy.deepcopy(snapshot)
        tampered["effectEvidenceByOccurrence"].pop()
        identity = {
            "resolvedLoadoutKey": tampered["resolvedLoadoutKey"],
            "exactAuthorityBySlot": simulation_snapshot_module._canonical(tampered["exactAuthorityBySlot"]),
            "effectEvidenceByOccurrence": simulation_snapshot_module._canonical(tampered["effectEvidenceByOccurrence"]),
            "talentProfileKey": tampered["talentProfileKey"],
            "characterContext": {**simulation_snapshot_module._canonical(tampered["characterContext"]), "talentLinesHash": tampered["talentLinesHash"]},
            "scenarioOptions": {**simulation_snapshot_module._canonical(tampered["scenarioOptions"]), "preparationLines": simulation_snapshot_module._canonical(tampered["preparationLines"])},
            "serializerInput": simulation_snapshot_module._canonical(tampered["serializerInput"]),
            "compilerRevision": tampered["compilerRevision"],
            "simcRuntimeRevision": tampered["simcRuntimeRevision"],
        }
        tampered["simulationSnapshotKey"] = simulation_snapshot_module._hash("simulation-snapshot-v2:sha256:", identity)
        tampered["rowHash"] = simulation_snapshot_module._hash("sha256:", {field: value for field, value in tampered.items() if field not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("SIMULATION_V2_EFFECT_EVIDENCE_CONTEXT_MISMATCH", verify_simulation_snapshot_v2(tampered, resolved_loadout=loadout, resolver_snapshot=source, authority_bundles=bundles))

    def test_v2_snapshot_verifier_rejects_rehashed_runtime_context_mismatch(self):
        """Would fail if snapshot runtime could drift from verified effect authority."""
        source = v2_resolver_snapshot()
        source["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        source["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-runtime-v2"}
        bundle = v2_bundle("head", "1001", ["A", "B", "A"])
        key = bundle.envelope.content_key
        bundles = {key: bundle}
        loadout = build_resolved_loadout_v2(
            resolver_snapshot=source, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles=bundles, gear_rule_revision="gear-rule-matrix-v1", resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        snapshot = build_simulation_snapshot_v2(
            resolved_loadout=loadout, talent_profile_key=TALENT_KEY, talent_lines=TALENT_LINES,
            character_context=character_context(), scenario_options=scenario(), preparation_lines=["optimal_raid=0"],
            compiler_revision="simc-profile-compiler-v2", simc_runtime_revision="simc-runtime-v2",
            resolver_snapshot=source,
            authority_bundles=bundles,
        )
        snapshot["simcRuntimeRevision"] = "simc-runtime-v3"
        identity = {
            "resolvedLoadoutKey": snapshot["resolvedLoadoutKey"],
            "exactAuthorityBySlot": simulation_snapshot_module._canonical(snapshot["exactAuthorityBySlot"]),
            "effectEvidenceByOccurrence": simulation_snapshot_module._canonical(snapshot["effectEvidenceByOccurrence"]),
            "talentProfileKey": snapshot["talentProfileKey"],
            "characterContext": {**simulation_snapshot_module._canonical(snapshot["characterContext"]), "talentLinesHash": snapshot["talentLinesHash"]},
            "scenarioOptions": {**simulation_snapshot_module._canonical(snapshot["scenarioOptions"]), "preparationLines": simulation_snapshot_module._canonical(snapshot["preparationLines"])},
            "serializerInput": simulation_snapshot_module._canonical(snapshot["serializerInput"]),
            "compilerRevision": snapshot["compilerRevision"],
            "simcRuntimeRevision": snapshot["simcRuntimeRevision"],
        }
        snapshot["simulationSnapshotKey"] = simulation_snapshot_module._hash("simulation-snapshot-v2:sha256:", identity)
        snapshot["rowHash"] = simulation_snapshot_module._hash("sha256:", {field: value for field, value in snapshot.items() if field not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("SIMULATION_V2_RUNTIME_CONTEXT_MISMATCH", verify_simulation_snapshot_v2(snapshot, resolved_loadout=loadout, resolver_snapshot=source, authority_bundles=bundles))

    def test_v2_snapshot_verifier_rejects_rehashed_serializer_and_character_context_drift(self):
        """Would fail if snapshot execution facts or class/spec outlived the loadout."""
        source = v2_resolver_snapshot()
        source["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        source["profileReadiness"]["requiredSlots"] = ["head"]
        source["profileReadiness"]["readySlots"] = ["head"]
        bundle = v2_bundle("head", "1001", ["A"])
        key = bundle.envelope.content_key
        bundles = {key: bundle}
        loadout = build_resolved_loadout_v2(
            resolver_snapshot=source, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles=bundles, gear_rule_revision="gear-rule-matrix-v1", resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        baseline = build_simulation_snapshot_v2(
            resolved_loadout=loadout, talent_profile_key=TALENT_KEY, talent_lines=TALENT_LINES,
            character_context=character_context(), scenario_options=scenario(), preparation_lines=["optimal_raid=0"],
            compiler_revision="simc-profile-compiler-v2", simc_runtime_revision="simc-runtime-v2",
            resolver_snapshot=source,
            authority_bundles=bundles,
        )

        def rehash(snapshot):
            snapshot["canonicalSimcInput"] = simulation_snapshot_module._v2_canonical_simc_input(
                snapshot["characterContext"], snapshot["scenarioOptions"], snapshot["talentLines"],
                snapshot["preparationLines"], snapshot["serializerInput"]["gearItems"],
            )
            snapshot["canonicalInputHash"] = "simc-input:sha256:" + __import__("hashlib").sha256(snapshot["canonicalSimcInput"].encode("utf-8")).hexdigest()
            identity = {
                "resolvedLoadoutKey": snapshot["resolvedLoadoutKey"],
                "exactAuthorityBySlot": simulation_snapshot_module._canonical(snapshot["exactAuthorityBySlot"]),
                "effectEvidenceByOccurrence": simulation_snapshot_module._canonical(snapshot["effectEvidenceByOccurrence"]),
                "talentProfileKey": snapshot["talentProfileKey"],
                "characterContext": {**simulation_snapshot_module._canonical(snapshot["characterContext"]), "talentLinesHash": snapshot["talentLinesHash"]},
                "scenarioOptions": {**simulation_snapshot_module._canonical(snapshot["scenarioOptions"]), "preparationLines": simulation_snapshot_module._canonical(snapshot["preparationLines"])},
                "serializerInput": simulation_snapshot_module._canonical(snapshot["serializerInput"]),
                "compilerRevision": snapshot["compilerRevision"],
                "simcRuntimeRevision": snapshot["simcRuntimeRevision"],
            }
            snapshot["simulationSnapshotKey"] = simulation_snapshot_module._hash("simulation-snapshot-v2:sha256:", identity)
            snapshot["rowHash"] = simulation_snapshot_module._hash("sha256:", {field: value for field, value in snapshot.items() if field not in {"rowHash", "originCatalogRevision"}})

        serializer = copy.deepcopy(baseline)
        serializer["serializerInput"]["gearItems"][0]["simcOptions"]["bonus_id"] = "9999"
        rehash(serializer)
        self.assertIn("SIMULATION_V2_SERIALIZER_CONTEXT_MISMATCH", verify_simulation_snapshot_v2(serializer, resolved_loadout=loadout, resolver_snapshot=source, authority_bundles=bundles))

        class_drift = copy.deepcopy(baseline)
        class_drift["characterContext"]["classKey"] = "warrior"
        rehash(class_drift)
        self.assertIn("SIMULATION_V2_CHARACTER_CONTEXT_MISMATCH", verify_simulation_snapshot_v2(class_drift, resolved_loadout=loadout, resolver_snapshot=source, authority_bundles=bundles))

        spec_drift = copy.deepcopy(baseline)
        spec_drift["characterContext"]["specKey"] = "fire"
        rehash(spec_drift)
        self.assertIn("SIMULATION_V2_CHARACTER_CONTEXT_MISMATCH", verify_simulation_snapshot_v2(spec_drift, resolved_loadout=loadout, resolver_snapshot=source, authority_bundles=bundles))

    def test_v2_snapshot_verifier_rejects_rehashed_non_mapping_compiler_contexts(self):
        """Would fail if malformed character/scenario containers raised or verified."""
        source, bundles, loadout, baseline = v2_snapshot_fixture()
        for field, hostile, code in (
            ("characterContext", ["not", "a", "mapping"], "SIMULATION_V2_CHARACTER_CONTEXT_INVALID"),
            ("scenarioOptions", "not-a-mapping", "SIMULATION_V2_SCENARIO_OPTIONS_INVALID"),
        ):
            with self.subTest(field=field):
                tampered = copy.deepcopy(baseline)
                tampered[field] = hostile
                rehash_v2_snapshot(tampered)
                try:
                    issues = verify_simulation_snapshot_v2(
                        tampered,
                        resolved_loadout=loadout,
                        resolver_snapshot=source,
                        authority_bundles=bundles,
                        compiler_revision="simc-profile-compiler-v2",
                    )
                except (AttributeError, KeyError, TypeError, ValueError) as error:
                    self.fail(f"{field} raised instead of failing closed: {error}")
                self.assertIn(code, issues)

    def test_v2_snapshot_rejects_rehashed_noncanonical_compiler_revision(self):
        """Would fail if compiler revision syntax or explicit context was optional."""
        source, bundles, loadout, baseline = v2_snapshot_fixture()
        for hostile in (None, " simc-profile-compiler-v2 "):
            with self.subTest(compiler_revision=hostile):
                tampered = copy.deepcopy(baseline)
                tampered["compilerRevision"] = hostile
                rehash_v2_snapshot(tampered)
                self.assertIn(
                    "SIMULATION_V2_COMPILER_REVISION_INVALID",
                    verify_simulation_snapshot_v2(
                        tampered,
                        resolved_loadout=loadout,
                        resolver_snapshot=source,
                        authority_bundles=bundles,
                        compiler_revision="simc-profile-compiler-v2",
                    ),
                )
        future = build_simulation_snapshot_v2(
            resolved_loadout=loadout,
            talent_profile_key=TALENT_KEY,
            talent_lines=TALENT_LINES,
            character_context=character_context(),
            scenario_options=scenario(),
            preparation_lines=["optimal_raid=0"],
            compiler_revision="simc-profile-compiler-v3",
            simc_runtime_revision="simc-runtime-v2",
            resolver_snapshot=source,
            authority_bundles=bundles,
        )
        self.assertEqual(future["status"], "ready")
        self.assertEqual(
            verify_simulation_snapshot_v2(
                future,
                resolved_loadout=loadout,
                resolver_snapshot=source,
                authority_bundles=bundles,
                compiler_revision="simc-profile-compiler-v3",
            ),
            [],
        )
        self.assertIn(
            "SIMULATION_V2_COMPILER_CONTEXT_MISMATCH",
            verify_simulation_snapshot_v2(
                future,
                resolved_loadout=loadout,
                resolver_snapshot=source,
                authority_bundles=bundles,
                compiler_revision="simc-profile-compiler-v2",
            ),
        )

    def test_v2_snapshot_rejects_boolean_and_nonfinite_compiler_inputs(self):
        """Would fail if v2 normalized boolean or non-finite numbers into SimC input."""
        source, bundles, loadout, _ = v2_snapshot_fixture()
        cases = (
            ({**character_context(), "level": True}, scenario()),
            (character_context(), {**scenario(), "desiredTargets": True}),
            (character_context(), {**scenario(), "varyCombatLength": float("nan")}),
            (character_context(), {**scenario(), "varyCombatLength": float("inf")}),
        )
        for hostile_character, hostile_scenario in cases:
            with self.subTest(character=hostile_character, scenario=hostile_scenario):
                result = build_simulation_snapshot_v2(
                    resolved_loadout=loadout,
                    talent_profile_key=TALENT_KEY,
                    talent_lines=TALENT_LINES,
                    character_context=hostile_character,
                    scenario_options=hostile_scenario,
                    preparation_lines=["optimal_raid=0"],
                    compiler_revision="simc-profile-compiler-v2",
                    simc_runtime_revision="simc-runtime-v2",
                    resolver_snapshot=source,
                    authority_bundles=bundles,
                )
                self.assertEqual(result["status"], "blocked")
                self.assertIn("SIMULATION_V2_COMPILER_INPUT_INVALID", result["problemCodes"])

    def test_v2_failure_uses_v2_schema(self):
        """Would fail if v2 errors returned a v1 envelope."""
        result = build_simulation_snapshot_v2(
            resolved_loadout={}, talent_profile_key="", talent_lines=[], character_context={}, scenario_options={},
            preparation_lines=[], compiler_revision="", simc_runtime_revision="",
        )
        self.assertEqual(result["schemaRevision"], "simulation-snapshot-v2")


if __name__ == "__main__":
    unittest.main()

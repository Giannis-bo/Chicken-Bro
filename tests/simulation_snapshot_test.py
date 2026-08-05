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
        source = resolver_snapshot()
        source["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        source["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"]}
        key = "exact-authority:sha256:" + "9" * 64
        loadout = build_resolved_loadout_v2(
            resolver_snapshot=source,
            exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: v2_bundle("head", "1001", key, ["A"])},
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
            origin_catalog_revision="gear-catalog:sha256:" + "b" * 64,
        )
        self.assertEqual(snapshot["status"], "ready")
        self.assertEqual(verify_simulation_snapshot_v2(snapshot), [])
        self.assertNotEqual(snapshot["simulationSnapshotKey"], self.build()["simulationSnapshotKey"])

    def test_v2_snapshot_keeps_exact_serializer_facts_for_same_item_id(self):
        """Would fail if two Exact instances with one itemId compiled identically."""
        source = resolver_snapshot()
        source["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        source["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"]}
        def snapshot_for(key, bonus):
            loadout = build_resolved_loadout_v2(
                resolver_snapshot=source,
                exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
                authority_bundles={key: v2_bundle("head", "1001", key, [], exact_fields={"bonusIds": [bonus]})},
                gear_rule_revision="gear-rule-matrix-v1", resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
            )
            return build_simulation_snapshot_v2(
                resolved_loadout=loadout, talent_profile_key=TALENT_KEY, talent_lines=TALENT_LINES,
                character_context=character_context(), scenario_options=scenario(), preparation_lines=["optimal_raid=0"],
                compiler_revision="simc-profile-compiler-v2", simc_runtime_revision="simc-runtime-v2",
            )
        first = snapshot_for("exact-authority:sha256:" + "6" * 64, "9001")
        second = snapshot_for("exact-authority:sha256:" + "7" * 64, "9002")
        self.assertEqual(first["status"], "ready")
        self.assertNotEqual(first["canonicalSimcInput"], second["canonicalSimcInput"])
        self.assertIn("bonus_id=9001", first["canonicalSimcInput"])

    def test_v2_snapshot_verifier_rejects_rehashed_canonical_input_tampering(self):
        """Would fail if a recomputed row hash could bless altered SimC bytes."""
        source = resolver_snapshot()
        source["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        source["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"]}
        key = "exact-authority:sha256:" + "a" * 64
        loadout = build_resolved_loadout_v2(
            resolver_snapshot=source, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: v2_bundle("head", "1001", key, [])}, gear_rule_revision="gear-rule-matrix-v1",
            resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        snapshot = build_simulation_snapshot_v2(
            resolved_loadout=loadout, talent_profile_key=TALENT_KEY, talent_lines=TALENT_LINES,
            character_context=character_context(), scenario_options=scenario(), preparation_lines=["optimal_raid=0"],
            compiler_revision="simc-profile-compiler-v2", simc_runtime_revision="simc-runtime-v2",
        )
        snapshot["canonicalSimcInput"] = snapshot["canonicalSimcInput"].replace("bonus_id=9001", "bonus_id=9999")
        snapshot["canonicalInputHash"] = "simc-input:sha256:" + __import__("hashlib").sha256(snapshot["canonicalSimcInput"].encode("utf-8")).hexdigest()
        snapshot["rowHash"] = simulation_snapshot_module._hash("sha256:", {key: value for key, value in snapshot.items() if key not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("SIMULATION_V2_CANONICAL_INPUT_INVALID", verify_simulation_snapshot_v2(snapshot))

    def test_v2_snapshot_verifier_binds_rehashed_serializer_and_talent_inputs(self):
        """Would fail if a v2 key ignored divergent Exact-derived compiler inputs."""
        source = resolver_snapshot()
        source["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        source["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"]}
        key = "exact-authority:sha256:" + "b" * 64
        loadout = build_resolved_loadout_v2(
            resolver_snapshot=source, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: v2_bundle("head", "1001", key, [])}, gear_rule_revision="gear-rule-matrix-v1",
            resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        baseline = build_simulation_snapshot_v2(
            resolved_loadout=loadout, talent_profile_key=TALENT_KEY, talent_lines=TALENT_LINES,
            character_context=character_context(), scenario_options=scenario(), preparation_lines=["optimal_raid=0"],
            compiler_revision="simc-profile-compiler-v2", simc_runtime_revision="simc-runtime-v2",
        )
        serializer = copy.deepcopy(baseline)
        serializer["serializerInput"]["gearItems"][0]["simcOptions"]["bonus_id"] = "9999"
        serializer["canonicalSimcInput"] = simulation_snapshot_module._v2_canonical_simc_input(
            serializer["characterContext"], serializer["scenarioOptions"], serializer["talentLines"],
            serializer["preparationLines"], serializer["serializerInput"]["gearItems"],
        )
        serializer["canonicalInputHash"] = "simc-input:sha256:" + __import__("hashlib").sha256(serializer["canonicalSimcInput"].encode("utf-8")).hexdigest()
        serializer["rowHash"] = simulation_snapshot_module._hash("sha256:", {key: value for key, value in serializer.items() if key not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("SIMULATION_SNAPSHOT_V2_IDENTITY_MISMATCH", verify_simulation_snapshot_v2(serializer))

        talents = copy.deepcopy(baseline)
        talents["talentLines"] = ["talents=DIFFERENT"]
        talents["canonicalSimcInput"] = simulation_snapshot_module._v2_canonical_simc_input(
            talents["characterContext"], talents["scenarioOptions"], talents["talentLines"],
            talents["preparationLines"], talents["serializerInput"]["gearItems"],
        )
        talents["canonicalInputHash"] = "simc-input:sha256:" + __import__("hashlib").sha256(talents["canonicalSimcInput"].encode("utf-8")).hexdigest()
        talents["rowHash"] = simulation_snapshot_module._hash("sha256:", {key: value for key, value in talents.items() if key not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("SIMULATION_V2_TALENT_IDENTITY_MISMATCH", verify_simulation_snapshot_v2(talents))

    def test_v2_snapshot_verifier_rejects_rehashed_non_mapping_authority_pair(self):
        """Would fail if a malformed authority entry were filtered before comparison."""
        source = resolver_snapshot()
        source["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        source["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"]}
        key = "exact-authority:sha256:" + "c" * 64
        loadout = build_resolved_loadout_v2(
            resolver_snapshot=source, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: v2_bundle("head", "1001", key, [])}, gear_rule_revision="gear-rule-matrix-v1",
            resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        tampered = build_simulation_snapshot_v2(
            resolved_loadout=loadout, talent_profile_key=TALENT_KEY, talent_lines=TALENT_LINES,
            character_context=character_context(), scenario_options=scenario(), preparation_lines=["optimal_raid=0"],
            compiler_revision="simc-profile-compiler-v2", simc_runtime_revision="simc-runtime-v2",
        )
        tampered["exactAuthorityBySlot"].append("not-a-pair")
        tampered["rowHash"] = simulation_snapshot_module._hash("sha256:", {key: value for key, value in tampered.items() if key not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("SIMULATION_V2_EXACT_AUTHORITY_INVALID", verify_simulation_snapshot_v2(tampered))

    def test_v2_snapshot_verifier_rejects_duplicate_effect_and_isolated_serializer_slot(self):
        """Would fail if mutable occurrence or slot rows could outlive loadout binding."""
        source = resolver_snapshot()
        source["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        source["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"]}
        key = "exact-authority:sha256:" + "d" * 64
        loadout = build_resolved_loadout_v2(
            resolver_snapshot=source, exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: v2_bundle("head", "1001", key, ["A"])}, gear_rule_revision="gear-rule-matrix-v1",
            resolver_revision="resolver-v2", simc_runtime_revision="simc-runtime-v2",
        )
        baseline = build_simulation_snapshot_v2(
            resolved_loadout=loadout, talent_profile_key=TALENT_KEY, talent_lines=TALENT_LINES,
            character_context=character_context(), scenario_options=scenario(), preparation_lines=["optimal_raid=0"],
            compiler_revision="simc-profile-compiler-v2", simc_runtime_revision="simc-runtime-v2",
        )
        occurrence = copy.deepcopy(baseline)
        occurrence["effectEvidenceByOccurrence"].append(copy.deepcopy(occurrence["effectEvidenceByOccurrence"][0]))
        occurrence["rowHash"] = simulation_snapshot_module._hash("sha256:", {key: value for key, value in occurrence.items() if key not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("SIMULATION_V2_EFFECT_EVIDENCE_INVALID", verify_simulation_snapshot_v2(occurrence))
        isolated = copy.deepcopy(baseline)
        isolated["serializerInput"]["gearItems"][0]["slot"] = "off_hand"
        isolated["rowHash"] = simulation_snapshot_module._hash("sha256:", {key: value for key, value in isolated.items() if key not in {"rowHash", "originCatalogRevision"}})
        self.assertIn("SIMULATION_V2_SERIALIZER_AUTHORITY_MISMATCH", verify_simulation_snapshot_v2(isolated))

    def test_v2_failure_uses_v2_schema(self):
        """Would fail if v2 errors returned a v1 envelope."""
        result = build_simulation_snapshot_v2(
            resolved_loadout={}, talent_profile_key="", talent_lines=[], character_context={}, scenario_options={},
            preparation_lines=[], compiler_revision="", simc_runtime_revision="",
        )
        self.assertEqual(result["schemaRevision"], "simulation-snapshot-v2")


if __name__ == "__main__":
    unittest.main()

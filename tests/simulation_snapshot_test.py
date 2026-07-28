import copy
import unittest

from server.simulation_snapshot import (
    build_simulation_snapshot,
    talent_profile_key,
)
from tests.gear_resolved_loadout_test import (
    TEMPLATE_HASH,
    exact_registry,
    resolver_snapshot,
)
from server.gear_resolved_loadout import build_resolved_loadout


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


if __name__ == "__main__":
    unittest.main()

import unittest
from dataclasses import replace

from server.app.simulation.compiler import SimcCompileError, SimcProfileCompiler, normalize_scenario, scenario_hash
from tests import app_simulation_compiler_test as compiler_tests


class WorkbenchScenarioTest(unittest.TestCase):
    def test_options_reach_profile_and_change_identity(self):
        fixture = compiler_tests.SimulationCompilerTest()
        fixture.setUp()
        options = dict(fightStyle='LightMovement', desiredTargets=3, iterations=1000,
                       maxTime=180, varyCombatLength=0.1, targetError=0.5,
                       raidBuffs=True, bloodlust=False)
        capabilities = replace(fixture.capabilities, compiler_revision='chickenbro-simc-compiler-v3')
        compiled = SimcProfileCompiler(capabilities=capabilities).compile(fixture.snapshot, options)
        for line in ('fight_style=LightMovement', 'max_time=180', 'vary_combat_length=0.1',
                     'target_error=0.5', 'optimal_raid=1', 'override.bloodlust=0'):
            self.assertIn(line, compiled.profile.splitlines())
        for key, changed in [('varyCombatLength', 0.2), ('targetError', 1), ('raidBuffs', False), ('bloodlust', True)]:
            self.assertNotEqual(compiled.scenario_hash, scenario_hash({**options, key: changed}))

    def test_legacy_normalization_remains_exact(self):
        self.assertEqual(normalize_scenario({}), dict(fightStyle='Patchwerk', desiredTargets=1, iterations=300))

    def test_rejects_unsupported_style_and_wrong_types(self):
        for options in [dict(fightStyle='ArbitraryStyle'), dict(desiredTargets=True), dict(iterations=1.5),
                        dict(varyCombatLength=float('nan')), dict(targetError=float('inf')),
                        dict(raidBuffs=1), dict(bloodlust='false'), dict(varyCombatLength=.51),
                        dict(targetError=5.1), dict(maxTime=601)]:
            with self.subTest(options=options), self.assertRaises(SimcCompileError):
                normalize_scenario(options)

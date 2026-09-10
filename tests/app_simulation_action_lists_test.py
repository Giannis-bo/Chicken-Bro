import copy
import unittest
from dataclasses import replace
from server.app.simulation.compiler import SimcCompileError, SimcProfileCompiler, normalize_scenario, scenario_hash
from server.app.simulation.experiments import merge_scenario
from tests import app_simulation_compiler_test as compiler_fixtures


class ActionListsTest(unittest.TestCase):
    def setUp(self):
        fixture = compiler_fixtures.SimulationCompilerTest(); fixture.setUp()
        self.snapshot = fixture.snapshot
        self.compiler = SimcProfileCompiler(capabilities=replace(fixture.capabilities,
            compiler_revision='chickenbro-simc-compiler-v6'))

    def test_two_orders_compile_distinct_profiles_without_changing_character(self):
        before = copy.deepcopy(self.snapshot.snapshot)
        a = {'default': ['strict_sequence,name=burst:stormkeeper:ascendance', 'lightning_bolt']}
        b = {'default': ['strict_sequence,name=burst:ascendance:stormkeeper', 'lightning_bolt']}
        first = self.compiler.compile(self.snapshot, {'actionLists': a})
        second = self.compiler.compile(self.snapshot, {'actionLists': b})
        self.assertIn('actions=strict_sequence,name=burst:stormkeeper:ascendance\nactions+=/lightning_bolt\n', first.profile)
        self.assertNotEqual(first.profile_sha256, second.profile_sha256)
        self.assertNotEqual(first.scenario_hash, second.scenario_hash)
        self.assertEqual(self.snapshot.snapshot, before)
        strip = lambda p: [line for line in p.splitlines() if not line.startswith('actions')]
        self.assertEqual(strip(first.profile), strip(second.profile))

    def test_rejects_injection_missing_default_oversize_and_dangling_lists(self):
        for lists in ({}, {'cooldowns':['ascendance']}, {'../file':['lightning_bolt'], 'default':['lightning_bolt']},
                      {'default':['lightning_bolt\ninput=/etc/passwd']}, {'default':['lightning_bolt input=x']},
                      {'default':['lightning_bolt'] * 257}, {'default':['call_action_list,name=missing']},
                      {'default':['run_action_list,name=default']}, {'default':['lightning_bolt#comment']}, {'default':['lightning_bolt,if=1/input=x']},
                      {'default':['strict_sequence,name=x:run_action_list,name=default']}):
            with self.subTest(lists=lists), self.assertRaises(SimcCompileError):
                normalize_scenario({'actionLists': lists})

    def test_replacement_is_atomic_and_omission_preserves_lists(self):
        original = {'actionLists': {'default':['call_action_list,name=burst','lightning_bolt'], 'burst':['ascendance']}, 'maxTime':60}
        self.assertEqual(merge_scenario(original, {'iterations':200})['actionLists'], original['actionLists'])
        patched = merge_scenario(original, {'actionLists':{'default':['lightning_bolt']}})
        self.assertEqual(patched['actionLists'], {'default':['lightning_bolt']})
        self.assertEqual(patched['maxTime'], 60)
        self.assertNotEqual(scenario_hash(original), scenario_hash(patched))

    def test_old_compiler_cannot_silently_ignore_custom_list(self):
        from tests import app_simulation_compiler_test as compiler_fixtures
        fixture=compiler_fixtures.SimulationCompilerTest();fixture.setUp()
        compiler=SimcProfileCompiler(capabilities=replace(fixture.capabilities,compiler_revision='chickenbro-simc-compiler-v5'))
        with self.assertRaises(SimcCompileError) as caught:
            compiler.compile(self.snapshot, {'actionLists': {'default':['lightning_bolt']}})
        self.assertEqual(caught.exception.code, 'COMPILER_UNAVAILABLE')

class ActionEvidenceTest(unittest.TestCase):
    def test_extracts_bounded_actual_actions_without_raw_fields(self):
        from server.app.simulation.action_lists import extract_action_evidence
        payload = {'sim':{'players':[{'name':'Sample','collected_data':{'action_sequence':[
            {'time':0, 'name':'stormkeeper', 'id':191634, 'target':'PRIVATE', 'secret':'PRIVATE'},
            {'time':1.5, 'name':'ascendance', 'id':114050}]}}]}}
        import json
        result=extract_action_evidence(json.dumps(payload), 'Sample', 'a'*64)
        self.assertEqual(result['sample'], [{'time':0.0,'name':'stormkeeper','spellId':191634}, {'time':1.5,'name':'ascendance','spellId':114050}])
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertEqual(result['profileSha256'], 'a'*64)
        payload['sim']['players'][0]['collected_data']['action_sequence'][1]['time']=-1
        with self.assertRaises(ValueError): extract_action_evidence(json.dumps(payload), 'Sample', 'a'*64)

    def test_missing_actual_actions_fail_closed(self):
        from server.app.simulation.action_lists import extract_action_evidence
        for raw in ('{}', '{"sim":{"players":[]}}', '{"sim":{"players":[{"name":"Other"}]}}'):
            with self.assertRaises(ValueError): extract_action_evidence(raw, 'Sample', 'a'*64)

import copy
import json
import unittest
from dataclasses import replace
from server.app.simulation.effective_config import verify_effective_config
from tests import app_simulation_compiler_test as compiler_fixtures

class EffectiveConfigTest(unittest.TestCase):
    def setUp(self):
        f=compiler_fixtures.SimulationCompilerTest();f.setUp()
        from server.app.simulation.compiler import SimcProfileCompiler
        self.compiled=SimcProfileCompiler(capabilities=replace(f.capabilities,compiler_revision='chickenbro-simc-compiler-v5')).compile(f.snapshot,
            {'equipmentOverrides':{'trinket1':{'itemId':9999,'itemLevel':285,'bonusIds':[],'gems':[],'enchant':None}}})
        talents=next(line.split('=',1)[1] for line in self.compiled.profile.splitlines() if line.startswith('talents='))
        self.report={'actor':{'talents':talents},'gear':[{'slot':slot,'itemId':item['itemId'],'itemLevel':285 if slot=='trinket1' else item['itemLevel']}
                      for slot,item in {**f.snapshot.snapshot['gear'],**self.compiled.scenario['equipmentOverrides']}.items()]}
    def test_food_identity_requires_matching_engine_actor_evidence(self):
        compiled = replace(self.compiled, scenario={'food': 'hearty_silvermoon_parade'})
        def raw(food, name=None):
            return json.dumps({'sim': {'players': [{'name': name or compiled.actor_name, 'food': food}]}})
        proof = verify_effective_config(compiled, self.report, raw('hearty_silvermoon_parade'))
        self.assertEqual(proof['food'], 'hearty_silvermoon_parade')
        self.assertIn('foodInputIdentity', proof['checked'])
        for payload in (None, raw('disabled'), raw('hearty_silvermoon_parade', 'OtherActor')):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                verify_effective_config(compiled, self.report, payload)

    def test_accepts_report_matching_effective_equipment_and_talents(self):
        proof=verify_effective_config(self.compiled,self.report)
        self.assertEqual(proof['profileSha256'],self.compiled.profile_sha256)
        self.assertEqual(proof['status'],'verified')

    def test_changed_enchant_cannot_pass_without_engine_gear_evidence(self):
        scenario = copy.deepcopy(self.compiled.scenario)
        scenario['equipmentOverrides']['trinket1']['enchant'] = 123
        compiled = replace(self.compiled, scenario=scenario)
        with self.assertRaisesRegex(ValueError, 'SIMC_EFFECTIVE_CONFIG_MISMATCH'):
            verify_effective_config(compiled, self.report)

    def test_engine_enchant_identity_is_bound_to_actor_slot_and_requested_change(self):
        scenario = copy.deepcopy(self.compiled.scenario)
        scenario['equipmentOverrides']['trinket1']['enchant'] = 123
        compiled = replace(self.compiled, scenario=scenario)
        def payload(encoded, name=None):
            return json.dumps({'sim': {'players': [{'name': name or compiled.actor_name,
                'gear': {'trinket1': {'encoded_item': encoded}}}]}})
        proof = verify_effective_config(compiled, self.report, payload('sample,id=9999,enchant_id=123'))
        self.assertEqual(proof['overriddenEnchants'], {'trinket1': 123})
        self.assertIn('overriddenEnchantIds', proof['checked'])
        self.assertEqual(proof['enchantEvidenceScope'], 'engine_reported_input_identity')
        for encoded in ('sample,id=9999', 'sample,id=9999,enchant_id=124',
                        'sample,id=9999,enchant_id=123,enchant_id=124',
                        'sample,id=1000,enchant_id=123', 'sample,id=9999,enchant_id=abc',
                        'sample,id=9999,enchant_id=123,enchant=other'):
            with self.subTest(encoded=encoded), self.assertRaises(ValueError):
                verify_effective_config(compiled, self.report, payload(encoded))
        with self.assertRaises(ValueError):
            verify_effective_config(compiled, self.report, payload('sample,id=9999,enchant_id=123', 'OtherActor'))

    def test_explicit_enchant_removal_is_checked_when_raw_report_is_available(self):
        def payload(encoded):
            return json.dumps({'sim': {'players': [{'name': self.compiled.actor_name,
                'gear': {'trinket1': {'encoded_item': encoded}}}]}})
        proof = verify_effective_config(self.compiled, self.report, payload('sample,id=9999'))
        self.assertEqual(proof['overriddenEnchants'], {'trinket1': None})
        with self.assertRaises(ValueError):
            verify_effective_config(self.compiled, self.report, payload('sample,id=9999,enchant_id=123'))
    def test_rejects_wrong_item_level_missing_gear_or_talents(self):
        for kind in ('item','level','gear','talents','missing'):
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                report=copy.deepcopy(self.report)
                trinket=next(x for x in report['gear'] if x['slot']=='trinket1')
                if kind=='item':trinket['itemId']=10
                if kind=='level':trinket['itemLevel']=280
                if kind=='gear':report['gear']=[]
                if kind=='talents':report['actor']['talents']='other'
                verify_effective_config(self.compiled,None if kind=='missing' else report)

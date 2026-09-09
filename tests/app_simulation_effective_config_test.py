import copy
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
    def test_accepts_report_matching_effective_equipment_and_talents(self):
        proof=verify_effective_config(self.compiled,self.report)
        self.assertEqual(proof['profileSha256'],self.compiled.profile_sha256)
        self.assertEqual(proof['status'],'verified')
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

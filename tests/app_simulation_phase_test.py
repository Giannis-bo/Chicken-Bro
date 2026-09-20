import json
import unittest
from dataclasses import replace
from tests.app_simulation_compiler_test import SimulationCompilerTest
from server.app.simulation.compiler import SimcProfileCompiler, SimcCompileError, normalize_scenario, scenario_hash

class PhaseCompilerTest(SimulationCompilerTest):
    def test_phase_compiles_native_state_and_fixed_window(self):
        compiler=SimcProfileCompiler(capabilities=replace(self.capabilities,compiler_revision='chickenbro-simc-compiler-v7'))
        phase={'initialState':{'resources':{'maelstrom':125},'buffs':{'flowing_elements':{'stacks':2,'remainingSeconds':15}}},
               'actionLists':{'default':['lightning_bolt']},'measurement':{'durationSeconds':20,'actions':[{'action':'elemental_blast','buff':'master_of_the_elements'}]},'iterations':8}
        c=compiler.compile(self.snapshot,phase)
        self.assertIn('initial_resource=maelstrom=125\n',c.profile)
        self.assertIn('override.precombat_state=buff.flowing_elements.stack=2\n',c.profile)
        self.assertIn('override.precombat_state=buff.flowing_elements.remains=15\n',c.profile)
        self.assertIn('max_time=20\n',c.profile)
        self.assertIn('actions.precombat=snapshot_stats,if=buff.flowing_elements.up&buff.flowing_elements.max_stack>=2\n',c.profile)
        self.assertNotEqual(c.scenario_hash,scenario_hash({}))

    def test_phase_rejects_conflicting_windows_precombat_and_injection(self):
        base={'actionLists':{'default':['lightning_bolt']},'measurement':{'durationSeconds':20},'iterations':8}
        for patch in ({'maxTime':30},{'varyCombatLength':.1},{'iterations':10000},
                      {'initialState':{'resources':{'energy':True}}},
                      {'initialState':{'buffs':{'x\ninput=y':{'stacks':1,'remainingSeconds':10}}}},
                      {'actionLists':{'default':['lightning_bolt'],'precombat':['potion']}},
                      {'initialState':{'buffs':{'x':{'stacks':1,'remainingSeconds':10,'value':500}}}}):
            with self.subTest(patch=patch),self.assertRaises(SimcCompileError):normalize_scenario({**base,**patch})

    def test_phase_requires_measurement_and_preserves_max(self):
        with self.assertRaises(SimcCompileError):normalize_scenario({'initialState':{'resources':{'energy':'max'}}})
        n=normalize_scenario({'actionLists':{'default':['lightning_bolt']},'measurement':{'durationSeconds':20},'initialState':{'resources':{'energy':'max'}}})
        self.assertEqual(n['initialState']['resources']['energy'],'max')
        self.assertLessEqual(n['iterations'],128)

if __name__=='__main__':unittest.main()

class PhaseEvidenceTest(unittest.TestCase):
    def fixture(self):
        state={'time':0,'name':'snapshot_stats','id':0,'resources':{'energy':40},'resources_max':{'energy':100},
               'buffs':[{'name':'slice_and_dice','id':315496,'stacks':1,'remains':10}], 'cooldowns':[]}
        return {'name':'Actor','collected_data':{'fight_length':{'mean':20},'dmg':{'mean':200},'compound_dmg':{'mean':200},'dps':{'mean':10},
                'action_sequence_precombat':[state], 'action_sequence':[
                    {**state,'name':'mutilate','id':1329}, {**state,'time':1,'name':'mutilate','id':1329,'buffs':[]}]},
                'gains':[{'name':'regen','energy':{'actual':20,'overflow':3}}]}
    def scenario(self):
        return normalize_scenario({'iterations':2,'initialState':{'resources':{'energy':40},'buffs':{'slice_and_dice':{'stacks':1,'remainingSeconds':10}}},
              'actionLists':{'default':['lightning_bolt']},'measurement':{'durationSeconds':20,'actions':[{'action':'mutilate','buff':'slice_and_dice'}]},
              'assertions':{'openingActions':['mutilate'],'requiredBuffs':['slice_and_dice']}})
    def test_all_iteration_metrics_count_buff_carry_and_overflow(self):
        from server.app.simulation.phase_evidence import inspect_iteration, aggregate_phase
        a=inspect_iteration(self.fixture(),self.scenario())
        self.assertEqual(a['actions'][0]['casts'],2)
        self.assertEqual(a['actions'][0]['withBuff'],1)
        self.assertEqual(a['resourceOverflow']['energy'],3)
        self.assertEqual(a['status'],'satisfied')
        b={**a,'damage':400}
        aggregate=aggregate_phase([a,b],self.scenario(),'a'*64)
        self.assertEqual(aggregate['damage']['mean'],300)
        self.assertEqual(aggregate['iterations'],2)
        self.assertEqual(aggregate['actions'][0]['withBuff']['mean'],1)
    def test_state_mismatch_or_late_snapshot_cannot_pass(self):
        from server.app.simulation.phase_evidence import inspect_iteration
        for kind in ('late','resource','duration','stacks'):
            a=self.fixture();s=a['collected_data']['action_sequence_precombat'][0]
            if kind=='late':s['time']=1
            if kind=='resource':s['resources']['energy']=41
            if kind=='duration':s['buffs'][0]['remains']=5
            if kind=='stacks':s['buffs'][0]['stacks']=2
            with self.subTest(kind=kind),self.assertRaises(ValueError):inspect_iteration(a,self.scenario())
    def test_required_effect_failure_and_short_batch_are_not_success(self):
        from server.app.simulation.phase_evidence import inspect_iteration, aggregate_phase
        s=self.scenario();s['assertions']['requiredBuffs']=['potion_of_recklessness_Crit']
        a=inspect_iteration(self.fixture(),s)
        self.assertEqual(a['status'],'violated')
        with self.assertRaises(ValueError):aggregate_phase([a],s,'a'*64)

class PhaseEngineEdgeTest(PhaseEvidenceTest):
    def test_indefinite_consumable_buff_is_preserved_without_fake_duration(self):
        from server.app.simulation.phase_evidence import inspect_iteration
        a=self.fixture();a['collected_data']['action_sequence'][0]['buffs']=[{'name':'ancestral_swiftness','id':443454,'stacks':1,'remains':-9223372036854776.0}]
        row=inspect_iteration(a,self.scenario())
        self.assertIsNone(row['sample'][0]['buffs']['ancestral_swiftness']['remains'])
    def test_opaque_sequence_cannot_hide_measured_actions(self):
        with self.assertRaises(SimcCompileError):normalize_scenario({'measurement':{'durationSeconds':20},'actionLists':{'default':['strict_sequence,name=x:ascendance:elemental_blast']}})

class PhasePetDamageTest(PhaseEvidenceTest):
    def test_total_damage_includes_guardian_and_pet_contributions(self):
        from server.app.simulation.phase_evidence import inspect_iteration
        a=self.fixture();a['collected_data']['compound_dmg']={'mean':300};a['collected_data']['dps']={'mean':15}
        self.assertEqual(inspect_iteration(a,self.scenario())['damage'],300)

class PhaseBatchTest(unittest.TestCase):
    def inputs(self):
        from dataclasses import dataclass
        from tests.app_simulation_report_test import report_fixture
        scenario=normalize_scenario({'iterations':2,'measurement':{'durationSeconds':20},
                                    'initialState':{'resources':{'energy':'max'}},'actionLists':{'default':['lightning_bolt']}})
        @dataclass
        class Compiled:
            scenario:dict
            profile:str='actor=sample\n'
            provenance:dict=None
            actor_name:str='Stormsample'
            profile_sha256:str='a'*64
            scenario_hash:str='b'*64
            runtime_revision:str='runtime'
        raw=report_fixture();actor=raw['sim']['players'][0]
        actor['collected_data'].update(PhaseEvidenceTest().fixture()['collected_data'])
        actor['gains']=PhaseEvidenceTest().fixture()['gains']
        state=actor['collected_data']['action_sequence_precombat'][0];state['resources']['energy']=100
        return Compiled(scenario,provenance={'sourceRawSha256':'1'*64}),raw

    def test_discovery_each_iteration_budget_and_aggregate_identity(self):
        from unittest.mock import patch
        from server.app.simulation.phase_execution import run_phase
        from server.app.simulation.worker import RawSimulationExecution
        from server.app.simulation.report_identity import validate_report_identity
        compiled,raw=self.inputs();calls=[]
        class Port:
            _timeout_seconds=45
            def _run_once(self, derived, revision, **kwargs):
                calls.append((derived.profile,kwargs))
                return RawSimulationExecution(0,'','','runtime',report_json=json.dumps(raw))
        with patch('server.app.simulation.phase_execution.verify_effective_config'):
            result=run_phase(Port(),compiled,'runtime')
        self.assertEqual(len(calls),3)
        self.assertNotIn('initial_resource=energy=100',calls[0][0])
        self.assertIn('initial_resource=energy=100',calls[1][0])
        self.assertTrue(all(c[1]['full_states'] and 0<c[1]['timeout_seconds']<=45 for c in calls))
        self.assertEqual(result.phase_evidence['iterations'],2)
        self.assertTrue(validate_report_identity(result.phase_identity,result.phase_report))

    def test_failed_assertion_stops_batch(self):
        from unittest.mock import patch
        from server.app.simulation.phase_execution import run_phase
        from server.app.simulation.worker import RawSimulationExecution,SimulationWorkerError
        compiled,raw=self.inputs();compiled.scenario['assertions']={'maxResourceOverflow':{'energy':0}}
        calls=[]
        class Port:
            _timeout_seconds=45
            def _run_once(self,*args,**kwargs):
                calls.append(1);return RawSimulationExecution(0,'','','runtime',report_json=json.dumps(raw))
        with patch('server.app.simulation.phase_execution.verify_effective_config'),self.assertRaisesRegex(SimulationWorkerError,'SIMC_PHASE_ASSERTION_FAILED'):
            run_phase(Port(),compiled,'runtime')
        self.assertEqual(len(calls),2)


class NativePhaseSchemaEntrypointTest(unittest.TestCase):
    def test_standalone_script_loads_phase_schema_outside_repository(self):
        import subprocess,sys,tempfile
        from pathlib import Path
        entry=Path(__file__).resolve().parents[1]/'server/chickenbro_native_mcp.py'
        with tempfile.TemporaryDirectory() as cwd:
            result=subprocess.run([sys.executable,str(entry)],cwd=cwd,input=json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/list','params':{}})+'\n',text=True,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        result=json.loads(result.stdout)['result']['tools']
        submit=next(t for t in result if t['name']=='submit_simulation')
        self.assertIn('initialState',submit['inputSchema']['properties']['scenario']['properties'])

import importlib.util
import json
from pathlib import Path
import unittest

FILE = Path(__file__).resolve().parents[1] / 'scripts/agent_benchmark_fixtures.py'


class FixturesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if FILE.exists():
            spec = importlib.util.spec_from_file_location('fixtures', FILE)
            cls.f = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.f)

    def test_corpus_has_four_paired_categories_and_multiturn(self):
        self.assertTrue(FILE.exists(), 'fixture implementation missing')
        self.assertEqual(len(self.f.CASES), 8)
        self.assertEqual(sorted([sum(c['category'] == k for c in self.f.CASES) for k in {c['category'] for c in self.f.CASES}]), [2]*4)
        self.assertGreaterEqual(sum(len(c['turns']) == 2 for c in self.f.CASES), 2)
        for c in self.f.CASES:
            self.assertTrue(c['rubric'] and c['requiredEvidence'])

    def test_all_declared_paths_have_evidence_and_are_replayable(self):
        self.assertTrue(FILE.exists(), 'fixture implementation missing')
        for case in self.f.CASES:
            s = self.f.FixtureSession(case['id'])
            for name, args in self.f.REFERENCE_CALLS[case['id']]:
                result = s.call(name, args)
                self.assertNotEqual(result['status'], 'error', (case['id'], name, result))
                self.assertEqual(result, s.call(name, args))
                self.assertTrue(result['fixture']['synthetic'])
            observed = {key for r in s.receipts for key in r['evidenceKeys']}
            self.assertTrue(set(case['requiredEvidence']) <= observed, (case['id'], observed))

    def test_actor_window_and_event_kind_filtering(self):
        self.assertTrue(FILE.exists(), 'fixture implementation missing')
        s = self.f.FixtureSession('wcl_timeline')
        args = {'target': self.f.WCL_URL + '?fight=7&source=11', 'options': {'view': 'events', 'dataType': 'Casts', 'startTime': 30000, 'endTime': 60000}}
        events = s.call('query_warcraftlogs_report', args)['facts'][0]['events']
        self.assertEqual([e['timestamp'] for e in events], [35000])
        args['options']['startTime'] = 0
        self.assertEqual(len(s.call('query_warcraftlogs_report', args)['facts'][0]['events']), 2)
        args['options']['endTime'] = 1000000
        self.assertEqual(s.call('query_warcraftlogs_report', args)['status'], 'error')

    def test_unknown_schema_and_unavailable_resources_fail_closed(self):
        self.assertTrue(FILE.exists(), 'fixture implementation missing')
        s = self.f.FixtureSession('wcl_healing')
        for name, args in [('unknown', {}), ('query_warcraftlogs_report', {'target': self.f.WCL_URL, 'owner': 'x'}), ('query_warcraftlogs_report', {'target': self.f.WCL_URL, 'options': {'view': 'oops'}}), ('research_public_web', {'target':'https://example.com/private'})]:
            self.assertEqual(s.call(name, args)['status'], 'error')

    def test_simc_rejects_unpreviewed_or_changed_controls_and_preserves_error(self):
        self.assertTrue(FILE.exists(), 'fixture implementation missing')
        s = self.f.FixtureSession('simc_equipment')
        submit = next(a for n,a in self.f.REFERENCE_CALLS['simc_equipment'] if n == 'submit_simulation')
        self.assertEqual(s.call('submit_simulation', submit)['status'], 'error')
        for name,args in self.f.REFERENCE_CALLS['simc_equipment']:
            result = s.call(name,args)
        self.assertEqual(result['comparison']['delta'], 5000)
        self.assertEqual(result['comparison']['baselineError'], 1000)
        changed = {**submit, 'scenario': {**submit['scenario'], 'iterations': 999}}
        self.assertEqual(s.call('preview_simulation', changed)['status'], 'error')

    def test_pagination_is_chronological_and_state_survives_next_turn(self):
        self.assertTrue(FILE.exists(), 'fixture implementation missing')
        s = self.f.FixtureSession('wcl_timeline')
        args = {'target':self.f.WCL_URL+'?fight=7', 'options':{'view':'events','limit':2}}
        fact = s.call('query_warcraftlogs_report',args)['facts'][0]
        self.assertEqual([e['timestamp'] for e in fact['events']], [5000,10000])
        self.assertEqual(fact['eventPage']['nextPageTimestamp'],35000)
        args['options']['startTime']=35000
        self.assertEqual(s.call('query_warcraftlogs_report',args)['facts'][0]['events'][0]['timestamp'],35000)
        s = self.f.FixtureSession('simc_apl')
        for name,args in self.f.REFERENCE_CALLS['simc_apl']:
            s.call(name,args)
        restored=self.f.FixtureSession('simc_apl')
        restored.__dict__.update(json.loads(json.dumps(s.__dict__)))
        self.assertEqual(restored.call('get_simulation_job',{'jobId':self.f.VAR_JOB}),s.call('get_simulation_job',{'jobId':self.f.VAR_JOB}))

    def test_nested_arguments_and_wrong_rankings_scope_are_rejected(self):
        self.assertTrue(FILE.exists(), 'fixture implementation missing')
        s = self.f.FixtureSession('rankings_raid')
        self.assertEqual(s.call('query_warcraftlogs_rankings', {'partition':2})['status'],'error')
        self.assertEqual(s.call('query_warcraftlogs_batch', {'queries':[{'target':self.f.WCL_URL,'options':{'sourceID':11}}]})['status'],'error')

    def test_raid_groups_bind_distinct_encounters_to_distinct_fights(self):
        s=self.f.FixtureSession('rankings_raid')
        rows=[]
        for name,args in self.f.REFERENCE_CALLS['rankings_raid']:
            result=s.call(name,args)
            if name=='query_warcraftlogs_rankings' and 'encounterId' in args:
                rows.append(result['facts'][0]['rankings'][0]['report']['fightID'])
        self.assertEqual(rows,[7,8])

    def test_native_grounding_collectors_recognize_only_returned_fixture_evidence(self):
        from server.app.chickenbro.answer_grounding import collect_evidence
        from server.app.chickenbro.simulation_grounding import collect_simulation_evidence
        for case_id,calls in self.f.REFERENCE_CALLS.items():
            s=self.f.FixtureSession(case_id)
            reports,simulations=None,None
            for name,args in calls:
                response=s.call(name,args)
                reports=collect_evidence(reports,response)
                simulations=collect_simulation_evidence(simulations,response)
                if name=='get_simulation_job':
                    self.assertEqual(simulations['jobs'][args['jobId']]['status'],'succeeded')
                    self.assertEqual(simulations['jobs'][args['jobId']]['metricName'],'dps')
            if case_id.startswith('wcl_') or case_id=='rankings_raid':
                self.assertTrue(reports['reports'],case_id)
                self.assertTrue(reports['coverage']['reportReceipts'],case_id)
            if case_id=='rankings_raid':
                self.assertEqual(len(reports['groups']),2)
                self.assertEqual(len(reports['coverage']['rankingSnapshots']),2)
                self.assertTrue(reports['coverage']['directories'])
                self.assertEqual({r['player']['id'] for r in reports['reports'] if r.get('group') and r.get('player')},{11,22})
            if case_id.startswith('simc_'):
                self.assertEqual(len(simulations['comparisons']),1)
                self.assertEqual(set(simulations['jobs']),{self.f.BASE_JOB,self.f.VAR_JOB})
            else:
                self.assertFalse(simulations['jobs'])

    def test_healing_native_totals_reconcile_with_raw_spell_rows(self):
        s=self.f.FixtureSession('wcl_healing')
        for actor,expected in [(11,800000),(22,600000)]:
            name,args=self.f.report(actor,'healing')
            healing=s.call(name,args)['facts'][0]['healing']
            self.assertEqual(healing['totals']['effective'],expected)
            self.assertEqual(sum(r['total']-r['overheal'] for r in healing['entries']),expected)
            self.assertEqual(sum(r['total'] for r in healing['entries']),1000000)

    def test_native_batch_preserves_independent_members(self):
        s=self.f.FixtureSession('wcl_healing')
        queries=[self.f.report(actor,'healing')[1] for actor in (11,22)]
        result=s.call('query_warcraftlogs_batch',{'queries':queries})
        self.assertEqual([r['facts'][0]['sourceId'] for r in result.get('results',[])],[11,22])
        self.assertTrue(all(r['status']=='verified' for r in result['results']))

    def test_simc_variants_preserve_nonexperimental_state_and_hash_actual_scenario(self):
        import hashlib
        for case_id in ('simc_equipment','simc_apl'):
            s=self.f.FixtureSession(case_id)
            base=s.call('get_simulation_job',{'jobId':self.f.BASE_JOB})
            edit=next(a for n,a in self.f.REFERENCE_CALLS[case_id] if n=='preview_simulation')
            if case_id=='simc_equipment':
                edit=json.loads(json.dumps(edit))
                edit['scenario']['actionLists']=base['scenario']['actionLists']
            for name in ('preview_simulation','submit_simulation'):
                self.assertNotEqual(s.call(name,edit)['status'],'error')
            variant=s.call('get_simulation_job',{'jobId':self.f.VAR_JOB})
            if case_id=='simc_equipment':
                self.assertEqual(base['scenario']['actionLists'],variant['scenario']['actionLists'])
            else:
                self.assertEqual(base['gear'],variant['gear'])
            for result in (base,variant):
                self.assertEqual(result['scenarioHash'],hashlib.sha256(json.dumps(result['scenario'],sort_keys=True).encode()).hexdigest())
                self.assertEqual(result['effectiveConfig'],result['scenario'])

    def test_equivalent_sequence_name_is_accepted_but_order_and_tail_are_not(self):
        s=self.f.FixtureSession('simc_apl')
        args={'baseJobId':self.f.BASE_JOB,'scenario':{'actionLists':{'default':['strict_sequence,name=experiment:lava_burst:lightning_bolt','lightning_bolt']}}}
        self.assertNotEqual(s.call('preview_simulation',args)['status'],'error')
        args['scenario']['actionLists']['default'][1]='lava_burst'
        self.assertEqual(s.call('preview_simulation',args)['status'],'error')
        args['scenario']['actionLists']['default']=['strict_sequence,name=experiment:lightning_bolt:lava_burst','lightning_bolt']
        self.assertEqual(s.call('preview_simulation',args)['status'],'error')

    def test_equivalent_acquisition_paths_emit_semantic_coverage(self):
        s=self.f.FixtureSession('wcl_timeline')
        result=s.call(*self.f.report(view='events'))
        required=next(c['requiredEvidence'] for c in self.f.CASES if c['id']=='wcl_timeline')
        self.assertTrue(set(required)<=set(result['evidenceKeys']))
        partial=s.call(*self.f.report(view='events',limit=1))
        self.assertNotIn('casts.22.30000.60000',partial['evidenceKeys'])
        s=self.f.FixtureSession('rankings_raid')
        result=s.call(*self.f.report(22,view='statistics',fight=8))
        self.assertIn('raid.actor22',result['evidenceKeys'])
        s=self.f.FixtureSession('simc_equipment')
        for name,args in self.f.REFERENCE_CALLS['simc_equipment']:
            if name=='get_simulation_job' and args['jobId']==self.f.VAR_JOB:
                continue
            result=s.call(name,args)
        self.assertIn('simc.variant',result['evidenceKeys'])

    def test_two_ranked_samples_can_be_acquired_by_offset(self):
        s=self.f.FixtureSession('rankings_mplus')
        args={'className':'shaman','spec':'elemental','limit':1}
        first=s.call('query_raiderio_rankings',args)
        self.assertEqual(first['pagination']['nextOffset'],1)
        second=s.call('query_raiderio_rankings',{**args,'offset':1})
        self.assertEqual(second['rankings'][0]['name'],'Fixturebeta')
        self.assertIsNone(second['pagination']['nextOffset'])


if __name__ == '__main__':
    unittest.main()

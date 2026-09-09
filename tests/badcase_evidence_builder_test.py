import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]
SCRIPT=REPO/'artifacts/verification/2026-09-09-badcase-workflow/build-generalization.py'
spec=importlib.util.spec_from_file_location('badcase_evidence_builder',SCRIPT)
b=importlib.util.module_from_spec(spec)
if SCRIPT.exists(): spec.loader.exec_module(b)


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(hasattr(b,'build'),'evidence builder required')
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.before=self.root/'before';self.after=self.root/'after'
        self.before.mkdir();self.after.mkdir()
        self.fixed=(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat()
        self.start=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
        self.manifest={'sourceCommit':'a'*40,'expectedBackend':'/release/baseline','baseInventory':{'x':'1'*64},
                       'files':{'x':'2'*64},'environmentHashes':{'api':'3'*64}}
        categories=['original','variant','independent_holdout','normal','permission']
        self.prereg={'group':'G6','fixed_at':self.fixed,'version':'v2','repetitions':2,
                     'criteria':{key:'fixed '+key for key in ('acquisition','analysis','completion','normal','permission','rates')},'samples':[]}
        self.verdicts={'review':{'mechanism':'general mechanism','root_cause_evidence':'actual baseline evidence',
                               'applicable_scope':'all ranking queries','excluded_boundaries':'causal claims',
                               'anti_case_specialization':{'status':'passed','reviewed_diff_sha256':'e'*64,'findings':[],
                                 'review_notes':'independent full diff review','reviewed_surfaces':['code','prompts','config','data_mappings']}},'trials':{'before':{},'after':{}}}
        for i,category in enumerate(categories):
            sample={'id':category,'category':category,'used_for_design':category!='independent_holdout',
                    'input_sha256':str(i+4)*64,'transformation':'changed names and wording' if category=='variant' else ''}
            self.prereg['samples'].append(sample)
            keys=['normal','completion'] if category=='normal' else ['permission','completion'] if category=='permission' else ['acquisition','analysis','completion']
            for phase,directory in [('before',self.before),('after',self.after)]:
                self.verdicts['trials'][phase][category]={}
                for repeat in (1,2):
                    outcome='failed' if phase=='before' and category not in ('normal','permission') else 'passed'
                    self.verdicts['trials'][phase][category][str(repeat)]={'criteria':{key:outcome for key in keys},'notes':'Independent judgment with matched scope and evidence'}
                    raw={'sample_id':category,'category':category,'repeat':repeat,'version':('baseline' if phase=='before' else 'candidate')+'-v2',
                         'source':'/release/baseline' if phase=='before' else '/release/candidate','observed_at':self.start,
                         'input_sha256':sample['input_sha256'],'model_config_sha256':'f'*64,'prompt_sha256':('9' if phase=='before' else '0')*64,
                         'conditions':{'model_config_sha256':'f'*64,'timeout_seconds':480,'source_access':'public_read'},
                         'duration_seconds':2.25,'cost':{'tool_calls':1,'provider_tokens':None,'provider_cost':None,'provider_cost_unit':None},
                         'calls':[{'result':'not exported'}],'answers':['private answer'], 'terminal':'completed'}
                    raw['conditions_sha256']=b.w.digest(raw['conditions'])
                    trial_path=directory/f'{category}-{repeat}.json'
                    trial_path.write_text(json.dumps(raw))
                    self.verdicts['trials'][phase][category][str(repeat)]['receipt_sha256']=b.w.file_sha(trial_path)

    def build(self):
        return b.build(self.prereg,self.manifest,self.verdicts,self.before,self.after,'d'*40,'e'*64,'/release/candidate')

    def test_measured_truthful_record_passes_gate_and_preserves_preregistration(self):
        record=self.build();self.assertEqual(record['status'],'passed')
        proof=record['groups']['G6'];self.assertEqual(proof['preregistration']['criteria'],self.prereg['criteria'])
        run=proof['pairs']['original']['before']['runs'][0]
        self.assertEqual(run['outcome'],'failed')
        self.assertEqual(run['evidence_sha256'],b.w.file_sha(self.before/'original-1.json'))
        self.assertEqual(run['observed_at'],b.w.timestamp((datetime.fromisoformat(self.start)+timedelta(seconds=2.25)).isoformat()))
        self.assertEqual(run['config_sha256'],b.w.digest(self.manifest['environmentHashes']))
        self.assertEqual(proof['pairs']['original']['after']['summary']['cost']['provider_cost'],None)
        self.assertNotIn('private answer',json.dumps(record))
        self.assertNotIn('not exported',json.dumps(record))

    def test_actual_failure_is_preserved_and_not_marked_passed(self):
        self.verdicts['trials']['after']['original']['1']['criteria']['analysis']='failed'
        record=self.build();self.assertEqual(record['status'],'unverified')
        self.assertEqual(record['groups']['G6']['pairs']['original']['after']['summary']['pass_rate'],0.5)

    def test_missing_extra_or_malformed_verdict_refuses_output(self):
        for mutation in ('missing','extra','notes','criteria'):
            with self.subTest(mutation=mutation):
                saved=copy.deepcopy(self.verdicts)
                if mutation=='missing': del self.verdicts['trials']['after']['original']['1']
                elif mutation=='extra': self.verdicts['trials']['after']['original']['3']=saved['trials']['after']['original']['1']
                elif mutation=='notes': del self.verdicts['trials']['after']['original']['1']['notes']
                else: self.verdicts['trials']['after']['original']['1']['criteria']['invented']='passed'
                with self.assertRaises(b.w.WorkflowError): self.build()
                self.verdicts=saved

    def test_missing_extra_wrong_source_hash_or_terminal_trial_rejected(self):
        path=self.after/'original-1.json';original=path.read_text()
        for mutation in ('missing','extra','source','input','conditions','terminal'):
            with self.subTest(mutation=mutation):
                raw=json.loads(original)
                if mutation=='missing': path.unlink()
                elif mutation=='extra': (self.after/'unknown-1.json').write_text(original)
                else:
                    if mutation=='source': raw['source']='/wrong/source'
                    elif mutation=='input': raw['input_sha256']='c'*64
                    elif mutation=='conditions': raw['conditions_sha256']='c'*64
                    else: raw['terminal']='failed';raw['answers']=[]
                    path.write_text(json.dumps(raw))
                    self.verdicts['trials']['after']['original']['1']['receipt_sha256']=b.w.file_sha(path)
                with self.assertRaises(b.w.WorkflowError): self.build()
                path.write_text(original)
                self.verdicts['trials']['after']['original']['1']['receipt_sha256']=b.w.file_sha(path)
                (self.after/'unknown-1.json').unlink(missing_ok=True)

    def test_no_mutation_of_inputs_and_private_atomic_output(self):
        prereg=copy.deepcopy(self.prereg);verdicts=copy.deepcopy(self.verdicts)
        record=self.build();b.write_private(self.root/'evidence.json',record)
        self.assertEqual(self.prereg,prereg);self.assertEqual(self.verdicts,verdicts)
        self.assertEqual((self.root/'evidence.json').stat().st_mode&0o777,0o600)
        with self.assertRaises(b.w.WorkflowError): b.write_private(self.root/'evidence.json',{'changed':True})

    def test_failed_terminal_with_failed_completion_is_retained(self):
        path=self.after/'original-1.json';raw=json.loads(path.read_text())
        raw.update(terminal='failed',answers=[]);path.write_text(json.dumps(raw))
        self.verdicts['trials']['after']['original']['1']['receipt_sha256']=b.w.file_sha(path)
        self.verdicts['trials']['after']['original']['1']['criteria']['completion']='failed'
        record=self.build()
        self.assertEqual(record['status'],'unverified')
        self.assertEqual(record['groups']['G6']['pairs']['original']['after']['runs'][0]['criteria']['completion'],'failed')

    def test_consistent_per_trial_cost_and_retired_versions_cannot_be_relabelled(self):
        path=self.after/'original-1.json';original=path.read_text()
        for field,value in [('version','candidate-v1'),('cost',{'tool_calls':99,'provider_tokens':None,'provider_cost':None,'provider_cost_unit':None})]:
            raw=json.loads(original);raw[field]=value;path.write_text(json.dumps(raw))
            with self.assertRaises(b.w.WorkflowError): self.build()
        path.write_text(original)

    def test_existing_same_output_is_private_and_symlinks_rejected(self):
        record=self.build();path=self.root/'same.json'
        b.write_private(path,record);path.chmod(0o644);b.write_private(path,record)
        self.assertEqual(path.stat().st_mode&0o777,0o600)
        link=self.root/'linked.json';link.symlink_to(path)
        with self.assertRaises(b.w.WorkflowError): b.write_private(link,record)

    def alias_fixture(self):
        for path in self.before.glob('*.json'):
            raw=json.loads(path.read_text());raw['source']='/opt/chickenbro';path.write_text(json.dumps(raw))
            self.verdicts['trials']['before'][raw['sample_id']][str(raw['repeat'])]['receipt_sha256']=b.w.file_sha(path)
        return {'alias':'/opt/chickenbro','resolved':self.manifest['expectedBackend'],'source_sha':'d'*40,
                'before_observed_at':self.fixed,'after_observed_at':b.w.utc_now(),
                'before_inventory_sha256':b.w.digest(self.manifest['baseInventory']),
                'after_inventory_sha256':b.w.digest(self.manifest['baseInventory'])}

    def build_alias(self,proof,alias='/opt/chickenbro'):
        return b.build(self.prereg,self.manifest,self.verdicts,self.before,self.after,'d'*40,'e'*64,
                       '/release/candidate',baseline_source=alias,baseline_alias_proof=proof)

    def test_verified_fixed_alias_retains_actual_runtime_and_raw_hash(self):
        proof=self.alias_fixture();path=self.before/'original-1.json';raw=path.read_bytes()
        with self.assertRaises(b.w.WorkflowError): self.build()
        record=self.build_alias(proof);self.assertEqual(record['status'],'passed')
        run=record['groups']['G6']['pairs']['original']['before']['runs'][0]
        self.assertEqual(run['runtime_id'],'/opt/chickenbro')
        self.assertEqual(run['evidence_sha256'],b.w.file_sha(path))
        self.assertEqual(path.read_bytes(),raw)
        self.assertEqual(record['baseline_alias_proof_sha256'],b.w.digest(proof))

    def test_alias_requires_proof_exact_identity_inventory_and_time_bracket(self):
        original=self.alias_fixture()
        for mutation in ('missing','before_hash','after_hash','start','finish','resolved','source_sha','proof_alias','arbitrary_alias'):
            with self.subTest(mutation=mutation):
                proof=copy.deepcopy(original);alias='/opt/chickenbro'
                if mutation=='missing': proof=None
                elif mutation in ('before_hash','after_hash'): proof[mutation.split('_')[0]+'_inventory_sha256']='0'*64
                elif mutation=='start': proof['before_observed_at']=b.w.utc_now()
                elif mutation=='finish': proof['after_observed_at']=self.start
                elif mutation=='resolved': proof['resolved']='/wrong/target'
                elif mutation=='source_sha': proof['source_sha']='0'*40
                elif mutation=='proof_alias': proof['alias']='/arbitrary'
                else: alias='/arbitrary'
                with self.assertRaises(b.w.WorkflowError): self.build_alias(proof,alias)

    def test_verdict_is_bound_to_exact_original_trial_bytes(self):
        path=self.after/'original-1.json';original=path.read_text()
        for mutation in ('missing_receipt','wrong_receipt','answer','calls_and_cost','format_only'):
            with self.subTest(mutation=mutation):
                verdict=self.verdicts['trials']['after']['original']['1'];saved=copy.deepcopy(verdict)
                if mutation=='missing_receipt': del verdict['receipt_sha256']
                elif mutation=='wrong_receipt': verdict['receipt_sha256']='0'*64
                elif mutation=='format_only': path.write_text(original+'\n')
                else:
                    raw=json.loads(original)
                    if mutation=='answer': raw['answers']=['Different answer not evaluated by reviewer']
                    else: raw['calls'].append({'result':'new evidence'});raw['cost']['tool_calls']+=1
                    path.write_text(json.dumps(raw))
                with self.assertRaises(b.w.WorkflowError): self.build()
                path.write_text(original);self.verdicts['trials']['after']['original']['1']=saved

if __name__=='__main__':unittest.main()

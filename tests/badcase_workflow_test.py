"""Real private-state behavior; subprocess boundaries are injected for offline checks."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'scripts/badcase_workflow.py'
spec = importlib.util.spec_from_file_location('badcase_workflow', MODULE)
w = importlib.util.module_from_spec(spec) if spec else None
if MODULE.exists():
    spec.loader.exec_module(w)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(hasattr(w, 'Workflow'), 'private workflow implementation required')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / 'state'
        self.flow = w.Workflow(self.root)

    def row(self, i=1):
        return dict(run_id=f'00000000-0000-0000-0000-{i:012d}',
                    feedback_at='2026-09-09T01:00:00.000000Z',
                    conversation_id='10000000-0000-0000-0000-000000000000',
                    question='exact private question', answer='exact private answer',
                    runtime_revision='runtime:original', context=[{'role':'user','content':'prior'}],
                    context_total=1)

    def test_scan_deduplicates_equal_timestamp_pages_and_retains_exact_pair(self):
        calls = []
        def fetch(cursor, limit):
            calls.append(cursor)
            return [self.row(i) for i in range(1, 4) if cursor is None or self.row(i)['run_id'] > cursor[1]][:limit]
        self.assertEqual(self.flow.scan(fetch, limit=2)['new'], 2)
        self.assertEqual(self.flow.scan(fetch, limit=2)['new'], 1)
        self.assertEqual(self.flow.scan(fetch, limit=2)['new'], 0)
        self.assertEqual(len(self.flow.state()['seen']), 3)
        packet = json.loads(next((self.root/'raw').glob('*.json')).read_text())
        self.assertEqual(packet['question'], 'exact private question')
        self.assertEqual(packet['answer'], 'exact private answer')
        self.assertEqual(packet['runtime_revision'], 'runtime:original')
        self.assertNotIn('private question', json.dumps(self.flow.status()))

    def test_failure_does_not_advance_cursor_and_retry_recovers_written_packets(self):
        original = self.flow.write
        def fail_state(name, data, **kwargs):
            if name == 'state.json':
                raise OSError('disk full')
            return original(name, data, **kwargs)
        with patch.object(self.flow, 'write', side_effect=fail_state):
            with self.assertRaises(OSError): self.flow.scan(lambda *_: [self.row()])
        self.assertIsNone(self.flow.state()['cursor'])
        self.assertEqual(self.flow.scan(lambda *_: [self.row()])['new'], 1)
        self.assertEqual(self.flow.scan(lambda *_: [self.row()])['new'], 0)

    def test_scan_rejects_invalid_order_oversize_and_untrusted_fields(self):
        for rows in ([self.row(2), self.row(1)], [dict(self.row(), run_id='../escape')], [self.row()]*101):
            with self.assertRaises(w.WorkflowError): self.flow.scan(lambda *_: rows)
            self.assertIsNone(self.flow.state()['cursor'])
        row = dict(self.row(), access_token='secret', reasoning='internal')
        self.flow.scan(lambda *_: [row])
        raw = next((self.root/'raw').glob('*.json')).read_text()
        self.assertNotIn('secret', raw)
        self.assertNotIn('internal', raw)

    def test_lock_and_private_modes_and_symlink_rejection(self):
        with self.flow.lock('scan'):
            with self.assertRaises(w.WorkflowError): self.flow.scan(lambda *_: [])
        self.flow.scan(lambda *_: [self.row()])
        for path in [self.root, *self.root.rglob('*')]:
            self.assertEqual(path.stat().st_mode & 0o777, 0o700 if path.is_dir() else 0o600)
        (self.root/'escape').symlink_to(Path(self.tmp.name))
        with self.assertRaises(w.WorkflowError): self.flow.write('escape/file.json', {})
        with self.assertRaises(w.WorkflowError): self.flow.write('../file.json', {})

    def test_retention_preserves_dedup_and_redacted_report(self):
        self.flow.scan(lambda *_: [self.row()], now=100)
        self.flow.prune(now=100 + 8*86400)
        self.assertEqual(list((self.root/'raw').glob('*.json')), [])
        self.assertEqual(len(self.flow.state()['seen']), 1)
        self.assertEqual(self.flow.scan(lambda *_: [self.row()])['new'], 0)

    def test_query_readonly_owner_scoped_context_cutoff(self):
        sql = w.scan_sql(None, 100)
        self.assertIn('BEGIN READ ONLY', sql)
        self.assertIn('LIMIT 100', sql)
        self.assertIn('m.user_id = r.user_id', sql)
        self.assertIn('(m.created_at, m.id) < (q.created_at, q.id)', sql)
        self.assertNotIn('access_token', sql)
        with self.assertRaises(w.WorkflowError): w.scan_sql(['bad\'; DROP', 'bad'], 100)

    def generalization_group(self, identity):
        categories=('original','variant','independent_holdout','normal','permission')
        fixed=w.utc_now()
        criteria={'complete':'Answer meets bounded requested scope with supporting sources'}
        assignment={category:dict(category=category,input_sha256=str(i+1)*64,
                    used_for_design=category != 'independent_holdout',
                    transformation='changed unrelated names and wording' if category == 'variant' else '',
                    criterion_ids=['complete']) for i,category in enumerate(categories)}
        prereg=dict(fixed_at=fixed,criteria=criteria,assignments=assignment,
                    minimum_repetitions=2,minimum_after_pass_rate=1.0,model_stochastic=True)
        pairs={}
        for category in categories:
            pair={}
            for phase in ('before','after'):
                outcome='failed' if phase == 'before' and category not in ('normal','permission') else 'passed'
                runs=[dict(trial_id=f'{category}-{phase}-{repeat}',observed_at=w.utc_now(),source_sha=identity['baseline_sha'] if phase=='before' else identity['source_sha'],
                    config_sha256='3'*64 if phase=='before' else identity['config_sha256'],
                    prompt_sha256='4'*64 if phase=='before' else '5'*64,runtime_id=phase+'-runtime',
                    conditions_sha256='6'*64,model_config_sha256='7'*64,
                    input_sha256=assignment[category]['input_sha256'],outcome=outcome,
                    criteria={'complete':outcome},duration_seconds=1.5,evidence_sha256=w.digest({'category':category,'phase':phase,'repeat':repeat}),
                    cost=dict(counter_scope='source_gateway_only',tool_calls=1,provider_tokens=None,provider_cost=None,provider_cost_unit=None)) for repeat in range(2)]
                pair[phase]={'runs':runs,'summary':dict(passed=2 if outcome=='passed' else 0,total=2,
                    pass_rate=1.0 if outcome=='passed' else 0.0,duration_seconds=3.0,
                    cost=dict(counter_scope='source_gateway_only',tool_calls=2,provider_tokens=None,provider_cost=None,provider_cost_unit=None))}
            pairs[category]=pair
        return dict(mechanism='missing general query entry',root_cause_evidence='baseline bounded query fails',
                    applicable_scope='ranking discovery',excluded_boundaries='no guaranteed combat conclusion',
                    anti_case_specialization=dict(status='passed',reviewed_diff_sha256=identity['diff_sha256'],
                        findings=[],review_notes='Reviewed code prompts config and mappings; no case selectors',
                        reviewed_surfaces=['code','prompts','config','data_mappings']),
                    preregistration=prereg,preregistration_sha256=w.digest(prereg),
                    baseline_config_sha256='3'*64,before_prompt_sha256='4'*64,after_prompt_sha256='5'*64,
                    conditions_sha256='6'*64,model_config_sha256='7'*64,pairs=pairs)

    def prepared(self):
        self.flow.scan(lambda *_: [self.row()])
        group = self.flow.group('G1', [self.row()['run_id']], 'rankings query', 'scope-v1')
        self.flow.decide('G1', group['report_sha256'], 'approved', 'user task message 2026-09-09')
        identity = dict(source_sha='a'*40, build_sha256='b'*64, config_sha256='c'*64,
                        baseline_sha='d'*40, diff_sha256='e'*64)
        manifest = dict(identity, groups={'G1':group['report_sha256']}, backend_only=True,
                        excluded_impacts=[], created_at=w.utc_now(), evidence={})
        for kind in w.EVIDENCE_KINDS:
            record = dict(identity, kind=kind, status='passed', observed_at=w.utc_now(),
                          details='actual verification evidence', checks={name:True for name in w.CHECKS[kind]})
            if kind == 'generalization':
                record['groups'] = {'G1': self.generalization_group(identity)}
                record['observed_at'] = w.utc_now()
            if kind == 'rollback':
                record['rollback_identity'] = dict(source_sha='d'*40, artifact_sha256='1'*64, config_sha256='2'*64)
            evidence_path = Path(self.tmp.name)/f'{kind}.json'
            evidence_path.write_text(json.dumps(record))
            manifest['evidence'][kind] = {'path':str(evidence_path), 'sha256':w.file_sha(evidence_path)}
        return manifest

    def test_approval_report_version_bound_and_no_empty_batch(self):
        with self.assertRaises(w.WorkflowError): self.flow.freeze({'groups':{}})
        self.flow.scan(lambda *_: [self.row()])
        g = self.flow.group('G1', [self.row()['run_id']], 'rankings', 'v1')
        with self.assertRaises(w.WorkflowError): self.flow.decide('G1', 'f'*64, 'approved', 'user')
        self.flow.decide('G1', g['report_sha256'], 'approved', 'user')
        self.flow.group('G1', [self.row()['run_id']], 'rankings', 'v2')
        self.assertNotEqual(self.flow.state()['groups']['G1']['decision'], 'approved')

    def test_freeze_rejects_missing_tampered_stale_wrong_sha_or_unsafe_evidence(self):
        good = self.prepared()
        for mutation in ('missing','tampered','source','scope','stale'):
            bad = copy.deepcopy(good)
            if mutation == 'missing': del bad['evidence']['candidate']
            elif mutation == 'tampered': bad['evidence']['review']['sha256']='f'*64
            elif mutation == 'source': bad['source_sha']='f'*40
            elif mutation == 'scope': bad['excluded_impacts']=['identity']
            else: bad['created_at']='2020-01-01T00:00:00Z'
            with self.subTest(mutation=mutation), self.assertRaises(w.WorkflowError): self.flow.freeze(bad)

    def test_release_requires_live_evidence_no_blind_retry_and_baseline_drift(self):
        manifest = self.prepared()
        batch = self.flow.freeze(manifest)
        calls=[]
        def executor(mode, data):
            calls.append(mode)
            if mode == 'preflight': return dict(batch_sha256=batch, baseline_sha='0'*40, clean=True, diff_sha256='e'*64)
            return {}
        with self.assertRaises(w.WorkflowError): self.flow.release(batch, executor)
        self.assertEqual(calls, ['preflight'])
        def incomplete(mode, data):
            if mode == 'preflight': return dict(batch_sha256=batch, baseline_sha='d'*40, clean=True, diff_sha256='e'*64)
            return {'status':'passed'}
        with self.assertRaises(w.WorkflowError): self.flow.release(batch, incomplete)
        with self.assertRaises(w.WorkflowError): self.flow.release(batch, incomplete)
        self.assertEqual(self.flow.state()['releases'][batch]['status'], 'failed')

    def test_release_success_is_noop_on_repeat_and_batch_immutable(self):
        batch=self.flow.freeze(self.prepared())
        calls=[]
        def executor(mode, data):
            calls.append(mode)
            if mode == 'preflight': return dict(batch_sha256=batch, baseline_sha='d'*40, clean=True, diff_sha256='e'*64)
            return dict(batch_sha256=batch, source_sha='a'*40, build_sha256='b'*64,
                        config_sha256='c'*64, status='passed', observed_at=w.utc_now(),
                        checks={key:True for key in w.LIVE_CHECKS})
        self.assertEqual(self.flow.release(batch, executor)['status'], 'released')
        self.assertEqual(self.flow.release(batch, executor)['status'], 'released')
        self.assertEqual(calls, ['preflight','release'])
        with self.assertRaises(w.WorkflowError): self.flow.write(f'batches/{batch}.json', {'changed':True}, immutable=True)

    def test_release_does_not_hold_state_lock_during_executor(self):
        batch = self.flow.freeze(self.prepared())
        def executor(mode, envelope):
            self.flow.scan(lambda *_: [])
            if mode == 'preflight':
                return dict(batch_sha256=batch, baseline_sha='d'*40, clean=True, diff_sha256='e'*64)
            return dict(batch_sha256=batch, source_sha='a'*40, build_sha256='b'*64,
                        config_sha256='c'*64, status='passed', observed_at=w.utc_now(),
                        checks={key:True for key in w.LIVE_CHECKS})
        self.assertEqual(self.flow.release(batch, executor)['status'], 'released')

    def test_missing_check_unapproved_group_and_tampered_frozen_batch_rejected(self):
        manifest = self.prepared()
        evidence = Path(manifest['evidence']['candidate']['path'])
        original = evidence.read_text()
        data = json.loads(original)
        data['checks']['real_chat_terminal'] = False
        evidence.write_text(json.dumps(data))
        manifest['evidence']['candidate']['sha256'] = w.file_sha(evidence)
        with self.assertRaises(w.WorkflowError): self.flow.freeze(manifest)
        evidence.write_text(original)
        manifest['evidence']['candidate']['sha256'] = w.file_sha(evidence)
        batch = self.flow.freeze(manifest)
        self.flow.decide('G1', manifest['groups']['G1'], 'deferred', 'user deferred')
        with self.assertRaises(w.WorkflowError): self.flow.release(batch, lambda *_: self.fail('must not execute'))
        self.flow.decide('G1', manifest['groups']['G1'], 'approved', 'user approved')
        self.flow.write(f'batches/{batch}.json', {'malicious':'replacement'})
        with self.assertRaises(w.WorkflowError): self.flow.release(batch, lambda *_: self.fail('must not execute'))

    def test_expired_evidence_and_live_wrong_identity_rejected(self):
        manifest = self.prepared()
        evidence = Path(manifest['evidence']['tests']['path'])
        data = json.loads(evidence.read_text())
        data['observed_at']='2020-01-01T00:00:00Z'
        evidence.write_text(json.dumps(data))
        manifest['evidence']['tests']['sha256']=w.file_sha(evidence)
        with self.assertRaises(w.WorkflowError): self.flow.freeze(manifest)
        batch = self.flow.freeze(self.prepared())
        def executor(mode, envelope):
            if mode == 'preflight': return dict(batch_sha256=batch,baseline_sha='d'*40,clean=True,diff_sha256='e'*64)
            return dict(batch_sha256=batch, source_sha='0'*40, build_sha256='b'*64,
                        config_sha256='c'*64,status='passed',observed_at=w.utc_now(),
                        checks={key:True for key in w.LIVE_CHECKS})
        with self.assertRaises(w.WorkflowError): self.flow.release(batch, executor)

    def test_fixed_executor_uses_json_stdin_and_refuses_drift(self):
        executable = Path(self.tmp.name)/'executor'
        executable.write_text('#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps({"mode":sys.argv[1], "data":json.load(sys.stdin)}))\n')
        executable.chmod(0o700)
        execute = w.external_executor(executable.absolute(), w.file_sha(executable))
        payload = {'question':'$(touch /tmp/never-execute) `id`; exit 7'}
        self.assertEqual(execute('preflight', payload), {'mode':'preflight','data':payload})
        executable.write_text('#!/bin/sh\nexit 0\n')
        with self.assertRaises(w.WorkflowError): execute('release', payload)

    def test_failed_source_cannot_retry_by_refreezing_new_timestamp(self):
        manifest=self.prepared()
        batch=self.flow.freeze(manifest)
        def executor(mode, data):
            if mode == 'preflight': return dict(batch_sha256=batch,baseline_sha='d'*40,clean=True,diff_sha256='e'*64)
            raise w.WorkflowError('execution failed')
        with self.assertRaises(w.WorkflowError): self.flow.release(batch, executor)
        manifest['created_at']=w.utc_now()
        again=self.flow.freeze(manifest)
        with self.assertRaises(w.WorkflowError): self.flow.release(again, lambda *_: self.fail('must not repeat failed source'))

    def test_rollback_identity_required_and_preexisting_live_proof_rejected(self):
        manifest=self.prepared()
        path=Path(manifest['evidence']['rollback']['path'])
        record=json.loads(path.read_text())
        del record['rollback_identity']
        path.write_text(json.dumps(record))
        manifest['evidence']['rollback']['sha256']=w.file_sha(path)
        with self.assertRaises(w.WorkflowError): self.flow.freeze(manifest)
        manifest=self.prepared()
        batch=self.flow.freeze(manifest)
        old=w.utc_now()
        def executor(mode, data):
            if mode == 'preflight': return dict(batch_sha256=batch,baseline_sha='d'*40,clean=True,diff_sha256='e'*64)
            return dict(batch_sha256=batch, source_sha='a'*40,build_sha256='b'*64,config_sha256='c'*64,
                        status='passed',observed_at=old,checks={key:True for key in w.LIVE_CHECKS})
        with self.assertRaises(w.WorkflowError): self.flow.release(batch,executor)

    def test_status_lists_frozen_ready_and_revoked_batches(self):
        manifest=self.prepared()
        batch=self.flow.freeze(manifest)
        self.assertEqual(self.flow.status()['batches'][batch]['status'], 'eligible')
        self.flow.decide('G1',manifest['groups']['G1'],'deferred','user deferred')
        self.assertEqual(self.flow.status()['batches'][batch]['status'], 'ineligible')
        self.assertNotIn('private question',json.dumps(self.flow.status()))

    def test_slow_scan_allows_release_and_merges_its_terminal_state(self):
        batch=self.flow.freeze(self.prepared())
        def executor(mode,data):
            if mode == 'preflight': return dict(batch_sha256=batch,baseline_sha='d'*40,clean=True,diff_sha256='e'*64)
            return dict(batch_sha256=batch, source_sha='a'*40,build_sha256='b'*64,config_sha256='c'*64,
                        status='passed',observed_at=w.utc_now(),checks={key:True for key in w.LIVE_CHECKS})
        def fetch(*_):
            self.assertEqual(self.flow.release(batch,executor)['status'],'released')
            return [self.row(2)]
        self.assertEqual(self.flow.scan(fetch)['new'],1)
        state=self.flow.state()
        self.assertEqual(state['releases'][batch]['status'],'released')
        self.assertEqual(len(state['seen']),2)

    def test_release_finalization_waits_for_brief_state_writer(self):
        batch=self.flow.freeze(self.prepared())
        locked=threading.Event()
        threads=[]
        def writer():
            with self.flow.lock('state'):
                locked.set()
                time.sleep(0.15)
        def executor(mode,data):
            if mode == 'preflight': return dict(batch_sha256=batch,baseline_sha='d'*40,clean=True,diff_sha256='e'*64)
            thread=threading.Thread(target=writer)
            threads.append(thread); thread.start()
            self.assertTrue(locked.wait(2))
            return dict(batch_sha256=batch, source_sha='a'*40,build_sha256='b'*64,config_sha256='c'*64,
                        status='passed',observed_at=w.utc_now(),checks={key:True for key in w.LIVE_CHECKS})
        try:
            self.assertEqual(self.flow.release(batch,executor)['status'],'released')
        finally:
            for thread in threads: thread.join(2)

    def test_periodic_reconciliation_recovers_late_commits_and_pages_past_duplicates(self):
        rows=[self.row(i) for i in range(2,8)]
        def fetch(cursor,limit):
            return [r for r in rows if cursor is None or [r['feedback_at'],r['run_id']] > cursor][:limit]
        for _ in range(4): self.flow.scan(fetch,limit=2)
        # A transaction created the feedback timestamp earlier but commits only now.
        rows.insert(0,self.row(1))
        for _ in range(16): self.flow.scan(fetch,limit=2)
        self.assertEqual(len(self.flow.state()['seen']),7)
        self.assertEqual(self.flow.state()['cursor'][1],self.row(7)['run_id'])
        self.assertEqual(self.flow.scan(fetch,limit=2)['new'],0)

    def test_state_lock_wait_is_bounded(self):
        with self.flow.lock('state'):
            started=time.monotonic()
            with self.assertRaises(w.WorkflowError):
                with self.flow.lock('state',timeout=0.05): self.fail('lock should stay exclusive')
            self.assertLess(time.monotonic()-started,0.5)

    def test_scan_preserves_approval_changes_and_reconciliation_failure_retries_same_page(self):
        manifest=self.prepared()
        def fetch(*_):
            self.flow.decide('G1',manifest['groups']['G1'],'deferred','user deferred while scan reads')
            with self.assertRaises(w.WorkflowError): self.flow.scan(lambda *_: [])
            return []
        self.flow.scan(fetch)
        self.assertEqual(self.flow.state()['groups']['G1']['decision'],'deferred')
        for _ in range(5): self.flow.scan(lambda *_: [])
        before=self.flow.state()
        def fail(*_): raise OSError('network unavailable')
        with self.assertRaises(OSError): self.flow.scan(fail)
        self.assertEqual(self.flow.state(),before)
        seen_cursors=[]
        def retry(cursor,limit):
            seen_cursors.append(cursor)
            return [self.row()]
        self.assertEqual(self.flow.scan(retry)['mode'],'reconciliation')
        self.assertEqual(seen_cursors,[None])

    def test_generalization_gate_rejects_missing_kind(self):
        manifest=self.prepared()
        manifest['evidence'].pop('generalization',None)
        with self.assertRaises(w.WorkflowError): self.flow.freeze(manifest)

    def test_generalization_rejects_unregistered_specialized_or_regressing_samples(self):
        mutations=('missing_variant','missing_holdout','used_holdout','late_fixed','specialization',
                   'failed_acceptance','normal_regression','permission_regression','wrong_conditions',
                   'wrong_source','missing_repeat','false_rate','missing_cost','same_variant','tampered_prereg')
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                manifest=self.prepared()
                self.assertIn('generalization',manifest['evidence'],'generalization evidence kind required')
                path=Path(manifest['evidence']['generalization']['path'])
                record=json.loads(path.read_text()); proof=record['groups']['G1']
                registration=proof['preregistration']
                if mutation=='missing_variant': del proof['pairs']['variant']
                elif mutation=='missing_holdout': del proof['pairs']['independent_holdout']
                elif mutation=='used_holdout': registration['assignments']['independent_holdout']['used_for_design']=True
                elif mutation=='late_fixed': registration['fixed_at']='2099-01-01T00:00:00Z'
                elif mutation=='specialization': proof['anti_case_specialization']['findings']=['hardcoded report id']
                elif mutation in ('failed_acceptance','normal_regression','permission_regression'):
                    category={'failed_acceptance':'original','normal_regression':'normal','permission_regression':'permission'}[mutation]
                    phase='after' if mutation=='failed_acceptance' else 'before'
                    trial=proof['pairs'][category][phase]['runs'][0]
                    trial['outcome']='failed';trial['criteria']['complete']='failed'
                elif mutation=='wrong_conditions': proof['pairs']['original']['before']['runs'][0]['conditions_sha256']='0'*64
                elif mutation=='wrong_source': proof['pairs']['variant']['after']['runs'][0]['source_sha']='0'*40
                elif mutation=='missing_repeat': proof['pairs']['independent_holdout']['after']['runs'].pop()
                elif mutation=='false_rate': proof['pairs']['original']['before']['summary']['pass_rate']=1
                elif mutation=='missing_cost': del proof['pairs']['original']['after']['runs'][0]['cost']
                elif mutation=='same_variant': registration['assignments']['variant']['input_sha256']=registration['assignments']['original']['input_sha256']
                elif mutation=='tampered_prereg': proof['preregistration_sha256']='0'*64
                if mutation!='tampered_prereg': proof['preregistration_sha256']=w.digest(registration)
                path.write_text(json.dumps(record));manifest['evidence']['generalization']['sha256']=w.file_sha(path)
                with self.assertRaises(w.WorkflowError): self.flow.freeze(manifest)

    def test_generalization_rejects_truthfully_reported_regression_and_reused_holdout(self):
        for mutation in ('normal','permission','after_failed','reused_holdout','counter_scope'):
            with self.subTest(mutation=mutation):
                manifest=self.prepared();path=Path(manifest['evidence']['generalization']['path'])
                record=json.loads(path.read_text());proof=record['groups']['G1']
                if mutation=='reused_holdout':
                    assignments=proof['preregistration']['assignments']
                    assignments['independent_holdout']['input_sha256']=assignments['variant']['input_sha256']
                    proof['preregistration_sha256']=w.digest(proof['preregistration'])
                    for phase in ('before','after'):
                        for trial in proof['pairs']['independent_holdout'][phase]['runs']:
                            trial['input_sha256']=assignments['variant']['input_sha256']
                elif mutation=='counter_scope':
                    for trial in proof['pairs']['normal']['after']['runs']: trial['cost']['counter_scope']='all_tools'
                    proof['pairs']['normal']['after']['summary']['cost']['counter_scope']='all_tools'
                else:
                    category='original' if mutation=='after_failed' else mutation
                    phase='after' if mutation=='after_failed' else 'before'
                    observed=proof['pairs'][category][phase]
                    for trial in observed['runs']:
                        trial['outcome']='failed';trial['criteria']['complete']='failed'
                    observed['summary'].update(passed=0,pass_rate=0)
                path.write_text(json.dumps(record));manifest['evidence']['generalization']['sha256']=w.file_sha(path)
                with self.assertRaises(w.WorkflowError): self.flow.freeze(manifest)

    def test_generalization_rejects_duplicate_execution_or_receipt_across_all_samples(self):
        for mutation in ('same_trial','same_receipt','copied_run','other_phase','other_sample','missing_trial','oversize_trial'):
            with self.subTest(mutation=mutation):
                manifest=self.prepared();path=Path(manifest['evidence']['generalization']['path'])
                record=json.loads(path.read_text());pairs=record['groups']['G1']['pairs']
                runs=pairs['original']['after']['runs'];first=runs[0]
                if mutation=='same_trial': runs[1]['trial_id']=first['trial_id']
                elif mutation=='same_receipt': runs[1]['evidence_sha256']=first['evidence_sha256']
                elif mutation=='copied_run': runs[1]=copy.deepcopy(first)
                elif mutation=='other_phase': pairs['original']['before']['runs'][0]['trial_id']=first['trial_id']
                elif mutation=='other_sample': pairs['normal']['after']['runs'][0]['evidence_sha256']=first['evidence_sha256']
                elif mutation=='missing_trial': del runs[1]['trial_id']
                else: runs[1]['trial_id']='x'*257
                path.write_text(json.dumps(record));manifest['evidence']['generalization']['sha256']=w.file_sha(path)
                with self.assertRaises(w.WorkflowError): self.flow.freeze(manifest)


if __name__ == '__main__': unittest.main()

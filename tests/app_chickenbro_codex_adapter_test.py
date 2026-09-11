import io
import json
import os
import subprocess
import sys
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from server.app.chickenbro.codex_adapter import CodexStreamError, CodexUnavailable, NativeCodexChatAdapter


def note(method, **params):
    return dict(method=method, params=params)


def item(method, text='', phase='final_answer', identity='answer', kind='agentMessage'):
    return note(method, threadId='thread', turnId='turn', item=dict(id=identity, type=kind, phase=phase, text=text))


def delta(text, identity='answer'):
    return note('item/agentMessage/delta', threadId='thread', turnId='turn', itemId=identity, delta=text)


def transcript(*body, status='completed'):
    return [dict(id=1, result=dict(userAgent='test')), dict(id=2, result=dict(thread=dict(id='thread'))),
            dict(id=3, result=dict(turn=dict(id='turn', status='inProgress'))), *body,
            note('turn/completed', threadId='thread', turn=dict(id='turn', status=status, error=None))]


def answer():
    return transcript(item('item/started'), delta('answer'), item('item/completed', 'answer'))


def replacement(old, new):
    text = json.dumps({'replacements': [{'old': old, 'new': new}]}, ensure_ascii=False)
    return transcript(item('item/started'), delta(text), item('item/completed', text))


class TrackingInput(io.BytesIO):
    def close(self):
        self.written = self.getvalue()
        super().close()


class FakeProcess:
    def __init__(self, events=None, returncode=0, wait_error=None):
        self.stdin = TrackingInput()
        self.stdout = io.BytesIO(b''.join(json.dumps(e).encode() + b'\n' for e in (events or [])))
        self.returncode, self.wait_error, self.killed, self.wait_calls = returncode, wait_error, False, 0
    def wait(self, timeout=None):
        self.wait_calls += 1
        if self.wait_error:
            raise self.wait_error
        return self.returncode
    def kill(self):
        self.killed = True
    def sent(self):
        return [json.loads(line) for line in self.stdin.written.splitlines()]


class Gateway:
    revoked = None
    def issue_capability(self):
        return 'job-capability'
    def revoke(self, token):
        self.revoked = token
    def answer_evidence(self, token):
        return {'reports': [], 'groups': [], 'truncated': False}


class ChickenbroCodexAdapterTest(unittest.TestCase):
    def test_upstream_error_metadata_uses_schema_allowlist_without_error_body(self):
        from server.app.chickenbro import codex_adapter as module
        from types import SimpleNamespace
        secret = 'PRIVATE-UPSTREAM-ERROR'
        for info, expected in [('usageLimitExceeded', 'usageLimitExceeded'),
                               ({'responseStreamDisconnected': {'httpStatusCode': 503, 'message': secret}}, 'responseStreamDisconnected'),
                               (secret, 'unknown'), ({secret: {}}, 'unknown')]:
            events = transcript(note('error', threadId='thread', turnId='turn', willRetry=False,
                error={'codexErrorInfo': info, 'message': secret, 'additionalDetails': secret}))
            with tempfile.TemporaryDirectory() as directory, patch.object(module._LOG, 'warning') as log:
                adapter = NativeCodexChatAdapter(jobs_dir=directory, enabled=True, popen=lambda *a, **k: FakeProcess(events))
                with self.assertRaises(CodexStreamError):
                    list(adapter.stream(prompt=secret, timeout_seconds=2,
                        tool_context=SimpleNamespace(run_id='12345678-1234-1234-1234-123456789abc')))
                row = [json.loads(c.args[1]) for c in log.call_args_list if c.args[0] == 'codex_internal_stage %s'][-1]
                self.assertEqual(row.get('upstream_kind'), expected)
                self.assertEqual(row.get('upstream_http_status'), 503 if expected == 'responseStreamDisconnected' else None)
                self.assertNotIn(secret, str(log.call_args_list))

    def test_native_failure_categories_are_private_and_distinct(self):
        from server.app.chickenbro import codex_adapter as module
        from types import SimpleNamespace
        secret = 'PRIVATE-PROVIDER-TOKEN'
        cases = [([], 'transport_eof'),
                 ([dict(id=1, error=dict(message=secret))], 'rpc_error'),
                 (transcript(status='failed'), 'turn_failed'),
                 (transcript(), 'final_missing'),
                 (transcript(note('error', threadId='other', turnId='turn', willRetry=False)), 'protocol_invalid'),
                 (transcript(note('error', threadId='thread', turnId='turn', willRetry=False,
                                  error=dict(message=secret))), 'upstream_error')]
        for events, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory, patch.object(module._LOG, 'warning') as log:
                adapter = NativeCodexChatAdapter(jobs_dir=directory, enabled=True, popen=lambda *a, **k: FakeProcess(events))
                with self.assertRaises(CodexStreamError) as caught:
                    list(adapter.stream(prompt=secret, timeout_seconds=2,
                        tool_context=SimpleNamespace(run_id='12345678-1234-1234-1234-123456789abc')))
                rows = [json.loads(c.args[1]) for c in log.call_args_list if c.args[0] == 'codex_internal_stage %s']
                self.assertEqual(rows[-1].get('failure_kind'), expected)
                self.assertEqual(caught.exception.code, 'CODEX_OUTPUT_INVALID')
                self.assertNotIn(secret, str(log.call_args_list))
                self.assertNotIn(expected, str(caught.exception))

    def test_invalid_output_records_distinct_private_failure_sites_without_content(self):
        from server.app.chickenbro import codex_adapter as module
        from types import SimpleNamespace
        sites = []
        secret = 'PRIVATE-UPSTREAM-ERROR-PROMPT'
        for events in ([], [dict(id=1, error=dict(message=secret))]):
            with tempfile.TemporaryDirectory() as directory, patch.object(module._LOG, 'warning') as log:
                adapter = NativeCodexChatAdapter(jobs_dir=directory, enabled=True,
                    popen=lambda *a, **k: FakeProcess(events))
                with self.assertRaises(CodexStreamError) as caught:
                    list(adapter.stream(prompt=secret, timeout_seconds=2,
                        tool_context=SimpleNamespace(run_id='12345678-1234-1234-1234-123456789abc')))
                self.assertEqual(caught.exception.code, 'CODEX_OUTPUT_INVALID')
                rows = [json.loads(c.args[1]) for c in log.call_args_list
                        if c.args[0] == 'codex_internal_stage %s']
                site = rows[-1]['failure_site']
                self.assertRegex(site, r'^codex_stdio\.py:[1-9][0-9]{0,5}$')
                sites.append(site)
                self.assertNotIn(secret, str(log.call_args_list))
                self.assertNotIn(directory, str(log.call_args_list))
        self.assertNotEqual(*sites)

    def test_reference_repair_context_selected_only_for_nonempty_pure_url_errors(self):
        from server.app.chickenbro import codex_adapter as module
        with patch.object(module,'_repair_context',return_value='FULL') as full, \
             patch.object(module,'_reference_repair_context',return_value='REFERENCES') as compact:
            for errors in (['WCL_REFERENCE_UNOBSERVED'],['WCL_REFERENCE_MALFORMED','WCL_REFERENCE_UNOBSERVED']):
                self.assertEqual(module._repair_context_for_errors({},errors),'REFERENCES')
            for errors in ([],['WCL_GROUP_OBSERVATION_EMPTY'],['WCL_REFERENCE_UNOBSERVED','WCL_GROUP_OBSERVATION_EMPTY'],['UNKNOWN'],[{}]):
                self.assertEqual(module._repair_context_for_errors({},errors),'FULL')
            self.assertEqual(compact.call_count,2);self.assertEqual(full.call_count,5)

    def test_reference_only_repair_uses_compact_identity_and_preserves_observation_then_revalidates(self):
        from server.app.chickenbro.answer_grounding import collect_evidence
        code='aB3dE5gH7jK9mN2p'
        good='https://www.warcraftlogs.com/reports/'+code+'?fight=7&source=9'
        bad='https://www.warcraftlogs.com/reports/'+'Z'*16+'?fight=7&source=9'
        draft='Observation remains unchanged. [log]('+bad+')'
        corrected=draft.replace(bad,good)
        evidence=collect_evidence({}, {'sourceKey':'warcraftlogs','status':'verified','facts':[{
            'reportCode':code,'fightId':7,'sourceId':9,
            'players':[{'id':9,'name':'Generic Actor','server':'Realm','region':'EU'}],
            'casts':{'entries':[{'name':'OMIT_CAST_BODY','guid':123,'total':4}]}}]})
        gateway=Gateway();gateway.answer_evidence=lambda token:evidence
        original=FakeProcess(transcript(item('item/started'),delta(draft),item('item/completed',draft)))
        repaired=FakeProcess(replacement(bad,good));processes=[original,repaired]
        with tempfile.TemporaryDirectory() as directory:
            adapter=NativeCodexChatAdapter(jobs_dir=directory,enabled=True,source_gateway=gateway,
                popen=lambda *a,**k:processes.pop(0))
            output=list(adapter.stream(prompt='question',timeout_seconds=480))
        self.assertEqual(output,[{'type':'delta','text':corrected},{'type':'completed','text':corrected}])
        payload=json.loads(repaired.sent()[3]['params']['input'][0]['text'])
        self.assertEqual(payload['evidence']['mode'],'reference_correction_only')
        self.assertEqual(payload['evidence']['positiveReferences'],[[code,'7','9']])
        self.assertEqual(payload['evidence']['identityDetails'][0]['player']['name'],'Generic Actor')
        self.assertNotIn('OMIT_CAST_BODY',json.dumps(payload))
        self.assertEqual(gateway.revoked,'job-capability');self.assertEqual(processes,[])
        config=repaired.sent()[2]['params']['config']
        self.assertEqual(config['web_search'],'disabled')
        self.assertFalse(config['features']['shell_tool'])

    def test_incomplete_reference_projection_fails_before_repair_process_and_leaks_no_draft(self):
        gateway=Gateway();gateway.answer_evidence=lambda token:{'referencesTruncated':True,'attemptedWcl':True,'references':[]}
        draft='https://www.warcraftlogs.com/reports/'+'Z'*16+'?fight=7&source=9'
        calls=[]
        def spawn(*a,**k):
            calls.append(True)
            return FakeProcess(transcript(item('item/started'),delta(draft),item('item/completed',draft)))
        with tempfile.TemporaryDirectory() as directory:
            adapter=NativeCodexChatAdapter(jobs_dir=directory,enabled=True,source_gateway=gateway,popen=spawn)
            with self.assertRaises(CodexStreamError) as caught:next(adapter.stream(prompt='q',timeout_seconds=480))
            self.assertEqual(caught.exception.code,'CODEX_OUTPUT_INVALID')
        self.assertEqual(len(calls),1)

    def test_native_web_receipts_are_run_bound_content_free_and_do_not_change_answer(self):
        from server.app.chickenbro import codex_adapter as module
        from types import SimpleNamespace
        secret = 'PRIVATE-QUERY-URL-CONTENT'
        events = [note('item/completed', threadId='thread', turnId='turn',
                  item={'id': str(i), 'type': 'webSearch', 'action': {'type': action, 'query': secret}, 'text': secret})
                  for i, action in enumerate(('search', 'openPage', 'findInPage', secret))]
        process = FakeProcess(transcript(*events, item('item/started'), delta('answer'), item('item/completed', 'answer')))
        run_id = '12345678-1234-1234-1234-123456789abc'
        with tempfile.TemporaryDirectory() as directory, patch.object(module._LOG, 'warning') as log:
            adapter = NativeCodexChatAdapter(jobs_dir=directory, enabled=True, popen=lambda *a, **k: process)
            output = list(adapter.stream(prompt=secret, timeout_seconds=20, tool_context=SimpleNamespace(run_id=run_id)))
        self.assertEqual(output[-1], {'type': 'completed', 'text': 'answer'})
        receipts = [json.loads(c.args[1]) for c in log.call_args_list if c.args[0] == 'codex_native_web_summary %s']
        self.assertEqual(receipts, [{'run_id': run_id, 'completed_events': {'search': 1, 'openPage': 1, 'findInPage': 1, 'other': 1}}])
        self.assertNotIn(secret, str(log.call_args_list))

    def test_internal_diagnostics_are_bounded_allowlisted_and_never_log_content(self):
        from server.app.chickenbro import codex_adapter as module
        secret = 'PRIVATE-PROMPT-PATCH-EXCEPTION'
        with patch.object(module._LOG, 'info') as log:
            diagnostic = module._RunDiagnostics('12345678-1234-1234-1234-123456789abc')
            for _ in range(100):
                diagnostic.emit('validation', validation_codes=['WCL_REFERENCE_UNOBSERVED', secret], code=secret,
                                failure_site=secret, failure_kind=secret)
                diagnostic.emit(secret, code=secret)
            self.assertEqual(log.call_count, 1)
            rendered = str(log.call_args_list)
            self.assertNotIn(secret, rendered)
            self.assertIn('WCL_REFERENCE_UNOBSERVED', rendered)
            module._RunDiagnostics(secret).emit('validation')
            self.assertEqual(log.call_count, 1)
        with patch.object(module._LOG, 'info', side_effect=RuntimeError(secret)), \
             patch.object(module._LOG, 'warning', side_effect=RuntimeError(secret)):
            diagnostic = module._RunDiagnostics('12345678-1234-1234-1234-123456789abc')
            diagnostic.emit('validation')
            diagnostic.emit('stream_failed', code='CODEX_OUTPUT_INVALID')

    def test_failure_diagnostics_visible_at_warning_with_safe_prior_validation_snapshot(self):
        import logging
        from server.app.chickenbro import codex_adapter as module
        records=[]
        class Capture(logging.Handler):
            def emit(self, record):records.append(json.loads(record.args[0]))
        logger=logging.Logger('isolated-diagnostic-test',level=logging.WARNING)
        logger.addHandler(Capture())
        with patch.object(module,'_LOG',logger):
            diagnostic=module._RunDiagnostics('12345678-1234-1234-1234-123456789abc')
            diagnostic.emit('validation',validation_codes=['WCL_REFERENCE_UNOBSERVED','PRIVATE'])
            diagnostic.emit('repair_enter')
            diagnostic.emit('repair_failed',phase='stream',code='CODEX_TIMEOUT')
            diagnostic.emit('stream_failed',code='CODEX_OUTPUT_INVALID')
        self.assertEqual(len(records),2)
        self.assertEqual(records[-1]['validation_codes'],['WCL_REFERENCE_UNOBSERVED'])
        self.assertEqual(records[-1]['repair_phase'],'stream')
        self.assertEqual(records[-1]['repair_code'],'CODEX_TIMEOUT')
        self.assertIn('repair_elapsed_ms',records[-1])
        self.assertNotIn('PRIVATE',str(records))

    def test_diagnostic_helpers_cannot_replace_business_error_with_unhashable_code(self):
        from server.app.chickenbro import codex_adapter as module
        from types import SimpleNamespace
        error=CodexStreamError('CODEX_OUTPUT_INVALID')
        error.code=['PRIVATE']
        self.assertEqual(module._diagnostic_error(error),'UNEXPECTED')
        def fail(*a,**k):raise RuntimeError('PRIVATE')
        token=module._DIAGNOSTICS.set(SimpleNamespace(emit=fail))
        try:module._diagnostic('stream_failed')
        finally:module._DIAGNOSTICS.reset(token)

    def test_slow_delivery_logger_cannot_cross_deadline_and_complete(self):
        from server.app.chickenbro import codex_adapter as module
        from types import SimpleNamespace
        now=[0.0]
        def log(message,payload):
            if json.loads(payload)['stage']=='delivery_complete':now[0]=2.01
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(module.time,'monotonic',side_effect=lambda:now[0]), \
             patch.object(module._LOG,'info',side_effect=log), patch.object(module._LOG,'warning'):
            adapter=NativeCodexChatAdapter(jobs_dir=directory,enabled=True,popen=lambda *a,**k:FakeProcess(answer()))
            stream=adapter.stream(prompt='q',timeout_seconds=2,
                tool_context=SimpleNamespace(run_id='12345678-1234-1234-1234-123456789abc'))
            self.assertEqual(next(stream),{'type':'delta','text':'answer'})
            with self.assertRaises(CodexStreamError) as caught:next(stream)
            self.assertEqual(caught.exception.code,'CODEX_TIMEOUT')
            self.assertIsNone(module._DIAGNOSTICS.get())

    def test_diagnostic_context_resets_on_generator_close_and_logger_failure(self):
        from server.app.chickenbro import codex_adapter as module
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory, patch.object(module._LOG, 'info', side_effect=RuntimeError('private')):
            adapter = NativeCodexChatAdapter(jobs_dir=directory, enabled=True, popen=lambda *a, **k: FakeProcess(answer()))
            stream = adapter.stream(prompt='PRIVATE', timeout_seconds=2,
                tool_context=SimpleNamespace(run_id='12345678-1234-1234-1234-123456789abc'))
            self.assertEqual(next(stream), {'type':'delta','text':'answer'})
            self.assertIsNotNone(module._DIAGNOSTICS.get())
            stream.close()
            self.assertIsNone(module._DIAGNOSTICS.get())
            result=list(adapter.stream(prompt='PRIVATE',timeout_seconds=2))
            self.assertEqual(result[-1],{'type':'completed','text':'answer'})
            self.assertIsNone(module._DIAGNOSTICS.get())

    def test_repair_diagnostics_distinguish_stream_timeout_and_patch_failure_without_content(self):
        from server.app.chickenbro import codex_adapter as module
        from types import SimpleNamespace
        secret = 'PRIVATE-DRAFT-PROMPT-PATCH'
        for mode in ('stream','patch_apply'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                processes=[FakeProcess(transcript(item('item/started'),delta(secret),item('item/completed',secret))),
                           FakeProcess(transcript(item('item/started'),delta(secret),item('item/completed',secret)))]
                emitted=[]
                with patch.object(module._LOG,'info') as log, patch.object(module._LOG,'warning',side_effect=log), \
                     patch.object(module,'_answer_errors',return_value=['WCL_REFERENCE_UNOBSERVED']), \
                     patch.object(module,'_repair_context',return_value='{}'):
                    adapter=NativeCodexChatAdapter(jobs_dir=directory,enabled=True,popen=lambda *a,**k:processes.pop(0))
                    hook=patch.object(module._RepairSession,'stream',side_effect=CodexStreamError('CODEX_TIMEOUT',secret)) if mode=='stream' else patch.object(module,'_apply_repair_patch',side_effect=CodexStreamError('CODEX_OUTPUT_INVALID',secret))
                    with hook, self.assertRaises(CodexStreamError) as caught:
                        emitted.extend(adapter.stream(prompt=secret,timeout_seconds=480,
                            tool_context=SimpleNamespace(run_id='12345678-1234-1234-1234-123456789abc')))
                    self.assertEqual(caught.exception.code,'CODEX_OUTPUT_INVALID')
                    self.assertEqual(emitted,[])
                    records=[json.loads(call.args[1]) for call in log.call_args_list]
                    failure=next(r for r in records if r['stage']=='repair_failed')
                    self.assertEqual(failure['phase'],mode)
                    self.assertEqual(failure['code'],'CODEX_TIMEOUT' if mode=='stream' else 'CODEX_OUTPUT_INVALID')
                    self.assertIn('repair_elapsed_ms',failure)
                    self.assertNotIn(secret,str(log.call_args_list))
                    self.assertIsNone(module._DIAGNOSTICS.get())

    def test_diagnostic_context_isolated_between_owner_threads(self):
        from server.app.chickenbro import codex_adapter as module
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        barrier=Barrier(2)
        ids=['12345678-1234-1234-1234-123456789abc','abcdefab-1234-1234-1234-123456789abc']
        def owner(run_id):
            token=module._DIAGNOSTICS.set(module._RunDiagnostics(run_id))
            try:
                barrier.wait(timeout=2)
                module._diagnostic('validation',validation_codes=['WCL_REFERENCE_MALFORMED'])
            finally:module._DIAGNOSTICS.reset(token)
            return module._DIAGNOSTICS.get()
        with patch.object(module._LOG,'info') as log, ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(owner,ids)),[None,None])
        self.assertEqual({json.loads(c.args[1])['run_id'] for c in log.call_args_list},set(ids))
        self.assertIsNone(module._DIAGNOSTICS.get())

    def test_repair_patch_applies_original_positions_without_touching_other_text(self):
        from server.app.chickenbro.codex_adapter import _apply_repair_patch
        draft = 'prefix old-one middle old-two suffix'
        patch_text = json.dumps({'replacements': [{'old': 'old-one', 'new': 'a much longer replacement'},
                                                 {'old': 'old-two', 'new': 'short'}]})
        self.assertEqual(_apply_repair_patch(draft, patch_text), 'prefix a much longer replacement middle short suffix')
        self.assertEqual(_apply_repair_patch('A B', json.dumps({'replacements': [
            {'old': 'A', 'new': 'B'}, {'old': 'B', 'new': 'C'}]})), 'B C')

    def test_repair_patch_schema_ambiguity_overlap_and_size_fail_closed(self):
        from server.app.chickenbro.codex_adapter import _apply_repair_patch
        cases = [([], '{}'), ('abc', 'not json'), ('abc', '[]'), ('abc', '{"replacements":[]}'),
                 ('abc', '{"replacements":[],"answer":"abc"}'),
                 ('abc', '{"replacements":[],"replacements":[]}'),
                 ('abc', '{"replacements":[{"old":"a","old":"b","new":"x"}]}'),
                 ('abc', '{"replacements":[{"old":"a","new":"b","extra":1}]}'),
                 ('abc', '{"replacements":[{"old":"","new":"b"}]}'),
                 ('abc', '{"replacements":[{"old":"a","new":3}]}'),
                 ('abc', '{"replacements":[{"old":"missing","new":"b"}]}'),
                 ('aaa', '{"replacements":[{"old":"aa","new":"b"}]}'),
                 ('abc', '{"replacements":[{"old":"ab","new":"x"},{"old":"bc","new":"y"}]}'),
                 ('abc', '{"replacements":[{"old":"a","new":"x"},{"old":"a","new":"y"}]}'),
                 ('abc', json.dumps({'replacements': [{'old': 'a', 'new': 'x'}] * 33})),
                 ('abc', json.dumps({'replacements': [{'old': 'a', 'new': 'x' * 16001}]})),
                 ('abc', ' ' * 64001 + '{}'),
                 ('abc', '[' * 1200 + ']' * 1200),
                 ('start' + 'x' * 262135, json.dumps({'replacements': [{'old': 'start', 'new': 'n' * 20}]})),
                 ('a' * 262144, json.dumps({'replacements': [{'old': 'a' * 16000, 'new': 'x'}]}))]
        for draft, patch_text in cases:
            with self.subTest(patch_text=patch_text[:80]), self.assertRaises(CodexStreamError) as caught:
                _apply_repair_patch(draft, patch_text)
            self.assertEqual(caught.exception.code, 'CODEX_OUTPUT_INVALID')

    def test_invalid_draft_repaired_once_before_any_answer_delta(self):
        from server.app.chickenbro import codex_adapter as module
        class EvidenceGateway(Gateway):
            def answer_evidence(self, token):
                return {'reports': [{'canonicalUrl': 'verified'}], 'groups': [], 'truncated': False}
        original = FakeProcess(transcript(item('item/started'), delta('BAD DRAFT'), item('item/completed', 'BAD DRAFT')))
        repaired = FakeProcess(replacement('BAD DRAFT', 'REPAIRED'))
        gateway, calls = EvidenceGateway(), []
        def popen(*args, **kwargs):
            calls.append(kwargs)
            if len(calls) == 2:
                self.assertEqual(gateway.revoked, 'job-capability')
            return original if len(calls) == 1 else repaired
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(module, '_answer_errors', side_effect=[['INVALID_REPORT_REFERENCE'], []]), \
             patch.object(module, '_repair_context', return_value='{"reports":[]}'), \
             patch.dict(os.environ, {'CODEX_HOME': directory}):
            adapter = NativeCodexChatAdapter(enabled=True, jobs_dir=directory, source_gateway=gateway, popen=popen)
            result = list(adapter.stream(prompt='original question', timeout_seconds=480))
        self.assertEqual(result, [{'type': 'delta', 'text': 'REPAIRED'}, {'type': 'completed', 'text': 'REPAIRED'}])
        self.assertEqual(len(calls), 2)
        self.assertFalse(any(key.startswith('CHICKENBRO_') for key in calls[1]['env']))
        config = repaired.sent()[2]['params']['config']
        self.assertEqual(config['web_search'], 'disabled')
        self.assertFalse(config['features']['shell_tool'])
        self.assertFalse(config['features']['unified_exec'])
        repair_input = repaired.sent()[3]['params']['input'][0]['text']
        self.assertIn('BAD DRAFT', repair_input)
        self.assertEqual(config['model_reasoning_effort'], 'low')

    def test_whole_answer_is_revalidated_after_patch_and_only_validated_answer_leaves(self):
        from server.app.chickenbro import codex_adapter as module
        draft, corrected = 'keep prefix\nBAD\nkeep suffix', 'keep prefix\nGOOD\nkeep suffix'
        processes = [FakeProcess(transcript(item('item/started'), delta(draft), item('item/completed', draft))),
                     FakeProcess(replacement('BAD', 'GOOD'))]
        seen = []
        def validate(text, evidence):
            seen.append(text)
            return [] if text == corrected else ['INVALID_REPORT_REFERENCE']
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'CODEX_HOME': directory}), \
             patch.object(module, '_answer_errors', side_effect=validate), patch.object(module, '_repair_context', return_value='{}'):
            adapter = NativeCodexChatAdapter(enabled=True, jobs_dir=directory, source_gateway=Gateway(),
                popen=lambda *a, **k: processes.pop(0))
            result = list(adapter.stream(prompt='q', timeout_seconds=480))
        self.assertEqual(seen, [draft, corrected])
        self.assertEqual(result, [{'type': 'delta', 'text': corrected}, {'type': 'completed', 'text': corrected}])

    def test_repair_failure_never_leaks_original_or_repaired_draft(self):
        from server.app.chickenbro import codex_adapter as module
        gateway = Gateway()
        gateway.answer_evidence = lambda token: {'reports': [{'id': 'evidence'}]}
        processes = [FakeProcess(answer()), FakeProcess(replacement('answer', 'corrected'))]
        emitted = []
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(module, '_answer_errors', return_value=['INVALID_REPORT_REFERENCE']), \
             patch.object(module, '_repair_context', return_value='{}'), \
             patch.dict(os.environ, {'CODEX_HOME': directory}):
            adapter = NativeCodexChatAdapter(enabled=True, jobs_dir=directory, source_gateway=gateway,
                popen=lambda *a, **k: processes.pop(0))
            with self.assertRaises(CodexStreamError) as caught:
                for event in adapter.stream(prompt='question', timeout_seconds=480):
                    emitted.append(event)
        self.assertEqual(caught.exception.code, 'CODEX_OUTPUT_INVALID')
        self.assertEqual(emitted, [])
        self.assertEqual(len(processes), 0)

    def test_repair_profile_explicitly_disables_inherited_servers_and_tools(self):
        from server.app.chickenbro.codex_adapter import _repair_profile
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'CODEX_HOME': directory}):
            Path(directory, 'config.toml').write_text('[mcp_servers.inherited]\ncommand="private-command"\n')
            original = {'model': 'gpt-6-astra', 'model_reasoning_effort': 'high', 'web_search': 'live', 'features': {'shell_tool': True},
                        'mcp_servers': {'chickenbro_toolbox': {'command': 'tool', 'enabled': True}}}
            result = _repair_profile(original)
        self.assertEqual(result['mcp_servers'], {'inherited': {'command': 'private-command', 'enabled': False},
                                                  'chickenbro_toolbox': {'command': 'tool', 'enabled': False}})
        self.assertTrue(original['features']['shell_tool'])
        self.assertEqual(result['model'], 'gpt-6-astra')
        self.assertEqual(result['model_reasoning_effort'], 'low')
        self.assertEqual(original['model_reasoning_effort'], 'high')
        self.assertTrue(all(result['features'][name] is False for name in ('shell_tool', 'unified_exec', 'apps', 'plugins', 'multi_agent')))

    def test_repair_deadline_uses_remaining_original_budget_and_rejects_tools(self):
        from server.app.chickenbro import codex_adapter as module
        adapter = NativeCodexChatAdapter(enabled=True)
        with patch.object(module.time, 'monotonic', return_value=476):
            with self.assertRaises(CodexStreamError) as caught:
                adapter._repair_answer('q', 'bad', ['BAD'], {}, 480, [], {}, {})
        self.assertEqual(caught.exception.code, 'CODEX_OUTPUT_INVALID')
        process = FakeProcess(replacement('bad', 'answer'))
        captured = []
        RealSession = module._RepairSession
        def session(child, deadline):
            captured.append(deadline)
            return RealSession(child, deadline)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'CODEX_HOME': directory}), \
             patch.object(module.time, 'monotonic', return_value=450), \
             patch.object(module, '_repair_context', return_value='{}'), \
             patch.object(module, '_answer_errors', return_value=[]), patch.object(module, '_RepairSession', side_effect=session):
            adapter = NativeCodexChatAdapter(enabled=True, jobs_dir=directory, popen=lambda *a, **k: process)
            self.assertEqual(adapter._repair_answer('q', 'bad', ['BAD'], {}, 480, [], {}, {}), 'answer')
        self.assertEqual(captured, [475])
        forbidden = FakeProcess(transcript(item('item/started', kind='mcpToolCall')))
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'CODEX_HOME': directory}), \
             patch.object(module, '_repair_context', return_value='{}'):
            adapter = NativeCodexChatAdapter(enabled=True, jobs_dir=directory, popen=lambda *a, **k: forbidden)
            with self.assertRaises(CodexStreamError) as caught:
                adapter._repair_answer('q', 'bad', ['BAD'], {}, time.monotonic() + 480, [], {}, {})
        self.assertEqual(caught.exception.code, 'CODEX_OUTPUT_INVALID')
        self.assertTrue(forbidden.killed)

    def test_repair_timeout_maps_to_invalid_and_revoked_evidence_never_leaks(self):
        from server.app.chickenbro import codex_adapter as module
        process = FakeProcess(answer(), wait_error=subprocess.TimeoutExpired('repair', 1))
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'CODEX_HOME': directory}), \
             patch.object(module, '_repair_context', return_value='{}'):
            adapter = NativeCodexChatAdapter(enabled=True, jobs_dir=directory, popen=lambda *a, **k: process)
            with self.assertRaises(CodexStreamError) as caught:
                adapter._repair_answer('q', 'bad', ['BAD'], {}, time.monotonic() + 480, [], {}, {})
        self.assertEqual(caught.exception.code, 'CODEX_OUTPUT_INVALID')
        self.assertTrue(process.killed)
        gateway = Gateway()
        gateway.answer_evidence = lambda token: (_ for _ in ()).throw(ValueError('expired private token'))
        emitted = []
        with tempfile.TemporaryDirectory() as directory:
            adapter = NativeCodexChatAdapter(enabled=True, jobs_dir=directory, source_gateway=gateway, popen=lambda *a, **k: FakeProcess(answer()))
            with self.assertRaises(CodexStreamError) as caught:
                for event in adapter.stream(prompt='q', timeout_seconds=480): emitted.append(event)
        self.assertEqual(emitted, [])
        self.assertEqual(caught.exception.code, 'CODEX_OUTPUT_INVALID')
        self.assertEqual(gateway.revoked, 'job-capability')

    def test_public_progress_still_streams_before_validation_and_close_terminates(self):
        process = FakeProcess(transcript(item('item/started', identity='thought', kind='reasoning'),
            note('item/reasoning/summaryTextDelta', threadId='thread', turnId='turn', itemId='thought', summaryIndex=0, delta='核对中'),
            item('item/completed', identity='thought', kind='reasoning'), item('item/started'), delta('answer'), item('item/completed', 'answer')))
        gateway = Gateway()
        with tempfile.TemporaryDirectory() as directory:
            adapter = NativeCodexChatAdapter(enabled=True, jobs_dir=directory, source_gateway=gateway, popen=lambda *a, **k: process)
            stream = adapter.stream(prompt='q', timeout_seconds=480)
            self.assertEqual(next(stream), {'type': 'progress', 'text': '核对中'})
            self.assertEqual(process.wait_calls, 0)
            stream.close()
        self.assertTrue(process.killed)
        self.assertEqual(gateway.revoked, 'job-capability')

    def test_empty_evidence_still_rejects_malformed_reference_and_repairs_without_facts(self):
        from server.app.chickenbro import codex_adapter as module
        bad = 'https://www.warcraftlogs.com/reports/jx不存在'
        good = '当前没有可核验的日志证据，不能确认这些结论。'
        processes = [FakeProcess(transcript(item('item/started'), delta(bad), item('item/completed', bad))),
                     FakeProcess(replacement(bad, good))]
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'CODEX_HOME': directory}):
            adapter = NativeCodexChatAdapter(enabled=True, jobs_dir=directory, source_gateway=Gateway(),
                popen=lambda *a, **k: processes.pop(0))
            result = list(adapter.stream(prompt='read logs', timeout_seconds=480))
        self.assertEqual(result, [{'type': 'delta', 'text': good}, {'type': 'completed', 'text': good}])
        self.assertEqual(processes, [])

    def test_attempted_wcl_empty_evidence_reaches_both_validation_passes(self):
        from server.app.chickenbro import codex_adapter as module
        gateway = Gateway()
        evidence = {'reports': [], 'groups': [], 'truncated': False, 'attemptedWcl': True}
        gateway.answer_evidence = lambda token: evidence
        processes = [FakeProcess(answer()), FakeProcess(replacement('answer', 'corrected'))]
        seen = []
        def validate(text, supplied):
            seen.append(supplied)
            return ['WCL_REFERENCE_UNOBSERVED'] if len(seen) == 1 else []
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'CODEX_HOME': directory}), \
             patch.object(module, '_answer_errors', side_effect=validate), \
             patch.object(module, '_repair_context', return_value=json.dumps(evidence)):
            adapter = NativeCodexChatAdapter(enabled=True, jobs_dir=directory, source_gateway=gateway,
                popen=lambda *a, **k: processes.pop(0))
            result = list(adapter.stream(prompt='read report', timeout_seconds=480))
        self.assertEqual(len(seen), 2)
        self.assertTrue(all(item['attemptedWcl'] is True for item in seen))
        self.assertEqual(result[-1]['type'], 'completed')

    def test_images_are_ordered_native_blocks_and_not_written_to_job_files(self):
        images = ['data:image/png;base64,aGVsbG8=', 'data:image/jpeg;base64,d29ybGQ=']
        process = FakeProcess(answer())
        with tempfile.TemporaryDirectory() as directory:
            adapter = NativeCodexChatAdapter(enabled=True, jobs_dir=directory, popen=lambda *a, **k: process)
            result = list(adapter.stream_for_chat(principal=None, conversation_id='chat', run_id='run',
                prompt='inspect attached images', timeout_seconds=2, images=images))
            for path in Path(directory).rglob('*'):
                if path.is_file():
                    self.assertNotIn(images[0], path.read_text())
        self.assertEqual(result[-1], dict(type='completed', text='answer'))
        self.assertEqual(process.sent()[-1]['params']['input'], [
            {'type': 'text', 'text': 'inspect attached images'},
            *[{'type': 'image', 'url': url} for url in images],
        ])

    def test_large_input_reaches_reading_runtime_without_truncation(self):
        from server.app.chickenbro.codex_stdio import CodexStdioSession
        process = subprocess.Popen([sys.executable, '-c',
            'import json,sys; value=json.loads(sys.stdin.buffer.readline()); print(len(value["input"]), flush=True)'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
        session = CodexStdioSession(process, time.monotonic() + 3)
        try:
            session.send({'input': '鸡' * (1024 * 1024)})
            self.assertEqual(process.stdout.readline(), b'1048576\n')
            self.assertEqual(process.wait(timeout=2), 0)
            self.assertTrue(os.get_blocking(process.stdin.fileno()))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdin.close()
            process.stdout.close()
            session.messages.close()

    def test_nonreading_runtime_input_times_out_before_child_exit(self):
        from server.app.chickenbro.codex_stdio import CodexStdioSession
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(1.5)'],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
        started = time.monotonic()
        session = CodexStdioSession(process, started + 0.15)
        try:
            with self.assertRaises(CodexStreamError) as caught:
                session.send({'input': 'x' * (2 * 1024 * 1024)})
            self.assertEqual(caught.exception.code, 'CODEX_TIMEOUT')
            self.assertLess(time.monotonic() - started, 1.0)
            self.assertIsNone(process.poll())
        finally:
            process.kill()
            process.wait()
            process.stdin.close()
            process.stdout.close()
            session.messages.close()

    def test_large_image_echo_is_bounded_and_not_forwarded(self):
        url = 'data:image/png;base64,' + 'YWJj' * 300000
        process = FakeProcess(transcript(
            note('item/started', threadId='thread', turnId='turn',
                 item={'id': 'user', 'type': 'userMessage', 'content': [{'type': 'image', 'url': url}]}),
            item('item/started'), delta('answer'), item('item/completed', 'answer')))
        with tempfile.TemporaryDirectory() as directory:
            adapter = NativeCodexChatAdapter(enabled=True, jobs_dir=directory, popen=lambda *a, **k: process)
            result = list(adapter.stream(prompt='inspect', timeout_seconds=2, images=[url]))
        self.assertEqual(result, [{'type': 'delta', 'text': 'answer'}, {'type': 'completed', 'text': 'answer'}])

    def test_invalid_images_fail_before_starting_runtime(self):
        bad_inputs = [['https://example.com/private.png'], ['file:///private.png'],
                      ['data:image/svg+xml;base64,aGVsbG8='], ['data:image/png;base64,!'],
                      ['data:image/png;base64,aGVsbG8='] * 10, 'data:image/png;base64,aGVsbG8=']
        for images in bad_inputs:
            with self.subTest(images=images), tempfile.TemporaryDirectory() as directory:
                def popen(*args, **kwargs):
                    self.fail('invalid image input started runtime')
                adapter = NativeCodexChatAdapter(enabled=True, jobs_dir=directory, popen=popen)
                with self.assertRaises(CodexStreamError):
                    list(adapter.stream(prompt='inspect', timeout_seconds=2, images=images))

    def test_text_only_turn_input_remains_unchanged(self):
        _, process = self.run_stream()
        self.assertEqual(process.sent()[-1]['params']['input'], [{'type': 'text', 'text': 'hello'}])

    def test_simulation_capability_uses_server_context_and_is_revoked(self):
        from uuid import uuid4
        from server.app.identity.domain import Principal
        class SimulationGateway:
            context = None
            revoked = None
            def issue_capability(self, context):
                self.context = context
                return 'simulation-capability'
            def revoke(self, token):
                self.revoked = token
        gateway = SimulationGateway()
        captured = {}
        process = FakeProcess(answer())
        def popen(command, **kwargs):
            captured.update(kwargs)
            return process
        principal = Principal(uuid4(), 'web_cookie')
        conversation_id, run_id = uuid4(), uuid4()
        with tempfile.TemporaryDirectory() as directory:
            adapter = NativeCodexChatAdapter(enabled=True, jobs_dir=directory, popen=popen,
                simulation_gateway=gateway, simulation_gateway_url='http://127.0.0.1:8792/api/v2/internal/chickenbro/simc-tool')
            events = list(adapter.stream_for_chat(principal=principal, conversation_id=conversation_id,
                run_id=run_id, prompt='simulate', timeout_seconds=30))
        self.assertEqual(events[-1]['type'], 'completed')
        self.assertEqual(gateway.context.principal, principal)
        self.assertEqual(gateway.context.run_id, run_id)
        self.assertEqual(gateway.context.conversation_id, conversation_id)
        self.assertEqual(captured['env']['CHICKENBRO_SIMULATION_GATEWAY_TOKEN'], 'simulation-capability')
        self.assertNotIn(str(principal.user_id), str(captured['env']))
        self.assertEqual(gateway.revoked, 'simulation-capability')

    def test_chat_profile_enables_live_native_web_search(self):
        from server.app.chickenbro.codex_adapter import _load_profile
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"CODEX_HOME": directory}):
            profile = Path(directory, "test.config.toml")
            for inherited in ("disabled", "cached", "live"):
                original = f'model="gpt-6-astra"\nweb_search="{inherited}"\n'
                profile.write_text(original, encoding='utf-8')
                for selected in (None, "test"):
                    with self.subTest(profile=selected, inherited=inherited):
                        self.assertEqual(_load_profile(selected).get("web_search"), "live")
                self.assertEqual(profile.read_text(), original)

    def test_profile_uses_current_release_toolbox_and_bounded_batch_timeout(self):
        from server.app.chickenbro.codex_adapter import _load_profile
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"CODEX_HOME": directory}):
            Path(directory, "test.config.toml").write_text(
                'model="gpt-6-astra"\nmodel_reasoning_effort="high"\n'
                '[mcp_servers.chickenbro_toolbox]\ncommand="/usr/bin/python3"\n'
                'args=["/opt/old-release/server/chickenbro_native_mcp.py"]\ntool_timeout_sec=30\n'
                'env_vars=["CHICKENBRO_SOURCE_GATEWAY_TOKEN", "HTTP_PROXY"]\n', encoding='utf-8')
            config = _load_profile("test")
            self.assertEqual(config["model"], "gpt-6-astra")
            self.assertEqual(config["model_reasoning_effort"], "high")
            self.assertEqual(config["mcp_servers"]["chickenbro_toolbox"]["args"],
                             [str(Path(__file__).resolve().parents[1] / "server/chickenbro_native_mcp.py")])
            self.assertEqual(config["mcp_servers"]["chickenbro_toolbox"]["tool_timeout_sec"], 90)
            self.assertEqual(config["mcp_servers"]["chickenbro_toolbox"]["env_vars"], [
                "CHICKENBRO_SOURCE_GATEWAY_TOKEN", "HTTP_PROXY",
                "CHICKENBRO_SIMULATION_GATEWAY_URL", "CHICKENBRO_SIMULATION_GATEWAY_TOKEN"])
            self.assertNotIn("tools", config["mcp_servers"]["chickenbro_toolbox"])
            scoped = _load_profile("test", allow_simulation=True)
            self.assertEqual(scoped["mcp_servers"]["chickenbro_toolbox"]["tools"], {
                "prepare_simulation": {"approval_mode": "approve"},
                "submit_simulation": {"approval_mode": "approve"},
            })

    def test_streams_public_summary_separately_and_rejects_wrong_turn(self):
        summary = note('item/reasoning/summaryTextDelta', threadId='thread', turnId='turn',
                       itemId='thought', summaryIndex=0, delta='正在核对技能覆盖率')
        body = [item('item/started', identity='thought', kind='reasoning'), summary,
                note('item/reasoning/textDelta', delta='private raw reasoning'),
                item('item/completed', identity='thought', kind='reasoning'),
                item('item/started'), delta('ans'), delta('wer'), item('item/completed', 'answer')]
        result, _ = self.run_stream(transcript(*body))
        self.assertEqual(result, [dict(type='progress', text='正在核对技能覆盖率'),
            dict(type='delta', text='answer'), dict(type='completed', text='answer')])
        self.assertEqual(result[-1], dict(type='completed', text='answer'))
        self.assertNotIn('private raw', json.dumps(result))
        summary['params']['turnId'] = 'other'
        with self.assertRaises(CodexStreamError):
            self.run_stream(transcript(*body))

    def test_oversized_public_summary_is_capped_without_losing_final_answer(self):
        result, _ = self.run_stream(transcript(
            item('item/started', identity='thought', kind='reasoning'),
            note('item/reasoning/summaryTextDelta', threadId='thread', turnId='turn',
                 itemId='thought', summaryIndex=0, delta='🐔' * 16001),
            note('item/reasoning/summaryTextDelta', threadId='thread', turnId='turn',
                 itemId='thought', summaryIndex=0, delta='more'),
            item('item/completed', identity='thought', kind='reasoning'),
            item('item/started'), delta('answer'), item('item/completed', 'answer')))
        self.assertEqual(len(result[0]['text']), 16000)
        self.assertEqual(result[-1], dict(type='completed', text='answer'))
        self.assertEqual(len(result), 3)

    def test_uses_native_app_server_transport(self):
        def popen(command, **kwargs):
            self.assertIn('app-server', command)
            return FakeProcess(answer())
        with tempfile.TemporaryDirectory() as directory:
            adapter = NativeCodexChatAdapter(jobs_dir=directory, enabled=True, popen=popen)
            list(adapter.stream(prompt='hello', timeout_seconds=2))

    def run_stream(self, events=None, process=None, gateway=None):
        process = process or FakeProcess(answer() if events is None else events)
        with tempfile.TemporaryDirectory() as directory:
            adapter = NativeCodexChatAdapter(jobs_dir=directory, enabled=True, source_gateway=gateway, popen=lambda *a, **k: process)
            result = list(adapter.stream(prompt='hello', timeout_seconds=2))
        return result, process

    def test_validated_fragmented_answer_has_bounded_durable_delivery_cost(self):
        # Each delivered delta becomes a separate guarded database transaction
        # in ChatWorker. Model token boundaries must not multiply that cost once
        # the complete answer has already been buffered and validated.
        fragments = ['鸡', '哥', '🐔', '\n'] * 250
        text = ''.join(fragments)
        result, _ = self.run_stream(transcript(item('item/started'),
            *(delta(part) for part in fragments), item('item/completed', text)))
        writes = [event['text'] for event in result if event['type'] == 'delta']
        self.assertEqual(''.join(writes), text)
        self.assertEqual(len(writes), 1)
        self.assertEqual(result[-1], {'type': 'completed', 'text': text})

    def test_validation_exhausting_deadline_leaks_no_coalesced_answer(self):
        from server.app.chickenbro import codex_adapter as module
        now = [0.0]
        gateway = Gateway()
        process = FakeProcess(transcript(item('item/started'), delta('one'), delta('two'), item('item/completed', 'onetwo')))
        def validate(text, evidence):
            self.assertEqual(text, 'onetwo')
            now[0] = 2.0
            return []
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(module.time, 'monotonic', side_effect=lambda: now[0]), \
             patch.object(module, '_answer_errors', side_effect=validate):
            adapter = NativeCodexChatAdapter(jobs_dir=directory, enabled=True, source_gateway=gateway,
                popen=lambda *a, **k: process)
            stream = adapter.stream(prompt='hello', timeout_seconds=2)
            with self.assertRaises(CodexStreamError) as caught:
                next(stream)
            self.assertEqual(caught.exception.code, 'CODEX_TIMEOUT')
            self.assertEqual(gateway.revoked, 'job-capability')

    def test_slow_durable_delivery_cannot_complete_after_original_deadline(self):
        from server.app.chickenbro import codex_adapter as module
        now = [0.0]
        process = FakeProcess(answer())
        with tempfile.TemporaryDirectory() as directory, patch.object(module.time, 'monotonic', side_effect=lambda: now[0]):
            adapter = NativeCodexChatAdapter(jobs_dir=directory, enabled=True, popen=lambda *a, **k: process)
            stream = adapter.stream(prompt='hello', timeout_seconds=2)
            self.assertEqual(next(stream), {'type': 'delta', 'text': 'answer'})
            # Simulate the synchronous consumer returning after a slow write.
            now[0] = 2.01
            with self.assertRaises(CodexStreamError) as caught:
                next(stream)
            self.assertEqual(caught.exception.code, 'CODEX_TIMEOUT')
            stream.close()

    def test_validated_final_answer_and_protocol_sequence(self):
        result, process = self.run_stream(transcript(item('item/started'), delta('one'), delta('two'), item('item/completed', 'onetwo')))
        self.assertEqual(result, [dict(type='delta', text='onetwo'), dict(type='completed', text='onetwo')])
        sent = process.sent()
        self.assertEqual([m['method'] for m in sent], ['initialize', 'initialized', 'thread/start', 'turn/start'])
        self.assertEqual(sent[2]['params']['approvalPolicy'], 'never')
        self.assertEqual(sent[2]['params']['sandbox'], 'read-only')
        self.assertTrue(sent[2]['params']['ephemeral'])
        self.assertEqual(sent[3]['params']['input'], [dict(type='text', text='hello')])
        self.assertEqual(sent[3]['params'].get('summary'), 'auto')

    def test_commentary_reasoning_tools_and_unknown_methods_never_exposed(self):
        events = transcript(item('item/started', phase='commentary', identity='comment'), delta('secret', 'comment'),
                            item('item/completed', 'secret', 'commentary', 'comment'),
                            note('item/reasoning/textDelta', delta='secret'), note('item/commandExecution/outputDelta', delta='secret'),
                            note('unknown', text='secret'), item('item/started'), delta('answer'), item('item/completed', 'answer'))
        result, _ = self.run_stream(events)
        self.assertEqual(result, [dict(type='delta', text='answer'), dict(type='completed', text='answer')])

    def test_unknown_phase_withheld_until_explicit_final_and_missing_phase_rejected(self):
        result, _ = self.run_stream(transcript(item('item/started', phase=None), delta('answer'), item('item/completed', 'answer')))
        self.assertEqual(result, [dict(type='completed', text='answer')])
        with self.assertRaises(CodexStreamError):
            self.run_stream(transcript(item('item/started', phase=None), delta('secret'), item('item/completed', 'secret', phase=None)))

    def test_mismatched_completed_text_is_not_saved_as_success(self):
        for final in ['different', 'answer extra', '']:
            with self.subTest(final=final), self.assertRaises(CodexStreamError):
                self.run_stream(transcript(item('item/started'), delta('answer'), item('item/completed', final)))

    def test_wrong_ids_duplicate_start_unstarted_delta_and_response_error_fail_closed(self):
        bad = [delta('secret', 'unknown'), dict(id=99, result={}), dict(id=1, error=dict(message='secret')),
               item('item/started'), note('error', message='secret')]
        for key in ['threadId', 'turnId']:
            event = delta('secret'); event['params'][key] = 'other'; bad.append(event)
        for event in bad:
            with self.subTest(event=event), self.assertRaises(CodexStreamError) as ctx:
                self.run_stream(transcript(item('item/started'), event))
            self.assertNotIn('secret', str(ctx.exception))

    def test_success_requires_completed_final_item_and_completed_turn(self):
        cases = [transcript(), answer()[:-1], transcript(item('item/started'), delta('answer'))]
        cases += [transcript(item('item/started'), item('item/completed', 'answer'), status=s) for s in ['failed', 'interrupted', 'inProgress']]
        for events in cases:
            with self.subTest(events=events), self.assertRaises(CodexStreamError): self.run_stream(events)

    def test_retryable_error_is_private_and_can_recover_within_same_turn(self):
        error = note('error', threadId='thread', turnId='turn', willRetry=True,
                     error=dict(message='private provider details', codexErrorInfo='responseStreamDisconnected'))
        result, _ = self.run_stream(transcript(item('item/started'), error, delta('answer'), item('item/completed', 'answer')))
        self.assertEqual(result[-1], dict(type='completed', text='answer'))
        for key, value in [('threadId', 'other'), ('turnId', 'other'), ('willRetry', False)]:
            bad = dict(error, params=dict(error['params'], **{key: value}))
            with self.subTest(key=key), self.assertRaises(CodexStreamError):
                self.run_stream(transcript(item('item/started'), bad))

    def test_approval_requests_fail_closed_and_revoke_capability(self):
        for method in ['item/commandExecution/requestApproval', 'item/fileChange/requestApproval', 'unknown/request']:
            process = FakeProcess(transcript(dict(id=80, method=method, params={}))); gateway = Gateway()
            with self.subTest(method=method), self.assertRaises(CodexStreamError): self.run_stream(process=process, gateway=gateway)
            self.assertTrue(process.killed); self.assertEqual(gateway.revoked, 'job-capability')
            response = process.sent()[-1]; self.assertEqual(response['id'], 80)
            if method == 'unknown/request': self.assertIn('error', response)
            else: self.assertEqual(response['result'], dict(decision='cancel'))

    def test_rules_reload_as_developer_instructions_and_not_user_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'AGENTS.md'
            with patch('server.app.chickenbro.codex_adapter._AGENT_RULES_PATH', path):
                for rules in ['rules one " \\ \n', 'rules two']:
                    path.write_bytes(rules.encode('utf-8')); _, process = self.run_stream()
                    self.assertEqual(process.sent()[2]['params']['developerInstructions'], rules)
                    self.assertEqual(process.sent()[3]['params']['input'][0]['text'], 'hello')

    def test_invalid_rules_and_disabled_or_unwritable_jobs_fail_before_spawn(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'AGENTS.md'
            with patch('server.app.chickenbro.codex_adapter._AGENT_RULES_PATH', path):
                for content in [None, b' \n', b'\xff', b'x' * 32769]:
                    if content is not None: path.write_bytes(content)
                    with self.assertRaises(CodexUnavailable): self.run_stream()
            for enabled, root in [(False, directory), (True, path)]:
                adapter = NativeCodexChatAdapter(enabled=enabled, jobs_dir=root, popen=lambda *a, **k: self.fail('must not spawn'))
                with self.assertRaises(CodexUnavailable): list(adapter.stream(prompt='hello', timeout_seconds=2))
        self.assertEqual(NativeCodexChatAdapter(enabled=False, runtime_revision='codex:verified').runtime_revision, 'codex:verified')

    def test_environment_profile_and_source_capability_are_preserved_without_credentials(self):
        captured = {}; process = FakeProcess(answer()); gateway = Gateway()
        def popen(command, **kwargs): captured.update(kwargs, command=command); return process
        env = dict(CODEX_HOME='/home/test/.codex', WOW_CODEX_PROFILE='chickenbro-native', HTTPS_PROXY='http://127.0.0.1:7890', WOW_DATABASE_URL='secret', WOW_WECHAT_SECRET='secret')
        with tempfile.TemporaryDirectory() as directory:
            env['CODEX_HOME'] = directory
            Path(directory, 'chickenbro-native.config.toml').write_text('model="gpt-6-astra"\nmodel_reasoning_effort="high"\n[mcp_servers.sources]\ncommand="existing-source-tool"\n')
            with patch.dict(os.environ, env):
                adapter = NativeCodexChatAdapter(jobs_dir=directory, enabled=True, source_gateway=gateway, popen=popen)
                list(adapter.stream(prompt='hello', timeout_seconds=2))
        self.assertIn('app-server', captured['command']); self.assertNotIn('exec', captured['command'])
        self.assertNotIn('--profile', captured['command'])
        config = process.sent()[2]['params']['config']
        self.assertEqual(config['model'], 'gpt-6-astra')
        self.assertEqual(config['model_reasoning_effort'], 'high')
        self.assertEqual(config['mcp_servers']['sources']['command'], 'existing-source-tool')
        for key in ['CODEX_HOME', 'HTTPS_PROXY']: self.assertEqual(captured['env'][key], env[key])
        for key in ['WOW_DATABASE_URL', 'WOW_WECHAT_SECRET']: self.assertNotIn(key, captured['env'])
        self.assertEqual(captured['env']['CHICKENBRO_SOURCE_GATEWAY_TOKEN'], 'job-capability')
        self.assertTrue(captured['env']['CHICKENBRO_NATIVE_OBSERVATIONS_PATH'].endswith('native-tool-observations.jsonl'))
        self.assertEqual(gateway.revoked, 'job-capability')

    def test_buffered_final_waits_for_exit_and_revocation_before_first_delta(self):
        for partial in [False, True]:
            gateway = Gateway(); process = FakeProcess(answer() if partial else transcript(item('item/started'), item('item/completed', 'answer')))
            with tempfile.TemporaryDirectory() as directory:
                adapter = NativeCodexChatAdapter(jobs_dir=directory, enabled=True, source_gateway=gateway, popen=lambda *a, **k: process)
                stream = adapter.stream(prompt='hello', timeout_seconds=2)
                self.assertEqual(next(stream)['type'], 'delta' if partial else 'completed')
                self.assertGreaterEqual(process.wait_calls, 1); self.assertEqual(gateway.revoked, 'job-capability')
                stream.close()
            self.assertFalse(process.killed)
            self.assertEqual(gateway.revoked, 'job-capability')

    def test_nonzero_exit_and_timeout_return_stable_errors(self):
        for kwargs, code in [(dict(returncode=17), 'CODEX_EXECUTION_FAILED'), (dict(wait_error=subprocess.TimeoutExpired('codex', 1)), 'CODEX_TIMEOUT')]:
            with self.subTest(code=code), self.assertRaises(CodexStreamError) as ctx: self.run_stream(process=FakeProcess(answer(), **kwargs))
            self.assertEqual(ctx.exception.code, code)

    def test_empty_invalid_json_and_non_object_never_complete(self):
        for value in [b'', b'secret\n', b'[]\n']:
            process = FakeProcess(); process.stdout = io.BytesIO(value)
            with self.subTest(value=value), self.assertRaises(CodexStreamError): self.run_stream(process=process)
            self.assertTrue(process.killed)

    def test_missing_invalid_and_unsafe_profile_fail_before_spawning(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'CODEX_HOME': ''}):
            with patch.dict(os.environ, {'CODEX_HOME': directory}):
                Path(directory, 'invalid.config.toml').write_text('invalid = [')
                for profile in ['missing', 'invalid', '../escape']:
                    adapter = NativeCodexChatAdapter(jobs_dir=directory, enabled=True, profile=profile,
                                                     popen=lambda *a, **k: self.fail('must not spawn'))
                    with self.subTest(profile=profile), self.assertRaises(CodexUnavailable):
                        list(adapter.stream(prompt='hello', timeout_seconds=2))

    def test_spawn_failure_revokes_capability(self):
        gateway = Gateway()
        with tempfile.TemporaryDirectory() as directory:
            adapter = NativeCodexChatAdapter(jobs_dir=directory, enabled=True, source_gateway=gateway,
                                             popen=lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()))
            with self.assertRaises(CodexUnavailable): list(adapter.stream(prompt='hello', timeout_seconds=2))
        self.assertEqual(gateway.revoked, 'job-capability')

    def test_posix_cleanup_targets_the_spawned_process_group_and_reaps_parent(self):
        process = FakeProcess(); process.pid = 4123
        with patch('server.app.chickenbro.codex_adapter.os.name', 'posix'), patch('server.app.chickenbro.codex_adapter.signal.SIGKILL', 9, create=True), patch('server.app.chickenbro.codex_adapter.os.killpg', create=True) as kill:
            NativeCodexChatAdapter._terminate(process)
        kill.assert_called_once()
        self.assertEqual(kill.call_args.args[0], 4123)
        self.assertEqual(process.wait_calls, 1)

if __name__ == '__main__': unittest.main()

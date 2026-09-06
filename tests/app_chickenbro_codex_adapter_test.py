import io
import json
import os
import subprocess
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


class ChickenbroCodexAdapterTest(unittest.TestCase):
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

    def test_incremental_final_answer_and_protocol_sequence(self):
        result, process = self.run_stream(transcript(item('item/started'), delta('one'), delta('two'), item('item/completed', 'onetwo')))
        self.assertEqual(result, [dict(type='delta', text='one'), dict(type='delta', text='two'), dict(type='completed', text='onetwo')])
        sent = process.sent()
        self.assertEqual([m['method'] for m in sent], ['initialize', 'initialized', 'thread/start', 'turn/start'])
        self.assertEqual(sent[2]['params']['approvalPolicy'], 'never')
        self.assertEqual(sent[2]['params']['sandbox'], 'read-only')
        self.assertTrue(sent[2]['params']['ephemeral'])
        self.assertEqual(sent[3]['params']['input'], [dict(type='text', text='hello')])

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

    def test_terminal_waits_for_exit_and_revocation_and_close_kills_partial_child(self):
        for partial in [False, True]:
            gateway = Gateway(); process = FakeProcess(answer() if partial else transcript(item('item/started'), item('item/completed', 'answer')))
            with tempfile.TemporaryDirectory() as directory:
                adapter = NativeCodexChatAdapter(jobs_dir=directory, enabled=True, source_gateway=gateway, popen=lambda *a, **k: process)
                stream = adapter.stream(prompt='hello', timeout_seconds=2)
                self.assertEqual(next(stream)['type'], 'delta' if partial else 'completed')
                if not partial:
                    self.assertGreaterEqual(process.wait_calls, 1); self.assertEqual(gateway.revoked, 'job-capability')
                stream.close()
            if partial: self.assertTrue(process.killed)
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

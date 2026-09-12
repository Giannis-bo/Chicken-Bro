import importlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from uuid import UUID
from unittest.mock import patch


class ChickenbroSkillToolTest(unittest.TestCase):
    def test_tool_advertises_only_four_fixed_names(self):
        mcp = importlib.import_module('server.chickenbro_native_mcp')
        definitions = {item['name']: item for item in mcp.handle_rpc_request(
            {'id': 1, 'method': 'tools/list'})['result']['tools']}
        self.assertIn('read_chickenbro_skill', definitions)
        definition = definitions['read_chickenbro_skill']
        schema = definition['inputSchema']
        self.assertEqual(schema['required'], ['skillId'])
        self.assertEqual(set(schema['properties']), {'skillId'})
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(schema['properties']['skillId']['enum'],
                         ['mechanics', 'wcl-analysis', 'rankings', 'simc-experiment'])
        self.assertTrue(definition['annotations']['readOnlyHint'])


class ChickenbroSkillLoaderTest(unittest.TestCase):
    def setUp(self):
        self.mcp = importlib.import_module('server.chickenbro_native_mcp')
        self.assertTrue(hasattr(self.mcp, 'read_chickenbro_skill'), 'Skill loader is not implemented')
        self.loader = importlib.import_module('server.app.chickenbro.agent_skills')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'agent' / 'skills'
        self.root.mkdir(parents=True)
        patcher = patch.object(self.loader, '_SKILLS_ROOT', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(self, arguments):
        observations = []
        with patch.object(self.mcp, 'urlopen', side_effect=AssertionError('Unexpected upstream call')), \
                patch.object(self.mcp, 'query_source_gateway', side_effect=AssertionError('Research budget touched')), \
                patch.object(self.mcp, 'query_simulation_gateway', side_effect=AssertionError('Simulation budget touched')):
            response = self.mcp.handle_rpc_request({'id': 1, 'method': 'tools/call', 'params': {
                'name': 'read_chickenbro_skill', 'arguments': arguments}}, observation_writer=observations.append)
        self.assertFalse(response['result']['isError'])
        result = json.loads(response['result']['content'][0]['text'])
        self.assertNotIn(Path(self.tmp.name).name, json.dumps([result, observations]))
        return result

    def test_all_names_return_exact_utf8_content_and_raw_byte_digest(self):
        for skill_id in ['mechanics', 'wcl-analysis', 'rankings', 'simc-experiment']:
            for newline in ['\n', '\r\n']:
                raw = ('# 流程' + newline + 'Evidence first.' + newline).encode('utf-8')
                (self.root / (skill_id + '.md')).write_bytes(raw)
                result = self.call({'skillId': skill_id})
                self.assertEqual(result['status'], 'available')
                self.assertEqual(result['skillId'], skill_id)
                self.assertEqual(result['content'], raw.decode('utf-8'))
                self.assertEqual(result['version'], 'sha256:' + hashlib.sha256(raw).hexdigest())

    def test_invalid_arguments_are_rejected_without_echoing_input(self):
        for args in [None, [], 'mechanics', {}, {'skillId': None}, {'skillId': []},
                     {'skillId': 1}, {'skillId': True}, {'skillId': 'unknown'},
                     {'skillId': '../secret'}, {'skillId': 'C:\\secret'},
                     {'skillId': 'https://secret.test'}, {'skillId': ' mechanics'},
                     {'skillId': 'mechanics', 'path': '/secret'},
                     {'skillId': 'mechanics', 'user_id': 'other'}]:
            with self.subTest(args=args):
                result = self.call(args)
                self.assertEqual(result['status'], 'unavailable')
                self.assertEqual(result['errorCode'], 'SKILL_ARGUMENTS_INVALID')
                self.assertNotIn('content', result)
                self.assertNotIn('secret', json.dumps(result))

    def test_missing_empty_invalid_utf8_and_oversized_files_fail_safely(self):
        result = self.call({'skillId': 'mechanics'})
        self.assertEqual(result['status'], 'unavailable')
        for raw in [b'', b' \r\n\t', b'\xff', b'x' * 16385, '中'.encode() * 5462]:
            (self.root / 'mechanics.md').write_bytes(raw)
            result = self.call({'skillId': 'mechanics'})
            self.assertEqual(result['status'], 'unavailable')
            self.assertNotIn('content', result)
        (self.root / 'mechanics.md').write_bytes(b'x' * 16384)
        self.assertEqual(self.call({'skillId': 'mechanics'})['status'], 'available')

    def test_directory_cannot_be_read_as_skill(self):
        (self.root / 'mechanics.md').mkdir()
        self.assertEqual(self.call({'skillId': 'mechanics'})['status'], 'unavailable')

    def test_observation_audits_only_valid_skill_identity_and_digest(self):
        packet = {'sourceKey': 'chickenbro_skill', 'status': 'available', 'skillId': 'mechanics',
                  'version': 'sha256:' + 'a' * 64, 'content': 'Do not log this workflow.'}
        observation = self.mcp._safe_observation(packet, tool_name='read_chickenbro_skill')
        self.assertEqual(observation.get('skillId'), 'mechanics')
        self.assertEqual(observation.get('version'), packet['version'])
        self.assertEqual(observation['sourceKey'], 'chickenbro_skill')
        self.assertNotIn('content', observation)
        for changes in [{'skillId': '/secret'}, {'version': '/secret'}, {'version': 'sha256:' + 'g' * 64}]:
            observation = self.mcp._safe_observation({**packet, **changes}, tool_name='read_chickenbro_skill')
            self.assertNotIn('secret', json.dumps(observation))
            self.assertFalse('skillId' in observation and 'version' in observation)

    def test_symlink_file_and_directory_are_rejected(self):
        outside = Path(self.tmp.name) / 'outside'
        outside.mkdir()
        (outside / 'mechanics.md').write_text('outside content', encoding='utf-8')
        link = self.root / 'mechanics.md'
        try:
            link.symlink_to(outside / 'mechanics.md')
        except OSError as exc:
            self.skipTest('Host cannot create symlinks: ' + str(exc.winerror if os.name == 'nt' else exc.errno))
        self.assertEqual(self.call({'skillId': 'mechanics'})['status'], 'unavailable')
        link.unlink()
        self.root.rmdir()
        self.root.symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.call({'skillId': 'mechanics'})['status'], 'unavailable')

    def test_read_failure_never_leaks_exception_path(self):
        (self.root / 'mechanics.md').write_text('safe', encoding='utf-8')
        with patch('os.open', side_effect=PermissionError('/sensitive/secret')):
            result = self.call({'skillId': 'mechanics'})
        self.assertEqual(result['status'], 'unavailable')
        self.assertNotIn('secret', json.dumps(result))

    @unittest.skipUnless(os.name == 'nt', 'Windows junction check')
    def test_windows_directory_junction_cannot_redirect_release_content(self):
        outside = Path(self.tmp.name) / 'outside'
        outside.mkdir()
        (outside / 'mechanics.md').write_text('outside content', encoding='utf-8')
        self.root.rmdir()
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(self.root), str(outside)],
                       check=True, capture_output=True)
        try:
            self.assertEqual(self.call({'skillId': 'mechanics'})['status'], 'unavailable')
        finally:
            self.root.rmdir()


class PackagedChickenbroSkillTest(unittest.TestCase):
    def test_actual_core_rules_load_and_fit_with_both_newline_formats(self):
        adapter = importlib.import_module('server.app.chickenbro.codex_adapter')
        path = Path(__file__).resolve().parents[1] / 'server/app/chickenbro/agent/AGENTS.md'
        raw = path.read_bytes()
        self.assertEqual(adapter._load_agent_rules(), raw.decode('utf-8'))
        lf = raw.replace(b'\r\n', b'\n')
        for variant in [lf, lf.replace(b'\n', b'\r\n')]:
            self.assertLessEqual(len(variant), 10 * 1024)
            with tempfile.TemporaryDirectory() as tmp:
                fixture = Path(tmp) / 'AGENTS.md'
                fixture.write_bytes(variant)
                with patch.object(adapter, '_AGENT_RULES_PATH', fixture):
                    self.assertEqual(adapter._load_agent_rules(), variant.decode('utf-8'))

    def test_actual_release_workflows_are_loadable_with_newline_headroom(self):
        loader = importlib.import_module('server.app.chickenbro.agent_skills')
        root = Path(__file__).resolve().parents[1] / 'server/app/chickenbro/agent/skills'
        for skill_id in ['mechanics', 'wcl-analysis', 'rankings', 'simc-experiment']:
            raw = (root / (skill_id + '.md')).read_bytes()
            result = loader.read_chickenbro_skill({'skillId': skill_id})
            self.assertEqual(result['status'], 'available')
            self.assertEqual(result['content'], raw.decode('utf-8'))
            self.assertEqual(result['version'], 'sha256:' + hashlib.sha256(raw).hexdigest())
            lf = raw.replace(b'\r\n', b'\n')
            for variant in [lf, lf.replace(b'\n', b'\r\n')]:
                self.assertLessEqual(len(variant), 16 * 1024)
                with tempfile.TemporaryDirectory() as tmp:
                    fixture_root = Path(tmp)
                    (fixture_root / (skill_id + '.md')).write_bytes(variant)
                    with patch.object(loader, '_SKILLS_ROOT', fixture_root):
                        self.assertEqual(loader.read_chickenbro_skill({'skillId': skill_id})['content'],
                                         variant.decode('utf-8'))


class ChickenbroJobRunIdentityTest(unittest.TestCase):
    def test_two_jobs_bind_only_their_distinct_server_run_uuid(self):
        adapter = importlib.import_module('server.app.chickenbro.codex_adapter')
        self.assertTrue(hasattr(adapter, '_bind_job_run'))
        with tempfile.TemporaryDirectory() as tmp:
            for name, run_id in [('one', UUID('12345678-1234-1234-1234-123456789abc')),
                                 ('two', '87654321-1234-1234-1234-123456789ABC')]:
                job = Path(tmp) / name
                job.mkdir()
                adapter._bind_job_run(job, SimpleNamespace(run_id=run_id, user_id='secret-owner', token='secret-token'))
                self.assertEqual(json.loads((job / 'run-identity.json').read_text()),
                                 {'runId': str(run_id).lower()})

    def test_missing_and_invalid_context_never_write_identity_or_secrets(self):
        adapter = importlib.import_module('server.app.chickenbro.codex_adapter')
        self.assertTrue(hasattr(adapter, '_bind_job_run'))
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp)
            for context in [None, SimpleNamespace(), *[SimpleNamespace(run_id=value) for value in
                    [None, 123, [], 'run', '../secret', 'secret-token', '12345678123412341234123456789abc']]]:
                adapter._bind_job_run(job, context)
                self.assertEqual(list(job.iterdir()), [])

    def test_stream_binds_before_spawning_runtime_and_fails_closed_on_write_error(self):
        adapter = importlib.import_module('server.app.chickenbro.codex_adapter')
        fixtures = importlib.import_module('tests.app_chickenbro_codex_adapter_test')
        run_id = '12345678-1234-1234-1234-123456789abc'
        captured = []
        def popen(*args, **kwargs):
            captured.append(json.loads((Path(kwargs['cwd']) / 'run-identity.json').read_text()))
            return fixtures.FakeProcess(fixtures.answer())
        with tempfile.TemporaryDirectory() as tmp:
            runtime = adapter.NativeCodexChatAdapter(jobs_dir=tmp, enabled=True, popen=popen)
            output = list(runtime.stream(prompt='private prompt', timeout_seconds=2,
                                         tool_context=SimpleNamespace(run_id=run_id)))
            self.assertEqual(output[-1]['type'], 'completed')
            self.assertEqual(captured, [{'runId': run_id}])
            with patch.object(Path, 'write_text', side_effect=PermissionError('private path')):
                with self.assertRaises(adapter.CodexUnavailable):
                    list(runtime.stream(prompt='private prompt', timeout_seconds=2,
                                        tool_context=SimpleNamespace(run_id=run_id)))
            self.assertEqual(len(captured), 1)


if __name__ == '__main__':
    unittest.main()

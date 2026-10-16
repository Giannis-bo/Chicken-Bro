"""The official product is independent of the retired personal QQ transport."""
import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
from tests.app_chickenbro_codex_adapter_test import FakeProcess, answer

ROOT = Path(__file__).resolve().parents[1]

class OfficialIntegrationTests(unittest.TestCase):
    def test_policy_and_repository_import_without_retired_package(self):
        self.assertFalse((ROOT / 'server/app/channels/qq').exists())
        policy = importlib.import_module('server.app.channels.qq_official.policy')
        repo = importlib.import_module('server.app.channels.qq_official.repository')
        event = policy.Trigger('official:test', 'group', 'member', 'msg', '/帮助')
        self.assertEqual(event.text, '/帮助')
        self.assertEqual(repo.OfficialRepository.__bases__, (object,))

    def test_official_bootstrap_does_not_need_historical_napcat_sql(self):
        sql = (ROOT / 'server/qq-official/000_schema.sql').read_text()
        for table in ('principals', 'inbox', 'outbox'):
            self.assertIn('qq_channel.' + table, sql)
        self.assertNotIn('companion_responses', sql)
        self.assertNotIn('ALTER TABLE chat.executions', sql)

    def test_tool_free_adapter_cannot_receive_gateways_or_empty_rules(self):
        for kw in ({'source_gateway': object()}, {'simulation_gateway': object()}, {'poe2_gateway': object()}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                NativeCodexChatAdapter(tool_free_instructions='trusted bounded rules', **kw)
        with self.assertRaises(ValueError):
            NativeCodexChatAdapter(tool_free_instructions='')

    def test_tool_free_adapter_uses_trusted_rules_and_disables_inherited_tools(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {'CODEX_HOME': tmp}):
            Path(tmp,'config.toml').write_text('model="gpt-6-astra"\n[mcp_servers.untrusted]\ncommand="/bin/false"\n')
            process=FakeProcess(answer())
            adapter=NativeCodexChatAdapter(jobs_dir=tmp,enabled=True,
                tool_free_instructions='trusted bounded rules',popen=lambda *a,**kw:process)
            self.assertEqual(list(adapter.stream(prompt='hello',timeout_seconds=10))[-1]['text'],'answer')
            params=process.sent()[2]['params'];self.assertEqual(params['developerInstructions'],'trusted bounded rules')
            self.assertEqual(params['config']['web_search'],'disabled')
            self.assertTrue(all(v['enabled'] is False for v in params['config']['mcp_servers'].values()))
            for key in ('shell_tool','apps','plugins','multi_agent','browser_use'):
                self.assertFalse(params['config']['features'][key])

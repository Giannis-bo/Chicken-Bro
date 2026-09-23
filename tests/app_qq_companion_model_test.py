import importlib
import unittest

class CompanionModelTest(unittest.TestCase):
    def module(self,name):
        self.assertIsNotNone(importlib.util.find_spec('server.app.channels.qq.'+name),name+' missing')
        return importlib.import_module('server.app.channels.qq.'+name)
    def test_social_disables_inherited_tools_without_mutation(self):
        m=self.module('execution_policy');src={'web_search':'live'}
        p=m.social_profile(src,{'extra':{'command':'private-tool'}})
        self.assertEqual(p['web_search'],'disabled');self.assertFalse(p['mcp_servers']['extra']['enabled'])
        self.assertFalse(p['features']['shell_tool']);self.assertEqual(src,{'web_search':'live'})
    def test_strict_decision_schema(self):
        m=self.module('companion_model')
        self.assertEqual(m.parse_decision('{"action":"reply","text":"鸡哥在"}').draft.text,'鸡哥在')
        for bad in ['{"action":"reply","shell":"cat /etc/passwd"}','not json','{"action":"reply","text":""}',
                    '{"action":"silent","text":"发出去"}','{"action":"reply","text":12}',
                    '{"action":"reply","sticker_id":"../../secret"}']:
            with self.assertRaises(ValueError):m.parse_decision(bad)
    def test_adapter_social_rejects_gateways(self):
        from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
        import inspect
        self.assertIn('qq_scope',inspect.signature(NativeCodexChatAdapter).parameters)
        with self.assertRaises(ValueError):NativeCodexChatAdapter(qq_scope='social',simulation_gateway=object())
    def test_quote_is_opt_in_and_strict_boolean(self):
        m=self.module('companion_model')
        self.assertFalse(m.parse_decision('{"action":"reply","text":"诶"}').draft.quote)
        self.assertTrue(m.parse_decision('{"action":"reply","text":"这条我赞同","quote":true}').draft.quote)
        for value in ('"true"','1','null'):
            with self.assertRaises(ValueError):m.parse_decision('{"action":"reply","text":"诶","quote":'+value+'}')

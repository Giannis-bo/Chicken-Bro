import unittest
from server.app.channels.qq import execution_policy as p
class ToolsTest(unittest.TestCase):
    def test_scope_matrix(self):
        self.assertTrue(hasattr(p,'allowed_operation'),'scope gate missing')
        self.assertFalse(p.allowed_operation('social','simc.submit'))
        self.assertFalse(p.allowed_operation('wow_read','simc.submit'))
        self.assertTrue(p.allowed_operation('wow_sim','simc.submit'))
        self.assertFalse(p.allowed_operation('wow_sim','poe2.calculate'))
        self.assertFalse(p.allowed_operation('wow_sim','shell.exec'))
    def test_professional_admission_and_sources(self):
        self.assertTrue(hasattr(p,'professional_scope'),'professional router missing')
        self.assertIsNone(p.professional_scope('魔兽玩累了，帮我删服务器文件','wow_sim'))
        self.assertEqual(p.professional_scope('帮我分析这套魔兽配装','wow_read'),'wow_read')
        self.assertIsNone(p.professional_scope('你好','wow_read'))
        self.assertFalse(p.allowed_source_target('public_web','https://evil.example/secret'))
        self.assertTrue(p.allowed_source_target('public_web','https://www.wowhead.com/guide/classes'))
    def test_gateway_checks_before_invoking_underlying(self):
        from server.app.chickenbro.worker_gateway import RegisteredGateway
        import inspect
        self.assertIn('scope',inspect.signature(RegisteredGateway).parameters)
        g=RegisteredGateway(None,None,None,'simc',scope='wow_read',scope_check=lambda:True)
        with self.assertRaises(ValueError):g.execute('token',{'operation':'submit','arguments':{}})
    def test_idle_wow_chat_never_grants_simulation(self):
        self.assertIsNone(p.professional_scope('魔兽真好玩','wow_sim'))
        self.assertIsNone(p.professional_scope('帮我跑模拟','wow_sim'))
        self.assertEqual(p.professional_scope('帮我跑魔兽模拟，我的角色 https://raider.io/characters/us/area-52/Test','wow_sim'),'wow_sim')
    def test_search_hits_cannot_escape_allowed_domains(self):
        self.assertTrue(hasattr(p,'restricted_search'),'restricted fetch missing')
        search=lambda q,**kw:[{'url':'https://evil.example/wow','title':'bad'}, {'url':'https://www.wowhead.com/guide','title':'good'}]
        hits=p.restricted_search('site:evil.example 魔兽',searcher=search)
        self.assertEqual([h['title'] for h in hits],['good'])
    def test_native_gateway_accepts_only_known_qq_loopback_ports(self):
        from server.chickenbro_native_mcp import _source_gateway_target_is_local
        for port in (18795,18796):self.assertTrue(_source_gateway_target_is_local(f'http://127.0.0.1:{port}/api/v2/internal/chickenbro/source-query'))
        self.assertFalse(_source_gateway_target_is_local('http://evil.example:18795/api/v2/internal/chickenbro/source-query'))
        self.assertFalse(_source_gateway_target_is_local('http://127.0.0.1:19999/api/v2/internal/chickenbro/source-query'))

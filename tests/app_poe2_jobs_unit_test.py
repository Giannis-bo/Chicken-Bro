import unittest
from datetime import datetime,timezone
from types import SimpleNamespace
from uuid import uuid4
from server.app.identity.domain import Principal
from server.app.poe2.domain import Poe2Build
from server.app.poe2.tools import Poe2ToolGateway, Poe2ToolUnauthorized


class Poe2ToolTests(unittest.TestCase):
    def test_worker_process_identity_is_unique(self):
        from server.app.poe2.worker import Poe2Worker
        first=Poe2Worker(object(),object()); second=Poe2Worker(object(),object())
        self.assertNotEqual(first.worker_id,second.worker_id)

    def test_import_get_are_summaries_and_large_export_is_explicitly_blocked(self):
        owner=uuid4(); build=Poe2Build(uuid4(),owner,'x','<PathOfBuilding2><Build/></PathOfBuilding2>',
            '0.3','Standard','a'*64,'engine','code',{},datetime.now(timezone.utc))
        class Application:
            def import_build(self,*args,**kwargs):return build
            def read_build(self,*args,**kwargs):return build
            def export(self,*args,**kwargs):return {'buildId':str(build.id),'exportCode':'x'*180000,
                'inputSha256':'a'*64,'engineVersion':'engine'}
        gateway=Poe2ToolGateway(Application()); principal=Principal(owner,'web_cookie')
        token=gateway.issue_capability(SimpleNamespace(game='poe2',principal=principal))
        imported=gateway.execute(token,'import',{'source':'xml'})
        fetched=gateway.execute(token,'get',{'buildId':str(build.id)})
        exported=gateway.execute(token,'export',{'buildId':str(build.id)})
        self.assertNotIn('source',imported); self.assertNotIn('source',fetched)
        self.assertEqual(exported['buildId'],str(build.id))
        self.assertEqual(exported['errorCode'],'POE2_EXPORT_TOO_LARGE')
        self.assertNotIn('exportCode',exported)

    def test_worker_gateway_has_bounded_large_poe2_import_and_explicit_export(self):
        from server.app.chickenbro.worker_gateway import tool_request_limit,tool_response_limit
        self.assertGreaterEqual(tool_request_limit('poe2'),4_000_000)
        self.assertEqual(tool_request_limit('simc'),32768)
        self.assertEqual(tool_response_limit('poe2.export'),180000)
        self.assertEqual(tool_response_limit('poe2.get'),180000)

    def test_capability_requires_poe2_and_revoke(self):
        gateway=Poe2ToolGateway(object())
        principal=Principal(uuid4(),'web_cookie')
        with self.assertRaises(ValueError):gateway.issue_capability(SimpleNamespace(game='wow',principal=principal))
        token=gateway.issue_capability(SimpleNamespace(game='poe2',principal=principal))
        gateway.revoke_capability(token)
        with self.assertRaises(Poe2ToolUnauthorized):gateway.answer_evidence(token)

    def test_operation_allowlist(self):
        gateway=Poe2ToolGateway(object()); principal=Principal(uuid4(),'web_cookie')
        token=gateway.issue_capability(SimpleNamespace(game='poe2',principal=principal))
        with self.assertRaises(ValueError):gateway.execute(token,'arbitrary',{})

if __name__=='__main__':unittest.main()

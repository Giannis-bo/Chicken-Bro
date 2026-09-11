import json
import tempfile
import unittest
from uuid import uuid4
from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
from server.app.identity.domain import Principal
from tests.app_chickenbro_codex_adapter_test import FakeProcess, transcript, item, delta, replacement
from server.app.chickenbro.answer_grounding import collect_evidence, validate_answer, repair_context

class IntegrationTest(unittest.TestCase):
    def test_simulation_unobserved_completion_repaired_before_delivery_and_evidence_revoked(self):
        class Gateway:
            revoked=False
            def issue_capability(self,context):return 'sim-token'
            def answer_evidence(self,token):
                assert not self.revoked
                return {'jobs':{},'comparisons':[]}
            def revoke(self,token):self.revoked=True
        gateway=Gateway()
        bad='本次模拟已完成。'
        good='尚未取得本次模拟结果。'
        calls=[]
        def popen(*args,**kwargs):
            calls.append(kwargs)
            return FakeProcess(transcript(item('item/started'),delta(bad),item('item/completed',bad))) if len(calls)==1 else FakeProcess(replacement(bad,good))
        with tempfile.TemporaryDirectory() as directory:
            adapter=NativeCodexChatAdapter(enabled=True,jobs_dir=directory,popen=popen,simulation_gateway=gateway)
            events=list(adapter.stream_for_chat(principal=Principal(uuid4(),'web_cookie'),conversation_id=uuid4(),run_id=uuid4(),prompt='模拟结果呢',timeout_seconds=30))
        self.assertEqual(events[-1]['text'],good)
        self.assertEqual(len(calls),2)
        self.assertTrue(gateway.revoked)
        self.assertNotIn(bad,str(events))

    def test_partial_history_is_not_promoted_by_verified_wrapper(self):
        result={'sourceKey':'warcraftlogs','status':'verified','facts':[{'reportCode':'AAAAAAAAAAAAAAAA','fightId':1,'sourceId':7,'status':'partial','view':'statistics','statistics':{'complete':False}}]}
        evidence=collect_evidence({},result)
        self.assertEqual(evidence['reports'][0]['status'],'partial')

    def test_simulation_context_survives_large_wcl_repair_projection(self):
        evidence={'reports':[],'groups':[],'simulation':{'jobs':{'job':{'status':'queued'}},'comparisons':[]},'unused':'x'*70000}
        self.assertEqual(json.loads(repair_context(evidence)).get('simulation'),evidence['simulation'])

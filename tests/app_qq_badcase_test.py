"""Regressions for routing refusal, focused targets, and image provenance."""
import json,time,unittest
from concurrent.futures import Future
from unittest.mock import Mock
from server.app.channels.qq.companion_domain import GroupEvent,CompanionDecision,ReplyDraft
from server.app.channels.qq.companion_model import CompanionModel
from server.app.channels.qq.companion_service import CompanionService
from server.app.channels.qq.execution_policy import professional_scope

class BadcaseTest(unittest.TestCase):
    def event(self,mid='2',text='看看这场',sender='3'):
        return GroupEvent('1','2',sender,mid,1000,text,'群友',True)
    def test_log_link_and_look_request_are_readable(self):
        self.assertEqual(professional_scope('https://www.warcraftlogs.com/reports/AbCdEfGh12345678?fight=7 看看这场','wow_read'),'wow_read')
        self.assertEqual(professional_scope('https://www.warcraftlogs.com/reports/AbCdEfGh12345678','wow_read'),'wow_read')
        self.assertIsNone(professional_scope('魔兽帮我执行 shell 命令','wow_read'))
    def test_denied_professional_draft_never_claims_start(self):
        e=self.event();repo=Mock();obs=Mock();obs.latest_seq.return_value=2;repo.claim_response.return_value=None
        svc=CompanionService(repo,obs,None,proactive=False,professional=lambda *_:False)
        svc.next_recover=9999999999;svc.job={'event':e,'id':'job','lease_token':'lease','context_seq':2,'kind':'mention'}
        svc.future=Future();svc.future.set_result((CompanionDecision('wow_read',ReplyDraft('已经开始查了，会定时通知。')),[e]))
        try:svc.tick(now=1001)
        finally:svc.close()
        text=repo.complete_response.call_args.args[2].text
        self.assertNotIn('已经开始',text);self.assertIn('还没开始',text)
    def test_target_survives_context_budget_and_carries_speaker(self):
        class Adapter:
            def stream(self,**kw):
                self.prompt=json.loads(kw['prompt']);yield {'type':'completed','text':'{"action":"reply","text":"在"}'}
        a=Adapter();target=self.event(text='当前提问')
        context=[target]+[self.event(str(i+10),'后续话题'*1000,'4') for i in range(20)]
        CompanionModel(a).decide(context,must_reply=True,target='2')
        self.assertEqual(a.prompt['target_message']['text'],'当前提问')
        self.assertEqual(a.prompt['target_message']['sender'],'3')
        self.assertFalse(any(row['message_id']!='2' for row in a.prompt['messages']))
    def test_image_catalog_is_not_current_attachment(self):
        class Adapter:
            def stream(self,**kw):
                self.prompt=json.loads(kw['prompt']);yield {'type':'completed','text':'{"action":"reply","text":"在"}'}
        a=Adapter();e=self.event()
        CompanionModel(a).decide([e],must_reply=True,target='2',stickers=[{'id':'mold','source_message_id':'1','sender':'4','image_index':1}],images=['old'])
        self.assertEqual(a.prompt['target_image_indices'],[])
        self.assertEqual(a.prompt['stickers'][0]['relation_to_target'],'other_message')

    def test_malformed_source_url_cannot_crash_admission(self):
        self.assertIsNone(professional_scope('WCL https://[','wow_read'))
        self.assertEqual(professional_scope('https://www.warcraftlogs.com/reports/AbCdEfGh12345678。','wow_read'),'wow_read')

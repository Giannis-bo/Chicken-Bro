import importlib
import unittest
from server.app.channels.qq.companion_domain import CompanionDecision,ReplyDraft

class CompanionServiceTest(unittest.TestCase):
    def module(self):
        name='server.app.channels.qq.companion_service'
        self.assertIsNotNone(importlib.util.find_spec(name),'companion service missing')
        return importlib.import_module(name)
    def test_mandatory_silent_and_failure_have_natural_reply(self):
        f=self.module().must_reply_draft
        self.assertEqual(f(CompanionDecision('silent'),'鸡哥在').text,'鸡哥在')
        self.assertEqual(f(CompanionDecision('reply',ReplyDraft('来了')),'fallback').text,'来了')
    def test_proactive_has_no_quota_or_random_gate(self):
        m=self.module()
        self.assertFalse(m.should_discard_proactive(decision_seq=4,current_seq=4))
        self.assertTrue(m.should_discard_proactive(decision_seq=4,current_seq=5))
    def test_meme_search_gets_one_visual_followup_and_rejects_unseen_image(self):
        from unittest.mock import Mock
        from server.app.channels.qq.companion_domain import GroupEvent
        e=GroupEvent('1','2','3','4',1000,'吃瓜','群友',True)
        repo=Mock();repo.recent_replies.return_value=[]
        observations=Mock();observations.context.return_value=[e]
        media=Mock();media.prepare.return_value=([],[])
        media.search.return_value=([{'id':'mfound'}],['data:image/png;base64,preview'])
        model=Mock();model.decide.side_effect=[
            CompanionDecision('reply',meme_query='吃瓜'),
            CompanionDecision('reply',ReplyDraft('一起吃瓜','munseen'),meme_query='再搜索')]
        service=self.module().CompanionService(repo,observations,model,stickers=media)
        try:decision,_=service._decide({'event':e,'kind':'mention'})
        finally:service.close()
        media.search.assert_called_once_with(e,'吃瓜')
        self.assertEqual(model.decide.call_count,2)
        self.assertEqual(model.decide.call_args.kwargs['images'],['data:image/png;base64,preview'])
        self.assertFalse(model.decide.call_args.kwargs['meme_search_available'])
        self.assertIsNone(decision.draft.sticker_id)
        self.assertEqual(decision.draft.text,'一起吃瓜')

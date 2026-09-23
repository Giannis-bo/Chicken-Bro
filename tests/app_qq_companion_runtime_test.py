import unittest
from server.app.channels.qq import runtime
from server.app.channels.qq.companion_domain import ReplyDraft
from server.app.channels.qq.onebot import OneBotError

class Repo:
    def __init__(self):self.done=[]
    def pending_outbox(self):return [{'id':'one','group_id':'22','message_id':'42','text':'笑死','sticker_id':'bad'}]
    def begin_send(self,id):return not self.done
    def finish_send(self,id,receipt=None):self.done.append(receipt)
class Transport:
    def __init__(self,error=False):self.calls=[];self.error=error
    def call(self,action,params):
        self.calls.append(params)
        if self.error:raise OneBotError('receipt timeout')
        return {'message_id':99}
class RuntimeTest(unittest.TestCase):
    def test_unquoted_image_failure_keeps_fallback_unquoted(self):
        class DirectRepo(Repo):
            def pending_outbox(self):return [{**super().pending_outbox()[0],'quote_reply':False}]
        class Catalog:
            def resolve(self,id):raise ValueError('unknown')
        r=DirectRepo();t=Transport();runtime.deliver_one(r,t,('22',),Catalog())
        self.assertEqual([x['type'] for x in t.calls[0]['message']],['text'])
    def test_mode_strict_and_worker_consistent(self):
        self.assertEqual(runtime.companion_options({},{}),(False,False))
        self.assertEqual(runtime.companion_options({'mode':'companion','proactiveEnabled':True},{'WOW_QQ_COMPANION_ENABLED':'1'}),(True,True))
        with self.assertRaises(ValueError):runtime.companion_options({'mode':'companion'}, {})
        with self.assertRaises(ValueError):runtime.companion_options({'mode':'x'}, {})
    def test_local_image_failure_falls_back_once_before_send(self):
        class Catalog:
            def resolve(self,id):raise ValueError('unknown')
        r=Repo();t=Transport();self.assertTrue(runtime.deliver_one(r,t,('22',),Catalog()))
        self.assertEqual(len(t.calls),1);self.assertEqual([x['type'] for x in t.calls[0]['message']],['reply','text'])
    def test_uncertain_image_has_no_second_send(self):
        r=Repo();t=Transport(True)
        with self.assertRaises(OneBotError):runtime.deliver_one(r,t,('22',))
        self.assertEqual(len(t.calls),1);self.assertEqual(r.done,[None])
    def test_proven_pre_handler_rejection_can_fallback_once(self):
        from unittest.mock import patch
        from server.app.channels.qq.onebot import OneBotRejected
        class RejectImage(Transport):
            def call(self,action,params):
                self.calls.append(params)
                if len(self.calls)==1:raise OneBotRejected('schema rejected')
                return {'message_id':99}
        r=Repo();t=RejectImage()
        with patch('server.app.channels.qq.stickers.render_reply',return_value=[{'type':'image','data':{'file':'base64://AA=='}}]):
            self.assertTrue(runtime.deliver_one(r,t,('22',),object()))
        self.assertEqual(len(t.calls),2);self.assertEqual([x['type'] for x in t.calls[1]['message']],['reply','text'])

import copy
import unittest


class QqPolicyTest(unittest.TestCase):
    def setUp(self):
        from server.app.channels.qq import policy
        self.policy = policy
        self.config = policy.ChannelConfig(bot_qq='12345', allowed_groups=('56789',), enabled=True)
        self.event = dict(post_type='message', message_type='group', self_id=12345,
            group_id=56789, user_id=98765, message_id=42, time=1000,
            message=[{'type':'at','data':{'qq':'12345'}},{'type':'text','data':{'text':' 怎样提升伤害？'}}])

    def test_only_fresh_real_at_in_allowed_group_is_accepted(self):
        got = self.policy.parse_event(self.event, self.config, now=1001)
        self.assertEqual(got.text, '怎样提升伤害？')
        for patch in [dict(self_id=22222),dict(group_id=99999),dict(user_id=12345),
                      dict(message_type='private'),dict(time=800),dict(time=1100),
                      dict(post_type='notice'),dict(message='[CQ:at,qq=12345] 问题'),
                      dict(message=[{'type':'text','data':{'text':'[CQ:at,qq=12345] 问题'}}])]:
            with self.subTest(patch=patch):
                self.assertIsNone(self.policy.parse_event({**self.event,**patch},self.config,now=1001))
        self.assertIsNone(self.policy.parse_event(self.event,self.policy.ChannelConfig('12345',('56789',),False),now=1001))

    def test_malformed_segments_and_oversized_messages_do_not_crash_or_enter_ai(self):
        for message in [None, [None], [{'type':'at','data':None}], self.event['message']+[{'type':'text','data':{'text':'x'*4100}}]]:
            event={**self.event,'message':message}
            result=self.policy.parse_event(event,self.config,now=1001)
            self.assertTrue(result is None or result.error)

    def test_image_input_gets_explicit_unsupported_reply_instead_of_hallucination(self):
        event=copy.deepcopy(self.event);event['message'].append({'type':'image','data':{'url':'http://127.0.0.1/secret'}})
        got=self.policy.parse_event(event,self.config,now=1001)
        self.assertTrue(got.error)

    def test_replies_are_bounded_and_control_codes_remain_text(self):
        chunks=self.policy.split_reply('结论\n\n'+'x'*9000+'[CQ:at,qq=all]')
        self.assertLessEqual(len(chunks),5)
        self.assertTrue(all(len(c)<=1500 for c in chunks))
        self.assertIn('过长',chunks[-1])
        segments=self.policy.reply_segments(42,'[CQ:at,qq=all]')
        self.assertEqual(segments,[{'type':'reply','data':{'id':'42'}},{'type':'text','data':{'text':'[CQ:at,qq=all]'}}])

if __name__=='__main__':unittest.main()

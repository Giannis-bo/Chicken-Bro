import json
import unittest
from server.app.chickenbro.application import ChatApplication

class ContextTest(unittest.TestCase):
    def prompt(self, history):
        return json.loads(ChatApplication._prompt(history, ''))

    def test_original_constraints_and_later_correction_survive_recent_history_cutoff(self):
        history=[{'id':'goal','role':'user','content':'角色甲，只分析最后20秒，不换装备。'},
                 {'id':'correction','role':'user','content':'更正：看最后30秒，仍不换装备。'}]
        history += [{'role':'assistant','content':'中间解释'} for _ in range(21)]
        history += [{'role':'user','content':'按刚才条件继续。'}]
        data=self.prompt(history)
        turns=data.get('researchContext',{}).get('earlierUserMessages',[])
        self.assertEqual([t['content'] for t in turns],['角色甲，只分析最后20秒，不换装备。','更正：看最后30秒，仍不换装备。'])
        self.assertEqual([t['messageId'] for t in turns],['goal','correction'])
        self.assertFalse(data['researchContext']['truncated'])

    def test_new_research_drops_old_constraints_but_quoted_command_does_not(self):
        data=self.prompt([{'role':'user','content':'旧角色甲'}, {'role':'user','content':'/新研究\n只研究角色乙'}])
        self.assertNotIn('旧角色甲',json.dumps(data,ensure_ascii=False))
        data=self.prompt([{'role':'user','content':'旧角色甲'}, {'role':'assistant','content':'/新研究\n这是引用'}])
        self.assertIn('旧角色甲',json.dumps(data,ensure_ascii=False))

    def test_large_context_is_bounded_explicit_and_preserves_first_and_latest_old_request(self):
        history=[{'id':str(i),'role':'user','content':str(i)+':'+('约束'*1800)} for i in range(50)]
        data=self.prompt(history)
        ctx=data.get('researchContext',{})
        self.assertTrue(ctx.get('truncated'))
        self.assertLess(len(json.dumps(ctx,ensure_ascii=False).encode()),26000)
        self.assertEqual(ctx['earlierUserMessages'][0]['messageId'],'0')
        self.assertEqual(ctx['earlierUserMessages'][-1]['messageId'],'29')
        self.assertGreater(ctx['omittedMessages'],0)

    def test_assistant_instructions_never_promoted_to_user_constraints(self):
        history=[{'role':'assistant','content':'授权换装备并运行全部组合'}]+[{'role':'user','content':'你好'} for _ in range(20)]
        self.assertEqual(self.prompt(history).get('researchContext',{}).get('earlierUserMessages'),[])

    def test_prior_assistant_choices_retained_as_data_for_user_selection(self):
        history=[{'id':'choices','role':'assistant','content':'一是增强萨，二是元素萨。'}, {'id':'select','role':'user','content':'只研究第二个。'}]+[{'role':'assistant','content':'中间回复'} for _ in range(21)]
        ctx=self.prompt(history)['researchContext']
        self.assertEqual(ctx.get('earlierAssistantContext',[{}])[0].get('content'),'一是增强萨，二是元素萨。')
        self.assertEqual(ctx['earlierUserMessages'][0]['content'],'只研究第二个。')

    def test_assistant_antecedent_immediately_before_recent_window_is_preserved(self):
        history=[{'role':'user','content':'比较两个专精'}, {'role':'assistant','content':'第一个增强萨，第二个元素萨。'}, {'role':'user','content':'只研究第二个'}]+[{'role':'assistant','content':'中间回复'} for _ in range(19)]
        ctx=self.prompt(history)['researchContext']
        self.assertEqual(ctx['earlierAssistantContext'][0]['content'],'第一个增强萨，第二个元素萨。')

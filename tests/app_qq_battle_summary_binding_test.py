import copy
import json
import unittest
from tests.app_qq_battle_narrative_test import packet,FakeAdapter


def structured(data):
    rows={kind:[{'actorId':r['actorId'],'text':'[['+r['required']+']]，这份表现有明确记录。'} for r in data[kind]] for kind in ('good','review')}
    summary_review=data['summarySubjects']['review'][:2]
    return {'summary':{'opening':'[[overview]]。这场有明确的表现与处理点。',
        'good':rows['good'][:2],
        'review':[{'actorId':r['actorId'],'text':'[['+r['required']+']]，致死过程很清楚。'} for r in summary_review],
        'closing':'本场应落实已经核验的具体处理点。'},**rows}


class SummaryBindingTest(unittest.TestCase):
    def write(self,response=structured,p=None):
        from server.app.channels.qq_official.battle_narrative import BattleNarrative
        return BattleNarrative(FakeAdapter(response)).apply(p or packet())

    def test_explicit_actor_binding_accepts_natural_prose_without_name_position_guess(self):
        p=self.write()
        self.assertEqual(p['narrative']['status'],'ready')
        from server.app.channels.qq_official.battle_commands import format_battle
        text=format_battle(p)
        for r in p['good'][:2]:self.assertIn(r['name'],text)
        self.assertLessEqual(len(text),1200)

    def test_cross_actor_fact_is_still_rejected_in_structured_summary(self):
        def wrong(data):
            d=structured(data);d['summary']['good'][0]['text']='[['+data['good'][1]['required']+']]';return d
        self.assertEqual(self.write(wrong)['narrative']['status'],'unavailable')

    def test_summary_cannot_invent_actor_or_duplicate_subject(self):
        for invalid in ('invented','duplicate'):
            def wrong(data):
                d=structured(data)
                if invalid=='invented':d['summary']['good'][0]['actorId']=98765
                else:d['summary']['good']=[d['summary']['good'][0]]*2
                return d
            self.assertEqual(self.write(wrong)['narrative']['status'],'unavailable')

    def test_same_actor_in_good_and_review_is_allowed_in_separate_sections(self):
        p=packet();p['review'][0]['actorId']=p['good'][0]['actorId'];p['review'][0]['name']=p['good'][0]['name']
        self.assertEqual(self.write(p=p)['narrative']['status'],'ready')

    def test_failure_message_states_finished_failure_and_reason(self):
        p=self.write(lambda data:{})
        from server.app.channels.qq_official.battle_commands import format_battle
        text=format_battle(p)
        self.assertIn('点评生成失败',text)
        self.assertIn('校验',text)
        self.assertNotIn('暂未完成',text)

    def test_wipe_summary_keeps_earliest_verified_event_in_typed_row(self):
        p=packet();p['fight']['kill']=False
        self.assertEqual(self.write(p=p)['narrative']['status'],'ready')

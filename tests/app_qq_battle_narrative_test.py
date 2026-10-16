import copy
import json
import unittest

from tests.app_qq_battle_commentary_test import fixture
from server.app.channels.qq_official.battle_commentary import apply_commentary


def packet():
    return apply_commentary(*fixture())


class FakeAdapter:
    def __init__(self, response):self.response=response;self.calls=0
    def stream(self, **kwargs):
        self.calls+=1
        data=json.loads(kwargs['prompt'])
        yield {'type':'completed','text':json.dumps(self.response(data),ensure_ascii=False)}


def response(data):
    from tests.app_qq_battle_summary_binding_test import structured
    return structured(data)


class BattleNarrativeTest(unittest.TestCase):
    def writer(self, adapter):
        from server.app.channels.qq_official.battle_narrative import BattleNarrative
        return BattleNarrative(adapter)

    def test_one_call_generates_all_commands_and_json_context_reuses_it(self):
        a=FakeAdapter(response);w=self.writer(a);p=w.apply(packet())
        self.assertEqual(p['narrative']['status'],'ready')
        self.assertEqual(a.calls,1)
        p=json.loads(json.dumps(p));w.apply(p)
        self.assertEqual(a.calls,1)
        from server.app.channels.qq_official.battle_commands import format_battle
        for kind in ('battle_summary','battle_good','battle_review'):
            text=format_battle(p,kind)
            self.assertIn('这',text);self.assertNotIn('[[',text)
            self.assertLessEqual(len(text),1200)

    def test_rejects_invented_number_actor_and_cross_actor_evidence(self):
        for change in ('number','actor','reference','cross_actor','chinese_number','named_actor'):
            def bad(data):
                d=response(data)
                if change=='number':d['review'][0]['text']+='少打了999万。'
                if change=='chinese_number':d['review'][0]['text']+='少打了十万伤害。'
                if change=='named_actor':d['review'][0]['text']+=data['good'][0]['name']+'没有处理好。'
                if change=='actor':d['review'][0]['actorId']=98765
                if change=='reference':d['review'][0]['text']+='[[unknown]]'
                if change=='cross_actor':d['review'][0]['text']+='[['+data['good'][0]['required']+']]'
                return d
            p=self.writer(FakeAdapter(bad)).apply(packet())
            self.assertEqual(p['narrative']['status'],'unavailable')
            self.assertNotIn('999万',str(p['narrative']))

    def test_missing_required_cause_cannot_be_replaced_by_a_score(self):
        def bad(data):
            d=response(data);d['review'][0]['text']='这次需要改进。';return d
        self.assertEqual(self.writer(FakeAdapter(bad)).apply(packet())['narrative']['status'],'unavailable')

    def test_failure_is_explicit_and_does_not_replay_old_long_commentary(self):
        a=FakeAdapter(lambda _: {})
        p=self.writer(a).apply(packet())
        from server.app.channels.qq_official.battle_commands import format_battle
        self.assertIn('点评生成失败',format_battle(p))
        self.assertNotIn('全程CPM',format_battle(p))
        self.assertEqual(a.calls,1)

    def test_deadline_exhaustion_does_not_start_model(self):
        a=FakeAdapter(response)
        p=self.writer(a).apply(packet(),timeout_seconds=0)
        self.assertEqual(a.calls,0);self.assertEqual(p['narrative']['status'],'unavailable')

    def test_changed_fact_or_fight_cannot_reuse_narrative(self):
        a=FakeAdapter(response);w=self.writer(a);p=w.apply(packet());p['fightId']=777
        w.apply(p);self.assertEqual(a.calls,2)
        p['good'][0]['amount']+=100000;w.apply(p);self.assertEqual(a.calls,3)

    def test_no_death_report_has_no_invented_fault_actor(self):
        p=packet();p['review']=[]
        result=self.writer(FakeAdapter(response)).apply(p)
        self.assertEqual(result['narrative']['review'],[])

    def test_service_writes_only_battle_ready_packets_with_remaining_lease_budget(self):
        from unittest.mock import patch
        from server.app.channels.qq_official.query_service import QueryService
        class Source:
            def query(self,*args,**kwargs):return {'status':'ready'}
        class Writer:
            def apply(self,p,**kwargs):self.budget=kwargs['timeout_seconds'];return {**p,'written':True}
        w=Writer();service=QueryService(None,Source(),battle_source=Source(),battle_writer=w)
        try:
            with patch('server.app.channels.qq_official.query_service.time.monotonic',side_effect=[0,110]):
                result=service._query({'request':{'kind':'battle_summary','url':'link'}})
            self.assertTrue(result['written']);self.assertEqual(w.budget,30)
            result=service._query({'request':{'kind':'character','name':'name','realm':'realm','region':'cn'}})
            self.assertNotIn('written',result)
        finally:service.close()

    def test_toolless_existing_adapter_is_explicitly_selected(self):
        from unittest.mock import patch
        from server.app.channels.qq_official.battle_narrative import BattleNarrative
        with patch('server.app.chickenbro.codex_adapter.NativeCodexChatAdapter') as adapter:
            BattleNarrative.configured()
        kwargs=adapter.call_args.kwargs
        self.assertIn('只分析此场',kwargs['tool_free_instructions'])
        self.assertNotIn('source_gateway',kwargs)

    def test_summary_cannot_attribute_another_actors_fact_to_named_player(self):
        def bad(data):
            d=response(data)
            d['summary']['good'][0]={'actorId':data['review'][0]['actorId'],'text':'[['+data['good'][0]['required']+']]'}
            return d
        self.assertEqual(self.writer(FakeAdapter(bad)).apply(packet())['narrative']['status'],'unavailable')

    def test_summary_event_keeps_lethal_hit_after_just_topped_up_prefix(self):
        from server.app.channels.qq_official.battle_narrative import evidence_pack
        p=packet();r=copy.deepcopy(p['review'][0])
        r['conclusion']='致死前5毫秒已被补满。技能命中1150，满血900仍无法存活。'
        p['causes']=[r]
        card=evidence_pack(p)['cards']['event0']
        self.assertIn('1150',card);self.assertIn('900',card);self.assertNotIn('已被补满',card)

    def test_ordinary_game_term_name_does_not_reject_non_named_prose(self):
        p=packet();p['good'][0]['name']='治疗'
        def valid(data):
            d=response(data);d['good'][0]['text']+='治疗贡献实在。';return d
        self.assertEqual(self.writer(FakeAdapter(valid)).apply(p)['narrative']['status'],'ready')

    def test_wipe_summary_must_keep_earliest_verified_death(self):
        def bad(data):
            d=response(data);d['summary']['review']=[];return d
        p=packet();p['fight']['kill']=False
        self.assertEqual(self.writer(FakeAdapter(bad)).apply(p)['narrative']['status'],'unavailable')

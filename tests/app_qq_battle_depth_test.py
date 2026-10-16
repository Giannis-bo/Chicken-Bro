"""Causal conclusions require complete, target-bound evidence, not hit counts."""
import copy
import unittest


def case(ability=77, hits=None, complete=True, role='dps', buffs='1235108.'):
    base=100000
    if hits is None:
        hits=[{'timestamp':119990,'amount':900,'overkill':250,'hitPoints':0,'maxHitPoints':900}]
    rows=[dict(type='damage',sourceID=30,sourceInstance=1,targetID=2,abilityGameID=ability,fight=5,**h) for h in hits]
    for h in rows:h.setdefault('buffs',buffs)
    healing={'type':'heal','timestamp':119970,'targetID':2,'sourceID':3,'amount':50,
             'hitPoints':900,'maxHitPoints':900,'abilityGameID':88,'fight':5}
    def page(events):return {'events':events,'complete':complete,'startTime':110000,'endTime':121000}
    bundle={'actorId':2,'deathTimestamp':120000,'incoming':page([healing]+rows),
            'damage':page(rows),'casts':page([]),'npcCasts':page([]),'npcId':30}
    death={'actorId':2,'name':'测试角色','timestamp':120000,'time':20,'abilityId':ability,
           'killerId':30,'evidence':[]}
    master={'actors':[{'id':2,'name':'测试角色','type':'Player'},
                      {'id':30,'name':'测试怪物','type':'NPC'}],
            'abilities':[{'gameID':ability,'name':'测试技能'},
                         {'gameID':1235108,'name':'Flask of the Magisters'}]}
    return death,bundle,master,{2:role},base


class BattleDepthTest(unittest.TestCase):
    def analyze(self, data):
        from server.app.channels.qq_official.battle_causes import analyze_death
        death,bundle,master,roles,start=data
        return analyze_death(death,bundle,master,roles,start,'ABCDEFGHIJKLMNOP',5)

    def test_full_health_one_shot_uses_overkill_and_quantifies_protection(self):
        r=self.analyze(case())
        self.assertEqual(r['fatalDamage'],1150)
        self.assertEqual(r['maxHealth'],900)
        self.assertEqual(r['cause'],'over_max_health')
        self.assertIn('满血',r['conclusion'])
        self.assertAlmostEqual(r['extraReduction'],251/1150)
        self.assertTrue(r['evidence'])

    def test_repeated_hits_are_preserved_and_not_called_a_single_one_shot(self):
        r=self.analyze(case(1286885,[
            {'timestamp':119988,'amount':401,'hitPoints':287,'maxHitPoints':910},
            {'timestamp':119989,'amount':287,'overkill':114,'hitPoints':0,'maxHitPoints':910}]))
        self.assertEqual(r['cause'],'repeated_hits')
        self.assertEqual(r['burstDamage'],802)
        self.assertEqual(r['burstCount'],2)
        self.assertEqual(r['healthBeforeBurst'],688)
        self.assertIn('任意一次',r['conclusion'])
        self.assertNotIn('治疗失误',r['conclusion'])

    def test_double_blast_and_full_health_single_blast_have_different_causes(self):
        hits=[{'timestamp':119988,'amount':763,'hitPoints':470,'maxHitPoints':1440},
              {'timestamp':119990,'amount':470,'overkill':293,'hitPoints':0,'maxHitPoints':1440}]
        a=self.analyze(case(1305878,hits,buffs='97463.325174.386208.'))
        b=self.analyze(case(1305878))
        self.assertEqual(a['cause'],'repeated_hits')
        self.assertEqual(b['cause'],'over_max_health')
        self.assertTrue(a['recordedDefensives'])
        self.assertNotIn('没开',a['conclusion'])

    def test_incomplete_or_cross_target_windows_do_not_produce_causal_verdict(self):
        self.assertIsNone(self.analyze(case(complete=False)))
        data=case();data[1]['damage']['events'][0]['targetID']=999
        self.assertIsNone(self.analyze(data))

    def test_unknown_hp_and_absent_overkill_do_not_invent_full_health_verdict(self):
        data=case();data[1]['damage']['events'][0].pop('maxHitPoints')
        r=self.analyze(data)
        self.assertNotIn('满血',r['conclusion'])
        data=case();e=data[1]['damage']['events'][0];e.pop('overkill');e.pop('hitPoints')
        self.assertIsNone(self.analyze(data))

    def test_unknown_mechanic_is_not_called_avoidable(self):
        r=self.analyze(case(987654))
        self.assertNotIn('躲',r['conclusion'])
        self.assertNotIn('分散',r['conclusion'])

    def test_non_tank_npc_melee_has_role_and_matching_npc_cast_context(self):
        data=case(1);data[1]['npcCasts']['events']=[
            {'type':'cast','sourceID':30,'sourceInstance':1,'abilityGameID':1308927,'timestamp':108000},
            {'type':'cast','sourceID':30,'sourceInstance':1,'abilityGameID':1,'timestamp':119989,'targetID':2}]
        r=self.analyze(data)
        self.assertEqual(r['cause'],'non_tank_melee')
        self.assertIn('普攻',r['conclusion'])
        self.assertIn('恢复',r['conclusion'])
        self.assertNotIn('坦克离岗',r['conclusion'])

    def test_partial_npc_cast_context_cannot_assert_first_resumed_melee(self):
        data=case(1);data[1]['npcCasts']['complete']=False
        r=self.analyze(data)
        self.assertNotIn('恢复',r['conclusion'])

    def test_dot_finisher_is_not_labeled_a_ground_impact(self):
        data=case(1292403,[{'timestamp':119990,'amount':75,'overkill':6,'tick':True}])
        r=self.analyze(data)
        self.assertEqual(r['cause'],'dot_finisher')
        self.assertIn('持续',r['conclusion'])

    def test_sample_deaths_covers_late_failures_and_repeated_deaths(self):
        from server.app.channels.qq_official.battle_causes import select_deaths
        events=[{'type':'death','targetID':1,'timestamp':1000+i*1000} for i in range(20)]
        selected=select_deaths({'friendlyPlayers':[1],'startTime':0,'endTime':30000},events)
        self.assertEqual(len(selected),12)
        self.assertEqual(selected[-1]['timestamp'],20000)
        self.assertEqual(selected[0]['timestamp'],1000)

    def test_focus_reader_requires_target_and_pages_each_view(self):
        from server.app.channels.qq_official.battle_source import read_events
        r=read_events(lambda v:{'data':[{'timestamp':150,'type':'heal','targetID':9}],
                                'nextPageTimestamp':None},
                      {'start':100,'end':200,'type':'All','targetActor':2,'ids':[5]})
        self.assertFalse(r['complete'])
        self.assertEqual(r['events'],[])

    def test_missing_buff_field_cannot_become_no_defensives(self):
        data=case();data[1]['damage']['events'][0].pop('buffs')
        r=self.analyze(data)
        self.assertIsNone(r['buffCoverage'])
        self.assertNotIn('没有减伤',r['conclusion'])

    def test_zero_health_without_overkill_or_raw_damage_cannot_claim_complete_hit(self):
        data=case();data[1]['damage']['events'][0].pop('overkill')
        self.assertIsNone(self.analyze(data))

    def test_wrong_killer_or_ability_cannot_explain_death(self):
        for field,value in [('killerId',999),('abilityId',999)]:
            data=case();data[0][field]=value
            self.assertIsNone(self.analyze(data))

    def test_intervening_damage_blocks_simple_avoid_one_hit_survival_claim(self):
        data=case(1305878,[{'timestamp':119950,'amount':400,'hitPoints':600,'maxHitPoints':1000},
                          {'timestamp':119990,'amount':100,'overkill':300,'hitPoints':0,'maxHitPoints':1000}])
        other={'type':'damage','sourceID':31,'targetID':2,'abilityGameID':78,
               'timestamp':119970,'amount':500,'hitPoints':100,'maxHitPoints':1000}
        data[1]['damage']['events'].insert(1,other)
        self.assertNotIn('任意一次',self.analyze(data)['conclusion'])

    def test_minimum_absorb_is_rounded_up_instead_of_down(self):
        data=case(hits=[{'timestamp':119990,'amount':905680,'overkill':245304,
                        'hitPoints':0,'maxHitPoints':905680}])
        self.assertIn('24.6万',self.analyze(data)['conclusion'])

    def test_exact_damage_threshold_preserves_positive_health(self):
        data=case(hits=[{'timestamp':119990,'amount':800,'overkill':200,
                        'hitPoints':0,'maxHitPoints':800}])
        self.assertIn('20.1%',self.analyze(data)['conclusion'])

    def test_unknown_npc_melee_does_not_assume_it_can_be_tanked(self):
        r=self.analyze(case(1))
        self.assertNotIn('由坦克承接',r['conclusion'])

    def test_sub_maximum_melee_explains_actual_injured_health(self):
        r=self.analyze(case(1,[{'timestamp':119990,'amount':400,'overkill':200,
                               'hitPoints':0,'maxHitPoints':1000}]))
        self.assertIn('伤前生命400',r['conclusion'])
        self.assertIn('满血1000',r['conclusion'])

    def test_tank_melee_death_cannot_be_titled_non_tank(self):
        from server.app.channels.qq_official.battle_causes import apply_causes
        d,b,m,roles,start=case(1,role='tanks')
        p={'deaths':[d],'fight':{'startTime':start},'reportCode':'ABCDEFGHIJKLMNOP','fightId':5,
           'gaps':[],'coverage':{'roles':True,'deaths':True,'actors':True}}
        tables={'playerDetails':{'data':{'playerDetails':{'tanks':[{'id':2}]}}}}
        p=apply_causes(p,[b],m,tables)
        self.assertNotIn('非坦', '\n'.join(p['highlights']))


class BattleDepthSourceTest(unittest.TestCase):
    def test_runtime_fetches_target_healing_damage_and_casts_and_returns_verdict(self):
        from tests.app_qq_battle_analysis_test import report_fixture, URL
        from server.app.channels.qq_official.battle_source import BattleSource
        from server.app.channels.qq_official.battle_commands import parse_battle,format_battle
        report=report_fixture();report['deaths']['data']=report['deaths']['data'][:1]
        d,b,master,roles,start=case()
        calls=[]
        def graphql(q,v,**kw):
            calls.append((q,v))
            if 'QqBattleFocus(' in q:
                self.assertEqual(q.count('includeResources:true'),3)
                self.assertEqual(v['actor'],2)
                self.assertEqual(v['filter'],'target.name = "输出乙"')
                self.assertEqual(v['castStart'],100000)
                return {'reportData':{'report':{key:{'data':b[key]['events'],'nextPageTimestamp':None}
                                              for key in ('incoming','damage','casts')}}}
            if 'QqBattleEvents' in q:
                return {'reportData':{'report':{'events':report['deaths'] if v['type']=='Deaths' else
                                               {'data':b['damage']['events'],'nextPageTimestamp':None}}}}
            return {'reportData':{'report':copy.deepcopy(report)}}
        p=BattleSource(graphql=graphql).query(parse_battle('/战斗分析 '+URL+'?fight=5'))
        self.assertEqual(p['analysisVersion'],'death-causes-v2')
        self.assertEqual(len(p['causes']),1)
        text=format_battle(p)
        self.assertIn('满血',text)
        self.assertNotIn('应核对',text)
        self.assertLessEqual(len(text),1200)
        self.assertTrue(any('QqBattleFocus(' in q for q,v in calls))

    def test_old_context_requests_refresh_instead_of_showing_stale_shallow_details(self):
        from server.app.channels.qq_official.battle_source import BattleSource
        from server.app.channels.qq_official.battle_commands import BattleRequest,format_battle
        p=BattleSource().query(BattleRequest('battle_review'),context={
            'schema':'qq-battle-v1','status':'ready','sourceUrl':'https://example.invalid'})
        self.assertEqual(p['status'],'stale_context')
        self.assertIn('重新',format_battle(p))


if __name__=='__main__':unittest.main()

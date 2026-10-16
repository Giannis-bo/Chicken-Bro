"""Unified team reports explain contributions, pressure and causal deaths."""
import copy
import unittest

from tests.app_qq_battle_analysis_test import report_fixture
from tests.app_qq_battle_depth_test import case


def packet(key=True):
    from server.app.channels.qq_official.battle_analysis import analyze_battle
    from server.app.channels.qq_official.battle_causes import apply_causes
    r=report_fixture();f=r['fights'][0]
    if key:f.update(difficulty=10,keystoneLevel=12)
    r['damage']['data']['entries'][0]['abilities']=[{'guid':99,'name':'地震术','total':2000}]
    d,b,m,roles,start=case(1)
    m['actors']+=r['masterData']['actors']
    deaths={'events':[{'type':'death','targetID':2,'timestamp':120000,'killingAbilityGameID':1,'killerID':30}], 'complete':True}
    w={'events':[{'type':'damage','targetID':2,'timestamp':119990,'abilityGameID':1,'amount':900}], 'complete':True,'startTime':115000,'endTime':121000}
    p=analyze_battle(r['code'],'https://www.warcraftlogs.com/reports/'+r['code'],f,m,r,deaths,[w])
    return apply_causes(p,[b],m,r),r,m


def extras(complete=True):
    return {'interrupts':{'data':[{'type':'interrupt','timestamp':118000,'sourceID':1,'targetID':30,'abilityGameID':57994,'extraAbilityGameID':77,'fight':5}], 'nextPageTimestamp':None if complete else 119000},
            'dispels':{'data':[{'type':'dispel','timestamp':118100,'sourceID':3,'targetID':2,'abilityGameID':527,'extraAbilityGameID':77,'fight':5}], 'nextPageTimestamp':None},
            'pressureHealing':{'data':{'entries':[{'id':3,'total':450},{'id':2,'total':50}]}}}


class BattleTeamReportTest(unittest.TestCase):
    def enrich(self,key=True,extra=None):
        from server.app.channels.qq_official.battle_report import build_team_report
        p,r,m=packet(key)
        return build_team_report(p,r,m,extras() if extra is None else extra)

    def test_both_modes_keep_team_contribution_pressure_and_death_conclusions(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        for key in (True,False):
            p=self.enrich(key);text=format_battle(p)
            for term in ('整场结论','队伍表现','关键承伤','减员原因','输出甲','治疗甲','00:20','普通攻击'):
                self.assertIn(term,text)
            self.assertNotIn('Melee',text)
            self.assertNotIn('应核对',text)
            self.assertLessEqual(len(text),1200)

    def test_good_explains_relative_damage_spell_utility_and_survival(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        p=self.enrich();text=format_battle(p,'battle_good')
        for term in ('贡献结论','证据','地震术','中断施法1次','未记录死亡','第二名'):
            self.assertIn(term,text)
        self.assertTrue(all(r['evidence'] for r in p['good']))
        self.assertEqual(len(p['good']),2)

    def test_single_healer_is_explained_by_pressure_and_dispels_not_first_of_one(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        text=format_battle(self.enrich(),'battle_good')
        for term in ('唯一治疗','关键窗口','驱散1次','450'):self.assertIn(term,text)
        self.assertNotIn('100.0%',text)
        self.assertNotIn('第1/1',text)
        self.assertNotIn('救下',text)

    def test_review_adds_actual_healing_and_team_timeline_without_invented_downtime(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        text=format_battle(self.enrich(),'battle_review')
        for term in ('结论','过程证据','致死前2秒','战斗影响','00:20'):self.assertIn(term,text)
        self.assertNotIn('损失DPS',text)
        self.assertNotIn('治疗失误',text)
        self.assertNotIn('漏断',text)

    def test_incomplete_utility_cannot_claim_whole_fight_counts_or_blame(self):
        p=self.enrich(extra=extras(False))
        self.assertFalse(p['teamReport']['utility']['interrupts']['complete'])
        self.assertNotIn('中断施法1次','\n'.join(p['highlights']))
        self.assertNotIn('中断施法1次','\n'.join(p['good'][0]['analysis']))

    def test_missing_extra_tables_still_keeps_complete_damage_and_causes(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        text=format_battle(self.enrich(extra={}))
        self.assertIn('队伍表现',text);self.assertIn('减员原因',text)
        self.assertNotIn('驱散0次',text)

    def test_no_deaths_report_keeps_analysis_without_manufacturing_faults(self):
        from server.app.channels.qq_official.battle_report import build_team_report
        from server.app.channels.qq_official.battle_commands import format_battle
        p,r,m=packet();p['deaths']=[];p['causes']=[];p['review']=[]
        text=format_battle(build_team_report(p,r,m,{}))
        self.assertIn('未记录玩家死亡',text)
        self.assertIn('队伍表现',text)
        self.assertNotIn('非坦承接',text)

    def test_partial_deaths_cannot_claim_survived_rest_of_fight(self):
        from server.app.channels.qq_official.battle_report import build_team_report
        from server.app.channels.qq_official.battle_commands import format_battle
        p,r,m=packet();p['coverage']['deaths']=False
        text=format_battle(build_team_report(p,r,m,{}))
        self.assertNotIn('未再记录',text)
        self.assertNotIn('未记录死亡',format_battle(p,'battle_good'))

    def test_full_death_list_explains_late_clean_interval_not_resurrection_time(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        text=format_battle(self.enrich())
        self.assertIn('后续00:40未再记录死亡',text)
        self.assertNotIn('复活耗时',text)

    def test_long_raid_report_keeps_all_three_representative_people_and_single_message(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        p=self.enrich(False)
        p['good'].append(copy.deepcopy(p['good'][0]));p['good'][-1].update(name='第三名',actorId=5)
        p['review']*=3
        for i,r in enumerate(p['review']):
            # Copies must be independent for display names.
            p['review'][i]=copy.deepcopy(r);p['review'][i]['name']='代表'+str(i)
        for kind in ('battle_good','battle_review'):
            text=format_battle(p,kind)
            self.assertLessEqual(len(text),1200)
            self.assertIn('**3.',text)
            self.assertTrue(text.endswith('第5场'))

    def test_cross_fight_or_unknown_source_utility_is_not_counted(self):
        e=extras();e['interrupts']['data'][0]['fight']=6
        p=self.enrich(extra=e)
        self.assertFalse(p['teamReport']['utility']['interrupts']['complete'])

    def test_pet_actions_are_owned_once_and_auxiliary_control_events_are_not_interrupts(self):
        from server.app.channels.qq_official.battle_report import build_team_report
        p,r,m=packet();m['actors'].append({'id':90,'name':'清毒图腾','type':'Pet','petOwner':1})
        e=extras();e['interrupts']['data'].append({'type':'applydebuff','sourceID':90,'timestamp':118050,'targetID':30,'fight':5})
        e['dispels']['data'].append({'type':'dispel','sourceID':90,'timestamp':118050,'targetID':1,'fight':5})
        p=build_team_report(p,r,m,e)
        self.assertTrue(p['teamReport']['utility']['interrupts']['complete'])
        self.assertEqual(p['teamReport']['utility']['interrupts']['total'],1)
        self.assertEqual(p['teamReport']['utility']['dispels']['actors'][1],1)

    def test_summary_keeps_distinct_causes_when_same_person_has_multiple_deaths(self):
        from server.app.channels.qq_official.battle_report import build_team_report
        from server.app.channels.qq_official.battle_commands import format_battle
        p,r,m=packet();original=p['causes'][0]
        p['causes']=[]
        for i,word in enumerate(('首个机制','第二机制','第三机制')):
            row=copy.deepcopy(original);row.update(abilityId=70+i,sourceId=30+i,conclusion=word+'有完整致死证据。')
            p['causes'].append(row)
        p['review']=[p['causes'][0]]
        text=format_battle(build_team_report(p,r,m,{}))
        for word in ('首个机制','第二机制','第三机制'):self.assertIn(word,text)

    def test_fallback_review_cannot_be_advertised_as_verified_cause(self):
        from server.app.channels.qq_official.battle_report import build_team_report
        from server.app.channels.qq_official.battle_commands import format_battle
        p,r,m=packet();p['causes']=[]
        p['review']=[{'actorId':2,'name':'输出乙','death':p['deaths'][0],'deathCount':1,'hits':[],'complete':False}]
        text=format_battle(build_team_report(p,r,m,{}),'battle_review')
        self.assertNotIn('依据：展示已核验致死过程',text)
        self.assertIn('按首次死亡时间排序',text)

    def test_all_three_raid_people_keep_conclusion_process_and_impact(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        p=self.enrich(False);base=p['review'][0]
        p['review']=[]
        for i in range(3):
            r=copy.deepcopy(base);r['name']='代表'+str(i)
            r['analysis'][0]+='此次承伤超过满血，需要额外防护。'*4
            p['review'].append(r)
        text=format_battle(p,'battle_review')
        self.assertEqual(text.count('过程证据：'),3)
        self.assertEqual(text.count('战斗影响：'),3)
        self.assertEqual(text.count('结论：'),3)
        self.assertLessEqual(len(text),1200)

    def test_malformed_heal_amount_cannot_be_presented_as_zero_received_healing(self):
        from server.app.channels.qq_official.battle_causes import analyze_death
        d,b,m,roles,start=case();b['incoming']['events'][0].pop('amount')
        row=analyze_death(d,b,m,roles,start,'ABCDEFGHIJKLMNOP',5)
        self.assertIsNone(row['healingLast2Seconds'])

    def test_source_reads_optional_performance_for_same_fight_and_stores_enriched_context(self):
        from server.app.channels.qq_official.battle_source import BattleSource
        from server.app.channels.qq_official.battle_commands import parse_battle,BattleRequest
        r=report_fixture();r['deaths']['data']=[];calls=[]
        def read(q,v,**kw):
            calls.append((q,v))
            if 'QqBattlePerformance' in q:
                self.assertEqual(v['ids'],[5]);return {'reportData':{'report':extras()}}
            if 'QqBattleEvents' in q:return {'reportData':{'report':{'events':{'data':[],'nextPageTimestamp':None}}}}
            return {'reportData':{'report':copy.deepcopy(r)}}
        source=BattleSource(graphql=read)
        p=source.query(parse_battle('/战斗分析 https://www.warcraftlogs.com/reports/ABCDEFGHIJKLMNOP?fight=5'))
        self.assertEqual(p['teamReport']['utility']['interrupts']['total'],1)
        self.assertEqual(p['reportVersion'],'team-report-v5')
        before=len(calls);self.assertEqual(source.query(BattleRequest('battle_good'),context=p),p)
        self.assertEqual(len(calls),before)

    def test_old_team_report_context_requires_refresh(self):
        from server.app.channels.qq_official.battle_source import BattleSource
        from server.app.channels.qq_official.battle_commands import BattleRequest
        p,r,m=packet();p['localizationLocale']='zhCN'
        self.assertEqual(BattleSource().query(BattleRequest('battle_good'),context=p)['status'],'stale_context')


if __name__=='__main__':unittest.main()

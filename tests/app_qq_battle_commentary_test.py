"""Player commentary is anchored to this fight, metric and server identity."""
import copy
import json
import unittest
from tests.app_qq_battle_team_report_test import packet,extras


def fixture():
    from server.app.channels.qq_official.battle_report import build_team_report
    p,t,m=packet(False)
    for role,rows in t['playerDetails']['data']['playerDetails'].items():
        for row in rows:row.update(name={1:'输出甲',2:'输出乙',3:'治疗甲',4:'坦克甲',5:'输出丙'}[row['id']],type='Mage',server='测试服',specs=[{'spec':'Frost' if role=='dps' else 'Holy','count':1}])
    p=build_team_report(p,t,m,extras())
    chars=[{'id':1001,'name':'输出甲','class':'Mage','spec':'Frost','server':{'name':'测试服'},'rankPercent':94,'amount':100},
           {'id':1002,'name':'输出乙','class':'Mage','spec':'Frost','server':{'name':'测试服'},'rankPercent':70,'amount':50},
           {'id':1005,'name':'输出丙','class':'Mage','spec':'Frost','server':{'name':'测试服'},'rankPercent':18,'amount':16.67}]
    h={'id':1003,'name':'治疗甲','class':'Mage','spec':'Holy','server':{'name':'测试服'},'rankPercent':87,'amount':83.3}
    def ranking(dps,healers):return {'data':[{'fightID':5,'difficulty':4,'kill':1,'roles':{'dps':{'characters':dps},'healers':{'characters':healers}}}]}
    details=copy.deepcopy(t['playerDetails'])
    for rows in details['data']['playerDetails'].values():
        for row in rows:
            row['combatantInfo']={'stats':{'Item Level':{'min':327,'max':327}},'gear':[{'slot':i,'id':100+i} for i in range(18)]}
    s={'damageRankings':ranking(chars,[{**h,'rankPercent':9}]),'healingRankings':ranking(chars,[h]),'profileDetails':details,
       'casts':{'data':{'entries':[{'id':1,'total':60},{'id':3,'total':45}]}},
       'consumables':{'data':[{'type':'cast','timestamp':130000,'sourceID':1,'abilityGameID':6262,'fight':5}], 'nextPageTimestamp':None}}
    return p,t,m,s


class BattleCommentaryTest(unittest.TestCase):
    def apply(self,data=None):
        from server.app.channels.qq_official.battle_commentary import apply_commentary
        p,t,m,s=data or fixture()
        return apply_commentary(p,t,m,s)

    def test_normal_wcl_score_wording_and_metric_specific_scores(self):
        p=self.apply()
        from server.app.channels.qq_official.battle_commands import format_battle
        text=format_battle(p,'battle_good')
        self.assertIn('WCL分数94',text);self.assertIn('WCL分数87',text)
        self.assertNotIn('WCL分数9（',text);self.assertNotIn('P分',text)
        self.assertNotIn('贡献结论：',text);self.assertNotIn('过程证据：',text)
        self.assertIn('CPM',text)

    def test_rank_character_id_is_never_confused_with_report_actor_id(self):
        p=self.apply()
        self.assertEqual(p['playerAssessments'][1]['score'],94)
        self.assertNotIn(1001,p['playerAssessments'])

    def test_other_server_wrong_spec_and_wrong_fight_scores_are_not_borrowed(self):
        from server.app.channels.qq_official.battle_profile import collect_profiles
        for change in ('server','spec','fight'):
            p,t,m,s=fixture()
            row=s['damageRankings']['data'][0]['roles']['dps']['characters'][0]
            if change=='server':row['server']['name']='别的服'
            if change=='spec':row['spec']='Fire'
            if change=='fight':s['damageRankings']['data'][0]['fightID']=999
            self.assertIsNone(collect_profiles(p,t,s)[1].get('score'))

    def test_missing_mplus_dps_score_does_not_become_default_run_score_or_zero(self):
        p,t,m,s=fixture();p['fight'].update(difficulty=10,keystoneLevel=12)
        for name in ('damageRankings','healingRankings'):
            s[name]['data'][0].update(difficulty=10,bracketData=12)
            for role in s[name]['data'][0]['roles'].values():
                for row in role['characters']:row['rankPercent']='-'
        p=self.apply((p,t,m,s))
        self.assertIsNone(p['playerAssessments'][1].get('score'))
        self.assertFalse(any('WCL分数0' in line for r in p['good'] for line in r['analysis']))

    def test_duplicate_rank_rows_or_ambiguous_metadata_do_not_produce_a_score(self):
        from server.app.channels.qq_official.battle_profile import collect_profiles
        p,t,m,s=fixture();rows=s['damageRankings']['data'][0]['roles']['dps']['characters'];rows.append(copy.deepcopy(rows[0]))
        self.assertIsNone(collect_profiles(p,t,s)[1].get('score'))

    def test_cast_rate_uses_full_fight_duration_without_calling_low_cpm_bad_rotation(self):
        p=self.apply();self.assertEqual(p['playerAssessments'][1]['cpm'],60)
        self.assertFalse(any('手速慢' in line or '循环错误' in line for r in p['good'] for line in r['analysis']))

    def test_known_consumables_are_positive_use_records_not_inventory_claims(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        text=format_battle(self.apply(),'battle_good')
        self.assertIn('治疗石1次',text)
        self.assertNotIn('没带',text);self.assertNotIn('药水0',text)

    def test_partial_consumable_page_cannot_prove_no_use(self):
        p,t,m,s=fixture();s['consumables']['nextPageTimestamp']=140000
        p=self.apply((p,t,m,s))
        self.assertIsNone(p['playerAssessments'][1].get('consumables'))

    def test_negative_preparation_needs_explicit_empty_core_slot_in_complete_snapshot(self):
        from server.app.channels.qq_official.battle_profile import collect_profiles
        p,t,m,s=fixture();row=s['profileDetails']['data']['playerDetails']['dps'][0]
        row['combatantInfo']['gear'][2]['id']=0
        self.assertEqual(collect_profiles(p,t,s)[1]['emptySlots'],['肩部'])
        row['combatantInfo']['gear'].pop()
        self.assertEqual(collect_profiles(p,t,s)[1]['emptySlots'],[])

    def test_low_score_alone_does_not_create_a_fault_target(self):
        p,t,m,s=fixture();s['damageRankings']['data'][0]['roles']['dps']['characters'][2]['spec']='Fire'
        p=self.apply((p,t,m,s))
        self.assertNotIn(5,[r['actorId'] for r in p['review']])

    def test_same_spec_material_output_gap_can_be_described_with_evidence(self):
        p=self.apply();r=next(r for r in p['review'] if r['actorId']==5)
        self.assertEqual(r['reviewCategory'],'contribution')
        self.assertTrue(r['evidence'])
        self.assertIn('同专精',''.join(r['analysis']))
        self.assertNotIn('没开技能',''.join(r['analysis']))

    def test_narrative_keeps_death_numerical_cause_without_blame_on_healer(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        text=format_battle(self.apply(),'battle_review')
        self.assertIn('1150',text);self.assertIn('900',text)
        self.assertNotIn('治疗失误',text);self.assertNotIn('没奶',text)
        self.assertNotIn('战斗影响：',text)

    def test_summary_keeps_whole_fight_pressure_and_causal_evidence_in_paragraphs(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        text=format_battle(self.apply())
        for word in ('整场结论','队伍表现','减员原因','承伤片段','00:20'):self.assertIn(word,text)
        self.assertNotIn('贡献结论：',text)
        self.assertLessEqual(len(text),1200)

    def test_caps_and_serialized_context_keep_every_selected_person(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        for key in (False,True):
            p,t,m,s=fixture()
            if key:p['fight'].update(keystoneLevel=12,difficulty=10)
            p=self.apply((p,t,m,s));p=json.loads(json.dumps(p))
            for kind,field in [('battle_good','good'),('battle_review','review')]:
                text=format_battle(p,kind)
                self.assertLessEqual(len(p[field]),2 if key else 3)
                self.assertLessEqual(len(text),1200)
                for row in p[field]:self.assertIn(row['name'],text)

    def test_malformed_profile_identity_is_ignored_without_poisoning_valid_analysis(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        p,t,m,s=fixture();s['profileDetails']['data']['playerDetails']['dps'][0]['server']=['测试服']
        p=self.apply((p,t,m,s))
        self.assertIsNone(p['playerAssessments'][1].get('score'))
        self.assertIn('1150',format_battle(p,'battle_review'))

    def test_same_identity_on_two_report_actors_is_not_assigned_one_rank_twice(self):
        from server.app.channels.qq_official.battle_profile import collect_profiles
        p,t,m,s=fixture()
        for container in (t['playerDetails'],s['profileDetails']):
            container['data']['playerDetails']['dps'][2]['name']='输出甲'
        profiles=collect_profiles(p,t,s)
        self.assertIsNone(profiles[1].get('score'));self.assertIsNone(profiles[5].get('score'))

    def test_three_just_topped_up_deaths_keep_the_actual_lethal_damage_sentence(self):
        from server.app.channels.qq_official.battle_causes import analyze_death
        from server.app.channels.qq_official.battle_commands import format_battle
        from tests.app_qq_battle_depth_test import case
        p,t,m,s=fixture();p['review']=[];p['deaths']=[]
        for actor in (1,2,5):
            d,b,master,roles,start=case(77);d['actorId']=actor;b['actorId']=actor
            for page in ('incoming','damage'):
                for e in b[page]['events']:e['targetID']=actor
            row=analyze_death(d,b,master,{actor:'dps'},start,p['reportCode'],p['fightId'])
            row['name']='长名字代表'+str(actor);row['deathCount']=1
            self.assertIn('已被补满',row['conclusion'])
            p['review'].append(row);p['deaths'].append(d)
            s['casts']['data']['entries'].append({'id':actor,'total':500})
        p['roleContributions']['damage']=[]
        p=self.apply((p,t,m,s));text=format_battle(p,'battle_review')
        self.assertEqual(text.count('1150'),3)
        self.assertLessEqual(len(text),1200)

    def test_missing_optional_profile_data_keeps_supported_contribution_and_causes(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        p,t,m,s=fixture();p=self.apply((p,t,m,{}))
        text=format_battle(p,'battle_good')
        self.assertNotIn('WCL分数',text);self.assertIn('中断施法1次',text)
        self.assertIn('1150',format_battle(p,'battle_review'))


if __name__=='__main__':unittest.main()

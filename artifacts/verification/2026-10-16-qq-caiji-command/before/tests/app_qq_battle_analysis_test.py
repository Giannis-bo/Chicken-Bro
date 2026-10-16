"""Battle contracts run on the cloud; synthetic facts never replace live evidence."""
import copy
import importlib
import unittest

URL = 'https://www.warcraftlogs.com/reports/ABCDEFGHIJKLMNOP'


def report_fixture(kill=True):
    fight = {'id':5,'name':"Ula'tek",'encounterID':3492,'difficulty':4,'kill':kill,
             'startTime':100000,'endTime':160000,'friendlyPlayers':[1,2,3,4,5],
             'inProgress':False,'keystoneLevel':None}
    actors = [{'id':i,'name':name,'type':'Player','subType':'Mage'} for i,name in
              [(1,'输出甲'),(2,'输出乙'),(3,'治疗甲'),(4,'坦克甲'),(5,'输出丙')]]
    actors.append({'id':9,'name':'宠物','type':'Pet','petOwner':1})
    return {'code':'ABCDEFGHIJKLMNOP','visibility':'public','fights':[fight],
            'masterData':{'actors':actors,'abilities':[{'gameID':77,'name':'危险技能'}]},
            'playerDetails':{'data':{'playerDetails':{
                'dps':[{'id':1},{'id':2},{'id':5}], 'healers':[{'id':3}], 'tanks':[{'id':4}]}}},
            'damage':{'data':{'entries':[{'id':1,'total':6000},{'id':2,'total':3000},
                                         {'id':5,'total':1000},{'id':9,'total':90000}]}},
            'healing':{'data':{'entries':[{'id':3,'total':5000,'overheal':20000}]}},
            'deaths':{'data':[{'type':'death','timestamp':120000,'targetID':2,
                               'killingAbilityGameID':77,'killerID':30},
                              {'type':'death','timestamp':120000,'targetID':5},
                              {'type':'death','timestamp':124000,'targetID':2},
                              {'type':'death','timestamp':121000,'targetID':9}],
                      'nextPageTimestamp':None}}


class BattleAnalysisTest(unittest.TestCase):
    def setUp(self):
        try:
            self.commands = importlib.import_module('server.app.channels.qq_official.battle_commands')
            self.source_module = importlib.import_module('server.app.channels.qq_official.battle_source')
        except ImportError:
            self.fail('QQ battle analysis not implemented')
        self.report = report_fixture()
        self.calls = []

    def graphql(self, query, variables=None, **kwargs):
        self.calls.append((query,variables))
        r = copy.deepcopy(self.report)
        if 'QqBattleEvents' in query:
            if variables['type']=='Deaths':return {'reportData':{'report':{'events':r['deaths']}}}
            r = {'events':{'data':[
                {'type':'damage','timestamp':119000,'sourceID':30,'targetID':2,'abilityGameID':77,'amount':500},
                {'type':'damage','timestamp':119500,'sourceID':30,'targetID':2,'abilityGameID':77,'amount':700,'hitPoints':0,'overkill':10},
                {'type':'damage','timestamp':120000,'sourceID':30,'targetID':5,'abilityGameID':77,'amount':300}],
                'nextPageTimestamp':None}}
        return {'reportData':{'report':r}}

    def read(self, text=None):
        request=self.commands.parse_battle(text or '/战斗分析 '+URL+'?fight=5')
        return self.source_module.BattleSource(graphql=self.graphql).query(request)

    def test_parse_summary_detail_and_explicit_fight(self):
        from server.app.channels.qq_official.query_commands import parse_query
        q=parse_query('/战斗分析 '+URL+'?fight=5&source=2&locale=cn 场次=6')
        self.assertEqual((q.kind,q.fight_id),('battle_summary',6))
        self.assertNotIn('source=',q.url)
        for command,kind in [('/战斗详情-大腿','battle_good'),('/战斗详情-毒瘤','battle_review')]:
            q=parse_query(command);self.assertEqual((q.kind,q.url),(kind,''))

    def test_strict_input_rejects_unknown_commands_hosts_and_conflicts(self):
        for text in ('/战斗分析','/战斗分析 ftp://warcraftlogs.com/reports/ABCDEFGHIJKLMNOP',
                     '/战斗分析 '+URL+'?fight=invalid','/战斗分析 '+URL+' 场次=0',
                     '/战斗分析 '+URL+' 场次=5 场次=6',
                     '/战斗分析 '+URL+'?fight=5&fight=6',
                     '/战斗分析 https://warcraftlogs.com.evil.invalid/reports/ABCDEFGHIJKLMNOP',
                     '/战斗分析 '+URL+' 随便分析','/战斗详情-大腿 他人的编号'):
            with self.subTest(text=text),self.assertRaises(ValueError):self.commands.parse_battle(text)

    def test_missing_fight_lists_both_kills_and_wipes_and_no_events(self):
        wipe=copy.deepcopy(self.report['fights'][0]);wipe.update(id=6,kill=False)
        self.report['fights'].append(wipe)
        p=self.read('/战斗分析 '+URL)
        self.assertEqual(p['status'],'selection')
        text=self.commands.format_battle(p,'battle_summary')
        for s in ('已击杀','灭团','5','6','场次='):self.assertIn(s,text)
        self.assertEqual(len(self.calls),1)

    def test_report_without_finished_raid_fights_has_explicit_empty_result(self):
        self.report['fights']=[]
        p=self.read('/战斗分析 '+URL)
        self.assertEqual(p['status'],'blocked')
        self.assertIn('没有',self.commands.format_battle(p,'battle_summary'))

    def test_kill_and_wipe_use_fight_relative_time_and_complete_deaths(self):
        for kill in (True,False):
            self.report['fights'][0]['kill']=kill
            p=self.read()
            self.assertEqual(p['status'],'ready')
            self.assertEqual(len(p['deaths']),3)
            self.assertEqual([d['time'] for d in p['deaths']],[20,20,24])
            text=self.commands.format_battle(p,'battle_summary')
            self.assertIn('已击杀' if kill else '灭团',text)
            self.assertIn('00:20',text)
            self.assertLessEqual(len(text),1200)
            self.assertIn('/战斗详情-毒瘤',text)

    def test_good_is_role_scoped_effective_healing_and_excludes_pets(self):
        p=self.read();rows=p['good']
        self.assertLessEqual(len(rows),3)
        self.assertIn(1,[r['actorId'] for r in rows])
        self.assertIn(3,[r['actorId'] for r in rows])
        self.assertNotIn(9,[r['actorId'] for r in rows])
        healer=next(r for r in rows if r['actorId']==3)
        self.assertEqual(healer['amount'],5000)
        self.assertEqual(healer['metric'],'effective_healing')

    def test_sampled_team_damage_window_preserves_targets_and_ability_evidence(self):
        p=self.read()
        windows=p['damageWindows']
        self.assertTrue(windows)
        window=next(w for w in windows if w['amount']==1500)
        self.assertEqual(window['targetCount'],2)
        self.assertEqual(window['abilities'][0]['abilityId'],77)
        self.assertTrue(window['complete'])
        self.assertIn('承伤片段',self.commands.format_battle(p,'battle_summary'))

    def test_first_three_distinct_deaths_have_their_own_damage_windows(self):
        from server.app.channels.qq_official.battle_analysis import select_windows
        fight={'startTime':0,'endTime':600000,'friendlyPlayers':[1,2,3]}
        deaths=[{'type':'death','targetID':i,'timestamp':t} for i,t in
                [(1,30000),(1,60000),(2,120000),(3,300000)]]
        windows=select_windows(fight,deaths)
        for t in (30000,120000,300000):
            self.assertTrue(any(a<=t-5000 and b>t for a,b in windows))
        self.assertLessEqual(len(windows),3)

    def test_review_has_actor_window_and_source_evidence_without_fault_inference(self):
        p=self.read();rows=p['review']
        self.assertGreater(len(rows),0);self.assertLessEqual(len(rows),3)
        for row in rows:
            self.assertIn(row['actorId'],(2,5))
            self.assertTrue(row['evidence'])
            for e in row['evidence']:
                self.assertEqual(e['reportCode'],'ABCDEFGHIJKLMNOP')
                self.assertEqual(e['fightId'],5)
        text=self.commands.format_battle(p,'battle_review')
        for claim in ('可规避','操作失误','治疗没奶','驱散延迟','技能可用','浪费了'):
            self.assertNotIn(claim,text)

    def test_no_deaths_does_not_manufacture_review_targets(self):
        self.report['deaths']['data']=[]
        p=self.read()
        self.assertEqual(p['review'],[])
        self.assertIn('暂无',self.commands.format_battle(p,'battle_review'))

    def test_missing_actor_and_missing_damage_table_do_not_become_zero_or_ranks(self):
        self.report['masterData']['actors']=[a for a in self.report['masterData']['actors'] if a['id']!=2]
        self.report['damage']={}
        p=self.read()
        self.assertFalse(p['coverage']['damage'])
        self.assertFalse(any(r['metric']=='damage' for r in p['good']))
        self.assertIn('未完整',self.commands.format_battle(p,'battle_summary'))

    def test_missing_or_conflicting_role_mapping_cannot_inflate_contribution(self):
        self.report['playerDetails']['data']['playerDetails']['dps']=[{'id':1},{'id':5}]
        p=self.read()
        self.assertFalse(p['coverage']['damage'])
        self.assertFalse(p['good'])
        self.report=report_fixture()
        self.report['playerDetails']['data']['playerDetails']['healers'].append({'id':1})
        self.assertFalse(self.read()['good'])

    def test_malformed_death_event_cannot_prove_zero_deaths(self):
        self.report['deaths']['data']=[{'timestamp':120000,'type':'death'}]
        p=self.read()
        self.assertFalse(p['coverage']['deaths'])
        self.assertNotIn('未记录玩家死亡',self.commands.format_battle(p,'battle_summary'))

    def test_private_in_progress_trash_and_absent_fight_are_rejected(self):
        for field,value in [('visibility','private'),('inProgress',True),('encounterID',0)]:
            self.report=report_fixture()
            if field=='visibility':self.report[field]=value
            else:self.report['fights'][0][field]=value
            self.assertNotEqual(self.read()['status'],'ready')
        self.report=report_fixture();self.assertNotEqual(self.read('/战斗分析 '+URL+' 场次=99')['status'],'ready')

    def test_detail_without_context_is_not_a_network_call(self):
        p=self.source_module.BattleSource(graphql=self.graphql).query(self.commands.parse_battle('/战斗详情-大腿'))
        self.assertEqual(p['status'],'missing_context');self.assertEqual(self.calls,[])

    def test_detail_reuses_exact_context_without_reading_other_report(self):
        p=self.read();self.calls=[]
        got=self.source_module.BattleSource(graphql=self.graphql).query(
            self.commands.parse_battle('/战斗详情-毒瘤'),context=p)
        self.assertEqual(got['reportCode'],p['reportCode']);self.assertEqual(self.calls,[])

    def test_provider_error_is_bounded_and_redacted(self):
        def broken(*args,**kwargs):raise RuntimeError('secret-token-do-not-print')
        p=self.source_module.BattleSource(graphql=broken).query(self.commands.parse_battle('/战斗分析 '+URL+'?fight=5'))
        self.assertEqual(p['status'],'unavailable')
        self.assertNotIn('secret-token',str(p))

    def test_metadata_only_after_all_statistical_reads_fail_is_not_success(self):
        def metadata_only(query,variables,**kwargs):
            if 'QqBattleContext' in query:return self.graphql(query,variables,**kwargs)
            raise TimeoutError()
        p=self.source_module.BattleSource(graphql=metadata_only).query(
            self.commands.parse_battle('/战斗分析 '+URL+'?fight=5'))
        self.assertEqual(p['status'],'unavailable')

    def test_long_names_many_deaths_stay_one_complete_message(self):
        p=self.read()
        for row in p['good']+p['review']:row['name']='很长的中文角色名[*]'*100
        for kind in ('battle_summary','battle_good','battle_review'):
            text=self.commands.format_battle(p,kind)
            self.assertLessEqual(len(text),1200)
            self.assertIn('warcraftlogs.com',text)
            from server.app.channels.qq_official.query_commands import markdown_parts
            self.assertEqual(len(markdown_parts(text)),1)


class BattlePaginationTest(unittest.TestCase):
    def test_missing_damage_target_and_wrong_fight_are_not_complete(self):
        from server.app.channels.qq_official.battle_source import read_events
        for event in ({'type':'damage','timestamp':150,'amount':10},
                      {'type':'damage','timestamp':150,'targetID':1,'amount':10,'fight':6}):
            result=read_events(lambda v:{'data':[event],'nextPageTimestamp':None},
                               {'start':100,'end':300,'type':'DamageTaken','ids':[5]})
            self.assertFalse(result['complete'])

    def test_boundary_half_open_no_dedup_of_legitimate_same_time_events(self):
        from server.app.channels.qq_official.battle_source import read_events
        pages=[{'data':[{'timestamp':100,'type':'damage'},{'timestamp':200,'type':'damage'}],
                'nextPageTimestamp':200},
               {'data':[{'timestamp':200,'type':'damage'},{'timestamp':200,'type':'damage'},
                        {'timestamp':300,'type':'damage'}],'nextPageTimestamp':None}]
        def fetch(variables):return pages.pop(0)
        result=read_events(fetch,{'start':100,'end':300},max_pages=3)
        self.assertTrue(result['complete'])
        self.assertEqual([e['timestamp'] for e in result['events']],[100,200,200])

    def test_stalled_cursor_missing_page_and_page_cap_are_partial(self):
        from server.app.channels.qq_official.battle_source import read_events
        for page in ({'data':[],'nextPageTimestamp':100},{'data':[]},
                     {'data':[],'nextPageTimestamp':150}):
            result=read_events(lambda v:page,{'start':100,'end':300},max_pages=1)
            self.assertFalse(result['complete'])


if __name__=='__main__':unittest.main()

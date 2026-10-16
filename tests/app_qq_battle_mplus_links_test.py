"""Shared-link compatibility and whole-key semantics at the real QQ boundary."""
import copy
import unittest

from tests.app_qq_battle_analysis_test import report_fixture

BASE='https://www.warcraftlogs.com/reports/ABCDEFGHIJKLMNOP'


class BattleLinksTest(unittest.TestCase):
    def parse(self,url,extra=''):
        from server.app.channels.qq_official.battle_commands import parse_battle
        return parse_battle('/战斗分析 '+url+extra)

    def test_url_variants_resolve_same_report_and_numeric_fight(self):
        variants=[
            BASE+'?fight=5&type=damage-done&source=all&target=99&start=12&end=89',
            BASE+'#type=summary&fight=5&view=events&pins=anything',
            'https://cn.warcraftlogs.com/reports/ABCDEFGHIJKLMNOP/#fight=5',
            'https://www.warcraftlogs.com/reports/ABCDEFGHIJKLMNOP/summary?fight=5',
            'https://de.warcraftlogs.com/reports/ABCDEFGHIJKLMNOP?fight=5&translate=true',
            'http://warcraftlogs.com/reports/ABCDEFGHIJKLMNOP?fight=5',
            'www.warcraftlogs.com/reports/ABCDEFGHIJKLMNOP?fight=5',
            '<'+BASE+'?fight=5&type=summary>',
            '[这场 战斗]('+BASE+'?fight=5&type=summary)',
            BASE+'?type=damage-done&amp;fight=5',
            BASE+'?fight=5#fight=5&type=summary',
            BASE+'?fight=%35&type=summary',
            BASE+'?fight=5。',
        ]
        for url in variants:
            with self.subTest(url=url):
                r=self.parse(url)
                self.assertEqual(r.url,BASE)
                self.assertEqual(r.fight_id,5)

    def test_last_all_and_multiple_fights_preserve_selection_intent(self):
        for value in ('last','all','1,2'):
            with self.subTest(value=value):self.assertEqual(self.parse(BASE+'#fight='+value).fight_id,value)
        self.assertEqual(self.parse(BASE+'?fight=last',' 场次=3').fight_id,3)

    def test_rejects_lookalikes_credentials_ports_and_conflicting_fights(self):
        for url in (
            'https://warcraftlogs.com.evil.invalid/reports/ABCDEFGHIJKLMNOP?fight=5',
            'https://evilwarcraftlogs.com/reports/ABCDEFGHIJKLMNOP?fight=5',
            'https://user:password@warcraftlogs.com/reports/ABCDEFGHIJKLMNOP?fight=5',
            'https://warcraftlogs.com:8443/reports/ABCDEFGHIJKLMNOP?fight=5',
            'ftp://warcraftlogs.com/reports/ABCDEFGHIJKLMNOP?fight=5',
            BASE+'?fight=5#fight=6',BASE+'?fight=0',BASE+'?fight=bad',
            BASE+'?fight=1,,2',BASE+'?fight=',
            'https://warcraftlogs.com/reports/ABC',
            'https://warcraftlogs.com/character/ABCDEFGHIJKLMNOP?fight=5'):
            with self.subTest(url=url),self.assertRaises(ValueError):self.parse(url)

    def test_extra_views_do_not_change_whole_fight_selection(self):
        for key in ('source','target','ability','type','start','end','phase','pins','filter','locale','translate','view','options'):
            self.assertEqual(self.parse(BASE+'?fight=5&'+key+'=arbitrary%20text').fight_id,5)


class BattleMplusTest(unittest.TestCase):
    def setUp(self):
        self.report=report_fixture()
        self.report['fights'][0].update(id=1,difficulty=10,keystoneLevel=12,name='测试大秘境',kill=True)
        self.report['deaths']['data']=[]
        self.calls=[]

    def read(self,suffix='?fight=1'):
        from server.app.channels.qq_official.battle_source import BattleSource
        from server.app.channels.qq_official.battle_commands import parse_battle
        def graphql(q,v,**kw):
            self.calls.append((q,v))
            if 'QqBattleEvents' in q:
                return {'reportData':{'report':{'events':{'data':[],'nextPageTimestamp':None}}}}
            return {'reportData':{'report':copy.deepcopy(self.report)}}
        return BattleSource(graphql=graphql).query(parse_battle('/战斗分析 '+BASE+suffix))

    def test_completed_key_is_analyzed_with_level_and_completion_not_raid_kill(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        p=self.read()
        self.assertEqual(p['status'],'ready')
        self.assertEqual(p['battleType'],'mythic_plus')
        self.assertEqual(p['fight']['keystoneLevel'],12)
        for kind in ('battle_summary','battle_good','battle_review'):
            text=format_battle(p,kind)
            self.assertIn('大秘境+12',text)
            self.assertIn('已完成',text)
            self.assertNotIn('已击杀',text)
            self.assertNotIn('限时',text)
            self.assertLessEqual(len(text),1200)

    def test_mplus_good_and_review_are_limited_to_two_but_raid_keeps_three(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        from server.app.channels.qq_official.battle_causes import apply_causes
        from tests.app_qq_battle_depth_test import case
        p=self.read()
        self.assertEqual(p['detailMaxPlayers'],2)
        self.assertEqual(len(p['good']),2)
        good=copy.deepcopy(p['good'][0]);good.update(actorId=999,name='不可出现的第三人')
        p['good'].append(good)
        self.assertNotIn('不可出现的第三人',format_battle(p,'battle_good'))
        deaths=[];bundles=[];actors=[]
        for i,name in [(1,'角色甲'),(2,'角色乙'),(3,'不可出现的第三人')]:
            d,b,m,roles,start=case(ability=70+i)
            d.update(actorId=i,name=name);b['actorId']=i
            for key in ('damage','incoming'):
                for e in b[key]['events']:e['targetID']=i
            deaths.append(d);bundles.append(b);actors.append({'id':i,'name':name,'type':'Player'})
        p['deaths']=deaths
        p['fight']['startTime']=100000
        p=apply_causes(p,bundles,{'actors':actors+[{'id':30,'name':'怪物','type':'NPC'}]}, {})
        self.assertEqual(len(p['review']),2)
        review=copy.deepcopy(p['review'][0]);review.update(actorId=999,name='不可出现的第三人')
        p['review'].append(review)
        self.assertNotIn('不可出现的第三人',format_battle(p,'battle_review'))
        self.report=report_fixture();self.report['deaths']['data']=[]
        raid=self.read('?fight=5')
        self.assertEqual(raid['detailMaxPlayers'],3)
        self.assertEqual(len(raid['good']),3)

    def test_ended_incomplete_key_is_not_called_a_single_wipe(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        self.report['fights'][0]['kill']=False
        p=self.read()
        self.assertEqual(p['status'],'ready')
        self.assertIn('未完成',format_battle(p))
        self.assertNotIn('灭团',format_battle(p))

    def test_dungeon_title_uses_log_game_zone_instead_of_boss_list(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        self.report['fights'][0].update(name='首领甲 / 首领乙 / ...',
                                       gameZone={'id':2813,'name':'Murder Row'})
        p=self.read()
        self.assertIn('密谋小径',format_battle(p).splitlines()[0])
        self.assertEqual(p['fight']['name'],'首领甲 / 首领乙 / ...')

    def test_last_resolves_report_metadata_and_ignores_trash_segments(self):
        second=copy.deepcopy(self.report['fights'][0]);second.update(id=2,startTime=200000,endTime=260000)
        trash=copy.deepcopy(second);trash.update(id=3,encounterID=0,startTime=270000,endTime=280000,keystoneLevel=0)
        self.report['fights'] += [second,trash]
        p=self.read('?fight=last&type=damage-done')
        self.assertEqual(p['fightId'],2)

    def test_last_in_progress_does_not_silently_analyze_earlier_key(self):
        second=copy.deepcopy(self.report['fights'][0]);second.update(id=2,startTime=200000,endTime=260000,inProgress=True)
        self.report['fights'].append(second)
        p=self.read('?fight=last')
        self.assertEqual(p['status'],'blocked')
        self.assertIn('进行',p['message'])

    def test_report_overview_lists_keys_and_raids_with_accurate_status(self):
        from server.app.channels.qq_official.battle_commands import format_battle
        raid=copy.deepcopy(self.report['fights'][0]);raid.update(id=2,keystoneLevel=0,difficulty=4,name='团本首领')
        self.report['fights'].append(raid)
        p=self.read('?fight=all&type=summary')
        self.assertEqual(p['status'],'selection')
        text=format_battle(p)
        self.assertIn('大秘境+12',text)
        self.assertIn('已完成',text)
        self.assertIn('已击杀',text)

    def test_multi_fight_link_offers_matching_single_fight_choices(self):
        for i in (2,3):
            row=copy.deepcopy(self.report['fights'][0]);row['id']=i;self.report['fights'].append(row)
        p=self.read('?fight=1,2')
        self.assertEqual(p['status'],'selection')
        self.assertEqual({f['id'] for f in p['fights']},{1,2})

    def test_in_progress_and_unsupported_content_have_specific_reasons(self):
        self.report['fights'][0]['inProgress']=True
        self.assertIn('进行',self.read()['message'])
        self.report['fights'][0].update(inProgress=False,encounterID=0,difficulty=0,keystoneLevel=0)
        message=self.read()['message']
        self.assertNotIn('不存在',message)
        self.assertIn('类型',message)

    def test_unlisted_readable_report_is_allowed_but_private_is_blocked(self):
        self.report['visibility']='unlisted'
        self.assertEqual(self.read()['status'],'ready')
        self.report['visibility']='private'
        self.assertEqual(self.read()['status'],'blocked')


if __name__=='__main__':unittest.main()

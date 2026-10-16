"""Chinese game labels are source-localized; character names and IDs are intact."""
import copy
import os
import unittest
from unittest.mock import patch

from tests.app_chickenbro_wcl_source_test import FakeResponse
from tests.app_qq_battle_analysis_test import report_fixture,URL


class WclLocaleRoutingTest(unittest.TestCase):
    def test_explicit_cn_locale_uses_fixed_cn_endpoint_without_changing_environment(self):
        from server.app.chickenbro import wcl_source as w
        with patch.dict(os.environ,{'WOW_WARCRAFTLOGS_GRAPHQL_URL':'https://www.warcraftlogs.com/api/v2/client'}):
            before=dict(os.environ)
            with patch.object(w,'_oauth_token',return_value='test-token'), patch.object(w,'urlopen',return_value=FakeResponse({'data':{}})) as opened:
                w._graphql('query',locale='zhCN')
                req=opened.call_args.args[0]
                self.assertEqual(req.full_url,'https://cn.warcraftlogs.com/api/v2/client')
                self.assertEqual(req.get_header('Accept-language'),'zh-CN')
                w._graphql('query')
                self.assertEqual(opened.call_args.args[0].full_url,'https://www.warcraftlogs.com/api/v2/client')
            self.assertEqual(dict(os.environ),before)

    def test_unknown_locale_cannot_select_arbitrary_authenticated_host(self):
        from server.app.chickenbro import wcl_source as w
        with patch.object(w,'urlopen') as opened,patch.object(w,'_oauth_token',return_value='test-token'):
            with self.assertRaises(ValueError):w._graphql('query',locale='https://evil.invalid')
            opened.assert_not_called()


class BattleLocaleTest(unittest.TestCase):
    def test_default_battle_reader_uses_cn_for_every_read_and_preserves_player_names(self):
        from server.app.channels.qq_official.battle_source import BattleSource
        from server.app.channels.qq_official.battle_commands import parse_battle,format_battle
        r=report_fixture();r['fights'][0]['name']='利希尔·烬怒 / 歼灭者萨祖克斯 / ...'
        r['masterData']['actors'][0]['name']='Giannis'
        r['masterData']['actors'].append({'id':30,'gameID':235465,'type':'NPC','name':'破坏魔惩罚者'})
        r['masterData']['abilities']=[{'gameID':77,'name':'绝命凶径'}]
        r['deaths']['data']=[]
        reads=[]
        def graphql(q,v,**kwargs):
            reads.append(kwargs)
            value=copy.deepcopy(r)
            if 'QqBattleEvents' in q:value={'events':{'data':[],'nextPageTimestamp':None}}
            return {'reportData':{'report':value}}
        with patch('server.app.channels.qq_official.battle_source._graphql',side_effect=graphql):
            p=BattleSource().query(parse_battle('/战斗分析 '+URL+'?fight=5'))
        self.assertTrue(reads)
        self.assertTrue(all(v.get('locale')=='zhCN' for v in reads))
        self.assertEqual(p['localizationLocale'],'zhCN')
        self.assertIn('利希尔·烬怒',format_battle(p))
        self.assertIn('Giannis',format_battle(p,'battle_good'))
        self.assertEqual(p['fightId'],5)

    def test_old_english_context_requires_fresh_cn_analysis(self):
        from server.app.channels.qq_official.battle_source import BattleSource
        from server.app.channels.qq_official.battle_commands import BattleRequest
        p=BattleSource().query(BattleRequest('battle_review'),context={
            'schema':'qq-battle-v1','status':'ready','analysisVersion':'death-causes-v2'})
        self.assertEqual(p['status'],'stale_context')

    def test_npc_context_filter_uses_game_id_not_translated_name(self):
        from server.app.channels.qq_official.battle_source import BattleSource
        from server.app.channels.qq_official.battle_commands import parse_battle
        r=report_fixture();r['deaths']['data']=r['deaths']['data'][:1]
        r['deaths']['data'][0].update(killingAbilityGameID=1,killerID=30)
        r['masterData']['actors'].append({'id':30,'gameID':259555,'name':'血腥响尾','type':'NPC'})
        hit={'type':'damage','timestamp':119990,'sourceID':30,'sourceInstance':1,'targetID':2,
             'abilityGameID':1,'amount':500,'overkill':100,'hitPoints':0,'maxHitPoints':400}
        def page(events):return {'data':events,'nextPageTimestamp':None}
        filters=[]
        def graphql(q,v,**kw):
            if 'QqBattleFocusedEvents' in q:
                filters.append(v['filter'])
                return {'reportData':{'report':{'events':page([])}}}
            if 'QqBattleFocus(' in q:
                return {'reportData':{'report':{'incoming':page([hit]),'damage':page([hit]),'casts':page([])}}}
            if 'QqBattleEvents' in q:
                return {'reportData':{'report':{'events':r['deaths'] if v['type']=='Deaths' else page([hit])}}}
            return {'reportData':{'report':copy.deepcopy(r)}}
        p=BattleSource(graphql=graphql).query(parse_battle('/战斗分析 '+URL+'?fight=5'))
        self.assertEqual(p['status'],'ready')
        self.assertIn('source.id = 259555',filters)
        self.assertFalse(any('血腥响尾' in f for f in filters))


if __name__=='__main__':unittest.main()

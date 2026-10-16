import copy
import importlib
import re
import unittest

CATALOG = {'worldData': {'zones': [
    {'id':53,'name':'The Venomous Abyss','frozen':False,'partitions':[{'id':2,'name':'12.1.5','default':True}],
     'difficulties':[{'id':3,'name':'Normal'},{'id':4,'name':'Heroic'},{'id':5,'name':'Mythic'}],
     'encounters':[{'id':3470,'name':"Nek'zali the Soulcoiler"},{'id':3445,'name':'Entombed Sentinels'}]},
    {'id':55,'name':'Mythic+ Season 2','frozen':False,'partitions':[{'id':1,'name':'Season 2','default':True}],
     'difficulties':[{'id':10,'name':'Dungeon'}], 'encounters':[{'id':61762,'name':"Kings' Rest"}]},
    {'id':54,'name':'PTR Raid','frozen':False,'partitions':[{'id':1,'default':True}],
     'difficulties':[{'id':4,'name':'Heroic'}],'encounters':[{'id':1,'name':'PTR Boss'}]}]}}
CHARACTER = {'id':72040639,'name':'Giannis','hidden':False,'server':{'name':'白银之手','slug':'silver-hand','region':{'slug':'CN'}},
 'gameData': {'global':{'name':'Giannis','realm':{'name':'白银之手','slug':'silver-hand'},'race':{'name':'黑铁矮人'},
    'character_class':{'id':7,'name':'萨满祭司'},'active_spec':{'name':'元素'},'equipped_item_level':317,
    'last_login_timestamp':1788709458000}, 'talents':{'specializations':[{'specialization':{'id':262},
        'loadouts':[{'is_active':True,'selected_hero_talent_tree':{'id':56,'name':'先知'}}]}]}}}
PROFILE = {'name':'Giannis','realm':'Silver Hand','region':'cn','race':'Dark Iron Dwarf','class':'Shaman',
 'active_spec_name':'Elemental','active_spec_role':'DPS','profile_url':'https://raider.io/characters/cn/silver-hand/Giannis',
 'last_crawled_at':'2026-10-13T14:51:57Z','gear':{'item_level_equipped':327,'updated_at':'2026-10-13T14:51:58Z'}}
DETAILS = {'characterDetails':{'character':{'name':'Giannis','path':'/characters/cn/silver-hand/Giannis',
 'region':{'slug':'cn'},'realm':{'slug':'silver-hand','name':'Silver Hand','altName':'白银之手'},
 'class':{'id':7,'name':'Shaman'},'spec':{'id':262,'name':'Elemental','role':'dps'},'race':{'name':'Dark Iron Dwarf'},
 'itemLevelEquipped':327,'talentLoadout':{'heroSubTreeId':56}}}}


class CharacterSourceTest(unittest.TestCase):
    def setUp(self):
        try:
            self.module = importlib.import_module('server.app.channels.qq_official.character_source')
        except ImportError:
            self.fail('read-only character source not implemented')
        from server.app.channels.qq_official.query_commands import parse_query
        self.parse = parse_query
        self.character = copy.deepcopy(CHARACTER)
        self.profile = copy.deepcopy(PROFILE)
        self.details = copy.deepcopy(DETAILS)
        self.requests = []
        self.catalog = copy.deepcopy(CATALOG)
        self.runs = [
          {'rankPercent':75.5,'amount':10000,'spec':'Elemental','bracketData':12,'medal':'bronze',
           'startTime':1791893839574,'report':{'code':'mZBg8DbyNdTrXcFL','fightID':5}},
          {'rankPercent':99.9,'amount':20000,'spec':'Elemental','bracketData':15,'medal':'none',
           'startTime':1791883839574,'report':{'code':'mZBg8DbyNdTrXcFL','fightID':2}}]

        self.raid_runs=[{'rankPercent':86.4,'amount':1234,'spec':'Elemental',
                        'startTime':1791893839574,'report':{'code':'mZBg8DbyNdTrXcFL','fightID':5}}]

    def graphql(self, query, variables=None, **kwargs):
        self.requests.append((query, variables))
        if 'worldData' in query: return self.catalog
        if 'gameData' in query: return {'characterData':{'character':self.character}}
        result={'id':72040639}
        for alias,args in re.findall(r'(q\d+):encounterRankings\(([^)]+)\)',query):
            eid=int(re.search(r'encounterID:(\d+)',args)[1])
            diff=int(re.search(r'difficulty:(\d+)',args)[1])
            metric=re.search(r'metric:(\w+)',args)[1]
            zone=next(z for z in self.catalog['worldData']['zones'] if any(e['id']==eid for e in z['encounters']))
            ranks=copy.deepcopy(self.runs if diff==10 else self.raid_runs if eid==3470 and diff==4 else [])
            ranks=[r for r in ranks if (r.get('spec')=='Restoration') == (metric=='hps')]
            result[alias]={'zone':zone['id'],'partition':int(re.search(r'partition:(-?\d+)',args)[1]),
                           'difficulty':diff,'metric':metric,'totalKills':len(ranks),'ranks':ranks}
        return {'characterData':{'character':result}}

    def fetch(self, url):
        return self.details if '/api/characters/' in url else self.profile

    def source(self):
        return self.module.CharacterQuerySource(graphql=self.graphql, fetch=self.fetch)

    def test_chinese_realm_current_profile_and_verified_hero(self):
        result = self.source().query(self.parse('/角色查询 Giannis 白银之手'))
        p = result['profile']
        self.assertEqual((p['race'],p['class'],p['spec'],p['hero'],p['itemLevel']),
                         ('黑铁矮人','萨满祭司','元素','先知',327))
        self.assertIn('2026-10-13',p['sourceTime'])
        self.assertEqual(self.requests[0][1]['realm'],'白银之手')

    def test_exact_layer_uses_real_runs_not_highest_level_summary(self):
        r = self.source().query(self.parse('/角色大米查询 Giannis 白银之手 副本=诸王之眠 层数=12'))
        rows = r['sections'][0]['rows']
        self.assertEqual([(x['level'],x['percentile'],x['timed']) for x in rows], [(12,75.5,True)])
        call = next(q for q,_ in self.requests if 'encounterRankings' in q)
        self.assertIn('byBracket:true',call)
        self.assertIn('compare:Rankings',call)
        self.assertIn('includePrivateLogs:false',call)

    def test_raid_includes_all_patch_partitions_and_filters_boss(self):
        r = self.source().query(self.parse('/角色团本查询 Giannis 白银之手 Boss=内克扎莉 难度=英雄'))
        self.assertEqual(r['sections'][0]['rows'][0]['percentile'],86.4)
        self.assertIn('全部分区',r['sections'][0]['scope'])
        calls = [q for q,_ in self.requests if 'encounterRankings' in q]
        self.assertTrue(any('encounterID:3470' in q and 'partition:-1' in q and 'difficulty:4' in q for q in calls))
        self.assertFalse(any('encounterID:1,' in q for q in calls))

    def test_identity_mismatch_does_not_emit_other_character_facts(self):
        self.character['name'] = 'Other'
        r = self.source().query(self.parse('/角色查询 Giannis 白银之手'))
        self.assertNotIn('profile', r)
        self.assertEqual(r['sections'][0]['status'], 'identity_mismatch')

    def test_wrong_raider_identity_never_uses_its_item_level(self):
        self.profile['name']='Other'; self.profile['gear']['item_level_equipped']=999
        r = self.source().query(self.parse('/角色查询 Giannis 白银之手'))
        self.assertNotEqual(r.get('profile',{}).get('itemLevel'),999)

    def test_missing_layer_not_zero_and_unknown_names_return_candidates(self):
        r = self.source().query(self.parse('/角色大米查询 Giannis 白银之手 副本=诸王之眠 层数=17'))
        self.assertEqual(r['sections'][0]['status'],'no_records')
        r = self.source().query(self.parse('/角色大米查询 Giannis 白银之手 副本=不存在'))
        self.assertIn('诸王之眠',r['sections'][0]['message'])

    def test_provider_failure_redacts_errors_and_differs_from_no_records(self):
        def fail(*args,**kwargs): raise RuntimeError('secret-token')
        r = self.module.CharacterQuerySource(graphql=fail,fetch=fail).query(self.parse('/角色查询 Giannis 白银之手'))
        self.assertIn('unavailable',str(r))
        self.assertNotIn('secret-token',str(r))

    def test_missing_percentile_and_bad_run_scope_are_not_valid_scores(self):
        self.runs[0]['rankPercent']=None
        self.runs[1]['bracketData']=True
        r = self.source().query(self.parse('/角色大米查询 Giannis 白银之手 副本=诸王之眠'))
        self.assertEqual(r['sections'][0]['rows'],[])
        self.assertEqual(r['sections'][0]['status'],'partial')

    def test_missing_supported_difficulty_returns_explicit_result(self):
        r = self.source().query(self.parse('/角色团本查询 Giannis 白银之手 难度=随机团队'))
        self.assertTrue(r['sections'])
        self.assertIn('难度',str(r['sections']))

    def test_multiple_current_raids_still_return_default_summary(self):
        other=copy.deepcopy(self.catalog['worldData']['zones'][0])
        other.update(id=56,name='Another Live Raid')
        self.catalog['worldData']['zones'].append(other)
        r=self.source().query(self.parse('/角色查询 Giannis 白银之手'))
        self.assertFalse(any(s.get('status')=='selection' for s in r['sections']))

    def test_raid_score_has_record_time_and_healer_uses_hps(self):
        self.raid_runs=[{'rankPercent':90.1,'spec':'Restoration','amount':400,'startTime':1791893839574,
                         'report':{'code':'mZBg8DbyNdTrXcFL','fightID':5}}]
        r=self.source().query(self.parse('/角色团本查询 Giannis 白银之手 Boss=内克扎莉 难度=英雄'))
        rows=[row for s in r['sections'] for row in s['rows']]
        self.assertEqual(rows[0]['metric'],'HPS')
        self.assertEqual(rows[0]['recordedAt'],1791893839574)


if __name__ == '__main__': unittest.main()

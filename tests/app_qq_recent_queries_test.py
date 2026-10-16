"""Recent fights, compact Markdown and official transport regression contracts."""
import copy
import json
import re
import unittest
import httpx
from tests.app_qq_character_source_test import CharacterSourceTest, CATALOG


class RecentQueriesTest(unittest.TestCase):
    setUp = CharacterSourceTest.setUp
    fetch = CharacterSourceTest.fetch
    source = CharacterSourceTest.source
    def graphql(self, query, variables=None, **kwargs):
        if 'encounterRankings' not in query:
            return CharacterSourceTest.graphql(self, query, variables, **kwargs)
        self.requests.append((query,variables))
        fields = re.findall(r'(q\d+):encounterRankings\(([^)]+)\)',query)
        result={'id':72040639}
        for alias,args in fields:
            eid=int(re.search(r'encounterID:(\d+)',args)[1])
            diff=int(re.search(r'difficulty:(\d+)',args)[1])
            metric=re.search(r'metric:(\w+)',args)[1]
            zone=next(z for z in self.catalog['worldData']['zones'] if any(e['id']==eid for e in z['encounters']))
            rows=copy.deepcopy(self.runs if diff==10 else getattr(self,'raid_runs',[]))
            rows=[x for x in rows if x.get('_encounter',eid)==eid and x.get('_difficulty',diff)==diff]
            if metric=='hps': rows=[]
            result[alias]={'zone':zone['id'],'partition':int(re.search(r'partition:(-?\d+)',args)[1]),
                           'difficulty':diff,'metric':metric,'totalKills':len(rows),'ranks':rows}
        return {'characterData':{'character':result}}

    def test_recent_is_sorted_by_time_not_percentile_and_same_boss_can_repeat(self):
        self.raid_runs=[{'rankPercent':99-i,'amount':1000,'spec':'Elemental','startTime':1791890000000+i*1000,
                        'report':{'code':'mZBg8DbyNdTrXcFL','fightID':i+1},'_encounter':3470,'_difficulty':4}
                       for i in range(8)]
        self.runs=copy.deepcopy(self.raid_runs)
        for r in self.runs: r.update(bracketData=12,medal='gold',_encounter=61762,_difficulty=10)
        result=self.source().query(self.parse('/角色查询 Giannis 白银之手'))
        self.assertEqual([s['title'] for s in result['sections']],['团本','大秘境'])
        for section in result['sections']:
            self.assertEqual(len(section['rows']),3)
            self.assertEqual([r['percentile'] for r in section['rows']],[92,93,94])
            self.assertEqual(len({r['reportUrl'] for r in section['rows']}),3)

    def test_dedup_and_filter_before_taking_three(self):
        self.runs=[dict(self.runs[0],startTime=1791890000000+i*1000,
                        report={'code':'mZBg8DbyNdTrXcFL','fightID':i+1},bracketData=12 if i<6 else 15)
                   for i in range(9)]
        self.runs.append(copy.deepcopy(self.runs[5]))
        result=self.source().query(self.parse('/角色大米查询 Giannis 白银之手 层数=12'))
        rows=result['sections'][0]['rows']
        self.assertEqual(len(rows),3)
        self.assertEqual([r['recordedAt'] for r in rows],[1791890000000+i*1000 for i in (5,4,3)])

    def test_each_category_limits_three_and_numbers_are_literal_not_auto_lists(self):
        from server.app.channels.qq_official.query_commands import format_result
        rows=[{'name':f'Boss{i}','spec':'元素','metric':'DPS','percentile':80,
               'recordedAt':1791890000000-i*1000} for i in range(5)]
        text=format_result({'identity':'玩家｜服','sections':[
            {'title':'团本','status':'ok','rows':rows},
            {'title':'大秘境','status':'ok','rows':rows}]})
        self.assertEqual(text.count('最近 3 场'),2)
        self.assertEqual(text.count('**1. Boss0**'),2)
        self.assertEqual(text.count('**3. Boss2**'),2)
        self.assertNotIn('Boss3',text)
        self.assertIsNone(re.search(r'(?m)^\d+\. ',text))

    def test_bad_timestamps_cannot_claim_recency(self):
        self.runs[0]['startTime']=None
        result=self.source().query(self.parse('/角色大米查询 Giannis 白银之手'))
        self.assertEqual(result['sections'][0]['status'],'partial')
        self.assertEqual(len(result['sections'][0]['rows']),1)

    def test_markdown_headings_compact_empty_sections_and_escape_source_names(self):
        from server.app.channels.qq_official.query_commands import format_result
        text=format_result({'identity':'Player_[fake](x)｜服','queriedAt':'2026-10-15T00:00:00Z',
            'sections':[{'title':'团本','status':'no_records','rows':[]},
                        {'title':'大秘境','status':'ok','rows':[{'name':'副本','level':12,'spec':'元素',
                           'metric':'DPS','percentile':75.2,'recordedAt':1791890000000,
                           'reportUrl':'https://www.warcraftlogs.com/reports/mZBg8DbyNdTrXcFL?fight=5'}]}]})
        self.assertIn('## 团本',text)
        self.assertIn('## 大秘境',text)
        self.assertIn('紫分',text)
        self.assertIn('[日志]',text)
        self.assertNotIn('最高',text)
        self.assertNotIn('Player_[fake](x)',text)
        self.assertEqual(text.count('暂无公开记录'),1)

    def test_markdown_transport_uses_type_two_and_preserves_reply_sequence(self):
        from server.app.channels.qq_official.client import OfficialClient
        sent=[]
        def handler(request):
            if request.url.path.endswith('getAppAccessToken'):
                return httpx.Response(200,json={'access_token':'token','expires_in':7200})
            sent.append(json.loads(request.content))
            return httpx.Response(200,json={'id':'receipt'})
        client=OfficialClient('102828220','test-secret',markdown=True,
                             http=httpx.Client(transport=httpx.MockTransport(handler)))
        client.send_group('group_A','msg_A','## 团本\n**Boss**',2)
        self.assertEqual(sent,[{'msg_type':2,'markdown':{'content':'## 团本\n**Boss**'},'msg_id':'msg_A','msg_seq':2}])

    def test_markdown_chunks_preserve_whole_links_and_are_bounded(self):
        from server.app.channels.qq_official.query_commands import markdown_parts
        line='- **副本** '+('[日志](https://www.warcraftlogs.com/reports/mZBg8DbyNdTrXcFL?fight=5)')
        text='## 大秘境\n'+'\n'.join([line]*35)
        chunks=markdown_parts(text)
        self.assertTrue(all(len(x)<=1500 for x in chunks))
        self.assertEqual('\n'.join(chunks),text)
        self.assertTrue(all(x.count('[日志](')==x.count('?fight=5)') for x in chunks))


if __name__=='__main__': unittest.main()

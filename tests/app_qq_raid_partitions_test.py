"""A new default patch must not hide older raid scores visible under WCL All."""
import copy
import re
import unittest
from tests import app_qq_character_source_test as fixtures


class RaidPartitionsTest(unittest.TestCase):
    setUp=fixtures.CharacterSourceTest.setUp
    fetch=fixtures.CharacterSourceTest.fetch
    source=fixtures.CharacterSourceTest.source

    def graphql(self,query,variables=None,**kwargs):
        if 'encounterRankings' not in query:
            return fixtures.CharacterSourceTest.graphql(self,query,variables,**kwargs)
        self.requests.append((query,variables))
        result={'id':72040639}
        for alias,args in re.findall(r'(q\d+):encounterRankings\(([^)]+)\)',query):
            eid=int(re.search(r'encounterID:(\d+)',args)[1])
            diff=int(re.search(r'difficulty:(\d+)',args)[1])
            part=int(re.search(r'partition:(-?\d+)',args)[1])
            metric=re.search(r'metric:(\w+)',args)[1]
            raid=diff!=10
            # Real failure shape: patch 12.1.5 is empty, All includes 12.1.
            ranks=copy.deepcopy(self.raid_runs if raid and part in (-1,1) and eid==3470 and diff==4 and metric=='dps'
                                else self.runs if not raid and metric=='dps' else [])
            result[alias]={'zone':53 if raid else 55,'partition':2 if getattr(self,'wrong_partition',False) and raid else part,
                           'difficulty':diff,'metric':metric,'totalKills':len(ranks),'ranks':ranks}
        return {'characterData':{'character':result}}

    def test_latest_patch_empty_still_returns_older_raid_fights(self):
        self.raid_runs=[dict(self.raid_runs[0],startTime=1791890000000+i*1000,rankPercent=80-i,
                            report={'code':'mZBg8DbyNdTrXcFL','fightID':i+1}) for i in range(7)]
        result=self.source().query(self.parse('/角色团本查询 Giannis 白银之手 Boss=内克扎莉 难度=英雄'))
        section=result['sections'][0]
        self.assertEqual(section['status'],'ok')
        self.assertIn('全部分区',section['scope'])
        self.assertNotIn('12.1.5',section['scope'])
        self.assertEqual([r['percentile'] for r in section['rows']],[74,75,76])
        self.assertTrue(any('partition:-1' in q for q,_ in self.requests if 'encounterRankings' in q))

    def test_wrong_returned_partition_is_failure_not_no_records(self):
        self.wrong_partition=True
        result=self.source().query(self.parse('/角色团本查询 Giannis 白银之手'))
        self.assertEqual(result['sections'][0]['status'],'unavailable')
        self.assertFalse(result['sections'][0]['rows'])

    def test_mplus_stays_in_its_current_season_partition(self):
        result=self.source().query(self.parse('/角色大米查询 Giannis 白银之手'))
        self.assertEqual(result['sections'][0]['status'],'ok')
        calls=[q for q,_ in self.requests if 'encounterRankings' in q]
        self.assertTrue(calls)
        self.assertTrue(all('partition:1' in q and 'partition:-1' not in q for q in calls))


if __name__=='__main__':unittest.main()

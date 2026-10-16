"""Player shorthand must preserve structured filters and avoid ambiguous guessing."""
import unittest
import copy
from tests import app_qq_character_source_test as fixtures
from server.app.channels.qq_official.query_commands import parse_query,QueryInputError
from server.app.channels.qq_official.query_labels import matches


class QueryShorthandTest(unittest.TestCase):
    def test_screenshot_heroic_boss_matches_explicit_filters(self):
        self.assertEqual(parse_query('/角色团本查询 Giannis 白银之手 H乌拉特克'),
                         parse_query('/角色团本查询 Giannis 白银之手 Boss=乌拉特克 难度=英雄'))

    def test_attached_separate_and_chinese_difficulty_with_short_names(self):
        for suffix,difficulty in (('n乌拉',3),('M乌拉',5),('英雄乌拉',4),('史诗乌拉',5),
                                  ('H 乌拉',4),('乌拉 H',4),('Boss=乌拉 H',4)):
            with self.subTest(suffix=suffix):
                q=parse_query('/角色团本查询 Giannis 白银之手 '+suffix)
                self.assertEqual((q.boss,q.difficulty),('乌拉',difficulty))
        q=parse_query('/角色团本查询 Giannis 白银之手 Nightbane')
        self.assertEqual((q.boss,q.difficulty),('Nightbane',None))

    def test_mplus_short_dungeon_and_key_level(self):
        for suffix in ('诸王+12','诸王 +12','诸王 层数=12'):
            with self.subTest(suffix=suffix):
                self.assertEqual(parse_query('/角色大米查询 Giannis 白银之手 '+suffix),
                                 parse_query('/角色大米查询 Giannis 白银之手 副本=诸王 层数=12'))

    def test_conflicting_duplicate_invalid_and_wrong_command_options_reject(self):
        for command in ('/角色团本查询 Giannis 白银之手 H乌拉 难度=史诗',
                        '/角色团本查询 Giannis 白银之手 H乌拉 Boss=内克扎莉',
                        '/角色团本查询 Giannis 白银之手 H M 乌拉',
                        '/角色大米查询 Giannis 白银之手 诸王+12 层数=13',
                        '/角色大米查询 Giannis 白银之手 诸王+1',
                        '/角色大米查询 Giannis 白银之手 诸王+100',
                        '/角色查询 Giannis 白银之手 H乌拉'):
            with self.subTest(command=command),self.assertRaises(QueryInputError):parse_query(command)

    def test_aliases_are_resolved_against_catalog_without_picking_ambiguous_match(self):
        bosses=[{'id':3492,'name':"Ula'tek"},{'id':3470,'name':"Nek'zali the Soulcoiler"},
                {'id':3379,'name':'Nymrissa Wavecaller'},{'id':3513,'name':"Kith'ix"}]
        self.assertEqual([r['id'] for r in matches('乌拉',bosses)],[3492])
        self.assertEqual([r['id'] for r in matches('内克扎莉',bosses)],[3470])
        self.assertEqual([r['id'] for r in matches('唤潮者',bosses)],[3379])
        self.assertEqual([r['id'] for r in matches('基希克斯',bosses)],[3513])
        self.assertEqual(len(matches('乌拉',bosses+[{'id':1,'name':'乌拉特克的回响'}])),2)

    def test_regions_and_required_identity_are_not_difficulty_tokens(self):
        q=parse_query('/角色团本查询 H乌拉 白银之手 H乌拉 美服')
        self.assertEqual((q.name,q.realm,q.region,q.boss,q.difficulty),('H乌拉','白银之手','us','乌拉',4))

    def test_numeric_boss_positions_and_explicit_ids_are_distinct(self):
        for suffix,index,difficulty in (('H8',8,4),('H9',9,4),('H10',10,4),('n8',8,3),
                                        ('m9',9,5),('H 10',10,4),('英雄8',8,4)):
            with self.subTest(suffix=suffix):
                q=parse_query('/角色团本查询 Giannis 白银之手 '+suffix)
                self.assertEqual((q.boss_index,q.boss,q.difficulty),(index,'',difficulty))
        q=parse_query('/角色团本查询 Giannis 白银之手 Boss=3492 H')
        self.assertEqual((q.boss,q.boss_index),('3492',None))
        for suffix in ('H0','H100','H8 Boss=乌拉特克','Boss=乌拉特克 H8'):
            with self.subTest(suffix=suffix),self.assertRaises(QueryInputError):
                parse_query('/角色团本查询 Giannis 白银之手 '+suffix)


class OrdinalSourceTest(unittest.TestCase):
    setUp=fixtures.CharacterSourceTest.setUp
    fetch=fixtures.CharacterSourceTest.fetch
    source=fixtures.CharacterSourceTest.source
    graphql=fixtures.CharacterSourceTest.graphql

    def test_catalog_order_and_out_of_range(self):
        result=self.source().query(self.parse('/角色团本查询 Giannis 白银之手 H2'))
        self.assertIn('2号 陵寝哨兵',result['sections'][0]['scope'])
        calls=[q for q,_ in self.requests if 'encounterRankings' in q]
        self.assertTrue(calls)
        self.assertTrue(all('encounterID:3445,' in q and 'encounterID:3470,' not in q for q in calls))
        self.requests=[]
        result=self.source().query(self.parse('/角色团本查询 Giannis 白银之手 H3'))
        self.assertEqual(result['sections'][0]['status'],'selection')
        self.assertIn('序号',result['sections'][0]['message'])
        self.assertFalse(any('encounterRankings' in q for q,_ in self.requests))

    def test_multiple_current_raids_need_explicit_selection_for_positions(self):
        other=copy.deepcopy(self.catalog['worldData']['zones'][0]);other.update(id=56,name='Other Current Raid')
        self.catalog['worldData']['zones'].append(other)
        result=self.source().query(self.parse('/角色团本查询 Giannis 白银之手 H1'))
        self.assertEqual(result['sections'][0]['status'],'selection')
        self.assertFalse(any('encounterRankings' in q for q,_ in self.requests))
        result=self.source().query(self.parse('/角色团本查询 Giannis 白银之手 团本=烈毒之渊 H1'))
        self.assertEqual(result['sections'][0]['status'],'ok')


if __name__=='__main__':unittest.main()

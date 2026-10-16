"""User-visible command, filtering and score contracts; executed on cloud."""
import importlib
import unittest


class CharacterCommandsTest(unittest.TestCase):
    def setUp(self):
        try:
            self.module = importlib.import_module('server.app.channels.qq_official.query_commands')
        except ImportError:
            self.fail('official QQ fixed character-query commands are not implemented')

    def test_required_identity_default_region_and_named_filters(self):
        q = self.module.parse_query('/角色查询 Giannis 白银之手')
        self.assertEqual((q.kind, q.name, q.realm, q.region), ('character', 'Giannis', '白银之手', 'cn'))
        q = self.module.parse_query('/角色团本查询 玩家 "Silver Hand" 地域=美服 Boss="Boss One" 难度=英雄')
        self.assertEqual((q.kind, q.region, q.boss, q.difficulty), ('raid', 'us', 'Boss One', 4))
        q = self.module.parse_query('/角色大米查询 玩家 服务器 副本=诸王之眠 层数=12')
        self.assertEqual((q.kind, q.dungeon, q.level), ('mplus', '诸王之眠', 12))

    def test_invalid_and_missing_input_rejects_before_source_lookup(self):
        for text in ('/角色查询', '/角色查询 玩家', '/角色查询 玩家 服 地域=未知',
                     '/角色查询 玩家 服 Boss=首领', '/角色团本查询 玩家 服 副本=副本',
                     '/角色大米查询 玩家 服 层数=-1', '/角色大米查询 玩家 服 层数=12 层数=13',
                     '/角色团本查询 玩家 服 难度=错误', '/角色查询 玩家 https://evil.invalid',
                     '/角色查询 玩家 服 不认识', '/角色查询 "玩家 服', '/游戏 poe2', '帮我跑分'):
            with self.subTest(text=text), self.assertRaises(self.module.QueryInputError):
                self.module.parse_query(text)

    def test_raw_decimal_colors_and_missing_are_not_zero(self):
        for score, color in ((0,'灰分'),(24.999,'灰分'),(25,'绿分'),(49.999,'绿分'),
                             (50,'蓝分'),(74.999,'蓝分'),(75,'紫分'),(94.999,'紫分'),
                             (95,'橙分'),(98.999,'橙分'),(99,'粉分'),(99.999,'粉分'),(100,'金分')):
            with self.subTest(score=score):
                self.assertIn(color, self.module.score_text(score))
        for value in (None, True, -1, 101, float('nan'), float('inf'), '75'):
            self.assertEqual(self.module.score_text(value), '暂无数据')
        for raw,expected in ((80.3157504015893,'80（紫分）'),(92.33264621485529,'92（紫分）'),
                             (74.04892020531919,'74（蓝分）'),(67.07189895344828,'67（蓝分）'),
                             (84.83121009116554,'85（紫分）'),(2.5,'3（灰分）'),
                             (24.5,'25（灰分）'),(74.9999,'75（蓝分）'),(99.5,'100（粉分）')):
            with self.subTest(raw=raw):
                self.assertEqual(self.module.score_text(raw),expected)

    def test_formatter_preserves_scope_time_identity_and_no_evaluation(self):
        packet = {'identity': 'Giannis｜白银之手｜国服', 'queriedAt': '2026-10-14T08:00:00Z',
                  'profile': {'race':'黑铁矮人','class':'萨满祭司','spec':'元素','hero':'先知',
                              'itemLevel':327, 'sourceTime':'2026-10-13T14:51:57Z', 'source':'Raider.IO'},
                  'sections':[{'title':'当前大米', 'scope':'Season 2｜同层 DPS 表现百分位｜历史',
                               'status':'ok', 'rows':[{'name':'诸王之眠','spec':'元素','percentile':74.999,
                                'level':12,'timed':True,'recordedAt':'2026-10-13T06:00:00Z'}]}],
                  'sources':['https://www.warcraftlogs.com/character/cn/silver-hand/Giannis']}
        text = self.module.format_result(packet)
        for word in ('Giannis','白银之手','327','先知','Raider.IO','2026-10-13','同层 DPS',
                     '诸王之眠','12','限时','蓝分','warcraftlogs.com'):
            self.assertIn(word, text)
        for word in ('优秀','建议','提升','操作差','你应该'):
            self.assertNotIn(word, text)

    def test_no_record_and_provider_failure_are_distinct(self):
        text = self.module.format_result({'identity':'玩家｜服｜国服','queriedAt':'now',
            'profile':{},
            'sections':[{'title':'团本','scope':'英雄','status':'no_records','rows':[]},
                        {'title':'大米','scope':'赛季','status':'unavailable','rows':[]}]})
        self.assertIn('暂无公开记录', text)
        self.assertIn('查询失败', text)
        self.assertIn('种族：暂无数据',text)
        self.assertNotIn('0（灰分）', text)

    def test_scope_guard_rejects_other_groups_and_multiple_groups(self):
        from server.app.channels.qq_official.policy import require_test_group
        require_test_group({'testGroupNumber':'1127827451','allowedGroupOpenIds':['group_A']})
        for raw in ({'testGroupNumber':'other','allowedGroupOpenIds':['group_A']},
                    {'testGroupNumber':'1127827451','allowedGroupOpenIds':['group_A','group_B']}):
            with self.assertRaises(ValueError): require_test_group(raw)

    def test_only_readonly_source_credentials_are_selected(self):
        from server.app.channels.qq_official.deployment import character_query_credentials
        env=character_query_credentials({'WOW_WARCRAFTLOGS_CLIENT_ID':'id',
            'WOW_WARCRAFTLOGS_CLIENT_SECRET':'secret','WOW_QQ_APP_KEY':'web-secret',
            'WOW_RAIDERIO_API_KEY':'not-required','OTHER_API_KEY':'other'})
        self.assertEqual(set(env),{'WOW_WARCRAFTLOGS_CLIENT_ID','WOW_WARCRAFTLOGS_CLIENT_SECRET'})


if __name__ == '__main__':
    unittest.main()

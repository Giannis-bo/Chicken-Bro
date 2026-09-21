import unittest
from server.app.poe2.tree_translation import translate_tree, translate_stats


class TranslationTests(unittest.TestCase):
    def test_effective_attribute_and_numbers_are_preserved(self):
        self.assertEqual(translate_stats(['+5 to Intelligence']), ['+5 智慧'])
        self.assertEqual(translate_stats(['15% increased chance to Shock']), ['感电几率提高 15%'])
        self.assertEqual(translate_stats(['999% increased chance to Shock']), ['999% increased chance to Shock'])

    def test_multiline_effect_is_translated_as_a_whole(self):
        lines = ['Arrows gain Critical Hit Chance as they travel farther, up to',
                 '40% increased Critical Hit Chance after 7 metres']
        result = translate_stats(lines)
        self.assertEqual(len(result), 1)
        self.assertIn('40%', result[0])
        self.assertIn('7', result[0])
        self.assertNotIn('Arrows', result[0])

    def test_reordered_source_effects_are_not_paired_by_position(self):
        self.assertEqual(translate_stats(['32% increased Spell Damage while wielding a Melee Weapon', '+10 to Dexterity']),
                         ['装备近战武器时法术伤害提高 32%', '+10 敏捷'])
        self.assertEqual(translate_stats(['Archon recovery period expires 10% faster']), ['执政官间隔期的消减速度加快 10%'])
        self.assertEqual(translate_stats(['Warcries Debilitate Enemies']), ['战吼使敌人疲惫'])

    def test_translation_does_not_mutate_engine_data_or_allocations(self):
        node = {'id': 1, 'name': 'Gemling Legionnaire', 'stats': ['+5 to Intelligence'],
                'allocated': True, 'allocation': 2, 'x': 42, 'y': 13}
        tree = {'nodes': [node], 'edges': []}
        translated = translate_tree(tree)['nodes'][0]
        self.assertEqual(node['name'], 'Gemling Legionnaire')
        self.assertEqual(translated['name'], '古灵使徒斗士')
        for key in ('id', 'allocated', 'allocation', 'x', 'y'):
            self.assertEqual(translated[key], node[key])
        self.assertEqual(translated['originalStats'], node['stats'])


if __name__ == '__main__': unittest.main()

"""Finite mapping contract; fixtures here are synthetic, never player exports."""
import copy
import json
import unittest
from server.app.poe2.imports.mapping import load_dictionary, map_snapshot


def synthetic_snapshot():
    return {
        'schema_version': 1,
        'role': {'name': 'Synthetic fixture', 'level': 80, 'class_name': 'Huntress', 'league_id': 'Synthetic'},
        'equipment': [{'baseType': '阿科扬战矛', 'typeLine': '阿科扬战矛', 'name': '',
                       'inventoryId': 'Weapon', 'frameType': 2, 'ilvl': 80, 'identified': True,
                       'properties': [], 'requirements': [], 'implicitMods': [],
                       'explicitMods': [{'description': '+101 生命上限', 'fractured': True}]}],
        'skills': {'base_info': [{'id': 'ActiveSkills.explosive_spear', 'name': '爆破战矛'}],
                   'items': [{'typeLine': '爆破战矛', 'support': False,
                              'properties': [{'name': '等级', 'values': [['20', 0]]}],
                              'socketedItems': [{'typeLine': '处决 II', 'support': True, 'properties': []}]}]},
        'passives': {'hashes': [], 'specialisations': {'set1': [], 'set2': []}, 'skill_overrides': {},
                     'jewel_slots': {}, 'quest_stats': [],
                     'quest_provenance': {'complete': True, 'choices': [], 'resistance_penalty': 0}},
        'jewels': {'status': 'present', 'items': []},
        'source': {'provider': 'wegame', 'game_data_version': '0_5', 'schema_gaps': []},
    }


class MappingTest(unittest.TestCase):
    def setUp(self):
        self.dictionary = load_dictionary()
        self.snapshot = synthetic_snapshot()

    def mapped(self):
        return map_snapshot(self.snapshot, self.dictionary)

    def test_complete_synthetic(self):
        result = self.mapped()
        self.assertEqual(result.issues, ())
        self.assertIsNotNone(result.character)
        self.assertEqual(result.character['equipment'][0]['explicitMods'][0],
                         {'description': '+101 to maximum Life', 'fractured': True})
        self.assertEqual(result.coverage['modifiers'], {'total': 1, 'mapped': 1, 'unmapped': 0})

    def test_unmapped_modifier_blocks_conversion(self):
        self.snapshot['equipment'][0]['explicitMods'].append({'description': '未登记测试词缀'})
        result = self.mapped()
        self.assertTrue(any(i.code == 'MOD_UNMAPPED' for i in result.issues))
        self.assertIsNone(result.character)

    def test_markers_preserve_resistance_element(self):
        self.snapshot['equipment'][0]['explicitMods'] = [
            {'description': '[Resistances|火焰抗性] +39%'},
            {'description': '[Resistances|冰霜抗性] +28%'},
            {'description': '[Resistances|闪电抗性] +17%'}]
        result = self.mapped()
        self.assertEqual([m['description'] for m in result.character['equipment'][0]['explicitMods']],
                         ['+39% to Fire Resistance', '+28% to Cold Resistance', '+17% to Lightning Resistance'])

    def test_support_tiers_remain_distinct(self):
        self.snapshot['skills']['items'][0]['socketedItems'].append(
            {'typeLine': '处决 III', 'support': True, 'properties': []})
        result = self.mapped()
        self.assertEqual([g['typeLine'] for g in result.character['skills'][0]['socketedItems']], ['Execute II', 'Execute III'])

    def test_unknown_version_missing_jewels_and_base_info(self):
        self.snapshot['source']['game_data_version'] = 'unknown'
        self.snapshot['jewels'] = {'status': 'missing'}
        self.snapshot['skills']['base_info'] = []
        codes = {i.code for i in self.mapped().issues}
        self.assertTrue({'GAME_VERSION_UNSUPPORTED', 'MISSING_JEWELS', 'MISSING_BASE_INFO'} <= codes)

    def test_unknown_schema_quest_and_flags_block(self):
        self.snapshot['source']['schema_gaps'] = ['unknown_item_fields']
        self.snapshot['passives'].pop('quest_provenance')
        self.snapshot['equipment'][0]['explicitMods'][0]['flags'] = 123
        codes = {i.code for i in self.mapped().issues}
        self.assertTrue({'SOURCE_SCHEMA_GAP', 'QUEST_PROVENANCE_MISSING', 'MOD_FLAGS_UNSUPPORTED'} <= codes)

    def test_unknown_nodes_counted(self):
        self.snapshot['passives']['hashes'] = [99999999]
        result = self.mapped()
        self.assertEqual(result.coverage['nodes'], {'total': 1, 'mapped': 0, 'unmapped': 1})
        self.assertIsNone(result.character)

    def test_two_weapon_sets_attribute_choice(self):
        node = next(k for k, v in self.dictionary['nodes'].items() if v['attribute'])
        self.snapshot['passives']['specialisations']['set2'] = [int(node)]
        self.snapshot['passives']['skill_overrides'][node] = {
            'id': 'generic_attribute_dexterity', 'name': '敏捷', 'grantedDexterity': 5, 'stats': ['+5 [Dexterity|敏捷]']}
        alternate = copy.deepcopy(self.snapshot['equipment'][0]);alternate['inventoryId'] = 'Weapon2'
        self.snapshot['equipment'].append(alternate)
        result = self.mapped()
        self.assertEqual(result.issues, ())
        self.assertEqual(result.character['passives']['skill_overrides'][node]['name'], 'Dexterity')
        self.assertEqual(result.character['equipment'][1]['inventoryId'], 'Weapon2')

    def test_public_output_excludes_untrusted_fields(self):
        self.snapshot['role']['name'] = {'token': 'PRIVATE_SENTINEL'}
        self.snapshot['role']['league_id'] = 'https://evil.test/PRIVATE_SENTINEL'
        self.snapshot['source']['rawresponse'] = {'secret': 'PRIVATE_SENTINEL'}
        self.snapshot['equipment'][0]['explicitMods'].append({'description': 'https://evil.test/PRIVATE_SENTINEL'})
        self.snapshot['passives']['skill_overrides']['PRIVATE_SENTINEL'] = {'token': 'PRIVATE_SENTINEL'}
        result = self.mapped()
        public = json.dumps({'preview': result.preview, 'issues': [vars(i) for i in result.issues]})
        self.assertNotIn('PRIVATE_SENTINEL', public)
        self.assertNotIn('evil.test', public)

    def test_preview_retains_safe_identity_and_times_only(self):
        self.snapshot['role'].update(name='我得矛盾', league_id='1152921504606849089')
        self.snapshot['source'].update(fetched_at='2026-09-20T12:30:00Z', source_updated_at=None)
        preview = self.mapped().preview
        self.assertEqual(preview['character'], '我得矛盾')
        self.assertEqual(preview['league'], '1152921504606849089')
        self.assertEqual(preview['fetchedAt'], '2026-09-20T12:30:00Z')
        self.assertIsNone(preview['sourceUpdatedAt'])
        self.snapshot['source']['token'] = 'hiddenvalue'
        self.snapshot['role'].update(name='hiddenvalue', league_id='https://evil.test/hiddenvalue')
        self.snapshot['source'].update(fetched_at='2026-99-20T12:30:00Z', source_updated_at={'token': 'hiddenvalue'})
        preview = self.mapped().preview
        self.assertEqual(preview['character'], 'Imported character')
        self.assertNotIn('league', preview)
        self.assertNotIn('fetchedAt', preview)
        self.assertIsNone(preview['sourceUpdatedAt'])
        self.assertNotIn('hiddenvalue', json.dumps(preview))

    def test_nonempty_jewels_and_modifiers_are_all_accounted_unmapped(self):
        self.snapshot['jewels'] = {'status': 'present', 'items': [
            {'jewel': {'name': '珠宝甲', 'mod_descriptions': [
                {'values_formats': [{'des': '+10 生命上限'}]},
                {'values_formats': [{'des': '[Resistances|火焰抗性] +5%'}]}]}},
            {'jewel': {'name': '珠宝乙', 'explicitMods': [{'description': '+20 生命上限'}],
                       'mod_descriptions': [{'values_formats': [{'des': '未知效果'}]}]}},
            {'unsupported': 'private value'}]}
        result = self.mapped()
        self.assertIsNone(result.character)
        self.assertEqual(result.coverage['items'], {'total': 4, 'mapped': 1, 'unmapped': 3})
        self.assertEqual(result.coverage['modifiers'], {'total': 5, 'mapped': 1, 'unmapped': 4})
        for kind in ('items', 'modifiers'):
            self.assertEqual(sum(row['kind'] == kind for row in result.ledger), result.coverage[kind]['total'])
        self.assertTrue(any(i.code == 'JEWEL_STRUCTURE_UNSUPPORTED' for i in result.issues))
        public = json.dumps([vars(i) for i in result.issues])
        self.assertNotIn('private value', public)
        self.assertTrue(all(row['status'] == 'unmapped' for row in result.ledger if row['path'].startswith('jewels.')))


if __name__ == '__main__':
    unittest.main()

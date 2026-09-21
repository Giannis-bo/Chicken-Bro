"""Opt-in CLOUD ONLY native conversion. Synthetic evidence, not national acceptance."""
import json
import os
from pathlib import Path
import unittest
from server.app.poe2.character_bridge import convert_character
from server.app.poe2.engine import PobEngine, decode_build
from server.app.poe2.imports.mapping import load_dictionary, map_snapshot
from tests.app_poe2_mapping_test import synthetic_snapshot


@unittest.skipUnless(os.environ.get('POE2_CHARACTER_LIVE') == '1', 'cloud native opt-in')
class CharacterBridgeLiveTest(unittest.TestCase):
    def test_native_import_export_roundtrip_synthetic(self):
        mapped = map_snapshot(synthetic_snapshot(), load_dictionary())
        self.assertEqual(mapped.issues, ())
        xml = convert_character(mapped.character)
        first = PobEngine().calculate(xml)
        second = PobEngine().calculate(decode_build(first['exportCode']))
        self.assertGreater(first['stats']['Life'], 0)
        self.assertGreater(first['stats']['TotalDPS'], 0)
        self.assertEqual(first['summary']['className'], 'Huntress')
        self.assertEqual(first['summary']['level'], 80)
        self.assertEqual(len(first['items']), 1)
        self.assertEqual([g['name'] for g in first['skills'][0]['gems']], ['Explosive Spear', 'Execute II'])
        self.assertIn('{fractured}', first['items'][0]['text'])
        self.assertEqual(first['effectiveConfig']['resistancePenalty'], 0)
        for key in ('Life', 'Mana', 'TotalDPS', 'FireResist', 'ColdResist', 'LightningResist', 'ChaosResist'):
            self.assertAlmostEqual(first['stats'][key], second['stats'][key])
        evidence = os.environ.get('POE2_CHARACTER_EVIDENCE')
        if evidence:
            p = Path(evidence);p.mkdir(exist_ok=True)
            (p / 'task4-synthetic.xml').write_text(xml)
            (p / 'task4-synthetic-result.json').write_text(json.dumps({'fixture': 'synthetic', 'coverage': mapped.coverage,
                'stats': first['stats'], 'effectiveConfig': first['effectiveConfig'], 'engineVersion': first['engineVersion'],
                'inputSha256': first['inputSha256'], 'outputSha256': first['outputSha256'],
                'roundtripStats': second['stats']}, indent=2))
        print('SYNTHETIC', json.dumps({'stats': first['stats'], 'coverage': mapped.coverage, 'engineVersion': first['engineVersion']}))

    def test_native_weapon_sets_attributes_quests_and_all_finite_modifiers(self):
        import copy
        snapshot = synthetic_snapshot()
        dictionary = load_dictionary()
        snapshot['equipment'][0]['explicitMods'] += [
            {'description': '[Resistances|火焰抗性] +39%', 'crafted': True},
            {'description': '[Resistances|冰霜抗性] +28%', 'mutated': True},
            {'description': '[Resistances|闪电抗性] +17%'},
            {'description': '[Resistances|混沌抗性] +13%'}]
        swap = copy.deepcopy(snapshot['equipment'][0]);swap['inventoryId'] = 'Weapon2'
        snapshot['equipment'].append(swap)
        snapshot['equipment'].append({'baseType': '紫晶戒指', 'typeLine': '紫晶戒指', 'name': '',
            'inventoryId': 'Ring', 'frameType': 0, 'ilvl': 80, 'identified': True,
            'implicitMods': [{'description': '[Resistances|混沌抗性] +13%'}], 'properties': [], 'requirements': []})
        snapshot['passives']['hashes'] = [13828, 1140, 15507, 48401]
        snapshot['passives']['specialisations'] = {'set1': [35987], 'set2': [61312]}
        snapshot['passives']['skill_overrides'] = {str(n): {'id': 'generic_attribute_dexterity',
            'name': '敏捷', 'grantedDexterity': 5, 'stats': ['+5 [Dexterity|敏捷]']} for n in (1140, 15507, 48401, 61312)}
        snapshot['passives']['quest_stats'] = ['冰霜抗性 +10%']
        snapshot['passives']['quest_provenance'] = {'complete': True,
            'choices': ['Act 1/Clearfell/Beira'], 'resistance_penalty': -20}
        mapped = map_snapshot(snapshot, dictionary)
        self.assertEqual(mapped.issues, ())
        xml = convert_character(mapped.character)
        result = PobEngine().calculate(xml)
        again = PobEngine().calculate(result['exportCode'])
        self.assertEqual({i['slot'] for i in result['items']}, {'Weapon 1', 'Weapon 1 Swap', 'Ring 1'})
        self.assertEqual(result['effectiveConfig']['resistancePenalty'], -20)
        self.assertTrue(result['effectiveConfig']['questAct 1ClearfellBeira'])
        self.assertTrue({13828, 1140, 15507, 48401, 35987, 61312} <= set(result['allocatedNodes']))
        for key in ('Life', 'Mana', 'TotalDPS', 'FireResist', 'ColdResist', 'LightningResist', 'ChaosResist'):
            self.assertAlmostEqual(result['stats'][key], again['stats'][key])
        print('SYNTHETIC_EXTENDED', json.dumps({'coverage': mapped.coverage, 'stats': result['stats']}))

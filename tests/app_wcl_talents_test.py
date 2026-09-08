import copy
import json
import unittest
from unittest.mock import patch
from pathlib import Path
from server.app.simulation.wcl_talents import reconstruct_fight_talents

FIXTURES = Path(__file__).parent / 'fixtures/simc'


class WclTalentReconstructionTest(unittest.TestCase):
    def setUp(self):
        self.details = json.loads((FIXTURES / 'giannis_raiderio_details.json').read_text())['characterDetails']['character']
        self.tree = json.loads((FIXTURES / 'giannis_wcl_report.json').read_text())['data']['reportData']['report']['events']['data'][0]['talentTree']
        self.expected = json.loads((FIXTURES / 'giannis_wcl_engine_export.json').read_text())['talents']

    def test_matches_independent_cloud_engine_export_including_apex_and_choices(self):
        code, proof = reconstruct_fight_talents(self.tree, 262, self.details, "elemental")
        self.assertEqual(code, self.expected)
        self.assertEqual(proof['entryCount'], 80)
        self.assertEqual(proof['heroSubTreeId'], 56)
        self.assertEqual(proof['gameBuild'], '12.1.0.69299')

    def test_log_order_and_current_talent_export_are_irrelevant(self):
        self.details.pop('talentLoadout')
        self.tree.reverse()
        self.assertEqual(reconstruct_fight_talents(self.tree, 262, self.details, "elemental")[0], self.expected)

    def test_rejects_incomplete_unknown_duplicate_wrong_class_and_invalid_ranks(self):
        for change in ('missing', 'duplicate', 'unknown', 'node', 'zero', 'bool', 'overrank', 'string', 'other_class'):
            with self.subTest(change=change):
                tree = copy.deepcopy(self.tree)
                if change == 'missing': tree.pop()
                if change == 'duplicate': tree.append(tree[0])
                if change == 'unknown': tree[0]['id'] = 999999999
                if change == 'node': tree[0]['nodeID'] += 1
                if change == 'zero': tree[0]['rank'] = 0
                if change == 'bool': tree[0]['rank'] = True
                if change == 'overrank': tree[0]['rank'] = 999
                if change == 'string': tree[0]['rank'] = '1'
                if change == 'other_class': tree[0] = {'id': 112112, 'nodeID': 90261, 'rank': 1}
                self.assertIsNone(reconstruct_fight_talents(tree, 262, self.details, "elemental"))

    def test_rejects_mixed_hero_trees_and_double_choices_even_with_equal_point_totals(self):
        tree = copy.deepcopy(self.tree)
        next(e for e in tree if e['nodeID'] == 99845)['id'] = 123376
        self.assertIsNone(reconstruct_fight_talents(tree, 262, self.details, "elemental"))

    def test_rejects_wrong_spec_and_unsupported_level(self):
        for spec in (263, True, '262', None):
            self.assertIsNone(reconstruct_fight_talents(self.tree, spec, self.details, "elemental"))
        self.details['level'] = 80
        self.assertIsNone(reconstruct_fight_talents(self.tree, 262, self.details, "elemental"))

    def test_missing_catalog_fails_closed_without_source_request_crash(self):
        with patch('server.app.simulation.wcl_talents._catalog', side_effect=FileNotFoundError):
            self.assertIsNone(reconstruct_fight_talents(self.tree, 262, self.details, "elemental"))

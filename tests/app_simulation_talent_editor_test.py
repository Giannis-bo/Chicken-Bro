import copy
import json
import unittest
from pathlib import Path
from server.app.simulation.wcl_talents import _catalog
from server.app.simulation.talent_editor import TalentEditError, decode_talents, edit_talents, talent_options

FIXTURES = Path(__file__).parent / 'fixtures/simc'
RUNTIME = 'simc:managed:' + _catalog()[0]['revision'] + ':' + 'a' * 64

class TalentEditorTest(unittest.TestCase):
    def setUp(self):
        self.code = json.loads((FIXTURES / 'fusionbolt_raider_talents_12_1.json').read_text())['talents']
        self.recorded = json.loads((FIXTURES / 'fusionbolt_raider_talents_12_1.json').read_text())['entries']
        self.character = {'classKey': 'shaman', 'specKey': 'elemental', 'level': 90}

    def test_decode_matches_independent_recorded_entries(self):
        decoded = decode_talents(self.code, self.character, RUNTIME)
        self.assertEqual({x['id']: x['rank'] for x in decoded}, {x['id']: x['rank'] for x in self.recorded})

    def test_export_with_inactive_hero_allocations_uses_only_selected_tree(self):
        # Addon export carries purchased Stormbringer nodes alongside active
        # Farseer. Engine create_talent_obj disables the inactive subtree.
        code = 'CYQALMl7AwW51MWzGneuHE3tPCAAAAzMbbzMGjZZZZMmhZAAAAgFzstZmZYzwCz2MTDNzCAMbzMzYmtFTbmZGjlZMzYGLWmZWGGzMLAADgZmZGDDD'
        decoded = decode_talents(code, self.character, RUNTIME)
        ranks = {e['id']: e['rank'] for e in decoded}
        self.assertEqual(len(decoded), 80)
        self.assertEqual(ranks[123377], 1)  # Farseer selection
        self.assertEqual(ranks[117485], 1)  # active hero root
        self.assertNotIn(128226, ranks)    # inactive purchased choice
        self.assertNotIn(117464, ranks)    # inactive purchased normal node
        edited = edit_talents({'string': code}, self.character, RUNTIME, {'string': code})
        self.assertEqual(edited['changes'], [])
        self.assertEqual({e['id']: e['rank'] for e in edited['loadout']}, ranks)

    def test_inactive_allocations_preserve_other_classes_and_reject_bad_ranks(self):
        fixtures = json.loads((FIXTURES / 'inactive_hero_exports_12_1.json').read_text())
        for fixture in fixtures:
            with self.subTest(profile=fixture['name']):
                baseline = decode_talents(fixture['baseline'], fixture['character'], RUNTIME)
                decoded = decode_talents(fixture['withInactive'], fixture['character'], RUNTIME)
                self.assertEqual(decoded, baseline)
                self.assertNotIn(fixture['inactiveEntry'], {e['id'] for e in decoded})
                for malformed in ('invalidInactiveRank', 'zeroInactiveRank'):
                    with self.assertRaises(TalentEditError):
                        decode_talents(fixture[malformed], fixture['character'], RUNTIME)

    def test_choice_edit_preserves_every_other_node_and_source(self):
        original = {'string': self.code}
        before = copy.deepcopy(original)
        options = talent_options(self.character, original, RUNTIME, 'Master of the Elements')
        choice = next(x for x in options['nodes'] if any(e['name'] == 'Master of the Elements' for e in x['entries']))
        target = next(e for e in choice['entries'] if e['name'] == 'Molten Wrath')
        edited = edit_talents(original, self.character, RUNTIME,
                              {'nodes': [{'nodeId': choice['nodeId'], 'entryId': target['entryId'], 'rank': 1}]})
        changed = {x['nodeID'] for x in decode_talents(edited['string'], self.character, RUNTIME)}
        self.assertEqual(changed, {x['nodeID'] for x in self.recorded})
        group = lambda rows: {n: sorted((x['id'], x['rank']) for x in rows if x['nodeID'] == n) for n in {x['nodeID'] for x in rows}}
        old = group(self.recorded)
        new = group(decode_talents(edited['string'], self.character, RUNTIME))
        self.assertEqual([k for k in old if old[k] != new[k]], [choice['nodeId']])
        self.assertEqual(new[choice['nodeId']], [(target['entryId'], 1)])
        self.assertEqual(original, before)

    def test_rejects_invalid_rank_foreign_entry_duplicate_and_injection(self):
        changes = [
            {'nodes': [{'nodeId': 99845, 'entryId': 123377, 'rank': True}]},
            {'nodes': [{'nodeId': 99845, 'entryId': 112112, 'rank': 1}]},
            {'nodes': [{'nodeId': 99845, 'entryId': 123377, 'rank': 99}]},
            {'nodes': [{'nodeId': 99845, 'entryId': 123377, 'rank': 1}] * 2},
            {'string': self.code + '\noutput=/tmp/x'},
        ]
        for patch in changes:
            with self.subTest(patch=patch), self.assertRaises(TalentEditError):
                edit_talents({'string': self.code}, self.character, RUNTIME, patch)

    def test_wrong_runtime_spec_and_truncated_export_fail_closed(self):
        for code, char, runtime in [(self.code, self.character, 'simc:unknown'),
                                   (self.code, {**self.character, 'specKey': 'enhancement'}, RUNTIME),
                                   (self.code[:20], self.character, RUNTIME)]:
            with self.assertRaises(TalentEditError):
                decode_talents(code, char, runtime)

    def test_current_official_profiles_and_cross_node_move(self):
        profiles = json.loads((FIXTURES / 'engine_talent_exports_12_1.json').read_text())
        self.assertGreaterEqual(len(profiles), 39)
        for fixture in profiles:
            with self.subTest(profile=fixture['name']):
                result = edit_talents({'string': fixture['talents']}, fixture['character'], RUNTIME,
                                      {'string': fixture['talents']})
                self.assertEqual(result['changes'], [])
        moved = edit_talents({'string': self.code}, self.character, RUNTIME, {'nodes': [
            {'nodeId': 103579, 'entryId': 127851, 'rank': 0},
            {'nodeId': 103622, 'entryId': 127902, 'rank': 1},
        ]})
        self.assertEqual({r['nodeId'] for r in moved['changes']}, {103579, 103622})
        self.assertEqual(moved['validation'], 'versioned_tree_rules')

    def test_tiered_node_uses_total_rank_with_engine_entry_order(self):
        result = edit_talents({'string': self.code}, self.character, RUNTIME,
                             {'nodes': [{'nodeId': 110402, 'entryId': 136974, 'rank': 4}]})
        self.assertEqual(result['changes'], [])
        self.assertEqual([(e['id'], e['rank']) for e in result['loadout'] if e['nodeID'] == 110402],
                         [(136974, 1), (136973, 2), (136972, 1)])

    def test_broken_parent_is_rejected_even_with_balanced_points(self):
        # Remove a selected prerequisite with selected descendants; spend its
        # point in an otherwise accessible utility node.
        with self.assertRaises(TalentEditError):
            edit_talents({'string': self.code}, self.character, RUNTIME, {'nodes': [
                {'nodeId': 103598, 'entryId': 127873, 'rank': 0},
                {'nodeId': 103622, 'entryId': 127902, 'rank': 1},
            ]})

    def test_item_variant_inherits_only_verified_upgrade_bonus(self):
        from server.app.simulation.item_variants import same_upgrade_variants
        gear = {'trinket2': {'itemId': 270167, 'itemLevel': 308, 'bonusIds': [6652, 13333, 12838]}}
        before = copy.deepcopy(gear)
        rows = same_upgrade_variants(270164, gear, RUNTIME)
        self.assertEqual(rows[0]['equipment'], {'itemId': 270164, 'itemLevel': 308,
                         'bonusIds': [12838], 'gems': [], 'enchant': None})
        self.assertEqual(rows[0]['replacesItemId'], 270167)
        self.assertEqual(gear, before)
        self.assertEqual(same_upgrade_variants(270164, gear, 'simc:unknown'), [])
        gear['trinket2']['itemLevel'] = 321
        self.assertEqual(same_upgrade_variants(270164, gear, RUNTIME), [])

class TalentCompilerTest(unittest.TestCase):
    def test_v5_compiles_override_binds_proof_and_keeps_legacy_hashes(self):
        from dataclasses import replace
        from tests.app_simulation_compiler_test import SimulationCompilerTest
        from server.app.simulation.compiler import SimcProfileCompiler, SimcCompileError
        f = SimulationCompilerTest(); f.setUp()
        raw = copy.deepcopy(f.snapshot.snapshot)
        raw['character']['level'] = 90
        raw['talents'] = {'string': json.loads((FIXTURES / 'fusionbolt_raider_talents_12_1.json').read_text())['talents']}
        snapshot = replace(f.snapshot, snapshot=raw)
        caps = replace(f.capabilities, compiler_revision='chickenbro-simc-compiler-v5', runtime_revision=RUNTIME)
        options = talent_options(raw['character'], raw['talents'], RUNTIME, 'Master of the Elements')
        node = options['nodes'][0]
        target = next(e for e in node['entries'] if e['name']=='Molten Wrath')
        patch = {'talentOverrides':{'nodes':[{'nodeId':node['nodeId'],'entryId':target['entryId'],'rank':1}]}}
        result = SimcProfileCompiler(capabilities=caps).compile(snapshot, patch)
        self.assertIn('talentOverrides', result.provenance)
        self.assertNotIn('talents='+raw['talents']['string']+'\n', result.profile)
        self.assertEqual(raw['talents'], snapshot.snapshot['talents'])
        with self.assertRaises(SimcCompileError):
            SimcProfileCompiler(capabilities=replace(caps, compiler_revision='chickenbro-simc-compiler-v4')).compile(snapshot,patch)

import copy
import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from server.app.simulation.localization import LocalizationCatalog, localize_report
from server.app.simulation.report_identity import extract_report_identity, npc_sources_from_html, validate_report_identity


def sample_report():
    return {'engine': {'gameVersion': '12.1.0.69299'},
            'abilities': [{'name': 'fire_blast', 'amount': 100}],
            'buffs': [{'name': 'bloodlust', 'uptime': 50}]}


def sample_raw():
    return {'sim': {'players': [{'stats': [{'name': 'fire_blast', 'id': 2136,
        'spell_name': 'Fire Blast', 'type': 'damage', 'compound_amount': 100,
        'children': [{'name': 'extra', 'id': 57984, 'type': 'damage', 'compound_amount': 25}]}],
        'buffs': [{'name': 'bloodlust', 'spell': 2825, 'uptime': 50}]}]}}


def sample_catalog():
    return LocalizationCatalog({'schemaVersion': 1, 'build': '12.1.0.69299', 'locale': 'zhCN',
        'spells': {'2136': '火焰冲击', '57984': '火焰冲击', '2825': '嗜血'},
        'creatures': {'61029': '原始火元素'}, 'items': {'123': '测试饰品'},
        'spellAliases': {'fire_blast': '火焰冲击', 'bloodlust': '嗜血'},
        'creatureAliases': {'primal_fire_elemental': '原始火元素'}}, 'a' * 64)


class SimulationLocalizationTest(unittest.TestCase):
    def test_coverage_rejects_changed_html_and_mismatched_runtime_identity(self):
        import contextlib
        import io
        from scripts.verify_simc_localization_matrix import analyze
        from tests.app_simulation_report_test import report_fixture
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); raw = json.dumps(report_fixture()).encode()
            html = b'<a href="https://www.wowhead.com/npc=61029">pet</a>'
            (root/'report.json').write_bytes(raw); (root/'report.html').write_bytes(html)
            runtime = 'simc:managed:' + 'a' * 40 + ':' + 'b' * 64
            row = {'returnCode': 0, 'report': 'report.json', 'profile': 'simc-' + 'a' * 40 + '/profiles/MID1/test.simc',
                   'reportSha256': hashlib.sha256(raw).hexdigest(), 'runtimeRevision': runtime,
                   'html': 'report.html', 'htmlStatus': 'present', 'htmlSha256': hashlib.sha256(html).hexdigest()}
            collection = {'engineSourceCommit': 'a' * 40, 'binarySha256': 'b' * 64, 'archiveSha256': 'c' * 64,
                          'runtimeRevision': runtime, 'records': [row]}
            for case in ('valid', 'html', 'runtime', 'archive'):
                changed = copy.deepcopy(collection)
                (root/'report.html').write_bytes(html + (b'changed' if case == 'html' else b''))
                if case == 'runtime': changed['records'][0]['runtimeRevision'] = 'other'
                if case == 'archive': changed['records'][0]['profile'] = 'simc-' + 'd' * 40 + '/profiles/MID1/test.simc'
                (root/'collection.json').write_text(json.dumps(changed))
                with contextlib.redirect_stdout(io.StringIO()): result = analyze(root)
                self.assertEqual('analysisError' in result['records'][0], case != 'valid', case)

    def test_healing_and_absorption_identities_follow_the_healing_metric(self):
        report = sample_report(); report['metric'] = {'name': 'hps'}
        raw = sample_raw(); raw['sim']['players'][0]['stats'][0]['type'] = 'absorb'
        identity = extract_report_identity(raw, report)
        self.assertEqual(identity['abilities'][0]['spellId'], 2136)
        self.assertTrue(validate_report_identity(identity, report))

    def test_version_bound_rules_never_mistake_auto_attack_markers_for_game_spells(self):
        from server.app.simulation.localization import catalog_for_build
        catalog = catalog_for_build('12.1.0.69299')
        runtime = 'simc:managed:f50a2121bf894570146507496f3e113bff68e445:' + 'b' * 64
        report = sample_report(); report['abilities'][0]['name'] = 'main_hand'
        raw = sample_raw(); raw['sim']['players'][0]['stats'][0].update(name='main_hand', id=1)
        identity = extract_report_identity(raw, report)
        label = localize_report(report, identity, catalog, engine_revision=runtime)['abilities'][0]
        self.assertEqual(label['text'], '主手自动攻击')
        self.assertEqual(label['method'], 'engine_rule')
        self.assertIsNone(label['spellId'])
        self.assertEqual(identity['abilities'][0]['spellId'], 1)
        self.assertEqual(localize_report(report, identity, catalog)['abilities'][0]['status'], 'unresolved')

    def test_known_legacy_report_keeps_verified_names_without_inventing_ids(self):
        from server.app.simulation.localization import catalog_for_build
        report = json.loads(Path('tests/fixtures/simc/giannis_elemental_report.json').read_text(encoding='utf-8'))
        before = copy.deepcopy(report)
        names = localize_report(report, None, catalog_for_build(report['engine']['gameVersion']),
            engine_revision='simc:managed:f50a2121bf894570146507496f3e113bff68e445:' + 'b' * 64)
        self.assertEqual(names['status'], 'legacy')
        for group in ('abilities', 'buffs'):
            self.assertTrue(all(label['status'] == 'legacy' and label['spellId'] is None for label in names[group]))
        self.assertEqual(report, before)

    def test_sidecar_cannot_be_reused_for_other_metrics_with_the_same_tokens(self):
        report = sample_report(); identity = extract_report_identity(sample_raw(), report)
        report['abilities'][0]['amount'] = 200
        self.assertFalse(validate_report_identity(identity, report))

    def test_html_embedded_report_templates_preserve_safe_npc_metadata(self):
        html = '<script>render(`<a href="https://www.wowhead.com/npc=61029">primal_fire_elemental</a>`)</script>'
        self.assertEqual(npc_sources_from_html(html), {'primal_fire_elemental': 61029})

    def test_public_localization_is_opt_in_and_does_not_mutate_persisted_metrics(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from tests.app_simulation_report_test import report_fixture
        from server.app.simulation.report import normalize_simc_report
        from server.app.simulation.application import public_simulation_report
        identity = {}
        report = normalize_simc_report(json.dumps(report_fixture()), expected_actor='Stormsample', identity_sink=identity)
        stored = {'report': report, 'reportIdentity': identity}
        before = copy.deepcopy(stored)
        view = SimpleNamespace(result=SimpleNamespace(result=stored, runtime_revision='r', primary_metric_name=report['metric']['name'], primary_metric_value=report['metric']['value']))
        self.assertEqual(public_simulation_report(view), report)
        with patch('server.app.simulation.localization.catalog_for_build', return_value=sample_catalog()):
            localized = public_simulation_report(view, localized=True)
        self.assertEqual(localized['schemaVersion'], 2)
        self.assertEqual(localized['metric'], report['metric'])
        self.assertEqual(localized['abilities'], report['abilities'])
        self.assertNotIn('reportIdentity', localized)
        self.assertEqual(stored, before)

    def test_parser_keeps_private_identifiers_without_expanding_the_v1_report(self):
        from tests.app_simulation_report_test import report_fixture
        from server.app.simulation.worker import RawSimulationExecution, SimulationResultParser
        raw = report_fixture()
        raw['sim']['players'][0]['stats'][0]['id'] = 188196
        metric = SimulationResultParser().parse(RawSimulationExecution(0, '', '', 'r', report_json=json.dumps(raw)), expected_actor='Stormsample')
        self.assertTrue(validate_report_identity(metric.report_identity, metric.report))
        self.assertTrue(any(row['spellId'] == 188196 for row in metric.report_identity['abilities']))
        self.assertEqual(metric.report['schemaVersion'], 1)
        self.assertNotIn('spellId', metric.report['abilities'][0])

    def test_ambiguous_alias_does_not_pick_one_candidate(self):
        catalog = sample_catalog(); catalog.data['spellAliases']['fire_blast'] = None
        result = localize_report(sample_report(), None, catalog)
        self.assertEqual(result['abilities'][0]['status'], 'ambiguous')
        self.assertNotEqual(result['abilities'][0]['text'], '火焰冲击')

    def test_ids_and_children_survive_without_adding_child_damage(self):
        report = sample_report(); before = copy.deepcopy(report)
        identity = extract_report_identity(sample_raw(), report)
        self.assertEqual(identity['abilities'][0]['spellId'], 2136)
        self.assertEqual(identity['abilities'][0]['children'][0]['spellId'], 57984)
        self.assertEqual(identity['buffs'][0]['spellId'], 2825)
        self.assertTrue(validate_report_identity(identity, report))
        self.assertEqual(report, before)

    def test_id_takes_precedence_over_an_unrelated_internal_alias(self):
        report = sample_report(); raw = sample_raw()
        raw['sim']['players'][0]['stats'][0]['name'] = 'misleading_alias'
        report['abilities'][0]['name'] = 'misleading_alias'
        result = localize_report(report, extract_report_identity(raw, report), sample_catalog())
        self.assertEqual(result['abilities'][0]['text'], '火焰冲击')
        self.assertEqual(result['abilities'][0]['method'], 'spell_id')
        self.assertEqual(result['status'], 'complete')

    def test_missing_id_never_reuses_a_different_spell_alias(self):
        report = sample_report(); identity = extract_report_identity(sample_raw(), report)
        identity['abilities'][0]['spellId'] = 999999
        result = localize_report(report, identity, sample_catalog())
        self.assertEqual(result['abilities'][0]['status'], 'unresolved')
        self.assertIn('999999', result['abilities'][0]['text'])
        self.assertEqual(result['status'], 'partial')

    def test_wrong_build_is_not_silently_filled_from_current_names(self):
        report = sample_report(); report['engine']['gameVersion'] = '12.0.0.1'
        result = localize_report(report, None, sample_catalog())
        self.assertEqual(result['status'], 'unavailable')
        self.assertIsNone(result['catalogRevision'])

    def test_legacy_names_are_distinct_from_verified_ids(self):
        result = localize_report(sample_report(), None, sample_catalog())
        self.assertEqual(result['abilities'][0]['text'], '火焰冲击')
        self.assertEqual(result['abilities'][0]['status'], 'legacy')
        self.assertIsNone(result['abilities'][0]['spellId'])
        self.assertEqual(result['status'], 'legacy')

    def test_pet_ids_are_extracted_only_from_unambiguous_simc_links(self):
        html = '<a href="https://www.wowhead.com/npc=61029">primal_fire_elemental</a>'
        self.assertEqual(npc_sources_from_html(html), {'primal_fire_elemental': 61029})
        ambiguous = html + '<a href="https://www.wowhead.com/npc=999">primal_fire_elemental</a>'
        self.assertEqual(npc_sources_from_html(ambiguous), {})
        self.assertEqual(npc_sources_from_html('<a href="https://bad.test/npc=61029">pet</a>'), {})

    def test_pet_source_is_kept_separate_from_the_player_spell(self):
        report = sample_report(); raw = sample_raw(); actor = raw['sim']['players'][0]
        actor['stats_pets'] = {'primal_fire_elemental': actor.pop('stats')}
        report['abilities'][0]['name'] = 'primal_fire_elemental: fire_blast'
        identity = extract_report_identity(raw, report, {'primal_fire_elemental': 61029})
        result = localize_report(report, identity, sample_catalog())
        self.assertEqual(result['abilities'][0]['text'], '原始火元素：火焰冲击')
        self.assertEqual(result['abilities'][0]['sourceNpcId'], 61029)

    def test_identity_cannot_be_reordered_or_attached_to_another_report(self):
        report = sample_report(); identity = extract_report_identity(sample_raw(), report)
        identity['abilities'][0]['token'] = 'different_spell'
        self.assertFalse(validate_report_identity(identity, report))
        with self.assertRaises(ValueError): localize_report(report, identity, sample_catalog())

    def test_catalog_loader_checks_hash_build_and_locale(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); data = sample_catalog().data
            packed = gzip.compress(json.dumps(data).encode(), mtime=0)
            (root/'catalog.json.gz').write_bytes(packed)
            manifest = {'build': data['build'], 'locale': 'zhCN', 'sha256': hashlib.sha256(packed).hexdigest()}
            (root/'manifest.json').write_text(json.dumps(manifest))
            catalog = LocalizationCatalog.load(root, data['build'])
            self.assertEqual(catalog.data['spells']['2825'], '嗜血')
            with self.assertRaises(ValueError): LocalizationCatalog.load(root, '12.0.0.1')
            (root/'catalog.json.gz').write_bytes(packed + b'changed')
            with self.assertRaises(ValueError): LocalizationCatalog.load(root, data['build'])


if __name__ == '__main__': unittest.main()

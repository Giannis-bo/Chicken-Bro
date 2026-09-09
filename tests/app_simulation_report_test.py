import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from server.app.simulation.report import normalize_simc_report, SimulationReportError

from server.app.simulation.worker import LocalSimulationCraftPort, RawSimulationExecution, SimulationResultParser, SimulationWorkerError
from server.app.simulation.readiness import ManagedSimcRuntimeIdentity


def report_fixture():
    return {
        'version': '1210-01', 'sim': {
            'options': {'iterations': 100, 'confidence_estimator': 2.0},
            'statistics': {'elapsed_time_seconds': 1.25},
            'players': [{
                'name': 'Stormsample', 'race': 'orc', 'level': 90, 'role': 'spell',
                'specialization': 'Elemental Shaman', 'talents': 'CYQAAAA',
                'dbc': {'version_used': 'Live', 'Live': {'wow_version': '12.1.0.69299', 'build_level': 69299}},
                'collected_data': {'dps': {'mean': 10000, 'mean_std_dev': 25, 'count': 99},
                    'fight_length': {'mean': 180}, 'resource_lost': {'maelstrom': {'mean': 150}},
                    'buffed_stats': {'attribute': {'intellect': 1200}, 'stats': {'crit_rating': 320}}},
                'stats': [{'name': 'lightning_bolt', 'type': 'damage', 'compound_amount': 900000,
                    'portion_amount': 0.5, 'num_executes': {'mean': 10},
                    'direct_results': {'crit': {'count': {'mean': 3}}, 'hit': {'count': {'mean': 7}}}}],
                'buffs': [{'name': 'bloodlust', 'uptime': 22.2}],
                'gains': [{'name': 'Lightning Bolt', 'maelstrom': {'actual': 160}}],
                'gear': {'main_hand': {'encoded_item': 'staff,id=12345,bonus_id=1/2', 'ilevel': 150}}
            }]
        }
    }


class SimulationReportTest(unittest.TestCase):
    def test_augmentation_selects_owner_not_simplified_teammates_and_preserves_identity(self):
        payload = report_fixture()
        actor = payload['sim']['players'][0]
        actor['specialization'] = 'Augmentation Evoker'
        allies = [{'name': name, 'specialization': 'Unknown', 'race': 'none',
                   'collected_data': {'dps': {'mean': 999999}}}
                  for name in ('Bob Shadow1', 'Bob Shadow2', 'Bob FDK', 'Bob BM',
                               'Bob Flat1', 'Bob Demo', 'Bob Healer1', 'Bob BDK')]
        payload['sim']['players'] = allies[:3] + [actor] + allies[3:]
        identity = {}
        report = normalize_simc_report(json.dumps(payload), expected_actor='Stormsample', identity_sink=identity)
        self.assertEqual(report['metric']['value'], 10000)
        self.assertEqual(report['actor']['name'], 'Stormsample')
        self.assertEqual(report['actor']['specialization'], 'Augmentation')
        self.assertEqual(identity['abilities'][0]['token'], 'lightning_bolt')
        # Another actual player or duplicate owner must never be silently ignored.
        for mutation in ('real_player', 'duplicate', 'wrong_spec', 'unexpected_ally'):
            changed = json.loads(json.dumps(payload))
            with self.subTest(mutation=mutation):
                if mutation == 'real_player': changed['sim']['players'][0]['specialization'] = 'Shadow Priest'
                elif mutation == 'duplicate': changed['sim']['players'][0]['name'] = 'Stormsample'
                elif mutation == 'wrong_spec': changed['sim']['players'][3]['specialization'] = 'Devastation Evoker'
                else: changed['sim']['players'][0]['name'] = 'Unexpected character'
                with self.assertRaises(SimulationReportError):
                    self.parse(changed)

    def setUp(self):
        self.identity = ManagedSimcRuntimeIdentity(Path('/test/simc'), 'a' * 40, 'b' * 64, 'r')
        identity_patch = patch('server.app.simulation.worker.inspect_managed_simc_runtime', create=True, return_value=self.identity)
        identity_patch.start()
        self.addCleanup(identity_patch.stop)

    def parse(self, payload):
        from server.app.simulation.report import normalize_simc_report
        return normalize_simc_report(json.dumps(payload), expected_actor='Stormsample')

    def test_real_json_shape_normalizes_actor_metric_units_and_details(self):
        report = self.parse(report_fixture())
        self.assertEqual(report['actor']['className'], 'Shaman')
        self.assertEqual(report['actor']['specialization'], 'Elemental')
        self.assertEqual(report['metric'], {'name': 'dps', 'value': 10000, 'error': 50})
        self.assertEqual(report['engine'], {'version': '1210-01', 'gameVersion': '12.1.0.69299', 'build': '69299'})
        self.assertEqual(report['statistics'], {'iterations': 99, 'fightLengthSeconds': 180, 'elapsedSeconds': 1.25})
        self.assertEqual(report['abilities'][0], {'name': 'lightning_bolt', 'amount': 900000, 'portion': 100, 'executions': 10, 'critPercent': 30})
        self.assertEqual(report['resources'], [{'name': 'maelstrom', 'gained': 160, 'lost': 150}])
        self.assertEqual(report['gear'], [{'slot': 'main_hand', 'itemId': 12345, 'itemLevel': 150}])
        self.assertEqual(report['buffs'], [{'name': 'bloodlust', 'uptime': 22.2}])

    def test_actor_mismatch_duplicates_and_nonfinite_metrics_fail(self):
        for change in ('actor', 'multiple', 'zero', 'nan', 'infinity', 'bool'):
            payload = report_fixture(); actor = payload['sim']['players'][0]
            if change == 'actor': actor['name'] = 'Other'
            elif change == 'multiple': payload['sim']['players'].append(actor.copy())
            else: actor['collected_data']['dps']['mean'] = {'zero': 0, 'nan': float('nan'), 'infinity': float('inf'), 'bool': True}[change]
            with self.subTest(change=change), self.assertRaises(ValueError): self.parse(payload)

    def test_healer_uses_hps_and_missing_optional_fields_stay_absent(self):
        payload = report_fixture(); actor = payload['sim']['players'][0]
        actor['role'] = 'heal'; actor['collected_data'] = {'hps': {'mean': 5000}}
        actor.pop('stats'); actor.pop('gear')
        report = self.parse(payload)
        self.assertEqual(report['metric'], {'name': 'hps', 'value': 5000, 'error': None})
        self.assertEqual(report['gear'], [])
        self.assertIsNone(report['statistics']['fightLengthSeconds'])

    def test_canonical_attribute_percentages_are_scaled_without_changing_ratings(self):
        payload = report_fixture()
        stats = payload['sim']['players'][0]['collected_data']['buffed_stats']['stats']
        stats.update({
            'crit_pct': 0.2537, 'haste_pct': 0.2537, 'mastery_pct': 0.2537,
            'versatility_pct': 0.2537, 'avoidance_pct': 0.2537, 'leech_pct': 0.2537,
            'crit_rating': 2537, 'haste_rating': 2537, 'mastery_rating': 2537,
            'versatility_rating': 2537, 'avoidance_rating': 2537, 'leech_rating': 2537,
            'speed_rating': 2537, 'spell_power': 2537, 'attack_power': 2537,
            'armor': 2537, 'manareg_per_second': 2537,
            'spell_crit': 0.2537, 'attack_crit': 0.2537, 'mastery_value': 0.2537,
            'spell_haste': 0.8, 'attack_haste': 0.8, 'spell_cast_speed': 0.8,
            'auto_attack_speed': 0.8, 'speed_pct': 7, 'unknown_custom_stat': 99,
        })
        attributes = {row['name']: row['value'] for row in self.parse(payload)['attributes']}
        for key in ('crit_pct', 'haste_pct', 'mastery_pct', 'versatility_pct', 'avoidance_pct', 'leech_pct'):
            with self.subTest(key=key): self.assertAlmostEqual(attributes[key], 25.37)
        for key in ('crit_rating', 'haste_rating', 'mastery_rating', 'versatility_rating', 'avoidance_rating',
                    'leech_rating', 'speed_rating', 'spell_power', 'attack_power', 'armor', 'manareg_per_second'):
            with self.subTest(key=key): self.assertEqual(attributes[key], 2537)
        for key in ('spell_crit', 'attack_crit', 'mastery_value', 'spell_haste', 'attack_haste',
                    'spell_cast_speed', 'auto_attack_speed', 'speed_pct', 'unknown_custom_stat'):
            with self.subTest(key=key): self.assertNotIn(key, attributes)
        self.assertEqual(attributes['intellect'], 1200)

    def test_buff_without_reported_uptime_is_omitted_and_explicit_zero_preserved(self):
        payload = report_fixture()
        actor = payload['sim']['players'][0]
        actor['buffs'] = [{'name': 'unknown_dynamic'}, {'name': 'zero_dynamic', 'uptime': 0}]
        actor['buffs_constant'] = [{'name': 'unknown_constant'}, {'name': 'known_constant', 'uptime': 100}]
        self.assertEqual(self.parse(payload)['buffs'], [
            {'name': 'zero_dynamic', 'uptime': 0}, {'name': 'known_constant', 'uptime': 100},
        ])

    def test_aggregated_ability_portions_use_matching_compound_amounts(self):
        payload = report_fixture()
        actor = payload['sim']['players'][0]
        actor['stats'] = [
            {'name': 'crash_lightning', 'type': 'damage', 'compound_amount': 75, 'portion_amount': 0.03989,
             'children': [{'name': 'child', 'type': 'damage', 'compound_amount': 60}]},
            {'name': 'lightning_bolt', 'type': 'damage', 'compound_amount': 25, 'portion_amount': 0.25},
        ]
        abilities = self.parse(payload)['abilities']
        self.assertEqual([(row['name'], row['amount'], row['portion']) for row in abilities],
                         [('crash_lightning', 75, 75), ('lightning_bolt', 25, 25)])

    def test_crit_rounding_at_one_hundred_remains_valid(self):
        from server.app.simulation.report import validate_simc_report
        payload = report_fixture()
        payload['sim']['players'][0]['stats'][0]['direct_results'] = {'crit': {'count': {'mean': 0.8378378378378378}}}
        report = self.parse(payload)
        self.assertEqual(report['abilities'][0]['critPercent'], 100)
        self.assertTrue(validate_simc_report(report))

    def test_persisted_report_canonicalization_is_narrow_and_does_not_mutate(self):
        from server.app.simulation.report import canonicalize_simc_report
        report = self.parse(report_fixture())
        report['abilities'][0]['critPercent'] = 100.00000000000001
        report['abilities'][0]['portion'] = 50
        report['buffs'][0]['uptime'] = -1e-14
        corrected = canonicalize_simc_report(report)
        self.assertEqual(corrected['abilities'][0]['critPercent'], 100)
        self.assertEqual(corrected['abilities'][0]['portion'], 100)
        self.assertEqual(corrected['buffs'][0]['uptime'], 0)
        self.assertEqual(report['abilities'][0]['critPercent'], 100.00000000000001)
        self.assertEqual(report['abilities'][0]['portion'], 50)
        self.assertEqual(report['buffs'][0]['uptime'], -1e-14)
        for invalid in (100.001, 100.00001, -0.001, float('nan'), float('inf'), True):
            report['abilities'][0]['critPercent'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError): canonicalize_simc_report(report)

    def test_arrays_strings_and_json_size_are_bounded(self):
        payload = report_fixture(); actor = payload['sim']['players'][0]
        actor['buffs'] = [{'name': 'x' * 500, 'uptime': 100}] * 1000
        report = self.parse(payload)
        self.assertLessEqual(len(report['buffs']), 256)
        self.assertLessEqual(len(report['buffs'][0]['name']), 160)
        from server.app.simulation.report import normalize_simc_report, MAX_REPORT_BYTES
        with self.assertRaises(ValueError): normalize_simc_report(' ' * (MAX_REPORT_BYTES + 1), expected_actor='Stormsample')

    def test_real_json_execution_does_not_fallback_to_successful_text(self):
        execution = RawSimulationExecution(0, 'Player: Stormsample\nDPS=10000\n', '', 'r', report_json='broken', requires_json=True)
        with self.assertRaises(SimulationWorkerError): SimulationResultParser().parse(execution, expected_actor='Stormsample')

    def test_persisted_report_validator_rejects_extra_keys_and_invalid_nested_data(self):
        from server.app.simulation.report import validate_simc_report
        report = self.parse(report_fixture())
        self.assertTrue(validate_simc_report(report))
        for case in ('secret', 'bool', 'nan', 'rows', 'missing', 'percent'):
            changed = json.loads(json.dumps(report))
            if case == 'secret': changed['actor']['rawProfile'] = 'private'
            elif case == 'bool': changed['metric']['value'] = True
            elif case == 'nan': changed['abilities'][0]['amount'] = float('nan')
            elif case == 'rows': changed['abilities'] *= 1000
            elif case == 'missing': del changed['gear']
            else: changed['buffs'][0]['uptime'] = 101
            with self.subTest(case=case): self.assertFalse(validate_simc_report(changed))

    def test_json_metric_survives_truncated_text(self):
        execution = RawSimulationExecution(0, 'header only', '', 'r', report_json=json.dumps(report_fixture()), requires_json=True)
        metric = SimulationResultParser().parse(execution, expected_actor='Stormsample')
        self.assertEqual((metric.value, metric.error, metric.error_pct), (10000, 50, 0.5))
        self.assertEqual(metric.report['actor']['name'], 'Stormsample')

    def test_derived_error_percentage_cannot_overflow_into_persisted_result(self):
        payload = report_fixture()
        payload['sim']['players'][0]['collected_data']['dps']['mean'] = 1e-320
        execution = RawSimulationExecution(0, '', '', 'r', report_json=json.dumps(payload), requires_json=True)
        with self.assertRaises(SimulationWorkerError):
            SimulationResultParser().parse(execution, expected_actor='Stormsample')

    def test_runner_private_output_is_read_then_removed(self):
        paths = []
        def runner(args, **kwargs):
            output = Path(next(v[5:].split(',')[0] for v in args if v.startswith('json=')))
            paths.append(output)
            self.assertTrue(output.parent.is_dir())
            output.write_text(json.dumps(report_fixture()), encoding='utf-8')
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        with patch('server.app.simulation.worker.os.path.isfile', return_value=True), patch('server.app.simulation.worker.os.access', return_value=True):
            execution = LocalSimulationCraftPort(binary='/test/simc', runtime_revision='r', runner=runner).run(SimpleNamespace(profile='shaman=Stormsample'), 'r')
        self.assertTrue(execution.requires_json)
        self.assertFalse(paths[0].parent.exists())
        self.assertEqual(json.loads(execution.report_json)['version'], '1210-01')

    def test_runner_missing_report_and_timeout_are_explicit_failures(self):
        for timeout in (False, True):
            def runner(*args, **kwargs):
                if timeout: raise subprocess.TimeoutExpired('simc', 45)
                return SimpleNamespace(returncode=0, stdout='Player: Stormsample\nDPS=10000', stderr='')
            with patch('server.app.simulation.worker.os.path.isfile', return_value=True), patch('server.app.simulation.worker.os.access', return_value=True):
                with self.assertRaises(SimulationWorkerError) as error:
                    LocalSimulationCraftPort(binary='/test/simc', runtime_revision='r', runner=runner).run(SimpleNamespace(profile='x'), 'r')
            self.assertEqual(error.exception.code, 'SIMC_TIMEOUT' if timeout else 'SIMC_REPORT_INVALID')

    def test_worker_refuses_changed_managed_binary_identity(self):
        changed = ManagedSimcRuntimeIdentity(Path('/test/simc'), 'c' * 40, 'd' * 64, 'other')
        with patch('server.app.simulation.worker.inspect_managed_simc_runtime', return_value=changed):
            with self.assertRaises(SimulationWorkerError) as error:
                LocalSimulationCraftPort(binary='/test/simc', runtime_revision='r', runner=lambda *a, **kw: None).run(SimpleNamespace(profile='x'), 'r')
        self.assertEqual(error.exception.code, 'SIMC_RUNTIME_REVISION_STALE')

    def test_oversized_output_and_identity_changes_cannot_publish_json(self):
        from server.app.simulation.report import MAX_REPORT_BYTES
        for case in ('oversized', 'identity_changed'):
            paths = []
            def runner(args, **kwargs):
                output = Path(next(v[5:].split(',')[0] for v in args if v.startswith('json=')))
                paths.append(output)
                if case == 'oversized':
                    with output.open('wb') as stream: stream.truncate(MAX_REPORT_BYTES + 1)
                else: output.write_text(json.dumps(report_fixture()), encoding='utf-8')
                return SimpleNamespace(returncode=0, stdout='', stderr='')
            changed = ManagedSimcRuntimeIdentity(Path('/test/simc'), 'c' * 40, 'd' * 64, 'other')
            with self.subTest(case=case), patch('server.app.simulation.worker.inspect_managed_simc_runtime', side_effect=[self.identity, changed if case == 'identity_changed' else self.identity]):
                with self.assertRaises(SimulationWorkerError) as error:
                    LocalSimulationCraftPort(binary='/test/simc', runtime_revision='r', runner=runner).run(SimpleNamespace(profile='x'), 'r')
            self.assertEqual(error.exception.code, 'SIMC_REPORT_INVALID' if case == 'oversized' else 'SIMC_RUNTIME_REVISION_STALE')
            self.assertFalse(paths[0].parent.exists())


if __name__ == '__main__': unittest.main()

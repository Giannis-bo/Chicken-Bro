import json
import unittest
from dataclasses import replace

from server.app.simulation.worker import RawSimulationExecution, SimulationResultParser
from tests.app_simulation_report_test import report_fixture
from tests import app_chickenbro_simulation_tools_test as tool_fixtures
from tests import app_simulation_worker_test as worker_fixtures


class EngineDiagnosticsTest(unittest.TestCase):
    def test_clean_and_legacy_execution_do_not_invent_diagnostics(self):
        parser = SimulationResultParser()
        metric = parser.parse(RawSimulationExecution(0, '', '', 'r', report_json=json.dumps(report_fixture())),
                              expected_actor='Stormsample')
        self.assertEqual(metric.engine_diagnostics, [])
        legacy = parser.parse(RawSimulationExecution(0, 'Player: Stormsample\nDPS=100\n', '', 'r'),
                              expected_actor='Stormsample')
        self.assertIsNone(legacy.engine_diagnostics)

    def test_parser_retains_engine_uncertainty_without_exposing_log_messages(self):
        payload = report_fixture()
        payload['logs'] = [
            {'level': 'implementation_not_yet_verified', 'message': 'private path /secret and actor'},
            {'level': 'implementation_not_yet_verified', 'message': 'second warning'},
            {'level': 'using_unverified_values', 'message': 'unknown coefficient'},
            {'level': 'trivial', 'message': 'routine note'},
        ]
        metric = SimulationResultParser().parse(
            RawSimulationExecution(0, '', '', 'runtime', report_json=json.dumps(payload)),
            expected_actor='Stormsample')
        self.assertEqual(getattr(metric, 'engine_diagnostics', None),
                         ['implementation_not_yet_verified', 'using_unverified_values'])
        self.assertEqual(metric.value, 10000)


class WorkerDiagnosticsTest(unittest.TestCase):
    setUp = worker_fixtures.SimulationWorkerTest.setUp
    build_worker = worker_fixtures.SimulationWorkerTest.build_worker

    def test_worker_persists_diagnostic_categories_alongside_profile_provenance(self):
        payload = report_fixture()
        payload['logs'] = [{'level': 'not_yet_implemented', 'message': '/private/path'}]
        worker, repository = self.build_worker(RawSimulationExecution(
            0, '', '', 'simc:current:abc', report_json=json.dumps(payload), requires_json=True))
        self.assertEqual(worker.handle(self.lease).value, 'succeeded')
        result = repository.results[0]
        self.assertEqual(result.result['engineDiagnostics'], ['not_yet_implemented'])
        self.assertEqual(result.result['provenance']['profileSha256'], result.profile_sha256)
        self.assertNotIn('/private/path', json.dumps(result.result))


class ComparisonDiagnosticsTest(unittest.TestCase):
    setUp = tool_fixtures.SimulationToolGatewayTest.setUp
    advance = tool_fixtures.SimulationToolGatewayTest.advance
    prepare = tool_fixtures.SimulationToolGatewayTest.prepare
    submit = tool_fixtures.SimulationToolGatewayTest.submit
    complete = tool_fixtures.SimulationToolGatewayTest.complete

    def test_comparison_carries_both_sides_uncertainty_and_preserves_owner_check(self):
        from server.app.simulation.compiler import SimcProfileCompiler
        caps = replace(self.application._runtime_capabilities, compiler_revision='chickenbro-simc-compiler-v4')
        self.application._runtime_capabilities = caps
        self.application._compiler = SimcProfileCompiler(capabilities=caps)
        a = self.submit(self.prepare()['snapshotId'])
        b = self.submit(a['snapshotId'], {'equipmentOverrides': {'trinket1': {'itemId': 9999, 'itemLevel': 285, 'bonusIds': [], 'gems': [], 'enchant': None}}})
        for packet, codes in ((a, ['implementation_not_yet_verified']),
                              (b, ['using_unverified_values', '/private'])):
            result = self.complete(packet)
            self.repository.save_result(replace(result, result={**result.result, 'engineDiagnostics': codes}))
            actual = self.gateway.execute(self.token, 'get', {'jobId': packet['jobId']})
            self.assertEqual(actual['result']['engineDiagnostics'], codes[:1])
            self.assertTrue(any('mechanic' in s.lower() for s in actual['limitations']))
        args = {'baselineJobId': a['jobId'], 'variantJobId': b['jobId']}
        packet = self.gateway.execute(self.token, 'compare', args)
        comparison = packet['comparison']
        self.assertEqual(comparison.get('engineDiagnostics'), {
            'baseline': ['implementation_not_yet_verified'], 'variant': ['using_unverified_values']})
        self.assertTrue(any('mechanic' in s.lower() for s in comparison['limitations']))
        from uuid import uuid4
        other = self.gateway.issue_capability(replace(self.context, principal=self.other, run_id=uuid4()))
        self.assertEqual(self.gateway.execute(other, 'compare', args)['status'], 'blocked')

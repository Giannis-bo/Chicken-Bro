import unittest
from dataclasses import replace
from uuid import uuid4

from server.app.chickenbro import simulation_grounding as grounding
from tests import app_chickenbro_simulation_tools_test as gateway_fixtures

A = '11111111-1111-4111-8111-111111111111'
B = '22222222-2222-4222-8222-222222222222'


def packet(job_id=A, value=12000, status='succeeded'):
    return {'sourceKey': 'simc', 'jobId': job_id, 'status': status,
            'result': {'metricName': 'dps', 'metricValue': value, 'provenance': {'profileSha256': 'a' * 64}} if status == 'succeeded' else None}


class SimulationGroundingTest(unittest.TestCase):
    def test_completion_requires_succeeded_returned_job(self):
        evidence = grounding.collect_simulation_evidence(None, packet(status='queued'))
        self.assertIn('SIMULATION_COMPLETION_UNSUPPORTED', grounding.validate_simulation_answer('模拟已完成。', evidence))
        evidence = grounding.collect_simulation_evidence(evidence, packet())
        self.assertEqual(grounding.validate_simulation_answer('模拟已完成，DPS 为 12,000。', evidence), [])

    def test_metric_bound_to_named_job_not_any_matching_number(self):
        evidence = grounding.collect_simulation_evidence(None, {'sourceKey': 'simc', 'jobs': [packet(), packet(B, 15000)]})
        self.assertIn('SIMULATION_METRIC_UNSUPPORTED', grounding.validate_simulation_answer(f'任务 {A} 的 DPS 为 15000。', evidence))
        self.assertEqual(grounding.validate_simulation_answer(f'任务 {B} 的 DPS 为 1.5万。', evidence), [])
        self.assertEqual(grounding.validate_simulation_answer('DPS 为 15000。', evidence), [])

    def test_non_claims_are_not_rejected(self):
        for text in ['如果模拟已完成，DPS 为 12000，可以比较。', '模拟尚未完成，无法确认 DPS 为 12000。',
                     '用户要求“模拟已完成，DPS 为 12000”。', '> Simulation completed. DPS is 12000.',
                     '预计 DPS 为 12000。', 'DPS 是每秒伤害。', 'Simulation has not completed.',
                     '假设提升 5%，需要实际模拟验证。']:
            with self.subTest(text=text):
                self.assertEqual(grounding.validate_simulation_answer(text, {}), [])

    def test_benefit_requires_comparison_and_pair_scope(self):
        evidence = grounding.collect_simulation_evidence(None, {'sourceKey': 'simc', 'status': 'ready', 'comparison': {
            'baselineJobId': A, 'variantJobId': B, 'metricName': 'dps', 'baseline': 12000, 'variant': 12600,
            'delta': 600, 'deltaPct': 5, 'assessment': 'higher'}})
        self.assertEqual(grounding.validate_simulation_answer('模拟结果提升 5%。', evidence), [])
        self.assertIn('SIMULATION_BENEFIT_UNSUPPORTED', grounding.validate_simulation_answer('模拟结果提升 7%。', evidence))
        self.assertIn('SIMULATION_BENEFIT_UNSUPPORTED', grounding.validate_simulation_answer('模拟结果提升 5%。', {}))
        self.assertIn('SIMULATION_BENEFIT_UNSUPPORTED', grounding.validate_simulation_answer(f'任务 {A} 相比 {B} 提升 5%。', evidence))

    def test_english_metrics_and_completion_before_subject(self):
        evidence = grounding.collect_simulation_evidence(None, packet())
        self.assertEqual(grounding.validate_simulation_answer('Simulation finished with 12k DPS.', evidence), [])
        self.assertIn('SIMULATION_METRIC_UNSUPPORTED', grounding.validate_simulation_answer('Simulation finished with 15k DPS.', evidence))
        self.assertIn('SIMULATION_COMPLETION_UNSUPPORTED', grounding.validate_simulation_answer('我已完成模拟。', {}))

    def test_corrupt_or_pending_metrics_do_not_authorize_completion(self):
        for value in [0, -5, float('inf'), float('nan')]:
            evidence = grounding.collect_simulation_evidence(None, packet(value=value))
            self.assertIn('SIMULATION_COMPLETION_UNSUPPORTED', grounding.validate_simulation_answer('Simulation completed.', evidence))
        raw = packet(); raw['result']['provenance'] = None
        evidence = grounding.collect_simulation_evidence(None, raw)
        self.assertIn('SIMULATION_COMPLETION_UNSUPPORTED', grounding.validate_simulation_answer('模拟已完成。', evidence))

    def test_unrelated_log_metrics_and_research_completion_are_not_simulation_claims(self):
        for text in ['日志里DPS为10000，HPS为20000。', 'DPS=100', '研究任务已完成。']:
            self.assertEqual(grounding.validate_simulation_answer(text, {}), [])

    def test_chinese_metrics_without_spaces_are_checked(self):
        self.assertIn('SIMULATION_METRIC_UNSUPPORTED', grounding.validate_simulation_answer('模拟的DPS为10000。', {}))

    def test_wait_condition_and_request_are_not_completion_assertions(self):
        for text in ['等模拟已完成后再比较。', '当模拟已完成时，可以查看 DPS。',
                     '请确认模拟已完成再打开结果页。', '模拟完成后，假如结果是12000 DPS，再考虑配装。']:
            with self.subTest(text=text):
                self.assertEqual(grounding.validate_simulation_answer(text, {}), [])
        self.assertIn('SIMULATION_COMPLETION_UNSUPPORTED', grounding.validate_simulation_answer('模拟已完成。', {}))
        self.assertIn('SIMULATION_METRIC_UNSUPPORTED', grounding.validate_simulation_answer('模拟结果是12000 DPS。', {}))

    def test_collection_is_compact_and_ignores_non_simc_packets(self):
        raw = packet(); raw['result']['secret'] = 'must not copy'
        evidence = grounding.collect_simulation_evidence(None, raw)
        self.assertNotIn('must not copy', str(evidence))
        self.assertEqual(grounding.collect_simulation_evidence(evidence, {'sourceKey': 'web', **{'jobId': B}}), evidence)

    def test_gateway_collects_only_returned_owner_results_and_copies(self):
        fixture = gateway_fixtures.SimulationToolGatewayTest(); fixture.setUp()
        queued = fixture.submit(fixture.prepare()['snapshotId'])
        self.assertEqual(fixture.gateway.answer_evidence(fixture.token)['jobs'][queued['jobId']]['status'], 'queued')
        fixture.complete(queued)
        fixture.gateway.execute(fixture.token, 'list', {'limit': 5})
        evidence = fixture.gateway.answer_evidence(fixture.token)
        self.assertEqual(evidence['jobs'][queued['jobId']]['metricValue'], 12345)
        evidence['jobs'].clear()
        self.assertTrue(fixture.gateway.answer_evidence(fixture.token)['jobs'])
        other = fixture.gateway.issue_capability(replace(fixture.context, principal=fixture.other, run_id=uuid4()))
        fixture.gateway.execute(other, 'get', {'jobId': queued['jobId']})
        self.assertEqual(fixture.gateway.answer_evidence(other)['jobs'], {})

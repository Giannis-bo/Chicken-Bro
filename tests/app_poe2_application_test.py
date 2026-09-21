import unittest
from uuid import uuid4


class Poe2ApplicationContractTests(unittest.TestCase):
    def test_compare_rejects_different_baselines_and_engine_versions(self):
        from server.app.poe2.application import compare_results, Poe2Error
        a = {'buildId': 'a', 'status': 'succeeded', 'result': {
            'inputSha256': 'x', 'engineVersion': '1', 'stats': {'Life': 100, 'CombinedDPS': 200}}}
        for b in ({**a, 'buildId': 'b'}, {**a, 'result': {**a['result'], 'engineVersion': '2'}},
                  {**a, 'status': 'queued'}):
            with self.assertRaises(Poe2Error):
                compare_results([a, b])

    def test_compare_has_explicit_zero_baseline_and_real_delta(self):
        from server.app.poe2.application import compare_results
        a = {'buildId': 'a', 'status': 'succeeded', 'result': {
            'inputSha256': 'x', 'engineVersion': '1', 'stats': {'Life': 100, 'CombinedDPS': 0}}}
        b = {**a, 'result': {**a['result'], 'stats': {'Life': 120, 'CombinedDPS': 10}}}
        result = compare_results([a, b])
        self.assertEqual(result['metrics']['Life'], {'baseline': 100, 'candidate': 120, 'delta': 20, 'percent': 20.0})
        self.assertIsNone(result['metrics']['CombinedDPS']['percent'])

    def test_success_requires_identity_and_finite_domain_metrics(self):
        from server.app.poe2.application import validate_result, Poe2Error
        for result in ({}, {'stats': {'Life': float('nan')}}, {'stats': {'Life': 0}},
                       {'stats': {'Life': 10}, 'engineVersion': 'unverified'}):
            with self.assertRaises(Poe2Error):
                validate_result(result)


if __name__ == '__main__':
    unittest.main()

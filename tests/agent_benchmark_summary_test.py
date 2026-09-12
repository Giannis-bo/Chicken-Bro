import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
spec = importlib.util.spec_from_file_location('summary', ROOT/'scripts/summarize-agent-benchmark.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def run(variant, usage):
    return {'caseId': 'c', 'category': 'wcl', 'trial': 1, 'variant': variant,
        'reviewId': variant, 'status': 'succeeded', 'totalMs': 100,
        'turns': [{'turnIndex': 0, 'startupMs': 5, 'timing': {'toolMs': 2, 'toolCount': 1,
            'tools': {}, 'repeatedQueries': [], 'issues': []}, 'modelUsage': usage}]}


class SummaryTests(unittest.TestCase):
    def test_unreviewed_answer_is_not_a_fast_pass(self):
        result = module.summarize([run('old', []), run('new', [])], [])
        self.assertEqual(result['overall']['pairedCount'], 0)
        self.assertEqual(result['overall']['variants']['new']['qualityCounts'], {'unreviewed': 1})

    def test_repairs_count_but_missing_usage_never_becomes_zero_cost(self):
        usage = [{'phase': 'primary', 'usage': {'inputTokens': 100, 'cachedInputTokens': 50, 'outputTokens': 10}},
                 {'phase': 'repair', 'usage': {'inputTokens': 20, 'cachedInputTokens': 0, 'outputTokens': 5}}]
        result = module.summarize([run('old', usage), run('new', [{'phase': 'primary', 'usage': None}])],
            [{'reviewId': v, 'quality': 'pass'} for v in ('old', 'new')])
        diagnostics = result['diagnosticsOnQualityPassedPairs']
        self.assertEqual(diagnostics['old']['totals']['uncachedInputTokens'], 70)
        self.assertEqual(diagnostics['old']['totals']['repairSessions'], 1)
        self.assertIsNone(diagnostics['new']['totals']['inputTokens'])

    def test_conflicting_duplicate_judgments_are_rejected(self):
        with self.assertRaises(ValueError):
            module.summarize([], [{'reviewId': 'x', 'quality': q} for q in ('pass', 'fail')])

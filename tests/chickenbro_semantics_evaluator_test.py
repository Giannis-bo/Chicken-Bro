import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/evaluate-chickenbro-semantics.py'


class SemanticsEvaluationTests(unittest.TestCase):
    def run_cli(self, *args):
        result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_corpus_validation_never_claims_semantic_pass(self):
        result = self.run_cli()
        self.assertEqual(result['caseCount'], 20)
        self.assertEqual(result['semanticStatus'], 'not_run')
        self.assertGreaterEqual(result['multiTurnCaseCount'], 4)

    def score(self, result):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.json'
            path.write_text(json.dumps({'results': [result]}))
            return self.run_cli('--traces', str(path))['results'][0]

    def base(self):
        return {'caseId': 'simple-class-question', 'configuration': {'runtimeRevision': 'test', 'model': 'test'},
                'turns': [{'turnIndex': 0, 'runStatus': 'succeeded', 'finalAnswer': '增强萨是萨满祭司的近战输出专精。',
                           'toolObservations': []}]}

    def test_successful_runtime_without_human_review_stays_unknown(self):
        self.assertEqual(self.score(self.base())['semanticStatus'], 'awaiting_review')

    def test_human_review_must_cover_every_rubric_item(self):
        trace = self.base()
        trace['humanReview'] = {'reviewer': 'test-reviewer', 'verdicts': ['pass'], 'notes': 'Reviewed'}
        self.assertEqual(self.score(trace)['semanticStatus'], 'awaiting_review')
        trace['humanReview']['verdicts'] = ['pass'] * 3
        self.assertEqual(self.score(trace)['semanticStatus'], 'passed')

    def test_missing_trace_turn_cannot_pass_even_with_review(self):
        trace = self.base()
        trace['turns'] = []
        trace['humanReview'] = {'reviewer': 'test', 'verdicts': ['pass'] * 3, 'notes': 'Reviewed'}
        self.assertEqual(self.score(trace)['semanticStatus'], 'insufficient_trace')

    def test_human_failure_is_preserved(self):
        trace = self.base()
        trace['humanReview'] = {'reviewer': 'test', 'verdicts': ['pass', 'fail', 'pass'], 'notes': 'Unnecessary research'}
        self.assertEqual(self.score(trace)['semanticStatus'], 'failed')

    def test_failed_execution_and_missing_identity_cannot_pass(self):
        trace = self.base()
        trace['humanReview'] = {'reviewer': 'test', 'verdicts': ['pass'] * 3, 'notes': 'Reviewed'}
        trace['turns'][0]['runStatus'] = 'failed'
        self.assertEqual(self.score(trace)['semanticStatus'], 'insufficient_trace')
        trace = self.base()
        trace.pop('configuration')
        self.assertEqual(self.score(trace)['semanticStatus'], 'insufficient_trace')

    def test_unrun_cases_are_visible_in_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.json'
            path.write_text(json.dumps({'results': [self.base()]}))
            summary = self.run_cli('--traces', str(path))
            self.assertEqual(summary['unrunCaseCount'], 19)
            self.assertNotEqual(summary['semanticStatus'], 'passed')


class LegacyResearchSelectionTests(unittest.TestCase):
    def load_cases(self, selected):
        # Execute only the real pure selector; importing the legacy cloud runner
        # also imports optional server libraries unavailable to an offline check.
        import ast
        import typing
        source = ROOT / 'scripts/evaluate-chickenbro-research.py'
        tree = ast.parse(source.read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_load_cases')
        namespace = {'json': json, 'Any': typing.Any,
                     'DEFAULT_CASES_PATH': ROOT / 'tests/fixtures/chickenbro-research-cases.json'}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        return namespace['_load_cases'](selected)

    def test_default_remains_original_three(self):
        self.assertEqual([case['id'] for case in self.load_cases([])], [
            'original-enhancement-crit', 'variant-enhancement-secondary-stats', 'simple-class-question'])

    def test_explicit_multi_turn_case_rejected(self):
        with self.assertRaisesRegex(ValueError, 'multi-turn'):
            self.load_cases(['context-correction'])

    def test_explicit_new_single_turn_case_allowed(self):
        self.assertEqual(self.load_cases(['version-ambiguous'])[0]['id'], 'version-ambiguous')


if __name__ == '__main__':
    unittest.main()

"""Retirement recovery journal must survive a fault between side effect and receipt."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'artifacts/verification/2026-10-16-retire-legacy-qq/cloud_cleanup.py'
spec = importlib.util.spec_from_file_location('legacy_qq_cleanup', SCRIPT)
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class CleanupJournalTests(unittest.TestCase):
    def test_side_effect_fault_leaves_intent_and_resumes_without_repeating_deletion(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(cleanup, 'ROOT', Path(tmp)):
            resource = Path(tmp) / 'resource'
            resource.write_text('old product')
            progress = {'done': [], 'intent': None}
            def interrupted():
                resource.unlink()
                raise RuntimeError('injected receipt fault')
            with self.assertRaises(RuntimeError):
                cleanup.operation(progress, 'resource', interrupted)
            persisted = json.loads((Path(tmp) / 'apply-progress.json').read_text())
            self.assertEqual(persisted, {'done': [], 'intent': 'resource'})
            cleanup.operation(persisted, 'resource', lambda: resource.unlink(missing_ok=True))
            self.assertEqual(persisted, {'done': ['resource'], 'intent': None})

    def test_completed_step_does_not_repeat_destructive_action(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(cleanup, 'ROOT', Path(tmp)):
            progress = {'done': [], 'intent': None}
            calls = []
            cleanup.operation(progress, 'step', lambda: calls.append('removed'))
            cleanup.operation(progress, 'step', lambda: calls.append('removed'))
            self.assertEqual(calls, ['removed'])
            self.assertEqual(json.loads((Path(tmp) / 'apply-progress.json').read_text()), progress)

    def test_same_name_replacement_container_is_never_a_retirement_target(self):
        saved = {'Id': 'original-id', 'Image': 'original-image'}
        for current in [
            {'Id': 'replacement-id', 'Image': 'original-image', 'State': {'Running': False}},
            {'Id': 'original-id', 'Image': 'replacement-image', 'State': {'Running': False}},
            {'Id': 'original-id', 'Image': 'original-image', 'State': {'Running': True}},
        ]:
            with self.subTest(current=current), self.assertRaises(AssertionError):
                cleanup.verify_container(saved, current)
        cleanup.verify_container(saved, {**saved, 'State': {'Running': False}})

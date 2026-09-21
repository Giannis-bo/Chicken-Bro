"""Cloud-only real engine acceptance against independently exported upstream fixtures."""
import json
import os
from pathlib import Path
import unittest


@unittest.skipUnless(os.environ.get('POE2_FIXTURE_DIR'), 'cloud engine fixture directory required')
class CloudPobTests(unittest.TestCase):
    def test_engine_child_cannot_create_network_socket(self):
        import subprocess
        import sys
        from server.app.poe2 import engine
        child = subprocess.run([sys.executable, str(Path(engine.__file__).with_name('engine_runner.py')),
            sys.executable, '-c', 'import socket; socket.socket()'], capture_output=True, text=True)
        self.assertNotEqual(child.returncode, 0)
        self.assertIn('Operation not permitted', child.stderr)

    def test_import_roundtrip_and_direct_upstream_parity(self):
        from server.app.poe2.engine import PobEngine
        from server.app.poe2.application import validate_result
        fixtures = Path(os.environ['POE2_FIXTURE_DIR'])
        engine = PobEngine()
        for source in sorted(fixtures.glob('build-*.xml')):
            with self.subTest(source=source.name):
                expected = json.loads(source.with_suffix('.json').read_text())
                result = engine.calculate(source.read_text())
                validate_result(result)
                for key, value in expected['stats'].items():
                    if isinstance(value, (int, float)):
                        self.assertAlmostEqual(result['stats'][key], value, places=5)
                again = engine.calculate(result['exportCode'])
                self.assertEqual(result['stats'], again['stats'])

    def test_equipment_changes_are_effective_and_next_job_is_clean(self):
        from server.app.poe2.engine import PobEngine
        source = (Path(os.environ['POE2_FIXTURE_DIR']) / 'build-1.xml').read_text()
        engine = PobEngine()
        original = engine.calculate(source)
        changed = engine.calculate(source, {'items': [{'slot': 'Ring 1', 'text':
            'Rarity: Rare\nTest Ring\nGold Ring\n--------\n+50 to maximum Life'}]})
        self.assertGreater(changed['stats']['Life'], original['stats']['Life'])
        restored = engine.calculate(source)
        self.assertEqual(original['stats'], restored['stats'])

    def test_skill_replacement_changes_damage_and_roundtrips(self):
        from server.app.poe2.engine import PobEngine
        source = (Path(os.environ['POE2_FIXTURE_DIR']) / 'build-1.xml').read_text()
        engine = PobEngine()
        original = engine.calculate(source)
        changed = engine.calculate(source, {'skillGroups': [{'index': 1, 'gems': [
            {'name': 'Spark', 'level': 15, 'quality': 0}]}]})
        self.assertNotEqual(original['stats']['CombinedDPS'], changed['stats']['CombinedDPS'])
        self.assertEqual(changed['skills'][0]['gems'][0]['name'], 'Spark')
        again = engine.calculate(changed['exportCode'])
        self.assertEqual(changed['stats'], again['stats'])
        self.assertIsInstance(changed['effectiveConfig'], dict)

    def test_passive_allocation_and_removal_use_real_connected_tree(self):
        from server.app.poe2.engine import PobEngine
        fixtures = Path(os.environ['POE2_FIXTURE_DIR'])
        node = json.loads((fixtures / 'build-1.json').read_text())['reachableNode']
        self.assertIsInstance(node, int)
        engine = PobEngine()
        original = engine.calculate((fixtures / 'build-1.xml').read_text())
        changed = engine.calculate(original['exportCode'], {'allocateNodes': [node]})
        self.assertIn(node, changed['allocatedNodes'])
        restored = engine.calculate(changed['exportCode'], {'deallocateNodes': [node]})
        self.assertNotIn(node, restored['allocatedNodes'])
        self.assertEqual(original['stats'], restored['stats'])


if __name__ == '__main__':
    unittest.main()

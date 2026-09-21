"""Offline cloud-only regression for supervisor stdout completion."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class SupervisorOutputTest(unittest.TestCase):
    def test_exited_worker_stdout_is_drained_to_complete_large_json(self):
        supervisor = Path(__file__).resolve().parents[1] / 'server/poe2_source_supervisor.py'
        node = '/opt/chickenbro-candidates/poe2-20260918/runtime/node-v22.19.0-linux-x64/bin/node'
        with tempfile.TemporaryDirectory(prefix='poe2-r4-') as directory:
            worker = Path(directory) / 'large.cjs'
            worker.write_text(
                "process.stdout.write(JSON.stringify({ok:true,snapshot:{"
                "text:'x'.repeat(227303),tail:'complete'}})+'\\n');"
            )
            # Force pipe reads smaller than its capacity and yield after each.
            # The writer exits while its final buffered chunks remain unread;
            # the old poll()-based early exit reproducibly truncates the JSON.
            harness = '''
import os, runpy, sys, time
original_read = os.read
def slow_read(fd, size):
    part = original_read(fd, min(size, 1024))
    if part:
        time.sleep(0.005)
    return part
os.read = slow_read
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name='__main__')
'''
            completed = subprocess.run(
                [sys.executable, '-c', harness, str(supervisor), '5000', node, str(worker)],
                input='{}\n', text=True, capture_output=True, timeout=7,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertTrue(result['ok'])
            self.assertEqual(result['snapshot']['text'], 'x' * 227303)
            self.assertEqual(result['snapshot']['tail'], 'complete')


if __name__ == '__main__':
    unittest.main()

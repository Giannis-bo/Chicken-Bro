import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from server.app.simulation.readiness import ManagedSimcRuntimeError, ManagedSimcRuntimeIdentity


class SimulationRuntimeInfoTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.binary = Path(self.temp.name) / 'simc'
        self.binary.write_bytes(b'fake binary; never execute locally')
        self.identity = ManagedSimcRuntimeIdentity(self.binary, 'a' * 40, 'b' * 64, 'simc:managed:' + 'a' * 40 + ':' + 'b' * 64)

    def test_verified_binary_banner_is_exposed_and_cached(self):
        from server.app.simulation.runtime import get_simc_runtime_info
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
            kwargs['stdout'].write(b'Nothing to sim! SimulationCraft 1210-01 for World of Warcraft 12.1.0.69299 Live\n')
            return SimpleNamespace(returncode=1)
        with patch('server.app.simulation.runtime.inspect_managed_simc_runtime', return_value=self.identity), patch('server.app.simulation.runtime.subprocess.run', side_effect=runner):
            result = get_simc_runtime_info({})
            result2 = get_simc_runtime_info({})
        self.assertEqual(result['version'], '1210-01')
        self.assertEqual(result['gameVersion'], '12.1.0.69299')
        self.assertEqual(result['build'], '69299')
        self.assertEqual(result['status'], 'available')
        self.assertEqual(result['sourceCommit'], 'a' * 40)
        self.assertEqual(result2, result)
        self.assertEqual(len(calls), 1)
        self.assertEqual(set(result), {'status', 'version', 'gameVersion', 'build', 'sourceCommit', 'runtimeRevision'})

    def test_invalid_identity_and_revision_never_probe_binary(self):
        from server.app.simulation.runtime import get_simc_runtime_info
        with patch('server.app.simulation.runtime.inspect_managed_simc_runtime', side_effect=ManagedSimcRuntimeError('SIMC_IDENTITY_INVALID')):
            result = get_simc_runtime_info({})
        self.assertEqual(result['status'], 'unavailable')
        self.assertIsNone(result['version'])
        with patch('server.app.simulation.runtime.inspect_managed_simc_runtime', return_value=self.identity):
            self.assertEqual(get_simc_runtime_info({'WOW_SIMC_RUNTIME_REVISION': 'wrong'})['status'], 'unavailable')

    def test_probe_timeout_and_missing_banner_remain_unavailable(self):
        from server.app.simulation.runtime import get_simc_runtime_info
        for case in ('timeout', 'invalid', 'oversized'):
            def runner(args, **kwargs):
                if case == 'timeout': raise subprocess.TimeoutExpired('simc', 3)
                kwargs['stdout'].write((b'X' * 9000) if case == 'oversized' else b'hash-only')
                return SimpleNamespace(returncode=0)
            with self.subTest(case=case), patch('server.app.simulation.runtime.inspect_managed_simc_runtime', return_value=self.identity), patch('server.app.simulation.runtime.subprocess.run', side_effect=runner):
                self.assertEqual(get_simc_runtime_info({})['status'], 'unavailable')


if __name__ == '__main__': unittest.main()

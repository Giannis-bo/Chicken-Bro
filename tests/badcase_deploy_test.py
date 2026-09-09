import importlib.util
from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('badcase_deploy', Path(__file__).resolve().parents[1] / 'scripts/badcase_deploy.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.r = object.__new__(d.Release)
        r = self.r
        r.base, r.target, r.web, r.overlay = (self.root / n for n in ('base', 'target', 'web', 'overlay'))
        for p in (r.base, r.web, r.overlay):
            p.mkdir()
        self.name = next(iter(sorted(d.ALLOWED)))
        for root, value in ((r.base, 'old'), (r.overlay, 'new')):
            file = root / self.name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(value)
        (r.base / 'unchanged').write_text('keep')
        (r.web / 'index.html').write_text('web')
        r.link, r.web_link = self.root / 'source', self.root / 'current'
        r.link.symlink_to(r.base)
        r.web_link.symlink_to(r.web)
        r.m = {'sourceCommit': 'a' * 40, 'baseInventory': d.inventory(r.base),
               'files': d.inventory(r.overlay), 'webFiles': d.inventory(r.web)}
        r.m['baseHashes'] = {self.name: r.m['baseInventory'][self.name]}
        r.envs = {}

    def test_stage_exact_copy_and_web_unchanged(self):
        self.r.stage()
        self.r.staged()
        self.assertEqual((self.r.target / self.name).read_text(), 'new')
        self.assertEqual((self.r.base / self.name).read_text(), 'old')
        self.assertEqual(self.r.web_link.resolve(), self.r.web)
        self.r.stage()  # exact rerun is idempotent

    def test_stage_rejects_hash_drift_and_unlisted_payload(self):
        (self.r.overlay / 'extra').write_text('unexpected')
        with self.assertRaisesRegex(RuntimeError, 'overlay inventory drift'):
            self.r.stage()
        (self.r.overlay / 'extra').unlink()
        (self.r.base / 'unchanged').write_text('changed')
        with self.assertRaisesRegex(RuntimeError, 'base inventory drift'):
            self.r.stage()

    def test_inventory_rejects_symlinks_even_inside_cache(self):
        cache = self.r.base / '__pycache__'
        cache.mkdir()
        (cache / 'escape').symlink_to('/etc')
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            d.inventory(self.r.base)

    def test_scoped_rejects_traversal_and_symlinks(self):
        for name in ('../secret', '/tmp/secret', 'a/../b', './x', 'a//b'):
            with self.assertRaises(RuntimeError):
                d.scoped(self.root, name)
        (self.root / 'escape').symlink_to('/tmp')
        with self.assertRaises(RuntimeError):
            d.scoped(self.root, 'escape/x')

    def test_web_and_pointer_drift_block_activation_before_stop(self):
        self.r.stage()
        (self.r.web / 'index.html').write_text('drift')
        with patch.object(self.r, 'idle_fence', self.fence), patch.object(d, 'service') as service:
            with self.assertRaisesRegex(RuntimeError, 'Web inventory drift'):
                self.r.activate(self.r.base, self.r.target)
            service.assert_not_called()

    @contextmanager
    def fence(self):
        yield Mock()

    def test_activation_stop_order_and_verify(self):
        self.r.stage()
        events = []
        with patch.object(self.r, 'idle_fence', self.fence), \
             patch.object(self.r, 'active', return_value={'chat': 0}), \
             patch.object(d, 'service', side_effect=lambda *a: events.append(a)), \
             patch.object(self.r, 'start', side_effect=lambda: events.append('start')), \
             patch.object(self.r, 'verify') as verify:
            self.r.activate(self.r.base, self.r.target)
        self.assertEqual(events, [('stop', 'chickenbro-api'), ('stop', 'chickenbro-worker'), 'start'])
        verify.assert_called_once_with(self.r.target)
        self.assertEqual(self.r.link.resolve(), self.r.target)

    def test_readiness_failure_triggers_fenced_base_recovery(self):
        self.r.stage()
        with patch.object(self.r, 'idle_fence', self.fence), \
             patch.object(self.r, 'active', return_value={'chat': 0}), \
             patch.object(d, 'service'), patch.object(self.r, 'start'), \
             patch.object(self.r, 'verify', side_effect=[RuntimeError('not ready'), None]) as verify:
            with self.assertRaisesRegex(RuntimeError, 'base recovery verified'):
                self.r.promote()
        self.assertEqual(self.r.link.resolve(), self.r.base)
        self.assertEqual(verify.call_count, 2)

    def test_busy_recovery_never_stops_or_switches_again(self):
        self.r.stage()
        calls = []
        @contextmanager
        def gate():
            calls.append('gate')
            if len(calls) == 2:
                raise RuntimeError('active task')
            yield Mock()
        with patch.object(self.r, 'idle_fence', gate), \
             patch.object(self.r, 'active', return_value={'chat': 0}), \
             patch.object(d, 'service') as service, patch.object(self.r, 'start'), \
             patch.object(self.r, 'verify', side_effect=RuntimeError('not ready')):
            with self.assertRaisesRegex(RuntimeError, 'recovery unsafe or failed'):
                self.r.promote()
        self.assertEqual(service.call_count, 2)
        self.assertEqual(self.r.link.resolve(), self.r.target)

    def test_active_queries_include_durable_execution_pending(self):
        conn = Mock()
        conn.execute.return_value.fetchone.return_value = (0,)
        self.r.active(conn)
        queries = '\n'.join(c.args[0] for c in conn.execute.call_args_list)
        self.assertIn("chat.executions WHERE stage IN ('pending','queued','running')", queries)

    def test_idle_wait_releases_transaction_and_times_out_without_stop(self):
        conn = Mock()
        @contextmanager
        def connect():
            yield conn
        self.r.connect = connect
        with patch.object(self.r, 'active', return_value={'executions': 1}), \
             patch.object(d.time, 'monotonic', side_effect=[0, 1, 120]), \
             patch.object(d, 'service') as service:
            with self.assertRaisesRegex(RuntimeError, 'active tasks'):
                with self.r.idle_fence():
                    self.fail('busy fence yielded')
            service.assert_not_called()

    def test_manifest_rejects_unauthorized_files(self):
        m = {**self.r.m, 'expectedBackend': '/opt/chickenbro-releases/base',
             'expectedWeb': '/var/www/chickenbro-web/releases/base'}
        m['files'] = {'server/app/api/routes/source_gateway.py': 'a' * 64}
        p = self.root / 'manifest.json'
        p.write_text(json.dumps(m))
        with self.assertRaisesRegex(RuntimeError, 'allowlist'):
            d.Release(p)

    def test_worker_listener_failure_never_starts_api(self):
        self.r.envs = {'chickenbro-worker': {'WOW_CHAT_WORKER_TOOL_PORT': '18794'}}
        commands = []
        def output(args, **kwargs):
            commands.append(args)
            return '42' if args[0] == 'systemctl' else 'no listener'
        with patch.object(d, 'service') as service, \
             patch.object(d.subprocess, 'check_output', side_effect=output), \
             patch.object(d.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'worker listener failed'):
                self.r.start()
        service.assert_called_once_with('start', 'chickenbro-worker')
        self.assertTrue(any('sport = :18794' in args for args in commands))

    def test_existing_staged_target_tamper_is_rejected(self):
        self.r.stage()
        (self.r.target / self.name).write_text('tampered')
        with self.assertRaisesRegex(RuntimeError, 'target inventory drift'):
            self.r.stage()
        self.assertEqual(self.r.link.resolve(), self.r.base)

    def recovery_fixture(self):
        self.r.path = self.root / 'manifest.json'
        self.r.envs = {u: {'WOW_DATABASE_URL': 'private-test-db', 'X': u} for u in d.UNITS}
        self.r.m['environmentHashes'] = {u: d.env_digest(e) for u, e in self.r.envs.items()}
        self.r.path.write_text(json.dumps(self.r.m))
        self.r.connect = Mock()

    def test_external_rollback_uses_snapshot_for_crashed_service(self):
        self.recovery_fixture()
        self.r.stage()
        expected_envs = self.r.envs.copy()
        with patch.object(d, 'require_private'):
            self.r.save_recovery()
            d.switch(self.r.link, self.r.target)
            self.r.envs = None
            def live(unit):
                if unit == d.UNITS[0]:
                    raise d.ServiceUnavailable('crashed')
                return expected_envs[unit]
            with patch.object(d, 'environment', side_effect=live), \
                 patch.object(self.r, 'activate') as activate:
                self.r.run('rollback')
            self.assertEqual(self.r.envs, expected_envs)
            activate.assert_called_once_with(self.r.target, self.r.base)

    def test_corrupt_target_does_not_prevent_base_recovery(self):
        self.r.stage()
        d.switch(self.r.link, self.r.target)
        (self.r.target / self.name).write_text('corrupt')
        with patch.object(self.r, 'idle_fence', self.fence), \
             patch.object(self.r, 'active', return_value={'chat': 0}), \
             patch.object(d, 'service'), patch.object(self.r, 'start'), \
             patch.object(self.r, 'verify'):
            self.r.activate(self.r.target, self.r.base)
        self.assertEqual(self.r.link.resolve(), self.r.base)

    def test_snapshot_rejects_hash_identity_drift_without_overwrite(self):
        self.recovery_fixture()
        with patch.object(d, 'require_private'):
            self.r.save_recovery()
            snapshot = self.r.recovery_path()
            before = snapshot.read_bytes()
            self.r.m['sourceCommit'] = 'b' * 40
            self.r.path.write_text(json.dumps(self.r.m))
            with self.assertRaisesRegex(RuntimeError, 'identity mismatch'):
                self.r.save_recovery()
            self.assertEqual(snapshot.read_bytes(), before)

    def test_snapshot_rejects_symlink_and_private_metadata_errors(self):
        self.recovery_fixture()
        with patch.object(d, 'require_private'):
            path = self.r.recovery_path()
            path.symlink_to(self.r.path)
            with self.assertRaises(OSError):
                self.r.read_recovery()
        from types import SimpleNamespace
        for uid, mode, nlink in ((501, 0o100600, 1), (0, 0o100644, 1), (0, 0o100600, 2)):
            with self.assertRaises(RuntimeError):
                d.require_private(SimpleNamespace(st_uid=uid, st_mode=mode, st_nlink=nlink))
        d.require_private(SimpleNamespace(st_uid=0, st_mode=0o100600, st_nlink=1))

    def test_snapshot_rejects_environment_tampering(self):
        self.recovery_fixture()
        with patch.object(d, 'require_private'):
            self.r.save_recovery()
            path = self.r.recovery_path()
            record = json.loads(path.read_text())
            record['environments'][d.UNITS[0]]['X'] = 'changed'
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(RuntimeError, 'environment hash mismatch'):
                self.r.read_recovery()

    def test_environment_hash_preserves_non_app_config(self):
        self.assertEqual(d.env_digest({'X': '1', 'INVOCATION_ID': 'old'}),
                         d.env_digest({'X': '1', 'INVOCATION_ID': 'new'}))
        self.assertNotEqual(d.env_digest({'X': '1'}), d.env_digest({'X': '2'}))


if __name__ == '__main__':
    unittest.main()

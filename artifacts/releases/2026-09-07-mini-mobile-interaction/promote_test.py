import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('promote', Path(__file__).with_name('promote.py'))
promote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(promote)


class PromotionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        self.code = root / 'chickenbro'; self.code.mkdir()
        (self.code / 'old.py').write_text('old')
        self.old_web = root / 'old-web'; self.old_web.mkdir()
        self.web = root / 'current'; self.web.symlink_to(self.old_web)
        self.commit = 'a' * 40
        self.payload = root / 'releases' / self.commit; self.payload.mkdir(parents=True)
        for name, text in {'server/app/main.py': 'api', 'server/app/worker/main.py': 'worker',
            'web/index.html': 'web', 'weapp/app.json': '{}',
            'weapp/wow-build.json': json.dumps({'gitHead': self.commit}), 'BRANCH_COMMIT': self.commit}.items():
            target = self.payload / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(text)
        self.manifest = {'commit': self.commit, 'files': promote.inventory(self.payload),
            'previousWeb': str(self.old_web), 'previousCodeHash': promote.digest(promote.inventory(self.code))}
        self.conf = root / 'release.env'
        self.dropins = [root / 'api.d' / 'release.conf', root / 'worker.d' / 'release.conf']
        for name, value in {'RELEASES': root / 'releases', 'CODE': self.code, 'WEB': self.web,
                            'CONF': self.conf, 'DROPINS': self.dropins}.items():
            p = patch.object(promote, name, value); p.start(); self.addCleanup(p.stop)
        for name, value in {'run': '', 'active_jobs': 0, 'ready': True}.items():
            p = patch.object(promote, name, return_value=value); setattr(self, name, p.start()); self.addCleanup(p.stop)
        p = patch.object(promote.os, 'geteuid', return_value=0); p.start(); self.addCleanup(p.stop)

    def test_dry_run_does_not_change_live_paths_or_config(self):
        self.assertEqual(promote.promote(self.manifest, self.payload)['status'], 'dry_run')
        self.assertFalse(self.code.is_symlink()); self.assertEqual(self.web.resolve(), self.old_web)
        self.assertFalse(self.conf.exists()); self.run.assert_not_called()

    def test_modified_payload_and_production_fail_before_mutation(self):
        (self.payload / 'web/index.html').write_text('changed')
        with self.assertRaises(ValueError): promote.promote(self.manifest, self.payload, True)
        (self.payload / 'web/index.html').write_text('web'); (self.code / 'old.py').write_text('changed')
        with self.assertRaises(ValueError): promote.promote(self.manifest, self.payload, True)
        self.run.assert_not_called(); self.assertFalse(self.conf.exists())

    def test_active_work_and_existing_config_fail_closed(self):
        self.active_jobs.return_value = 1
        with self.assertRaises(ValueError): promote.promote(self.manifest, self.payload, True)
        self.active_jobs.return_value = 0; self.conf.write_text('existing')
        with self.assertRaises(ValueError): promote.promote(self.manifest, self.payload, True)
        self.assertEqual(self.conf.read_text(), 'existing'); self.run.assert_not_called()

    def test_success_preserves_verified_old_code_and_switches_exact_paths(self):
        result = promote.promote(self.manifest, self.payload, True)
        self.assertEqual(result['status'], 'code_web_promoted')
        self.assertEqual(self.code.resolve(), self.payload); self.assertEqual(self.web.resolve(), self.payload / 'web')
        self.assertEqual((Path(result['rollbackCode']) / 'old.py').read_text(), 'old')
        self.assertIn('WOW_TEST_LOGIN_ENABLED=0', self.conf.read_text())

    def test_failed_start_restores_original_code_web_and_config(self):
        def run(*args):
            if args[:2] == ('systemctl', 'start'): raise RuntimeError('start failed')
            return ''
        self.run.side_effect = run
        with self.assertRaises(RuntimeError): promote.promote(self.manifest, self.payload, True)
        self.assertFalse(self.code.is_symlink()); self.assertEqual((self.code / 'old.py').read_text(), 'old')
        self.assertEqual(self.web.resolve(), self.old_web); self.assertFalse(self.conf.exists())
        self.assertFalse(any(p.exists() for p in self.dropins))

    def test_dangling_pending_link_fails_before_services_stop(self):
        pending = self.web.with_name(self.web.name + '.release-next')
        pending.symlink_to(self.payload / 'missing')
        with self.assertRaises(ValueError): promote.promote(self.manifest, self.payload, True)
        self.run.assert_not_called(); self.assertFalse(self.conf.exists())
        self.assertTrue(pending.is_symlink())

    def test_link_replace_failure_cleans_owned_pending_and_recovers_services(self):
        original_replace = Path.replace
        def fail_pending(path, target):
            if path.name.endswith('.release-next'): raise OSError('rename failed')
            return original_replace(path, target)
        with patch.object(Path, 'replace', fail_pending):
            with self.assertRaises(OSError): promote.promote(self.manifest, self.payload, True)
        pending = self.web.with_name(self.web.name + '.release-next')
        self.assertFalse(pending.is_symlink()); self.assertFalse(self.code.is_symlink())
        self.assertEqual((self.code / 'old.py').read_text(), 'old')
        self.assertEqual(self.web.resolve(), self.old_web); self.assertFalse(self.conf.exists())
        self.assertIn(unittest.mock.call('systemctl', 'restart', *promote.UNITS), self.run.call_args_list)


if __name__ == '__main__': unittest.main()

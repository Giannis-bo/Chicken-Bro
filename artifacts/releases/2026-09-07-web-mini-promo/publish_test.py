"""Exercise archive permissions and failure recovery without remote side effects."""
import hashlib
import importlib.util
import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('publish', Path(__file__).with_name('publish.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

class PublishTest(unittest.TestCase):
    def test_stage_preserves_executable_mode(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d).resolve()
            archive = base / 'payload.tgz'
            with tarfile.open(archive, 'w:gz') as tar:
                for name in ('server/update.sh', 'web/index.html'):
                    info = tarfile.TarInfo(name)
                    info.size = 4
                    tar.addfile(info, io.BytesIO(b'test'))
            manifest = {'files': {n: hashlib.sha256(b'test').hexdigest() for n in ('server/update.sh', 'web/index.html')}, 'modes': {'server/update.sh': 0o755, 'web/index.html': 0o644}, 'archiveSha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'previewLinks': {}}
            with patch.object(p, 'validate'):
                p.stage(manifest, archive, base / 'release')
            self.assertEqual((base / 'release/server/update.sh').stat().st_mode & 0o7777, 0o755)
            self.assertEqual((base / 'release/web/index.html').stat().st_mode & 0o7777, 0o644)
            self.assertEqual(p.files(base / 'release'), manifest['files'])

    def test_switch_cleans_own_pending_link_on_failure(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d).resolve()
            target = base / 'old'
            target.mkdir()
            link = base / 'current'
            link.symlink_to(target)
            with patch.object(Path, 'replace', side_effect=OSError('injected')):
                with self.assertRaises(OSError):
                    p.switch(link, base / 'new')
            self.assertEqual(link.resolve(), target)
            self.assertFalse((base / 'current.brand-next').is_symlink())

    def test_rollback_failure_does_not_skip_config_or_services(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d).resolve()
            code, web = base / 'code', base / 'web'
            old_code, old_web = base / 'old-code', base / 'old-web'
            old_code.mkdir(); old_web.mkdir()
            code.symlink_to(old_code); web.symlink_to(old_web)
            dropins = tuple(base / (u + '.d') / 'release.conf' for u in p.UNITS)
            manifest = {'commit': 'a'*40, 'previousCode': str(old_code), 'previousWeb': str(old_web), 'migrations': ['migration']}
            calls = []
            def run(*args):
                calls.append(args)
                return 'migration' if args[0] == 'sudo' else ''
            def switch(link, target):
                if link == code:
                    raise OSError('injected pointer failure')
            with patch.multiple(p, CODE=code, WEB=web, DROPINS=dropins), patch.object(p, 'validate'), patch.object(p, 'ready', return_value=True), patch.object(p, 'active_jobs', return_value=0), patch.object(p, 'run', side_effect=run), patch.object(p, 'switch', side_effect=switch):
                with self.assertRaisesRegex(RuntimeError, 'rollback needs attention'):
                    p.promote(manifest, base / 'new', True)
            self.assertTrue(all(not path.exists() for path in dropins))
            self.assertIn(('systemctl', 'daemon-reload'), calls)
            for unit in p.UNITS:
                self.assertIn(('systemctl', 'restart', unit), calls)

if __name__ == '__main__':
    unittest.main()

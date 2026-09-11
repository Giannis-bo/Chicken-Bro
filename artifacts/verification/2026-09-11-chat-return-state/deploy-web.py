"""Exact-manifest static Web release; no API, worker or database mutation."""
import hashlib
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import threading
import urllib.request

mode, manifest_path = sys.argv[1:]
manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8-sig'))
current = Path('/var/www/chickenbro-web/current')
target = Path(manifest['target'])
baseline = Path(manifest['baseline'])
packet = Path(manifest_path).parent
assert target.parent == Path('/var/www/chickenbro-web/releases')
assert baseline.parent == target.parent and baseline.is_dir()

def inventory(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob('*')) if p.is_file()}

def report(data):
    (packet / (mode + '-result.json')).write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(data))

if mode == 'stage':
    assert current.resolve() == baseline
    assert str(Path('/opt/chickenbro').resolve()) == manifest['backend']
    assert not target.exists(), 'Never overwrite an existing release'
    previous = inventory(baseline)
    (packet / 'baseline-inventory.json').write_text(json.dumps(previous, indent=2))
    with tarfile.open(packet / 'web.tar.gz') as archive:
        members = [m for m in archive.getmembers() if m.isfile()]
        names = [m.name.removeprefix('./') for m in members]
        assert set(names) == set(manifest['files']) and len(names) == len(set(names))
        target.mkdir()
        for member, name in zip(members, names):
            file = target / name
            assert target in file.resolve().parents
            data = archive.extractfile(member).read()
            assert hashlib.sha256(data).hexdigest() == manifest['files'][name]
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
            file.chmod(0o644)
    assert inventory(target) == manifest['files']
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(target), **kwargs)
        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for name, digest in manifest['files'].items():
            data = urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/{name}', timeout=20).read()
            assert hashlib.sha256(data).hexdigest() == digest
    finally:
        server.shutdown()
        server.server_close()
    assert inventory(baseline) == previous
    report({'status': 'staged_verified', 'files': len(manifest['files']), 'current': str(current.resolve()), 'target': str(target), 'httpVerification': 'isolated-loopback-static-files'})
elif mode in ('promote', 'rollback'):
    old, new = (baseline, target) if mode == 'promote' else (target, baseline)
    assert current.is_symlink() and current.resolve() == old
    assert inventory(target) == manifest['files']
    assert inventory(baseline) == json.loads((packet / 'baseline-inventory.json').read_text())
    assert str(Path('/opt/chickenbro').resolve()) == manifest['backend']
    temporary = current.with_name('current-chat-return-' + manifest['sourceCommit'][:12])
    assert not temporary.exists() and not temporary.is_symlink()
    temporary.symlink_to(new)
    os.replace(temporary, current)
    assert current.resolve() == new
    report({'status': mode + '_complete', 'web': str(current.resolve()), 'backend': str(Path('/opt/chickenbro').resolve()), 'previousPreserved': True, 'sourceCommit': manifest['sourceCommit']})
else:
    raise ValueError('Unknown mode')

"""Build this release manifest from pinned source and live identities; cloud only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys

commit = sys.argv[1]
assert re.fullmatch('[0-9a-f]{40}', commit)
root = Path('/var/lib/chickenbro-research-player-identity-20260917')
source = Path('/opt/chickenbro-candidates/research-player-identity-20260917')
files = ['server/app/chickenbro/research_budget.py']
p = root / 'deploy.py'
s = p.read_text()
s, replaced = re.subn(r'^ALLOWED = .*$', 'ALLOWED = frozenset(' + repr(tuple(files)) + ')', s, flags=re.M)
assert replaced == 1
p.write_text(s)
spec = importlib.util.spec_from_file_location('deploy', p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
base = Path('/opt/chickenbro').resolve()
web = Path('/var/www/chickenbro-web/current').resolve()
assert base.name == 'badcase-057378afc7b30e904b6bdd333283c93867dfb4b0'
assert web.name == 'changelog-7a457b6dab5571647af8626b182577b462b26d78'
overlay = root / 'overlay'
overlay.mkdir(exist_ok=True)
for name in files:
    dest = overlay / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / name, dest)
inventory = m.inventory(base)
manifest = {'sourceCommit': commit, 'expectedBackend': str(base), 'expectedWeb': str(web),
            'baseInventory': inventory, 'files': m.inventory(overlay),
            'baseHashes': {name: inventory.get(name) for name in files},
            'webFiles': m.inventory(web),
            'environmentHashes': {u: m.env_digest(m.environment(u)) for u in m.UNITS}}
server_files = {str(p.relative_to(source)): m.sha(p) for p in (source / 'server').rglob('*')
                if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
expected = {**inventory, **manifest['files']}
newline_only = []
for name, sha in server_files.items():
    if expected.get(name) != sha:
        assert name not in files and (base/name).is_file(), 'non-overlay server source drift'
        assert (source/name).read_bytes().replace(b'\r\n',b'\n') == (base/name).read_bytes().replace(b'\r\n',b'\n'), 'non-newline server source drift'
        newline_only.append(name)
(root / 'manifest.json').write_text(json.dumps(manifest, indent=2))
# Preserve deployed base bytes, bind those exact bytes as well as source parity.
(root / 'server-files.json').write_text(json.dumps({name:expected[name] for name in server_files}, indent=2))
(root / 'source-parity.json').write_text(json.dumps({'sourceCommit':commit, 'sourceHashes':server_files,
    'newlineOnlyBaseDifferences':newline_only, 'otherDifferences':[]}, indent=2))
print(json.dumps({'sourceCommit': commit, 'runtimeFileCount': len(server_files), 'overlayFileCount': len(files),
                  'base': str(base), 'web': str(web), 'manifestSha256': m.sha(root/'manifest.json')}))

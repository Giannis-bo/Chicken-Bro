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
root = Path('/var/lib/chickenbro-simc-repair-20261016')
source = Path('/opt/chickenbro-candidates/simc-update-20261016')
files = ['server/app/simulation/compiler.py', 'server/app/simulation/data/traits-12.1.0.json', 'server/app/simulation/data/trait-labels-12.1.0.json', 'server/app/simulation/data/trait-paths-12.1.0.json', 'server/app/simulation/data/item-variants-12.1.0.json', 'server/app/simulation/data/localization/12.1.5.70391/catalog.json.gz', 'server/app/simulation/data/localization/12.1.5.70391/engine-rules.json', 'server/app/simulation/data/localization/12.1.5.70391/manifest.json']
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
assert str(base) == json.loads((root/'baseline.json').read_text())['base']
assert str(web) == json.loads((root/'baseline.json').read_text())['web']
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
server_files = {name:digest for name,digest in {**inventory, **manifest['files']}.items() if name.startswith('server/')}
expected = {**inventory, **manifest['files']}
source_hashes = {name:m.sha(source/name) for name in files}
assert source_hashes == manifest['files']
(root / 'manifest.json').write_text(json.dumps(manifest, indent=2))
# Preserve deployed base bytes, bind those exact bytes as well as source parity.
(root / 'server-files.json').write_text(json.dumps({name:expected[name] for name in server_files}, indent=2))
(root / 'source-parity.json').write_text(json.dumps({'overlaySourceCommit':commit, 'sourceHashes':source_hashes, 'preservedBase':str(base), 'runtimeBaseHashesBound':True}, indent=2))
print(json.dumps({'sourceCommit': commit, 'runtimeFileCount': len(server_files), 'overlayFileCount': len(files),
                  'base': str(base), 'web': str(web), 'manifestSha256': m.sha(root/'manifest.json')}))

engines = {}
for commit in ['eed909156d8eccbfca0f284cc271c080949d6a20','76f8118cf3f7f41dad20708e8328e1f4ab2deebc']:
    release = Path('/opt/wow-simc/releases')/commit
    digest = m.sha(release/'simc')
    assert digest == (release/'binary.sha256').read_text().strip()
    engines[commit] = {'binarySha256':digest,'sourceArchiveSha256':(release/'source-archive.sha256').read_text().strip()}
(root/'engine-manifest.json').write_text(json.dumps(engines,indent=2))
backup = root/'old-engine-restore-copy'
backup.mkdir(exist_ok=True)
old=Path('/opt/wow-simc/releases/eed909156d8eccbfca0f284cc271c080949d6a20')
for name in ['simc','.commit','binary.sha256','source-archive.sha256']:
    if not (backup/name).exists():
        shutil.copy2(old/name,backup/name)
    assert m.sha(old/name)==m.sha(backup/name)
assert (old/'simc').stat().st_ino != (backup/'simc').stat().st_ino
print('independent old engine copy verified')

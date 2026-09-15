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
root = Path('/var/lib/chickenbro-simc-update-20260915')
source = Path('/opt/chickenbro-candidates/simc-update-20260915')
files = ['server/app/simulation/wcl_talents.py', 'server/app/simulation/data/trait-labels-12.1.0.json', 'server/app/simulation/data/item-variants-12.1.0.json', 'server/app/simulation/data/trait-paths-12.1.0.json', 'server/app/simulation/data/traits-12.1.0.json', 'server/app/simulation/data/localization/12.1.0.69814/catalog.json.gz', 'server/app/simulation/data/localization/12.1.0.69814/engine-rules.json', 'server/app/simulation/data/localization/12.1.0.69814/manifest.json', 'server/chickenbro_simc_runtime_update.sh']
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
assert base.name == 'badcase-22037c2a27c8db331e31d7a481425c97455f7c99'
assert web.name == 'chat-return-0f8b3ce9da11012e1afdcaaa5675d243ae0f8d67'
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

engines = {}
for commit in ['f50a2121bf894570146507496f3e113bff68e445','ac0f3a3c7ff9e521137c0ca1760d548330c697f3']:
    release = Path('/opt/wow-simc/releases')/commit
    digest = m.sha(release/'simc')
    assert digest == (release/'binary.sha256').read_text().strip()
    engines[commit] = {'binarySha256':digest,'sourceArchiveSha256':(release/'source-archive.sha256').read_text().strip()}
(root/'engine-manifest.json').write_text(json.dumps(engines,indent=2))
backup = root/'old-engine-restore-copy'
backup.mkdir(exist_ok=False)
old=Path('/opt/wow-simc/releases/f50a2121bf894570146507496f3e113bff68e445')
for name in ['simc','.commit','binary.sha256','source-archive.sha256']:
    shutil.copy2(old/name,backup/name)
    assert m.sha(old/name)==m.sha(backup/name)
assert (old/'simc').stat().st_ino != (backup/'simc').stat().st_ino
print('independent old engine copy verified')

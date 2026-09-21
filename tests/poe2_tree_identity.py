"""Cloud-only public artifact readback for the isolated tree Candidate."""
import hashlib
import json
from pathlib import Path
import subprocess
import httpx

ROOT = Path('/opt/chickenbro-candidates/poe2-20260918')
FILES = [
    'server/app/poe2/tree_view.lua', 'server/app/poe2/bridge.lua', 'server/app/poe2/engine.py',
    'server/app/poe2/application.py', 'server/app/api/routes/poe2.py',
    'packages/domain/src/poe2-tree.ts', 'packages/domain/src/index.ts', 'packages/api-client/src/poe2.ts',
    'apps/mini-taro/src/web/Poe2PassiveTree.tsx', 'apps/mini-taro/src/web/Poe2PassiveTree.module.scss',
    'apps/mini-taro/src/web/poe2-tree-canvas.ts', 'apps/mini-taro/src/web/WebPoe2.tsx',
    'scripts/prepare-poe2-tree-art.py',
]


def main():
    digest = lambda data: hashlib.sha256(data).hexdigest()
    source = {name: digest((ROOT / 'source' / name).read_bytes()) for name in FILES}
    files = {str(path.relative_to(ROOT / 'passive-tree-web-build')): digest(path.read_bytes())
             for path in (ROOT / 'passive-tree-web-build').rglob('*') if path.is_file()}
    with httpx.Client(timeout=30, trust_env=False) as client:
        for name, sha in files.items():
            assert digest((ROOT / 'web' / name).read_bytes()) == sha, name
            response = client.get('https://www.chickenbro.cloud/poe2-candidate/' + name)
            assert response.status_code == 200 and digest(response.content) == sha, name
    commit = subprocess.check_output(['git', '-C', str(ROOT / 'upstream/pob'), 'rev-parse', 'HEAD'], text=True).strip()
    assert commit == '7d6f530cbdab20389ff8bc6ba97a37ac27f74e41'
    art = json.loads((ROOT / 'passive-tree-art/7d6f530c/manifest.json').read_text())
    assert art['engineCommit'] == commit
    report = dict(passed=True, publicFilesMatched=len(files), engineCommit=commit, treeVersion='0_5',
                  sourceFiles=source, sourceManifestSha256=digest(json.dumps(source, sort_keys=True).encode()),
                  webFiles=files, atlasIcons=len(art['icons']), archiveSha256=art['archiveSha256'],
                  scope='poe2_candidate_only', userAcceptance='pending', recoveryDrill=False,
                  recoveryDirectory=str(ROOT / 'evidence/passive-tree'), uncommitted=True)
    (ROOT / 'evidence/passive-tree/identity.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({key: report[key] for key in ('passed', 'publicFilesMatched', 'sourceManifestSha256', 'atlasIcons', 'engineCommit')}))


if __name__ == '__main__': main()

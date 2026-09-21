"""Cloud-only source/build/public identity and translation coverage receipt."""
import hashlib
import json
from pathlib import Path
import re
import httpx
from server.app.poe2.tree_translation import translate_tree
from tests.poe2_tree_identity import FILES as TREE_FILES

ROOT = Path('/opt/chickenbro-candidates/poe2-20260918')
OUT = ROOT / 'evidence/two-step-cn'


def main():
    digest = lambda data: hashlib.sha256(data).hexdigest()
    files = sorted(set(TREE_FILES + ['server/app/poe2/repository.py', 'server/app/poe2/tree_translation.py',
        'server/app/poe2/tree-zh-CN.json', 'apps/mini-taro/src/web/WebPoe2.module.scss',
        'scripts/prepare-poe2-tree-translations.py']))
    source = {name: digest((ROOT / 'source' / name).read_bytes()) for name in files}
    web = {str(p.relative_to(ROOT / 'two-step-cn-web-build')): digest(p.read_bytes())
           for p in (ROOT / 'two-step-cn-web-build').rglob('*') if p.is_file()}
    with httpx.Client(timeout=30, trust_env=False) as client:
        for name, sha in web.items():
            assert digest((ROOT / 'web' / name).read_bytes()) == sha, name
            response = client.get('https://www.chickenbro.cloud/poe2-candidate/' + name)
            assert response.status_code == 200 and digest(response.content) == sha, name
    original = json.loads((ROOT / 'evidence/passive-tree/tree-private.json').read_text())
    translated = translate_tree(original)
    for a, b in zip(original['nodes'], translated['nodes']):
        assert {k: v for k, v in a.items() if k not in ('name', 'stats')} == {
            k: v for k, v in b.items() if k not in ('name', 'stats', 'originalName', 'originalStats')}
        assert b['originalName'] == a['name'] and b['originalStats'] == a['stats']
        assert all(not re.search(r'[A-Za-z]{3,}', line) for line in [b['name'], *b['stats']])
    assert original['edges'] == translated['edges']
    report = {'passed': True, 'publicFilesMatched': len(web), 'sourceFiles': source,
        'sourceManifestSha256': digest(json.dumps(source, sort_keys=True).encode()), 'webFiles': web,
        'translatedNodes': len(translated['nodes']), 'engineGeometryAndAllocationsPreserved': True,
        'treeVersion': original['treeVersion'], 'engineVersion': original['engineVersion'],
        'scope': 'poe2_candidate_only', 'uncommitted': True, 'userAcceptance': 'pending', 'recoveryDrill': False}
    (OUT / 'identity.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ('passed', 'publicFilesMatched', 'sourceManifestSha256', 'translatedNodes')}))


if __name__ == '__main__': main()

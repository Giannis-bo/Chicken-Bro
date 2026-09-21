"""Cloud-only source/artifact identity and public Candidate verification."""
from pathlib import Path
import hashlib
import json
import subprocess
import urllib.request

ROOT = Path('/opt/chickenbro-candidates/poe2-20260918')
SOURCE = ROOT / 'source'


def digest(data): return hashlib.sha256(data).hexdigest()


def main():
    files = {}
    for folder in ('server', 'packages', 'apps', 'tests'):
        for path in sorted((SOURCE / folder).rglob('*')):
            relative = path.relative_to(SOURCE)
            if (not path.is_file() or set(relative.parts) & {'node_modules', 'dist', '__pycache__'}
                    or path.suffix in ('.pyc', '.tsbuildinfo')):
                continue
            files[str(relative)] = digest(path.read_bytes())
    for name in ('package.json', 'package-lock.json', 'vitest.config.ts', 'tsconfig.json'):
        files[name] = digest((SOURCE / name).read_bytes())
    source_digest = digest(json.dumps(files, sort_keys=True, separators=(',', ':')).encode())
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    web = {}
    for path in sorted((ROOT / 'web').rglob('*')):
        if not path.is_file(): continue
        name = str(path.relative_to(ROOT / 'web'))
        expected = digest(path.read_bytes())
        with opener.open('https://www.chickenbro.cloud/poe2-candidate/' + name, timeout=20) as response:
            assert response.status == 200
            actual = digest(response.read())
        assert actual == expected, name
        web[name] = expected
    site = Path('/etc/nginx/sites-enabled/wow-v2-web').read_text()
    original = (ROOT / 'evidence/nginx-before-poe2.conf').read_text()
    include = '    include /etc/nginx/snippets/chickenbro-poe2-candidate.conf;\n'
    assert site.replace(include, '') == original
    for path in ('/', '/test/', '/web-candidate/'):
        with opener.open('https://www.chickenbro.cloud' + path, timeout=20) as response:
            assert response.status == 200
    for path in ('/poe2-candidate/poe2', '/poe2-candidate/simc'):
        with opener.open('https://www.chickenbro.cloud' + path, timeout=20) as response:
            assert digest(response.read()) == web['index.html']
    for name in ('project-state.json', 'backend-owner-map.json', 'project-owner-map.json'):
        json.loads((SOURCE / 'docs' / name).read_text())
    engine = subprocess.check_output(['git', '-C', str(ROOT / 'upstream/pob'), 'rev-parse', 'HEAD'], text=True).strip()
    assert engine == '7d6f530cbdab20389ff8bc6ba97a37ac27f74e41'
    report = {'baseCommit': 'fe0e398697bf31791d213a5845a0818cf54572df', 'uncommitted': True,
        'sourceManifestSha256': source_digest, 'engineCommit': engine,
        'publicFilesMatched': len(web), 'productionNginxUnchangedExceptCandidateInclude': True,
        'retainedRoutesHttp200': ['/', '/test/', '/web-candidate/'], 'sourceFiles': files, 'webFiles': web}
    (ROOT / 'evidence/delivery-identity.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k not in ('sourceFiles', 'webFiles')}, ensure_ascii=False))


if __name__ == '__main__': main()

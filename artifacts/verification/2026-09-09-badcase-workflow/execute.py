#!/usr/bin/env python3
"""Locally hash-approved entry point. Payload hashes must be frozen before approval."""
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

REPO = Path('/Users/boyuan/Documents/wow_mini_program')
ROOT = Path('/Users/boyuan/.codex/badcase/chickenbro/release')
REMOTE_ROOT = '/var/tmp/chickenbro-badcase-release-20260909'
# Operator fills the final exact digests, then freezes THIS wrapper's digest.
PAYLOAD_SHA256 = {'manifest.json': 'df45f9d9324b0bb0614f06a57f5c6d71aab3345ae984a1fc1bb8282543c92420', 'deploy.py': 'f8b5a8664abe4d4afc950eac42638d294921f14af51e8a077a114ee171b48a0b', 'execute-remote.py': 'ef19e5e675d6503e0045cb53ea659e0d983c04ef8f2293b3104f4ebc4fbd491c', 'http-smoke.py': '566fd7716a6870dc889f151630b8cf99d954e5c370c3e814a265146898089c1a', 'general-smoke.py': '172eeeceafdea5b65a4b8c7b4655c704c9e95ff022dfc41db5b8ae8d395ac0ff'}
BOOTSTRAP = r'''
import hashlib,json,os,stat,sys
from pathlib import Path
root=Path(sys.argv[1]);pins=json.loads(sys.argv[2]);mode=sys.argv[3]
assert root.absolute()==root.resolve(), 'payload directory symlink'
st=root.lstat();assert stat.S_ISDIR(st.st_mode) and st.st_uid==0 and stat.S_IMODE(st.st_mode)==0o700
blobs={}
for name,expected in pins.items():
    assert Path(name).name==name
    fd=os.open(root/name,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        st=os.fstat(f.fileno())
        assert stat.S_ISREG(st.st_mode) and st.st_uid==0 and st.st_nlink==1 and stat.S_IMODE(st.st_mode)==0o600
        data=f.read()
    assert hashlib.sha256(data).hexdigest()==expected, 'payload hash mismatch: '+name
    blobs[name]=data
request=json.load(sys.stdin)
sys.argv=[str(root/'execute-remote.py'),mode]
exec(compile(blobs['execute-remote.py'],str(root/'execute-remote.py'),'exec'),
     {'__name__':'__main__','__file__':str(root/'execute-remote.py'),
      'VERIFIED_PAYLOAD':blobs,'REQUEST_ENVELOPE':request})
'''


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_source(batch, manifest):
    source, base = batch['source_sha'], batch['baseline_sha']
    assert source == manifest['sourceCommit']
    for ref in (source, base):
        assert re.fullmatch('[0-9a-f]{40}', ref)
    # Harness/docs-only follow-up commits are allowed; the server tree is exact.
    trees = [subprocess.check_output(['git', 'rev-parse', ref + ':server'], cwd=REPO, text=True).strip()
             for ref in ('HEAD', source)]
    assert trees[0] == trees[1], 'HEAD server tree differs from approved source'
    subprocess.run(['git', 'diff', '--quiet'], cwd=REPO, check=True)
    subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=REPO, check=True)
    changed = subprocess.check_output(['git', 'diff', '--name-only', base, source, '--', 'server'], cwd=REPO, text=True).splitlines()
    assert set(changed) == set(manifest['files'])
    for path, expected in manifest['files'].items():
        assert hashlib.sha256(subprocess.check_output(['git', 'show', source + ':' + path], cwd=REPO)).hexdigest() == expected


def private_text(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(value)


def main():
    mode = sys.argv[1]
    assert mode in ('preflight', 'release')
    assert all(re.fullmatch('[0-9a-f]{64}', value) for value in PAYLOAD_SHA256.values()), 'payload digests must be frozen'
    envelope = json.load(sys.stdin)
    data = (ROOT / 'manifest.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == PAYLOAD_SHA256['manifest.json']
    validate_source(envelope['batch'], json.loads(data))
    command = shlex.join(['sudo', '/opt/chickenbro-runtime/bin/python', '-c', BOOTSTRAP,
                          REMOTE_ROOT, json.dumps(PAYLOAD_SHA256), mode])
    try:
        process = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'ControlPath=/tmp/badcase-ssh-%C', 'wow-lighthouse', command],
                                 input=json.dumps(envelope), capture_output=True, text=True, timeout=1700)
    except subprocess.TimeoutExpired as failure:
        def decoded(value):
            return value.decode(errors='replace') if isinstance(value, bytes) else value or ''
        private_text(ROOT / (mode + '-private.stdout'), decoded(failure.stdout))
        private_text(ROOT / (mode + '-private.stderr'), decoded(failure.stderr) + '\nSSH executor timeout; inspect remote recovery evidence.\n')
        raise RuntimeError('SSH executor timed out; inspect private recovery evidence') from None
    private_text(ROOT / (mode + '-private.stdout'), process.stdout)
    private_text(ROOT / (mode + '-private.stderr'), process.stderr)
    assert process.returncode == 0, 'fixed remote executor failed; inspect private recovery evidence'
    result = json.loads(process.stdout)
    assert result['batch_sha256'] == envelope['batch_sha256']
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

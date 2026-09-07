import hashlib,json,tarfile,urllib.request
from pathlib import Path
base=Path('/tmp/chickenbro-duration-2474eb314')
raw=(base/'manifest.json').read_bytes()
import sys
assert hashlib.sha256(raw).hexdigest()==sys.argv[1]
m=json.loads(raw)
archive=base/'web.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==m['archiveSha256']
assert m['commit'].startswith('2474eb314') and len(m['commit'])==40
root=Path('/var/www/chickenbro-web/releases')/('chat-duration-'+m['commit'])
current=Path('/var/www/chickenbro-web/current')
old=Path('/opt/chickenbro-releases/c8faf06322a98dc6f754ae8dbf96cfc8ba72c665/web')
assert current.is_symlink() and current.resolve()==old
assert not root.exists() and not root.is_symlink()
nextlink=current.with_name('current.chat-duration-next')
assert not nextlink.exists() and not nextlink.is_symlink()
with tarfile.open(archive,'r:gz') as tar:
    members=tar.getmembers()
    assert len(members)==len(m['files']) and {i.name for i in members}==set(m['files'])
    assert all(i.isfile() and not Path(i.name).is_absolute() and '..' not in Path(i.name).parts for i in members)
    root.mkdir(mode=0o755)
    for i in members:
        dest=root/i.name;dest.parent.mkdir(parents=True,exist_ok=True)
        data=tar.extractfile(i).read()
        assert hashlib.sha256(data).hexdigest()==m['files'][i.name]
        with dest.open('xb') as f:f.write(data)
        dest.chmod(0o644)
(root/'previews').mkdir()
(root/'previews/login-home-20260907').symlink_to('/var/www/chickenbro-web/previews/login-home-20260907-avatar-a613d6385820')
nextlink.symlink_to(root)
try:
    nextlink.replace(current)
    with urllib.request.urlopen('https://www.chickenbro.cloud/js/app.js',timeout=15) as r: actual=hashlib.sha256(r.read()).hexdigest()
    assert actual==m['files']['js/app.js']
except Exception:
    if nextlink.is_symlink():nextlink.unlink()
    nextlink.symlink_to(old);nextlink.replace(current)
    raise
finally:
    if nextlink.is_symlink():nextlink.unlink()
print(json.dumps({'status':'published','webCommit':m['commit'],'webRoot':str(root),'rollbackWeb':str(old),'jsHashVerified':True,'apiWorkerCommit':'c8faf06322a98dc6f754ae8dbf96cfc8ba72c665'}))

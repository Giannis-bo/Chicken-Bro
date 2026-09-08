import hashlib,json,sys,tarfile,urllib.request
from pathlib import Path
base=Path('/tmp/chickenbro-themes-20260908')
raw=(base/'manifest.json').read_bytes()
assert hashlib.sha256(raw).hexdigest()==sys.argv[2]
m=json.loads(raw)
current=Path('/var/www/chickenbro-web/current')
old=Path(m['expectedCurrent'])
root=Path('/var/www/chickenbro-web/releases')/('themes-'+m['commit'])
preview=Path('/var/www/chickenbro-web/previews/themes-20260908')
nextlink=current.with_name('current.themes-next')
assert current.is_symlink() and current.resolve()==old
assert not nextlink.exists() and not nextlink.is_symlink()
def check_files(target,files):
    for name,digest in files.items():assert hashlib.sha256((target/name).read_bytes()).hexdigest()==digest
if sys.argv[1]=='stage':
    for kind,target in [('web',root),('preview',preview)]:
        archive=base/(kind+'.tar.gz')
        assert hashlib.sha256(archive.read_bytes()).hexdigest()==m[kind]['archiveSha256']
        assert not target.exists() and not target.is_symlink()
        with tarfile.open(archive,'r:gz') as tar:
            entries=tar.getmembers()
            assert len(entries)==len(m[kind]['files']) and {i.name for i in entries}==set(m[kind]['files'])
            assert all(i.isfile() and not Path(i.name).is_absolute() and '..' not in Path(i.name).parts for i in entries)
            target.mkdir(mode=0o755)
            for entry in entries:
                data=tar.extractfile(entry).read()
                assert hashlib.sha256(data).hexdigest()==m[kind]['files'][entry.name]
                dest=target/entry.name;dest.parent.mkdir(parents=True,exist_ok=True)
                with dest.open('xb') as f:f.write(data)
                dest.chmod(0o644)
        check_files(target,m[kind]['files'])
    preview_link=old/'previews/themes-20260908'
    assert not preview_link.exists() and not preview_link.is_symlink()
    preview_link.symlink_to(preview)
    (root/'previews').symlink_to(old/'previews',target_is_directory=True)
    print(json.dumps({'status':'staged','root':str(root),'preview':str(preview),'commit':m['commit']}))
elif sys.argv[1]=='promote':
    check_files(root,m['web']['files'])
    nextlink.symlink_to(root)
    try:
        assert current.resolve()==old
        nextlink.replace(current)
        for name,digest in m['web']['files'].items():
            with urllib.request.urlopen('https://www.chickenbro.cloud/'+name,timeout=30) as response:
                assert hashlib.sha256(response.read()).hexdigest()==digest,name
        for path in ['', 'simc']:
            with urllib.request.urlopen('https://www.chickenbro.cloud/'+path,timeout=30) as response:
                assert hashlib.sha256(response.read()).hexdigest()==m['web']['files']['index.html']
    except Exception:
        if nextlink.is_symlink():nextlink.unlink()
        nextlink.symlink_to(old);nextlink.replace(current)
        raise
    finally:
        if nextlink.is_symlink():nextlink.unlink()
    print(json.dumps({'status':'published','root':str(root),'rollback':str(old),'commit':m['commit'],'publicFilesVerified':len(m['web']['files'])}))
else:raise ValueError('unknown mode')

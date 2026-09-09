from pathlib import Path
import json,tarfile,hashlib,subprocess
s=Path('/tmp/chickenbro-images-release');m=json.loads((s/'manifest-merged.json').read_text());archive=s/'payload-merged.tgz';assert hashlib.sha256(archive.read_bytes()).hexdigest()==m['archiveSha256']
r=Path('/opt/chickenbro-releases')/m['release'];assert not r.exists();r.mkdir(mode=0o755)
with tarfile.open(archive) as t:
 assert set(t.getnames())==set(m['files'])
 for member in t.getmembers():
  assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
 t.extractall(r,filter='data')
assert all(hashlib.sha256((r/n).read_bytes()).hexdigest()==sha for n,sha in m['files'].items())
(s/'manifest.json').write_text(json.dumps(m,indent=2));(s/'previous-source.json').write_bytes((s/'previous-source-merged.json').read_bytes())
subprocess.run(['env','IMAGE_RELEASE='+m['release'],'IMAGE_COMMIT='+m['commit'],'/opt/chickenbro-runtime/bin/python',str(s/'prepare_merged.py')],check=True)
print(json.dumps({'staged':str(r),'filesVerified':len(m['files'])}))

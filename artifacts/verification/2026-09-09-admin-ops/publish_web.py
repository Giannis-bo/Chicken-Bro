"""Exact Web-only follow-up; leaves API, Worker, admin binding and data untouched."""
import hashlib,json,os,shutil,sys
from pathlib import Path
from uuid import uuid4
import httpx
payload=Path(sys.argv[1]);m=json.loads((payload/'manifest.json').read_text());sha=m['sourceCommit']
assert len(sha)==40 and all(c in '0123456789abcdef' for c in sha)
link=Path('/var/www/chickenbro-web/current');before=link.resolve()
assert str(before)==m['expectedWeb']
target=Path('/var/www/chickenbro-web/releases/admin-ops-web-'+sha)
def inventory(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
old=inventory(before)
assert inventory(payload/'web')==m['webFiles']
if not target.exists():shutil.copytree(payload/'web',target)
assert inventory(target)==m['webFiles']
assert link.resolve()==before
new=link.with_name('.admin-web-'+uuid4().hex);new.symlink_to(target);os.replace(new,link)
with httpx.Client(base_url='https://www.chickenbro.cloud',timeout=30) as c:
 for name,digest in m['webFiles'].items():
  r=c.get('/'+name,headers={'Accept-Encoding':'identity','Cache-Control':'no-cache'})
  assert r.status_code==200 and hashlib.sha256(r.content).hexdigest()==digest,'public hash mismatch: '+name
assert inventory(before)==old
print(json.dumps({'webSourceCommit':sha,'publicFilesMatched':len(m['webFiles']),'oldWebUnchanged':True,'previousWeb':str(before),'currentWeb':str(target)}))

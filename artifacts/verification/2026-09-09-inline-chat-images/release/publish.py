import argparse,hashlib,json,tarfile,urllib.request,concurrent.futures
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--promote',action='store_true');p.add_argument('--verify',action='store_true');a=p.parse_args();base=Path('/tmp/inline-image-release');m=json.loads((base/'manifest.json').read_text());link=Path('/var/www/chickenbro-web/current');dest=link.parent/'releases'/m['release']
assert str(Path('/opt/chickenbro').resolve())==m['expectedBackend'],'Backend release changed'
if not a.verify:assert str(link.resolve())==m['previousWeb'],'Web release changed'
assert hashlib.sha256((base/'web.tgz').read_bytes()).hexdigest()==m['archiveSha256']
if not dest.exists():
 dest.mkdir(mode=0o755)
 with tarfile.open(base/'web.tgz') as t:
  assert set(t.getnames())==set(m['files'])
  assert all(x.isfile() and not Path(x.name).is_absolute() and '..' not in Path(x.name).parts for x in t.getmembers())
  t.extractall(dest,filter='data')
assert all(hashlib.sha256((dest/n).read_bytes()).hexdigest()==h for n,h in m['files'].items())
def health():
 with urllib.request.urlopen('https://www.chickenbro.cloud/api/v2/health/readiness',timeout=15) as r:assert json.load(r)['status']=='ready'
def switch(target):
 temp=link.with_name('current.inline-next');assert not temp.exists() and not temp.is_symlink();temp.symlink_to(target);temp.replace(link)
def public_verify():
 assert link.resolve()==dest
 def check(item):
  n,h=item
  with urllib.request.urlopen(urllib.request.Request('https://www.chickenbro.cloud/'+n,headers={'Cache-Control':'no-cache'}),timeout=30) as r:assert hashlib.sha256(r.read()).hexdigest()==h,n
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(check,m['files'].items()))
 health()
health()
if a.promote:
 switch(dest)
 try:public_verify()
 except BaseException:
  switch(m['previousWeb']);health();raise
elif a.verify:public_verify()
print(json.dumps({'mode':'promoted' if a.promote else 'verified' if a.verify else 'staged','sourceCommit':m['sourceCommit'],'web':str(dest),'previousWeb':m['previousWeb'],'backendUnchanged':m['expectedBackend'],'filesVerified':len(m['files']),'publicFilesVerified':len(m['files']) if a.promote or a.verify else 0,'readiness':'ready'}))

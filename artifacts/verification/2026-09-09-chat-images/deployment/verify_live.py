from pathlib import Path
import json,hashlib,subprocess,urllib.request,concurrent.futures
s=Path('/tmp/chickenbro-images-release');m=json.loads((s/'manifest.json').read_text());r=Path('/opt/chickenbro');w=Path('/var/www/chickenbro-web/current')
assert str(r.resolve())=='/opt/chickenbro-releases/'+m['release'];assert str(w.resolve())=='/var/www/chickenbro-web/releases/'+m['release']
assert all(hashlib.sha256((r/n).read_bytes()).hexdigest()==sha for n,sha in m['files'].items())
web={n[4:]:sha for n,sha in m['files'].items() if n.startswith('web/')}
def verify(item):
 n,sha=item
 with urllib.request.urlopen(urllib.request.Request('https://www.chickenbro.cloud/'+n,headers={'Cache-Control':'no-cache'}),timeout=30) as res:
  assert hashlib.sha256(res.read()).hexdigest()==sha,n
 return n
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:checked=list(pool.map(verify,web.items()))
health={}
for host in ['www.chickenbro.cloud','api.chickenbro.cloud']:
 with urllib.request.urlopen('https://'+host+'/api/v2/health/readiness',timeout=15) as res:
  state=json.load(res);assert state['status']=='ready';health[host]=state['status']
pid=subprocess.check_output(['systemctl','show','chickenbro-api','-p','MainPID','--value'],text=True).strip()
env=dict(v.split('=',1) for v in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in v)
assert env['CHICKENBRO_CHAT_IMAGES_ENABLED']=='1'
assert subprocess.check_output(['systemctl','is-active','chickenbro-image-retention.timer'],text=True).strip()=='active'
assert subprocess.check_output(['systemctl','show','chickenbro-image-retention.service','-p','Result','--value'],text=True).strip()=='success'
print(json.dumps({'sourceCommit':m['commit'],'runtimeFilesVerified':len(m['files']),'publicWebFilesVerified':len(checked),'publicReadiness':health,'imagesEnabled':True,'retentionTimer':'active','retentionLastRun':'success','previousCode':m['previousCode'],'previousWeb':m['previousWeb']}))

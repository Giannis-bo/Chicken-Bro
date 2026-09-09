import json,hashlib,os,subprocess
from pathlib import Path
from urllib.request import urlopen
m=json.loads(Path('/tmp/chickenbro-simc-release-0649a2e85/manifest.json').read_text())
root=Path('/opt/chickenbro').resolve();web=Path('/var/www/chickenbro-web/current').resolve()
assert root.name=='simc-all-'+m['sourceCommit'] and web.name==root.name
actual={str(p.relative_to(root)): ('link:'+os.readlink(p) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest()) for p in root.rglob('*') if (p.is_file() or p.is_symlink()) and '__pycache__' not in p.parts and p.suffix!='.pyc'}
assert actual=={**m['baseInventory'],**m['files']}
for name,sha in m['webFiles'].items():
 assert hashlib.sha256((web/name).read_bytes()).hexdigest()==sha
 with urlopen('https://www.chickenbro.cloud/'+name,timeout=30) as r: assert hashlib.sha256(r.read()).hexdigest()==sha,name
units={}
for unit in ['chickenbro-api','chickenbro-worker']:
 pid=subprocess.check_output(['systemctl','show',unit,'-p','MainPID','--value'],text=True).strip()
 env=dict(x.split('=',1) for x in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in x)
 assert env['WOW_SIMC_SUPPORTED_SPECS']=='all'
 assert Path('/proc/'+pid+'/cwd').resolve()==root
 units[unit]={'pid':pid,'supportedSpecs':'all','cwd':str(root)}
with urlopen('https://www.chickenbro.cloud/api/v2/health/readiness',timeout=10) as r: readiness=json.load(r)
assert readiness['status']=='ready'
print(json.dumps({'passed':True,'sourceCommit':m['sourceCommit'],'backendFileCount':len(actual),'webFilesVerifiedOverHttps':len(m['webFiles']),'units':units,'readiness':readiness}))

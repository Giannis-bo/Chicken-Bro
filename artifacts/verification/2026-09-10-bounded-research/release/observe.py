"""Read-only runtime and artifact inventory; never emits credentials."""
import json,subprocess
from pathlib import Path
from urllib.parse import urlsplit
import deploy
base=Path('/opt/chickenbro').resolve();web=Path('/var/www/chickenbro-web/current').resolve()
envs={u:deploy.environment(u) for u in deploy.UNITS}
assert all(urlsplit(e['WOW_DATABASE_URL']).path=='/chickenbro_prod' for e in envs.values())
units={}
for u in deploy.UNITS:
 pid=subprocess.check_output(['systemctl','show',u,'-p','MainPID','--value'],text=True).strip()
 assert Path('/proc/'+pid+'/cwd').resolve()==base
 paths=subprocess.check_output(['systemctl','show',u,'-p','FragmentPath','-p','DropInPaths','--value'],text=True).split()
 units[u]={'cwd':str(base),'unitFiles':{p:deploy.sha(Path(p)) for p in paths}}
print(json.dumps({'expectedBackend':str(base),'expectedWeb':str(web),'baseInventory':deploy.inventory(base),'webFiles':deploy.inventory(web),'environmentHashes':{u:deploy.env_digest(e) for u,e in envs.items()},'units':units},indent=2))

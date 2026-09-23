"""Cloud: bind actual deployed base and exact two-file overlay."""
import hashlib,importlib.util,json,os,re,shutil,sys
from pathlib import Path
os.umask(0o077)
commit=sys.argv[1];assert re.fullmatch('[0-9a-f]{40}',commit)
root=Path('/var/lib/chickenbro-badcase-wcl-window-20260923');root.mkdir(mode=0o700,exist_ok=True)
source=Path('/opt/chickenbro-candidates/badcase-wcl-window-20260923')
files=['server/app/chickenbro/wcl_source.py','server/app/chickenbro/wcl_statistics.py']
shutil.copyfile(source/'artifacts/verification/2026-09-23-badcase-wcl-window/deploy.py',root/'deploy.py')
spec=importlib.util.spec_from_file_location('deploy',root/'deploy.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
base=Path('/opt/chickenbro').resolve();web=Path('/var/www/chickenbro-web/current').resolve()
assert str(base)=='/opt/chickenbro-releases/wow-chat-context-20260921'
assert web.name=='changelog-9aa62cb3febd3dabefb0a033a1638d6830abb7d8'
overlay=root/'overlay';overlay.mkdir(exist_ok=True)
for f in files:
 dest=overlay/f;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/f,dest)
baseinv=m.inventory(base)
manifest={'sourceCommit':commit,'expectedBackend':str(base),'expectedWeb':str(web),'baseInventory':baseinv,'files':m.inventory(overlay),'baseHashes':{f:baseinv[f] for f in files},'webFiles':m.inventory(web),'environmentHashes':{u:m.env_digest(m.environment(u)) for u in m.UNITS}}
path=root/'manifest.json';assert not path.exists();path.write_text(json.dumps(manifest,indent=2))
print(json.dumps({'sourceCommit':commit,'changedFiles':manifest['files'],'manifestSha256':m.sha(path),'base':str(base),'web':str(web)}))

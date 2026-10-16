import hashlib,importlib.util,json,os,shutil,subprocess
from pathlib import Path
os.umask(0o077)
root=Path('/var/lib/chickenbro-simc-update-20261016')
s=importlib.util.spec_from_file_location('deploy',root/'deploy.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
base=Path('/opt/chickenbro').resolve();web=Path('/var/www/chickenbro-web/current').resolve();engine=Path('/opt/wow-simc/current').resolve()
assert engine.name=='eed909156d8eccbfca0f284cc271c080949d6a20'
candidate=Path('/opt/chickenbro-candidates/simc-update-20261016')
units={}
for unit in m.UNITS:
 env=m.environment(unit);pid=subprocess.check_output(['systemctl','show',unit,'-p','MainPID','--value'],text=True).strip()
 assert Path('/proc/'+pid+'/cwd').resolve()==base
 units[unit]={'pid':pid,'cwd':str(base),'environmentSha256':m.env_digest(env)}
record={'base':str(base),'web':str(web),'candidate':str(candidate),'engine':str(engine),'units':units}
assert not (root/'baseline.json').exists()
(root/'baseline.json').write_text(json.dumps(record,indent=2))
assert not candidate.exists()
shutil.copytree(base,candidate,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
shutil.copyfile('/var/lib/chickenbro-simc-update-20261009/independent-split.simc',root/'independent-split.simc')
print(json.dumps(record))

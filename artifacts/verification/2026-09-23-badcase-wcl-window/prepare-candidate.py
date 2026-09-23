import shutil,json,hashlib
from pathlib import Path
base=Path('/opt/chickenbro').resolve()
assert str(base)=='/opt/chickenbro-releases/wow-chat-context-20260921'
target=Path('/opt/chickenbro-candidates/badcase-wcl-runtime-20260923')
assert not target.exists()
shutil.copytree(base,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
source=Path('/opt/chickenbro-candidates/badcase-wcl-window-20260923')
for f in ('server/app/chickenbro/wcl_source.py','server/app/chickenbro/wcl_statistics.py'):
 shutil.copyfile(source/f,target/f)
print(json.dumps({'base':str(base),'candidate':str(target),'changedFiles':2}))

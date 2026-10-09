"""Read back and exercise the independent rollback binary without switching production."""
from pathlib import Path
import hashlib,json,subprocess,shutil
root=Path('/var/lib/chickenbro-simc-update-20261009')
copy=root/'old-engine-restore-copy'
original=Path('/opt/wow-simc/releases/ac0f3a3c7ff9e521137c0ca1760d548330c697f3')
if not copy.exists():
 shutil.copytree(original,copy)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert (copy/'simc').stat().st_ino!=(original/'simc').stat().st_ino
assert sha(copy/'simc')==sha(original/'simc')==(copy/'binary.sha256').read_text().strip()
report=root/'recovery-smoke-raw.json'
with (root/'recovery-smoke.log').open('w') as log:
 subprocess.run([str(copy/'simc'),str(root/'independent-split.simc'),'iterations=100','max_time=60','threads=1','item_db_source=local','seed=69933',f'json={report},full_states=0'],cwd=root,stdout=log,stderr=log,timeout=90,check=True)
data=json.loads(report.read_text());dps=data['sim']['players'][0]['collected_data']['dps']['mean'];assert dps>0
result={'status':'passed','sourceCommit':original.name,'binarySha256':sha(copy/'simc'),'independentCopy':True,'dps':dps,'productionRollbackDrill':False}
(root/'recovery-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

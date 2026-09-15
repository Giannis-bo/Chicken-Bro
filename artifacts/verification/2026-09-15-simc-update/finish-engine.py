"""Seal the already compiled exact source build after the recorded discovery failure."""
from pathlib import Path
import fcntl,hashlib,json,os,shutil,subprocess
root=Path('/var/lib/chickenbro-simc-update-20260915');commit='ac0f3a3c7ff9e521137c0ca1760d548330c697f3'
with open('/run/lock/chickenbro-simc-runtime-update.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert Path('/opt/wow-simc/current').resolve().name=='f50a2121bf894570146507496f3e113bff68e445'
 work=next(Path('/opt/wow-simc/work').glob('update-'+commit+'.*'));binary=work/'build/simc'
 assert '[100%] Built target simc' in (root/'build.log').read_text()
 with (root/'spell-query.log').open('w') as log:subprocess.run([str(binary),'spell_query=spell.name=Bloodlust'],stdout=log,stderr=log,check=True,timeout=60)
 release=Path('/opt/wow-simc/releases')/commit;assert not release.exists()
 stage=root/'sealed-engine';stage.mkdir()
 shutil.copyfile(binary,stage/'simc');(stage/'simc').chmod(0o755)
 bh=hashlib.sha256(binary.read_bytes()).hexdigest();ah=hashlib.sha256((work/'source.tar.gz').read_bytes()).hexdigest()
 for name,value in [('.commit',commit),('binary.sha256',bh),('source-archive.sha256',ah)]:
  (stage/name).write_text(value+'\n');(stage/name).chmod(0o644)
 stage.chmod(0o755);os.rename(stage,release)
 result=dict(status='prepared_not_promoted',sourceCommit=commit,binarySha256=bh,sourceArchiveSha256=ah)
 (root/'engine-prepared.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

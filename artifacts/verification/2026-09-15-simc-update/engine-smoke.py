"""Bounded cloud-only upstream profiles and independent talent-export proof."""
from pathlib import Path
import hashlib,json,subprocess,sys,os
os.umask(0o077)
root=Path('/var/lib/chickenbro-simc-update-20260915');source=next(Path('/opt/wow-simc/work').glob('update-ac0*/source'))
revision='ac0f3a3c7ff9e521137c0ca1760d548330c697f3';binary=Path('/opt/wow-simc/releases')/revision/'simc'
assert binary.is_file();assert hashlib.sha256(binary.read_bytes()).hexdigest()==(binary.parent/'binary.sha256').read_text().strip()
sys.path.insert(0,'/opt/chickenbro-candidates/simc-update-20260915')
from server.app.simulation.report import normalize_simc_report
from server.app.simulation.localization import catalog_for_build,localize_report
cases=[('enhancement','MID2_Shaman_Enhancement.simc'),('protection','MID2_Paladin_Protection.simc'),('affliction','MID2_Warlock_Affliction_Hellcaller.simc'),('independent',None)]
results=[]
for name,filename in cases:
 profile=(source/'profiles/MID2'/filename).read_text() if filename else (root/'independent-split.simc').read_text()
 report=root/(name+'-engine.json')
 args=[str(binary),'-','iterations=100','max_time=60','threads=1','item_db_source=local','seed=69814',f'json={report},full_states=0','report_details=1']
 if name=='enhancement':args+=['raid_events=adds,count=3,first=15,cooldown=30,duration=10']
 with (root/(name+'-engine.log')).open('w') as log:
  done=subprocess.run(args,input=profile,text=True,stdout=log,stderr=log,cwd=root,timeout=90)
 assert done.returncode==0,(name,done.returncode)
 data=json.loads(report.read_text());actor=data['sim']['players'][0];dps=actor['collected_data']['dps']['mean'];assert dps>0
 normalized=normalize_simc_report(report.read_bytes(),expected_actor=actor['name'])
 catalog=catalog_for_build('12.1.0.69814');assert catalog
 assert normalized['engine']['gameVersion']=='12.1.0.69814'
 record={'case':name,'sourceCommit':revision,'binarySha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
  'profileSha256':hashlib.sha256(profile.encode()).hexdigest(),'reportSha256':hashlib.sha256(report.read_bytes()).hexdigest(),
  'dps':dps,'gameBuild':normalized['engine']['gameVersion'],'normalized':True}
 results.append(record);(root/'engine-smoke.json').write_text(json.dumps(results,indent=2));print(json.dumps(record),flush=True)
 if name=='independent':
  talents=actor.get('talents');assert isinstance(talents,str),type(talents)
  proof={'runtimeSource':revision,'gameBuild':'12.1.0.69814','method':'Cloud SimC export from independent class_talents/spec_talents/hero_talents entry-rank input','talents':talents}
  (root/'giannis_wcl_engine_export_69814.json').write_text(json.dumps(proof,indent=2)+'\n')

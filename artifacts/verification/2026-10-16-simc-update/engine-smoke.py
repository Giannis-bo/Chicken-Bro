"""Bounded cloud-only upstream profiles and independent talent-export proof."""
from pathlib import Path
import hashlib,json,subprocess,sys,os
os.umask(0o077)
root=Path('/var/lib/chickenbro-simc-update-20261016');source=next(p for p in Path('/opt/wow-simc/work').glob('update-76f811*/source') if (p/'CMakeLists.txt').exists())
revision='76f8118cf3f7f41dad20708e8328e1f4ab2deebc';binary=Path('/opt/wow-simc/releases')/revision/'simc'
assert binary.is_file();assert hashlib.sha256(binary.read_bytes()).hexdigest()==(binary.parent/'binary.sha256').read_text().strip()
sys.path.insert(0,'/opt/chickenbro-candidates/simc-update-20261016')
from server.app.simulation.report import normalize_simc_report
from server.app.simulation.localization import catalog_for_build,localize_report
cases=[('enhancement','MID2_Shaman_Enhancement.simc'),('protection','MID2_Paladin_Protection.simc'),('devourer','MID2_Demon_Hunter_Devourer.simc'),('independent',None)]
results=json.loads((root/'engine-smoke.json').read_text()) if (root/'engine-smoke.json').exists() else []
for record in results:
 assert record['sourceCommit']==revision
 assert record['reportSha256']==hashlib.sha256((root/(record['case']+'-engine.json')).read_bytes()).hexdigest()
 assert record['binarySha256']==hashlib.sha256(binary.read_bytes()).hexdigest()
for name,filename in cases:
 if name in {r['case'] for r in results}:continue
 profile=((root/'devourer-current-path.simc').read_text() if name=='devourer' else (source/'profiles/MID2'/filename).read_text()) if filename else (root/'independent-split.simc').read_text()
 report=root/(name+'-engine.json')
 args=[str(binary),'-','iterations=100','max_time=60','threads=1','item_db_source=local','seed=70391',f'json={report},full_states=0','report_details=1']
 if name=='enhancement':args+=['raid_events=adds,count=3,first=15,cooldown=30,duration=10']
 with (root/(name+'-engine.log')).open('w') as log:
  done=subprocess.run(args,input=profile,text=True,stdout=log,stderr=log,cwd=root,timeout=90)
 assert done.returncode==0,(name,done.returncode)
 data=json.loads(report.read_text());actor=data['sim']['players'][0];dps=actor['collected_data']['dps']['mean'];assert dps>0
 normalized=normalize_simc_report(report.read_bytes(),expected_actor=actor['name'])
 catalog=catalog_for_build('12.1.5.70391');assert catalog
 assert normalized['engine']['gameVersion']=='12.1.5.70391'
 record={'case':name,'sourceCommit':revision,'binarySha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
  'profileSha256':hashlib.sha256(profile.encode()).hexdigest(),'reportSha256':hashlib.sha256(report.read_bytes()).hexdigest(),
  'dps':dps,'gameBuild':normalized['engine']['gameVersion'],'normalized':True}
 if name=='devourer':
  from server.app.simulation.talent_editor import edit_talents
  current='simc:managed:'+revision+':'+record['binarySha256']
  character={'classKey':'demon_hunter','specKey':'devourer','level':90}
  edited=edit_talents({'string':actor['talents']},character,current,{'string':actor['talents']})
  assert edited['changes']==[]
  record['newDevourerGraphValidated']=True
 results.append(record);(root/'engine-smoke.json').write_text(json.dumps(results,indent=2));print(json.dumps(record),flush=True)
 if name=='independent':
  talents=actor.get('talents');assert isinstance(talents,str),type(talents)
  proof={'runtimeSource':revision,'gameBuild':'12.1.5.70391','method':'Cloud SimC export from independent class_talents/spec_talents/hero_talents entry-rank input','talents':talents}
  (root/'giannis_wcl_engine_export_70391.json').write_text(json.dumps(proof,indent=2)+'\n')

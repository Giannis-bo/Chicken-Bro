from pathlib import Path
import subprocess,json,sys,hashlib,os
os.umask(0o077)
r=Path('/var/lib/chickenbro-simc-update-20261016');profile=(r/'failed-live-profile.simc').read_text();out=r/'thread-allocation';out.mkdir(mode=0o700,exist_ok=True)
sys.path.insert(0,'/opt/chickenbro-candidates/simc-update-20261016');from server.app.simulation.action_lists import extract_action_evidence
cases=[('small-shared',8,4,0),('many-shared',100,32,0),('small-strict',8,4,1),('normal-strict',100,4,1),('many-strict',100,32,1)]
results=[]
for label,iterations,threads,strict in cases:
 report=out/(label+'.json')
 with (out/(label+'.log')).open('w') as log:
  done=subprocess.run(['/opt/wow-simc/candidate-20261016/simc','-',f'iterations={iterations}',f'threads={threads}',f'strict_work_queue={strict}','seed=70391',f'json={report},full_states=0','report_details=1'],input=profile,text=True,stdout=log,stderr=log,timeout=60,cwd=out)
 assert done.returncode==0
 data=json.loads(report.read_text());a=data['sim']['players'][0];rows=a['collected_data'].get('action_sequence')
 try:extract_action_evidence(report.read_bytes(),a['name'],hashlib.sha256(profile.encode()).hexdigest());status='passed'
 except ValueError:status='failed'
 record={'case':label,'iterations':iterations,'threads':threads,'strictWorkQueue':strict,'actionEvidence':status,'rowCount':len(rows) if rows else None,'dps':a['collected_data']['dps']['mean'],'reportSha256':hashlib.sha256(report.read_bytes()).hexdigest()};results.append(record);print(json.dumps(record),flush=True)
(out/'summary.json').write_text(json.dumps(results,indent=2))

from pathlib import Path
import json,sys,subprocess,re,hashlib,os
os.umask(0o077)
r=Path('/var/lib/chickenbro-simc-update-20261016');sys.path.insert(0,'/opt/chickenbro-candidates/simc-update-20261016')
from server.app.simulation.action_lists import extract_action_evidence
profile=(r/'failed-live-profile.simc').read_text();r=r/'repair-reproduction';r.mkdir(mode=0o700,exist_ok=True);results=[]
for seed in range(7,71):
 out=r/f'probe-actions-{seed}.json';log=r/f'probe-actions-{seed}.log'
 with log.open('w') as f:
  done=subprocess.run(['/opt/wow-simc/candidate-20261016/simc','-',f'seed={seed}',f'json={out},full_states=0','report_details=1'],input=profile,text=True,stdout=f,stderr=f,timeout=60,cwd=r)
 assert done.returncode==0
 raw=out.read_bytes();data=json.loads(raw);a=data['sim']['players'][0];rows=a['collected_data'].get('action_sequence');bad=[];last=-1
 for v in rows or []:
  tick=v.get('time');name=v.get('name');spell=v.get('id')
  if type(tick) not in (int,float) or tick<last or ('name' in v and (not isinstance(name,str) or not re.fullmatch(r'[a-zA-Z0-9_]{1,120}',name) or type(spell)is not int)):bad.append({k:v[k] for k in ['time','name','id'] if k in v})
  if isinstance(tick,(int,float)):last=tick
 try:extract_action_evidence(raw,a['name'],hashlib.sha256(profile.encode()).hexdigest());status='passed'
 except ValueError:status='failed'
 record={'seed':seed,'actionEvidence':status,'rowCount':len(rows) if rows else None,'invalidRows':bad[:20],'dps':a['collected_data']['dps']['mean'],'reportSha256':hashlib.sha256(raw).hexdigest()};results.append(record);print(json.dumps(record),flush=True)
 if status=='failed':break
(r/'probe-actions.json').write_text(json.dumps(results,indent=2))

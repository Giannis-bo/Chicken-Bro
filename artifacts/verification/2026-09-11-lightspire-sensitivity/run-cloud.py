"""Three cloud-only Lightspire duration trials. Refuse any attempted run replay."""
import fcntl, hashlib, json, os, subprocess, time
from pathlib import Path
os.umask(0o077)
ROOT=Path('/var/lib/chickenbro-lightspire-sensitivity-20260911')
ENGINE=Path('/opt/wow-simc/current/simc')
BINARY='69b3e5fb56f3b7149fa239059cb510f1924ef5cd6690db718812df4d938172da'
PROFILE='c2d946481482050bdaf26bf5c2d4bb347e08db05c636cc44b0feb4a41bbc5a93'
def sha(x):return hashlib.sha256(x).hexdigest()
def write(n,d):(ROOT/n).write_text(json.dumps(d,indent=2)+'\n')
with open('/run/lock/chickenbro-candidate-validation.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert sha(ENGINE.read_bytes())==BINARY
 ROOT.mkdir(mode=0o700,exist_ok=True)
 assert not (ROOT/'started.json').exists(),'Inspect prior attempt; never blindly repeat'
 original=Path('/var/lib/chickenbro-trinket-mechanism-20260911/baseline-private.simc').read_text()
 baseline=original.replace('trinket1=,id=249343,ilevel=298','trinket1=,id=250214,ilevel=321').replace('trinket2=,id=250144,ilevel=298','trinket2=,id=273796,ilevel=321')
 assert sha(baseline.encode())==PROFILE
 write('started.json',{'at':time.time(),'sourceProfileSha256':PROFILE,'binarySha256':BINARY,'newCombatCeiling':3,'priorSpellQueries':1})
 results={'binarySha256':BINARY,'sourceProfileSha256':PROFILE,'cases':[]}
 for val in [.5,.1,1.0]:
  label=str(val);profile=baseline+f'midnight.lightspire_core_duration_multiplier={val}\n'
  inp=ROOT/(label+'-private.simc');out=ROOT/(label+'-private.json');inp.write_text(profile)
  write(label+'-started.json',{'at':time.time(),'profileSha256':sha(profile.encode())})
  begin=time.monotonic();r=subprocess.run(['/usr/bin/nice','-n','10',str(ENGINE),str(inp),'threads=1','seed=20260911','json2='+str(out)],capture_output=True,timeout=120)
  (ROOT/(label+'-private.log')).write_bytes(r.stdout+r.stderr);assert r.returncode==0,'Inspect private log'
  report=json.loads(out.read_text());sim=report['sim'];p=sim['players'][0];metric=p['collected_data']['dps'];gear=p['gear'];assert metric['mean']>0 and metric['count']>=9900
  for slot,item in [('trinket1',250214),('trinket2',273796)]:assert gear[slot]['ilevel']==321 and f'id={item}' in gear[slot]['encoded_item']
  buff=next(b for b in p['buffs'] if b['name']=='lights_blessing')
  results['cases'].append({'multiplier':val,'dps':metric['mean'],'meanStdDev':metric['mean_std_dev'],'count':metric['count'],'elapsedSeconds':time.monotonic()-begin,'profileSha256':sha(profile.encode()),'reportSha256':sha(out.read_bytes()),'lightBuff':{k:buff.get(k) for k in ['name','spell','uptime','start_count','refresh_count','duration']},'controls':{k:sim['options'].get(k) for k in ['iterations','max_time','vary_combat_length','fixed_time','desired_targets','seed','confidence']},'gear':{k:gear[k] for k in ['trinket1','trinket2']},'diagnosticLevels':[b.get('level') for b in report.get('logs',[])]})
  write('result.json',results)
  print(json.dumps({'multiplier':val,'dps':metric['mean'],'uptime':buff['uptime']}),flush=True)
 assert sha(ENGINE.read_bytes())==BINARY
 results['finished']=True;results['combatRuns']=3;write('result.json',results)

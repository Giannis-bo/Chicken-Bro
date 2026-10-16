from pathlib import Path
import hashlib,json,os,pwd,re,subprocess,sys
r=Path('/var/lib/chickenbro/simc-repair-20261016')
if '--worker-environment' not in sys.argv:
 pid=subprocess.check_output(['systemctl','show','chickenbro-worker','-p','MainPID','--value'],text=True).strip()
 env=dict(v.split('=',1) for v in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in v)
 env.update(PYTHONPATH='/opt/chickenbro-candidates/simc-update-20261016',WOW_SIMC_BIN='/opt/wow-simc/candidate-20261016/simc')
 env.pop('WOW_SIMC_RUNTIME_REVISION',None)
 u=pwd.getpwnam('ubuntu');os.setgroups([u.pw_gid]);os.setgid(u.pw_gid);os.setuid(u.pw_uid);os.umask(0o077);os.chdir('/opt/chickenbro-candidates/simc-update-20261016')
 os.execve('/opt/chickenbro-runtime/bin/python',['python',str(r/'worker-port-probe.py'),'--worker-environment'],env)
from types import SimpleNamespace
from server.app.simulation.worker import LocalSimulationCraftPort,SimulationResultParser
from server.app.simulation.readiness import SimcRuntimeCapabilities
from server.app.simulation.action_lists import extract_action_evidence
profile=(r/'profile.simc').read_text();digest=hashlib.sha256(profile.encode()).hexdigest();runtime=SimcRuntimeCapabilities.from_env().runtime_revision
results=[]
for i in range(1,7):
 def capture(args,**kwargs):
  completed=subprocess.run(args,**kwargs)
  for prefix,name in [('json=','report.json'),('html=','report.html')]:
   entry=next(x for x in args if x.startswith(prefix));p=Path(entry.split('=',1)[1].split(',')[0])
   if p.is_file():(r/f'port-{i}-{name}').write_bytes(p.read_bytes())
  (r/f'port-{i}-stdout.log').write_text(completed.stdout);(r/f'port-{i}-stderr.log').write_text(completed.stderr)
  return completed
 compiled=SimpleNamespace(profile=profile,profile_sha256=digest,actor_name='Giannis')
 execution=LocalSimulationCraftPort(runtime_revision=runtime,runner=capture).run(compiled,runtime)
 metric=SimulationResultParser().parse(execution,expected_actor='Giannis')
 try:extract_action_evidence(execution.report_json,'Giannis',digest);status='passed'
 except ValueError:status='failed'
 data=json.loads(execution.report_json);a=data['sim']['players'][0];rows=a['collected_data'].get('action_sequence')
 record={'iteration':i,'status':status,'dps':metric.value,'profileSha256':digest,'rawBytes':len(execution.report_json),'rowCount':len(rows) if rows else None,'reportSha256':hashlib.sha256(execution.report_json).hexdigest(),'seed':data['sim'].get('options',{}).get('seed')}
 results.append(record);print(json.dumps(record),flush=True)
 if status=='failed':break
(r/'port-probe.json').write_text(json.dumps(results,indent=2))

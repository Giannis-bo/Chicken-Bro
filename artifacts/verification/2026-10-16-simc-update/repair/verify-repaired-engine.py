from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import json,sys,os,subprocess,hashlib,re
from uuid import UUID
import psycopg
os.umask(0o077)
r=Path('/var/lib/chickenbro-simc-update-20261016');sys.path.insert(0,'/opt/chickenbro-candidates/simc-update-20261016')
pid=subprocess.check_output(['systemctl','show','chickenbro-api','-p','MainPID','--value'],text=True).strip();env=dict(v.split('=',1) for v in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in v)
@contextmanager
def connection():
 with psycopg.connect(env['WOW_DATABASE_URL'],passfile=env['PGPASSFILE']) as c:yield c
from server.app.simulation.repository import PostgresSimulationRepository
from server.app.simulation.readiness import SimcRuntimeCapabilities
from server.app.simulation.compiler import SimcProfileCompiler
from server.app.simulation.action_lists import extract_action_evidence
jid=json.loads((r/'live-private.json').read_text())['lastJobId'];payload=json.loads((r/'failed-live-payload.json').read_text())
with connection() as c:
 row=c.execute('SELECT user_id,snapshot_id FROM simc.simulation_jobs WHERE id=%s',(jid,)).fetchone()
 history=c.execute("SELECT j.id,j.status,j.public_error_code,j.runtime_revision FROM simc.simulation_jobs j WHERE j.snapshot_id=%s ORDER BY j.created_at DESC LIMIT 6",(row[1],)).fetchall()
 print('same_snapshot_history',json.dumps(history,default=str),flush=True)
snapshot=PostgresSimulationRepository(connection).get_snapshot(row[0],row[1]);caps=SimcRuntimeCapabilities.from_env({**env,'WOW_SIMC_BIN':'/opt/wow-simc/candidate-20261016/simc'})
caps=replace(caps,compiler_revision=payload['compilerRevision']);compiled=SimcProfileCompiler(capabilities=caps).compile(snapshot,payload['scenario'])
(r/'repaired-live-profile.simc').write_text(compiled.profile)
assert 'strict_work_queue=1\n' in compiled.profile
out=r/'repaired-thread-proof';out.mkdir(mode=0o700,exist_ok=True);results=[]
for label,iterations,threads in [('original-failure-shape',100,32),('holdout',128,64),('normal',100,4),('one-iteration',1,1)]:
 report=out/(label+'.json')
 with (out/(label+'.log')).open('w') as log:
  done=subprocess.run(['/opt/wow-simc/candidate-20261016/simc','-',f'iterations={iterations}',f'threads={threads}','seed=70391',f'json={report},full_states=0','report_details=1'],input=compiled.profile,text=True,stdout=log,stderr=log,timeout=60,cwd=out)
 assert done.returncode==0
 data=json.loads(report.read_text());actor=data['sim']['players'][0];evidence=extract_action_evidence(report.read_bytes(),compiled.actor_name,compiled.profile_sha256)
 assert actor['collected_data']['dps']['mean']>0 and evidence['sample']
 record={'case':label,'iterations':iterations,'threads':threads,'profileSha256':compiled.profile_sha256,'strictWorkQueue':True,'dps':actor['collected_data']['dps']['mean'],'sampledActions':len(evidence['sample']),'reportSha256':hashlib.sha256(report.read_bytes()).hexdigest()};results.append(record);print(json.dumps(record),flush=True)
(out/'summary.json').write_text(json.dumps(results,indent=2))

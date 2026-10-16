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
(r/'failed-live-profile.simc').write_text(compiled.profile)
results=[]
for label,revision in [('old','eed909156d8eccbfca0f284cc271c080949d6a20'),('new','76f8118cf3f7f41dad20708e8328e1f4ab2deebc')]:
 report=r/('diagnose-live-'+label+'.json');html=r/('diagnose-live-'+label+'.html')
 with (r/('diagnose-live-'+label+'.log')).open('w') as log:
  done=subprocess.run(['/opt/wow-simc/releases/'+revision+'/simc','-',f'json={report},full_states=0',f'html={html}','report_details=1'],input=compiled.profile,text=True,stdout=log,stderr=log,timeout=60,cwd=r)
 assert done.returncode==0
 data=json.loads(report.read_text());actor=next(a for a in data['sim']['players'] if a['name']==compiled.actor_name);rows=actor['collected_data'].get('action_sequence');bad=[];last=-1
 for v in rows or []:
  tick=v.get('time');name=v.get('name');spell=v.get('id')
  if type(tick) not in (int,float) or tick<last or ('name' in v and (not isinstance(name,str) or not re.fullmatch(r'[a-zA-Z0-9_]{1,120}',name) or type(spell)is not int)):bad.append({k:v[k] for k in ['time','name','id'] if k in v})
  if isinstance(tick,(float,int)):last=tick
 try:extract_action_evidence(report.read_bytes(),compiled.actor_name,compiled.profile_sha256);status='passed'
 except ValueError:status='failed'
 record={'label':label,'engine':revision,'profileSha256':compiled.profile_sha256,'dps':actor['collected_data']['dps']['mean'],'rows':len(rows) if rows else None,'actionEvidence':status,'invalidRows':bad[:20]}
 results.append(record);print(json.dumps(record),flush=True)
(r/'live-diagnosis.json').write_text(json.dumps(results,indent=2))

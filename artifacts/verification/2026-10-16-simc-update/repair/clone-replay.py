from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,unquote
from uuid import uuid4
import json,os,sys,subprocess,re,psycopg
os.umask(0o077);root=Path('/var/lib/chickenbro-simc-update-20261016');sys.path.insert(0,'/opt/chickenbro-candidates/simc-update-20261016')
pid=subprocess.check_output(['systemctl','show','chickenbro-api','-p','MainPID','--value'],text=True).strip();env=dict(v.split('=',1) for v in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in v)
dsn=urlsplit(env['WOW_DATABASE_URL']);password=None
for line in Path(env['PGPASSFILE']).read_text().splitlines():
 f=[re.sub(r'\\(.)',r'\1',v) for v in re.split(r'(?<!\\):',line)]
 if len(f)==5 and f[2]==dsn.path.lstrip('/') and f[3]==unquote(dsn.username):password=f[4];break
assert password
@contextmanager
def production():
 with psycopg.connect(env['WOW_DATABASE_URL'],passfile=env['PGPASSFILE']) as c:yield c
@contextmanager
def candidate():
 with psycopg.connect(urlunsplit(dsn._replace(path='/chickenbro_simc_candidate_20261016')),password=password) as c:yield c
from server.app.simulation.repository import PostgresSimulationRepository
with production() as c:row=c.execute('SELECT user_id,snapshot_id FROM simc.simulation_jobs WHERE id=%s',('ad82df72-1bf1-4640-ad94-51d55b2cd3fa',)).fetchone()
source=PostgresSimulationRepository(production).get_snapshot(*row)
with candidate() as c:
 uid=c.execute("SELECT DISTINCT j.user_id FROM simc.simulation_jobs j JOIN identity.user_identities i ON i.user_id=j.user_id JOIN ops.job_queue q ON q.id=j.id AND q.aggregate_id=j.id WHERE j.status='succeeded' AND q.domain='simc' AND q.command_type='run_simulation' AND i.provider='qq' AND EXISTS (SELECT 1 FROM simc.source_snapshots s WHERE s.user_id=j.user_id AND s.snapshot_json->'character'->>'classKey'='shaman' AND s.snapshot_json->'character'->>'specKey'='elemental') ORDER BY j.user_id LIMIT 1").fetchone()[0]
replay=PostgresSimulationRepository(candidate).save_snapshot_with_next_revision(replace(source,id=uuid4(),user_id=uid,source_key='simc-upgrade-failed-live-replay-20261016'))
(root/'replay-candidate.json').write_text(json.dumps({'snapshotId':str(replay.id),'sameSnapshotContent':replay.snapshot==source.snapshot,'sameRawSha256':replay.raw_sha256==source.raw_sha256},indent=2));print(str(replay.id))

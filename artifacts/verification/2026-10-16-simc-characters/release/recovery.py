"""Privately back up production, restore independently, and test the additive schema."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys

from deploy import Release, require, sha
os.umask(0o077)
packet=Path(__file__).resolve().parent
r=Release(packet/'manifest.json')
r.baseline(r.base)
r.staged()
name='chickenbro_simc_characters_recovery_verified_20261016'
require(name != 'chickenbro_prod','recovery database must be independent')
admin=pwd.getpwnam('postgres')
python='/opt/chickenbro-runtime/bin/python'
def as_postgres(code, *, data=None, pass_fds=()):
    result=subprocess.run([python,'-c',code],input=data,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        user=admin.pw_uid,group=admin.pw_gid,cwd='/opt',pass_fds=pass_fds,check=False)
    require(result.returncode == 0,'isolated recovery subprocess failed')
    return result.stdout
proof=packet/'database-recovery.json'
require(not proof.exists(),'existing recovery proof: verify it instead of repeating a backup')
dump=packet/'production-before.sql'
if dump.exists():
    # The immutable exported backup may be reused after a failed verifier; never overwrite it.
    import re
    counts={}
    current=None
    with dump.open() as handle:
        for line in handle:
            match=re.match(r'^COPY ((?:identity|chat|simc|ops|poe2)\.[a-z_]+) \(',line)
            if match:
                current=match.group(1);counts[current]=0
            elif current is not None:
                if line.rstrip('\n') == '\\.':current=None
                else:counts[current]+=1
    require(len(counts)>20,'backup COPY inventory incomplete')
else:
    from uuid import uuid4
    partial = packet/('production-before.partial-'+uuid4().hex)
    with partial.open('xb') as output:
        code="""import psycopg,subprocess,json
with psycopg.connect('postgresql:///chickenbro_prod') as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
 snapshot=c.execute('SELECT pg_export_snapshot()').fetchone()[0]
 tables=c.execute("SELECT schemaname,tablename FROM pg_tables WHERE schemaname IN ('identity','chat','simc','ops','poe2') ORDER BY schemaname,tablename").fetchall()
 counts={s+'.'+t:c.execute('SELECT count(*) FROM '+psycopg.sql.Identifier(s,t).as_string(c)).fetchone()[0] for s,t in tables}
 subprocess.run(['pg_dump','--dbname=chickenbro_prod','--no-owner','--snapshot='+snapshot],stdout=FD,check=True)
 print(json.dumps(counts))
""".replace('stdout=FD','stdout='+str(output.fileno()))
        compile(code,'exported-backup','exec')
        counts=json.loads(as_postgres(code,pass_fds=(output.fileno(),)))
        output.flush()
        os.fsync(output.fileno())
    require(partial.stat().st_size > 0, 'empty backup output')
    os.rename(partial,dump)
dump.chmod(0o600)
exists=as_postgres("import psycopg\nwith psycopg.connect('postgresql:///postgres') as c:print(c.execute(\"SELECT count(*) FROM pg_database WHERE datname='"+name+"'\").fetchone()[0])").strip()
require(exists == '0','independent recovery database already exists')
subprocess.run(['sudo','-n','-u','postgres','createdb','--template=template0','--encoding=UTF8',name],check=True)
with dump.open('rb') as handle:
    restored=subprocess.run(['sudo','-n','-u','postgres','psql','-X','-q','-v','ON_ERROR_STOP=1','-d',name,'-f','-'],stdin=handle,
        stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
require(restored.returncode == 0,'backup restore failed')
verify='''import psycopg,json
expected=json.load(__import__('sys').stdin)
with psycopg.connect('postgresql:///DB') as c:
 actual={key:c.execute('SELECT count(*) FROM '+psycopg.sql.Identifier(*key.split('.')).as_string(c)).fetchone()[0] for key in expected}
 assert actual==expected
 assert c.execute("SELECT to_regclass('simc.character_preferences')").fetchone()[0] is None
print(json.dumps({'restoredTables':len(actual),'restoreCountsMatched':True}))
'''.replace('DB',name)
result=json.loads(as_postgres(verify,data=json.dumps(counts)))
source=Path('/opt/chickenbro-candidates/simc-character-bindings-20261016')
apply="""import sys,psycopg,json
from pathlib import Path
sys.path.insert(0,'SOURCE')
with psycopg.connect('postgresql:///DB') as c:
 assert c.execute("SELECT to_regclass('simc.character_preferences')").fetchone()[0] is None
 c.execute(Path('SOURCE/server/migrations/product/0021_simc_characters.sql').read_text())
 c.execute("INSERT INTO ops.schema_migrations (id,description) VALUES ('0021_simc_characters','Apply clean product migration 0021_simc_characters')")
 assert c.execute("SELECT has_table_privilege('wow_app','simc.character_preferences','SELECT,INSERT,UPDATE')").fetchone()[0]
from contextlib import contextmanager
from server.app.simulation.characters import CharacterBindings
from server.app.simulation.repository import PostgresSimulationRepository
from server.app.simulation.application import SimulationApplicationError
from server.app.identity.domain import Principal
@contextmanager
def runtime_connection():
 with psycopg.connect('postgresql:///DB') as c:
  c.execute('SET ROLE wow_app')
  yield c
repo=PostgresSimulationRepository(runtime_connection)
service=CharacterBindings(repo)
with runtime_connection() as c:
 row=c.execute("SELECT user_id,id FROM simc.source_snapshots WHERE provider='raiderio' AND readiness='READY_FOR_SIMC' ORDER BY fetched_at DESC LIMIT 1").fetchone()
 other=c.execute('SELECT id FROM identity.users WHERE id<>%s LIMIT 1',(row[0],)).fetchone()[0]
principal=Principal(row[0],'web_cookie')
snapshot=repo.get_snapshot(row[0],row[1])
bound=service.bind(principal,snapshot)
assert len(bound['items'])==1
assert service.read(Principal(other,'web_cookie'))=={'items':[],'selectedId':None}
assert service.change(principal,bound['selectedId'],unbind=True)['items']==[]
print(json.dumps({'runtimeRoleBindingReadUnbind':True,'secondOwnerIsolated':True}))
""".replace('SOURCE',str(source)).replace('DB',name)
sanity=json.loads(as_postgres(apply))
(packet/'database-backup-manifest.json').write_text(json.dumps({'tables':counts,'dumpSha256':sha(dump),'countsSource':'immutable exported pg_dump COPY records'},indent=2)+'\n')
result.update({'database':name,'dumpSha256':sha(dump),'newMigrationVerified':True,'runtimeRoleChecks':sanity,
    'recoveryBackendCopyVerified':True,'recoveryWebCopyVerified':True,'productionDataOverwritten':False,
    'productionRollbackDrill':False})
proof.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))

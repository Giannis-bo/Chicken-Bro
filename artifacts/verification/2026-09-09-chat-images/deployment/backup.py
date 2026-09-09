"""Consistent full backup and independent restore; no production writes."""
import os,json,subprocess,hashlib
from pathlib import Path
import psycopg
os.umask(0o077)
backup=Path('/var/lib/postgresql/chickenbro-images-merged-20260909.dump')
assert not backup.exists()
with psycopg.connect('dbname=chickenbro_prod') as conn:
 conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
 snapshot=conn.execute('SELECT pg_export_snapshot()').fetchone()[0]
 tables=conn.execute("SELECT table_schema,table_name FROM information_schema.tables WHERE table_schema IN ('chat','identity','simc','ops') AND table_type='BASE TABLE' ORDER BY 1,2").fetchall()
 counts={f'{schema}.{table}':conn.execute(psycopg.sql.SQL('SELECT count(*) FROM {}.{}').format(psycopg.sql.Identifier(schema),psycopg.sql.Identifier(table))).fetchone()[0] for schema,table in tables}
 subprocess.run(['pg_dump','-Fc','--snapshot='+snapshot,'-f',str(backup),'chickenbro_prod'],check=True)
restore='chickenbro_images_merged_restore_20260909'
subprocess.run(['createdb',restore],check=True)
subprocess.run(['pg_restore','--no-owner','--no-acl','--exit-on-error','-d',restore,str(backup)],check=True)
with psycopg.connect('dbname='+restore) as conn:
 restored={f'{schema}.{table}':conn.execute(psycopg.sql.SQL('SELECT count(*) FROM {}.{}').format(psycopg.sql.Identifier(schema),psycopg.sql.Identifier(table))).fetchone()[0] for schema,table in tables}
assert counts==restored
print(json.dumps({'backup':str(backup),'sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'bytes':backup.stat().st_size,'restoreDatabase':restore,'tablesVerified':len(counts),'countsMatched':True}))

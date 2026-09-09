"""Isolated empty database and private environment, derived from running API."""
import os,subprocess,json,shlex
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
root=Path('/opt/chickenbro-releases')/os.environ['IMAGE_RELEASE']
assert root.is_dir()
pid=subprocess.check_output(['systemctl','show','chickenbro-api','-p','MainPID','--value'],text=True).strip()
env=dict(v.split('=',1) for v in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in v)
db='chickenbro_images_merged_candidate_20260909'
exists=subprocess.check_output(['sudo','-u','postgres','psql','-X','-At','-d','postgres','-c',f"SELECT count(*) FROM pg_database WHERE datname='{db}'"],text=True).strip()
if exists!='0':raise SystemExit('Candidate database already exists; inspect before reuse')
subprocess.run(['sudo','-u','postgres','createdb','--owner=wow_app',db],check=True)
uri=urlsplit(env['WOW_DATABASE_URL']);old_db=uri.path[1:]
env['WOW_DATABASE_URL']=urlunsplit(uri._replace(path='/'+db))
pgpass=Path('/etc/chickenbro-images-merged-candidate.pgpass')
assert not pgpass.exists()
pgpass.write_text(Path(env['PGPASSFILE']).read_text().replace(':'+old_db+':',':'+db+':'));pgpass.chmod(0o600)
subprocess.run(['chown','ubuntu:ubuntu',str(pgpass)],check=True)
env.update(PGPASSFILE=str(pgpass),WOW_APP_ENV='candidate',WOW_API_V2_PORT='8793',WOW_WORKER_V2_HEARTBEAT_PATH='/var/lib/chickenbro/candidate-worker-heartbeat.json',WOW_TEST_LOGIN_ENABLED='0',
 CHICKENBRO_CHAT_IMAGES_ENABLED='1',PYTHONPATH=str(root),WOW_CODEX_JOBS_DIR='/var/lib/chickenbro/images-candidate-jobs')
# Migrate via database administrator; application runtime keeps existing narrow grants.
subprocess.run(['sudo','-u','postgres','env','PYTHONPATH='+str(root),'/opt/chickenbro-runtime/bin/python','-c',
 "import psycopg,importlib;from pathlib import Path; c=psycopg.connect('dbname="+db+"',autocommit=True);print(importlib.import_module('server.migrations.product.apply').apply_product_migrations(c,Path('"+str(root)+"/server/migrations/product')))"],check=True)
path=Path('/etc/chickenbro-images-merged-candidate.env');assert not path.exists()
allowed={k:v for k,v in env.items() if k.startswith(('WOW_','CHICKENBRO_','CODEX_')) or k in ['HOME','PATH','PGPASSFILE','PYTHONPATH','LANG','TZ','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','all_proxy','no_proxy']}
path.write_text(''.join(k+'='+json.dumps(v)+'\n' for k,v in allowed.items()));path.chmod(0o600)
subprocess.run(['systemd-run','--unit=chickenbro-images-candidate','--property=User=ubuntu','--property=WorkingDirectory='+str(root),
 '--property=EnvironmentFile='+str(path),'--property=UMask=0077','/opt/chickenbro-runtime/bin/python','-m','uvicorn','server.app.main:app','--host','127.0.0.1','--port','8793'],check=True)
subprocess.run(['systemd-run','--unit=chickenbro-images-candidate-worker','--property=User=ubuntu','--property=WorkingDirectory='+str(root),'--property=EnvironmentFile='+str(path),'--property=UMask=0077','/opt/chickenbro-runtime/bin/python','-m','server.app.worker.main','--worker-id','chickenbro-simc-candidate-worker'],check=True)
print(json.dumps({'database':db,'port':8793,'code':str(root),'configuration':'private'}))

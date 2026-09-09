"""Exact reviewed screenshot release; additive migration, reversible pointers."""
import argparse,hashlib,json,subprocess,time,os,shutil
from pathlib import Path
import urllib.request
p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');args=p.parse_args()
stage=Path('/tmp/chickenbro-images-release');m=json.loads((stage/'manifest.json').read_text());root=Path('/opt/chickenbro-releases')/m['release'];web=Path('/var/www/chickenbro-web/releases')/m['release']
code_link=Path('/opt/chickenbro');web_link=Path('/var/www/chickenbro-web/current')
assert str(code_link.resolve())==m['previousCode'] and str(web_link.resolve())==m['previousWeb'],'Live pointers changed'
assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==sha for name,sha in m['files'].items()),'Staged bytes differ'
for name,sha in json.loads((stage/'previous-source.json').read_text()).items():
 assert hashlib.sha256((code_link/name).read_bytes()).hexdigest()==sha,'Live source changed: '+name
nginx=[Path('/etc/nginx/sites-available/wow-v2-web'),Path('/etc/nginx/sites-enabled/api.chickenbro.cloud')]
block='''location = /api/v2/chat/images {
    client_max_body_size 7m;
    proxy_pass http://127.0.0.1:8790;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_read_timeout 540s;
}
'''
before={str(p):p.read_bytes() for p in nginx}
for raw in before.values():
 assert raw.count(b'location ^~ /api/v2/ {')==1 and b'location = /api/v2/chat/images' not in raw,'Nginx topology changed'
def run(*cmd):return subprocess.check_output(cmd,text=True,stderr=subprocess.PIPE).strip()
def active():
 return int(run('sudo','-u','postgres','psql','-X','-At','-d','chickenbro_prod','-c',"SELECT (SELECT count(*) FROM chat.agent_runs WHERE status='streaming')+(SELECT count(*) FROM ops.job_queue WHERE status IN ('queued','running'))"))
assert active()==0,'Production has active work, wait for drain'
with urllib.request.urlopen('http://127.0.0.1:8790/api/v2/health/readiness') as r: assert json.load(r)['status']=='ready'
with urllib.request.urlopen('http://127.0.0.1:8793/api/v2/health/readiness') as r: assert json.load(r)['status']=='ready','Candidate is not ready'
flag=Path('/etc/systemd/system/chickenbro-api.service.d/99-chat-images.conf')
service=Path('/etc/systemd/system/chickenbro-image-retention.service');timer=Path('/etc/systemd/system/chickenbro-image-retention.timer')
assert not any(p.exists() for p in [flag,service,timer])
if web.exists():
 assert all(hashlib.sha256((web/name[4:]).read_bytes()).hexdigest()==sha for name,sha in m['files'].items() if name.startswith('web/')),'Existing staged Web bytes differ'
result={'commit':m['commit'],'previousCode':m['previousCode'],'previousWeb':m['previousWeb'],'newCode':str(root),'newWeb':str(web),'mode':'dry_run'}
if not args.apply:
 print(json.dumps(result));raise SystemExit()
assert os.geteuid()==0
backup=Path('/var/lib/chickenbro/images-release-config-backup-retry2');assert not backup.exists();backup.mkdir(mode=0o700)
for i,(name,data) in enumerate(before.items()):(backup/str(i)).write_bytes(data)
(backup/'manifest.json').write_text(json.dumps({str(i):name for i,name in enumerate(before)}))
def switch(link,target):
 pending=link.with_name(link.name+'.images-next');assert not pending.exists() and not pending.is_symlink()
 pending.symlink_to(target);pending.replace(link)
stopped=False
try:
 run('systemctl','stop','chickenbro-api','chickenbro-worker');stopped=True
 assert active()==0,'Work arrived before stop; preserving previous runtime'
 run('sudo','-u','postgres','env','PYTHONPATH='+str(root),'/opt/chickenbro-runtime/bin/python','-c',"import psycopg,importlib;from pathlib import Path;c=psycopg.connect('dbname=chickenbro_prod',autocommit=True);importlib.import_module('server.migrations.product.apply').apply_product_migrations(c,Path('"+str(root)+"/server/migrations/product'))")
 if not web.exists():shutil.copytree(root/'web',web)
 for file in nginx:file.write_text(before[str(file)].decode().replace('location ^~ /api/v2/ {',block+'\nlocation ^~ /api/v2/ {'))
 run('nginx','-t')
 flag.write_text('[Service]\nEnvironment=CHICKENBRO_CHAT_IMAGES_ENABLED=1\n')
 service.write_text('''[Unit]
Description=Expire private Chickenbro image payloads
After=network.target
[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/opt/chickenbro
Environment=PYTHONPATH=/opt/chickenbro
Environment=WOW_APP_ENV=production
EnvironmentFile=-/etc/chickenbro-source.env
EnvironmentFile=-/etc/chickenbro-api.env
EnvironmentFile=/etc/chickenbro-release-20260907.env
EnvironmentFile=/etc/chickenbro-wechat-trial-20260907.env
EnvironmentFile=/etc/chickenbro-faq-20260908.env
UMask=0077
ExecStart=/opt/chickenbro-runtime/bin/python -m server.purge_chat_images --apply
''')
 timer.write_text('''[Unit]
Description=Daily private Chickenbro image expiry
[Timer]
OnCalendar=*-*-* 04:30:00
Persistent=true
Unit=chickenbro-image-retention.service
[Install]
WantedBy=timers.target
''')
 switch(code_link,root);switch(web_link,web)
 run('systemctl','daemon-reload');run('systemctl','start','chickenbro-api','chickenbro-worker');stopped=False
 run('systemctl','reload','nginx')
 for attempt in range(20):
  try:
   with urllib.request.urlopen('http://127.0.0.1:8790/api/v2/health/readiness',timeout=3) as r: ready=json.load(r)['status']=='ready'
  except Exception:ready=False
  if ready:break
  time.sleep(1)
 assert ready,'New runtime is not ready'
 run('systemctl','enable','--now','chickenbro-image-retention.timer')
 run('systemctl','start','chickenbro-image-retention.service')
 result.update(mode='applied',readiness='ready',timer='active',configBackup=str(backup));print(json.dumps(result))
except BaseException:
 # Quiesce admissions before deciding whether old code can read all writes.
 run('systemctl','stop','chickenbro-api','chickenbro-worker')
 if timer.exists():run('systemctl','disable','--now','chickenbro-image-retention.timer')
 if service.exists():run('systemctl','stop','chickenbro-image-retention.service')
 bound=None
 try:
  relation=run('sudo','-u','postgres','psql','-X','-At','-d','chickenbro_prod','-c',"SELECT to_regclass('chat.images') IS NOT NULL")
  if relation=='f':bound=0
  elif relation=='t':bound=int(run('sudo','-u','postgres','psql','-X','-At','-d','chickenbro_prod','-c','SELECT count(*) FROM chat.images WHERE message_id IS NOT NULL'))
 except Exception:pass
 if bound==0:
  if code_link.resolve()!=Path(m['previousCode']):switch(code_link,m['previousCode'])
  if web_link.resolve()!=Path(m['previousWeb']):switch(web_link,m['previousWeb'])
  for file in nginx:file.write_bytes(before[str(file)])
  for owned in (flag,service,timer):
   if owned.exists():owned.unlink()
 else:
  # Unknown state must keep the image-aware reader, with uploads disabled.
  if not web.exists():shutil.copytree(root/'web',web)
  if code_link.resolve()!=root:switch(code_link,root)
  if web_link.resolve()!=web:switch(web_link,web)
  flag.write_text('[Service]\nEnvironment=CHICKENBRO_CHAT_IMAGES_ENABLED=0\n')
 run('systemctl','daemon-reload');run('systemctl','restart','chickenbro-api','chickenbro-worker')
 run('nginx','-t');run('systemctl','reload','nginx')
 recovered=False
 for attempt in range(30):
  try:
   with urllib.request.urlopen('http://127.0.0.1:8790/api/v2/health/readiness',timeout=3) as r:recovered=json.load(r)['status']=='ready'
  except Exception:recovered=False
  if recovered:break
  time.sleep(1)
 assert recovered,'Rollback runtime readiness failed'
 pid=run('systemctl','show','chickenbro-api','-p','MainPID','--value')
 effective=dict(v.split('=',1) for v in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in v)
 assert effective.get('CHICKENBRO_CHAT_IMAGES_ENABLED','0')!='1','Rollback uploads remain enabled'
 raise

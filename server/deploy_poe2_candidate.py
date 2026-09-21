"""Cloud-only, task-scoped Candidate provisioning. Never switches production."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path('/opt/chickenbro-candidates/poe2-20260918')
DB = 'chickenbro_poe2_candidate'
MARKER = 'Chickenbro POE2 Candidate 20260918'


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def sql(query, database='postgres'):
    return run('sudo', '-u', 'postgres', 'psql', '-X', '-At', '-v', 'ON_ERROR_STOP=1', '-d', database, '-c', query)


def provision():
    exists = sql(f"SELECT count(*) FROM pg_database WHERE datname='{DB}'") == '1'
    if exists:
        if sql(f"SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname='{DB}'") != MARKER:
            raise RuntimeError('Existing database is not this task Candidate')
    else:
        sql(f'CREATE DATABASE {DB}')
        sql(f"COMMENT ON DATABASE {DB} IS '{MARKER}'")
    sql(f'REVOKE CONNECT ON DATABASE {DB} FROM PUBLIC; GRANT CONNECT ON DATABASE {DB} TO wow_app')
    code = """from pathlib import Path
import psycopg
from server.migrations.product.apply import apply_product_migrations
with psycopg.connect('dbname=chickenbro_poe2_candidate') as conn:
    print('migrations:',apply_product_migrations(conn,Path('server/migrations/product')))
"""
    print(run('sudo', '-u', 'postgres', '/opt/chickenbro-runtime/bin/python', '-c', code, cwd=ROOT / 'source'))
    jobs = Path('/var/lib/chickenbro/poe2-candidate-codex-jobs')
    jobs.mkdir(mode=0o700, exist_ok=True)
    run('chown', 'ubuntu:ubuntu', str(jobs))
    common = f'''[Unit]
Description=Chickenbro POE2 isolated Candidate
After=network-online.target mihomo.service
Wants=network-online.target
[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory={ROOT}/source
Environment=PYTHONPATH={ROOT}/source
EnvironmentFile=/etc/chickenbro-source.env
EnvironmentFile=/etc/chickenbro-api.env
EnvironmentFile=/etc/chickenbro-test-login.env
Environment=PATH=/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/var/lib/chickenbro /home/ubuntu/.codex
ReadOnlyPaths={ROOT} /opt/chickenbro-runtime /opt/wow-simc
Restart=always
RestartSec=5
TimeoutStopSec=540
'''
    for mode in ('api', 'worker'):
        path = Path(f'/etc/systemd/system/chickenbro-poe2-candidate-{mode}.service')
        content = common + f'ExecStart=/opt/chickenbro-runtime/bin/python -m server.poe2_candidate_runtime {mode}\n[Install]\nWantedBy=multi-user.target\n'
        if path.exists() and path.read_text() != content:
            raise RuntimeError('Existing Candidate unit differs; inspect it')
        path.write_text(content)
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', '--now', 'chickenbro-poe2-candidate-api', 'chickenbro-poe2-candidate-worker')
    print('Candidate services started; business verification remains required')


def publish():
    if not (ROOT / 'web/index.html').is_file():
        raise RuntimeError('Candidate Web artifact missing')
    snippet = Path('/etc/nginx/snippets/chickenbro-poe2-candidate.conf')
    content = f'''location = /poe2-candidate {{ return 302 /poe2-candidate/; }}
location ^~ /poe2-candidate/api/v2/internal/ {{ return 404; }}
location ^~ /poe2-candidate/api/v2/ {{
    proxy_pass http://127.0.0.1:8796/api/v2/;
    client_max_body_size 7m;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_read_timeout 540s;
}}
location ^~ /poe2-candidate/ {{
    alias {ROOT}/web/;
    index index.html;
    rewrite ^/poe2-candidate/(simc|poe2|admin)/?$ /poe2-candidate/index.html last;
    add_header Cache-Control "no-store" always;
}}
'''
    site = Path('/etc/nginx/sites-enabled/wow-v2-web')
    original = site.read_text()
    include = '    include /etc/nginx/snippets/chickenbro-poe2-candidate.conf;\n'
    marker = '    include /etc/nginx/snippets/chickenbro-qq-candidate.conf;\n'
    if include not in original and original.count(marker) != 1:
        raise RuntimeError('Nginx site layout changed')
    backup = ROOT / 'evidence/nginx-before-poe2.conf'
    if not backup.exists():
        backup.write_text(original)
    if snippet.exists() and snippet.read_text() != content:
        raise RuntimeError('Existing Candidate snippet differs')
    snippet.write_text(content)
    site.write_text(original if include in original else original.replace(marker, marker + include))
    try:
        run('nginx', '-t')
    except Exception:
        site.write_text(original)
        raise
    run('systemctl', 'reload', 'nginx')
    print('Candidate path published; production root and upstream unchanged')


if __name__ == '__main__':
    if sys.argv[1:] == ['provision']: provision()
    elif sys.argv[1:] == ['publish']: publish()
    else: raise SystemExit('provision|publish required')

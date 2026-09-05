"""Known-host isolated test environment. No production DB writes or cutover."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys


ROOT = Path('/opt/chickenbro-test')
ENV_FILE = Path('/etc/chickenbro-test-login.env')
MARKER = 'Chickenbro isolated test login database v1'


def command(*args, input=None):
    return subprocess.check_output(args, input=input, text=True, stderr=subprocess.PIPE)


def sql(statement, database='postgres'):
    return command('sudo', '-u', 'postgres', 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-At', '-d', database,
                   '-c', statement).strip()


def write_private(path, text):
    # Contains only credential digests, never plaintext credentials.
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as handle:
        handle.write(text)


def configure(hashes):
    if set(hashes) != {'A', 'B'} or any(re.fullmatch('[0-9a-f]{64}', v) is None for v in hashes.values()):
        raise ValueError('two credential hashes are required')
    if hashes['A'] == hashes['B']:
        raise ValueError('credentials must be different')
    if sql("SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname='chickenbro_test'") != MARKER:
        raise ValueError('test database is not managed by this task')
    write_private(ENV_FILE, 'WOW_TEST_LOGIN_ENABLED=1\n' + ''.join(
        f'WOW_TEST_LOGIN_{account}_SHA256={hashes[account]}\n' for account in ('A', 'B')))
    from server.app.identity.test_accounts import TEST_ACCOUNT_IDS
    owners = ','.join("'" + str(value) + "'::uuid" for value in TEST_ACCOUNT_IDS.values())
    sql(f'UPDATE identity.auth_sessions SET revoked_at=now() WHERE user_id IN ({owners}) AND revoked_at IS NULL',
        'chickenbro_test')
    command('systemctl', 'restart', 'chickenbro-test-api.service', 'chickenbro-test-worker.service')


def disable():
    if not ENV_FILE.is_file():
        raise ValueError('test environment is not configured')
    text = ENV_FILE.read_text().replace('WOW_TEST_LOGIN_ENABLED=1', 'WOW_TEST_LOGIN_ENABLED=0')
    write_private(ENV_FILE, text)
    from server.app.identity.test_accounts import TEST_ACCOUNT_IDS
    owners = ','.join("'" + str(value) + "'::uuid" for value in TEST_ACCOUNT_IDS.values())
    sql(f'UPDATE identity.auth_sessions SET revoked_at=now() WHERE user_id IN ({owners}) AND revoked_at IS NULL',
        'chickenbro_test')
    command('systemctl', 'restart', 'chickenbro-test-api.service', 'chickenbro-test-worker.service')


def publish():
    if not (ROOT / 'current/web/index.html').is_file():
        raise ValueError('verified test Web build is missing')
    api_location = '''location ^~ /test/api/v2/ {
    rewrite ^/test(/api/v2/.*)$ $1 break;
    proxy_pass http://127.0.0.1:8792;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_buffering off;
    proxy_read_timeout 540s;
}
'''
    web_location = '''location = /test { return 302 /test/; }
location ^~ /test/ {
    alias /opt/chickenbro-test/current/web/;
    index index.html;
    add_header Cache-Control "no-store" always;
}
'''
    originals = {}
    updates = {}
    snippets = {}
    for name in ('wow-v2-web', 'api.chickenbro.cloud'):
        path = Path('/etc/nginx/sites-enabled') / name
        text = path.read_text()
        originals[path] = text
        include = f'    include /etc/nginx/snippets/chickenbro-test-{name}.conf;\n'
        marker = 'location ^~ /api/v2/ {'
        if include not in text:
            if text.count(marker) != 1:
                raise ValueError('existing proxy layout requires review')
            text = text.replace(marker, include + marker)
        snippet = Path(f'/etc/nginx/snippets/chickenbro-test-{name}.conf')
        expected = api_location + (web_location if name == 'wow-v2-web' else '')
        if snippet.exists() and snippet.read_text() != expected:
            raise ValueError('existing test proxy differs; inspect before replacing')
        snippets[snippet] = expected
        updates[path] = text
    try:
        for snippet, content in snippets.items():
            snippet.write_text(content)
        for path, content in updates.items():
            path.write_text(content)
        command('nginx', '-t')
        command('systemctl', 'reload', 'nginx')
    except Exception:
        for path, text in originals.items():
            path.write_text(text)
        raise


def prepare(release):
    release = Path(release).resolve()
    if (release.parent != ROOT / 'releases' or re.fullmatch('[0-9a-f]{40}', release.name) is None
            or not (release / 'server/app/main.py').is_file()):
        raise ValueError('release must be an exact commit directory under the managed test root')
    if shutil.disk_usage('/').free < 2 * 1024 ** 3:
        raise ValueError('test environment requires at least 2 GiB free')
    if not Path('/opt/chickenbro-runtime/bin/python').is_file():
        raise ValueError('existing runtime is unavailable; no dependencies will be installed')
    exists = sql("SELECT count(*) FROM pg_database WHERE datname='chickenbro_test'") == '1'
    if not exists:
        sql('CREATE DATABASE chickenbro_test')
        sql(f"COMMENT ON DATABASE chickenbro_test IS '{MARKER}'")
    if sql("SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname='chickenbro_test'") != MARKER:
        raise ValueError('refusing to touch an existing unmanaged database')
    command('sudo', '-u', 'postgres', 'env', f'PYTHONPATH={release}',
            '/opt/chickenbro-runtime/bin/python', '-', input=f'''
from pathlib import Path
import psycopg
from server.migrations.product.apply import apply_product_migrations
with psycopg.connect("dbname=chickenbro_test") as connection:
    apply_product_migrations(connection, Path({str(release / 'server/migrations/product')!r}))
''')
    sql('REVOKE CONNECT ON DATABASE chickenbro_test FROM PUBLIC; GRANT CONNECT ON DATABASE chickenbro_test TO wow_app')
    # Reuse the existing read-only Codex runtime and credential files; no secret copying.
    api = Path('/etc/systemd/system/chickenbro-api.service').read_text()
    api = api.replace('Description=', 'Description=TEST ENVIRONMENT - ', 1)
    api = api.replace('/opt/chickenbro', str(ROOT / 'current'))
    api = api.replace(str(ROOT / 'current') + '-runtime', '/opt/chickenbro-runtime')
    api = api.replace('Environment=WOW_APP_ENV=production', 'Environment=WOW_APP_ENV=test')
    api = api.replace('WOW_API_V2_PORT=8790', 'WOW_API_V2_PORT=8792')
    api = api.replace('__Host-chickenbro-session', '__Host-chickenbro-test-session')
    api = api.replace('__Host-chickenbro-csrf', '__Host-chickenbro-test-csrf')
    api = api.replace('/var/lib/chickenbro/codex-jobs', '/var/lib/chickenbro/test-codex-jobs')
    api = re.sub(r'^ExecStart=.*$', 'ExecStart=/opt/chickenbro-runtime/bin/python -m server.test_login_runtime api', api, flags=re.M)
    api = api.replace('[Service]', '[Service]\nEnvironmentFile=/etc/chickenbro-test-login.env')
    # Put the test digest file last so older environment files cannot enable/disable it accidentally.
    api = api.replace('EnvironmentFile=/etc/chickenbro-test-login.env\n', '')
    api = api.replace('ExecStart=', 'EnvironmentFile=/etc/chickenbro-test-login.env\nExecStart=', 1)
    worker = api.replace('server.test_login_runtime api', 'server.test_login_runtime worker')
    current = ROOT / 'current'
    if current.exists() and not current.is_symlink():
        raise ValueError('managed current path must be a symlink')
    pending = ROOT / 'next'
    if pending.exists() or pending.is_symlink():
        raise ValueError('unfinished test release switch requires inspection')
    pending.symlink_to(release, target_is_directory=True)
    pending.replace(current)
    Path('/etc/systemd/system/chickenbro-test-api.service').write_text(api)
    Path('/etc/systemd/system/chickenbro-test-worker.service').write_text(worker)
    hashes = {account: hashlib.sha256(secrets.token_urlsafe(32).encode()).hexdigest() for account in ('A', 'B')}
    if not ENV_FILE.exists():
        write_private(ENV_FILE, 'WOW_TEST_LOGIN_ENABLED=0\n' + ''.join(
            f'WOW_TEST_LOGIN_{account}_SHA256={hashes[account]}\n' for account in ('A', 'B')))
    command('systemctl', 'daemon-reload')
    command('systemctl', 'enable', '--now', 'chickenbro-test-api.service', 'chickenbro-test-worker.service')
    command('systemctl', 'restart', 'chickenbro-test-api.service', 'chickenbro-test-worker.service')
    return {'database': 'chickenbro_test', 'releaseCommit': release.name, 'port': 8792,
            'credentialSetup': 'Run scripts/configure-test-login.py on your computer.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--release-dir')
    parser.add_argument('--configure', action='store_true')
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--disable', action='store_true')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({'status': 'dry_run', 'database': 'chickenbro_test', 'root': str(ROOT),
                          'productionWrites': False, 'requiresExistingRuntime': True}))
        return
    if os.geteuid() != 0:
        raise ValueError('apply requires the existing host administrator')
    if args.disable:
        disable()
        print(json.dumps({'status': 'disabled', 'oldTestSessions': 'revoked'}))
    elif args.publish:
        publish()
        print(json.dumps({'status': 'published', 'url': 'https://www.chickenbro.cloud/test/'}))
    elif args.configure:
        configure(json.load(sys.stdin))
        print(json.dumps({'status': 'configured', 'oldTestSessions': 'revoked'}))
    else:
        print(json.dumps(prepare(args.release_dir)))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Test environment operation failed; inspect managed paths without exposing credentials.') from None

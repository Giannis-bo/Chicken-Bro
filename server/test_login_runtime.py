"""Start the isolated test runtime using existing host credentials only in memory."""
import csv
import os
from pathlib import Path
import sys
from urllib.parse import urlparse


def prepare_environment(source, read_text=lambda path: Path(path).read_text()):
    env = dict(source)
    database = urlparse(env.get('WOW_DATABASE_URL', ''))
    if (database.scheme not in {'postgresql', 'postgres'} or database.path != '/chickenbro_prod'
            or database.query or database.fragment or not database.username):
        raise ValueError('unexpected source database configuration')
    password = database.password
    if password is None:
        expected = [database.hostname or 'localhost', str(database.port or 5432),
                    'chickenbro_prod', database.username]
        for line in read_text(env.get('PGPASSFILE', '')).splitlines():
            if not line or line.startswith('#'):
                continue
            fields = next(csv.reader([line], delimiter=':', escapechar='\\', quoting=csv.QUOTE_NONE))
            if len(fields) == 5 and all(a == '*' or a == b for a, b in zip(fields[:4], expected)):
                password = fields[4]
                break
    if not password:
        raise ValueError('existing runtime database credential is unavailable')
    env['PGPASSWORD'] = password
    env['WOW_DATABASE_URL'] = database._replace(path='/chickenbro_test').geturl()
    # EnvironmentFile values override systemd Environment=; enforce isolation here.
    env.update({
        'WOW_APP_ENV': 'test', 'WOW_API_V2_HOST': '127.0.0.1', 'WOW_API_V2_PORT': '8792',
        'WOW_WEB_ORIGIN': 'https://www.chickenbro.cloud',
        'WOW_WEB_COOKIE_NAME': '__Host-chickenbro-test-session',
        'WOW_WEB_CSRF_COOKIE_NAME': '__Host-chickenbro-test-csrf',
        'WOW_WORKER_V2_HEARTBEAT_PATH': '/var/lib/chickenbro/test-worker-heartbeat.json',
        'WOW_CODEX_JOBS_DIR': '/var/lib/chickenbro/test-codex-jobs',
        'WOW_WEB_SESSION_TTL_SECONDS': '86400',
    })
    return env


if __name__ == '__main__':
    if sys.argv[1:] not in (['api'], ['worker']):
        raise SystemExit('usage: python -m server.test_login_runtime api|worker')
    try:
        os.environ.update(prepare_environment(os.environ))
    except Exception:
        raise SystemExit('Test runtime configuration failed; no service was started.') from None
    args = (['-m', 'uvicorn', 'server.app.main:app', '--host', '127.0.0.1', '--port', '8792']
            if sys.argv[1] == 'api' else
            ['-m', 'server.app.worker.main', '--worker-id', 'chickenbro-test-worker'])
    os.execv(sys.executable, [sys.executable, *args])

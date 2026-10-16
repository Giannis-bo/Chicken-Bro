"""Loopback-only cloud acceptance harness with formal synthetic sessions and real sources."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Thread
from uuid import uuid4

import psycopg
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.app.main import create_app
from server.app.platform.config import AppSettings
from server.app.identity.domain import digest, new_opaque_token
from server.app.identity.repository import PostgresIdentityRepository
from server.app.worker.main import build_worker
from server.app.platform.worker_heartbeat import WorkerHeartbeatWriter

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://simc-characters-candidate.invalid'
DSN = os.environ['WOW_DATABASE_URL']
PRIVATE = Path(os.environ['SIMC_CHARACTER_PRIVATE'])
connect = lambda: psycopg.connect(DSN)
identity = PostgresIdentityRepository(connect)
sessions = {}
now = datetime.now(timezone.utc)
for name in ('A', 'B'):
    owner = identity.upsert_qq_identity(appid='1', openid=f'simc-character-{name}-{uuid4()}',
        profile={'nickname': f'角色绑定验证 {name}'}, now=now)
    token, csrf = new_opaque_token(), new_opaque_token()
    identity.issue_auth_session(token_hash=digest(token), user_id=owner,
        kind='web_cookie', expires_at=now+timedelta(hours=2))
    sessions[name] = {'token': token, 'csrf': csrf, 'owner': str(owner)}
PRIVATE.mkdir(mode=0o700, exist_ok=True)
fixture = PRIVATE / 'sessions.json'
fixture.write_text(json.dumps(sessions))
fixture.chmod(0o600)
settings = AppSettings(environment='candidate', database_url=DSN, host='127.0.0.1', port=8885,
    web_origin=ORIGIN, qq_appid='1', qq_redirect_uri=ORIGIN+'/api/v2-candidate/auth/qq/callback',
    web_cookie_name='__Host-simc-characters-session', web_csrf_cookie_name='__Host-chickenbro-csrf')
app = create_app(settings=settings)
web = ROOT / 'apps/mini-taro/dist/h5'
app.mount('/static', StaticFiles(directory=web/'static'), name='static')
app.mount('/brand', StaticFiles(directory=web/'brand'), name='brand')
@app.get('/{path:path}')
def frontend(path: str):
    target = (web / path).resolve()
    if target.is_relative_to(web.resolve()) and target.is_file():
        return FileResponse(target)
    return FileResponse(web / 'index.html')
worker = build_worker(worker_id='simc-characters-candidate', lease_seconds=120)
worker.service_heartbeat = WorkerHeartbeatWriter(path=PRIVATE/'worker-heartbeat.json', environment='candidate', worker_id='simc-characters-candidate').write
Thread(target=lambda: worker.run_forever(lambda: False), daemon=True).start()

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
sys.path.insert(0, '/opt/chickenbro')
pid = subprocess.check_output(['systemctl', 'show', 'chickenbro-api.service', '-p', 'MainPID', '--value'], text=True).strip()
env = dict(x.split('=', 1) for x in Path('/proc/' + pid + '/environ').read_text().split('\0') if '=' in x)
os.environ.update(env)
from server.app.platform.config import AppSettings
from server.app.platform.postgres import PostgresConnectionFactory
from server.accept_chickenbro_candidate import PostgresAcceptanceSeeder, CandidateHttpGateway, run_candidate_acceptance, AcceptanceError
# The legacy acceptance core predates compiler v3. Bind its strict comparisons
# to this reviewed release's expected revision; never derive it from API output.
import server.accept_chickenbro_candidate as acceptance
acceptance.COMPILER_REVISION = 'chickenbro-simc-compiler-v3'
assert env.get('WOW_SIMC_COMPILER_REVISION') == acceptance.COMPILER_REVISION
settings = AppSettings.from_env(os.environ)
factory = PostgresConnectionFactory(settings).connection
seed = None
try:
    seed = PostgresAcceptanceSeeder(factory).seed(expected_database='chickenbro_prod', app_context=settings.wechat_appid,
        now=datetime.now(timezone.utc), use_latest_ready_snapshot=True)
    manifest = json.loads(Path(sys.argv[1]).read_text())
    evidence = run_candidate_acceptance(seed, CandidateHttpGateway(seed, www_origin='https://www.chickenbro.cloud',
        api_origin='https://api.chickenbro.cloud', prefix='/api/v2', csrf_cookie_name='__Host-chickenbro-csrf'),
        expected_commit=manifest['commit'], web_build_identity=manifest['webBuildIdentity'],
        weapp_build_identity=manifest['weappBuildIdentity'], prefix='/api/v2')
    evidence['status'] = 'production_automated_business_smoke_passed'
    evidence['expectedCompilerRevision'] = acceptance.COMPILER_REVISION
    evidence['transportScope'].update(miniBearer='public_production_api', webCookieCsrf='public_production_api',
                                     migratedReadySnapshot=True)
    print(json.dumps(evidence))
except Exception as error:
    print(json.dumps({'status':'failed','code':error.code if isinstance(error, AcceptanceError) else type(error).__name__}))
    raise SystemExit(1) from None
finally:
    if seed:
        with factory() as connection:
            with connection.cursor() as cursor:
                for token in (seed.mini_token, seed.other_mini_token):
                    cursor.execute('UPDATE identity.auth_sessions SET revoked_at=now() WHERE token_hash=%s AND revoked_at IS NULL',
                                   (hashlib.sha256(token.encode()).hexdigest(),))
                cursor.execute("UPDATE identity.users SET status='disabled', updated_at=now() WHERE id=%s", (seed.other_user_id,))

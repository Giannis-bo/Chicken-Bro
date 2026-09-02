const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

const script = fs.readFileSync('server/deploy_web_v2_lighthouse.sh', 'utf8')
const service = fs.readFileSync('server/wow-v2-api.service', 'utf8')
const workerService = fs.readFileSync('server/wow-v2-worker.service', 'utf8')
const nginx = fs.readFileSync('server/wow-v2-web.nginx', 'utf8')

test('prototype candidate deployment packages and backs up the complete additive v2 schema', () => {
  for (const migration of [
    '0038_chickenbro_simc_platform_foundation.sql',
    '0039_wechat_web_login_sessions.sql',
    '0040_web_prototype_sessions.sql',
  ]) {
    assert.match(script, new RegExp(migration.replaceAll('.', '\\.') ))
  }
  assert.match(script, /pg_dump[\s\S]*postgres-target\.dump/)
  assert.match(script, /sha256sum[\s\S]*candidate package checksum mismatch/)
  assert.match(script, /WOW_WEB_PROTOTYPE_ENABLED/)
})

test('prototype candidate records a scoped database backup when unrelated tables are not dumpable', () => {
  assert.match(script, /postgres-target\.scope/)
  assert.match(script, /pg_dump[\s\S]*--table=identity\.users[\s\S]*--table=ops\.schema_migrations/)
  assert.match(script, /full database dump failed|scoped database backup/i)
})

test('prototype candidate runs additive migrations as the existing wow_migrator owner', () => {
  assert.match(script, /WOW_DATABASE_MIGRATOR_URL/)
  assert.match(script, /SET ROLE wow_migrator/)
  assert.match(script, /sudo -u postgres env -u PGPASSFILE -u PGHOST -u PGPORT -u PGUSER/)
  assert.match(script, /migration_auth_mode=/)
  assert.match(script, /migration_is_applied/)
  assert.match(script, /skipped_migration=/)
})

test('prototype candidate deployment preserves isolated service and verifies public boundaries', () => {
  assert.match(service, /^EnvironmentFile=-\/etc\/wow-v2-api\.env$/m)
  assert.match(service, /^EnvironmentFile=-\/etc\/wow-v2-source\.env$/m)
  assert.match(service, /^Environment=WOW_DATABASE_RUNTIME=postgres_only$/m)
  assert.match(service, /^Environment=WOW_CODEX_BIN=\/usr\/local\/bin\/codex$/m)
  assert.match(service, /^Environment=WOW_CODEX_HOME=\/home\/ubuntu\/\.codex$/m)
  assert.match(service, /^Environment=WOW_CODEX_JOBS_DIR=\/var\/lib\/wow-backend\/codex-jobs$/m)
  assert.match(service, /^Environment=WOW_CODEX_PROFILE=chickenbro-native$/m)
  for (const variable of ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY', 'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy']) {
    assert.match(service, new RegExp('^Environment=' + variable + '=.+$', 'm'))
  }
  assert.match(service, /^Environment=ALL_PROXY=http:\/\/127\.0\.0\.1:7890$/m)
  assert.match(service, /^Environment=all_proxy=http:\/\/127\.0\.0\.1:7890$/m)
  assert.doesNotMatch(service, /^Environment=(ALL_PROXY|all_proxy)=socks5h:\/\//m)
  assert.match(service, /^Environment=WOW_CHICKENBRO_CODEX_ENABLED=1$/m)
  assert.match(service, /^Environment=WOW_WEB_PROTOTYPE_ENABLED=1$/m)
  assert.match(service, /^Environment=WOW_SIMC_SUPPORTED_SPECS=shaman:elemental$/m)
  assert.match(script, /TLS_CERT=.*www\.chickenbro\.cloud\/www\.chickenbro\.cloud_bundle\.pem/)
  assert.match(nginx, /ssl_certificate \/etc\/nginx\/ssl\/www\.chickenbro\.cloud\/www\.chickenbro\.cloud_bundle\.pem/)
  assert.match(nginx, /ssl_certificate_key \/etc\/nginx\/ssl\/www\.chickenbro\.cloud\/www\.chickenbro\.cloud\.key/)
  assert.match(script, /WOW_WEB_PROTOTYPE_ENABLED.*1|prototype.*enabled/i)
  assert.match(script, /WOW_CHICKENBRO_CODEX_ENABLED.*1|Codex.*enabled/i)
  assert.match(script, /WOW_CODEX_BIN.*-x|codex.*executable/i)
  assert.match(script, /chickenbro-native\.config\.toml\.template/)
  assert.match(script, /chickenbro_native_mcp\.py/)
  assert.match(script, /CODEX_PROFILE_PATH/)
  assert.match(script, /__CHICKENBRO_CANDIDATE_ROOT__/)
  assert.match(script, /codex-profile-state/)
  assert.match(script, /WOW_V2_SKIP_DEPENDENCY_INSTALL/)
  assert.match(script, /wow-v2-source\.env/)
  assert.match(script, /WOW_WARCRAFTLOGS_CLIENT_ID/)
  assert.match(script, /WOW_RAIDERIO_API_KEY/)
  assert.match(script, /mode 0600/)
  assert.match(script, /prototype\/sessions/)
  assert.match(script, /\/api\/v2\/me/)
  assert.match(script, /AUTH_REQUIRED/)
  assert.match(script, /127\.0\.0\.1:8790\/health/)
  assert.match(script, /www\.chickenbro\.cloud\/.*https|--resolve www\.chickenbro\.cloud:443:127\.0\.0\.1 https:\/\/www\.chickenbro\.cloud\//)
  assert.match(script, /v2-worker\.service/)
  assert.match(script, /v2-worker\.service[\s\S]*rollback_v2/)
  assert.match(script, /tar -xzf "\$\{BACKUP_DIR\}\/v2-paths\.tgz"[\s\S]*server\/app/)
  assert.match(script, /wait_for_http[\s\S]*for attempt in \{1\.\.15\}/)
  assert.match(script, /wait_for_worker[\s\S]*for attempt in \{1\.\.15\}/)
  assert.match(script, /systemctl stop "\$\{V2_SERVICE\}" "\$\{V2_WORKER_SERVICE\}"/)
  assert.match(script, /worker_pid=.*systemctl show/)
})

test('candidate starts the SimC worker as a separate isolated service', () => {
  assert.match(workerService, /^EnvironmentFile=-\/etc\/wow-v2-api\.env$/m)
  assert.match(workerService, /^Environment=WOW_APP_ENV=production$/m)
  assert.match(workerService, /^Environment=WOW_DATABASE_RUNTIME=postgres_only$/m)
  assert.match(workerService, /^Environment=WOW_SIMC_SUPPORTED_SPECS=shaman:elemental$/m)
  assert.match(workerService, /-m server\.app\.worker\.main/)
  assert.doesNotMatch(workerService, /wow-backend\.env/)
  assert.match(script, /wow-v2-worker/)
  assert.match(script, /server\/wow-v2-worker\.service/)
  assert.match(script, /enable --now[\s\S]*V2_SERVICE[\s\S]*V2_WORKER_SERVICE/)
  assert.match(nginx, /proxy_buffering off/)
  assert.match(nginx, /proxy_read_timeout 210s/)
})

const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const crypto = require('node:crypto')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

function read(path) {
  return fs.readFileSync(path, 'utf8')
}

function readinessValidatorSource() {
  const script = read('server/deploy_chickenbro_candidate_lighthouse.sh')
  const marker = 'import hashlib\nimport json\nimport sys\nimport uuid\nfrom pathlib import Path\n\noutput_path = Path(sys.argv[1])'
  const start = script.indexOf(marker)
  const end = script.indexOf('\nPY\n)"', start)
  assert.ok(start >= 0 && end > start, 'embedded readiness validator must be extractable')
  return script.slice(start, end)
}

function backupManifestValidatorSource() {
  const script = read('server/deploy_chickenbro_candidate_lighthouse.sh')
  const marker = 'import hashlib\nimport json\nimport os\nimport re\nimport sys\nfrom datetime import datetime\nfrom pathlib import Path\n\nmanifest_path = Path(sys.argv[1])'
  const start = script.indexOf(marker)
  const end = script.indexOf('\nPY\n\nBACKUP_DEVICE=', start)
  assert.ok(start >= 0 && end > start, 'embedded backup manifest validator must be extractable')
  return script.slice(start, end)
}

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex')
}

function runBackupManifestValidator(mutate = (payload) => payload) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'chickenbro-backup-manifest-'))
  try {
    const archive = path.join(directory, 'backup.age')
    const restoreEvidence = path.join(directory, 'restore-evidence.json')
    const manifest = path.join(directory, 'restore-verified.json')
    const archiveBytes = Buffer.from('encrypted-backup-fixture')
    const restoreEvidenceBytes = Buffer.from('{"status":"passed"}\n')
    fs.writeFileSync(archive, archiveBytes, { mode: 0o600 })
    fs.writeFileSync(restoreEvidence, restoreEvidenceBytes, { mode: 0o600 })
    const payload = mutate({
      schemaVersion: 'chickenbro-independent-backup-v1',
      backupId: 'backup-20260903',
      sourceDatabase: 'wow_test',
      archivePath: archive,
      archiveSha256: sha256(archiveBytes),
      archiveBytes: archiveBytes.length,
      createdAt: '2026-09-03T00:00:00Z',
      deviceId: String(fs.statSync(directory).dev),
      encrypted: true,
      sensitiveConfigurationEncrypted: true,
      encryption: { scheme: 'age', keyReferenceSha256: 'a'.repeat(64) },
      restoreVerified: true,
      restore: {
        targetDatabase: 'chickenbro_restore_verify_20260903',
        commandExitCode: 0,
        schemaVerified: true,
        rowSampleVerified: true,
        hashSampleVerified: true,
        verifiedAt: '2026-09-03T00:30:00Z',
        operator: 'reviewed-operator',
        evidencePath: restoreEvidence,
        evidenceSha256: sha256(restoreEvidenceBytes),
      },
    })
    fs.writeFileSync(manifest, `${JSON.stringify(payload)}\n`, { mode: 0o600 })
    return spawnSync('python3', ['-', manifest], {
      encoding: 'utf8',
      input: backupManifestValidatorSource(),
    })
  } finally {
    fs.rmSync(directory, { recursive: true, force: true })
  }
}

function readinessPayload(status = 'partial', overrides = {}) {
  return {
    status,
    requestId: '00000000-0000-4000-8000-000000000001',
    components: {
      database: { status: 'ready', code: '' },
      wechat_mini: { status: 'ready', code: '' },
      worker: { status: 'unconfigured', code: 'WORKER_NOT_CONFIGURED' },
      ...overrides,
    },
  }
}

function runReadinessValidator(payloads) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'chickenbro-readiness-'))
  try {
    const output = path.join(directory, 'summary.json')
    const descriptors = Object.entries(payloads).map(([surface, payload]) => {
      const input = path.join(directory, `${surface}.json`)
      fs.writeFileSync(input, `${JSON.stringify(payload)}\n`, { mode: 0o600 })
      return `${surface}=${input}`
    })
    const result = spawnSync('python3', ['-', output, ...descriptors], {
      encoding: 'utf8',
      input: readinessValidatorSource(),
    })
    return {
      ...result,
      summary: fs.existsSync(output) ? JSON.parse(fs.readFileSync(output, 'utf8')) : null,
    }
  } finally {
    fs.rmSync(directory, { recursive: true, force: true })
  }
}

test('formal production and candidate services have separate roots, ports and secret files', () => {
  const productionApi = read('server/chickenbro-api.service')
  const candidateApi = read('server/chickenbro-api-candidate.service')
  const worker = read('server/chickenbro-worker.service')
  const candidateWorker = read('server/chickenbro-worker-candidate.service')

  assert.match(productionApi, /WorkingDirectory=\/opt\/chickenbro/)
  assert.match(productionApi, /EnvironmentFile=-?\/etc\/chickenbro-api\.env/)
  assert.ok(
    productionApi.indexOf('EnvironmentFile=-/etc/chickenbro-source.env')
      < productionApi.indexOf('EnvironmentFile=-/etc/chickenbro-api.env'),
    'production API env must override imported source credentials',
  )
  assert.match(productionApi, /WOW_APP_ENV=production/)
  assert.match(productionApi, /WOW_API_V2_HOST=127\.0\.0\.1/)
  assert.match(productionApi, /WOW_API_V2_PORT=8790/)
  assert.match(productionApi, /WOW_WEB_PROTOTYPE_ENABLED=0/)
  assert.match(productionApi, /pages\/auth\/web-login-confirm/)

  assert.match(candidateApi, /WorkingDirectory=\/opt\/chickenbro-candidate/)
  assert.match(candidateApi, /EnvironmentFile=-?\/etc\/chickenbro-api-candidate\.env/)
  assert.ok(
    candidateApi.indexOf('EnvironmentFile=-/etc/chickenbro-source-candidate.env')
      < candidateApi.indexOf('EnvironmentFile=-/etc/chickenbro-api-candidate.env'),
    'candidate API env must override imported source credentials',
  )
  assert.match(candidateApi, /WOW_APP_ENV=candidate/)
  assert.match(candidateApi, /WOW_API_V2_HOST=127\.0\.0\.1/)
  assert.match(candidateApi, /WOW_API_V2_PORT=8791/)
  assert.match(candidateApi, /WOW_WEB_COOKIE_NAME=__Host-chickenbro-candidate-session/)
  assert.match(candidateApi, /WOW_WEB_CSRF_COOKIE_NAME=__Host-chickenbro-candidate-csrf/)
  assert.match(candidateApi, /WOW_WEB_PROTOTYPE_ENABLED=0/)
  assert.match(candidateApi, /WOW_WECHAT_ENV_VERSION=trial/)
  assert.match(candidateApi, /WOW_WECHAT_CHECK_PATH=1/)

  assert.match(worker, /EnvironmentFile=-?\/etc\/chickenbro-worker\.env/)
  assert.match(worker, /\/opt\/chickenbro-runtime\/bin\/python -m server\.app\.worker\.main/)
  assert.match(worker, /NoNewPrivileges=true/)
  assert.match(worker, /ProtectSystem=strict/)
  assert.match(worker, /ReadWritePaths=\/var\/lib\/chickenbro/)

  assert.match(candidateWorker, /WorkingDirectory=\/opt\/chickenbro-candidate/)
  assert.match(candidateWorker, /EnvironmentFile=-?\/etc\/chickenbro-worker-candidate\.env/)
  assert.match(candidateWorker, /PYTHONPATH=\/opt\/chickenbro-candidate/)
  assert.match(candidateWorker, /worker-id chickenbro-simc-candidate-worker/)

  for (const service of [productionApi, candidateApi, worker, candidateWorker]) {
    assert.doesNotMatch(service, /WOW_WEB_PROTOTYPE_ENABLED=1/)
    assert.doesNotMatch(service, /wow-v2|wow-mini-program-candidate|\/opt\/wow-mini-program/)
  }
})

test('nginx keeps production stable while exposing path-isolated candidate routes', () => {
  const nginx = read('server/chickenbro-web.nginx')

  assert.match(nginx, /# BEGIN CHICKENBRO CANDIDATE WWW/)
  assert.match(nginx, /location = \/web-candidate/)
  assert.match(nginx, /location \^~ \/web-candidate\//)
  assert.match(nginx, /\/var\/www\/chickenbro-candidate\/current\//)
  assert.match(nginx, /location \^~ \/api\/v2-candidate\//)
  assert.match(nginx, /proxy_pass http:\/\/127\.0\.0\.1:8791\/api\/v2\//)
  assert.match(nginx, /# BEGIN CHICKENBRO CANDIDATE API/)
  assert.doesNotMatch(nginx, /proxy_pass http:\/\/127\.0\.0\.1:8791\/api\/v2-candidate\//)
  assert.doesNotMatch(nginx, /server_name|listen 443|location \^~ \/api\/v2\//)
})

test('candidate deploy is content-addressed, candidate-only, reversible and exact-smoked', () => {
  const script = read('server/deploy_chickenbro_candidate_lighthouse.sh')

  assert.match(script, /MODE="dry-run"/)
  assert.match(script, /--apply/)
  assert.match(script, /CANDIDATE_ROOT="\/opt\/chickenbro-candidate"/)
  assert.match(script, /CANDIDATE_DATABASE="chickenbro_candidate"/)
  assert.match(script, /CANDIDATE_PORT="8791"/)
  assert.match(script, /CANDIDATE_PREFIX="\/api\/v2-candidate"/)
  assert.match(script, /CANDIDATE_WORKER_SERVICE="chickenbro-worker-candidate"/)
  assert.match(script, /CANDIDATE_WORKER_ENV="\/etc\/chickenbro-worker-candidate\.env"/)
  assert.match(script, /LEGACY_CANDIDATE_SERVICE="wow-v2-api-candidate"/)
  assert.match(script, /service_state "\$\{LEGACY_CANDIDATE_SERVICE\}"/)
  assert.match(script, /enable_state "\$\{LEGACY_CANDIDATE_SERVICE\}"/)
  assert.match(script, /systemctl stop "\$\{LEGACY_CANDIDATE_SERVICE\}"/)
  assert.match(script, /systemctl disable "\$\{LEGACY_CANDIDATE_SERVICE\}"/)
  assert.match(script, /systemctl mask --runtime "\$\{LEGACY_CANDIDATE_SERVICE\}"/)
  assert.match(script, /systemctl unmask --runtime "\$\{LEGACY_CANDIDATE_SERVICE\}"/)
  assert.match(script, /legacyCandidateServiceRetired/)
  assert.doesNotMatch(script, /WORKER_SERVICE="chickenbro-worker"/)
  assert.doesNotMatch(script, /WORKER_ENV="\/etc\/chickenbro-worker\.env"/)
  assert.match(script, /WOW_API_V2_PREFIX="\$\{CANDIDATE_PREFIX\}"/)
  assert.match(script, /WOW_WEB_AUTH_API_PREFIX="\$\{CANDIDATE_PREFIX\}"/)
  assert.match(script, /WOW_WEB_CSRF_COOKIE_NAME="__Host-chickenbro-candidate-csrf"/)
  assert.match(script, /CANDIDATE_PGPASSFILE="\/etc\/chickenbro-api-candidate\.pgpass"/)
  assert.match(script, /WOW_DEPLOY_START_ASYNC_SYNCS="0"/)
  assert.match(script, /WOW_DEPLOY_START_ASYNC_SYNCS.*must remain 0/)

  assert.match(script, /SOURCE_ARCHIVE_SHA256/)
  assert.match(script, /chickenbro-candidate-\$\{SOURCE_ARCHIVE_SHA256\}\.tar\.gz/)
  assert.match(script, /SOURCE_MANIFEST_SHA256/)
  assert.match(script, /sha256sum --check/)
  assert.match(script, /DEPLOYED_MANIFEST_SHA256/)
  assert.match(script, /EXPECTED_COMMIT/)
  assert.match(script, /git[^\n]+rev-parse HEAD/)

  assert.match(script, /server\/migrations\/product\/0001_chickenbro_simc_core\.sql/)
  assert.match(script, /server\/migrations\/product\/0002_chat_idempotent_replay\.sql/)
  assert.match(script, /import fastapi, httpx, psycopg, uvicorn/)
  assert.match(script, /server\/accept_chickenbro_candidate\.py/)
  assert.match(script, /run build:weapp/)
  assert.match(script, /apps\/mini-taro\/dist\/weapp/)
  assert.match(script, /WEAPP_BUILD_IDENTITY/)
  assert.match(script, /WeApp wow-build gitHead mismatch/)
  assert.match(script, /wow-weapp-build-v1/)
  assert.match(script, /"\$\{RUNTIME_ROOT\}\/bin\/python" -m server\.migrations\.product\.postgres_legacy/)
  assert.match(script, /captured-watermark/)
  assert.match(script, /reconciliation.*matched/)
  assert.match(script, /candidate\.pgpass/)
  assert.match(script, /wow_test.*wow_app/)
  assert.match(script, /legacy DSN is not the reviewed local wow_app identity/)
  assert.match(script, /target = f"postgresql:\/\/wow_app@127\.0\.0\.1:5432\//)
  assert.match(script, /--host=127\.0\.0\.1[\s\S]*--port=5432[\s\S]*--username=wow_app[\s\S]*--dbname=wow_test/)
  assert.doesNotMatch(script, /psql[^\n]+--dbname="\$\{WOW_DATABASE_URL\}"/)
  assert.match(script, /for public_origin in https:\/\/www\.chickenbro\.cloud https:\/\/api\.chickenbro\.cloud/)
  assert.match(script, /"\$\{public_origin\}\$\{CANDIDATE_PREFIX\}\/health\/readiness"/)
  assert.doesNotMatch(script, /0040_web_prototype_sessions|server\/migrations\/postgres\/0040/)

  assert.match(script, /rollback_candidate\(\)/)
  assert.match(script, /trap rollback_candidate EXIT/)
  assert.match(script, /readlink -f -- "\$\{API_NGINX_SITE\}"/)
  assert.match(script, /nginx -t/)
  assert.match(script, /systemctl is-active --quiet "\$\{CANDIDATE_API_SERVICE\}"/)
  assert.match(script, /systemctl is-active --quiet "\$\{CANDIDATE_WORKER_SERVICE\}"/)
  assert.match(script, /\$\{CANDIDATE_PREFIX\}\/health\/readiness/)
  assert.match(script, /readiness-summary\.json/)
  assert.match(script, /required readiness component is not ready/)
  assert.match(script, /candidate readiness contains a blocked component/)
  assert.match(script, /readiness payloads disagree across candidate origins/)
  assert.match(script, /\$\{CANDIDATE_PREFIX\}\/me/)
  assert.match(script, /\$\{CANDIDATE_PREFIX\}\/chat\/conversations/)
  assert.match(script, /\$\{CANDIDATE_PREFIX\}\/simc\/jobs/)
  assert.match(script, /formal-route-\$\{origin_label\}-\$\{route_label\}\.json/)
  assert.match(script, /formal anonymous route did not return AUTH_REQUIRED/)

  assert.doesNotMatch(script, /prototype(?:\/|[-_])login|prototype_sessions/)
  assert.doesNotMatch(script, /systemctl (?:start|restart|enable).*wow-(?:data|community|gear|stat|talent|websim|recommended)/)
  assert.doesNotMatch(script, /(?:DROP|ALTER|TRUNCATE|DELETE|UPDATE|INSERT)[^\n]*wow_test/i)
  assert.doesNotMatch(script, /WOW_DATABASE_URL=.*wow_test/)
})

test('candidate deploy rejects attempts to enable legacy async synchronizers before any remote work', () => {
  const result = spawnSync('bash', ['server/deploy_chickenbro_candidate_lighthouse.sh', '--dry-run'], {
    cwd: process.cwd(),
    encoding: 'utf8',
    env: { ...process.env, WOW_DEPLOY_START_ASYNC_SYNCS: '1' },
  })

  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /WOW_DEPLOY_START_ASYNC_SYNCS must remain 0/)
  assert.doesNotMatch(`${result.stdout}\n${result.stderr}`, /Running independent-backup|Building the exact candidate/)
})

test('candidate deploy records identities without serializing credentials', () => {
  const script = read('server/deploy_chickenbro_candidate_lighthouse.sh')

  assert.match(script, /branchCommit/)
  assert.match(script, /sourceArchiveSha256/)
  assert.match(script, /deployedManifestSha256/)
  assert.match(script, /databaseMigrationIds/)
  assert.match(script, /apiServiceIdentity/)
  assert.match(script, /candidateWorkerServiceIdentity/)
  assert.match(script, /codexRuntimeIdentity/)
  assert.match(script, /simcRuntimeIdentity/)
  assert.match(script, /webBuildIdentity/)
  assert.match(script, /wwwNginxIdentity/)
  assert.match(script, /apiNginxIdentity/)
  assert.match(script, /rollbackManifestSha256/)
  assert.match(script, /candidate-acceptance\.json/)
  assert.match(script, /automated-acceptance\.json/)
  assert.match(script, /"\$\{RUNTIME_ROOT\}\/bin\/python" -m server\.accept_chickenbro_candidate/)
  assert.match(script, /--expected-database "\$\{CANDIDATE_DATABASE\}"/)
  assert.match(script, /automated_candidate_acceptance_passed/)
  assert.match(script, /"realDualClientAcceptance": "pending"/)
  assert.match(script, /"status": "candidate_deployed_user_acceptance_pending"/)
  assert.match(script, /partial_not_promotable/)
  assert.doesNotMatch(script, /candidate_deployed_automated_smoke_only/)
  assert.match(script, /weappBuildIdentity/)

  assert.doesNotMatch(script, /cat .*\.env|printenv|env \|/)
  assert.doesNotMatch(script, /echo .*WOW_(?:DATABASE_URL|WECHAT_SECRET|LIGHTHOUSE_PASSWORD)/)
})

test('candidate backup gate requires encrypted archive and complete restore proof', () => {
  const valid = runBackupManifestValidator()
  assert.equal(valid.status, 0, valid.stderr)

  for (const mutate of [
    (payload) => ({ ...payload, encrypted: false }),
    (payload) => ({ ...payload, sensitiveConfigurationEncrypted: false }),
    (payload) => ({ ...payload, archiveSha256: '0'.repeat(64) }),
    (payload) => ({ ...payload, restore: { ...payload.restore, commandExitCode: 1 } }),
    (payload) => ({ ...payload, restore: { ...payload.restore, targetDatabase: 'wow_test' } }),
    (payload) => ({ ...payload, restore: { ...payload.restore, schemaVerified: false } }),
  ]) {
    const rejected = runBackupManifestValidator(mutate)
    assert.notEqual(rejected.status, 0)
    assert.match(rejected.stderr, /independent backup manifest is not restore-verified/)
  }
})

test('candidate readiness keeps partial literal and non-promotable across all origins', () => {
  const payload = readinessPayload()
  const result = runReadinessValidator({
    internal: payload,
    www: { ...payload, requestId: '00000000-0000-4000-8000-000000000002' },
    api: { ...payload, requestId: '00000000-0000-4000-8000-000000000003' },
  })

  assert.equal(result.status, 0, result.stderr)
  assert.equal(result.stdout.trim(), 'partial')
  assert.equal(result.summary.status, 'partial')
  assert.equal(result.summary.disposition, 'partial_not_promotable')
  assert.equal(result.summary.observations.length, 3)
})

test('candidate readiness fails closed on blocked or cross-origin disagreement', () => {
  const blocked = runReadinessValidator({
    internal: readinessPayload('blocked', { worker: { status: 'blocked', code: 'WORKER_DOWN' } }),
  })
  assert.notEqual(blocked.status, 0)
  assert.match(blocked.stderr, /candidate readiness contains a blocked component/)

  const partial = readinessPayload()
  const disagreed = runReadinessValidator({
    internal: partial,
    www: {
      ...partial,
      requestId: '00000000-0000-4000-8000-000000000002',
      components: { ...partial.components, worker: { status: 'ready', code: '' } },
    },
  })
  assert.notEqual(disagreed.status, 0)
  assert.match(disagreed.stderr, /readiness payloads disagree across candidate origins/)
})

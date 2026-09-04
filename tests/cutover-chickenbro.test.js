const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const crypto = require('node:crypto')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const scriptPath = 'server/cutover_chickenbro_lighthouse.sh'

function readScript() {
  return fs.readFileSync(scriptPath, 'utf8')
}

function functionBody(source, name, nextName) {
  const start = source.indexOf(`${name}() {`)
  const end = source.indexOf(`\n${nextName}() {`, start)
  assert.ok(start >= 0 && end > start, `${name} must be extractable`)
  return source.slice(start, end)
}

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex')
}

function evidenceValidatorSource() {
  const source = readScript()
  const marker = 'import hashlib\nimport json\nimport re\nimport sys\nfrom datetime import datetime\nfrom pathlib import Path\n\nbackup_path, candidate_path, real_path'
  const start = source.indexOf(marker)
  const end = source.indexOf('\nPY\n\nif [[ "${BACKUP_MODE}" == "independent" ]]', start)
  assert.ok(start >= 0 && end > start, 'embedded cutover evidence validator must be extractable')
  return source.slice(start, end)
}

function runEvidenceValidator(
  mutate = ({ backup, candidate, real, automated }) => ({
  backup,
  candidate,
  real,
  automated,
  }),
  backupMode = 'independent',
) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'chickenbro-cutover-evidence-'))
  const candidateRoot = path.join(root, 'candidate-runs', 'run-1')
  fs.mkdirSync(candidateRoot, { recursive: true, mode: 0o700 })
  try {
    const commit = 'a'.repeat(40)
    const inventorySha = 'b'.repeat(64)
    const backupManifestSha = 'c'.repeat(64)
    const archive = path.join(root, 'backup.age')
    const restoreEvidence = path.join(root, 'restore.json')
    const automatedPath = path.join(candidateRoot, 'automated-acceptance.json')
    const candidatePath = path.join(candidateRoot, 'candidate-acceptance.json')
    const realPath = path.join(candidateRoot, 'real-acceptance.json')
    const archiveBytes = Buffer.from('encrypted-archive')
    const restoreBytes = Buffer.from('{"status":"passed"}\n')
    fs.writeFileSync(archive, archiveBytes, { mode: 0o600 })
    fs.writeFileSync(restoreEvidence, restoreBytes, { mode: 0o600 })

    let automated = {
      status: 'automated_candidate_acceptance_passed',
      branchCommit: commit,
      webBuildIdentity: 'd'.repeat(64),
      weappBuildIdentity: 'e'.repeat(64),
    }
    let automatedBytes = Buffer.from(`${JSON.stringify(automated)}\n`)
    let candidate = {
      status: 'candidate_deployed_user_acceptance_pending',
      branchCommit: commit,
      inventorySha256: inventorySha,
      independentBackupManifestSha256: backupMode === 'independent' ? backupManifestSha : null,
      deployedManifestSha256: 'f'.repeat(64),
      webBuildIdentity: automated.webBuildIdentity,
      weappBuildIdentity: automated.weappBuildIdentity,
      automatedAcceptance: {
        status: 'passed',
        report: 'automated-acceptance.json',
        sha256: sha256(automatedBytes),
      },
      readiness: {
        status: 'ready',
        components: {
          database: { status: 'ready' },
          wechat_mini: { status: 'ready' },
          worker: { status: 'ready' },
        },
      },
      realDualClientAcceptance: 'pending',
      recordedAt: '2026-09-03T00:00:00Z',
    }
    let candidateBytes = Buffer.from(`${JSON.stringify(candidate)}\n`)
    let real = {
      schemaVersion: 'chickenbro-real-dual-client-acceptance-v1',
      status: 'real_dual_client_acceptance_passed',
      branchCommit: commit,
      candidateEvidenceSha256: sha256(candidateBytes),
      webBuildIdentity: candidate.webBuildIdentity,
      weappBuildIdentity: candidate.weappBuildIdentity,
      testedRoutes: [
        'pages/chickenbro/index',
        'pages/simc/index',
        'pages/simc/tasks',
        'pages/simc/task-detail',
        'pages/auth/web-login-confirm',
      ],
      loginMode: 'user_authorized_skipped',
      routeContractEvidenceHash: '8'.repeat(64),
      realWechatQrLogin: { status: 'skipped', evidenceHash: '1'.repeat(64) },
      crossClientChat: { status: 'passed', objectHash: '2'.repeat(64) },
      crossClientSimc: { status: 'passed', objectHash: '3'.repeat(64) },
      ownerIsolation: { status: 'passed', objectHash: '4'.repeat(64) },
      acceptedAt: '2026-09-03T00:10:00Z',
    }
    let backup = {
      schemaVersion: 'chickenbro-independent-backup-v1',
      backupId: 'backup-1',
      sourceDatabase: 'wow_test',
      archivePath: archive,
      archiveSha256: sha256(archiveBytes),
      archiveBytes: archiveBytes.length,
      createdAt: '2026-09-03T00:00:00Z',
      deviceId: String(fs.statSync(root).dev),
      encrypted: true,
      sensitiveConfigurationEncrypted: true,
      encryption: { scheme: 'age', keyReferenceSha256: '4'.repeat(64) },
      restoreVerified: true,
      restore: {
        targetDatabase: 'chickenbro_restore_verify_test',
        commandExitCode: 0,
        schemaVerified: true,
        rowSampleVerified: true,
        hashSampleVerified: true,
        verifiedAt: '2026-09-03T00:05:00Z',
        operator: 'reviewed-operator',
        evidencePath: restoreEvidence,
        evidenceSha256: sha256(restoreBytes),
      },
    }

    ;({ backup, candidate, real, automated } = mutate({ backup, candidate, real, automated }))
    automatedBytes = Buffer.from(`${JSON.stringify(automated)}\n`)
    candidate = {
      ...candidate,
      automatedAcceptance: {
        ...candidate.automatedAcceptance,
        sha256: candidate.automatedAcceptance.sha256 === 'preserve-invalid'
          ? '0'.repeat(64)
          : sha256(automatedBytes),
      },
    }
    candidateBytes = Buffer.from(`${JSON.stringify(candidate)}\n`)
    real = {
      ...real,
      candidateEvidenceSha256: real.candidateEvidenceSha256 === 'preserve-invalid'
        ? '0'.repeat(64)
        : sha256(candidateBytes),
    }
    fs.writeFileSync(automatedPath, automatedBytes, { mode: 0o600 })
    fs.writeFileSync(candidatePath, candidateBytes, { mode: 0o600 })
    fs.writeFileSync(realPath, `${JSON.stringify(real)}\n`, { mode: 0o600 })
    const backupPath = path.join(root, 'restore-verified.json')
    if (backupMode === 'independent') {
      fs.writeFileSync(backupPath, `${JSON.stringify(backup)}\n`, { mode: 0o600 })
    }

    return spawnSync('python3', [
      '-', backupPath, candidatePath, realPath, commit, sha256(candidateBytes),
      inventorySha, backupMode === 'independent' ? backupManifestSha : '', backupMode,
    ], {
      encoding: 'utf8',
      input: evidenceValidatorSource(),
    })
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
}

function sealValidatorSource() {
  const source = readScript()
  const marker = 'import hashlib\nimport json\nimport os\nimport re\nimport stat\nimport sys\nfrom datetime import datetime\nfrom pathlib import Path\n\ncutover_path, acceptance_path, boundary_path, sealed_path'
  const start = source.indexOf(marker)
  const end = source.indexOf('\nPY\n\nadvance_state() {', start)
  assert.ok(start >= 0 && end > start, 'embedded accepted-write validator must be extractable')
  return source.slice(start, end)
}

function runSealValidator(mutate = ({ cutover, acceptance }) => ({ cutover, acceptance })) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'chickenbro-cutover-seal-'))
  try {
    const commit = 'a'.repeat(40)
    const cutoverPath = path.join(root, 'production-cutover.json')
    const acceptancePath = path.join(root, 'production-user-acceptance.json')
    const boundaryPath = path.join(root, 'WRITE_AUTHORITY_BOUNDARY')
    const sealedPath = `${cutoverPath}.sealed`
    const boundaryAt = '2026-09-03T01:00:00Z'
    let cutover = {
      schemaVersion: 'chickenbro-production-cutover-v1',
      status: 'production_cutover_switched_production_acceptance_pending',
      state: 'switched',
      branchCommit: commit,
      writeAuthorityBoundaryAt: boundaryAt,
      webBuildIdentity: 'b'.repeat(64),
      weappBuildIdentity: 'c'.repeat(64),
      postCutoverRealUserAcceptance: 'pending',
    }
    let acceptance = {
      schemaVersion: 'chickenbro-production-dual-client-acceptance-v1',
      status: 'production_dual_client_acceptance_passed',
      branchCommit: commit,
      cutoverEvidenceSha256: '',
      webBuildIdentity: cutover.webBuildIdentity,
      weappBuildIdentity: cutover.weappBuildIdentity,
      testedRoutes: [
        'pages/chickenbro/index',
        'pages/simc/index',
        'pages/simc/tasks',
        'pages/simc/task-detail',
        'pages/auth/web-login-confirm',
      ],
      loginMode: 'user_authorized_skipped',
      routeContractEvidenceHash: '8'.repeat(64),
      realWechatQrLogin: { status: 'skipped', evidenceHash: '1'.repeat(64) },
      crossClientChat: { status: 'passed', objectHash: '2'.repeat(64) },
      crossClientSimc: { status: 'passed', objectHash: '3'.repeat(64) },
      ownerIsolation: { status: 'passed', objectHash: '4'.repeat(64) },
      logoutIndependence: { status: 'passed', evidenceHash: '5'.repeat(64) },
      serviceRestartRecovery: { status: 'passed', evidenceHash: '6'.repeat(64) },
      userConfirmation: { status: 'accepted', evidenceHash: '7'.repeat(64) },
      firstAcceptedWriteAt: '2026-09-03T01:01:00Z',
      acceptedAt: '2026-09-03T01:10:00Z',
    }
    ;({ cutover, acceptance } = mutate({ cutover, acceptance }))
    const cutoverBytes = Buffer.from(`${JSON.stringify(cutover)}\n`)
    acceptance = {
      ...acceptance,
      cutoverEvidenceSha256: acceptance.cutoverEvidenceSha256 === 'preserve-invalid'
        ? '0'.repeat(64)
        : sha256(cutoverBytes),
    }
    const acceptanceBytes = Buffer.from(`${JSON.stringify(acceptance)}\n`)
    fs.writeFileSync(cutoverPath, cutoverBytes, { mode: 0o600 })
    fs.chmodSync(cutoverPath, 0o600)
    fs.writeFileSync(acceptancePath, acceptanceBytes, { mode: 0o600 })
    fs.chmodSync(acceptancePath, 0o600)
    fs.writeFileSync(boundaryPath, `${boundaryAt}\n`, { mode: 0o600 })
    const result = spawnSync('python3', [
      '-', cutoverPath, acceptancePath, boundaryPath, commit,
      sha256(cutoverBytes), sha256(acceptanceBytes), sealedPath,
    ], {
      encoding: 'utf8',
      input: sealValidatorSource(),
    })
    return {
      ...result,
      sealed: result.status === 0 ? JSON.parse(fs.readFileSync(sealedPath, 'utf8')) : null,
    }
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
}

test('cutover is an explicit monotonic state machine with exact evidence inputs', () => {
  const script = readScript()

  assert.match(script, /MODE="dry-run"/)
  assert.match(script, /preflight -> write_fenced -> delta_migrated -> switched -> accepted_write/)
  assert.match(
    script,
    /STATE_SEQUENCE=\(preflight write_fenced delta_migrated switched accepted_write\)/,
  )
  assert.match(script, /advance_state\(\)/)
  assert.match(script, /invalid cutover state transition/)
  assert.match(script, /legacy_read_only/)
  assert.match(script, /WRITE_AUTHORITY_BOUNDARY/)
  assert.match(script, /firstAcceptedWriteAt/)

  for (const argument of [
    '--apply',
    '--seal-accepted-write',
    '--candidate-commit',
    '--inventory-sha',
    '--backup-manifest-sha',
    '--candidate-evidence-path',
    '--candidate-evidence-sha',
    '--real-acceptance-path',
    '--real-acceptance-sha',
    '--cutover-evidence-path',
    '--cutover-evidence-sha',
    '--production-acceptance-path',
    '--production-acceptance-sha',
  ]) {
    assert.ok(script.includes(argument), `missing exact input ${argument}`)
  }

  assert.doesNotMatch(script, /(?:find|ls)[^\n]*(?:latest|candidate-acceptance|real-acceptance)/i)
  assert.doesNotMatch(script, /sort[^\n]*(?:tail|head)[^\n]*(?:acceptance|evidence)/i)
})

test('no-backup cutover requires explicit irreversible authorization and records the mode', () => {
  const script = readScript()

  assert.match(script, /--no-independent-backup/)
  assert.match(script, /--irreversible-no-backup-confirmation/)
  assert.match(script, /I_UNDERSTAND_NO_BACKUP_IS_IRREVERSIBLE/)
  assert.match(script, /none_user_authorized/)
  assert.match(script, /independentBackupManifestSha256/)
  assert.match(script, /backupMode/)
})

test('public activation and accepted-write sealing are separate monotonic gates', () => {
  const script = readScript()

  assert.match(script, /WRITE_AUTHORITY_BOUNDARY/)
  assert.match(script, /production_cutover_switched_production_acceptance_pending/)
  assert.match(script, /"state": "switched"/)
  assert.match(script, /chickenbro-production-dual-client-acceptance-v1/)
  assert.match(script, /production_dual_client_acceptance_passed/)
  assert.match(script, /firstAcceptedWriteAt/)
  assert.match(script, /cutoverEvidenceSha256/)
  assert.match(script, /productionAcceptanceSha256/)
  assert.match(script, /advance_state accepted_write/)
  assert.doesNotMatch(script, /firstNewWriteSemantics.*authority/i)

  const applyStart = script.indexOf('# Candidate builds intentionally use')
  const sealStart = script.indexOf('if [[ "${MODE}" == "seal-accepted-write" ]]')
  const boundary = script.indexOf('WRITE_AUTHORITY_BOUNDARY_AT=', applyStart)
  const publicStart = script.indexOf('systemctl start "${PRODUCTION_API_SERVICE}"', boundary)
  const pendingEvidence = script.indexOf('production_cutover_switched_production_acceptance_pending', publicStart)
  const sealBody = script.slice(sealStart, applyStart)
  assert.ok(boundary >= 0 && publicStart > boundary)
  assert.ok(pendingEvidence > publicStart)
  assert.match(sealBody, /advance_state accepted_write/)
  assert.doesNotMatch(script.slice(applyStart), /advance_state accepted_write/)
})

test('production cutover owns an isolated native Codex profile with rollback evidence', () => {
  const script = readScript()

  assert.match(script, /PRODUCTION_CODEX_PROFILE="\/home\/\$\{REMOTE_USER\}\/\.codex\/chickenbro-production\.config\.toml"/)
  assert.match(script, /production-codex-profile/)
  assert.match(script, /CODEX_PROFILE_IDENTITY/)
  assert.match(script, /__CHICKENBRO_RUNTIME_ROOT__/)
  assert.match(script, /server\/chickenbro_native_mcp\.py/)
  assert.match(script, /server\/chickenbro_public_web_research\.py/)
})

test('accepted-write seal requires exact post-cutover real-user evidence', () => {
  const valid = runSealValidator()
  assert.equal(valid.status, 0, valid.stderr)
  assert.equal(valid.sealed.state, 'accepted_write')
  assert.equal(valid.sealed.postCutoverRealUserAcceptance, 'passed')
  assert.equal(valid.sealed.firstNewWriteAt, '2026-09-03T01:01:00Z')

  const mutations = [
    ({ cutover, acceptance }) => ({
      cutover: { ...cutover, state: 'accepted_write' }, acceptance,
    }),
    ({ cutover, acceptance }) => ({
      cutover, acceptance: { ...acceptance, cutoverEvidenceSha256: 'preserve-invalid' },
    }),
    ({ cutover, acceptance }) => ({
      cutover, acceptance: { ...acceptance, testedRoutes: acceptance.testedRoutes.slice(1) },
    }),
    ({ cutover, acceptance }) => ({
      cutover, acceptance: { ...acceptance, crossClientSimc: { status: 'failed', objectHash: '3'.repeat(64) } },
    }),
    ({ cutover, acceptance }) => ({
      cutover, acceptance: { ...acceptance, userConfirmation: { status: 'pending', evidenceHash: '7'.repeat(64) } },
    }),
    ({ cutover, acceptance }) => ({
      cutover, acceptance: { ...acceptance, firstAcceptedWriteAt: '2026-09-03T00:59:59Z' },
    }),
    ({ cutover, acceptance }) => ({
      cutover, acceptance: { ...acceptance, accessToken: 'forbidden' },
    }),
  ]
  for (const mutate of mutations) {
    const rejected = runSealValidator(mutate)
    assert.notEqual(rejected.status, 0)
  }
})

test('dry-run is the default and cannot authorize a remote mutation', () => {
  const result = spawnSync('bash', [scriptPath, '--dry-run'], {
    cwd: process.cwd(),
    encoding: 'utf8',
  })

  assert.equal(result.status, 0, result.stderr)
  const payload = JSON.parse(result.stdout)
  assert.equal(payload.mode, 'dry-run')
  assert.equal(payload.mutationAuthorized, false)
  assert.equal(payload.sourceDatabase, 'wow_test')
  assert.equal(payload.targetDatabase, 'chickenbro_prod')
  assert.equal(payload.state, 'preflight')
  assert.match(payload.branchCommit, /^[0-9a-f]{40}$/)
  assert.match(payload.inventorySha256, /^[0-9a-f]{64}$/)
  assert.doesNotMatch(`${result.stdout}\n${result.stderr}`, /Running production cutover|write_fenced/)
})

test('apply fails closed before SSH when any content-addressed approval is absent', () => {
  const result = spawnSync('bash', [scriptPath, '--apply'], {
    cwd: process.cwd(),
    encoding: 'utf8',
  })

  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /--apply requires --candidate-commit/)
  assert.doesNotMatch(`${result.stdout}\n${result.stderr}`, /Running production cutover/)
})

test('candidate and real dual-client acceptance are separately validated', () => {
  const script = readScript()

  assert.match(script, /candidate_deployed_user_acceptance_pending/)
  assert.match(script, /automatedAcceptance/)
  assert.match(script, /automated_candidate_acceptance_passed/)
  assert.match(script, /automated-acceptance\.json/)
  assert.match(script, /candidate readiness is not fully ready/)
  assert.match(script, /realDualClientAcceptance.*pending/)
  assert.match(script, /chickenbro-real-dual-client-acceptance-v1/)
  assert.match(script, /real_dual_client_acceptance_passed/)
  assert.match(script, /pages\/auth\/web-login-confirm/)
  assert.match(script, /user_authorized_skipped/)
  assert.match(script, /accept_chickenbro_dual_client\.py/)
  assert.match(script, /crossClientChat/)
  assert.match(script, /crossClientSimc/)
  assert.match(script, /ownerIsolation/)
  assert.match(script, /webBuildIdentity/)
  assert.match(script, /weappBuildIdentity/)
  assert.match(script, /candidateEvidenceSha256/)
  assert.match(script, /candidate acceptance SHA mismatch/)
  assert.match(script, /real acceptance SHA mismatch/)
})

test('cutover evidence validator accepts only restore-verified, ready and cross-client-passed evidence', () => {
  const valid = runEvidenceValidator()
  assert.equal(valid.status, 0, valid.stderr)

  const noBackup = runEvidenceValidator(undefined, 'none_user_authorized')
  assert.equal(noBackup.status, 0, noBackup.stderr)

  const noBackupWithIdentity = runEvidenceValidator(
    ({ backup, candidate, real, automated }) => ({
      backup,
      candidate: { ...candidate, independentBackupManifestSha256: 'c'.repeat(64) },
      real,
      automated,
    }),
    'none_user_authorized',
  )
  assert.notEqual(noBackupWithIdentity.status, 0)

  const mutations = [
    ({ backup, candidate, real, automated }) => ({
      backup: { ...backup, encrypted: false }, candidate, real, automated,
    }),
    ({ backup, candidate, real, automated }) => ({
      backup, candidate: { ...candidate, readiness: { ...candidate.readiness, status: 'partial' } }, real, automated,
    }),
    ({ backup, candidate, real, automated }) => ({
      backup, candidate, real: { ...real, testedRoutes: real.testedRoutes.slice(1) }, automated,
    }),
    ({ backup, candidate, real, automated }) => ({
      backup, candidate, real: { ...real, crossClientSimc: { status: 'failed', objectHash: '2'.repeat(64) } }, automated,
    }),
    ({ backup, candidate, real, automated }) => ({
      backup, candidate: { ...candidate, automatedAcceptance: { ...candidate.automatedAcceptance, sha256: 'preserve-invalid' } }, real, automated,
    }),
    ({ backup, candidate, real, automated }) => ({
      backup, candidate, real: { ...real, access_token: 'forbidden' }, automated,
    }),
  ]
  for (const mutate of mutations) {
    const rejected = runEvidenceValidator(mutate)
    assert.notEqual(rejected.status, 0)
  }
})

test('full migration precedes the write fence and one reconciled delta follows it', () => {
  const script = readScript()
  const full = script.indexOf('--mode full')
  const fence = script.indexOf('advance_state write_fenced')
  const delta = script.indexOf('--mode delta')
  const switchState = script.indexOf('advance_state switched')

  assert.ok(full >= 0, 'full migration is required')
  assert.ok(fence > full, 'full migration must complete before the write fence')
  assert.ok(delta > fence, 'delta migration must run behind the write fence')
  assert.ok(switchState > delta, 'public switch must follow the final delta')
  assert.match(script, /--from-watermark "\$\{FULL_WATERMARK\}"/)
  assert.match(script, /capturedWatermark/)
  assert.match(script, /reconciliation.*matched/)
  assert.match(script, /FULL_MIGRATION_REPORT_SHA256/)
  assert.match(script, /DELTA_MIGRATION_REPORT_SHA256/)
  assert.doesNotMatch(script, /--captured-watermark/)
})

test('the extracted production stage stays traversable by the service user', () => {
  const script = readScript()
  const extracted = script.indexOf('tar -xzf "${REMOTE_ARCHIVE}" -C "${STAGE_DIR}"')
  const migration = script.indexOf('--mode full')
  const normalized = script.indexOf('chmod 0755 "${STAGE_DIR}"', extracted)

  assert.ok(extracted >= 0, 'production archive extraction is required')
  assert.ok(normalized > extracted && normalized < migration, 'stage root permissions must be restored after extraction')
})

test('the fence stops an exact reviewed writer set and makes wow_test read only', () => {
  const script = readScript()

  assert.match(script, /LEGACY_WRITER_UNITS=\(/)
  for (const unit of [
    'wow-backend.service',
    'wow-v2-api.service',
    'wow-v2-worker.service',
    'wow-chickenbro-source-refresh.timer',
    'wow-community-template-sync.timer',
    'wow-data-health-followup.timer',
    'wow-gear-release-refresh.timer',
    'wow-gear-stat-snapshot-worker.service',
    'wow-recommended-bis-guard-sync.timer',
    'wow-season-recommended-gear-sync.timer',
    'wow-simc-runtime-update.service',
    'wow-simc-version-check.service',
    'wow-simc-version-check.timer',
    'wow-stat-weights-sync.timer',
    'wow-websim-sync.timer',
  ]) {
    assert.ok(script.includes(unit), `missing reviewed legacy writer ${unit}`)
  }
  assert.match(script, /systemctl mask --runtime/)
  assert.match(script, /systemctl disable "\$\{unit\}"/)
  assert.match(script, /ALTER DATABASE wow_test SET default_transaction_read_only = on/)
  assert.match(script, /ALTER ROLE wow_app IN DATABASE wow_test SET default_transaction_read_only = on/)
  assert.match(script, /pg_terminate_backend/)
  assert.match(script, /current_setting\('default_transaction_read_only'\)/)
  assert.match(script, /SOURCE_CONNECTION_COUNT/)
  assert.match(script, /source database still has active application connections/)
  assert.match(script, /wow-attribute-rule-audit\.service/)
  assert.match(script, /wow-v2-api-candidate\.service/)
  assert.match(script, /wow-news-backend\.service/)
  assert.doesNotMatch(script, /LEGACY_WRITER_UNITS=.*\*/)
})

test('the public switch reuses the accepted candidate identity on chickenbro_prod', () => {
  const script = readScript()

  assert.match(script, /PRODUCTION_ROOT="\/opt\/chickenbro"/)
  assert.match(script, /PRODUCTION_DATABASE="chickenbro_prod"/)
  assert.match(script, /PRODUCTION_PORT="8790"/)
  assert.match(script, /CANDIDATE_ROOT="\/opt\/chickenbro-candidate"/)
  assert.match(script, /CANDIDATE_API_SERVICE="chickenbro-api-candidate"/)
  assert.match(script, /CANDIDATE_WORKER_SERVICE="chickenbro-worker-candidate"/)
  assert.match(script, /systemctl stop "\$\{CANDIDATE_API_SERVICE\}" "\$\{CANDIDATE_WORKER_SERVICE\}"/)
  assert.match(script, /systemctl disable "\$\{CANDIDATE_API_SERVICE\}" "\$\{CANDIDATE_WORKER_SERVICE\}"/)
  assert.match(script, /systemctl mask --runtime "\$\{CANDIDATE_API_SERVICE\}" "\$\{CANDIDATE_WORKER_SERVICE\}"/)
  assert.match(script, /WOW_API_V2_PREFIX="\/api\/v2"/)
  assert.match(script, /WOW_WEB_AUTH_API_PREFIX="\/api\/v2"/)
  assert.match(script, /WOW_WEB_CSRF_COOKIE_NAME="__Host-chickenbro-csrf"/)
  assert.match(script, /WOW_H5_PUBLIC_PATH="\/"/)
  assert.match(script, /run build:h5/)
  assert.match(script, /run build:weapp/)
  assert.match(script, /PRODUCTION_WEB_BUILD_IDENTITY/)
  assert.match(script, /PRODUCTION_WEAPP_BUILD_IDENTITY/)
  assert.match(script, /chickenbro-api\.service/)
  assert.match(script, /chickenbro-worker\.service/)
  assert.match(script, /\/etc\/chickenbro-api\.env/)
  assert.match(script, /\/etc\/chickenbro-worker\.env/)
  assert.match(script, /\/var\/www\/chickenbro-web\/current/)
  assert.match(script, /# BEGIN CHICKENBRO PRODUCTION API/)
  assert.match(script, /location \^~ \/api\/v2\//)
  assert.match(script, /proxy_pass http:\/\/127\.0\.0\.1:8790;/)
  assert.match(script, /nginx -t/)
  assert.match(script, /systemctl is-active --quiet "\$\{PRODUCTION_API_SERVICE\}"/)
  assert.match(script, /systemctl is-active --quiet "\$\{PRODUCTION_WORKER_SERVICE\}"/)
  assert.match(script, /export PGPASSFILE="\$\{PRODUCTION_PGPASSFILE\}"/)
})

test('rollback may restore legacy writes only before the irreversible first-write boundary', () => {
  const script = readScript()
  const preWrite = functionBody(script, 'pre_write_rollback', 'post_write_recovery')
  const postWrite = functionBody(script, 'post_write_recovery', 'handle_failure')

  assert.match(preWrite, /WRITE_AUTHORITY_BOUNDARY/)
  assert.match(preWrite, /ALTER DATABASE wow_test RESET default_transaction_read_only/)
  assert.match(preWrite, /ALTER ROLE wow_app IN DATABASE wow_test RESET default_transaction_read_only/)
  assert.match(preWrite, /restore_unit_states/)
  assert.match(script, /systemctl unmask --runtime/)

  assert.match(postWrite, /legacy_read_only/)
  assert.match(postWrite, /ALTER DATABASE wow_test SET default_transaction_read_only = on/)
  assert.match(postWrite, /ALTER DATABASE chickenbro_prod SET default_transaction_read_only = on/)
  assert.doesNotMatch(postWrite, /wow_test RESET default_transaction_read_only/)
  assert.doesNotMatch(postWrite, /wow_test[^\n]*(?:off|false)/i)

  const sealStart = script.indexOf('if [[ "${MODE}" == "seal-accepted-write" ]]')
  const applyStart = script.indexOf('# Candidate builds intentionally use')
  const sealBody = script.slice(sealStart, applyStart)
  const accepted = sealBody.indexOf('advance_state accepted_write')
  assert.ok(accepted >= 0)
  assert.doesNotMatch(sealBody.slice(accepted), /wow_test RESET default_transaction_read_only/)
  assert.doesNotMatch(script, /DROP DATABASE|TRUNCATE|DELETE FROM/i)
})

test('cutover records redacted identities and never serializes credentials', () => {
  const script = readScript()

  assert.match(script, /validate_nginx_owner\(\)/)
  assert.match(script, /API_NGINX_SITE.*API_NGINX_OWNER.*api\.chickenbro\.cloud/s)

  for (const field of [
    'writeFenceAt',
    'fullWatermark',
    'deltaWatermark',
    'writeAuthorityBoundaryAt',
    'firstNewWriteAt',
    'sourceDatabaseReadOnly',
    'branchCommit',
    'candidateEvidenceSha256',
    'realAcceptanceSha256',
    'fullMigrationReportSha256',
    'deltaMigrationReportSha256',
    'apiServiceIdentity',
    'workerServiceIdentity',
    'webBuildIdentity',
    'weappBuildIdentity',
    'wwwNginxIdentity',
    'apiNginxIdentity',
    'rollbackClassification',
    'productionAcceptanceSha256',
  ]) {
    assert.ok(script.includes(field), `missing cutover evidence field ${field}`)
  }

  assert.doesNotMatch(script, /cat .*\.env|printenv|env \|/)
  assert.doesNotMatch(script, /echo .*WOW_(?:DATABASE_URL|WECHAT_SECRET|LIGHTHOUSE_PASSWORD)/)
  assert.doesNotMatch(script, /(?:session_key|openid|accessToken)\s*[=:]/i)
  assert.match(script, /rm -f -- "\$\{PRODUCTION_PGPASSFILE\}\.new"/)
})

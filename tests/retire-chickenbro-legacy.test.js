const assert = require('node:assert/strict')
const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const { spawnSync } = require('node:child_process')

const repositoryRoot = path.resolve(__dirname, '..')
const scriptPath = path.join(repositoryRoot, 'server/retire_chickenbro_legacy_lighthouse.sh')
const manifestPath = path.join(
  repositoryRoot,
  'docs/refactor/chickenbro-simc-cloud-cleanup-manifest.json',
)
const inventoryPath = path.join(repositoryRoot, 'docs/refactor/chickenbro-simc-cloud-inventory.json')

function sha256(bytes) {
  return crypto.createHash('sha256').update(bytes).digest('hex')
}

function sourceAndValidate(kind, target, scope = 'full_retirement') {
  return spawnSync('bash', ['-c', 'source "$1"; validate_deletion_target "$2" "$3" "$4"', 'test', scriptPath, kind, target, scope], {
    cwd: repositoryRoot,
    encoding: 'utf8',
  })
}

test('protected targets and broad or unresolved targets are rejected', () => {
  for (const [kind, target] of [
    ['postgres_database', 'chickenbro_prod'],
    ['systemd_unit', 'chickenbro-api.service'],
    ['systemd_unit', 'chickenbro-worker.service'],
    ['directory', '/opt/wow-simc/current'],
    ['directory', '/opt/wow-simc'],
    ['directory', '/var/lib/postgresql'],
    ['directory', '/var/www/chickenbro-web'],
  ]) {
    const result = sourceAndValidate(kind, target)
    assert.notEqual(result.status, 0, `${kind}:${target}`)
    assert.match(result.stderr, /protected target/i)
  }

  const protectedWowTest = sourceAndValidate('postgres_database', 'wow_test', 'capacity_pre_cleanup')
  assert.notEqual(protectedWowTest.status, 0)
  assert.match(protectedWowTest.stderr, /protected target/i)

  for (const [kind, target] of [
    ['postgres_database', 'wow_*'],
    ['systemd_unit', 'wow-*.service'],
    ['directory', '/opt'],
    ['directory', '/var/lib'],
    ['directory', '/'],
    ['directory', '~'],
    ['file', '$HOME'],
    ['file', '/etc/../etc/wow-backend.env'],
  ]) {
    const result = sourceAndValidate(kind, target)
    assert.notEqual(result.status, 0, `${kind}:${target}`)
    assert.match(result.stderr, /exact target/i)
  }
})

test('capacity pre-cleanup accepts only the four exact databases and env companions', () => {
  const allowlist = [
    'wow_gear_evidence_01adf184_r14',
    'wow_gear_evidence_0be65754_r24',
    'wow_gear_evidence_145dee16_r22',
    'wow_gear_evidence_15f514d5_r23',
  ]
  for (const target of allowlist) {
    const result = sourceAndValidate('postgres_database', target, 'capacity_pre_cleanup')
    assert.equal(result.status, 0, result.stderr)
  }

  for (const target of ['wow_prod', 'wow_gear_evidence_20260831', 'wow_gear_evidence_01adf184_r14_copy']) {
    const result = sourceAndValidate('postgres_database', target, 'capacity_pre_cleanup')
    assert.notEqual(result.status, 0, target)
    assert.match(result.stderr, /exact capacity allowlist/i)
  }

  for (const target of [
    '/etc/wow-backend-candidate-gear-evidence-r14.env',
    '/etc/wow-backend-candidate-gear-evidence-r24.env',
    '/etc/wow-backend-candidate-gear-evidence-r22.env',
    '/etc/wow-backend-candidate-gear-evidence-r23.env',
  ]) {
    const result = sourceAndValidate('file', target, 'capacity_pre_cleanup')
    assert.equal(result.status, 0, result.stderr)
  }
})

test('cloud cleanup manifest covers every observed legacy unit and database exactly', () => {
  const inventoryBytes = fs.readFileSync(inventoryPath)
  const inventory = JSON.parse(inventoryBytes)
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))

  assert.equal(manifest.schemaVersion, 2)
  assert.equal(manifest.mode, 'dry-run')
  assert.equal(manifest.deletionAuthorized, false)
  assert.equal(manifest.sourceInventory.path, 'docs/refactor/chickenbro-simc-cloud-inventory.json')
  assert.equal(manifest.sourceInventory.sha256, sha256(inventoryBytes))
  assert.equal(manifest.sourceInventory.observedAt, inventory.observedAt)
  assert.deepEqual(manifest.targetIdentity, {
    provider: 'tencent_cvm',
    instanceId: 'ins-93tgv1rb',
    region: 'ap-shanghai',
    zone: 'ap-shanghai-2',
    publicAddress: '124.223.51.33',
    sshTarget: 'wow-lighthouse',
    refreshRequiredBeforeApply: true,
  })
  assert.equal(manifest.businessRecovery.status, 'not_run')
  assert.equal(manifest.businessRecovery.manifestSchema, 'chickenbro-whitelist-recovery-v1')
  assert.equal(manifest.acceptedProductionRecovery.status, 'not_run')
  assert.equal(manifest.capacityPreCleanup.requiresPhase5Acceptance, false)
  assert.equal(manifest.capacityPreCleanup.protectsWowTest, true)
  assert.deepEqual(
    manifest.capacityPreCleanup.exactDatabaseAllowlist,
    [
      'wow_gear_evidence_01adf184_r14',
      'wow_gear_evidence_0be65754_r24',
      'wow_gear_evidence_145dee16_r22',
      'wow_gear_evidence_15f514d5_r23',
    ],
  )
  assert.deepEqual(manifest.capacityPreCleanup.configurationScanRoots, [
    '/etc',
    '/opt/chickenbro',
    '/opt/wow-mini-program',
    '/opt/wow-v2-staging',
    '/var/www',
  ])
  assert.equal(manifest.productionAcceptance.status, 'not_run')

  const resources = manifest.resources
  assert.ok(Array.isArray(resources) && resources.length > 0)
  assert.equal(new Set(resources.map((item) => item.id)).size, resources.length)
  assert.equal(new Set(resources.map((item) => `${item.kind}:${item.target}`)).size, resources.length)
  assert.ok(resources.every((item) => item.gateStatus === 'blocked'))

  const unitTargets = new Set(
    resources.filter((item) => item.kind === 'systemd_unit').map((item) => item.target),
  )
  const databaseTargets = new Set(
    resources.filter((item) => item.kind === 'postgres_database').map((item) => item.target),
  )
  assert.deepEqual(
    unitTargets,
    new Set(inventory.units.map((item) => item.name).filter((name) => name.startsWith('wow-'))),
  )
  assert.deepEqual(
    databaseTargets,
    new Set(inventory.databases.map((item) => item.name).filter((name) => name.startsWith('wow_'))),
  )
  for (const resource of resources.filter((item) => item.capacityPreCleanup && item.kind === 'postgres_database')) {
    assert.equal(resource.observed.tableCount, 71)
    assert.ok(Number.isInteger(resource.observed.approximateRows))
  }

  const protectedTargets = new Set(manifest.protectedResources.map((item) => item.target))
  for (const target of [
    'chickenbro_prod',
    'chickenbro-api.service',
    'chickenbro-worker.service',
    '/opt/chickenbro',
    '/opt/chickenbro-runtime',
    '/opt/wow-simc',
    '/opt/wow-simc/current',
    '/var/lib/postgresql',
    '/var/www/chickenbro-web',
    '/etc/nginx/sites-available/wow-v2-web',
    '/etc/nginx/sites-enabled/api.chickenbro.cloud',
  ]) {
    assert.ok(protectedTargets.has(target), target)
  }

  assert.ok(manifest.unresolvedRequiredTargets.some((item) => item.id === 'legacy-runtime-pgpass-path'))
  assert.ok(manifest.unresolvedRequiredTargets.every((item) => item.status === 'blocked'))
})

test('dry-run reports every resource and never authorizes mutation', () => {
  const result = spawnSync('bash', [scriptPath, '--manifest', manifestPath, '--dry-run'], {
    cwd: repositoryRoot,
    encoding: 'utf8',
  })
  assert.equal(result.status, 0, result.stderr)
  const payload = JSON.parse(result.stdout)
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))
  assert.equal(payload.mode, 'dry-run')
  assert.equal(payload.mutationAuthorized, false)
  assert.equal(payload.counts.total, manifest.resources.length)
  assert.equal(payload.counts.blocked, manifest.resources.length)
  assert.equal(payload.counts.ready, 0)
  assert.equal(payload.unresolvedBlockerCount, manifest.unresolvedRequiredTargets.length)
  assert.ok(payload.results.every((item) => item.status === 'blocked'))
})

test('capacity pre-cleanup dry-run reports only the exact four databases and env companions', () => {
  const result = spawnSync('bash', [
    scriptPath,
    '--manifest', manifestPath,
    '--capacity-pre-cleanup',
    '--dry-run',
  ], { cwd: repositoryRoot, encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr)
  const payload = JSON.parse(result.stdout)
  assert.equal(payload.scope, 'capacity_pre_cleanup')
  assert.equal(payload.mutationAuthorized, false)
  assert.equal(payload.counts.total, 8)
  assert.deepEqual(
    payload.results.filter((item) => item.kind === 'postgres_database').map((item) => item.target),
    [
      'wow_gear_evidence_01adf184_r14',
      'wow_gear_evidence_0be65754_r24',
      'wow_gear_evidence_145dee16_r22',
      'wow_gear_evidence_15f514d5_r23',
    ],
  )
  assert.deepEqual(
    payload.results.filter((item) => item.kind === 'file').map((item) => item.target),
    [
      '/etc/wow-backend-candidate-gear-evidence-r14.env',
      '/etc/wow-backend-candidate-gear-evidence-r24.env',
      '/etc/wow-backend-candidate-gear-evidence-r22.env',
      '/etc/wow-backend-candidate-gear-evidence-r23.env',
    ],
  )
})

test('apply fails closed before remote execution without reviewed identities and ready gates', () => {
  const result = spawnSync('bash', [scriptPath, '--manifest', manifestPath, '--apply'], {
    cwd: repositoryRoot,
    encoding: 'utf8',
  })
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /--apply requires --manifest-sha and --recovery-manifest-sha/i)

  const manifestSha = sha256(fs.readFileSync(manifestPath))
  const blocked = spawnSync('bash', [
    scriptPath,
    '--manifest', manifestPath,
    '--apply',
    '--manifest-sha', manifestSha,
    '--recovery-manifest-sha', 'a'.repeat(64),
  ], { cwd: repositoryRoot, encoding: 'utf8' })
  assert.notEqual(blocked.status, 0)
  assert.match(blocked.stderr, /deletionAuthorized=true|blocked cleanup manifest/i)
})

test('retirement implementation has live probes and no recursive or wildcard delete primitive', () => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  assert.doesNotMatch(source, /rm\s+-r|rmSync|rmdirSync|find\s+[^\n]+-delete|DROP\s+DATABASE\s+wow_\*/i)
  assert.match(source, /pg_stat_activity/)
  assert.match(source, /DROP DATABASE/)
  assert.match(source, /systemctl/)
  assert.match(source, /readlink -f/)
  assert.match(source, /sha256sum/)
  assert.match(source, /mv --/)
  assert.match(source, /whitelist-recovery\.json/)
  assert.match(source, /metadata\.tencentyun\.com\/latest\/meta-data\/instance-id/)
  assert.match(source, /metadata\.tencentyun\.com\/latest\/meta-data\/placement\/region/)
  assert.match(source, /metadata\.tencentyun\.com\/latest\/meta-data\/placement\/zone/)
  assert.match(source, /lsof/)
  assert.match(source, /if \[\[ "\$\{RETIREMENT_SCOPE\}" != "capacity_pre_cleanup" \]\]; then\s+systemctl is-active/)
  assert.match(source, /if \[\[ "\$\{RETIREMENT_SCOPE\}" != "capacity_pre_cleanup" \]\]; then\s+systemctl daemon-reload/)
  assert.doesNotMatch(source, /--exclude(?:-dir)?=/)
  assert.match(source, /acceptedProductionRecovery/)
  assert.match(source, /archiveSha256/)
  assert.match(source, /evidenceSha256/)
  assert.match(source, /migrationReport/)
  assert.match(source, /chickenbro_restore_verify_/)
})

test('capacity reference scan covers every reviewed root and excludes only exact evidence paths', () => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  for (const root of [
    '/etc',
    '/opt/chickenbro',
    '/opt/wow-mini-program',
    '/opt/wow-v2-staging',
    '/var/www',
  ]) {
    assert.ok(source.includes(root), `missing reference scan root: ${root}`)
  }
  assert.match(source, /REFERENCE_EVIDENCE_EXCLUSIONS/)
  assert.match(source, /grep -Fxq -- "\$\{candidate\}"/)
  assert.doesNotMatch(source, /excluded_basename|basename -- "\$\{target\}"/)
})

test('reference scanner finds the needle in every configured root without basename-wide hiding', () => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  const helper = source.match(/runtime_configuration_references\(\) \{[\s\S]*?\n\}/)?.[0]
  assert.ok(helper, 'missing runtime_configuration_references helper')
  const directory = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'chickenbro-refs-'))
  try {
    const roots = ['etc', 'opt-chickenbro', 'opt-wow-mini-program', 'opt-wow-v2-staging', 'var-www']
      .map((name) => path.join(directory, name))
    const expected = []
    for (const [index, root] of roots.entries()) {
      fs.mkdirSync(root, { recursive: true })
      const file = path.join(root, index === 0 || index === 1 ? 'same-name.env' : `config-${index}`)
      fs.writeFileSync(file, 'DATABASE=reviewed-database\n')
      expected.push(file)
    }
    const rootsFile = path.join(directory, 'roots.txt')
    const exclusionsFile = path.join(directory, 'exclusions.txt')
    fs.writeFileSync(rootsFile, `${roots.join('\n')}\n`)
    fs.writeFileSync(exclusionsFile, `${expected[0]}\n`)
    const result = spawnSync('bash', ['-c', [
      'set -euo pipefail',
      `CONFIGURATION_SCAN_ROOTS=${JSON.stringify(rootsFile)}`,
      `REFERENCE_EVIDENCE_EXCLUSIONS=${JSON.stringify(exclusionsFile)}`,
      helper,
      'runtime_configuration_references reviewed-database',
    ].join('\n')], { encoding: 'utf8' })
    assert.equal(result.status, 0, result.stderr)
    assert.deepEqual(result.stdout.trim().split('\n').sort(), expected.slice(1).sort())
    assert.ok(result.stdout.includes(expected[1]), 'same basename at another exact path must remain visible')
  } finally {
    fs.rmSync(directory, { recursive: true, force: true })
  }
})

test('capacity preflight rejects symlinked or realpath-drifted env companions', () => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  assert.match(source, /validate_capacity_env_file\(\)/)
  assert.match(source, /! -L "\$\{target\}"/)
  assert.match(source, /realpath -e -- "\$\{target\}"/)
  assert.match(source, /"\$\{target_real\}" == "\$\{target\}"/)
  assert.match(source, /"\$\{target%\/\*\}" == "\/etc"/)
})

test('capacity apply preflights every pair before mutation and journals each irreversible boundary', () => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  const preflightCall = source.indexOf('capacity_preflight_all_pairs\n')
  const applyCall = source.indexOf('capacity_apply_pairs\n')
  assert.ok(preflightCall > 0 && applyCall > preflightCall, 'all-pair preflight must precede apply')
  assert.match(source, /fresh_database_counts/)
  assert.match(source, /expected_table_count/)
  assert.match(source, /expected_row_count/)
  assert.match(source, /preflight_complete/)
  assert.match(source, /env_quarantined/)
  assert.match(source, /drop_started/)
  assert.match(source, /completed/)
  assert.match(source, /failed_recovered/)
  assert.match(source, /ALTER DATABASE %I WITH ALLOW_CONNECTIONS/)
  assert.match(source, /os\.fsync/)
  assert.match(source, /os\.replace/)
  assert.match(source, /"before"/)
  assert.match(source, /"after"/)
})

test('capacity database preflight permits only its exact companion then requires zero references after quarantine', () => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  assert.match(source, /configuration references differ from exact companion/)
  assert.match(source, /database still has configuration references after companion quarantine/)
  assert.match(source, /process_environment_reference_count/)
})

test('remote metadata refresh precedes temporary files and quarantine directories', () => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  const remote = source.slice(source.indexOf("bash -s <<'REMOTE'"))
  const metadata = remote.indexOf('LIVE_INSTANCE_ID=')
  assert.ok(metadata > 0)
  assert.ok(metadata < remote.indexOf('MANIFEST_TMP="$(mktemp)"'))
  assert.ok(metadata < remote.indexOf('install -d -o root -g root -m 0700 -- "${RUN_ROOT}"'))
})

test('manifest and dry-run contain no secret-bearing fields or values', () => {
  const serialized = fs.readFileSync(manifestPath, 'utf8').toLowerCase()
  for (const forbidden of ['password', 'secret', 'cookie', 'openid', 'unionid', 'databaseurl']) {
    assert.doesNotMatch(serialized, new RegExp(`"${forbidden}"\\s*:`))
  }
  assert.doesNotMatch(serialized, /postgres(?:ql)?:\/\/[^\s/@:]+:[^\s/@]+@/)
})

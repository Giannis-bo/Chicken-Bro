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

function extractShellFunction(source, name) {
  return source.match(new RegExp(`${name}\\(\\) \\{[\\s\\S]*?\\n\\}`))?.[0] || ''
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
  assert.equal(manifest.businessRecovery.status, 'restore_verified')
  assert.equal(manifest.businessRecovery.manifestSchema, 'chickenbro-whitelist-recovery-v1')
  assert.equal(manifest.acceptedProductionRecovery.status, 'not_run')
  assert.equal(manifest.capacityPreCleanup.authorized, true)
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
  assert.ok(resources.filter((item) => item.capacityPreCleanup).every((item) => item.gateStatus === 'ready'))
  assert.ok(resources.filter((item) => !item.capacityPreCleanup).every((item) => item.gateStatus === 'blocked'))

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
    assert.ok(Number.isInteger(resource.observed.exactRows))
    assert.ok(resource.observed.exactRows >= 0)
    assert.deepEqual(resource.blockedReasons, [])
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
  assert.equal(payload.counts.blocked, manifest.resources.length - 8)
  assert.equal(payload.counts.ready, 8)
  assert.equal(payload.unresolvedBlockerCount, manifest.unresolvedRequiredTargets.length)
  assert.equal(payload.results.filter((item) => item.status === 'ready').length, 8)
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
  assert.equal(payload.counts.ready, 8)
  assert.equal(payload.counts.blocked, 0)
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
  const helper = extractShellFunction(source, 'runtime_configuration_reference_probe')
  assert.ok(helper, 'missing runtime_configuration_reference_probe helper')
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
      'runtime_configuration_reference_probe reviewed-database',
    ].join('\n')], { encoding: 'utf8' })
    assert.equal(result.status, 0, result.stderr)
    const lines = result.stdout.trim().split('\n')
    assert.equal(lines.shift(), 'matched')
    assert.deepEqual(lines.sort(), expected.slice(1).sort())
    assert.ok(result.stdout.includes(expected[1]), 'same basename at another exact path must remain visible')
  } finally {
    fs.rmSync(directory, { recursive: true, force: true })
  }
})

test('an exact absent scan root is a clear contribution, not a probe error', (t) => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  const helper = extractShellFunction(source, 'runtime_configuration_reference_probe')
  assert.ok(helper)
  const directory = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'chickenbro-absent-root-'))
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }))
  const rootsFile = path.join(directory, 'roots.txt')
  const exclusionsFile = path.join(directory, 'exclusions.txt')
  fs.writeFileSync(rootsFile, `${path.join(directory, 'absent')}\n`)
  fs.writeFileSync(exclusionsFile, '')
  const result = spawnSync('bash', ['-c', [
    'set -euo pipefail',
    `CONFIGURATION_SCAN_ROOTS=${JSON.stringify(rootsFile)}`,
    `REFERENCE_EVIDENCE_EXCLUSIONS=${JSON.stringify(exclusionsFile)}`,
    helper,
    'runtime_configuration_reference_probe reviewed-database',
  ].join('\n')], { encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr)
  assert.equal(result.stdout.trim(), 'clear')
})

test('configuration, process, and open-handle probe errors never report clear', (t) => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  const configurationProbe = extractShellFunction(source, 'runtime_configuration_reference_probe')
  const processProbe = extractShellFunction(source, 'process_environment_reference_probe')
  const openHandleProbe = extractShellFunction(source, 'open_handle_probe')
  assert.ok(configurationProbe && processProbe && openHandleProbe, 'missing three-state probe helper')
  const directory = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'chickenbro-probe-error-'))
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }))
  const root = path.join(directory, 'root')
  const processRoot = path.join(directory, 'proc')
  fs.mkdirSync(root)
  fs.mkdirSync(path.join(processRoot, '123'), { recursive: true })
  fs.writeFileSync(path.join(processRoot, '123', 'environ'), 'DATABASE=reviewed')
  const rootsFile = path.join(directory, 'roots.txt')
  const exclusionsFile = path.join(directory, 'exclusions.txt')
  fs.writeFileSync(rootsFile, `${root}\n`)
  fs.writeFileSync(exclusionsFile, '')

  const cases = [
    {
      helper: configurationProbe,
      setup: [
        `CONFIGURATION_SCAN_ROOTS=${JSON.stringify(rootsFile)}`,
        `REFERENCE_EVIDENCE_EXCLUSIONS=${JSON.stringify(exclusionsFile)}`,
        'find() { printf "permission denied\\n" >&2; return 2; }',
      ],
      call: 'runtime_configuration_reference_probe reviewed',
    },
    {
      helper: processProbe,
      setup: [
        `PROCESS_ENVIRON_ROOT=${JSON.stringify(processRoot)}`,
        'grep() { printf "read error\\n" >&2; return 2; }',
      ],
      call: 'process_environment_reference_probe reviewed',
    },
    {
      helper: openHandleProbe,
      setup: ['lsof() { printf "tool error\\n" >&2; return 2; }'],
      call: `open_handle_probe ${JSON.stringify(path.join(directory, 'reviewed.env'))}`,
    },
  ]
  for (const item of cases) {
    const result = spawnSync('bash', ['-c', [
      'set -u',
      ...item.setup,
      item.helper,
      'set +e',
      `output="$(${item.call})"`,
      'status=$?',
      'printf "%s:%s\\n" "${status}" "${output}"',
      '[[ "${status}" -ne 0 && "${output}" == "error" ]]',
    ].join('\n')], { encoding: 'utf8' })
    assert.equal(result.status, 0, result.stderr)
    assert.match(result.stdout, /^[1-9][0-9]*:error$/m)
  }
})

test('expected process exit and empty lsof rc=1 are explicit clear states', (t) => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  const processProbe = extractShellFunction(source, 'process_environment_reference_probe')
  const openHandleProbe = extractShellFunction(source, 'open_handle_probe')
  assert.ok(processProbe && openHandleProbe)
  const directory = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'chickenbro-probe-clear-'))
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }))
  const processRoot = path.join(directory, 'proc')
  const environment = path.join(processRoot, '123', 'environ')
  fs.mkdirSync(path.dirname(environment), { recursive: true })
  fs.writeFileSync(environment, 'DATABASE=reviewed')
  const processResult = spawnSync('bash', ['-c', [
    'set -u',
    `PROCESS_ENVIRON_ROOT=${JSON.stringify(processRoot)}`,
    `VANISHING_ENV=${JSON.stringify(environment)}`,
    'grep() { rm -f -- "${VANISHING_ENV}"; return 2; }',
    processProbe,
    'process_environment_reference_probe reviewed',
  ].join('\n')], { encoding: 'utf8' })
  assert.equal(processResult.status, 0, processResult.stderr)
  assert.equal(processResult.stdout.trim(), 'clear\t0')

  const lsofResult = spawnSync('bash', ['-c', [
    'set -u',
    'lsof() { return 1; }',
    openHandleProbe,
    'open_handle_probe /etc/reviewed.env',
  ].join('\n')], { encoding: 'utf8' })
  assert.equal(lsofResult.status, 0, lsofResult.stderr)
  assert.equal(lsofResult.stdout.trim(), 'clear')
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
  assert.match(source, /expected_exact_row_count/)
  assert.match(source, /preflight_complete/)
  assert.match(source, /env_move_intent/)
  assert.match(source, /env_quarantined/)
  assert.match(source, /fence_intent/)
  assert.match(source, /drop_intent/)
  assert.match(source, /completed/)
  assert.match(source, /failed_recovered/)
  assert.match(source, /ALTER DATABASE %I WITH ALLOW_CONNECTIONS/)
  assert.match(source, /os\.fsync/)
  assert.match(source, /os\.replace/)
  assert.match(source, /"before"/)
  assert.match(source, /"after"/)
})

test('ready capacity databases require a reviewed exact-row identity, never planner statistics', (t) => {
  const directory = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'chickenbro-exact-rows-'))
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }))
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))
  const database = manifest.resources.find((item) => item.capacityPreCleanup && item.kind === 'postgres_database')
  database.gateStatus = 'ready'
  database.restoreCheck = 'not_required'
  database.deleteAfter = '2026-09-03T00:00:00Z'
  delete database.observed.exactRows
  const changedManifest = path.join(directory, 'manifest.json')
  fs.writeFileSync(changedManifest, `${JSON.stringify(manifest)}\n`)

  const result = spawnSync('bash', [scriptPath, '--manifest', changedManifest, '--dry-run'], {
    cwd: repositoryRoot,
    encoding: 'utf8',
  })
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /exact table\/row counts/i)
})

test('database row identity executes exact COUNT queries and rejects planner-stat shortcuts', () => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  const helper = extractShellFunction(source, 'fresh_database_counts')
  assert.ok(helper, 'missing fresh_database_counts helper')
  const result = spawnSync('bash', ['-c', [
    'set -euo pipefail',
    'sudo() {',
    '  local arguments="$*"',
    '  [[ "${arguments}" != *"n_live_tup"* ]] || return 91',
    '  if [[ "${arguments}" == *"SELECT count(*)::bigint FROM pg_stat_user_tables"* ]]; then printf "2\\n"; return 0; fi',
    '  if [[ "${arguments}" == *"string_agg(format"* ]]; then printf "SELECT (SELECT count(*)::bigint FROM app.first) + (SELECT count(*)::bigint FROM app.second)\\n"; return 0; fi',
    '  if [[ "${arguments}" == *"SELECT (SELECT count(*)::bigint FROM app.first)"* ]]; then printf "37\\n"; return 0; fi',
    '  return 92',
    '}',
    helper,
    'fresh_database_counts reviewed_database',
  ].join('\n')], { encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr)
  assert.equal(result.stdout.trim(), '2\t37')
})

test('database existence probe returns unknown on command failure instead of absent', () => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  const helper = extractShellFunction(source, 'probe_capacity_database_existence')
  assert.ok(helper, 'missing probe_capacity_database_existence helper')
  const result = spawnSync('bash', ['-c', [
    'set -u',
    'sudo() { return 55; }',
    helper,
    'set +e',
    'output="$(probe_capacity_database_existence reviewed_database)"',
    'probe_status=$?',
    'printf "%s:%s\\n" "${probe_status}" "${output}"',
    '[[ "${probe_status}" -ne 0 && "${output}" == "unknown" ]]',
  ].join('\n')], { encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr)
  assert.match(result.stdout, /^[1-9][0-9]*:unknown$/m)
})

test('one target session fences and revalidates identity without terminating sessions', (t) => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  const helper = extractShellFunction(source, 'fence_and_verify_capacity_database')
  assert.ok(helper, 'missing fence_and_verify_capacity_database helper')
  const directory = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'chickenbro-fence-session-'))
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }))
  const sqlPath = path.join(directory, 'fence.sql')
  const argsPath = path.join(directory, 'args.txt')
  const result = spawnSync('bash', ['-c', [
    'set -euo pipefail',
    `TEST_SQL=${JSON.stringify(sqlPath)}`,
    `TEST_ARGS=${JSON.stringify(argsPath)}`,
    'sudo() {',
    '  printf "%s\\n" "$*" > "${TEST_ARGS}"',
    '  command cat > "${TEST_SQL}"',
    '  printf "capacity_fenced_verified\\n"',
    '}',
    helper,
    'fence_and_verify_capacity_database reviewed_database 100 2 37 postgres',
  ].join('\n')], { encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr)
  assert.match(fs.readFileSync(argsPath, 'utf8'), /--dbname=reviewed_database/)
  const sql = fs.readFileSync(sqlPath, 'utf8')
  assert.ok(sql.indexOf('ALLOW_CONNECTIONS false') < sql.indexOf('pg_database_size'))
  assert.match(sql, /pid <> pg_backend_pid\(\)/)
  assert.match(sql, /SELECT count\(\*\)::bigint FROM/)
  assert.doesNotMatch(sql, /pg_terminate_backend/)
})

test('capacity apply fences and verifies before env quarantine, then drops without killing sessions', (t) => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  const helper = extractShellFunction(source, 'capacity_apply_pair')
  assert.ok(helper, 'missing capacity_apply_pair helper')
  const directory = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'chickenbro-apply-order-'))
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }))
  const envPath = path.join(directory, 'reviewed.env')
  const logPath = path.join(directory, 'events.log')
  fs.writeFileSync(envPath, 'DATABASE=reviewed_database\n')
  const result = spawnSync('bash', ['-c', [
    'set -eEuo pipefail',
    `RUN_ROOT=${JSON.stringify(directory)}`,
    `TEST_LOG=${JSON.stringify(logPath)}`,
    `ENV_PATH=${JSON.stringify(envPath)}`,
    'capacity_preflight_pair() { printf "preflight\\n" >> "${TEST_LOG}"; }',
    'write_capacity_pair_journal() { printf "journal:%s\\n" "$2" >> "${TEST_LOG}"; }',
    'capacity_pair_failure() { printf "failure:%s\\n" "$1" >> "${TEST_LOG}"; exit "$1"; }',
    'capacity_pair_abort() { return 1; }',
    'fence_and_verify_capacity_database() { printf "mutate:fence\\n" >> "${TEST_LOG}"; }',
    'open_handle_probe() { printf "clear\\n"; }',
    'runtime_configuration_reference_probe() { printf "clear\\n"; }',
    'process_environment_reference_probe() { printf "clear\\t0\\n"; }',
    'probe_capacity_database_existence() { printf "absent\\n"; }',
    'record_result() { return 0; }',
    'mv() { printf "mutate:env_move\\n" >> "${TEST_LOG}"; command mv "$@"; }',
    'sudo() {',
    '  local arguments="$*"',
    '  [[ "${arguments}" != *"pg_terminate_backend"* ]] || return 90',
    '  if [[ "${arguments}" == *"SELECT format(\'DROP DATABASE"* ]]; then printf "DROP DATABASE reviewed_database\\n"; return 0; fi',
    '  if [[ "${arguments}" == *"--command=DROP DATABASE"* ]]; then printf "mutate:drop\\n" >> "${TEST_LOG}"; return 0; fi',
    '  return 91',
    '}',
    helper,
    `capacity_apply_pair db-id reviewed_database env-id ${JSON.stringify(envPath)} ${'a'.repeat(64)} 100 2 37 postgres true`,
  ].join('\n')], { encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr)
  const events = fs.readFileSync(logPath, 'utf8').trim().split('\n')
  const expectedOrder = [
    'preflight',
    'journal:fence_intent',
    'mutate:fence',
    'journal:env_move_intent',
    'mutate:env_move',
    'journal:drop_intent',
    'mutate:drop',
    'journal:completed',
  ]
  let prior = -1
  for (const event of expectedOrder) {
    const index = events.indexOf(event)
    assert.ok(index > prior, `${event} is out of order: ${events.join(',')}`)
    prior = index
  }
  assert.doesNotMatch(helper, /pg_terminate_backend/)
})

test('actual-state reconcile safely resolves fence, env-move, and drop crash windows', (t) => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  const helper = extractShellFunction(source, 'reconcile_capacity_pair_actual')
  assert.ok(helper, 'missing reconcile_capacity_pair_actual helper')
  for (const boundary of ['fence', 'env_move', 'drop']) {
    const directory = fs.mkdtempSync(path.join(require('node:os').tmpdir(), `chickenbro-reconcile-${boundary}-`))
    t.after(() => fs.rmSync(directory, { recursive: true, force: true }))
    fs.mkdirSync(path.join(directory, 'pair-journals'))
    const envPath = path.join(directory, 'reviewed.env')
    const quarantinePath = path.join(directory, 'env-id')
    const databaseState = path.join(directory, 'database.state')
    const allowsState = path.join(directory, 'allows.state')
    const logPath = path.join(directory, 'events.log')
    const envBody = 'DATABASE=reviewed_database\n'
    const envSha = sha256(Buffer.from(envBody))
    fs.writeFileSync(databaseState, boundary === 'drop' ? 'absent' : 'present')
    fs.writeFileSync(allowsState, 'false')
    if (boundary === 'fence') fs.writeFileSync(envPath, envBody)
    else fs.writeFileSync(quarantinePath, envBody)

    const result = spawnSync('bash', ['-c', [
      'set -euo pipefail',
      `RUN_ROOT=${JSON.stringify(directory)}`,
      `TEST_STAGE=${JSON.stringify(boundary)}`,
      `DATABASE_STATE=${JSON.stringify(databaseState)}`,
      `ALLOWS_STATE=${JSON.stringify(allowsState)}`,
      `TEST_LOG=${JSON.stringify(logPath)}`,
      'capacity_journal_intent_stage() { printf "%s\\n" "${TEST_STAGE}"; }',
      'probe_capacity_database_existence() { command cat "${DATABASE_STATE}"; }',
      'probe_capacity_database_identity() { printf "postgres\\t%s\\t100\\n" "$(command cat "${ALLOWS_STATE}")"; }',
      'fresh_database_counts() { [[ "$(command cat "${ALLOWS_STATE}")" == "true" ]] || return 88; printf "2\\t37\\n"; }',
      'restore_capacity_database_allow_connections() { printf "%s" "$2" > "${ALLOWS_STATE}"; printf "restore_allow:%s\\n" "$2" >> "${TEST_LOG}"; }',
      'capacity_exact_file_state() {',
      '  if [[ -f "$1" && ! -L "$1" ]]; then printf "exact\\n";',
      '  elif [[ ! -e "$1" && ! -L "$1" ]]; then printf "absent\\n";',
      '  else printf "error\\n"; return 1; fi',
      '}',
      'write_capacity_pair_journal() { printf "journal:%s\\n" "$2" >> "${TEST_LOG}"; }',
      helper,
      `reconcile_capacity_pair_actual db-id reviewed_database env-id ${JSON.stringify(envPath)} ${envSha} 100 2 37 postgres true`,
    ].join('\n')], { encoding: 'utf8' })
    assert.equal(result.status, 0, `${boundary}: ${result.stderr}`)
    const events = fs.readFileSync(logPath, 'utf8').trim().split('\n')
    if (boundary === 'drop') {
      assert.ok(events.includes('journal:reconciled_completed'))
      assert.ok(!fs.existsSync(envPath))
      assert.ok(fs.existsSync(quarantinePath))
    } else {
      assert.ok(events.includes('journal:reconciled_recovered'))
      assert.equal(fs.readFileSync(allowsState, 'utf8'), 'true')
      assert.equal(fs.readFileSync(envPath, 'utf8'), envBody)
      assert.ok(!fs.existsSync(quarantinePath))
    }
  }
})

test('post-action fence, env-move, and drop crashes enter actual-state reconciliation', (t) => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  const applyHelper = extractShellFunction(source, 'capacity_apply_pair')
  const failureHelper = extractShellFunction(source, 'capacity_pair_failure')
  assert.ok(applyHelper && failureHelper)
  for (const [boundary, expectedStatus] of [['fence', 71], ['env_move', 72], ['drop', 73]]) {
    const directory = fs.mkdtempSync(path.join(require('node:os').tmpdir(), `chickenbro-executed-${boundary}-`))
    t.after(() => fs.rmSync(directory, { recursive: true, force: true }))
    const envPath = path.join(directory, 'reviewed.env')
    const databaseState = path.join(directory, 'database.state')
    const allowsState = path.join(directory, 'allows.state')
    const logPath = path.join(directory, 'events.log')
    fs.writeFileSync(envPath, 'DATABASE=reviewed_database\n')
    fs.writeFileSync(databaseState, 'present')
    fs.writeFileSync(allowsState, 'true')
    fs.mkdirSync(path.join(directory, 'pair-journals'))
    const result = spawnSync('bash', ['-c', [
      'set -eEuo pipefail',
      `RUN_ROOT=${JSON.stringify(directory)}`,
      `ENV_PATH=${JSON.stringify(envPath)}`,
      `DATABASE_STATE=${JSON.stringify(databaseState)}`,
      `ALLOWS_STATE=${JSON.stringify(allowsState)}`,
      `TEST_LOG=${JSON.stringify(logPath)}`,
      `FAIL_BOUNDARY=${JSON.stringify(boundary)}`,
      'capacity_preflight_pair() { return 0; }',
      'write_capacity_pair_journal() { return 0; }',
      'capacity_pair_abort() { return 1; }',
      'record_result() { return 0; }',
      'open_handle_probe() { printf "clear\\n"; }',
      'runtime_configuration_reference_probe() { printf "clear\\n"; }',
      'process_environment_reference_probe() { printf "clear\\t0\\n"; }',
      'probe_capacity_database_existence() { command cat "${DATABASE_STATE}"; }',
      'fence_and_verify_capacity_database() {',
      '  printf "false" > "${ALLOWS_STATE}"',
      '  [[ "${FAIL_BOUNDARY}" != "fence" ]] || return 71',
      '}',
      'mv() {',
      '  command mv "$@"',
      '  [[ "${FAIL_BOUNDARY}" != "env_move" ]] || return 72',
      '}',
      'sudo() {',
      '  local arguments="$*"',
      '  if [[ "${arguments}" == *"SELECT format(\'DROP DATABASE"* ]]; then printf "DROP DATABASE reviewed_database\\n"; return 0; fi',
      '  if [[ "${arguments}" == *"--command=DROP DATABASE"* ]]; then',
      '    printf "absent" > "${DATABASE_STATE}"',
      '    [[ "${FAIL_BOUNDARY}" != "drop" ]] || return 73',
      '    return 0',
      '  fi',
      '  return 90',
      '}',
      'reconcile_capacity_pair_actual() {',
      '  local quarantine="${RUN_ROOT}/env-id"',
      '  local observed_database observed_allows',
      '  observed_database="$(command cat "${DATABASE_STATE}")"',
      '  observed_allows="$(command cat "${ALLOWS_STATE}")"',
      '  case "${FAIL_BOUNDARY}" in',
      '    fence) [[ "${observed_database}:${observed_allows}" == "present:false" && -f "${ENV_PATH}" && ! -e "${quarantine}" ]] ;;',
      '    env_move) [[ "${observed_database}:${observed_allows}" == "present:false" && ! -e "${ENV_PATH}" && -f "${quarantine}" ]] ;;',
      '    drop) [[ "${observed_database}:${observed_allows}" == "absent:false" && ! -e "${ENV_PATH}" && -f "${quarantine}" ]] ;;',
      '  esac',
      '  printf "reconcile:%s\\n" "${FAIL_BOUNDARY}" >> "${TEST_LOG}"',
      '}',
      failureHelper,
      applyHelper,
      `capacity_apply_pair db-id reviewed_database env-id ${JSON.stringify(envPath)} ${'a'.repeat(64)} 100 2 37 postgres true`,
    ].join('\n')], { encoding: 'utf8' })
    assert.equal(result.status, expectedStatus, `${boundary}: ${result.stderr}`)
    assert.equal(fs.readFileSync(logPath, 'utf8').trim(), `reconcile:${boundary}`)
  }
})

test('an existing capacity run only reconciles actual state and requires a fresh manifest', (t) => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  const helper = extractShellFunction(source, 'capacity_resume_existing_run')
  assert.ok(helper, 'missing capacity_resume_existing_run helper')
  const directory = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'chickenbro-resume-'))
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }))
  const pairsPath = path.join(directory, 'capacity-pairs.tsv')
  const logPath = path.join(directory, 'events.log')
  const sha = 'a'.repeat(64)
  fs.writeFileSync(pairsPath, [
    `db-one\treviewed_one\tenv-one\t/etc/one.env\t${sha}\t100\t2\t37\tpostgres\ttrue`,
    `db-two\treviewed_two\tenv-two\t/etc/two.env\t${sha}\t200\t3\t41\tpostgres\ttrue`,
  ].join('\n') + '\n')

  const result = spawnSync('bash', ['-c', [
    'set -u',
    `CAPACITY_PAIRS=${JSON.stringify(pairsPath)}`,
    `TEST_LOG=${JSON.stringify(logPath)}`,
    'reconcile_capacity_pair_actual() { printf "reconcile:%s\\n" "$2" >> "${TEST_LOG}"; }',
    'capacity_apply_pair() { printf "MUTATED\\n" >> "${TEST_LOG}"; }',
    helper,
    'set +e',
    'capacity_resume_existing_run',
    'status=$?',
    'printf "status:%s\\n" "${status}" >> "${TEST_LOG}"',
    'exit 0',
  ].join('\n')], { encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr)
  const events = fs.readFileSync(logPath, 'utf8').trim().split('\n')
  assert.deepEqual(events, ['reconcile:reviewed_one', 'reconcile:reviewed_two', 'status:75'])
  assert.match(result.stderr, /fresh.*inventory.*manifest/i)
})

test('the same manifest run root is detected before O_EXCL artifacts and never blindly replayed', () => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  const runRoot = source.indexOf('RUN_ROOT="${QUARANTINE_ROOT}/${REVIEWED_REMOTE_MANIFEST_SHA}"')
  const existingCheck = source.indexOf('if [[ -e "${RUN_ROOT}" ]]', runRoot)
  const runRootInstall = source.indexOf('install -d -o root -g root -m 0700 -- "${RUN_ROOT}"', runRoot)
  assert.ok(runRoot > 0 && existingCheck > runRoot && existingCheck < runRootInstall)
  const resumeCall = source.indexOf('    capacity_resume_existing_run', runRootInstall)
  const applyCall = source.indexOf('  capacity_apply_pairs', resumeCall)
  assert.ok(resumeCall > runRootInstall && applyCall > resumeCall)
  assert.match(source.slice(resumeCall - 500, resumeCall), /RUN_ROOT_EXISTED.*true/)
  assert.doesNotMatch(source.slice(existingCheck, resumeCall), /\n  capacity_apply_pairs\n/)
})

test('between-pair drift aborts before the later pair mutates', (t) => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  const preflightAll = extractShellFunction(source, 'capacity_preflight_all_pairs')
  const applyAll = extractShellFunction(source, 'capacity_apply_pairs')
  assert.ok(preflightAll && applyAll, 'missing capacity pair orchestration helpers')
  const directory = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'chickenbro-between-pairs-'))
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }))
  const pairsPath = path.join(directory, 'pairs.tsv')
  const logPath = path.join(directory, 'events.log')
  const sha = 'a'.repeat(64)
  fs.writeFileSync(pairsPath, [
    `db-one\treviewed_one\tenv-one\t/etc/one.env\t${sha}\t100\t2\t37\tpostgres\ttrue`,
    `db-two\treviewed_two\tenv-two\t/etc/two.env\t${sha}\t200\t3\t41\tpostgres\ttrue`,
  ].join('\n') + '\n')

  const result = spawnSync('bash', ['-c', [
    'set -euo pipefail',
    `RUN_ROOT=${JSON.stringify(directory)}`,
    `CAPACITY_PAIRS=${JSON.stringify(pairsPath)}`,
    `TEST_LOG=${JSON.stringify(logPath)}`,
    'DRIFTED=false',
    'install() { command mkdir -p "${9}"; }',
    'capacity_preflight_pair() {',
    '  printf "preflight:%s\\n" "$2" >> "${TEST_LOG}"',
    '  if [[ "$2" == "reviewed_two" && "${DRIFTED}" == "true" ]]; then return 86; fi',
    '}',
    'write_capacity_pair_journal() { printf "journal:%s\\n" "$3" >> "${TEST_LOG}"; }',
    'capacity_apply_pair() {',
    '  capacity_preflight_pair "$@"',
    '  printf "mutate:%s\\n" "$2" >> "${TEST_LOG}"',
    '  [[ "$2" != "reviewed_one" ]] || DRIFTED=true',
    '}',
    preflightAll,
    applyAll,
    'capacity_preflight_all_pairs',
    'capacity_apply_pairs',
  ].join('\n')], { encoding: 'utf8' })
  assert.equal(result.status, 86, result.stderr)
  const events = fs.readFileSync(logPath, 'utf8').trim().split('\n')
  assert.ok(events.includes('mutate:reviewed_one'))
  assert.equal(events.filter((event) => event === 'preflight:reviewed_two').length, 2)
  assert.ok(!events.includes('mutate:reviewed_two'))
})

test('capacity database preflight permits only its exact companion then requires zero references after quarantine', () => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  assert.match(source, /configuration references differ from exact companion/)
  assert.match(source, /database still has configuration references after companion quarantine/)
  assert.match(source, /runtime_configuration_reference_probe/)
  assert.match(source, /process_environment_reference_probe/)
  assert.match(source, /open_handle_probe/)
  assert.doesNotMatch(source, /pg_terminate_backend/)
})

test('remote metadata refresh precedes temporary files and quarantine directories', () => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  const remote = source.slice(source.indexOf("bash -s <<'REMOTE'"))
  const rootCheck = remote.indexOf('require_remote_root')
  const metadata = remote.indexOf('LIVE_INSTANCE_ID=')
  assert.ok(rootCheck > 0 && rootCheck < metadata)
  assert.ok(metadata < remote.indexOf('MANIFEST_TMP="$(mktemp)"'))
  assert.ok(metadata < remote.indexOf('install -d -o root -g root -m 0700 -- "${RUN_ROOT}"'))
})

test('the complete remote heredoc enters one non-interactive root context and rejects non-root execution', () => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  assert.match(source, /"\$\{SSH_TARGET\}"\s+sudo -n env[\s\S]*?bash -s <<'REMOTE'/)
  const helper = extractShellFunction(source, 'require_remote_root')
  assert.ok(helper, 'missing require_remote_root helper')
  const result = spawnSync('bash', ['-c', [
    'set -u',
    'die_remote() { return 77; }',
    helper,
    'require_remote_root',
  ].join('\n')], { encoding: 'utf8' })
  assert.equal(result.status, 77, result.stderr)
})

test('remote recovery traps inherit through apply helpers', () => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  const remote = source.slice(source.indexOf("bash -s <<'REMOTE'"))
  assert.match(remote, /^bash -s <<'REMOTE'\nset -Eeuo pipefail/m)
})

test('manifest and dry-run contain no secret-bearing fields or values', () => {
  const serialized = fs.readFileSync(manifestPath, 'utf8').toLowerCase()
  for (const forbidden of ['password', 'secret', 'cookie', 'openid', 'unionid', 'databaseurl']) {
    assert.doesNotMatch(serialized, new RegExp(`"${forbidden}"\\s*:`))
  }
  assert.doesNotMatch(serialized, /postgres(?:ql)?:\/\/[^\s/@:]+:[^\s/@]+@/)
})

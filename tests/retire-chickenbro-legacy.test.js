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

function sourceAndValidate(kind, target) {
  return spawnSync('bash', ['-c', 'source "$1"; validate_deletion_target "$2" "$3"', 'test', scriptPath, kind, target], {
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

test('exact allowlisted legacy resource shapes pass target validation', () => {
  for (const [kind, target] of [
    ['postgres_database', 'wow_test'],
    ['systemd_unit', 'wow-backend.service'],
    ['file', '/etc/wow-v2-api.env'],
    ['directory', '/opt/wow-mini-program'],
  ]) {
    const result = sourceAndValidate(kind, target)
    assert.equal(result.status, 0, result.stderr)
  }
})

test('cloud cleanup manifest covers every observed legacy unit and database exactly', () => {
  const inventoryBytes = fs.readFileSync(inventoryPath)
  const inventory = JSON.parse(inventoryBytes)
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))

  assert.equal(manifest.schemaVersion, 1)
  assert.equal(manifest.mode, 'dry-run')
  assert.equal(manifest.deletionAuthorized, false)
  assert.equal(manifest.sourceInventory.path, 'docs/refactor/chickenbro-simc-cloud-inventory.json')
  assert.equal(manifest.sourceInventory.sha256, sha256(inventoryBytes))
  assert.equal(manifest.sourceInventory.observedAt, inventory.observedAt)
  assert.equal(manifest.independentRecovery.status, 'missing')
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

test('apply fails closed before remote execution without reviewed identities and ready gates', () => {
  const result = spawnSync('bash', [scriptPath, '--manifest', manifestPath, '--apply'], {
    cwd: repositoryRoot,
    encoding: 'utf8',
  })
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /--apply requires --manifest-sha and --backup-manifest-sha/i)

  const manifestSha = sha256(fs.readFileSync(manifestPath))
  const blocked = spawnSync('bash', [
    scriptPath,
    '--manifest', manifestPath,
    '--apply',
    '--manifest-sha', manifestSha,
    '--backup-manifest-sha', 'a'.repeat(64),
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
  assert.match(source, /restore-verified\.json/)
})

test('manifest and dry-run contain no secret-bearing fields or values', () => {
  const serialized = fs.readFileSync(manifestPath, 'utf8').toLowerCase()
  for (const forbidden of ['password', 'secret', 'cookie', 'openid', 'unionid', 'databaseurl']) {
    assert.doesNotMatch(serialized, new RegExp(`"${forbidden}"\\s*:`))
  }
  assert.doesNotMatch(serialized, /postgres(?:ql)?:\/\/[^\s/@:]+:[^\s/@]+@/)
})

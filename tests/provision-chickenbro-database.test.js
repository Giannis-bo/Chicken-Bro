const assert = require('node:assert/strict')
const { createHash } = require('node:crypto')
const { readFileSync } = require('node:fs')
const { spawnSync } = require('node:child_process')
const path = require('node:path')
const test = require('node:test')

const ROOT = path.resolve(__dirname, '..')
const SCRIPT = path.join(ROOT, 'server', 'provision_chickenbro_database_lighthouse.sh')
const INVENTORY = path.join(ROOT, 'docs', 'refactor', 'chickenbro-simc-cloud-inventory.json')

function source() {
  return readFileSync(SCRIPT, 'utf8')
}

function inventorySha() {
  return createHash('sha256').update(readFileSync(INVENTORY)).digest('hex')
}

function run(args = [], env = {}) {
  return spawnSync('bash', [SCRIPT, ...args], {
    cwd: ROOT,
    encoding: 'utf8',
    env: { ...process.env, ...env },
  })
}

test('provisioning is fixed-target dry-run by default and contains no destructive legacy operation', () => {
  const script = source()

  assert.match(script, /MODE="dry-run"/)
  assert.match(script, /TARGET_DATABASE="chickenbro_prod"/)
  assert.match(script, /SOURCE_DATABASE="wow_test"/)
  assert.match(script, /blocked_until_independent_legacy_cleanup_or_storage_expansion/)
  assert.doesNotMatch(script, /\bDROP\s+DATABASE\b/i)
  assert.doesNotMatch(script, /\bdropdb\b/i)
  assert.doesNotMatch(script, /rm\s+-[^\n]*r[^\n]*f|rm\s+-[^\n]*f[^\n]*r/i)
})

test('apply path is fail-closed on reviewed state, capacity, independent backup and restore-list gates', () => {
  const script = source()

  for (const contract of [
    'candidateDatabaseProvisioningAuthorized',
    '--inventory-sha',
    '--backup-device',
    'WOW_REBUILD_BACKUP_ROOT',
    'WOW_REBUILD_MANAGEMENT_ROLE',
    'stat -c',
    'df -PB1',
    'pg_database_size',
    'pg_dump',
    'pg_restore --list',
    'server/migrations/product',
    'ops.schema_migrations',
    'UNEXPECTED_SCHEMA_COUNT',
    'runtime_business_delete',
    'public',
    'content',
    'cache',
    'knowledge',
    'analytics',
    'INVENTORY_OBSERVED_AT',
    'INVENTORY_MAX_AGE_SECONDS',
  ]) {
    assert.ok(script.includes(contract), `missing apply gate: ${contract}`)
  }
  assert.match(script, /POSTGRES_DEVICE_ID[^\n]*BACKUP_DEVICE_ID|BACKUP_DEVICE_ID[^\n]*POSTGRES_DEVICE_ID/)
  assert.match(script, /TARGET_DATABASE_EXISTS/)
  assert.match(script, /TARGET_CONNECTIONS/)
  assert.match(script, /rolname\s*=\s*current_user[\s\S]{0,200}rolcreatedb/)
})

test('local dry-run emits redacted blocked JSON and performs no prerequisite command check', () => {
  const result = run([], {
    WOW_REBUILD_BACKUP_ROOT: '/do-not-print/private-backup',
    WOW_REBUILD_MANAGEMENT_ROLE: 'do_not_print_role',
  })

  assert.equal(result.status, 0, result.stderr)
  const payload = JSON.parse(result.stdout)
  assert.equal(payload.mode, 'dry-run')
  assert.equal(payload.targetDatabase, 'chickenbro_prod')
  assert.equal(payload.sourceDatabase, 'wow_test')
  assert.equal(payload.capacityGate, 'blocked_until_independent_legacy_cleanup_or_storage_expansion')
  assert.equal(payload.mutationAuthorized, false)
  assert.equal(payload.inventorySha, inventorySha())
  assert.doesNotMatch(result.stdout + result.stderr, /do-not-print|private-backup/i)
})

test('reviewed inventory hash is exact and apply stops before external state while authorization is false', () => {
  const wrong = run(['--dry-run', '--inventory-sha', '0'.repeat(64)])
  assert.notEqual(wrong.status, 0)
  assert.match(wrong.stderr, /inventory SHA does not match/i)

  const blocked = run([
    '--apply',
    '--inventory-sha', inventorySha(),
    '--backup-device', '/approved/independent-device',
  ], {
    WOW_REBUILD_BACKUP_ROOT: '/approved/independent-device/rebuild',
    WOW_REBUILD_MANAGEMENT_ROLE: 'postgres',
  })
  assert.notEqual(blocked.status, 0)
  assert.match(blocked.stderr, /candidateDatabaseProvisioningAuthorized=false/)
  assert.doesNotMatch(blocked.stdout + blocked.stderr, /postgresql:\/\/|password|secret/i)
})

test('script has valid bash syntax', () => {
  const result = spawnSync('bash', ['-n', SCRIPT], { cwd: ROOT, encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr)
})

const assert = require('node:assert/strict')
const { createHash } = require('node:crypto')
const { chmodSync, mkdtempSync, readFileSync, rmSync, writeFileSync } = require('node:fs')
const { spawnSync } = require('node:child_process')
const os = require('node:os')
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
  assert.match(script, /blocked_until_whitelist_recovery_and_exact_capacity_cleanup_or_storage_expansion/)
  assert.doesNotMatch(script, /\bDROP\s+DATABASE\b/i)
  assert.doesNotMatch(script, /\bdropdb\b/i)
  assert.doesNotMatch(script, /rm\s+-[^\n]*r[^\n]*f|rm\s+-[^\n]*f[^\n]*r/i)
})

test('apply path builds and restore-verifies only the migrated business whitelist', () => {
  const script = source()

  for (const contract of [
    'candidateDatabaseProvisioningAuthorized',
    '--inventory-sha',
    'WOW_CHICKENBRO_RECOVERY_ROOT',
    'MIGRATION_RUNTIME_PYTHON',
    'df -B1 --output=avail',
    'pg_database_size',
    'pg_dump',
    'pg_restore --list',
    '--exit-on-error',
    'server.migrations.product.postgres_legacy',
    'MIGRATION_RECONCILIATION_DIVERGED',
    'chickenbro-whitelist-recovery-v1',
    'chickenbro_restore_verify_',
    'restoreReconciliationSha256',
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
  assert.doesNotMatch(script, /--backup-device|WOW_REBUILD_BACKUP_ROOT|BACKUP_DEVICE_ID/)
  assert.doesNotMatch(script, /pg_dump[\s\S]{0,220}--dbname="\$\{SOURCE_DATABASE\}"/)
  assert.match(script, /pg_dump[\s\S]{0,220}--dbname="\$\{TARGET_DATABASE\}"/)
  assert.match(script, /"\$\{MIGRATION_RUNTIME_PYTHON\}" -m server\.migrations\.product\.postgres_legacy/)
  assert.match(script, /TARGET_DATABASE_EXISTS/)
  assert.match(script, /TARGET_CONNECTIONS/)
  assert.match(script, /target database already exists; a fresh clean target is required/)
  assert.doesNotMatch(script, /already_provisioned_exact_identity/)
  assert.match(script, /rolname = '\$\{DATABASE_OWNER_ROLE\}' AND rolcanlogin/)
  assert.match(script, /--mode verify-restore/)
  assert.doesNotMatch(
    script.slice(script.indexOf('pg_restore \\\n'), script.indexOf('RECOVERY_MANIFEST_NEW=')),
    /--mode full/,
  )
  assert.doesNotMatch(
    script.slice(script.indexOf('sudo -n -u postgres pg_restore \\\n'), script.indexOf('VERIFY_DATABASE_URL=')),
    /--no-owner/,
    'restore must preserve the schema/object owners covered by the identity comparison',
  )
})

test('restore streams the root-only whitelist archive into the postgres process', () => {
  const script = source()
  const restoreStart = script.indexOf('sudo -n -u postgres pg_restore \\\n')
  const restoreEnd = script.indexOf('VERIFY_DATABASE_URL=', restoreStart)

  assert.ok(restoreStart >= 0 && restoreEnd > restoreStart, 'missing isolated restore command')
  const restoreCommand = script.slice(restoreStart, restoreEnd)
  assert.match(
    restoreCommand,
    /--dbname="\$\{VERIFY_DATABASE\}" \\\n\s*< "\$\{WHITELIST_ARCHIVE\}"/,
    'the root shell must open the archive before sudo changes identity to postgres',
  )
  assert.doesNotMatch(
    restoreCommand,
    /\n\s*"\$\{WHITELIST_ARCHIVE\}"/,
    'postgres cannot open a path below the mode-0700 recovery directory',
  )
})

test('apply uses peer-authenticated postgres management and exact staged app pgpass entries', () => {
  const script = source()

  assert.match(script, /sudo -n -u postgres psql/)
  assert.doesNotMatch(script, /--username="\$\{MANAGEMENT_ROLE\}"/)
  assert.match(script, /source\/target\/restore pgpass entries/i)
  assert.match(script, /PGPASSFILE="\$\{STAGED_PGPASSFILE\}"/)
  assert.match(script, /current_user[\s\S]{0,120}postgres/)
  const firstHostMutation = script.indexOf('install -d -o root -g root -m 0700 "${RECOVERY_ROOT}"')
  assert.ok(script.indexOf("pg_query 'SELECT current_user'") < firstHostMutation)
  assert.ok(script.indexOf('explicit source wow_app authentication preflight failed') < firstHostMutation)
})

test('GNU df capacity probe does not combine POSIX mode with output selection', () => {
  const script = source()
  const match = script.match(/df_available_bytes\(\) \{[\s\S]*?\n\}/)
  assert.ok(match, 'missing df_available_bytes helper')
  assert.doesNotMatch(match[0], /\s-P(?:B1)?\s|\s-P\s/)

  const directory = mkdtempSync(path.join(os.tmpdir(), 'chickenbro-df-'))
  const stub = path.join(directory, 'df')
  writeFileSync(stub, `#!/usr/bin/env bash\nif [[ " $* " == *" -P "* || " $* " == *" -PB1 "* ]]; then exit 64; fi\nprintf 'Avail\\n987654321\\n'\n`)
  chmodSync(stub, 0o755)
  try {
    const result = spawnSync('bash', ['-c', `${match[0]}\ndf_available_bytes /var/lib/postgresql`], {
      encoding: 'utf8',
      env: { ...process.env, PATH: `${directory}:${process.env.PATH}` },
    })
    assert.equal(result.status, 0, result.stderr)
    assert.equal(result.stdout.trim(), '987654321')
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
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
  assert.equal(
    payload.capacityGate,
    'blocked_until_whitelist_recovery_and_exact_capacity_cleanup_or_storage_expansion',
  )
  assert.equal(payload.mutationAuthorized, false)
  assert.equal(payload.inventorySha, inventorySha())
  assert.doesNotMatch(result.stdout + result.stderr, /do-not-print|private-backup/i)
})

test('reviewed inventory hash is exact and authorized apply still stops before external state without an exact pgpass path', () => {
  const wrong = run(['--dry-run', '--inventory-sha', '0'.repeat(64)])
  assert.notEqual(wrong.status, 0)
  assert.match(wrong.stderr, /inventory SHA does not match/i)

  const blocked = run([
    '--apply',
    '--inventory-sha', inventorySha(),
  ], {
    WOW_CHICKENBRO_RECOVERY_ROOT: '/var/lib/chickenbro-recovery',
    WOW_REBUILD_MANAGEMENT_ROLE: 'postgres',
  })
  assert.notEqual(blocked.status, 0)
  assert.match(blocked.stderr, /WOW_REBUILD_PGPASSFILE must be an absolute path/)
  assert.doesNotMatch(blocked.stdout + blocked.stderr, /postgresql:\/\/|password|secret/i)
})

test('apply refreshes and matches the exact Tencent CVM identity before database work', () => {
  const script = source()

  for (const expected of [
    'ins-93tgv1rb',
    'ap-shanghai',
    'ap-shanghai-2',
    '124.223.51.33',
    'metadata.tencentyun.com/latest/meta-data/instance-id',
    'metadata.tencentyun.com/latest/meta-data/placement/region',
    'metadata.tencentyun.com/latest/meta-data/placement/zone',
  ]) {
    assert.ok(script.includes(expected), `missing target identity gate: ${expected}`)
  }
  assert.match(script, /refresh_target_identity/)
  assert.match(script, /target identity mismatch/i)
  assert.ok(
    script.indexOf('refresh_target_identity\n') < script.indexOf('install -d -o root -g root -m 0700 "${RECOVERY_ROOT}"'),
    'metadata refresh must be the first apply-side action',
  )
})

test('script has valid bash syntax', () => {
  const result = spawnSync('bash', ['-n', SCRIPT], { cwd: ROOT, encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr)
})

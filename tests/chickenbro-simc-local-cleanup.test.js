const assert = require('node:assert/strict')
const crypto = require('node:crypto')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')
const { spawnSync } = require('node:child_process')

const cleanupPath = path.resolve(__dirname, '../scripts/apply-chickenbro-simc-local-cleanup.js')

function loadCleanup() {
  return require(cleanupPath)
}

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex')
}

function memoryRepository(files, options = {}) {
  const state = new Map(Object.entries(files).map(([name, value]) => [name, Buffer.from(value)]))
  const deleted = []
  return {
    headCommit: options.headCommit || 'a'.repeat(40),
    phase5Accepted: options.phase5Accepted === true,
    matchesInventoryBase: options.matchesInventoryBase,
    listTrackedFiles: () => [...state.keys()].sort(),
    readFile: (name) => {
      if (!state.has(name)) throw new Error(`missing ${name}`)
      return state.get(name)
    },
    isRegularFile: (name) => state.has(name),
    deleteFile: (name) => {
      if (!state.delete(name)) throw new Error(`missing ${name}`)
      deleted.push(name)
    },
    deleted,
    has: (name) => state.has(name),
  }
}

function inventoryFor(entries, commit = 'a'.repeat(40)) {
  const { computeInventorySha256 } = loadCleanup()
  const dispositionCounts = {}
  const categoryCounts = {}
  for (const entry of entries) {
    dispositionCounts[entry.disposition] = (dispositionCounts[entry.disposition] || 0) + 1
    categoryCounts[entry.category] = (categoryCounts[entry.category] || 0) + 1
  }
  const inventory = {
    schemaVersion: 1,
    generatedFromCommit: commit,
    excludedSelfPath: 'docs/refactor/chickenbro-simc-refactor-inventory.json',
    sourceRulesSha256: 'b'.repeat(64),
    entryCount: entries.length,
    unresolvedCount: dispositionCounts.review || 0,
    dispositionCounts,
    categoryCounts,
    entries,
  }
  return { ...inventory, inventorySha256: computeInventorySha256(inventory) }
}

function entry(name, disposition, content, category = 'fixture') {
  return {
    path: name,
    disposition,
    category,
    owner: 'test',
    reason: 'fixture',
    matchedRule: 'fixture',
    bytes: Buffer.byteLength(content),
    sha256: sha256(content),
  }
}

test('cleanup accepts exact files and rejects directories, globs and broad roots', () => {
  const { validateTarget } = loadCleanup()

  assert.equal(validateTarget('server/news_backend.py'), 'server/news_backend.py')
  for (const invalid of [
    '', '.', '..', '../legacy.py', '/server/legacy.py', 'server/', 'docs/**',
    'server/*.py', 'server/[ab].py', '~', '$HOME', 'C:\\legacy.py',
  ]) {
    assert.throws(() => validateTarget(invalid), /exact file/i, invalid)
  }
})

test('changed or missing delete targets fail closed before caller analysis', () => {
  const { verifyCleanup, verifyHash } = loadCleanup()
  const deleteEntry = entry('server/legacy.py', 'delete', 'old\n')

  assert.throws(
    () => verifyHash('server/legacy.py', Buffer.from('changed\n'), deleteEntry.sha256),
    /hash mismatch/i,
  )
  const changed = verifyCleanup(
    inventoryFor([deleteEntry]),
    memoryRepository({ 'server/legacy.py': 'changed\n' }),
  )
  assert.equal(changed.deletable.length, 0)
  assert.equal(changed.blocked[0].reason, 'HASH_MISMATCH')

  const missing = verifyCleanup(inventoryFor([deleteEntry]), memoryRepository({}))
  assert.equal(missing.blocked[0].reason, 'TARGET_MISSING')
})

test('a retained import, documentation link or route literal blocks deletion', () => {
  const { verifyCleanup } = loadCleanup()
  const legacy = entry('server/legacy.py', 'delete', 'old\n')
  const importCaller = entry(
    'server/current.py',
    'keep',
    'from server.legacy import run\n',
  )
  const docsCaller = entry(
    'docs/current.md',
    'keep',
    '[legacy](../server/legacy.py)\n',
  )
  const route = entry('pages/legacy/index.js', 'delete', 'Page({})\n')
  const configCaller = entry(
    'apps/mini-taro/src/app.config.ts',
    'migrate',
    "export default { pages: ['pages/legacy/index'] }\n",
  )
  const entries = [legacy, importCaller, docsCaller, route, configCaller]
  const repository = memoryRepository(Object.fromEntries(entries.map((item) => [
    item.path,
    item.path === legacy.path
      ? 'old\n'
      : item.path === importCaller.path
        ? 'from server.legacy import run\n'
        : item.path === docsCaller.path
          ? '[legacy](../server/legacy.py)\n'
          : item.path === route.path
            ? 'Page({})\n'
            : "export default { pages: ['pages/legacy/index'] }\n",
  ])))

  const result = verifyCleanup(inventoryFor(entries), repository)
  const legacyBlock = result.blocked.find((item) => item.path === legacy.path)
  const routeBlock = result.blocked.find((item) => item.path === route.path)
  assert.equal(legacyBlock.reason, 'RETAINED_CALLER')
  assert.deepEqual(legacyBlock.callers, ['docs/current.md', 'server/current.py'])
  assert.equal(routeBlock.reason, 'RETAINED_CALLER')
  assert.deepEqual(routeBlock.callers, ['apps/mini-taro/src/app.config.ts'])
})

test('references from another exact delete target do not block an atomic cleanup set', () => {
  const { verifyCleanup } = loadCleanup()
  const callerContent = "require('./target')\n"
  const entries = [
    entry('legacy/caller.js', 'delete', callerContent),
    entry('legacy/target.js', 'delete', 'module.exports = {}\n'),
  ]
  const result = verifyCleanup(
    inventoryFor(entries),
    memoryRepository({
      'legacy/caller.js': callerContent,
      'legacy/target.js': 'module.exports = {}\n',
    }),
  )
  assert.deepEqual(result.blocked, [])
  assert.deepEqual(result.deletable.map((item) => item.path), [
    'legacy/caller.js',
    'legacy/target.js',
  ])
})

test('plain prose and cleanup-control fixtures are not treated as runtime callers', () => {
  const { verifyCleanup } = loadCleanup()
  const entries = [
    entry('app.js', 'delete', 'legacy app\n'),
    entry('server/legacy.py', 'delete', 'old\n'),
    {
      ...entry('apps/current/index.html', 'keep', '<div id="app"></div>\n'),
      matchedRule: 'current-client',
    },
    {
      ...entry('docs/notes.md', 'keep', 'Retired server/legacy.py after cutover.\n'),
      matchedRule: 'current-docs',
    },
    {
      ...entry(
        'tests/cleanup-policy.test.js',
        'keep',
        "assert.equal(validateTarget('server/legacy.py'), 'server/legacy.py')\n",
        'current-control-plane',
      ),
      matchedRule: 'rebuild-inventory-owner',
    },
  ]
  const result = verifyCleanup(
    inventoryFor(entries),
    memoryRepository(Object.fromEntries(entries.map((item) => [
      item.path,
      item.path === 'app.js'
        ? 'legacy app\n'
        : item.path === 'server/legacy.py'
          ? 'old\n'
        : item.path === 'docs/notes.md'
          ? 'Retired server/legacy.py after cutover.\n'
          : item.path === 'apps/current/index.html'
            ? '<div id="app"></div>\n'
          : "assert.equal(validateTarget('server/legacy.py'), 'server/legacy.py')\n",
    ]))),
  )

  assert.deepEqual(result.blocked, [])
  assert.deepEqual(result.deletable.map((item) => item.path), ['app.js', 'server/legacy.py'])
})

test('immutable current-rebuild evidence records do not act as live callers', () => {
  const { verifyCleanup } = loadCleanup()
  const legacy = entry('server/legacy.py', 'delete', 'old\n')
  const evidence = {
    ...entry(
      'artifacts/releases/current/manifest.json',
      'keep',
      '{"observedPath":"server/legacy.py"}\n',
      'current-release-evidence',
    ),
    matchedRule: 'current-rebuild-release-packet',
  }
  const result = verifyCleanup(
    inventoryFor([legacy, evidence]),
    memoryRepository({
      'server/legacy.py': 'old\n',
      'artifacts/releases/current/manifest.json': '{"observedPath":"server/legacy.py"}\n',
    }),
  )

  assert.deepEqual(result.blocked, [])
  assert.deepEqual(result.deletable.map((item) => item.path), ['server/legacy.py'])
})

test('unclassified tracked files and inventory identity drift are review blockers', () => {
  const { verifyCleanup } = loadCleanup()
  const keep = entry('README.md', 'keep', 'current\n')
  const inventory = inventoryFor([keep])
  const repository = memoryRepository({
    'README.md': 'current\n',
    'future/new-owner.ts': 'export {}\n',
  })

  const result = verifyCleanup(inventory, repository)
  assert.deepEqual(result.review, [{ path: 'future/new-owner.ts', reason: 'UNCLASSIFIED_TRACKED_FILE' }])

  const drifted = { ...inventory, entryCount: 99 }
  assert.throws(() => verifyCleanup(drifted, repository), /inventory identity mismatch/i)

  const inconsistentCounts = {
    ...inventory,
    dispositionCounts: { keep: 99 },
  }
  inconsistentCounts.inventorySha256 = loadCleanup().computeInventorySha256(inconsistentCounts)
  assert.throws(
    () => verifyCleanup(inconsistentCounts, repository),
    /inventory identity mismatch: disposition counts/i,
  )
})

test('an inventory-only commit is accepted while any other post-base diff remains review', () => {
  const { verifyCleanup } = loadCleanup()
  const keep = entry('README.md', 'keep', 'current\n')
  const inventory = inventoryFor([keep])

  const inventoryOnly = verifyCleanup(
    inventory,
    memoryRepository({ 'README.md': 'current\n' }, {
      headCommit: 'c'.repeat(40),
      matchesInventoryBase: () => true,
    }),
  )
  assert.deepEqual(inventoryOnly.review, [])

  const codeDrift = verifyCleanup(
    inventory,
    memoryRepository({ 'README.md': 'current\n' }, {
      headCommit: 'c'.repeat(40),
      matchesInventoryBase: () => false,
    }),
  )
  assert.equal(codeDrift.review[0].reason, 'INVENTORY_BASE_COMMIT_DIFFERS_FROM_HEAD')
})

test('apply is atomic, exact, and requires Phase 5 accepted production evidence', () => {
  const { applyCleanup, verifyCleanup } = loadCleanup()
  const legacyContent = 'legacy\n'
  const keepContent = 'keep\n'
  const entries = [
    entry('legacy/old.js', 'delete', legacyContent),
    entry('current/keep.js', 'keep', keepContent),
  ]
  const inventory = inventoryFor(entries)
  const blockedRepository = memoryRepository({
    'legacy/old.js': legacyContent,
    'current/keep.js': keepContent,
  })
  const verified = verifyCleanup(inventory, blockedRepository)
  assert.throws(
    () => applyCleanup(verified, blockedRepository),
    /Phase 5 accepted production evidence/i,
  )
  assert.equal(blockedRepository.has('legacy/old.js'), true)

  const readyRepository = memoryRepository({
    'legacy/old.js': legacyContent,
    'current/keep.js': keepContent,
  }, { phase5Accepted: true })
  const ready = verifyCleanup(inventory, readyRepository)
  const applied = applyCleanup(ready, readyRepository)
  assert.deepEqual(applied.deleted, ['legacy/old.js'])
  assert.equal(readyRepository.has('legacy/old.js'), false)
  assert.equal(readyRepository.has('current/keep.js'), true)
})

test('Phase 5 acceptance reads the current project-state gate contract', (t) => {
  const { readPhase5Accepted } = loadCleanup()
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'chickenbro-phase5-gate-'))
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  const evidenceRelative = 'artifacts/releases/phase5/evidence.json'
  fs.mkdirSync(path.join(root, 'docs'), { recursive: true })
  fs.mkdirSync(path.join(root, 'artifacts/releases/phase5'), { recursive: true })
  fs.writeFileSync(path.join(root, 'docs/project-state.json'), `${JSON.stringify({
    schemaVersion: 2,
    gates: {
      phase5Evidence: evidenceRelative,
      productionCutoverAuthorized: true,
      productionCutoverReady: true,
    },
  })}\n`)
  fs.writeFileSync(path.join(root, evidenceRelative), `${JSON.stringify({
    highestEvidenceLevel: 'live_verified',
    manualAcceptance: { status: 'complete' },
    runtimeEvidence: [{
      type: 'production_cutover',
      state: 'accepted_write',
      postCutoverRealUserAcceptance: 'passed',
    }],
  })}\n`)

  assert.equal(readPhase5Accepted(root), true)

  const evidence = JSON.parse(fs.readFileSync(path.join(root, evidenceRelative), 'utf8'))
  evidence.manualAcceptance.status = 'complete_with_user_waiver'
  fs.writeFileSync(path.join(root, evidenceRelative), `${JSON.stringify(evidence)}\n`)
  assert.equal(readPhase5Accepted(root), true)

  evidence.manualAcceptance.status = 'pending'
  fs.writeFileSync(path.join(root, evidenceRelative), `${JSON.stringify(evidence)}\n`)
  assert.equal(readPhase5Accepted(root), false)
})

test('CLI reports retired targets as missing and cannot replay cleanup without review inputs', () => {
  const result = spawnSync(process.execPath, [
    cleanupPath,
    '--inventory',
    'docs/refactor/chickenbro-simc-refactor-inventory.json',
    '--dry-run',
  ], {
    cwd: path.resolve(__dirname, '..'),
    encoding: 'utf8',
  })
  assert.equal(result.status, 0, result.stderr)
  const payload = JSON.parse(result.stdout)
  assert.equal(payload.mode, 'dry-run')
  assert.equal(payload.mutationAuthorized, false)
  assert.equal(payload.counts.review, 0)
  assert.equal(payload.counts.deletable, 0)
  assert.equal(payload.counts.blocked, 2588)
  assert.ok(payload.blocked.every((item) => item.reason === 'TARGET_MISSING'))

  const apply = spawnSync(process.execPath, [
    cleanupPath,
    '--inventory',
    'docs/refactor/chickenbro-simc-refactor-inventory.json',
    '--apply',
  ], {
    cwd: path.resolve(__dirname, '..'),
    encoding: 'utf8',
  })
  assert.notEqual(apply.status, 0)
  assert.match(apply.stderr, /--apply requires --inventory-sha and --commit/)
})

test('cleanup implementation contains no recursive or shell-based delete primitive', () => {
  const source = fs.readFileSync(cleanupPath, 'utf8')
  assert.doesNotMatch(
    source,
    /rm\s+-r|rmSync|rmdirSync|exec(?:File)?Sync\(['"]rm|spawnSync\(['"]rm|shell:\s*true/,
  )
  assert.match(source, /unlinkSync/)
  assert.match(source, /productionCutoverAuthorized/)
  assert.match(source, /postCutoverRealUserAcceptance/)
})

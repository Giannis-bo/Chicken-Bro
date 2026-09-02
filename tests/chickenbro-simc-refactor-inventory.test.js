const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')
const { execFileSync, spawnSync } = require('node:child_process')

const {
  buildInventory,
  canonicalJson,
  classifyPath,
  loadRules,
  validateRules,
} = require('../scripts/build-chickenbro-simc-refactor-inventory')

const repositoryRoot = path.resolve(__dirname, '..')
const rulesPath = path.join(repositoryRoot, 'docs/refactor/chickenbro-simc-disposition-rules.json')
const generatedInventoryPath = 'docs/refactor/chickenbro-simc-refactor-inventory.json'
const builderPath = path.join(repositoryRoot, 'scripts/build-chickenbro-simc-refactor-inventory.js')

test('target owners are kept while prototype and legacy product surfaces are retired', () => {
  const rules = loadRules(rulesPath)

  assert.equal(classifyPath('server/app/chickenbro/domain.py', rules).disposition, 'keep')
  assert.equal(classifyPath('server/app/api/routes/prototype.py', rules).disposition, 'delete')
  assert.equal(classifyPath('apps/mini-taro/src/pages/news/news.tsx', rules).disposition, 'delete')
  assert.equal(classifyPath('server/news_backend.py', rules).disposition, 'delete')
  assert.equal(
    classifyPath('server/migrations/postgres/0038_chickenbro_simc_platform_foundation.sql', rules).disposition,
    'migrate',
  )
})

test('specific rules win before broader known-tree rules', () => {
  const rules = validateRules({
    schemaVersion: 1,
    rules: [
      {
        id: 'keep-target',
        disposition: 'keep',
        category: 'target-code',
        owner: 'target',
        reason: 'Target owner.',
        prefixes: ['server/app/chickenbro/'],
      },
      {
        id: 'retire-server',
        disposition: 'delete',
        category: 'legacy-code',
        owner: 'retirement',
        reason: 'Known legacy server tree.',
        prefixes: ['server/'],
      },
    ],
  })

  const result = classifyPath('server/app/chickenbro/domain.py', rules)
  assert.equal(result.disposition, 'keep')
  assert.equal(result.matchedRule, 'keep-target')
})

test('unknown top-level paths fail closed without a repository catch-all', () => {
  const rules = loadRules(rulesPath)
  assert.deepEqual(classifyPath('future-product/new-owner.ts', rules), {
    disposition: 'review',
    category: 'unresolved',
    owner: '',
    reason: 'NO_RULE_MATCH',
    matchedRule: '',
  })
  assert.throws(
    () =>
      validateRules({
        schemaVersion: 1,
        rules: [
          {
            id: 'forbidden-catch-all',
            disposition: 'delete',
            category: 'legacy',
            owner: 'retirement',
            reason: 'Invalid.',
            prefixes: [''],
          },
        ],
      }),
    /catch-all/i,
  )
})

test('inventory ordering, file hashes, and content hash are deterministic', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'chickenbro-simc-inventory-'))
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  fs.mkdirSync(path.join(root, 'known'), { recursive: true })
  fs.writeFileSync(path.join(root, 'known/a.txt'), 'alpha\n')
  fs.writeFileSync(path.join(root, 'known/b.txt'), 'beta\n')

  const rules = validateRules({
    schemaVersion: 1,
    rules: [
      {
        id: 'known-fixture',
        disposition: 'keep',
        category: 'fixture',
        owner: 'test',
        reason: 'Determinism fixture.',
        prefixes: ['known/'],
      },
    ],
  })
  const options = {
    root,
    commit: 'a'.repeat(40),
    rules,
    excludedSelfPath: generatedInventoryPath,
  }
  const first = buildInventory({ ...options, paths: ['known/b.txt', 'known/a.txt'] })
  const second = buildInventory({ ...options, paths: ['known/a.txt', 'known/b.txt'] })

  assert.deepEqual(first, second)
  assert.deepEqual(first.entries.map((entry) => entry.path), ['known/a.txt', 'known/b.txt'])
  assert.match(first.inventorySha256, /^[0-9a-f]{64}$/)
  assert.ok(first.entries.every((entry) => /^[0-9a-f]{64}$/.test(entry.sha256)))
  assert.equal(first.excludedSelfPath, generatedInventoryPath)
  assert.equal(first.unresolvedCount, 0)
  assert.equal(canonicalJson(first), canonicalJson(second))
})

test('every current repository path is classified and the inventory excludes only itself', () => {
  const rules = loadRules(rulesPath)
  const paths = execFileSync('git', ['ls-files', '-co', '--exclude-standard', '-z'], {
    cwd: repositoryRoot,
    encoding: 'utf8',
  })
    .split('\0')
    .filter(Boolean)
    .filter((relativePath) => relativePath !== generatedInventoryPath)

  const unresolved = paths
    .map((relativePath) => ({ relativePath, result: classifyPath(relativePath, rules) }))
    .filter(({ result }) => result.disposition === 'review')

  assert.deepEqual(unresolved, [])
})

test('CLI may replace only its output file while rejecting every other tracked change', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'chickenbro-simc-inventory-cli-'))
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  fs.mkdirSync(path.join(root, 'known'), { recursive: true })
  fs.writeFileSync(path.join(root, 'known/a.txt'), 'alpha\n')
  fs.writeFileSync(path.join(root, 'inventory.json'), '{}\n')
  fs.writeFileSync(path.join(root, 'rules.json'), `${JSON.stringify({
    schemaVersion: 1,
    rules: [{
      id: 'fixture',
      disposition: 'keep',
      category: 'fixture',
      owner: 'test',
      reason: 'Fixture files.',
      paths: ['rules.json'],
      prefixes: ['known/'],
    }],
  })}\n`)
  execFileSync('git', ['init', '-q'], { cwd: root })
  execFileSync('git', ['config', 'user.name', 'Inventory Test'], { cwd: root })
  execFileSync('git', ['config', 'user.email', 'inventory@example.invalid'], { cwd: root })
  execFileSync('git', ['add', '.'], { cwd: root })
  execFileSync('git', ['commit', '-qm', 'fixture'], { cwd: root })

  fs.writeFileSync(path.join(root, 'inventory.json'), '{"stale":true}\n')
  const outputOnly = spawnSync(process.execPath, [
    builderPath,
    '--rules',
    'rules.json',
    '--output',
    'inventory.json',
  ], { cwd: root, encoding: 'utf8' })
  assert.equal(outputOnly.status, 0, outputOnly.stderr)

  fs.writeFileSync(path.join(root, 'known/a.txt'), 'changed\n')
  const codeDrift = spawnSync(process.execPath, [
    builderPath,
    '--rules',
    'rules.json',
    '--output',
    'inventory.json',
  ], { cwd: root, encoding: 'utf8' })
  assert.notEqual(codeDrift.status, 0)
  assert.match(codeDrift.stderr, /tracked worktree must be clean/i)
})

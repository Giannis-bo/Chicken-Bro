const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const {
  collectGearCatalogCallers,
  writeCallerAudit,
} = require('../scripts/audit-gear-catalog-callers')

function writeFixture(root, relativePath, content) {
  const filePath = path.join(root, relativePath)
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  fs.writeFileSync(filePath, content, 'utf8')
  return relativePath
}

function fixtureRepository() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-gear-caller-audit-'))
  const files = [
    writeFixture(root, 'server/runtime_reader.py', [
      'GEAR_PATH = "/api/websim/gear"',
      'binding = load_active_manifest_binding()',
    ].join('\n')),
    writeFixture(root, 'server/gear_release_store.py', [
      'def load_active_public_gear(self):',
      '    return {}',
      'def load_active_manifest_binding(self):',
      '    return {}',
    ].join('\n')),
    writeFixture(root, 'apps/mini-taro/src/api.ts', [
      'const endpoint = "/api/websim/gear/resolve"',
      'const revision = payload.gearCatalogRevision',
    ].join('\n')),
    writeFixture(root, 'packages/api-client/src/websim.ts', [
      'const revision = payload.gearCatalogReleaseId',
    ].join('\n')),
    writeFixture(root, 'packages/api-client/src/websim.test.ts', [
      'expect(payload.gearCatalogRevision).toBeDefined()',
    ].join('\n')),
    writeFixture(root, 'pages/builds/websim-api.js', [
      'const endpoint = "/api/websim/profile"',
    ].join('\n')),
    writeFixture(root, 'tests/runtime-reader.test.js', [
      'expect(path).toBe("/api/simulator/simc")',
    ].join('\n')),
    writeFixture(root, 'docs/catalog.md', [
      '`gearCatalogReleaseId` is documented here.',
    ].join('\n')),
    writeFixture(root, 'artifacts/releases/old/evidence.json', JSON.stringify({
      route: '/api/websim/gear',
    })),
    writeFixture(root, 'scripts/runtime-proxy.js', [
      'const revision = response.gearCatalogRevision',
    ].join('\n')),
    writeFixture(root, 'scripts/audit-gear-catalog-callers.js', [
      'const symbols = ["gearCatalogRevision"]',
    ].join('\n')),
    writeFixture(root, 'server/comments_only.py', [
      '# /api/websim/gear',
      '# load_active_public_gear()',
    ].join('\n')),
    writeFixture(root, 'apps/mini-taro/src/comments.ts', [
      '// /api/websim/profile',
      '/* gearCatalogRevision */',
    ].join('\n')),
  ]
  return { root, files }
}

test('caller audit separates runtime, Taro, compatibility, tests/docs and unresolved files', () => {
  const { root, files } = fixtureRepository()
  try {
    const result = collectGearCatalogCallers({ root, allowlist: files })

    assert.equal(result.schemaRevision, 'gear-catalog-callers-v1')
    assert.match(result.reportId, /^gear-catalog-callers:sha256:[0-9a-f]{64}$/)
    assert.deepEqual(
      result.categories.activeBackend.map((entry) => entry.path),
      ['server/runtime_reader.py', 'server/runtime_reader.py'],
    )
    assert.deepEqual(
      result.categories.taro.map((entry) => entry.path),
      [
        'apps/mini-taro/src/api.ts',
        'apps/mini-taro/src/api.ts',
        'packages/api-client/src/websim.ts',
      ],
    )
    assert.deepEqual(
      result.categories.compatibility.map((entry) => entry.path),
      ['pages/builds/websim-api.js'],
    )
    assert.deepEqual(
      result.categories.testsDocs.map((entry) => entry.path),
      [
        'artifacts/releases/old/evidence.json',
        'docs/catalog.md',
        'packages/api-client/src/websim.test.ts',
        'tests/runtime-reader.test.js',
      ],
    )
    assert.deepEqual(
      result.categories.unresolved.map((entry) => entry.path),
      ['scripts/runtime-proxy.js'],
    )
    assert.equal(result.runtimeCallerCount, 6)
    assert.equal(result.unresolvedCount, 1)
    assert.equal(result.status, 'partial')
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})

test('definitions and comments are not recorded as callers', () => {
  const { root, files } = fixtureRepository()
  try {
    const result = collectGearCatalogCallers({ root, allowlist: files })
    const serialized = JSON.stringify(result)

    assert.doesNotMatch(serialized, /server\/gear_release_store\.py/)
    assert.doesNotMatch(serialized, /comments_only/)
    assert.doesNotMatch(serialized, /comments\.ts/)
    assert.ok(
      Object.values(result.categories)
        .flat()
        .every((entry) => !Object.hasOwn(entry, 'source')),
    )
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})

test('report identity is stable across allowlist order', () => {
  const { root, files } = fixtureRepository()
  try {
    const first = collectGearCatalogCallers({ root, allowlist: files })
    const second = collectGearCatalogCallers({
      root,
      allowlist: [...files].reverse(),
    })

    assert.equal(first.reportId, second.reportId)
    assert.deepEqual(first, second)
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})

test('atomic output stays inside the repository and never overwrites', () => {
  const { root, files } = fixtureRepository()
  try {
    const report = collectGearCatalogCallers({ root, allowlist: files })
    const output = path.join(root, 'artifacts', 'caller-inventory.json')

    const written = writeCallerAudit({ root, output, report })

    assert.equal(written, 'artifacts/caller-inventory.json')
    assert.deepEqual(JSON.parse(fs.readFileSync(output, 'utf8')), report)
    assert.throws(
      () => writeCallerAudit({ root, output, report }),
      /already exists/,
    )
    assert.throws(
      () => writeCallerAudit({
        root,
        output: path.join(os.tmpdir(), 'outside-caller-inventory.json'),
        report,
      }),
      /inside the repository/,
    )
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})

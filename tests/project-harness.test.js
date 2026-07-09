const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const harnessScript = 'scripts/project-harness.js'

function runHarness(args = [], options = {}) {
  return spawnSync(process.execPath, [harnessScript, ...args], {
    encoding: 'utf8',
    ...options
  })
}

function writeFile(filePath, source) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  fs.writeFileSync(filePath, source)
}

test('project harness emits the current repo-native harness manifest as read-only JSON', () => {
  const result = runHarness(['--json', '--slug', 'harness-smoke', '--date', '2026-07-09'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const manifest = JSON.parse(result.stdout)
  assert.equal(manifest.status, 'project_harness_manifest_ready')
  assert.equal(manifest.schemaVersion, 1)
  assert.equal(manifest.harness.version, 'v0.2')
  assert.equal(manifest.harness.source, 'docs/harness.md')
  assert.equal(manifest.safety.noNetwork, true)
  assert.equal(manifest.safety.noDeploy, true)
  assert.equal(manifest.safety.noSsh, true)
  assert.equal(manifest.safety.productionWrites, false)
  assert.equal(manifest.write.enabled, false)
  assert.equal(manifest.evidence.dataHealth.status, 'not_collected')
  assert.equal(manifest.evidence.deploySmoke.status, 'not_run')
  assert.equal(manifest.evidence.localTests.status, 'not_run')
  assert.ok(Array.isArray(manifest.riskMatrix))
  assert.deepEqual(Object.keys(manifest.gates).sort(), [
    'currentTruth',
    'engineeringHealth',
    'evidencePromotion',
    'feedbackLoop',
    'impactMap',
    'ownershipContract',
    'releaseRollback',
    'requirementChallenge'
  ].sort())
  assert.ok(manifest.gates.currentTruth.sources.some((source) => source.path === 'docs/roadmap.md' && source.exists))
  assert.ok(manifest.gates.engineeringHealth.hotspotFiles.some((file) => file.path === 'server/websim_payload.py' && file.exists))
  assert.ok(manifest.gates.releaseRollback.rollbackStrategies.includes('resync_repair'))
})

test('project harness writes a local release manifest only when --write is requested', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-'))
  writeFile(path.join(root, 'docs/harness.md'), [
    '# Repo-native Harness',
    '',
    '> Harness version：v9.9。',
    '> 最后更新：2099-01-02。',
    '',
    '## Policy Change Log',
    '',
    '| Version | Date | Change |',
    '| --- | --- | --- |',
    '| v9.9 | 2099-01-02 | Fixture policy. |',
    ''
  ].join('\n'))
  writeFile(path.join(root, 'docs/roadmap.md'), '# Roadmap\n')
  writeFile(path.join(root, 'docs/README.md'), '# Docs\n')

  const result = runHarness([
    '--root',
    root,
    '--json',
    '--write',
    '--date',
    '2026-07-09',
    '--slug',
    '../Harness Smoke!!'
  ])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const manifest = JSON.parse(result.stdout)
  assert.equal(manifest.harness.version, 'v9.9')
  assert.equal(manifest.write.enabled, true)
  assert.equal(manifest.release.date, '2026-07-09')
  assert.equal(manifest.release.slug, 'harness-smoke')
  assert.equal(
    manifest.write.path,
    'artifacts/releases/2026-07-09-harness-smoke/manifest.json'
  )

  const writtenManifestPath = path.join(root, manifest.write.path)
  assert.ok(fs.existsSync(writtenManifestPath), 'manifest should be written under local artifacts/releases')
  const writtenManifest = JSON.parse(fs.readFileSync(writtenManifestPath, 'utf8'))
  assert.equal(writtenManifest.harness.version, 'v9.9')
  assert.equal(writtenManifest.safety.productionWrites, false)
  assert.equal(writtenManifest.repo.git.status, 'not_git_repository')
})

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
  assert.equal(manifest.harness.version, 'v0.3')
  assert.equal(manifest.harness.source, 'docs/harness.md')
  assert.equal(manifest.safety.noNetwork, true)
  assert.equal(manifest.safety.repositoryRemoteSyncPreapproved, true)
  assert.equal(manifest.safety.repositoryRemoteSyncScope, 'configured_project_remote_only')
  assert.equal(manifest.safety.noDeploy, true)
  assert.equal(manifest.safety.noSsh, true)
  assert.equal(manifest.safety.productionWrites, false)
  assert.equal(manifest.evidencePacket.status, 'not_attached')
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
    'repositoryRemoteSync',
    'releaseRollback',
    'requirementChallenge'
  ].sort())
  assert.ok(manifest.gates.currentTruth.sources.some((source) => source.path === 'docs/roadmap.md' && source.exists))
  assert.ok(manifest.gates.engineeringHealth.hotspotFiles.some((file) => file.path === 'server/websim_payload.py' && file.exists))
  assert.equal(manifest.gates.repositoryRemoteSync.preapprovedForConfiguredProjectRemote, true)
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

test('project harness sanitizes release path segments before writing artifacts', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-path-'))
  writeFile(path.join(root, 'docs/harness.md'), [
    '# Repo-native Harness',
    '',
    '> Harness version：v9.9。',
    '> 最后更新：2099-01-02。',
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
    '../../../outside',
    '--slug',
    '../Harness Smoke!!'
  ])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const manifest = JSON.parse(result.stdout)
  assert.equal(manifest.release.date, 'outside')
  assert.equal(manifest.release.slug, 'harness-smoke')
  assert.equal(
    manifest.write.path,
    'artifacts/releases/outside-harness-smoke/manifest.json'
  )
  assert.ok(
    path.resolve(root, manifest.write.path).startsWith(path.resolve(root, 'artifacts/releases') + path.sep),
    'write path should remain under artifacts/releases'
  )
  assert.ok(fs.existsSync(path.join(root, manifest.write.path)))
})

test('project harness loads a local evidence packet without executing it', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-evidence-'))
  writeFile(path.join(root, 'docs/harness.md'), [
    '# Repo-native Harness',
    '',
    '> Harness version：v9.9。',
    '> 最后更新：2099-01-02。',
    ''
  ].join('\n'))
  writeFile(path.join(root, 'docs/roadmap.md'), '# Roadmap\n')
  writeFile(path.join(root, 'docs/README.md'), '# Docs\n')
  writeFile(path.join(root, 'artifacts/releases/sample/evidence.json'), JSON.stringify({
    status: 'local_verified',
    highestEvidenceLevel: 'local_verified',
    scope: ['harness'],
    verification: [
      {
        command: 'node --test tests/project-harness.test.js',
        status: 'pass'
      }
    ],
    risks: [],
    rollback: ['code_rollback'],
    summary: 'Harness evidence packet fixture.'
  }, null, 2))

  const result = runHarness([
    '--root',
    root,
    '--json',
    '--evidence-file',
    'artifacts/releases/sample/evidence.json'
  ])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const manifest = JSON.parse(result.stdout)
  assert.equal(manifest.evidencePacket.status, 'ready')
  assert.equal(manifest.evidencePacket.path, 'artifacts/releases/sample/evidence.json')
  assert.equal(manifest.evidencePacket.declaredStatus, 'local_verified')
  assert.equal(manifest.evidencePacket.highestEvidenceLevel, 'local_verified')
  assert.deepEqual(manifest.evidencePacket.missingFields, [])
})

test('project harness refuses evidence packets outside the repository root', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-evidence-boundary-'))
  const result = runHarness([
    '--root',
    root,
    '--json',
    '--evidence-file',
    '../outside.json'
  ])

  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /Refusing evidence file outside repository root/)
})

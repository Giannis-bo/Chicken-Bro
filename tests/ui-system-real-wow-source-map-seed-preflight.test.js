const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const preflightScript = 'scripts/ui-system-real-wow-source-map-seed-preflight.js'
const seedDocPath = 'docs/design/2026-07-07-wow-ui-system-real-wow-source-map-seed.md'
const manifestPath = 'artifacts/ui-system-rebuild/20260707-real-wow-source-map-seed/manifest.json'
const readmePath = 'artifacts/ui-system-rebuild/20260707-real-wow-source-map-seed/README.md'

function runPreflight(args = []) {
  return spawnSync(process.execPath, [preflightScript, ...args], {
    encoding: 'utf8'
  })
}

function read(filePath) {
  return fs.readFileSync(filePath, 'utf8')
}

function readJson(filePath) {
  return JSON.parse(read(filePath))
}

function writeCandidate(mutator) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-real-source-map-seed-'))
  const candidatePath = path.join(directory, 'seed.json')
  const manifest = readJson(manifestPath)
  fs.writeFileSync(candidatePath, JSON.stringify(mutator(manifest), null, 2))
  return candidatePath
}

test('real WoW source-map seed preflight accepts the current seed artifact', () => {
  const result = runPreflight(['--require-seed', '--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'real_wow_source_map_seed_ready')
  assert.equal(report.seedReady, true)
  assert.equal(report.runtimeSourceMapReady, false)
  assert.equal(report.sourceEntryCount, 10)
  assert.equal(report.contractAssertionCount, 5)
  assert.deepEqual(report.missingRequirements, [])
  assert.ok(report.coveredEntityTypes.includes('hero'))
  assert.ok(report.coveredEntityTypes.includes('affix'))
  assert.ok(report.coveredSurfaces.includes('news_list_detail'))
  assert.ok(report.coveredSurfaces.includes('profile_templates'))
})

test('real WoW source-map seed preflight rejects generated or promoted object sources', () => {
  const candidatePath = writeCandidate((manifest) => {
    manifest.runtimeVerified = true
    manifest.sourceEntries[0].sourceClass = 'imagegen'
    manifest.sourceEntries[0].owner = 'MaterialImage'
    manifest.sourceEntries[0].generatedByImagegen = true
    manifest.sourceEntries[0].containsGeneratedObject = true
    manifest.sourceEntries[0].assetPath = 'assets/generated/fake-class-icon.png'
    return manifest
  })
  const result = runPreflight(['--seed-file', candidatePath, '--require-seed', '--json'])

  assert.equal(result.status, 17)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'real_wow_source_map_seed_invalid')
  assert.equal(report.seedReady, false)
  assert.ok(report.missingRequirements.includes('runtimeVerified_false'))
  assert.ok(report.missingRequirements.includes('sourceEntries[0].sourceClass_allowed'))
  assert.ok(report.missingRequirements.includes('sourceEntries[0].sourceClass_not_forbidden'))
  assert.ok(report.missingRequirements.includes('sourceEntries[0].owner_GameObjectIcon'))
  assert.ok(report.missingRequirements.includes('sourceEntries[0].generatedByImagegen_false'))
  assert.ok(report.missingRequirements.includes('sourceEntries[0].containsGeneratedObject_false'))
  assert.ok(report.missingRequirements.includes('sourceEntries[0].seed_must_not_bind_runtime_assetPath'))
})

test('real WoW source-map seed preflight rejects missing entity and surface coverage', () => {
  const candidatePath = writeCandidate((manifest) => {
    manifest.sourceEntries = manifest.sourceEntries.filter((entry) => entry.entityType !== 'affix')
    manifest.sourceEntries.forEach((entry) => {
      entry.allowedSurfaces = entry.allowedSurfaces.filter((surface) => surface !== 'news_list_detail')
    })
    return manifest
  })
  const result = runPreflight(['--seed-file', candidatePath, '--require-seed', '--json'])

  assert.equal(result.status, 17)

  const report = JSON.parse(result.stdout)
  assert.ok(report.missingRequirements.includes('entityType:affix'))
  assert.ok(report.missingRequirements.includes('surface:news_list_detail'))
})

test('real WoW source-map seed docs remain non-runtime and non-promoting', () => {
  const source = read(seedDocPath)
  const manifest = readJson(manifestPath)
  const readme = read(readmePath)

  assert.match(source, /^Status: `real_wow_source_map_seed_ready`$/m)
  assert.match(source, /not a runtime source map/)
  assert.match(source, /do not draw spec icons with imagegen/)
  assert.match(source, /This seed can only prove `real_wow_source_map_seed_ready`/)

  assert.equal(manifest.status, 'real_wow_source_map_seed_ready')
  assert.equal(manifest.preflightScript, preflightScript)
  assert.equal(manifest.runtimeSourceMapReady, false)
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activeImplementationPermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.ok(manifest.sourceEntries.some((entry) => entry.entityType === 'item' && entry.payloadFields.includes('payload.equippedSet.*.gameAsset.iconUrl')))
  assert.ok(manifest.sourceEntries.every((entry) => entry.owner === 'GameObjectIcon'))
  assert.ok(manifest.nonPromotion.includes('not final_accepted'))

  assert.match(readme, /runtimeSourceMapReady: false/)
})

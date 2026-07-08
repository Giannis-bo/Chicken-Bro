const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const preflightScript = 'scripts/ui-system-material-asset-seed-preflight.js'
const seedDocPath = 'docs/design/2026-07-07-wow-ui-system-material-asset-seed.md'
const manifestPath = 'artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json'
const readmePath = 'artifacts/ui-system-rebuild/20260707-material-asset-seed/README.md'

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
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-material-asset-seed-'))
  const candidatePath = path.join(directory, 'seed.json')
  const manifest = readJson(manifestPath)
  fs.writeFileSync(candidatePath, JSON.stringify(mutator(manifest), null, 2))
  return candidatePath
}

test('material asset seed preflight accepts the current low-semantic seed artifact', () => {
  const result = runPreflight(['--require-seed', '--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'material_asset_seed_ready')
  assert.equal(report.materialAssetSeedReady, true)
  assert.equal(report.productionManifest, false)
  assert.equal(report.pageIntegration, false)
  assert.equal(report.runtimeVerified, false)
  assert.equal(report.finalAccepted, false)
  assert.equal(report.assetSeedCount, 9)
  assert.equal(report.quarantineCount, 5)
  assert.equal(report.contractAssertionCount, 3)
  assert.deepEqual(report.missingRequirements, [])
  assert.ok(report.coveredClasses.includes('state-base'))
  assert.ok(report.coveredClasses.includes('state-atomic'))
  assert.ok(report.coveredSurfaces.includes('news_home'))
  assert.ok(report.coveredSurfaces.includes('profile_templates'))
  assert.equal(report.packageBudget.maxKb, 512)
})

test('material asset seed preflight rejects promoted or fact-bearing generated material', () => {
  const candidatePath = writeCandidate((manifest) => {
    manifest.productionManifest = true
    manifest.runtimeVerified = true
    manifest.assetSeeds[0].containsFakeChrome = true
    manifest.assetSeeds[0].containsRealWowObject = true
    manifest.assetSeeds[0].productionUseAllowed = true
    manifest.assetSeeds[0].pageDirectUseAllowed = true
    manifest.assetSeeds[0].requiresRecutBeforeProduction = false
    return manifest
  })
  const result = runPreflight(['--seed-file', candidatePath, '--require-seed', '--json'])

  assert.equal(result.status, 19)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'material_asset_seed_invalid')
  assert.equal(report.materialAssetSeedReady, false)
  assert.ok(report.missingRequirements.includes('productionManifest_false'))
  assert.ok(report.missingRequirements.includes('runtimeVerified_false'))
  assert.ok(report.missingRequirements.includes('assetSeeds[0].containsFakeChrome_false'))
  assert.ok(report.missingRequirements.includes('assetSeeds[0].containsRealWowObject_false'))
  assert.ok(report.missingRequirements.includes('assetSeeds[0].productionUseAllowed_false'))
  assert.ok(report.missingRequirements.includes('assetSeeds[0].pageDirectUseAllowed_false'))
  assert.ok(report.missingRequirements.includes('assetSeeds[0].requiresRecutBeforeProduction_true'))
})

test('material asset seed preflight rejects missing class coverage and quarantine paths', () => {
  const candidatePath = writeCandidate((manifest) => {
    manifest.assetSeeds = manifest.assetSeeds.filter((asset) => asset.class !== 'state-atomic')
    manifest.assetSeeds[0].path = 'assets/generated/ui-v2-1-slices/20260703/news_tab_icon_all_pass36.png'
    manifest.assetSeeds[0].width = 1
    manifest.assetSeeds[0].height = 1
    return manifest
  })
  const result = runPreflight(['--seed-file', candidatePath, '--require-seed', '--json'])

  assert.equal(result.status, 19)

  const report = JSON.parse(result.stdout)
  assert.ok(report.missingRequirements.includes('class:state-atomic'))
  assert.ok(report.missingRequirements.includes('assetSeeds[0].path_not_quarantine_or_reference'))
  assert.ok(report.missingRequirements.includes('assetSeeds[0].declared_dimensions_match_file'))
})

test('material asset seed docs remain seed-only and non-promoting', () => {
  const source = read(seedDocPath)
  const manifest = readJson(manifestPath)
  const readme = read(readmePath)

  assert.match(source, /^Status: `material_asset_seed_ready`$/m)
  assert.match(source, /not a production manifest/)
  assert.match(source, /All `pageDirectUseAllowed` and `productionUseAllowed` flags are `false`/)
  assert.match(source, /This seed can only prove `material_asset_seed_ready`/)

  assert.equal(manifest.status, 'material_asset_seed_ready')
  assert.equal(manifest.preflightScript, preflightScript)
  assert.equal(manifest.materialAssetSeedReady, true)
  assert.equal(manifest.productionManifest, false)
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activeImplementationPermit, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.finalAccepted, false)
  assert.ok(manifest.assetSeeds.some((asset) => asset.class === 'state-atomic' && asset.owner === 'StatusVisual'))
  assert.ok(manifest.assetSeeds.every((asset) => asset.containsText === false))
  assert.ok(manifest.assetSeeds.every((asset) => asset.productionUseAllowed === false))
  assert.ok(manifest.nonPromotion.includes('not production_asset_manifest'))

  assert.match(readme, /productionManifest: false/)
  assert.match(readme, /assetSeedCount: 9/)
})

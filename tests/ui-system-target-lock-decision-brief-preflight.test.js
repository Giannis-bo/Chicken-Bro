const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const preflightScript = 'scripts/ui-system-target-lock-decision-brief-preflight.js'
const docPath = 'docs/design/2026-07-07-wow-ui-system-target-lock-decision-brief.md'
const manifestPath = 'artifacts/ui-system-rebuild/20260707-target-lock-decision-brief/manifest.json'
const readmePath = 'artifacts/ui-system-rebuild/20260707-target-lock-decision-brief/README.md'
const materialAssetSeedPath = 'artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json'

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

function tempFile(name, content) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-target-brief-'))
  const file = path.join(directory, name)
  fs.writeFileSync(file, content)
  return file
}

function tempJson(data) {
  return tempFile('manifest.json', JSON.stringify(data, null, 2))
}

test('target-lock decision brief preflight validates the compact user decision packet', () => {
  const result = runPreflight(['--require-ready', '--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'target_lock_decision_brief_ready')
  assert.equal(report.readyForUserDecision, true)
  assert.equal(report.targetLocked, false)
  assert.equal(report.activeImplementationPermit, false)
  assert.equal(report.pageIntegration, false)
  assert.equal(report.runtimeVerified, false)
  assert.equal(report.finalAccepted, false)
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.recommendedTargetName, 'A-Cockpit + B-Ledger + C-Captain')
  assert.equal(report.recommendedFirstSurface, 'news_list_detail')
  assert.equal(report.failedCheckCount, 0)
  assert.ok(report.checks.some((check) => check.id === 'brief_pattern:production_asset_manifest_preflight' && check.status === 'pass'))
  assert.ok(report.checks.some((check) => check.id === 'brief_pattern:real_wow_source_map_preflight' && check.status === 'pass'))
  assert.ok(report.checks.some((check) => check.id === 'material_seed_semantic_safety' && check.status === 'pass'))
  assert.ok(report.checks.some((check) => check.id === 'source_map_seed_no_imagegen_objects' && check.status === 'pass'))
})

test('target-lock decision brief preflight fails closed when the brief hides runtime gates', () => {
  const badBrief = tempFile('brief.md', [
    '# Bad Brief',
    '',
    'Status: `target_lock_decision_brief`',
    '',
    '## Recommended Target',
    '',
    'A-Cockpit + B-Ledger + C-Captain',
    '',
    '## Decision Options',
    '',
    'Confirm recommended target'
  ].join('\n'))

  const result = runPreflight([
    '--brief-file',
    badBrief,
    '--require-ready',
    '--json'
  ])

  assert.equal(result.status, 17)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'target_lock_decision_brief_invalid')
  assert.equal(report.readyForUserDecision, false)
  assert.ok(report.failedChecks.some((check) => check.id === 'brief_section:Production Asset Manifest Gate'))
  assert.ok(report.failedChecks.some((check) => check.id === 'brief_section:Real WoW Source Map Gate'))
  assert.ok(report.failedChecks.some((check) => check.id === 'brief_pattern:runtime_evidence'))
})

test('target-lock decision brief preflight fails closed for unsafe material seed', () => {
  const materialSeed = readJson(materialAssetSeedPath)
  materialSeed.productionManifest = true
  materialSeed.assetSeeds[0].containsRealWowObject = true
  materialSeed.assetSeeds[0].pageDirectUseAllowed = true
  const badMaterialSeed = tempJson(materialSeed)

  const result = runPreflight([
    '--material-asset-seed',
    badMaterialSeed,
    '--require-ready',
    '--json'
  ])

  assert.equal(result.status, 17)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'target_lock_decision_brief_invalid')
  assert.ok(report.failedChecks.some((check) => check.id === 'material_seed_not_production_manifest'))
  assert.ok(report.failedChecks.some((check) => check.id === 'material_seed_semantic_safety'))
})

test('target-lock decision brief artifact is non-promoting and complete enough for user choice', () => {
  const source = read(docPath)
  const manifest = readJson(manifestPath)
  const readme = read(readmePath)

  assert.match(source, /^Status: `target_lock_decision_brief`$/m)
  assert.match(source, /Recommended target: `A-Cockpit \+ B-Ledger \+ C-Captain`/)
  assert.match(source, /Recommended first active surface after target lock: `news_list_detail`/)
  assert.match(source, /Production Asset Manifest Gate/)
  assert.match(source, /Real WoW Source Map Gate/)
  assert.match(source, /Page Integration Gate/)
  assert.match(source, /Runtime Evidence Gate/)
  assert.match(source, /This brief proves only `target_lock_decision_brief`/)

  assert.equal(manifest.status, 'target_lock_decision_brief')
  assert.equal(manifest.preflightScript, preflightScript)
  assert.equal(manifest.recommendedTargetName, 'A-Cockpit + B-Ledger + C-Captain')
  assert.equal(manifest.recommendedFirstSurface, 'news_list_detail')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activeImplementationPermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.ok(manifest.requiredRuntimeGates.includes('production_asset_manifest_preflight'))
  assert.ok(manifest.requiredRuntimeGates.includes('real_wow_source_map_preflight'))
  assert.ok(manifest.checkedEvidence.includes(materialAssetSeedPath))
  assert.ok(manifest.nonPromotion.includes('not final_accepted'))

  assert.match(readme, /targetLocked: false/)
  assert.match(readme, /not a target lock/)
})

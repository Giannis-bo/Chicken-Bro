const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const preflightScript = 'scripts/ui-system-first-surface-activation-readiness-preflight.js'
const docPath = 'docs/design/2026-07-07-wow-ui-system-first-surface-activation-readiness-preflight.md'
const manifestPath = 'artifacts/ui-system-rebuild/20260707-first-surface-activation-readiness-preflight/manifest.json'
const readmePath = 'artifacts/ui-system-rebuild/20260707-first-surface-activation-readiness-preflight/README.md'
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

function writeCandidate(fileName, sourceObject) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-first-surface-readiness-'))
  const filePath = path.join(directory, fileName)
  fs.writeFileSync(filePath, JSON.stringify(sourceObject, null, 2))
  return filePath
}

test('first surface activation readiness preflight passes for current news_list_detail packet', () => {
  const result = runPreflight(['--require-ready', '--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'first_surface_activation_readiness_ready')
  assert.equal(report.surface, 'news_list_detail')
  assert.equal(report.readyForTargetLockActivation, true)
  assert.equal(report.targetLocked, false)
  assert.equal(report.activeImplementationPermit, false)
  assert.equal(report.pageIntegration, false)
  assert.equal(report.runtimeVerified, false)
  assert.equal(report.finalAccepted, false)
  assert.equal(report.checkedPathCount, 16)
  assert.equal(report.failingCheckCount, 0)
  assert.ok(report.requiredOwners.includes('ArticleReader'))
  assert.ok(report.requiredTemplateScenes.includes('news_detail_copy_source'))
  assert.equal(report.nextLegalTransition.includes('target-lock confirmation'), true)
})

test('first surface activation readiness preflight fails closed for unsafe material seed', () => {
  const materialSeed = readJson(materialAssetSeedPath)
  materialSeed.productionManifest = true
  materialSeed.assetSeeds[0].containsFakeChrome = true
  materialSeed.assetSeeds[0].pageDirectUseAllowed = true
  const candidatePath = writeCandidate('material-seed.json', materialSeed)

  const result = runPreflight([
    '--material-asset-seed',
    candidatePath,
    '--require-ready',
    '--json'
  ])

  assert.equal(result.status, 18)

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'first_surface_activation_readiness_incomplete')
  assert.equal(report.readyForTargetLockActivation, false)
  assert.ok(report.failingChecks.some((check) => check.id === 'material_asset_seed_not_production'))
  assert.ok(report.failingChecks.some((check) => check.id === 'material_asset_seed_semantic_safety'))
})

test('first surface activation readiness preflight fails on component overflow and promotion', () => {
  const componentManifest = readJson('artifacts/ui-system-rebuild/20260707-news-list-detail-component-precheck/manifest.json')
  componentManifest.runtimeVerified = true
  componentManifest.measurements[0].document.horizontalOverflow = 12
  const candidatePath = writeCandidate('component-precheck.json', componentManifest)

  const result = runPreflight([
    '--component-precheck',
    candidatePath,
    '--require-ready',
    '--json'
  ])

  assert.equal(result.status, 18)

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'first_surface_activation_readiness_incomplete')
  assert.equal(report.readyForTargetLockActivation, false)
  assert.ok(report.failingChecks.some((check) => check.id === 'componentPrecheck_non_promotion' || check.id === 'component_precheck_non_promotion'))
  assert.ok(report.failingChecks.some((check) => check.id === 'component_precheck_no_horizontal_overflow'))
})

test('first surface activation readiness docs remain non-promoting', () => {
  const source = read(docPath)
  const manifest = readJson(manifestPath)
  const readme = read(readmePath)

  assert.match(source, /^Status: `first_surface_activation_readiness_ready`$/m)
  assert.match(source, /not `target_locked`/)
  assert.match(source, /not an active implementation permit/)
  assert.match(source, /Design read: WOW 小程序 redesign-overhaul/)
  assert.match(source, /material asset seed is ready/)
  assert.match(source, /active-permit template inherits decision brief and two-part goal boundaries/)
  assert.match(source, /node scripts\/ui-system-first-surface-activation-readiness-preflight\.js --require-ready --json/)

  assert.equal(manifest.status, 'first_surface_activation_readiness_ready')
  assert.equal(manifest.preflightScript, preflightScript)
  assert.equal(manifest.readyForTargetLockActivation, true)
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activeImplementationPermit, false)
  assert.equal(manifest.pageIntegration, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.equal(manifest.checkedPathCount, 16)
  assert.equal(manifest.expectedMaterialAssetSeedStatus, 'material_asset_seed_ready')
  assert.equal(manifest.expectedDecisionBriefStatus, 'target_lock_decision_brief')
  assert.equal(manifest.expectedTwoPartGoalSyncStatus, 'two_part_goal_sync')
  assert.ok(manifest.checkedEvidence.includes(materialAssetSeedPath))
  assert.ok(manifest.checkedEvidence.includes('artifacts/ui-system-rebuild/20260707-real-wow-source-map-seed/manifest.json'))
  assert.ok(manifest.nonPromotion.includes('not final_accepted'))

  assert.match(readme, /activeImplementationPermit: false/)
  assert.match(readme, /Material asset seed: `material_asset_seed_ready`/)
  assert.match(readme, /Decision brief: `target_lock_decision_brief`/)
  assert.match(readme, /Two-part goal sync: `two_part_goal_sync`/)
})

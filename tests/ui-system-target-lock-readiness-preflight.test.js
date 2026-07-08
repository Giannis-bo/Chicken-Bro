const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const preflightScript = 'scripts/ui-system-target-lock-readiness-preflight.js'
const docPath = 'docs/design/2026-07-07-wow-ui-system-target-lock-readiness-preflight.md'
const manifestPath = 'artifacts/ui-system-rebuild/20260707-target-lock-readiness-preflight/manifest.json'
const readmePath = 'artifacts/ui-system-rebuild/20260707-target-lock-readiness-preflight/README.md'
const materialAssetSeedPath = 'artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json'
const decisionBriefPath = 'artifacts/ui-system-rebuild/20260707-target-lock-decision-brief/manifest.json'

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

function tempJson(data) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-target-readiness-'))
  const file = path.join(directory, 'manifest.json')
  fs.writeFileSync(file, JSON.stringify(data, null, 2))
  return file
}

test('target-lock readiness preflight validates the current decision packet is ready for user choice', () => {
  const result = runPreflight(['--require-ready', '--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'target_lock_readiness_ready')
  assert.equal(report.readyForUserDecision, true)
  assert.equal(report.targetLocked, false)
  assert.equal(report.activePermit, false)
  assert.equal(report.pageIntegration, false)
  assert.equal(report.runtimeVerified, false)
  assert.equal(report.finalAccepted, false)
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.recommendedTargetName, 'A-Cockpit + B-Ledger + C-Captain')
  assert.equal(report.failedCheckCount, 0)
  assert.ok(report.checks.some((check) => check.id === 'material_seed_status' && check.status === 'pass'))
  assert.ok(report.checks.some((check) => check.id === 'material_seed_semantic_safety' && check.status === 'pass'))
  assert.ok(report.checks.some((check) => check.id === 'material_seed_package_budget' && check.status === 'pass'))
  assert.ok(report.checks.some((check) => check.id === 'decision_brief_runtime_gates' && check.status === 'pass'))
  assert.ok(report.checks.some((check) => check.id === 'decision_brief_first_surface' && check.status === 'pass'))
  assert.ok(report.requiredCoreSurfaces.includes('current_spec_workbench'))
  assert.ok(report.requiredOwners.includes('StatusVisual'))
  assert.equal(report.nextRequiredEvidence, 'explicit user target-lock confirmation or written modification')
})

test('target-lock readiness preflight fails closed when proposal manifest promotes target lock', () => {
  const badProposal = tempJson({
    status: 'target_lock_proposal',
    targetLocked: true,
    hybrid: {
      name: 'A-Cockpit + B-Ledger + C-Captain'
    },
    foundationOwners: [],
    assetBoundary: {
      productionMaterialClasses: []
    },
    candidateContactSheet: 'missing.png'
  })

  const result = runPreflight([
    '--proposal-manifest',
    badProposal,
    '--require-ready',
    '--json'
  ])

  assert.equal(result.status, 14)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'target_lock_readiness_invalid')
  assert.equal(report.readyForUserDecision, false)
  assert.ok(report.failedChecks.some((check) => check.id === 'proposal_non_promotion'))
  assert.ok(report.failedChecks.some((check) => check.id === 'proposal_owners_cover_foundation'))
  assert.equal(report.nextRequiredEvidence, 'repair target-lock readiness evidence before asking for decision')
})

test('target-lock readiness preflight fails closed for unsafe material asset seed', () => {
  const materialSeed = readJson(materialAssetSeedPath)
  materialSeed.productionManifest = true
  materialSeed.assetSeeds[0].containsFakeChrome = true
  materialSeed.assetSeeds[0].productionUseAllowed = true
  const badMaterialSeed = tempJson(materialSeed)

  const result = runPreflight([
    '--material-asset-seed',
    badMaterialSeed,
    '--require-ready',
    '--json'
  ])

  assert.equal(result.status, 14)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'target_lock_readiness_invalid')
  assert.equal(report.readyForUserDecision, false)
  assert.ok(report.failedChecks.some((check) => check.id === 'material_seed_not_production_manifest'))
  assert.ok(report.failedChecks.some((check) => check.id === 'material_seed_semantic_safety'))
})

test('target-lock readiness preflight fails closed when decision brief omits runtime gates', () => {
  const decisionBrief = readJson(decisionBriefPath)
  decisionBrief.requiredRuntimeGates = ['page_adoption_preflight']
  const badDecisionBrief = tempJson(decisionBrief)

  const result = runPreflight([
    '--decision-brief',
    badDecisionBrief,
    '--require-ready',
    '--json'
  ])

  assert.equal(result.status, 14)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'target_lock_readiness_invalid')
  assert.equal(report.readyForUserDecision, false)
  assert.ok(report.failedChecks.some((check) => check.id === 'decision_brief_runtime_gates'))
})

test('target-lock readiness artifact records non-promoting preflight status', () => {
  const source = read(docPath)
  const manifest = readJson(manifestPath)
  const readme = read(readmePath)

  assert.match(source, /^Status: `target_lock_readiness_preflight`$/m)
  assert.match(source, /target_lock_readiness_ready/)
  assert.match(source, /not `target_locked`/)
  assert.match(source, /Material asset seed safety/)
  assert.match(source, /explicit user target-lock confirmation or written modification/)

  assert.equal(manifest.status, 'target_lock_readiness_preflight')
  assert.equal(manifest.preflightScript, preflightScript)
  assert.equal(manifest.expectedReadyStatus, 'target_lock_readiness_ready')
  assert.equal(manifest.expectedRequireReadyExitCode, 0)
  assert.equal(manifest.expectedInvalidExitCode, 14)
  assert.equal(manifest.expectedMaterialAssetSeedStatus, 'material_asset_seed_ready')
  assert.equal(manifest.expectedMaterialAssetSeedProductionManifest, false)
  assert.ok(manifest.checkedEvidence.includes(materialAssetSeedPath))
  assert.ok(manifest.checkedEvidence.includes(decisionBriefPath))
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.runtimeVerified, false)
  assert.ok(manifest.requiredCoreSurfaces.includes('profile_templates'))
  assert.ok(manifest.requiredOwners.includes('ChatShell'))
  assert.ok(manifest.nonPromotion.includes('not final_accepted'))

  assert.match(readme, /targetLocked: false/)
  assert.match(readme, /Material asset seed: `material_asset_seed_ready`/)
})

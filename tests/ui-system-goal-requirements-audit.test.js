const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')

const auditScript = 'scripts/ui-system-goal-requirements-audit.js'
const auditDocPath = 'docs/design/2026-07-07-wow-ui-system-goal-requirements-audit.md'
const manifestPath = 'artifacts/ui-system-rebuild/20260707-goal-requirements-audit/manifest.json'
const readmePath = 'artifacts/ui-system-rebuild/20260707-goal-requirements-audit/README.md'

function runAudit(args = []) {
  return spawnSync(process.execPath, [auditScript, ...args], {
    encoding: 'utf8'
  })
}

function read(filePath) {
  return fs.readFileSync(filePath, 'utf8')
}

function readJson(filePath) {
  return JSON.parse(read(filePath))
}

test('goal requirements audit blocks completion while runtime evidence and permits are missing', () => {
  const result = runAudit(['--require-complete', '--json'])

  assert.equal(result.status, 7)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'ui_system_goal_requirements_incomplete')
  assert.equal(report.goalComplete, false)
  assert.equal(report.completionClaimAllowed, false)
  assert.equal(report.runtimeVerifiedAllowed, false)
  assert.equal(report.finalAcceptedAllowed, false)
  assert.equal(report.implementationGateStatus, 'ui_system_implementation_gate_blocked')
  assert.equal(report.implementationAllowed, false)
  assert.ok(report.requiredSurfaces.includes('chickenbro'))
  assert.ok(report.requiredSurfaces.includes('profile_templates'))
  assert.ok(report.missingRequirements.includes('target_locked_design'))
  assert.ok(report.missingRequirements.includes('runtime_screenshots'))
  assert.ok(report.blockedRequirements.includes('page_integration'))
  assert.ok(report.weakEvidenceRequirements.includes('component_owner_system'))
  assert.ok(report.weakEvidenceRequirements.includes('imagegen_asset_boundary'))
  assert.ok(report.weakEvidenceRequirements.includes('real_wow_source_boundary'))
  assert.ok(report.nextRequiredEvidence.includes('explicit target lock or written modification'))
  assert.ok(report.nextRequiredEvidence.includes('production asset manifest derived from the material asset seed'))
  assert.ok(report.nextRequiredEvidence.includes('runtime real WoW source map derived from the source-map seed'))
})

test('goal requirements audit document and manifest cannot promote the rebuild', () => {
  const source = read(auditDocPath)
  const manifest = readJson(manifestPath)
  const readme = read(readmePath)

  assert.match(source, /^Status: `ui_system_goal_requirements_incomplete`$/m)
  assert.match(source, /goalComplete=false/)
  assert.match(source, /runtimeVerifiedAllowed=false/)
  assert.match(source, /finalAcceptedAllowed=false/)
  assert.match(source, /docs\/design\/2026-07-07-wow-ui-system-target-locked-decision\.md/)
  assert.match(source, /docs\/plans\/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit\.md/)
  assert.match(source, /real mini-program screenshots/)
  assert.match(source, /DevTools action ledger/)
  assert.match(source, /Core Page Freeze Preflight/)
  assert.match(source, /ui-system-core-page-freeze-preflight\.js --require-frozen/)
  assert.match(source, /Owner Registry Preflight/)
  assert.match(source, /ui-system-owner-registry-preflight\.js --require-ready/)
  assert.match(source, /Material Asset Seed/)
  assert.match(source, /ui-system-material-asset-seed-preflight\.js --require-seed/)
  assert.match(source, /Real WoW Source Map Seed/)
  assert.match(source, /ui-system-real-wow-source-map-seed\.js --require-seed|ui-system-real-wow-source-map-seed-preflight\.js --require-seed/)
  assert.match(source, /First Surface Activation Readiness Preflight/)
  assert.match(source, /ui-system-first-surface-activation-readiness-preflight\.js --require-ready/)

  assert.equal(manifest.status, 'ui_system_goal_requirements_incomplete')
  assert.equal(manifest.auditScript, auditScript)
  assert.equal(manifest.goalComplete, false)
  assert.equal(manifest.expectedRequireCompleteExitCode, 7)
  assert.ok(manifest.requiredSurfaces.includes('current_spec_workbench'))
  assert.ok(manifest.missingCompletionEvidence.includes('route smoke execution manifest'))
  assert.ok(manifest.missingCompletionEvidence.includes('passing core page freeze preflight'))
  assert.ok(manifest.missingCompletionEvidence.includes('production asset manifest derived from material asset seed'))
  assert.ok(manifest.missingCompletionEvidence.includes('runtime real WoW source map derived from source-map seed'))
  assert.equal(manifest.linkedCorePageFreezePreflight.script, 'scripts/ui-system-core-page-freeze-preflight.js')
  assert.equal(manifest.linkedCorePageFreezePreflight.expectedRequireFrozenExitCode, 16)
  assert.equal(manifest.linkedCorePageFreezePreflight.currentFrozenCoreFileCount, 44)
  assert.equal(manifest.linkedOwnerRegistryPreflight.script, 'scripts/ui-system-owner-registry-preflight.js')
  assert.equal(manifest.linkedOwnerRegistryPreflight.expectedRequireReadyExitCode, 0)
  assert.equal(manifest.linkedOwnerRegistryPreflight.ownerCount, 26)
  assert.equal(manifest.linkedOwnerRegistryPreflight.surfaceCount, 10)
  assert.equal(manifest.linkedMaterialAssetSeedPreflight.script, 'scripts/ui-system-material-asset-seed-preflight.js')
  assert.equal(manifest.linkedMaterialAssetSeedPreflight.expectedRequireSeedExitCode, 0)
  assert.equal(manifest.linkedMaterialAssetSeedPreflight.assetSeedCount, 9)
  assert.equal(manifest.linkedMaterialAssetSeedPreflight.requiredClassCount, 7)
  assert.equal(manifest.linkedMaterialAssetSeedPreflight.requiredSurfaceCount, 10)
  assert.equal(manifest.linkedMaterialAssetSeedPreflight.packageBudgetKb.current, 444.84)
  assert.equal(manifest.linkedRealWowSourceMapSeedPreflight.script, 'scripts/ui-system-real-wow-source-map-seed-preflight.js')
  assert.equal(manifest.linkedRealWowSourceMapSeedPreflight.expectedRequireSeedExitCode, 0)
  assert.equal(manifest.linkedRealWowSourceMapSeedPreflight.sourceEntryCount, 10)
  assert.equal(manifest.linkedFirstSurfaceActivationReadinessPreflight.script, 'scripts/ui-system-first-surface-activation-readiness-preflight.js')
  assert.equal(manifest.linkedFirstSurfaceActivationReadinessPreflight.surface, 'news_list_detail')
  assert.equal(manifest.linkedFirstSurfaceActivationReadinessPreflight.expectedRequireReadyExitCode, 0)
  assert.equal(manifest.linkedFirstSurfaceActivationReadinessPreflight.failingCheckCount, 0)
  assert.ok(manifest.linkedFirstSurfaceActivationReadinessPreflight.requiredRouteSmokeSceneIds.includes('news_detail_copy_source'))
  assert.match(manifest.linkedFirstSurfaceActivationReadinessPreflight.nonPromotionBoundary, /not target_locked/)
  assert.equal(manifest.linkedImplementationGatePreflight.script, 'scripts/ui-system-implementation-gate.js')
  assert.equal(manifest.linkedImplementationGatePreflight.expectedRequireImplementationExitCode, 6)
  assert.ok(manifest.linkedImplementationGatePreflight.passingChecks.includes('first_surface_readiness'))
  assert.ok(manifest.linkedImplementationGatePreflight.blockingChecks.includes('active_permit'))
  assert.ok(manifest.nonPromotion.includes('not final_accepted'))

  assert.match(readme, /goalComplete: false/)
  assert.match(readme, /firstSurfaceActivationReadiness/)
  assert.match(readme, /materialAssetSeed/)
})

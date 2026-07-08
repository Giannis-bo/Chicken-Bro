const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const preflightScript = 'scripts/ui-system-target-lock-decision-preflight.js'
const templatePath = 'docs/design/2026-07-07-wow-ui-system-target-locked-decision-template.md'
const manifestPath = 'artifacts/ui-system-rebuild/20260707-target-lock-decision-template/manifest.json'
const readmePath = 'artifacts/ui-system-rebuild/20260707-target-lock-decision-template/README.md'
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

function makeCandidate(source) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-target-lock-'))
  const file = path.join(directory, 'decision.md')
  fs.writeFileSync(file, source)
  return file
}

function makeJsonCandidate(sourceObject) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-target-lock-'))
  const file = path.join(directory, 'candidate.json')
  fs.writeFileSync(file, JSON.stringify(sourceObject, null, 2))
  return file
}

const validCandidate = `# WOW UI System Target Locked Decision

Status: \`target_locked\`

## User Decision Source

User confirmed: 确认 A-Cockpit + B-Ledger + C-Captain 为 target lock

## Confirmed Target

A-Cockpit + B-Ledger + C-Captain

## Decision Brief Boundary

The decision is based on artifacts/ui-system-rebuild/20260707-target-lock-decision-brief/manifest.json with status target_lock_decision_brief_ready. The brief keeps targetLocked=false, activeImplementationPermit=false, pageIntegration=false, runtimeVerified=false and finalAccepted=false before this record. The brief also requires production_asset_manifest_preflight, real_wow_source_map_preflight, page_adoption_preflight, visual_acceptance_preflight, route_smoke_execution_preflight and devtools_action_ledger_preflight before runtime acceptance.

## First-Class Surfaces

- news_home
- news_list_detail
- builds_tab
- current_spec_workbench
- talent_simulator
- gear_detail
- simc
- chickenbro
- tasks
- profile_templates

## Foundation Owner Rules

Use shared owner components.

## Surface Owner Rules

Pages compose owners and bind route/data only.

## Asset Production And Quarantine Rules

Imagegen assets remain low-semantic material unless manifest-approved.

## Material Asset Seed Boundary

The decision references artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json with status material_asset_seed_ready. This seed is not a production manifest: productionManifest=false, pageDirectUseAllowed=false and productionUseAllowed=false. Production assets still require a later production asset manifest after active permit.

## Real WoW Object Source Rules

Real WoW objects cannot come from imagegen.

## Route Smoke Rules

Route smoke covers all scenes before runtime promotion.

## Implementation Permit Rule

Exactly one draft permit may become active after this decision.

## Non-Promotion Boundary

This is target lock, not implementation, not runtime_verified, and not final_accepted. Runtime verification requires real WeChat mini-program screenshots, component crops, overlay/red-zone, scorecard, route smoke and DevTools action ledger.

## Next Allowed Action

Create exactly one active implementation permit.
`

test('target lock decision preflight reports the real decision record as missing by default', () => {
  const result = runPreflight(['--require-decision', '--json'])

  assert.equal(result.status, 4)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'target_lock_decision_missing')
  assert.equal(report.candidatePath, 'docs/design/2026-07-07-wow-ui-system-target-locked-decision.md')
  assert.equal(report.decisionRecordExists, false)
  assert.equal(report.targetLocked, false)
  assert.equal(report.validDecisionRecord, false)
  assert.ok(report.missingRequirements.includes('decision_record_file'))
  assert.ok(report.requiredSurfaces.includes('chickenbro'))
  assert.equal(report.decisionBriefPath, decisionBriefPath)
  assert.equal(report.materialSeedPath, materialAssetSeedPath)
})

test('target lock decision preflight validates a complete candidate record', () => {
  const candidate = makeCandidate(validCandidate)
  const result = runPreflight(['--candidate-file', candidate, '--require-decision', '--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'target_lock_decision_ready')
  assert.equal(report.decisionRecordExists, true)
  assert.equal(report.targetLocked, true)
  assert.equal(report.validDecisionRecord, true)
  assert.equal(report.decisionBriefPath, decisionBriefPath)
  assert.equal(report.materialSeedPath, materialAssetSeedPath)
  assert.deepEqual(report.missingRequirements, [])
  assert.equal(report.nextRequiredEvidence, 'exactly one active implementation permit')
})

test('target lock decision preflight fails closed for unsafe or incomplete decision brief', () => {
  const badBrief = readJson(decisionBriefPath)
  badBrief.requiredRuntimeGates = ['page_adoption_preflight']
  badBrief.runtimeVerified = true
  const badBriefPath = makeJsonCandidate(badBrief)
  const candidate = makeCandidate(validCandidate)

  const result = runPreflight([
    '--candidate-file',
    candidate,
    '--decision-brief',
    badBriefPath,
    '--require-decision',
    '--json'
  ])

  assert.equal(result.status, 4)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'target_lock_decision_invalid')
  assert.equal(report.targetLocked, false)
  assert.equal(report.validDecisionRecord, false)
  assert.ok(report.missingRequirements.includes('decision_brief_not_runtime_verified'))
  assert.ok(report.missingRequirements.includes('decision_brief_runtime_gate:production_asset_manifest_preflight'))
  assert.ok(report.missingRequirements.includes('decision_brief_runtime_gate:real_wow_source_map_preflight'))
})

test('target lock decision preflight fails closed for unsafe material seed', () => {
  const badSeed = readJson(materialAssetSeedPath)
  badSeed.productionManifest = true
  badSeed.assetSeeds[0].containsBusinessConclusion = true
  badSeed.assetSeeds[0].productionUseAllowed = true
  const badSeedPath = makeJsonCandidate(badSeed)
  const candidate = makeCandidate(validCandidate)

  const result = runPreflight([
    '--candidate-file',
    candidate,
    '--material-asset-seed',
    badSeedPath,
    '--require-decision',
    '--json'
  ])

  assert.equal(result.status, 4)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'target_lock_decision_invalid')
  assert.equal(report.targetLocked, false)
  assert.equal(report.validDecisionRecord, false)
  assert.ok(report.missingRequirements.includes('material_seed_not_production'))
  assert.ok(report.missingRequirements.some((item) => item.startsWith('unsafe_material_seed:')))
})

test('target lock template remains template-only and cannot promote implementation', () => {
  const source = read(templatePath)
  const manifest = readJson(manifestPath)
  const readme = read(readmePath)

  assert.match(source, /^Status: `target_locked_template_only`$/m)
  assert.match(source, /Do not rename this file into the real decision record automatically/)
  assert.match(source, /node scripts\/ui-system-target-lock-decision-preflight\.js --require-decision --json/)
  assert.match(source, /Decision Brief Boundary/)
  assert.match(source, /target_lock_decision_brief/)
  assert.match(source, /Material Asset Seed Boundary/)
  assert.match(source, /material_asset_seed_ready/)
  assert.match(source, /news_home/)
  assert.match(source, /profile_templates/)

  assert.equal(manifest.status, 'target_lock_decision_template_and_preflight')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.preflightScript, preflightScript)
  assert.equal(manifest.requiredDecisionBriefPath, decisionBriefPath)
  assert.equal(manifest.expectedDecisionBriefStatus, 'target_lock_decision_brief')
  assert.equal(manifest.expectedMaterialAssetSeedStatus, 'material_asset_seed_ready')
  assert.equal(manifest.expectedMaterialSeedProductionManifest, false)
  assert.equal(manifest.requiredMaterialAssetSeedPath, materialAssetSeedPath)
  assert.ok(manifest.requiredSurfaces.includes('current_spec_workbench'))
  assert.ok(manifest.requiredSections.includes('Material Asset Seed Boundary'))
  assert.ok(manifest.requiredSections.includes('Decision Brief Boundary'))
  assert.ok(manifest.requiredSections.includes('User Decision Source'))
  assert.ok(manifest.requiredRuntimeGates.includes('production_asset_manifest_preflight'))
  assert.ok(manifest.requiredRuntimeGates.includes('real_wow_source_map_preflight'))
  assert.ok(manifest.nonPromotion.includes('not runtime_verified'))

  assert.match(readme, /targetLocked: false/)
  assert.match(readme, /decisionBrief: `target_lock_decision_brief`/)
  assert.match(readme, /materialAssetSeed: `material_asset_seed_ready`/)
})

const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const preflightScript = 'scripts/ui-system-active-permit-preflight.js'
const templatePath = 'docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit-template.md'
const manifestPath = 'artifacts/ui-system-rebuild/20260707-news-list-detail-active-permit-template/manifest.json'
const readmePath = 'artifacts/ui-system-rebuild/20260707-news-list-detail-active-permit-template/README.md'
const materialAssetSeedPath = 'artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json'
const decisionBriefPath = 'artifacts/ui-system-rebuild/20260707-target-lock-decision-brief/manifest.json'
const twoPartGoalSyncPath = 'artifacts/ui-system-rebuild/20260707-two-part-goal-sync/manifest.json'

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
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-active-permit-'))
  const file = path.join(directory, 'permit.md')
  fs.writeFileSync(file, source)
  return file
}

function makeJsonCandidate(sourceObject) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-active-permit-'))
  const file = path.join(directory, 'candidate.json')
  fs.writeFileSync(file, JSON.stringify(sourceObject, null, 2))
  return file
}

const validTargetDecisionCandidate = `# WOW UI System Target Locked Decision

Status: \`target_locked\`

## Material Asset Seed Boundary

The decision references artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json with status material_asset_seed_ready.

## Decision Brief Boundary

The decision references artifacts/ui-system-rebuild/20260707-target-lock-decision-brief/manifest.json with status target_lock_decision_brief_ready.

## Runtime Gates

- production_asset_manifest_preflight
- real_wow_source_map_preflight
- page_adoption_preflight
- visual_acceptance_preflight
- route_smoke_execution_preflight
- devtools_action_ledger_preflight
`

const validPermitCandidate = `# News List Detail Active Implementation Permit

Status: \`active_implementation_permit\`
Surface: \`news_list_detail\`

## Two-Part Goal Boundary

Uses artifacts/ui-system-rebuild/20260707-two-part-goal-sync/manifest.json with status two_part_goal_sync. This inherits the rule that UI system rebuild comes before single-surface implementation and that page integration stays blocked without active permit evidence.

## Target Lock Decision

Uses docs/design/2026-07-07-wow-ui-system-target-locked-decision.md.

## Decision Brief Boundary

Uses artifacts/ui-system-rebuild/20260707-target-lock-decision-brief/manifest.json with status target_lock_decision_brief_ready.

## Allowed Files

- pages/news/list.wxml
- pages/news/list.wxss
- pages/news/list.js
- pages/news/list.json
- pages/news/detail.wxml
- pages/news/detail.wxss
- pages/news/detail.js
- pages/news/detail.json
- pages/news/news-api.js
- components/article-list-board/*
- components/article-reader/*

## Forbidden Files And Actions

Forbid app.json, project.config.json, tabBar, appid, route registration, backend schema changes, builds, workbench, Chickenbro, profile, fake source badges and hidden fallback.

## Owner Components

- ArticleListBoard
- ArticleReader
- PageFrame
- WowPanel
- RankedFeed
- EvidenceLedger
- ActionButton
- MaterialImage
- GameObjectIcon

## Material Asset Boundary

Use artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json with status material_asset_seed_ready. It is a seed only: pageDirectUseAllowed=false and productionUseAllowed=false, with no page direct use and no production direct use.

## Production Asset Manifest Gate

Before page integration, run node scripts/ui-system-production-asset-manifest-preflight.js --require-production-manifest --json for the real production asset manifest derived from the seed.

## Real WoW Source Map Gate

Before page integration, run node scripts/ui-system-real-wow-source-map-preflight.js --require-source-map --json for the real runtime source map. Real WoW objects stay outside imagegen material.

## Data Boundary

Use requestArticleList, requestArticleDetail, bodyBlocksZh, sourceBadges and article.sourceUrl.

## Protected Behaviors

Require source_translation, official_verified, approved, official sourceTier, visible fallback, explicit missing id and copy article.sourceUrl.

## Route Smoke Scenes

- news_channel_official
- news_list_metric_updates
- news_list_loading
- news_list_empty
- news_list_fallback
- news_list_open_detail
- news_detail_first
- news_detail_missing_id
- news_detail_not_found
- news_detail_fallback
- news_detail_copy_source
- news_detail_back_to_list

## Pre-Integration Checks

Rerun component precheck, target lock preflight and node scripts/ui-system-target-lock-decision-preflight.js --require-decision --json.

## Post-Integration Evidence

Collect screenshots, crops, overlay, red-zone, scorecard, route smoke and DevTools ledger.

## Stop Conditions

Stop on missing target lock, component geometry gaps or hidden fallback.

## Non-Promotion Boundary

This is not runtime_verified or final_accepted.
`

test('active permit preflight accepts the active news_list_detail permit by default', () => {
  const result = runPreflight(['--surface', 'news_list_detail', '--require-active-permit', '--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'active_permit_ready')
  assert.equal(report.surface, 'news_list_detail')
  assert.equal(report.targetDecisionExists, true)
  assert.equal(report.targetDecisionValid, true)
  assert.equal(report.decisionBriefPath, decisionBriefPath)
  assert.equal(report.decisionBriefValid, true)
  assert.equal(report.twoPartGoalSyncPath, twoPartGoalSyncPath)
  assert.equal(report.twoPartGoalSyncValid, true)
  assert.equal(report.permitExists, true)
  assert.equal(report.materialSeedPath, materialAssetSeedPath)
  assert.equal(report.materialSeedValid, true)
  assert.equal(report.implementationAllowed, true)
  assert.deepEqual(report.blockingReasons, [])
  assert.deepEqual(report.missingRequirements, [])
  assert.ok(report.requiredOwnerComponents.includes('ArticleReader'))
  assert.ok(report.requiredRouteSmokeScenes.includes('news_detail_copy_source'))
})

test('active permit preflight still blocks candidate permit while target lock is absent', () => {
  const candidate = makeCandidate(validPermitCandidate)
  const missingTargetDecision = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'wow-missing-target-')), 'missing.md')
  const result = runPreflight([
    '--surface',
    'news_list_detail',
    '--permit-file',
    candidate,
    '--target-decision-file',
    missingTargetDecision,
    '--require-active-permit',
    '--json'
  ])

  assert.equal(result.status, 5)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'active_permit_invalid')
  assert.equal(report.permitExists, true)
  assert.equal(report.targetDecisionExists, false)
  assert.equal(report.targetDecisionValid, false)
  assert.equal(report.implementationAllowed, false)
  assert.ok(report.blockingReasons.includes('missing_target_locked_decision_record'))
  assert.ok(report.missingRequirements.includes('target_decision_file'))
})

test('active permit preflight accepts complete candidate when target lock, decision brief, two-part goal and material seed are valid', () => {
  const candidate = makeCandidate(validPermitCandidate)
  const targetDecision = makeCandidate(validTargetDecisionCandidate)
  const result = runPreflight([
    '--surface',
    'news_list_detail',
    '--permit-file',
    candidate,
    '--target-decision-file',
    targetDecision,
    '--require-active-permit',
    '--json'
  ])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'active_permit_ready')
  assert.equal(report.targetDecisionExists, true)
  assert.equal(report.targetDecisionValid, true)
  assert.equal(report.decisionBriefValid, true)
  assert.equal(report.twoPartGoalSyncValid, true)
  assert.equal(report.materialSeedValid, true)
  assert.equal(report.permitExists, true)
  assert.equal(report.activePermitValid, true)
  assert.equal(report.implementationAllowed, true)
  assert.deepEqual(report.missingRequirements, [])
})

test('active permit preflight fails closed for unsafe decision brief and two-part goal sync', () => {
  const candidate = makeCandidate(validPermitCandidate)
  const targetDecision = makeCandidate(validTargetDecisionCandidate)
  const badBrief = readJson(decisionBriefPath)
  badBrief.runtimeVerified = true
  badBrief.requiredRuntimeGates = badBrief.requiredRuntimeGates.filter((gate) => gate !== 'production_asset_manifest_preflight')
  const badBriefPath = makeJsonCandidate(badBrief)
  const badGoalSync = readJson(twoPartGoalSyncPath)
  badGoalSync.pageIntegrationAllowed = true
  badGoalSync.deduplicatedTwoPartDocument = false
  const badGoalSyncPath = makeJsonCandidate(badGoalSync)

  const result = runPreflight([
    '--surface',
    'news_list_detail',
    '--permit-file',
    candidate,
    '--target-decision-file',
    targetDecision,
    '--decision-brief',
    badBriefPath,
    '--two-part-goal-sync',
    badGoalSyncPath,
    '--require-active-permit',
    '--json'
  ])

  assert.equal(result.status, 5)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'active_permit_invalid')
  assert.equal(report.decisionBriefValid, false)
  assert.equal(report.twoPartGoalSyncValid, false)
  assert.equal(report.implementationAllowed, false)
  assert.ok(report.blockingReasons.includes('invalid_target_lock_decision_brief'))
  assert.ok(report.blockingReasons.includes('invalid_two_part_goal_sync'))
  assert.ok(report.missingRequirements.includes('decision_brief_not_runtime_verified'))
  assert.ok(report.missingRequirements.includes('decision_brief_runtime_gate:production_asset_manifest_preflight'))
  assert.ok(report.missingRequirements.includes('two_part_goal_sync_deduplicated'))
  assert.ok(report.missingRequirements.includes('two_part_goal_sync_not_page_integration'))
})

test('active permit preflight fails closed for unsafe material seed', () => {
  const candidate = makeCandidate(validPermitCandidate)
  const targetDecision = makeCandidate(validTargetDecisionCandidate)
  const badSeed = readJson(materialAssetSeedPath)
  badSeed.productionManifest = true
  badSeed.assetSeeds[0].containsText = true
  badSeed.assetSeeds[0].pageDirectUseAllowed = true
  const badSeedPath = makeJsonCandidate(badSeed)

  const result = runPreflight([
    '--surface',
    'news_list_detail',
    '--permit-file',
    candidate,
    '--target-decision-file',
    targetDecision,
    '--material-asset-seed',
    badSeedPath,
    '--require-active-permit',
    '--json'
  ])

  assert.equal(result.status, 5)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'active_permit_invalid')
  assert.equal(report.materialSeedValid, false)
  assert.equal(report.implementationAllowed, false)
  assert.ok(report.blockingReasons.includes('invalid_material_asset_seed'))
  assert.ok(report.missingRequirements.includes('material_seed_not_production'))
  assert.ok(report.missingRequirements.some((item) => item.startsWith('unsafe_material_seed:')))
})

test('active permit template remains template-only and preserves news constraints', () => {
  const source = read(templatePath)
  const manifest = readJson(manifestPath)
  const readme = read(readmePath)

  assert.match(source, /^Status: `active_implementation_permit_template_only`$/m)
  assert.match(source, /Do not rename this file into the real active permit automatically/)
  assert.match(source, /pages\/news\/list\.wxml/)
  assert.match(source, /components\/article-reader\/\*/)
  assert.match(source, /Material Asset Boundary/)
  assert.match(source, /Production Asset Manifest Gate/)
  assert.match(source, /Real WoW Source Map Gate/)
  assert.match(source, /material_asset_seed_ready/)
  assert.match(source, /project\.config\.json/)
  assert.match(source, /news_detail_copy_source/)
  assert.match(source, /node scripts\/ui-system-active-permit-preflight\.js --surface news_list_detail --require-active-permit --json/)

  assert.equal(manifest.status, 'active_implementation_permit_template_and_preflight')
  assert.equal(manifest.surface, 'news_list_detail')
  assert.equal(manifest.targetLocked, false)
  assert.equal(manifest.activePermit, false)
  assert.equal(manifest.preflightScript, preflightScript)
  assert.equal(manifest.requiredDecisionBriefPath, decisionBriefPath)
  assert.equal(manifest.requiredTwoPartGoalSyncPath, twoPartGoalSyncPath)
  assert.equal(manifest.requiredMaterialAssetSeedPath, materialAssetSeedPath)
  assert.equal(manifest.expectedMaterialAssetSeedStatus, 'material_asset_seed_ready')
  assert.ok(manifest.allowedFiles.includes('pages/news/news-api.js'))
  assert.ok(manifest.requiredSections.includes('Two-Part Goal Boundary'))
  assert.ok(manifest.requiredSections.includes('Decision Brief Boundary'))
  assert.ok(manifest.requiredSections.includes('Material Asset Boundary'))
  assert.ok(manifest.preIntegrationChecks.includes('target_lock_decision_brief_preflight'))
  assert.ok(manifest.preIntegrationChecks.includes('two_part_goal_sync'))
  assert.ok(manifest.preIntegrationChecks.includes('production_asset_manifest_preflight'))
  assert.ok(manifest.preIntegrationChecks.includes('real_wow_source_map_preflight'))
  assert.ok(manifest.requiredOwnerComponents.includes('EvidenceLedger'))
  assert.ok(manifest.routeSmokeScenes.includes('news_detail_back_to_list'))
  assert.ok(manifest.nonPromotion.includes('not runtime_verified'))

  assert.match(readme, /activePermit: false/)
  assert.match(readme, /decisionBrief: `target_lock_decision_brief`/)
  assert.match(readme, /twoPartGoalSync: `two_part_goal_sync`/)
  assert.match(readme, /materialAssetSeed: `material_asset_seed_ready`/)
})

#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const DEFAULT_TARGET_DECISION_PATH = 'docs/design/2026-07-07-wow-ui-system-target-locked-decision.md'
const DEFAULT_DECISION_BRIEF_PATH = 'artifacts/ui-system-rebuild/20260707-target-lock-decision-brief/manifest.json'
const DEFAULT_TWO_PART_GOAL_SYNC_PATH = 'artifacts/ui-system-rebuild/20260707-two-part-goal-sync/manifest.json'
const DEFAULT_MATERIAL_SEED_PATH = 'artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json'
const DEFAULT_PERMIT_BY_SURFACE = {
  news_list_detail: 'docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md'
}
const REQUIRED_MATERIAL_CLASSES = [
  'panel',
  'border',
  'texture',
  'socket',
  'state-base',
  'state-atomic',
  'decorative'
]
const REQUIRED_OWNER_COMPONENTS = [
  'ArticleListBoard',
  'ArticleReader',
  'PageFrame',
  'WowPanel',
  'RankedFeed',
  'EvidenceLedger',
  'ActionButton',
  'MaterialImage',
  'GameObjectIcon'
]
const REQUIRED_ROUTE_SMOKE_SCENES = [
  'news_channel_official',
  'news_list_metric_updates',
  'news_list_loading',
  'news_list_empty',
  'news_list_fallback',
  'news_list_open_detail',
  'news_detail_first',
  'news_detail_missing_id',
  'news_detail_not_found',
  'news_detail_fallback',
  'news_detail_copy_source',
  'news_detail_back_to_list'
]
const REQUIRED_RUNTIME_GATES = [
  'production_asset_manifest_preflight',
  'real_wow_source_map_preflight',
  'page_adoption_preflight',
  'visual_acceptance_preflight',
  'route_smoke_execution_preflight',
  'devtools_action_ledger_preflight'
]
const REQUIRED_ALLOWED_FILES = [
  'pages/news/list.wxml',
  'pages/news/list.wxss',
  'pages/news/list.js',
  'pages/news/list.json',
  'pages/news/detail.wxml',
  'pages/news/detail.wxss',
  'pages/news/detail.js',
  'pages/news/detail.json',
  'pages/news/news-api.js',
  'components/article-list-board/*',
  'components/article-reader/*'
]
const REQUIRED_PATTERNS = [
  { id: 'status_active_implementation_permit', pattern: /^Status: `active_implementation_permit`$/m },
  { id: 'surface_news_list_detail', pattern: /Surface:\s*`news_list_detail`|Surface\s*\n[\s\S]*news_list_detail/ },
  { id: 'two_part_goal_boundary_section', pattern: /Two-Part Goal Boundary/ },
  { id: 'target_lock_decision_section', pattern: /Target Lock Decision/ },
  { id: 'decision_brief_boundary_section', pattern: /Decision Brief Boundary/ },
  { id: 'allowed_files_section', pattern: /Allowed Files/ },
  { id: 'forbidden_files_and_actions_section', pattern: /Forbidden Files And Actions/ },
  { id: 'owner_components_section', pattern: /Owner Components/ },
  { id: 'material_asset_boundary_section', pattern: /Material Asset Boundary/ },
  { id: 'production_asset_manifest_gate_section', pattern: /Production Asset Manifest Gate/ },
  { id: 'real_wow_source_map_gate_section', pattern: /Real WoW Source Map Gate/ },
  { id: 'data_boundary_section', pattern: /Data Boundary/ },
  { id: 'protected_behaviors_section', pattern: /Protected Behaviors/ },
  { id: 'route_smoke_scenes_section', pattern: /Route Smoke Scenes/ },
  { id: 'pre_integration_checks_section', pattern: /Pre-Integration Checks/ },
  { id: 'post_integration_evidence_section', pattern: /Post-Integration Evidence/ },
  { id: 'stop_conditions_section', pattern: /Stop Conditions/ },
  { id: 'non_promotion_boundary_section', pattern: /Non-Promotion Boundary/ },
  { id: 'forbid_app_json', pattern: /app\.json/ },
  { id: 'forbid_project_config', pattern: /project\.config\.json/ },
  { id: 'forbid_unrelated_surfaces', pattern: /builds[\s\S]*workbench[\s\S]*Chickenbro[\s\S]*profile|profile[\s\S]*Chickenbro[\s\S]*workbench[\s\S]*builds/ },
  { id: 'target_decision_preflight', pattern: /ui-system-target-lock-decision-preflight\.js/ },
  { id: 'two_part_goal_sync_path', pattern: /artifacts\/ui-system-rebuild\/20260707-two-part-goal-sync\/manifest\.json/ },
  { id: 'two_part_goal_sync_status', pattern: /two_part_goal_sync/ },
  { id: 'decision_brief_path', pattern: /artifacts\/ui-system-rebuild\/20260707-target-lock-decision-brief\/manifest\.json/ },
  { id: 'decision_brief_ready_status', pattern: /target_lock_decision_brief_ready|target_lock_decision_brief/ },
  { id: 'material_seed_path', pattern: /artifacts\/ui-system-rebuild\/20260707-material-asset-seed\/manifest\.json/ },
  { id: 'material_seed_ready', pattern: /material_asset_seed_ready/ },
  { id: 'material_seed_no_direct_use', pattern: /pageDirectUseAllowed=false[\s\S]*productionUseAllowed=false|no page direct use[\s\S]*no production direct use/i },
  { id: 'production_asset_manifest_preflight', pattern: /ui-system-production-asset-manifest-preflight\.js/ },
  { id: 'real_wow_source_map_preflight', pattern: /ui-system-real-wow-source-map-preflight\.js/ },
  { id: 'visible_fallback', pattern: /fallback[\s\S]*visible|visible[\s\S]*fallback/i },
  { id: 'source_translation_gate', pattern: /source_translation/ },
  { id: 'official_verified_gate', pattern: /official_verified/ },
  { id: 'copy_source_url', pattern: /article\.sourceUrl/ }
]

function optionValue(args, name, fallback) {
  const index = args.indexOf(name)
  if (index === -1) {
    return fallback
  }
  return args[index + 1]
}

function resolvePath(filePath) {
  return path.isAbsolute(filePath) ? filePath : path.join(ROOT, filePath)
}

function exists(filePath) {
  return fs.existsSync(resolvePath(filePath))
}

function read(filePath) {
  return fs.readFileSync(resolvePath(filePath), 'utf8')
}

function readJson(filePath) {
  return JSON.parse(read(filePath))
}

function includesAll(actual, expected) {
  const actualSet = new Set(actual || [])
  return expected.filter((item) => !actualSet.has(item))
}

function validateTargetDecision(targetDecisionPath) {
  const missingRequirements = []
  if (!exists(targetDecisionPath)) {
    return ['target_decision_file']
  }
  const source = read(targetDecisionPath)
  if (!/^Status: `target_locked`$/m.test(source)) {
    missingRequirements.push('target_decision_status')
  }
  if (!source.includes('Decision Brief Boundary')) {
    missingRequirements.push('target_decision_decision_brief_boundary')
  }
  if (!source.includes(DEFAULT_DECISION_BRIEF_PATH)) {
    missingRequirements.push('target_decision_decision_brief_path')
  }
  if (!/target_lock_decision_brief_ready|target_lock_decision_brief/.test(source)) {
    missingRequirements.push('target_decision_decision_brief_ready')
  }
  if (!source.includes('Material Asset Seed Boundary')) {
    missingRequirements.push('target_decision_material_seed_boundary')
  }
  if (!source.includes(DEFAULT_MATERIAL_SEED_PATH)) {
    missingRequirements.push('target_decision_material_seed_path')
  }
  if (!source.includes('material_asset_seed_ready')) {
    missingRequirements.push('target_decision_material_seed_ready')
  }
  for (const gate of REQUIRED_RUNTIME_GATES) {
    if (!source.includes(gate)) {
      missingRequirements.push(`target_decision_runtime_gate:${gate}`)
    }
  }
  return missingRequirements
}

function validateDecisionBrief(decisionBriefPath) {
  if (!exists(decisionBriefPath)) {
    return ['decision_brief_file']
  }
  let manifest
  try {
    manifest = readJson(decisionBriefPath)
  } catch (error) {
    return ['decision_brief_json_parse']
  }

  const missingRequirements = []
  if (manifest.status !== 'target_lock_decision_brief') missingRequirements.push('decision_brief_status')
  if (manifest.expectedReadyStatus !== 'target_lock_decision_brief_ready') missingRequirements.push('decision_brief_ready_status')
  if (manifest.recommendedTargetName !== 'A-Cockpit + B-Ledger + C-Captain') missingRequirements.push('decision_brief_target')
  if (manifest.recommendedFirstSurface !== 'news_list_detail') missingRequirements.push('decision_brief_first_surface')
  if (manifest.targetLocked !== false) missingRequirements.push('decision_brief_not_target_locked')
  if (manifest.activeImplementationPermit !== false) missingRequirements.push('decision_brief_not_active_permit')
  if (manifest.pageIntegration !== false) missingRequirements.push('decision_brief_not_page_integration')
  if (manifest.runtimeVerified !== false) missingRequirements.push('decision_brief_not_runtime_verified')
  if (manifest.finalAccepted !== false) missingRequirements.push('decision_brief_not_final_accepted')
  for (const gate of includesAll(manifest.requiredRuntimeGates, REQUIRED_RUNTIME_GATES)) {
    missingRequirements.push(`decision_brief_runtime_gate:${gate}`)
  }
  if (manifest.materialAssetSeed?.expectedStatus !== 'material_asset_seed_ready') {
    missingRequirements.push('decision_brief_material_seed')
  }
  if (manifest.realWowSourceMapSeed?.expectedStatus !== 'real_wow_source_map_seed_ready') {
    missingRequirements.push('decision_brief_source_map_seed')
  }
  return missingRequirements
}

function validateTwoPartGoalSync(twoPartGoalSyncPath) {
  if (!exists(twoPartGoalSyncPath)) {
    return ['two_part_goal_sync_file']
  }
  let manifest
  try {
    manifest = readJson(twoPartGoalSyncPath)
  } catch (error) {
    return ['two_part_goal_sync_json_parse']
  }

  const missingRequirements = []
  if (manifest.status !== 'two_part_goal_sync') missingRequirements.push('two_part_goal_sync_status')
  if (manifest.visibleTwoStepGoalSynced !== true) missingRequirements.push('two_part_goal_sync_visible')
  if (manifest.step1CodexGoalToUseNow !== true) missingRequirements.push('two_part_goal_sync_step1')
  if (manifest.step2ProjectDocumentationUpdateContract !== true) missingRequirements.push('two_part_goal_sync_step2')
  if (manifest.deduplicatedTwoPartDocument !== true) missingRequirements.push('two_part_goal_sync_deduplicated')
  if (manifest.activeGoalKeptOpen !== true) missingRequirements.push('two_part_goal_sync_active_goal_open')
  if (manifest.targetLocked !== false) missingRequirements.push('two_part_goal_sync_not_target_locked')
  if (manifest.activeImplementationPermit !== false) missingRequirements.push('two_part_goal_sync_not_active_permit')
  if (manifest.pageIntegrationAllowed !== false) missingRequirements.push('two_part_goal_sync_not_page_integration')
  if (manifest.runtimeVerified !== false) missingRequirements.push('two_part_goal_sync_not_runtime_verified')
  if (manifest.finalAccepted !== false) missingRequirements.push('two_part_goal_sync_not_final_accepted')
  if (!String(manifest.codexGoal || '').includes('WOW 小程序 UI 系统重建')) {
    missingRequirements.push('two_part_goal_sync_codex_goal')
  }
  return missingRequirements
}

function validateMaterialSeed(materialSeedPath) {
  if (!exists(materialSeedPath)) {
    return ['material_seed_file']
  }
  let manifest
  try {
    manifest = readJson(materialSeedPath)
  } catch (error) {
    return ['material_seed_json_parse']
  }

  const missingRequirements = []
  if (manifest.status !== 'material_asset_seed_ready') missingRequirements.push('material_seed_status')
  if (manifest.materialAssetSeedReady !== true) missingRequirements.push('material_seed_ready')
  if (manifest.productionManifest !== false) missingRequirements.push('material_seed_not_production')

  const seeds = manifest.assetSeeds || []
  const classes = Array.from(new Set(seeds.map((seed) => seed.class).filter(Boolean)))
  for (const materialClass of includesAll(classes, REQUIRED_MATERIAL_CLASSES)) {
    missingRequirements.push(`material_class:${materialClass}`)
  }
  const unsafeSeeds = seeds.filter((seed) => (
    seed.containsText !== false ||
    seed.containsFakeChrome !== false ||
    seed.containsRealWowObject !== false ||
    seed.containsSourceLogo !== false ||
    seed.containsBusinessConclusion !== false ||
    seed.containsGeneratedObjectIcon !== false ||
    seed.pageDirectUseAllowed !== false ||
    seed.productionUseAllowed !== false ||
    seed.requiresRecutBeforeProduction !== true
  ))
  for (const seed of unsafeSeeds) {
    missingRequirements.push(`unsafe_material_seed:${seed.id || 'unknown'}`)
  }

  return missingRequirements
}

function validatePermit(source) {
  const missingRequirements = []
  for (const requirement of REQUIRED_PATTERNS) {
    if (!requirement.pattern.test(source)) {
      missingRequirements.push(requirement.id)
    }
  }
  for (const owner of REQUIRED_OWNER_COMPONENTS) {
    if (!source.includes(owner)) {
      missingRequirements.push(`owner:${owner}`)
    }
  }
  for (const scene of REQUIRED_ROUTE_SMOKE_SCENES) {
    if (!source.includes(scene)) {
      missingRequirements.push(`route:${scene}`)
    }
  }
  for (const file of REQUIRED_ALLOWED_FILES) {
    if (!source.includes(file)) {
      missingRequirements.push(`allowedFile:${file}`)
    }
  }
  return missingRequirements
}

function buildReport(args) {
  const surface = optionValue(args, '--surface', 'news_list_detail')
  const permitPath = optionValue(args, '--permit-file', DEFAULT_PERMIT_BY_SURFACE[surface])
  const targetDecisionPath = optionValue(args, '--target-decision-file', DEFAULT_TARGET_DECISION_PATH)
  const decisionBriefPath = optionValue(args, '--decision-brief', DEFAULT_DECISION_BRIEF_PATH)
  const twoPartGoalSyncPath = optionValue(args, '--two-part-goal-sync', DEFAULT_TWO_PART_GOAL_SYNC_PATH)
  const materialSeedPath = optionValue(args, '--material-asset-seed', DEFAULT_MATERIAL_SEED_PATH)
  const targetDecisionExists = exists(targetDecisionPath)
  const targetDecisionMissingRequirements = validateTargetDecision(targetDecisionPath)
  const targetDecisionValid = targetDecisionMissingRequirements.length === 0
  const decisionBriefMissingRequirements = validateDecisionBrief(decisionBriefPath)
  const decisionBriefValid = decisionBriefMissingRequirements.length === 0
  const twoPartGoalSyncMissingRequirements = validateTwoPartGoalSync(twoPartGoalSyncPath)
  const twoPartGoalSyncValid = twoPartGoalSyncMissingRequirements.length === 0
  const materialSeedMissingRequirements = validateMaterialSeed(materialSeedPath)
  const materialSeedValid = materialSeedMissingRequirements.length === 0
  const blockingReasons = []

  if (!targetDecisionExists) {
    blockingReasons.push('missing_target_locked_decision_record')
  } else if (!targetDecisionValid) {
    blockingReasons.push('invalid_target_locked_decision_record')
  }
  if (!materialSeedValid) {
    blockingReasons.push('invalid_material_asset_seed')
  }
  if (!decisionBriefValid) {
    blockingReasons.push('invalid_target_lock_decision_brief')
  }
  if (!twoPartGoalSyncValid) {
    blockingReasons.push('invalid_two_part_goal_sync')
  }
  if (!permitPath || !exists(permitPath)) {
    blockingReasons.push('missing_active_implementation_permit')
    return {
      status: 'active_permit_missing',
      surface,
      targetDecisionPath,
      targetDecisionExists,
      targetDecisionValid,
      targetDecisionMissingRequirements,
      decisionBriefPath,
      decisionBriefValid,
      decisionBriefMissingRequirements,
      twoPartGoalSyncPath,
      twoPartGoalSyncValid,
      twoPartGoalSyncMissingRequirements,
      materialSeedPath,
      materialSeedValid,
      materialSeedMissingRequirements,
      permitPath,
      permitExists: false,
      activePermitValid: false,
      implementationAllowed: false,
      blockingReasons,
      missingRequirements: ['active_permit_file'],
      requiredOwnerComponents: REQUIRED_OWNER_COMPONENTS,
      requiredRouteSmokeScenes: REQUIRED_ROUTE_SMOKE_SCENES
    }
  }

  const source = read(permitPath)
  const permitMissingRequirements = validatePermit(source)
  const missingRequirements = [
    ...targetDecisionMissingRequirements,
    ...decisionBriefMissingRequirements,
    ...twoPartGoalSyncMissingRequirements,
    ...materialSeedMissingRequirements,
    ...permitMissingRequirements
  ]
  const activePermitValid = targetDecisionValid &&
    decisionBriefValid &&
    twoPartGoalSyncValid &&
    materialSeedValid &&
    missingRequirements.length === 0
  if (!activePermitValid && missingRequirements.length > 0) {
    blockingReasons.push('active_permit_incomplete')
  }

  return {
    status: activePermitValid ? 'active_permit_ready' : 'active_permit_invalid',
    surface,
    targetDecisionPath,
    targetDecisionExists,
    targetDecisionValid,
    targetDecisionMissingRequirements,
    decisionBriefPath,
    decisionBriefValid,
    decisionBriefMissingRequirements,
    twoPartGoalSyncPath,
    twoPartGoalSyncValid,
    twoPartGoalSyncMissingRequirements,
    materialSeedPath,
    materialSeedValid,
    materialSeedMissingRequirements,
    permitPath,
    permitExists: true,
    activePermitValid,
    implementationAllowed: activePermitValid,
    blockingReasons,
    missingRequirements,
    requiredOwnerComponents: REQUIRED_OWNER_COMPONENTS,
    requiredRouteSmokeScenes: REQUIRED_ROUTE_SMOKE_SCENES
  }
}

function main() {
  const args = process.argv.slice(2)
  const flags = new Set(args)
  const report = buildReport(args)

  if (flags.has('--json')) {
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
  } else {
    process.stdout.write(`status=${report.status}\n`)
    process.stdout.write(`surface=${report.surface}\n`)
    process.stdout.write(`implementationAllowed=${report.implementationAllowed}\n`)
    if (report.blockingReasons.length) {
      process.stdout.write(`blockingReasons=${report.blockingReasons.join(',')}\n`)
    }
  }

  if (flags.has('--require-active-permit') && !report.implementationAllowed) {
    process.exitCode = 5
  }
}

main()

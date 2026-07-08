#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const EXIT_NOT_READY = 18

const REQUIRED_SURFACE = 'news_list_detail'
const REQUIRED_OWNERS = ['ArticleListBoard', 'ArticleReader']
const REQUIRED_TEMPLATE_OWNERS = [
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
const REQUIRED_TEMPLATE_SCENES = [
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
const REQUIRED_ACTIVE_PERMIT_SECTIONS = [
  'Two-Part Goal Boundary',
  'Decision Brief Boundary',
  'Material Asset Boundary',
  'Production Asset Manifest Gate',
  'Real WoW Source Map Gate',
  'Post-Integration Evidence',
  'Non-Promotion Boundary'
]
const REQUIRED_ACTIVE_PERMIT_PRECHECKS = [
  'target_lock_decision_brief_preflight',
  'target_lock_decision_preflight',
  'active_permit_preflight',
  'two_part_goal_sync',
  'production_asset_manifest_preflight',
  'real_wow_source_map_preflight',
  'page_adoption_preflight'
]
const REQUIRED_ROUTE_PLAN_SCENES = [
  'news_home_top',
  'news_home_scrolled',
  'news_channel_official',
  'news_detail_first'
]
const REQUIRED_MATERIAL_CLASSES = [
  'panel',
  'border',
  'texture',
  'socket',
  'state-base',
  'state-atomic',
  'decorative'
]

const DEFAULT_PATHS = {
  activationPacket: 'docs/plans/2026-07-07-wow-ui-system-target-lock-decision-and-news-list-detail-activation-packet.md',
  activationPacketManifest: 'artifacts/ui-system-rebuild/20260707-target-lock-decision-and-news-list-detail-activation-packet/manifest.json',
  targetLockReadiness: 'artifacts/ui-system-rebuild/20260707-target-lock-readiness-preflight/manifest.json',
  ownerRegistry: 'artifacts/ui-system-rebuild/20260707-owner-registry-preflight/manifest.json',
  materialAssetSeed: 'artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json',
  sourceMapSeed: 'artifacts/ui-system-rebuild/20260707-real-wow-source-map-seed/manifest.json',
  permitDraft: 'artifacts/ui-system-rebuild/20260707-news-list-detail-permit-draft/manifest.json',
  activePermitTemplate: 'artifacts/ui-system-rebuild/20260707-news-list-detail-active-permit-template/manifest.json',
  ownerSkeleton: 'artifacts/ui-system-rebuild/20260707-news-list-detail-owner-skeleton/manifest.json',
  componentPrecheck: 'artifacts/ui-system-rebuild/20260707-news-list-detail-component-precheck/manifest.json',
  routeSmokePlan: 'artifacts/ui-system-rebuild/20260707-route-smoke-plan/manifest.json',
  routeSmokeExecutionTemplate: 'artifacts/ui-system-rebuild/20260707-route-smoke-execution-template/manifest.json',
  visualAcceptanceTemplate: 'artifacts/ui-system-rebuild/20260707-visual-acceptance-scorecard-template/manifest.json',
  devtoolsLedgerTemplate: 'artifacts/ui-system-rebuild/20260707-devtools-action-ledger-template/manifest.json',
  pageAdoptionTemplate: 'artifacts/ui-system-rebuild/20260707-page-adoption-preflight-template/manifest.json',
  productionAssetTemplate: 'artifacts/ui-system-rebuild/20260707-production-asset-manifest-template/manifest.json'
}

function optionValue(args, name, fallback) {
  const index = args.indexOf(name)
  return index === -1 ? fallback : args[index + 1]
}

function resolvePath(filePath) {
  return path.isAbsolute(filePath) ? filePath : path.join(ROOT, filePath)
}

function exists(filePath) {
  return Boolean(filePath) && fs.existsSync(resolvePath(filePath))
}

function read(filePath) {
  return fs.readFileSync(resolvePath(filePath), 'utf8')
}

function readJson(filePath) {
  return JSON.parse(read(filePath))
}

function boolIsFalse(value) {
  return value === false || value === undefined
}

function includesAll(actual, expected) {
  const actualSet = new Set(actual || [])
  return expected.filter((item) => !actualSet.has(item))
}

function addCheck(checks, id, pass, detail = {}) {
  checks.push({ id, status: pass ? 'pass' : 'fail', ...detail })
}

function safeJson(checks, id, filePath) {
  if (!exists(filePath)) {
    addCheck(checks, `${id}_exists`, false, { path: filePath })
    return null
  }
  try {
    const data = readJson(filePath)
    addCheck(checks, `${id}_json_parse`, true, { path: filePath })
    return data
  } catch (error) {
    addCheck(checks, `${id}_json_parse`, false, {
      path: filePath,
      error: error.message
    })
    return null
  }
}

function validateNonPromotion(checks, id, manifest) {
  if (!manifest) return
  const fields = [
    'targetLocked',
    'activePermit',
    'activeImplementationPermit',
    'pageIntegration',
    'implementationAllowed',
    'runtimeVerified',
    'finalAccepted',
    'strictGateEligible',
    'devtoolsTouched'
  ]
  const promoted = fields.filter((field) => !boolIsFalse(manifest[field]))
  addCheck(checks, `${id}_non_promotion`, promoted.length === 0, { promoted })
}

function validateActivationPacket(checks, paths) {
  if (!exists(paths.activationPacket)) {
    addCheck(checks, 'activation_packet_doc_exists', false, { path: paths.activationPacket })
    return
  }
  const source = read(paths.activationPacket)
  addCheck(checks, 'activation_packet_doc_exists', true, { path: paths.activationPacket })
  addCheck(checks, 'activation_packet_status_draft', /^Status: `activation_packet_draft`$/m.test(source))
  addCheck(checks, 'activation_packet_mentions_news_list_detail', source.includes(REQUIRED_SURFACE))
  addCheck(checks, 'activation_packet_non_promotion', /not `target_locked`[\s\S]*not an active implementation permit[\s\S]*not page integration/.test(source))
  for (const scene of REQUIRED_TEMPLATE_SCENES) {
    addCheck(checks, `activation_packet_scene:${scene}`, source.includes(scene))
  }
}

function validateTargetReadiness(checks, manifest) {
  if (!manifest) return
  addCheck(checks, 'target_readiness_expected_ready', manifest.expectedReadyStatus === 'target_lock_readiness_ready', {
    actual: manifest.expectedReadyStatus
  })
  addCheck(checks, 'target_readiness_recommends_target', manifest.recommendedTargetName === 'A-Cockpit + B-Ledger + C-Captain', {
    actual: manifest.recommendedTargetName
  })
  addCheck(checks, 'target_readiness_includes_news_list_detail', (manifest.requiredCoreSurfaces || []).includes(REQUIRED_SURFACE))
}

function validateOwnerRegistry(checks, manifest) {
  if (!manifest) return
  const coverage = manifest.surfaceCoverage || {}
  addCheck(checks, 'owner_registry_ready', manifest.status === 'owner_registry_source_ready' && manifest.ownerRegistryReady === true, {
    actual: manifest.status
  })
  addCheck(checks, 'owner_registry_news_list_detail_owners', includesAll(coverage[REQUIRED_SURFACE], REQUIRED_OWNERS).length === 0, {
    missingOwners: includesAll(coverage[REQUIRED_SURFACE], REQUIRED_OWNERS)
  })
  addCheck(checks, 'owner_registry_boundaries', (
    manifest.boundaryOwners?.realObjectIconOwner === 'GameObjectIcon' &&
    manifest.boundaryOwners?.materialOwner === 'MaterialImage' &&
    manifest.boundaryOwners?.evidenceOwner === 'EvidenceLedger'
  ), {
    boundaryOwners: manifest.boundaryOwners || {}
  })
}

function validateSourceMapSeed(checks, manifest) {
  if (!manifest) return
  addCheck(checks, 'source_map_seed_ready', manifest.status === 'real_wow_source_map_seed_ready', { actual: manifest.status })
  addCheck(checks, 'source_map_seed_runtime_false', manifest.runtimeSourceMapReady === false)
  const sourceEntries = manifest.sourceEntries || []
  const newsSourceEntries = sourceEntries.filter((entry) => (entry.allowedSurfaces || []).includes(REQUIRED_SURFACE))
  addCheck(checks, 'source_map_seed_news_surface_entries', newsSourceEntries.length > 0, {
    entryCount: newsSourceEntries.length
  })
  const generatedEntries = sourceEntries.filter((entry) => entry.generatedByImagegen !== false || entry.containsGeneratedObject !== false)
  addCheck(checks, 'source_map_seed_no_generated_objects', generatedEntries.length === 0, {
    generatedEntries: generatedEntries.map((entry) => entry.id)
  })
}

function validateMaterialAssetSeed(checks, manifest) {
  if (!manifest) return
  const assetSeeds = manifest.assetSeeds || []
  const coveredClasses = Array.from(new Set(assetSeeds.map((seed) => seed.class).filter(Boolean)))
  const newsSeeds = assetSeeds.filter((seed) => (seed.allowedSurfaces || []).includes(REQUIRED_SURFACE))
  const unsafeSeeds = assetSeeds.filter((seed) => (
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

  addCheck(checks, 'material_asset_seed_ready', manifest.status === 'material_asset_seed_ready' && manifest.materialAssetSeedReady === true, {
    actual: manifest.status,
    materialAssetSeedReady: manifest.materialAssetSeedReady
  })
  addCheck(checks, 'material_asset_seed_not_production', manifest.productionManifest === false, {
    productionManifest: manifest.productionManifest
  })
  addCheck(checks, 'material_asset_seed_class_coverage', includesAll(coveredClasses, REQUIRED_MATERIAL_CLASSES).length === 0, {
    missingMaterialClasses: includesAll(coveredClasses, REQUIRED_MATERIAL_CLASSES)
  })
  addCheck(checks, 'material_asset_seed_news_surface', newsSeeds.length > 0, {
    seedCount: newsSeeds.length
  })
  addCheck(checks, 'material_asset_seed_semantic_safety', unsafeSeeds.length === 0, {
    unsafeSeedIds: unsafeSeeds.map((seed) => seed.id)
  })
  addCheck(checks, 'material_asset_seed_package_budget', (
    manifest.packageBudget &&
    manifest.packageBudget.currentKb <= manifest.packageBudget.maxKb &&
    manifest.packageBudget.maxKb <= 512
  ), {
    packageBudget: manifest.packageBudget || null
  })
}

function validatePermitDraft(checks, manifest) {
  if (!manifest) return
  addCheck(checks, 'permit_draft_surface', manifest.status === 'implementation_permit_draft' && manifest.surface === REQUIRED_SURFACE, {
    status: manifest.status,
    surface: manifest.surface
  })
}

function validateActivePermitTemplate(checks, manifest) {
  if (!manifest) return
  addCheck(checks, 'active_permit_template_status', manifest.status === 'active_implementation_permit_template_and_preflight', {
    actual: manifest.status
  })
  addCheck(checks, 'active_permit_template_surface', manifest.surface === REQUIRED_SURFACE, { actual: manifest.surface })
  addCheck(checks, 'active_permit_template_decision_brief_boundary', (
    manifest.requiredDecisionBriefPath === 'artifacts/ui-system-rebuild/20260707-target-lock-decision-brief/manifest.json' &&
    manifest.expectedDecisionBriefStatus === 'target_lock_decision_brief' &&
    manifest.expectedDecisionBriefReadyStatus === 'target_lock_decision_brief_ready'
  ), {
    requiredDecisionBriefPath: manifest.requiredDecisionBriefPath,
    expectedDecisionBriefStatus: manifest.expectedDecisionBriefStatus,
    expectedDecisionBriefReadyStatus: manifest.expectedDecisionBriefReadyStatus
  })
  addCheck(checks, 'active_permit_template_two_part_goal_boundary', (
    manifest.requiredTwoPartGoalSyncPath === 'artifacts/ui-system-rebuild/20260707-two-part-goal-sync/manifest.json' &&
    manifest.expectedTwoPartGoalSyncStatus === 'two_part_goal_sync'
  ), {
    requiredTwoPartGoalSyncPath: manifest.requiredTwoPartGoalSyncPath,
    expectedTwoPartGoalSyncStatus: manifest.expectedTwoPartGoalSyncStatus
  })
  addCheck(checks, 'active_permit_template_owner_coverage', includesAll(manifest.requiredOwnerComponents, REQUIRED_TEMPLATE_OWNERS).length === 0, {
    missingOwners: includesAll(manifest.requiredOwnerComponents, REQUIRED_TEMPLATE_OWNERS)
  })
  addCheck(checks, 'active_permit_template_scene_coverage', includesAll(manifest.routeSmokeScenes, REQUIRED_TEMPLATE_SCENES).length === 0, {
    missingScenes: includesAll(manifest.routeSmokeScenes, REQUIRED_TEMPLATE_SCENES)
  })
  addCheck(checks, 'active_permit_template_section_coverage', includesAll(manifest.requiredSections, REQUIRED_ACTIVE_PERMIT_SECTIONS).length === 0, {
    missingSections: includesAll(manifest.requiredSections, REQUIRED_ACTIVE_PERMIT_SECTIONS)
  })
  addCheck(checks, 'active_permit_template_precheck_coverage', includesAll(manifest.preIntegrationChecks, REQUIRED_ACTIVE_PERMIT_PRECHECKS).length === 0, {
    missingPrechecks: includesAll(manifest.preIntegrationChecks, REQUIRED_ACTIVE_PERMIT_PRECHECKS)
  })
}

function validateOwnerSkeleton(checks, manifest) {
  if (!manifest) return
  addCheck(checks, 'owner_skeleton_status', manifest.status === 'owner_skeleton_source_precheck' && manifest.surface === REQUIRED_SURFACE, {
    status: manifest.status,
    surface: manifest.surface
  })
  const owners = (manifest.ownerComponents || []).map((owner) => owner.owner)
  addCheck(checks, 'owner_skeleton_owner_coverage', includesAll(owners, REQUIRED_OWNERS).length === 0, {
    missingOwners: includesAll(owners, REQUIRED_OWNERS)
  })
  addCheck(checks, 'owner_skeleton_fixture_matrix', (manifest.fixtureIds || []).length >= 10, {
    fixtureCount: (manifest.fixtureIds || []).length
  })
}

function validateComponentPrecheck(checks, manifest) {
  if (!manifest) return
  addCheck(checks, 'component_precheck_status', manifest.status === 'surface_component_precheck' && manifest.surface === REQUIRED_SURFACE, {
    status: manifest.status,
    surface: manifest.surface
  })
  addCheck(checks, 'component_precheck_flags', manifest.componentPrecheck === true && manifest.browserPrecheck === true, {
    componentPrecheck: manifest.componentPrecheck,
    browserPrecheck: manifest.browserPrecheck
  })
  addCheck(checks, 'component_precheck_owner_reports_pass', (manifest.ownerReports || []).every((owner) => owner.status === 'pass'), {
    ownerStatuses: (manifest.ownerReports || []).map((owner) => `${owner.owner}:${owner.status}`)
  })
  addCheck(checks, 'component_precheck_no_failures', (manifest.failures || []).length === 0, {
    failures: manifest.failures || []
  })
  addCheck(checks, 'component_precheck_no_warnings', (manifest.warnings || []).length === 0, {
    warnings: manifest.warnings || []
  })
  const overflow = (manifest.measurements || []).filter((measurement) => (measurement.document || {}).horizontalOverflow !== 0)
  addCheck(checks, 'component_precheck_no_horizontal_overflow', overflow.length === 0, {
    overflow: overflow.map((item) => item.viewport?.id || 'unknown')
  })
  addCheck(checks, 'component_precheck_crops_exist', (manifest.crops || []).length >= 7 && exists(manifest.contactSheet), {
    cropCount: (manifest.crops || []).length,
    contactSheet: manifest.contactSheet
  })
}

function validateRouteSmokePlan(checks, manifest) {
  if (!manifest) return
  addCheck(checks, 'route_smoke_plan_status', manifest.status === 'route_smoke_plan_draft', { actual: manifest.status })
  const sceneIds = (manifest.scenes || []).map((scene) => scene.id)
  addCheck(checks, 'route_smoke_plan_core_scene_count', sceneIds.length >= 27, { sceneCount: sceneIds.length })
  addCheck(checks, 'route_smoke_plan_news_scene_coverage', includesAll(sceneIds, REQUIRED_ROUTE_PLAN_SCENES).length === 0, {
    missingScenes: includesAll(sceneIds, REQUIRED_ROUTE_PLAN_SCENES)
  })
  addCheck(checks, 'route_smoke_plan_capture_safe_policy', manifest.devtoolsPolicy?.requiresCaptureSafe === true, {
    devtoolsPolicy: manifest.devtoolsPolicy || {}
  })
}

function validateTemplateStatus(checks, id, manifest, expectedStatus) {
  if (!manifest) return
  addCheck(checks, `${id}_status`, manifest.status === expectedStatus, {
    actual: manifest.status,
    expected: expectedStatus
  })
}

function buildReport(args) {
  const paths = { ...DEFAULT_PATHS }
  for (const key of Object.keys(paths)) {
    paths[key] = optionValue(args, `--${key.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)}`, paths[key])
  }

  const checks = []
  validateActivationPacket(checks, paths)

  const manifests = {
    activationPacketManifest: safeJson(checks, 'activation_packet_manifest', paths.activationPacketManifest),
    targetLockReadiness: safeJson(checks, 'target_lock_readiness', paths.targetLockReadiness),
    ownerRegistry: safeJson(checks, 'owner_registry', paths.ownerRegistry),
    materialAssetSeed: safeJson(checks, 'material_asset_seed', paths.materialAssetSeed),
    sourceMapSeed: safeJson(checks, 'source_map_seed', paths.sourceMapSeed),
    permitDraft: safeJson(checks, 'permit_draft', paths.permitDraft),
    activePermitTemplate: safeJson(checks, 'active_permit_template', paths.activePermitTemplate),
    ownerSkeleton: safeJson(checks, 'owner_skeleton', paths.ownerSkeleton),
    componentPrecheck: safeJson(checks, 'component_precheck', paths.componentPrecheck),
    routeSmokePlan: safeJson(checks, 'route_smoke_plan', paths.routeSmokePlan),
    routeSmokeExecutionTemplate: safeJson(checks, 'route_smoke_execution_template', paths.routeSmokeExecutionTemplate),
    visualAcceptanceTemplate: safeJson(checks, 'visual_acceptance_template', paths.visualAcceptanceTemplate),
    devtoolsLedgerTemplate: safeJson(checks, 'devtools_ledger_template', paths.devtoolsLedgerTemplate),
    pageAdoptionTemplate: safeJson(checks, 'page_adoption_template', paths.pageAdoptionTemplate),
    productionAssetTemplate: safeJson(checks, 'production_asset_template', paths.productionAssetTemplate)
  }

  for (const [id, manifest] of Object.entries(manifests)) {
    validateNonPromotion(checks, id, manifest)
  }

  validateTemplateStatus(checks, 'activation_packet_manifest', manifests.activationPacketManifest, 'activation_packet_draft')
  validateTargetReadiness(checks, manifests.targetLockReadiness)
  validateOwnerRegistry(checks, manifests.ownerRegistry)
  validateMaterialAssetSeed(checks, manifests.materialAssetSeed)
  validateSourceMapSeed(checks, manifests.sourceMapSeed)
  validatePermitDraft(checks, manifests.permitDraft)
  validateActivePermitTemplate(checks, manifests.activePermitTemplate)
  validateOwnerSkeleton(checks, manifests.ownerSkeleton)
  validateComponentPrecheck(checks, manifests.componentPrecheck)
  validateRouteSmokePlan(checks, manifests.routeSmokePlan)
  validateTemplateStatus(checks, 'route_smoke_execution_template', manifests.routeSmokeExecutionTemplate, 'route_smoke_execution_template_only')
  validateTemplateStatus(checks, 'visual_acceptance_template', manifests.visualAcceptanceTemplate, 'visual_acceptance_scorecard_template_only')
  validateTemplateStatus(checks, 'devtools_ledger_template', manifests.devtoolsLedgerTemplate, 'devtools_action_ledger_template_only')
  validateTemplateStatus(checks, 'page_adoption_template', manifests.pageAdoptionTemplate, 'page_adoption_preflight_template_only')
  validateTemplateStatus(checks, 'production_asset_template', manifests.productionAssetTemplate, 'production_asset_manifest_template_only')

  const failingChecks = checks.filter((check) => check.status === 'fail')
  const ready = failingChecks.length === 0
  return {
    status: ready ? 'first_surface_activation_readiness_ready' : 'first_surface_activation_readiness_incomplete',
    surface: REQUIRED_SURFACE,
    readyForTargetLockActivation: ready,
    targetLocked: false,
    activeImplementationPermit: false,
    pageIntegration: false,
    runtimeVerified: false,
    finalAccepted: false,
    checkedPathCount: Object.keys(paths).length,
    checkCount: checks.length,
    failingCheckCount: failingChecks.length,
    failingChecks,
    requiredOwners: REQUIRED_OWNERS,
    requiredTemplateScenes: REQUIRED_TEMPLATE_SCENES,
    requiredRoutePlanScenes: REQUIRED_ROUTE_PLAN_SCENES,
    nextLegalTransition: 'explicit target-lock confirmation or written modification, then target-locked decision record, then exactly one active implementation permit',
    nonPromotion: [
      'not target_locked',
      'not active_implementation_permit',
      'not page_integration',
      'not runtime_verified',
      'not final_accepted'
    ]
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
    process.stdout.write(`readyForTargetLockActivation=${report.readyForTargetLockActivation}\n`)
    process.stdout.write(`failingCheckCount=${report.failingCheckCount}\n`)
  }

  if (flags.has('--require-ready') && !report.readyForTargetLockActivation) {
    process.exitCode = EXIT_NOT_READY
  }
}

main()

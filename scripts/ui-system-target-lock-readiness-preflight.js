#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const EXIT_NOT_READY = 14

const REQUIRED_CORE_SURFACES = [
  'news_home',
  'news_list_detail',
  'builds_tab',
  'current_spec_workbench',
  'talent_simulator',
  'gear_detail',
  'simc',
  'chickenbro',
  'tasks',
  'profile_templates'
]

const REQUIRED_CANDIDATE_SURFACES = [
  'news',
  'builds',
  'workbench',
  'chickenbro'
]

const REQUIRED_ROUTE_SMOKE_SURFACES = [
  'news',
  'builds',
  'workbench',
  'talent',
  'gear',
  'simc',
  'chickenbro',
  'tasks',
  'profile'
]

const REQUIRED_OWNERS = [
  'AppShell',
  'PageFrame',
  'WowPanel',
  'MaterialImage',
  'GameObjectIcon',
  'StatusVisual',
  'ActionButton',
  'ModuleCard',
  'ChannelDock',
  'RankedFeed',
  'EvidenceLedger',
  'ChatShell'
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
  readinessReview: 'docs/design/2026-07-07-wow-ui-system-target-lock-readiness-review.md',
  readinessManifest: 'artifacts/ui-system-rebuild/20260707-target-lock-readiness-review/manifest.json',
  decisionBrief: 'artifacts/ui-system-rebuild/20260707-target-lock-decision-brief/manifest.json',
  proposal: 'docs/design/2026-07-07-wow-ui-system-target-lock-proposal.md',
  proposalManifest: 'artifacts/ui-system-rebuild/20260707-target-lock-proposal/manifest.json',
  candidates: 'docs/design/2026-07-07-wow-ui-system-phase3-design-candidates.md',
  candidatesManifest: 'artifacts/ui-system-rebuild/20260707-phase3-target-candidates/manifest.json',
  foundationContracts: 'docs/design/2026-07-07-wow-ui-system-foundation-component-contracts.md',
  foundationManifest: 'artifacts/ui-system-rebuild/20260707-foundation-component-contracts/manifest.json',
  surfaceContracts: 'docs/design/2026-07-07-wow-ui-system-surface-owner-contracts.md',
  surfaceManifest: 'artifacts/ui-system-rebuild/20260707-surface-owner-contracts/manifest.json',
  assetManifestDraft: 'artifacts/ui-system-rebuild/20260707-asset-manifest-draft/manifest.json',
  materialAssetSeed: 'artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json',
  routeSmokePlan: 'artifacts/ui-system-rebuild/20260707-route-smoke-plan/manifest.json',
  permitCoverage: 'artifacts/ui-system-rebuild/20260707-permit-coverage-matrix/manifest.json',
  browserComponentPrecheck: 'artifacts/ui-system-rebuild/20260707-browser-component-precheck/manifest.json'
}

function optionValue(args, name, fallback) {
  const index = args.indexOf(name)
  return index === -1 ? fallback : args[index + 1]
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

function unique(values) {
  return Array.from(new Set(values))
}

function includesAll(actual, expected) {
  const actualSet = new Set(actual || [])
  return expected.filter((item) => !actualSet.has(item))
}

function boolIsFalse(value) {
  return value === false || value === undefined
}

function collectFileChecks(paths) {
  return Object.entries(paths)
    .map(([id, filePath]) => ({
      id,
      path: filePath,
      exists: exists(filePath)
    }))
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
  if (!manifest) {
    return
  }
  const fields = [
    'targetLocked',
    'activePermit',
    'activeImplementationPermit',
    'pageIntegration',
    'implementationPermit',
    'runtimeVerified',
    'finalAccepted',
    'strictGateEligible',
    'devtoolsTouched'
  ]
  const promoted = fields.filter((field) => !boolIsFalse(manifest[field]))
  addCheck(checks, `${id}_non_promotion`, promoted.length === 0, { promoted })
}

function buildReport(args) {
  const paths = {
    ...DEFAULT_PATHS,
    readinessManifest: optionValue(args, '--readiness-manifest', DEFAULT_PATHS.readinessManifest),
    decisionBrief: optionValue(args, '--decision-brief', DEFAULT_PATHS.decisionBrief),
    proposalManifest: optionValue(args, '--proposal-manifest', DEFAULT_PATHS.proposalManifest),
    candidatesManifest: optionValue(args, '--candidates-manifest', DEFAULT_PATHS.candidatesManifest),
    routeSmokePlan: optionValue(args, '--route-smoke-plan', DEFAULT_PATHS.routeSmokePlan),
    permitCoverage: optionValue(args, '--permit-coverage', DEFAULT_PATHS.permitCoverage),
    browserComponentPrecheck: optionValue(args, '--browser-component-precheck', DEFAULT_PATHS.browserComponentPrecheck),
    assetManifestDraft: optionValue(args, '--asset-manifest-draft', DEFAULT_PATHS.assetManifestDraft),
    materialAssetSeed: optionValue(args, '--material-asset-seed', DEFAULT_PATHS.materialAssetSeed)
  }

  const checks = []
  const fileChecks = collectFileChecks(paths)
  for (const check of fileChecks) {
    addCheck(checks, `file:${check.id}`, check.exists, { path: check.path })
  }

  const readiness = safeJson(checks, 'readiness_manifest', paths.readinessManifest)
  const decisionBrief = safeJson(checks, 'decision_brief', paths.decisionBrief)
  const proposal = safeJson(checks, 'proposal_manifest', paths.proposalManifest)
  const candidates = safeJson(checks, 'candidates_manifest', paths.candidatesManifest)
  const foundation = safeJson(checks, 'foundation_manifest', paths.foundationManifest)
  const surface = safeJson(checks, 'surface_manifest', paths.surfaceManifest)
  const asset = safeJson(checks, 'asset_manifest_draft', paths.assetManifestDraft)
  const materialSeed = safeJson(checks, 'material_asset_seed', paths.materialAssetSeed)
  const routeSmoke = safeJson(checks, 'route_smoke_plan', paths.routeSmokePlan)
  const permitCoverage = safeJson(checks, 'permit_coverage', paths.permitCoverage)
  const browserPrecheck = safeJson(checks, 'browser_component_precheck', paths.browserComponentPrecheck)

  for (const [id, manifest] of Object.entries({
    readiness,
    decisionBrief,
    proposal,
    candidates,
    foundation,
    surface,
    asset,
    materialSeed,
    routeSmoke,
    permitCoverage,
    browserPrecheck
  })) {
    validateNonPromotion(checks, id, manifest)
  }

  if (readiness) {
    addCheck(checks, 'readiness_status', readiness.status === 'target_lock_readiness_review', {
      actual: readiness.status
    })
    addCheck(checks, 'readiness_decision_state', readiness.decisionReadiness === 'ready_for_user_decision', {
      actual: readiness.decisionReadiness
    })
    addCheck(checks, 'readiness_missing_user_decision_only', (readiness.checklistReview || []).some((item) => item.readiness === 'missing_user_decision'), {
      checklistReadiness: (readiness.checklistReview || []).map((item) => item.readiness)
    })
  }

  if (decisionBrief) {
    addCheck(checks, 'decision_brief_status', decisionBrief.status === 'target_lock_decision_brief', {
      actual: decisionBrief.status
    })
    addCheck(checks, 'decision_brief_target', decisionBrief.recommendedTargetName === 'A-Cockpit + B-Ledger + C-Captain', {
      actual: decisionBrief.recommendedTargetName
    })
    addCheck(checks, 'decision_brief_first_surface', decisionBrief.recommendedFirstSurface === 'news_list_detail', {
      actual: decisionBrief.recommendedFirstSurface
    })
    addCheck(checks, 'decision_brief_material_seed', decisionBrief.materialAssetSeed?.expectedStatus === 'material_asset_seed_ready', {
      actual: decisionBrief.materialAssetSeed?.expectedStatus
    })
    addCheck(checks, 'decision_brief_source_map_seed', decisionBrief.realWowSourceMapSeed?.expectedStatus === 'real_wow_source_map_seed_ready', {
      actual: decisionBrief.realWowSourceMapSeed?.expectedStatus
    })
    addCheck(checks, 'decision_brief_runtime_gates', includesAll(decisionBrief.requiredRuntimeGates, [
      'production_asset_manifest_preflight',
      'real_wow_source_map_preflight',
      'page_adoption_preflight',
      'visual_acceptance_preflight',
      'route_smoke_execution_preflight',
      'devtools_action_ledger_preflight'
    ]).length === 0, {
      missingGates: includesAll(decisionBrief.requiredRuntimeGates, [
        'production_asset_manifest_preflight',
        'real_wow_source_map_preflight',
        'page_adoption_preflight',
        'visual_acceptance_preflight',
        'route_smoke_execution_preflight',
        'devtools_action_ledger_preflight'
      ])
    })
  }

  if (proposal) {
    addCheck(checks, 'proposal_status', proposal.status === 'target_lock_proposal', { actual: proposal.status })
    addCheck(checks, 'proposal_hybrid_name', proposal.hybrid?.name === 'A-Cockpit + B-Ledger + C-Captain', {
      actual: proposal.hybrid?.name
    })
    addCheck(checks, 'proposal_owners_cover_foundation', includesAll(proposal.foundationOwners, REQUIRED_OWNERS).length === 0, {
      missingOwners: includesAll(proposal.foundationOwners, REQUIRED_OWNERS)
    })
    addCheck(checks, 'proposal_material_classes', includesAll(proposal.assetBoundary?.productionMaterialClasses, REQUIRED_MATERIAL_CLASSES).length === 0, {
      missingMaterialClasses: includesAll(proposal.assetBoundary?.productionMaterialClasses, REQUIRED_MATERIAL_CLASSES)
    })
    addCheck(checks, 'proposal_contact_sheet_exists', exists(proposal.candidateContactSheet), {
      path: proposal.candidateContactSheet
    })
  }

  if (candidates) {
    const candidateIds = (candidates.candidates || []).map((candidate) => candidate.id)
    addCheck(checks, 'candidates_status', candidates.status === 'target_candidate_reference', { actual: candidates.status })
    addCheck(checks, 'candidates_have_abc', includesAll(candidateIds, ['A', 'B', 'C']).length === 0, {
      candidateIds
    })
    addCheck(checks, 'candidates_key_surface_visuals', includesAll(candidates.surfaces, REQUIRED_CANDIDATE_SURFACES).length === 0, {
      missingSurfaces: includesAll(candidates.surfaces, REQUIRED_CANDIDATE_SURFACES)
    })
    addCheck(checks, 'candidates_contact_sheet_exists', exists(candidates.contactSheet), {
      path: candidates.contactSheet
    })
  }

  if (foundation) {
    addCheck(checks, 'foundation_owner_contracts_cover_all', includesAll(foundation.foundationOwners, REQUIRED_OWNERS).length === 0, {
      missingOwners: includesAll(foundation.foundationOwners, REQUIRED_OWNERS)
    })
  }

  if (surface) {
    addCheck(checks, 'surface_contract_manifest_exists', surface.status === 'surface_owner_contract_draft' || surface.status === 'component_contract_draft', {
      actual: surface.status
    })
  }

  if (asset) {
    addCheck(checks, 'asset_manifest_status', asset.status === 'asset_manifest_draft', { actual: asset.status })
    addCheck(checks, 'asset_allowed_material_classes', includesAll(asset.allowedProductionMaterialClasses, REQUIRED_MATERIAL_CLASSES).length === 0, {
      missingMaterialClasses: includesAll(asset.allowedProductionMaterialClasses, REQUIRED_MATERIAL_CLASSES)
    })
    addCheck(checks, 'asset_forbids_imagegen_real_objects', (asset.realSourceMap?.forbiddenSourceClasses || []).includes('imagegen'), {
      forbiddenSourceClasses: asset.realSourceMap?.forbiddenSourceClasses || []
    })
  }

  if (materialSeed) {
    const assetSeeds = materialSeed.assetSeeds || []
    const coveredClasses = unique(assetSeeds.map((seed) => seed.class).filter(Boolean))
    const coveredSurfaces = unique(assetSeeds.flatMap((seed) => seed.allowedSurfaces || []))
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

    addCheck(checks, 'material_seed_status', materialSeed.status === 'material_asset_seed_ready' && materialSeed.materialAssetSeedReady === true, {
      actual: materialSeed.status,
      materialAssetSeedReady: materialSeed.materialAssetSeedReady
    })
    addCheck(checks, 'material_seed_not_production_manifest', materialSeed.productionManifest === false, {
      productionManifest: materialSeed.productionManifest
    })
    addCheck(checks, 'material_seed_class_coverage', includesAll(coveredClasses, REQUIRED_MATERIAL_CLASSES).length === 0, {
      missingMaterialClasses: includesAll(coveredClasses, REQUIRED_MATERIAL_CLASSES)
    })
    addCheck(checks, 'material_seed_surface_coverage', includesAll(coveredSurfaces, REQUIRED_CORE_SURFACES).length === 0, {
      missingSurfaces: includesAll(coveredSurfaces, REQUIRED_CORE_SURFACES)
    })
    addCheck(checks, 'material_seed_semantic_safety', unsafeSeeds.length === 0, {
      unsafeSeedIds: unsafeSeeds.map((seed) => seed.id)
    })
    addCheck(checks, 'material_seed_package_budget', (
      materialSeed.packageBudget &&
      materialSeed.packageBudget.currentKb <= materialSeed.packageBudget.maxKb &&
      materialSeed.packageBudget.maxKb <= 512
    ), {
      packageBudget: materialSeed.packageBudget || null
    })
  }

  if (routeSmoke) {
    const sceneSurfaces = unique((routeSmoke.scenes || []).map((scene) => scene.surface))
    addCheck(checks, 'route_smoke_status', routeSmoke.status === 'route_smoke_plan_draft', { actual: routeSmoke.status })
    addCheck(checks, 'route_smoke_scene_count', (routeSmoke.scenes || []).length >= 27, {
      sceneCount: (routeSmoke.scenes || []).length
    })
    addCheck(checks, 'route_smoke_surface_coverage', includesAll(sceneSurfaces, REQUIRED_ROUTE_SMOKE_SURFACES).length === 0, {
      missingSurfaces: includesAll(sceneSurfaces, REQUIRED_ROUTE_SMOKE_SURFACES)
    })
    addCheck(checks, 'route_smoke_capture_safe_policy', routeSmoke.devtoolsPolicy?.requiresCaptureSafe === true, {
      requiresCaptureSafe: routeSmoke.devtoolsPolicy?.requiresCaptureSafe
    })
  }

  if (permitCoverage) {
    const permitSurfaces = (permitCoverage.knownPermitDrafts || []).map((permit) => permit.surface)
    const activePermits = (permitCoverage.knownPermitDrafts || []).filter((permit) => permit.active)
    const missingDraftFiles = (permitCoverage.knownPermitDrafts || [])
      .filter((permit) => !exists(permit.path))
      .map((permit) => permit.path)
    addCheck(checks, 'permit_coverage_status', permitCoverage.status === 'permit_coverage_matrix_draft', {
      actual: permitCoverage.status
    })
    addCheck(checks, 'permit_coverage_core_surfaces', includesAll(permitSurfaces, REQUIRED_CORE_SURFACES).length === 0, {
      missingSurfaces: includesAll(permitSurfaces, REQUIRED_CORE_SURFACES)
    })
    addCheck(checks, 'permit_coverage_no_active_permit_yet', activePermits.length === 0, {
      activePermits: activePermits.map((permit) => permit.surface)
    })
    addCheck(checks, 'permit_draft_files_exist', missingDraftFiles.length === 0, {
      missingDraftFiles
    })
  }

  if (browserPrecheck) {
    const viewportIds = (browserPrecheck.viewports || []).map((viewport) => viewport.id)
    addCheck(checks, 'browser_precheck_status', browserPrecheck.status === 'browser_component_precheck', {
      actual: browserPrecheck.status
    })
    addCheck(checks, 'browser_precheck_viewports', includesAll(viewportIds, ['compact', 'standard', 'large']).length === 0, {
      viewportIds
    })
    addCheck(checks, 'browser_precheck_failures_empty', (browserPrecheck.failures || []).length === 0, {
      failures: browserPrecheck.failures || []
    })
    addCheck(checks, 'browser_precheck_no_horizontal_overflow', (browserPrecheck.measurements || []).every((measurement) => measurement.document?.horizontalOverflow === 0), {
      overflows: (browserPrecheck.measurements || []).map((measurement) => ({
        viewport: measurement.viewport?.id,
        horizontalOverflow: measurement.document?.horizontalOverflow
      }))
    })
  }

  const failedChecks = checks.filter((check) => check.status === 'fail')
  const readyForUserDecision = failedChecks.length === 0

  return {
    status: readyForUserDecision ? 'target_lock_readiness_ready' : 'target_lock_readiness_invalid',
    readyForUserDecision,
    targetLocked: false,
    activePermit: false,
    pageIntegration: false,
    runtimeVerified: false,
    finalAccepted: false,
    devtoolsTouched: false,
    recommendedTargetName: readiness?.recommendedTargetName || proposal?.hybrid?.name || null,
    requiredCoreSurfaces: REQUIRED_CORE_SURFACES,
    requiredOwners: REQUIRED_OWNERS,
    checkCount: checks.length,
    failedCheckCount: failedChecks.length,
    failedChecks,
    checks,
    nextRequiredEvidence: readyForUserDecision
      ? 'explicit user target-lock confirmation or written modification'
      : 'repair target-lock readiness evidence before asking for decision'
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
    process.stdout.write(`readyForUserDecision=${report.readyForUserDecision}\n`)
    process.stdout.write(`failedCheckCount=${report.failedCheckCount}\n`)
    if (report.failedCheckCount > 0) {
      process.stdout.write(`failedChecks=${report.failedChecks.map((check) => check.id).join(',')}\n`)
    }
  }

  if (flags.has('--require-ready') && !report.readyForUserDecision) {
    process.exitCode = EXIT_NOT_READY
  }
}

main()
